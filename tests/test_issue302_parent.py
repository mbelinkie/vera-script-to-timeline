"""Synthetic coverage for the durable v2 parent dispatcher."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import (
    workflow_v2,
    workflow_v2_cli,
    workflow_v2_launcher,
    workflow_v2_parent,
)
from vera_timeline_agent.studio_spike import (
    PublicResolveAdapter as BasePublicResolveAdapter,
)
from vera_timeline_agent.studio_spike import (
    StudioSpikeError,
)


@pytest.fixture(autouse=True)
def _isolate_parent_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        workflow_v2_parent, "PARENT_STATE_ROOT", tmp_path / "parent-state"
    )


def _case(tmp_path: Path) -> tuple[Path, str, Path, Path, dict[str, Any]]:
    release = tmp_path / "release"
    installed = release / "vera-delivery-v2"
    installed.mkdir(parents=True)
    manifest = installed / "release.json"
    manifest.write_bytes(b"synthetic release manifest")
    package = tmp_path / "package"
    package.mkdir()
    attestation = tmp_path / "attestation.json"
    attestation.write_text(json.dumps({"packageDir": str(package)}))
    evidence = tmp_path / "evidence"
    request = {
        "schemaVersion": "vera-injected-delivery-request/v2",
        "releaseSha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "attestationPath": str(attestation),
        "attestationSha256": "a" * 64,
        "packageDir": str(package),
        "projectName": "Synthetic Project",
        "timelineName": "Synthetic Timeline",
        "action": "preflight",
        "authorizeNewNonproduction": False,
        "externalScripting": "Local",
        "evidenceDir": str(evidence),
    }
    request_path = installed / "request.json"
    request_path.write_text(json.dumps(request, sort_keys=True))
    expected = hashlib.sha256(request_path.read_bytes()).hexdigest()
    return request_path, expected, manifest, evidence, request


def _patch_release_checks(monkeypatch: pytest.MonkeyPatch, manifest: Path) -> None:
    monkeypatch.setattr(workflow_v2_cli, "_no_symlinks", lambda _path: None)
    monkeypatch.setattr(workflow_v2_cli, "_verify_release", lambda _release: manifest)


def _patch_release_checks_for(
    monkeypatch: pytest.MonkeyPatch, *manifests: Path
) -> None:
    manifest_by_release = {path.parent.parent.absolute(): path for path in manifests}
    monkeypatch.setattr(workflow_v2_cli, "_no_symlinks", lambda _path: None)
    monkeypatch.setattr(
        workflow_v2_cli,
        "_verify_release",
        lambda release: manifest_by_release[Path(release).absolute()],
    )


def _patch_popen(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[list[str]], list[int]]:
    commands: list[list[str]] = []
    held_fds: list[int] = []

    def fake_popen(command: list[str], **kwargs: Any) -> object:
        commands.append(command)
        held_fds.append(os.dup(kwargs["pass_fds"][0]))
        return object()

    monkeypatch.setattr(workflow_v2_parent.subprocess, "Popen", fake_popen)
    return commands, held_fds


def _close_fds(fds: list[int]) -> None:
    for fd in fds:
        os.close(fd)


def _two_cases(
    tmp_path: Path,
) -> tuple[
    tuple[Path, str, Path, Path, dict[str, Any]],
    tuple[Path, str, Path, Path, dict[str, Any]],
]:
    first_root = tmp_path / "first-request"
    second_root = tmp_path / "second-request"
    first_root.mkdir()
    second_root.mkdir()
    return _case(first_root), _case(second_root)


_PARENT_INVOCATION_ID = "1" * 32


def _context(expected: str, request: dict[str, Any]) -> dict[str, str]:
    return {
        "requestSha256": expected,
        "releaseSha256": request["releaseSha256"],
        "attestationSha256": request["attestationSha256"],
        "requestedProjectName": request["projectName"],
        "requestedTimelineName": request["timelineName"],
        "parentInvocationId": _PARENT_INVOCATION_ID,
    }


def _session(evidence: Path, request_path: Path, expected: str) -> None:
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "parent.lock").touch()
    workflow_v2_parent._write(
        evidence / "parent.json",
        {
            "schemaVersion": "vera-delivery-parent/v1",
            "requestPath": str(request_path.absolute()),
            "requestSha256": expected,
            "startedAt": "2026-10-25T00:00:00+00:00",
            "monotonicStarted": 10.0,
            "invocationId": _PARENT_INVOCATION_ID,
        },
    )


def _completed_operation(
    evidence: Path,
    expected: str,
    request: dict[str, Any],
    *,
    status: str = "verified",
    returncode: int = 0,
    bad_hash: bool = False,
    corrupt_result: bool = False,
    missing_result: bool = False,
    mismatch_context: bool = False,
    parent_invocation_id: str | None = None,
) -> None:
    context = _context(expected, request)
    session = workflow_v2_parent._read(evidence / "parent.json")
    if parent_invocation_id is not None:
        context["parentInvocationId"] = parent_invocation_id
    workflow_v2_parent._write(evidence / f"started-{expected}.json", context)
    report_path = evidence / f"result-{expected}.json"
    report = {
        "schemaVersion": "vera-injected-delivery-result/v2",
        "status": status,
        "verified": status == "verified",
        "discrepancies": [] if status == "verified" else ["synthetic-failure"],
        **context,
    }
    if mismatch_context:
        report["requestedTimelineName"] = "Different Timeline"
    if corrupt_result:
        report_path.write_bytes(b"{not-json")
        report_path.chmod(0o400)
    elif not missing_result:
        workflow_v2_parent._write(report_path, report)
    workflow_v2_parent._write(
        evidence / f"hashes-{expected}.json",
        {
            "resultPath": str(report_path),
            "resultSha256": (
                "0" * 64
                if bad_hash or missing_result
                else workflow_v2_parent._digest(report_path)
            ),
            **context,
        },
    )
    workflow_v2_parent._write(
        evidence / "parent-exit.json",
        {
            "returncode": returncode,
            "monotonicFinished": session["monotonicStarted"] + 1.0,
            "requestSha256": expected,
        },
    )


def test_launcher_names_attempt_evidence_with_request_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_path, expected, _manifest, evidence, request = _case(tmp_path)
    package = Path(request["packageDir"])
    monkeypatch.setattr(
        workflow_v2_launcher,
        "load_verified_package_v2",
        lambda *_args: SimpleNamespace(
            root=package,
            attestation={
                "projectName": request["projectName"],
                "timelineName": request["timelineName"],
            },
        ),
    )

    delivery_calls: list[None] = []

    def run_delivery(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        delivery_calls.append(None)
        return {
            "schemaVersion": "vera-injected-delivery-result/v2",
            "status": "preflight_passed",
            "verified": False,
            "discrepancies": [],
        }

    monkeypatch.setattr(workflow_v2_launcher, "run_workflow_delivery_v2", run_delivery)

    report_path = workflow_v2_launcher.run_installed_request_v2(
        object(), request_path, expected_request_sha256=expected
    )
    with pytest.raises(FileExistsError):
        workflow_v2_launcher.run_installed_request_v2(
            object(), request_path, expected_request_sha256=expected
        )

    assert report_path == evidence / f"result-{expected}.json"
    assert (evidence / f"started-{expected}.json").exists()
    assert (evidence / f"hashes-{expected}.json").exists()
    assert len(delivery_calls) == 1


def test_start_is_idempotent_and_unknown_after_worker_lock_releases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_path, expected, manifest, evidence, _request_value = _case(tmp_path)
    _patch_release_checks(monkeypatch, manifest)
    commands, held_fds = _patch_popen(monkeypatch)
    try:
        first = workflow_v2_parent.start(request_path, expected, Path("ResolvePython"))
        second = workflow_v2_parent.start(request_path, expected, Path("ResolvePython"))

        assert first["state"] == second["state"] == "live"
        assert len(commands) == 1
        assert commands[0][1].endswith("workflow_v2_parent.py")

        _close_fds(held_fds)
        held_fds.clear()
        after_exit_without_receipt = workflow_v2_parent.start(
            request_path, expected, Path("ResolvePython")
        )
        assert after_exit_without_receipt["state"] == "unknown"
        assert len(commands) == 1
        assert (evidence / "parent.json").exists()
    finally:
        _close_fds(held_fds)


def test_start_requires_local_scripting_authority_before_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_path, _expected, _manifest, evidence, request = _case(tmp_path)
    request["externalScripting"] = "None"
    request_path.write_text(json.dumps(request, sort_keys=True))
    expected = hashlib.sha256(request_path.read_bytes()).hexdigest()
    commands, held_fds = _patch_popen(monkeypatch)
    try:
        with pytest.raises(ValueError, match="Local"):
            workflow_v2_parent.start(request_path, expected, Path("ResolvePython"))

        assert commands == []
        assert not (evidence / "parent.json").exists()
    finally:
        _close_fds(held_fds)


def test_v2_probe_allows_missing_timeline_but_checks_present_timeline_surface() -> None:
    def resolve_with_timeline(timeline: object | None) -> SimpleNamespace:
        root = SimpleNamespace(
            GetSubFolderList=lambda: [],
            GetClipList=lambda: [],
        )
        pool = SimpleNamespace(
            ImportMedia=lambda *_args: [],
            CreateEmptyTimeline=lambda *_args: None,
            AddSubFolder=lambda *_args: None,
            GetRootFolder=lambda: root,
            GetCurrentFolder=lambda: None,
            SetCurrentFolder=lambda *_args: True,
            ImportFolderFromFile=lambda *_args: True,
            AppendToTimeline=lambda *_args: [],
        )
        project = SimpleNamespace(
            GetSetting=lambda _key: "24",
            GetMediaPool=lambda: pool,
            GetCurrentTimeline=lambda: timeline,
        )
        manager = SimpleNamespace(
            GetProjectListInCurrentFolder=lambda: [],
            GetCurrentProject=lambda: project,
            CreateProject=lambda *_args: project,
            SaveProject=lambda *_args: True,
            CloseProject=lambda *_args: True,
            LoadProject=lambda *_args: project,
        )
        return SimpleNamespace(
            GetCurrentPage=lambda: "edit",
            GetProjectManager=lambda: manager,
        )

    settings = {"timelineFrameRate": "24"}
    empty_resolve = resolve_with_timeline(None)
    limitations = workflow_v2.PublicResolveAdapter(empty_resolve).probe(settings)
    assert "Timeline APIs will be checked on the new target." in limitations[-1]
    with pytest.raises(StudioSpikeError, match="no timeline"):
        BasePublicResolveAdapter(empty_resolve).probe(settings)

    for adapter_type in (BasePublicResolveAdapter, workflow_v2.PublicResolveAdapter):
        with pytest.raises(StudioSpikeError, match="GetTrackCount"):
            adapter_type(resolve_with_timeline(SimpleNamespace())).probe(settings)


def test_wait_timeout_after_sixty_seconds_stays_live_without_redispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request_path, expected, manifest, evidence, _request_value = _case(tmp_path)
    _patch_release_checks(monkeypatch, manifest)
    commands, held_fds = _patch_popen(monkeypatch)
    try:
        workflow_v2_parent.start(request_path, expected, Path("ResolvePython"))
        started = workflow_v2_parent._read(evidence / "parent.json")["monotonicStarted"]
        clock = {"now": started + 61.0}
        monkeypatch.setattr(workflow_v2_parent.time, "monotonic", lambda: clock["now"])
        monkeypatch.setattr(
            workflow_v2_parent.time,
            "sleep",
            lambda seconds: clock.__setitem__("now", clock["now"] + seconds),
        )

        report = workflow_v2_parent.wait(request_path, expected, 1.0)

        assert report["state"] == "live"
        assert clock["now"] >= started + 62.0

        monkeypatch.setattr(
            workflow_v2_parent.sys,
            "argv",
            [
                "workflow_v2_parent.py",
                "resume",
                "--request",
                str(request_path),
                "--request-sha256",
                expected,
                "--wait-seconds",
                "0",
            ],
        )
        assert workflow_v2_parent.main() == 0
        assert json.loads(capsys.readouterr().out)["state"] == "live"
        assert len(commands) == 1
    finally:
        _close_fds(held_fds)


def test_only_one_concurrent_start_reserves_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_path, expected, manifest, _evidence, _request_value = _case(tmp_path)
    _patch_release_checks(monkeypatch, manifest)
    commands, held_fds = _patch_popen(monkeypatch)
    barrier = threading.Barrier(2)

    def start_together() -> dict[str, Any]:
        barrier.wait()
        return workflow_v2_parent.start(request_path, expected, Path("ResolvePython"))

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            reports = list(pool.map(lambda _index: start_together(), range(2)))
        assert all(report["state"] in {"live", "unknown"} for report in reports)
        assert len(commands) == 1
    finally:
        _close_fds(held_fds)


@pytest.mark.parametrize(
    ("prior_state", "expected_state"),
    [("live", "live"), ("unknown", "unknown"), ("failed", "failed")],
)
def test_new_request_waits_for_prior_host_operation_to_be_resolved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prior_state: str,
    expected_state: str,
) -> None:
    first, second = _two_cases(tmp_path)
    first_path, first_hash, first_manifest, first_evidence, first_request = first
    second_path, second_hash, second_manifest, _second_evidence, _second_request = (
        second
    )
    _patch_release_checks_for(monkeypatch, first_manifest, second_manifest)
    commands, held_fds = _patch_popen(monkeypatch)
    try:
        workflow_v2_parent.start(first_path, first_hash, Path("ResolvePython"))
        if prior_state in {"unknown", "failed"}:
            _close_fds(held_fds)
            held_fds.clear()
        if prior_state == "failed":
            invocation_id = workflow_v2_parent._read(first_evidence / "parent.json")[
                "invocationId"
            ]
            _completed_operation(
                first_evidence,
                first_hash,
                first_request,
                bad_hash=True,
                parent_invocation_id=invocation_id,
            )

        assert workflow_v2_parent.status(first_path, first_hash)["state"] == (
            expected_state
        )
        with pytest.raises(ValueError, match="live or unresolved"):
            workflow_v2_parent.start(second_path, second_hash, Path("ResolvePython"))
        assert len(commands) == 1
    finally:
        _close_fds(held_fds)


def test_new_request_is_allowed_after_prior_valid_terminal_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = _two_cases(tmp_path)
    first_path, first_hash, first_manifest, first_evidence, first_request = first
    second_path, second_hash, second_manifest, _second_evidence, _second_request = (
        second
    )
    _patch_release_checks_for(monkeypatch, first_manifest, second_manifest)
    commands, held_fds = _patch_popen(monkeypatch)
    try:
        workflow_v2_parent.start(first_path, first_hash, Path("ResolvePython"))
        _close_fds(held_fds)
        held_fds.clear()
        invocation_id = workflow_v2_parent._read(first_evidence / "parent.json")[
            "invocationId"
        ]
        _completed_operation(
            first_evidence,
            first_hash,
            first_request,
            parent_invocation_id=invocation_id,
        )
        assert workflow_v2_parent.status(first_path, first_hash)["state"] == "terminal"

        result = workflow_v2_parent.start(
            second_path, second_hash, Path("ResolvePython")
        )

        assert result["state"] == "live"
        assert len(commands) == 2
    finally:
        _close_fds(held_fds)


def test_corrupt_active_host_pointer_fails_closed_before_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_path, expected, _manifest, _evidence, _request_value = _case(tmp_path)
    state_root = workflow_v2_parent.PARENT_STATE_ROOT
    state_root.mkdir(parents=True)
    (state_root / "active.json").write_text("{not-json")
    commands, held_fds = _patch_popen(monkeypatch)
    try:
        with pytest.raises(ValueError):
            workflow_v2_parent.start(request_path, expected, Path("ResolvePython"))
        assert commands == []
    finally:
        _close_fds(held_fds)


def test_status_distinguishes_live_unknown_and_terminal_results(
    tmp_path: Path,
) -> None:
    request_path, expected, _manifest, evidence, request = _case(tmp_path)
    _session(evidence, request_path, expected)

    with (evidence / "parent.lock").open("r") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert workflow_v2_parent.status(request_path, expected)["state"] == "live"
    assert workflow_v2_parent.status(request_path, expected)["state"] == "unknown"

    _completed_operation(evidence, expected, request, status="verified")
    success = workflow_v2_parent.status(request_path, expected)
    assert success["state"] == "terminal"
    assert success["verified"] is True


@pytest.mark.parametrize("status", ["mutation_failed", "verification_failed"])
def test_workflow_failure_is_still_a_terminal_result(
    tmp_path: Path,
    status: str,
) -> None:
    request_path, expected, _manifest, evidence, request = _case(tmp_path)
    _session(evidence, request_path, expected)
    _completed_operation(evidence, expected, request, status=status)

    report = workflow_v2_parent.status(request_path, expected)

    assert report["state"] == "terminal"
    assert report["verified"] is False
    assert report["result"]["status"] == status


@pytest.mark.parametrize(
    "damage",
    [
        "missing-final",
        "missing-result-json",
        "corrupt-hash",
        "corrupt-result-json",
        "context-mismatch",
        "foreign-parent-invocation",
    ],
)
def test_worker_exit_with_missing_or_bad_final_is_failed_and_never_replayed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
) -> None:
    request_path, expected, manifest, evidence, request = _case(tmp_path)
    _session(evidence, request_path, expected)
    if damage == "missing-final":
        workflow_v2_parent._write(
            evidence / f"started-{expected}.json", _context(expected, request)
        )
        workflow_v2_parent._write(
            evidence / "parent-exit.json",
            {"returncode": 0, "monotonicFinished": 11.0, "requestSha256": expected},
        )
    elif damage == "corrupt-hash":
        _completed_operation(evidence, expected, request, bad_hash=True)
    elif damage == "missing-result-json":
        _completed_operation(evidence, expected, request, missing_result=True)
    elif damage == "corrupt-result-json":
        _completed_operation(evidence, expected, request, corrupt_result=True)
    elif damage == "foreign-parent-invocation":
        _completed_operation(
            evidence,
            expected,
            request,
            parent_invocation_id="2" * 32,
        )
    else:
        _completed_operation(evidence, expected, request, mismatch_context=True)

    report = workflow_v2_parent.status(request_path, expected)
    _patch_release_checks(monkeypatch, manifest)
    commands, held_fds = _patch_popen(monkeypatch)
    try:
        repeated_start = workflow_v2_parent.start(
            request_path, expected, Path("ResolvePython")
        )
        assert report["state"] == repeated_start["state"] == "failed"
        assert len(commands) == 0
    finally:
        _close_fds(held_fds)


def test_nonzero_worker_exit_is_failed_even_with_a_valid_workflow_report(
    tmp_path: Path,
) -> None:
    request_path, expected, _manifest, evidence, request = _case(tmp_path)
    _session(evidence, request_path, expected)
    _completed_operation(evidence, expected, request, returncode=1)

    report = workflow_v2_parent.status(request_path, expected)

    assert report["state"] == "failed"
    assert report["verified"] is False
