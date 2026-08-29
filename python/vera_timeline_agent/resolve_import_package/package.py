"""Build and independently verify one Resolve Free import project."""

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from itertools import pairwise
from pathlib import Path, PurePosixPath
from typing import Any, cast

import opentimelineio as otio  # type: ignore[import-untyped]

from vera_timeline_agent.otio_package import (
    PackageBuildError as ContractValidationError,
)
from vera_timeline_agent.otio_package import (
    validate_build_report,
    validate_timeline_manifest,
)
from vera_timeline_agent.placeholder_slate import render_placeholder_slate

MANIFEST_FILENAME = "timeline-manifest.json"
REPORT_FILENAME = "build-report.json"
OTIO_FILENAME = "timeline.otio"
INSTRUCTIONS_FILENAME = "IMPORT_INSTRUCTIONS.md"
VERIFICATION_FILENAME = "package-verification.json"
_HASH_PREFIX = "sha256:"
_RECEIPT_SCHEMA = "resolve-import-package-verification/v1"
_SUPPORTED_POLICIES = {"clone_or_copy", "copy"}

JsonObject = dict[str, Any]


class ResolveImportPackageError(RuntimeError):
    """An actionable error that prevents ready-to-import publication."""


@dataclass(frozen=True)
class ResolveImportPackageResult:
    """Paths and counts for one published, verified project root."""

    project_root: Path
    build_root: Path
    manifest_path: Path
    report_path: Path
    otio_path: Path
    instructions_path: Path
    verification_path: Path
    build_id: str
    event_count: int
    marker_count: int
    media_count: int
    reused: bool


@dataclass(frozen=True)
class ResolveImportVerification:
    """Counts proven by independently parsing all published artifacts."""

    build_id: str
    event_count: int
    marker_count: int
    media_count: int


@dataclass(frozen=True)
class _MaterializationRequest:
    source_id: str
    artifact_id: str
    origin: Path
    policy: str


