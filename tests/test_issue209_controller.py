"""Real disk journal exclusion/CAS/recovery; no native or operator authority."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.qualification_output_controller_v2 import (
    OutputAttemptJournal,
    QualificationOutputController,
    _hash,
    _json_hash,
    _ReceiptVault,
    issue_operator_approval,
    output_profile_snapshot,
    verify_revised_preflight_v2,
)
from vera_timeline_agent.qualification_output_records_v2 import (
    AUTHORITY_REFERENCE_FIELDS,
    CONTEXT_HASH_FIELDS,
    EMPTY_HEAD,
    LANE,
    OutputConsistencyError,
    _canonical,
)


def context(
    *, invocation: str = "invocation-one", package: str = "a" * 64
) -> dict[str, Any]:
    value: dict[str, Any] = {key: "a" * 64 for key in CONTEXT_HASH_FIELDS}
    value.update(
        {
            "lane": LANE,
            "invocationId": invocation,
            "caseId": "case-one",
            "phase": "pristine",
            "target": {
                "projectUid": "project-one",
                "timelineUid": "timeline-one",
                "projectName": "disposable",
                "timelineName": "disposable",
            },
            "binding": {"kind": "baseline"},
            "packageSha256": package,
        }
    )
    projection = {
        k: v
        for k, v in value.items()
        if k not in AUTHORITY_REFERENCE_FIELDS | {"invocationId"}
    }
    value["binding"]["bindingSha256"] = _json_hash(projection)
    return value


def commit(journal: OutputAttemptJournal, ctx: dict[str, Any]) -> dict[str, Any]:
    return journal.commit(
        ctx,
        _canonical(
            {
                "context": ctx,
                "predictionBytesSha256": _hash(b"prediction"),
                "commitmentReceiptSha256": "b" * 64,
            }
        ),
        b"prediction",
    )


def reserve(journal: OutputAttemptJournal, row: dict[str, Any]) -> dict[str, Any]:
    return journal.transition(
        row["context"],
        "reserved_by_render_intent",
        expected_head=row["entrySha256"],
        reservation=_canonical(
            {
                "context": row["context"],
                "commitmentRawSha256": row["commitmentRawSha256"],
                "commitmentPayloadSha256": row["commitmentPayloadSha256"],
            }
        ),
    )


def test_reopened_journal_has_complete_cross_binding_uid_chain(tmp_path: Path) -> None:
    first = context()
    journal = OutputAttemptJournal(tmp_path / "private", first)
    a = commit(journal, first)
    second = context(package="b" * 64)
    b = commit(OutputAttemptJournal(tmp_path / "private", second), second)
    assert b["sequence"] == 1
    assert b["priorHeadSha256"] == a["entrySha256"]
    assert len(journal.history()) == 2


def test_invocation_and_authority_renewal_cannot_reset_attempt(tmp_path: Path) -> None:
    first = context()
    journal = OutputAttemptJournal(tmp_path / "private", first)
    commit(journal, first)
    renewed = context(invocation="invocation-two")
    renewed["preflightSha256"] = "c" * 64
    assert renewed["binding"] == first["binding"]
    with pytest.raises(OutputConsistencyError, match="already attempted"):
        commit(journal, renewed)
    assert len(journal.history()) == 1


def test_two_handles_cannot_reserve_same_commitment(tmp_path: Path) -> None:
    ctx = context()
    one = OutputAttemptJournal(tmp_path / "private", ctx)
    two = OutputAttemptJournal(tmp_path / "private", ctx)
    row = commit(one, ctx)
    reserve(one, row)
    with pytest.raises(OutputConsistencyError, match="CAS"):
        reserve(two, row)


@pytest.mark.parametrize(
    "state", ["uncertain", "compared_consistent", "compared_refused"]
)
def test_terminal_and_uncertain_are_never_retryable(tmp_path: Path, state: str) -> None:
    ctx = context()
    journal = OutputAttemptJournal(tmp_path / "private", ctx)
    row = reserve(journal, commit(journal, ctx))
    result = (
        None
        if state == "uncertain"
        else _canonical(
            {
                "context": ctx,
                "status": state,
                "priorLedgerHeadSha256": row["entrySha256"],
                "commitmentRawSha256": row["commitmentRawSha256"],
                "reservationRawSha256": row["reservationRawSha256"],
            }
        )
    )
    journal.transition(ctx, state, expected_head=row["entrySha256"], result=result)
    with pytest.raises(OutputConsistencyError, match="already attempted"):
        commit(journal, ctx)


def test_terminal_cas_detects_other_binding_interleaving(tmp_path: Path) -> None:
    ctx = context()
    journal = OutputAttemptJournal(tmp_path / "private", ctx)
    first = reserve(journal, commit(journal, ctx))
    commit(journal, context(package="c" * 64))
    with pytest.raises(OutputConsistencyError, match="CAS"):
        journal.transition(ctx, "uncertain", expected_head=first["entrySha256"])
    assert len(journal.history()) == 3


def test_partial_publication_requires_read_only_recovery(tmp_path: Path) -> None:
    ctx = context()
    journal = OutputAttemptJournal(tmp_path / "private", ctx)
    commit(journal, ctx)
    (journal.directory / "pending-0001.json").write_text("{}")
    with pytest.raises(OutputConsistencyError, match="read-only recovery"):
        journal.history()
    with pytest.raises(OutputConsistencyError, match="read-only recovery"):
        commit(journal, context(package="c" * 64))


def test_recovery_reports_partial_fixed_files_without_mutating_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import qualification_output_native_v2 as native

    ctx = context()
    journal = OutputAttemptJournal(tmp_path / "host", ctx)
    commit(journal, ctx)
    pending = journal.directory / "pending-0001.json"
    pending.write_bytes(b"partial host publication")
    operation = tmp_path / "native" / "00000000"
    operation.mkdir(parents=True)
    fixed = {
        "request": operation / "request.json",
        "authority": operation / "authority.json",
        "start": operation / "native-start.json",
        "intent": operation / "intent.json",
    }
    for name, path in fixed.items():
        path.write_bytes(name.encode())

    controller = object.__new__(QualificationOutputController)
    controller.context = ctx
    controller.journal = journal

    def paths(_context_value: dict[str, Any], _sequence: int) -> tuple[Path, ...]:
        return (
            operation / "result.json",
            fixed["authority"],
            fixed["intent"],
            fixed["request"],
        )

    def partial(_context_value: dict[str, Any]) -> tuple[int, str]:
        raise OutputConsistencyError("read-only recovery required")

    monkeypatch.setattr(native, "native_request_paths", paths)
    monkeypatch.setattr(native, "next_native_operation", partial)
    before = {path: path.read_bytes() for path in operation.iterdir()}
    before[pending] = pending.read_bytes()

    report = controller.inspect_recovery()

    assert report["status"] == "incomplete"
    assert report["reportType"] == "inventory_only_not_qualified_receipts"
    assert any(
        item["path"] == str(pending) for item in report["hostJournal"]["pending"]
    )
    slot = report["nativeOperations"][0]
    assert slot["request"]["sha256"] == _hash(fixed["request"].read_bytes())
    assert slot["start"]["sha256"] == _hash(fixed["start"].read_bytes())
    assert slot["intent"]["sha256"] == _hash(fixed["intent"].read_bytes())
    assert "authority" not in slot
    after = {path: path.read_bytes() for path in operation.iterdir()}
    after[pending] = pending.read_bytes()
    assert after == before
    assert not (operation / "effects").exists()


def test_recovery_distinguishes_empty_and_complete_fixed_chains(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import qualification_output_native_v2 as native

    ctx = context()
    journal_dir = tmp_path / "host"
    journal_dir.mkdir()
    journal = type(
        "Journal", (), {"directory": journal_dir, "history": lambda self: []}
    )()
    controller = object.__new__(QualificationOutputController)
    controller.context = ctx
    controller.journal = journal
    operations = tmp_path / "native"

    def paths(_context_value: dict[str, Any], sequence: int) -> tuple[Path, ...]:
        operation = operations / f"{sequence:08d}"
        return (
            operation / "result.json",
            operation / "authority.json",
            operation / "intent.json",
            operation / "request.json",
        )

    def tail(_context_value: dict[str, Any]) -> tuple[int, str]:
        if all(paths(ctx, sequence)[0].is_file() for sequence in range(7)):
            raise OutputConsistencyError("reviewed native action plan is exhausted")
        return 0, EMPTY_HEAD

    def verify(path: Path, _digest: str) -> dict[str, Any]:
        sequence = int(path.parent.name)
        return {"sequence": sequence, "status": "complete"}

    monkeypatch.setattr(native, "native_request_paths", paths)
    monkeypatch.setattr(native, "next_native_operation", tail)
    monkeypatch.setattr(native, "verify_native_result", verify)
    assert controller.inspect_recovery()["status"] == "empty"

    for sequence in range(7):
        result_path = paths(ctx, sequence)[0]
        result_path.parent.mkdir(parents=True)
        result_path.write_bytes(f"result-{sequence}".encode())
    journal.history = lambda: [
        {
            "sequence": 0,
            "state": "compared_consistent",
            "entrySha256": "a" * 64,
            "context": ctx,
        }
    ]
    report = controller.inspect_recovery()
    assert report["status"] == "complete"
    assert report["nextOperation"] is None


def test_mutated_or_missing_middle_entry_refuses(tmp_path: Path) -> None:
    ctx = context()
    journal = OutputAttemptJournal(tmp_path / "private", ctx)
    row = commit(journal, ctx)
    path = journal.directory / "entry-0000.json"
    path.chmod(0o600)
    row["priorHeadSha256"] = "f" * 64
    path.write_bytes(_canonical(row))
    with pytest.raises(OutputConsistencyError, match="partial journal"):
        journal.history()


def test_symlink_and_public_root_refuse(tmp_path: Path) -> None:
    root = tmp_path / "private"
    root.mkdir(mode=0o755)
    with pytest.raises(OutputConsistencyError, match="private"):
        OutputAttemptJournal(root, context())
    alias = tmp_path / "alias"
    alias.symlink_to(root)
    with pytest.raises(OutputConsistencyError, match="symlink"):
        OutputAttemptJournal(alias, context())


def test_context_cannot_move_to_other_uid_chain(tmp_path: Path) -> None:
    ctx = context()
    journal = OutputAttemptJournal(tmp_path / "private", ctx)
    changed = copy.deepcopy(ctx)
    changed["target"]["timelineUid"] = "another-timeline"
    changed["binding"].pop("bindingSha256")
    projection = {
        k: v
        for k, v in changed.items()
        if k not in AUTHORITY_REFERENCE_FIELDS | {"invocationId"}
    }
    changed["binding"]["bindingSha256"] = _json_hash(projection)
    with pytest.raises(OutputConsistencyError, match="chain"):
        commit(journal, changed)
    assert journal.history() == []


def test_revised_preflight_is_statically_default_deny() -> None:
    with pytest.raises(OutputConsistencyError, match="#215"):
        verify_revised_preflight_v2({"verifier": "accept"})


def test_compare_refuses_environment_drift_before_comparison_or_cas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typing import cast

    from vera_timeline_agent import qualification_output_v2 as output

    calls: list[str] = []

    def environment_drift(_self: QualificationOutputController) -> None:
        calls.append("environment")
        raise OutputConsistencyError("environment drift")

    def forbidden_compare(*_args: Any, **_kwargs: Any) -> Any:
        calls.append("compare")
        raise AssertionError("comparison must not run after environment drift")

    monkeypatch.setattr(
        QualificationOutputController, "_environment_current", environment_drift
    )
    monkeypatch.setattr(output, "compare_committed_output", forbidden_compare)
    controller = object.__new__(QualificationOutputController)

    with pytest.raises(OutputConsistencyError, match="environment drift"):
        controller.compare(cast(output.CommittedOutput, object()))

    assert calls == ["environment"]


def test_empty_journal_head_is_exact_frozen_domain(tmp_path: Path) -> None:
    journal = OutputAttemptJournal(tmp_path / "private", context())
    row = commit(journal, context())
    assert row["priorHeadSha256"] == EMPTY_HEAD


def test_host_receipt_integrity_domain_and_retained_provenance(tmp_path: Path) -> None:
    import json

    vault = _ReceiptVault(tmp_path / "receipts")
    payload = {"context": context(), "prediction": "bounded"}
    receipt = vault._issue(
        "output_prediction_commitment", payload, (b"source provenance",)
    )
    vault.authenticate("output_prediction_commitment", receipt, payload)
    reopened = _ReceiptVault(tmp_path / "receipts")
    reopened.authenticate("output_prediction_commitment", receipt, payload)
    with pytest.raises(OutputConsistencyError, match="domain"):
        reopened.authenticate("output_decode_record", receipt, payload)
    changed = json.loads(receipt)
    changed["payload"]["prediction"] = "forged"
    with pytest.raises(OutputConsistencyError, match="integrity"):
        reopened.authenticate(
            "output_prediction_commitment", _canonical(changed), changed["payload"]
        )
    evidence = vault.root / _hash(b"source provenance")
    evidence.chmod(0o600)
    evidence.write_bytes(b"altered")
    with pytest.raises(OutputConsistencyError, match="evidence changed"):
        vault.authenticate("output_prediction_commitment", receipt, payload)


def test_caller_receipt_or_legacy_kind_cannot_enroll(tmp_path: Path) -> None:
    vault = _ReceiptVault(tmp_path / "receipts")
    with pytest.raises(OutputConsistencyError, match="unsupported"):
        vault._issue("render_receipt", {}, (b"fake",))
    other = _ReceiptVault(tmp_path / "other")
    receipt = other._issue("output_geometry_snapshot", {}, (b"same hashes",))
    with pytest.raises(OutputConsistencyError, match="integrity"):
        vault.authenticate("output_geometry_snapshot", receipt, {})


def test_operator_issuer_rejects_wrong_actor_before_interaction(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    from vera_timeline_agent.qualification_output_controller_v2 import (
        OPERATOR_PLAN_SCHEMA,
        OPERATOR_PLAN_STATUS,
        OPERATOR_PROPOSAL_SCHEMA,
    )
    from vera_timeline_agent.qualification_output_native_v2 import APPROVAL_FIELDS

    proposal: dict[str, Any] = dict.fromkeys(
        APPROVAL_FIELDS | {"proposalStatus"}, "placeholder"
    )
    proposal.update(
        {
            "schemaVersion": OPERATOR_PROPOSAL_SCHEMA,
            "lane": LANE,
            "proposalStatus": OPERATOR_PLAN_STATUS,
            "operator": "not-the-local-operator-209",
        }
    )
    plan.write_bytes(
        _canonical(
            {
                "schemaVersion": OPERATOR_PLAN_SCHEMA,
                "lane": LANE,
                "authorityStatus": OPERATOR_PLAN_STATUS,
                "proposal": proposal,
            }
        )
    )
    destination = tmp_path / "approval.json"
    with pytest.raises(OutputConsistencyError, match="operator identity"):
        issue_operator_approval(plan, destination)
    assert not destination.exists()


def test_review_only_operator_plan_is_not_native_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import qualification_output_native_v2 as native
    from vera_timeline_agent import workflow_v2_cli
    from vera_timeline_agent.qualification_output_controller_v2 import (
        OPERATOR_PLAN_SCHEMA,
        OPERATOR_PLAN_STATUS,
        OPERATOR_PROPOSAL_SCHEMA,
    )

    controller = object.__new__(QualificationOutputController)
    controller.context = context()
    admission_path = tmp_path / "admission.json"
    admission_path.write_bytes(b"admission")
    release_manifest = tmp_path / "release" / "vera-delivery-v2" / "release.json"
    release_manifest.parent.mkdir(parents=True)
    release_manifest.write_bytes(b"reviewed release")
    controller.release_root = tmp_path / "release"
    controller.admission = type(
        "Admission",
        (),
        {"profile": native.R16_PROFILE, "admission_path": admission_path},
    )()
    plan_path = tmp_path / "operator-plan.json"
    plan_path.write_bytes(
        _canonical(
            {
                "schemaVersion": OPERATOR_PLAN_SCHEMA,
                "lane": LANE,
                "authorityStatus": OPERATOR_PLAN_STATUS,
                "proposal": {
                    "schemaVersion": OPERATOR_PROPOSAL_SCHEMA,
                    "lane": LANE,
                    "proposalStatus": OPERATOR_PLAN_STATUS,
                    "operator": "reviewer",
                },
            }
        )
    )
    monkeypatch.setattr(
        QualificationOutputController, "_environment_current", lambda _self: None
    )
    monkeypatch.setattr(
        workflow_v2_cli, "_verify_output_release", lambda _root: release_manifest
    )

    with pytest.raises(OutputConsistencyError, match="closed operator approval"):
        native.verify_operator_approval(
            plan_path.read_bytes(),
            context=controller.context,
            profile=native.R16_PROFILE,
            admission_sha256=_hash(admission_path.read_bytes()),
            release_manifest_sha256=_hash(release_manifest.read_bytes()),
        )
    with pytest.raises(OutputConsistencyError, match="closed operator approval"):
        controller.prepare_native_request("construct", {}, approval_path=plan_path)


def test_operator_plan_proposal_is_not_approval_bytes() -> None:
    from vera_timeline_agent import qualification_output_native_v2 as native
    from vera_timeline_agent.qualification_output_controller_v2 import (
        OPERATOR_PLAN_SCHEMA,
        OPERATOR_PLAN_STATUS,
        OPERATOR_PROPOSAL_FIELDS,
        OPERATOR_PROPOSAL_SCHEMA,
        _approval_from_proposal,
        _operator_plan_proposal,
    )

    proposal = dict.fromkeys(OPERATOR_PROPOSAL_FIELDS, "placeholder")
    proposal.update(
        {
            "schemaVersion": OPERATOR_PROPOSAL_SCHEMA,
            "lane": LANE,
            "proposalStatus": OPERATOR_PLAN_STATUS,
        }
    )
    raw = _canonical(
        {
            "schemaVersion": OPERATOR_PLAN_SCHEMA,
            "lane": LANE,
            "authorityStatus": OPERATOR_PLAN_STATUS,
            "proposal": proposal,
        }
    )
    parsed = _operator_plan_proposal(raw)
    assert "proposalStatus" in parsed
    assert _approval_from_proposal(parsed)["schemaVersion"] == native.APPROVAL_SCHEMA
    with pytest.raises(OutputConsistencyError, match="closed operator approval"):
        native.verify_operator_approval(
            raw,
            context=context(),
            profile=native.R16_PROFILE,
            admission_sha256="a" * 64,
            release_manifest_sha256="b" * 64,
        )


def test_post_capture_refusal_is_retained_and_blocks_retry(tmp_path: Path) -> None:
    ctx = context()
    journal = OutputAttemptJournal(tmp_path / "private", ctx)
    row = reserve(journal, commit(journal, ctx))
    controller = object.__new__(QualificationOutputController)
    controller.context = ctx
    controller.journal = journal

    controller._retain_finalize_refusal(
        result_sha256="f" * 64,
        stage="decode",
        error=OutputConsistencyError("decoded output differs"),
    )

    latest = journal.history()[-1]
    assert latest["state"] == "uncertain"
    marker = next(journal.directory.glob("finalize-refusal-*.json"))
    assert b"decoded output differs" in marker.read_bytes()
    with pytest.raises(OutputConsistencyError, match="already attempted"):
        commit(journal, ctx)
    assert row["state"] == "reserved_by_render_intent"


def test_committed_prediction_is_durable_before_reservation(tmp_path: Path) -> None:
    journal = OutputAttemptJournal(tmp_path / "private", context())
    row = commit(journal, context())
    assert (
        journal.artifacts / row["predictionBytesSha256"]
    ).read_bytes() == b"prediction"
    artifact = journal.artifacts / row["commitmentRawSha256"]
    artifact.chmod(0o600)
    artifact.write_bytes(b"tampered")
    with pytest.raises(OutputConsistencyError, match="artifact differs"):
        journal.history()


def test_tail_truncation_cannot_hide_an_attempt(tmp_path: Path) -> None:
    journal = OutputAttemptJournal(tmp_path / "private", context())
    commit(journal, context())
    (journal.directory / "entry-0000.json").unlink()
    (journal.directory / "pending-0000.json").unlink()
    with pytest.raises(OutputConsistencyError, match="read-only recovery"):
        commit(journal, context())


@pytest.mark.parametrize(
    "rate",
    [
        {"numerator": 24, "denominator": 1},
        {"numerator": 24000.0, "denominator": 1001},
    ],
)
def test_profile_refuses_other_or_approximate_rate(rate: dict[str, Any]) -> None:
    with pytest.raises(OutputConsistencyError, match="24000/1001"):
        output_profile_snapshot(
            {"timeline": {"frameRate": rate, "width": 1920, "height": 1080}}
        )


def test_profile_keeps_exact_finite_codec_and_dimensions() -> None:
    import json

    value = json.loads(
        output_profile_snapshot(
            {
                "timeline": {
                    "frameRate": {"numerator": 24000, "denominator": 1001},
                    "width": 1920,
                    "height": 1080,
                }
            }
        )
    )
    assert (
        value["container"],
        value["videoCodec"],
        value["audioCodec"],
        value["audioBitDepth"],
        value["sampleRate"],
        value["channels"],
    ) == ("mov", "prores422", "lpcm", 24, 48000, 2)


def test_host_native_request_cannot_skip_the_fixed_first_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import qualification_output_native_v2 as native
    from vera_timeline_agent import workflow_v2_cli

    controller = object.__new__(QualificationOutputController)
    controller.context = context()
    admission_path = tmp_path / "admission.json"
    admission_path.write_bytes(b"admission")
    controller.release_root = tmp_path / "release"
    release_manifest = controller.release_root / "vera-delivery-v2" / "release.json"
    release_manifest.parent.mkdir(parents=True)
    release_manifest.write_bytes(b"reviewed release")
    controller.admission = type(
        "Admission",
        (),
        {"profile": native.R16_PROFILE, "admission_path": admission_path},
    )()
    approval_path = tmp_path / "approval.json"
    approval_path.write_bytes(_canonical({"releaseManifestSha256": "d" * 64}))
    checked: list[dict[str, Any]] = []
    approval_checks: list[dict[str, Any]] = []

    monkeypatch.setattr(
        QualificationOutputController, "_environment_current", lambda _self: None
    )
    monkeypatch.setattr(
        workflow_v2_cli,
        "_verify_output_release",
        lambda _root: release_manifest,
    )

    def fake_approval(_raw: bytes, **kwargs: Any) -> dict[str, Any]:
        approval_checks.append(kwargs)
        return {
            "operator": "reviewer",
            "expiresAt": "2026-10-17T00:00:00Z",
            "releaseManifestSha256": "d" * 64,
            "confirmations": {},
        }

    monkeypatch.setattr(native, "verify_operator_approval", fake_approval)

    def next_operation(actual: dict[str, Any]) -> tuple[int, str]:
        checked.append(actual)
        return 0, EMPTY_HEAD

    monkeypatch.setattr(native, "next_native_operation", next_operation)
    with pytest.raises(OutputConsistencyError, match="fixed reviewed stage order"):
        controller.prepare_native_request(
            "save_reopen", {}, approval_path=approval_path
        )
    assert checked == [controller.context]
    assert approval_checks[0]["release_manifest_sha256"] == _hash(
        release_manifest.read_bytes()
    )


def test_native_request_handoff_pins_both_release_hash_domains(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from vera_timeline_agent import workflow_v2_cli

    controller = object.__new__(QualificationOutputController)
    controller.context = context()
    controller.release_root = tmp_path / "release"
    host_artifacts = tmp_path / "host-artifacts"
    host_artifacts.mkdir()
    controller.journal = type("Journal", (), {"artifacts": host_artifacts})()
    manifest = controller.release_root / "vera-delivery-v2" / "release.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(b"reviewed raw release manifest")
    monkeypatch.setattr(
        workflow_v2_cli, "_verify_output_release", lambda _root: manifest
    )

    request_path = tmp_path / "native" / "00000002" / "request.json"
    request_path.parent.mkdir(parents=True)
    request_path.write_bytes(
        _canonical(
            {
                "context": controller.context,
                "sequence": 2,
                "action": "capture_pre",
                "releaseManifestSha256": _hash(manifest.read_bytes()),
                "release": {"sha256": controller.context["installedReleaseSha256"]},
            }
        )
    )
    handoff_path = controller._publish_native_operator_handoff(
        request_path, 2, "capture_pre"
    )
    assert handoff_path.parent == host_artifacts
    assert handoff_path.parent != request_path.parent
    handoff = json.loads(handoff_path.read_bytes())

    assert handoff["sequence"] == 2
    assert handoff["action"] == "capture_pre"
    assert handoff["hostRequest"] == {
        "path": str(request_path),
        "sha256": _hash(request_path.read_bytes()),
    }
    assert handoff["reviewedReleaseSource"] == {
        "root": str(controller.release_root),
        "rootMeaning": "prepared reviewed output-release bundle to install",
        "manifestPath": str(manifest),
        "releaseManifestSha256": _hash(manifest.read_bytes()),
        "normalizedContentSha256": controller.context["installedReleaseSha256"],
    }
    assert handoff["installedRequestRelativePath"] == "vera-delivery-v2/request.json"
    manual_flow = handoff["manualFlow"]
    assert manual_flow["sourceInstallRequiredForThisStage"] is False
    assert any(
        "archive the prior installed request" in step
        for step in manual_flow["requestReplacement"]
    )
    assert "Keep Resolve running" in manual_flow["launch"]
    assert "Do not restart Resolve" in manual_flow["launch"]
