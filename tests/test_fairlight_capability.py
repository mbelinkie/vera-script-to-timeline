from __future__ import annotations

import json
import subprocess
import sys
import wave
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.fairlight_capability import (
    CapabilityEvidence,
    FairlightProbeConfig,
    FairlightProbeError,
    OriginalAudioEvidence,
    ProbeExecution,
    ResolveEvidence,
    load_probe_config,
    run_fairlight_capability_probe,
    select_fairlight_preset,
    write_operator_handoff,
)


def _capability(status: str = "supported-api") -> CapabilityEvidence:
    return CapabilityEvidence(
        status=status,
        operation="bounded mutation",
        before={"enabled": False},
        request={"enabled": True},
        readback={"enabled": True},
        restored={"enabled": False},
        explanation="mutation, readback, and restoration agreed",
    )


def _preserved(source: Path, digest: str) -> OriginalAudioEvidence:
    return OriginalAudioEvidence(
        source_path=str(source),
        source_sha256_before=digest,
        source_sha256_after=digest,
        original_media_id="original-media",
        original_timeline_item_present=True,
        original_clip_enabled=True,
        replacement_timeline_item_present=False,
        preserved=True,
        explanation="original source and restored timeline item were verified",
    )


def _execution(source: Path, digest: str) -> ProbeExecution:
    return ProbeExecution(
        channel_mapping=_capability(),
        capabilities={
            "voiceIsolation": _capability(),
            "dialogueLeveler": _capability(),
            "normalization": _capability(),
            "eqDynamicsPreset": _capability("operator-only"),
            "pcmWavRender": _capability(),
        },
        attachment_path={
            "exactStartFrame": 0,
            "replacementSurvivedReopen": True,
            "replacementRemoved": True,
            "originalRestoredAfterReopen": True,
        },
        original_audio=_preserved(source, digest),
        fairlight_presets=("VERA Dialogue",),
        rendered_wav={
            "sampleRate": 48000,
            "codec": "Linear PCM",
            "bitDepth": 24,
        },
        discrepancies=(),
    )


class RecordingAdapter:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[str] = []

    def preflight(self, config: FairlightProbeConfig) -> ResolveEvidence:
        self.calls.append("preflight")
        return ResolveEvidence(
            product_name="DaVinci Resolve Studio",
            version="21.1.0",
            build="14",
            suffix="",
            current_page="fairlight",
        )

    def execute(
        self,
        config: FairlightProbeConfig,
        source_path: Path,
        source_sha256: str,
    ) -> ProbeExecution:
        self.calls.append("execute")
        if self.fail:
            raise RuntimeError("replacement append failed")
        return _execution(source_path, source_sha256)

    def restore_original_audio(
        self, source_path: Path, source_sha256: str
    ) -> OriginalAudioEvidence:
        self.calls.append("restore_original_audio")
        return _preserved(source_path, source_sha256)


def _config(tmp_path: Path, **overrides: Any) -> FairlightProbeConfig:
    values: dict[str, Any] = {
        "project_name": "VERA Issue 110 Fairlight Probe 20260909-170000",
        "output_dir": tmp_path / "issue-110-output",
        "external_scripting_setting": "None",
        "documentation_retrieved_at": "2026-09-09",
        "fairlight_preset_name": None,
    }
    values.update(overrides)
    return FairlightProbeConfig(**values)


def test_report_schema_and_serialization_are_stable(tmp_path: Path) -> None:
    adapter = RecordingAdapter()
    report = run_fairlight_capability_probe(
        object(), _config(tmp_path), adapter_factory=lambda _: adapter
    )

    first = report.to_json()
    second = report.to_json()
    value = json.loads(first)

    assert first == second and first.endswith("\n")
    assert value["schemaVersion"] == "vera-fairlight-capability-report-v1"
    assert value["status"] == "verified"
    assert value["runtime"]["pythonVersion"]
    assert set(value["capabilities"]) == {
        "voiceIsolation",
        "dialogueLeveler",
        "normalization",
        "eqDynamicsPreset",
        "pcmWavRender",
    }
    assert value["originalAudio"]["preserved"] is True
    assert adapter.calls == ["preflight", "execute"]


def test_unsafe_setting_refuses_before_files_or_adapter(tmp_path: Path) -> None:
    config = _config(tmp_path, external_scripting_setting="Local")

    with pytest.raises(FairlightProbeError, match="must remain None"):
        run_fairlight_capability_probe(
            object(),
            config,
            adapter_factory=lambda _: (_ for _ in ()).throw(
                AssertionError("adapter constructed")
            ),
        )

    assert not config.output_dir.exists()


