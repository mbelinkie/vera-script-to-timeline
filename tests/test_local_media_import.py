"""Synthetic real-filesystem / injected fault coverage for private #381 worker."""

from __future__ import annotations

import dataclasses
import errno
import hashlib
import json
import os
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

import pytest
from vera_timeline_agent import local_media_import as engine
from vera_timeline_agent.local_media_import import (
    import_local_media,
    reconcile_inspected_import,
)
from vera_timeline_agent.local_media_import_model import (
    ClipUse,
    DecodedMediaFacts,
    ImportModelError,
    LocalImportApproval,
    MediaKind,
)

CANARY = "PRIVATE_SOURCE_ROOT_CANARY"
DATA = b"\x89PNG\r\n\x1a\n" + b"synthetic single-frame bytes" * 32
VIDEO = b"synthetic-video-data" * 32


def _uuid(n: int) -> str:
    return str(uuid.UUID(int=n, version=4))


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


class FakeDecoder:
    def __init__(self, *, frames: int = 100) -> None:
        self.frames = frames
        self.calls = 0

    def decode(self, fd: int, kind: str) -> DecodedMediaFacts:
        self.calls += 1
        content = os.pread(fd, 65536, 0)
        if kind == "image" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("PRIVATE ROOT CANARY media is corrupt")
        if kind == "clip" and not content.startswith(b"synthetic-video"):
            raise ValueError("bad clip")
        return DecodedMediaFacts(
            kind=cast(MediaKind, kind),
            probe_hash=_sha(content + b"probe"),
            width=64,
            height=64,
            decoded_frame_count=self.frames if kind == "clip" else None,
        )


@pytest.fixture
def fixture(tmp_path: Path) -> tuple[LocalImportApproval, Path, Path, Path]:
    source_root = tmp_path / CANARY
    source_root.mkdir()
    (source_root / "good").mkdir()
    (source_root / "good" / "still.png").write_bytes(DATA)
    project = tmp_path / "project"
    project.mkdir()
    state = tmp_path / "PRIVATE_STATE_CANARY"
    state.mkdir(mode=0o700)
    approval = LocalImportApproval(
        project_id=_uuid(1),
        import_id=_uuid(2),
        asset_id=_uuid(3),
        media_reference_id=_uuid(4),
        source_root_id="trusted_operator",
        source_root=source_root,
        project_root=project,
        source_segments=("good", "still.png"),
        expected_content_hash=_sha(DATA),
        expected_size_bytes=len(DATA),
        max_size_bytes=100000,
        minimum_free_bytes=0,
        kind="image",
    )
    return approval, state, source_root / "good" / "still.png", project


def _run(
    approval: LocalImportApproval, state: Path, **kwargs: Any
) -> engine.ImportExecution:
    return import_local_media(
        approval,
        state_root=state,
        authorize=kwargs.pop("authorize", lambda _: True),
        decoder=kwargs.pop("decoder", FakeDecoder()),
        clone=kwargs.pop("clone", lambda _src, _dst: False),
        **kwargs,
    )


def _refuse(code: str, call: Any, *args: Any, **kwargs: Any) -> None:
    with pytest.raises(ImportModelError) as caught:
        call(*args, **kwargs)
    assert caught.value.code == code
    safe = json.dumps(caught.value.to_portable_dict())
    assert "CANARY" not in safe
    assert "/tmp/" not in safe


def _dest(approval: LocalImportApproval, project: Path) -> Path:
    return project / approval.project_relative_locator


