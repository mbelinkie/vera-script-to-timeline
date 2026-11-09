"""#500 unit-simulated diagnostics; these are NOT actual-Mac/Resolve evidence."""

from __future__ import annotations

import json
import platform
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import resolve_readiness_diagnostic as diag


def synthetic() -> dict[str, Any]:
    return {
        "schema": 1,
        "source": "native-swift-ax",
        "platform": "macOS",
        "bundleId": diag.BUNDLE_ID,
        "applications": [
            {
                "pid": 412,
                "bundleId": diag.BUNDLE_ID,
                "executablePath": (
                    "/Applications/DaVinci Resolve/DaVinci Resolve.app"
                    "/Contents/MacOS/Resolve"
                ),
                "version": "21.1.1",
                "build": "10",
                "frontmost": True,
            }
        ],
        "tcc": {
            "status": 0,
            "promptRequested": False,
            "abi": "AEDesc*",
            "targetBundleId": diag.AUTOMATION_TARGET,
        },
        "ax": {"trusted": True, "promptRequested": False},
        "window": {
            "count": 1,
            "title": "VERA Delivery disposable",
            "main": True,
            "focused": False,
            "modalPresent": False,
            "focusRole": "AXGroup",
            "focusDescription": "group",
        },
        "menuItems": {
            "page_edit": {"found": True, "enabled": True, "mark": None},
            "trim_roll": {"found": True, "enabled": False},
            "nudge_right": {"found": True, "enabled": False, "cmdChar": None},
            "timeline_focus": {"found": True, "cmdChar": None},
            "save_control": {"found": True, "cmdChar": None},
        },
        "session": {"onConsole": True, "loginDone": True},
    }


def states(report: dict[str, Any]) -> dict[str, str]:
    return {name: entry["state"] for name, entry in report["checks"].items()}


def test_observed_ax_main_does_not_imply_focused_edit_or_track_ready() -> None:
    result = diag.assess(synthetic(), "VERA Delivery disposable")
    found = states(result)
    assert not result["ready"]
    assert found["main_window"] == "pass"
    assert found["focused_window"] == "fail"
    assert found["edit_page"] == "unknown"
    assert found["timeline_focused"] == "unknown"
    assert found["v1_only"] == "unknown"
    assert found["nudge_accelerator"] == "unknown"
    assert found["focus_accelerator"] == "unknown"
    assert found["unlocked_console"] == "unknown"


@pytest.mark.parametrize(
    ("change", "field", "expected"),
    [
        (
            lambda v: v["applications"].append(v["applications"][0].copy()),
            "single_process",
            "fail",
        ),
        (lambda v: v["applications"][0].update(pid=-1), "executable_identity", "fail"),
        (
            lambda v: v["applications"][0].update(bundleId="evil.app"),
            "executable_identity",
            "fail",
        ),
        (
            lambda v: v["applications"][0].update(executablePath="/bin/Resolve"),
            "executable_identity",
            "fail",
        ),
        (
            lambda v: v["applications"][0].update(version="22.0"),
            "studio_version",
            "fail",
        ),
        (lambda v: v["applications"][0].update(frontmost=False), "foreground", "fail"),
        (lambda v: v["window"].update(count=2), "single_window", "fail"),
        (lambda v: v["window"].update(title="Wrong project"), "correct_window", "fail"),
        (lambda v: v["window"].update(modalPresent=True), "modal_absent", "fail"),
        (lambda v: v["ax"].update(trusted=False), "accessibility_no_prompt", "fail"),
        (
            lambda v: v["ax"].update(promptRequested=True),
            "accessibility_no_prompt",
            "fail",
        ),
        (lambda v: v["tcc"].update(status=-1743), "automation_no_prompt", "fail"),
        (
            lambda v: v["tcc"].update(promptRequested=True),
            "automation_no_prompt",
            "fail",
        ),
        (lambda v: v["tcc"].update(abi="int"), "automation_no_prompt", "fail"),
        (
            lambda v: v["tcc"].update(targetBundleId=diag.BUNDLE_ID),
            "automation_no_prompt",
            "fail",
        ),
        (
            lambda v: v["menuItems"]["trim_roll"].update(found=False),
            "trim_roll_available",
            "unknown",
        ),
        (
            lambda v: v["menuItems"]["nudge_right"].update(enabled=None),
            "nudge_available",
            "unknown",
        ),
    ],
)
def test_fail_closed_guards(
    change: Callable[[dict[str, Any]], None], field: str, expected: str
) -> None:
    data = synthetic()
    change(data)
    result = diag.assess(data, "VERA Delivery disposable")
    assert result["ready"] is False
    assert states(result)[field] == expected


def test_no_window_target_is_never_accepted_from_a_correct_current_title() -> None:
    result = diag.assess(synthetic(), None)
    assert states(result)["correct_window"] == "unknown"
    assert not result["ready"]


def test_marked_edit_requires_observed_selection_not_merely_menu_enabled() -> None:
    observed = synthetic()
    observed["menuItems"]["page_edit"]["mark"] = "✓"
    assert (
        states(diag.assess(observed, "VERA Delivery disposable"))["edit_page"] == "pass"
    )
    observed["menuItems"]["page_edit"]["mark"] = ""
    assert (
        states(diag.assess(observed, "VERA Delivery disposable"))["edit_page"]
        == "unknown"
    )
    observed["menuItems"]["page_edit"]["mark"] = "-"
    assert (
        states(diag.assess(observed, "VERA Delivery disposable"))["edit_page"]
        == "unknown"
    )


