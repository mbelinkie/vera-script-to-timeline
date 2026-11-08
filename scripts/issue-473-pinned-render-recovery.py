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

import argparse
import hashlib
import importlib.util
import json
import os
import pwd
import subprocess
import sys
import time
from datetime import timedelta
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


def first_missing_native_result(
    root: Path, controller: Any, carrier: Any, native: Any
) -> tuple[int, str, Path]:
    """Identify the sole prepared/unstarted native action from original files.

    Never call native.next_native_operation to cross an immutable prepared
    request: that official operation-tail API intentionally refuses an intent
    without a completed result. Observe already-published genuine results and
    the carrier's authenticated ingestion instead of pretending it is new.
    """
    for sequence, action in enumerate(
        native.action_plan_for_context(controller.context)
    ):
        result, _authority, _native_intent, request = native.native_request_paths(
            controller.context, sequence
        )
        if not result.is_file() or result.is_symlink():
            need(
                not result.exists() and not result.is_symlink(),
                "native result is not a regular completed file",
            )
            return sequence, action, request
        step = root / f"native-{sequence:02d}"
        state = carrier.status(step)
        need(
            state["state"] == "native_result_verified"
            and state["verified"] is True
            and (step / "host-ingested.json").is_file(),
            "preceding native effect not independently host authenticated",
        )
        verified = native.verify_native_result(result, sha(result.read_bytes()))
        need(
            verified.get("status") == "complete"
            and verified.get("action") == action
            and verified.get("context") == controller.context,
            "preceding signed native result differs",
        )
    raise RuntimeError("all original native results already complete")


def approve_existing_render_output(
    root: Path,
    controller: Any,
    carrier: Any,
    native: Any,
    *,
    session_path: Path,
    session_sha: str,
) -> None:
    """Issue genuine attributed authority for ONLY signed polling/post-capture.

    Original native and host already explicitly support existing output for
    poll_render/capture_post, but their historical agent issuance wrapper
    mistakenly insisted that the MOV be absent for every stage. Reuse the
    original review-only proposal, its operator-approval constructor, exact
    native verifier with documented require_output_absent=False, and its
    append-only agent-issuance format. No approval is synthesized for new
    construct, queue, start, edited, foreign or uncertain operations.
    """
    from vera_timeline_agent import qualification_output_controller_v2 as host
    from vera_timeline_agent.workflow_v2_cli import _verify_output_release

    # A clean child may be executing its already-claimed one-use operation.
    # Do not examine its uncommitted tail or issue a new authority mid-effect.
    count = len(native.action_plan_for_context(controller.context))
    for prior_sequence in range(count):
        native_result, _, _, _ = native.native_request_paths(
            controller.context, prior_sequence
        )
        if (
            root / f"native-{prior_sequence:02d}" / "intent.json"
        ).exists() and not native_result.exists():
            return
    sequence, action, pending_request = first_missing_native_result(
        root, controller, carrier, native
    )
    if action not in {"poll_render", "capture_post"}:
        return
    result_path, _, _, native_request = native.native_request_paths(
        controller.context, sequence
    )
    if (
        native_request != pending_request
        or native_request.exists()
        or result_path.exists()
    ):
        return
    approval_path = root / f"operator-approval-{sequence:02d}.json"
    if approval_path.exists() or approval_path.is_symlink():
        return
    predecessor = "start_render" if action == "poll_render" else "poll_render"
    previous = root / f"native-{sequence - 1:02d}"
    if not (previous / "host-ingested.json").exists():
        return  # Original controller must authenticate and ingest first.
    state = carrier.status(previous)
    need(
        state["state"] == "native_result_verified" and state["verified"] is True,
        "post-start approval requires actual authentic predecessor",
    )
    retained = json.loads(carrier._read(previous / "host-ingested.json"))
    need(
        retained.get("action") == predecessor and retained.get("status") == "complete",
        "original host predecessor is not complete",
    )
    plan = root / f"operator-plan-{sequence:02d}.json"
    if not plan.exists():
        controller.prepare_operator_plan(plan)
    raw = host._read(plan)
    proposal = host._operator_plan_proposal(raw)
    need(
        proposal["operator"] == pwd.getpwuid(os.getuid()).pw_name,
        "actual OS operator differs",
    )
    approval = host._approval_from_proposal(proposal)
    controller._environment_current()
    manifest = _verify_output_release(controller.release_root)
    expected = (
        native.NATIVE_STATE_ROOT
        / "renders"
        / host._json_hash(controller.journal.chain)
        / (controller.context["binding"]["bindingSha256"] + ".mov")
    )
    need(
        approval["context"] == controller.context
        and approval["target"] == controller.context["target"]
        and approval["invocationId"] == controller.context["invocationId"]
        and approval["profile"] == controller.admission.profile
        and approval["packageRoot"] == str(controller.admission.package_root)
        and approval["admissionSha256"]
        == sha(host._read(controller.admission.admission_path))
        and approval["releaseManifestSha256"] == sha(host._read(manifest))
        and approval["outputPath"] == str(expected)
        and expected.is_file()
        and not expected.is_symlink()
        and approval["actionPlan"]
        == list(native.action_plan_for_context(controller.context)),
        "existing MOV is not exactly the signed original approved output",
    )
    host._safe(approval_path)
    issuance_path = approval_path.with_name(approval_path.name + ".issuance.json")
    need(
        not approval_path.exists()
        and not issuance_path.exists()
        and not issuance_path.is_symlink()
        and approval_path.parent.is_dir()
        and approval_path.parent.stat().st_uid == os.getuid()
        and approval_path.parent.stat().st_mode & 0o077 == 0,
        "original private one-use approval destination is not empty",
    )
    now = controller.trust.checked_now()
    approval["issuedAt"] = host._iso(now)
    approval["expiresAt"] = host._iso(
        now + timedelta(seconds=native.MAX_LIFETIME_SECONDS)
    )
    need(
        host._read(plan) == raw
        and host._canonical(host._operator_plan_proposal(raw))
        == host._canonical(proposal),
        "signed proposal changed while issuing output authority",
    )
    approved_raw = host._canonical(approval)
    native.verify_operator_approval(
        approved_raw,
        context=proposal["context"],
        profile=proposal["profile"],
        admission_sha256=proposal["admissionSha256"],
        release_manifest_sha256=proposal["releaseManifestSha256"],
        require_live=True,
        require_output_absent=False,
    )
    consent = "Continue until closed"
    host._publish(
        issuance_path,
        host._canonical(
            {
                "schemaVersion": "qualification-output-agent-issuance/v1",
                "issuanceMode": "agent_mediated_not_transcript_authenticated",
                "consentReference": (
                    "https://github.com/mbelinkie/vera-script-to-timeline/issues/473"
                ),
                "consentInstruction": consent,
                "sessionPath": str(session_path),
                "sessionSha256": session_sha,
                "planSha256": sha(raw),
                "approvalSha256": sha(approved_raw),
                "scope": approval,
            }
        ),
    )
    host._publish(approval_path, approved_raw)
    print("approved_existing_original_MOV_for", action, sequence, flush=True)


