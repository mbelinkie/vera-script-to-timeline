"""Offline fakes for the single-call R4 relink-only recovery."""

import hashlib
import importlib.util
import json
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("r4_recovery", HERE / "r4-recovery.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SOURCE = HERE / "inputs/relink/base.mov"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _media(path, *, offline=False, source_bytes=None):
    props = {
        "File Name": "base.mov",
        "File Path": ("OFFLINE - " + str(path) if offline else str(path)),
        "Online Status": "Offline" if offline else "Online",
        "Clip Directory": str(path.parent),
    }
    return {
        "GetUniqueId": {"value": MODULE.MEDIA_UID},
        "GetClipProperty": {"value": props},
        "GetMarkers": {"value": {}},
        "GetAudioMapping": {"value": {}},
        "sourceBytes": source_bytes
        or (
            {
                "status": "offline-locator-not-accessed",
                "approvedLocator": str(path),
                "expectedSha256": MODULE.MEDIA_SHA256,
            }
            if offline
            else {
                "status": "reachable",
                "sha256": MODULE.MEDIA_SHA256,
                "hashMatches": True,
            }
        ),
    }


def _state(project_name, source, *, offline=False):
    item = {
        "GetUniqueId": {"value": MODULE.ITEM_UID},
        "GetStart": {"value": 0},
        "GetEnd": {"value": 199},
        "GetDuration": {"value": 199},
        "GetSourceStartFrame": {"value": 0},
        "GetSourceEndFrame": {"value": 199},
        "GetTrackTypeAndIndex": {"value": ["video", 1]},
        "GetMediaPoolItem": _media(source, offline=offline),
    }
    timelines = [
        {
            "GetName": {"value": "VERA 141 R4 availability"},
            "GetUniqueId": {"value": MODULE.R4_UID},
            "GetStartFrame": {"value": 0},
            "GetEndFrame": {"value": 200},
            "GetMarkers": {"value": {}},
            "tracks": [{"type": "video", "index": 1, "items": [item]}],
        }
    ]
    for uid, name in {
        "29ae8331-b86e-4041-a548-960695cc7b24": "VERA 141 Batched Matrix",
        "88f7923d-55a7-471f-b09b-cf10f9fae8ad": "VERA 141 Baseline",
        "aa2b8e36-83bd-4292-9e33-217c00ca192f": "VERA 141 R1 identity",
    }.items():
        timelines.append(
            {
                "GetName": {"value": name},
                "GetUniqueId": {"value": uid},
                "GetStartFrame": {"value": 0},
                "GetEndFrame": {"value": 200},
                "GetMarkers": {"value": {}},
                "tracks": [],
            }
        )
    return {
        "projectId": MODULE.PROJECT_ID,
        "projectName": project_name,
        "GetSettings": {"value": {}},
        "timelines": timelines,
    }


def _inventory(source, *, offline=False):
    media = _media(source, offline=offline)
    return {
        "folders": [
            {"uid": "folder-root", "name": "Master"},
            {"uid": "folder-relink", "name": "relink"},
        ],
        "items": [
            {
                "uid": MODULE.ORIGINAL_UID,
                "name": {"value": "base.mov"},
                "folderUid": "folder-root",
                "evidence": {
                    "GetUniqueId": {"value": MODULE.ORIGINAL_UID},
                    "GetClipProperty": {"value": {"File Path": "shared/base.mov"}},
                    "sourceBytes": {"status": "timeline-uid-not-hashed"},
                },
            },
            {
                "uid": MODULE.MEDIA_UID,
                "name": {"value": "base.mov"},
                "folderUid": "folder-relink",
                "evidence": {
                    "GetUniqueId": {"value": MODULE.MEDIA_UID},
                    "GetName": {"value": "base.mov"},
                    "GetClipProperty": {"value": media["GetClipProperty"]["value"]},
                    "sourceBytes": media["sourceBytes"],
                },
            },
        ],
        "timelineMappings": [
            {
                "timelineUid": {"value": MODULE.R4_UID},
                "poolItemUid": {"value": MODULE.R4_POOL_UID},
            },
            *[
                {
                    "timelineUid": {"value": uid},
                    "poolItemUid": {"value": f"proxy-{uid}"},
                }
                for uid in (
                    "29ae8331-b86e-4041-a548-960695cc7b24",
                    "88f7923d-55a7-471f-b09b-cf10f9fae8ad",
                    "aa2b8e36-83bd-4292-9e33-217c00ca192f",
                )
            ],
        ],
    }


class Probe:
    ROOT = None

    @staticmethod
    def sha256(path):
        return digest(path)

    @staticmethod
    def errors(value):
        found = []
        if isinstance(value, dict):
            if "error" in value:
                found.append(value["error"])
            if value.get("value", False) is None:
                found.append("null getter")
            if value.get("hashMatches") is False:
                found.append("hash mismatch")
            if value.get("status") in {
                "unapproved-locator-not-accessed",
                "symlink-not-accessed",
            }:
                found.append(value["status"])
            for child in value.values():
                found.extend(Probe.errors(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(Probe.errors(child))
        return found

    @staticmethod
    def require_current(resolve, config, identity):
        project = resolve.manager.project
        if (
            project.uid != identity["projectId"]
            or project.name != config["projectName"]
        ):
            raise RuntimeError("project changed")
        return project

    @staticmethod
    def observe(resolve, config, identity, expected):
        del config, identity
        if set(expected) != resolve.manager.project.store.expected_sources:
            raise RuntimeError("manifest source expectations are incomplete")
        return deepcopy(resolve.manager.store.state)

    @staticmethod
    def _r4_pool_inventory(project, expected):
        if set(expected) != project.store.expected_sources:
            raise RuntimeError("manifest source expectations are incomplete")
        if project.store.fail_pool_read:
            raise RuntimeError("offline read refusal")
        return deepcopy(project.store.inventory)


class ItemHandle:
    def __init__(self, uid):
        self.uid = uid

    def GetUniqueId(self):
        return self.uid


class Folder:
    def __init__(self, store, clips=(), children=()):
        self.store = store
        self.clips = clips
        self.children = children

    def GetClipList(self):
        return [ItemHandle(uid) for uid in self.clips]

    def GetSubFolderList(self):
        return self.children


class Pool:
    def __init__(self, store):
        self.store = store

    def GetRootFolder(self):
        child = Folder(self.store, [MODULE.MEDIA_UID])
        return Folder(self.store, [MODULE.ORIGINAL_UID], [child])

    def RelinkClips(self, clips, folder):
        self.store.calls.append(
            ("RelinkClips", [x.GetUniqueId() for x in clips], folder)
        )
        self.store.set_online()
        if self.store.drift:
            self.store.inventory["items"][0]["name"] = {"value": "changed.mov"}
        if self.store.mode == "throw":
            raise RuntimeError("injected relink exception after restoration")
        return self.store.mode != "false"


class TimelineHandle:
    def __init__(self, uid):
        self.uid = uid

    def GetUniqueId(self):
        return self.uid


class Project:
    def __init__(self, store):
        self.store = store
        self.uid = MODULE.PROJECT_ID
        self.name = store.project_name

    def GetCurrentTimeline(self):
        return TimelineHandle(self.store.selected_uid)

    def GetMediaPool(self):
        return Pool(self.store)


class Manager:
    def __init__(self, store):
        self.store = store
        self.project = Project(store)

    def GetCurrentProject(self):
        return self.project


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
        return MODULE.BUILD


class Store:
    def __init__(self, project_name, source, mode="true"):
        self.project_name = project_name
        self.source = source
        self.state = _state(project_name, source, offline=True)
        self.inventory = _inventory(source, offline=True)
        self.selected_uid = MODULE.R4_UID
        self.mode = mode
        self.drift = False
        self.fail_pool_read = False
        self.calls = []
        self.expected_sources = set()

    def set_online(self):
        self.state = _state(self.project_name, self.source)
        self.inventory = _inventory(self.source)


def _write_pin(path, value):
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return digest(path)


def _setup(root, *, mode="true", preflight_drift=False):
    out = root / "out"
    output = out / "issue-141-observation-fake"
    media = out / "issue-141-media-fake"
    output.mkdir(parents=True)
    (media / "relink").mkdir(parents=True)
    source = media / "relink/base.mov"
    shutil.copyfile(SOURCE, source)
    other_source = media / "base.png"
    shutil.copyfile(HERE / "inputs/base.png", other_source)
    project_name = "VERA Issue 141 Synthetic Probe fake"
    store = Store(project_name, source, mode)
    online_state = _state(project_name, source)
    online_pool = _inventory(source)
    offline_state = deepcopy(store.state)
    offline_pool = deepcopy(store.inventory)
    if preflight_drift:
        store.state["timelines"][0]["GetName"] = {"value": "drift"}
    manifest = {
        "kind": "generated-synthetic-inputs-not-Resolve-evidence",
        "files": [
            {
                "path": "base.png",
                "sha256": digest(other_source),
                "sizeBytes": other_source.stat().st_size,
            },
            {
                "path": "relink/base.mov",
                "sha256": MODULE.MEDIA_SHA256,
                "sizeBytes": MODULE.MEDIA_SIZE,
            },
        ],
    }
    manifest_path = media / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    setup_capture = {
        "stage": "R4-post-append-partial-state-read-only",
        "consistency": "equal-adjacent-reads",
        "captureFailure": None,
        "environment": {"version": MODULE.BUILD},
        "passes": [online_state, online_state],
    }
    capture_path = output / MODULE.CAPTURE_NAME
    capture_hash = _write_pin(capture_path, setup_capture)
    setup_pool = {
        "status": "equal-read-only-pool-inventory",
        "capture": {"capturePath": str(capture_path), "sha256": capture_hash},
        "passes": [online_pool, online_pool],
    }
    pool_hash = _write_pin(output / MODULE.POOL_NAME, setup_pool)
    matrix = {
        "consistency": "equal-adjacent-reads",
        "captureFailure": None,
        "environment": {"version": MODULE.BUILD},
        "passes": [
            {
                "projectId": MODULE.PROJECT_ID,
                "projectName": project_name,
                "timelines": online_state["timelines"][1:],
            },
        ]
        * 2,
    }
    matrix_hash = _write_pin(output / MODULE.MATRIX_NAME, matrix)
    offline_capture = {
        "stage": "R4-offline-prefix-read-only",
        "consistency": "equal-adjacent-reads",
        "captureFailure": None,
        "passes": [offline_state, offline_state],
    }
    offcap_hash = _write_pin(output / MODULE.OFFLINE_CAPTURE_NAME, offline_capture)
    offline_pool_pin = {
        "status": "equal-read-only-pool-inventory",
        "capture": {
            "capturePath": str(output / MODULE.OFFLINE_CAPTURE_NAME),
            "sha256": offcap_hash,
        },
        "passes": [offline_pool, offline_pool],
    }
    offpool_hash = _write_pin(output / MODULE.OFFLINE_POOL_NAME, offline_pool_pin)
    unlink_capture = {
        "phase": "UnlinkClips",
        "timelinePasses": [offline_state, {"error": "pool read failed"}],
        "poolPasses": [{"error": "pool read failed"}],
    }
    unlink_hash = _write_pin(output / MODULE.UNLINK_CAPTURE, unlink_capture)
    refusal = {
        "reason": "RuntimeError: Unlink did not establish the pinned offline state"
    }
    refusal_hash = _write_pin(output / MODULE.REFUSAL_FILE, refusal)
    journal = output / MODULE.TRANSITION_JOURNAL
    journal.write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {
                    "method": "UnlinkClips",
                    "phase": "request",
                    "value": {"uids": [MODULE.MEDIA_UID]},
                },
                {"method": "UnlinkClips", "phase": "return", "value": True},
            )
        )
        + "\n",
        encoding="utf-8",
    )
    journal_hash = digest(journal)
    plugin_root = root / "plugin"
    plugin_root.mkdir()
    result = plugin_root / MODULE.PLUGIN_RESULT
    result.write_text(json.dumps({"status": "launcher-failed"}), encoding="utf-8")
    plugin_hash = digest(result)
    config = {
        "action": "r4-recovery",
        "externalScriptingSetting": "None",
        "projectName": project_name,
        "outputDir": str(output),
        "mediaDir": str(media),
        "manifestSha256": digest(manifest_path),
    }
    Probe.ROOT = root
    store.expected_sources = {str(source), str(other_source)}
    MODULE.PLUGIN_ROOT = plugin_root
    MODULE.CAPTURE_SHA256 = capture_hash
    MODULE.POOL_SHA256 = pool_hash
    MODULE.MATRIX_SHA256 = matrix_hash
    MODULE.OFFLINE_CAPTURE_SHA256 = offcap_hash
    MODULE.OFFLINE_POOL_SHA256 = offpool_hash
    MODULE.UNLINK_CAPTURE_SHA256 = unlink_hash
    MODULE.REFUSAL_SHA256 = refusal_hash
    MODULE.TRANSITION_JOURNAL_SHA256 = journal_hash
    MODULE.PLUGIN_RESULT_SHA256 = plugin_hash
    return output, config, store, source


