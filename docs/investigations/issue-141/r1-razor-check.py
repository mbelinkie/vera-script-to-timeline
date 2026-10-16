"""Focused fake checks for R1-razor native preparation; never launches Resolve."""

import hashlib
import importlib.util
import json
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "out" / "issue-141-observation-20260930-01a0f318"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


module = load("r1_razor", HERE / "r1-razor.py")
probe = load("r1_razor_real_probe", HERE / "probe.py")
reader = load("r1_razor_reader", HERE / "r4-range-repair.py")
PIN_CAPTURE = json.loads((OUT / module.R4_CAPTURE).read_text())
PIN_POOL = json.loads((OUT / module.R4_POOL).read_text())
PIN_MATRIX = json.loads((OUT / module.MATRIX_CAPTURE).read_text())


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Timeline:
    def __init__(self, store, uid):
        self.store, self.uid = store, uid

    def _row(self):
        return next(
            row
            for row in self.store.matrix["timelines"]
            if row["GetUniqueId"]["value"] == self.uid
        )

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self._row()["GetName"]["value"]

    def GetTrackCount(self, kind):
        return sum(track["type"] == kind for track in self._row()["tracks"])

    def GetIsTrackLocked(self, kind, index):
        track = next(
            row
            for row in self._row()["tracks"]
            if row["type"] == kind and row["index"] == index
        )
        return track["GetIsTrackLocked"]["value"]

    def SetTrackLock(self, kind, index, locked):
        self.store.calls.append(("SetTrackLock", kind, index, locked))
        self.store.lock_count += 1
        if self.store.mode == "lock-false" and self.store.lock_count == 2:
            return False
        track = next(
            row
            for row in self._row()["tracks"]
            if row["type"] == kind and row["index"] == index
        )
        track["GetIsTrackLocked"]["value"] = locked
        if self.store.mode == "drift" and self.store.lock_count == 1:
            self.store.matrix["GetSettings"]["value"]["fakeDrift"] = True
        return True

    def GetCurrentTimecode(self):
        return self.store.playhead

    def SetCurrentTimecode(self, value):
        self.store.calls.append(("SetCurrentTimecode", value))
        if self.store.mode == "playhead-false":
            return False
        self.store.playhead = value
        return True


class Project:
    def __init__(self, store):
        self.store = store

    def GetUniqueId(self):
        return module.PROJECT_ID

    def GetName(self):
        return self.store.project_name

    def IsRenderingInProgress(self):
        return False

    def GetCurrentTimeline(self):
        return Timeline(self.store, self.store.selected_uid)

    def GetTimelineCount(self):
        return len(self.store.matrix["timelines"])

    def GetTimelineByIndex(self, index):
        row = self.store.matrix["timelines"][index - 1]
        return Timeline(self.store, row["GetUniqueId"]["value"])

    def SetCurrentTimeline(self, timeline):
        self.store.calls.append(("SetCurrentTimeline", timeline.GetUniqueId()))
        if self.store.mode == "select-false":
            return False
        self.store.selected_uid = timeline.GetUniqueId()
        return True

    def GetCurrentRenderFormatAndCodec(self):
        return {"format": "mov", "codec": "H264"}

    def GetRenderJobList(self):
        return []


class Manager:
    def __init__(self, project):
        self.project = project

    def GetCurrentProject(self):
        return self.project


class Resolve:
    def __init__(self, store):
        self.store = store
        self.project = Project(store)

    def GetProductName(self):
        return "DaVinci Resolve Studio"

    def GetVersion(self):
        return module.BUILD

    def GetCurrentPage(self):
        return "edit"

    def GetProjectManager(self):
        return Manager(self.project)