def dispatch_exact_prepared_render(
    root: Path, controller: Any, carrier: Any, native: Any, helper: Any
) -> None:
    """Dispatch a prepared original signed render effect, never reprepare it.

    The reviewed host may write its native *preparation intent* before its
    generic idle-target preflight discovers the host's own reservation. That
    intent blocks next_native_operation by design. It does not mean Resolve
    executed anything: the native-start file and carrier intent distinguish
    started/uncertain effects. Require both to be ABSENT and all predecessors
    authenticated, then delegate only preflight to the strict reviewed helper.
    """
    sequence, action, request_path = first_missing_native_result(
        root, controller, carrier, native
    )
    need(action in helper.RENDER_ACTIONS, "non-render stage cannot use helper")
    native_result, authority_path, intent_path, source_request = (
        native.native_request_paths(controller.context, sequence)
    )
    need(
        source_request == request_path
        and not native_result.exists()
        and not native_result.is_symlink()
        and authority_path.is_file()
        and not authority_path.is_symlink()
        and intent_path.is_file()
        and not intent_path.is_symlink()
        and request_path.is_file()
        and not request_path.is_symlink(),
        "original native signed preparation is incomplete or ambiguous",
    )
    step = root / f"native-{sequence:02d}"
    need(
        not (step / "intent.json").exists()
        and not (step / "intent.json").is_symlink()
        and not (request_path.parent / "native-start.json").exists()
        and not (request_path.parent / "native-start.json").is_symlink(),
        "original native effect is already started or uncertain; never replay",
    )
    request_sha = sha(carrier._read(request_path))
    verified = carrier._checked_request(
        request_path, request_sha, controller.release_root
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
            "not the exact signed render-stage target",
        )
        helper.preflight_owned_render(signed)

    carrier.start(
        step,
        request_path,
        request_sha,
        controller.release_root,
        preflight=preflight,
    )
    print("original_native_dispatched_once", sequence, action, flush=True)


