from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from vera_timeline_agent import package_cache
from vera_timeline_agent.package_cache import (
    FileStamp,
    PackageCache,
    SourceChangedError,
    clone_or_copy,
    default_cache_root,
    entry_key,
    source_stamp,
)


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _new_cache(tmp_path: Path) -> tuple[PackageCache, Path, Path, str]:
    source = tmp_path / "source.mov"
    staged = tmp_path / "staged.mov"
    source.write_bytes(b"some media")
    staged.write_bytes(source.read_bytes())
    return (
        PackageCache(tmp_path / "private-cache"),
        source,
        staged,
        _digest(b"some media"),
    )


def test_keys_cover_path_device_inode_size_mtime_and_expected_hash() -> None:
    source = Path("/example/source.mov")
    stamp = FileStamp(1, 2, 100, 123)
    digest = "sha256:" + "a" * 64
    first = entry_key(source, stamp, digest)
    assert first == entry_key(source, stamp, digest)
    for changed in (
        FileStamp(2, 2, 100, 123),
        FileStamp(1, 3, 100, 123),
        FileStamp(1, 2, 101, 123),
        FileStamp(1, 2, 100, 124),
    ):
        assert entry_key(source, changed, digest) != first
    assert entry_key(Path("/different/source.mov"), stamp, digest) != first
    assert entry_key(source, stamp, "sha256:" + "b" * 64) != first
    with pytest.raises(ValueError, match="expected hash"):
        entry_key(source, stamp, "not-a-hash")


