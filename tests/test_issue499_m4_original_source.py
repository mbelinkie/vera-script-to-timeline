"""No-Resolve, fail-closed M4 edited-original-source path adversarial tests.

All tests use injected SDK objects only; no consumed case or native effect.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import test_issue209_native as fake
import test_issue215_native as edited_fixture
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent import resolve_test_bench_edited_stage as edited
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent.qualification_output_records_v2 import (
    OutputConsistencyError,
    _canonical,
)


def test_original_imported_media_is_only_authorized_observed_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolve, request, admitted, clip, _ = fake._geometry_case(tmp_path)
    original = Path(admitted["sourceRoot"])
    edited_root = tmp_path / "new-edited-admission-copy"
    copied = edited_root / "media/shot.mov"
    copied.parent.mkdir(parents=True)
    copied.write_bytes((original / "media/shot.mov").read_bytes())
    outside = tmp_path / "untrusted-same-bytes.mov"
    outside.write_bytes(copied.read_bytes())
    request["profile"] = native.MATRIX_PROFILE
    request["context"]["caseId"] = "synthetic-312"
    request["context"] = edited_fixture._edited_context(request["context"])
    admitted["sourceRoot"] = edited_root

    def valid_original(
        _request: dict[str, Any], _admitted: dict[str, Any]
    ) -> dict[str, Any]:
        return {**_admitted, "sourceRoot": original}

    monkeypatch.setattr(native, "_m4_edited_original_source_admission", valid_original)
    original_result = native._capture_observed_geometry(
        resolve, request, admitted, None
    )
    assert original_result["items"]
    for wrong in (copied, outside):
        clip.media.path = wrong
        with pytest.raises(
            OutputConsistencyError, match="outside the admitted package"
        ):
            native._capture_observed_geometry(resolve, request, admitted, None)
    alias = tmp_path / "symlink-to-admitted.mov"
    alias.symlink_to(original / "media/shot.mov")
    clip.media.path = alias
    with pytest.raises(OutputConsistencyError, match="symlink"):
        native._capture_observed_geometry(resolve, request, admitted, None)
    clip.media.path = original / "media/shot.mov"
    clip.media.path.write_bytes(b"changed after verified original capture")
    with pytest.raises(
        OutputConsistencyError, match="native media source bytes differ"
    ):
        native._capture_observed_geometry(resolve, request, admitted, None)


def _origin_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Use real SQLite rows and exact pinned files in the synthetic sibling layout."""
    import sqlite3

    from vera_timeline_agent import workflow_v2 as workflow

    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    monkeypatch.setattr(native, "_context", lambda c: c)
    case = tmp_path / ".local/state/vera/issue-499-original-proof-unit"
    pristine_root = case / "pristine/admitted/package/PublicPackage"
    edited_root = case / "edited/admitted/package/PublicPackage"
    pristine_root.mkdir(parents=True, mode=0o700)
    edited_root.mkdir(parents=True, mode=0o700)
    job_id = "resolve-reverse-" + "1" * 32
    job_dir = case / "queue" / job_id
    job_dir.mkdir(parents=True, mode=0o700)
    target = {"projectUid": "first", "timelineUid": "second"}
    base_context: dict[str, Any] = {k: "pin" for k in edited._SESSION_CONTEXT_FIELDS}
    base_context.update(
        target=target,
        caseId="synthetic-312",
        phase="pristine",
        invocationId="old",
        binding={"kind": "baseline"},
    )
    edited_context = copy.deepcopy(base_context)
    edited_context.update(phase="edited", invocationId="new")
    manifest = {"timeline": {"durationFrames": 1407}}
    view = {
        "sources": [{"id": "source", "path": "media/clip.mov", "contentHash": "a" * 64}]
    }
    original_file = pristine_root / "media/clip.mov"
    original_file.parent.mkdir(parents=True)
    original_file.write_bytes(b"pristine original bytes")
    edited_file = edited_root / "media/clip.mov"
    edited_file.parent.mkdir(parents=True)
    edited_file.write_bytes(original_file.read_bytes())
    admission_meta = {
        "schemaVersion": "qualification-output-package-admission/v1",
        "profile": native.MATRIX_PROFILE,
        "manifestSha256": "b" * 64,
        "viewSha256": "c" * 64,
        "originalDocumentSha256": "d" * 64,
        "executionDocumentSha256": "e" * 64,
    }

    def write_pinned(
        path: Path, obj: dict[str, Any], *, m4_queue_record: bool = False
    ) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = queue.canonical(obj) if m4_queue_record else _canonical(obj)
        path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    pristine_admission = (
        case / "pristine/admitted/qualification-output-package-admission.json"
    )
    edited_admission = (
        case / "edited/admitted/qualification-output-package-admission.json"
    )
    pristine_admission_sha = write_pinned(pristine_admission, admission_meta)
    edited_admission_sha = write_pinned(edited_admission, admission_meta)
    pristine_session_path = case / "pristine/session.json"
    edited_session_path = case / "edited/session.json"

    def session(
        phase: str, ctx: dict[str, Any], admission_path: Path, admission_sha: str
    ) -> dict[str, Any]:
        return {
            "schemaVersion": "qualification-output-session/v1",
            "lane": "bounded_output_residual_consistency",
            "profile": native.MATRIX_PROFILE,
            "admissionPath": str(admission_path),
            "admissionSha256": admission_sha,
            "releaseRoot": str(case / phase / "release"),
            "context": ctx,
            "hostJournalRoot": str(tmp_path / "test-host-journal"),
        }

    pristine_sha = write_pinned(
        pristine_session_path,
        session("pristine", base_context, pristine_admission, pristine_admission_sha),
    )
    write_pinned(
        edited_session_path,
        session("edited", edited_context, edited_admission, edited_admission_sha),
    )
    baseline_ref = {"path": str(pristine_session_path), "sha256": pristine_sha}
    original_operation_id = "6cf08d56-0076-4d19-b6a9-56a339918397"
    capture_ref = {"path": str(case / "capture.json"), "sha256": "f" * 64}
    plan_sha = write_pinned(
        job_dir / "plan.json",
        {
            "schema": "vera.resolve-test-reverse-plan/v1",
            "caseId": "synthetic-312",
            "initialTarget": target,
            "baselineSession": baseline_ref,
        },
        m4_queue_record=True,
    )
    receipt = {
        "schema": "vera.resolve-test-reverse-receipt/v1",
        "stage": "pristine",
        "operationId": original_operation_id,
        "session": baseline_ref,
        "capture": capture_ref,
    }
    receipt_sha = write_pinned(
        job_dir / "receipt-pristine.json", receipt, m4_queue_record=True
    )
    db = sqlite3.connect(case / "queue/queue.sqlite3")
    try:
        db.execute("CREATE TABLE reverse_jobs (id TEXT PRIMARY KEY, plan_sha TEXT)")
        db.execute(
            "CREATE TABLE reverse_stages (job_id TEXT, ordinal INTEGER, "
            "name TEXT, state TEXT, operation_id TEXT, "
            "receipt_path TEXT, receipt_sha TEXT)"
        )
        db.execute("INSERT INTO reverse_jobs VALUES (?,?)", (job_id, plan_sha))
        db.execute(
            "INSERT INTO reverse_stages VALUES (?,?,?,?,?,?,?)",
            (
                job_id,
                0,
                "pristine",
                "verified",
                original_operation_id,
                str(job_dir / "receipt-pristine.json"),
                receipt_sha,
            ),
        )
        db.commit()
    finally:
        db.close()
    (case / "pristine/admitted/attestation.json").write_bytes(
        b"immutable synthetic public attestation\n"
    )
    monkeypatch.setattr(
        native,
        "verify_native_result",
        lambda _p, _h: {
            "status": "complete",
            "action": "capture_post",
            "context": base_context,
            "target": target,
            "nativeGeometry": {"items": [{"itemUid": "fixture"}]},
        },
    )
    monkeypatch.setattr(
        workflow,
        "load_verified_package_v2",
        lambda _path, _hash: SimpleNamespace(
            root=pristine_root, manifest=manifest, view=view
        ),
    )
    request = {
        "profile": native.MATRIX_PROFILE,
        "context": edited_context,
        "target": target,
    }
    admitted = {
        "sourceRoot": edited_root,
        "manifest": manifest,
        "view": view,
        "admission": admission_meta,
    }
    objects = {
        "caseRoot": case,
        "receipt": receipt,
        "receiptPath": job_dir / "receipt-pristine.json",
        "request": request,
        "admitted": admitted,
        "target": target,
        "originalRoot": pristine_root,
    }
    return request, admitted, objects


