"""Native boundary admission for the current compiler Presenter fixture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent.qualification_output_records_v2 import (
    AUTHORITY_REFERENCE_FIELDS,
    CONTEXT_HASH_FIELDS,
    EMPTY_HEAD,
    LANE,
    OutputConsistencyError,
    _canonical,
    _json_hash,
)


def _context() -> dict[str, Any]:
    value: dict[str, Any] = {key: "a" * 64 for key in CONTEXT_HASH_FIELDS}
    value.update(
        {
            "lane": LANE,
            "invocationId": "issue250-invocation",
            "caseId": "issue250-presenter",
            "phase": "pristine",
            "target": {
                "projectUid": "project-one",
                "timelineUid": "timeline-one",
                "projectName": "disposable-project",
                "timelineName": "disposable-timeline",
            },
            "binding": {"kind": "baseline"},
        }
    )
    projection = {
        key: child
        for key, child in value.items()
        if key not in AUTHORITY_REFERENCE_FIELDS | {"invocationId"}
    }
    projection["binding"] = {"kind": "baseline"}
    value["binding"]["bindingSha256"] = _json_hash(projection)
    return value


def _native_request(tmp_path: Path) -> bytes:
    root = tmp_path.resolve() / "wrapper" / "package"
    operation = tmp_path.resolve() / "native" / "operations" / "00000000"
    operation.mkdir(parents=True)
    context = _context()
    request = {
        "schemaVersion": native.REQUEST_SCHEMA,
        "lane": LANE,
        "profile": native.PRESENTER_PROFILE,
        "action": "construct",
        "operationId": "issue250-operation",
        "sequence": 0,
        "priorResultSha256": EMPTY_HEAD,
        "context": context,
        "target": context["target"],
        "package": {
            "profile": native.PRESENTER_PROFILE,
            "packageRoot": str(root),
            "attestationPath": str(root.parent / "attestation.json"),
            "attestationSha256": "b" * 64,
            "admissionPath": str(
                root.parent / "qualification-output-package-admission.json"
            ),
            "admissionSha256": "c" * 64,
        },
        "inputs": {
            "originalDocumentPath": str(root / "Original/script-document-v2.json"),
            "originalDependenciesPath": str(
                root / "Original/compiler-dependencies-v2.json"
            ),
            "executionDocumentPath": str(root / "Execution/script-document-v2.json"),
            "executionDependenciesPath": str(
                root / "Execution/compiler-dependencies-v2.json"
            ),
        },
        "sourceGraph": {
            "path": str(tmp_path.resolve() / "source-graph.json"),
            "sha256": context["nativeSourceGraphSha256"],
        },
        "release": {
            "path": str(tmp_path.resolve() / "release.json"),
            "sha256": context["installedReleaseSha256"],
        },
        "releaseManifestSha256": "e" * 64,
        "renderIntent": None,
        "authority": {
            "path": str(tmp_path.resolve() / "authority.json"),
            "sha256": "f" * 64,
        },
        "intent": {"path": str(tmp_path.resolve() / "intent.json"), "sha256": "1" * 64},
        "reservation": None,
        "payload": {},
        "resultPath": str(operation / "result.json"),
    }
    return _canonical(request)


def _presenter_rows() -> tuple[dict[str, Any], dict[str, Any]]:
    warning = {
        "code": "TEMPORARY_PRESENTER_STILL",
        "entity": {
            "id": native.PRESENTER_SLOT_ID,
            "kind": "slot",
            "path": "presenterStill",
        },
        "evidence": {
            "kind": "details",
            "message": native.PRESENTER_WARNING_MESSAGE,
        },
        "id": native.PRESENTER_WARNING_ID,
        "message": native.PRESENTER_WARNING_MESSAGE,
        "recoveryActionKinds": ["REPLACE_TEMPORARY_PRESENTER"],
        "severity": "warning",
    }
    recovery = {
        "documentId": "current-presenter-document",
        "instruction": (
            "Replace the temporary still with an accepted presenter source when "
            "available."
        ),
        "kind": "REPLACE_TEMPORARY_PRESENTER",
        "slotId": native.PRESENTER_SLOT_ID,
    }
    return warning, recovery


def _presenter_admission() -> tuple[dict[str, Any], dict[str, Any]]:
    warning, recovery = _presenter_rows()
    admission = {
        "disposition": "qualification_only",
        "creativeQualification": "unqualified_temporary_presenter",
        "diagnostics": [warning],
        "recoveryActions": [recovery],
    }
    report = {"diagnostics": [warning], "recoveryActions": [recovery]}
    return admission, report


def test_current_presenter_profile_is_an_explicit_closed_native_profile(
    tmp_path: Path,
) -> None:
    assert native.PRESENTER_PROFILE == "qualification-output-current-presenter/v1"
    assert native.PRESENTER_PROFILE in native.PROFILES
    assert native.PRESENTER_PROFILE not in native.PUBLIC_PROFILES
    raw = _native_request(tmp_path)

    checked = native.verify_native_request(
        raw,
        expected_request_sha256=hashlib.sha256(raw).hexdigest(),
        current=False,
    )

    assert checked["profile"] == native.PRESENTER_PROFILE


def test_current_presenter_admission_requires_exact_hashed_report_rows() -> None:
    admission, report = _presenter_admission()
    native._verify_presenter_admission(admission, report, "current-presenter-document")

    admission["diagnostics"] = [{**admission["diagnostics"][0], "message": "forged"}]
    with pytest.raises(OutputConsistencyError, match="warning rows differ"):
        native._verify_presenter_admission(
            admission, report, "current-presenter-document"
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("creativeQualification", "qualified_synthetic_only", "qualification-only"),
        ("disposition", "verified_synthetic", "qualification-only"),
    ],
)
def test_current_presenter_admission_keeps_unqualified_labels(
    field: str, value: str, message: str
) -> None:
    admission, report = _presenter_admission()
    admission[field] = value

    with pytest.raises(OutputConsistencyError, match=message):
        native._verify_presenter_admission(
            admission, report, "current-presenter-document"
        )


def test_current_presenter_admission_requires_the_issue_owned_slot() -> None:
    admission, report = _presenter_admission()
    report["diagnostics"][0]["entity"]["id"] = "another-slot"
    admission["diagnostics"] = report["diagnostics"]
    report["recoveryActions"][0]["slotId"] = "another-slot"
    admission["recoveryActions"] = report["recoveryActions"]

    with pytest.raises(
        OutputConsistencyError, match="unexpected current Presenter warning"
    ):
        native._verify_presenter_admission(
            admission, report, "current-presenter-document"
        )


def test_current_presenter_recovery_uses_original_document_identity() -> None:
    admission, report = _presenter_admission()
    report["recoveryActions"][0]["documentId"] = "another-document"
    admission["recoveryActions"] = report["recoveryActions"]

    with pytest.raises(
        OutputConsistencyError, match="unexpected current Presenter recovery"
    ):
        native._verify_presenter_admission(
            admission, report, "current-presenter-document"
        )


def _presenter_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    execution_source_hash: str = "sha256:" + "4" * 64,
) -> tuple[Path, dict[str, Any], Path, dict[str, Any]]:
    root = tmp_path.resolve() / "package"
    compiler = root / "Compiler"
    delivery = root / "Delivery"
    originals = root / "Original"
    execution = root / "Execution"
    compiler.mkdir(parents=True)
    delivery.mkdir()
    originals.mkdir()
    execution.mkdir()
    original_document = _canonical({"document": "issue250-current-presenter"})
    original_dependencies_value: dict[str, Any] = {
        "compiler": {
            "profileHash": "sha256:" + "2" * 64,
            "sourceHash": "sha256:" + "3" * 64,
            "version": "compiler/v2",
        },
        "fixture": "issue250-current-presenter",
    }
    original_dependencies = _canonical(original_dependencies_value)
    execution_dependencies_value = {
        **original_dependencies_value,
        "compiler": {
            **original_dependencies_value["compiler"],
            "sourceHash": execution_source_hash,
        },
    }
    execution_dependencies = _canonical(execution_dependencies_value)
    (originals / "script-document-v2.json").write_bytes(original_document)
    (originals / "compiler-dependencies-v2.json").write_bytes(original_dependencies)
    (execution / "script-document-v2.json").write_bytes(original_document)
    execution_dependencies_path = execution / "compiler-dependencies-v2.json"
    execution_dependencies_path.write_bytes(execution_dependencies)
    pinned_originals = tmp_path.resolve() / "pinned-presenter-originals"
    pinned_originals.mkdir()
    (pinned_originals / "script-document-v2.json").write_bytes(original_document)
    (pinned_originals / "compiler-dependencies-v2.json").write_bytes(
        original_dependencies
    )
    presenter_originals = {
        "script-document-v2.json": hashlib.sha256(original_document).hexdigest(),
        "compiler-dependencies-v2.json": hashlib.sha256(
            original_dependencies
        ).hexdigest(),
    }
    monkeypatch.setattr(native, "_PRESENTER_INPUT_ROOT", pinned_originals)
    monkeypatch.setattr(native, "_PRESENTER_ORIGINALS", presenter_originals)
    timeline = {
        "startFrame": 0,
        "durationFrames": 10,
        "frameRate": {"numerator": 24000, "denominator": 1001},
        "width": 1920,
        "height": 1080,
        "audioSampleRate": 48000,
    }
    manifest_raw = _canonical(
        {
            "compiler": execution_dependencies_value["compiler"],
            "timeline": timeline,
            "tracks": [],
        }
    )
    view_raw = _canonical({"timeline": timeline, "tracks": []})
    (compiler / "timeline-manifest-v2.json").write_bytes(manifest_raw)
    (delivery / "delivery-view.json").write_bytes(view_raw)
    admission = {
        "profile": native.PRESENTER_PROFILE,
        "disposition": "qualification_only",
        "creativeQualification": "unqualified_temporary_presenter",
        "originalDocumentSha256": presenter_originals["script-document-v2.json"],
        "originalDependenciesSha256": presenter_originals[
            "compiler-dependencies-v2.json"
        ],
        "executionDocumentSha256": presenter_originals["script-document-v2.json"],
        "executionDependenciesSha256": hashlib.sha256(
            execution_dependencies
        ).hexdigest(),
        "manifestSha256": hashlib.sha256(manifest_raw).hexdigest(),
        "viewSha256": hashlib.sha256(view_raw).hexdigest(),
    }
    monkeypatch.setattr(native, "_verify_admission", lambda _request: admission)
    monkeypatch.setattr(
        native,
        "_verify_r16_original_currentness",
        lambda: pytest.fail("current Presenter must not use R16 private identities"),
    )
    request = {
        "profile": native.PRESENTER_PROFILE,
        "package": {"packageRoot": str(root)},
    }
    return root, admission, execution_dependencies_path, request


@pytest.mark.parametrize(
    "execution_source_hash", ["sha256:" + "3" * 64, "sha256:" + "4" * 64]
)
def test_current_presenter_admission_materializes_media_from_package_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    execution_source_hash: str,
) -> None:
    root, _admission, _execution_dependencies_path, request = _presenter_package(
        tmp_path, monkeypatch, execution_source_hash=execution_source_hash
    )

    checked = native._admission_profile(request)

    assert checked["sourceRoot"] == root


def test_current_presenter_execution_dependencies_change_only_source_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, admission, execution_dependencies_path, request = _presenter_package(
        tmp_path, monkeypatch
    )
    execution_dependencies_value = json.loads(execution_dependencies_path.read_bytes())
    execution_dependencies_value["fixture"] = "changed"
    execution_dependencies_raw = _canonical(execution_dependencies_value)
    execution_dependencies_path.write_bytes(execution_dependencies_raw)
    admission["executionDependenciesSha256"] = hashlib.sha256(
        execution_dependencies_raw
    ).hexdigest()

    with pytest.raises(
        OutputConsistencyError, match=r"changed beyond compiler\.sourceHash"
    ):
        native._admission_profile(request)


def test_output_prepare_cli_accepts_the_current_presenter_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import qualification_output_controller_v2 as controller
    from vera_timeline_agent.workflow_v2_cli import main

    captured: dict[str, Any] = {}

    def prepare(path: Path, **kwargs: Any) -> Path:
        captured.update(kwargs)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"session")
        (path.parent / "operator-plan.json").write_bytes(b"plan")
        return path

    monkeypatch.setattr(controller, "prepare_output_session", prepare)

    result = main(
        [
            "output-prepare",
            "--output",
            str(tmp_path / "session.json"),
            "--profile",
            native.PRESENTER_PROFILE,
            "--project-uid",
            "project-one",
            "--timeline-uid",
            "timeline-one",
            "--project-name",
            "disposable-project",
            "--timeline-name",
            "disposable-timeline",
            "--case-id",
            "issue250-presenter",
        ]
    )

    assert result == 0
    assert captured["profile"] == native.PRESENTER_PROFILE
    assert captured["package_root"] is None
