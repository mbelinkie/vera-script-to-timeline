"""One guarded render from Resolve Workspace → Console.

The Console supplies the already-connected ``resolve`` object.  This helper
does not call ``scriptapp`` and never changes the source mapping.  The root
actor writes one action configuration under the new output directory, then
executes the command documented in ``plan.md`` exactly once.  The helper
atomically disarms that configuration before configuring the render.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
OUTPUT = Path(
    "REPOSITORY/"
    "out/issue149-workflow-discriminators-20261003-kit-02"
)
DEFAULT_CONFIG = OUTPUT / "params" / "d3-console-render.json"
PROJECT_NAME = "VERA Issue 149 WI Discriminators 20261003-kit-02"
SCHEMA_VERSION = "issue-149-console-render-v1"
ACTION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _safe(value: Any) -> Any:
    try:
        json.dumps(value, allow_nan=False)
        return value
    except (TypeError, ValueError, OverflowError):
        if isinstance(value, dict):
            return {str(key): _safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_safe(item) for item in value]
        return {"__native_type__": type(value).__name__, "__repr__": repr(value)}


def _write(path: Path, value: Any, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w", encoding="utf-8") as stream:
        json.dump(_safe(value), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _disarm(path: Path, config: dict[str, Any]) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        disarmed = dict(config)
        disarmed.update(
            {
                "action": "__disarmed__",
                "disarmedFrom": config.get("action"),
                "disarmedAt": datetime.now(UTC).isoformat(),
            }
        )
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(disarmed, stream, indent=2, sort_keys=True, allow_nan=False)
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
            {"at": datetime.now(UTC).isoformat(), "phase": phase, "value": _safe(value)},
            stream,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")


def _validate(config: dict[str, Any]) -> None:
    if config.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("Console render schema differs")
    if config.get("externalScriptingSetting") != "None":
        raise RuntimeError("Console render requires External Scripting None")
    if config.get("projectName") != PROJECT_NAME:
        raise RuntimeError("Console render project differs")
    action_id = config.get("actionId")
    if not isinstance(action_id, str) or not ACTION_RE.fullmatch(action_id):
        raise RuntimeError("Console render actionId is unsafe")
    phase = config.get("phase")
    if not isinstance(phase, str) or not phase:
        raise RuntimeError("Console render phase is required")
    if config.get("action") != "console-render":
        raise RuntimeError("Console render action is missing or disarmed")
    output = Path(str(config.get("outputDir", "")))
    if output != OUTPUT or output.is_symlink() or output.name != OUTPUT.name:
        raise RuntimeError("Console render output is not the owned discriminator output")
    if not isinstance(config.get("timelineUid"), str) or not config["timelineUid"]:
        raise RuntimeError("Console render timeline UID is required")
    render = config.get("render")
    if not isinstance(render, dict) or not isinstance(render.get("settings"), dict):
        raise RuntimeError("Console render settings are required")
    owned = config.get("owned")
    if not isinstance(owned, dict) or not isinstance(owned.get("projectUid"), str):
        raise RuntimeError("Console render owned project UID is required")
    console_digest = config.get("consoleSourceSha256")
    harness_digest = config.get("harnessSourceSha256")
    if (
        not isinstance(console_digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", console_digest)
        or not isinstance(harness_digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", harness_digest)
    ):
        raise RuntimeError("Console and harness source hashes are required")
    if _sha256(Path(__file__)) != console_digest:
        raise RuntimeError("Console helper source differs from staged hash")
    harness_path = HERE / "harness.py"
    if _sha256(harness_path) != harness_digest:
        raise RuntimeError("discriminator harness source differs from staged hash")


def main(injected: Any, config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    if injected is None:
        raise RuntimeError("Resolve did not inject an object; no external fallback")
    if config_path.is_symlink() or not config_path.is_file():
        raise RuntimeError("Console render configuration is missing or symlinked")
    raw = config_path.read_bytes()
    config = json.loads(raw.decode("utf-8"))
    _validate(config)
    output = Path(config["outputDir"])
    action_id = config["actionId"]
    result_path = output / f"console-render-result-{action_id}.json"
    progress_path = output / f"console-render-progress-{action_id}.jsonl"
    if result_path.exists() or progress_path.exists():
        raise RuntimeError("Console render action was already dispatched")
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.touch(exist_ok=False)
    _record(progress_path, "started", {"configSha256": hashlib.sha256(raw).hexdigest()})
    _disarm(config_path, config)
    _record(progress_path, "disarmed", {"actionId": action_id})

    harness_spec = __import__("importlib.util").util.spec_from_file_location(
        "issue149_discriminator_harness_console", HERE / "harness.py"
    )
    if harness_spec is None or harness_spec.loader is None:
        raise RuntimeError("could not load the discriminator harness")
    harness = __import__("importlib.util").util.module_from_spec(harness_spec)
    harness_spec.loader.exec_module(harness)
    journal = harness.Journal(output, action_id)
    result: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "action": "console-render",
        "actionId": action_id,
        "configSha256": hashlib.sha256(raw).hexdigest(),
        "journal": str(journal.path),
        "progress": str(progress_path),
    }
    try:
        project = harness._current_project(injected, journal, config)
        harness._owned_guard(project, journal, config)
        pre = harness._capture(journal, injected, project, "pre")
        render = harness._render_stage(injected, project, config, journal)
        if render is None:
            raise RuntimeError("Console render settings produced no render")
        poll_config = dict(config, jobId=render["jobId"])
        poll = harness._render_poll(project, poll_config, journal)
        post = harness._capture(journal, injected, project, "post")
        result.update({"status": "ok", "render": render, "poll": poll, "pre": pre, "post": post})
    except Exception as error:
        result.update({"status": "failure", "error": {"type": type(error).__name__, "message": str(error)}})
        journal.write("console-render", "failure", result)
    _write(result_path, result, exclusive=True)
    _record(progress_path, "result-written", {"result": str(result_path), "status": result["status"]})
    return result


if "resolve" in globals():
    override = globals().get("CONSOLE_CONFIG_PATH")
    main(globals()["resolve"], Path(override) if isinstance(override, str) else DEFAULT_CONFIG)
