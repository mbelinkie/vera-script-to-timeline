from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import roundtrip_wi as wi


class Media:
    def __init__(self, path: Path) -> None:
        self.path = path

    def GetUniqueId(self) -> str:
        return "native-media"

    def GetClipProperty(self) -> dict[str, str]:
        return {"File Path": str(self.path), "Online Status": "Online"}


class Item:
    def __init__(self, path: Path) -> None:
        self.uid = "native-item"
        self.start, self.duration, self.source = 0, 50, 0
        self.fraction = 0.0
        self.links: list[Item] = []
        self.media = Media(path)

    def GetUniqueId(self) -> str:
        return self.uid

    def GetStart(self, fractional: bool = False) -> int | float:
        return self.start + (self.fraction if fractional else 0)

    def GetEnd(self, fractional: bool = False) -> int | float:
        return self.GetStart(fractional) + self.duration

    def GetDuration(self, fractional: bool = False) -> int | float:
        return float(self.duration) if fractional else self.duration

    def GetSourceStartFrame(self) -> int:
        return self.source

    def GetSourceEndFrame(self) -> int:
        return self.source + self.duration - 1

    def GetClipEnabled(self) -> bool:
        return True

    def GetSpeed(self) -> int:
        return 100

    def GetMediaPoolItem(self) -> Media:
        return self.media

    def GetLinkedItems(self) -> list[Item]:
        return self.links


class Timeline:
    def __init__(self, item: Item) -> None:
        self.item = item
        self.link_calls = 0

    def GetUniqueId(self) -> str:
        return "native-timeline"

    def GetName(self) -> str:
        return "VERA build build-id"

    def GetStartFrame(self) -> int:
        return 0

    def GetEndFrame(self) -> int:
        return 50

    def GetSetting(self, key: str) -> str | None:
        return {
            "timelineFrameRate": "25",
            "timelineResolutionWidth": "320",
            "timelineResolutionHeight": "180",
            "audioSampleRate": "48000",
        }.get(key)

    def GetTrackCount(self, kind: str) -> int:
        return 1 if kind == "video" else 0

    def GetTrackName(self, kind: str, index: int) -> str:
        return "Picture"

    def GetItemListInTrack(self, kind: str, index: int) -> list[Item]:
        return [self.item]

    def GetMarkers(self) -> dict[str, Any]:
        return {}

    def SetClipsLinked(self, items: list[Item], linked: bool) -> bool:
        self.link_calls += 1
        assert linked and len(items) == 2
        items[0].links = [items[1]]
        items[1].links = [items[0]]
        return True


class Project:
    def __init__(self, timeline: Timeline) -> None:
        self.timeline = timeline

    def GetUniqueId(self) -> str:
        return "native-project"

    def GetName(self) -> str:
        return "VERA Studio build build-id"

    def GetCurrentTimeline(self) -> Timeline:
        return self.timeline


class Resolve:
    def __init__(self, timeline: Timeline) -> None:
        self.project = Project(timeline)

    def GetProductName(self) -> str:
        return "DaVinci Resolve Studio"

    def GetVersion(self) -> list[int | str]:
        return [21, 1, 1, 10, ""]

    def GetProjectManager(self) -> Resolve:
        return self

    def GetCurrentProject(self) -> Project:
        return self.project


def fixture(tmp_path: Path) -> tuple[Resolve, dict[str, Any], Path]:
    package = tmp_path / "package"
    package.mkdir()
    source = package / "source.mov"
    source.write_bytes(b"explicit fake media bytes")
    item = Item(source)
    manifest = {
        "buildId": "build-id",
        "timeline": {
            "startFrame": 0,
            "durationFrames": 50,
            "frameRate": {"numerator": 25, "denominator": 1},
            "width": 320,
            "height": 180,
            "audioSampleRate": 48000,
        },
        "tracks": [
            {
                "id": "video-1",
                "kind": "video",
                "index": 1,
                "name": "Picture",
                "role": "primary",
            }
        ],
        "sources": [
            {
                "id": "source",
                "kind": "video",
                "path": "source.mov",
                "contentHash": wi.digest(source.read_bytes()),
            }
        ],
        "events": [
            {
                "id": "event",
                "sourceId": "source",
                "trackId": "video-1",
                "trackKind": "video",
                "recordRange": {"startFrame": 0, "durationFrames": 50},
                "sourceRange": {"startFrame": 0, "durationFrames": 50},
            }
        ],
        "markers": [],
    }
    return Resolve(Timeline(item)), manifest, package


