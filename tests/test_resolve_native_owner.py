from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_controller_v2 as controller
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent import resolve_native_owner as owner
from vera_timeline_agent import workflow_v2_parent
from vera_timeline_agent.qualification_output_records_v2 import _canonical


def _result(
    directory: Path,
    sequence: int,
    action: str,
    status: str = "complete",
    job_status: str | None = None,
) -> Path:
    operation = directory / f"{sequence:08d}"
    operation.mkdir(parents=True)
    (operation / "request.json").write_text("{}", encoding="utf-8")
    (operation / "native-start.json").write_text("{}", encoding="utf-8")
    value: dict[str, Any] = {"action": action, "status": status}
    if job_status is not None:
        value["renderStatus"] = {"JobStatus": job_status}
    result_path = operation / "result.json"
    result_path.write_text(json.dumps(value), encoding="utf-8")
    return result_path


def _verified_json(path: Path, _sha256: str) -> dict[str, Any]:
    result = json.loads(path.read_bytes())
    if not isinstance(result, dict):
        raise ValueError("verified result is not an object")
    return result


def test_close_only_release_keeps_an_inherited_flock_owned() -> None:
    descriptor = owner.acquire_native_owner()
    inherited = os.dup(descriptor)
    owner.release_native_owner(descriptor)

    with pytest.raises(owner.NativeOwnerError) as error:
        owner.acquire_native_owner()
    assert error.value.reason == "owner_busy"

    owner.release_native_owner(inherited)
    replacement = owner.acquire_native_owner()
    owner.release_native_owner(replacement)


def test_prepared_empty_host_journal_vaults_do_not_claim_native_ownership() -> None:
    chain = {
        "projectUid": "project",
        "timelineUid": "timeline",
        "caseId": "case",
        "phase": "pristine",
    }
    directory = owner.OUTPUT_ATTEMPTS_ROOT / controller._json_hash(chain)
    directory.mkdir(parents=True)
    (directory / "chain.json").write_bytes(_canonical(chain))
    (directory / "lock").touch()
    (directory / "artifacts").mkdir()
    (directory / "receipts").mkdir()
    owner.preflight_native_owner()
    (directory / "pending-0000.json").write_text("{}")
    with pytest.raises(owner.NativeOwnerError):
        owner.preflight_native_owner()


def test_inherited_owner_is_reentrant_and_is_not_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor = owner.acquire_native_owner()
    monkeypatch.setenv(owner.OWNER_FD_ENV, str(descriptor))
    monkeypatch.setattr(
        owner,
        "_check_parent_operation",
        lambda *_args: pytest.fail("inherited owner must reuse the parent preflight"),
    )
    monkeypatch.setattr(
        owner,
        "_check_issue328_marker",
        lambda *_args: pytest.fail("inherited owner must reuse the parent preflight"),
    )

    with owner.native_owner() as first, owner.native_owner() as nested:
        assert first == nested == descriptor

    with pytest.raises(owner.NativeOwnerError):
        owner.acquire_native_owner()
    owner.release_native_owner(descriptor)


def test_inherited_owner_must_match_the_shared_lock_inode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    descriptor = owner.acquire_native_owner()
    monkeypatch.setenv(owner.OWNER_FD_ENV, str(descriptor))
    monkeypatch.setattr(owner, "OWNER_LOCK_PATH", tmp_path / "other.lock")

    with pytest.raises(owner.NativeOwnerError) as error, owner.native_owner():
        pytest.fail("wrong lock inode was accepted")
    assert error.value.reason == "invalid_inherited_owner"
    owner.release_native_owner(descriptor)


