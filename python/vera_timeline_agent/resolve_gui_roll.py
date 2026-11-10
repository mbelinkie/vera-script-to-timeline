"""#491's bounded F1 GUI *attempt*, not an M4 native edit or verifier.

This is deliberately not a CLI or an independent native operation owner. The
#473 controller must already hold ``resolve_native_owner.native_owner`` and
provide its authenticated, pristine SDK readback and durable one-use journal.
No function here selects a project, saves it, grants TCC, or signs a receipt.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import threading
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

from . import resolve_gui_helper_protocol as helper
from . import resolve_native_owner

ACTUATOR_CLASS: Literal["gui"] = "gui"
OPERATION: Literal["M4.edited"] = "M4.edited"
RESOLVE_VERSION = "21.1.1.10"
RESOLVE_BUNDLE_ID = "com.blackmagic-design.DaVinciResolve"
RESOLVE_PROCESS = "Resolve"
KEYBOARD_PRESET = "DaVinci Resolve"
BEFORE_BOUNDARY = 327
AFTER_BOUNDARY = 351
ROLL_FRAMES: Literal[24] = 24
EXTENT_FRAMES = 1407
EXPECTED_RATE = (24000, 1001)
NATIVE_ITEM_COUNT = 11
NATIVE_TRACK_COUNT = 6
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_CONSUMED_DISPATCH: ContextVar[bool] = ContextVar(
    "f1_consumed_gui_dispatch", default=False
)
# The real System Events transport requires *both* an already-consumed
# one-use journal and an independently SDK→OS→SDK-attested original M4 host.
# A caller-supplied TrustedUiReadiness or a wrapper executor cannot mint this.
_VERIFIED_HOST_DISPATCH: ContextVar[tuple[str, int, Callable[[], None]] | None] = (
    ContextVar("issue499_verified_host_dispatch", default=None)
)
_DISPOSABLE_PROJECT = re.compile(
    r"VERA Delivery [0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12} [0-9a-f]{12}\Z"
)

# One fixed, reviewed menu operation. No caller-supplied script, shell,
# coordinates, target index, edit delta or generic keyboard command is accepted.
# The SDK pins the 327 cut and frame-351 playhead; the actor performs absolute
# track deselection, a single V1 toggle from the known all-off state, whole-
# clip deselection and normal-mode setting before ONE named Roll. Qt's missing
# AXFocused/menu checkmarks are not fabricated by this actor.
ROLL_APPLESCRIPT = r"""
on run argv
  if (count of argv) is not 2 then error "exactly one PID and pinned window required"
  set expectedPidText to item 1 of argv
  if expectedPidText is "" then error "empty process PID"
  repeat with digitChar in characters of expectedPidText
    if (contents of digitChar) is not in "0123456789" then error "invalid process PID"
  end repeat
  set expectedPid to expectedPidText as integer
  if expectedPid <= 0 then error "invalid process PID"
  set expectedProjectWindow to item 2 of argv
  tell application "System Events"
    set matches to every application process whose unix id is expectedPid
    if (count of matches) is not 1 then error "pinned process disappeared"
    tell item 1 of matches
      if unix id is not expectedPid then error "pinned process PID changed"
      if bundle identifier is not "com.blackmagic-design.DaVinciResolve" then
        error "pinned process bundle changed"
      end if
      if not frontmost then error "Resolve is not frontmost"
      if (count of windows) is not 1 then error "unexpected Resolve windows"
      if (name of front window) is not expectedProjectWindow then
        error "Resolve target window differs"
      end if
      if (value of attribute "AXMain" of front window) is not true then
        error "target window is not main"
      end if
      if (exists sheet 1 of front window) then error "Resolve modal is open"
      -- Double official-SDK admission already authenticated Edit, full 11-UID
      -- unchanged pristine geometry and playhead 351. Qt does not expose
      -- reliable page/selected-track/normal-mode AX checkmarks.
      set editMenu to menu "Edit" of menu bar 1
      set deselectItem to menu item "Deselect All" of editMenu
      set timelineMenu to menu "Timeline" of menu bar 1
      set autoMenu to menu 1 of menu item "Auto Select" of timelineMenu
      set allOff to menu item "Auto Deselect All Tracks" of autoMenu
      set v1On to menu item "Auto Select/Deselect V1" of autoMenu
      if not (enabled of allOff) or not (enabled of v1On) then
        error "absolute V1-only track setup unavailable"
      end if
      set trimMenu to menu "Trim" of menu bar 1
      set normalMode to menu item "Normal Edit Mode" of trimMenu
      set rollMenu to menu 1 of menu item "Roll" of trimMenu
      set rollItem to menu item "Start to Playhead" of rollMenu
      if not (enabled of normalMode) then error "normal mode unavailable"
      -- Resolve disables Deselect All when the SDK-proved clip selection is
      -- already empty. It is an idempotent clean-up, not a required enabled
      -- state; missing menu items still throw rather than being assumed.
      if (enabled of deselectItem) then click deselectItem
      click allOff
      -- Reacquire submenu after the absolute setter; the V1 leaf is a
      -- toggle, therefore it is safe ONLY after Auto Deselect All Tracks.
      set autoMenu to menu 1 of menu item "Auto Select" of menu "Timeline" of menu bar 1
      click menu item "Auto Select/Deselect V1" of autoMenu
      click normalMode
      if (enabled of menu item "Deselect All" of menu "Edit" of menu bar 1) then
        click menu item "Deselect All" of menu "Edit" of menu bar 1
      end if
      if unix id is not expectedPid or ¬
         bundle identifier is not "com.blackmagic-design.DaVinciResolve" then
        error "Resolve process identity changed after setup"
      end if
      if not frontmost or (count of windows) is not 1 or ¬
         name of front window is not expectedProjectWindow or ¬
         (value of attribute "AXMain" of front window) is not true or ¬
         (exists sheet 1 of front window) then
        error "Resolve target window/modal changed after setup"
      end if
      -- No ambiguous target retry: exactly one native effect command.
      set trimMenu to menu "Trim" of menu bar 1
      set rollMenu to menu 1 of menu item "Roll" of trimMenu
      set rollItem to menu item "Start to Playhead" of rollMenu
      if not (enabled of rollItem) then error "named Roll unavailable after setup"
      click rollItem
    end tell
  end tell
