#!/usr/bin/env python3
"""One-shot inspection/focus request for Phase 3; NEVER a native edit.

Use only with a known, authorized disposable Resolve window. This script is
not part of the future M4 Roll queue; no Roll operation can be requested.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCHEMA = "vera.gui-helper-focus-request/v1"
REPLY_SCHEMA = "vera.gui-helper-focus-reply/v1"
RESOLVE_BUNDLE = "com.blackmagic-design.DaVinciResolve"


def canonical(obj: object) -> bytes:
    return (json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=True) + "\n").encode()


def private_spool(path: Path) -> None:
    meta = path.lstat()
    if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.getuid() or meta.st_mode & 0o077:
        raise ValueError("refuse missing/non-private/aliased helper spool")


def publish(path: Path, request: dict[str, object]) -> bytes:
    private_spool(path)
    raw = canonical(request)
    dest = path / (str(request["requestId"]) + ".focus-request.json")
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        if os.write(fd, raw) != len(raw):
            raise RuntimeError("incomplete focus request write")
        os.fsync(fd)
    finally:
        os.close(fd)
    parent = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--window", required=True)
    parser.add_argument("--operation", choices=("inspect", "focus"), default="inspect")
    parser.add_argument("--id", required=True)
    parser.add_argument("--spool", type=Path, default=Path.home() / "Library/Application Support/VERA/GUI Helper/spool")
    args = parser.parse_args()
    if args.pid <= 0 or not 8 <= len(args.id) <= 128 or not args.id.replace("-", "").replace("_", "").isalnum():
        parser.error("invalid PID or unique request ID")
    if "\n" in args.window or not args.window:
        parser.error("invalid exact target window")
    request: dict[str, object] = {
        "schema": SCHEMA,
        "requestId": args.id,
        "deadlineAt": (datetime.now(UTC) + timedelta(seconds=30)).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "operation": args.operation,
        "resolvePid": args.pid,
        "resolveBundleIdentifier": RESOLVE_BUNDLE,
        "windowName": args.window,
    }
    raw = publish(args.spool, request)
    reply_path = args.spool / (args.id + ".focus-reply.json")
    expected_sha = hashlib.sha256(raw).hexdigest()
    for _ in range(60):
        time.sleep(0.1)
        if not reply_path.exists():
            continue
        reply = json.loads(reply_path.read_bytes())
        if reply.get("schema") != REPLY_SCHEMA or reply.get("requestSha256") != expected_sha or reply.get("requestId") != args.id:
            raise ValueError("untrusted helper focus reply")
        print(json.dumps(reply, sort_keys=True))
        return
    raise TimeoutError("helper did not publish a focused response; NO EDIT CLAIMED")


if __name__ == "__main__":
    main()