def test_original_m4_receipt_provenance_closed_source_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, admitted, objects = _origin_case(tmp_path, monkeypatch)
    actual = native._m4_edited_original_source_admission(request, admitted)
    assert actual["sourceRoot"] == objects["originalRoot"]
    assert admitted["sourceRoot"] != actual["sourceRoot"]
    assert native._admitted_media_path(actual, actual["view"]["sources"][0]).is_file()
    original_target = request["target"]
    request["target"] = {"projectUid": "forged", "timelineUid": "other"}
    with pytest.raises(OutputConsistencyError, match="original source is not bound"):
        native._m4_edited_original_source_admission(request, admitted)
    request["target"] = original_target
    forged_receipt = dict(objects["receipt"])
    forged_receipt["session"] = {
        "path": "/tmp/unapproved-session",
        "sha256": "0" * 64,
    }
    objects["receiptPath"].write_bytes(_canonical(forged_receipt))
    with pytest.raises(OutputConsistencyError, match="SHA256 differs"):
        native._m4_edited_original_source_admission(request, admitted)


@pytest.mark.parametrize("which", ["plan", "receipt"])
def test_m4_original_queue_requires_exact_canonical_newline_even_if_rehashed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, which: str
) -> None:
    import sqlite3

    request, admitted, objects = _origin_case(tmp_path, monkeypatch)
    receipt_path = objects["receiptPath"]
    plan_path = receipt_path.parent / "plan.json"
    path = plan_path if which == "plan" else receipt_path
    original = path.read_bytes()
    assert original.endswith(b"\n") and not original.endswith(b"\n\n")
    # Changing a signed SHA alone must never authorize a different JSON byte
    # encoding. The M4 queue emits exactly ONE trailing LF; output-host JSON
    # has no LF and is intentionally a different canonical format.
    changed = original[:-1] if which == "plan" else original + b"\n"
    path.write_bytes(changed)
    digest = hashlib.sha256(changed).hexdigest()
    db = sqlite3.connect(objects["caseRoot"] / "queue/queue.sqlite3")
    try:
        if which == "plan":
            db.execute("UPDATE reverse_jobs SET plan_sha=?", (digest,))
        else:
            db.execute("UPDATE reverse_stages SET receipt_sha=?", (digest,))
        db.commit()
    finally:
        db.close()
    label = "plan" if which == "plan" else "pristine receipt"
    with pytest.raises(
        OutputConsistencyError,
        match=f"M4 signed {label} must be canonical immutable JSON",
    ):
        native._m4_edited_original_source_admission(request, admitted)


