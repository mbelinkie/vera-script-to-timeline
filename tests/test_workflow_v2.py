from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from issue177_package_fixture import make_package_case
from vera_timeline_agent import workflow_v2
from vera_timeline_agent.studio_spike import (
    StudioSpikeError,
    _still_source_frame_duration,
)
from vera_timeline_agent.v2_package import verify_v2_package
from vera_timeline_agent.workflow_package import SOURCE_PINS


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_package(
    tmp_path: Path,
    *,
    fractional: bool = False,
    frame_rate: tuple[int, int] | None = None,
    view_frame_rate: tuple[int, int] | None = None,
    return_frame: int | None = None,
    source_audio: bool = False,
    source_audio_gain: int | float = -18,
    source_audio_policy: str | None = None,
    source_audio_range_duration: int | None = None,
    picture_treatment: dict[str, Any] | None = None,
    marker_track_kind: str = "video",
    marker_track_index: int = 2,
    visual_event_count: int = 1,
) -> tuple[Path, str, dict[str, Any]]:
    root = tmp_path / "package"
    build_id, manifest_id, report_id, document_id = (
        str(uuid.uuid4()) for _ in range(4)
    )
    event_id, marker_id, source_id = (str(uuid.uuid4()) for _ in range(3))
    build = root / "Builds" / build_id
    source_bytes = b"synthetic media bytes"
    source_path = root / "Media" / "Resolved" / f"{source_id}.mov"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(source_bytes)
    source_hash = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    audio_source_id = str(uuid.uuid4())
    audio_path = root / "Media" / "Narration" / f"{audio_source_id}.wav"
    if source_audio:
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"synthetic audio sidecar")
        audio_hash = "sha256:" + hashlib.sha256(audio_path.read_bytes()).hexdigest()

    numerator, denominator = frame_rate or ((24000, 1001) if fractional else (25, 1))
    rate = {"numerator": numerator, "denominator": denominator}
    timeline = {
        "frameRate": rate,
        "width": 1920,
        "height": 1080,
        "audioSampleRate": 48000,
        "startFrame": 0,
        "durationFrames": 10 * visual_event_count,
    }
    tracks = [
        {"id": "video-root", "kind": "video", "index": 1, "name": "Root"},
        {
            "id": "markers",
            "kind": marker_track_kind,
            "index": marker_track_index,
            "name": "Markers",
        },
    ]
    if source_audio:
        tracks.append(
            {"id": "source-audio", "kind": "audio", "index": 1, "name": "Source Audio"}
        )
    composition = {
        "topology": "primary_root_child_overlay",
        "primaryRootTrackId": "video-root",
        "childTrackIds": [],
        "overlayTrackIds": [],
        "rootContinuous": True,
        "returns": (
            []
            if return_frame is None
            else [
                {
                    "returnSlotId": str(uuid.uuid4()),
                    "rootEventId": event_id,
                    "recordFrame": return_frame,
                    "emitsNewSourceEvent": False,
                }
            ]
        ),
    }
    visual = {
        "eventId": event_id,
        "kind": "primary_visual",
        "trackId": "video-root",
        "trackRole": "primary_root",
        "recordRange": {"startFrame": 0, "endFrame": 10},
        "sourceRange": {"startFrame": 0, "endFrame": 10},
        "sourceTimeMapping": None,
        "preparationBindingHash": None,
        "audio": None,
        "provenance": {"sourceId": source_id, "deliveredSourceHash": source_hash},
    }
    if picture_treatment is not None:
        visual["pictureTreatment"] = picture_treatment
    marker = {
        "eventId": marker_id,
        "kind": "script_marker",
        "trackId": "markers",
        "trackRole": "marker",
        "recordRange": {"startFrame": 5, "endFrame": 6},
        "sourceRange": None,
        "sourceTimeMapping": None,
        "preparationBindingHash": None,
        "audio": None,
        "marker": {
            "supportingItemId": str(uuid.uuid4()),
            "text": "PRIVATE marker text",
        },
        "provenance": {"sourceId": None, "documentId": document_id},
    }
    events: list[dict[str, Any]] = [visual, marker]
    view_source_kind = (
        "still"
        if picture_treatment and picture_treatment.get("kind") == "still_frame"
        else "video"
    )
    view_sources: list[dict[str, Any]] = [
        {
            "id": source_id,
            "kind": view_source_kind,
            "path": f"Media/Resolved/{source_id}.mov",
            "contentHash": source_hash,
        }
    ]
    view_events: list[dict[str, Any]] = [
        {
            "id": event_id,
            "kind": "primary_visual",
            "sourceId": source_id,
            "trackId": "video-root",
            "trackKind": "video",
            "recordRange": {"startFrame": 0, "durationFrames": 10},
            "sourceRange": {"startFrame": 0, "durationFrames": 10},
            "v2Event": visual,
            "gainDb": None,
            "pictureTreatment": visual.get("pictureTreatment"),
        }
    ]
    if source_audio:
        audio_event = {
            "eventId": audio_source_id,
            "kind": "source_audio",
            "trackId": "source-audio",
            "trackRole": "source_audio",
            "recordRange": {"startFrame": 0, "endFrame": 10},
            "sourceRange": None,
            "sourceTimeMapping": None,
            "preparationBindingHash": "sha256:" + "1" * 64,
            "audio": {
                "audioPolicy": source_audio_policy
                or ("quiet" if source_audio_gain == -18 else "full"),
                "levelPolicyVersion": "source-audio-level/v1",
                "gainDb": source_audio_gain,
                "streamIndex": 0,
                "audioHash": audio_hash,
                "sampleRange": {"startFrame": 0, "endFrame": 4800},
            },
            "provenance": {"sourceId": source_id, "deliveredSourceHash": source_hash},
        }
        events.insert(1, audio_event)
        view_sources.append(
            {
                "id": audio_source_id,
                "kind": "audio",
                "path": f"Media/Narration/{audio_source_id}.wav",
                "contentHash": audio_hash,
            }
        )
        view_events.append(
            {
                "id": audio_source_id,
                "kind": "source_audio",
                "sourceId": audio_source_id,
                "trackId": "source-audio",
                "trackKind": "audio",
                "recordRange": {"startFrame": 0, "durationFrames": 10},
                "sourceRange": {
                    "startFrame": 0,
                    "durationFrames": source_audio_range_duration or 10,
                },
                "v2Event": audio_event,
                "gainDb": source_audio_gain,
                "pictureTreatment": None,
            }
        )
    for index in range(1, visual_event_count):
        next_visual = deepcopy(visual)
        next_visual["eventId"] = str(uuid.uuid4())
        next_visual["recordRange"] = {
            "startFrame": index * 10,
            "endFrame": (index + 1) * 10,
        }
        events.insert(-1, next_visual)
        next_view_event = deepcopy(view_events[0])
        next_view_event["id"] = next_visual["eventId"]
        next_view_event["recordRange"]["startFrame"] = index * 10
        next_view_event["v2Event"] = next_visual
        view_events.append(next_view_event)
    manifest = {
        "schemaVersion": "timeline-manifest/v2",
        "id": manifest_id,
        "buildId": build_id,
        "document": {"documentId": document_id},
        "timeline": timeline,
        "tracks": tracks,
        "sources": [{"id": source_id, "deliveredHash": source_hash}],
        "events": events,
        "composition": composition,
        "preparationBindings": [],
    }
    view_timeline = dict(timeline)
    if view_frame_rate is not None:
        view_timeline["frameRate"] = {
            "numerator": view_frame_rate[0],
            "denominator": view_frame_rate[1],
        }
    view: dict[str, Any] = {
        "schemaVersion": "resolve-native-view/v2",
        "timeline": view_timeline,
        "tracks": tracks,
        "sources": view_sources,
        "events": view_events,
        "markers": [
            {
                "id": marker_id,
                "frame": 5,
                "color": "YELLOW",
                "name": "Script note",
                "note": "PRIVATE marker text",
                "provenance": marker,
            }
        ],
        "composition": composition,
    }
    report = {
        "schemaVersion": "build-report/v2",
        "id": report_id,
        "buildId": build_id,
        "status": "ready",
        "document": {"documentId": document_id},
    }
    document = {"schemaVersion": "script-document/v2", "id": document_id}
    dependencies = {
        "schemaVersion": "compiler-dependencies/v2",
        "build": {
            "buildId": build_id,
            "manifestId": manifest_id,
            "reportId": report_id,
        },
    }
    _write(build / "timeline-manifest.json", manifest)
    _write(build / "build-report.json", report)
    _write(build / "script-document.json", document)
    _write(build / "compiler-dependencies.json", dependencies)
    _write(build / "delivery-view.json", view)
    (build / "timeline.otio").write_bytes(b"hash-bound OTIO placeholder; never parsed")
    receipt_path = build / "package-verification.json"
    package_files = sorted(path for path in root.rglob("*") if path.is_file())
    file_hashes = {
        path.relative_to(root).as_posix(): "sha256:" + _hash(path)
        for path in package_files
    }
    _write(
        receipt_path,
        {
            "schemaVersion": "v2-package-verification/v1",
            "status": "ready_to_import",
            "buildId": build_id,
            "manifestId": manifest_id,
            "reportId": report_id,
            "documentId": document_id,
            "eventCount": len(view_events),
            "manifestEventCount": len(events),
            "markerCount": len(view["markers"]),
            "mediaCount": len(view_sources),
            "fileHashes": file_hashes,
            "sourceHashes": {
                source["id"]: source["contentHash"] for source in view_sources
            },
            "preparations": {},
        },
    )
    files = {name: _hash(build / name) for name in workflow_v2.BUILD_FILE_NAMES}
    package_files = sorted(path for path in root.rglob("*") if path.is_file())
    inventory = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _hash(path),
            "sizeBytes": path.stat().st_size,
        }
        for path in package_files
    ]
    project_name = f"VERA Delivery {build_id} 012345abcdef"
    attestation_value = {
        "schemaVersion": "vera-injected-delivery-attestation/v2",
        "status": "ready_to_import",
        "sourcePins": SOURCE_PINS,
        "packageDir": str(root),
        "buildId": build_id,
        "projectName": project_name,
        "timelineName": project_name,
        "verifiedAt": datetime.now(UTC).isoformat(),
        "verifier": {
            "implementation": "CPython",
            "pythonVersion": "3.12.14",
            "sourceHashes": {"python/vera_timeline_agent/workflow_v2.py": "f" * 64},
        },
        "verification": {
            "eventCount": len(view_events),
            "markerCount": len(view["markers"]),
            "mediaCount": len(view_sources),
        },
        "packageFiles": inventory,
        "files": files,
    }
    attestation_path = tmp_path / "attestation.json"
    _write(attestation_path, attestation_value)
    return attestation_path, _hash(attestation_path), attestation_value


