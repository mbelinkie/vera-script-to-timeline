"""Measure a native Resolve render against its Issue 178 qualification case."""

from __future__ import annotations

import array
import json
import math
import sys
import wave
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Any, cast

from vera_timeline_agent.media_preparation import MediaTools, file_hash

Json = dict[str, Any]
TARGET_RATE = Fraction(24000, 1001)
AUDIO_RATE = 48000
SAMPLES_PER_FRAME = AUDIO_RATE * TARGET_RATE.denominator // TARGET_RATE.numerator
_CLICK_SEARCH_SAMPLES = AUDIO_RATE // 20  # Search 50 ms; gate remains 10 ms.
_CLICK_RESIDUAL_SAMPLES = AUDIO_RATE // 100
_CLICK_DRIFT_SAMPLES = AUDIO_RATE // 200  # 5 ms
_GAIN_TOLERANCE_DB = 0.5


@dataclass(frozen=True)
class _PreparedInput:
    video_path: Path
    audio_path: Path | None
    receipt_path: Path
    binding: Json


@dataclass(frozen=True)
class MeasurementCase:
    """The persisted, small set of case data needed after native rendering."""

    case_name: str
    manifest: Json
    preparations: dict[str, _PreparedInput]
    expected_frame_ordinals: dict[str, tuple[int, ...]]
    expected_audio_samples: dict[str, tuple[int, ...]]
    audio_policies: dict[str, str]
    expected_audio_gain_db: dict[str, float | None]


def _case_path(root: Path, value: object, description: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{description} must be a relative path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{description} escapes the qualification case root")
    resolved_root = root.resolve(strict=True)
    resolved = (resolved_root / relative).resolve(strict=True)
    if not resolved.is_relative_to(resolved_root) or not resolved.is_file():
        raise ValueError(
            f"{description} is missing or outside the qualification case root"
        )
    return resolved


def _integer_tuple_map(value: object, description: str) -> dict[str, tuple[int, ...]]:
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be an object")
    result: dict[str, tuple[int, ...]] = {}
    for label, samples in value.items():
        if (
            not isinstance(label, str)
            or not isinstance(samples, list)
            or any(type(sample) is not int for sample in samples)
        ):
            raise ValueError(f"{description} has an invalid entry")
        result[label] = tuple(samples)
    return result


def load_measurement_case(root: Path) -> MeasurementCase:
    """Load persisted qualification evidence without rebuilding its media."""
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("qualification case root must be an absolute real directory")
    root = root.resolve(strict=True)
    summary_path = root / "qualification-case.json"
    if summary_path.is_symlink() or not summary_path.is_file():
        raise ValueError("persisted qualification-case.json is missing")
    summary = cast(Json, json.loads(summary_path.read_bytes()))
    if summary.get("schemaVersion") != "issue178-qualification-case/v1":
        raise ValueError("unsupported persisted qualification case")
    case_name = summary.get("caseName")
    manifest = summary.get("manifest")
    raw_preparations = summary.get("preparations")
    if not isinstance(case_name, str) or not isinstance(manifest, dict):
        raise ValueError("persisted qualification identity or manifest is invalid")
    if not isinstance(raw_preparations, dict) or not raw_preparations:
        raise ValueError("persisted qualification preparations are invalid")

    preparations: dict[str, _PreparedInput] = {}
    for label, item in raw_preparations.items():
        if not isinstance(label, str) or not isinstance(item, dict):
            raise ValueError("persisted preparation entry is invalid")
        audio_value = item.get("audioPath")
        audio_path = (
            None
            if audio_value is None
            else _case_path(root, audio_value, f"{label} audioPath")
        )
        binding = item.get("binding")
        if not isinstance(binding, dict):
            raise ValueError(f"{label} preparation binding is invalid")
        preparations[label] = _PreparedInput(
            video_path=_case_path(root, item.get("videoPath"), f"{label} videoPath"),
            audio_path=audio_path,
            receipt_path=_case_path(
                root, item.get("receiptPath"), f"{label} receiptPath"
            ),
            binding=cast(Json, binding),
        )

    expected_ordinals = _integer_tuple_map(
        summary.get("expectedFrameOrdinals"), "expectedFrameOrdinals"
    )
    expected_audio_samples = _integer_tuple_map(
        summary.get("expectedAudioSamples"), "expectedAudioSamples"
    )
    raw_policies = summary.get("audioPolicies")
    raw_gains = summary.get("expectedAudioGainDb")
    if not isinstance(raw_policies, dict) or not isinstance(raw_gains, dict):
        raise ValueError("persisted source-audio expectations are invalid")
    if any(
        not isinstance(label, str) or not isinstance(policy, str)
        for label, policy in raw_policies.items()
    ):
        raise ValueError("persisted source-audio policies are invalid")
    gains: dict[str, float | None] = {}
    for label, gain in raw_gains.items():
        if not isinstance(label, str) or (
            gain is not None and type(gain) not in {int, float}
        ):
            raise ValueError("persisted source-audio gains are invalid")
        gains[label] = None if gain is None else float(gain)
    expected_labels = set(preparations)
    if (
        set(expected_ordinals) != expected_labels
        or set(expected_audio_samples) != expected_labels
        or set(raw_policies) != expected_labels
        or set(gains) != expected_labels
    ):
        raise ValueError(
            "persisted qualification case fields do not cover the same preparations"
        )
    return MeasurementCase(
        case_name=case_name,
        manifest=cast(Json, manifest),
        preparations=preparations,
        expected_frame_ordinals=expected_ordinals,
        expected_audio_samples=expected_audio_samples,
        audio_policies=cast(dict[str, str], raw_policies),
        expected_audio_gain_db=gains,
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _integer(value: object, description: str) -> int:
    if type(value) is not int:
        raise ValueError(f"invalid {description}: {value!r}")
    return value


def _json_objects(value: object, description: str) -> list[Json]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{description} must be a list of objects")
    return cast(list[Json], value)


def _fraction(value: object, description: str) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, str):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError) as error:
            raise ValueError(f"invalid {description}: {value!r}") from error
    if isinstance(value, Mapping):
        numerator = value.get("numerator")
        denominator = value.get("denominator")
        if type(numerator) is int and type(denominator) is int and denominator > 0:
            return Fraction(numerator, denominator)
    raise ValueError(f"invalid {description}: {value!r}")


