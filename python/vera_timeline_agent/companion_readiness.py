"""Read-only companion setup diagnostics; never authorizes native side effects.

This module inspects only the versioned injected Workflow Integration release
and the operator's approved local package root. It never connects to Resolve,
imports a shipped runtime, installs, pairs, repairs or writes into evidence
owned by #109. Pairing/service observations are untrusted operator claims, so
the best possible state is ``native_preflight_required``.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from .workflow_package import SOURCE_PINS, sha256, write_immutable_json

SCHEMA = "vera-companion-readiness/v1"
POLICY_SCHEMA = "vera-companion-policy/v1"
MANIFEST_KEYS = {"schemaVersion", "deliveryVersion", "sourcePins", "files"}
RELEASE_ENTRY_KEYS = {"path", "sha256", "sizeBytes"}
POLICY_KEYS = {
    "schemaVersion",
    "releaseVersion",
    "releaseSha256",
    "approvedRoots",
    "approvedTools",
}
OBSERVATION_KEYS = {
    "packageRoot",
    "pairingState",
    "serviceState",
    "restartRequired",
}
ACTIONS = {
    "first_run": (
        "Quit Resolve; manually install a matching versioned Workflow "
        "Integration release; restart Resolve."
    ),
    "incompatible_version": (
        "Quit Resolve; retain the old version and manually install the "
        "approved compatible release; restart Resolve."
    ),
    "repair_required": (
        "Do not run the installed script. Preserve reports; quit Resolve and "
        "manually replace the entire installed release, never merge source "
        "folders."
    ),
    "approval_required": (
        "Use an explicitly approved local package root and the supported "
        "injected Resolve tool; do not expand access automatically."
    ),
    "restart_required": (
        "Restart Resolve after the operator's update, then rerun this "
        "diagnostic and its native preflight."
    ),
    "unpaired": (
        "Pair using the separately accepted service flow; never copy "
        "credentials into a report. Rerun diagnostics afterward."
    ),
    "disconnected": (
        "Check the companion service manually; reconnect using its accepted "
        "interface, then recheck without replaying any uncertain build."
    ),
    "native_preflight_required": (
        "Launch the existing injected Resolve preflight manually. This "
        "diagnostic never authorizes or proves a build."
    ),
}


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _relative_file(name: object) -> PurePosixPath:
    """Accept only plain POSIX relative paths declared by a shipped release."""
    if type(name) is not str or not name or "\\" in name or "\0" in name:
        raise ValueError("invalid release file path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in name.split("/")):
        raise ValueError("unsafe release file path")
    return path


def _within(path: Path, root: Path) -> bool:
    """Compare existing ancestry identity for APFS case and firmlink aliases.

    Mirrors the repository's native qualification containment check instead of
    comparing resolved spellings, which can differ by case or firmlink path on
    a default macOS volume.
    """
    if path.is_relative_to(root):
        return True
    try:
        if not root.exists():
            return False
        info = root.stat()
        identity = (info.st_dev, info.st_ino)
        return any(
            candidate.exists()
            and (candidate.stat().st_dev, candidate.stat().st_ino) == identity
            for candidate in (path, *path.parents)
        )
    except OSError:
        return False


def _plain_directory(path: Path) -> bool:
    try:
        return not path.is_symlink() and path.is_dir()
    except OSError:
        return False


def _plain_install_path(path: Path) -> bool:
    """Refuse symbolic links anywhere in the installed root's path."""
    try:
        return not any(candidate.is_symlink() for candidate in (path, *path.parents))
    except OSError:
        return False