def test_preflight_blocks_an_unknown_retained_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner.PARENT_ACTIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    owner.PARENT_ACTIVE_PATH.write_text(
        json.dumps({"requestPath": "/private/request.json", "requestSha256": "a" * 64}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        workflow_v2_parent, "status", lambda *_args, **_kwargs: {"state": "unknown"}
    )

    with pytest.raises(owner.NativeOwnerError) as error:
        owner.preflight_native_owner()
    assert error.value.reason == "parent_unresolved"
    assert str(owner.PARENT_ACTIVE_PATH) in error.value.private_detail
    assert str(owner.PARENT_ACTIVE_PATH) not in str(error.value)


def test_preflight_allows_a_verified_terminal_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner.PARENT_ACTIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    owner.PARENT_ACTIVE_PATH.write_text(
        json.dumps({"requestPath": "/private/request.json", "requestSha256": "b" * 64}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        workflow_v2_parent,
        "status",
        lambda *_args, **_kwargs: {"state": "terminal", "verified": True},
    )

    owner.preflight_native_owner()


def test_preflight_blocks_queued_render_until_terminal_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = "a" * 64
    operations = owner.OUTPUT_TARGETS_ROOT / key / "operations"
    _result(operations, 0, "queue_render")
    monkeypatch.setattr(native, "verify_native_result", _verified_json)

    with pytest.raises(owner.NativeOwnerError) as error:
        owner.preflight_native_owner()
    assert error.value.reason == "output_render_unresolved"
    assert key[:12] in error.value.private_detail


def test_preflight_allows_terminal_render_after_host_finalization_uncertainty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = "b" * 64
    operations = owner.OUTPUT_TARGETS_ROOT / key / "operations"
    _result(operations, 0, "queue_render")
    _result(operations, 1, "start_render")
    _result(operations, 2, "poll_render", job_status="Complete")
    _result(operations, 3, "capture_post")
    monkeypatch.setattr(native, "verify_native_result", _verified_json)
    monkeypatch.setattr(
        owner, "_active_output_host_chains", lambda _native: {key: "uncertain"}
    )

    owner.preflight_native_owner()


def test_returned_synchronous_failure_retains_target_uncertainty_without_live_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = owner.OUTPUT_TARGETS_ROOT / ("e" * 64) / "operations"
    result = _result(operations, 0, "construct", status="uncertain")
    original = result.read_bytes()
    monkeypatch.setattr(native, "verify_native_result", _verified_json)
    owner.preflight_native_owner()
    assert result.read_bytes() == original
    assert json.loads(original)["status"] == "uncertain"


def test_uncertain_render_start_remains_an_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = owner.OUTPUT_TARGETS_ROOT / ("d" * 64) / "operations"
    _result(operations, 0, "queue_render")
    _result(operations, 1, "start_render", status="uncertain")
    monkeypatch.setattr(native, "verify_native_result", _verified_json)
    with pytest.raises(owner.NativeOwnerError):
        owner.preflight_native_owner()


@pytest.mark.parametrize(
    "changed",
    ["none", "sha", "jobs", "host", "next-operation", "effect", "record-symlink"],
)
def test_paused_historical_queue_is_isolated_only_with_exact_observation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, changed: str
) -> None:
    key = "8" * 64
    operations = owner.OUTPUT_TARGETS_ROOT / key / "operations"
    result_path = _result(operations, 0, "queue_render", status="uncertain")
    result = {
        "sequence": 0,
        "action": "queue_render",
        "status": "uncertain",
        "operationId": "paused-original",
        "target": {"projectUid": "old-project", "timelineUid": "old-timeline"},
        "effectLedger": [
            {"method": "Project.SetRenderSettings", "outcome": "observed"},
            {"method": "Project.AddRenderJob", "outcome": "unknown"},
        ],
    }
    result_path.write_text(json.dumps(result), encoding="utf-8")
    host = owner.OUTPUT_ATTEMPTS_ROOT / key
    host.mkdir(parents=True)
    (host / "chain.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(native, "verify_native_result", _verified_json)
    monkeypatch.setattr(
        owner, "_active_output_host_chains", lambda _: {key: "uncertain"}
    )
    record = {
        "schemaVersion": "vera.paused-output-observation/v1",
        "targetKey": key,
        "sequence": 0,
        "operationId": "paused-original",
        "resultSha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
        "hostHistorySha256": owner._output_host_history_sha256(key),
        "projectUid": "old-project",
        "timelineUid": "old-timeline",
        "observedAt": "2026-11-06T17:00:00+00:00",
        "observedStatuses": ["Complete"],
        "matchingJobCount": 0,
    }
    owner.PAUSED_OUTPUT_ROOT.mkdir(parents=True)
    attestation = owner.PAUSED_OUTPUT_ROOT / f"{key}.json"
    if changed == "sha":
        record["resultSha256"] = "f" * 64
    elif changed == "jobs":
        record["matchingJobCount"] = 1
    elif changed == "effect":
        ledger = result["effectLedger"]
        assert isinstance(ledger, list)
        assert isinstance(ledger[-1], dict)
        ledger[-1]["method"] = "Project.StartRendering"
        result_path.write_text(json.dumps(result), encoding="utf-8")
        record["resultSha256"] = hashlib.sha256(result_path.read_bytes()).hexdigest()
    elif changed == "host":
        (host / "chain.json").write_text('{"changed": true}', encoding="utf-8")
    elif changed == "next-operation":
        _result(operations, 1, "capture_post")
    if changed == "record-symlink":
        target = tmp_path / "other-observation.json"
        target.write_text(json.dumps(record), encoding="utf-8")
        attestation.symlink_to(target)
    else:
        attestation.write_text(json.dumps(record), encoding="utf-8")

    if changed == "none":
        owner.preflight_native_owner()
        with owner.native_owner():
            pass
    else:
        with pytest.raises(owner.NativeOwnerError) as error:
            owner.preflight_native_owner()
        assert error.value.reason == "output_operation_unresolved"


@pytest.mark.parametrize("active_render", [False, True])
def test_paused_queue_observation_uses_actual_exact_project_readback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, active_render: bool
) -> None:
    key = "7" * 64
    operations = owner.OUTPUT_TARGETS_ROOT / key / "operations"
    path = _result(operations, 0, "queue_render", status="uncertain")
    request_path = tmp_path / "old-request.json"
    output_path = tmp_path / "old-output.mov"
    request_raw = json.dumps({"payload": {"outputPath": str(output_path)}}).encode()
    request_path.write_bytes(request_raw)
    result = {
        "sequence": 0,
        "action": "queue_render",
        "status": "uncertain",
        "operationId": "old-queued-action",
        "nativeIdentity": {
            "product": "DaVinci Resolve Studio",
            "version": [21, 1, 1, 10, ""],
        },
        "target": {
            "projectUid": "old-project",
            "projectName": "old-project-name",
            "timelineUid": "old-timeline",
            "timelineName": "old-timeline-name",
        },
        "effectLedger": [{"method": "Project.AddRenderJob", "outcome": "unknown"}],
        "requestPath": str(request_path),
        "requestSha256": hashlib.sha256(request_raw).hexdigest(),
    }
    path.write_text(json.dumps(result), encoding="utf-8")
    old_bytes = path.read_bytes()
    host = owner.OUTPUT_ATTEMPTS_ROOT / key
    host.mkdir(parents=True)
    (host / "chain.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(native, "verify_native_result", _verified_json)
    monkeypatch.setattr(
        owner, "_active_output_host_chains", lambda _: {key: "uncertain"}
    )

    class FakeTimeline:
        def GetUniqueId(self) -> str:
            return "old-timeline"

        def GetName(self) -> str:
            return "old-timeline-name"

    class FakeProject:
        def GetUniqueId(self) -> str:
            return "old-project"

        def GetName(self) -> str:
            return "old-project-name"

        def GetCurrentTimeline(self) -> FakeTimeline:
            return FakeTimeline()

        def IsRenderingInProgress(self) -> bool:
            return active_render

        def GetRenderJobList(self) -> list[dict[str, str]]:
            return [{"JobId": "prior-completed", "OutputFilename": "other.mov"}]

        def GetRenderJobStatus(self, _id: str) -> dict[str, str]:
            return {"JobStatus": "Complete"}

    project = FakeProject()
    manager = SimpleNamespace(GetCurrentProject=lambda: project)
    resolve = SimpleNamespace(
        GetProductName=lambda: "DaVinci Resolve Studio",
        GetVersion=lambda: [21, 1, 1, 10, ""],
        GetProjectManager=lambda: manager,
    )
    monkeypatch.setitem(
        sys.modules,
        "DaVinciResolveScript",
        SimpleNamespace(scriptapp=lambda _: resolve),
    )
    if active_render:
        with pytest.raises(ValueError, match="active/unknown render"):
            owner.observe_paused_queue(path)
        assert not owner.PAUSED_OUTPUT_ROOT.exists()
    else:
        attested = owner.observe_paused_queue(path)
        assert json.loads(attested.read_bytes())["matchingJobCount"] == 0
        owner.preflight_native_owner()
        with pytest.raises(FileExistsError):
            owner.observe_paused_queue(path)
    assert path.read_bytes() == old_bytes


@pytest.mark.parametrize("expired", [False, True])
def test_preflight_checks_prepared_unstarted_authority_expiry(
    monkeypatch: pytest.MonkeyPatch, expired: bool
) -> None:
    key = "c" * 64
    operation = owner.OUTPUT_TARGETS_ROOT / key / "operations" / "00000000"
    operation.mkdir(parents=True)
    request_path = operation / "request.json"
    request = {"action": "construct", "context": {"test": "only"}}
    request_path.write_text(json.dumps(request), encoding="utf-8")
    expiry = datetime.now(UTC) + timedelta(days=-1 if expired else 1)
    monkeypatch.setattr(
        native,
        "verify_native_request",
        lambda _raw, **_kwargs: request,
    )
    monkeypatch.setattr(
        native,
        "_verify_authority",
        lambda *_args, **_kwargs: ({"expiresAt": expiry.isoformat()}, "d" * 64, {}),
    )
    monkeypatch.setattr(native, "_verify_reservation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        native, "_verify_intent", lambda *_args, **_kwargs: ({}, "e" * 64)
    )

    if expired:
        owner.preflight_native_owner()
    else:
        with pytest.raises(owner.NativeOwnerError) as error:
            owner.preflight_native_owner()
        assert error.value.reason == "output_operation_unresolved"


def test_preflight_does_not_treat_an_expired_unstarted_render_as_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = "f" * 64
    operations = owner.OUTPUT_TARGETS_ROOT / key / "operations"
    _result(operations, 0, "capture_pre")
    operation = operations / "00000001"
    operation.mkdir()
    request_path = operation / "request.json"
    request = {"action": "queue_render", "context": {"test": "only"}}
    request_path.write_text(json.dumps(request), encoding="utf-8")
    expiry = datetime.now(UTC) - timedelta(days=1)
    monkeypatch.setattr(native, "verify_native_result", _verified_json)
    monkeypatch.setattr(
        native,
        "verify_native_request",
        lambda _raw, **_kwargs: request,
    )
    monkeypatch.setattr(
        native,
        "_verify_authority",
        lambda *_args, **_kwargs: ({"expiresAt": expiry.isoformat()}, "d" * 64, {}),
    )
    monkeypatch.setattr(native, "_verify_reservation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        native, "_verify_intent", lambda *_args, **_kwargs: ({}, "e" * 64)
    )

    owner.preflight_native_owner()


@pytest.mark.parametrize("previously_started", [False, True])
def test_expired_unstarted_start_preserves_any_previously_started_render(
    monkeypatch: pytest.MonkeyPatch,
    previously_started: bool,
) -> None:
    operations = owner.OUTPUT_TARGETS_ROOT / ("9" * 64) / "operations"
    sequence = 0
    if previously_started:
        _result(operations, sequence, "start_render")
        sequence += 1
    queued = _result(operations, sequence, "queue_render")
    operation = operations / f"{sequence + 1:08d}"
    operation.mkdir()
    request = {"action": "start_render", "context": {"test": "only"}}
    (operation / "request.json").write_text(json.dumps(request))
    monkeypatch.setattr(native, "verify_native_result", _verified_json)
    monkeypatch.setattr(
        native, "verify_native_request", lambda *_args, **_kwargs: request
    )
    monkeypatch.setattr(
        native,
        "_verify_authority",
        lambda *_args, **_kwargs: (
            {"expiresAt": (datetime.now(UTC) - timedelta(days=1)).isoformat()},
            "d" * 64,
            {},
        ),
    )
    monkeypatch.setattr(native, "_verify_reservation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        native, "_verify_intent", lambda *_args, **_kwargs: ({}, "e" * 64)
    )
    original = queued.read_bytes()
    if previously_started:
        with pytest.raises(owner.NativeOwnerError):
            owner.preflight_native_owner()
    else:
        owner.preflight_native_owner()
    assert queued.read_bytes() == original
    assert json.loads(original)["action"] == "queue_render"


@pytest.mark.parametrize("record", ["request", "start", "effects"])
def test_preflight_rejects_symlinked_native_records(
    record: str, tmp_path: Path
) -> None:
    key = {"request": "1", "start": "2", "effects": "3"}[record] * 64
    operations = owner.OUTPUT_TARGETS_ROOT / key / "operations"
    operation = operations / "00000000"
    if record == "effects":
        operation.mkdir(parents=True)
        (operation / "effects").symlink_to(tmp_path / "missing-effects")
    else:
        result_path = _result(operations, 0, "capture_pre")
        record_path = (
            result_path.parent
            / {
                "request": "request.json",
                "start": "native-start.json",
            }[record]
        )
        target_path = tmp_path / f"{record}.json"
        target_path.write_text("{}", encoding="utf-8")
        record_path.unlink()
        record_path.symlink_to(target_path)

    with pytest.raises(owner.NativeOwnerError) as error:
        owner.preflight_native_owner()
    assert error.value.reason == "output_operation_unresolved"


def test_standalone_owner_does_not_import_the_output_host_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        owner,
        "_check_parent_operation",
        lambda: None,
    )
    monkeypatch.setattr(
        owner,
        "_check_issue328_marker",
        lambda: None,
    )
    monkeypatch.setattr(owner, "_active_output_host_chains", lambda _native: {})
    with owner.native_owner():
        assert owner.OWNER_LOCK_PATH.exists()


def test_standalone_writers_refuse_retained_render_but_output_can_continue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        owner, "_active_output_host_chains", lambda _native: {"chain": "uncertain"}
    )
    with pytest.raises(owner.NativeOwnerError), owner.native_owner():
        pytest.fail("a non-output writer stole an unresolved render reservation")
    with owner.native_owner(output_lane=True):
        assert owner.OWNER_LOCK_PATH.exists()
