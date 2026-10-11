from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from vera_timeline_agent import workflow_delivery
from vera_timeline_agent.studio_assembly_acceptance import (
    build_studio_assembly_acceptance_package,
)
from vera_timeline_agent.studio_spike import ConnectedFacts
from vera_timeline_agent.workflow_delivery_cli import attest_package
from vera_timeline_agent.workflow_package import (
    WorkflowPackageError,
    sha256,
)

pytestmark = pytest.mark.slow
ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class VerifiedFixture:
    package: Path
    attestation: Path
    attestation_sha256: str


@pytest.fixture(scope="module")
def verified_fixture(tmp_path_factory: pytest.TempPathFactory) -> VerifiedFixture:
    root = tmp_path_factory.mktemp("workflow-delivery")
    package = build_studio_assembly_acceptance_package(root / "package").project_root
    attestation = root / "attestation.json"
    attest_package(package, attestation)
    return VerifiedFixture(package, attestation, sha256(attestation))


def _copy_fixture(tmp_path: Path, fixture: VerifiedFixture) -> VerifiedFixture:
    package = tmp_path / "package"
    shutil.copytree(fixture.package, package)
    attestation = tmp_path / "attestation.json"
    attest_package(package, attestation)
    return VerifiedFixture(package, attestation, sha256(attestation))


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _tamper_package(package: Path) -> None:
    manifest = next((package / "Builds").glob("*/timeline-manifest.json"))
    manifest.write_bytes(manifest.read_bytes() + b"\n")


