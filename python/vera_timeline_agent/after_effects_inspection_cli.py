"""Run the read-only After Effects inspection workflow and emit JSON evidence."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .after_effects_inspection import (
    AfterEffectsInspectionError,
    inspect_after_effects_project,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("project", type=Path, help="read-only .aep source path")
    value.add_argument("--collection-report", type=Path)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        report = inspect_after_effects_project(
            arguments.project, collection_report=arguments.collection_report
        )
    except (AfterEffectsInspectionError, OSError) as error:
        print(f"After Effects inspection failed safely: {error}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
