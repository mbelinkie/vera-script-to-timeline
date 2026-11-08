"""Clean-process entry point for the fixed, reviewed VERA Delivery v2 launcher.

This file MUST remain outside the ``vera_timeline_agent`` package: Resolve's
reviewed bootstrap refuses a preloaded application runtime.  No user-supplied
Python source, module name, shell string or callable is executed here.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import runpy
import sys
from pathlib import Path
from typing import Any

_INSTALLED_SDK = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Developer/Scripting/Modules/DaVinciResolveScript.py"
)


def _resolve_via_official_sdk(*, sdk_override: Path | None = None) -> Any:
    """Resolve the vendor's self-replacing module, not its bootstrap wrapper.

    The installed DaVinciResolveScript.py deliberately assigns
    sys.modules[__name__] = fusionscript. Executing a spec into a local
    module object without re-reading sys.modules leaves no scriptapp method.
    """
    if sdk_override is None:
        try:
            import DaVinciResolveScript as dvr  # type: ignore[import-not-found]
        except ImportError:
            dvr = None
    else:
        dvr = None
    if dvr is None:
        sdk = _INSTALLED_SDK if sdk_override is None else sdk_override
        if sdk.is_symlink() or not sdk.is_file():
            raise RuntimeError("official installed Resolve scripting SDK unavailable")
        spec = importlib.util.spec_from_file_location("DaVinciResolveScript", sdk)
        if spec is None or spec.loader is None:
            raise RuntimeError("official installed Resolve scripting SDK cannot load")
        initial = importlib.util.module_from_spec(spec)
        previous = sys.modules.get(spec.name)
        sys.modules[spec.name] = initial
        try:
            spec.loader.exec_module(initial)
            dvr = sys.modules.get(spec.name, initial)
        except BaseException:
            if previous is None:
                sys.modules.pop(spec.name, None)
            else:
                sys.modules[spec.name] = previous
            raise
    scriptapp = getattr(dvr, "scriptapp", None)
    if not callable(scriptapp):
        raise RuntimeError("official SDK did not expose scriptapp after bootstrap")
    resolve = scriptapp("Resolve")
    if not resolve:
        raise RuntimeError("Resolve Studio Local scripting unavailable")
    return resolve


def main() -> None:
    if sys.argv[1:] == ["--probe-sdk"]:
        resolve = _resolve_via_official_sdk()
        print(
            json.dumps(
                {
                    "state": "official_sdk_connected_read_only",
                    "product": resolve.GetProductName(),
                    "version": resolve.GetVersionString(),
                    "nativeEffects": False,
                },
                sort_keys=True,
            )
        )
        return
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
    resolve = _resolve_via_official_sdk()
    os.environ["VERA_NATIVE_OWNER_FD"] = sys.argv[2]
    runpy.run_path(
        str(launcher), run_name="__main__", init_globals={"resolve": resolve}
    )


if __name__ == "__main__":
    main()
