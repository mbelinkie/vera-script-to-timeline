from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.otio_package import build_otio_package
from vera_timeline_agent.studio_spike import (
    ConnectedFacts,
    LocalFacts,
    PublicResolveAdapter,
    detect_local_capabilities,
    run_delivery,
)
from vera_timeline_agent.studio_spike_cli import main

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPOSITORY_ROOT / "tests/data/slice_0_2/timeline-manifest.json"
MEDIA_ROOT = REPOSITORY_ROOT / "fixtures"


@pytest.fixture
def package(tmp_path: Path) -> Path:
    output = tmp_path / "accepted-package"
    build_otio_package(MANIFEST, MEDIA_ROOT, output)
    return output


@pytest.fixture
def standard_local() -> LocalFacts:
    return LocalFacts(
        os_name="macOS",
        os_version="15.1",
        architecture="x86_64",
        app_path="/Applications/DaVinci Resolve/DaVinci Resolve.app",
        app_installed=True,
        install_source="blackmagic_standard",
        bundle_name="DaVinci Resolve",
        bundle_version="21.0.4",
        bundle_build="21.0.40005",
        mas_receipt=False,
        scripting_module_path="/sdk/DaVinciResolveScript.py",
        scripting_module_installed=True,
        scripting_docs_path="/sdk/README.txt",
        scripting_docs_installed=True,
    )


class RecordingAdapter:
    def __init__(
        self,
        connected: ConnectedFacts | None = None,
        *,
        probe_error: Exception | None = None,
        discrepancies: tuple[str, ...] = (),
    ) -> None:
        self.connected = connected or ConnectedFacts(
            "DaVinci Resolve Studio", "studio", "21.0.4", "21.0.40005", True
        )
        self.probe_error = probe_error
        self.discrepancies = discrepancies
        self.calls: list[tuple[str, Any]] = []

    def connected_facts(self) -> ConnectedFacts:
        self.calls.append(("connected_facts", None))
        return self.connected

    def probe(self, settings: Mapping[str, str]) -> tuple[str, ...]:
        self.calls.append(("probe", dict(settings)))
        if self.probe_error:
            raise self.probe_error
        return ()

    def check_project_name_available(self, name: str) -> None:
        self.calls.append(("check_project_name_available", name))

    def create_project(self, name: str) -> None:
        self.calls.append(("create_project", name))

    def configure_project(self, settings: Mapping[str, str]) -> None:
        self.calls.append(("configure_project", dict(settings)))

    def create_bin(self, name: str) -> None:
        self.calls.append(("create_bin", name))

    def import_media(self, sources: Sequence[tuple[str, Path]]) -> None:
        self.calls.append(("import_media", tuple(sources)))

    def create_timeline(self, name: str) -> None:
        self.calls.append(("create_timeline", name))

    def configure_tracks(self, tracks: Sequence[Mapping[str, Any]]) -> None:
        self.calls.append(("configure_tracks", tuple(dict(track) for track in tracks)))

    def place_event(self, event: Mapping[str, Any]) -> None:
        self.calls.append(("place_event", dict(event)))

    def insert_fusion_title(self, title_name: str, record_frame: int) -> None:
        self.calls.append(("insert_fusion_title", (title_name, record_frame)))

    def add_marker(self, marker: Mapping[str, Any], custom_data: str) -> None:
        self.calls.append(("add_marker", (dict(marker), custom_data)))

    def save_close_reopen(self, project_name: str) -> None:
        self.calls.append(("save_close_reopen", project_name))

    def verify(self, manifest: Mapping[str, Any]) -> tuple[str, ...]:
        self.calls.append(("verify", manifest["id"]))
        return self.discrepancies


def test_detects_objective_local_facts_without_import_or_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = tmp_path / "DaVinci Resolve.app"
    contents = app / "Contents"
    contents.mkdir(parents=True)
    import plistlib

    with (contents / "Info.plist").open("wb") as stream:
        plistlib.dump(
            {
                "CFBundleDisplayName": "DaVinci Resolve",
                "CFBundleShortVersionString": "21.0.4",
                "CFBundleVersion": "21.0.40005",
            },
            stream,
        )
    sdk = tmp_path / "Scripting"
    (sdk / "Modules").mkdir(parents=True)
    (sdk / "Modules/DaVinciResolveScript.py").write_text("raise AssertionError")
    (sdk / "README.txt").write_text("installed docs")
    monkeypatch.setattr("platform.mac_ver", lambda: ("15.1", ("", "", ""), ""))
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    facts = detect_local_capabilities(app, sdk)
    assert facts.install_source == "blackmagic_standard"
    assert facts.bundle_version == "21.0.4"
    assert facts.bundle_build == "21.0.40005"
    assert facts.mas_receipt is False
    assert facts.scripting_module_installed and facts.scripting_docs_installed


