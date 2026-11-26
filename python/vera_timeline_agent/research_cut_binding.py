"""Materialize a Research cut and bind the decoded, file-local frame interval."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any

from .build_stage_receipt import hash_file
from .media_preparation import MediaInspection, MediaTools, inspect_media, wire

Json = dict[str, Any]


def cut_identity(snapshot: Json) -> Json:
    selection = snapshot["loggedSelection"]
    return {
        "schemaVersion": 1,
        "clipId": str(uuid.UUID(snapshot["clipId"])),
        "projectId": snapshot["researchProjectId"],
        "catalogVideoId": snapshot["catalogVideoId"],
        "sourceVideoId": snapshot["video"]["youtubeVideoId"],
        "selectionTrackId": selection["trackId"],
        "selectionTrackVersion": selection["transcriptVersion"],
        "exportStartMs": selection["exportStartMs"],
        "exportEndMs": selection["exportEndMs"],
    }


def verify_cut(folder: Path, snapshot: Json) -> tuple[Path, str]:
    """Verify the returned package against the frozen selection and actual bytes."""
    expected = cut_identity(snapshot)
    clip_id = expected["clipId"]
    manifest = folder / f"{clip_id}.json"
    if not manifest.is_file():
        raise ValueError("Research cut manifest is missing")
    hash_file(manifest)
    record = json.loads(manifest.read_bytes())
    if any(record.get(key) != value for key, value in expected.items()):
        raise ValueError(
            f"Research cut does not match the frozen clip selection: {folder}. "
            "Choose an export root containing the matching cut."
        )
    video_name = f"{clip_id}.mp4"
    video_hash = ""
    names: set[str] = set()
    for artifact in record["artifacts"]:
        name = artifact["name"]
        if (
            not isinstance(name, str)
            or name in names
            or (
                name != video_name
                and not re.fullmatch(
                    re.escape(clip_id) + r"\.[a-zA-Z0-9-]{2,35}\.srt", name
                )
            )
        ):
            raise ValueError("Unexpected Research cut artifact")
        names.add(name)
        path = folder / name
        digest = "sha256:" + hash_file(path)
        if (
            digest != f"sha256:{artifact['sha256']}"
            or path.stat().st_size != artifact["byteSize"]
        ):
            raise ValueError("Research cut artifact failed byte verification")
        if name == video_name:
            video_hash = digest
    if not video_hash or f"{clip_id}.en.srt" not in names:
        raise ValueError("Research cut is missing its video or English subtitle")
    if {item.name for item in folder.iterdir()} - {".DS_Store"} != names | {
        manifest.name
    }:
        raise ValueError("Unexpected files in Research cut package")
    return folder / video_name, video_hash


def copy_cut(folder: Path, snapshot: Json, clip_directory: Path) -> Path:
    """Copy then reverify before publishing, leaving the Research package untouched."""
    _, digest = verify_cut(folder, snapshot)
    artifact_id = digest.removeprefix("sha256:")
    destination = clip_directory / artifact_id
    if any(part.is_symlink() for part in (destination, *destination.parents)):
        raise ValueError("Research media destination cannot use symbolic links")
    if destination.exists():
        _, existing_hash = verify_cut(destination, snapshot)
        if existing_hash != digest:
            raise ValueError("Project media already contains a different Research cut")
        return destination
    clip_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".copy-", dir=clip_directory) as attempt:
        stage = Path(attempt) / "cut"
        shutil.copytree(
            folder, stage, symlinks=True, ignore=shutil.ignore_patterns(".DS_Store")
        )
        if verify_cut(stage, snapshot)[1] != digest:
            raise ValueError("Research cut changed during copy")
        stage.rename(destination)
    return destination


def research_clip_folder(media: Path, snapshot: Json) -> Path:
    clip_id = str(uuid.UUID(snapshot["clipId"]))
    version = snapshot["clipVersion"]
    if type(version) is not int or version < 1:
        raise ValueError("Invalid Research revision")
    path = media / "Research Clips" / clip_id / str(version)
    if (
        not path.is_absolute()
        or ".." in path.parts
        or any(part.is_symlink() for part in (path, *path.parents))
    ):
        raise ValueError("Research cache path must be local and cannot use symlinks")
    return path


def find_cached_research_cut(directory: Path, snapshot: Json) -> Path | None:
    if not directory.exists():
        return None
    candidates = sorted(
        path for path in directory.iterdir() if not path.name.startswith(".")
    )
    if not candidates:
        return None
    if len(candidates) != 1:
        raise ValueError("Several copies claim the same Research clip revision")
    cut = candidates[0]
    _, digest = verify_cut(cut, snapshot)
    if cut.name != digest.removeprefix("sha256:"):
        raise ValueError("Project Research copy has a different content identity")
    return cut


def bind_research_cut(
    row: Json, folder: Path, tools: MediaTools
) -> tuple[Path, MediaInspection, Json]:
    """Bind a standalone occurrence; logged milliseconds never enter frame math."""
    snapshot = row["researchClip"]
    video, digest = verify_cut(folder, snapshot)
    # Research's renderer writes one video and one audio stream, in that order.
    media = inspect_media(
        video, video_stream_index=0, audio_stream_index=1, tools=tools
    )
    if media.content_hash != digest:
        raise ValueError("Research cut changed during inspection")
    frame_count = len(media.video_frames)
    media_id = str(
        uuid.uuid5(uuid.UUID(snapshot["clipId"]), f"{snapshot['clipVersion']}:{digest}")
    )
    binding = {
        "clipId": snapshot["clipId"],
        "clipVersion": snapshot["clipVersion"],
        "mediaReferenceId": media_id,
        "loggedStartFrame": 0,
        "loggedEndFrame": frame_count,
    }
    prior = row.get("frameBinding")
    if prior is not None and prior != binding:
        raise ValueError(
            "Existing Research frame binding does not match the verified cut"
        )
    timing = row["visualOnlyTiming"]
    selected = timing.get("selectedSourceRange")
    if selected is None and prior is None:
        selected = {"startFrame": 0, "durationFrames": frame_count}
    if selected is None:
        raise ValueError("Existing Research binding has no selected range")
    start = selected["startFrame"]
    end = start + selected["durationFrames"]
    if not 0 <= start < end <= frame_count:
        raise ValueError("Research selection lies outside the verified cut")
    row["frameBinding"] = binding
    row["payload"].update(
        pictureKind="clip",
        source={"kind": "media_reference", "mediaReferenceId": media_id},
    )
    timing["selectedSourceRange"] = selected
    audio = media.audio
    assert audio is not None and media.audio_origin is not None
    # The logical clock is the cut file, not the original YouTube video.
    descriptor = {
        "payloadId": row["payload"]["payloadId"],
        "owner": {"kind": "visual_only_block", "blockId": row["id"]},
        "mediaReferenceId": media_id,
        "sourceSnapshot": {
            "system": "research",
            "snapshotId": snapshot["clipId"],
            "version": snapshot["clipVersion"],
            "packageId": media_id,
            "contentHash": digest,
            "probeHash": media.probe_hash,
        },
        "logicalSourceBounds": {
            "startFrame": 0,
            "endFrame": frame_count,
            "frameRate": wire(media.rate),
        },
        "sourceFrameMap": {
            "packageFrameZeroLogicalFrame": 0,
            "packageVideoPtsOrigin": wire(media.pts_origin),
            "loggedTimeAtPackageFrameZero": wire(Fraction(0)),
            "decodedPackageFrameRate": wire(media.rate),
            "decodedPackageFrameCount": frame_count,
            "packageVideoTimeBase": wire(media.time_base),
            "sourceAudioStreamMappings": [
                {
                    "streamIndex": audio["index"],
                    "sampleRate": int(audio["sample_rate"]),
                    "audioHash": media.audio_hash,
                    "probeHash": media.probe_hash,
                    "packagePtsOrigin": wire(media.audio_origin),
                    "loggedTimeAtPackageOrigin": wire(
                        media.audio_origin - media.pts_origin
                    ),
                }
            ],
            "descriptorHash": media.probe_hash,
            "probeHash": media.probe_hash,
        },
        "occurrenceSourceInFrame": start,
        "selectedSourceRange": {"startFrame": start, "endFrame": end},
        "preparedMediaRequirementKey": None,
    }
    return video, media, descriptor
