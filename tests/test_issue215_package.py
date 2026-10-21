"""Revised package bytes stay bound to their proof pins and preserved originals."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_package_v2 as package
from vera_timeline_agent import qualification_output_proof_v2 as proof
from vera_timeline_agent.qualification_output_records_v2 import (
    OutputConsistencyError,
    _canonical,
)


def _pin(path: Path) -> dict[str, str]:
    return {"path": str(path), "sha256": package._hash_file(path)}


def _write(path: Path, raw: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def _pin_inputs(case: Any, root: Path) -> tuple[Path, dict[str, Any]]:
    original_document_raw = case.document_path.read_bytes() + b"\n"
    original_dependencies = json.loads(case.dependencies_path.read_bytes())
    original_dependencies["build"]["buildId"] = "issue215-original-build"
    original_dependencies_raw = _canonical(original_dependencies)
    original_document = _write(root / "original-document.json", original_document_raw)
    original_dependencies_path = _write(
        root / "original-dependencies.json", original_dependencies_raw
    )
    baseline_dependencies = _write(
        root / "baseline-dependencies.json", original_dependencies_raw
    )
    value: dict[str, Any] = {
        "schemaVersion": proof.PREFLIGHT_SCHEMA,
        "lane": "bounded_output_residual_consistency",
        "status": "prepared",
        "originalInputs": {
            "document": _pin(original_document),
            "dependencies": _pin(original_dependencies_path),
        },
        "baselineInputs": {
            "document": _pin(case.document_path),
            "dependencies": _pin(baseline_dependencies),
        },
        "executionInputs": {
            "document": _pin(case.document_path),
            "dependencies": _pin(case.dependencies_path),
        },
        "manifest": _pin(case.manifest_path),
        "report": _pin(case.report_path),
    }
    path = _write(root / "revised-preflight.json", _canonical(value))
    return path, value


def _install_package_verifier_seam(monkeypatch: pytest.MonkeyPatch) -> None:
    """Double only proof-chain verification; keep package verification real."""

    def verify(path: Path, expected_sha256: str) -> dict[str, Any]:
        raw = package._read(path)
        if package._sha(raw) != expected_sha256:
            raise OutputConsistencyError("revised preflight raw pin differs")
        value = package._json(raw, "test revised preflight")
        if (
            value.get("schemaVersion") != proof.PREFLIGHT_SCHEMA
            or value.get("status") != "prepared"
        ):
            raise OutputConsistencyError("revised preflight shape differs")
        return value

    monkeypatch.setattr(proof, "verify_revised_preflight_v2", verify)


def test_revision_package_seam_refuses_any_compiler_output_pin_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Check package bindings with only the proof-chain verifier seam doubled."""
    from issue177_package_fixture import make_package_case

    case = make_package_case(tmp_path / "public-source")
    case.build()
    preflight_path, preflight = _pin_inputs(case, tmp_path / "pins")
    _install_package_verifier_seam(monkeypatch)
    package_bytes = {
        "document": case.document_path.read_bytes(),
        "dependencies": case.dependencies_path.read_bytes(),
        "manifest": case.manifest_path.read_bytes(),
        "report": case.report_path.read_bytes(),
    }

    for index, (field, raw) in enumerate(package_bytes.items()):
        bad_preflight = copy.deepcopy(preflight)
        wrong_path = _write(tmp_path / f"wrong-{field}.json", raw + b" ")
        pin = _pin(wrong_path)
        if field in {"document", "dependencies"}:
            bad_preflight["executionInputs"][field] = pin
        else:
            bad_preflight[field] = pin
        bad_preflight_path = _write(
            tmp_path / f"bad-preflight-{index}.json", _canonical(bad_preflight)
        )
        output_root = tmp_path / f"refused-{index}"
        with pytest.raises(package.QualificationPackageError, match="preflight pins"):
            package.admit_qualification_revision_v2(
                output_root,
                package_root=case.project_root,
                preparation_paths=case.preparation_paths,
                revised_preflight_path=bad_preflight_path,
                revised_preflight_sha256=package._sha(bad_preflight_path.read_bytes()),
            )
        assert not output_root.exists()

    stale_baseline = copy.deepcopy(preflight)
    stale_baseline["baselineInputs"]["dependencies"] = _pin(case.dependencies_path)
    stale_baseline_path = _write(
        tmp_path / "stale-baseline-preflight.json", _canonical(stale_baseline)
    )
    with pytest.raises(
        package.QualificationPackageError, match="fresh from the baseline"
    ):
        package.admit_qualification_revision_v2(
            tmp_path / "stale-build-admission",
            package_root=case.project_root,
            preparation_paths=case.preparation_paths,
            revised_preflight_path=stale_baseline_path,
            revised_preflight_sha256=package._sha(stale_baseline_path.read_bytes()),
        )
    assert not (tmp_path / "stale-build-admission").exists()

    stale_original = copy.deepcopy(preflight)
    original_path = Path(stale_original["originalInputs"]["dependencies"]["path"])
    original_path.write_bytes(original_path.read_bytes() + b" ")
    stale_original_root = tmp_path / "stale-original"
    with pytest.raises(package.QualificationPackageError, match="dependencies"):
        package.admit_qualification_revision_v2(
            stale_original_root,
            package_root=case.project_root,
            preparation_paths=case.preparation_paths,
            revised_preflight_path=preflight_path,
            revised_preflight_sha256=package._sha(preflight_path.read_bytes()),
        )
    assert not stale_original_root.exists()

    stale_preflight = _write(
        tmp_path / "stale-preflight.json", preflight_path.read_bytes() + b" "
    )
    with pytest.raises(package.QualificationPackageError, match="raw pin"):
        package.admit_qualification_revision_v2(
            tmp_path / "stale-preflight-output",
            package_root=case.project_root,
            preparation_paths=case.preparation_paths,
            revised_preflight_path=stale_preflight,
            revised_preflight_sha256=package._sha(preflight_path.read_bytes()),
        )

    for field in ("document", "dependencies"):
        bad_original = copy.deepcopy(preflight)
        pin = bad_original["originalInputs"][field]
        source = Path(pin["path"])
        changed_path = _write(
            tmp_path / f"changed-original-{field}.json",
            source.read_bytes() + b" ",
        )
        pin["path"] = str(changed_path)
        bad_original_path = _write(
            tmp_path / f"bad-original-{field}-preflight.json",
            _canonical(bad_original),
        )
        bad_original_root = tmp_path / f"bad-original-{field}-output"
        with pytest.raises(package.QualificationPackageError, match="pin bytes differ"):
            package.admit_qualification_revision_v2(
                bad_original_root,
                package_root=case.project_root,
                preparation_paths=case.preparation_paths,
                revised_preflight_path=bad_original_path,
                revised_preflight_sha256=package._sha(bad_original_path.read_bytes()),
            )
        assert not bad_original_root.exists()


