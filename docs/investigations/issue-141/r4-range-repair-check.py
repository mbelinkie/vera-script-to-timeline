"""Fake acceptance checks for the single-call R4 timeline-range repair."""

import hashlib
import importlib.util
import json
import tempfile
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "r4_range_repair", HERE / "r4-range-repair.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Probe:
    ROOT = None

    @staticmethod
    def sha256(path):
        return digest(path)

    @staticmethod
    def errors(value):
        found = []
        if isinstance(value, dict):
            if "error" in value or value.get("hashMatches") is False:
                found.append("invalid evidence")
            if value.get("value", False) is None:
                found.append("null getter")
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
            raise RuntimeError("project identity drift")
        return project

    @staticmethod
    def observe(resolve, config, identity, expected):
        del config, identity
        if resolve.store.fail_after_set and resolve.store.setter_calls:
            raise RuntimeError("injected incomplete readback")
        if set(expected) != set(resolve.store.expected):
            raise RuntimeError("manifest byte expectations incomplete")
        return deepcopy(resolve.store.state)

    @staticmethod
    def _r4_pool_inventory(project, expected):
        if set(expected) != set(project.store.expected):
            raise RuntimeError("manifest byte expectations incomplete")
        return deepcopy(project.store.pool)

    @staticmethod
    def source_evidence(locator, expected):
        path = Path(locator)
        if path.is_symlink():
            return {"status": "symlink-not-accessed"}
        value = digest(path)
        return {"sha256": value, "hashMatches": value == expected[locator]}


def _timeline(uid, name, *, start=0, end=200, timecode="00:00:00:00", tracks=None):
    return {
        "GetName": {"value": name},
        "GetUniqueId": {"value": uid},
        "GetStartFrame": {"value": start},
        "GetEndFrame": {"value": end},
        "GetStartTimecode": {"value": timecode},
        "GetSettings": {"value": {"timelineFrameRate": "25"}},
        "GetMarkers": {"value": {"0": {"name": "pinned"}}},
        "tracks": tracks or [],
    }


class TimelineHandle:
    def __init__(self, store, uid):
        self.store, self.uid = store, uid

    def _row(self):
        return next(
            row
            for row in self.store.state["timelines"]
            if row["GetUniqueId"]["value"] == self.uid
        )

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self._row()["GetName"]["value"]

    def SetStartTimecode(self, value):
        self.store.setter_calls.append(value)
        if self.store.mode == "raise" and len(self.store.setter_calls) == 1:
            raise RuntimeError("injected setter exception")
        if self.store.mode == "false" and len(self.store.setter_calls) == 1:
            return False
        if self.store.mode == "failed-restore" and len(self.store.setter_calls) > 1:
            return False
        row = self._row()
        if value == MODULE.ORIGINAL_TIMECODE:
            row["GetStartTimecode"]["value"] = MODULE.ORIGINAL_TIMECODE
            row["GetStartFrame"]["value"] = 90000
            row["GetEndFrame"]["value"] = 90000
            return self.store.mode != "failed-restore"
        row["GetStartTimecode"]["value"] = MODULE.TARGET_TIMECODE
        row["GetStartFrame"]["value"] = 0
        row["GetEndFrame"]["value"] = (
            90000
            if self.store.mode in {"partial", "failed-restore"}
            else 199
            if self.store.mode == "end-199"
            else 200
        )
        if self.store.mode == "shifted":
            row["tracks"][0]["items"][0]["GetStart"]["value"] = 1
        if self.store.drift_after_set:
            self.store.state["timelines"][0]["GetSettings"]["value"]["changed"] = True
        return True


class Project:
    def __init__(self, store):
        self.store = store
        self.uid, self.name = MODULE.PROJECT_ID, store.project_name

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name

    def IsRenderingInProgress(self):
        return self.store.rendering

    def GetCurrentTimeline(self):
        return TimelineHandle(self.store, self.store.selected_uid)

    def GetTimelineCount(self):
        return len(self.store.state["timelines"])

    def GetTimelineByIndex(self, index):
        row = self.store.state["timelines"][index - 1]
        return TimelineHandle(self.store, row["GetUniqueId"]["value"])

    def SetCurrentTimeline(self, target):
        self.store.selection_calls.append(target.GetUniqueId())
        self.store.selected_uid = target.GetUniqueId()
        return True


class Manager:
    def __init__(self, store):
        self.project = Project(store)

    def GetCurrentProject(self):
        return self.project


