"""Actual temporary filesystem attacks on new issue-owned record primitives."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from vera_timeline_agent import roundtrip_v2_records as records


@pytest.mark.parametrize(
    "raw",
    [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'{"x":9007199254740992}', b"[]"],
)
def test_untrusted_json_refuses(raw: bytes) -> None:
    with pytest.raises(records.ProofNativeError):
        records._parse(raw)


def test_immutable_records_reuse_exact_bytes_only(tmp_path: Path) -> None:
    path = tmp_path / "nested/record.json"
    records.publish_immutable_output(path, b'{"x":1}')
    records.publish_immutable_output(path, b'{"x":1}')
    with pytest.raises(records.ProofNativeError, match="ownership differs"):
        records.publish_immutable_output(path, b'{"x":2}')
    assert path.read_bytes() == b'{"x":1}'


def test_symlink_and_hardlink_inputs_and_outputs_refuse(tmp_path: Path) -> None:
    original = tmp_path / "original"
    original.write_bytes(b"immutable")
    link = tmp_path / "symbolic"
    link.symlink_to(original)
    with pytest.raises((OSError, records.ProofNativeError)):
        records._operator_bytes(link)
    with pytest.raises(records.ProofNativeError):
        records.publish_immutable_output(link, b"immutable")
    hard = tmp_path / "hard"
    os.link(original, hard)
    with pytest.raises(records.ProofNativeError):
        records._file_hash(original)


def test_opened_input_replacement_is_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "record"
    path.write_bytes(b"old")
    open_file = records._open_file

    def replace_after_open(subject: Path, flags: int, mode: int = 0o400) -> int:
        fd = open_file(subject, flags, mode)
        replacement = tmp_path / "replacement"
        replacement.write_bytes(b"new")
        replacement.replace(subject)
        return fd

    monkeypatch.setattr(records, "_open_file", replace_after_open)
    with pytest.raises(records.ProofNativeError, match="changed while read"):
        records._operator_bytes(path)


def test_pcm_read_retains_byte_identity_and_explicit_bound(tmp_path: Path) -> None:
    path = tmp_path / "pcm"
    path.write_bytes(bytes(9 * 1024 * 1024))
    with pytest.raises(records.ProofNativeError, match="bounded record"):
        records._operator_bytes(path)
    raw = records._operator_bytes(path, limit=64 * 1024 * 1024)
    assert records._digest(raw) == records._file_hash(path)
