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
from vera_timeline_agent import timeline_baseline
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
        self.finalize_drops_markers = False
        self.handle = 100
        self.fades = {"FadeIn": 0.0, "FadeOut": 0.0}
        self.color = ""
        self.timeline: Timeline | None = None

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

    # Calls that exist from Resolve 21.1.2 on.
    def GetEnd(self, _subframe: bool = False) -> int:
        return self.start + self.duration

    def GetRightOffset(self) -> int:
        return self.handle

    def SetRightOffset(self, value: float) -> bool:
        if value < 0:
            return False
        self.duration += self.handle - int(value)
        self.handle = int(value)
        return True

    def SetPosition(self, position: dict[str, Any]) -> bool:
        assert self.timeline is not None
        for members in self.timeline.tracks.values():
            if self in members:
                members.remove(self)
        self.timeline.tracks.setdefault(("audio", position["trackIndex"]), []).append(
            self
        )
        self.start = int(position["startFrame"])
        return True

    def CopyAttributes(self, targets: list[Item], options: dict[str, bool]) -> bool:
        assert options == {"allAudioAttributes": True, "allClipAttributes": True}
        for target in targets:
            target.properties = dict(self.properties)
            target.markers = copy.deepcopy(self.markers)
        return True

    def GetFades(self) -> dict[str, float]:
        return dict(self.fades)

    def SetFades(self, fades: dict[str, float]) -> bool:
        self.fades = dict(fades)
        return True

    def GetClipColor(self) -> str:
        return self.color

    def SetClipColor(self, color: str) -> bool:
        self.color = color
        return True

    def ClearClipColor(self) -> bool:
        self.color = ""
        return True

    def AddTransition(self, options: dict[str, Any]) -> Item:
        assert self.timeline is not None and options["position"] == "end"
        half = options["duration"] // 2
        dissolve = Item(
            f"dissolve-{self.GetEnd()}", self.GetEnd() - half, half * 2, None
        )
        dissolve.timeline = self.timeline
        self.timeline.tracks["video", 1].append(dissolve)
        return dissolve

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
        if self.finalize_drops_markers:
            self.markers = {0: self.markers[0]}
        return self.finalize_ok


