"""M4 closed, fail-stop operator/host handoff for one same-target reverse chain.

This coordinator does not synthesize a native edit, operator approval, inference,
or rebuild. An M4 stage is journaled before its existing reviewed output-host
flow may be invoked. The installed host owns every native effect and the
authentication of its results; no shell/GUI shortcut or repeat dispatch exists.

The four stages are *not* four independent M2 jobs: pristine and edited must
retain the same native project/timeline UIDs. Rebuild must use an independent
fresh UID and a signed one-use revised-build reservation. A submitted receipt
is pinned in SQLite before verification, so a crash can only recheck the exact
same evidence. Failure/partial/UNKNOWN cannot promote a subsequent stage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import sys
import time
import uuid
from collections.abc import Mapping, Sequence
from datetime import timedelta
from pathlib import Path
from typing import Any

from . import resolve_test_queue as queue
from .resolve_native_owner import (
    NativeOwnerError,
    preflight_selected_disposable,
)

SCHEMA = "vera.resolve-test-reverse-plan/v1"
RECEIPT_SCHEMA = "vera.resolve-test-reverse-receipt/v1"
STAGES = ("pristine", "edited", "revision", "rebuild")
ID_RE = re.compile(r"resolve-reverse-[a-f0-9]{32}\Z")
SHA_RE = re.compile(r"[a-f0-9]{64}\Z")
# The same unique synthetic naming requirement used by the M2 native owner.
DISPOSABLE_RE = re.compile(
    r"VERA Delivery [0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12} [0-9a-f]{12}\Z"
)
PLAN_FIELDS = frozenset(
    {
        "schema",
        "name",
        "caseId",
        "baselineSession",
        "initialTarget",
        "freshTarget",
        "maxElapsedSeconds",
        "maxDiskBytes",
        "runAt",
        "deadlineAt",
    }
)
TARGET_FIELDS = frozenset({"projectUid", "timelineUid", "projectName", "timelineName"})
REF_FIELDS = frozenset({"path", "sha256"})
MAX_RECEIPT_BYTES = 16 * 1024


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _ref(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != REF_FIELDS:
        raise queue.QueueError(f"{label} requires a pinned path and digest")
    path, digest = value.get("path"), value.get("sha256")
    if (
        not isinstance(path, str)
        or not isinstance(digest, str)
        or not SHA_RE.fullmatch(digest)
        or len(path) > 4096
        or not Path(path).is_absolute()
        or ".." in Path(path).parts
        or str(Path(path)) != path
    ):
        raise queue.QueueError(f"{label} requires an absolute safe SHA-256 reference")
    return {"path": path, "sha256": digest}


def _target(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != TARGET_FIELDS:
        raise queue.QueueError(f"{label} has unsupported identity fields")
    for key in TARGET_FIELDS:
        item = value[key]
        if (
            not isinstance(item, str)
            or not item
            or len(item) > 256
            or any(ord(character) < 32 for character in item)
        ):
            raise queue.QueueError(f"{label}.{key} must be a bounded identity")
    if (
        value["projectName"] != value["timelineName"]
        or not DISPOSABLE_RE.fullmatch(value["projectName"])
        or value["projectUid"] == value["timelineUid"]
    ):
        raise queue.QueueError(f"{label} requires a unique synthetic disposable")
    return dict(value)


def validate_plan(raw: object) -> dict[str, Any]:
    if (
        not isinstance(raw, dict)
        or not PLAN_FIELDS - {"runAt", "deadlineAt"} <= raw.keys()
        or not raw.keys() <= PLAN_FIELDS
    ):
        raise queue.QueueError("invalid closed M4 plan fields")
    plan = dict(raw)
    if plan["schema"] != SCHEMA:
        raise queue.QueueError("unsupported M4 version")
    queue.simple_id(plan["name"], "name")
    queue.simple_id(plan["caseId"], "caseId")
    plan["baselineSession"] = _ref(plan["baselineSession"], "baselineSession")
    plan["initialTarget"] = _target(plan["initialTarget"], "initialTarget")
    plan["freshTarget"] = _target(plan["freshTarget"], "freshTarget")
    initial, fresh = plan["initialTarget"], plan["freshTarget"]
    if initial["projectName"] == fresh["projectName"] or set(
        (initial["projectUid"], initial["timelineUid"])
    ) & set((fresh["projectUid"], fresh["timelineUid"])):
        raise queue.QueueError("rebuild must reserve a distinct fresh native target")
    queue.limited_int(plan["maxElapsedSeconds"], "maxElapsedSeconds", 60, 14400)
    queue.limited_int(plan["maxDiskBytes"], "maxDiskBytes", 1048576, 4 * 1024**3)
    scheduled = queue.dt(plan.get("runAt", queue.iso(queue.now_utc())))
    deadline = queue.dt(
        plan.get(
            "deadlineAt",
            queue.iso(scheduled + timedelta(seconds=plan["maxElapsedSeconds"] + 3600)),
        )
    )
    if deadline <= scheduled:
        raise queue.QueueError("M4 deadline must follow schedule")
    plan["runAt"], plan["deadlineAt"] = queue.iso(scheduled), queue.iso(deadline)
    return plan


def _read_pinned(reference: Mapping[str, str], *, limit: int) -> bytes:
    pin = _ref(dict(reference), "evidence")
    raw = _read_bounded(Path(pin["path"]), limit=limit)
    if _sha(raw) != pin["sha256"]:
        raise queue.QueueError("evidence digest differs")
    return raw


def _read_bounded(path: Path, *, limit: int) -> bytes:
    """Read only a single-link regular file via a no-follow descriptor."""
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise queue.QueueError("evidence symbolic-link path refused")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        metadata = os.fstat(fd)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size > limit
        ):
            raise queue.QueueError(
                "evidence must be bounded, regular and single-linked"
            )
        chunks = bytearray()
        while len(chunks) <= limit:
            part = os.read(fd, min(65536, limit + 1 - len(chunks)))
            if not part:
                break
            chunks.extend(part)
        raw = bytes(chunks)
        if len(raw) > limit:
            raise queue.QueueError("evidence size differs")
        return raw
    finally:
        os.close(fd)


def _load_plan(store: queue.Store, job_id: str) -> dict[str, Any]:
    folder = _jobdir(store, job_id)
    with store.connect() as db:
        row = db.execute(
            "SELECT plan_sha FROM reverse_jobs WHERE id=?", (job_id,)
        ).fetchone()
    if row is None:
        raise queue.QueueError("unknown reverse job")
    raw = _read_pinned(
        {"path": str(folder / "plan.json"), "sha256": row["plan_sha"]}, limit=131072
    )
    result = validate_plan(json.loads(raw))
    if queue.canonical(result) != raw:
        raise queue.QueueError("frozen reverse plan is not canonical")
    return result


def _jobdir(store: queue.Store, job_id: str) -> Path:
    if not ID_RE.fullmatch(job_id):
        raise queue.QueueError("invalid reverse job ID")
    path = store.root / job_id
    queue.reject_unsafe_path(path, "reverse job")
    return path


def _event(db: sqlite3.Connection, job_id: str, kind: str, detail: str) -> None:
    db.execute(
        "INSERT INTO reverse_events(job_id,at,kind,detail) VALUES(?,?,?,?)",
        (job_id, queue.iso(queue.now_utc()), kind, detail),
    )


def target_reserved(db: sqlite3.Connection, name: str) -> bool:
    return (
        db.execute("SELECT 1 FROM reverse_targets WHERE name=?", (name,)).fetchone()
        is not None
    )


def any_unresolved(store: queue.Store) -> bool:
    """An M4 native stage cannot be displaced by an independent M2/M3 build."""
    with store.connect() as db:
        return (
            db.execute(
                "SELECT 1 FROM reverse_jobs j JOIN reverse_stages s ON s.job_id=j.id "
                "WHERE s.intent_at IS NOT NULL AND "
                "s.state IN ('awaiting_operator','verifying','unknown') "
                "LIMIT 1"
            ).fetchone()
            is not None
        )


def _m2_active(db: sqlite3.Connection) -> bool:
    return (
        db.execute(
            "SELECT 1 FROM jobs j JOIN native_attempts n ON n.job_id=j.id "
            "WHERE j.state IN ('running','unknown') AND n.intent_at IS NOT NULL LIMIT 1"
        ).fetchone()
        is not None
    )


def enqueue(store: queue.Store, path: Path, at: str | None = None) -> str:
    submitted = queue.read_plan_file(path)
    if at is not None:
        if not isinstance(submitted, dict):
            raise queue.QueueError("M4 plan must be an object")
        submitted["runAt"] = at
    plan = validate_plan(submitted)
    # Authenticate the existing output host, not a caller-invented authority.
    from .qualification_output_controller_v2 import load_output_session
    from .qualification_output_native_v2 import native_request_paths

    baseline = load_output_session(
        Path(plan["baselineSession"]["path"]), plan["baselineSession"]["sha256"]
    )
    if (
        baseline.context.get("phase") != "pristine"
        or baseline.context.get("caseId") != plan["caseId"]
        or baseline.context.get("target") != plan["initialTarget"]
    ):
        raise queue.QueueError("pristine host session does not match the M4 authority")
    first_native_result = native_request_paths(baseline.context, 0)[0]
    if first_native_result.exists():
        raise queue.QueueError(
            "pristine target already has native operations; no adoption"
        )
    frozen = queue.canonical(plan)
    job_id = f"resolve-reverse-{uuid.uuid4().hex}"
    folder = _jobdir(store, job_id)
    folder.mkdir(mode=0o700)
    queue.atomic_write(folder / "plan.json", frozen)
    (folder / "plan.json").chmod(0o400)
    queue.sync_directory(store.root)
    now = queue.iso(queue.now_utc())
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if _m2_active(db):
            raise queue.QueueError("unresolved M2 native owner; M4 cannot enroll")
        for target in (plan["initialTarget"], plan["freshTarget"]):
            existing = db.execute("SELECT locator FROM native_attempts").fetchall()
            if any(
                json.loads(row["locator"]).get("projectName") == target["projectName"]
                for row in existing
            ):
                raise queue.QueueError("native target already reserved by M2/M3")
        db.execute(
            "INSERT INTO reverse_jobs(id,state,plan_sha,submitted_at,"
            "run_at,deadline_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                job_id,
                "queued",
                _sha(frozen),
                now,
                queue.dt(plan["runAt"]).timestamp(),
                queue.dt(plan["deadlineAt"]).timestamp(),
                now,
            ),
        )
        for target in (plan["initialTarget"], plan["freshTarget"]):
            db.execute(
                "INSERT INTO reverse_targets(name,project_uid,timeline_uid,job_id) "
                "VALUES(?,?,?,?)",
                (
                    target["projectName"],
                    target["projectUid"],
                    target["timelineUid"],
                    job_id,
                ),
            )
        for ordinal, name in enumerate(STAGES):
            db.execute(
                "INSERT INTO reverse_stages(job_id,ordinal,name,operation_id) "
                "VALUES(?,?,?,?)",
                (job_id, ordinal, name, str(uuid.uuid4())),
            )
        _event(db, job_id, "enqueued", "immutable_host_bound_reverse_plan")
    publish(store, job_id)
    return job_id


def _stage_receipt(store: queue.Store, job_id: str, ordinal: int) -> dict[str, Any]:
    with store.connect() as db:
        stage = db.execute(
            "SELECT * FROM reverse_stages WHERE job_id=? AND ordinal=?",
            (job_id, ordinal),
        ).fetchone()
    if stage is None or stage["state"] != "verified":
        raise queue.QueueError("preceding M4 stage has no authenticated receipt")
    reference = {"path": stage["receipt_path"], "sha256": stage["receipt_sha"]}
    return _parse_receipt(
        _read_pinned(reference, limit=MAX_RECEIPT_BYTES),
        STAGES[ordinal],
        stage["operation_id"],
    )


def _parse_receipt(raw: bytes, stage: str, operation_id: str) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise queue.QueueError("invalid reverse receipt JSON") from exc
    if not isinstance(value, dict):
        raise queue.QueueError("reverse receipt must be an object")
    fields = (
        {"schema", "stage", "operationId", "proof"}
        if stage == "revision"
        else {
            "schema",
            "stage",
            "operationId",
            "session",
            "capture",
        }
    )
    if (
        set(value) != fields
        or value["schema"] != RECEIPT_SCHEMA
        or value["stage"] != stage
        or value["operationId"] != operation_id
    ):
        raise queue.QueueError(
            "reverse receipt version, stage or one-use identity differs"
        )
    for key in fields - {"schema", "stage", "operationId"}:
        value[key] = _ref(value[key], key)
    if queue.canonical(value) != raw:
        raise queue.QueueError("reverse receipt must be canonical immutable JSON")
    return value


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise queue.QueueError("duplicate reverse receipt field")
        result[key] = value
    return result


def _verified_output(
    receipt: Mapping[str, Any],
    phase: str,
    target: Mapping[str, Any],
    case_id: str,
    intent_at: str,
) -> tuple[Any, dict[str, Any]]:
    from .qualification_output_controller_v2 import load_output_session
    from .qualification_output_native_v2 import (
        native_request_paths,
        verify_native_result,
    )
    from .qualification_output_proof_v2 import _load_terminal_output_with_comparison

    session_ref, capture_ref = receipt["session"], receipt["capture"]
    controller = load_output_session(Path(session_ref["path"]), session_ref["sha256"])
    context = controller.context
    if (
        context.get("phase") != phase
        or context.get("caseId") != case_id
        or context.get("target") != target
    ):
        raise queue.QueueError(
            "native output context/UID differs from authorized M4 stage"
        )
    # The existing host verifies every request, approval, effect ledger, and
    # current source/reference across the fixed sequence of native results.
    result = verify_native_result(Path(capture_ref["path"]), capture_ref["sha256"])
    if (
        result.get("status") != "complete"
        or result.get("action") != "capture_post"
        or result.get("context") != context
        or result.get("target") != target
        or not isinstance(result.get("nativeGeometry"), dict)
    ):
        raise queue.QueueError("complete real native readback required")
    first_result_path = native_request_paths(context, 0)[0]
    first_result = verify_native_result(
        first_result_path, _sha(first_result_path.read_bytes())
    )
    if (
        first_result.get("status") != "complete"
        or first_result.get("action")
        != ("observe_edited" if phase == "edited" else "construct")
        or first_result.get("context") != context
    ):
        raise queue.QueueError("reviewed native first action missing or inauthentic")
    # A fully authenticated existing result cannot be retroactively adopted:
    # the host's durable first effect intent must postdate the M4 intent.
    intent = json.loads(Path(first_result["intentPath"]).read_bytes())
    if queue.dt(intent["createdAt"]) < queue.dt(intent_at):
        raise queue.QueueError("native operation predates the durable M4 intent")
    _load_terminal_output_with_comparison(controller)
    geometry = result["nativeGeometry"]
    if (
        geometry.get("rate") != "24000/1001"
        or geometry.get("extentFrames") != 1407
        or not isinstance(geometry.get("items"), list)
        or len(geometry["items"]) != 11
        or not isinstance(geometry.get("tracks"), list)
        or len(geometry["tracks"]) != 6
    ):
        raise queue.QueueError(
            "qualified native 11-event, 6-track 1407-frame geometry required"
        )
    return controller, result


def _verify_stage(
    store: queue.Store,
    job_id: str,
    ordinal: int,
    receipt: dict[str, Any],
    intent_at: str,
) -> None:
    from .qualification_output_proof_v2 import QualificationOutputProofV2
    from .resolve_test_queue_reverse import (
        verify_reverse_receipts,
        verify_supported_boundary,
    )

    plan = _load_plan(store, job_id)
    if ordinal == 0:
        if receipt["session"] != plan["baselineSession"]:
            raise queue.QueueError(
                "pristine session is not the enrolled host authority"
            )
        _verified_output(
            receipt,
            "pristine",
            plan["initialTarget"],
            plan["caseId"],
            intent_at,
        )
        return
    pristine = _stage_receipt(store, job_id, 0)
    if ordinal == 1:
        _, before = _verified_output(
            pristine,
            "pristine",
            plan["initialTarget"],
            plan["caseId"],
            _intent(store, job_id, 0),
        )
        _, after = _verified_output(
            receipt,
            "edited",
            plan["initialTarget"],
            plan["caseId"],
            intent_at,
        )
        verify_supported_boundary(before["nativeGeometry"], after["nativeGeometry"])
        return
    edited = _stage_receipt(store, job_id, 1)
    if ordinal == 2:
        proof = QualificationOutputProofV2(
            Path(receipt["proof"]["path"]), receipt["proof"]["sha256"]
        )
        accepted, _ = proof.accepted_revision()
        if (
            accepted.get("outcome") != "accept"
            or proof.session["baselineSession"] != pristine["session"]
            or proof.session["editedSession"] != edited["session"]
            or proof.baseline.context.get("target") != plan["initialTarget"]
            or proof.edited.context.get("target") != plan["initialTarget"]
        ):
            raise queue.QueueError(
                "accepted inferred revision does not bind the proven edit"
            )
        return
    revision = _stage_receipt(store, job_id, 2)
    from .qualification_output_controller_v2 import load_output_session

    fresh = load_output_session(
        Path(receipt["session"]["path"]), receipt["session"]["sha256"]
    )
    if fresh.context.get("target") != plan["freshTarget"]:
        raise queue.QueueError("rebuild is not the separately reserved fresh target")
    _verified_output(
        receipt,
        "rebuild",
        plan["freshTarget"],
        plan["caseId"],
        intent_at,
    )
    verdict = verify_reverse_receipts(
        proof_path=Path(revision["proof"]["path"]),
        proof_sha256=revision["proof"]["sha256"],
        pristine_result_path=Path(pristine["capture"]["path"]),
        pristine_result_sha256=pristine["capture"]["sha256"],
        edited_result_path=Path(edited["capture"]["path"]),
        edited_result_sha256=edited["capture"]["sha256"],
        fresh_session_path=Path(receipt["session"]["path"]),
        fresh_session_sha256=receipt["session"]["sha256"],
        fresh_result_path=Path(receipt["capture"]["path"]),
        fresh_result_sha256=receipt["capture"]["sha256"],
    )
    if (
        verdict.get("status") != "verified"
        or verdict.get("provenance") != "host_authenticated_no_replay"
    ):
        raise queue.QueueError("final authenticated revision/PCM verification refused")


def _intent(store: queue.Store, job_id: str, ordinal: int) -> str:
    with store.connect() as db:
        row = db.execute(
            "SELECT intent_at FROM reverse_stages WHERE job_id=? AND ordinal=?",
            (job_id, ordinal),
        ).fetchone()
    if row is None or not isinstance(row["intent_at"], str):
        raise queue.QueueError("preceding native intent is missing")
    return row["intent_at"]


def _end(store: queue.Store, job_id: str, reason: str, state: str) -> None:
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "UPDATE reverse_jobs SET state=?,reason=?,ended_at=?,updated_at=? "
            "WHERE id=? AND state NOT IN ('completed_verified','canceled')",
            (
                state,
                reason,
                queue.iso(queue.now_utc()),
                queue.iso(queue.now_utc()),
                job_id,
            ),
        )
        _event(db, job_id, state, reason)


def worker_tick(store: queue.Store) -> bool:
    """At most one pending M4 stage; never performs an editor/native effect.

    The ordinary M2 queue worker calls this under the shared worker lock. The
    handed-off reviewed host retains exclusive native ownership on every call.
    """
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT j.id,j.run_at,j.deadline_at,j.started_at FROM reverse_jobs j "
            "WHERE j.state='queued' AND j.run_at<=? ORDER BY j.run_at,j.id LIMIT 1",
            (time.time(),),
        ).fetchone()
        if row is None or _m2_active(db):
            return False
        other = db.execute(
            "SELECT 1 FROM reverse_stages s WHERE s.intent_at IS NOT NULL "
            "AND s.state IN ('awaiting_operator','verifying','unknown') LIMIT 1"
        ).fetchone()
        if other:
            return False
        next_stage = db.execute(
            "SELECT ordinal FROM reverse_stages WHERE job_id=? AND state='pending' "
            "ORDER BY ordinal LIMIT 1",
            (row["id"],),
        ).fetchone()
        if next_stage is None:
            return False
        job_id, ordinal = row["id"], next_stage["ordinal"]
    plan = _load_plan(store, job_id)
    now = queue.now_utc()
    elapsed = (
        (now - queue.dt(row["started_at"])).total_seconds() if row["started_at"] else 0
    )
    if now.timestamp() >= row["deadline_at"] or elapsed >= plan["maxElapsedSeconds"]:
        _end(store, job_id, "reverse_time_or_deadline_exceeded", "blocked")
        publish(store, job_id)
        return True
    # The below-40-GiB Producer override intentionally removes a *threshold*;
    # actual required free space and the finite job disk bound remain enforced.
    if shutil.disk_usage(store.root).free < plan["maxDiskBytes"]:
        _end(store, job_id, "insufficient_actual_free_space", "blocked")
        publish(store, job_id)
        return True
    try:
        # The reviewed output host requires a pre-existing empty project and
        # timeline with *real* Resolve UIDs. The M2 preflight instead requires
        # its target NOT to exist, so it cannot authorize this separate M4
        # route. Scope historical UNKNOWN only to the selected, exact UID;
        # never clear or trust a foreign retained operation.
        target = plan["initialTarget"] if ordinal < 3 else plan["freshTarget"]
        preflight_selected_disposable(target, require_empty=ordinal in (0, 3))
    except (NativeOwnerError, OSError, ValueError):
        _end(store, job_id, "global_native_owner_or_host_history_unresolved", "blocked")
        publish(store, job_id)
        return True
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        # Selection/preflight are read-only and happen outside this transaction.
        # A concurrent cancel may have won during that interval.  Claim the
        # parent first so a canceled job can never acquire a native intent.
        parent = db.execute(
            "UPDATE reverse_jobs SET state='awaiting_operator',"
            "started_at=COALESCE(started_at,?),updated_at=? "
            "WHERE id=? AND state='queued'",
            (queue.iso(now), queue.iso(now), job_id),
        )
        if parent.rowcount != 1:
            return False
        changed = db.execute(
            "UPDATE reverse_stages SET state='awaiting_operator',intent_at=? "
            "WHERE job_id=? AND ordinal=? AND state='pending' AND intent_at IS NULL",
            (queue.iso(now), job_id, ordinal),
        )
        if changed.rowcount != 1:
            raise queue.QueueError("M4 stage intent already consumed")
        _event(db, job_id, "intent", f"{STAGES[ordinal]}:one_use_host_handoff")
    publish(store, job_id)
    return True


def submit(store: queue.Store, job_id: str) -> None:
    """Pin one canonical host-evidence manifest, then reconcile without replay."""
    _load_plan(store, job_id)
    with store.connect() as db:
        row = db.execute(
            "SELECT ordinal,name,operation_id FROM reverse_stages "
            "WHERE job_id=? AND state='awaiting_operator'",
            (job_id,),
        ).fetchone()
    if row is None:
        raise queue.QueueError("no open stage; duplicate or uncertain M4 submission")
    path = _jobdir(store, job_id) / f"receipt-{row['name']}.json"
    if not path.exists():
        raise queue.QueueError("missing private M4 receipt")
    raw = _read_bounded(path, limit=MAX_RECEIPT_BYTES)
    digest = _sha(raw)
    raw = _read_pinned({"path": str(path), "sha256": digest}, limit=MAX_RECEIPT_BYTES)
    # Pin any readable submission BEFORE trying to interpret it. A wrong
    # operation ID or malformed receipt is an UNKNOWN effect, not a prompt to
    # replace the receipt and claim a second delivery.
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        changed = db.execute(
            "UPDATE reverse_stages SET state='verifying',receipt_path=?,receipt_sha=? "
            "WHERE job_id=? AND ordinal=? AND state='awaiting_operator' "
            "AND receipt_sha IS NULL",
            (str(path), digest, job_id, row["ordinal"]),
        )
        if changed.rowcount != 1:
            raise queue.QueueError("M4 receipt already consumed")
        db.execute(
            "UPDATE reverse_jobs SET state='verifying',updated_at=? WHERE id=?",
            (queue.iso(queue.now_utc()), job_id),
        )
        _event(db, job_id, "receipt_pinned", row["name"])
    reconcile(store, job_id)


def reconcile(store: queue.Store, job_id: str) -> None:
    """Crash recovery: recheck *only* the immutable submitted receipt."""
    with store.connect() as db:
        row = db.execute(
            "SELECT ordinal,name,operation_id,intent_at,receipt_path,receipt_sha "
            "FROM reverse_stages WHERE job_id=? AND state='verifying'",
            (job_id,),
        ).fetchone()
    if row is None:
        return
    try:
        plan = _load_plan(store, job_id)
        with store.connect() as db:
            parent_job = db.execute(
                "SELECT started_at,deadline_at FROM reverse_jobs WHERE id=?",
                (job_id,),
            ).fetchone()
        if (
            parent_job is None
            or time.time() >= parent_job["deadline_at"]
            or (
                parent_job["started_at"]
                and (
                    queue.now_utc() - queue.dt(parent_job["started_at"])
                ).total_seconds()
                >= plan["maxElapsedSeconds"]
            )
        ):
            raise queue.QueueError("reverse receipt arrived beyond bounded deadline")
        receipt = _parse_receipt(
            _read_pinned(
                {"path": row["receipt_path"], "sha256": row["receipt_sha"]},
                limit=MAX_RECEIPT_BYTES,
            ),
            row["name"],
            row["operation_id"],
        )
        _verify_stage(store, job_id, row["ordinal"], receipt, row["intent_at"])
        success = True
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, RuntimeError):
        success = False
    now = queue.iso(queue.now_utc())
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        changed = db.execute(
            "UPDATE reverse_stages SET state=?,verified_at=? "
            "WHERE job_id=? AND ordinal=? "
            "AND state='verifying' AND receipt_sha=?",
            (
                "verified" if success else "unknown",
                now if success else None,
                job_id,
                row["ordinal"],
                row["receipt_sha"],
            ),
        )
        if changed.rowcount != 1:
            raise queue.QueueError("M4 stage state moved during reconciliation")
        new_state = (
            "unknown"
            if not success
            else "completed_verified"
            if row["ordinal"] == len(STAGES) - 1
            else "queued"
        )
        reason = (
            "authentic_host_chain_verified"
            if success
            else "unverified_stage_do_not_replay"
        )
        db.execute(
            "UPDATE reverse_jobs SET state=?,reason=?,updated_at=?,ended_at=? "
            "WHERE id=?",
            (new_state, reason, now, now if new_state != "queued" else None, job_id),
        )
        _event(db, job_id, new_state, f"{row['name']}:{reason}")
    publish(store, job_id)


def cancel(store: queue.Store, job_id: str) -> None:
    _load_plan(store, job_id)
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        job = db.execute(
            "SELECT state FROM reverse_jobs WHERE id=?", (job_id,)
        ).fetchone()
        if job["state"] in ("canceled", "completed_verified", "unknown"):
            return
        started = db.execute(
            "SELECT 1 FROM reverse_stages WHERE job_id=? AND intent_at IS NOT NULL",
            (job_id,),
        ).fetchone()
        # Once an intent exists, cancellation cannot prove effects did not occur.
        state = "unknown" if started else "canceled"
        db.execute(
            "UPDATE reverse_jobs SET state=?,reason=?,cancel_requested=1,"
            "ended_at=?,updated_at=? WHERE id=?",
            (
                state,
                "cancel_requires_native_inspection"
                if started
                else "cancel_before_intent",
                queue.iso(queue.now_utc()),
                queue.iso(queue.now_utc()),
                job_id,
            ),
        )
        if started:
            db.execute(
                "UPDATE reverse_stages SET state='unknown' WHERE job_id=? AND state IN "
                "('awaiting_operator','verifying')",
                (job_id,),
            )
        _event(db, job_id, state, "no_automatic_native_replay_or_clear")
    publish(store, job_id)


def publish(store: queue.Store, job_id: str) -> dict[str, Any]:
    plan = _load_plan(store, job_id)
    with store.connect() as db:
        job = db.execute("SELECT * FROM reverse_jobs WHERE id=?", (job_id,)).fetchone()
        stages = [
            dict(stage)
            for stage in db.execute(
                "SELECT ordinal,name,state,intent_at,operation_id,receipt_sha,"
                "verified_at "
                "FROM reverse_stages WHERE job_id=? ORDER BY ordinal",
                (job_id,),
            )
        ]
        events = [
            dict(event)
            for event in db.execute(
                "SELECT at,kind,detail FROM reverse_events WHERE job_id=? ORDER BY seq",
                (job_id,),
            )
        ]
    active = next(
        (step for step in stages if step["state"] == "awaiting_operator"), None
    )
    status: dict[str, Any] = {
        "schema": "vera.resolve-test-reverse-status/v1",
        "jobId": job_id,
        "state": job["state"],
        "reason": job["reason"],
        "updatedAt": job["updated_at"],
        "stage": active["name"] if active else None,
        "humanRequired": bool(active),
        "readyFor312Phase2": job["state"] == "completed_verified",
        "nativeVerified": job["state"] == "completed_verified",
        "warning": (
            "No native effects are dispatched by M4; "
            "use only the approved host output queue."
        ),
    }
    report = {
        **status,
        "planSha256": job["plan_sha"],
        "caseId": plan["caseId"],
        "stages": stages,
        "events": events,
        "benchmarkDurationClaimed": False,
        "historical312OperationsReplayed": False,
    }
    folder = _jobdir(store, job_id)
    queue.atomic_write(folder / "status.json", queue.canonical(status))
    queue.atomic_write(folder / "report.json", queue.canonical(report))
    queue.atomic_write(
        folder / "report.md",
        (
            f"# M4 reverse queue {job_id}\n\n"
            f"State: {job['state']}; stage: {status['stage'] or 'none'}.\n\n"
            f"Authenticated final proof: {status['nativeVerified']}.\n\n"
            "Only host-native effects; no synthetic substitutions or replay.\n"
        ).encode(),
    )
    if job["state"] == "completed_verified":
        proof = {
            "schema": "vera.resolve-test-reverse-handoff/v1",
            "jobId": job_id,
            "caseId": plan["caseId"],
            "nativeVerified": True,
            "original312HistoryUntouched": True,
            "resume": "#312 existing phase 2/5; then #313, no restart",
            "stages": [
                {
                    "stage": s["name"],
                    "receiptPath": str(folder / f"receipt-{s['name']}.json"),
                    "receiptSha256": s["receipt_sha"],
                    "evidence": _stage_receipt(store, job_id, s["ordinal"]),
                }
                for s in stages
            ],
        }
        queue.atomic_write(folder / "handoff-private.json", queue.canonical(proof))
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="M4 bounded native same-target reverse queue"
    )
    parser.add_argument("--root", type=Path, default=queue.DEFAULT_ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("enqueue")
    add.add_argument("--plan", type=Path, required=True)
    for name in ("status", "submit", "cancel", "reconcile"):
        commands.add_parser(name).add_argument("job_id")
    commands.add_parser("worker-once")
    args = parser.parse_args(argv)
    try:
        store = queue.Store(args.root)
        if args.command == "enqueue":
            print(enqueue(store, args.plan))
        elif args.command == "worker-once":
            with (store.root / "worker.lock").open("a+b") as lock:
                import fcntl

                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                worker_tick(store)
        else:
            if args.command == "submit":
                submit(store, args.job_id)
            elif args.command == "cancel":
                cancel(store, args.job_id)
            elif args.command == "reconcile":
                reconcile(store, args.job_id)
            print(json.dumps(publish(store, args.job_id), sort_keys=True))
        return 0
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError) as exc:
        print(f"M4 refused: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
