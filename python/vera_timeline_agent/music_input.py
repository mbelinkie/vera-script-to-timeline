"""Freeze explicitly located, hash-verified PCM music before the Node v2 compiler.

This module never searches for media or modifies a user's source files. The
``event:<stable music event UUID>`` key is the only accepted music locator.
"""

from __future__ import annotations

import hashlib
import os
import stat
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .build_jobs import BuildJobError


def music_event_id(document_id: str, span_id: str, artifact_id: str) -> str:
    digest = hashlib.sha256(
        f"music:{document_id}:{span_id}:{artifact_id}".encode()
    ).hexdigest()[:32]
    return (
        f"{digest[:8]}-{digest[8:12]}-5{digest[13:16]}-8{digest[17:20]}-{digest[20:]}"
    )


def _plain_music_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        raise BuildJobError("music locator must be an absolute local path")
    path = path.absolute()
    if any(node.is_symlink() for node in (path, *path.parents)):
        raise BuildJobError(f"music symbolic link is not permitted: {path.name}")
    return path


def inspect_music(path: Path, expected_hash: str) -> int:
    """Verify bytes and exact 48-kHz, mono, 16-bit PCM frame count."""
    path = _plain_music_path(str(path))
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise BuildJobError(
            f"music file cannot be opened safely: {path.name}"
        ) from error
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise BuildJobError(f"music file must be regular: {path.name}")
    try:
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise BuildJobError(f"music file must be regular: {path.name}")
            try:
                with wave.open(stream, "rb") as wav:
                    if (
                        wav.getnchannels() != 1
                        or wav.getframerate() != 48000
                        or wav.getcomptype() != "NONE"
                        or wav.getsampwidth() != 2
                        or wav.getnframes() < 1
                    ):
                        raise BuildJobError(
                            f"music file requires 48kHz mono PCM16 WAV: {path.name}"
                        )
                    sample_count = wav.getnframes()
                    total = 0
                    while total < sample_count:
                        chunk = wav.readframes(min(65536, sample_count - total))
                        if not chunk or len(chunk) % wav.getsampwidth():
                            raise BuildJobError(
                                f"music WAV data is truncated: {path.name}"
                            )
                        total += len(chunk) // wav.getsampwidth()
                    if total != sample_count:
                        raise BuildJobError(f"music WAV data is truncated: {path.name}")
            except (EOFError, wave.Error, OSError) as error:
                raise BuildJobError(f"invalid music WAV file: {path.name}") from error
            stream.seek(0)
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
            after = os.fstat(stream.fileno())
            if (before.st_ino, before.st_dev, before.st_size, before.st_mtime_ns) != (
                after.st_ino,
                after.st_dev,
                after.st_size,
                after.st_mtime_ns,
            ):
                raise BuildJobError(f"music file changed while reading: {path.name}")
            if (path.stat().st_ino, path.stat().st_dev) != (
                before.st_ino,
                before.st_dev,
            ):
                raise BuildJobError(f"music file was replaced: {path.name}")
            if f"sha256:{digest.hexdigest()}" != expected_hash:
                raise BuildJobError(f"music content hash mismatch: {path.name}")
            return sample_count
    except OSError as error:
        raise BuildJobError(f"music file read failed: {path.name}") from error


@dataclass(frozen=True)
class MusicResolution:
    dependencies: dict[str, Any]
    media_paths: dict[str, str]
    pins: tuple[tuple[Path, str, int], ...]
    missing_paths: tuple[Path, ...]


