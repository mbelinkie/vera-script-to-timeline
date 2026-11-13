"""Installed, stdlib-only bootstrap for ordinary verified v2 Resolve delivery.

No VERA runtime is imported until its closed release inventory and request pin
have been checked. Retired qualification and probe requests are not supported.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).absolute()
RELEASE_NAME = "vera-delivery-v2"
LAUNCHER_NAME = "VERA Delivery v2.py"
TI_RUNTIME_FILES = (
    "__init__.py",
    "studio_spike.py",
    "text_plus_template.py",
    "workflow_package.py",
    "workflow_delivery.py",
    "workflow_launcher.py",
    "workflow_v2.py",
    "row_timeline_map.py",
    "transition_delivery_v2.py",
    "workflow_v2_launcher.py",
    "native_image_motion.py",
    "resolve_native_owner.py",
    "workflow_v2_parent.py",
)
REQUEST_KEYS = {
    "schemaVersion",
    "releaseSha256",
    "attestationPath",
    "attestationSha256",
    "packageDir",
    "projectName",
    "timelineName",
    "action",
    "authorizeNewNonproduction",
    "externalScripting",
    "evidenceDir",
}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _no_symlinks(path: Path) -> None:
    if any(item.is_symlink() for item in (path, *path.absolute().parents)):
        raise RuntimeError("symbolic link in installed delivery path")


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _object(payload: bytes) -> dict[str, Any]:
    def no_duplicate_keys(entries: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in entries:
            if key in result:
                raise RuntimeError("duplicate installed JSON field")
            result[key] = value
        return result

    value = json.loads(payload, object_pairs_hook=no_duplicate_keys)
    if not isinstance(value, dict):
        raise RuntimeError("installed JSON root must be an object")
    return value


def _check_request(request: dict[str, Any]) -> None:
    if set(request) != REQUEST_KEYS or request.get("schemaVersion") != (
        "vera-injected-delivery-request/v2"
    ):
        raise RuntimeError("unsupported operator request")
    if any(
        not isinstance(request[key], str) or not request[key]
        for key in REQUEST_KEYS - {"authorizeNewNonproduction", "externalScripting"}
    ):
        raise RuntimeError("invalid operator request fields")
    if any(
        not HEX64.fullmatch(request[key])
        for key in ("releaseSha256", "attestationSha256")
    ):
        raise RuntimeError("invalid operator request digest")
    if (
        request["action"] not in {"preflight", "build"}
        or type(request["authorizeNewNonproduction"]) is not bool
        or request["externalScripting"] not in {None, "Local", "None"}
    ):
        raise RuntimeError("invalid operator authorization")


def _verified_runtime(root: Path, request: dict[str, Any]) -> Path:
    """Check exact installed bytes and inventory before any package import."""
    release_root = root / RELEASE_NAME
    manifest_path = release_root / "release.json"
    _no_symlinks(manifest_path)
    release_bytes = manifest_path.read_bytes()
    if _digest(release_bytes) != request["releaseSha256"]:
        raise RuntimeError("installed release hash differs from operator request")
    manifest = _object(release_bytes)
    if (
        set(manifest) != {"schemaVersion", "deliveryVersion", "sourcePins", "files"}
        or manifest["schemaVersion"] != "vera-injected-delivery-release/v2"
        or manifest["deliveryVersion"] != "2"
        or not isinstance(manifest["sourcePins"], dict)
        or not isinstance(manifest["files"], list)
    ):
        raise RuntimeError("unsupported installed release")

    expected = {
        f"{RELEASE_NAME}/python/vera_timeline_agent/{name}" for name in TI_RUNTIME_FILES
    } | {LAUNCHER_NAME}
    declared: set[str] = set()
    for entry in manifest["files"]:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"path", "sha256", "sizeBytes"}
            or type(entry["path"]) is not str
            or not entry["path"]
            or "\\" in entry["path"]
            or Path(entry["path"]).is_absolute()
            or any(part in {"", ".", ".."} for part in entry["path"].split("/"))
            or entry["path"] in declared
            or type(entry["sizeBytes"]) is not int
            or entry["sizeBytes"] < 0
            or type(entry["sha256"]) is not str
            or not HEX64.fullmatch(entry["sha256"])
        ):
            raise RuntimeError("invalid closed installed release inventory")
        path = root / entry["path"]
        _no_symlinks(path)
        if (
            not path.is_file()
            or not path.resolve().is_relative_to(root)
            or path.stat().st_size != entry["sizeBytes"]
            or _digest(path.read_bytes()) != entry["sha256"]
        ):
            raise RuntimeError("installed source differs from the versioned release")
        declared.add(entry["path"])
    if declared != expected:
        raise RuntimeError("installed runtime inventory is not closed")

    children = list(release_root.rglob("*"))
    if any(
        path.is_symlink() or not (path.is_file() or path.is_dir()) for path in children
    ):
        raise RuntimeError("unsupported entry in installed release")
    installed = {
        path.relative_to(root).as_posix()
        for path in children
        if path.is_file() and path not in {manifest_path, release_root / "request.json"}
    }
    installed.add(LAUNCHER_NAME)
    if installed != declared:
        raise RuntimeError("installed source inventory differs from release")
    allowed_dirs = {
        parent.as_posix()
        for name in declared
        for parent in Path(name).parents
        if parent != Path(".")
    }
    actual_dirs = {release_root.relative_to(root).as_posix()} | {
        path.relative_to(root).as_posix() for path in children if path.is_dir()
    }
    if actual_dirs != allowed_dirs:
        raise RuntimeError("installed directory inventory differs from release")
    return release_root / "python"


def launch(injected_resolve: object) -> None:
    _no_symlinks(SCRIPT_PATH)
    root = SCRIPT_PATH.parent
    request_path = root / RELEASE_NAME / "request.json"
    _no_symlinks(request_path)
    request_bytes = request_path.read_bytes()
    request = _object(request_bytes)
    _check_request(request)
    runtime = _verified_runtime(root, request)
    if any(
        name == "vera_timeline_agent" or name.startswith("vera_timeline_agent.")
        for name in sys.modules
    ):
        raise RuntimeError("a VERA runtime is already loaded; restart Resolve")
    sys.dont_write_bytecode = True
    sys.pycache_prefix = None
    sys.path.insert(0, str(runtime))
    from vera_timeline_agent.workflow_v2_launcher import run_installed_request_v2

    print(
        run_installed_request_v2(
            injected_resolve,
            request_path,
            expected_request_sha256=_digest(request_bytes),
        )
    )


def retain_bootstrap_refusal(failure: dict[str, Any]) -> None:
    """Keep fresh, safe refusal evidence without importing unverified code."""
    try:
        request_path = SCRIPT_PATH.parent / RELEASE_NAME / "request.json"
        _no_symlinks(request_path)
        request = _object(request_path.read_bytes())
        evidence = Path(request["evidenceDir"])
        _no_symlinks(evidence)
        protected = [
            SCRIPT_PATH.parent.resolve(),
            Path(request["packageDir"]).resolve(),
        ]
        attestation = Path(request["attestationPath"])
        if attestation.exists():
            _no_symlinks(attestation)
            protected.append(
                Path(_object(attestation.read_bytes())["packageDir"]).resolve()
            )
        if not evidence.is_absolute() or any(
            evidence.resolve().is_relative_to(path) for path in protected
        ):
            raise RuntimeError("unsafe evidence directory")
        evidence.mkdir(parents=True, mode=0o700, exist_ok=True)
        path = evidence / f"bootstrap-refusal-{uuid.uuid4().hex}.json"
        with path.open("x", encoding="utf-8") as stream:
            json.dump(failure, stream, indent=2, sort_keys=True)
        path.chmod(0o400)
        failure["reportPath"] = str(path)
    except Exception:
        failure["reportRetention"] = "unavailable; retain this Console output"
    print(json.dumps(failure, indent=2, sort_keys=True))


try:
    launch(globals().get("resolve"))
except Exception as error:
    retain_bootstrap_refusal(
        {
            "status": "workflow_v2_launcher_failed",
            "verified": False,
            "detail": str(error),
        }
    )
