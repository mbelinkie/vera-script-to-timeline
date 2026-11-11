"""Private write-once diagnostics for NEW Test Bench runs only.

These files are explanatory evidence, never native receipts or a replay cursor.
Any failed publication is terminal for the caller; partial records stay put.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from . import resolve_test_bench_diagnostics as contract

MAX_RECORDS = 8192
MIN_FREE_BYTES = 256 * 1024 * 1024
_RECORD = re.compile(r"record-(\d{6})\.json\Z")


class DiagnosticWriteError(RuntimeError):
    """Refuse additional effects when diagnostic history is not durable."""


def _private_directory(path: Path, *, create: bool = False) -> None:
    if not path.is_absolute() or ".." in path.parts:
        raise DiagnosticWriteError("unsafe diagnostic directory")
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise DiagnosticWriteError("symlink in diagnostic directory")
    if create and not path.exists():
        path.mkdir(mode=0o700)  # parent must already be private and admitted
        _sync_directory(path.parent)
    info = path.stat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
    ):
        raise DiagnosticWriteError("diagnostic directory not owner-only")


def _sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _bounded_read(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
            or info.st_size > contract.MAX_RECORD_BYTES
        ):
            raise DiagnosticWriteError("unsafe diagnostic record")
        raw = os.read(fd, contract.MAX_RECORD_BYTES + 1)
        if len(raw) > contract.MAX_RECORD_BYTES or os.read(fd, 1):
            raise DiagnosticWriteError("oversized diagnostic record")
        return raw
    finally:
        os.close(fd)


class DiagnosticJournal:
    """One case/stage-bound, multi-process serialized, immutable event chain.

    The caller owns the admission and must provide an already-private root.
    This class cannot inspect a carrier, launch a host, or certify a result.
    """

    def __init__(
        self,
        root: Path,
        *,
        case_id: str,
        phase: str,
        stage: str | None = None,
        job_id: str | None = None,
        operation_id: str | None = None,
        pins: dict[str, str | None] | None = None,
    ) -> None:
        # No user-supplied diagnostic subdirectory; fixed owner-only sibling.
        _private_directory(root)
        self.root = root / "diagnostics-v1"
        self.records = self.root / "records"
        _private_directory(self.root, create=True)
        _private_directory(self.records, create=True)
        self.identity: dict[str, Any] = {
            "caseId": case_id,
            "jobId": job_id,
            "operationId": operation_id,
            "phase": phase,
            "stage": stage,
            "action": None,
            "nativeSequence": None,
        }
        self.pins: dict[str, str | None] = {
            "frozenSourceSha256": None,
            "actorSha256": None,
            "targetSha256": None,
            "authorizationSha256": None,
        }
        if pins is not None:
            self.pins.update(pins)
        self.last_verified: dict[str, Any] | None = None
        self.next_pending: dict[str, Any] | None = None
        self._poisoned = False
        # Validate caller-provided identity and pins BEFORE accepting events.
        self._make("claim", "before_claim", "pending", 0, None)

    def cursor(
        self,
        *,
        action: str | None = None,
        sequence: int | None = None,
        last_verified: dict[str, Any] | None = None,
        next_pending: dict[str, Any] | None = None,
    ) -> None:
        """Only the caller's already-verified original result may advance this."""
        self.identity["action"] = action
        self.identity["nativeSequence"] = sequence
        if last_verified is not None:
            self.last_verified = dict(last_verified)
        self.next_pending = dict(next_pending) if next_pending is not None else None

    def _make(
        self,
        event: str,
        boundary: str,
        status: str,
        index: int,
        previous: str | None,
        *,
        exception: BaseException | None = None,
        proof_layer: str = "none",
        proof_sha256: str | None = None,
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        value = {
            "schema": contract.SCHEMA,
            "recordIndex": index,
            "previousRecordSha256": previous,
            "kind": "exception" if exception is not None else "stage",
            "event": "exception" if exception is not None else event,
            "boundary": boundary,
            "status": "unknown" if exception is not None else status,
            "proofLayer": "none" if exception is not None else proof_layer,
            "proofSha256": None if exception is not None else proof_sha256,
            "clock": contract.timestamp(),
            "identity": dict(self.identity),
            "pins": dict(self.pins),
            "lastVerified": self.last_verified,
            "nextPending": self.next_pending,
            "evidence": [] if evidence is None else evidence,
            "exception": contract.exception_details(exception)
            if exception is not None
            else None,
        }
        contract.validate_record(value)
        return value

    def _chain_tip(self) -> tuple[int, str | None]:
        _private_directory(self.records)
        names = sorted(os.listdir(self.records))
        if len(names) >= MAX_RECORDS:
            raise DiagnosticWriteError("diagnostic quota exhausted")
        previous: str | None = None
        for index, name in enumerate(names):
            if name != f"record-{index:06d}.json" or not _RECORD.fullmatch(name):
                raise DiagnosticWriteError("unexpected or partial diagnostic record")
            raw = _bounded_read(self.records / name)
            try:
                record = json.loads(raw)
                if (
                    contract.canonical_bytes(record) != raw
                    or record["recordIndex"] != index
                    or record["previousRecordSha256"] != previous
                    or record["identity"]["caseId"] != self.identity["caseId"]
                    or record["identity"]["phase"] != self.identity["phase"]
                    or record["identity"]["stage"] != self.identity["stage"]
                    or record["identity"]["jobId"] != self.identity["jobId"]
                    or record["identity"]["operationId"] != self.identity["operationId"]
                    or record["pins"] != self.pins
                ):
                    raise DiagnosticWriteError("diagnostic chain/identity mismatch")
            except (ValueError, KeyError, TypeError) as error:
                raise DiagnosticWriteError("malformed diagnostic chain") from error
            previous = hashlib.sha256(raw).hexdigest()
        return len(names), previous

    def emit(
        self,
        event: str,
        boundary: str,
        *,
        status: str = "observed",
        exception: BaseException | None = None,
        proof_layer: str = "none",
        proof_sha256: str | None = None,
        evidence: list[dict[str, Any]] | None = None,
    ) -> None:
        """O_EXCL/fsync; evidence contains only vetted hashes, never file paths.

        Raw MOV/PCM files are never opened or duplicated by this writer.
        """
        try:
            if self._poisoned:
                raise DiagnosticWriteError("writer failed previously; never resume")
            _private_directory(self.root)
            lock_path = self.root / "writer.lock"
            fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            try:
                info = os.fstat(fd)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid()
                    or info.st_mode & 0o077
                    or info.st_nlink != 1
                ):
                    raise DiagnosticWriteError("unsafe diagnostic lock")
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                index, previous = self._chain_tip()
                statfs = os.statvfs(self.root)
                if statfs.f_bavail * statfs.f_frsize < MIN_FREE_BYTES:
                    raise DiagnosticWriteError("diagnostic free-space floor reached")
                raw = contract.canonical_bytes(
                    self._make(
                        event,
                        boundary,
                        status,
                        index,
                        previous,
                        exception=exception,
                        proof_layer=proof_layer,
                        proof_sha256=proof_sha256,
                        evidence=evidence,
                    )
                )
                path = self.records / f"record-{index:06d}.json"
                out = os.open(
                    path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                )
                try:
                    offset = 0
                    while offset < len(raw):
                        written = os.write(out, raw[offset:])
                        if written <= 0:
                            raise DiagnosticWriteError("short diagnostic write")
                        offset += written
                    os.fsync(out)
                finally:
                    os.close(out)
                _sync_directory(self.records)
            finally:
                os.close(fd)
        except BaseException:
            self._poisoned = True
            raise
