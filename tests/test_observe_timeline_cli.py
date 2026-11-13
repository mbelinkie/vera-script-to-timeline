"""SDK-free tests of the edit report on the #522 readback path."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_readback_timeline_cli import FakeItem, FakeResolve, FakeTimeline, _case
from vera_timeline_agent import observe_timeline_cli as cli
from vera_timeline_agent import readback_timeline_cli as readback
from vera_timeline_agent.build_timeline_once import exclusive_resolve_build
from vera_timeline_agent.row_timeline_map import (
    make_row_timeline_map,
    observe_item_details,
)


class Clip(FakeItem):
    def __init__(self, event: dict[str, Any], uid: str) -> None:
        super().__init__(event, uid)
        self.name = str(event["id"])
        self.source_start: int | None = 100
        self.source_end = 111

    def GetMarkers(self) -> dict[int, dict[str, str]]:
        return {3: {"customData": self.stamp}} if self.stamp else {}

    def GetName(self) -> str:
        return self.name

    def GetMediaPoolItem(self) -> Clip:
        return self

    def GetMediaId(self) -> str:
        return self.name

    def GetSourceStartFrame(self) -> int | None:
        return self.source_start

    def GetSourceEndFrame(self) -> int:
        return self.source_end


def _baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, FakeResolve, FakeTimeline, Clip, Clip]:
    output, saved, resolve = _case(tmp_path, monkeypatch)
    monkeypatch.setattr(
        cli,
        "exclusive_resolve_build",
        lambda: exclusive_resolve_build(tmp_path / "resolve.lock"),
    )
    package = readback._load_readback_package(output)
    timeline = FakeTimeline(package.view)
    assert resolve.project is not None
    resolve.project.timeline = timeline
    video, audio = (
        Clip(event, "native-" + event["id"]) for event in package.view["events"]
    )
    timeline.items["video", 1] = [video]
    timeline.items["audio", 1] = [audio]
    before = make_row_timeline_map(
        package.manifest,
        package.view,
        [
            {**item, **observe_item_details(clip)}
            for item, clip in zip(
                saved["rows"][0]["items"], (audio, video), strict=True
            )
        ],
        project_name="P",
        resolve_project_id="p-uid",
        timeline_name="T",
        timeline_id="t-uid",
        version=2,
    )
    (output / "row-timeline-map.json").write_text(json.dumps(before))
    return output, resolve, timeline, video, audio


def test_untouched_baseline_has_zero_differences_and_explicit_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, resolve, _, _, _ = _baseline(tmp_path, monkeypatch)
    report = cli.observe_output(output, resolve_factory=lambda: resolve)
    assert report["differenceCount"] == 0
    assert report["cannotRead"][:2] == ["grades", "effects"]
    assert report["rows"][0]["rowId"] == "row-a"
    assert [item["status"] for item in report["rows"][0]["items"]] == [
        ["unchanged"],
        ["unchanged"],
    ]
    assert readback.readback_output(output, resolve_factory=lambda: resolve).startswith(
        "PASS"
    )


def test_reports_move_trim_removal_and_added_clip_under_original_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, resolve, timeline, video, audio = _baseline(tmp_path, monkeypatch)
    video.start = 14
    audio.source_start = 102
    audio.start = 2
    audio.duration = 10
    audio.stamp = ""  # A trim may hide the clip marker.
    added = Clip(timeline.view["events"][0], "editor")
    added.stamp = ""
    added.start = 2
    added.duration = 4
    timeline.items["video", 1].append(added)
    report = cli.observe_output(output, resolve_factory=lambda: resolve)
    assert report["differenceCount"] == 3
    row = report["rows"][0]
    assert row["rowId"] == "row-a"
    trim, move, addition = row["items"]
    assert trim["status"] == ["trimmed"]
    assert trim["changes"]["sourceStartFrame"] == {"before": 100, "after": 102}
    assert move["status"] == ["moved"]
    assert addition["status"] == ["added"]
    assert addition["resolveItemId"] == "editor"

    timeline.items["audio", 1].clear()
    report = cli.observe_output(output, resolve_factory=lambda: resolve)
    assert report["rows"][0]["items"][0]["status"] == ["removed"]
    assert report["differenceCount"] == 3


def test_unreadable_source_and_addition_outside_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, resolve, timeline, video, _ = _baseline(tmp_path, monkeypatch)
    video.source_start = None
    added = Clip(timeline.view["events"][0], "outside")
    added.stamp = ""
    added.start = 11
    timeline.items["video", 2] = [added]
    report = cli.observe_output(output, resolve_factory=lambda: resolve)
    unknown = report["rows"][0]["items"][1]
    assert unknown["status"] == ["cannot tell"]
    assert unknown["cannotRead"] == ["sourceStartFrame"]
    assert report["rows"][1]["rowId"] is None
    assert report["rows"][1]["items"][0]["rowAttribution"].startswith("cannot tell")


@pytest.mark.parametrize("collision", ["copied stamp", "duplicate UID", "wrong stamp"])
def test_stops_when_identity_is_ambiguous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, collision: str
) -> None:
    output, resolve, timeline, video, audio = _baseline(tmp_path, monkeypatch)
    if collision == "wrong stamp":
        video.stamp = audio.stamp
    else:
        uid = video.uid if collision == "duplicate UID" else "extra"
        timeline.items["video", 1].append(Clip(timeline.view["events"][0], uid))
    with pytest.raises(ValueError, match="ambiguous"):
        cli.observe_output(output, resolve_factory=lambda: resolve)


def test_duplicate_and_other_project_refused_without_switching_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, resolve, timeline, _, _ = _baseline(tmp_path, monkeypatch)
    assert resolve.project is not None
    resolve.project.timeline = FakeTimeline(
        timeline.view, uid="duplicate", name="T Copy"
    )
    with pytest.raises(ValueError, match="build target 'T'"):
        cli.observe_output(output, resolve_factory=lambda: resolve)
    resolve.project.timeline.name = "T"
    with pytest.raises(ValueError, match="original timeline 'T'"):
        cli.observe_output(output, resolve_factory=lambda: resolve)
    resolve.project.timeline = timeline
    assert (
        cli.observe_output(output, resolve_factory=lambda: resolve)["differenceCount"]
        == 0
    )
    resolve.project.uid = "wrong-project"
    with pytest.raises(ValueError, match="project UID differs"):
        cli.observe_output(output, resolve_factory=lambda: resolve)


def test_missing_or_old_baseline_refused_before_connecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output, _, _ = _case(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "_external_resolve", lambda: pytest.fail("called Resolve"))
    assert cli.main(["--output", str(output)]) == 2
    assert "version 1" in capsys.readouterr().err
    (output / "row-timeline-map.json").unlink()
    assert cli.main(["--output", str(output)]) == 2
    assert "no row-timeline-map.json baseline" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("start", "duration", "source_start", "source_end", "expected"),
    [
        (0, 24, 100, 111, ["cannot tell"]),
        (0, 24, 100, 109, ["cannot tell"]),
        (7, 10, 100, 109, ["trimmed", "moved"]),
        (2, 10, 102, 111, ["trimmed"]),
        (7, 10, 102, 111, ["trimmed", "moved"]),
        (7, 24, 100, 111, ["moved", "cannot tell"]),
    ],
)
def test_distinguishes_retime_head_trim_and_combined_move(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    start: int,
    duration: int,
    source_start: int,
    source_end: int,
    expected: list[str],
) -> None:
    output, resolve, _, video, _ = _baseline(tmp_path, monkeypatch)
    video.start, video.duration = start, duration
    video.source_start, video.source_end = source_start, source_end
    report = cli.observe_output(output, resolve_factory=lambda: resolve)
    assert report["rows"][0]["items"][1]["status"] == expected


def test_addition_follows_the_current_row_when_managed_clips_shift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, resolve, timeline, video, audio = _baseline(tmp_path, monkeypatch)
    video.start = audio.start = 24
    added = Clip(timeline.view["events"][0], "editor")
    added.stamp = ""
    added.start, added.duration = 25, 2
    timeline.items["video", 1].append(added)
    report = cli.observe_output(output, resolve_factory=lambda: resolve)
    assert len(report["rows"]) == 1
    assert report["rows"][0]["rowId"] == "row-a"
    assert report["rows"][0]["items"][-1]["status"] == ["added"]


def test_addition_after_gap_closure_uses_surviving_row_identity() -> None:
    rows: list[dict[str, Any]] = [
        {"rowId": "removed", "items": [{"resolveItemId": "gone"}]},
        {"rowId": "later", "items": [{"resolveItemId": "kept"}]},
    ]
    current = {"kept": {"startFrame": 0, "durationFrames": 12}}
    addition = {"startFrame": 2, "durationFrames": 2}
    assert cli._row_for_addition(addition, rows, current, {}) == "later"
    rows.append({"rowId": None, "items": [{"resolveItemId": "unassigned"}]})
    current["unassigned"] = {"startFrame": 0, "durationFrames": 12}
    assert cli._row_for_addition(addition, rows, current, {}) is None


def test_addition_in_a_gap_between_one_rows_clips_stays_unassigned() -> None:
    rows = [
        {
            "rowId": "a",
            "items": [{"resolveItemId": "video"}, {"resolveItemId": "audio"}],
        }
    ]
    current = {
        "video": {"startFrame": 100, "durationFrames": 24},
        "audio": {"startFrame": 0, "durationFrames": 24},
    }
    assert (
        cli._row_for_addition(
            {"startFrame": 60, "durationFrames": 2}, rows, current, {}
        )
        is None
    )


def test_spanning_music_does_not_assign_a_deleted_rows_replacement() -> None:
    rows = [
        {
            "rowId": "a",
            "items": [
                {"resolveItemId": "a-video"},
                {"resolveItemId": "bed", "eventId": "music-event"},
            ],
        },
        {"rowId": "b", "items": [{"resolveItemId": "b-video"}]},
    ]
    current = {
        "a-video": {"startFrame": 0, "durationFrames": 24},
        "bed": {"startFrame": 0, "durationFrames": 48},
    }
    addition = {"startFrame": 24, "durationFrames": 24}
    kinds = {"music-event": "music"}
    assert cli._row_for_addition(addition, rows, current, kinds) is None
    current["b-video"] = {"startFrame": 24, "durationFrames": 24}
    assert cli._row_for_addition(addition, rows, current, kinds) == "b"
