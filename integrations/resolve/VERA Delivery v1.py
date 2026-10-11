"""Repository-owned Workflow Integration v1; Resolve injects `resolve`."""

import hashlib
import json
import sys
import uuid
from pathlib import Path

PLUGIN_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)
# Resolve can exec a script without __file__; retain #107's documented root.
SCRIPT_PATH = Path(globals().get("__file__", str(PLUGIN_ROOT / "VERA Delivery v1.py")))


def launch(injected_resolve: object) -> None:
    root = SCRIPT_PATH.resolve().parent
    release_root = root / "vera-delivery-v1"
    request_path = release_root / "request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    release_path = release_root / "release.json"
    if (
        hashlib.sha256(release_path.read_bytes()).hexdigest()
        != request["releaseSha256"]
    ):
        raise RuntimeError("installed release hash differs from the operator request")
    release = json.loads(release_path.read_text(encoding="utf-8"))
    if release.get("schemaVersion") != "vera-injected-delivery-release/v1":
        raise RuntimeError("unsupported installed release")
    for entry in release["files"]:
        path = root / entry["path"]
        if (
            not path.resolve().is_relative_to(root)
            or path.is_symlink()
            or path.stat().st_size != entry["sizeBytes"]
            or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]
        ):
            raise RuntimeError("installed source differs from the versioned release")
    runtime = release_root / "python"
    declared_python = {entry["path"] for entry in release["files"]}
    installed_python = {
        path.relative_to(root).as_posix() for path in runtime.rglob("*.py")
    } | {SCRIPT_PATH.name}
    if installed_python != declared_python:
        raise RuntimeError("installed Python source inventory differs from release")
    if list(runtime.rglob("*.pyc")):
        raise RuntimeError("runtime bytecode cache present; reinstall clean release")
    for name, module in tuple(sys.modules.items()):
        if name == "vera_timeline_agent" or name.startswith("vera_timeline_agent."):
            module_path = getattr(module, "__file__", None)
            if not module_path or not Path(module_path).resolve().is_relative_to(
                runtime
            ):
                raise RuntimeError("another VERA runtime is loaded; restart Resolve")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(runtime))
    from vera_timeline_agent.workflow_launcher import run_installed_request

    report = run_installed_request(injected_resolve, request_path)
    print(report)


try:
    launch(globals().get("resolve"))
except Exception as error:
    failure = {
        "status": "workflow_launcher_failed",
        "verified": False,
        "detail": str(error),
    }
    # Retain bootstrap failures without importing unverified installed code.
    try:
        config = json.loads(
            (SCRIPT_PATH.resolve().parent / "vera-delivery-v1/request.json").read_text()
        )
        evidence = Path(config["evidenceDir"])
        package = Path(config["packageDir"]).resolve()
        protected_roots = [package]
        attestation_path = Path(config["attestationPath"])
        if attestation_path.exists():
            protected_roots.append(
                Path(json.loads(attestation_path.read_text())["packageDir"]).resolve()
            )
        if not evidence.is_absolute() or any(
            evidence.resolve().is_relative_to(root) for root in protected_roots
        ):
            raise RuntimeError("unsafe evidence directory")
        evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = evidence / f"bootstrap-refusal-{uuid.uuid4().hex}.json"
        with path.open("x", encoding="utf-8") as stream:
            json.dump(failure, stream, indent=2, sort_keys=True)
        path.chmod(0o400)
        failure["reportPath"] = str(path)
    except Exception:
        failure["reportRetention"] = "unavailable; retain this Console output"
    print(json.dumps(failure, indent=2, sort_keys=True))
