"""Offline fake checks for the guarded R4 unlink/relink transition."""

import hashlib
import importlib.util
import json
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "r4_transitions", HERE / "r4-transitions.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SOURCE = HERE / "inputs/relink/base.mov"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _timeline(uid, name, *, r4=False, source_path=""):
    row = {
        "GetName": {"value": name},
        "GetUniqueId": {"value": uid},
        "GetStartFrame": {"value": 0},
        "GetEndFrame": {"value": 200},
        "GetMarkers": {"value": {}},
        "tracks": [],
    }
    if not r4:
        return row
    props = {
        "File Name": "base.mov",
        "File Path": source_path,
        "Online Status": "Online",
    }
    media = {
        "GetUniqueId": {"value": MODULE.MEDIA_UID},
        "GetClipProperty": {"value": props},
        "GetMarkers": {"value": {}},
        "GetAudioMapping": {"value": {}},
        "sourceBytes": {
            "status": "reachable",
            "sha256": MODULE.MEDIA_SHA256,
            "hashMatches": True,
        },
    }
    occurrence = {
        "GetUniqueId": {"value": MODULE.ITEM_UID},
        "GetStart": {"value": 0},
        "GetEnd": {"value": 199},
        "GetDuration": {"value": 199},
        "GetSourceStartFrame": {"value": 0},
        "GetSourceEndFrame": {"value": 199},
        "GetTrackTypeAndIndex": {"value": ["video", 1]},
        "GetMediaPoolItem": media,
    }
    row["tracks"] = [{"type": "video", "index": 1, "items": [occurrence]}]
    return row


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
        del config
        project = resolve.manager.project
        if project.uid != identity["projectId"]:
            raise RuntimeError("project identity changed")
        return project

    @staticmethod
    def observe(resolve, config, identity, expected):
        del config, identity, expected
        return deepcopy(resolve.manager.project.store.state)

    @staticmethod
    def _r4_pool_inventory(project, expected):
        del expected
        if project.store.fail_inventory:
            raise RuntimeError("injected inventory refusal")
        if (
            project.store.inventory["items"][1]["evidence"]["GetClipProperty"][
                "value"
            ].get("File Path")
            == ""
        ):
            error = RuntimeError("offline blank locator is not approved for hashing")
            error.diagnostic = {
                "failedEntry": {"uid": MODULE.MEDIA_UID, "File Path": ""}
            }
            raise error
        return deepcopy(project.store.inventory)


class MediaItem:
    def __init__(self, uid, store):
        self.uid = uid
        self.store = store
        store.handles.append(self)

    def GetUniqueId(self):
        return self.uid


class Folder:
    def __init__(self, uid, store, clips=(), children=()):
        self.uid = uid
        self.store = store
        self.clips = clips
        self.children = children

    def GetUniqueId(self):
        return self.uid

    def GetClipList(self):
        return [MediaItem(uid, self.store) for uid in self.clips]

    def GetSubFolderList(self):
        return self.children


class MediaPool:
    def __init__(self, store):
        self.store = store

    def GetRootFolder(self):
        child = Folder("folder-child", self.store, [MODULE.MEDIA_UID])
        return Folder("folder-root", self.store, [MODULE.ORIGINAL_UID], [child])

    def UnlinkClips(self, clips):
        self.store.calls.append(("UnlinkClips", [clip.GetUniqueId() for clip in clips]))
        if self.store.unlink_mode not in {"no-mutation", "false-no-mutation"}:
            self.store.set_offline(blank=self.store.offline_blank)
        if self.store.mutate_unrelated:
            self.store.inventory["items"][0]["name"] = {"value": "changed.mov"}
        if self.store.mutate_occurrence:
            self.store.state["timelines"][0]["tracks"][0]["items"][0]["GetUniqueId"] = {
                "value": "changed-occurrence"
            }
        if self.store.change_media_after_unlink:
            self.store.source.write_bytes(b"changed source bytes")
        if self.store.change_context_after_unlink:
            self.store.selected_uid = "changed-context"
        if self.store.unlink_mode == "throw":
            raise RuntimeError("injected unlink throw")
        return self.store.unlink_mode not in {"false", "false-no-mutation"}

    def RelinkClips(self, clips, folder_path):
        self.store.calls.append(
            ("RelinkClips", [clip.GetUniqueId() for clip in clips], folder_path)
        )
        if self.store.relink_mode not in {"no-mutation", "false-no-mutation"}:
            self.store.set_online()
        if self.store.relink_mode == "throw":
            raise RuntimeError("injected relink throw")
        return self.store.relink_mode not in {"false", "false-no-mutation"}


