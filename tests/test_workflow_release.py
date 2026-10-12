from __future__ import annotations

import importlib.util
import json
import marshal
import os
import struct
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from vera_timeline_agent import workflow_delivery, workflow_launcher
from vera_timeline_agent.studio_assembly_acceptance import (
    build_studio_assembly_acceptance_package,
)
from vera_timeline_agent.studio_spike import ConnectedFacts, PublicResolveAdapter
from vera_timeline_agent.workflow_delivery_cli import (
    LAUNCHER_NAME,
    RELEASE_NAME,
    attest_package,
    build_release,
)
from vera_timeline_agent.workflow_launcher import run_installed_request
from vera_timeline_agent.workflow_package import (
    read_object,
    sha256,
    write_immutable_json,
)


@dataclass(frozen=True)
class ReadyPackage:
    package: Path
    attestation: Path
    attestation_sha256: str


def _request(release: Path, evidence: Path, package: Path) -> Path:
    return write_immutable_json(
        release / RELEASE_NAME / "request.json",
        {
            "schemaVersion": "vera-injected-delivery-request/v1",
            "releaseSha256": sha256(release / RELEASE_NAME / "release.json"),
            "attestationPath": str(package.parent / "missing-attestation.json"),
            "attestationSha256": "0" * 64,
            "packageDir": str(package),
            "projectName": "missing-target",
            "timelineName": "missing-target",
            "evidenceDir": str(evidence),
            "action": "preflight",
            "authorizeNewNonproduction": False,
            "externalScripting": "None",
        },
    )


def _ready_request_value(
    release: Path,
    evidence: Path,
    ready: ReadyPackage,
) -> dict[str, Any]:
    attestation = read_object(ready.attestation)
    return {
        "schemaVersion": "vera-injected-delivery-request/v1",
        "releaseSha256": sha256(release / RELEASE_NAME / "release.json"),
        "attestationPath": str(ready.attestation),
        "attestationSha256": ready.attestation_sha256,
        "packageDir": str(ready.package),
        "projectName": attestation["projectName"],
        "timelineName": attestation["timelineName"],
        "evidenceDir": str(evidence),
        "action": "preflight",
        "authorizeNewNonproduction": False,
        "externalScripting": None,
    }


def _ready_request(
    release: Path,
    evidence: Path,
    ready: ReadyPackage,
) -> Path:
    return write_immutable_json(
        release / RELEASE_NAME / "request.json",
        _ready_request_value(release, evidence, ready),
    )


