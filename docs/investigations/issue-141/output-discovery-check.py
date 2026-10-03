"""Stdlib fake acceptance for read-only Project render API discovery."""

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "output_discovery", HERE / "output-discovery.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Probe:
    PREFIX = "VERA Issue 141 Synthetic Probe "
    ROOT = None
    __file__ = str(HERE / "probe.py")

    @staticmethod
    def sha256(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

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

    @staticmethod
    def _pass_timeline(value, uid):
        matches = [
            row
            for row in value.get("timelines", [])
            if row["GetUniqueId"]["value"] == uid
        ]
        if len(matches) != 1:
            raise RuntimeError("timeline mismatch")
        return matches[0]

    @staticmethod
    def require_current(resolve, config, identity):
        project = resolve.manager.project
        if (
            project.uid != identity["projectId"]
            or project.name != config["projectName"]
        ):
            raise RuntimeError("wrong project")
        return project

    @staticmethod
    def observe(resolve, config, identity, expected):
        project = Probe.require_current(resolve, config, identity)
        if project.changed:
            return {**project.snapshot, "settingsChanged": True}
        # Native markers have numeric keys; persisted captures use JSON keys.
        value = json.loads(json.dumps(project.snapshot))
        value["timelines"][0]["GetMarkers"]["value"] = {
            0: {"customData": "issue-141 fake marker"}
        }
        value["timelines"][0]["GetTrackTypeAndIndex"]["value"] = ("video", 1)
        return value

    @staticmethod
    def source_evidence(locator, expected):
        path = Path(locator)
        return {"sha256": Probe.sha256(path)}


class Project:
    def __init__(
        self, snapshot, uid="97037b5a-aab6-48a9-b7e4-4c5697ae10a0", error_method=None
    ):
        self.snapshot, self.uid = snapshot, uid
        self.name = "VERA Issue 141 Synthetic Probe fake"
        self.current = Timeline()
        self.changed = False
        self.error_method = error_method
        self.calls = []

    def GetName(self):
        return self.name

    def GetUniqueId(self):
        return self.uid

    def GetCurrentTimeline(self):
        return self.current

    def _read(self, method, value):
        self.calls.append(method)
        if self.error_method == method:
            raise RuntimeError("injected getter failure")
        return value

    def GetRenderFormats(self):
        return self._read("GetRenderFormats", {"QuickTime": "mov"})

    def GetRenderCodecs(self, fmt):
        assert fmt == "mov"
        return self._read("GetRenderCodecs", {"Uncompressed": "raw"})

    def GetAudioRenderFormats(self):
        return self._read("GetAudioRenderFormats", {"Wave": "wav"})

    def GetAudioRenderCodecs(self, fmt):
        assert fmt == "wav"
        return self._read("GetAudioRenderCodecs", {"Linear PCM": "lpcm"})

    def GetCurrentRenderFormatAndCodec(self):
        return self._read(
            "GetCurrentRenderFormatAndCodec", {"format": "mov", "codec": "raw"}
        )

    def GetCurrentRenderMode(self):
        return self._read("GetCurrentRenderMode", 1)

    def GetRenderJobList(self):
        return self._read("GetRenderJobList", [])

    def IsRenderingInProgress(self):
        return self._read("IsRenderingInProgress", False)


class Timeline:
    def GetUniqueId(self):
        return "29ae8331-b86e-4041-a548-960695cc7b24"


class Manager:
    def __init__(self, project):
        self.project = project

    def GetCurrentProject(self):
        return self.project


class Resolve:
    def __init__(self, project):
        self.manager, self.project = Manager(project), project

    def GetProjectManager(self):
        return self.manager

    def GetProductName(self):
        return "DaVinci Resolve Studio"

    def GetVersion(self):
        return [21, 1, 0, 14, ""]


def fixture():
    snapshot = {
        "projectId": "97037b5a-aab6-48a9-b7e4-4c5697ae10a0",
        "projectName": "VERA Issue 141 Synthetic Probe fake",
        "GetSettings": {"value": {"timelineFrameRate": "25"}},
        "timelines": [
            {"GetUniqueId": {"value": uid}, "GetName": {"value": name}, "tracks": []}
            for uid, name in (
                ("29ae8331-b86e-4041-a548-960695cc7b24", "VERA 141 Batched Matrix"),
                ("88f7923d-55a7-471f-b09b-cf10f9fae8ad", "VERA 141 Baseline"),
                ("aa2b8e36-83bd-4292-9e33-217c00ca192f", "VERA 141 R1 identity"),
            )
        ],
    }
    snapshot["timelines"][0]["GetMarkers"] = {
        "value": {"0": {"customData": "issue-141 fake marker"}}
    }
    snapshot["timelines"][0]["GetTrackTypeAndIndex"] = {"value": ["video", 1]}
    return snapshot


def run_case(*, wrong_project=False, changed=False, error_method=None):
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "out").mkdir()
        output = root / "out" / "issue-141-observation-fake"
        output.mkdir()
        media = root / "out" / "issue-141-media-fake"
        media.mkdir()
        source = media / "base.mov"
        source.write_bytes(b"synthetic test only")
        manifest = {
            "kind": "generated-synthetic-inputs-not-Resolve-evidence",
            "installedDocs": {},
            "files": [{"path": "base.mov", "sha256": Probe.sha256(source)}],
        }
        (media / "manifest.json").write_text(json.dumps(manifest))
        snapshot = fixture()
        project = Project(
            snapshot,
            uid="wrong" if wrong_project else snapshot["projectId"],
            error_method=error_method,
        )
        project.changed = changed
        resolve = Resolve(project)
        pin = output / module.PIN_NAME
        pin_payload = {
            "consistency": "equal-adjacent-reads",
            "passes": [snapshot, snapshot],
        }
        pin.write_text(json.dumps(pin_payload))
        old_root, old_hash = Probe.ROOT, module.PIN_SHA256
        Probe.ROOT = root
        module.PIN_SHA256 = Probe.sha256(pin)
        config = {
            "projectName": project.name,
            "externalScriptingSetting": "None",
            "outputDir": str(output),
            "checkpointPath": str(pin),
            "mediaDir": str(media),
            "manifestSha256": Probe.sha256(media / "manifest.json"),
        }
        try:
            try:
                result = module.run(resolve, config, probe=Probe)
                return result, project, output
            except RuntimeError as error:
                return str(error), project, output
        finally:
            Probe.ROOT, module.PIN_SHA256 = old_root, old_hash


success, project, _ = run_case()
assert success["unchanged"] is True
assert project.calls == [
    "GetRenderFormats",
    "GetRenderCodecs",
    "GetAudioRenderFormats",
    "GetAudioRenderCodecs",
    "GetCurrentRenderFormatAndCodec",
    "GetCurrentRenderMode",
    "GetRenderJobList",
    "IsRenderingInProgress",
]
assert success["projectReads"]["GetRenderFormats"]["value"] == {"QuickTime": "mov"}

for kwargs in ({"wrong_project": True}, {"changed": True}):
    result, project, output = run_case(**kwargs)
    assert isinstance(result, str)
    assert project.calls == []

result, project, _ = run_case(error_method="GetRenderFormats")
assert result["unchanged"] is True
assert result["projectReads"]["GetRenderFormats"]["status"] == "error"
assert "injected getter failure" in result["projectReads"]["GetRenderFormats"]["error"]
print("R2 output discovery fake acceptance passed (no live Resolve evidence)")
