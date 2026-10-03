"""Focused fake-only checks for the protected six-timeline adaptation."""

import importlib.util
import tempfile
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ISSUE = ROOT / "docs/investigations/issue-141"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ISSUE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = load("probe")
reader = load("r4-range-repair")
editorial = load("editorial-cases")

IDENTITIES = {
    **probe.PROTECTED_TIMELINE_IDENTITIES,
}


class Timeline:
    def __init__(self, uid, name):
        self.uid, self.name = uid, name

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name

    def GetTrackCount(self, kind):
        del kind
        return 0

    def GetStartFrame(self):
        return 0

    def GetEndFrame(self):
        return 0

    def GetStartTimecode(self):
        return "00:00:00:00"

    def GetSettings(self):
        return {}

    def GetMarkers(self):
        return {}


class Project:
    def __init__(self, rows):
        self.rows = rows

    def GetUniqueId(self):
        return "project"

    def GetName(self):
        return "protected-check"

    def GetTimelineCount(self):
        return len(self.rows)

    def GetTimelineByIndex(self, index):
        return self.rows[index - 1]

    def GetSettings(self):
        return {}


class Resolve:
    def __init__(self, project):
        self.project = project

    class Manager:
        def __init__(self, project):
            self.project = project

        def GetCurrentProject(self):
            return self.project

    def GetProjectManager(self):
        return self.Manager(self.project)


def rows(mapping):
    return [Timeline(uid, name) for uid, name in mapping.items()]


def observe(mapping, protected):
    config = {"projectName": "protected-check"}
    if protected:
        config["timelineInventory"] = probe.PROTECTED_INVENTORY
    handles = mapping if isinstance(mapping, list) else rows(mapping)
    return probe.observe(
        Resolve(Project(handles)), config, {"projectId": "project"}, {}
    )


def rejects(call):
    try:
        call()
    except (RuntimeError, ValueError):
        return
    raise AssertionError("expected guarded refusal")


def timeline_checks():
    assert observe(IDENTITIES, True)["timelineInventory"] == probe.PROTECTED_INVENTORY
    legacy = {
        uid: name
        for uid, name in IDENTITIES.items()
        if uid in probe.LEGACY_TIMELINE_IDENTITIES
    }
    assert "timelineInventory" not in observe(legacy, False)

    missing = dict(IDENTITIES)
    missing.pop("21436b8f-057c-49e6-80ba-5f733abe87b2")
    rejects(lambda: observe(missing, True))
    unknown = dict(IDENTITIES)
    unknown["unknown"] = "transcription test 3"
    unknown.pop("21436b8f-057c-49e6-80ba-5f733abe87b2")
    rejects(lambda: observe(unknown, True))
    duplicate = rows(IDENTITIES)
    duplicate[-1] = Timeline(
        "21436b8f-057c-49e6-80ba-5f733abe87b2", "transcription test 1"
    )
    rejects(lambda: observe(duplicate, True))
    extra = dict(IDENTITIES)
    extra["unknown"] = "transcription test 3"
    rejects(lambda: observe(extra, True))


class Media:
    def __init__(self, uid, name, path):
        self.uid, self.name, self.path = uid, name, path

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name

    def GetClipProperty(self):
        return {
            "File Name": self.name,
            "File Path": self.path,
            "Online Status": "Online",
        }

    def GetMarkers(self):
        return {}

    def GetAudioMapping(self):
        return {}


class Folder:
    def __init__(self, clip):
        self.clip = clip

    def GetUniqueId(self):
        return "folder"

    def GetName(self):
        return "root"

    def GetClipList(self):
        return [self.clip]

    def GetSubFolderList(self):
        return []


class Pool:
    def __init__(self, clip):
        self.folder = Folder(clip)

    def GetRootFolder(self):
        return self.folder


class PoolProject:
    def __init__(self, clip):
        self.pool = Pool(clip)

    def GetTimelineCount(self):
        return 0

    def GetMediaPool(self):
        return self.pool


def source_checks():
    protected = Media(
        probe.PROTECTED_SOURCE_UID, probe.PROTECTED_SOURCE_NAME, "/private/real.mp4"
    )
    original_hash = probe.sha256
    calls = []

    def counted(path):
        calls.append(str(path))
        return original_hash(path)

    probe.sha256 = counted
    try:
        evidence = probe.media_evidence(protected, {})
        assert calls == []
        assert evidence["GetUniqueId"] == {"value": probe.PROTECTED_SOURCE_UID}
        assert evidence["GetName"] == {"value": probe.PROTECTED_SOURCE_NAME}
        assert evidence["GetClipProperty"]["value"]["File Path"] == protected.path
        assert evidence["sourceBytes"] == {
            "status": "protected-locator-not-accessed"
        }
        inventory = probe._r4_pool_inventory(PoolProject(protected), {})
        assert calls == []
        assert inventory["items"][0]["evidence"]["sourceBytes"] == {
            "status": "protected-locator-not-accessed"
        }

        with tempfile.NamedTemporaryFile() as source:
            expected = {
                source.name: original_hash(source.name),
            }
            generated = Media("generated", "base.mov", source.name)
            result = probe.media_evidence(generated, expected)
            assert result["sourceBytes"]["hashMatches"] is True
            assert calls == [source.name]
    finally:
        probe.sha256 = original_hash


def pair_checks():
    protected_state = {
        "projectId": "project",
        "timelineInventory": reader.PROTECTED_INVENTORY,
        "timelines": [
            {
                "GetUniqueId": {"value": uid},
                "GetName": {"value": name},
            }
            for uid, name in IDENTITIES.items()
        ],
    }
    pair = {
        "timelineInventory": reader.PROTECTED_INVENTORY,
        "timelinePasses": [protected_state, deepcopy(protected_state)],
        "poolPasses": [{"items": []}, {"items": []}],
        "timelineConsistency": "equal-adjacent-reads",
        "poolConsistency": "equal-adjacent-reads",
    }

    class PairProbe:
        @staticmethod
        def errors(value):
            del value
            return []

    state, _ = reader._validate_read_pair(pair, PairProbe)
    assert state["timelineInventory"] == reader.PROTECTED_INVENTORY
    changed = deepcopy(pair)
    changed["timelinePasses"][1]["timelines"][0]["GetName"]["value"] = "wrong"
    rejects(lambda: reader._validate_read_pair(changed, PairProbe))

    assert editorial._timeline(protected_state, reader)["GetUniqueId"] == {
        "value": probe.MATRIX_PARTIAL_ID
    }
    legacy_state = {
        **protected_state,
        "timelines": protected_state["timelines"][:4],
    }
    del legacy_state["timelineInventory"]
    assert editorial._timeline(legacy_state, reader)["GetUniqueId"] == {
        "value": probe.MATRIX_PARTIAL_ID
    }
    bad = deepcopy(protected_state)
    bad["timelines"].append(
        {"GetUniqueId": {"value": "extra"}, "GetName": {"value": "extra"}}
    )
    rejects(lambda: editorial._timeline(bad, reader))


if __name__ == "__main__":
    timeline_checks()
    source_checks()
    pair_checks()
    print("protected inventory checks passed")
