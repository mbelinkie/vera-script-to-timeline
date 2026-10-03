"""Offline guards for the Issue 149 Workflow Integration discriminator kit.

This module deliberately exercises only stdlib code and small fake native
shapes.  It does not launch Resolve, call Hammerspoon, install a plugin, or
touch a media file outside a temporary directory.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load("issue149_discriminator_harness", HERE / "harness.py")
launcher = _load("issue149_discriminator_launcher", HERE / "launcher.py")
console = _load("issue149_discriminator_console", HERE / "console-render.py")


class Journal:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def api_request(self, method, args):
        self.calls.append(("request", method))

    def write(self, method, phase, value):
        self.calls.append((phase, method))


class KnownDisposable:
    def __init__(self, statuses=None, rendering=False):
        self.statuses = statuses or {
            "old-terminal": {"JobStatus": "Complete"},
            "old-failed": {"JobStatus": "Failed"},
        }
        self.rendering = rendering

    def GetName(self):
        return "VERA 149 Discriminators 20261002-b"

    def GetUniqueId(self):
        return "known-disposable-149"

    def GetRenderJobList(self):
        return [
            {"JobId": job_id, "RenderJobName": f"Job {index}", "Settings": {}}
            for index, job_id in enumerate(self.statuses, start=1)
        ]

    def GetRenderJobStatus(self, job_id):
        return dict(self.statuses[job_id])

    def IsRenderingInProgress(self):
        return self.rendering


class Manager:
    def __init__(self, project):
        self.project = project

    def GetCurrentProject(self):
        return self.project


def _config(root: Path, action: str = "w3-mapping-mute") -> dict:
    output = root / "out" / harness.OUTPUT_NAME
    media = output / "media"
    output.mkdir(parents=True)
    media.mkdir()
    probe = HERE / "harness.py"
    return {
        "schemaVersion": harness.SCHEMA_VERSION,
        "externalScriptingSetting": "None",
        "projectName": harness.PROJECT_NAME,
        "action": action,
        "phase": action,
        "actionId": "offline-" + action,
        "stateId": "offline-state-" + action,
        "probePath": str(probe),
        "probeSha256": hashlib.sha256(probe.read_bytes()).hexdigest(),
        "outputDir": str(output),
        "mediaDir": str(media),
        "owned": {"projectUid": "project-uid"},
        "timelineUid": "timeline-uid",
        "itemUid": "item-uid",
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="issue149-discriminator-check-") as temp:
        root = Path(temp)

        config = _config(root)
        harness._validate_config(config)
        prepare = _config(root / "prepare", "prepare")
        prepare.pop("owned")
        prepare["actionId"] = "offline-prepare"
        prepare["allowEmptyUntitled"] = True
        harness._validate_config(prepare)
        guarded = dict(prepare)
        guarded.pop("allowEmptyUntitled")
        guarded["creationGuard"] = {
            "mode": "known-disposable",
            "projectName": "VERA 149 Discriminators 20261002-b",
            "projectUid": "known-disposable-149",
            "allowedProjectNames": ["VERA 149 Discriminators 20261002-b"],
        }
        guarded["actionId"] = "offline-prepare-known"
        harness._validate_config(guarded)

        journal = Journal()
        result = harness._creation_guard(journal, Manager(KnownDisposable()), guarded)
        assert result["mode"] == "known-disposable"
        assert result["projectUid"] == "known-disposable-149"
        assert all("JobStatus" not in row for row in result["renderJobs"])
        assert result["renderJobStatuses"] == [
            {"jobId": "old-terminal", "status": {"JobStatus": "Complete"}},
            {"jobId": "old-failed", "status": {"JobStatus": "Failed"}},
        ]
        assert [method for phase, method in journal.calls if phase == "request"] == [
            "GetCurrentProject",
            "GetName",
            "GetUniqueId",
            "GetRenderJobList",
            "GetRenderJobStatus",
            "GetRenderJobStatus",
            "IsRenderingInProgress",
        ]
        try:
            bad = dict(guarded)
            bad["creationGuard"] = dict(guarded["creationGuard"], projectUid="wrong")
            harness._creation_guard(Journal(), Manager(KnownDisposable()), bad)
        except harness.HarnessError:
            pass
        else:
            raise AssertionError("known-disposable UID mismatch was accepted")

        try:
            harness._creation_guard(
                Journal(),
                Manager(KnownDisposable({"active": {"JobStatus": "Rendering"}})),
                guarded,
            )
        except harness.HarnessError:
            pass
        else:
            raise AssertionError("active queued render was accepted")

        try:
            harness._creation_guard(
                Journal(),
                Manager(KnownDisposable({"unknown": {"CompletionPercentage": 100}})),
                guarded,
            )
        except harness.HarnessError:
            pass
        else:
            raise AssertionError("unknown queued render was accepted")

        try:
            harness._creation_guard(
                Journal(), Manager(KnownDisposable(rendering=True)), guarded
            )
        except harness.HarnessError:
            pass
        else:
            raise AssertionError("globally rendering project was accepted")

        try:
            protected = dict(guarded)
            protected["creationGuard"] = dict(
                guarded["creationGuard"],
                projectName="VERA Issue 141 Synthetic Probe",
                allowedProjectNames=["VERA Issue 141 Synthetic Probe"],
            )
            harness._creation_guard(Journal(), Manager(KnownDisposable()), protected)
        except harness.HarnessError:
            pass
        else:
            raise AssertionError("protected #141 project name was accepted")

        media = root / "swap-media"
        media.mkdir()
        replacement = media / "replacement.mov"
        replacement.write_bytes(b"synthetic audio and video")
        digest = hashlib.sha256(replacement.read_bytes()).hexdigest()
        swap = {
            "path": str(replacement),
            "replacementHasAudio": True,
            "replacementAudioChannels": 1,
            "expectedSha256": digest,
        }
        checked, path = harness._swap_guard(
            {"mediaDir": str(media), "swap": swap}
        )
        assert checked["replacementAudioChannels"] == 1 and path == replacement
        try:
            harness._swap_guard(
                {
                    "mediaDir": str(media),
                    "swap": dict(swap, replacementHasAudio=False),
                }
            )
        except harness.HarnessError:
            pass
        else:
            raise AssertionError("audio-less W6 replacement was accepted")

        assert launcher._output_path({"outputDir": str(config["outputDir"])}) == Path(
            config["outputDir"]
        )

        console_config = {
            "schemaVersion": console.SCHEMA_VERSION,
            "externalScriptingSetting": "None",
            "projectName": console.PROJECT_NAME,
            "action": "console-render",
            "phase": "offline-console-render",
            "actionId": "offline-console-render",
            "outputDir": str(console.OUTPUT),
            "timelineUid": "timeline-uid",
            "owned": {"projectUid": "project-uid"},
            "render": {"settings": {}},
            "consoleSourceSha256": hashlib.sha256(
                (HERE / "console-render.py").read_bytes()
            ).hexdigest(),
            "harnessSourceSha256": hashlib.sha256(
                (HERE / "harness.py").read_bytes()
            ).hexdigest(),
        }
        console._validate(console_config)
        for key in ("consoleSourceSha256", "harnessSourceSha256"):
            broken_console = dict(console_config, **{key: "0" * 64})
            try:
                console._validate(broken_console)
            except RuntimeError:
                pass
            else:
                raise AssertionError(f"Console source pin was not checked: {key}")

    source = (HERE / "harness.py").read_text(encoding="utf-8")
    launcher_source = (HERE / "launcher.py").read_text(encoding="utf-8")
    assert "scriptapp" not in source + launcher_source
    assert "DaVinci Resolve/" in launcher_source
    assert "Workflow Integration Plugins" in launcher_source
    assert "/Blackmagic Design/Resolve/Workflow Integration Plugins" not in launcher_source
    assert "SetCurrentRenderMode" in source
    assert not re.search(r"(?<!Current)SetRenderMode", source)
    assert "w3-mapping-mute" in source and "w6-relink-render" in source
    macro = (HERE / "hammerspoon-launch.lua").read_text(encoding="utf-8")
    assert "VERA 149 Discriminators 20261002-b" in macro
    plan = (HERE / "plan.md").read_text(encoding="utf-8")
    assert "compile(open(" in plan and "__file__=" in plan
    print("Issue 149 discriminator guards passed; no native application was launched")


if __name__ == "__main__":
    main()
