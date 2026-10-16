"""Fake-only checks for audio-cases.py; never calls Resolve."""

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

import probe

spec = importlib.util.spec_from_file_location(
    "audio_cases", Path(__file__).with_name("audio-cases.py")
)
assert spec is not None and spec.loader is not None
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)

PROJECT_NAME = "VERA Issue 141 Synthetic Probe audio-check"
PROJECT_ID = "audio-check-project"
ENVIRONMENT = {"version": audio.PINNED_BUILD}
IDENTITY = {"projectId": PROJECT_ID}


class Media:
    def __init__(self, uid, filename, locator):
        self.uid, self.filename, self.locator = uid, filename, locator

    def GetUniqueId(self):
        return self.uid

    def GetClipProperty(self):
        return {"File Name": self.filename, "File Path": self.locator}


class Item:
    def __init__(self, uid, info, media, timeline):
        self.uid, self.info, self.media, self.timeline = uid, info, media, timeline
        self.enabled = info["enabled"]
        self.speed = {"Percentage": 100.0, "PitchCorrection": True}
        self.duration = info["duration"]
        self.end = info["end"]
        self.source_end = 199

    def GetUniqueId(self):
        return self.uid

    def GetMediaPoolItem(self):
        return self.media

    def GetTrackTypeAndIndex(self):
        return list(self.info["track"])

    def GetStart(self):
        return self.info["start"]

    def GetEnd(self):
        return self.end

    def GetDuration(self):
        return self.duration

    def GetSourceStartFrame(self):
        return 0

    def GetSourceEndFrame(self):
        return self.source_end

    def GetClipEnabled(self):
        return self.enabled

    def GetSpeed(self):
        return dict(self.speed)

    def GetMarkers(self):
        return {"0": {"customData": self.info["marker"]}}

    def SetClipEnabled(self, enabled):
        self.timeline.project.mutations.append(("SetClipEnabled", self.uid, enabled))
        self.enabled = enabled
        return not (self.timeline.project.fault == "partial-clip" and enabled)

    def SetSpeed(self, options):
        options = dict(options)
        percentage = options["Percentage"]
        assert options["RippleTimeline"] is False
        assert options["PitchCorrection"] is True
        self.timeline.project.mutations.append(("SetSpeed", self.uid, options))
        linked = self.timeline.project.linked(self.uid)
        factor = 100.0 / percentage
        for item in [self, *linked]:
            item.speed["Percentage"] = percentage
            if percentage == 100:
                item.duration = item.info["duration"]
                item.end = item.info["end"]
                item.source_end = 199
            else:
                item.duration = round(199 * factor)
                item.end = item.info["start"] + item.duration - 1
                item.source_end = min(199, round(199 / factor))
        return not (
            self.timeline.project.fault == "partial-speed" and percentage == 50.0
        )


class Timeline:
    def __init__(self, project):
        self.project = project
        self.current_timecode = "00:00:03:12"
        self.track_enabled = {
            (kind, index): True
            for kind, count in (("video", 3), ("audio", 3))
            for index in range(1, count + 1)
        }
        self.items = []

    def GetUniqueId(self):
        return audio.TIMELINE_ID

    def GetTrackCount(self, kind):
        return {"video": 3, "audio": 3, "subtitle": 0}[kind]

    def GetTrackName(self, kind, index):
        return f"{kind.title()} {index}"

    def GetTrackSubType(self, kind, index):
        assert kind == "audio"
        return "stereo" if index == 1 else "mono"

    def GetIsTrackLocked(self, _kind, _index):
        return False

    def GetIsTrackEnabled(self, kind, index):
        return self.track_enabled[(kind, index)]

    def SetTrackEnable(self, kind, index, enabled):
        self.project.mutations.append(("SetTrackEnable", kind, index, enabled))
        self.track_enabled[(kind, index)] = enabled
        return not (self.project.fault == "partial-track" and not enabled)

    def GetItemListInTrack(self, kind, index):
        return [item for item in self.items if item.info["track"] == (kind, index)]

    def GetCurrentTimecode(self):
        return self.current_timecode


class Project:
    def __init__(self, fault=None, *, timeline_id=None):
        self.name = PROJECT_NAME
        self.project_id = PROJECT_ID
        self.fault = fault
        self.mutations = []
        self.timeline = Timeline(self)
        if timeline_id is not None:
            self.timeline.GetUniqueId = lambda: timeline_id

    def GetName(self):
        return self.name

    def GetUniqueId(self):
        return self.project_id

    def GetCurrentTimeline(self):
        return self.timeline

    def linked(self, uid):
        if uid == audio.RETIME_VIDEO_ID:
            return [self.timeline.items_by_id[audio.RETIME_AUDIO_ID]]
        if uid == audio.RETIME_AUDIO_ID:
            return [self.timeline.items_by_id[audio.RETIME_VIDEO_ID]]
        return []