def test_real_menu_accelerator_control_is_not_imputed_when_absent() -> None:
    observed = synthetic()
    observed["menuItems"]["timeline_focus"] = {
        "found": False,
        "cmdChar": "4",
        "cmdModifiers": 0,
    }
    assert (
        states(diag.assess(observed, "VERA Delivery disposable"))["focus_accelerator"]
        == "unknown"
    )
    observed["menuItems"]["timeline_focus"]["found"] = True
    observed["menuItems"]["timeline_focus"]["cmdChar"] = None
    observed["menuItems"]["save_control"]["cmdChar"] = (
        "s"  # AX control also absent on Mac
    )
    assert (
        states(diag.assess(observed, "VERA Delivery disposable"))["focus_accelerator"]
        == "unknown"
    )
    observed["menuItems"]["timeline_focus"]["cmdChar"] = "3"
    observed["menuItems"]["timeline_focus"]["cmdModifiers"] = 0
    assert (
        states(diag.assess(observed, "VERA Delivery disposable"))["focus_accelerator"]
        == "fail"
    )
    observed["menuItems"]["timeline_focus"]["cmdChar"] = "4"
    del observed["menuItems"]["timeline_focus"]["cmdModifiers"]
    assert (
        states(diag.assess(observed, "VERA Delivery disposable"))["focus_accelerator"]
        == "unknown"
    )
    observed["menuItems"]["timeline_focus"]["cmdModifiers"] = 0  # Command implicit
    assert (
        states(diag.assess(observed, "VERA Delivery disposable"))["focus_accelerator"]
        == "pass"
    )
    observed["menuItems"]["timeline_focus"]["cmdModifiers"] = 8  # no Command
    assert (
        states(diag.assess(observed, "VERA Delivery disposable"))["focus_accelerator"]
        == "fail"
    )


@pytest.mark.parametrize(
    "invalid", [None, [], {}, {"schema": 1, "source": "mock", "platform": "macOS"}]
)
def test_malicious_or_ambiguous_probe_claims_never_pass(invalid: object) -> None:
    report = diag.assess(invalid if isinstance(invalid, dict) else {}, None)
    assert not report["ready"]
    assert "invalid_native_probe_schema" in report["errors"]


def test_wrong_platform_or_bad_process_shape_refuse() -> None:
    observed = synthetic()
    observed["platform"] = "Linux"
    assert diag.assess(observed, "VERA Delivery disposable")["errors"] == ["not_macos"]
    observed["platform"] = "macOS"
    observed["applications"] = [{"pid": "str"}]
    assert states(diag.assess(observed, None))["executable_identity"] == "fail"


def test_native_probe_bundle_id_must_match_before_classifying_checks() -> None:
    observed = synthetic()
    observed["bundleId"] = "com.example.impostor"
    report = diag.assess(observed, "VERA Delivery disposable")
    assert report["ready"] is False
    assert report["errors"] == ["unexpected_bundle_id"]
    assert states(report)["native_host"] == "unknown"


def test_linux_cannot_claim_actual_host_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: pytest.fail("native call")
    )
    report = diag.run_probe("VERA Delivery disposable")
    assert report["evidence"] == "not-run"
    assert report["hostVerified"] is False
    assert report["ready"] is False


@pytest.mark.parametrize("scenario", ["timeout", "bad_json", "nonzero", "nonobject"])
def test_probe_error_never_reports_host_verified(
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Darwin")

    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        if scenario == "timeout":
            raise subprocess.TimeoutExpired(cmd="swift", timeout=1)
        if scenario == "bad_json":
            return SimpleNamespace(returncode=0, stdout="not json", stderr="")
        if scenario == "nonobject":
            return SimpleNamespace(returncode=0, stdout="[]", stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="failed")

    monkeypatch.setattr(subprocess, "run", fake_run)
    report = diag.run_probe(None)
    assert report["evidence"] == "probe-error"
    assert report["hostVerified"] is False
    assert report["ready"] is False


def test_swift_diagnostic_is_read_only_no_prompt_and_uses_correct_abi() -> None:
    swift = Path(diag.PROBE).read_text()
    assert "AEDeterminePermissionToAutomateTarget(" in swift
    assert "&target, typeWildCard, typeWildCard, false" in swift
    assert "AECreateDesc(typeApplicationBundleID" in swift
    assert "AXIsProcessTrustedWithOptions" in swift
    assert "kAXTrustedCheckOptionPrompt" in swift
    assert "AXUIElementCopyAttributeValue" in swift
    for prohibited in (
        "AXUIElementPerformAction(",
        "AXUIElementSetAttributeValue(",
        "CGEventPost(",
        'activate("',
        "AppleEventSend(",
        "AEEventSend(",
    ):
        assert prohibited not in swift


def test_assessment_is_json_serializable() -> None:
    json.dumps(diag.assess(synthetic(), "VERA Delivery disposable"))