@pytest.mark.parametrize("requested", [None, "Missing preset"])
def test_unverified_preset_is_refused_without_mutation(requested: str | None) -> None:
    selected, evidence = select_fairlight_preset(("VERA Dialogue",), requested)

    assert selected is None
    assert evidence.status in {"operator-only", "unavailable"}
    assert evidence.request == {"presetName": requested}
    assert evidence.readback is None


def test_failure_restores_and_reports_original_audio(tmp_path: Path) -> None:
    adapter = RecordingAdapter(fail=True)
    report = run_fairlight_capability_probe(
        object(), _config(tmp_path), adapter_factory=lambda _: adapter
    )

    value = json.loads(report.to_json())
    assert report.status == "mutation_failed"
    assert report.original_audio.preserved
    assert "replacement append failed" in report.message
    assert value["originalAudio"]["replacementTimelineItemPresent"] is False
    assert adapter.calls == ["preflight", "execute", "restore_original_audio"]


def test_restoration_failure_is_retained_for_operator_inspection(
    tmp_path: Path,
) -> None:
    class RestorationFailAdapter(RecordingAdapter):
        def restore_original_audio(
            self, source_path: Path, source_sha256: str
        ) -> OriginalAudioEvidence:
            self.calls.append("restore_original_audio")
            raise RuntimeError("save/reopen unavailable")

    adapter = RestorationFailAdapter(fail=True)
    report = run_fairlight_capability_probe(
        object(), _config(tmp_path), adapter_factory=lambda _: adapter
    )

    assert report.status == "mutation_failed"
    assert report.original_audio.preserved is False
    assert report.original_audio.source_sha256_before == (
        report.original_audio.source_sha256_after
    )
    assert "restoration failed" in report.message
    assert "operator must inspect" in report.original_audio.explanation


def test_handoff_names_automated_and_operator_boundaries(tmp_path: Path) -> None:
    report = run_fairlight_capability_probe(
        object(), _config(tmp_path), adapter_factory=lambda _: RecordingAdapter()
    )
    handoff = tmp_path / "operator-handoff.md"

    write_operator_handoff(report, handoff)
    text = handoff.read_text(encoding="utf-8")

    assert "1." in text
    assert "External scripting using** remains **None" in text
    assert "eqDynamicsPreset: `operator-only`" in text
    assert "#108" in text
    assert "presenter" in text.lower()


def test_handoff_records_failed_closed_wav_boundary(tmp_path: Path) -> None:
    report = run_fairlight_capability_probe(
        object(), _config(tmp_path), adapter_factory=lambda _: RecordingAdapter()
    )
    report = replace(report, rendered_wav=None)
    handoff = tmp_path / "operator-handoff-unavailable.md"

    write_operator_handoff(report, handoff)
    text = handoff.read_text(encoding="utf-8")

    assert "PCM-WAV rendering is recorded as `unavailable`" in text
    assert "rejected request and failed-closed attachment path" in text


class FakeMedia:
    def __init__(self, path: Path, media_id: str) -> None:
        self.path = path
        self.media_id = media_id
        self.mapping: dict[str, Any] = {
            "embedded_audio_channels": 2,
            "track_mapping": {
                "1": {
                    "channel_idx": [1, 2],
                    "mute": False,
                    "type": "stereo",
                }
            },
        }

    def GetClipProperty(self) -> dict[str, str]:
        return {"File Path": str(self.path)}

    def GetMediaId(self) -> str:
        return self.media_id

    def GetAudioMapping(self) -> str:
        return json.dumps(self.mapping)

    def SetAudioMapping(self, value: str) -> bool:
        self.mapping = json.loads(value)
        return True


class FakeItem:
    def __init__(self, media: FakeMedia, start: int) -> None:
        self.media = media
        self.start = start
        self.enabled = True
        self.linked: list[FakeItem] = []
        self.voice = {"isEnabled": False, "amount": 0}
        self.properties: dict[str, Any] = {
            "AudioVolumeEnabled": True,
            "AudioVolume": 0.0,
            "AudioDialogueLevelerEnabled": False,
            "AudioDialogueLevelerMode": 0,
            "AudioDialogueLevelerReduceLoudDialogue": False,
            "AudioDialogueLevelerLiftSoftDialogue": False,
            "AudioDialogueLevelerBackgroundReduction": False,
            "AudioDialogueLevelerOutputGain": 0.0,
        }

    def GetStart(self, _subframe: bool) -> int:
        return self.start

    def GetMediaPoolItem(self) -> FakeMedia:
        return self.media

    def GetClipEnabled(self) -> bool:
        return self.enabled

    def SetClipEnabled(self, enabled: bool) -> bool:
        self.enabled = enabled
        return True

    def GetLinkedItems(self) -> list[FakeItem]:
        return self.linked

    def GetVoiceIsolationState(self) -> dict[str, Any]:
        return dict(self.voice)

    def SetVoiceIsolationState(self, state: dict[str, Any]) -> bool:
        self.voice = dict(state)
        return True

    def GetProperties(self) -> dict[str, Any]:
        return dict(self.properties)

    def SetProperties(self, values: dict[str, Any]) -> bool:
        self.properties.update(values)
        return True