def test_free_never_constructs_or_invokes_resolve_adapter(
    package: Path, standard_local: LocalFacts
) -> None:
    def forbidden(_: LocalFacts) -> RecordingAdapter:
        raise AssertionError("Free delivery imported or connected to Resolve")

    result = run_delivery(
        package, "free", adapter_factory=forbidden, local_facts=standard_local
    )
    assert result.status == "ready_to_import"
    assert "not imported, connected, or invoked" in result.message


def test_studio_rejects_nonzero_timeline_start_before_connection(
    tmp_path: Path, standard_local: LocalFacts
) -> None:
    manifest = json.loads(MANIFEST.read_text())
    manifest["timeline"]["startFrame"] = 100
    for event in manifest["events"]:
        event["recordRange"]["startFrame"] += 100
    for transition in manifest["transitions"]:
        transition["atFrame"] += 100
    for marker in manifest["markers"]:
        marker["frame"] += 100
    adjusted = tmp_path / "nonzero-start.json"
    adjusted.write_text(json.dumps(manifest))
    package = tmp_path / "nonzero-package"
    build_otio_package(adjusted, MEDIA_ROOT, package)

    def forbidden(_: LocalFacts) -> RecordingAdapter:
        raise AssertionError("nonzero start crossed the pre-connection stop")

    result = run_delivery(
        package,
        "studio",
        adapter_factory=forbidden,
        local_facts=standard_local,
    )
    assert result.status == "stopped_safely"
    assert "frame-zero" in result.message


@pytest.mark.parametrize(
    ("changes", "needle"),
    [
        ({"app_installed": False}, "not installed"),
        (
            {"install_source": "mac_app_store", "mas_receipt": True},
            "Mac App Store",
        ),
        ({"scripting_module_installed": False}, "module is missing"),
        ({"scripting_docs_installed": False}, "documentation is missing"),
    ],
)
def test_local_safety_stops_before_adapter_factory(
    package: Path,
    standard_local: LocalFacts,
    changes: dict[str, Any],
    needle: str,
) -> None:
    values = standard_local.__dict__ | changes

    def forbidden(_: LocalFacts) -> RecordingAdapter:
        raise AssertionError("adapter factory crossed a local safety stop")

    result = run_delivery(
        package,
        "studio",
        adapter_factory=forbidden,
        local_facts=LocalFacts(**values),
    )
    assert result.status == "stopped_safely"
    assert needle in result.message


@pytest.mark.parametrize(
    "connected",
    [
        ConnectedFacts("DaVinci Resolve", "free", "21.0.4", "21.0.40005", True),
        ConnectedFacts("DaVinci Resolve Studio", "studio", "21.0.4", "5", False),
    ],
)
def test_connected_safety_stops_after_observation_but_before_mutation(
    package: Path, standard_local: LocalFacts, connected: ConnectedFacts
) -> None:
    adapter = RecordingAdapter(connected)
    result = run_delivery(
        package,
        "studio",
        action="build",
        adapter_factory=lambda _: adapter,
        local_facts=standard_local,
    )
    assert result.status == "stopped_safely"
    assert [call[0] for call in adapter.calls] == ["connected_facts"]


def test_connection_and_probe_failures_are_actionable_and_nonmutating(
    package: Path, standard_local: LocalFacts
) -> None:
    connection = run_delivery(
        package,
        "studio",
        adapter_factory=lambda _: (_ for _ in ()).throw(RuntimeError("disabled")),
        local_facts=standard_local,
    )
    assert connection.status == "stopped_safely"
    assert "enable local external scripting" in connection.message
    adapter = RecordingAdapter(probe_error=RuntimeError("unsupported response"))
    probe = run_delivery(
        package,
        "studio",
        action="build",
        adapter_factory=lambda _: adapter,
        local_facts=standard_local,
    )
    assert probe.status == "stopped_safely"
    assert [call[0] for call in adapter.calls] == ["connected_facts", "probe"]


