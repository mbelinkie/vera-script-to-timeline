"""Fake-native still calibration checks; never calls Resolve."""

import json
import tempfile
from copy import deepcopy
from pathlib import Path

import probe

ORIGINAL_PICTURE_CASES = deepcopy(probe.PICTURE_CASES)
TIMELINE_ID = "29ae8331-b86e-4041-a548-960695cc7b24"
PROJECT_ID = "project-test"
PROJECT_NAME = "VERA Issue 141 Synthetic Probe picture-check"
ENVIRONMENT = {"version": [21, 1, 0, 14, ""]}
IDENTITY = {"projectId": PROJECT_ID}
PASS = {
    "projectId": PROJECT_ID,
    "timelines": [
        {"GetUniqueId": {"value": probe.BASELINE_ID}},
        {"GetUniqueId": {"value": probe.R1_ID}},
        {"GetUniqueId": {"value": TIMELINE_ID}},
    ],
}


class FakeTimeline:
    def __init__(self, timeline_id):
        self.timeline_id = timeline_id
        self.timecode = "00:00:03:12"
        self.set_calls = []

    def GetUniqueId(self):
        return self.timeline_id

    def GetCurrentTimecode(self):
        return self.timecode

    def SetCurrentTimecode(self, timecode):
        self.set_calls.append(timecode)
        self.timecode = timecode
        return True


class FakeProject:
    def __init__(self, timeline):
        self.timeline = timeline
        self.exports = []

    def GetName(self):
        return PROJECT_NAME

    def GetUniqueId(self):
        return PROJECT_ID

    def GetCurrentTimeline(self):
        return self.timeline

    def ExportCurrentFrameAsStill(self, destination):
        path = Path(destination)
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake-image-data")
        self.exports.append(path)
        return True


class FakeManager:
    def __init__(self, project):
        self.project = project

    def GetCurrentProject(self):
        return self.project


class FakeResolve:
    def __init__(self, project):
        self.manager = FakeManager(project)

    def GetProjectManager(self):
        return self.manager

    def GetCurrentPage(self):
        return "edit"


def install_capture_stub(output, *, changed_first=False):
    calls = 0

    def capture(_resolve, _config, _identity, _expected, _output, stamp, _environment):
        nonlocal calls
        calls += 1
        value = PASS
        if changed_first and calls == 1:
            value = {**PASS, "changed": True}
        path = output / f"capture-{stamp}.json"
        path.write_text(json.dumps({"passes": [value, value]}), encoding="utf-8")
        return {
            "status": "equal-adjacent-reads",
            "capturePath": str(path),
            "sha256": probe.sha256(path),
        }

    probe.capture = capture


def run_case(root, *, changed_first=False, wrong_selection=False):
    output = root / "output"
    output.mkdir()
    capture_path = output / probe.PICTURE_CAPTURE
    capture_path.write_text(
        json.dumps({"consistency": "equal-adjacent-reads", "passes": [PASS, PASS]}),
        encoding="utf-8",
    )
    probe.PICTURE_CAPTURE_SHA256 = probe.sha256(capture_path)
    install_capture_stub(output, changed_first=changed_first)
    timeline = FakeTimeline("wrong-selection" if wrong_selection else TIMELINE_ID)
    project = FakeProject(timeline)
    result = probe.picture_calibration(
        FakeResolve(project),
        {"action": "picture-calibration", "projectName": PROJECT_NAME},
        IDENTITY,
        {},
        output,
        "fake",
        ENVIRONMENT,
    )
    return result, project, timeline


with tempfile.TemporaryDirectory() as directory:
    result, project, timeline = run_case(Path(directory))
    assert result["status"] == "candidate-exports-retained", result
    assert [path.name for path in project.exports] == [
        "frame-000.png",
        "frame-198.png",
        "frame-199.png",
        "frame-200.png",
    ]
    assert timeline.set_calls == [
        "00:00:00:00",
        "00:00:07:23",
        "00:00:07:24",
        "00:00:08:00",
        "00:00:03:12",
    ]
    assert result["exports"][-1]["pngHeaderMatches"] is True
    assert result["evidence"] and Path(result["evidence"]).is_file()

with tempfile.TemporaryDirectory() as directory:
    result, project, _timeline = run_case(Path(directory), changed_first=True)
    assert result["status"] == "picture-preflight-refused", result
    assert project.exports == []
    assert Path(result["evidence"]).is_file()