def test_direct_native_reader_does_not_echo_expected_geometry(tmp_path: Path) -> None:
    resolve, manifest, package = fixture(tmp_path)
    resolve.project.timeline.item.start = 7
    observed = wi.read_native(
        resolve,
        manifest,
        package_root=package,
        version=[21, 1, 1, 10, ""],
        project_uid="native-project",
        timeline_uid="native-timeline",
    )
    assert observed["items"][0]["recordRange"]["startFrame"] == 7
    assert manifest["events"][0]["recordRange"]["startFrame"] == 0
    assert observed["items"][0]["sourcePath"] == str(package / "source.mov")


@pytest.mark.parametrize("fault", ["fraction", "setting", "source", "target"])
def test_unknown_native_facts_and_changed_target_refuse(
    tmp_path: Path, fault: str
) -> None:
    resolve, manifest, package = fixture(tmp_path)
    if fault == "fraction":
        resolve.project.timeline.item.fraction = 0.5
    elif fault == "setting":
        resolve.project.timeline.GetSetting = lambda key: None  # type: ignore[method-assign]
    elif fault == "source":
        (package / "source.mov").write_bytes(b"changed bytes")
    else:
        resolve.project.GetUniqueId = lambda: "other-project"  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        wi.read_native(
            resolve,
            copy.deepcopy(manifest),
            package_root=package,
            version=[21, 1, 1, 10, ""],
            project_uid="native-project",
            timeline_uid="native-timeline",
        )