class Project:
    uid = MODULE.PROJECT_ID

    def __init__(self, store):
        self.store = store

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.store.project_name

    def GetCurrentTimeline(self):
        return Timeline(self.store.selected_uid)

    def GetMediaPool(self):
        return MediaPool(self.store)


class Timeline:
    def __init__(self, uid):
        self.uid = uid

    def GetUniqueId(self):
        return self.uid


class Manager:
    def __init__(self, store):
        self.store = store
        self.project = Project(store)

    def GetCurrentProject(self):
        return self.project

    def SaveProject(self):
        self.store.calls.append(("SaveProject", MODULE.PROJECT_ID))
        if self.store.save_mode == "throw":
            raise RuntimeError("injected save throw")
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
        return MODULE.BUILD


class Store:
    def __init__(self, project_name, media_path):
        self.project_name = project_name
        self.source = media_path / "relink/base.mov"
        self.selected_uid = MODULE.R4_UID
        self.state = {
            "projectId": MODULE.PROJECT_ID,
            "projectName": project_name,
            "GetSettings": {"value": {}},
            "timelines": [
                _timeline(
                    MODULE.R4_UID,
                    "VERA 141 R4 availability",
                    r4=True,
                    source_path=str(self.source),
                ),
                *[
                    _timeline(uid, name)
                    for uid, name in MODULE.ORIGINAL_TIMELINES.items()
                ],
            ],
        }
        item = {
            "uid": MODULE.MEDIA_UID,
            "name": {"value": "base.mov"},
            "folderUid": "folder-child",
            "evidence": {
                "GetUniqueId": {"value": MODULE.MEDIA_UID},
                "GetClipProperty": {
                    "value": {
                        "File Name": "base.mov",
                        "File Path": str(self.source),
                        "Online Status": "Online",
                    }
                },
                "sourceBytes": {
                    "status": "reachable",
                    "sha256": MODULE.MEDIA_SHA256,
                    "hashMatches": True,
                },
            },
        }
        original = {
            "uid": MODULE.ORIGINAL_UID,
            "name": {"value": "base.mov"},
            "folderUid": "folder-root",
            "evidence": {"GetClipProperty": {"value": {"File Path": "original.mov"}}},
        }
        self.inventory = {
            "folders": [
                {"uid": "folder-root", "name": "Root"},
                {"uid": "folder-child", "name": "R4"},
            ],
            "items": [original, item],
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
                    for uid in MODULE.ORIGINAL_TIMELINES
                ],
            ],
        }
        self.calls = []
        self.handles = []
        self.unlink_mode = "true"
        self.relink_mode = "true"
        self.save_mode = "true"
        self.mutate_unrelated = False
        self.mutate_occurrence = False
        self.change_media_after_unlink = False
        self.change_context_after_unlink = False
        self.offline_blank = False
        self.fail_inventory = False

    def set_offline(self, *, blank=False):
        for values in self._property_maps():
            values["Online Status"] = "Offline"
            if blank:
                values["File Path"] = ""
        self._set_bytes({"status": "unavailable", "error": "FileNotFoundError"})

    def set_online(self):
        for values in self._property_maps():
            values["Online Status"] = "Online"
            values["File Path"] = str(self.source)
        self._set_bytes(
            {"status": "reachable", "sha256": MODULE.MEDIA_SHA256, "hashMatches": True}
        )

    def _property_maps(self):
        return [
            self.state["timelines"][0]["tracks"][0]["items"][0]["GetMediaPoolItem"][
                "GetClipProperty"
            ]["value"],
            self.inventory["items"][1]["evidence"]["GetClipProperty"]["value"],
        ]

    def _set_bytes(self, value):
        self.state["timelines"][0]["tracks"][0]["items"][0]["GetMediaPoolItem"][
            "sourceBytes"
        ] = deepcopy(value)
        self.inventory["items"][1]["evidence"]["sourceBytes"] = deepcopy(value)