class Timeline:
    def __init__(self, project: Project, name: str, uid: str, length: int) -> None:
        self.project, self.name, self.uid, self.length = project, name, uid, length
        self.tracks: dict[tuple[str, int], list[Item]] = {("video", 1): []}
        self.markers: dict[int, Any] = {}

    def GetName(self) -> str:
        return self.name

    def GetUniqueId(self) -> str:
        return self.uid

    def GetStartFrame(self) -> int:
        return 0

    def GetEndFrame(self) -> int:
        return max(
            [self.length]
            + [m.GetEnd() for members in self.tracks.values() for m in members]
        )

    def GetMarkers(self) -> dict[int, Any]:
        return copy.deepcopy(self.markers)

    def DeleteMarkerAtFrame(self, frame: int) -> bool:
        return self.markers.pop(frame, None) is not None

    def AddMarker(
        self, frame: int, color: str, name: str, note: str, duration: int, data: str
    ) -> bool:
        if frame in self.markers:
            return False
        self.markers[frame] = {"color": color, "name": name, "customData": data}
        return True

    def _cuts(self) -> dict[Item, tuple[Item | None, Item | None]]:
        """Each transition with the clips on either side of its cut."""
        found = {}
        for members in self.tracks.values():
            for dissolve in (m for m in members if m.media is None):
                cut = dissolve.start + dissolve.duration // 2
                clips = [m for m in members if m.media is not None]
                found[dissolve] = (
                    next((c for c in clips if c.GetEnd() == cut), None),
                    next((c for c in clips if c.start == cut), None),
                )
        return found

    def MoveItems(
        self, items: list[Item], position: dict[str, float], linked: bool = True
    ) -> bool:
        assert linked is False
        delta = int(position["startFrame"]) - min(item.start for item in items)
        cuts = self._cuts()
        for members in self.tracks.values():
            for item in (m for m in members if m in items):
                for other in members:
                    if other in items or other.media is None:
                        continue
                    if (
                        item.start + delta < other.GetEnd()
                        and other.start < item.GetEnd() + delta
                    ):
                        return False  # Resolve refuses an overlapping move.
        for item in items:
            item.start += delta
        # A dissolve travels with a cut that stays closed and is lost otherwise.
        for dissolve, (left, right) in cuts.items():
            if left is not None and right is not None and left.GetEnd() == right.start:
                dissolve.start = right.start - dissolve.duration // 2
            else:
                for members in self.tracks.values():
                    if dissolve in members:
                        members.remove(dissolve)
        self.length = max(
            (m.GetEnd() for members in self.tracks.values() for m in members),
            default=0,
        )
        return True

    def AddTrack(self, kind: str) -> bool:
        self.tracks[kind, self.GetTrackCount(kind) + 1] = []
        return True

    def DeleteTrack(self, kind: str, index: int) -> bool:
        return self.tracks.pop((kind, index), None) == []

    def DeleteClips(self, items: list[Item], ripple: bool) -> bool:
        assert ripple is False
        for members in self.tracks.values():
            for item in items:
                if item in members:
                    members.remove(item)
        return True

    def GetTrackCount(self, kind: str) -> int:
        return max((index for k, index in self.tracks if k == kind), default=0)

    def GetItemListInTrack(self, kind: str, index: int) -> list[Item]:
        return list(self.tracks.get((kind, index), []))

    def DuplicateTimeline(self, name: str) -> Timeline:
        number = len(self.project.timelines)
        clone = Timeline(self.project, name, f"{self.uid}-copy{number}", self.length)
        for slot, items in self.tracks.items():
            clone.tracks[slot] = []
            for item in items:
                twin = copy.copy(item)
                twin.uid = f"{item.uid}-copy{number}"
                twin.markers = copy.deepcopy(item.markers)
                # Resolve omits default-valued audio settings on a fresh copy.
                twin.properties = {k: v for k, v in item.properties.items() if v}
                twin.takes = list(item.takes)
                twin.timeline = clone
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

    def AppendToTimeline(self, infos: list[dict[str, Any]]) -> list[Item]:
        assert self.current is not None
        info = infos[0]
        length = info["endFrame"] - info["startFrame"]
        item = Item(f"placed-{info['recordFrame']}", info["recordFrame"], length, None)
        item.media = Media(info["mediaPoolItem"].name)
        item.source_start = info["startFrame"]
        item.color = "Green"  # Seen on Studio 21.2: a placed tone arrives coloured.
        item.timeline = self.current
        self.current.tracks["audio", info["trackIndex"]].append(item)
        return [item]

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
    voices: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """A document, manifest and delivery view with one picture per row.

    ``voices`` adds a narration clip of the row's length under each picture.
    """
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
        if voices:
            voice = voices[row]
            spoken = {
                "eventId": f"voice-{row}",
                "kind": "narration",
                "trackId": "a",
                "provenance": {
                    "documentId": DOCUMENT,
                    "blockId": row,
                    "sourceId": f"src-{voice}",
                    "deliveredSourceHash": f"sha256:{voice}",
                },
                "recordRange": {"startFrame": start, "endFrame": start + length},
                "sourceRange": {"startFrame": 0, "endFrame": length},
            }
            events.append(spoken)
            view_events.append(
                {
                    "id": spoken["eventId"],
                    "sourceId": f"src-{voice}",
                    "kind": "narration",
                    "trackId": "a",
                    "trackKind": "audio",
                    "recordRange": {"startFrame": start, "durationFrames": length},
                    "sourceRange": {"startFrame": 0, "durationFrames": length},
                    "v2Event": spoken,
                }
            )
            sources[f"src-{voice}"] = {
                "id": f"src-{voice}",
                "kind": "audio",
                "path": f"Media/Narration/{voice}.wav",
                "contentHash": f"sha256:{voice}",
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
        "tracks": [{"id": "v"}, {"id": "a"}] if voices else [{"id": "v"}],
        "events": events,
        "transitions": transitions or [],
    }
    view = {
        "timeline": {"startFrame": 0, "durationFrames": start},
        "tracks": [
            {"id": "v", "kind": "video", "index": 1, "name": "Video"},
            *(
                [{"id": "a", "kind": "audio", "index": 1, "name": "Audio"}]
                if voices
                else []
            ),
        ],
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
        *,
        version: tuple[int, ...] = (21, 1, 1, 10),
        voices: dict[str, str] | None = None,
        new_voices: dict[str, str] | None = None,
        old_transitions: list[dict[str, Any]] | None = None,
        **current: Any,
    ) -> None:
        original = {row: (f"clip-{row}", 10) for row in ROWS}
        document, manifest, view = _build(
            "build-1", original, voices=voices, transitions=old_transitions
        )
        if voices:
            current["voices"] = new_voices or voices
        self.old_view = view
        self.document, self.manifest, self.view = _build(
            "build-2", {**original, **changed}, **current
        )
        self.project = Project()
        self.timeline = Timeline(self.project, "T", "t-uid", 30)
        self.project.timelines.append(self.timeline)
        self.project.current = self.timeline
        if voices:
            self.timeline.tracks["audio", 1] = []
        placed = []
        for event in view["events"]:
            item = Item(
                f"native-{event['id']}",
                event["recordRange"]["startFrame"],
                10,
                Media(event["sourceId"].removeprefix("src-")),
                _stamp(event),
            )
            item.timeline = self.timeline
            self.timeline.tracks[event["trackKind"], 1].append(item)
            placed.append(item)
        self.resolve = Resolve(self.project)
        self.resolve.version = [*version, ""]
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
                    "trackId": event["trackId"],
                    "trackKind": event["trackKind"],
                    "trackIndex": 1,
                    "startFrame": item.start,
                    "durationFrames": 10,
                    **observe_item_details(item),
                }
                for event, item in zip(view["events"], placed, strict=True)
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
        self.packages = {self.baseline: package}
        monkeypatch.setattr(
            timeline_baseline,
            "_load_readback_package",
            lambda root: self.packages[root],
        )
        monkeypatch.setattr(
            cli,
            "exclusive_resolve_build",
            lambda: exclusive_resolve_build(tmp_path / "resolve.lock"),
        )

    def prepare(self, options: cli.UpdateOptions, _timings: Any) -> Any:
        options.output.mkdir()
        build = self.manifest["buildId"]
        for folder in ("Media/Resolved", "Media/Narration", f"Builds/{build}"):
            (options.output / "package" / folder).mkdir(parents=True)
        (
            options.output / "package" / f"Builds/{build}/script-document.json"
        ).write_text(json.dumps(self.document))
        for source in self.view["sources"]:
            (options.output / "package" / source["path"]).write_bytes(b"picture")
        current = SimpleNamespace(
            root=options.output / "package",
            manifest=self.manifest,
            view=self.view,
            attestation={"timelineName": "new name", "buildId": build},
        )
        self.packages[options.output] = current
        return current

    def run(self, choice: Any, **extra: Any) -> dict[str, Any]:
        self.said: list[str] = []
        return cli.update_once(
            cli.UpdateOptions(self.baseline, self.script, self.output),
            lambda _plans: choice,
            emit=self.said.append,
            resolve_factory=lambda: self.resolve,
            prepare=self.prepare,
            now=lambda: datetime(2026, 11, 14, 9, 30, len(self.project.timelines) - 1),
            **extra,
        )

    def clip(self, row: str, kind: str = "event") -> Item:
        return next(
            item
            for members in self.timeline.tracks.values()
            for item in members
            if item.uid == f"native-{kind}-{row}"
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
    after = timeline_baseline.load_baseline(case.output)
    assert after.updated_in_place and after.saved["timelineName"] == "T"
    observed = observe_current(case.resolve, after.saved, after.view)
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
    assert not (case.output / "timeline-update.json").exists()


def test_losing_his_marker_on_the_swapped_clip_stops_the_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, SWAP)
    clip = case.clip("row-2")
    clip.markers[5] = {"name": "fix colour here", "customData": ""}
    clip.finalize_drops_markers = True
    with pytest.raises(UncertainResult, match="your markers"):
        case.run("safe")


