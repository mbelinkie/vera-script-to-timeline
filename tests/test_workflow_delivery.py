from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from vera_timeline_agent import workflow_delivery, workflow_launcher
from vera_timeline_agent.studio_assembly_acceptance import (
    build_studio_assembly_acceptance_package,
)
from vera_timeline_agent.studio_spike import ConnectedFacts
from vera_timeline_agent.studio_spike import (
    PublicResolveAdapter as AcceptedResolveAdapter,
)
from vera_timeline_agent.workflow_delivery_cli import attest_package
from vera_timeline_agent.workflow_package import (
    WorkflowPackageError,
    load_verified_package,
    sha256,
    write_immutable_json,
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

    def assert_current_target(self) -> None:
        if self.fail_on == "assert_current_target":
            raise RuntimeError("current project changed")

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
        ConnectedFacts("DaVinci Resolve Studio", "studio", "21.1.1", "9", True),
        ConnectedFacts("DaVinci Resolve Studio", "studio", "21.1.1", "11", True),
        ConnectedFacts("DaVinci Resolve Studio", "studio", "21.1.0", "15", True),
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


@pytest.mark.parametrize(
    ("stage", "next_stage"),
    [
        ("import_media", "create_timeline"),
        ("place_events", "add_marker"),
        ("add_marker", "save_close_reopen"),
    ],
)
def test_late_package_drift_stops_before_next_mutation(
    tmp_path: Path,
    verified_fixture: VerifiedFixture,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    next_stage: str,
) -> None:
    fixture = _copy_fixture(tmp_path, verified_fixture)
    adapter = RecordingAdapter(
        mutate_after=stage, mutate=lambda: _tamper_package(fixture.package)
    )
    result = _run(fixture, adapter=adapter, monkeypatch=monkeypatch)

    assert result["status"] == "mutation_failed"
    assert result["partialTargetRetained"] is True
    assert adapter.calls[-1][0] == stage
    assert next_stage not in [name for name, _ in adapter.calls]


def test_project_context_switch_stops_before_next_stage(
    verified_fixture: VerifiedFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = RecordingAdapter(mutate_after="import_media")
    adapter.mutate = lambda: setattr(adapter, "fail_on", "assert_current_target")
    result = _run(verified_fixture, adapter=adapter, monkeypatch=monkeypatch)

    assert result["status"] == "mutation_failed"
    assert result["partialTargetRetained"] is True
    assert adapter.calls[-1][0] == "import_media"
    assert "current project changed" in result["message"]


def test_attestation_parses_the_same_bytes_it_hashes(
    tmp_path: Path,
    verified_fixture: VerifiedFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "attestation.json"
    payload = verified_fixture.attestation.read_bytes()
    path.write_bytes(payload)
    original = json.loads(payload)
    altered = dict(original, projectName=original["projectName"][:-12] + "123456789abc")
    altered["timelineName"] = altered["projectName"]
    read_bytes = Path.read_bytes
    reads = 0

    def replacing_read(target: Path) -> bytes:
        nonlocal reads
        value = read_bytes(target)
        if target == path:
            reads += 1
            path.write_text(json.dumps(altered))
        return value

    monkeypatch.setattr(Path, "read_bytes", replacing_read)
    package = load_verified_package(path, verified_fixture.attestation_sha256)
    assert reads == 1
    assert package.attestation["projectName"] == original["projectName"]


def _native_adapter(
    *,
    current_id: str = "created-project",
    reopened_id: str = "created-project",
    timeline_count: int = 1,
    switch_after_save: bool = False,
) -> tuple[workflow_delivery.PublicResolveAdapter, list[str]]:
    calls: list[str] = []
    timeline = SimpleNamespace(GetUniqueId=lambda: "created-timeline")
    project = SimpleNamespace(
        GetUniqueId=lambda: "created-project",
        GetCurrentTimeline=lambda: timeline,
    )
    reopened = SimpleNamespace(
        GetUniqueId=lambda: reopened_id,
        GetCurrentTimeline=lambda: timeline,
        GetTimelineCount=lambda: timeline_count,
        GetMediaPool=lambda: object(),
    )
    current = SimpleNamespace(
        GetUniqueId=lambda: current_id, GetCurrentTimeline=lambda: timeline
    )

    def save() -> bool:
        nonlocal current
        calls.append("save")
        if switch_after_save:
            current = SimpleNamespace(GetUniqueId=lambda: "unrelated-project")
        return True

    def close(_project: Any) -> bool:
        calls.append("close")
        return True

    def load(_name: str) -> Any:
        nonlocal current
        calls.append("load")
        current = reopened
        return reopened

    adapter = workflow_delivery.PublicResolveAdapter(object())
    adapter.project = project
    adapter.timeline = timeline
    adapter.expected_project_id = "created-project"
    adapter.expected_timeline_id = "created-timeline"
    adapter.manager = SimpleNamespace(
        GetCurrentProject=lambda: current,
        SaveProject=save,
        CloseProject=close,
        LoadProject=load,
    )
    return adapter, calls


def test_native_save_refuses_to_save_an_unrelated_current_project() -> None:
    adapter, calls = _native_adapter(current_id="existing-project")
    with pytest.raises(ValueError, match="current project changed"):
        adapter.save_close_reopen("target")
    assert calls == []


def test_native_close_refuses_context_switch_after_save() -> None:
    adapter, calls = _native_adapter(switch_after_save=True)
    with pytest.raises(ValueError, match="current project changed"):
        adapter.save_close_reopen("target")
    assert calls == ["save"]


@pytest.mark.parametrize(
    ("reopened_id", "timeline_count", "message"),
    [
        ("wrong-project", 1, "unique identity differs"),
        ("created-project", 2, "exactly one timeline"),
    ],
)
def test_native_reopen_requires_created_identity_and_one_timeline(
    reopened_id: str,
    timeline_count: int,
    message: str,
) -> None:
    adapter, calls = _native_adapter(
        reopened_id=reopened_id, timeline_count=timeline_count
    )
    with pytest.raises(ValueError, match=message):
        adapter.save_close_reopen("target")
    assert calls == ["save", "close", "load"]


def test_native_save_reopen_retains_project_and_timeline_identity() -> None:
    adapter, calls = _native_adapter()
    adapter.save_close_reopen("target")
    assert calls == ["save", "close", "load"]
    adapter.assert_current_target()


@pytest.mark.parametrize("extra_outside", [False, True])
def test_media_readback_normalizes_paths_and_detects_unexpected_bins(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra_outside: bool,
) -> None:
    monkeypatch.setattr(AcceptedResolveAdapter, "verify", lambda *_: ())
    source = tmp_path / "clip.mov"
    media = SimpleNamespace(
        GetMediaId=lambda: "source-media",
        GetClipProperty=lambda _key: str(tmp_path / "unused" / ".." / "clip.mov"),
    )
    package_folder = SimpleNamespace(
        GetUniqueId=lambda: "package-folder",
        GetName=lambda: "Package Media",
        GetSubFolderList=lambda: [],
        GetClipList=lambda: [media],
    )
    assembly_folder = SimpleNamespace(
        GetUniqueId=lambda: "assembly-folder",
        GetName=lambda: "VERA Studio Assembly",
        GetSubFolderList=lambda: [package_folder],
        GetClipList=lambda: [],
    )
    root_folder = SimpleNamespace(
        GetUniqueId=lambda: "root-folder",
        GetSubFolderList=lambda: [assembly_folder],
        GetClipList=lambda: [media] if extra_outside else [],
    )
    adapter = workflow_delivery.PublicResolveAdapter(object())
    adapter.pool = SimpleNamespace(GetRootFolder=lambda: root_folder)
    adapter.timeline = SimpleNamespace(
        GetMediaPoolItem=lambda: None, GetMarkers=lambda: {}
    )
    adapter.created_bins = ["VERA Studio Assembly", "Package Media"]
    adapter.media_id_by_source = {"source": "source-media"}
    adapter.expected_paths = {"source": source.resolve()}
    discrepancies = adapter.verify(
        {"tracks": [], "events": [], "markers": [], "sources": [{"id": "source"}]}
    )

    assert discrepancies == (
        ("unexpected media outside the package media folder",) if extra_outside else ()
    )


def test_missing_track_retains_base_discrepancies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = ("video track count: expected 1, got 0", "video track 1 is missing")
    monkeypatch.setattr(AcceptedResolveAdapter, "verify", lambda *_: expected)
    folder = SimpleNamespace(
        GetUniqueId=lambda: "root", GetClipList=lambda: [], GetSubFolderList=lambda: []
    )
    adapter = workflow_delivery.PublicResolveAdapter(object())
    adapter.pool = SimpleNamespace(GetRootFolder=lambda: folder)
    adapter.timeline = SimpleNamespace(
        GetTrackCount=lambda _kind: 0,
        GetMarkers=lambda: {},
        GetMediaPoolItem=lambda: None,
        GetItemListInTrack=lambda *_: pytest.fail("missing track must not be read"),
    )
    discrepancies = adapter.verify(
        {
            "tracks": [{"id": "v1", "kind": "video", "index": 1}],
            "events": [],
            "markers": [],
            "sources": [],
        }
    )
    assert discrepancies == expected


def _operator_request(tmp_path: Path, fixture: VerifiedFixture) -> Path:
    attestation = _attestation_value(fixture.attestation)
    request = {
        "schemaVersion": "vera-injected-delivery-request/v1",
        "attestationPath": str(fixture.attestation),
        "attestationSha256": fixture.attestation_sha256,
        "packageDir": str(fixture.package),
        "evidenceDir": str(tmp_path / "evidence"),
        "releaseSha256": "0" * 64,
        "projectName": attestation["projectName"],
        "timelineName": attestation["timelineName"],
        "action": "build",
        "authorizeNewNonproduction": True,
        "externalScripting": "None",
    }
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request))
    return path


def test_result_remains_in_console_if_final_report_storage_fails(
    tmp_path: Path,
    verified_fixture: VerifiedFixture,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = _operator_request(tmp_path, verified_fixture)
    result = {
        "status": "mutation_failed",
        "partialTargetRetained": True,
        "projectName": _attestation_value(verified_fixture.attestation)["projectName"],
        "discrepancies": ["save failed"],
    }
    monkeypatch.setattr(
        workflow_launcher, "run_workflow_delivery", lambda *_a, **_k: dict(result)
    )
    write = write_immutable_json

    def fail_final(path: Path, value: object) -> Path:
        if path.name.startswith("result-"):
            raise OSError("storage failed")
        return write(path, value)

    monkeypatch.setattr(workflow_launcher, "write_immutable_json", fail_final)
    with pytest.raises(OSError, match="storage failed"):
        workflow_launcher.run_installed_request(
            object(), request, expected_request_sha256=sha256(request)
        )
    printed = json.loads(capsys.readouterr().out)
    assert printed["partialTargetRetained"] is True
    assert printed["projectName"] == result["projectName"]
    assert printed["discrepancies"] == ["save failed"]


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
