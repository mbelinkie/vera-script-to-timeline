"""One-use #473 edited-native host continuation on the exact frozen source.

Must run with PYTHONPATH=python from #473's immutable 3ea32582 source
checkout. This script is NOT part of that source graph. It only orchestrates
the original reviewed host for a genuinely saved same-target native edit.

prepare: build a new edited session, no native effect.
drive: one bounded launch of the original official v2 observe/render host.
       No automatic retry after a failed, partial or unknown native action.
After terminal completion M4 verification happens separately, and only with
the corrected, independently audited M4 rational-rate verifier.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path.home() / ".local/state/vera/issue-473-studio-05"
FROZEN = ROOT / "pinned-code"
ORIGINAL_COMMIT = "3ea32582a6761ead588762ba2df2f95bf80bd8e9"
ORIGINAL_GRAPH_SHA = "1dc6db11389bb6f322b0f05446f142d9fdd072d873019aa507803c3f0cd1c7cc"
PRISTINE_SESSION_SHA = (
    "59919054ae9080c63f50263a931b17a6e21486359a21c8c1d086a15955f590e2"
)
SAVED_EDIT_INTENT_SHA = (
    "e0ed830884ab80cdcbdf3ef6187d6eabd194fdbcf88c0acc72b80b058148b14d"
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError("#473 edited host refused: " + message)


def inputs() -> tuple[object, str, dict[str, object]]:
    from vera_timeline_agent import qualification_output_package_v2 as package
    from vera_timeline_agent import resolve_test_bench_m4_runner as runner
    from vera_timeline_agent import resolve_test_queue as queue
    from vera_timeline_agent import resolve_test_queue_m4 as m4

    require(Path.cwd().resolve() == FROZEN.resolve(), "not original source directory")
    rev = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    ).stdout.strip()
    require(rev == ORIGINAL_COMMIT, "original host commit changed")
    require(
        package._sha(package._admission_code_source_graph_raw()) == ORIGINAL_GRAPH_SHA,
        "original signed source graph changed",
    )
    original_session = ROOT / "run/pristine/session.json"
    require(
        original_session.is_file()
        and digest(original_session.read_bytes()) == PRISTINE_SESSION_SHA,
        "authenticated pristine session differs",
    )
    edit_intent = ROOT / "run/edit-ui-intent.json"
    require(
        edit_intent.is_file()
        and not edit_intent.is_symlink()
        and digest(edit_intent.read_bytes()) == SAVED_EDIT_INTENT_SHA,
        "original saved identity-preserving edit intent differs",
    )
    store = queue.Store(ROOT / "queue")
    plan_path = ROOT / "run/m4-plan.json"
    job_id = runner._find_job(store, digest(plan_path.read_bytes()))
    require(job_id is not None, "M4 job missing")
    assert isinstance(job_id, str)
    plan = m4._load_plan(store, job_id)
    report = m4.publish(store, job_id)
    require(
        report["state"] == "awaiting_operator"
        and report["stage"] == "edited"
        and [stage["state"] for stage in report["stages"]]
        == ["verified", "awaiting_operator", "pending", "pending"],
        "only original M4 edited handoff is eligible",
    )
    intent = json.loads(edit_intent.read_bytes())
    require(
        intent.get("initialTarget") == plan["initialTarget"]
        and intent.get("stageOperationId") == report["stages"][1]["operation_id"]
        and plan["baselineSession"]
        == {"path": str(original_session), "sha256": PRISTINE_SESSION_SHA},
        "M4 stage/target edit identity differs",
    )
    return store, job_id, plan


def prepare() -> None:
    from vera_timeline_agent.qualification_output_proof_v2 import (
        prepare_edited_output_session,
    )

    _store, job_id, plan = inputs()
    root = ROOT / "run/edited"
    require(
        not root.exists() and not root.is_symlink(), "edited session already attempted"
    )
    session = prepare_edited_output_session(
        root,
        baseline_session=Path(plan["baselineSession"]["path"]),
        baseline_sha256=plan["baselineSession"]["sha256"],
    )
    from vera_timeline_agent.qualification_output_controller_v2 import (
        load_output_session,
    )

    sha = digest(session.read_bytes())
    ctrl = load_output_session(session, sha)
    require(
        ctrl.context["phase"] == "edited"
        and ctrl.context["target"] == plan["initialTarget"],
        "new edited host session does not bind the saved original target",
    )
    print(
        json.dumps(
            {
                "state": "edited_session_prepared_no_native_effect",
                "jobId": job_id,
                "session": {"path": str(session), "sha256": sha},
                "target": ctrl.context["target"],
            },
            sort_keys=True,
        ),
        flush=True,
    )


def drive() -> None:
    from vera_timeline_agent import resolve_test_bench_carrier as carrier
    from vera_timeline_agent import resolve_test_bench_output as output
    from vera_timeline_agent import resolve_test_queue as queue
    from vera_timeline_agent.qualification_output_controller_v2 import (
        load_output_session,
    )

    store, job_id, plan = inputs()
    edited_session = ROOT / "run/edited/session.json"
    require(
        edited_session.is_file() and not edited_session.is_symlink(),
        "edited host session not already prepared",
    )
    sha = digest(edited_session.read_bytes())
    controller = load_output_session(edited_session, sha)
    require(
        controller.context["phase"] == "edited"
        and controller.context["target"] == plan["initialTarget"],
        "edited native target or phase differs",
    )
    terminal_receipt = store.root / job_id / "receipt-edited.json"
    require(
        not terminal_receipt.exists() and not terminal_receipt.is_symlink(),
        "edited M4 receipt already exists; do not replay",
    )
    root = ROOT / "run/edited-actions"
    carrier._private(root, create=True)
    intent = root / "one-use-run-intent.json"
    require(
        not intent.exists() and not intent.is_symlink(),
        "one-use edited native launch already consumed",
    )
    carrier._once(
        intent,
        queue.canonical(
            {
                "schema": "vera.issue473-original-edited-host-once/v1",
                "jobId": job_id,
                "session": {"path": str(edited_session), "sha256": sha},
                "pristineSessionSha256": PRISTINE_SESSION_SHA,
                "savedEditIntentSha256": SAVED_EDIT_INTENT_SHA,
            }
        ),
    )
    result = output.drive(
        root,
        session_path=edited_session,
        session_sha256=sha,
        installed=controller.release_root,
        consent_reference="https://github.com/mbelinkie/vera-script-to-timeline/issues/473",
        consent_instruction="Continue until closed",
        max_seconds=7200,
        minimum_free_bytes=1073741824,
    )
    require(
        result["state"] == "terminal_native_verified"
        and result["session"] == {"path": str(edited_session), "sha256": sha},
        "edited host not yet authenticated terminal MOV/PCM",
    )
    from vera_timeline_agent import resolve_test_queue_m4 as m4

    report = m4.publish(store, job_id)
    receipt = {
        "schema": m4.RECEIPT_SCHEMA,
        "stage": "edited",
        "operationId": report["stages"][1]["operation_id"],
        "session": result["session"],
        "capture": result["capture"],
    }
    # Publish only immutable original evidence. Stage submission is a
    # separately authenticated action through the corrected M4 verifier.
    carrier._once(terminal_receipt, queue.canonical(receipt))
    print(
        json.dumps(
            {
                "state": "edited_native_output_terminal_ready_to_submit",
                "jobId": job_id,
                "receipt": {
                    "path": str(terminal_receipt),
                    "sha256": digest(terminal_receipt.read_bytes()),
                },
                "nativeCapture": result["capture"],
            },
            sort_keys=True,
        ),
        flush=True,
    )


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("prepare", "drive"))
    args = cli.parse_args()
    if args.action == "prepare":
        prepare()
    else:
        drive()


if __name__ == "__main__":
    main()
