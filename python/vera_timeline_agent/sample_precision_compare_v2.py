"""Host-side PCM comparison for the Issue 257 native sample probe."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import stat
import struct
import wave
from pathlib import Path
from typing import Any

SAMPLE_RATE = 48_000
CHANNELS = 2
SAMPLE_COUNT = 400_400
BASELINE_CONTROL_SAMPLES = 200_200
GAP_START = 232_320
GAP_END = 241_440
ROLLING_WINDOW = 960
MAX_PROGRAMME_RMS = 0.0004
MAX_ROLLING_RMS = 0.006
_PCM_SCALE = 1 << 23
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_INSTALLED_REQUEST_PATH = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins/vera-delivery-v2/request.json"
)
_OBSERVATION_STAGES = (
    "baseline",
    "baseline_after_reopen",
    "sample_lift",
    "sample_lift_after_reopen",
)
_RESULT_KEYS = {
    "schemaVersion",
    "status",
    "requestPath",
    "requestSha256",
    "hostRequestPath",
    "hostRequestSha256",
    "releaseSha256",
    "target",
    "source",
    "review",
    "programme",
    "profile",
    "oneUseIntentPath",
    "oneUseIntentSha256",
    "startedAt",
    "finishedAt",
    "preflight",
    "effects",
    "observations",
    "construction",
    "calibration",
    "render",
    "failure",
}
_EFFECT_SEQUENCE = (
    ("import_original_source", "ImportMedia"),
    ("append_baseline", "AppendToTimeline"),
    ("baseline_save", "SaveProject"),
    ("baseline_close", "CloseProject"),
    ("baseline_reopen", "LoadProject"),
    ("delete_own_baseline_nonripple", "Timeline.DeleteClips"),
    ("append_fractional_survivors", "AppendToTimeline"),
    ("sample_lift_save", "SaveProject"),
    ("sample_lift_close", "CloseProject"),
    ("sample_lift_reopen", "LoadProject"),
    ("render_select_format", "SetCurrentRenderFormatAndCodec"),
    ("render_select_single_clip", "SetCurrentRenderMode"),
    ("render_set_settings", "SetRenderSettings"),
    ("render_add_job", "AddRenderJob"),
    ("render_start_exact_job", "StartRendering"),
)


class SamplePrecisionCompareError(ValueError):
    """The bound source or native PCM cannot support this comparison."""


def _digest(value: str, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise SamplePrecisionCompareError(f"{label} must be a lowercase SHA256")
    return value


def _source_pcm(
    source_wav: bytes, expected_wav_sha256: str, expected_pcm_sha256: str
) -> list[int]:
    if type(source_wav) is not bytes:
        raise SamplePrecisionCompareError("source WAV must be immutable bytes")
    wav_sha256 = _digest(expected_wav_sha256, "source WAV hash")
    pcm_sha256 = _digest(expected_pcm_sha256, "source PCM hash")
    if hashlib.sha256(source_wav).hexdigest() != wav_sha256:
        raise SamplePrecisionCompareError("source WAV hash differs from its binding")
    try:
        with wave.open(io.BytesIO(source_wav), "rb") as stream:
            if (
                stream.getnchannels() != 1
                or stream.getsampwidth() != 3
                or stream.getframerate() != SAMPLE_RATE
                or stream.getnframes() != SAMPLE_COUNT
                or stream.getcomptype() != "NONE"
            ):
                raise SamplePrecisionCompareError(
                    "source WAV profile or extent differs"
                )
            raw = stream.readframes(SAMPLE_COUNT)
    except (EOFError, OSError, wave.Error) as error:
        raise SamplePrecisionCompareError("source WAV is not readable PCM") from error
    if len(raw) != SAMPLE_COUNT * 3:
        raise SamplePrecisionCompareError("source WAV PCM extent differs")
    if hashlib.sha256(raw).hexdigest() != pcm_sha256:
        raise SamplePrecisionCompareError("source PCM hash differs from its binding")
    values = []
    for offset in range(0, len(raw), 3):
        value = int.from_bytes(raw[offset : offset + 3], "little")
        values.append(value - (1 << 24) if value & (1 << 23) else value)
    return values


def _native_samples(raw: bytes, sample_format: str) -> tuple[list[int | float], int]:
    if type(raw) is not bytes:
        raise SamplePrecisionCompareError("native PCM must be immutable bytes")
    widths = {"s24le": 3, "s24-s32le": 4, "f32le": 4, "f64le": 8}
    width = widths.get(sample_format)
    if width is None:
        raise SamplePrecisionCompareError("native PCM format is unsupported")
    if len(raw) != SAMPLE_COUNT * CHANNELS * width:
        raise SamplePrecisionCompareError("native PCM sample count differs")
    if sample_format == "s24le":
        values: list[int | float] = []
        for offset in range(0, len(raw), 3):
            value = int.from_bytes(raw[offset : offset + 3], "little")
            values.append(value - (1 << 24) if value & (1 << 23) else value)
        return values, width
    code = {"s24-s32le": "i", "f32le": "f", "f64le": "d"}[sample_format]
    values = [item[0] for item in struct.iter_unpack(f"<{code}", raw)]
    if sample_format == "s24-s32le":
        if any(
            type(value) is not int or not -(1 << 23) <= value < (1 << 23)
            for value in values
        ):
            raise SamplePrecisionCompareError("native PCM exceeds signed 24-bit range")
    elif any(not math.isfinite(value) or not -1.0 <= value <= 1.0 for value in values):
        raise SamplePrecisionCompareError(
            "native floating PCM is non-finite or out of range"
        )
    return values, width


def compare_pcm(
    source_wav: bytes,
    native_interleaved_pcm: bytes,
    *,
    source_wav_sha256: str,
    source_pcm_sha256: str,
    native_pcm_sha256: str,
    native_sample_format: str,
    gap_start: int = GAP_START,
    gap_end: int = GAP_END,
) -> dict[str, Any]:
    """Compare exact zero-lag programme PCM, with only the reviewed gap muted.

    Integer formats use signed 24-bit sample values. ``s24-s32le`` is the
    pinned decoder's sign-extended signed-24 domain in four-byte containers.
    Floating formats are normalized full-scale samples.
    """
    if (gap_start, gap_end) != (GAP_START, GAP_END):
        raise SamplePrecisionCompareError("reviewed omission extent differs")
    source = _source_pcm(source_wav, source_wav_sha256, source_pcm_sha256)
    native_sha256 = _digest(native_pcm_sha256, "native PCM hash")
    if hashlib.sha256(native_interleaved_pcm).hexdigest() != native_sha256:
        raise SamplePrecisionCompareError("native PCM hash differs from its binding")
    actual, _ = _native_samples(native_interleaved_pcm, native_sample_format)

    errors: tuple[list[float], list[float]] = ([], [])
    exact_gap_zero = [True, True]
    for frame, expected_sample in enumerate(source):
        in_gap = GAP_START <= frame < GAP_END
        expected_int = 0 if in_gap else expected_sample
        for channel in range(CHANNELS):
            sample = actual[frame * CHANNELS + channel]
            if in_gap and sample != 0:
                exact_gap_zero[channel] = False
            if native_sample_format in {"f32le", "f64le"}:
                expected = expected_int / _PCM_SCALE
                error = float(sample) - expected
            else:
                error = (int(sample) - expected_int) / _PCM_SCALE
            errors[channel].append(error)

    channels = []
    for channel, channel_errors in enumerate(errors):
        rms = math.sqrt(
            math.fsum(error * error for error in channel_errors) / SAMPLE_COUNT
        )
        rolling_sum = 0.0
        max_rolling = 0.0
        squares = [error * error for error in channel_errors]
        for index, square in enumerate(squares):
            rolling_sum += square
            if index >= ROLLING_WINDOW:
                rolling_sum -= squares[index - ROLLING_WINDOW]
            if index >= ROLLING_WINDOW - 1:
                max_rolling = max(
                    max_rolling,
                    math.sqrt(max(0.0, rolling_sum / ROLLING_WINDOW)),
                )
        channels.append(
            {
                "channel": channel,
                "programmeRms": rms,
                "maxAbsoluteResidual": max(abs(error) for error in channel_errors),
                "maxSliding960Rms": max_rolling,
                "gapExactlyZero": exact_gap_zero[channel],
                "pass": (
                    exact_gap_zero[channel]
                    and rms <= MAX_PROGRAMME_RMS
                    and max_rolling <= MAX_ROLLING_RMS
                ),
            }
        )

    return {
        "schemaVersion": "vera-sample-precision-pcm-comparison/v1",
        "sourceWavSha256": source_wav_sha256,
        "sourcePcmSha256": source_pcm_sha256,
        "nativePcmSha256": native_sha256,
        "sampleRate": SAMPLE_RATE,
        "sourceChannels": 1,
        "nativeChannels": CHANNELS,
        "sampleCount": SAMPLE_COUNT,
        "nativeSampleFormat": native_sample_format,
        "gap": {"startSample": GAP_START, "endSample": GAP_END},
        "programmeRmsLimit": MAX_PROGRAMME_RMS,
        "maxSliding960RmsLimit": MAX_ROLLING_RMS,
        "channels": channels,
        "status": "pass" if all(item["pass"] for item in channels) else "fail",
    }


class _EvidenceError(SamplePrecisionCompareError):
    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


def _read_record(
    path: Path, *, immutable: bool = False, limit: int = 64 * 1024 * 1024
) -> bytes:
    from . import sample_precision_probe_v2 as probe

    path = Path(path)
    if immutable:
        try:
            info = path.lstat()
        except OSError as error:
            raise SamplePrecisionCompareError(
                "immutable probe evidence is unavailable"
            ) from error
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o222:
            raise SamplePrecisionCompareError(
                "probe evidence is not immutable regular data"
            )
    return probe._read(path, limit=limit)


def _file_sha256(path: Path, *, limit: int = 2 * 1024 * 1024 * 1024) -> str:
    from . import sample_precision_probe_v2 as probe

    path = Path(path)
    probe._no_symlink_ancestry(path)
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise SamplePrecisionCompareError("bound file is unavailable") from error
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > limit
        ):
            raise SamplePrecisionCompareError("bound file is outside its safe profile")
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(fd, 1024 * 1024):
            size += len(chunk)
            if size > limit:
                raise SamplePrecisionCompareError("bound file exceeded its size limit")
            digest.update(chunk)
        after = os.fstat(fd)
        if size != before.st_size or (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise SamplePrecisionCompareError("bound file changed while hashing")
        return digest.hexdigest()
    finally:
        os.close(fd)


def _load_json(payload: bytes, label: str) -> dict[str, Any]:
    from . import sample_precision_probe_v2 as probe

    try:
        return probe._json_object(payload)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise SamplePrecisionCompareError(
            f"{label} is not a closed JSON object"
        ) from error


def _finite_number(value: Any, label: str) -> float:
    if type(value) not in {int, float} or not math.isfinite(value):
        raise _EvidenceError("ambiguous", f"{label} is not a finite numeric getter")
    return float(value)


def _getter_number(item: dict[str, Any], key: str) -> float:
    raw = item.get("rawGetters")
    if type(raw) is not dict or key not in raw or type(raw[key]) is not dict:
        raise _EvidenceError("unsupported", f"required getter {key} is absent")
    getter = raw[key]
    if getter.get("status") == "unsupported":
        raise _EvidenceError("unsupported", f"required getter {key} is unsupported")
    if getter.get("status") != "supported":
        raise _EvidenceError("ambiguous", f"required getter {key} is ambiguous")
    expected_args = {
        "GetStart(True)": [True],
        "GetEnd(True)": [True],
        "GetDuration(True)": [True],
        "GetSourceStartTime": [],
        "GetSourceEndTime": [],
    }.get(key)
    if expected_args is not None and getter.get("arguments") != expected_args:
        raise _EvidenceError("ambiguous", f"getter {key} arguments differ")
    if getter.get("pythonType") not in {"int", "float"}:
        raise _EvidenceError(
            "ambiguous", f"getter {key} returned an uncalibratable type"
        )
    value = getter.get("value")
    if type(value) not in {int, float} or type(value).__name__ != getter["pythonType"]:
        raise _EvidenceError("ambiguous", f"getter {key} raw value/type disagree")
    return _finite_number(value, key)


def _baseline_control_frames(observations: Any) -> int:
    if type(observations) is not list or len(observations) < 2:
        raise _EvidenceError("unsupported", "baseline control observations are absent")
    values = []
    for stage, snapshot in zip(_OBSERVATION_STAGES[:2], observations[:2], strict=True):
        if type(snapshot) is not dict or snapshot.get("stage") != stage:
            raise _EvidenceError("ambiguous", "baseline control order differs")
        items = snapshot.get("items")
        if type(items) is not list or len(items) != 1 or type(items[0]) is not dict:
            raise _EvidenceError(
                "unsupported", "baseline control getter is unavailable"
            )
        values.append(_getter_number(items[0], "GetDuration(True)"))
    frame_choices = [
        frame_count
        for frame_count in (100, 101)
        if all(abs(value * 2002 - frame_count * 2002) < 0.5 for value in values)
    ]
    if len(frame_choices) != 1:
        raise _EvidenceError(
            "ambiguous",
            "baseline input-end calibration is not uniquely 100 or 101 frames",
        )
    return frame_choices[0]


def _geometry(observations: Any) -> dict[str, Any]:
    """Report calibrated geometry, including numeric edge errors on failure."""
    if type(observations) is not list or len(observations) != len(_OBSERVATION_STAGES):
        raise _EvidenceError("ambiguous", "native probe lifecycle is incomplete")
    stages: dict[str, list[dict[str, Any]]] = {}
    for expected_stage, snapshot in zip(_OBSERVATION_STAGES, observations, strict=True):
        if type(snapshot) is not dict or snapshot.get("stage") != expected_stage:
            raise _EvidenceError("ambiguous", "native geometry snapshot order differs")
        items = snapshot.get("items")
        expected_count = 1 if expected_stage.startswith("baseline") else 2
        if type(items) is not list or len(items) != expected_count:
            raise _EvidenceError(
                "unsupported", f"{expected_stage} item inventory is incomplete"
            )
        stages[expected_stage] = items

    identities: dict[str, tuple[Any, Any, Any]] = {}
    for stage, items in stages.items():
        seen: set[str] = set()
        for index, item in enumerate(items):
            if type(item) is not dict:
                raise _EvidenceError("ambiguous", f"{stage} item row is malformed")
            timeline_uid = item.get("timelineItemUid")
            source_uid = item.get("sourceUID")
            media_uid = item.get("mediaUID")
            if (
                type(timeline_uid) is not str
                or not timeline_uid
                or (
                    source_uid is not None
                    and (type(source_uid) is not str or not source_uid)
                )
                or type(media_uid) is not str
                or not media_uid
            ):
                raise _EvidenceError(
                    "unsupported", f"{stage} item identity is incomplete"
                )
            if timeline_uid in seen:
                raise _EvidenceError(
                    "ambiguous", f"{stage} contains duplicate timeline item UIDs"
                )
            seen.add(timeline_uid)
            identities[f"{stage}:{index}"] = (timeline_uid, source_uid, media_uid)

    if identities["baseline:0"][0] != identities["baseline_after_reopen:0"][0]:
        raise _EvidenceError(
            "ambiguous", "baseline timeline item UID changed after reopen"
        )
    for index in range(2):
        if (
            identities[f"sample_lift:{index}"][0]
            != identities[f"sample_lift_after_reopen:{index}"][0]
        ):
            raise _EvidenceError(
                "ambiguous", "survivor timeline item UID changed after reopen"
            )
    media_identities = {(row[1], row[2]) for row in identities.values()}
    if len(media_identities) != 1:
        raise _EvidenceError(
            "ambiguous", "observations do not bind to one source media item"
        )
    if len({row[0] for row in identities.values()}) != 3:
        raise _EvidenceError(
            "ambiguous", "baseline and survivor timeline item identities overlap"
        )

    baseline_frames = _baseline_control_frames(observations)
    baseline_samples = baseline_frames * 2002
    record_ranges = {
        "baseline": [(0, baseline_samples)],
        "baseline_after_reopen": [(0, baseline_samples)],
        "sample_lift": [(0, GAP_START), (GAP_END, SAMPLE_COUNT)],
        "sample_lift_after_reopen": [(0, GAP_START), (GAP_END, SAMPLE_COUNT)],
    }
    source_rows: list[tuple[str, int, dict[str, Any], tuple[int, int]]] = []
    timeline_rows: list[
        tuple[str, int, dict[str, Any], tuple[int, int], float, float, float]
    ] = []
    for stage, items in stages.items():
        for index, (item, expected_range) in enumerate(
            zip(items, record_ranges[stage], strict=True)
        ):
            _getter_number(item, "GetSourceStartTime")
            _getter_number(item, "GetSourceEndTime")
            source_rows.append((stage, index, item, expected_range))
            start_frame = _getter_number(item, "GetStart(True)")
            end_frame = _getter_number(item, "GetEnd(True)")
            duration_frames = _getter_number(item, "GetDuration(True)")
            timeline_rows.append(
                (
                    stage,
                    index,
                    item,
                    expected_range,
                    start_frame,
                    end_frame,
                    duration_frames,
                )
            )

    baseline_timeline_rows = [
        row for row in timeline_rows if row[0] in {"baseline", "baseline_after_reopen"}
    ]
    timeline_candidates: list[dict[str, Any]] = []
    for endpoint, end_adjustment in (("exclusive", 0), ("inclusive", 1)):
        checks: list[dict[str, Any]] = []
        for (
            stage,
            index,
            item,
            expected_range,
            start_frame,
            end_frame,
            duration,
        ) in baseline_timeline_rows:
            expected_start, expected_end = expected_range
            actual_start = start_frame * 2002
            actual_end = (end_frame + end_adjustment) * 2002
            actual_duration = duration * 2002
            errors = {
                "startSamples": actual_start - expected_start,
                "exclusiveEndSamples": actual_end - expected_end,
                "durationSamples": actual_duration - (expected_end - expected_start),
            }
            checks.append(
                {
                    "stage": stage,
                    "itemIndex": index,
                    "timelineItemUid": item["timelineItemUid"],
                    "readbackErrorsSamples": errors,
                    "pass": all(abs(error) < 0.5 for error in errors.values()),
                }
            )
        if all(check["pass"] for check in checks):
            timeline_candidates.append({"endEndpoint": endpoint, "checks": checks})
    if len(timeline_candidates) != 1:
        raise _EvidenceError(
            "ambiguous",
            "timeline endpoint semantics do not uniquely prove sample edges",
        )
    timeline_endpoint = timeline_candidates[0]["endEndpoint"]
    timeline_adjustment = 0 if timeline_endpoint == "exclusive" else 1
    timeline_checks: list[dict[str, Any]] = []
    for (
        stage,
        index,
        item,
        expected_range,
        start_frame,
        end_frame,
        duration,
    ) in timeline_rows:
        expected_start, expected_end = expected_range
        actual_start = start_frame * 2002
        actual_end = (end_frame + timeline_adjustment) * 2002
        actual_duration = duration * 2002
        errors = {
            "startSamples": actual_start - expected_start,
            "exclusiveEndSamples": actual_end - expected_end,
            "durationSamples": actual_duration - (expected_end - expected_start),
        }
        timeline_checks.append(
            {
                "stage": stage,
                "itemIndex": index,
                "timelineItemUid": item["timelineItemUid"],
                "expectedRecordStartSamples": expected_start,
                "expectedRecordEndExclusiveSamples": expected_end,
                "actualRecordStartSamples": actual_start,
                "actualRecordEndExclusiveSamples": actual_end,
                "readbackErrorsSamples": errors,
                "pass": all(abs(error) < 0.5 for error in errors.values()),
            }
        )

    baseline_source_rows = [
        row for row in source_rows if row[0] in {"baseline", "baseline_after_reopen"}
    ]
    candidates: list[dict[str, Any]] = []
    for unit, scale in (("seconds", SAMPLE_RATE), ("milliseconds", SAMPLE_RATE / 1000)):
        for endpoint, end_adjustment in (
            ("exclusive", 0),
            ("inclusive_sample", 1),
            ("inclusive_frame", 2002),
        ):
            checks = []
            for stage, index, item, expected in baseline_source_rows:
                raw_start = _getter_number(item, "GetSourceStartTime")
                raw_end = _getter_number(item, "GetSourceEndTime")
                start_error = raw_start * scale - expected[0]
                end_error = raw_end * scale + end_adjustment - expected[1]
                checks.append(
                    {
                        "stage": stage,
                        "itemIndex": index,
                        "timelineItemUid": item["timelineItemUid"],
                        "startErrorSamples": start_error,
                        "endExclusiveErrorSamples": end_error,
                        "pass": abs(start_error) < 0.5 and abs(end_error) < 0.5,
                    }
                )
            if all(check["pass"] for check in checks):
                candidates.append(
                    {"unit": unit, "endEndpoint": endpoint, "checks": checks}
                )
    if len(candidates) != 1:
        raise _EvidenceError(
            "ambiguous",
            "source time units/end-point semantics are not uniquely calibrated",
        )

    source_unit = candidates[0]["unit"]
    source_endpoint = candidates[0]["endEndpoint"]
    source_scale = SAMPLE_RATE if source_unit == "seconds" else SAMPLE_RATE / 1000
    source_adjustment = {
        "exclusive": 0,
        "inclusive_sample": 1,
        "inclusive_frame": 2002,
    }[source_endpoint]
    source_checks: list[dict[str, Any]] = []
    for stage, index, item, expected in source_rows:
        raw_start = _getter_number(item, "GetSourceStartTime")
        raw_end = _getter_number(item, "GetSourceEndTime")
        actual_start = raw_start * source_scale
        actual_end = raw_end * source_scale + source_adjustment
        start_error = actual_start - expected[0]
        end_error = actual_end - expected[1]
        source_checks.append(
            {
                "stage": stage,
                "itemIndex": index,
                "timelineItemUid": item["timelineItemUid"],
                "expectedSourceStartSamples": expected[0],
                "expectedSourceEndExclusiveSamples": expected[1],
                "actualSourceStartSamples": actual_start,
                "actualSourceEndExclusiveSamples": actual_end,
                "startErrorSamples": start_error,
                "endExclusiveErrorSamples": end_error,
                "pass": abs(start_error) < 0.5 and abs(end_error) < 0.5,
            }
        )

    geometry_pass = all(row["pass"] for row in (*timeline_checks, *source_checks))
    reason = None if geometry_pass else "measured record or source edge mismatch"
    baseline_timeline = [
        check
        for check in timeline_checks
        if check["stage"] in {"baseline", "baseline_after_reopen"}
    ]
    baseline_source = [
        check
        for check in source_checks
        if check["stage"] in {"baseline", "baseline_after_reopen"}
    ]
    return {
        "status": "pass" if geometry_pass else "mismatch",
        "reason": reason,
        "baselineControlFrames": baseline_frames,
        "timelineEndEndpoint": timeline_endpoint,
        "baselineGetterPrecision": {
            "status": "pass"
            if all(row["pass"] for row in (*baseline_timeline, *baseline_source))
            else "mismatch",
            "timelineChecks": baseline_timeline,
            "sourceTimeChecks": baseline_source,
        },
        "sourceTimeCalibration": {
            "unit": source_unit,
            "endEndpoint": source_endpoint,
            "candidateCount": len(candidates),
            "calibratedFrom": "baseline_control",
            "checks": source_checks,
        },
        "timelineChecks": timeline_checks,
        "itemIdentities": [
            {
                "stageAndIndex": key,
                "timelineItemUid": value[0],
                "sourceUID": value[1],
                "mediaUID": value[2],
            }
            for key, value in identities.items()
        ],
    }


def _geometry_report(observations: Any) -> dict[str, Any]:
    baseline = _baseline_precision_report(observations)
    try:
        report = _geometry(observations)
        report["baselineGetterPrecision"] = baseline
        return report
    except _EvidenceError as error:
        return {
            "status": error.status,
            "baselineGetterPrecision": baseline,
            "reason": str(error),
        }
    except SamplePrecisionCompareError as error:
        return {
            "status": "ambiguous",
            "baselineGetterPrecision": baseline,
            "reason": str(error),
        }


def _baseline_precision_report(observations: Any) -> dict[str, Any]:
    try:
        if type(observations) is not list or len(observations) < 2:
            raise _EvidenceError(
                "unsupported", "baseline getter snapshots are unavailable"
            )
        baseline_rows = []
        for expected_stage, snapshot in zip(
            _OBSERVATION_STAGES[:2], observations[:2], strict=True
        ):
            if type(snapshot) is not dict or snapshot.get("stage") != expected_stage:
                raise _EvidenceError("ambiguous", "baseline snapshot order differs")
            items = snapshot.get("items")
            if type(items) is not list or len(items) != 1 or type(items[0]) is not dict:
                raise _EvidenceError(
                    "unsupported", "baseline clip getter snapshot is unavailable"
                )
            baseline_rows.append((expected_stage, items[0]))
        first_uid = baseline_rows[0][1].get("timelineItemUid")
        if any(row.get("timelineItemUid") != first_uid for _, row in baseline_rows):
            raise _EvidenceError(
                "ambiguous", "baseline timeline item UID changed after reopen"
            )
        timeline_rows: list[tuple[str, dict[str, Any], float, float, float]] = []
        source_checks: list[tuple[str, float, float]] = []
        baseline_frames = _baseline_control_frames(observations)
        baseline_samples = baseline_frames * 2002
        for stage, row in baseline_rows:
            start = _getter_number(row, "GetStart(True)") * 2002
            end = _getter_number(row, "GetEnd(True)")
            duration = _getter_number(row, "GetDuration(True)") * 2002
            timeline_rows.append((stage, row, start, end, duration))
            source_checks.append(
                (
                    stage,
                    _getter_number(row, "GetSourceStartTime"),
                    _getter_number(row, "GetSourceEndTime"),
                )
            )
        timeline_candidates: list[dict[str, Any]] = []
        for endpoint, end_adjustment in (("exclusive", 0), ("inclusive", 1)):
            row_checks: list[dict[str, Any]] = []
            for stage, row, start, end, duration in timeline_rows:
                row_errors = {
                    "startSamples": start,
                    "exclusiveEndSamples": (end + end_adjustment) * 2002
                    - baseline_samples,
                    "durationSamples": duration - baseline_samples,
                }
                row_checks.append(
                    {
                        "stage": stage,
                        "timelineItemUid": row["timelineItemUid"],
                        "readbackErrorsSamples": row_errors,
                        "pass": all(abs(value) < 0.5 for value in row_errors.values()),
                    }
                )
            if all(item["pass"] for item in row_checks):
                timeline_candidates.append(
                    {"endEndpoint": endpoint, "checks": row_checks}
                )
        if len(timeline_candidates) != 1:
            raise _EvidenceError(
                "ambiguous",
                "baseline timeline getter precision is not uniquely calibrated",
            )
        candidates: list[dict[str, Any]] = []
        for unit, scale in (
            ("seconds", SAMPLE_RATE),
            ("milliseconds", SAMPLE_RATE / 1000),
        ):
            for endpoint, end_adjustment in (
                ("exclusive", 0),
                ("inclusive_sample", 1),
                ("inclusive_frame", 2002),
            ):
                unit_errors = [
                    (
                        start * scale,
                        end * scale + end_adjustment - baseline_samples,
                    )
                    for _, start, end in source_checks
                ]
                if all(
                    abs(start) < 0.5 and abs(end) < 0.5 for start, end in unit_errors
                ):
                    candidates.append(
                        {
                            "unit": unit,
                            "endEndpoint": endpoint,
                            "errors": unit_errors,
                        }
                    )
        if len(candidates) != 1:
            raise _EvidenceError(
                "ambiguous",
                "baseline source-time getter units are not uniquely calibrated",
            )
        return {
            "status": "pass",
            "baselineControlFrames": baseline_frames,
            "unit": candidates[0]["unit"],
            "endEndpoint": candidates[0]["endEndpoint"],
            "candidateCount": len(candidates),
            "timelineEndEndpoint": timeline_candidates[0]["endEndpoint"],
            "timelineChecks": timeline_candidates[0]["checks"],
            "sourceTimeChecks": [
                {"stage": stage, "start": start, "end": end}
                for stage, start, end in source_checks
            ],
        }
    except _EvidenceError as error:
        return {"status": error.status, "reason": str(error)}


def _source_and_review_current(request: dict[str, Any]) -> bytes:
    from . import sample_precision_probe_v2 as probe

    source_path = Path(request["sourcePath"])
    pcm_sha, sample_count = probe._validate_source(
        source_path, expected_sha=request["sourceSha256"]
    )
    if pcm_sha != request["sourcePcmSha256"] or sample_count != SAMPLE_COUNT:
        raise SamplePrecisionCompareError(
            "reviewed original source PCM binding differs"
        )
    review_path = Path(request["reviewPath"])
    if hashlib.sha256(_read_record(review_path)).hexdigest() != request["reviewSha256"]:
        raise SamplePrecisionCompareError("review confirmation bytes changed")
    marker_sha, marker_path = probe._verify_review(review_path)
    if marker_sha != request["markerSha256"] or marker_path != Path(
        request["markerPath"]
    ):
        raise SamplePrecisionCompareError("review marker binding differs")
    return _read_record(source_path)


def _current_release(request: dict[str, Any]) -> None:
    from . import sample_precision_probe_v2 as probe
    from . import workflow_v2_cli
    from .workflow_package import sha256

    root = Path(request["releaseRoot"])
    manifest = workflow_v2_cli._verify_release_files(
        root, workflow_v2_cli.SAMPLE_PRECISION_RUNTIME_FILES
    )
    if sha256(manifest) != request["releaseSha256"]:
        raise SamplePrecisionCompareError("request-pinned release manifest changed")
    if (
        probe._verify_release(root, request["releaseSha256"])
        != request["releaseSha256"]
    ):
        raise SamplePrecisionCompareError("native precision release binding changed")


def _verify_result_bindings(
    request: dict[str, Any],
    request_path: Path,
    result: dict[str, Any],
    result_path: Path,
) -> None:
    from . import sample_precision_probe_v2 as probe

    if (
        set(result) != _RESULT_KEYS
        or result.get("schemaVersion") != probe.RESULT_SCHEMA
    ):
        raise SamplePrecisionCompareError(
            "native result schema or closed shape differs"
        )
    if result.get("status") not in {
        "rendered_for_pcm_verification",
        "unsupported",
        "ambiguous",
    }:
        raise SamplePrecisionCompareError("native result status is invalid")
    output_dir = Path(request["outputDir"])
    if (
        request_path != output_dir / "request.json"
        or result_path != output_dir / "result.json"
        or result.get("hostRequestPath") != str(request_path)
        or type(result.get("hostRequestSha256")) is not str
        or result.get("hostRequestSha256")
        != hashlib.sha256(_read_record(request_path, immutable=True)).hexdigest()
        or type(result.get("requestPath")) is not str
        or Path(result["requestPath"]) != _INSTALLED_REQUEST_PATH
        or type(result.get("requestSha256")) is not str
        or result.get("requestSha256") != result.get("hostRequestSha256")
        or result.get("releaseSha256") != request["releaseSha256"]
        or result.get("target") != request["target"]
        or result.get("source")
        != {
            "path": request["sourcePath"],
            "sha256": request["sourceSha256"],
            "pcmSha256": request["sourcePcmSha256"],
            "sampleRate": request["sampleRate"],
            "channels": request["channels"],
            "bitDepth": request["bitDepth"],
            "samples": request["sourceSamples"],
        }
        or result.get("review")
        != {
            "path": request["reviewPath"],
            "sha256": request["reviewSha256"],
            "markerPath": request["markerPath"],
            "markerSha256": request["markerSha256"],
        }
        or result.get("programme")
        != {
            "frameSamples": request["frameSamples"],
            "sampleRate": request["sampleRate"],
            "channels": request["channels"],
            "bitDepth": request["bitDepth"],
            "sourceSamples": request["sourceSamples"],
            "programmeSamples": request["programmeSamples"],
            "targetGap": request["targetGap"],
            "supports": request["supports"],
        }
        or result.get("profile") != request["profile"]
    ):
        raise SamplePrecisionCompareError("native result does not bind to this request")
    if request["outputDir"] != str(output_dir) or not output_dir.is_absolute():
        raise SamplePrecisionCompareError("request output directory is not canonical")

    intent_root = probe.PROBE_STATE_ROOT / "intents"
    target_key = hashlib.sha256(
        "\0".join(
            (request["target"]["projectUid"], request["target"]["timelineUid"])
        ).encode()
    ).hexdigest()
    target_intent = intent_root / f"target-{target_key}.json"
    invocation_intent = intent_root / f"request-{result['requestSha256']}.json"
    if result.get("oneUseIntentPath") != str(target_intent):
        raise SamplePrecisionCompareError("native result intent target differs")
    target_bytes = _read_record(target_intent, immutable=True)
    invocation_bytes = _read_record(invocation_intent, immutable=True)
    target_record = _load_json(target_bytes, "target intent")
    invocation_record = _load_json(invocation_bytes, "invocation intent")
    if (
        hashlib.sha256(target_bytes).hexdigest() != result.get("oneUseIntentSha256")
        or target_record != invocation_record
        or target_record.get("schemaVersion") != "vera-sample-precision-probe-intent/v1"
        or target_record.get("requestSha256") != result["requestSha256"]
        or target_record.get("target") != request["target"]
    ):
        raise SamplePrecisionCompareError("native one-use intent binding differs")


def _verify_effect_journals(
    result: dict[str, Any], request_sha: str, output_dir: Path
) -> None:

    effects = result.get("effects")
    if type(effects) is not list or len(effects) > len(_EFFECT_SEQUENCE):
        raise SamplePrecisionCompareError("native effect list is malformed")
    if result["status"] == "rendered_for_pcm_verification" and len(effects) != len(
        _EFFECT_SEQUENCE
    ):
        raise SamplePrecisionCompareError(
            "completed native result has an incomplete effect journal"
        )
    journal_dir = output_dir / "journal"
    seen_paths: set[Path] = set()
    for index, row in enumerate(effects):
        if type(row) is not dict or index >= len(_EFFECT_SEQUENCE):
            raise SamplePrecisionCompareError("native effect row is malformed")
        expected_stage, expected_method = _EFFECT_SEQUENCE[index]
        if row.get("stage") != expected_stage or row.get("method") != expected_method:
            raise SamplePrecisionCompareError("native effect sequence differs")
        journal_path = Path(row.get("journalPath", ""))
        if (
            journal_path.parent != journal_dir
            or not journal_path.name.startswith(f"effect-{index + 1:02d}-")
            or journal_path in seen_paths
        ):
            raise SamplePrecisionCompareError("native effect journal path differs")
        seen_paths.add(journal_path)
        payload = _read_record(journal_path, immutable=True)
        if hashlib.sha256(payload).hexdigest() != row.get("journalSha256"):
            raise SamplePrecisionCompareError("native effect journal hash differs")
        journal = _load_json(payload, "native effect journal")
        if (
            set(journal)
            != {
                "schemaVersion",
                "requestSha256",
                "target",
                "stage",
                "method",
                "arguments",
                "preparedAt",
                "status",
            }
            or journal.get("schemaVersion") != "vera-sample-precision-probe-effect/v1"
            or journal.get("requestSha256") != request_sha
            or journal.get("target") != result["target"]
            or journal.get("stage") != expected_stage
            or journal.get("method") != expected_method
            or journal.get("arguments") != row.get("arguments")
            or journal.get("status") != "prepared_before_native_call"
        ):
            raise SamplePrecisionCompareError("native effect journal content differs")
        if (
            result["status"] == "rendered_for_pcm_verification"
            and row.get("status") != "returned"
        ):
            raise SamplePrecisionCompareError("completed native effect did not return")
    if result["status"] == "rendered_for_pcm_verification":
        render = result.get("render")
        if type(render) is not dict or type(render.get("outputPath")) is not str:
            raise SamplePrecisionCompareError(
                "completed result has no fixed render path"
            )
        from . import sample_precision_probe_v2 as probe

        expected_settings = probe._render_settings(Path(render["outputPath"]))
        if effects[12].get("arguments") != [expected_settings]:
            raise SamplePrecisionCompareError(
                "render settings effect journal differs from the fixed request"
            )
        if effects[10].get("arguments") != ["mov", "ProRes422"]:
            raise SamplePrecisionCompareError("render format effect journal differs")
        if effects[11].get("arguments") != [1]:
            raise SamplePrecisionCompareError("render mode effect journal differs")
        if effects[13].get("arguments") != []:
            raise SamplePrecisionCompareError("render job effect journal differs")
        if effects[14].get("arguments") != [[render.get("jobId")]]:
            raise SamplePrecisionCompareError("render start effect journal differs")


def _verify_construction(result: dict[str, Any]) -> None:
    construction = result.get("construction")
    if (
        type(construction) is not dict
        or construction.get("status") != "constructed_fractional_arguments"
    ):
        raise SamplePrecisionCompareError("native survivor construction is incomplete")
    baseline = construction.get("baseline")
    calibration = construction.get("calibration")
    try:
        observed_duration = _finite_number(
            calibration.get("observedDurationFrames")
            if type(calibration) is dict
            else None,
            "baseline calibration duration",
        )
    except _EvidenceError as error:
        raise SamplePrecisionCompareError(str(error)) from error
    frame_choices = [
        (frames, adjustment)
        for frames, adjustment in ((100, 0), (101, -1))
        if abs(observed_duration - frames) < 0.5 / 2002
    ]
    if len(frame_choices) == 1 and type(result.get("observations")) is list:
        try:
            baseline_frames = _baseline_control_frames(result["observations"])
        except _EvidenceError as error:
            raise SamplePrecisionCompareError(str(error)) from error
    else:
        baseline_frames = None
    if (
        len(frame_choices) != 1
        or type(calibration) is not dict
        or calibration.get("inputEndFrame") != 100
        or calibration.get("appendEndFrameAdjustment") != frame_choices[0][1]
        or result.get("calibration") != calibration
        or baseline_frames != frame_choices[0][0]
        or any(
            abs(
                _getter_number(snapshot["items"][0], "GetDuration(True)")
                - observed_duration
            )
            >= 0.5 / 2002
            for snapshot in result["observations"][:2]
        )
    ):
        raise SamplePrecisionCompareError("native baseline calibration differs")
    if (
        type(baseline) is not dict
        or baseline.get("startFrame") != 0.0
        or baseline.get("endFrame") != 100.0
        or baseline.get("recordFrame") != 0.0
        or baseline.get("trackIndex") != 1
        or baseline.get("mediaType") != 2
    ):
        raise SamplePrecisionCompareError("native baseline arguments differ")
    delete = construction.get("delete")
    if (
        type(delete) is not dict
        or delete.get("timelineItemUid")
        != result["observations"][0]["items"][0].get("timelineItemUid")
        or delete.get("rippleDelete") is not False
    ):
        raise SamplePrecisionCompareError(
            "native deletion was not the owned non-ripple edit"
        )
    survivors = construction.get("survivors")
    expected = [
        {"startSample": 0, "endSampleExclusive": GAP_START},
        {"startSample": GAP_END, "endSampleExclusive": SAMPLE_COUNT},
    ]
    if type(survivors) is not dict or survivors.get("sourceSampleRanges") != expected:
        raise SamplePrecisionCompareError("native survivor source ranges differ")
    infos = survivors.get("infos")
    if type(infos) is not list or len(infos) != 2:
        raise SamplePrecisionCompareError(
            "native survivor append arguments are incomplete"
        )
    media_uids = {
        item.get("mediaUID")
        for snapshot in result["observations"]
        for item in snapshot["items"]
    }
    if len(media_uids) != 1 or any(
        item.get("mediaPoolItem") not in media_uids for item in infos
    ):
        raise SamplePrecisionCompareError(
            "native survivor arguments target a different media item"
        )
    for index, (info, source_range) in enumerate(zip(infos, expected, strict=True)):
        start = source_range["startSample"] / 2002
        end = (
            source_range["endSampleExclusive"] / 2002
            + calibration["appendEndFrameAdjustment"]
        )
        if (
            type(info) is not dict
            or info.get("startFrame") != start
            or info.get("endFrame") != end
            or info.get("recordFrame") != start
            or info.get("trackIndex") != 1
            or info.get("mediaType") != 2
        ):
            raise SamplePrecisionCompareError(
                f"native survivor {index} arguments differ"
            )


def _verify_post_render_snapshot(result: dict[str, Any]) -> None:
    render = result.get("render")
    observations = result.get("observations")
    post_render = render.get("postRenderObservation") if type(render) is dict else None
    if (
        type(observations) is not list
        or len(observations) != len(_OBSERVATION_STAGES)
        or type(post_render) is not dict
        or post_render.get("stage") != "sample_lift_after_render"
        or post_render.get("items") != observations[-1].get("items")
    ):
        raise SamplePrecisionCompareError(
            "sample-lift geometry changed or is unverified after native render"
        )


def _verdict(
    native_status: str, geometry: dict[str, Any], pcm: dict[str, Any]
) -> tuple[str, str | None]:
    if pcm.get("status") == "fail":
        return "unsupported", "measured_pcm_mismatch"
    if geometry.get("status") == "mismatch":
        return "unsupported", "measured_geometry_mismatch"
    if geometry.get("status") == "ambiguous":
        return "ambiguous", "geometry_or_mapping_ambiguous"
    if geometry.get("status") != "pass":
        return "unsupported", "required_getter_unavailable"
    if native_status == "ambiguous":
        return "ambiguous", "native_probe_ambiguous"
    if pcm.get("status") != "pass":
        return "unsupported", "pcm_decode_unavailable"
    if native_status != "rendered_for_pcm_verification":
        return "unsupported", "native_probe_unsupported"
    return "supported", None


def _decode_probe_mov(
    mov_path: Path, expected_sha256: str
) -> tuple[bytes, dict[str, Any]]:
    """Decode the probe MOV with the shipped pinned tools, without #215 lineage."""
    from . import qualification_output_decode_v2 as decoder

    expected_sha = _digest(expected_sha256, "native MOV hash")
    fd, input_state = decoder._input_fd(mov_path)
    try:
        input_sha = decoder._hash_fd(fd)
        if input_sha != expected_sha:
            raise SamplePrecisionCompareError(
                "native MOV hash differs from the immutable result"
            )
        source_graph = decoder._source_graph_sha256()
        toolchain = decoder._verify_toolchain()
        input_ref = f"/dev/fd/{fd}"
        profile = decoder._probe_mov(fd, input_ref)
        decoder._validate_profile(profile, extent_frames=200, width=1920, height=1080)
        raw_s32 = decoder._decode_mov(fd, input_ref, SAMPLE_COUNT)
        pcm = decoder._signed24_domain(raw_s32, SAMPLE_COUNT)
        if (
            decoder._hash_fd(fd) != input_sha
            or decoder._state(os.fstat(fd)) != input_state
        ):
            raise SamplePrecisionCompareError("native MOV changed during decode")
        try:
            if (
                mov_path.resolve(strict=True) != mov_path
                or decoder._state(mov_path.lstat()) != input_state
            ):
                raise SamplePrecisionCompareError(
                    "native MOV path changed during decode"
                )
        except OSError as error:
            raise SamplePrecisionCompareError(
                "native MOV path changed during decode"
            ) from error
        decoder._assert_toolchain_current(toolchain)
        if decoder._source_graph_sha256() != source_graph:
            raise SamplePrecisionCompareError(
                "pinned decoder source graph changed during decode"
            )
        identity = {
            "ffmpeg": {
                "path": toolchain.ffmpeg.path,
                "version": toolchain.ffmpeg.version,
                "sha256": toolchain.ffmpeg.sha256,
            },
            "ffprobe": {
                "path": toolchain.ffprobe.path,
                "version": toolchain.ffprobe.version,
                "sha256": toolchain.ffprobe.sha256,
            },
            "profile": "QuickTime/ProRes422/apcn + stereo PCM24/lpcm/48k, 200 frames",
            "decoderIdentitySha256": decoder._decoder_identity_sha256(
                toolchain, width=1920, height=1080
            ),
            "decoderSourceGraphSha256": source_graph,
            "decoderCommandSha256": decoder._command_sha256(input_ref, toolchain),
            "sampleCount": SAMPLE_COUNT,
            "decodedPcmSha256": hashlib.sha256(pcm).hexdigest(),
        }
        return pcm, identity
    finally:
        os.close(fd)


