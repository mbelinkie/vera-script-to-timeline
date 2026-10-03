"""Focused stdlib checks for the guarded audio-output experiment."""

import hashlib
import importlib.util
import json
import shutil
import tempfile
import wave
from pathlib import Path

SCRIPT = Path(__file__).with_name("audio-output.py")
spec = importlib.util.spec_from_file_location("audio_output", SCRIPT)
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


class Timeline:
    def GetUniqueId(self):
        return audio.MATRIX_ID


class Project:
    def __init__(self, mode="complete"):
        self.mode = mode
        self.settings = {"prior": True}
        self.format = {"format": "mov", "codec": "H264"}
        self.render_mode = 1
        self.jobs = []
        self.presets = ["Existing"]
        self.active = False
        self.job_status = "Queued"
        self.fail_load = False
        self.mutations = 0
        self.mode_reads = 0
        self.settings_calls = 0
        self.save_calls = 0

    def GetCurrentTimeline(self):
        return Timeline()

    def GetCurrentRenderFormatAndCodec(self):
        return self.format

    def GetCurrentRenderMode(self):
        self.mode_reads += 1
        if (
            self.mode == "configured-readback-raise"
            and self.settings.get("ExportVideo") is False
            and self.mode_reads == 2
        ):
            raise RuntimeError("injected configured readback failure")
        return self.render_mode

    def GetRenderJobList(self):
        return [dict(x) for x in self.jobs]

    def IsRenderingInProgress(self):
        return self.active

    def GetRenderPresetList(self):
        return list(self.presets)

    def SaveAsNewRenderPreset(self, name):
        self.mutations += 1
        self.save_calls += 1
        self.presets.append(name)
        return True

    def SetRenderSettings(self, settings):
        self.mutations += 1
        self.settings_calls += 1
        self.settings = dict(settings)
        if self.mode == "settings-false":
            return False
        if self.mode == "settings-raise":
            raise RuntimeError("partial settings failure")
        return True

    def LoadRenderPreset(self, name):
        if self.fail_load:
            raise RuntimeError("restore refused")
        self.settings = {"prior": True}
        return True

    def DeleteRenderPreset(self, name):
        self.presets.remove(name)
        return True

    def AddRenderJob(self):
        job = {
            "JobId": "job-1",
            "PresetName": self.presets[-1],
            "TargetDir": self.settings["TargetDir"],
            "OutputFilename": self.settings["CustomName"] + ".wav",
            "IsExportVideo": False,
            "IsExportAudio": True,
            "AudioSampleRate": 48000,
            "AudioBitDepth": 16,
            "AudioCodec": "lpcm",
        }
        job["PresetName"] = "Custom"
        if self.mode == "bad-job":
            job["TargetDir"] = "/outside"
        self.jobs.append(job)
        return "job-1"

    def StartRendering(self, ids):
        assert ids == ["job-1"]
        self.active = True
        if self.mode == "start-false":
            self.active = False
            return False
        if self.mode == "start-raise":
            self.active = False
            raise RuntimeError("injected StartRendering failure")
        if self.mode == "terminal-failure":
            self.active = False
            self.job_status = "Failed"
        elif self.mode in {"complete", "native-complete"}:
            path = Path(self.jobs[0]["TargetDir"]) / self.jobs[0]["OutputFilename"]
            with wave.open(str(path), "wb") as out:
                out.setnchannels(2)
                out.setsampwidth(2)
                out.setframerate(48000)
                out.writeframes(b"\0" * 400)
            self.active = False
            self.job_status = (
                "Render Complete" if self.mode == "native-complete" else "Complete"
            )
        return True

    def GetRenderJobStatus(self, job_id):
        return {"JobStatus": self.job_status}

    def DeleteRenderJob(self, job_id):
        self.jobs.clear()
        return True


