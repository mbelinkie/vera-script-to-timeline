"""Verified Resolve Free packaging for one explicitly declared EV24 bake."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
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

from .package import (
    INSTRUCTIONS_FILENAME,
    MANIFEST_FILENAME,
    OTIO_FILENAME,
    REPORT_FILENAME,
    VERIFICATION_FILENAME,
    ResolveImportPackageError,
    _canonical_json,
    _marker_color,
    _rate,
    _safe_existing_regular,
    _safe_manifest_destination,
    _sha256_file,
    _time_range,
    _track_kind,
    _unique_by_id,
    _validate_verified_at,
    _verify_probe,
)

_SCHEMA = "resolve-free-baked-graphic-candidate/v1"
_HASH_PREFIX = "sha256:"

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class BakedGraphicPackageResult:
    """The only published root for one verified baked-candidate package."""

    project_root: Path
    build_root: Path
    verification_path: Path
    otio_path: Path
    reused: bool


@dataclass(frozen=True)
class _Bake:
    event: JsonObject
    source: JsonObject
    origin: Path
    artifact_id: str
    renderer: JsonObject
    manual_item_id: str
    expected: JsonObject


def _load(path: Path, label: str) -> tuple[JsonObject, bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ResolveImportPackageError(f"could not read {label}: {error}") from error
    if not isinstance(value, dict):
        raise ResolveImportPackageError(f"{label} must be an object")
    if raw != _canonical_json(value):
        raise ResolveImportPackageError(f"{label} is not canonical JSON")
    return cast(JsonObject, value), raw


def _hash(value: str, label: str) -> str:
    if not value.startswith(_HASH_PREFIX) or len(value) != 71:
        raise ResolveImportPackageError(f"{label} is not a sha256 content hash")
    return value[len(_HASH_PREFIX) :]


def _validate_contracts(manifest: JsonObject, report: JsonObject) -> None:
    try:
        validate_timeline_manifest(manifest)
        validate_build_report(report)
    except ContractValidationError as error:
        raise ResolveImportPackageError(str(error)) from error


def _events(
    manifest: JsonObject, report: JsonObject
) -> tuple[dict[str, JsonObject], dict[str, JsonObject], dict[str, JsonObject]]:
    sources = _unique_by_id(cast(list[JsonObject], manifest["sources"]), "source")
    events = _unique_by_id(cast(list[JsonObject], manifest["events"]), "event")
    results: dict[str, JsonObject] = {}
    for result in cast(list[JsonObject], report["eventResults"]):
        event_id = result.get("eventId")
        if not isinstance(event_id, str) or event_id in results:
            raise ResolveImportPackageError(
                "build report has duplicate or invalid event result"
            )
        results[event_id] = result
    if set(events) != set(results):
        raise ResolveImportPackageError("build report event results are incomplete")
    for event_id, event in events.items():
        source = sources.get(cast(str, event["sourceId"]))
        result = results[event_id]
        if source is None or any(
            result.get(key) != event[key]
            for key in ("sourceId", "trackId", "trackKind", "recordRange")
        ):
            raise ResolveImportPackageError(
                f"report differs from manifest event {event_id}"
            )
        if event["kind"] == "fusion_graphic":
            if (
                source["kind"] != "fusion_template"
                or result.get("graphicMaterialization") != "placeholder"
                or result.get("disposition") != "placeholder"
                or result.get("manualCompletionRequired") is not True
            ):
                raise ResolveImportPackageError(
                    f"graphic {event_id} does not retain Free placeholder outcome"
                )
        elif event["kind"] != source["kind"]:
            raise ResolveImportPackageError(
                f"event {event_id} kind differs from its source"
            )
    return sources, events, results


def _origin(plan_path: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ResolveImportPackageError(f"{label} has no origin")
    path = Path(value)
    return _safe_existing_regular(
        path if path.is_absolute() else plan_path.parent / path, label
    )


def _normal_origins(
    plan_path: Path, manifest: JsonObject
) -> dict[str, tuple[Path, str]]:
    value, _ = _load(plan_path, "materialization plan")
    expected = {
        source["id"]
        for source in cast(list[JsonObject], manifest["sources"])
        if source["kind"] not in {"placeholder", "fusion_template"}
    }
    if set(value) != expected:
        raise ResolveImportPackageError(
            "materialization plan does not name exactly the non-graphic media"
        )
    result: dict[str, tuple[Path, str]] = {}
    for source_id in expected:
        entry = value[source_id]
        if (
            not isinstance(entry, dict)
            or set(entry) != {"artifactId", "origin", "policy"}
            or entry.get("policy") not in {"copy", "clone_or_copy"}
            or not isinstance(entry.get("artifactId"), str)
            or not entry["artifactId"]
        ):
            raise ResolveImportPackageError(
                f"materialization plan entry {source_id} is invalid"
            )
        result[cast(str, source_id)] = (
            _origin(plan_path, entry["origin"], f"origin for source {source_id}"),
            entry["artifactId"],
        )
    return result


def _bakes(
    plan_path: Path, manifest: JsonObject, report: JsonObject
) -> dict[str, _Bake]:
    value, _ = _load(plan_path, "baked graphic plan")
    if (
        set(value) != {"schemaVersion", "bakes"}
        or value["schemaVersion"] != _SCHEMA
        or not isinstance(value["bakes"], list)
    ):
        raise ResolveImportPackageError("baked graphic plan has an unsupported schema")
    sources, events, _ = _events(manifest, report)
    graphic_events = {
        event_id: event
        for event_id, event in events.items()
        if event["kind"] == "fusion_graphic"
    }
    if len(value["bakes"]) != len(graphic_events):
        raise ResolveImportPackageError(
            "baked graphic plan must name every and only Fusion graphic"
        )
    manual_by_event = {
        item["entity"]["id"]: item["id"]
        for item in cast(list[JsonObject], report["manualCompletionItems"])
        if item["entity"]["kind"] == "timeline_event"
    }
    bakes: dict[str, _Bake] = {}
    required = {
        "eventId",
        "artifactId",
        "origin",
        "renderer",
        "template",
        "semanticSnapshotHash",
        "manualCompletionItemId",
        "expected",
    }
    for entry in cast(list[JsonObject], value["bakes"]):
        if not isinstance(entry, dict) or set(entry) != required:
            raise ResolveImportPackageError("baked graphic entry has unexpected fields")
        event_id = entry.get("eventId")
        event = graphic_events.get(cast(str, event_id))
        if event is None or event_id in bakes:
            raise ResolveImportPackageError(
                "baked graphic entry has an unknown or duplicate event"
            )
        source = sources[event["sourceId"]]
        if (
            entry["template"]
            != {
                key: source[key]
                for key in (
                    "templateKey",
                    "projectRevisionId",
                    "packageDigest",
                    "entryAssetHash",
                )
            }
            or entry["semanticSnapshotHash"] != event["semanticSnapshotHash"]
        ):
            raise ResolveImportPackageError(
                f"baked graphic {event_id} has stale template or semantic identity"
            )
        if entry["manualCompletionItemId"] != manual_by_event.get(event_id):
            raise ResolveImportPackageError(
                f"baked graphic {event_id} would silently replace the Free manual item"
            )
        renderer = entry["renderer"]
        expected = entry["expected"]
        if (
            not isinstance(entry["artifactId"], str)
            or not entry["artifactId"]
            or not isinstance(renderer, dict)
            or set(renderer) != {"name", "version"}
            or not all(
                isinstance(renderer[key], str) and renderer[key] for key in renderer
            )
            or not isinstance(expected, dict)
            or set(expected)
            != {"width", "height", "frameRate", "durationFrames", "alpha"}
            or expected["alpha"] is not True
            or expected["frameRate"] != manifest["timeline"]["frameRate"]
            or expected["durationFrames"] != event["recordRange"]["durationFrames"]
            or expected["width"] != manifest["timeline"]["width"]
            or expected["height"] != manifest["timeline"]["height"]
        ):
            raise ResolveImportPackageError(
                f"baked graphic {event_id} has invalid expected media facts"
            )
        bakes[cast(str, event_id)] = _Bake(
            event,
            source,
            _origin(plan_path, entry["origin"], f"baked origin for {event_id}"),
            entry["artifactId"],
            renderer,
            cast(str, entry["manualCompletionItemId"]),
            expected,
        )
    return bakes


def _alpha(pix_fmt: object) -> bool:
    return isinstance(pix_fmt, str) and any(
        token in pix_fmt.lower()
        for token in ("yuva", "rgba", "argb", "bgra", "abgr", "gbrap")
    )


def _bake_facts(bake: _Bake, ffprobe: str) -> JsonObject:
    probe = _verify_probe(
        {"id": bake.event["id"], "kind": "video", **bake.expected, "audioChannels": 0},
        bake.origin,
        ffprobe,
        Fraction(
            bake.expected["frameRate"]["numerator"],
            bake.expected["frameRate"]["denominator"],
        ),
    )
    # _verify_probe validates timing, dimensions, and rate. Alpha is intentionally
    # checked from an independent probe so a non-alpha video cannot masquerade.
    from .package import _probe

    streams = _probe(bake.origin, ffprobe)["streams"]
    video = next(
        (stream for stream in streams if stream.get("codec_type") == "video"), None
    )
    if not isinstance(video, dict) or not _alpha(video.get("pix_fmt")):
        raise ResolveImportPackageError(
            f"baked graphic {bake.event['id']} is missing alpha"
        )
    return {**probe, "alpha": True, "pixelFormat": video["pix_fmt"]}


def _relative(source: JsonObject, event_id: str | None = None) -> PurePosixPath:
    if event_id is not None:
        return PurePosixPath("Media") / "Graphics" / f"{event_id}.mov"
    if source["kind"] == "placeholder":
        return PurePosixPath("Media") / "Placeholders" / f"{source['id']}.png"
    return _safe_manifest_destination(source)


def _locator(relative: PurePosixPath) -> str:
    return (PurePosixPath("..") / ".." / relative).as_posix()


def _build_otio(manifest: JsonObject, bakes: Mapping[str, JsonObject]) -> Any:
    settings = cast(JsonObject, manifest["timeline"])
    rate = _rate(manifest)
    start = cast(int, settings["startFrame"])
    end = start + cast(int, settings["durationFrames"])
    timeline = otio.schema.Timeline(
        name=f"VERA baked candidate {manifest['buildId']}",
        global_start_time=otio.opentime.RationalTime(start, rate),
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
            event_start, duration = (
                cast(int, event["recordRange"]["startFrame"]),
                cast(int, event["recordRange"]["durationFrames"]),
            )
            if event_start > cursor:
                track.append(
                    otio.schema.Gap(
                        source_range=_time_range(0, event_start - cursor, rate)
                    )
                )
            source = sources[event["sourceId"]]
            bake = bakes.get(cast(str, event["id"]))
            source_range = event.get(
                "sourceRange", {"startFrame": 0, "durationFrames": duration}
            )
            source_rate = (
                rate
                if bake is not None or source["kind"] != "video"
                else source["frameRate"]["numerator"]
                / source["frameRate"]["denominator"]
            )
            relative = _relative(
                source, cast(str, event["id"]) if bake is not None else None
            )
            ref_meta: JsonObject = {
                "source_id": source["id"],
                "source_kind": source["kind"],
            }
            clip_meta: JsonObject = {
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
            if bake is not None:
                ref_meta["graphic_bake"] = bake
                clip_meta["graphic_bake"] = bake
            elif source["kind"] == "placeholder":
                ref_meta.update({"label": source["label"], "reason": source["reason"]})
                clip_meta["placeholder"] = {
                    "label": source["label"],
                    "reason": source["reason"],
                }
            else:
                ref_meta["content_hash"] = source["contentHash"]
            track.append(
                otio.schema.Clip(
                    name=f"baked: {event['id']}"
                    if bake is not None
                    else cast(str, source.get("label", source["kind"])),
                    media_reference=otio.schema.ExternalReference(
                        target_url=_locator(relative),
                        available_range=_time_range(
                            0,
                            duration
                            if bake is not None
                            else cast(int, source.get("durationFrames", duration)),
                            source_rate,
                        ),
                        metadata={"vera": ref_meta},
                    ),
                    source_range=_time_range(
                        cast(int, source_range["startFrame"]),
                        cast(int, source_range["durationFrames"]),
                        source_rate,
                    ),
                    metadata={"vera": clip_meta},
                )
            )
            cursor = event_start + duration
        if cursor < end:
            track.append(
                otio.schema.Gap(source_range=_time_range(0, end - cursor, rate))
            )
        timeline.tracks.append(track)
    for marker in cast(list[JsonObject], manifest["markers"]):
        timeline.tracks.markers.append(
            otio.schema.Marker(
                name=marker["name"],
                marked_range=_time_range(cast(int, marker["frame"]) - start, 0, rate),
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


def _instructions(manifest: JsonObject, report: JsonObject) -> bytes:
    items = "\n".join(
        f"- `{item['id']}` — {item['action']}"
        for item in report["manualCompletionItems"]
    )
    return f"""# VERA Resolve Free baked-graphic candidate