def test_copy_success_private_receipt_and_idempotent_replay(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, source, project = fixture
    before = source.read_bytes()
    decoder = FakeDecoder()
    execution = _run(approval, state, decoder=decoder)
    assert execution.status == "completed"
    assert execution.result.completed_mode == "copy"
    target = _dest(approval, project)
    assert target.read_bytes() == before
    assert source.read_bytes() == before
    assert (source.stat().st_dev, source.stat().st_ino) != (
        target.stat().st_dev,
        target.stat().st_ino,
    )
    assert target.stat().st_nlink == 1
    portable = json.dumps(execution.to_portable_dict())
    assert CANARY not in portable and "sourceRoot" not in portable
    receipt = state / "receipts" / (approval.import_id + ".json")
    assert receipt.stat().st_mode & 0o077 == 0
    assert receipt.exists()
    assert "sourceSegments" not in receipt.read_text()
    assert CANARY not in receipt.read_text()
    attempt = state / "attempts" / (approval.import_id + ".json")
    assert attempt.stat().st_mode & 0o077 == 0
    assert "good" in attempt.read_text()
    old_inode = target.stat().st_ino
    old_receipt = receipt.read_bytes()
    repeated = _run(approval, state, decoder=decoder)
    assert repeated.status == "duplicate"
    assert repeated.result == execution.result
    assert target.stat().st_ino == old_inode
    assert receipt.read_bytes() == old_receipt
    assert decoder.calls == 2


def test_true_clone_injected_is_separately_verified_and_source_kept(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, source, project = fixture

    def fake_clone(src: int, dest: int) -> bool:
        os.write(dest, os.pread(src, len(DATA), 0))
        return True

    result = _run(approval, state, clone=fake_clone)
    assert result.result.completed_mode == "clone"
    assert _dest(approval, project).read_bytes() == DATA
    assert source.read_bytes() == DATA
    assert _dest(approval, project).stat().st_ino != source.stat().st_ino


def test_clone_unsupported_or_partial_falls_back_to_full_copy(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, _, project = fixture

    def unsupported(src: int, dest: int) -> bool:
        os.write(dest, b"garbagepartial")
        raise OSError(errno.EOPNOTSUPP, "clone unsupported")

    result = _run(approval, state, clone=unsupported)
    assert result.result.completed_mode == "copy"
    assert _dest(approval, project).read_bytes() == DATA


def test_no_untrusted_auto_approval_and_no_side_effect(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, source, project = fixture
    _refuse("approval_required", _run, None, state)
    for permission in (lambda _: False, lambda _: None):
        _refuse("permission_denied", _run, approval, state, authorize=permission)
    assert list(project.iterdir()) == []
    assert source.read_bytes() == DATA


def test_approval_exception_is_private_and_denied(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, _, _ = fixture

    def denied(_approval: LocalImportApproval) -> bool:
        raise RuntimeError(CANARY)

    _refuse("permission_denied", _run, approval, state, authorize=denied)


def test_wrong_hash_and_size_do_not_publish(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, source, project = fixture
    _refuse(
        "content_mismatch",
        _run,
        dataclasses.replace(approval, expected_content_hash=_sha(b"wrong")),
        state,
    )
    _refuse(
        "content_mismatch",
        _run,
        dataclasses.replace(approval, expected_size_bytes=len(DATA) - 1),
        state,
    )
    assert source.read_bytes() == DATA
    assert not _dest(approval, project).exists()


def test_size_quota_and_source_unchanged(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, source, project = fixture
    _refuse("size_limit", dataclasses.replace, approval, max_size_bytes=len(DATA) - 1)
    _refuse("insufficient_space", _run, approval, state, free_bytes=lambda _: 1)
    assert source.read_bytes() == DATA
    assert not _dest(approval, project).exists()


@pytest.mark.parametrize(
    "unsafe", ["file_symlink", "intermediate_symlink", "fifo", "missing", "directory"]
)
def test_unsafe_source_refused_without_reading_external(
    fixture: tuple[LocalImportApproval, Path, Path, Path], unsafe: str
) -> None:
    approval, state, source, project = fixture
    name = "unsafe.png"
    if unsafe == "file_symlink":
        (source.parent / name).symlink_to(source)
    elif unsafe == "intermediate_symlink":
        (approval.source_root / "linkdir").symlink_to(source.parent)
        approval = dataclasses.replace(
            approval, source_segments=("linkdir", "still.png")
        )
    elif unsafe == "fifo":
        os.mkfifo(source.parent / name)
    elif unsafe == "directory":
        (source.parent / name).mkdir()
    if unsafe != "intermediate_symlink":
        approval = dataclasses.replace(approval, source_segments=("good", name))
    _refuse(
        "source_unavailable" if unsafe == "missing" else "source_unsafe",
        _run,
        approval,
        state,
    )
    assert source.read_bytes() == DATA
    assert not _dest(approval, project).exists()


def test_unsafe_roots_and_overlaps_refused(
    fixture: tuple[LocalImportApproval, Path, Path, Path], tmp_path: Path
) -> None:
    approval, state, source, _ = fixture
    alias = tmp_path / "source_alias"
    alias.symlink_to(approval.source_root, target_is_directory=True)
    _refuse(
        "source_unsafe", _run, dataclasses.replace(approval, source_root=alias), state
    )
    nested = approval.source_root / "subproject"
    nested.mkdir()
    _refuse("root_overlap", dataclasses.replace, approval, project_root=nested)
    assert source.read_bytes() == DATA


def test_source_mutation_after_open_is_caught(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, source, project = fixture

    def source_mutated(_src: int, _dst: int) -> bool:
        source.write_bytes(b"changed while being copied")
        return False

    _refuse("source_changed", _run, approval, state, clone=source_mutated)
    assert not _dest(approval, project).exists()


def test_source_name_swapped_after_open_is_caught(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, source, project = fixture
    old = source.parent / "previous.png"

    def swapped(_src: int, _dst: int) -> bool:
        source.rename(old)
        source.write_bytes(DATA)
        return False

    _refuse("source_changed", _run, approval, state, clone=swapped)
    assert not _dest(approval, project).exists()
    assert old.read_bytes() == DATA


def test_decoder_and_clip_handle_refusal(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, source, project = fixture

    class Broken:
        def decode(self, fd: int, kind: str) -> DecodedMediaFacts:
            raise ValueError(CANARY)

    _refuse("undecodable_media", _run, approval, state, decoder=Broken())
    assert not _dest(approval, project).exists()
    assert source.read_bytes() == DATA

    (source.parent / "clip.mp4").write_bytes(VIDEO)
    clip = dataclasses.replace(
        approval,
        import_id=_uuid(21),
        asset_id=_uuid(22),
        media_reference_id=_uuid(23),
        source_segments=("good", "clip.mp4"),
        kind="clip",
        clip_use=ClipUse(5, 96, 5, 6),
        expected_content_hash=_sha(VIDEO),
        expected_size_bytes=len(VIDEO),
    )
    _refuse("invalid_bounds", _run, clip, state, decoder=FakeDecoder(frames=100))
    assert not _dest(clip, project).exists()
    assert (source.parent / "clip.mp4").read_bytes() == VIDEO


def test_same_id_different_approval_or_target_tamper_fails_closed(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, source, project = fixture
    _run(approval, state)
    _refuse(
        "import_conflict",
        _run,
        dataclasses.replace(approval, source_root_id="other"),
        state,
    )
    dest = _dest(approval, project)
    dest.write_bytes(b"tampered")
    _refuse("needs_inspection", _run, approval, state)
    assert dest.read_bytes() == b"tampered"
    assert source.read_bytes() == DATA


def test_same_bytes_replaced_inode_does_not_count_as_verified_replay(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, source, project = fixture
    _run(approval, state)
    target = _dest(approval, project)
    original_inode = target.stat().st_ino
    parked = target.with_suffix(".parked")
    target.rename(parked)
    target.write_bytes(DATA)
    target.chmod(0o600)
    assert target.stat().st_ino != original_inode
    _refuse("needs_inspection", _run, approval, state)
    assert target.read_bytes() == DATA
    assert source.read_bytes() == DATA


def test_target_symlink_collision_cannot_be_replaced(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, source, project = fixture
    dest = _dest(approval, project)
    dest.parent.mkdir(parents=True, mode=0o700)
    dest.symlink_to(source)
    with pytest.raises(ImportModelError) as caught:
        _run(approval, state)
    assert caught.value.code in ("publication_conflict", "source_unsafe")
    assert dest.is_symlink() and source.read_bytes() == DATA


def test_crash_before_publish_is_pending_and_never_auto_removed(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, source, project = fixture

    def crashed(_src: int, _dst: int) -> bool:
        raise RuntimeError("injected process loss")

    with pytest.raises(RuntimeError):
        _run(approval, state, clone=crashed)
    assert len(list(_dest(approval, project).parent.glob("*.partial"))) == 1
    _refuse("incomplete_attempt", _run, approval, state)
    _refuse(
        "needs_inspection",
        reconcile_inspected_import,
        approval,
        state_root=state,
        authorize=lambda _: True,
        decoder=FakeDecoder(),
    )
    assert source.read_bytes() == DATA


def test_crash_after_publish_requires_inspected_reconcile(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approval, state, source, project = fixture
    original = engine._write_once

    def crash_receipt(parent: int, name: str, data: dict[str, object]) -> None:
        if name == approval.import_id + ".json" and "result" in data:
            raise RuntimeError("crash after publish")
        original(parent, name, data)

    with monkeypatch.context() as patch:
        patch.setattr(engine, "_write_once", crash_receipt)
        with pytest.raises(RuntimeError):
            _run(approval, state)
    assert _dest(approval, project).read_bytes() == DATA
    _refuse("incomplete_attempt", _run, approval, state)
    recovered = reconcile_inspected_import(
        approval, state_root=state, authorize=lambda _: True, decoder=FakeDecoder()
    )
    assert recovered.status == "recovered"
    assert _run(approval, state).status == "duplicate"
    assert source.read_bytes() == DATA


def test_reconcile_refuses_replaced_published_bytes(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approval, state, source, project = fixture
    original = engine._write_once

    def crash_receipt(parent: int, name: str, data: dict[str, object]) -> None:
        if "result" in data:
            raise RuntimeError("simulated")
        original(parent, name, data)

    with monkeypatch.context() as patch:
        patch.setattr(engine, "_write_once", crash_receipt)
        with pytest.raises(RuntimeError):
            _run(approval, state)
    _dest(approval, project).write_bytes(b"wrong")
    _refuse(
        "needs_inspection",
        reconcile_inspected_import,
        approval,
        state_root=state,
        authorize=lambda _: True,
        decoder=FakeDecoder(),
    )
    assert not (state / "receipts" / (approval.import_id + ".json")).exists()
    assert source.read_bytes() == DATA


def test_reconcile_refuses_target_changed_while_decoding(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approval, state, source, project = fixture
    original = engine._write_once

    def crash_receipt(parent: int, name: str, data: dict[str, object]) -> None:
        if "result" in data:
            raise RuntimeError("injected crash after publish")
        original(parent, name, data)

    with monkeypatch.context() as patch:
        patch.setattr(engine, "_write_once", crash_receipt)
        with pytest.raises(RuntimeError):
            _run(approval, state)
    target = _dest(approval, project)

    class MutatingDecoder(FakeDecoder):
        def decode(self, fd: int, kind: str) -> DecodedMediaFacts:
            facts = super().decode(fd, kind)
            target.write_bytes(b"same initially, changed after decoding")
            return facts

    _refuse(
        "needs_inspection",
        reconcile_inspected_import,
        approval,
        state_root=state,
        authorize=lambda _: True,
        decoder=MutatingDecoder(),
    )
    assert not (state / "receipts" / (approval.import_id + ".json")).exists()
    assert source.read_bytes() == DATA


def test_concurrent_same_id_publishes_once(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, source, project = fixture
    gate = threading.Barrier(2)

    def task() -> str:
        gate.wait(timeout=5)
        return _run(approval, state).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(task)
        b = pool.submit(task)
        assert {a.result(timeout=10), b.result(timeout=10)} == {
            "completed",
            "duplicate",
        }
    assert _dest(approval, project).read_bytes() == DATA
    assert source.read_bytes() == DATA
    assert len(list((state / "receipts").glob("*.json"))) == 1


def test_distinct_import_id_cannot_overwrite_same_asset(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, source, project = fixture
    _run(approval, state)
    rival = dataclasses.replace(approval, import_id=_uuid(20))
    _refuse("publication_conflict", _run, rival, state)
    assert _dest(approval, project).read_bytes() == DATA
    assert source.read_bytes() == DATA


def test_ffmpeg_decoder_rejects_unrecognized_magic_without_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "unknown"
    data.write_bytes(b"#EXTM3U\nhttp://private.example/secret")

    def no_subprocess(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("unrecognized format must not invoke a tool")

    monkeypatch.setattr(subprocess, "run", no_subprocess)
    fd = os.open(data, os.O_RDONLY)
    try:
        _refuse("unsupported_media", engine.FFmpegDecoder().decode, fd, "clip")
    finally:
        os.close(fd)


def test_ffmpeg_decoder_checks_full_frame_count_and_private_fd_only(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, source, _ = fixture
    commands: list[list[str]] = []

    def synthetic_decoder(
        args: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        assert "pass_fds" in kwargs and len(kwargs["pass_fds"]) == 1
        assert "shell" not in kwargs
        assert "-protocol_whitelist" in args
        assert "file,pipe" in args
        assert "-f" in args and "image2pipe" in args
        assert "-timeout" not in args
        if args[0] == "ffprobe":
            assert "-count_frames" in args and "-select_streams" in args
            output = json.dumps(
                {
                    "streams": [
                        {
                            "codec_type": "video",
                            "codec_name": "png",
                            "width": 64,
                            "height": 64,
                            "nb_read_frames": "1",
                        }
                    ]
                }
            )
        else:
            assert "-frames:v" in args and "-progress" in args
            output = "frame=1\nprogress=end\n"
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr(subprocess, "run", synthetic_decoder)
    fd = os.open(source, os.O_RDONLY)
    try:
        facts = engine.FFmpegDecoder().decode(fd, "image")
        assert facts.width == facts.height == 64
        assert facts.decoded_frame_count is None
        assert facts.probe_hash.startswith("sha256:")
    finally:
        os.close(fd)
    assert len(commands) == 2
    assert str(source) not in str(commands)


def test_ffmpeg_decoder_refuses_incomplete_decode(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, source, _ = fixture

    def incomplete(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        stdout = (
            '{"streams":[{"codec_type":"video","codec_name":"png",'
            '"width":64,"height":64,"nb_read_frames":"1"}]}'
            if args[0] == "ffprobe"
            else "frame=0\nprogress=end\n"
        )
        return subprocess.CompletedProcess(args, 0, stdout, "")

    monkeypatch.setattr(subprocess, "run", incomplete)
    fd = os.open(source, os.O_RDONLY)
    try:
        _refuse("undecodable_media", engine.FFmpegDecoder().decode, fd, "image")
    finally:
        os.close(fd)


def test_no_overwrite_if_concurrent_file_appears_during_copy(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, source, project = fixture
    target = _dest(approval, project)

    def competing_writer(_src: int, _dst: int) -> bool:
        target.write_bytes(b"other import's bytes")
        return False

    _refuse("publication_conflict", _run, approval, state, clone=competing_writer)
    assert target.read_bytes() == b"other import's bytes"
    assert source.read_bytes() == DATA


def test_replay_rechecks_current_permission(
    fixture: tuple[LocalImportApproval, Path, Path, Path],
) -> None:
    approval, state, _, project = fixture
    _run(approval, state)
    _refuse("permission_denied", _run, approval, state, authorize=lambda _: False)
    assert _dest(approval, project).read_bytes() == DATA
