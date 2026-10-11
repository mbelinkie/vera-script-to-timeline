"""Standard-library recheck of an independently verified, immutable handoff.

Derived from accepted #107 c9614eaf7bf7aa88f4cf33e77180ff5a393377e4;
uses the production ready package layout accepted by #34.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

ATTESTATION_SCHEMA = "vera-injected-delivery-attestation/v1"
SOURCE_PINS = {
    "issue34": "2586dded4d3566e944d7938604b20bded6fc36fb",
    "issue107": "c9614eaf7bf7aa88f4cf33e77180ff5a393377e4",
    "issue147": "75029de57baa594d3dfc7f509a09cfc21943e088",
}


class WorkflowPackageError(ValueError):
    """Unverified or changed handoff; no native action is authorized."""


@dataclass(frozen=True)
class VerifiedPackage:
    root: Path
    manifest: dict[str, Any]
    attestation: dict[str, Any]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_inventory(root: Path) -> list[dict[str, Any]]:
    if root.is_symlink() or not root.is_dir():
        raise WorkflowPackageError("package must be a regular directory")
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise WorkflowPackageError("package contains a symbolic link")
        if path.is_dir():
            continue
        if not path.is_file():
            raise WorkflowPackageError("package contains an unsupported entry")
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256(path),
                "sizeBytes": path.stat().st_size,
            }
        )
    if not entries:
        raise WorkflowPackageError("package is empty")
    return entries


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise WorkflowPackageError("handoff must contain one JSON object")
    return cast(dict[str, Any], value)


def write_immutable_json(path: Path, value: object) -> Path:
    """Publish complete bytes without replacing any earlier evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".vera-handoff-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o400)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def load_verified_package(path: Path, expected_sha256: str) -> VerifiedPackage:
    if (
        path.is_symlink()
        or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        or sha256(path) != expected_sha256
    ):
        raise WorkflowPackageError("attestation hash mismatch or unsafe path")
    value = read_object(path)
    if (
        value.get("schemaVersion") != ATTESTATION_SCHEMA
        or value.get("status") != "ready_to_import"
        or value.get("sourcePins") != SOURCE_PINS
    ):
        raise WorkflowPackageError("unverified or unsupported attestation")
    root_value = value.get("packageDir")
    if not isinstance(root_value, str) or not Path(root_value).is_absolute():
        raise WorkflowPackageError("packageDir must be absolute")
    root = Path(root_value)
    if path.resolve().is_relative_to(root.resolve()):
        raise WorkflowPackageError("attestation must be outside the package")
    if value.get("packageFiles") != file_inventory(root):
        raise WorkflowPackageError("stale package: bytes changed since verification")
    verified_at = value.get("verifiedAt")
    if not isinstance(verified_at, str):
        raise WorkflowPackageError("missing verification timestamp")
    if datetime.fromisoformat(verified_at).utcoffset() is None:
        raise WorkflowPackageError("verification timestamp must include timezone")
    verifier = value.get("verifier")
    if (
        not isinstance(verifier, dict)
        or verifier.get("implementation") != "CPython"
        or not isinstance(verifier.get("pythonVersion"), str)
        or not verifier["pythonVersion"].startswith("3.12.")
    ):
        raise WorkflowPackageError("missing independent locked-runtime verifier")
    build_id = value.get("buildId")
    if not isinstance(build_id, str) or not re.fullmatch(
        r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", build_id
    ):
        raise WorkflowPackageError("invalid build identity")
    build = root / "Builds" / build_id
    manifest = read_object(build / "timeline-manifest.json")
    receipt = read_object(build / "package-verification.json")
    if (
        manifest.get("buildId") != build_id
        or receipt.get("buildId") != build_id
        or receipt.get("status") != "ready_to_import"
        or receipt.get("manifest", {}).get("contentHash")
        != "sha256:" + sha256(build / "timeline-manifest.json")
        or value.get("verification")
        != {
            "eventCount": len(manifest["events"]),
            "markerCount": len(manifest["markers"]),
            "mediaCount": len(manifest["sources"]),
        }
    ):
        raise WorkflowPackageError("manifest/receipt/verification identity mismatch")
    project_name = value.get("projectName")
    if not isinstance(project_name, str) or not re.fullmatch(
        "VERA Delivery " + re.escape(build_id) + r" [0-9a-f]{12}", project_name
    ):
        raise WorkflowPackageError("target must be a unique build-derived name")
    if value.get("timelineName") != project_name:
        raise WorkflowPackageError("timeline identity mismatch")
    return VerifiedPackage(root, manifest, value)
