"""Closed fake-host orchestration tests: no real Resolve or approvals used."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from vera_timeline_agent import resolve_test_bench_output as output
from vera_timeline_agent import resolve_test_queue as queue


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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
        def __init__(self):
            self.context = context

        def prepare_operator_plan(self, path):
            steps.append("plan")
            path.write_text("reviewed proposal")

        def prepare_next_native_request(self, approval):
            assert approval.exists()
            steps.append("prepared")
            request.write_text("pinned one-use native request")

        def finalize_output(self, path, sha):
            steps.append("finalize")

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
        lambda path, sha: {"action": "capture_post", "sequence": 0},
    )

    def approval(*args, **kwargs):
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

    def dispatch(step, source, digest, installed, **options):
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
    assert calls == []


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