@dataclass(frozen=True)
class _Connected:
    edition: str = "studio"
    scripting_available: bool = True
    suffix: str = ""
    version: str = "21.1.1"
    build: str = "10"


class _FakeAdapter:
    def __init__(
        self,
        *,
        fail_on: str | None = None,
        mutate: Any = None,
        verification_discrepancies: tuple[str, ...] = (),
    ) -> None:
        self.calls: list[str] = []
        self.fail_on = fail_on
        self.mutate = mutate
        self.mutations = 0
        self.verification_discrepancies = verification_discrepancies

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if self.mutate == name:
            self.mutations += 1
        if self.fail_on == name:
            raise RuntimeError(name)

    def connected_facts(self) -> Any:
        self._call("connected_facts")
        return _Connected()

    def probe(self, settings: Any) -> tuple[str, ...]:
        self.settings = dict(settings)
        self._call("probe")
        return ()

    def check_project_name_available(self, _name: str) -> None:
        self._call("collision")

    def assert_current_target(self) -> None:
        self._call("target")

    def create_project(self, _name: str) -> None:
        self._call("create_project")
        self.assert_current_target()

    def configure_project(self, _settings: Any) -> None:
        self._call("configure_project")

    def create_bin(self, _name: str) -> None:
        self._call("create_bin")

    def import_media(self, _sources: Any) -> None:
        self._call("import_media")

    def create_timeline(self, _name: str) -> None:
        self._call("create_timeline")

    def configure_tracks(self, _tracks: Any) -> None:
        self._call("configure_tracks")

    def place_event(self, _event: Any) -> None:
        self._call("place_event")

    def import_verified_otio(self, _path: Path, _view: Any, _name: str) -> None:
        self._call("import_verified_otio")

    def add_v2_marker(self, _marker: Any) -> None:
        self._call("add_marker")

    def save_close_reopen(self, _name: str) -> None:
        self._call("save_close_reopen")

    def verify(self, _view: Any) -> tuple[str, ...]:
        self._call("verify")
        return self.verification_discrepancies


def _existing_project_fixture() -> tuple[Any, Any, Any]:
    """A project with two old timelines; SDK objects change on reopen."""

    class Timeline:
        def __init__(self, uid: str, name: str) -> None:
            self.uid, self.name = uid, name

        def GetUniqueId(self) -> str:
            return self.uid

        def GetName(self) -> str:
            return self.name

        def SetStartTimecode(self, _value: str) -> bool:
            return True

        def GetStartFrame(self) -> int:
            return 0

    class Folder:
        def __init__(self) -> None:
            self.names: list[str] = []

        def GetUniqueId(self) -> str:
            return "root-bin"

        def GetSubFolderList(self) -> list[Any]:
            return [
                SimpleNamespace(GetName=lambda name=name: name) for name in self.names
            ]

    class Pool:
        def __init__(self) -> None:
            self.creates = 0
            self.root = Folder()
            self.current_folder: Any = self.root

        def GetRootFolder(self) -> Folder:
            return self.root

        def GetCurrentFolder(self) -> Any:
            return self.current_folder

        def SetCurrentFolder(self, folder: Any) -> bool:
            self.current_folder = folder
            return True

        def AddSubFolder(self, parent: Any, name: str) -> Any:
            if parent is self.root:
                self.root.names.append(name)
            return SimpleNamespace(GetName=lambda: name, GetUniqueId=lambda: name)

        def CreateEmptyTimeline(self, name: str) -> Timeline:
            self.creates += 1
            created = Timeline(f"new-{self.creates}", name)
            project.timelines.append(created)
            project.current = created
            return created

    class Project:
        def __init__(self) -> None:
            self.timelines = [
                Timeline("old-1", "Prior A"),
                Timeline("old-2", "Prior B"),
            ]
            self.current = self.timelines[0]
            self.pool = Pool()
            self.settings = {
                "timelineFrameRate": "25.000",
                "timelineResolutionWidth": "1920",
                "timelineResolutionHeight": "1080",
                "timelineSampleRate": "48000",
            }

        def GetUniqueId(self) -> str:
            return "existing-project-uid"

        def GetName(self) -> str:
            return "Review Project"

        def GetSetting(self, key: str) -> str:
            return self.settings[key]

        def GetTimelineCount(self) -> int:
            return len(self.timelines)

        def GetTimelineByIndex(self, index: int) -> Timeline:
            return self.timelines[index - 1]

        def GetCurrentTimeline(self) -> Timeline:
            return self.current

        def SetCurrentTimeline(self, candidate: Timeline) -> bool:
            if candidate not in self.timelines:
                return False
            self.current = candidate
            return True

        def GetMediaPool(self) -> Pool:
            return self.pool

    class Manager:
        def __init__(self) -> None:
            self.names = ["Review Project"]
            self.saves = 0
            self.closes = 0
            self.loads = 0

        def GetProjectListInCurrentFolder(self) -> list[str]:
            return self.names

        def GetCurrentProject(self) -> Project:
            return project

        def SaveProject(self) -> bool:
            self.saves += 1
            return True

        def CloseProject(self, candidate: Project) -> bool:
            assert candidate is project
            self.closes += 1
            return True

        def LoadProject(self, name: str) -> Project:
            assert name == "Review Project"
            self.loads += 1
            project.timelines = [Timeline(t.uid, t.name) for t in project.timelines]
            project.current = project.timelines[0]
            return project

    project = Project()
    manager = Manager()
    adapter = workflow_v2.PublicResolveAdapter(object())
    adapter.manager = manager
    return adapter, project, manager


def _existing_settings() -> dict[str, str]:
    return {
        "timelineFrameRate": "25",
        "timelineResolutionWidth": "1920",
        "timelineResolutionHeight": "1080",
        "timelineSampleRate": "48000",
    }


def test_existing_project_preserves_two_old_uids_and_rebinds_new_uid() -> None:
    adapter, project, manager = _existing_project_fixture()
    old = adapter._timeline_inventory(project)
    adapter.preflight_existing_project(
        "Review Project", _existing_settings(), "VERA New"
    )
    assert adapter.expected_project_id == "existing-project-uid"
    assert adapter.previous_timelines == old
    assert project.pool.creates == 0 and manager.saves == 0
    # Unlike a fresh project, existing mode starts from any selected media bin
    # and uses a uniquely named new root/bin; no prior bin gets changed.
    project.pool.current_folder = SimpleNamespace(GetUniqueId=lambda: "old-bin")
    adapter.create_bin("VERA VERA New")
    adapter.create_bin("Package Media")
    assert project.pool.root.names == ["VERA VERA New"]
    assert adapter.created_bins == ["VERA VERA New", "Package Media"]
    adapter.create_timeline("VERA New")
    created = adapter.timeline
    adapter.save_close_reopen("Review Project")
    assert adapter.timeline is not created  # SDK object rebound, not stale reference
    assert adapter.timeline.GetUniqueId() == "new-1"
    assert project.GetCurrentTimeline() is adapter.timeline
    assert adapter._timeline_inventory(project) == (*old, ("new-1", "VERA New"))
    assert manager.saves == manager.loads == manager.closes == 1

    # A second invocation selects a distinct timeline and leaves the first intact.
    again = workflow_v2.PublicResolveAdapter(object())
    again.manager = manager
    again.preflight_existing_project(
        "Review Project", _existing_settings(), "VERA Second"
    )
    again.create_timeline("VERA Second")
    again.save_close_reopen("Review Project")
    assert again._timeline_inventory(project) == (
        *old,
        ("new-1", "VERA New"),
        ("new-2", "VERA Second"),
    )


@pytest.mark.parametrize(
    "failure", ["missing", "ambiguous", "wrong-rate", "name", "bin", "switched"]
)
def test_existing_preflight_refuses_without_native_writes(failure: str) -> None:
    adapter, project, manager = _existing_project_fixture()
    target_name = "VERA New"
    if failure == "missing":
        manager.names = []
    if failure == "ambiguous":
        manager.names = ["Review Project", "Review Project"]
    if failure == "wrong-rate":
        project.settings["timelineFrameRate"] = "24"
    if failure == "name":
        target_name = "Prior A"
    if failure == "bin":
        project.pool.root.names.append("VERA VERA New")
    if failure == "switched":
        project.GetName = lambda: "Another Project"
    with pytest.raises(ValueError):
        adapter.preflight_existing_project(
            "Review Project", _existing_settings(), target_name
        )
    assert project.GetTimelineCount() == 2
    assert project.pool.creates == manager.saves == manager.loads == 0


def test_existing_project_switch_and_reopened_uid_drift_fail_closed() -> None:
    adapter, project, manager = _existing_project_fixture()
    adapter.preflight_existing_project(
        "Review Project", _existing_settings(), "VERA New"
    )
    adapter.create_timeline("VERA New")
    project.current = project.timelines[0]
    with pytest.raises(ValueError, match="current timeline changed"):
        adapter.assert_current_target()
    assert manager.saves == 0
    project.current = project.timelines[-1]
    original_load = manager.LoadProject

    def changed_uid(name: str) -> Any:
        reopened = original_load(name)
        reopened.timelines[-1].uid = "switched-uid"
        return reopened

    manager.LoadProject = changed_uid
    with pytest.raises(
        ValueError, match="reopened project changed timeline identities"
    ):
        adapter.save_close_reopen("Review Project")
    assert manager.saves == manager.loads == manager.closes == 1


def test_existing_reopen_refuses_old_timeline_uid_drift() -> None:
    adapter, project, manager = _existing_project_fixture()
    adapter.preflight_existing_project(
        "Review Project", _existing_settings(), "VERA New"
    )
    adapter.create_timeline("VERA New")
    original_load = manager.LoadProject

    def changed_prior_uid(name: str) -> Any:
        reopened = original_load(name)
        reopened.timelines[0].uid = "altered-prior-uid"
        return reopened

    manager.LoadProject = changed_prior_uid
    with pytest.raises(
        ValueError, match="reopened project changed timeline identities"
    ):
        adapter.save_close_reopen("Review Project")
    assert project.timelines[-1].GetUniqueId() == "new-1"
    assert manager.saves == manager.loads == manager.closes == 1


