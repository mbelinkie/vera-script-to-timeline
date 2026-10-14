"""Independent v2 package attestation and reproducible injected release."""

from __future__ import annotations

import argparse
import platform
import shutil
import sys
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from .workflow_delivery_cli import RUNTIME_FILES as V1_RUNTIME_FILES
from .workflow_package import (
    SOURCE_PINS,
    file_inventory,
    read_object,
    sha256,
    write_immutable_json,
)

RELEASE_NAME = "vera-delivery-v2"
LAUNCHER_NAME = "VERA Delivery v2.py"
RUNTIME_FILES = (
    *V1_RUNTIME_FILES,
    "workflow_v2.py",
    "workflow_v2_launcher.py",
    "native_qualification_v2.py",
    "target_identity_v2.py",
)
BUILD_FILES = (
    "timeline-manifest.json",
    "build-report.json",
    "script-document.json",
    "compiler-dependencies.json",
    "delivery-view.json",
    "timeline.otio",
    "package-verification.json",
)


def attest_package_v2(package_root: Path, output: Path) -> Path:
    """An independent locked-runtime pass precedes the immutable handoff."""
    from .v2_package import verify_v2_package
    from .workflow_v2 import load_verified_package_v2

    if (
        platform.python_implementation() != "CPython"
        or platform.python_version() != "3.12.14"
    ):
        raise ValueError("v2 attestation requires locked CPython 3.12.14")
    _regular_directory(package_root)
    root = package_root.absolute()
    _no_symlinks(output)
    if output.resolve().is_relative_to(root) or output.exists() or output.is_symlink():
        raise ValueError("attestation must be new and outside the package")
    before = file_inventory(root)
    verified = verify_v2_package(root)
    if before != file_inventory(root):
        raise ValueError("package changed during independent verification")
    build = root / "Builds" / verified.build_id
    repository = Path(__file__).resolve().parents[2]
    verifier_sources = [
        Path("python/vera_timeline_agent/v2_package.py"),
        Path("python/vera_timeline_agent/workflow_v2.py"),
        Path("python/vera_timeline_agent/workflow_v2_cli.py"),
        Path("python/vera_timeline_agent/workflow_package.py"),
        Path("python/vera_timeline_agent/narration/models.py"),
        Path("python/vera_timeline_agent/placeholder_slate.py"),
        Path("packages/contracts/src/compiler-core.ts"),
        Path("packages/contracts/src/compiler-core-v2.ts"),
        Path("pyproject.toml"),
        Path("uv.lock"),
        *[
            Path("contracts") / name
            for name in (
                "script-document-v2.schema.json",
                "compiler-dependencies-v2.schema.json",
                "timeline-manifest-v2.schema.json",
                "build-report-v2.schema.json",
            )
        ],
    ]
    name = f"VERA Delivery {verified.build_id} {uuid.uuid4().hex[:12]}"
    value = {
        "schemaVersion": "vera-injected-delivery-attestation/v2",
        "status": "ready_to_import",
        "sourcePins": SOURCE_PINS,
        "packageDir": str(root),
        "buildId": verified.build_id,
        "projectName": name,
        "timelineName": name,
        "verifiedAt": datetime.now(UTC).isoformat(),
        "verifier": {
            "implementation": platform.python_implementation(),
            "pythonVersion": platform.python_version(),
            "sourceHashes": {
                path.as_posix(): sha256(repository / path) for path in verifier_sources
            },
        },
        "verification": {
            "eventCount": verified.event_count,
            "markerCount": verified.marker_count,
            "mediaCount": verified.media_count,
        },
        "packageFiles": before,
        "files": {name: sha256(build / name) for name in BUILD_FILES},
    }
    # Check the same runtime consumer before publishing the operator handoff.
    temporary = output.with_name(f".{output.name}-{uuid.uuid4().hex}.check")
    try:
        write_immutable_json(temporary, value)
        load_verified_package_v2(temporary, sha256(temporary))
        return write_immutable_json(output, value)
    finally:
        temporary.unlink(missing_ok=True)


def _regular_directory(path: Path) -> None:
    absolute = path.absolute()
    _no_symlinks(absolute)
    if not absolute.is_dir():
        raise ValueError("package must be a regular directory")


def _no_symlinks(path: Path) -> None:
    absolute = path.absolute()
    if any(part.is_symlink() for part in (absolute, *absolute.parents)):
        raise ValueError("symbolic link in handoff path")


