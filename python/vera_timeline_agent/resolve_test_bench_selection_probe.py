"""Read-only selection/track containment probe for a NEW signed M4 case.

Resolve 21.1.1 Qt does not expose reliable selected menu marks or timeline
focus. The 21.1.1 SDK *does* expose GetSelectedClips and GetIsTrackLocked.
This module can independently check those facts after a separately approved,
bounded GUI **selection-only** preparation. It must never be interpreted as
proof that a Roll edit point itself appears in GetSelectedClips, nor as
permission to attempt an edit. No SDK/GUI setter or one-use journal is used.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from . import resolve_gui_roll as gui
from .resolve_test_bench_gui_stage import _read_only_playhead_frame

_TRACK_SLOTS = (
    ("video", 1),
    ("video", 2),
    ("video", 3),
    ("video", 4),
    ("video", 5),
    ("audio", 1),
)


def _live_items_match(
    timeline: Any, signed_items: dict[str, dict[str, Any]], tracks: list[dict[str, Any]]
) -> None:
    """Require all actual native UIDs/positions to match the pristine receipt.

    Selected clips alone cannot establish that the original cut has not
    already moved or that another item has been inserted on a different track.
    """
    slots = {(row["kind"], row["index"]): row["trackId"] for row in tracks}
    observed: set[str] = set()
    for kind, index in _TRACK_SLOTS:
        actual = timeline.GetItemListInTrack(kind, index)
        _require(
            isinstance(actual, (list, tuple)) and len(actual) <= gui.NATIVE_ITEM_COUNT,
            "live native track items unavailable or excessive",
        )
        for item in actual:
            _require(item is not None, "null native timeline item")
            uid = item.GetUniqueId()
            _require(
                type(uid) is str and uid in signed_items and uid not in observed,
                "new, duplicate or unknown native item UID",
            )
            row = signed_items[uid]
            links = item.GetLinkedItems()
            _require(
                row.get("kind") == kind
                and row.get("trackId") == slots[(kind, index)]
                and type(row.get("recordStart")) is int
                and type(row.get("recordDuration")) is int
                and row["recordDuration"] > 0
                and type(item.GetStart(False)) is int
                and item.GetStart(False) == row["recordStart"]
                and type(item.GetDuration(False)) is int
                and item.GetDuration(False) == row["recordDuration"]
                and isinstance(links, (list, tuple))
                and sorted(peer.GetUniqueId() for peer in links)
                == sorted(row.get("linkedItemUids", [])),
                "live native frame/track/links differ from pristine capture",
            )
            observed.add(uid)
    _require(observed == set(signed_items), "native signed item inventory incomplete")


@dataclass(frozen=True, slots=True)
class SelectedBoundaryEvidence:
    project_uid: str
    timeline_uid: str
    selected_uids: tuple[str, str]
    locked_non_v1: bool
    playhead_frame: int


def _require(value: bool, detail: str) -> None:
    if not value:
        raise gui.GuiRollRefused("M4 candidate SDK selection probe refused: " + detail)


def inspect_selected_boundary(
    resolve: Any,
    inventory: gui.PristineSdkInventory,
    signed_geometry: Mapping[str, Any],
) -> SelectedBoundaryEvidence:
    """Return independently read SDK facts; refuse UNKNOWN and extra selection.

    Only the held native owner may invoke this against a previously admitted
    **new disposable** original M4 target. The authenticated parent must load
    the geometry from the original signed pristine receipt, not caller JSON.
    Its result is candidate evidence; the actual selected Roll edit point may
    not be exposed by GetSelectedClips, which requires an independent native
    selection-only trial before this can be used by production dispatch.
    """
    gui._require_owner_lock()
    target = inventory.target
    _require(
        inventory.pristine_verified is True
        and gui._DISPOSABLE_PROJECT.fullmatch(target.project_name) is not None
        and target.project_name == target.timeline_name == target.expected_window_name,
        "not the authenticated new disposable target",
    )
    _require(resolve.GetCurrentPage() == "edit", "SDK Edit page unavailable")
    manager = resolve.GetProjectManager()
    project = manager.GetCurrentProject() if manager is not None else None
    timeline = project.GetCurrentTimeline() if project is not None else None
    _require(
        project is not None
        and timeline is not None
        and project.GetUniqueId() == target.project_uid
        and project.GetName() == target.project_name
        and timeline.GetUniqueId() == target.timeline_uid
        and timeline.GetName() == target.timeline_name
        and project.IsRenderingInProgress() is False,
        "SDK project/timeline identity or idle state differs",
    )
    assert timeline is not None
    tracks = signed_geometry.get("tracks")
    items = signed_geometry.get("items")
    _require(
        isinstance(tracks, list) and len(tracks) == len(_TRACK_SLOTS),
        "signed six-track geometry invalid",
    )
    _require(
        isinstance(items, list) and len(items) == gui.NATIVE_ITEM_COUNT,
        "signed eleven-item geometry invalid",
    )
    assert isinstance(tracks, list) and isinstance(items, list)
    # Validate types BEFORE using values in sets/dicts: malformed signed
    # geometry must refuse, rather than raising TypeError on a list-valued ID.
    _require(
        all(
            isinstance(row, dict)
            and type(row.get("kind")) is str
            and type(row.get("index")) is int
            and type(row.get("trackId")) is str
            and bool(row["trackId"])
            for row in tracks
        )
        and all(
            isinstance(row, dict)
            and type(row.get("itemUid")) is str
            and bool(row["itemUid"])
            and type(row.get("trackId")) is str
            and type(row.get("kind")) is str
            and type(row.get("recordStart")) is int
            and type(row.get("recordDuration")) is int
            and isinstance(row.get("linkedItemUids"), list)
            and all(type(uid) is str for uid in row["linkedItemUids"])
            for row in items
        ),
        "signed geometry contains invalid native types",
    )
    _require(
        {(row["kind"], row["index"]) for row in tracks} == set(_TRACK_SLOTS)
        and len({row["trackId"] for row in tracks}) == len(_TRACK_SLOTS),
        "signed six-track topology differs",
    )
    by_uid = {row.get("itemUid"): row for row in items}
    _require(
        all(type(row.get("itemUid")) is str and row["itemUid"] for row in items)
        and len(by_uid) == gui.NATIVE_ITEM_COUNT
        and set(by_uid) == set(inventory.item_uids)
        and {inventory.left_item_uid, inventory.right_item_uid} <= set(by_uid),
        "signed item UID inventory differs",
    )
    left = by_uid[inventory.left_item_uid]
    right = by_uid[inventory.right_item_uid]
    v1 = next(row for row in tracks if row["kind"] == "video" and row["index"] == 1)
    _require(
        inventory.left_track_kind == inventory.right_track_kind == "video"
        and inventory.left_track_index == inventory.right_track_index == 1
        and inventory.left_track_id == inventory.right_track_id == v1["trackId"]
        and left.get("kind") == right.get("kind") == "video"
        and left.get("trackId") == right.get("trackId") == inventory.left_track_id
        and left.get("recordStart") == 0
        and left.get("recordDuration") == gui.BEFORE_BOUNDARY
        and right.get("recordStart") == gui.BEFORE_BOUNDARY
        and right.get("recordDuration") == 151
        and left.get("linkedItemUids") == right.get("linkedItemUids") == []
        and all(
            row["itemUid"] in {inventory.left_item_uid, inventory.right_item_uid}
            or (
                type(row.get("recordStart")) is int
                and type(row.get("recordDuration")) is int
                and row["recordDuration"] > 0
                and row["recordStart"] != gui.BEFORE_BOUNDARY
                and row["recordStart"] + row["recordDuration"] != gui.BEFORE_BOUNDARY
            )
            for row in items
        ),
        "signed 327 boundary co-selection or linkage is not isolated",
    )
    for kind in ("video", "audio", "subtitle"):
        expected_count = 5 if kind == "video" else 1 if kind == "audio" else 0
        count = timeline.GetTrackCount(kind)
        _require(
            type(count) is int and count == expected_count,
            "actual track count differs",
        )
    # Locking alone never proves selection: historical #141 showed locked
    # tracks could still contribute selected clips. It is defense in depth.
    for kind, index in _TRACK_SLOTS:
        required = (kind, index) != ("video", 1)
        _require(
            timeline.GetIsTrackLocked(kind, index) is required,
            "actual SDK track containment locks absent or unknown",
        )
    _live_items_match(timeline, by_uid, tracks)
    _require(
        _read_only_playhead_frame(timeline) == gui.BEFORE_BOUNDARY,
        "playhead changed from signed frame 327",
    )
    selected = timeline.GetSelectedClips()
    _require(
        type(selected) is list
        and len(selected) == 2
        and all(item is not None for item in selected),
        "selected boundary clips unavailable or selection is ambiguous",
    )
    assert isinstance(selected, list)
    selected_uids = [item.GetUniqueId() for item in selected]
    _require(
        all(type(uid) is str for uid in selected_uids)
        and len(set(selected_uids)) == 2
        and set(selected_uids) == {inventory.left_item_uid, inventory.right_item_uid},
        "selection differs from exact signed left/right native UIDs",
    )
    for item in selected:
        uid = item.GetUniqueId()
        row = by_uid[uid]
        _require(
            item.GetStart(False) == row["recordStart"]
            and item.GetDuration(False) == row["recordDuration"],
            "selected clip position differs from signed pristine cut",
        )
    # Selection is live UI state. Re-identify the owning target/page/playhead
    # after reading it; changing context during SDK reads must fail closed.
    after_project = manager.GetCurrentProject()
    after_timeline = (
        after_project.GetCurrentTimeline() if after_project is not None else None
    )
    gui._require_owner_lock()
    _require(
        resolve.GetCurrentPage() == "edit"
        and after_project is not None
        and after_project.GetUniqueId() == target.project_uid
        and after_project.GetName() == target.project_name
        and after_project.IsRenderingInProgress() is False
        and after_timeline is not None
        and after_timeline.GetUniqueId() == target.timeline_uid
        and after_timeline.GetName() == target.timeline_name
        and _read_only_playhead_frame(after_timeline) == gui.BEFORE_BOUNDARY
        and all(
            after_timeline.GetTrackCount(kind)
            == (5 if kind == "video" else 1 if kind == "audio" else 0)
            for kind in ("video", "audio", "subtitle")
        )
        and all(
            after_timeline.GetIsTrackLocked(kind, index)
            is ((kind, index) != ("video", 1))
            for kind, index in _TRACK_SLOTS
        ),
        "SDK target/page/playhead/track-lock drifted during selection readback",
    )
    _live_items_match(after_timeline, by_uid, tracks)
    return SelectedBoundaryEvidence(
        project_uid=target.project_uid,
        timeline_uid=target.timeline_uid,
        selected_uids=(inventory.left_item_uid, inventory.right_item_uid),
        locked_non_v1=True,
        playhead_frame=gui.BEFORE_BOUNDARY,
    )
