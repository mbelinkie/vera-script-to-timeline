"""Disposable, non-authoritative copies of verified v2 package inputs.

The caller must independently verify packaged bytes. A metadata hit avoids
reading *source* bytes, not the final package verification. All cache I/O is
best effort; source identity failures are never best effort.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CACHE_NAME = "vera-script-to-timeline"
CACHE_FORMAT = 1
_BLOB = "media.bin"
_RECORD = "entry.json"
_COPY_SIZE = 1024 * 1024

Clone = Callable[[int, int], None]


class SourceChangedError(RuntimeError):
    """A supplied input is unsafe or changed during a cache operation."""


class _CacheMiss(Exception):
    """Unsafe, unavailable or stale cache material (never a source refusal)."""


@dataclass(frozen=True)
class FileStamp:
    device: int
    inode: int
    size: int
    mtime_ns: int

    @classmethod
    def from_stat(cls, value: os.stat_result) -> FileStamp:
        return cls(value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)

    def as_list(self) -> list[int]:
        return [self.device, self.inode, self.size, self.mtime_ns]


def default_cache_root(
    *,
    platform_name: str | None = None,
    home: Path | None = None,
    xdg_cache_home: str | None = None,
) -> Path:
    """Select the documented user-cache location, independent of the output."""
    platform_name = sys.platform if platform_name is None else platform_name
    home = Path.home() if home is None else home
    if platform_name == "darwin":
        return home / "Library" / "Caches" / CACHE_NAME
    xdg_cache_home = (
        os.environ.get("XDG_CACHE_HOME") if xdg_cache_home is None else xdg_cache_home
    )
    base = Path(xdg_cache_home) if xdg_cache_home else home / ".cache"
    if not base.is_absolute():
        base = home / ".cache"
    return base / CACHE_NAME


def _expected_hash(value: str) -> None:
    if (
        len(value) != 71
        or not value.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in value[7:])
    ):
        raise ValueError("expected hash must be lowercase sha256:<64 hex digits>")


def entry_key(source: Path, stamp: FileStamp, expected_hash: str) -> str:
    _expected_hash(expected_hash)
    identity = [CACHE_FORMAT, str(source.absolute()), *stamp.as_list(), expected_hash]
    data = json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def _no_symlink_components(path: Path) -> None:
    for component in (path.absolute(), *path.absolute().parents):
        if component.is_symlink():
            raise SourceChangedError(
                f"supplied media contains a symbolic link: {component}"
            )


def source_stamp(source: Path) -> FileStamp:
    """Refuse original symlinks and nonregular inputs even on a warm hit."""
    try:
        _no_symlink_components(source)
        details = source.stat(follow_symlinks=False)
    except OSError as error:
        raise SourceChangedError(
            f"cannot inspect supplied media {source}: {error}"
        ) from error
    if not stat.S_ISREG(details.st_mode):
        raise SourceChangedError(f"supplied media must be a regular file: {source}")
    return FileStamp.from_stat(details)


def _same_source(source: Path, stamp: FileStamp) -> None:
    if source_stamp(source) != stamp:
        raise SourceChangedError(f"supplied media changed during cache use: {source}")


def _private_root(root: Path, *, create: bool) -> bool:
    """A missing/unusable cache never becomes a build error."""
    try:
        for component in (root.absolute(), *root.absolute().parents):
            if component.is_symlink():
                return False
        if create:
            root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = root.stat(follow_symlinks=False)
        return (
            stat.S_ISDIR(info.st_mode)
            and not bool(stat.S_IMODE(info.st_mode) & 0o077)
            and info.st_uid == os.getuid()
        )
    except OSError:
        return False


def _regular_cache_file(path: Path) -> os.stat_result:
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise _CacheMiss(f"unsafe cache file: {path}")
    return info


def _read_record(path: Path) -> Any:
    info = _regular_cache_file(path)
    if info.st_size > 4096:
        raise _CacheMiss("oversized cache metadata")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        if FileStamp.from_stat(opened) != FileStamp.from_stat(info):
            raise _CacheMiss("cache metadata replaced while opening")
        with os.fdopen(fd, "rb", closefd=False) as reader:
            content = reader.read(4097)
        if len(content) > 4096:
            raise _CacheMiss("oversized cache metadata")
        return json.loads(content)
    finally:
        os.close(fd)


@dataclass(frozen=True)
class CacheEntry:
    source: Path
    stamp: FileStamp
    expected_hash: str
    key: str
    blob: Path
    blob_stamp: FileStamp


def _record(
    source: Path, stamp: FileStamp, expected_hash: str, key: str
) -> dict[str, Any]:
    return {
        "version": CACHE_FORMAT,
        "key": key,
        "source": str(source.absolute()),
        "stamp": stamp.as_list(),
        "hash": expected_hash,
    }


def _clone_linux(source_fd: int, target_fd: int) -> None:
    import fcntl

    fcntl.ioctl(target_fd, 0x40049409, source_fd)  # FICLONE; otherwise plain copy


def clone_or_copy(
    source: Path,
    destination: Path,
    *,
    clone: Clone | None = None,
    private: bool = False,
) -> None:
    """Create an independent file using CoW if supported, never a link.

    clone is fd-based so tests can simulate success, unsupported volumes and
    partial-copy errors. The macOS path clonefile variant is used when present.
    """
    before = _regular_cache_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    created = False
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    src_fd = os.open(source, flags)
    try:
        if FileStamp.from_stat(os.fstat(src_fd)) != FileStamp.from_stat(before):
            raise _CacheMiss("cache blob changed before opening")
        # clonefile creates its destination itself, unlike Linux FICLONE.
        mac_clone = getattr(os, "clonefile", None)
        cloned = False
        if clone is None and sys.platform == "darwin" and callable(mac_clone):
            try:
                mac_clone(source, destination)
                created = True
                cloned = True
            except OSError:
                if destination.is_file() and not destination.is_symlink():
                    destination.unlink()
                elif destination.is_symlink():
                    destination.unlink()
                    raise _CacheMiss("clone created a symbolic link") from None
        if not cloned:
            dst_fd = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600 if private else 0o666,
            )
            created = True
            try:
                operation = (
                    clone
                    if clone is not None
                    else (_clone_linux if sys.platform == "linux" else None)
                )
                if operation is not None:
                    try:
                        operation(src_fd, dst_fd)
                        cloned = True
                    except OSError:
                        os.ftruncate(dst_fd, 0)
                        os.lseek(dst_fd, 0, os.SEEK_SET)
                if not cloned:
                    os.lseek(src_fd, 0, os.SEEK_SET)
                    with (
                        os.fdopen(src_fd, "rb", closefd=False) as reader,
                        os.fdopen(dst_fd, "wb", closefd=False) as writer,
                    ):
                        shutil.copyfileobj(reader, writer, _COPY_SIZE)
                        writer.flush()
                os.fsync(dst_fd)
            finally:
                os.close(dst_fd)
        else:
            with destination.open("rb") as dst:
                os.fsync(dst.fileno())
        if private:
            # macOS clonefile inherits the source's mode; cache files do not.
            destination.chmod(0o600)
        after = os.fstat(src_fd)
        now = source.stat(follow_symlinks=False)
        if FileStamp.from_stat(after) != FileStamp.from_stat(
            before
        ) or FileStamp.from_stat(now) != FileStamp.from_stat(before):
            raise _CacheMiss("cache input changed during clone or copy")
        target = _regular_cache_file(destination)
        if target.st_size != before.st_size or (
            target.st_dev,
            target.st_ino,
        ) == (before.st_dev, before.st_ino):
            raise _CacheMiss("cached copy is linked to source or has wrong size")
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise
    finally:
        os.close(src_fd)


class PackageCache:
    """Private keyed cache; metadata and media atomically published together."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = default_cache_root() if root is None else root

    def lookup(
        self, source: Path, expected_hash: str, *, stamp: FileStamp | None = None
    ) -> CacheEntry | None:
        """An entry hit never reads original media contents."""
        current = source_stamp(source)
        if stamp is not None and current != stamp:
            raise SourceChangedError(f"supplied media changed before lookup: {source}")
        key = entry_key(source, current, expected_hash)
        if not _private_root(self.root, create=False):
            _same_source(source, current)
            return None
        folder = self.root / key
        try:
            directory = folder.stat(follow_symlinks=False)
            if not stat.S_ISDIR(directory.st_mode):
                return None
            if set(item.name for item in folder.iterdir()) != {_BLOB, _RECORD}:
                return None
            if _read_record(folder / _RECORD) != _record(
                source, current, expected_hash, key
            ):
                return None
            blob = folder / _BLOB
            info = _regular_cache_file(blob)
            if info.st_size != current.size:
                return None
            found = CacheEntry(
                source, current, expected_hash, key, blob, FileStamp.from_stat(info)
            )
        except (OSError, ValueError, TypeError, _CacheMiss):
            return None
        finally:
            _same_source(source, current)
        return found

    def publish(
        self,
        source: Path,
        expected_hash: str,
        staged: Path,
        *,
        stamp: FileStamp | None = None,
        clone: Clone | None = None,
    ) -> CacheEntry | None:
        """Save a *caller-verified* staged file without rereading source bytes.

        Failure to write cache is a miss. Source stamp changes still raise.
        """
        current = source_stamp(source)
        if stamp is not None and current != stamp:
            raise SourceChangedError(f"supplied media changed before caching: {source}")
        key = entry_key(source, current, expected_hash)
        if not _private_root(self.root, create=True):
            _same_source(source, current)
            return None
        try:
            with tempfile.TemporaryDirectory(
                prefix=".writing-", dir=self.root
            ) as temporary:
                folder = Path(temporary)
                clone_or_copy(staged, folder / _BLOB, clone=clone, private=True)
                if (folder / _BLOB).stat().st_size != current.size:
                    return None
                record_bytes = json.dumps(
                    _record(source, current, expected_hash, key),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
                with (folder / _RECORD).open("xb") as writer:
                    writer.write(record_bytes)
                    writer.flush()
                    os.fsync(writer.fileno())
                stage_fd = os.open(folder, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(stage_fd)
                finally:
                    os.close(stage_fd)
                _same_source(source, current)
                # An existing winner (or corrupt entry) is never overwritten.
                with suppress(OSError):
                    os.rename(folder, self.root / key)
                    parent_fd = os.open(
                        self.root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                    )
                    try:
                        os.fsync(parent_fd)
                    finally:
                        os.close(parent_fd)
        except (OSError, _CacheMiss):
            return None
        finally:
            _same_source(source, current)
        return self.lookup(source, expected_hash, stamp=current)

    def materialize(
        self, entry: CacheEntry, destination: Path, *, clone: Clone | None = None
    ) -> bool:
        """False on stale/unreadable cache; never silently ignore source drift."""
        _same_source(entry.source, entry.stamp)
        current = self.lookup(entry.source, entry.expected_hash, stamp=entry.stamp)
        if current is None or current.blob_stamp != entry.blob_stamp:
            return False
        try:
            clone_or_copy(entry.blob, destination, clone=clone)
        except (OSError, _CacheMiss):
            return False
        finally:
            try:
                _same_source(entry.source, entry.stamp)
            except SourceChangedError:
                destination.unlink(missing_ok=True)
                raise
        return True

    def discard(self, entry: CacheEntry) -> None:
        """Discard a suspect entry before a fresh-source retry (best effort)."""
        if not _private_root(self.root, create=False):
            return
        directory = self.root / entry.key
        try:
            if stat.S_ISDIR(directory.stat(follow_symlinks=False).st_mode):
                shutil.rmtree(directory)
        except OSError:
            pass
