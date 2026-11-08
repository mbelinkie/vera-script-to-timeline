"""Strict original-source #473 proof observation and picture-only inference.

One-use pure host steps only; run with the original 3ea32582 source checkout.
This does not dispatch Resolve, fabricate native geometry, make provider calls,
or approve arbitrary inference conflicts. Check M4 edited verified first.
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


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RuntimeError("#473 original revision refused: " + reason)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def original() -> tuple[Any, Any, str, dict[str, Any]]:
    from vera_timeline_agent import qualification_output_package_v2 as package
    from vera_timeline_agent import resolve_test_bench_m4_runner as runner
    from vera_timeline_agent import resolve_test_queue as queue
    from vera_timeline_agent import resolve_test_queue_m4 as m4

    require(
        Path.cwd().resolve() == (ROOT / "pinned-code").resolve(),
        "not the original pinned checkout",
    )
    git = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        check=True,
        text=True,
        timeout=10,
    )
    require(git.stdout.strip() == SOURCE_COMMIT, "original source commit differs")
    require(
        package._sha(package._admission_code_source_graph_raw()) == SOURCE_GRAPH,
        "original source graph changed",
    )
    store = queue.Store(ROOT / "queue")
    plan_path = ROOT / "run/m4-plan.json"
    job_id = runner._find_job(store, sha(plan_path.read_bytes()))
    require(job_id is not None, "original job missing")
    assert isinstance(job_id, str)
    plan = m4._load_plan(store, job_id)
    report = m4.publish(store, job_id)
    require(
        report["state"] in {"queued", "awaiting_operator"}
        and [s["state"] for s in report["stages"]][:2] == ["verified", "verified"]
        and report["stages"][2]["state"] in {"pending", "awaiting_operator"}
        and report["stages"][3]["state"] == "pending",
        "original edited M4 not verified or revision already attempted",
    )
    pristine = ROOT / "run/pristine/session.json"
    edited = ROOT / "run/edited/session.json"
    require(
        pristine.is_file()
        and sha(pristine.read_bytes()) == PRISTINE_SHA
        and edited.is_file()
        and plan["baselineSession"] == {"path": str(pristine), "sha256": PRISTINE_SHA},
        "original prerequisite session differs",
    )
    return store, m4, job_id, plan


def proof() -> Any:
    from vera_timeline_agent.qualification_output_proof_v2 import (
        QualificationOutputProofV2,
    )

    session = ROOT / "run/revision/session.json"
    require(session.is_file(), "original proof session not prepared")
    return QualificationOutputProofV2(session, sha(session.read_bytes()))


def start() -> None:
    from vera_timeline_agent import resolve_test_bench_m4_runner as runner

    store, m4, job_id, _plan = original()
    report = m4.publish(store, job_id)
    require(
        report["state"] == "queued" and report["stages"][2]["state"] == "pending",
        "original M4 revision must be pending and unstarted",
    )
    require(
        runner._worker_once(store),
        "reviewed M4 worker could not acquire revision one-use handoff",
    )
    report = m4.publish(store, job_id)
    require(
        report["state"] == "awaiting_operator" and report["stage"] == "revision",
        "original revision stage did not acquire durable M4 intent",
    )
    print(
        json.dumps(
            {"state": "M4_revision_one_use_handoff", "jobId": job_id},
            sort_keys=True,
        ),
        flush=True,
    )


def prepare() -> None:
    from vera_timeline_agent.qualification_output_proof_v2 import (
        prepare_output_proof_v2,
    )

    store, m4, job_id, _plan = original()
    report = m4.publish(store, job_id)
    require(
        report["state"] == "awaiting_operator" and report["stage"] == "revision",
        "revision must have its original durable M4 intent before proof work",
    )
    pristine = ROOT / "run/pristine/session.json"
    edited = ROOT / "run/edited/session.json"
    destination = ROOT / "run/revision"
    require(
        not destination.exists() and not destination.is_symlink(),
        "proof preparation was already attempted",
    )
    session = prepare_output_proof_v2(
        destination,
        baseline_session=pristine,
        baseline_sha256=sha(pristine.read_bytes()),
        edited_session=edited,
        edited_sha256=sha(edited.read_bytes()),
    )
    print(
        json.dumps(
            {
                "state": "original_proof_session_prepared",
                "proof": {"path": str(session), "sha256": sha(session.read_bytes())},
            },
            sort_keys=True,
        )
    )


def observe() -> None:
    original()
    p = proof()
    require(
        not (p.root / "evidence.json").exists()
        and not (p.root / "evidence-receipt.json").exists(),
        "original observation already exists; inspect instead",
    )
    path = p.observe("synthetic-312")
    print(
        json.dumps(
            {
                "state": "original_A_picture_only_evidence_observed",
                "evidence": {"path": str(path), "sha256": sha(path.read_bytes())},
            },
            sort_keys=True,
        ),
        flush=True,
    )


def inspect_inference() -> None:
    original()
    p = proof()
    result = p.infer()
    print(
        json.dumps(
            {
                "state": "original_inference_read_only",
                "caseKinds": result["caseKinds"],
                "commands": result["commands"],
                "boundaryConflicts": result["boundaryConflicts"],
                "omission": result["omission"],
                "inferenceHash": result["inferenceHash"],
            },
            sort_keys=True,
        ),
        flush=True,
    )


def accept_inference() -> None:
    original()
    p = proof()
    result = p.infer()
    require(
        result["caseKinds"] == ["A"]
        and result["boundaryConflicts"] == []
        and result["omission"] is None
        and result["commands"]["boundary"] is not None
        and result["commands"]["trim"] is None,
        "a creative conflict, unexpected case or audio edit needs explicit review",
    )
    require(
        not (p.root / "inference-decision.json").exists()
        and not (p.root / "stage.json").exists(),
        "inference already decided; no replay",
    )
    decision = {
        "schemaVersion": "qualification-output-decision/v1",
        "proposalHash": result["inferenceHash"],
        "historyHash": "sha256:" + sha(b"[]\n"),
        "outcome": "accept",
    }
    stage = p.decide_inference(decision)
    require(
        stage["outcome"] == "accept" and stage["regeneration"] is None,
        "picture-only accepted inference unexpectedly demands narration",
    )
    print(
        json.dumps(
            {"state": "inference_accepted_original_picture_only", "stage": stage},
            sort_keys=True,
        ),
        flush=True,
    )


def propose() -> None:
    original()
    p = proof()
    require(
        not (p.root / "proposal.json").exists(),
        "existing proposal cannot be replaced",
    )
    candidate = p.proposal()
    print(
        json.dumps(
            {
                "state": "picture_only_revision_proposed_no_acceptance",
                "proposalHash": candidate["proposalHash"],
                "revisionComparison": candidate["revision"]["comparisonText"],
                "regeneration": candidate["request"]["handoff"],
            },
            sort_keys=True,
        ),
        flush=True,
    )


def accept_proposal() -> None:
    original()
    p = proof()
    require(
        not (p.root / "revision-ledger.json").exists(),
        "revision already decided; no replay",
    )
    inference = p.infer()
    require(
        inference["caseKinds"] == ["A"]
        and inference["boundaryConflicts"] == []
        and inference["omission"] is None
        and inference["commands"]["boundary"] is not None
        and inference["commands"]["trim"] is None,
        "proposal no longer matches accepted picture-only A boundary",
    )
    stage = p._stage()
    require(
        stage["outcome"] == "accept" and stage["regeneration"] is None,
        "proposal needs unsanctioned replacement audio or a new choice",
    )
    candidate = json.loads((p.root / "proposal.json").read_bytes())
    require(
        candidate["inference"]["inferenceHash"] == inference["inferenceHash"]
        and candidate["inferenceDecision"] == p._accepted_inference()
        and candidate["inferenceHistory"] == []
        and candidate["request"]["commands"]
        == {
            "boundary": inference["commands"]["boundary"],
            "trim": None,
            "omission": None,
        }
        and candidate["request"]["preparedMedia"] == []
        and candidate["request"]["handoff"] is None,
        "revision proposal alters scope, media, narration or source lineage",
    )
    decision = {
        "schemaVersion": "qualification-output-decision/v1",
        "proposalHash": candidate["proposalHash"],
        "historyHash": "sha256:" + sha(b"[]\n"),
        "outcome": "accept",
    }
    result = p.decide(decision)
    require(
        result["outcome"] == "accept"
        and result["history"] == [candidate["proposalHash"]],
        "original host did not accept only the authenticated proposal",
    )
    p.accepted_revision()
    print(
        json.dumps(
            {
                "state": "original_picture_only_revision_accepted",
                "proposalHash": candidate["proposalHash"],
                "revisedDocumentSha256": sha(
                    (p.root / "revision-document.json").read_bytes()
                ),
            },
            sort_keys=True,
        ),
        flush=True,
    )


def submit() -> None:
    from vera_timeline_agent import resolve_test_bench_carrier as carrier
    from vera_timeline_agent import resolve_test_queue as queue

    store, m4, job_id, _plan = original()
    report = m4.publish(store, job_id)
    require(
        report["stage"] == "revision"
        and report["stages"][2]["state"] == "awaiting_operator",
        "original M4 revision not awaiting authenticated proof",
    )
    p = proof()
    p.accepted_revision()
    receipt = {
        "schema": m4.RECEIPT_SCHEMA,
        "stage": "revision",
        "operationId": report["stages"][2]["operation_id"],
        "proof": {
            "path": str(p.session_path),
            "sha256": sha(p.session_path.read_bytes()),
        },
    }
    path = store.root / job_id / "receipt-revision.json"
    require(
        not path.exists() and not path.is_symlink(),
        "original revision receipt already submitted; no replay",
    )
    carrier._once(path, queue.canonical(receipt))
    m4.submit(store, job_id)
    report = m4.publish(store, job_id)
    require(
        report["state"] == "queued"
        and [stage["state"] for stage in report["stages"]]
        == ["verified", "verified", "verified", "pending"],
        "reviewed M4 revision did not independently accept its proof",
    )
    print(
        json.dumps(
            {
                "state": "original_M4_revision_verified",
                "jobId": job_id,
                "next": "rebuild",
            },
            sort_keys=True,
        ),
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "start",
            "prepare",
            "observe",
            "inspect",
            "accept-inference",
            "propose",
            "accept-proposal",
            "submit",
        ),
    )
    action = parser.parse_args().action
    if action == "start":
        start()
    elif action == "prepare":
        prepare()
    elif action == "observe":
        observe()
    elif action == "inspect":
        inspect_inference()
    elif action == "accept-inference":
        accept_inference()
    elif action == "propose":
        propose()
    elif action == "accept-proposal":
        accept_proposal()
    else:
        submit()


if __name__ == "__main__":
    # The original native controller remains SHA-pinned and unmodified. The
    # separately reviewed proof-only reader preserves its synthetic-312 case
    # identity instead of inventing an A-labelled native receipt.
    from issue473_proof_bridge import load

    load()
    main()
