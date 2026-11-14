"""SDK-free tests of updating only the changed rows of a finished timeline."""

from __future__ import annotations

import copy
import json
import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import timeline_update as planning
from vera_timeline_agent import update_timeline_cli as cli
from vera_timeline_agent.build_jobs import NeedsAction, UncertainResult
from vera_timeline_agent.build_timeline_once import exclusive_resolve_build
from vera_timeline_agent.observe_timeline_cli import observe_current
from vera_timeline_agent.row_timeline_map import (
    make_row_timeline_map,
    observe_item_details,
)
from vera_timeline_agent.workflow_v2 import _stamp

DOCUMENT = "doc-1"
ROWS = ("row-1", "row-2", "row-3")
FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "packages/contracts/test/fixtures/timeline-update-attempt.json"
)


class Media:
    def __init__(self, name: str) -> None:
        self.name = name
        self.stale = False

    def GetUniqueId(self) -> str:
        return f"pool-{self.name}"

    def GetMediaId(self) -> str | None:
        # A handle taken from the Media Pool dies when the project closes.
        return None if self.stale else f"media-{self.name}"


class Item:
    """A timeline clip or transition with the calls the update uses."""

    def __init__(
        self, uid: str, start: int, duration: int, media: Media | None, stamp: str = ""
    ) -> None:
        self.uid, self.start, self.duration, self.media = uid, start, duration, media
        self.source_start = 0
        self.markers: dict[int, dict[str, Any]] = (
            {0: {"customData": stamp, "name": "VERA v2 event"}} if stamp else {}
        )
        self.properties: dict[str, Any] = {
            "ZoomX": 1.0,
            "Pan": 0.0,
            "AudioVoiceIsolationEnabled": False,
        }
        self.nodes = 1
        self.takes: list[dict[str, Any]] = []
        self.finalize_ok = True

    def GetUniqueId(self) -> str:
        return self.uid

    def GetType(self) -> str:
        return "clip" if self.media else "transition"

    def GetName(self) -> str:
        return self.media.name if self.media else "Cross Dissolve"

    def GetStart(self, _subframe: bool = False) -> int:
        return self.start

    def GetDuration(self, _subframe: bool = False) -> int:
        return self.duration

    def GetMediaPoolItem(self) -> Media | None:
        return self.media

    def GetSourceStartFrame(self) -> int:
        return self.source_start

    def GetSourceEndFrame(self) -> int:
        return self.source_start + self.duration - 1

    def GetMarkers(self) -> dict[int, dict[str, Any]]:
        return copy.deepcopy(self.markers)

    def GetMarkerCustomData(self, frame: int) -> str:
        return str(self.markers.get(frame, {}).get("customData", ""))

    def DeleteMarkerAtFrame(self, frame: int) -> bool:
        return self.markers.pop(frame, None) is not None

    def AddMarker(
        self, frame: int, color: str, name: str, note: str, duration: int, data: str
    ) -> bool:
        if frame in self.markers:
            return False
        self.markers[frame] = {"customData": data, "name": name, "note": note}
        return True

    def GetProperties(self) -> dict[str, Any]:
        return dict(self.properties)

    def GetFusionCompCount(self) -> int:
        return 0

    def GetNodeGraph(self) -> Item:
        return self

    def GetNumNodes(self) -> int:
        return self.nodes

    def GetTakesCount(self) -> int:
        return len(self.takes)

    def AddTake(self, media: Media, start: int, end: int) -> bool:
        if not self.takes:
            self.takes.append({"mediaPoolItem": self.media, "start": self.source_start})
        self.takes.append({"mediaPoolItem": media, "start": start})
        return True

    def GetTakeByIndex(self, index: int) -> dict[str, Any]:
        return self.takes[index - 1]

    def SelectTakeByIndex(self, index: int) -> bool:
        take = self.takes[index - 1]
        # The clip holds its own reference, not the caller's pool handle.
        self.media, self.source_start = Media(take["mediaPoolItem"].name), take["start"]
        return True

    def FinalizeTake(self) -> bool:
        if self.finalize_ok:
            self.takes = []
        return self.finalize_ok


