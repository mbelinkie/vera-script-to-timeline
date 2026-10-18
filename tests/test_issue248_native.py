"""Bounded native retry admission and lineage checks for issue #248."""

from __future__ import annotations

import hashlib
import json
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent.qualification_output_records_v2 import (
    LANE,
    OutputConsistencyError,
    _canonical,
)

_runtime_fixture: Any = import_module("test_issue209_seam")._runtime_fixture


def _failure(status: str = "Failed") -> dict[str, Any]:
    return {
        "action": "poll_render",
        "sequence": 5,
        "status": "partial",
        "renderStatus": {"JobStatus": status},
        "jobId": "failed-job",
    }


@pytest.mark.parametrize("failed_status", ["Failed", "Cancelled"])
def test_native_action_preserves_original_stages_and_resolves_only_one_retry(
    monkeypatch: pytest.MonkeyPatch,
    failed_status: str,
) -> None:
    context: dict[str, Any] = {}
    assert [native.native_action(context, index) for index in range(6)] == list(
        native.APPROVAL_ACTION_PLAN[:6]
    )

    poll = _failure(failed_status)
    retry_capture = {
        "action": "retry_capture",
        "sequence": 6,
        "status": "complete",
    }
    queue = {
        "action": "queue_render",
        "sequence": 3,
        "status": "complete",
        "jobId": "failed-job",
        "outputPath": "/tmp/binding.mov",
        "settings": {},
        "commitmentRawSha256": "a" * 64,
        "reservationSha256": "b" * 64,
        "renderIntentSha256": "c" * 64,
    }
    start = {
        **queue,
        "action": "start_render",
        "sequence": 4,
        "queuedResultSha256": "d" * 64,
    }
    results = {3: queue, 4: start, 5: poll, 6: retry_capture}

    monkeypatch.setattr(
        native, "_routing_result_at", lambda _context, seq: results[seq]
    )

    assert native.native_action(context, 6) == "retry_capture"
    assert [native.native_action(context, index) for index in range(7, 11)] == list(
        native.RETRY_ACTION_PLAN[1:]
    )
    with pytest.raises(OutputConsistencyError, match="action plan is exhausted"):
        native.native_action(context, 11)


@pytest.mark.parametrize("job_status", ["Rendering", "Queued", "unknown", "Complete"])
def test_native_action_does_not_turn_nonterminal_poll_into_retry(
    monkeypatch: pytest.MonkeyPatch, job_status: str
) -> None:
    monkeypatch.setattr(
        native,
        "_routing_result_at",
        lambda _context, _sequence: _failure(job_status),
    )
    with pytest.raises(OutputConsistencyError, match="only a terminal"):
        native.native_action({}, 6)


def test_native_action_routing_does_not_recursively_verify_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results = {
        5: _failure(),
        6: {"action": "retry_capture", "sequence": 6, "status": "complete"},
    }
    monkeypatch.setattr(
        native, "_routing_result_at", lambda _context, seq: results[seq]
    )
    calls = 0

    def verify(_path: Path, _expected_sha256: str) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise AssertionError("action routing must not recursively verify history")

    monkeypatch.setattr(native, "verify_native_result", verify)

    assert [native.native_action({}, sequence) for sequence in range(6, 11)] == [
        "retry_capture",
        "queue_render",
        "start_render",
        "poll_render",
        "capture_post",
    ]
    assert calls == 0


