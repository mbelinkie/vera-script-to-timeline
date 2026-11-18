"""Build one VERA v2 script in Resolve Studio (foreground command)."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from .build_music_warnings import publish_latest_music_warnings
from .build_jobs import BuildJobError, NeedsAction, UncertainResult
from .build_timeline_once import BuildOptions, StageTimings, build_once


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--script", type=Path, help="v2 script JSON")
    command.add_argument(
        "--inputs", type=Path, help="directory of previously prepared v2 inputs"
    )
    command.add_argument(
        "--output", type=Path, help="new, unused local output directory"
    )
    command.add_argument(
        "--publish-report",
        type=Path,
        help="publish a successful build report without rebuilding the timeline",
    )
    command.add_argument(
        "--existing-project", help="add a new timeline to this named project"
    )
    command.add_argument(
        "--resolve-app",
        type=Path,
        metavar="BUNDLE.app",
        help="select a Resolve Studio app bundle (default: standard installation)",
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
    command = parser()
    args = command.parse_args(argv)
    if args.publish_report is not None:
        if args.script is not None or args.output is not None:
            command.error(
                "--publish-report cannot be combined with --script or --output"
            )
        published, reason = publish_latest_music_warnings(args.publish_report)
        if published:
            print("Latest build warnings published in VERA.")
            return 0
        print(f"Build report was not published to VERA: {reason}", file=sys.stderr)
        return 3
    if args.script is None or args.output is None:
        command.error("--script and --output are required for a Resolve build")
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
        resolve_app=args.resolve_app,
    )
    timings = StageTimings(package_detail=args.package_timings)
    try:
        completed = build_once(options, timings=timings)
        for warning in completed.named_transition_cuts:
            print(f"Named transition built as cut_insufficient_handles: {warning}")
        for warning in completed.music_warnings:
            print(f"Music warning: {warning}")
        for event_id, outcome in completed.bar_removal_outcomes:
            print(f"Black bar removal for {event_id}: {outcome}")
        token_configured = bool(os.environ.get("VERA_STT_QA_AUTHORING_TOKEN"))
        if token_configured:
            published, publish_reason = publish_latest_music_warnings(
                options.output / "build-report.json"
            )
        elif completed.music_warnings:
            published, publish_reason = (
                False,
                "VERA_STT_QA_AUTHORING_TOKEN is not set to the local authoring token",
            )
        else:
            published, publish_reason = True, ""
        timings.finish(
            frames=completed.frames,
            numerator=completed.numerator,
            denominator=completed.denominator,
            passed=True,
        )
        if not published:
            print(
                "Resolve timeline was built and saved, but its music warnings were not "
                f"published to VERA: {publish_reason}. Do not rerun; retry with "
                f"--publish-report {options.output / 'build-report.json'}.",
                file=sys.stderr,
            )
            return 3
        if token_configured:
            print("Latest build warnings published in VERA.")
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