def _write_pin(path, value):
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return digest(path)


def _setup(root, *, source_changed=False):
    out = root / "out"
    output = out / "issue-141-observation-fake"
    media = out / "issue-141-media-fake"
    output.mkdir(parents=True)
    media.mkdir()
    (media / "relink").mkdir()
    shutil.copyfile(SOURCE, media / "relink/base.mov")
    if source_changed:
        (media / "relink/base.mov").write_bytes(b"wrong bytes")
    manifest = {
        "kind": "generated-synthetic-inputs-not-Resolve-evidence",
        "files": [
            {
                "path": "relink/base.mov",
                "sha256": MODULE.MEDIA_SHA256,
                "sizeBytes": MODULE.MEDIA_SIZE,
            }
        ],
    }
    manifest_path = media / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    project_name = "VERA Issue 141 Synthetic Probe fake"
    store = Store(project_name, media)
    checkpoint_pass = {
        "projectId": MODULE.PROJECT_ID,
        "projectName": project_name,
        "timelines": [
            _timeline(uid, name) for uid, name in MODULE.ORIGINAL_TIMELINES.items()
        ],
    }
    capture = {
        "kind": "real-injected-readback",
        "stage": "R4-post-append-partial-state-read-only",
        "consistency": "equal-adjacent-reads",
        "captureFailure": None,
        "environment": {"version": MODULE.BUILD},
        "passes": [deepcopy(store.state), deepcopy(store.state)],
    }
    capture_path = output / MODULE.CAPTURE_NAME
    module_capture_hash = _write_pin(capture_path, capture)
    pool = {
        "status": "equal-read-only-pool-inventory",
        "capture": {
            "capturePath": str(capture_path),
            "sha256": module_capture_hash,
            "status": "equal-adjacent-reads",
        },
        "passes": [deepcopy(store.inventory), deepcopy(store.inventory)],
    }
    pool_hash = _write_pin(output / MODULE.POOL_NAME, pool)
    checkpoint_path = output / MODULE.MATRIX_NAME
    checkpoint = {
        "consistency": "equal-adjacent-reads",
        "captureFailure": None,
        "environment": {"version": MODULE.BUILD},
        "passes": [deepcopy(checkpoint_pass), deepcopy(checkpoint_pass)],
    }
    matrix_hash = _write_pin(checkpoint_path, checkpoint)
    finalize_journal = output / "fake-finalize.jsonl"
    finalize_journal.write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {"method": "SaveProject", "phase": "request", "value": {}},
                {"method": "SaveProject", "phase": "return", "value": True},
                {
                    "method": "R4Finalize",
                    "phase": "complete",
                    "value": {"status": "saved-pinned-r4-state"},
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )
    plugin_root = root / "plugin"
    plugin_root.mkdir()
    finalize_result = plugin_root / "fake-result.json"
    finalize_result.write_text(
        json.dumps({"status": "saved-pinned-r4-state"}), encoding="utf-8"
    )
    config = {
        "action": "r4-transitions",
        "externalScriptingSetting": "None",
        "projectName": project_name,
        "outputDir": str(output),
        "mediaDir": str(media),
        "manifestSha256": digest(manifest_path),
    }
    Probe.ROOT = root
    MODULE.PLUGIN_ROOT = plugin_root
    MODULE.CAPTURE_SHA256 = module_capture_hash
    MODULE.POOL_SHA256 = pool_hash
    MODULE.MATRIX_SHA256 = matrix_hash
    MODULE.FINALIZE_JOURNAL_NAME = finalize_journal.name
    MODULE.FINALIZE_JOURNAL_SHA256 = digest(finalize_journal)
    MODULE.FINALIZE_RESULT_NAME = finalize_result.name
    MODULE.FINALIZE_RESULT_SHA256 = digest(finalize_result)
    return output, config, store


