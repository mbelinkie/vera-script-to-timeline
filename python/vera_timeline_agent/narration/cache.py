from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import shutil
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from vera_timeline_agent.narration.models import canonical_json_bytes, sha256_bytes

CacheKind = Literal["synthesis", "normalization", "assets"]


class CacheError(RuntimeError):
    pass


@dataclass(frozen=True)
class CacheEntry:
    path: Path
    files: dict[str, bytes]
    metadata: dict[str, Any]


def _validate_name(name: str) -> None:
    if not name or name in {".", ".."} or Path(name).name != name:
        raise CacheError(f"unsafe cache filename: {name!r}")


class NarrationCache:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve() / "v1"
        for name in ("locks", "synthesis", "normalization", "assets"):
            path = self.root / name
            path.mkdir(parents=True, exist_ok=True)
            if path.is_symlink():
                raise CacheError(f"cache path may not be a symbolic link: {path}")

    @contextlib.contextmanager
    def lock(self, key: str) -> Iterator[None]:
        if not re_full_key(key):
            raise CacheError("cache key must be 64 lowercase hexadecimal characters")
        path = self.root / "locks" / f"{key}.lock"
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _target(self, kind: CacheKind, key: str) -> Path:
        if kind == "assets":
            parts = key.split("/")
            if (
                len(parts) != 2
                or re.fullmatch(r"[A-Za-z0-9-]{1,128}", parts[0]) is None
                or not re_full_key(parts[1])
            ):
                raise CacheError("asset key must be <safe-block-id>/<sha256-hex>")
            return self.root / kind / parts[0] / parts[1]
        if not re_full_key(key):
            raise CacheError("cache key must be 64 lowercase hexadecimal characters")
        return self.root / kind / key

    def _assert_safe_ancestors(self, path: Path) -> None:
        current = path
        while True:
            if current.is_symlink():
                raise CacheError(
                    f"cache path may not contain a symbolic link: {current}"
                )
            if current == self.root:
                return
            if self.root not in current.parents:
                raise CacheError("cache path escapes the cache root")
            current = current.parent

    def read(self, kind: CacheKind, key: str, metadata_name: str) -> CacheEntry | None:
        _validate_name(metadata_name)
        target = self._target(kind, key)
        self._assert_safe_ancestors(target)
        if not target.exists():
            return None
        if target.is_symlink() or not target.is_dir():
            raise CacheError(f"unsafe cache entry: {target}")
        actual_paths = list(target.iterdir())
        if any(path.is_symlink() or not path.is_file() for path in actual_paths):
            raise CacheError("cache entry contains a symbolic link or non-file")
        metadata_path = target / metadata_name
        if not metadata_path.exists():
            raise CacheError("cache inventory is missing its metadata record")
        try:
            metadata_value = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CacheError("cache metadata is unreadable") from error
        if not isinstance(metadata_value, dict):
            raise CacheError("cache metadata is not an object")
        metadata = cast(dict[str, Any], metadata_value)
        inventory = metadata.get("inventory")
        if not isinstance(inventory, dict):
            raise CacheError("cache metadata inventory is invalid")
        expected = set(inventory) | {metadata_name}
        actual = {path.name for path in actual_paths}
        if actual != expected:
            raise CacheError("cache inventory does not match directory contents")
        files: dict[str, bytes] = {}
        for path in actual_paths:
            if path.stat(follow_symlinks=False).st_nlink != 1:
                raise CacheError("cache entry contains a hard link")
            if path.name == metadata_name:
                continue
            content = path.read_bytes()
            expected_hash = inventory.get(path.name)
            if expected_hash != sha256_bytes(content):
                raise CacheError(f"cache hash mismatch for {path.name}")
            files[path.name] = content
        if metadata.get("key") != key or metadata.get("kind") != kind:
            raise CacheError("cache metadata identity does not match its locator")
        return CacheEntry(path=target, files=files, metadata=metadata)

    def publish(
        self,
        kind: CacheKind,
        key: str,
        files: dict[str, bytes],
        metadata_name: str,
        metadata: dict[str, Any],
    ) -> str:
        _validate_name(metadata_name)
        for name in files:
            _validate_name(name)
        if metadata_name in files:
            raise CacheError("metadata filename conflicts with payload")
        existing = self.read(kind, key, metadata_name)
        if existing is not None:
            expected_metadata = {**metadata, "kind": kind, "key": key}
            comparable = {
                k: v for k, v in existing.metadata.items() if k != "inventory"
            }
            if existing.files != files or comparable != expected_metadata:
                raise CacheError(
                    "immutable cache entry already exists with different contents"
                )
            return "reused"

        parent = self._target(kind, key).parent
        self._assert_safe_ancestors(parent)
        parent.mkdir(parents=True, exist_ok=True)
        if parent.is_symlink():
            raise CacheError("cache parent may not be a symbolic link")
        staging_prefix = f".{key.replace('/', '.')}."
        staging = Path(tempfile.mkdtemp(prefix=staging_prefix, dir=parent))
        target = self._target(kind, key)
        try:
            inventory = {
                name: sha256_bytes(content) for name, content in sorted(files.items())
            }
            complete_metadata = {
                **metadata,
                "kind": kind,
                "key": key,
                "inventory": inventory,
            }
            for name, content in files.items():
                (staging / name).write_bytes(content)
            (staging / metadata_name).write_bytes(
                canonical_json_bytes(complete_metadata)
            )
            for path in staging.iterdir():
                with path.open("rb") as handle:
                    os.fsync(handle.fileno())
            directory_descriptor = os.open(staging, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
            try:
                os.rename(staging, target)
            except OSError as error:
                winner = self.read(kind, key, metadata_name)
                if winner is None:
                    raise
                expected_metadata = {**metadata, "kind": kind, "key": key}
                comparable = {
                    k: v for k, v in winner.metadata.items() if k != "inventory"
                }
                if winner.files != files or comparable != expected_metadata:
                    raise CacheError(
                        "concurrent cache winner has different contents"
                    ) from error
                return "reused"
            return "generated"
        finally:
            if staging.exists():
                shutil.rmtree(staging)


def re_full_key(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )
