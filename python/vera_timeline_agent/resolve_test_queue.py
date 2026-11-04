"""Persistent M1 synthetic test queue. No native Resolve adapter exists here.

The queue is deliberately independent of the product build-job engine and of
the separate GitHub CI queue. It accepts only versioned declarative plans whose
adapters come from a hard-coded mock allowlist, so no plan can start a process,
touch media, or contact the network.

SQLite (WAL, ``synchronous=FULL``) is authoritative. Derived ``status.json``,
``report.json`` and ``report.md`` files are rebuilt from it atomically whenever
a job is inspected or changes state. A single ``flock`` gives one worker at a
time per queue root; a worker that finds a job left ``running`` by a dead
process records it as ``unknown`` and never redispatches it.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
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
            """)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(
            self.root / "queue.sqlite3", timeout=20, isolation_level=None
        )
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=20000")
        db.execute("PRAGMA synchronous=FULL")
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
        folder.mkdir(mode=0o700, exist_ok=True)
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
                "nativeVerified": False,
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
                "syntheticOnly": True,
                "nativeVerified": False,
                "verifiedStatistics": None,
                "warning": "M1 mock records are not real Resolve or output proof.",
            }
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
        store.append(db, job_id, "enqueued", "synthetic_only")
    store.publish(job_id)
    return job_id


def cancel(store: Store, job_id: str) -> None:
    store.get(job_id)
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row["state"] in TERMINAL:
            return
        if row["state"] == "queued":
            db.execute(
                "UPDATE jobs SET state='canceled',ended_at=? WHERE id=?",
                (iso(now_utc()), job_id),
            )
            store.append(db, job_id, "canceled", "before_execution")
        else:
            db.execute("UPDATE jobs SET cancel_requested=1 WHERE id=?", (job_id,))
            store.append(db, job_id, "cancel_requested", "cooperative_mock_boundary")
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


def worker_once(store: Store) -> bool:
    """Execute at most one due job. Return False for busy/no-work."""
    with (store.root / "worker.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        orphaned: list[str] = []
        job_id: str | None = None
        worker_id = uuid.uuid4().hex
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT id FROM jobs WHERE state='running'").fetchall()
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
                    "SELECT id,deadline_at FROM jobs WHERE state='queued' "
                    "AND run_at<=? ORDER BY run_at,id LIMIT 1",
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
        description="M1 offline synthetic test queue; no Resolve access"
    )
    value.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    sub = value.add_subparsers(dest="command", required=True)
    new = sub.add_parser("enqueue")
    new.add_argument("--plan", type=Path, required=True)
    new.add_argument("--at")
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
        if options.command == "enqueue":
            print(enqueue(store, options.plan, options.at))
        elif options.command == "list":
            with store.connect() as db:
                result = [
                    dict(row)
                    for row in db.execute(
                        "SELECT id,state,submitted_at,started_at,ended_at FROM jobs "
                        "ORDER BY submitted_at DESC,id DESC"
                    )
                ]
            print(json.dumps(result, sort_keys=True))
        elif options.command == "status":
            print(json.dumps(store.publish(options.job_id)["status"], sort_keys=True))
        elif options.command == "report":
            report = store.publish(options.job_id)
            if options.format == "json":
                print(json.dumps(report, sort_keys=True))
            else:
                print(
                    (store.jobdir(options.job_id) / "report.md").read_text(
                        encoding="utf-8"
                    )
                )
        elif options.command == "cancel":
            cancel(store, options.job_id)
            print(json.dumps(store.publish(options.job_id)["status"], sort_keys=True))
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
    except (QueueError, OSError, json.JSONDecodeError, sqlite3.Error) as exc:
        print(f"queue refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
