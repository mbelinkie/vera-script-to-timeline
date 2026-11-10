"""Qualified #499 M4 GUI seam: signed helper only, no AppleEvents fallback.

The owning host verifies immutable case, pristine receipt, Edit page, frame
351 and SDK identity. The GUI helper performs fixed focus, inspection and
exactly one Roll. OS replies remain UNKNOWN until independent edited host.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic, sleep
from typing import Any

from . import resolve_gui_helper_protocol as protocol
from . import resolve_gui_roll as gui
from . import resolve_test_bench_carrier as carrier
from . import resolve_test_bench_gui_stage as stage
from . import resolve_test_bench_helper_transport as transport
from . import resolve_test_bench_ui_readiness as ui
from . import resolve_test_queue as queue
from . import resolve_test_queue_m4 as m4


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise gui.GuiRollRefused("signed M4 helper: " + reason)


def _sdk_recheck(resolve: Any, intent: gui.GuiRollIntent) -> None:
    gui._require_owner_lock()
    _require(resolve.GetCurrentPage() == "edit", "Edit page drift before GUI effect")
    manager = resolve.GetProjectManager()
    project = manager.GetCurrentProject() if manager is not None else None
    timeline = project.GetCurrentTimeline() if project is not None else None
    _require(
        project is not None
        and timeline is not None
        and project.GetUniqueId() == intent.target.project_uid
        and timeline.GetUniqueId() == intent.target.timeline_uid
        and stage._read_only_playhead_frame(timeline) == gui.AFTER_BOUNDARY
        and datetime.now(UTC) < intent.expires_at,
        "target, frame 351 or original deadline drift",
    )


def prepare_owned_helper_readiness(
    store: queue.Store,
    job_id: str,
    resolve: Any,
    desktop: transport.SignedHelperDesktop,
) -> tuple[gui.GuiRollIntent, gui.PristineSdkInventory, gui.TrustedUiReadiness]:
    """Trusted SDK → helper focus → helper read-only menu → SDK bracket."""
    ui._ATTESTED.set(None)
    gui._require_owner_lock()
    intent, inventory = stage.prepare_owned_f1_inputs(store, job_id, resolve)
    _require(desktop.actor_pin == intent.actor_pin, "case helper actor pin differs")
    pid = desktop.resolve_pid()  # actual macOS process-executable census
    focus = desktop.focus(
        job_id, intent.stage_operation_id, pid, intent.target.expected_window_name
    )
    inspected = desktop.focus(
        job_id,
        intent.stage_operation_id,
        pid,
        intent.target.expected_window_name,
        operation="inspect",
    )
    _require(focus == inspected, "helper focus and read-only observer differ")
    _require(
        type(focus) is dict
        and set(focus)
        == {
            "resolvePid",
            "bundleIdentifier",
            "windowName",
            "mainWindow",
            "foreground",
            "noModalOrSheet",
            "rollEnabled",
        }
        and type(focus["resolvePid"]) is int
        and focus["resolvePid"] == pid
        and focus["bundleIdentifier"] == gui.RESOLVE_BUNDLE_ID
        and focus["windowName"] == intent.target.expected_window_name
        and all(
            focus[field] is True
            for field in ("mainWindow", "foreground", "noModalOrSheet", "rollEnabled")
        ),
        "exact signed-helper PID/window/foreground/menu evidence missing",
    )
    readiness = gui.TrustedUiReadiness(
        os_name="Darwin",
        resolve_version=gui.RESOLVE_VERSION,
        resolve_bundle_id=focus["bundleIdentifier"],
        frontmost_bundle_id=focus["bundleIdentifier"],
        frontmost_process="signed-helper-observed-resolve",
        process_pid=pid,
        front_window_name=focus["windowName"],
        accessibility_trusted=True,
        automation_trusted=False,
        modal_present=False,
        edit_page=True,
        timeline_focused=False,
        v1_only=False,
        trim_roll_menu_enabled=True,
        nudge_menu_enabled=False,
        keyboard_preset="not-used-by-fixed-menu-helper",
        keyboard_focus_binding=None,
        keyboard_nudge_binding=None,
        helper_proven=True,
    )
    gui._validate(intent, inventory, readiness, datetime.now(UTC))
    after_intent, after_inventory = stage.prepare_owned_f1_inputs(
        store, job_id, resolve
    )
    _require(
        after_inventory == inventory
        and after_intent == replace(intent, expires_at=after_intent.expires_at),
        "signed SDK inventory/session drift during helper observation",
    )
    gui._validate(intent, inventory, readiness, datetime.now(UTC))
    ui._ATTESTED.set((intent, inventory, readiness, monotonic()))
    return intent, inventory, readiness


class HelperRollExecutor:
    """One preauthenticated case, one owner-held signed-helper spool request."""

    def __init__(
        self,
        store: queue.Store,
        job_id: str,
        intent: gui.GuiRollIntent,
        desktop: transport.SignedHelperDesktop,
        *,
        case_root: Path,
        authority: Mapping[str, Any],
    ) -> None:
        self.store = store
        self.job_id = job_id
        self.intent = intent
        self.desktop = desktop
        self.case_root = case_root
        self.authority = dict(authority)

    def execute_once(self, expected_window_name: str, process_pid: int) -> None:
        _require(gui._CONSUMED_DISPATCH.get() is True, "journal not consumed")
        gui._require_owner_lock()
        verified = gui._VERIFIED_HOST_DISPATCH.get()
        _require(
            verified is not None
            and verified[0] == expected_window_name
            and verified[1] == process_pid
            and self.intent.target.expected_window_name == expected_window_name,
            "original target not SDK/OS-attested for this dispatch",
        )
        assert verified is not None
        verified[2]()  # post-journal SDK recheck; refusal is UNKNOWN, not retry
        root_record = json.loads(
            carrier._read(self.case_root / "complete-loop-intent.json", 32768)
        )
        auth_sha = hashlib.sha256(queue.canonical(self.authority)).hexdigest()
        _require(
            type(root_record) is dict
            and root_record.get("authority", {}).get("sha256") == auth_sha
            and root_record.get("sourceGraphSha256")
            == self.authority.get("sourceGraphSha256")
            and self.authority.get("actorPin") == self.intent.actor_pin
            and self.authority.get("initialTarget")
            == stage._target_dict(self.intent.target),
            "fresh immutable case/root/source/actor authority differs",
        )
        # Read the EXACT already consumed journal, not another caller's digest.
        path = m4._jobdir(self.store, self.job_id) / "f1-gui-edit" / "gui-intent.json"
        journal = carrier._read(path, 32768)
        record = json.loads(journal)
        _require(
            queue.canonical(record) == journal
            and record.get("jobId") == self.job_id
            and record.get("operationId") == self.intent.stage_operation_id
            and record.get("actorPin") == self.intent.actor_pin,
            "canonical same-operation one-use journal differs",
        )
        _require(
            self.desktop.actor_pin == self.intent.actor_pin,
            "installed helper process pin differs at dispatch",
        )
        deadline = min(
            self.intent.expires_at, datetime.now(UTC) + timedelta(seconds=60)
        )
        _require(datetime.now(UTC) < deadline, "no unexpired helper deadline")
        digest = hashlib.sha256(
            (self.job_id + ":" + self.intent.stage_operation_id).encode()
        ).hexdigest()[:32]
        request = {
            "schema": protocol.REQUEST_SCHEMA,
            "requestId": "roll-" + digest,
            "deadlineAt": deadline.isoformat().replace("+00:00", "Z"),
            "operation": protocol.OPERATION,
            "jobId": self.job_id,
            "stageOperationId": self.intent.stage_operation_id,
            "fixtureId": protocol.FIXTURE,
            "trialId": "trial-"
            + hashlib.sha256((self.job_id + auth_sha).encode()).hexdigest()[:24],
            "resolvePid": process_pid,
            "windowName": expected_window_name,
            "projectUid": self.intent.target.project_uid,
            "timelineUid": self.intent.target.timeline_uid,
            "sourceGraphSha256": self.authority["sourceGraphSha256"],
            "actorPin": self.intent.actor_pin,
            "pristineCaptureSha256": self.intent.pristine_capture_sha256,
            "oneUseIntentSha256": hashlib.sha256(journal).hexdigest(),
            "authoritySha256": auth_sha,
        }
        protocol.validate_request(queue.canonical(request), installed=True)
        self.desktop.roll(request)
        # A helper 'dispatched-unknown' means no claim of native edit success.


def dispatch_owned_helper_f1_once(
    store: queue.Store,
    job_id: str,
    resolve: Any,
    *,
    case_root: Path,
    authority: Mapping[str, Any],
) -> gui.GuiRollAttempt:
    """The ONLY qualified production GUI path; no legacy dependency."""
    gui._require_owner_lock()
    actor_pin = stage.helper_actor_pin_from_authority(store, job_id)
    desktop = transport.SignedHelperDesktop(actor_pin)
    intent, inventory, readiness = prepare_owned_helper_readiness(
        store, job_id, resolve, desktop
    )
    _sdk_recheck(resolve, intent)
    ui._consume_attested_ui_readiness(intent, inventory, readiness)
    scope = gui._VERIFIED_HOST_DISPATCH.set(
        (
            intent.target.expected_window_name,
            readiness.process_pid,
            lambda: _sdk_recheck(resolve, intent),
        )
    )
    try:
        return gui.OneUseGuiRollActuator(
            stage.OriginalM4GuiJournal(store, job_id),
            HelperRollExecutor(
                store,
                job_id,
                intent,
                desktop,
                case_root=case_root,
                authority=authority,
            ),
        ).attempt(intent, inventory, readiness)
    finally:
        gui._VERIFIED_HOST_DISPATCH.reset(scope)


def observe_settled_edited_geometry(
    store: queue.Store, job_id: str, resolve: Any, *, max_seconds: float = 12.0
) -> None:
    """Bounded read-only SDK settle *under the original owner lock*.

    Unchanged pristine geometry can settle; any different geometry that is not
    exactly the expected two-UID Roll is terminal UNKNOWN. Never redispatch.
    This is not a substitute for the subsequent independent save/reopen host.
    """
    from .qualification_output_native_v2 import verify_native_result

    gui._require_owner_lock()
    _require(0 < max_seconds <= 30, "invalid bounded observation window")
    pristine = m4._stage_receipt(store, job_id, 0)
    record = verify_native_result(
        Path(pristine["capture"]["path"]), pristine["capture"]["sha256"]
    )
    graph = record["nativeGeometry"]
    tracks = graph["tracks"]
    original = {row["itemUid"]: row for row in graph["items"]}
    _require(
        len(original) == gui.NATIVE_ITEM_COUNT
        and len(tracks) == gui.NATIVE_TRACK_COUNT,
        "original signed geometry is malformed",
    )
    # Identify the unique original V1 327 cut from signed geometry, never
    # choose an arbitrary clip pair based on the current edited state.
    v1 = [row for row in tracks if row.get("kind") == "video" and row.get("index") == 1]
    _require(len(v1) == 1, "signed V1 track is missing/ambiguous")
    first = [
        row
        for row in graph["items"]
        if row.get("trackId") == v1[0]["trackId"]
        and row.get("kind") == "video"
        and row.get("recordStart") == 0
        and row.get("recordDuration") == gui.BEFORE_BOUNDARY
    ]
    second = [
        row
        for row in graph["items"]
        if row.get("trackId") == v1[0]["trackId"]
        and row.get("kind") == "video"
        and row.get("recordStart") == gui.BEFORE_BOUNDARY
        and row.get("recordDuration") == 151
    ]
    _require(
        len(first) == len(second) == 1 and first[0]["itemUid"] != second[0]["itemUid"],
        "unique authenticated V1 327 cut missing",
    )
    left, right = first[0]["itemUid"], second[0]["itemUid"]
    deadline = monotonic() + max_seconds
    while monotonic() < deadline:
        _require(resolve.GetCurrentPage() == "edit", "Edit page drift after dispatch")
        manager = resolve.GetProjectManager()
        project = manager.GetCurrentProject() if manager is not None else None
        timeline = project.GetCurrentTimeline() if project is not None else None
        _require(
            project is not None
            and timeline is not None
            and project.GetUniqueId() == record["target"]["projectUid"]
            and timeline.GetUniqueId() == record["target"]["timelineUid"],
            "native UID/page drift after dispatch",
        )
        assert timeline is not None
        observed: dict[str, tuple[int, int]] = {}
        for spec in tracks:
            kind, index = spec["kind"], spec["index"]
            _require(
                timeline.GetTrackCount(kind) == (5 if kind == "video" else 1),
                "native track-count drift after dispatch",
            )
            _require(
                timeline.GetTrackName(kind, index) == spec["name"]
                and timeline.GetIsTrackEnabled(kind, index) == spec["enabled"]
                and timeline.GetIsTrackLocked(kind, index) == spec["locked"],
                "native track state drift after dispatch",
            )
            items = timeline.GetItemListInTrack(kind, index)
            _require(
                type(items) in {list, tuple} and len(items) <= gui.NATIVE_ITEM_COUNT,
                "missing or oversized native track items",
            )
            for item in items:
                uid = item.GetUniqueId()
                _require(
                    type(uid) is str and uid in original and uid not in observed,
                    "new, aliased or duplicate item UID after dispatch",
                )
                start, duration = item.GetStart(False), item.GetDuration(False)
                _require(
                    type(start) is int and type(duration) is int,
                    "native geometry type drift after dispatch",
                )
                observed[uid] = (start, duration)
        _require(set(observed) == set(original), "missing native UID after dispatch")
        pending = False
        for uid, row in original.items():
            old = (row["recordStart"], row["recordDuration"])
            new = (
                (0, gui.AFTER_BOUNDARY)
                if uid == left
                else (gui.AFTER_BOUNDARY, 151 - gui.ROLL_FRAMES)
                if uid == right
                else old
            )
            actual = observed[uid]
            if actual == old and uid in {left, right}:
                pending = True
            elif actual != new:
                raise gui.GuiRollUnknown("unexpected native geometry; no Roll retry")
        if not pending:
            return
        sleep(0.2)
    raise gui.GuiRollUnknown("native Roll geometry did not settle; no retry")
