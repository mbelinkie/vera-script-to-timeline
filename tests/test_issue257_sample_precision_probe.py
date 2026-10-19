"""Focused fake-native tests for the explicitly selected issue #257 probe."""

from __future__ import annotations

import hashlib
import json
import sys
import wave
from pathlib import Path
from typing import Any, cast

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "python"))
from vera_timeline_agent import sample_precision_probe_v2 as probe


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_release(root: Path) -> None:
    entries = []
    launcher = root / "VERA Delivery v2.py"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_bytes(b"launcher")
    paths = ["VERA Delivery v2.py"]
    for name in probe.RELEASE_RUNTIME_FILES:
        path = root / "vera-delivery-v2" / "python" / "vera_timeline_agent" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"fixture:{name}".encode())
        paths.append(path.relative_to(root).as_posix())
    for name in paths:
        path = root / name
        entries.append(
            {"path": name, "sha256": _sha(path), "sizeBytes": path.stat().st_size}
        )
    manifest = {
        "schemaVersion": "vera-injected-delivery-release/v2",
        "deliveryVersion": "2",
        "sourcePins": {},
        "files": entries,
    }
    (root / "vera-delivery-v2" / "release.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )


def _environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, str, dict[str, str]]:
    pcm = b"\0\0\0" * 400400
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "original.wav"
    with wave.open(str(source), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(3)
        writer.setframerate(48000)
        writer.writeframes(pcm)
    marker_dir = tmp_path / "review"
    marker_dir.mkdir()
    marker = marker_dir / "markers.csv"
    marker.write_bytes(b"reviewed markers\n")
    marker_sha = _sha(marker)
    source_sha = _sha(source)
    pcm_sha = hashlib.sha256(pcm).hexdigest()
    review = marker_dir / "human-confirmation.json"
    review_value = {
        "schemaVersion": "issue215-c-reviewed-source/v1",
        "confirmation": (
            'I listened to Audition. I confirm the placement of "to" "this" and "cute".'
        ),
        "confirmationSource": "direct user message in Codex task test-thread",
        "frameSamples": 2002,
        "originalSourceAudioHash": f"sha256:{source_sha}",
        "sourcePcmSha256": f"sha256:{pcm_sha}",
        "reviewedMarkerFile": str(marker),
        "reviewedMarkerFileHash": f"sha256:{marker_sha}",
        "supports": probe.SUPPORTS,
    }
    review.write_text(json.dumps(review_value, sort_keys=True), encoding="utf-8")
    release = tmp_path / "release"
    release.mkdir()
    _write_release(release)
    monkeypatch.setattr(probe, "SOURCE_SHA256", source_sha)
    monkeypatch.setattr(probe, "SOURCE_PCM_SHA256", pcm_sha)
    monkeypatch.setattr(probe, "REVIEW_SHA256", _sha(review))
    monkeypatch.setattr(probe, "MARKER_SHA256", marker_sha)
    target = {
        "projectUid": "project-257-test",
        "timelineUid": "timeline-257-test",
        "projectName": "VERA257PrecisionTest",
        "timelineName": "VERA257PrecisionTest",
    }
    request = probe.prepare_probe_request(
        release_root=release,
        output=tmp_path / "evidence",
        source=source,
        review=review,
        target=target,
        producer_authorization=(
            "Explicit issue task authorization for this disposable probe."
        ),
        task_id="test-257-thread",
    )
    return request, _sha(request), target


def test_request_binds_release_original_pcm_review_and_fractional_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_path, digest, target = _environment(tmp_path, monkeypatch)
    request = probe.load_probe_request(request_path, digest)

    assert request["target"] == target
    assert request["sourceSha256"] == probe.SOURCE_SHA256
    assert request["sourcePcmSha256"] == probe.SOURCE_PCM_SHA256
    assert request["reviewSha256"] == probe.REVIEW_SHA256
    assert request["markerSha256"] == probe.MARKER_SHA256
    assert request["targetGap"] == {"startSample": 232320, "endSample": 241440}
    assert request["programmeSamples"] == 400400
    assert request["producerAuthorization"].startswith("Explicit issue task")

    source = Path(request["sourcePath"])
    source.write_bytes(source.read_bytes() + b"x")
    with pytest.raises(ValueError, match="source bytes changed"):
        probe._validate_source(source)


def test_request_pin_and_historical_expiry_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_path, digest, _ = _environment(tmp_path, monkeypatch)
    request = json.loads(request_path.read_text())
    request["issuedAt"] = "2000-01-01T00:00:00+00:00"
    request["expiresAt"] = "2000-01-01T00:30:00+00:00"
    payload = (
        json.dumps(request, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
    )
    request_path.chmod(0o600)
    request_path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()

    with pytest.raises(ValueError, match="expired"):
        probe.load_probe_request(request_path, digest)
    historical = probe.load_probe_request(request_path, digest, require_live=False)
    assert historical["requestId"] == request["requestId"]
    with pytest.raises(ValueError, match="changed"):
        probe.load_probe_request(request_path, "0" * 64, require_live=False)


def test_global_intent_is_one_use_for_target_and_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_path, digest, target = _environment(tmp_path, monkeypatch)
    request = probe.load_probe_request(request_path, digest)
    monkeypatch.setattr(probe, "PROBE_STATE_ROOT", tmp_path / "probe-state")

    intent_path, intent_sha = probe._claim_once(request, digest)
    assert intent_path.is_file()
    assert intent_sha == _sha(intent_path)
    with pytest.raises(FileExistsError):
        probe._claim_once(request, digest)
    assert target["projectUid"] in intent_path.read_text()


def test_installed_release_ignores_sibling_plugins_but_pins_own_inventory(
    tmp_path: Path,
) -> None:
    release = tmp_path / "plugins"
    release.mkdir()
    _write_release(release)
    sibling = release / "An Unrelated Plugin" / "data.json"
    sibling.parent.mkdir()
    sibling.write_text("owned by another plugin", encoding="utf-8")

    manifest_sha = probe._verify_release(release, installed=True)
    assert manifest_sha == _sha(release / "vera-delivery-v2" / "release.json")

    owned_extra = release / "vera-delivery-v2" / "untracked.json"
    owned_extra.write_text("unexpected", encoding="utf-8")
    with pytest.raises(ValueError, match="undeclared"):
        probe._verify_release(release, manifest_sha, installed=True)


def test_runner_refuses_installed_request_that_differs_from_host_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    host_request, _, _ = _environment(tmp_path, monkeypatch)
    installed_request = tmp_path / "installed-request.json"
    installed_bytes = host_request.read_bytes() + b" "
    installed_request.write_bytes(installed_bytes)
    installed_sha = hashlib.sha256(installed_bytes).hexdigest()

    with pytest.raises(ValueError, match="differs from canonical host request"):
        probe.run_sample_precision_probe(
            object(), installed_request, expected_request_sha256=installed_sha
        )


def test_snapshot_preserves_raw_frame_and_source_time_values() -> None:
    class Media:
        def GetUniqueId(self) -> str:
            return "media-uid"

    class Item:
        def GetUniqueId(self) -> str:
            return "timeline-item-uid"

        def GetMediaPoolItem(self) -> Media:
            return Media()

        def GetMediaId(self) -> str:
            return "source-uid"

        def GetStart(self, in_frames: bool = False) -> float:
            return 12.5 if in_frames else 12.5 / 23.976

        def GetEnd(self, in_frames: bool = False) -> float:
            return 19.25 if in_frames else 19.25 / 23.976

        def GetDuration(self, in_frames: bool) -> float:
            return 6.75 if in_frames else 6.75 / 23.976

        def GetSourceStartFrame(self) -> float:
            return 3.25

        def GetSourceEndFrame(self) -> float:
            return 10.0

        def GetSourceStartTime(self) -> float:
            return 3.25 / 23.976

        def GetSourceEndTime(self) -> float:
            return 11.0 / 23.976

        def GetStartTime(self) -> float:
            raise RuntimeError("not implemented by this Resolve build")

    class Timeline:
        def GetItemListInTrack(self, kind: str, index: int) -> list[Item]:
            assert (kind, index) == ("audio", 1)
            return [Item()]

    item = probe._snapshot("sample_lift", Timeline(), 1)["items"][0]
    assert item["timelineItemUid"] == "timeline-item-uid"
    assert item["sourceUID"] == "source-uid"
    assert item["mediaUID"] == "media-uid"
    getters = item["rawGetters"]
    assert getters["GetStart(True)"]["value"] == 12.5
    assert getters["GetStart(True)"]["pythonType"] == "float"
    assert getters["GetSourceStartTime"]["value"] == 3.25 / 23.976
    assert getters["GetSourceStartTime"]["arguments"] == []
    assert getters["GetStartTime"]["status"] == "ambiguous"
    assert getters["GetStartTime"]["value"] is None


class _NativeState:
    def __init__(
        self,
        request: dict[str, Any],
        *,
        fail_lift: bool = False,
        active_timeout: bool = False,
        append_end_inclusive: bool = False,
        wrong_project_on_load: bool = False,
    ) -> None:
        self.request = request
        self.project_uid = cast(str, request["target"]["projectUid"])
        self.project_name = cast(str, request["target"]["projectName"])
        self.timeline_uid = cast(str, request["target"]["timelineUid"])
        self.timeline_name = cast(str, request["target"]["timelineName"])
        self.media: list[dict[str, Any]] = []
        self.clips: list[dict[str, Any]] = []
        self.epoch = 0
        self.next_uid = 1
        self.fail_lift = fail_lift
        self.active_timeout = active_timeout
        self.append_end_inclusive = append_end_inclusive
        self.wrong_project_on_load = wrong_project_on_load
        self.append_count = 0
        self.queue: list[dict[str, Any]] = []
        self.render_settings: dict[str, Any] = {}
        self.render_format: dict[str, str] = {}
        self.render_mode = 0
        self.render_status = "Ready"


class _Media:
    def __init__(self, state: _NativeState, row: dict[str, Any]) -> None:
        self.state, self.row, self.epoch = state, row, state.epoch

    def GetUniqueId(self) -> str:
        return cast(str, self.row["uid"])

    def GetMediaId(self) -> str:
        return cast(str, self.row["uid"])

    def GetClipProperty(self) -> dict[str, str]:
        return {"Online Status": "Online", "File Path": cast(str, self.row["path"])}


class _TimelineItem:
    def __init__(self, state: _NativeState, row: dict[str, Any]) -> None:
        self.state, self.row = state, row

    def GetUniqueId(self) -> str:
        return cast(str, self.row["uid"])

    def GetMediaId(self) -> str:
        return cast(str, self.row["mediaUid"])

    def GetMediaPoolItem(self) -> _Media:
        row = next(
            media for media in self.state.media if media["uid"] == self.row["mediaUid"]
        )
        return _Media(self.state, row)

    def GetStart(self, in_frames: bool = False) -> float:
        record_frame = cast(float, self.row["recordFrame"])
        return record_frame if in_frames else record_frame / 23.976

    def GetEnd(self, in_frames: bool = False) -> float:
        end = (
            cast(float, self.row["recordFrame"])
            + cast(float, self.row["endFrame"])
            - cast(float, self.row["startFrame"])
        )
        return end if in_frames else end / 23.976

    def GetStartTime(self) -> float:
        return cast(float, self.row["recordFrame"]) / 23.976

    def GetEndTime(self) -> float:
        return (
            cast(float, self.row["recordFrame"])
            + cast(float, self.row["endFrame"])
            - cast(float, self.row["startFrame"])
            + 1
        ) / 23.976

    def GetDuration(self, in_frames: bool) -> float:
        frames = (
            cast(float, self.row["endFrame"])
            - cast(float, self.row["startFrame"])
            + int(self.state.append_end_inclusive)
        )
        return frames if in_frames else frames / 23.976

    def GetSourceStartFrame(self) -> float:
        return cast(float, self.row["startFrame"])

    def GetSourceEndFrame(self) -> float:
        return cast(float, self.row["endFrame"])

    def GetSourceStartTime(self) -> float:
        return cast(float, self.row["startFrame"]) / 23.976

    def GetSourceEndTime(self) -> float:
        return (
            cast(float, self.row["endFrame"]) + int(self.state.append_end_inclusive)
        ) / 23.976


class _TimelineMedia:
    def __init__(self, state: _NativeState) -> None:
        self.state = state

    def GetUniqueId(self) -> str:
        return "timeline-pool-uid"


class _Folder:
    def __init__(self, state: _NativeState) -> None:
        self.state = state

    def GetUniqueId(self) -> str:
        return "root-folder"

    def GetClipList(self) -> list[Any]:
        return [
            _TimelineMedia(self.state),
            *(_Media(self.state, row) for row in self.state.media),
        ]

    def GetSubFolderList(self) -> list[Any]:
        return []


class _MediaPool:
    def __init__(self, state: _NativeState) -> None:
        self.state = state

    def GetRootFolder(self) -> _Folder:
        return _Folder(self.state)

    def ImportMedia(self, paths: list[str]) -> list[_Media]:
        imported = []
        for path in paths:
            row = {"uid": f"media-{self.state.next_uid}", "path": path}
            self.state.next_uid += 1
            self.state.media.append(row)
            imported.append(_Media(self.state, row))
        return imported

    def AppendToTimeline(self, infos: list[dict[str, Any]]) -> list[_TimelineItem]:
        self.state.append_count += 1
        if self.state.fail_lift and self.state.append_count == 2:
            raise RuntimeError("fractional AppendToTimeline unavailable")
        placed = []
        for info in infos:
            media = info["mediaPoolItem"]
            if media.epoch != self.state.epoch:
                raise RuntimeError("stale media-pool handle after project reopen")
            row = {
                "uid": f"clip-{self.state.next_uid}",
                "mediaUid": media.GetUniqueId(),
                "startFrame": info["startFrame"],
                "endFrame": info["endFrame"],
                "recordFrame": info["recordFrame"],
            }
            self.state.next_uid += 1
            self.state.clips.append(row)
            placed.append(_TimelineItem(self.state, row))
        return placed


class _Timeline:
    def __init__(self, state: _NativeState) -> None:
        self.state = state

    def GetUniqueId(self) -> str:
        return self.state.timeline_uid

    def GetName(self) -> str:
        return self.state.timeline_name

    def GetSetting(self, key: str) -> str:
        return {
            "timelineFrameRate": "23.976",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
        }[key]

    def GetStartFrame(self) -> int:
        return 0

    def GetStartTimecode(self) -> str:
        return "00:00:00:00"

    def GetTrackCount(self, kind: str) -> int:
        return {"video": 1, "audio": 1, "subtitle": 0}[kind]

    def GetItemListInTrack(self, kind: str, index: int) -> list[_TimelineItem]:
        assert kind in {"audio", "video"} and index == 1
        if kind != "audio":
            return []
        return [_TimelineItem(self.state, row) for row in self.state.clips]

    def GetMarkers(self) -> dict[str, Any]:
        return {}

    def GetMediaPoolItem(self) -> _TimelineMedia:
        return _TimelineMedia(self.state)

    def DeleteClips(self, items: list[_TimelineItem], ripple: bool) -> bool:
        assert ripple is False
        ids = {item.GetUniqueId() for item in items}
        self.state.clips = [row for row in self.state.clips if row["uid"] not in ids]
        return True


class _Project:
    def __init__(self, state: _NativeState, *, project_uid: str | None = None) -> None:
        self.state = state
        self.project_uid = project_uid or state.project_uid
        self.timeline = _Timeline(state)
        self.pool = _MediaPool(state)

    def GetUniqueId(self) -> str:
        return self.project_uid

    def GetName(self) -> str:
        return self.state.project_name

    def GetCurrentTimeline(self) -> _Timeline:
        return self.timeline

    def GetMediaPool(self) -> _MediaPool:
        return self.pool

    def GetSetting(self, key: str) -> str:
        assert key == "timelineSampleRate"
        return "48000"

    def IsRenderingInProgress(self) -> bool:
        return self.state.render_status == "Rendering"

    def GetRenderJobList(self) -> list[dict[str, Any]]:
        return list(self.state.queue)

    def GetRenderFormats(self) -> dict[str, str]:
        return {"QuickTime": "mov"}

    def GetRenderCodecs(self, fmt: str) -> dict[str, str]:
        assert fmt == "mov"
        return {"Apple ProRes 422": "ProRes422"}

    def GetAudioRenderCodecs(self, fmt: str) -> dict[str, str]:
        assert fmt == "mov"
        return {"Linear PCM": "lpcm"}

    def SetCurrentRenderFormatAndCodec(self, fmt: str, codec: str) -> bool:
        self.state.render_format = {"format": fmt, "codec": codec}
        return True

    def GetCurrentRenderFormatAndCodec(self) -> dict[str, str]:
        return dict(self.state.render_format)

    def SetCurrentRenderMode(self, mode: int) -> bool:
        self.state.render_mode = mode
        return True

    def GetCurrentRenderMode(self) -> int:
        return self.state.render_mode

    def SetRenderSettings(self, settings: dict[str, Any]) -> bool:
        self.state.render_settings = dict(settings)
        return True

    def GetRenderSettings(self) -> dict[str, Any]:
        return dict(self.state.render_settings)

    def AddRenderJob(self) -> str:
        settings = self.state.render_settings
        job_id = "job-257"
        self.state.queue.append(
            {
                "JobId": job_id,
                "TargetDir": settings["TargetDir"],
                "OutputFilename": settings["CustomName"] + ".mov",
                "RenderMode": "Single clip",
                "IsExportVideo": True,
                "IsExportAudio": True,
                "AudioBitDepth": 24,
                "AudioSampleRate": 48000,
                "AudioChannels": 2,
                "FrameRate": 23.976,
                "MarkIn": 0,
                "MarkOut": 199,
                "FormatWidth": 1920,
                "FormatHeight": 1080,
                "VideoCodec": "ProRes422",
                "AudioCodec": "lpcm",
                "VideoFormat": "mov",
            }
        )
        self.state.render_status = "Ready"
        return job_id

    def GetRenderJobStatus(self, job_id: str) -> dict[str, Any]:
        assert job_id == "job-257"
        return {"JobStatus": self.state.render_status, "CompletionPercentage": 100}

    def StartRendering(self, job_ids: list[str]) -> bool:
        assert job_ids == ["job-257"]
        settings = self.state.render_settings
        output = Path(settings["TargetDir"]) / (settings["CustomName"] + ".mov")
        output.write_bytes(b"fake native mov payload")
        self.state.render_status = (
            "Rendering" if self.state.active_timeout else "Complete"
        )
        return True


class _Manager:
    def __init__(self, state: _NativeState) -> None:
        self.state = state
        self.current: Any = _Project(state)
        self.loaded_names: list[str] = []
        self.saw_nonempty_current_at_load: list[bool] = []

    def GetCurrentProject(self) -> Any:
        return self.current

    def SaveProject(self) -> bool:
        return self.current is not None

    def CloseProject(self, project: _Project) -> bool:
        assert project is self.current
        # Resolve may expose a placeholder/default project wrapper after close.
        self.current = object()
        return True

    def LoadProject(self, name: str) -> _Project:
        assert name == self.state.project_name
        self.loaded_names.append(name)
        self.saw_nonempty_current_at_load.append(self.current is not None)
        self.state.epoch += 1
        self.current = _Project(
            self.state,
            project_uid=(
                "unexpected-project-uid"
                if self.state.wrong_project_on_load
                else self.state.project_uid
            ),
        )
        return cast(_Project, self.current)


class _Resolve:
    def __init__(self, state: _NativeState) -> None:
        self.manager = _Manager(state)

    def GetProductName(self) -> str:
        return "DaVinci Resolve Studio"

    def GetVersion(self) -> list[Any]:
        return [21, 1, 1, 10, ""]

    def GetProjectManager(self) -> _Manager:
        return self.manager


@pytest.mark.parametrize(
    ("fail_lift", "append_end_inclusive"),
    [(False, True), (True, True), (False, False)],
)
def test_runner_journals_fractional_lift_and_retains_partial_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fail_lift: bool,
    append_end_inclusive: bool,
) -> None:
    request_path, request_sha, _ = _environment(tmp_path, monkeypatch)
    request = probe.load_probe_request(request_path, request_sha)
    release_sha = request["releaseSha256"]
    monkeypatch.setattr(
        probe,
        "_verify_release",
        lambda _root, expected=None, **_kw: expected or release_sha,
    )
    monkeypatch.setattr(probe, "PROBE_STATE_ROOT", tmp_path / "probe-state")
    state = _NativeState(
        request,
        fail_lift=fail_lift,
        append_end_inclusive=append_end_inclusive,
    )

    resolve = _Resolve(state)
    result_path = probe.run_sample_precision_probe(
        resolve, request_path, expected_request_sha256=request_sha
    )
    result = json.loads(result_path.read_text())
    adjustment = -1 if append_end_inclusive else 0
    expected_duration = 101 if append_end_inclusive else 100
    assert result["requestPath"] == str(request_path)
    assert result["hostRequestPath"] == str(request_path)
    assert result["requestSha256"] == request_sha
    assert result["hostRequestSha256"] == request_sha
    assert result["construction"]["calibration"] == {
        "inputEndFrame": 100,
        "observedDurationFrames": expected_duration,
        "appendEndFrameAdjustment": adjustment,
    }
    assert result["calibration"] == result["construction"]["calibration"]
    assert resolve.manager.loaded_names == [request["target"]["projectName"]] * (
        1 if fail_lift else 2
    )
    assert resolve.manager.saw_nonempty_current_at_load == [True] * (
        1 if fail_lift else 2
    )
    baseline_effect = next(
        row for row in result["effects"] if row["stage"] == "append_baseline"
    )
    assert baseline_effect["arguments"][0][0]["endFrame"] == 100.0
    assert result["status"] == (
        "ambiguous" if fail_lift else "rendered_for_pcm_verification"
    )
    expected_stages = [
        "baseline",
        "baseline_after_reopen",
    ]
    if not fail_lift:
        expected_stages.extend(["sample_lift", "sample_lift_after_reopen"])
    assert [row["stage"] for row in result["observations"]] == expected_stages
    delete_effect = next(
        row
        for row in result["effects"]
        if row["stage"] == "delete_own_baseline_nonripple"
    )
    assert delete_effect["method"] == "Timeline.DeleteClips"
    assert delete_effect["arguments"]["rippleDelete"] is False
    lift_effect = next(
        row
        for row in result["effects"]
        if row["stage"] == "append_fractional_survivors"
    )
    assert lift_effect["status"] == ("ambiguous" if fail_lift else "returned")
    assert lift_effect["journalPath"] and Path(lift_effect["journalPath"]).is_file()
    lift_infos = lift_effect["arguments"][0]["infos"]
    assert lift_infos[0]["startFrame"] == 0.0
    assert lift_infos[0]["endFrame"] == 232320 / 2002 + adjustment
    assert lift_infos[1]["startFrame"] == 241440 / 2002
    assert lift_infos[1]["endFrame"] == 400400 / 2002 + adjustment
    assert (
        result["observations"][1]["items"][0]["rawGetters"]["GetSourceStartTime"][
            "status"
        ]
        == "supported"
    )
    if fail_lift:
        assert result["render"]["status"] == "incomplete"
        assert result["failure"]["message"] == "fractional AppendToTimeline unavailable"
        assert not (Path(request["outputDir"]) / "renders").exists()
    else:
        assert result["render"]["status"] == "rendered_for_pcm_verification"
        assert result["render"]["jobStatus"]["JobStatus"] == "Complete"
        assert _sha(Path(result["render"]["outputPath"])) == result["render"]["sha256"]
        assert (
            result["render"]["postRenderObservation"]["items"]
            == result["observations"][-1]["items"]
        )


def test_reopen_loads_authorized_name_then_rejects_changed_project_uid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_path, request_sha, _ = _environment(tmp_path, monkeypatch)
    request = probe.load_probe_request(request_path, request_sha)
    release_sha = request["releaseSha256"]
    monkeypatch.setattr(
        probe,
        "_verify_release",
        lambda _root, expected=None, **_kw: expected or release_sha,
    )
    monkeypatch.setattr(probe, "PROBE_STATE_ROOT", tmp_path / "probe-state")
    state = _NativeState(request, wrong_project_on_load=True)
    resolve = _Resolve(state)

    result_path = probe.run_sample_precision_probe(
        resolve, request_path, expected_request_sha256=request_sha
    )
    result = json.loads(result_path.read_text())

    assert result["status"] == "ambiguous"
    assert result["failure"]["message"] == "reopened target identity differs"
    assert resolve.manager.loaded_names == [request["target"]["projectName"]]
    assert resolve.manager.saw_nonempty_current_at_load == [True]
    assert not any(
        effect["stage"] == "delete_own_baseline_nonripple"
        for effect in result["effects"]
    )


def test_render_timeout_retains_exact_active_job_without_claiming_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_path, request_sha, _ = _environment(tmp_path, monkeypatch)
    request = probe.load_probe_request(request_path, request_sha)
    release_sha = request["releaseSha256"]
    monkeypatch.setattr(
        probe,
        "_verify_release",
        lambda _root, expected=None, **_kw: expected or release_sha,
    )
    monkeypatch.setattr(probe, "RENDER_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(probe, "PROBE_STATE_ROOT", tmp_path / "probe-state")
    state = _NativeState(request, active_timeout=True)

    result_path = probe.run_sample_precision_probe(
        _Resolve(state), request_path, expected_request_sha256=request_sha
    )
    result = json.loads(result_path.read_text())
    assert result["status"] == "ambiguous"
    assert result["render"]["status"] == "active_timeout_retained"
    assert result["render"]["jobId"] == "job-257"
    assert result["render"]["jobStatus"]["JobStatus"] == "Rendering"


def test_queue_readback_remains_authoritative_without_project_settings_getter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_path, request_sha, _ = _environment(tmp_path, monkeypatch)
    request = probe.load_probe_request(request_path, request_sha)
    release_sha = request["releaseSha256"]
    monkeypatch.setattr(
        probe,
        "_verify_release",
        lambda _root, expected=None, **_kw: expected or release_sha,
    )
    monkeypatch.setattr(_Project, "GetRenderSettings", None)
    monkeypatch.setattr(probe, "PROBE_STATE_ROOT", tmp_path / "probe-state")
    result_path = probe.run_sample_precision_probe(
        _Resolve(_NativeState(request)),
        request_path,
        expected_request_sha256=request_sha,
    )
    result = json.loads(result_path.read_text())
    assert result["status"] == "rendered_for_pcm_verification"
    assert result["render"]["settings"]["readback"] == {
        "status": "unsupported",
        "method": "Project.GetRenderSettings",
    }
    assert result["render"]["job"]["AudioChannels"] == 2
    assert result["render"]["job"]["FrameRate"] == 23.976
