"""Read-only, fail-closed macOS preflight for #473's *one* F1 M4 edit.

No public JSON/booleans are a trusted readiness claim. The production entry
point re-authenticates the original M4 capture through the held native owner,
then obtains OS observations using a fixed, read-only System Events probe.
Unknown macOS properties are *not* guessed from the SDK or earlier trials.

The production preflight may bring the *already-running, exact signed-app*
Resolve process to the foreground before independently observing it. It never
switches pages, selects tracks, alters TCC, positions the playhead, invokes
the #495 actuator, or writes a native receipt.
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
from dataclasses import replace
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

# A separate, bounded preflight action: focus only an existing trusted Resolve
# process after the SDK/owner have identified the intended disposable target.
# Never launch the app (which could open an arbitrary recent producer project),
# choose a document, or send a keyboard/menu event. The OS read-only observer
# below must still recheck every fact; this is not a readiness attestation.
_FOREGROUND_EXISTING_JXA = r"""
ObjC.import('AppKit');
ObjC.import('Carbon');
ObjC.bindFunction('AEDeterminePermissionToAutomateTarget',
  ['int', ['void*', 'uint32_t', 'uint32_t', 'bool']]);
function unwrap(x) { return x === null || x === undefined ? null : ObjC.unwrap(x); }
function noPromptOSStatusAllowed(status) {
  return typeof status === 'number' && status === 0;
}
function systemEventsTargetDescriptor() {
  // 'bund' is typeApplicationBundleID; the old JXA bridge selector fails.
  const bundleData = $('com.apple.systemevents')
    .dataUsingEncoding($.NSUTF8StringEncoding);
  if (bundleData.isNil()) return null;
  const descriptor = $.NSAppleEventDescriptor.descriptorWithDescriptorTypeData(
    0x62756e64, bundleData
  );
  if (descriptor.isNil() || descriptor.descriptorType !== 0x62756e64) return null;
  return descriptor;
}
function focusExistingViaSystemEvents(pid) {
  try {
    // Cooperative App Activation can decline a request on current macOS.
    // Only an already-allowed, no-prompt System Events actor may set the
    // *same existing process* frontmost. Never launch or manipulate windows.
    const descriptor = systemEventsTargetDescriptor();
    if (descriptor === null) return false;
    const permission = $.AEDeterminePermissionToAutomateTarget(
      descriptor.aeDesc, 0x2a2a2a2a, 0x2a2a2a2a, false
    );
    if (!noPromptOSStatusAllowed(permission)) {
      return false;
    }
    const matches = Application('System Events').applicationProcesses
      .whose({unixId:pid})();
    if (matches.length !== 1) return false;
    const proc = matches[0];
    if (typeof proc.unixId() !== 'number' || proc.unixId() !== pid) return false;
    proc.frontmost = true;
    return true;
  } catch (_) { return false; }
}
function run() {
  const workspace = $.NSWorkspace.sharedWorkspace;
  const matches = unwrap(workspace.runningApplications).filter(
    x => unwrap(x.bundleIdentifier) === 'com.blackmagic-design.DaVinciResolve'
  );
  if (matches.length !== 1) return JSON.stringify({activated:false,processPid:0});
  const app = matches[0];
  const info = $.NSBundle.bundleWithURL(app.bundleURL).infoDictionary;
  const version = unwrap(info.objectForKey($('CFBundleShortVersionString')));
  const build = unwrap(info.objectForKey($('CFBundleVersion')));
  const pid = Number(app.processIdentifier);
  if (unwrap(app.bundleURL.path) !==
        '/Applications/DaVinci Resolve/DaVinci Resolve.app' ||
      version !== '21.1.1' || build !== '21.1.10010' ||
      !Number.isInteger(pid) || pid <= 0 || app.terminated) {
    return JSON.stringify({activated:false,processPid:0});
  }
  const front = workspace.frontmostApplication;
  if (front === null || Number(front.processIdentifier) !== pid) {
    // A declined cooperative activation must not skip the separately
    // authorized, one-use PID-bound System Events fallback below.
    try { app.activateWithOptions(0); } catch (_) { /* fallback only */ }
    $.NSThread.sleepForTimeInterval(0.2);
  }
  // macOS can finish the Spaces/window transition shortly after activation
  // returns. Observe once more after a small, bounded settle; do not dispatch
  // another activation or infer success from the API's return value alone.
  let observed = workspace.frontmostApplication;
  if (observed === null || Number(observed.processIdentifier) !== pid) {
    $.NSThread.sleepForTimeInterval(0.3);
    observed = workspace.frontmostApplication;
  }
  if (observed === null || Number(observed.processIdentifier) !== pid) {
    if (focusExistingViaSystemEvents(pid)) {
      $.NSThread.sleepForTimeInterval(0.2);
      observed = workspace.frontmostApplication;
    }
  }
  return JSON.stringify({
    activated: observed !== null && Number(observed.processIdentifier) === pid,
    processPid: pid
  });
}
run();
""".strip()

_OS_READ_ONLY_JXA = r"""
ObjC.import('AppKit');
ObjC.import('ApplicationServices');
ObjC.import('Carbon');
// NSAppleEventDescriptor.aeDesc is an AEDesc pointer. JXA's imported typed
// Carbon binding rejects it with "Ref has incompatible type" before macOS can
// answer the permission query. Bind the same native function with its pointer
// argument as void*; the address, wildcard event codes and no-prompt flag stay
// unchanged. Only the void* binding was exercised on the Mac prior to the
// descriptor construction repair below; no live TCC grant is inferred.
ObjC.bindFunction('AEDeterminePermissionToAutomateTarget',
  ['int', ['void*', 'uint32_t', 'uint32_t', 'bool']]);