class Resolve:
    def __init__(self, project):
        self.project = project
        self.export_calls = []

    def ExportRenderPreset(self, name, path):
        assert name in self.project.presets
        self.export_calls.append((name, path))
        destination = Path(path)
        destination.mkdir()
        (destination / f"{name}.xml").write_bytes(b"snapshot")
        return True

    def GetProductName(self):
        return "DaVinci Resolve Studio"

    def GetVersion(self):
        return audio.BUILD

    def GetProjectManager(self):
        return None


class Probe:
    PREFIX = "VERA"

    def __init__(self, root, project):
        self.ROOT = root
        self.project = project
        self.observations = 0

    def require_current(self, resolve, config, identity):
        return self.project

    def observe(self, resolve, config, identity, expected):
        self.observations += 1
        if (
            self.project.mode == "configured-capture-failure"
            and 4 <= self.observations <= 5
        ):
            raise RuntimeError("injected configured capture failure")
        return {
            "projectId": audio.PROJECT_ID,
            "projectName": config["projectName"],
            "timelines": [
                {
                    "GetUniqueId": {"value": audio.MATRIX_ID},
                    "GetName": {"value": "VERA 141 Batched Matrix"},
                }
            ],
        }

    def errors(self, values):
        return [x for x in values if isinstance(x, dict) and "error" in x]


def setup(mode="complete"):
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    out = root / "out"
    out.mkdir()
    output = out / "issue-141-observation-test"
    output.mkdir()
    media = out / "issue-141-media-test"
    media.mkdir()
    manifest = {"kind": "generated-synthetic-inputs-not-Resolve-evidence", "files": []}
    manifest_path = media / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    checkpoint = output / "pin.json"
    project = Project(mode)
    probe = Probe(root, project)
    row = probe.observe(None, {"projectName": "VERA test"}, {}, {})
    checkpoint.write_text(
        json.dumps(
            {
                "selectedTimelineUid": audio.MATRIX_ID,
                "timelineConsistency": "equal-adjacent-reads",
                "poolConsistency": "equal-adjacent-reads",
                "timelinePasses": [row, row],
                "poolPasses": [{"fake": "pool"}, {"fake": "pool"}],
            }
        )
    )
    audio.PIN_NAME = "pin.json"
    audio.PIN_SHA256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    config = {
        "action": "audio-output",
        "externalScriptingSetting": "None",
        "projectName": "VERA test",
        "outputDir": str(output),
        "mediaDir": str(media),
        "checkpointPath": str(checkpoint),
        "manifestSha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "renderTimeoutSeconds": 0.01,
    }
    return temp, config, probe, Resolve(project), project


