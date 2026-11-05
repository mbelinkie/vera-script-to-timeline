from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
    monkeypatch.setattr(
        owner,
        "_active_output_host_chains",
        lambda _native: pytest.fail("standalone entries use their lane guard"),
    )
    with owner.native_owner():
        assert owner.OWNER_LOCK_PATH.exists()