end run
""".strip()
# Independent, review-pinned digest: edits to the script do not implicitly
# authorize themselves by recalculating the expected value on import.
ROLL_SCRIPT_SHA256 = "9595f41eb5a943e245628d0f537aead0e6cc49447554294153aa7281314c0845"


class GuiRollRefused(ValueError):
    """No GUI executor call was made; the adapter's admission gate rejected it."""


class GuiRollUnknown(RuntimeError):
    """A one-use intent may have affected Resolve; no replay is allowed."""


@dataclass(frozen=True, slots=True)
class NativeTarget:
    project_uid: str
    project_name: str
    timeline_uid: str
    timeline_name: str
    expected_window_name: str


@dataclass(frozen=True, slots=True)
class PristineSdkInventory:
    """A #473 independently verified SDK observation, not a GUI observation."""

    target: NativeTarget
    capture_sha256: str
    item_uids: tuple[str, ...]
    left_item_uid: str
    right_item_uid: str
    left_track_id: str
    right_track_id: str
    left_track_kind: str
    right_track_kind: str
    left_track_index: int
    right_track_index: int
    left_record_start: int
    left_record_duration: int
    right_record_start: int
    right_record_duration: int
    boundary_frame: int
    playhead_frame: int
    track_count: int
    extent_frames: int
    rate: tuple[int, int]
    pristine_verified: bool


@dataclass(frozen=True, slots=True)
class GuiRollIntent:
    """A *reference* to #473's pre-existing authority, never a new token."""

    actuator_class: Literal["gui"]
    operation: Literal["M4.edited"]
    stage_operation_id: str
    target: NativeTarget
    pristine_capture_sha256: str
    item_uids: tuple[str, ...]
    left_item_uid: str
    right_item_uid: str
    actor_pin: dict[str, object]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class TrustedUiReadiness:
    """Read-only checks supplied by the authenticated #473 host preflight."""

    os_name: str
    resolve_version: str
    resolve_bundle_id: str
    frontmost_bundle_id: str
    frontmost_process: str
    process_pid: int
    front_window_name: str
    accessibility_trusted: bool
    automation_trusted: bool
    modal_present: bool
    edit_page: bool
    timeline_focused: bool
    v1_only: bool
    trim_roll_menu_enabled: bool
    nudge_menu_enabled: bool
    keyboard_preset: str
    keyboard_focus_binding: str | None
    keyboard_nudge_binding: str | None
    normal_edit_mode: bool = False
    # True is useful only with the privately attested signed-helper transport.
    # A caller-created dataclass never authorizes its own native effect.
    helper_proven: bool = False


@dataclass(frozen=True, slots=True)
class GuiRollAttempt:
    """An OS command was attempted; SDK/native outcome is ALWAYS unknown."""

    state: Literal["unknown"]
    actuator_class: Literal["gui"]
    stage_operation_id: str
    named_roll_commands: Literal[1]
    native_verified: Literal[False]
    receipt_issued: Literal[False]


class ExistingOneUseJournal(Protocol):
    def consume_before_effect(self, intent: GuiRollIntent) -> bool:
        """Atomically persist the EXISTING owner-verified intent, reject replay.

        Return True only after durable consumption; errors/False fail closed.
        The #473 owner must validate the stage/operation and journal itself.
        """


