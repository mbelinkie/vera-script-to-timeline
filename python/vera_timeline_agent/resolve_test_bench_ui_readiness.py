"""Read-only, fail-closed macOS preflight for #473's *one* F1 M4 edit.

No public JSON/booleans are a trusted readiness claim. The production entry
point re-authenticates the original M4 capture through the held native owner,
then obtains OS observations using a fixed, read-only System Events probe.
Unknown macOS properties are *not* guessed from the SDK or earlier trials.

This module never switches pages, focuses windows, selects tracks, alters TCC,
positions the playhead, invokes the #495 actuator, or writes a native receipt.
"""

from __future__ import annotations

import json
import os
import platform
import stat
import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any, Protocol

from . import resolve_gui_roll as gui

# An in-process, one-consumption provenance check for the *actual* executor.
# Constructing a TrustedUiReadiness dataclass with caller-chosen True values
# does not create this evidence. The shared owner must still be held.
_ATTESTED: ContextVar[
    tuple[gui.GuiRollIntent, gui.PristineSdkInventory, gui.TrustedUiReadiness, float]
    | None
] = ContextVar("issue499_owner_sdk_os_ui_attested", default=None)

# JXA uses NSWorkspace (actual process identity) and System Events (read-only
# AX state). No activate/click/keystroke, no user-supplied code, no shell. It
# deliberately does NOT open Keyboard Customization. Instead, it obtains the
# two active *menu item* accelerators through AX. The independent local
# preferences read below confirms the unmodified default preset. Both proofs
# are mandatory; a config file alone cannot prove the live effective binding.
_KEYBOARD_DIR = Path.home() / "Library/Preferences/Blackmagic Design/DaVinci Resolve"
_KEYBOARD_CONFIG_PATH = _KEYBOARD_DIR / "config.user.xml"
_KEYBOARD_PRESETS_PATH = _KEYBOARD_DIR / "keyboard.preset.xml"