def test_preflight_is_nonmutating_and_surfaces_public_api_gap(
    package: Path, standard_local: LocalFacts
) -> None:
    adapter = RecordingAdapter()
    result = run_delivery(
        package,
        "studio",
        adapter_factory=lambda _: adapter,
        local_facts=standard_local,
    )
    assert result.status == "preflight_passed"
    assert [call[0] for call in adapter.calls] == [
        "connected_facts",
        "probe",
        "check_project_name_available",
    ]
    assert "cannot enumerate stock Fusion titles" in result.manual_completion[0]


def test_preflight_reports_older_studio_without_inventing_support_minimum(
    package: Path, standard_local: LocalFacts
) -> None:
    adapter = RecordingAdapter(
        ConnectedFacts("DaVinci Resolve Studio", "studio", "20.3.2", "9", True)
    )
    result = run_delivery(
        package,
        "studio",
        adapter_factory=lambda _: adapter,
        local_facts=standard_local,
    )
    assert result.status == "preflight_passed"
    assert result.connected is not None and result.connected.version == "20.3.2"


def test_project_name_collision_stops_before_mutation(
    package: Path, standard_local: LocalFacts
) -> None:
    class CollisionAdapter(RecordingAdapter):
        def check_project_name_available(self, name: str) -> None:
            super().check_project_name_available(name)
            raise RuntimeError("project already exists")

    adapter = CollisionAdapter()
    result = run_delivery(
        package,
        "studio",
        action="build",
        adapter_factory=lambda _: adapter,
        local_facts=standard_local,
        project_name="Existing project",
    )
    assert result.status == "stopped_safely"
    assert [name for name, _ in adapter.calls] == [
        "connected_facts",
        "probe",
        "check_project_name_available",
    ]


def test_success_has_exact_order_frames_settings_tracks_marker_and_reopen(
    package: Path, standard_local: LocalFacts
) -> None:
    adapter = RecordingAdapter()
    result = run_delivery(
        package,
        "studio",
        action="build",
        adapter_factory=lambda _: adapter,
        local_facts=standard_local,
        project_name="Unique producer-approved spike",
    )
    assert result.status == "verified" and result.verified
    names = [call[0] for call in adapter.calls]
    assert names == [
        "connected_facts",
        "probe",
        "check_project_name_available",
        "create_project",
        "configure_project",
        "create_bin",
        "create_bin",
        "import_media",
        "create_timeline",
        "configure_tracks",
        *("place_event" for _ in range(5)),
        "insert_fusion_title",
        "add_marker",
        "save_close_reopen",
        "verify",
    ]
    settings = next(
        value for name, value in adapter.calls if name == "configure_project"
    )
    assert settings == {
        "timelineFrameRate": "23.976",
        "timelinePlaybackFrameRate": "23.976",
        "timelineResolutionWidth": "1920",
        "timelineResolutionHeight": "1080",
        "timelineSampleRate": "48000",
    }
    events = [value for name, value in adapter.calls if name == "place_event"]
    assert [event["recordRange"]["startFrame"] for event in events] == [
        0,
        18,
        36,
        54,
        0,
    ]
    assert [event.get("sourceRange", {}).get("startFrame", 0) for event in events] == [
        2,
        4,
        6,
        0,
        0,
    ]
    assert [event["recordRange"]["durationFrames"] for event in events] == [
        18,
        18,
        18,
        18,
        72,
    ]
    tracks = next(value for name, value in adapter.calls if name == "configure_tracks")
    assert [(track["kind"], track["index"], track["name"]) for track in tracks] == [
        (track["kind"], track["index"], track["name"])
        for track in json.loads(MANIFEST.read_text())["tracks"]
    ]
    marker, custom = next(
        value for name, value in adapter.calls if name == "add_marker"
    )
    assert marker["frame"] == 33
    assert json.loads(custom)["markerId"] == marker["id"]


def test_verification_discrepancies_remain_explicit(
    package: Path, standard_local: LocalFacts
) -> None:
    adapter = RecordingAdapter(discrepancies=("video track 3 count mismatch",))
    result = run_delivery(
        package,
        "studio",
        action="build",
        adapter_factory=lambda _: adapter,
        local_facts=standard_local,
    )
    assert result.status == "verification_failed"
    assert not result.verified
    assert result.discrepancies == ("video track 3 count mismatch",)


