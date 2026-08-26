"""CLI for the retained pinned-Text+ Resolve capability validation."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .studio_spike import StudioSpikeError
from .text_plus_template import TemplateValidationError
from .text_plus_validation import run_text_plus_validation


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--action", choices=("preflight", "build"), required=True)
    value.add_argument("--project-name", required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        result = run_text_plus_validation(
            action=arguments.action,
            project_name=arguments.project_name,
        )
    except (OSError, StudioSpikeError, TemplateValidationError, ValueError) as error:
        print(f"Text+ validation failed safely: {error}", file=sys.stderr)
        return 2
    sys.stdout.write(result.to_json())
    return 0 if result.status in {"preflight_passed", "verified"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