def _load_json(path: Path, label: str) -> tuple[JsonObject, bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except FileNotFoundError as error:
        raise ResolveImportPackageError(f"{label} does not exist: {path}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ResolveImportPackageError(
            f"could not read {label} {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise ResolveImportPackageError(f"{label} must contain one JSON object: {path}")
    return cast(JsonObject, value), raw


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _require_canonical(value: JsonObject, raw: bytes, label: str) -> None:
    if raw != _canonical_json(value):
        raise ResolveImportPackageError(
            f"{label} is not canonical JSON; refusing to rewrite compiler output"
        )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise ResolveImportPackageError(f"could not hash {path}: {error}") from error
    return digest.hexdigest()


def _hash_value(value: str, label: str) -> str:
    if not value.startswith(_HASH_PREFIX) or len(value) != len(_HASH_PREFIX) + 64:
        raise ResolveImportPackageError(f"{label} is not a sha256 content hash")
    return value[len(_HASH_PREFIX) :]


def _unique_by_id(values: list[JsonObject], label: str) -> dict[str, JsonObject]:
    result: dict[str, JsonObject] = {}
    for value in values:
        identity = cast(str, value["id"])
        if identity in result:
            raise ResolveImportPackageError(f"duplicate {label} id {identity}")
        result[identity] = value
    return result


def _safe_relative_path(value: str, label: str) -> PurePosixPath:
    if "\\" in value:
        raise ResolveImportPackageError(f"{label} must use POSIX separators: {value}")
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != value
    ):
        raise ResolveImportPackageError(f"unsafe {label}: {value}")
    return path


def _safe_manifest_destination(source: Mapping[str, Any]) -> PurePosixPath:
    source_id = cast(str, source["id"])
    value = cast(str, source["path"])
    path = _safe_relative_path(value, f"manifest path for source {source_id}")
    if len(path.parts) < 3 or path.parts[0] != "Media":
        raise ResolveImportPackageError(
            f"source {source_id} destination must be below Media/: {value}"
        )
    expected_area = (
        "Narration"
        if source["kind"] == "audio" and path.parts[1] == "Narration"
        else "Resolved"
    )
    if path.parts[1] != expected_area:
        raise ResolveImportPackageError(
            f"source {source_id} has unsupported media destination: {value}"
        )
    return path


def _safe_existing_regular(path: Path, label: str) -> Path:
    try:
        absolute = path.absolute()
        current = Path(absolute.anchor)
        for component in absolute.parts[1:]:
            current /= component
            entry = current.lstat()
            if stat.S_ISLNK(entry.st_mode):
                raise ResolveImportPackageError(
                    f"{label} contains a symbolic link: {path}"
                )
        details = absolute.stat(follow_symlinks=False)
    except FileNotFoundError as error:
        raise ResolveImportPackageError(f"{label} does not exist: {path}") from error
    except OSError as error:
        raise ResolveImportPackageError(
            f"could not inspect {label} {path}: {error}"
        ) from error
    if not stat.S_ISREG(details.st_mode):
        raise ResolveImportPackageError(f"{label} is not a regular file: {path}")
    if details.st_nlink != 1:
        raise ResolveImportPackageError(f"{label} is hard-linked: {path}")
    return absolute


def _load_plan(
    plan_path: Path, sources: dict[str, JsonObject]
) -> dict[str, _MaterializationRequest]:
    value, _ = _load_json(plan_path, "materialization plan")
    expected = {
        source_id
        for source_id, source in sources.items()
        if source["kind"] != "placeholder"
    }
    if set(value) != expected:
        raise ResolveImportPackageError(
            "materialization plan source IDs differ from non-placeholder manifest "
            f"sources; missing={sorted(expected - set(value))}, "
            f"unexpected={sorted(set(value) - expected)}"
        )
    result: dict[str, _MaterializationRequest] = {}
    for source_id in sorted(expected):
        entry = value[source_id]
        if not isinstance(entry, dict) or set(entry) != {
            "artifactId",
            "origin",
            "policy",
        }:
            raise ResolveImportPackageError(
                f"materialization plan entry {source_id} must contain exactly "
                "artifactId, origin, and policy"
            )
        artifact_id = entry["artifactId"]
        origin_value = entry["origin"]
        policy = entry["policy"]
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ResolveImportPackageError(f"source {source_id} has no artifactId")
        if not isinstance(origin_value, str) or not origin_value:
            raise ResolveImportPackageError(f"source {source_id} has no origin")
        if not isinstance(policy, str) or policy not in _SUPPORTED_POLICIES:
            raise ResolveImportPackageError(
                f"source {source_id} policy must be one of "
                f"{sorted(_SUPPORTED_POLICIES)}"
            )
        origin = Path(origin_value)
        if not origin.is_absolute():
            origin = plan_path.parent / origin
        origin = _safe_existing_regular(origin, f"origin for source {source_id}")
        result[source_id] = _MaterializationRequest(
            source_id=source_id,
            artifact_id=artifact_id,
            origin=origin,
            policy=policy,
        )
    return result


def _validate_contracts(manifest: JsonObject, report: JsonObject) -> None:
    try:
        validate_timeline_manifest(manifest)
        validate_build_report(report)
    except ContractValidationError as error:
        raise ResolveImportPackageError(str(error)) from error


def _range_end(frame_range: Mapping[str, Any]) -> int:
    return cast(int, frame_range["startFrame"] + frame_range["durationFrames"])


def _validate_report_linkage(
    manifest: JsonObject, report: JsonObject, manifest_bytes: bytes
) -> None:
    status = report["status"]
    if status not in {"ready", "ready_with_warnings"}:
        raise ResolveImportPackageError(
            f"compiler report status {status!r} cannot be published"
        )
    comparisons = (
        (report["buildId"], manifest["buildId"], "build ID"),
        (report["sourceDocument"], manifest["sourceDocument"], "source document"),
        (report["timeline"], manifest["timeline"], "timeline settings"),
        (report["manifest"]["id"], manifest["id"], "manifest ID"),
        (
            report["manifest"]["contentHash"],
            f"{_HASH_PREFIX}{_sha256_bytes(manifest_bytes)}",
            "manifest content hash",
        ),
    )
    for actual, expected, label in comparisons:
        if actual != expected:
            raise ResolveImportPackageError(
                f"build report {label} differs from manifest"
            )

    events = cast(list[JsonObject], manifest["events"])
    results = cast(list[JsonObject], report["eventResults"])
    result_by_event: dict[str, JsonObject] = {}
    for result in results:
        event_id = cast(str, result["eventId"])
        if event_id in result_by_event:
            raise ResolveImportPackageError(
                f"duplicate build report event result {event_id}"
            )
        result_by_event[event_id] = result
    if set(result_by_event) != {cast(str, event["id"]) for event in events}:
        raise ResolveImportPackageError("build report event results are incomplete")
    for event in events:
        event_id = cast(str, event["id"])
        result = result_by_event[event_id]
        expected_disposition = (
            "placeholder" if event["kind"] == "placeholder" else "placed"
        )
        expected = {
            "sourceId": event["sourceId"],
            "trackId": event["trackId"],
            "trackKind": event["trackKind"],
            "recordRange": event["recordRange"],
            "disposition": expected_disposition,
        }
        if any(result[key] != value for key, value in expected.items()):
            raise ResolveImportPackageError(
                f"build report event result differs from manifest event {event_id}"
            )

    manual_items = cast(list[JsonObject], report["manualCompletionItems"])
    if len({item["id"] for item in manual_items}) != len(manual_items):
        raise ResolveImportPackageError(
            "build report has duplicate manual-completion IDs"
        )
    issues = cast(list[JsonObject], report["issues"])
    expected_summary = {
        "sourceCount": len(manifest["sources"]),
        "eventCount": len(events),
        "markerCount": len(manifest["markers"]),
        "placedCount": sum(result["disposition"] == "placed" for result in results),
        "placeholderCount": sum(
            result["disposition"] == "placeholder" for result in results
        ),
        "manualCompletionCount": len(manual_items),
        "warningCount": sum(issue["severity"] == "warning" for issue in issues),
        "errorCount": sum(
            issue["severity"] in {"error", "blocking"} for issue in issues
        ),
    }
    if report["summary"] != expected_summary:
        raise ResolveImportPackageError("build report summary counts are inconsistent")
    if expected_summary["errorCount"]:
        raise ResolveImportPackageError(
            "ready compiler report contains error or blocking issues"
        )
    expected_status = (
        "ready_with_warnings" if expected_summary["warningCount"] else "ready"
    )
    if report["status"] != expected_status:
        raise ResolveImportPackageError(
            "build report readiness status is inconsistent with warning count"
        )


def _validate_manifest_semantics(manifest: JsonObject) -> None:
    tracks = cast(list[JsonObject], manifest["tracks"])
    sources = cast(list[JsonObject], manifest["sources"])
    events = cast(list[JsonObject], manifest["events"])
    transitions = cast(list[JsonObject], manifest["transitions"])
    markers = cast(list[JsonObject], manifest["markers"])
    track_by_id = _unique_by_id(tracks, "track")
    source_by_id = _unique_by_id(sources, "source")
    event_by_id = _unique_by_id(events, "event")
    _unique_by_id(transitions, "transition")
    _unique_by_id(markers, "marker")

    slots: set[tuple[str, int]] = set()
    for track in tracks:
        slot = (cast(str, track["kind"]), cast(int, track["index"]))
        if slot in slots:
            raise ResolveImportPackageError(f"duplicate track slot {slot[0]} {slot[1]}")
        slots.add(slot)

    timeline = cast(JsonObject, manifest["timeline"])
    timeline_start = cast(int, timeline["startFrame"])
    timeline_end = timeline_start + cast(int, timeline["durationFrames"])
    events_by_track: defaultdict[str, list[JsonObject]] = defaultdict(list)
    used_source_ids: set[str] = set()
    destinations: set[PurePosixPath] = set()
    portable_destinations: set[str] = set()
    for source in sources:
        if source["kind"] != "placeholder":
            destination = _safe_manifest_destination(source)
            if destination in destinations:
                raise ResolveImportPackageError(
                    f"duplicate media destination {destination}"
                )
            destinations.add(destination)
            portable = unicodedata.normalize("NFC", destination.as_posix()).casefold()
            if portable in portable_destinations:
                raise ResolveImportPackageError(
                    "case-folded or normalized media destination collision: "
                    f"{destination}"
                )
            portable_destinations.add(portable)

    for event in events:
        event_id = cast(str, event["id"])
        resolved_track = track_by_id.get(cast(str, event["trackId"]))
        resolved_source = source_by_id.get(cast(str, event["sourceId"]))
        if resolved_track is None or resolved_source is None:
            raise ResolveImportPackageError(
                f"event {event_id} has an unknown track or source"
            )
        if event["trackKind"] != resolved_track["kind"]:
            raise ResolveImportPackageError(f"event {event_id} track kind differs")
        if event["kind"] != resolved_source["kind"]:
            raise ResolveImportPackageError(f"event {event_id} source kind differs")
        record_range = cast(JsonObject, event["recordRange"])
        if (
            record_range["startFrame"] < timeline_start
            or _range_end(record_range) > timeline_end
        ):
            raise ResolveImportPackageError(f"event {event_id} is outside the timeline")
        if event["kind"] in {"audio", "video"}:
            source_range = cast(JsonObject, event["sourceRange"])
            if _range_end(source_range) > resolved_source["durationFrames"]:
                raise ResolveImportPackageError(
                    f"event {event_id} exceeds source duration"
                )
            if event["kind"] == "audio":
                duration_matches = (
                    source_range["durationFrames"] == record_range["durationFrames"]
                )
            else:
                source_rate = cast(JsonObject, resolved_source["frameRate"])
                timeline_rate = cast(JsonObject, timeline["frameRate"])
                duration_matches = (
                    source_range["durationFrames"]
                    * source_rate["denominator"]
                    * timeline_rate["numerator"]
                    == record_range["durationFrames"]
                    * timeline_rate["denominator"]
                    * source_rate["numerator"]
                )
            if not duration_matches:
                raise ResolveImportPackageError(
                    f"event {event_id} requires unsupported retiming"
                )
        used_source_ids.add(cast(str, event["sourceId"]))
        events_by_track[cast(str, event["trackId"])].append(event)

    if used_source_ids != set(source_by_id):
        raise ResolveImportPackageError(
            "manifest contains unused or missing source records"
        )
    for track_id, track_events in events_by_track.items():
        ordered = sorted(
            track_events, key=lambda item: item["recordRange"]["startFrame"]
        )
        for previous, current in pairwise(ordered):
            if (
                _range_end(previous["recordRange"])
                > current["recordRange"]["startFrame"]
            ):
                raise ResolveImportPackageError(
                    f"events {previous['id']} and {current['id']} overlap on "
                    f"track {track_id}"
                )

    declared_boundaries: set[tuple[str, str, int]] = set()
    for transition in transitions:
        if transition["kind"] != "hard_cut":
            raise ResolveImportPackageError("only hard-cut transitions are supported")
        before = event_by_id.get(cast(str, transition["fromEventId"]))
        after = event_by_id.get(cast(str, transition["toEventId"]))
        if (
            before is None
            or after is None
            or before["trackId"] != after["trackId"]
            or _range_end(before["recordRange"]) != transition["atFrame"]
            or after["recordRange"]["startFrame"] != transition["atFrame"]
        ):
            raise ResolveImportPackageError(
                f"hard cut {transition['id']} is not an adjacent same-track boundary"
            )
        boundary = (
            cast(str, transition["fromEventId"]),
            cast(str, transition["toEventId"]),
            cast(int, transition["atFrame"]),
        )
        if boundary in declared_boundaries:
            raise ResolveImportPackageError(
                f"hard cut {transition['id']} duplicates a declared boundary"
            )
        declared_boundaries.add(boundary)
    adjacent_boundaries: set[tuple[str, str, int]] = set()
    for track_id, track_events in events_by_track.items():
        if track_by_id[track_id]["kind"] != "video":
            continue
        ordered = sorted(
            track_events, key=lambda item: item["recordRange"]["startFrame"]
        )
        for previous, current in pairwise(ordered):
            at_frame = _range_end(previous["recordRange"])
            if at_frame == current["recordRange"]["startFrame"]:
                adjacent_boundaries.add(
                    (cast(str, previous["id"]), cast(str, current["id"]), at_frame)
                )
    if adjacent_boundaries != declared_boundaries:
        raise ResolveImportPackageError(
            "manifest hard-cut declarations differ from adjacent video boundaries"
        )
    for marker in markers:
        if marker["state"] != "placed":
            raise ResolveImportPackageError(f"marker {marker['id']} is not placed")
        if not timeline_start <= marker["frame"] <= timeline_end:
            raise ResolveImportPackageError(
                f"marker {marker['id']} is outside the timeline"
            )


def _probe(path: Path, executable: str) -> JsonObject:
    command = [
        executable,
        "-v",
        "error",
        "-count_frames",
        "-show_entries",
        "stream=codec_type,width,height,channels,sample_rate,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,duration,duration_ts,time_base",
        "-of",
        "json",
        str(path),
    ]
    try:
        process = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError as error:
        raise ResolveImportPackageError(f"could not run FFprobe: {error}") from error
    if process.returncode != 0:
        detail = process.stderr.strip() or f"exit {process.returncode}"
        raise ResolveImportPackageError(f"FFprobe rejected {path}: {detail}")
    try:
        value = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise ResolveImportPackageError(
            f"FFprobe returned invalid JSON for {path}"
        ) from error
    if not isinstance(value, dict) or not isinstance(value.get("streams"), list):
        raise ResolveImportPackageError(f"FFprobe found no streams in {path}")
    return cast(JsonObject, value)


def _fraction(value: str, label: str) -> Fraction:
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ResolveImportPackageError(f"invalid FFprobe {label}: {value}") from error


def _duration_frames(stream: Mapping[str, Any], rate: Fraction) -> int | None:
    duration_ts = stream.get("duration_ts")
    time_base = stream.get("time_base")
    if duration_ts not in {None, "N/A"} and isinstance(time_base, str):
        duration = Fraction(int(duration_ts)) * _fraction(time_base, "time_base")
    elif isinstance(stream.get("duration"), str) and stream["duration"] != "N/A":
        duration = _fraction(cast(str, stream["duration"]), "duration")
    else:
        return None
    frames = duration * rate
    return (frames.numerator + frames.denominator - 1) // frames.denominator


def _verify_probe(
    source: JsonObject,
    path: Path,
    executable: str,
    timeline_rate: Fraction | None = None,
) -> JsonObject:
    probed = _probe(path, executable)
    streams = cast(list[JsonObject], probed["streams"])
    kind = cast(str, source["kind"])
    if kind == "audio":
        audio = next(
            (stream for stream in streams if stream.get("codec_type") == "audio"), None
        )
        if audio is None:
            raise ResolveImportPackageError(
                f"source {source['id']} has no audio stream"
            )
        sample_rate = int(audio.get("sample_rate", 0))
        channels = int(audio.get("channels", 0))
        if sample_rate != source["sampleRate"] or channels != source["channels"]:
            raise ResolveImportPackageError(
                f"source {source['id']} audio metadata differs from manifest"
            )
        if timeline_rate is None:
            raise ResolveImportPackageError("audio verification requires timeline rate")
        actual_duration = _duration_frames(audio, timeline_rate)
        declared_duration = cast(int, source["durationFrames"])
        if actual_duration is None or abs(actual_duration - declared_duration) > 1:
            raise ResolveImportPackageError(
                f"source {source['id']} duration differs from manifest"
            )
        return {
            "sampleRate": sample_rate,
            "channels": channels,
            "durationFrames": actual_duration,
        }

    video = next(
        (stream for stream in streams if stream.get("codec_type") == "video"), None
    )
    if video is None:
        raise ResolveImportPackageError(f"source {source['id']} has no video stream")
    width = int(video.get("width", 0))
    height = int(video.get("height", 0))
    if width != source["width"] or height != source["height"]:
        raise ResolveImportPackageError(
            f"source {source['id']} dimensions differ from manifest"
        )
    facts: JsonObject = {"width": width, "height": height}
    if kind == "video":
        rate_data = cast(JsonObject, source["frameRate"])
        expected_rate = Fraction(rate_data["numerator"], rate_data["denominator"])
        rate_text = cast(
            str, video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
        )
        actual_rate = _fraction(rate_text, "frame rate")
        if actual_rate != expected_rate:
            raise ResolveImportPackageError(
                f"source {source['id']} frame rate differs from manifest"
            )
        declared_duration = cast(int, source["durationFrames"])
        count_value = video.get("nb_read_frames") or video.get("nb_frames")
        actual_duration = (
            int(count_value)
            if count_value not in {None, "N/A"}
            else _duration_frames(video, expected_rate)
        )
        if actual_duration is None or abs(actual_duration - declared_duration) > 1:
            raise ResolveImportPackageError(
                f"source {source['id']} duration differs from manifest"
            )
        facts.update(
            {
                "frameRate": {
                    "numerator": actual_rate.numerator,
                    "denominator": actual_rate.denominator,
                },
                "durationFrames": actual_duration,
            }
        )
        if "audioChannels" in source:
            audio = next(
                (stream for stream in streams if stream.get("codec_type") == "audio"),
                None,
            )
            actual_channels = 0 if audio is None else int(audio.get("channels", 0))
            if actual_channels != source["audioChannels"]:
                raise ResolveImportPackageError(
                    f"source {source['id']} embedded audio channels differ from "
                    "manifest"
                )
            facts["audioChannels"] = actual_channels
    return facts


def _clone_file(source: Path, destination: Path) -> bool:
    if sys.platform == "darwin":
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            clonefile = libc.clonefile
            clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
            clonefile.restype = ctypes.c_int
            result = clonefile(os.fsencode(source), os.fsencode(destination), 0)
            if result == 0:
                return True
        except (AttributeError, OSError):
            pass
        destination.unlink(missing_ok=True)
        return False
    if sys.platform.startswith("linux"):
        try:
            import fcntl

            ficlone = 0x40049409
            with (
                source.open("rb") as input_stream,
                destination.open("xb") as output_stream,
            ):
                fcntl.ioctl(output_stream.fileno(), ficlone, input_stream.fileno())
            return True
        except OSError as error:
            destination.unlink(missing_ok=True)
            if error.errno not in {
                errno.EINVAL,
                errno.ENOTTY,
                errno.EOPNOTSUPP,
                errno.EXDEV,
            }:
                return False
    return False


def _materialize(source: Path, destination: Path, policy: str) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if policy == "clone_or_copy" and _clone_file(source, destination):
        mode = "clone"
    else:
        try:
            shutil.copyfile(source, destination)
        except OSError as error:
            raise ResolveImportPackageError(
                f"could not copy {source} to {destination}: {error}"
            ) from error
        mode = "copy"
    details = destination.stat(follow_symlinks=False)
    if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
        raise ResolveImportPackageError(
            f"materialized media is not an independent regular file: {destination}"
        )
    return mode


def _rate(manifest: Mapping[str, Any]) -> float:
    frame_rate = manifest["timeline"]["frameRate"]
    return cast(float, frame_rate["numerator"] / frame_rate["denominator"])


def _time_range(start: int, duration: int, rate: float) -> Any:
    return otio.opentime.TimeRange(
        otio.opentime.RationalTime(start, rate),
        otio.opentime.RationalTime(duration, rate),
    )


def _track_kind(kind: str) -> str:
    if kind == "video":
        return cast(str, otio.schema.Track.Kind.Video)
    if kind == "audio":
        return cast(str, otio.schema.Track.Kind.Audio)
    return kind


def _marker_color(value: str) -> str:
    normalized = value.upper()
    return (
        normalized
        if normalized
        in {
            "RED",
            "PINK",
            "ORANGE",
            "YELLOW",
            "GREEN",
            "CYAN",
            "BLUE",
            "PURPLE",
            "MAGENTA",
            "BLACK",
            "WHITE",
        }
        else "RED"
    )


def _media_locator(source: JsonObject) -> str:
    if source["kind"] == "placeholder":
        relative = PurePosixPath("Media") / "Placeholders" / f"{source['id']}.png"
    else:
        relative = _safe_manifest_destination(source)
    return (PurePosixPath("..") / ".." / relative).as_posix()


def _build_otio(manifest: JsonObject) -> Any:
    settings = cast(JsonObject, manifest["timeline"])
    start = cast(int, settings["startFrame"])
    end = start + cast(int, settings["durationFrames"])
    timeline_rate = _rate(manifest)
    timeline = otio.schema.Timeline(
        name=f"VERA build {manifest['buildId']}",
        global_start_time=otio.opentime.RationalTime(start, timeline_rate),
    )
    timeline.metadata["vera"] = {
        "schema_version": manifest["schemaVersion"],
        "manifest_id": manifest["id"],
        "build_id": manifest["buildId"],
        "timeline_settings": settings,
    }
    timeline.tracks.metadata["vera"] = {"hard_cuts": manifest["transitions"]}
    sources = _unique_by_id(cast(list[JsonObject], manifest["sources"]), "source")
    by_track: defaultdict[str, list[JsonObject]] = defaultdict(list)
    for event in cast(list[JsonObject], manifest["events"]):
        by_track[event["trackId"]].append(event)

    for track_data in cast(list[JsonObject], manifest["tracks"]):
        track = otio.schema.Track(
            name=track_data["name"],
            kind=_track_kind(cast(str, track_data["kind"])),
            metadata={
                "vera": {
                    "track_id": track_data["id"],
                    "track_kind": track_data["kind"],
                    "track_index": track_data["index"],
                }
            },
        )
        cursor = start
        for event in sorted(
            by_track[track_data["id"]],
            key=lambda item: item["recordRange"]["startFrame"],
        ):
            event_start = cast(int, event["recordRange"]["startFrame"])
            duration = cast(int, event["recordRange"]["durationFrames"])
            if event_start > cursor:
                track.append(
                    otio.schema.Gap(
                        source_range=_time_range(0, event_start - cursor, timeline_rate)
                    )
                )
            source = sources[event["sourceId"]]
            source_range = cast(
                JsonObject,
                event.get("sourceRange", {"startFrame": 0, "durationFrames": duration}),
            )
            source_rate = timeline_rate
            if source["kind"] == "video":
                rate_data = cast(JsonObject, source["frameRate"])
                source_rate = rate_data["numerator"] / rate_data["denominator"]
            available_duration = cast(int, source.get("durationFrames", duration))
            metadata: JsonObject = {
                "source_id": source["id"],
                "source_kind": source["kind"],
            }
            if source["kind"] == "placeholder":
                metadata.update({"label": source["label"], "reason": source["reason"]})
            else:
                metadata["content_hash"] = source["contentHash"]
            media_reference = otio.schema.ExternalReference(
                target_url=_media_locator(source),
                available_range=_time_range(0, available_duration, source_rate),
                metadata={"vera": metadata},
            )
            clip = otio.schema.Clip(
                name=(
                    cast(str, source["label"])
                    if source["kind"] == "placeholder"
                    else f"{source['kind']}: {PurePosixPath(source['path']).name}"
                ),
                media_reference=media_reference,
                source_range=_time_range(
                    cast(int, source_range["startFrame"]),
                    cast(int, source_range["durationFrames"]),
                    source_rate,
                ),
                metadata={
                    "vera": {
                        "event_id": event["id"],
                        "event_kind": event["kind"],
                        "source_id": event["sourceId"],
                        "source_kind": source["kind"],
                        "track_id": event["trackId"],
                        "record_range": event["recordRange"],
                        "timing_precision": event["timingPrecision"],
                        "alignment_version": event["alignmentVersion"],
                        "provenance": event["provenance"],
                        **(
                            {
                                "placeholder": {
                                    "label": source["label"],
                                    "reason": source["reason"],
                                }
                            }
                            if source["kind"] == "placeholder"
                            else {}
                        ),
                    }
                },
            )
            track.append(clip)
            cursor = event_start + duration
        if cursor < end:
            track.append(
                otio.schema.Gap(
                    source_range=_time_range(0, end - cursor, timeline_rate)
                )
            )
        timeline.tracks.append(track)

    for marker in cast(list[JsonObject], manifest["markers"]):
        timeline.tracks.markers.append(
            otio.schema.Marker(
                name=marker["name"],
                marked_range=_time_range(
                    cast(int, marker["frame"]) - start, 0, timeline_rate
                ),
                color=_marker_color(cast(str, marker["color"])),
                metadata={
                    "vera": {
                        "marker_id": marker["id"],
                        "note": marker["note"],
                        "original_color": marker["color"],
                        "provenance": marker["provenance"],
                    }
                },
            )
        )
    return timeline


def _instructions(manifest: JsonObject, report: JsonObject) -> str:
    tracks = cast(list[JsonObject], manifest["tracks"])
    markers = cast(list[JsonObject], manifest["markers"])
    items = cast(list[JsonObject], report["manualCompletionItems"])
    track_lines = "\n".join(
        f"- {track['kind']} {track['index']}: `{track['name']}`" for track in tracks
    )
    marker_lines = (
        "\n".join(
            f"- frame {marker['frame']}: {marker['name']} ({marker['color']})"
            for marker in markers
        )
        or "- None"
    )
    manual_lines = (
        "\n".join(f"- `{item['id']}` — {item['action']}" for item in items) or "- None"
    )
    return f"""# VERA Resolve Free import instructions

Build: `{manifest["buildId"]}`

Keep the complete Authoring Project folder intact. The OTIO file links media
through safe project-relative paths into `../../Media/`.

## Before import

1. Confirm `{VERIFICATION_FILENAME}` reports `ready_to_import`.
2. Read `{REPORT_FILENAME}`; its issues and manual-completion list are the
   compiler's unchanged authoritative report.
3. Do not rename, move, or replace individual files.

## Import

1. In DaVinci Resolve Free choose **File → Import → Timeline…**.
2. Select `{OTIO_FILENAME}` in this directory.
3. If Resolve requests relinking, select the Authoring Project `Media/`
   directory and do not substitute similarly named media.
4. Play the complete {manifest["timeline"]["durationFrames"]}-frame timeline at
   the manifest's {manifest["timeline"]["frameRate"]["numerator"]}/
   {manifest["timeline"]["frameRate"]["denominator"]} fps rate.
5. Confirm all edits are hard cuts, all placeholder slates are visible and
   labeled, narration is audible, and resolved media is online.

## Expected tracks

{track_lines}

## Expected markers

{marker_lines}

## Manual completion

{manual_lines}

Automated verification proves package structure, hashes, media facts, and
parsed OTIO agreement. It does not claim that Resolve Free imported or played
the timeline correctly; that final observation is the producer acceptance gate.
"""


def _plain_metadata(value: Any) -> Any:
    if hasattr(value, "items"):
        return {key: _plain_metadata(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)) or type(value).__name__ == "AnyVector":
        return [_plain_metadata(item) for item in value]
    return value


def _default_verified_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_verified_at(value: object) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ResolveImportPackageError(
            "verification receipt verifiedAt must be an RFC 3339 UTC timestamp"
        )
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError as error:
        raise ResolveImportPackageError(
            "verification receipt verifiedAt must be an RFC 3339 UTC timestamp"
        ) from error
    if parsed.tzinfo != UTC:
        raise ResolveImportPackageError(
            "verification receipt verifiedAt must be an RFC 3339 UTC timestamp"
        )
    return value


def _receipt(
    manifest: JsonObject,
    manifest_bytes: bytes,
    report: JsonObject,
    report_bytes: bytes,
    materializations: list[JsonObject],
    placeholders: list[JsonObject],
    verified_at: str,
    otio_bytes: bytes,
    instructions_bytes: bytes,
) -> JsonObject:
    return {
        "schemaVersion": _RECEIPT_SCHEMA,
        "status": "ready_to_import",
        "verifiedAt": verified_at,
        "buildId": manifest["buildId"],
        "manifest": {
            "id": manifest["id"],
            "contentHash": f"{_HASH_PREFIX}{_sha256_bytes(manifest_bytes)}",
        },
        "buildReport": {
            "id": report["id"],
            "contentHash": f"{_HASH_PREFIX}{_sha256_bytes(report_bytes)}",
        },
        "packageArtifacts": {
            "timelineOtio": {
                "path": OTIO_FILENAME,
                "contentHash": f"{_HASH_PREFIX}{_sha256_bytes(otio_bytes)}",
            },
            "importInstructions": {
                "path": INSTRUCTIONS_FILENAME,
                "contentHash": f"{_HASH_PREFIX}{_sha256_bytes(instructions_bytes)}",
            },
        },
        "timeline": manifest["timeline"],
        "eventCount": len(manifest["events"]),
        "markerCount": len(manifest["markers"]),
        "mediaCount": len(manifest["sources"]),
        "manualCompletionItemIds": [
            item["id"] for item in report["manualCompletionItems"]
        ],
        "materializations": materializations,
        "placeholderSlates": placeholders,
    }


def _write_package(
    staging: Path,
    manifest: JsonObject,
    manifest_bytes: bytes,
    report: JsonObject,
    report_bytes: bytes,
    requests: dict[str, _MaterializationRequest],
    ffprobe_executable: str,
    verified_at: str,
) -> None:
    build_id = cast(str, manifest["buildId"])
    build_root = staging / "Builds" / build_id
    build_root.mkdir(parents=True)
    (build_root / MANIFEST_FILENAME).write_bytes(manifest_bytes)
    (build_root / REPORT_FILENAME).write_bytes(report_bytes)
    materializations: list[JsonObject] = []
    placeholders: list[JsonObject] = []
    for source in cast(list[JsonObject], manifest["sources"]):
        source_id = cast(str, source["id"])
        if source["kind"] == "placeholder":
            relative = PurePosixPath("Media") / "Placeholders" / f"{source_id}.png"
            destination = staging.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = render_placeholder_slate(
                cast(str, source["label"]),
                cast(int, manifest["timeline"]["width"]),
                cast(int, manifest["timeline"]["height"]),
            )
            destination.write_bytes(data)
            _verify_probe(
                {
                    "id": source_id,
                    "kind": "still",
                    "width": manifest["timeline"]["width"],
                    "height": manifest["timeline"]["height"],
                },
                destination,
                ffprobe_executable,
            )
            placeholders.append(
                {
                    "sourceId": source_id,
                    "path": relative.as_posix(),
                    "contentHash": f"{_HASH_PREFIX}{_sha256_file(destination)}",
                    "label": source["label"],
                    "reason": source["reason"],
                    "width": manifest["timeline"]["width"],
                    "height": manifest["timeline"]["height"],
                }
            )
            continue
        request = requests[source_id]
        relative = _safe_manifest_destination(source)
        expected_hash = _hash_value(
            cast(str, source["contentHash"]), f"source {source_id} hash"
        )
        actual_origin_hash = _sha256_file(request.origin)
        if actual_origin_hash != expected_hash:
            raise ResolveImportPackageError(
                f"origin hash mismatch for source {source_id}: expected "
                f"{expected_hash}, found {actual_origin_hash}"
            )
        destination = staging.joinpath(*relative.parts)
        mode = _materialize(request.origin, destination, request.policy)
        actual_hash = _sha256_file(destination)
        if actual_hash != expected_hash:
            raise ResolveImportPackageError(
                f"materialized hash mismatch for source {source_id}"
            )
        timeline_rate_data = cast(JsonObject, manifest["timeline"]["frameRate"])
        facts = _verify_probe(
            source,
            destination,
            ffprobe_executable,
            Fraction(
                timeline_rate_data["numerator"], timeline_rate_data["denominator"]
            ),
        )
        materializations.append(
            {
                "sourceId": source_id,
                "artifactId": request.artifact_id,
                "mode": mode,
                "path": relative.as_posix(),
                "contentHash": source["contentHash"],
                "mediaFacts": facts,
            }
        )

    timeline = _build_otio(manifest)
    otio.adapters.write_to_file(
        timeline, str(build_root / OTIO_FILENAME), adapter_name="otio_json"
    )
    otio_bytes = (build_root / OTIO_FILENAME).read_bytes()
    instructions_bytes = _instructions(manifest, report).encode("utf-8")
    (build_root / INSTRUCTIONS_FILENAME).write_bytes(instructions_bytes)
    receipt = _receipt(
        manifest,
        manifest_bytes,
        report,
        report_bytes,
        materializations,
        placeholders,
        verified_at,
        otio_bytes,
        instructions_bytes,
    )
    (build_root / VERIFICATION_FILENAME).write_bytes(_canonical_json(receipt))


def _result(
    project_root: Path, verification: ResolveImportVerification, reused: bool
) -> ResolveImportPackageResult:
    build_root = project_root / "Builds" / verification.build_id
    return ResolveImportPackageResult(
        project_root=project_root,
        build_root=build_root,
        manifest_path=build_root / MANIFEST_FILENAME,
        report_path=build_root / REPORT_FILENAME,
        otio_path=build_root / OTIO_FILENAME,
        instructions_path=build_root / INSTRUCTIONS_FILENAME,
        verification_path=build_root / VERIFICATION_FILENAME,
        build_id=verification.build_id,
        event_count=verification.event_count,
        marker_count=verification.marker_count,
        media_count=verification.media_count,
        reused=reused,
    )


def build_resolve_import_package(
    manifest_path: Path | str,
    report_path: Path | str,
    materialization_plan_path: Path | str,
    project_root: Path | str,
    *,
    ffprobe_executable: str = "ffprobe",
    verified_at: str | None = None,
) -> ResolveImportPackageResult:
    """Build, verify, and atomically publish one new section-8.2 project root."""
    manifest_file = Path(manifest_path)
    report_file = Path(report_path)
    plan_file = Path(materialization_plan_path)
    output = Path(project_root)
    manifest, manifest_bytes = _load_json(manifest_file, "timeline manifest")
    report, report_bytes = _load_json(report_file, "build report")
    _require_canonical(manifest, manifest_bytes, "timeline manifest")
    _require_canonical(report, report_bytes, "build report")
    _validate_contracts(manifest, report)
    _validate_report_linkage(manifest, report, manifest_bytes)
    _validate_manifest_semantics(manifest)
    sources = _unique_by_id(cast(list[JsonObject], manifest["sources"]), "source")
    requests = _load_plan(plan_file, sources)
    publication_time = _validate_verified_at(verified_at or _default_verified_at())

    if output.exists():
        try:
            verification = verify_resolve_import_package(
                output, ffprobe_executable=ffprobe_executable
            )
        except ResolveImportPackageError as error:
            raise ResolveImportPackageError(
                "project root already exists and is not the same verified package: "
                f"{output}"
            ) from error
        build_root = output / "Builds" / verification.build_id
        if (build_root / MANIFEST_FILENAME).read_bytes() != manifest_bytes or (
            build_root / REPORT_FILENAME
        ).read_bytes() != report_bytes:
            raise ResolveImportPackageError(
                "project root already exists for different compiler artifacts: "
                f"{output}"
            )
        receipt, _ = _load_json(
            build_root / VERIFICATION_FILENAME, "verification receipt"
        )
        actual_artifacts = {
            entry["sourceId"]: entry["artifactId"]
            for entry in cast(list[JsonObject], receipt["materializations"])
        }
        expected_artifacts = {
            source_id: item.artifact_id for source_id, item in requests.items()
        }
        if actual_artifacts != expected_artifacts:
            raise ResolveImportPackageError(
                "project root already exists for different materialization artifacts: "
                f"{output}"
            )
        return _result(output, verification, True)

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
        )
    except OSError as error:
        raise ResolveImportPackageError(
            f"could not create staging directory: {error}"
        ) from error
    try:
        _write_package(
            staging,
            manifest,
            manifest_bytes,
            report,
            report_bytes,
            requests,
            ffprobe_executable,
            publication_time,
        )
        verification = verify_resolve_import_package(
            staging, ffprobe_executable=ffprobe_executable
        )
        if output.exists():
            raise ResolveImportPackageError(
                f"project root appeared during publication: {output}"
            )
        os.replace(staging, output)
    except ResolveImportPackageError:
        raise
    except Exception as error:
        raise ResolveImportPackageError(
            f"could not build Resolve import package: {error}"
        ) from error
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return _result(output, verification, False)