def setup_continuation(mode="complete"):
    temp, config, probe, resolve, project = setup(mode)
    prior = Path(config["outputDir"]) / audio.CONTINUATION_DIR
    prior.mkdir()
    name = audio.CONTINUATION_NAME
    snapshot = prior / f"{name}.drp"
    snapshot.mkdir()
    xml = snapshot / f"{name}.xml"
    xml.write_bytes(b"snapshot")
    audio.CONTINUATION_XML_SHA = hashlib.sha256(xml.read_bytes()).hexdigest()
    preflight = prior / "preflight.json"
    pinned = json.loads(Path(config["checkpointPath"]).read_text())["timelinePasses"][0]
    preflight.write_text(json.dumps({"passes": [pinned, pinned]}))
    audio.CONTINUATION_PREFLIGHT_SHA = hashlib.sha256(
        preflight.read_bytes()
    ).hexdigest()
    events = [
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
        ("SaveAsNewRenderPreset", "request"),
        ("SaveAsNewRenderPreset", "return"),
        ("GetRenderPresetList", "request"),
        ("GetRenderPresetList", "return"),
        ("ExportRenderPreset", "request"),
        ("ExportRenderPreset", "return"),
    ]
    prior_presets = list(project.presets)
    project.presets.append(name)
    rows = []
    for method, phase in events:
        value = None
        if method == "GetRenderPresetList" and phase == "return":
            value = (
                prior_presets
                if len(
                    [r for r in rows if r["method"] == method and r["phase"] == phase]
                )
                == 0
                else [*prior_presets, name]
            )
        elif method == "ExportRenderPreset" and phase == "request":
            value = [name, str(snapshot)]
        elif method == "ExportRenderPreset" and phase == "return":
            value = True
        elif method == "SaveAsNewRenderPreset" and phase == "request":
            value = [name]
        elif method == "SaveAsNewRenderPreset" and phase == "return":
            value = True
        rows.append({"method": method, "phase": phase, "value": value})
    journal = prior / "journal.jsonl"
    journal.write_text("".join(json.dumps(row) + "\n" for row in rows))
    audio.CONTINUATION_JOURNAL_SHA = hashlib.sha256(journal.read_bytes()).hexdigest()
    comparison = prior.parent / "audio-export-refusal-independent-comparison.json"
    plugin_root = Path(config["outputDir"]).parent / "plugin"
    plugin_root.mkdir()
    result = plugin_root / audio.CONTINUATION_RESULT_NAME
    result.write_text(json.dumps({"status": "launcher-failed"}))
    audio.PLUGIN_ROOT = plugin_root
    audio.CONTINUATION_RESULT_SHA = hashlib.sha256(result.read_bytes()).hexdigest()
    comparison.write_text(
        json.dumps(
            {
                "files": {
                    "journal.jsonl": audio.CONTINUATION_JOURNAL_SHA,
                    "preflight.json": audio.CONTINUATION_PREFLIGHT_SHA,
                    f"{name}.xml": audio.CONTINUATION_XML_SHA,
                    audio.CONTINUATION_RESULT_NAME: audio.CONTINUATION_RESULT_SHA,
                },
                "setSettingsQueuedOrRendered": False,
                "fullPreflightEqualsSelectedMatrixPin": True,
            }
        )
    )
    audio.CONTINUATION_COMPARISON_SHA = hashlib.sha256(
        comparison.read_bytes()
    ).hexdigest()
    config["action"] = "audio-output-continue"
    return temp, config, probe, resolve, project, journal, preflight, xml


def check(name, fn):
    fn()
    print("PASS", name)


def invalid_timeout_before_mutation():
    t, c, p, r, project = setup()
    try:
        c["renderTimeoutSeconds"] = 0
        try:
            audio.run(r, c, probe=p)
        except RuntimeError as error:
            assert "timeout" in str(error).lower()
        else:
            raise AssertionError("invalid timeout accepted")
        assert project.mutations == 0 and project.jobs == []
    finally:
        t.cleanup()


def post_settings_readback_failure_restores():
    t, c, p, r, project = setup("configured-readback-raise")
    try:
        try:
            audio.run(r, c, probe=p)
        except RuntimeError as error:
            assert "verification failed" in str(error).lower()
        else:
            raise AssertionError("readback failure accepted")
        assert project.settings == {"prior": True} and project.jobs == []
        assert project.presets == ["Existing"]
    finally:
        t.cleanup()


def post_settings_capture_failure_restores():
    t, c, p, r, project = setup("configured-capture-failure")
    try:
        try:
            audio.run(r, c, probe=p)
        except RuntimeError as error:
            assert "verification failed" in str(error).lower()
        else:
            raise AssertionError("configured capture failure accepted")
        assert project.settings == {"prior": True} and project.jobs == []
        assert project.presets == ["Existing"]
    finally:
        t.cleanup()


def success():
    t, c, p, r, project = setup()
    try:
        result = audio.run(r, c, probe=p)
        assert result["status"] == "render-complete-restored"
        assert project.jobs == [] and project.presets == ["Existing"]
    finally:
        t.cleanup()


def native_render_complete():
    t, c, p, r, project = setup("native-complete")
    try:
        result = audio.run(r, c, probe=p)
        assert result["status"] == "render-complete-restored"
        assert result["jobStatus"]["JobStatus"] == "Render Complete"
        assert project.jobs == [] and project.presets == ["Existing"]
    finally:
        t.cleanup()


