"""Stdlib fake checks for the bounded R4 wrong-bytes replacement."""

import hashlib
import importlib.util
import json
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "r4_wrong_bytes", HERE / "r4-wrong-bytes.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
GOOD_SOURCE = HERE / "inputs/base.mov"
RELINK_SOURCE = HERE / "inputs/relink/base.mov"
WRONG_SOURCE = HERE / "inputs/wrong/base.mov"
PNG = b"\x89PNG\r\n\x1a\n" + bytes(32)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _props(path, *, original=False):
    return {
        "File Name": "base.mov",
        "File Path": str(path),
        "Online Status": "Online",
        "File Type": "QuickTime",
        "Resolution": "640x360",
    }


def _timeline(uid, name, source=None):
    row = {
        "GetName": {"value": name},
        "GetUniqueId": {"value": uid},
        "GetStartFrame": {"value": 0},
        "GetEndFrame": {"value": 199},
        "GetStartTimecode": {"value": "00:00:00:00"},
        "GetSettings": {"value": {}},
        "GetMarkers": {"value": {}},
        "tracks": [],
    }
    if source is not None:
        row["tracks"] = [
            {
                "type": "video",
                "index": 1,
                "GetTrackName": {"value": "V1"},
                "GetIsTrackEnabled": {"value": True},
                "GetIsTrackLocked": {"value": False},
                "items": [
                    {
                        "GetUniqueId": {"value": MODULE.OCCURRENCE_UID},
                        "GetStart": {"value": 0},
                        "GetEnd": {"value": 199},
                        "GetDuration": {"value": 199},
                        "GetSourceStartFrame": {"value": 0},
                        "GetSourceEndFrame": {"value": 199},
                        "GetTrackTypeAndIndex": {"value": ["video", 1]},
                        "GetMediaPoolItem": {
                            "GetUniqueId": {"value": MODULE.MEDIA_UID},
                            "GetClipProperty": {"value": _props(source)},
                            "GetMarkers": {"value": {}},
                            "GetAudioMapping": {"value": {}},
                            "sourceBytes": {
                                "status": "reachable",
                                "sha256": digest(source),
                                "hashMatches": digest(source) == MODULE.MEDIA_SHA256,
                            },
                        },
                    }
                ],
            },
            {
                "type": "audio",
                "index": 1,
                "GetTrackName": {"value": "A1"},
                "GetIsTrackEnabled": {"value": True},
                "GetIsTrackLocked": {"value": False},
                "GetTrackSubType": {"value": "stereo"},
                "items": [],
            },
        ]
    return row


class Probe:
    ROOT = None

    @staticmethod
    def sha256(path):
        return digest(path)

    @staticmethod
    def read(obj, method, *args):
        try:
            value = getattr(obj, method)(*args)
            json.dumps(value, allow_nan=False)
            return {"value": value}
        except Exception as error:
            return {"error": f"{type(error).__name__}: {error}"}

    @staticmethod
    def errors(value):
        result = []
        if isinstance(value, dict):
            if "error" in value:
                result.append(value["error"])
            if value.get("hashMatches") is False:
                result.append("source-hash-mismatch")
            if value.get("value", False) is None:
                result.append("null-getter-result-not-established")
            for child in value.values():
                result.extend(Probe.errors(child))
        elif isinstance(value, list):
            for child in value:
                result.extend(Probe.errors(child))
        return result

    @staticmethod
    def media_evidence(item, expected):
        result = {
            method: Probe.read(item, method)
            for method in (
                "GetUniqueId",
                "GetClipProperty",
                "GetMarkers",
                "GetAudioMapping",
            )
        }
        path = result["GetClipProperty"]["value"].get("File Path")
        result["sourceBytes"] = {
            "status": "reachable",
            "sha256": digest(path),
            "hashMatches": digest(path) == expected[path],
        }
        return result

    @staticmethod
    def _r4_pool_inventory(project, expected):
        del expected
        return _fake_pool(project.store)

    @staticmethod
    def require_current(resolve, config, identity):
        del config
        if resolve.store.project.uid != identity["projectId"]:
            raise RuntimeError("project identity changed")
        return resolve.store.project

    @staticmethod
    def observe(resolve, config, identity, expected):
        del config, identity, expected
        fail_now = resolve.store.observe_failure > 0 and (
            not resolve.store.failure_only_after_wrong
            or digest(resolve.store.media_path) == MODULE.WRONG_SHA256
        )
        if fail_now:
            resolve.store.observe_failure -= 1
            raise RuntimeError("injected transient observation failure")
        return deepcopy(resolve.store.state())