class Timeline:
    def __init__(self, project: Project, name: str, uid: str, length: int) -> None:
        self.project, self.name, self.uid, self.length = project, name, uid, length
        self.tracks: dict[tuple[str, int], list[Item]] = {("video", 1): []}

    def GetName(self) -> str:
        return self.name

    def GetUniqueId(self) -> str:
        return self.uid

    def GetStartFrame(self) -> int:
        return 0

    def GetEndFrame(self) -> int:
        return self.length

    def GetMarkers(self) -> dict[int, Any]:
        return {}

    def GetTrackCount(self, kind: str) -> int:
        return max((index for k, index in self.tracks if k == kind), default=0)

    def GetItemListInTrack(self, kind: str, index: int) -> list[Item]:
        return list(self.tracks.get((kind, index), []))

    def DuplicateTimeline(self, name: str) -> Timeline:
        clone = Timeline(self.project, name, f"{self.uid}-copy", self.length)
        for slot, items in self.tracks.items():
            clone.tracks[slot] = []
            for item in items:
                twin = copy.copy(item)
                twin.uid = f"{item.uid}-copy"
                twin.markers = copy.deepcopy(item.markers)
                # Resolve omits default-valued audio settings on a fresh copy.
                twin.properties = {k: v for k, v in item.properties.items() if v}
                twin.takes = list(item.takes)
                clone.tracks[slot].append(twin)
        self.project.timelines.append(clone)
        self.project.current = clone
        return clone


class Project:
    def __init__(self) -> None:
        self.timelines: list[Timeline] = []
        self.current: Timeline | None = None
        self.imported: list[str] = []

    def GetName(self) -> str:
        return "P"

    def GetUniqueId(self) -> str:
        return "p-uid"

    def GetTimelineCount(self) -> int:
        return len(self.timelines)

    def GetTimelineByIndex(self, index: int) -> Timeline:
        return self.timelines[index - 1]

    def GetCurrentTimeline(self) -> Timeline | None:
        return self.current

    def SetCurrentTimeline(self, timeline: Timeline) -> bool:
        self.current = timeline
        return True

    def GetMediaPool(self) -> Project:
        return self

    def GetRootFolder(self) -> str:
        return "root"

    def AddSubFolder(self, _parent: str, name: str) -> str:
        return name

    def SetCurrentFolder(self, _folder: str) -> bool:
        return True

    def ImportMedia(self, paths: list[str]) -> list[Media]:
        self.imported.extend(paths)
        self.handles = [Media(Path(path).stem) for path in paths]
        return self.handles


class Resolve:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.version = [21, 1, 1, 10, ""]
        self.saves = self.reopens = 0

    def IsStudio(self) -> bool:
        return True

    def GetVersion(self) -> list[Any]:
        return self.version

    def GetProjectManager(self) -> Resolve:
        return self

    def GetCurrentProject(self) -> Project:
        return self.project

    def SaveProject(self) -> bool:
        self.saves += 1
        return True

    def CloseProject(self, project: Project) -> bool:
        for handle in getattr(project, "handles", []):
            handle.stale = True
        return True

    def LoadProject(self, _name: str) -> Project:
        self.reopens += 1
        return self.project