def _existing_directory(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def _safe_absolute(value: object) -> bool:
    return (
        type(value) is str
        and "\0" not in value
        and Path(value).is_absolute()
        and ".." not in Path(value).parts
    )


def _manifest_from_bytes(payload: bytes) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("release manifest must be one JSON object")
    return value


def _release_state(root: Path, version: str, expected_hash: str) -> str | None:
    """Return the blocking release state, or ``None`` for a verified release.

    The scan mirrors both shipped launchers: only the selected
    ``vera-delivery-vN/`` subtree and its top-level launcher are owned by the
    release. Other plugins may share the Workflow Integration Plugins root.
    """
    try:
        return _release_state_checked(root, version, expected_hash)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        # Unreadable, malformed or racing input must never look installed.
        return "repair_required"


def _release_state_checked(root: Path, version: str, expected_hash: str) -> str | None:
    if not root.exists():
        return "repair_required" if root.is_symlink() else "first_run"
    if root.is_symlink() or not root.is_dir():
        return "repair_required"
    release_root = root / f"vera-delivery-v{version}"
    manifest_path = release_root / "release.json"
    launcher_name = f"VERA Delivery v{version}.py"
    if release_root.is_symlink() or (
        release_root.exists() and not release_root.is_dir()
    ):
        return "repair_required"
    if not manifest_path.is_file():
        if release_root.exists():
            return "repair_required"
        versioned = [
            path
            for path in root.glob("vera-delivery-v*")
            if path.is_dir() or path.is_symlink()
        ]
        if any((path / "release.json").is_file() for path in versioned):
            return "incompatible_version"
        if versioned:
            return "repair_required"
        if (root / launcher_name).is_symlink() or (root / launcher_name).exists():
            return "repair_required"
        return "first_run"
    if manifest_path.is_symlink():
        return "repair_required"
    if not _plain_install_path(root):
        # v2 rejects a symlinked launcher ancestry before importing source.
        return "repair_required"
    payload = manifest_path.read_bytes()
    if _sha256_bytes(payload) != expected_hash:
        return "repair_required"
    manifest = _manifest_from_bytes(payload)
    if set(manifest) != MANIFEST_KEYS:
        return "repair_required"
    if (
        manifest["schemaVersion"] != f"vera-injected-delivery-release/v{version}"
        or manifest["deliveryVersion"] != version
        or manifest["sourcePins"] != SOURCE_PINS
    ):
        return "incompatible_version"
    files = manifest["files"]
    if not isinstance(files, list) or not files:
        return "repair_required"
    declared: set[str] = set()
    for item in files:
        if not isinstance(item, dict) or set(item) != RELEASE_ENTRY_KEYS:
            return "repair_required"
        relative = _relative_file(item["path"])
        name = relative.as_posix()
        if name in declared or not (
            name == launcher_name
            or name.startswith(f"vera-delivery-v{version}/python/")
        ):
            return "repair_required"
        digest = item["sha256"]
        size = item["sizeBytes"]
        if (
            type(digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or type(size) is not int
            or size < 0
        ):
            return "repair_required"
        path = root.joinpath(*relative.parts)
        if (
            path.is_symlink()
            or not path.is_file()
            or not _within(path, root)
            or path.stat().st_size != size
            or sha256(path) != digest
        ):
            return "repair_required"
        declared.add(name)
    if launcher_name not in declared:
        return "repair_required"
    entries = list(release_root.rglob("*"))
    if any(
        path.is_symlink() or not (path.is_file() or path.is_dir()) for path in entries
    ):
        return "repair_required"
    installed_files = {
        path.relative_to(root).as_posix()
        for path in entries
        if path.is_file()
        and path not in {manifest_path, release_root / "request.json"}
        and path.name != ".DS_Store"
    } | {launcher_name}
    declared_directories = {
        parent.as_posix()
        for name in declared
        for parent in PurePosixPath(name).parents
        if parent.as_posix() != "."
    }
    installed_directories = {release_root.relative_to(root).as_posix()} | {
        path.relative_to(root).as_posix() for path in entries if path.is_dir()
    }
    if installed_files != declared or installed_directories != declared_directories:
        return "repair_required"
    return None


def _validate(policy: dict[str, Any], observation: dict[str, Any]) -> None:
    if not isinstance(policy, dict) or set(policy) != POLICY_KEYS:
        raise ValueError("unsupported companion policy")
    if policy["schemaVersion"] != POLICY_SCHEMA:
        raise ValueError("unsupported companion policy")
    if type(policy["releaseVersion"]) is not str or policy["releaseVersion"] not in (
        "1",
        "2",
    ):
        raise ValueError("unsupported release version")
    if (
        type(policy["releaseSha256"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", policy["releaseSha256"]) is None
    ):
        raise ValueError("invalid trusted release digest")
    roots = policy["approvedRoots"]
    if not isinstance(roots, list) or not all(_safe_absolute(root) for root in roots):
        raise ValueError("invalid approved roots")
    if policy["approvedTools"] != ["resolve:injected"]:
        raise ValueError("only the accepted injected Resolve tool is supported")
    if not isinstance(observation, dict) or set(observation) != OBSERVATION_KEYS:
        raise ValueError("unsupported diagnostic observation")
    if observation["pairingState"] not in ("unknown", "unpaired", "paired"):
        raise ValueError("invalid pairing state")
    if observation["serviceState"] not in (
        "unknown",
        "disconnected",
        "connected",
    ):
        raise ValueError("invalid service state")
    if type(observation["restartRequired"]) is not bool:
        raise ValueError("invalid restart observation")
    selected = observation["packageRoot"]
    if selected is not None and not _safe_absolute(selected):
        raise ValueError("invalid package root")


def _package_root_approved(policy: dict[str, Any], observation: dict[str, Any]) -> bool:
    selected = observation["packageRoot"]
    if not isinstance(selected, str):
        return False
    path = Path(selected)
    if not _plain_directory(path):
        return False
    roots = [Path(value) for value in policy["approvedRoots"]]
    # An unusable (missing or symlinked) allowlist entry cannot authorize the
    # selected package, but it must not invalidate a different usable root.
    return any(_plain_directory(root) and _within(path, root) for root in roots)


def inspect_readiness(
    installed_root: Path,
    policy: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    """Classify operator observations; a paired claim is not authentication."""
    _validate(policy, observation)
    if "\0" in str(installed_root):
        raise ValueError("invalid installed root")
    root = installed_root.absolute()
    if ".." in root.parts:
        raise ValueError("installed root must not contain '..'")
    version = policy["releaseVersion"]
    state = _release_state(root, version, policy["releaseSha256"])
    if state is None:
        if not _package_root_approved(policy, observation):
            state = "approval_required"
        elif observation["restartRequired"]:
            state = "restart_required"
        elif observation["pairingState"] != "paired":
            state = "unpaired"
        elif observation["serviceState"] != "connected":
            state = "disconnected"
        else:
            state = "native_preflight_required"
    assert state in ACTIONS
    return {
        "schemaVersion": SCHEMA,
        "state": state,
        "deliveryVersion": version,
        "releaseSha256": policy["releaseSha256"],
        "nextAction": ACTIONS[state],
        "canBuild": False,
        "nativeVerified": False,
        "evidenceKind": "read_only_local_diagnostic_operator_observations_untrusted",
    }


def retain_report(
    output: Path,
    installed_root: Path,
    policy: dict[str, Any],
    observation: dict[str, Any],
) -> Path:
    """Publish one immutable report outside the installed release and package."""
    report = inspect_readiness(installed_root, policy, observation)
    if not output.is_absolute():
        raise ValueError("report path must be absolute")
    if ".." in output.parts:
        raise ValueError("report path must not contain '..'")
    try:
        output_is_symlink = output.is_symlink()
    except OSError as error:
        raise ValueError("invalid report path") from error
    if output_is_symlink:
        raise ValueError("report must not replace a symbolic link")
    if not _existing_directory(output.parent):
        raise ValueError("report parent directory must already exist")
    if _within(output, installed_root.absolute()):
        raise ValueError("report must be outside the installed release")
    selected = observation["packageRoot"]
    if isinstance(selected, str) and _within(output, Path(selected)):
        raise ValueError("report must be outside the ready package")
    return write_immutable_json(output, report)