def checkpoint_refusal():
    t, c, p, r, _ = setup()
    try:
        audio.PIN_SHA256 = "0" * 64
        try:
            audio.run(r, c, probe=p)
        except RuntimeError as error:
            assert "checkpoint" in str(error).lower()
        else:
            raise AssertionError("checkpoint mismatch accepted")
    finally:
        t.cleanup()


def selected_checkpoint_refusal():
    for damage in ("selection", "pool"):
        t, c, p, r, project = setup()
        try:
            path = Path(c["checkpointPath"])
            pin = json.loads(path.read_text())
            if damage == "selection":
                pin["selectedTimelineUid"] = "other"
            else:
                pin["poolPasses"][1] = {"fake": "drift"}
            path.write_text(json.dumps(pin))
            audio.PIN_SHA256 = hashlib.sha256(path.read_bytes()).hexdigest()
            try:
                audio.run(r, c, probe=p)
            except RuntimeError:
                pass
            else:
                raise AssertionError("invalid selected-Matrix pin accepted")
            assert project.mutations == 0
        finally:
            t.cleanup()


def path_refusal():
    t, c, p, r, _ = setup()
    try:
        c["outputDir"] = str(Path(c["outputDir"]).parent / "other")
        try:
            audio.run(r, c, probe=p)
        except RuntimeError:
            pass
        else:
            raise AssertionError("unowned output accepted")
    finally:
        t.cleanup()


def queue_refusal():
    t, c, p, r, project = setup()
    project.jobs.append({"JobId": "preexisting"})
    try:
        try:
            audio.run(r, c, probe=p)
        except RuntimeError:
            pass
        else:
            raise AssertionError("non-empty queue accepted")
    finally:
        t.cleanup()


def settings_refusal():
    t, c, p, r, project = setup("settings-raise")
    try:
        result = audio.run(r, c, probe=p)
        assert result["status"] == "settings-refused-restored"
        assert project.settings == {"prior": True} and project.presets == ["Existing"]
    finally:
        t.cleanup()


def malformed_job_refusal():
    t, c, p, r, project = setup("bad-job")
    try:
        result = audio.run(r, c, probe=p)
        assert result["status"] == "queued-job-refused-settings-restored"
        assert project.jobs and project.active is False
        assert project.presets[-1].startswith("VERA141_AUDIO_OUTPUT_")
    finally:
        t.cleanup()


def start_refusal(mode):
    t, c, p, r, project = setup(mode)
    try:
        result = audio.run(r, c, probe=p)
        assert result["status"] == "queued-job-refused-settings-restored"
        assert project.settings == {"prior": True}
        assert len(project.jobs) == 1 and len(project.presets) == 2
        assert project.active is False
    finally:
        t.cleanup()


def terminal_failure():
    t, c, p, r, project = setup("terminal-failure")
    try:
        result = audio.run(r, c, probe=p)
        assert result["status"] == "render-failed-restored"
        assert project.jobs == [] and project.presets == ["Existing"]
    finally:
        t.cleanup()


def timeout_pending():
    t, c, p, r, project = setup("pending")
    try:
        project.StartRendering = lambda ids: setattr(project, "active", True) or True
        result = audio.run(r, c, probe=p)
        assert result["status"] == "pending-active-render"
        assert project.active and project.jobs and len(project.presets) == 2
        recovery = Path(result["recoveryPreset"])
        assert recovery.is_file() and recovery.suffix == ".xml"
        assert (
            hashlib.sha256(recovery.read_bytes()).hexdigest()
            == result["recoverySha256"]
        )
    finally:
        t.cleanup()


def restoration_failure():
    t, c, p, r, project = setup("terminal-failure")
    project.fail_load = True
    try:
        try:
            audio.run(r, c, probe=p)
        except RuntimeError as error:
            assert "restoration" in str(error).lower()
        else:
            raise AssertionError("restore failure was hidden")
        assert project.jobs and project.presets[-1].startswith("VERA141_AUDIO_OUTPUT_")
    finally:
        t.cleanup()


