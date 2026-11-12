"""Prepare the public 30-row #312 fixture for the #520 build-speed check.

Only local public speech replay, generated silent video, and compiler/media
preparation are used. This module never contacts Resolve or a speech provider.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import subprocess
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from .build_compiler_bridge import invoke_bridge
from .generated.contracts.script_document_v2_schema import NarrationBlockV2
from .issue312_fixture import MAX_BYTES, placement_plan, source_command
from .issue312_speech import checked_alignment, prepare_rows, verify_source
from .media_preparation import (
    POLICY_HASH,
    PROFILE,
    PROFILE_HASH,
    MediaTools,
    PreparationAuthorization,
    inspect_media,
    prepare_media,
    wire,
)
from .narration.cache import NarrationCache
from .narration.compiler_dependencies_v2 import narration_v2_dependency_from_asset
from .narration.models import NarrationAudioAsset, canonical_json_bytes, identity_hash
from .v2_package import (
    _compiler_hash,
    _file_hash,
    build_v2_package,
    verify_v2_package,
)

ROOT = Path(__file__).resolve().parents[2]
RATE = Fraction(24, 1)
Json = dict[str, Any]


def _id(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "vera:issue520-long:" + label))


def _write(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def _plain(path: Path) -> None:
    if any(part.is_symlink() for part in (path.absolute(), *path.absolute().parents)):
        raise ValueError(f"symbolic-link path refused: {path}")


def _sources(
    root: Path, seconds: int, tools: MediaTools
) -> tuple[Json, list[Json], dict[str, Any]]:
    if type(seconds) is not int or not 3 <= seconds <= 120:
        raise ValueError("source duration must be 3-120 seconds")
    root.mkdir(parents=True, exist_ok=False)
    plan = placement_plan()
    plan["timeline"]["rate"] = wire(RATE)
    for source in plan["sources"]:
        source["rate"] = wire(RATE)
    inspections: dict[str, Any] = {}
    records: list[Json] = []
    total = 0
    for source in plan["sources"]:
        path = root / f"{source['id']}.mp4"
        command = source_command(source, path, source_seconds=seconds, ffmpeg="ffmpeg")
        subprocess.run(command, check=True, capture_output=True, timeout=1800)
        inspection = inspect_media(
            path, video_stream_index=0, audio_stream_index=None, tools=tools
        )
        video = inspection.video
        if (
            inspection.rate != RATE
            or inspection.audio is not None
            or video.get("codec_name") != "h264"
            or video.get("pix_fmt") != "yuv420p"
            or video.get("width") != source["width"]
            or video.get("height") != source["height"]
            or len(inspection.video_frames) != seconds * 24
            or any(
                video.get(key) != value
                for key, value in {
                    "color_range": "tv",
                    "color_space": "bt709",
                    "color_transfer": "bt709",
                    "color_primaries": "bt709",
                    "field_order": "progressive",
                }.items()
            )
        ):
            raise ValueError(
                f"generated source is not verified exact 24 fps: {source['id']}"
            )
        total += path.stat().st_size
        if total > MAX_BYTES:
            raise ValueError("24 fps source set exceeds 2 GiB; retain failed attempt")
        inspections[source["id"]] = inspection
        records.append(
            {
                **source,
                "file": path.name,
                "sha256": inspection.content_hash,
                "probeHash": inspection.probe_hash,
                "decodedFrames": len(inspection.video_frames),
                "sizeBytes": path.stat().st_size,
                "command": command,
            }
        )
    _write(
        root / "source-set.json",
        {
            "schemaVersion": "issue-312-source-set/v1",
            "plan": plan,
            "generatorHash": _file_hash(Path(__file__)),
            "sourceSeconds": seconds,
            "rights": "CC0-1.0; generated mathematical video patterns",
            "sources": records,
            "complete": True,
            "totalSourceBytes": total,
        },
    )
    return plan, records, inspections


def _descriptor(item: Json, owner: Json, source: Json, inspection: Any) -> Json:
    source_id = source["id"]
    frame_map = {
        "packageFrameZeroLogicalFrame": 0,
        "packageVideoPtsOrigin": wire(inspection.pts_origin),
        "loggedTimeAtPackageFrameZero": wire(Fraction(0)),
        "decodedPackageFrameRate": wire(inspection.rate),
        "decodedPackageFrameCount": len(inspection.video_frames),
        "packageVideoTimeBase": wire(inspection.time_base),
        "sourceAudioStreamMappings": [],
        "descriptorHash": inspection.probe_hash,
        "probeHash": inspection.probe_hash,
    }
    return {
        "payloadId": _id(item["id"] + ":payload"),
        "owner": owner,
        "mediaReferenceId": _id(source_id),
        "sourceSnapshot": {
            "system": "local_import",
            "snapshotId": _id(source_id + ":snapshot"),
            "version": 1,
            "packageId": _id(source_id + ":package"),
            "contentHash": inspection.content_hash,
            "probeHash": inspection.probe_hash,
        },
        "logicalSourceBounds": {
            "startFrame": 0,
            "endFrame": len(inspection.video_frames),
            "frameRate": wire(inspection.rate),
        },
        "sourceFrameMap": frame_map,
        "occurrenceSourceInFrame": item["sourceInFrame"],
        "selectedSourceRange": None,
        "preparedMediaRequirementKey": None,
    }


def _block_payload(
    item: Json,
    owner: Json,
    sources: dict[str, Json],
    inspections: dict[str, Any],
    descriptors: list[Json],
) -> Json:
    payload_id = _id(item["id"] + ":payload")
    if item.get("pictureKind") == "intentional_placeholder":
        return {
            "kind": "visual",
            "payloadId": payload_id,
            "pictureKind": "intentional_placeholder",
            "source": {
                "kind": "intentional_placeholder",
                "text": f"ISSUE 312 FIXTURE {item['id']}",
            },
            "sourceUsage": None,
            "audioPolicy": "mute",
            "framingPolicy": "contain",
        }
    descriptor = _descriptor(
        item, owner, sources[item["source"]], inspections[item["source"]]
    )
    descriptors.append(descriptor)
    return {
        "kind": "visual",
        "payloadId": descriptor["payloadId"],
        "pictureKind": "clip",
        "source": {
            "kind": "media_reference",
            "mediaReferenceId": descriptor["mediaReferenceId"],
        },
        "sourceUsage": {"sourceInFrame": item["sourceInFrame"]},
        "audioPolicy": "mute",
        "framingPolicy": "contain",
    }


def _document(
    plan: Json, rows: list[Json], records: list[Json], inspections: dict[str, Any]
) -> tuple[Json, list[Json]]:
    sources = {source["id"]: source for source in records}
    descriptors: list[Json] = []
    document: Json = {
        "schemaVersion": "script-document/v2",
        "id": _id("document"),
        "projectId": _id("project"),
        "title": "Public long build-speed fixture #520",
        "activeDraft": {"blocks": [], "supportingItems": []},
        "ideaOutline": [],
        "extras": [],
        "liveHeadSequence": 0,
        "liveStateVector": "",
        "liveContentHash": "",
    }
    for index, record in enumerate(rows):
        block = copy.deepcopy(record["block"])
        sequence = _id(f"row:{index}:sequence")
        block.update(
            orderKey=f"{index:03d}",
            state="active",
            notes=[],
            overlayEvents=[],
            timingPolicy="narration_spine",
        )
        slots = []
        for item in (row for row in plan["pictures"] if row["row"] == index):
            slot_id = _id(item["id"] + ":slot")
            boundary: Json = {"kind": "row_start"}
            if slots:
                token = block["tokens"][30 if item["id"] == "picture-01" else 22]
                boundary = {
                    "kind": "spoken_word",
                    "anchor": {
                        "blockId": block["id"],
                        "tokenId": token["id"],
                        "quotedWord": token["value"],
                        "anchorVersion": 1,
                        "affinity": "before",
                    },
                }
            slots.append(
                {
                    "id": slot_id,
                    "kind": "content",
                    "version": 1,
                    "relation": {"kind": "base" if not slots else "sequential"},
                    "boundaryBefore": boundary,
                    "playoutPolicy": "match_structural_interval",
                    "payload": _block_payload(
                        item,
                        {
                            "kind": "primary_slot",
                            "sequenceId": sequence,
                            "slotId": slot_id,
                        },
                        sources,
                        inspections,
                        descriptors,
                    ),
                }
            )
        block["primaryVisualSequence"] = {"id": sequence, "version": 1, "slots": slots}
        for item in (row for row in plan["overlays"] if row["row"] == index):
            event_id = _id(item["id"])
            token = block["tokens"][item["tokenIndex"]]
            payload = _block_payload(
                item,
                {
                    "kind": "overlay_event",
                    "blockId": block["id"],
                    "overlayEventId": event_id,
                },
                sources,
                inspections,
                descriptors,
            )
            block["overlayEvents"].append(
                {
                    "id": event_id,
                    "version": 1,
                    "payload": payload,
                    "timing": {
                        "kind": "timed",
                        "durationMs": item["durationMs"],
                        "start": {
                            "kind": "word",
                            "anchor": {
                                "blockId": block["id"],
                                "tokenId": token["id"],
                                "quotedWord": token["value"],
                                "anchorVersion": 1,
                                "affinity": "before",
                            },
                        },
                    },
                }
            )
        document["activeDraft"]["blocks"].append(block)
    document["liveContentHash"] = _compiler_hash(
        {key: value for key, value in document.items() if key != "liveContentHash"}
    )
    return document, descriptors


def _dependencies(document: Json, rows: list[Json], maps: list[Json]) -> Json:
    deps = json.loads(
        (ROOT / "tests/data/authoring_v2/compiler-dependencies-v2.json").read_bytes()
    )
    for key in ("buildId", "manifestId", "reportId"):
        deps["build"][key] = str(uuid.uuid4())
    deps["compiler"]["sourceHash"] = _file_hash(
        ROOT / "packages/contracts/src/compiler-core-v2.ts"
    )
    frames = sum(
        math.ceil(
            Fraction(
                row["evidence"]["audio"]["durationSamples"],
                row["evidence"]["audio"]["sampleRate"],
            )
            * RATE
        )
        for row in rows
    )
    deps["timeline"].update(frameRate=wire(RATE), durationFrames=frames)
    video_roles = ("root", "overlay", "presenter", "placeholder", "markers")
    deps["tracks"] = [
        {"id": role, "kind": "video", "index": i + 1, "name": role.title()}
        for i, role in enumerate(video_roles)
    ]
    deps["tracks"].append(
        {"id": "narration", "kind": "audio", "index": 1, "name": "Narration"}
    )
    deps["roles"] = {
        "primaryRootTrackId": "root",
        "childTrackIds": [],
        "overlayTrackIds": ["overlay"],
        "presenterTrackId": "presenter",
        "placeholderTrackId": "placeholder",
        "narrationTrackId": "narration",
        "sourceAudioTrackIds": [],
        "markerTrackId": "markers",
    }
    deps["document"].update(
        documentId=document["id"],
        projectId=document["projectId"],
        contentHash=document["liveContentHash"],
        textHash="sha256:"
        + hashlib.sha256(
            "\n".join(row["block"]["text"] for row in rows).encode()
        ).hexdigest(),
    )
    (
        deps["narrationTimingMaps"],
        deps["preparedMedia"],
        deps["occurrenceResolutions"],
    ) = maps, [], []
    return deps


def _key(descriptor: Json, requested: Json, tool_hash: str) -> str:
    return identity_hash(
        {
            "mediaReferenceId": descriptor["mediaReferenceId"],
            "sourceSnapshot": descriptor["sourceSnapshot"],
            "sourceFrameMap": descriptor["sourceFrameMap"],
            "videoStreamIndex": 0,
            "audioStreamIndex": None,
            "requestedRange": requested,
            "targetRate": wire(RATE),
            "profile": {
                "policyHash": POLICY_HASH,
                "profileHash": PROFILE_HASH,
                "toolHash": tool_hash,
                "profileVersion": PROFILE["version"],
            },
        }
    )


def prepare_long_fixture(
    source_root: Path, alignment_path: Path, output: Path, *, source_seconds: int = 30
) -> Path:
    source_root, alignment_path = source_root.absolute(), alignment_path.absolute()
    _plain(source_root)
    _plain(alignment_path)
    verify_source(source_root)
    alignment = json.loads(alignment_path.read_bytes())
    checked_alignment(alignment)
    if alignment.get("provenance", {}).get("settings", {}).get("mfaExitCode") != 0:
        raise ValueError("successful retained MFA alignment is required")
    root = output.absolute()
    _plain(root)
    root.mkdir(parents=True, exist_ok=False)
    tools = MediaTools()
    plan, sources, inspections = _sources(root / "video-sources", source_seconds, tools)
    speech_path = prepare_rows(source_root, alignment_path, root / "speech", rows=30)
    speech = json.loads(speech_path.read_bytes())
    rows = [row for row in speech["rows"] if row.get("alternate") is not True]
    if len(rows) != 30:
        raise ValueError("30 measured narration rows are required")
    cache = NarrationCache(speech_path.parent / "cache")
    maps: list[Json] = []
    audio_paths: dict[str, Path] = {}
    for row in rows:
        asset_entry = cache.read("assets", row["assetKey"], "asset.json")
        if asset_entry is None:
            raise ValueError("verified public narration cache asset is missing")
        asset = NarrationAudioAsset(**asset_entry.metadata["asset"])
        mapping = narration_v2_dependency_from_asset(
            asset,
            asset_entry.files["timing.json"],
            cast(NarrationBlockV2, row["block"]),
        )
        maps.append(cast(Json, mapping))
        audio_paths[mapping["audio"]["narrationAssetId"]] = (
            speech_path.parent / row["audioFile"]
        ).absolute()
    document, descriptors = _document(plan, rows, sources, inspections)
    deps = _dependencies(document, rows, maps)
    deps["occurrenceResolutions"] = descriptors
    script_path, deps_path = root / "script.json", root / "compiler-dependencies.json"
    _write(script_path, document)
    _write(deps_path, deps)

    source_root_paths = {
        source["id"]: root / "video-sources" / source["file"] for source in sources
    }
    source_by_ref = {_id(source["id"]): source for source in sources}
    descriptor_by_payload = {
        descriptor["payloadId"]: descriptor for descriptor in descriptors
    }
    tool_hash = identity_hash(tools.fingerprint())
    initial = invoke_bridge("needs", script_path, deps_path).needs["requirements"]
    unique: dict[str, tuple[Json, Json, Path]] = {}
    for need in initial:
        descriptor = descriptor_by_payload[need["payloadId"]]
        if need["sourceSufficiency"] != "sufficient":
            raise ValueError(
                "generated source does not cover the compiler's requested range"
            )
        source = source_by_ref[descriptor["mediaReferenceId"]]
        key = _key(descriptor, need["requestedRange"], tool_hash)
        descriptor["preparedMediaRequirementKey"] = key
        unique.setdefault(key, (descriptor, need, source_root_paths[source["id"]]))

    authorization = PreparationAuthorization(
        reference="issue520-public-24fps-synthetic-fixture",
        read_roots=(root / "video-sources",),
        write_root=root / "prepared-media",
        tool_hash=tool_hash,
        allow_conversion=False,
    )
    prepared: dict[str, Any] = {}
    preparation_paths: dict[str, Path] = {}
    for key, (descriptor, need, path) in unique.items():
        item = prepare_media(
            path,
            cast(Any, descriptor),
            cast(Any, need["requestedRange"]),
            cast(Any, wire(RATE)),
            authorization=authorization,
            video_stream_index=0,
            audio_stream_index=None,
            tools=tools,
        )
        if (
            item.binding["requirementKey"] != key
            or item.binding["mode"] != "verified_reuse"
        ):
            raise ValueError(
                "24 fps media did not produce an exact verified-reuse binding"
            )
        prepared[key] = item
        preparation_paths[key] = item.receipt_path
    deps["preparedMedia"] = [item.binding for item in prepared.values()]
    _write(deps_path, deps)
    needs = invoke_bridge("needs", script_path, deps_path).needs
    if {row["requirementKey"] for row in needs["requirements"]} != set(prepared):
        raise ValueError("prepared media keys differ from compiler requirements")
    _write(root / "media-needs.json", needs)
    _write(
        root / "preparation-paths.json",
        {key: str(path) for key, path in preparation_paths.items()},
    )

    compiled = invoke_bridge("compile", script_path, deps_path).result
    manifest_path, report_path = (
        root / "preflight-manifest.json",
        root / "preflight-report.json",
    )
    manifest_path.write_text(compiled["manifestJson"], encoding="utf-8")
    report_path.write_text(compiled["reportJson"], encoding="utf-8")
    descriptor_by_key = {d["preparedMediaRequirementKey"]: d for d in descriptors}
    media_paths: dict[str, Path] = {}
    for source in compiled["manifest"]["sources"]:
        source_id = source["id"]
        if isinstance(source.get("narrationAudio"), dict):
            media_paths[f"source:{source_id}"] = audio_paths[source_id]
        else:
            key = source["preparationRequirementKey"]
            media_paths[f"source:{source_id}"] = prepared[key].video_path
            original = source_by_ref[descriptor_by_key[key]["mediaReferenceId"]]
            media_paths[f"original:{source_id}"] = source_root_paths[original["id"]]
    _write(
        root / "media-paths.json", {key: str(path) for key, path in media_paths.items()}
    )
    package_root = root / "preflight-package"
    package = build_v2_package(
        manifest_path,
        report_path,
        script_path,
        deps_path,
        package_root,
        media_paths=media_paths,
        preparation_paths=preparation_paths,
    )
    checked = verify_v2_package(package_root)
    if checked.build_id != package.build_id:
        raise ValueError("preflight package identity differs after verification")
    timeline = compiled["manifest"]["timeline"]
    result = {
        "schemaVersion": "issue-520-long-fixture/v1",
        "timelineRate": wire(RATE),
        "durationFrames": timeline["durationFrames"],
        "durationSeconds": float(Fraction(timeline["durationFrames"], 24)),
        "rows": len(rows),
        "events": len(compiled["manifest"]["events"]),
        "sources": len(sources),
        "requirements": len(prepared),
        "package": str(package_root),
        "buildId": package.build_id,
        "alignment": str(alignment_path),
        "alignmentHash": _file_hash(alignment_path),
        "sourceSet": str(root / "video-sources" / "source-set.json"),
        "speechRows": str(speech_path),
    }
    _write(root / "fixture.json", result)
    return root / "fixture.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--alignment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-seconds", type=int, default=30)
    args = parser.parse_args()
    print(
        prepare_long_fixture(
            args.source_root,
            args.alignment,
            args.output,
            source_seconds=args.source_seconds,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
