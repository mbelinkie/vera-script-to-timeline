"""One-use guarded Resolve Studio UI roll: the exact 327→351 held-picture edit.

Never an alternative v2 host or a source rewrite. Run only after a genuine
pristine M4 receipt is independently verified, all other Resolve owners have
released, and the *original* disposable project is already selected. An
immutable edit intent precedes changing even the playhead. No replay or
cleanup-on-failure: the original project, IDs and partially edited target are
retained for investigation. Only the original v2 host can subsequently capture
and qualify this candidate; success here alone is NOT an M4 acceptance.

Studio 21.1.1 lacks a qualified native roll-edit setter. The shipped Edit
Page supports Command-4 (focus timeline), V (select nearest edit point) and
period (roll one frame right). This script operates the UI exactly once with
24 physical period key events, then independently reads all native items,
source frames, links and settings before allowing SaveProject.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any

ALLOWED_ROOTS = frozenset(
    {
        Path.home() / f".local/state/vera/issue-473-studio-{index:02d}"
        for index in (5, 7)
    }
)
START_FRAME = 327
END_FRAME = 351
UI_SCHEMA = "vera.issue473-native-roll-intent/v1"
NATIVE_ITEM_FIELDS = frozenset(
    {
        "itemUid",
        "trackId",
        "kind",
        "recordStart",
        "recordDuration",
        "sourceStart",
        "sourceDuration",
        "mediaUid",
        "linkedItemUids",
        "marker",
    }
)


def need(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError("#473 guarded roll refused: " + message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pair(rows: Mapping[str, Mapping[str, Any]]) -> tuple[str, str]:
    lefts = [
        row
        for row in rows.values()
        if row.get("kind") == "video"
        and type(row.get("recordStart")) is int
        and type(row.get("recordDuration")) is int
        and row["recordStart"] + row["recordDuration"] == START_FRAME
    ]
    need(len(lefts) == 1, "original 327 left boundary item is ambiguous")
    left = lefts[0]
    rights = [
        row
        for row in rows.values()
        if row.get("kind") == "video"
        and row.get("recordStart") == START_FRAME
        and row.get("trackId") == left.get("trackId")
        and row.get("itemUid") != left.get("itemUid")
        and type(row.get("recordDuration")) is int
        and row["recordDuration"] > END_FRAME - START_FRAME
    ]
    need(len(rights) == 1, "original 327 right boundary item is ambiguous")
    left_uid, right_uid = left["itemUid"], rights[0]["itemUid"]
    need(
        type(left_uid) is str
        and bool(left_uid)
        and type(right_uid) is str
        and bool(right_uid)
        and left_uid != right_uid,
        "actual boundary UID is invalid",
    )
    return left_uid, right_uid


def _expect_geometry(geometry: Any) -> dict[str, dict[str, Any]]:
    need(isinstance(geometry, dict), "authenticated native geometry missing")
    need(
        geometry.get("rate") == {"numerator": 24000, "denominator": 1001}
        and type(geometry.get("extentFrames")) is int
        and geometry["extentFrames"] == 1407,
        "wrong source/native rational-rate programme",
    )
    tracks, items = geometry.get("tracks"), geometry.get("items")
    need(
        isinstance(tracks, list)
        and len(tracks) == 6
        and isinstance(items, list)
        and len(items) == 11,
        "original six-track eleven-item geometry missing",
    )
    assert isinstance(items, list)
    rows: dict[str, dict[str, Any]] = {}
    for item in items:
        need(isinstance(item, dict), "invalid native item")
        uid = item.get("itemUid")
        need(
            isinstance(uid, str) and bool(uid) and uid not in rows,
            "missing or repeated native item UID",
        )
        assert isinstance(uid, str)
        rows[uid] = item
    left_uid, right_uid = _pair(rows)
    left, right = rows[left_uid], rows[right_uid]
    need(
        left.get("kind") == right.get("kind") == "video"
        and left.get("trackId") == right.get("trackId")
        and left.get("recordStart") == 0
        and left.get("recordDuration") == START_FRAME
        and right.get("recordStart") == START_FRAME
        and right.get("recordDuration") == 151
        and left.get("sourceStart") == right.get("sourceStart") == 0,
        "original native held-picture boundary geometry differs",
    )
    return rows


def _selected(resolve: Any, target: Mapping[str, str]) -> tuple[Any, Any, Any]:
    manager = resolve.GetProjectManager()
    need(manager is not None, "Resolve project manager unavailable")
    project = manager.GetCurrentProject()
    timeline = project.GetCurrentTimeline() if project else None
    need(project is not None and timeline is not None, "no selected native target")
    need(
        project.GetUniqueId() == target["projectUid"]
        and project.GetName() == target["projectName"]
        and timeline.GetUniqueId() == target["timelineUid"]
        and timeline.GetName() == target["timelineName"],
        "actual selected project/timeline UID or name differs",
    )
    need(project.IsRenderingInProgress() is False, "selected target still rendering")
    return manager, project, timeline


def snapshot(
    resolve: Any, target: Mapping[str, str], geometry: Mapping[str, Any]
) -> dict[str, Any]:
    """Independently observe the SDK; never patch or infer any native metadata."""
    from vera_timeline_agent.qualification_output_native_v2 import (
        _source_time_error_samples,
    )

    _expect_geometry(geometry)
    _manager, _project, timeline = _selected(resolve, target)
    tracks = geometry["tracks"]
    expected_track = {(row["kind"], row["index"]): row for row in tracks}
    observed: dict[str, dict[str, Any]] = {}
    for kind in ("video", "audio", "subtitle"):
        count = timeline.GetTrackCount(kind)
        need(
            type(count) is int
            and count == max((i for k, i in expected_track if k == kind), default=0),
            "native track count changed",
        )
        for index in range(1, count + 1):
            spec = expected_track.get((kind, index))
            need(spec is not None, "new or foreign native track")
            assert spec is not None
            need(
                timeline.GetTrackName(kind, index) == spec["name"]
                and timeline.GetIsTrackEnabled(kind, index) == spec["enabled"]
                and timeline.GetIsTrackLocked(kind, index) == spec["locked"],
                "native track state changed",
            )
            items = timeline.GetItemListInTrack(kind, index)
            need(
                isinstance(items, (list, tuple)) and len(items) <= 32,
                "invalid native item inventory",
            )
            for item in items:
                uid = item.GetUniqueId()
                need(
                    isinstance(uid, str) and uid not in observed,
                    "replaced or duplicate native item UID",
                )
                media = item.GetMediaPoolItem()
                links = item.GetLinkedItems()
                need(
                    media is not None and isinstance(links, (list, tuple)),
                    "unreadable native source or links",
                )
                src_start = item.GetSourceStartFrame()
                src_end = item.GetSourceEndFrame()
                rec_start = item.GetStart(False)
                rec_duration = item.GetDuration(False)
                need(
                    all(
                        type(x) is int
                        for x in (src_start, src_end, rec_start, rec_duration)
                    )
                    and src_end >= src_start
                    and rec_duration > 0,
                    "native item frame getters invalid",
                )
                # Studio stills can report an arbitrary nonzero single-frame
                # counter, which the original #472 native verifier correctly
                # normalizes only after verifying independent source-time
                # getters, single-frame media and approved still FPS.
                # Retain the original raw frame counters separately and demand
                # that both stay unchanged during this one-use UI edit.
                expected_rows = _expect_geometry(geometry)
                baseline = expected_rows.get(uid)
                candidate_held = (
                    kind == "video"
                    and baseline is not None
                    and baseline.get("sourceStart") == 0
                    and baseline.get("sourceDuration") == baseline.get("recordDuration")
                    and src_start == src_end
                    and src_start >= 0
                )
                is_held = False
                if candidate_held:
                    props = media.GetClipProperty()
                    need(
                        isinstance(props, dict)
                        and props.get("Frames") == "1"
                        and props.get("Online Status") == "Online",
                        "held media lacks authentic online single-frame properties",
                    )
                    raw_fps = props.get("FPS")
                    fps_period: Fraction | None = None
                    if type(raw_fps) in {str, int, float}:
                        try:
                            fps = Decimal(str(raw_fps))
                            if fps.is_finite() and fps > 0:
                                fps_period = Fraction(1, 1) / Fraction(fps)
                        except (InvalidOperation, ZeroDivisionError):
                            pass
                    start_time = getattr(item, "GetSourceStartTime", None)
                    end_time = getattr(item, "GetSourceEndTime", None)
                    need(
                        callable(start_time) and callable(end_time),
                        "held single-frame source time getters are unavailable",
                    )
                    start_error = _source_time_error_samples(
                        start_time(), 0, Fraction(1)
                    )
                    timeline_end_error = _source_time_error_samples(
                        end_time(), 1, Fraction(1001, 24000)
                    )
                    still_end_error = (
                        _source_time_error_samples(end_time(), 1, fps_period)
                        if fps_period is not None
                        else None
                    )
                    need(
                        start_error is not None
                        and abs(start_error) <= 1
                        and (
                            (
                                timeline_end_error is not None
                                and abs(timeline_end_error) <= 1
                            )
                            or (
                                still_end_error is not None
                                and abs(still_end_error) <= 1
                            )
                        ),
                        "held still source-time edges differ from admitted frame",
                    )
                    is_held = True
                observed[uid] = {
                    "itemUid": uid,
                    "trackId": spec["trackId"],
                    "kind": kind,
                    "recordStart": rec_start,
                    "recordDuration": rec_duration,
                    "sourceStart": 0 if is_held else src_start,
                    "sourceDuration": (
                        rec_duration
                        if is_held
                        else src_end - src_start + (kind == "audio")
                    ),
                    "sourceStartGetter": src_start,
                    "sourceEndGetter": src_end,
                    "mediaUid": media.GetUniqueId(),
                    "linkedItemUids": sorted(peer.GetUniqueId() for peer in links),
                    "marker": item.GetMarkerCustomData(0),
                }
    return observed


def _assert_before(actual: dict[str, Any], geometry: Mapping[str, Any]) -> None:
    expected = _expect_geometry(geometry)
    left_uid, right_uid = _pair(expected)
    need(actual.keys() == expected.keys(), "actual native item UID set differs")
    for uid, row in actual.items():
        baseline = expected[uid]
        comparable = NATIVE_ITEM_FIELDS - {"marker"}
        if uid not in {left_uid, right_uid}:
            # The host authenticates off-by-one EOF source clock forms from
            # immutable media provenance; the SDK getter alone cannot
            # reproduce that branch. Both raw getters remain fixed across UI.
            comparable -= {"sourceDuration"}
        different = sorted(
            field for field in comparable if row[field] != baseline[field]
        )
        numeric_difference = {
            field: {"observed": row[field], "captured": baseline[field]}
            for field in different
            if field
            in {"sourceStart", "sourceDuration", "recordStart", "recordDuration"}
        }
        need(
            not different and isinstance(row["marker"], str) and bool(row["marker"]),
            "actual native clip/media/links/ranges differ BEFORE the edit "
            f"(itemUid={uid}; fields={different}; frames={numeric_difference}; "
            f"sourceEndGetter={row['sourceEndGetter']})",
        )


def _assert_after(
    before: Mapping[str, Mapping[str, Any]],
    after: Mapping[str, Mapping[str, Any]],
) -> None:
    need(before.keys() == after.keys(), "one or more native item UIDs replaced")
    left_uid, right_uid = _pair(before)
    for uid, current in after.items():
        old = before[uid]
        if uid == left_uid:
            allowed = {"recordDuration", "sourceDuration"}
            need(
                current.get("recordDuration") == old["recordDuration"] + 24
                and current.get("sourceDuration") == old["sourceDuration"] + 24,
                "left native held-picture clip did not extend exactly 24 frames",
            )
        elif uid == right_uid:
            allowed = {"recordStart", "recordDuration", "sourceDuration"}
            need(
                current.get("recordStart") == old["recordStart"] + 24
                and current.get("recordDuration") == old["recordDuration"] - 24
                and current.get("sourceDuration") == old["sourceDuration"] - 24,
                "right native held-picture clip did not shift exactly 24 frames",
            )
        else:
            allowed = set()
        need(
            {k: v for k, v in current.items() if k not in allowed}
            == {k: v for k, v in old.items() if k not in allowed},
            "unrelated native item, source-in, UID, links, marker, or track changed",
        )


def _timecode(start: str, delta: int) -> str:
    need(
        bool(re.fullmatch(r"\d{2}:\d{2}:\d{2}:\d{2}", start)),
        "unsupported start timecode",
    )
    h, m, s, f = (int(part) for part in start.split(":"))
    need(f < 24 and s < 60 and m < 60, "invalid non-drop start timecode")
    total = ((h * 3600 + m * 60 + s) * 24 + f) + delta
    need(0 <= total < 24 * 3600 * 24, "timecode outside one day")
    f = total % 24
    total //= 24
    h, m, s = total // 3600, total // 60 % 60, total % 60
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


def _roll_ui_once(expected_project_name: str) -> None:
    """One verified edit command; NEVER retry any failed OS interaction."""
    source = """
