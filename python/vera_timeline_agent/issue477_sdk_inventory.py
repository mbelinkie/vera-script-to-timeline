"""Offline, bounded declaration inventory for VERA #477; never loads the SDK.

This is *static evidence*, not a Resolve capability probe or edit authorization.
All version labels are supplied by the caller and are not authenticated by this
module. Even a complete, documented setter surface cannot prove a same-UID roll.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

MAX_BYTES = 2_000_000
_METHODS = {
    "TimelineItem": frozenset(
        {
            "GetUniqueId",
            "GetStart",
            "GetEnd",
            "GetLeftOffset",
            "GetRightOffset",
            "SetLeftOffset",
            "SetRightOffset",
            "SetPosition",
            "GetPosition",
        }
    ),
    "Timeline": frozenset({"MoveItems", "GetStartFrame", "GetEndFrame"}),
}
_NEW_METHOD_ARGUMENT = {
    ("TimelineItem", "SetLeftOffset"): "offset",
    ("TimelineItem", "SetRightOffset"): "offset",
    ("TimelineItem", "SetPosition"): "position",
    ("Timeline", "MoveItems"): "timelineItems",
}


def _read_regular(path: Path) -> tuple[bytes, tuple[int, int]]:
    """Read a regular text file without following final or directory symlinks.

    Checking components catches ordinary symlinks; O_NOFOLLOW prevents a final
    component swap between the check and opening. O_NONBLOCK refuses FIFOs
    without hanging. A bounded read also protects against a growing file.
    """
    if not isinstance(path, Path):
        raise ValueError("SDK input must be a Path")
    absolute = path.absolute()
    if any(part.is_symlink() for part in (absolute, *absolute.parents)):
        raise ValueError("SDK input must not contain symlinks")
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        fd = os.open(absolute, flags)
    except OSError as exc:
        raise ValueError("SDK input cannot be opened as a regular file") from exc
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode):
            raise ValueError("SDK input must be a regular file")
        if meta.st_size > MAX_BYTES:
            raise ValueError("SDK input exceeds byte limit")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            raw = handle.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("SDK input exceeds byte limit")
        return raw, (meta.st_dev, meta.st_ino)
    finally:
        os.close(fd)


def _version(label: str | None) -> tuple[int, int, int] | None:
    if label is None:
        return None
    if not re.fullmatch(r"\d{1,3}\.\d{1,3}(?:\.\d{1,3}(?:\.\d{1,3})?)?", label):
        raise ValueError("expected numerical caller version label, e.g. 21.1.2.10")
    parts = tuple(int(p) for p in label.split("."))
    return parts[0], parts[1], parts[2] if len(parts) > 2 else 0


def _declarations(text: str) -> tuple[dict[str, dict[str, dict[str, Any]]], bool]:
    try:
        tree = ast.parse(text, filename="<offline-sdk-stub>")
    except (SyntaxError, RecursionError, ValueError) as exc:
        raise ValueError("malformed SDK stub syntax") from exc
    result: dict[str, dict[str, dict[str, Any]]] = {name: {} for name in _METHODS}
    found: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name not in result:
            continue
        if node.name in found:
            raise ValueError(f"duplicate SDK class: {node.name}")
        found.add(node.name)
        seen: set[str] = set()
        for child in node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if child.name in seen:
                raise ValueError(f"duplicate SDK method: {node.name}.{child.name}")
            seen.add(child.name)
            if child.name not in _METHODS[node.name]:
                continue
            try:
                signature = f"{child.name}({ast.unparse(child.args)})"
                if child.returns is not None:
                    signature += f" -> {ast.unparse(child.returns)}"
            except (RecursionError, ValueError) as exc:
                raise ValueError("malformed SDK signature") from exc
            if len(signature) > 1024:
                raise ValueError("SDK signature exceeds output limit")
            positional = child.args.posonlyargs + child.args.args
            result[node.name][child.name] = {
                "line": child.lineno,
                "signature": signature,
                "parameters": [arg.arg for arg in positional],
                "synchronous": isinstance(child, ast.FunctionDef),
                "decorated": bool(child.decorator_list),
            }
    return result, found == set(_METHODS)


def _assessment(
    version: tuple[int, int, int] | None,
    declarations: dict[str, dict[str, dict[str, Any]]],
    complete_classes: bool,
) -> str:
    if version is None or not complete_classes:
        return "unknown"
    new_symbols = all(
        declarations[cls].get(name, {}).get("parameters", [])[:2] == ["self", parameter]
        and declarations[cls][name]["synchronous"]
        and not declarations[cls][name]["decorated"]
        for (cls, name), parameter in _NEW_METHOD_ARGUMENT.items()
    )
    if version < (21, 1, 2):
        return (
            "not_declared_in_supplied_stub"
            if not any(name in declarations[cls] for cls, name in _NEW_METHOD_ARGUMENT)
            else "unknown"
        )
    if new_symbols and "GetUniqueId" in declarations["TimelineItem"]:
        return "candidate_unverified"
    return "unknown"


def inventory(
    stub: Path,
    version_label: str | None = None,
    *,
    readme: Path | None = None,
    changelog: Path | None = None,
) -> dict[str, Any]:
    """Inventory at most three caller-selected files; never infer live behavior.

    The supplied version label, even when plausible, is not a verified installed
    application version. Source hashes establish bytes, not vendor provenance.
    """
    version = _version(version_label)
    files: dict[str, dict[str, Any]] = {}
    identities: set[tuple[int, int]] = set()
    stub_text: str | None = None
    for role, path in (("stub", stub), ("readme", readme), ("changelog", changelog)):
        if path is None:
            continue
        if not isinstance(path, Path) or path.suffix != (
            ".pyi" if role == "stub" else ".md"
        ):
            raise ValueError(f"unexpected {role} extension")
        raw, identity = _read_regular(path)
        if identity in identities:
            raise ValueError("duplicate SDK input (same file or hard link)")
        identities.add(identity)
        try:
            decoded = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{role} is not UTF-8 text") from exc
        files[role] = {
            "name": path.name,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        if role == "stub":
            stub_text = decoded
    if stub_text is None:
        raise ValueError("SDK stub is required")
    declarations, complete = _declarations(stub_text)
    return {
        "evidenceClass": "offline_static_declarations_only",
        "files": files,
        "versionLabel": version_label,
        "versionLabelSource": "caller_supplied_unverified",
        "installedBuildVerified": False,
        "classesComplete": complete,
        "declarations": declarations,
        "state": _assessment(version, declarations, complete),
        "sameUidRollNativeVerified": False,
        "mayExecuteNativeEdit": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stub", type=Path, help="existing local .pyi text file")
    parser.add_argument("--version-label", help="unverified caller-supplied version")
    parser.add_argument("--readme", type=Path, help="optional existing README.md")
    parser.add_argument("--changelog", type=Path, help="optional existing CHANGELOG.md")
    args = parser.parse_args(argv)
    try:
        result = inventory(
            args.stub, args.version_label, readme=args.readme, changelog=args.changelog
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
