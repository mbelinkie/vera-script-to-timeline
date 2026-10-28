"""Focused safety and mutation tests for the injected #326 native probe."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, cast

import pytest

from scripts import issue326_native_probe as probe


def _write(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _case(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    case_root = root / "cases" / "word-end-b"
    package_root = case_root / "package"
    build = package_root / "Builds" / "build-326"
    narration_path = package_root / "Media" / "Narration" / "narration.wav"
    image_path = package_root / "Media" / "Resolved" / "placeholder.png"
    music_path = case_root / "shared" / "music.wav"
    base_otio_path = build / "timeline.otio"
    manifest_path = case_root / "compile-input" / "timeline-manifest-v2.json"
    original_path = case_root / "authoring" / "original.json"
    effective_path = case_root / "authoring" / "effective.json"
    derived_path = case_root / "derived-music.otio"

    file_hashes = {
        "Builds/build-326/timeline.otio": _write(base_otio_path, b"base timeline"),
        "Media/Narration/narration.wav": _write(narration_path, b"narration samples"),
        "Media/Resolved/placeholder.png": _write(image_path, b"placeholder image"),
    }
    original_hash = _write(original_path, b"original authoring snapshot")
    effective_hash = _write(effective_path, b"effective authoring snapshot")
    manifest_hash = _write(manifest_path, b"pinned manifest")
    music_hash = _write(music_path, b"music samples")
    derived_hash = _write(derived_path, b"derived OTIO")

    events = [
        {
            "durationFrames": 48,
            "eventId": "narration-a",
            "kind": "narration",
            "recordStartFrame": 0,
            "sourceInFrame": 0,
            "sourcePath": str(narration_path),
            "sourceSha256": f"sha256:{file_hashes['Media/Narration/narration.wav']}",
            "trackIndex": 1,
            "trackKind": "audio",
        },
        {
            "durationFrames": 48,
            "eventId": "placeholder-a",
            "kind": "placeholder",
            "recordStartFrame": 0,
            "sourceInFrame": 0,
            "sourcePath": str(image_path),
            "sourceSha256": f"sha256:{file_hashes['Media/Resolved/placeholder.png']}",
            "trackIndex": 1,
            "trackKind": "video",
        },
        {
            "durationFrames": 84,
            "eventId": "music-bed",
            "kind": "music",
            "recordStartFrame": 0,
            "sourceInFrame": 24,
            "sourcePath": str(music_path),
            "sourceSha256": f"sha256:{music_hash}",
            "trackIndex": 2,
            "trackKind": "audio",
        },
    ]
    sidecar: dict[str, Any] = {
        "schemaVersion": "issue326-music-probe/v1",
        "evidenceLevel": "probe_only",
        "caseId": "word-end-b",
        "authoringSnapshot": {
            "path": str(original_path),
            "rawSha256": f"sha256:{original_hash}",
        },
        "effectiveAuthoringSnapshot": {
            "path": str(effective_path),
            "rawSha256": f"sha256:{effective_hash}",
        },
        "base": {
            "buildId": "build-326",
            "packageRoot": str(package_root),
            "manifest": {
                "path": str(manifest_path),
                "sha256": f"sha256:{manifest_hash}",
            },
            "otio": {
                "path": str(base_otio_path),
                "sha256": f"sha256:{file_hashes['Builds/build-326/timeline.otio']}",
            },
            "verification": {
                "fileHashes": {
                    key: f"sha256:{value}" for key, value in file_hashes.items()
                }
            },
        },
        "timeline": {
            "frameRate": {"numerator": 24, "denominator": 1},
            "audioSampleRate": 48000,
            "rows": [],
        },
        "music": {
            "durationFrames": 84,
            "recordStartFrame": 0,
            "recordEndFrame": 84,
            "recordRange": {"startFrame": 0, "endFrame": 84, "durationFrames": 84},
            "sourceTrimSamples": 48000,
            "sourceRangeSamples": {"startSample": 48000, "endSample": 216000},
            "sourcePath": str(music_path),
            "sourceSha256": f"sha256:{music_hash}",
            "source": {"path": str(music_path), "sha256": f"sha256:{music_hash}"},
            "gainDb": -12,
            "fade": {"curve": "linear", "fadeInFrames": 6, "fadeOutFrames": 6},
            "expectedNative": {"events": events},
        },
        "derivedOtio": {"path": str(derived_path), "sha256": f"sha256:{derived_hash}"},
    }
    sidecar_path = case_root / "music-probe.json"
    sidecar_path.write_text(json.dumps(sidecar, sort_keys=True), encoding="utf-8")
    request: dict[str, Any] = {
        "action": "import",
        "operationId": "word-end-b-import-1",
        "projectName": "VERA326_MUSIC_TEST",
        "projectId": "project-326",
        "caseId": "word-end-b",
        "timelineName": "VERA326_MUSIC_word_end_b_1",
        "sidecarPath": str(sidecar_path),
        "sidecarSha256": hashlib.sha256(sidecar_path.read_bytes()).hexdigest(),
        "otioPath": str(derived_path),
        "otioSha256": derived_hash,
    }
    return request, sidecar


class _Media:
    def __init__(self, path: str) -> None:
        self.path = path

    def GetClipProperty(self) -> dict[str, str]:
        return {"File Path": self.path}


class _Item:
    def __init__(
        self, row: dict[str, Any], *, partial_invalid_write: bool = False
    ) -> None:
        self.row = row
        self.properties = {"AudioVolumeEnabled": True, "AudioVolume": 0.0}
        self.fades = {"FadeIn": 0, "FadeOut": 0}
        self.clip_enabled = True
        self.partial_invalid_write = partial_invalid_write
        self.set_properties_calls: list[dict[str, Any]] = []

    def GetUniqueId(self) -> str:
        return cast(str, self.row["eventId"])

    def GetMediaPoolItem(self) -> _Media:
        return _Media(self.row["sourcePath"])

    def GetSourceStartFrame(self) -> int:
        if self.row["kind"] == "placeholder":
            return 6
        return cast(int, self.row["sourceInFrame"])

    def GetSourceEndFrame(self) -> int:
        if self.row["kind"] == "narration":
            return cast(int, self.row["sourceInFrame"] + self.row["durationFrames"] - 1)
        if self.row["kind"] == "placeholder":
            return 6
        return cast(int, self.row["sourceInFrame"] + self.row["durationFrames"])

    def GetSourceStartTime(self) -> float:
        return cast(float, self.row["sourceInFrame"] / 24)

    def GetSourceEndTime(self) -> float:
        if self.row["kind"] == "placeholder":
            return 1 / 24
        return cast(
            float, (self.row["sourceInFrame"] + self.row["durationFrames"]) / 24
        )

    def GetStart(self) -> int:
        return cast(int, self.row["recordStartFrame"])

    def GetEnd(self) -> int:
        return cast(int, self.row["recordStartFrame"] + self.row["durationFrames"])

    def GetDuration(self) -> int:
        return cast(int, self.row["durationFrames"])

    def GetProperties(self) -> dict[str, Any]:
        return dict(self.properties)

    def GetFades(self) -> dict[str, int]:
        return dict(self.fades)

    def GetClipEnabled(self) -> bool:
        return self.clip_enabled

    def SetClipEnabled(self, enabled: bool) -> bool:
        self.clip_enabled = enabled
        return True

    def SetProperties(self, values: dict[str, Any]) -> bool:
        self.set_properties_calls.append(dict(values))
        if "VERA326InvalidProbeProperty" in values:
            if self.partial_invalid_write:
                self.properties["AudioVolume"] = values["AudioVolume"]
            return False
        self.properties.update(values)
        return True

    def SetFades(self, values: dict[str, int]) -> bool:
        self.fades = dict(values)
        return True


class _Timeline:
    def __init__(
        self,
        uid: str,
        name: str,
        events: list[dict[str, Any]],
        *,
        partial_invalid_write: bool = False,
    ) -> None:
        self.uid, self.name = uid, name
        self.rows = events
        self.items = {
            (kind, index): [
                _Item(row, partial_invalid_write=partial_invalid_write)
                for row in events
                if row["trackKind"] == kind and row["trackIndex"] == index
            ]
            for kind in ("audio", "video")
            for index in {
                row["trackIndex"] for row in events if row["trackKind"] == kind
            }
        }
        self.enabled: dict[tuple[str, int], bool] = {key: True for key in self.items}

    def GetUniqueId(self) -> str:
        return self.uid

    def GetName(self) -> str:
        return self.name

    def GetTrackCount(self, kind: str) -> int:
        indexes = [index for track_kind, index in self.items if track_kind == kind]
        return max(indexes, default=0)

    def GetItemListInTrack(self, kind: str, index: int) -> list[_Item]:
        return self.items.get((kind, index), [])

    def GetIsTrackEnabled(self, kind: str, index: int) -> bool:
        return self.enabled[(kind, index)]

    def SetTrackEnable(self, kind: str, index: int, enabled: bool) -> bool:
        self.enabled[(kind, index)] = enabled
        return True


class _Pool:
    def __init__(
        self, project: _Project, sidecar: dict[str, Any], calls: list[Any]
    ) -> None:
        self.project, self.sidecar, self.calls = project, sidecar, calls

    def ImportTimelineFromFile(self, path: str, options: dict[str, Any]) -> _Timeline:
        self.calls.append(("ImportTimelineFromFile", path, options))
        timeline = _Timeline(
            "timeline-1",
            options["timelineName"],
            self.sidecar["music"]["expectedNative"]["events"],
        )
        self.project.timelines.append(timeline)
        return timeline


class _Project:
    def __init__(
        self,
        sidecar: dict[str, Any],
        calls: list[Any],
        *,
        partial_invalid_write: bool = False,
    ) -> None:
        self.sidecar, self.calls = sidecar, calls
        self.timelines: list[_Timeline] = []
        self.pool = _Pool(self, sidecar, calls)
        self.partial_invalid_write = partial_invalid_write
        self.render_jobs: list[dict[str, Any]] = []
        self.render_statuses: dict[str, dict[str, Any]] = {}
        self.render_settings: dict[str, Any] = {}
        self.render_presets: list[str] = []
        self.start_render_calls: list[tuple[list[str], bool]] = []
        self.current_render_format = {"format": "unknown", "codec": ""}
        self.current_render_mode = 1
        self.next_job_number = 1

    def GetName(self) -> str:
        return "VERA326_MUSIC_TEST"

    def GetUniqueId(self) -> str:
        return "project-326"

    def GetTimelineCount(self) -> int:
        return len(self.timelines)

    def GetTimelineByIndex(self, index: int) -> _Timeline:
        return self.timelines[index - 1]

    def GetMediaPool(self) -> _Pool:
        return self.pool

    def GetAudioRenderFormats(self) -> dict[str, str]:
        return {"Wave": "wav"}

    def GetAudioRenderCodecs(self, _format: str) -> dict[str, str]:
        return {"Linear PCM": "lpcm"}

    def IsRenderingInProgress(self) -> bool:
        return False

    def GetRenderJobList(self) -> list[Any]:
        return list(self.render_jobs)

    def GetRenderJobStatus(self, job_id: str) -> dict[str, Any]:
        return dict(self.render_statuses[job_id])

    def GetCurrentRenderFormatAndCodec(self) -> dict[str, str]:
        return dict(self.current_render_format)

    def GetCurrentRenderMode(self) -> int:
        return self.current_render_mode

    def GetRenderPresetList(self) -> list[str]:
        return list(self.render_presets)

    def SaveAsNewRenderPreset(self, name: str) -> bool:
        self.render_presets.append(name)
        return True

    def SetRenderSettings(self, settings: dict[str, Any]) -> bool:
        self.render_settings = dict(settings)
        return True

    def AddRenderJob(self) -> str:
        job_id = f"job-{self.next_job_number}"
        self.next_job_number += 1
        timeline = self.timelines[-1]
        job = {
            "JobId": job_id,
            "TimelineName": timeline.GetName(),
            "IsExportVideo": False,
            "IsExportAudio": True,
            "AudioSampleRate": self.render_settings["AudioSampleRate"],
            "AudioBitDepth": self.render_settings["AudioBitDepth"],
            "AudioCodec": self.render_settings["AudioCodec"],
            "TargetDir": self.render_settings["TargetDir"],
            "OutputFilename": self.render_settings["CustomName"] + ".wav",
        }
        self.render_jobs.append(job)
        self.render_statuses[job_id] = {"JobStatus": "Ready", "CompletionPercentage": 0}
        return job_id

    def StartRendering(self, job_ids: list[str], interactive: bool) -> bool:
        self.start_render_calls.append((list(job_ids), interactive))
        job_id = job_ids[0]
        job = next(row for row in self.render_jobs if row["JobId"] == job_id)
        target = Path(job["TargetDir"]) / job["OutputFilename"]
        target.write_bytes(b"RIFF" + (48).to_bytes(4, "little") + b"WAVE" + b"\0" * 40)
        self.render_statuses[job_id] = {
            "JobStatus": "Complete",
            "CompletionPercentage": 100,
        }
        return True


class _Manager:
    def __init__(self, project: _Project) -> None:
        self.current = project

    def GetCurrentProject(self) -> _Project:
        return self.current


class _Resolve:
    def __init__(self, project: _Project) -> None:
        self.manager = _Manager(project)

    def GetProductName(self) -> str:
        return "DaVinci Resolve Studio"

    def GetVersionString(self) -> str:
        return "21.1.1.10"

    def GetProjectManager(self) -> _Manager:
        return self.manager


def _native(
    request: dict[str, Any],
    sidecar: dict[str, Any],
    *,
    partial_invalid_write: bool = False,
) -> tuple[_Resolve, _Project, list[Any]]:
    calls: list[Any] = []
    project = _Project(sidecar, calls, partial_invalid_write=partial_invalid_write)
    resolve = _Resolve(project)
    return resolve, project, calls


def _configure_request(request: dict[str, Any]) -> dict[str, Any]:
    return {
        **request,
        "action": "configure",
        "operationId": "word-end-b-configure-1",
        "timelineId": "timeline-1",
        "timelineName": "VERA326_MUSIC_word_end_b_1",
    }


def test_import_requires_the_pinned_project_identity_before_any_native_write(
    tmp_path: Path,
) -> None:
    request, sidecar = _case(tmp_path)
    resolve, project, calls = _native(request, sidecar)
    request["projectId"] = "some-other-project"

    with pytest.raises(ValueError, match="project identity changed"):
        probe.run(resolve, request)

    assert calls == []
    assert project.GetTimelineCount() == 0


def test_import_checks_all_pinned_inputs_before_calling_resolve(tmp_path: Path) -> None:
    request, sidecar = _case(tmp_path)
    resolve, project, calls = _native(request, sidecar)
    music_path = Path(sidecar["music"]["sourcePath"])
    music_path.write_bytes(b"changed music")

    with pytest.raises(ValueError, match="bytes changed"):
        probe.run(resolve, request)

    assert calls == []
    assert project.GetTimelineCount() == 0


def test_import_refuses_a_missing_source_before_calling_resolve(tmp_path: Path) -> None:
    request, sidecar = _case(tmp_path)
    resolve, project, calls = _native(request, sidecar)
    Path(sidecar["music"]["sourcePath"]).unlink()

    with pytest.raises(ValueError, match="not an existing absolute file"):
        probe.run(resolve, request)

    assert calls == []
    assert project.GetTimelineCount() == 0


def test_import_refuses_an_invalid_music_extent_before_calling_resolve(
    tmp_path: Path,
) -> None:
    request, sidecar = _case(tmp_path)
    resolve, project, calls = _native(request, sidecar)
    sidecar["music"]["expectedNative"]["events"][-1]["durationFrames"] = 0
    sidecar_path = Path(request["sidecarPath"])
    sidecar_path.write_text(json.dumps(sidecar, sort_keys=True), encoding="utf-8")
    request["sidecarSha256"] = hashlib.sha256(sidecar_path.read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="invalid extent"):
        probe.run(resolve, request)

    assert calls == []
    assert project.GetTimelineCount() == 0


def test_sidecar_accepts_the_eleven_second_frame_bound(tmp_path: Path) -> None:
    request, sidecar = _case(tmp_path)
    placeholder = next(
        row
        for row in sidecar["music"]["expectedNative"]["events"]
        if row["kind"] == "placeholder"
    )
    placeholder["recordStartFrame"] = 216
    sidecar_path = Path(request["sidecarPath"])
    sidecar_path.write_text(json.dumps(sidecar, sort_keys=True), encoding="utf-8")
    request["sidecarSha256"] = hashlib.sha256(sidecar_path.read_bytes()).hexdigest()

    payload, _ = probe._sidecar(request)

    assert payload["caseId"] == "word-end-b"
    assert (
        max(
            row["recordStartFrame"] + row["durationFrames"]
            for row in payload["music"]["expectedNative"]["events"]
        )
        == probe.MAX_RENDER_FRAMES
        == 264
    )


def test_import_adds_one_new_named_timeline_and_reads_back_every_event(
    tmp_path: Path,
) -> None:
    request, sidecar = _case(tmp_path)
    resolve, project, calls = _native(request, sidecar)

    result = probe.run(resolve, request)

    assert result["status"] == "imported"
    assert result["timelineId"] == "timeline-1"
    assert result["readback"]["timelineName"] == request["timelineName"]
    assert len(result["readback"]["events"]) == len(
        sidecar["music"]["expectedNative"]["events"]
    )
    narration = next(
        row for row in result["readback"]["events"] if row["eventId"] == "narration-a"
    )
    placeholder = next(
        row for row in result["readback"]["events"] if row["eventId"] == "placeholder-a"
    )
    assert narration["nativeSourceEndFrame"] == 47
    assert narration["sourceOutFrame"] == 48
    assert placeholder["nativeSourceStartFrame"] == 6
    assert placeholder["sourceInFrame"] == 0
    assert placeholder["sourceOutFrame"] == 1
    assert placeholder["durationFrames"] == 48
    assert calls[0][0] == "ImportTimelineFromFile"
    assert calls[0][2] == {
        "timelineName": request["timelineName"],
        "importSourceClips": True,
    }
    assert result["nativeMutationAttempts"] == ["mediaPool.ImportTimelineFromFile"]
    assert project.GetTimelineCount() == 1


def test_diagnostic_readback_exposes_raw_getters_without_mutation(
    tmp_path: Path,
) -> None:
    request, sidecar = _case(tmp_path)
    resolve, project, calls = _native(request, sidecar)
    timeline = _Timeline(
        "timeline-1",
        "VERA326_MUSIC_word_end_b_1",
        sidecar["music"]["expectedNative"]["events"],
    )
    project.timelines.append(timeline)
    request.update(
        action="diagnose",
        operationId="word-end-b-diagnose-1",
        timelineId="timeline-1",
        timelineName=timeline.GetName(),
    )

    result = probe.run(resolve, request)

    narration = next(
        row for row in result["events"] if row["timelineItemId"] == "narration-a"
    )
    assert narration["getters"]["GetSourceStartFrame"] == 0
    assert narration["getters"]["GetSourceEndFrame"] == 47
    assert narration["getters"]["GetStart"] == 0
    assert narration["getters"]["GetEnd"] == 48
    assert narration["getters"]["GetDuration"] == 48
    assert result["trackEnableControl"]["getterAvailable"] is True
    assert result["trackEnableControl"]["audioTracks"] == [
        {"trackIndex": 1, "value": True},
        {"trackIndex": 2, "value": True},
    ]
    assert calls == []
    assert result["nativeMutationAttempts"] == []


def test_configure_proves_invalid_property_atomic_then_applies_gain_and_fades(
    tmp_path: Path,
) -> None:
    request, sidecar = _case(tmp_path)
    resolve, project, calls = _native(request, sidecar)
    project.timelines.append(
        _Timeline(
            "timeline-1",
            "VERA326_MUSIC_word_end_b_1",
            sidecar["music"]["expectedNative"]["events"],
        )
    )

    result = probe.run(resolve, _configure_request(request))

    music = next(
        row for row in result["readback"]["events"] if row["eventId"] == "music-bed"
    )
    assert result["atomicInvalidKey"] == {"returnedFalse": True, "unchanged": True}
    assert music["audioProperties"] == {"AudioVolumeEnabled": True, "AudioVolume": -12}
    assert music["fades"] == {"FadeIn": 6, "FadeOut": 6}
    assert result["narrationBefore"] == result["narrationAfter"]
    item = project.timelines[0].GetItemListInTrack("audio", 2)[0]
    assert len(item.set_properties_calls) == 2
    assert [call[0] for call in calls] == []


def test_configure_stops_if_invalid_property_partially_changes_gain(
    tmp_path: Path,
) -> None:
    request, sidecar = _case(tmp_path)
    resolve, project, _ = _native(request, sidecar, partial_invalid_write=True)
    project.timelines.append(
        _Timeline(
            "timeline-1",
            "VERA326_MUSIC_word_end_b_1",
            sidecar["music"]["expectedNative"]["events"],
            partial_invalid_write=True,
        )
    )

    with pytest.raises(probe.ProbeFailure, match="not atomic") as error:
        probe.run(resolve, _configure_request(request))

    item = project.timelines[0].GetItemListInTrack("audio", 2)[0]
    assert item.properties["AudioVolume"] == -24.0
    assert len(item.set_properties_calls) == 1
    assert error.value.native_mutation_attempts == ["musicItem.SetProperties"]


def test_render_starts_only_the_new_owned_job_and_restores_music_occurrence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, sidecar = _case(tmp_path)
    resolve, project, _ = _native(request, sidecar)
    timeline = _Timeline(
        "timeline-1",
        "VERA326_MUSIC_word_end_b_1",
        sidecar["music"]["expectedNative"]["events"],
    )
    project.timelines.append(timeline)
    parent = tmp_path / "renders"
    parent.mkdir()
    old_job = {
        "JobId": "old-ready-job",
        "TimelineName": "VERA326_MUSIC_duration_end_b_original",
        "IsExportVideo": False,
        "IsExportAudio": True,
        "TargetDir": str(
            tmp_path / "prior-case" / "native-renders" / "prior-operation"
        ),
        "OutputFilename": "vera326-duration-end-b-narration-prior-operation.wav",
    }
    project.render_jobs.append(old_job)
    project.render_statuses["old-ready-job"] = {
        "JobStatus": "Ready",
        "CompletionPercentage": 0,
    }
    output = parent / "word-end-b-baseline-test-1"
    request.update(
        action="render",
        operationId="word-end-b-baseline-test-1",
        timelineId=timeline.GetUniqueId(),
        timelineName=timeline.GetName(),
        includeMusic=False,
        bitDepth=16,
        renderDirectory=str(output),
    )
    monkeypatch.setattr(
        shutil,
        "disk_usage",
        lambda _path: type("DiskUsage", (), {"free": probe.MIN_FREE_BYTES})(),
    )

    result = probe.run(resolve, request)

    assert result["status"] == "rendered"
    assert result["renderJobId"] == "job-1"
    assert result["retainedReadyJobs"] == [
        {"job": old_job, "status": project.render_statuses["old-ready-job"]}
    ]
    assert project.start_render_calls == [(["job-1"], False)]
    assert result["musicClipEnabledBefore"] is True
    assert result["musicClipEnabledAfterDisable"] is False
    assert result["musicClipEnabledAfterRestore"] is True
    assert result["musicClipEnabledAfterRender"] is True
    assert timeline.GetItemListInTrack("audio", 2)[0].GetClipEnabled() is True
    assert project.render_presets == []
    assert Path(result["outputPath"]).is_file()
    assert result["renderJobStatus"]["JobStatus"] == "Complete"


def test_render_timeout_preserves_partial_evidence_without_restoring_active_clip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, sidecar = _case(tmp_path)
    resolve, project, _ = _native(request, sidecar)
    timeline = _Timeline(
        "timeline-1",
        "VERA326_MUSIC_word_end_b_1",
        sidecar["music"]["expectedNative"]["events"],
    )
    project.timelines.append(timeline)
    parent = tmp_path / "renders"
    parent.mkdir()
    output = parent / "word-end-b-render-timeout-test-1"
    request.update(
        action="render",
        operationId=output.name,
        timelineId=timeline.GetUniqueId(),
        timelineName=timeline.GetName(),
        includeMusic=False,
        bitDepth=16,
        renderDirectory=str(output),
    )
    monkeypatch.setattr(
        shutil,
        "disk_usage",
        lambda _path: type("DiskUsage", (), {"free": probe.MIN_FREE_BYTES})(),
    )
    active = {"value": False}
    start_rendering = project.StartRendering

    def start_and_stay_active(job_ids: list[str], interactive: bool) -> bool:
        started = start_rendering(job_ids, interactive)
        project.render_statuses[job_ids[0]] = {
            "JobStatus": "Rendering",
            "CompletionPercentage": 60,
        }
        active["value"] = True
        return started

    monkeypatch.setattr(project, "StartRendering", start_and_stay_active)
    monkeypatch.setattr(project, "IsRenderingInProgress", lambda: active["value"])
    ticks = iter((0.0, 0.0, 2.0))
    monkeypatch.setattr(time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(probe, "RENDER_TIMEOUT_SECONDS", 1)

    with pytest.raises(probe.ProbeFailure, match="did not finish") as error:
        probe.run(resolve, request)

    evidence = error.value.partial_evidence
    assert evidence is not None
    assert evidence["status"] == "failed"
    assert evidence["renderJobId"] == "job-1"
    assert evidence["renderDirectory"] == str(output)
    assert evidence["renderJobStatus"]["JobStatus"] == "Rendering"
    assert evidence["musicClipEnabledAfterRestore"] is None
    assert evidence["renderStillActive"] is True
    assert timeline.GetItemListInTrack("audio", 2)[0].GetClipEnabled() is False


def test_workflow_launcher_writes_partial_probe_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import runpy

    native_root = tmp_path / ".local/share/vera/issue-326-native"
    native_root.mkdir(parents=True)
    operation = "launcher-partial-evidence-test-1"
    partial = {
        "status": "failed",
        "renderJobId": "job-1",
        "renderDirectory": str(tmp_path / "render-output"),
        "renderJobStatus": {"JobStatus": "Rendering"},
        "musicClipEnabledAfterRestore": None,
        "renderStillActive": True,
    }
    attempts = ["project.StartRendering"]
    source = tmp_path / "failing_probe.py"
    source.write_text(
        "def run(resolve, request):\n"
        "    error = RuntimeError('render timeout')\n"
        f"    error.native_mutation_attempts = {attempts!r}\n"
        f"    error.partial_evidence = {partial!r}\n"
        "    raise error\n",
        encoding="utf-8",
    )
    request = {
        "operationId": operation,
        "action": "render",
        "script": str(source),
        "scriptSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    (native_root / "request.json").write_text(json.dumps(request), encoding="utf-8")
    launcher = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "issue326_workflow_launcher.py"
    )
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    runpy.run_path(str(launcher), init_globals={"resolve": object()})

    result = json.loads((native_root / f"{operation}.result.json").read_bytes())[
        "result"
    ]
    assert result["nativeMutationAttempts"] == attempts
    assert result["partialEvidence"] == partial


def test_render_refuses_before_writes_without_occurrence_enable_readback(
    tmp_path: Path,
) -> None:
    request, sidecar = _case(tmp_path)
    resolve, project, calls = _native(request, sidecar)
    timeline = _Timeline(
        "timeline-1",
        "VERA326_MUSIC_word_end_b_1",
        sidecar["music"]["expectedNative"]["events"],
    )
    music_item = timeline.GetItemListInTrack("audio", 2)[0]
    music_item.GetClipEnabled = None  # type: ignore[assignment]
    project.timelines.append(timeline)
    parent = tmp_path / "renders"
    parent.mkdir()
    output = parent / "word-end-b-baseline-1"
    request.update(
        action="render",
        operationId="word-end-b-baseline-1",
        timelineId="timeline-1",
        timelineName=timeline.GetName(),
        includeMusic=False,
        renderDirectory=str(output),
    )

    with pytest.raises(
        ValueError, match="music occurrence enable control is unavailable"
    ):
        probe.run(resolve, request)

    assert calls == []
    assert not output.exists()