def test_rows_named_out_of_order_are_applied_and_recorded_in_plan_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, {**SWAP, "row-3": ("another-picture", 10)})
    report = case.run(["3", "2"])
    assert [row["rowId"] for row in report["rowsUpdated"]] == ["row-2", "row-3"]
    attempt = case.read("update-attempt.json")
    first, second = (outcome["receipt"] for outcome in attempt["outcomes"])
    assert attempt["completed"] and first["after"] == second["before"]
    assert attempt["baseline"] == second["after"]


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
    assert "remembers them" in case.said[-1]

    # The partial update's folder is the baseline for finishing the job later.
    later = timeline_baseline.load_baseline(case.output)
    assert (
        observe_current(case.resolve, later.saved, later.view)["differenceCount"] == 0
    )
    case.baseline, case.output = case.output, tmp_path / "second"
    case.manifest = {**case.manifest, "buildId": "build-3"}
    report = case.run("safe")
    assert [row["rowId"] for row in report["rowsUpdated"]] == ["row-3"]
    assert report["baselineComplete"]
    assert case.clip("row-3").media.name == "another-picture"  # type: ignore[union-attr]
    assert case.clip("row-2").media.name == "new-picture"  # type: ignore[union-attr]
    assert len(case.project.timelines) == 3  # One archive per update.
    final = timeline_baseline.load_baseline(case.output)
    assert (
        observe_current(case.resolve, final.saved, final.view)["differenceCount"] == 0
    )


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


