"""Receipt bytes bind identity but do not themselves prove an external effect."""

import hashlib
from pathlib import Path

import pytest

from vera_timeline_agent.build_jobs import BuildJobError, StageContext
from vera_timeline_agent.build_stage_receipt import (
    exact_receipt_matches, hash_file, read_receipt, receipt_bytes,
)


def context(tmp_path: Path) -> StageContext:
    return StageContext(
        project_id="p", job_id="j", snapshot_id="a" * 64,
        stage="compiling", stage_key=hashlib.sha256(b"p\0j\0compiling").hexdigest(),
        output_path=tmp_path / "output", attempt_id=2, lease_epoch=1,
        report_progress=lambda _: None, renew_lease=lambda: None,
    )


def evidence() -> dict:
    return dict(snapshot_sha256="a" * 64, adapter_id="compiler-v2",
                adapter_version="compiler.v2", input_hashes={"document": "b" * 64},
                output_hashes={"manifest": "c" * 64, "report": "d" * 64})


def test_canonical_receipt_is_revision_and_stage_bound(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    raw = receipt_bytes(ctx, **evidence())
    assert raw == receipt_bytes(ctx, **evidence())
    assert exact_receipt_matches(ctx, raw, **evidence())
    assert read_receipt(raw)["stageKey"] == ctx.stage_key
    assert not exact_receipt_matches(ctx, raw, **{**evidence(), "snapshot_sha256": "f" * 64})
    assert not exact_receipt_matches(ctx, raw, **{**evidence(), "output_hashes": {"manifest": "f" * 64}})
    with pytest.raises(BuildJobError, match="stage key"):
        receipt_bytes(ctx.__class__(**{**ctx.__dict__, "stage_key": "c" * 64}), **evidence())


def test_malformed_or_forged_receipt_is_refused(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    with pytest.raises(BuildJobError, match="SHA-256"):
        receipt_bytes(ctx, **{**evidence(), "snapshot_sha256": "not a digest"})
    with pytest.raises(BuildJobError, match="output hashes"):
        receipt_bytes(ctx, **{**evidence(), "output_hashes": {}})
    with pytest.raises(BuildJobError, match="invalid input hash label"):
        receipt_bytes(ctx, **{**evidence(), "input_hashes": {"../evil": "b" * 64}})
    raw = receipt_bytes(ctx, **evidence())
    with pytest.raises(BuildJobError, match="schema"):
        read_receipt(raw.replace(b'"schemaVersion"', b'"unapproved":0,"schemaVersion"'))
    with pytest.raises(BuildJobError, match="duplicate"):
        read_receipt(raw.replace(b'"projectId":"p"', b'"projectId":"p","projectId":"p"'))


def test_file_hash_rejects_symlinks_and_missing_bytes(tmp_path: Path) -> None:
    file = tmp_path / "source"
    file.write_bytes(b"abc")
    assert hash_file(file) == hashlib.sha256(b"abc").hexdigest()
    link = tmp_path / "link"
    link.symlink_to(file)
    with pytest.raises(BuildJobError, match="symlink"):
        hash_file(link)
    with pytest.raises(BuildJobError, match="missing"):
        hash_file(tmp_path / "missing")