def _range(value: object, description: str) -> tuple[int, int]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{description} must be an object")
    start = value.get("startFrame")
    end = value.get("endFrame")
    if type(start) is not int or type(end) is not int or end <= start:
        raise ValueError(f"{description} must be a positive half-open frame range")
    return start, end


def _probe_json(tools: MediaTools, arguments: Sequence[str]) -> Json:
    return cast(Json, json.loads(tools.run([tools.ffprobe, *arguments])))


def _decode_rgb_frames(tools: MediaTools, mov_path: Path) -> tuple[int, ...]:
    raw = tools.run(
        [
            tools.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            str(mov_path),
            "-map",
            "0:v:0",
            "-vf",
            "crop=ih:ih:(iw-ih)/2:0,scale=64:64:flags=neighbor",
            "-an",
            "-fps_mode",
            "passthrough",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]
    )
    frame_size = 64 * 64 * 3
    _require(len(raw) % frame_size == 0, "render decode produced a partial RGB frame")
    ordinals: list[int] = []
    for start in range(0, len(raw), frame_size):
        frame = raw[start : start + frame_size]
        value = 0
        for bit in range(12):
            row, column = divmod(bit, 4)
            x = 4 + column * 15 + 5
            y = 4 + row * 14 + 5
            offset = (y * 64 + x) * 3
            if sum(frame[offset : offset + 3]) >= 384:
                value |= 1 << bit
        ordinals.append(value)
    return tuple(ordinals)


def _verify_video_probe(
    case: MeasurementCase,
    mov_path: Path,
    tools: MediaTools,
) -> tuple[Json, Fraction, int]:
    manifest = case.manifest
    timeline = manifest["timeline"]
    rate = _fraction(timeline["frameRate"], "manifest frame rate")
    _require(
        rate == TARGET_RATE, f"manifest frame rate is {rate}, expected {TARGET_RATE}"
    )
    expected_frames = _integer(timeline["durationFrames"], "manifest durationFrames")
    _require(expected_frames > 0, "manifest durationFrames must be positive")
    _require(mov_path.suffix.lower() == ".mov", "native render must be a MOV")
    _require(
        mov_path.is_file() and not mov_path.is_symlink(),
        "rendered MOV is missing or is a symlink",
    )

    probe = _probe_json(
        tools,
        [
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_streams",
            "-show_frames",
            "-show_entries",
            "stream=codec_name,width,height,pix_fmt,time_base,avg_frame_rate,r_frame_rate,duration,duration_ts,nb_frames:frame=best_effort_timestamp,best_effort_timestamp_time,duration,duration_time",
            "-of",
            "json",
            str(mov_path),
        ],
    )
    streams = _json_objects(probe.get("streams"), "video streams")
    frames = _json_objects(probe.get("frames"), "video frames")
    _require(len(streams) == 1, "render must contain one video stream")
    stream = streams[0]
    _require(stream.get("codec_name") == "prores", "render video must use ProRes")
    _require(
        stream.get("width") == 1920 and stream.get("height") == 1080,
        "render video must be 1920x1080",
    )
    _require(
        stream.get("pix_fmt") == "yuv422p10le",
        "render video must use 10-bit 4:2:2 ProRes pixels",
    )
    average_rate = _fraction(stream.get("avg_frame_rate"), "render average frame rate")
    _require(
        average_rate == rate,
        f"render average frame rate is {average_rate}, expected {rate}",
    )
    time_base = _fraction(stream.get("time_base"), "render video time base")
    _require(time_base > 0, "render video time base must be positive")
    _require(
        len(frames) == expected_frames,
        f"render has {len(frames)} frames, expected {expected_frames}",
    )

    timestamps: list[Fraction] = []
    packet_durations: list[Fraction] = []
    for frame in frames:
        if "best_effort_timestamp" in frame:
            timestamps.append(Fraction(int(frame["best_effort_timestamp"])) * time_base)
        elif "best_effort_timestamp_time" in frame:
            timestamps.append(
                _fraction(frame["best_effort_timestamp_time"], "frame timestamp")
            )
        else:
            raise AssertionError("rendered frame has no presentation timestamp")
        if "duration" in frame:
            packet_durations.append(Fraction(int(frame["duration"])) * time_base)
        elif "duration_time" in frame:
            packet_durations.append(_fraction(frame["duration_time"], "frame duration"))
    _require(
        len(timestamps) == expected_frames,
        "render PTS count differs from manifest frame count",
    )
    expected_frame_duration = 1 / rate
    for index, (left, right) in enumerate(pairwise(timestamps)):
        _require(
            right - left == expected_frame_duration,
            f"render cadence differs at frame {index}: "
            f"{right - left}, expected {expected_frame_duration}",
        )
    _require(
        len(packet_durations) == expected_frames
        and all(duration == expected_frame_duration for duration in packet_durations),
        "rendered frame packet duration differs from exact 24000/1001 cadence",
    )

    measured_duration = Fraction(expected_frames, 1) / rate
    stream_duration: Fraction | None = None
    if stream.get("duration") not in (None, "N/A"):
        stream_duration = _fraction(stream["duration"], "render video duration")
    elif stream.get("duration_ts") not in (None, "N/A"):
        stream_duration = Fraction(int(stream["duration_ts"])) * time_base
    if stream_duration is not None:
        duration_error_frames = abs(stream_duration - measured_duration) * rate
        _require(
            duration_error_frames <= 1,
            "render video duration differs by "
            f"{float(duration_error_frames):.6f} target frames",
        )
        measured_duration = stream_duration
    else:
        duration_error_frames = Fraction(0)
    return stream, measured_duration, expected_frames