class Store:
    def __init__(self, project_name, mode):
        self.project_name = project_name
        self.r4 = deepcopy(PIN_CAPTURE["passes"][0])
        self.matrix = deepcopy(PIN_MATRIX["passes"][0])
        r4_timeline = next(
            row
            for row in self.r4["timelines"]
            if row["GetUniqueId"]["value"] == module.R4_UID
        )
        self.matrix["timelines"].append(deepcopy(r4_timeline))
        for track in self.matrix["timelines"][-1]["tracks"]:
            track["GetIsTrackEnabled"] = {"value": False}
        self.matrix["timelines"].sort(key=lambda row: row["GetUniqueId"]["value"])
        self.pool = deepcopy(PIN_POOL["passes"][0])
        self.selected_uid = module.R4_UID
        self.playhead = "00:00:07:24"
        self.mode = mode
        self.calls, self.lock_count = [], 0


def run(mode="success", *, corrupt_pin=False):
    with tempfile.TemporaryDirectory(
        prefix="issue-141-observation-r1-razor-", dir=ROOT / "out"
    ) as temp:
        output = Path(temp)
        for name in (
            module.R4_CAPTURE,
            module.R4_POOL,
            module.RESTORED_PAIR,
            module.MATRIX_CAPTURE,
        ):
            shutil.copy2(OUT / name, output / name)
        project_name = PIN_CAPTURE["passes"][0]["projectName"]
        media = ROOT / "out" / "issue-141-media-20260930-01a0f318"
        config = {
            "action": "r1-razor-prepare",
            "externalScriptingSetting": "None",
            "projectName": project_name,
            "outputDir": str(output),
            "mediaDir": str(media),
            "manifestSha256": digest(media / "manifest.json"),
        }
        if corrupt_pin:
            (output / module.R4_CAPTURE).write_text("tampered")
        store = Store(project_name, mode)
        resolve = Resolve(store)
        probe.ROOT = ROOT
        probe.sha256 = digest
        probe.require_current = lambda _resolve, cfg, identity: (
            resolve.project
            if identity["projectId"] == module.PROJECT_ID
            and cfg["projectName"] == store.project_name
            else None
        )
        probe.observe = lambda *_args: deepcopy(
            store.r4 if store.selected_uid == module.R4_UID else store.matrix
        )
        probe._r4_pool_inventory = lambda *_args: deepcopy(store.pool)
        try:
            result = module.run(resolve, config, probe=probe)
        except RuntimeError as error:
            if not corrupt_pin:
                raise
            return {
                "status": "raised-before-native-setters",
                "failure": f"{type(error).__name__}: {error}",
            }, store
        return result, store


def demo():
    result, store = run()
    assert result["status"] == "prepared-for-editorial-selection", result
    assert result["targetUids"] == {
        "video": "33270bc5-52d0-4361-a6e3-96eb2b6d4a91",
        "audio": "4d08e64a-85fd-4dfe-ac80-77e4d9d28835",
    }
    assert result["split"] == {
        "case": "R1-razor",
        "localFrame": 100,
        "absoluteFrame": 1600,
        "timecode": "00:01:04:00",
        "frameRate": 25,
    }
    assert store.selected_uid == module.MATRIX_UID
    assert store.playhead == "00:01:04:00"
    assert store.calls == [
        ("SetCurrentTimeline", module.MATRIX_UID),
        ("SetTrackLock", "video", 2, True),
        ("SetTrackLock", "video", 3, True),
        ("SetTrackLock", "audio", 2, True),
        ("SetTrackLock", "audio", 3, True),
        ("SetCurrentTimecode", "00:01:04:00"),
    ]
    assert result["noEditorialCommandDispatched"] is True
    assert Path(result["preparedPairSha256"])

    for mode, count in (
        ("select-false", 1),
        ("lock-false", 3),
        ("playhead-false", 6),
        ("drift", 6),
    ):
        result, store = run(mode)
        assert result["status"] == "partial-state-review-required", (mode, result)
        assert len(result["setters"]) == count
        assert result.get("partialReadback") == "partial-readback.json"
        if mode in {"lock-false", "drift"}:
            assert any(
                track["GetIsTrackLocked"]["value"]
                for track in store.matrix["timelines"][0]["tracks"]
            )
    result, store = run(corrupt_pin=True)
    assert result["status"] == "raised-before-native-setters"
    assert result["failure"]
    assert store.calls == []
    print("R1-razor preparation fake checks passed")


if __name__ == "__main__":
    demo()
