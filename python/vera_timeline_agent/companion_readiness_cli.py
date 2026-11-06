"""Emit one immutable, non-authorizing companion setup/recovery report."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .companion_readiness import retain_report
from .workflow_package import read_object, sha256


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed-root", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--observation", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        report = retain_report(
            arguments.output.absolute(),
            arguments.installed_root.absolute(),
            read_object(arguments.policy),
            read_object(arguments.observation),
        )
    except Exception as error:
        # A diagnostic boundary never leaks a traceback or retries.
        print(f"Companion readiness refused: {error}", file=sys.stderr)
        return 2
    print(f"{report} sha256:{sha256(report)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