def capture_request(
    tmp_path: Path, *, omission: bool = False
) -> tuple[Resolve, Path, dict[str, Any]]:
    resolve, manifest, package = fixture(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(wi.encoded(manifest))
    identity_path = tmp_path / "identity.json"
    identity = {
        "projectUid": "native-project",
        "timelineUid": "native-timeline",
        "occurrences": {
            "event": {"itemUid": "native-item", "mediaUid": "native-media"}
        },
    }
    identity_path.write_bytes(wi.encoded(identity))
    request = {
        "schemaVersion": "issue-144-omission-capture-request/v1"
        if omission
        else "issue-144-capture-request/v1",
        "purpose": "propose-omission" if omission else "bind-baseline",
        "binding": "sha256:" + "1" * 64,
        "snapshotId": "1" * 64,
        "evidenceLevel": "synthetic_injected",
        "nonce": "test-nonce",
        "manifestPath": str(manifest_path),
        "manifestHash": wi.file_hash(manifest_path),
        "identityPath": str(identity_path),
        "identityHash": wi.file_hash(identity_path),
        "expectedIdentity": identity,
        "packageRoot": str(package),
        "sources": {
            "python/vera_timeline_agent/roundtrip_wi.py": wi.file_hash(
                Path(wi.__file__)
            )
        },
    }
    directory = tmp_path / "captures" / "basis" / "test-nonce"
    directory.mkdir(parents=True)
    path = directory / "request.json"
    path.write_bytes(wi.encoded(request))
    kwargs = {
        "proof_root": tmp_path,
        "source_root": Path(wi.__file__).parents[2],
        "version": [21, 1, 1, 10, ""],
        "request_hash": wi.file_hash(path),
        "code_hash": wi.file_hash(Path(wi.__file__)),
    }
    return resolve, path, kwargs


def test_complete_capture_is_immutable_and_replay_reads_real_handles(
    tmp_path: Path,
) -> None:
    resolve, path, kwargs = capture_request(tmp_path)
    response = wi.capture(resolve, path, **kwargs)
    assert response["observationA"] == response["observationB"]
    assert response["observationA"]["items"][0]["eventId"] == "event"
    assert (path.parent / "response.json").read_bytes() == wi.encoded(response)
    assert wi.capture(resolve, path, **kwargs) == response
    resolve.project.timeline.item.start = 7
    with pytest.raises(RuntimeError, match="immutable"):
        wi.capture(resolve, path, **kwargs)
    assert (path.parent / "response.json").read_bytes() == wi.encoded(response)


def test_omission_capture_needs_complete_controls_and_never_invents_split_ids(
    tmp_path: Path,
) -> None:
    resolve, path, kwargs = capture_request(tmp_path, omission=True)
    resolve.project.timeline.item.uid = "actual-new-split"
    with pytest.raises(RuntimeError, match="complete control"):
        wi.capture(resolve, path, **kwargs)
    assert not (path.parent / "response.json").exists()
    assert (path.parent / "refused.json").exists()
    assert (path.parent / "raw-0.json").exists()

    def controls(_resolve: Any, _observed: dict[str, Any]) -> dict[str, Any]:
        return {
            "programControls": {"gainDb": 0, "effects": [], "limiter": False},
            "audioControls": [],
        }

    response = wi.capture(resolve, path, audio_controls=controls, **kwargs)
    item = response["observationA"]["items"][0]
    assert item["itemUid"] == "actual-new-split" and "eventId" not in item


@pytest.mark.parametrize(
    "raw", [b'{"x":1e400}', b'{"x":9007199254740992}', b'{"x":1,"x":2}']
)
def test_wi_json_refuses_unsafe_numbers_and_duplicate_keys(
    tmp_path: Path, raw: bytes
) -> None:
    path = tmp_path / "unsafe.json"
    path.write_bytes(raw)
    with pytest.raises(RuntimeError):
        wi.load(path)


def action_request(
    tmp_path: Path, action: str = "link"
) -> tuple[Resolve, Path, dict[str, Any]]:
    resolve, path, kwargs = capture_request(tmp_path)
    request = wi.load(path)
    manifest = wi.load(Path(request["manifestPath"]))
    timeline = resolve.project.timeline
    audio = Item(timeline.item.media.path)
    audio.uid = "paired-audio"
    timeline.GetTrackCount = lambda kind: 1 if kind in ("video", "audio") else 0  # type: ignore[method-assign]
    timeline.GetItemListInTrack = lambda kind, index: [  # type: ignore[method-assign]
        timeline.item if kind == "video" else audio
    ]
    manifest["tracks"].append(
        {
            "id": "audio-1",
            "kind": "audio",
            "index": 1,
            "name": "Picture",
            "role": "narration",
        }
    )
    Path(request["manifestPath"]).write_bytes(wi.encoded(manifest))
    request["manifestHash"] = wi.file_hash(Path(request["manifestPath"]))
    request.update(
        schemaVersion="issue-144-wi-action/v1",
        action=action,
        parameters={"pair": [timeline.item.uid, audio.uid]},
    )
    before = wi.read_native(
        resolve,
        manifest,
        package_root=Path(request["packageRoot"]),
        version=kwargs["version"],
        project_uid="native-project",
        timeline_uid="native-timeline",
    )
    request["expectedObservationHash"] = wi.digest(wi.encoded(before))
    if action != "link":
        request["parameters"] = {
            "outputPath": str(tmp_path / "render.wav"),
            "settings": {
                "format": "wav",
                "scope": "full-program",
                "sampleRate": 48000,
                "channels": 2,
                "sampleWidth": 2,
                "startFrame": 0,
                "durationFrames": 50,
            },
        }
    path.write_bytes(wi.encoded(request))
    kwargs["request_hash"] = wi.file_hash(path)
    return resolve, path, kwargs


def test_link_reserves_root_intent_and_replays_without_second_effect(
    tmp_path: Path,
) -> None:
    resolve, path, kwargs = action_request(tmp_path)
    result = wi.perform(resolve, path, **kwargs)
    assert result["status"] == "linked" and resolve.project.timeline.link_calls == 1
    assert list((tmp_path / "wi-effects").glob("*/intent.json"))
    assert wi.perform(resolve, path, **kwargs) == result
    assert resolve.project.timeline.link_calls == 1
    resolve.project.timeline.item.start += 1
    with pytest.raises(RuntimeError):
        wi.perform(resolve, path, **kwargs)
    assert resolve.project.timeline.link_calls == 1


def test_lost_link_response_reconciles_read_only_and_uncertain_intent_never_retries(
    tmp_path: Path,
) -> None:
    resolve, path, kwargs = action_request(tmp_path)
    timeline = resolve.project.timeline
    original = timeline.SetClipsLinked

    def lost(items: list[Item], linked: bool) -> bool:
        original(items, linked)
        raise RuntimeError("lost response")

    timeline.SetClipsLinked = lost  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="lost response"):
        wi.perform(resolve, path, **kwargs)
    assert wi.perform(resolve, path, **kwargs)["status"] == "linked"
    assert timeline.link_calls == 1
    timeline.item.links.clear()
    with pytest.raises(RuntimeError):
        wi.perform(resolve, path, **kwargs)
    assert timeline.link_calls == 1


