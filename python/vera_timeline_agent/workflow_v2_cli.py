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
from typing import Any

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
OUTPUT_RUNTIME_FILES = (
    *RUNTIME_FILES,
    "qualification_output_native_v2.py",
    "qualification_output_records_v2.py",
)
SAMPLE_PRECISION_RUNTIME_FILES = (*RUNTIME_FILES, "sample_precision_probe_v2.py")
# The #259 import probe reuses the #257 helpers, so it ships both modules.
SAMPLE_IMPORT_RUNTIME_FILES = (
    *SAMPLE_PRECISION_RUNTIME_FILES,
    "sample_import_probe_v2.py",
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
        Path("python/vera_timeline_agent/source_audio_endpoint.py"),
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
    return _build_release(output, RUNTIME_FILES)


def build_output_release_v2(output: Path) -> Path:
    """Separately named closed output sibling; legacy release is unchanged."""
    return _build_release(output, OUTPUT_RUNTIME_FILES)


def build_sample_precision_release_v2(output: Path) -> Path:
    """Explicit finite precision experiment, separate from strict output lanes."""
    return _build_release(output, SAMPLE_PRECISION_RUNTIME_FILES)


def build_sample_import_release_v2(output: Path) -> Path:
    """Explicit finite OTIO-import experiment, separate from every other lane."""
    return _build_release(output, SAMPLE_IMPORT_RUNTIME_FILES)


def _build_release(output: Path, runtime_files: tuple[str, ...]) -> Path:
    _no_symlinks(output)
    output.mkdir(parents=True, exist_ok=False)
    runtime = output / RELEASE_NAME / "python" / "vera_timeline_agent"
    runtime.mkdir(parents=True)
    source = Path(__file__).parent
    for name in runtime_files:
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
    return _verify_release_files(root, RUNTIME_FILES)


def _verify_output_release(root: Path) -> Path:
    return _verify_release_files(root, OUTPUT_RUNTIME_FILES)


def _verify_release_files(root: Path, runtime_files: tuple[str, ...]) -> Path:
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
        for name in runtime_files
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
    output_release = commands.add_parser("output-release")
    output_release.add_argument("--output", type=Path, required=True)
    precision_release = commands.add_parser("sample-precision-release")
    precision_release.add_argument("--output", type=Path, required=True)
    precision_prepare = commands.add_parser("sample-precision-prepare")
    for name in ("release", "output", "source", "review"):
        precision_prepare.add_argument(f"--{name}", type=Path, required=True)
    for name in (
        "project-uid",
        "timeline-uid",
        "project-name",
        "timeline-name",
        "producer-authorization",
        "task-id",
    ):
        precision_prepare.add_argument(f"--{name}", required=True)
    precision_finalize = commands.add_parser("sample-precision-finalize")
    for name in ("request", "result", "output"):
        precision_finalize.add_argument(f"--{name}", type=Path, required=True)
    import_release = commands.add_parser("sample-import-release")
    import_release.add_argument("--output", type=Path, required=True)
    import_prepare = commands.add_parser("sample-import-prepare")
    for name in ("release", "output", "source", "review"):
        import_prepare.add_argument(f"--{name}", type=Path, required=True)
    for name in (
        "project-uid",
        "timeline-uid",
        "project-name",
        "timeline-name",
        "producer-authorization",
        "task-id",
    ):
        import_prepare.add_argument(f"--{name}", required=True)
    import_prepare.add_argument("--with-picture", action="store_true")
    import_finalize = commands.add_parser("sample-import-finalize")
    for name in ("request", "result", "output"):
        import_finalize.add_argument(f"--{name}", type=Path, required=True)
    output_authorize = commands.add_parser("output-authorize")
    output_authorize.add_argument("--plan", type=Path, required=True)
    output_authorize.add_argument("--output", type=Path, required=True)
    output_prepare = commands.add_parser("output-prepare")
    output_prepare.add_argument("--output", type=Path, required=True)
    output_prepare.add_argument(
        "--profile",
        choices=(
            "verified-v2-package/v1",
            "qualification-output-studio-matrix/v1",
            "qualification-output-r16-presenter-override/v1",
            "qualification-output-current-presenter/v1",
        ),
        required=True,
    )
    output_prepare.add_argument("--package", type=Path)
    output_prepare.add_argument(
        "--preparation",
        nargs=2,
        action="append",
        default=[],
        metavar=("KEY", "RECEIPT"),
    )
    output_prepare.add_argument("--project-uid", required=True)
    output_prepare.add_argument("--timeline-uid", required=True)
    output_prepare.add_argument("--project-name", required=True)
    output_prepare.add_argument("--timeline-name", required=True)
    output_prepare.add_argument("--case-id", required=True)
    output_next = commands.add_parser("output-next")
    output_next.add_argument("--session", type=Path, required=True)
    output_next.add_argument("--session-sha256", required=True)
    output_next.add_argument("--approval", type=Path, required=True)
    output_retry = commands.add_parser("output-retry")
    output_retry.add_argument("--session", type=Path, required=True)
    output_retry.add_argument("--session-sha256", required=True)
    output_retry.add_argument("--approval", type=Path, required=True)
    output_retry_plan = commands.add_parser("output-retry-plan")
    output_retry_plan.add_argument("--session", type=Path, required=True)
    output_retry_plan.add_argument("--session-sha256", required=True)
    output_retry_plan.add_argument("--output", type=Path, required=True)
    output_replan = commands.add_parser("output-replan")
    output_replan.add_argument("--session", type=Path, required=True)
    output_replan.add_argument("--session-sha256", required=True)
    output_replan.add_argument(
        "--output", "--plan", dest="output", type=Path, required=True
    )
    output_recover = commands.add_parser("output-recover")
    output_recover.add_argument("--session", type=Path, required=True)
    output_recover.add_argument("--session-sha256", required=True)
    output_ingest = commands.add_parser("output-ingest")
    output_ingest.add_argument("--session", type=Path, required=True)
    output_ingest.add_argument("--session-sha256", required=True)
    output_ingest.add_argument("--result", type=Path, required=True)
    output_ingest.add_argument("--result-sha256", required=True)
    output_finalize = commands.add_parser("output-finalize")
    output_finalize.add_argument("--session", type=Path, required=True)
    output_finalize.add_argument("--session-sha256", required=True)
    output_finalize.add_argument("--result", type=Path, required=True)
    output_finalize.add_argument("--result-sha256", required=True)
    output_edited = commands.add_parser("output-edited")
    output_edited.add_argument("--baseline-session", type=Path, required=True)
    output_edited.add_argument("--baseline-sha256", required=True)
    output_edited.add_argument("--output", type=Path, required=True)
    output_proof = commands.add_parser("output-proof")
    output_proof.add_argument("--baseline-session", type=Path, required=True)
    output_proof.add_argument("--baseline-sha256", required=True)
    output_proof.add_argument("--edited-session", type=Path, required=True)
    output_proof.add_argument("--edited-sha256", required=True)
    output_proof.add_argument("--output", type=Path, required=True)
    output_proof_step = commands.add_parser("output-proof-step")
    output_proof_step.add_argument("--session", type=Path, required=True)
    output_proof_step.add_argument("--session-sha256", required=True)
    output_proof_step.add_argument(
        "--action",
        choices=(
            "observe",
            "infer",
            "decide-inference",
            "regenerate",
            "proposal",
            "decide",
            "preflight",
        ),
        required=True,
    )
    output_proof_step.add_argument("--input", type=Path)
    output_proof_step.add_argument("--case", choices=("A", "B", "C"))
    output_proof_step.add_argument("--cache-dir", type=Path)
    output_proof_step.add_argument("--ledger", type=Path)
    output_proof_step.add_argument(
        "--aws-data-policy", choices=("provider_terms_accepted", "opt_out_confirmed")
    )
    output_proof_step.add_argument("--confirm-provider-call", action="store_true")
    output_revised = commands.add_parser("output-revised")
    output_revised.add_argument("--proof-session", type=Path, required=True)
    output_revised.add_argument("--proof-sha256", required=True)
    output_revised.add_argument("--package", type=Path, required=True)
    output_revised.add_argument(
        "--preparation",
        nargs=2,
        action="append",
        default=[],
        metavar=("KEY", "RECEIPT"),
    )
    output_revised.add_argument("--output", type=Path, required=True)
    for name in ("project-uid", "timeline-uid", "project-name", "timeline-name"):
        output_revised.add_argument("--" + name, required=True)
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
    output: Path | dict[str, Any]
    native_handoff_path: Path | None = None
    try:
        if arguments.command == "attest":
            output = attest_package_v2(arguments.package, arguments.output)
        elif arguments.command == "release":
            output = build_release_v2(arguments.output)
        elif arguments.command == "output-release":
            output = build_output_release_v2(arguments.output)
        elif arguments.command == "sample-precision-release":
            output = build_sample_precision_release_v2(arguments.output)
        elif arguments.command == "sample-precision-prepare":
            from .sample_precision_probe_v2 import prepare_probe_request

            _verify_release_files(arguments.release, SAMPLE_PRECISION_RUNTIME_FILES)
            output = prepare_probe_request(
                release_root=arguments.release.absolute(),
                output=arguments.output.absolute(),
                source=arguments.source.absolute(),
                review=arguments.review.absolute(),
                target={
                    "projectUid": arguments.project_uid,
                    "timelineUid": arguments.timeline_uid,
                    "projectName": arguments.project_name,
                    "timelineName": arguments.timeline_name,
                },
                producer_authorization=arguments.producer_authorization,
                task_id=arguments.task_id,
            )
        elif arguments.command == "sample-precision-finalize":
            from .sample_precision_compare_v2 import finalize_probe

            output = finalize_probe(
                arguments.request.absolute(),
                arguments.result.absolute(),
                arguments.output.absolute(),
            )
        elif arguments.command == "sample-import-release":
            output = build_sample_import_release_v2(arguments.output)
        elif arguments.command == "sample-import-prepare":
            from .sample_import_probe_v2 import prepare_import_request

            _verify_release_files(arguments.release, SAMPLE_IMPORT_RUNTIME_FILES)
            output = prepare_import_request(
                release_root=arguments.release.absolute(),
                output=arguments.output.absolute(),
                source=arguments.source.absolute(),
                review=arguments.review.absolute(),
                target={
                    "projectUid": arguments.project_uid,
                    "timelineUid": arguments.timeline_uid,
                    "projectName": arguments.project_name,
                    "timelineName": arguments.timeline_name,
                },
                producer_authorization=arguments.producer_authorization,
                task_id=arguments.task_id,
                with_picture=arguments.with_picture,
            )
        elif arguments.command == "sample-import-finalize":
            from .sample_import_compare_v2 import finalize_import_probe

            output = finalize_import_probe(
                arguments.request.absolute(),
                arguments.result.absolute(),
                arguments.output.absolute(),
            )
        elif arguments.command == "output-authorize":
            from .qualification_output_controller_v2 import issue_operator_approval

            output = issue_operator_approval(
                arguments.plan.absolute(), arguments.output.absolute()
            )
        elif arguments.command == "output-prepare":
            from .qualification_output_controller_v2 import prepare_output_session

            preparation_paths = {
                key: Path(path).absolute() for key, path in arguments.preparation
            }
            if len(preparation_paths) != len(arguments.preparation):
                raise ValueError("duplicate preparation requirement key")
            output = prepare_output_session(
                arguments.output.absolute(),
                profile=arguments.profile,
                package_root=(
                    None if arguments.package is None else arguments.package.absolute()
                ),
                preparation_paths=preparation_paths or None,
                target={
                    "projectUid": arguments.project_uid,
                    "timelineUid": arguments.timeline_uid,
                    "projectName": arguments.project_name,
                    "timelineName": arguments.timeline_name,
                },
                case_id=arguments.case_id,
            )
        elif arguments.command in {"output-next", "output-retry"}:
            from .qualification_output_controller_v2 import load_output_session

            controller = load_output_session(
                arguments.session.absolute(), arguments.session_sha256
            )
            output = (
                controller.prepare_render_retry_request(arguments.approval.absolute())
                if arguments.command == "output-retry"
                else controller.prepare_next_native_request(
                    arguments.approval.absolute()
                )
            )
            native_handoff_path = controller.native_operator_handoff_path(output)
        elif arguments.command in {"output-replan", "output-retry-plan"}:
            from .qualification_output_controller_v2 import load_output_session

            controller = load_output_session(
                arguments.session.absolute(), arguments.session_sha256
            )
            output = (
                controller.prepare_render_retry_plan(arguments.output.absolute())
                if arguments.command == "output-retry-plan"
                else controller.prepare_operator_replan(arguments.output.absolute())
            )
        elif arguments.command == "output-recover":
            from .qualification_output_controller_v2 import load_output_session

            controller = load_output_session(
                arguments.session.absolute(), arguments.session_sha256
            )
            output = controller.inspect_recovery()
        elif arguments.command == "output-ingest":
            from .qualification_output_controller_v2 import load_output_session

            controller = load_output_session(
                arguments.session.absolute(), arguments.session_sha256
            )
            output = controller.ingest_native_result(
                arguments.result.absolute(), arguments.result_sha256
            )
        elif arguments.command == "output-finalize":
            from .qualification_output_controller_v2 import load_output_session

            controller = load_output_session(
                arguments.session.absolute(), arguments.session_sha256
            )
            output = controller.finalize_output(
                arguments.result.absolute(), arguments.result_sha256
            )
        elif arguments.command == "output-edited":
            from .qualification_output_proof_v2 import prepare_edited_output_session

            output = prepare_edited_output_session(
                arguments.output.absolute(),
                baseline_session=arguments.baseline_session.absolute(),
                baseline_sha256=arguments.baseline_sha256,
            )
        elif arguments.command == "output-proof":
            from .qualification_output_proof_v2 import prepare_output_proof_v2

            output = prepare_output_proof_v2(
                arguments.output.absolute(),
                baseline_session=arguments.baseline_session.absolute(),
                baseline_sha256=arguments.baseline_sha256,
                edited_session=arguments.edited_session.absolute(),
                edited_sha256=arguments.edited_sha256,
            )
        elif arguments.command == "output-proof-step":
            from .qualification_output_controller_v2 import _read
            from .qualification_output_proof_v2 import QualificationOutputProofV2
            from .qualification_output_records_v2 import _parse, _shape

            proof = QualificationOutputProofV2(
                arguments.session.absolute(), arguments.session_sha256
            )
            if arguments.action == "observe":
                if arguments.case is None or arguments.input is not None:
                    raise ValueError(
                        "observe requires an isolated case and "
                        "no supplied observation JSON"
                    )
                output = proof.observe(arguments.case)
            else:
                if arguments.case is not None:
                    raise ValueError("observation arguments are only valid for observe")
                provider_flags = (
                    arguments.cache_dir,
                    arguments.ledger,
                    arguments.aws_data_policy,
                )
                if arguments.action == "regenerate":
                    if arguments.input is not None or None in provider_flags:
                        raise ValueError(
                            "regenerate requires --cache-dir, --ledger and "
                            "--aws-data-policy and takes no input file"
                        )
                    from .narration.campaign import Ledger
                    from .roundtrip_v2_narration import production_narration_service

                    handoff = proof.regenerate_row(
                        service=production_narration_service(
                            arguments.cache_dir.absolute(),
                            data_policy=arguments.aws_data_policy,
                        ),
                        ledger=Ledger(arguments.ledger.absolute()),
                        confirm_provider_call=arguments.confirm_provider_call,
                    )
                    output = (
                        {"regeneration": "not needed: no narration text changed"}
                        if handoff is None
                        else {
                            "regeneration": "handoff retained",
                            "handoff": str(
                                proof.root / "regeneration" / "row-handoff.json"
                            ),
                        }
                    )
                elif any(provider_flags) or arguments.confirm_provider_call:
                    raise ValueError("provider flags are only valid for regenerate")
                elif arguments.action in {"infer", "preflight"}:
                    if arguments.input is not None:
                        raise ValueError(
                            "this operation does not accept supplied inputs"
                        )
                    output = (
                        proof.infer()
                        if arguments.action == "infer"
                        else proof.prepare_revised_preflight()
                    )
                elif arguments.action == "proposal" and arguments.input is None:
                    output = proof.proposal()
                else:
                    if arguments.input is None:
                        raise ValueError(
                            "explicit decision/proposal input file required"
                        )
                    supplied = _parse(_read(arguments.input.absolute()))
                    if arguments.action == "decide-inference":
                        output = proof.decide_inference(supplied)
                    elif arguments.action == "decide":
                        output = proof.decide(supplied)
                    else:
                        _shape(supplied, "preparedMedia handoff", "proposal inputs")
                        output = proof.proposal(
                            prepared_media=supplied["preparedMedia"],
                            handoff=supplied["handoff"],
                        )
        elif arguments.command == "output-revised":
            from .qualification_output_proof_v2 import prepare_revised_output_session

            preparations = {
                key: Path(path).absolute() for key, path in arguments.preparation
            }
            if len(preparations) != len(arguments.preparation):
                raise ValueError("duplicate preparation requirement key")
            output = prepare_revised_output_session(
                arguments.output.absolute(),
                proof_session=arguments.proof_session.absolute(),
                proof_sha256=arguments.proof_sha256,
                package_root=arguments.package.absolute(),
                preparation_paths=preparations,
                target={
                    "projectUid": arguments.project_uid,
                    "timelineUid": arguments.timeline_uid,
                    "projectName": arguments.project_name,
                    "timelineName": arguments.timeline_name,
                },
            )
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
                    "externalScripting": (
                        "None" if arguments.external_scripting_none else None
                    ),
                    "evidenceDir": str(arguments.evidence_dir.absolute()),
                },
            )
        if isinstance(output, Path):
            print(f"{output.absolute()} sha256:{sha256(output)}")
            if arguments.command in {
                "output-prepare",
                "output-edited",
                "output-revised",
            }:
                plan = output.parent / "operator-plan.json"
                print(f"{plan.absolute()} sha256:{sha256(plan)}")
            elif arguments.command in {"output-next", "output-retry"}:
                if native_handoff_path is None:
                    raise ValueError("native operator handoff is missing")
                print(
                    f"{native_handoff_path.absolute()} "
                    f"sha256:{sha256(native_handoff_path)}"
                )
        else:
            import json

            print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    except Exception as error:
        print(f"Preparation refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
