"""Read-only, injected candidate UID/track containment for #499; no live GUI."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import resolve_gui_roll as gui
from vera_timeline_agent import resolve_test_bench_selection_probe as selection

NAME = "VERA Delivery 123e4567-e89b-12d3-a456-426614174000 012345abcdef"
TARGET = gui.NativeTarget("project-uid", NAME, "timeline-uid", NAME, NAME)
UIDS = tuple(f"uid-{i}" for i in range(11))


def inventory() -> gui.PristineSdkInventory:
    return gui.PristineSdkInventory(
        target=TARGET,
        capture_sha256="a" * 64,
        item_uids=UIDS,
        left_item_uid=UIDS[0],
        right_item_uid=UIDS[1],
        left_track_id="v1",
        right_track_id="v1",
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


def signed_geometry() -> dict[str, Any]:
    return {
        "tracks": [
            {"trackId": f"v{i}", "kind": "video", "index": i} for i in range(1, 6)
        ]
        + [{"trackId": "a1", "kind": "audio", "index": 1}],
        "items": [
            {
                "itemUid": uid,
                "kind": "video" if i < 2 else "audio",
                "trackId": "v1" if i < 2 else "a1",
                "recordStart": 0 if i == 0 else 327 if i == 1 else 500 + i * 40,
                "recordDuration": 327 if i == 0 else 151 if i == 1 else 20,
                "linkedItemUids": [],
            }
            for i, uid in enumerate(UIDS)
        ],
    }


class FakeTimeline:
    def __init__(self) -> None:
        self.uid = TARGET.timeline_uid
        self.name = TARGET.timeline_name
        self.timecode = "00:00:13:15"  # 327 frames at nominal 24 fps
        self.counts = {"video": 5, "audio": 1, "subtitle": 0}
        self.locks: dict[tuple[str, int], object] = {
            ("video", i): (i != 1) for i in range(1, 6)
        }
        self.locks[("audio", 1)] = True
        self.items_by_track: dict[tuple[str, int], list[Any]] = {
            (kind, index): []
            for kind, index in (
                ("video", 1),
                ("video", 2),
                ("video", 3),
                ("video", 4),
                ("video", 5),
                ("audio", 1),
            )
        }
        for row in signed_geometry()["items"]:
            item = FakeItem(row["itemUid"], row["recordStart"], row["recordDuration"])
            self.items_by_track[(row["kind"], 1)].append(item)
        self.selection: object = list(self.items_by_track[("video", 1)])

    def GetUniqueId(self) -> str:
        return self.uid

    def GetName(self) -> str:
        return self.name

    def GetTrackCount(self, kind: str) -> int:
        return self.counts[kind]

    def GetIsTrackLocked(self, kind: str, index: int) -> object:
        return self.locks[kind, index]

    def GetItemListInTrack(self, kind: str, index: int) -> list[Any]:
        return self.items_by_track[kind, index]

    def GetSelectedClips(self) -> object:
        return self.selection

    def GetCurrentTimecode(self) -> str:
        return self.timecode

    def GetStartTimecode(self) -> str:
        return "00:00:00:00"

    def GetStartFrame(self) -> int:
        return 0


class FakeItem:
    def __init__(self, uid: str, start: int, duration: int) -> None:
        self.uid = uid
        self.start = start
        self.duration = duration
        self.links: list[FakeItem] = []

    def GetUniqueId(self) -> str:
        return self.uid

    def GetStart(self, _subframe: bool) -> int:
        return self.start

    def GetDuration(self, _subframe: bool) -> int:
        return self.duration

    def GetLinkedItems(self) -> list[FakeItem]:
        return self.links


class FakeProject:
    def __init__(self, timeline: FakeTimeline) -> None:
        self.uid = TARGET.project_uid
        self.name = TARGET.project_name
        self.timeline = timeline

    def GetUniqueId(self) -> str:
        return self.uid

    def GetName(self) -> str:
        return self.name

    def GetCurrentTimeline(self) -> FakeTimeline:
        return self.timeline

    def IsRenderingInProgress(self) -> bool:
        return False


class FakeResolve:
    def __init__(self) -> None:
        self.timeline = FakeTimeline()
        self.project = FakeProject(self.timeline)
        self.page = "edit"
        self.manager = SimpleNamespace(GetCurrentProject=lambda: self.project)

    def GetCurrentPage(self) -> str:
        return self.page

    def GetProjectManager(self) -> SimpleNamespace:
        return self.manager


@pytest.fixture(autouse=True)
def mock_native_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gui, "_require_owner_lock", lambda: None)


def test_exact_selected_uids_and_sdk_track_locks_are_read_only() -> None:
    resolve = FakeResolve()
    result = selection.inspect_selected_boundary(
        resolve, inventory(), signed_geometry()
    )
    assert result == selection.SelectedBoundaryEvidence(
        project_uid=TARGET.project_uid,
        timeline_uid=TARGET.timeline_uid,
        selected_uids=(UIDS[0], UIDS[1]),
        locked_non_v1=True,
        playhead_frame=327,
    )
    # The fake exposes no setters, native journals, menu actors or writes.


@pytest.mark.parametrize(
    "fault",
    [
        "wrong-page",
        "wrong-project",
        "wrong-timeline",
        "wrong-name",
        "wrong-timeline-name",
        "wrong-track-count",
        "unlocked-v2",
        "unknown-v2-lock",
        "locked-v1",
        "unlocked-a1",
        "wrong-playhead",
        "no-selection",
        "one-selection",
        "extra-selected-v2",
        "wrong-selected-uid",
        "duplicate-selection",
        "unknown-selection",
        "not-a-list",
        "late-page-drift",
        "native-boundary-already-rolled",
        "native-extra-item",
        "native-missing-item",
        "native-wrong-track",
        "selected-stale-start",
    ],
)
def test_candidate_containment_refuses_unknown_and_wrong_target(fault: str) -> None:
    resolve = FakeResolve()
    inv = inventory()
    if fault == "wrong-page":
        resolve.page = "deliver"
    elif fault == "wrong-project":
        resolve.project.uid = "producer-project"
    elif fault == "wrong-timeline":
        resolve.timeline.uid = "old-timeline"
    elif fault == "wrong-name":
        resolve.project.name = "Producer Project"
    elif fault == "wrong-timeline-name":
        resolve.timeline.name = "Producer Timeline"
    elif fault == "wrong-track-count":
        resolve.timeline.counts["video"] = 4
    elif fault == "unlocked-v2":
        resolve.timeline.locks[("video", 2)] = False
    elif fault == "unknown-v2-lock":
        resolve.timeline.locks[("video", 2)] = None
    elif fault == "locked-v1":
        resolve.timeline.locks[("video", 1)] = True
    elif fault == "unlocked-a1":
        resolve.timeline.locks[("audio", 1)] = False
    elif fault == "wrong-playhead":
        resolve.timeline.timecode = "00:00:13:16"
    elif fault == "no-selection":
        resolve.timeline.selection = []
    elif fault == "one-selection":
        resolve.timeline.selection = [SimpleNamespace(GetUniqueId=lambda: UIDS[0])]
    elif fault == "extra-selected-v2":
        resolve.timeline.selection = [
            SimpleNamespace(GetUniqueId=lambda: UIDS[0]),
            SimpleNamespace(GetUniqueId=lambda: UIDS[1]),
            SimpleNamespace(GetUniqueId=lambda: UIDS[2]),
        ]
    elif fault == "wrong-selected-uid":
        resolve.timeline.selection = [
            SimpleNamespace(GetUniqueId=lambda: UIDS[0]),
            SimpleNamespace(GetUniqueId=lambda: UIDS[3]),
        ]
    elif fault == "duplicate-selection":
        resolve.timeline.selection = [
            SimpleNamespace(GetUniqueId=lambda: UIDS[0]),
            SimpleNamespace(GetUniqueId=lambda: UIDS[0]),
        ]
    elif fault == "unknown-selection":
        resolve.timeline.selection = [
            SimpleNamespace(GetUniqueId=lambda: UIDS[0]),
            SimpleNamespace(GetUniqueId=lambda: None),
        ]
    elif fault == "not-a-list":
        resolve.timeline.selection = {"0": UIDS[0], "1": UIDS[1]}
    elif fault == "native-boundary-already-rolled":
        items = resolve.timeline.items_by_track[("video", 1)]
        items[0].duration = 351
        items[1].start = 351
    elif fault == "native-extra-item":
        resolve.timeline.items_by_track[("audio", 1)].append(
            FakeItem("extra-uid", 950, 10)
        )
    elif fault == "native-missing-item":
        resolve.timeline.items_by_track[("audio", 1)].pop()
    elif fault == "native-wrong-track":
        item = resolve.timeline.items_by_track[("audio", 1)].pop()
        resolve.timeline.items_by_track[("video", 2)].append(item)
    elif fault == "selected-stale-start":
        resolve.timeline.selection = [
            FakeItem(UIDS[0], 7, 327),
            FakeItem(UIDS[1], 327, 151),
        ]
    else:
        count = 0

        def page() -> str:
            nonlocal count
            count += 1
            return "edit" if count == 1 else "deliver"

        resolve.GetCurrentPage = page  # type: ignore[method-assign]
    with pytest.raises(gui.GuiRollRefused):
        selection.inspect_selected_boundary(resolve, inv, signed_geometry())


@pytest.mark.parametrize(
    "fault",
    [
        "producer-name",
        "unsigned-inventory",
        "duplicate-geometry",
        "missing-track",
        "invalid-lock",
        "linked-boundary",
        "other-cut-at-327",
        "wrong-boundary-track",
        "list-track-id",
        "list-item-uid",
    ],
)
def test_candidate_selection_refuses_unbound_or_invalid_provenance(fault: str) -> None:
    resolve = FakeResolve()
    inv = inventory()
    geom = signed_geometry()
    if fault == "producer-name":
        inv = replace(inv, target=replace(inv.target, project_name="Producer"))
    elif fault == "unsigned-inventory":
        inv = replace(inv, pristine_verified=False)
    elif fault == "duplicate-geometry":
        geom["items"][2]["itemUid"] = UIDS[0]
    elif fault == "missing-track":
        geom["tracks"][1]["kind"] = "audio"
    elif fault == "linked-boundary":
        geom["items"][0]["linkedItemUids"] = [UIDS[2]]
    elif fault == "other-cut-at-327":
        geom["items"][5]["recordStart"] = 327
    elif fault == "wrong-boundary-track":
        geom["items"][0]["trackId"] = "v2"
    elif fault == "list-track-id":
        geom["tracks"][0]["trackId"] = ["v1"]
    elif fault == "list-item-uid":
        geom["items"][0]["itemUid"] = [UIDS[0]]
    else:
        resolve.timeline.locks[("video", 3)] = "true"
    with pytest.raises(gui.GuiRollRefused):
        selection.inspect_selected_boundary(resolve, inv, geom)


def test_losing_owner_during_selection_readback_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checks = 0

    def check_owner() -> None:
        nonlocal checks
        checks += 1
        if checks >= 2:
            raise gui.GuiRollRefused("original native owner lost")

    monkeypatch.setattr(gui, "_require_owner_lock", check_owner)
    with pytest.raises(gui.GuiRollRefused, match="owner lost"):
        selection.inspect_selected_boundary(
            FakeResolve(), inventory(), signed_geometry()
        )
    assert checks == 2


@pytest.mark.parametrize("late_change", ["new-track", "new-item", "new-link"])
def test_live_inventory_rechecked_after_sdk_selection(
    late_change: str,
) -> None:
    resolve = FakeResolve()
    original = resolve.timeline.GetSelectedClips

    def selected_then_drift() -> object:
        selected = original()
        if late_change == "new-track":
            resolve.timeline.counts["video"] = 6
        elif late_change == "new-item":
            resolve.timeline.items_by_track[("audio", 1)].append(
                FakeItem("new-after-selection", 990, 2)
            )
        else:
            resolve.timeline.items_by_track[("video", 1)][0].links = [
                resolve.timeline.items_by_track[("audio", 1)][0]
            ]
        return selected

    resolve.timeline.GetSelectedClips = selected_then_drift  # type: ignore[method-assign]
    with pytest.raises(gui.GuiRollRefused):
        selection.inspect_selected_boundary(resolve, inventory(), signed_geometry())
