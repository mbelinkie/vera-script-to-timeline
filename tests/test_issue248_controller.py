"""Durable host-journal rules for one confirmed failed-render retry."""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent.qualification_output_controller_v2 import (
    OutputAttemptJournal,
    QualificationOutputController,
)
from vera_timeline_agent.qualification_output_records_v2 import (
    EMPTY_HEAD,
    OutputConsistencyError,
    _canonical,
    _hash,
)

_attempt_helpers: Any = import_module("test_issue209_controller")
commit: Any = _attempt_helpers.commit
context: Any = _attempt_helpers.context
reserve: Any = _attempt_helpers.reserve


def _controller(
    journal: OutputAttemptJournal, ctx: dict[str, Any]
) -> QualificationOutputController:
    controller = object.__new__(QualificationOutputController)
    controller.context = ctx
    controller.journal = journal
    return controller


def _failure_bytes(
    ctx: dict[str, Any], reservation: dict[str, Any], *, status: str = "Failed"
) -> bytes:
    return _canonical(
        {
            "context": ctx,
            "status": "partial",
            "action": "poll_render",
            "renderStatus": {"JobStatus": status},
            "reservationSha256": reservation["reservationRawSha256"],
            "commitmentRawSha256": reservation["commitmentRawSha256"],
        }
    )


def _install_result_verifier(
    monkeypatch: pytest.MonkeyPatch, expected: dict[str, Any]
) -> None:
    def verify(path: Path, result_sha256: str) -> dict[str, Any]:
        raw = path.read_bytes()
        if _hash(raw) != result_sha256:
            raise OutputConsistencyError("native result digest differs")
        return expected

    monkeypatch.setattr(native, "verify_native_result", verify)


def _recommit(
    journal: OutputAttemptJournal,
    ctx: dict[str, Any],
    prediction: bytes = b"prediction",
) -> dict[str, Any]:
    return journal.commit(
        ctx,
        _canonical(
            {
                "context": ctx,
                "predictionBytesSha256": _hash(prediction),
                "commitmentReceiptSha256": "c" * 64,
                "retryCommitment": True,
            }
        ),
        prediction,
    )


def _record_failed_render(
    controller: QualificationOutputController,
    reservation: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    path: Path,
    *,
    status: str = "Failed",
) -> tuple[Path, str]:
    raw = _failure_bytes(controller.context, reservation, status=status)
    path.write_bytes(raw)
    _install_result_verifier(
        monkeypatch,
        {
            **json.loads(raw),
            "reservationSha256": reservation["reservationRawSha256"],
            "commitmentRawSha256": reservation["commitmentRawSha256"],
        },
    )
    result = (path, _hash(raw))
    controller.record_native_failure(result)
    return result


def test_failed_attempt_is_preserved_across_one_recommit_and_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = context()
    journal = OutputAttemptJournal(tmp_path / "private", ctx)
    controller = _controller(journal, ctx)
    first_commit = commit(journal, ctx)
    first_reservation = reserve(journal, first_commit)
    failed_path = tmp_path / "failed-poll.json"
    failed_path.write_bytes(_failure_bytes(ctx, first_reservation, status="Cancelled"))
    failure_raw = failed_path.read_bytes()
    _install_result_verifier(
        monkeypatch,
        json.loads(failure_raw),
    )
    controller.record_native_failure((failed_path, _hash(failure_raw)))

    retry_commit = _recommit(journal, ctx)
    retry_reservation = reserve(journal, retry_commit)

    rows = journal.history()
    assert [row["state"] for row in rows] == [
        "committed",
        "reserved_by_render_intent",
        "render_failed",
        "committed",
        "reserved_by_render_intent",
    ]
    assert rows[2]["resultRawSha256"] == _hash(failure_raw)
    assert rows[0]["reservationRawSha256"] is None
    assert rows[1]["reservationRawSha256"] != rows[4]["reservationRawSha256"]
    assert rows[3]["commitmentRawSha256"] != rows[0]["commitmentRawSha256"]
    assert rows[3]["context"] == rows[0]["context"] == ctx
    assert rows[3]["predictionBytesSha256"] == rows[0]["predictionBytesSha256"]
    assert retry_reservation["reservationRawSha256"] == rows[4]["reservationRawSha256"]


