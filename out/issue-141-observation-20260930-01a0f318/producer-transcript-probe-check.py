"""Small stdlib fake-Resolve check for the producer transcript probe."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "producer-transcript-probe.py"
SPEC = importlib.util.spec_from_file_location("producer_transcript_probe", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _transcript(text, *, words=True):
    segments = [{"text": text}]
    if words:
        segments[0]["words"] = [
            {
                "text": token,
                "start": "00:00:00:00",
                "end": "00:00:00:01",
            }
            for token in MODULE._word_raw_tokens(text)
        ]
    return {"language": "en", "segments": segments}


class Media:
    def __init__(self, uid, name, transcriptions, properties=None):
        self.uid = uid
        self.name = name
        self.transcriptions = transcriptions
        self.properties = {} if properties is None else properties
        self.transcription_calls = []
        self.property_calls = []

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name

    def GetTranscription(self, nested=False):
        self.transcription_calls.append(nested)
        return self.transcriptions[nested]

    def GetClipProperty(self, key=None):
        self.property_calls.append(key)
        return self.properties[key]


class MissingTranscriptionMedia:
    def __init__(self, uid, name):
        self.uid = uid
        self.name = name

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name


class BrokenRemoteProxy:
    """Models a bridge proxy whose repr consults a missing remote class."""

    @property
    def __class__(self):
        return None

    def __repr__(self):
        return self.__class__.__name__


class Item:
    def __init__(self, uid, media, track=("video", 1)):
        self.uid = uid
        self.media = media
        self.track = list(track)

    def GetUniqueId(self):
        return self.uid

    def GetMediaPoolItem(self):
        return self.media

    def GetStart(self):
        return 100

    def GetEnd(self):
        return 200

    def GetSourceStartFrame(self):
        return 0

    def GetSourceEndFrame(self):
        return 100

    def GetSourceStartTime(self):
        return 0.0

    def GetSourceEndTime(self):
        return 4.0

    def GetSpeed(self):
        return {"speed": 100.0}

    def GetClipEnabled(self):
        return True

    def GetTrackTypeAndIndex(self):
        return list(self.track)


class Timeline:
    def __init__(self, uid, name, pool, item):
        self.uid = uid
        self.name = name
        self.pool = pool
        self.item = item

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name

    def GetMediaPoolItem(self):
        return self.pool

    def GetTrackCount(self, track_type):
        return 1 if track_type == "video" else 0

    def GetItemListInTrack(self, track_type, index):
        assert (track_type, index) == ("video", 1)
        return [self.item]


class Project:
    def __init__(self, timelines):
        self.timelines = timelines

    def GetUniqueId(self):
        return MODULE.PROJECT_ID

    def GetName(self):
        return MODULE.PROJECT_NAME

    def GetCurrentTimeline(self):
        return self.timelines[0]

    def GetTimelineCount(self):
        return len(self.timelines)

    def GetTimelineByIndex(self, index):
        return self.timelines[index - 1]


class Manager:
    def __init__(self, project):
        self.project = project

    def GetCurrentProject(self):
        return self.project


class Resolve:
    def __init__(self, project, drift=False):
        self.project = project
        self.manager = Manager(project)
        self.drift = drift
        self.page_calls = 0

    def GetProductName(self):
        return "DaVinci Resolve Studio"

    def GetVersion(self):
        return [21, 1, 0, 14, ""]

    def GetProjectManager(self):
        return self.manager

    def GetCurrentPage(self):
        self.page_calls += 1
        return "edit" if not self.drift else f"edit-{self.page_calls}"


class FreshTimelineProxy:
    """Returns a new opaque handle each read while keeping identity stable."""

    def __init__(self, timeline):
        self.timeline = timeline

    def __repr__(self):
        return f"<FreshTimelineProxy {id(self):#x}>"

    def GetUniqueId(self):
        return self.timeline.GetUniqueId()

    def GetName(self):
        return self.timeline.GetName()


class FreshHandleProject(Project):
    def GetCurrentTimeline(self):
        return FreshTimelineProxy(self.timelines[0])


def _make_case(*, nested=False, missing=False, drift=False):
    source_text = MODULE.TARGET_TEXTS["transcription test 1"]
    source = Media(
        "source-uid",
        "producer-clip.mov",
        {False: _transcript(source_text), True: _transcript(source_text)},
        {"FPS": "25", "Start TC": "01:00:00:00"},
    )
    if missing:
        first_pool = MissingTranscriptionMedia("pool-1", "transcription test 1")
        second_pool = MissingTranscriptionMedia("pool-2", "transcription test 2")
    elif nested:
        first_pool = Media(
            "pool-1",
            "transcription test 1",
            {False: None, True: _transcript(MODULE.TARGET_TEXTS["transcription test 1"])},
        )
        second_pool = Media(
            "pool-2",
            "TRANSCRIPTION TEST 2",
            {False: None, True: _transcript(MODULE.TARGET_TEXTS["transcription test 2"])},
        )
    else:
        first_pool = Media(
            "pool-1",
            "Transcription Test 1",
            {False: _transcript(MODULE.TARGET_TEXTS["transcription test 1"]), True: None},
        )
        second_pool = Media(
            "pool-2",
            "transcription TEST 2",
            {False: _transcript(MODULE.TARGET_TEXTS["transcription test 2"]), True: None},
        )
    timelines = [
        Timeline("timeline-1", "Transcription Test 1", first_pool, Item("occ-1", source)),
        Timeline("timeline-2", "transcription TEST 2", second_pool, Item("occ-2", source)),
        Timeline("unrelated", "unrelated timeline", source, Item("occ-3", source)),
    ]
    return Resolve(Project(timelines), drift=drift), source, first_pool, second_pool


def _run(resolve, root):
    return MODULE.run(
        resolve,
        {
            "action": MODULE.ACTION,
            "projectId": MODULE.PROJECT_ID,
            "projectName": MODULE.PROJECT_NAME,
            "externalScriptingSetting": "None",
            "outputDir": str(root),
        },
    )


def main():
    source_text = MODULE.TARGET_TEXTS["transcription test 1"]
    opaque = MODULE._jsonable(BrokenRemoteProxy())
    assert opaque["unserializableType"] == "BrokenRemoteProxy"
    assert opaque["repr"] == "<opaque>"
    assert "__name__" in opaque["serializationError"]

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        resolve, source, first_pool, second_pool = _make_case()
        normal = _run(resolve, root / "normal") if (root / "normal").mkdir() is None else None
        assert normal["status"] == "complete"
        assert normal["comparisons"]["transcription test 1"]["timeline"]["modes"]["False"]["passes"][0]["status"] == "match"
        assert normal["comparisons"]["transcription test 2"]["timeline"]["modes"]["False"]["passes"][0]["status"] == "match"
        assert source.transcription_calls == [False, False, True, True]
        assert source.property_calls == ["FPS", "Start TC"]
        assert first_pool.transcription_calls == [False, False, True, True]
        assert second_pool.transcription_calls == [False, False, True, True]

        nested_root = root / "nested"
        nested_root.mkdir()
        resolve, _, first_pool, _ = _make_case(nested=True)
        nested = _run(resolve, nested_root)
        assert nested["status"] == "complete"
        assert nested["comparisons"]["transcription test 1"]["timeline"]["modes"]["True"]["passes"][0]["status"] == "match"
        assert nested["directTimelineTranscriptAvailable"] is True

        missing_root = root / "missing"
        missing_root.mkdir()
        resolve, _, _, _ = _make_case(missing=True)
        missing = _run(resolve, missing_root)
        assert missing["status"] == "complete"
        assert missing["comparisons"]["transcription test 1"]["timeline"]["modes"]["False"]["passes"][0]["status"] == "unavailable"
        assert missing["comparisons"]["transcription test 1"]["source"]["modes"]["False"]["passes"][0]["status"] == "match"

        drift_root = root / "drift"
        drift_root.mkdir()
        resolve, _, _, _ = _make_case(drift=True)
        drift = _run(resolve, drift_root)
        assert drift["status"] == "refused"
        assert drift["contextUnchanged"] is False

        context = MODULE._context(resolve, resolve.project)
        changed_proxy_repr = json.loads(json.dumps(context))
        changed_proxy_repr["currentTimeline"]["getter"]["value"]["repr"] = "<other-address>"
        assert MODULE._context_key(context) == MODULE._context_key(changed_proxy_repr)

        fresh_project = FreshHandleProject(resolve.project.timelines)
        fresh_resolve = Resolve(fresh_project)
        first_context = MODULE._context(fresh_resolve, fresh_project)
        second_context = MODULE._context(fresh_resolve, fresh_project)
        assert first_context["currentTimeline"]["getter"]["value"]["repr"] != second_context["currentTimeline"]["getter"]["value"]["repr"]
        assert MODULE._context_key(first_context) == MODULE._context_key(second_context)
        changed_uid = json.loads(json.dumps(first_context))
        changed_uid["currentTimeline"]["identity"]["GetUniqueId"]["value"] = "different"
        assert MODULE._context_key(first_context) != MODULE._context_key(changed_uid)

        source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "SetCurrentTimeline",
            "SetCurrentTimecode",
            "TranscribeAudio",
            "ClearTranscription",
            "SaveProject",
            "Export",
            "Render",
        ):
            assert forbidden not in source, forbidden

        result = {
            "status": "passed",
            "cases": ["normal", "nested", "missing", "drift-guard"],
            "sourceComparisonText": source_text,
            "mutationTokensAbsent": True,
        }
        artifact = HERE / "producer-transcript-probe-local-check.json"
        artifact.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