class Manager:
    def __init__(self, project):
        self.project = project

    def GetCurrentProject(self):
        return self.project


class Resolve:
    def __init__(self, project):
        self.manager = Manager(project)

    def GetProductName(self):
        return "DaVinci Resolve Studio"

    def GetProjectManager(self):
        return self.manager


def make_capture(project, source_paths):
    linked = {
        audio.RETIME_VIDEO_ID: [audio.RETIME_AUDIO_ID],
        audio.RETIME_AUDIO_ID: [audio.RETIME_VIDEO_ID],
        audio.RESIDUAL_ID: [],
    }
    tracks = []
    for kind, count in (("video", 3), ("audio", 3)):
        for index in range(1, count + 1):
            items = []
            for item in project.timeline.GetItemListInTrack(kind, index):
                info = item.info
                items.append(
                    {
                        "GetUniqueId": {"value": item.uid},
                        "GetName": {"value": info["filename"]},
                        "GetTrackTypeAndIndex": {"value": list(info["track"])},
                        "GetStart": {"value": info["start"]},
                        "GetEnd": {"value": item.end},
                        "GetEnd(True)": {"value": float(item.end)},
                        "GetDuration": {"value": item.duration},
                        "GetDuration(True)": {"value": float(item.duration)},
                        "GetLeftOffset": {"value": 0},
                        "GetLeftOffset(True)": {"value": 0.0},
                        "GetRightOffset": {"value": 0},
                        "GetRightOffset(True)": {"value": 0.0},
                        "GetSourceStartFrame": {"value": 0},
                        "GetSourceEndFrame": {"value": item.source_end},
                        "GetSourceStartTime": {"value": 0.0},
                        "GetSourceEndTime": {"value": item.source_end / 25},
                        "GetStart(True)": {"value": float(info["start"])},
                        "GetSpeed": {"value": dict(item.speed)},
                        "GetClipEnabled": {"value": item.enabled},
                        "GetMarkers": {"value": {"0": {"customData": info["marker"]}}},
                        "GetLinkedItems": [{"value": uid} for uid in linked[item.uid]],
                        "GetMediaPoolItem": {
                            "GetUniqueId": {"value": info["mediaUid"]},
                            "GetClipProperty": {
                                "value": {
                                    "File Name": info["filename"],
                                    "File Path": source_paths[info["filename"]],
                                }
                            },
                            "sourceBytes": {
                                "status": "reachable",
                                "sha256": hashlib.sha256(
                                    Path(source_paths[info["filename"]]).read_bytes()
                                ).hexdigest(),
                                "hashMatches": True,
                            },
                        },
                    }
                )
            tracks.append(
                {
                    "type": kind,
                    "index": index,
                    "GetTrackName": {"value": f"{kind.title()} {index}"},
                    "GetIsTrackEnabled": {
                        "value": project.timeline.track_enabled[(kind, index)]
                    },
                    "GetIsTrackLocked": {"value": False},
                    **(
                        {
                            "GetTrackSubType": {
                                "value": "stereo" if index == 1 else "mono"
                            }
                        }
                        if kind == "audio"
                        else {}
                    ),
                    "items": items,
                }
            )
    return {
        "projectId": PROJECT_ID,
        "projectName": PROJECT_NAME,
        "timelines": [
            {"GetUniqueId": {"value": probe.BASELINE_ID}, "tracks": []},
            {"GetUniqueId": {"value": probe.R1_ID}, "tracks": []},
            {"GetUniqueId": {"value": audio.TIMELINE_ID}, "tracks": tracks},
        ],
    }