def test_second_failed_render_exhausts_the_binding_retry_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = context()
    journal = OutputAttemptJournal(tmp_path / "private", ctx)
    controller = _controller(journal, ctx)
    first_reservation = reserve(journal, commit(journal, ctx))
    _record_failed_render(
        controller, first_reservation, monkeypatch, tmp_path / "first-failure.json"
    )
    second_reservation = reserve(journal, _recommit(journal, ctx))
    _record_failed_render(
        controller,
        second_reservation,
        monkeypatch,
        tmp_path / "second-failure.json",
    )

    with pytest.raises(OutputConsistencyError, match="retry budget exhausted"):
        _recommit(journal, ctx)
    assert [row["state"] for row in journal.history()].count("render_failed") == 2


@pytest.mark.parametrize("changed", ["context", "prediction"])
def test_retry_refuses_changed_context_or_prediction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    ctx = context()
    journal = OutputAttemptJournal(tmp_path / "private", ctx)
    controller = _controller(journal, ctx)
    reservation = reserve(journal, commit(journal, ctx))
    _record_failed_render(
        controller, reservation, monkeypatch, tmp_path / "failed-poll.json"
    )

    if changed == "context":
        with pytest.raises(
            OutputConsistencyError, match="recommitted prediction or context"
        ):
            _recommit(journal, context(invocation="invocation-two"))
    else:
        with pytest.raises(
            OutputConsistencyError, match="recommitted prediction or context"
        ):
            _recommit(journal, ctx, prediction=b"changed prediction")


def test_uncertain_result_cannot_be_recommitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = context()
    journal = OutputAttemptJournal(tmp_path / "private", ctx)
    controller = _controller(journal, ctx)
    reserved = reserve(journal, commit(journal, ctx))
    raw = _canonical({"context": ctx, "status": "partial", "action": "queue_render"})
    path = tmp_path / "uncertain-result.json"
    path.write_bytes(raw)
    _install_result_verifier(monkeypatch, json.loads(raw))
    controller.record_uncertain((path, _hash(raw)))

    with pytest.raises(OutputConsistencyError, match="already attempted"):
        _recommit(journal, ctx)
    assert journal.history()[-1]["state"] == "uncertain"
    assert reserved["state"] == "reserved_by_render_intent"


@pytest.mark.parametrize(
    "native_status,job_status",
    [("refused", "Failed"), ("complete", "Complete"), ("partial", "Error")],
)
def test_only_terminal_failed_or_cancelled_poll_can_enter_render_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    native_status: str,
    job_status: str,
) -> None:
    ctx = context()
    journal = OutputAttemptJournal(tmp_path / "private", ctx)
    controller = _controller(journal, ctx)
    reservation = reserve(journal, commit(journal, ctx))
    raw = _failure_bytes(ctx, reservation, status=job_status)
    path = tmp_path / "poll-result.json"
    path.write_bytes(raw)
    _install_result_verifier(
        monkeypatch,
        {
            **json.loads(raw),
            "status": native_status,
        },
    )

    with pytest.raises(OutputConsistencyError, match="actual terminal render failure"):
        controller.record_native_failure((path, _hash(raw)))
    assert journal.history()[-1]["state"] == "reserved_by_render_intent"


