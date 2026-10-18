"""Bounded conversion of complete source-audio endpoints to a frame envelope."""

from __future__ import annotations

import hashlib
import io
import re
import wave
from fractions import Fraction
from typing import Any

_SAMPLE_RATE = 48_000
_MAX_WAV_BYTES = 128 * 1024 * 1024


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"invalid {label}")
    return value


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"invalid {label}")
    return value


def _ceil(value: Fraction) -> int:
    return -((-value.numerator) // value.denominator)


def endpoint_plan(
    event: dict[str, Any], audio_record: dict[str, Any], timeline_rate: Fraction
) -> tuple[int, int, int] | None:
    """Return exact sidecar sample edges and their integer-frame envelope if needed."""
    if not isinstance(timeline_rate, Fraction) or timeline_rate <= 0:
        raise ValueError("invalid timeline rate")
    event = _object(event, "event")
    audio_record = _object(audio_record, "audio record")
    audio = _object(event.get("audio"), "event audio")
    sample_range = _object(audio.get("sampleRange"), "source sample range")
    source_start = _integer(sample_range.get("startFrame"), "source sample start")
    source_end = _integer(
        sample_range.get("endFrame"), "source sample end", source_start + 1
    )
    mapping = _object(event.get("sourceTimeMapping"), "source time mapping")
    frame_map = _object(mapping.get("sourceFrameMap"), "source frame map")
    audio_mappings = frame_map.get("sourceAudioStreamMappings")
    if not isinstance(audio_mappings, list) or len(audio_mappings) != 1:
        raise ValueError("source audio must have one verified stream")
    source_rate = _integer(
        _object(audio_mappings[0], "source audio stream").get("sampleRate"),
        "source sample rate",
        1,
    )
    resampled_first = _integer(
        audio_record.get("resampledFirstSample"), "resampled first sample"
    )
    decoded_samples = _integer(audio_record.get("decodedSamples"), "decoded samples", 1)
    first_sample = (
        _ceil(Fraction(source_start * _SAMPLE_RATE, source_rate)) - resampled_first
    )
    exclusive_sample = (
        _ceil(Fraction(source_end * _SAMPLE_RATE, source_rate)) - resampled_first
    )
    if not 0 <= first_sample < exclusive_sample <= decoded_samples:
        raise ValueError("source interval exceeds the verified PCM sidecar")

    record = _object(event.get("recordRange"), "record range")
    record_start = _integer(record.get("startFrame"), "record start")
    record_end = _integer(record.get("endFrame"), "record end", record_start + 1)
    record_frames = record_end - record_start

    exact_start = (
        Fraction(source_start, source_rate) - Fraction(resampled_first, _SAMPLE_RATE)
    ) * timeline_rate
    exact_end = (
        Fraction(source_end, source_rate) - Fraction(resampled_first, _SAMPLE_RATE)
    ) * timeline_rate
    if exact_start.denominator == exact_end.denominator == 1:
        if (
            exact_start < 0
            or exact_end <= exact_start
            or exact_end - exact_start != record_frames
        ):
            raise ValueError("aligned source audio duration differs from record range")
        return None

    samples_per_frame = Fraction(_SAMPLE_RATE, 1) / timeline_rate
    if samples_per_frame.denominator != 1:
        raise ValueError("timeline frame does not map to integer PCM samples")
    frame_samples = samples_per_frame.numerator
    if exact_start.denominator != 1 or first_sample % frame_samples:
        raise ValueError("fractional source audio start is unsupported")
    if source_start != _integer(
        audio_record.get("sourceFirstSample"), "source first sample"
    ) or source_end != _integer(
        audio_record.get("sourceExclusiveSample"), "source exclusive sample", 1
    ):
        raise ValueError("fractional endpoint requires the complete prepared interval")

    exact_frames = Fraction(source_end - source_start, source_rate) * timeline_rate
    if _ceil(exact_frames) != record_frames:
        raise ValueError("record range does not round the selected source duration")
    envelope_samples = record_frames * frame_samples
    remainder = envelope_samples - (exclusive_sample - first_sample)
    if remainder < 0 or 2 * remainder >= frame_samples:
        raise ValueError("source endpoint is outside the bounded frame envelope")
    channels = _integer(audio_record.get("channels"), "audio channels", 1)
    if channels not in {1, 2}:
        raise ValueError("unsupported source audio channel count")
    if envelope_samples * channels * 3 > _MAX_WAV_BYTES - 64:
        raise ValueError("endpoint WAV exceeds the size bound")
    return first_sample, exclusive_sample, envelope_samples


def endpoint_wav(
    raw: bytes, plan: tuple[int, int, int], audio_record: dict[str, Any]
) -> bytes:
    """Copy the selected PCM24 samples and zero-fill only the frame envelope tail."""
    audio_record = _object(audio_record, "audio record")
    if not isinstance(raw, bytes) or len(raw) > _MAX_WAV_BYTES:
        raise ValueError("invalid or oversized source WAV")
    expected_hash = audio_record.get("contentHash")
    if (
        not isinstance(expected_hash, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", expected_hash) is None
        or hashlib.sha256(raw).hexdigest() != expected_hash.removeprefix("sha256:")
    ):
        raise ValueError("source WAV hash differs")
    if not isinstance(plan, tuple) or len(plan) != 3:
        raise ValueError("invalid endpoint plan")
    first_sample = _integer(plan[0], "endpoint start")
    exclusive_sample = _integer(plan[1], "endpoint end", first_sample + 1)
    envelope_samples = _integer(
        plan[2], "frame envelope", exclusive_sample - first_sample
    )
    channels = _integer(audio_record.get("channels"), "audio channels", 1)
    decoded_samples = _integer(audio_record.get("decodedSamples"), "decoded samples", 1)
    if channels not in {1, 2} or exclusive_sample > decoded_samples:
        raise ValueError("endpoint plan exceeds the verified PCM extent")
    if envelope_samples * channels * 3 > _MAX_WAV_BYTES - 64:
        raise ValueError("endpoint WAV exceeds the size bound")

    try:
        with wave.open(io.BytesIO(raw), "rb") as source:
            params = source.getparams()
            pcm = source.readframes(decoded_samples + 1)
    except (EOFError, OSError, wave.Error) as error:
        raise ValueError("source WAV is invalid") from error
    if (
        params.nchannels != channels
        or params.sampwidth != 3
        or params.framerate != _SAMPLE_RATE
        or params.nframes != decoded_samples
        or params.comptype != "NONE"
        or len(pcm) != decoded_samples * channels * 3
    ):
        raise ValueError("source WAV profile or decoded extent differs")

    frame_bytes = channels * 3
    selected = pcm[first_sample * frame_bytes : exclusive_sample * frame_bytes]
    padding_frames = envelope_samples - (exclusive_sample - first_sample)
    payload = selected + bytes(padding_frames * frame_bytes)
    output = io.BytesIO()
    with wave.open(output, "wb") as destination:
        destination.setparams((channels, 3, _SAMPLE_RATE, 0, "NONE", "not compressed"))
        destination.writeframes(payload)
    result = output.getvalue()
    if len(result) > _MAX_WAV_BYTES:
        raise ValueError("endpoint WAV exceeds the size bound")
    return result
