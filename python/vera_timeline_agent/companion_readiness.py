"""Read-only companion setup diagnostics; never authorizes native side effects."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

from .workflow_package import SOURCE_PINS, read_object, sha256, write_immutable_json

SCHEMA = "vera-companion-readiness/v1"
POLICY_KEYS = {
    "schemaVersion",
    "releaseVersion",
    "releaseSha256",
    "approvedRoots",
    "approvedTools",
}
OBSERVATION_KEYS = {"packageRoot", "pairingState", "serviceState", "restartRequired"}
ACTIONS = {
    "first_run": (
        "Quit Resolve; manually install a matching versioned Workflow Integration "
        "release; restart Resolve."
    ),
    "incompatible_version": (
        "Quit Resolve; retain the old version and manually install the approved "
        "compatible release; restart Resolve."
    ),
    "repair_required": (
        "Do not run the installed script. Preserve reports; quit Resolve and "
        "manually replace the entire installed release, never merge source folders."
    ),
    "approval_required": (
        "Use an explicitly approved local package root and the supported injected "
        "Resolve tool; do not expand access automatically."
    ),
    "restart_required": (
        "Restart Resolve after the operator's update, then rerun this diagnostic "
        "and its native preflight."
    ),
    "unpaired": (
        "Pair using the separately accepted service flow; never copy credentials "
        "into a report. Rerun diagnostics afterward."
    ),
    "disconnected": (
        "Check the companion service manually; reconnect using its accepted "
        "interface, then recheck without replaying any uncertain build."
    ),
    "native_preflight_required": (
        "Launch the existing injected Resolve preflight manually. This diagnostic "
        "never authorizes or proves a build."
    ),
}


def _is_plain_path(path: Path) -> bool:
    absolute = path.absolute()
    return not any(item.is_symlink() for item in (absolute, *absolute.parents))


def _relative_file(name: object) -> PurePosixPath:
    if not isinstance(name, str):
        raise ValueError("invalid release file path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in name.split("/")):
        raise ValueError("unsafe release file path")
    return path


def _release_state(root: Path, version: str, expected_hash: str) -> str | None:
    folder = root / f"vera-delivery-v{version}"
    manifest_path = folder / "release.json"
    if (root.exists() and not root.is_dir()) or (
        root.exists() and not _is_plain_path(root)
    ):
        return "repair_required"
    if not root.is_dir():
        return "first_run"
    if folder.is_symlink():
        return "repair_required"
    if folder.exists() and not manifest_path.is_file():
        return "repair_required"
    if not manifest_path.is_file():
        other = "2" if version == "1" else "1"
        return (
            "incompatible_version"
            if (root / f"vera-delivery-v{other}/release.json").is_file()
            else "first_run"
        )
    if not _is_plain_path(root) or not _is_plain_path(manifest_path):
        return "repair_required"
    try:
        manifest = read_object(manifest_path)
        if set(manifest) != {
            "schemaVersion",
            "deliveryVersion",
            "sourcePins",
            "files",
        }:
            return "repair_required"
        if (
            manifest.get("schemaVersion")
            != f"vera-injected-delivery-release/v{version}"
            or manifest.get("deliveryVersion") != version
        ):
            return "incompatible_version"
        if manifest.get("sourcePins") != SOURCE_PINS:
            return "incompatible_version"
        if sha256(manifest_path) != expected_hash:
            return "repair_required"
        files = manifest.get("files")
        if not isinstance(files, list) or not files:
            return "repair_required"
        declared: set[str] = set()
        for item in files:
            if not isinstance(item, dict) or set(item) != {
                "path",
                "sha256",
                "sizeBytes",
            }:
                return "repair_required"
            relative = _relative_file(item["path"])
            name = relative.as_posix()
            if name in declared or not (
                name == f"VERA Delivery v{version}.py"
                or name.startswith(f"vera-delivery-v{version}/python/")
            ):
                return "repair_required"
            declared.add(name)
            file = root.joinpath(*relative.parts)
            if (
                not _is_plain_path(file)
                or not file.is_file()
                or not isinstance(item["sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
                or type(item["sizeBytes"]) is not int
                or file.stat().st_size != item["sizeBytes"]
                or sha256(file) != item["sha256"]
            ):
                return "repair_required"
        if f"VERA Delivery v{version}.py" not in declared:
            return "repair_required"
        # The Plugins directory can contain unrelated installed integrations.
        # Inspect ONLY the selected release folder and its root-level launcher.
        observed: set[str] = {f"VERA Delivery v{version}.py"}
        actual_dirs: set[str] = {folder.relative_to(root).as_posix()}
        for path in folder.rglob("*"):
            if not _is_plain_path(path):
                return "repair_required"
            if path.is_file():
                name = path.relative_to(root).as_posix()
                if (
                    name
                    in {
                        f"vera-delivery-v{version}/release.json",
                        f"vera-delivery-v{version}/request.json",
                    }
                    or path.name == ".DS_Store"
                ):
                    continue
                observed.add(name)
            elif path.is_dir():
                actual_dirs.add(path.relative_to(root).as_posix())
            else:
                return "repair_required"
        expected_dirs = {
            parent.as_posix()
            for name in declared
            for parent in PurePosixPath(name).parents
            if parent.as_posix() != "."
        }
        if observed != declared or actual_dirs != expected_dirs:
            return "repair_required"
    except (OSError, ValueError, TypeError, KeyError):
        return "repair_required"
    return None


def _validate(policy: dict[str, Any], observation: dict[str, Any]) -> None:
    if (
        set(policy) != POLICY_KEYS
        or policy["schemaVersion"] != "vera-companion-policy/v1"
    ):
        raise ValueError("unsupported companion policy")
    if policy["releaseVersion"] not in ("1", "2") or not isinstance(
        policy["releaseVersion"], str
    ):
        raise ValueError("unsupported release version")
    if not isinstance(policy["releaseSha256"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", policy["releaseSha256"]
    ):
        raise ValueError("invalid trusted release digest")
    if not isinstance(policy["approvedRoots"], list) or not all(
        isinstance(root, str) and Path(root).is_absolute()
        for root in policy["approvedRoots"]
    ):
        raise ValueError("invalid approved roots")
    if policy["approvedTools"] not in ([], ["resolve:injected"]):
        raise ValueError("only the accepted injected Resolve tool is supported")
    if set(observation) != OBSERVATION_KEYS:
        raise ValueError("unsupported diagnostic observation")
    if (
        observation["pairingState"] not in ("unknown", "unpaired", "paired")
        or observation["serviceState"] not in ("unknown", "disconnected", "connected")
        or type(observation["restartRequired"]) is not bool
    ):
        raise ValueError("invalid observation values")
    if observation["packageRoot"] is not None and (
        not isinstance(observation["packageRoot"], str)
        or not Path(observation["packageRoot"]).is_absolute()
    ):
        raise ValueError("invalid package root")


def inspect_readiness(
    installed_root: Path, policy: dict[str, Any], observation: dict[str, Any]
) -> dict[str, Any]:
    """Classify observations; a 'paired' claim is not authentication."""
    _validate(policy, observation)
    version = policy["releaseVersion"]
    state = _release_state(installed_root, version, policy["releaseSha256"])
    if state is None:
        roots = [Path(value) for value in policy["approvedRoots"]]
        selected = observation["packageRoot"]
        if (
            selected is None
            or not Path(selected).is_dir()
            or not roots
            or not policy["approvedTools"]
            or not all(_is_plain_path(root) for root in roots)
            or not _is_plain_path(Path(selected))
            or not any(
                Path(selected).resolve().is_relative_to(root.resolve())
                for root in roots
            )
        ):
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
    if (
        not output.is_absolute()
        or not _is_plain_path(output)
        or output.resolve().is_relative_to(installed_root.resolve())
    ):
        raise ValueError(
            "report must be outside the installed release and non-symlinked"
        )
    selected = observation.get("packageRoot")
    if isinstance(selected, str) and output.resolve().is_relative_to(
        Path(selected).resolve()
    ):
        raise ValueError("report must be outside the ready package")
    return write_immutable_json(
        output, inspect_readiness(installed_root, policy, observation)
    )
