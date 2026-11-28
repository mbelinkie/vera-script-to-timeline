"""Prepare and locate exact kept Research Music selections in project Media."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, BinaryIO
from uuid import NAMESPACE_URL, UUID, uuid5

from .build_jobs import BuildJobError, publish_immutable_output
from .build_stage_receipt import hash_file
from .media_preparation import MediaTools
from .music_input import inspect_music, music_event_id

_DEMUXERS = {
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/mp4": "mov",
    "audio/ogg": "ogg",
    "audio/flac": "flac",
    "audio/webm": "matroska",
}
_MAX_BYTES = 50 * 1024 * 1024
_MAX_DURATION_MS = 30 * 60_000
_SAMPLE_RATE = 48_000


def _sample_range(selection: dict[str, Any]) -> tuple[int, int]:
    start, end = selection["startMs"], selection["endMs"]
    if not 0 <= start < end <= _MAX_DURATION_MS:
        raise BuildJobError("Invalid saved Research Music range")
    return start * 48, end * 48


def _source_pin(
    project_id: str, selection: dict[str, Any], digest: str
) -> dict[str, Any]:
    identity = ":".join(
        UUID(value).hex
        for value in (
            project_id,
            selection["researchProjectId"],
            selection["sourceId"],
            selection["itemId"],
        )
    )
    revision = json.dumps(selection, sort_keys=True, separators=(",", ":"))
    return {
        "mediaReferenceId": str(
            uuid5(NAMESPACE_URL, f"vera:research-music:{identity}")
        ),
        "artifactId": str(
            uuid5(
                NAMESPACE_URL, f"vera:research-music-v1:{identity}:{revision}:{digest}"
            )
        ),
        "artifactVersion": 1,
        "contentHash": digest,
        "researchSelection": selection,
    }


def _artifact_path(root: Path, project_id: str, artifact_id: str) -> Path:
    if not root.is_absolute() or ".." in root.parts:
        raise BuildJobError("Research Music needs a local project Media directory")
    path = root / "Research Music" / str(UUID(project_id)) / f"{UUID(artifact_id)}.wav"
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise BuildJobError("Research Music paths cannot use symlinks")
    return path


def prepare_selection(
    root: Path, request: dict[str, Any], stream: BinaryIO
) -> dict[str, Any]:
    project_id, selection = request["projectId"], request["selection"]
    start, end = _sample_range(selection)
    content = stream.read(_MAX_BYTES + 1)
    if (
        not content
        or len(content) > _MAX_BYTES
        or "sha256:" + hashlib.sha256(content).hexdigest() != selection["playbackHash"]
    ):
        raise BuildJobError("Research Music bytes differ from the kept original")
    with tempfile.TemporaryDirectory(prefix="vera-research-music-") as directory:
        source = Path(directory) / "input"
        wav = Path(directory).resolve() / "selection.wav"
        source.write_bytes(content)
        tools = MediaTools()
        tools.run(
            [
                tools.ffmpeg,
                "-v",
                "error",
                "-nostdin",
                "-xerror",
                "-protocol_whitelist",
                "file",
                "-f",
                _DEMUXERS[request["mimeType"]],
                "-i",
                str(source),
                "-map",
                "0:a:0",
                "-vn",
                "-sn",
                "-dn",
                "-af",
                f"aresample={_SAMPLE_RATE},atrim=start_sample={start}:end_sample={end}",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                "-fflags",
                "+bitexact",
                "-flags:a",
                "+bitexact",
                str(wav),
            ],
            timeout=90,
        )
        digest = "sha256:" + hash_file(wav)
        if inspect_music(wav, digest) != end - start:
            raise BuildJobError(
                "Kept Research Music cannot supply the exact saved range"
            )
        pin = _source_pin(project_id, selection, digest)
        path = _artifact_path(root, project_id, pin["artifactId"])
        publish_immutable_output(path, wav.read_bytes())
    return {"source": pin, "durationSamples": end - start}


def locate_research_music(
    document: dict[str, Any], media_root: Path, paths: dict[str, Any]
) -> bool:
    """Find project-owned event locators for the existing PCM verifier."""
    found = False
    for span in document.get("rowAudioSpans", []):
        source = span["source"]
        selection = source.get("researchSelection")
        if selection is None:
            continue
        found = True
        project_id = document["projectId"]
        if source != _source_pin(project_id, selection, source["contentHash"]):
            raise BuildJobError(
                "Saved Research Music provenance does not match its project artifact"
            )
        path = _artifact_path(media_root, project_id, source["artifactId"])
        key = (
            f"event:{music_event_id(document['id'], span['id'], source['artifactId'])}"
        )
        if key in paths and paths[key] != str(path):
            raise BuildJobError(
                "Research Music locator differs from its project artifact"
            )
        if not path.is_file():
            raise BuildJobError(
                "Prepared Research Music is missing from this project's Media. "
                "Resolve the saved selection again."
            )
        paths[key] = str(path)
    return found