def _run(output, config, store):
    return MODULE.run(Resolve(store), config, probe=Probe)


def _refuses(output, config, store, message):
    try:
        _run(output, config, store)
    except RuntimeError:
        pass
    else:
        raise AssertionError(message)


def check():
    with tempfile.TemporaryDirectory() as temporary:
        output, config, store = _setup(Path(temporary))
        result = _run(output, config, store)
        assert result["status"] == "restored-online-and-saved"
        assert [call[0] for call in store.calls] == [
            "UnlinkClips",
            "RelinkClips",
            "SaveProject",
        ]
        assert all(call[1] == [MODULE.MEDIA_UID] for call in store.calls[:2])
        assert store.calls[1][2] == str(Path(config["mediaDir"]) / "relink")
        assert len({id(handle) for handle in store.handles}) >= 2
        assert store.inventory["items"][0]["uid"] == MODULE.ORIGINAL_UID
        assert store.inventory["items"][0]["evidence"]["GetClipProperty"]["value"] == {
            "File Path": "original.mov"
        }
        assert store.inventory["timelineMappings"][0]["poolItemUid"] == {
            "value": MODULE.R4_POOL_UID
        }
        final = next(output.glob("r4-transitions-*-post-save.json"))
        assert json.loads(final.read_text())["status"] == "equal-adjacent-reads"

    for changed, selected in (("content", False), (None, True)):
        with tempfile.TemporaryDirectory() as temporary:
            output, config, store = _setup(Path(temporary))
            if changed:
                store.state["timelines"][0]["GetName"] = {"value": "changed"}
            if selected:
                store.selected_uid = "other"
            _refuses(output, config, store, "changed live state/context must refuse")
            assert store.calls == []

    for mutate in ("capture", "pool"):
        with tempfile.TemporaryDirectory() as temporary:
            output, config, store = _setup(Path(temporary))
            path = output / (
                MODULE.CAPTURE_NAME if mutate == "capture" else MODULE.POOL_NAME
            )
            path.write_text("{}", encoding="utf-8")
            _refuses(output, config, store, "changed evidence pin must refuse")
            assert store.calls == []

    with tempfile.TemporaryDirectory() as temporary:
        output, config, store = _setup(Path(temporary), source_changed=True)
        _refuses(output, config, store, "wrong-byte locator must refuse")
        assert store.calls == []

    for damage in ("live-pool", "locator", "proxy"):
        with tempfile.TemporaryDirectory() as temporary:
            output, config, store = _setup(Path(temporary))
            if damage == "live-pool":
                store.inventory["items"][0]["name"] = {"value": "changed.mov"}
            elif damage == "locator":
                store.state["timelines"][0]["tracks"][0]["items"][0][
                    "GetMediaPoolItem"
                ]["GetClipProperty"]["value"]["File Path"] = "wrong/base.mov"
                store.inventory["items"][1]["evidence"]["GetClipProperty"]["value"][
                    "File Path"
                ] = "wrong/base.mov"
            else:
                store.inventory["timelineMappings"][0]["poolItemUid"] = {
                    "value": MODULE.MEDIA_UID
                }
            _refuses(output, config, store, "changed pool/locator/proxy must refuse")
            assert store.calls == []

    with tempfile.TemporaryDirectory() as temporary:
        output, config, store = _setup(Path(temporary))
        result_file = MODULE.PLUGIN_ROOT / MODULE.FINALIZE_RESULT_NAME
        result_file.write_text("{}", encoding="utf-8")
        _refuses(output, config, store, "changed finalizer-result pin must refuse")
        assert store.calls == []

    for mode in ("false", "throw"):
        with tempfile.TemporaryDirectory() as temporary:
            output, config, store = _setup(Path(temporary))
            store.unlink_mode = mode
            result = _run(output, config, store)
            assert result["status"] == "recovered-online-after-unlink-return-refusal"
            assert [call[0] for call in store.calls] == [
                "UnlinkClips",
                "RelinkClips",
                "SaveProject",
            ]

    for mode in ("false", "throw"):
        with tempfile.TemporaryDirectory() as temporary:
            output, config, store = _setup(Path(temporary))
            store.unlink_mode = mode
            store.relink_mode = "false-no-mutation"
            _refuses(output, config, store, "failed recovery must not be retried")
            assert [call[0] for call in store.calls] == [
                "UnlinkClips",
                "RelinkClips",
            ]

    with tempfile.TemporaryDirectory() as temporary:
        output, config, store = _setup(Path(temporary))
        store.offline_blank = True
        store.unlink_mode = "throw"
        _refuses(output, config, store, "blank locator inventory refusal must stop")
        assert [call[0] for call in store.calls] == ["UnlinkClips"]
        post = next(output.glob("r4-transitions-*-unlink-postflight.json"))
        readback = json.loads(post.read_text())
        assert readback["status"] == "incomplete-or-inconsistent-refused"
        assert "diagnostic" in readback["poolPasses"][0]

    for mutation in (
        "no-mutation",
        "false-no-mutation",
        "unrelated",
        "occurrence",
    ):
        with tempfile.TemporaryDirectory() as temporary:
            output, config, store = _setup(Path(temporary))
            if mutation in {"no-mutation", "false-no-mutation"}:
                store.unlink_mode = mutation
            elif mutation == "unrelated":
                store.mutate_unrelated = True
            else:
                store.mutate_occurrence = True
            _refuses(output, config, store, "unproven offline transition must refuse")
            assert [call[0] for call in store.calls] == ["UnlinkClips"]

    with tempfile.TemporaryDirectory() as temporary:
        output, config, store = _setup(Path(temporary))
        store.change_media_after_unlink = True
        store.unlink_mode = "throw"
        _refuses(output, config, store, "failed recovery source guard must refuse")
        assert [call[0] for call in store.calls] == ["UnlinkClips"]

    with tempfile.TemporaryDirectory() as temporary:
        output, config, store = _setup(Path(temporary))
        store.change_context_after_unlink = True
        store.unlink_mode = "throw"
        _refuses(output, config, store, "changed recovery context must refuse")
        assert [call[0] for call in store.calls] == ["UnlinkClips"]

    for mode in ("false", "throw"):
        with tempfile.TemporaryDirectory() as temporary:
            output, config, store = _setup(Path(temporary))
            store.relink_mode = mode
            result = _run(output, config, store)
            assert result["status"] == "restored-online-after-relink-return-refusal"
            assert [call[0] for call in store.calls] == [
                "UnlinkClips",
                "RelinkClips",
                "SaveProject",
            ]

    with tempfile.TemporaryDirectory() as temporary:
        output, config, store = _setup(Path(temporary))
        store.relink_mode = "false-no-mutation"
        _refuses(output, config, store, "failed relink must not retry")
        assert [call[0] for call in store.calls] == ["UnlinkClips", "RelinkClips"]

    for mode in ("false", "throw"):
        with tempfile.TemporaryDirectory() as temporary:
            output, config, store = _setup(Path(temporary))
            store.save_mode = mode
            _refuses(output, config, store, "save false/throw must refuse")
            assert [call[0] for call in store.calls] == [
                "UnlinkClips",
                "RelinkClips",
                "SaveProject",
            ]


if __name__ == "__main__":
    check()
    print("R4 transition fake checks passed (no live Resolve evidence)")
