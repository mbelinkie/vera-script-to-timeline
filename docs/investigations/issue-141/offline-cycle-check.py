"""Fake checks for the bounded native offline picture cycle."""

import hashlib
import importlib.util
import json
import tempfile
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fake = load("offline_cycle_range_fake", "r4-range-repair-check.py")
cycle = load("offline_cycle", "offline-cycle.py")
reader = fake.MODULE
ITEM_UID = cycle.ITEM_UID


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Handle:
    def GetUniqueId(self):
        return reader.MEDIA_UID


class Folder:
    def GetUniqueId(self):
        return "root"

    def GetClipList(self):
        return [Handle()]

    def GetSubFolderList(self):
        return []


class Pool:
    def __init__(self, project):
        self.project = project

    def GetRootFolder(self):
        return Folder()

    def UnlinkClips(self, clips):
        store = self.project.store
        store.calls.append(("UnlinkClips", [x.GetUniqueId() for x in clips]))
        if store.mode == "unlink-throw":
            raise RuntimeError("injected unlink throw")
        self.project.set_online(False)
        if store.mode == "unknown-drift":
            store.state["GetSettings"]["value"]["unexpected"] = True
        return store.mode != "unlink-false"

    def RelinkClips(self, clips, folder):
        store = self.project.store
        store.calls.append(("RelinkClips", [x.GetUniqueId() for x in clips], folder))
        self.project.set_online(True)
        return store.mode != "relink-false"


class Timeline(fake.TimelineHandle):
    def __init__(self, project):
        super().__init__(project.store, reader.R4_UID)
        self.project = project

    def GetCurrentTimecode(self):
        return self.project.resolve.timecode

    def SetCurrentTimecode(self, value):
        self.project.store.calls.append(("SetCurrentTimecode", value))
        self.project.resolve.timecode = value
        return True


class Project(fake.Project):
    def GetCurrentTimeline(self):
        return Timeline(self)

    def GetMediaPool(self):
        return Pool(self)

    def GetCurrentRenderFormatAndCodec(self):
        return {"format": "mov", "codec": "H264"}

    def GetRenderJobList(self):
        return []

    def ExportCurrentFrameAsStill(self, path):
        self.store.calls.append(
            ("ExportCurrentFrameAsStill", self.resolve.timecode, path)
        )
        if self.store.mode == "offline-export-false" and not self.is_online():
            return False
        if self.store.mode == "online-export-false" and self.is_online():
            return False
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\nfake still")
        return True

    def is_online(self):
        return (
            self.store.pool["items"][0]["evidence"]["GetClipProperty"]["value"][
                "Online Status"
            ]
            == "Online"
        )

    def set_online(self, online):
        store = self.store
        value = "Online" if online else "Offline"
        path = str(store.source)
        for props in (
            store.state["timelines"][1]["tracks"][0]["items"][0]["GetMediaPoolItem"][
                "GetClipProperty"
            ]["value"],
            store.pool["items"][0]["evidence"]["GetClipProperty"]["value"],
        ):
            props["Online Status"] = value
            props["File Path"] = path if online else f"OFFLINE - {path}"
            props["Clip Directory"] = str(store.source.parent) if online else ""
        bytes_evidence = (
            {"status": "reachable", "sha256": digest(store.source), "hashMatches": True}
            if online
            else {
                "status": "offline-locator-not-accessed",
                "approvedLocator": path,
                "expectedSha256": digest(store.source),
            }
        )
        store.state["timelines"][1]["tracks"][0]["items"][0]["GetMediaPoolItem"][
            "sourceBytes"
        ] = deepcopy(bytes_evidence)
        store.pool["items"][0]["evidence"]["sourceBytes"] = deepcopy(bytes_evidence)


class Resolve(fake.Resolve):
    def __init__(self, store):
        super().__init__(store)
        self.project = Project(store)
        self.project.resolve = self
        self.page = "edit"
        self.timecode = "00:00:07:24"

    def GetProjectManager(self):
        return self.manager

    def GetCurrentPage(self):
        return self.page

    def GetProductName(self):
        return "DaVinci Resolve Studio"

    def GetVersion(self):
        return reader.BUILD


class Probe(fake.Probe):
    @staticmethod
    def require_current(resolve, config, identity):
        project = resolve.project
        if (
            project.GetUniqueId() != identity["projectId"]
            or project.GetName() != config["projectName"]
        ):
            raise RuntimeError("project identity mismatch")
        return project

    @staticmethod
    def observe(resolve, config, identity, expected):
        del config, identity, expected
        return deepcopy(resolve.store.state)

    @staticmethod
    def _r4_pool_inventory(project, expected):
        del expected
        return deepcopy(project.store.pool)

    @staticmethod
    def source_evidence(locator, expected):
        value = digest(locator)
        return {"sha256": value, "hashMatches": value == expected[locator]}


