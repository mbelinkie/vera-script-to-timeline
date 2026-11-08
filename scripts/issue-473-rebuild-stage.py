"""Source-pinned one-use fresh-target #473 M4 rebuild continuation.

Only original signed host, actual V2 revised-preflight admission, distinct
pre-enrolled empty Resolve project, and independent native render are allowed.
Run from the original 3ea32582 checkout; immutable native receipts are never
replayed and no M4 acceptance is claimed before external verification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path.home() / ".local/state/vera/issue-473-studio-05"
SOURCE_COMMIT = "3ea32582a6761ead588762ba2df2f95bf80bd8e9"
SOURCE_GRAPH = "1dc6db11389bb6f322b0f05446f142d9fdd072d873019aa507803c3f0cd1c7cc"
PRISTINE_SHA = "59919054ae9080c63f50263a931b17a6e21486359a21c8c1d086a15955f590e2"


def need(value: bool, explanation: str) -> None:
    if not value:
        raise RuntimeError("#473 original rebuild refused: " + explanation)


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def prerequisites() -> tuple[Any, Any, str, dict[str, Any], dict[str, Any]]:
    from vera_timeline_agent import qualification_output_package_v2 as package
    from vera_timeline_agent import resolve_test_bench_m4_runner as runner
    from vera_timeline_agent import resolve_test_queue as queue
    from vera_timeline_agent import resolve_test_queue_m4 as m4

    need(
        Path.cwd().resolve() == (ROOT / "pinned-code").resolve(),
        "not the original signed source checkout",
    )
    git = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    need(git.stdout.strip() == SOURCE_COMMIT, "source checkout changed")
    need(
        package._sha(package._admission_code_source_graph_raw()) == SOURCE_GRAPH,
        "source graph was modified after signing",
    )
    config = runner.validate_config(json.loads((ROOT / "config.json").read_bytes()))
    need(
        Path(config["root"]) == ROOT / "run"
        and Path(config["queueRoot"]) == ROOT / "queue"
        and config["caseId"] == "synthetic-312",
        "original campaign configuration or roots differ",
    )
    store = queue.Store(ROOT / "queue")
    plan = ROOT / "run/m4-plan.json"
    job_id = runner._find_job(store, sha(plan.read_bytes()))
    need(job_id is not None, "original queue enrollment is missing")
    assert isinstance(job_id, str)
    m4_plan = m4._load_plan(store, job_id)
    report = m4.publish(store, job_id)
    need(
        report["state"] in {"queued", "awaiting_operator"}
        and [row["state"] for row in report["stages"]][:3]
        == ["verified", "verified", "verified"]
        and report["stages"][3]["state"] in {"pending", "awaiting_operator"},
        "M4 revised acceptance is missing or fresh effect was already spent",
    )
    need(
        m4_plan["baselineSession"]["sha256"] == PRISTINE_SHA,
        "rebuild does not refer to original accepted pristine session",
    )
    return store, m4, job_id, m4_plan, config


def start() -> None:
    from vera_timeline_agent import resolve_test_bench_m4_runner as runner
    from vera_timeline_agent import resolve_test_queue_m4_provision as provision

    store, m4, job_id, plan, _config = prerequisites()
    report = m4.publish(store, job_id)
    need(
        report["state"] == "queued" and report["stages"][3]["state"] == "pending",
        "original rebuild M4 handoff not unspent",
    )
    selection = provision.select(ROOT / "run/provision", "fresh")
    need(
        selection == {"state": "selected_verified", "stage": "fresh"},
        "wrong fresh target",
    )
    provisioned = provision.completed(ROOT / "run/provision")
    need(
        provisioned["fresh"] == plan["freshTarget"]
        and provisioned["initial"] == plan["initialTarget"],
        "selected target not from originally authenticated two-target plan",
    )
    need(runner._worker_once(store), "M4 did not reserve the one-use fresh rebuild")
    report = m4.publish(store, job_id)
    need(
        report["state"] == "awaiting_operator" and report["stage"] == "rebuild",
        "fresh rebuild stage failed to acquire durable M4 intent",
    )
    print(
        json.dumps(
            {"state": "M4_fresh_rebuild_one_use_handoff", "jobId": job_id},
            sort_keys=True,
        ),
        flush=True,
    )


def prepare() -> None:
    from vera_timeline_agent import resolve_test_bench_m4_runner as runner
    from vera_timeline_agent.qualification_output_proof_v2 import (
        QualificationOutputProofV2,
        prepare_revised_output_session,
    )

    store, m4, job_id, plan, config = prerequisites()
    report = m4.publish(store, job_id)
    need(
        report["state"] == "awaiting_operator" and report["stage"] == "rebuild",
        "fresh rebuild M4 intent not enrolled",
    )
    proof_path = ROOT / "run/revision/session.json"
    need(proof_path.is_file(), "original revision proof missing")
    proof = QualificationOutputProofV2(proof_path, sha(proof_path.read_bytes()))
    proof.accepted_revision()
    destination = ROOT / "run/rebuild"
    need(
        not destination.exists() and not destination.is_symlink(),
        "fresh rebuild session already attempted; do not replay",
    )
    package_root = Path(config["packageRoot"])
    preparation_paths = runner._matrix_preparation_paths(
        package_root, case_id=config["caseId"]
    )
    narration = runner._matrix_narration_paths(
        package_root,
        Path(config["narrationEvidenceRoot"]),
        case_id=config["caseId"],
    )
    session = prepare_revised_output_session(
        destination,
        proof_session=proof_path,
        proof_sha256=sha(proof_path.read_bytes()),
        package_root=package_root,
        preparation_paths=preparation_paths,
        target=plan["freshTarget"],
        narration_evidence_paths=narration,
    )
    from vera_timeline_agent.qualification_output_controller_v2 import (
        load_output_session,
    )

    controller = load_output_session(session, sha(session.read_bytes()))
    need(
        controller.context["phase"] == "rebuild"
        and controller.context["target"] == plan["freshTarget"],
        "revised host session is not reserved to exact fresh target",
    )
    print(
        json.dumps(
            {
                "state": "accepted_revision_fresh_host_prepared",
                "jobId": job_id,
                "session": {"path": str(session), "sha256": sha(session.read_bytes())},
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

    store, m4, job_id, plan, _config = prerequisites()
    report = m4.publish(store, job_id)
    need(
        report["state"] == "awaiting_operator" and report["stage"] == "rebuild",
        "fresh M4 native handoff no longer current",
    )
    session = ROOT / "run/rebuild/session.json"
    need(
        session.is_file() and not session.is_symlink(),
        "fresh signed host session absent",
    )
    digest = sha(session.read_bytes())
    controller = load_output_session(session, digest)
    need(
        controller.context["phase"] == "rebuild"
        and controller.context["target"] == plan["freshTarget"],
        "fresh host context differs",
    )
    receipt = store.root / job_id / "receipt-rebuild.json"
    need(
        not receipt.exists() and not receipt.is_symlink(),
        "fresh native receipt already exists; no replay",
    )
    root = ROOT / "run/rebuild-actions"
    carrier._private(root, create=True)
    intent = root / "one-use-run-intent.json"
    need(
        not intent.exists() and not intent.is_symlink(),
        "native rebuilt host operation already started; no replay",
    )
    carrier._once(
        intent,
        queue.canonical(
            {
                "schema": "vera.issue473-original-rebuild-host-once/v1",
                "jobId": job_id,
                "session": {"path": str(session), "sha256": digest},
                "pristineSessionSha256": PRISTINE_SHA,
                "freshTarget": plan["freshTarget"],
            }
        ),
    )
    result = output.drive(
        root,
        session_path=session,
        session_sha256=digest,
        installed=controller.release_root,
        consent_reference="https://github.com/mbelinkie/vera-script-to-timeline/issues/473",
        consent_instruction="Keep going, don't stop",
        max_seconds=7200,
        minimum_free_bytes=1073741824,
    )
    need(
        result["state"] == "terminal_native_verified"
        and result["session"] == {"path": str(session), "sha256": digest},
        "new native rebuild is not terminal MOV/PCM verified",
    )
    m4_receipt = {
        "schema": m4.RECEIPT_SCHEMA,
        "stage": "rebuild",
        "operationId": report["stages"][3]["operation_id"],
        "session": result["session"],
        "capture": result["capture"],
    }
    carrier._once(receipt, queue.canonical(m4_receipt))
    print(
        json.dumps(
            {
                "state": "original_rebuild_native_receipt_ready_for_independent_M4",
                "receipt": {"path": str(receipt), "sha256": sha(receipt.read_bytes())},
            },
            sort_keys=True,
        ),
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "prepare", "drive"))
    action = parser.parse_args().action
    if action == "start":
        start()
    elif action == "prepare":
        prepare()
    else:
        drive()


if __name__ == "__main__":
    from issue473_proof_bridge import load

    load()
    main()
