"""Prepare generated letterbox/pillarbox clips for the normal v2 Studio build.

This is an offline fixture builder. It never imports Resolve or performs a
native operation. The resulting inputs are consumed by build_timeline_cli.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any

from vera_timeline_agent.build_compiler_bridge import invoke_bridge
from vera_timeline_agent.media_preparation import (
    MediaTools,
    PreparationAuthorization,
    inspect_media,
    prepare_media,
    wire,
)
from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.v2_package import _compiler_hash

ROOT = Path(__file__).resolve().parents[1]
NODE_BIN = (
    "/Users/matthewbelinkie/.local/share/vera/toolchains/node-v24.19.0-darwin-x64/bin"
)
TEMPLATE = ROOT / (
    "tests/data/authoring_v2/issue_173/compiler/selected-clip-ntsc.input.golden.json"
)
RATE = Fraction(24, 1)
FRAME_COUNT = 72
CLIPS = {
    "letterbox": "testsrc2=size=320x140:rate=24:duration=3,pad=320:180:0:20:black",
    "pillarbox": "testsrc2=size=272x180:rate=24:duration=3,pad=320:180:24:0:black",
}
CONTROLS = {
    "near-black": "color=c=0x101010:s=320x180:r=24:d=3",
    "changing": (
        "testsrc2=size=320x140:rate=24:duration=1.5,pad=320:180:0:20:black[a];"
        "testsrc2=size=320x180:rate=24:duration=1.5[b];[a][b]concat=n=2:v=1:a=0"
    ),
    "ambiguous": (
        "color=c=0x080808:s=320x180:r=24:d=3,"
        "drawbox=x=120:y=60:w=80:h=60:color=white:t=fill"
    ),
    "override": CLIPS["letterbox"],
}
Json = dict[str, Any]


def _id(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"vera:issue600-native:{label}"))


def _write(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def _refresh_document_binding(document: Json, dependencies: Json) -> None:
    document["liveContentHash"] = _compiler_hash(
        {key: value for key, value in document.items() if key != "liveContentHash"}
    )
    text_hash = "sha256:" + hashlib.sha256(b"").hexdigest()
    dependencies["document"].update(
        {
            "documentId": document["id"],
            "projectId": document["projectId"],
            "liveHeadSequence": document["liveHeadSequence"],
            "contentHash": document["liveContentHash"],
            "textHash": text_hash,
            "settingsHash": dependencies["authoringDefaults"]["settingsHash"],
        }
    )


def _generate_clip(path: Path, graph: str) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-n",
            "-f",
            "lavfi",
            "-i",
            graph,
            "-frames:v",
            str(FRAME_COUNT),
            "-an",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            "-color_range",
            "tv",
            "-colorspace",
            "bt709",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-x264-params",
            "colorprim=bt709:transfer=bt709:colormatrix=bt709",
            "-r",
            "24",
            "-movflags",
            "+faststart",
            str(path),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )


def prepare(
    root: Path, *, hide_encoded_bars: bool = False, controls: bool = False
) -> Path:
    if root.exists() or root.is_symlink():
        raise ValueError("choose a new, unused fixture directory")
    root = root.absolute()
    media = root / "media"
    inputs = root / "inputs"
    media.mkdir(parents=True)
    inputs.mkdir()

    tools = MediaTools()
    tool_hash = identity_hash(tools.fingerprint())
    authorization = PreparationAuthorization(
        reference=f"issue600-generated-{uuid.uuid4().hex[:12]}",
        read_roots=(media,),
        write_root=root / "preparation",
        tool_hash=tool_hash,
    )
    original_paths: dict[str, Path] = {}
    inspections = {}
    clips = {**CLIPS, **CONTROLS} if controls else CLIPS
    for name, graph in clips.items():
        path = media / f"issue600-{name}.mp4"
        _generate_clip(path, graph)
        inspection = inspect_media(
            path, video_stream_index=0, audio_stream_index=None, tools=tools
        )
        if (
            inspection.rate != RATE
            or len(inspection.video_frames) != FRAME_COUNT
            or inspection.video["width"] != 320
            or inspection.video["height"] != 180
            or inspection.audio is not None
        ):
            raise ValueError(f"generated {name} fixture failed media inspection")
        original_paths[name] = path
        inspections[name] = inspection

    source_template = json.loads(TEMPLATE.read_bytes())
    document = copy.deepcopy(source_template["document"])
    dependencies = copy.deepcopy(source_template["dependencies"])
    if hide_encoded_bars:
        dependencies["authoringDefaults"]["hideEncodedBars"] = True
    run_id = uuid.uuid4().hex[:12]
    document.update(
        id=_id(f"document:{run_id}"),
        projectId=_id(f"project:{run_id}"),
        title=f"Issue 600 generated bars {run_id}",
    )
    dependencies["build"] = {
        "buildId": _id(f"build:{run_id}"),
        "manifestId": _id(f"manifest:{run_id}"),
        "reportId": _id(f"report:{run_id}"),
        "buildClass": "preview",
    }
    dependencies["timeline"].update(
        frameRate=wire(RATE), durationFrames=FRAME_COUNT * len(clips)
    )
    blocks = []
    occurrence_templates = []
    for index, name in enumerate(clips):
        block = copy.deepcopy(source_template["document"]["activeDraft"]["blocks"][0])
        block_id = _id(f"block:{run_id}:{name}")
        payload_id = _id(f"payload:{run_id}:{name}")
        reference_id = _id(f"reference:{run_id}:{name}")
        block.update(id=block_id, orderKey=f"a{index}")
        block["payload"].update(
            payloadId=payload_id,
            audioPolicy="mute",
            source={"kind": "media_reference", "mediaReferenceId": reference_id},
        )
        block["payload"].pop("framingPolicy", None)
        if name == "override":
            block["payload"]["framingPolicy"] = "contain"
        block["visualOnlyTiming"]["selectedSourceRange"] = {
            "startFrame": 0,
            "durationFrames": FRAME_COUNT,
        }

        original = inspections[name]
        occurrence = copy.deepcopy(
            source_template["dependencies"]["occurrenceResolutions"][0]
        )
        occurrence.update(
            payloadId=payload_id,
            owner={"kind": "visual_only_block", "blockId": block_id},
            mediaReferenceId=reference_id,
            sourceSnapshot={
                "system": "local_import",
                "snapshotId": _id(f"snapshot:{run_id}:{name}"),
                "version": 1,
                "packageId": _id(f"package:{run_id}:{name}"),
                "contentHash": original.content_hash,
                "probeHash": original.probe_hash,
            },
            logicalSourceBounds={
                "startFrame": 0,
                "endFrame": FRAME_COUNT,
                "frameRate": wire(RATE),
            },
            sourceFrameMap={
                "packageFrameZeroLogicalFrame": 0,
                "packageVideoPtsOrigin": wire(original.pts_origin),
                "loggedTimeAtPackageFrameZero": wire(original.pts_origin),
                "decodedPackageFrameRate": wire(RATE),
                "decodedPackageFrameCount": FRAME_COUNT,
                "packageVideoTimeBase": wire(original.time_base),
                "sourceAudioStreamMappings": [],
                "descriptorHash": original.probe_hash,
                "probeHash": original.probe_hash,
            },
            occurrenceSourceInFrame=0,
            selectedSourceRange={"startFrame": 0, "endFrame": FRAME_COUNT},
            preparedMediaRequirementKey=None,
        )
        occurrence_templates.append((name, occurrence))
        blocks.append(block)

    document["activeDraft"]["blocks"] = blocks
    dependencies["occurrenceResolutions"] = [item for _, item in occurrence_templates]
    dependencies["preparedMedia"] = []
    _refresh_document_binding(document, dependencies)
    script_path = inputs / "script-document.json"
    dependencies_path = inputs / "compiler-dependencies.json"
    needs_dependencies_path = inputs / "unprepared-compiler-dependencies.json"
    _write(script_path, document)
    _write(needs_dependencies_path, dependencies)
    needs = invoke_bridge("needs", script_path, needs_dependencies_path).needs

    prepared: dict[str, Any] = {}
    for request in needs["requirements"]:
        name, occurrence = next(
            (name, item)
            for name, item in occurrence_templates
            if item["payloadId"] == request["payloadId"]
        )
        result = prepare_media(
            original_paths[name],
            occurrence,
            request["requestedRange"],
            wire(RATE),
            authorization=authorization,
            video_stream_index=0,
            audio_stream_index=None,
            tools=tools,
        )
        occurrence["preparedMediaRequirementKey"] = result.binding["requirementKey"]
        dependencies["preparedMedia"].append(result.binding)
        prepared[result.binding["requirementKey"]] = result

    _refresh_document_binding(document, dependencies)
    _write(script_path, document)
    _write(dependencies_path, dependencies)
    compiled = invoke_bridge("compile", script_path, dependencies_path).result
    if not compiled.get("ok"):
        raise ValueError(f"generated v2 build inputs did not compile: {compiled}")

    media_paths: dict[str, str] = {}
    preparation_paths: dict[str, str] = {}
    for source in compiled["manifest"]["sources"]:
        key = source.get("preparationRequirementKey")
        if key:
            result = prepared[key]
            media_paths[f"source:{source['id']}"] = str(result.video_path)
            media_paths[f"original:{source['id']}"] = str(
                original_paths[
                    next(
                        name
                        for name, occurrence in occurrence_templates
                        if occurrence["mediaReferenceId"] == source["mediaReferenceId"]
                    )
                ]
            )
            preparation_paths[key] = str(result.receipt_path)
    _write(inputs / "media-paths.json", media_paths)
    _write(inputs / "preparation-paths.json", preparation_paths)
    _write(inputs / "expected-manifest.json", compiled["manifest"])
    _write(
        root / "fixture.json",
        {
            "schemaVersion": "issue600-normal-build-fixture/v1",
            "projectTitle": document["title"],
            "timeline": {"width": 1920, "height": 1080, "frameRate": wire(RATE)},
            "clips": [
                {
                    "name": name,
                    "path": str(original_paths[name]),
                    "sha256": inspections[name].content_hash,
                    "usedFrames": FRAME_COUNT,
                    "expectedActiveRect": (
                        {"x": 0, "y": 20, "width": 320, "height": 140}
                        if name == "letterbox"
                        else {"x": 24, "y": 0, "width": 272, "height": 180}
                        if name == "pillarbox"
                        else None
                    ),
                }
                for name in clips
            ],
            "normalBuildCommand": (
                f'PATH="{NODE_BIN}:$PATH" ctx-wire run uv run --frozen python -m '
                f"vera_timeline_agent.build_timeline_cli --script {script_path} "
                f"--inputs {inputs} --output {root / 'built'}"
            ),
        },
    )
    return root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="new disposable fixture directory")
    parser.add_argument("--hide-encoded-bars", action="store_true")
    parser.add_argument("--controls", action="store_true")
    args = parser.parse_args()
    try:
        root = prepare(
            args.root, hide_encoded_bars=args.hide_encoded_bars, controls=args.controls
        )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.error(f"fixture preparation failed: {error}")
    print(f"Prepared offline issue #600 normal-build fixture at {root}")
    print(
        f'Run: PATH="{NODE_BIN}:$PATH" ctx-wire run '
        "uv run --frozen python -m vera_timeline_agent.build_timeline_cli "
        f"--script {root / 'inputs/script-document.json'} "
        f"--inputs {root / 'inputs'} --output {root / 'built'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
