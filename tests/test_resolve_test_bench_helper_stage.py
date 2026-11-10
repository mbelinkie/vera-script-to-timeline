"""Phase 24/31: simulated signed-helper seams, no OS, GUI or native edit."""

from __future__ import annotations

import ctypes
import hashlib
import json
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from _actor_pin import actor_pin
from test_resolve_test_bench_ui_readiness import sdk_inputs
from vera_timeline_agent import resolve_gui_helper_protocol as protocol
from vera_timeline_agent import resolve_gui_roll as gui
from vera_timeline_agent import resolve_test_bench_carrier as carrier
from vera_timeline_agent import resolve_test_bench_gui_stage as stage
from vera_timeline_agent import resolve_test_bench_helper_stage as helper_stage
from vera_timeline_agent import resolve_test_bench_helper_transport as transport
from vera_timeline_agent import resolve_test_bench_m4_runner as runner
from vera_timeline_agent import resolve_test_bench_output as output
from vera_timeline_agent import resolve_test_bench_ui_readiness as ui
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import resolve_test_queue_m4 as m4


def _desktop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> transport.SignedHelperDesktop:
    spool = tmp_path / "private-spool"
    spool.mkdir(mode=0o700)
    pin = cast(dict[str, Any], actor_pin())
    real_validate = protocol.validate_actor_pin
    monkeypatch.setattr(
        protocol, "validate_actor_pin", lambda value, **_kw: real_validate(value)
    )
    monkeypatch.setattr(
        protocol,
        "observe_helper_pid",
        lambda pid, executable: (
            pid == 4321 and executable == pin["binary"]["executablePath"]
        ),
    )
    carrier._once(
        spool / "self-status.json",
        queue.canonical(
            {
                "schema": transport.SELF_SCHEMA,
                "helperPid": 4321,
                "bundleIdentifier": protocol.BUNDLE_ID,
                "executablePath": pin["binary"]["executablePath"],
                "accessibilityTrusted": True,
                "observedAt": time.time(),
            }
        ),
    )
    return transport.SignedHelperDesktop(pin, spool)


def _focus_reply(
    desktop: transport.SignedHelperDesktop,
    destination: Path,
    *,
    change: dict[str, object] | None = None,
) -> bytes:
    name = destination.name.removesuffix(".focus-reply.json")
    request_raw = carrier._read(desktop.spool / (name + ".focus-request.json"))
    request = json.loads(request_raw)
    observation: dict[str, object] = {
        "resolvePid": request["resolvePid"],
        "bundleIdentifier": gui.RESOLVE_BUNDLE_ID,
        "windowName": request["windowName"],
        "mainWindow": True,
        "foreground": True,
        "noModalOrSheet": True,
        "rollEnabled": True,
    }
    if change:
        observation.update(change)
    return queue.canonical(
        {
            "schema": transport.FOCUS_REPLY_SCHEMA,
            "requestId": name,
            "requestSha256": hashlib.sha256(request_raw).hexdigest(),
            "helperPid": 4321,
            "status": "ready",
            "detail": "exact target observed",
            "observation": observation,
        }
    )


@pytest.mark.parametrize(
    "change",
    [
        {"accessibilityTrusted": False},
        {"helperPid": 9999},
        {"executablePath": "/tmp/unauthorized"},
        {"bundleIdentifier": "untrusted"},
        {"observedAt": time.time() - 600},
        {"observedAt": time.time() + 600},
        {"helperPid": True},
    ],
)
def test_actual_helper_accessibility_process_self_status_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: dict[str, object]
) -> None:
    desktop = _desktop(tmp_path, monkeypatch)
    path = desktop.spool / "self-status.json"
    value = json.loads(path.read_bytes())
    value.update(change)
    path.write_bytes(queue.canonical(value))
    with pytest.raises(gui.GuiRollRefused, match="Accessibility not ready"):
        desktop.readiness()


def test_actual_helper_status_is_unspoofed_and_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    desktop = _desktop(tmp_path, monkeypatch)
    assert desktop.readiness() == 4321
    monkeypatch.setattr(protocol, "observe_helper_pid", lambda _pid, _executable: False)
    with pytest.raises(gui.GuiRollRefused, match="Accessibility not ready"):
        desktop.readiness()


