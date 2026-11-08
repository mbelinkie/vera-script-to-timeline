"""#489: bounded, offline string inventory of explicitly selected Resolve bundle files.

Only reads bytes. Never imports the Resolve SDK, loads a library, starts a process,
connects to Resolve/ResolveMCP or authorizes a native edit. A string is NOT an API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

MAX_FILES = 48
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_RESOURCE_BYTES = 2 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
MAX_RELATIVE_PARTS = 16

# Controls that should already exist in the installed 21.1.1 surface.
POSITIVE_CONTROLS = ("AddTake", "FinalizeTake", "GetSmartReframeStatus")
# 21.1.2+ names or *possible* roll primitives. Finding any string proves
# neither a callable method nor a vendor-supported operation.
EDIT_CANDIDATES = (
    "SetLeftOffset",
    "SetRightOffset",
    "SetPosition",
    "GetPosition",
    "MoveItems",
    "RollEdit",
    "RippleTrim",
)
IMPOSSIBLE_CONTROL = "VERA489_IMPOSSIBLE_NATIVE_METHOD_9d1297b1"
PROBES = (*POSITIVE_CONTROLS, *EDIT_CANDIDATES, IMPOSSIBLE_CONTROL)
_TOKEN_PATTERNS = {
    name: re.compile(
        rb"(?<![A-Za-z0-9_])" + name.encode("ascii") + rb"(?![A-Za-z0-9_])"
    )
    for name in PROBES
}
_MACHO_MAGIC = {
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf",
    b"\xbf\xba\xfe\xca",
}
# Only extract *candidate tool identifiers*; never emit nearby strings,
# metadata, argument values, environment settings or configuration contents.
_TOOL_NAME = re.compile(
    rb'(?:"name"|"tool_name")\s*:\s*"([A-Za-z][A-Za-z0-9_.-]{2,79})"'
)
_EDIT_NAME = re.compile(r"roll|trim|ripple|slip|edit|move|cut|shift", re.IGNORECASE)
_SECRET_NAME = re.compile(r"key|secret|password|token|credential", re.IGNORECASE)
_PRIVATE_RESOURCE = re.compile(
    r"(^\.env|config|credential|token|secret|password|keychain|private|auth)",
    re.IGNORECASE,
)
_SCAN_OVERLAP = max(max(len(name) for name in PROBES) + 2, 128)


def _tool_hints(raw: bytes) -> set[str]:
    return {
        name
        for hit in _TOOL_NAME.finditer(raw)
        if (name := hit.group(1).decode("ascii"))
        and _EDIT_NAME.search(name)
        and not _SECRET_NAME.search(name)
    }


def _relative_parts(path: Path) -> tuple[str, ...]:
    if not isinstance(path, Path) or path.is_absolute():
        raise ValueError("candidate must be a relative Path inside the app")
    # Check spelling before Path normalizes redundant slashes or dot segments.
    raw = str(path)
    if raw.startswith("/") or any(part in {"", ".", ".."} for part in raw.split("/")):
        raise ValueError("unsafe candidate path")
    parts = path.parts
    if not parts or len(parts) > MAX_RELATIVE_PARTS:
        raise ValueError("candidate path depth limit")
    return parts


def _open_bundle(root: Path) -> int:
    """Open every absolute directory component without following symlinks."""
    if not isinstance(root, Path) or not root.is_absolute() or root.suffix != ".app":
        raise ValueError("expected absolute existing .app bundle")
    parts = root.parts[1:]
    if not parts or any(part in {".", ".."} for part in parts):
        raise ValueError("unsafe bundle root")
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    fd = os.open("/", flags)
    try:
        for part in parts:
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except OSError as exc:
        raise ValueError("bundle directory missing, inaccessible or symlinked") from exc
    finally:
        # Ownership transfers to the caller only after a successful return.
        if sys.exc_info()[0] is not None:
            os.close(fd)


def _open_candidate(bundle_fd: int, parts: tuple[str, ...]) -> int:
    flags_dir = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    flags_dir |= getattr(os, "O_CLOEXEC", 0)
    flags_file = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
    flags_file |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    current = os.dup(bundle_fd)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, flags_dir, dir_fd=current)
            os.close(current)
            current = next_fd
        return os.open(parts[-1], flags_file, dir_fd=current)
    except OSError as exc:
        raise ValueError("candidate missing, inaccessible or symlinked") from exc
    finally:
        os.close(current)


def _format_label(prefix: bytes) -> str:
    if len(prefix) >= 28 and prefix[:4] in _MACHO_MAGIC:
        return "Mach-O-magic-only"
    return "unrecognized"


def _inspect_fd(fd: int, role: str) -> tuple[dict[str, Any], set[str], set[str]]:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("candidate is not a regular file")
    limit = MAX_RESOURCE_BYTES if role == "resource" else MAX_FILE_BYTES
    if before.st_size > limit:
        raise ValueError("candidate exceeds byte limit")
    digest = hashlib.sha256()
    found: set[str] = set()
    names: set[str] = set()
    prefix = b""
    tail = b""
    resource_data = bytearray()
    count = 0
    while True:
        chunk = os.read(fd, min(CHUNK_BYTES, limit - count + 1))
        if not chunk:
            break
        count += len(chunk)
        if count > limit:
            raise ValueError("candidate exceeds byte limit while reading")
        digest.update(chunk)
        if len(prefix) < 32:
            prefix = (prefix + chunk)[:32]
        window = tail + chunk
        # Defer matches terminating exactly at a chunk boundary: the next
        # byte may be an identifier character (e.g. SetLeftOffset_Fake).
        found.update(
            name
            for name, pattern in _TOKEN_PATTERNS.items()
            if any(match.end() < len(window) for match in pattern.finditer(window))
        )
        if role == "binary":
            names.update(_tool_hints(window))
        # Retain enough bytes for exact token matching across read boundaries.
        tail = window[-_SCAN_OVERLAP:]
        if role == "resource":
            resource_data.extend(chunk)
    # At actual EOF, a token ending at the last byte is legitimate.
    found.update(
        name for name, pattern in _TOKEN_PATTERNS.items() if pattern.search(tail)
    )
    after = os.fstat(fd)
    if count != before.st_size or (
        before.st_dev,
        before.st_ino,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError("candidate changed during inspection")
    if role == "resource":
        names = _tool_hints(bytes(resource_data))
    return (
        {
            "bytes": count,
            "sha256": digest.hexdigest(),
            "format": _format_label(prefix) if role == "binary" else "resource-data",
        },
        found,
        names,
    )


def audit(
    app: Path,
    *,
    binaries: Sequence[Path],
    resources: Sequence[Path] = (),
    version_label: str | None = None,
) -> dict[str, Any]:
    """Inventory caller-specified files ONLY; never claim full-app coverage."""
    if version_label is not None and not re.fullmatch(
        r"\d{1,3}\.\d{1,3}(?:\.\d{1,3}(?:\.\d{1,3})?)?", version_label
    ):
        raise ValueError("invalid unverified version label")
    if not binaries:
        raise ValueError("at least one explicit binary candidate is required")
    entries = [(p, "binary") for p in binaries] + [(p, "resource") for p in resources]
    if len(entries) > MAX_FILES:
        raise ValueError("candidate file-count limit")
    for path, role in entries:
        parts = _relative_parts(path)
        if role == "binary" and path.suffix.lower() not in {"", ".dylib", ".so"}:
            raise ValueError("binary candidate must be Mach-O, dylib or .so path")
        if role == "resource":
            if any(_PRIVATE_RESOURCE.search(part) for part in parts):
                raise ValueError("refusing private configuration or credentials")
            if path.suffix.lower() not in {
                ".json",
                ".md",
                ".txt",
                ".plist",
                ".strings",
            }:
                raise ValueError("resource must be public documentation or manifest")
    entries.sort(key=lambda entry: (entry[0].as_posix(), entry[1]))
    files: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    seen_inodes: set[tuple[int, int]] = set()
    binary_hits: set[str] = set()
    resource_hits: set[str] = set()
    tool_hints: set[str] = set()
    all_macho = True
    total = 0
    bundle_fd = _open_bundle(app)
    try:
        for relative, role in entries:
            name = relative.as_posix()
            if name in seen_paths:
                raise ValueError("duplicate candidate path")
            seen_paths.add(name)
            fd = _open_candidate(bundle_fd, _relative_parts(relative))
            try:
                metadata = os.fstat(fd)
                inode = (metadata.st_dev, metadata.st_ino)
                if inode in seen_inodes:
                    raise ValueError("duplicate candidate file identity")
                seen_inodes.add(inode)
                if metadata.st_size < 0 or total + metadata.st_size > MAX_TOTAL_BYTES:
                    raise ValueError("aggregate byte limit")
                total += metadata.st_size
                details, hits, names = _inspect_fd(fd, role)
            finally:
                os.close(fd)
            files.append({"path": name, "role": role, **details})
            tool_hints.update(names)
            if role == "binary":
                binary_hits.update(hits)
                all_macho &= details["format"] == "Mach-O-magic-only"
            else:
                resource_hits.update(hits)
    except OSError as exc:
        raise ValueError("read-only candidate inspection failed") from exc
    finally:
        os.close(bundle_fd)
    controls = all(name in binary_hits for name in POSITIVE_CONTROLS)
    any_edit = any(name in binary_hits for name in EDIT_CANDIDATES)
    # The impossible-name control is a fail-closed validity check, not proof
    # that the searched strings would have been callable if present.
    if IMPOSSIBLE_CONTROL in binary_hits or not all_macho:
        state = "INCONCLUSIVE"
    elif any_edit:
        state = "present-but-unsupported"
    elif controls:
        state = "absent"
    else:
        state = "INCONCLUSIVE"
    return {
        "evidenceClass": "explicit_subset_offline_string_inventory_only",
        "appPath": str(app),
        "versionLabel": version_label,
        "versionLabelSource": "caller_supplied_unverified",
        "files": files,
        "totalBytes": total,
        "positiveControls": {name: name in binary_hits for name in POSITIVE_CONTROLS},
        "binaryMethodNames": {name: name in binary_hits for name in EDIT_CANDIDATES},
        "resourceMethodNames": {name: name in resource_hits for name in PROBES},
        "impossibleControlAbsent": IMPOSSIBLE_CONTROL not in binary_hits,
        "candidateMcpEditToolNames": sorted(tool_hints)[:MAX_FILES],
        "needsIndependentMcpToolReview": bool(tool_hints),
        "scannedSetState": state,
        "fullAppCoverageVerified": False,
        "installedBuildVerified": False,
        "vendorApiSupportVerified": False,
        "sameUidRollNativeVerified": False,
        "mayExecuteNativeEdit": False,
        "mayUnblock473Or312": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, type=Path, help="existing .app path")
    parser.add_argument("--binary", required=True, action="append", type=Path)
    parser.add_argument("--resource", action="append", default=[], type=Path)
    parser.add_argument(
        "--version-label", help="caller-supplied; not a runtime version"
    )
    args = parser.parse_args(argv)
    try:
        result = audit(
            args.app,
            binaries=args.binary,
            resources=args.resource,
            version_label=args.version_label,
        )
    except (OSError, ValueError) as exc:
        print(f"static inventory INCONCLUSIVE: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
