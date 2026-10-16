"""Fake acceptance check for the save-only R4 finalizer."""

import hashlib
import importlib.util
import json
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("r4_finalize", HERE / "r4-finalize.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SOURCE = HERE / "inputs/relink/base.mov"


def _timeline(uid, name, *, r4=False):
    value = {
        "GetName": {"value": name},
        "GetUniqueId": {"value": uid},
        "GetSettings": {"value": {}},
        "GetMarkers": {"value": {"0": {"name": "pin"}}},
        "tracks": [],
    }
    if r4:
        media = {
            "GetUniqueId": {"value": module.MEDIA_UID},
            "GetClipProperty": {
                "value": {
                    "File Path": "MEDIA_PATH",
                    "Online Status": "Online",
                }
            },
            "GetMarkers": {"value": {}},
            "GetAudioMapping": {"value": {}},
            "sourceBytes": {
                "status": "reachable",
                "sha256": module.MEDIA_SHA256,
                "hashMatches": True,
            },
        }
        value["tracks"] = [
            {
                "type": "video",
                "index": 1,
                "items": [
                    {
                        "GetUniqueId": {"value": module.ITEM_UID},
                        "GetStart": {"value": 0},
                        "GetEnd": {"value": 199},
                        "GetDuration": {"value": 199},
                        "GetSourceStartFrame": {"value": 0},
                        "GetSourceEndFrame": {"value": 199},
                        "GetTrackTypeAndIndex": {"value": ["video", 1]},
                        "GetMediaPoolItem": media,
                    }
                ],
            },
            {"type": "audio", "index": 1, "items": []},
        ]
    return value


class Probe:
    ROOT = None

    @staticmethod
    def sha256(path):
        with Path(path).open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    @staticmethod
    def errors(value):
        found = []
        if isinstance(value, dict):
            if "error" in value:
                found.append(value["error"])
            if value.get("value", False) is None:
                found.append("null-getter-result-not-established")
            if value.get("status") in {
                "unapproved-locator-not-accessed",
                "symlink-not-accessed",
            }:
                found.append(value["status"])
            if value.get("hashMatches") is False:
                found.append("source-hash-mismatch")
            for child in value.values():
                found.extend(Probe.errors(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(Probe.errors(child))
        return found

    @staticmethod
    def require_current(resolve, config, identity):
        project = resolve.GetProjectManager().GetCurrentProject()
        if (
            project.uid != identity["projectId"]
            or project.name != config["projectName"]
        ):
            raise RuntimeError("project identity changed")
        return project

    @staticmethod
    def observe(resolve, config, identity, expected):
        del config, identity, expected
        state = deepcopy(resolve.manager.store.observation)
        state["timelines"][0]["GetMarkers"]["value"] = {
            int(key): value
            for key, value in state["timelines"][0]["GetMarkers"]["value"].items()
        }
        target = next(
            row
            for row in state["timelines"]
            if row["GetUniqueId"]["value"] == module.R4_UID
        )
        item = target["tracks"][0]["items"][0]
        item["GetTrackTypeAndIndex"]["value"] = tuple(
            item["GetTrackTypeAndIndex"]["value"]
        )
        return state

    @staticmethod
    def _r4_pool_inventory(project, expected):
        del expected
        return deepcopy(project.store.inventory)


class TimelineHandle:
    def __init__(self, uid):
        self.uid = uid

    def GetUniqueId(self):
        return self.uid


class Project:
    def __init__(self, store):
        self.store = store
        self.uid = module.PROJECT_ID
        self.name = store.project_name
        store.handles.append(self)

    def GetCurrentTimeline(self):
        return TimelineHandle(self.store.selected_uid)

    def GetTimelineCount(self):
        return len(self.store.observation["timelines"])

    def GetTimelineByIndex(self, index):
        return TimelineHandle(
            self.store.observation["timelines"][index - 1]["GetUniqueId"]["value"]
        )


class Manager:
    def __init__(self, store):
        self.store = store

    def GetCurrentProject(self):
        return Project(self.store)

    def SaveProject(self):
        self.store.save_calls += 1
        if self.store.save_mode == "raise":
            raise RuntimeError("injected SaveProject failure")
        return self.store.save_mode != "false"


class Resolve:
    def __init__(self, store):
        self.manager = Manager(store)

    def GetProjectManager(self):
        return self.manager

    @staticmethod
    def GetProductName():
        return "DaVinci Resolve Studio"

    @staticmethod
    def GetVersion():
        return module.BUILD


class Store:
    def __init__(self, project_name, observation, inventory, *, save_mode="true"):
        self.project_name = project_name
        self.observation = observation
        self.inventory = inventory
        self.selected_uid = module.R4_UID
        self.save_mode = save_mode
        self.save_calls = 0
        self.handles = []


def _setup(root, *, save_mode="true", changed_live=None, changed_selected=False):
    out = root / "out"
    output = out / "issue-141-observation-fake"
    media = out / "issue-141-media-fake"
    output.mkdir(parents=True)
    media.mkdir()
    relink = media / "relink"
    relink.mkdir()
    shutil.copyfile(SOURCE, relink / "base.mov")
    source = relink / "base.mov"
    project_name = "VERA Issue 141 Synthetic Probe fake"
    observation = {
        "projectId": module.PROJECT_ID,
        "projectName": project_name,
        "GetSettings": {"value": {}},
        "timelines": [
            _timeline(module.R4_UID, "VERA 141 R4 availability", r4=True),
            _timeline(
                "29ae8331-b86e-4041-a548-960695cc7b24", "VERA 141 Batched Matrix"
            ),
            _timeline("88f7923d-55a7-471f-b09b-cf10f9fae8ad", "VERA 141 Baseline"),
            _timeline("aa2b8e36-83bd-4292-9e33-217c00ca192f", "VERA 141 R1 identity"),
        ],
    }
    observation["timelines"][0]["tracks"][0]["items"][0]["GetMediaPoolItem"][
        "GetClipProperty"
    ]["value"]["File Path"] = str(source)
    inventory = {
        "folders": [{"uid": "folder-root", "name": "Root"}],
        "items": [
            {
                "uid": module.MEDIA_UID,
                "name": {"value": "base.mov"},
                "folderUid": "folder-root",
                "evidence": {
                    "GetUniqueId": {"value": module.MEDIA_UID},
                    "GetClipProperty": {
                        "value": {
                            "File Path": str(source),
                            "Online Status": "Online",
                        }
                    },
                    "sourceBytes": {
                        "status": "reachable",
                        "sha256": module.MEDIA_SHA256,
                        "hashMatches": True,
                    },
                },
            }
        ],
        "timelineMappings": [
            {
                "timelineUid": {"value": module.R4_UID},
                "poolItemUid": {"value": module.R4_POOL_UID},
            }
        ],
    }
    pinned_observation = deepcopy(observation)
    pinned_inventory = deepcopy(inventory)
    if changed_live == "content":
        observation["timelines"][0]["GetName"]["value"] = "changed"
    if changed_live == "pool":
        inventory["items"][0]["name"] = {"value": "changed.mov"}
    capture = {
        "kind": "real-injected-readback",
        "stage": "R4-post-append-partial-state-read-only",
        "capturedAt": "20261001T003310.397326Z",
        "environment": {"version": module.BUILD},
        "consistency": "equal-adjacent-reads",
        "captureFailure": None,
        "getterFailures": [],
        "passes": [pinned_observation, pinned_observation],
    }
    pool = {
        "status": "equal-read-only-pool-inventory",
        "capture": {
            "capturePath": str(output / module.CAPTURE_NAME),
            "sha256": module.CAPTURE_SHA256,
            "status": "equal-adjacent-reads",
        },
        "passes": [pinned_inventory, pinned_inventory],
    }
    capture_path = output / module.CAPTURE_NAME
    pool_path = output / module.POOL_NAME
    capture_path.write_text(json.dumps(capture), encoding="utf-8")
    pool_path.write_text(json.dumps(pool), encoding="utf-8")
    module.CAPTURE_SHA256 = hashlib.sha256(capture_path.read_bytes()).hexdigest()
    pool["capture"]["sha256"] = module.CAPTURE_SHA256
    pool_path.write_text(json.dumps(pool), encoding="utf-8")
    module.POOL_SHA256 = hashlib.sha256(pool_path.read_bytes()).hexdigest()
    # Reset the capture hash after incorporating its actual file bytes in the pool pin.
    pool["capture"]["sha256"] = module.CAPTURE_SHA256
    pool_path.write_text(json.dumps(pool), encoding="utf-8")
    module.POOL_SHA256 = hashlib.sha256(pool_path.read_bytes()).hexdigest()
    manifest = {
        "kind": "generated-synthetic-inputs-not-Resolve-evidence",
        "files": [{"path": "relink/base.mov", "sha256": module.MEDIA_SHA256}],
    }
    manifest_path = media / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    config = {
        "action": "r4-finalize",
        "externalScriptingSetting": "None",
        "projectName": project_name,
        "outputDir": str(output),
        "mediaDir": str(media),
        "manifestSha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }
    store = Store(project_name, observation, inventory, save_mode=save_mode)
    if changed_selected:
        store.selected_uid = "wrong-selected-timeline"
    return output, config, store


def _run(output, config, store):
    return module.run(Resolve(store), config, probe=Probe)


def check():
    original_hashes = (module.CAPTURE_SHA256, module.POOL_SHA256)
    with tempfile.TemporaryDirectory() as temporary:
        Probe.ROOT = Path(temporary)
        output, config, store = _setup(Probe.ROOT)
        result = _run(output, config, store)
        assert result["status"] == "saved-pinned-r4-state"
        assert store.save_calls == 1
        assert len({id(handle) for handle in store.handles}) > 1
        postflight = json.loads(Path(result["postflight"]).read_text())
        assert postflight["timelinePasses"] == [store.observation, store.observation]
        assert postflight["poolPasses"] == [store.inventory, store.inventory]

    for changed_live, changed_selected in (
        ("content", False),
        ("pool", False),
        (None, True),
    ):
        with tempfile.TemporaryDirectory() as temporary:
            Probe.ROOT = Path(temporary)
            output, config, store = _setup(
                Probe.ROOT,
                changed_live=changed_live,
                changed_selected=changed_selected,
            )
            try:
                _run(output, config, store)
            except RuntimeError:
                pass
            else:
                raise AssertionError("changed content/pool/context must refuse")
            assert store.save_calls == 0

    with tempfile.TemporaryDirectory() as temporary:
        Probe.ROOT = Path(temporary)
        output, config, store = _setup(Probe.ROOT)
        (output / module.CAPTURE_NAME).write_text("{}", encoding="utf-8")
        try:
            _run(output, config, store)
        except RuntimeError:
            pass
        else:
            raise AssertionError("changed pin must refuse")
        assert store.save_calls == 0

    with tempfile.TemporaryDirectory() as temporary:
        Probe.ROOT = Path(temporary)
        output, config, store = _setup(Probe.ROOT)
        (output / module.POOL_NAME).write_text("{}", encoding="utf-8")
        try:
            _run(output, config, store)
        except RuntimeError:
            pass
        else:
            raise AssertionError("changed pool pin must refuse")
        assert store.save_calls == 0

    for save_mode in ("false", "raise"):
        with tempfile.TemporaryDirectory() as temporary:
            Probe.ROOT = Path(temporary)
            output, config, store = _setup(Probe.ROOT, save_mode=save_mode)
            try:
                _run(output, config, store)
            except RuntimeError:
                pass
            else:
                raise AssertionError("false/throw SaveProject must refuse")
            assert store.save_calls == 1
            assert list(output.glob("r4-finalize-*-postflight.json"))

    module.CAPTURE_SHA256, module.POOL_SHA256 = original_hashes


if __name__ == "__main__":
    check()
    print("R4 finalize fake acceptance passed (no live Resolve evidence)")
