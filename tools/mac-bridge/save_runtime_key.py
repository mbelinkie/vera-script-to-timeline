"""Store an existing tunnel runtime key in the login Keychain, never on argv.

Run manually in the existing Terminal where CONTROL_PLANE_API_KEY is exported.
Do not run this through mac_exec: that subprocess deliberately strips secrets.
"""

from __future__ import annotations

import getpass
import os
import re
import secrets
import subprocess

SERVICE = "com.vera.mac-bridge.runtime-key"


def save_from_environment() -> None:
    key = os.environ.get("CONTROL_PLANE_API_KEY", "")
    if not key or len(key) > 4096:
        raise SystemExit(
            "CONTROL_PLANE_API_KEY is missing or invalid in this Terminal."
        )
    try:
        key_bytes = key.encode("ascii")
    except UnicodeEncodeError:
        raise SystemExit(
            "Runtime key must contain printable ASCII characters."
        ) from None
    if not all(33 <= value <= 126 for value in key_bytes):
        raise SystemExit(
            "Runtime key contains unsupported whitespace/control characters."
        )
    account = getpass.getuser()
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", account):
        raise SystemExit("Unsupported account name; no key was stored.")

    # The key is encoded only in security's private STDIN stream, not command
    # arguments, shell history, Git, or a temporary file.
    command = (
        f"add-generic-password -U -a {account} -s {SERVICE} -X {key_bytes.hex()}\n"
    )
    try:
        created = subprocess.run(
            ["/usr/bin/security", "-i"],
            input=command,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise SystemExit("Keychain write did not complete.") from None
    if created.returncode != 0:
        raise SystemExit("Keychain write failed. The credential was not printed.")

    # Read back without displaying. A Keychain permission dialog may occur.
    try:
        check = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-a",
                account,
                "-s",
                SERVICE,
                "-w",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise SystemExit("Could not verify the Keychain item.") from None
    if check.returncode != 0 or not secrets.compare_digest(
        check.stdout.rstrip(b"\n"), key_bytes
    ):
        raise SystemExit("Keychain read-back did not match. Do not switch to launchd.")
    print("KEYCHAIN_READY")


if __name__ == "__main__":
    save_from_environment()
