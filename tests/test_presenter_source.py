"""Presenter grade source (#94) against a small stand-in for Resolve.

The stand-in copies what Studio 21.1.1 build 10 did in the live check: a new
timeline's A1 is stereo, CreateCompoundClip returns nothing for picture plus
sound although it works, and audio items answer False for picture properties.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import presenter_source as ps

RATE = Fraction(30000, 1001)
START = 108000


class Clip:
    def __init__(
        self, name: str, kind: str, size: str, frames: int, path: str = ""
    ) -> None:
        self.name = name
        self.props = {
            "Type": kind,
            "Resolution": size,
            "Frames": str(frames),
            "File Path": path,
        }

    def GetName(self) -> str:
        return self.name

    def GetClipProperty(self, key: str) -> str:
        return self.props[key]


class Item:
    def __init__(self, clip: Clip, kind: str, start: int, end: int, record: int):
        self.clip, self.kind = clip, kind
        self.left, self.length, self.record = start, end - start, record
        self.props: dict[str, float] = {"ZoomX": 1.0, "ZoomY": 1.0}

    def GetStart(self, _subframe: bool) -> int:
        return self.record

    def GetDuration(self, _subframe: bool) -> int:
        return self.length

    def GetLeftOffset(self, _subframe: bool) -> int:
        return self.left

    def GetMediaPoolItem(self) -> Clip:
        return self.clip

    def GetProperty(self, key: str) -> Any:
        return self.props[key] if self.kind == "video" else False

    def SetProperty(self, key: str, value: float) -> bool:
        if self.kind != "video":
            return False
        self.props[key] = value
        return True


class Timeline:
    def __init__(self, name: str, project: Project) -> None:
        self.name, self.project = name, project
        self.settings = dict(project.settings)
        self.audio_types = ["stereo"]
        self.tracks: dict[str, list[Item]] = {"video": [], "audio": []}

    def GetName(self) -> str:
        return self.name

    def GetStartFrame(self) -> int:
        return START

    def SetSetting(self, key: str, value: str) -> bool:
        self.settings[key] = value
        return True

    def GetSetting(self, key: str) -> str:
        return self.settings[key]

    def AddTrack(self, _kind: str, subtype: str) -> bool:
        self.audio_types.append(subtype)
        return True

    def DeleteTrack(self, _kind: str, index: int) -> bool:
        del self.audio_types[index - 1]
        return True

    def GetTrackSubType(self, _kind: str, index: int) -> str:
        return self.audio_types[index - 1]

    def GetItemListInTrack(self, kind: str, _index: int) -> list[Item]:
        return self.tracks[kind]

    def CreateCompoundClip(self, items: list[Item], info: dict[str, str]) -> None:
        if self.project.fail == "compound":
            return None
        size = (
            f"{self.settings['timelineResolutionWidth']}"
            f"x{self.settings['timelineResolutionHeight']}"
        )
        compound = Clip(info["name"], "Compound", size, items[0].length)
        for item in items:
            item.clip = compound
        return None


class Folder:
    def __init__(self, name: str) -> None:
        self.name = name
        self.folders: list[Folder] = []

    def GetName(self) -> str:
        return self.name

    def GetSubFolderList(self) -> list[Folder]:
        return self.folders


class Pool:
    def __init__(self, project: Project) -> None:
        self.project, self.root = project, Folder("Master")

    def GetRootFolder(self) -> Folder:
        return self.root

    def AddSubFolder(self, parent: Folder, name: str) -> Folder:
        parent.folders.append(Folder(name))
        return parent.folders[-1]

    def SetCurrentFolder(self, _folder: Folder) -> bool:
        return True

    def ImportMedia(self, paths: list[str]) -> list[Clip]:
        size, frames = self.project.media
        # Not in the order asked for: Resolve does not promise one.
        return [
            Clip(Path(paths[1]).name, "Audio", "", frames, paths[1]),
            Clip(Path(paths[0]).name, "Video + Audio", size, frames, paths[0]),
        ]

    def CreateEmptyTimeline(self, name: str) -> Timeline:
        timeline = Timeline(name, self.project)
        self.project.timelines.append(timeline)
        self.project.current = timeline
        return timeline

    def AppendToTimeline(self, infos: list[dict[str, Any]]) -> list[Item]:
        info = infos[0]
        timeline = self.project.current
        assert timeline is not None
        kinds = {1: ["video"], 2: ["audio"]}.get(
            info.get("mediaType", 0), ["video", "audio"]
        )
        made = [
            Item(
                info["mediaPoolItem"],
                kind,
                info["startFrame"],
                info["endFrame"],
                info["recordFrame"],
            )
            for kind in kinds
        ]
        for item in made:
            timeline.tracks[item.kind].append(item)
        return made[:1]


class Project:
    def __init__(self, name: str, media: tuple[str, int]) -> None:
        self.name, self.media = name, media
        self.settings = {
            "timelineFrameRate": "24",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
            "timelineInputResMismatchBehavior": "centerCrop",
        }
        self.timelines: list[Timeline] = []
        self.current: Timeline | None = None
        self.pool = Pool(self)
        self.fail = ""

    def GetName(self) -> str:
        return self.name

    def SetSetting(self, key: str, value: str) -> bool:
        self.settings[key] = value
        return True

    def GetSetting(self, key: str) -> str:
        return self.settings[key]

    def GetMediaPool(self) -> Pool:
        return self.pool

    def GetTimelineCount(self) -> int:
        return len(self.timelines)

    def GetTimelineByIndex(self, index: int) -> Timeline:
        return self.timelines[index - 1]

    def SetCurrentTimeline(self, timeline: Timeline) -> bool:
        self.current = timeline
        return True


class Resolve:
    """Also the project manager."""

    def __init__(self, media: tuple[str, int] = ("3840x2160", 7320)) -> None:
        self.media = media
        self.projects: dict[str, Project] = {}
        self.current: Project | None = None
        self.saved = self.closed = 0
        self.fail = ""

    def GetProjectManager(self) -> Resolve:
        return self

    def GetProjectListInCurrentFolder(self) -> list[str]:
        return list(self.projects)

    def CreateProject(self, name: str) -> Project:
        self.current = self.projects[name] = Project(name, self.media)
        self.current.fail = self.fail
        return self.current

    def GetCurrentProject(self) -> Project | None:
        return self.current

    def SaveProject(self) -> bool:
        self.saved += 1
        return True

    def CloseProject(self, _project: Project) -> bool:
        self.closed += 1
        self.current = None
        return True

    def LoadProject(self, name: str) -> Project:
        project = self.projects[name]
        if self.fail == "zoom lost on reopen":
            for timeline in project.timelines:
                for item in timeline.tracks["video"]:
                    item.props.update(ZoomX=1.0, ZoomY=1.0)
        self.current = project
        return project


def recording(width: int = 3840, height: int = 2160, frames: int = 7320) -> Any:
    return ps.Recording(
        Path("/media/semi1b.mp4"), Path("/media/clean.wav"), width, height, RATE, frames
    )


def test_tight_zoom_is_pixel_for_pixel_and_never_shrinks() -> None:
    assert ps.tight_zoom((3840, 2160), (1920, 1080)) == 2.0
    assert ps.tight_zoom((1920, 1080), (1920, 1080)) == 1.0
    assert ps.tight_zoom((1280, 720), (1920, 1080)) == 1.0


def test_cleaned_audio_must_match_the_video_length() -> None:
    samples = round(7320 / RATE * ps.AUDIO_RATE)
    ps.check_lengths(7320, RATE, samples)
    with pytest.raises(ps.SourceError, match="not the same length"):
        ps.check_lengths(7320, RATE, samples - ps.AUDIO_RATE)


def test_builds_a_full_size_source_and_framed_pieces_that_survive_reopen() -> None:
    resolve = Resolve()
    built = ps.build_source(resolve, recording(), project_name="P", sample=True)

    project = resolve.projects["P"]
    assert project.settings["timelineFrameRate"] == "29.97"
    assert project.settings["timelineInputResMismatchBehavior"] == "scaleToFit"
    assert (resolve.saved, resolve.closed) == (1, 1)
    source, sample = project.timelines
    assert project.current is source
    assert source.settings["timelineResolutionWidth"] == "3840"
    assert source.audio_types == ["mono"]
    assert [
        item.clip.name for item in source.tracks["video"] + source.tracks["audio"]
    ] == [
        "semi1b SOURCE",
        "semi1b SOURCE",
    ]
    tight, wide = sample.tracks["video"]
    assert (tight.props["ZoomX"], tight.props["ZoomY"]) == (2.0, 2.0)
    assert (wide.props["ZoomX"], wide.props["ZoomY"]) == (1.0, 1.0)
    assert [(item.left, item.record - START) for item in sample.tracks["audio"]] == [
        (piece.start, piece.offset) for piece in built.pieces
    ]
    text = ps.report(built)
    assert "zoom 2 (pixel for pixel)" in text
    assert "not 4K" not in text


def test_smaller_recording_is_built_at_its_own_size_and_says_so() -> None:
    resolve = Resolve(media=("1920x1080", 600))
    built = ps.build_source(
        resolve, recording(1920, 1080, 600), project_name="P", sample=True
    )
    source = resolve.projects["P"].timelines[0]
    assert source.settings["timelineResolutionHeight"] == "1080"
    text = ps.report(built)
    assert "1920x1080, not 4K" in text
    assert "tight and wide are the same picture" in text


@pytest.mark.parametrize(
    ("fail", "message"),
    [
        ("compound", "does not hold the whole picture"),
        ("zoom lost on reopen", "tight piece did not read back"),
    ],
)
def test_refuses_when_resolve_does_not_read_back_as_built(
    fail: str, message: str
) -> None:
    resolve = Resolve()
    resolve.fail = fail
    with pytest.raises(ps.SourceError, match=message):
        ps.build_source(resolve, recording(), project_name="P", sample=True)


def test_a_failed_build_says_what_it_left_behind() -> None:
    resolve = Resolve()
    resolve.fail = "compound"
    with pytest.raises(ps.SourceError, match='unfinished project "P" is left'):
        ps.build_source(resolve, recording(), project_name="P")


def test_refuses_an_existing_project_name_and_a_second_source() -> None:
    resolve = Resolve()
    ps.build_source(resolve, recording(), project_name="P")
    with pytest.raises(ps.SourceError, match="already exists"):
        ps.build_source(resolve, recording(), project_name="P")
    with pytest.raises(ps.SourceError, match="already has a source"):
        ps.build_source(resolve, recording(), project_name="P", existing_project=True)


def test_existing_project_must_be_open_and_at_the_recording_rate() -> None:
    resolve = Resolve()
    with pytest.raises(ps.SourceError, match="Open the project"):
        ps.build_source(resolve, recording(), project_name="P", existing_project=True)
    resolve.CreateProject("P")
    with pytest.raises(ps.SourceError, match=r"not 29\.97 fps"):
        ps.build_source(resolve, recording(), project_name="P", existing_project=True)
