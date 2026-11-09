"""One *newly authorized*, source-frozen start for the original #473 M4 queue.

Not a recovery/retry command: a spent full-loop intent allows read-only audit
only. The original four operation IDs, queue, signed receipts and official SDK
carrier remain authoritative. Never use this on a previous M4 campaign.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from . import resolve_test_bench_carrier as carrier
from . import resolve_test_bench_edited_stage as edited
from . import resolve_test_bench_gui_stage as gui
from . import resolve_test_bench_m4_runner as runner
from . import resolve_test_bench_page_stage as page
from . import resolve_test_bench_playhead_stage as playhead
from . import resolve_test_bench_revision_stage as revision
from . import resolve_test_queue as queue
from . import resolve_test_queue_m4 as m4
from . import resolve_test_queue_m4_provision as provision
from .resolve_gui_roll import ROLL_SCRIPT_SHA256
from .resolve_native_owner import _local_resolve_connection, native_owner
from .roundtrip_v2_records import proof_source_hashes_v2

AUTHORITY_SCHEMA = "vera.test-bench-473-case-specific-authority/v1"
INTENT_SCHEMA = "vera.test-bench-473-complete-loop/v1"
_HEX = re.compile(r"[0-9a-f]{40}\Z")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise queue.QueueError("frozen original M4 one-start refused: " + message)


def _source_hash() -> str:
    return hashlib.sha256(queue.canonical(proof_source_hashes_v2())).hexdigest()


def _frozen_source(commit: str) -> str:
    """Verify the exact approved Phase-4 HEAD AND every source-graph input.

    Documentation may differ on the target Mac, but no tracked or untracked
    source input may be changed. The signed output admission checks its own
    Python/compiler/lock graph again at each later native action.
    """
    _require(
        isinstance(commit, str) and _HEX.fullmatch(commit) is not None,
        "exact Phase-4 commit required",
    )
    repo = Path(__file__).resolve().parents[2]

    def git(*args: str) -> str:
        done = subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        _require(done.returncode == 0, "git source pin unavailable")
        return done.stdout.strip()

    _require(git("rev-parse", "HEAD") == commit, "frozen Phase-4 commit changed")
    _require(
        git("status", "--porcelain", "--untracked-files=all") == "",
        "dirty checkout may alter sealed source inputs",
    )
    return _source_hash()


def _authority(
    raw: bytes, value: dict[str, Any], commit: str, graph: str
) -> dict[str, Any]:
    """Require a *separate* actual Producer instruction bound to THIS run.

    This is a conductor-supplied attribution, not a cryptographic signature of
    a chat transcript. The trusted caller must authenticate that authorization
    outside the program; the previous #491 exception and old M4 are invalid.
    """
    try:
        authority = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise queue.QueueError("case-specific authority is not JSON") from error
    fields = {
        "schema",
        "caseId",
        "configSha256",
        "frozenCommit",
        "sourceGraphSha256",
        "approvalReference",
        "approvalInstruction",
        "issuedAt",
        "expiresAt",
        "initialTarget",
        "freshTarget",
        "operation",
        "fromFrame",
        "toFrame",
        "scriptSha256",
    }
    _require(
        isinstance(authority, dict)
        and set(authority) == fields
        and queue.canonical(authority) == raw,
        "closed, canonical, exact run authority required",
    )
    _require(
        authority["schema"] == AUTHORITY_SCHEMA
        and authority["caseId"] == value["caseId"] == "synthetic-312"
        and authority["configSha256"]
        == hashlib.sha256(queue.canonical(value)).hexdigest()
        and authority["frozenCommit"] == commit
        and authority["sourceGraphSha256"] == graph
        and authority["approvalReference"] == value["consentReference"]
        and authority["approvalInstruction"] == value["consentInstruction"]
        and authority["operation"] == "M4.edited.one-use-gui-roll"
        and type(authority["fromFrame"]) is int
        and type(authority["toFrame"]) is int
        and authority["fromFrame"] == 327
        and authority["toFrame"] == 351
        and authority["scriptSha256"] == ROLL_SCRIPT_SHA256,
        "new precise Producer instruction, source hash or fixed GUI action differs",
    )
    # This is an operator-authenticated attribution, not a cryptographic
    # signature. Its freshness is still independently bounded: stale case
    # consent and the earlier generic #491 exception cannot start a new run.
    _require(
        type(authority["issuedAt"]) is str
        and type(authority["expiresAt"]) is str
        and type(authority["approvalReference"]) is str
        and bool(authority["approvalReference"].strip())
        and "491" not in authority["approvalReference"],
        "fresh case-specific authority timestamp/reference required; #491 is obsolete",
    )
    try:
        issued = queue.dt(authority["issuedAt"])
        expires = queue.dt(authority["expiresAt"])
    except (ValueError, TypeError, OverflowError) as error:
        raise queue.QueueError("invalid case-specific authorization time") from error
    now = datetime.now(UTC)
    _require(
        issued <= now < expires
        and now - issued <= timedelta(minutes=30)
        and timedelta(0) < expires - issued <= timedelta(minutes=30),
        "case-specific authorization expired, future-dated or not fresh",
    )
    targets = provision.completed(Path(value["root"]) / "provision")
    _require(
        authority["initialTarget"] == targets["initial"]
        and authority["freshTarget"] == targets["fresh"]
        and targets["initial"] != targets["fresh"],
        "newly provisioned native targets differ from fresh authorization",
    )
    return dict(authority)


def _advance(store: queue.Store, job_id: str, stage: str) -> None:
    report = m4.publish(store, job_id)
    _require(
        report["state"] == "queued"
        and next(row for row in report["stages"] if row["name"] == stage)["state"]
        == "pending",
        "prior original M4 stage was not verified",
    )
    _require(
        runner._worker_once(store) is True,
        "original M4 worker did not enroll next single stage",
    )
    next_report = m4.publish(store, job_id)
    _require(
        next_report["state"] == "awaiting_operator" and next_report["stage"] == stage,
        "original M4 stage/operation changed during worker claim",
    )


def start(
    config_path: Path, authority_path: Path, *, frozen_commit: str
) -> dict[str, Any]:
    """One foreground call; no repeat invocation may ever dispatch an effect."""
    graph = _frozen_source(frozen_commit)
    config_raw = carrier._read(config_path, 16384)
    value = runner.validate_config(json.loads(config_raw))
    _require(config_raw == queue.canonical(value), "noncanonical immutable new config")
    authorization_raw = carrier._read(authority_path, 32768)
    authority = _authority(authorization_raw, value, frozen_commit, graph)
    root = runner._absolute(value["root"], "root")
    carrier._private(root)
    _require(
        (root / "config.json").is_file()
        and carrier._read(root / "config.json", 16384) == config_raw
        and all(
            not (root / name).exists() and not (root / name).is_symlink()
            for name in (
                "m4-plan.json",
                "source-preflight",
                "pristine",
                "pristine-stage",
                "edit-capability",
                "f1-gui-edit",
                "edited",
                "edited-stage",
                "revision",
                "rebuild",
                "rebuild-stage",
            )
        ),
        "new one-start root already used or lacks pinned fresh config",
    )
    # Before ANY native/preflight action; a loss here is UNKNOWN, never a new
    # attempt even if no native operation is visible. Phase 5 must use a new
    # sacrificial campaign after source freeze, not the historical pristine.
    intent_path = root / "complete-loop-intent.json"
    _require(
        not intent_path.exists() and not intent_path.is_symlink(),
        "one-start already spent; read-only inspect, never replay",
    )
    try:
        carrier._once(
            intent_path,
            queue.canonical(
                {
                    "schema": INTENT_SCHEMA,
                    "config": {
                        "path": str(config_path),
                        "sha256": hashlib.sha256(config_raw).hexdigest(),
                    },
                    "authority": {
                        "path": str(authority_path),
                        "sha256": hashlib.sha256(authorization_raw).hexdigest(),
                    },
                    "frozenCommit": frozen_commit,
                    "sourceGraphSha256": graph,
                }
            ),
        )
    except FileExistsError as error:
        raise queue.QueueError("one-start already spent; never replay") from error
    result = runner.start(value)
    job_id = result.get("jobId")
    _require(
        isinstance(job_id, str)
        and result.get("state") == "blocked_unattended_native_roll_edit_not_proven",
        "new pristine host not independently verified; no downstream stages",
    )
    assert isinstance(job_id, str)
    store = queue.Store(runner._absolute(value["queueRoot"], "queueRoot"))
    _advance(store, job_id, "edited")
    # The shared native owner protects the sole GUI action. Release BEFORE
    # carrier.start, which independently preflights and acquires that owner.
    with native_owner(output_lane=True):
        resolve = _local_resolve_connection()
        _require(resolve is not None, "official Studio SDK unavailable")
        page.open_owned_edit_page(
            store, job_id, resolve, case_root=root, authority=authority
        )
        playhead.position_owned_327(store, job_id, resolve)
        attempted = gui.dispatch_owned_f1_once(store, job_id, resolve)
        _require(
            attempted.state == "unknown"
            and attempted.native_verified is False
            and attempted.receipt_issued is False,
            "GUI OS result cannot certify edited M4",
        )
    edited.start(store, job_id, value)
    _advance(store, job_id, "revision")
    revision.revision(store, job_id, value)
    # The M4 queue's fresh-stage worker requires its newly provisioned empty
    # project ALREADY selected. The pristine/edited host leaves the initial
    # project selected. Use only the original provisioner to select the exact
    # independent UID; never invent or create a replacement project.
    provision.select(root / "provision", "fresh")
    _advance(store, job_id, "rebuild")
    revision.rebuild(store, job_id, value)
    report = m4.publish(store, job_id)
    _require(
        report["state"] == "completed_verified"
        and report["readyFor312Phase2"] is True
        and [row["state"] for row in report["stages"]] == ["verified"] * 4,
        "four original signed M4 receipts incomplete",
    )
    return {
        "state": "original_M4_four_stages_verified",
        "jobId": job_id,
        "frozenCommit": frozen_commit,
        "sourceGraphSha256": graph,
    }


class _ReadOnlyStore(queue.Store):
    """Inspect an existing SQLite queue; never initialize files or mutate WAL."""

    def __init__(self, root: Path) -> None:
        self.root = root
        _require((root / "queue.sqlite3").is_file(), "original queue absent")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        database = sqlite3.connect(
            f"file:{self.root / 'queue.sqlite3'}?mode=ro",
            uri=True,
            timeout=10,
            isolation_level=None,
        )
        database.row_factory = sqlite3.Row
        try:
            yield database
        finally:
            database.close()


def inspect(config_path: Path) -> dict[str, Any]:
    """Read-only original queue inspection, without resume, enqueue or replay."""
    value = runner.validate_config(json.loads(carrier._read(config_path, 16384)))
    root = runner._absolute(value["root"], "root")
    intent = root / "complete-loop-intent.json"
    if not intent.is_file():
        return {"state": "not_started", "verified": False}
    recorded = json.loads(carrier._read(intent, 16384))
    _require(
        isinstance(recorded, dict)
        and set(recorded)
        == {"schema", "config", "authority", "frozenCommit", "sourceGraphSha256"}
        and carrier._read(intent, 16384) == queue.canonical(recorded),
        "one-start intent is not canonical or has changed",
    )
    _require(
        recorded.get("schema") == INTENT_SCHEMA
        and recorded.get("config")
        == {
            "path": str(config_path),
            "sha256": hashlib.sha256(queue.canonical(value)).hexdigest(),
        },
        "one-start audit source or intent changed",
    )
    plan_path = root / "m4-plan.json"
    if not plan_path.is_file():
        return {"state": "unknown_after_intent", "verified": False}
    store = _ReadOnlyStore(runner._absolute(value["queueRoot"], "queueRoot"))
    job_id = runner._find_job(
        store, hashlib.sha256(carrier._read(plan_path)).hexdigest()
    )
    if job_id is None:
        return {"state": "unknown_before_enrollment", "verified": False}
    m4._load_plan(store, job_id)
    with store.connect() as db:
        parent = db.execute(
            "SELECT state FROM reverse_jobs WHERE id=?", (job_id,)
        ).fetchone()
        stages = db.execute(
            "SELECT name,state,operation_id,receipt_sha FROM reverse_stages "
            "WHERE job_id=? ORDER BY ordinal",
            (job_id,),
        ).fetchall()
    _require(
        parent is not None and len(stages) == 4, "original M4 queue state incomplete"
    )
    verified = parent["state"] == "completed_verified" and all(
        row["state"] == "verified" and row["receipt_sha"] is not None for row in stages
    )
    if verified:
        for ordinal in range(4):
            m4._stage_receipt(store, job_id, ordinal)
    return {
        "state": parent["state"],
        "verified": verified,
        "jobId": job_id,
        "stages": [
            {
                "name": row["name"],
                "state": row["state"],
                "operationId": row["operation_id"],
            }
            for row in stages
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "inspect"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--authority", type=Path)
    parser.add_argument("--frozen-commit")
    args = parser.parse_args()
    try:
        if args.action == "start":
            _require(
                args.authority is not None and args.frozen_commit is not None,
                "fresh separate Producer authority and frozen SHA required",
            )
            assert args.authority is not None and args.frozen_commit is not None
            result = start(
                args.config, args.authority, frozen_commit=args.frozen_commit
            )
        else:
            result = inspect(args.config)
        print(json.dumps(result, sort_keys=True))
        return (
            0
            if result.get("verified") is True
            or result.get("state") == "original_M4_four_stages_verified"
            else 2
        )
    except (OSError, ValueError, TypeError, RuntimeError, KeyError) as error:
        print(json.dumps({"state": "unknown", "verified": False, "detail": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
