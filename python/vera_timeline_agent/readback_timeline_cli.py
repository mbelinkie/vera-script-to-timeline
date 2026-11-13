"""Read and compare the already open Resolve timeline to a checked VERA build."""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from .build_jobs import NeedsAction
from .build_timeline_once import _external_resolve, exclusive_resolve_build
from .row_timeline_map import compare_reopened_row_map
from .workflow_v2 import (
    VerifiedPackageV2,
    _read_regular,
    _regular_absolute,
    _strict_object,
    load_verified_package_v2,
    observe_current_timeline_v2,
)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument(
        "--output", type=Path, required=True, help="existing checked build results"
    )
    command.add_argument(
        "--project",
        help="exact currently open project name for a mapless existing-project build",
    )
    return command


def _load_readback_package(root: Path) -> VerifiedPackageV2:
    attestation_path = root / "v2-attestation.json"
    raw_attestation = _read_regular(
        attestation_path, "build attestation", max_bytes=16 * 1024 * 1024
    )
    return load_verified_package_v2(
        attestation_path, hashlib.sha256(raw_attestation).hexdigest()
    )


def _read_saved_row_map(root: Path) -> dict[str, Any] | None:
    path = root / "row-timeline-map.json"
    if not path.exists() and not path.is_symlink():
        return None
    return _strict_object(
        _read_regular(path, "saved row map", max_bytes=16 * 1024 * 1024),
        "saved row map",
    )


def readback_output(
    output: Path,
    *,
    project: str | None = None,
    resolve_factory: Callable[[], Any] | None = None,
) -> str:
    """Inspect package + SDK without selecting, saving or modifying Resolve."""
    if project is not None and (
        not project.strip()
        or project != project.strip()
        or len(project) > 128
        or any(ord(character) < 32 for character in project)
    ):
        raise ValueError("invalid --project name")
    root = _regular_absolute(output.absolute(), "build output", directory=True)
    package = _load_readback_package(root)
    saved = _read_saved_row_map(root)
    if saved is not None:
        expected_project = saved.get("projectName")
        if (
            not isinstance(expected_project, str)
            or not expected_project.strip()
            or (project is not None and project != expected_project)
        ):
            raise ValueError("--project differs from saved map project target")
        for key in ("resolveProjectId", "timelineId"):
            if not isinstance(saved.get(key), str) or not saved[key].strip():
                raise ValueError(f"saved row map has missing or invalid {key}")
    else:
        expected_project = project or package.attestation["projectName"]
    expected_timeline = package.attestation["timelineName"]
    if saved is not None and saved.get("timelineName") != expected_timeline:
        raise ValueError("saved map timeline name differs from attested build")

    # Coordinate with the build's single native lock, without touching the
    # current project or timeline. Another active native job is a refusal.
    with exclusive_resolve_build():
        snapshot = observe_current_timeline_v2(
            (resolve_factory or _external_resolve)(),
            package.view,
            project_name=expected_project,
            timeline_name=expected_timeline,
            project_uid=saved["resolveProjectId"] if saved is not None else None,
            timeline_uid=saved["timelineId"] if saved is not None else None,
            transition_plans=package.manifest.get("transitions", ()),
        )
    result = compare_reopened_row_map(
        package.manifest,
        package.view,
        snapshot["observed"],
        project_name=snapshot["projectName"],
        resolve_project_id=snapshot["resolveProjectId"],
        timeline_name=snapshot["timelineName"],
        timeline_id=snapshot["timelineId"],
        saved_map=saved,
    )
    if result == "saved-uid-match":
        return "PASS: current Resolve target, events, rows and saved item UIDs match"
    return (
        "PASS: current Resolve timeline structurally matches attested view "
        "(no saved map; prior item UID continuity not checked)"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        print(readback_output(args.output, project=args.project))
        return 0
    except (ValueError, OSError, NeedsAction) as error:
        print(f"MISMATCH: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        # Resolve may be closed or its local SDK unavailable. Never attempt
        # to open/change a project and never treat an SDK error as a match.
        print(
            f"MISMATCH: Resolve readback unavailable ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
