"""Closed fake-host orchestration tests: no real Resolve or approvals used."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, NoReturn

import pytest
from vera_timeline_agent import resolve_test_bench_output as output
from vera_timeline_agent import resolve_test_queue as queue


def _fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[str, Any], list[str], Path, Path]:
    from vera_timeline_agent import qualification_output_controller_v2 as host
    from vera_timeline_agent import qualification_output_native_v2 as native

    context = {
        "target": {
            "projectUid": "synthetic-project",
            "timelineUid": "synthetic-timeline",
        }
    }
    steps: list[str] = []
    native_dir = tmp_path / "native" / "00000000"
    native_dir.mkdir(parents=True)
    request = native_dir / "request.json"
    result = native_dir / "result.json"

    class Host:
        def __init__(self) -> None:
            self.context = context

        def prepare_operator_plan(self, path: Path) -> None:
            steps.append("plan")
            path.write_text("reviewed proposal")

        def prepare_next_native_request(self, approval: Path) -> None:
            assert approval.exists()
            steps.append("prepared")
            request.write_text("pinned one-use native request")

        def finalize_output(self, path: Path, sha: str) -> None:
            steps.append("finalize")

        def ingest_native_result(self, path: Path, sha: str) -> dict[str, Any]:
            steps.append("ingested")
            return {
                "sequence": 0,
                "action": "capture_post",
                "status": "complete",
                "resultSha256": sha,
                "hostStage": "post_capture_ready_to_finalize",
            }

    monkeypatch.setattr(output, "_session", lambda *args: Host())
    monkeypatch.setattr(
        native, "action_plan_for_context", lambda context: ("capture_post",)
    )
    monkeypatch.setattr(
        native,
        "native_request_paths",
        lambda context, seq: (
            result,
            native_dir / "authority",
            native_dir / "intent",
            request,
        ),
    )
    monkeypatch.setattr(
        native,
        "verify_native_result",
        lambda path, sha: {
            "action": "capture_post",
            "sequence": 0,
            "status": "complete",
        },
    )

    def approval(*args: Any, **kwargs: Any) -> None:
        steps.append("approval")
        args[1].write_text("attributed approval")

    monkeypatch.setattr(host, "issue_operator_approval", approval)
    root = tmp_path / "run"
    kwargs = {
        "session_path": tmp_path / "host-session.json",
        "session_sha256": "a" * 64,
        "installed": tmp_path / "installed",
        "consent_reference": "Producer issue #473",
        "consent_instruction": (
            "One-start unattended synthetic Test Bench; no unrelated projects"
        ),
        "minimum_free_bytes": 1,
    }
    return root, kwargs, steps, request, result


def test_driver_prepares_and_dispatches_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import resolve_test_bench_carrier as carrier

    root, kwargs, calls, request, _ = _fixture(tmp_path, monkeypatch)

    def dispatch(
        step: Path, source: Path, digest: str, installed: Path, **options: Any
    ) -> dict[str, str]:
        calls.append("launch")
        assert source == request
        assert digest == hashlib.sha256(request.read_bytes()).hexdigest()
        step.mkdir()
        (step / "intent.json").write_text("durable synthetic intent")
        return {"state": "dispatched_once"}

    monkeypatch.setattr(carrier, "start", dispatch)
    assert output.tick(root, **kwargs) == {
        "state": "running",
        "action": "capture_post",
        "sequence": 0,
    }
    assert calls == ["plan", "approval", "prepared", "launch"]
    monkeypatch.setattr(carrier, "status", lambda step: {"state": "unknown"})
    with pytest.raises(queue.QueueError, match="never retry"):
        output.tick(root, **kwargs)
    assert calls == ["plan", "approval", "prepared", "launch"]


def test_existing_complete_native_only_after_independent_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import resolve_test_bench_carrier as carrier

    root, kwargs, calls, _, result = _fixture(tmp_path, monkeypatch)
    step = root / "native-00"
    root.mkdir(mode=0o700)
    step.mkdir(parents=True, mode=0o700)
    (step / "intent.json").write_text("durable synthetic intent")
    result.write_text("authenticated by fake host fixture")
    monkeypatch.setattr(
        carrier,
        "status",
        lambda step: {
            "state": "native_result_verified",
            "result": {
                "path": str(result),
                "sha256": hashlib.sha256(result.read_bytes()).hexdigest(),
            },
        },
    )
    monkeypatch.setattr(output, "_terminal", lambda controller: True)
    verified = output.tick(root, **kwargs)
    assert verified["state"] == "terminal_native_verified"
    assert (
        verified["capture"]["sha256"] == hashlib.sha256(result.read_bytes()).hexdigest()
    )
    assert calls == ["ingested"]


def test_cannot_adopt_unowned_native_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, kwargs, calls, _, result = _fixture(tmp_path, monkeypatch)
    result.write_bytes(b"unowned prior result")
    with pytest.raises(queue.QueueError, match="no historical adoption"):
        output.tick(root, **kwargs)
    assert calls == []


def test_cannot_adopt_started_external_native_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, kwargs, calls, request, _ = _fixture(tmp_path, monkeypatch)
    root.mkdir(mode=0o700)
    (root / "operator-plan-00.json").write_text("proposal")
    (root / "operator-approval-00.json").write_text("approval")
    request.write_text("native request")
    (request.parent / "native-start.json").write_text("unknown effect")
    with pytest.raises(queue.QueueError, match="already started"):
        output.tick(root, **kwargs)
    assert calls == []


def test_missing_actual_producer_instruction_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, kwargs, calls, _, _ = _fixture(tmp_path, monkeypatch)
    kwargs["consent_instruction"] = " "
    with pytest.raises(queue.QueueError, match="Producer instruction"):
        output.tick(root, **kwargs)
    assert calls == []


def test_finalize_crash_is_inspect_only_and_cannot_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import resolve_test_bench_carrier as carrier

    root, kwargs, calls, _, native_result = _fixture(tmp_path, monkeypatch)
    root.mkdir(mode=0o700)
    step = root / "native-00"
    step.mkdir(mode=0o700)
    (step / "intent.json").write_text("one-use fake host intent")
    native_result.write_text("synthetic authenticated fixture")
    monkeypatch.setattr(
        carrier,
        "status",
        lambda path: {
            "state": "native_result_verified",
            "result": {
                "path": str(native_result),
                "sha256": hashlib.sha256(native_result.read_bytes()).hexdigest(),
            },
        },
    )
    monkeypatch.setattr(output, "_terminal", lambda controller: False)

    def crash(_self: Any, _path: Path, _sha: str) -> NoReturn:
        calls.append("finalizer-effect")
        raise RuntimeError("finalizer died after state mutation")

    original = output._session

    def session(*args: Any) -> Any:
        result = original(*args)
        result.finalize_output = lambda path, sha: crash(result, path, sha)
        return result

    monkeypatch.setattr(output, "_session", session)
    with pytest.raises(RuntimeError, match="finalizer died"):
        output.tick(root, **kwargs)
    assert (root / "finalize-intent.json").exists()
    with pytest.raises(queue.QueueError, match="never replay"):
        output.tick(root, **kwargs)
    assert calls == ["ingested", "finalizer-effect"]


def test_deadline_expiration_after_request_preparation_never_dispatches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import qualification_output_controller_v2 as host
    from vera_timeline_agent import resolve_test_bench_carrier as carrier

    root, kwargs, calls, request, _ = _fixture(tmp_path, monkeypatch)
    clock = [100.0]
    monkeypatch.setattr(
        "vera_timeline_agent.resolve_test_bench_output.time.time",
        lambda: clock[0],
    )

    def expire_after_approval(*args: Any, **kwargs: Any) -> None:
        args[1].write_text("test-only attributed approval")
        calls.append("approval")
        clock[0] = 105.0

    monkeypatch.setattr(host, "issue_operator_approval", expire_after_approval)
    monkeypatch.setattr(
        carrier,
        "start",
        lambda *args, **kwargs: pytest.fail("expired host must not dispatch"),
    )
    with pytest.raises(queue.QueueError, match="before native dispatch"):
        output.tick(root, **kwargs, hard_deadline=104)
    assert calls == ["plan", "approval", "prepared"]
    assert request.exists()
