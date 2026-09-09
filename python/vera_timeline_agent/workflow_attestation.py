"""Standard-library boundary for externally verified Resolve package input."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

SCHEMA_VERSION = "vera-workflow-package-attestation-v1"
REQUIRED_PACKAGE_FILES = frozenset(
    {
        "IMPORT_INSTRUCTIONS.md",
        "build-report.json",
        "timeline-manifest.json",
        "timeline.otio",
    }
)


class WorkflowAttestationError(ValueError):
    """The external verification attestation is missing or no longer matches."""


@dataclass(frozen=True)
class VerifiedWorkflowPackage:
    """Package input whose bytes still match an external verification pass."""

    package_dir: Path
    project_name: str
    manifest: dict[str, Any]
    verification: dict[str, int]
    verifier: dict[str, str]
    verified_at: str


def write_workflow_attestation(
    package_dir: Path,
    output_path: Path,
    *,
    project_name: str,
    verification: Mapping[str, int],
) -> Path:
    """Bind a successful external package verification to exact package bytes."""
    package_root = package_dir.resolve(strict=True)
    output = output_path.resolve()
    if output.is_relative_to(package_root):
        raise WorkflowAttestationError(
            "workflow attestation must be stored outside the verified package"
        )
    _require_project_name(project_name)
    files = _package_files(package_root)
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "packageDir": str(package_root),
        "projectName": project_name,
        "verifiedAt": datetime.now(UTC).isoformat(),
        "verifier": {
            "implementation": platform.python_implementation(),
            "pythonVersion": platform.python_version(),
        },
        "verification": dict(verification),
        "packageFiles": files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", dir=output.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def load_verified_workflow_package(attestation_path: Path) -> VerifiedWorkflowPackage:
    """Recheck attested bytes without importing VERA's external verifier stack."""
    value = _read_object(attestation_path, "workflow attestation")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        raise WorkflowAttestationError("unsupported workflow attestation schema")
    package_value = value.get("packageDir")
    if not isinstance(package_value, str) or not Path(package_value).is_absolute():
        raise WorkflowAttestationError("packageDir must be an absolute path")
    package_root = Path(package_value).resolve(strict=True)
    project_name = value.get("projectName")
    if not isinstance(project_name, str):
        raise WorkflowAttestationError("projectName must be a string")
    _require_project_name(project_name)
    expected_files = value.get("packageFiles")
    if not isinstance(expected_files, list) or not expected_files:
        raise WorkflowAttestationError("packageFiles must be a nonempty list")
    if expected_files != _package_files(package_root):
        raise WorkflowAttestationError(
            "package bytes changed since external verification; "
            "no Resolve action occurred"
        )
    verification = _verification(value.get("verification"))
    verifier = _verifier(value.get("verifier"))
    verified_at = value.get("verifiedAt")
    if not isinstance(verified_at, str) or not verified_at:
        raise WorkflowAttestationError("verifiedAt must be a nonempty string")
    manifest = _read_object(
        package_root / "timeline-manifest.json", "timeline manifest"
    )
    return VerifiedWorkflowPackage(
        package_root,
        project_name,
        manifest,
        verification,
        verifier,
        verified_at,
    )


def _package_files(package_root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(package_root.rglob("*")):
        relative = path.relative_to(package_root).as_posix()
        if path.is_symlink():
            raise WorkflowAttestationError(
                f"verified package contains a symbolic link: {relative}"
            )
        if path.is_dir():
            continue
        if not path.is_file():
            raise WorkflowAttestationError(
                f"verified package contains an unsupported entry: {relative}"
            )
        entries.append(
            {
                "path": relative,
                "sha256": _sha256(path),
                "sizeBytes": path.stat().st_size,
            }
        )
    paths = {cast(str, entry["path"]) for entry in entries}
    missing = REQUIRED_PACKAGE_FILES - paths
    if missing:
        raise WorkflowAttestationError(
            "verified package is missing required files: " + ", ".join(sorted(missing))
        )
    return entries


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WorkflowAttestationError(
            f"could not read {label} {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise WorkflowAttestationError(f"{label} must contain one JSON object")
    return cast(dict[str, Any], value)


def _require_project_name(value: str) -> None:
    if (
        not value.strip()
        or value != value.strip()
        or any(character in value for character in "\r\n")
    ):
        raise WorkflowAttestationError(
            "projectName must be a nonempty single-line unique name"
        )


def _verification(value: object) -> dict[str, int]:
    keys = ("eventCount", "markerCount", "mediaCount")
    if not isinstance(value, dict) or set(value) != set(keys):
        raise WorkflowAttestationError("verification counts are incomplete")
    if any(
        not isinstance(value[key], int)
        or isinstance(value[key], bool)
        or value[key] < 0
        for key in keys
    ):
        raise WorkflowAttestationError(
            "verification counts must be nonnegative integers"
        )
    return {key: cast(int, value[key]) for key in keys}


def _verifier(value: object) -> dict[str, str]:
    keys = ("implementation", "pythonVersion")
    if not isinstance(value, dict) or set(value) != set(keys):
        raise WorkflowAttestationError("verifier identity is incomplete")
    if any(not isinstance(value[key], str) or not value[key] for key in keys):
        raise WorkflowAttestationError("verifier identity values must be strings")
    return {key: cast(str, value[key]) for key in keys}