class FakeTimeline:
    def __init__(self) -> None:
        self.tracks: dict[int, list[FakeItem]] = {}
        self.track_names: dict[int, str] = {}

    def SetStartTimecode(self, value: str) -> bool:
        return value == "00:00:00:00"

    def GetTrackCount(self, kind: str) -> int:
        return len(self.tracks) if kind == "audio" else 0

    def AddTrack(self, kind: str, subtype: str) -> bool:
        if kind != "audio" or subtype != "mono":
            return False
        self.tracks[len(self.tracks) + 1] = []
        return True

    def SetTrackName(self, kind: str, index: int, name: str) -> bool:
        if kind != "audio" or index not in self.tracks:
            return False
        self.track_names[index] = name
        return True

    def GetNormalizeAudioModes(self) -> list[str]:
        return ["Sample Peak Program"]

    def NormalizeAudioLevel(
        self, items: list[FakeItem], options: dict[str, Any]
    ) -> bool:
        if options != {
            "normalizationMode": "Sample Peak Program",
            "setLevelMode": 1,
            "targetLevel": -30.0,
        }:
            return False
        for item in items:
            item.properties["AudioVolume"] = -15.0
        return True

    def SetClipsLinked(self, items: list[FakeItem], linked: bool) -> bool:
        for item in items:
            item.linked = [candidate for candidate in items if candidate is not item]
            if not linked:
                item.linked = []
        return True

    def DeleteClips(self, items: list[FakeItem], ripple: bool) -> bool:
        if ripple:
            return False
        for values in self.tracks.values():
            values[:] = [item for item in values if item not in items]
        return True

    def GetItemListInTrack(self, kind: str, index: int) -> list[FakeItem]:
        return list(self.tracks[index]) if kind == "audio" else []


class FakePool:
    def __init__(self, project: FakeProject) -> None:
        self.project = project
        self.timeline: FakeTimeline | None = None
        self.next_media_id = 1

    def GetCurrentFolder(self) -> object:
        return object()

    def AddSubFolder(self, _parent: object, _name: str) -> object:
        return object()

    def SetCurrentFolder(self, _folder: object) -> bool:
        return True

    def CreateEmptyTimeline(self, _name: str) -> FakeTimeline:
        self.timeline = FakeTimeline()
        self.project.timeline = self.timeline
        return self.timeline

    def ImportMedia(self, values: list[str]) -> list[FakeMedia]:
        path = Path(values[0])
        media = FakeMedia(path, f"media-{self.next_media_id}")
        self.next_media_id += 1
        return [media]

    def AppendToTimeline(self, values: list[dict[str, Any]]) -> list[FakeItem]:
        assert self.timeline is not None
        value = values[0]
        item = FakeItem(value["mediaPoolItem"], value["recordFrame"])
        self.timeline.tracks[value["trackIndex"]].append(item)
        return [item]