class Resolve:
    def __init__(self, store):
        self.store = store
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
    def __init__(self, project_name, source, *, mode="success", drift_after_set=False):
        self.project_name, self.source = project_name, source
        self.expected = {str(source): digest(source)}
        media = {
            "GetUniqueId": {"value": MODULE.MEDIA_UID},
            "GetClipProperty": {
                "value": {
                    "File Name": "base.mov",
                    "File Path": str(source),
                    "Online Status": "Online",
                }
            },
            "GetMarkers": {"value": {}},
            "GetAudioMapping": {"value": {}},
            "sourceBytes": {
                "status": "reachable",
                "sha256": digest(source),
                "hashMatches": True,
            },
        }
        item = {
            "GetUniqueId": {"value": MODULE.ITEM_UID},
            "GetStart": {"value": 0},
            "GetEnd": {"value": 199},
            "GetDuration": {"value": 199},
            "GetSourceStartFrame": {"value": 0},
            "GetSourceEndFrame": {"value": 199},
            "GetTrackTypeAndIndex": {"value": ["video", 1]},
            "GetMediaPoolItem": media,
        }
        self.state = {
            "projectId": MODULE.PROJECT_ID,
            "projectName": project_name,
            "GetSettings": {"value": {"timelineFrameRate": "25"}},
            "timelines": [
                _timeline(MODULE.MATRIX_UID, MODULE.MATRIX_NAME),
                _timeline(
                    MODULE.R4_UID,
                    MODULE.R4_NAME,
                    start=90000,
                    end=90000,
                    timecode=MODULE.ORIGINAL_TIMECODE,
                    tracks=[
                        {
                            "type": "video",
                            "index": 1,
                            "GetTrackName": {"value": "V1"},
                            "items": [item],
                        },
                        {
                            "type": "audio",
                            "index": 1,
                            "GetTrackName": {"value": "A1"},
                            "items": [],
                        },
                    ],
                ),
                _timeline("88f7923d-55a7-471f-b09b-cf10f9fae8ad", "VERA 141 Baseline"),
                _timeline(
                    "aa2b8e36-83bd-4292-9e33-217c00ca192f", "VERA 141 R1 identity"
                ),
            ],
        }
        self.pool = {
            "folders": [{"uid": "root", "name": "Master"}],
            "items": [
                {
                    "uid": MODULE.MEDIA_UID,
                    "name": {"value": "base.mov"},
                    "evidence": {
                        "GetUniqueId": {"value": MODULE.MEDIA_UID},
                        "GetClipProperty": {"value": media["GetClipProperty"]["value"]},
                        "sourceBytes": media["sourceBytes"],
                    },
                }
            ],
            "timelineMappings": [
                {
                    "timelineUid": {"value": MODULE.MATRIX_UID},
                    "poolItemUid": {"value": "matrix-proxy"},
                },
                {
                    "timelineUid": {"value": MODULE.R4_UID},
                    "poolItemUid": {"value": MODULE.R4_POOL_UID},
                },
                {
                    "timelineUid": {"value": "88f7923d-55a7-471f-b09b-cf10f9fae8ad"},
                    "poolItemUid": {"value": "base-proxy"},
                },
                {
                    "timelineUid": {"value": "aa2b8e36-83bd-4292-9e33-217c00ca192f"},
                    "poolItemUid": {"value": "r1-proxy"},
                },
            ],
        }
        self.selected_uid, self.rendering = MODULE.MATRIX_UID, False
        self.mode, self.drift_after_set = mode, drift_after_set
        self.fail_after_set = mode == "incomplete"
        self.setter_calls, self.selection_calls = [], []


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return digest(path)


def _setup(root, *, mode="success", drift_after_set=False):
    out = root / "out"
    output, media = out / "issue-141-observation-fake", out / "issue-141-media-fake"
    output.mkdir(parents=True)
    media.mkdir(parents=True)
    source = media / "base.mov"
    source.write_bytes(b"synthetic base media")
    project_name = "VERA Issue 141 Synthetic Probe fake"
    store = Store(project_name, source, mode=mode, drift_after_set=drift_after_set)
    manifest = {
        "kind": "generated-synthetic-inputs-not-Resolve-evidence",
        "files": [
            {
                "path": "base.mov",
                "sha256": digest(source),
                "sizeBytes": source.stat().st_size,
            }
        ],
    }
    manifest_path = media / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    config = {
        "action": "r4-range-repair",
        "externalScriptingSetting": "None",
        "projectName": project_name,
        "outputDir": str(output),
        "mediaDir": str(media),
        "manifestSha256": digest(manifest_path),
    }
    state = store.state
    pool = store.pool
    matrix = {
        "selectedTimelineUid": MODULE.MATRIX_UID,
        "timelineConsistency": "equal-adjacent-reads",
        "poolConsistency": "equal-adjacent-reads",
        "timelinePasses": [state, deepcopy(state)],
        "poolPasses": [pool, deepcopy(pool)],
    }
    r4_capture = {
        "consistency": "equal-adjacent-reads",
        "captureFailure": None,
        "passes": [state, deepcopy(state)],
    }
    r4_pool = {
        "status": "equal-read-only-pool-inventory",
        "capture": {
            "capturePath": str(output / "r4.json"),
            "sha256": "PIN_CAPTURE_SHA",
        },
        "passes": [pool, deepcopy(pool)],
    }
    old = (
        MODULE.MATRIX_PIN,
        MODULE.MATRIX_SHA256,
        MODULE.R4_CAPTURE_PIN,
        MODULE.R4_CAPTURE_SHA256,
        MODULE.R4_POOL_PIN,
        MODULE.R4_POOL_SHA256,
    )
    MODULE.MATRIX_PIN, MODULE.MATRIX_SHA256 = (
        "matrix.json",
        _write(output / "matrix.json", matrix),
    )
    MODULE.R4_CAPTURE_PIN, MODULE.R4_CAPTURE_SHA256 = (
        "r4.json",
        _write(output / "r4.json", r4_capture),
    )
    r4_pool["capture"]["sha256"] = MODULE.R4_CAPTURE_SHA256
    MODULE.R4_POOL_PIN, MODULE.R4_POOL_SHA256 = (
        "pool.json",
        _write(output / "pool.json", r4_pool),
    )
    Probe.ROOT = root
    return Resolve(store), config, old