def test_root_selection_all_platforms(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    home = Path("/home/editor")
    assert default_cache_root(platform_name="darwin", home=home) == (
        home / "Library/Caches/vera-script-to-timeline"
    )
    assert default_cache_root(platform_name="linux", home=home) == (
        home / ".cache/vera-script-to-timeline"
    )
    monkeypatch.setenv("XDG_CACHE_HOME", "/var/tmp/editor-cache")
    assert default_cache_root(platform_name="linux", home=home) == (
        Path("/var/tmp/editor-cache/vera-script-to-timeline")
    )
    assert default_cache_root(
        platform_name="linux", home=home, xdg_cache_home="relative"
    ) == (home / ".cache/vera-script-to-timeline")


def test_cold_publish_hit_and_independent_materialization(tmp_path: Path) -> None:
    cache, source, staged, expected = _new_cache(tmp_path)
    assert cache.lookup(source, expected) is None
    entry = cache.publish(source, expected, staged)
    assert entry is not None
    assert cache.root.stat().st_mode & 0o077 == 0
    assert entry.blob.stat().st_mode & 0o077 == 0
    assert entry.blob.stat().st_nlink == 1
    assert cache.lookup(source, expected) == entry
    dest = tmp_path / "package/media.mov"
    assert cache.materialize(entry, dest)
    assert dest.read_bytes() == staged.read_bytes()
    assert not dest.is_symlink()
    assert dest.stat().st_ino not in {entry.blob.stat().st_ino, source.stat().st_ino}
    dest.write_bytes(b"changed independently")
    assert entry.blob.read_bytes() == b"some media"
    assert source.read_bytes() == b"some media"


def test_same_size_mtime_edit_and_same_path_inode_swap_miss(tmp_path: Path) -> None:
    cache, source, staged, expected = _new_cache(tmp_path)
    first = cache.publish(source, expected, staged)
    assert first is not None
    old = source.stat()
    source.write_bytes(b"other data")  # exact same length
    os.utime(source, ns=(old.st_atime_ns, old.st_mtime_ns + 1_000_000))
    assert source.stat().st_size == old.st_size
    assert cache.lookup(source, expected) is None
    assert entry_key(source, source_stamp(source), expected) != first.key

    changed = source_stamp(source)
    swapped = tmp_path / "replacement"
    swapped.write_bytes(b"other data")
    os.utime(swapped, ns=(changed.mtime_ns, changed.mtime_ns))
    os.replace(swapped, source)
    assert source_stamp(source).inode != changed.inode
    assert cache.lookup(source, expected) is None
    assert entry_key(source, source_stamp(source), expected) != entry_key(
        source, changed, expected
    )


@pytest.mark.parametrize("tamper", ["json", "blob", "blob-link", "hardlink", "extra"])
def test_corrupt_or_unsafe_entries_are_cache_misses(
    tmp_path: Path, tamper: str
) -> None:
    cache, source, staged, expected = _new_cache(tmp_path)
    entry = cache.publish(source, expected, staged)
    assert entry is not None
    folder = entry.blob.parent
    if tamper == "json":
        (folder / "entry.json").write_text('{"version":999}')
    elif tamper == "blob":
        entry.blob.write_bytes(b"short")
    elif tamper == "blob-link":
        entry.blob.unlink()
        entry.blob.symlink_to(source)
    elif tamper == "hardlink":
        os.link(entry.blob, tmp_path / "other-hard-link")
    else:
        (folder / "extra").write_bytes(b"unknown")
    assert cache.lookup(source, expected) is None
    assert source.read_bytes() == b"some media"


def test_missing_unwritable_and_symlink_cache_are_nonfatal(tmp_path: Path) -> None:
    cache, source, staged, expected = _new_cache(tmp_path)
    assert not cache.root.exists()
    assert cache.lookup(source, expected) is None
    unsafe = tmp_path / "redirect"
    unsafe.symlink_to(tmp_path, target_is_directory=True)
    bad = PackageCache(unsafe / "nested")
    assert bad.lookup(source, expected) is None
    assert bad.publish(source, expected, staged) is None
    root = tmp_path / "public"
    root.mkdir(mode=0o777)
    root.chmod(0o777)
    public = PackageCache(root)
    assert public.publish(source, expected, staged) is None
    assert public.lookup(source, expected) is None
    # A file in place of the root is also an ordinary miss.
    file_root = tmp_path / "not-a-folder"
    file_root.write_bytes(b"file")
    assert PackageCache(file_root).publish(source, expected, staged) is None


def test_clone_success_fallback_and_partial_clone_fallback(tmp_path: Path) -> None:
    cache, source, staged, expected = _new_cache(tmp_path)
    entry = cache.publish(source, expected, staged)
    assert entry is not None
    called = 0

    def clone_success(source_fd: int, destination_fd: int) -> None:
        nonlocal called
        called += 1
        os.write(destination_fd, os.read(source_fd, 1024))

    cloned = tmp_path / "cloned.bin"
    assert cache.materialize(entry, cloned, clone=clone_success)
    assert called == 1
    assert cloned.read_bytes() == b"some media"

    def clone_partial_error(source_fd: int, destination_fd: int) -> None:
        os.write(destination_fd, b"partial")
        raise OSError("cross device or unsupported")

    fallback = tmp_path / "fallback.bin"
    assert cache.materialize(entry, fallback, clone=clone_partial_error)
    assert fallback.read_bytes() == b"some media"
    assert fallback.stat().st_nlink == 1
    assert fallback.stat().st_ino != entry.blob.stat().st_ino


def test_macos_fd_clone_and_unsupported_volume_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"mac clone sample")
    monkeypatch.setattr(package_cache.sys, "platform", "darwin")
    calls: list[Path] = []

    def fake_native_clone(fd: int, destination: Path) -> None:
        calls.append(destination)
        destination.write_bytes(os.read(fd, 1024))

    monkeypatch.setattr(package_cache, "_clone_macos", fake_native_clone)
    clone = tmp_path / "cloned.png"
    clone_or_copy(source, clone)
    assert calls == [clone]
    assert clone.read_bytes() == source.read_bytes()
    assert clone.stat().st_ino != source.stat().st_ino

    def unsupported(_fd: int, _destination: Path) -> None:
        raise OSError("unsupported volume")

    monkeypatch.setattr(package_cache, "_clone_macos", unsupported)
    copied = tmp_path / "copied.png"
    clone_or_copy(source, copied)
    assert copied.read_bytes() == source.read_bytes()
    assert copied.stat().st_nlink == 1