def test_adjusted_manifest_settings_and_track_map_flow_without_constants(
    tmp_path: Path, standard_local: LocalFacts
) -> None:
    manifest = json.loads(MANIFEST.read_text())
    manifest["timeline"].update(
        {"width": 1280, "height": 720, "audioSampleRate": 44100}
    )
    manifest["tracks"][2]["name"] = "Picture inserts — adjusted"
    manifest["tracks"][5]["name"] = "Temporary voice — adjusted"
    adjusted_manifest = tmp_path / "adjusted.json"
    adjusted_manifest.write_text(json.dumps(manifest))
    package = tmp_path / "adjusted-package"
    build_otio_package(adjusted_manifest, MEDIA_ROOT, package)
    adapter = RecordingAdapter()
    result = run_delivery(
        package,
        "studio",
        action="build",
        adapter_factory=lambda _: adapter,
        local_facts=standard_local,
    )
    assert result.status == "verified"
    settings = next(
        value for name, value in adapter.calls if name == "configure_project"
    )
    assert settings["timelineResolutionWidth"] == "1280"
    assert settings["timelineResolutionHeight"] == "720"
    assert settings["timelineSampleRate"] == "44100"
    tracks = next(value for name, value in adapter.calls if name == "configure_tracks")
    assert tracks[2]["name"] == "Picture inserts — adjusted"
    assert tracks[5]["name"] == "Temporary voice — adjusted"


def test_post_mutation_failure_reports_possible_partial_project(
    package: Path, standard_local: LocalFacts
) -> None:
    class FailingAdapter(RecordingAdapter):
        def configure_project(self, settings: Mapping[str, str]) -> None:
            super().configure_project(settings)
            raise RuntimeError("injected project-setting failure")

    adapter = FailingAdapter()
    result = run_delivery(
        package,
        "studio",
        action="build",
        adapter_factory=lambda _: adapter,
        local_facts=standard_local,
        project_name="Partial project test",
    )
    assert result.status == "mutation_failed"
    assert "partial project may remain" in result.message
    assert [name for name, _ in adapter.calls] == [
        "connected_facts",
        "probe",
        "check_project_name_available",
        "create_project",
        "configure_project",
    ]


def test_public_adapter_sets_and_checks_frame_zero_timeline_start() -> None:
    class Timeline:
        def __init__(self) -> None:
            self.timecode: str | None = None

        def SetStartTimecode(self, value: str) -> bool:
            self.timecode = value
            return True

        def GetStartFrame(self) -> int:
            return 0

    timeline = Timeline()

    class Pool:
        def CreateEmptyTimeline(self, name: str) -> Timeline:
            assert name == "VERA test"
            return timeline

    adapter = PublicResolveAdapter(object())
    adapter.pool = Pool()
    adapter.create_timeline("VERA test")
    assert adapter.timeline is timeline
    assert timeline.timecode == "00:00:00:00"


def test_public_import_maps_reordered_results_by_documented_file_path(
    tmp_path: Path,
) -> None:
    one = (tmp_path / "one.mov").resolve()
    two = (tmp_path / "two.wav").resolve()

    class Item:
        def __init__(self, path: Path, media_id: str) -> None:
            self.path = path
            self.media_id = media_id

        def GetClipProperty(self, name: str) -> str:
            assert name == "File Path"
            return str(self.path)

        def GetMediaId(self) -> str:
            return self.media_id

    first = Item(one, "media-one")
    second = Item(two, "media-two")

    class Pool:
        def ImportMedia(self, paths: list[str]) -> list[Item]:
            assert paths == [str(one), str(two)]
            return [second, first]

    adapter = PublicResolveAdapter(object())
    adapter.pool = Pool()
    adapter.import_media([("source-one", one), ("source-two", two)])
    assert adapter.media_by_source == {
        "source-one": first,
        "source-two": second,
    }
    assert adapter.media_id_by_source == {
        "source-one": "media-one",
        "source-two": "media-two",
    }


