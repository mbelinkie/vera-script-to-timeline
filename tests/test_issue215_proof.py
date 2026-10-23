"""New bridge trust-boundary checks; synthetic seals never qualify native work."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_issue214_comparison import rendered, terminal
from test_issue214_prediction import case, change_items
from vera_timeline_agent import qualification_output_controller_v2 as controller_module
from vera_timeline_agent import qualification_output_proof_v2 as proof
from vera_timeline_agent import qualification_output_v2 as output
from vera_timeline_agent.qualification_output_controller_v2 import (
    QualificationOutputController,
)
from vera_timeline_agent.qualification_output_records_v2 import (
    LANE,
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


def test_raw_provider_handoff_refuses_before_proof_or_provider_work() -> None:
    session: Any = object.__new__(proof.QualificationOutputProofV2)
    with pytest.raises(OutputConsistencyError, match="manual replacement handoff"):
        session.proposal(handoff={"schemaVersion": "issue-189-v2-row-handoff/v1"})


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
        sealed.output.lineage,
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
    monkeypatch.setattr(
        controller,
        "_render_lineage",
        lambda: pytest.fail("terminal loading must not rebuild a live reservation"),
    )
    return controller, sealed


def test_output_session_checks_admission_once_after_reconstruction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = case()
    session_path = tmp_path / "session.json"
    session = {
        "schemaVersion": "qualification-output-session/v1",
        "lane": LANE,
        "profile": "synthetic-test",
        "admissionPath": str(tmp_path / "admission.json"),
        "admissionSha256": "admission-pin",
        "releaseRoot": str(tmp_path),
        "context": c.binding["context"],
        "hostJournalRoot": str(controller_module.HOST_STATE_ROOT),
    }
    raw = _canonical(session)
    session_path.write_bytes(raw)
    checks = 0

    class Admission:
        def assert_current(self) -> None:
            nonlocal checks
            checks += 1

    class Controller:
        def __init__(
            self, _root: Path, *, admission: Admission, **_kwargs: Any
        ) -> None:
            admission.assert_current()
            self.context = c.binding["context"]

    monkeypatch.setattr(controller_module, "QualificationOutputController", Controller)
    from vera_timeline_agent import qualification_output_package_v2 as package

    monkeypatch.setattr(
        package, "_load_qualification_package_v2", lambda *_args: Admission()
    )
    monkeypatch.setattr(
        package,
        "load_qualification_package_v2",
        lambda *_args: pytest.fail(
            "session loading must defer to the controller check"
        ),
    )
    loaded = controller_module.load_output_session(session_path, _hash(raw))
    assert loaded.context == c.binding["context"]
    assert checks == 1


def test_terminal_loader_recomputes_complete_chain_without_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, sealed = controller_fixture(tmp_path, monkeypatch)
    currentness_checks = 0

    def environment_current() -> None:
        nonlocal currentness_checks
        currentness_checks += 1

    monkeypatch.setattr(controller, "_environment_current", environment_current)
    reopened = proof.load_terminal_output(controller)
    assert reopened.comparison == sealed.comparison
    assert reopened.ledger == sealed.ledger
    assert reopened.output.decoded_samples == sealed.output.decoded_samples
    assert currentness_checks == 2


def test_observation_transports_original_phase_input_binding_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pristine = case()
    edited = case(phase="edited")
    controllers = {
        "pristine": SimpleNamespace(inputs=pristine.inputs),
        "edited": SimpleNamespace(inputs=edited.inputs),
    }
    outputs = {
        "pristine": SimpleNamespace(
            output=SimpleNamespace(
                inputs=pristine.inputs, prediction=b"\0" * 16, decoded_samples=b"\0" * 8
            ),
            comparison=b"pristine comparison",
        ),
        "edited": SimpleNamespace(
            output=SimpleNamespace(
                inputs=edited.inputs, prediction=b"\0" * 16, decoded_samples=b"\0" * 8
            ),
            comparison=b"edited comparison",
        ),
    }
    monkeypatch.setattr(
        proof,
        "_load_terminal_output",
        lambda controller: outputs[
            "pristine" if controller is controllers["pristine"] else "edited"
        ],
    )
    monkeypatch.setattr(
        proof,
        "load_terminal_output",
        lambda _controller: pytest.fail(
            "evidence must use its pair-wide currentness boundary"
        ),
    )
    session: Any = object.__new__(proof.QualificationOutputProofV2)
    session.baseline = controllers["pristine"]
    session.edited = controllers["edited"]
    currentness_checks = 0

    def current() -> None:
        nonlocal currentness_checks
        currentness_checks += 1

    session._current = current
    requests: list[dict[str, Any]] = []

    def pure(request: dict[str, Any]) -> dict[str, str]:
        session._current()
        requests.append(request)
        if request["mode"] == "baseline":
            result = {"documentHash": "document", "dependenciesHash": "dependencies"}
        else:
            result = {}
        session._current()
        return result

    session._pure = pure
    evidence = session.evidence("A")
    observation = evidence["cases"][0]
    assert (
        observation["pristineInputBindingJson"]
        == pristine.inputs.input_binding.decode()
    )
    assert observation["editedInputBindingJson"] == edited.inputs.input_binding.decode()
    assert "sourceEntries" in observation["pristineInputBindingJson"]
    assert "nativeSources" in observation["pristineInputBindingJson"]
    assert requests[-1]["evidence"] == evidence
    assert currentness_checks == 6


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
    one.baseline = SimpleNamespace(journal=journal, context={"caseId": "C"})
    two.baseline = SimpleNamespace(journal=journal, context={"caseId": "C"})
    one.edited = two.edited = SimpleNamespace(journal=journal)
    one.root, two.root = tmp_path / "one", tmp_path / "two"
    identity = "sha256:" + _hash(b"same actual inference")
    decision = b"explicit accepted decision"
    one._claim_decision("inference", identity, decision)
    two._check_decision_claim("inference", identity, decision)
    with pytest.raises(OutputConsistencyError, match="already decided"):
        two._claim_decision("inference", identity, decision)
    # Reissuing C's source review changes its inference hash, not its native pair.
    with pytest.raises(OutputConsistencyError, match="already decided"):
        two._claim_decision("inference", "sha256:" + _hash(b"new review"), decision)
    with pytest.raises(OutputConsistencyError, match="differs"):
        two._check_decision_claim("inference", identity, b"changed decision")


def test_pair_trust_keeps_distinct_phase_vaults_without_receipt_fallback() -> None:
    from test_issue214_records import SealedTrust

    pristine, edited = SealedTrust(), SealedTrust()
    left, right = {"phase": "pristine"}, {"phase": "edited"}
    baseline_controller: Any = SimpleNamespace(context=left, trust=pristine)
    edited_controller: Any = SimpleNamespace(context=right, trust=edited)
    trust = proof._PairTrust(baseline_controller, edited_controller)
    expected = {"context": right, "value": "actual edited payload"}
    receipt = edited.seal("output_residual_comparison", expected)
    trust.authenticate("output_residual_comparison", receipt, expected)
    assert pristine.calls == []
    assert edited.calls == ["output_residual_comparison"]
    geometry = {"geometry": {"context": right}, "inputBinding": {"context": right}}
    geometry_receipt = edited.seal("output_geometry_snapshot", geometry)
    trust.authenticate("output_geometry_snapshot", geometry_receipt, geometry)
    assert pristine.calls == []
    with pytest.raises(OutputConsistencyError, match="outside"):
        trust.authenticate(
            "output_residual_comparison", receipt, {"context": {"phase": "rebuild"}}
        )
    with pytest.raises(OutputConsistencyError, match="authentication"):
        trust.authenticate("output_residual_comparison", receipt, {"context": left})


def test_pair_comparison_authenticates_separate_phase_receipts() -> None:
    pristine, edited = case(), case(phase="edited")
    item = json.loads(edited.inputs.geometry)["geometry"]["items"][0]
    change_items(edited, [{**item, "recordDuration": 2, "sourceDuration": 2}])
    left, right = (
        terminal(pristine, rendered(pristine)),
        terminal(edited, rendered(edited)),
    )
    baseline_controller: Any = SimpleNamespace(
        context=pristine.binding["context"], trust=pristine.trust
    )
    edited_controller: Any = SimpleNamespace(
        context=edited.binding["context"], trust=edited.trust
    )
    result = output.compare_prediction_pair(
        left, right, trust=proof._PairTrust(baseline_controller, edited_controller)
    )
    assert result["geometryStability"] == result["controlStability"] == "not_claimed"


@pytest.mark.parametrize(
    "attack", [None, "target", "case", "invocation", "root", "missing"]
)
def test_reopened_rebuild_requires_its_original_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attack: str | None
) -> None:
    baseline = SimpleNamespace(
        context={"caseId": "A", "target": {"timelineUid": "original"}},
        journal=SimpleNamespace(directory=tmp_path / "journal"),
    )
    admission = tmp_path / "revised/admitted/admission.json"
    admission.parent.mkdir(parents=True)
    admission.write_bytes(b"admission")
    proof_pin = {"path": str(tmp_path / "proof.json"), "sha256": "1" * 64}
    owner = SimpleNamespace(baseline=baseline, session_pin=proof_pin)
    monkeypatch.setattr(proof, "QualificationOutputProofV2", lambda *_: owner)
    record = {"proofSession": proof_pin, "revisionLedger": {"sha256": "2" * 64}}
    target = {"timelineUid": "fresh"}
    reservation = baseline.journal.directory / "proof-rebuilds" / ("2" * 64 + ".json")
    reservation.parent.mkdir(parents=True)
    reservation.write_bytes(
        _canonical(
            {
                "proofSession": proof_pin,
                "preflightSha256": "3" * 64,
                "outputRoot": str(admission.parent.parent),
                "target": target,
                "caseId": "A",
                "invocationId": "first",
                "admission": proof._pin(admission),
            }
        )
    )
    if attack == "missing":
        reservation.unlink()
    if attack == "root":
        admission = tmp_path / "copied/admitted/admission.json"
        admission.parent.mkdir(parents=True)
        admission.write_bytes(b"admission")

    def verify() -> None:
        proof.verify_revised_rebuild_reservation_v2(
            record,
            "3" * 64,
            admission_path=admission,
            target={"timelineUid": "another"} if attack == "target" else target,
            case_id="B" if attack == "case" else "A",
            invocation_id="second" if attack == "invocation" else "first",
        )

    if attack is None:
        verify()
    else:
        with pytest.raises(OutputConsistencyError):
            verify()
