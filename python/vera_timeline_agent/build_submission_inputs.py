"""Trusted, byte-exact inputs for a frozen #507 build submission.

Transport-supplied source pins are claims, not paths or accepted media records.
The caller must inject an authority backed by accepted source records and
explicit compiler-dependencies/v2 authoring metadata. Nothing is synthesized.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import jsonschema  # type: ignore[import-untyped]
from referencing import Registry, Resource

_SOURCE_LIMIT = 8 * 1024**3
_CHUNK = 1024 * 1024


class FrozenInputRefusal(RuntimeError):
    """Never expose the media locator or private metadata in transport errors."""


@dataclass(frozen=True)
class AcceptedSourceFile:
    project_id: str
    source_id: str
    revision: str
    sha256: str
    path: Path


class TrustedBuildInputAuthority(Protocol):
    """Server-side accepted store and explicitly qualified authoring adapter.

    Implementations must recheck acceptance and project scope at each lookup;
    the manifest is never the source of an accepted file locator or metadata.
    """

    def accepted_source(
        self, project_id: str, source_id: str, revision: str
    ) -> AcceptedSourceFile | None: ...

    def frozen_dependencies(
        self, project_id: str, job_id: str
    ) -> Mapping[str, Any] | None: ...


def checked_compiler_dependencies(
    raw: Mapping[str, Any] | None,
    manifest: Mapping[str, Any],
    pins: Mapping[str, tuple[str, str]],
) -> bytes:
    """Validate supplied complete v2 metadata, never add missing fields."""
    if raw is None or not isinstance(raw, dict):
        raise FrozenInputRefusal("trusted compiler metadata required")
    try:
        contracts = Path(__file__).resolve().parents[2] / "contracts"
        schemas = [
            json.loads((contracts / name).read_bytes())
            for name in (
                "script-document-v2.schema.json",
                "compiler-dependencies-v2.schema.json",
            )
        ]
        registry: Registry[Any] = Registry().with_resources(
            (item["$id"], Resource.from_contents(item)) for item in schemas
        )
        validator = jsonschema.Draft202012Validator(
            schemas[1], registry=registry, format_checker=jsonschema.FormatChecker()
        )
        if next(validator.iter_errors(raw), None) is not None:
            raise FrozenInputRefusal("invalid compiler-dependencies/v2 metadata")
        doc = json.loads(manifest["documentJson"])
        settings = json.loads(manifest["settingsJson"])
        binding = raw["document"]
        if (
            not isinstance(doc, dict)
            or not isinstance(settings, dict)
            or doc.get("projectId") != manifest["projectId"]
            or settings.get("projectId") != manifest["projectId"]
            or binding["projectId"] != manifest["projectId"]
            or binding["documentId"] != doc.get("id")
            or binding["revision"] != manifest["documentRevision"]
            or binding["contentHash"] != manifest["documentDigest"]
            or binding["settingsHash"] != manifest["settingsDigest"]
            or raw["authoringDefaults"]["settingsHash"] != manifest["settingsDigest"]
            or raw["build"]["buildId"] != manifest["jobId"]
            or raw["build"]["buildClass"] != manifest["buildClass"]
        ):
            raise FrozenInputRefusal("compiler metadata differs from frozen submission")
        for item in raw["occurrenceResolutions"]:
            source_id = item["mediaReferenceId"]
            if (
                source_id not in pins
                or item["sourceSnapshot"]["contentHash"] != pins[source_id][1]
            ):
                raise FrozenInputRefusal("compiler source identity not accepted")
        if raw["preparedMedia"]:
            raise FrozenInputRefusal("unverified prepared media in frozen metadata")
        return json.dumps(
            raw, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    except FrozenInputRefusal:
        raise
    except (OSError, ValueError, TypeError, KeyError, jsonschema.SchemaError):
        raise FrozenInputRefusal("invalid trusted compiler metadata") from None


def _source_descriptor(
    record: AcceptedSourceFile | None,
    project_id: str,
    source_id: str,
    revision: str,
    digest: str,
    roots: tuple[Path, ...],
) -> int:
    if (
        not isinstance(record, AcceptedSourceFile)
        or (record.project_id, record.source_id, record.revision, record.sha256)
        != (project_id, source_id, revision, digest)
        or not isinstance(record.path, Path)
        or not record.path.is_absolute()
        or not roots
    ):
        raise FrozenInputRefusal("source is not in the accepted versioned store")
    path = record.path
    try:
        for root in roots:
            if not root.is_absolute() or any(
                p.is_symlink() for p in (root, *root.parents)
            ):
                raise FrozenInputRefusal("untrusted accepted source root")
            facts = root.stat()
            if (
                not stat.S_ISDIR(facts.st_mode)
                or facts.st_uid != os.getuid()
                or facts.st_mode & 0o077
            ):
                raise FrozenInputRefusal("accepted source root must be private")
    except OSError:
        raise FrozenInputRefusal("accepted source root unavailable") from None
    if not any(path.is_relative_to(root) for root in roots) or any(
        p.is_symlink() for p in (path, *path.parents)
    ):
        raise FrozenInputRefusal("source outside trusted accepted roots")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        facts = os.fstat(fd)
        if (
            not stat.S_ISREG(facts.st_mode)
            or facts.st_nlink != 1
            or facts.st_size < 1
            or facts.st_size > _SOURCE_LIMIT
        ):
            os.close(fd)
            raise FrozenInputRefusal("accepted source is not a bounded regular file")
        return fd
    except OSError:
        raise FrozenInputRefusal("accepted source unavailable") from None


def frozen_source_file(
    authority: TrustedBuildInputAuthority,
    project_id: str,
    source_id: str,
    revision: str,
    digest: str,
    roots: tuple[Path, ...],
    destination: Path | None,
) -> Path | None:
    """Recheck accepted record and bytes; optionally create an immutable copy.

    An existing copy is verified, never overwritten. The accepted source is
    opened without following symlinks and hashed from the same descriptor read.
    """
    try:
        record = authority.accepted_source(project_id, source_id, revision)
    except (OSError, ValueError, KeyError):
        raise FrozenInputRefusal("accepted source lookup failed") from None
    fd = _source_descriptor(record, project_id, source_id, revision, digest, roots)
    output_fd: int | None = None
    created = False
    complete = False
    try:
        if destination is not None:
            if destination.is_symlink():
                raise FrozenInputRefusal("unsafe frozen source destination")
            try:
                output_fd = os.open(
                    destination,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                )
                created = True
            except FileExistsError:
                pass
        digest_state = hashlib.sha256()
        with os.fdopen(fd, "rb") as source:
            fd = -1
            while part := source.read(_CHUNK):
                digest_state.update(part)
                if output_fd is not None:
                    remaining = memoryview(part)
                    while remaining:
                        remaining = remaining[os.write(output_fd, remaining) :]
        if "sha256:" + digest_state.hexdigest() != digest:
            raise FrozenInputRefusal("accepted source bytes changed")
        if output_fd is not None:
            os.fsync(output_fd)
        if destination is not None:
            if output_fd is not None:
                os.close(output_fd)
                output_fd = None
            facts = destination.stat(follow_symlinks=False)
            with os.fdopen(
                os.open(destination, os.O_RDONLY | os.O_NOFOLLOW), "rb"
            ) as saved:
                saved_hash = hashlib.file_digest(saved, "sha256").hexdigest()
            if (
                not stat.S_ISREG(facts.st_mode)
                or facts.st_nlink != 1
                or facts.st_mode & 0o777 != 0o600
                or saved_hash != digest[7:]
            ):
                raise FrozenInputRefusal("frozen accepted source copy changed")
        complete = True
        return destination
    finally:
        if fd != -1:
            os.close(fd)
        if output_fd is not None:
            os.close(output_fd)
        if created and not complete and destination is not None:
            destination.unlink(missing_ok=True)