def resolve_music_bindings(
    document: dict[str, Any], dependencies: dict[str, Any], media_paths: dict[str, Any]
) -> MusicResolution:
    """Return new effective inputs; never mutate originals or discover files."""
    import copy

    effective = copy.deepcopy(dependencies)
    paths = copy.deepcopy(media_paths)
    spans = document.get("rowAudioSpans", [])
    if not isinstance(spans, list):
        raise BuildJobError("invalid frozen music spans")
    existing = effective.get("musicBindings", [])
    if not isinstance(existing, list):
        raise BuildJobError("invalid frozen music binding array")
    prior: dict[str, dict[str, Any]] = {}
    for entry in existing:
        if not isinstance(entry, dict) or not isinstance(entry.get("spanId"), str):
            raise BuildJobError("invalid music binding")
        if entry["spanId"] in prior:
            raise BuildJobError("duplicate music binding")
        prior[entry["spanId"]] = entry
    bindings: list[dict[str, Any]] = []
    pins: list[tuple[Path, str, int]] = []
    missing: list[Path] = []
    used: set[str] = set()
    for span in spans:
        if not isinstance(span, dict) or not isinstance(span.get("source"), dict):
            raise BuildJobError("invalid frozen music source")
        span_id = span.get("id")
        source = span["source"]
        if not isinstance(span_id, str) or span_id in used:
            raise BuildJobError("duplicate or invalid music span ID")
        used.add(span_id)
        if not all(
            isinstance(source.get(key), str) for key in ("artifactId", "contentHash")
        ):
            raise BuildJobError("music source lacks pinned artifact/hash")
        old = prior.get(span_id)
        if old and old.get("source") != source:
            raise BuildJobError("music binding source identity mismatch")
        key = f"event:{music_event_id(document['id'], span_id, source['artifactId'])}"
        raw = paths.get(key)
        if raw is not None and not isinstance(raw, str):
            raise BuildJobError("invalid music locator")
        path = _plain_music_path(raw) if raw is not None else None
        filename = (
            path.name
            if path is not None
            else (old or {}).get("displayFilename", source["artifactId"])
        )
        if path is None or not path.exists():
            if old and old.get("status") == "ready":
                raise BuildJobError(f"previously ready music disappeared: {filename}")
            if path is not None:
                missing.append(path)
                paths.pop(key)
            binding = {
                "spanId": span_id,
                "source": source,
                "displayFilename": filename,
                "status": "missing",
            }
        else:
            samples = inspect_music(path, source["contentHash"])
            binding = {
                "spanId": span_id,
                "source": source,
                "displayFilename": filename,
                "status": "ready",
                "sampleRate": 48000,
                "channels": 1,
                "durationSamples": samples,
            }
            pins.append((path, source["contentHash"], samples))
        if old and old != binding:
            raise BuildJobError(f"prepared music binding changed: {filename}")
        bindings.append(binding)
    if set(prior) - used:
        raise BuildJobError("unreferenced frozen music binding")
    if spans:
        effective["musicBindings"] = bindings
    if pins:
        roles = effective["roles"]
        tracks = effective["tracks"]
        music_id = roles.get("musicTrackId", "music-a5")
        if music_id == roles.get("narrationTrackId") or music_id in roles.get(
            "sourceAudioTrackIds", []
        ):
            raise BuildJobError("music A5 role overlaps another audio role")
        at_five = [
            track
            for track in tracks
            if track.get("kind") == "audio" and track.get("index") == 5
        ]
        if at_five and any(track.get("id") != music_id for track in at_five):
            raise BuildJobError("music A5 is already occupied by another audio track")
        named = [track for track in tracks if track.get("id") == music_id]
        if named and any(
            track.get("kind") != "audio" or track.get("index") != 5 for track in named
        ):
            raise BuildJobError("music track identity is not A5 audio")
        if not named:
            tracks.append(
                {"id": music_id, "kind": "audio", "index": 5, "name": "A5 Music"}
            )
        roles["musicTrackId"] = music_id
    return MusicResolution(effective, paths, tuple(pins), tuple(missing))


def verify_music_pins(resolution: MusicResolution) -> None:
    for path, expected_hash, expected_samples in resolution.pins:
        if inspect_music(path, expected_hash) != expected_samples:
            raise BuildJobError(f"music sample duration changed: {path.name}")
    for path in resolution.missing_paths:
        if path.exists() or path.is_symlink():
            raise BuildJobError(f"missing music changed after freeze: {path.name}")
