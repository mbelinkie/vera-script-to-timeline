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
import json
import re
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

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
    plan = m4._load_plan(store, job_id)
    _require(
        receipt["session"] == plan["baselineSession"],
        "signed pristine session/source pin differs from original M4 baseline",
    )
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
    assert isinstance(tracks, list)
    # The original signed native topology is five *video* tracks and one
    # *audio* track. Earlier mock data mislabeled these as V1+A1..A5;
    # inspecting those AX menus would leave V2..V5 entirely unchecked.
    expected_slots = {
        ("video", 1),
        ("video", 2),
        ("video", 3),
        ("video", 4),
        ("video", 5),
        ("audio", 1),
    }
    _require(
        len({row.get("trackId") for row in tracks if isinstance(row, dict)}) == 6
        and {
            (row.get("kind"), row.get("index"))
            for row in tracks
            if isinstance(row, dict)
        }
        == expected_slots
        and all(
            row.get("locked") is ((row.get("kind"), row.get("index")) != ("video", 1))
            for row in tracks
        ),
        "signed V1-only unlocked, five other locked track topology differs",
    )
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
    assert isinstance(left, dict) and isinstance(right, dict)
    # The retained Phase-10 *historical* capture had only this V1 cut and no
    # links, but it is not authority for a NEW case. Independently require
    # these facts in that new case's signed pristine capture before the OS
    # preflight or durable one-use journal. A selection on another track at
    # 327 (or linked boundary clip) could widen a menu Roll unexpectedly.
    _require(
        all(
            type(row.get("recordStart")) is int
            and type(row.get("recordDuration")) is int
            and row["recordStart"] >= 0
            and row["recordDuration"] > 0
            and (
                row["itemUid"] in {intent.left_item_uid, intent.right_item_uid}
                or (
                    row["recordStart"] != gui.BEFORE_BOUNDARY
                    and row["recordStart"] + row["recordDuration"]
                    != gui.BEFORE_BOUNDARY
                )
            )
            for row in items
        )
        and left.get("linkedItemUids") == []
        and right.get("linkedItemUids") == [],
        "another boundary or linked items make F1 GUI co-selection unsafe",
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
            now + timedelta(seconds=60) < intent.expires_at <= absolute_deadline
            and intent.expires_at - now <= timedelta(minutes=5),
            "GUI intent stale, too close to expiry or outside original M4 ceiling",
        )
        carrier._private(self.root, create=True)
        _require(
            shutil.disk_usage(self.root).free >= plan["maxDiskBytes"],
            "original M4 actual free disk budget unavailable",
        )
        _require(
            not (self.root / "gui-intent.json").exists()
            and not (self.root / "gui-intent.json").is_symlink(),
            "GUI one-use intent previously consumed; inspect without replay",
        )
        # An earlier crash, even after writing only part of the O_EXCL file,
        # permanently spends the operation. Never unlink or rewrite it.
        record = {
            "schema": "vera.issue473-one-use-f1-gui/v2",
            "jobId": self.job_id,
            "operationId": intent.stage_operation_id,
            "actuatorClass": gui.ACTUATOR_CLASS,
            "target": _target_dict(intent.target),
            "actorPin": intent.actor_pin,
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
    *,
    resolve: Any | None = None,
) -> gui.GuiRollAttempt:
    """Only for a *new*, independently authorized, already-owned host run.

    This deliberately does not acquire the native lock, issue an approval,
    save/reopen the project or create an M4 receipt. Only the owning #473 host
    may call it after separate case-specific authority and read-only preflight.
    """
    gui._require_owner_lock()
    # Only an independent, owner-held OS+SDK probe may authorize the REAL
    # System Events executor. The public dataclass remains fakeable for tests;
    # it is not a production-ready privilege or permission claim.
    real_executor = isinstance(executor, gui.SystemEventsRollExecutor)
    _verify_original_capture(store, job_id, intent, inventory)
    transport_scope = None
    if real_executor:
        from .resolve_test_bench_ui_readiness import (
            _consume_attested_ui_readiness,
        )

        _require(resolve is not None, "real transport needs original SDK handle")
        assert resolve is not None

        def recheck_sdk() -> None:
            gui._require_owner_lock()
            _require(
                resolve.GetCurrentPage() == "edit",
                "SDK Edit page changed just before fixed GUI transport",
            )
            manager = resolve.GetProjectManager()
            project = manager.GetCurrentProject() if manager is not None else None
            timeline = project.GetCurrentTimeline() if project is not None else None
            _require(
                project is not None
                and timeline is not None
                and project.GetUniqueId() == intent.target.project_uid
                and timeline.GetUniqueId() == intent.target.timeline_uid
                and _read_only_playhead_frame(timeline) == gui.AFTER_BOUNDARY
                and datetime.now(UTC) < intent.expires_at,
                "SDK target/frame351/deadline changed before fixed GUI transport",
            )

        recheck_sdk()  # pre-journal: protect one-use intent from stale SDK
        _consume_attested_ui_readiness(intent, inventory, readiness)
        transport_scope = gui._VERIFIED_HOST_DISPATCH.set(
            (intent.target.expected_window_name, readiness.process_pid, recheck_sdk)
        )
    try:
        return gui.OneUseGuiRollActuator(
            OriginalM4GuiJournal(store, job_id), executor
        ).attempt(intent, inventory, readiness)
    finally:
        if transport_scope is not None:
            gui._VERIFIED_HOST_DISPATCH.reset(transport_scope)


