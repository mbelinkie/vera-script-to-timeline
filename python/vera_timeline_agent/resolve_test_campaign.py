"""Closed, immutable M3 campaign contract over independent one-use M2 native plans.

Phase 1 only: no native dispatch or live Resolve access occurs here. The later
coordinator must activate one already-prepared child using M2's guarded path.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
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