def test_prior_media_root_rejects_symlink_and_outside_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, admitted, _objects = _origin_case(tmp_path, monkeypatch)
    path = Path(admitted["sourceRoot"])
    external = tmp_path / "external"
    external.mkdir()
    admitted["sourceRoot"] = external
    with pytest.raises(OutputConsistencyError, match="closed case layout"):
        native._m4_edited_original_source_admission(request, admitted)
    admitted["sourceRoot"] = path
    parent = path.parent
    swapped = parent.with_name("hidden-original")
    parent.rename(swapped)
    parent.symlink_to(swapped, target_is_directory=True)
    with pytest.raises(OutputConsistencyError, match="symlink"):
        native._m4_edited_original_source_admission(request, admitted)


def test_edited_source_verifier_runs_in_actual_installed_runtime_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reproduce the exact release package import boundary before any GUI Roll.

    Run the full M4 origin proof in a NEW child Python interpreter with only
    copies from the actual resolved output-release runtime closure. This catches
    host-only lazy imports that unit tests importing from the repo cannot catch.
    """
    import json
    import os
    import shutil
    import subprocess
    import sys

    from vera_timeline_agent import workflow_v2_cli as installed

    request, admitted, objects = _origin_case(tmp_path, monkeypatch)
    assert set(native._OUTPUT_RUNTIME_FILES) == set(installed.OUTPUT_RUNTIME_FILES)
    source = Path(__file__).resolve().parents[1] / "python/vera_timeline_agent"
    sandbox = tmp_path / "installed-closure-only"
    package = sandbox / "vera_timeline_agent"
    package.mkdir(parents=True)
    for name in installed.OUTPUT_RUNTIME_FILES:
        shutil.copyfile(source / name, package / name)
    input_path = tmp_path / "source-provenance-input.json"
    input_path.write_text(
        json.dumps(
            {
                "request": request,
                "admitted": {**admitted, "sourceRoot": str(admitted["sourceRoot"])},
            }
        )
    )
    script = r"""
import json, sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent import workflow_v2
x = json.loads(Path(sys.argv[2]).read_text())
request, admitted = x['request'], x['admitted']
admitted['sourceRoot'] = Path(admitted['sourceRoot'])
native._context = lambda context: context
pristine_context = dict(request['context'])
pristine_context.update(phase='pristine', invocationId='old')
native.verify_native_result = lambda _path,_digest: {
    'status':'complete', 'action':'capture_post',
    'context': pristine_context, 'target': request['target'],
    'nativeGeometry': {'items': [{'itemUid':'fixture'}]},
}
workflow_v2.load_verified_package_v2 = lambda _p,_d: SimpleNamespace(
    root=Path.home()/'.local/state/vera/issue-499-original-proof-unit/pristine/admitted/package/PublicPackage',
    manifest=admitted['manifest'], view=admitted['view'],
)
verified = native._m4_edited_original_source_admission(request, admitted)
expected = Path.home() / (
    '.local/state/vera/issue-499-original-proof-unit/'
    'pristine/admitted/package/PublicPackage'
)
assert verified['sourceRoot'] == expected
for forbidden in (
    'vera_timeline_agent.resolve_test_queue',
    'vera_timeline_agent.resolve_test_queue_m4',
    'vera_timeline_agent.resolve_test_bench_edited_stage',
    'vera_timeline_agent.qualification_output_controller_v2',
):
    assert forbidden not in sys.modules, forbidden
print('INSTALLED_CLOSURE_M4_PRISTINE_SOURCE_OK')
"""
    environment = dict(os.environ)
    environment["HOME"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(sandbox), str(input_path)],
        cwd=sandbox,
        env=environment,
        text=True,
        capture_output=True,
        timeout=25,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "INSTALLED_CLOSURE_M4_PRISTINE_SOURCE_OK" in result.stdout
    assert objects["originalRoot"].is_dir()