class FakeProject:
    def __init__(self, name: str) -> None:
        self.name = name
        self.pool = FakePool(self)
        self.timeline: FakeTimeline | None = None
        self.render_settings: dict[str, Any] = {}
        self.render_status: dict[str, Any] = {}

    def GetName(self) -> str:
        return self.name

    def SetSettings(self, _values: dict[str, str]) -> bool:
        return True

    def GetMediaPool(self) -> FakePool:
        return self.pool

    def GetCurrentTimeline(self) -> FakeTimeline | None:
        return self.timeline

    def GetAudioRenderFormats(self) -> dict[str, str]:
        return {"Wave": "wav"}

    def GetAudioRenderCodecs(self, extension: str) -> dict[str, str]:
        return {"Linear PCM": "Linear PCM"} if extension == "wav" else {}

    def SetCurrentRenderMode(self, mode: int) -> bool:
        return mode == 1

    def SetCurrentRenderFormatAndCodec(self, extension: str, codec: str) -> bool:
        return (extension, codec) == ("wav", "Linear PCM")

    def SetRenderSettings(self, values: dict[str, Any]) -> bool:
        self.render_settings = dict(values)
        return True

    def AddRenderJob(self) -> str:
        return "job-1"

    def StartRendering(self, job_ids: list[str], interactive: bool) -> bool:
        if job_ids != ["job-1"] or interactive:
            return False
        output = (
            Path(self.render_settings["TargetDir"])
            / f"{self.render_settings['CustomName']}.wav"
        )
        with wave.open(str(output), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(3)
            writer.setframerate(48000)
            writer.writeframes(b"\x00\x00\x00" * 48000)
        self.render_status = {"JobStatus": "Complete", "CompletionPercentage": 100}
        return True

    def GetRenderJobStatus(self, job_id: str) -> dict[str, Any]:
        return dict(self.render_status) if job_id == "job-1" else {}


class FakeManager:
    def __init__(self) -> None:
        self.project: FakeProject | None = None

    def GetProjectListInCurrentFolder(self) -> list[str]:
        return [] if self.project is None else [self.project.name]

    def CreateProject(self, name: str) -> FakeProject:
        self.project = FakeProject(name)
        return self.project

    def SaveProject(self) -> bool:
        return self.project is not None

    def CloseProject(self, project: FakeProject) -> bool:
        return project is self.project

    def LoadProject(self, name: str) -> FakeProject | None:
        return (
            self.project
            if self.project is not None and self.project.name == name
            else None
        )


class FakeResolve:
    NORMALIZE_AUDIO_SET_LEVEL_INDEPENDENT = 1
    DIALOGUE_LEVELER_MODE_OPTIMIZE_MODERATE_LEVELS = 1
    DIALOGUE_LEVELER_MODE_MORE_LIFT_FOR_LOW_LEVELS = 2

    def __init__(self) -> None:
        self.manager = FakeManager()

    def GetProductName(self) -> str:
        return "DaVinci Resolve Studio"

    def GetVersion(self) -> list[int | str]:
        return [21, 1, 0, 14, ""]

    def GetCurrentPage(self) -> str:
        return "fairlight"

    def GetProjectManager(self) -> FakeManager:
        return self.manager

    def GetFairlightPresets(self) -> list[str]:
        return []


def test_public_adapter_mutates_reads_back_and_restores(tmp_path: Path) -> None:
    report = run_fairlight_capability_probe(FakeResolve(), _config(tmp_path))

    assert report.status == "verified"
    assert report.channel_mapping.status == "supported-api"
    assert report.channel_mapping.readback["track_mapping"] == {
        "1": {"channel_idx": [1], "mute": False, "type": "mono"}
    }
    assert report.capabilities["voiceIsolation"].status == "supported-api"
    assert report.capabilities["dialogueLeveler"].status == "supported-api"
    assert report.capabilities["normalization"].status == "supported-api"
    assert report.capabilities["eqDynamicsPreset"].status == "operator-only"
    assert report.capabilities["pcmWavRender"].status == "supported-api"
    assert report.attachment_path["replacementSurvivedReopen"] is True
    assert report.attachment_path["replacementRemoved"] is True
    assert report.attachment_path["originalRestoredAfterReopen"] is True
    assert report.original_audio.preserved is True


def test_config_and_injected_import_stay_standard_library_only(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "pythonPath": str(Path(__file__).resolve().parents[1] / "python"),
                "projectName": "VERA Issue 110 Fairlight Probe 20260909-180000",
                "outputDir": str(tmp_path / "new-output"),
                "externalScriptingSetting": "None",
                "documentationRetrievedAt": "2026-09-09",
                "fairlightPresetName": None,
            }
        ),
        encoding="utf-8",
    )

    assert load_probe_config(config_path).external_scripting_setting == "None"
    python_root = Path(__file__).resolve().parents[1] / "python"
    command = (
        "import sys; "
        f"sys.path.insert(0, {str(python_root)!r}); "
        "import vera_timeline_agent.fairlight_capability; "
        "assert not ({'opentimelineio', 'jsonschema', 'referencing'} "
        "& set(sys.modules))"
    )
    completed = subprocess.run(
        [sys.executable, "-S", "-c", command],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_staged_launcher_is_distinct_from_issue_6_and_external_bridge() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    staged = (
        repository_root
        / "staging/resolve-workflow-integration/VERA Issue 110 Fairlight Probe.py"
    ).read_text(encoding="utf-8")

    assert "vera-issue-110-fairlight-probe-result.json" in staged
    assert "DaVinciResolveScript" not in staged
    assert "scriptapp" not in staged
    assert "site-packages" not in staged
    assert ".venv" not in staged
    assert "vera-issue-6-full-build" not in staged