def _prepared_audio_data(path: Path) -> tuple[int, int, bytes]:
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        width = source.getsampwidth()
        rate = source.getframerate()
        frame_count = source.getnframes()
        raw = source.readframes(frame_count)
    _require(
        channels == 2 and width == 3 and rate == AUDIO_RATE,
        f"prepared audio profile is invalid: {path}",
    )
    _require(
        len(raw) == frame_count * channels * width,
        f"prepared audio is truncated: {path}",
    )
    return frame_count, channels, raw


def _int24(raw: bytes, offset: int) -> int:
    value = int.from_bytes(raw[offset : offset + 3], "little", signed=False)
    return value - (1 << 24) if value & (1 << 23) else value


def _verify_prepared_audio(
    case: MeasurementCase,
) -> tuple[dict[str, Json], dict[str, tuple[int, int, bytes]]]:
    preparations = case.preparations
    expected_clicks = case.expected_audio_samples
    summaries: dict[str, Json] = {}
    data_by_label: dict[str, tuple[int, int, bytes]] = {}
    for label, prepared in preparations.items():
        audio_path = prepared.audio_path
        verification = cast(Json, prepared.binding["verification"])
        source_audio = cast(Json, verification["sourceAudio"])
        if audio_path is None:
            _require(
                source_audio.get("status") == "absent",
                f"{label} has no prepared audio but its binding does not say absent",
            )
            _require(
                not expected_clicks.get(label, ()),
                f"{label} has expected clicks but no prepared audio",
            )
            summaries[label] = {"status": "absent", "sampleCount": 0}
            continue

        _require(
            source_audio.get("status") == "aligned",
            f"{label} prepared source audio is not aligned",
        )
        _require(
            source_audio.get("sampleRate") == AUDIO_RATE,
            f"{label} prepared source audio is not 48 kHz",
        )

        record = cast(Json, json.loads(prepared.receipt_path.read_bytes()))
        audio_record = cast(Json, record["audio"])
        frame_count, channels, raw = _prepared_audio_data(audio_path)
        decoded_samples = _integer(
            audio_record.get("decodedSamples"), f"{label} decoded samples"
        )
        source_first = _integer(
            audio_record.get("sourceFirstSample"), f"{label} source first sample"
        )
        source_exclusive = _integer(
            audio_record.get("sourceExclusiveSample"),
            f"{label} source exclusive sample",
        )
        prepared_first = _integer(
            audio_record.get("resampledFirstSample"), f"{label} prepared first sample"
        )
        prepared_exclusive = _integer(
            audio_record.get("resampledExclusiveSample"),
            f"{label} prepared exclusive sample",
        )
        _require(
            abs(source_first - prepared_first) <= 1,
            f"{label} prepared first sample boundary differs by more than one sample",
        )
        _require(
            abs(source_exclusive - prepared_exclusive) <= 1,
            f"{label} prepared end sample boundary differs by more than one sample",
        )
        expected_count = prepared_exclusive - prepared_first
        _require(
            abs(decoded_samples - expected_count) <= 1,
            f"{label} receipt sample count differs from its boundaries",
        )
        _require(
            abs(frame_count - decoded_samples) <= 1,
            f"{label} prepared WAV sample count differs from its receipt",
        )

        endpoint_error = abs(
            _fraction(
                audio_record["endpointError"], f"{label} prepared audio endpoint error"
            )
        )
        _require(
            endpoint_error <= Fraction(1, AUDIO_RATE),
            f"{label} prepared audio endpoint differs by more than one sample",
        )
        max_drift = abs(
            _fraction(source_audio["maxDrift"], f"{label} preparation sync drift")
        )
        _require(
            max_drift <= Fraction(1, 1000),
            f"{label} preparation sync drift exceeds 1 ms",
        )

        clicks = expected_clicks.get(label, ())
        for click in clicks:
            _require(
                click >= 0 and click + 4 < frame_count,
                f"{label} expected click is outside prepared audio",
            )
            peak = max(
                abs(_int24(raw, sample * channels * 3 + channel * 3))
                for sample in range(click, click + 4)
                for channel in range(channels)
            )
            _require(
                peak >= 1_000_000,
                f"{label} expected prepared click is missing at sample {click}",
            )

        summaries[label] = {
            "status": source_audio.get("status"),
            "sampleCount": frame_count,
            "sourceFirstSample": source_first,
            "preparedFirstSample": prepared_first,
            "sourceExclusiveSample": source_exclusive,
            "preparedExclusiveSample": prepared_exclusive,
            "endpointErrorSamples": float(endpoint_error * AUDIO_RATE),
            "maxSyncDriftMs": float(max_drift * 1000),
            "expectedClicks": len(clicks),
        }
        data_by_label[label] = (frame_count, channels, raw)
    return summaries, data_by_label


