"""Presenter timeline from approved takes (#48) against a stand-in for Resolve.

The stand-in copies what Studio 21.1.1 build 10 did in the live check: a
source placed with no media type lands its picture and linked sound on the
same track number, and only the picture answers for zoom.
"""

from __future__ import annotations

import copy
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from test_recorded_conform_cli import _case, _invoke
from vera_timeline_agent import presenter_conform as pc
from vera_timeline_agent import presenter_source as ps
from vera_timeline_agent.recorded_word_evidence import canonical_json, sha256

START = 86400
NAMES = ps.Names.of("made-up")


def _no_manifest(_script: Path, _dependencies: Path) -> dict[str, Any]:
    return {"ready": False, "diagnostics": [{"code": "PREPARATION_HASH_MISMATCH"}]}


def _frozen(tmp_path: Path, rate: int = 30) -> tuple[dict[str, Path], Path]:
    """A #47 snapshot of the shared sample, with the timeline at the camera rate."""
    paths, data = _case(tmp_path)
    data["dependencies"]["timeline"]["frameRate"] = {
        "numerator": rate,
        "denominator": 1,
    }
    prepared = paths["prepared"]
    (prepared / "compiler-dependencies.json").write_bytes(
        canonical_json(data["dependencies"])
    )
    old = [m["narrationAssetId"] for m in data["dependencies"]["narrationTimingMaps"]]
    (prepared / "media-paths.json").write_bytes(
        canonical_json({f"source:{asset}": f"/voice/{asset}.wav" for asset in set(old)})
    )
    out = paths["output_root"] / "frozen"
    _invoke(paths, out, _no_manifest)
    return paths, out


def _recording(paths: dict[str, Path], frames: int = 360) -> ps.Recording:
    return ps.Recording(
        paths["video"],
        paths["video"].with_name("clean.wav"),
        3840,
        2160,
        Fraction(30),
        frames,
    )


def _prepare(paths: dict[str, Path], frozen: Path, folder: Path, **more: Any) -> Any:
    return pc.prepare_inputs(
        frozen,
        paths["prepared"],
        more.pop("video", paths["video"]),
        paths["video"].with_name("clean.wav"),
        folder,
        probe_recording=lambda video, audio: _recording(paths, **more),
    )


def test_inputs_carry_recorded_timing_and_an_empty_presenter_track(
    tmp_path: Path,
) -> None:
    paths, frozen = _frozen(tmp_path)
    inputs = _prepare(paths, frozen, tmp_path / "build-inputs")

    built = json.loads((inputs.folder / "compiler-dependencies.json").read_bytes())
    by_id = {track["id"]: (track["kind"], track["index"]) for track in built["tracks"]}
    assert by_id[pc.PICTURE_TRACK] == ("video", 1)
    assert by_id[pc.SOUND_TRACK] == ("audio", 1)
    assert by_id["video-root"] == ("video", 2) and by_id["narration"] == ("audio", 2)
    assert "presenter" not in by_id  # the old empty presenter track is replaced
    assert built["roles"]["presenterTrackId"] == pc.PICTURE_TRACK
    assert built["roles"]["sourceAudioTrackIds"] == [pc.SOUND_TRACK]
    # row-1 is 60 camera frames, row-2 keeps its 4 s voice, row-3 is 90 frames.
    assert built["timeline"]["durationFrames"] == 60 + 120 + 90

    media = json.loads((inputs.folder / "media-paths.json").read_bytes())
    takes = [row for row in inputs.snapshot["rows"] if row["state"] == "take"]
    assert len(takes) == 2
    carriers = sorted((inputs.folder / "timing-carriers").glob("*.wav"))
    assert len(carriers) == 2 and set(map(str, carriers)) < set(media.values())
    kept = [
        row["oldNarrationAssetId"]
        for row in inputs.snapshot["rows"]
        if row["state"] == "temp_voice"
    ]
    assert [key for key in media if key.endswith(tuple(kept))] or not kept


def test_refuses_a_different_recording_by_name(tmp_path: Path) -> None:
    paths, frozen = _frozen(tmp_path)
    other = paths["video"].with_name("another-day.mov")
    other.write_bytes(b"not the approved recording")
    with pytest.raises(
        pc.ConformError, match=r'"another-day.mov" is not the recording'
    ):
        _prepare(paths, frozen, tmp_path / "build-inputs", video=other)
    assert not (tmp_path / "build-inputs").exists()


def test_refuses_a_timeline_at_another_frame_rate(tmp_path: Path) -> None:
    paths, frozen = _frozen(tmp_path, rate=24)
    with pytest.raises(pc.ConformError, match="24/1 fps and the recording is 30 fps"):
        _prepare(paths, frozen, tmp_path / "build-inputs")


