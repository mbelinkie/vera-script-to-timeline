"""#297: sample-accurate verification of narration normalization alignment."""

from __future__ import annotations

import math
import random
import struct
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import vera_timeline_agent.narration.measure as measure_module
from issue182_fixture import build_cache, wav_bytes
from vera_timeline_agent.narration.measure import (
    DEFAULT_PARAMETERS,
    Lag,
    LoadedAsset,
    MeasurementError,
    estimate_lag,
    load_asset,
    read_wav,
)
from vera_timeline_agent.narration.models import sha256_bytes
from vera_timeline_agent.narration.normalize import Normalizer

RATE = 48_000
SAMPLE_COUNT = RATE * 9 // 10


def _speech_like(
    seed: int = 297,
    sample_count: int = SAMPLE_COUNT,
    *,
    pad_silence: bool = True,
    fade_edges: bool = True,
) -> list[int]:
    """Return deterministic, band-limited noise with a varying speech-like gain."""
    rng = random.Random(seed)
    padding = RATE // 40 if pad_silence else 0
    core_count = sample_count - 2 * padding
    white = [rng.uniform(-1.0, 1.0) for _ in range(core_count)]
    # A short triangular FIR removes white-noise spikes while retaining unique
    # sample detail for alignment checks.
    weights = (1, 2, 3, 4, 5, 4, 3, 2, 1)
    weight_sum = sum(weights)
    filtered: list[float] = []
    for i in range(core_count):
        filtered.append(
            sum(
                weight * white[j]
                for weight, j in zip(weights, range(i - 4, i + 5), strict=True)
                if 0 <= j < core_count
            )
            / weight_sum
        )

    # Random gain knots every 10 ms create changing local levels without
    # repeating a phrase-sized envelope.
    knot_count = math.ceil(core_count / (RATE // 100)) + 1
    gains = [rng.uniform(0.18, 0.9) for _ in range(knot_count)]
    knot_samples = RATE // 100
    output: list[int] = []
    for i, sample in enumerate(filtered):
        knot, offset = divmod(i, knot_samples)
        fraction = offset / knot_samples
        gain = gains[knot] * (1.0 - fraction) + gains[knot + 1] * fraction
        output.append(round(sample * gain * 54_000))
    if pad_silence:
        return [0] * padding + output + [0] * padding
    if not fade_edges:
        return output
    fade_samples = RATE // 100
    for i in range(fade_samples):
        fade = 0.5 - 0.5 * math.cos(math.pi * i / fade_samples)
        output[i] = round(output[i] * fade)
        output[-i - 1] = round(output[-i - 1] * fade)
    return output


def _pcm(samples: list[int]) -> bytes:
    return struct.pack(f"<{len(samples)}h", *samples)


def _shift(samples: list[int], lag_samples: int) -> list[int]:
    """Shift normalized audio; positive lag means it starts later than raw."""
    if lag_samples > 0:
        return [0] * lag_samples + samples[:-lag_samples]
    if lag_samples < 0:
        shift = -lag_samples
        return samples[shift:] + [0] * shift
    return samples.copy()


def _insert_then_delete(samples: list[int], insert_at: int, gap: int) -> list[int]:
    edited = samples.copy()
    edited.insert(insert_at, edited[insert_at])
    del edited[insert_at + gap]
    return edited


def _estimate(raw: list[int], normalized: list[int]) -> Lag:
    return estimate_lag(_pcm(raw), RATE, normalized, DEFAULT_PARAMETERS)


def _loaded_asset_48k(
    root: Path,
    raw: list[int],
    wav: bytes,
    *,
    normalization_profile: str = "test",
    sample_format: str = "s16",
) -> LoadedAsset:
    cache, _asset, asset_key = build_cache(root, raw_sample_rate=RATE)
    loaded = load_asset(cache, asset_key)
    _samples, rate, channels, frames = read_wav(wav)
    raw_pcm = _pcm(raw)
    asset = replace(
        loaded.asset,
        normalization_profile=normalization_profile,
        raw_audio_hash=sha256_bytes(raw_pcm),
        normalized_audio_hash=sha256_bytes(wav),
        duration_samples=frames,
        duration_ms=frames * 1000 // rate,
        sample_rate=rate,
        channels=channels,
        sample_format=sample_format,
    )
    return replace(
        loaded,
        asset=asset,
        wav_bytes=wav,
        raw_pcm=raw_pcm,
        raw_sample_rate=rate,
    )


def _mock_normalizer(
    monkeypatch: pytest.MonkeyPatch,
    *,
    raw_pcm: bytes,
    expected_wav: bytes,
    profile_id: str = "test",
) -> None:
    class DeterministicNormalizer:
        tool_fingerprint = "sha256:" + "5" * 64

        def __init__(self, *, profile_id: str) -> None:
            assert profile_id == expected_profile

        def normalize_pcm(
            self, audio: bytes, *, sample_rate: int, channels: int
        ) -> SimpleNamespace:
            assert audio == raw_pcm
            assert sample_rate == RATE
            assert channels == 1
            return SimpleNamespace(wav_bytes=expected_wav)

    expected_profile = profile_id
    monkeypatch.setattr(measure_module, "Normalizer", DeterministicNormalizer)


@pytest.mark.parametrize(
    ("lag_samples", "normalizer"),
    [
        (0, lambda sample: round(sample * 0.63)),
        (0, lambda sample: round(math.copysign(abs(sample) ** 0.88, sample))),
        (47, lambda sample: sample),
        (-71, lambda sample: sample),
    ],
)
def test_independent_speech_like_windows_verify_exact_sample_lag(
    lag_samples: int, normalizer: Callable[[int], int]
) -> None:
    raw = _speech_like()
    normalized = _shift([normalizer(sample) for sample in raw], lag_samples)

    lag = _estimate(raw, normalized)

    assert lag.samples == lag_samples
    assert lag.method == "sample_correlation"
    assert lag.uncertainty_samples == 0
    assert lag.windows_verified >= 3


def test_unrelated_nonperiodic_audio_is_refused() -> None:
    raw = _speech_like(seed=297)
    normalized = _speech_like(seed=298)

    with pytest.raises(MeasurementError):
        _estimate(raw, normalized)


def test_periodic_signal_with_many_equivalent_lags_is_refused() -> None:
    raw = [
        round(18_000 * math.sin(2 * math.pi * 440 * i / RATE))
        for i in range(SAMPLE_COUNT)
    ]

    with pytest.raises(MeasurementError):
        _estimate(raw, raw.copy())


def test_silence_is_refused() -> None:
    silence = [0] * SAMPLE_COUNT

    with pytest.raises(MeasurementError):
        _estimate(silence, silence.copy())


def test_local_timing_drift_across_audio_windows_is_refused() -> None:
    raw = _speech_like()
    split = SAMPLE_COUNT // 2
    shift = 36
    normalized = raw[:split] + [0] * shift + raw[split:-shift]

    with pytest.raises(MeasurementError):
        _estimate(raw, normalized)


def test_local_insert_then_delete_inside_one_check_window_is_refused() -> None:
    raw = _speech_like()
    check_samples = RATE * 5 // 1000
    window_start = (SAMPLE_COUNT // 2 // check_samples) * check_samples
    insert_at = window_start + check_samples // 8
    delete_at = window_start + check_samples * 7 // 8
    normalized = _insert_then_delete(raw, insert_at, delete_at - insert_at)

    assert len(normalized) == len(raw)
    assert insert_at // check_samples == (delete_at - 1) // check_samples
    assert normalized[:insert_at] == raw[:insert_at]
    assert normalized[delete_at:] == raw[delete_at:]
    with pytest.raises(MeasurementError):
        _estimate(raw, normalized)


def test_transform_gate_refuses_insert_delete_across_check_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = _speech_like()
    check_samples = RATE * 5 // 1000
    boundary = (SAMPLE_COUNT // 2 // check_samples) * check_samples
    insert_at = boundary - 20
    delete_at = boundary + 20
    expected_samples = [round(sample * 0.63) for sample in raw]
    normalized = _insert_then_delete(expected_samples, insert_at, delete_at - insert_at)

    assert len(normalized) == len(expected_samples)
    assert insert_at // check_samples == boundary // check_samples - 1
    assert delete_at // check_samples == boundary // check_samples
    assert normalized[:insert_at] == expected_samples[:insert_at]
    assert normalized[delete_at:] == expected_samples[delete_at:]
    lag = estimate_lag(_pcm(raw), RATE, normalized, DEFAULT_PARAMETERS)
    assert lag.samples == 0
    expected_wav = wav_bytes(expected_samples)
    loaded = _loaded_asset_48k(tmp_path, raw, wav_bytes(normalized))
    _mock_normalizer(monkeypatch, raw_pcm=_pcm(raw), expected_wav=expected_wav)

    with pytest.raises(MeasurementError, match="PCM differs"):
        measure_module._verify_normalization_transform(loaded, lag)


@pytest.mark.parametrize("gap", [2, 4, 8, 12, 20])
def test_transform_gate_refuses_short_edits_accepted_by_correlation(
    gap: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = _speech_like()
    expected_samples = [round(sample * 0.63) for sample in raw]
    boundary = RATE * 675 // 1000
    insert_at = boundary - gap // 2
    normalized = _insert_then_delete(expected_samples, insert_at, gap)
    lag = estimate_lag(_pcm(raw), RATE, normalized, DEFAULT_PARAMETERS)
    assert lag.samples == 0

    expected_wav = wav_bytes(expected_samples)
    loaded = _loaded_asset_48k(tmp_path, raw, wav_bytes(normalized))
    _mock_normalizer(monkeypatch, raw_pcm=_pcm(raw), expected_wav=expected_wav)

    with pytest.raises(MeasurementError, match="PCM differs"):
        measure_module._verify_normalization_transform(loaded, lag)


@pytest.mark.parametrize("lag_samples", [0, 47, -71])
@pytest.mark.parametrize(
    "normalizer",
    [
        lambda sample: round(sample * 0.63),
        lambda sample: round(math.copysign(abs(sample) ** 0.88, sample)),
    ],
)
def test_transform_gate_accepts_reproduced_gain_or_compression(
    lag_samples: int,
    normalizer: Callable[[int], int],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _speech_like()
    expected_samples = [normalizer(sample) for sample in raw]
    normalized = _shift(expected_samples, lag_samples)
    lag = estimate_lag(_pcm(raw), RATE, normalized, DEFAULT_PARAMETERS)
    assert lag.samples == lag_samples

    expected_wav = wav_bytes(expected_samples)
    loaded = _loaded_asset_48k(tmp_path, raw, wav_bytes(normalized))
    _mock_normalizer(monkeypatch, raw_pcm=_pcm(raw), expected_wav=expected_wav)

    measure_module._verify_normalization_transform(loaded, lag)


@pytest.mark.parametrize("sample_count", [RATE * 9 // 10 + 1, RATE * 9 // 10 + 2])
def test_nonzero_final_sample_and_odd_length_preserve_true_zero_lag(
    sample_count: int,
) -> None:
    raw = _speech_like(sample_count=sample_count, pad_silence=False, fade_edges=False)
    normalized = [round(sample * 0.63) for sample in raw]

    assert len(raw) == sample_count
    assert all(raw[-5:])
    lag = _estimate(raw, normalized)

    assert lag.samples == 0
    assert lag.method == "sample_correlation"
    assert lag.uncertainty_samples == 0
    assert lag.windows_verified >= 3


@pytest.mark.parametrize("edit", ["insertion", "deletion"])
@pytest.mark.parametrize("edit_samples", [1, 37])
def test_sample_insertion_or_deletion_breaks_continuous_alignment(
    edit: str, edit_samples: int
) -> None:
    raw = _speech_like()
    split = SAMPLE_COUNT // 2
    if edit == "insertion":
        normalized = raw[:split] + [0] * edit_samples + raw[split:-edit_samples]
    else:
        normalized = raw[:split] + raw[split + edit_samples :] + [0] * edit_samples

    with pytest.raises(MeasurementError):
        _estimate(raw, normalized)


@pytest.mark.parametrize(
    "transform",
    [
        lambda samples: [-sample for sample in samples],
        lambda samples: list(reversed(samples)),
    ],
)
def test_polarity_inversion_and_time_reversal_are_refused(
    transform: Callable[[list[int]], list[int]],
) -> None:
    raw = _speech_like()

    with pytest.raises(MeasurementError):
        _estimate(raw, transform(raw))


@pytest.mark.slow
def test_real_normalizer_pcm24_output_verifies_zero_sample_lag(
    tmp_path: Path,
) -> None:
    raw = _speech_like(sample_count=RATE * 3 // 2, pad_silence=False)
    normalized = Normalizer().normalize_pcm(_pcm(raw), sample_rate=RATE, channels=1)
    samples, sample_rate, channels, frames = read_wav(normalized.wav_bytes)

    assert normalized.sample_format == "s32 (24 bit)"
    assert sample_rate == RATE
    assert channels == 1
    assert frames == len(raw)
    lag = estimate_lag(_pcm(raw), RATE, samples, DEFAULT_PARAMETERS)
    loaded = _loaded_asset_48k(
        tmp_path,
        raw,
        normalized.wav_bytes,
        normalization_profile=normalized.profile_id,
        sample_format=normalized.sample_format,
    )
    loaded = replace(
        loaded,
        asset=replace(loaded.asset, tool_fingerprint=normalized.tool_fingerprint),
    )

    assert lag.samples == 0
    assert lag.method == "sample_correlation"
    assert lag.uncertainty_samples == 0
    assert lag.windows_verified >= 3
    measure_module._verify_normalization_transform(loaded, lag)


def test_changed_media_tool_requires_cached_pcm_renormalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = _speech_like()
    wav = wav_bytes(raw)
    loaded = _loaded_asset_48k(tmp_path, raw, wav)
    _mock_normalizer(monkeypatch, raw_pcm=_pcm(raw), expected_wav=wav)
    monkeypatch.setattr(
        "vera_timeline_agent.narration.measure.Normalizer.tool_fingerprint",
        "sha256:" + "6" * 64,
    )
    with pytest.raises(MeasurementError, match=r"media tool changed.*re-normalize"):
        measure_module._verify_normalization_transform(loaded, Lag(0, 0.0, 1.0, 0))
