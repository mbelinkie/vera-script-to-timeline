"""Build one VERA v2 script in Resolve Studio (foreground command)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .build_jobs import BuildJobError, NeedsAction, UncertainResult
from .build_timeline_once import BuildOptions, StageTimings, build_once


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--script", type=Path, required=True, help="v2 script JSON")
    command.add_argument(
        "--inputs", type=Path, help="directory of previously prepared v2 inputs"
    )
    command.add_argument(
        "--output", type=Path, required=True, help="new, unused local output directory"
    )
    command.add_argument(
        "--existing-project", help="add a new timeline to this named project"
    )
    command.add_argument(
        "--package-timings",
        action="store_true",
        help="print optional package hash/copy/slate/audio/verification sub-timings",
    )
    command.add_argument(
        "--package-cache",
        type=Path,
        metavar="FOLDER",
        help="override the disposable per-user source media package cache",
    )
    return command


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.existing_project is not None and (
        not args.existing_project.strip()
        or args.existing_project != args.existing_project.strip()
        or len(args.existing_project) > 128
        or any(ord(char) < 32 for char in args.existing_project)
    ):
        print("Build refused: invalid existing project name", file=sys.stderr)
        return 2
    options = BuildOptions(
        script=args.script,
        inputs=args.inputs,
        output=args.output,
        existing_project=args.existing_project,
        package_cache=args.package_cache,
    )
    timings = StageTimings(package_detail=args.package_timings)
    try:
        completed = build_once(options, timings=timings)
        timings.finish(
            frames=completed.frames,
            numerator=completed.numerator,
            denominator=completed.denominator,
            passed=True,
        )
        print(
            "New timeline in named Studio project saved and independently verified."
            if options.existing_project is not None
            else "New Studio project saved and independently verified."
        )
        return 0
    except (BuildJobError, NeedsAction, UncertainResult) as error:
        timings.fail()
        print(f"Build refused: {error}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        timings.fail()
        print(f"Build refused: {type(error).__name__} in local inputs", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