def test_existing_workflow_never_creates_project_or_changes_its_settings(
    tmp_path: Path,
) -> None:
    attestation, digest, details = _make_package(tmp_path)

    class ExistingAdapter(_FakeAdapter):
        def preflight_existing_project(
            self, project: str, settings: Any, name: str
        ) -> None:
            assert project == "Review Project"
            assert settings["timelineFrameRate"] == "25"
            assert name == details["timelineName"]
            self._call("existing_preflight")

    adapter = ExistingAdapter()
    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="Local",
        existing_project="Review Project",
        adapter_factory=lambda _resolve: adapter,
    )
    assert result["status"] == "verified"
    assert result["projectName"] == "Review Project"
    assert "create_project" not in adapter.calls
    assert "configure_project" not in adapter.calls
    assert "collision" not in adapter.calls
    assert "existing_preflight" in adapter.calls
    assert adapter.calls.index("existing_preflight") < adapter.calls.index("create_bin")
    assert adapter.calls.index("save_close_reopen") < adapter.calls.index("verify")


def test_existing_native_whole_otio_refuses_before_adapter_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attestation, digest, _ = _make_package(tmp_path)
    monkeypatch.setattr(workflow_v2, "_requires_native_otio", lambda _view: True)
    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="Local",
        existing_project="Review Project",
        adapter_factory=lambda _resolve: pytest.fail("unsafe OTIO cannot connect"),
    )
    assert result["status"] == "stopped_safely"
    assert result["partialTargetRetained"] is False
    assert result["failureStage"] == "package validation"
    assert "unsafe inside an existing project" in result["refusal"]


def test_existing_settings_refusal_is_sanitized_and_before_writes(
    tmp_path: Path,
) -> None:
    attestation, digest, _ = _make_package(tmp_path)

    class Incompatible(_FakeAdapter):
        def preflight_existing_project(self, *_args: Any) -> None:
            raise ValueError("existing project rate or settings differ from script")

    adapter = Incompatible()
    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="Local",
        existing_project="Review Project",
        adapter_factory=lambda _resolve: adapter,
    )
    assert result["status"] == "stopped_safely"
    assert result["refusal"] == "existing project rate or settings differ from script"
    assert adapter.calls == ["connected_facts", "probe"]


@pytest.mark.parametrize(
    ("framing", "scaling", "accepted"),
    [
        ("contain", 2, True),
        ("contain", 3, False),
        ("cover", 3, True),
        ("cover", 1, False),
    ],
)
def test_issue336_real_adapter_imports_one_otio_without_append_or_duplicate_stamps(
    tmp_path: Path,
    framing: str,
    scaling: int,
    accepted: bool,
) -> None:
    """Model public Resolve import APIs, not native pixel output."""
    picture = {
        "kind": "still_frame",
        "framingPolicy": framing,
        "imageMotion": {"mode": "none"},
    }
    attestation, digest, _ = _make_package(tmp_path, picture_treatment=picture)
    package = workflow_v2.load_verified_package_v2(attestation, digest)
    source = package.view["sources"][0]
    source_path = package.root / source["path"]
    counts = {"import": 0, "append": 0, "delete_marker": 0, "stamped": 0}

    class Media:
        def GetMediaId(self) -> str:
            return "exact-source-id"

        def GetClipProperty(self, _name: str) -> str:
            return str(source_path)

    media = Media()

    class Clip:
        def GetStart(self, _relative: bool) -> int:
            return 0

        def GetDuration(self, _relative: bool) -> int:
            return 10

        def GetMediaPoolItem(self) -> Media:
            return media

        def GetProperties(self) -> dict[str, Any]:
            return {"DynamicZoomEnabled": False, "Scaling": scaling}

        def AddMarker(self, *_args: Any) -> bool:
            counts["stamped"] += 1
            return True

    clip = Clip()

    class Timeline:
        def __init__(self) -> None:
            self.markers: dict[int, Any] = {5: {"from_native_otio": True}}

        def GetName(self) -> str:
            return "VERA Test"

        def GetUniqueId(self) -> str:
            return "new-timeline-uid"

        def GetMediaPoolItem(self) -> None:
            return None

        def GetStartFrame(self) -> int:
            return 0

        def GetEndFrame(self) -> int:
            return 10

        def GetTrackCount(self, kind: str) -> int:
            return 2 if kind == "video" else 0

        def GetTrackName(self, _kind: str, index: int) -> str:
            return "Root" if index == 1 else "Markers"

        def GetItemListInTrack(self, _kind: str, index: int) -> list[Clip]:
            return [clip] if index == 1 else []

        def GetMarkers(self) -> dict[int, Any]:
            return self.markers

        def DeleteMarkerAtFrame(self, frame: int) -> bool:
            counts["delete_marker"] += 1
            self.markers.pop(frame)
            return True

        def AddMarker(self, frame: int, *_args: Any) -> bool:
            self.markers[frame] = {}
            counts["stamped"] += 1
            return True

    timeline = Timeline()

    class Folder:
        def GetUniqueId(self) -> str:
            return "root"

        def GetClipList(self) -> list[Media]:
            return [media]

        def GetSubFolderList(self) -> list[Any]:
            return []

    class Pool:
        def ImportTimelineFromFile(self, path: str, options: Any) -> Timeline:
            assert path.endswith("timeline.otio")
            assert options == {"timelineName": "VERA Test", "importSourceClips": True}
            counts["import"] += 1
            return timeline

        def AppendToTimeline(self, *_args: Any) -> None:
            counts["append"] += 1

        def GetRootFolder(self) -> Folder:
            return Folder()

    class Project:
        def GetTimelineCount(self) -> int:
            return counts["import"]

        def SetCurrentTimeline(self, candidate: Timeline) -> bool:
            return candidate is timeline

    adapter = workflow_v2.PublicResolveAdapter.__new__(workflow_v2.PublicResolveAdapter)
    adapter.pool = Pool()
    adapter.resolve = SimpleNamespace(SCALE_FIT="fit", SCALE_CROP="crop")
    adapter.project = Project()
    adapter.timeline = None
    adapter.expected_timeline_id = None
    adapter.expected_events = {}
    adapter.expected_stamps = {}
    adapter.expected_properties = {}
    adapter.expected_source_ranges = {}
    adapter._v2_root = package.root
    adapter.media_by_source = {}
    adapter.media_id_by_source = {}
    adapter.assert_current_target = lambda: None  # type: ignore[method-assign]

    otio = package.root / "Builds" / package.manifest["buildId"] / "timeline.otio"
    if not accepted:
        with pytest.raises(workflow_v2.WorkflowV2Error, match="scaling"):
            adapter.import_verified_otio(otio, package.view, "VERA Test")
        assert counts["import"] == 1
        assert counts["stamped"] == 0
        return
    adapter.import_verified_otio(otio, package.view, "VERA Test")
    assert counts == {"import": 1, "append": 0, "delete_marker": 1, "stamped": 1}
    assert adapter.media_id_by_source[source["id"]] == "exact-source-id"
    assert adapter.expected_properties[package.view["events"][0]["id"]] == {
        "DynamicZoomEnabled": False,
        "Scaling": 2 if framing == "contain" else 3,
    }
    with pytest.raises(workflow_v2.WorkflowV2Error, match="fresh empty target"):
        adapter.import_verified_otio(otio, package.view, "VERA Test")
    assert counts["import"] == 1


def test_issue336_native_still_hold_uses_single_source_frame() -> None:
    event = {
        "sourceRange": {"startFrame": 0, "durationFrames": 24},
        "pictureTreatment": {"kind": "still_frame", "imageMotion": {"mode": "none"}},
    }
    source = {"kind": "still"}
    manifest_source = {"sourceFrameMap": {"decodedPackageFrameCount": 1}}
    assert workflow_v2._native_otio_single_frame_hold(event, source, manifest_source)
    assert not workflow_v2._native_otio_single_frame_hold(
        event, {"kind": "video"}, manifest_source
    )
    assert not workflow_v2._native_otio_single_frame_hold(
        event, source, {"sourceFrameMap": {"decodedPackageFrameCount": 2}}
    )
    assert not workflow_v2._native_otio_single_frame_hold(
        event, source, {"sourceFrameMap": {"decodedPackageFrameCount": True}}
    )
    assert not workflow_v2._native_otio_single_frame_hold(
        {**event, "sourceRange": {"startFrame": 2, "durationFrames": 24}},
        source,
        manifest_source,
    )
    assert not workflow_v2._native_otio_single_frame_hold(
        {**event, "pictureTreatment": {"kind": "still_frame"}}, source, manifest_source
    )


def test_native_otio_refuses_mixed_plain_stills_and_allows_video() -> None:
    motion = {"kind": "still_frame", "imageMotion": {"mode": "none"}}
    plain = {"kind": "still", "composition": {"framingPolicy": "contain"}}
    view: dict[str, Any] = {
        "sources": [
            {"id": "image", "kind": "still"},
            {"id": "presenter", "kind": "video"},
        ],
        "events": [
            {"id": "motion", "sourceId": "image", "pictureTreatment": motion},
            {"id": "plain", "sourceId": "presenter", "pictureTreatment": plain},
        ],
    }
    assert workflow_v2._requires_native_otio(view)
    assert workflow_v2._native_otio_has_unqualified_plain_stills(view)
    view["events"][1]["pictureTreatment"] = None
    assert not workflow_v2._native_otio_has_unqualified_plain_stills(view)


