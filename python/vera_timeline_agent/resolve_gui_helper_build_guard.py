#!/usr/bin/env python3
"""Fail-closed signed-helper build guard shared with native M4 owner.

The wrapper is NOT a native operation: it checks only case carrier-lock inodes,
then holds the native-owner exclusive lock while a single pinned shell build
installs its signed binary. It never manipulates case journals or Resolve.
"""

from __future__ import annotations

import fcntl
import os
import stat
import subprocess
import sys
from pathlib import Path

from vera_timeline_agent.resolve_native_owner import OWNER_FD_ENV, native_owner


class ActiveNativeCampaign(RuntimeError):
    pass


def active_conductor_cases(state_root: Path) -> tuple[str, ...]:
    """Only read native carrier locks; an active entire-run lock blocks build."""
    active: list[str] = []
    if not state_root.is_dir() or state_root.is_symlink():
        raise ActiveNativeCampaign(
            "private VERA state directory unavailable or aliased"
        )
    for root in sorted(state_root.iterdir()):
        if not root.is_dir() or root.is_symlink():
            continue
        lock_dir = root / ".conductor-launch"
        if not lock_dir.is_dir() or lock_dir.is_symlink():
            continue
        path = lock_dir / "carrier.lock"
        if not path.exists() and not path.is_symlink():
            continue
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
                or info.st_nlink != 1
            ):
                raise ActiveNativeCampaign("unsafe Conductor carrier lock identity")
            try:
                fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                active.append(root.name)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
    return tuple(active)


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    build = root / "macos/vera-gui-helper/build.sh"
    if len(sys.argv) != 1 or not build.is_file():
        raise ActiveNativeCampaign("unknown build parameters or helper source")
    state = Path.home() / ".local/state/vera"
    # All signed helper replacement starts while holding the exact same owner
    # as the Resolve host. Check the longer-lived Conductor carrier lock too:
    # M4 releases native-owner during CPU/package work, but NOT carrier.lock.
    with native_owner(output_lane=True) as descriptor:
        active = active_conductor_cases(state)
        if active:
            raise ActiveNativeCampaign(
                "signed helper build forbidden while Conductor case owns native run: "
                + ", ".join(active)
            )
        env = os.environ.copy()
        env[OWNER_FD_ENV] = str(descriptor)
        env["PYTHONPATH"] = str(root / "python")
        completed = subprocess.run(
            ["/bin/sh", str(build)],
            env=env,
            pass_fds=(descriptor,),
            check=False,
            timeout=180,
        )
        return completed.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ActiveNativeCampaign,
        OSError,
        ValueError,
        subprocess.TimeoutExpired,
    ) as exc:
        print("BLOCK: guarded signed helper build:", str(exc), file=sys.stderr)
        raise SystemExit(78) from exc
