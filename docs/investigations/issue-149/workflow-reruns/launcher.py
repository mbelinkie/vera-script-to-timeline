"""Hash-bound Workflow Integration launcher for Issue 149 Phase 10.

Resolve supplies the injected ``resolve`` object when this file is evaluated
from the Workflow Integration menu.  A missing injection is a hard failure;
there is no external bridge or external-scripting fallback.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)
CONFIG = PLUGIN_ROOT / "vera-issue-149-workflow-reruns.json"
RESULT_PREFIX = "vera-issue-149-workflow-reruns-result-"
PROGRESS_PREFIX = "vera-issue-149-workflow-reruns-progress-"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _safe_json(value: Any) -> Any:
    try:
        json.dumps(value, allow_nan=False)
        return value
    except (TypeError, ValueError, OverflowError):
        if isinstance(value, dict):
            return {str(key): _safe_json(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_safe_json(item) for item in value]
        return {"__native_type__": type(value).__name__, "__repr__": repr(value)}


def _write_json(path: Path, value: Any, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if exclusive else "w"
    with path.open(mode, encoding="utf-8") as stream:
        json.dump(_safe_json(value), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _atomic_json(path: Path, value: Any) -> None:
    """Disarm in the same directory so a rerun cannot see a half-write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                _safe_json(value), stream, indent=2, sort_keys=True, allow_nan=False
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _record(path: Path, phase: str, value: Any) -> None:
    with path.open("a", encoding="utf-8") as stream:
        json.dump(
            {
                "at": datetime.now(UTC).isoformat(),
                "phase": phase,
                "value": _safe_json(value),
            },
            stream,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")


def _error(error: BaseException) -> dict[str, str]:
    return {"type": type(error).__name__, "message": str(error)}


def _action_id(config: Any) -> str:
    value = config.get("actionId") if isinstance(config, dict) else None
    if (
        isinstance(value, str)
        and value
        and all(character.isalnum() or character in "_.-" for character in value)
    ):
        return value
    return "invalid-" + hashlib.sha256(repr(config).encode()).hexdigest()[:16]


def _output_path(config: Any) -> Path:
    value = config.get("outputDir") if isinstance(config, dict) else None
    if not isinstance(value, str):
        return PLUGIN_ROOT
    path = Path(value)
    if (
        not path.is_absolute()
        or path.is_symlink()
        or path.name != "issue149-workflow-reruns-20261002-kit-01"
        or path.parent.name != "out"
    ):
        return PLUGIN_ROOT
    return path


def _load_probe(config: dict[str, Any]):
    probe_value = config.get("probePath")
    digest = config.get("probeSha256")
    if not isinstance(probe_value, str) or not isinstance(digest, str):
        raise RuntimeError("probePath and probeSha256 are required")
    probe_path = Path(probe_value)
    if (
        not probe_path.is_absolute()
        or probe_path.is_symlink()
        or not probe_path.is_file()
    ):
        raise RuntimeError("probePath must be an absolute non-symlink file")
    if sha256(probe_path) != digest:
        raise RuntimeError("probe source differs from staged hash; stop")
    launcher_path = config.get("launcherPath")
    launcher_digest = config.get("launcherSha256")
    if launcher_path is not None or launcher_digest is not None:
        if not isinstance(launcher_path, str) or not isinstance(launcher_digest, str):
            raise RuntimeError(
                "launcherPath and launcherSha256 must be supplied together"
            )
        path = Path(launcher_path)
        if (
            path.is_symlink()
            or not path.is_absolute()
            or not path.is_file()
            or sha256(path) != launcher_digest
        ):
            raise RuntimeError("launcher source differs from staged hash; stop")
    spec = importlib.util.spec_from_file_location(
        "vera_issue_149_workflow_reruns", probe_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the stdlib-only harness")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if not callable(getattr(module, "run", None)):
        raise RuntimeError("staged harness has no run entrypoint")
    return module


def main(injected: Any, config_path: Path = CONFIG) -> dict[str, Any]:
    """Run one staged action; the caller must supply Resolve's injected object."""
    if config_path.is_symlink() or not config_path.is_file():
        raise RuntimeError("the staged action configuration is missing or symlinked")
    config_bytes = config_path.read_bytes()
    config_sha256 = hashlib.sha256(config_bytes).hexdigest()
    config = json.loads(config_bytes.decode("utf-8"))
    action_id = _action_id(config)
    output = _output_path(config)
    progress = output / f"{PROGRESS_PREFIX}{action_id}.jsonl"
    result = output / f"{RESULT_PREFIX}{action_id}.json"
    if progress.exists() or result.exists():
        raise RuntimeError(
            "actionId has already been dispatched; retain prior evidence"
        )
    progress.parent.mkdir(parents=True, exist_ok=True)
    progress.touch(exist_ok=False)
    _record(progress, "started", {"actionId": action_id, "configSha256": config_sha256})
    try:
        probe = _load_probe(config)
        _record(
            progress,
            "probe-verified",
            {
                "probePath": config.get("probePath"),
                "probeSha256": config.get("probeSha256"),
            },
        )
        # Disarm before the harness can perform any mutation.  The original
        # parsed object remains in memory for this one invocation only.
        disarmed = dict(config)
        disarmed.update(
            {
                "action": "__disarmed__",
                "disarmedFrom": config.get("action"),
                "disarmedAt": datetime.now(UTC).isoformat(),
            }
        )
        _atomic_json(config_path, disarmed)
        _record(
            progress,
            "disarmed",
            {"actionId": action_id, "action": config.get("action")},
        )
        if injected is None:
            raise RuntimeError(
                "Resolve injected object is missing; no external fallback"
            )
        _record(
            progress,
            "probe-request",
            {"action": config.get("action"), "phase": config.get("phase")},
        )
        returned = probe.run(injected, config, configSha256=config_sha256)
        if not isinstance(returned, dict):
            raise RuntimeError("harness returned a non-object result")
        if returned.get("actionId") != action_id:
            raise RuntimeError("harness result actionId differs from staged action")
        returned = {
            **returned,
            "launcher": "workflow-injected",
            "progress": str(progress),
        }
        _record(progress, "probe-return", {"status": returned.get("status")})
    except Exception as error:
        returned = {
            "status": "launcher-failed",
            "actionId": action_id,
            "configSha256": config_sha256,
            "error": _error(error),
            "progress": str(progress),
        }
        _record(progress, "failure", returned)
    _write_json(result, returned, exclusive=True)
    _record(
        progress,
        "result-written",
        {"result": str(result), "status": returned.get("status")},
    )
    return returned


# Resolve evaluates this file with a global ``resolve`` object.  Importing the
# module for the stdlib harness check has no side effects.
if "resolve" in globals():
    main(globals()["resolve"])
elif __name__ == "__main__":
    main(None)
