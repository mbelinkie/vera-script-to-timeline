"""#300: qualify same-rate normalization from an independent FFmpeg clock."""

from __future__ import annotations

import json
import math
import struct
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import vera_timeline_agent.narration.measure as measure_module
from issue182_fixture import build_cache, frozen_block, wav_bytes
from vera_timeline_agent.narration.measure import (
    DEFAULT_PARAMETERS,
    LoadedAsset,
    MeasurementError,
    estimate_lag,
    load_asset,
    measure_asset,
    read_wav,
)
from vera_timeline_agent.narration.models import identity_hash, sha256_bytes
from vera_timeline_agent.narration.normalize import (
    DEFAULT_PROFILE_ID,
    NORMALIZER_VERSION,
    MediaToolError,
    Normalizer,
)

RATE = 48_000
TOOL = "sha256:" + "5" * 64


def _clock_trace(
    *,
    input_frames: list[tuple[int, int, int]] | None = None,
    output_frames: list[tuple[int, int, int]] | None = None,
    mode: str = "linear",
    conversion_rate: int = RATE,
    include_frames: bool = True,
) -> str:
    lines = [
        json.dumps({"input_i": "-20.0", "normalization_type": mode}),
        "ch:1 chl:mono fmt:s16 r:48000Hz -> "
        f"ch:1 chl:mono fmt:s32 r:{conversion_rate}Hz",
    ]
    if include_frames:
        frames = {
            "input": input_frames or [(0, 0, 4), (1, 4, 4)],
            "output": output_frames or [(0, 0, 4), (1, 4, 4)],
        }
        for label, rows in frames.items():
            for index, pts, count in rows:
                lines.append(
                    f"[ashowinfo@clock_{label} @ 00000001] n:{index} "
                    f"pts:{pts} pts_time:{pts / RATE:.6f} fmt:s32 "
                    f"channels:1 chlayout:mono rate:48000 nb_samples:{count} "
                    "checksum:00000000"
                )
    return "\n".join(lines)


def _clock_normalizer(*, profile_id: str = DEFAULT_PROFILE_ID) -> Normalizer:
    normalizer = Normalizer(profile_id=profile_id)
    # Synthetic stderr is qualified against the exact runtime version whose
    # verbose frame format is under test. Avoid probing the host tools here.
    normalizer._version = "8.1.2"
    normalizer._fingerprint = TOOL
    return normalizer


@pytest.mark.parametrize(
    "stderr",
    [
        pytest.param(_clock_trace(mode="dynamic"), id="dynamic-loudnorm"),
        pytest.param(_clock_trace(include_frames=False), id="missing-frame-trace"),
        pytest.param(
            _clock_trace(conversion_rate=44_100), id="rate-conversion-in-graph"
        ),
        pytest.param(
            _clock_trace(input_frames=[(0, 1, 4), (1, 5, 4)]),
            id="nonzero-input-pts",
        ),
        pytest.param(
            _clock_trace(output_frames=[(0, 1, 4), (1, 5, 4)]),
            id="delayed-output-pts",
        ),
        pytest.param(
            _clock_trace(input_frames=[(0, 0, 4), (2, 4, 4)]),
            id="frame-count-discontinuity",
        ),
    ],
)
def test_clock_refuses_unqualified_or_discontinuous_traces(stderr: str) -> None:
    with pytest.raises(MediaToolError):
        _clock_normalizer()._verify_clock(stderr, source_samples=8, padding_samples=0)


def test_clock_requires_padding_to_follow_the_complete_source_trace() -> None:
    stderr = _clock_trace(
        input_frames=[(0, 0, 4), (1, 4, 4)],
        # Total duration is right, but the second source frame has been extended
        # with padding before the input clock has ended.
        output_frames=[(0, 0, 4), (1, 4, 5), (2, 9, 1)],
    )

    with pytest.raises(MediaToolError, match="does not admit padding"):
        _clock_normalizer()._verify_clock(stderr, source_samples=8, padding_samples=2)


def test_clock_refuses_non_default_normalization_profile() -> None:
    with pytest.raises(MediaToolError, match="unqualified normalization profile"):
        _clock_normalizer(profile_id="test")._verify_clock(
            _clock_trace(), source_samples=8, padding_samples=0
        )


def test_clock_accepts_contiguous_unpadded_source_coordinates() -> None:
    stderr = _clock_trace()

    clock = _clock_normalizer()._verify_clock(
        stderr, source_samples=8, padding_samples=0
    )

    assert clock["method"] == "same_rate_linear_filter_clock/v1"
    assert clock["originSamples"] == clock["delaySamples"] == 0
    assert clock["ffmpegVersion"] == "8.1.2"
    assert clock["sourceSamples"] == 8
    assert clock["outputSamples"] == 8
    assert clock["tailPaddingSamples"] == 0
    assert clock["framesVerified"] == 2