_OS_READ_ONLY_JXA = r"""
ObjC.import('AppKit');
ObjC.import('ApplicationServices');
ObjC.import('Carbon');
function unwrap(x) { return x === null || x === undefined ? null : ObjC.unwrap(x); }
function attr(obj, name) {
  try { return obj.attributes.byName(name).value(); } catch (_) { return null; }
}
function menuItem(proc, menuName, path) {
  let m = proc.menuBars[0].menuBarItems.byName(menuName).menus[0];
  for (let i = 0; i < path.length; i++) {
    let item = m.menuItems.byName(path[i]);
    if (!item.exists()) return null;
    if (i === path.length - 1) return item;
    m = item.menus[0];
  }
  return null;
}
function enabled(item) {
  try { return item !== null && item.enabled() === true; }
  catch (_) { return false; }
}
function shortcut(item, expectedChar, expectedModifiers, result) {
  // AX advertises the *live effective* menu accelerator, not an assumed
  // factory default. No inferred keyboard map, fallback glyph, or coercion.
  if (!enabled(item) ||
      attr(item, 'AXMenuItemCmdChar') !== expectedChar ||
      attr(item, 'AXMenuItemCmdModifiers') !== expectedModifiers) return null;
  return result;
}
function checked(item) {
  const mark = item === null ? null : attr(item, 'AXMenuItemMarkChar');
  // A missing/unknown AX mark is NOT an unchecked or checked item.
  if (mark === null) return null;
  return String(mark) === '\u2713' || String(mark) === '\u2714';
}
function run() {
  const workspace = $.NSWorkspace.sharedWorkspace;
  const running = unwrap(workspace.runningApplications);
  const matches = running.filter(
    x => unwrap(x.bundleIdentifier) === 'com.blackmagic-design.DaVinciResolve'
  );
  const front = workspace.frontmostApplication;
  const app = matches.length === 1 ? matches[0] : null;
  let result = {
    runningResolveCount: matches.length,
    processName: app ? unwrap(app.localizedName) : null,
    processPid: app ? Number(app.processIdentifier) : null,
    bundleId: app ? unwrap(app.bundleIdentifier) : null,
    bundlePath: app ? unwrap(app.bundleURL.path) : null,
    bundleShortVersion: null, bundleBuild: null,
    frontmostPid: front ? Number(front.processIdentifier) : null,
    frontmostBundleId: front ? unwrap(front.bundleIdentifier) : null,
    frontmostProcess: front ? unwrap(front.localizedName) : null,
    accessibility: false, automation: false,
    windowCount: null, windowName: null, windowFrontmost: null,
    modalPresent: null, editPage: null, timelineFocused: null,
    v1Only: null, trimRollMenu: null, nudgeMenu: null,
    keyboardPreset: null, keyboardFocus: null, keyboardNudge: null
  };
  if (app !== null && app.bundleURL !== null) {
    const info = $.NSBundle.bundleWithURL(app.bundleURL).infoDictionary;
    result.bundleShortVersion = unwrap(
      info.objectForKey($('CFBundleShortVersionString'))
    );
    result.bundleBuild = unwrap(info.objectForKey($('CFBundleVersion')));
  }
  // AXIsProcessTrusted() does NOT request access and does not modify TCC.
  // Only if already trusted may the OS actor inspect System Events.
  result.accessibility = Boolean($.AXIsProcessTrusted());
  if (!result.accessibility || app === null ||
      result.frontmostPid !== result.processPid) {
    return JSON.stringify(result);
  }
  // Query Automation permission *without prompting*. A System Events read
  // itself can trigger a TCC prompt if permission has not already been granted.
  // 0x2a2a2a2a is typeWildCard ('****') for both event class and event ID.
  try {
    const systemEvents = $.NSAppleEventDescriptor.descriptorWithBundleIdentifier(
      $('com.apple.systemevents')
    );
    result.automation = $.AEDeterminePermissionToAutomateTarget(
      systemEvents.aeDesc, 0x2a2a2a2a, 0x2a2a2a2a, false
    ) === 0;
  } catch (_) { result.automation = false; }
  if (!result.automation) return JSON.stringify(result);
  try {
    const events = Application('System Events');
    const proc = events.applicationProcesses.byName('Resolve');
    if (!proc.exists() || !proc.frontmost()) return JSON.stringify(result);
    // A successful read is evidence of this OS actor's automation access;
    // a missing permission, denial or AX failure must never be set true.
    const windows = proc.windows();
    result.windowCount = windows.length;
    if (windows.length !== 1) return JSON.stringify(result);
    const win = windows[0];
    result.windowName = win.name();
    // System Events' windows need not expose a `frontmost` property. Demand
    // both explicit AXMain and AXFocused marks, never infer from one window.
    result.windowFrontmost = attr(win, 'AXMain') === true &&
      attr(win, 'AXFocused') === true;
    result.modalPresent = win.sheets().length !== 0;
    const edit = menuItem(proc, 'Workspace', ['Switch to Page', 'Edit']);
    result.editPage = checked(edit) === true;
    const focused = attr(proc, 'AXFocusedUIElement');
    // No guessing from a visible timeline. AX must identify the focused area.
    result.timelineFocused = focused !== null &&
      attr(focused, 'AXRoleDescription') === 'timeline';
    // Original signed M4 has precisely V1 and A1 through A5 (six tracks).
    const auto = ['V1', 'A1', 'A2', 'A3', 'A4', 'A5'];
    const states = auto.map(t => checked(menuItem(
      proc, 'Timeline', ['Auto Select', 'Auto Select/Deselect ' + t]
    )));
    result.v1Only = states[0] === true && states.slice(1).every(s => s === false);
    result.trimRollMenu = enabled(menuItem(
      proc, 'Trim', ['Select Nearest Edit To', 'Roll']
    ));
    result.nudgeMenu = enabled(menuItem(proc, 'Trim', ['Nudge', 'One Frame Right']));
    result.keyboardFocus = shortcut(menuItem(
      proc, 'Workspace', ['Active Panel Selection', 'Timeline']
    ), '4', 0, 'Command-4');
    // kAXMenuItemModifierNoCommand=8; the F1 actuator uses the menu item,
    // but we also verify its expected default accelerator without using it.
    result.keyboardNudge = shortcut(menuItem(
      proc, 'Trim', ['Nudge', 'One Frame Right']
    ), '.', 8, '.');
  } catch (_) {
    // An AX/TCC exception must fail closed; never synthesize positive flags.
    result.automation = false;
  }
  return JSON.stringify(result);
}
run();
""".strip()


class OsSnapshot(Protocol):
    def observe(self) -> Mapping[str, object]:
        """Return raw OS observations; no expectation or target assertions."""


