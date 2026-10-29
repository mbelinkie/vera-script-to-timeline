"""Compose #312 public inputs through the existing compiler/preparation/package.

This is fixture setup, not a timed benchmark or native execution entry point.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import subprocess
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from .generated.contracts.compiler_dependencies_v2_schema import RationalRate
from .issue312_fixture import RATE
from .media_preparation import (
    MediaTools,
    PreparationAuthorization,
    inspect_media,
    prepare_media,
    wire,
)
from .narration.models import canonical_json_bytes, identity_hash
from .performance_v2 import increment, recording_context, span
from .qualification_output_package_v2 import MATRIX_PREPARATION_ROOT
from .v2_package import _compiler_hash, _file_hash, _render_slate, build_v2_package

ROOT = Path(__file__).resolve().parents[2]
NODE = Path(
    "/Users/matthewbelinkie/.local/share/vera/toolchains/node-v24.19.0-darwin-x64/bin/node"
)
Json = dict[str, Any]


class CountingMediaTools(MediaTools):
    """Observe existing tool dispatches without changing the qualified adapter."""

    def run(self, command: list[str], *, timeout: float = 600) -> bytes:
        increment("subprocess.calls")
        probe = Path(command[0]).name == "ffprobe"
        if probe:
            increment("probe.calls")
        with span("preparation.probe" if probe else "preparation.process"):
            return super().run(command, timeout=timeout)


def _write(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def _id(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "vera:issue312:" + label))


def _compile(document: Path, dependencies: Path) -> Json:
    with span("forward.compile_media_needs"):
        increment("subprocess.calls")
        result = subprocess.run(
            [
                str(NODE),
                str(ROOT / "packages/contracts/src/issue-190-compile-cli.ts"),
                str(document),
                str(dependencies),
            ],
            capture_output=True,
            check=False,
            timeout=120,
            env={
                **os.environ,
                "PATH": str(NODE.parent) + os.pathsep + os.environ["PATH"],
            },
        )
        if result.returncode not in {0, 1} or not result.stdout:
            raise ValueError(
                "pinned compiler process failed: " + result.stderr.decode()[:500]
            )
        value = json.loads(result.stdout)
        if not value["result"].get("ok") or not value["needs"].get("ok"):
            raise ValueError("compiler refused: " + result.stdout.decode()[:2000])
        return cast(Json, value)


def prepare_package(
    source_set_path: Path,
    speech_rows_path: Path,
    output_root: Path,
    *,
    preparation_root: Path | None = None,
) -> Path:
    sources = json.loads(source_set_path.read_bytes())
    speech = json.loads(speech_rows_path.read_bytes())
    if sources.get("complete") is not True:
        raise ValueError("complete verified source set required")
    plan = sources["plan"]
    rows = [row for row in speech["rows"] if not row["alternate"]]
    if len(rows) != plan["narrationRows"]:
        raise ValueError("narration density differs from source plan")
    root = output_root.absolute()
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise ValueError("symbolic-link fixture output refused")
    root.mkdir(parents=True, exist_ok=False)
    template = json.loads(
        (ROOT / "tests/data/authoring_v2/compiler-dependencies-v2.json").read_bytes()
    )
    document: Json = {
        "schemaVersion": "script-document/v2",
        "id": _id("document"),
        "projectId": _id("project"),
        "title": "Public representative synthetic edit #312",
        "activeDraft": {"blocks": [], "supportingItems": []},
        "ideaOutline": [],
        "extras": [],
        "liveHeadSequence": 0,
        "liveStateVector": "",
        "liveContentHash": "",
    }
    deps = copy.deepcopy(template)
    for key in ("buildId", "manifestId", "reportId"):
        deps["build"][key] = str(uuid.uuid4())
    deps["compiler"]["sourceHash"] = _file_hash(
        ROOT / "packages/contracts/src/compiler-core-v2.ts"
    )
    deps["timeline"].update(
        frameRate=wire(RATE),
        durationFrames=sum(
            math.ceil(
                Fraction(row["evidence"]["audio"]["durationSamples"], 48000) * RATE
            )
            for row in rows
        ),
    )
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
    deps["narrationTimingMaps"], deps["preparedMedia"] = [], []
    deps["narrationBoundaryEvidence"] = [row["evidence"] for row in rows]
    deps["occurrenceResolutions"] = []
    source_by_id = {source["id"]: source for source in sources["sources"]}
    tools = CountingMediaTools()
    inspected: dict[str, Any] = {}
    occurrence_paths: dict[str, Path] = {}

    with recording_context() as recorder:
        with span("forward.source_inspection"):
            for sid, spec in source_by_id.items():
                path = (source_set_path.parent / spec["file"]).absolute()
                if _file_hash(path) != spec["sha256"]:
                    raise ValueError("generated source changed")
                inspected[sid] = inspect_media(
                    path, video_stream_index=0, audio_stream_index=None, tools=tools
                )

        def visual(item: Json, owner: Json) -> Json:
            if item.get("pictureKind") == "intentional_placeholder":
                return {
                    "kind": "visual",
                    "payloadId": _id(item["id"] + ":payload"),
                    "pictureKind": "intentional_placeholder",
                    "source": {
                        "kind": "intentional_placeholder",
                        "text": "Public synthetic held picture " + item["id"],
                    },
                    "sourceUsage": None,
                    "audioPolicy": "mute",
                    "framingPolicy": "contain",
                }
            sid = item["source"]
            inspection = inspected[sid]
            payload_id = _id(item["id"] + ":payload")
            rate = Fraction(source_by_id[sid]["rate"]["numerator"], 1001)
            frame_map = {
                "packageFrameZeroLogicalFrame": 0,
                "packageVideoPtsOrigin": wire(inspection.pts_origin),
                "loggedTimeAtPackageFrameZero": wire(Fraction(0)),
                "decodedPackageFrameRate": wire(rate),
                "decodedPackageFrameCount": len(inspection.video_frames),
                "packageVideoTimeBase": wire(inspection.time_base),
                "sourceAudioStreamMappings": [],
                "descriptorHash": inspection.probe_hash,
                "probeHash": inspection.probe_hash,
            }
            descriptor = {
                "payloadId": payload_id,
                "owner": owner,
                "mediaReferenceId": _id(sid),
                "sourceSnapshot": {
                    "system": "local_import",
                    "snapshotId": _id(sid + ":snapshot"),
                    "version": 1,
                    "packageId": _id(sid + ":package"),
                    "contentHash": inspection.content_hash,
                    "probeHash": inspection.probe_hash,
                },
                "logicalSourceBounds": {
                    "startFrame": 0,
                    "endFrame": len(inspection.video_frames),
                    "frameRate": wire(rate),
                },
                "sourceFrameMap": frame_map,
                "occurrenceSourceInFrame": item["sourceInFrame"],
                "selectedSourceRange": None,
                "preparedMediaRequirementKey": None,
            }
            deps["occurrenceResolutions"].append(descriptor)
            occurrence_paths[payload_id] = (
                source_set_path.parent / source_by_id[sid]["file"]
            ).absolute()
            return {
                "kind": "visual",
                "payloadId": payload_id,
                "pictureKind": "clip",
                "source": {"kind": "media_reference", "mediaReferenceId": _id(sid)},
                "sourceUsage": {"sourceInFrame": item["sourceInFrame"]},
                "audioPolicy": "mute",
                "framingPolicy": "contain",
            }

        for index, row in enumerate(rows):
            block = copy.deepcopy(row["block"])
            sequence_id = _id(f"row:{index}:sequence")
            block.update(
                orderKey=f"{index:03d}",
                state="active",
                notes=[],
                overlayEvents=[],
                timingPolicy="narration_spine",
            )
            slots: list[Json] = []
            for item in [p for p in plan["pictures"] if p["row"] == index]:
                slot_id = _id(item["id"] + ":slot")
                token = block["tokens"][item["start"].get("tokenIndex", 0)]
                boundary = (
                    {"kind": "row_start"}
                    if not slots
                    else {
                        "kind": "spoken_word",
                        "anchor": {
                            "blockId": block["id"],
                            "tokenId": token["id"],
                            "quotedWord": token["value"],
                            "anchorVersion": 1,
                            "affinity": "before",
                        },
                    }
                )
                slots.append(
                    {
                        "id": slot_id,
                        "kind": "content",
                        "version": 1,
                        "relation": {"kind": "base" if not slots else "sequential"},
                        "boundaryBefore": boundary,
                        "playoutPolicy": "match_structural_interval",
                        "payload": visual(
                            item,
                            {
                                "kind": "primary_slot",
                                "sequenceId": sequence_id,
                                "slotId": slot_id,
                            },
                        ),
                    }
                )
            block["primaryVisualSequence"] = {
                "id": sequence_id,
                "version": 1,
                "slots": slots,
            }
            for item in [p for p in plan["overlays"] if p["row"] == index]:
                event_id = _id(item["id"])
                token = block["tokens"][item["tokenIndex"]]
                block["overlayEvents"].append(
                    {
                        "id": event_id,
                        "version": 1,
                        "payload": visual(
                            item,
                            {
                                "kind": "overlay_event",
                                "blockId": block["id"],
                                "overlayEventId": event_id,
                            },
                        ),
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
            {k: v for k, v in document.items() if k != "liveContentHash"}
        )
        deps["document"].update(
            documentId=document["id"],
            projectId=document["projectId"],
            contentHash=document["liveContentHash"],
            textHash="sha256:"
            + hashlib.sha256(
                "\n".join(row["block"]["text"] for row in rows).encode()
            ).hexdigest(),
        )
        doc_path, deps_path = root / "document.json", root / "dependencies.json"
        _write(doc_path, document)
        _write(deps_path, deps)
        needs = _compile(doc_path, deps_path)["needs"]["requirements"]
        authorization = PreparationAuthorization(
            reference="issue312-public-synthetic-fixture",
            read_roots=(source_set_path.parent.absolute(),),
            write_root=(
                preparation_root.absolute()
                if preparation_root is not None
                else MATRIX_PREPARATION_ROOT / ("issue312-" + root.name)
            ),
            tool_hash=identity_hash(tools.fingerprint()),
        )
        preparations = {}
        prepared_by_inputs: dict[str, Any] = {}
        with span("forward.preparation"):
            for descriptor in deps["occurrenceResolutions"]:
                need = next(
                    n for n in needs if n["payloadId"] == descriptor["payloadId"]
                )
                preparation_inputs = identity_hash(
                    {
                        "mediaReferenceId": descriptor["mediaReferenceId"],
                        "sourceSnapshot": descriptor["sourceSnapshot"],
                        "sourceFrameMap": descriptor["sourceFrameMap"],
                        "videoStreamIndex": 0,
                        "audioStreamIndex": None,
                        "requestedRange": need["requestedRange"],
                        "targetRate": wire(RATE),
                    }
                )
                prepared = prepared_by_inputs.get(preparation_inputs)
                if prepared is None:
                    prepared = prepare_media(
                        occurrence_paths[descriptor["payloadId"]],
                        descriptor,
                        need["requestedRange"],
                        cast(RationalRate, wire(RATE)),
                        authorization=authorization,
                        video_stream_index=0,
                        audio_stream_index=None,
                        tools=tools,
                    )
                    prepared_by_inputs[preparation_inputs] = prepared
                requirement_key = prepared.binding["requirementKey"]
                descriptor["preparedMediaRequirementKey"] = requirement_key
                # Multiple occurrences may intentionally share one source,
                # range, and authenticated preparation requirement. Keep each
                # occurrence's reference, but publish one binding per key so
                # the compiler's dependency collection remains unique.
                if requirement_key not in preparations:
                    deps["preparedMedia"].append(prepared.binding)
                    preparations[requirement_key] = prepared
        _write(deps_path, deps)
        compiled = _compile(doc_path, deps_path)["result"]
        if compiled["report"]["status"] != "ready":
            raise ValueError("fixture is not ready: " + compiled["reportJson"][:2500])
        manifest_path, report_path = root / "manifest.json", root / "report.json"
        manifest_path.write_text(compiled["manifestJson"])
        report_path.write_text(compiled["reportJson"])
        media = {}
        by_payload = {d["payloadId"]: d for d in deps["occurrenceResolutions"]}
        for source in compiled["manifest"]["sources"]:
            sid = source["id"]
            if "narrationAudio" in source:
                row = next(r for r in rows if r["evidence"]["narrationAssetId"] == sid)
                media["source:" + sid] = (
                    speech_rows_path.parent / row["audioFile"]
                ).absolute()
            else:
                prepared = preparations[source["preparationRequirementKey"]]
                descriptor = next(
                    d
                    for d in by_payload.values()
                    if d["preparedMediaRequirementKey"]
                    == source["preparationRequirementKey"]
                )
                media["source:" + sid] = prepared.video_path
                media["original:" + sid] = occurrence_paths[descriptor["payloadId"]]
        actual_events = compiled["manifest"]["events"]
        for event in actual_events:
            if event["kind"] == "placeholder":
                slate_path = root / (event["eventId"] + ".png")
                slate_path.write_bytes(
                    _render_slate(
                        event["pictureTreatment"]["text"],
                        deps["timeline"]["width"],
                        deps["timeline"]["height"],
                    )
                )
                media["event:" + event["eventId"]] = slate_path
        if (
            len(actual_events) != plan["expectedEvents"]
            or sum(event["kind"] == "narration" for event in actual_events) != len(rows)
            or sum(
                event["kind"] in {"primary_visual", "placeholder"}
                for event in actual_events
            )
            != len(plan["pictures"])
            or sum(event["kind"] == "overlay_visual" for event in actual_events)
            != len(plan["overlays"])
        ):
            raise ValueError("compiled fixture density differs from declared plan")
        build_v2_package(
            manifest_path,
            report_path,
            doc_path,
            deps_path,
            root / "package",
            media_paths=media,
            preparation_paths={key: p.receipt_path for key, p in preparations.items()},
        )
    result_path = root / "fixture.json"
    _write(
        result_path,
        {
            "schemaVersion": "issue-312-prepared-fixture/v1",
            "package": str(root / "package"),
            "sourceSet": str(source_set_path.absolute()),
            "speechRows": str(speech_rows_path.absolute()),
            "preparations": {
                key: str(p.receipt_path) for key, p in preparations.items()
            },
            "performance": recorder.snapshot(),
            "expectedEvents": plan["expectedEvents"],
            "placementPlan": plan,
        },
    )
    return result_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-set", type=Path, required=True)
    parser.add_argument("--speech-rows", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preparation-root", type=Path)
    args = parser.parse_args()
    print(
        prepare_package(
            args.source_set,
            args.speech_rows,
            args.output,
            preparation_root=args.preparation_root,
        )
    )
