"""#473 binding for the *approved* #495 one-use M4 GUI edit attempt.

This is not an executable entry point. A fresh, case-specifically authorized
native host must supply its independently observed SDK inventory and trusted
OS/TCC preflight while holding the shared native owner. The original M4 queue,
signed pristine capture, cumulative deadline and consumed intent all remain
authoritative. A GUI attempt is *always* UNKNOWN until the separate official
SDK save/reopen/readback and independent M4 verifier finish.

In particular, this module cannot resurrect the expired historical #473 run.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import resolve_gui_roll as gui
from . import resolve_test_bench_carrier as carrier
from . import resolve_test_queue as queue
from . import resolve_test_queue_m4 as m4
from .qualification_output_native_v2 import verify_native_result


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise gui.GuiRollRefused("#473 M4 F1 stage refused: " + detail)


def _target_dict(target: gui.NativeTarget) -> dict[str, str]:
    return {
        "projectUid": target.project_uid,
        "projectName": target.project_name,
        "timelineUid": target.timeline_uid,
        "timelineName": target.timeline_name,
    }


def _verify_original_capture(
    store: queue.Store,
    job_id: str,
    intent: gui.GuiRollIntent,
    inventory: gui.PristineSdkInventory,
) -> None:
    """Re-verify signed M4 pristine evidence, not caller-provided JSON alone."""
    receipt = m4._stage_receipt(store, job_id, 0)
    original = verify_native_result(
        Path(receipt["capture"]["path"]), receipt["capture"]["sha256"]
    )
    target = _target_dict(intent.target)
    geometry = original.get("nativeGeometry")
    _require(
        original.get("status") == "complete"
        and original.get("action") == "capture_post"
        and original.get("target") == target
        and original.get("context", {}).get("target") == target
        and isinstance(geometry, dict),
        "signed original pristine native capture differs",
    )
    assert isinstance(geometry, dict)
    items = geometry.get("items")
    tracks = geometry.get("tracks")
    rate = geometry.get("rate")
    _require(
        isinstance(items, list)
        and len(items) == gui.NATIVE_ITEM_COUNT
        and all(isinstance(row, dict) for row in items)
        and isinstance(tracks, list)
        and len(tracks) == gui.NATIVE_TRACK_COUNT
        and isinstance(rate, dict)
        and rate.get("numerator") == gui.EXPECTED_RATE[0]
        and rate.get("denominator") == gui.EXPECTED_RATE[1]
        and geometry.get("extentFrames") == gui.EXTENT_FRAMES,
        "signed pristine geometry incomplete or not the approved matrix",
    )
    assert isinstance(items, list)
    by_uid = {row.get("itemUid"): row for row in items if isinstance(row, dict)}
    _require(
        len(by_uid) == gui.NATIVE_ITEM_COUNT
        and set(by_uid) == set(inventory.item_uids)
        and intent.item_uids == inventory.item_uids
        and inventory.capture_sha256 == receipt["capture"]["sha256"]
        and intent.pristine_capture_sha256 == inventory.capture_sha256
        and inventory.target == intent.target
        and inventory.pristine_verified is True,
        "SDK inventory/UIDs not bound to signed pristine capture",
    )
    left = by_uid.get(intent.left_item_uid)
    right = by_uid.get(intent.right_item_uid)
    _require(
        isinstance(left, dict)
        and isinstance(right, dict)
        and left.get("kind") == right.get("kind") == "video"
        and left.get("trackId") == right.get("trackId") == inventory.left_track_id
        and left.get("recordStart") == inventory.left_record_start == 0
        and left.get("recordDuration")
        == inventory.left_record_duration
        == gui.BEFORE_BOUNDARY
        and right.get("recordStart")
        == inventory.right_record_start
        == gui.BEFORE_BOUNDARY
        and right.get("recordDuration") == inventory.right_record_duration == 151,
        "signed SDK left/right boundary differs",
    )


class OriginalM4GuiJournal:
    """One-use, fsynced dispatch journal tied to a *new* approved M4 operation.

    Caller must additionally verify the NEW case-specific Producer operation
    authority before calling ``attempt``; #491's product exception alone is
    not such an authorization. The queue binds a specific approved operation.
    """

    def __init__(self, store: queue.Store, job_id: str):
        self.store = store
        self.job_id = job_id
        # The original authenticated M4 queue owns this canonical path.
        # A caller must not choose another directory to evade a spent intent.
        self.root = m4._jobdir(store, job_id) / "f1-gui-edit"

    def consume_before_effect(self, intent: gui.GuiRollIntent) -> bool:
        plan = m4._load_plan(self.store, self.job_id)
        _require(
            plan["caseId"] == "synthetic-312"
            and plan["initialTarget"] == _target_dict(intent.target)
            and plan["initialTarget"] != plan["freshTarget"],
            "not original enrolled distinct synthetic M4 initial target",
        )
        with self.store.connect() as db:
            parent = db.execute(
                "SELECT state,started_at,deadline_at FROM reverse_jobs WHERE id=?",
                (self.job_id,),
            ).fetchone()
            rows = [
                dict(row)
                for row in db.execute(
                    "SELECT ordinal,name,state,operation_id,receipt_sha "
                    "FROM reverse_stages WHERE job_id=? ORDER BY ordinal",
                    (self.job_id,),
                )
            ]
        _require(
            parent is not None
            and parent["state"] == "awaiting_operator"
            and parent["started_at"] is not None
            and parent["deadline_at"] == queue.dt(plan["deadlineAt"]).timestamp()
            and len(rows) == 4
            and rows[0]["name"] == "pristine"
            and rows[0]["state"] == "verified"
            and rows[0]["receipt_sha"] is not None
            and rows[1]["name"] == "edited"
            and rows[1]["state"] == "awaiting_operator"
            and rows[1]["receipt_sha"] is None
            and rows[1]["operation_id"] == intent.stage_operation_id
            and all(row["state"] == "pending" for row in rows[2:]),
            "no newly awaiting one-use edited M4 operation",
        )
        now = datetime.now(UTC)
        absolute_deadline = min(
            queue.dt(plan["deadlineAt"]),
            queue.dt(plan["runAt"]) + timedelta(seconds=plan["maxElapsedSeconds"]),
            queue.dt(parent["started_at"])
            + timedelta(seconds=plan["maxElapsedSeconds"]),
        )
        _require(
            now < intent.expires_at <= absolute_deadline
            and intent.expires_at - now <= timedelta(minutes=5),
            "GUI intent expired, unbounded or outside original M4 ceiling",
        )
        carrier._private(self.root, create=True)
        _require(
            not (self.root / "gui-intent.json").exists()
            and not (self.root / "gui-intent.json").is_symlink(),
            "GUI one-use intent previously consumed; inspect without replay",
        )
        # An earlier crash, even after writing only part of the O_EXCL file,
        # permanently spends the operation. Never unlink or rewrite it.
        record = {
            "schema": "vera.issue473-one-use-f1-gui/v1",
            "jobId": self.job_id,
            "operationId": intent.stage_operation_id,
            "actuatorClass": gui.ACTUATOR_CLASS,
            "target": _target_dict(intent.target),
            "scriptSha256": intent.script_sha256,
            "captureSha256": intent.pristine_capture_sha256,
            "itemUids": list(intent.item_uids),
            "expiresAt": queue.iso(intent.expires_at),
            "m4DeadlineAt": queue.iso(absolute_deadline),
            "m4PlanSha256": hashlib.sha256(queue.canonical(plan)).hexdigest(),
        }
        try:
            carrier._once(self.root / "gui-intent.json", queue.canonical(record))
        except FileExistsError:
            return False
        return True


def attempt_once(
    store: queue.Store,
    job_id: str,
    intent: gui.GuiRollIntent,
    inventory: gui.PristineSdkInventory,
    readiness: gui.TrustedUiReadiness,
    executor: gui.FixedRollExecutor,
) -> gui.GuiRollAttempt:
    """Only for a *new*, independently authorized, already-owned host run.

    This deliberately does not acquire the native lock, issue an approval,
    save/reopen the project or create an M4 receipt. Only the owning #473 host
    may call it after separate case-specific authority and read-only preflight.
    """
    gui._require_owner_lock()
    _verify_original_capture(store, job_id, intent, inventory)
    return gui.OneUseGuiRollActuator(
        OriginalM4GuiJournal(store, job_id), executor
    ).attempt(intent, inventory, readiness)