@pytest.mark.parametrize(
    "change",
    [
        {},
        {"mainWindow": False},
        {"foreground": False},
        {"rollEnabled": False},
        {"noModalOrSheet": False},
        {"resolvePid": 9999},
        {"windowName": "another disposable project"},
        {"bundleIdentifier": "wrong app"},
        {"mainWindow": "true"},
    ],
)
def test_read_only_helper_menu_and_focus_refuse_any_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: dict[str, object],
) -> None:
    desktop = _desktop(tmp_path, monkeypatch)
    pid = 1234
    name = "VERA Delivery 123e4567-e89b-12d3-a456-426614174000 012345abcdef"
    monkeypatch.setattr(
        desktop,
        "_wait",
        lambda destination, _seconds: _focus_reply(desktop, destination, change=change),
    )
    # Production helper client may not spawn osascript even for a read-only menu.
    monkeypatch.setattr(
        subprocess, "run", lambda *_args, **_kwargs: pytest.fail("legacy fallback")
    )
    if change:
        with pytest.raises(gui.GuiRollRefused, match="PID, foreground"):
            desktop.focus("job-original-123", "m4-original-edited-123", pid, name)
    else:
        assert (
            desktop.focus("job-original-123", "m4-original-edited-123", pid, name)[
                "rollEnabled"
            ]
            is True
        )
    # The helper focus request ID is consumed even after a refusal.
    with pytest.raises(FileExistsError):
        desktop.focus("job-original-123", "m4-original-edited-123", pid, name)


def test_helper_reply_must_match_original_request_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    desktop = _desktop(tmp_path, monkeypatch)
    monkeypatch.setattr(
        desktop,
        "_wait",
        lambda destination, _seconds: _focus_reply(desktop, destination).replace(
            b'"status":"ready"', b'"status":"refused"'
        ),
    )
    with pytest.raises(gui.GuiRollRefused, match="tampered"):
        desktop.focus(
            "job-original-123", "m4-original-edited-123", 1234, "VERA Delivery"
        )


def test_exact_helper_actor_and_sdk_bracket_without_automation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    intent, inventory = sdk_inputs()
    calls: list[str] = []
    monkeypatch.setattr(gui, "_require_owner_lock", lambda: None)

    def inputs(*_args: Any) -> tuple[gui.GuiRollIntent, gui.PristineSdkInventory]:
        calls.append("sdk")
        return intent, inventory

    monkeypatch.setattr(stage, "prepare_owned_f1_inputs", inputs)

    class Desktop:
        actor_pin = intent.actor_pin

        def resolve_pid(self) -> int:
            calls.append("process-census")
            return 1234

        def focus(self, *_args: Any, **kwargs: Any) -> dict[str, Any]:
            calls.append("helper:" + kwargs.get("operation", "focus"))
            return {
                "resolvePid": 1234,
                "bundleIdentifier": gui.RESOLVE_BUNDLE_ID,
                "windowName": intent.target.expected_window_name,
                "mainWindow": True,
                "foreground": True,
                "noModalOrSheet": True,
                "rollEnabled": True,
            }

    proof = helper_stage.prepare_owned_helper_readiness(
        object(),  # type: ignore[arg-type]
        "new-case-m4",
        object(),
        Desktop(),  # type: ignore[arg-type]
    )
    assert proof[:2] == (intent, inventory)
    assert proof[2].helper_proven is True
    assert proof[2].automation_trusted is False
    ui._consume_attested_ui_readiness(*proof)
    assert calls == ["sdk", "process-census", "helper:focus", "helper:inspect", "sdk"]


