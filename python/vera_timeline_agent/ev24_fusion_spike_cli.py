"""Run the bounded EV24 Fusion semantic-input capability spike."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .ev24_fusion_spike import Ev24SpikeError, run_ev24_spike
from .studio_spike import StudioSpikeError


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--action", choices=("preflight", "build"), required=True)
    value.add_argument("--project-name", required=True)
    value.add_argument("--report", type=Path)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        result = run_ev24_spike(
            action=arguments.action,
            project_name=arguments.project_name,
        )
        payload = result.to_json()
        if arguments.report is not None:
            if arguments.report.exists():
                raise Ev24SpikeError(
                    f"refusing to overwrite retained evidence: {arguments.report}"
                )
            arguments.report.write_text(payload, encoding="utf-8")
        sys.stdout.write(payload)
        return 0 if result.status in {"preflight_passed", "verified"} else 2
    except (Ev24SpikeError, StudioSpikeError, OSError, ValueError) as error:
        print(f"EV24 capability spike stopped safely: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