Build: `{manifest["buildId"]}`

This package contains a candidate baked EV24 clip. `build-report.json` remains
the compiler's unchanged Free placeholder outcome; the candidate is not a
silent replacement and needs the external fidelity check below.

1. Keep the complete Authoring Project folder intact.
2. In tested Resolve Free, import `timeline.otio`. Do not replace media.
3. Compare animation, transparent regions, semantic text/badge values, rate,
   and duration to the named Studio render.
4. Record acceptance or failure against the retained candidate receipt.

## Retained compiler manual items

{items or "- None"}
""".encode()


def _receipt(
    manifest: JsonObject,
    manifest_bytes: bytes,
    report: JsonObject,
    report_bytes: bytes,
    bakes: list[JsonObject],
    otio_bytes: bytes,
    instructions: bytes,
    verified_at: str,
) -> JsonObject:
    return {
        "schemaVersion": _SCHEMA,
        "status": "ready_for_external_acceptance",
        "verifiedAt": verified_at,
        "buildId": manifest["buildId"],
        "manifest": {
            "id": manifest["id"],
            "contentHash": f"sha256:{hashlib.sha256(manifest_bytes).hexdigest()}",
        },
        "buildReport": {
            "id": report["id"],
            "contentHash": f"sha256:{hashlib.sha256(report_bytes).hexdigest()}",
        },
        "timeline": manifest["timeline"],
        "graphicBakeCandidates": bakes,
        "packageArtifacts": {
            "timelineOtio": {
                "path": OTIO_FILENAME,
                "contentHash": f"sha256:{hashlib.sha256(otio_bytes).hexdigest()}",
            },
            "importInstructions": {
                "path": INSTRUCTIONS_FILENAME,
                "contentHash": f"sha256:{hashlib.sha256(instructions).hexdigest()}",
            },
        },
    }


def build_baked_graphic_package(
    manifest_path: Path | str,
    report_path: Path | str,
    materialization_plan_path: Path | str,
    baked_graphic_plan_path: Path | str,
    project_root: Path | str,
    *,
    ffprobe_executable: str = "ffprobe",
    verified_at: str = "2026-09-22T00:00:00Z",
) -> BakedGraphicPackageResult:
    """Publish an EV24 candidate only after exact provenance and media checks."""
    manifest, manifest_bytes = _load(Path(manifest_path), "timeline manifest")
    report, report_bytes = _load(Path(report_path), "build report")
    _validate_contracts(manifest, report)
    _events(manifest, report)
    normal = _normal_origins(Path(materialization_plan_path), manifest)
    bakes = _bakes(Path(baked_graphic_plan_path), manifest, report)
    verified_at = _validate_verified_at(verified_at)
    root = Path(project_root)
    if root.exists():
        verify_baked_graphic_package(root, ffprobe_executable=ffprobe_executable)
        return BakedGraphicPackageResult(
            root,
            root / "Builds" / manifest["buildId"],
            root / "Builds" / manifest["buildId"] / VERIFICATION_FILENAME,
            root / "Builds" / manifest["buildId"] / OTIO_FILENAME,
            True,
        )
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{root.name}.staging-", dir=root.parent))
    try:
        build = staging / "Builds" / manifest["buildId"]
        build.mkdir(parents=True)
        (build / MANIFEST_FILENAME).write_bytes(manifest_bytes)
        (build / REPORT_FILENAME).write_bytes(report_bytes)
        baked_receipt: list[JsonObject] = []
        for source in cast(list[JsonObject], manifest["sources"]):
            if source["kind"] == "fusion_template":
                continue
            relative = _relative(source)
            destination = staging.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source["kind"] == "placeholder":
                destination.write_bytes(
                    render_placeholder_slate(
                        cast(str, source["label"]),
                        cast(int, manifest["timeline"]["width"]),
                        cast(int, manifest["timeline"]["height"]),
                    )
                )
            else:
                origin, _ = normal[cast(str, source["id"])]
                if _sha256_file(origin) != _hash(
                    cast(str, source["contentHash"]), f"source {source['id']} hash"
                ):
                    raise ResolveImportPackageError(
                        f"origin hash mismatch for source {source['id']}"
                    )
                shutil.copyfile(origin, destination)
        for event_id, bake in bakes.items():
            facts = _bake_facts(bake, ffprobe_executable)
            relative = _relative(bake.source, event_id)
            destination = staging.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bake.origin, destination)
            baked_receipt.append(
                {
                    "eventId": event_id,
                    "sourceId": bake.source["id"],
                    "artifactId": bake.artifact_id,
                    "path": relative.as_posix(),
                    "contentHash": f"sha256:{_sha256_file(destination)}",
                    "renderer": bake.renderer,
                    "template": {
                        key: bake.source[key]
                        for key in (
                            "templateKey",
                            "projectRevisionId",
                            "packageDigest",
                            "entryAssetHash",
                        )
                    },
                    "semanticSnapshotHash": bake.event["semanticSnapshotHash"],
                    "manualCompletionItemId": bake.manual_item_id,
                    "mediaFacts": facts,
                }
            )
        timeline = _build_otio(
            manifest, {entry["eventId"]: entry for entry in baked_receipt}
        )
        otio.adapters.write_to_file(
            timeline, str(build / OTIO_FILENAME), adapter_name="otio_json"
        )
        otio_bytes = (build / OTIO_FILENAME).read_bytes()
        instructions = _instructions(manifest, report)
        (build / INSTRUCTIONS_FILENAME).write_bytes(instructions)
        (build / VERIFICATION_FILENAME).write_bytes(
            _canonical_json(
                _receipt(
                    manifest,
                    manifest_bytes,
                    report,
                    report_bytes,
                    baked_receipt,
                    otio_bytes,
                    instructions,
                    verified_at,
                )
            )
        )
        verify_baked_graphic_package(staging, ffprobe_executable=ffprobe_executable)
        os.replace(staging, root)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    build = root / "Builds" / manifest["buildId"]
    return BakedGraphicPackageResult(
        root, build, build / VERIFICATION_FILENAME, build / OTIO_FILENAME, False
    )


def verify_baked_graphic_package(
    project_root: Path | str, *, ffprobe_executable: str = "ffprobe"
) -> None:
    """Verify a published candidate package without trusting its receipt."""
    root = Path(project_root)
    builds = [path for path in (root / "Builds").iterdir() if path.is_dir()]
    if len(builds) != 1:
        raise ResolveImportPackageError(
            "candidate package must contain exactly one build"
        )
    build = builds[0]
    manifest, manifest_bytes = _load(
        build / MANIFEST_FILENAME, "packaged timeline manifest"
    )
    report, report_bytes = _load(build / REPORT_FILENAME, "packaged build report")
    receipt, _ = _load(build / VERIFICATION_FILENAME, "candidate receipt")
    _validate_contracts(manifest, report)
    _events(manifest, report)
    if (
        receipt.get("schemaVersion") != _SCHEMA
        or receipt.get("status") != "ready_for_external_acceptance"
        or receipt.get("buildId") != manifest["buildId"]
    ):
        raise ResolveImportPackageError("candidate receipt identity differs")
    bakes = cast(list[JsonObject], receipt.get("graphicBakeCandidates", []))
    graphics = [
        event for event in manifest["events"] if event["kind"] == "fusion_graphic"
    ]
    if len(bakes) != len(graphics):
        raise ResolveImportPackageError("candidate receipt graphic inventory differs")
    actual_files = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    expected_files = {
        f"Builds/{manifest['buildId']}/{name}"
        for name in (
            MANIFEST_FILENAME,
            REPORT_FILENAME,
            OTIO_FILENAME,
            INSTRUCTIONS_FILENAME,
            VERIFICATION_FILENAME,
        )
    }
    for source in manifest["sources"]:
        if source["kind"] != "fusion_template":
            expected_files.add(_relative(source).as_posix())
    for entry in bakes:
        expected_files.add(cast(str, entry["path"]))
    if actual_files != expected_files:
        raise ResolveImportPackageError("candidate package inventory differs")
    bake_by_event = {entry["eventId"]: entry for entry in bakes}
    for event in graphics:
        receipt_entry = bake_by_event.get(event["id"])
        if receipt_entry is None:
            raise ResolveImportPackageError(
                f"candidate receipt graphic inventory differs: {event['id']}"
            )
        if receipt_entry.get("semanticSnapshotHash") != event[
            "semanticSnapshotHash"
        ] or receipt_entry.get("template") != {
            key: next(
                source
                for source in manifest["sources"]
                if source["id"] == event["sourceId"]
            )[key]
            for key in (
                "templateKey",
                "projectRevisionId",
                "packageDigest",
                "entryAssetHash",
            )
        }:
            raise ResolveImportPackageError(
                f"candidate receipt provenance differs: {event['id']}"
            )
        path = root / cast(str, receipt_entry["path"])
        if receipt_entry.get("contentHash") != f"sha256:{_sha256_file(path)}":
            raise ResolveImportPackageError(
                f"candidate media hash differs: {event['id']}"
            )
        expected = {
            "width": manifest["timeline"]["width"],
            "height": manifest["timeline"]["height"],
            "frameRate": manifest["timeline"]["frameRate"],
            "durationFrames": event["recordRange"]["durationFrames"],
            "alpha": True,
        }
        bake = _Bake(
            cast(JsonObject, event),
            cast(
                JsonObject,
                next(
                    source
                    for source in manifest["sources"]
                    if source["id"] == event["sourceId"]
                ),
            ),
            path,
            cast(str, receipt_entry["artifactId"]),
            cast(JsonObject, receipt_entry["renderer"]),
            cast(str, receipt_entry["manualCompletionItemId"]),
            expected,
        )
        if receipt_entry.get("mediaFacts") != _bake_facts(bake, ffprobe_executable):
            raise ResolveImportPackageError(
                f"candidate media facts differ: {event['id']}"
            )
    timeline = otio.adapters.read_from_file(str(build / OTIO_FILENAME))
    clips = [
        child
        for track in timeline.tracks
        for child in track
        if isinstance(child, otio.schema.Clip)
    ]
    for event in graphics:
        clip = next(
            (
                clip
                for clip in clips
                if clip.metadata.get("vera", {}).get("event_id") == event["id"]
            ),
            None,
        )
        if (
            clip is None
            or clip.media_reference.target_url
            != _locator(
                _relative(
                    cast(
                        JsonObject,
                        next(
                            source
                            for source in manifest["sources"]
                            if source["id"] == event["sourceId"]
                        ),
                    ),
                    cast(str, event["id"]),
                )
            )
            or _plain(clip.metadata.get("vera", {}).get("graphic_bake"))
            != bake_by_event[event["id"]]
        ):
            raise ResolveImportPackageError(
                f"OTIO baked graphic differs: {event['id']}"
            )
    expected_receipt = _receipt(
        manifest,
        manifest_bytes,
        report,
        report_bytes,
        bakes,
        (build / OTIO_FILENAME).read_bytes(),
        (build / INSTRUCTIONS_FILENAME).read_bytes(),
        _validate_verified_at(receipt.get("verifiedAt")),
    )
    if receipt != expected_receipt:
        raise ResolveImportPackageError("candidate receipt is inconsistent")


def _plain(value: Any) -> Any:
    if hasattr(value, "items"):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)) or type(value).__name__ == "AnyVector":
        return [_plain(item) for item in value]
    return value


def main(argv: Sequence[str] | None = None) -> int:
    """Build a candidate package without invoking a renderer."""
    parser = argparse.ArgumentParser(
        description="Package one declared EV24 baked-media candidate for Resolve Free."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("materialization_plan", type=Path)
    parser.add_argument("baked_graphic_plan", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ffprobe", default="ffprobe")
    arguments = parser.parse_args(argv)
    try:
        result = build_baked_graphic_package(
            arguments.manifest,
            arguments.report,
            arguments.materialization_plan,
            arguments.baked_graphic_plan,
            arguments.output,
            ffprobe_executable=arguments.ffprobe,
        )
    except ResolveImportPackageError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "ready_for_external_acceptance",
                "projectRoot": str(result.project_root),
                "buildRoot": str(result.build_root),
                "verificationReceipt": str(result.verification_path),
                "reused": result.reused,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
