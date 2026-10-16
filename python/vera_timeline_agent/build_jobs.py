"""Durable, job-scoped build orchestration for Slice 1.7.

Adapters must use the stable stage key for their own idempotent side effects.
``reconcile`` must return false only after an authoritative absence check.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, cast

Mode = Literal["free", "studio"]
CORE_STAGES = (
    "generating_speech",
    "resolving_media",
    "compiling",
    "writing_interchange",
    "verifying_import_package",
)
STUDIO_STAGES = (
    "building_resolve_timeline",
    "verifying_timeline",
    "rendering_mp4",
    "verifying_mp4",
    "uploading",
)
ALL_STAGES = CORE_STAGES + STUDIO_STAGES


class BuildJobError(RuntimeError):
    """Invalid job request, scope, state, lease, or artifact."""


class NeedsAction(RuntimeError):
    """A local capability must recover before the stage can run."""


class UncertainResult(RuntimeError):
    """The adapter cannot yet prove whether its side effect completed."""


def publish_immutable_output(path: Path, content: bytes) -> None:
    """Atomically publish one local receipt without replacing an existing one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != content:
                raise BuildJobError(
                    "immutable stage receipt has different bytes"
                ) from None
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class BuildRequest:
    project_id: str
    snapshot_id: str
    idempotency_key: str
    mode: Mode
    render: bool = False
    delivery: bool = False

    def validate(self) -> None:
        for label, value in (
            ("project ID", self.project_id),
            ("snapshot ID", self.snapshot_id),
            ("idempotency key", self.idempotency_key),
        ):
            if not value or len(value) > 256 or value.strip() != value:
                raise BuildJobError(f"invalid {label}")
        if self.mode not in ("free", "studio"):
            raise BuildJobError("mode must be free or studio")
        if self.mode == "free" and (self.render or self.delivery):
            raise BuildJobError("Free jobs cannot request automated render/delivery")
        if self.delivery and not self.render:
            raise BuildJobError("delivery requires a requested render")


@dataclass(frozen=True)
class StageContext:
    project_id: str
    job_id: str
    snapshot_id: str
    stage: str
    stage_key: str
    output_path: Path
    attempt_id: int
    lease_epoch: int
    report_progress: Callable[[str], None] = field(repr=False)
    renew_lease: Callable[[], None] = field(repr=False)


class StageAdapter(Protocol):
    def reconcile(self, context: StageContext) -> bool:
        """Return true only for a verified effect under ``stage_key``."""

    def execute(self, context: StageContext) -> None:
        """Perform an effect idempotently under ``stage_key``."""


@dataclass(frozen=True)
class _Lease:
    job_id: str
    project_id: str
    snapshot_id: str
    stage: str
    epoch: int
    attempt_id: int
    worker: str


