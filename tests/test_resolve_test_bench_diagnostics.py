"""#512 phase 1: contract-only tests; no native imports or Resolve effects."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import resolve_test_bench_diagnostics as diagnostics

SOURCE = "a" * 64
NATIVE = "b" * 64


def _record() -> dict[str, Any]:
    return {
        "schema": diagnostics.SCHEMA,
        "recordIndex": 0,
        "previousRecordSha256": None,
        "kind": "stage",
        "event": "carrier_result",
        "boundary": "after_carrier",
        "status": "observed",
        "proofLayer": "authenticated_native_result",
        "proofSha256": NATIVE,
        "clock": {
            "utc": "2026-11-11T16:30:00.000000Z",
            "monotonicNs": 1234,
            "pid": 456,
        },
        "identity": {
            "caseId": "vera499phase26h2426ee095c73443d",
            "jobId": None,
            "operationId": None,
            "phase": "pristine",
            "stage": "pristine",
            "action": "start_render",
            "nativeSequence": 4,
        },
        "pins": {
            "frozenSourceSha256": SOURCE,
            "actorSha256": NATIVE,
            "targetSha256": None,
            "authorizationSha256": None,
        },
        "lastVerified": {
            "nativeSequence": 4,
            "action": "start_render",
            "resultSha256": NATIVE,
        },
        "nextPending": {"nativeSequence": 5, "action": "poll_render"},
        "evidence": [
            {
                "role": "native_result",
                "sha256": NATIVE,
                "sizeBytes": 1249,
                "locatorSha256": SOURCE,
            }
        ],
        "exception": None,
    }


def test_canonical_contract_and_no_embedded_native_authority() -> None:
    record = _record()
    raw = diagnostics.canonical_bytes(record)
    assert raw.endswith(b"\n")
    assert json.loads(raw) == record
    assert diagnostics.canonical_bytes(json.loads(raw)) == raw
    assert b"/Users/" not in raw
    assert hashlib.sha256(raw).hexdigest() != SOURCE


def test_exception_never_passes_and_scrubs_sensitive_details() -> None:
    try:
        raise RuntimeError(
            "Authorization: Bearer abc123 password=verysecret api_key='highsecret' "
            "email admin@example.com in /Users/privateuser/private/key.txt "
            "at https://example.org/upload?token=abc"
        )
    except RuntimeError as error:
        detail = diagnostics.exception_details(error)
    raw = json.dumps(detail)
    for secret in (
        "abc123",
        "verysecret",
        "highsecret",
        "admin@example.com",
        "privateuser",
        "example.org",
    ):
        assert secret not in raw
    assert detail["className"] == "RuntimeError"
    assert detail["frames"]
    assert all(frame["file"] == "redacted.py" for frame in detail["frames"])
    value = _record()
    value.update(
        kind="exception",
        event="exception",
        status="unknown",
        proofLayer="none",
        proofSha256=None,
        exception=detail,
    )
    assert diagnostics.validate_record(value) == value


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("schema", "vera.test-bench-diagnostic/v0"),
        ("event", "native_pass"),
        ("status", "verified"),
        ("kind", ["stage"]),
        ("proofLayer", "pass"),
        ("proofSha256", None),
        ("recordIndex", True),
        ("previousRecordSha256", "c" * 64),
    ],
)
def test_closed_enums_and_broken_chain_refused(field: str, bad: object) -> None:
    value = _record()
    value[field] = bad
    with pytest.raises(diagnostics.DiagnosticContractError):
        diagnostics.validate_record(value)


def test_nonzero_index_requires_prior_digest() -> None:
    value = _record()
    value["recordIndex"] = 1
    value["previousRecordSha256"] = SOURCE
    diagnostics.validate_record(value)
    value["previousRecordSha256"] = None
    with pytest.raises(diagnostics.DiagnosticContractError):
        diagnostics.validate_record(value)


def test_proof_layers_never_confuse_process_native_m4_and_thread_ack() -> None:
    value = _record()
    value["proofLayer"] = "signed_m4_receipt"
    with pytest.raises(diagnostics.DiagnosticContractError, match="M4"):
        diagnostics.validate_record(value)
    value["event"] = "m4_receipt"
    diagnostics.validate_record(value)
    value["proofLayer"] = "origin_thread_ack"
    with pytest.raises(diagnostics.DiagnosticContractError, match="ACK"):
        diagnostics.validate_record(value)
    value["event"] = "origin_thread_ack"
    diagnostics.validate_record(value)


def test_unknown_exception_must_not_claim_native_verification() -> None:
    value = _record()
    value.update(
        kind="exception",
        event="exception",
        status="unknown",
        exception={
            "className": "RuntimeError",
            "message": "missing poll",
            "frames": [],
        },
    )
    with pytest.raises(diagnostics.DiagnosticContractError, match="never certifies"):
        diagnostics.validate_record(value)
    value["proofLayer"] = "none"
    value["proofSha256"] = None
    diagnostics.validate_record(value)


def test_rejects_unredacted_payload_and_unsafe_frame() -> None:
    value = _record()
    value.update(
        kind="exception",
        event="exception",
        status="unknown",
        proofLayer="none",
        proofSha256=None,
    )
    value["exception"] = {
        "className": "ValueError",
        "message": "password=secret",
        "frames": [],
    }
    with pytest.raises(diagnostics.DiagnosticContractError, match="unredacted"):
        diagnostics.validate_record(value)
    value["exception"]["message"] = diagnostics.redact("password=secret")
    value["exception"]["frames"] = [
        {"file": "/Users/person/sensitive.py", "function": "foo", "line": 8}
    ]
    with pytest.raises(diagnostics.DiagnosticContractError, match="traceback"):
        diagnostics.validate_record(value)


def test_payload_bounds_nonfinite_and_cross_case_fields() -> None:
    value = _record()
    for bad in ("../../another-case", "/Users/private", "a" * 101):
        copy_record = copy.deepcopy(value)
        copy_record["identity"]["caseId"] = bad
        with pytest.raises(diagnostics.DiagnosticContractError):
            diagnostics.validate_record(copy_record)
    value["evidence"] = value["evidence"] * (diagnostics.MAX_EVIDENCE_REFS + 1)
    with pytest.raises(diagnostics.DiagnosticContractError, match="quota"):
        diagnostics.validate_record(value)
    value = _record()
    value["evidence"][0]["sizeBytes"] = 2**63
    with pytest.raises(diagnostics.DiagnosticContractError, match="size"):
        diagnostics.validate_record(value)


def test_redaction_is_bounded_and_idempotent_for_known_tokens() -> None:
    message = "temporary " + ("x" * 5000) + " password=secret"
    scrubbed = diagnostics.redact(message)
    assert len(scrubbed) <= diagnostics.MAX_MESSAGE_CHARS
    assert "password=secret" not in scrubbed
    assert diagnostics.redact(scrubbed) == scrubbed
    assert "abc123" not in diagnostics.redact("Authorization: Bearer abc123")
    assert "C:\\Users\\John\\secret.txt" not in diagnostics.redact(
        "C:\\Users\\John\\secret.txt"
    )


def test_unprintable_exception_is_safe() -> None:
    class HostileError(Exception):
        def __str__(self) -> str:
            raise RuntimeError("secret should not escape")

    assert (
        diagnostics.exception_details(HostileError())["message"]
        == "[unprintable exception]"
    )


def test_seventh_incident_map_marks_five_host_actions_but_zero_m4_receipts() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "docs/verification/issue-512-seventh-case-map.json"
    )
    incident = json.loads(path.read_text(encoding="utf-8"))
    assert incident["conductor"]["launchResult"] == "unknown-after-claim"
    assert incident["conductor"]["nativeRetryPermitted"] is False
    assert incident["macEvidenceNotMountedHere"] is True
    assert incident["signedM4ReceiptsPresent"] == 0
    assert incident["signedM4ReceiptsRequired"] == 4
    assert incident["strict312Acceptance"] == "not_run"
    actions = incident["stages"][0]["authenticatedNativeResults"]
    assert [item["nativeSequence"] for item in actions] == list(range(5))
    assert [item["action"] for item in actions] == [
        "construct",
        "save_reopen",
        "capture_pre",
        "queue_render",
        "start_render",
    ]
    assert incident["stages"][0]["firstAbsentNativeRequest"] == {
        "nativeSequence": 5,
        "action": "poll_render",
    }
    assert all(stage["signedM4Receipt"] is False for stage in incident["stages"])
