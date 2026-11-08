"""Read-only proof and explicitly audited correction of the one #473 M4 verdict.

The original #473 stage's receipt is IMMUTABLE and already consumed. Its
signed Studio readback has a rational frame-rate object, while the original
M4 checker incorrectly expected a display string. Reauthenticate every
preceding M4 check with the *unchanged, source-graph-pinned* 3ea32582 host,
require that the original verifier fail at exactly that last predicate, and
apply the independently corrected rational predicate to the authenticated
native result. Never rerun a native operation, mint authority, or alter the
session, original receipt, installed source graph or project.

An explicit --apply makes a ONE-WAY, audited database correction only when
the original stage is precisely unknown with its original matching pinned
receipt and all later stages are untouched. --inspect NEVER mutates state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

RUN = Path.home() / ".local/state/vera/issue-473-studio-05"
PINNED = RUN / "pinned-code"
JOB = "resolve-reverse-6d7e20fad0b64b418d6a94930526557d"
FROZEN_COMMIT = "3ea32582a6761ead588762ba2df2f95bf80bd8e9"
GRAPH_SHA = "1dc6db11389bb6f322b0f05446f142d9fdd072d873019aa507803c3f0cd1c7cc"
SESSION_SHA = "59919054ae9080c63f50263a931b17a6e21486359a21c8c1d086a15955f590e2"
RECEIPT_SHA = "60bab65ad24bd2d0942fb70bd1f09b4c3c912ff8b9f1fe6855a6b3265281c748"
CAPTURE_SHA = "3b83ec5801ca58e0da0f2392a2fe27ebf98ec37dd6592e36593a6ce5b5a8da74"
ORIGINAL_FORMAT_REFUSAL = (
    "qualified native 11-event, 6-track 1407-frame geometry required"
)
AUDIT_NAME = "verification-correction-pristine-rational-rate-v1.json"


def demand(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError("immutable #473 M4 correction refused: " + reason)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def correct_geometry(geometry: Any) -> None:
    """Exact closed-native geometry; never accept a string or approximations."""
    demand(isinstance(geometry, dict), "native geometry is not an object")
    rate = geometry.get("rate")
    demand(
        isinstance(rate, dict)
        and set(rate) == {"numerator", "denominator"}
        and type(rate["numerator"]) is int
        and type(rate["denominator"]) is int
        and rate == {"numerator": 24000, "denominator": 1001},
        "native rate is not the exact 24000/1001 rational",
    )
    demand(
        type(geometry.get("extentFrames")) is int and geometry["extentFrames"] == 1407,
        "actual native timeline extent differs",
    )
    for name, expected in (("items", 11), ("tracks", 6)):
        rows = geometry.get(name)
        demand(
            isinstance(rows, list) and len(rows) == expected,
            f"actual native {name} count differs",
        )


def _one_time_audit(path: Path, evidence: dict[str, Any], canonical: Any) -> None:
    payload = canonical(evidence)
    if path.exists() or path.is_symlink():
        demand(
            path.is_file() and not path.is_symlink() and path.read_bytes() == payload,
            "previous audit differs; refusing replacement",
        )
        return
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o400,
    )
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(path, 0o400)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def run(*, apply: bool) -> None:
    demand(Path.cwd().resolve() == PINNED.resolve(), "not original pinned checkout")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()
    demand(head == FROZEN_COMMIT, "original Git commit differs")
    from vera_timeline_agent import qualification_output_native_v2 as native
    from vera_timeline_agent import qualification_output_package_v2 as package
    from vera_timeline_agent import resolve_test_queue as queue
    from vera_timeline_agent import resolve_test_queue_m4 as m4

    demand(
        package._sha(package._admission_code_source_graph_raw()) == GRAPH_SHA,
        "original host source graph no longer current",
    )
    store = queue.Store(RUN / "queue")
    directory = m4._jobdir(store, JOB)
    plan = m4._load_plan(store, JOB)
    receipt_path = directory / "receipt-pristine.json"
    with store.connect() as db:
        job = db.execute(
            "SELECT state,reason,plan_sha,deadline_at,started_at "
            "FROM reverse_jobs WHERE id=?",
            (JOB,),
        ).fetchone()
        rows = list(
            db.execute(
                "SELECT * FROM reverse_stages WHERE job_id=? ORDER BY ordinal", (JOB,)
            )
        )
    demand(job is not None and job["state"] == "unknown", "not original unknown job")
    demand(
        time.time() < job["deadline_at"]
        and job["started_at"] is not None
        and (queue.now_utc() - queue.dt(job["started_at"])).total_seconds()
        < plan["maxElapsedSeconds"],
        "original bounded M4 campaign has expired",
    )
    demand(
        job["reason"] == "unverified_stage_do_not_replay",
        "another refusal reason is present",
    )
    demand(len(rows) == 4, "four original M4 stages required")
    stage = rows[0]
    demand(
        stage["state"] == "unknown"
        and stage["name"] == "pristine"
        and stage["ordinal"] == 0
        and stage["receipt_sha"] == RECEIPT_SHA
        and stage["receipt_path"] == str(receipt_path)
        and stage["intent_at"] is not None
        and stage["verified_at"] is None
        and all(
            row["ordinal"] == i
            and row["name"] == m4.STAGES[i]
            and row["state"] == "pending"
            and row["intent_at"] is None
            and row["receipt_sha"] is None
            for i, row in enumerate(rows[1:], 1)
        ),
        "other one-use stage or M4 verdict has advanced",
    )
    raw = m4._read_pinned(
        {"path": str(receipt_path), "sha256": RECEIPT_SHA},
        limit=m4.MAX_RECEIPT_BYTES,
    )
    receipt = m4._parse_receipt(raw, "pristine", stage["operation_id"])
    demand(
        receipt["session"] == plan["baselineSession"]
        and receipt["session"]["sha256"] == SESSION_SHA
        and receipt["capture"]["sha256"] == CAPTURE_SHA
        and receipt["session"]["path"] == str(RUN / "run/pristine/session.json"),
        "original frozen session/native receipt differs",
    )
    try:
        # This authenticates the entire source-sealed output session,
        # one-use native result lineage, time ordering, and PCM comparison,
        # then *must* fail at the original M4 format bug, and nowhere else.
        m4._verified_output(
            receipt,
            "pristine",
            plan["initialTarget"],
            plan["caseId"],
            stage["intent_at"],
        )
    except queue.QueueError as error:
        demand(
            str(error) == ORIGINAL_FORMAT_REFUSAL,
            "original verifier failed for another reason: " + str(error),
        )
    else:
        raise ValueError("original verifier unexpectedly accepted the receipt")
    native_result = native.verify_native_result(
        Path(receipt["capture"]["path"]), CAPTURE_SHA
    )
    demand(
        native_result["status"] == "complete"
        and native_result["action"] == "capture_post"
        and native_result["context"]["target"] == plan["initialTarget"],
        "original native identity/terminal result differs",
    )
    correct_geometry(native_result["nativeGeometry"])
    evidence = {
        "schema": "vera.issue473-original-pristine-rational-reverification/v1",
        "jobId": JOB,
        "stage": "pristine",
        "originalVerifierCommit": FROZEN_COMMIT,
        "sourceGraphSha256": GRAPH_SHA,
        "receiptSha256": RECEIPT_SHA,
        "nativeCaptureSha256": CAPTURE_SHA,
        "originalFailure": ORIGINAL_FORMAT_REFUSAL,
        "nativeGeometrySha256": digest(
            queue.canonical(native_result["nativeGeometry"])
        ),
        "correctedRule": "exact_native_rational_24000_1001_no_coercion",
        "reexecutedNativeOperations": False,
    }
    print(json.dumps({"state": "read_only_reverified", **evidence}, sort_keys=True))
    if not apply:
        return
    # No native effects. Hold the SQLite writer lock during final eligibility,
    # immutable audit publication and one-way correction of this pinned row.
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        current = db.execute(
            "SELECT state,reason,plan_sha,deadline_at FROM reverse_jobs WHERE id=?",
            (JOB,),
        ).fetchone()
        saved = db.execute(
            "SELECT * FROM reverse_stages WHERE job_id=? AND ordinal=0", (JOB,)
        ).fetchone()
        later = db.execute(
            "SELECT ordinal,state,intent_at,receipt_sha FROM reverse_stages "
            "WHERE job_id=? AND ordinal>0 ORDER BY ordinal",
            (JOB,),
        ).fetchall()
        demand(
            current is not None
            and current["state"] == "unknown"
            and current["reason"] == "unverified_stage_do_not_replay"
            and current["plan_sha"] == job["plan_sha"]
            and time.time() < current["deadline_at"]
            and saved is not None
            and saved["state"] == "unknown"
            and saved["receipt_sha"] == RECEIPT_SHA
            and saved["receipt_path"] == str(receipt_path)
            and saved["intent_at"] == stage["intent_at"]
            and all(
                row["ordinal"] == i
                and row["state"] == "pending"
                and row["intent_at"] is None
                and row["receipt_sha"] is None
                for i, row in enumerate(later, 1)
            ),
            "queue changed since original read-only attestation",
        )
        demand(
            digest(receipt_path.read_bytes()) == RECEIPT_SHA,
            "pinned receipt changed during verification",
        )
        audit = directory / AUDIT_NAME
        _one_time_audit(audit, evidence, queue.canonical)
        instant = queue.iso(queue.now_utc())
        updated = db.execute(
            "UPDATE reverse_stages SET state='verified',verified_at=? "
            "WHERE job_id=? AND ordinal=0 AND state='unknown' AND receipt_sha=?",
            (instant, JOB, RECEIPT_SHA),
        )
        demand(updated.rowcount == 1, "one-use stage correction was not exclusive")
        updated = db.execute(
            "UPDATE reverse_jobs SET state='queued',reason=?,updated_at=?,"
            "ended_at=NULL WHERE id=? AND state='unknown'",
            ("read_only_rational_rate_correction", instant, JOB),
        )
        demand(updated.rowcount == 1, "one-use job correction was not exclusive")
        m4._event(
            db,
            JOB,
            "read_only_verifier_correction",
            AUDIT_NAME + ":same_original_receipt_no_native_replay",
        )
    report = m4.publish(store, JOB)
    print(
        json.dumps(
            {
                "state": report["state"],
                "verifiedStages": [
                    row["name"]
                    for row in report["stages"]
                    if row["state"] == "verified"
                ],
                "audit": str(directory / AUDIT_NAME),
                "remainingStage": "edited",
            },
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", default=False)
    args = parser.parse_args()
    run(apply=args.apply)


if __name__ == "__main__":
    main()
