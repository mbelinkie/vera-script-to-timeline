"""Crash and fault tests for non-authoritative, one-use diagnostic logging."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import resolve_test_bench_diagnostic_journal as journal


@pytest.fixture
def private_root(tmp_path: Path) -> Path:
    root = tmp_path / "case"
    root.mkdir(mode=0o700)
    return root


def _writer(root: Path, *, case_id: str = "case12345") -> journal.DiagnosticJournal:
    return journal.DiagnosticJournal(
        root,
        case_id=case_id,
        phase="pristine",
        stage="pristine",
        pins={"frozenSourceSha256": "a" * 64},
    )


def _records(root: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text())
        for path in sorted((root / "diagnostics-v1" / "records").iterdir())
    ]


def test_immutable_chain_and_original_host_cursor(private_root: Path) -> None:
    writer = _writer(private_root)
    writer.emit("claim", "before_claim", status="pending")
    writer.emit("claim", "after_claim")
    writer.cursor(
        action="start_render",
        sequence=4,
        last_verified={
            "nativeSequence": 4,
            "action": "start_render",
            "resultSha256": "b" * 64,
        },
        next_pending={"nativeSequence": 5, "action": "poll_render"},
    )
    try:
        raise RuntimeError("Authorization: Bearer abc123 /Users/private/case")
    except RuntimeError as error:
        writer.emit("exception", "before_dispatch", exception=error)
    records = _records(private_root)
    assert [record["recordIndex"] for record in records] == [0, 1, 2]
    first = (writer.records / "record-000000.json").read_bytes()
    assert records[1]["previousRecordSha256"] == hashlib.sha256(first).hexdigest()
    assert records[2]["kind"] == "exception"
    assert records[2]["status"] == "unknown"
    assert records[2]["proofLayer"] == "none"
    assert records[2]["lastVerified"]["action"] == "start_render"
    assert records[2]["nextPending"]["action"] == "poll_render"
    assert b"abc123" not in (writer.records / "record-000002.json").read_bytes()
    assert b"/Users/private" not in (writer.records / "record-000002.json").read_bytes()
    assert os.stat(writer.records).st_mode & 0o077 == 0
    assert os.stat(writer.records / "record-000000.json").st_mode & 0o077 == 0


def test_two_writers_append_without_replacing(private_root: Path) -> None:
    a = _writer(private_root)
    b = _writer(private_root)
    a.emit("admission", "before_admission")
    original = (a.records / "record-000000.json").read_bytes()
    b.emit("preparation", "after_preparation")
    assert len(_records(private_root)) == 2
    assert (a.records / "record-000000.json").read_bytes() == original
    with pytest.raises(FileExistsError):
        os.open(
            a.records / "record-000000.json",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )


@pytest.mark.parametrize("fault", ["write", "fsync", "directory", "space"])
def test_faults_fail_closed_and_preserve_partial_evidence(
    private_root: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    writer = _writer(private_root)
    writer.emit("claim", "after_claim")
    original = (writer.records / "record-000000.json").read_bytes()
    original_write = os.write
    original_sync = os.fsync
    original_dir_sync = journal._sync_directory
    original_statvfs = os.statvfs

    def failing_write(fd: int, data: bytes) -> int:
        raise OSError("ENOSPC after claim")

    def failing_fsync(fd: int) -> None:
        raise OSError("EIO after claim")

    def failing_dir_sync(path: Path) -> None:
        if path == writer.records:
            raise OSError("directory fsync failed")
        original_dir_sync(path)

    if fault == "write":
        monkeypatch.setattr(os, "write", failing_write)
    elif fault == "fsync":
        monkeypatch.setattr(os, "fsync", failing_fsync)
    elif fault == "directory":
        monkeypatch.setattr(journal, "_sync_directory", failing_dir_sync)
    else:
        statfs = original_statvfs(private_root)

        class NoSpace:
            f_bavail = 0
            f_frsize = statfs.f_frsize

        monkeypatch.setattr(os, "statvfs", lambda _: NoSpace())
    try:
        with pytest.raises((OSError, journal.DiagnosticWriteError)):
            writer.emit("native_dispatch", "before_dispatch")
    finally:
        monkeypatch.setattr(os, "write", original_write)
        monkeypatch.setattr(os, "fsync", original_sync)
        monkeypatch.setattr(journal, "_sync_directory", original_dir_sync)
        monkeypatch.setattr(os, "statvfs", original_statvfs)
    assert (writer.records / "record-000000.json").read_bytes() == original
    if fault == "space":
        assert len(_records(private_root)) == 1
    else:
        # A failed incomplete write is NEVER repaired or reused as an ordinal.
        with pytest.raises(journal.DiagnosticWriteError):
            writer.emit("native_dispatch", "before_dispatch")


def test_symlink_foreign_case_and_torn_record_are_fail_closed(
    private_root: Path,
) -> None:
    writer = _writer(private_root)
    writer.emit("claim", "after_claim")
    with pytest.raises(journal.DiagnosticWriteError, match="chain/identity"):
        _writer(private_root, case_id="different_case").emit(
            "admission", "before_admission"
        )
    (writer.records / "record-000001.json").write_bytes(b"{broken")
    with pytest.raises(journal.DiagnosticWriteError):
        writer.emit("admission", "before_admission")
    assert (writer.records / "record-000001.json").read_bytes() == b"{broken"


def test_journal_rejects_symlink_and_extra_record(private_root: Path) -> None:
    writer = _writer(private_root)
    (writer.records / "extra.json").symlink_to(private_root / "missing")
    with pytest.raises(journal.DiagnosticWriteError):
        writer.emit("claim", "before_claim")
