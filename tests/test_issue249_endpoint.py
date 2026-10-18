from __future__ import annotations

import hashlib
import io
import wave
from fractions import Fraction
from typing import Any

import pytest
from vera_timeline_agent.source_audio_endpoint import endpoint_plan, endpoint_wav


def _wav(pcm: bytes, *, channels: int, frames: int) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setparams((channels, 3, 48_000, frames, "NONE", "not compressed"))
        stream.writeframes(pcm)
    return output.getvalue()


def _event(seconds: int, record_frames: int) -> dict[str, Any]:
    samples = seconds * 48_000
    return {
        "kind": "source_audio",
        "audio": {"sampleRange": {"startFrame": 0, "endFrame": samples}},
        "sourceTimeMapping": {
            "sourceFrameMap": {"sourceAudioStreamMappings": [{"sampleRate": 48_000}]}
        },
        "recordRange": {"startFrame": 0, "endFrame": record_frames},
    }


@pytest.mark.parametrize(
    ("seconds", "record_frames", "remainder"), [(3, 72, 144), (10, 240, 480)]
)
@pytest.mark.parametrize("channels", [1, 2])
def test_complete_source_endpoint_is_copied_then_zero_filled(
    seconds: int, record_frames: int, remainder: int, channels: int
) -> None:
    selected_samples = seconds * 48_000
    decoded_samples = selected_samples + 2
    sample_frame = b"\x11\x22\x33" * channels
    trailing_frame = b"\xee\xad\xde" * channels
    pcm = sample_frame * selected_samples + trailing_frame * 2
    raw = _wav(pcm, channels=channels, frames=decoded_samples)
    audio_record = {
        "resampledFirstSample": 0,
        "sourceFirstSample": 0,
        "sourceExclusiveSample": selected_samples,
        "decodedSamples": decoded_samples,
        "channels": channels,
        "contentHash": "sha256:" + hashlib.sha256(raw).hexdigest(),
    }

    plan = endpoint_plan(
        _event(seconds, record_frames), audio_record, Fraction(24_000, 1001)
    )
    assert plan == (0, selected_samples, record_frames * 2002)
    output = endpoint_wav(raw, plan, audio_record)

    with wave.open(io.BytesIO(output), "rb") as stream:
        assert stream.getparams()[:4] == (channels, 3, 48_000, record_frames * 2002)
        rendered = stream.readframes(record_frames * 2002 + 1)
    frame_bytes = channels * 3
    copied_bytes = selected_samples * frame_bytes
    assert rendered[:copied_bytes] == pcm[:copied_bytes]
    assert rendered[copied_bytes:] == bytes(remainder * frame_bytes)
    assert trailing_frame * 2 not in rendered


def test_aligned_source_audio_keeps_existing_path_without_receipt_fields() -> None:
    event = {
        "audio": {"sampleRange": {"startFrame": 0, "endFrame": 2002}},
        "sourceTimeMapping": {
            "sourceFrameMap": {"sourceAudioStreamMappings": [{"sampleRate": 48_000}]}
        },
        "recordRange": {"startFrame": 0, "endFrame": 1},
    }
    assert (
        endpoint_plan(
            event,
            {"resampledFirstSample": 0, "decodedSamples": 2002},
            Fraction(24_000, 1001),
        )
        is None
    )


def test_exact_frame_edges_keep_legacy_fractional_pcm_support() -> None:
    event = {
        "audio": {"sampleRange": {"startFrame": 0, "endFrame": 8008}},
        "sourceTimeMapping": {
            "sourceFrameMap": {"sourceAudioStreamMappings": [{"sampleRate": 48_000}]}
        },
        "recordRange": {"startFrame": 0, "endFrame": 5},
    }
    assert (
        endpoint_plan(
            event,
            {"resampledFirstSample": 0, "decodedSamples": 8008},
            Fraction(30_000, 1001),
        )
        is None
    )


def test_fractional_endpoint_rejects_unaligned_start() -> None:
    event = _event(3, 72)
    event["audio"]["sampleRange"]["startFrame"] = 1
    with pytest.raises(ValueError, match="start"):
        endpoint_plan(
            event,
            {
                "resampledFirstSample": 0,
                "sourceFirstSample": 1,
                "sourceExclusiveSample": 144_000,
                "decodedSamples": 144_000,
                "channels": 1,
            },
            Fraction(24_000, 1001),
        )


def test_fractional_endpoint_rejects_a_rounded_but_not_exact_frame_start() -> None:
    event: dict[str, Any] = {
        "audio": {"sampleRange": {"startFrame": 1839, "endFrame": 134_139}},
        "sourceTimeMapping": {
            "sourceFrameMap": {"sourceAudioStreamMappings": [{"sampleRate": 44_100}]}
        },
        "recordRange": {"startFrame": 0, "endFrame": 72},
    }
    with pytest.raises(ValueError, match="start"):
        endpoint_plan(
            event,
            {
                "resampledFirstSample": 0,
                "sourceFirstSample": 1839,
                "sourceExclusiveSample": 134_139,
                "decodedSamples": 146_002,
                "channels": 1,
            },
            Fraction(24_000, 1001),
        )


def test_fractional_endpoint_requires_the_complete_prepared_interval() -> None:
    with pytest.raises(ValueError, match="complete prepared interval"):
        endpoint_plan(
            _event(3, 72),
            {
                "resampledFirstSample": 0,
                "sourceFirstSample": 0,
                "sourceExclusiveSample": 144_001,
                "decodedSamples": 144_001,
                "channels": 1,
            },
            Fraction(24_000, 1001),
        )


def test_fractional_endpoint_rejects_an_excess_record_envelope() -> None:
    with pytest.raises(ValueError, match="round the selected source duration"):
        endpoint_plan(
            _event(3, 73),
            {
                "resampledFirstSample": 0,
                "sourceFirstSample": 0,
                "sourceExclusiveSample": 144_000,
                "decodedSamples": 144_000,
                "channels": 1,
            },
            Fraction(24_000, 1001),
        )


def test_endpoint_wav_rejects_wrong_hash_and_wav_extent() -> None:
    pcm = b"\x12\x34\x56" * 10
    raw = _wav(pcm, channels=1, frames=10)
    plan = (0, 8, 10)
    record = {
        "contentHash": "sha256:" + "0" * 64,
        "decodedSamples": 10,
        "channels": 1,
    }
    with pytest.raises(ValueError, match="hash"):
        endpoint_wav(raw, plan, record)

    record["contentHash"] = "sha256:" + hashlib.sha256(raw).hexdigest()
    record["decodedSamples"] = 11
    with pytest.raises(ValueError, match="profile or decoded extent"):
        endpoint_wav(raw, plan, record)


def test_endpoint_wav_requires_pcm24_and_expected_channels() -> None:
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setparams((1, 2, 48_000, 10, "NONE", "not compressed"))
        stream.writeframes(b"\x12\x34" * 10)
    raw = output.getvalue()
    record = {
        "contentHash": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "decodedSamples": 10,
        "channels": 1,
    }
    with pytest.raises(ValueError, match="profile or decoded extent"):
        endpoint_wav(raw, (0, 8, 10), record)