def test_public_adapter_translates_manifest_ranges_to_documented_clip_info() -> None:
    class Pool:
        def __init__(self) -> None:
            self.values: list[list[dict[str, Any]]] = []

        def AppendToTimeline(self, values: list[dict[str, Any]]) -> list[object]:
            self.values.append(values)
            return [object()]

    manifest = json.loads(MANIFEST.read_text())
    pool = Pool()
    adapter = PublicResolveAdapter(object())
    adapter.pool = pool
    adapter.timeline = object()
    adapter.media_by_source = {
        source["id"]: f"media:{source['id']}" for source in manifest["sources"]
    }
    adapter._track_id_map = {
        track["id"]: track["index"] for track in manifest["tracks"]
    }
    for event in manifest["events"]:
        adapter.place_event(event)
    assert [call[0]["startFrame"] for call in pool.values] == [2, 4, 6, 0, 0]
    assert [call[0]["endFrame"] for call in pool.values] == [19, 21, 23, 17, 71]
    assert [call[0]["recordFrame"] for call in pool.values] == [0, 18, 36, 54, 0]
    assert [call[0]["trackIndex"] for call in pool.values] == [3, 3, 3, 3, 1]
    assert [call[0]["mediaType"] for call in pool.values] == [1, 1, 1, 1, 2]


def test_public_verifier_checks_media_identity_and_observable_result() -> None:
    custom = json.dumps(
        {"markerId": "marker-1", "provenance": {"kind": "test"}},
        sort_keys=True,
        separators=(",", ":"),
    )
    marker_info = {
        "color": "Blue",
        "duration": 1,
        "note": "note",
        "name": "review",
        "customData": custom,
    }

    class Media:
        def __init__(self, media_id: str) -> None:
            self.media_id = media_id

        def GetMediaId(self) -> str:
            return self.media_id

    class Item:
        def __init__(self, unique_id: str, media_id: str | None = None) -> None:
            self.unique_id = unique_id
            self.media = Media(media_id) if media_id is not None else None

        def GetUniqueId(self) -> str:
            return self.unique_id

        def GetStart(self, _: bool) -> int:
            return 0

        def GetDuration(self, _: bool) -> int:
            return 18

        def GetSourceStartFrame(self) -> int:
            return 2

        def GetMediaPoolItem(self) -> Media | None:
            return self.media

    title = Item("title-id")
    event = Item("event-id", "wrong-media-id")

    class Timeline:
        def GetName(self) -> str:
            return "Timeline"

        def GetStartFrame(self) -> int:
            return 0

        def GetEndFrame(self) -> int:
            return 18

        def GetTrackName(self, kind: str, index: int) -> str:
            assert (kind, index) == ("video", 2)
            return "Pictures"

        def GetTrackCount(self, kind: str) -> int:
            return 2 if kind == "video" else 0

        def GetItemListInTrack(self, kind: str, index: int) -> list[Item]:
            assert kind == "video"
            return {1: [title], 2: [event]}[index]

        def GetMarkers(self) -> dict[int, dict[str, Any]]:
            return {3: marker_info}

        def GetMarkerByCustomData(self, value: str) -> dict[str, Any]:
            return marker_info if value == custom else {}

    class Project:
        def GetName(self) -> str:
            return "Project"

        def GetSetting(self, key: str) -> str:
            assert key == "timelineFrameRate"
            return "24"

    class Pool:
        def GetRootFolder(self) -> object:
            return object()

    manifest = {
        "timeline": {"startFrame": 0, "durationFrames": 18},
        "tracks": [{"id": "pictures", "kind": "video", "index": 2, "name": "Pictures"}],
        "events": [
            {
                "id": "event-1",
                "sourceId": "source-1",
                "trackId": "pictures",
                "trackKind": "video",
                "recordRange": {"startFrame": 0, "durationFrames": 18},
                "sourceRange": {"startFrame": 2, "durationFrames": 18},
            }
        ],
        "markers": [
            {
                "id": "marker-1",
                "frame": 3,
                "color": "Blue",
                "name": "review",
                "note": "note",
                "provenance": {"kind": "test"},
            }
        ],
    }
    adapter = PublicResolveAdapter(object())
    adapter.project = Project()
    adapter.pool = Pool()
    adapter.timeline = Timeline()
    adapter.expected_project_name = "Project"
    adapter.expected_timeline_name = "Timeline"
    adapter.expected_settings = {"timelineFrameRate": "24"}
    adapter.media_id_by_source = {"source-1": "expected-media-id"}
    adapter.fusion_title_id = "title-id"

    assert adapter.verify(manifest) == (
        "event event-1: source media identity mismatch",
    )
    event.media = Media("expected-media-id")
    assert adapter.verify(manifest) == ()


def test_cli_detect_does_not_need_resolve(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing.app"
    assert main(["detect", "--app-path", str(missing)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["app_installed"] is False
    assert output["install_source"] == "missing"
