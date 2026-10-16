"""Issue-owned fake injected runtime; never installed/real Studio evidence."""

from __future__ import annotations

import copy
import wave
from pathlib import Path
from typing import Any

from vera_timeline_agent.roundtrip_v2_records import JsonObject


class FakeItem:
    def __init__(self, event: JsonObject, source: JsonObject, root: Path) -> None:
        self.uid = "item:" + str(event["id"])
        self.source = source
        self.root = root
        self.start = int(event["recordRange"]["startFrame"])
        self.duration = int(event["recordRange"]["durationFrames"])
        self.source_start = int(event["sourceRange"]["startFrame"])
        self.source_end = (
            self.source_start + int(event["sourceRange"]["durationFrames"]) - 1
        )
        self.enabled = True
        self.links: list[FakeItem] = []

    def GetUniqueId(self) -> str:
        return self.uid

    def GetMediaPoolItem(self) -> Any:
        return self

    def GetClipProperty(self) -> JsonObject:
        return {
            "File Path": str(self.root / self.source["path"]),
            "Online Status": "Online",
        }

    def GetStart(self, _fractional: bool) -> int:
        return self.start

    def GetDuration(self, _fractional: bool) -> int:
        return self.duration

    def GetEnd(self, _fractional: bool) -> int:
        return self.start + self.duration

    def GetSourceStartFrame(self) -> int:
        return self.source_start

    def GetSourceEndFrame(self) -> int:
        return self.source_end

    def GetLinkedItems(self) -> list[FakeItem]:
        return self.links

    def GetClipEnabled(self) -> bool:
        return self.enabled

    def GetSpeed(self) -> JsonObject:
        return {
            "Percentage": 100.0,
            "PitchCorrection": False,
            "StretchKeyframesToFit": False,
            "RippleTimeline": False,
        }


class FakeTimeline:
    def __init__(self, package: Any) -> None:
        self.uid = "fake-timeline-uid"
        self.name = str(package.attestation["timelineName"])
        self.timeline = copy.deepcopy(package.manifest["timeline"])
        self.tracks = copy.deepcopy(package.view["tracks"])
        self.items: dict[tuple[str, int], list[FakeItem]] = {}
        self.mapping: JsonObject = {}
        for event in package.view["events"]:
            source = next(
                s for s in package.view["sources"] if s["id"] == event["sourceId"]
            )
            track = next(t for t in self.tracks if t["id"] == event["trackId"])
            item = FakeItem(event, source, package.root)
            self.items.setdefault((track["kind"], track["index"]), []).append(item)
            self.mapping[item.uid] = {"eventId": event["id"], "sourceId": source["id"]}
        self.markers: JsonObject = {}
        self.reads = 0
        self.drift_markers = False
        self.track_enabled = True
        self.track_locked = False

    def GetUniqueId(self) -> str:
        return self.uid

    def GetName(self) -> str:
        return self.name

    def GetSetting(self, key: str) -> str:
        if key == "timelineFrameRate":
            rate = self.timeline["frameRate"]
            return "23.976" if rate["denominator"] != 1 else str(rate["numerator"])
        return str(
            self.timeline[
                {
                    "timelineResolutionWidth": "width",
                    "timelineResolutionHeight": "height",
                    "timelineSampleRate": "audioSampleRate",
                }[key]
            ]
        )

    def GetStartFrame(self) -> int:
        return int(self.timeline["startFrame"])

    def GetEndFrame(self) -> int:
        return self.GetStartFrame() + int(self.timeline["durationFrames"])

    def GetTrackCount(self, kind: str) -> int:
        return sum(t["kind"] == kind for t in self.tracks)

    def GetTrackName(self, kind: str, index: int) -> str:
        return str(
            next(
                t["name"]
                for t in self.tracks
                if t["kind"] == kind and t["index"] == index
            )
        )

    def GetIsTrackEnabled(self, _kind: str, _index: int) -> bool:
        return self.track_enabled

    def GetIsTrackLocked(self, _kind: str, _index: int) -> bool:
        return self.track_locked

    def GetItemListInTrack(self, kind: str, index: int) -> list[FakeItem]:
        return self.items.get((kind, index), [])

    def GetMarkers(self) -> JsonObject:
        self.reads += 1
        return (
            {"read": self.reads} if self.drift_markers else copy.deepcopy(self.markers)
        )