def dispatch_owned_f1_once(
    store: queue.Store, job_id: str, resolve: Any
) -> gui.GuiRollAttempt:
    """Single production transport for a separately authorized *new* M4 run.

    The caller already owns the host-wide native lock and has verified fresh
    case-specific Producer authority. Nothing here can grant that authority,
    acquire another owner, choose a target, set a playhead, or resume an old
    campaign. Only the fixed, reviewed #495 System Events script is dispatched.
    An OS success means UNKNOWN pending the independent phase-3 native host;
    no native write/receipt/promotion is attempted in this phase.
    """
    from .resolve_test_bench_ui_readiness import prepare_owned_ui_readiness

    gui._require_owner_lock()
    intent, inventory, readiness = prepare_owned_ui_readiness(store, job_id, resolve)
    return attempt_once(
        store,
        job_id,
        intent,
        inventory,
        readiness,
        gui.SystemEventsRollExecutor(),
        resolve=resolve,
    )


def _read_only_playhead_frame(timeline: Any) -> int:
    """Read the SDK timecode without setting the playhead or clip position.

    Studio's exact 24000/1001 synthetic case has 24 nominal, non-drop-frame
    timecode; a semicolon, malformed component or nonzero start-frame breaks
    this narrow qualification rather than guessing a frame.
    """

    def frames(value: object) -> int:
        _require(
            type(value) is str
            and re.fullmatch(r"\d{2}:\d{2}:\d{2}:\d{2}", value) is not None,
            "actual SDK playhead/timecode unavailable or drop-frame",
        )
        assert isinstance(value, str)
        hours, minutes, seconds, frame = map(int, value.split(":"))
        _require(
            hours < 24 and minutes < 60 and seconds < 60 and frame < 24,
            "actual SDK timecode component outside 24 nominal fps",
        )
        return ((hours * 60 + minutes) * 60 + seconds) * 24 + frame

    current = timeline.GetCurrentTimecode()
    start = timeline.GetStartTimecode()
    start_frame = timeline.GetStartFrame()
    _require(
        type(start_frame) is int and start_frame >= 0,
        "actual SDK timeline start frame unavailable",
    )
    return frames(current) - frames(start)


def helper_actor_pin_from_authority(
    store: queue.Store, job_id: str
) -> dict[str, object]:
    """Bind the edited operation to the Conductor's original case attribution.

    A journal must never invent its own actor pin or fall back to AppleScript.
    """
    plan = m4._load_plan(store, job_id)
    path = m4._jobdir(store, job_id) / "f1-gui-edit" / "actor-authority.json"
    try:
        raw = carrier._read(path, 32768)
        record = json.loads(raw)
        _require(
            isinstance(record, dict)
            and set(record) == {"jobId", "actorPin", "planSha256"}
            and record["jobId"] == job_id
            and record["planSha256"]
            == hashlib.sha256(queue.canonical(plan)).hexdigest()
            and raw == queue.canonical(record),
            "immutable per-job helper identity missing",
        )
        from . import resolve_gui_helper_protocol as helper

        helper.validate_actor_pin(record["actorPin"])
        return cast(dict[str, object], record["actorPin"])
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise gui.GuiRollRefused(
            "missing, altered or obsolete case helper actor pin"
        ) from error