def continuation_success_and_cleanup():
    t, c, p, r, project, journal, preflight, xml = setup_continuation()
    try:
        result = audio.run(r, c, probe=p)
        assert result["status"] == "render-complete-restored"
        assert project.jobs == [] and project.presets == ["Existing"]
        assert project.save_calls == 0 and r.export_calls == []
        assert project.settings_calls == 1
        assert (
            hashlib.sha256(journal.read_bytes()).hexdigest()
            == audio.CONTINUATION_JOURNAL_SHA
        )
        assert (
            hashlib.sha256(preflight.read_bytes()).hexdigest()
            == audio.CONTINUATION_PREFLIGHT_SHA
        )
        assert (
            hashlib.sha256(xml.read_bytes()).hexdigest() == audio.CONTINUATION_XML_SHA
        )
    finally:
        t.cleanup()


def continuation_refusals_before_settings():
    for damage in (
        "journal",
        "preflight",
        "xml",
        "wrong-xml-name",
        "xml-symlink",
        "snapshot-symlink",
        "preset-list",
        "context",
        "content",
    ):
        t, c, p, r, project, journal, preflight, xml = setup_continuation()
        try:
            if damage == "journal":
                journal.write_text(journal.read_text() + "{}\n")
            elif damage == "preflight":
                preflight.write_text("{}")
            elif damage == "xml":
                xml.write_bytes(b"changed")
            elif damage == "wrong-xml-name":
                xml.rename(xml.with_name("wrong.xml"))
            elif damage == "xml-symlink":
                replacement = xml.with_name("replacement.xml")
                replacement.write_bytes(xml.read_bytes())
                xml.unlink()
                xml.symlink_to(replacement.name)
            elif damage == "snapshot-symlink":
                snapshot = xml.parent
                replacement = snapshot.with_name("replacement.drp")
                replacement.mkdir()
                (replacement / xml.name).write_bytes(xml.read_bytes())
                shutil.rmtree(snapshot)
                snapshot.symlink_to(replacement, target_is_directory=True)
            elif damage == "preset-list":
                project.presets.remove(audio.CONTINUATION_NAME)
            elif damage == "context":
                p.require_current = lambda *_: (_ for _ in ()).throw(
                    RuntimeError("injected context drift")
                )
            else:
                p.observe = lambda *_: {"changed": True}
            try:
                audio.run(r, c, probe=p)
            except RuntimeError:
                pass
            else:
                raise AssertionError(f"damaged continuation {damage} accepted")
            assert project.settings_calls == 0 and project.save_calls == 0
            assert r.export_calls == []
        finally:
            t.cleanup()


if __name__ == "__main__":
    check("invalid timeout before mutation", invalid_timeout_before_mutation)
    check(
        "post-settings readback failure restoration",
        post_settings_readback_failure_restores,
    )
    check(
        "post-settings capture failure restoration",
        post_settings_capture_failure_restores,
    )
    check("success and cleanup", success)
    check("documented Render Complete status", native_render_complete)
    check("checkpoint refusal", checkpoint_refusal)
    check(
        "selected checkpoint and pool inconsistency refusal",
        selected_checkpoint_refusal,
    )
    check("path refusal", path_refusal)
    check("preexisting queue refusal", queue_refusal)
    check("partial settings failure restoration", settings_refusal)
    check("malformed queued job retained", malformed_job_refusal)
    check(
        "StartRendering false retains job and restores settings",
        lambda: start_refusal("start-false"),
    )
    check(
        "StartRendering exception retains job and restores settings",
        lambda: start_refusal("start-raise"),
    )
    check("terminal failure restoration", terminal_failure)
    check("active timeout preserves recovery", timeout_pending)
    check("restoration failure retains recovery", restoration_failure)
    check(
        "pinned continuation renders and cleans up without re-export",
        continuation_success_and_cleanup,
    )
    check(
        "continuation pin/context refusals precede settings",
        continuation_refusals_before_settings,
    )
