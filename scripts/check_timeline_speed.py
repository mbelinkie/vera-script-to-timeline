"""Build two prepared scripts in Resolve and compare each build with its duration."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

STAGE = re.compile(r"^(.+): (PASS|FAIL) \(([0-9.]+)s\)$")
DURATION = re.compile(r"^PASS: \d+ frames \(([0-9.]+)s timeline\); total ([0-9.]+)s$")


def run_case(name: str, script: Path, inputs: Path, output: Path) -> bool:
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
    stages = {}
    duration = total = None
    for line in process.stdout.splitlines():
        stage = STAGE.fullmatch(line)
        if stage and stage[2] == "PASS":
            stages[stage[1]] = float(stage[3])
        match = DURATION.fullmatch(line)
        if match:
            duration = float(match[1])
            total = float(match[2])
    elapsed = stages.get("Resolve step + check")
    if stages:
        print("| Stage | Seconds |")
        print("| --- | ---: |")
        for stage_name, seconds in stages.items():
            print(f"| {stage_name} | {seconds:.2f} |")
    if (
        process.returncode
        or elapsed is None
        or duration is None
        or total is None
        or duration <= 0
    ):
        print(f"{name}: FAIL — build or verification did not complete")
        return False
    # The command prints rounded values; do not pass a borderline result.
    passed = total + 0.005 < duration - 0.0005
    print("| Case | Timeline (s) | Resolve + check (s) | Total (s) | Result |")
    print("| --- | ---: | ---: | ---: | --- |")
    print(
        f"| {name} | {duration:.3f} | {elapsed:.2f} | {total:.2f} | "
        f"{'PASS' if passed else 'FAIL'} |"
    )
    return passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for case in ("short", "long"):
        parser.add_argument(f"--{case}-script", type=Path, required=True)
        parser.add_argument(f"--{case}-inputs", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, required=True, help="unused output directory"
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output directory must not already exist")
    args.output.mkdir(parents=True)
    for name in ("short", "long"):
        if not run_case(
            name,
            getattr(args, f"{name}_script"),
            getattr(args, f"{name}_inputs"),
            args.output / name,
        ):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
