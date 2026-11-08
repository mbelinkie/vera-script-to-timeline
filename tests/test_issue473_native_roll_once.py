"""No Resolve/UI effects: tests for guarded, irreversible #473 roll candidate."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/issue-473-native-roll-once.py"
SPEC = importlib.util.spec_from_file_location("issue473_native_roll", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
ROLL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROLL)


def baseline() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for index in range(11):
        row: dict[str, Any] = {
            "itemUid": f"audio-{index}",
            "trackId": "audio",
            "kind": "audio",
            "recordStart": index * 100,
            "recordDuration": 42,
            "sourceStart": 0,
            "sourceDuration": 42,
            "mediaUid": f"media-{index}",
            "linkedItemUids": [],
            "marker": "immutable-native-event-stamp",
        }
        if index == 0:
            row.update(
                itemUid=ROLL.LEFT_UID,
                trackId="root",
                kind="video",
                recordStart=0,
                recordDuration=327,
                sourceDuration=327,
            )
        elif index == 1:
            row.update(
                itemUid=ROLL.RIGHT_UID,
                trackId="root",
                kind="video",
                recordStart=327,
                recordDuration=151,
                sourceDuration=151,
            )
        items.append(row)
    return {
        "rate": {"numerator": 24000, "denominator": 1001},
        "extentFrames": 1407,
        "tracks": [{"trackId": f"track-{i}"} for i in range(6)],
        "items": items,
    }


def snapshot_fixture() -> dict[str, dict[str, Any]]:
    return {
        row["itemUid"]: {**row, "sourceEndGetter": 0 if row["kind"] == "video" else 41}
        for row in baseline()["items"]
    }


def _sdk_fixture() -> tuple[Any, dict[str, str], dict[str, Any]]:
    geometry = baseline()
    target = {
        "projectUid": "synthetic-only-project",
        "timelineUid": "synthetic-only-timeline",
        "projectName": "VERA Delivery synthetic-only-project",
        "timelineName": "VERA Delivery synthetic-only-project",
    }
    tracks = [
        {
            "kind": "video" if index < 2 else "audio",
            "index": index + 1 if index < 2 else index - 1,
            "trackId": "root"
            if index == 0
            else "overlay"
            if index == 1
            else "audio"
            if index == 2
            else f"audio-{index}",
            "name": f"track-{index}",
            "enabled": True,
            "locked": False,
        }
        for index in range(6)
    ]
    geometry["tracks"] = tracks
    rows = geometry["items"]
    authentic = dict(target)

    def native_item(row: dict[str, Any]) -> Any:
        frozen = row["kind"] == "video"
        return SimpleNamespace(
            GetUniqueId=lambda: row["itemUid"],
            GetStart=lambda subframe=False: row["recordStart"],
            GetDuration=lambda subframe=False: row["recordDuration"],
            GetSourceStartFrame=lambda: row["sourceStart"],
            GetSourceEndFrame=lambda: (
                row["sourceStart"]
                if frozen
                else row["sourceStart"] + row["sourceDuration"] - 1
            ),
            GetMediaPoolItem=lambda: SimpleNamespace(
                GetUniqueId=lambda: row["mediaUid"]
            ),
            GetLinkedItems=lambda: [],
            GetMarkerCustomData=lambda offset: row["marker"],
        )

    inventory = {row["itemUid"]: native_item(row) for row in rows}

    def spec(kind: str, index: int) -> dict[str, Any]:
        return next(t for t in tracks if t["kind"] == kind and t["index"] == index)

    timeline = SimpleNamespace(
        GetUniqueId=lambda: authentic["timelineUid"],
        GetName=lambda: authentic["timelineName"],
        GetTrackCount=lambda kind: max(
            (t["index"] for t in tracks if t["kind"] == kind), default=0
        ),
        GetTrackName=lambda kind, index: spec(kind, index)["name"],
        GetIsTrackEnabled=lambda kind, index: spec(kind, index)["enabled"],
        GetIsTrackLocked=lambda kind, index: spec(kind, index)["locked"],
        GetItemListInTrack=lambda kind, index: [
            inventory[r["itemUid"]]
            for r in rows
            if r["trackId"] == spec(kind, index)["trackId"] and r["kind"] == kind
        ],
    )
    project = SimpleNamespace(
        GetUniqueId=lambda: authentic["projectUid"],
        GetName=lambda: authentic["projectName"],
        GetCurrentTimeline=lambda: timeline,
        IsRenderingInProgress=lambda: False,
    )
    resolve = SimpleNamespace(
        GetProjectManager=lambda: SimpleNamespace(GetCurrentProject=lambda: project)
    )
    return resolve, target, geometry


def test_read_only_native_sdk_snapshot_matches_all_original_uids() -> None:
    resolve, target, geometry = _sdk_fixture()
    live = ROLL.snapshot(resolve, target, geometry)
    assert live == snapshot_fixture()
    ROLL._assert_before(live, geometry)


def test_sdk_refuses_wrong_native_project_before_touching_timeline() -> None:
    resolve, target, geometry = _sdk_fixture()
    target["projectUid"] = "another-project"
    with pytest.raises(ValueError, match="selected project/timeline UID"):
        ROLL.snapshot(resolve, target, geometry)


def edited(before: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    after = copy.deepcopy(before)
    after[ROLL.LEFT_UID]["recordDuration"] += 24
    after[ROLL.LEFT_UID]["sourceDuration"] += 24
    after[ROLL.RIGHT_UID]["recordStart"] += 24
    after[ROLL.RIGHT_UID]["recordDuration"] -= 24
    after[ROLL.RIGHT_UID]["sourceDuration"] -= 24
    return after


def test_exact_pure_boundary_and_all_other_native_metadata() -> None:
    rows = snapshot_fixture()
    ROLL._expect_geometry(baseline())
    ROLL._assert_before(rows, baseline())
    ROLL._assert_after(rows, edited(rows))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda a: a[ROLL.LEFT_UID].update(recordDuration=350),
        lambda a: a[ROLL.RIGHT_UID].update(recordStart=350),
        lambda a: a[ROLL.RIGHT_UID].update(sourceStart=24),
        lambda a: a[ROLL.RIGHT_UID].update(sourceEndGetter=24),
        lambda a: a[ROLL.LEFT_UID].update(mediaUid="new-media"),
        lambda a: a[ROLL.LEFT_UID].update(marker="changed"),
        lambda a: a[ROLL.RIGHT_UID].update(itemUid="new-item"),
        lambda a: a["audio-2"].update(recordStart=225),
        lambda a: a["audio-2"].update(sourceStart=12),
        lambda a: a["audio-2"].update(linkedItemUids=["foreign"]),
        lambda a: a.pop(ROLL.LEFT_UID),
    ],
)
def test_unsafe_roll_or_changed_audio_uid_is_never_a_saved_candidate(
    mutation: Any,
) -> None:
    before = snapshot_fixture()
    after = edited(before)
    mutation(after)
    with pytest.raises(ValueError, match="guarded roll refused"):
        ROLL._assert_after(before, after)


@pytest.mark.parametrize(
    ("original", "offset", "expected"),
    [
        ("01:00:00:00", 327, "01:00:13:15"),
        ("01:00:00:00", 351, "01:00:14:15"),
        ("00:00:59:23", 1, "00:01:00:00"),
    ],
)
def test_playhead_uses_exact_24_frame_nondrop_position(
    original: str, offset: int, expected: str
) -> None:
    assert ROLL._timecode(original, offset) == expected


def test_one_os_event_batch_with_verified_window_and_no_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: Any) -> Any:
        called.append(argv)
        assert kwargs["timeout"] == 20
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(ROLL.subprocess, "run", fake_run)
    ROLL._roll_ui_once("original-disposable-only")
    assert len(called) == 1
    assert called[0][0] == "osascript"
    assert called[0][-1] == "original-disposable-only"
    assert "if name of front window is not expectedProjectName" in called[0][2]
    assert "repeat 24 times" in called[0][2]
    assert "key code 47" in called[0][2]


def test_os_failure_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    def fail(argv: object, **_kwargs: Any) -> Any:
        calls.append(argv)
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(ROLL.subprocess, "run", fail)
    with pytest.raises(ValueError, match="without replay"):
        ROLL._roll_ui_once("original-disposable-only")
    assert len(calls) == 1
