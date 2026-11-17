"""Conservative quiet-gap observations for a frozen narration timing map.

The detector binds every result to the delivered WAV bytes and reports only
quiet analysis windows between adjacent timing-map onsets. A reported window
is not an estimate of the preceding token's audible end and carries no claim
about onset or boundary accuracy.
"""

from __future__ import annotations

import hashlib
import sys
import wave
from array import array
from collections.abc import Mapping
from fractions import Fraction
from io import BytesIO
from itertools import pairwise
from typing import Any

SCHEMA_VERSION = "vera-speech-gaps/v1"
METHOD = "pcm_quiet_windows_between_onsets/v1"
DEFAULT_PARAMETERS: dict[str, int] = {
    "analysisWindowMs": 5,
    "analysisHopMs": 1,
    "quietThresholdDbfs": -42,
    "minimumQuietDurationMs": 30,
}
_HASH_PREFIX = "sha256:"


class SpeechGapError(ValueError):
    """The WAV or timing map cannot support a safe quiet-gap observation."""


def _is_positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _ceil_fraction(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def _wav_samples(wav_bytes: bytes) -> tuple[array[int], int, int, int, int]:
    if not isinstance(wav_bytes, bytes) or not wav_bytes:
        raise SpeechGapError("delivered WAV bytes are required")
    try:
        with wave.open(BytesIO(wav_bytes), "rb") as source:
            channels = source.getnchannels()
            width = source.getsampwidth()
            rate = source.getframerate()
            frames = source.getnframes()
            compression = source.getcomptype()
            raw = source.readframes(frames)
    except (EOFError, OSError, wave.Error) as error:
        raise SpeechGapError(
            f"delivered audio is not a readable WAV: {error}"
        ) from error
    if compression != "NONE":
        raise SpeechGapError("delivered WAV must use uncompressed PCM")
    if channels < 1 or rate < 1 or frames < 1:
        raise SpeechGapError("delivered WAV dimensions must be positive")
    if width not in (2, 3):
        raise SpeechGapError("delivered WAV must use PCM-16 or PCM-24 samples")
    if len(raw) != frames * channels * width:
        raise SpeechGapError("delivered WAV frame data is truncated")

    samples: array[int]
    if width == 2:
        samples = array("h")
        samples.frombytes(raw)
        if samples.itemsize != 2:  # pragma: no cover - platform guard
            raise SpeechGapError("unsupported platform short size")
        if sys.byteorder == "big":  # pragma: no cover
            samples.byteswap()
    else:
        samples = array("i")
        samples.extend(
            int.from_bytes(raw[index : index + 3], "little", signed=True)
            for index in range(0, len(raw), 3)
        )
    return samples, rate, channels, frames, width


def _timing_map_values(
    timing_map: Mapping[str, Any], *, sample_rate: int, frame_count: int
) -> tuple[str, str, str, list[tuple[str, int]]]:
    block_id = timing_map.get("blockId")
    timing_hash = timing_map.get("timingHash")
    audio_hash = timing_map.get("audioHash")
    audio = timing_map.get("audio")
    tokens = timing_map.get("tokens")
    if not isinstance(block_id, str) or not block_id:
        raise SpeechGapError("timing map blockId is required")
    if not isinstance(timing_hash, str) or not timing_hash.startswith(_HASH_PREFIX):
        raise SpeechGapError("timing map timingHash is invalid")
    if not isinstance(audio_hash, str) or not audio_hash.startswith(_HASH_PREFIX):
        raise SpeechGapError("timing map audioHash is invalid")
    if not isinstance(audio, Mapping) or audio.get("audioHash") != audio_hash:
        raise SpeechGapError("timing map audio binding disagrees with audioHash")
    if (
        audio.get("sampleRate") != sample_rate
        or audio.get("durationSamples") != frame_count
        or not _is_positive_integer(audio.get("channels"))
    ):
        raise SpeechGapError("timing map audio dimensions differ from delivered WAV")
    if not isinstance(tokens, list) or not tokens:
        raise SpeechGapError("frozen token onsets are required")

    starts: list[tuple[str, int]] = []
    previous_sample = -1
    seen: set[str] = set()
    for token in tokens:
        if not isinstance(token, Mapping):
            raise SpeechGapError("timing-map token is invalid")
        token_id = token.get("tokenId")
        start_time = token.get("startTime")
        if not isinstance(token_id, str) or not token_id or token_id in seen:
            raise SpeechGapError("timing-map tokenId is missing or duplicated")
        if not isinstance(start_time, Mapping):
            raise SpeechGapError("timing-map token startTime is invalid")
        numerator = start_time.get("numerator")
        denominator = start_time.get("denominator")
        if (
            not isinstance(numerator, int)
            or isinstance(numerator, bool)
            or numerator < 0
            or not _is_positive_integer(denominator)
        ):
            raise SpeechGapError("timing-map token startTime is invalid")
        sample = _ceil_fraction(Fraction(numerator, denominator) * sample_rate)
        if sample >= frame_count:
            raise SpeechGapError("timing-map token onset is outside delivered WAV")
        if sample <= previous_sample:
            raise SpeechGapError("timing-map token onsets are not strictly increasing")
        seen.add(token_id)
        starts.append((token_id, sample))
        previous_sample = sample
    return block_id, timing_hash, audio_hash, starts


def _quiet_runs_ending_at_or_before(
    prefix_energy: array[float],
    *,
    left_sample: int,
    right_sample: int,
    window_frames: int,
    hop_frames: int,
    threshold_squared: float,
    minimum_frames: int,
) -> list[tuple[int, int]]:
    """Return qualifying quiet runs on a grid anchored at ``right_sample``."""
    if right_sample - left_sample < window_frames:
        return []
    starts: list[int] = []
    position = right_sample - window_frames
    while position >= left_sample:
        starts.append(position)
        position -= hop_frames
    starts.reverse()

    quiet: list[bool] = []
    for start in starts:
        end = start + window_frames
        # Peak energy per frame was accumulated across the loudest channel.
        mean_square = (prefix_energy[end] - prefix_energy[start]) / window_frames
        quiet.append(mean_square <= threshold_squared)

    runs: list[tuple[int, int]] = []
    index = 0
    while index < len(starts):
        if not quiet[index]:
            index += 1
            continue
        first = index
        while index + 1 < len(starts) and quiet[index + 1]:
            index += 1
        last = index
        start_sample = starts[first]
        end_sample = starts[last] + window_frames
        covered_frames = end_sample - start_sample
        if covered_frames >= minimum_frames:
            runs.append((start_sample, end_sample))
        index += 1
    return runs


def detect_speech_gaps(
    timing_map: Mapping[str, Any], wav_bytes: bytes
) -> dict[str, Any]:
    """Observe unique terminal quiet runs between adjacent frozen onsets.

    A detected run is a measured low-energy PCM window, not a word-end
    estimate. Its end is the incoming token's onset sample boundary. No
    temporal accuracy bound is inferred from that association.
    """
    if not isinstance(timing_map, Mapping):
        raise SpeechGapError("frozen timing map must be an object")
    samples, sample_rate, channels, frame_count, width = _wav_samples(wav_bytes)
    actual_hash = _HASH_PREFIX + hashlib.sha256(wav_bytes).hexdigest()
    declared_hash = timing_map.get("audioHash")
    if actual_hash != declared_hash:
        raise SpeechGapError("delivered WAV hash differs from frozen timing map")
    audio = timing_map.get("audio")
    if not isinstance(audio, Mapping) or audio.get("channels") != channels:
        raise SpeechGapError("timing map channel count differs from delivered WAV")
    block_id, timing_hash, audio_hash, starts = _timing_map_values(
        timing_map, sample_rate=sample_rate, frame_count=frame_count
    )

    if len(starts) == 1:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "method": METHOD,
            "blockId": block_id,
            "timingHash": timing_hash,
            "audioHash": audio_hash,
            "audio": {
                "sampleRate": sample_rate,
                "channels": channels,
                "durationSamples": frame_count,
            },
            "parameters": dict(DEFAULT_PARAMETERS),
            "tokenPairs": [],
        }

    # A single prefix holds the per-frame loudest-channel energy, so silence in
    # one channel cannot hide speech in another channel.
    scale = float(1 << (width * 8 - 1))
    prefix_energy = array("d", [0.0])
    running = 0.0
    for frame in range(frame_count):
        offset = frame * channels
        peak = max(abs(samples[offset + channel]) for channel in range(channels))
        normalized = peak / scale
        running += normalized * normalized
        prefix_energy.append(running)

    parameters = dict(DEFAULT_PARAMETERS)
    window_frames = max(1, (sample_rate * parameters["analysisWindowMs"] + 500) // 1000)
    hop_frames = max(1, (sample_rate * parameters["analysisHopMs"] + 500) // 1000)
    minimum_frames = (sample_rate * parameters["minimumQuietDurationMs"] + 999) // 1000
    threshold_squared = 10.0 ** (parameters["quietThresholdDbfs"] / 10.0)
    pairs: list[dict[str, Any]] = []
    for (before_id, left), (after_id, right) in pairwise(starts):
        runs = _quiet_runs_ending_at_or_before(
            prefix_energy,
            left_sample=left,
            right_sample=right,
            window_frames=window_frames,
            hop_frames=hop_frames,
            threshold_squared=threshold_squared,
            minimum_frames=minimum_frames,
        )
        status: str
        reason: str
        quiet_window: dict[str, int] | None = None
        gap_duration = 0
        if not runs:
            status = "absent"
            reason = "no_qualifying_quiet_run"
        elif len(runs) > 1:
            status = "ambiguous"
            reason = "multiple_qualifying_quiet_runs"
        elif runs[0][1] != right or runs[0][0] - left < window_frames:
            status = "absent"
            reason = "nonterminal_quiet_run"
        else:
            start_sample, end_sample = runs[0]
            status = "detected"
            reason = "unique_terminal_quiet_run"
            gap_duration = end_sample - start_sample
            quiet_window = {
                "startSample": start_sample,
                "endSample": end_sample,
                "durationSamples": gap_duration,
            }
        pairs.append(
            {
                "beforeTokenId": before_id,
                "afterTokenId": after_id,
                "onsetWindow": {"startSample": left, "endSample": right},
                "status": status,
                "gapDurationSamples": gap_duration,
                "quietWindow": quiet_window,
                "reason": reason,
            }
        )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "method": METHOD,
        "blockId": block_id,
        "timingHash": timing_hash,
        "audioHash": audio_hash,
        "audio": {
            "sampleRate": sample_rate,
            "channels": channels,
            "durationSamples": frame_count,
        },
        "parameters": parameters,
        "tokenPairs": pairs,
    }