def seal_case_actor_pin(store: queue.Store, job_id: str, actor_pin: object) -> None:
    """Bind one immutable Conductor authority actor to the fresh job before edit."""
    from . import resolve_gui_helper_protocol as helper

    helper.validate_actor_pin(actor_pin)
    plan = m4._load_plan(store, job_id)
    _require(plan["caseId"] == helper.FIXTURE, "original fixture identity required")
    root = m4._jobdir(store, job_id) / "f1-gui-edit"
    carrier._private(root, create=True)
    carrier._once(
        root / "actor-authority.json",
        queue.canonical(
            {
                "jobId": job_id,
                "actorPin": actor_pin,
                "planSha256": hashlib.sha256(queue.canonical(plan)).hexdigest(),
            }
        ),
    )


def prepare_owned_f1_inputs(
    store: queue.Store, job_id: str, resolve: Any
) -> tuple[gui.GuiRollIntent, gui.PristineSdkInventory]:
    """Produce trustworthy SDK-based inputs; NO edit, UI, queue, or journal effects.

    A currently owned native host must still separately prove exact UI/TCC
    readiness and enroll the same M4 edited operation before GUI dispatch.
    Reauthenticates the original static admission seal and signed pristine
    output. Source graph drift fails closed: do NOT reseal historical evidence.
    """
    from .qualification_output_controller_v2 import load_output_session
    from .qualification_output_proof_v2 import _load_terminal_output_with_comparison
    from .resolve_test_bench_edit_probe import inspect_selected

    gui._require_owner_lock()
    plan = m4._load_plan(store, job_id)
    receipt = m4._stage_receipt(store, job_id, 0)
    _require(
        plan["caseId"] == "synthetic-312"
        and plan["initialTarget"] != plan["freshTarget"]
        and receipt["session"] == plan["baselineSession"],
        "new original M4 and pristine session source pin required",
    )
    with store.connect() as db:
        parent = db.execute(
            "SELECT state,started_at,deadline_at FROM reverse_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        rows = [
            dict(row)
            for row in db.execute(
                "SELECT ordinal,name,state,operation_id,receipt_sha "
                "FROM reverse_stages WHERE job_id=? ORDER BY ordinal",
                (job_id,),
            )
        ]
    _require(
        parent is not None
        and parent["state"] in {"queued", "awaiting_operator"}
        and parent["started_at"] is not None
        and len(rows) == 4
        and rows[0]["name"] == "pristine"
        and rows[0]["state"] == "verified"
        and rows[0]["receipt_sha"] is not None
        and rows[1]["name"] == "edited"
        and rows[1]["state"] in {"pending", "awaiting_operator"}
        and rows[1]["receipt_sha"] is None
        and all(row["state"] == "pending" for row in rows[2:]),
        "not an eligible one-use M4 edited operation after verified pristine",
    )
    now = datetime.now(UTC)
    deadline = min(
        queue.dt(plan["deadlineAt"]),
        queue.dt(plan["runAt"]) + timedelta(seconds=plan["maxElapsedSeconds"]),
        queue.dt(parent["started_at"]) + timedelta(seconds=plan["maxElapsedSeconds"]),
    )
    _require(
        now + timedelta(seconds=60) < deadline,
        "original cumulative M4 deadline too close or expired",
    )
    session = load_output_session(
        Path(receipt["session"]["path"]), receipt["session"]["sha256"]
    )
    _require(
        session.context.get("phase") == "pristine"
        and session.context.get("target") == plan["initialTarget"],
        "signed original session phase or native target differs",
    )
    _load_terminal_output_with_comparison(session)
    capture = verify_native_result(
        Path(receipt["capture"]["path"]), receipt["capture"]["sha256"]
    )
    geometry = capture.get("nativeGeometry")
    _require(
        capture.get("status") == "complete"
        and capture.get("action") == "capture_post"
        and capture.get("target") == plan["initialTarget"]
        and capture.get("context") == session.context
        and isinstance(geometry, dict),
        "authenticated original native geometry/capture required",
    )
    assert isinstance(geometry, dict)
    sdk = inspect_selected(resolve, plan["initialTarget"], geometry)
    _require(
        sdk.get("disposition") == "read_only_no_edit_authorized"
        and sdk.get("resolveVersion") == [21, 1, 1, 10, ""],
        "installed SDK differs from approved Studio 21.1.1.10",
    )
    _require(resolve.GetCurrentPage() == "edit", "current Edit page not SDK-proven")
    target = gui.NativeTarget(
        project_uid=plan["initialTarget"]["projectUid"],
        project_name=plan["initialTarget"]["projectName"],
        timeline_uid=plan["initialTarget"]["timelineUid"],
        timeline_name=plan["initialTarget"]["timelineName"],
        expected_window_name=plan["initialTarget"]["projectName"],
    )
    manager = resolve.GetProjectManager()
    project = manager.GetCurrentProject() if manager is not None else None
    timeline = project.GetCurrentTimeline() if project is not None else None
    _require(timeline is not None, "actual selected SDK timeline unavailable")
    assert timeline is not None
    selected_clips = timeline.GetSelectedClips()
    _require(
        type(selected_clips) is list and selected_clips == [],
        "whole-clip SDK selection must be empty before named Roll setup",
    )
    playhead_frame = _read_only_playhead_frame(timeline)
    rows_by_uid = {
        row.get("itemUid"): row
        for row in geometry.get("items", [])
        if isinstance(row, dict)
    }
    left = rows_by_uid.get(sdk["leftItemUid"])
    right = rows_by_uid.get(sdk["rightItemUid"])
    _require(
        isinstance(left, dict) and isinstance(right, dict),
        "original signed adjacent native item UID missing",
    )
    assert isinstance(left, dict) and isinstance(right, dict)
    tracks = geometry.get("tracks")
    _require(isinstance(tracks, list), "original six-track matrix unavailable")
    assert isinstance(tracks, list)
    slot = next(
        (
            row
            for row in tracks
            if isinstance(row, dict) and row.get("trackId") == left.get("trackId")
        ),
        None,
    )
    _require(
        isinstance(slot, dict)
        and slot.get("kind") == "video"
        and slot.get("index") == 1,
        "original boundary is not on exact V1 track",
    )
    item_rows = geometry.get("items")
    _require(
        isinstance(item_rows, list)
        and len(item_rows) == gui.NATIVE_ITEM_COUNT
        and all(
            isinstance(item, dict) and type(item.get("itemUid")) is str
            for item in item_rows
        ),
        "eleven signed native item IDs required",
    )
    assert isinstance(item_rows, list)
    inventory = gui.PristineSdkInventory(
        target=target,
        capture_sha256=receipt["capture"]["sha256"],
        item_uids=tuple(row["itemUid"] for row in item_rows),
        left_item_uid=sdk["leftItemUid"],
        right_item_uid=sdk["rightItemUid"],
        left_track_id=left["trackId"],
        right_track_id=right["trackId"],
        left_track_kind="video",
        right_track_kind="video",
        left_track_index=1,
        right_track_index=1,
        left_record_start=left["recordStart"],
        left_record_duration=left["recordDuration"],
        right_record_start=right["recordStart"],
        right_record_duration=right["recordDuration"],
        boundary_frame=gui.BEFORE_BOUNDARY,
        playhead_frame=playhead_frame,
        track_count=len(tracks),
        extent_frames=geometry["extentFrames"],
        rate=(geometry["rate"]["numerator"], geometry["rate"]["denominator"]),
        pristine_verified=True,
    )
    intent = gui.GuiRollIntent(
        actuator_class="gui",
        operation="M4.edited",
        stage_operation_id=rows[1]["operation_id"],
        target=target,
        pristine_capture_sha256=receipt["capture"]["sha256"],
        item_uids=inventory.item_uids,
        left_item_uid=inventory.left_item_uid,
        right_item_uid=inventory.right_item_uid,
        actor_pin=helper_actor_pin_from_authority(store, job_id),
        expires_at=min(deadline, now + timedelta(minutes=4)),
    )
    _verify_original_capture(store, job_id, intent, inventory)
    _require(
        inventory.playhead_frame == gui.AFTER_BOUNDARY,
        "actual SDK playhead must already be at 351 before GUI intent",
    )
    return intent, inventory