def build_release_v2(output: Path) -> Path:
    """Ship only the stdlib native runtime; never install into Resolve."""
    _no_symlinks(output)
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
            "schemaVersion": "vera-injected-delivery-release/v2",
            "deliveryVersion": "2",
            "sourcePins": SOURCE_PINS,
            "files": file_inventory(output),
        },
    )
    manifest.chmod(0o444)
    return manifest


def _verify_release(root: Path) -> Path:
    _regular_directory(root)
    manifest = root / RELEASE_NAME / "release.json"
    _no_symlinks(manifest)
    value = read_object(manifest)
    if (
        set(value) != {"schemaVersion", "deliveryVersion", "sourcePins", "files"}
        or value["schemaVersion"] != "vera-injected-delivery-release/v2"
        or value["deliveryVersion"] != "2"
        or value["sourcePins"] != SOURCE_PINS
    ):
        raise ValueError("request requires a versioned v2 release")
    inventory = [
        item
        for item in file_inventory(root)
        if item["path"]
        not in {f"{RELEASE_NAME}/release.json", f"{RELEASE_NAME}/request.json"}
    ]
    source = Path(__file__).parent
    expected = {
        f"{RELEASE_NAME}/python/vera_timeline_agent/{name}": sha256(source / name)
        for name in RUNTIME_FILES
    }
    expected[LAUNCHER_NAME] = sha256(
        Path(__file__).resolve().parents[2] / "integrations/resolve" / LAUNCHER_NAME
    )
    if (
        inventory != value["files"]
        or {item["path"]: item["sha256"] for item in inventory} != expected
    ):
        raise ValueError(
            "installed release differs from the current repository-owned runtime"
        )
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
    authorize = commands.add_parser("capability-authorize")
    authorize.add_argument("--release", type=Path, required=True)
    authorize.add_argument("--approval", type=Path, required=True)
    authorize.add_argument("--operator", required=True)
    authorize.add_argument("--project-uid", required=True)
    authorize.add_argument("--timeline-uid", required=True)
    authorize.add_argument("--project-name", required=True)
    authorize.add_argument("--timeline-name", required=True)
    authorize.add_argument("--output", type=Path, required=True)
    authorize.add_argument("--evidence-dir", type=Path, required=True)
    authorize.add_argument(
        "--confirm-saved-disposable-nonproduction", action="store_true"
    )
    authorize.add_argument("--confirm-read-only", action="store_true")
    authorize.add_argument("--external-scripting-none", action="store_true")
    capability = commands.add_parser("capability-request")
    capability.add_argument("authority", type=Path)
    capability.add_argument("--output", type=Path, required=True)
    identity = commands.add_parser("identity-authorize")
    identity.add_argument("--release", type=Path, required=True)
    identity.add_argument("--installed-root", type=Path, required=True)
    identity.add_argument("--approval", type=Path, required=True)
    identity.add_argument("--operator", required=True)
    identity.add_argument("--project-name", required=True)
    identity.add_argument("--timeline-name", required=True)
    identity.add_argument("--output", type=Path, required=True)
    identity.add_argument("--evidence-dir", type=Path, required=True)
    identity.add_argument(
        "--confirm-saved-disposable-nonproduction", action="store_true"
    )
    identity.add_argument("--confirm-read-only", action="store_true")
    identity.add_argument("--external-scripting-none", action="store_true")
    identity_request = commands.add_parser("identity-request")
    identity_request.add_argument("authority", type=Path)
    identity_request.add_argument("--output", type=Path, required=True)
    from_identity = commands.add_parser("capability-authorize-from-identity")
    from_identity.add_argument("result", type=Path)
    from_identity.add_argument("--result-sha256", required=True)
    from_identity.add_argument("--acknowledge-result-sha256", required=True)
    from_identity.add_argument("--confirm-displayed-target", action="store_true")
    from_identity.add_argument("--approval", type=Path, required=True)
    from_identity.add_argument("--operator", required=True)
    from_identity.add_argument("--output", type=Path, required=True)
    from_identity.add_argument("--evidence-dir", type=Path, required=True)
    from_identity.add_argument(
        "--confirm-saved-disposable-nonproduction", action="store_true"
    )
    from_identity.add_argument("--confirm-read-only", action="store_true")
    from_identity.add_argument("--external-scripting-none", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "attest":
            output = attest_package_v2(arguments.package, arguments.output)
        elif arguments.command == "release":
            output = build_release_v2(arguments.output)
        elif arguments.command == "capability-authorize":
            from .native_qualification_v2 import create_capability_authority

            _verify_release(arguments.release)
            output = create_capability_authority(
                arguments.output.absolute(),
                release_root=arguments.release.absolute(),
                repository_root=Path(__file__).resolve().parents[2],
                target={
                    "projectUid": arguments.project_uid,
                    "timelineUid": arguments.timeline_uid,
                    "projectName": arguments.project_name,
                    "timelineName": arguments.timeline_name,
                },
                evidence_dir=arguments.evidence_dir.absolute(),
                approval_path=arguments.approval.absolute(),
                operator=arguments.operator,
                confirm_saved_disposable=arguments.confirm_saved_disposable_nonproduction,
                confirm_read_only=arguments.confirm_read_only,
                external_scripting_none=arguments.external_scripting_none,
            )
        elif arguments.command == "capability-request":
            from .native_qualification_v2 import prepare_capability_request

            output = prepare_capability_request(
                arguments.output.absolute(),
                authority_path=arguments.authority.absolute(),
            )
        elif arguments.command == "identity-authorize":
            from .target_identity_v2 import create_identity_authority

            _verify_release(arguments.release)
            output = create_identity_authority(
                arguments.output.absolute(),
                release_root=arguments.release.absolute(),
                installed_root=arguments.installed_root.absolute(),
                repository_root=Path(__file__).resolve().parents[2],
                target={
                    "projectName": arguments.project_name,
                    "timelineName": arguments.timeline_name,
                },
                evidence_dir=arguments.evidence_dir.absolute(),
                approval_path=arguments.approval.absolute(),
                operator=arguments.operator,
                confirm_saved_disposable=arguments.confirm_saved_disposable_nonproduction,
                confirm_read_only=arguments.confirm_read_only,
                external_scripting_none=arguments.external_scripting_none,
            )
        elif arguments.command == "identity-request":
            from .target_identity_v2 import prepare_identity_request

            output = prepare_identity_request(
                arguments.output.absolute(),
                authority_path=arguments.authority.absolute(),
            )
        elif arguments.command == "capability-authorize-from-identity":
            import json

            from .target_identity_v2 import (
                create_capability_authority_from_identity,
                ti_receipt,
            )

            observed, _ = ti_receipt(
                arguments.result.absolute(), arguments.result_sha256
            )
            print(
                json.dumps(
                    {
                        "resultSha256": arguments.result_sha256,
                        "target": observed["target"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            # Confirmation is an attended operator decision; no target substitution.
            if (
                input(
                    "Confirm all four displayed identifiers and the current target; "
                    "type CONFIRM: "
                )
                != "CONFIRM"
            ):
                raise ValueError("displayed target was not confirmed")
            output = create_capability_authority_from_identity(
                arguments.output.absolute(),
                result_path=arguments.result.absolute(),
                result_sha256=arguments.result_sha256,
                acknowledge_result_sha256=arguments.acknowledge_result_sha256,
                confirm_displayed_target=arguments.confirm_displayed_target,
                approval_path=arguments.approval.absolute(),
                evidence_dir=arguments.evidence_dir.absolute(),
                operator=arguments.operator,
                confirm_saved_disposable=arguments.confirm_saved_disposable_nonproduction,
                confirm_read_only=arguments.confirm_read_only,
                external_scripting_none=arguments.external_scripting_none,
            )
        else:
            from .workflow_v2 import load_verified_package_v2

            attestation = arguments.attestation.absolute()
            package = load_verified_package_v2(attestation, sha256(attestation))
            for path in (arguments.output, arguments.evidence_dir, arguments.release):
                _no_symlinks(path)
            if arguments.output.resolve().is_relative_to(
                package.root
            ) or arguments.evidence_dir.resolve().is_relative_to(package.root):
                raise ValueError("request/evidence must be outside package")
            if arguments.action == "build" and not (
                arguments.authorize_new_nonproduction
                and arguments.external_scripting_none
            ):
                raise ValueError("build requires both operator authorizations")
            release_manifest = _verify_release(arguments.release)
            output = write_immutable_json(
                arguments.output,
                {
                    "schemaVersion": "vera-injected-delivery-request/v2",
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
                    "evidenceDir": str(arguments.evidence_dir.absolute()),
                },
            )
        print(f"{output.absolute()} sha256:{sha256(output)}")
        return 0
    except Exception as error:
        print(f"Preparation refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
