"""Clean-process entry point for the fixed, reviewed VERA Delivery v2 launcher.

This file MUST remain outside the ``vera_timeline_agent`` package: Resolve's
reviewed bootstrap refuses a preloaded application runtime.  No user-supplied
Python source, module name, shell string or callable is executed here.
"""

from __future__ import annotations

import hashlib
import json
import os
import runpy
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("fixed carrier arguments required")
    root = Path(sys.argv[1])
    if not root.is_absolute() or any(p.is_symlink() for p in (root, *root.parents)):
        raise RuntimeError("unsafe carrier run root")
    intent_path = root / "intent.json"
    if intent_path.is_symlink() or intent_path.stat().st_size > 16384:
        raise RuntimeError("unsafe intent")
    intent = json.loads(intent_path.read_bytes())
    if intent.get("schema") != "vera.test-bench-native-carrier/v1":
        raise RuntimeError("invalid carrier intent")
    installed = Path(intent["installedRoot"])
    if not installed.is_absolute() or any(
        p.is_symlink() for p in (installed, *installed.parents)
    ):
        raise RuntimeError("unsafe installed release root")
    launcher = installed / "VERA Delivery v2.py"
    request = installed / "vera-delivery-v2/request.json"
    if any(p.is_symlink() for p in (launcher, request)):
        raise RuntimeError("installed code/request symlink refused")
    if hashlib.sha256(request.read_bytes()).hexdigest() != intent["requestSha256"]:
        raise RuntimeError("installed request SHA differs before native effect")
    # The pinned launcher independently verifies its own installed release,
    # authority, target, exact request and one-use native effect journal.
    import DaVinciResolveScript as dvr  # type: ignore[import-not-found]

    resolve = dvr.scriptapp("Resolve")
    if not resolve:
        raise RuntimeError("Resolve Studio Local scripting unavailable")
    os.environ["VERA_NATIVE_OWNER_FD"] = sys.argv[2]
    runpy.run_path(
        str(launcher), run_name="__main__", init_globals={"resolve": resolve}
    )


if __name__ == "__main__":
    main()
