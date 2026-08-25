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

    def probe(self) -> tuple[str, ...]:
        self.calls.append(("probe", None))
        if self.probe_error:
            raise self.probe_error
        return ()

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
    assert [call[0] for call in adapter.calls] == ["connected_facts", "probe"]
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


def test_cli_detect_does_not_need_resolve(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing.app"
    assert main(["detect", "--app-path", str(missing)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["app_installed"] is False
    assert output["install_source"] == "missing"
