"""Closed M3 campaign contract and serial coordinator for guarded M2 native jobs.

Campaign children are independent one-use M2 plans. Every child is journaled
and transactionally reserved *before* the M2 dispatcher may consume its intent.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import time
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from . import resolve_test_queue as queue
from . import resolve_test_queue_native as native

CAMPAIGN_SCHEMA = "vera.resolve-test-campaign/v1"
CAMPAIGN_ID_PATTERN = re.compile(r"resolve-campaign-[a-f0-9]{32}\Z")
MAX_CASES = 100  # capacity ceiling, never a required campaign size
MAX_TRIALS = 200
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ELAPSED_SECONDS = 6 * 3600
MAX_DISK_BYTES = 4 * 1024**3
_PLAN_KEYS = frozenset(
    {
        "schema",
        "name",
        "order",
        "runAt",
        "deadlineAt",
        "maxElapsedSeconds",
        "maxDiskBytes",
        "cases",
        "trials",
    }
)
_CASE_KEYS = frozenset({"id", "comparisonKey"})
_TRIAL_KEYS = frozenset(
    {
        "id",
        "caseId",
        "variant",
        "round",
        "cacheMode",
        "sourceCommit",
        "plan",
        "planSha256",
    }
)
_VARIANTS = frozenset({"single", "baseline", "candidate"})
_CACHE_MODES = frozenset({"warm", "isolated_fresh"})


def _non_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise queue.QueueError("duplicate JSON object key")
        value[key] = item
    return value


def read_campaign_file(path: Path) -> object:
    """Read at most 2 MiB of regular, non-symlinked JSON; M2 keeps its 128 KiB cap."""
    queue.reject_unsafe_path(path, "campaign plan path")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise queue.QueueError("campaign input cannot be opened safely") from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > MAX_FILE_BYTES
            or metadata.st_nlink != 1
        ):
            raise queue.QueueError("campaign plan must be a regular file <=2 MiB")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            raise queue.QueueError("campaign plan exceeds 2 MiB")
        return json.loads(
            content,
            object_pairs_hook=_non_duplicate_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                queue.QueueError("invalid JSON number")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise queue.QueueError("campaign input must be valid JSON") from exc
    finally:
        os.close(descriptor)


def _native_request(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Read pinned one-use request identity without executing or launching it.

    Full M2 preflight (release, attestation, current package) is mandatory again
    immediately before phase-2 activation. This is not proof of native success.
    """
    native_fields = cast(Mapping[str, Any], plan["native"])
    path = Path(native_fields["requestPath"])
    native._no_symlinks(path)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise queue.QueueError("native request is missing or unsafe") from exc
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_mode & 0o222
            or info.st_size > 65536
        ):
            raise queue.QueueError("native request must be an immutable regular file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            content = stream.read(65537)
    finally:
        os.close(fd)
    if (
        len(content) > 65536
        or hashlib.sha256(content).hexdigest() != native_fields["requestSha256"]
    ):
        raise queue.QueueError("native request bytes differ from pinned SHA-256")
    try:
        request = json.loads(content, object_pairs_hook=_non_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise queue.QueueError("native request is not valid JSON") from exc
    if not isinstance(request, dict) or set(request) != native._REQUEST_KEYS:
        raise queue.QueueError("native request has unsupported fields")
    if (
        request["schemaVersion"] != native.REQUEST_SCHEMA
        or request["action"] != "build"
        or request["authorizeNewNonproduction"] is not True
        or request["externalScripting"] != "Local"
        or any(
            request[key] != native_fields[other]
            for key, other in (
                ("releaseSha256", "releaseSha256"),
                ("attestationSha256", "attestationSha256"),
                ("projectName", "projectName"),
                ("timelineName", "timelineName"),
            )
        )
    ):
        raise queue.QueueError("native request identity/authorization differs")
    paths = {
        key: native._absolute_path(request[key], key)
        for key in ("attestationPath", "packageDir", "evidenceDir")
    }
    evidence = paths["evidenceDir"].resolve()
    for protected in (
        path.parent.parent.resolve(),
        paths["packageDir"].resolve(),
        paths["attestationPath"].resolve(),
    ):
        if evidence.is_relative_to(protected) or protected.is_relative_to(evidence):
            raise queue.QueueError(
                "native evidence destination overlaps protected input"
            )
    return cast(dict[str, Any], request)


def order_campaign_trials(
    trials: Sequence[Mapping[str, Any]],
    *,
    mode: str,
) -> list[dict[str, Any]]:
    """Fixed declaration order or bounded A/B then B/A pairs by ascending round."""
    if not isinstance(mode, str) or mode not in {"fixed", "alternating"}:
        raise queue.QueueError("unsupported campaign order")
    if mode == "fixed":
        return [dict(item) for item in trials]
    groups: dict[str, dict[int, dict[str, dict[str, Any]]]] = {}
    for item in trials:
        case_id, round_, variant = (
            item.get("caseId"),
            item.get("round"),
            item.get("variant"),
        )
        if (
            not isinstance(case_id, str)
            or type(round_) is not int
            or not 1 <= round_ <= 5
            or not isinstance(variant, str)
            or variant not in {"baseline", "candidate"}
        ):
            raise queue.QueueError(
                "alternating requires bounded baseline/candidate pairs"
            )
        pair = groups.setdefault(case_id, {}).setdefault(round_, {})
        if variant in pair:
            raise queue.QueueError("duplicate variant in alternating round")
        pair[variant] = dict(item)
    result: list[dict[str, Any]] = []
    for rounds in groups.values():
        if sorted(rounds) != list(range(1, len(rounds) + 1)):
            raise queue.QueueError("alternating rounds must be consecutive from one")
        for round_, pair in sorted(rounds.items()):
            if set(pair) != {"baseline", "candidate"}:
                raise queue.QueueError("incomplete baseline/candidate pair")
            order = (
                ("baseline", "candidate") if round_ % 2 else ("candidate", "baseline")
            )
            result.extend(pair[variant] for variant in order)
    return result


def validate_campaign_plan(source: object) -> dict[str, Any]:
    """Validate a fully declared campaign, preserving separate one-use M2 plans."""
    if not isinstance(source, dict) or set(source) != _PLAN_KEYS:
        raise queue.QueueError("campaign requires exact closed plan keys")
    data = dict(source)
    if data["schema"] != CAMPAIGN_SCHEMA:
        raise queue.QueueError("unsupported campaign schema")
    queue.simple_id(data["name"], "campaign name")
    if not isinstance(data["order"], str) or data["order"] not in {
        "fixed",
        "alternating",
    }:
        raise queue.QueueError("campaign order must be fixed or alternating")
    max_elapsed = queue.limited_int(
        data["maxElapsedSeconds"], "maxElapsedSeconds", 1, MAX_ELAPSED_SECONDS
    )
    queue.limited_int(data["maxDiskBytes"], "maxDiskBytes", 1048576, MAX_DISK_BYTES)
    start, deadline = queue.dt(data["runAt"]), queue.dt(data["deadlineAt"])
    if not start < deadline or (deadline - start).total_seconds() > max_elapsed:
        raise queue.QueueError(
            "campaign deadline must follow start within aggregate time cap"
        )
    data["runAt"], data["deadlineAt"] = queue.iso(start), queue.iso(deadline)
    cases = data["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise queue.QueueError("campaign requires 1..100 cases (100 is only a maximum)")
    case_map: dict[str, str] = {}
    for row in cases:
        if not isinstance(row, dict) or set(row) != _CASE_KEYS:
            raise queue.QueueError("invalid campaign case keys")
        case_id = queue.simple_id(row["id"], "case id")
        if case_id in case_map:
            raise queue.QueueError("duplicate campaign case id")
        case_map[case_id] = queue.simple_id(row["comparisonKey"], "comparisonKey")
    trials = data["trials"]
    if not isinstance(trials, list) or not 1 <= len(trials) <= MAX_TRIALS:
        raise queue.QueueError("campaign requires 1..200 trials")
    seen_ids: set[str] = set()
    seen_requests: set[str] = set()
    seen_targets: set[str] = set()
    seen_evidence: set[str] = set()
    seen_slots: set[tuple[str, int, str]] = set()
    seen_cases: set[str] = set()
    rounds: dict[str, set[int]] = {key: set() for key in case_map}
    normalized: list[dict[str, Any]] = []
    for trial in trials:
        if not isinstance(trial, dict) or set(trial) != _TRIAL_KEYS:
            raise queue.QueueError("invalid campaign trial keys")
        trial_id = queue.simple_id(trial["id"], "trial id")
        case_id = queue.simple_id(trial["caseId"], "trial caseId")
        variant = trial["variant"]
        round_ = queue.limited_int(trial["round"], "trial round", 1, 5)
        if (
            case_id not in case_map
            or not isinstance(variant, str)
            or variant not in _VARIANTS
            or not isinstance(trial["cacheMode"], str)
            or trial["cacheMode"] not in _CACHE_MODES
        ):
            raise queue.QueueError("unknown case, variant or cache mode")
        if trial_id in seen_ids or (case_id, round_, variant) in seen_slots:
            raise queue.QueueError("duplicate trial identity")
        if not isinstance(
            trial["sourceCommit"], str
        ) or not queue.COMMIT_PATTERN.fullmatch(trial["sourceCommit"]):
            raise queue.QueueError("trial sourceCommit must be a pinned commit")
        child = trial["plan"]
        if not isinstance(child, dict) or not native.is_native(child):
            raise queue.QueueError("campaign children must be native v2 plans")
        if "runAt" not in child or "deadlineAt" not in child:
            raise queue.QueueError(
                "every child must have explicit immutable time bounds"
            )
        try:
            normalized_child = native.validate_native_plan(child)
        except ValueError as exc:
            raise queue.QueueError(f"invalid child native plan: {exc}") from exc
        if normalized_child != child:
            raise queue.QueueError(
                "child native plan must be fully normalized before freezing"
            )
        child_digest = hashlib.sha256(queue.canonical(normalized_child)).hexdigest()
        if (
            not isinstance(trial["planSha256"], str)
            or trial["planSha256"] != child_digest
        ):
            raise queue.QueueError("child plan SHA-256 mismatch")
        if "sourceCommit" in child and child["sourceCommit"] != trial["sourceCommit"]:
            raise queue.QueueError("child source commit differs from trial commit")
        child_start, child_end = queue.dt(child["runAt"]), queue.dt(child["deadlineAt"])
        if child_start > deadline or child_end < start or child_end > deadline:
            raise queue.QueueError("child deadline/schedule exceeds campaign bounds")
        request = _native_request(normalized_child)
        request_sha = normalized_child["native"]["requestSha256"]
        target = normalized_child["targetId"]
        evidence = request["evidenceDir"]
        if (
            request_sha in seen_requests
            or target in seen_targets
            or evidence in seen_evidence
            or normalized_child["native"]["projectName"] in seen_targets
        ):
            raise queue.QueueError(
                "duplicate native request, target or evidence identity"
            )
        seen_requests.add(request_sha)
        seen_targets.add(target)
        seen_targets.add(normalized_child["native"]["projectName"])
        seen_evidence.add(evidence)
        seen_ids.add(trial_id)
        seen_slots.add((case_id, round_, variant))
        rounds[case_id].add(round_)
        seen_cases.add(case_id)
        normalized.append({**trial, "plan": normalized_child})
    if seen_cases != set(case_map):
        raise queue.QueueError(
            "each declared campaign case requires at least one trial"
        )
    for case_id, values in rounds.items():
        if sorted(values) != list(range(1, max(values) + 1)):
            raise queue.QueueError(f"nonconsecutive rounds for {case_id}")
    data["trials"] = order_campaign_trials(normalized, mode=data["order"])
    return data


def enqueue_campaign(store: queue.Store, path: Path) -> str:
    """Atomically record the immutable campaign and step identities, not effects."""
    plan = validate_campaign_plan(read_campaign_file(path))
    # Enqueue is a pure attended preparation step. Prove all installed v2
    # requests/releases/attestations/packages now, then phase 2 rechecks at
    # activation. This does not acquire native ownership or start Resolve.
    for trial in plan["trials"]:
        try:
            native.preflight(trial["plan"])
        except ValueError as exc:
            raise queue.QueueError("campaign child native preflight refused") from exc
    content = queue.canonical(plan)
    if len(content) > MAX_FILE_BYTES:
        raise queue.QueueError("normalized campaign exceeds 2 MiB")
    digest = hashlib.sha256(content).hexdigest()
    campaign_id = f"resolve-campaign-{uuid.uuid4().hex}"
    folder = store.root / campaign_id
    folder.mkdir(mode=0o700)
    queue.atomic_write(folder / "plan.json", content)
    (folder / "plan.json").chmod(0o400)
    queue.sync_directory(store.root)
    try:
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for trial in plan["trials"]:
                request_sha = trial["plan"]["native"]["requestSha256"]
                if db.execute(
                    "SELECT 1 FROM native_attempts WHERE request_sha=?", (request_sha,)
                ).fetchone():
                    raise queue.QueueError("native request already reserved by M2")
            db.execute(
                "INSERT INTO campaigns(id,state,submitted_at,run_at,deadline_at,"
                "plan_sha,max_elapsed_seconds,max_disk_bytes) "
                "VALUES(?,'queued',?,?,?,?,?,?)",
                (
                    campaign_id,
                    queue.iso(queue.now_utc()),
                    queue.dt(plan["runAt"]).timestamp(),
                    queue.dt(plan["deadlineAt"]).timestamp(),
                    digest,
                    plan["maxElapsedSeconds"],
                    plan["maxDiskBytes"],
                ),
            )
            for ordinal, trial in enumerate(plan["trials"]):
                child = trial["plan"]
                db.execute(
                    "INSERT INTO campaign_trials(campaign_id,ordinal,trial_id,"
                    "case_id,variant,round,plan_sha,request_sha,target_id,"
                    "evidence_dir) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        campaign_id,
                        ordinal,
                        trial["id"],
                        trial["caseId"],
                        trial["variant"],
                        trial["round"],
                        trial["planSha256"],
                        child["native"]["requestSha256"],
                        child["targetId"],
                        _native_request(child)["evidenceDir"],
                    ),
                )
            db.execute(
                "INSERT INTO campaign_events(campaign_id,at,kind,detail) "
                "VALUES(?,?,?,?)",
                (campaign_id, queue.iso(queue.now_utc()), "enqueued", "frozen"),
            )
    except BaseException:
        # The orphaned immutable folder is harmless if SQLite refused the plan.
        raise
    return campaign_id


def load_frozen_campaign(store: queue.Store, campaign_id: str) -> dict[str, Any]:
    """Refuse changed parent bytes, child identity drift, or unsafe native inputs."""
    if not CAMPAIGN_ID_PATTERN.fullmatch(campaign_id):
        raise queue.QueueError("invalid campaign ID")
    with store.connect() as db:
        campaign = db.execute(
            "SELECT plan_sha FROM campaigns WHERE id=?", (campaign_id,)
        ).fetchone()
        steps = db.execute(
            "SELECT ordinal,trial_id,case_id,variant,round,plan_sha,"
            "request_sha,target_id,evidence_dir "
            "FROM campaign_trials WHERE campaign_id=? ORDER BY ordinal",
            (campaign_id,),
        ).fetchall()
    if campaign is None:
        raise queue.QueueError("unknown campaign")
    folder = store.root / campaign_id
    content = folder / "plan.json"
    try:
        descriptor = os.open(content, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise queue.QueueError("frozen campaign plan unavailable") from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_mode & 0o222
            or metadata.st_size > MAX_FILE_BYTES
        ):
            raise queue.QueueError(
                "frozen campaign plan is not an immutable regular file"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            frozen = stream.read(MAX_FILE_BYTES + 1)
    finally:
        os.close(descriptor)
    if (
        len(frozen) > MAX_FILE_BYTES
        or hashlib.sha256(frozen).hexdigest() != campaign["plan_sha"]
    ):
        raise queue.QueueError("frozen campaign plan changed")
    try:
        parsed = json.loads(frozen, object_pairs_hook=_non_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise queue.QueueError("frozen campaign plan JSON unreadable") from exc
    plan = validate_campaign_plan(parsed)
    if queue.canonical(plan) != frozen or len(steps) != len(plan["trials"]):
        raise queue.QueueError("frozen campaign plan/step count differs")
    for i, (row, trial) in enumerate(zip(steps, plan["trials"], strict=True)):
        child = trial["plan"]
        identity = (
            i,
            trial["id"],
            trial["caseId"],
            trial["variant"],
            trial["round"],
            trial["planSha256"],
            child["native"]["requestSha256"],
            child["targetId"],
            _native_request(child)["evidenceDir"],
        )
        if tuple(row) != identity:
            raise queue.QueueError("frozen campaign step identity changed")
    return plan


def _event(db: Any, campaign_id: str, kind: str, detail: str) -> None:
    """Only fixed, non-private reason codes may enter the campaign journal."""
    db.execute(
        "INSERT INTO campaign_events(campaign_id,at,kind,detail) VALUES(?,?,?,?)",
        (campaign_id, queue.iso(queue.now_utc()), kind, detail),
    )


def _stop(
    db: Any, campaign_id: str, state: str, reason: str, *, cancel_pending: bool = False
) -> None:
    now = queue.iso(queue.now_utc())
    db.execute(
        "UPDATE campaigns SET state=?,reason=?,ended_at=?,version=version+1 "
        "WHERE id=? AND state IN ('queued','running')",
        (state, reason, now, campaign_id),
    )
    if cancel_pending:
        db.execute(
            "UPDATE campaign_trials SET state='canceled',outcome='canceled',ended_at=? "
            "WHERE campaign_id=? AND state='pending'",
            (now, campaign_id),
        )
    _event(db, campaign_id, state, reason)


def _child_record(db: Any, campaign_id: str) -> Any:
    return db.execute(
        "SELECT * FROM campaign_trials WHERE campaign_id=? "
        "AND state!='completed_verified' ORDER BY ordinal LIMIT 1",
        (campaign_id,),
    ).fetchone()


def _sync_child(store: queue.Store, campaign_id: str, ordinal: int) -> None:
    """Reflect only a guarded M2 terminal state; do not infer native success."""
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        step = db.execute(
            "SELECT * FROM campaign_trials WHERE campaign_id=? AND ordinal=?",
            (campaign_id, ordinal),
        ).fetchone()
        if step is None or not step["child_job_id"]:
            raise queue.QueueError("campaign child binding missing")
        job = db.execute(
            "SELECT * FROM jobs WHERE id=?", (step["child_job_id"],)
        ).fetchone()
        attempt = db.execute(
            "SELECT * FROM native_attempts WHERE job_id=?",
            (step["child_job_id"],),
        ).fetchone()
        if (
            job is None
            or attempt is None
            or job["plan_sha"] != step["plan_sha"]
            or attempt["request_sha"] != step["request_sha"]
            or job["attempt"] != 1
        ):
            _stop(db, campaign_id, "unknown", "child_binding_changed")
            return
        state = job["state"]
        if state in {"queued", "running"}:
            return
        if state == "completed_verified" and not (
            attempt["intent_at"] and attempt["native_verified"] == 1
        ):
            state = "unknown"
        if step["state"] != state:
            db.execute(
                "UPDATE campaign_trials SET state=?,outcome=?,started_at=?,ended_at=? "
                "WHERE campaign_id=? AND ordinal=? AND child_job_id=?",
                (
                    state,
                    state,
                    job["started_at"],
                    job["ended_at"],
                    campaign_id,
                    ordinal,
                    step["child_job_id"],
                ),
            )
            _event(db, campaign_id, "child_terminal", state)
        if state != "completed_verified":
            disposition = (
                "unknown"
                if state == "unknown"
                else "canceled"
                if state == "canceled"
                else "blocked"
                if state == "blocked_native"
                else "failed"
            )
            _stop(db, campaign_id, disposition, f"child_{state}", cancel_pending=True)


def _run_bound_child(store: queue.Store, campaign_id: str, step: Any) -> bool:
    """Resume before-intent only; once M2 wrote intent, observe and NEVER start."""
    child_id = cast(str, step["child_job_id"])
    with store.connect() as db:
        job = db.execute("SELECT * FROM jobs WHERE id=?", (child_id,)).fetchone()
        attempt = db.execute(
            "SELECT intent_at FROM native_attempts WHERE job_id=?", (child_id,)
        ).fetchone()
        campaign = db.execute(
            "SELECT cancel_pending FROM campaigns WHERE id=?", (campaign_id,)
        ).fetchone()
    if job is None or attempt is None or campaign is None:
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            _stop(db, campaign_id, "unknown", "missing_child_native_record")
        return True
    if job["state"] in {"running", "unknown"} and attempt["intent_at"]:
        # Even a lost start reply / crashed worker with an UNKNOWN parent may
        # only query the exact retained request and invocation.
        queue.reconcile_native(store, child_id, worker_locked=True)
    elif job["state"] == "running" and not attempt["intent_at"]:
        if campaign["cancel_pending"]:
            queue.finish(
                store, child_id, job["worker_id"], "canceled", "before_native_intent"
            )
        elif _native_slot_busy(store):
            # After a crash-before-intent another M2 worker may have claimed
            # the host slot. Never consume our first native intent into it.
            return False
        else:
            # No intent has ever been committed: the only safe restart window
            # in which a previously activated child can begin its FIRST start.
            queue.run_native(store, child_id, job["worker_id"], worker_locked=True)
    _sync_child(store, campaign_id, step["ordinal"])
    return True


def _native_slot_busy(store: queue.Store) -> bool:
    """Never bypass a foreign M2 pending/running or uncertain native owner."""
    with store.connect() as db:
        occupied = db.execute(
            "SELECT j.id,j.state FROM jobs j "
            "LEFT JOIN campaign_trials c ON c.child_job_id=j.id "
            "WHERE c.child_job_id IS NULL AND "
            "(j.state='running' OR (j.state='queued' AND j.run_at<=?)) "
            "ORDER BY j.submitted_at LIMIT 1",
            (time.time(),),
        ).fetchone()
        unsafe = db.execute(
            "SELECT j.id,j.state FROM jobs j JOIN native_attempts n "
            "ON n.job_id=j.id WHERE n.intent_at IS NOT NULL "
            "AND j.state IN ('running','unknown','failed_native','blocked_native') "
            "ORDER BY j.submitted_at LIMIT 1"
        ).fetchone()
    if unsafe:
        if unsafe["state"] in {"running", "unknown"}:
            queue.reconcile_native(store, unsafe["id"], worker_locked=True)
        return True
    return occupied is not None


def _activate_child(
    store: queue.Store, campaign_id: str, ordinal: int, plan: Mapping[str, Any]
) -> bool:
    """Freeze job file, then *atomically* link job + one-use native attempt.

    If killed between file creation and the SQLite commit, an unreferenced
    directory remains but cannot dispatch. If killed after commit, the next
    tick sees this same child and its durable intent (or absence of intent).
    """
    child_id = f"resolve-test-{uuid.uuid4().hex}"
    worker_id = uuid.uuid4().hex
    frozen = queue.canonical(plan)
    digest = hashlib.sha256(frozen).hexdigest()
    folder = store.jobdir(child_id)
    folder.mkdir(mode=0o700)
    queue.atomic_write(folder / "plan.json", frozen)
    (folder / "plan.json").chmod(0o400)
    queue.sync_directory(store.root)
    started = queue.iso(queue.now_utc())
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        campaign = db.execute(
            "SELECT * FROM campaigns WHERE id=?", (campaign_id,)
        ).fetchone()
        step = db.execute(
            "SELECT * FROM campaign_trials WHERE campaign_id=? AND ordinal=?",
            (campaign_id, ordinal),
        ).fetchone()
        if (
            campaign is None
            or campaign["state"] not in {"queued", "running"}
            or campaign["cancel_pending"]
            or campaign["pause_after_active"]
            or step is None
            or step["state"] != "pending"
            or step["child_job_id"] is not None
            or digest != step["plan_sha"]
            or plan["native"]["requestSha256"] != step["request_sha"]
            or plan["targetId"] != step["target_id"]
        ):
            return False
        db.execute(
            "INSERT INTO jobs(id,state,submitted_at,run_at,deadline_at,"
            "started_at,plan_sha,worker_id,attempt) "
            "VALUES(?,'running',?,?,?,?,?,?,1)",
            (
                child_id,
                started,
                queue.dt(plan["runAt"]).timestamp(),
                queue.dt(plan["deadlineAt"]).timestamp(),
                started,
                digest,
                worker_id,
            ),
        )
        db.execute(
            "INSERT INTO native_attempts(job_id,request_sha,locator) VALUES(?,?,?)",
            (child_id, step["request_sha"], queue.canonical(plan["native"]).decode()),
        )
        db.execute(
            "UPDATE campaign_trials SET child_job_id=?,state='running',started_at=? "
            "WHERE campaign_id=? AND ordinal=? AND child_job_id IS NULL",
            (child_id, started, campaign_id, ordinal),
        )
        db.execute(
            "UPDATE campaigns SET state='running',started_at=COALESCE(started_at,?),"
            "version=version+1 WHERE id=?",
            (started, campaign_id),
        )
        store.append(db, child_id, "running", "campaign_native_worker")
        _event(db, campaign_id, "child_activated", f"ordinal:{ordinal}")
    return True


def campaign_worker_once(store: queue.Store) -> bool:
    """One due campaign step under M2's shared lock; never poll indefinitely.

    Multiple workers (including M2's own worker) are serialized per queue
    root; the guarded native host owner is rechecked by M2/parent at dispatch.
    """
    with (store.root / "worker.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        with store.connect() as db:
            row = db.execute(
                "SELECT * FROM campaigns WHERE state='running' "
                "OR (state='queued' AND run_at<=?) "
                "ORDER BY CASE state WHEN 'running' THEN 0 ELSE 1 END,"
                "run_at,id LIMIT 1",
                (time.time(),),
            ).fetchone()
        if row is None:
            return False
        campaign_id = cast(str, row["id"])
        now = time.time()
        if row["state"] == "queued" and row["run_at"] > now:
            return False
        try:
            plan = load_frozen_campaign(store, campaign_id)
        except (OSError, ValueError, KeyError, TypeError):
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                _stop(db, campaign_id, "unknown", "frozen_campaign_integrity_refused")
            return True
        with store.connect() as db:
            first = _child_record(db, campaign_id)
            flags = db.execute(
                "SELECT cancel_pending,pause_after_active,started_at "
                "FROM campaigns WHERE id=?",
                (campaign_id,),
            ).fetchone()
        if first is not None and first["child_job_id"]:
            try:
                return _run_bound_child(store, campaign_id, first)
            except Exception:
                # A crash/lost reply never permits redispatch after intent.
                # The next invocation reads SQLite before doing anything.
                return True
        if flags["cancel_pending"]:
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                _stop(
                    db,
                    campaign_id,
                    "canceled",
                    "pending_trials_canceled",
                    cancel_pending=True,
                )
            return True
        if flags["pause_after_active"]:
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "UPDATE campaigns SET state='paused',reason='paused_after_active',"
                    "version=version+1 WHERE id=? AND state IN ('queued','running')",
                    (campaign_id,),
                )
                _event(db, campaign_id, "paused", "paused_after_active")
            return True
        if first is None:
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                _stop(
                    db,
                    campaign_id,
                    "completed_verified",
                    "all_children_native_verified",
                )
            return True
        if first["state"] != "pending":
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                _stop(db, campaign_id, "unknown", "unexpected_child_state")
            return True
        elapsed = (
            (queue.now_utc() - queue.dt(flags["started_at"])).total_seconds()
            if flags["started_at"]
            else 0.0
        )
        if (
            now >= row["deadline_at"]
            or elapsed >= row["max_elapsed_seconds"]
            or elapsed < 0
        ):
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                _stop(
                    db,
                    campaign_id,
                    "blocked",
                    "campaign_time_budget",
                    cancel_pending=True,
                )
            return True
        trial_plan = plan["trials"][first["ordinal"]]["plan"]
        if queue.dt(trial_plan["runAt"]).timestamp() > now:
            return False
        if now >= queue.dt(trial_plan["deadlineAt"]).timestamp():
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                _stop(
                    db,
                    campaign_id,
                    "blocked",
                    "child_deadline_before_start",
                    cancel_pending=True,
                )
            return True
        # Resource checks are conservative here; full recursive accounting and
        # resource reports are supplied by phase 3. No native launch on failure.
        if shutil.disk_usage(store.root).free < row["max_disk_bytes"]:
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                _stop(
                    db,
                    campaign_id,
                    "blocked",
                    "insufficient_campaign_space",
                    cancel_pending=True,
                )
            return True
        if _native_slot_busy(store):
            return False
        if not _activate_child(store, campaign_id, first["ordinal"], trial_plan):
            return True
        with store.connect() as db:
            activated = _child_record(db, campaign_id)
        if activated is not None and activated["child_job_id"]:
            try:
                _run_bound_child(store, campaign_id, activated)
            except Exception:
                # Preserve the in-flight child for same-identity restart.
                return True
        return True
