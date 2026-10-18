"""New bridge trust-boundary checks; synthetic seals never qualify native work."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_issue214_comparison import rendered, terminal
from test_issue214_prediction import case
from vera_timeline_agent import qualification_output_proof_v2 as proof
from vera_timeline_agent.qualification_output_controller_v2 import (
    QualificationOutputController,
)
from vera_timeline_agent.qualification_output_records_v2 import (
    OutputConsistencyError,
    _canonical,
    _hash,
)


def test_pin_rejects_changed_bytes_symlinks_and_aliases(tmp_path: Path) -> None:
    path = tmp_path / "original.json"
    path.write_bytes(b"{}")
    pin = proof._pin(path)
    assert proof._pinned(pin) == b"{}"
    path.write_bytes(b"[]")
    with pytest.raises(OutputConsistencyError, match="changed"):
        proof._pinned(pin)
    path.write_bytes(b"{}")
    alias = tmp_path / "alias.json"
    os.link(path, alias)
    with pytest.raises(OutputConsistencyError, match="identity"):
        proof._pinned(pin)
    alias.unlink()
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(OutputConsistencyError, match="symlink"):
        proof._pinned({"path": str(link), "sha256": pin["sha256"]})


@pytest.mark.parametrize(
    "schema",
    [
        "issue-192-v2-revised-preflight/v1",
        "issue-189-v2-omission-evidence/v1",
        "qualification-output-revised-preflight/v1",
    ],
)
def test_partial_or_legacy_preflight_cannot_reach_a_session(
    tmp_path: Path, schema: str
) -> None:
    path = tmp_path / "preflight.json"
    path.write_bytes(
        _canonical(
            {"schemaVersion": schema, "status": "prepared", "verifier": "accept"}
        )
    )
    with pytest.raises(OutputConsistencyError, match="closed"):
        proof.verify_revised_preflight_v2(path, _hash(path.read_bytes()))


def controller_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, Any]:
    """Only native I/O is doubled; #214 authenticates/recomputes every record."""
    c = case()
    sealed = terminal(c, rendered(c))
    artifacts, vault = tmp_path / "artifacts", tmp_path / "receipts"
    artifacts.mkdir()
    vault.mkdir()
    for raw in (
        sealed.output.commitment,
        sealed.output.prediction,
        sealed.output.reservation,
        sealed.output.decode_record,
        sealed.output.decoded_samples,
        sealed.comparison,
    ):
        (artifacts / _hash(raw)).write_bytes(raw)
    for raw in (*c.trust.seals, sealed.output.post_geometry):
        (vault / _hash(raw)).write_bytes(raw)
    controller: Any = object.__new__(QualificationOutputController)
    controller.context = c.binding["context"]
    controller.journal = SimpleNamespace(
        artifacts=artifacts, history=lambda: copy.deepcopy(sealed.ledger)
    )
    controller.vault = SimpleNamespace(root=vault)
    controller.trust = c.trust
    monkeypatch.setattr(controller, "_environment_current", lambda: None)
    monkeypatch.setattr(controller, "_native_result", lambda _: None)
    monkeypatch.setattr(controller, "_render_sequences", lambda: (2, 3, 4, 5, 6))
    monkeypatch.setattr(controller, "_pre_capture_inputs", lambda **_: c.inputs)
    monkeypatch.setattr(controller, "_render_lineage", lambda: sealed.output.lineage)
    return controller, sealed


def test_terminal_loader_recomputes_complete_chain_without_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, sealed = controller_fixture(tmp_path, monkeypatch)
    reopened = proof.load_terminal_output(controller)
    assert reopened.comparison == sealed.comparison
    assert reopened.ledger == sealed.ledger
    assert reopened.output.decoded_samples == sealed.output.decoded_samples


@pytest.mark.parametrize(
    "attack", ["missing_terminal", "uncertain", "changed_decode", "changed_comparison"]
)
def test_partial_uncertain_or_changed_terminal_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attack: str
) -> None:
    controller, sealed = controller_fixture(tmp_path, monkeypatch)
    if attack == "missing_terminal":
        controller.journal.history = lambda: sealed.ledger[:-1]
    elif attack == "uncertain":
        rows = copy.deepcopy(sealed.ledger)
        rows[-1]["state"] = "uncertain"
        controller.journal.history = lambda: rows
    elif attack == "changed_decode":
        path = controller.journal.artifacts / _hash(sealed.output.decoded_samples)
        raw = bytearray(path.read_bytes())
        raw[0] ^= 1
        path.write_bytes(raw)
    else:
        path = controller.journal.artifacts / _hash(sealed.comparison)
        path.write_bytes(path.read_bytes().replace(b"unverified", b"verified!!"))
    with pytest.raises(OutputConsistencyError):
        proof.load_terminal_output(controller)


def test_decision_is_single_use_across_proof_directories(tmp_path: Path) -> None:
    from test_issue209_controller import context
    from vera_timeline_agent.qualification_output_controller_v2 import (
        OutputAttemptJournal,
    )

    journal = OutputAttemptJournal(tmp_path / "host", context())
    one: Any = object.__new__(proof.QualificationOutputProofV2)
    two: Any = object.__new__(proof.QualificationOutputProofV2)
    one.baseline = SimpleNamespace(journal=journal)
    two.baseline = SimpleNamespace(journal=journal)
    one.root, two.root = tmp_path / "one", tmp_path / "two"
    identity = "sha256:" + _hash(b"same actual inference")
    decision = b"explicit accepted decision"
    one._claim_decision("inference", identity, decision)
    two._check_decision_claim("inference", identity, decision)
    with pytest.raises(OutputConsistencyError, match="already decided"):
        two._claim_decision("inference", identity, decision)
    with pytest.raises(OutputConsistencyError, match="differs"):
        two._check_decision_claim("inference", identity, b"changed decision")