def _attestation_value(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _write_attestation(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


class RecordingAdapter:
    def __init__(
        self,
        *,
        connected: ConnectedFacts | None = None,
        discrepancies: tuple[str, ...] = (),
        fail_on: str | None = None,
        mutate_after: str | None = None,
        mutate: Callable[[], None] | None = None,
    ) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.connected = connected or ConnectedFacts(
            "DaVinci Resolve Studio", "studio", "21.1.0", "14", True
        )
        self.discrepancies = discrepancies
        self.fail_on = fail_on
        self.mutate_after = mutate_after
        self.mutate = mutate

    def _record(self, name: str, *arguments: Any) -> None:
        self.calls.append((name, arguments))
        if self.mutate_after == name and self.mutate is not None:
            self.mutate()
        if self.fail_on == name:
            raise RuntimeError(f"{name} failed")

    def connected_facts(self) -> ConnectedFacts:
        self._record("connected_facts")
        return self.connected

    def probe(self, settings: Mapping[str, str]) -> tuple[str, ...]:
        self._record("probe", dict(settings))
        return ("probe gap",)

    def check_project_name_available(self, name: str) -> None:
        self._record("check_project_name_available", name)

    def create_project(self, name: str) -> None:
        self._record("create_project", name)

    def configure_project(self, settings: Mapping[str, str]) -> None:
        self._record("configure_project", dict(settings))

    def create_bin(self, name: str) -> None:
        self._record("create_bin", name)

    def import_media(self, sources: Sequence[tuple[str, Path]]) -> None:
        self._record("import_media", tuple(sources))

    def create_timeline(self, name: str) -> None:
        self._record("create_timeline", name)

    def configure_tracks(self, tracks: Sequence[Mapping[str, Any]]) -> None:
        self._record("configure_tracks", tuple(dict(track) for track in tracks))

    def place_events(self, events: Sequence[Mapping[str, Any]]) -> None:
        self._record("place_events", tuple(dict(event) for event in events))

    def add_marker(self, marker: Mapping[str, Any], custom_data: str) -> None:
        self._record("add_marker", (dict(marker), custom_data))

    def save_close_reopen(self, project_name: str) -> None:
        self._record("save_close_reopen", project_name)

    def verify(self, manifest: Mapping[str, Any]) -> tuple[str, ...]:
        self._record("verify", manifest["id"])
        return self.discrepancies


def _use_adapter(monkeypatch: pytest.MonkeyPatch, adapter: RecordingAdapter) -> None:
    monkeypatch.setattr(
        workflow_delivery, "PublicResolveAdapter", lambda _resolve: adapter
    )


def _run(
    fixture: VerifiedFixture,
    *,
    adapter: RecordingAdapter,
    monkeypatch: pytest.MonkeyPatch,
    action: str = "build",
    authorize: bool = True,
    external_scripting: str | None = "None",
) -> dict[str, Any]:
    _use_adapter(monkeypatch, adapter)
    return workflow_delivery.run_workflow_delivery(
        object(),
        fixture.attestation,
        fixture.attestation_sha256,
        action=action,
        authorize_new_nonproduction=authorize,
        external_scripting=external_scripting,
    )


def test_attestation_output_is_immutable_before_delivery(
    verified_fixture: VerifiedFixture,
) -> None:
    before = verified_fixture.attestation.read_bytes()

    with pytest.raises(WorkflowPackageError):
        attest_package(verified_fixture.package, verified_fixture.attestation)

    assert verified_fixture.attestation.read_bytes() == before


@pytest.mark.parametrize(
    "kind", ["tampered", "missing", "hash_mismatch", "false_ready"]
)
def test_invalid_attestation_stops_before_adapter(
    tmp_path: Path,
    verified_fixture: VerifiedFixture,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    if kind == "missing":
        attestation = tmp_path / "missing.json"
        expected_hash = "0" * 64
    else:
        attestation = tmp_path / f"{kind}.json"
        value = _attestation_value(verified_fixture.attestation)
        if kind == "tampered":
            value["projectName"] = "VERA Delivery tampered"
        elif kind == "false_ready":
            value["status"] = "verification_failed"
        _write_attestation(attestation, value)
        expected_hash = "0" * 64 if kind == "hash_mismatch" else sha256(attestation)

    def forbidden(_resolve: Any) -> RecordingAdapter:
        raise AssertionError("invalid attestation reached the native adapter")

    monkeypatch.setattr(workflow_delivery, "PublicResolveAdapter", forbidden)
    result = workflow_delivery.run_workflow_delivery(
        object(), attestation, expected_hash, action="preflight"
    )

    assert result["status"] == "stopped_safely"
    assert result["verified"] is False
    assert result["partialTargetRetained"] is False
    assert "connected" not in result


@pytest.mark.parametrize(
    ("authorize", "external_scripting"),
    [(False, "None"), (True, None), (True, "Lua")],
)
def test_build_requires_both_operator_authorizations(
    verified_fixture: VerifiedFixture,
    monkeypatch: pytest.MonkeyPatch,
    authorize: bool,
    external_scripting: str | None,
) -> None:
    adapter = RecordingAdapter()
    result = _run(
        verified_fixture,
        adapter=adapter,
        monkeypatch=monkeypatch,
        authorize=authorize,
        external_scripting=external_scripting,
    )

    assert result["status"] == "stopped_safely"
    assert adapter.calls == []


def test_missing_injected_object_stops_before_native_adapter(
    verified_fixture: VerifiedFixture,
) -> None:
    result = workflow_delivery.run_workflow_delivery(
        None,
        verified_fixture.attestation,
        verified_fixture.attestation_sha256,
        action="preflight",
    )

    assert result["status"] == "stopped_safely"
    assert "Resolve did not inject" in result["message"]


@pytest.mark.parametrize(
    "connected",
    [
        ConnectedFacts("DaVinci Resolve", "free", "21.1.0", "14", True),
        ConnectedFacts("DaVinci Resolve Studio", "studio", "20.0.0", "1", True),
        ConnectedFacts(
            "DaVinci Resolve Studio", "studio", "21.1.0", "14", True, "beta"
        ),
    ],
)
def test_unsupported_object_or_version_stops_before_probe(
    verified_fixture: VerifiedFixture,
    monkeypatch: pytest.MonkeyPatch,
    connected: ConnectedFacts,
) -> None:
    adapter = RecordingAdapter(connected=connected)
    result = _run(
        verified_fixture,
        adapter=adapter,
        monkeypatch=monkeypatch,
        action="preflight",
        authorize=False,
        external_scripting=None,
    )

    assert result["status"] == "stopped_safely"
    assert [name for name, _ in adapter.calls] == ["connected_facts"]


def test_preflight_is_read_only_and_uses_attested_target_names(
    verified_fixture: VerifiedFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = RecordingAdapter()
    result = _run(
        verified_fixture,
        adapter=adapter,
        monkeypatch=monkeypatch,
        action="preflight",
        authorize=False,
        external_scripting=None,
    )

    assert result["status"] == "preflight_passed"
    assert result["verified"] is False
    assert [name for name, _ in adapter.calls] == [
        "connected_facts",
        "probe",
        "check_project_name_available",
    ]
    assert result["projectName"] == result["timelineName"]
    assert result["connected"]["version"] == "21.1.0"


@pytest.mark.parametrize(("version", "build"), [("21.1.0", "14"), ("21.1.1", "10")])
def test_preflight_accepts_supported_studio_identities(
    verified_fixture: VerifiedFixture,
    monkeypatch: pytest.MonkeyPatch,
    version: str,
    build: str,
) -> None:
    result = _run(
        verified_fixture,
        adapter=RecordingAdapter(
            connected=ConnectedFacts(
                "DaVinci Resolve Studio", "studio", version, build, True
            )
        ),
        monkeypatch=monkeypatch,
        action="preflight",
        authorize=False,
        external_scripting=None,
    )

    assert result["status"] == "preflight_passed"


def test_build_uses_exact_mutation_order(
    verified_fixture: VerifiedFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = RecordingAdapter()
    result = _run(
        verified_fixture,
        adapter=adapter,
        monkeypatch=monkeypatch,
    )

    assert result["status"] == "verified"
    assert result["verified"] is True
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


def test_collision_stops_before_project_creation(
    verified_fixture: VerifiedFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = RecordingAdapter(fail_on="check_project_name_available")
    result = _run(
        verified_fixture,
        adapter=adapter,
        monkeypatch=monkeypatch,
    )

    assert result["status"] == "stopped_safely"
    assert result["partialTargetRetained"] is False
    assert [name for name, _ in adapter.calls] == [
        "connected_facts",
        "probe",
        "check_project_name_available",
    ]


def test_package_drift_during_preflight_stops_before_create(
    tmp_path: Path,
    verified_fixture: VerifiedFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _copy_fixture(tmp_path, verified_fixture)
    adapter = RecordingAdapter(
        mutate_after="probe", mutate=lambda: _tamper_package(fixture.package)
    )
    result = _run(fixture, adapter=adapter, monkeypatch=monkeypatch)

    assert result["status"] == "stopped_safely"
    assert result["partialTargetRetained"] is False
    assert [name for name, _ in adapter.calls] == [
        "connected_facts",
        "probe",
        "check_project_name_available",
    ]


def test_package_drift_after_create_retains_named_partial_target(
    tmp_path: Path,
    verified_fixture: VerifiedFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _copy_fixture(tmp_path, verified_fixture)
    adapter = RecordingAdapter(
        mutate_after="create_project", mutate=lambda: _tamper_package(fixture.package)
    )
    result = _run(fixture, adapter=adapter, monkeypatch=monkeypatch)

    assert result["status"] == "mutation_failed"
    assert result["partialTargetRetained"] is True
    assert result["projectName"] == result["timelineName"]
    assert [name for name, _ in adapter.calls] == [
        "connected_facts",
        "probe",
        "check_project_name_available",
        "create_project",
    ]


def test_save_reopen_failure_preserves_package_and_partial_target(
    verified_fixture: VerifiedFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _snapshot(verified_fixture.package)
    adapter = RecordingAdapter(fail_on="save_close_reopen")
    result = _run(
        verified_fixture,
        adapter=adapter,
        monkeypatch=monkeypatch,
    )

    assert result["status"] == "mutation_failed"
    assert result["partialTargetRetained"] is True
    assert _snapshot(verified_fixture.package) == before


def test_discrepancies_are_retained_as_unverified_result(
    verified_fixture: VerifiedFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = RecordingAdapter(discrepancies=("unexpected marker",))
    result = _run(
        verified_fixture,
        adapter=adapter,
        monkeypatch=monkeypatch,
    )

    assert result["status"] == "verification_failed"
    assert result["verified"] is False
    assert result["partialTargetRetained"] is True
    assert result["discrepancies"] == ["unexpected marker"]


def test_workflow_delivery_imports_without_native_verifier_dependencies() -> None:
    code = (
        "import sys; "
        "import vera_timeline_agent.workflow_delivery; "
        "forbidden = ('opentimelineio', 'jsonschema', 'boto3'); "
        "assert not any(name == item or name.startswith(item + '.') "
        "for name in sys.modules for item in forbidden); "
        "assert 'vera_timeline_agent.resolve_import_package' not in sys.modules"
    )
    completed = subprocess.run(
        [sys.executable, "-S", "-c", code],
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT / "python")},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
