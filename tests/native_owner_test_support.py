"""Isolate installed Resolve launcher subprocesses from host owner state."""

from __future__ import annotations

import os
from pathlib import Path


def isolated_native_owner_env(test_root: Path) -> dict[str, str]:
    home = test_root / ".private-native-owner-home"
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    environment.pop("VERA_NATIVE_OWNER_FD", None)
    return environment
