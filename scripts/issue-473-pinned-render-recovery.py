"""Once-only #473 continuation of its *unstarted* original render reservation.

This is a diagnostic recovery carrier, not a source-graph override. It runs
the untouched, exact admission-pinned 3ea32582 Python host, and uses an
independently SHA-pinned, read-only render-owner preflight from the newer
#473 branch through the old carrier's explicit preflight argument. All native
effects still execute solely through the original installed VERA Delivery v2
source and its original signed native request/authority. No monkeypatch or
reissue of any previous native operation is permitted.

Only intended for the fully identified, already approved #473 campaign 05.
Any stale seal, different checkout/source, missing original receipt, partial
operation, other owner or native-start record stops permanently.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any

RUN = Path.home() / ".local/state/vera/issue-473-studio-05"
FROZEN = RUN / "pinned-code"
SOURCE = (
    Path.home()
    / ".local/state/vera/issue-473-studio-01/checkout/python"
    / "vera_timeline_agent/resolve_test_bench_render_preflight.py"
)
FROZEN_COMMIT = "3ea32582a6761ead588762ba2df2f95bf80bd8e9"
SOURCE_SHA = "6c8ebcffe1d0cc2c4bf7d211a224a166e6441d3aee70052ea59fcfd939205ed2"
SESSION_SHA = "59919054ae9080c63f50263a931b17a6e21486359a21c8c1d086a15955f590e2"
SOURCE_GRAPH_SHA = "1dc6db11389bb6f322b0f05446f142d9fdd072d873019aa507803c3f0cd1c7cc"


def need(ok: bool, explanation: str) -> None:
    if not ok:
        raise RuntimeError("Issue 473 original recovery refused: " + explanation)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    # Checked before any import of the original host; no source-graph patching.
    need(Path.cwd().resolve() == FROZEN.resolve(), "run in original frozen checkout")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()
    need(head == FROZEN_COMMIT, "original Git commit differs")
    need(SOURCE.is_file() and not SOURCE.is_symlink(), "new preflight source missing")
    need(sha(SOURCE.read_bytes()) == SOURCE_SHA, "new preflight source hash differs")

    from vera_timeline_agent import qualification_output_native_v2 as native
    from vera_timeline_agent import qualification_output_package_v2 as package
    from vera_timeline_agent import resolve_native_owner as owner
    from vera_timeline_agent import resolve_test_bench_carrier as carrier
    from vera_timeline_agent import resolve_test_bench_m4_runner as runner
    from vera_timeline_agent import resolve_test_bench_output as output
    from vera_timeline_agent import resolve_test_queue as queue
    from vera_timeline_agent.qualification_output_controller_v2 import (
        load_output_session,
    )

    need(
        package._sha(package._admission_code_source_graph_raw()) == SOURCE_GRAPH_SHA,
        "retained Python/TypeScript source graph is not original",
    )
    session_path = RUN / "run/pristine/session.json"
    need(sha(session_path.read_bytes()) == SESSION_SHA, "original session byte changed")
    controller = load_output_session(session_path, SESSION_SHA)
    need(controller.context.get("phase") == "pristine", "not original pristine phase")
    need(controller.context.get("caseId") == "synthetic-312", "original case changed")

    # Import as a *separate external preflight*, never add files to frozen
    # vera_timeline_agent package or mutate its sealed code source graph.
    spec = importlib.util.spec_from_file_location(
        "vera_timeline_agent.resolve_test_bench_render_preflight", SOURCE
    )
    need(spec is not None and spec.loader is not None, "verified helper loader absent")
    assert spec is not None and spec.loader is not None
    helper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helper
    try:
        spec.loader.exec_module(helper)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    need(isinstance(helper, ModuleType), "verified helper is not a module")

    root = RUN / "run/pristine-actions"
    need(root.is_dir(), "original stage journal absent")
    actions = native.action_plan_for_context(controller.context)
    need(
        actions[:3] == ("construct", "save_reopen", "capture_pre")
        or actions[:3] == ["construct", "save_reopen", "capture_pre"],
        "original native prefix changed",
    )
    # Original immutable complete receipts must have been *already* ingested.
    for sequence, action in enumerate(actions[:3]):
        step = root / f"native-{sequence:02d}"
        receipt = json.loads(carrier._read(step / "host-ingested.json"))
        need(
            receipt.get("action") == action and receipt.get("status") == "complete",
            "original native prefix lacks host-authenticated completion",
        )
        need(
            carrier.status(step)["state"] == "native_result_verified",
            "original native prefix is no longer authentic",
        )

    expires = time.monotonic() + 1800
    while time.monotonic() < expires:
        try:
            result = output.tick(
                root,
                session_path=session_path,
                session_sha256=SESSION_SHA,
                installed=controller.release_root,
                consent_reference="https://github.com/mbelinkie/vera-script-to-timeline/issues/473",
                consent_instruction="Continue until closed",
                minimum_free_bytes=1073741824,
            )
        except owner.NativeOwnerError as refusal:
            need(
                refusal.reason == "selected_disposable_not_idle"
                and (
                    "selected project has unresolved output operation"
                    in refusal.private_detail
                    or refusal.private_detail
                    == "pending, active or unknown render job"
                ),
                "foreign/shared native owner refused stage",
            )
            # The old generic preflight only refuses the host's OWN signed
            # reservation. Delegate that one read-only stage check to the
            # reviewed external helper, then use the OLD carrier for effects.
            pending = None
            for sequence, action in enumerate(actions):
                result_path, _auth, _intent, request_path = native.native_request_paths(
                    controller.context, sequence
                )
                if not result_path.exists():
                    pending = (sequence, action, request_path)
                    break
            need(pending is not None, "no unfinished original native step")
            sequence, action, request_path = pending
            need(action in helper.RENDER_ACTIONS, "non-render stage cannot use helper")
            need(
                request_path.is_file() and not request_path.is_symlink(),
                "exact original prepared native request missing",
            )
            step = root / f"native-{sequence:02d}"
            need(
                not (step / "intent.json").exists()
                and not (step / "intent.json").is_symlink()
                and not (request_path.parent / "native-start.json").exists(),
                "original native effect is started or uncertain; never replay",
            )
            digest = sha(carrier._read(request_path))
            verified = carrier._checked_request(
                request_path, digest, controller.release_root
            )
            need(
                verified["sequence"] == sequence
                and verified["action"] == action
                and verified["context"] == controller.context,
                "original signed operation identity differs",
            )

            def preflight(
                target: Any, *, require_empty: bool, signed: dict[str, Any] = verified
            ) -> None:
                need(
                    target == controller.context["target"] and not require_empty,
                    "not an exact signed render-stage target",
                )
                helper.preflight_owned_render(signed)

            carrier.start(
                step,
                request_path,
                digest,
                controller.release_root,
                preflight=preflight,
            )
            print("original_native_dispatched_once", sequence, action, flush=True)
            continue

        if result["state"] == "terminal_native_verified":
            store = queue.Store(RUN / "queue")
            plan_path = RUN / "run/m4-plan.json"
            job_id = runner._find_job(store, sha(carrier._read(plan_path)))
            need(job_id is not None, "original M4 job not enrolled")
            runner._submit_original(store, job_id, "pristine", result)
            print("original_pristine_receipt_submitted", job_id, flush=True)
            return
        need(result.get("state") == "running", "unexpected host output state")
        time.sleep(0.5)
    raise RuntimeError("original render recovery deadline; do not replay effects")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("original_recovery_refused", type(error).__name__, str(error), flush=True)
        raise