def _decode_render_audio(tools: MediaTools, mov_path: Path) -> array.array[float]:
    raw = tools.run(
        [
            tools.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            str(mov_path),
            "-map",
            "0:a:0",
            "-vn",
            "-acodec",
            "pcm_f32le",
            "-f",
            "f32le",
            "-",
        ]
    )
    _require(len(raw) % 4 == 0, "render audio decode produced a partial float sample")
    samples = array.array("f")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    _require(len(samples) % 2 == 0, "render audio decode is not stereo")
    return samples


def _click_template(
    raw: bytes, channels: int, click: int
) -> tuple[tuple[float, float], ...]:
    return tuple(
        (
            _int24(raw, sample * channels * 3) / float(1 << 23),
            _int24(raw, sample * channels * 3 + 3) / float(1 << 23),
        )
        for sample in range(click, click + 4)
    )


def _measure_click(
    rendered: array.array[float],
    template: Sequence[tuple[float, float]],
    expected_start: int,
) -> tuple[int, float, float, float]:
    template_energy = sum(left * left + right * right for left, right in template)
    _require(template_energy > 0, "prepared click template has no signal")
    best_lag: int | None = None
    best_correlation = -math.inf
    best_rendered_energy = 0.0
    best_dot = 0.0
    for lag in range(-_CLICK_SEARCH_SAMPLES, _CLICK_SEARCH_SAMPLES + 1):
        start = expected_start + lag
        if start < 0 or start + len(template) > len(rendered) // 2:
            continue
        dot = 0.0
        rendered_energy = 0.0
        for index, (left, right) in enumerate(template):
            output_left = rendered[(start + index) * 2]
            output_right = rendered[(start + index) * 2 + 1]
            dot += left * output_left + right * output_right
            rendered_energy += output_left * output_left + output_right * output_right
        if rendered_energy == 0:
            continue
        correlation = dot / math.sqrt(template_energy * rendered_energy)
        if correlation > best_correlation:
            best_lag = lag
            best_correlation = correlation
            best_rendered_energy = rendered_energy
            best_dot = dot
    if best_lag is None:
        raise AssertionError("rendered click was not found inside its timing window")
    _require(
        best_correlation >= 0.9,
        f"rendered click shape correlation is {best_correlation:.3f}",
    )
    gain = math.sqrt(best_rendered_energy / template_energy)
    return best_lag, best_correlation, gain, best_dot


