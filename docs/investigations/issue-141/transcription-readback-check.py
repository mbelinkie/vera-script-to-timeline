"""Small fake success/refusal check for the transcription readback helper."""

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "transcription_readback", HERE / "transcription-readback.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Media:
    def __init__(self, uid, name, values):
        self.uid, self.name, self.values = uid, name, values
        self.calls = []

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name

    def GetClipProperty(self):
        return {"File Name": self.name, "File Path": self.values["path"]}

    def GetTranscription(self, nested=False):
        self.calls.append(nested)
        value = self.values["transcription"][nested]
        if isinstance(value, BaseException):
            raise value
        return value


class Item:
    def __init__(self, uid, media):
        self.uid, self.media = uid, media

    def GetUniqueId(self):
        return self.uid

    def GetTrackTypeAndIndex(self):
        return ["audio", 1]

    def GetMediaPoolItem(self):
        return self.media


class Timeline:
    def __init__(self, source, proxy):
        self.source, self.proxy = source, proxy
        self.occurrence = Item("occurrence", source)

    def GetUniqueId(self):
        return MODULE.MATRIX_UID

    def GetName(self):
        return MODULE.MATRIX_NAME

    def GetItemListInTrack(self, kind, index):
        assert (kind, index) == ("audio", 1)
        return [self.occurrence]

    def GetMediaPoolItem(self):
        return self.proxy


class Project:
    def __init__(self, timeline, source, proxy, jobs=None):
        self.timeline = timeline
        self.timelines = [
            timeline,
            SimpleNamespace(
                GetUniqueId=lambda: "64de8a4c-86bd-4f19-9d20-47b8940f610b",
                GetName=lambda: "VERA 141 R4 availability",
                GetMediaPoolItem=lambda: proxy,
            ),
            SimpleNamespace(
                GetUniqueId=lambda: "88f7923d-55a7-471f-b09b-cf10f9fae8ad",
                GetName=lambda: "VERA 141 Baseline",
                GetMediaPoolItem=lambda: proxy,
            ),
            SimpleNamespace(
                GetUniqueId=lambda: "aa2b8e36-83bd-4292-9e33-217c00ca192f",
                GetName=lambda: "VERA 141 R1 identity",
                GetMediaPoolItem=lambda: proxy,
            ),
        ]
        self.source, self.proxy = source, proxy
        self.jobs = [] if jobs is None else jobs

    def GetUniqueId(self):
        return MODULE.PROJECT_ID

    def GetName(self):
        return MODULE.PROJECT_NAME

    def GetCurrentTimeline(self):
        return self.timeline

    def GetTimelineCount(self):
        return len(self.timelines)

    def GetTimelineByIndex(self, index):
        return self.timelines[index - 1]

    def IsRenderingInProgress(self):
        return False

    def GetRenderJobList(self):
        return self.jobs


class Resolve:
    def __init__(self, project):
        self.project = project

    def GetProductName(self):
        return "DaVinci Resolve Studio"

    def GetVersion(self):
        return (21, 1, 0, 14, "")

    def GetProjectManager(self):
        return SimpleNamespace(GetCurrentProject=lambda: self.project)


