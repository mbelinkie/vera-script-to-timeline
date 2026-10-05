from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_issue144_omission_generation import setup
from vera_timeline_agent.roundtrip_build import ProofBuildError, load_operator_json


def test_validator_fault_before_service_call_can_resume_without_second_synthesis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import roundtrip_narration as narration

    session, _boundary, provider, _service, accepted = setup(tmp_path)
    key = accepted["decisionKey"]
    original_pointer = session.pointer.read_bytes()
    actual = subprocess.run

    def failed_validator(args: Any, **kwargs: Any) -> Any:
        if len(args) > 1 and args[1] == str(narration.VALIDATOR):
            raise subprocess.TimeoutExpired(args, 120)
        return actual(args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(subprocess, "run", failed_validator)
        with pytest.raises(subprocess.TimeoutExpired):
            session.run("generate-omission", decision_key=key)
    assert not provider.requests
    assert (session.root / "decisions" / key / "generation-inputs.json").exists()
    assert not list((session.root / "generation-calls").glob("*/intent.json"))
    assert session.run("generate-omission", decision_key=key)["status"] == "finalized"
    assert len(provider.requests) == 1
    assert session.pointer.read_bytes() == original_pointer


def test_uncertain_request_is_shared_across_byte_different_decisions(
    tmp_path: Path,
) -> None:
    session, _boundary, provider, _service, accepted = setup(tmp_path)
    provider.fail = True
    with pytest.raises(ProofBuildError):
        session.run("generate-omission", decision_key=accepted["decisionKey"])
    assert len(provider.requests) == 1
    path = session.root / "omission-decisions.json"
    choices = load_operator_json(path)
    path.write_text(json.dumps(choices, indent=2))
    other = session.run("decide-omission")
    assert other["decisionKey"] != accepted["decisionKey"]
    provider.fail = False
    with pytest.raises(ProofBuildError, match="synthesis cache is missing"):
        session.run("generate-omission", decision_key=other["decisionKey"])
    assert len(provider.requests) == 1
    intents = list((session.root / "generation-calls").glob("*/intent.json"))
    assert len(intents) == 1


def test_normalization_failure_resumes_from_synthesis_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, _boundary, provider, service, accepted = setup(tmp_path)
    key = accepted["decisionKey"]
    actual_normalize = service.normalizer.normalize_pcm
    calls = 0

    def fail_normalization(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("synthetic normalization failure")
        return actual_normalize(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(service.normalizer, "normalize_pcm", fail_normalization)
        with pytest.raises(ProofBuildError):
            session.run("generate-omission", decision_key=key)
    assert len(provider.requests) == 1
    assert session.run("generate-omission", decision_key=key)["status"] == "finalized"
    assert len(provider.requests) == 1