def test_render_once_inspection_checks_exact_job_settings_and_full_stereo_pcm(
    tmp_path: Path,
) -> None:
    import wave

    resolve, path, kwargs = action_request(tmp_path, "render")
    with pytest.raises(RuntimeError, match="render boundary"):
        wi.perform(resolve, path, **kwargs)
    assert not (tmp_path / "wi-effects").exists()
    calls: list[str] = []

    def renderer(
        _resolve: Any,
        operation: str,
        parameters: dict[str, Any],
        job: dict[str, Any] | None,
    ) -> dict[str, Any]:
        calls.append(operation)
        result = {
            "jobId": "actual-job",
            "projectUid": "native-project",
            "timelineUid": "native-timeline",
            **parameters,
            "state": "queued" if operation == "queue" else "complete",
        }
        if operation == "queue":
            with wave.open(parameters["outputPath"], "wb") as stream:
                stream.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
                stream.writeframes(b"\0" * (96000 * 4))
        else:
            assert job is None or job["jobId"] == "actual-job"
        return result

    queued = wi.perform(resolve, path, render_boundary=renderer, **kwargs)
    assert queued["status"] == "queued"
    assert wi.perform(resolve, path, render_boundary=renderer, **kwargs) == queued
    assert calls == ["queue", "inspect"]
    complete = wi.perform(
        resolve, path, inspect_render=True, render_boundary=renderer, **kwargs
    )
    assert complete["status"] == "complete" and complete["sampleCount"] == 96000
    assert calls == ["queue", "inspect", "inspect"]
    assert (
        wi.perform(
            resolve, path, inspect_render=True, render_boundary=renderer, **kwargs
        )
        == complete
    )
    assert calls == ["queue", "inspect", "inspect", "inspect"]


def test_native_inspector_matches_existing_shape_and_missing_marker_does_not_fall_back(
    tmp_path: Path,
) -> None:
    resolve, manifest, package = fixture(tmp_path)
    kwargs = {
        "package_root": package,
        "version": [21, 1, 1, 10, ""],
        "project_uid": "native-project",
        "timeline_uid": "native-timeline",
    }
    result = wi.inspect_native(resolve, manifest, **kwargs)
    assert result["schemaVersion"] == "issue-144-native-readback/v1"
    assert (
        "linkedUids" not in result["items"][0] and "available" not in result["items"][0]
    )
    manifest["markers"] = [{"id": "missing-marker"}]
    with pytest.raises(RuntimeError, match="marker inventory"):
        wi.inspect_native(resolve, manifest, **kwargs)