def test_admission_cache_keeps_original_and_execution_bytes_distinct(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "admission"
    root = output_root / "package"
    root.mkdir(parents=True)
    attestation_path = output_root / "attestation.json"
    attestation_path.write_bytes(b"test-only attestation")
    original_document = b'{"id":"original"}'
    original_dependencies = b'{"build":{"buildId":"original"}}'
    execution_document = _canonical({"id": "revised", "activeDraft": {"blocks": []}})
    execution_dependencies = b'{"build":{"buildId":"fresh"}}'
    original_document_path = _write(
        tmp_path / "original-document.json", original_document
    )
    original_dependencies_path = _write(
        tmp_path / "original-dependencies.json", original_dependencies
    )
    tracked_paths: dict[Path, tuple[int, int, int, int, int]] = {}
    tracked_hashes: dict[Path, str] = {}
    for path in (original_document_path, original_dependencies_path):
        package._track(path, tracked_paths, tracked_hashes)
    view: dict[str, Any] = {"sources": [], "events": []}
    report = {"diagnostics": [], "recoveryActions": []}
    report_raw = _canonical(report)

    admission = package._finish_admission(
        output_root,
        profile=package.MATRIX_PROFILE,
        disposition="verified_matrix_inputs",
        creative_qualification="unqualified_studio_matrix",
        original_document=original_document,
        original_dependencies=original_dependencies,
        execution_document=execution_document,
        execution_dependencies=execution_dependencies,
        manifest={"events": []},
        manifest_raw=b'{"events":[]}',
        report=report,
        report_raw=report_raw,
        compiler_runs=(b"{}", b"{}"),
        view=view,
        view_raw=_canonical(view),
        diagnostics=[],
        recoveries=[],
        preflight_raw=b"{}",
        preparation_raw=b"{}",
        source_entries=[],
        source_proofs={},
        source_wavs={},
        source_paths={},
        tracked_paths=tracked_paths,
        tracked_hashes=tracked_hashes,
        tracked_links={},
        proof_payloads={},
        attestation_path=attestation_path,
    )

    assert admission.blobs["originalDocumentSha256"] == original_document
    assert admission.blobs["originalDependenciesSha256"] == original_dependencies
    assert admission.blobs["executionDocumentSha256"] == execution_document
    assert admission.blobs["executionDependenciesSha256"] == execution_dependencies
    admission_path, digest = admission.serialize_native_admission()
    reopened = package.load_qualification_package_v2(admission_path, digest)
    assert reopened.blobs == admission.blobs
    assert original_document_path in reopened._tracked_paths
    assert original_dependencies_path in reopened._tracked_paths