def fake_controls(
    _project: Any, timeline: FakeTimeline, _target: JsonObject
) -> JsonObject:
    return {
        "programControls": {
            "gainDb": 0,
            "effects": [],
            "limiter": False,
            "automation": [],
            "destination": "stereo-program",
        },
        "routes": [
            {
                "itemUid": item.uid,
                "sourceId": timeline.mapping[item.uid]["sourceId"],
                "controls": {
                    "enabled": True,
                    "mute": False,
                    "solo": False,
                    "gainDb": 0,
                    "pan": 0,
                    "effects": [],
                    "sends": [],
                    "automation": [],
                    "destination": "stereo-program",
                    "channelMap": "mono-dual",
                },
            }
            for (kind, _), items in timeline.items.items()
            if kind == "audio"
            for item in items
        ],
    }


class FakeProject:
    def __init__(self, package: Any) -> None:
        self.uid = "fake-project-uid"
        self.name = str(package.attestation["projectName"])
        self.timeline = FakeTimeline(package)
        self.queue: list[JsonObject] = []
        self.settings: JsonObject = {}
        self.format: JsonObject = {}
        self.status = "Ready"
        self.calls: list[str] = []
        self.attack: str | None = None
        self.pending = False

    def GetUniqueId(self) -> str:
        return self.uid

    def GetName(self) -> str:
        return self.name

    def GetCurrentTimeline(self) -> FakeTimeline:
        return self.timeline

    def SetCurrentRenderFormatAndCodec(self, format_name: str, codec: str) -> bool:
        self.calls.append("format")
        self.format = {"format": format_name, "codec": codec}
        return self.attack != "format"

    def GetCurrentRenderFormatAndCodec(self) -> JsonObject:
        return dict(self.format)

    def SetRenderSettings(self, settings: JsonObject) -> bool:
        self.calls.append("settings")
        self.settings = dict(settings)
        return self.attack != "settings"

    def AddRenderJob(self) -> str:
        self.calls.append("add")
        s = self.settings
        job = {
            "JobId": "actual-fake-job",
            "TimelineName": self.name,
            "TargetDir": s["TargetDir"],
            "OutputFilename": s["CustomName"] + ".wav",
            "IsExportVideo": False,
            "IsExportAudio": True,
            "MarkIn": s["MarkIn"],
            "MarkOut": s["MarkOut"],
            "AudioBitDepth": 24,
            "AudioSampleRate": 48000,
            "AudioCodec": s["AudioCodec"],
            "RenderMode": "Single clip",
            "ReplaceExistingFilesInPlace": False,
        }
        if self.attack == "job-id":
            return "invented-id"
        if self.attack == "output":
            job["OutputFilename"] = "different.wav"
        if self.attack == "job-settings":
            job["AudioBitDepth"] = 16
        if self.attack == "unknown-control":
            del job["AudioSampleRate"]
        self.queue.append(job)
        return "actual-fake-job"

    def GetRenderJobList(self) -> list[JsonObject]:
        return copy.deepcopy(self.queue)

    def GetRenderJobStatus(self, job_id: str) -> JsonObject:
        assert job_id == "actual-fake-job"
        return {
            "JobStatus": self.status,
            "CompletionPercentage": 99
            if self.attack == "incomplete"
            else 100
            if self.status == "Complete"
            else 0,
        }

    def StartRendering(self, job_ids: list[str], interactive: bool) -> bool:
        assert job_ids == ["actual-fake-job"] and interactive is False
        self.calls.append("start")
        if self.attack == "uncertain":
            raise RuntimeError("fake disconnected after possible start")
        self.status = "Rendering" if self.pending else "Complete"
        if not self.pending:
            self.write_output()
        return True

    def write_output(self) -> None:
        output = Path(self.settings["TargetDir"]) / (
            self.settings["CustomName"] + ".wav"
        )
        count = (
            (self.settings["MarkOut"] - self.settings["MarkIn"] + 1)
            * 48000
            * self.timeline.timeline["frameRate"]["denominator"]
            // self.timeline.timeline["frameRate"]["numerator"]
        )
        if self.attack == "short":
            count -= 1
        with wave.open(str(output), "wb") as stream:
            stream.setnchannels(1 if self.attack == "mono" else 2)
            stream.setsampwidth(3)
            stream.setframerate(48000)
            stream.writeframes(b"\0" * count * (3 if self.attack == "mono" else 6))
        if self.attack == "truncated":
            output.write_bytes(output.read_bytes()[:-6])


class FakeResolve:
    def __init__(self, package: Any) -> None:
        self.project = FakeProject(package)

    def GetProductName(self) -> str:
        return "DaVinci Resolve Studio"

    def GetVersion(self) -> list[Any]:
        return [21, 1, 1, 10, ""]

    def GetProjectManager(self) -> FakeResolve:
        return self

    def GetCurrentProject(self) -> FakeProject:
        return self.project