class Probe:
    ROOT = None

    @staticmethod
    def sha256(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    @staticmethod
    def require_current(resolve, config, identity):
        project = resolve.project
        if project.GetUniqueId() != identity["projectId"]:
            raise RuntimeError("wrong project")
        if project.GetName() != config["projectName"]:
            raise RuntimeError("wrong project name")
        return project

    @staticmethod
    def observe(resolve, config, identity, expected):
        del config, identity, expected
        return resolve.state

    @staticmethod
    def _r4_pool_inventory(project, expected):
        source = project.source
        proxy = project.proxy
        return {
            "folders": [{"uid": "root", "name": "Master"}],
            "items": [
                {
                    "uid": MODULE.SOURCE_UID,
                    "name": {"value": MODULE.SOURCE_NAME},
                    "evidence": {
                        "GetUniqueId": {"value": MODULE.SOURCE_UID},
                        "GetClipProperty": {
                            "value": source.GetClipProperty()
                        },
                        "sourceBytes": {
                            "sha256": expected[source.values["path"]],
                            "hashMatches": True,
                        },
                    },
                },
                {
                    "uid": "proxy-uid",
                    "name": {"value": MODULE.MATRIX_NAME},
                    "evidence": {
                        "GetUniqueId": {"value": "proxy-uid"},
                        "GetClipProperty": {"value": proxy.GetClipProperty()},
                        "sourceBytes": {"status": "timeline-uid-not-hashed"},
                    },
                },
            ],
            "timelineMappings": [
                {
                    "timelineUid": {"value": MODULE.MATRIX_UID},
                    "poolItemUid": {"value": "proxy-uid"},
                }
            ],
        }

    @staticmethod
    def errors(value):
        found = []
        if isinstance(value, dict):
            if "error" in value:
                found.append(value["error"])
            for child in value.values():
                found.extend(Probe.errors(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(Probe.errors(child))
        return found


def _state(project_name, source, proxy):
    return {
        "projectId": MODULE.PROJECT_ID,
        "projectName": project_name,
        "GetSettings": {"value": {"timelineFrameRate": "25"}},
        "timelines": [
            {
                "GetUniqueId": {"value": MODULE.MATRIX_UID},
                "GetName": {"value": MODULE.MATRIX_NAME},
                "tracks": [],
            },
            {
                "GetUniqueId": {"value": "64de8a4c-86bd-4f19-9d20-47b8940f610b"},
                "GetName": {"value": "VERA 141 R4 availability"},
                "tracks": [],
            },
            {
                "GetUniqueId": {"value": "88f7923d-55a7-471f-b09b-cf10f9fae8ad"},
                "GetName": {"value": "VERA 141 Baseline"},
                "tracks": [],
            },
            {
                "GetUniqueId": {"value": "aa2b8e36-83bd-4292-9e33-217c00ca192f"},
                "GetName": {"value": "VERA 141 R1 identity"},
                "tracks": [],
            },
        ],
    }


def _setup(root, *, jobs=None):
    output = root / "out" / "issue-141-observation-fake"
    media_dir = root / "out" / "issue-141-media-fake"
    output.mkdir(parents=True)
    media_dir.mkdir()
    source_path = media_dir / MODULE.SOURCE_NAME
    source_path.write_bytes(b"synthetic repeated audio")
    manifest = {
        "kind": "generated-synthetic-inputs-not-Resolve-evidence",
        "files": [
            {
                "path": MODULE.SOURCE_NAME,
                "sha256": Probe.sha256(source_path),
                "sizeBytes": source_path.stat().st_size,
            }
        ],
    }
    manifest_path = media_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    values = {
        "path": str(source_path),
        "transcription": {
            False: {"language": "en", "segments": [{"text": "one"}]},
            True: {"language": "en", "segments": []},
        },
    }
    source = Media(MODULE.SOURCE_UID, MODULE.SOURCE_NAME, values)
    proxy = Media(
        "proxy-uid",
        MODULE.MATRIX_NAME,
        {
            "path": str(source_path),
            "transcription": {
                False: {"language": "en", "segments": [{"text": "proxy"}]},
                True: None,
            },
        },
    )
    timeline = Timeline(source, proxy)
    project = Project(timeline, source, proxy, jobs=jobs)
    project.manager = SimpleNamespace(GetCurrentProject=lambda: project)
    project.state = _state(MODULE.PROJECT_NAME, source, proxy)
    resolve = Resolve(project)
    resolve.state = project.state
    checkpoint_dir = output / "checkpoint"
    checkpoint_dir.mkdir()
    checkpoint = checkpoint_dir / "matrix.json"
    checkpoint.write_text(
        json.dumps(
            {
                "selectedTimelineUid": MODULE.MATRIX_UID,
                "timelineConsistency": "equal-adjacent-reads",
                "poolConsistency": "equal-adjacent-reads",
                "timelinePasses": [project.state, project.state],
                "poolPasses": [
                    Probe._r4_pool_inventory(
                        project, {str(source_path): Probe.sha256(source_path)}
                    ),
                    Probe._r4_pool_inventory(
                        project, {str(source_path): Probe.sha256(source_path)}
                    ),
                ],
            }
        ),
        encoding="utf-8",
    )
    old_pin, old_sha = MODULE.READER_FILE, MODULE.READER_SHA256
    old_reader = MODULE._load_reader
    class Reader:
        BUILD = (21, 1, 0, 14, "")
        PROJECT_ID = MODULE.PROJECT_ID
        MATRIX_UID = MODULE.MATRIX_UID
        MATRIX_NAME = MODULE.MATRIX_NAME
        R4_UID = "64de8a4c-86bd-4f19-9d20-47b8940f610b"
        R4_NAME = "VERA 141 R4 availability"
        MATRIX_PIN = "matrix.json"
        MATRIX_SHA256 = Probe.sha256(checkpoint)

        @staticmethod
        def _manifest(config, root, probe):
            del config, root, probe
            return media_dir, {str(source_path): Probe.sha256(source_path)}

        @staticmethod
        def _pin(path, name, digest, probe):
            assert (path.name, digest) == (name, Reader.MATRIX_SHA256)
            return json.loads(path.read_text(encoding="utf-8"))

        @staticmethod
        def _validate_read_pair(value, probe):
            del probe
            return value["timelinePasses"][0], value["poolPasses"][0]

        @staticmethod
        def _context(resolve, config, identity, probe, selected_uid):
            del identity, probe
            if resolve.project.GetCurrentTimeline().GetUniqueId() != selected_uid:
                raise RuntimeError("wrong selection")
            return resolve.project

        @staticmethod
        def _read_pair(resolve, config, identity, expected, selected_uid, probe):
            del config, identity, expected, selected_uid, probe
            pool = Probe._r4_pool_inventory(
                resolve.project, {str(source_path): Probe.sha256(source_path)}
            )
            return {
                "selectedTimelineUid": Reader.MATRIX_UID,
                "timelineConsistency": "equal-adjacent-reads",
                "poolConsistency": "equal-adjacent-reads",
                "timelinePasses": [resolve.state, resolve.state],
                "poolPasses": [pool, pool],
            }

    MODULE._load_reader = lambda: Reader
    Probe.ROOT = root
    config = {
        "action": MODULE.ACTION,
        "externalScriptingSetting": "None",
        "projectName": MODULE.PROJECT_NAME,
        "outputDir": str(output),
        "mediaDir": str(media_dir),
        "manifestSha256": Probe.sha256(manifest_path),
        "checkpointPath": str(checkpoint),
        "checkpointSha256": Reader.MATRIX_SHA256,
    }
    return resolve, config, source, proxy, old_pin, old_sha, old_reader


def demo():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        resolve, config, source, proxy, old_pin, old_sha, old_reader = _setup(root)
        try:
            report = MODULE.run(resolve, config, probe=Probe)
            assert report["status"] == "transcription-readback-retained"
            assert report["fullTimelinePoolStateUnchanged"] is True
            assert report["checkpoint"]["path"] == "checkpoint/matrix.json"
            assert source.calls == [False, False, True, True]
            assert proxy.calls == [False, False, True, True]
            results = report["transcriptions"]["results"]
            assert results["source"]["GetTranscription(True)"]["state"] == "empty"
            assert (
                results["matrixTimelinePoolProxy"]["GetTranscription(True)"][
                    "state"
                ]
                == "missing"
            )
        finally:
            MODULE.READER_FILE, MODULE.READER_SHA256 = old_pin, old_sha
            MODULE._load_reader = old_reader

    for label, mutate in (
        ("missing checkpoint", lambda config, root: config.update(
            checkpointPath=str(Path(config["outputDir"]) / "missing.json")
        )),
        ("escaped checkpoint", lambda config, root: config.update(
            checkpointPath=str(root / "outside.json")
        )),
        ("wrong checkpoint hash", lambda config, root: config.update(
            checkpointSha256="0" * 64
        )),
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            resolve, config, source, proxy, old_pin, old_sha, old_reader = _setup(root)
            if label == "escaped checkpoint":
                Path(config["checkpointPath"]).replace(root / "outside.json")
            mutate(config, root)
            try:
                try:
                    MODULE.run(resolve, config, probe=Probe)
                    raise AssertionError(f"{label} was accepted")
                except RuntimeError as error:
                    assert "checkpoint" in str(error).lower()
                assert source.calls == []
                assert proxy.calls == []
            finally:
                MODULE.READER_FILE, MODULE.READER_SHA256 = old_pin, old_sha
                MODULE._load_reader = old_reader

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        resolve, config, source, proxy, old_pin, old_sha, old_reader = _setup(
            root, jobs=[{"JobId": "foreign"}]
        )
        try:
            try:
                MODULE.run(resolve, config, probe=Probe)
                raise AssertionError("non-empty render queue was accepted")
            except RuntimeError as error:
                assert "queue" in str(error)
            assert source.calls == []
            assert proxy.calls == []
        finally:
            MODULE.READER_FILE, MODULE.READER_SHA256 = old_pin, old_sha
            MODULE._load_reader = old_reader


if __name__ == "__main__":
    demo()