def _build(
    build: str,
    pictures: dict[str, tuple[str, int]],
    *,
    order: tuple[str, ...] = ROWS,
    transitions: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """A document, manifest and delivery view with one picture per row."""
    events, view_events, sources, start = [], [], {}, 0
    for row in order:
        name, length = pictures[row]
        original = {
            "eventId": f"event-{row}",
            "kind": "primary_visual",
            "trackId": "v",
            "provenance": {
                "documentId": DOCUMENT,
                "blockId": row,
                "sourceId": f"src-{name}",
                "deliveredSourceHash": f"sha256:{name}",
            },
            "recordRange": {"startFrame": start, "endFrame": start + length},
            "sourceRange": {"startFrame": 0, "endFrame": length},
        }
        events.append(original)
        view_events.append(
            {
                "id": original["eventId"],
                "sourceId": f"src-{name}",
                "kind": "primary_visual",
                "trackId": "v",
                "trackKind": "video",
                "recordRange": {"startFrame": start, "durationFrames": length},
                "sourceRange": {"startFrame": 0, "durationFrames": length},
                "v2Event": original,
            }
        )
        sources[f"src-{name}"] = {
            "id": f"src-{name}",
            "kind": "video",
            "path": f"Media/Resolved/{name}.mp4",
            "contentHash": f"sha256:{name}",
        }
        start += length
    document = {
        "schemaVersion": "script-document/v2",
        "id": DOCUMENT,
        "projectId": "project-1",
        "activeDraft": {
            "blocks": [
                {"type": "visual_only", "id": row, "text": f"About {row}"}
                for row in order
            ]
        },
    }
    manifest = {
        "schemaVersion": "timeline-manifest/v2",
        "id": f"manifest-{build}",
        "buildId": build,
        "document": {
            "documentId": DOCUMENT,
            "projectId": "project-1",
            "revision": 1,
            "contentHash": f"sha256:{build}",
        },
        "tracks": [{"id": "v"}],
        "events": events,
        "transitions": transitions or [],
    }
    view = {
        "timeline": {"startFrame": 0, "durationFrames": start},
        "tracks": [{"id": "v", "kind": "video", "index": 1, "name": "Video"}],
        "events": view_events,
        "sources": list(sources.values()),
        "markers": [],
    }
    return document, manifest, view


class Case:
    """A built and finished timeline plus a changed script."""

    def __init__(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        changed: dict[str, tuple[str, int]],
        **current: Any,
    ) -> None:
        original = {row: (f"clip-{row}", 10) for row in ROWS}
        document, manifest, view = _build("build-1", original)
        self.old_view = view
        self.document, self.manifest, self.view = _build(
            "build-2", {**original, **changed}, **current
        )
        self.project = Project()
        self.timeline = Timeline(self.project, "T", "t-uid", 30)
        self.project.timelines.append(self.timeline)
        self.project.current = self.timeline
        for event in view["events"]:
            self.timeline.tracks["video", 1].append(
                Item(
                    f"native-{event['id']}",
                    event["recordRange"]["startFrame"],
                    10,
                    Media(event["sourceId"].removeprefix("src-")),
                    _stamp(event),
                )
            )
        self.resolve = Resolve(self.project)
        self.baseline = tmp_path / "baseline"
        (self.baseline / "Builds" / "build-1").mkdir(parents=True)
        (self.baseline / "Builds" / "build-1" / "script-document.json").write_text(
            json.dumps(document)
        )
        saved = make_row_timeline_map(
            manifest,
            view,
            [
                {
                    "eventId": event["id"],
                    "resolveItemId": item.uid,
                    "trackId": "v",
                    "trackKind": "video",
                    "trackIndex": 1,
                    "startFrame": item.start,
                    "durationFrames": 10,
                    **observe_item_details(item),
                }
                for event, item in zip(
                    view["events"], self.timeline.tracks["video", 1], strict=True
                )
            ],
            project_name="P",
            resolve_project_id="p-uid",
            timeline_name="T",
            timeline_id="t-uid",
            version=2,
        )
        (self.baseline / "row-timeline-map.json").write_text(json.dumps(saved))
        self.output = tmp_path / "update"
        self.script = tmp_path / "script.json"
        self.script.write_text(json.dumps(self.document))
        self.package = package = SimpleNamespace(
            root=self.baseline,
            manifest=manifest,
            view=view,
            attestation={"timelineName": "T", "buildId": "build-1"},
        )
        monkeypatch.setattr(cli, "_load_readback_package", lambda _root: package)
        monkeypatch.setattr(
            cli,
            "exclusive_resolve_build",
            lambda: exclusive_resolve_build(tmp_path / "resolve.lock"),
        )

    def prepare(self, options: cli.UpdateOptions, _timings: Any) -> Any:
        options.output.mkdir()
        media = options.output / "package" / "Media" / "Resolved"
        media.mkdir(parents=True)
        for source in self.view["sources"]:
            (options.output / "package" / source["path"]).write_bytes(b"picture")
        return SimpleNamespace(
            root=options.output / "package", manifest=self.manifest, view=self.view
        )

    def run(self, choice: Any, **extra: Any) -> dict[str, Any]:
        self.said: list[str] = []
        return cli.update_once(
            cli.UpdateOptions(self.baseline, self.script, self.output),
            lambda _plans: choice,
            emit=self.said.append,
            resolve_factory=lambda: self.resolve,
            prepare=self.prepare,
            now=lambda: datetime(2026, 11, 14, 9, 30, 0),
            **extra,
        )

    def clip(self, row: str) -> Item:
        return next(
            item
            for item in self.timeline.tracks["video", 1]
            if item.uid == f"native-event-{row}"
        )

    def read(self, name: str) -> Any:
        return json.loads((self.output / name).read_text())


SWAP = {"row-2": ("new-picture", 10)}


def test_nothing_agreed_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, SWAP)
    report = case.run(None)
    assert report["status"] == "unchanged"
    assert report["rowsOutOfSync"][0]["label"].startswith("Row 2")
    assert len(case.project.timelines) == 1
    assert case.clip("row-2").media.name == "clip-row-2"  # type: ignore[union-attr]
    assert case.resolve.saves == 0 and not case.project.imported
    assert "Safe to update" in case.said[0]
    assert not (case.output / "update-plan.json").exists()