def _raw_samples(count: int = 2400) -> list[int]:
    return [
        round(
            8000 * math.sin(2 * math.pi * index / 53)
            + 1700 * math.sin(2 * math.pi * index / 17)
        )
        for index in range(count)
    ]


def _normalization_identity(loaded: LoadedAsset) -> str:
    return identity_hash(
        {
            "recordVersion": "normalization-key/v1",
            "rawAudioHash": loaded.asset.raw_audio_hash,
            "rawTimingHash": loaded.asset.raw_timing_hash,
            "profileId": loaded.asset.normalization_profile,
            "toolFingerprint": loaded.asset.tool_fingerprint,
            "normalizerVersion": NORMALIZER_VERSION,
        }
    )


def _loaded_for_replay(root: Path, raw: bytes, output: bytes) -> LoadedAsset:
    cache, _asset, asset_key = build_cache(root, raw_sample_rate=RATE)
    loaded = load_asset(cache, asset_key)
    _samples, rate, channels, frames = read_wav(output)
    asset = replace(
        loaded.asset,
        raw_audio_hash=sha256_bytes(raw),
        normalized_audio_hash=sha256_bytes(output),
        normalization_profile=DEFAULT_PROFILE_ID,
        tool_fingerprint=TOOL,
        duration_samples=frames,
        duration_ms=frames * 1000 // rate,
        sample_rate=rate,
        channels=channels,
        sample_format="s16",
    )
    prepared = replace(
        loaded,
        asset=asset,
        wav_bytes=output,
        raw_pcm=raw,
        raw_sample_rate=RATE,
    )
    return replace(
        prepared,
        asset=replace(
            prepared.asset, normalization_hash=_normalization_identity(prepared)
        ),
    )


def _install_replay_normalizer(
    monkeypatch: pytest.MonkeyPatch,
    expected_wav: bytes,
    *,
    fingerprint: str = TOOL,
) -> None:
    class ReplayNormalizer:
        def __init__(self, *, profile_id: str) -> None:
            self.profile_id = profile_id
            self.tool_fingerprint = fingerprint

        def normalize_pcm(
            self,
            audio: bytes,
            *,
            sample_rate: int,
            channels: int,
            audit_clock: bool = False,
        ) -> SimpleNamespace:
            assert audio
            assert sample_rate == RATE
            assert channels == 1
            assert audit_clock
            return SimpleNamespace(
                wav_bytes=expected_wav,
                clock={
                    "method": "same_rate_linear_filter_clock/v1",
                    "tailPaddingSamples": 0,
                    "framesVerified": 3,
                },
            )

    monkeypatch.setattr(measure_module, "Normalizer", ReplayNormalizer)


