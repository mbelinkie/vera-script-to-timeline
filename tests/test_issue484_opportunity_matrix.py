"""#484 versioned opportunity input: fake-only contract and safety regressions."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.issue484_opportunity_matrix import (
    MatrixError,
    read_matrix,
    validate_matrix,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/plans/resolve-21-2-new-capabilities-opportunities.json"


def baseline() -> dict[str, Any]:
    return copy.deepcopy(read_matrix(MATRIX, repo_root=ROOT))


def test_checked_in_matrix_all_probes_still_unexecuted() -> None:
    data = baseline()
    assert len(data["opportunities"]) >= 15
    assert {row["introduced"] for row in data["opportunities"]} == {
        "21.1.2",
        "21.2",
    }
    assert {row["rank"] for row in data["opportunities"]} == {
        "high-impact-near-term",
        "worth-testing",
        "defer",
        "unsupported",
    }
    assert all(
        row["nativeProbe"]["status"] == "NOT EXECUTED" for row in data["opportunities"]
    )
    assert all(not row["realNativeProven"] for row in data["opportunities"])


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("evidencePolicy", "noNativeExecution"), False),
        (("evidencePolicy", "noAutomaticInstallation"), False),
        (("evidencePolicy", "noPermissionPromotion"), False),
        (("opportunities", 0, "nativeProbe", "status"), "accepted"),
        (("opportunities", 0, "nativeProbe", "mustNotOperateExistingTargets"), False),
        (("opportunities", 0, "realNativeProven"), True),
        (("opportunities", 0, "productQualified"), True),
        (("opportunities", 0, "confidence"), "real native-proven"),
        (("opportunities", 0, "introduced"), "21.1.1"),
        (("opportunities", 0, "rank"), "ready-to-run"),
    ],
)
def test_proposed_native_execution_or_evidence_promotion_is_rejected(
    path: tuple[str | int, ...], value: object
) -> None:
    data = baseline()
    current: Any = data
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value
    with pytest.raises(MatrixError):
        validate_matrix(data, repo_root=ROOT)


def test_duplicate_row_or_missing_source_is_rejected() -> None:
    data = baseline()
    data["opportunities"].append(copy.deepcopy(data["opportunities"][0]))
    with pytest.raises(MatrixError, match="duplicate opportunity"):
        validate_matrix(data, repo_root=ROOT)

    data = baseline()
    data["opportunities"][0]["sourceIds"] = ["fabricated-source"]
    with pytest.raises(MatrixError):
        validate_matrix(data, repo_root=ROOT)


def test_malformed_evidence_policy_is_rejected() -> None:
    data = baseline()
    data["evidencePolicy"] = None
    with pytest.raises(MatrixError, match="missing evidence policy"):
        validate_matrix(data, repo_root=ROOT)


def test_no_unverified_vendor_hash_claims() -> None:
    data = baseline()
    data["sourceLedger"]["M1"]["sha256"] = "0" * 64
    with pytest.raises(MatrixError, match="unverified mirror"):
        validate_matrix(data, repo_root=ROOT)


@pytest.mark.parametrize(
    "reference",
    [
        "/tmp/native-project.drp",
        "../../README.md",
        ".pipeline/473/issue.md",
        "python/vera_timeline_agent/nonexistent_method.py",
    ],
)
def test_missing_or_unsafe_repo_code_reference_is_rejected(reference: str) -> None:
    data = baseline()
    data["opportunities"][0]["codeRefs"] = [reference]
    with pytest.raises(MatrixError):
        validate_matrix(data, repo_root=ROOT)


def test_duplicate_json_keys_are_rejected_before_validation(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.json"
    matrix.write_text(
        '{"schemaVersion": "v1", "schemaVersion": "v2"}', encoding="utf-8"
    )
    with pytest.raises(MatrixError, match="duplicate JSON key"):
        read_matrix(matrix, repo_root=ROOT)


def test_symlink_and_oversize_matrix_are_rejected(tmp_path: Path) -> None:
    link = tmp_path / "matrix-link.json"
    link.symlink_to(MATRIX)
    with pytest.raises(MatrixError, match="symlink"):
        read_matrix(link, repo_root=ROOT)

    big = tmp_path / "big.json"
    big.write_bytes(b" " * (1_000_000 + 1))
    with pytest.raises(MatrixError, match="bounded"):
        read_matrix(big, repo_root=ROOT)


def test_not_executable_manifest_even_with_newer_version_label() -> None:
    data = baseline()
    item = data["opportunities"][0]
    item["introduced"] = "21.2"
    assert (
        validate_matrix(data, repo_root=ROOT)["opportunities"][0]["realNativeProven"]
        is False
    )
    item["nativeProbe"]["status"] = "PASSED"
    with pytest.raises(MatrixError, match="NOT EXECUTED"):
        validate_matrix(data, repo_root=ROOT)


def test_offline_input_roundtrips_without_sdk_import(tmp_path: Path) -> None:
    data = baseline()
    output = tmp_path / "opportunities.json"
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    assert read_matrix(output, repo_root=ROOT) == data