class MediaHandle:
    def __init__(self, uid):
        self.uid = uid

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        if self.store.pool_drift and self.uid == MODULE.MEDIA_UID:
            return "changed.mov"
        return "base.mov"

    def GetClipProperty(self):
        path = (
            self.store.shared_path
            if self.uid == MODULE.ORIGINAL_UID
            else self.store.media_path
        )
        return _props(path)

    def GetMarkers(self):
        return {}

    def GetAudioMapping(self):
        return {}


class Folder:
    def __init__(self, uid, store, clip_ids=(), children=()):
        self.uid = uid
        self.store = store
        self.clip_ids = clip_ids
        self.children = children

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.uid

    def GetClipList(self):
        handles = []
        for uid in self.clip_ids:
            item = MediaHandle(uid)
            item.store = self.store
            handles.append(item)
        return handles

    def GetSubFolderList(self):
        return self.children


class MediaPool:
    def __init__(self, store):
        self.store = store

    def GetRootFolder(self):
        child = Folder("folder-r4", self.store, [MODULE.MEDIA_UID])
        return Folder("root", self.store, [MODULE.ORIGINAL_UID], [child])

    def RelinkClips(self, items, folder_path):
        self.store.calls.append(
            ("RelinkClips", [item.GetUniqueId() for item in items], folder_path)
        )
        return self.store.relink_result


class Timeline:
    def __init__(self, store, uid):
        self.store = store
        self.uid = uid

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return next(
            row["name"] for row in self.store.timelines if row["uid"] == self.uid
        )

    def GetMediaPoolItem(self):
        uid = MODULE.R4_POOL_UID if self.uid == MODULE.R4_UID else f"proxy-{self.uid}"
        return ProxyItem(
            uid,
            next(row["name"] for row in self.store.timelines if row["uid"] == self.uid),
        )

    def GetCurrentTimecode(self):
        return self.store.timecode

    def SetCurrentTimecode(self, value):
        self.store.timecode = value
        self.store.calls.append(("SetCurrentTimecode", value))
        return True


class Project:
    def __init__(self, store):
        self.store = store
        self.uid = MODULE.PROJECT_ID
        self.name = store.project_name

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name

    def GetTimelineCount(self):
        return len(self.store.timelines)

    def GetTimelineByIndex(self, index):
        return Timeline(self.store, self.store.timelines[index - 1]["uid"])

    def GetCurrentTimeline(self):
        return Timeline(self.store, self.store.selected_uid)

    def GetMediaPool(self):
        return MediaPool(self.store)

    def GetRenderJobList(self):
        return self.store.render_jobs

    def ExportCurrentFrameAsStill(self, destination):
        self.store.calls.append(("ExportCurrentFrameAsStill", str(destination)))
        Path(destination).write_bytes(PNG)
        return True


class ProxyItem:
    def __init__(self, uid, name):
        self.uid = uid
        self.name = name

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name

    def GetClipProperty(self):
        return {}


class Store:
    def __init__(self, project_name, media_path):
        self.project_name = project_name
        self.media_dir = media_path
        self.media_path = media_path / "relink/base.mov"
        self.shared_path = media_path / "base.mov"
        self.selected_uid = MODULE.R4_UID
        self.timelines = [
            {"uid": MODULE.R4_UID, "name": "VERA 141 R4 availability"},
            *[
                {"uid": uid, "name": name}
                for uid, name in MODULE.ORIGINAL_TIMELINES.items()
            ],
        ]
        self.timecode = "00:00:01:00"
        self.calls = []
        self.observe_failure = 0
        self.failure_only_after_wrong = False
        self.pool_drift = False
        self.relink_result = True
        self.page = "edit"
        self.render_jobs = []

    def state(self):
        return {
            "projectId": MODULE.PROJECT_ID,
            "projectName": self.project_name,
            "GetSettings": {"value": {}},
            "timelines": [
                _timeline(row["uid"], row["name"], self.media_path)
                if row["uid"] == MODULE.R4_UID
                else _timeline(row["uid"], row["name"])
                for row in self.timelines
            ],
        }


def _pool(store):
    expected = {
        str(store.media_path): MODULE.MEDIA_SHA256,
        str(store.shared_path): MODULE.MEDIA_SHA256,
    }
    fake_project = store.project
    return MODULE._pool_inventory(fake_project, Probe, expected)


class Resolve:
    def __init__(self, store):
        self.store = store
        store.project = Project(store)

    def GetProjectManager(self):
        return self

    def GetCurrentProject(self):
        return self.store.project

    def GetProductName(self):
        return "DaVinci Resolve Studio"

    def GetVersion(self):
        return MODULE.BUILD

    def GetCurrentPage(self):
        return self.store.page


