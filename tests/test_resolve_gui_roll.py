"""#495 F1 actuator tests: synthetic SDK/UI data, no real Resolve or GUI."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import resolve_gui_roll as gui

NOW = datetime(2026, 11, 8, 20, 0, tzinfo=UTC)
NAME = "VERA Delivery 123e4567-e89b-12d3-a456-426614174000 012345abcdef"
TARGET = gui.NativeTarget("project-uid", NAME, "timeline-uid", NAME, NAME)
UIDS = tuple(f"original-item-{i}" for i in range(11))


def valid() -> tuple[
    gui.GuiRollIntent, gui.PristineSdkInventory, gui.TrustedUiReadiness
]:
    receipt = "a" * 64
    intent = gui.GuiRollIntent(
        actuator_class="gui",
        operation="M4.edited",
        stage_operation_id="m4-edited-test-001",
        target=TARGET,
        pristine_capture_sha256=receipt,
        item_uids=UIDS,
        left_item_uid=UIDS[0],
        right_item_uid=UIDS[1],
        script_sha256=gui.ROLL_SCRIPT_SHA256,
        expires_at=NOW + timedelta(minutes=5),
    )
    inventory = gui.PristineSdkInventory(
        target=TARGET,
        capture_sha256=receipt,
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
        resolve_version="21.1.1.10",
        resolve_bundle_id=gui.RESOLVE_BUNDLE_ID,
        frontmost_bundle_id=gui.RESOLVE_BUNDLE_ID,
        frontmost_process="Resolve",
        front_window_name=NAME,
        accessibility_trusted=True,
        automation_trusted=True,
        modal_present=False,
        edit_page=True,
        timeline_focused=True,
        v1_only=True,
        trim_roll_menu_enabled=True,
        nudge_menu_enabled=True,
        keyboard_preset="DaVinci Resolve",
        keyboard_focus_binding="Command-4",
        keyboard_nudge_binding=".",
    )
    return intent, inventory, readiness


class FakeJournal:
    def __init__(self) -> None:
        self.spent: set[str] = set()
        self.calls = 0
        self.fail_ambiguously = False

    def consume_before_effect(self, intent: gui.GuiRollIntent) -> bool:
        self.calls += 1
        if self.fail_ambiguously:
            raise OSError("disk write unsure")
        if intent.stage_operation_id in self.spent:
            return False
        self.spent.add(intent.stage_operation_id)
        return True


class FakeExecutor:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[str] = []
        self.error = error

    def execute_once(self, expected_window_name: str) -> None:
        self.calls.append(expected_window_name)
        if self.error is not None:
            raise self.error


@pytest.fixture(autouse=True)
def prohibit_real_process(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("unit tests must not run real osascript/Resolve")

    monkeypatch.setattr(subprocess, "run", blocked)


@pytest.fixture
def admitted_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    # Fake-only owner. Production must use the held original native-owner FD.
    monkeypatch.setattr(gui, "_require_owner_lock", lambda: None)


def test_fixed_f1_script_is_24_named_menu_events_no_arbitrary_input() -> None:
    source = gui.ROLL_APPLESCRIPT
    assert hashlib.sha256(source.encode()).hexdigest() == gui.ROLL_SCRIPT_SHA256
    assert source.count("repeat 24 times") == 1
    assert source.count('click menu item "One Frame Right"') == 1
    for exact_menu in (
        'menu "Workspace"',
        'menu item "Edit"',
        'menu "Timeline"',
        'menu item "Auto Deselect All Tracks"',
        'menu item "Auto Select/Deselect V1"',
        'menu "Trim"',
        'menu item "Select Nearest Edit To"',
        'menu item "Roll"',
        'menu item "Nudge"',
    ):
        assert exact_menu in source
    assert "click at" not in source
    assert "do shell script" not in source
    assert "grant" not in source.lower()
    assert "SaveProject" not in source


def test_script_changed_before_admission_does_not_spend_or_dispatch(
    monkeypatch: pytest.MonkeyPatch, admitted_owner: None
) -> None:
    intent, inventory, readiness = valid()
    journal, executor = FakeJournal(), FakeExecutor()
    monkeypatch.setattr(gui, "ROLL_APPLESCRIPT", gui.ROLL_APPLESCRIPT + "\n-- changed")
    with pytest.raises(gui.GuiRollRefused, match="reviewed GUI script hash differs"):
        gui.OneUseGuiRollActuator(journal, executor).attempt(
            intent, inventory, readiness, now=NOW
        )
    assert journal.calls == 0 and executor.calls == []


def test_script_changed_after_journal_consume_cannot_reach_osascript(
    monkeypatch: pytest.MonkeyPatch, admitted_owner: None
) -> None:
    intent, inventory, readiness = valid()

    class TamperJournal(FakeJournal):
        def consume_before_effect(self, intent: gui.GuiRollIntent) -> bool:
            consumed = super().consume_before_effect(intent)
            monkeypatch.setattr(gui, "ROLL_APPLESCRIPT", "-- altered after consume")
            return consumed

    journal = TamperJournal()
    actuator = gui.OneUseGuiRollActuator(journal, gui.SystemEventsRollExecutor())
    with pytest.raises(gui.GuiRollUnknown, match="no retry"):
        actuator.attempt(intent, inventory, readiness, now=NOW)
    with pytest.raises(gui.GuiRollRefused, match="already been dispatched"):
        actuator.attempt(intent, inventory, readiness, now=NOW)
    assert journal.spent == {intent.stage_operation_id}


def test_single_dispatch_reports_unknown_only(admitted_owner: None) -> None:
    intent, inventory, readiness = valid()
    journal = FakeJournal()
    executor = FakeExecutor()
    result = gui.OneUseGuiRollActuator(journal, executor).attempt(
        intent, inventory, readiness, now=NOW
    )
    assert journal.calls == 1
    assert journal.spent == {intent.stage_operation_id}
    assert executor.calls == [NAME]
    assert result == gui.GuiRollAttempt(
        state="unknown",
        actuator_class="gui",
        stage_operation_id=intent.stage_operation_id,
        requested_frame_events=24,
        native_verified=False,
        receipt_issued=False,
    )
    assert "success" not in repr(result).lower()


@pytest.mark.parametrize(
    ("component", "changes"),
    [
        ("intent", {"actuator_class": "native"}),
        ("intent", {"operation": "M4.pristine"}),
        ("intent", {"stage_operation_id": ""}),
        ("intent", {"target": replace(TARGET, project_uid="other")}),
        ("intent", {"target": replace(TARGET, project_name="Producer personal")}),
        ("intent", {"target": replace(TARGET, timeline_name="different timeline")}),
        ("intent", {"target": replace(TARGET, expected_window_name="other")}),
        ("intent", {"pristine_capture_sha256": "b" * 64}),
        ("intent", {"item_uids": (*UIDS[:-1], "replaced-item")}),
        ("intent", {"left_item_uid": "other-item"}),
        ("intent", {"right_item_uid": UIDS[0]}),
        ("intent", {"script_sha256": "b" * 64}),
        ("intent", {"expires_at": NOW}),
        ("inventory", {"target": replace(TARGET, timeline_uid="new-native-timeline")}),
        ("inventory", {"pristine_verified": False}),
        ("inventory", {"capture_sha256": "b" * 64}),
        ("inventory", {"item_uids": (*UIDS[:-1], UIDS[0])}),
        ("inventory", {"left_item_uid": UIDS[2]}),
        ("inventory", {"right_item_uid": UIDS[0]}),
        ("inventory", {"right_track_id": "foreign-track"}),
        ("inventory", {"right_track_index": 2}),
        ("inventory", {"left_track_kind": "audio"}),
        ("inventory", {"left_record_duration": 326}),
        ("inventory", {"right_record_start": 351}),
        ("inventory", {"right_record_duration": 127}),
        ("inventory", {"boundary_frame": 351}),
        ("inventory", {"playhead_frame": 326}),
        ("inventory", {"track_count": 5}),
        ("inventory", {"extent_frames": 1408}),
        ("inventory", {"rate": (24, 1)}),
        ("readiness", {"os_name": "Linux"}),
        ("readiness", {"resolve_version": "21.1.2.0"}),
        ("readiness", {"resolve_bundle_id": "other-app"}),
        ("readiness", {"frontmost_bundle_id": "com.apple.finder"}),
        ("readiness", {"frontmost_process": "Finder"}),
        ("readiness", {"front_window_name": "Other Project"}),
        ("readiness", {"accessibility_trusted": False}),
        ("readiness", {"automation_trusted": False}),
        ("readiness", {"modal_present": True}),
        ("readiness", {"edit_page": False}),
        ("readiness", {"timeline_focused": False}),
        ("readiness", {"v1_only": False}),
        ("readiness", {"trim_roll_menu_enabled": False}),
        ("readiness", {"nudge_menu_enabled": False}),
        ("readiness", {"keyboard_preset": "Other"}),
        ("readiness", {"keyboard_focus_binding": "Command-5"}),
        ("readiness", {"keyboard_nudge_binding": ","}),
    ],
)
def test_preflight_denials_have_no_journal_or_gui_effect(
    admitted_owner: None, component: str, changes: dict[str, Any]
) -> None:
    intent, inventory, readiness = valid()
    components: dict[str, Any] = {
        "intent": intent,
        "inventory": inventory,
        "readiness": readiness,
    }
    components[component] = replace(components[component], **changes)
    journal, executor = FakeJournal(), FakeExecutor()
    with pytest.raises(gui.GuiRollRefused):
        gui.OneUseGuiRollActuator(journal, executor).attempt(
            components["intent"],
            components["inventory"],
            components["readiness"],
            now=NOW,
        )
    assert journal.calls == 0
    assert executor.calls == []


def test_missing_existing_native_owner_refuses_before_journal() -> None:
    intent, inventory, readiness = valid()
    journal, executor = FakeJournal(), FakeExecutor()
    with pytest.raises(gui.GuiRollRefused, match="native owner"):
        gui.OneUseGuiRollActuator(journal, executor).attempt(
            intent,
            inventory,
            readiness,
            now=NOW,
        )
    assert journal.calls == 0
    assert executor.calls == []


def test_expired_or_timezone_naive_intent_refuses(admitted_owner: None) -> None:
    intent, inventory, readiness = valid()
    for timestamp in (NOW - timedelta(seconds=1), NOW.replace(tzinfo=None)):
        journal, executor = FakeJournal(), FakeExecutor()
        with pytest.raises(gui.GuiRollRefused):
            gui.OneUseGuiRollActuator(journal, executor).attempt(
                replace(intent, expires_at=timestamp),
                inventory,
                readiness,
                now=NOW,
            )
        assert journal.calls == 0 and executor.calls == []


def test_journal_replay_across_actuator_instances_is_refused(
    admitted_owner: None,
) -> None:
    intent, inventory, readiness = valid()
    journal, executor = FakeJournal(), FakeExecutor()
    first = gui.OneUseGuiRollActuator(journal, executor)
    first.attempt(intent, inventory, readiness, now=NOW)
    with pytest.raises(gui.GuiRollRefused, match="already been dispatched"):
        first.attempt(intent, inventory, readiness, now=NOW)
    with pytest.raises(gui.GuiRollRefused, match="already spent"):
        gui.OneUseGuiRollActuator(journal, executor).attempt(
            intent,
            inventory,
            readiness,
            now=NOW,
        )
    assert journal.calls == 2 and executor.calls == [NAME]


def test_ambiguous_durable_journal_consumption_fails_without_gui(
    admitted_owner: None,
) -> None:
    intent, inventory, readiness = valid()
    journal, executor = FakeJournal(), FakeExecutor()
    journal.fail_ambiguously = True
    actuator = gui.OneUseGuiRollActuator(journal, executor)
    with pytest.raises(gui.GuiRollUnknown, match="journal unknown"):
        actuator.attempt(intent, inventory, readiness, now=NOW)
    with pytest.raises(gui.GuiRollRefused, match="already been dispatched"):
        actuator.attempt(intent, inventory, readiness, now=NOW)
    assert journal.calls == 1 and executor.calls == []


@pytest.mark.parametrize(
    "error",
    [
        OSError("one of 24 events failed"),
        subprocess.TimeoutExpired(cmd="osascript", timeout=90),
        gui.GuiRollUnknown("partial one-frame nudge"),
        RuntimeError("executor process crashed after frame 1"),
    ],
)
def test_partial_crash_timeout_unknown_is_spent_and_never_retried(
    admitted_owner: None,
    error: Exception,
) -> None:
    intent, inventory, readiness = valid()
    journal, executor = FakeJournal(), FakeExecutor(error)
    actuator = gui.OneUseGuiRollActuator(journal, executor)
    with pytest.raises(gui.GuiRollUnknown, match="no retry"):
        actuator.attempt(intent, inventory, readiness, now=NOW)
    with pytest.raises(gui.GuiRollRefused, match="already been dispatched"):
        actuator.attempt(intent, inventory, readiness, now=NOW)
    assert journal.calls == 1 and executor.calls == [NAME]


def test_fixed_production_executor_only_passes_pinned_script_and_argv(
    monkeypatch: pytest.MonkeyPatch,
    admitted_owner: None,
) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(args: list[str], **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(gui.GuiRollRefused, match="no consumed"):
        gui.SystemEventsRollExecutor().execute_once(NAME)
    assert not calls
    intent, inventory, readiness = valid()
    journal = FakeJournal()
    result = gui.OneUseGuiRollActuator(journal, gui.SystemEventsRollExecutor()).attempt(
        intent,
        inventory,
        readiness,
        now=NOW,
    )
    assert result.state == "unknown" and not result.native_verified
    assert journal.spent == {intent.stage_operation_id}
    assert len(calls) == 1
    argv, options = calls[0]
    assert argv == ["osascript", "-e", gui.ROLL_APPLESCRIPT, NAME]
    assert options["timeout"] == 90 and options["check"] is False
    with pytest.raises(gui.GuiRollRefused, match="no consumed"):
        gui.SystemEventsRollExecutor().execute_once("bad\nwindow")
    assert len(calls) == 1


def test_os_exit_failure_cannot_be_accepted_even_if_script_was_dispatched(
    monkeypatch: pytest.MonkeyPatch,
    admitted_owner: None,
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1),
    )
    intent, inventory, readiness = valid()
    with pytest.raises(gui.GuiRollUnknown, match="uncertain"):
        gui.OneUseGuiRollActuator(
            FakeJournal(), gui.SystemEventsRollExecutor()
        ).attempt(
            intent,
            inventory,
            readiness,
            now=NOW,
        )
    with pytest.raises(gui.GuiRollRefused, match="no consumed"):
        gui.SystemEventsRollExecutor().execute_once(NAME)
