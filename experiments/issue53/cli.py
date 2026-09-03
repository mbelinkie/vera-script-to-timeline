"""Local experimental JSON entry point; never invokes transcription or a provider."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from experiments.issue53.takes import Record, discover


def write_private(path: Path, value: Record) -> None:
    """Exclusive, restrictive output outside any Git worktree."""
    parent = path.parent.resolve(strict=True)
    if any((p / ".git").exists() for p in [parent, *parent.parents]):
        raise ValueError("Private reports must be outside Git worktrees")
    data = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    )
    fd = os.open(parent / path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = discover(json.loads(args.input.read_text()))
        write_private(args.output, report)
    except (ValueError, OSError, KeyError, TypeError):
        print("Experiment validation/output creation failed; no success claimed.")
        return 1
    print("Local report retained; review needed. No keeper approved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
