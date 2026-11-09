#!/usr/bin/env python3
"""Read-only, fail-closed diagnostics for Resolve Studio 21.1.1.10 (#500).

This is NOT an M4 verifier or a way to authorize or dispatch native operations.
It deliberately does not import the production GUI roll or its source-seal owner.
Run on the Mac with ``python3 scripts/resolve_readiness_diagnostic.py``.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

BUNDLE_ID = "com.blackmagic-design.DaVinciResolve"
AUTOMATION_TARGET = "com.apple.systemevents"
STUDIO_VERSION = "21.1.1.10"
PROBE = Path(__file__).with_name("resolve_readiness_probe.swift")
CHECK_NAMES = (
    "native_host",
    "single_process",
    "executable_identity",
    "studio_version",
    "automation_no_prompt",
    "accessibility_no_prompt",
    "foreground",
    "single_window",
    "correct_window",
    "main_window",
    "focused_window",
    "modal_absent",
    "edit_page",
    "timeline_focused",
    "v1_only",
    "trim_roll_available",
    "nudge_available",
    "focus_accelerator",
    "nudge_accelerator",
    "unlocked_console",
)


def check(
    state: Literal["pass", "fail", "unknown"],
    observed: Any,
    reason: str,
) -> dict[str, Any]:
    return {"state": state, "observed": observed, "reason": reason}


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _boolean(value: Any, description: str, *, invert: bool = False) -> dict[str, Any]:
    if type(value) is not bool:
        return check("unknown", value, f"{description}: not observable")
    return check("pass" if value != invert else "fail", value, description)


def _menu(native: dict[str, Any], key: str) -> dict[str, Any]:
    menus = native.get("menuItems")
    item = menus.get(key) if isinstance(menus, dict) else None
    return item if isinstance(item, dict) else {}


def _accelerator(native: dict[str, Any], key: str, expected: str) -> dict[str, Any]:
    item = _menu(native, key)
    if item.get("found") is not True:
        return check("unknown", item, f"{key}: menu item not observed")
    char = item.get("cmdChar")
    if char is None:
        return check(
            "unknown", None, f"{key}: AXMenuItemCmdChar absent; no shortcut inferred"
        )
    if not isinstance(char, str) or not char:
        return check("unknown", char, f"{key}: invalid AX accelerator")
    modifiers = item.get("cmdModifiers")
    if type(modifiers) is not int:
        return check(
            "unknown",
            {"char": char, "modifiers": modifiers},
            f"{key}: AX accelerator modifiers absent; effective binding unknown",
        )
    # AXMenuItemCmdModifiers: Command is implicit except for bit 3 (NoCommand).
    # A focus shortcut is Command+4; a single-frame period nudge is unmodified.
    command_present = not bool(modifiers & 8)
    expected_command = key == "timeline_focus"
    if command_present != expected_command or modifiers & 7:
        return check(
            "fail",
            {"char": char, "modifiers": modifiers},
            f"{key}: menu modifiers disagree with expected binding",
        )
    # A displayed key is not proof of keyboard focus or effective bindings.
    return check(
        "pass" if char == expected else "fail",
        {"char": char, "modifiers": modifiers},
        f"{key}: reported AX accelerator only; effective keymap unverified",
    )


def assess(native: dict[str, Any], expected_window: str | None) -> dict[str, Any]:
    """Classify raw observations without upgrading missing fields to successes."""
    checks = {name: check("unknown", None, "not observed") for name in CHECK_NAMES}
    provenance = native.get("source")
    if native.get("schema") != 1 or provenance != "native-swift-ax":
        return {
            "ready": False,
            "checks": checks,
            "errors": ["invalid_native_probe_schema"],
        }
    if native.get("platform") != "macOS":
        return {"ready": False, "checks": checks, "errors": ["not_macos"]}
    if native.get("bundleId") != BUNDLE_ID:
        return {"ready": False, "checks": checks, "errors": ["unexpected_bundle_id"]}
    checks["native_host"] = check("pass", "macOS", "native Swift read-only probe")

    apps = native.get("applications")
    if not isinstance(apps, list):
        apps = []
    checks["single_process"] = check(
        "pass" if len(apps) == 1 else "fail",
        len(apps),
        "exactly one running app with the pinned bundle identifier required",
    )
    if len(apps) != 1 or not isinstance(apps[0], dict):
        return {"ready": False, "checks": checks, "errors": ["process_count_or_shape"]}
    app = apps[0]
    path = app.get("executablePath")
    valid_path = (
        isinstance(path, str)
        and path.endswith("/Contents/MacOS/Resolve")
        and app.get("bundleId") == BUNDLE_ID
        and type(app.get("pid")) is int
        and app["pid"] > 0
    )
    checks["executable_identity"] = check(
        "pass" if valid_path else "fail",
        path,
        "bundle ID, running PID and actual Resolve executable must match",
    )
    version = app.get("version")
    build = app.get("build")
    correct_version = version == STUDIO_VERSION or (
        version == "21.1.1" and str(build) == "21.1.10010"
    )
    checks["studio_version"] = check(
        "pass" if correct_version else ("unknown" if version is None else "fail"),
        {"version": version, "build": build},
        "pinned Studio 21.1.1 build 10 only",
    )
    checks["foreground"] = _boolean(app.get("frontmost"), "foreground app identity")

    tcc = _object(native.get("tcc"))
    code = tcc.get("status")
    if (
        tcc.get("promptRequested") is not False
        or tcc.get("abi") != "AEDesc*"
        or tcc.get("targetBundleId") != AUTOMATION_TARGET
    ):
        checks["automation_no_prompt"] = check(
            "fail", tcc, "no-prompt ABI proof missing"
        )
    elif type(code) is int:
        checks["automation_no_prompt"] = check(
            "pass" if code == 0 else "fail",
            code,
            "System Events TCC no-prompt check; OSStatus 0 proves only narrow consent",
        )
    else:
        checks["automation_no_prompt"] = check(
            "unknown", code, "TCC API did not return an OSStatus"
        )
    ax = _object(native.get("ax"))
    checks["accessibility_no_prompt"] = (
        _boolean(ax.get("trusted"), "AXIsProcessTrustedWithOptions(prompt=false)")
        if ax.get("promptRequested") is False
        else check("fail", ax, "AX prompt prohibition not established")
    )

    window = _object(native.get("window"))
    count = window.get("count")
    checks["single_window"] = (
        check("pass" if count == 1 else "fail", count, "exactly one AX window required")
        if type(count) is int
        else check("unknown", count, "AXWindows unavailable")
    )
    title = window.get("title")
    if not expected_window:
        checks["correct_window"] = check(
            "unknown", title, "no exact target supplied; title cannot be approved"
        )
    elif not isinstance(title, str):
        checks["correct_window"] = check("unknown", title, "AXTitle unavailable")
    else:
        checks["correct_window"] = check(
            "pass" if title == expected_window else "fail",
            title,
            "exact project window title match",
        )
    checks["main_window"] = _boolean(
        window.get("main"), "AXMain status (not a proxy for AXFocused)"
    )
    checks["focused_window"] = _boolean(
        window.get("focused"), "AXFocused status (not inferred from AXMain)"
    )
    checks["modal_absent"] = _boolean(
        window.get("modalPresent"), "AXSheet observation", invert=True
    )

    edit = _menu(native, "page_edit")
    mark = edit.get("mark")
    if edit.get("found") is False:
        checks["edit_page"] = check(
            "unknown", edit, "Edit menu item missing; page not observed"
        )
    elif isinstance(mark, str) and mark.strip() in {"✓", "✔"}:
        checks["edit_page"] = check(
            "pass", mark, "Edit item has an observable selected mark"
        )
    else:
        checks["edit_page"] = check(
            "unknown",
            mark,
            "AXMenuItemMarkChar missing or unrecognized; "
            "menu enablement does not prove Edit page",
        )

    role = window.get("focusRole")
    if role == "AXTimeline":
        checks["timeline_focused"] = check(
            "pass", role, "explicit AX timeline-focused role"
        )
    else:
        checks["timeline_focused"] = check(
            "unknown",
            {"role": role, "description": window.get("focusDescription")},
            "focused group/description is not reliable timeline focus proof",
        )
    checks["v1_only"] = check(
        "unknown",
        native.get("trackStates"),
        "AX track marks absent; menu enablement does not prove V1-only selection",
    )
    for name, key in (
        ("trim_roll_available", "trim_roll"),
        ("nudge_available", "nudge_right"),
    ):
        item = _menu(native, key)
        if item.get("found") is True:
            checks[name] = _boolean(
                item.get("enabled"), f"AX menu {key} enabled (capability only)"
            )
        else:
            checks[name] = check("unknown", item, f"{key} menu not observed")
    checks["focus_accelerator"] = _accelerator(native, "timeline_focus", "4")
    checks["nudge_accelerator"] = _accelerator(native, "nudge_right", ".")

    session = _object(native.get("session"))
    on_console = session.get("onConsole")
    login_done = session.get("loginDone")
    if type(on_console) is bool and type(login_done) is bool:
        checks["unlocked_console"] = check(
            "pass" if on_console and login_done else "fail",
            {"onConsole": on_console, "loginDone": login_done},
            "CGSession signals (do not establish screen-unlocked state independently)",
        )
        # Console/session hints do not prove the screen is unlocked; refuse.
        checks["unlocked_console"]["state"] = "unknown"
    return {
        "ready": all(x["state"] == "pass" for x in checks.values()),
        "checks": checks,
        "errors": [],
    }


def run_probe(expected_window: str | None, *, timeout: int = 25) -> dict[str, Any]:
    if platform.system() != "Darwin":
        return {
            "evidence": "not-run",
            "hostVerified": False,
            "ready": False,
            "checks": {
                name: check("unknown", None, "non-macOS host") for name in CHECK_NAMES
            },
            "errors": ["requires_macos_real_host"],
        }
    try:
        proc = subprocess.run(
            ["swift", str(PROBE)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "evidence": "probe-error",
            "hostVerified": False,
            "ready": False,
            "checks": {},
            "errors": [type(exc).__name__],
        }
    if proc.returncode != 0:
        return {
            "evidence": "probe-error",
            "hostVerified": False,
            "ready": False,
            "checks": {},
            "errors": ["swift_nonzero_exit", proc.stderr[-500:]],
        }
    try:
        native = json.loads(proc.stdout)
    except (ValueError, TypeError):
        return {
            "evidence": "probe-error",
            "hostVerified": False,
            "ready": False,
            "checks": {},
            "errors": ["invalid_json"],
        }
    if not isinstance(native, dict):
        return {
            "evidence": "probe-error",
            "hostVerified": False,
            "ready": False,
            "checks": {},
            "errors": ["invalid_object"],
        }
    assessment = assess(native, expected_window)
    # Only actual Darwin subprocess evidence is "actual-host". No fixture flag.
    verified = not assessment["errors"]
    return {
        "evidence": "actual-host" if verified else "probe-error",
        "hostVerified": verified,
        "raw": native,
        **assessment,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected-window", help="exact approved Resolve project window title"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=25,
        help="read-only Swift query timeout in seconds",
    )
    args = parser.parse_args()
    report = run_probe(args.expected_window, timeout=max(1, min(120, args.timeout)))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("hostVerified") else 2


if __name__ == "__main__":
    sys.exit(main())