class FixedRollExecutor(Protocol):
    def execute_once(self, expected_window_name: str, process_pid: int) -> None:
        """Attempt exactly one fixed, reviewed named Roll plus deterministic setup."""


class SystemEventsRollExecutor:
    """Opt-in production executor. Never instantiated by the adapter/tests."""

    def execute_once(self, expected_window_name: str, process_pid: int) -> None:
        # This is NOT a second invocation path: a direct call cannot operate
        # without the actuator's already-consumed journal and current lock.
        _require(_CONSUMED_DISPATCH.get(), "no consumed F1 dispatch")
        _require_owner_lock()
        verified = _VERIFIED_HOST_DISPATCH.get()
        _require(
            verified is not None
            and verified[0] == expected_window_name
            and verified[1] == process_pid,
            "no independently attested original-M4 host transport",
        )
        assert verified is not None
        _require(
            hashlib.sha256(ROLL_APPLESCRIPT.encode("utf-8")).hexdigest()
            == ROLL_SCRIPT_SHA256,
            "reviewed GUI script changed before OS dispatch",
        )
        # Historical System Events transport is permanently ineligible for the
        # new versioned helper authority. This cannot execute a consumed case.
        raise GuiRollRefused("legacy System Events actuator has no helper authority")
        # An argv value, not interpolated into AppleScript or a shell string.
        # Subprocess exit 0 says nothing about the *native* result.
        if not _safe_name(expected_window_name):
            raise GuiRollRefused("invalid fixed window name")
        _require(type(process_pid) is int and process_pid > 0, "invalid exact PID")
        # Re-read the same selected SDK target/page/playhead immediately
        # before launching osascript. A late drift *after* journal fsync is
        # UNKNOWN and may NEVER be retried.
        verified[2]()
        try:
            result = subprocess.run(
                [
                    "/usr/bin/osascript",
                    "-e",
                    ROLL_APPLESCRIPT,
                    str(process_pid),
                    expected_window_name,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=90,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise GuiRollUnknown(
                "GUI result unknown; inspect without replay"
            ) from error
        if result.returncode != 0:
            raise GuiRollUnknown("GUI result unknown; inspect without replay")


def _safe_name(value: object) -> bool:
    return (
        type(value) is str
        and 0 < len(value) <= 160
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise GuiRollRefused("#491 F1 GUI roll refused: " + reason)


def _require_owner_lock() -> None:
    """Fail without the CURRENT #473 native-owner context, never acquire anew."""
    descriptor = resolve_native_owner._HELD_OWNER_FD.get()
    _require(descriptor is not None, "shared native owner not held")
    assert descriptor is not None
    resolve_native_owner._validate_inherited_owner(descriptor)


def _validate(
    intent: GuiRollIntent,
    inventory: PristineSdkInventory,
    readiness: TrustedUiReadiness,
    now: datetime,
) -> None:
    target = intent.target
    _require(
        intent.actuator_class == ACTUATOR_CLASS and intent.operation == OPERATION,
        "not the single approved M4 edited GUI operation",
    )
    _require(
        type(intent.stage_operation_id) is str
        and bool(re.fullmatch(r"[a-zA-Z0-9_-]{8,128}", intent.stage_operation_id)),
        "missing authenticated stage operation identifier",
    )
    _require(
        all(
            _safe_name(v)
            for v in (
                target.project_uid,
                target.project_name,
                target.timeline_uid,
                target.timeline_name,
                target.expected_window_name,
            )
        ),
        "target identity invalid",
    )
    _require(
        bool(_DISPOSABLE_PROJECT.fullmatch(target.project_name))
        and target.timeline_name == target.project_name
        and target.expected_window_name == target.project_name,
        "not an exact fresh disposable project/window/timeline",
    )
    _require(
        type(intent.pristine_capture_sha256) is str
        and bool(_HEX64.fullmatch(intent.pristine_capture_sha256))
        and intent.pristine_capture_sha256 == inventory.capture_sha256,
        "authenticated pristine receipt differs",
    )
    _require(
        _valid_actor_pin(intent.actor_pin),
        "versioned helper source/signing identity differs",
    )
    _require(
        intent.target == inventory.target and inventory.pristine_verified is True,
        "verified original selected SDK target missing",
    )
    _require(
        type(inventory.item_uids) is tuple
        and type(intent.item_uids) is tuple
        and len(inventory.item_uids) == NATIVE_ITEM_COUNT
        and len(set(inventory.item_uids)) == NATIVE_ITEM_COUNT
        and all(_safe_name(uid) for uid in inventory.item_uids)
        and intent.item_uids == inventory.item_uids,
        "all original eleven native UIDs must match",
    )
    _require(
        intent.left_item_uid == inventory.left_item_uid
        and intent.right_item_uid == inventory.right_item_uid
        and intent.left_item_uid in inventory.item_uids
        and intent.right_item_uid in inventory.item_uids
        and intent.left_item_uid != intent.right_item_uid,
        "original left/right native item UIDs differ",
    )
    _require(
        inventory.left_track_id == inventory.right_track_id
        and _safe_name(inventory.left_track_id)
        and inventory.left_track_kind == inventory.right_track_kind == "video"
        and type(inventory.left_track_index) is int
        and type(inventory.right_track_index) is int
        and inventory.left_track_index == inventory.right_track_index == 1,
        "not the original V1-only boundary",
    )
    _require(
        all(
            type(value) is int
            for value in (
                inventory.left_record_start,
                inventory.left_record_duration,
                inventory.right_record_start,
                inventory.right_record_duration,
                inventory.boundary_frame,
                inventory.playhead_frame,
                inventory.extent_frames,
                inventory.track_count,
            )
        )
        and inventory.left_record_start == 0
        and inventory.left_record_duration == BEFORE_BOUNDARY
        and inventory.right_record_start == BEFORE_BOUNDARY
        and inventory.right_record_duration == 151
        and inventory.boundary_frame == BEFORE_BOUNDARY
        and inventory.playhead_frame == AFTER_BOUNDARY
        and inventory.extent_frames == EXTENT_FRAMES
        and inventory.track_count == NATIVE_TRACK_COUNT
        and inventory.rate == EXPECTED_RATE,
        "original 327 cut, SDK frame 351 playhead, six-track inventory differs",
    )
    _require(
        type(now) is datetime
        and now.tzinfo is not None
        and type(intent.expires_at) is datetime
        and intent.expires_at.tzinfo is not None
        and now < intent.expires_at,
        "one-use intent is expired or time invalid",
    )
    _require(
        readiness.os_name == "Darwin"
        and readiness.resolve_version == RESOLVE_VERSION
        and readiness.resolve_bundle_id == RESOLVE_BUNDLE_ID
        and readiness.frontmost_bundle_id == RESOLVE_BUNDLE_ID
        and _safe_name(readiness.frontmost_process)
        and type(readiness.process_pid) is int
        and readiness.process_pid > 0
        and readiness.front_window_name == target.expected_window_name,
        "installed Resolve version, app identity, focus or window differs",
    )
    _require(
        readiness.accessibility_trusted is True
        and (readiness.helper_proven is True or readiness.automation_trusted is True)
        and readiness.modal_present is False
        and readiness.trim_roll_menu_enabled is True,
        "helper Accessibility or named Roll/setup menu preflight denied",
    )
    _require(
        readiness.helper_proven is True or readiness.keyboard_preset == KEYBOARD_PRESET,
        "unexpected preset provenance",
    )


def _valid_actor_pin(value: object) -> bool:
    try:
        helper.validate_actor_pin(value)
    except helper.HelperProtocolError:
        return False
    return True


class OneUseGuiRollActuator:
    """One possible OS dispatch; even a crash/timeout irrevocably spends it."""

    def __init__(self, journal: ExistingOneUseJournal, executor: FixedRollExecutor):
        self._journal = journal
        self._executor = executor
        self._spent = False
        self._guard = threading.Lock()

    def attempt(
        self,
        intent: GuiRollIntent,
        inventory: PristineSdkInventory,
        readiness: TrustedUiReadiness,
        *,
        now: datetime | None = None,
    ) -> GuiRollAttempt:
        with self._guard:
            _require(not self._spent, "this actuator has already been dispatched")
            if isinstance(self._executor, SystemEventsRollExecutor):
                _require(
                    _VERIFIED_HOST_DISPATCH.get() is not None,
                    "no independently attested original-M4 host transport",
                )
            _validate(
                intent, inventory, readiness, datetime.now(UTC) if now is None else now
            )
            _require_owner_lock()
            # Mark local attempt spent even if journal I/O dies ambiguously.
            self._spent = True
            try:
                consumed = self._journal.consume_before_effect(intent)
            except Exception as error:
                raise GuiRollUnknown(
                    "one-use journal unknown; no GUI dispatch"
                ) from error
            _require(consumed is True, "one-use intent already spent or not authorized")
            dispatch_scope = _CONSUMED_DISPATCH.set(True)
            try:
                self._executor.execute_once(
                    intent.target.expected_window_name, readiness.process_pid
                )
            except Exception as error:
                raise GuiRollUnknown(
                    "GUI attempt uncertain; no retry, save, or acceptance"
                ) from error
            finally:
                _CONSUMED_DISPATCH.reset(dispatch_scope)
            # An OS process exit 0 is not a native SDK observation.
            return GuiRollAttempt(
                state="unknown",
                actuator_class=ACTUATOR_CLASS,
                stage_operation_id=intent.stage_operation_id,
                named_roll_commands=1,
                native_verified=False,
                receipt_issued=False,
            )