def test_refuses_changed_snapshot_blocked_rows_and_other_prepared_inputs(
    tmp_path: Path,
) -> None:
    paths, frozen = _frozen(tmp_path)
    snapshot = json.loads((frozen / "snapshot.json").read_bytes())
    edited = copy.deepcopy(snapshot)
    edited["rows"][0]["framing"] = "tight"
    (frozen / "snapshot.json").write_bytes(canonical_json(edited))
    with pytest.raises(pc.ConformError, match="not an unchanged"):
        pc.load_snapshot(frozen)

    blocked = copy.deepcopy(snapshot)
    del blocked["snapshotSha256"]
    blocked["rows"][1]["state"] = "needs_pickup"
    blocked["snapshotSha256"] = sha256(canonical_json(blocked))
    (frozen / "snapshot.json").write_bytes(canonical_json(blocked))
    with pytest.raises(pc.ConformError, match=r"row-2 \(needs_pickup\)"):
        pc.load_snapshot(frozen)

    (frozen / "snapshot.json").write_bytes(canonical_json(snapshot))
    deps = paths["prepared"] / "compiler-dependencies.json"
    changed = json.loads(deps.read_bytes())
    changed["build"]["buildId"] = "00000000-0000-4000-8000-0000000000ff"
    deps.write_bytes(canonical_json(changed))
    with pytest.raises(pc.ConformError, match="not the ones the takes were frozen"):
        _prepare(paths, frozen, tmp_path / "build-inputs")


def test_names_a_clip_too_short_for_the_recorded_words(tmp_path: Path) -> None:
    paths, frozen = _frozen(tmp_path)
    impact = json.loads((frozen / "impact.json").read_bytes())
    impact["shortSources"] = [
        {
            "sourceId": "harbour-drone.mp4",
            "requiredRange": "0-90",
            "availableRange": "0-60",
        }
    ]
    (frozen / "impact.json").write_bytes(canonical_json(impact))
    with pytest.raises(pc.ConformError, match=r"harbour-drone.mp4.*Nothing is looped"):
        _prepare(paths, frozen, tmp_path / "build-inputs")


def test_take_outside_the_recording_is_refused(tmp_path: Path) -> None:
    paths, frozen = _frozen(tmp_path)
    with pytest.raises(pc.ConformError, match="row-3: the take is outside"):
        _prepare(paths, frozen, tmp_path / "build-inputs", frames=200)


# --- the Resolve step -------------------------------------------------------


class Clip:
    def __init__(self, name: str, kind: str = "Compound", frames: int = 360) -> None:
        self.name = name
        self.props = {"Type": kind, "Resolution": "3840x2160", "Frames": str(frames)}

    def GetName(self) -> str:
        return self.name

    def GetClipProperty(self, key: str) -> str:
        return self.props[key]


class Item:
    count = 0

    def __init__(self, clip: Clip, kind: str, left: int, length: int, record: int):
        Item.count += 1
        self.uid = f"item-{Item.count}"
        self.clip, self.kind = clip, kind
        self.left, self.length, self.record = left, length, record
        self.name, self.color = clip.name, ""
        self.props = {"ZoomX": 1.0, "ZoomY": 1.0}

    def GetUniqueId(self) -> str:
        return self.uid

    def GetStart(self, _subframe: bool) -> int:
        return self.record

    def GetDuration(self, _subframe: bool) -> int:
        return self.length

    def GetLeftOffset(self, _subframe: bool) -> int:
        return self.left

    def GetMediaPoolItem(self) -> Clip:
        return self.clip

    def GetName(self) -> str:
        return self.name

    def SetName(self, name: str) -> bool:
        self.name = name
        return True

    def GetClipColor(self) -> str:
        return self.color

    def SetClipColor(self, color: str) -> bool:
        self.color = color
        return True

    def GetProperty(self, key: str) -> Any:
        return self.props[key] if self.kind == "video" else False

    def SetProperty(self, key: str, value: float) -> bool:
        self.props[key] = value
        return self.kind == "video"


