"""Prepare a disposable #586 still/music fixture for the normal v2 Build route.

This command only creates synthetic local media and frozen compiler inputs. It
does not import Resolve, create a project, build a timeline, or perform any
native write. Run the printed Build command separately when the fixture is
ready for the qualified Resolve check.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import shlex
import struct
import subprocess
import uuid
import wave
import zlib
from fractions import Fraction
from pathlib import Path
from typing import Any

from vera_timeline_agent.build_compiler_bridge import invoke_bridge
from vera_timeline_agent.media_preparation import (
    MediaTools,
    PreparationAuthorization,
    file_hash,
    wire,
)
from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.prep_media_inputs import prepare_still_media
from vera_timeline_agent.v2_package import _compiler_hash

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (
    ROOT / "tests/data/authoring_v2/issue_173/compiler/"
    "visual-only-image-still-25fps-default.input.golden.json"
)
RATE = Fraction(24, 1)
STILL_SIZE = (1600, 900)
MUSIC_SAMPLE_RATE = 48_000
MUSIC_SAMPLES = MUSIC_SAMPLE_RATE * 5
SOURCE_IN_FRAME = 24
SOURCE_OUT_FRAME = 120
ORIGINAL_TIMELINE_IN_FRAME = 12
EXPECTED_DURATION_FRAMES = SOURCE_OUT_FRAME - SOURCE_IN_FRAME
Json = dict[str, Any]


def _id(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"vera:issue586-native:{label}"))


def _write(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def _generate_png(path: Path) -> None:
    """Write one deterministic RGB8 frame with visible zoom witnesses."""
    width, height = STILL_SIZE
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            color = (170, 170, 170)
            if x < 48 and y < 48:
                color = (245, 24, 20)
            elif x >= width - 48 and y < 48:
                color = (20, 240, 25)
            elif x < 48 and y >= height - 48:
                color = (24, 35, 245)
            elif x >= width - 48 and y >= height - 48:
                color = (245, 240, 15)
            elif abs(x - int(width * 0.72)) < 20 and abs(y - int(height * 0.3)) < 20:
                color = (245, 25, 245)
            raw.extend(color)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(raw, 6))
        + _png_chunk(b"IEND", b"")
    )


def _generate_wav(path: Path) -> None:
    """Write a deterministic five-second, 48-kHz mono PCM16 source bed."""
    frames = bytearray()
    for index in range(MUSIC_SAMPLES):
        sample = int(9000 * math.sin(2 * math.pi * 220 * index / MUSIC_SAMPLE_RATE))
        frames.extend(struct.pack("<h", sample))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(MUSIC_SAMPLE_RATE)
        output.writeframes(frames)


def _refresh_document_binding(document: Json, dependencies: Json) -> None:
    document["liveContentHash"] = _compiler_hash(
        {key: value for key, value in document.items() if key != "liveContentHash"}
    )
    dependencies["document"].update(
        {
            "documentId": document["id"],
            "projectId": document["projectId"],
            "liveHeadSequence": document["liveHeadSequence"],
            "contentHash": document["liveContentHash"],
            "textHash": "sha256:" + hashlib.sha256(b"").hexdigest(),
            "settingsHash": dependencies["authoringDefaults"]["settingsHash"],
        }
    )


def _still_descriptor(
    run_id: str,
    block_id: str,
    payload_id: str,
    media_reference_id: str,
    still: Path,
) -> Json:
    source_hash = file_hash(still)
    source_probe = {
        "kind": "image",
        "demuxer": "image2pipe",
        "codec": "png",
        "width": STILL_SIZE[0],
        "height": STILL_SIZE[1],
        "frames": 1,
    }
    probe_hash = identity_hash(source_probe)
    snapshot = {
        "system": "local_import",
        "snapshotId": _id(f"snapshot:{run_id}"),
        "version": 1,
        "packageId": _id(f"package:{run_id}"),
        "contentHash": source_hash,
        "probeHash": probe_hash,
    }
    frame_map = {
        "packageFrameZeroLogicalFrame": 0,
        "packageVideoPtsOrigin": wire(Fraction(0)),
        "loggedTimeAtPackageFrameZero": wire(Fraction(0)),
        "decodedPackageFrameRate": wire(RATE),
        "decodedPackageFrameCount": 1,
        "packageVideoTimeBase": wire(Fraction(1, 24)),
        "sourceAudioStreamMappings": [],
        "descriptorHash": identity_hash({"snapshot": snapshot, "probe": source_probe}),
        "probeHash": probe_hash,
    }
    return {
        "payloadId": payload_id,
        "owner": {"kind": "visual_only_block", "blockId": block_id},
        "mediaReferenceId": media_reference_id,
        "sourceSnapshot": snapshot,
        "logicalSourceBounds": {
            "startFrame": 0,
            "endFrame": 1,
            "frameRate": wire(RATE),
        },
        "sourceFrameMap": frame_map,
        "occurrenceSourceInFrame": 0,
        "selectedSourceRange": None,
        "preparedMediaRequirementKey": None,
    }


def prepare(root: Path) -> Path:
    if root.exists() or root.is_symlink():
        raise ValueError("choose a new, unused fixture directory")
    root = root.absolute()
    media = root / "media"
    inputs = root / "inputs"
    preparation = root / "preparation"
    media.mkdir(parents=True)
    inputs.mkdir()

    still = media / "issue586-default-zoom.png"
    music = media / "issue586-trim-source.wav"
    _generate_png(still)
    _generate_wav(music)
    run_id = uuid.uuid4().hex[:12]
    template = json.loads(TEMPLATE.read_bytes())
    document = copy.deepcopy(template["document"])
    dependencies = copy.deepcopy(template["dependencies"])
    block = copy.deepcopy(document["activeDraft"]["blocks"][0])
    block_id = _id(f"block:{run_id}")
    payload_id = _id(f"payload:{run_id}")
    still_reference_id = _id(f"still-reference:{run_id}")
    music_reference_id = _id(f"music-reference:{run_id}")
    cue_id = _id(f"cue:{run_id}")
    block.update(id=block_id, orderKey="a0")
    block["payload"].update(
        payloadId=payload_id,
        source={"kind": "media_reference", "mediaReferenceId": still_reference_id},
        audioPolicy="mute",
    )
    # Omitted framingPolicy is the qualified ordinary-image default-zoom route.
    block["payload"].pop("framingPolicy", None)
    block["visualOnlyTiming"] = {
        "kind": "visual_only",
        "matchAudioDuration": {"cueId": cue_id},
    }
    document.update(
        id=_id(f"document:{run_id}"),
        projectId=_id(f"project:{run_id}"),
        title=f"Issue 586 matched still {run_id}",
    )
    document["activeDraft"]["blocks"] = [block]
    music_hash = file_hash(music)
    span = {
        "id": cue_id,
        "startRowId": block_id,
        "endRowId": block_id,
        "source": {
            "mediaReferenceId": music_reference_id,
            "artifactId": _id(f"music-artifact:{run_id}"),
            "artifactVersion": 1,
            "contentHash": music_hash,
        },
        "settings": {"gainDb": -12},
        # #574 fixed source endpoints + one timeline pin derive timelineOut.
        "timing": {
            "sourceInFrame": SOURCE_IN_FRAME,
            "sourceOutFrame": SOURCE_OUT_FRAME,
            "timelineIn": {"kind": "frame", "frame": ORIGINAL_TIMELINE_IN_FRAME},
        },
    }
    document["rowAudioSpans"] = [span]
    dependencies["build"] = {
        "buildId": _id(f"build:{run_id}"),
        "manifestId": _id(f"manifest:{run_id}"),
        "reportId": _id(f"report:{run_id}"),
        "buildClass": "preview",
    }
    dependencies["timeline"].update(
        frameRate=wire(RATE), durationFrames=EXPECTED_DURATION_FRAMES
    )
    dependencies["authoringDefaults"]["visualOnlyStillDurationMs"] = 4000
    dependencies["tracks"].append(
        {"id": "music-a5", "kind": "audio", "index": 5, "name": "A5 Music"}
    )
    dependencies["roles"]["musicTrackId"] = "music-a5"
    dependencies["occurrenceResolutions"] = [
        _still_descriptor(run_id, block_id, payload_id, still_reference_id, still)
    ]
    dependencies["preparedMedia"] = []
    dependencies["musicBindings"] = [
        {
            "spanId": cue_id,
            "source": span["source"],
            "displayFilename": music.name,
            "status": "ready",
            "sampleRate": MUSIC_SAMPLE_RATE,
            "channels": 1,
            "durationSamples": MUSIC_SAMPLES,
        }
    ]
    _refresh_document_binding(document, dependencies)
    script_path = inputs / "script-document.json"
    dependencies_path = inputs / "compiler-dependencies.json"
    _write(script_path, document)
    _write(dependencies_path, dependencies)

    needs = invoke_bridge("needs", script_path, dependencies_path).needs
    requirements = needs.get("requirements")
    if not isinstance(requirements, list) or len(requirements) != 1:
        raise ValueError(f"expected one still media requirement, got {requirements!r}")
    need = requirements[0]
    if (
        need.get("payloadId") != payload_id
        or need.get("sourceSufficiency") != "sufficient"
    ):
        raise ValueError(f"still media requirement is not sufficient: {need!r}")

    tools = MediaTools()
    authorization = PreparationAuthorization(
        reference=f"issue586-generated-{run_id}",
        read_roots=(media,),
        write_root=preparation,
        tool_hash=identity_hash(tools.fingerprint()),
    )
    prepared = prepare_still_media(
        still,
        dependencies["occurrenceResolutions"][0],
        need["requestedRange"],
        wire(RATE),
        authorization=authorization,
        tools=tools,
    )
    descriptor = dependencies["occurrenceResolutions"][0]
    descriptor["preparedMediaRequirementKey"] = prepared.binding["requirementKey"]
    dependencies["preparedMedia"] = [prepared.binding]
    _refresh_document_binding(document, dependencies)
    _write(script_path, document)
    _write(dependencies_path, dependencies)

    compiled = invoke_bridge("compile", script_path, dependencies_path).result
    manifest = compiled["manifest"]
    if (
        manifest["timeline"]["frameRate"] != wire(RATE)
        or manifest["timeline"]["durationFrames"] != EXPECTED_DURATION_FRAMES
    ):
        raise ValueError("compiled timeline does not retain the 24fps matched duration")
    still_events = [
        event
        for event in manifest["events"]
        if event["kind"] == "primary_visual"
        and event["provenance"]["payloadId"] == payload_id
    ]
    music_events = [event for event in manifest["events"] if event["kind"] == "music"]
    if len(still_events) != 1 or len(music_events) != 1:
        raise ValueError(
            "compiler did not emit exactly one matched still and music event"
        )
    if still_events[0]["recordRange"] != music_events[0]["recordRange"]:
        raise ValueError("matched still and music event ranges differ")
    media_paths: dict[str, str] = {}
    preparation_paths = {prepared.binding["requirementKey"]: str(prepared.receipt_path)}
    for source in manifest["sources"]:
        source_id = source["id"]
        if "musicAudio" in source:
            # The normal package route expands the event locator into these
            # source keys; mapping them here would duplicate that ownership.
            continue
        elif (
            source.get("preparationRequirementKey")
            == prepared.binding["requirementKey"]
        ):
            media_paths[f"source:{source_id}"] = str(still)
            media_paths[f"original:{source_id}"] = str(still)
    music_event_id = music_events[0]["eventId"]
    media_paths[f"event:{music_event_id}"] = str(music)
    _write(inputs / "media-paths.json", media_paths)
    _write(inputs / "preparation-paths.json", preparation_paths)
    _write(inputs / "expected-manifest.json", manifest)
    _write(
        root / "fixture.json",
        {
            "schemaVersion": "issue586-normal-build-fixture/v1",
            "projectTitle": document["title"],
            "timeline": {
                "width": 1920,
                "height": 1080,
                "frameRate": wire(RATE),
                "durationFrames": EXPECTED_DURATION_FRAMES,
            },
            "still": {
                "path": str(still),
                "sha256": file_hash(still),
                "width": STILL_SIZE[0],
                "height": STILL_SIZE[1],
                "defaultZoom": True,
            },
            "music": {
                "path": str(music),
                "sha256": music_hash,
                "sampleRate": MUSIC_SAMPLE_RATE,
                "channels": 1,
                "durationSamples": MUSIC_SAMPLES,
                "sourceInFrame": SOURCE_IN_FRAME,
                "sourceOutFrame": SOURCE_OUT_FRAME,
                "originalTimelineInFrame": ORIGINAL_TIMELINE_IN_FRAME,
                "expectedFrames": EXPECTED_DURATION_FRAMES,
            },
            "match": {
                "cueId": cue_id,
                "payloadId": payload_id,
                "stillAndMusicRecordRange": still_events[0]["recordRange"],
            },
            "offlineCompilerProof": {
                "manifest": str(inputs / "expected-manifest.json"),
                "report": compiled["report"],
            },
            "normalBuildCommand": (
                "ctx-wire run uv run --frozen python -m "
                "vera_timeline_agent.build_timeline_cli "
                f"--script {shlex.quote(str(script_path))} "
                f"--inputs {shlex.quote(str(inputs))} "
                f"--output {shlex.quote(str(root / 'built'))}"
            ),
        },
    )
    return root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="new disposable fixture directory")
    args = parser.parse_args()
    try:
        root = prepare(args.root)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.error(f"fixture preparation failed: {error}")
    print(f"Prepared offline issue #586 normal-build fixture at {root}")
    print(
        "Run with the project-pinned Node on PATH: "
        "ctx-wire run uv run --frozen python -m "
        "vera_timeline_agent.build_timeline_cli "
        f"--script {shlex.quote(str(root / 'inputs/script-document.json'))} "
        f"--inputs {shlex.quote(str(root / 'inputs'))} "
        f"--output {shlex.quote(str(root / 'built'))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
