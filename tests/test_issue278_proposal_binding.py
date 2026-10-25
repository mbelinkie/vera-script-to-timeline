"""The host rejects a competing choice before retaining revision acceptance."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_proof_v2 as proof
from vera_timeline_agent.qualification_output_records_v2 import (
    OutputConsistencyError,
    _canonical,
)


@pytest.mark.parametrize("changed", ["choice", "history", "handoff"])
def test_candidate_cannot_replace_sealed_choice_or_verified_handoff(
    tmp_path: Path, changed: str
) -> None:
    host: Any = object.__new__(proof.QualificationOutputProofV2)
    host.root = tmp_path
    decision = {
        "outcome": "accept",
        "boundaryChoice": {"tokenId": "sealed surviving word", "affinity": "before"},
    }
    handoff = {"request": {"decisionHash": "sealed choice"}}
    host._accepted_inference = lambda: copy.deepcopy(decision)
    host._stage = lambda: {"regeneration": {"decisionHash": "sealed choice"}}
    host._regenerated_handoff = lambda _: copy.deepcopy(handoff)
    host._pure = lambda _: pytest.fail("a competing sealed decision reached the bridge")
    host._claim_decision = lambda *_: pytest.fail("accepted revision was claimed")
    candidate: dict[str, Any] = {
        "inferenceDecision": copy.deepcopy(decision),
        "inferenceHistory": [],
        "request": {"handoff": copy.deepcopy(handoff)},
    }
    if changed == "choice":
        candidate["inferenceDecision"]["boundaryChoice"]["tokenId"] = "competing word"
    elif changed == "history":
        candidate["inferenceHistory"] = ["competing history"]
    else:
        candidate["request"]["handoff"]["request"]["decisionHash"] = "competing choice"
    (tmp_path / "proposal.json").write_bytes(_canonical(candidate))
    with pytest.raises(OutputConsistencyError):
        host.decide({"outcome": "accept"})
    for name in (
        "decision.json",
        "result.json",
        "revision-ledger.json",
        "revision-document.json",
        "revision-dependencies.json",
    ):
        assert not (tmp_path / name).exists()