class Timeline:
    def __init__(self, name: str, start: int, size: tuple[int, int]) -> None:
        self.name, self.start = name, start
        self.settings = {
            "timelineResolutionWidth": str(size[0]),
            "timelineResolutionHeight": str(size[1]),
        }
        self.tracks: dict[str, list[list[Item]]] = {"video": [[]], "audio": [[]]}

    def GetName(self) -> str:
        return self.name

    def GetStartFrame(self) -> int:
        return self.start

    def GetSetting(self, key: str) -> str:
        return self.settings[key]

    def GetTrackCount(self, kind: str) -> int:
        return len(self.tracks[kind])

    def GetTrackSubType(self, _kind: str, _index: int) -> str:
        return "mono"

    def GetItemListInTrack(self, kind: str, index: int) -> list[Item]:
        return list(self.tracks[kind][index - 1])

    def DeleteClips(self, items: list[Item], _ripple: bool) -> bool:
        for lanes in self.tracks.values():
            for lane in lanes:
                lane[:] = [item for item in lane if item not in items]
        return True

    def add(
        self, kind: str, index: int, clip: Clip, left: int, length: int, at: int
    ) -> Item:
        lanes = self.tracks[kind]
        while len(lanes) < index:
            lanes.append([])
        item = Item(clip, kind, left, length, self.start + at)
        lanes[index - 1].append(item)
        return item


class Project:
    def __init__(self, name: str) -> None:
        self.name = name
        self.timelines: list[Timeline] = []
        self.current: Timeline | None = None
        self.lose = ""

    def GetName(self) -> str:
        return self.name

    def GetMediaPool(self) -> Project:
        return self

    def GetTimelineCount(self) -> int:
        return len(self.timelines)

    def GetTimelineByIndex(self, index: int) -> Timeline:
        return self.timelines[index - 1]

    def SetCurrentTimeline(self, timeline: Timeline) -> bool:
        self.current = timeline
        return True

    def AppendToTimeline(self, infos: list[dict[str, Any]]) -> list[Item]:
        info, timeline = infos[0], self.current
        assert timeline is not None
        return [
            timeline.add(
                kind,
                info["trackIndex"],
                info["mediaPoolItem"],
                info["startFrame"],
                info["endFrame"] - info["startFrame"],
                info["recordFrame"] - timeline.start,
            )
            for kind in ("video", "audio")
        ]


class Resolve:
    """Also the project manager."""

    def __init__(self, project: Project) -> None:
        self.project, self.saved = project, 0

    def GetProjectManager(self) -> Resolve:
        return self

    def GetCurrentProject(self) -> Project:
        return self.project

    def SaveProject(self) -> bool:
        self.saved += 1
        return True

    def CloseProject(self, _project: Project) -> bool:
        return True

    def LoadProject(self, _name: str) -> Project:
        project = self.project
        if project.lose == "zoom":
            for item in project.timelines[-1].tracks["video"][0]:
                item.props.update(ZoomX=1.0, ZoomY=1.0)
        if project.lose == "earlier":
            project.timelines[1].tracks["video"][0].pop()
        return project


SNAPSHOT: dict[str, Any] = {
    "rows": [
        {
            "rowId": "row-1",
            "blockId": "b1",
            "state": "take",
            "framing": "wide",
            "effectiveCut": {"startFrame": 60, "endFrame": 120},
        },
        {"rowId": "row-2", "blockId": "b2", "state": "temp_voice", "framing": "wide"},
        {
            "rowId": "row-3",
            "blockId": "b3",
            "state": "take",
            "framing": "tight",
            "effectiveCut": {"startFrame": 180, "endFrame": 270},
        },
    ]
}


def _event(
    event_id: str, kind: str, block: str, start: int, end: int, **more: Any
) -> dict[str, Any]:
    return {
        "eventId": event_id,
        "kind": kind,
        "provenance": {"blockId": block},
        "recordRange": {"startFrame": start, "endFrame": end},
        **more,
    }


STILL = {"pictureTreatment": {"kind": "still"}}
MANIFEST: dict[str, Any] = {
    "timeline": {"startFrame": 0},
    "events": [
        _event("n1", "narration", "b1", 0, 60),
        _event("oc1", "placeholder", "b1", 0, 25, **STILL),
        _event(
            "slate1", "placeholder", "b1", 25, 60, pictureTreatment={"kind": "slate"}
        ),
        _event("n2", "narration", "b2", 60, 180),
        _event("oc2", "placeholder", "b2", 60, 180, **STILL),
        _event("n3", "narration", "b3", 180, 270),
        _event("clip3", "primary_visual", "b3", 180, 270),
    ],
}
# event -> (kind, track) as the normal build delivers it after the relayout
WHERE = {"n": ("audio", 2), "o": ("video", 2), "s": ("video", 2), "c": ("video", 2)}