def _check_audio_topology(
    case: MeasurementCase,
    source_to_label: Mapping[str, str],
    visual_events: Sequence[Json],
    audio_events: Sequence[Json],
) -> tuple[dict[str, Json], dict[str, Json]]:
    policies = case.audio_policies
    expected_gains = case.expected_audio_gain_db
    labels = set(case.preparations)
    _require(
        set(policies) == labels,
        "qualification case audio policies do not cover every preparation",
    )
    _require(
        set(expected_gains) == labels,
        "qualification case expected gains do not cover every preparation",
    )
    by_label_visual: dict[str, Json] = {}
    for event in visual_events:
        source_id = cast(Json, event["provenance"]).get("sourceId")
        label = source_to_label.get(cast(str, source_id))
        if label is None:
            raise AssertionError(
                f"render visual event references unknown source {source_id!r}"
            )
        _require(
            label not in by_label_visual,
            f"qualification case has duplicate visual events for {label}",
        )
        by_label_visual[label] = event
    _require(
        set(by_label_visual) == labels,
        "manifest visual events do not cover every prepared source",
    )

    by_label_audio: dict[str, Json] = {}
    for event in audio_events:
        provenance = cast(Json, event["provenance"])
        label = source_to_label.get(cast(str, provenance.get("sourceId")))
        if label is None:
            raise AssertionError(
                "manifest source-audio event references an unknown source"
            )
        _require(
            label not in by_label_audio,
            f"qualification case has duplicate source-audio events for {label}",
        )
        by_label_audio[label] = event

    for label in labels:
        policy = policies[label]
        _require(
            policy in {"mute", "quiet", "full"},
            f"{label} has unsupported source-audio policy {policy!r}",
        )
        audio_event = by_label_audio.get(label)
        expected_gain = expected_gains[label]
        if policy == "mute":
            _require(
                audio_event is None,
                f"{label} mute policy unexpectedly compiled a source-audio event",
            )
            _require(
                expected_gain is None,
                f"{label} mute policy must have no expected audio gain",
            )
            continue
        if audio_event is None:
            raise AssertionError(f"{label} {policy} policy has no source-audio event")
        audio = cast(Json, audio_event["audio"])
        expected_policy_gain = 0.0 if policy == "full" else -18.0
        _require(
            audio.get("audioPolicy") == policy,
            f"{label} source-audio event policy differs from the case",
        )
        _require(
            audio.get("gainDb") == expected_policy_gain,
            f"{label} source-audio event gain differs from its policy",
        )
        _require(
            expected_gain == expected_policy_gain,
            f"{label} case gain differs from its source-audio policy",
        )
        _require(
            audio_event["recordRange"] == by_label_visual[label]["recordRange"],
            f"{label} source audio and picture cuts differ",
        )
        sample_start, sample_end = _range(
            audio["sampleRange"], f"{label} source audio sample range"
        )
        _require(
            sample_end > sample_start, f"{label} source audio sample range is empty"
        )
        receipt = cast(
            Json, json.loads(case.preparations[label].receipt_path.read_bytes())
        )
        prepared_audio = cast(Json, receipt["audio"])
        prepared_start = _integer(
            prepared_audio.get("sourceFirstSample"),
            f"{label} prepared source first sample",
        )
        prepared_end = _integer(
            prepared_audio.get("sourceExclusiveSample"),
            f"{label} prepared source exclusive sample",
        )
        _require(
            abs(sample_start - prepared_start) <= 1,
            f"{label} compiled source-audio start differs from preparation by "
            "more than one sample",
        )
        _require(
            abs(sample_end - prepared_end) <= 1,
            f"{label} compiled source-audio end differs from preparation by "
            "more than one sample",
        )
    return by_label_visual, by_label_audio


def _measure_rendered_clicks(
    label: str,
    policy: str,
    expected_gain: float | None,
    visual_event: Json,
    prepared_audio: tuple[int, int, bytes] | None,
    expected_clicks: Sequence[int],
    rendered: array.array[float],
    audio_event: Json | None,
) -> Json:
    start_frame, end_frame = _range(
        visual_event["recordRange"], f"{label} picture record range"
    )
    start_sample = start_frame * SAMPLES_PER_FRAME
    end_sample = end_frame * SAMPLES_PER_FRAME
    if policy == "mute":
        _require(
            audio_event is None,
            f"{label} mute policy has rendered source-audio topology",
        )
        _require(
            end_sample <= len(rendered) // 2,
            f"{label} mute interval exceeds rendered audio",
        )
        peak = max(
            (abs(value) for value in rendered[start_sample * 2 : end_sample * 2]),
            default=0.0,
        )
        _require(
            peak <= 2 / float(1 << 23),
            f"{label} mute interval contains source audio (peak {peak:.7f})",
        )
        return {
            "policy": policy,
            "expectedGainDb": None,
            "measuredGainDb": None,
            "clickResidualSamples": [],
            "maxResidualMs": 0.0,
            "driftMs": 0.0,
            "mutedPeak": peak,
        }

    if prepared_audio is None or audio_event is None:
        raise AssertionError(
            f"{label} enabled audio has no prepared or compiled source audio"
        )
    frame_count, channels, raw = prepared_audio
    _require(channels == 2, f"{label} prepared source audio is not stereo")
    _require(
        len(expected_clicks) >= 2,
        f"{label} needs at least two prepared clicks to measure drift",
    )
    sample_start, sample_end = _range(
        cast(Json, audio_event["audio"])["sampleRange"], f"{label} audio sample range"
    )
    _require(
        abs((sample_end - sample_start) - frame_count) <= 1,
        f"{label} source-audio event sample range differs from prepared audio "
        "by more than one sample",
    )

    residuals: list[int] = []
    expected_energy = 0.0
    rendered_energy = 0.0
    correlations: list[float] = []
    for click in expected_clicks:
        _require(click + 4 < frame_count, f"{label} click is outside prepared audio")
        template = _click_template(raw, channels, click)
        lag, correlation, gain, _ = _measure_click(
            rendered, template, start_sample + click
        )
        residuals.append(lag)
        correlations.append(correlation)
        expected_energy += sum(left * left + right * right for left, right in template)
        rendered_energy += (
            gain * gain * sum(left * left + right * right for left, right in template)
        )
    max_residual = max(abs(residual) for residual in residuals)
    drift = max(residuals) - min(residuals)
    _require(
        max_residual <= _CLICK_RESIDUAL_SAMPLES,
        f"{label} rendered click residual exceeds 10 ms",
    )
    _require(
        drift <= _CLICK_DRIFT_SAMPLES, f"{label} rendered click drift exceeds 5 ms"
    )
    _require(
        expected_energy > 0 and rendered_energy > 0,
        f"{label} click gain has no measurable energy",
    )
    measured_gain = 20 * math.log10(math.sqrt(rendered_energy / expected_energy))
    if expected_gain is None:
        raise AssertionError(f"{label} enabled audio has no expected gain")
    _require(
        abs(measured_gain - expected_gain) <= _GAIN_TOLERANCE_DB,
        f"{label} measured gain {measured_gain:.3f} dB differs from "
        f"{expected_gain:.1f} dB",
    )
    return {
        "policy": policy,
        "expectedGainDb": expected_gain,
        "measuredGainDb": measured_gain,
        "clickResidualSamples": residuals,
        "maxResidualMs": max_residual * 1000 / AUDIO_RATE,
        "driftMs": drift * 1000 / AUDIO_RATE,
        "minimumClickCorrelation": min(correlations),
    }