@pytest.mark.parametrize("condition", ["actor", "sdk", "foreground"])
def test_failed_helper_admission_never_creates_dispatch_attestation(
    monkeypatch: pytest.MonkeyPatch,
    condition: str,
) -> None:
    intent, inventory = sdk_inputs()
    monkeypatch.setattr(gui, "_require_owner_lock", lambda: None)
    events: list[str] = []

    def inputs(*_args: Any) -> tuple[gui.GuiRollIntent, gui.PristineSdkInventory]:
        events.append("sdk")
        if condition == "sdk" and events.count("sdk") == 2:
            return replace(intent, left_item_uid="tampered-uid"), inventory
        return intent, inventory

    monkeypatch.setattr(stage, "prepare_owned_f1_inputs", inputs)

    class Desktop:
        actor_pin = (
            {**intent.actor_pin, "sourceManifestSha256": "0" * 64}
            if condition == "actor"
            else intent.actor_pin
        )

        def resolve_pid(self) -> int:
            events.append("census")
            return 1234

        def focus(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            events.append("focus")
            return {
                "resolvePid": 1234,
                "bundleIdentifier": gui.RESOLVE_BUNDLE_ID,
                "windowName": intent.target.expected_window_name,
                "mainWindow": condition != "foreground",
                "foreground": condition != "foreground",
                "noModalOrSheet": True,
                "rollEnabled": True,
            }

    with pytest.raises(gui.GuiRollRefused):
        helper_stage.prepare_owned_helper_readiness(
            object(),  # type: ignore[arg-type]
            "new-case-m4",
            object(),
            Desktop(),  # type: ignore[arg-type]
        )
    assert ui._ATTESTED.get() is None


@pytest.mark.parametrize(
    "condition", ["valid", "authority-drift", "journal-drift", "sdk-drift"]
)
def test_one_spent_helper_roll_dispatch_pins_are_immutable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    condition: str,
) -> None:
    intent, _inventory = sdk_inputs()
    job_id = "job-original-12345"
    case_root = tmp_path / "new-case"
    case_root.mkdir()
    job_root = tmp_path / job_id
    (job_root / "f1-gui-edit").mkdir(parents=True)
    authority = {
        "actorPin": intent.actor_pin,
        "sourceGraphSha256": "c" * 64,
        "initialTarget": stage._target_dict(intent.target),
    }
    authority_sha = hashlib.sha256(queue.canonical(authority)).hexdigest()
    carrier._once(
        case_root / "complete-loop-intent.json",
        queue.canonical(
            {
                "authority": {
                    "sha256": authority_sha
                    if condition != "authority-drift"
                    else "d" * 64
                },
                "sourceGraphSha256": authority["sourceGraphSha256"],
            }
        ),
    )
    carrier._once(
        job_root / "f1-gui-edit" / "gui-intent.json",
        queue.canonical(
            {
                "jobId": job_id,
                "operationId": intent.stage_operation_id
                if condition != "journal-drift"
                else "wrong",
                "actorPin": intent.actor_pin,
            }
        ),
    )
    monkeypatch.setattr(gui, "_require_owner_lock", lambda: None)
    monkeypatch.setattr(m4, "_jobdir", lambda *_: job_root)
    real_request = protocol.validate_request
    monkeypatch.setattr(
        protocol,
        "validate_request",
        lambda raw, **_kw: real_request(raw),
    )
    dispatches: list[dict[str, Any]] = []
    desktop = SimpleNamespace(
        actor_pin=intent.actor_pin,
        roll=lambda request: dispatches.append(request),
    )
    executor = helper_stage.HelperRollExecutor(
        object(),  # type: ignore[arg-type]
        job_id,
        intent,
        desktop,  # type: ignore[arg-type]
        case_root=case_root,
        authority=authority,
    )
    consumed = gui._CONSUMED_DISPATCH.set(True)

    def sdk_recheck() -> None:
        if condition == "sdk-drift":
            raise gui.GuiRollRefused("SDK drifted")

    verified = gui._VERIFIED_HOST_DISPATCH.set(
        (intent.target.expected_window_name, 1234, sdk_recheck)
    )
    try:
        if condition == "valid":
            executor.execute_once(intent.target.expected_window_name, 1234)
            assert len(dispatches) == 1
            request = dispatches[0]
            assert (
                request["oneUseIntentSha256"]
                == hashlib.sha256(
                    carrier._read(job_root / "f1-gui-edit" / "gui-intent.json")
                ).hexdigest()
            )
            assert request["authoritySha256"] == authority_sha
            assert request["sourceGraphSha256"] == "c" * 64
        else:
            with pytest.raises(gui.GuiRollRefused):
                executor.execute_once(intent.target.expected_window_name, 1234)
            assert not dispatches
    finally:
        gui._CONSUMED_DISPATCH.reset(consumed)
        gui._VERIFIED_HOST_DISPATCH.reset(verified)