def _built() -> tuple[Resolve, Project, Timeline, dict[str, Any], ps.Recording]:
    """A project holding the source, an earlier edit and the normal build."""
    project = Project("P")
    source = Clip(NAMES.source)
    grade = Timeline(NAMES.grade_timeline, START, (3840, 2160))
    grade.add("video", 1, source, 0, 360, 0)
    grade.add("audio", 1, source, 0, 360, 0)
    earlier = Timeline("Temp voice cut", 0, (1920, 1080))
    earlier.add("video", 1, Clip("old.mp4", "Video"), 0, 100, 0)
    edit = Timeline("New cut", 0, (1920, 1080))
    rows: dict[str, list[dict[str, Any]]] = {}
    for event in MANIFEST["events"]:
        kind, index = WHERE[event["eventId"][0]]
        span = event["recordRange"]
        item = edit.add(
            kind,
            index,
            Clip(event["eventId"], "Video"),
            0,
            span["endFrame"] - span["startFrame"],
            span["startFrame"],
        )
        rows.setdefault(event["provenance"]["blockId"], []).append(
            {
                "eventId": event["eventId"],
                "resolveItemId": item.uid,
                "trackKind": kind,
                "trackIndex": index,
                "startFrame": span["startFrame"],
                "durationFrames": item.length,
            }
        )
    project.timelines = [grade, earlier, edit]
    row_map = {"rows": [{"rowId": key, "items": items} for key, items in rows.items()]}
    recording = ps.Recording(
        Path("/media/made-up.mov"),
        Path("/media/clean.wav"),
        3840,
        2160,
        Fraction(30),
        360,
    )
    return Resolve(project), project, edit, row_map, recording


def test_plan_puts_each_take_on_its_row_and_replaces_only_its_stand_ins() -> None:
    plan = pc.plan_takes(SNAPSHOT, MANIFEST)
    assert [(take.label, take.piece) for take in plan.takes] == [
        ("OC WIDE row-1", ps.Piece(60, 120, 0, "wide")),
        ("OC TIGHT row-3", ps.Piece(180, 270, 180, "tight")),
    ]
    # The slate on a word, the picture over row 3 and the whole temp-voice row stay.
    assert plan.replaced == ("n1", "oc1", "n3")

    longer = copy.deepcopy(MANIFEST)
    longer["events"][0]["recordRange"]["endFrame"] = 61
    with pytest.raises(pc.ConformError, match="row-1: the built row is not the length"):
        pc.plan_takes(SNAPSHOT, longer)


def test_takes_replace_the_stand_ins_and_survive_reopen() -> None:
    resolve, project, edit, row_map, recording = _built()
    plan = pc.plan_takes(SNAPSHOT, MANIFEST)
    pc.check_project(resolve, "P", recording)
    before = pc.other_timelines(project, "New cut")

    pc.conform_timeline(resolve, "P", "New cut", recording, plan, row_map, before)

    assert resolve.saved == 1 and project.current is edit
    picture, sound = edit.tracks["video"][0], edit.tracks["audio"][0]
    assert [
        (i.name, i.color, i.left, i.length, i.record, i.props["ZoomX"]) for i in picture
    ] == [
        ("OC WIDE row-1", "Blue", 60, 60, 0, 1.0),
        ("OC TIGHT row-3", "Orange", 180, 90, 180, 2.0),
    ]
    assert [(i.clip.name, i.left, i.record) for i in sound] == [
        (NAMES.source, 60, 0),
        (NAMES.source, 180, 180),
    ]
    assert [i.clip.name for i in edit.tracks["video"][1]] == ["slate1", "oc2", "clip3"]
    assert [i.clip.name for i in edit.tracks["audio"][1]] == ["n2"]


@pytest.mark.parametrize(
    ("lose", "message"),
    [("zoom", "row-3: the take did not read back"), ("earlier", "earlier timeline")],
)
def test_a_result_that_does_not_read_back_is_refused_and_named(
    lose: str, message: str
) -> None:
    resolve, project, _, row_map, recording = _built()
    project.lose = lose
    plan = pc.plan_takes(SNAPSHOT, MANIFEST)
    before = pc.other_timelines(project, "New cut")
    with pytest.raises(pc.ConformError, match=message) as refused:
        pc.conform_timeline(resolve, "P", "New cut", recording, plan, row_map, before)
    assert 'timeline "New cut" is left in "P"' in str(refused.value)


def test_a_project_without_the_recording_source_is_refused_before_building() -> None:
    resolve, project, _, _, recording = _built()
    project.timelines.pop(0)
    with pytest.raises(pc.ConformError, match=r'no source for "made-up\.mov"'):
        pc.check_project(resolve, "P", recording)
    project.name = "Other"
    with pytest.raises(pc.ConformError, match='Open the project "P"'):
        pc.check_project(resolve, "P", recording)


def test_report_lists_takes_and_rows_left_on_the_temporary_voice() -> None:
    plan = pc.plan_takes(SNAPSHOT, MANIFEST)
    text = pc.report(pc.Conformed("P", "New cut", plan.takes, ("row-2",)))
    assert "row-3: recording frames 180-270 at timeline frame 180, tight" in text
    assert "Still on the temporary voice: row-2." in text
