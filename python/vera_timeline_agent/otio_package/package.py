"""TimelineManifest v1 to deterministic, self-contained OTIO package support."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path, PurePosixPath
from typing import Any, cast

import jsonschema  # type: ignore[import-untyped]
import opentimelineio as otio  # type: ignore[import-untyped]
from referencing import Registry, Resource

MANIFEST_FILENAME = "timeline-manifest.json"
OTIO_FILENAME = "timeline.otio"
BUILD_REPORT_FILENAME = "build-report.json"
IMPORT_INSTRUCTIONS_FILENAME = "IMPORT_INSTRUCTIONS.md"

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_CONTRACTS_DIRECTORY = _REPOSITORY_ROOT / "contracts"
_SCHEMA_FILES = (
    "script-document-v1.schema.json",
    "timeline-manifest-v1.schema.json",
    "build-report-v1.schema.json",
)
_TIMELINE_SCHEMA_ID = (
    "https://schemas.vera.video/contracts/timeline-manifest-v1.schema.json"
)
_REPORT_SCHEMA_ID = "https://schemas.vera.video/contracts/build-report-v1.schema.json"
_HASH_PREFIX = "sha256:"

JsonObject = dict[str, Any]


class PackageBuildError(RuntimeError):
    """An actionable failure that prevents publishing a verified package."""


@dataclass(frozen=True)
class PackageResult:
    """Published package paths and verified acceptance counts."""

    output_dir: Path
    manifest_path: Path
    otio_path: Path
    report_path: Path
    instructions_path: Path
    event_count: int
    marker_count: int
    media_count: int


@dataclass(frozen=True)
class VerificationResult:
    """Counts proven by a package verification pass."""

    event_count: int
    marker_count: int
    media_count: int


def _load_json_object(path: Path, label: str) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise PackageBuildError(f"{label} does not exist: {path}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PackageBuildError(f"could not read {label} {path}: {error}") from error
    if not isinstance(value, dict):
        raise PackageBuildError(f"{label} must contain one JSON object: {path}")
    return cast(JsonObject, value)


def _schemas() -> tuple[dict[str, JsonObject], Registry[Any]]:
    schemas: dict[str, JsonObject] = {}
    resources: list[tuple[str, Resource[Any]]] = []
    for filename in _SCHEMA_FILES:
        path = _CONTRACTS_DIRECTORY / filename
        schema = _load_json_object(path, "contract schema")
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str):
            raise PackageBuildError(f"contract schema has no string $id: {path}")
        schemas[schema_id] = schema
        resources.append((schema_id, Resource.from_contents(schema)))
    return schemas, Registry().with_resources(resources)


def _validate_schema(value: object, schema_id: str, label: str) -> None:
    schemas, registry = _schemas()
    validator = jsonschema.Draft202012Validator(
        schemas[schema_id],
        registry=registry,
        format_checker=jsonschema.FormatChecker(),
    )
    errors = sorted(validator.iter_errors(value), key=lambda error: error.json_path)
    if errors:
        first = errors[0]
        raise PackageBuildError(
            f"{label} schema validation failed at {first.json_path}: {first.message}"
        )


def validate_timeline_manifest(value: object) -> None:
    """Validate a value against the accepted TimelineManifest v1 schema."""
    _validate_schema(value, _TIMELINE_SCHEMA_ID, "timeline manifest")


def validate_build_report(value: object) -> None:
    """Validate a value against the accepted BuildReport v1 schema."""
    _validate_schema(value, _REPORT_SCHEMA_ID, "build report")


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _frame_rate(manifest: Mapping[str, Any]) -> float:
    timeline = manifest["timeline"]
    rate = timeline["frameRate"]
    return cast(float, rate["numerator"] / rate["denominator"])


def _range_end(frame_range: Mapping[str, Any]) -> int:
    return cast(int, frame_range["startFrame"] + frame_range["durationFrames"])


def _validate_semantics(manifest: JsonObject, media_root: Path) -> None:
    tracks = cast(list[JsonObject], manifest["tracks"])
    sources = cast(list[JsonObject], manifest["sources"])
    events = cast(list[JsonObject], manifest["events"])
    transitions = cast(list[JsonObject], manifest["transitions"])
    markers = cast(list[JsonObject], manifest["markers"])

    track_by_id = _unique_by_id(tracks, "track")
    source_by_id = _unique_by_id(sources, "source")
    event_by_id = _unique_by_id(events, "event")
    track_slots: set[tuple[str, int]] = set()
    for track in tracks:
        slot = (track["kind"], track["index"])
        if slot in track_slots:
            raise PackageBuildError(
                f"duplicate {track['kind']} track index {track['index']}"
            )
        track_slots.add(slot)

    timeline = cast(JsonObject, manifest["timeline"])
    timeline_start = cast(int, timeline["startFrame"])
    timeline_end = timeline_start + cast(int, timeline["durationFrames"])
    events_by_track: defaultdict[str, list[JsonObject]] = defaultdict(list)
    for event in events:
        event_id = cast(str, event["id"])
        track_id = cast(str, event["trackId"])
        source_id = cast(str, event["sourceId"])
        target_track = track_by_id.get(track_id)
        source = source_by_id.get(source_id)
        if target_track is None:
            raise PackageBuildError(
                f"event {event_id} references unknown track {track_id}"
            )
        if source is None:
            raise PackageBuildError(
                f"event {event_id} references unknown source {source_id}"
            )
        if event["trackKind"] != target_track["kind"]:
            raise PackageBuildError(
                f"event {event_id} kind {event['trackKind']} does not match target "
                f"track kind {target_track['kind']}"
            )
        if event["kind"] != source["kind"]:
            raise PackageBuildError(
                f"event {event_id} kind {event['kind']} does not match source kind "
                f"{source['kind']}"
            )
        if event["kind"] == "placeholder":
            raise PackageBuildError(
                f"event {event_id} is a placeholder; Slice 0.2 only packages "
                "media events"
            )
        record_range = cast(JsonObject, event["recordRange"])
        if (
            record_range["startFrame"] < timeline_start
            or _range_end(record_range) > timeline_end
        ):
            raise PackageBuildError(
                f"event {event_id} record range falls outside the timeline range"
            )
        if event["kind"] in {"video", "audio"}:
            source_range = cast(JsonObject, event["sourceRange"])
            if _range_end(source_range) > source["durationFrames"]:
                raise PackageBuildError(
                    f"event {event_id} source range exceeds source duration"
                )
            if event["kind"] == "video" and not _durations_match_without_retime(
                source_range, record_range, source, timeline
            ):
                raise PackageBuildError(
                    f"event {event_id} requires a retime because source and "
                    "record durations differ"
                )
            if event["kind"] == "audio" and (
                source_range["durationFrames"] != record_range["durationFrames"]
            ):
                raise PackageBuildError(
                    f"event {event_id} requires an audio retime, which Slice 0.2 "
                    "does not support"
                )
        events_by_track[track_id].append(event)

    for track_id, track_events in events_by_track.items():
        ordered = sorted(
            track_events, key=lambda event: event["recordRange"]["startFrame"]
        )
        for previous, current in pairwise(ordered):
            if (
                _range_end(previous["recordRange"])
                > current["recordRange"]["startFrame"]
            ):
                raise PackageBuildError(
                    f"event {current['id']} overlaps {previous['id']} on track "
                    f"{track_id}"
                )

    for transition in transitions:
        transition_id = cast(str, transition["id"])
        from_event = event_by_id.get(transition["fromEventId"])
        to_event = event_by_id.get(transition["toEventId"])
        if from_event is None or to_event is None:
            raise PackageBuildError(
                f"hard cut {transition_id} references an unknown event"
            )
        at_frame = transition["atFrame"]
        if (
            from_event["trackId"] != to_event["trackId"]
            or _range_end(from_event["recordRange"]) != at_frame
            or to_event["recordRange"]["startFrame"] != at_frame
        ):
            raise PackageBuildError(
                f"hard cut {transition_id} is not an adjacent same-track boundary"
            )

    for marker in markers:
        if marker["state"] != "placed":
            raise PackageBuildError(
                f"marker {marker['id']} is unplaced and cannot be represented in OTIO"
            )
        if not timeline_start <= marker["frame"] <= timeline_end:
            raise PackageBuildError(f"marker {marker['id']} falls outside the timeline")

    _validate_media_sources(sources, media_root)


def _durations_match_without_retime(
    source_range: JsonObject,
    record_range: JsonObject,
    source: JsonObject,
    timeline: JsonObject,
) -> bool:
    source_rate = cast(JsonObject, source["frameRate"])
    timeline_rate = cast(JsonObject, timeline["frameRate"])
    source_side = (
        source_range["durationFrames"]
        * source_rate["denominator"]
        * timeline_rate["numerator"]
    )
    timeline_side = (
        record_range["durationFrames"]
        * timeline_rate["denominator"]
        * source_rate["numerator"]
    )
    return cast(bool, source_side == timeline_side)


def _unique_by_id(values: list[JsonObject], label: str) -> dict[str, JsonObject]:
    result: dict[str, JsonObject] = {}
    for value in values:
        identity = cast(str, value["id"])
        if identity in result:
            raise PackageBuildError(f"duplicate {label} id {identity}")
        result[identity] = value
    return result


def _safe_source_path(media_root: Path, project_path: str) -> Path:
    root = media_root.resolve()
    candidate = (root / PurePosixPath(project_path)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise PackageBuildError(
            f"media path escapes media root: {project_path}"
        ) from error
    return candidate


def _validate_media_sources(sources: list[JsonObject], media_root: Path) -> None:
    paths: set[str] = set()
    for source in sources:
        if source["kind"] == "placeholder":
            continue
        project_path = cast(str, source["path"])
        if project_path in paths:
            raise PackageBuildError(f"duplicate media destination path: {project_path}")
        paths.add(project_path)
        source_path = _safe_source_path(media_root, project_path)
        if not source_path.is_file():
            raise PackageBuildError(
                f"media source does not exist or is not a file: {source_path}"
            )
        actual_hash = _sha256_file(source_path)
        expected_hash = cast(str, source["contentHash"])[len(_HASH_PREFIX) :]
        if actual_hash != expected_hash:
            raise PackageBuildError(
                f"media hash mismatch for {project_path}: expected {expected_hash}, "
                f"found {actual_hash}"
            )


def _rational_time(frames: int, rate: float) -> Any:
    return otio.opentime.RationalTime(frames, rate)


def _time_range(start_frames: int, duration_frames: int, rate: float) -> Any:
    return otio.opentime.TimeRange(
        _rational_time(start_frames, rate),
        _rational_time(duration_frames, rate),
    )


def _otio_track_kind(kind: str) -> str:
    if kind == "video":
        return cast(str, otio.schema.Track.Kind.Video)
    if kind == "audio":
        return cast(str, otio.schema.Track.Kind.Audio)
    return kind


def _source_rate(source: Mapping[str, Any], timeline_rate: float) -> float:
    if source["kind"] != "video":
        return timeline_rate
    frame_rate = source["frameRate"]
    return cast(float, frame_rate["numerator"] / frame_rate["denominator"])


def _build_otio(manifest: JsonObject) -> Any:
    timeline_settings = cast(JsonObject, manifest["timeline"])
    start_frame = cast(int, timeline_settings["startFrame"])
    end_frame = start_frame + cast(int, timeline_settings["durationFrames"])
    timeline_rate = _frame_rate(manifest)
    timeline = otio.schema.Timeline(
        name=f"VERA build {manifest['buildId']}",
        global_start_time=_rational_time(start_frame, timeline_rate),
    )
    timeline.metadata["vera"] = {
        "schema_version": manifest["schemaVersion"],
        "manifest_id": manifest["id"],
        "build_id": manifest["buildId"],
        "timeline_settings": timeline_settings,
    }
    timeline.tracks.metadata["vera"] = {
        "hard_cuts": manifest["transitions"],
    }

    sources = _unique_by_id(cast(list[JsonObject], manifest["sources"]), "source")
    events_by_track: defaultdict[str, list[JsonObject]] = defaultdict(list)
    for event in cast(list[JsonObject], manifest["events"]):
        events_by_track[event["trackId"]].append(event)

    for track_data in cast(list[JsonObject], manifest["tracks"]):
        track = otio.schema.Track(
            name=track_data["name"],
            kind=_otio_track_kind(track_data["kind"]),
            metadata={
                "vera": {
                    "track_id": track_data["id"],
                    "track_kind": track_data["kind"],
                    "track_index": track_data["index"],
                }
            },
        )
        cursor = start_frame
        ordered_events = sorted(
            events_by_track[track_data["id"]],
            key=lambda event: event["recordRange"]["startFrame"],
        )
        for event in ordered_events:
            event_start = cast(int, event["recordRange"]["startFrame"])
            if event_start > cursor:
                track.append(
                    otio.schema.Gap(
                        source_range=_time_range(0, event_start - cursor, timeline_rate)
                    )
                )
            source = sources[event["sourceId"]]
            event_duration = cast(int, event["recordRange"]["durationFrames"])
            source_range = cast(
                JsonObject,
                event.get(
                    "sourceRange",
                    {"startFrame": 0, "durationFrames": event_duration},
                ),
            )
            source_rate = _source_rate(source, timeline_rate)
            available_duration = cast(
                int, source.get("durationFrames", source_range["durationFrames"])
            )
            media_reference = otio.schema.ExternalReference(
                target_url=source["path"],
                available_range=_time_range(0, available_duration, source_rate),
                metadata={
                    "vera": {
                        "source_id": source["id"],
                        "source_kind": source["kind"],
                        "content_hash": source["contentHash"],
                    }
                },
            )
            clip = otio.schema.Clip(
                name=f"{source['kind']}: {PurePosixPath(source['path']).name}",
                media_reference=media_reference,
                source_range=_time_range(
                    source_range["startFrame"],
                    source_range["durationFrames"],
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
                    }
                },
            )
            track.append(clip)
            cursor = event_start + event_duration
        if cursor < end_frame:
            track.append(
                otio.schema.Gap(
                    source_range=_time_range(0, end_frame - cursor, timeline_rate)
                )
            )
        timeline.tracks.append(track)

    for marker_data in cast(list[JsonObject], manifest["markers"]):
        marker_frame = cast(int, marker_data["frame"])
        timeline.tracks.markers.append(
            otio.schema.Marker(
                name=marker_data["name"],
                marked_range=_time_range(marker_frame - start_frame, 0, timeline_rate),
                color=_marker_color(cast(str, marker_data["color"])),
                metadata={
                    "vera": {
                        "marker_id": marker_data["id"],
                        "note": marker_data["note"],
                        "original_color": marker_data["color"],
                        "provenance": marker_data["provenance"],
                    }
                },
            )
        )
    return timeline


def _marker_color(color: str) -> str:
    normalized = color.upper()
    known = {
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
    return normalized if normalized in known else "RED"


def _build_report(manifest: JsonObject, manifest_hash: str) -> JsonObject:
    events = cast(list[JsonObject], manifest["events"])
    markers = cast(list[JsonObject], manifest["markers"])
    sources = cast(list[JsonObject], manifest["sources"])
    report_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"vera:build-report:{manifest['id']}")
    )
    narration_event = next(
        (event for event in events if event["kind"] == "audio"), None
    )
    if narration_event is None:
        raise PackageBuildError(
            "manifest has no audio event to use as Slice 0.2 synthetic narration"
        )
    issue_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"vera:temporary-narration:{manifest['id']}")
    )
    report: JsonObject = {
        "schemaVersion": "build-report/v1",
        "id": report_id,
        "buildId": manifest["buildId"],
        "buildClass": "preview",
        "status": "ready_with_warnings",
        "temporaryNarration": True,
        "sourceDocument": manifest["sourceDocument"],
        "manifest": {
            "id": manifest["id"],
            "contentHash": f"{_HASH_PREFIX}{manifest_hash}",
        },
        "timeline": manifest["timeline"],
        "summary": {
            "sourceCount": len(sources),
            "eventCount": len(events),
            "markerCount": len(markers),
            "placedCount": len(events),
            "placeholderCount": 0,
            "manualCompletionCount": 0,
            "warningCount": 1,
            "errorCount": 0,
        },
        "eventResults": [
            {
                "eventId": event["id"],
                "disposition": "placed",
                "sourceId": event["sourceId"],
                "trackId": event["trackId"],
                "trackKind": event["trackKind"],
                "recordRange": event["recordRange"],
                "message": (
                    "Placed synthetic test narration from the canonical manifest."
                    if event["kind"] == "audio"
                    else "Placed media from the canonical manifest."
                ),
            }
            for event in events
        ],
        "issues": [
            {
                "id": issue_id,
                "severity": "warning",
                "code": "TEMPORARY_NARRATION",
                "message": (
                    "The narration placement uses the frozen synthetic ambient WAV "
                    "as test narration; it is not generated speech."
                ),
                "entity": {
                    "kind": "block",
                    "id": narration_event["provenance"]["blockId"],
                },
            }
        ],
        "manualCompletionItems": [],
    }
    validate_build_report(report)
    return report


def _instructions(manifest: JsonObject) -> str:
    events = cast(list[JsonObject], manifest["events"])
    tracks = _unique_by_id(cast(list[JsonObject], manifest["tracks"]), "track")
    markers = cast(list[JsonObject], manifest["markers"])
    video_count = sum(event["kind"] == "video" for event in events)
    still_count = sum(event["kind"] == "still" for event in events)
    audio_count = sum(event["kind"] == "audio" for event in events)
    picture_tracks = _used_track_names(events, tracks, {"video", "still"})
    audio_tracks = _used_track_names(events, tracks, {"audio"})
    marker_description = ", ".join(
        f"{marker['color']} **{marker['name']}**" for marker in markers
    )
    picture_expectation = (
        f"{video_count} trimmed video {_plural(video_count, 'clip')} and "
        f"{still_count} {_plural(still_count, 'still')}"
    )
    audio_expectation = (
        f"{audio_count} synthetic test narration {_plural(audio_count, 'placement')}"
    )
    return f"""# VERA OTIO import package