def _keyboard_file(path: Path) -> bytes:
    """Read one fixed owned regular XML file, without following a swapped leaf."""
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_uid != os.getuid()
                or before.st_nlink != 1
                or not 0 < before.st_size <= 128 * 1024
            ):
                raise gui.GuiRollRefused("keyboard preferences owner/type/size differ")
            raw = stream.read(128 * 1024 + 1)
            after = os.fstat(stream.fileno())
            if len(raw) != before.st_size or (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
            ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                raise gui.GuiRollRefused("keyboard preferences changed during read")
            return raw
    except OSError as error:
        raise gui.GuiRollRefused("keyboard preferences unreadable") from error


def _keyboard_sources(config_path: Path, presets_path: Path) -> tuple[bytes, bytes]:
    return _keyboard_file(config_path), _keyboard_file(presets_path)


def _parse_keyboard_preset(sources: tuple[bytes, bytes]) -> str:
    """Verify Resolve's default active mapping and absence of stored overrides.

    This is only half the proof. AX separately verifies the effective menu
    shortcuts on the foreground Resolve process before admission.
    """
    try:
        if any(b"<!DOCTYPE" in raw or b"<!ENTITY" in raw for raw in sources):
            raise ValueError("XML declarations unsupported")
        config, presets = (ET.fromstring(raw) for raw in sources)
        mapping = config.findall(".//KeyboardMappings")
        custom = config.findall(".//CustomKeyboardPreset")
        fields = presets.findall(".//FieldsBlob")
        overrides = presets.findall(".//PresetListBA")
        if not (
            config.tag == "SM_UserPrefs"
            and presets.tag == "SmKeyboardPresetList"
            and len(mapping) == len(custom) == len(fields) == len(overrides) == 1
            and mapping[0].text == "0"
            and not mapping[0].attrib
            and not list(custom[0])
            and not custom[0].attrib
            and not (custom[0].text or "").strip()
            and not list(fields[0])
            and not fields[0].attrib
            and not (fields[0].text or "").strip()
            and not list(overrides[0])
            and not overrides[0].attrib
            and not (overrides[0].text or "").strip()
        ):
            raise ValueError("nondefault active keyboard mapping or overrides")
    except (ET.ParseError, ValueError) as error:
        raise gui.GuiRollRefused(
            "keyboard preset not independently verified as unmodified default"
        ) from error
    return gui.KEYBOARD_PRESET


def _trusted_keyboard_preset(config_path: Path, presets_path: Path) -> str:
    return _parse_keyboard_preset(_keyboard_sources(config_path, presets_path))


class MacReadOnlyObserver:
    """Fixed, no-action OS observer; injectable *only* in unit-level tests."""

    def observe(self) -> Mapping[str, object]:
        if platform.system() != "Darwin":
            raise gui.GuiRollRefused("read-only UI probe requires macOS")
        before = _keyboard_sources(_KEYBOARD_CONFIG_PATH, _KEYBOARD_PRESETS_PATH)
        try:
            completed = subprocess.run(
                ["/usr/bin/osascript", "-l", "JavaScript", "-e", _OS_READ_ONLY_JXA],
                check=False,
                text=True,
                capture_output=True,
                timeout=12,
            )
            if completed.returncode != 0 or len(completed.stdout) > 8192:
                raise gui.GuiRollRefused("read-only macOS UI probe failed")
            snapshot = json.loads(completed.stdout)
        except (OSError, subprocess.TimeoutExpired, ValueError) as error:
            raise gui.GuiRollRefused("read-only macOS UI probe unavailable") from error
        if not isinstance(snapshot, dict):
            raise gui.GuiRollRefused("untrusted OS UI observation format")
        # The fixed JXA deliberately cannot assert a keyboard preset by itself.
        # Reject any OS-supplied green preset, then check the same bytes again
        # after the live OS observation (refuse a preset swapped mid-preflight).
        if snapshot.get("keyboardPreset") is not None:
            raise gui.GuiRollRefused("keyboard preset must come from owned files")
        after = _keyboard_sources(_KEYBOARD_CONFIG_PATH, _KEYBOARD_PRESETS_PATH)
        if before != after:
            raise gui.GuiRollRefused("keyboard preferences changed during OS probe")
        snapshot["keyboardPreset"] = _parse_keyboard_preset(after)
        return snapshot


def _field(snapshot: Mapping[str, object], name: str, kind: type) -> Any:
    value = snapshot.get(name)
    if type(value) is not kind:
        raise gui.GuiRollRefused("OS UI observation missing or ambiguous: " + name)
    return value


def _readiness_from_os(
    snapshot: Mapping[str, object], target: gui.NativeTarget
) -> gui.TrustedUiReadiness:
    """Validate concrete observations; no default True, coercion, or inference."""
    required = {
        "runningResolveCount": int,
        "processPid": int,
        "processName": str,
        "bundleId": str,
        "bundlePath": str,
        "bundleShortVersion": str,
        "bundleBuild": str,
        "frontmostPid": int,
        "frontmostBundleId": str,
        "frontmostProcess": str,
        "accessibility": bool,
        "automation": bool,
        "windowCount": int,
        "windowName": str,
        "windowFrontmost": bool,
        "modalPresent": bool,
        "editPage": bool,
        "timelineFocused": bool,
        "v1Only": bool,
        "trimRollMenu": bool,
        "nudgeMenu": bool,
        "keyboardPreset": str,
        "keyboardFocus": str,
        "keyboardNudge": str,
    }
    if set(snapshot) != set(required):
        raise gui.GuiRollRefused("unrecognized or incomplete OS UI evidence")
    observation = {
        name: _field(snapshot, name, kind) for name, kind in required.items()
    }
    gui._require(
        observation["runningResolveCount"] == 1
        and observation["processPid"] > 0
        and observation["processPid"] == observation["frontmostPid"]
        and observation["windowCount"] == 1
        and observation["windowFrontmost"] is True
        and observation["processName"] in {"Resolve", "DaVinci Resolve"}
        and observation["bundleId"] == gui.RESOLVE_BUNDLE_ID
        and observation["frontmostBundleId"] == gui.RESOLVE_BUNDLE_ID
        and observation["frontmostProcess"] == observation["processName"]
        and observation["bundlePath"]
        == "/Applications/DaVinci Resolve/DaVinci Resolve.app"
        and observation["bundleShortVersion"] == "21.1.1"
        and observation["bundleBuild"] == "21.1.10010"
        and observation["windowName"] == target.expected_window_name,
        "actual Resolve process/bundle/build/window or frontmost identity differs",
    )
    readiness = gui.TrustedUiReadiness(
        os_name="Darwin",
        resolve_version=gui.RESOLVE_VERSION,  # independently SDK-pinned by owner
        resolve_bundle_id=observation["bundleId"],
        frontmost_bundle_id=observation["frontmostBundleId"],
        frontmost_process=gui.RESOLVE_PROCESS,
        front_window_name=observation["windowName"],
        accessibility_trusted=observation["accessibility"],
        automation_trusted=observation["automation"],
        modal_present=observation["modalPresent"],
        edit_page=observation["editPage"],
        timeline_focused=observation["timelineFocused"],
        v1_only=observation["v1Only"],
        trim_roll_menu_enabled=observation["trimRollMenu"],
        nudge_menu_enabled=observation["nudgeMenu"],
        keyboard_preset=observation["keyboardPreset"],
        keyboard_focus_binding=observation["keyboardFocus"],
        keyboard_nudge_binding=observation["keyboardNudge"],
    )
    return readiness


def prepare_owned_ui_readiness(
    store: Any, job_id: str, resolve: Any
) -> tuple[gui.GuiRollIntent, gui.PristineSdkInventory, gui.TrustedUiReadiness]:
    """Authenticated M4 SDK + independent OS, no caller-provided readiness.

    Production uses only the fixed Mac observer; fake observations are admitted
    by testing ``_readiness_from_os`` in isolation, never by a host argument.
    """
    from . import resolve_test_bench_gui_stage as stage

    _ATTESTED.set(None)
    gui._require_owner_lock()
    intent, inventory = stage.prepare_owned_f1_inputs(store, job_id, resolve)
    snapshot = MacReadOnlyObserver().observe()
    readiness = _readiness_from_os(snapshot, intent.target)
    gui._validate(intent, inventory, readiness, datetime.now(UTC))
    _ATTESTED.set((intent, inventory, readiness, monotonic()))
    return intent, inventory, readiness


def _consume_attested_ui_readiness(
    intent: gui.GuiRollIntent,
    inventory: gui.PristineSdkInventory,
    readiness: gui.TrustedUiReadiness,
) -> None:
    """Only phase-2 production dispatch can consume fresh OS/SDK provenance."""
    proof = _ATTESTED.get()
    _ATTESTED.set(None)  # fail-stop even if identity, owner, or age differs
    gui._require(
        proof is not None
        and proof[0] is intent
        and proof[1] is inventory
        and proof[2] is readiness
        and 0 <= monotonic() - proof[3] <= 5,
        "no fresh authenticated same-owner SDK/OS UI readiness",
    )
    gui._require_owner_lock()