def run_case(root, fault=None):
    output = root / "output"
    output.mkdir()
    project = Project(fault)
    media = {
        "base.mov": ("9202163a-8381-43e6-9157-3a60f35c6f79", "base bytes"),
        "repeated.wav": ("a7ad9e19-d49b-428b-9fd5-95c90d60e6f8", "audio bytes"),
    }
    source_paths = {}
    for filename, (_uid, contents) in media.items():
        path = root / filename
        path.write_bytes(contents.encode())
        source_paths[filename] = str(path)
    audio.SOURCE_HASHES = {
        name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
        for name, path in source_paths.items()
    }
    for uid, spec in audio.TARGETS.items():
        filename = spec["filename"]
        kind, index = spec["track"]
        info = {
            **spec,
            "track": (kind, index),
            "marker": spec["marker"],
            "filename": filename,
        }
        item = Item(
            uid,
            info,
            Media(spec["mediaUid"], filename, source_paths[filename]),
            project.timeline,
        )
        project.timeline.items.append(item)
    project.timeline.items_by_id = {item.uid: item for item in project.timeline.items}
    for uid, item in project.timeline.items_by_id.items():
        item.info["linkedIds"] = (
            [audio.RETIME_AUDIO_ID]
            if uid == audio.RETIME_VIDEO_ID
            else [audio.RETIME_VIDEO_ID]
            if uid == audio.RETIME_AUDIO_ID
            else []
        )
    if fault == "target":
        project.timeline.items_by_id[audio.RESIDUAL_ID].media.uid = "wrong-media"

    baseline = make_capture(project, source_paths)
    checkpoint_path = output / audio.PINNED_CAPTURE
    checkpoint_path.write_text(
        json.dumps(
            {"consistency": "equal-adjacent-reads", "passes": [baseline, baseline]}
        ),
        encoding="utf-8",
    )
    audio.PINNED_SHA256 = probe.sha256(checkpoint_path)
    calls = 0

    def fake_capture(_resolve, _config, _identity, _expected, _output, stamp, _env):
        nonlocal calls
        calls += 1
        value = make_capture(project, source_paths)
        if fault == "preflight" and calls == 1:
            value = {**value, "extra": True}
        path = output / f"capture-{stamp}.json"
        path.write_text(
            json.dumps(
                {"consistency": "equal-adjacent-reads", "passes": [value, value]}
            ),
            encoding="utf-8",
        )
        return {"status": "equal-adjacent-reads", "capturePath": str(path)}

    probe.capture = fake_capture
    result = audio.run(
        Resolve(project),
        {"projectName": PROJECT_NAME},
        IDENTITY,
        {path: audio.SOURCE_HASHES[name] for name, path in source_paths.items()},
        output,
        "fake",
        ENVIRONMENT,
        probe=probe,
    )
    return result, project


with tempfile.TemporaryDirectory() as directory:
    result, project = run_case(Path(directory))
    assert result["status"] == "candidate-audio-states-retained", result
    assert project.mutations == [
        ("SetClipEnabled", audio.RESIDUAL_ID, True),
        ("SetClipEnabled", audio.RESIDUAL_ID, False),
        ("SetTrackEnable", "audio", 2, False),
        ("SetTrackEnable", "audio", 2, True),
        (
            "SetSpeed",
            audio.RETIME_VIDEO_ID,
            {"Percentage": 50.0, "PitchCorrection": True, "RippleTimeline": False},
        ),
        (
            "SetSpeed",
            audio.RETIME_VIDEO_ID,
            {"Percentage": 100.0, "PitchCorrection": True, "RippleTimeline": False},
        ),
    ]
    assert all(
        item.enabled is audio.TARGETS[item.uid]["enabled"]
        for item in project.timeline.items
    )
    assert all(
        item.GetSpeed() == {"Percentage": 100.0, "PitchCorrection": True}
        for item in project.timeline.items
    )
    assert result["evidence"] and Path(result["evidence"]).is_file()

for fault in (
    "preflight",
    "target",
    "partial-clip",
    "partial-track",
    "partial-speed",
):
    with tempfile.TemporaryDirectory() as directory:
        result, project = run_case(Path(directory), fault=fault)
        assert result["status"] == "audio-cases-refused", result
        if fault in {"preflight", "target"}:
            assert project.mutations == []
        elif fault == "partial-clip":
            assert project.mutations == [
                ("SetClipEnabled", audio.RESIDUAL_ID, True),
                ("SetClipEnabled", audio.RESIDUAL_ID, False),
            ]
            assert project.timeline.items_by_id[audio.RESIDUAL_ID].enabled is False
        elif fault == "partial-track":
            assert project.mutations == [
                ("SetClipEnabled", audio.RESIDUAL_ID, True),
                ("SetClipEnabled", audio.RESIDUAL_ID, False),
                ("SetTrackEnable", "audio", 2, False),
                ("SetTrackEnable", "audio", 2, True),
            ]
            assert project.timeline.GetIsTrackEnabled("audio", 2) is True
        else:
            assert project.mutations == [
                ("SetClipEnabled", audio.RESIDUAL_ID, True),
                ("SetClipEnabled", audio.RESIDUAL_ID, False),
                ("SetTrackEnable", "audio", 2, False),
                ("SetTrackEnable", "audio", 2, True),
                (
                    "SetSpeed",
                    audio.RETIME_VIDEO_ID,
                    {
                        "Percentage": 50.0,
                        "PitchCorrection": True,
                        "RippleTimeline": False,
                    },
                ),
                (
                    "SetSpeed",
                    audio.RETIME_VIDEO_ID,
                    {
                        "Percentage": 100.0,
                        "PitchCorrection": True,
                        "RippleTimeline": False,
                    },
                ),
            ]
            assert all(
                item.GetSpeed() == {"Percentage": 100.0, "PitchCorrection": True}
                for item in project.timeline.items
            )

print("audio cases fake-native checks passed")
