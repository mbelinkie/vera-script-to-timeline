"""Command-line entry point for one verified Resolve Studio assembly."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .studio_assembly import StudioAssemblyError, run_studio_assembly


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("package", type=Path, help="verified Authoring Project root")
    value.add_argument("--action", choices=("preflight", "build"), default="preflight")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        result = run_studio_assembly(arguments.package, action=arguments.action)
    except (OSError, StudioAssemblyError, ValueError) as error:
        print(f"Studio assembly stopped safely: {error}", file=sys.stderr)
        return 2
    sys.stdout.write(result.to_json())
    return 0 if result.status in {"preflight_passed", "verified"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
