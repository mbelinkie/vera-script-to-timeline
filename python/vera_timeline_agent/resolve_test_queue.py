"""Persistent local test queue with mock v1 and opt-in guarded native v2 plans.

The queue is deliberately independent of the product build-job engine and of
the separate GitHub CI queue. It accepts only versioned declarative plans whose
adapters come from a closed allowlist: v1 mock adapters and one explicit v2
guarded native build. No plan supplies executable commands or imports.

SQLite (WAL, ``synchronous=FULL``) is authoritative. Derived ``status.json``,
``report.json`` and ``report.md`` files are rebuilt from it atomically whenever
a job is inspected or changes state. A single ``flock`` gives one worker at a
time per queue root. Mock orphans become unknown; native attempts reconcile
the same detached parent and never redispatch.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import platform
import plistlib
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from . import resolve_test_queue_native as native
from . import workflow_v2_parent as parent
from .resolve_native_owner import (
    NativeOwnerError,
    preflight_independent_disposable,
)

PLAN_SCHEMA = "vera.resolve-test-plan/v1"
REPORT_SCHEMA = "vera.resolve-test-report/v1"
MOCK_ADAPTERS = frozenset({"mock.pass", "mock.fail", "mock.block"})
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
JOB_PATTERN = re.compile(r"resolve-test-[a-f0-9]{32}\Z")
SHA_PATTERN = re.compile(r"[a-f0-9]{64}\Z")
COMMIT_PATTERN = re.compile(r"[a-f0-9]{40}\Z")
TERMINAL = frozenset(
    {
        "completed_simulated",
        "failed_simulated",
        "blocked_simulated",
        "canceled",
        "expired",
        "timed_out",
        "unknown",
        "completed_verified",
        "failed_native",
        "blocked_native",
    }
)
LAUNCH_LABEL = "org.vera.resolve-test-queue.m1"
PLAN_IDENTITY_KEYS = (
    "name",
    "fixtureId",
    "fixtureSha256",
    "targetId",
    "targetPolicy",
    "category",
    "sourceCommit",
    "runAt",
    "deadlineAt",
)
DEFAULT_ROOT = (
    Path.home() / "Library" / "Application Support" / "VERA" / "resolve-test-queue"
)


class QueueError(ValueError):
    """A refused request or a state that cannot be proven safe."""


def now_utc() -> datetime:
    return datetime.now(UTC)


def dt(value: str) -> datetime:
    if not isinstance(value, str):
        raise QueueError("date/time must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise QueueError("date/time must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise QueueError("date/time must include timezone")
    return parsed.astimezone(UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def reject_unsafe_path(path: Path, label: str) -> None:
    """Refuse ``..`` traversal and a symlinked final path component.

    Ancestor symlinks owned by the operating system (for example macOS
    ``/var`` -> ``/private/var`` around the pytest temporary directory) are
    intentionally allowed so a legitimate absolute path is not misclassified.
    Plan files are additionally opened with ``O_NOFOLLOW``.
    """
    if ".." in path.parts:
        raise QueueError(f"{label} must not contain parent traversal")
    if path.is_symlink():
        raise QueueError(f"{label} must not reference symlinks")


def simple_id(value: object, name: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value) or ".." in value:
        raise QueueError(f"{name} must be a simple identifier, not a path")
    return value


def limited_int(value: object, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise QueueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def validate_plan(source: object, at: str | None = None) -> dict[str, Any]:
    if native.is_native(source):
        try:
            return native.validate_native_plan(source, at)
        except ValueError as error:
            raise QueueError(str(error)) from error
    if not isinstance(source, dict):
        raise QueueError("plan must be a JSON object")
    plan = cast(dict[str, Any], source.copy())
    required = {
        "schema",
        "name",
        "fixtureId",
        "fixtureSha256",
        "targetId",
        "targetPolicy",
        "category",
        "maxElapsedSeconds",
        "maxDiskBytes",
        "cases",
    }
    allowed = required | {"runAt", "deadlineAt", "sourceCommit"}
    if not required <= plan.keys() or not plan.keys() <= allowed:
        raise QueueError("missing or unsupported plan keys")
    if plan["schema"] != PLAN_SCHEMA or plan["targetPolicy"] != "synthetic_only":
        raise QueueError("M1 accepts synthetic_only plans only")
    for key in ("name", "fixtureId", "targetId", "category"):
        simple_id(plan[key], key)
    if not plan["fixtureId"].startswith("synthetic-") or not plan[
        "targetId"
    ].startswith("disposable-"):
        raise QueueError("fixture/target must use synthetic-/disposable- prefixes")
    if not isinstance(plan["fixtureSha256"], str) or not SHA_PATTERN.fullmatch(
        plan["fixtureSha256"]
    ):
        raise QueueError("fixtureSha256 must be lower-case 64-digit hex")
    limited_int(plan["maxElapsedSeconds"], "maxElapsedSeconds", 1, 14400)
    limited_int(plan["maxDiskBytes"], "maxDiskBytes", 1048576, 1073741824)
    if "sourceCommit" in plan and (
        not isinstance(plan["sourceCommit"], str)
        or not COMMIT_PATTERN.fullmatch(plan["sourceCommit"])
    ):
        raise QueueError("sourceCommit must be a lowercase 40-digit hex commit")
    cases = plan["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= 32:
        raise QueueError("cases must be an array of 1..32 items")
    seen: set[str] = set()
    count = 0
    for item in cases:
        if not isinstance(item, dict) or set(item) != {
            "id",
            "adapter",
            "iterations",
            "delayMs",
        }:
            raise QueueError("invalid case keys")
        case = cast(dict[str, Any], item)
        identifier = simple_id(case["id"], "case.id")
        if identifier in seen:
            raise QueueError("duplicate case ID")
        seen.add(identifier)
        if not isinstance(case["adapter"], str) or case["adapter"] not in MOCK_ADAPTERS:
            raise QueueError(
                "non-allowlisted adapter; real/native/command adapters disabled"
            )
        count += limited_int(case["iterations"], "iterations", 1, 3)
        limited_int(case["delayMs"], "delayMs", 0, 300000)
    if count > 64:
        raise QueueError("max 64 trials per job")
    scheduled = dt(at or plan.get("runAt", iso(now_utc())))
    deadline = (
        dt(plan["deadlineAt"])
        if "deadlineAt" in plan
        else scheduled + timedelta(seconds=plan["maxElapsedSeconds"] + 3600)
    )
    if deadline <= scheduled:
        raise QueueError("deadlineAt must follow runAt")
    plan["runAt"] = iso(scheduled)
    plan["deadlineAt"] = iso(deadline)
    return plan


def folder_bytes(folder: Path) -> int:
    """Sum regular-file sizes, tolerating files replaced by concurrent readers."""
    total = 0
    try:
        entries = list(folder.iterdir())
    except OSError:
        return total
    for item in entries:
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def sync_directory(path: Path) -> None:
    directory = os.open(path, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def atomic_write(path: Path, value: bytes) -> None:
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}")
    try:
        with temp.open("xb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        sync_directory(path.parent)
    finally:
        temp.unlink(missing_ok=True)


class Store:
    """SQLite is authoritative; report files are rebuildable durable snapshots."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        reject_unsafe_path(self.root, "queue root")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    run_at REAL NOT NULL,
                    deadline_at REAL NOT NULL,
                    started_at TEXT,
                    ended_at TEXT,
                    plan_sha TEXT NOT NULL,
                    worker_id TEXT,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    reason TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    detail TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trials (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    iteration INTEGER NOT NULL,
                    adapter TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    wall_seconds REAL NOT NULL,
                    outcome TEXT NOT NULL,
                    native_verified INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS native_attempts (
                    job_id TEXT PRIMARY KEY,
                    request_sha TEXT NOT NULL UNIQUE,
                    locator TEXT NOT NULL,
                    intent_at TEXT,
                    invocation_id TEXT,
                    parent_state TEXT,
                    native_verified INTEGER NOT NULL DEFAULT 0
                );
                -- M3 is additive: existing M1/M2 records and one-use intents
                -- retain their original schema, identities and meaning.
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    state TEXT NOT NULL DEFAULT 'queued',
                    submitted_at TEXT NOT NULL,
                    run_at REAL NOT NULL,
                    deadline_at REAL NOT NULL,
                    plan_sha TEXT NOT NULL,
                    max_elapsed_seconds INTEGER NOT NULL,
                    max_disk_bytes INTEGER NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    pause_after_active INTEGER NOT NULL DEFAULT 0,
                    cancel_pending INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT,
                    ended_at TEXT,
                    reason TEXT
                );
                CREATE TABLE IF NOT EXISTS campaign_trials (
                    campaign_id TEXT NOT NULL REFERENCES campaigns(id),
                    ordinal INTEGER NOT NULL CHECK(ordinal >= 0 AND ordinal < 200),
                    trial_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    variant TEXT NOT NULL
                        CHECK(variant IN ('single','baseline','candidate')),
                    round INTEGER NOT NULL CHECK(round BETWEEN 1 AND 5),
                    plan_sha TEXT NOT NULL,
                    request_sha TEXT NOT NULL UNIQUE,
                    target_id TEXT NOT NULL UNIQUE,
                    evidence_dir TEXT NOT NULL UNIQUE,
                    child_job_id TEXT UNIQUE REFERENCES jobs(id),
                    state TEXT NOT NULL DEFAULT 'pending',
                    outcome TEXT,
                    started_at TEXT,
                    ended_at TEXT,
                    environment_sha TEXT,
                    timing_spans_json TEXT,
                    PRIMARY KEY(campaign_id, ordinal),
                    UNIQUE(campaign_id, trial_id)
                );
                CREATE TABLE IF NOT EXISTS campaign_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT NOT NULL REFERENCES campaigns(id),
                    at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    detail TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS campaign_events_by_campaign
                    ON campaign_events(campaign_id, seq);
                CREATE TABLE IF NOT EXISTS campaign_commands (
                    command_id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL REFERENCES campaigns(id),
                    at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    version INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS campaign_heartbeats (
                    campaign_id TEXT PRIMARY KEY REFERENCES campaigns(id),
                    seq INTEGER NOT NULL DEFAULT 0,
                    at TEXT NOT NULL
                );
                -- M4 owns its own closed, non-replayable reverse stages. No
                -- M2/M3 identity, adapter or historical operation is changed.
                CREATE TABLE IF NOT EXISTS reverse_jobs (
                    id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    plan_sha TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    run_at REAL NOT NULL,
                    deadline_at REAL NOT NULL,
                    started_at TEXT,
                    ended_at TEXT,
                    updated_at TEXT NOT NULL,
                    reason TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS reverse_stages (
                    job_id TEXT NOT NULL REFERENCES reverse_jobs(id),
                    ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 0 AND 3),
                    name TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending',
                    intent_at TEXT,
                    operation_id TEXT NOT NULL UNIQUE,
                    receipt_path TEXT,
                    receipt_sha TEXT UNIQUE,
                    verified_at TEXT,
                    PRIMARY KEY(job_id, ordinal)
                );
                CREATE TABLE IF NOT EXISTS reverse_targets (
                    name TEXT PRIMARY KEY,
                    project_uid TEXT NOT NULL UNIQUE,
                    timeline_uid TEXT NOT NULL UNIQUE,
                    job_id TEXT NOT NULL REFERENCES reverse_jobs(id)
                );
                CREATE TABLE IF NOT EXISTS reverse_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL REFERENCES reverse_jobs(id),
                    at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    detail TEXT NOT NULL
                );
            """)
            # Existing phase-1/2 stores predate optional authenticated M3
            # measurement metadata. Never alter M1/M2 tables or report bytes.
            columns = {
                row["name"] for row in db.execute("PRAGMA table_info(campaign_trials)")
            }
            for name in ("environment_sha", "timing_spans_json"):
                if name not in columns:
                    db.execute(f"ALTER TABLE campaign_trials ADD COLUMN {name} TEXT")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(
            self.root / "queue.sqlite3", timeout=20, isolation_level=None
        )
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=20000")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            if db.in_transaction:
                db.commit()
        except BaseException:
            if db.in_transaction:
                db.rollback()
            raise
        finally:
            db.close()

    def jobdir(self, job_id: str) -> Path:
        if not JOB_PATTERN.fullmatch(job_id):
            raise QueueError("invalid job ID")
        result = self.root / job_id
        if result.is_symlink():
            raise QueueError("job directory must not be a symlink")
        return result

    def get(self, job_id: str) -> sqlite3.Row:
        self.jobdir(job_id)
        with self.connect() as db:
            value = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if value is None:
            raise QueueError("unknown job")
        return cast(sqlite3.Row, value)

    def append(
        self, db: sqlite3.Connection, job_id: str, kind: str, detail: str
    ) -> None:
        db.execute(
            "INSERT INTO events(job_id,at,kind,detail) VALUES(?,?,?,?)",
            (job_id, iso(now_utc()), kind, detail),
        )

    def publish(self, job_id: str) -> dict[str, Any]:
        folder = self.jobdir(job_id)
        with (self.root / "publish.lock").open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            with self.connect() as db:
                db.execute("BEGIN")
                row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
                if row is None:
                    raise QueueError("unknown job")
                journal = [
                    dict(item)
                    for item in db.execute(
                        "SELECT seq,at,kind,detail FROM events "
                        "WHERE job_id=? ORDER BY seq",
                        (job_id,),
                    )
                ]
                trials = [
                    dict(item)
                    for item in db.execute(
                        "SELECT case_id,iteration,adapter,started_at,ended_at,"
                        "wall_seconds,outcome,native_verified "
                        "FROM trials WHERE job_id=? ORDER BY seq",
                        (job_id,),
                    )
                ]
                attempt = db.execute(
                    "SELECT intent_at,invocation_id,parent_state,native_verified "
                    "FROM native_attempts WHERE job_id=?",
                    (job_id,),
                ).fetchone()
            folder.mkdir(mode=0o700, exist_ok=True)
            identity = frozen_plan_identity(self, job_id, row["plan_sha"])
            status = {
                "jobId": job_id,
                "state": row["state"],
                "reason": row["reason"],
                "submittedAt": row["submitted_at"],
                "scheduledAt": iso(datetime.fromtimestamp(row["run_at"], UTC)),
                "deadlineAt": iso(datetime.fromtimestamp(row["deadline_at"], UTC)),
                "startedAt": row["started_at"],
                "endedAt": row["ended_at"],
                "attempt": row["attempt"],
                "workerId": row["worker_id"],
                "cancelRequested": bool(row["cancel_requested"]),
                "planSha256": row["plan_sha"],
                "nativeVerified": bool(attempt and attempt["native_verified"]),
            }
            report = {
                "schema": REPORT_SCHEMA,
                "status": status,
                "plan": identity,
                "planIntegrity": (
                    "verified" if identity is not None else "unavailable_or_changed"
                ),
                "trials": trials,
                "journal": journal,
                "syntheticOnly": attempt is None,
                "nativeVerified": status["nativeVerified"],
                "verifiedStatistics": None,
                "warning": (
                    "Native build readback only; no render or PCM proof."
                    if attempt
                    else "M1 mock records are not real Resolve or output proof."
                ),
            }
            if attempt:
                report["native"] = dict(attempt)
            atomic_write(folder / "status.json", canonical(status))
            atomic_write(folder / "report.json", canonical(report))
            if identity is None:
                identity_line = (
                    "Plan identity: unavailable; frozen plan bytes are missing, "
                    "changed or unreadable.\n\n"
                )
            else:
                identity_line = (
                    f"Fixture: {identity['fixtureId']} "
                    f"(SHA-256 {identity['fixtureSha256']}); "
                    f"target: {identity['targetId']}; "
                    f"category: {identity['category']}.\n\n"
                )
            markdown = (
                f"# Offline queue {job_id}\n\n"
                f"State: {row['state']}; reason: {row['reason'] or 'none'}.\n\n"
                f"{identity_line}"
                f"Plan SHA-256: {row['plan_sha']}.\n\n"
                f"Recorded synthetic trials: {len(trials)}. Native proof: NO.\n\n"
                "No Resolve, actual media, save/reopen or performance conclusions.\n"
            )
            if attempt:
                markdown = (
                    f"# Native queue {job_id}\n\n"
                    f"State: {row['state']}; reason: {row['reason'] or 'none'}.\n\n"
                    f"{identity_line}"
                    "Native save/reopen/readback verified: "
                    f"{status['nativeVerified']}.\n\n"
                    "No render or PCM proof. Live/unknown work is never replayed.\n"
                )
            atomic_write(folder / "report.md", markdown.encode("utf-8"))
            return report


def read_plan_file(path: Path) -> object:
    reject_unsafe_path(path, "plan path")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 131072:
            raise QueueError("plan must be a regular JSON file <=128 KiB")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read(131073)
        if len(content) > 131072:
            raise QueueError("plan too large")
        return json.loads(content)
    finally:
        os.close(descriptor)


def frozen_plan_identity(
    store: Store, job_id: str, digest: str
) -> dict[str, Any] | None:
    """Return identity fields of the intact frozen plan, or ``None``.

    A missing, changed, unreadable or non-object frozen plan yields ``None`` so
    report publication stays available while explicitly marking the loss of
    plan integrity; it never reconstructs a plan from mutable input.
    """
    path = store.jobdir(job_id) / "plan.json"
    try:
        if path.is_symlink() or not path.is_file():
            return None
        frozen = path.read_bytes()
    except OSError:
        return None
    if hashlib.sha256(frozen).hexdigest() != digest:
        return None
    try:
        parsed = json.loads(frozen)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    plan = cast(dict[str, Any], parsed)
    return {key: plan.get(key) for key in PLAN_IDENTITY_KEYS}


def enqueue(store: Store, plan_path: Path, at: str | None = None) -> str:
    plan = validate_plan(read_plan_file(plan_path), at)
    frozen = canonical(plan)
    digest = hashlib.sha256(frozen).hexdigest()
    job_id = f"resolve-test-{uuid.uuid4().hex}"
    folder = store.jobdir(job_id)
    folder.mkdir(mode=0o700)
    atomic_write(folder / "plan.json", frozen)
    (folder / "plan.json").chmod(0o400)
    sync_directory(store.root)
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "INSERT INTO jobs(id,state,submitted_at,run_at,deadline_at,plan_sha) "
            "VALUES(?,?,?,?,?,?)",
            (
                job_id,
                "queued",
                iso(now_utc()),
                dt(plan["runAt"]).timestamp(),
                dt(plan["deadlineAt"]).timestamp(),
                digest,
            ),
        )
        if native.is_native(plan):
            from . import resolve_test_queue_m4 as reverse

            if reverse.target_reserved(db, plan["native"]["projectName"]):
                raise QueueError("native target reserved by a guarded reverse workflow")
            existing = db.execute(
                "SELECT 1 FROM campaign_trials WHERE request_sha=?",
                (plan["native"]["requestSha256"],),
            ).fetchone()
            if existing:
                raise QueueError("native request already reserved by campaign")
            db.execute(
                "INSERT INTO native_attempts(job_id,request_sha,locator) VALUES(?,?,?)",
                (
                    job_id,
                    plan["native"]["requestSha256"],
                    canonical(plan["native"]).decode(),
                ),
            )
        store.append(db, job_id, "enqueued", plan["targetPolicy"])
    store.publish(job_id)
    return job_id


def cancel(store: Store, job_id: str) -> None:
    store.get(job_id)
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()
        attempt = db.execute(
            "SELECT intent_at FROM native_attempts WHERE job_id=?", (job_id,)
        ).fetchone()
        if row["state"] in TERMINAL and not (
            attempt and attempt["intent_at"] and row["state"] == "unknown"
        ):
            return
        if row["state"] == "queued":
            db.execute(
                "UPDATE jobs SET state='canceled',ended_at=? WHERE id=?",
                (iso(now_utc()), job_id),
            )
            store.append(db, job_id, "canceled", "before_execution")
        else:
            db.execute("UPDATE jobs SET cancel_requested=1 WHERE id=?", (job_id,))
            store.append(
                db,
                job_id,
                "cancel_requested",
                (
                    "native_reconciliation_required"
                    if attempt
                    else "cooperative_mock_boundary"
                ),
            )
    store.publish(job_id)


def finish(store: Store, job_id: str, worker_id: str, state: str, reason: str) -> None:
    if state not in TERMINAL:
        raise QueueError("cannot finish with nonterminal state")
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if state == "completed_simulated":
            current = db.execute(
                "SELECT cancel_requested FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
            if current is not None and current["cancel_requested"]:
                state = "canceled"
                reason = "mock_stopped_without_native_effect"
        changed = db.execute(
            "UPDATE jobs SET state=?,reason=?,ended_at=? "
            "WHERE id=? AND state='running' AND worker_id=?",
            (state, reason, iso(now_utc()), job_id, worker_id),
        )
        if changed.rowcount != 1:
            raise QueueError("worker cannot finish an unowned job")
        store.append(db, job_id, state, reason)
    store.publish(job_id)


def run_mock(store: Store, job_id: str, worker_id: str) -> None:
    row = store.get(job_id)
    path = store.jobdir(job_id) / "plan.json"
    if path.is_symlink() or not path.is_file():
        finish(store, job_id, worker_id, "unknown", "missing_frozen_plan")
        return
    try:
        frozen = path.read_bytes()
    except OSError:
        finish(store, job_id, worker_id, "unknown", "unreadable_frozen_plan")
        return
    if hashlib.sha256(frozen).hexdigest() != row["plan_sha"]:
        finish(store, job_id, worker_id, "unknown", "changed_frozen_plan")
        return
    try:
        plan = validate_plan(json.loads(frozen))
    except (QueueError, json.JSONDecodeError):
        finish(store, job_id, worker_id, "unknown", "invalid_frozen_plan")
        return
    start = time.monotonic()
    folder = store.jobdir(job_id)
    for case in plan["cases"]:
        for iteration in range(1, case["iterations"] + 1):
            started = now_utc()
            t0 = time.monotonic()
            while True:
                current = store.get(job_id)
                if current["cancel_requested"]:
                    finish(
                        store,
                        job_id,
                        worker_id,
                        "canceled",
                        "mock_stopped_without_native_effect",
                    )
                    return
                if time.monotonic() - start >= plan["maxElapsedSeconds"]:
                    finish(
                        store,
                        job_id,
                        worker_id,
                        "timed_out",
                        "job_elapsed_budget_exhausted",
                    )
                    return
                if time.time() >= current["deadline_at"]:
                    finish(
                        store, job_id, worker_id, "expired", "absolute_deadline_reached"
                    )
                    return
                if (
                    folder_bytes(folder) > plan["maxDiskBytes"]
                    or shutil.disk_usage(store.root).free < 1048576
                ):
                    finish(
                        store,
                        job_id,
                        worker_id,
                        "blocked_simulated",
                        "disk_budget_or_space",
                    )
                    return
                remaining = case["delayMs"] / 1000.0 - (time.monotonic() - t0)
                if remaining <= 0:
                    break
                time.sleep(min(0.05, remaining))
            result = case["adapter"].removeprefix("mock.") + "_simulated"
            finished = now_utc()
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "INSERT INTO trials(job_id,case_id,iteration,adapter,started_at,"
                    "ended_at,wall_seconds,outcome,native_verified) "
                    "VALUES(?,?,?,?,?,?,?,?,0)",
                    (
                        job_id,
                        case["id"],
                        iteration,
                        case["adapter"],
                        iso(started),
                        iso(finished),
                        time.monotonic() - t0,
                        result,
                    ),
                )
                store.append(db, job_id, "trial", f"{case['id']}:{iteration}:{result}")
            store.publish(job_id)
            if result == "fail_simulated":
                finish(
                    store, job_id, worker_id, "failed_simulated", f"case:{case['id']}"
                )
                return
            if result == "block_simulated":
                finish(
                    store, job_id, worker_id, "blocked_simulated", f"case:{case['id']}"
                )
                return
    finish(store, job_id, worker_id, "completed_simulated", "all_mock_cases_completed")


RESOLVE_PYTHON = Path(
    "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Resources/"
    "ResolvePython/ResolvePython"
)


def load_frozen_plan(store: Store, job_id: str) -> dict[str, Any]:
    row = store.get(job_id)
    path = store.jobdir(job_id) / "plan.json"
    content = path.read_bytes()
    if path.is_symlink() or hashlib.sha256(content).hexdigest() != row["plan_sha"]:
        raise QueueError("frozen plan changed")
    return validate_plan(json.loads(content))


def reconcile_native(store: Store, job_id: str, *, worker_locked: bool = False) -> None:
    """Read the same guarded operation; never dispatch from reconciliation."""
    if not worker_locked:
        with (store.root / "worker.lock").open("a+b") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            _reconcile_native_locked(store, job_id)
        return
    _reconcile_native_locked(store, job_id)


def _reconcile_native_locked(store: Store, job_id: str) -> None:
    with store.connect() as db:
        attempt = db.execute(
            "SELECT * FROM native_attempts WHERE job_id=?", (job_id,)
        ).fetchone()
    row = store.get(job_id)
    if (
        not attempt
        or not attempt["intent_at"]
        or row["state"] not in {"running", "unknown"}
    ):
        return
    locator = json.loads(attempt["locator"])
    response = parent.status(Path(locator["requestPath"]), attempt["request_sha"])
    verdict = native.classify_parent_status(
        response,
        request_sha256=attempt["request_sha"],
        project_name=locator["projectName"],
        timeline_name=locator["timelineName"],
        cancel_requested=bool(row["cancel_requested"]),
        release_sha256=locator["releaseSha256"],
        attestation_sha256=locator["attestationSha256"],
        expected=locator["expected"],
    )
    reason = verdict.reason
    state = {
        "live": "running",
        "verified": "completed_verified",
        "failed": "failed_native",
        "blocked": "blocked_native",
        "unknown": "unknown",
    }[verdict.disposition]
    verified = verdict.native_verified
    invocation: str | None = None
    completed_at: datetime | None = None
    parent_elapsed: float | None = None
    try:
        plan = load_frozen_plan(store, job_id)
        request = native.preflight(plan)
        intent = parent._read(Path(request["evidenceDir"]) / "queue-intent.json")
        if intent != {
            "jobId": job_id,
            "attempt": row["attempt"],
            "planSha256": row["plan_sha"],
            "requestSha256": attempt["request_sha"],
        }:
            raise QueueError("native intent belongs to another job")
        record = parent._read(Path(request["evidenceDir"]) / "parent.json")
        invocation = record["invocationId"]
        if (
            not isinstance(invocation, str)
            or not invocation
            or record["requestSha256"] != attempt["request_sha"]
            or record["requestPath"] != locator["requestPath"]
            or (attempt["invocation_id"] and invocation != attempt["invocation_id"])
        ):
            raise QueueError("parent identity changed")
        if state == "completed_verified" or response.get("state") == "terminal":
            elapsed = response.get("elapsedSeconds")
            if (
                isinstance(elapsed, bool)
                or not isinstance(elapsed, (int, float))
                or not math.isfinite(elapsed)
                or elapsed < 0
            ):
                raise ValueError("authenticated parent elapsed time is invalid")
            parent_elapsed = float(elapsed)
            completed_at_value = response.get("completedAt")
            if not isinstance(completed_at_value, str):
                raise ValueError("authenticated parent completion time is missing")
            completed_at = dt(completed_at_value)
            started_at = dt(row["started_at"])
            intent_at = dt(attempt["intent_at"])
            if intent_at < started_at or completed_at < intent_at:
                raise ValueError("authenticated parent completion predates dispatch")
            if state == "completed_verified":
                pre_dispatch = (intent_at - started_at).total_seconds()
                if completed_at.timestamp() >= row["deadline_at"]:
                    state, reason, verified = (
                        "timed_out",
                        "deadline_exceeded_native_completed",
                        False,
                    )
                elif parent_elapsed + pre_dispatch >= plan["maxElapsedSeconds"]:
                    state, reason, verified = (
                        "timed_out",
                        "elapsed_budget_exceeded_native_completed",
                        False,
                    )
                elif (
                    folder_bytes(Path(request["evidenceDir"]))
                    + folder_bytes(store.jobdir(job_id))
                    > plan["maxDiskBytes"]
                ):
                    state, reason, verified = (
                        "blocked_native",
                        "disk_budget_exceeded_native_completed",
                        False,
                    )
        elif state in {"running", "unknown"}:
            # Budget expiry does not prove native work stopped.
            elapsed = (now_utc() - dt(row["started_at"])).total_seconds()
            budget = None
            if time.time() >= row["deadline_at"]:
                budget = "deadline_exceeded"
            elif elapsed >= plan["maxElapsedSeconds"]:
                budget = "elapsed_budget_exceeded"
            elif (
                folder_bytes(Path(request["evidenceDir"]))
                + folder_bytes(store.jobdir(job_id))
                > plan["maxDiskBytes"]
            ):
                budget = "disk_budget_exceeded"
            elif shutil.disk_usage(store.root).free < plan["maxDiskBytes"]:
                budget = "insufficient_space"
            if budget:
                reason = (
                    budget
                    + "_native_"
                    + ("live" if state == "running" else "uncertain")
                )
        else:
            elapsed = response.get("elapsedSeconds")
            if (
                not isinstance(elapsed, bool)
                and isinstance(elapsed, (int, float))
                and math.isfinite(elapsed)
                and elapsed >= 0
            ):
                parent_elapsed = float(elapsed)
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        state, reason, verified = (
            "unknown",
            "native_identity_input_or_completion_clock_unavailable",
            False,
        )
    terminal = state not in {"running", "unknown"}
    finished_at = iso(completed_at) if completed_at is not None else iso(now_utc())
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        current = db.execute(
            "SELECT state,reason FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
        if current["state"] not in {"running", "unknown"}:
            return
        db.execute(
            "UPDATE native_attempts SET invocation_id=COALESCE(invocation_id,?),"
            "parent_state=?,native_verified=? WHERE job_id=?",
            (invocation, response.get("state", "unknown"), int(verified), job_id),
        )
        db.execute(
            "UPDATE jobs SET state=?,reason=?,ended_at=? WHERE id=?",
            (state, reason, finished_at if terminal else None, job_id),
        )
        if current["state"] != state or current["reason"] != reason:
            store.append(db, job_id, state, reason)
        if terminal:
            db.execute(
                "INSERT INTO trials(job_id,case_id,iteration,adapter,"
                "started_at,ended_at,"
                "wall_seconds,outcome,native_verified) VALUES(?,?,1,?,?,?,?,?,?)",
                (
                    job_id,
                    "native-build",
                    "native.v2.guarded_build",
                    attempt["intent_at"],
                    finished_at,
                    parent_elapsed or 0.0,
                    state,
                    int(verified),
                ),
            )
    store.publish(job_id)


def run_native(
    store: Store, job_id: str, worker_id: str, *, worker_locked: bool = False
) -> None:
    """One preflight and one dispatch after a durable intent. No retries."""
    try:
        from . import resolve_test_queue_m4 as reverse

        if reverse.any_unresolved(store):
            raise QueueError("another M4 native target has an unclosed stage")
        plan = load_frozen_plan(store, job_id)
        request = native.preflight(plan)
        evidence = Path(request["evidenceDir"])
        if evidence.exists() and any(evidence.iterdir()):
            raise QueueError("native request/evidence already used")
        # The final parent rechecks under the exclusive host owner lock. This
        # first read-only check prevents consuming a queue intent needlessly.
        preflight_independent_disposable(plan["native"]["projectName"])
        if (
            folder_bytes(store.jobdir(job_id)) > plan["maxDiskBytes"]
            or shutil.disk_usage(store.root).free < plan["maxDiskBytes"]
        ):
            finish(store, job_id, worker_id, "blocked_native", "insufficient_space")
            return
    except NativeOwnerError:
        finish(store, job_id, worker_id, "blocked_native", "blocked_resource_owner")
        return
    except (OSError, ValueError, KeyError, TypeError):
        finish(store, job_id, worker_id, "blocked_native", "native_preflight_refused")
        return
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        elapsed = (now_utc() - dt(row["started_at"])).total_seconds()
        predispatch_result: tuple[str, str] | None = None
        if elapsed < 0:
            predispatch_result = (
                "blocked_native",
                "clock_uncertain_before_native_dispatch",
            )
        elif row["cancel_requested"]:
            predispatch_result = ("canceled", "before_native_dispatch")
        elif time.time() >= row["deadline_at"]:
            predispatch_result = ("expired", "before_native_dispatch")
        elif elapsed >= plan["maxElapsedSeconds"]:
            predispatch_result = ("timed_out", "before_native_dispatch")
        if predispatch_result is not None:
            state, reason = predispatch_result
            db.execute(
                "UPDATE jobs SET state=?,reason=?,ended_at=? WHERE id=?",
                (state, reason, iso(now_utc()), job_id),
            )
            store.append(db, job_id, state, reason)
            return
        changed = db.execute(
            "UPDATE native_attempts SET intent_at=? "
            "WHERE job_id=? AND intent_at IS NULL",
            (iso(now_utc()), job_id),
        )
        if changed.rowcount != 1:
            raise QueueError("native dispatch intent already consumed")
        store.append(db, job_id, "native_dispatch_intent", "one_use_guarded_build")
    try:
        evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
        parent._write(
            evidence / "queue-intent.json",
            {
                "jobId": job_id,
                "attempt": row["attempt"],
                "planSha256": row["plan_sha"],
                "requestSha256": plan["native"]["requestSha256"],
            },
        )
        sync_directory(evidence)
        start_result = parent.start(
            Path(plan["native"]["requestPath"]),
            plan["native"]["requestSha256"],
            RESOLVE_PYTHON,
            independent_disposable=True,
        )
        if start_result.get("state") == "busy":
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "UPDATE native_attempts SET parent_state='busy' WHERE job_id=?",
                    (job_id,),
                )
            finish(store, job_id, worker_id, "blocked_native", "blocked_resource_owner")
            return
    except NativeOwnerError:
        # The parent raises this only before reserving or launching our request.
        finish(store, job_id, worker_id, "blocked_native", "blocked_resource_owner")
        return
    except Exception:
        # A lost reply or spawn error cannot authorize a second invocation.
        pass
    reconcile_native(store, job_id, worker_locked=worker_locked)


def worker_once(store: Store) -> bool:
    """Execute at most one due job. Return False for busy/no-work."""
    with (store.root / "worker.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        from . import resolve_test_queue_m4 as reverse

        if reverse.worker_tick(store):
            return True
        with store.connect() as db:
            active_native = db.execute(
                "SELECT j.id,n.intent_at FROM jobs j "
                "JOIN native_attempts n ON j.id=n.job_id "
                "WHERE j.state IN ('running','unknown') AND n.intent_at IS NOT NULL "
                "ORDER BY j.submitted_at LIMIT 1"
            ).fetchone()
        if active_native and active_native["intent_at"]:
            reconcile_native(store, active_native["id"], worker_locked=True)
            return True
        orphaned: list[str] = []
        job_id: str | None = None
        worker_id = uuid.uuid4().hex
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # Campaign child ownership belongs to the M3 coordinator. A crash
            # before its durable native intent can safely continue that SAME
            # child; the ordinary M2 worker must not orphan it as mock work.
            old = db.execute(
                "SELECT j.id FROM jobs j LEFT JOIN campaign_trials c "
                "ON c.child_job_id=j.id WHERE j.state='running' "
                "AND c.child_job_id IS NULL"
            ).fetchall()
            for value in old:
                previous_id = cast(str, value["id"])
                db.execute(
                    "UPDATE jobs SET state='unknown',reason=?,ended_at=? WHERE id=?",
                    ("interrupted_worker_no_replay", iso(now_utc()), previous_id),
                )
                store.append(db, previous_id, "unknown", "interrupted_worker_no_replay")
                orphaned.append(previous_id)
            if not orphaned:
                selected = db.execute(
                    "SELECT j.id,j.deadline_at FROM jobs j "
                    "LEFT JOIN campaign_trials c ON c.child_job_id=j.id "
                    "WHERE j.state='queued' AND j.run_at<=? "
                    "AND c.child_job_id IS NULL "
                    "AND (NOT EXISTS (SELECT 1 FROM reverse_stages s WHERE "
                    "s.intent_at IS NOT NULL AND "
                    "s.state IN ('awaiting_operator','verifying','unknown')) "
                    "OR NOT EXISTS (SELECT 1 FROM native_attempts n "
                    "WHERE n.job_id=j.id)) "
                    "ORDER BY j.run_at,j.id LIMIT 1",
                    (time.time(),),
                ).fetchone()
                if selected is not None:
                    job_id = cast(str, selected["id"])
                    if time.time() >= selected["deadline_at"]:
                        db.execute(
                            "UPDATE jobs SET state='expired',reason=?,ended_at=? "
                            "WHERE id=?",
                            ("expired_before_start", iso(now_utc()), job_id),
                        )
                        store.append(db, job_id, "expired", "expired_before_start")
                    else:
                        db.execute(
                            "UPDATE jobs SET state='running',started_at=?,worker_id=?,"
                            "attempt=attempt+1 WHERE id=?",
                            (iso(now_utc()), worker_id, job_id),
                        )
                        store.append(db, job_id, "running", f"worker:{worker_id}")
        for previous_id in orphaned:
            store.publish(previous_id)
        if orphaned:
            # Recovery is never treated as permission to replay.
            return True
        if job_id is None:
            return False
        store.publish(job_id)
        if store.get(job_id)["state"] == "running":
            try:
                with store.connect() as db:
                    native_job = db.execute(
                        "SELECT 1 FROM native_attempts WHERE job_id=?", (job_id,)
                    ).fetchone()
                if native_job:
                    run_native(store, job_id, worker_id, worker_locked=True)
                else:
                    run_mock(store, job_id, worker_id)
            except Exception:
                # Do not invent or overwrite a result; preserve the journal and
                # refuse retry. A terminal state committed before a publication
                # failure stays authoritative.
                if store.get(job_id)["state"] == "running":
                    finish(
                        store,
                        job_id,
                        worker_id,
                        "unknown",
                        "unexpected_worker_failure",
                    )
        store.publish(job_id)
        return True


def agent_plist(root: Path, executable: str) -> bytes:
    """Pure LaunchAgent definition. Never install on import or in a test."""
    return plistlib.dumps(
        {
            "Label": LAUNCH_LABEL,
            "ProgramArguments": [
                executable,
                "-m",
                "vera_timeline_agent.resolve_test_queue",
                "--root",
                str(root),
                "worker",
                "once",
            ],
            "StartInterval": 60,
            "RunAtLoad": True,
            "ProcessType": "Background",
            "StandardOutPath": str(root / "launchd.stdout.log"),
            "StandardErrorPath": str(root / "launchd.stderr.log"),
        },
        sort_keys=True,
    )


def install_agent(store: Store) -> None:
    if platform.system() != "Darwin":
        raise QueueError("LaunchAgent installation is macOS only")
    plist = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_LABEL}.plist"
    plist.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Keep the venv interpreter path as-is: resolving a symlinked
    # ``.venv/bin/python`` would bypass the environment that imports this module.
    payload = agent_plist(store.root, sys.executable)
    if plist.is_symlink():
        raise QueueError("existing LaunchAgent differs; refusing overwrite")
    if plist.exists():
        if plist.read_bytes() != payload:
            raise QueueError("existing LaunchAgent differs; refusing overwrite")
        loaded = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCH_LABEL}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if loaded.returncode == 0:
            print("Matching LaunchAgent is already loaded.")
            return
    else:
        atomic_write(plist, payload)
    try:
        subprocess.run(
            ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        # Deliberately preserve the written plist for diagnostics, no repeated effect.
        raise QueueError(
            "launchctl bootstrap failed; inspect user's launchd domain"
        ) from exc
    print(f"Installed opt-in user LaunchAgent {LAUNCH_LABEL}")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Local mock queue and opt-in guarded native v2 build queue"
    )
    value.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    sub = value.add_subparsers(dest="command", required=True)
    new = sub.add_parser("enqueue")
    new.add_argument("--plan", type=Path, required=True)
    new.add_argument("--at")
    prepare = sub.add_parser("prepare-native")
    prepare.add_argument("--request", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--at")
    prepare.add_argument("--max-elapsed-seconds", type=int, default=900)
    prepare.add_argument("--max-disk-bytes", type=int, default=67108864)
    sub.add_parser("list")
    lookup = sub.add_parser("status")
    lookup.add_argument("job_id")
    report = sub.add_parser("report")
    report.add_argument("job_id")
    report.add_argument("--format", choices=("json", "markdown"), default="json")
    stop = sub.add_parser("cancel")
    stop.add_argument("job_id")
    worker = sub.add_parser("worker")
    worker.add_argument("action", choices=("once", "serve"))
    worker.add_argument("--interval", type=int, default=60)
    sub.add_parser("install-launchd")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    options = parser().parse_args(argv)
    try:
        store = Store(options.root)
        from . import resolve_test_queue_m4 as reverse

        if options.command == "enqueue":
            source = read_plan_file(options.plan)
            if isinstance(source, dict) and source.get("schema") == reverse.SCHEMA:
                print(reverse.enqueue(store, options.plan, at=options.at))
            else:
                print(enqueue(store, options.plan, options.at))
        elif options.command == "prepare-native":
            from .workflow_package import sha256
            from .workflow_v2 import load_verified_package_v2

            request_path = options.request.absolute()
            request = parent._read(request_path)
            package = load_verified_package_v2(
                Path(request["attestationPath"]), request["attestationSha256"]
            )
            build_id = package.attestation["buildId"]
            plan = validate_plan(
                {
                    "schema": native.NATIVE_SCHEMA,
                    "name": "native-guarded-build",
                    "fixtureId": "synthetic-" + build_id,
                    "fixtureSha256": request["attestationSha256"],
                    "targetId": "disposable-" + build_id,
                    "targetPolicy": "new_disposable_native",
                    "category": "native-save-reopen",
                    "maxElapsedSeconds": options.max_elapsed_seconds,
                    "maxDiskBytes": options.max_disk_bytes,
                    "cases": [
                        {
                            "id": "native-build",
                            "adapter": "native.v2.guarded_build",
                            "iterations": 1,
                            "delayMs": 0,
                        }
                    ],
                    "native": {
                        "requestPath": str(request_path),
                        "requestSha256": sha256(request_path),
                        "releaseSha256": request["releaseSha256"],
                        "attestationSha256": request["attestationSha256"],
                        "projectName": request["projectName"],
                        "timelineName": request["timelineName"],
                        "expected": native.expected_for_package(package),
                    },
                },
                options.at,
            )
            native.preflight(plan)
            reject_unsafe_path(options.output, "native plan output")
            with options.output.open("xb") as output:
                os.fchmod(output.fileno(), 0o600)
                output.write(canonical(plan))
                output.flush()
                os.fsync(output.fileno())
            sync_directory(options.output.absolute().parent)
            print("Prepared private native plan; no Resolve operation started.")
        elif options.command == "list":
            with store.connect() as db:
                result = [
                    dict(row)
                    for row in db.execute(
                        "SELECT id,state,submitted_at,started_at,ended_at FROM jobs "
                        "ORDER BY submitted_at DESC,id DESC"
                    )
                ]
                result.extend(
                    dict(row)
                    for row in db.execute(
                        "SELECT id,state,submitted_at,started_at,ended_at "
                        "FROM reverse_jobs ORDER BY submitted_at DESC,id DESC"
                    )
                )
            print(json.dumps(result, sort_keys=True))
        elif options.command == "status":
            if reverse.ID_RE.fullmatch(options.job_id):
                reverse.reconcile(store, options.job_id)
                status = reverse.publish(store, options.job_id)
            else:
                reconcile_native(store, options.job_id)
                status = store.publish(options.job_id)["status"]
            print(json.dumps(status, sort_keys=True))
        elif options.command == "report":
            if reverse.ID_RE.fullmatch(options.job_id):
                reverse.reconcile(store, options.job_id)
                report = reverse.publish(store, options.job_id)
            else:
                reconcile_native(store, options.job_id)
                report = store.publish(options.job_id)
            if options.format == "json":
                print(json.dumps(report, sort_keys=True))
            else:
                folder = (
                    reverse._jobdir(store, options.job_id)
                    if reverse.ID_RE.fullmatch(options.job_id)
                    else store.jobdir(options.job_id)
                )
                print((folder / "report.md").read_text(encoding="utf-8"))
        elif options.command == "cancel":
            if reverse.ID_RE.fullmatch(options.job_id):
                reverse.cancel(store, options.job_id)
                print(
                    json.dumps(reverse.publish(store, options.job_id), sort_keys=True)
                )
            else:
                cancel(store, options.job_id)
                print(
                    json.dumps(store.publish(options.job_id)["status"], sort_keys=True)
                )
        elif options.command == "worker":
            if options.action == "once":
                worker_once(store)
            else:
                limited_int(options.interval, "interval", 1, 3600)
                while True:
                    worker_once(store)
                    time.sleep(options.interval)
        elif options.command == "install-launchd":
            install_agent(store)
        return 0
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
        print(f"queue refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
