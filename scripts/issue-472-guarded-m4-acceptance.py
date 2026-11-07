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
    admit_qualification_package_v2,
    load_qualification_package_v2,
)
from vera_timeline_agent.resolve_native_owner import preflight_selected_disposable
from vera_timeline_agent.v2_package import verify_v2_package
from vera_timeline_agent.workflow_v2_cli import build_output_release_v2

PACKAGE = Path.home() / ".local/state/vera/issue-472-guarded-m4-02/package"
EXPECTED_BUILD_ID = "4ece95a3-8b4e-413e-bef2-b4e6512341a6"
PREPS = (
    Path.home() / "Library/Application Support/VERA/qualification-output-preparation/"
    "issue178-20261016-01/cases/issue312-package-current-S-approved-v2/published"
)
SPEECH = (
    Path.home()
    / ".codex/worktrees/f861/VERA Script to Timeline/out/issue312/rehearsal-speech-v1"
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


def _inventory() -> tuple[dict[str, Path], dict[str, dict[str, Path]]]:
    checked = verify_v2_package(PACKAGE)
    if checked.build_id != EXPECTED_BUILD_ID or checked.event_count != 11:
        raise RuntimeError("verified current compiler synthetic package changed")
    builds = list((PACKAGE / "Builds").iterdir())
    if len(builds) != 1 or not builds[0].is_dir():
        raise RuntimeError("original synthetic package has no unique build")
    manifest = json.loads((builds[0] / "timeline-manifest.json").read_bytes())
    deps = json.loads((builds[0] / "compiler-dependencies.json").read_bytes())
    if (
        manifest["timeline"]["durationFrames"] != 1407
        or manifest["timeline"]["frameRate"]
        != {"numerator": 24000, "denominator": 1001}
        or len(manifest["events"]) != 11
        or len(manifest["tracks"]) != 6
        or len(manifest["preparationBindings"]) != 6
        or len(deps["narrationBoundaryEvidence"]) != 3
        or deps["compiler"]["sourceHash"]
        != "sha256:"
        + hashlib.sha256(
            (Path.cwd() / "packages/contracts/src/compiler-core-v2.ts").read_bytes()
        ).hexdigest()
    ):
        raise RuntimeError("current compiled fixture geometry or compiler differs")
    preps: dict[str, Path] = {}
    for row in manifest["preparationBindings"]:
        key = row["requirementKey"].removeprefix("sha256:")
        path = PREPS / key / "receipt.json"
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("retained preparation evidence unavailable")
        preps[f"sha256:{key}"] = path
    narration: dict[str, dict[str, Path]] = {}
    for row in deps["narrationBoundaryEvidence"]:
        block = row["blockId"]
        if row["verification"].get("method") != "measured_audio_boundaries/v1":
            raise RuntimeError("retained speech measurement type differs")
        timing = (
            SPEECH / "cache" / row["audio"]["locator"].rsplit("/", 1)[0] / "timing.json"
        )
        measurement = SPEECH / row["verification"]["measurementArtifactLocator"]
        if any(x.is_symlink() or not x.is_file() for x in (timing, measurement)):
            raise RuntimeError("retained speech evidence unavailable")
        narration[block] = {"timing": timing, "measurement": measurement}
    return preps, narration


def _admission(root: Path) -> Any:
    admission_path = root / "admitted/qualification-output-package-admission.json"
    if not admission_path.is_file() or admission_path.is_symlink():
        raise RuntimeError("fresh current-runtime admission unavailable")
    raw = admission_path.read_bytes()
    a = load_qualification_package_v2(admission_path, hashlib.sha256(raw).hexdigest())
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
            if e["eventId"] == "f5871317-bdb5-558b-8c05-6ed0fe4b6889"
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
    preps, narrations = _inventory()
    return {
        "state": "source_inventory_present_before_fresh_admission",
        "preparationReceipts": len(preps),
        "narrationMeasurements": len(narrations),
        "timelineFrames": 1407,
        "nativeEffects": False,
    }


def verify(root: Path) -> dict[str, Any]:
    admission = _admission(root)
    return {
        "state": "current_admission_authenticated",
        "admission": _pin(admission.admission_path),
        "profile": admission.profile,
        "eventCount": len(admission.manifest["events"]),
        "trackCount": len(admission.manifest["tracks"]),
        "timelineFrames": admission.manifest["timeline"]["durationFrames"],
        "nativeEffects": False,
    }


def admit(root: Path) -> dict[str, Any]:
    if root.exists() or root.is_symlink():
        raise RuntimeError("a fresh one-use run root is required")
    preps, narrations = _inventory()
    carrier._private(root, create=True)
    admission = admit_qualification_package_v2(
        root / "admitted",
        profile=MATRIX_PROFILE,
        package_root=PACKAGE,
        preparation_paths=preps,
        narration_evidence_paths=narrations,
    )
    a = _admission(root)
    if a.admission_path != admission.admission_path:
        raise RuntimeError("fresh source admission identity changed")
    return {
        "state": "fresh_source_admission_authenticated",
        "admission": _pin(admission.admission_path),
        "nativeEffects": False,
    }


def prepare(root: Path) -> dict[str, Any]:
    a = _admission(root)  # Verify new sealed admission BEFORE any SDK effects.
    if (root / "provision").exists() or (root / "setup-pin.json").exists():
        raise RuntimeError("one-use target provision already started")
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
        "admissionPath": str(a.admission_path),
        "admissionSha256": _hash(_read(a.admission_path)),
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
        max_native_sequence=1,
    )
    return {"state": "one_host_transition", "transition": outcome}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("check", "admit", "verify", "prepare", "tick", "status")
    )
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    if args.action != "check" and args.root is None:
        parser.error("--root is required")
    try:
        if args.action == "check":
            result = check()
        elif args.action == "admit":
            result = admit(args.root)
        elif args.action == "verify":
            result = verify(args.root)
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