def _native_audio_fixture(gain_db: int | float) -> tuple[Any, Any, dict[str, Any]]:
    class Media:
        def GetMediaId(self) -> str:
            return "media-id"

    class Item:
        def __init__(self, media: Media) -> None:
            self.media = media
            self.properties: dict[str, Any] = {}
            self.marker_custom_data: str | None = None
            self.start = 0
            self.duration = 10
            self.source_start = 0
            self.source_end = 9

        def AddMarker(self, *_args: Any) -> bool:
            self.marker_custom_data = _args[-1]
            return True

        def SetProperties(self, properties: dict[str, Any]) -> bool:
            self.properties = dict(properties)
            return True

        def GetProperties(self) -> dict[str, Any]:
            return dict(self.properties)

        def GetStart(self, _track: bool) -> int:
            return self.start

        def GetDuration(self, _track: bool) -> int:
            return self.duration

        def GetSourceStartFrame(self) -> int:
            return self.source_start

        def GetSourceEndFrame(self) -> int:
            return self.source_end

        def GetMediaPoolItem(self) -> Media:
            return self.media

        def GetMarkerCustomData(self, _frame: int) -> str | None:
            return self.marker_custom_data

    class Pool:
        def __init__(self, item: Item) -> None:
            self.item = item
            self.infos: list[dict[str, Any]] = []

        def AppendToTimeline(self, infos: list[dict[str, Any]]) -> list[Item]:
            self.infos = infos
            record_frame = infos[0]["recordFrame"]
            self.item.start = record_frame
            self.item.duration = infos[0]["endFrame"] - infos[0]["startFrame"]
            self.item.source_start = infos[0]["startFrame"]
            self.item.source_end = infos[0]["endFrame"] - 1
            return [self.item]

    class Timeline:
        def __init__(self, item: Item) -> None:
            self.item = item
            self.track_counts = {"audio": 1}
            self.track_names = {("audio", 1): "Source Audio"}
            self.items_by_track: dict[tuple[str, int], list[Any]] = {
                ("audio", 1): [item]
            }
            self.markers: dict[int, dict[str, Any]] = {}

        def GetName(self) -> str:
            return "VERA Delivery test"

        def GetStartFrame(self) -> int:
            return 0

        def GetEndFrame(self) -> int:
            return 10

        def GetTrackCount(self, kind: str) -> int:
            return self.track_counts.get(kind, 0)

        def GetTrackName(self, kind: str, index: int) -> str:
            return self.track_names.get((kind, index), "")

        def GetItemListInTrack(self, kind: str, index: int) -> list[Item]:
            return self.items_by_track.get((kind, index), [])

        def GetMarkers(self) -> dict[int, Any]:
            return self.markers

        def AddMarker(
            self,
            frame: int,
            color: str,
            name: str,
            note: str,
            duration: int,
            custom_data: str,
        ) -> bool:
            self.markers[frame] = {
                "color": color,
                "name": name,
                "note": note,
                "duration": duration,
                "customData": custom_data,
            }
            return True

        def GetMarkerCustomData(self, frame: int) -> str | None:
            marker = self.markers.get(frame)
            return marker.get("customData") if marker is not None else None

    class Project:
        def GetName(self) -> str:
            return "VERA Delivery test"

    media = Media()
    item = Item(media)
    pool = Pool(item)
    event_id = f"source-audio-{gain_db}"
    event = {
        "id": event_id,
        "kind": "source_audio",
        "sourceId": "audio-source",
        "trackId": "audio-track",
        "trackKind": "audio",
        "recordRange": {"startFrame": 0, "durationFrames": 10},
        "sourceRange": {"startFrame": 0, "durationFrames": 10},
        "v2Event": {
            "eventId": event_id,
            "audio": {
                "audioPolicy": "quiet" if gain_db == -18 else "full",
                "gainDb": gain_db,
            },
        },
        "gainDb": gain_db,
        "pictureTreatment": None,
    }
    view: dict[str, Any] = {
        "timeline": {"startFrame": 0, "durationFrames": 10},
        "tracks": [
            {"id": "audio-track", "kind": "audio", "index": 1, "name": "Source Audio"}
        ],
        "events": [event],
    }
    adapter: Any = workflow_v2.PublicResolveAdapter.__new__(
        workflow_v2.PublicResolveAdapter
    )
    adapter.resolve = SimpleNamespace()
    adapter.assert_current_target = lambda: None
    adapter.media_by_source = {"audio-source": media}
    adapter.media_id_by_source = {"audio-source": "media-id"}
    adapter.pool = pool
    adapter.timeline = Timeline(item)
    adapter.project = Project()
    adapter.expected_project_name = "VERA Delivery test"
    adapter.expected_timeline_name = "VERA Delivery test"
    adapter.expected_settings = {}
    adapter._v2_sources = {"audio-source": {"kind": "audio"}}
    adapter._v2_tracks = tuple(view["tracks"])
    adapter._v2_timeline = {"width": 1920, "height": 1080}
    adapter.expected_events = {}
    adapter.expected_stamps = {}
    adapter.expected_properties = {}
    adapter.expected_source_ranges = {}
    adapter.timeline_marker_stamps = {}
    adapter.expected_markers = {}
    adapter._verify_bins = lambda _discrepancies: None
    adapter._verify_media_inventory = lambda _view, _discrepancies: None
    return adapter, item, view


def test_loader_checks_closed_v2_handoff_without_parsing_otio(tmp_path: Path) -> None:
    attestation, digest, _ = _make_package(tmp_path)

    loaded = workflow_v2.load_verified_package_v2(attestation, digest)

    assert loaded.view["schemaVersion"] == "resolve-native-view/v2"
    assert loaded.view["events"][0]["v2Event"] == loaded.manifest["events"][0]


def test_strict_json_rejects_overflowing_float_exponent() -> None:
    with pytest.raises(workflow_v2.WorkflowV2Error, match="non-finite"):
        workflow_v2._strict_object(b'{"value":1e999}', "test JSON")


def test_loader_rejects_attestation_symlink_and_package_drift(tmp_path: Path) -> None:
    attestation, digest, value = _make_package(tmp_path)
    linked = tmp_path / "linked.json"
    linked.symlink_to(attestation)
    with pytest.raises(workflow_v2.WorkflowV2Error):
        workflow_v2.load_verified_package_v2(linked, digest)

    root = Path(value["packageDir"])
    next((root / "Media" / "Resolved").glob("*.mov")).write_bytes(b"changed")
    with pytest.raises(workflow_v2.WorkflowV2Error):
        workflow_v2.load_verified_package_v2(attestation, digest)


def test_composition_return_must_be_strictly_inside_root_event(
    tmp_path: Path,
) -> None:
    attestation, digest, _ = _make_package(tmp_path, return_frame=5)
    workflow_v2.load_verified_package_v2(attestation, digest)

    for frame in (0, 10):
        boundary_dir = tmp_path / f"boundary-{frame}"
        boundary_dir.mkdir()
        attestation, digest, _ = _make_package(boundary_dir, return_frame=frame)
        with pytest.raises(workflow_v2.WorkflowV2Error, match="interior"):
            workflow_v2.load_verified_package_v2(attestation, digest)


@pytest.mark.parametrize(
    ("composition", "track_by_id", "message"),
    [
        (
            {
                "topology": "primary_root_child_overlay",
                "primaryRootTrackId": "root",
                "childTrackIds": ["root"],
                "overlayTrackIds": ["child"],
                "rootContinuous": True,
                "returns": [],
            },
            {
                "root": {"id": "root", "kind": "video", "index": 1},
                "child": {"id": "child", "kind": "video", "index": 2},
            },
            "roles overlap",
        ),
        (
            {
                "topology": "primary_root_child_overlay",
                "primaryRootTrackId": "root",
                "childTrackIds": ["child"],
                "overlayTrackIds": ["child"],
                "rootContinuous": True,
                "returns": [],
            },
            {
                "root": {"id": "root", "kind": "video", "index": 1},
                "child": {"id": "child", "kind": "video", "index": 2},
            },
            "roles overlap",
        ),
        (
            {
                "topology": "primary_root_child_overlay",
                "primaryRootTrackId": "root",
                "childTrackIds": ["child"],
                "overlayTrackIds": ["overlay"],
                "rootContinuous": True,
                "returns": [],
            },
            {
                "root": {"id": "root", "kind": "video", "index": 2},
                "child": {"id": "child", "kind": "video", "index": 1},
                "overlay": {"id": "overlay", "kind": "video", "index": 3},
            },
            "child tracks must follow",
        ),
        (
            {
                "topology": "primary_root_child_overlay",
                "primaryRootTrackId": "root",
                "childTrackIds": ["child"],
                "overlayTrackIds": ["overlay"],
                "rootContinuous": True,
                "returns": [],
            },
            {
                "root": {"id": "root", "kind": "video", "index": 1},
                "child": {"id": "child", "kind": "video", "index": 3},
                "overlay": {"id": "overlay", "kind": "video", "index": 2},
            },
            "overlay tracks must follow",
        ),
    ],
)
def test_composition_roles_are_disjoint_and_index_ordered(
    composition: dict[str, Any],
    track_by_id: dict[str, dict[str, Any]],
    message: str,
) -> None:
    manifest = {
        "composition": composition,
        "timeline": {"durationFrames": 10},
    }
    view = {
        "events": [
            {
                "id": "root-event",
                "trackId": "root",
                "recordRange": {"startFrame": 0, "durationFrames": 10},
            }
        ]
    }

    with pytest.raises(workflow_v2.WorkflowV2Error, match=message):
        workflow_v2._validate_composition(manifest, view, track_by_id)


def test_public_builder_handoff_preserves_root_child_overlay_return(
    tmp_path: Path,
) -> None:
    case = make_package_case(
        tmp_path, scenario="root-child-overlay-return", rate="25fps"
    )

    built = case.build()
    verified = verify_v2_package(case.project_root)
    package_dir = case.project_root / "Builds" / built.build_id
    manifest = json.loads((package_dir / "timeline-manifest.json").read_text())
    view = json.loads((package_dir / "delivery-view.json").read_text())
    tracks = {track["id"]: track for track in view["tracks"]}

    assert verified.build_id == built.build_id
    assert verified.event_count > 0
    assert manifest["composition"]["returns"]
    workflow_v2._validate_composition(manifest, view, tracks)


def test_unsupported_fractional_build_refuses_before_adapter(tmp_path: Path) -> None:
    attestation, digest, _ = _make_package(tmp_path, frame_rate=(30000, 1001))
    called = False

    def forbidden(_resolve: Any) -> Any:
        nonlocal called
        called = True
        raise AssertionError("fractional build reached Resolve")

    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=forbidden,
    )
    assert result["status"] == "stopped_safely"
    assert called is False


def test_23976_build_runs_guarded_save_reopen_and_readback(tmp_path: Path) -> None:
    attestation, digest, _ = _make_package(tmp_path, fractional=True)
    preflight_adapter = _FakeAdapter()
    preflight = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        allow_fractional_native=True,
        adapter_factory=lambda _resolve: preflight_adapter,
    )
    assert preflight["status"] == "preflight_passed"
    assert preflight["nativeRateQualified"] is True
    assert "nativeRateLimitation" not in preflight
    assert preflight_adapter.settings["timelineFrameRate"] == "23.976"

    adapter = _FakeAdapter()
    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        allow_fractional_native=True,
        adapter_factory=lambda _resolve: adapter,
    )

    assert result["status"] == "verified"
    assert result["nativeRateQualified"] is True
    assert adapter.settings["timelineFrameRate"] == "23.976"
    assert adapter.calls[:5] == [
        "connected_facts",
        "probe",
        "collision",
        "create_project",
        "target",
    ]
    assert adapter.calls[-2:] == ["save_close_reopen", "verify"]