def _fake_pool(store):
    mapping = [
        {
            "timelineUid": {"value": row["uid"]},
            "timelineName": {"value": row["name"]},
            "poolItemUid": {
                "value": MODULE.R4_POOL_UID
                if row["uid"] == MODULE.R4_UID
                else f"proxy-{row['uid']}"
            },
            "poolItemName": {"value": row["name"]},
            "poolItemProperties": {"value": {}},
        }
        for row in store.timelines
    ]
    items = []
    for uid, path, folder in (
        (MODULE.ORIGINAL_UID, store.shared_path, "root"),
        (MODULE.MEDIA_UID, store.media_path, "folder-r4"),
    ):
        name = (
            "changed.mov"
            if store.pool_drift and uid == MODULE.MEDIA_UID
            else "base.mov"
        )
        props = _props(path)
        actual = digest(path)
        item_evidence = {
            "GetUniqueId": {"value": uid},
            "GetName": {"value": name},
            "GetClipProperty": {"value": props},
            "GetMarkers": {"value": {}},
            "GetAudioMapping": {"value": {}},
            "sourceBytes": {
                "status": "reachable",
                "sha256": actual,
                "hashMatches": actual == MODULE.MEDIA_SHA256,
            },
        }
        items.append(
            {
                "uid": uid,
                "name": {"value": name},
                "folderUid": folder,
                "evidence": item_evidence,
            }
        )
    return {
        "folders": [
            {"uid": "root", "name": "root"},
            {"uid": "folder-r4", "name": "folder-r4"},
        ],
        "items": items,
        "timelineMappings": mapping,
    }


def _setup(root):
    out = root / "out"
    output = out / "issue-141-observation-fake"
    media = out / "issue-141-media-fake"
    output.mkdir(parents=True)
    media.mkdir(parents=True)
    for relative, source in (
        ("base.mov", GOOD_SOURCE),
        ("relink/base.mov", RELINK_SOURCE),
        ("wrong/base.mov", WRONG_SOURCE),
    ):
        path = media / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, path)
    manifest = {
        "kind": "generated-synthetic-inputs-not-Resolve-evidence",
        "files": [
            {
                "path": relative,
                "sha256": digest(media / relative),
                "sizeBytes": (media / relative).stat().st_size,
            }
            for relative in ("base.mov", "relink/base.mov", "wrong/base.mov")
        ],
    }
    manifest_path = media / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    name = "VERA Issue 141 Synthetic Probe fake"
    store = Store(name, media)
    resolve = Resolve(store)
    pool = _fake_pool(store)
    state = store.state()
    checkpoint = {
        "consistency": "equal-adjacent-reads",
        "captureFailure": None,
        "environment": {"version": MODULE.BUILD},
        "passes": [state, deepcopy(state)],
    }
    checkpoint_path = output / "fresh-r4.json"
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    pool_checkpoint = {
        "status": "equal-read-only-pool-inventory",
        "capture": {
            "capturePath": str(checkpoint_path),
            "sha256": digest(checkpoint_path),
            "status": "equal-adjacent-reads",
        },
        "passes": [pool, deepcopy(pool)],
    }
    pool_checkpoint_path = output / "fresh-r4-pool.json"
    pool_checkpoint_path.write_text(json.dumps(pool_checkpoint), encoding="utf-8")
    offline_dir = output / "offline-cycle-continuation-fake"
    prior_dir = output / "offline-cycle-fake"
    offline_dir.mkdir()
    prior_dir.mkdir()
    prior_result = prior_dir / "result.json"
    prior_result.write_text(json.dumps({"unlinkReturn": True, "unlinkError": None}))
    prior_journal = prior_dir / "journal.jsonl"
    prior_journal.write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {"method": "MediaPool.UnlinkClips", "phase": "request"},
                {"method": "MediaPool.UnlinkClips", "phase": "return", "value": True},
            )
        )
        + "\n"
    )
    groups = {}
    for phase, directory in (("online", prior_dir), ("offline", offline_dir)):
        groups[f"{phase}Samples"] = []
        for frame in (0, 50):
            path = directory / f"{phase}-frame-{frame:03d}.png"
            path.write_bytes(PNG)
            groups[f"{phase}Samples"].append(
                {
                    "phase": phase,
                    "frame": frame,
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": digest(path),
                }
            )
    transition_result = {
        "status": "offline-cycle-candidates-retained",
        "fullOriginalStateRestored": True,
        "restoredPlayhead": "00:00:07:24",
        "relinkReturn": True,
        "relinkError": None,
        "priorCheckpoint": str(prior_dir),
        "priorResultSha256": digest(prior_result),
        "priorJournalSha256": digest(prior_journal),
        **groups,
    }
    result_path = offline_dir / MODULE.OFFLINE_RESULT_NAME
    result_path.write_text(json.dumps(transition_result))
    transition_journal = offline_dir / MODULE.OFFLINE_JOURNAL_NAME
    transition_journal.write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {"method": "MediaPool.RelinkClips", "phase": "request"},
                {"method": "MediaPool.RelinkClips", "phase": "return", "value": True},
            )
        )
        + "\n"
    )
    (offline_dir / "restored-postflight.json").write_text(
        json.dumps(
            {
                "timelineConsistency": "equal-adjacent-reads",
                "poolConsistency": "equal-adjacent-reads",
                "timelinePasses": checkpoint["passes"],
                "poolPasses": pool_checkpoint["passes"],
            }
        )
    )
    config = {
        "action": "r4-wrong-bytes",
        "externalScriptingSetting": "None",
        "projectName": name,
        "outputDir": str(output),
        "mediaDir": str(media),
        "manifestSha256": digest(manifest_path),
    }
    Probe.ROOT = root
    MODULE.CHECKPOINT_NAME = checkpoint_path.name
    MODULE.CHECKPOINT_SHA256 = digest(checkpoint_path)
    MODULE.POOL_CHECKPOINT_NAME = pool_checkpoint_path.name
    MODULE.POOL_CHECKPOINT_SHA256 = digest(pool_checkpoint_path)
    MODULE.OFFLINE_CYCLE_DIR = offline_dir.name
    MODULE.OFFLINE_RESULT_SHA256 = digest(result_path)
    MODULE.OFFLINE_JOURNAL_SHA256 = digest(transition_journal)
    return output, config, store, resolve, result_path


