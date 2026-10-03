from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from vera_timeline_agent.studio_assembly import run_studio_assembly
from vera_timeline_agent.studio_assembly_acceptance import (
    build_studio_assembly_acceptance_package,
)
from vera_timeline_agent.studio_spike import (
    BLACKMAGIC_BUNDLE_ID,
    ConnectedFacts,
    LocalFacts,
    PublicResolveAdapter,
)

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _package(tmp_path: Path) -> Path:
    output = tmp_path / "Studio assembly acceptance project"
    return build_studio_assembly_acceptance_package(output).project_root


def test_acceptance_package_uses_the_resolve_production_baseline(
    tmp_path: Path,
) -> None:
    result = build_studio_assembly_acceptance_package(tmp_path / "acceptance")
    manifest = _load(result.manifest_path)

    assert manifest["buildId"] == "13000000-0000-4000-8000-000000000036"
    assert manifest["timeline"]["width"] == 1920
    assert manifest["timeline"]["height"] == 1080


def _local() -> LocalFacts:
    return LocalFacts(
        os_name="macOS",
        os_version="15.1",
        architecture="arm64",
        app_path="/Applications/DaVinci Resolve/DaVinci Resolve.app",
        app_installed=True,
        install_source="blackmagic_package_receipt",
        bundle_name="DaVinci Resolve",
        bundle_identifier=BLACKMAGIC_BUNDLE_ID,
        bundle_version="21.0.4",
        bundle_build="21.0.40005",
        mas_receipt=False,
        package_receipt_id="com.blackmagic-design.ManifestLite",
        package_receipt_version="21.0.4",
        scripting_module_path="/sdk/DaVinciResolveScript.py",
        scripting_module_installed=True,
        scripting_docs_path="/sdk/README.txt",
        scripting_docs_installed=True,
    )


class RecordingAdapter:
    def __init__(
        self,
        *,
        connected: ConnectedFacts | None = None,
        discrepancies: tuple[str, ...] = (),
    ) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.connected = connected or ConnectedFacts(
            "DaVinci Resolve Studio", "studio", "21.0.4", "5", True
        )
        self.discrepancies = discrepancies

    def connected_facts(self) -> ConnectedFacts:
        self.calls.append(("connected_facts", None))
        return self.connected

    def probe(self, settings: Mapping[str, str]) -> tuple[str, ...]:
        self.calls.append(("probe", dict(settings)))
        return ("The public API cannot prove a mutation-only call during preflight.",)

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

    def place_events(self, events: Sequence[Mapping[str, Any]]) -> None:
        self.calls.append(("place_events", tuple(dict(event) for event in events)))

    def add_marker(self, marker: Mapping[str, Any], custom_data: str) -> None:
        self.calls.append(("add_marker", (dict(marker), custom_data)))

    def save_close_reopen(self, project_name: str) -> None:
        self.calls.append(("save_close_reopen", project_name))

    def verify(self, manifest: Mapping[str, Any]) -> tuple[str, ...]:
        self.calls.append(("verify", manifest["id"]))
        return self.discrepancies


def test_unverified_package_stops_before_resolve_connection(tmp_path: Path) -> None:
    project = _package(tmp_path)
    receipt = next((project / "Builds").glob("*/package-verification.json"))
    receipt.write_bytes(receipt.read_bytes() + b"tamper")

    def forbidden(_: LocalFacts) -> RecordingAdapter:
        raise AssertionError("unverified package reached the Resolve adapter")

    result = run_studio_assembly(
        project, local_facts=_local(), adapter_factory=forbidden
    )

    assert result.status == "stopped_safely"
    assert "not a verified ready_to_import package" in result.message


def test_preflight_is_nonmutating_and_names_target_from_build_identity(
    tmp_path: Path,
) -> None:
    project = _package(tmp_path)
    adapter = RecordingAdapter()

    result = run_studio_assembly(
        project, local_facts=_local(), adapter_factory=lambda _: adapter
    )

    assert result.status == "preflight_passed"
    assert [name for name, _ in adapter.calls] == [
        "connected_facts",
        "probe",
        "check_project_name_available",
    ]
    assert result.project_name == f"VERA Studio build {result.build_id}"
    assert result.timeline_name == f"VERA build {result.build_id}"
    assert "never falls back to Resolve UI automation" in result.manual_completion[1]


def test_preflight_accepts_the_recorded_21_1_studio_baseline(
    tmp_path: Path,
) -> None:
    project = _package(tmp_path)
    adapter = RecordingAdapter(
        connected=ConnectedFacts(
            "DaVinci Resolve Studio", "studio", "21.1.0", "14", True
        )
    )
    local = LocalFacts(
        **(
            _local().__dict__
            | {
                "bundle_version": "21.1.0",
                "bundle_build": "21.1.00014",
                "install_source": "unknown_non_mas",
                "package_receipt_version": "21.0.4",
                "scripting_docs_installed": False,
            }
        )
    )

    result = run_studio_assembly(
        project, local_facts=local, adapter_factory=lambda _: adapter
    )

    assert result.status == "preflight_passed"
    assert [name for name, _ in adapter.calls] == [
        "connected_facts",
        "probe",
        "check_project_name_available",
    ]


