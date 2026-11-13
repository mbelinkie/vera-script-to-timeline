"""Prepare the same two synthetic rows and compile each script variant offline."""

import argparse
import copy
import json
import subprocess
import uuid
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
from vera_timeline_agent.narration.models import identity_hash

from scripts.issue326_prepare_music_probe import (
    INPUT_TEMPLATE,
    _refresh_bindings,
    _row_audio,
    _write_pcm_wav,
)

RATE = {"numerator": 24, "denominator": 1}
SOURCE_IN = 24
VARIANTS = {
    "original": (("A", "B"), "B", 96),
    "same": (("A", "B"), "C", 96),
    "longer": (("A", "B"), "B", 144),
    "swap": (("B", "A"), "B", 96),
}


def uid(run: str, label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"vera:327:{run}:{label}"))


def write(path: Path, value: object) -> None:
    with path.open("x") as output:
        json.dump(value, output, indent=2, default=str)


def prepare(root: Path) -> None:
    root.mkdir()
    media = root / "media"
    media.mkdir()
    run = f"VERA-327-{uuid.uuid4().hex[:8]}"
    tools = MediaTools()
    authorization = PreparationAuthorization(
        reference=run,
        read_roots=(media,),
        write_root=root / "preparation",
        tool_hash=identity_hash(tools.fingerprint()),
    )
    descriptors = {}
    for name, hue in (("A", 0), ("B", 80), ("C", 165), ("Spare", 240)):
        picture = media / f"{name}.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=640x360:rate=24",
                "-vf",
                f"hue=h={hue}",
                "-frames:v",
                "24" if name == "Spare" else "192",
                "-c:v",
                "libx264",
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
                "-threads",
                "2",
                str(picture),
            ],
            check=True,
            timeout=60,
        )
        if name == "Spare":
            continue
        probe = inspect_media(
            picture, video_stream_index=0, audio_stream_index=None, tools=tools
        )
        descriptors[name] = {
            "mediaReferenceId": uid(run, f"media-{name}"),
            "sourceSnapshot": {
                "system": "local_import",
                "snapshotId": uid(run, f"snapshot-{name}"),
                "version": 1,
                "packageId": uid(run, f"package-{name}"),
                "contentHash": probe.content_hash,
                "probeHash": probe.probe_hash,
            },
            "logicalSourceBounds": {
                "startFrame": 0,
                "endFrame": 192,
                "frameRate": RATE,
            },
            "sourceFrameMap": {
                "packageFrameZeroLogicalFrame": 0,
                "packageVideoPtsOrigin": wire(probe.pts_origin),
                "loggedTimeAtPackageFrameZero": wire(probe.pts_origin),
                "decodedPackageFrameRate": RATE,
                "decodedPackageFrameCount": 192,
                "packageVideoTimeBase": wire(probe.time_base),
                "sourceAudioStreamMappings": [],
                "descriptorHash": probe.probe_hash,
                "probeHash": probe.probe_hash,
            },
            "occurrenceSourceInFrame": SOURCE_IN,
            "selectedSourceRange": None,
            "preparedMediaRequirementKey": None,
        }

    for label, frames, hz in (("A", 96, 220), ("B", 96, 330), ("B", 144, 330)):
        _write_pcm_wav(media / f"{label}-{frames}.wav", [(hz, frames * 2000)], 0.12)

    template = json.loads(INPUT_TEMPLATE.read_bytes())
    for revision, (variant, (order, second_picture, second_length)) in enumerate(
        VARIANTS.items(), start=1
    ):
        inputs = root / variant
        inputs.mkdir()
        document = copy.deepcopy(template["document"])
        document.update(
            id=uid(run, "document"), projectId=uid(run, "project"), title=run
        )
        dependencies = copy.deepcopy(template["dependencies"])
        dependencies["build"] = {
            "buildId": uid(run, f"{variant}-build"),
            "manifestId": uid(run, f"{variant}-manifest"),
            "reportId": uid(run, f"{variant}-report"),
            "buildClass": "preview",
        }
        dependencies["document"]["revision"] = revision
        dependencies["timeline"].update(
            frameRate=RATE, durationFrames=96 + second_length, width=640, height=360
        )
        dependencies.update(
            narrationTimingMaps=[], occurrenceResolutions=[], preparedMedia=[]
        )
        blocks = document["activeDraft"]["blocks"]
        blocks.clear()
        media_paths: dict[str, Path] = {}
        originals = {}
        for index, label in enumerate(order):
            frames = 96 if label == "A" else second_length
            name = "A" if label == "A" else second_picture
            tone = media / f"{label}-{frames}.wav"
            info = _row_audio(run, label, uid(run, f"row-{label}"), label, tone, frames)
            row, timing = info["row"], info["timing"]
            row["orderKey"] = f"a{index}"
            sequence = row["primaryVisualSequence"]
            slot = sequence["slots"][0]
            descriptor = copy.deepcopy(descriptors[name])
            descriptor.update(
                payloadId=slot["payload"]["payloadId"],
                owner={
                    "kind": "primary_slot",
                    "sequenceId": sequence["id"],
                    "slotId": slot["id"],
                },
            )
            slot["payload"].update(
                pictureKind="clip",
                source={
                    "kind": "media_reference",
                    "mediaReferenceId": descriptor["mediaReferenceId"],
                },
                sourceUsage={"sourceInFrame": SOURCE_IN},
            )
            blocks.append(row)
            dependencies["narrationTimingMaps"].append(timing)
            dependencies["occurrenceResolutions"].append(descriptor)
            media_paths[f"source:{info['assetId']}"] = tone
            originals[descriptor["mediaReferenceId"]] = media / f"{name}.mp4"
        _refresh_bindings(document, dependencies)
        script = inputs / "script-document.json"
        deps = inputs / "compiler-dependencies.json"
        unprepared = inputs / "unprepared.json"
        write(script, document)
        write(unprepared, dependencies)
        needs = invoke_bridge("needs", script, unprepared).needs
        prepared: dict[str, Any] = {}
        for request in needs["requirements"]:
            descriptor = next(
                item
                for item in dependencies["occurrenceResolutions"]
                if item["payloadId"] == request["payloadId"]
            )
            result = prepare_media(
                originals[request["mediaReferenceId"]],
                descriptor,
                request["requestedRange"],
                RATE,
                authorization=authorization,
                video_stream_index=0,
                audio_stream_index=None,
                tools=tools,
            )
            key = result.binding["requirementKey"]
            descriptor["preparedMediaRequirementKey"] = key
            dependencies["preparedMedia"].append(result.binding)
            prepared[key] = result
        write(deps, dependencies)
        compiled = invoke_bridge("compile", script, deps).result
        if not compiled["ok"]:
            raise ValueError(compiled)
        manifest = compiled["manifest"]
        for source in manifest["sources"]:
            if key := source.get("preparationRequirementKey"):
                media_paths[f"source:{source['id']}"] = prepared[key].video_path
                media_paths[f"original:{source['id']}"] = originals[
                    source["mediaReferenceId"]
                ]
        write(inputs / "media-paths.json", media_paths)
        write(
            inputs / "preparation-paths.json",
            {key: item.receipt_path for key, item in prepared.items()},
        )
        write(inputs / "expected-manifest.json", manifest)
        print(f"{variant}: {manifest['timeline']['durationFrames']} frames")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    prepare(parser.parse_args().root.resolve())
