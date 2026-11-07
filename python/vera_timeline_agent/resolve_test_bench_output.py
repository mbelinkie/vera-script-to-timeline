"""Unattended one-use output-host action chain, with read-only recovery.

This layer only automates the *already approved* qualification output host.
Each native operation uses the reviewed controller to prepare its own signed
request and the separately installed-source-verified carrier to execute it.
An incomplete carrier is never replaced by a new native effect, even after a
restart.  This module does not make editing or script decisions on its own.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

from . import resolve_test_bench_carrier as carrier
from . import resolve_test_queue as queue


def _pin(path: Path) -> dict[str, str]:
    return {
        "path": str(path),
        "sha256": hashlib.sha256(carrier._read(path)).hexdigest(),
    }


def _root(path: Path) -> None:
    carrier._private(path, create=True)


def _session(path: Path, digest: str) -> Any:
    from .qualification_output_controller_v2 import load_output_session

    return load_output_session(path, digest)


def _terminal(controller: Any) -> bool:
    from .qualification_output_proof_v2 import _load_terminal_output_with_comparison

    try:
        _load_terminal_output_with_comparison(controller)
        return True
    except (OSError, ValueError, KeyError, RuntimeError, TypeError):
        return False


def tick(
    root: Path,
    *,
    session_path: Path,
    session_sha256: str,
    installed: Path,
    consent_reference: str,
    consent_instruction: str,
    minimum_free_bytes: int = 256 * 1024 * 1024,
    python: Path | None = None,
) -> dict[str, Any]:
    """Advance at most one host effect, or inspect an already-issued one.

    The real consent instruction must come from a trusted agent's actual
    Producer directive.  This method does *not* authenticate chat transcripts
    and must not be exposed as an unauthenticated request handler.
    """
    from .qualification_output_controller_v2 import issue_operator_approval
    from .qualification_output_native_v2 import (
        action_plan_for_context,
        native_request_paths,
        verify_native_result,
    )

    _root(root)
    if (
        not consent_reference.strip()
        or not consent_instruction.strip()
        or len(consent_instruction) > 4096
    ):
        raise queue.QueueError("actual bounded Producer instruction required")
    if minimum_free_bytes < 1 or shutil.disk_usage(root).free < minimum_free_bytes:
        raise queue.QueueError("Test Bench actual free disk below reserved bound")
    controller = _session(session_path, session_sha256)
    actions = action_plan_for_context(controller.context)
    for sequence, action in enumerate(actions):
        path, _, _, request = native_request_paths(controller.context, sequence)
        step = root / f"native-{sequence:02d}"
        if path.exists() or path.is_symlink():
            if not (step / "intent.json").exists():
                raise queue.QueueError("unowned native result; no historical adoption")
            state = carrier.status(step)
            if state["state"] != "native_result_verified":
                raise queue.QueueError("partial, stale, or UNKNOWN native result")
            receipt = state["result"]
            verified = verify_native_result(Path(receipt["path"]), receipt["sha256"])
            if verified["action"] != action or verified["sequence"] != sequence:
                raise queue.QueueError("native action order/identity differs")
            # Ingest only authenticated original results. Repeated historical
            # inspection does not dispatch another native effect.
            if action == "capture_post":
                if not _terminal(controller):
                    controller.finalize_output(Path(receipt["path"]), receipt["sha256"])
                if not _terminal(controller):
                    raise queue.QueueError("native MOV/PCM is not terminal verified")
            continue
        if (step / "intent.json").exists():
            state = carrier.status(step)
            if state["state"] == "live":
                return {"state": "running", "action": action, "sequence": sequence}
            raise queue.QueueError("lost/uncertain native reply; inspect, never retry")
        # Preparing a reviewed native request itself reserves an immutable
        # effect slot. If it exists without our carrier, check it was never
        # started; a crash after request preparation is inspectable.
        plan = root / f"operator-plan-{sequence:02d}.json"
        approval = root / f"operator-approval-{sequence:02d}.json"
        if not request.exists():
            if not plan.exists():
                controller.prepare_operator_plan(plan)
            if not approval.exists():
                issue_operator_approval(
                    plan,
                    approval,
                    session_path=session_path,
                    session_sha256=session_sha256,
                    consent_reference=consent_reference,
                    consent_instruction=consent_instruction,
                )
            controller.prepare_next_native_request(approval)
        elif not approval.exists() or not plan.exists():
            raise queue.QueueError("unowned prepared request; refuse adoption")
        # Refuse a manually executed native request, not just a terminal
        # result: that is an uncertain operation owned by another carrier.
        if (request.parent / "native-start.json").exists():
            raise queue.QueueError("native effect already started outside Test Bench")
        if not request.exists():
            raise queue.QueueError("reviewed host did not create exact native request")
        request_pin = _pin(request)
        carrier.start(
            step,
            request,
            request_pin["sha256"],
            installed,
            **({} if python is None else {"python": python}),
        )
        return {"state": "running", "action": action, "sequence": sequence}

    if not _terminal(controller):
        raise queue.QueueError("host chain is not terminal MOV/PCM verified")
    final_path = native_request_paths(controller.context, len(actions) - 1)[0]
    return {
        "state": "terminal_native_verified",
        "session": {"path": str(session_path), "sha256": session_sha256},
        "capture": _pin(final_path),
    }


def drive(
    root: Path,
    *,
    session_path: Path,
    session_sha256: str,
    installed: Path,
    consent_reference: str,
    consent_instruction: str,
    max_seconds: int = 14400,
    minimum_free_bytes: int = 256 * 1024 * 1024,
) -> dict[str, Any]:
    """One start, bounded polling; on failure return without replaying."""
    if not isinstance(max_seconds, int) or not 60 <= max_seconds <= 14400:
        raise queue.QueueError("bounded 1-minute to 4-hour run required")
    _root(root)
    deadline_file = root / "deadline.json"
    if not deadline_file.exists():
        carrier._once(
            deadline_file,
            queue.canonical(
                {
                    "schema": "vera.test-bench-output-deadline/v1",
                    "session": {"path": str(session_path), "sha256": session_sha256},
                    "installed": str(installed),
                    "deadline": time.time() + max_seconds,
                }
            ),
        )
    deadline = json.loads(carrier._read(deadline_file))
    if (
        deadline.get("schema") != "vera.test-bench-output-deadline/v1"
        or deadline.get("session")
        != {"path": str(session_path), "sha256": session_sha256}
        or deadline.get("installed") != str(installed)
        or type(deadline.get("deadline")) not in (int, float)
    ):
        raise queue.QueueError("immutable output-chain deadline/identity changed")
    while time.time() < deadline["deadline"]:
        outcome = tick(
            root,
            session_path=session_path,
            session_sha256=session_sha256,
            installed=installed,
            consent_reference=consent_reference,
            consent_instruction=consent_instruction,
            minimum_free_bytes=minimum_free_bytes,
        )
        if outcome["state"] != "running":
            return outcome
        time.sleep(0.5)
    raise queue.QueueError("output deadline reached; do not replay native effects")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--session-sha256", required=True)
    parser.add_argument("--installed", type=Path, required=True)
    parser.add_argument("--consent-reference", required=True)
    parser.add_argument("--consent-instruction", required=True)
    parser.add_argument("--max-seconds", type=int, default=14400)
    parser.add_argument("--minimum-free-bytes", type=int, default=256 * 1024 * 1024)
    args = parser.parse_args()
    try:
        outcome = drive(
            args.root,
            session_path=args.session,
            session_sha256=args.session_sha256,
            installed=args.installed,
            consent_reference=args.consent_reference,
            consent_instruction=args.consent_instruction,
            max_seconds=args.max_seconds,
            minimum_free_bytes=args.minimum_free_bytes,
        )
        print(json.dumps(outcome, sort_keys=True))
        return 0 if outcome["state"] == "terminal_native_verified" else 2
    except (OSError, ValueError, TypeError, RuntimeError, KeyError) as error:
        print(json.dumps({"state": "unknown", "verified": False, "detail": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
