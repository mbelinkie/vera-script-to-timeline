"""Operation-local reuse for native result and host-history verification."""

from __future__ import annotations

import hashlib
import json
import stat
from collections import Counter
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent.qualification_output_records_v2 import (
    OutputConsistencyError,
    _canonical,
)

_runtime_fixture: Any = import_module("test_issue209_seam")._runtime_fixture
_record_host_failure: Any = import_module("test_issue248_native")._record_host_failure


def test_result_verification_reuses_only_completed_path_digest_pairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = (tmp_path / "root.json", "a" * 64)
    left = (tmp_path / "left.json", "b" * 64)
    right = (tmp_path / "right.json", "c" * 64)
    shared = (tmp_path / "shared.json", "d" * 64)
    same_path_new_digest = (shared[0], "e" * 64)
    children = {
        root: [left, right],
        left: [shared],
        right: [shared, same_path_new_digest],
    }
    calls: list[tuple[Path, str]] = []

    def verify(path: Path, digest: str) -> dict[str, str]:
        key = (path, digest)
        calls.append(key)
        for child in children.get(key, []):
            native.verify_native_result(*child)
        return {"path": str(path), "digest": digest}

    monkeypatch.setattr(native, "_verify_native_result", verify)

    native.verify_native_result(*root)
    expected_keys = set(children) | {shared, same_path_new_digest}
    assert Counter(calls) == Counter(dict.fromkeys(expected_keys, 1))

    native.verify_native_result(*root)
    assert Counter(calls) == Counter(dict.fromkeys(expected_keys, 2))


def test_failed_result_verification_is_not_cached_and_clears_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "result.json"
    digest = "a" * 64
    calls = 0

    def verify(_path: Path, _digest: str) -> dict[str, str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OutputConsistencyError("first verification failed")
        return {"status": "complete"}

    monkeypatch.setattr(native, "_verify_native_result", verify)

    with pytest.raises(OutputConsistencyError, match="first verification failed"):
        native.verify_native_result(path, digest)
    assert native._VERIFICATION.get() is None
    assert native.verify_native_result(path, digest) == {"status": "complete"}
    assert calls == 2
    assert native._VERIFICATION.get() is None


def test_host_history_is_shared_within_one_scope_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = {
        "target": {"projectUid": "project-one", "timelineUid": "timeline-one"},
        "caseId": "case-one",
        "phase": "pristine",
    }
    rows = [{"state": "committed"}]
    calls = 0

    def verify(_context: dict[str, Any]) -> list[dict[str, str]]:
        nonlocal calls
        calls += 1
        return rows

    monkeypatch.setattr(native, "_verify_host_attempt_history", verify)

    with native._verification_scope():
        assert native._host_attempt_history(context) is rows
        assert native._host_attempt_history(context) is rows
    assert calls == 1

    with native._verification_scope():
        assert native._host_attempt_history(context) is rows
    assert calls == 2


def _write_preserving_mode(path: Path, raw: bytes) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    path.chmod(mode | stat.S_IWUSR)
    try:
        path.write_bytes(raw)
    finally:
        path.chmod(mode)


def test_host_history_reads_reused_retained_artifact_once_per_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, _, _, context, _, _ = _runtime_fixture(tmp_path, monkeypatch)
    prediction = b"stable render prediction"
    _record_host_failure(controller, context, prediction, sequence=5, attempt=1)
    _record_host_failure(controller, context, prediction, sequence=9, attempt=2)
    prediction_digest = hashlib.sha256(prediction).hexdigest()
    prediction_path = controller.journal.artifacts / prediction_digest
    reads: list[Path] = []
    original_read = native._read

    def count_read(path: Path, label: str, **kwargs: Any) -> bytes:
        if label == "host retained attempt artifact":
            reads.append(path)
        return original_read(path, label, **kwargs)

    monkeypatch.setattr(native, "_read", count_read)

    for _ in range(2):
        with native._verification_scope():
            history = native._host_attempt_history(context)
            assert [row["state"] for row in history] == [
                "committed",
                "reserved_by_render_intent",
                "render_failed",
                "committed",
                "reserved_by_render_intent",
                "render_failed",
            ]

    assert reads.count(prediction_path) == 2

    original_mode = stat.S_IMODE(prediction_path.stat().st_mode)
    _write_preserving_mode(prediction_path, b"changed retained prediction")
    assert stat.S_IMODE(prediction_path.stat().st_mode) == original_mode
    with pytest.raises(OutputConsistencyError, match="host retained artifact changed"):
        native._host_attempt_history(context)


def test_native_operation_tail_reuses_ancestors_across_result_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, _, context, _, _ = _runtime_fixture(tmp_path, monkeypatch)
    first_path = native.native_request_paths(context, 0)[0]
    second_path = native.native_request_paths(context, 1)[0]
    first_path.parent.mkdir(parents=True)
    first_path.write_bytes(b"result-zero")
    first_path.chmod(0o400)
    second_path.parent.mkdir(parents=True)
    second_path.write_bytes(b"result-one")
    second_path.chmod(0o400)
    first_digest = hashlib.sha256(first_path.read_bytes()).hexdigest()
    second_digest = hashlib.sha256(second_path.read_bytes()).hexdigest()
    calls: list[tuple[Path, str]] = []

    def verify(path: Path, digest: str) -> dict[str, Any]:
        calls.append((path, digest))
        if path == second_path:
            native.verify_native_result(first_path, first_digest)
        return {"sequence": int(path.parent.name), "status": "complete"}

    monkeypatch.setattr(native, "_verify_native_result", verify)

    assert native._native_operation_tail(context) == (2, second_digest)
    assert Counter(calls) == Counter(
        {(first_path, first_digest): 1, (second_path, second_digest): 1}
    )


@pytest.mark.parametrize("tamper", ["authority", "result"])
def test_public_result_verification_rechecks_changed_retained_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tamper: str
) -> None:
    controller, approval_path, installed_root, context, resolve, _ = _runtime_fixture(
        tmp_path, monkeypatch
    )
    request_path = controller.prepare_native_request(
        "construct", {}, approval_path=approval_path
    )
    request_raw = request_path.read_bytes()
    installed_root.mkdir()
    installed_request = installed_root / "request.json"
    installed_request.write_bytes(request_raw)
    installed_request.chmod(0o400)
    result_path = native.run_qualification_output_request(
        resolve,
        installed_request,
        expected_request_sha256=hashlib.sha256(request_raw).hexdigest(),
    )
    result_raw = result_path.read_bytes()
    result_digest = hashlib.sha256(result_raw).hexdigest()
    assert (
        native.verify_native_result(result_path, result_digest)["status"] == "complete"
    )

    expected_digest = result_digest
    if tamper == "authority":
        authority_path = native.native_request_paths(context, 0)[1]
        authority = json.loads(authority_path.read_bytes())
        authority["permissions"] = ["save_reopen"]
        _write_preserving_mode(authority_path, _canonical(authority))
        error = "native authority digest differs"
    else:
        result = json.loads(result_raw)
        result["action"] = "save_reopen"
        tampered_raw = _canonical(result)
        _write_preserving_mode(result_path, tampered_raw)
        expected_digest = hashlib.sha256(tampered_raw).hexdigest()
        error = "native action order differs"

    with pytest.raises(OutputConsistencyError, match=error):
        native.verify_native_result(result_path, expected_digest)
