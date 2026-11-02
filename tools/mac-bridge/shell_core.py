# ruff: noqa: E501
# Embedded AppleScript uses long literal dialog lines.
"""Mac-local command execution gate for the private VERA MCP bridge.

Commands normally require on-Mac approval. The operator may opt into a short-lived
machine-wide trusted window after a separate on-Mac confirmation. This is not
a sandbox: commands retain the local user's full file/network permissions.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import selectors
import signal
import subprocess
import threading
import time
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path

MAX_COMMAND_CHARS = 240  # Full command should fit in the Mac approval dialog.
MAX_OUTPUT_BYTES = 16 * 1024
MAX_TIMEOUT_SECONDS = 35
APPROVAL_SECONDS = 45
MAX_TRUST_MINUTES = 15
DEFAULT_TRUST_MINUTES = 10
SHELL_BIN = "/bin/zsh"
WORKSPACE_CONFIG = Path.home() / ".config" / "vera-mac-bridge" / "workspace"
_trust_lock = threading.RLock()
_exec_lock = threading.Lock()
_trusted_until = 0.0
_trust_generation = 0

# Never interpolate a shell command into AppleScript source. Pass it as argv.
APPROVAL_SCRIPT = r"""
on run argv
    set commandText to item 1 of argv
    set locationText to item 2 of argv
    set promptText to "A ChatGPT thread requests a Terminal command on this Mac." & return & return & "Working directory: " & locationText & return & "Command: " & commandText & return & return & "Output will be returned to ChatGPT. Approve only if you trust it."
    set decision to display dialog promptText with title "VERA Mac Bridge" buttons {"Deny", "Run once"} default button "Deny" cancel button "Deny" with icon caution giving up after 45
    if gave up of decision then return "DENIED"
    return button returned of decision
end run
"""

TRUST_SCRIPT = r"""
on run argv
    set durationText to item 1 of argv
    set promptText to "Enable TEMPORARY automatic Terminal execution for " & durationText & " minutes?" & return & return & "While enabled, ANY ChatGPT conversation with access to your VERA Mac Bridge can run ANY shell command, including commands that read secrets, change files, or access the network, without another approval prompt." & return & return & "This is NOT limited to one chat or sandboxed to VERA." & return & return & "Stop tunnel-client or call mac_trust_disable to end access. Enable only if you trust every active chat."
    set decision to display dialog promptText with title "VERA Mac Bridge - Elevated Trust Window" buttons {"Deny", "Enable"} default button "Deny" cancel button "Deny" with icon caution giving up after 45
    if gave up of decision then return "DENIED"
    return button returned of decision