def test_same_length_swap_updates_one_row_and_keeps_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, SWAP)
    graded = case.clip("row-1")
    graded.nodes, graded.properties["ZoomX"] = 3, 1.4
    report = case.run("safe")
    assert report["status"] == "updated"
    assert [row["label"] for row in report["rowsUpdated"]] == ["Row 2 “About row-2”"]
    assert report["archiveTimeline"] == "T archive 2026-11-14 093000"
    swapped = case.clip("row-2")
    assert swapped.media.name == "new-picture"  # type: ignore[union-attr]
    assert (swapped.start, swapped.duration, swapped.takes) == (10, 10, [])
    assert (graded.nodes, graded.properties["ZoomX"]) == (3, 1.4)
    assert case.clip("row-3").media.name == "clip-row-3"  # type: ignore[union-attr]
    archive = case.project.timelines[1]
    assert archive.name == report["archiveTimeline"]
    assert [item.media.name for item in archive.tracks["video", 1]] == [  # type: ignore[union-attr]
        "clip-row-1",
        "clip-row-2",
        "clip-row-3",
    ]
    assert case.project.current is case.timeline
    assert case.resolve.reopens == 1
    attempt = case.read("update-attempt.json")
    assert attempt["completed"] and attempt["outcomes"][0]["status"] == "verified"
    # The update folder is now a baseline the read-back accepts unchanged.
    assert report["baselineComplete"]
    new_map = case.read("row-timeline-map.json")
    assert case.read("timeline-update.json")["timelineName"] == "T"
    observed = observe_current(case.resolve, new_map, case.view)
    assert observed["differenceCount"] == 0


def test_longer_row_and_the_rows_after_it_are_refused_with_the_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, {"row-2": ("clip-row-2", 14)})
    report = case.run("safe")
    assert report["status"] == "unchanged"
    reasons = {row["label"][:5]: row["reason"] for row in report["rowsRefused"]}
    assert "changes length from 10 to 14" in reasons["Row 2"]
    assert "would move 4 frames" in reasons["Row 3"]
    assert "cannot move or trim" in reasons["Row 3"]
    assert len(case.project.timelines) == 1
    with pytest.raises(NeedsAction, match="cannot be updated"):
        Case(tmp_path / "again", monkeypatch, {"row-2": ("clip-row-2", 14)}).run(["2"])


def test_reorder_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case = Case(tmp_path, monkeypatch, {}, order=("row-2", "row-1", "row-3"))
    report = case.run("safe")
    assert report["status"] == "unchanged"
    assert any("changed position" in row["reason"] for row in report["rowsRefused"])


def test_conflict_row_needs_naming_and_is_reported_out_of_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, SWAP)
    editor = Item("editor-clip", 12, 4, Media("b-roll"))
    case.timeline.tracks["video", 2] = [editor]
    report = case.run("safe")
    assert report["status"] == "unchanged"
    assert report["rowsOutOfSync"][0]["reason"] == "In conflict and not named."
    assert "In conflict" in case.said[0]
    assert len(case.project.timelines) == 1

    named = Case(tmp_path / "named", monkeypatch, SWAP)
    named.timeline.tracks["video", 2] = [Item("editor-clip", 12, 4, Media("b-roll"))]
    report = named.run(["2"])
    assert report["status"] == "updated"
    assert named.clip("row-2").media.name == "new-picture"  # type: ignore[union-attr]
    kept = named.timeline.tracks["video", 2][0]
    assert (kept.start, kept.duration, kept.media.name) == (12, 4, "b-roll")  # type: ignore[union-attr]


def test_hand_moved_clip_cannot_be_swapped_even_when_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, SWAP)
    case.clip("row-2").source_start = 3
    with pytest.raises(NeedsAction, match="by hand in Resolve"):
        case.run(["2"])
    assert len(case.project.timelines) == 1


def _transition(build_row: str = "row-2", duration: int = 4) -> dict[str, Any]:
    return {
        "id": "dissolve-1",
        "fromRowId": "row-1",
        "toRowId": "row-2",
        "trackId": "v",
        "boundaryFrame": 10,
        "outgoingEventId": "event-row-1",
        "incomingEventId": f"event-{build_row}",
        "requestedDurationFrames": duration,
        "alignment": "center",
        "startFrame": 10 - duration // 2,
        "endFrame": 10 + duration // 2,
        "disposition": "apply",
    }


def test_row_with_a_transition_is_updated_and_the_transition_stays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, SWAP, transitions=[_transition()])
    case.package.manifest = {**case.package.manifest, "transitions": [_transition()]}
    dissolve = Item("dissolve", 8, 4, None)
    case.timeline.tracks["video", 1].insert(1, dissolve)
    report = case.run("safe")
    assert report["status"] == "updated"
    assert any("transition" in line for line in case.said[0].splitlines())
    assert dissolve in case.timeline.tracks["video", 1]
    assert (dissolve.start, dissolve.duration) == (8, 4)


