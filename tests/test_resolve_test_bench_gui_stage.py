"""#473 F1 bindings: fake SDK/OS only; never operate a real Resolve instance."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from vera_timeline_agent import resolve_gui_roll as gui
from vera_timeline_agent import resolve_test_bench_gui_stage as stage
from vera_timeline_agent import resolve_test_queue_m4 as m4

JOB = "resolve-reverse-" + "a" * 32
NAME = "VERA Delivery 123e4567-e89b-12d3-a456-426614174000 012345abcdef"
TARGET = gui.NativeTarget("fresh-project", NAME, "fresh-timeline", NAME, NAME)
UIDS = tuple(f"item-{i}" for i in range(11))
SHA = "a" * 64


class FakeStore:
    def __init__(self, db: sqlite3.Connection, root: Path):
        self.db = db
        self.root = root
        self.root.mkdir(mode=0o700)

    def connect(self) -> sqlite3.Connection:
        return self.db


class FakeExecutor:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    def execute_once(self, window_name: str) -> None:
        assert window_name == NAME
        self.calls += 1
        if self.fail:
            raise OSError("crash after GUI dispatch")


@pytest.fixture
def setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[
    tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ]
]:
    now = datetime.now(UTC)
    intent = gui.GuiRollIntent(
        actuator_class="gui",
        operation="M4.edited",
        stage_operation_id="fresh-edited-001",
        target=TARGET,
        pristine_capture_sha256=SHA,
        item_uids=UIDS,
        left_item_uid=UIDS[0],
        right_item_uid=UIDS[1],
        script_sha256=gui.ROLL_SCRIPT_SHA256,
        expires_at=now + timedelta(minutes=2),
    )
    inventory = gui.PristineSdkInventory(
        target=TARGET,
        capture_sha256=SHA,
        item_uids=UIDS,
        left_item_uid=UIDS[0],
        right_item_uid=UIDS[1],
        left_track_id="original-V1",
        right_track_id="original-V1",
        left_track_kind="video",
        right_track_kind="video",
        left_track_index=1,
        right_track_index=1,
        left_record_start=0,
        left_record_duration=327,
        right_record_start=327,
        right_record_duration=151,
        boundary_frame=327,
        playhead_frame=327,
        track_count=6,
        extent_frames=1407,
        rate=(24000, 1001),
        pristine_verified=True,
    )
    readiness = gui.TrustedUiReadiness(
        os_name="Darwin",
        resolve_version=gui.RESOLVE_VERSION,
        resolve_bundle_id=gui.RESOLVE_BUNDLE_ID,
        frontmost_bundle_id=gui.RESOLVE_BUNDLE_ID,
        frontmost_process=gui.RESOLVE_PROCESS,
        front_window_name=NAME,
        accessibility_trusted=True,
        automation_trusted=True,
        modal_present=False,
        edit_page=True,
        timeline_focused=True,
        v1_only=True,
        trim_roll_menu_enabled=True,
        nudge_menu_enabled=True,
        keyboard_preset=gui.KEYBOARD_PRESET,
        keyboard_focus_binding="Command-4",
        keyboard_nudge_binding=".",
    )
    plan = {
        "caseId": "synthetic-312",
        "initialTarget": stage._target_dict(TARGET),
        "freshTarget": {
            "projectUid": "another-project",
            "projectName": "another",
            "timelineUid": "another-timeline",
            "timelineName": "another",
        },
        "deadlineAt": (now + timedelta(minutes=10)).isoformat(),
        "runAt": (now - timedelta(minutes=1)).isoformat(),
        "maxElapsedSeconds": 3600,
    }
    monkeypatch.setattr(m4, "_load_plan", lambda _store, _job: plan)
    monkeypatch.setattr(
        m4,
        "_stage_receipt",
        lambda _store, _job, _ordinal: {
            "capture": {"path": str(tmp_path / "signed-pristine.json"), "sha256": SHA}
        },
    )
    geometry = {
        "rate": {"numerator": 24000, "denominator": 1001},
        "extentFrames": 1407,
        "tracks": [{"trackId": f"track-{i}"} for i in range(6)],
        "items": [
            {
                "itemUid": uid,
                "kind": "video" if i < 2 else "audio",
                "trackId": "original-V1" if i < 2 else f"track-{i}",
                "recordStart": 0 if i == 0 else 327,
                "recordDuration": 327 if i == 0 else 151,
            }
            for i, uid in enumerate(UIDS)
        ],
    }
    signed = {
        "status": "complete",
        "action": "capture_post",
        "target": stage._target_dict(TARGET),
        "context": {"target": stage._target_dict(TARGET)},
        "nativeGeometry": geometry,
    }
    monkeypatch.setattr(stage, "verify_native_result", lambda *_args: signed)
    monkeypatch.setattr(gui, "_require_owner_lock", lambda: None)
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        "CREATE TABLE reverse_stages (job_id TEXT, ordinal INTEGER, name TEXT, "
        "state TEXT, operation_id TEXT, receipt_sha TEXT)"
    )
    db.execute(
        "CREATE TABLE reverse_jobs (id TEXT, state TEXT, started_at TEXT, "
        "deadline_at REAL)"
    )
    db.execute(
        "INSERT INTO reverse_jobs VALUES (?,?,?,?)",
        (
            JOB,
            "awaiting_operator",
            (now - timedelta(minutes=1)).isoformat(),
            (now + timedelta(minutes=10)).timestamp(),
        ),
    )
    for ordinal, name in enumerate(("pristine", "edited", "revision", "rebuild")):
        db.execute(
            "INSERT INTO reverse_stages VALUES (?,?,?,?,?,?)",
            (
                JOB,
                ordinal,
                name,
                "verified"
                if ordinal == 0
                else "awaiting_operator"
                if ordinal == 1
                else "pending",
                "pristine-001" if ordinal == 0 else intent.stage_operation_id,
                SHA if ordinal == 0 else None,
            ),
        )
    yield (
        FakeStore(db, tmp_path / "queue"),
        intent,
        inventory,
        readiness,
        FakeExecutor(),
    )
    db.close()


def _call(
    values: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
) -> gui.GuiRollAttempt:
    store, intent, inventory, readiness, executor = values
    return stage.attempt_once(store, JOB, intent, inventory, readiness, executor)  # type: ignore[arg-type]


def _journal_root(
    values: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
) -> Path:
    return values[0].root / JOB / "f1-gui-edit"


def test_exact_new_stage_spends_once_never_fabricates_receipt(
    tmp_path: Path,
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
) -> None:
    root = _journal_root(setup)
    result = _call(setup)
    assert result.state == "unknown"
    assert result.native_verified is False and result.receipt_issued is False
    assert setup[4].calls == 1
    journal = json.loads((root / "gui-intent.json").read_bytes())
    assert journal["actuatorClass"] == "gui"
    assert journal["operationId"] == "fresh-edited-001"
    assert journal["captureSha256"] == SHA
    assert journal["scriptSha256"] == gui.ROLL_SCRIPT_SHA256
    with pytest.raises(gui.GuiRollUnknown, match="no GUI dispatch"):
        _call(setup)
    assert setup[4].calls == 1


def test_unknown_after_dispatch_is_irrevocably_spent(
    tmp_path: Path,
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
) -> None:
    setup[4].fail = True
    with pytest.raises(gui.GuiRollUnknown, match="no retry"):
        _call(setup)
    assert (_journal_root(setup) / "gui-intent.json").exists()
    with pytest.raises(gui.GuiRollUnknown, match="no GUI dispatch"):
        _call(setup)
    assert setup[4].calls == 1


def test_crash_after_fsync_before_os_dispatch_preserves_spent_intent(
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_once = stage.carrier._once

    def crash_after_fsync(path: Path, raw: bytes) -> None:
        original_once(path, raw)
        raise OSError("simulated loss after durable one-use write")

    monkeypatch.setattr(stage.carrier, "_once", crash_after_fsync)
    with pytest.raises(gui.GuiRollUnknown, match="no GUI dispatch"):
        _call(setup)
    assert (_journal_root(setup) / "gui-intent.json").exists()
    assert setup[4].calls == 0
    monkeypatch.setattr(stage.carrier, "_once", original_once)
    with pytest.raises(gui.GuiRollUnknown, match="no GUI dispatch"):
        _call(setup)
    assert setup[4].calls == 0


@pytest.mark.parametrize("state", ["pending", "verified", "unknown", "verifying"])
def test_no_spend_without_fresh_awaiting_edited_stage(
    tmp_path: Path,
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
    state: str,
) -> None:
    setup[0].db.execute("UPDATE reverse_stages SET state=? WHERE ordinal=1", (state,))
    with pytest.raises(gui.GuiRollUnknown, match="no GUI dispatch"):
        _call(setup)
    assert not (_journal_root(setup) / "gui-intent.json").exists()
    assert setup[4].calls == 0


def test_stale_signed_geometry_refuses_before_intent(
    tmp_path: Path,
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = {
        "status": "complete",
        "action": "capture_post",
        "target": stage._target_dict(TARGET),
        "context": {"target": stage._target_dict(TARGET)},
        "nativeGeometry": {"items": []},
    }
    monkeypatch.setattr(stage, "verify_native_result", lambda *_args: fake)
    with pytest.raises(gui.GuiRollRefused, match="geometry incomplete"):
        _call(setup)
    assert not (_journal_root(setup) / "gui-intent.json").exists()


def test_no_spend_with_expired_original_m4_deadline(
    tmp_path: Path,
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    monkeypatch.setattr(
        m4,
        "_load_plan",
        lambda _store, _job: {
            "caseId": "synthetic-312",
            "initialTarget": stage._target_dict(TARGET),
            "freshTarget": {"projectUid": "different"},
            "deadlineAt": (now - timedelta(minutes=2)).isoformat(),
            "runAt": (now - timedelta(hours=2)).isoformat(),
            "maxElapsedSeconds": 3600,
        },
    )
    with pytest.raises(gui.GuiRollUnknown, match="no GUI dispatch"):
        _call(setup)
    assert not (_journal_root(setup) / "gui-intent.json").exists()


@pytest.mark.parametrize(
    "corruption",
    [
        "wrong-target",
        "missing-permission",
        "unreviewed-script",
        "changed-item-uid",
    ],
)
def test_gui_admission_fails_closed_on_source_and_environment(
    tmp_path: Path,
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
    corruption: str,
) -> None:
    store, intent, inventory, readiness, executor = setup
    if corruption == "wrong-target":
        intent = replace(intent, target=replace(TARGET, project_uid="foreign-project"))
    elif corruption == "missing-permission":
        readiness = replace(readiness, accessibility_trusted=False)
    elif corruption == "unreviewed-script":
        intent = replace(intent, script_sha256="b" * 64)
    else:
        inventory = replace(inventory, item_uids=(*UIDS[:-1], "substituted"))
    with pytest.raises((gui.GuiRollUnknown, gui.GuiRollRefused)):
        stage.attempt_once(
            store,  # type: ignore[arg-type]
            JOB,
            intent,
            inventory,
            readiness,
            executor,
        )
    assert not (_journal_root(setup) / "gui-intent.json").exists()
    assert executor.calls == 0


def test_parent_job_not_awaiting_operator_refuses_before_spend(
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
) -> None:
    setup[0].db.execute("UPDATE reverse_jobs SET state='unknown' WHERE id=?", (JOB,))
    with pytest.raises(gui.GuiRollUnknown, match="no GUI dispatch"):
        _call(setup)
    assert not (_journal_root(setup) / "gui-intent.json").exists()
    assert setup[4].calls == 0


def test_wrong_m4_operation_id_refuses_without_spend(
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
) -> None:
    store, intent, inventory, readiness, executor = setup
    intent = replace(intent, stage_operation_id="different-new-operation")
    with pytest.raises(gui.GuiRollUnknown, match="no GUI dispatch"):
        stage.attempt_once(
            store,  # type: ignore[arg-type]
            JOB,
            intent,
            inventory,
            readiness,
            executor,
        )
    assert not (_journal_root(setup) / "gui-intent.json").exists()
    assert executor.calls == 0
