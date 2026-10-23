from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from issue177_package_fixture import make_package_case
from vera_timeline_agent import workflow_v2
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
        "durationFrames": 10,
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

    def add_v2_marker(self, _marker: Any) -> None:
        self._call("add_marker")

    def save_close_reopen(self, _name: str) -> None:
        self._call("save_close_reopen")

    def verify(self, _view: Any) -> tuple[str, ...]:
        self._call("verify")
        return self.verification_discrepancies


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


def test_fractional_rate_preflight_is_read_only_and_build_refuses_before_adapter(
    tmp_path: Path,
) -> None:
    attestation, digest, _ = _make_package(tmp_path, fractional=True)
    adapter = _FakeAdapter()
    preflight = workflow_v2.run_workflow_delivery_v2(
        object(), attestation, digest, adapter_factory=lambda _resolve: adapter
    )
    assert preflight["status"] == "preflight_passed"
    assert "timelineFrameRate" not in adapter.settings
    assert "nativeRateLimitation" in preflight

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


def test_native_source_audio_is_refused_before_adapter_creation(tmp_path: Path) -> None:
    attestation, digest, _ = _make_package(tmp_path, source_audio=True)
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
    class Item:
        def __init__(self) -> None:
            self.properties: dict[str, Any] = {}

        def AddMarker(self, *_args: Any) -> bool:
            return True

        def SetProperties(self, properties: dict[str, Any]) -> bool:
            self.properties = dict(properties)
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
    adapter.assert_current_target = lambda: None
    adapter.media_by_source = {"source": object()}
    adapter.pool = pool
    adapter._v2_sources = {"source": {"kind": "video"}}
    adapter._v2_tracks = ({"id": "video-track", "kind": "video", "index": 1},)
    adapter._v2_timeline = {"width": 1920, "height": 1080}
    adapter.expected_events = {}
    adapter.expected_stamps = {}
    adapter.expected_properties = {}
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