def setup(root, mode):
    output, media = (
        root / "out/issue-141-observation-fake",
        root / "out/issue-141-media-fake",
    )
    output.mkdir(parents=True)
    (media / "relink").mkdir(parents=True)
    source = media / "relink/base.mov"
    source.write_bytes(b"fixed fake source")
    name = "VERA Issue 141 Synthetic Probe fake"
    manifest = {
        "kind": "generated-synthetic-inputs-not-Resolve-evidence",
        "files": [
            {
                "path": "relink/base.mov",
                "sha256": digest(source),
                "sizeBytes": source.stat().st_size,
            }
        ],
    }
    (media / "manifest.json").write_text(json.dumps(manifest))
    config = {
        "action": "offline-cycle",
        "externalScriptingSetting": "None",
        "projectName": name,
        "outputDir": str(output),
        "mediaDir": str(media),
        "manifestSha256": digest(media / "manifest.json"),
    }
    store = fake.Store(name, source)
    store.mode, store.calls = mode, []
    store.expected = {str(source): digest(source)}
    r4 = store.state["timelines"][1]
    r4.update(
        GetStartFrame={"value": 0},
        GetEndFrame={"value": 199},
        GetStartTimecode={"value": "00:00:00:00"},
    )
    item = r4["tracks"][0]["items"][0]
    item["GetUniqueId"] = {"value": ITEM_UID}
    item["GetMediaPoolItem"]["GetClipProperty"]["value"].update(
        {
            "File Path": str(source),
            "Clip Directory": str(source.parent),
            "Online Status": "Online",
        }
    )
    poolrow = store.pool["items"][0]
    poolrow["evidence"]["GetClipProperty"]["value"].update(
        {
            "File Path": str(source),
            "Clip Directory": str(source.parent),
            "Online Status": "Online",
        }
    )
    store.selected_uid = reader.R4_UID
    resolve = Resolve(store)
    state, pool = deepcopy(store.state), deepcopy(store.pool)
    cap = {
        "consistency": "equal-adjacent-reads",
        "captureFailure": None,
        "passes": [state, deepcopy(state)],
    }
    poolpin = {
        "status": "equal-read-only-pool-inventory",
        "capture": {
            "capturePath": str(output / cycle.CAPTURE_NAME),
            "sha256": "will-fill",
        },
        "passes": [pool, deepcopy(pool)],
    }
    cpath, ppath = output / cycle.CAPTURE_NAME, output / cycle.POOL_NAME
    cpath.write_text(json.dumps(cap))
    cycle.CAPTURE_SHA = digest(cpath)
    poolpin["capture"]["sha256"] = cycle.CAPTURE_SHA
    ppath.write_text(json.dumps(poolpin))
    cycle.POOL_SHA = digest(ppath)
    checkpoint_cap = deepcopy(cap)
    checkpoint_pool = deepcopy(poolpin)
    (output / cycle.CHECKPOINT_CAPTURE_NAME).write_text(json.dumps(checkpoint_cap))
    cycle.CHECKPOINT_CAPTURE_SHA = digest(output / cycle.CHECKPOINT_CAPTURE_NAME)
    checkpoint_pool["capture"]["capturePath"] = str(
        output / cycle.CHECKPOINT_CAPTURE_NAME
    )
    checkpoint_pool["capture"]["sha256"] = cycle.CHECKPOINT_CAPTURE_SHA
    (output / cycle.CHECKPOINT_POOL_NAME).write_text(json.dumps(checkpoint_pool))
    cycle.CHECKPOINT_POOL_SHA = digest(output / cycle.CHECKPOINT_POOL_NAME)
    Probe.ROOT = root
    return resolve, config, store, source


