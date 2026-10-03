"""Create the retained synthetic package for Studio assembly acceptance."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from vera_timeline_agent.resolve_import_package import ResolveImportPackageError

from .studio_assembly_acceptance import build_studio_assembly_acceptance_package


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--output", type=Path, required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        result = build_studio_assembly_acceptance_package(arguments.output)
    except ResolveImportPackageError as error:
        print(f"Acceptance package was not created: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": "ready_to_import",
                "projectRoot": str(result.project_root),
                "buildId": result.build_id,
                "verificationReceipt": str(result.verification_path),
                "reused": result.reused,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
