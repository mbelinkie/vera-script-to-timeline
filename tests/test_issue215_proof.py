"""New bridge trust-boundary checks; synthetic seals never qualify native work."""

from __future__ import annotations

import copy
import json
import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_issue214_comparison import rendered, shortened_pair, terminal
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
    _parse,
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case_value: Any | None = None
) -> tuple[Any, Any]:
    """Only native I/O is doubled; #214 authenticates/recomputes every record."""
    c = case() if case_value is None else case_value
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


def test_proof_pair_reuses_same_call_terminal_verifications(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pristine_case, edited_case = shortened_pair(source_start=1)
    pristine_root, edited_root = tmp_path / "pristine", tmp_path / "edited"
    pristine_root.mkdir()
    edited_root.mkdir()
    pristine_controller, pristine = controller_fixture(
        pristine_root, monkeypatch, pristine_case
    )
    edited_controller, edited = controller_fixture(
        edited_root, monkeypatch, edited_case
    )
    expected = output.compare_prediction_pair(
        pristine, edited, trust=pristine_case.trust
    )
    terminal_checks: list[output.TerminalOutput] = []
    terminal_comparison = output._terminal_comparison

    def count_terminal_checks(
        value: output.TerminalOutput, trust: Any
    ) -> dict[str, Any]:
        terminal_checks.append(value)
        return terminal_comparison(value, trust)

    monkeypatch.setattr(output, "_terminal_comparison", count_terminal_checks)
    session: Any = object.__new__(proof.QualificationOutputProofV2)
    session.baseline = pristine_controller
    session.edited = edited_controller
    session._current = lambda: None
    session._pure = lambda request: (
        {"documentHash": "document", "dependenciesHash": "dependencies"}
        if request["mode"] == "baseline"
        else {}
    )

    evidence = session.evidence("B")
    assert len(terminal_checks) == 2
    assert evidence["cases"][0]["pairJson"] == _canonical(expected).decode()

    terminal_checks.clear()
    assert (
        output.compare_prediction_pair(pristine, edited, trust=pristine_case.trust)
        == expected
    )
    assert len(terminal_checks) == 2

    terminal_checks.clear()
    with pytest.raises(OutputConsistencyError):
        output.compare_prediction_pair(
            replace(pristine, ledger=pristine.ledger[:-1]),
            edited,
            trust=pristine_case.trust,
        )
    assert len(terminal_checks) == 1


def test_accepted_revision_reuses_one_fresh_evidence_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pristine_case, edited_case = case(), case(phase="edited")
    pristine_root, edited_root = tmp_path / "pristine", tmp_path / "edited"
    pristine_root.mkdir()
    edited_root.mkdir()
    pristine_controller, pristine_sealed = controller_fixture(
        pristine_root, monkeypatch, pristine_case
    )
    edited_controller, _edited_sealed = controller_fixture(
        edited_root, monkeypatch, edited_case
    )
    host: Any = object.__new__(proof.QualificationOutputProofV2)
    host.root = tmp_path / "proof"
    host.root.mkdir()
    host.session_pin = {"sha256": "a" * 64}

    def authenticate(_kind: str, receipt: bytes, expected: dict[str, Any]) -> None:
        assert _parse(receipt)["payload"] == expected

    pristine_controller.vault.authenticate = authenticate
    host.baseline = pristine_controller
    host.edited = edited_controller
    host._current = lambda: None
    host._check_decision_claim = lambda *_args: None
    host._regenerated_handoff = lambda _stage: None

    terminal_comparisons: list[output.TerminalOutput] = []
    compare_terminal = output._terminal_comparison

    def count_terminal_comparison(
        value: output.TerminalOutput, trust: Any
    ) -> dict[str, Any]:
        terminal_comparisons.append(value)
        return compare_terminal(value, trust)

    monkeypatch.setattr(output, "_terminal_comparison", count_terminal_comparison)

    facts = {"documentHash": "document", "dependenciesHash": "dependencies"}
    requests: list[dict[str, Any]] = []
    inference_decision = {"outcome": "accept", "decision": "inference"}
    inference_raw = _canonical(inference_decision)
    stage = {"stage": "verified"}
    stage_raw = _canonical(stage)
    inference_payload = {
        "inferenceHash": "sha256:" + "b" * 64,
        "proofSessionSha256": host.session_pin["sha256"],
        "decisionSha256": _hash(inference_raw),
        "stageSha256": _hash(stage_raw),
    }
    candidate = {
        "proposalHash": "sha256:" + "c" * 64,
        "request": {"handoff": None},
        "revision": {"manifestJson": "manifest", "reportJson": "report"},
    }
    candidate_raw = _canonical(candidate)
    decision = {"decision": "accept"}
    decision_raw = _canonical(decision)
    document, dependencies = {"revised": True}, {"build": {"buildId": "new"}}
    result = {
        "outcome": "accept",
        "history": [candidate["proposalHash"]],
        "document": document,
        "dependencies": dependencies,
    }
    result_raw = _canonical(result)

    def pure(request: dict[str, Any]) -> dict[str, Any]:
        requests.append(request)
        return cast(
            dict[str, Any],
            {
                "baseline": facts,
                "infer": {},
                "stage": stage,
                "decide": result,
            }[request["mode"]],
        )

    host._pure = pure

    evidence_result = host.evidence("A")
    evidence_raw = _canonical(evidence_result)
    evidence_path = host.root / "evidence.json"
    evidence_path.write_bytes(evidence_raw)
    (host.root / "evidence-receipt.json").write_bytes(
        _canonical(
            {
                "payload": {
                    "proofSessionSha256": host.session_pin["sha256"],
                    "evidenceSha256": _hash(evidence_raw),
                    "omissionSupport": None,
                }
            }
        )
    )
    assert len(terminal_comparisons) == 2
    terminal_comparisons.clear()
    requests.clear()

    for name, raw in (
        ("inference-decision.json", inference_raw),
        ("inference-decision-receipt.json", _canonical({"payload": inference_payload})),
        ("stage.json", stage_raw),
        ("revision-ledger.json", b"placeholder"),
        ("proposal.json", candidate_raw),
        ("decision.json", decision_raw),
        ("result.json", result_raw),
        ("revision-document.json", _canonical(document)),
        ("revision-dependencies.json", _canonical(dependencies)),
        ("revision-manifest.json", b"manifest"),
        ("revision-report.json", b"report"),
    ):
        (host.root / name).write_bytes(raw)
    ledger = {
        "schemaVersion": "qualification-output-revision-ledger/v1",
        "lane": LANE,
        "proofSessionSha256": host.session_pin["sha256"],
        "evidenceSha256": _hash(evidence_raw),
        "inferenceDecisionSha256": _hash(inference_raw),
        "candidateSha256": _hash(candidate_raw),
        "decisionSha256": _hash(decision_raw),
        "resultSha256": _hash(result_raw),
        "outcome": "accept",
        "history": result["history"],
    }
    (host.root / "revision-ledger.json").write_bytes(_canonical(ledger))
    (host.root / "decision-receipt.json").write_bytes(_canonical({"payload": ledger}))

    assert host._accepted_inference() == inference_decision
    assert host._accepted_inference() == inference_decision
    assert len(terminal_comparisons) == 4
    terminal_comparisons.clear()
    requests.clear()

    first = host.accepted_revision()
    second = host.accepted_revision()
    revision_requests = [
        request for request in requests if request["mode"] in {"stage", "decide"}
    ]
    assert len(terminal_comparisons) == 4
    assert revision_requests[0]["evidence"] is revision_requests[1]["evidence"]
    assert revision_requests[2]["evidence"] is revision_requests[3]["evidence"]
    assert _canonical(revision_requests[0]["evidence"]) == evidence_raw
    assert _canonical(revision_requests[2]["evidence"]) == evidence_raw
    assert _canonical(first[0]) == _canonical(second[0]) == result_raw
    assert _canonical(first[1]) == _canonical(second[1]) == candidate_raw
    assert (host.root / "result.json").read_bytes() == result_raw

    evidence_path.write_bytes(_canonical({**evidence_result, "changed": True}))
    with pytest.raises(OutputConsistencyError, match="observation origin differs"):
        host.accepted_revision()
    assert len(terminal_comparisons) == 4

    evidence_path.write_bytes(evidence_raw)
    decoded_path = pristine_controller.journal.artifacts / _hash(
        pristine_sealed.output.decoded_samples
    )
    decoded = bytearray(decoded_path.read_bytes())
    decoded[0] ^= 1
    decoded_path.write_bytes(decoded)
    with pytest.raises(OutputConsistencyError):
        host.accepted_revision()
    assert len(terminal_comparisons) == 5

    decoded_path.write_bytes(pristine_sealed.output.decoded_samples)
    terminal_comparisons.clear()
    requests.clear()

    def mutate_evidence_after_ledger_check(_stage: Any) -> None:
        evidence_path.write_bytes(_canonical({**evidence_result, "changed": True}))

    host._regenerated_handoff = mutate_evidence_after_ledger_check
    with pytest.raises(
        OutputConsistencyError, match="evidence changed during accepted revision"
    ):
        host.accepted_revision()
    assert not any(request["mode"] == "decide" for request in requests)
    assert len(terminal_comparisons) == 2
    evidence_path.write_bytes(evidence_raw)


@pytest.mark.parametrize("tamper", [False, True])
def test_revised_environment_rechecks_same_proof_before_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tamper: bool
) -> None:
    from vera_timeline_agent import qualification_output_proof_v2 as proof_module
    from vera_timeline_agent import roundtrip_v2_records

    session_path = tmp_path / "proof-session.json"
    session_path.write_bytes(b"pinned proof session")
    session_pin = proof_module._pin(session_path)
    preflight_path = tmp_path / "revised-preflight.json"
    preflight_path.write_bytes(b"pinned preflight")
    record = {"proofSession": session_pin}
    events: list[str] = []

    def check_proof_current() -> None:
        events.append("proof-current")
        proof_module._pinned(session_pin)

    current_proof = SimpleNamespace(
        session_pin=session_pin, _current=check_proof_current
    )

    def verify_preflight(path: Path, digest: str) -> tuple[dict[str, Any], Any]:
        assert path == preflight_path and digest == "d" * 64
        assert proof_module._pinned(session_pin) == b"pinned proof session"
        events.append("preflight")
        if tamper:
            session_path.write_bytes(b"changed after preflight")
        return record, current_proof

    def verify_reservation(*_args: Any, proof: Any, **_kwargs: Any) -> None:
        assert proof is current_proof
        events.append("reservation")

    monkeypatch.setattr(
        proof_module, "_verify_revised_preflight_with_proof_v2", verify_preflight
    )
    monkeypatch.setattr(
        proof_module,
        "_verify_revised_rebuild_reservation_for_proof_v2",
        verify_reservation,
    )
    monkeypatch.setattr(roundtrip_v2_records, "proof_source_hashes_v2", lambda: {})
    monkeypatch.setattr(
        controller_module, "output_release_snapshot", lambda _root: b"release"
    )
    monkeypatch.setattr(
        controller_module, "output_runtime_snapshot", lambda: b"runtime"
    )
    controller: Any = object.__new__(QualificationOutputController)
    controller.admission = SimpleNamespace(
        admission_path=tmp_path / "admission.json",
        assert_current=lambda: events.append("admission"),
    )
    controller.revised_preflight = (preflight_path, "d" * 64)
    controller.release_root = tmp_path / "release"
    controller.context = {
        "target": {"timelineUid": "fresh"},
        "caseId": "A",
        "invocationId": "invocation",
    }
    controller.blobs = {
        "hostSourceGraphSha256": _canonical({}),
        "installedReleaseSha256": b"release",
        "runtimeSha256": b"runtime",
    }

    if tamper:
        with pytest.raises(OutputConsistencyError, match="bytes or identity changed"):
            controller._environment_current()
        assert "reservation" not in events
    else:
        controller._environment_current()
        assert events[:4] == ["admission", "preflight", "proof-current", "reservation"]