def demo():
    baseline = {
        "source": {
            "GetUniqueId": {"value": reader.MEDIA_UID},
            "GetClipProperty": {
                "value": {"File Path": "/media/base.mov", "Online Status": "Online"}
            },
            "sourceBytes": {"sha256": "good"},
        },
        "other": {
            "GetUniqueId": {"value": "other-media"},
            "GetClipProperty": {
                "value": {"File Path": "/media/other.mov", "Online Status": "Online"}
            },
            "sourceBytes": {"sha256": "other-good"},
        },
    }
    changed_other = deepcopy(baseline)
    changed_other["other"]["GetClipProperty"]["value"]["Online Status"] = "Offline"
    changed_other["other"]["sourceBytes"]["sha256"] = "wrong"
    assert not cycle._normalize_offline(changed_other, baseline, "/media/base.mov")

    for mode in (
        "success",
        "offline-export-false",
        "online-export-false",
        "unknown-drift",
        "unlink-false",
        "unlink-throw",
        "relink-false",
        "bad-pin",
        "bad-source",
    ):
        with tempfile.TemporaryDirectory() as directory:
            resolve, config, store, source = setup(Path(directory), mode)
            if mode == "bad-pin":
                (Path(config["outputDir"]) / cycle.CAPTURE_NAME).write_text("tampered")
            if mode == "bad-source":
                source.write_bytes(b"changed")
            if mode in {"bad-pin", "bad-source"}:
                try:
                    cycle.run(resolve, config, probe=Probe)
                except RuntimeError:
                    assert store.calls == []
                    continue
                raise AssertionError(f"{mode} must refuse before native calls")
            result = cycle.run(resolve, config, probe=Probe)
            calls = store.calls
            unlink_count = sum(call[0] == "UnlinkClips" for call in calls)
            relink_count = sum(call[0] == "RelinkClips" for call in calls)
            assert unlink_count == (
                0 if mode in {"bad-pin", "bad-source", "online-export-false"} else 1
            ), (mode, calls)
            assert relink_count == (
                1
                if mode
                in {"success", "offline-export-false", "unlink-false", "relink-false"}
                else 0
            ), (mode, calls)
            assert sum(call[0] == "ExportCurrentFrameAsStill" for call in calls) <= 4
            assert "SaveProject" not in [call[0] for call in calls]
            if mode == "success":
                assert (
                    result["status"] == "offline-cycle-candidates-retained"
                    and len(result["samples"]) == 4
                )
                assert resolve.timecode == "00:00:07:24"
            if mode == "unknown-drift":
                assert relink_count == 0
                assert result["failure"]
                assert "restoredPlayhead" not in result
            if mode == "offline-export-false":
                assert relink_count == 1 and result.get("offlineStillFailure")
            if mode in {"bad-pin", "bad-source", "online-export-false"}:
                assert unlink_count == 0
    print("Offline cycle fake checks passed")


def continuation_setup(root, mode="success"):
    resolve, config, store, _ = setup(root, "success")
    media = Path(config["mediaDir"])
    source = media / "relink/base.mov"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fixed fake source")
    manifest = {
        "kind": "generated-synthetic-inputs-not-Resolve-evidence",
        "files": [
            {
                "path": "relink/base.mov",
                "sha256": digest(source),
                "sizeBytes": source.stat().st_size,
            }
        ],
    }
    (media / "manifest.json").write_text(json.dumps(manifest))
    config["manifestSha256"] = digest(media / "manifest.json")
    config["action"] = "offline-picture-continuation"
    store.source, store.expected, store.mode = (
        source,
        {str(source): digest(source)},
        mode,
    )
    resolve.timecode = "00:00:02:00"
    row = store.state["timelines"][1]
    row.update(
        GetStartFrame={"value": 0},
        GetEndFrame={"value": 199},
        GetStartTimecode={"value": "00:00:00:00"},
    )
    item = row["tracks"][0]["items"][0]
    item["GetUniqueId"] = {"value": ITEM_UID}
    for props in (
        item["GetMediaPoolItem"]["GetClipProperty"]["value"],
        store.pool["items"][0]["evidence"]["GetClipProperty"]["value"],
    ):
        props.update(
            {
                "File Path": str(source),
                "Clip Directory": str(source.parent),
                "Online Status": "Online",
            }
        )
    for evidence in (
        item["GetMediaPoolItem"],
        store.pool["items"][0]["evidence"],
    ):
        evidence["sourceBytes"] = {
            "status": "reachable",
            "sha256": digest(source),
            "hashMatches": True,
        }
    store.selected_uid = reader.R4_UID
    partial = Path(config["outputDir"]) / cycle.PARTIAL_NAME
    partial.mkdir()
    resolve.project.set_online(True)
    online_state, online_pool = deepcopy(store.state), deepcopy(store.pool)
    resolve.project.set_online(False)
    offline_state, offline_pool = deepcopy(store.state), deepcopy(store.pool)
    if mode == "unknown-pinned":
        online_state["timelines"][1]["GetSettings"]["value"]["unexpected"] = True
    if mode == "unknown-prefix":
        offline_state["timelines"][1]["tracks"][0]["items"][0]["GetMediaPoolItem"][
            "GetClipProperty"
        ]["value"]["File Path"] = "OFFLINE - /unexpected/path.mov"

    def pair(state, pool):
        return {
            "selectedTimelineUid": reader.R4_UID,
            "timelineConsistency": "equal-adjacent-reads",
            "poolConsistency": "equal-adjacent-reads",
            "timelinePasses": [state, deepcopy(state)],
            "poolPasses": [pool, deepcopy(pool)],
        }

    def write(name, value):
        path = partial / name
        path.write_text(json.dumps(value))
        return digest(path)

    online = pair(online_state, online_pool)
    offline = pair(offline_state, offline_pool)
    cycle.PARTIAL_ONLINE_SHA = write("online-preflight.json", online)
    cycle.PARTIAL_OFFLINE_SHA = write("offline-postflight.json", offline)
    journal = partial / "journal.jsonl"
    journal.write_text(
        json.dumps({"method": "MediaPool.UnlinkClips", "phase": "request"}) + "\n"
    )
    cycle.PARTIAL_JOURNAL_SHA = digest(journal)
    imgs = []
    for frame, tc in ((0, "00:00:00:00"), (50, "00:00:02:00")):
        name = f"online-frame-{frame:03d}.png"
        image = partial / name
        image.write_bytes(b"\x89PNG\r\n\x1a\nfake online")
        imgs.append(
            {
                "phase": "online",
                "frame": frame,
                "timecode": tc,
                "path": str(image),
                "bytes": image.stat().st_size,
                "sha256": digest(image),
            }
        )
    result = {
        "status": "offline-cycle-review-required",
        "unlinkReturn": True,
        "unlinkError": None,
        "initialPlayhead": "00:00:07:24",
        "initialPage": "edit",
        "failure": "RuntimeError: Offline full-state delta exceeded approved leaves",
        "samples": imgs,
    }
    cycle.PARTIAL_RESULT_SHA = write("result.json", result)
    cycle.PARTIAL_SOURCE_SHA = digest(source)
    # Update fake pin bytes and their bound capture references.
    out = Path(config["outputDir"])
    cap = {
        "consistency": "equal-adjacent-reads",
        "captureFailure": None,
        "passes": [online_state, deepcopy(online_state)],
    }
    cpath = out / cycle.CAPTURE_NAME
    cpath.write_text(json.dumps(cap))
    cycle.CAPTURE_SHA = digest(cpath)
    pool_pin = {
        "status": "equal-read-only-pool-inventory",
        "capture": {"capturePath": str(cpath), "sha256": cycle.CAPTURE_SHA},
        "passes": [online_pool, deepcopy(online_pool)],
    }
    ppath = out / cycle.POOL_NAME
    ppath.write_text(json.dumps(pool_pin))
    cycle.POOL_SHA = digest(ppath)
    cycle.RANGE_REPAIR_SHA = digest(HERE / "r4-range-repair.py")
    cycle.TRANSITIONS_SHA = digest(HERE / "r4-transitions.py")
    Probe.ROOT = root
    return resolve, config, store, source


