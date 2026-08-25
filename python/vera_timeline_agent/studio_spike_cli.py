"""Command-line interface for the bounded Resolve Studio scripting spike."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from vera_timeline_agent.otio_package import PackageBuildError

from .studio_spike import StudioSpikeError, detect_local_capabilities, run_delivery


def parser() -> argparse.ArgumentParser:
    """Build the Slice 0.4 argument parser."""
    value = argparse.ArgumentParser(description=__doc__)
    commands = value.add_subparsers(dest="command", required=True)
    detect = commands.add_parser("detect", help="detect local facts without connecting")
    detect.add_argument("--app-path", type=Path)
    delivery = commands.add_parser("run", help="verify package and preflight/build")
    delivery.add_argument("package", type=Path)
    delivery.add_argument("--mode", choices=("free", "studio"), required=True)
    delivery.add_argument(
        "--action", choices=("preflight", "build"), default="preflight"
    )
    delivery.add_argument("--project-name")
    delivery.add_argument("--fusion-title", default="Text+")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    """Run detection or the fail-closed delivery workflow."""
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "detect":
            facts = detect_local_capabilities(
                app_path=arguments.app_path
                if arguments.app_path is not None
                else Path("/Applications/DaVinci Resolve/DaVinci Resolve.app")
            )
            import json
            from dataclasses import asdict

            sys.stdout.write(json.dumps(asdict(facts), indent=2, sort_keys=True) + "\n")
            return 0
        result = run_delivery(
            arguments.package,
            arguments.mode,
            action=arguments.action,
            project_name=arguments.project_name,
            fusion_title=arguments.fusion_title,
        )
        sys.stdout.write(result.to_json())
        return (
            0
            if result.status
            not in {"stopped_safely", "mutation_failed", "verification_failed"}
            else 2
        )
    except (PackageBuildError, StudioSpikeError, OSError, ValueError) as error:
        print(f"Slice 0.4 failed safely: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
