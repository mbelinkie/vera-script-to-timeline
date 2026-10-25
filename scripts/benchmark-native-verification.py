"""Read-only #254 measurement of a retained native/host retry evidence chain."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--revision", help="Read the native verifier from this Git ref")
    args = parser.parse_args()
    name = "vera_timeline_agent.qualification_output_native_v2"
    if args.revision:
        source = subprocess.check_output(
            [
                "git",
                "show",
                f"{args.revision}:python/vera_timeline_agent/"
                "qualification_output_native_v2.py",
            ]
        )
        module = types.ModuleType(name)
        module.__package__ = "vera_timeline_agent"
        module.__file__ = str(
            Path(
                "python/vera_timeline_agent/qualification_output_native_v2.py"
            ).resolve()
        )
        sys.modules[name] = module
        exec(compile(source, name, "exec"), module.__dict__)
    else:
        module = importlib.import_module(name)

    digest = hashlib.sha256(args.result.read_bytes()).hexdigest()
    sha256 = hashlib.sha256
    hashed_bytes = 0
    hash_calls = 0

    class CountedHash:
        def __init__(self, data: bytes = b"") -> None:
            nonlocal hashed_bytes, hash_calls
            hash_calls += 1
            hashed_bytes += len(data)
            self.inner = sha256(data)

        def update(self, data: bytes) -> None:
            nonlocal hashed_bytes
            hashed_bytes += len(data)
            self.inner.update(data)

        def copy(self) -> CountedHash:
            copied = object.__new__(CountedHash)
            copied.inner = self.inner.copy()
            return copied

        def __getattr__(self, name: str) -> Any:
            return getattr(self.inner, name)

    # Includes HMAC and streaming file hashes, not merely bytes read from disk.
    hashlib.sha256 = CountedHash  # type: ignore[assignment]
    started = time.perf_counter()
    try:
        result = module.verify_native_result(args.result, digest)
    finally:
        elapsed = time.perf_counter() - started
        hashlib.sha256 = sha256
    print(
        json.dumps(
            {
                "revision": args.revision or "working-tree",
                "verificationSeconds": elapsed,
                "sha256InputBytes": hashed_bytes,
                "sha256Calls": hash_calls,
                "action": result["action"],
                "sequence": result["sequence"],
                "status": result["status"],
                "renderStatus": result["renderStatus"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