def test_23976_native_rate_is_opt_in_and_defaults_to_refusal(
    tmp_path: Path,
) -> None:
    attestation, digest, _ = _make_package(tmp_path, fractional=True)
    preflight_adapter = _FakeAdapter()
    preflight = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        adapter_factory=lambda _resolve: preflight_adapter,
    )
    assert preflight["status"] == "preflight_passed"
    assert preflight["nativeRateQualified"] is False
    assert preflight["nativeRateLimitation"] == (
        "24000/1001 is not natively qualified."
    )
    assert "timelineFrameRate" not in preflight_adapter.settings

    called = False

    def forbidden(_resolve: Any) -> Any:
        nonlocal called
        called = True
        raise AssertionError("default fractional build reached Resolve")

    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=forbidden,
    )
    assert result["status"] == "stopped_safely"
    assert result["nativeRateQualified"] is False
    assert called is False


def test_unsupported_ntsc_fraction_is_rejected_before_adapter(tmp_path: Path) -> None:
    attestation, digest, _ = _make_package(tmp_path, frame_rate=(30000, 1001))
    called = False

    def forbidden(_resolve: Any) -> Any:
        nonlocal called
        called = True
        raise AssertionError("unsupported rate reached Resolve")

    result = workflow_v2.run_workflow_delivery_v2(
        object(), attestation, digest, adapter_factory=forbidden
    )

    assert result["status"] == "stopped_safely"
    assert called is False


def test_view_frame_rate_must_match_verified_manifest(tmp_path: Path) -> None:
    attestation, digest, _ = _make_package(
        tmp_path, frame_rate=(25, 1), view_frame_rate=(24, 1)
    )
    called = False

    def forbidden(_resolve: Any) -> Any:
        nonlocal called
        called = True
        raise AssertionError("mismatched view rate reached Resolve")

    result = workflow_v2.run_workflow_delivery_v2(
        object(), attestation, digest, adapter_factory=forbidden
    )

    assert result["status"] == "stopped_safely"
    assert called is False


def test_build_authorization_order_and_private_marker_text_redaction(
    tmp_path: Path,
) -> None:
    attestation, digest, _ = _make_package(tmp_path)
    adapter = _FakeAdapter()
    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=lambda _resolve: adapter,
    )
    assert result["status"] == "verified"
    assert adapter.calls[:5] == [
        "connected_facts",
        "probe",
        "collision",
        "create_project",
        "target",
    ]
    assert adapter.calls.count("place_event") == 1
    assert adapter.calls.count("add_marker") == 1
    assert "PRIVATE marker text" not in json.dumps(result)


def test_changed_packaged_media_after_preflight_refuses_before_native_call(
    tmp_path: Path,
) -> None:
    attestation, digest, value = _make_package(tmp_path)
    preflight = workflow_v2.run_workflow_delivery_v2(
        object(), attestation, digest, adapter_factory=lambda _: _FakeAdapter()
    )
    assert preflight["status"] == "preflight_passed"

    media = next((Path(value["packageDir"]) / "Media" / "Resolved").glob("*.mov"))
    media.write_bytes(media.read_bytes() + b"changed-after-packaging")
    adapter = _FakeAdapter()
    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=lambda _: adapter,
    )
    assert result["status"] == "stopped_safely"
    assert result["verified"] is False
    assert result["partialTargetRetained"] is False
    assert adapter.calls == []


def test_media_tamper_during_read_only_preflight_refuses_before_first_native_write(
    tmp_path: Path,
) -> None:
    attestation, digest, value = _make_package(tmp_path)
    media = next((Path(value["packageDir"]) / "Media" / "Resolved").glob("*.mov"))

    class ChangingPreflight(_FakeAdapter):
        def probe(self, settings: Any) -> tuple[str, ...]:
            result = super().probe(settings)
            media.write_bytes(media.read_bytes() + b"changed-during-preflight")
            return result

    adapter = ChangingPreflight()
    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=lambda _: adapter,
    )
    assert "probe" in adapter.calls
    assert result["status"] == "stopped_safely"
    assert result["verified"] is False
    assert result["partialTargetRetained"] is False
    assert "create_project" not in adapter.calls
    assert "import_media" not in adapter.calls


@pytest.mark.parametrize("change_during", ["place_event", "verify"])
def test_mid_build_media_swap_after_native_readback_cannot_verify(
    tmp_path: Path, change_during: str
) -> None:
    attestation, digest, value = _make_package(tmp_path)
    media = next((Path(value["packageDir"]) / "Media" / "Resolved").glob("*.mov"))

    class ChangingAdapter(_FakeAdapter):
        def _call(self, name: str) -> None:
            super()._call(name)
            if name == change_during:
                media.write_bytes(media.read_bytes() + b"swapped-during-native")

    adapter = ChangingAdapter()
    observed: list[tuple[str, bool]] = []
    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=lambda _: adapter,
        stage_observer=lambda label, _seconds, succeeded: observed.append(
            (label, succeeded)
        ),
    )
    assert "place_event" in adapter.calls
    assert "save_close_reopen" in adapter.calls
    assert "verify" in adapter.calls
    assert result["status"] == "mutation_failed"
    assert result["verified"] is False
    assert result["partialTargetRetained"] is True
    assert result["failureStage"] == "final package validation"
    assert observed[-1] == ("verify", False)


@pytest.mark.parametrize("visual_event_count", [1, 7])
def test_build_deep_package_loads_do_not_scale_with_placed_clips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, visual_event_count: int
) -> None:
    attestation, digest, _ = _make_package(
        tmp_path, visual_event_count=visual_event_count
    )
    real_loader = workflow_v2.load_verified_package_v2
    loads = 0

    def counted_loader(
        path: Path, expected_digest: str
    ) -> workflow_v2.VerifiedPackageV2:
        nonlocal loads
        loads += 1
        return real_loader(path, expected_digest)

    monkeypatch.setattr(workflow_v2, "load_verified_package_v2", counted_loader)
    adapter = _FakeAdapter()
    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=lambda _: adapter,
    )
    assert result["status"] == "verified"
    assert adapter.calls.count("place_event") == visual_event_count
    assert adapter.calls.count("target") >= visual_event_count + 9
    assert loads == 3  # entry, first write, and post-readback; never per clip


def test_marker_metadata_is_preflightable_and_redacted(tmp_path: Path) -> None:
    attestation, digest, _ = _make_package(tmp_path)
    result = workflow_v2.run_workflow_delivery_v2(
        object(), attestation, digest, adapter_factory=lambda _resolve: _FakeAdapter()
    )

    assert result["status"] == "preflight_passed"
    assert result["nativeSubtitleTracksQualified"] is True
    assert "PRIVATE marker text" not in json.dumps(result)


def test_native_subtitle_tracks_refuse_before_adapter_creation(tmp_path: Path) -> None:
    attestation, digest, _ = _make_package(
        tmp_path, marker_track_kind="subtitle", marker_track_index=1
    )
    called = False

    def forbidden(_resolve: Any) -> Any:
        nonlocal called
        called = True
        raise AssertionError("unqualified subtitle track reached Resolve")

    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=forbidden,
    )

    assert result["status"] == "stopped_safely"
    assert result["nativeSubtitleTracksQualified"] is False
    assert result["partialTargetRetained"] is False
    assert called is False


@pytest.mark.parametrize("motion_bearing", [False, True])
def test_native_source_audio_is_refused_before_adapter_creation(
    tmp_path: Path, motion_bearing: bool
) -> None:
    treatment = (
        {
            "kind": "still_frame",
            "pictureKind": "image",
            "framingPolicy": "contain",
            "imageMotion": {"mode": "none"},
        }
        if motion_bearing
        else None
    )
    attestation, digest, _ = _make_package(
        tmp_path, source_audio=True, picture_treatment=treatment
    )
    called = False

    def forbidden(_resolve: Any) -> Any:
        nonlocal called
        called = True
        raise AssertionError("unqualified sidecar reached adapter")

    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=forbidden,
    )
    assert result["status"] == "stopped_safely"
    assert called is False
    assert result["sourceAudioNativeQualified"] is False


@pytest.mark.parametrize(
    ("policy", "gain_db", "expected_status"),
    [
        ("full", -0.1, "preflight_passed"),
        ("quiet", -0.1, "stopped_safely"),
        ("full", -0.2, "stopped_safely"),
    ],
)
def test_source_audio_preflight_allows_only_approved_headroom_pair(
    tmp_path: Path,
    policy: str,
    gain_db: int | float,
    expected_status: str,
) -> None:
    attestation, digest, _ = _make_package(
        tmp_path,
        source_audio=True,
        source_audio_gain=gain_db,
        source_audio_policy=policy,
    )
    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        adapter_factory=lambda _resolve: _FakeAdapter(),
    )

    assert result["status"] == expected_status


@pytest.mark.parametrize("gain_db", [-18, -0.1, 0])
def test_native_audio_adapter_writes_and_reads_back_policy_gain(
    gain_db: int | float,
) -> None:
    adapter, item, view = _native_audio_fixture(gain_db)
    event = view["events"][0]

    adapter.place_event(event)

    assert adapter.pool.infos[0]["mediaType"] == 2
    assert item.properties == {"AudioVolumeEnabled": True, "AudioVolume": gain_db}
    assert adapter.expected_properties[event["id"]] == item.properties


def test_native_audio_reopened_gain_discrepancy_is_reported() -> None:
    adapter, item, view = _native_audio_fixture(-18)
    event = view["events"][0]
    adapter.place_event(event)

    # Resolve accepted the write, but the saved/reopened item reports Full.
    item.properties["AudioVolume"] = 0

    assert adapter.verify(view) == ("event-properties",)


@pytest.mark.parametrize("stray_slot", [2, 3])
def test_readback_checks_undeclared_and_declared_empty_track_slots(
    stray_slot: int,
) -> None:
    adapter, item, view = _native_audio_fixture(-18)
    timeline = adapter.timeline
    timeline.track_counts["audio"] = 3
    timeline.track_names[("audio", 3)] = "Declared Empty"
    timeline.items_by_track[("audio", stray_slot)] = [item]
    view["tracks"].append(
        {"id": "declared-empty", "kind": "audio", "index": 3, "name": "Declared Empty"}
    )
    adapter._v2_tracks = tuple(view["tracks"])

    assert adapter.verify(view) == ("event-count",)


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("name", "Changed marker name"),
        ("note", "Changed marker note"),
        ("color", "Blue"),
        ("duration", 2),
    ],
)
def test_readback_checks_marker_properties(field: str, changed: Any) -> None:
    adapter, _item, view = _native_audio_fixture(-18)
    marker = {
        "id": "script-marker",
        "frame": 5,
        "color": "YELLOW",
        "name": "Script note",
        "note": "Private source text",
        "provenance": {"eventId": "script-marker"},
    }
    adapter.add_v2_marker(marker)
    adapter.timeline.markers[5][field] = changed

    assert adapter.verify(view) == ("marker-properties",)


