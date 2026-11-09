"""#473 F1 bindings: fake SDK/OS only; never operate a real Resolve instance."""

from __future__ import annotations

import json
import shutil
import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from vera_timeline_agent import resolve_gui_roll as gui
from vera_timeline_agent import resolve_test_bench_carrier as carrier
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
        "baselineSession": {"path": str(tmp_path / "baseline.json"), "sha256": SHA},
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
        "maxDiskBytes": 1048576,
    }
    monkeypatch.setattr(m4, "_load_plan", lambda _store, _job: plan)
    monkeypatch.setattr(
        m4,
        "_stage_receipt",
        lambda _store, _job, _ordinal: {
            "session": plan["baselineSession"],
            "capture": {"path": str(tmp_path / "signed-pristine.json"), "sha256": SHA},
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
    original_once = carrier._once

    def crash_after_fsync(path: Path, raw: bytes) -> None:
        original_once(path, raw)
        raise OSError("simulated loss after durable one-use write")

    monkeypatch.setattr(carrier, "_once", crash_after_fsync)
    with pytest.raises(gui.GuiRollUnknown, match="no GUI dispatch"):
        _call(setup)
    assert (_journal_root(setup) / "gui-intent.json").exists()
    assert setup[4].calls == 0
    monkeypatch.setattr(carrier, "_once", original_once)
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
            "baselineSession": {"path": str(tmp_path / "baseline.json"), "sha256": SHA},
            "initialTarget": stage._target_dict(TARGET),
            "freshTarget": {"projectUid": "different"},
            "deadlineAt": (now - timedelta(minutes=2)).isoformat(),
            "runAt": (now - timedelta(hours=2)).isoformat(),
            "maxElapsedSeconds": 3600,
            "maxDiskBytes": 1048576,
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


def test_pristine_session_source_pin_mismatch_fails_before_gui(
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = m4._stage_receipt

    def tampered(store: FakeStore, job_id: str, ordinal: int) -> dict[str, object]:
        receipt = dict(original(store, job_id, ordinal))  # type: ignore[arg-type]
        receipt["session"] = {"path": "/tmp/other-session.json", "sha256": SHA}
        return receipt

    monkeypatch.setattr(m4, "_stage_receipt", tampered)
    with pytest.raises(gui.GuiRollRefused, match="session/source pin differs"):
        _call(setup)
    assert not (_journal_root(setup) / "gui-intent.json").exists()
    assert setup[4].calls == 0


def test_m4_disk_reserve_blocks_before_spend(
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "disk_usage", lambda *_args: SimpleNamespace(free=0))
    with pytest.raises(gui.GuiRollUnknown, match="no GUI dispatch"):
        _call(setup)
    assert not (_journal_root(setup) / "gui-intent.json").exists()
    assert setup[4].calls == 0


def _setup_read_only_f1_preparation(
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
    monkeypatch: pytest.MonkeyPatch,
    *,
    current_timecode: str = "00:00:13:15",
    version: list[object] | None = None,
) -> tuple[SimpleNamespace, list[str]]:
    """Fake SDK and signed-loader boundaries, never any GUI dispatch."""
    from vera_timeline_agent import qualification_output_controller_v2 as controller
    from vera_timeline_agent import qualification_output_proof_v2 as proof
    from vera_timeline_agent import resolve_test_bench_edit_probe as probe

    expected_target = stage._target_dict(TARGET)
    events: list[str] = []
    monkeypatch.setattr(
        controller,
        "load_output_session",
        lambda *_args: SimpleNamespace(
            context={"phase": "pristine", "target": expected_target}
        ),
    )

    def verified(*_args: object) -> None:
        events.append("verified")

    monkeypatch.setattr(proof, "_load_terminal_output_with_comparison", verified)
    original_result = stage.__dict__["verify_native_result"](Path(""), SHA)
    geometry = dict(original_result["nativeGeometry"])
    geometry["tracks"] = [
        {"trackId": "original-V1", "kind": "video", "index": 1},
        *(
            {"trackId": f"track-{index}", "kind": "audio", "index": index}
            for index in range(1, 6)
        ),
    ]

    def signed(*_args: object) -> dict[str, object]:
        return {
            **original_result,
            "context": {"phase": "pristine", "target": expected_target},
            "nativeGeometry": geometry,
        }

    monkeypatch.setattr(stage, "verify_native_result", signed)

    def inspect(_resolve: object, target: object, signed: object) -> dict[str, object]:
        events.append("read-only SDK inspected")
        assert target == expected_target and signed is geometry
        return {
            "disposition": "read_only_no_edit_authorized",
            "resolveVersion": [21, 1, 1, 10, ""] if version is None else version,
            "leftItemUid": UIDS[0],
            "rightItemUid": UIDS[1],
        }

    monkeypatch.setattr(probe, "inspect_selected", inspect)
    timeline = SimpleNamespace(
        GetCurrentTimecode=lambda: current_timecode,
        GetStartTimecode=lambda: "00:00:00:00",
        GetStartFrame=lambda: 0,
    )
    sdk = SimpleNamespace(
        GetProjectManager=lambda: SimpleNamespace(
            GetCurrentProject=lambda: SimpleNamespace(
                GetCurrentTimeline=lambda: timeline
            )
        )
    )
    return sdk, events


def test_owned_f1_input_factory_binds_exact_verified_sdk_evidence_no_effect(
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk, events = _setup_read_only_f1_preparation(setup, monkeypatch)
    intent, inventory = stage.prepare_owned_f1_inputs(setup[0], JOB, sdk)  # type: ignore[arg-type]
    assert intent.stage_operation_id == setup[1].stage_operation_id
    assert intent.script_sha256 == gui.ROLL_SCRIPT_SHA256
    assert intent.item_uids == UIDS
    assert inventory.playhead_frame == 327
    assert inventory.left_record_duration == 327
    assert inventory.right_record_start == 327
    assert inventory.right_record_duration == 151
    assert inventory.target == TARGET
    assert events == ["verified", "read-only SDK inspected"]
    assert setup[4].calls == 0
    assert not (_journal_root(setup) / "gui-intent.json").exists()
    assert (
        setup[0]
        .db.execute("SELECT state FROM reverse_stages WHERE ordinal=1")
        .fetchone()[0]
        == "awaiting_operator"
    )


@pytest.mark.parametrize(
    ("timecode", "version", "expected"),
    [
        ("00:00:00:00", None, "playhead must already"),
        ("00:00:13:14", None, "playhead must already"),
        ("00:00:13;15", None, "playhead/timecode unavailable"),
        ("00:00:13:24", None, "timecode component"),
        ("00:00:13:15", [21, 1, 1, 10, None], "installed SDK differs"),
        ("00:00:13:15", [21, 1, 2, 10, ""], "installed SDK differs"),
    ],
)
def test_owned_f1_input_factory_refuses_unproved_playhead_and_sdk(
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
    monkeypatch: pytest.MonkeyPatch,
    timecode: str,
    version: list[object] | None,
    expected: str,
) -> None:
    sdk, _ = _setup_read_only_f1_preparation(
        setup, monkeypatch, current_timecode=timecode, version=version
    )
    with pytest.raises(gui.GuiRollRefused, match=expected):
        stage.prepare_owned_f1_inputs(setup[0], JOB, sdk)  # type: ignore[arg-type]
    assert setup[4].calls == 0
    assert not (_journal_root(setup) / "gui-intent.json").exists()


def test_owned_f1_input_factory_refuses_changed_source_seal_before_sdk(
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vera_timeline_agent import qualification_output_controller_v2 as controller

    sdk, events = _setup_read_only_f1_preparation(setup, monkeypatch)

    def reject_seal(*_args: object) -> None:
        raise ValueError("admission seal metadata differs")

    monkeypatch.setattr(controller, "load_output_session", reject_seal)
    with pytest.raises(ValueError, match="admission seal metadata differs"):
        stage.prepare_owned_f1_inputs(setup[0], JOB, sdk)  # type: ignore[arg-type]
    assert events == []
    assert setup[4].calls == 0
    assert not (_journal_root(setup) / "gui-intent.json").exists()


def test_owned_f1_input_factory_refuses_edited_or_later_stage_replay(
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk, events = _setup_read_only_f1_preparation(setup, monkeypatch)
    setup[0].db.execute("UPDATE reverse_stages SET state='verified' WHERE ordinal=2")
    with pytest.raises(gui.GuiRollRefused, match="eligible one-use"):
        stage.prepare_owned_f1_inputs(setup[0], JOB, sdk)  # type: ignore[arg-type]
    assert events == []
    assert not (_journal_root(setup) / "gui-intent.json").exists()


def test_owned_f1_input_factory_requires_original_m4_time_budget(
    setup: tuple[
        FakeStore,
        gui.GuiRollIntent,
        gui.PristineSdkInventory,
        gui.TrustedUiReadiness,
        FakeExecutor,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk, events = _setup_read_only_f1_preparation(setup, monkeypatch)
    setup[0].db.execute(
        "UPDATE reverse_jobs SET started_at=? WHERE id=?",
        ((datetime.now(UTC) - timedelta(hours=3)).isoformat(), JOB),
    )
    with pytest.raises(gui.GuiRollRefused, match="deadline"):
        stage.prepare_owned_f1_inputs(setup[0], JOB, sdk)  # type: ignore[arg-type]
    assert events == []
    assert not (_journal_root(setup) / "gui-intent.json").exists()