def test_build_places_the_verified_package_and_retains_discrepancies(
    tmp_path: Path,
) -> None:
    project = _package(tmp_path)
    manifest = _load(next((project / "Builds").glob("*/timeline-manifest.json")))
    adapter = RecordingAdapter(discrepancies=("marker mismatch",))

    result = run_studio_assembly(
        project,
        action="build",
        local_facts=_local(),
        adapter_factory=lambda _: adapter,
    )

    assert result.status == "verification_failed"
    assert result.discrepancies == ("marker mismatch",)
    assert [name for name, _ in adapter.calls] == [
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
        "place_events",
        "add_marker",
        "save_close_reopen",
        "verify",
    ]
    sources = next(value for name, value in adapter.calls if name == "import_media")
    assert {source_id for source_id, _ in sources} == {
        source["id"] for source in manifest["sources"]
    }
    assert next(
        value for name, value in adapter.calls if name == "place_events"
    ) == tuple(manifest["events"])


def test_collision_stops_before_mutation_and_mutation_failure_keeps_target(
    tmp_path: Path,
) -> None:
    project = _package(tmp_path)

    class CollisionAdapter(RecordingAdapter):
        def check_project_name_available(self, name: str) -> None:
            super().check_project_name_available(name)
            raise RuntimeError("target exists")

    collision = CollisionAdapter()
    stopped = run_studio_assembly(
        project,
        action="build",
        local_facts=_local(),
        adapter_factory=lambda _: collision,
    )
    assert stopped.status == "stopped_safely"
    assert [name for name, _ in collision.calls] == [
        "connected_facts",
        "probe",
        "check_project_name_available",
    ]

    class FailingAdapter(RecordingAdapter):
        def configure_project(self, settings: Mapping[str, str]) -> None:
            super().configure_project(settings)
            raise RuntimeError("setting rejected")

    failed = FailingAdapter()
    retained = run_studio_assembly(
        project,
        action="build",
        local_facts=_local(),
        adapter_factory=lambda _: failed,
    )
    assert retained.status == "mutation_failed"
    assert retained.project_name == f"VERA Studio build {retained.build_id}"
    assert "partial project may remain" in retained.message


def test_public_verifier_allows_manifest_only_assembly_without_fusion_title() -> None:
    class Project:
        def GetName(self) -> str:
            return "Project"

    class Timeline:
        def GetName(self) -> str:
            return "Timeline"

        def GetStartFrame(self) -> int:
            return 0

        def GetEndFrame(self) -> int:
            return 0

        def GetTrackCount(self, _: str) -> int:
            return 0

        def GetMarkers(self) -> dict[int, object]:
            return {}

    class Pool:
        def GetRootFolder(self) -> object:
            return object()

    adapter = PublicResolveAdapter(object())
    adapter.project = Project()
    adapter.timeline = Timeline()
    adapter.pool = Pool()
    adapter.expected_project_name = "Project"
    adapter.expected_timeline_name = "Timeline"
    assert (
        adapter.verify(
            {
                "timeline": {"startFrame": 0, "durationFrames": 0},
                "tracks": [],
                "events": [],
                "markers": [],
            }
        )
        == ()
    )


def test_public_adapter_applies_the_still_range_rule_to_placeholder_events() -> None:
    class Media:
        def __init__(self) -> None:
            self.marks: list[tuple[object, ...]] = []

        def SetMarkInOut(self, *values: object) -> bool:
            self.marks.append(("set", *values))
            return True

        def ClearMarkInOut(self, *values: object) -> bool:
            self.marks.append(("clear", *values))
            return True

    class Pool:
        def __init__(self) -> None:
            self.values: list[dict[str, Any]] = []

        def AppendToTimeline(self, values: list[dict[str, Any]]) -> list[object]:
            self.values.extend(values)
            return [object()]

    media = Media()
    pool = Pool()
    adapter = PublicResolveAdapter(object())
    adapter.pool = pool
    adapter.observed_connected = ConnectedFacts(
        "DaVinci Resolve Studio", "studio", "21.1.0", "14", True
    )
    adapter.media_by_source = {"placeholder-source": media}
    adapter._track_id_map = {"video-placeholders": 5}
    adapter.place_events(
        [
            {
                "id": "placeholder-event",
                "kind": "placeholder",
                "sourceId": "placeholder-source",
                "trackId": "video-placeholders",
                "recordRange": {"startFrame": 0, "durationFrames": 72},
            }
        ]
    )

    assert media.marks == [("set", 0, 72, "video"), ("clear", "video")]
    assert pool.values[0]["endFrame"] == 72