def _verify_ordinals(
    case: MeasurementCase,
    events: Sequence[Json],
    source_to_label: Mapping[str, str],
    rendered_ordinals: Sequence[int],
    expected_frames: int,
) -> list[Json]:
    expected_by_label = case.expected_frame_ordinals
    cursor = 0
    cuts: list[Json] = []
    for event in sorted(
        events, key=lambda item: _range(item["recordRange"], "visual record range")[0]
    ):
        record_start, record_end = _range(event["recordRange"], "visual record range")
        _require(
            record_start == cursor,
            f"visual topology has a gap or overlap at record frame {cursor}",
        )
        source_id = cast(Json, event["provenance"]).get("sourceId")
        label = source_to_label.get(cast(str, source_id))
        if label is None:
            raise AssertionError(
                f"visual event uses an unknown prepared source {source_id!r}"
            )
        source_start, source_end = _range(
            event["sourceRange"], f"{label} prepared source range"
        )
        expected_source = expected_by_label[label]
        _require(
            source_end <= len(expected_source),
            f"{label} source range exceeds its prepared ordinal sequence",
        )
        expected = expected_source[source_start:source_end]
        _require(
            len(expected) == record_end - record_start,
            f"{label} source range does not match its rendered cut length",
        )
        observed = tuple(rendered_ordinals[record_start:record_end])
        _require(
            len(observed) == len(expected),
            f"{label} rendered cut exceeds the decoded output",
        )
        _require(
            observed == expected,
            f"{label} rendered ordinal sampling differs in record frames "
            f"[{record_start}, {record_end})",
        )
        cuts.append(
            {
                "label": label,
                "recordStartFrame": record_start,
                "recordEndFrame": record_end,
                "preparedStartFrame": source_start,
                "preparedEndFrame": source_end,
                "sampledFrames": len(observed),
            }
        )
        cursor = record_end
    _require(
        cursor == expected_frames,
        f"visual topology ends at frame {cursor}, expected {expected_frames}",
    )
    return cuts


def authenticate_render(
    case: MeasurementCase, mov_path: Path, session_path: Path, session_sha256: str
) -> Json:
    """Bind measurements to the authenticated completed native operation chain."""
    from vera_timeline_agent.qualification_output_controller_v2 import (
        load_output_session,
    )

    controller = load_output_session(session_path, session_sha256)
    admission = controller.admission
    admission.assert_current()
    _require(
        case.manifest == admission.manifest,
        "measurement manifest differs from admitted package",
    )
    bindings = {
        row["requirementKey"]: row for row in admission.manifest["preparationBindings"]
    }
    _require(
        set(bindings)
        == {
            prepared.binding["requirementKey"]
            for prepared in case.preparations.values()
        },
        "measurement preparation inventory differs",
    )
    for prepared in case.preparations.values():
        _require(
            prepared.binding == bindings[prepared.binding["requirementKey"]],
            "measurement preparation binding differs",
        )
        _require(
            file_hash(prepared.video_path)
            == prepared.binding["verification"]["deliveredHash"],
            "measurement prepared picture bytes differ from admission",
        )
        for path in (prepared.receipt_path, prepared.audio_path):
            if path is not None:
                _require(
                    admission._tracked_hashes.get(path)
                    == file_hash(path).removeprefix("sha256:"),
                    "measurement preparation bytes differ from admission",
                )
    attempt = controller._latest_attempt()
    _require(
        attempt is not None and attempt["state"] == "compared_consistent",
        "completed native output comparison required",
    )
    completion_path, completion_hash, completion = controller._native_result(5)
    _require(
        completion["status"] == "complete"
        and completion["outputPath"] == str(mov_path),
        "measurement MOV differs from completed native output",
    )
    output_hash = file_hash(mov_path).removeprefix("sha256:")
    _require(
        completion["sourceOutputRawSha256"] == output_hash,
        "measurement MOV bytes differ from native output",
    )
    return {
        "sessionSha256": session_sha256,
        "admissionSha256": file_hash(admission.admission_path).removeprefix("sha256:"),
        "manifestSha256": admission.admission["manifestSha256"],
        "completionResultPath": str(completion_path),
        "completionResultSha256": completion_hash,
        "outputSha256": output_hash,
    }


