"""Check a decoded #326 music render against its narration-only baseline."""

from __future__ import annotations

import argparse
import json
import math
import sys
import wave
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from statistics import median
from typing import Any

RATE = 48_000
SAMPLES_PER_FRAME = 2_000
WINDOW = 2_400  # 50 ms; aligned to the 0.5-second source tone changes.
VOICE_DELTA_LIMIT = 0.012
OUTSIDE_MUSIC_LIMIT = 0.02


@dataclass(frozen=True)
class ToneRow:
    row_id: str
    start_frame: int
    end_frame: int
    frequency: float
    peak: float


@dataclass(frozen=True)
class Probe:
    case_id: str
    narration: tuple[ToneRow, ...]
    music_start_frame: int
    music_end_frame: int
    trim_sample: int
    source_start: int
    source_end: int
    segment_samples: int
    source_frequencies: tuple[float, ...]
    source_peak: float
    gain_db: float
    fade_frames: int

    @property
    def start(self) -> int:
        return self.music_start_frame * SAMPLES_PER_FRAME

    @property
    def end(self) -> int:
        return self.music_end_frame * SAMPLES_PER_FRAME


@dataclass(frozen=True)
class Pcm:
    channels: tuple[tuple[float, ...], ...]
    width: int

    @property
    def sample_count(self) -> int:
        return len(self.channels[0])


def _integer(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"probe field {key!r} must be an integer")
    return value


def _number(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"probe field {key!r} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"probe field {key!r} must be finite")
    return result


def _load_probe(path: Path) -> Probe:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read probe JSON: {exc}") from exc
    if not isinstance(data, dict) or _integer(data, "sampleRate") != RATE:
        raise ValueError("probe must be an object with sampleRate 48000")
    case_id = data.get("caseId")
    rows_data, music = data.get("narration"), data.get("music")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("probe caseId must be a non-empty string")
    if not isinstance(rows_data, list) or not rows_data or not isinstance(music, dict):
        raise ValueError("probe needs narration rows and a music object")
    rows: list[ToneRow] = []
    for row in rows_data:
        if not isinstance(row, dict) or not isinstance(row.get("rowId"), str):
            raise ValueError("probe narration rows need a rowId")
        start, end = _integer(row, "recordStartFrame"), _integer(row, "recordEndFrame")
        frequency, peak = _number(row, "frequencyHz"), _number(row, "peakAmplitude")
        if start < 0 or end <= start or not 0 < frequency < 500 or peak <= 0:
            raise ValueError("probe narration row has invalid timing or tone values")
        rows.append(ToneRow(row["rowId"], start, end, frequency, peak))

    start = _integer(music, "recordStartFrame")
    end = _integer(music, "recordEndFrame")
    trim = _integer(music, "sourceTrimSamples")
    segment_samples = _integer(music, "segmentSamples")
    source_peak = _number(music, "sourcePeak")
    gain_db = _number(music, "gainDb")
    fade_frames = _integer(music, "fadeFrames")
    source_range = music.get("sourceRangeSamples")
    frequencies_data = music.get("segmentFrequenciesHz")
    if not isinstance(source_range, dict) or not isinstance(frequencies_data, list):
        raise ValueError(
            "probe music needs sourceRangeSamples and segmentFrequenciesHz"
        )
    source_start = _integer(source_range, "startSample")
    source_end = _integer(source_range, "endSample")
    frequencies = tuple(float(value) for value in frequencies_data)
    duration_samples = (end - start) * SAMPLES_PER_FRAME
    if (
        start < 0
        or end <= start
        or trim < 0
        or segment_samples <= 0
        or source_peak <= 0
        or fade_frames <= 0
        or source_start != trim
        or source_end - source_start != duration_samples
        or fade_frames * 2 * SAMPLES_PER_FRAME >= duration_samples
        or any(not math.isfinite(value) or value <= 500 for value in frequencies)
        or len(set(frequencies)) != len(frequencies)
        or math.ceil(source_end / segment_samples) > len(frequencies)
    ):
        raise ValueError(
            "probe music timing, source range, or source-code pattern is invalid"
        )
    return Probe(
        case_id,
        tuple(rows),
        start,
        end,
        trim,
        source_start,
        source_end,
        segment_samples,
        frequencies,
        source_peak,
        gain_db,
        fade_frames,
    )


def _read_wav(path: Path) -> Pcm:
    try:
        with wave.open(str(path), "rb") as stream:
            channels, width, rate, count, compression = (
                stream.getnchannels(),
                stream.getsampwidth(),
                stream.getframerate(),
                stream.getnframes(),
                stream.getcomptype(),
            )
            raw = stream.readframes(count)
    except (OSError, wave.Error) as exc:
        raise ValueError(f"cannot decode {path}: {exc}") from exc
    if (
        rate != RATE
        or width not in (2, 3)
        or channels not in (1, 2)
        or compression != "NONE"
    ):
        raise ValueError(
            f"{path} must be uncompressed 48 kHz mono/stereo 16/24-bit PCM"
        )
    frame_bytes = channels * width
    if len(raw) != count * frame_bytes:
        raise ValueError(f"{path} has an incomplete PCM frame")
    scale = float(1 << (8 * width - 1))
    samples: list[list[float]] = [[] for _ in range(channels)]
    for offset in range(0, len(raw), frame_bytes):
        for channel in range(channels):
            start = offset + channel * width
            value = int.from_bytes(raw[start : start + width], "little", signed=True)
            samples[channel].append(value / scale)
    return Pcm(tuple(tuple(channel) for channel in samples), width)


@lru_cache(maxsize=64)
def _basis(frequency: float) -> tuple[tuple[float, ...], tuple[float, ...]]:
    return (
        tuple(math.cos(2 * math.pi * frequency * i / RATE) for i in range(WINDOW)),
        tuple(math.sin(2 * math.pi * frequency * i / RATE) for i in range(WINDOW)),
    )


def _tone_peak(samples: Sequence[float], start: int, frequency: float) -> float:
    cosine, sine = _basis(frequency)
    c = sum(samples[start + i] * cosine[i] for i in range(WINDOW))
    s = sum(samples[start + i] * sine[i] for i in range(WINDOW))
    return 2.0 / WINDOW * math.hypot(c, s)


def _peaks(audio: Pcm, start: int, frequency: float) -> tuple[float, ...]:
    return tuple(_tone_peak(channel, start, frequency) for channel in audio.channels)


def _expected_frequency(probe: Probe, center_sample: int) -> float:
    source_sample = probe.trim_sample + center_sample - probe.start
    index = source_sample // probe.segment_samples
    if index >= len(probe.source_frequencies):
        raise ValueError("source-code pattern does not cover the cue")
    return probe.source_frequencies[index]


def _rmse_from_linear(
    levels: list[float], target: float, fade_samples: int, fade_out: bool
) -> float:
    errors: list[float] = []
    for index, measured in enumerate(levels):
        center = index * WINDOW + WINDOW / 2
        expected = (
            (fade_samples - center) / fade_samples
            if fade_out
            else center / fade_samples
        )
        expected = min(1.0, max(0.0, expected)) * target
        errors.append((measured - expected) ** 2)
    return math.sqrt(sum(errors) / max(1, len(errors))) / target


def check_render(
    probe_path: Path, baseline_path: Path, mixed_path: Path
) -> dict[str, Any]:
    probe = _load_probe(probe_path)
    baseline, mixed = _read_wav(baseline_path), _read_wav(mixed_path)
    if (
        len(baseline.channels) != len(mixed.channels)
        or baseline.sample_count != mixed.sample_count
    ):
        raise ValueError(
            "baseline and mixed renders must have matching channels and duration"
        )
    if probe.end > mixed.sample_count:
        raise ValueError("music cue extends past the decoded WAV")

    gain = 10 ** (probe.gain_db / 20)
    target_source_peak = probe.source_peak * gain
    fade_samples = probe.fade_frames * SAMPLES_PER_FRAME
    windows: list[dict[str, Any]] = []
    max_voice_delta = 0.0
    baseline_music_peak = 0.0
    outside_music_peak = 0.0

    for start in range(0, mixed.sample_count - WINDOW + 1, WINDOW):
        center = start + WINDOW // 2
        music_inside = probe.start <= center < probe.end
        music_frequency = _expected_frequency(probe, center) if music_inside else None
        voice_frequencies = {
            row.frequency
            for row in probe.narration
            if row.start_frame * SAMPLES_PER_FRAME < start + WINDOW
            and row.end_frame * SAMPLES_PER_FRAME > start
        }
        for frequency in voice_frequencies:
            before = _peaks(baseline, start, frequency)
            after = _peaks(mixed, start, frequency)
            for left, right in zip(before, after, strict=True):
                max_voice_delta = max(max_voice_delta, abs(left - right))
                if abs(left - right) > VOICE_DELTA_LIMIT:
                    raise ValueError(
                        f"narration changed at sample {center} ({frequency:g} Hz, "
                        f"peak delta {abs(left - right):.4f})"
                    )
        if music_frequency is None:
            outside_music_peak = max(
                outside_music_peak,
                max(
                    max(_peaks(mixed, start, frequency), default=0.0)
                    for frequency in probe.source_frequencies
                ),
            )
            continue
        base_music = _peaks(baseline, start, music_frequency)
        mixed_music = _peaks(mixed, start, music_frequency)
        baseline_music_peak = max(baseline_music_peak, *base_music)
        windows.append(
            {
                "start": start,
                "frequency": music_frequency,
                "baselineMusic": base_music,
                "mixedMusic": mixed_music,
            }
        )

    if not windows:
        raise ValueError("render has no full analysis windows inside the music cue")
    if baseline_music_peak > OUTSIDE_MUSIC_LIMIT:
        raise ValueError(
            "baseline is not narration-only "
            f"(music-band peak {baseline_music_peak:.4f})"
        )
    if outside_music_peak > OUTSIDE_MUSIC_LIMIT:
        raise ValueError(
            f"music is audible outside its cue (peak {outside_music_peak:.4f})"
        )

    route_ratios: list[list[float]] = [[] for _ in mixed.channels]
    for row in probe.narration:
        row_start, row_end = (
            row.start_frame * SAMPLES_PER_FRAME,
            row.end_frame * SAMPLES_PER_FRAME,
        )
        for start in range(row_start + WINDOW, row_end - WINDOW, WINDOW):
            for channel, peak in enumerate(_peaks(baseline, start, row.frequency)):
                route_ratios[channel].append(peak / row.peak)
    if any(not ratios for ratios in route_ratios):
        raise ValueError("baseline has no stable narration tone in every channel")
    route_scale = tuple(median(ratios) for ratios in route_ratios)
    active_channels = tuple(
        index for index, value in enumerate(route_scale) if value > 0.05
    )
    if not active_channels:
        raise ValueError("baseline narration is silent in every channel")
    expected_channel_peak = tuple(target_source_peak * scale for scale in route_scale)

    steady = [
        item
        for item in windows
        if probe.start + fade_samples
        <= item["start"] + WINDOW // 2
        < probe.end - fade_samples
    ]
    stable_peaks: list[list[float]] = [[] for _ in mixed.channels]
    for item in steady:
        for channel in active_channels:
            observed = item["mixedMusic"][channel]
            expected = expected_channel_peak[channel]
            if abs(observed - expected) > max(0.012, expected * 0.2):
                raise ValueError(
                    "music source tone or -12 dB gain differs at "
                    f"{item['start'] + WINDOW // 2} samples "
                    f"({item['frequency']:g} Hz, channel {channel + 1}: "
                    f"{observed:.4f}, expected {expected:.4f})"
                )
            stable_peaks[channel].append(observed)
    if not steady:
        raise ValueError("music cue has no steady windows outside its fades")

    def normalized_level(item: dict[str, Any]) -> float:
        active = [
            item["mixedMusic"][channel] / route_scale[channel]
            for channel in active_channels
        ]
        return median(active)

    fade_in = [
        normalized_level(item)
        for item in windows
        if probe.start <= item["start"]
        and item["start"] + WINDOW <= probe.start + fade_samples
    ]
    fade_out = [
        normalized_level(item)
        for item in windows
        if probe.end - fade_samples <= item["start"]
        and item["start"] + WINDOW <= probe.end
    ]
    fade_windows = fade_samples // WINDOW
    if len(fade_in) != fade_windows or len(fade_out) != fade_windows:
        raise ValueError("decoded render does not contain all declared fade windows")
    tolerance = target_source_peak * 0.1
    if any(right + tolerance < left for left, right in pairwise(fade_in)):
        raise ValueError("music fade-in is not monotone")
    if any(right > left + tolerance for left, right in pairwise(fade_out)):
        raise ValueError("music fade-out is not monotone")
    if fade_in[0] > target_source_peak * 0.45 or fade_in[-1] < target_source_peak * 0.7:
        raise ValueError("music fade-in does not span the declared six-frame edge")
    if (
        fade_out[0] < target_source_peak * 0.7
        or fade_out[-1] > target_source_peak * 0.45
    ):
        raise ValueError("music fade-out does not span the declared six-frame edge")

    in_rmse = _rmse_from_linear(fade_in, target_source_peak, fade_samples, False)
    out_rmse = _rmse_from_linear(fade_out, target_source_peak, fade_samples, True)
    frequencies_seen = sorted({item["frequency"] for item in windows})
    return {
        "caseId": probe.case_id,
        "verified": True,
        "decoded": {
            "sampleRate": RATE,
            "channels": len(mixed.channels),
            "baselineBitsPerSample": baseline.width * 8,
            "mixedBitsPerSample": mixed.width * 8,
            "sampleCount": mixed.sample_count,
        },
        "music": {
            "recordRangeFrames": [probe.music_start_frame, probe.music_end_frame],
            "sourceRangeSamples": [probe.source_start, probe.source_end],
            "sourceTrimSamples": probe.trim_sample,
            "sourceCodeFrequenciesCheckedHz": frequencies_seen,
            "steadyWindowsChecked": len(steady),
            "expectedPeakAfterGain": target_source_peak,
            "expectedPeakPerChannel": list(expected_channel_peak),
            "observedSteadyPeakPerChannel": [
                median(values) if values else 0.0 for values in stable_peaks
            ],
            "observedSteadyRmsPerChannel": [
                median(values) / math.sqrt(2) if values else 0.0
                for values in stable_peaks
            ],
            "outsideCuePeak": outside_music_peak,
            "fadeFrames": probe.fade_frames,
            "fadeInObservedPeakRatios": [
                value / target_source_peak for value in fade_in
            ],
            "fadeOutObservedPeakRatios": [
                value / target_source_peak for value in fade_out
            ],
            "fadeInLinearCurveRmse": in_rmse,
            "fadeOutLinearCurveRmse": out_rmse,
            "linearCurveErrorIsDiagnosticOnly": True,
        },
        "narration": {
            "unchangedAgainstBaseline": True,
            "maximumObservedPeakDelta": max_voice_delta,
            "allowedPeakDelta": VOICE_DELTA_LIMIT,
        },
        "limits": [
            "Tones detect wrong trim, replacement, and >=50 ms source shifts.",
            "Level checks catch sustained ducks; brief changes may pass.",
            "Fade curve error is diagnostic because Resolve may use another curve.",
            "Synthetic tones do not qualify arbitrary music or ducking behavior.",
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--baseline-wav", type=Path, required=True)
    parser.add_argument("--mixed-wav", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = check_render(args.probe, args.baseline_wav, args.mixed_wav)
    except ValueError as exc:
        print(json.dumps({"verified": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
