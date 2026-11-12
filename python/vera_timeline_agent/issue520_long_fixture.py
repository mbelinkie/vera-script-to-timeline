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


def _timing_inputs(speech_path: Path) -> tuple[list[Json], dict[str, Path]]:
    speech = json.loads(speech_path.read_bytes())
    rows = [row for row in speech["rows"] if row.get("alternate") is not True]
    if len(rows) != 30:
        raise ValueError("30 measured narration rows are required")
    cache = NarrationCache(speech_path.parent / "cache")
    maps, audio_paths = [], {}
    for row in rows:
        entry = cache.read("assets", row["assetKey"], "asset.json")
        if entry is None:
            raise ValueError("verified public narration cache asset is missing")
        asset = NarrationAudioAsset(**entry.metadata["asset"])
        mapping = narration_v2_dependency_from_asset(
            asset, entry.files["timing.json"], cast(NarrationBlockV2, row["block"])
        )
        maps.append(cast(Json, mapping))
        audio_paths[mapping["audio"]["narrationAssetId"]] = (
            speech_path.parent / row["audioFile"]
        ).absolute()
    return maps, audio_paths


def _complete_fixture(root: Path, source_root: Path, alignment_path: Path) -> Path:
    """Finish only verified prepared inputs; never overwrite an existing attempt."""
    root = root.absolute()
    _plain(root)
    if not root.is_dir():
        raise ValueError("saved fixture output directory is unavailable")
    source_root, alignment_path = source_root.absolute(), alignment_path.absolute()
    _plain(source_root)
    _plain(alignment_path)
    verify_source(source_root)
    alignment = json.loads(alignment_path.read_bytes())
    checked_alignment(alignment)
    if alignment.get("provenance", {}).get("settings", {}).get("mfaExitCode") != 0:
        raise ValueError("successful retained MFA alignment is required")

    source_manifest_path = root / "video-sources" / "source-set.json"
    speech_path = root / "speech" / "speech-rows.json"
    script_path, deps_path = root / "script.json", root / "compiler-dependencies.json"
    for path in (source_manifest_path, speech_path, script_path, deps_path):
        _plain(path)
        if not path.is_file():
            raise ValueError(f"incomplete saved fixture input: {path.name}")
    later_outputs = (
        "prepared-inputs",
        "media-needs.json",
        "preparation-paths.json",
        "media-paths.json",
        "preflight-manifest.json",
        "preflight-report.json",
        "preflight-package",
        "fixture.json",
    )
    if any((root / name).exists() for name in later_outputs):
        raise ValueError(
            "saved fixture already has later-stage outputs; inspect before resuming"
        )
    preparation_root = root / "prepared-media"
    if preparation_root.exists():
        _plain(preparation_root)
        if not preparation_root.is_dir():
            raise ValueError("saved media-preparation path is not a directory")

    source_set = json.loads(source_manifest_path.read_bytes())
    if (
        source_set.get("complete") is not True
        or source_set.get("schemaVersion") != "issue-312-source-set/v1"
        or source_set.get("plan", {}).get("timeline", {}).get("rate") != wire(RATE)
        or len(source_set.get("sources", [])) != 24
    ):
        raise ValueError(
            "saved source set is not the complete 24 fps representative fixture"
        )
    sources = source_set["sources"]
    if len({source["id"] for source in sources}) != 24:
        raise ValueError("saved source set contains duplicate source identities")
    source_root_paths = {}
    for source in sources:
        if source.get("rate") != wire(RATE):
            raise ValueError("saved source metadata is not exact 24 fps")
        path = root / "video-sources" / source["file"]
        _plain(path)
        if not path.is_file() or _file_hash(path) != source.get("sha256"):
            raise ValueError(f"saved source bytes changed: {source['id']}")
        source_root_paths[source["id"]] = path

    speech = json.loads(speech_path.read_bytes())
    if speech.get("alignmentHash") != _file_hash(alignment_path):
        raise ValueError("saved speech rows do not use the supplied measured alignment")
    rows = [row for row in speech["rows"] if row.get("alternate") is not True]
    document, deps = (
        json.loads(script_path.read_bytes()),
        json.loads(deps_path.read_bytes()),
    )
    if (
        document.get("schemaVersion") != "script-document/v2"
        or len(document.get("activeDraft", {}).get("blocks", [])) != 30
        or deps.get("schemaVersion") != "compiler-dependencies/v2"
        or len(rows) != 30
    ):
        raise ValueError("saved script and speech rows do not contain 30 rows")
    expected_maps, audio_paths = _timing_inputs(speech_path)
    if canonical_json_bytes(expected_maps) != canonical_json_bytes(
        deps.get("narrationTimingMaps")
    ):
        raise ValueError(
            "saved narration timing maps differ from measured cache assets"
        )
    if document.get("liveContentHash") != _compiler_hash(
        {key: value for key, value in document.items() if key != "liveContentHash"}
    ):
        raise ValueError("saved script content hash is stale")

    descriptors = deps.get("occurrenceResolutions")
    if not isinstance(descriptors, list) or not descriptors:
        raise ValueError("saved visual occurrence mappings are missing")
    source_by_ref = {_id(source["id"]): source for source in sources}
    descriptor_by_payload = {
        descriptor["payloadId"]: descriptor for descriptor in descriptors
    }
    tools = MediaTools()
    tool_hash = identity_hash(tools.fingerprint())
    initial = invoke_bridge("needs", script_path, deps_path).needs["requirements"]
    unique: dict[str, tuple[Json, Json, Path]] = {}
    for need in initial:
        descriptor = descriptor_by_payload[need["payloadId"]]
        if need["sourceSufficiency"] != "sufficient":
            raise ValueError(
                "saved source does not cover the compiler's requested range"
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
    prepared, preparation_paths = {}, {}
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
        prepared[key], preparation_paths[key] = item, item.receipt_path

    # Publish the CLI-ready inputs in a fresh directory so the original
    # generated document and first-pass dependencies remain byte-identical.
    ready = root / "prepared-inputs"
    ready.mkdir(exist_ok=False)
    ready_script, ready_deps = (
        ready / "script.json",
        ready / "compiler-dependencies.json",
    )
    ready_script.write_bytes(script_path.read_bytes())
    deps["preparedMedia"] = [item.binding for item in prepared.values()]
    _write(ready_deps, deps)
    needs = invoke_bridge("needs", ready_script, ready_deps).needs
    if {row["requirementKey"] for row in needs["requirements"]} != set(prepared):
        raise ValueError("prepared media keys differ from compiler requirements")
    _write(ready / "media-needs.json", needs)
    _write(
        ready / "preparation-paths.json",
        {key: str(path) for key, path in preparation_paths.items()},
    )

    compiled = invoke_bridge("compile", ready_script, ready_deps).result
    manifest_path, report_path = (
        ready / "preflight-manifest.json",
        ready / "preflight-report.json",
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
        ready / "media-paths.json",
        {key: str(path) for key, path in media_paths.items()},
    )
    package_root = ready / "preflight-package"
    package = build_v2_package(
        manifest_path,
        report_path,
        ready_script,
        ready_deps,
        package_root,
        media_paths=media_paths,
        preparation_paths=preparation_paths,
    )
    checked = verify_v2_package(package_root)
    if checked.build_id != package.build_id:
        raise ValueError("preflight package identity differs after verification")
    timeline = compiled["manifest"]["timeline"]
    _write(
        root / "fixture.json",
        {
            "schemaVersion": "issue-520-long-fixture/v1",
            "timelineRate": wire(RATE),
            "durationFrames": timeline["durationFrames"],
            "durationSeconds": float(Fraction(timeline["durationFrames"], 24)),
            "rows": len(rows),
            "events": len(compiled["manifest"]["events"]),
            "sources": len(sources),
            "requirements": len(prepared),
            "inputDirectory": str(ready),
            "package": str(package_root),
            "buildId": package.build_id,
            "alignment": str(alignment_path),
            "alignmentHash": _file_hash(alignment_path),
            "sourceSet": str(source_manifest_path),
            "speechRows": str(speech_path),
        },
    )
    return root / "fixture.json"


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
    maps, _ = _timing_inputs(speech_path)
    document, descriptors = _document(plan, rows, sources, inspections)
    deps = _dependencies(document, rows, maps)
    deps["occurrenceResolutions"] = descriptors
    _write(root / "script.json", document)
    _write(root / "compiler-dependencies.json", deps)
    return _complete_fixture(root, source_root, alignment_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--alignment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-seconds", type=int, default=30)
    parser.add_argument(
        "--resume", action="store_true", help="finish a saved incomplete fixture"
    )
    args = parser.parse_args()
    if args.resume:
        print(_complete_fixture(args.output, args.source_root, args.alignment))
        return 0
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
