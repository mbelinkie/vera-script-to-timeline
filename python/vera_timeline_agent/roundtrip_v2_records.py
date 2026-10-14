"""Small standard-library record primitives for the injected #190 runtime."""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

JsonObject = dict[str, Any]
ROOT = Path(__file__).resolve().parents[2]
ReceiptVerifier = Callable[[str, bytes, JsonObject], None]


class ProofNativeError(RuntimeError):
    """A native proof boundary refused without inventing a capability."""


def fact(condition: bool, message: str) -> None:
    if not condition:
        raise ProofNativeError(message)


def shape(value: Any, keys: str, label: str) -> JsonObject:
    fact(isinstance(value, dict) and set(value) == set(keys.split()), f"{label} shape")
    return cast(JsonObject, value)


def identity(value: Any) -> str:
    fact(isinstance(value, str) and 0 < len(value) <= 256, "identity required")
    return cast(str, value)


def integer(value: Any, minimum: int = 0) -> int:
    fact(type(value) is int and minimum <= value <= 2**53 - 1, "exact integer required")
    return cast(int, value)


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _regular(path: Path) -> Path:
    absolute = path.absolute()
    for component in (absolute, *absolute.parents):
        fact(not component.is_symlink(), "symbolic-link input refused")
    info = absolute.stat()
    fact(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "independent file required")
    return absolute


def _operator_bytes(path: Path, *, limit: int = 8 * 1024 * 1024) -> bytes:
    with os.fdopen(_open_file(path, os.O_RDONLY), "rb") as stream:
        before = os.fstat(stream.fileno())
        fact(before.st_nlink > 0, "input changed while read")
        fact(
            stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
            "independent file required",
        )
        fact(before.st_size <= limit, "bounded record required")
        raw = stream.read(limit + 1)
        fact(len(raw) == before.st_size, "record size changed while read")
        _unchanged(path, before, os.fstat(stream.fileno()))
        return raw


def _open_file(path: Path, flags: int, mode: int = 0o400) -> int:
    """Walk with directory descriptors so swapped ancestors cannot follow links."""
    absolute = path.absolute()
    descriptor = os.open(absolute.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in absolute.parts[1:-1]:
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
            )
            os.close(descriptor)
            descriptor = child
        return os.open(absolute.name, flags | os.O_NOFOLLOW, mode, dir_fd=descriptor)
    finally:
        os.close(descriptor)


def _unchanged(path: Path, before: os.stat_result, after: os.stat_result) -> None:
    def key(info: os.stat_result) -> tuple[int, ...]:
        return (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
            info.st_nlink,
        )

    fact(
        key(before) == key(after) == key(_regular(path).stat()),
        "input changed while read",
    )


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with os.fdopen(_open_file(path, os.O_RDONLY), "rb") as stream:
        before = os.fstat(stream.fileno())
        fact(before.st_nlink > 0, "input changed while read")
        fact(
            stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
            "independent file required",
        )
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        _unchanged(path, before, os.fstat(stream.fileno()))
    return "sha256:" + digest.hexdigest()


def _parse(raw: bytes) -> JsonObject:
    def pairs(values: list[tuple[str, Any]]) -> JsonObject:
        result: JsonObject = {}
        for key, value in values:
            fact(key not in result, "duplicate record key")
            result[key] = value
        return result

    def invalid(value: str) -> Any:
        raise ProofNativeError(f"nonfinite record number: {value}")

    def floating(value: str) -> float:
        parsed = float(value)
        fact(math.isfinite(parsed), "nonfinite record number")
        return parsed

    def exact(value: str) -> int:
        parsed = int(value)
        fact(abs(parsed) <= 2**53 - 1, "unsafe record integer")
        return parsed

    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=pairs,
        parse_constant=invalid,
        parse_float=floating,
        parse_int=exact,
    )
    fact(isinstance(value, dict), "one object record required")
    return cast(JsonObject, value)


def _destination(path: Path) -> None:
    absolute = path.absolute()
    for component in (absolute, *absolute.parents):
        fact(not component.is_symlink(), "symbolic-link output refused")
        if component.exists():
            info = component.stat()
            fact(
                stat.S_ISDIR(info.st_mode)
                or (
                    component == absolute
                    and stat.S_ISREG(info.st_mode)
                    and info.st_nlink == 1
                ),
                "unsafe output component",
            )


def publish_immutable_output(path: Path, raw: bytes) -> None:
    _destination(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = _open_file(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        fact(_operator_bytes(path) == raw, "immutable record ownership differs")
        return
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def proof_source_hashes_v2() -> JsonObject:
    """Pin the entire consumed TS/schema graph plus accepted Python boundaries."""
    paths = {
        *(
            p
            for p in (ROOT / "packages/contracts/src").rglob("*")
            if p.suffix in {".ts", ".json", ".svg"}
        ),
        *sorted((ROOT / "contracts").glob("*.json")),
        ROOT / "package-lock.json",
        ROOT / "uv.lock",
        ROOT / "pyproject.toml",
        *sorted((ROOT / "python/vera_timeline_agent").rglob("*.py")),
    }
    return {str(path.relative_to(ROOT)): _file_hash(path) for path in sorted(paths)}
