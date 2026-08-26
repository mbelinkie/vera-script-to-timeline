from __future__ import annotations

import math
import struct
from pathlib import Path

import pytest
from vera_timeline_agent.narration.normalize import MediaToolError, Normalizer


def sine_pcm(duration_seconds: float, *, sample_rate: int = 16000) -> bytes:
    samples = round(duration_seconds * sample_rate)
    return b"".join(
        struct.pack(
            "<h", round(9000 * math.sin(2 * math.pi * 440 * index / sample_rate))
        )
        for index in range(samples)
    )


def high_crest_pcm(duration_seconds: float, *, sample_rate: int = 16000) -> bytes:
    samples = round(duration_seconds * sample_rate)
    return b"".join(
        struct.pack(
            "<h",
            round(
                (2200 if index % (sample_rate // 4) >= 240 else 22000)
                * math.sin(2 * math.pi * 220 * index / sample_rate)
            ),
        )
        for index in range(samples)
    )


def test_two_pass_normalization_is_verified_and_same_tool_byte_identical(
    tmp_path: Path,
) -> None:
    normalizer = Normalizer()
    raw = sine_pcm(1.0)

    first = normalizer.normalize_pcm(raw, sample_rate=16000, channels=1)
    second = normalizer.normalize_pcm(raw, sample_rate=16000, channels=1)

    assert first.wav_bytes == second.wav_bytes
    assert first.sample_rate == 48000
    assert first.channels == 1
    assert first.sample_format == "s32 (24 bit)"
    assert first.duration_samples == 48000
    assert first.padding_samples == 0
    assert first.integrated_lufs == pytest.approx(-16.0, abs=0.3)
    assert first.true_peak_dbtp <= -1.4
    assert first.tool_fingerprint.startswith("sha256:")
    output = tmp_path / "normalized.wav"
    output.write_bytes(first.wav_bytes)
    assert normalizer.verify_wav(output).duration_samples == 48000


def test_short_audio_is_padded_only_to_minimum_measurable_duration() -> None:
    result = Normalizer().normalize_pcm(sine_pcm(0.1), sample_rate=16000, channels=1)

    assert result.duration_samples == 19200
    assert result.padding_samples == 14400
    assert result.integrated_lufs == pytest.approx(-16.0, abs=0.5)


def test_high_crest_dialogue_meets_loudness_and_true_peak_targets() -> None:
    result = Normalizer().normalize_pcm(
        high_crest_pcm(1.0), sample_rate=16000, channels=1
    )

    assert result.integrated_lufs == pytest.approx(-16.0, abs=0.5)
    assert result.true_peak_dbtp <= -1.5


@pytest.mark.parametrize(
    ("audio", "sample_rate", "channels", "message"),
    [
        (b"\x00\x00" * 100, 16000, 1, "silent"),
        (b"\x01", 16000, 1, "16-bit"),
        (b"\x01\x00" * 100, 0, 1, "sample rate"),
        (b"\x01\x00" * 100, 16000, 2, "mono"),
    ],
)
def test_corrupt_unsupported_or_silent_provider_media_fails(
    audio: bytes, sample_rate: int, channels: int, message: str
) -> None:
    with pytest.raises(MediaToolError, match=message):
        Normalizer().normalize_pcm(audio, sample_rate=sample_rate, channels=channels)


def test_placeholder_is_audible_deterministic_and_clearly_separate() -> None:
    normalizer = Normalizer()
    first = normalizer.placeholder("block-a")
    second = normalizer.placeholder("block-a")

    assert first.wav_bytes == second.wav_bytes
    assert first.duration_samples == 48000
    assert first.integrated_lufs > -40