def expected_prepared_ordinals(binding: Json) -> tuple[int, ...]:
    """Derive numbered-source expectations from the authenticated P5 mapping."""
    mapping = binding["timeMapping"]
    rate = _fraction(mapping["sourceRate"], "original rate")
    target = _fraction(binding["targetRate"], "prepared rate")
    count = binding["verification"]["decodedFrameCount"]
    origin = mapping["sourceFrameMap"]["packageFrameZeroLogicalFrame"]
    first = (
        Fraction(0)
        if binding["mode"] == "verified_reuse"
        else Fraction(binding["requestedRange"]["sourceInFrame"] - origin, 1) / rate
    )
    return tuple(
        math.floor((first + Fraction(frame, 1) / target) * rate)
        for frame in range(count)
    )


def verify_composite_ordinals(
    manifest: Json,
    source_ordinals: Mapping[str, tuple[int, ...]],
    rendered: Sequence[int],
) -> Json:
    """Verify every visible numbered frame across roots, children and overlays."""
    events = [
        event
        for event in manifest["events"]
        if event["kind"] in {"primary_visual", "overlay_visual"}
    ]
    tracks = {track["id"]: track["index"] for track in manifest["tracks"]}
    count = manifest["timeline"]["durationFrames"]
    _require(len(rendered) == count, "composite rendered frame count differs")
    appearances: dict[str, list[int]] = {}
    for frame in range(count):
        active = [
            event
            for event in events
            if event["recordRange"]["startFrame"]
            <= frame
            < event["recordRange"]["endFrame"]
        ]
        _require(bool(active), f"composite has no picture at frame {frame}")
        event = max(active, key=lambda row: tracks[row["trackId"]])
        source_frame = (
            event["sourceRange"]["startFrame"]
            + frame
            - event["recordRange"]["startFrame"]
        )
        expected = source_ordinals[event["provenance"]["sourceId"]][source_frame]
        _require(
            rendered[frame] == expected, f"composite ordinal differs at frame {frame}"
        )
        appearances.setdefault(event["eventId"], []).append(frame)
    return {
        event_id: {
            "visibleFrames": len(frames),
            "firstFrame": frames[0],
            "lastFrame": frames[-1],
        }
        for event_id, frames in appearances.items()
    }


def measure_topology_render(
    case: MeasurementCase,
    mov_path: Path,
    outputdir: Path,
    *,
    session_path: Path,
    session_sha256: str,
) -> Json:
    binding = authenticate_render(case, mov_path, session_path, session_sha256)
    sources = case.manifest["sources"]
    expected = {
        source["id"]: expected_prepared_ordinals(prepared.binding)
        for source in sources
        for prepared in case.preparations.values()
        if source.get("preparationRequirementKey") == prepared.binding["requirementKey"]
    }
    tools = MediaTools()
    _, duration, count = _verify_video_probe(case, mov_path, tools)
    rendered = _decode_rgb_frames(tools, mov_path)
    appearances = verify_composite_ordinals(case.manifest, expected, rendered)
    events = case.manifest["events"]
    _require(
        any(event["kind"] == "overlay_visual" for event in events),
        "topology case requires an independent overlay",
    )
    _require(
        any(event["kind"] == "narration" for event in events),
        "topology case requires authenticated narration",
    )
    _require(
        not any(event["kind"] == "source_audio" for event in events),
        "this topology fixture requires muted source clips",
    )
    result = {
        "schemaVersion": "issue178-topology-measurements/v1",
        "status": "passed",
        "nativeBinding": binding,
        "frameCount": count,
        "durationSeconds": float(duration),
        "appearances": appearances,
    }
    outputdir.mkdir(parents=True, exist_ok=False)
    (outputdir / "topology-measurements.json").write_text(json.dumps(result, indent=2))
    return result