def _run(root, **kwargs):
    resolve, config, old = _setup(root, **kwargs)
    try:
        return MODULE.run(resolve, config, probe=Probe), resolve, config
    finally:
        (
            MODULE.MATRIX_PIN,
            MODULE.MATRIX_SHA256,
            MODULE.R4_CAPTURE_PIN,
            MODULE.R4_CAPTURE_SHA256,
            MODULE.R4_POOL_PIN,
            MODULE.R4_POOL_SHA256,
        ) = old


def demo():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        report, resolve, config = _run(root)
        store = resolve.store
        assert report["status"] == "repaired-unsaved"
        assert store.setter_calls == [MODULE.TARGET_TIMECODE]
        assert store.selection_calls == [MODULE.R4_UID]
        timeline = next(
            row
            for row in store.state["timelines"]
            if row["GetUniqueId"]["value"] == MODULE.R4_UID
        )
        assert timeline["GetStartFrame"]["value"] == 0
        assert 50 < timeline["GetEndFrame"]["value"] <= 200
        assert not any(
            method in {"AppendToTimeline", "ImportMedia", "SaveProject"}
            for method in store.setter_calls
        )
        journal = [
            json.loads(line)
            for line in Path(report["journal"]).read_text().splitlines()
        ]
        assert [
            (row["method"], row["phase"])
            for row in journal
            if row["method"] == "SetStartTimecode"
        ] == [("SetStartTimecode", "request"), ("SetStartTimecode", "return")]
        assert {row["phase"] for row in journal if row["method"] == "Capture"} >= {
            "matrix-preflight",
            "r4-preflight",
            "r4-postflight",
        }

        with tempfile.TemporaryDirectory() as temp:
            resolve, config, old = _setup(Path(temp), mode="end-199")
            try:
                report = MODULE.run(resolve, config, probe=Probe)
                assert report["status"] == "repaired-unsaved"
                assert (
                    resolve.store.state["timelines"][1]["GetEndFrame"]["value"] == 199
                )
            finally:
                (
                    MODULE.MATRIX_PIN,
                    MODULE.MATRIX_SHA256,
                    MODULE.R4_CAPTURE_PIN,
                    MODULE.R4_CAPTURE_SHA256,
                    MODULE.R4_POOL_PIN,
                    MODULE.R4_POOL_SHA256,
                ) = old

        for mode in ("false", "raise", "partial"):
            with tempfile.TemporaryDirectory() as temp:
                resolve, config, old = _setup(Path(temp), mode=mode)
                try:
                    try:
                        MODULE.run(resolve, config, probe=Probe)
                        raise AssertionError(f"{mode} setter was accepted")
                    except RuntimeError as error:
                        assert "failed" in str(error) or "evidence retained" in str(
                            error
                        )
                    assert resolve.store.setter_calls[0] == MODULE.TARGET_TIMECODE
                    if mode == "partial":
                        assert resolve.store.setter_calls == [
                            MODULE.TARGET_TIMECODE,
                            MODULE.ORIGINAL_TIMECODE,
                        ]
                        assert resolve.store.selected_uid == MODULE.MATRIX_UID
                    else:
                        assert resolve.store.setter_calls == [MODULE.TARGET_TIMECODE]
                        assert resolve.store.selected_uid == MODULE.MATRIX_UID
                finally:
                    (
                        MODULE.MATRIX_PIN,
                        MODULE.MATRIX_SHA256,
                        MODULE.R4_CAPTURE_PIN,
                        MODULE.R4_CAPTURE_SHA256,
                        MODULE.R4_POOL_PIN,
                        MODULE.R4_POOL_SHA256,
                    ) = old

        with tempfile.TemporaryDirectory() as temp:
            resolve, config, old = _setup(Path(temp), mode="incomplete")
            try:
                try:
                    MODULE.run(resolve, config, probe=Probe)
                    raise AssertionError("incomplete postflight was accepted")
                except RuntimeError as error:
                    assert "postflight is incomplete" in str(error)
                assert resolve.store.setter_calls == [MODULE.TARGET_TIMECODE]
                assert resolve.store.selected_uid == MODULE.R4_UID
                evidence = next(Path(config["outputDir"]).glob("r4-range-repair-*"))
                after = json.loads((evidence / "r4-postflight.json").read_text())
                assert after["timelineConsistency"] != "equal-adjacent-reads"
                assert (evidence / "report.json").is_file()
            finally:
                (
                    MODULE.MATRIX_PIN,
                    MODULE.MATRIX_SHA256,
                    MODULE.R4_CAPTURE_PIN,
                    MODULE.R4_CAPTURE_SHA256,
                    MODULE.R4_POOL_PIN,
                    MODULE.R4_POOL_SHA256,
                ) = old

        for drift in ("shifted", "failed-restore"):
            with tempfile.TemporaryDirectory() as temp:
                resolve, config, old = _setup(Path(temp), mode=drift)
                try:
                    try:
                        MODULE.run(resolve, config, probe=Probe)
                        raise AssertionError(f"{drift} postflight was accepted")
                    except RuntimeError:
                        pass
                    assert resolve.store.setter_calls[0] == MODULE.TARGET_TIMECODE
                    if drift == "shifted":
                        assert resolve.store.setter_calls == [MODULE.TARGET_TIMECODE]
                        assert resolve.store.selected_uid == MODULE.R4_UID
                    else:
                        assert resolve.store.setter_calls == [
                            MODULE.TARGET_TIMECODE,
                            MODULE.ORIGINAL_TIMECODE,
                        ]
                        assert resolve.store.selected_uid == MODULE.R4_UID
                finally:
                    (
                        MODULE.MATRIX_PIN,
                        MODULE.MATRIX_SHA256,
                        MODULE.R4_CAPTURE_PIN,
                        MODULE.R4_CAPTURE_SHA256,
                        MODULE.R4_POOL_PIN,
                        MODULE.R4_POOL_SHA256,
                    ) = old

        with tempfile.TemporaryDirectory() as temp:
            resolve, config, old = _setup(Path(temp), drift_after_set=True)
            try:
                try:
                    MODULE.run(resolve, config, probe=Probe)
                    raise AssertionError("unrelated timeline drift was accepted")
                except RuntimeError:
                    pass
                assert resolve.store.setter_calls == [MODULE.TARGET_TIMECODE]
                assert resolve.store.selected_uid == MODULE.R4_UID
            finally:
                (
                    MODULE.MATRIX_PIN,
                    MODULE.MATRIX_SHA256,
                    MODULE.R4_CAPTURE_PIN,
                    MODULE.R4_CAPTURE_SHA256,
                    MODULE.R4_POOL_PIN,
                    MODULE.R4_POOL_SHA256,
                ) = old

        for drift in ("matrix", "selection", "rendering", "source-symlink"):
            with tempfile.TemporaryDirectory() as temp:
                resolve, config, old = _setup(Path(temp))
                try:
                    if drift == "matrix":
                        resolve.store.state["timelines"][0]["GetSettings"]["value"][
                            "changed"
                        ] = True
                    elif drift == "selection":
                        resolve.store.selected_uid = MODULE.R4_UID
                    elif drift == "rendering":
                        resolve.store.rendering = True
                    else:
                        source = resolve.store.source
                        replacement = source.with_suffix(".replacement")
                        source.rename(replacement)
                        source.symlink_to(replacement)
                    try:
                        MODULE.run(resolve, config, probe=Probe)
                        raise AssertionError(f"{drift} preflight drift was accepted")
                    except (RuntimeError, OSError):
                        pass
                    assert resolve.store.setter_calls == []
                    assert resolve.store.selected_uid == (
                        MODULE.R4_UID if drift == "selection" else MODULE.MATRIX_UID
                    )
                    if drift == "matrix":
                        assert resolve.store.selection_calls == []
                finally:
                    (
                        MODULE.MATRIX_PIN,
                        MODULE.MATRIX_SHA256,
                        MODULE.R4_CAPTURE_PIN,
                        MODULE.R4_CAPTURE_SHA256,
                        MODULE.R4_POOL_PIN,
                        MODULE.R4_POOL_SHA256,
                    ) = old


if __name__ == "__main__":
    demo()