with tempfile.TemporaryDirectory() as directory:
    result, project, _timeline = run_case(Path(directory), wrong_selection=True)
    assert result["status"] == "picture-calibration-refused", result
    assert project.exports == []

print("picture calibration fake-native checks passed")


class CaseMedia:
    def __init__(self, filename, locator, uid):
        self.filename, self.locator, self.uid = filename, locator, uid

    def GetUniqueId(self):
        return self.uid

    def GetClipProperty(self):
        return {"File Name": self.filename, "File Path": self.locator}


class CaseItem:
    def __init__(self, name, spec, media, project):
        self.name, self.spec, self.media, self.project = name, spec, media, project
        self.enabled = False
        self.properties = {"Opacity": 100.0, "TransformEnabled": True}

    def GetUniqueId(self):
        return self.spec["uid"]

    def GetMediaPoolItem(self):
        return self.media

    def GetStart(self):
        return self.spec["start"]

    def GetEnd(self):
        return self.spec["end"]

    def GetDuration(self):
        return self.spec["duration"]

    def GetSourceStartFrame(self):
        return 0

    def GetSourceEndFrame(self):
        return self.spec["sourceEnd"]

    def GetTrackTypeAndIndex(self):
        return ["video", self.spec["track"]]

    def GetType(self):
        return "video"

    def GetMarkers(self):
        return {0: self.spec["marker"]["0"]}

    def GetClipEnabled(self):
        return self.enabled

    def GetProperties(self):
        return dict(self.properties)

    def SetClipEnabled(self, enabled):
        self.project.mutations.append(("SetClipEnabled", self.name, enabled))
        self.enabled = enabled
        return True

    def SetProperties(self, properties):
        self.project.mutations.append(("SetProperties", self.name, properties))
        self.properties.update(properties)
        return not (
            getattr(self.project, "partial_setter", False)
            and properties.get("Opacity") == 25.0
        )


class CaseTimeline:
    def __init__(self, project, timeline_id):
        self.project, self.timeline_id = project, timeline_id
        self.timecode = "00:00:03:12"

    def GetUniqueId(self):
        return self.timeline_id

    def GetItemListInTrack(self, kind, index):
        assert kind == "video"
        return [item for item in self.project.items if item.spec["track"] == index]

    def GetCurrentTimecode(self):
        return self.timecode

    def SetCurrentTimecode(self, timecode):
        self.timecode = timecode
        return True


class CaseProject:
    def __init__(self, timeline_id, project_id=PROJECT_ID):
        self.project_id = project_id
        self.timeline = CaseTimeline(self, timeline_id)
        self.items = []
        self.mutations = []
        self.exports = []

    def GetName(self):
        return PROJECT_NAME

    def GetUniqueId(self):
        return self.project_id

    def GetCurrentTimeline(self):
        return self.timeline

    def ExportCurrentFrameAsStill(self, destination):
        path = Path(destination)
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake-image-data")
        self.exports.append(path)
        self.mutations.append(("ExportCurrentFrameAsStill", str(path)))
        return True


class CaseResolve(FakeResolve):
    def GetProductName(self):
        return "DaVinci Resolve Studio"