@pytest.mark.parametrize(
    "tamper",
    [
        pytest.param("shift", id="whole-output-shift"),
        pytest.param("insert-delete", id="same-length-insert-delete"),
        pytest.param("duplicate", id="same-length-duplicate"),
        pytest.param("local-drift", id="local-clock-drift"),
        pytest.param("same-sign", id="same-sign-amplitude-change"),
    ],
)
def test_exact_replay_rejects_same_length_pcm_tampering(
    tamper: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_samples = _raw_samples()
    raw = struct.pack(f"<{len(raw_samples)}h", *raw_samples)
    expected_samples = [round(sample * 0.72) for sample in raw_samples]
    if tamper == "shift":
        observed_samples = [0, *expected_samples[:-1]]
    elif tamper == "insert-delete":
        observed_samples = expected_samples.copy()
        observed_samples.insert(400, observed_samples[400])
        del observed_samples[1401]
    elif tamper == "duplicate":
        observed_samples = expected_samples.copy()
        observed_samples[1100] = observed_samples[1099]
    elif tamper == "local-drift":
        split = len(expected_samples) // 2
        observed_samples = [
            *expected_samples[:split],
            0,
            0,
            *expected_samples[split:-2],
        ]
    else:
        observed_samples = [
            int(math.copysign(max(0, round(abs(sample) * 0.9)), sample))
            for sample in expected_samples
        ]
    assert len(observed_samples) == len(expected_samples)
    assert observed_samples != expected_samples

    expected_wav = wav_bytes(expected_samples)
    observed_wav = wav_bytes(observed_samples)
    loaded = _loaded_for_replay(tmp_path, raw, observed_wav)
    _install_replay_normalizer(monkeypatch, expected_wav)

    with pytest.raises(MeasurementError, match="PCM differs"):
        measure_module._verify_normalization_transform(loaded, None)


def test_transform_gate_rejects_wrong_tool_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_samples = _raw_samples()
    raw = struct.pack(f"<{len(raw_samples)}h", *raw_samples)
    output = wav_bytes([round(sample * 0.72) for sample in raw_samples])
    loaded = _loaded_for_replay(tmp_path, raw, output)
    _install_replay_normalizer(monkeypatch, output, fingerprint="sha256:" + "6" * 64)

    with pytest.raises(MeasurementError, match="media tool changed"):
        measure_module._verify_normalization_transform(loaded, None)


def test_transform_gate_rejects_wrong_normalization_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_samples = _raw_samples()
    raw = struct.pack(f"<{len(raw_samples)}h", *raw_samples)
    output = wav_bytes([round(sample * 0.72) for sample in raw_samples])
    loaded = _loaded_for_replay(tmp_path, raw, output)
    loaded = replace(
        loaded,
        asset=replace(loaded.asset, normalization_hash="sha256:" + "9" * 64),
    )
    _install_replay_normalizer(monkeypatch, output)

    with pytest.raises(MeasurementError, match="normalization identity differs"):
        measure_module._verify_normalization_transform(loaded, None)


@pytest.mark.parametrize("binding", ["raw", "output"])
def test_measurement_rejects_stale_raw_or_output_hash_binding(
    binding: str, tmp_path: Path
) -> None:
    cache, _asset, asset_key = build_cache(tmp_path)
    loaded = load_asset(cache, asset_key)
    if binding == "raw":
        loaded = replace(loaded, raw_pcm=loaded.raw_pcm + b"\x00\x00")
        expected = "raw provider PCM hash differs"
    else:
        loaded = replace(loaded, wav_bytes=loaded.wav_bytes + b"stale")
        expected = "normalized audio hash differs"

    with pytest.raises(MeasurementError, match=expected):
        measure_asset(
            loaded,
            frozen_block(),
            artifact_locator="v1/measurements/issue300.json",
        )


def _ambiguous_positive_tone(samples: int) -> list[int]:
    # This four-second 100 Hz waveform stays positive at every sample while
    # repeating exactly within the sample-correlation search window.
    return [
        round(2_000 + 1_000 * math.sin(2 * math.pi * 100 * index / RATE))
        for index in range(samples)
    ]


@pytest.mark.slow
def test_real_clock_qualifies_ambiguous_same_rate_audio_and_emits_artifact(
    tmp_path: Path,
) -> None:
    normalizer = Normalizer()
    if normalizer.ffmpeg_version != "8.1.2":
        pytest.skip("clock trace is qualified for FFmpeg 8.1.2")

    raw_samples = _ambiguous_positive_tone(RATE * 4)
    raw = struct.pack(f"<{len(raw_samples)}h", *raw_samples)
    normalized = normalizer.normalize_pcm(
        raw, sample_rate=RATE, channels=1, audit_clock=True
    )
    normalized_samples, rate, channels, frames = read_wav(normalized.wav_bytes)
    assert rate == RATE and channels == 1 and frames == len(raw_samples)
    assert normalized.clock is not None
    assert normalized.clock["originSamples"] == 0
    assert normalized.clock["delaySamples"] == 0
    assert normalized.clock["sourceSamples"] == len(raw_samples)

    with pytest.raises(MeasurementError):
        estimate_lag(raw, RATE, normalized_samples, DEFAULT_PARAMETERS)

    cache, _asset, asset_key = build_cache(tmp_path, raw_sample_rate=RATE)
    loaded = load_asset(cache, asset_key)
    asset = replace(
        loaded.asset,
        raw_audio_hash=sha256_bytes(raw),
        normalized_audio_hash=sha256_bytes(normalized.wav_bytes),
        normalization_profile=normalized.profile_id,
        tool_fingerprint=normalized.tool_fingerprint,
        duration_samples=normalized.duration_samples,
        duration_ms=normalized.duration_ms,
        sample_rate=normalized.sample_rate,
        channels=normalized.channels,
        sample_format=normalized.sample_format,
    )
    loaded = replace(loaded, asset=asset, raw_pcm=raw, raw_sample_rate=RATE)
    loaded = replace(
        loaded,
        wav_bytes=normalized.wav_bytes,
        asset=replace(
            loaded.asset,
            normalization_hash=_normalization_identity(loaded),
        ),
    )

    measured = measure_asset(
        loaded,
        frozen_block(),
        artifact_locator="v1/measurements/issue300.json",
    )
    lag = measured.artifact["lag"]
    assert lag["method"] == "qualified_linear_transform"
    assert lag["samples"] == 0
    assert lag["transformVerification"]["clock"] == normalized.clock
    assert lag["transformVerification"]["method"] == "reproduced_pcm"
