"""Strict macOS Seatbelt workspace shell for ordinary ChatGPT conversations.

Different from mac_exec: this tool never runs unconfined. Its only writable
filesystem tree is an operator-provisioned isolated workspace, and it has no
network or Mach-service grants. It must fail CLOSED if sandbox-exec is absent.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
import uuid

from shell_core import (
    MAX_COMMAND_CHARS,
    MAX_OUTPUT_BYTES,
    MAX_TIMEOUT_SECONDS,
    _kill_group,
    audit,
    now_utc,
)

SANDBOX_BIN = Path("/usr/bin/sandbox-exec")
SHELL_BIN = Path("/bin/zsh")
WORKSPACE_ROOT = Path.home() / ".local" / "share" / "vera-mac-bridge" / "workspace"
# Do not expose this as a user-supplied path/argument.
MAX_POLICY_CHARS = 16000


def workspace_root() -> Path:
    """Verify a dedicated local root; never use the user's main VERA checkout."""
    if sys.platform != "darwin" or not SANDBOX_BIN.is_file():
        raise ValueError("Mac kernel sandbox is unavailable")
    root = WORKSPACE_ROOT
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Dedicated workspace has not been provisioned locally")
    resolved = root.resolve(strict=True)
    if resolved != root:
        raise ValueError("Dedicated workspace cannot be redirected by a symlink")
    state = root.stat()
    if state.st_uid != os.getuid() or state.st_mode & 0o022:
        raise ValueError("Workspace must be owned by the user and not group/world writable")
    return root


def _sbpl_path(path: Path) -> str:
    value = str(path)
    if "\x00" in value or "\r" in value or "\n" in value or '"' in value:
        raise ValueError("Unsafe path for sandbox policy")
    return json.dumps(value, ensure_ascii=True)


def profile_for(root: Path) -> str:
    """Deny-by-default native Seatbelt profile inherited by all child processes.

    Only system binaries/frameworks and the dedicated workspace are readable.
    Only the dedicated workspace and /dev/null are writable. No network access,
    Mach-service lookup, TCC/Keychain access, or arbitrary home-directory access.
    """
    root = root.resolve(strict=True)
    ancestors = [p for p in reversed(root.parents) if str(p) != "/"]
    metadata = " ".join(
        f"(literal {_sbpl_path(p)})" for p in ancestors
    )
    system_read = " ".join(
        f'(subpath "{p}")' for p in
        ("/System", "/usr", "/bin", "/sbin", "/Library")
    )
    lines = [
        "(version 1)",
        "(deny default)",
        "(allow process-exec process-fork sysctl-read)",
        '(allow file-read* file-test-existence (literal "/") (literal "/dev/null") (literal "/dev/urandom") '
        + system_read + f" (subpath {_sbpl_path(root)}))",
        "(allow file-read-metadata file-test-existence " + metadata + ")",
        f"(allow file-write* (subpath {_sbpl_path(root)}) (literal \"/dev/null\"))",
        "(deny network*)",
    ]
    result = "\n".join(lines)
    if len(result) > MAX_POLICY_CHARS:
        raise ValueError("Sandbox policy is too large")
    return result


def _environment(root: Path) -> dict[str, str]:
    return {
        "HOME": str(root),
        "TMPDIR": str(root),
        "PATH": "/Library/Developer/CommandLineTools/usr/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "en_US.UTF-8",
        "LC_ALL": "C",
        "PAGER": "cat",
        "GIT_PAGER": "cat",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_OPTIONAL_LOCKS": "0",
        "npm_config_offline": "true",
    }


def _execute_sandboxed(command: str, root: Path, timeout_seconds: int) -> dict:
    """Launch via absolute sandbox-exec path; never fall back to raw zsh."""
    policy = profile_for(root)
    try:
        proc = subprocess.Popen(
            [str(SANDBOX_BIN), "-p", policy, str(SHELL_BIN), "-f", "-c", command],
            cwd=root, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True, env=_environment(root),
        )
    except OSError:
        return {
            "status": "sandbox_launch_failed",
            "exit_code": None, "stdout": "", "stderr": "",
            "truncated": False,
        }
    started = time.monotonic()
    selector = selectors.DefaultSelector()
    chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
    total = 0
    truncated = False
    timed_out = False
    try:
        assert proc.stdout and proc.stderr
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
                part = os.read(key.fileobj.fileno(), 4096)
                if not part:
                    selector.unregister(key.fileobj)
                    continue
                available = MAX_OUTPUT_BYTES - total
                chunks[key.data].append(part[:available])
                total += min(len(part), available)
                if len(part) > available or total >= MAX_OUTPUT_BYTES:
                    truncated = True
                    _kill_group(proc)
                    break
            if truncated:
                break
        try:
            code = proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            code = proc.wait(timeout=2)
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
        "status": (
            "timed_out" if timed_out else "output_limit" if truncated
            else "completed" if code == 0 else "failed"
        ),
        "exit_code": code,
        "stdout": b"".join(chunks["stdout"]).decode("utf-8", "replace"),
        "stderr": b"".join(chunks["stderr"]).decode("utf-8", "replace"),
        "truncated": truncated,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def workspace_exec(command: str, timeout_seconds: int = 25) -> dict:
    """A general single-line command inside a strict, isolated Mac workspace.

    Reject if sandbox preparation fails. No macOS Run once dialog is necessary,
    because the kernel denies reads/writes outside the dedicated workspace,
    network access and Mach service access. Host plugin policy still applies.
    """
    request_id = str(uuid.uuid4())
    record = {"request_id": request_id, "time": now_utc(),
              "operation": "workspace_exec", "status": "rejected"}
    if not isinstance(command, str) or not (1 <= len(command) <= MAX_COMMAND_CHARS):
        return {"request_id": request_id, "status": "rejected", "error": "Invalid command length"}
    if not command.strip() or any(ch in command for ch in "\x00\r\n"):
        return {"request_id": request_id, "status": "rejected", "error": "Expected single-line command"}
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        return {"request_id": request_id, "status": "rejected", "error": "Invalid timeout"}
    try:
        root = workspace_root()
        profile_for(root)
    except (OSError, ValueError) as exc:
        return {"request_id": request_id, "status": "unavailable", "error": str(exc)}
    # Fail closed if metadata cannot be recorded before execution.
    record["status"] = "sandbox_requested"
    if not audit(record):
        return {"request_id": request_id, "status": "audit_unavailable"}
    try:
        result = _execute_sandboxed(command, root, timeout_seconds)
    except Exception:
        result = {"status": "sandbox_error", "message": "Restricted execution failed"}
    record["status"] = result["status"]
    audit(record)
    return {"request_id": request_id, "workspace": "isolated", **result}


def workspace_info() -> dict:
    try:
        root = workspace_root()
        policy = profile_for(root)
    except (OSError, ValueError) as exc:
        return {"available": False, "reason": str(exc)}
    return {
        "available": True,
        "mode": "seatbelt-deny-default",
        "network": "denied",
        "filesystem_write": "dedicated_workspace_only",
        "filesystem_read": "system_paths_and_dedicated_workspace",
        "policy_size": len(policy),
        "prompt": "not_required_inside_sandbox",
    }