def test_source_audio_projection_must_match_record_duration(tmp_path: Path) -> None:
    attestation, digest, _ = _make_package(
        tmp_path, source_audio=True, source_audio_range_duration=9
    )
    called = False

    def forbidden(_resolve: Any) -> Any:
        nonlocal called
        called = True
        raise AssertionError("invalid source-audio range reached Resolve")

    result = workflow_v2.run_workflow_delivery_v2(
        object(), attestation, digest, adapter_factory=forbidden
    )
    assert result["status"] == "stopped_safely"
    assert called is False


def test_slate_metadata_is_preflightable_but_native_build_refuses(
    tmp_path: Path,
) -> None:
    attestation, digest, _ = _make_package(
        tmp_path,
        picture_treatment={
            "kind": "slate",
            "purpose": "unresolved",
            "text": "PRIVATE authored slate text",
        },
    )
    adapter = _FakeAdapter()
    preflight = workflow_v2.run_workflow_delivery_v2(
        object(), attestation, digest, adapter_factory=lambda _resolve: adapter
    )
    assert preflight["status"] == "preflight_passed"
    assert preflight["nativePictureTreatmentsQualified"] is False

    called = False

    def forbidden(_resolve: Any) -> Any:
        nonlocal called
        called = True
        raise AssertionError("unrendered authored slate reached Resolve")

    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=forbidden,
    )
    assert result["status"] == "stopped_safely"
    assert called is False
    assert "PRIVATE authored slate text" not in json.dumps(result)


def test_still_frame_cover_is_preflightable_but_not_native_qualified(
    tmp_path: Path,
) -> None:
    attestation, digest, _ = _make_package(
        tmp_path,
        picture_treatment={
            "kind": "still_frame",
            "pictureKind": "image",
            "framingPolicy": "cover",
        },
    )
    preflight = workflow_v2.run_workflow_delivery_v2(
        object(), attestation, digest, adapter_factory=lambda _resolve: _FakeAdapter()
    )
    assert preflight["status"] == "preflight_passed"
    assert preflight["nativePictureTreatmentsQualified"] is False


def test_unsupported_picture_treatment_fails_before_adapter(tmp_path: Path) -> None:
    attestation, digest, _ = _make_package(
        tmp_path,
        picture_treatment={"kind": "unsupported", "value": "unknown"},
    )
    called = False

    def forbidden(_resolve: Any) -> Any:
        nonlocal called
        called = True
        return _FakeAdapter()

    result = workflow_v2.run_workflow_delivery_v2(
        object(), attestation, digest, adapter_factory=forbidden
    )
    assert result["status"] == "stopped_safely"
    assert called is False


def test_video_source_with_still_treatment_gets_still_composition_properties() -> None:
    calls: list[str] = []

    class Item:
        def __init__(self) -> None:
            self.properties: dict[str, Any] = {}
            self.property_calls: list[dict[str, Any]] = []

        def AddMarker(self, *_args: Any) -> bool:
            return True

        def SetProperties(self, properties: dict[str, Any]) -> bool:
            calls.append("scaling" if "Scaling" in properties else "properties")
            self.property_calls.append(dict(properties))
            self.properties.update(properties)
            if "Scaling" in properties:
                self.properties["AnchorPointX"] = 1119.12568
                self.properties["AnchorPointY"] = 629.507
            for key in ("AnchorPointX", "AnchorPointY"):
                if key in properties:
                    self.properties[key] = properties[key] * 1.1657559198542806
            return True

        def GetProperties(self) -> dict[str, Any]:
            return self.properties

    class Pool:
        def __init__(self, item: Item) -> None:
            self.item = item
            self.infos: list[dict[str, Any]] = []

        def AppendToTimeline(self, infos: list[dict[str, Any]]) -> list[Item]:
            self.infos = infos
            return [self.item]

    item = Item()
    pool = Pool(item)
    adapter: Any = workflow_v2.PublicResolveAdapter.__new__(
        workflow_v2.PublicResolveAdapter
    )
    adapter.resolve = SimpleNamespace(SCALE_FIT="fit", COMPOSITE_NORMAL="normal")
    adapter.assert_current_target = lambda: calls.append("target")
    adapter.media_by_source = {"source": object()}
    adapter.pool = pool
    adapter._v2_sources = {"source": {"kind": "video"}}
    adapter._v2_tracks = ({"id": "video-track", "kind": "video", "index": 1},)
    adapter._v2_timeline = {"width": 1920, "height": 1080}
    adapter.expected_events = {}
    adapter.expected_stamps = {}
    adapter.expected_properties = {}
    adapter.expected_source_ranges = {}
    adapter.timeline_marker_stamps = {}
    event = {
        "id": "still-event",
        "kind": "primary_visual",
        "sourceId": "source",
        "trackId": "video-track",
        "trackKind": "video",
        "recordRange": {"startFrame": 0, "durationFrames": 10},
        "sourceRange": {"startFrame": 3, "durationFrames": 10},
        "v2Event": {"eventId": "still-event"},
        "gainDb": None,
        "pictureTreatment": {
            "kind": "still",
            "composition": {
                "framingPolicy": "contain",
                "horizontalAlignment": "center",
                "verticalAlignment": "center",
                "backgroundColor": "#000000",
                "motionPreset": "none",
            },
        },
    }

    adapter.place_event(event)

    assert pool.infos[0]["mediaType"] == 1
    assert item.properties["Scaling"] == "fit"
    assert item.properties["CompositeMode"] == "normal"
    assert item.property_calls[0] == {"Scaling": "fit"}
    assert item.property_calls[1]["AnchorPointX"] == 0
    assert item.property_calls[1]["AnchorPointY"] == 0
    assert item.properties["AnchorPointX"] == 0
    assert item.properties["AnchorPointY"] == 0
    assert calls == ["target", "target", "scaling", "target", "properties"]


@pytest.mark.parametrize(
    ("duration", "source_fps", "timeline_rate", "expected"),
    [
        (142, "24", {"numerator": 24000, "denominator": 1001}, 143),
        (142, "24", {"numerator": 25, "denominator": 1}, 137),
    ],
)
def test_still_source_frame_duration_uses_exact_rate_conversion(
    duration: int,
    source_fps: str,
    timeline_rate: dict[str, int],
    expected: int,
) -> None:
    assert _still_source_frame_duration(duration, source_fps, timeline_rate) == expected


def test_still_source_frame_duration_refuses_unknown_fps() -> None:
    with pytest.raises(StudioSpikeError, match="frame rate is unavailable"):
        _still_source_frame_duration(
            142, None, {"numerator": 24000, "denominator": 1001}
        )


def _fractional_still_proof() -> tuple[dict[str, Any], ...]:
    content_hash = "sha256:" + "a" * 64
    manifest_event = {
        "eventId": "still-event",
        "kind": "primary_visual",
        "sourceRange": {"startFrame": 0, "endFrame": 1},
        "provenance": {
            "sourceId": "still-source",
            "deliveredSourceHash": content_hash,
        },
    }
    event = {
        "id": "still-event",
        "kind": "primary_visual",
        "sourceId": "still-source",
        "recordRange": {"startFrame": 0, "durationFrames": 142},
        "sourceRange": {"startFrame": 0, "durationFrames": 1},
        "v2Event": manifest_event,
    }
    source = {"id": "still-source", "kind": "still", "contentHash": content_hash}
    manifest_source = {
        "id": "still-source",
        "deliveredHash": content_hash,
    }
    timeline = {
        "frameRate": {"numerator": 24000, "denominator": 1001},
        "audioSampleRate": 48000,
    }
    observations = {
        "actual_start": 91,
        "actual_end": 91,
        "source_times": {"GetSourceStartTime": 0.0, "GetSourceEndTime": 1 / 24},
        "speed": {"Percentage": 0},
        "media_properties": {"Frames": "1", "FPS": "24"},
        "record_duration": 142,
    }
    return event, source, manifest_source, timeline, observations


def _fractional_video_proof() -> tuple[dict[str, Any], ...]:
    content_hash = "sha256:" + "b" * 64
    rate = {"numerator": 24000, "denominator": 1001}
    source_frame_map = {
        "decodedPackageFrameCount": 1000,
        "decodedPackageFrameRate": rate,
        "probeHash": "probe-hash",
        "descriptorHash": "probe-hash",
        "packageFrameZeroLogicalFrame": 0,
        "packageVideoPtsOrigin": {"numerator": 0, "denominator": 1},
        "loggedTimeAtPackageFrameZero": {"numerator": 0, "denominator": 1},
    }
    mapping = {
        "sourceFrameMap": source_frame_map,
        "sourceOrigin": {"numerator": 0, "denominator": 1},
        "deliveredOrigin": {"numerator": 0, "denominator": 1},
        "sourceRate": rate,
        "deliveredRate": rate,
    }
    verification = {
        "deliveredHash": content_hash,
        "decodedFrameCount": 1000,
        "decodedFrameRate": rate,
        "probeHash": "probe-hash",
    }
    binding = {
        "requirementKey": "video-prep",
        "timeMapping": mapping,
        "verification": verification,
    }
    manifest_event = {
        "eventId": "video-event",
        "kind": "primary_visual",
        "sourceRange": {"startFrame": 396, "endFrame": 466},
        "sourceTimeMapping": mapping,
        "provenance": {
            "sourceId": "video-source",
            "deliveredSourceHash": content_hash,
        },
    }
    event = {
        "id": "video-event",
        "kind": "primary_visual",
        "sourceId": "video-source",
        "recordRange": {"startFrame": 0, "durationFrames": 70},
        "sourceRange": {"startFrame": 396, "durationFrames": 70},
        "v2Event": manifest_event,
    }
    source = {"id": "video-source", "kind": "video", "contentHash": content_hash}
    manifest_source = {
        "id": "video-source",
        "deliveredHash": content_hash,
        "deliveredProbeHash": "probe-hash",
        "sourceFrameMap": source_frame_map,
        "sourceTimeMapping": mapping,
        "preparationRequirementKey": "video-prep",
    }
    timeline = {"frameRate": rate, "audioSampleRate": 48000}
    observations = {
        "actual_start": 395,
        "actual_end": 465,
        "source_times": {
            "GetSourceStartTime": 396 * 1001 / 24000,
            "GetSourceEndTime": 466 * 1001 / 24000,
        },
        "speed": {"Percentage": 100},
        "media_properties": {"Frames": "1000"},
        "record_duration": 70,
    }
    return (
        event,
        source,
        manifest_source,
        timeline,
        observations,
        {"video-prep": binding},
    )