def test_proof_pair_refuses_disk_tamper_before_pair_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pristine_case, edited_case = shortened_pair(source_start=1)
    pristine_root, edited_root = tmp_path / "pristine", tmp_path / "edited"
    pristine_root.mkdir()
    edited_root.mkdir()
    pristine_controller, pristine = controller_fixture(
        pristine_root, monkeypatch, pristine_case
    )
    edited_controller, _edited = controller_fixture(
        edited_root, monkeypatch, edited_case
    )
    decoded_path = pristine_controller.journal.artifacts / _hash(
        pristine.output.decoded_samples
    )
    decoded = bytearray(decoded_path.read_bytes())
    decoded[0] ^= 1
    decoded_path.write_bytes(decoded)
    pair_checks: list[bool] = []
    monkeypatch.setattr(
        output,
        "_compare_prediction_pair_from_verified",
        lambda *_args: pair_checks.append(True),
    )
    session: Any = object.__new__(proof.QualificationOutputProofV2)
    session.baseline = pristine_controller
    session.edited = edited_controller
    session._current = lambda: None
    session._pure = lambda _request: {}

    with pytest.raises(OutputConsistencyError):
        session.evidence("B")
    assert pair_checks == []


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
        "_load_terminal_output_with_comparison",
        lambda controller: (
            outputs["pristine" if controller is controllers["pristine"] else "edited"],
            {},
        ),
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
        current()
        requests.append(request)
        if request["mode"] == "baseline":
            result = {"documentHash": "document", "dependenciesHash": "dependencies"}
        else:
            result = {}
        current()
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