def test_changed_transition_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, SWAP, transitions=[_transition()])
    report = case.run("safe")
    assert report["status"] == "unchanged"
    assert {row["label"][:5] for row in report["rowsRefused"]} == {"Row 1", "Row 2"}
    assert "transition" in report["rowsRefused"][0]["reason"]


def test_unconfirmed_write_stops_and_is_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, SWAP)
    case.clip("row-2").finalize_ok = False
    with pytest.raises(UncertainResult, match="do not run the update again"):
        case.run("safe")
    assert case.read("update-attempt.json")["outcomes"][0]["status"] == "uncertain"
    report = case.read("update-report.json")
    assert report["status"] == "uncertain"
    assert report["rowsUncertain"][0]["rowId"] == "row-2"
    assert len(case.project.timelines) == 2  # The archive is the way back.
    assert case.resolve.reopens == 0
    assert not (case.output / "row-timeline-map.json").exists()


def test_timeline_edited_while_plan_is_shown_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, SWAP)

    def choose(_plans: Any) -> str:
        case.clip("row-1").properties["ZoomX"] = 2.0
        return "safe"

    with pytest.raises(NeedsAction, match="changed while the plan was shown"):
        cli.update_once(
            cli.UpdateOptions(case.baseline, case.script, case.output),
            choose,
            emit=lambda _: None,
            resolve_factory=lambda: case.resolve,
            prepare=case.prepare,
        )
    assert len(case.project.timelines) == 1


def test_row_left_out_stays_out_of_sync_and_keeps_the_earlier_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, {**SWAP, "row-3": ("another-picture", 10)})
    report = case.run(["2"])
    assert report["status"] == "updated"
    assert [row["rowId"] for row in report["rowsUpdated"]] == ["row-2"]
    assert [row["rowId"] for row in report["rowsOutOfSync"]] == ["row-3"]
    assert case.clip("row-3").media.name == "clip-row-3"  # type: ignore[union-attr]
    assert not report["baselineComplete"]
    assert not (case.output / "row-timeline-map.json").exists()
    assert "earlier baseline" in case.said[-1]


def test_other_resolve_version_is_refused_before_any_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, SWAP)
    case.resolve.version = [21, 1, 2, 3, ""]
    with pytest.raises(NeedsAction, match="only been measured"):
        case.run("safe")


def test_non_picture_change_is_refused() -> None:
    document, manifest, view = _build("b1", {row: (row, 10) for row in ROWS})
    _, new_manifest, new_view = _build("b2", {**{r: (r, 10) for r in ROWS}})
    view["events"][1]["v2Event"]["kind"] = "narration"
    new_view["events"][1]["v2Event"]["kind"] = "narration"
    new_view["events"][1]["v2Event"]["provenance"]["deliveredSourceHash"] = "other"
    row = {
        "rowId": "row-2",
        "scriptChange": "changed",
        "reordered": False,
        "shiftFrames": 0,
        "baselineStartFrame": 10,
        "baselineEndFrame": 20,
        "currentStartFrame": 10,
        "currentEndFrame": 20,
        "state": "script_changed",
        "reason": "",
        "hazards": [],
    }
    plans = planning.plan_rows(
        baseline_manifest=manifest,
        baseline_view=view,
        baseline_document=document,
        current_manifest=new_manifest,
        current_view=new_view,
        current_document=document,
        saved_map={
            "rows": [{"items": [{"eventId": "event-row-2", "resolveItemId": "uid-2"}]}]
        },
        comparison={"rows": [row]},
        observation={
            "rows": [{"items": [{"resolveItemId": "uid-2", "status": ["unchanged"]}]}]
        },
        takes={"uid-2": 0},
    )
    assert "narration, music" in plans[0]["refusal"]
    assert plans[0]["edits"] == []


def test_plan_and_attempt_match_the_contract_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The TypeScript #328 contract loads this same file; see its test."""
    case = Case(tmp_path, monkeypatch, {**SWAP, "row-3": ("clip-row-3", 12)})
    case.run("safe")
    attempt = case.read("update-attempt.json")
    assert attempt["plan"]["hash"] == planning.outbound_hash(
        {key: value for key, value in attempt["plan"].items() if key != "hash"}
    )
    assert [item["disposition"] for item in attempt["plan"]["changes"]] == [
        "selected",
        "blocked",
    ]
    if os.environ.get("VERA_WRITE_UPDATE_FIXTURE") == "1":
        FIXTURE.write_text(json.dumps(attempt, sort_keys=True, indent=2) + "\n")
    assert json.loads(FIXTURE.read_text()) == attempt
