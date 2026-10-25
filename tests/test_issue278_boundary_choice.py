"""Synthetic #278 Python/Node seam; no native qualification or provider calls."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_proof_v2 as proof
from vera_timeline_agent.qualification_output_controller_v2 import _ReceiptVault
from vera_timeline_agent.qualification_output_records_v2 import (
    OutputConsistencyError,
    _canonical,
)
from vera_timeline_agent.roundtrip_v2_records import ROOT

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def anchored_case() -> dict[str, Any]:
    node = shutil.which("node")
    assert node is not None
    result = subprocess.run(
        [node, str(ROOT / "packages/contracts/test/issue-278-case.ts")],
        capture_output=True,
        check=True,
        text=True,
        timeout=120,
    )
    value: dict[str, Any] = json.loads(result.stdout)
    return value


def session_for(root: Path, case: dict[str, Any], journal: Any | None = None) -> Any:
    """Double native/session currentness only; use the real CLI, claims and seals."""
    root.mkdir(mode=0o700)
    host: Any = object.__new__(proof.QualificationOutputProofV2)
    host.root = root
    host.session_pin = {"sha256": "1" * 64}
    host._current = lambda: None
    host._evidence = lambda: copy.deepcopy(case["evidence"])
    if journal is None:
        directory = root / "native-journal"
        directory.mkdir(mode=0o700)
        journal = SimpleNamespace(
            directory=directory, history=lambda: [], _lock=nullcontext
        )
    host.baseline = SimpleNamespace(
        context={"caseId": "C"},
        journal=journal,
        vault=_ReceiptVault(root / "vault"),
        blobs={
            "executionDocumentSha256": _canonical(case["document"]),
            "executionDependenciesSha256": _canonical(case["dependencies"]),
        },
    )
    host.edited = SimpleNamespace(journal=journal)
    return host


def decision_for(host: Any, *, choice: bool, outcome: str = "accept") -> dict[str, Any]:
    inference = host.infer()
    assert inference["caseKinds"] == ["C"]
    assert inference["omission"]["tokenIds"]
    conflicts = inference["boundaryConflicts"]
    assert len(conflicts) == 1
    assert conflicts[0]["choices"]
    # The TS decision domain hashes pretty JSON with a trailing newline.
    decision = {
        "schemaVersion": "qualification-output-decision/v1",
        "proposalHash": inference["inferenceHash"],
        "historyHash": "sha256:" + hashlib.sha256(b"[]\n").hexdigest(),
        "outcome": outcome,
    }
    if choice:
        decision["boundaryChoice"] = conflicts[0]["choices"][0]
    return decision


def assert_no_revision(host: Any, original: dict[str, bytes]) -> None:
    assert host.baseline.blobs == original
    assert not (host.root / "regeneration").exists()
    assert not (host.root / "revision-document.json").exists()
    assert not (host.root / "revision-dependencies.json").exists()


def test_undecided_and_rejected_conflict_cannot_start_synthesis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, anchored_case: dict[str, Any]
) -> None:
    monkeypatch.setattr(proof, "campaign_ledger", lambda _: None)
    service = SimpleNamespace(
        synthesize=lambda *_args, **_kwargs: pytest.fail("unexpected synthesis")
    )
    host = session_for(tmp_path / "undecided", anchored_case)
    original = copy.deepcopy(host.baseline.blobs)
    with pytest.raises(OutputConsistencyError, match=r"boundary|choice|conflict"):
        host.decide_inference(decision_for(host, choice=False))
    assert not (host.root / "inference-decision.json").exists()
    assert not (host.root / "stage.json").exists()
    with pytest.raises(FileNotFoundError):
        host.regenerate_row(service=service, confirm_provider_call=True)
    assert_no_revision(host, original)

    rejected = session_for(tmp_path / "rejected", anchored_case)
    original = copy.deepcopy(rejected.baseline.blobs)
    stage = rejected.decide_inference(
        decision_for(rejected, choice=False, outcome="reject")
    )
    assert stage["document"] == anchored_case["document"]
    assert stage["dependencies"] == anchored_case["dependencies"]
    assert stage["regeneration"] is None
    with pytest.raises(OutputConsistencyError, match="rejected or is undecided"):
        rejected.regenerate_row(service=service, confirm_provider_call=True)
    assert_no_revision(rejected, original)


def test_choice_is_sealed_recomputed_and_single_use_on_native_chain(
    tmp_path: Path, anchored_case: dict[str, Any]
) -> None:
    host = session_for(tmp_path / "accepted", anchored_case)
    decision = decision_for(host, choice=True)
    original = copy.deepcopy(host.baseline.blobs)
    stage = host.decide_inference(decision)
    assert stage["outcome"] == "accept"
    assert stage["regeneration"] is not None
    assert host._accepted_inference() == decision
    row = next(
        block
        for block in stage["document"]["activeDraft"]["blocks"]
        if block["id"] == decision["boundaryChoice"]["blockId"]
    )
    removed = stage["inference"]["omission"]["tokenIds"]
    assert all(token["id"] not in removed for token in row["tokens"])
    assert decision["boundaryChoice"]["tokenId"] in {
        token["id"] for token in row["tokens"]
    }
    with pytest.raises(OutputConsistencyError, match="already decided"):
        host.decide_inference(decision)
    replay = session_for(tmp_path / "replayed", anchored_case, host.baseline.journal)
    with pytest.raises(OutputConsistencyError, match="already decided"):
        replay.decide_inference(decision)
    assert not (replay.root / "stage.json").exists()
    assert not (replay.root / "inference-decision.json").exists()
    assert_no_revision(host, original)


@pytest.mark.parametrize("changed", ["removed", "unknown", "sequence", "inference"])
def test_invalid_choice_refuses_before_retaining_accepted_state(
    tmp_path: Path, anchored_case: dict[str, Any], changed: str
) -> None:
    host = session_for(tmp_path / changed, anchored_case)
    decision = decision_for(host, choice=True)
    original = copy.deepcopy(host.baseline.blobs)
    command = decision["boundaryChoice"]
    if changed == "removed":
        command["tokenId"] = anchored_case["evidence"]["cases"][0]["omissionSupport"][
            "selectedTokenId"
        ]
    elif changed == "unknown":
        command["tokenId"] = "00000000-0000-4000-8000-999999999999"
    elif changed == "sequence":
        command["expectedSequenceVersion"] += 1
    else:
        decision["proposalHash"] = "sha256:" + "0" * 64
    with pytest.raises(OutputConsistencyError):
        host.decide_inference(decision)
    assert not (host.root / "inference-decision.json").exists()
    assert not (host.root / "stage.json").exists()
    assert not (host.baseline.journal.directory / "proof-decisions").exists()
    assert_no_revision(host, original)


@pytest.mark.parametrize("changed", ["decision", "stage", "evidence", "document"])
def test_retained_choice_stage_and_original_inputs_cannot_drift(
    tmp_path: Path, anchored_case: dict[str, Any], changed: str
) -> None:
    case = copy.deepcopy(anchored_case)
    host = session_for(tmp_path / changed, case)
    decision = decision_for(host, choice=True)
    stage = host.decide_inference(decision)
    if changed in {"decision", "stage"}:
        name = "inference-decision" if changed == "decision" else "stage"
        path = host.root / f"{name}.json"
        path.chmod(0o600)
        value = copy.deepcopy(decision if changed == "decision" else stage)
        if changed == "decision":
            value["boundaryChoice"]["affinity"] = "invalid"
        else:
            value["document"]["title"] = "altered stage"
        path.write_bytes(_canonical(value))
    elif changed == "evidence":
        case["evidence"]["cases"][0]["omissionSupport"]["audioSha256"] = "0" * 64
    else:
        document = copy.deepcopy(case["document"])
        document["activeDraft"]["blocks"][0]["version"] += 1
        host.baseline.blobs["executionDocumentSha256"] = _canonical(document)
    with pytest.raises(OutputConsistencyError):
        host._accepted_inference()
    assert not (host.root / "regeneration").exists()
    assert not (host.root / "revision-document.json").exists()