def measure_render(
    case: MeasurementCase,
    mov_path: Path,
    outputdir: Path,
    *,
    session_path: Path,
    session_sha256: str,
) -> dict[str, Any]:
    """Measure an actual native render and raise if any Issue 178 gate fails.

    The rendered MOV is probed and decoded from disk. Timeline cut expectations,
    source-audio policy, preparation bounds and gain targets all come from the
    supplied ordinary qualification case.
    """
    binding = authenticate_render(case, mov_path, session_path, session_sha256)
    for prepared_label, prepared in case.preparations.items():
        _require(
            case.expected_frame_ordinals[prepared_label]
            == expected_prepared_ordinals(prepared.binding),
            "persisted ordinal expectations differ from admitted mapping",
        )
    _require(outputdir.is_absolute(), "measurement output directory must be absolute")
    outputdir.mkdir(parents=True, exist_ok=True)
    tools = MediaTools()
    video_stream, video_duration, expected_frames = _verify_video_probe(
        case, mov_path, tools
    )

    manifest = case.manifest
    sources = cast(list[Json], manifest["sources"])
    preparations = case.preparations
    requirement_to_label = {
        cast(str, prepared.binding["requirementKey"]): label
        for label, prepared in preparations.items()
    }
    source_to_label: dict[str, str] = {}
    for source in sources:
        requirement = source.get("preparationRequirementKey")
        if not isinstance(requirement, str):
            raise AssertionError(
                f"manifest source {source.get('id')!r} has no preparation requirement"
            )
        label = requirement_to_label.get(requirement)
        if label is None:
            raise AssertionError(
                f"manifest source {source.get('id')!r} has no prepared case input"
            )
        source_id = source.get("id")
        if not isinstance(source_id, str):
            raise AssertionError("manifest source id is invalid")
        source_to_label[source_id] = label

    events = cast(list[Json], manifest["events"])
    visual_events = [event for event in events if event.get("kind") == "primary_visual"]
    audio_events = [event for event in events if event.get("kind") == "source_audio"]
    _require(
        len(visual_events) == len(preparations),
        f"manifest has {len(visual_events)} primary visual events for "
        f"{len(preparations)} prepared clips",
    )
    other_picture_events = [
        event
        for event in events
        if event.get("kind") in {"overlay_visual", "placeholder"}
    ]
    _require(
        not other_picture_events,
        "qualification render includes unsupported overlay or placeholder "
        "picture events",
    )

    by_label_visual, by_label_audio = _check_audio_topology(
        case, source_to_label, visual_events, audio_events
    )
    rendered_ordinals = _decode_rgb_frames(tools, mov_path)
    _require(
        len(rendered_ordinals) == expected_frames,
        "decoded ordinal frame count differs from ffprobe",
    )
    cuts = _verify_ordinals(
        case, visual_events, source_to_label, rendered_ordinals, expected_frames
    )

    audio_probe = _probe_json(
        tools,
        [
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_streams",
            "-show_entries",
            "stream=codec_name,sample_rate,channels,channel_layout,start_time,duration",
            "-of",
            "json",
            str(mov_path),
        ],
    )
    audio_streams = _json_objects(audio_probe.get("streams"), "render audio streams")
    _require(len(audio_streams) == 1, "render must contain one program audio stream")
    audio_stream = audio_streams[0]
    _require(
        audio_stream.get("codec_name") == "pcm_s24le", "render audio must be 24-bit PCM"
    )
    _require(
        audio_stream.get("sample_rate") == str(AUDIO_RATE),
        "render audio must be 48 kHz",
    )
    _require(audio_stream.get("channels") == 2, "render audio must be stereo")

    prepared_summaries, prepared_data = _verify_prepared_audio(case)
    rendered_audio = _decode_render_audio(tools, mov_path)
    rendered_sample_count = len(rendered_audio) // 2
    expected_render_samples = expected_frames * SAMPLES_PER_FRAME
    _require(
        abs(rendered_sample_count - expected_render_samples) <= SAMPLES_PER_FRAME,
        "render audio duration differs from the timeline by more than one frame",
    )
    expected_clicks = case.expected_audio_samples
    policies = case.audio_policies
    expected_gains = case.expected_audio_gain_db
    rendered_audio_measurements: dict[str, Json] = {}
    for label in preparations:
        rendered_audio_measurements[label] = _measure_rendered_clicks(
            label,
            policies[label],
            expected_gains[label],
            by_label_visual[label],
            prepared_data.get(label),
            expected_clicks.get(label, ()),
            rendered_audio,
            by_label_audio.get(label),
        )

    stream_duration_value = video_stream.get("duration")
    if stream_duration_value not in (None, "N/A"):
        duration_error_frames = (
            abs(
                _fraction(stream_duration_value, "video duration")
                - Fraction(expected_frames, 1) / TARGET_RATE
            )
            * TARGET_RATE
        )
    else:
        duration_error_frames = Fraction(0)
    result: dict[str, Any] = {
        "schemaVersion": "issue178-render-measurements/v1",
        "status": "passed",
        "caseName": case.case_name,
        "movPath": str(mov_path),
        "nativeBinding": binding,
        "targetFrameRate": {
            "numerator": TARGET_RATE.numerator,
            "denominator": TARGET_RATE.denominator,
        },
        "frameCount": len(rendered_ordinals),
        "durationSeconds": float(video_duration),
        "durationErrorFrames": float(duration_error_frames),
        "cuts": cuts,
        "preparedAudio": prepared_summaries,
        "renderedAudio": {
            "sampleRate": AUDIO_RATE,
            "channels": 2,
            "sampleCount": rendered_sample_count,
            "events": rendered_audio_measurements,
        },
    }
    result_path = outputdir / "issue178-render-measurements.json"
    result_path.write_text(
        json.dumps(
            result, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    result["resultPath"] = str(result_path)
    return result
