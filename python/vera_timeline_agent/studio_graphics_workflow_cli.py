"""Locked external preparation for EV24 injected delivery; never installs."""

from __future__ import annotations

import argparse
import platform
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from .studio_graphics_workflow import (
    GRAPHIC_ATTESTATION,
    GRAPHIC_PINS,
    GRAPHIC_REQUEST,
    load_graphic_handoff,
)
from .workflow_delivery_cli import RUNTIME_FILES, attest_package
from .workflow_package import file_inventory, read_object, sha256, write_immutable_json

RELEASE_NAME = "vera-graphics-v1"
LAUNCHER_NAME = "VERA Graphics v1.py"
GRAPHICS_RUNTIME_FILES = (
    "ev24_fusion_spike.py",
    "studio_graphics_runtime.py",
    "studio_graphics_workflow.py",
    "studio_graphics_launcher.py",
)


def attest_graphic_package(package_root: Path, output: Path) -> Path:
    from .studio_graphics import verify_studio_graphic_package

    if platform.python_implementation() != "CPython" or sys.version_info[:2] != (3, 12):
        raise ValueError("preparation requires locked CPython 3.12")
    if package_root.is_symlink():
        raise ValueError("Studio package cannot be a symbolic link")
    root = package_root.resolve(strict=True)
    if output.resolve().is_relative_to(root):
        raise ValueError("attestation must be outside the Studio package")
    before = file_inventory(root)
    verify_studio_graphic_package(root)
    if file_inventory(root) != before:
        raise ValueError("Studio package changed during independent verification")
    output.mkdir(parents=True, exist_ok=False)
    transport = attest_package(root / "Transport", output / "transport.json")
    value = read_object(transport)
    if file_inventory(root) != before:
        raise ValueError("Studio package changed during transport verification")
    result = write_immutable_json(
        output / "graphic.json",
        {
            **{
                key: value[key]
                for key in (
                    "buildId",
                    "projectName",
                    "timelineName",
                    "verifier",
                    "verifiedAt",
                )
            },
            "schemaVersion": GRAPHIC_ATTESTATION,
            "sourcePins": GRAPHIC_PINS,
            "status": "ready_for_studio",
            "packageDir": str(root),
            "packageFiles": before,
            "transportAttestationPath": str(transport.resolve()),
            "transportAttestationSha256": sha256(transport),
        },
    )
    load_graphic_handoff(result, sha256(result))
    return result


def build_graphics_release(output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=False)
    runtime = output / RELEASE_NAME / "python/vera_timeline_agent"
    runtime.mkdir(parents=True)
    source = Path(__file__).parent
    for name in (*RUNTIME_FILES, *GRAPHICS_RUNTIME_FILES):
        shutil.copyfile(source / name, runtime / name)
    shutil.copyfile(
        source.parents[1] / "integrations/resolve" / LAUNCHER_NAME,
        output / LAUNCHER_NAME,
    )
    manifest = write_immutable_json(
        output / RELEASE_NAME / "release.json",
        {
            "schemaVersion": "vera-injected-delivery-release/v1",
            "deliveryVersion": "1",
            "sourcePins": GRAPHIC_PINS,
            "files": file_inventory(output),
        },
    )
    manifest.chmod(0o444)
    return manifest


def prepare_graphic_request(
    attestation: Path,
    release: Path,
    output: Path,
    evidence: Path,
    *,
    action: str = "preflight",
    authorize_new_nonproduction: bool = False,
    external_scripting_none: bool = False,
) -> Path:
    attestation = attestation.resolve(strict=True)
    package = load_graphic_handoff(attestation, sha256(attestation))
    if output.resolve().is_relative_to(
        package.root
    ) or evidence.resolve().is_relative_to(package.root):
        raise ValueError("request/evidence must be outside the Studio package")
    if action not in {"preflight", "build"}:
        raise ValueError("unsupported graphic action")
    if action == "build" and not (
        authorize_new_nonproduction and external_scripting_none
    ):
        raise ValueError("build requires both operator authorizations")
    return write_immutable_json(
        output,
        {
            "schemaVersion": GRAPHIC_REQUEST,
            "releaseSha256": sha256(release / RELEASE_NAME / "release.json"),
            "attestationPath": str(attestation),
            "attestationSha256": sha256(attestation),
            "packageDir": str(package.root),
            "projectName": package.attestation["projectName"],
            "timelineName": package.attestation["timelineName"],
            "action": action,
            "authorizeNewNonproduction": authorize_new_nonproduction,
            "externalScripting": "None" if external_scripting_none else None,
            "evidenceDir": str(evidence.resolve()),
        },
    )


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
    args = parser.parse_args(argv)
    try:
        if args.command == "attest":
            path = attest_graphic_package(args.package, args.output)
        elif args.command == "release":
            path = build_graphics_release(args.output)
        else:
            path = prepare_graphic_request(
                args.attestation,
                args.release,
                args.output,
                args.evidence_dir,
                action=args.action,
                authorize_new_nonproduction=args.authorize_new_nonproduction,
                external_scripting_none=args.external_scripting_none,
            )
        print(f"{path.resolve()} sha256:{sha256(path)}")
        return 0
    except Exception as error:
        print(f"Graphics preparation refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