def _record_host_failure(
    controller: Any,
    context: dict[str, Any],
    prediction: bytes,
    sequence: int,
    attempt: int,
) -> None:
    journal = controller.journal
    commitment = _canonical(
        {
            "context": context,
            "predictionBytesSha256": hashlib.sha256(prediction).hexdigest(),
            "commitmentReceiptSha256": f"{attempt:064x}",
        }
    )
    commitment_value = json.loads(commitment)
    commitment_payload_sha = hashlib.sha256(
        _canonical(
            {
                key: value
                for key, value in commitment_value.items()
                if key != "commitmentReceiptSha256"
            }
        )
    ).hexdigest()
    journal.commit(context, commitment, prediction)
    reservation = _canonical(
        {
            "context": context,
            "commitmentRawSha256": hashlib.sha256(commitment).hexdigest(),
            "commitmentPayloadSha256": commitment_payload_sha,
        }
    )
    rows = journal.history()
    journal.transition(
        context,
        "reserved_by_render_intent",
        expected_head=rows[-1]["entrySha256"],
        reservation=reservation,
    )
    result: dict[str, Any] = dict.fromkeys(native.RESULT_FIELDS)
    result.update(
        {
            "schemaVersion": native.RESULT_SCHEMA,
            "lane": LANE,
            "profile": native.SYNTHETIC_PROFILE,
            "action": "poll_render",
            "operationId": f"host-history-test-{sequence}",
            "sequence": sequence,
            "priorResultSha256": "0" * 64,
            "requestSha256": "1" * 64,
            "authoritySha256": "2" * 64,
            "intentSha256": "3" * 64,
            "reservationSha256": hashlib.sha256(reservation).hexdigest(),
            "context": context,
            "target": context["target"],
            "status": "partial",
            "reason": "Resolve reported a terminal failed render",
            "commitmentRawSha256": hashlib.sha256(commitment).hexdigest(),
            "renderStatus": {"JobStatus": "Failed"},
            "effectLedger": [],
        }
    )
    result_raw = _canonical(result)
    result_path = native.native_request_paths(context, sequence)[0]
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_bytes(result_raw)
    result_path.chmod(0o400)
    rows = journal.history()
    journal.transition(
        context,
        "render_failed",
        expected_head=rows[-1]["entrySha256"],
        result=result_raw,
    )


def test_host_attempt_history_authenticates_original_and_retry_poll_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller, _, _, context, _, _ = _runtime_fixture(tmp_path, monkeypatch)
    prediction = b"stable render prediction"

    _record_host_failure(controller, context, prediction, sequence=5, attempt=1)
    _record_host_failure(controller, context, prediction, sequence=9, attempt=2)

    history = native._host_attempt_history(context)
    assert [row["state"] for row in history] == [
        "committed",
        "reserved_by_render_intent",
        "render_failed",
        "committed",
        "reserved_by_render_intent",
        "render_failed",
    ]


def test_host_attempt_history_rejects_non_poll_retry_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller, _, _, context, _, _ = _runtime_fixture(tmp_path, monkeypatch)
    prediction = b"stable render prediction"

    _record_host_failure(controller, context, prediction, sequence=5, attempt=1)
    _record_host_failure(controller, context, prediction, sequence=10, attempt=2)

    with pytest.raises(OutputConsistencyError, match="outside the reviewed poll slots"):
        native._host_attempt_history(context)


def test_full_native_chain_verification_rejects_tampered_result_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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

    tampered = json.loads(result_path.read_bytes())
    tampered["action"] = "save_reopen"
    result_path.chmod(0o600)
    result_path.write_bytes(_canonical(tampered))
    result_path.chmod(0o400)

    with pytest.raises(OutputConsistencyError, match="native action order differs"):
        native._native_operation_tail(context)


def test_refused_retry_capture_does_not_need_matching_geometry() -> None:
    original_capture = {
        "action": "capture_pre",
        "status": "complete",
        "nativeGeometry": {"timeline": "original"},
        "inputBindingSha256": "a" * 64,
    }
    refused_capture = {
        "status": "refused",
        "nativeGeometry": None,
        "inputBindingSha256": None,
    }

    native._verify_retry_capture_geometry(refused_capture, original_capture)
    with pytest.raises(OutputConsistencyError, match="differs from original"):
        native._verify_retry_capture_geometry(
            {
                **refused_capture,
                "status": "complete",
                "nativeGeometry": {"timeline": "changed"},
            },
            original_capture,
        )


