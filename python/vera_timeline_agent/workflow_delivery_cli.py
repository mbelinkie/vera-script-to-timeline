"""Locked-runtime preparation only; never connects to or installs into Resolve."""

from __future__ import annotations

import argparse
import platform
import shutil
import sys
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from .workflow_package import (
    ATTESTATION_SCHEMA,
    SOURCE_PINS,
    WorkflowPackageError,
    file_inventory,
    load_verified_package,
    sha256,
    write_immutable_json,
)

RELEASE_NAME = "vera-delivery-v1"
LAUNCHER_NAME = "VERA Delivery v1.py"
RUNTIME_FILES = (
    "__init__.py",
    "studio_spike.py",
    "text_plus_template.py",
    "workflow_package.py",
    "workflow_delivery.py",
    "workflow_launcher.py",
)


def attest_package(package_root: Path, output: Path) -> Path:
    """Verify independently, then bind stable bytes to a fresh unique target."""
    from .resolve_import_package import verify_resolve_import_package

    if package_root.is_symlink():
        raise WorkflowPackageError("package root must not be a symbolic link")
    root = package_root.resolve(strict=True)
    if output.resolve().is_relative_to(root) or output.exists():
        raise WorkflowPackageError("attestation must be new and outside package")
    if platform.python_implementation() != "CPython" or sys.version_info[:2] != (3, 12):
        raise WorkflowPackageError("preparation requires locked CPython 3.12")
    before = file_inventory(root)
    verification = verify_resolve_import_package(root)
    if before != file_inventory(root):
        raise WorkflowPackageError("package changed during independent verification")
    name = f"VERA Delivery {verification.build_id} {uuid.uuid4().hex[:12]}"
    return write_immutable_json(
        output,
        {
            "schemaVersion": ATTESTATION_SCHEMA,
            "status": "ready_to_import",
            "sourcePins": SOURCE_PINS,
            "packageDir": str(root),
            "buildId": verification.build_id,
            "projectName": name,
            "timelineName": name,
            "verifiedAt": datetime.now(UTC).isoformat(),
            "verifier": {
                "implementation": platform.python_implementation(),
                "pythonVersion": platform.python_version(),
            },
            "verification": {
                "eventCount": verification.event_count,
                "markerCount": verification.marker_count,
                "mediaCount": verification.media_count,
            },
            "packageFiles": before,
        },
    )


def build_release(output: Path) -> Path:
    """Copy only stdlib runtime source; inventory is deterministic for a revision."""
    output.mkdir(parents=True, exist_ok=False)
    runtime = output / RELEASE_NAME / "python" / "vera_timeline_agent"
    runtime.mkdir(parents=True)
    source = Path(__file__).parent
    for name in RUNTIME_FILES:
        shutil.copyfile(source / name, runtime / name)
    launcher = (
        Path(__file__).resolve().parents[2] / "integrations/resolve" / LAUNCHER_NAME
    )
    shutil.copyfile(launcher, output / LAUNCHER_NAME)
    manifest = write_immutable_json(
        output / RELEASE_NAME / "release.json",
        {
            "schemaVersion": "vera-injected-delivery-release/v1",
            "deliveryVersion": "1",
            "sourcePins": SOURCE_PINS,
            "files": file_inventory(output),
        },
    )
    # Public source inventory must remain readable after administrator installation.
    manifest.chmod(0o444)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    attest = commands.add_parser("attest")
    attest.add_argument("package", type=Path)
    attest.add_argument("--output", type=Path, required=True)
    release = commands.add_parser("release")
    release.add_argument("--output", type=Path, required=True)
    request = commands.add_parser("request")
    request.add_argument("attestation", type=Path)
    request.add_argument("--release", type=Path, required=True)
    request.add_argument("--output", type=Path, required=True)
    request.add_argument("--evidence-dir", type=Path, required=True)
    request.add_argument(
        "--action", choices=("preflight", "build"), default="preflight"
    )
    request.add_argument("--authorize-new-nonproduction", action="store_true")
    request.add_argument("--external-scripting-none", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "attest":
            output = attest_package(arguments.package, arguments.output)
        elif arguments.command == "release":
            output = build_release(arguments.output)
        else:
            attestation = arguments.attestation.resolve(strict=True)
            package = load_verified_package(attestation, sha256(attestation))
            if arguments.output.resolve().is_relative_to(
                package.root
            ) or arguments.evidence_dir.resolve().is_relative_to(package.root):
                raise WorkflowPackageError("request/evidence must be outside package")
            if arguments.action == "build" and not (
                arguments.authorize_new_nonproduction
                and arguments.external_scripting_none
            ):
                raise WorkflowPackageError(
                    "build requires both operator authorizations"
                )
            release_manifest = arguments.release / RELEASE_NAME / "release.json"
            output = write_immutable_json(
                arguments.output,
                {
                    "schemaVersion": "vera-injected-delivery-request/v1",
                    "releaseSha256": sha256(release_manifest),
                    "attestationPath": str(attestation),
                    "attestationSha256": sha256(attestation),
                    "packageDir": str(package.root),
                    "projectName": package.attestation["projectName"],
                    "timelineName": package.attestation["timelineName"],
                    "action": arguments.action,
                    "authorizeNewNonproduction": arguments.authorize_new_nonproduction,
                    "externalScripting": "None"
                    if arguments.external_scripting_none
                    else None,
                    "evidenceDir": str(arguments.evidence_dir.resolve()),
                },
            )
        print(f"{output.resolve()} sha256:{sha256(output)}")
        return 0
    except Exception as error:
        print(f"Preparation refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
