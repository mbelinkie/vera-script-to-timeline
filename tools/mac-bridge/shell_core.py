"""Mac-local command execution gate for the private VERA MCP bridge.

Every command requires a separate affirmative *local* macOS GUI decision.
The command is intentionally general-purpose; do not mistake this for a sandbox.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
import uuid
from datetime import datetime, timezone

MAX_COMMAND_CHARS = 240  # Full command should fit in the Mac approval dialog.
MAX_OUTPUT_BYTES = 16 * 1024
MAX_TIMEOUT_SECONDS = 35
APPROVAL_SECONDS = 45
SHELL_BIN = "/bin/zsh"

# Never interpolate a shell command into AppleScript source. Pass it as argv.
APPROVAL_SCRIPT = r'''
on run argv
    set commandText to item 1 of argv
    set locationText to item 2 of argv
    set promptText to "A ChatGPT thread requests a Terminal command on this Mac." & return & return & "Working directory: " & locationText & return & "Command: " & commandText & return & return & "Output will be returned to ChatGPT. Approve only if you trust it."
    set decision to display dialog promptText with title "VERA Mac Bridge" buttons {"Deny", "Run once"} default button "Deny" cancel button "Deny" with icon caution giving up after 45
    if gave up of decision then return "DENIED"
    return button returned of decision
end run
'''


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_cwd(cwd: str) -> Path:
    """No caller-selected absolute cwd; home and an operator-configured VERA path."""
    if cwd == "home":
        root = Path.home()
    elif cwd == "vera":
        configured = os.environ.get("VERA_WORKSPACE", "")
        if not configured:
            raise ValueError("VERA_WORKSPACE is not configured locally")
        root = Path(configured).expanduser()
    else:
        raise ValueError("cwd must be 'vera' or 'home'")
    resolved = root.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("configured working directory is not a directory")
    return resolved


def validate(command: str, cwd: str, timeout_seconds: int) -> Path:
    if not isinstance(command, str) or not (1 <= len(command) <= MAX_COMMAND_CHARS):
        raise ValueError(f"command must be 1-{MAX_COMMAND_CHARS} characters")
    if any(c in command for c in "\x00\r\n") or not command.strip():
        raise ValueError("command must be one nonempty line without NUL or CR/LF")
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
        raise ValueError("timeout_seconds must be an integer")
    if not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout_seconds must be 1-{MAX_TIMEOUT_SECONDS}")
    return resolve_cwd(cwd)


def confirm_on_mac(command: str, folder: Path) -> bool:
    """Fail closed if no logged-in desktop, GUI denial, timeout, or osascript error."""
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", APPROVAL_SCRIPT, command, str(folder)],
            capture_output=True, text=True, timeout=APPROVAL_SECONDS + 6,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip() == "Run once"


def _kill_group(proc: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def execute_bounded(command: str, folder: Path, timeout_seconds: int) -> dict:
    """Execute approved shell syntax, kill the process group on timeout/output cap.

    Only the operator's explicit local permission makes this acceptable. The
    executed shell can read/write anything the user's macOS account can.
    """
    env = {
        "HOME": str(Path.home()),
        "USER": os.environ.get("USER", ""),
        "LOGNAME": os.environ.get("LOGNAME", ""),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "PATH": os.environ.get("VERA_BRIDGE_PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"),
        "PAGER": "cat",
        "GIT_PAGER": "cat",
    }
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            [SHELL_BIN, "-f", "-c", command],
            cwd=folder,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            env=env,
        )
    except OSError:
        return {"status": "launch_failed", "exit_code": None, "stdout": "", "stderr": "Cannot start shell", "truncated": False}

    chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
    total = 0
    timed_out = False
    truncated = False
    selector = selectors.DefaultSelector()
    try:
        assert proc.stdout is not None and proc.stderr is not None
        for name, stream in (("stdout", proc.stdout), ("stderr", proc.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map():
            remaining = timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                timed_out = True
                _kill_group(proc)
                break
            for key, _ in selector.select(timeout=min(remaining, 0.25)):
                data = os.read(key.fileobj.fileno(), 4096)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                available = MAX_OUTPUT_BYTES - total
                if len(data) > available:
                    chunks[key.data].append(data[:available])
                    total = MAX_OUTPUT_BYTES
                    truncated = True
                    _kill_group(proc)
                    break
                chunks[key.data].append(data)
                total += len(data)
            if truncated:
                break
        try:
            exit_code = proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            exit_code = proc.wait(timeout=2)
    finally:
        selector.close()
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()
        if proc.poll() is None:
            _kill_group(proc)
            proc.wait(timeout=2)

    return {
        "status": "timed_out" if timed_out else "output_limit" if truncated else "completed" if exit_code == 0 else "failed",
        "exit_code": exit_code,
        "stdout": b"".join(chunks["stdout"]).decode("utf-8", "replace"),
        "stderr": b"".join(chunks["stderr"]).decode("utf-8", "replace"),
        "truncated": truncated,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def audit(record: dict) -> None:
    """Metadata-only, private best-effort journal; no command string or output."""
    location = Path.home() / ".local" / "state" / "vera-mac-bridge" / "audit.jsonl"
    try:
        location.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        handle = os.open(str(location), os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        try:
            os.write(handle, (json.dumps(record, separators=(",", ":")) + "\n").encode())
        finally:
            os.close(handle)
    except OSError:
        # Do not leak local filesystem details to the remote caller.
        pass


def mac_exec_local(command: str, cwd: str = "vera", timeout_seconds: int = 25) -> dict:
    request_id = str(uuid.uuid4())
    record = {"request_id": request_id, "time": now_utc(), "cwd": cwd,
              "command_sha256": hashlib.sha256(command.encode("utf-8", "replace")).hexdigest(),
              "status": "rejected"}
    try:
        folder = validate(command, cwd, timeout_seconds)
    except (ValueError, OSError) as exc:
        result = {"request_id": request_id, "status": "rejected", "error": str(exc)}
        audit(record)
        return result
    if not confirm_on_mac(command, folder):
        record["status"] = "denied"
        audit(record)
        return {"request_id": request_id, "status": "denied", "message": "No on-Mac approval received"}
    try:
        result = execute_bounded(command, folder, timeout_seconds)
    except Exception:
        result = {"status": "internal_error", "message": "Local execution failed; details withheld"}
    record["status"] = result["status"]
    audit(record)
    return {"request_id": request_id, "cwd": cwd, **result}