def main(phase: str = "pristine") -> None:
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
    need(phase in {"pristine", "edited"}, "unsupported recovery phase")
    session_path = RUN / f"run/{phase}/session.json"
    session_sha = SESSION_SHA
    if phase == "edited":
        launch_intent = RUN / "run/edited-actions/one-use-run-intent.json"
        need(
            launch_intent.is_file() and not launch_intent.is_symlink(),
            "original edited one-use host launch is missing",
        )
        pinned = json.loads(launch_intent.read_bytes())
        need(
            pinned.get("schema") == "vera.issue473-original-edited-host-once/v1"
            and pinned.get("pristineSessionSha256") == SESSION_SHA
            and pinned.get("session", {}).get("path") == str(session_path),
            "edited launch provenance differs",
        )
        session_sha = pinned["session"]["sha256"]
        need(
            isinstance(session_sha, str)
            and len(session_sha) == 64
            and all(ch in "0123456789abcdef" for ch in session_sha),
            "invalid original edited session digest",
        )
    need(sha(session_path.read_bytes()) == session_sha, "original session byte changed")
    controller = load_output_session(session_path, session_sha)
    need(controller.context.get("phase") == phase, "original host phase differs")
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

    root = RUN / f"run/{phase}-actions"
    need(root.is_dir(), "original stage journal absent")
    actions = native.action_plan_for_context(controller.context)
    expected_prefix = (
        ("construct", "save_reopen", "capture_pre")
        if phase == "pristine"
        else ("observe_edited", "save_reopen", "capture_pre")
    )
    need(tuple(actions[:3]) == expected_prefix, "original native prefix changed")
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
        approve_existing_render_output(
            root,
            controller,
            carrier,
            native,
            session_path=session_path,
            session_sha=session_sha,
        )
        try:
            result = output.tick(
                root,
                session_path=session_path,
                session_sha256=session_sha,
                installed=controller.release_root,
                consent_reference="https://github.com/mbelinkie/vera-script-to-timeline/issues/473",
                consent_instruction="Continue until closed",
                minimum_free_bytes=1073741824,
            )
        except native.OutputConsistencyError as error:
            if str(error) == "approved output already exists":
                approve_existing_render_output(
                    root,
                    controller,
                    carrier,
                    native,
                    session_path=session_path,
                    session_sha=session_sha,
                )
            else:
                need(
                    str(error)
                    == (
                        "native operation has an immutable intent without "
                        "a terminal result; read-only recovery required"
                    ),
                    "host refused an unknown or foreign native operation",
                )
                dispatch_exact_prepared_render(
                    root, controller, carrier, native, helper
                )
            continue
        except owner.NativeOwnerError as refusal:
            need(
                refusal.reason == "selected_disposable_not_idle"
                and (
                    "selected project has unresolved output operation"
                    in refusal.private_detail
                    or refusal.private_detail == "pending, active or unknown render job"
                ),
                "foreign/shared native owner refused stage",
            )
            # Only the original signed/prepared render stage is eligible;
            # never restart a previously started or unknown operation.
            dispatch_exact_prepared_render(root, controller, carrier, native, helper)
            continue

        if result["state"] == "terminal_native_verified":
            store = queue.Store(RUN / "queue")
            plan_path = RUN / "run/m4-plan.json"
            job_id = runner._find_job(store, sha(carrier._read(plan_path)))
            need(job_id is not None, "original M4 job not enrolled")
            if phase == "pristine":
                runner._submit_original(store, job_id, "pristine", result)
                print("original_pristine_receipt_submitted", job_id, flush=True)
            else:
                from vera_timeline_agent import resolve_test_queue_m4 as m4

                report = m4.publish(store, job_id)
                need(
                    report["stage"] == "edited"
                    and report["stages"][1]["state"] == "awaiting_operator",
                    "edited M4 stage is not awaiting original receipt",
                )
                receipt = {
                    "schema": m4.RECEIPT_SCHEMA,
                    "stage": "edited",
                    "operationId": report["stages"][1]["operation_id"],
                    "session": result["session"],
                    "capture": result["capture"],
                }
                retained = store.root / job_id / "receipt-edited.json"
                carrier._once(retained, queue.canonical(receipt))
                print(
                    "original_edited_receipt_preserved_for_independent_M4",
                    str(retained),
                    sha(carrier._read(retained)),
                    flush=True,
                )
            return
        need(result.get("state") == "running", "unexpected host output state")
        time.sleep(0.5)
    raise RuntimeError("original render recovery deadline; do not replay effects")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--phase", choices=("pristine", "edited"), default="pristine")
    args = cli.parse_args()
    try:
        main(args.phase)
    except Exception as error:
        print("original_recovery_refused", type(error).__name__, str(error), flush=True)
        raise
