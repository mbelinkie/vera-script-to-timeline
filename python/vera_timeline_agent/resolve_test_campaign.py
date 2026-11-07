"""Closed M3 campaign contract and serial coordinator for guarded M2 native jobs.

Campaign children are independent one-use M2 plans. Every child is journaled
and transactionally reserved *before* the M2 dispatcher may consume its intent.
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
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, cast

from . import resolve_test_queue as queue
from . import resolve_test_queue_native as native
from . import workflow_v2_parent as parent

CAMPAIGN_SCHEMA = "vera.resolve-test-campaign/v1"
CAMPAIGN_ID_PATTERN = re.compile(r"resolve-campaign-[a-f0-9]{32}\Z")
MAX_CASES = 100  # capacity ceiling, never a required campaign size
MAX_TRIALS = 200
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ELAPSED_SECONDS = 6 * 3600
MAX_DISK_BYTES = 4 * 1024**3
CAMPAIGN_LAUNCH_LABEL = "org.vera.resolve-test-campaign-worker.m3"
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
_CONTROL_ACTIONS = frozenset({"pause", "resume", "cancel", "reconcile"})
_REASON_CODE = re.compile(r"[a-z][a-z0-9_:-]{0,100}\Z")
_TIMING_NAMES = frozenset(
    {"setup", "native_wait", "save", "reopen", "readback", "measurement"}
)


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
    protected_native_paths: list[tuple[Path, Path, Path]] = []
    variant_commits: dict[tuple[str, str], str] = {}
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
        variant_key = (case_id, variant)
        if variant_key in variant_commits and (
            variant_commits[variant_key] != trial["sourceCommit"]
        ):
            raise queue.QueueError("one case/variant cannot mix source commits")
        variant_commits[variant_key] = trial["sourceCommit"]
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
        native_paths = (
            Path(evidence).resolve(),
            Path(normalized_child["native"]["requestPath"]).resolve(),
            Path(request["packageDir"]).resolve(),
        )
        if (
            request_sha in seen_requests
            or target in seen_targets
            or evidence in seen_evidence
            or normalized_child["native"]["projectName"] in seen_targets
        ):
            raise queue.QueueError(
                "duplicate native request, target or evidence identity"
            )
        if any(
            a == b or a.is_relative_to(b) or b.is_relative_to(a)
            for previous in protected_native_paths
            for a in (native_paths[0],)
            for b in previous
        ) or any(
            a == b or a.is_relative_to(b) or b.is_relative_to(a)
            for previous in protected_native_paths
            for a in (native_paths[1], native_paths[2])
            for b in (previous[0],)
        ):
            raise queue.QueueError("campaign evidence overlaps another native input")
        seen_requests.add(request_sha)
        seen_targets.add(target)
        seen_targets.add(normalized_child["native"]["projectName"])
        seen_evidence.add(evidence)
        protected_native_paths.append(native_paths)
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


def _safe_reason(value: object) -> str | None:
    """Reports never repeat raw exception text, filesystem paths or secrets."""
    return value if isinstance(value, str) and _REASON_CODE.fullmatch(value) else None


def _safe_stamp(value: object) -> str | None:
    try:
        return queue.iso(queue.dt(cast(str, value))) if value is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def _owned_bytes(
    store: queue.Store,
    campaign_id: str,
    *,
    exclude_projections: bool = False,
    frozen_plan: Mapping[str, Any] | None = None,
) -> int:
    """Count all campaign-owned trees (including evidence), without following links.

    SQLite and unrelated M2 work are not billed to a campaign. Reject links,
    hardlinks and special files rather than undercounting resources. Caller
    must treat any accounting error as a BLOCKED result before next dispatch.
    """
    if not CAMPAIGN_ID_PATTERN.fullmatch(campaign_id):
        raise queue.QueueError("invalid campaign ID")
    plan = (
        frozen_plan
        if frozen_plan is not None
        else load_frozen_campaign(store, campaign_id)
    )
    with store.connect() as db:
        records = db.execute(
            "SELECT child_job_id,evidence_dir FROM campaign_trials "
            "WHERE campaign_id=? ORDER BY ordinal",
            (campaign_id,),
        ).fetchall()
    if len(records) != len(plan["trials"]):
        raise queue.QueueError("campaign resource identities differ")
    paths = [store.root / campaign_id]
    projections = (
        {
            store.root / campaign_id / name
            for name in ("status.json", "report.json", "report.md")
        }
        if exclude_projections
        else set()
    )
    for record, trial in zip(records, plan["trials"], strict=True):
        if record["evidence_dir"] != _native_request(trial["plan"])["evidenceDir"]:
            raise queue.QueueError("campaign evidence identity changed")
        if record["child_job_id"]:
            paths.append(store.jobdir(record["child_job_id"]))
            paths.append(Path(record["evidence_dir"]))
    total = 0
    visited: set[tuple[int, int]] = set()
    scanned = 0

    def walk(path: Path) -> None:
        nonlocal total, scanned
        if path in projections:
            return
        scanned += 1
        if scanned > 50000:
            raise queue.QueueError("campaign resource tree exceeds accounting limit")
        try:
            info = path.lstat()
        except FileNotFoundError:
            # A not-yet-created native evidence directory is normal.
            return
        if stat.S_ISLNK(info.st_mode) or not (
            stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)
        ):
            raise queue.QueueError("campaign resource tree contains unsafe entries")
        key = (info.st_dev, info.st_ino)
        if key in visited or (info.st_nlink > 1 and stat.S_ISREG(info.st_mode)):
            raise queue.QueueError("campaign resource tree has shared entries")
        visited.add(key)
        if stat.S_ISREG(info.st_mode):
            total += info.st_size
        else:
            with os.scandir(path) as entries:
                for entry in entries:
                    walk(Path(entry.path))

    for path in paths:
        walk(path)
    return total


def _budget_problem(
    store: queue.Store,
    campaign_id: str,
    record: Any,
    frozen_plan: Mapping[str, Any],
) -> str | None:
    """Never convert clock or storage uncertainty into a successful campaign."""
    try:
        now = queue.now_utc()
        if now.timestamp() >= record["deadline_at"]:
            return "campaign_deadline_exceeded"
        if record["started_at"] is not None:
            elapsed = (now - queue.dt(record["started_at"])).total_seconds()
            if not math.isfinite(elapsed) or elapsed < 0:
                return "campaign_clock_uncertain"
            if elapsed >= record["max_elapsed_seconds"]:
                return "campaign_elapsed_exceeded"
        with (store.root / "publish.lock").open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if (
                _owned_bytes(store, campaign_id, frozen_plan=frozen_plan)
                > record["max_disk_bytes"]
            ):
                return "campaign_disk_budget_exceeded"
        if shutil.disk_usage(store.root).free < record["max_disk_bytes"]:
            return "insufficient_campaign_space"
    except (OSError, ValueError, TypeError, OverflowError):
        return "campaign_resources_unverifiable"
    return None


def _campaign_limits_match(record: Any, plan: Mapping[str, Any]) -> bool:
    """SQLite scheduling/limits may not silently widen the frozen plan."""
    return bool(
        record["max_elapsed_seconds"] == plan["maxElapsedSeconds"]
        and record["max_disk_bytes"] == plan["maxDiskBytes"]
        and record["run_at"] == queue.dt(plan["runAt"]).timestamp()
        and record["deadline_at"] == queue.dt(plan["deadlineAt"]).timestamp()
    )


def _capture_verified_measurement(step: Any, attempt: Any) -> tuple[str, str] | None:
    """Second read-only parent authentication pins the native environment.

    The M2 classifier is authoritative; this supplements, never replaces,
    its identity, one-use and verified-readback guards. A missing/ambiguous
    environment leaves a successful child visible but *not comparable*.
    """
    if (
        not attempt["intent_at"]
        or attempt["native_verified"] != 1
        or not attempt["invocation_id"]
    ):
        return None
    try:
        request_path = Path(json.loads(attempt["locator"])["requestPath"])
        response = parent.status(request_path, attempt["request_sha"])
        locator = json.loads(attempt["locator"])
        verdict = native.classify_parent_status(
            response,
            request_sha256=attempt["request_sha"],
            project_name=locator["projectName"],
            timeline_name=locator["timelineName"],
            release_sha256=locator["releaseSha256"],
            attestation_sha256=locator["attestationSha256"],
            expected=locator["expected"],
        )
        session = parent._read(Path(step["evidence_dir"]) / "parent.json")
        if (
            response.get("state") != "terminal"
            or verdict.disposition != "verified"
            or verdict.native_verified is not True
            or session.get("invocationId") != attempt["invocation_id"]
            or session.get("requestSha256") != attempt["request_sha"]
            or session.get("requestPath") != str(request_path)
        ):
            return None
        result = response["result"]
        connected = result.get("connected")
        if not isinstance(connected, dict) or connected.get("edition") != "studio":
            return None
        version, build = connected.get("version"), connected.get("build")
        if (
            not isinstance(version, str)
            or not 1 <= len(version) <= 40
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", version)
            or type(build) not in (str, int)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", str(build))
        ):
            return None
        environment = hashlib.sha256(
            queue.canonical(
                {
                    "edition": "studio",
                    "version": version,
                    "build": str(build),
                    "system": platform.system(),
                    "machine": platform.machine(),
                    "host": platform.node(),
                }
            )
        ).hexdigest()
        spans = result.get("timingSpansSeconds", {})
        if not isinstance(spans, dict) or not set(spans) <= _TIMING_NAMES:
            return None
        if any(
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not 0 <= value <= MAX_ELAPSED_SECONDS
            for value in spans.values()
        ):
            return None
        spans = {name: float(value) for name, value in spans.items()}
        return environment, queue.canonical(spans).decode().strip()
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return None


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
        measurement = (
            _capture_verified_measurement(step, attempt)
            if state == "completed_verified"
            else None
        )
        if step["state"] != state:
            db.execute(
                "UPDATE campaign_trials SET state=?,outcome=?,started_at=?,ended_at=?,"
                "environment_sha=?,timing_spans_json=? "
                "WHERE campaign_id=? AND ordinal=? AND child_job_id=?",
                (
                    state,
                    state,
                    job["started_at"],
                    job["ended_at"],
                    measurement[0] if measurement else None,
                    measurement[1] if measurement else None,
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
            "SELECT * FROM campaigns WHERE id=?", (campaign_id,)
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
        # A bound child without native intent is an admitted *reservation*,
        # not an exemption from the finite campaign/child budgets. This is
        # safe to stop because no native start has ever been authorized.
        bounds = load_frozen_campaign(store, campaign_id)
        expired = time.time() >= job["deadline_at"]
        problem = _budget_problem(store, campaign_id, campaign, bounds)
        if expired or problem:
            queue.finish(
                store,
                child_id,
                job["worker_id"],
                "blocked_native",
                (
                    "child_deadline_before_intent"
                    if expired
                    else "campaign_budget_before_intent"
                ),
            )
        elif campaign["cancel_pending"]:
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
            "AND j.state IN ('running','unknown') "
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


def _campaign_worker_tick(store: queue.Store) -> bool:
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
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO campaign_heartbeats(campaign_id,seq,at) "
                "VALUES(?,1,?) ON CONFLICT(campaign_id) DO UPDATE SET "
                "seq=seq+1,at=excluded.at",
                (campaign_id, queue.iso(queue.now_utc())),
            )
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
        if not _campaign_limits_match(row, plan):
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                _stop(
                    db,
                    campaign_id,
                    "unknown",
                    "campaign_frozen_limits_changed",
                    cancel_pending=True,
                )
            return True
        # Every child was already authenticated by _sync_child. Do not let a
        # later LaunchAgent tick or a pause override a completed campaign.
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
        problem = _budget_problem(store, campaign_id, row, plan)
        if problem:
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                _stop(db, campaign_id, "blocked", problem, cancel_pending=True)
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


def campaign_worker_once(store: queue.Store) -> bool:
    """Tick once; publish settled snapshots, with live reads served from SQLite.

    Avoid rereading every immutable native request on every active heartbeat.
    The status/report CLI and private monitor rebuild a current snapshot on
    demand; a terminal or paused worker produces a final on-disk snapshot.
    """
    changed = _campaign_worker_tick(store)
    if changed:
        with store.connect() as db:
            latest = db.execute(
                "SELECT c.id,c.state FROM campaigns c "
                "JOIN campaign_heartbeats h ON h.campaign_id=c.id "
                "ORDER BY h.at DESC,h.seq DESC LIMIT 1"
            ).fetchone()
        if latest is not None and latest["state"] not in {"queued", "running"}:
            publish_campaign(store, latest["id"])
    return changed


def control_campaign(
    store: queue.Store,
    campaign_id: str,
    *,
    action: str,
    command_id: str,
    actor: str,
    authorized: bool = False,
) -> dict[str, Any]:
    """Durable, exactly-once operator intent, never permission to dispatch.

    A trusted local CLI or authenticated web handler must explicitly authorize
    the caller. A replay returns the original audit result without repeating
    effects; reusing a command ID for different arguments is refused.
    """
    if not authorized:
        raise queue.QueueError("campaign control requires authenticated operator")
    if not CAMPAIGN_ID_PATTERN.fullmatch(campaign_id):
        raise queue.QueueError("invalid campaign ID")
    queue.simple_id(command_id, "command id")
    queue.simple_id(actor, "operator identity")
    if action not in _CONTROL_ACTIONS:
        raise queue.QueueError("unsupported campaign control")
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute(
            "SELECT * FROM campaign_commands WHERE command_id=?", (command_id,)
        ).fetchone()
        if previous is not None:
            if (
                previous["campaign_id"] != campaign_id
                or previous["action"] != action
                or previous["actor"] != actor
            ):
                raise queue.QueueError("command replay changed scope or arguments")
            return {
                "commandId": command_id,
                "action": action,
                "outcome": previous["outcome"],
                "version": previous["version"],
                "replayed": True,
            }
        record = db.execute(
            "SELECT * FROM campaigns WHERE id=?", (campaign_id,)
        ).fetchone()
        if record is None:
            raise queue.QueueError("unknown campaign")
        state = record["state"]
        outcome = "accepted"
        if action == "pause":
            if state in {"queued", "running"}:
                db.execute(
                    "UPDATE campaigns SET pause_after_active=1,"
                    "state=CASE WHEN state='queued' THEN 'paused' ELSE state END,"
                    "reason=CASE WHEN state='queued' THEN 'paused_before_start' "
                    "ELSE reason END,version=version+1 WHERE id=?",
                    (campaign_id,),
                )
            elif state == "paused":
                outcome = "already_paused"
            else:
                raise queue.QueueError("cannot pause terminal campaign")
        elif action == "resume":
            if record["cancel_pending"]:
                raise queue.QueueError("cannot resume canceled campaign")
            if state == "paused":
                db.execute(
                    "UPDATE campaigns SET pause_after_active=0,reason=NULL,"
                    "state=CASE WHEN started_at IS NULL THEN 'queued' "
                    "ELSE 'running' END,"
                    "version=version+1 WHERE id=?",
                    (campaign_id,),
                )
            elif state in {"queued", "running"} and record["pause_after_active"]:
                db.execute(
                    "UPDATE campaigns SET pause_after_active=0,version=version+1 "
                    "WHERE id=?",
                    (campaign_id,),
                )
            else:
                raise queue.QueueError("campaign is not paused")
        elif action == "cancel":
            if state in {"queued", "paused"}:
                now = queue.iso(queue.now_utc())
                db.execute(
                    "UPDATE campaigns SET state='canceled',cancel_pending=1,"
                    "reason='operator_canceled_pending',ended_at=?,"
                    "version=version+1 WHERE id=?",
                    (now, campaign_id),
                )
                db.execute(
                    "UPDATE campaign_trials SET state='canceled',outcome='canceled',"
                    "ended_at=? WHERE campaign_id=? AND state='pending'",
                    (now, campaign_id),
                )
            elif state == "running":
                if record["cancel_pending"]:
                    outcome = "already_requested"
                else:
                    db.execute(
                        "UPDATE campaigns SET cancel_pending=1,version=version+1 "
                        "WHERE id=?",
                        (campaign_id,),
                    )
            else:
                raise queue.QueueError("cannot cancel terminal campaign")
        elif action == "reconcile":
            # No worker tick or parent.start may be called from this path.
            outcome = "read_only_observation_requested"
        updated = db.execute(
            "SELECT version FROM campaigns WHERE id=?", (campaign_id,)
        ).fetchone()
        db.execute(
            "INSERT INTO campaign_commands(command_id,campaign_id,at,actor,"
            "action,outcome,version) VALUES(?,?,?,?,?,?,?)",
            (
                command_id,
                campaign_id,
                queue.iso(queue.now_utc()),
                actor,
                action,
                outcome,
                updated["version"],
            ),
        )
        _event(db, campaign_id, "operator_" + action, outcome)
    if action == "reconcile":
        reconcile_campaign(store, campaign_id)
    return {
        "commandId": command_id,
        "action": action,
        "outcome": outcome,
        "version": updated["version"],
        "replayed": False,
    }


def reconcile_campaign(store: queue.Store, campaign_id: str) -> bool:
    """Observe only the already-bound native request under M2's worker lock."""
    if not CAMPAIGN_ID_PATTERN.fullmatch(campaign_id):
        raise queue.QueueError("invalid campaign ID")
    with (store.root / "worker.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        with store.connect() as db:
            record = db.execute(
                "SELECT state FROM campaigns WHERE id=?", (campaign_id,)
            ).fetchone()
            if record is None:
                raise queue.QueueError("unknown campaign")
            step = db.execute(
                "SELECT * FROM campaign_trials WHERE campaign_id=? "
                "AND child_job_id IS NOT NULL AND state IN ('running','unknown') "
                "ORDER BY ordinal LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if step is None:
                return True
            attempt = db.execute(
                "SELECT intent_at FROM native_attempts WHERE job_id=?",
                (step["child_job_id"],),
            ).fetchone()
        if attempt is None:
            raise queue.QueueError("missing bound native intent")
        if attempt["intent_at"]:
            queue.reconcile_native(store, step["child_job_id"], worker_locked=True)
            _sync_child(store, campaign_id, step["ordinal"])
        return True


def _verified_observation(step: Any, job: Any, attempt: Any, native_row: Any) -> bool:
    """All of the M2 job, receipt and native row must agree on one identity."""
    identity_matches = bool(
        job is not None
        and attempt is not None
        and native_row is not None
        and step["state"] == "completed_verified"
        and job["state"] == "completed_verified"
        and job["attempt"] == 1
        and job["plan_sha"] == step["plan_sha"]
        and attempt["request_sha"] == step["request_sha"]
        and attempt["native_verified"] == 1
        and attempt["parent_state"] == "terminal"
        and attempt["intent_at"]
        and attempt["invocation_id"]
        and native_row["native_verified"] == 1
        and native_row["outcome"] == "completed_verified"
        and native_row["started_at"] == attempt["intent_at"]
        and native_row["ended_at"] == job["ended_at"]
        and type(native_row["wall_seconds"]) in (int, float)
        and math.isfinite(native_row["wall_seconds"])
        and native_row["wall_seconds"] >= 0
    )
    if not identity_matches:
        return False
    try:
        begun = queue.dt(job["started_at"])
        intent = queue.dt(attempt["intent_at"])
        ended = queue.dt(job["ended_at"])
        return begun <= intent <= ended
    except (ValueError, TypeError, OverflowError):
        return False


def verified_duration_summary(
    observations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Statistics exclude unverified, different-environment, or changed inputs."""
    groups: dict[tuple[str, ...], list[float]] = defaultdict(list)
    for row in observations:
        duration = row.get("wallSeconds")
        if not (
            row.get("nativeVerified") is True
            and row.get("comparable") is True
            and isinstance(duration, (int, float))
            and not isinstance(duration, bool)
            and math.isfinite(duration)
            and duration >= 0
        ):
            continue
        key = (
            row["caseId"],
            row["comparisonKey"],
            row["variant"],
            row["environmentSha256"],
            row["semanticSha256"],
            row["cacheMode"],
        )
        groups[key].append(float(duration))
    return [
        {
            "caseId": key[0],
            "comparisonKey": key[1],
            "variant": key[2],
            "environmentSha256": key[3],
            "semanticSha256": key[4],
            "cacheMode": key[5],
            "measurementScope": "parent_monotonic_native_elapsed",
            "n": len(values),
            "medianSeconds": median(values),
            "minSeconds": min(values),
            "maxSeconds": max(values),
            "rawSeconds": values,
        }
        for key, values in sorted(groups.items())
    ]


def _paired_regressions(stats: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    pairs: dict[tuple[str, ...], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in stats:
        key = (
            row["caseId"],
            row["comparisonKey"],
            row["environmentSha256"],
            row["semanticSha256"],
            row["cacheMode"],
        )
        pairs[key][row["variant"]] = row
    result = []
    for pair_key, variants in sorted(pairs.items()):
        if not {"baseline", "candidate"} <= variants.keys():
            continue
        baseline = variants["baseline"]["medianSeconds"]
        candidate = variants["candidate"]["medianSeconds"]
        result.append(
            {
                "caseId": pair_key[0],
                "comparisonKey": pair_key[1],
                "environmentSha256": pair_key[2],
                "semanticSha256": pair_key[3],
                "cacheMode": pair_key[4],
                "baselineMedianSeconds": baseline,
                "candidateMedianSeconds": candidate,
                "deltaSeconds": candidate - baseline,
                "regressionPercent": (
                    (candidate - baseline) / baseline * 100 if baseline > 0 else None
                ),
            }
        )
    return result


def publish_campaign(store: queue.Store, campaign_id: str) -> dict[str, Any]:
    """Stable sanitized, rebuildable status/report from SQLite + frozen bytes."""
    if not CAMPAIGN_ID_PATTERN.fullmatch(campaign_id):
        raise queue.QueueError("invalid campaign ID")
    with (store.root / "publish.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        with store.connect() as db:
            db.execute("BEGIN")
            record = db.execute(
                "SELECT * FROM campaigns WHERE id=?", (campaign_id,)
            ).fetchone()
            if record is None:
                raise queue.QueueError("unknown campaign")
            steps = db.execute(
                "SELECT * FROM campaign_trials WHERE campaign_id=? ORDER BY ordinal",
                (campaign_id,),
            ).fetchall()
            heartbeat = db.execute(
                "SELECT seq,at FROM campaign_heartbeats WHERE campaign_id=?",
                (campaign_id,),
            ).fetchone()
            journal = db.execute(
                "SELECT seq,at,kind,detail FROM campaign_events "
                "WHERE campaign_id=? ORDER BY seq",
                (campaign_id,),
            ).fetchall()
            commands = db.execute(
                "SELECT command_id,at,action,outcome,version "
                "FROM campaign_commands WHERE campaign_id=? ORDER BY at,command_id",
                (campaign_id,),
            ).fetchall()
            children = {}
            for step in steps:
                child_id = step["child_job_id"]
                if child_id:
                    children[child_id] = (
                        db.execute(
                            "SELECT * FROM jobs WHERE id=?", (child_id,)
                        ).fetchone(),
                        db.execute(
                            "SELECT * FROM native_attempts WHERE job_id=?",
                            (child_id,),
                        ).fetchone(),
                        db.execute(
                            "SELECT * FROM trials WHERE job_id=? "
                            "ORDER BY seq DESC LIMIT 1",
                            (child_id,),
                        ).fetchone(),
                    )
        try:
            plan = load_frozen_campaign(store, campaign_id)
        except (OSError, ValueError, KeyError, TypeError):
            plan = None
        if plan is not None and not _campaign_limits_match(record, plan):
            plan = None
        case_keys = (
            {row["id"]: row["comparisonKey"] for row in plan["cases"]} if plan else {}
        )
        observations = []
        for step in steps:
            ordinal = step["ordinal"]
            trial = plan["trials"][ordinal] if plan is not None else None
            job, attempt, native_row = children.get(
                step["child_job_id"], (None, None, None)
            )
            authenticated = bool(
                trial is not None
                and _verified_observation(step, job, attempt, native_row)
            )
            env = step["environment_sha"]
            semantic = (
                hashlib.sha256(
                    queue.canonical(trial["plan"]["native"]["expected"])
                ).hexdigest()
                if trial is not None
                else None
            )
            spans: dict[str, float] = {}
            try:
                if step["timing_spans_json"] is not None:
                    parsed_spans = json.loads(step["timing_spans_json"])
                    if (
                        not isinstance(parsed_spans, dict)
                        or not set(parsed_spans) <= _TIMING_NAMES
                        or any(
                            type(value) not in (float, int)
                            or not math.isfinite(value)
                            or value < 0
                            for value in parsed_spans.values()
                        )
                    ):
                        raise ValueError("invalid measurement spans")
                    spans = parsed_spans
            except (ValueError, TypeError):
                authenticated = False
            comparable = bool(
                authenticated
                and isinstance(env, str)
                and queue.SHA_PATTERN.fullmatch(env)
                and semantic is not None
                and spans is not None
            )
            observations.append(
                {
                    "ordinal": ordinal,
                    "trialId": step["trial_id"],
                    "caseId": step["case_id"],
                    "comparisonKey": case_keys.get(step["case_id"]),
                    "variant": step["variant"],
                    "round": step["round"],
                    "sourceCommit": trial["sourceCommit"] if trial else None,
                    "cacheMode": trial["cacheMode"] if trial else None,
                    "planSha256": step["plan_sha"],
                    "requestSha256": step["request_sha"],
                    "targetId": step["target_id"],
                    "childJobId": step["child_job_id"],
                    "state": _safe_reason(step["state"]) or "unknown",
                    "startedAt": _safe_stamp(step["started_at"]),
                    "endedAt": _safe_stamp(step["ended_at"]),
                    "nativeVerified": authenticated,
                    "comparable": comparable,
                    "environmentSha256": env if comparable else None,
                    "semanticSha256": semantic if comparable else None,
                    "wallSeconds": (
                        native_row["wall_seconds"] if authenticated else None
                    ),
                    "nativeWaitSeconds": (
                        spans.get("native_wait") if comparable else None
                    ),
                    "namedOverheadSeconds": spans if comparable else {},
                    # No fabricated setup/queue/network subtraction or guessed wait.
                    "evidence": (
                        "authenticated_native_receipt"
                        if authenticated
                        else "not_authenticated_for_statistics"
                    ),
                }
            )
        stats = verified_duration_summary(observations)
        counts: dict[str, int] = {}
        for row in observations:
            state = row["state"]
            counts[state] = counts.get(state, 0) + 1
        try:
            used_bytes = _owned_bytes(
                store, campaign_id, exclude_projections=True, frozen_plan=plan
            )
        except (OSError, ValueError, TypeError):
            used_bytes = None
        status = {
            "schema": "vera.resolve-test-campaign-status/v1",
            "campaignId": campaign_id,
            "state": _safe_reason(record["state"]) or "unknown",
            "reason": _safe_reason(record["reason"]),
            "planSha256": record["plan_sha"],
            "planIntegrity": (
                "verified" if plan is not None else "unavailable_or_changed"
            ),
            "scheduledAt": queue.iso(datetime.fromtimestamp(record["run_at"], UTC)),
            "deadlineAt": queue.iso(datetime.fromtimestamp(record["deadline_at"], UTC)),
            "startedAt": _safe_stamp(record["started_at"]),
            "endedAt": _safe_stamp(record["ended_at"]),
            "pauseAfterActive": bool(record["pause_after_active"]),
            "cancelPending": bool(record["cancel_pending"]),
            "heartbeat": (
                {"seq": heartbeat["seq"], "at": _safe_stamp(heartbeat["at"])}
                if heartbeat
                else None
            ),
            "activeCaseId": next(
                (step["case_id"] for step in steps if step["state"] == "running"),
                None,
            ),
            "activeTrialId": next(
                (step["trial_id"] for step in steps if step["state"] == "running"),
                None,
            ),
            "version": record["version"],
            "counts": counts,
            "verifiedTrials": sum(row["nativeVerified"] for row in observations),
            "comparableTrials": sum(row["comparable"] for row in observations),
            "totalTrials": len(steps),
            "budget": {
                "maxElapsedSeconds": record["max_elapsed_seconds"],
                "maxDiskBytes": record["max_disk_bytes"],
                "ownedBytes": used_bytes,
                "accountingVerified": used_bytes is not None,
            },
        }
        report = {
            "schema": "vera.resolve-test-campaign-report/v1",
            "status": status,
            "observations": observations,
            "statistics": stats,
            "regressions": _paired_regressions(stats),
            "journal": [
                {
                    "seq": item["seq"],
                    "at": _safe_stamp(item["at"]),
                    "kind": _safe_reason(item["kind"]) or "redacted",
                    "detail": _safe_reason(item["detail"]) or "redacted",
                }
                for item in journal
            ],
            "commands": [
                {
                    "commandId": queue.simple_id(item["command_id"], "command id"),
                    "at": _safe_stamp(item["at"]),
                    "action": _safe_reason(item["action"]) or "redacted",
                    "outcome": _safe_reason(item["outcome"]) or "redacted",
                    "version": item["version"],
                }
                for item in commands
            ],
            "limitations": (
                "M2 authenticated native save/reopen/readback only; no render/PCM "
                "claim. Timing comparisons require a pinned Resolve build and "
                "host identity. Missing spans are omitted, not estimated."
            ),
        }

        def markdown(value: int | None) -> bytes:
            lines = [
                f"# Native campaign {campaign_id}",
                "",
                f"State: {status['state']} ({status['reason'] or 'none'}).",
                f"Plan SHA-256: {record['plan_sha']}; "
                f"integrity: {status['planIntegrity']}.",
                f"Trials: {len(steps)}; native verified: {status['verifiedTrials']}; "
                f"comparable: {status['comparableTrials']}.",
                f"States: {json.dumps(counts, sort_keys=True)}.",
                f"Budget: {value if value is not None else 'unverifiable'} "
                f"/ {record['max_disk_bytes']} bytes.",
                "",
                "## Verified comparable timing",
            ]
            for entry in stats:
                lines.append(
                    f"- {entry['caseId']} {entry['variant']} ({entry['cacheMode']}): "
                    f"n={entry['n']}, median {entry['medianSeconds']:.3f}s, "
                    f"range {entry['minSeconds']:.3f}-{entry['maxSeconds']:.3f}s."
                )
            if not stats:
                lines.append("None: unverified or incompatible measurements excluded.")
            lines.extend(["", str(report["limitations"]), ""])
            return "\n".join(lines).encode("utf-8")

        # Projections are themselves part of the aggregate disk budget.
        # Compute their final byte length to a fixed point before writing,
        # so repeated reads are byte-identical and never underreport storage.
        guess = used_bytes
        for _ in range(8):
            status["budget"]["ownedBytes"] = guess
            status_bytes = queue.canonical(status)
            report_bytes = queue.canonical(report)
            markdown_bytes = markdown(guess)
            if used_bytes is None:
                break
            actual = (
                used_bytes + len(status_bytes) + len(report_bytes) + len(markdown_bytes)
            )
            if actual == guess:
                break
            guess = actual
        else:
            raise queue.QueueError("campaign report byte accounting did not converge")
        folder = store.root / campaign_id
        queue.atomic_write(folder / "status.json", status_bytes)
        queue.atomic_write(folder / "report.json", report_bytes)
        queue.atomic_write(folder / "report.md", markdown_bytes)
        return report


def campaign_agent_plist(root: Path, executable: str) -> bytes:
    """Opt-in campaign worker, separate from M1/M2 and the web monitor."""
    return plistlib.dumps(
        {
            "Label": CAMPAIGN_LAUNCH_LABEL,
            "ProgramArguments": [
                executable,
                "-m",
                "vera_timeline_agent.resolve_test_campaign",
                "--root",
                str(root),
                "worker",
                "once",
            ],
            "StartInterval": 30,
            "RunAtLoad": True,
            "ProcessType": "Background",
            "StandardOutPath": str(root / "campaign-worker.stdout.log"),
            "StandardErrorPath": str(root / "campaign-worker.stderr.log"),
        },
        sort_keys=True,
    )


def install_campaign_agent(store: queue.Store) -> None:
    if platform.system() != "Darwin":
        raise queue.QueueError("campaign LaunchAgent is macOS only")
    plist = Path.home() / "Library" / "LaunchAgents" / f"{CAMPAIGN_LAUNCH_LABEL}.plist"
    plist.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    queue.reject_unsafe_path(plist, "campaign LaunchAgent")
    payload = campaign_agent_plist(store.root, sys.executable)
    if plist.exists():
        if plist.read_bytes() != payload:
            raise queue.QueueError("campaign LaunchAgent differs; refusing overwrite")
    else:
        fd = os.open(plist, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
    loaded = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{CAMPAIGN_LAUNCH_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if loaded.returncode != 0:
        subprocess.run(
            ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)],
            check=True,
            capture_output=True,
            text=True,
        )


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Finite guarded native M3 campaigns")
    value.add_argument("--root", type=Path, default=queue.DEFAULT_ROOT)
    sub = value.add_subparsers(dest="command", required=True)
    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("--plan", type=Path, required=True)
    for command in ("status", "report", "pause", "resume", "cancel", "reconcile"):
        target = sub.add_parser(command)
        target.add_argument("campaign_id")
        if command == "report":
            target.add_argument(
                "--format", choices=("json", "markdown"), default="json"
            )
        if command in _CONTROL_ACTIONS:
            target.add_argument("--command-id", required=True)
    worker = sub.add_parser("worker")
    worker.add_argument("action", choices=("once", "serve"))
    worker.add_argument("--interval", type=int, default=30)
    sub.add_parser("install-launchd")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    options = parser().parse_args(argv)
    try:
        store = queue.Store(options.root)
        if options.command == "enqueue":
            campaign_id = enqueue_campaign(store, options.plan)
            print(campaign_id)
            publish_campaign(store, campaign_id)
        elif options.command in {"status", "report"}:
            report = publish_campaign(store, options.campaign_id)
            if options.command == "status":
                print(json.dumps(report["status"], sort_keys=True))
            elif options.format == "json":
                print(json.dumps(report, sort_keys=True))
            else:
                print((store.root / options.campaign_id / "report.md").read_text())
        elif options.command in _CONTROL_ACTIONS:
            result = control_campaign(
                store,
                options.campaign_id,
                action=options.command,
                command_id=options.command_id,
                actor="local-operator",
                authorized=True,
            )
            publish_campaign(store, options.campaign_id)
            print(json.dumps(result, sort_keys=True))
        elif options.command == "worker":
            if options.action == "once":
                campaign_worker_once(store)
            else:
                queue.limited_int(options.interval, "interval", 1, 3600)
                while True:
                    campaign_worker_once(store)
                    time.sleep(options.interval)
        elif options.command == "install-launchd":
            install_campaign_agent(store)
            print("Opt-in M3 campaign worker LaunchAgent installed.")
        return 0
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        print(f"campaign refused: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