def test_next_native_operation_requires_explicit_retry_after_failed_poll(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "operations"
    context: dict[str, Any] = {}
    rows = {
        sequence: {
            "sequence": sequence,
            "status": "complete",
            "action": native.APPROVAL_ACTION_PLAN[sequence],
        }
        for sequence in range(5)
    }
    rows[5] = _failure()

    def paths(_context: dict[str, Any], sequence: int) -> tuple[Path, Path, Path, Path]:
        operation = root / f"{sequence:08d}"
        return (
            operation / "result.json",
            operation / "authority.json",
            operation / "intent.json",
            operation / "request.json",
        )

    monkeypatch.setattr(native, "_context", lambda value: value)
    monkeypatch.setattr(native, "native_request_paths", paths)
    monkeypatch.setattr(
        native, "verify_native_result", lambda path, _sha: rows[int(path.parent.name)]
    )
    monkeypatch.setattr(
        native, "_routing_result_at", lambda _context, sequence: rows[sequence]
    )
    monkeypatch.setattr(
        native,
        "verified_render_failure",
        lambda _context: (Path("/tmp/5.json"), "5" * 64, rows[5]),
    )

    with pytest.raises(OutputConsistencyError, match="explicit retry entrypoint"):
        native.next_native_operation(context, retry=True)

    for sequence in range(6):
        result_path = paths(context, sequence)[0]
        result_path.parent.mkdir(parents=True)
        result_path.write_bytes(f"result-{sequence}".encode())

    with pytest.raises(OutputConsistencyError, match="partial/uncertain"):
        native.next_native_operation(context)

    rows[5] = _failure("Rendering")
    with pytest.raises(OutputConsistencyError, match="partial/uncertain"):
        native.next_native_operation(context, retry=True)

    rows[5] = _failure()

    sequence, prior = native.next_native_operation(context, retry=True)
    assert sequence == 6
    assert prior == hashlib.sha256(b"result-5").hexdigest()


def test_poll_result_retains_terminal_failure_and_partial_output_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started_path = tmp_path / "started.json"
    started_path.write_bytes(b"started")
    output_path = tmp_path / "partial.mov"
    output_path.write_bytes(b"partial render bytes")
    started_sha = hashlib.sha256(b"started").hexdigest()
    previous = {
        "jobId": "failed-job",
        "outputPath": str(output_path),
        "settings": {},
        "commitmentRawSha256": "a" * 64,
        "reservationSha256": "b" * 64,
        "renderIntentSha256": "c" * 64,
        "queuedResultSha256": "d" * 64,
        "startedAt": "2026-10-16T12:00:00Z",
    }
    project = type(
        "Project",
        (),
        {"GetRenderJobStatus": lambda _self, _job_id: {"JobStatus": "Failed"}},
    )()
    request = {
        "sequence": 5,
        "payload": {
            "startedResultPath": str(started_path),
            "startedResultSha256": started_sha,
            "jobId": "failed-job",
        },
    }
    monkeypatch.setattr(
        native,
        "_previous_result",
        lambda *_args: (previous, started_sha, started_path),
    )
    monkeypatch.setattr(
        native, "_project_timeline", lambda *_args: (None, project, None)
    )

    result = native._poll_render(request, object(), {}, None)

    assert result["status"] == "partial"
    assert result["renderStatus"] == {"JobStatus": "Failed"}
    assert (
        result["sourceOutputRawSha256"]
        == hashlib.sha256(b"partial render bytes").hexdigest()
    )


@pytest.mark.parametrize(
    ("render_state", "message"),
    [
        (None, "render state unavailable"),
        (True, "still rendering"),
        ("raise", "render state is unreadable"),
    ],
)
def test_retry_requires_resolve_to_confirm_rendering_has_stopped(
    render_state: Any, message: str
) -> None:
    class Project:
        def IsRenderingInProgress(self) -> Any:
            if render_state == "raise":
                raise RuntimeError("Resolve status read failed")
            return render_state

    project = Project()
    if render_state is None:
        delattr(Project, "IsRenderingInProgress")
    with pytest.raises(OutputConsistencyError, match=message):
        native._verify_retry_job_quiescent(project, _failure())


def test_retry_capture_requires_unchanged_geometry_and_terminal_queue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path.resolve()
    retry_output = base / "binding-retry-1.mov"
    context: dict[str, Any] = {}
    geometry = {"context": context, "timeline": "unchanged"}
    original_capture = {
        "action": "capture_pre",
        "status": "complete",
        "nativeGeometry": geometry,
        "inputBindingSha256": "a" * 64,
    }
    failed_output = base / "binding.mov"
    failed_output.write_bytes(b"retained partial output")
    failure = {
        **_failure(),
        "outputPath": str(failed_output),
        "sourceOutputRawSha256": hashlib.sha256(b"retained partial output").hexdigest(),
    }

    class Project:
        def IsRenderingInProgress(self) -> bool:
            return False

        def GetRenderJobList(self) -> list[dict[str, str]]:
            return [{"JobId": "failed-job"}]

        def GetRenderJobStatus(self, _job_id: str) -> dict[str, str]:
            return {"JobStatus": "Failed"}

    project = Project()
    request = {
        "context": context,
    }
    monkeypatch.setattr(
        native,
        "_previous_result",
        lambda *_args: (failure, "e" * 64, Path("/tmp/5.json")),
    )
    monkeypatch.setattr(native, "verified_render_failure", lambda _context: None)
    monkeypatch.setattr(
        native,
        "_native_result_at",
        lambda _context, sequence: (
            base / f"{sequence}.json",
            f"{sequence:x}" * 64,
            original_capture
            if sequence == 2
            else {
                "action": "queue_render",
                "status": "complete",
                "sequence": 3,
                "outputPath": "/tmp/binding.mov",
            },
        ),
    )
    monkeypatch.setattr(
        native,
        "_input_binding",
        lambda *_args: ({}, b"", "a" * 64, base / "binding.json"),
    )
    monkeypatch.setattr(
        native, "_project_timeline", lambda *_args: (None, project, None)
    )
    monkeypatch.setattr(
        native,
        "_verify_authority",
        lambda *_args, **_kwargs: ({}, "", {"outputPath": str(retry_output)}),
    )
    monkeypatch.setattr(native, "_retry_output_path", lambda _context: retry_output)
    monkeypatch.setattr(
        native,
        "_capture",
        lambda *_args, **_kwargs: {
            "nativeGeometry": geometry,
            "inputBindingSha256": "a" * 64,
        },
    )

    assert native._retry_capture(request, object(), {})["nativeGeometry"] == geometry

    monkeypatch.setattr(
        native,
        "_capture",
        lambda *_args, **_kwargs: {
            "nativeGeometry": {"context": context, "timeline": "changed"},
            "inputBindingSha256": "a" * 64,
        },
    )
    with pytest.raises(
        OutputConsistencyError, match="geometry or input binding changed"
    ):
        native._retry_capture(request, object(), {})

    failed_output.write_bytes(b"changed partial output")
    with pytest.raises(OutputConsistencyError, match="output changed before retry"):
        native._retry_capture(request, object(), {})


def test_retry_capture_request_is_valid_before_reservation_and_uses_fresh_approval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller, original_approval_path, _, context, _, _ = _runtime_fixture(
        tmp_path, monkeypatch
    )
    prediction = b"stable retry prediction"
    commitment = _canonical(
        {
            "context": context,
            "predictionBytesSha256": hashlib.sha256(prediction).hexdigest(),
            "commitmentReceiptSha256": "a" * 64,
        }
    )
    controller.journal.commit(context, commitment, prediction)
    commitment_value = json.loads(commitment)
    reservation = _canonical(
        {
            "context": context,
            "commitmentRawSha256": hashlib.sha256(commitment).hexdigest(),
            "commitmentPayloadSha256": hashlib.sha256(
                _canonical(
                    {
                        key: value
                        for key, value in commitment_value.items()
                        if key != "commitmentReceiptSha256"
                    }
                )
            ).hexdigest(),
        }
    )
    rows = controller.journal.history()
    controller.journal.transition(
        context,
        "reserved_by_render_intent",
        expected_head=rows[-1]["entrySha256"],
        reservation=reservation,
    )
    failed_result = _canonical(
        {
            "context": context,
            "status": "partial",
            "action": "poll_render",
            "renderStatus": {"JobStatus": "Failed"},
            "reservationSha256": hashlib.sha256(reservation).hexdigest(),
            "commitmentRawSha256": hashlib.sha256(commitment).hexdigest(),
        }
    )
    rows = controller.journal.history()
    controller.journal.transition(
        context,
        "render_failed",
        expected_head=rows[-1]["entrySha256"],
        result=failed_result,
    )

    original_approval_raw = original_approval_path.read_bytes()
    retry_approval = json.loads(original_approval_raw)
    retry_approval["approvalId"] = "approval-retry-one"
    retry_approval["actionPlan"] = list(native.RETRY_ACTION_PLAN)
    retry_approval["outputPath"] = str(
        Path(retry_approval["outputPath"]).with_name("approved-retry-1.mov")
    )
    retry_approval_path = tmp_path / "retry-approval.json"
    retry_approval_path.write_bytes(_canonical(retry_approval))
    retry_approval_path.chmod(0o400)
    input_binding_path = tmp_path / "retry-input-binding.json"
    input_binding_path.write_bytes(_canonical({"context": context}))
    input_binding_path.chmod(0o400)
    monkeypatch.setattr(
        controller,
        "_input_binding",
        lambda: (input_binding_path.read_bytes(), input_binding_path),
    )
    monkeypatch.setattr(
        native,
        "next_native_operation",
        lambda _context, retry=False: (6, hashlib.sha256(failed_result).hexdigest()),
    )
    monkeypatch.setattr(
        native,
        "native_action",
        lambda _context, _sequence: "retry_capture",
    )

    request_path = controller.prepare_render_retry_request(retry_approval_path)
    request_raw = request_path.read_bytes()
    request = native.verify_native_request(
        request_raw,
        expected_request_sha256=hashlib.sha256(request_raw).hexdigest(),
    )
    assert request["sequence"] == 6
    assert request["reservation"] is None
    assert request["renderIntent"] is None
    assert native._approval_plan_for_request(request) == native.RETRY_ACTION_PLAN
    assert all(
        native._approval_plan_for_request({"sequence": sequence, "action": action})
        == native.RETRY_ACTION_PLAN
        for sequence, action in (
            (6, "retry_capture"),
            (7, "queue_render"),
            (8, "start_render"),
        )
    )
    authority, authority_sha, checked_approval = native._verify_authority(request)
    _, intent_sha = native._verify_intent(request, authority_sha, None)
    assert authority["action"] == "retry_capture"
    assert checked_approval["actionPlan"] == list(native.RETRY_ACTION_PLAN)
    assert intent_sha == request["intent"]["sha256"]

    stale_authority = json.loads(Path(request["authority"]["path"]).read_bytes())
    stale_authority["approvalPath"] = str(original_approval_path)
    stale_authority["approvalSha256"] = hashlib.sha256(
        original_approval_raw
    ).hexdigest()
    stale_authority_raw = _canonical(stale_authority)
    stale_authority_path = tmp_path / "retry-authority-with-original-approval.json"
    stale_authority_path.write_bytes(stale_authority_raw)
    stale_authority_path.chmod(0o400)
    stale_request = {
        **request,
        "authority": {
            "path": str(stale_authority_path),
            "sha256": hashlib.sha256(stale_authority_raw).hexdigest(),
        },
    }
    with pytest.raises(
        OutputConsistencyError, match="outside the reviewed approval plan"
    ):
        native._verify_authority(stale_request)


def test_retry_queue_rechecks_geometry_before_render_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context: dict[str, Any] = {}
    original_geometry = {"context": context, "timeline": "original"}
    calls: list[str] = []
    retry_capture = {
        "action": "retry_capture",
        "status": "complete",
        "nativeGeometry": original_geometry,
        "inputBindingPath": "/tmp/binding.json",
        "inputBindingSha256": "a" * 64,
    }
    failure = _failure()
    original = {
        "action": "capture_pre",
        "status": "complete",
        "nativeGeometry": original_geometry,
        "inputBindingSha256": "a" * 64,
    }
    monkeypatch.setattr(
        native,
        "_previous_result",
        lambda *_args: (retry_capture, "e" * 64, Path("/tmp/6.json")),
    )
    monkeypatch.setattr(
        native,
        "_native_result_at",
        lambda _context, sequence: (
            Path(f"/tmp/{sequence}.json"),
            f"{sequence:x}" * 64,
            failure if sequence == 5 else original,
        ),
    )
    monkeypatch.setattr(native, "verified_render_failure", lambda _context: None)
    monkeypatch.setattr(
        native, "_project_timeline", lambda *_args: (None, object(), None)
    )
    monkeypatch.setattr(native, "_verify_retry_job_quiescent", lambda *_args: None)
    monkeypatch.setattr(
        native,
        "_input_binding",
        lambda *_args: ({}, b"", "a" * 64, Path("/tmp/binding.json")),
    )

    def capture_geometry(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        calls.append("geometry")
        return {"context": context, "timeline": "changed"}

    monkeypatch.setattr(native, "_capture_geometry", capture_geometry)

    request = {
        "sequence": 7,
        "context": context,
        "package": {"packageRoot": "/tmp/package"},
        "profile": native.SYNTHETIC_PROFILE,
        "payload": {
            "settings": {},
            "outputPath": "/tmp/binding-retry-1.mov",
            "outputFilename": "binding-retry-1",
        },
    }
    state: dict[str, Any] = {"effects": []}
    with pytest.raises(
        OutputConsistencyError, match="geometry or input binding changed"
    ):
        native._queue_render(request, object(), {}, state, None)
    assert calls == ["geometry"]
    assert state["effects"] == []