def continuation_demo():
    for mode in (
        "success",
        "offline-export-false",
        "relink-false",
        "unknown-pinned",
        "unknown-prefix",
        "bad-source",
        "bad-result-pin",
    ):
        with tempfile.TemporaryDirectory() as directory:
            resolve, config, store, source = continuation_setup(Path(directory), mode)
            if mode == "bad-source":
                source.write_bytes(b"changed bytes")
            if mode == "bad-result-pin":
                partial = Path(config["outputDir"]) / cycle.PARTIAL_NAME
                (partial / "result.json").write_text("tampered")
            if mode in {
                "bad-source",
                "bad-result-pin",
                "unknown-pinned",
                "unknown-prefix",
            }:
                try:
                    cycle.run(resolve, config, probe=Probe)
                except RuntimeError:
                    assert not [c for c in store.calls if c[0] == "RelinkClips"]
                    continue
                raise AssertionError(f"{mode} must refuse before native mutation")
            report = cycle.run(resolve, config, probe=Probe)
            relinks = [c for c in store.calls if c[0] == "RelinkClips"]
            unlinks = [c for c in store.calls if c[0] == "UnlinkClips"]
            exports = [c for c in store.calls if c[0] == "ExportCurrentFrameAsStill"]
            assert len(unlinks) == 0 and len(relinks) == (
                0 if mode in {"unknown-pinned", "unknown-prefix"} else 1
            ), (mode, store.calls)
            assert len(exports) <= 2 and all(
                "online-frame" not in c[-1] for c in exports
            )
            assert not [c for c in store.calls if c[0] == "SaveProject"]
            if mode == "success":
                assert report["status"] == "offline-cycle-candidates-retained"
                assert (
                    len(report["onlineSamples"]) == len(report["offlineSamples"]) == 2
                )
                assert (
                    report["fullOriginalStateRestored"]
                    and resolve.timecode == "00:00:07:24"
                )
            if mode == "offline-export-false":
                assert len(relinks) == 1 and report.get("offlineStillFailure")
            if mode == "relink-false":
                assert len(relinks) == 1 and report["fullOriginalStateRestored"]
                assert report["status"] == "offline-cycle-continuation-review-required"
    print("Offline continuation fake checks passed")


if __name__ == "__main__":
    demo()
    continuation_demo()