@pytest.mark.parametrize("pids", [[1234], [], [1234, 2345]])
def test_mac_runner_uses_exact_native_process_census_not_system_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pids: list[int],
) -> None:
    desktop = _desktop(tmp_path, monkeypatch)

    class Proc:
        def proc_listallpids(self, pointer: Any, _size: int) -> int:
            if pointer is None:
                return 4
            for i, pid in enumerate([1234, 2345, 0, 7777]):
                pointer[i] = pid
            return 4

    monkeypatch.setattr(ctypes, "CDLL", lambda *_: Proc())
    monkeypatch.setattr(
        protocol,
        "observe_helper_pid",
        lambda pid, executable: (
            pid in pids and executable == transport.RESOLVE_EXECUTABLE
        ),
    )
    monkeypatch.setattr(
        subprocess, "run", lambda *_args, **_kwargs: pytest.fail("legacy process probe")
    )
    if len(pids) == 1:
        assert desktop.resolve_pid() == 1234
    else:
        with pytest.raises(gui.GuiRollRefused, match="exactly one installed Resolve"):
            desktop.resolve_pid()


@pytest.mark.parametrize(
    "mode",
    [
        "edited",
        "unchanged",
        "wrong-geometry",
        "missing-uid",
        "duplicate-uid",
        "wrong-target",
        "wrong-track",
        "moved-uid",
    ],
)
def test_read_only_sdk_settle_is_bounded_and_never_infers_edit(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    items: list[dict[str, Any]] = []
    tracks: list[dict[str, Any]] = []
    for i in range(1, 6):
        tracks.append(
            {
                "kind": "video",
                "index": i,
                "trackId": f"video-{i}",
                "name": f"V{i}",
                "enabled": True,
                "locked": i > 1,
            }
        )
    tracks.append(
        {
            "kind": "audio",
            "index": 1,
            "trackId": "audio-1",
            "name": "A1",
            "enabled": True,
            "locked": True,
        }
    )
    for i in range(11):
        index = 1 if i < 2 else (2 + (i - 2) // 2 if i < 10 else 1)
        kind = "video" if i < 10 else "audio"
        row: dict[str, Any] = {
            "itemUid": f"uid-{i}",
            "kind": kind,
            "trackId": f"{kind}-{index}",
            "recordStart": 0 if i == 0 else 327 if i == 1 else 600 + i * 20,
            "recordDuration": 327 if i == 0 else 151 if i == 1 else 20,
        }
        items.append(row)
    graph = {"items": items, "tracks": tracks}
    record = {
        "nativeGeometry": graph,
        "target": {
            "projectUid": "original-project",
            "timelineUid": "original-timeline",
        },
    }
    monkeypatch.setattr(gui, "_require_owner_lock", lambda: None)
    monkeypatch.setattr(
        m4,
        "_stage_receipt",
        lambda *_: {"capture": {"path": "/fake", "sha256": "a" * 64}},
    )
    from vera_timeline_agent import qualification_output_native_v2 as native

    monkeypatch.setattr(native, "verify_native_result", lambda *_: record)

    class Item:
        def __init__(self, row: dict[str, Any]):
            self.row = row

        def GetUniqueId(self) -> str:
            return str(self.row["itemUid"])

        def GetStart(self, _round: bool) -> int:
            if (
                mode
                in {
                    "edited",
                    "wrong-geometry",
                    "missing-uid",
                    "duplicate-uid",
                    "wrong-target",
                    "wrong-track",
                    "moved-uid",
                }
                and self.row["itemUid"] == "uid-1"
            ):
                return 400 if mode == "wrong-geometry" else 351
            return int(self.row["recordStart"])

        def GetDuration(self, _round: bool) -> int:
            if mode != "unchanged" and self.row["itemUid"] == "uid-0":
                return 351
            if mode != "unchanged" and self.row["itemUid"] == "uid-1":
                return 127
            return int(self.row["recordDuration"])

    class Timeline:
        def GetUniqueId(self) -> str:
            return "original-timeline"

        def GetTrackCount(self, kind: str) -> int:
            return 5 if kind == "video" else 1

        def GetTrackName(self, kind: str, index: int) -> str:
            return f"{kind[0].upper()}{index}"

        def GetIsTrackEnabled(self, _kind: str, _index: int) -> bool:
            return True

        def GetIsTrackLocked(self, kind: str, index: int) -> bool:
            return (kind, index) != ("video", 1) if mode != "wrong-track" else False

        def GetItemListInTrack(self, kind: str, index: int) -> list[Item]:
            matched = [row for row in items if row["trackId"] == f"{kind}-{index}"]
            if mode == "missing-uid" and kind == "video" and index == 1:
                matched = matched[:1]
            if mode == "duplicate-uid" and kind == "video" and index == 1:
                matched = matched + matched[:1]
            if mode == "moved-uid" and kind == "video" and index == 1:
                matched = [row for row in matched if row["itemUid"] != "uid-1"]
            if mode == "moved-uid" and kind == "video" and index == 2:
                matched = [*matched, items[1]]
            return [Item(row) for row in matched]

    timeline = Timeline()
    project = SimpleNamespace(
        GetUniqueId=lambda: (
            "wrong-project" if mode == "wrong-target" else "original-project"
        ),
        GetCurrentTimeline=lambda: timeline,
    )
    resolve = SimpleNamespace(
        GetCurrentPage=lambda: "edit",
        GetProjectManager=lambda: SimpleNamespace(GetCurrentProject=lambda: project),
    )
    if mode == "edited":
        helper_stage.observe_settled_edited_geometry(
            object(),  # type: ignore[arg-type]
            "job-test",
            resolve,
        )
    else:
        with pytest.raises((gui.GuiRollRefused, gui.GuiRollUnknown)):
            helper_stage.observe_settled_edited_geometry(
                object(),  # type: ignore[arg-type]
                "job-test",
                resolve,
                max_seconds=0.015,
            )


@pytest.mark.parametrize(
    "change",
    ["tamper-record", "alias-path", "alias-parent", "hardlink-path", "reverify-drift"],
)
def test_prepared_edit_session_pin_reauthenticated_without_gui_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from vera_timeline_agent import resolve_test_bench_edited_stage as edited

    job = "job-original-12345"
    operation = "m4-original-edited-1234"
    ref: dict[str, str] = {"path": str(tmp_path / "session.json"), "sha256": "a" * 64}
    Path(ref["path"]).write_text("synthetic-only")
    if change == "alias-path":
        (tmp_path / "alias-session.json").symlink_to(ref["path"])
        ref["path"] = str(tmp_path / "alias-session.json")
    elif change == "alias-parent":
        real_parent = tmp_path / "session-parent"
        real_parent.mkdir()
        (real_parent / "session.json").write_text("synthetic-only")
        (tmp_path / "alias-parent").symlink_to(real_parent, target_is_directory=True)
        ref["path"] = str(tmp_path / "alias-parent" / "session.json")
    elif change == "hardlink-path":
        hardlink = tmp_path / "hardlink-session.json"
        hardlink.hardlink_to(Path(ref["path"]))
        ref["path"] = str(hardlink)
    pristine = {
        "capture": {"sha256": "b" * 64},
        "session": {"path": str(tmp_path / "pristine.json"), "sha256": "c" * 64},
    }
    pin = actor_pin()
    admission = {
        "schema": "vera.test-bench-edited-pre-gui-admission/v1",
        "jobId": job,
        "operationId": operation,
        "session": ref,
        "actorPin": pin,
        "pristineCaptureSha256": "b" * 64,
    }
    if change == "tamper-record":
        admission["pristineCaptureSha256"] = "d" * 64
    carrier._once(
        tmp_path / "edited-session-admission.json", queue.canonical(admission)
    )
    config = {"root": str(tmp_path)}
    plan = {"initialTarget": {"projectUid": "initial"}}
    monkeypatch.setattr(runner, "validate_config", lambda *_: config)
    monkeypatch.setattr(m4, "_load_plan", lambda *_: plan)
    monkeypatch.setattr(m4, "_stage_receipt", lambda *_: pristine)
    monkeypatch.setattr(edited, "_deadline", lambda *_: (time.time() + 100, operation))
    monkeypatch.setattr(stage, "helper_actor_pin_from_authority", lambda *_: pin)
    effects: list[str] = []

    def session_load(path: Path, _digest: str) -> SimpleNamespace:
        effects.append("admission-loader")
        if change == "reverify-drift":
            raise ValueError("edited admission changed after preparation")
        return SimpleNamespace(context={"target": plan["initialTarget"]})

    monkeypatch.setattr(output, "_session", session_load)
    monkeypatch.setattr(
        edited, "_same_source_distinct_edited_admission", lambda *_: True
    )
    with pytest.raises(
        (ValueError, queue.QueueError), match=r"pin|aliased|admission changed"
    ):
        edited.verify_prepared_identity(object(), job, config, ref)  # type: ignore[arg-type]
    if change in {"tamper-record", "alias-path", "alias-parent", "hardlink-path"}:
        assert effects == []