def finalize_probe(request_path: Path, result_path: Path, output: Path) -> Path:
    """Authenticate a completed native probe and publish the host PCM verdict."""
    from . import sample_precision_probe_v2 as probe
    from .workflow_package import write_immutable_json

    request_path, result_path, output = map(Path, (request_path, result_path, output))
    for path in (request_path, result_path, output):
        probe._no_symlink_ancestry(Path(os.path.abspath(path)))
    if output.exists() or output.is_symlink():
        raise SamplePrecisionCompareError("finalization report path already exists")
    if (
        not request_path.is_absolute()
        or not result_path.is_absolute()
        or not output.is_absolute()
    ):
        raise SamplePrecisionCompareError("finalization paths must be absolute")
    request_bytes = _read_record(request_path, immutable=True)
    request_sha = hashlib.sha256(request_bytes).hexdigest()
    request = probe.load_probe_request(request_path, request_sha, require_live=False)
    result_bytes = _read_record(result_path, immutable=True)
    result_sha = hashlib.sha256(result_bytes).hexdigest()
    result = _load_json(result_bytes, "native result")
    _verify_result_bindings(request, request_path, result, result_path)

    _current_release(request)
    source_wav = _source_and_review_current(request)
    _verify_effect_journals(result, request_sha, Path(request["outputDir"]))
    geometry = _geometry_report(result.get("observations"))
    native_render: dict[str, Any] = {"status": "unsupported"}
    pcm: dict[str, Any] = {
        "status": "unsupported",
        "reason": "native render was not authenticated",
    }
    host_comparator_sha = hashlib.sha256(_read_record(Path(__file__))).hexdigest()
    decoder_identity: dict[str, Any] | None = None

    if result["status"] == "rendered_for_pcm_verification":
        _verify_construction(result)
        _verify_post_render_snapshot(result)
        render = result.get("render")
        if type(render) is not dict:
            raise SamplePrecisionCompareError("native render record is malformed")
        output_dir = Path(request["outputDir"])
        expected_mov = output_dir / "renders" / f"issue257-{request['requestId']}.mov"
        if (
            render.get("status") != "rendered_for_pcm_verification"
            or render.get("outputPath") != str(expected_mov)
            or type(render.get("sha256")) is not str
            or render.get("formatCodec") != {"format": "mov", "codec": "ProRes422"}
            or type(render.get("jobId")) is not str
            or type(render.get("job")) is not dict
            or type(render.get("jobStatus")) is not dict
            or render["jobStatus"].get("JobStatus") != "Complete"
        ):
            raise SamplePrecisionCompareError(
                "native render profile or terminal job binding differs"
            )
        try:
            probe._verify_job(render["job"], render["jobId"], expected_mov)
            requested_settings = probe._render_settings(expected_mov)
        except (ValueError, TypeError, KeyError) as error:
            raise SamplePrecisionCompareError(
                "native render job differs from the fixed profile"
            ) from error
        if (
            type(render.get("settings")) is not dict
            or render["settings"].get("requested") != requested_settings
        ):
            raise SamplePrecisionCompareError("native render requested settings differ")
        readback = render["settings"].get("readback")
        if type(readback) is not dict:
            raise SamplePrecisionCompareError(
                "native render settings readback is malformed"
            )
        if readback.get("status") in {"unsupported", "ambiguous"}:
            if readback.get("method") != "Project.GetRenderSettings":
                raise SamplePrecisionCompareError(
                    "render settings getter diagnostic differs"
                )
        elif any(
            readback.get(key) != value for key, value in requested_settings.items()
        ):
            raise SamplePrecisionCompareError(
                "native render settings getter differs from the fixed profile"
            )
        mov_sha = _file_sha256(expected_mov)
        if mov_sha != render["sha256"]:
            raise SamplePrecisionCompareError(
                "native render bytes differ from result hash"
            )
        native_render = {
            "status": "authenticated",
            "path": str(expected_mov),
            "sha256": mov_sha,
            "jobId": render["jobId"],
            "job": render["job"],
            "jobStatus": render["jobStatus"],
            "formatCodec": render["formatCodec"],
            "settings": render["settings"],
        }
        try:
            decoded, decoder_identity = _decode_probe_mov(expected_mov, mov_sha)
            pcm = compare_pcm(
                source_wav,
                decoded,
                source_wav_sha256=request["sourceSha256"],
                source_pcm_sha256=request["sourcePcmSha256"],
                native_pcm_sha256=hashlib.sha256(decoded).hexdigest(),
                native_sample_format="s24-s32le",
                gap_start=request["targetGap"]["startSample"],
                gap_end=request["targetGap"]["endSample"],
            )
        except (
            SamplePrecisionCompareError,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            pcm = {"status": "unsupported", "reason": str(error)[:1000]}
        if (
            hashlib.sha256(_read_record(Path(__file__))).hexdigest()
            != host_comparator_sha
        ):
            raise SamplePrecisionCompareError(
                "host PCM comparator source changed during finalization"
            )
    else:
        pcm["reason"] = (
            "PCM comparison not run: native probe produced no completed render/MOV"
        )

    # Recheck every mutable source binding after the potentially long decode.
    _current_release(request)
    if (
        hashlib.sha256(_read_record(request_path, immutable=True)).hexdigest()
        != request_sha
    ):
        raise SamplePrecisionCompareError("probe request changed during finalization")
    if (
        hashlib.sha256(_read_record(result_path, immutable=True)).hexdigest()
        != result_sha
    ):
        raise SamplePrecisionCompareError("native result changed during finalization")
    if (
        hashlib.sha256(_source_and_review_current(request)).hexdigest()
        != request["sourceSha256"]
    ):
        raise SamplePrecisionCompareError("reviewed source changed during finalization")
    if (
        native_render.get("status") == "authenticated"
        and _file_sha256(Path(native_render["path"])) != native_render["sha256"]
    ):
        raise SamplePrecisionCompareError("native MOV changed during finalization")

    verdict, reason_category = _verdict(result["status"], geometry, pcm)
    report = {
        "schemaVersion": "vera-sample-precision-probe-finalization/v1",
        "status": verdict,
        "reasonCategory": reason_category,
        "requestPath": str(request_path),
        "requestSha256": request_sha,
        "hostRequestPath": str(request_path),
        "hostRequestSha256": request_sha,
        "resultPath": str(result_path),
        "resultSha256": result_sha,
        "releaseSha256": request["releaseSha256"],
        "nativeResultStatus": result["status"],
        "nativeRequestPath": result["requestPath"],
        "nativeRequestSha256": result["requestSha256"],
        "target": request["target"],
        "source": result["source"],
        "review": result["review"],
        "nativeRender": native_render,
        "baselineGetterPrecision": geometry.get(
            "baselineGetterPrecision", {"status": "unsupported"}
        ),
        "baselineCalibration": result.get("calibration"),
        "geometry": geometry,
        "pcm": pcm,
        "decoder": decoder_identity,
        "hostComparatorSha256": host_comparator_sha,
        "failure": result.get("failure"),
    }
    protected = (
        Path(request["sourcePath"]).parent,
        Path(request["reviewPath"]).parent,
        Path(request["markerPath"]).parent,
        Path(request["releaseRoot"]),
    )
    if any(
        output.is_relative_to(path) or path.is_relative_to(output) for path in protected
    ):
        raise SamplePrecisionCompareError(
            "finalization output overlaps reviewed media or evidence"
        )
    write_immutable_json(output, report)
    return output
