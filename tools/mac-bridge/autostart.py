"""Stage a user LaunchAgent for the private VERA Mac Bridge.

The launcher retrieves the runtime key from macOS Keychain at login.
There is no secret, unattended trust grant, or public listener in this plist.
'prepare' does NOT start or stop the existing tunnel.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile

SERVICE = "com.vera.mac-bridge.runtime-key"
LABEL = "com.vera.mac-bridge"
PROFILE = "vera-shell"
HOME = Path.home()
ROOT = HOME / ".local" / "share" / "vera-mac-bridge"
BINARY_SOURCE = HOME / "Downloads" / "tunnel-client-v0.0.19-darwin-amd64" / "tunnel-client"
BINARY_DEST = ROOT / "bin" / "tunnel-client"
WRAPPER = ROOT / "run-tunnel.zsh"
PLIST = HOME / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def wrapper_source(binary: Path = BINARY_DEST) -> bytes:
    binary_q = shlex.quote(str(binary))
    service_q = shlex.quote(SERVICE)
    return (f"""#!/bin/zsh -f
set -euo pipefail
umask 077
unset CONTROL_PLANE_API_KEY
key=$(/usr/bin/security find-generic-password -a "$(/usr/bin/id -un)" -s {service_q} -w 2>/dev/null) || exit 78
[[ -n "$key" ]] || exit 78
export CONTROL_PLANE_API_KEY="$key"
unset key
exec {binary_q} run --profile {PROFILE}
""").encode()


def plist_data(wrapper: Path = WRAPPER) -> bytes:
    data = {
        "Label": LABEL,
        "ProgramArguments": ["/bin/zsh", "-f", str(wrapper)],
        "LimitLoadToSessionType": "Aqua",
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 60,
        "ProcessType": "Interactive",
        "StandardOutPath": "/dev/null",
        "StandardErrorPath": "/dev/null",
    }
    return plistlib.dumps(data, sort_keys=True)


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_write(path: Path, content: bytes, mode: int) -> None:
    if path.is_symlink():
        raise RuntimeError(f"Refusing symlink destination: {path}")
    if path.exists():
        if not path.is_file() or path.read_bytes() != content:
            raise RuntimeError(f"Refusing to overwrite different existing file: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix=".bridge-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def prepare() -> None:
    if not BINARY_SOURCE.is_file() or not os.access(BINARY_SOURCE, os.X_OK):
        raise RuntimeError("Existing official tunnel-client executable not found")
    if not (HOME / ".config" / "tunnel-client" / f"{PROFILE}.yaml").is_file():
        raise RuntimeError("Existing vera-shell tunnel profile not found")
    if not (Path(__file__).parent / "server.py").is_file():
        raise RuntimeError("MCP server.py missing")
    if BINARY_DEST.is_symlink():
        raise RuntimeError("Refusing symlink binary destination")
    BINARY_DEST.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if BINARY_DEST.exists():
        if _file_hash(BINARY_DEST) != _file_hash(BINARY_SOURCE):
            raise RuntimeError("Installed tunnel binary differs: manual review required")
    else:
        shutil.copyfile(BINARY_SOURCE, BINARY_DEST)
        BINARY_DEST.chmod(0o700)
    _safe_write(WRAPPER, wrapper_source(), 0o700)
    _safe_write(PLIST, plist_data(), 0o600)
    print("LAUNCHAGENT_STAGED")
    print("No service was started; the current Terminal tunnel remains unchanged.")


def status() -> None:
    label = f"gui/{os.getuid()}/{LABEL}"
    result = subprocess.run(
        ["/bin/launchctl", "print", label],
        capture_output=True, text=True, check=False, timeout=8,
    )
    print("LAUNCHAGENT_LOADED" if result.returncode == 0 else "LAUNCHAGENT_NOT_LOADED")
    print("PLIST_PRESENT" if PLIST.is_file() else "PLIST_ABSENT")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("prepare", "status"):
        raise SystemExit("Usage: python autostart.py {prepare|status}")
    try:
        if sys.argv[1] == "prepare":
            prepare()
        else:
            status()
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f"Autostart configuration not completed: {exc}") from None