def _verify_inventory(project_root: Path, manifest: JsonObject) -> None:
    build_id = cast(str, manifest["buildId"])
    expected = {
        f"Builds/{build_id}/{MANIFEST_FILENAME}",
        f"Builds/{build_id}/{REPORT_FILENAME}",
        f"Builds/{build_id}/{OTIO_FILENAME}",
        f"Builds/{build_id}/{INSTRUCTIONS_FILENAME}",
        f"Builds/{build_id}/{VERIFICATION_FILENAME}",
    }
    for source in cast(list[JsonObject], manifest["sources"]):
        if source["kind"] == "placeholder":
            expected.add(f"Media/Placeholders/{source['id']}.png")
        else:
            expected.add(_safe_manifest_destination(source).as_posix())
    entries = list(project_root.rglob("*"))
    actual: set[str] = set()
    for path in entries:
        relative = path.relative_to(project_root).as_posix()
        details = path.lstat()
        if stat.S_ISLNK(details.st_mode):
            raise ResolveImportPackageError(
                f"package contains a symbolic link: {relative}"
            )
        if stat.S_ISREG(details.st_mode):
            if details.st_nlink != 1:
                raise ResolveImportPackageError(
                    f"package contains a hard-linked file: {relative}"
                )
            actual.add(relative)
        elif not stat.S_ISDIR(details.st_mode):
            raise ResolveImportPackageError(
                f"package contains unsupported entry: {relative}"
            )
    if actual != expected:
        raise ResolveImportPackageError(
            f"package inventory differs; missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )


def _verify_otio(project_root: Path, manifest: JsonObject) -> None:
    build_root = project_root / "Builds" / cast(str, manifest["buildId"])
    try:
        timeline = otio.adapters.read_from_file(str(build_root / OTIO_FILENAME))
    except (OSError, RuntimeError, ValueError) as error:
        raise ResolveImportPackageError(f"OTIO could not be parsed: {error}") from error
    if not isinstance(timeline, otio.schema.Timeline):
        raise ResolveImportPackageError("OTIO root is not a Timeline")
    settings = cast(JsonObject, manifest["timeline"])
    timeline_rate = _rate(manifest)
    start = cast(int, settings["startFrame"])
    if (
        timeline.global_start_time is None
        or timeline.global_start_time.rescaled_to(timeline_rate).to_frames() != start
        or _plain_metadata(timeline.metadata.get("vera", {}).get("timeline_settings"))
        != settings
        or timeline.metadata.get("vera", {}).get("manifest_id") != manifest["id"]
        or timeline.metadata.get("vera", {}).get("build_id") != manifest["buildId"]
    ):
        raise ResolveImportPackageError(
            "OTIO timeline identity, rate, or settings differ"
        )
    expected_tracks = cast(list[JsonObject], manifest["tracks"])
    if len(timeline.tracks) != len(expected_tracks):
        raise ResolveImportPackageError("OTIO track count differs")
    actual_events: dict[str, JsonObject] = {}
    for track, expected_track in zip(timeline.tracks, expected_tracks, strict=True):
        metadata = track.metadata.get("vera", {})
        if (
            track.name != expected_track["name"]
            or track.kind != _track_kind(cast(str, expected_track["kind"]))
            or metadata.get("track_id") != expected_track["id"]
            or metadata.get("track_kind") != expected_track["kind"]
            or metadata.get("track_index") != expected_track["index"]
            or track.duration().rescaled_to(timeline_rate).to_frames()
            != settings["durationFrames"]
        ):
            raise ResolveImportPackageError(
                f"OTIO track differs: {expected_track['id']}"
            )
        cursor = start
        for child in track:
            duration = child.duration().rescaled_to(timeline_rate).to_frames()
            if isinstance(child, otio.schema.Clip):
                event_id = child.metadata.get("vera", {}).get("event_id")
                if not isinstance(event_id, str) or event_id in actual_events:
                    raise ResolveImportPackageError(
                        "OTIO has missing or duplicate event identity"
                    )
                reference = child.media_reference
                if (
                    not isinstance(reference, otio.schema.ExternalReference)
                    or child.source_range is None
                ):
                    raise ResolveImportPackageError(
                        f"OTIO event {event_id} has no external media range"
                    )
                actual_events[event_id] = {
                    "trackId": metadata.get("track_id"),
                    "recordRange": {"startFrame": cursor, "durationFrames": duration},
                    "sourceRange": {
                        "startFrame": child.source_range.start_time.to_frames(),
                        "durationFrames": child.source_range.duration.to_frames(),
                    },
                    "mediaPath": reference.target_url,
                    "metadata": _plain_metadata(child.metadata.get("vera", {})),
                    "referenceMetadata": _plain_metadata(
                        reference.metadata.get("vera", {})
                    ),
                }
            elif not isinstance(child, otio.schema.Gap):
                raise ResolveImportPackageError(
                    "OTIO contains a transition or unsupported item"
                )
            cursor += duration

    sources = _unique_by_id(cast(list[JsonObject], manifest["sources"]), "source")
    expected_events = _unique_by_id(cast(list[JsonObject], manifest["events"]), "event")
    if set(actual_events) != set(expected_events):
        raise ResolveImportPackageError("OTIO event inventory differs")
    for event_id, event in expected_events.items():
        source = sources[event["sourceId"]]
        duration = event["recordRange"]["durationFrames"]
        source_range = event.get(
            "sourceRange", {"startFrame": 0, "durationFrames": duration}
        )
        expected_metadata = {
            "event_id": event["id"],
            "event_kind": event["kind"],
            "source_id": event["sourceId"],
            "source_kind": source["kind"],
            "track_id": event["trackId"],
            "record_range": event["recordRange"],
            "timing_precision": event["timingPrecision"],
            "alignment_version": event["alignmentVersion"],
            "provenance": event["provenance"],
            **(
                {"placeholder": {"label": source["label"], "reason": source["reason"]}}
                if source["kind"] == "placeholder"
                else {}
            ),
        }
        expected_reference = {
            "source_id": source["id"],
            "source_kind": source["kind"],
            **(
                {"label": source["label"], "reason": source["reason"]}
                if source["kind"] == "placeholder"
                else {"content_hash": source["contentHash"]}
            ),
        }
        actual = actual_events[event_id]
        if actual != {
            "trackId": event["trackId"],
            "recordRange": event["recordRange"],
            "sourceRange": source_range,
            "mediaPath": _media_locator(source),
            "metadata": expected_metadata,
            "referenceMetadata": expected_reference,
        }:
            raise ResolveImportPackageError(
                f"OTIO event differs from manifest: {event_id}"
            )
        relative_media = PurePosixPath(cast(str, actual["mediaPath"]))
        if relative_media.parts[:2] != ("..", "..") or ".." in relative_media.parts[2:]:
            raise ResolveImportPackageError(
                f"OTIO event {event_id} has unsafe media reference"
            )

    if (
        _plain_metadata(timeline.tracks.metadata.get("vera", {}).get("hard_cuts"))
        != manifest["transitions"]
    ):
        raise ResolveImportPackageError("OTIO hard cuts differ from manifest")
    actual_markers = list(timeline.tracks.markers)
    markers = cast(list[JsonObject], manifest["markers"])
    if len(actual_markers) != len(markers):
        raise ResolveImportPackageError("OTIO marker count differs")
    for actual, expected in zip(actual_markers, markers, strict=True):
        expected_metadata = {
            "marker_id": expected["id"],
            "note": expected["note"],
            "original_color": expected["color"],
            "provenance": expected["provenance"],
        }
        if (
            actual.name != expected["name"]
            or actual.marked_range.start_time.rescaled_to(timeline_rate).to_frames()
            != expected["frame"] - start
            or actual.marked_range.duration.rescaled_to(timeline_rate).to_frames() != 0
            or actual.color != _marker_color(cast(str, expected["color"]))
            or _plain_metadata(actual.metadata.get("vera", {})) != expected_metadata
        ):
            raise ResolveImportPackageError(f"OTIO marker differs: {expected['id']}")


def verify_resolve_import_package(
    project_root: Path | str,
    *,
    ffprobe_executable: str = "ffprobe",
) -> ResolveImportVerification:
    """Verify exact inventory, bytes, media facts, receipt, and parsed OTIO."""
    root = Path(project_root)
    if not root.is_dir() or root.is_symlink():
        raise ResolveImportPackageError(
            f"project root is not a regular directory: {root}"
        )
    builds = root / "Builds"
    try:
        build_directories = [
            path for path in builds.iterdir() if path.is_dir() and not path.is_symlink()
        ]
    except OSError as error:
        raise ResolveImportPackageError(
            f"could not inspect Builds directory: {error}"
        ) from error
    if len(build_directories) != 1:
        raise ResolveImportPackageError(
            "project must contain exactly one build directory"
        )
    build_root = build_directories[0]
    manifest, manifest_bytes = _load_json(
        build_root / MANIFEST_FILENAME, "packaged timeline manifest"
    )
    report, report_bytes = _load_json(
        build_root / REPORT_FILENAME, "packaged build report"
    )
    receipt, receipt_bytes = _load_json(
        build_root / VERIFICATION_FILENAME, "verification receipt"
    )
    _require_canonical(manifest, manifest_bytes, "packaged timeline manifest")
    _require_canonical(report, report_bytes, "packaged build report")
    _require_canonical(receipt, receipt_bytes, "verification receipt")
    _validate_contracts(manifest, report)
    _validate_report_linkage(manifest, report, manifest_bytes)
    _validate_manifest_semantics(manifest)
    if build_root.name != manifest["buildId"]:
        raise ResolveImportPackageError(
            "build directory name differs from manifest build ID"
        )
    _verify_inventory(root, manifest)

    materialization_by_source: dict[str, JsonObject] = {}
    for entry in cast(list[JsonObject], receipt.get("materializations", [])):
        source_id = cast(str, entry.get("sourceId"))
        if source_id in materialization_by_source:
            raise ResolveImportPackageError(
                f"duplicate receipt materialization {source_id}"
            )
        materialization_by_source[source_id] = entry
    placeholder_by_source: dict[str, JsonObject] = {}
    for entry in cast(list[JsonObject], receipt.get("placeholderSlates", [])):
        source_id = cast(str, entry.get("sourceId"))
        if source_id in placeholder_by_source:
            raise ResolveImportPackageError(
                f"duplicate receipt placeholder {source_id}"
            )
        placeholder_by_source[source_id] = entry

    materializations: list[JsonObject] = []
    placeholders: list[JsonObject] = []
    for source in cast(list[JsonObject], manifest["sources"]):
        source_id = cast(str, source["id"])
        if source["kind"] == "placeholder":
            relative = PurePosixPath("Media") / "Placeholders" / f"{source_id}.png"
            path = root.joinpath(*relative.parts)
            _verify_probe(
                {
                    "id": source_id,
                    "kind": "still",
                    "width": manifest["timeline"]["width"],
                    "height": manifest["timeline"]["height"],
                },
                path,
                ffprobe_executable,
            )
            expected = {
                "sourceId": source_id,
                "path": relative.as_posix(),
                "contentHash": f"{_HASH_PREFIX}{_sha256_file(path)}",
                "label": source["label"],
                "reason": source["reason"],
                "width": manifest["timeline"]["width"],
                "height": manifest["timeline"]["height"],
            }
            if placeholder_by_source.get(source_id) != expected:
                raise ResolveImportPackageError(
                    f"receipt placeholder differs: {source_id}"
                )
            placeholders.append(expected)
            continue
        relative = _safe_manifest_destination(source)
        path = root.joinpath(*relative.parts)
        actual_hash = _sha256_file(path)
        if actual_hash != _hash_value(
            cast(str, source["contentHash"]), f"source {source_id} hash"
        ):
            raise ResolveImportPackageError(
                f"packaged media hash mismatch: {source_id}"
            )
        timeline_rate_data = cast(JsonObject, manifest["timeline"]["frameRate"])
        facts = _verify_probe(
            source,
            path,
            ffprobe_executable,
            Fraction(
                timeline_rate_data["numerator"], timeline_rate_data["denominator"]
            ),
        )
        recorded = materialization_by_source.get(source_id)
        if (
            recorded is None
            or set(recorded)
            != {"sourceId", "artifactId", "mode", "path", "contentHash", "mediaFacts"}
            or not isinstance(recorded.get("artifactId"), str)
            or not recorded["artifactId"]
            or recorded.get("mode") not in {"clone", "copy"}
            or recorded.get("path") != relative.as_posix()
            or recorded.get("contentHash") != source["contentHash"]
            or recorded.get("mediaFacts") != facts
        ):
            raise ResolveImportPackageError(
                f"receipt materialization differs: {source_id}"
            )
        materializations.append(recorded)

    verified_at = _validate_verified_at(receipt.get("verifiedAt"))
    otio_bytes = (build_root / OTIO_FILENAME).read_bytes()
    instructions_bytes = (build_root / INSTRUCTIONS_FILENAME).read_bytes()
    expected_receipt = _receipt(
        manifest,
        manifest_bytes,
        report,
        report_bytes,
        materializations,
        placeholders,
        verified_at,
        otio_bytes,
        instructions_bytes,
    )
    if receipt != expected_receipt:
        raise ResolveImportPackageError("verification receipt is inconsistent")
    _verify_otio(root, manifest)
    if instructions_bytes != _instructions(manifest, report).encode("utf-8"):
        raise ResolveImportPackageError("import instructions are inconsistent")
    return ResolveImportVerification(
        build_id=cast(str, manifest["buildId"]),
        event_count=len(manifest["events"]),
        marker_count=len(manifest["markers"]),
        media_count=len(manifest["sources"]),
    )