function unwrap(x) { return x === null || x === undefined ? null : ObjC.unwrap(x); }
function noPromptOSStatusAllowed(status) {
  return typeof status === 'number' && status === 0;
}
function systemEventsTargetDescriptor() {
  // 'bund' is typeApplicationBundleID; the old JXA bridge selector fails.
  const bundleData = $('com.apple.systemevents')
    .dataUsingEncoding($.NSUTF8StringEncoding);
  if (bundleData.isNil()) return null;
  const descriptor = $.NSAppleEventDescriptor.descriptorWithDescriptorTypeData(
    0x62756e64, bundleData
  );
  if (descriptor.isNil() || descriptor.descriptorType !== 0x62756e64) return null;
  return descriptor;
}
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
  // Match the fixed AppleScript exactly; ambiguous mixed/alternate marks
  // must not consume a one-use journal before the actor would refuse.
  if (mark === '\u2713') return true;
  if (mark === '') return false;
  return null;
}
function autoSelectStates(proc, tracks) {
  // Resolve's AX menu lookup crosses a process boundary. Read the common
  // Auto Select submenu once, not six times; each leaf and its live mark
  // must still exist independently. Missing/unknown remains null, never false.
  const root = menuItem(proc, 'Timeline', ['Auto Select']);
  const menu = root === null ? null : root.menus[0];
  return tracks.map(track => {
    if (menu === null) return null;
    const item = menu.menuItems.byName('Auto Select/Deselect ' + track);
    return item.exists() ? checked(item) : null;
  });
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
    v1Only: null, normalEditMode: null, trimRollMenu: null, nudgeMenu: null,
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
    const systemEvents = systemEventsTargetDescriptor();
    if (systemEvents === null) return JSON.stringify(result);
    // The actual Mac Carbon binding returned primitive number 0 (noErr).
    // Accept only that exact type/value; never coerce null, false, strings
    // or bridged wrapper objects to authorization, or request a TCC prompt.
    const permission = $.AEDeterminePermissionToAutomateTarget(
      systemEvents.aeDesc, 0x2a2a2a2a, 0x2a2a2a2a, false
    );
    result.automation = noPromptOSStatusAllowed(permission);
  } catch (_) { result.automation = false; }
  if (!result.automation) return JSON.stringify(result);
  try {
    const events = Application('System Events');
    const matchesByPid = events.applicationProcesses
      .whose({unixId:result.processPid})();
    if (matchesByPid.length !== 1) return JSON.stringify(result);
    const proc = matchesByPid[0];
    const osProcessPid = proc.unixId();
    if (typeof osProcessPid !== 'number' ||
        osProcessPid !== result.processPid || !proc.frontmost()) {
      return JSON.stringify(result);
    }
    // A successful read is evidence of this OS actor's automation access;
    // a missing permission, denial or AX failure must never be set true.
    const windows = proc.windows();
    result.windowCount = windows.length;
    if (windows.length !== 1) return JSON.stringify(result);
    const win = windows[0];
    result.windowName = win.name();
    // Real Qt reports AXFocused=false even for the sole correct AXMain window
    // with separately verified NSWorkspace frontmost PID. Named menu dispatch
    // uses that exact AXMain window, not timeline keyboard focus. This field
    // represents frontmost process + AXMain, NOT an inferred AXFocused mark.
    result.windowFrontmost = attr(win, 'AXMain') === true;
    result.modalPresent = win.sheets().length !== 0;
    // Qt does not expose reliable selected page, timeline focus, Auto Select,
    // normal-mode marks or shortcut characters through AX. Never assert these
    // fields true. The official SDK independently checks Edit + pinned 11 UIDs
    // on both sides of this OS check, and the fixed actuator performs absolute
    // menu setup before its one native effect. Required named menu availability
    // is independently read below via bounded AppleScript, not many JXA proxy
    // menu traversals (which exhaust the real host's osascript process).
    result.editPage = false;
    result.timelineFocused = false;
    result.v1Only = false;
    result.normalEditMode = false;
    result.trimRollMenu = false;
    result.nudgeMenu = false;
  } catch (_) {
    // An AX/TCC exception must fail closed; never synthesize positive flags.
    result.automation = false;
  }
  return JSON.stringify(result);
}
run();
""".strip()


_OS_ACTOR_MENU_READ_ONLY_APPLESCRIPT = r"""
on run argv
  if (count of argv) is not 2 then error "exact PID and window required"
  set expectedPidText to item 1 of argv
  if expectedPidText is "" then error "missing PID"
  repeat with digitChar in characters of expectedPidText
    if (contents of digitChar) is not in "0123456789" then error "invalid PID"
  end repeat
  set expectedPid to expectedPidText as integer
  set expectedWindow to item 2 of argv
  tell application "System Events"
    set matches to every application process whose unix id is expectedPid
    if (count of matches) is not 1 then error "Resolve PID changed"
    tell item 1 of matches
      if unix id is not expectedPid then error "Resolve PID changed"
      if bundle identifier is not "com.blackmagic-design.DaVinciResolve" then
        error "Resolve bundle changed"
      end if
      if not frontmost or (count of windows) is not 1 then
        error "Resolve window no longer frontmost/unique"
      end if
      if (name of front window) is not expectedWindow then
        error "Resolve selected window changed"
      end if
      if (value of attribute "AXMain" of front window) is not true then
        error "Resolve main window changed"
      end if
      if (exists sheet 1 of front window) then error "Resolve modal opened"
      set editMenu to menu "Edit" of menu bar 1
      set deselectItem to menu item "Deselect All" of editMenu
      set timelineMenu to menu "Timeline" of menu bar 1
      set autoMenu to menu 1 of menu item "Auto Select" of timelineMenu
      set allOff to menu item "Auto Deselect All Tracks" of autoMenu
      set v1On to menu item "Auto Select/Deselect V1" of autoMenu
      set trimMenu to menu "Trim" of menu bar 1
      set normalMode to menu item "Normal Edit Mode" of trimMenu
      set rollMenu to menu 1 of menu item "Roll" of trimMenu
      set rollItem to menu item "Start to Playhead" of rollMenu
      if not (exists deselectItem) or not (enabled of allOff) or ¬
         not (enabled of v1On) or not (enabled of normalMode) or ¬
         not (exists rollItem) then error "required single-Roll menus unavailable"
      return "READY"
    end tell
  end tell