This folder is a self-contained Slice 0.2 interoperability package for build:

`{manifest["buildId"]}`

Keep the folder intact so the project-relative media links in `{OTIO_FILENAME}`
continue to point into `media/`.

The audio on {audio_tracks} is **synthetic test narration**: the frozen
procedural ambient fixture is standing in for generated narration only to
exercise audio placement. It is not speech and is not evidence for a voice
provider.

## Inspect before import

1. Open `{MANIFEST_FILENAME}` to inspect the canonical {len(events)} events and
   configurable track map.
2. Open `{BUILD_REPORT_FILENAME}` and confirm every event is listed as placed,
   the marker count is one, and `TEMPORARY_NARRATION` is the only warning.
3. Do not move individual files out of this folder before import.

## Import in DaVinci Resolve

1. Open the target project and choose **File → Import → Timeline…**.
2. Select `{OTIO_FILENAME}` from this folder and use Resolve's OpenTimelineIO
   import option when prompted.
3. If Resolve asks for media, point it at this package's `media/` directory;
   do not substitute similarly named files.
4. Inspect the placed events:
   - Picture track(s): {picture_tracks}.
     Expected: {picture_expectation}.
   - Audio track(s): {audio_tracks}.
     Expected: {audio_expectation}.
   - Marker(s): {marker_description}.