def _launch(
    release: Path,
    *,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = None
    if environment is not None:
        env = os.environ.copy()
        env.update(environment)
    return subprocess.run(
        [sys.executable, "-S", str(release / LAUNCHER_NAME)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _run_twice(release: Path) -> subprocess.CompletedProcess[str]:
    code = (
        "import runpy, sys; "
        "runpy.run_path(sys.argv[1], run_name='__main__'); "
        "runpy.run_path(sys.argv[1], run_name='__main__')"
    )
    return subprocess.run(
        [sys.executable, "-S", "-c", code, str(release / LAUNCHER_NAME)],
        check=True,
        capture_output=True,
        text=True,
    )


def _write_cached_module(
    source: Path,
    cache_root: Path,
    source_text: str,
) -> Path:
    previous_prefix = sys.pycache_prefix
    sys.pycache_prefix = str(cache_root)
    try:
        cache_path = Path(importlib.util.cache_from_source(str(source)))
    finally:
        sys.pycache_prefix = previous_prefix
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    code = compile(source_text, str(source), "exec")
    stat = source.stat()
    header = b"".join(
        (
            importlib.util.MAGIC_NUMBER,
            struct.pack("<I", 0),
            struct.pack("<II", int(stat.st_mtime), stat.st_size),
        )
    )
    cache_path.write_bytes(header + marshal.dumps(code))
    return cache_path


@pytest.fixture(scope="module")
def ready_package(tmp_path_factory: pytest.TempPathFactory) -> ReadyPackage:
    root = tmp_path_factory.mktemp("workflow-release-ready")
    package = build_studio_assembly_acceptance_package(root / "package").project_root
    attestation = root / "attestation.json"
    attest_package(package, attestation)
    return ReadyPackage(package, attestation, sha256(attestation))


class PreflightAdapter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def connected_facts(self) -> ConnectedFacts:
        self.calls.append("connected_facts")
        return ConnectedFacts("DaVinci Resolve Studio", "studio", "21.1.0", "14", True)

    def probe(self, settings: Mapping[str, str]) -> tuple[str, ...]:
        self.calls.append("probe")
        return ()

    def check_project_name_available(self, name: str) -> None:
        self.calls.append("check_project_name_available")


def test_release_is_reproducible_and_refuses_replacement(tmp_path: Path) -> None:
    one = build_release(tmp_path / "one")
    two = build_release(tmp_path / "two")
    assert one.read_bytes() == two.read_bytes()
    with pytest.raises(FileExistsError):
        build_release(tmp_path / "one")
    assert one.read_bytes() == two.read_bytes()


def test_installed_launcher_retains_unique_missing_attestation_reports(
    tmp_path: Path,
) -> None:
    release = tmp_path / "release"
    build_release(release)
    evidence = tmp_path / "evidence"
    package = tmp_path / "package"
    package.mkdir()
    _request(release, evidence, package)
    first = _launch(release)
    second = _launch(release)
    assert first.stdout != second.stdout
    reports = list(evidence.glob("result-*.json"))
    assert len(reports) == 2
    for path in reports:
        result = read_object(path)
        assert result["status"] == "stopped_safely"
        assert result["verified"] is False
        assert result["partialTargetRetained"] is False
        assert result["injectedObjectAvailable"] is False
    hashes = [read_object(path) for path in evidence.glob("hashes-*.json")]
    assert {item["resultSha256"] for item in hashes} == {sha256(p) for p in reports}
    assert list(package.iterdir()) == []


def test_request_package_mismatch_cannot_write_evidence_into_ready_input(
    tmp_path: Path,
) -> None:
    release = tmp_path / "release"
    build_release(release)
    package = tmp_path / "ready-package"
    package.mkdir()
    declared = tmp_path / "wrong-package"
    request = _request(release, package, declared)
    value = read_object(request)
    write_immutable_json(Path(value["attestationPath"]), {"packageDir": str(package)})
    result = json.loads(_launch(release).stdout)
    assert result["status"] == "workflow_launcher_failed"
    assert result["reportRetention"].startswith("unavailable")
    assert list(package.iterdir()) == []


def test_finder_metadata_does_not_invalidate_installed_release(tmp_path: Path) -> None:
    release = tmp_path / "release"
    build_release(release)
    evidence = tmp_path / "evidence"
    package = tmp_path / "package"
    package.mkdir()
    _request(release, evidence, package)
    release_root = release / RELEASE_NAME
    for folder in (release_root, release_root / "python" / "vera_timeline_agent"):
        (folder / ".DS_Store").write_bytes(b"Finder metadata")

    _launch(release)
    assert not list(evidence.glob("bootstrap-refusal-*.json"))
    reports = list(evidence.glob("result-*.json"))
    assert len(reports) == 1
    assert read_object(reports[0])["status"] == "stopped_safely"
    assert list(package.iterdir()) == []


@pytest.mark.parametrize(
    "tamper",
    [
        "source",
        "release",
        "extra",
        "bytecode",
        "extension",
        "nonpython",
        "empty_cache",
    ],
)
def test_bootstrap_integrity_refuses_before_import(
    tmp_path: Path,
    tamper: str,
) -> None:
    release = tmp_path / "release"
    build_release(release)
    evidence = tmp_path / "evidence"
    package = tmp_path / "package"
    package.mkdir()
    _request(release, evidence, package)
    runtime = release / RELEASE_NAME / "python" / "vera_timeline_agent"
    if tamper == "source":
        with (runtime / "workflow_delivery.py").open("a") as stream:
            stream.write("\nraise AssertionError('unverified code executed')\n")
    elif tamper == "release":
        path = release / RELEASE_NAME / "release.json"
        path.chmod(0o600)
        path.write_text("{}")
    elif tamper == "extra":
        (runtime / "unexpected.py").write_text("raise AssertionError('extra source')")
    elif tamper == "bytecode":
        (runtime / "stale.pyc").write_bytes(b"stale")
    elif tamper == "extension":
        (runtime / "workflow_delivery.cpython-314-darwin.so").write_bytes(b"bad")
    elif tamper == "nonpython":
        (runtime / "unexpected.txt").write_text("unexpected")
    else:
        (runtime / "__pycache__").mkdir()
    result = json.loads(_launch(release).stdout)
    assert result["status"] == "workflow_launcher_failed"
    assert list(evidence.glob("bootstrap-refusal-*.json"))
    assert not list(evidence.glob("started-*.json"))
    assert list(package.iterdir()) == []


def test_bootstrap_resets_external_pycache_prefix_before_import(
    tmp_path: Path,
) -> None:
    release = tmp_path / "release"
    build_release(release)
    evidence = tmp_path / "evidence"
    package = tmp_path / "package"
    package.mkdir()
    _request(release, evidence, package)
    runtime_source = (
        release
        / RELEASE_NAME
        / "python"
        / "vera_timeline_agent"
        / "workflow_launcher.py"
    )
    cache_root = tmp_path / "external-pycache"
    _write_cached_module(
        runtime_source,
        cache_root,
        "raise AssertionError('cached workflow launcher executed')",
    )

    launched = _launch(
        release,
        environment={"PYTHONPYCACHEPREFIX": str(cache_root)},
    )

    assert "cached workflow launcher executed" not in launched.stdout
    assert len(list(evidence.glob("result-*.json"))) == 1
    assert not list(evidence.glob("bootstrap-refusal-*.json"))


def test_bootstrap_refuses_second_launch_with_same_runtime_loaded(
    tmp_path: Path,
) -> None:
    release = tmp_path / "release"
    build_release(release)
    evidence = tmp_path / "evidence"
    package = tmp_path / "package"
    package.mkdir()
    _request(release, evidence, package)

    launched = _run_twice(release)

    assert launched.returncode == 0
    assert len(list(evidence.glob("result-*.json"))) == 1
    assert len(list(evidence.glob("bootstrap-refusal-*.json"))) == 1


def test_shipped_six_file_runtime_imports_under_python_s(tmp_path: Path) -> None:
    release = tmp_path / "release"
    build_release(release)
    runtime = release / RELEASE_NAME / "python"
    code = (
        "import sys; "
        "import vera_timeline_agent.workflow_launcher; "
        "import vera_timeline_agent.workflow_delivery; "
        "forbidden = ('opentimelineio', 'jsonschema', 'boto3'); "
        "assert not any(name == item or name.startswith(item + '.') "
        "for name in sys.modules for item in forbidden); "
        "assert 'vera_timeline_agent.resolve_import_package' not in sys.modules"
    )
    completed = subprocess.run(
        [sys.executable, "-S", "-c", code],
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(runtime)},
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.slow
def test_installed_request_runs_verified_preflight_and_prints_full_result(
    tmp_path: Path,
    ready_package: ReadyPackage,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    release = tmp_path / "release"
    build_release(release)
    evidence = tmp_path / "evidence"
    request = _ready_request(release, evidence, ready_package)
    adapter = PreflightAdapter()
    monkeypatch.setattr(
        workflow_delivery, "PublicResolveAdapter", lambda _resolve: adapter
    )

    report = run_installed_request(
        object(), request, expected_request_sha256=sha256(request)
    )

    result = read_object(report)
    printed = capsys.readouterr().out
    assert result["status"] == "preflight_passed"
    assert result["verified"] is False
    assert "preflight_passed" in printed
    assert adapter.calls == [
        "connected_facts",
        "probe",
        "check_project_name_available",
    ]
    hashes = list(evidence.glob("hashes-*.json"))
    assert len(hashes) == 1
    assert read_object(hashes[0])["resultSha256"] == sha256(report)


@pytest.mark.slow
def test_shipped_launcher_runs_read_only_preflight_with_injected_resolve(
    tmp_path: Path,
    ready_package: ReadyPackage,
) -> None:
    release = tmp_path / "release"
    build_release(release)
    evidence = tmp_path / "evidence"
    _ready_request(release, evidence, ready_package)
    before = {
        path.relative_to(ready_package.package).as_posix(): path.read_bytes()
        for path in ready_package.package.rglob("*")
        if path.is_file()
    }
    code = """
import runpy
import sys
from types import SimpleNamespace


def forbidden(*args, **kwargs):
    raise AssertionError("preflight invoked a Resolve mutator")


root = SimpleNamespace(
    GetSubFolderList=lambda: [],
    GetClipList=lambda: [],
)
timeline = SimpleNamespace(
    GetTrackCount=lambda kind: 0,
    GetItemListInTrack=lambda kind, index: [],
)
pool = SimpleNamespace(
    GetRootFolder=lambda: root,
    GetCurrentFolder=forbidden,
    SetCurrentFolder=forbidden,
    AddSubFolder=forbidden,
    ImportMedia=forbidden,
    CreateEmptyTimeline=forbidden,
    ImportFolderFromFile=forbidden,
    AppendToTimeline=forbidden,
)
project = SimpleNamespace(
    GetSetting=lambda key: "valid value",
    GetMediaPool=lambda: pool,
    GetCurrentTimeline=lambda: timeline,
    SetSetting=forbidden,
)
manager = SimpleNamespace(
    GetProjectListInCurrentFolder=lambda: [],
    GetCurrentProject=lambda: project,
    CreateProject=forbidden,
    SaveProject=forbidden,
    CloseProject=forbidden,
    LoadProject=forbidden,
)
resolve = SimpleNamespace(
    GetProductName=lambda: "DaVinci Resolve Studio",
    GetVersion=lambda: [21, 1, 0, 14, ""],
    GetCurrentPage=lambda: "edit",
    GetProjectManager=lambda: manager,
)


runpy.run_path(
    sys.argv[1],
    run_name="__main__",
    init_globals={"resolve": resolve},
)
"""
    completed = subprocess.run(
        [sys.executable, "-S", "-c", code, str(release / LAUNCHER_NAME)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert len(list(evidence.glob("started-*.json"))) == 1
    reports = list(evidence.glob("result-*.json"))
    assert len(reports) == 1
    assert read_object(reports[0])["status"] == "preflight_passed"
    assert len(list(evidence.glob("hashes-*.json"))) == 1
    assert not list(evidence.glob("bootstrap-refusal-*.json"))
    after = {
        path.relative_to(ready_package.package).as_posix(): path.read_bytes()
        for path in ready_package.package.rglob("*")
        if path.is_file()
    }
    assert after == before


@pytest.mark.slow
def test_installed_request_prints_result_before_report_write_failure(
    tmp_path: Path,
    ready_package: ReadyPackage,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    release = tmp_path / "release"
    build_release(release)
    evidence = tmp_path / "evidence"
    request = _ready_request(release, evidence, ready_package)
    adapter = PreflightAdapter()
    monkeypatch.setattr(
        workflow_delivery, "PublicResolveAdapter", lambda _resolve: adapter
    )
    original_writer = cast(
        Callable[[Path, object], Path],
        workflow_launcher.__dict__["write_immutable_json"],
    )

    def fail_result_write(path: Path, value: object) -> Path:
        if path.name.startswith("result-"):
            raise OSError("simulated result storage failure")
        return original_writer(path, value)

    monkeypatch.setattr(workflow_launcher, "write_immutable_json", fail_result_write)
    with pytest.raises(OSError, match="simulated result storage failure"):
        run_installed_request(
            object(), request, expected_request_sha256=sha256(request)
        )

    assert "preflight_passed" in capsys.readouterr().out
    assert len(list(evidence.glob("started-*.json"))) == 1
    assert not list(evidence.glob("result-*.json"))


@pytest.mark.slow
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("projectName", "VERA Delivery wrong target"),
        ("timelineName", "VERA Delivery wrong timeline"),
        ("action", "unsupported"),
        ("action", True),
        ("authorizeNewNonproduction", 0),
    ],
)
def test_installed_request_rejects_unbound_target_and_request_types(
    tmp_path: Path,
    ready_package: ReadyPackage,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    release = tmp_path / "release"
    build_release(release)
    evidence = tmp_path / "evidence"
    request_value = _ready_request_value(release, evidence, ready_package)
    request_value[field] = value
    request = write_immutable_json(
        release / RELEASE_NAME / "request.json", request_value
    )

    def forbidden(*_: object, **__: object) -> dict[str, Any]:
        raise AssertionError("invalid request reached native delivery")

    monkeypatch.setattr(
        "vera_timeline_agent.workflow_launcher.run_workflow_delivery", forbidden
    )
    with pytest.raises(ValueError):
        run_installed_request(
            object(), request, expected_request_sha256=sha256(request)
        )
    assert not list(evidence.glob("result-*.json"))


@pytest.mark.slow
def test_installed_request_refuses_request_hash_mismatch(
    tmp_path: Path,
    ready_package: ReadyPackage,
) -> None:
    release = tmp_path / "release"
    build_release(release)
    evidence = tmp_path / "evidence"
    request = _ready_request(release, evidence, ready_package)

    with pytest.raises(ValueError):
        run_installed_request(object(), request, expected_request_sha256="0" * 64)

    assert not list(evidence.glob("started-*.json"))


def test_readback_checks_unused_media_paths_and_extra_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(PublicResolveAdapter, "verify", lambda *_: ())

    class Media:
        def __init__(self, identity: str, path: str) -> None:
            self.identity, self.path = identity, path

        def GetMediaId(self) -> str:
            return self.identity

        def GetClipProperty(self, key: str) -> str:
            assert key == "File Path"
            return self.path

    media = [Media("used", "/package/used.mov"), Media("unused", "/wrong/path.mov")]

    class Folder:
        def GetUniqueId(self) -> str:
            return "package-media"

        def GetClipList(self) -> list[Media]:
            return media

        def GetSubFolderList(self) -> list[object]:
            return []

    class Pool:
        def GetRootFolder(self) -> Folder:
            return Folder()

    class Timeline:
        def GetMediaPoolItem(self) -> Media:
            return Media("timeline", "")

        def GetMarkers(self) -> dict[int, dict[str, Any]]:
            return {3: {}, 4: {}}

    adapter = workflow_delivery.PublicResolveAdapter(object())
    adapter.pool, adapter.timeline = Pool(), Timeline()
    adapter.media_id_by_source = {"used-source": "used", "unused-source": "unused"}
    adapter.expected_paths = {
        "used-source": Path("/package/used.mov"),
        "unused-source": Path("/package/unused.mov"),
    }
    manifest = {
        "sources": [{"id": "used-source"}, {"id": "unused-source"}],
        "markers": [{"frame": 3}],
    }
    assert adapter.verify(manifest) == (
        "marker inventory differs from manifest",
        "source unused-source: reopened media identity differs",
    )
    media[1].path = "/package/unused.mov"
    media.append(Media("timeline", ""))
    assert adapter.verify(manifest) == ("marker inventory differs from manifest",)
    media.append(Media("extra", "/package/extra.mov"))
    assert "package media count differs from manifest" in adapter.verify(manifest)


def test_readback_verifies_source_endpoint_in_source_rate_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(PublicResolveAdapter, "verify", lambda *_: ())

    class Item:
        source_end = 30

        def GetStart(self, _: bool) -> int:
            return 0

        def GetSourceEndFrame(self) -> int:
            return self.source_end

    item = Item()

    class Timeline:
        def GetItemListInTrack(self, *_: object) -> list[Item]:
            return [item]

        def GetTrackCount(self, *_: object) -> int:
            return 1

        def GetMarkers(self) -> dict[int, object]:
            return {}

        def GetMediaPoolItem(self) -> None:
            return None

    class Folder:
        def GetUniqueId(self) -> str:
            return "package-media"

        def GetClipList(self) -> list[object]:
            return []

        def GetSubFolderList(self) -> list[object]:
            return []

    class Pool:
        def GetRootFolder(self) -> Folder:
            return Folder()

    adapter = workflow_delivery.PublicResolveAdapter(object())
    adapter.timeline, adapter.pool = Timeline(), Pool()
    manifest = {
        "sources": [],
        "markers": [],
        "tracks": [{"id": "v1", "kind": "video", "index": 1}],
        "events": [
            {
                "id": "event-1",
                "trackId": "v1",
                "recordRange": {"startFrame": 0, "durationFrames": 24},
                "sourceRange": {"startFrame": 2, "durationFrames": 30},
            }
        ],
    }
    assert adapter.verify(manifest) == ("event event-1: source end mismatch",)
    item.source_end = 31
    assert adapter.verify(manifest) == ()