def run_test(output, config, store):
    return MODULE.run(Resolve(store), config, probe=Probe)


def check():
    for mode, expected in (
        ("true", "relinked-online-unsaved"),
        ("false", "relink-refused-but-restored-online-unsaved"),
        ("throw", "relink-refused-but-restored-online-unsaved"),
    ):
        with tempfile.TemporaryDirectory() as temporary:
            output, config, store, source = _setup(Path(temporary), mode=mode)
            result = run_test(output, config, store)
            assert result["status"] == expected
            assert len(store.calls) == 1 and store.calls[0][0] == "RelinkClips"
            assert store.calls[0][1] == [MODULE.MEDIA_UID]
            assert store.calls[0][2] == str(source.parent)
            assert (
                store.state["timelines"][0]["tracks"][0]["items"][0][
                    "GetMediaPoolItem"
                ]["GetClipProperty"]["value"]["Online Status"]
                == "Online"
            )
            assert not any(
                call[0]
                in {"UnlinkClips", "SaveProject", "ImportMedia", "AppendToTimeline"}
                for call in store.calls
            )

    for damage in ("context", "inventory"):
        with tempfile.TemporaryDirectory() as temporary:
            output, config, store, _ = _setup(Path(temporary))
            if damage == "context":
                store.selected_uid = "other"
            else:
                store.fail_pool_read = True
            try:
                run_test(output, config, store)
            except RuntimeError:
                pass
            else:
                raise AssertionError("preflight refusal was ignored")
            assert store.calls == []

    with tempfile.TemporaryDirectory() as temporary:
        output, config, store, _ = _setup(Path(temporary))
        store.expected_sources.remove(str(Path(config["mediaDir"]) / "base.png"))
        try:
            run_test(output, config, store)
        except RuntimeError:
            pass
        else:
            raise AssertionError("missing original-source expectation was accepted")
        assert store.calls == []

    with tempfile.TemporaryDirectory() as temporary:
        output, config, store, _ = _setup(Path(temporary))
        store.drift = True
        try:
            run_test(output, config, store)
        except RuntimeError:
            pass
        else:
            raise AssertionError("post-relink unrelated drift was accepted")
        assert len(store.calls) == 1


if __name__ == "__main__":
    check()
    print("R4 recovery fake checks passed (no live Resolve evidence)")