5. Confirm there are hard cuts and no dissolves or other transitions.
6. Keep this package unchanged as the evidence input for the Slice 0.3 import
   trial.

Automated package verification proves OTIO parseability and agreement with the
manifest; it does **not** claim DaVinci Resolve import fidelity. Exact Resolve
behavior is observed and recorded by the producer in Slice 0.3.
"""


def _used_track_names(
    events: list[JsonObject],
    tracks: dict[str, JsonObject],
    event_kinds: set[str],
) -> str:
    names: list[str] = []
    for event in events:
        if event["kind"] not in event_kinds:
            continue
        name = cast(str, tracks[event["trackId"]]["name"])
        if name not in names:
            names.append(name)
    return ", ".join(f"`{name}`" for name in names) or "no matching track"


def _plural(count: int, singular: str) -> str:
    return singular if count == 1 else f"{singular}s"


def _copy_media(manifest: JsonObject, media_root: Path, package_root: Path) -> None:
    for source in cast(list[JsonObject], manifest["sources"]):
        if source["kind"] == "placeholder":
            continue
        project_path = cast(str, source["path"])
        source_path = _safe_source_path(media_root, project_path)
        destination = package_root / PurePosixPath(project_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination)
        actual_hash = _sha256_file(destination)
        expected_hash = cast(str, source["contentHash"])[len(_HASH_PREFIX) :]
        if actual_hash != expected_hash:
            raise PackageBuildError(
                f"copied media hash mismatch for {project_path}: expected "
                f"{expected_hash}, found {actual_hash}"
            )


def build_otio_package(
    manifest_path: Path | str,
    media_root: Path | str,
    output_dir: Path | str,
) -> PackageResult:
    """Build, verify, and atomically publish one new OTIO package directory."""
    input_path = Path(manifest_path)
    source_root = Path(media_root)
    output = Path(output_dir)
    manifest = _load_json_object(input_path, "timeline manifest")
    validate_timeline_manifest(manifest)
    _validate_semantics(manifest, source_root)
    if output.exists():
        try:
            verification = verify_otio_package(output)
        except PackageBuildError as error:
            raise PackageBuildError(
                f"output path already exists and is not the same verified package: "
                f"{output}"
            ) from error
        if (output / MANIFEST_FILENAME).read_bytes() != _canonical_json_bytes(manifest):
            raise PackageBuildError(
                f"output path already exists for a different manifest: {output}"
            )
        return _package_result(output, verification)

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
        )
    except OSError as error:
        raise PackageBuildError(
            f"could not create output staging directory for {output}: {error}"
        ) from error

    try:
        manifest_bytes = _canonical_json_bytes(manifest)
        (staging / MANIFEST_FILENAME).write_bytes(manifest_bytes)
        _copy_media(manifest, source_root, staging)

        timeline = _build_otio(manifest)
        otio.adapters.write_to_file(
            timeline,
            str(staging / OTIO_FILENAME),
            adapter_name="otio_json",
        )
        report = _build_report(manifest, _sha256_bytes(manifest_bytes))
        (staging / BUILD_REPORT_FILENAME).write_bytes(_canonical_json_bytes(report))
        (staging / IMPORT_INSTRUCTIONS_FILENAME).write_text(
            _instructions(manifest), encoding="utf-8"
        )

        verification = verify_otio_package(staging)
        if output.exists():
            raise PackageBuildError(
                f"output path appeared during build and will not be replaced: {output}"
            )
        os.replace(staging, output)
    except PackageBuildError:
        raise
    except Exception as error:
        raise PackageBuildError(f"could not build OTIO package: {error}") from error
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

    return _package_result(output, verification)


def _package_result(output: Path, verification: VerificationResult) -> PackageResult:
    return PackageResult(
        output_dir=output,
        manifest_path=output / MANIFEST_FILENAME,
        otio_path=output / OTIO_FILENAME,
        report_path=output / BUILD_REPORT_FILENAME,
        instructions_path=output / IMPORT_INSTRUCTIONS_FILENAME,
        event_count=verification.event_count,
        marker_count=verification.marker_count,
        media_count=verification.media_count,
    )


def _verification_error(message: str) -> PackageBuildError:
    return PackageBuildError(f"package verification failed: {message}")


def _verify_structure(package_root: Path, manifest: JsonObject) -> list[JsonObject]:
    sources = cast(list[JsonObject], manifest["sources"])
    media_sources = [source for source in sources if source["kind"] != "placeholder"]
    expected = {
        MANIFEST_FILENAME,
        OTIO_FILENAME,
        BUILD_REPORT_FILENAME,
        IMPORT_INSTRUCTIONS_FILENAME,
        *(cast(str, source["path"]) for source in media_sources),
    }
    actual = {
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise _verification_error(
            f"file inventory differs; missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )
    if len(list(package_root.glob("*.otio"))) != 1:
        raise _verification_error("package must contain exactly one root .otio file")
    return media_sources


def _verify_media(package_root: Path, sources: list[JsonObject]) -> None:
    for source in sources:
        project_path = cast(str, source["path"])
        path = package_root / PurePosixPath(project_path)
        actual = _sha256_file(path)
        expected = cast(str, source["contentHash"])[len(_HASH_PREFIX) :]
        if actual != expected:
            raise _verification_error(
                f"media hash mismatch for {project_path}: expected {expected}, "
                f"found {actual}"
            )


def _child_duration_frames(child: Any, timeline_rate: float) -> int:
    return cast(int, child.duration().rescaled_to(timeline_rate).to_frames())


def _plain_otio_metadata(value: Any) -> Any:
    if hasattr(value, "items"):
        return {key: _plain_otio_metadata(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)) or type(value).__name__ == "AnyVector":
        return [_plain_otio_metadata(item) for item in value]
    return value


def _verify_otio(package_root: Path, manifest: JsonObject) -> None:
    try:
        timeline = otio.adapters.read_from_file(str(package_root / OTIO_FILENAME))
    except (OSError, RuntimeError, ValueError) as error:
        raise _verification_error(f"OTIO could not be parsed: {error}") from error
    if not isinstance(timeline, otio.schema.Timeline):
        raise _verification_error("OTIO root is not a Timeline")

    settings = cast(JsonObject, manifest["timeline"])
    timeline_rate = _frame_rate(manifest)
    start_frame = cast(int, settings["startFrame"])
    if timeline.global_start_time is None:
        raise _verification_error("OTIO has no global start time")
    if timeline.global_start_time.rescaled_to(timeline_rate).to_frames() != start_frame:
        raise _verification_error("OTIO global start frame differs from manifest")
    vera_timeline = timeline.metadata.get("vera", {})
    if (
        vera_timeline.get("manifest_id") != manifest["id"]
        or vera_timeline.get("build_id") != manifest["buildId"]
        or vera_timeline.get("timeline_settings") != settings
    ):
        raise _verification_error("OTIO timeline metadata differs from manifest")

    expected_tracks = cast(list[JsonObject], manifest["tracks"])
    if len(timeline.tracks) != len(expected_tracks):
        raise _verification_error("OTIO track count differs from manifest")
    actual_events: dict[str, JsonObject] = {}
    for actual_track, expected_track in zip(
        timeline.tracks, expected_tracks, strict=True
    ):
        track_metadata = actual_track.metadata.get("vera", {})
        if (
            actual_track.name != expected_track["name"]
            or actual_track.kind != _otio_track_kind(expected_track["kind"])
            or track_metadata.get("track_id") != expected_track["id"]
            or track_metadata.get("track_kind") != expected_track["kind"]
            or track_metadata.get("track_index") != expected_track["index"]
        ):
            raise _verification_error(
                f"OTIO track differs from manifest track {expected_track['id']}"
            )
        cursor = start_frame
        for child in actual_track:
            duration = _child_duration_frames(child, timeline_rate)
            if isinstance(child, otio.schema.Gap):
                cursor += duration
                continue
            if not isinstance(child, otio.schema.Clip):
                raise _verification_error(
                    f"unexpected OTIO child type {type(child).__name__}"
                )
            event_metadata = child.metadata.get("vera", {})
            event_id = event_metadata.get("event_id")
            if not isinstance(event_id, str) or event_id in actual_events:
                raise _verification_error("OTIO event ID is missing or duplicated")
            media_reference = child.media_reference
            if not isinstance(media_reference, otio.schema.ExternalReference):
                raise _verification_error(
                    f"event {event_id} has no external media reference"
                )
            if child.source_range is None:
                raise _verification_error(f"event {event_id} has no source range")
            actual_events[event_id] = {
                "trackId": track_metadata.get("track_id"),
                "recordRange": {
                    "startFrame": cursor,
                    "durationFrames": duration,
                },
                "sourceRange": {
                    "startFrame": child.source_range.start_time.to_frames(),
                    "durationFrames": child.source_range.duration.to_frames(),
                },
                "mediaPath": media_reference.target_url,
                "eventKind": event_metadata.get("event_kind"),
                "sourceId": event_metadata.get("source_id"),
                "sourceKind": event_metadata.get("source_kind"),
            }
            cursor += duration
        expected_end = start_frame + cast(int, settings["durationFrames"])
        if cursor != expected_end:
            raise _verification_error(
                f"OTIO track duration differs from manifest: {expected_track['id']}"
            )

    source_by_id = _unique_by_id(cast(list[JsonObject], manifest["sources"]), "source")
    expected_events = cast(list[JsonObject], manifest["events"])
    if set(actual_events) != {cast(str, event["id"]) for event in expected_events}:
        raise _verification_error("OTIO event IDs differ from manifest")
    for event in expected_events:
        source = source_by_id[event["sourceId"]]
        source_range = cast(
            JsonObject,
            event.get(
                "sourceRange",
                {
                    "startFrame": 0,
                    "durationFrames": event["recordRange"]["durationFrames"],
                },
            ),
        )
        expected = {
            "trackId": event["trackId"],
            "recordRange": event["recordRange"],
            "sourceRange": source_range,
            "mediaPath": source["path"],
            "eventKind": event["kind"],
            "sourceId": event["sourceId"],
            "sourceKind": source["kind"],
        }
        if actual_events[event["id"]] != expected:
            raise _verification_error(
                f"OTIO event differs from manifest: {event['id']}"
            )

    transitions = list(
        timeline.tracks.find_children(descended_from_type=otio.schema.Transition)
    )
    if transitions:
        raise _verification_error("OTIO contains unintended transition objects")
    actual_hard_cuts = _plain_otio_metadata(
        timeline.tracks.metadata.get("vera", {}).get("hard_cuts")
    )
    if actual_hard_cuts != manifest["transitions"]:
        raise _verification_error("OTIO hard-cut metadata differs from manifest")

    _verify_markers(timeline, manifest, timeline_rate, start_frame)


def _verify_markers(
    timeline: Any,
    manifest: JsonObject,
    timeline_rate: float,
    start_frame: int,
) -> None:
    expected_markers = cast(list[JsonObject], manifest["markers"])
    if len(timeline.tracks.markers) != len(expected_markers):
        raise _verification_error("OTIO marker count differs from manifest")
    for actual, expected in zip(timeline.tracks.markers, expected_markers, strict=True):
        vera = actual.metadata.get("vera", {})
        actual_frame = (
            actual.marked_range.start_time.rescaled_to(timeline_rate).to_frames()
            + start_frame
        )
        if (
            actual.name != expected["name"]
            or actual_frame != expected["frame"]
            or actual.marked_range.duration.to_frames() != 0
            or actual.color != _marker_color(expected["color"])
            or vera.get("marker_id") != expected["id"]
            or vera.get("note") != expected["note"]
            or vera.get("original_color") != expected["color"]
            or _plain_otio_metadata(vera.get("provenance")) != expected["provenance"]
        ):
            raise _verification_error(
                f"OTIO marker differs from manifest: {expected['id']}"
            )


def _verify_report(package_root: Path, manifest: JsonObject) -> None:
    report_path = package_root / BUILD_REPORT_FILENAME
    report = _load_json_object(report_path, "build report")
    validate_build_report(report)
    manifest_hash = f"{_HASH_PREFIX}{_sha256_file(package_root / MANIFEST_FILENAME)}"
    expected = _build_report(manifest, manifest_hash[len(_HASH_PREFIX) :])
    if report != expected:
        raise _verification_error("build report is incomplete or differs from manifest")


def verify_otio_package(package_dir: Path | str) -> VerificationResult:
    """Verify package structure, hashes, report, and OTIO against its manifest."""
    package_root = Path(package_dir)
    if not package_root.is_dir():
        raise PackageBuildError(f"package directory does not exist: {package_root}")
    manifest_path = package_root / MANIFEST_FILENAME
    manifest = _load_json_object(manifest_path, "canonical timeline manifest")
    validate_timeline_manifest(manifest)
    if manifest_path.read_bytes() != _canonical_json_bytes(manifest):
        raise _verification_error("canonical manifest serialization differs")
    instructions_path = package_root / IMPORT_INSTRUCTIONS_FILENAME
    if instructions_path.is_file() and instructions_path.read_text(
        encoding="utf-8"
    ) != (_instructions(manifest)):
        raise _verification_error("import instructions differ from the manifest")
    media_sources = _verify_structure(package_root, manifest)
    _verify_media(package_root, media_sources)
    _verify_otio(package_root, manifest)
    _verify_report(package_root, manifest)
    return VerificationResult(
        event_count=len(cast(list[object], manifest["events"])),
        marker_count=len(cast(list[object], manifest["markers"])),
        media_count=len(media_sources),
    )