on run argv
set expectedProjectName to item 1 of argv
tell application "DaVinci Resolve" to activate
delay 0.4
tell application "System Events"
  tell process "Resolve"
    if not frontmost then error "Resolve is not the frontmost UI"
    if name of front window is not expectedProjectName then
      error "Resolve window target differs"
    end if
    keystroke "4" using shift down
    delay 0.4
    keystroke "4" using command down
    delay 0.2
    keystroke "v"
    delay 0.2
    repeat 24 times
      key code 47
      delay 0.07
    end repeat
  end tell
end tell
end run
"""
    result = subprocess.run(
        ["osascript", "-e", source, expected_project_name],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    need(
        result.returncode == 0,
        "one-use UI edit returned an error; inspect without replay",
    )


def audit_spent_attempt(root: Path) -> None:
    """Read-only native audit of the exact failed attempt; no replay or save."""
    from vera_timeline_agent import qualification_output_native_v2 as native
    from vera_timeline_agent import resolve_native_owner as owner
    from vera_timeline_agent import resolve_test_bench_m4_runner as runner
    from vera_timeline_agent import resolve_test_queue as queue
    from vera_timeline_agent import resolve_test_queue_m4 as m4

    need(root in ALLOWED_ROOTS and root.is_dir(), "not an enrolled 473 campaign")
    store = queue.Store(root / "queue")
    plan_file = root / "run/m4-plan.json"
    job_id = runner._find_job(store, digest(plan_file.read_bytes()))
    need(job_id is not None, "original M4 job absent")
    assert isinstance(job_id, str)
    status = m4.publish(store, job_id)
    need(
        status["stages"][0]["state"] == "verified"
        and status["stages"][1]["state"] == "awaiting_operator",
        "edited one-use M4 handoff changed",
    )
    intent_path = root / "run/edit-ui-intent.json"
    need(
        intent_path.is_file() and not intent_path.is_symlink(),
        "original one-use edit intent missing",
    )
    intent = json.loads(intent_path.read_bytes())
    plan = m4._load_plan(store, job_id)
    receipt = m4._stage_receipt(store, job_id, 0)
    sha = receipt["capture"]["sha256"]
    need(
        intent.get("schema") == UI_SCHEMA
        and intent.get("stageOperationId") == status["stages"][1]["operation_id"]
        and intent.get("pristineCaptureSha256") == sha
        and intent.get("initialTarget") == plan["initialTarget"],
        "one-use edit intent provenance differs",
    )
    verified = native.verify_native_result(Path(receipt["capture"]["path"]), sha)
    original = verified["nativeGeometry"]
    expected = _expect_geometry(original)
    left_uid, right_uid = _pair(expected)
    need(
        intent["leftItemUid"] == left_uid and intent["rightItemUid"] == right_uid,
        "one-use edit intent source items differ",
    )
    resolve = owner._local_resolve_connection()
    need(resolve is not None, "SDK connection missing")
    actual = snapshot(resolve, plan["initialTarget"], original)
    need(
        actual.keys() == expected.keys(),
        "native timeline item UIDs changed; stop instead of replay",
    )
    compared = {
        uid: {
            key: {"captured": expected[uid][key], "observed": actual[uid][key]}
            for key in (
                "recordStart",
                "recordDuration",
                "sourceStart",
                "sourceDuration",
            )
        }
        for uid in (left_uid, right_uid)
    }
    unrelated = sorted(
        uid
        for uid in expected
        if uid not in {left_uid, right_uid}
        and any(
            actual[uid][key] != expected[uid][key]
            for key in ("recordStart", "recordDuration", "mediaUid")
        )
    )
    print(
        json.dumps(
            {
                "state": "read_only_spent_edit_audit",
                "oneUseIntentSha256": digest(intent_path.read_bytes()),
                "leftRight": compared,
                "unrelatedItemUidsChanged": unrelated,
                "noNativeEffectOrReplay": True,
            },
            sort_keys=True,
        )
    )


def run(root: Path, *, inspect_only: bool = False) -> None:
    from vera_timeline_agent import qualification_output_native_v2 as native
    from vera_timeline_agent import resolve_native_owner as owner
    from vera_timeline_agent import resolve_test_bench_m4_runner as runner
    from vera_timeline_agent import resolve_test_queue as queue
    from vera_timeline_agent import resolve_test_queue_m4 as m4

    need(
        root in ALLOWED_ROOTS and root.is_dir() and not root.is_symlink(),
        "only the two explicitly enrolled #473 campaigns are eligible",
    )
    store = queue.Store(root / "queue")
    pinned_plan = root / "run/m4-plan.json"
    need(
        pinned_plan.is_file() and not pinned_plan.is_symlink(),
        "original M4 plan is unavailable",
    )
    job_id = runner._find_job(store, digest(pinned_plan.read_bytes()))
    need(job_id is not None, "original M4 job not enrolled")
    assert isinstance(job_id, str)
    status = m4.publish(store, job_id)
    need(
        status["state"] == "queued"
        and [row["state"] for row in status["stages"]]
        == ["verified", "pending", "pending", "pending"],
        "M4 pristine receipt is not independently verified and awaiting edit",
    )
    plan = m4._load_plan(store, job_id)
    need(plan["caseId"] == "synthetic-312", "not an approved reverse fixture")
    initial = plan["initialTarget"]
    receipt = m4._stage_receipt(store, job_id, 0)
    need(
        receipt["session"] == plan["baselineSession"],
        "signed pristine session differs from original M4 enrollment",
    )
    capture_sha = receipt["capture"]["sha256"]
    result = native.verify_native_result(Path(receipt["capture"]["path"]), capture_sha)
    need(
        result["status"] == "complete"
        and result["action"] == "capture_post"
        and result["context"]["target"] == initial
        and result["context"]["phase"] == "pristine"
        and result["context"]["caseId"] == plan["caseId"],
        "native pristine source is not complete",
    )
    geometry = result["nativeGeometry"]
    left_uid, right_uid = _pair(_expect_geometry(geometry))
    # Do not mark the M4 job blocked just because another caller selected a
    # different target. Check the actual project BEFORE the M4 worker tick.
    resolve = owner._local_resolve_connection()
    need(resolve is not None, "official local Resolve SDK unavailable")
    _selected(resolve, initial)
    owner.preflight_selected_disposable(initial, require_empty=False)
    before = snapshot(resolve, initial, geometry)
    _assert_before(before, geometry)
    if inspect_only:
        print(
            json.dumps(
                {
                    "state": "read_only_roll_ready_no_native_effect",
                    "jobId": job_id,
                    "target": initial,
                    "captureSha256": capture_sha,
                    "nativeItemSnapshotSha256": digest(queue.canonical(before)),
                    "leftItemUid": left_uid,
                    "rightItemUid": right_uid,
                    "editIntentCreated": False,
                },
                sort_keys=True,
            )
        )
        return
    need(
        runner._worker_once(store),
        "one-use M4 edited handoff not available",
    )
    status = m4.publish(store, job_id)
    need(
        status["stage"] == "edited"
        and status["stages"][1]["state"] == "awaiting_operator",
        "M4 edited stage not durably enrolled",
    )
    intent = root / "run/edit-ui-intent.json"
    need(
        not intent.exists() and not intent.is_symlink(),
        "edit intent spent; do not replay",
    )
    content = queue.canonical(
        {
            "schema": UI_SCHEMA,
            "stageOperationId": status["stages"][1]["operation_id"],
            "initialTarget": initial,
            "pristineCaptureSha256": capture_sha,
            "beforeSnapshotSha256": digest(queue.canonical(before)),
            "leftItemUid": left_uid,
            "rightItemUid": right_uid,
            "fromFrame": START_FRAME,
            "toFrame": END_FRAME,
            "command": "Resolve_Edit_timeline_V_24_period_nudges_once",
        }
    )
    descriptor = os.open(
        intent,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o400,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    queue.sync_directory(intent.parent)
    with owner.native_owner(output_lane=True):
        # The selected project can change between the earlier read-only
        # preflight and GUI focus. Verify it again under the shared owner.
        resolve = owner._local_resolve_connection()
        need(resolve is not None, "SDK disappeared after durable edit intent")
        _selected(resolve, initial)
        need(
            snapshot(resolve, initial, geometry) == before,
            "native target changed before the one-use command",
        )
        _manager, _project, timeline = _selected(resolve, initial)
        t = _timecode(timeline.GetStartTimecode(), START_FRAME)
        need(
            timeline.SetCurrentTimecode(t) is True,
            "could not set exact native edit-boundary playhead",
        )
        need(timeline.GetCurrentTimecode() == t, "playhead readback differs")
        _roll_ui_once(initial["projectName"])
        actual = snapshot(resolve, initial, geometry)
        _assert_after(before, actual)
        manager, _project, _timeline = _selected(resolve, initial)
        need(manager.SaveProject() is True, "native edited project did not save")
        need(
            snapshot(resolve, initial, geometry) == actual,
            "native SaveProject changed the edit",
        )
    print(
        json.dumps(
            {
                "state": "edit_candidate_saved_unqualified",
                "operationId": status["stages"][1]["operation_id"],
                "target": initial,
                "nativeEdits": [left_uid, right_uid],
                "replayed": False,
            },
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--inspect", action="store_true", default=False)
    parser.add_argument("--audit-after", action="store_true", default=False)
    args = parser.parse_args()
    need(
        not (args.inspect and args.audit_after),
        "inspection and spent-attempt audit are mutually exclusive",
    )
    if args.audit_after:
        audit_spent_attempt(args.root)
    else:
        run(args.root, inspect_only=args.inspect)


if __name__ == "__main__":
    main()
