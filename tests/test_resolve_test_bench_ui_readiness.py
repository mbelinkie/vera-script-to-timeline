"""#499: injected read-only Mac/SDK evidence, no UI or native effects."""

from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import resolve_gui_roll as gui
from vera_timeline_agent import resolve_test_bench_gui_stage as stage
from vera_timeline_agent import resolve_test_bench_ui_readiness as ui

NAME = "VERA Delivery 123e4567-e89b-12d3-a456-426614174000 012345abcdef"
TARGET = gui.NativeTarget("sdk-project-id", NAME, "sdk-timeline-id", NAME, NAME)
UIDS = tuple(f"native-uid-{n}" for n in range(11))


def sdk_inputs() -> tuple[gui.GuiRollIntent, gui.PristineSdkInventory]:
    inventory = gui.PristineSdkInventory(
        target=TARGET,
        capture_sha256="a" * 64,
        item_uids=UIDS,
        left_item_uid=UIDS[0],
        right_item_uid=UIDS[1],
        left_track_id="V1-id",
        right_track_id="V1-id",
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
    intent = gui.GuiRollIntent(
        actuator_class="gui",
        operation="M4.edited",
        stage_operation_id="original-edited-1234",
        target=TARGET,
        pristine_capture_sha256=inventory.capture_sha256,
        item_uids=UIDS,
        left_item_uid=UIDS[0],
        right_item_uid=UIDS[1],
        script_sha256=gui.ROLL_SCRIPT_SHA256,
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    return intent, inventory


def os_snapshot() -> dict[str, object]:
    """Independently mockable macOS *raw* fact set, not caller readiness."""
    return {
        "runningResolveCount": 1,
        "processPid": 1234,
        "processName": "Resolve",
        "bundleId": gui.RESOLVE_BUNDLE_ID,
        "bundlePath": "/Applications/DaVinci Resolve/DaVinci Resolve.app",
        "bundleShortVersion": "21.1.1",
        "bundleBuild": "21.1.10010",
        "frontmostPid": 1234,
        "frontmostBundleId": gui.RESOLVE_BUNDLE_ID,
        "frontmostProcess": "Resolve",
        "accessibility": True,
        "automation": True,
        "windowCount": 1,
        "windowName": NAME,
        "windowFrontmost": True,
        "modalPresent": False,
        "editPage": True,
        "timelineFocused": True,
        "v1Only": True,
        "trimRollMenu": True,
        "nudgeMenu": True,
        "keyboardPreset": gui.KEYBOARD_PRESET,
        "keyboardFocus": "Command-4",
        "keyboardNudge": ".",
    }


def test_mock_trusted_mac_positive_exact_sdk_and_fixed_hash() -> None:
    intent, inventory = sdk_inputs()
    readiness = ui._readiness_from_os(os_snapshot(), intent.target)
    gui._validate(intent, inventory, readiness, datetime.now(UTC))
    assert readiness == gui.TrustedUiReadiness(
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
        keyboard_preset="DaVinci Resolve",
        keyboard_focus_binding="Command-4",
        keyboard_nudge_binding=".",
    )


@pytest.mark.parametrize(
    ("name", "bad"),
    [
        ("runningResolveCount", 2),
        ("processPid", 0),
        ("processName", "Another Editor"),
        ("bundleId", "com.apple.finder"),
        ("bundlePath", "/Applications/Other.app"),
        ("bundlePath", "/tmp/DaVinci Resolve.app"),
        ("bundleShortVersion", "21.1.2"),
        ("bundleBuild", "21.1.10011"),
        ("frontmostPid", 1235),
        ("frontmostBundleId", "com.apple.finder"),
        ("frontmostProcess", "Finder"),
        ("accessibility", False),
        ("automation", False),
        ("windowCount", 0),
        ("windowCount", 2),
        ("windowName", "Producer Personal"),
        ("windowFrontmost", False),
        ("modalPresent", True),
        ("editPage", False),
        ("timelineFocused", False),
        ("v1Only", False),
        ("trimRollMenu", False),
        ("nudgeMenu", False),
        ("keyboardPreset", "Adobe Premiere Pro"),
        ("keyboardFocus", "Command-5"),
        ("keyboardNudge", ","),
        ("keyboardPreset", None),
        ("processPid", True),
        ("accessibility", 1),
        ("v1Only", "true"),
    ],
)
def test_refuses_wrong_process_window_version_tcc_focus_track_and_keymap(
    name: str, bad: object
) -> None:
    intent, inventory = sdk_inputs()
    facts = os_snapshot()
    facts[name] = bad
    with pytest.raises(gui.GuiRollRefused):
        readiness = ui._readiness_from_os(facts, intent.target)
        gui._validate(intent, inventory, readiness, datetime.now(UTC))


@pytest.mark.parametrize("name", list(os_snapshot()))
def test_missing_observation_is_never_inferred(name: str) -> None:
    snapshot = os_snapshot()
    del snapshot[name]
    with pytest.raises(gui.GuiRollRefused, match="incomplete OS UI evidence"):
        ui._readiness_from_os(snapshot, TARGET)


def test_unknown_and_injected_keys_fail() -> None:
    facts = os_snapshot()
    facts["fakeGreenStatus"] = True
    with pytest.raises(gui.GuiRollRefused, match="unrecognized"):
        ui._readiness_from_os(facts, TARGET)
    facts.pop("fakeGreenStatus")
    facts["keyboardPreset"] = None
    with pytest.raises(gui.GuiRollRefused):
        ui._readiness_from_os(facts, TARGET)


@pytest.mark.parametrize(
    "bad_sdk",
    [
        {"pristine_verified": False},
        {"target": replace(TARGET, timeline_uid="other")},
        {"playhead_frame": 326},
        {"left_track_index": 2},
        {"right_track_kind": "audio"},
        {"item_uids": (*UIDS[:-1], UIDS[0])},
    ],
)
def test_authenticated_sdk_facts_cannot_be_replaced_by_os_claims(
    bad_sdk: dict[str, Any],
) -> None:
    intent, inventory = sdk_inputs()
    with pytest.raises(gui.GuiRollRefused):
        gui._validate(
            intent,
            replace(inventory, **bad_sdk),
            ui._readiness_from_os(os_snapshot(), TARGET),
            datetime.now(UTC),
        )


def test_production_entrypoint_reauthenticates_under_owner_and_uses_os_not_caller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    intent, inventory = sdk_inputs()
    monkeypatch.setattr(gui, "_require_owner_lock", lambda: calls.append("owner"))

    def authenticated(_store: object, _job: str, _sdk: object) -> tuple[Any, Any]:
        calls.append("signed SDK")
        return intent, inventory

    def observed(_self: object) -> dict[str, object]:
        calls.append("read OS")
        return os_snapshot()

    monkeypatch.setattr(stage, "prepare_owned_f1_inputs", authenticated)
    monkeypatch.setattr(ui.MacReadOnlyObserver, "observe", observed)
    outcome = ui.prepare_owned_ui_readiness(object(), "original-M4-job", object())
    assert outcome[0] is intent and outcome[1] is inventory
    assert outcome[2].v1_only is True
    assert calls == ["owner", "signed SDK", "read OS"]
    ui._consume_attested_ui_readiness(*outcome)
    assert calls[-1] == "owner"
    with pytest.raises(gui.GuiRollRefused, match="no fresh authenticated"):
        ui._consume_attested_ui_readiness(*outcome)


def test_real_executor_cannot_consume_forged_green_ui_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    intent, inventory = sdk_inputs()
    readiness = ui._readiness_from_os(os_snapshot(), TARGET)
    monkeypatch.setattr(gui, "_require_owner_lock", lambda: None)
    with pytest.raises(gui.GuiRollRefused, match="no fresh authenticated"):
        stage.attempt_once(
            object(),  # type: ignore[arg-type]
            "original-M4-job",
            intent,
            inventory,
            readiness,
            gui.SystemEventsRollExecutor(),
        )


def test_subclass_of_real_executor_cannot_skip_attestation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DerivedExecutor(gui.SystemEventsRollExecutor):
        pass

    intent, inventory = sdk_inputs()
    monkeypatch.setattr(gui, "_require_owner_lock", lambda: None)
    with pytest.raises(gui.GuiRollRefused, match="no fresh authenticated"):
        stage.attempt_once(
            object(),  # type: ignore[arg-type]
            "original-M4-job",
            intent,
            inventory,
            ui._readiness_from_os(os_snapshot(), TARGET),
            DerivedExecutor(),
        )


def test_attestation_is_bound_to_exact_object_identity_and_short_age(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    intent, inventory = sdk_inputs()
    readiness = ui._readiness_from_os(os_snapshot(), TARGET)
    monkeypatch.setattr(gui, "_require_owner_lock", lambda: None)
    clock = 100.0
    ui._ATTESTED.set((intent, inventory, readiness, clock))
    monkeypatch.setattr(ui, "monotonic", lambda: clock + 6)
    with pytest.raises(gui.GuiRollRefused, match="no fresh authenticated"):
        ui._consume_attested_ui_readiness(intent, inventory, readiness)
    monkeypatch.setattr(ui, "monotonic", lambda: clock + 1)
    ui._ATTESTED.set((intent, inventory, readiness, clock))
    with pytest.raises(gui.GuiRollRefused, match="no fresh authenticated"):
        ui._consume_attested_ui_readiness(intent, inventory, replace(readiness))
    with pytest.raises(gui.GuiRollRefused, match="no fresh authenticated"):
        ui._consume_attested_ui_readiness(intent, inventory, readiness)


def test_production_entrypoint_fails_before_observing_if_owner_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny() -> None:
        raise gui.GuiRollRefused("native owner absent")

    monkeypatch.setattr(gui, "_require_owner_lock", deny)
    monkeypatch.setattr(
        ui.MacReadOnlyObserver,
        "observe",
        lambda _self: pytest.fail("OS must not run without owner"),
    )
    with pytest.raises(gui.GuiRollRefused, match="owner absent"):
        ui.prepare_owned_ui_readiness(object(), "original-M4-job", object())


def test_non_mac_does_not_spawn_or_edit_os(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("no subprocess on Linux"),
    )
    with pytest.raises(gui.GuiRollRefused, match="requires macOS"):
        ui.MacReadOnlyObserver().observe()


@pytest.mark.parametrize("status,output", [(1, "{}"), (0, "[]"), (0, "bad")])
def test_malformed_or_failed_system_events_never_returns_green(
    monkeypatch: pytest.MonkeyPatch, status: int, output: str
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=status, stdout=output),
    )
    with pytest.raises(gui.GuiRollRefused):
        ui.MacReadOnlyObserver().observe()


def test_fixed_jxa_never_activates_clicks_or_changes_keyboard_or_tcc() -> None:
    source = ui._OS_READ_ONLY_JXA
    for forbidden in (
        ".activate(",
        ".click(",
        ".keystroke(",
        "AXPress",
        "AXSet",
        "SetCurrentTimecode",
        "requestAccess",
        "tccutil",
        "save(",
    ):
        assert forbidden not in source
    assert "result.keyboardPreset: null" not in source  # actual JSON key
    assert "keyboardPreset: null" in source
    assert "AXIsProcessTrusted" in source
    assert "AEDeterminePermissionToAutomateTarget" in source
    assert "0x2a2a2a2a, 0x2a2a2a2a, false" in source
    assert "['V1', 'A1', 'A2', 'A3', 'A4', 'A5']" in source
    assert "AXMenuItemCmdChar" in source
    assert "AXMenuItemCmdModifiers" in source
    assert "'Active Panel Selection', 'Timeline'" in source
    assert "'Nudge', 'One Frame Right'" in source
    assert "'4', 0, 'Command-4'" in source
    assert "'.', 8, '.'" in source
    assert "attr(item, 'AXMenuItemCmdChar') !== expectedChar" in source
    assert "attr(item, 'AXMenuItemCmdModifiers') !== expectedModifiers" in source


def _write_keyboard_preferences(tmp_path: Any) -> tuple[Any, Any]:
    config = tmp_path / "config.user.xml"
    preset = tmp_path / "keyboard.preset.xml"
    config.write_text(
        '<?xml version="1.0"?><SM_UserPrefs>'
        "<KeyboardMappings>0</KeyboardMappings>"
        "<CustomKeyboardPreset/></SM_UserPrefs>"
    )
    preset.write_text(
        '<?xml version="1.0"?><SmKeyboardPresetList>'
        "<FieldsBlob/><PresetListBA/></SmKeyboardPresetList>"
    )
    return config, preset


def test_real_read_only_default_keyboard_preset_files(tmp_path: Any) -> None:
    config, preset = _write_keyboard_preferences(tmp_path)
    assert ui._trusted_keyboard_preset(config, preset) == gui.KEYBOARD_PRESET


@pytest.mark.parametrize(
    ("config_change", "preset_change"),
    [
        ("<KeyboardMappings>1</KeyboardMappings>", None),
        (
            "<KeyboardMappings>0</KeyboardMappings><KeyboardMappings>0</KeyboardMappings>",
            None,
        ),
        ("<CustomKeyboardPreset>Custom</CustomKeyboardPreset>", None),
        ("<CustomKeyboardPreset><Key/></CustomKeyboardPreset>", None),
        ('<CustomKeyboardPreset name="forged"/>', None),
        ("<!DOCTYPE x [ <!ENTITY x 'DaVinci Resolve'> ]>", None),
        (None, "<PresetListBA>overrides</PresetListBA>"),
        (None, "<PresetListBA><Shortcut/></PresetListBA>"),
    ],
)
def test_refuses_nondefault_or_ambiguous_active_mapping(
    tmp_path: Any, config_change: str | None, preset_change: str | None
) -> None:
    config, preset = _write_keyboard_preferences(tmp_path)
    if config_change is not None:
        original = config.read_text()
        if config_change.startswith("<!DOCTYPE"):
            config.write_text(config_change + original)
        elif config_change.startswith("<KeyboardMappings>"):
            config.write_text(
                original.replace(
                    "<KeyboardMappings>0</KeyboardMappings>", config_change
                )
            )
        else:
            config.write_text(
                original.replace("<CustomKeyboardPreset/>", config_change)
            )
    if preset_change is not None:
        preset.write_text(preset.read_text().replace("<PresetListBA/>", preset_change))
    with pytest.raises(gui.GuiRollRefused, match="keyboard"):
        ui._trusted_keyboard_preset(config, preset)


def test_missing_symlinked_and_oversized_preferences_fail_closed(tmp_path: Any) -> None:
    config, preset = _write_keyboard_preferences(tmp_path)
    other = tmp_path / "other.xml"
    other.write_bytes(config.read_bytes())
    config.unlink()
    config.symlink_to(other)
    with pytest.raises(gui.GuiRollRefused, match="keyboard"):
        ui._trusted_keyboard_preset(config, preset)
    config.unlink()
    config.write_bytes(other.read_bytes())
    preset.write_bytes(b"x" * 131073)
    with pytest.raises(gui.GuiRollRefused, match="keyboard"):
        ui._trusted_keyboard_preset(config, preset)


def test_observer_rejects_changed_live_keyboard_preferences(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    config, preset = _write_keyboard_preferences(tmp_path)
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(ui, "_KEYBOARD_CONFIG_PATH", config)
    monkeypatch.setattr(ui, "_KEYBOARD_PRESETS_PATH", preset)

    def replaced(_args: object, **_kwargs: object) -> Any:
        snapshot = os_snapshot()
        snapshot["keyboardPreset"] = None
        # Still a valid default preset. Only the *two-read change detection*
        # can catch this mid-probe change, not the parser's preset validation.
        config.write_text(config.read_text() + "\n")
        return SimpleNamespace(returncode=0, stdout=json.dumps(snapshot))

    monkeypatch.setattr(subprocess, "run", replaced)
    with pytest.raises(gui.GuiRollRefused, match="keyboard"):
        ui.MacReadOnlyObserver().observe()


def test_observer_returns_raw_not_authenticated_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    config, preset = _write_keyboard_preferences(tmp_path)
    monkeypatch.setattr(ui, "_KEYBOARD_CONFIG_PATH", config)
    monkeypatch.setattr(ui, "_KEYBOARD_PRESETS_PATH", preset)

    def run(args: list[str], **kwargs: object) -> Any:
        assert args[:5] == [
            "/usr/bin/osascript",
            "-l",
            "JavaScript",
            "-e",
            ui._OS_READ_ONLY_JXA,
        ]
        assert kwargs["timeout"] == 12
        snapshot = os_snapshot()
        snapshot["keyboardPreset"] = None
        return SimpleNamespace(returncode=0, stdout=json.dumps(snapshot))

    monkeypatch.setattr(subprocess, "run", run)
    assert ui.MacReadOnlyObserver().observe() == os_snapshot()


def test_observer_does_not_trust_forged_preset_claim(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    config, preset = _write_keyboard_preferences(tmp_path)
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(ui, "_KEYBOARD_CONFIG_PATH", config)
    monkeypatch.setattr(ui, "_KEYBOARD_PRESETS_PATH", preset)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps(os_snapshot())
        ),
    )
    with pytest.raises(gui.GuiRollRefused, match="keyboard preset must come"):
        ui.MacReadOnlyObserver().observe()
