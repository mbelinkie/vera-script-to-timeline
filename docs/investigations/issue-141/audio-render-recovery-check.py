"""Stdlib fake checks for the one-shot render-preset import recovery."""

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("audio-render-recovery.py")
spec = importlib.util.spec_from_file_location("audio_render_recovery", SCRIPT)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class Timeline:
    def GetUniqueId(self):
        return recovery.MATRIX_ID


class Project:
    def __init__(self, mode="restore"):
        self.mode = mode
        self.format = {"format": "unknown", "codec": ""}
        self.mode_value = 1
        self.presets = ["Prior A", "Prior B", recovery.PRESET_NAME]
        self.calls = []

    def GetUniqueId(self):
        return recovery.PROJECT_ID

    def GetName(self):
        return "VERA recovery fake"

    def GetCurrentTimeline(self):
        return Timeline()

    def GetCurrentRenderFormatAndCodec(self):
        return self.format

    def GetCurrentRenderMode(self):
        return self.mode_value

    def GetRenderJobList(self):
        return []

    def IsRenderingInProgress(self):
        return False

    def GetRenderPresetList(self):
        return list(self.presets)

    def SetRenderSettings(self, settings):
        assert settings == {"ExportVideo": True}
        self.calls.append(("SetRenderSettings", settings))
        if self.mode == "throw":
            raise RuntimeError("injected toggle failure")
        if self.mode == "false":
            return False
        if self.mode == "restore":
            self.format = {"format": "mov", "codec": "H264"}
        return True

    def SetCurrentRenderFormatAndCodec(self, format, codec):
        assert (format, codec) == ("mov", "H264")
        self.calls.append(("SetCurrentRenderFormatAndCodec", (format, codec)))
        if self.mode == "throw":
            raise RuntimeError("injected selection failure")
        if self.mode == "false":
            return False
        if self.mode == "restore":
            self.format = {"format": format, "codec": codec}
        return True


class Manager:
    def __init__(self, project):
        self.project = project

    def GetCurrentProject(self):
        return self.project


class Resolve:
    def __init__(self, project, mode="restore"):
        self.project = project
        self.manager = Manager(project)
        self.mode = mode
        self.import_calls = []
        self.page = "deliver"

    def GetProjectManager(self):
        return self.manager

    def GetProductName(self):
        return "DaVinci Resolve Studio"

    def GetVersion(self):
        return recovery.BUILD

    def GetCurrentPage(self):
        return self.page

    def ImportRenderPreset(self, path):
        self.import_calls.append(path)
        self.project.calls.append(("ImportRenderPreset", path))
        if self.mode == "throw":
            raise RuntimeError("injected import failure")
        if self.mode == "false":
            return False
        if self.mode == "restore":
            self.project.format = {"format": "mov", "codec": "H264"}
        if self.mode == "extra-preset":
            self.project.format = {"format": "mov", "codec": "H264"}
            self.project.presets.append("Unexpected extra")
        return True