end run
""".strip()


class OsSnapshot(Protocol):
    def observe(self) -> Mapping[str, object]:
        """Return raw OS observations; no expectation or target assertions."""


class MacResolveForegroundActivator:
    """Focus existing exact Resolve only; not a source of trusted UI state."""

    def activate_existing(self) -> int:
        if platform.system() != "Darwin":
            raise gui.GuiRollRefused("Resolve foreground activation requires macOS")
        try:
            # System Events is an auto-terminating Apple helper: a pristine
            # native render may last longer than its idle lifetime. Without
            # starting the helper in the background, the subsequent no-prompt
            # Automation query returns -600 despite valid Terminal TCC/AX and
            # makes the pinned one-use GUI operation fail prematurely. This
            # ONLY brings up System Events, not Resolve or a media project;
            # the existing OS actor still independently requires the exact
            # running Resolve PID, installed build, TCC 0 and foreground readback.
            helper = subprocess.run(
                ["/usr/bin/open", "-g", "-a", "System Events"],
                check=False,
                text=True,
                capture_output=True,
                timeout=5,
            )
            if helper.returncode != 0:
                raise gui.GuiRollRefused("System Events helper unavailable")
            completed = subprocess.run(
                [
                    "/usr/bin/osascript",
                    "-l",
                    "JavaScript",
                    "-e",
                    _FOREGROUND_EXISTING_JXA,
                ],
                check=False,
                text=True,
                capture_output=True,
                timeout=8,
            )
            if completed.returncode != 0 or len(completed.stdout) > 256:
                raise gui.GuiRollRefused("Resolve foreground activation failed")
            outcome = json.loads(completed.stdout)
            if (
                not isinstance(outcome, dict)
                or set(outcome) != {"activated", "processPid"}
                or outcome["activated"] is not True
                or type(outcome["processPid"]) is not int
                or outcome["processPid"] <= 0
            ):
                raise gui.GuiRollRefused("Resolve foreground activation refused")
            return outcome["processPid"]
        except (OSError, subprocess.TimeoutExpired, ValueError) as error:
            raise gui.GuiRollRefused(
                "Resolve foreground activation unavailable"
            ) from error


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
        if snapshot.get("trimRollMenu") is not False:
            raise gui.GuiRollRefused("menu readiness must come from the fixed actor")
        # The no-prompt TCC/AX query above must succeed *before* another
        # System Events actor. This fixed, read-only AppleScript checks the
        # very same named setup menus the pinned one-Roll actuator will use.
        # It binds PID, bundle, frontmost, exact window, AXMain and no modal,
        # rather than trusting inaccessible Qt checkmarks or setting a flag.
        if (
            snapshot.get("automation") is True
            and snapshot.get("accessibility") is True
            and type(snapshot.get("processPid")) is int
            and snapshot.get("processPid") == snapshot.get("frontmostPid")
            and type(snapshot.get("windowName")) is str
            and snapshot.get("windowFrontmost") is True
            and snapshot.get("modalPresent") is False
        ):
            try:
                menus = subprocess.run(
                    [
                        "/usr/bin/osascript",
                        "-l",
                        "AppleScript",
                        "-e",
                        _OS_ACTOR_MENU_READ_ONLY_APPLESCRIPT,
                        str(snapshot["processPid"]),
                        snapshot["windowName"],
                    ],
                    check=False,
                    text=True,
                    capture_output=True,
                    timeout=12,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                raise gui.GuiRollRefused(
                    "read-only actor menu preflight unavailable"
                ) from error
            snapshot["trimRollMenu"] = (
                menus.returncode == 0 and menus.stdout.strip() == "READY"
            )
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
    # The reviewed #503 actor sends only menus, no keyboard events. Qt's
    # missing effective shortcut characters are diagnostics, not permission
    # to infer them and not a required input to one-use menu-only dispatch.
    if name in {"keyboardFocus", "keyboardNudge"} and (
        value is None or type(value) is str
    ):
        return value
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
        "normalEditMode": bool,
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
        and gui._safe_name(observation["processName"])
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
        # Copy the independently observed name. Never manufacture `Resolve`
        # from the bundle, frontmost PID or a matching window title: the
        # actuator currently targets the named System Events process.
        frontmost_process=observation["frontmostProcess"],
        process_pid=observation["processPid"],
        front_window_name=observation["windowName"],
        accessibility_trusted=observation["accessibility"],
        automation_trusted=observation["automation"],
        modal_present=observation["modalPresent"],
        edit_page=observation["editPage"],
        timeline_focused=observation["timelineFocused"],
        v1_only=observation["v1Only"],
        normal_edit_mode=observation["normalEditMode"],
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
    activated_pid = MacResolveForegroundActivator().activate_existing()
    snapshot = MacReadOnlyObserver().observe()
    gui._require(
        type(snapshot.get("processPid")) is int
        and snapshot["processPid"] == activated_pid,
        "Resolve process changed after foreground activation",
    )
    readiness = _readiness_from_os(snapshot, intent.target)
    gui._validate(intent, inventory, readiness, datetime.now(UTC))
    # Independent SDK→OS→SDK bracket: a page/selected target/playhead/UID
    # change in the OS observation window invalidates the one-use intent.
    # The second SDK pass rereads the signed session and ALL 11 native item
    # UIDs, six tracks and 327 playhead, rather than trusting the first data.
    intent_after, inventory_after = stage.prepare_owned_f1_inputs(
        store, job_id, resolve
    )
    gui._require(
        inventory_after == inventory
        and intent_after == replace(intent, expires_at=intent_after.expires_at),
        "original signed SDK target or one-use stage changed during OS preflight",
    )
    gui._validate(intent_after, inventory_after, readiness, datetime.now(UTC))
    # A second SDK read must not renew a previously issued one-use deadline.
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