def _fractional_narration_proof(
    *, sample_count: int = 367_000, duration_frames: int = 184
) -> tuple[dict[str, Any], ...]:
    content_hash = "sha256:" + "c" * 64
    sample_rate = 48_000
    manifest_event = {
        "eventId": "narration-event",
        "kind": "narration",
        "sourceRange": None,
        "provenance": {"sourceId": "narration-source"},
    }
    event = {
        "id": "narration-event",
        "kind": "narration",
        "sourceId": "narration-source",
        "recordRange": {"startFrame": 0, "durationFrames": duration_frames},
        "sourceRange": {"startFrame": 0, "durationFrames": duration_frames},
        "v2Event": manifest_event,
    }
    source = {
        "id": "narration-source",
        "kind": "audio",
        "contentHash": content_hash,
    }
    manifest_source = {
        "id": "narration-source",
        "narrationAudio": {
            "audioHash": content_hash,
            "durationSamples": sample_count,
            "sampleRate": sample_rate,
        },
    }
    timeline = {
        "frameRate": {"numerator": 24000, "denominator": 1001},
        "audioSampleRate": sample_rate,
    }
    observations = {
        "actual_start": 0,
        "actual_end": duration_frames - 2,
        "source_times": {
            "GetSourceStartTime": 0.0,
            "GetSourceEndTime": sample_count / sample_rate,
        },
        "speed": {"Percentage": 100},
        "media_properties": {},
        "record_duration": duration_frames,
    }
    return event, source, manifest_source, timeline, observations


def _video_proof_at_24fps(
    *, start: int = 396, decoded_frame_count: int = 1000, actual_end: int | None = None
) -> tuple[dict[str, Any], ...]:
    event, source, manifest_source, timeline, observations, bindings = (
        _fractional_video_proof()
    )
    rate = {"numerator": 24, "denominator": 1}
    end = start + observations["record_duration"]
    timeline["frameRate"] = rate
    source_frame_map = manifest_source["sourceFrameMap"]
    source_frame_map["decodedPackageFrameCount"] = decoded_frame_count
    source_frame_map["decodedPackageFrameRate"] = rate
    manifest_source["sourceTimeMapping"]["sourceRate"] = rate
    manifest_source["sourceTimeMapping"]["deliveredRate"] = rate
    event["v2Event"]["sourceTimeMapping"]["sourceRate"] = rate
    event["v2Event"]["sourceTimeMapping"]["deliveredRate"] = rate
    bindings["video-prep"]["timeMapping"]["sourceRate"] = rate
    bindings["video-prep"]["timeMapping"]["deliveredRate"] = rate
    bindings["video-prep"]["verification"]["decodedFrameCount"] = decoded_frame_count
    bindings["video-prep"]["verification"]["decodedFrameRate"] = rate
    event["sourceRange"] = {"startFrame": start, "durationFrames": end - start}
    event["v2Event"]["sourceRange"] = {"startFrame": start, "endFrame": end}
    observations["actual_start"] = start
    observations["actual_end"] = end if actual_end is None else actual_end
    observations["source_times"] = {
        "GetSourceStartTime": start / 24,
        "GetSourceEndTime": end / 24,
    }
    return event, source, manifest_source, timeline, observations, bindings


def _fractional_source_range_matches(
    proof: tuple[dict[str, Any], ...],
) -> bool:
    event, source, manifest_source, timeline, observations, *binding_value = proof
    return workflow_v2._fractional_source_range_matches(
        event=event,
        source=source,
        manifest_source=manifest_source,
        preparation_bindings=binding_value[0] if binding_value else {},
        timeline=timeline,
        **observations,
    )


def test_fractional_still_source_clock_requires_single_held_frame_and_exact_times() -> (
    None
):
    proof = _fractional_still_proof()
    assert _fractional_source_range_matches(proof)

    event, source, manifest_source, timeline, observations = proof
    bad_times = {
        **observations,
        "source_times": {"GetSourceStartTime": 0.0, "GetSourceEndTime": 2 / 24},
    }
    assert not workflow_v2._fractional_source_range_matches(
        event=event,
        source=source,
        manifest_source=manifest_source,
        preparation_bindings={},
        timeline=timeline,
        **bad_times,
    )
    bad_frames = {**observations, "media_properties": {"Frames": "2", "FPS": "24"}}
    assert not workflow_v2._fractional_source_range_matches(
        event=event,
        source=source,
        manifest_source=manifest_source,
        preparation_bindings={},
        timeline=timeline,
        **bad_frames,
    )

    static_image_speed = {**observations, "speed": {"Percentage": 100}}
    assert workflow_v2._fractional_source_range_matches(
        event=event,
        source=source,
        manifest_source=manifest_source,
        preparation_bindings={},
        timeline=timeline,
        **static_image_speed,
    )


def test_fractional_placeholder_still_binds_its_reference_hash_to_view_source() -> None:
    content_hash = "sha256:" + "e" * 64
    manifest_event: dict[str, Any] = {
        "eventId": "placeholder-event",
        "kind": "placeholder",
        "sourceRange": None,
        "provenance": {"sourceId": None},
        "pictureTreatment": {
            "kind": "still",
            "reference": {"contentHash": content_hash},
        },
    }
    event = {
        "id": "placeholder-event",
        "kind": "placeholder",
        "sourceId": "placeholder-event",
        "recordRange": {"startFrame": 0, "durationFrames": 142},
        "sourceRange": {"startFrame": 0, "durationFrames": 142},
        "v2Event": manifest_event,
    }
    source = {
        "id": "placeholder-event",
        "kind": "still",
        "contentHash": content_hash,
    }
    timeline = {
        "frameRate": {"numerator": 24000, "denominator": 1001},
        "audioSampleRate": 48000,
    }
    observations = {
        "actual_start": 12,
        "actual_end": 12,
        "source_times": {"GetSourceStartTime": 0.0, "GetSourceEndTime": 1 / 24},
        "speed": {"Percentage": 0},
        "media_properties": {"Frames": "1", "FPS": "24"},
        "record_duration": 142,
    }
    kwargs: dict[str, Any] = {
        "event": event,
        "source": source,
        "manifest_source": {},
        "preparation_bindings": {},
        "timeline": timeline,
        **observations,
    }
    assert workflow_v2._fractional_source_range_matches(**kwargs)

    manifest_event["pictureTreatment"]["reference"]["contentHash"] = (
        "sha256:" + "f" * 64
    )
    assert not workflow_v2._fractional_source_range_matches(**kwargs)


def test_fractional_video_source_clock_requires_hash_bound_rate_and_source_times() -> (
    None
):
    proof = _fractional_video_proof()
    assert _fractional_source_range_matches(proof)

    event, source, manifest_source, timeline, observations, bindings = proof
    for changed in ("time", "frame", "end_frame", "source", "hash", "rate"):
        bad_event = json.loads(json.dumps(event))
        bad_source = dict(source)
        bad_manifest_source = json.loads(json.dumps(manifest_source))
        bad_timeline = json.loads(json.dumps(timeline))
        bad_observations = json.loads(json.dumps(observations))
        if changed == "time":
            bad_observations["source_times"]["GetSourceEndTime"] += 1 / 24_000
        elif changed == "frame":
            bad_observations["actual_start"] -= 1
        elif changed == "end_frame":
            bad_observations["actual_end"] -= 1
        elif changed == "source":
            bad_event["v2Event"]["provenance"]["sourceId"] = "other-source"
        elif changed == "hash":
            bad_observations["source_times"] = dict(observations["source_times"])
            bad_source["contentHash"] = "sha256:" + "d" * 64
        else:
            bad_timeline["frameRate"] = {"numerator": 30000, "denominator": 1001}
        assert not workflow_v2._fractional_source_range_matches(
            event=bad_event,
            source=bad_source,
            manifest_source=bad_manifest_source,
            preparation_bindings=bindings,
            timeline=bad_timeline,
            **bad_observations,
        ), changed


def test_fractional_narration_source_clock_requires_sample_bound_eof() -> None:
    proof = _fractional_narration_proof()
    assert _fractional_source_range_matches(proof)

    event, source, manifest_source, timeline, observations = proof
    for changed in ("time", "frame", "source", "hash", "rate"):
        bad_event = json.loads(json.dumps(event))
        bad_source = dict(source)
        bad_manifest_source = json.loads(json.dumps(manifest_source))
        bad_timeline = json.loads(json.dumps(timeline))
        bad_observations = json.loads(json.dumps(observations))
        if changed == "time":
            bad_observations["source_times"]["GetSourceEndTime"] += 2 / 48_000
        elif changed == "frame":
            bad_observations["actual_end"] += 1
        elif changed == "source":
            bad_event["v2Event"]["provenance"]["sourceId"] = "other-source"
        elif changed == "hash":
            bad_manifest_source["narrationAudio"]["audioHash"] = "sha256:" + "d" * 64
        else:
            bad_timeline["frameRate"] = {"numerator": 30000, "denominator": 1001}
        assert not workflow_v2._fractional_source_range_matches(
            event=bad_event,
            source=bad_source,
            manifest_source=bad_manifest_source,
            preparation_bindings={},
            timeline=bad_timeline,
            **bad_observations,
        ), changed


def test_fractional_narration_accepts_authored_record_end_within_audio_extent() -> None:
    for sample_count in (400_000, 368_368):
        proof = _fractional_narration_proof(sample_count=sample_count)
        event, source, manifest_source, timeline, observations = proof
        record_end = Fraction(184 * 1001, 24000)
        authored_end = {
            **observations,
            "actual_end": 183,
            "source_times": {
                "GetSourceStartTime": 0.0,
                "GetSourceEndTime": float(record_end),
            },
        }
        assert _fractional_source_range_matches(
            (event, source, manifest_source, timeline, authored_end)
        ), sample_count

    proof = _fractional_narration_proof(sample_count=367_000, duration_frames=185)
    event, source, manifest_source, timeline, observations = proof
    assert not _fractional_source_range_matches(
        (
            event,
            source,
            manifest_source,
            timeline,
            {
                **observations,
                "actual_end": 184,
                "source_times": {
                    "GetSourceStartTime": 0.0,
                    "GetSourceEndTime": float(Fraction(185 * 1001, 24000)),
                },
            },
        )
    )


