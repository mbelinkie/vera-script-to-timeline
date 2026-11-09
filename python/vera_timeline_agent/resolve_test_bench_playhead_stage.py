"""Narrow, SDK-owned frame-327 navigation before one-use F1 GUI dispatch.

The original output host does not promise to leave its playhead at the 327
picture cut. A fresh unattended one-start would otherwise fail the already
reviewed read-only F1 precondition. This does not edit, save or render media:
it moves only the *exact* independently verified pristine disposable timeline
playhead, then rechecks position and native geometry under the same owner.

The caller must first claim the original M4 edited stage, retain its separate
Producer approval and the full-loop pre-effect intent. On any partial failure
it must stop; a replay may not retarget or apply a second GUI operation.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from . import resolve_gui_roll as roll
from . import resolve_test_bench_gui_stage as gui
from . import resolve_test_queue as queue
from . import resolve_test_queue_m4 as m4
from .qualification_output_controller_v2 import load_output_session
from .qualification_output_native_v2 import verify_native_result
from .qualification_output_proof_v2 import _load_terminal_output_with_comparison
from .resolve_test_bench_edit_probe import inspect_selected


def _require(value: bool, reason: str) -> None:
    if not value:
        raise queue.QueueError(
            "original M4 owned playhead preflight refused: " + reason
        )


def _frames(timecode: Any) -> int:
    _require(
        isinstance(timecode, str)
        and re.fullmatch(r"[0-9]{2}:[0-9]{2}:[0-9]{2}:[0-9]{2}", timecode) is not None,
        "actual 24-nominal non-drop SDK timecode required",
    )
    assert isinstance(timecode, str)
    hours, minutes, seconds, frame = map(int, timecode.split(":"))
    _require(
        hours < 24 and minutes < 60 and seconds < 60 and frame < 24,
        "invalid 24-nominal SDK timecode component",
    )
    return ((hours * 60 + minutes) * 60 + seconds) * 24 + frame


def _timecode(frames: int) -> str:
    _require(
        type(frames) is int and 0 <= frames < 24 * 60 * 60 * 24,
        "playhead offset would wrap the one-day timecode",
    )
    frame = frames % 24
    seconds = frames // 24
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}:{frame:02}"


def position_owned_327(store: queue.Store, job_id: str, resolve: Any) -> None:
    """Safe fixed SDK navigation, verified before *and* after touching playhead."""
    roll._require_owner_lock()
    plan = m4._load_plan(store, job_id)
    _require(
        plan["caseId"] == "synthetic-312"
        and plan["initialTarget"] != plan["freshTarget"],
        "only new distinct Test Bench targets eligible",
    )
    gui_root = m4._jobdir(store, job_id) / "f1-gui-edit"
    gui_intent = gui_root / "gui-intent.json"

    def check_unspent_and_fresh() -> None:
        _require(
            not gui_root.is_symlink()
            and not gui_intent.exists()
            and not gui_intent.is_symlink(),
            "one-use GUI journal already spent or uncertain",
        )
        with store.connect() as db:
            parent = db.execute(
                "SELECT state,started_at,deadline_at FROM reverse_jobs WHERE id=?",
                (job_id,),
            ).fetchone()
            edited = db.execute(
                "SELECT state,intent_at,receipt_sha FROM reverse_stages "
                "WHERE job_id=? AND ordinal=1",
                (job_id,),
            ).fetchone()
        _require(
            parent is not None
            and edited is not None
            and parent["state"] == "awaiting_operator"
            and parent["started_at"] is not None
            and parent["deadline_at"] == queue.dt(plan["deadlineAt"]).timestamp()
            and edited["state"] == "awaiting_operator"
            and edited["receipt_sha"] is None
            and isinstance(edited["intent_at"], str),
            "one newly enrolled, unspent edited operation required",
        )
        started = queue.dt(parent["started_at"])
        intent = queue.dt(edited["intent_at"])
        deadline = min(
            queue.dt(plan["deadlineAt"]),
            queue.dt(plan["runAt"]) + timedelta(seconds=plan["maxElapsedSeconds"]),
            started + timedelta(seconds=plan["maxElapsedSeconds"]),
        )
        now = datetime.now(UTC)
        _require(
            started <= intent <= now and now + timedelta(seconds=60) < deadline,
            "one-use edited intent or cumulative M4 deadline expired",
        )

    check_unspent_and_fresh()
    receipt = m4._stage_receipt(store, job_id, 0)
    _require(
        receipt["session"] == plan["baselineSession"],
        "pinned original pristine session changed",
    )
    with store.connect() as db:
        parent = db.execute(
            "SELECT state FROM reverse_jobs WHERE id=?", (job_id,)
        ).fetchone()
        rows = [
            dict(row)
            for row in db.execute(
                "SELECT ordinal,state,receipt_sha,intent_at FROM reverse_stages "
                "WHERE job_id=? ORDER BY ordinal",
                (job_id,),
            )
        ]
    _require(
        parent is not None
        and parent["state"] == "awaiting_operator"
        and len(rows) == 4
        and rows[0]["state"] == "verified"
        and rows[0]["receipt_sha"] is not None
        and rows[1]["state"] == "awaiting_operator"
        and rows[1]["intent_at"] is not None
        and rows[1]["receipt_sha"] is None
        and all(row["state"] == "pending" for row in rows[2:]),
        "one original edited M4 intent must already be exclusively enrolled",
    )
    session = load_output_session(
        Path(receipt["session"]["path"]), receipt["session"]["sha256"]
    )
    _require(
        session.context.get("phase") == "pristine"
        and session.context.get("caseId") == plan["caseId"]
        and session.context.get("target") == plan["initialTarget"],
        "source-sealed output session differs from original target",
    )
    _load_terminal_output_with_comparison(session)
    result = verify_native_result(
        Path(receipt["capture"]["path"]), receipt["capture"]["sha256"]
    )
    native_geometry = result.get("nativeGeometry")
    _require(
        result.get("status") == "complete"
        and result.get("action") == "capture_post"
        and result.get("context") == session.context
        and result.get("target") == plan["initialTarget"]
        and isinstance(native_geometry, dict),
        "real sealed pristine capture and exact SDK target required",
    )
    assert isinstance(native_geometry, dict)
    before = inspect_selected(resolve, plan["initialTarget"], native_geometry)
    _require(
        before.get("disposition") == "read_only_no_edit_authorized"
        and before.get("resolveVersion") == [21, 1, 1, 10, ""],
        "only exact verified Studio 21.1.1.10 native inventory eligible",
    )
    manager = resolve.GetProjectManager()
    project = manager.GetCurrentProject() if manager is not None else None
    timeline = project.GetCurrentTimeline() if project is not None else None
    _require(
        project is not None
        and timeline is not None
        and project.GetUniqueId() == plan["initialTarget"]["projectUid"]
        and project.GetName() == plan["initialTarget"]["projectName"]
        and timeline.GetUniqueId() == plan["initialTarget"]["timelineUid"]
        and timeline.GetName() == plan["initialTarget"]["timelineName"]
        and project.IsRenderingInProgress() is False,
        "actual selected project UID or timeline UID/idle state changed",
    )
    assert timeline is not None
    current = gui._read_only_playhead_frame(timeline)
    if current != roll.BEFORE_BOUNDARY:
        check_unspent_and_fresh()
        start = _frames(timeline.GetStartTimecode())
        wanted = _timecode(start + roll.BEFORE_BOUNDARY)
        _require(
            timeline.SetCurrentTimecode(wanted) is True,
            "exact reversible SDK playhead navigation refused",
        )
    _require(
        gui._read_only_playhead_frame(timeline) == roll.BEFORE_BOUNDARY,
        "SDK playhead did not land on exact 327-frame cut",
    )
    check_unspent_and_fresh()
    after = inspect_selected(resolve, plan["initialTarget"], native_geometry)
    _require(
        after == before,
        "timeline native inventory/source/position changed during navigation",
    )
