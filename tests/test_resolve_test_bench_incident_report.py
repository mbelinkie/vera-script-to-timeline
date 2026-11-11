"""Adversarial, no-effect Test Bench reporting and seventh-case regression."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import resolve_test_bench_diagnostic_journal as journal
from vera_timeline_agent import resolve_test_bench_diagnostics as contract
from vera_timeline_agent import resolve_test_bench_incident_report as report

SEVENTH = (
    Path(__file__).resolve().parents[1]
    / "docs/verification/issue-512-seventh-case-map.json"
)


@pytest.fixture
def case_root(tmp_path: Path) -> Path:
    root = tmp_path / "case"
    root.mkdir(mode=0o700)
    return root


def _writer(
    root: Path, *, case_id: str = "case123", stage: str = "pristine"
) -> journal.DiagnosticJournal:
    return journal.DiagnosticJournal(
        root,
        case_id=case_id,
        phase=stage,
        stage=stage,
        pins={"frozenSourceSha256": "a" * 64, "actorSha256": "b" * 64},
    )


def _record_path(root: Path, index: int) -> Path:
    return root / "diagnostics-v1" / "records" / f"record-{index:06d}.json"


def test_seventh_map_json_and_markdown_are_true_zero_of_four(
    capsys: pytest.CaptureFixture[str],
) -> None:
    incident = report.report_from_seventh_map(SEVENTH)
    assert incident["caseId"] == "vera499phase26h2426ee095c73443d"
    assert (
        incident["sourcePins"]["frozenCommit"]
        == "91e260291ed279a3789e1022afc2e0250c2d5b0a"
    )
    assert incident["stageCounts"]["authenticatedNativeResultsInPriorAudit"] == 5
    assert incident["m4"]["signedReceiptsPresentInPriorAudit"] == 0
    assert incident["m4"]["required"] == 4
    assert incident["lastVerifiedActionClaim"]["action"] == "start_render"
    assert incident["firstMissingBoundary"]["action"] == "poll_render"
    assert incident["firstMissingBoundary"]["requestPresent"] is False
    assert incident["nativeRetryPermitted"] is False
    assert any(
        item["role"] == "prior_audit_source_map" and item["verifiedByReader"]
        for item in incident["evidenceInventory"]
    )
    assert all(
        not item["verifiedByReader"]
        for item in incident["evidenceInventory"]
        if item["role"] != "prior_audit_source_map"
    )
    assert report.main(["--seventh-map", str(SEVENTH), "--format", "markdown"]) == 0
    output = capsys.readouterr().out
    assert "0/4 M4" in output
    assert "start_render" in output
    assert "poll_render" in output
    assert "pristine" in output and "rebuild" in output
    assert report.main(["--seventh-map", str(SEVENTH)]) == 0
    assert json.loads(capsys.readouterr().out) == incident


def test_read_only_chain_crash_unknown_and_render_pcm_refs(case_root: Path) -> None:
    writer = _writer(case_root)
    writer.emit("claim", "before_claim", status="pending")
    writer.emit("claim", "after_claim")
    for sequence, action in enumerate(
        ("construct", "save_reopen", "capture_pre", "queue_render", "start_render")
    ):
        writer.cursor(
            action=action,
            sequence=sequence,
            last_verified={
                "nativeSequence": sequence,
                "action": action,
                "resultSha256": "c" * 64,
            },
            next_pending={
                "nativeSequence": sequence + 1,
                "action": "poll_render" if sequence == 4 else "next_action",
            },
        )
        writer.emit(
            "carrier_result",
            "after_carrier",
            proof_layer="authenticated_native_result",
            proof_sha256="c" * 64,
        )
        writer.emit("ingestion", "after_ingest")
    try:
        raise RuntimeError("token=hush /Users/secret/private.mov")
    except RuntimeError as error:
        writer.emit("exception", "before_dispatch", exception=error)

    # Materialize a canonical next record carrying safe pointers without opening media.
    prior = _record_path(case_root, 12)
    original = prior.read_bytes()
    payload: dict[str, Any] = json.loads(original)
    payload["evidence"] = [
        {
            "role": "mov",
            "sha256": "d" * 64,
            "sizeBytes": 10**12,
            "locatorSha256": "e" * 64,
        },
        {
            "role": "pcm",
            "sha256": "f" * 64,
            "sizeBytes": 1024,
            "locatorSha256": "a" * 64,
        },
    ]
    # Writer's immutable bytes must not be changed; publish a separate test-only record.
    path = _record_path(case_root, 13)
    payload["recordIndex"] = 13
    payload["previousRecordSha256"] = hashlib.sha256(original).hexdigest()
    path.write_bytes(contract.canonical_bytes(payload))
    path.chmod(0o600)
    frozen = {p: p.read_bytes() for p in sorted(path.parent.iterdir())}
    incident = report.report_from_diagnostics([case_root], case_id="case123")
    assert incident["stageCounts"]["hostIngestedActionClaims"] == 5
    assert incident["lastVerifiedActionClaim"]["action"] == "start_render"
    assert incident["firstMissingBoundary"]["action"] == "poll_render"
    assert incident["m4"]["signedReceiptsVerifiedByReader"] == 0
    assert incident["nativeRetryPermitted"] is False
    assert any(
        row["role"] == "mov"
        and row["sha256"] == "d" * 64
        and not row["verifiedByReader"]
        for row in incident["evidenceInventory"]
    )
    assert any(
        row["role"] == "pcm" and row["locatorSha256"] == "a" * 64
        for row in incident["evidenceInventory"]
    )
    output = json.dumps(incident) + report.as_markdown(incident)
    assert "hush" not in output and "/Users/secret" not in output
    assert frozen == {p: p.read_bytes() for p in sorted(path.parent.iterdir())}


def test_explicit_stage_counts_and_signed_diagnostic_does_not_prove_m4(
    case_root: Path,
) -> None:
    writer = _writer(case_root)
    writer.emit(
        "m4_receipt",
        "after_receipt",
        proof_layer="signed_m4_receipt",
        proof_sha256="d" * 64,
    )
    incident = report.report_from_diagnostics([case_root], case_id="case123")
    assert incident["stages"][0]["signedM4ReceiptClaims"] == 1
    assert incident["m4"]["signedReceiptsVerifiedByReader"] == 0
    assert "UNPROVEN" in incident["m4"]["verdict"]


def test_cleared_pending_not_revived_and_input_stage_order_not_authoritative(
    case_root: Path, tmp_path: Path
) -> None:
    pristine = _writer(case_root)
    pristine.cursor(
        action="capture_post",
        sequence=8,
        next_pending={"nativeSequence": 8, "action": "capture_post"},
    )
    pristine.emit("native_dispatch", "before_dispatch", status="pending")
    pristine.cursor(action="capture_post", sequence=8, next_pending=None)
    pristine.emit("ingestion", "after_ingest")
    edited_root = tmp_path / "edited_stage"
    edited_root.mkdir(mode=0o700)
    _writer(edited_root, stage="edited").emit("claim", "after_claim")
    incident = report.report_from_diagnostics(
        [edited_root, case_root], case_id="case123"
    )
    assert [stage["name"] for stage in incident["stages"]] == ["pristine", "edited"]
    assert incident["firstMissingBoundary"] == {
        "stage": "pristine",
        "event": "m4_receipt",
        "reason": "no independently verified stage receipt",
    }


def test_evidence_hashed_pointers_emitted_durably_without_opening_media(
    case_root: Path,
) -> None:
    writer = _writer(case_root)
    mov = {
        "role": "mov",
        "sha256": "d" * 64,
        "sizeBytes": 1_000_000_000,
        "locatorSha256": "e" * 64,
    }
    pcm = {
        "role": "pcm",
        "sha256": "f" * 64,
        "sizeBytes": 123456,
        "locatorSha256": "c" * 64,
    }
    writer.emit("mov_pcm", "after_ingest", evidence=[mov, pcm])
    original = _record_path(case_root, 0).read_bytes()
    incident = report.report_from_diagnostics([case_root], case_id="case123")
    refs = incident["evidenceInventory"]
    assert any(
        r["role"] == "mov"
        and r["sha256"] == mov["sha256"]
        and not r["verifiedByReader"]
        for r in refs
    )
    assert any(
        r["role"] == "pcm"
        and r["locatorSha256"] == pcm["locatorSha256"]
        and not r["verifiedByReader"]
        for r in refs
    )
    assert _record_path(case_root, 0).read_bytes() == original

    bad_root = case_root.parent / "invalid_case"
    bad_root.mkdir(mode=0o700)
    bad = _writer(bad_root)
    with pytest.raises(contract.DiagnosticContractError):
        bad.emit(
            "mov_pcm",
            "after_ingest",
            evidence=[{**mov, "locatorSha256": "/Users/secret/file.mov"}],
        )
    assert not list((bad_root / "diagnostics-v1" / "records").iterdir())


@pytest.mark.parametrize(
    "mutation",
    [
        "broken_json",
        "oversized",
        "gap",
        "chain",
        "permissions",
        "symlink",
        "unexpected",
        "foreign_case",
    ],
)
def test_refuses_malformed_or_cross_case_records_without_reading_unrelated(
    case_root: Path, tmp_path: Path, mutation: str
) -> None:
    writer = _writer(case_root)
    writer.emit("claim", "after_claim")
    valid = _record_path(case_root, 0)
    before = valid.read_bytes()
    unrelated = tmp_path / "unrelated-sensitive.json"
    unrelated.write_text("password=unrelated-sentinel", encoding="utf-8")
    if mutation == "broken_json":
        valid.write_bytes(b"{bad")
    elif mutation == "oversized":
        valid.write_bytes(b"x" * (contract.MAX_RECORD_BYTES + 1))
    elif mutation == "gap":
        _record_path(case_root, 2).write_bytes(b"irrelevant")
    elif mutation == "chain":
        value = json.loads(before)
        value["recordIndex"] = 1
        value["previousRecordSha256"] = "f" * 64
        _record_path(case_root, 1).write_bytes(contract.canonical_bytes(value))
    elif mutation == "permissions":
        valid.chmod(0o644)
    elif mutation == "symlink":
        valid.unlink()
        valid.symlink_to(unrelated)
    elif mutation == "unexpected":
        (valid.parent / "extra.json").write_bytes(b"{}")
    else:
        value = json.loads(before)
        value["identity"]["caseId"] = "other_case"
        valid.write_bytes(contract.canonical_bytes(value))
    with pytest.raises((report.IncidentReadError, OSError)) as error:
        report.report_from_diagnostics([case_root], case_id="case123")
    assert "unrelated-sentinel" not in str(error.value)
    assert unrelated.read_text() == "password=unrelated-sentinel"


def test_wrong_case_root_symlink_and_cross_stage_identity(
    case_root: Path, tmp_path: Path
) -> None:
    _writer(case_root).emit("claim", "after_claim")
    other = tmp_path / "case2"
    other.mkdir(mode=0o700)
    _writer(other, case_id="othercase", stage="edited").emit("claim", "after_claim")
    with pytest.raises(report.IncidentReadError, match="unrelated case"):
        report.report_from_diagnostics([case_root, other], case_id="case123")
    link = tmp_path / "link"
    link.symlink_to(case_root, target_is_directory=True)
    with pytest.raises(report.IncidentReadError, match="symlink"):
        report.report_from_diagnostics([link], case_id="case123")
    with pytest.raises(report.IncidentReadError, match="duplicate"):
        report.report_from_diagnostics([case_root, case_root], case_id="case123")
    with pytest.raises(report.IncidentReadError, match="unsafe"):
        report.report_from_diagnostics([case_root], case_id="../other")


def test_clock_rollback_pid_change_and_malformed_clock(
    case_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = _writer(case_root)
    clocks: list[dict[str, Any]] = [
        {"utc": "2026-11-11T15:00:00.000000Z", "monotonicNs": 3000, "pid": 10},
        {"utc": "2026-11-11T14:59:00.000000Z", "monotonicNs": 1000, "pid": 11},
    ]
    monkeypatch.setattr(contract, "timestamp", lambda: clocks.pop(0))
    writer.emit("claim", "before_claim", status="pending")
    writer.emit("claim", "after_claim")
    incident = report.report_from_diagnostics([case_root], case_id="case123")
    stage = incident["stages"][0]
    assert stage["elapsed"]["monotonicNs"] is None
    assert any("Wall clock moved backwards" in x for x in incident["uncertainties"])
    assert any("monotonic clock boundary" in x for x in incident["uncertainties"])
    invalid = json.loads(_record_path(case_root, 1).read_bytes())
    invalid["clock"]["utc"] = "2026-99-99T15:00:00.000000Z"
    _record_path(case_root, 1).write_bytes(json.dumps(invalid).encode())
    with pytest.raises(report.IncidentReadError):
        report.report_from_diagnostics([case_root], case_id="case123")


def test_reading_never_calls_resolve_or_writes_and_cli_fail_closed(
    case_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    writer = _writer(case_root)
    writer.emit("claim", "after_claim")
    before = _record_path(case_root, 0).read_bytes()
    monkeypatch.setattr(
        os, "system", lambda _: pytest.fail("unexpected external command")
    )
    assert (
        report.main(
            [
                "--case-root",
                str(case_root),
                "--case-id",
                "case123",
                "--format",
                "markdown",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "Test Bench incident report" in output
    assert "UNPROVEN" in output
    assert _record_path(case_root, 0).read_bytes() == before
    assert report.main(["--case-root", str(case_root), "--case-id", "wrongcase"]) == 2
    assert "Incident report refused" in capsys.readouterr().err


def test_count_quota_and_source_map_tamper(
    case_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    writer = _writer(case_root)
    writer.emit("claim", "after_claim")
    writer.emit("claim", "after_claim")
    monkeypatch.setattr(journal, "MAX_RECORDS", 1)
    with pytest.raises(report.IncidentReadError, match="quota"):
        report.report_from_diagnostics([case_root], case_id="case123")
    original = json.loads(SEVENTH.read_text())
    mutated = copy.deepcopy(original)
    mutated["signedM4ReceiptsPresent"] = 4
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(mutated))
    with pytest.raises(report.IncidentReadError, match="M4"):
        report.report_from_seventh_map(map_path)
    map_path.write_bytes(b"{" * (report.MAX_MAP_BYTES + 1))
    with pytest.raises(report.IncidentReadError):
        report.report_from_seventh_map(map_path)