def test_source_is_never_symlink_or_changed_mid_copy(tmp_path: Path) -> None:
    cache, source, staged, expected = _new_cache(tmp_path)
    first = source_stamp(source)
    with pytest.raises(SourceChangedError, match="changed"):
        cache.publish(source, expected, staged, stamp=FileStamp(1, 2, 3, 4))
    entry = cache.publish(source, expected, staged, stamp=first)
    assert entry is not None
    link = tmp_path / "source-link"
    link.symlink_to(source)
    with pytest.raises(SourceChangedError, match="symbolic link"):
        cache.lookup(link, expected)

    def source_race(source_fd: int, destination_fd: int) -> None:
        os.write(destination_fd, os.read(source_fd, 1024))
        source.write_bytes(b"new content")

    dest = tmp_path / "racy-package"
    with pytest.raises(SourceChangedError, match="changed"):
        cache.materialize(entry, dest, clone=source_race)
    assert not dest.exists()
    assert cache.lookup(source, expected) is None


def test_publish_source_race_does_not_create_a_cache_entry(tmp_path: Path) -> None:
    cache, source, staged, expected = _new_cache(tmp_path)

    def mutate_while_cloning(source_fd: int, destination_fd: int) -> None:
        os.write(destination_fd, os.read(source_fd, 1024))
        source.write_bytes(b"new content")

    with pytest.raises(SourceChangedError, match="changed"):
        cache.publish(source, expected, staged, clone=mutate_while_cloning)
    assert cache.lookup(source, expected) is None
    assert list(cache.root.iterdir()) == []


def test_private_cache_does_not_trust_an_entry_directory_symlink(
    tmp_path: Path,
) -> None:
    cache, source, staged, expected = _new_cache(tmp_path)
    entry = cache.publish(source, expected, staged)
    assert entry is not None
    entry.blob.parent.rename(tmp_path / "moved-entry")
    entry.blob.parent.symlink_to(tmp_path / "moved-entry", target_is_directory=True)
    assert cache.lookup(source, expected) is None
    assert not cache.materialize(entry, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_atomic_private_publish_and_failure_does_not_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache, source, staged, expected = _new_cache(tmp_path)
    original = clone_or_copy

    def fail_copy(*args: object, **kwargs: object) -> None:
        raise OSError("simulated volume failure")

    monkeypatch.setattr("vera_timeline_agent.package_cache.clone_or_copy", fail_copy)
    assert cache.publish(source, expected, staged) is None
    assert cache.lookup(source, expected) is None
    assert list(cache.root.iterdir()) == []
    monkeypatch.setattr("vera_timeline_agent.package_cache.clone_or_copy", original)
    entry = cache.publish(source, expected, staged)
    assert entry is not None
    assert set(path.name for path in entry.blob.parent.iterdir()) == {
        "media.bin",
        "entry.json",
    }
    cache.discard(entry)
    assert cache.lookup(source, expected) is None


def test_plain_copy_rejects_linked_cache_source_and_existing_destination(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original"
    original.write_bytes(b"bytes")
    link = tmp_path / "linked"
    link.symlink_to(original)
    with pytest.raises(Exception, match="unsafe cache file"):
        clone_or_copy(link, tmp_path / "target")
    duplicate = tmp_path / "duplicate"
    os.link(original, duplicate)
    with pytest.raises(Exception, match="unsafe cache file"):
        clone_or_copy(original, tmp_path / "target")
    duplicate.unlink()
    dest = tmp_path / "target"
    dest.write_bytes(b"must survive")
    with pytest.raises(FileExistsError):
        clone_or_copy(original, dest)
    assert dest.read_bytes() == b"must survive"