def test_24fps_video_source_clock_is_a_proof_bound_fallback() -> None:
    event, source, manifest_source, timeline, observations, bindings = (
        _video_proof_at_24fps()
    )
    arguments: dict[str, Any] = {
        "event": event,
        "source": source,
        "manifest_source": manifest_source,
        "preparation_bindings": bindings,
        "timeline": timeline,
        **observations,
    }
    assert not workflow_v2._fractional_source_range_matches(**arguments)
    assert workflow_v2._fractional_source_range_matches(**arguments, allow_24fps=True)

    bad_end = {**arguments, "actual_end": observations["actual_end"] - 1}
    assert not workflow_v2._fractional_source_range_matches(**bad_end, allow_24fps=True)
    bad_time = {
        **arguments,
        "source_times": {
            **observations["source_times"],
            "GetSourceEndTime": observations["source_times"]["GetSourceEndTime"]
            + 2 / 48_000,
        },
    }
    assert not workflow_v2._fractional_source_range_matches(
        **bad_time, allow_24fps=True
    )
    bad_binding = {
        **arguments,
        "source": {**source, "contentHash": "sha256:" + "d" * 64},
    }
    assert not workflow_v2._fractional_source_range_matches(
        **bad_binding, allow_24fps=True
    )


def test_24fps_video_source_clock_keeps_only_the_proven_eof_inclusive_shape() -> None:
    event, source, manifest_source, timeline, observations, bindings = (
        _video_proof_at_24fps(start=930, decoded_frame_count=1000, actual_end=999)
    )
    arguments = {
        "event": event,
        "source": source,
        "manifest_source": manifest_source,
        "preparation_bindings": bindings,
        "timeline": timeline,
        **observations,
        "allow_24fps": True,
    }
    assert workflow_v2._fractional_source_range_matches(**arguments)
    assert not workflow_v2._fractional_source_range_matches(
        **{**arguments, "actual_end": 998}
    )


def test_24fps_still_and_narration_source_clocks_keep_exact_source_proofs() -> None:
    event, source, manifest_source, timeline, observations = _fractional_still_proof()
    timeline["frameRate"] = {"numerator": 24, "denominator": 1}
    assert workflow_v2._fractional_source_range_matches(
        event=event,
        source=source,
        manifest_source=manifest_source,
        preparation_bindings={},
        timeline=timeline,
        **observations,
        allow_24fps=True,
    )
    observations["actual_start"] = observations["actual_end"] = 0
    assert workflow_v2._fractional_source_range_matches(
        event=event,
        source=source,
        manifest_source=manifest_source,
        preparation_bindings={},
        timeline=timeline,
        **observations,
        allow_24fps=True,
    )
    bad_still = {
        **observations,
        "source_times": {"GetSourceStartTime": 0.0, "GetSourceEndTime": 2 / 24},
    }
    assert not workflow_v2._fractional_source_range_matches(
        event=event,
        source=source,
        manifest_source=manifest_source,
        preparation_bindings={},
        timeline=timeline,
        **bad_still,
        allow_24fps=True,
    )

    event, source, manifest_source, timeline, observations = (
        _fractional_narration_proof()
    )
    timeline["frameRate"] = {"numerator": 24, "denominator": 1}
    arguments = {
        "event": event,
        "source": source,
        "manifest_source": manifest_source,
        "preparation_bindings": {},
        "timeline": timeline,
        **observations,
        "allow_24fps": True,
    }
    assert workflow_v2._fractional_source_range_matches(**arguments)
    bad_eof = {
        **arguments,
        "source_times": {
            **observations["source_times"],
            "GetSourceEndTime": observations["source_times"]["GetSourceEndTime"]
            + 2 / 48_000,
        },
    }
    assert not workflow_v2._fractional_source_range_matches(**bad_eof)


def test_fractional_multiframe_video_still_refuses_before_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    treatment = {
        "kind": "still",
        "composition": {
            "framingPolicy": "contain",
            "horizontalAlignment": "center",
            "verticalAlignment": "center",
            "backgroundColor": "#000000",
            "motionPreset": "none",
        },
    }
    attestation, digest, _ = _make_package(
        tmp_path, fractional=True, picture_treatment=treatment
    )
    verified_package = workflow_v2.load_verified_package_v2(attestation, digest)

    def package_with_frame_count(frame_count: int) -> Any:
        manifest = json.loads(json.dumps(verified_package.manifest))
        manifest["sources"][0]["sourceFrameMap"] = {
            "decodedPackageFrameCount": frame_count
        }
        return SimpleNamespace(
            root=verified_package.root,
            manifest=manifest,
            view=verified_package.view,
            attestation=verified_package.attestation,
        )

    single_frame_package = package_with_frame_count(1)
    monkeypatch.setattr(
        workflow_v2, "load_verified_package_v2", lambda *_args: single_frame_package
    )
    admitted = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        allow_fractional_native=True,
        adapter_factory=lambda _resolve: _FakeAdapter(),
    )
    assert admitted["status"] == "verified", (
        admitted.get("failureStage"),
        admitted.get("failureType"),
        admitted.get("nativePictureTreatmentsQualified"),
    )
    assert admitted["nativePictureTreatmentsQualified"] is True

    adapter_called = False

    def forbidden(_resolve: Any) -> Any:
        nonlocal adapter_called
        adapter_called = True
        raise AssertionError("multi-frame still reached Resolve")

    multiframe_package = package_with_frame_count(2)
    monkeypatch.setattr(
        workflow_v2, "load_verified_package_v2", lambda *_args: multiframe_package
    )
    refused = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        allow_fractional_native=True,
        adapter_factory=forbidden,
    )
    assert refused["status"] == "stopped_safely"
    assert refused["nativePictureTreatmentsQualified"] is False
    assert adapter_called is False


def test_still_media_placement_converts_duration_but_preserves_start() -> None:
    class Media:
        def __init__(self) -> None:
            self.marked: tuple[int, int] | None = None

        def GetClipProperty(self, _name: str) -> str:
            return "24"

        def SetMarkInOut(self, start: int, end: int, _kind: str) -> bool:
            self.marked = (start, end)
            return True

        def ClearMarkInOut(self, _kind: str) -> bool:
            self.marked = None
            return True

    class Item:
        def __init__(self) -> None:
            self.properties: dict[str, Any] = {}

        def AddMarker(self, *_args: Any) -> bool:
            return True

        def SetProperties(self, properties: dict[str, Any]) -> bool:
            self.properties.update(properties)
            return True

        def GetProperties(self) -> dict[str, Any]:
            return dict(self.properties)

    class Pool:
        def __init__(self, item: Item) -> None:
            self.item = item
            self.infos: list[dict[str, Any]] = []

        def AppendToTimeline(self, infos: list[dict[str, Any]]) -> list[Item]:
            self.infos = infos
            return [self.item]

    media, item = Media(), Item()
    pool = Pool(item)
    adapter: Any = workflow_v2.PublicResolveAdapter.__new__(
        workflow_v2.PublicResolveAdapter
    )
    adapter.resolve = SimpleNamespace(SCALE_FIT="fit", COMPOSITE_NORMAL="normal")
    adapter.assert_current_target = lambda: None
    adapter.media_by_source = {"source": media}
    adapter.pool = pool
    adapter._v2_sources = {"source": {"kind": "still"}}
    adapter._v2_tracks = ({"id": "video-track", "kind": "video", "index": 1},)
    adapter._v2_timeline = {
        "width": 1920,
        "height": 1080,
        "frameRate": {"numerator": 24000, "denominator": 1001},
    }
    adapter.expected_events = {}
    adapter.expected_stamps = {}
    adapter.expected_properties = {}
    adapter.expected_source_ranges = {}
    adapter.timeline_marker_stamps = {}
    event = {
        "id": "still-event",
        "kind": "primary_visual",
        "sourceId": "source",
        "trackId": "video-track",
        "trackKind": "video",
        "recordRange": {"startFrame": 0, "durationFrames": 142},
        "sourceRange": {"startFrame": 3, "durationFrames": 142},
        "v2Event": {"eventId": "still-event"},
        "gainDb": None,
        "pictureTreatment": None,
    }

    adapter.place_event(event)

    assert pool.infos[0]["startFrame"] == 3
    assert pool.infos[0]["endFrame"] == 146
    assert media.marked is None
    assert adapter.expected_source_ranges[event["id"]] == (3, 145)


def test_failed_save_retains_named_partial_target(tmp_path: Path) -> None:
    attestation, digest, _ = _make_package(tmp_path)
    adapter = _FakeAdapter(fail_on="save_close_reopen")
    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=lambda _resolve: adapter,
    )
    assert result["status"] == "mutation_failed"
    assert result["partialTargetRetained"] is True
    assert result["discrepancies"] == ["native-delivery-failure"]


def test_reopened_readback_mismatch_retains_partial_target(tmp_path: Path) -> None:
    attestation, digest, _ = _make_package(tmp_path)
    adapter = _FakeAdapter(verification_discrepancies=("event-properties",))

    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="None",
        adapter_factory=lambda _resolve: adapter,
    )

    assert result["status"] == "verification_failed"
    assert result["partialTargetRetained"] is True
    assert result["discrepancies"] == ["event-properties"]
    assert adapter.calls.index("save_close_reopen") < adapter.calls.index("verify")


@pytest.mark.parametrize(
    ("failure", "expected_stages"),
    [
        (None, [("build", True), ("save/reopen", True), ("verify", True)]),
        ("save_close_reopen", [("build", True), ("save/reopen", False)]),
    ],
)
def test_native_stage_observer_is_ordered_and_marks_uncertain_writes(
    tmp_path: Path,
    failure: str | None,
    expected_stages: list[tuple[str, bool]],
) -> None:
    attestation, digest, _ = _make_package(tmp_path)
    adapter = _FakeAdapter(fail_on=failure)
    seen: list[tuple[str, bool]] = []
    result = workflow_v2.run_workflow_delivery_v2(
        object(),
        attestation,
        digest,
        action="build",
        authorize_new_nonproduction=True,
        external_scripting="Local",
        adapter_factory=lambda _resolve: adapter,
        stage_observer=lambda label, elapsed, success: (
            seen.append((label, success)) if elapsed >= 0 else pytest.fail("clock")
        ),
    )
    assert seen == expected_stages
    assert result["status"] == ("verified" if failure is None else "mutation_failed")
    assert result["partialTargetRetained"] == (failure is not None)