def test_retry_plan_requires_matching_ingested_native_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = context()
    journal = OutputAttemptJournal(tmp_path / "private", ctx)
    controller = _controller(journal, ctx)
    reservation = reserve(journal, commit(journal, ctx))
    failure_path = tmp_path / "failed-poll.json"
    failure_raw = _failure_bytes(ctx, reservation)
    failure_path.write_bytes(failure_raw)
    failure_sha = _hash(failure_raw)
    _install_result_verifier(
        monkeypatch,
        json.loads(failure_raw),
    )
    with pytest.raises(OutputConsistencyError, match="digest differs"):
        controller.record_native_failure((failure_path, "0" * 64))
    assert journal.history()[-1]["state"] == "reserved_by_render_intent"
    controller.record_native_failure((failure_path, failure_sha))
    planned: list[bool] = []
    monkeypatch.setattr(controller, "_environment_current", lambda: None)

    def prepare_plan(path: Path, *, retry: bool) -> Path:
        planned.append(retry)
        return path

    monkeypatch.setattr(controller, "prepare_operator_plan", prepare_plan)
    monkeypatch.setattr(
        native, "next_native_operation", lambda *_args, **_kwargs: (6, EMPTY_HEAD)
    )
    monkeypatch.setattr(
        native,
        "verified_render_failure",
        lambda _context: (failure_path, "0" * 64, {}),
    )

    with pytest.raises(OutputConsistencyError, match="ingested before retry"):
        controller.prepare_render_retry_plan(tmp_path / "retry-plan.json")
    assert planned == []

    monkeypatch.setattr(
        native,
        "verified_render_failure",
        lambda _context: (failure_path, failure_sha, {}),
    )
    plan = tmp_path / "retry-plan.json"
    assert controller.prepare_render_retry_plan(plan) == plan
    assert planned == [True]

    uncertain_ctx = context(package="d" * 64)
    uncertain_journal = OutputAttemptJournal(tmp_path / "uncertain", uncertain_ctx)
    uncertain_row = reserve(uncertain_journal, commit(uncertain_journal, uncertain_ctx))
    uncertain_journal.transition(
        uncertain_ctx,
        "uncertain",
        expected_head=uncertain_row["entrySha256"],
    )
    uncertain_controller = _controller(uncertain_journal, uncertain_ctx)
    monkeypatch.setattr(uncertain_controller, "_environment_current", lambda: None)

    def reject_retry_plan(*_args: Any, **_kwargs: Any) -> Path:
        pytest.fail("uncertain attempt must not produce a retry plan")

    monkeypatch.setattr(
        uncertain_controller, "prepare_operator_plan", reject_retry_plan
    )
    with pytest.raises(OutputConsistencyError, match="ingested before retry"):
        uncertain_controller.prepare_render_retry_plan(tmp_path / "uncertain-plan.json")


def test_retry_request_creates_no_native_request_until_failure_is_ingested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = context()
    journal = OutputAttemptJournal(tmp_path / "private", ctx)
    controller = _controller(journal, ctx)
    reserved = reserve(journal, commit(journal, ctx))
    approval_path = tmp_path / "retry-approval.json"
    approval_path.write_bytes(
        _canonical({"actionPlan": list(native.RETRY_ACTION_PLAN)})
    )
    called: list[str] = []

    def input_binding() -> tuple[bytes, Path]:
        return b"binding", tmp_path / "binding.json"

    def prepare_request(action: str, *_args: Any, **_kwargs: Any) -> Path:
        called.append(action)
        return tmp_path / "retry-request.json"

    def publish_handoff(*_args: Any) -> None:
        called.append("handoff")

    monkeypatch.setattr(controller, "_input_binding", input_binding)
    monkeypatch.setattr(controller, "prepare_native_request", prepare_request)
    monkeypatch.setattr(controller, "_publish_native_operator_handoff", publish_handoff)

    with pytest.raises(
        OutputConsistencyError, match="confirmed render failure required"
    ):
        controller.prepare_render_retry_request(approval_path)
    assert called == []
    assert reserved["state"] == "reserved_by_render_intent"

    _record_failed_render(
        controller,
        reserved,
        monkeypatch,
        tmp_path / "failed-poll.json",
    )
    request = controller.prepare_render_retry_request(approval_path)
    assert request == tmp_path / "retry-request.json"
    assert called == ["retry_capture", "handoff"]