class BuildJobStore:
    """SQLite state and one receipt path per logical stage.

    A worker is given an explicit project/job pair; there is no global job
    enumeration or lease operation. Every write is fenced by the lease epoch.
    """

    def __init__(self, root: Path, *, clock: Callable[[], float] = time.time) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir(exist_ok=True)
        self.database = self.root / "build-jobs.sqlite3"
        self.clock = clock
        with self._connection() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=FULL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    lease_epoch INTEGER NOT NULL DEFAULT 0,
                    lease_worker TEXT,
                    lease_until REAL,
                    active_stage TEXT,
                    last_error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    UNIQUE(project_id, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS stages (
                    job_id TEXT NOT NULL REFERENCES jobs(id),
                    position INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    path TEXT,
                    sha256 TEXT,
                    size INTEGER,
                    completed_at REAL,
                    PRIMARY KEY(job_id, name)
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL REFERENCES jobs(id),
                    stage TEXT NOT NULL,
                    epoch INTEGER NOT NULL,
                    worker TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    finished_at REAL,
                    detail TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL REFERENCES jobs(id),
                    at REAL NOT NULL,
                    kind TEXT NOT NULL,
                    stage TEXT,
                    epoch INTEGER,
                    message TEXT NOT NULL
                );
                """
            )

    @contextmanager
    def _connection(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA foreign_keys=ON")
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if write:
                connection.commit()
        except BaseException:
            if write:
                connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _job(
        connection: sqlite3.Connection, project_id: str, job_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM jobs WHERE id = ? AND project_id = ?", (job_id, project_id)
        ).fetchone()
        if row is None:
            raise BuildJobError("job not found in project scope")
        return cast(sqlite3.Row, row)

    @staticmethod
    def _event(
        connection: sqlite3.Connection,
        job_id: str,
        now: float,
        kind: str,
        message: str,
        stage: str | None = None,
        epoch: int | None = None,
    ) -> None:
        connection.execute(
            "INSERT INTO events(job_id, at, kind, stage, epoch, message) "
            "VALUES(?,?,?,?,?,?)",
            (job_id, now, kind, stage, epoch, message),
        )

    def submit(self, request: BuildRequest) -> str:
        request.validate()
        request_hash = hashlib.sha256(
            json.dumps(asdict(request), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        now = self.clock()
        with self._connection(write=True) as connection:
            existing = connection.execute(
                "SELECT id, request_hash FROM jobs "
                "WHERE project_id=? AND idempotency_key=?",
                (request.project_id, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise BuildJobError(
                        "idempotency key belongs to a different request"
                    )
                return str(existing["id"])
            job_id = uuid.uuid4().hex
            connection.execute(
                """INSERT INTO jobs(id, project_id, snapshot_id, idempotency_key,
                   request_hash, mode, status, created_at, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    job_id,
                    request.project_id,
                    request.snapshot_id,
                    request.idempotency_key,
                    request_hash,
                    request.mode,
                    "queued",
                    now,
                    now,
                ),
            )
            for position, name in enumerate(ALL_STAGES):
                requested = position < len(CORE_STAGES) or (
                    request.mode == "studio"
                    and (
                        position < 7
                        or (
                            name in ("rendering_mp4", "verifying_mp4")
                            and request.render
                        )
                        or (name == "uploading" and request.delivery)
                    )
                )
                connection.execute(
                    "INSERT INTO stages(job_id, position, name, status) "
                    "VALUES(?,?,?,?)",
                    (job_id, position, name, "requested" if requested else "skipped"),
                )
            self._event(connection, job_id, now, "submitted", "job queued")
            return job_id

    def status(self, project_id: str, job_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            job = self._job(connection, project_id, job_id)
            stages = connection.execute(
                "SELECT name,status,path,sha256,size,completed_at FROM stages "
                "WHERE job_id=? ORDER BY position",
                (job_id,),
            ).fetchall()
            attempts = connection.execute(
                "SELECT id,stage,epoch,worker,status,started_at,finished_at,detail "
                "FROM attempts WHERE job_id=? ORDER BY id",
                (job_id,),
            ).fetchall()
            events = connection.execute(
                "SELECT id,at,kind,stage,epoch,message FROM events "
                "WHERE job_id=? ORDER BY id",
                (job_id,),
            ).fetchall()
            return {
                "id": job_id,
                "projectId": project_id,
                "snapshotId": job["snapshot_id"],
                "mode": job["mode"],
                "status": job["status"],
                "cancelRequested": bool(job["cancel_requested"]),
                "activeStage": job["active_stage"],
                "leaseEpoch": job["lease_epoch"],
                "leaseUntil": job["lease_until"],
                "lastError": job["last_error"],
                "stages": [dict(row) for row in stages],
                "attempts": [dict(row) for row in attempts],
                "events": [dict(row) for row in events],
            }

    def _output_path(self, job_id: str, stage: str) -> Path:
        return self.artifacts / job_id / stage / "output"

    def _verify_output(self, job_id: str, stage: str) -> tuple[str, int]:
        path = self._output_path(job_id, stage)
        if any(
            parent.is_symlink()
            for parent in (path, *path.parents)
            if parent != self.root.parent
        ):
            raise BuildJobError(f"stage artifact contains a symbolic link: {stage}")
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError as error:
            raise BuildJobError(
                f"stage artifact is missing or unreadable: {stage}"
            ) from error
        try:
            facts = os.fstat(descriptor)
            for pending in path.parent.glob(".pending-*"):
                if (
                    pending.is_file()
                    and pending.stat(follow_symlinks=False).st_ino == facts.st_ino
                ):
                    pending.unlink()
            facts = os.fstat(descriptor)
            if not stat.S_ISREG(facts.st_mode) or facts.st_nlink != 1:
                raise BuildJobError(
                    f"stage artifact is not an independent file: {stage}"
                )
            digest = hashlib.sha256()
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if os.fstat(descriptor).st_size != facts.st_size:
                raise BuildJobError(
                    f"stage artifact changed during verification: {stage}"
                )
            return digest.hexdigest(), facts.st_size
        finally:
            os.close(descriptor)

    def _verify_completed(self, project_id: str, job_id: str) -> bool:
        with self._connection() as connection:
            self._job(connection, project_id, job_id)
            completed = connection.execute(
                "SELECT name,path,sha256,size FROM stages "
                "WHERE job_id=? AND status='complete'",
                (job_id,),
            ).fetchall()
        for stage in completed:
            try:
                digest, size = self._verify_output(job_id, str(stage["name"]))
                if (
                    stage["path"] != str(self._output_path(job_id, str(stage["name"])))
                    or digest != stage["sha256"]
                    or size != stage["size"]
                ):
                    raise BuildJobError(f"verified artifact changed: {stage['name']}")
            except BuildJobError as error:
                with self._connection(write=True) as connection:
                    job = self._job(connection, project_id, job_id)
                    if job["status"] not in ("canceled", "import_confirmed"):
                        now = self.clock()
                        active_stage = job["active_stage"]
                        if active_stage is not None:
                            connection.execute(
                                "UPDATE attempts SET status='revoked',finished_at=?,"
                                "detail=? WHERE job_id=? AND epoch=? "
                                "AND status='running'",
                                (now, str(error), job_id, job["lease_epoch"]),
                            )
                            connection.execute(
                                "UPDATE stages SET status='requested' "
                                "WHERE job_id=? AND name=? AND status='running'",
                                (job_id, active_stage),
                            )
                        connection.execute(
                            "UPDATE jobs SET status='failed',last_error=?,updated_at=?,"
                            "active_stage=NULL,lease_worker=NULL,lease_until=NULL "
                            "WHERE id=?",
                            (str(error), now, job_id),
                        )
                        self._event(
                            connection, job_id, now, "integrity_failed", str(error)
                        )
                return False
        return True

    def _expire(
        self, connection: sqlite3.Connection, job: sqlite3.Row, now: float
    ) -> None:
        stage = job["active_stage"]
        if stage is None:
            return
        connection.execute(
            "UPDATE attempts SET status='expired',finished_at=?,detail='lease expired' "
            "WHERE job_id=? AND epoch=? AND status='running'",
            (now, job["id"], job["lease_epoch"]),
        )
        connection.execute(
            "UPDATE stages SET status='requested' "
            "WHERE job_id=? AND name=? AND status='running'",
            (job["id"], stage),
        )
        connection.execute(
            "UPDATE jobs SET status='queued',active_stage=NULL,lease_worker=NULL,"
            "lease_until=NULL,updated_at=? WHERE id=?",
            (now, job["id"]),
        )
        self._event(
            connection,
            str(job["id"]),
            now,
            "lease_expired",
            "lease expired",
            str(stage),
            int(job["lease_epoch"]),
        )

    def _cancel_idle(
        self, connection: sqlite3.Connection, job_id: str, now: float
    ) -> None:
        connection.execute(
            "UPDATE stages SET status='canceled' WHERE job_id=? "
            "AND status IN ('requested','waiting','failed')",
            (job_id,),
        )
        connection.execute(
            "UPDATE jobs SET status='canceled',active_stage=NULL,lease_worker=NULL,"
            "lease_until=NULL,updated_at=? WHERE id=?",
            (now, job_id),
        )
        self._event(connection, job_id, now, "canceled", "canceled at stage boundary")

    def _claim(
        self, project_id: str, job_id: str, worker: str, lease_seconds: float
    ) -> _Lease | None:
        if not worker or lease_seconds <= 0:
            raise BuildJobError("worker and positive lease duration are required")
        now = self.clock()
        with self._connection(write=True) as connection:
            job = self._job(connection, project_id, job_id)
            if job["status"] in (
                "complete",
                "ready_to_import",
                "import_confirmed",
                "canceled",
                "failed",
                "waiting",
            ):
                return None
            if job["active_stage"] is not None:
                if job["lease_until"] is not None and job["lease_until"] > now:
                    return None
                self._expire(connection, job, now)
            if job["cancel_requested"]:
                self._cancel_idle(connection, job_id, now)
                return None
            stage = connection.execute(
                "SELECT name FROM stages WHERE job_id=? AND status='requested' "
                "ORDER BY position LIMIT 1",
                (job_id,),
            ).fetchone()
            if stage is None:
                return None
            epoch = int(job["lease_epoch"]) + 1
            name = str(stage["name"])
            connection.execute(
                "UPDATE stages SET status='running' WHERE job_id=? AND name=?",
                (job_id, name),
            )
            connection.execute(
                "UPDATE jobs SET status='running',active_stage=?,lease_epoch=?,"
                "lease_worker=?,lease_until=?,updated_at=? WHERE id=?",
                (name, epoch, worker, now + lease_seconds, now, job_id),
            )
            attempt = connection.execute(
                "INSERT INTO attempts(job_id,stage,epoch,worker,status,started_at) "
                "VALUES(?,?,?,?,?,?)",
                (job_id, name, epoch, worker, "running", now),
            )
            attempt_id = attempt.lastrowid
            assert attempt_id is not None
            self._event(
                connection,
                job_id,
                now,
                "stage_started",
                "stage attempt started",
                name,
                epoch,
            )
            return _Lease(
                job_id,
                project_id,
                str(job["snapshot_id"]),
                name,
                epoch,
                attempt_id,
                worker,
            )

    def _has_lease(self, job: sqlite3.Row, lease: _Lease, now: float) -> bool:
        return (
            job["status"] == "running"
            and job["active_stage"] == lease.stage
            and job["lease_epoch"] == lease.epoch
            and job["lease_worker"] == lease.worker
            and job["lease_until"] is not None
            and job["lease_until"] > now
        )

    def _progress(self, lease: _Lease, message: str) -> None:
        if not message or len(message) > 1000:
            raise BuildJobError("progress message must contain 1-1000 characters")
        now = self.clock()
        with self._connection(write=True) as connection:
            job = self._job(connection, lease.project_id, lease.job_id)
            if not self._has_lease(job, lease, now):
                raise BuildJobError("progress rejected: lease is stale")
            self._event(
                connection,
                lease.job_id,
                now,
                "progress",
                message,
                lease.stage,
                lease.epoch,
            )

    def _renew(self, lease: _Lease, lease_seconds: float) -> None:
        now = self.clock()
        with self._connection(write=True) as connection:
            job = self._job(connection, lease.project_id, lease.job_id)
            if not self._has_lease(job, lease, now):
                raise BuildJobError("renewal rejected: lease is stale")
            connection.execute(
                "UPDATE jobs SET lease_until=?,updated_at=? WHERE id=?",
                (now + lease_seconds, now, lease.job_id),
            )
            self._event(
                connection,
                lease.job_id,
                now,
                "lease_renewed",
                "worker renewed stage lease",
                lease.stage,
                lease.epoch,
            )

    def _finish(self, lease: _Lease, digest: str, size: int) -> bool:
        now = self.clock()
        with self._connection(write=True) as connection:
            job = self._job(connection, lease.project_id, lease.job_id)
            if not self._has_lease(job, lease, now):
                if (
                    job["active_stage"] == lease.stage
                    and job["lease_epoch"] == lease.epoch
                ):
                    self._expire(connection, job, now)
                return False
            connection.execute(
                "UPDATE stages SET status='complete',path=?,sha256=?,size=?,"
                "completed_at=? "
                "WHERE job_id=? AND name=? AND status='running'",
                (
                    str(self._output_path(lease.job_id, lease.stage)),
                    digest,
                    size,
                    now,
                    lease.job_id,
                    lease.stage,
                ),
            )
            connection.execute(
                "UPDATE attempts SET status='complete',finished_at=? WHERE id=?",
                (now, lease.attempt_id),
            )
            remaining = connection.execute(
                "SELECT COUNT(*) FROM stages WHERE job_id=? AND status='requested'",
                (lease.job_id,),
            ).fetchone()[0]
            status_value = (
                "queued"
                if remaining
                else ("ready_to_import" if job["mode"] == "free" else "complete")
            )
            connection.execute(
                "UPDATE jobs SET status=?,active_stage=NULL,lease_worker=NULL,"
                "lease_until=NULL,updated_at=?,last_error=NULL WHERE id=?",
                (status_value, now, lease.job_id),
            )
            self._event(
                connection,
                lease.job_id,
                now,
                "stage_complete",
                digest,
                lease.stage,
                lease.epoch,
            )
            if job["cancel_requested"]:
                self._cancel_idle(connection, lease.job_id, now)
            return True

    def _stop_attempt(self, lease: _Lease, status_value: str, message: str) -> None:
        now = self.clock()
        with self._connection(write=True) as connection:
            job = self._job(connection, lease.project_id, lease.job_id)
            if not self._has_lease(job, lease, now):
                if (
                    job["active_stage"] == lease.stage
                    and job["lease_epoch"] == lease.epoch
                ):
                    self._expire(connection, job, now)
                return
            connection.execute(
                "UPDATE attempts SET status=?,finished_at=?,detail=? WHERE id=?",
                (status_value, now, message, lease.attempt_id),
            )
            connection.execute(
                "UPDATE stages SET status=? WHERE job_id=? AND name=?",
                (status_value, lease.job_id, lease.stage),
            )
            connection.execute(
                "UPDATE jobs SET status=?,active_stage=NULL,lease_worker=NULL,"
                "lease_until=NULL,last_error=?,updated_at=? WHERE id=?",
                (status_value, message, now, lease.job_id),
            )
            self._event(
                connection,
                lease.job_id,
                now,
                status_value,
                message,
                lease.stage,
                lease.epoch,
            )
            if job["cancel_requested"]:
                self._cancel_idle(connection, lease.job_id, now)

    def run_one(
        self,
        project_id: str,
        job_id: str,
        worker: str,
        adapter: StageAdapter,
        *,
        lease_seconds: float = 300,
    ) -> bool:
        """Run at most one stage; false means terminal, busy, waiting, or failed."""
        if not self._verify_completed(project_id, job_id):
            return False
        lease = self._claim(project_id, job_id, worker, lease_seconds)
        if lease is None:
            return False
        context = StageContext(
            project_id=project_id,
            job_id=job_id,
            snapshot_id=lease.snapshot_id,
            stage=lease.stage,
            stage_key=hashlib.sha256(
                f"{project_id}\0{job_id}\0{lease.stage}".encode()
            ).hexdigest(),
            output_path=self._output_path(job_id, lease.stage),
            attempt_id=lease.attempt_id,
            lease_epoch=lease.epoch,
            report_progress=lambda message: self._progress(lease, message),
            renew_lease=lambda: self._renew(lease, lease_seconds),
        )
        try:
            if not adapter.reconcile(context):
                adapter.execute(context)
                if not adapter.reconcile(context):
                    raise UncertainResult("stage response has no verified receipt")
            digest, size = self._verify_output(job_id, lease.stage)
        except (NeedsAction, UncertainResult) as error:
            self._stop_attempt(lease, "waiting", str(error))
            return False
        except Exception as error:
            self._stop_attempt(lease, "failed", str(error))
            return False
        return self._finish(lease, digest, size)

    def resume(self, project_id: str, job_id: str) -> str:
        now = self.clock()
        with self._connection(write=True) as connection:
            job = self._job(connection, project_id, job_id)
            if job["status"] not in ("waiting", "failed"):
                raise BuildJobError("only waiting or failed jobs can resume")
            connection.execute(
                "UPDATE stages SET status='requested' WHERE job_id=? "
                "AND status IN ('waiting','failed')",
                (job_id,),
            )
            connection.execute(
                "UPDATE jobs SET status='queued',last_error=NULL,updated_at=? "
                "WHERE id=?",
                (now, job_id),
            )
            self._event(connection, job_id, now, "resumed", "job queued for retry")
            return "queued"

    def cancel(self, project_id: str, job_id: str) -> str:
        now = self.clock()
        with self._connection(write=True) as connection:
            job = self._job(connection, project_id, job_id)
            if job["status"] in (
                "complete",
                "ready_to_import",
                "import_confirmed",
                "canceled",
                "failed",
            ):
                return str(job["status"])
            connection.execute(
                "UPDATE jobs SET cancel_requested=1,updated_at=? WHERE id=?",
                (now, job_id),
            )
            self._event(
                connection, job_id, now, "cancel_requested", "cancellation requested"
            )
            if job["active_stage"] is None or job["lease_until"] <= now:
                if job["active_stage"] is not None:
                    self._expire(connection, job, now)
                self._cancel_idle(connection, job_id, now)
                return "canceled"
            return "cancel_requested"

    def confirm_import(self, project_id: str, job_id: str) -> str:
        if not self._verify_completed(project_id, job_id):
            raise BuildJobError("cannot confirm a changed import package")
        now = self.clock()
        with self._connection(write=True) as connection:
            job = self._job(connection, project_id, job_id)
            if job["status"] == "import_confirmed":
                return "import_confirmed"
            if job["mode"] != "free" or job["status"] != "ready_to_import":
                raise BuildJobError("only a ready Free package can be confirmed")
            connection.execute(
                "UPDATE jobs SET status='import_confirmed',updated_at=? WHERE id=?",
                (now, job_id),
            )
            self._event(connection, job_id, now, "import_confirmed", "import confirmed")
            return "import_confirmed"
