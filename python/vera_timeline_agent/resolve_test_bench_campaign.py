"""Reusable, one-start, fail-closed Test Bench native-output stage controller.

This accepts only an independently admitted, source-pinned v2 output session.
It delegates ALL Resolve effects to the existing reviewed native-output driver,
never to GUI events, XML imports, or a second timeline engine.  A launch is
spent BEFORE calling the driver; after a crash, only read-only status is legal.
The same verified host contract can be reused by a later #313 benchmark, but
this module does not enroll, approve, or run any #313 experiment by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from . import resolve_test_bench_carrier as carrier
from . import resolve_test_bench_diagnostic_journal as diagnostics
from . import resolve_test_bench_output as output
from . import resolve_test_queue as queue

SCHEMA = "vera.test-bench-stage-controller/v1"
_FIELDS = frozenset(
    {
        "schema",
        "root",
        "session",
        "installed",
        "releaseManifestSha256",
        "caseId",
        "phase",
        "target",
        "deadlineUnix",
        "maxDiskBytes",
        "consentReference",
        "consentInstruction",
    }
)
_PHASES = frozenset({"pristine", "edited", "rebuild"})


def _require(ok: bool, detail: str) -> None:
    if not ok:
        raise queue.QueueError("Test Bench stage refused: " + detail)


def _path(value: Any) -> Path:
    _require(
        isinstance(value, str)
        and Path(value).is_absolute()
        and ".." not in Path(value).parts,
        "absolute safe path required",
    )
    assert isinstance(value, str)
    return Path(value)


def validate(value: Any) -> dict[str, Any]:
    """Validate the exact, previously consented one-stage launch contract."""
    from .resolve_test_queue_m4 import _ref, _target

    _require(isinstance(value, dict) and set(value) == _FIELDS, "closed plan required")
    assert isinstance(value, dict)
    _require(value["schema"] == SCHEMA, "wrong plan schema")
    for field in ("root", "installed"):
        _path(value[field])
    session = _ref(value["session"], "stage session")
    _path(session["path"])
    _require(
        isinstance(value["releaseManifestSha256"], str)
        and len(value["releaseManifestSha256"]) == 64
        and all(ch in "0123456789abcdef" for ch in value["releaseManifestSha256"]),
        "pinned release SHA-256 required",
    )
    queue.simple_id(value["caseId"], "caseId")
    _require(value["phase"] in _PHASES, "unreviewed native stage")
    _target(value["target"], "stage target")
    _require(
        type(value["deadlineUnix"]) in (int, float)
        and math.isfinite(value["deadlineUnix"])
        and value["deadlineUnix"] > 0,
        "finite immutable cumulative deadline required",
    )
    queue.limited_int(value["maxDiskBytes"], "maxDiskBytes", 1048576, 4 * 1024**3)
    for field in ("consentReference", "consentInstruction"):
        _require(
            isinstance(value[field], str) and 0 < len(value[field].strip()) <= 4096,
            "actual Producer consent and attribution required",
        )
    # A configuration cannot intentionally use its own journal as source.
    root = _path(value["root"])
    _require(
        root != _path(value["installed"])
        and root != _path(session["path"])
        and root not in _path(session["path"]).parents,
        "stage journal, release and immutable session must be independent",
    )
    return dict(value)


def _host(plan: dict[str, Any]) -> Any:
    """Reauthenticate source and installed-release bytes before any effect."""
    from .workflow_v2_cli import _verify_output_release

    installed = _path(plan["installed"])
    manifest = _verify_output_release(installed)
    _require(
        hashlib.sha256(carrier._read(manifest)).hexdigest()
        == plan["releaseManifestSha256"],
        "installed release manifest differs from source pin",
    )
    session = plan["session"]
    controller = output._session(_path(session["path"]), session["sha256"])
    context = controller.context
    _require(
        context.get("caseId") == plan["caseId"]
        and context.get("phase") == plan["phase"]
        and context.get("target") == plan["target"]
        and controller.release_root == installed,
        "original host session/target/case/phase differs",
    )
    return controller


def inspect(plan: dict[str, Any]) -> dict[str, Any]:
    """Read-only reconciliation: never creates or reissues a native operation."""
    value = validate(plan)
    root = _path(value["root"])
    if not root.is_dir() or not (root / "stage-intent.json").is_file():
        return {"state": "not_started", "verified": False}
    carrier._private(root)
    _require(
        carrier._read(root / "stage-intent.json") == queue.canonical(value),
        "spent stage intent differs; UNKNOWN",
    )
    controller = _host(value)
    if not output._terminal(controller):
        return {"state": "unknown_or_running", "verified": False}
    receipt = root / "terminal.json"
    if not receipt.is_file():
        return {"state": "terminal_host_verified", "verified": True}
    original = json.loads(carrier._read(receipt))
    _require(
        isinstance(original, dict)
        and original.get("schema") == "vera.test-bench-stage-terminal/v1"
        and original.get("session") == value["session"],
        "saved terminal identity differs",
    )
    from .qualification_output_native_v2 import verify_native_result

    capture = original.get("capture")
    _require(isinstance(capture, dict), "terminal capture pin missing")
    verified = verify_native_result(_path(capture["path"]), capture["sha256"])
    _require(
        verified.get("status") == "complete"
        and verified.get("action") == "capture_post"
        and verified.get("target") == value["target"]
        and verified.get("context") == controller.context,
        "terminal native capture not independently verified",
    )
    return {"state": "terminal_native_verified", "verified": True, "capture": capture}


def start(plan: dict[str, Any]) -> dict[str, Any]:
    """Attempt a stage once. Never resume a consumed stage by running this again."""
    value = validate(plan)
    root = _path(value["root"])
    carrier._private(root, create=True)
    with carrier._lock(root):
        # Also refuses when an earlier process died between writing its
        # durable intent and launching the first approved native action.
        _require(
            not (root / "stage-intent.json").exists()
            and not (root / "stage-intent.json").is_symlink(),
            "one-use stage spent; use inspect, never replay",
        )
        diagnostic = diagnostics.DiagnosticJournal(
            root,
            case_id=value["caseId"],
            phase=value["phase"],
            stage=value["phase"],
            pins={
                "targetSha256": hashlib.sha256(
                    queue.canonical(value["target"])
                ).hexdigest(),
            },
        )
        diagnostic.emit("admission", "before_admission", status="pending")
        try:
            _host(value)
            diagnostic.emit("admission", "after_admission")
        except BaseException as error:
            with suppress(BaseException):
                diagnostic.emit("exception", "before_admission", exception=error)
            raise
        clock = time.time()
        _require(
            math.isfinite(clock) and 60 <= value["deadlineUnix"] - clock <= 14400,
            "cumulative authority has less than 60 seconds or exceeds four hours",
        )
        _require(
            shutil.disk_usage(root).free >= value["maxDiskBytes"],
            "reserved native disk budget unavailable",
        )
        # Every action also checks this same absolute ceiling immediately
        # before dispatch (including after a slow source preflight).
        diagnostic.emit("claim", "before_claim", status="pending")
        carrier._once(root / "stage-intent.json", queue.canonical(value))
        try:
            diagnostic.emit("claim", "after_claim")
            remaining = min(14400, math.ceil(value["deadlineUnix"] - clock))
            result = output.drive(
                root / "native-actions",
                session_path=_path(value["session"]["path"]),
                session_sha256=value["session"]["sha256"],
                installed=_path(value["installed"]),
                consent_reference=value["consentReference"],
                consent_instruction=value["consentInstruction"],
                max_seconds=remaining,
                hard_deadline=value["deadlineUnix"],
                minimum_free_bytes=value["maxDiskBytes"],
                diagnostic=diagnostic,
            )
        except BaseException as error:
            with suppress(BaseException):
                diagnostic.emit("exception", "after_claim", exception=error)
            raise
        _require(
            result.get("state") == "terminal_native_verified",
            "reviewed native driver did not return terminal MOV/PCM",
        )
        controller = _host(value)
        _require(output._terminal(controller), "signed host MOV/PCM is not terminal")
        from .qualification_output_native_v2 import verify_native_result

        capture = result["capture"]
        verified = verify_native_result(_path(capture["path"]), capture["sha256"])
        _require(
            verified.get("status") == "complete"
            and verified.get("action") == "capture_post"
            and verified.get("target") == value["target"]
            and verified.get("context") == controller.context,
            "signed capture target/source differs",
        )
        diagnostic.emit("verification", "before_finalize", status="pending")
        carrier._once(
            root / "terminal.json",
            queue.canonical(
                {
                    "schema": "vera.test-bench-stage-terminal/v1",
                    "session": value["session"],
                    "capture": capture,
                }
            ),
        )
        diagnostic.emit("verification", "after_finalize")
        return {
            "state": "terminal_native_verified",
            "verified": True,
            "session": value["session"],
            "capture": capture,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "inspect"))
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        plan = json.loads(carrier._read(args.config, 32 * 1024))
        result = start(plan) if args.action == "start" else inspect(plan)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["state"] == "terminal_native_verified" else 2
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        print(json.dumps({"state": "blocked", "verified": False, "detail": str(error)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
