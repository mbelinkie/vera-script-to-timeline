"""Command-line interface for the Slice 1.4 Resolve import package."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .package import ResolveImportPackageError, build_resolve_import_package


def parser() -> argparse.ArgumentParser:
    """Create the package-writer argument parser."""
    value = argparse.ArgumentParser(
        description=(
            "Materialize a compiler manifest/report into one verified Resolve Free "
            "Authoring Project."
        )
    )
    value.add_argument("manifest", type=Path, help="canonical TimelineManifest v1 JSON")
    value.add_argument(
        "report", type=Path, help="matching canonical BuildReport v1 JSON"
    )
    value.add_argument(
        "materialization_plan",
        type=Path,
        help="internal sourceId-keyed artifactId/origin/policy JSON",
    )
    value.add_argument(
        "--output",
        required=True,
        type=Path,
        help="new Authoring Project root, or the exact verified result to reuse",
    )
    value.add_argument(
        "--ffprobe",
        default="ffprobe",
        help="FFprobe executable used for media verification",
    )
    return value


def main(argv: Sequence[str] | None = None) -> int:
    """Build one verified project and print a stable JSON result."""
    arguments = parser().parse_args(argv)
    try:
        result = build_resolve_import_package(
            arguments.manifest,
            arguments.report,
            arguments.materialization_plan,
            arguments.output,
            ffprobe_executable=arguments.ffprobe,
        )
    except ResolveImportPackageError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "ready_to_import",
                "buildId": result.build_id,
                "projectRoot": str(result.project_root),
                "buildRoot": str(result.build_root),
                "verificationReceipt": str(result.verification_path),
                "reused": result.reused,
                "eventCount": result.event_count,
                "markerCount": result.marker_count,
                "mediaCount": result.media_count,
            },
            sort_keys=True,
        )
    )
    return 0