def run_picture_case(root, *, fault=None):
    output = root / "output"
    output.mkdir()
    specs = deepcopy(probe.PICTURE_CASES)
    source_paths = {}
    project = CaseProject("wrong-selection" if fault == "selection" else TIMELINE_ID)
    for name, spec in specs.items():
        source_dir = root / name
        source_dir.mkdir()
        source = source_dir / spec["filename"]
        source.write_bytes((name + " test source").encode())
        digest = probe.sha256(source)
        spec["sha256"] = digest
        source_paths[str(source)] = digest
        media = CaseMedia(spec["filename"], str(source), spec["mediaUid"])
        item = CaseItem(name, spec, media, project)
        project.items.append(item)

    def snapshot():
        tracks = [{"index": index, "items": []} for index in range(1, 7)]
        for item in project.items:
            spec = item.spec
            entry = {
                "GetUniqueId": {"value": spec["uid"]},
                "GetClipEnabled": {"value": item.enabled},
                "GetStart": {"value": spec["start"]},
                "GetEnd": {"value": spec["end"]},
                "GetDuration": {"value": spec["duration"]},
                "GetSourceStartFrame": {"value": 0},
                "GetSourceEndFrame": {"value": spec["sourceEnd"]},
                "GetTrackTypeAndIndex": {"value": ["video", spec["track"]]},
                "GetType": {"value": "video"},
                "GetMarkers": {"value": spec["marker"]},
                "GetProperties": {"value": dict(item.properties)},
                "GetMediaPoolItem": {
                    "GetUniqueId": {"value": item.media.uid},
                    "GetClipProperty": {
                        "value": {
                            "File Name": item.media.filename,
                            "File Path": item.media.locator,
                        }
                    },
                },
            }
            tracks[spec["track"] - 1]["items"].append(entry)
        return {
            "projectId": PROJECT_ID,
            "timelines": [
                {"GetUniqueId": {"value": probe.BASELINE_ID}, "tracks": []},
                {"GetUniqueId": {"value": probe.R1_ID}, "tracks": []},
                {
                    "GetUniqueId": {"value": TIMELINE_ID},
                    "tracks": tracks,
                },
            ],
        }

    probe.PICTURE_CASES = specs
    pinned = snapshot()
    pinned_file = output / probe.PICTURE_CAPTURE
    pinned_file.write_text(
        json.dumps({"consistency": "equal-adjacent-reads", "passes": [pinned, pinned]}),
        encoding="utf-8",
    )
    probe.PICTURE_CAPTURE_SHA256 = probe.sha256(pinned_file)
    if fault == "target":
        project.items[0].media.uid = "wrong-media-uid"
    project.partial_setter = fault == "partial-setter"
    capture_calls = 0

    def fake_capture(_resolve, _config, _identity, _expected, _output, stamp, _env):
        nonlocal capture_calls
        capture_calls += 1
        value = snapshot()
        if fault == "preflight" and capture_calls == 1:
            value = {**value, "unexpected": True}
        if fault == "extra-delta" and capture_calls == 3:
            value = {**value, "unexpected": True}
        path = output / f"capture-{stamp}.json"
        path.write_text(
            json.dumps(
                {"consistency": "equal-adjacent-reads", "passes": [value, value]}
            ),
            encoding="utf-8",
        )
        return {"status": "equal-adjacent-reads", "capturePath": str(path)}

    probe.capture = fake_capture
    result = probe.picture_cases(
        CaseResolve(project),
        {"action": "picture-cases", "projectName": PROJECT_NAME},
        IDENTITY,
        source_paths,
        output,
        "cases",
        ENVIRONMENT,
    )
    return result, project, capture_calls, ORIGINAL_PICTURE_CASES


with tempfile.TemporaryDirectory() as directory:
    result, project, _calls, specs = run_picture_case(Path(directory))
    probe.PICTURE_CASES = specs
    assert result["status"] == "candidate-case-exports-retained", result
    assert len(project.exports) == 14
    assert len(result["exports"]) == 14
    assert len(project.mutations) == 22  # 8 setters, 14 still exports
    assert all(item.enabled is False for item in project.items)
    assert all(item.properties["Opacity"] == 100.0 for item in project.items)
    assert Path(result["evidence"]).is_file()

for fault in ("selection", "preflight", "target"):
    with tempfile.TemporaryDirectory() as directory:
        result, project, _calls, specs = run_picture_case(Path(directory), fault=fault)
        probe.PICTURE_CASES = specs
        assert result["status"] == "picture-cases-refused", result
        assert project.mutations == []

with tempfile.TemporaryDirectory() as directory:
    result, project, _calls, specs = run_picture_case(
        Path(directory), fault="extra-delta"
    )
    probe.PICTURE_CASES = specs
    assert result["status"] == "picture-cases-refused", result
    assert project.exports == []
    assert all(item.enabled is False for item in project.items)
    assert all(item.properties["Opacity"] == 100.0 for item in project.items)

with tempfile.TemporaryDirectory() as directory:
    result, project, _calls, specs = run_picture_case(
        Path(directory), fault="partial-setter"
    )
    probe.PICTURE_CASES = specs
    assert result["status"] == "picture-cases-refused", result
    assert all(item.enabled is False for item in project.items)
    assert all(item.properties["Opacity"] == 100.0 for item in project.items)

print("picture cases fake-native checks passed")
