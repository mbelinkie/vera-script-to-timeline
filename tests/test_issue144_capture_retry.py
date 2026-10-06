"""Capture reservation regression only; not a native positive proof."""

from pathlib import Path
from typing import Any

import pytest
from test_issue144_prepared_build import _inputs
from vera_timeline_agent.roundtrip_build import ProofBuildError, _digest, _receipt_bytes
from vera_timeline_agent.roundtrip_proof import ProofSession


@pytest.mark.parametrize("malformed", [False, True])
def test_semantic_refusal_is_terminal_and_next_attempt_reads_fresh_nonce(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    malformed: bool,
) -> None:
    root = tmp_path / "proof"
    _inputs(root)
    session = ProofSession(root)
    identity = {
        "projectUid": "explicit-fake-project",
        "timelineUid": "explicit-fake-timeline",
        "occurrences": {},
    }
    # Isolate reservation/validation, not assembly or native qualification.
    monkeypatch.setattr(session, "_ready", lambda build: identity)
    session.build.manifest_path.parent.mkdir(parents=True)
    session.build.manifest_path.write_bytes(b"{}\n")
    (session.build.run_root / "native-identity.json").write_bytes(
        _receipt_bytes(identity)
    )
    requests: list[dict[str, Any]] = []

    def capture(request: dict[str, Any]) -> dict[str, Any]:
        requests.append(request)
        observation: Any = {"valid": len(requests) > 1}
        if malformed:
            observation = (
                []
                if len(requests) == 1
                else {
                    "projectUid": identity["projectUid"],
                    "timelineUid": identity["timelineUid"],
                    "evidenceLevel": "synthetic_injected",
                    "items": [],
                }
            )
        return {
            "schemaVersion": "issue-144-capture-response/v1",
            "nonce": request["nonce"],
            "requestHash": _digest(_receipt_bytes(request)),
            "observationA": observation,
            "observationB": observation,
        }

    def validate(observation: dict[str, Any]) -> None:
        if malformed:
            session._occurrence_identity(observation, identity, "synthetic_injected")
            return
        if not observation["valid"]:
            raise ProofBuildError("unknown occurrence facts")

    session.capture = capture
    with pytest.raises(ProofBuildError, match=r"unknown occurrence|capture target"):
        session._capture_files(
            session.build, "reservation-regression", "fixed-binding", validate=validate
        )
    refused = next((root / "captures").glob("*/*/refused.json"))
    retained = {p.name: p.read_bytes() for p in refused.parent.iterdir()}
    assert "response.json" in retained and "consumed.json" not in retained
    a, b = session._capture_files(
        session.build, "reservation-regression", "fixed-binding", validate=validate
    )
    assert a == b
    assert a == (
        {
            "projectUid": identity["projectUid"],
            "timelineUid": identity["timelineUid"],
            "evidenceLevel": "synthetic_injected",
            "items": [],
        }
        if malformed
        else {"valid": True}
    )
    assert len(requests) == 2 and requests[0]["nonce"] != requests[1]["nonce"]
    assert {p.name: p.read_bytes() for p in refused.parent.iterdir()} == retained
    assert len(list((root / "captures").glob("*/*/consumed.json"))) == 1