def test_uncertain_unperformed_link_and_different_nonce_cannot_authorize_retry(
    tmp_path: Path,
) -> None:
    resolve, path, kwargs = action_request(tmp_path)
    calls: list[list[Item]] = []

    def uncertain(items: list[Item], linked: bool) -> bool:
        calls.append(items)
        return False

    resolve.project.timeline.SetClipsLinked = uncertain  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="uncertain"):
        wi.perform(resolve, path, **kwargs)
    with pytest.raises(RuntimeError, match="no retry"):
        wi.perform(resolve, path, **kwargs)
    assert len(calls) == 1
    request = wi.load(path)
    request["nonce"] = "different-nonce"
    new = path.parent.parent / request["nonce"] / "request.json"
    new.parent.mkdir()
    new.write_bytes(wi.encoded(request))
    kwargs["request_hash"] = wi.file_hash(new)
    with pytest.raises(RuntimeError, match="effect ownership"):
        wi.perform(resolve, new, **kwargs)
    assert len(calls) == 1


def test_tampered_before_state_and_stale_native_state_refuse_before_effect(
    tmp_path: Path,
) -> None:
    resolve, path, kwargs = action_request(tmp_path)
    resolve.project.timeline.item.start = 1
    with pytest.raises(RuntimeError, match="stale"):
        wi.perform(resolve, path, **kwargs)
    assert resolve.project.timeline.link_calls == 0
    assert not (tmp_path / "wi-effects").exists()
    resolve.project.timeline.item.start = 0
    wi.perform(resolve, path, **kwargs)
    intent = next((tmp_path / "wi-effects").glob("*/intent.json"))
    value = wi.load(intent)
    value["before"]["items"][0]["recordRange"]["startFrame"] += 1
    intent.write_bytes(wi.encoded(value))
    with pytest.raises(RuntimeError, match="effect ownership"):
        wi.perform(resolve, path, **kwargs)
    assert resolve.project.timeline.link_calls == 1


def test_lost_render_response_recovers_only_through_owned_job_inspection(
    tmp_path: Path,
) -> None:
    resolve, path, kwargs = action_request(tmp_path, "render")
    calls = []

    def renderer(
        _resolve: Any,
        operation: str,
        parameters: dict[str, Any],
        job: dict[str, Any] | None,
    ) -> dict[str, Any]:
        calls.append(operation)
        if operation == "queue":
            raise RuntimeError("lost queued-job response")
        return {
            "jobId": "actual-owned-job",
            "projectUid": "native-project",
            "timelineUid": "native-timeline",
            **parameters,
            "state": "rendering",
        }

    with pytest.raises(RuntimeError, match="lost queued"):
        wi.perform(resolve, path, render_boundary=renderer, **kwargs)
    with pytest.raises(RuntimeError, match="no retry"):
        wi.perform(resolve, path, render_boundary=renderer, **kwargs)
    assert calls == ["queue"]
    result = wi.perform(
        resolve, path, inspect_render=True, render_boundary=renderer, **kwargs
    )
    assert result["status"] == "needs_action" and calls == [
        "queue",
        "inspect",
        "inspect",
    ]


def test_complete_job_with_wrong_pcm_never_publishes_complete_receipt(
    tmp_path: Path,
) -> None:
    import wave

    resolve, path, kwargs = action_request(tmp_path, "render")

    def renderer(
        _resolve: Any,
        operation: str,
        parameters: dict[str, Any],
        job: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if operation == "queue":
            with wave.open(parameters["outputPath"], "wb") as stream:
                stream.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
                stream.writeframes(b"\0" * 96000 * 2)
        return {
            "jobId": "wrong-mono-output",
            "projectUid": "native-project",
            "timelineUid": "native-timeline",
            **parameters,
            "state": "queued" if operation == "queue" else "complete",
        }

    wi.perform(resolve, path, render_boundary=renderer, **kwargs)
    with pytest.raises(RuntimeError, match="stereo PCM extent"):
        wi.perform(
            resolve, path, inspect_render=True, render_boundary=renderer, **kwargs
        )
    assert not list((tmp_path / "wi-effects").glob("*/complete.json"))