# --- Resolve Studio 21.2: rows may change length and later rows move in place.

V212 = (21, 2, 0, 6)
LONGER = {"row-2": ("clip-row-2", 14)}


def test_longer_row_moves_later_rows_in_place_and_keeps_their_finishing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, LONGER, version=V212)
    graded = case.clip("row-3")
    graded.nodes, graded.properties["ZoomX"] = 3, 1.4
    graded.markers[4] = {"name": "hand note", "customData": ""}
    editor = Item("editor-clip", 22, 4, Media("b-roll"))
    editor.timeline = case.timeline
    case.timeline.tracks["video", 2] = [editor]
    report = case.run("safe")
    assert report["status"] == "updated"
    assert [row["rowId"] for row in report["rowsUpdated"]] == ["row-2", "row-3"]
    assert "updated together" in case.said[0] and "10 to 14 frames" in case.said[0]
    grown = case.clip("row-2")
    assert (grown.start, grown.duration) == (10, 14)
    assert (graded.start, graded.duration) == (24, 10)
    assert (graded.nodes, graded.properties["ZoomX"]) == (3, 1.4)
    assert graded.markers[4]["name"] == "hand note"
    assert (editor.start, editor.duration) == (26, 4)  # It rode along with row 3.
    assert case.clip("row-1").start == 0
    assert len(case.project.timelines) == 2 and case.resolve.reopens == 1
    assert case.read("update-attempt.json")["completed"]
    after = timeline_baseline.load_baseline(case.output)
    assert after.manifest["buildId"] == "build-2"
    observed = observe_current(case.resolve, after.saved, after.view)
    assert observed["differenceCount"] == 1  # Only the clip he added himself.

    # A further edit starts from this update: row 2 goes back to its old length.
    case.baseline, case.output = case.output, tmp_path / "second"
    case.document, manifest, case.view = _build(
        "build-3", {row: (f"clip-{row}", 10) for row in ROWS}
    )
    case.manifest = manifest
    case.script.write_text(json.dumps(case.document))
    report = case.run("safe")
    assert report["status"] == "updated"
    assert (grown.duration, graded.start, editor.start) == (10, 20, 22)


def test_all_safe_rows_waits_when_a_row_of_a_length_change_is_in_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, LONGER, version=V212)
    editor = Item("editor-clip", 8, 4, Media("b-roll"))  # Across the 1|2 cut.
    editor.timeline = case.timeline
    case.timeline.tracks["video", 2] = [editor]
    report = case.run("safe")
    assert report["status"] == "unchanged" and len(case.project.timelines) == 1
    with pytest.raises(NeedsAction, match="Also name: Row 3"):
        Case(tmp_path / "one", monkeypatch, LONGER, version=V212).run(["2"])


def test_shorter_row_trims_first_and_pulls_later_rows_earlier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, {"row-1": ("clip-row-1", 6)}, version=V212)
    report = case.run("safe")
    assert report["status"] == "updated"
    assert [
        (item.start, item.duration) for item in case.timeline.tracks["video", 1]
    ] == [(0, 6), (6, 10), (16, 10)]
    assert case.timeline.GetEndFrame() == 26


