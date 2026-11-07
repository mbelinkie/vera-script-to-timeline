#!/usr/bin/env python3
"""One-use #472 acceptance using the real authenticated M4 output host.

Run on a private, newly provisioned Resolve project. The genuine, closed
qualification host owns construct/save_reopen; this script only orchestrates
already-reviewed controller and source-verified carrier entry points.

Each command is at most one native transition. Never retry a native intent
or adopt an earlier #312 result. All reports stay in private Mac storage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from vera_timeline_agent import resolve_test_bench_carrier as carrier
from vera_timeline_agent import resolve_test_bench_output as host_actions
from vera_timeline_agent import resolve_test_queue_m4_provision as provision
from vera_timeline_agent.qualification_output_controller_v2 import (
    HOST_STATE_ROOT,
    LANE,
    QualificationOutputController,
    _canonical,
    _hash,
    _publish,
    _read,
    load_output_session,
)
from vera_timeline_agent.qualification_output_native_v2 import (
    native_request_paths,
    verify_native_result,
)
from vera_timeline_agent.qualification_output_package_v2 import (
    MATRIX_PROFILE,
    load_qualification_package_v2,
)
from vera_timeline_agent.resolve_native_owner import preflight_selected_disposable
from vera_timeline_agent.workflow_v2_cli import build_output_release_v2

PRIVATE_ROOT = Path.home() / (
    "Library/Application Support/VERA/private-preparation/issue-312-m4-acceptance"
)
ADMISSION = (
    PRIVATE_ROOT / "compiler-refresh-01/admitted-final-01/"
    "qualification-output-package-admission.json"
)
CASE_ID = "synthetic-472"
CONSENT_REFERENCE = "ChatGPT producer conversation 2026-11-07: Okay go ahead"
CONSENT_INSTRUCTION = (
    "Okay go ahead: run #472 on a new disposable Resolve Studio target "
    "using the actual guarded M4 output adapter; never replay the original "
    "partial #312 target, never begin the #473 campaign."
)


def _pin(path: Path) -> dict[str, str]:
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _admission() -> Any:
    if not ADMISSION.is_file() or ADMISSION.is_symlink():
        raise RuntimeError("sealed original synthetic admission unavailable")
    raw = ADMISSION.read_bytes()
    a = load_qualification_package_v2(ADMISSION, hashlib.sha256(raw).hexdigest())
    if (
        a.profile != MATRIX_PROFILE
        or a.manifest["timeline"]["durationFrames"] != 1407
        or len(a.manifest["events"]) != 11
        or len(a.manifest["tracks"]) != 6
    ):
        raise RuntimeError("current admitted synthetic matrix differs")
    expected = next(
        (
            e
            for e in a.manifest["events"]
            if e["id"] == "f5871317-bdb5-558b-8c05-6ed0fe4b6889"
        ),
        None,
    )
    if expected is None or expected["recordRange"] != {
        "startFrame": 715,
        "endFrame": 929,
    }:
        raise RuntimeError("native target event/record bounds changed")
    return a


def _record(root: Path) -> dict[str, Any]:
    file = root / "setup-pin.json"
    if not file.is_file() or file.is_symlink():
        raise RuntimeError("original setup pin is unavailable")
    value = json.loads(carrier._read(file))
    if (
        set(value) != {"schema", "session", "target"}
        or value["schema"] != "vera.472-guarded-m4-physical/v1"
    ):
        raise RuntimeError("setup pin has unsupported shape")
    return value


def check() -> dict[str, Any]:
    a = _admission()
    return {
        "state": "admission_authenticated",
        "profile": a.profile,
        "events": len(a.manifest["events"]),
        "tracks": len(a.manifest["tracks"]),
        "timelineFrames": a.manifest["timeline"]["durationFrames"],
        "nativeEffects": False,
    }


def prepare(root: Path) -> dict[str, Any]:
    if root.exists() or root.is_symlink():
        raise RuntimeError("a fresh one-use run root is required")
    a = _admission()  # All existing evidence checked BEFORE project creation.
    carrier._private(root, create=True)
    provision_root = root / "provision"
    provision.reserve(provision_root)
    advanced = provision.advance(provision_root)
    if advanced != {"state": "stage_verified", "stage": "initial", "created": True}:
        raise RuntimeError("independent native project creation was not verified")
    target = provision._target(
        provision_root, "initial", provision._plan(provision_root)
    )
    preflight_selected_disposable(target, require_empty=True)
    release_root = root / "release"
    build_output_release_v2(release_root)
    controller = QualificationOutputController(
        HOST_STATE_ROOT,
        admission=a,
        release_root=release_root,
        target=target,
        case_id=CASE_ID,
        phase="pristine",
        invocation_id=str(__import__("uuid").uuid4()),
    )
    session = {
        "schemaVersion": "qualification-output-session/v1",
        "lane": LANE,
        "profile": MATRIX_PROFILE,
        "admissionPath": str(ADMISSION),
        "admissionSha256": _hash(_read(ADMISSION)),
        "releaseRoot": str(release_root),
        "context": controller.context,
        "hostJournalRoot": str(HOST_STATE_ROOT),
    }
    session_path = root / "session.json"
    _publish(session_path, _canonical(session))
    controller.prepare_operator_plan(root / "operator-plan.json")
    record = {
        "schema": "vera.472-guarded-m4-physical/v1",
        "session": _pin(session_path),
        "target": target,
    }
    carrier._once(root / "setup-pin.json", _canonical(record))
    loaded = load_output_session(session_path, record["session"]["sha256"])
    if loaded.context != controller.context:
        raise RuntimeError("new session does not roundtrip exact host context")
    return {
        "state": "fresh_native_target_and_signed_host_ready",
        "target": target,
        "context": controller.context,
        "session": record["session"],
        "nativeOutputEffects": False,
    }


def _receipt(root: Path, sequence: int) -> dict[str, Any]:
    pin = _record(root)
    ctl = load_output_session(Path(pin["session"]["path"]), pin["session"]["sha256"])
    result_path, _, _, _ = native_request_paths(ctl.context, sequence)
    step = root / f"native-{sequence:02d}"
    if not (step / "intent.json").exists():
        return {
            "state": "not_started",
            "action": "construct" if sequence == 0 else "save_reopen",
        }
    status = carrier.status(step)
    if status["state"] != "native_result_verified":
        return {
            "state": status["state"],
            "sequence": sequence,
            "verified": False,
        }
    raw = carrier._read(result_path)
    verified = verify_native_result(result_path, hashlib.sha256(raw).hexdigest())
    if (
        verified.get("sequence") != sequence
        or verified.get("status") != "complete"
        or verified.get("action") != ("construct" if sequence == 0 else "save_reopen")
        or verified.get("target") != pin["target"]
    ):
        return {"state": "result_not_complete", "sequence": sequence, "verified": False}
    return {
        "state": "complete",
        "sequence": sequence,
        "verified": True,
        "action": verified["action"],
        "sha256": hashlib.sha256(raw).hexdigest(),
        "nativeGeometry": verified.get("nativeGeometry"),
    }


def status(root: Path) -> dict[str, Any]:
    first = _receipt(root, 0)
    second = _receipt(root, 1)
    return {
        "state": (
            "both_native_actions_verified"
            if first["state"] == second["state"] == "complete"
            else "pending_or_failed"
        ),
        "construct": first,
        "saveReopen": second,
    }


def tick(root: Path) -> dict[str, Any]:
    pin = _record(root)
    first = _receipt(root, 0)
    second = _receipt(root, 1)
    if second["state"] == "complete":
        return status(root)  # NEVER dispatch later render/capture actions.
    if first["state"] not in ("not_started", "complete", "live"):
        raise RuntimeError("first native result is unsafe; no retry")
    if second["state"] not in ("not_started", "live"):
        raise RuntimeError("save/reopen result is unsafe; no retry")
    ctl = load_output_session(Path(pin["session"]["path"]), pin["session"]["sha256"])
    outcome = host_actions.tick(
        root,
        session_path=Path(pin["session"]["path"]),
        session_sha256=pin["session"]["sha256"],
        installed=ctl.release_root,
        consent_reference=CONSENT_REFERENCE,
        consent_instruction=CONSENT_INSTRUCTION,
    )
    return {"state": "one_host_transition", "transition": outcome}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "prepare", "tick", "status"))
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    if args.action != "check" and args.root is None:
        parser.error("--root is required")
    try:
        if args.action == "check":
            result = check()
        elif args.action == "prepare":
            result = prepare(args.root)
        elif args.action == "tick":
            result = tick(args.root)
        else:
            result = status(args.root)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        print(
            json.dumps({"state": "failed_closed", "reason": str(error)}, sort_keys=True)
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