end run
"""


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


def resolve_cwd(cwd: str) -> Path:
    """No caller-selected absolute cwd; home and an operator-configured VERA path."""
    if cwd == "home":
        root = Path.home()
    elif cwd == "vera":
        configured = os.environ.get("VERA_WORKSPACE", "")
        if not configured:
            if WORKSPACE_CONFIG.is_symlink():
                raise ValueError("workspace config must not be a symlink")
            try:
                configured = WORKSPACE_CONFIG.read_text(encoding="utf-8").strip()
            except FileNotFoundError:
                raise ValueError("VERA_WORKSPACE is not configured locally") from None
        if not configured or "\n" in configured or "\r" in configured:
            raise ValueError("workspace path must be one nonempty line")
        root = Path(configured).expanduser()
        if not root.is_absolute():
            raise ValueError("workspace path must be absolute")
    else:
        raise ValueError("cwd must be 'vera' or 'home'")
    resolved = root.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("configured working directory is not a directory")
    return resolved


def validate(command: str, cwd: str, timeout_seconds: int) -> Path:
    if not isinstance(command, str) or not (1 <= len(command) <= MAX_COMMAND_CHARS):
        raise ValueError(f"command must be 1-{MAX_COMMAND_CHARS} characters")
    if not command.strip() or any(
        unicodedata.category(char) in {"Cc", "Cf", "Zl", "Zp"} for char in command
    ):
        raise ValueError(
            "command must be one printable line without control or format characters"
        )
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
            capture_output=True,
            text=True,
            timeout=APPROVAL_SECONDS + 6,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip() == "Run once"


def trust_remaining_seconds() -> int:
    """Process-local, nonpersistent authority shared by all MCP sessions."""
    with _trust_lock:
        return max(0, int(_trusted_until - time.monotonic() + 0.999))


def trust_status() -> dict:
    remaining = trust_remaining_seconds()
    return {
        "status": "active" if remaining else "inactive",
        "remaining_seconds": remaining,
        "scope": "all_chats_with_bridge_access",
        "authorization": "local_opt_in",
    }


def trust_disable() -> dict:
    global _trusted_until, _trust_generation
    with _trust_lock:
        _trusted_until = 0.0
        _trust_generation += 1
    audit({"time": now_utc(), "operation": "trust_disable", "status": "disabled"})
    return trust_status()


def trust_enable(minutes: int = DEFAULT_TRUST_MINUTES) -> dict:
    """Enable a short, global trust window after a separate local OS dialog."""
    global _trusted_until, _trust_generation
    if type(minutes) is not int or not 1 <= minutes <= MAX_TRUST_MINUTES:
        return {
            "status": "rejected",
            "error": f"minutes must be an integer from 1 to {MAX_TRUST_MINUTES}",
        }
    # Invalidate an existing grant and older in-flight approval dialogs.
    trust_disable()
    with _trust_lock:
        request_generation = _trust_generation
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", TRUST_SCRIPT, str(minutes)],
            capture_output=True,
            text=True,
            timeout=APPROVAL_SECONDS + 6,
            check=False,
        )
        authorized = result.returncode == 0 and result.stdout.strip() == "Enable"
    except (OSError, subprocess.TimeoutExpired):
        authorized = False
    if not authorized:
        audit({"time": now_utc(), "operation": "trust_enable", "status": "denied"})
        return {
            "result": "denied",
            "message": "No on-Mac trust authorization received",
            **trust_status(),
        }
    with _trust_lock:
        # Disable (or a newer enable attempt) must revoke the older dialog.
        if request_generation != _trust_generation:
            return {"result": "canceled", **trust_status()}
        # Persist the authorization before publishing it to mac_exec callers.
        # Keep the lock so no command can observe a grant whose audit failed.
        if not audit(
            {
                "time": now_utc(),
                "operation": "trust_enable",
                "status": "enabled",
                "minutes": minutes,
            }
        ):
            _trust_generation += 1
        else:
            _trusted_until = time.monotonic() + 60 * minutes
            return {"result": "enabled", **trust_status()}
        return {"result": "audit_unavailable", **trust_status()}


def _kill_group(proc: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)


def execute_bounded(
    command: str,
    folder: Path,
    timeout_seconds: int,
    *,
    trust_generation: int | None = None,
) -> dict:
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
        "PATH": os.environ.get(
            "VERA_BRIDGE_PATH",
            "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        ),
        "PAGER": "cat",
        "GIT_PAGER": "cat",
    }
    started = time.monotonic()
    try:
        if trust_generation is None:
            proc = subprocess.Popen(
                [SHELL_BIN, "-f", "-c", command],
                cwd=folder,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                env=env,
            )
        else:
            # Serialize the final grant check with trust_disable. Once the
            # child starts, it is an in-flight command; disabling trust blocks
            # new commands but does not terminate work already underway.
            with _trust_lock:
                if (
                    trust_generation != _trust_generation
                    or _trusted_until <= time.monotonic()
                ):
                    return {
                        "status": "trust_revoked",
                        "exit_code": None,
                        "stdout": "",
                        "stderr": "Temporary trust ended before command start",
                        "truncated": False,
                    }
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
        return {
            "status": "launch_failed",
            "exit_code": None,
            "stdout": "",
            "stderr": "Cannot start shell",
            "truncated": False,
        }

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
        _kill_group(proc)
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
        "status": "timed_out"
        if timed_out
        else "output_limit"
        if truncated
        else "completed"
        if exit_code == 0
        else "failed",
        "exit_code": exit_code,
        "stdout": b"".join(chunks["stdout"]).decode("utf-8", "replace"),
        "stderr": b"".join(chunks["stderr"]).decode("utf-8", "replace"),
        "truncated": truncated,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def audit(record: dict) -> bool:
    """Append only non-secret metadata; return False on write failure."""
    location = Path.home() / ".local" / "state" / "vera-mac-bridge" / "audit.jsonl"
    try:
        location.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_APPEND | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        handle = os.open(str(location), flags, 0o600)
        try:
            os.fchmod(handle, 0o600)
            payload = (
                json.dumps(record, separators=(",", ":"), default=str) + "\n"
            ).encode()
            if os.write(handle, payload) != len(payload):
                return False
            os.fsync(handle)
        finally:
            os.close(handle)
    except OSError:
        return False
    return True


def mac_exec_local(command: str, cwd: str = "vera", timeout_seconds: int = 25) -> dict:
    request_id = str(uuid.uuid4())
    record = {
        "request_id": request_id,
        "time": now_utc(),
        "cwd": cwd if isinstance(cwd, str) else "<invalid>",
        "command_sha256": (
            hashlib.sha256(command.encode("utf-8", "replace")).hexdigest()
            if isinstance(command, str)
            else None
        ),
        "status": "rejected",
    }
    try:
        folder = validate(command, cwd, timeout_seconds)
    except (ValueError, OSError) as exc:
        audit(record)
        return {"request_id": request_id, "status": "rejected", "error": str(exc)}
    if not _exec_lock.acquire(blocking=False):
        record["status"] = "busy"
        audit(record)
        return {
            "request_id": request_id,
            "status": "busy",
            "message": "Another command is active",
        }
    try:
        with _trust_lock:
            trusted = _trusted_until > time.monotonic()
            trust_generation = _trust_generation if trusted else None
        approval_mode = "temporary_trust" if trusted else "per_command"
        if approval_mode == "per_command" and not confirm_on_mac(command, folder):
            record["status"] = "denied"
            audit(record)
            return {
                "request_id": request_id,
                "status": "denied",
                "message": "No on-Mac approval received",
            }
        record["status"] = "approved"
        record["approval_mode"] = approval_mode
        if not audit(record):
            return {
                "request_id": request_id,
                "status": "audit_unavailable",
                "message": "Local audit unavailable: command not executed",
            }
        try:
            if trust_generation is None:
                result = execute_bounded(command, folder, timeout_seconds)
            else:
                result = execute_bounded(
                    command,
                    folder,
                    timeout_seconds,
                    trust_generation=trust_generation,
                )
        except Exception:
            result = {
                "status": "internal_error",
                "message": "Local execution failed; details withheld",
            }
        record["status"] = result["status"]
        if not audit(record):
            return {
                "request_id": request_id,
                "cwd": cwd,
                "approval_mode": approval_mode,
                "status": "audit_incomplete",
                "execution_status": result["status"],
                "message": "Command finished, but the final local audit record could not be written",
                **{key: value for key, value in result.items() if key != "status"},
            }
        return {
            "request_id": request_id,
            "cwd": cwd,
            "approval_mode": approval_mode,
            **result,
        }
    finally:
        _exec_lock.release()
