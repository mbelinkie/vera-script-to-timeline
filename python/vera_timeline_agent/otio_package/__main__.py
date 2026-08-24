"""Command-line entry point for the bounded Slice 0.2 package writer."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .package import PackageBuildError, build_otio_package


def parser() -> argparse.ArgumentParser:
    """Create the package-writer argument parser."""
    value = argparse.ArgumentParser(
        description=(
            "Convert a schema-valid TimelineManifest v1 into a verified, "
            "self-contained OTIO import package."
        )
    )
    value.add_argument("manifest", type=Path, help="TimelineManifest v1 JSON file")
    value.add_argument(
        "--media-root",
        required=True,
        type=Path,
        help="directory against which manifest media paths are resolved",
    )
    value.add_argument(
        "--output",
        required=True,
        type=Path,
        help="new output directory; an existing path is never replaced",
    )
    return value


def main(argv: Sequence[str] | None = None) -> int:
    """Build one package and report the parse-verification result."""
    arguments = parser().parse_args(argv)
    try:
        result = build_otio_package(
            arguments.manifest,
            arguments.media_root,
            arguments.output,
        )
    except PackageBuildError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Ready verified OTIO import package: {result.output_dir}")
    print(
        f"Verified {result.event_count} events, {result.marker_count} marker, "
        f"and {result.media_count} media files."
    )
    print(f"Read import instructions: {result.instructions_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