def test_new_longer_narration_replaces_the_clip_and_carries_its_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    voices = {row: f"voice-{row}" for row in ROWS}
    case = Case(
        tmp_path,
        monkeypatch,
        LONGER,
        version=V212,
        voices=voices,
        new_voices={**voices, "row-2": "retake"},
    )
    old = case.clip("row-2", "voice")
    old.properties["AudioVolume"] = -6.0
    old.fades = {"FadeIn": 4.0, "FadeOut": 4.0}
    report = case.run("safe")
    assert report["status"] == "updated"
    assert any("new recording" in line for line in case.said[0].splitlines())
    tones = sorted(case.timeline.tracks["audio", 1], key=lambda item: item.start)
    assert [(t.start, t.duration) for t in tones] == [(0, 10), (10, 14), (24, 10)]
    new = tones[1]
    assert new is not old and new.media.name == "retake"  # type: ignore[union-attr]
    assert new.properties["AudioVolume"] == -6.0 and new.fades["FadeIn"] == 4.0
    assert new.color == "" and case.timeline.GetTrackCount("audio") == 1
    after = timeline_baseline.load_baseline(case.output)
    assert (
        observe_current(case.resolve, after.saved, after.view)["differenceCount"] == 0
    )


def test_script_transition_on_the_opened_cut_is_put_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = {
        **_transition(),
        "fromRowId": "row-2",
        "toRowId": "row-3",
        "boundaryFrame": 20,
        "outgoingEventId": "event-row-2",
        "incomingEventId": "event-row-3",
        "startFrame": 18,
        "endFrame": 22,
        "effectIdentity": {"name": "Cross Dissolve", "category": "simple"},
    }
    moved = {**plan, "boundaryFrame": 24, "startFrame": 22, "endFrame": 26}
    case = Case(
        tmp_path,
        monkeypatch,
        LONGER,
        version=V212,
        old_transitions=[plan],
        transitions=[moved],
    )
    dissolve = Item("dissolve", 18, 4, None)
    dissolve.timeline = case.timeline
    case.timeline.tracks["video", 1].append(dissolve)
    report = case.run("safe")
    assert report["status"] == "updated"
    assert any("puts the script's transition back" in line for line in case.said)
    spans = [
        (item.start, item.duration)
        for item in case.timeline.tracks["video", 1]
        if item.media is None
    ]
    assert spans == [(22, 4)] and dissolve not in case.timeline.tracks["video", 1]


def test_hand_made_transition_on_the_opened_cut_stops_before_any_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, LONGER, version=V212)
    dissolve = Item("dissolve", 18, 4, None)
    dissolve.timeline = case.timeline
    case.timeline.tracks["video", 1].append(dissolve)
    report = case.run("safe")
    assert report["status"] == "unchanged"
    assert "made by hand at frame 18" in report["rowsRefused"][0]["reason"]
    assert "Refused" in case.said[0]  # He sees it in the plan, before agreeing.
    assert len(case.project.timelines) == 1 and case.clip("row-2").duration == 10


def test_hand_made_transition_between_rows_that_move_together_goes_along(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, {"row-1": ("clip-row-1", 14)}, version=V212)
    dissolve = Item("dissolve", 18, 4, None)  # On the 2|3 cut at frame 20.
    dissolve.timeline = case.timeline
    case.timeline.tracks["video", 1].append(dissolve)
    report = case.run("safe")
    assert report["status"] == "updated"
    assert dissolve in case.timeline.tracks["video", 1]
    assert (dissolve.start, dissolve.duration) == (22, 4)


def test_reorder_and_hand_moved_later_clip_block_the_whole_length_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(
        tmp_path, monkeypatch, {}, version=V212, order=("row-2", "row-1", "row-3")
    )
    report = case.run("safe")
    assert report["status"] == "unchanged"
    assert any("reordering rows" in row["reason"] for row in report["rowsRefused"])

    moved = Case(tmp_path / "moved", monkeypatch, LONGER, version=V212)
    moved.clip("row-3").source_start = 3
    report = moved.run("safe")
    assert report["status"] == "unchanged"
    reasons = {row["rowId"]: row["reason"] for row in report["rowsRefused"]}
    assert "by hand in Resolve" in reasons["row-3"]
    assert "every changed row has to be updated together" in reasons["row-2"]
    assert len(moved.project.timelines) == 1


def test_same_length_swap_still_works_alone_on_the_newer_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = Case(tmp_path, monkeypatch, SWAP, version=V212)
    report = case.run("safe")
    assert report["status"] == "updated"
    assert case.clip("row-2").media.name == "new-picture"  # type: ignore[union-attr]
    assert timeline_baseline.load_baseline(case.output).updated_in_place