def _run(output, config, resolve):
    return MODULE.run(resolve, config, probe=Probe)


def _refuses(output, config, resolve, phrase):
    try:
        _run(output, config, resolve)
    except RuntimeError as error:
        assert phrase in str(error) or "partial evidence" in str(error)
    else:
        raise AssertionError("expected refusal: " + phrase)


def check():
    for drift in ("sample", "restored-pair"):
        with tempfile.TemporaryDirectory() as temporary:
            output, config, store, resolve, result_path = _setup(Path(temporary))
            if drift == "sample":
                dependency = json.loads(result_path.read_text())
                Path(dependency["onlineSamples"][0]["path"]).write_bytes(b"changed")
            else:
                path = result_path.parent / "restored-postflight.json"
                value = json.loads(path.read_text())
                value["timelinePasses"] = []
                path.write_text(json.dumps(value))
            _refuses(output, config, resolve, "partial evidence")
            assert digest(store.media_path) == MODULE.MEDIA_SHA256
            assert not store.calls
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        output, config, store, resolve, _ = _setup(root)
        before_shared, before_wrong = (
            digest(store.shared_path),
            digest(store.media_dir / "wrong/base.mov"),
        )
        result = _run(output, config, resolve)
        assert result["status"] == "restored-original-bytes"
        call_names = [call[0] for call in store.calls]
        assert call_names == [
            "RelinkClips",
            "SetCurrentTimecode",
            "ExportCurrentFrameAsStill",
            "SetCurrentTimecode",
            "RelinkClips",
            "SetCurrentTimecode",
            "ExportCurrentFrameAsStill",
            "SetCurrentTimecode",
        ]
        assert store.calls[0][1:] == (
            [MODULE.MEDIA_UID],
            str(store.media_dir / "relink"),
        )
        assert store.calls[4][1:] == (
            [MODULE.MEDIA_UID],
            str(store.media_dir / "relink"),
        )
        records = [
            json.loads(line)
            for line in Path(result["journal"]).read_text().splitlines()
        ]
        methods = [(row["method"], row["phase"]) for row in records]
        assert methods.index(("atomic-replace-wrong-bytes", "request")) < methods.index(
            ("atomic-replace-wrong-bytes", "return")
        )
        assert methods.index(("atomic-replace-wrong-bytes", "return")) < methods.index(
            ("RelinkClips", "request")
        )
        relink_rows = [row for row in records if row["method"] == "RelinkClips"]
        assert [row["phase"] for row in relink_rows] == ["request", "return"] * 2
        assert relink_rows[0]["value"]["wrongBytes"] is True
        assert relink_rows[2]["value"]["wrongBytes"] is False
        assert methods.index(
            ("atomic-restore-original-bytes", "request")
        ) < methods.index(("atomic-restore-original-bytes", "return"))
        evidence = json.loads(Path(result["evidence"]).read_text())
        assert evidence["wrongMismatch"]["actualSha256"] == MODULE.WRONG_SHA256
        assert evidence["wrongMismatch"]["expectedSha256"] == MODULE.MEDIA_SHA256
        assert evidence["restored"] is True
        assert digest(store.media_path) == MODULE.MEDIA_SHA256
        assert digest(store.shared_path) == before_shared
        assert digest(store.media_dir / "wrong/base.mov") == before_wrong
        assert not list((store.media_dir / "relink").glob(".r4-wrong-bytes-*"))

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        output, config, store, resolve, _ = _setup(root)
        store.selected_uid = "changed"
        _refuses(output, config, resolve, "selected")
        assert digest(store.media_path) == MODULE.MEDIA_SHA256
        assert not store.calls

    for drift in ("timeline", "pool"):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output, config, store, resolve, _ = _setup(root)
            if drift == "timeline":
                store.timelines[0]["name"] = "changed"
            else:
                store.pool_drift = True
            _refuses(output, config, resolve, "checkpoint")
            assert digest(store.media_path) == MODULE.MEDIA_SHA256
            assert not store.calls

    for drift in ("page", "queue"):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output, config, store, resolve, _ = _setup(root)
            if drift == "page":
                store.page = "cut"
            else:
                store.render_jobs = [{"jobId": "busy"}]
            _refuses(output, config, resolve, "page, playhead, or idle render-queue")
            assert digest(store.media_path) == MODULE.MEDIA_SHA256
            assert not store.calls

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        output, config, store, resolve, _ = _setup(root)
        (store.media_dir / "relink/base.mov").unlink()
        (store.media_dir / "relink/base.mov").symlink_to(store.shared_path)
        _refuses(output, config, resolve, "manifest candidate differs")
        assert not store.calls

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        output, config, store, resolve, _ = _setup(root)
        (store.media_dir / "wrong/base.mov").write_bytes(b"changed wrong source")
        _refuses(output, config, resolve, "manifest candidate differs")
        assert digest(store.media_path) == MODULE.MEDIA_SHA256
        assert not store.calls

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        output, config, store, resolve, _ = _setup(root)
        store.observe_failure = 1
        _refuses(output, config, resolve, "partial evidence")
        assert digest(store.media_path) == MODULE.MEDIA_SHA256

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        output, config, store, resolve, _ = _setup(root)
        store.observe_failure = 1
        store.failure_only_after_wrong = True
        _refuses(output, config, resolve, "partial evidence")
        assert digest(store.media_path) == MODULE.MEDIA_SHA256
        result_file = next(
            path
            for path in output.glob("r4-wrong-bytes-*.json")
            if json.loads(path.read_text()).get("kind")
            == "same-locator-wrong-bytes-observation-not-asset-identity-proof"
        )
        evidence = json.loads(result_file.read_text())
        assert evidence["restored"] is True
        assert evidence["failure"].startswith("RuntimeError: injected transient")

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        output, config, store, resolve, _ = _setup(root)
        original_replace = MODULE.os.replace
        count = 0

        def replace_then_throw(source, destination):
            nonlocal count
            original_replace(source, destination)
            count += 1
            if count == 1:
                raise OSError("injected failure after atomic wrong-byte replace")

        MODULE.os.replace = replace_then_throw
        try:
            _refuses(output, config, resolve, "partial evidence")
        finally:
            MODULE.os.replace = original_replace
        assert digest(store.media_path) == MODULE.MEDIA_SHA256
        assert digest(store.shared_path) == MODULE.MEDIA_SHA256
        evidence = next(
            path
            for path in output.glob("r4-wrong-bytes-*.json")
            if json.loads(path.read_text()).get("kind")
            == "same-locator-wrong-bytes-observation-not-asset-identity-proof"
        )
        assert json.loads(evidence.read_text())["restored"] is True

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        output, config, store, resolve, _ = _setup(root)
        store.relink_result = False
        _refuses(output, config, resolve, "partial evidence")
        assert digest(store.media_path) == MODULE.MEDIA_SHA256
        assert digest(store.shared_path) == MODULE.MEDIA_SHA256
        assert not any(call[0] == "ExportCurrentFrameAsStill" for call in store.calls)


if __name__ == "__main__":
    check()
    print("R4 wrong-bytes fake checks passed (no live Resolve evidence)")
