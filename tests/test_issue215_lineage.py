"""Native rebuilds recheck the exact host-approved revision proof pins."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

import pytest
import test_issue209_native as fixtures
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent.qualification_output_records_v2 import (
    AUTHORITY_REFERENCE_FIELDS,
    LANE,
    OutputConsistencyError,
    _canonical,
    _json_hash,
    _parse,
)


def _pin_file(root: Path, name: str, raw: bytes | None = None) -> dict[str, str]:
    return _pin_path(root / name, raw if raw is not None else name.encode())


def _pin_path(path: Path, raw: bytes) -> dict[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.chmod(0o400)
    return {"path": str(path), "sha256": native._hash(path.read_bytes())}


def _revised_context(
    context: dict[str, Any], preflight: dict[str, str], record: dict[str, Any]
) -> dict[str, Any]:
    result = copy.deepcopy(context)
    result["phase"] = "rebuild"
    result["hostSourceGraphSha256"] = native._hash(_canonical(record["sourceHashes"]))
    result["originalDocumentSha256"] = record["originalInputs"]["document"]["sha256"]
    result["originalDependenciesSha256"] = record["originalInputs"]["dependencies"][
        "sha256"
    ]
    result["executionDocumentSha256"] = record["executionInputs"]["document"]["sha256"]
    result["executionDependenciesSha256"] = record["executionInputs"]["dependencies"][
        "sha256"
    ]
    result["manifestSha256"] = record["manifest"]["sha256"]
    result["reportSha256"] = record["report"]["sha256"]
    result["preflightSha256"] = preflight["sha256"]
    binding = {
        "kind": "revised",
        "acceptedDecisionReceiptSha256": record["acceptedDecisionReceipt"]["sha256"],
        "revisionLedgerSha256": record["revisionLedger"]["sha256"],
        "proposalEvidenceSha256": record["evidence"]["sha256"],
        "revisedDocumentSha256": result["executionDocumentSha256"],
        "revisedDependenciesSha256": result["executionDependenciesSha256"],
        "revisedManifestSha256": result["manifestSha256"],
    }
    result["binding"] = binding
    projection = {
        key: value
        for key, value in result.items()
        if key not in AUTHORITY_REFERENCE_FIELDS | {"invocationId"}
    }
    projection["binding"] = binding
    binding["bindingSha256"] = _json_hash(projection)
    return result


def _revised_request(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    request, _ = fixtures._native_request(tmp_path, native.SYNTHETIC_PROFILE)
    root = tmp_path / "accepted-revision"
    root.mkdir()
    original_document = _pin_path(
        Path(request["inputs"]["originalDocumentPath"]), b"original document"
    )
    original_dependencies = _pin_path(
        Path(request["inputs"]["originalDependenciesPath"]), b"original deps"
    )
    execution_document = _pin_path(
        Path(request["inputs"]["executionDocumentPath"]), b"execution document"
    )
    execution_dependencies = _pin_path(
        Path(request["inputs"]["executionDependenciesPath"]), b"execution deps"
    )

    record: dict[str, Any] = {
        "schemaVersion": "qualification-output-revised-preflight/v1",
        "lane": LANE,
        "status": "prepared",
        "sourceHashes": {"qualification_output_proof_v2.py": "a" * 64},
        "proofSession": _pin_file(root, "proof-session.json"),
        "originalInputs": {
            "document": original_document,
            "dependencies": original_dependencies,
        },
        "baselineInputs": {
            "document": _pin_file(root, "baseline-document.json"),
            "dependencies": _pin_file(root, "baseline-dependencies.json"),
        },
        "executionInputs": {
            "document": execution_document,
            "dependencies": execution_dependencies,
        },
        "manifest": _pin_file(root, "manifest.json"),
        "report": _pin_file(root, "report.json"),
        "evidence": _pin_file(root, "evidence.json"),
        "proposal": _pin_file(root, "proposal.json"),
        "decision": {},
        "result": {},
        "revisionLedger": {},
        "acceptedDecisionReceipt": _pin_file(root, "accepted-receipt.json"),
        "proofFiles": {
            name: _pin_file(root, f"{name}.json")
            for name in native.REVISED_PREFLIGHT_REQUIRED_PROOF_FILES
        }
        | {name: None for name in native.REVISED_PREFLIGHT_OMISSION_PROOF_FILES},
    }
    record["decision"] = _pin_file(
        root, "decision.json", _canonical({"outcome": "accept"})
    )
    record["result"] = _pin_file(root, "result.json", _canonical({"outcome": "accept"}))
    ledger = {
        "schemaVersion": "qualification-output-revision-ledger/v1",
        "lane": LANE,
        "proofSessionSha256": record["proofSession"]["sha256"],
        "evidenceSha256": record["evidence"]["sha256"],
        "inferenceDecisionSha256": "1" * 64,
        "candidateSha256": record["proposal"]["sha256"],
        "decisionSha256": record["decision"]["sha256"],
        "resultSha256": record["result"]["sha256"],
        "outcome": "accept",
        "history": [],
    }
    record["revisionLedger"] = _pin_file(
        root, "revision-ledger.json", _canonical(ledger)
    )
    pins = [
        record["proofSession"],
        *record["originalInputs"].values(),
        *record["baselineInputs"].values(),
        *record["executionInputs"].values(),
        *(
            record[name]
            for name in (
                "manifest",
                "report",
                "evidence",
                "proposal",
                "decision",
                "result",
                "revisionLedger",
                "acceptedDecisionReceipt",
            )
        ),
        *(pin for pin in record["proofFiles"].values() if pin is not None),
    ]
    record["verifiedFiles"] = {pin["path"]: pin["sha256"] for pin in pins}
    receipt = _pin_file(root, "preflight-receipt.json")
    record["receipt"] = receipt

    preflight_path = root / "revised-preflight.json"
    preflight_raw = _canonical(record)
    preflight_path.write_bytes(preflight_raw)
    preflight_path.chmod(0o400)
    preflight_ref = {"path": str(preflight_path), "sha256": native._hash(preflight_raw)}
    request["context"] = _revised_context(request["context"], preflight_ref, record)
    request["revisedPreflight"] = preflight_ref
    for field, context_field, raw in (
        ("sourceGraph", "nativeSourceGraphSha256", b"native source graph"),
        ("release", "installedReleaseSha256", b"installed release"),
    ):
        pin = _pin_path(Path(request[field]["path"]), raw)
        request[field]["sha256"] = pin["sha256"]
        request["context"][context_field] = pin["sha256"]
    context = request["context"]
    projection = {
        key: value
        for key, value in context.items()
        if key not in AUTHORITY_REFERENCE_FIELDS | {"invocationId"}
    }
    projection["binding"] = {
        key: value
        for key, value in context["binding"].items()
        if key != "bindingSha256"
    }
    context["binding"]["bindingSha256"] = _json_hash(projection)
    return request, record


def test_revised_preflight_is_checked_before_native_rebuild(tmp_path: Path) -> None:
    request, _ = _revised_request(tmp_path)
    raw = _canonical(request)
    checked = native.verify_native_request(
        raw,
        expected_request_sha256=hashlib.sha256(raw).hexdigest(),
        current=True,
    )
    assert checked["revisedPreflight"] == request["revisedPreflight"]


@pytest.mark.parametrize(
    "pin_path",
    [
        "decision",
        "proofFiles.inferenceDecision",
        "originalInputs.document",
        "originalInputs.dependencies",
        "baselineInputs.dependencies",
    ],
)
def test_revised_preflight_refuses_stale_decision_or_required_input(
    tmp_path: Path, pin_path: str
) -> None:
    request, record = _revised_request(tmp_path)
    if "." in pin_path:
        group, name = pin_path.split(".")
        target = Path(record[group][name]["path"])
    else:
        target = Path(record[pin_path]["path"])
    target.chmod(0o600)
    target.write_bytes(b"changed after host verification")

    raw = _canonical(request)
    with pytest.raises(OutputConsistencyError):
        native.verify_native_request(
            raw,
            expected_request_sha256=hashlib.sha256(raw).hexdigest(),
            current=True,
        )


def test_revised_preflight_rejects_unknown_inventory_or_rebuild_request_fields(
    tmp_path: Path,
) -> None:
    request, _ = _revised_request(tmp_path)
    request["unexpected"] = True
    raw = _canonical(request)
    with pytest.raises(OutputConsistencyError, match="closed native request shape"):
        native.verify_native_request(
            raw,
            expected_request_sha256=hashlib.sha256(raw).hexdigest(),
            current=False,
        )


def test_revised_preflight_record_rejects_unknown_fields(tmp_path: Path) -> None:
    request, _ = _revised_request(tmp_path)
    preflight = Path(request["revisedPreflight"]["path"])
    record = _parse(preflight.read_bytes())
    record["unexpected"] = True
    preflight.chmod(0o600)
    raw = _canonical(record)
    preflight.write_bytes(raw)
    preflight.chmod(0o400)
    request["revisedPreflight"]["sha256"] = native._hash(raw)

    with pytest.raises(OutputConsistencyError, match="closed revised preflight shape"):
        native._verify_revised_preflight_currentness(request)


def test_revised_preflight_requires_all_or_no_omission_proof_pins(
    tmp_path: Path,
) -> None:
    request, _ = _revised_request(tmp_path)
    preflight = Path(request["revisedPreflight"]["path"])
    record = _parse(preflight.read_bytes())
    record["proofFiles"]["omissionSupport"] = {
        "path": str(tmp_path / "omission-support.json"),
        "sha256": "a" * 64,
    }
    preflight.chmod(0o600)
    raw = _canonical(record)
    preflight.write_bytes(raw)
    preflight.chmod(0o400)
    request["revisedPreflight"]["sha256"] = native._hash(raw)

    with pytest.raises(
        OutputConsistencyError,
        match="omission proof pins must be all present or all absent",
    ):
        native._verify_revised_preflight_currentness(request)


def test_revised_preflight_accepts_all_current_omission_proof_pins(
    tmp_path: Path,
) -> None:
    request, _ = _revised_request(tmp_path)
    preflight = Path(request["revisedPreflight"]["path"])
    record = _parse(preflight.read_bytes())
    for name in native.REVISED_PREFLIGHT_OMISSION_PROOF_FILES:
        pin = _pin_file(preflight.parent, f"{name}.json")
        record["proofFiles"][name] = pin
        record["verifiedFiles"][pin["path"]] = pin["sha256"]
    preflight.chmod(0o600)
    raw = _canonical(record)
    preflight.write_bytes(raw)
    preflight.chmod(0o400)
    request["revisedPreflight"]["sha256"] = native._hash(raw)

    native._verify_revised_preflight_currentness(request)


def test_revised_preflight_ref_is_required_only_for_revised_rebuild(
    tmp_path: Path,
) -> None:
    request, _ = _revised_request(tmp_path)
    request.pop("revisedPreflight")
    raw = _canonical(request)
    with pytest.raises(
        OutputConsistencyError, match="native request fields differ for context"
    ):
        native.verify_native_request(
            raw,
            expected_request_sha256=hashlib.sha256(raw).hexdigest(),
            current=False,
        )

    baseline, _ = fixtures._native_request(
        tmp_path / "baseline", native.SYNTHETIC_PROFILE
    )
    baseline["revisedPreflight"] = {
        "path": str(tmp_path / "missing.json"),
        "sha256": "0" * 64,
    }
    raw = _canonical(baseline)
    with pytest.raises(
        OutputConsistencyError, match="native request fields differ for context"
    ):
        native.verify_native_request(
            raw,
            expected_request_sha256=hashlib.sha256(raw).hexdigest(),
            current=False,
        )