class Probe:
    PREFIX = "VERA"

    def __init__(self, root, project, timeline, pool):
        self.ROOT, self.project = root, project
        self.timeline, self.pool = timeline, pool
        self.drift = None

    def errors(self, value):
        found = []
        if isinstance(value, dict):
            if "error" in value or value.get("hashMatches") is False:
                found.append("bad evidence")
            for child in value.values():
                found.extend(self.errors(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(self.errors(child))
        return found

    def require_current(self, resolve, config, identity):
        if self.drift == "project":
            raise RuntimeError("injected project drift")
        p = resolve.manager.project
        if (
            p.GetUniqueId() != identity["projectId"]
            or p.GetName() != config["projectName"]
        ):
            raise RuntimeError("project mismatch")
        return p

    def observe(self, *args):
        if self.drift == "timeline":
            return {"changed": True}
        return self.timeline

    def _r4_pool_inventory(self, project, expected):
        if self.drift == "pool":
            return {"changed": True}
        return self.pool


def setup(mode="restore", damage=None):
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    out = root / "out"
    out.mkdir()
    output, media = out / "issue-141-observation-test", out / "issue-141-media-test"
    output.mkdir()
    media.mkdir()
    source = media / "base.mov"
    source.write_bytes(b"synthetic source")
    manifest = {
        "kind": "generated-synthetic-inputs-not-Resolve-evidence",
        "files": [
            {
                "path": "base.mov",
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "sizeBytes": source.stat().st_size,
            }
        ],
    }
    manifest_path = media / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    original = {
        "projectId": recovery.PROJECT_ID,
        "projectName": "VERA recovery fake",
        "state": "unchanged",
        "timelines": [
            {
                "GetUniqueId": {"value": recovery.MATRIX_ID},
                "GetName": {"value": "VERA 141 Batched Matrix"},
            }
        ],
    }
    pool = {
        "items": [
            {
                "sourceBytes": {
                    "status": "reachable",
                    "sha256": manifest["files"][0]["sha256"],
                    "hashMatches": True,
                }
            }
        ]
    }
    project = Project()
    probe = Probe(root, project, original, pool)
    checkpoint = output / recovery.PIN_NAME
    pin_value = {
        "selectedTimelineUid": recovery.MATRIX_ID,
        "timelineConsistency": "equal-adjacent-reads",
        "poolConsistency": "equal-adjacent-reads",
        "timelinePasses": [original, original],
        "poolPasses": [pool, pool],
    }
    checkpoint.write_text(json.dumps(pin_value))
    recovery.PIN_SHA = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    failed = output / recovery.FAILED_RUN
    failed.mkdir()
    export_run = output / recovery.EXPORT_RUN
    export_run.mkdir()
    prior_dir = export_run / f"{recovery.PRESET_NAME}.drp"
    prior_dir.mkdir()
    xml = prior_dir / f"{recovery.PRESET_NAME}.xml"
    xml.write_bytes(b"pinned XML")
    recovery.XML_SHA = hashlib.sha256(xml.read_bytes()).hexdigest()
    preflight = failed / "preflight.json"
    preflight.write_text(json.dumps({"passes": [original, original]}))
    recovery.PREFLIGHT_SHA = hashlib.sha256(preflight.read_bytes()).hexdigest()
    base_presets = ["Prior A", "Prior B"]
    retained_presets = [*base_presets, recovery.PRESET_NAME]
    export_journal = export_run / "journal.jsonl"
    export_events = [
        {"method": "GetRenderPresetList", "phase": "request", "value": []},
        {"method": "GetRenderPresetList", "phase": "return", "value": base_presets},
        {
            "method": "SaveAsNewRenderPreset",
            "phase": "request",
            "value": [recovery.PRESET_NAME],
        },
        {"method": "SaveAsNewRenderPreset", "phase": "return", "value": True},
        {"method": "GetRenderPresetList", "phase": "request", "value": []},
        {"method": "GetRenderPresetList", "phase": "return", "value": retained_presets},
        {
            "method": "ExportRenderPreset",
            "phase": "request",
            "value": [recovery.PRESET_NAME, str(prior_dir)],
        },
        {"method": "ExportRenderPreset", "phase": "return", "value": True},
    ]
    export_journal.write_text("".join(json.dumps(row) + "\n" for row in export_events))
    recovery.EXPORT_JOURNAL_SHA = hashlib.sha256(
        export_journal.read_bytes()
    ).hexdigest()
    rows = []
    sequence = [
        ("SyntheticManifest", "verified"),
        ("AudioOutput", "start"),
        ("Capture", "preflight"),
        ("GetCurrentRenderFormatAndCodec", "request"),
        ("GetCurrentRenderFormatAndCodec", "return"),
        ("GetCurrentRenderMode", "request"),
        ("GetCurrentRenderMode", "return"),
        ("GetRenderJobList", "request"),
        ("GetRenderJobList", "return"),
        ("IsRenderingInProgress", "request"),
        ("IsRenderingInProgress", "return"),
        ("GetRenderPresetList", "request"),
        ("GetRenderPresetList", "return"),
        ("PresetRecovery", "verified-existing"),
        ("RenderPresetRecovery", "verified"),
        ("SetRenderSettings", "request"),
        ("SetRenderSettings", "return"),
        ("GetCurrentRenderFormatAndCodec", "request"),
        ("GetCurrentRenderFormatAndCodec", "return"),
        ("GetCurrentRenderMode", "request"),
        ("GetCurrentRenderMode", "return"),
        ("GetRenderJobList", "request"),
        ("GetRenderJobList", "return"),
        ("IsRenderingInProgress", "request"),
        ("IsRenderingInProgress", "return"),
        ("GetRenderPresetList", "request"),
        ("GetRenderPresetList", "return"),
        ("IsRenderingInProgress", "request"),
        ("IsRenderingInProgress", "return"),
        ("GetRenderJobList", "request"),
        ("GetRenderJobList", "return"),
        ("LoadRenderPreset", "request"),
        ("LoadRenderPreset", "return"),
        ("GetCurrentRenderFormatAndCodec", "request"),
        ("GetCurrentRenderFormatAndCodec", "return"),
        ("GetCurrentRenderMode", "request"),
        ("GetCurrentRenderMode", "return"),
        ("GetRenderJobList", "request"),
        ("GetRenderJobList", "return"),
        ("IsRenderingInProgress", "request"),
        ("IsRenderingInProgress", "return"),
        ("GetRenderPresetList", "request"),
        ("GetRenderPresetList", "return"),
        ("AudioOutput", "prequeue-restoration-failure"),
        ("AudioOutput", "restoration-failure"),
    ]
    for method, phase in sequence:
        value = None
        if method == "SetRenderSettings" and phase == "return":
            value = True
        if method == "GetCurrentRenderFormatAndCodec" and phase == "return":
            value = {"format": "unknown", "codec": ""}
        if method == "GetCurrentRenderMode" and phase == "return":
            value = 1
        if method == "GetRenderJobList" and phase == "return":
            value = []
        if method == "IsRenderingInProgress" and phase == "return":
            value = False
        if method == "GetRenderPresetList" and phase == "return":
            value = retained_presets
        if method == "LoadRenderPreset" and phase == "request":
            value = [recovery.PRESET_NAME]
        if method == "LoadRenderPreset" and phase == "return":
            value = True
        if method == "PresetRecovery" and phase == "verified-existing":
            value = {"name": recovery.PRESET_NAME}
        if method == "RenderPresetRecovery" and phase == "verified":
            value = {"name": recovery.PRESET_NAME, "sha256": recovery.XML_SHA}
        if method == "AudioOutput":
            value = "RuntimeError"
        rows.append({"method": method, "phase": phase, "value": value})
    journal = failed / "journal.jsonl"
    journal.write_text("".join(json.dumps(row) + "\n" for row in rows))
    recovery.JOURNAL_SHA = hashlib.sha256(journal.read_bytes()).hexdigest()
    plugin = root / "plugin"
    plugin.mkdir()
    result = plugin / recovery.RESULT_NAME
    result.write_text(
        json.dumps({"status": "launcher-failed", "detail": "Post-settings refusal"})
    )
    recovery.RESULT_SHA = hashlib.sha256(result.read_bytes()).hexdigest()
    recovery.PLUGIN_ROOT = plugin
    recovery.FAILED_RUN = failed.name
    refusal_dir = output / recovery.REFUSAL_RUN
    refusal_dir.mkdir()
    refusal_journal = refusal_dir / "journal.jsonl"
    refusal = "RuntimeError: Exact selected Matrix/Edit context required"
    refusal_rows = [
        {
            "method": "Capture",
            "phase": "preflight",
            "value": {
                "timelinePasses": [{"error": refusal}],
                "poolPasses": [{"error": refusal}],
            },
        },
        {"method": "Recovery", "phase": "refusal", "value": refusal},
        {
            "method": "Recovery",
            "phase": "complete",
            "value": {"status": "preflight-refused-no-import", "importCalled": False},
        },
    ]
    refusal_journal.write_text("".join(json.dumps(row) + "\n" for row in refusal_rows))
    recovery.REFUSAL_JOURNAL_SHA = hashlib.sha256(
        refusal_journal.read_bytes()
    ).hexdigest()
    refusal_result = plugin / recovery.REFUSAL_RESULT_NAME
    refusal_result.write_text(
        json.dumps(
            {
                "failure": refusal,
                "importCalled": False,
                "status": "preflight-refused-no-import",
            }
        )
    )
    recovery.REFUSAL_RESULT_SHA = hashlib.sha256(
        refusal_result.read_bytes()
    ).hexdigest()
    diagnostic = {
        "stage": "after-audio-recovery-context-refusal",
        "consistency": "equal-adjacent-reads",
        "captureFailure": None,
        "getterFailures": [],
        "passes": [original, original],
        "environment": {
            "context": {
                "currentPage": {"value": "deliver"},
                "selectedTimelineUid": {"value": recovery.MATRIX_ID},
                "renderState": {
                    "GetCurrentRenderFormatAndCodec": {
                        "value": {"format": "unknown", "codec": ""}
                    },
                    "GetCurrentRenderMode": {"value": 1},
                    "GetRenderJobList": {"value": []},
                    "IsRenderingInProgress": {"value": False},
                    "GetRenderPresetList": {"value": retained_presets},
                },
            }
        },
    }
    diagnostic_path = output / recovery.DIAGNOSTIC_NAME
    diagnostic_path.write_text(json.dumps(diagnostic))
    recovery.DIAGNOSTIC_SHA = hashlib.sha256(diagnostic_path.read_bytes()).hexdigest()
    config = {
        "action": "audio-render-recovery",
        "externalScriptingSetting": "None",
        "projectName": "VERA recovery fake",
        "outputDir": str(output),
        "mediaDir": str(media),
        "manifestSha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "checkpointPath": str(checkpoint),
    }
    project.presets = retained_presets
    resolve = Resolve(project, mode)
    if damage == "pool":
        probe.drift = "pool"
    if damage == "context":
        probe.drift = "project"
    if damage == "content":
        probe.drift = "timeline"
    if damage == "format":
        project.format = {"format": "mov", "codec": "H264"}
    if damage == "preset":
        project.presets = ["Prior A", recovery.PRESET_NAME]
    if damage == "source-bytes":
        source.write_bytes(b"changed source")
    if damage == "edit-page":
        resolve.page = "edit"
    if damage == "diagnostic":
        diagnostic_path.write_text("{}")
    if damage == "refusal":
        refusal_result.write_text("{}")
    return temp, resolve, config, probe, project, xml


def run_check(mode, expected_status):
    temp, resolve, config, probe, project, xml = setup(mode)
    try:
        result = recovery.run(resolve, config, probe=probe)
        assert result["status"] == expected_status
        assert len(resolve.import_calls) == 1
        assert resolve.import_calls[0] == str(xml)
        assert hashlib.sha256(xml.read_bytes()).hexdigest() == recovery.XML_SHA
        if mode == "extra-preset":
            assert "Unexpected extra" in project.presets
    finally:
        temp.cleanup()


def guard_refusals():
    for damage in (
        "context",
        "pool",
        "content",
        "format",
        "preset",
        "source-bytes",
        "edit-page",
        "diagnostic",
        "refusal",
    ):
        temp, resolve, config, probe, project, _ = setup(damage=damage)
        try:
            try:
                result = recovery.run(resolve, config, probe=probe)
            except RuntimeError:
                assert damage in {"source-bytes", "diagnostic", "refusal"}
                result = None
            if result is not None:
                assert result["status"] == "preflight-refused-no-import", damage
            assert resolve.import_calls == [] and project.calls == [], damage
        finally:
            temp.cleanup()


def toggle_checks(select_format=False):
    for mode in ("restore", "false", "throw", "unknown", "pool", "bad-pin"):
        temp, resolve, config, probe, project, xml = setup()
        try:
            config["action"] = "audio-video-toggle-recovery"
            project.mode = mode
            prior = Path(config["outputDir"]) / recovery.IMPORT_RUN
            prior.mkdir()
            result_path = recovery.PLUGIN_ROOT / recovery.IMPORT_RESULT_NAME
            result_path.write_text(
                json.dumps(
                    {
                        "status": "import-unresolved-or-refused",
                        "importCalled": True,
                        "importReturn": False,
                        "importError": None,
                        "timelineAndPoolUnchanged": True,
                        "xmlSha256After": recovery.XML_SHA,
                    }
                )
            )
            (prior / "journal.jsonl").write_text(
                json.dumps(
                    {"method": "ImportRenderPreset", "phase": "return", "value": False}
                )
            )
            (prior / "postflight.json").write_text(
                json.dumps(
                    {
                        "timelinePasses": [probe.timeline, probe.timeline],
                        "poolPasses": [probe.pool, probe.pool],
                    }
                )
            )
            recovery.IMPORT_RESULT_SHA = hashlib.sha256(
                result_path.read_bytes()
            ).hexdigest()
            recovery.IMPORT_JOURNAL_SHA = hashlib.sha256(
                (prior / "journal.jsonl").read_bytes()
            ).hexdigest()
            recovery.IMPORT_POSTFLIGHT_SHA = hashlib.sha256(
                (prior / "postflight.json").read_bytes()
            ).hexdigest()
            if select_format:
                config["action"] = "audio-format-selection-recovery"
                prior_toggle = Path(config["outputDir"]) / recovery.TOGGLE_RUN
                prior_toggle.mkdir()
                toggle_result = recovery.PLUGIN_ROOT / recovery.TOGGLE_RESULT_NAME
                toggle_result.write_text(
                    json.dumps(
                        {
                            "status": "video-toggle-unresolved-or-refused",
                            "setterCalled": True,
                            "setterReturn": True,
                            "setterError": None,
                            "importCalled": False,
                            "timelineAndPoolUnchanged": True,
                        }
                    )
                )
                (prior_toggle / "journal.jsonl").write_text("pinned native toggle")
                (prior_toggle / "postflight.json").write_bytes(
                    (prior / "postflight.json").read_bytes()
                )
                recovery.TOGGLE_RESULT_SHA = hashlib.sha256(
                    toggle_result.read_bytes()
                ).hexdigest()
                recovery.TOGGLE_JOURNAL_SHA = hashlib.sha256(
                    (prior_toggle / "journal.jsonl").read_bytes()
                ).hexdigest()
            if mode == "pool":
                probe.drift = "pool"
            if mode == "bad-pin":
                result_path.write_text("changed")
                try:
                    recovery.run(resolve, config, probe=probe)
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("tampered refused-import pin accepted")
                assert project.calls == [] and resolve.import_calls == []
                continue
            result = recovery.run(resolve, config, probe=probe)
            expected = (
                (
                    "format-selected-content-unchanged"
                    if select_format
                    else "video-enabled-known-format-content-unchanged"
                )
                if mode == "restore"
                else "preflight-refused-no-import"
                if mode == "pool"
                else (
                    "format-selection-unresolved-or-refused"
                    if select_format
                    else "video-toggle-unresolved-or-refused"
                )
            )
            assert result["status"] == expected, (mode, result)
            assert resolve.import_calls == [] and result["importCalled"] is False
            assert len(project.calls) == (0 if mode == "pool" else 1)
            assert hashlib.sha256(xml.read_bytes()).hexdigest() == recovery.XML_SHA
        finally:
            temp.cleanup()


if __name__ == "__main__":
    run_check("restore", "import-restored-known-format-content-unchanged")
    run_check("false", "import-unresolved-or-refused")
    run_check("throw", "import-unresolved-or-refused")
    run_check("extra-preset", "import-unresolved-or-refused")
    guard_refusals()
    toggle_checks()
    toggle_checks(select_format=True)
    print("Audio render recovery fake checks passed")
