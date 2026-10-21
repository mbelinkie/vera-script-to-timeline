"""Public v2 packaging keeps only concrete temporary-presenter warnings."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from issue177_package_fixture import _refresh_document_closure, _write_json
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent import qualification_output_package_v2 as qualification_package
from vera_timeline_agent import v2_package
from vera_timeline_agent.qualification_output_records_v2 import (
    OutputConsistencyError,
    _canonical,
)

Json = dict[str, Any]
_COMPILER_FIXTURES = Path(__file__).parent / "data/authoring_v2/issue_173/compiler"
_TEMPORARY_STILL_REPORT = "presenter-still-fallback"


def _presenter_compiler_fixture() -> tuple[Json, Json, Json, Json]:
    raw_inputs = json.loads(
        (
            _COMPILER_FIXTURES / f"{_TEMPORARY_STILL_REPORT}.input.golden.json"
        ).read_text()
    )
    document = copy.deepcopy(raw_inputs["document"])
    dependencies = copy.deepcopy(raw_inputs["dependencies"])
    manifest = json.loads(
        (
            _COMPILER_FIXTURES / f"{_TEMPORARY_STILL_REPORT}.manifest.golden.json"
        ).read_text()
    )
    report = json.loads(
        (
            _COMPILER_FIXTURES / f"{_TEMPORARY_STILL_REPORT}.report.golden.json"
        ).read_text()
    )
    dependencies["timeline"] = copy.deepcopy(manifest["timeline"])
    report["timeline"] = copy.deepcopy(manifest["timeline"])
    manifest["tracks"] = copy.deepcopy(dependencies["tracks"])
    manifest["roles"] = copy.deepcopy(dependencies["roles"])
    manifest["authoringDefaults"] = copy.deepcopy(dependencies["authoringDefaults"])
    _refresh_document_closure(document, dependencies, manifest, report)
    return document, dependencies, manifest, report


def test_public_packager_accepts_the_real_compiler_temporary_still_warning() -> None:
    document, dependencies, manifest, report = _presenter_compiler_fixture()

    v2_package._validate_inputs(document, dependencies, manifest, report)


def test_native_matrix_admission_accepts_canonical_presenter_warning() -> None:
    document, _dependencies, manifest, report = _presenter_compiler_fixture()
    admission = {
        "diagnostics": copy.deepcopy(report["diagnostics"]),
        "recoveryActions": copy.deepcopy(report["recoveryActions"]),
    }

    native._verify_public_package_diagnostics(
        native.MATRIX_PROFILE, admission, document, manifest, report
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown-warning",
        "error",
        "admission-warning-mismatch",
        "admission-recovery-mismatch",
    ],
)
def test_native_matrix_admission_refuses_noncanonical_or_mismatched_warning_rows(
    mutation: str,
) -> None:
    document, _dependencies, manifest, report = _presenter_compiler_fixture()
    admission = {
        "diagnostics": copy.deepcopy(report["diagnostics"]),
        "recoveryActions": copy.deepcopy(report["recoveryActions"]),
    }
    if mutation == "unknown-warning":
        report["diagnostics"][0]["code"] = "OTHER_WARNING"
        admission["diagnostics"] = copy.deepcopy(report["diagnostics"])
    elif mutation == "error":
        report["diagnostics"][0]["severity"] = "error"
        admission["diagnostics"] = copy.deepcopy(report["diagnostics"])
    elif mutation == "admission-warning-mismatch":
        admission["diagnostics"][0]["message"] = "forged warning"
    elif mutation == "admission-recovery-mismatch":
        admission["recoveryActions"] = []

    with pytest.raises(OutputConsistencyError):
        native._verify_public_package_diagnostics(
            native.MATRIX_PROFILE, admission, document, manifest, report
        )


def test_native_synthetic_admission_keeps_empty_diagnostics_invariant() -> None:
    document, _dependencies, manifest, report = _presenter_compiler_fixture()
    admission = {
        "diagnostics": copy.deepcopy(report["diagnostics"]),
        "recoveryActions": copy.deepcopy(report["recoveryActions"]),
    }

    with pytest.raises(OutputConsistencyError, match="synthetic package diagnostics"):
        native._verify_public_package_diagnostics(
            native.SYNTHETIC_PROFILE, admission, document, manifest, report
        )


def test_matrix_cached_reopen_refuses_discarded_report_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document, dependencies, manifest, report = _presenter_compiler_fixture()
    output = tmp_path / "matrix-admission"
    package_root = output / "package"
    package_root.mkdir(parents=True)
    attestation_path = output / "attestation.json"
    attestation_path.write_bytes(b"#177 attestation")
    cache_root = tmp_path / "admission-cache"
    monkeypatch.setattr(qualification_package, "_ADMISSION_CACHE_ROOT", cache_root)
    monkeypatch.setattr(
        qualification_package, "_ADMISSION_CACHE_KEY", cache_root / "hmac-key"
    )
    view: Json = {"sources": [], "events": []}
    raw_empty = b"{}"
    qualification_package._finish_admission(
        output,
        profile=qualification_package.MATRIX_PROFILE,
        disposition="verified_matrix_inputs",
        creative_qualification="unqualified_studio_matrix",
        original_document=_canonical(document),
        original_dependencies=_canonical(dependencies),
        execution_document=_canonical(document),
        execution_dependencies=_canonical(dependencies),
        manifest=manifest,
        manifest_raw=_canonical(manifest),
        report=report,
        report_raw=_canonical(report),
        compiler_runs=(raw_empty, raw_empty),
        view=view,
        view_raw=_canonical(view),
        # Model an older sealed Matrix cache that dropped report diagnostics.
        diagnostics=[],
        recoveries=[],
        preflight_raw=raw_empty,
        preparation_raw=raw_empty,
        source_entries=[],
        source_proofs={},
        source_wavs={},
        source_paths={},
        tracked_paths={},
        tracked_hashes={},
        tracked_links={},
        proof_payloads={},
        attestation_path=attestation_path,
    )
    admission_path = output / "qualification-output-package-admission.json"

    with pytest.raises(
        qualification_package.QualificationPackageError,
        match="diagnostic rows differ from the full report",
    ):
        qualification_package.load_qualification_package_v2(
            admission_path, qualification_package._sha(admission_path.read_bytes())
        )


def test_public_packager_ignores_temporary_presenters_on_excluded_rows() -> None:
    document, dependencies, manifest, report = _presenter_compiler_fixture()
    excluded_block = copy.deepcopy(document["activeDraft"]["blocks"][0])
    excluded_block.update(
        {
            "id": "00000000-0000-4000-8000-000000000020",
            "orderKey": "b0",
            "text": "parked",
            "state": "excluded",
        }
    )
    excluded_block["tokens"] = [
        {
            "id": "00000000-0000-4000-8000-000000000021",
            "value": "parked",
            "startOffset": 0,
            "endOffset": 6,
        }
    ]
    sequence = excluded_block["primaryVisualSequence"]
    sequence["id"] = "00000000-0000-4000-8000-000000000022"
    sequence["slots"][0]["id"] = "00000000-0000-4000-8000-000000000023"
    document["activeDraft"]["blocks"].append(excluded_block)
    _refresh_document_closure(document, dependencies, manifest, report)

    v2_package._validate_inputs(document, dependencies, manifest, report)


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown-warning",
        "error",
        "missing-warning",
        "missing-still",
        "wrong-recovery-slot",
        "forged-diagnostic-id",
        "warning-on-recorded-choice",
    ],
)
def test_public_packager_refuses_noncanonical_or_unbacked_presenter_warnings(
    mutation: str,
) -> None:
    document, dependencies, manifest, report = _presenter_compiler_fixture()
    diagnostic = report["diagnostics"][0]
    if mutation == "unknown-warning":
        diagnostic["code"] = "OTHER_WARNING"
    elif mutation == "error":
        diagnostic["severity"] = "error"
    elif mutation == "missing-warning":
        report["diagnostics"] = []
    elif mutation == "missing-still":
        manifest["events"] = [
            event for event in manifest["events"] if event["kind"] != "placeholder"
        ]
    elif mutation == "wrong-recovery-slot":
        report["recoveryActions"][0]["slotId"] = "other-slot"
    elif mutation == "forged-diagnostic-id":
        diagnostic["id"] = "00000000-0000-5000-8000-000000000000"
    if mutation in {"missing-still", "warning-on-recorded-choice"}:
        if mutation == "warning-on-recorded-choice":
            slot = document["activeDraft"]["blocks"][0]["primaryVisualSequence"][
                "slots"
            ][0]
            slot["payload"]["presenterChoiceId"] = (
                "00000000-0000-4000-8000-000000000099"
            )
        _refresh_document_closure(document, dependencies, manifest, report)

    with pytest.raises(v2_package.V2PackageError):
        v2_package._validate_inputs(document, dependencies, manifest, report)


def test_package_verify_replay_retains_canonical_presenter_warning(
    tmp_path: Path,
) -> None:
    document, dependencies, manifest, report = _presenter_compiler_fixture()
    tmp_path = tmp_path.resolve()

    # The compiler fixture pins placeholder media and narration by content hash.
    # Use existing repository media for the package copy while leaving its
    # compiler warning and event semantics intact.
    narration_path = (
        Path(__file__).parents[1] / "fixtures/media/audio-ambient-bed.wav"
    ).resolve()
    narration_hash = "sha256:" + hashlib.sha256(narration_path.read_bytes()).hexdigest()
    for timing_map in dependencies.get("narrationTimingMaps", []):
        timing_map["audioHash"] = narration_hash
        if isinstance(timing_map.get("audio"), dict):
            timing_map["audio"]["audioHash"] = narration_hash
    for source in manifest["sources"]:
        narration = source.get("narrationAudio")
        if isinstance(narration, dict):
            narration["audioHash"] = narration_hash
    for event in manifest["events"]:
        if event["kind"] == "narration":
            event["provenance"]["originalSourceHash"] = narration_hash
            event["provenance"]["deliveredSourceHash"] = narration_hash
    _refresh_document_closure(document, dependencies, manifest, report)

    input_paths: dict[str, Path] = {}
    for name, value in (
        ("document", document),
        ("dependencies", dependencies),
        ("manifest", manifest),
        ("report", report),
    ):
        path = tmp_path / f"{name}.json"
        _write_json(path, value)
        input_paths[name] = path

    still_event = next(
        event for event in manifest["events"] if event["kind"] == "placeholder"
    )
    narration_source = next(
        source for source in manifest["sources"] if "narrationAudio" in source
    )
    still_path = (
        Path(__file__).parents[1] / "packages/contracts/src/assets/generic-torso-v1.svg"
    ).resolve()
    package_root = tmp_path / "public-package"
    v2_package.build_v2_package(
        input_paths["manifest"],
        input_paths["report"],
        input_paths["document"],
        input_paths["dependencies"],
        package_root,
        media_paths={
            f"event:{still_event['eventId']}": still_path,
            f"source:{narration_source['id']}": narration_path,
        },
        preparation_paths={},
    )

    verified = v2_package.verify_v2_package(package_root)
    report_path = (
        package_root
        / v2_package.BUILD_DIRECTORY
        / verified.build_id
        / v2_package.REPORT_FILENAME
    )
    packaged_report = json.loads(report_path.read_text())
    assert packaged_report["diagnostics"] == report["diagnostics"]
    assert packaged_report["recoveryActions"] == report["recoveryActions"]
