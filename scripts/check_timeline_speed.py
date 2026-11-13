"""Build two prepared scripts in Resolve and compare each build with its duration."""

import argparse
import math
import re
import subprocess
import sys
from pathlib import Path

STAGE = re.compile(r"^(.+): (PASS|FAIL) \(([0-9.]+)s\)$")
FRAME_COUNT = re.compile(r"^PASS: ([0-9]+) frames ")
DURATION = re.compile(r"^PASS: \d+ frames \(([0-9.]+)s timeline\); total ([0-9.]+)s$")


def run_case(
    name: str, script: Path, inputs: Path, output: Path
) -> tuple[float, float, bool] | None:
    command = [
        sys.executable,
        "-m",
        "vera_timeline_agent.build_timeline_cli",
        "--script",
        str(script),
        "--inputs",
        str(inputs),
        "--output",
        str(output),
    ]
    print(f"\n{name}", flush=True)
    process = subprocess.run(
        command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    print(process.stdout, end="", flush=True)
    resolve_check_passed = False
    frame_count = None
    duration = total = None
    for line in process.stdout.splitlines():
        stage = STAGE.fullmatch(line)
        if stage and stage[1] == "Resolve step + check" and stage[2] == "PASS":
            resolve_check_passed = True
        frame_match = FRAME_COUNT.match(line)
        if frame_match:
            frame_count = int(frame_match[1])
        match = DURATION.fullmatch(line)
        if match:
            duration = float(match[1])
            total = float(match[2])
    if (
        process.returncode
        or not resolve_check_passed
        or frame_count is None
        or duration is None
        or total is None
        or not math.isfinite(duration)
        or not math.isfinite(total)
        or duration <= 0
        or total < 0
        or not math.isclose(frame_count / 24, duration, rel_tol=0.0, abs_tol=0.0005)
    ):
        print(f"{name}: FAIL — build or verification did not complete")
        return None
    # The command prints rounded values; do not pass a borderline result.
    passed = total + 0.005 < duration - 0.0005
    return duration, total, passed


def print_results(
    results: list[tuple[str, float, float | None, float | None, bool]],
) -> None:
    print("\n24 fps timeline speed check")
    print("| Case | Preparation (s) | Timeline (s) | Build plus check (s) | Result |")
    print("| --- | ---: | ---: | ---: | --- |")
    for name, preparation, duration, total, passed in results:
        timeline = f"{duration:.3f}" if duration is not None else "—"
        command_total = f"{total:.2f}" if total is not None else "—"
        print(
            f"| {name} | {preparation:.2f} | {timeline} | {command_total} | "
            f"{'PASS' if passed else 'FAIL'} |"
        )
    print("This check does not cover the default 23.976 fps route.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for case in ("short", "long"):
        parser.add_argument(f"--{case}-script", type=Path, required=True)
        parser.add_argument(f"--{case}-inputs", type=Path, required=True)
        parser.add_argument(
            f"--{case}-preparation-seconds",
            type=float,
            required=True,
            help=(
                "elapsed offline input-preparation seconds (shown, excluded from gate)"
            ),
        )
    parser.add_argument(
        "--output", type=Path, required=True, help="new root for each Resolve result"
    )
    args = parser.parse_args()
    for case in ("short", "long"):
        seconds = getattr(args, f"{case}_preparation_seconds")
        if not math.isfinite(seconds) or seconds < 0:
            parser.error(f"--{case}-preparation-seconds must be finite and nonnegative")
    if args.output.exists():
        parser.error("output directory must not already exist")
    args.output.mkdir(parents=True)
    passed = True
    results: list[tuple[str, float, float | None, float | None, bool]] = []
    for name in ("short", "long"):
        preparation = getattr(args, f"{name}_preparation_seconds")
        result = run_case(
            name,
            getattr(args, f"{name}_script"),
            getattr(args, f"{name}_inputs"),
            args.output / name,
        )
        if result is None:
            results.append((name, preparation, None, None, False))
            print_results(results)
            return 1
        duration, total, case_passed = result
        results.append((name, preparation, duration, total, case_passed))
        passed = passed and case_passed
    print_results(results)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
