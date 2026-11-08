"""Single-start M4 preparation and verified pristine stage, with strict gates.

Native execution is disabled unless the exact reviewed #472 correction is
merged into this checkout.  This runner does not manufacture a native roll
edit, infer human approval, or pretend M4 finished when the trusted editing
route is unavailable. All native operations go through the v2 host carrier.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from . import resolve_test_bench_carrier as carrier
from . import resolve_test_bench_edit_probe as edit_probe
from . import resolve_test_bench_output as output
from . import resolve_test_queue as queue
from . import resolve_test_queue_m4 as m4
from . import resolve_test_queue_m4_provision as provision

SCHEMA = "vera.test-bench-one-start/v1"
_CASE_312_PREPARATION = "issue312-package-current-S-approved-v2"
FIELDS = frozenset(
    {
        "schema",
        "root",
        "queueRoot",
        "name",
        "caseId",
        "packageRoot",
        "profile",
        "maxElapsedSeconds",
        "maxDiskBytes",
        "consentReference",
        "consentInstruction",
        "merged472Commit",
    }
)


def _absolute(value: Any, name: str) -> Path:
    if not isinstance(value, str):
        raise queue.QueueError(f"{name} must be an absolute path")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise queue.QueueError(f"{name} must be an absolute safe path")
    return path


def validate_config(value: Any) -> dict[str, Any]:
    from .qualification_output_native_v2 import MATRIX_PROFILE

    if not isinstance(value, dict) or set(value) != FIELDS:
        raise queue.QueueError("closed one-start Test Bench configuration required")
    if (
        value["schema"] != SCHEMA
        or value["profile"] != MATRIX_PROFILE
        or value["caseId"] != "synthetic-312"
    ):
        raise queue.QueueError("only the approved #312 studio-matrix fixture")
    for key in ("root", "queueRoot", "packageRoot"):
        _absolute(value[key], key)
    if len({value[k] for k in ("root", "queueRoot", "packageRoot")}) != 3:
        raise queue.QueueError("separate private run, queue and package roots required")
    queue.simple_id(value["name"], "name")
    queue.simple_id(value["caseId"], "caseId")
    queue.limited_int(value["maxElapsedSeconds"], "maxElapsedSeconds", 60, 14400)
    queue.limited_int(value["maxDiskBytes"], "maxDiskBytes", 1048576, 4 * 1024**3)
    for key in ("consentReference", "consentInstruction"):
        if not isinstance(value[key], str) or not 0 < len(value[key].strip()) <= 4096:
            raise queue.QueueError(f"actual bounded {key} required")
    if not isinstance(value["merged472Commit"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", value["merged472Commit"]
    ):
        raise queue.QueueError("exact merged #472 correction commit SHA required")
    return dict(value)


def _merged_472(commit: str) -> None:
    """No real Resolve acceptance while #472 is being repaired."""
    repository = Path(__file__).resolve().parents[2]

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=repository,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    if (
        git("merge-base", "--is-ancestor", commit, "HEAD").returncode != 0
        or git("merge-base", "--is-ancestor", commit, "origin/main").returncode != 0
        or git("merge-base", "--is-ancestor", "origin/main", "HEAD").returncode != 0
    ):
        raise queue.QueueError(
            "#472 correction not merged into origin/main and current checkout"
        )
    # A locally modified verifier would defeat the merge provenance check;
    # that source belongs to #472 and must be exactly the fetched main version.
    verifier_path = "python/vera_timeline_agent/qualification_output_native_v2.py"
    if git("diff", "--quiet", "origin/main", "--", verifier_path).returncode != 0:
        raise queue.QueueError("#472 verifier has unmerged local modifications")
    changes = git("diff-tree", "--no-commit-id", "--name-only", "-r", commit)
    if changes.returncode != 0 or verifier_path not in changes.stdout.splitlines():
        raise queue.QueueError("#472 source-range verifier commit not authenticated")


def _find_job(store: queue.Store, plan_sha: str) -> str | None:
    """Recover an enqueue-to-pointer crash using the exact existing DB row."""
    with store.connect() as db:
        jobs = db.execute(
            "SELECT id FROM reverse_jobs WHERE plan_sha=?", (plan_sha,)
        ).fetchall()
    if len(jobs) > 1:
        raise queue.QueueError("ambiguous original M4 enrollment")
    return str(jobs[0]["id"]) if jobs else None


def _matrix_preparation_paths(package_root: Path, *, case_id: str) -> dict[str, Path]:
    """Prove the EXACT #312 published preparation receipts before any effect.

    Never select an arbitrary filesystem directory, substitute an embedded
    receipt without its real published media, or guess a creative revision.
    This is the already approved fixed synthetic source for #312 only.
    """
    from . import v2_package
    from .qualification_output_package_v2 import MATRIX_PREPARATION_ROOT

    if case_id != "synthetic-312":
        raise queue.QueueError("unsupported unattended studio-matrix case")
    verified = v2_package.verify_v2_package(package_root)
    build = package_root / "Builds" / verified.build_id
    manifest = json.loads((build / v2_package.MANIFEST_FILENAME).read_bytes())
    bindings = manifest.get("preparationBindings")
    if (
        not isinstance(bindings, list)
        or len(bindings) != 6
        or len(manifest.get("events", [])) != 11
        or manifest.get("timeline", {}).get("durationFrames") != 1407
    ):
        raise queue.QueueError("approved 11-event #312 matrix package required")
    published = MATRIX_PREPARATION_ROOT / _CASE_312_PREPARATION / "published"
    prepared: dict[str, Path] = {}
    for binding in bindings:
        key = binding.get("requirementKey") if isinstance(binding, dict) else None
        if (
            not isinstance(key, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", key) is None
            or key in prepared
        ):
            raise queue.QueueError("malformed/duplicate approved preparation key")
        embedded = (
            build
            / "Preparation"
            / "receipts"
            / hashlib.sha256(key.encode()).hexdigest()
            / "receipt.json"
        )
        receipt = published / key[7:] / "receipt.json"
        for path in (embedded, receipt):
            v2_package._require_path_components_no_symlink(path, "matrix receipt")
        if (
            not embedded.is_file()
            or not receipt.is_file()
            or embedded.read_bytes() != receipt.read_bytes()
        ):
            raise queue.QueueError(
                "current published source receipt differs from reviewed package"
            )
        prepared[key] = receipt
    return prepared


def _preflight_before_native(value: dict[str, Any]) -> None:
    """Refuse inadequate disk or wrong matrix fixture before project creation."""

    root = _absolute(value["root"], "root")
    carrier._private(root, create=True)
    if shutil.disk_usage(root).free < value["maxDiskBytes"]:
        raise queue.QueueError(
            "Test Bench actual free disk below the reserved native budget"
        )
    # Authenticates each actual published source receipt and all 11 events
    # before provision creates even a disposable project in Resolve.
    _matrix_preparation_paths(
        _absolute(value["packageRoot"], "packageRoot"),
        case_id=value["caseId"],
    )


def _one_start_setup(value: dict[str, Any]) -> tuple[queue.Store, str, dict[str, str]]:
    from .qualification_output_controller_v2 import prepare_output_session

    root = _absolute(value["root"], "root")
    carrier._private(root, create=True)
    store = queue.Store(_absolute(value["queueRoot"], "queueRoot"))
    provision_root = root / "provision"
    provision.provision(provision_root)
    targets = provision.completed(provision_root)
    provision.select(provision_root, "initial")
    pristine_root = root / "pristine"
    baseline = pristine_root / "session.json"
    if not baseline.exists():
        prepare_output_session(
            pristine_root,
            profile=value["profile"],
            package_root=_absolute(value["packageRoot"], "packageRoot"),
            preparation_paths=_matrix_preparation_paths(
                _absolute(value["packageRoot"], "packageRoot"),
                case_id=value["caseId"],
            ),
            target=targets["initial"],
            case_id=value["caseId"],
        )
    pinned = output._pin(baseline)
    # Load/recompute host provenance before accepting an earlier session.
    controller = output._session(baseline, pinned["sha256"])
    if (
        controller.context.get("target") != targets["initial"]
        or controller.context.get("caseId") != value["caseId"]
        or controller.context.get("phase") != "pristine"
    ):
        raise queue.QueueError("baseline session is not for this Test Bench target")
    plan_path = root / "m4-plan.json"
    if not plan_path.exists():
        plan = m4.validate_plan(
            {
                "schema": m4.SCHEMA,
                "name": value["name"],
                "caseId": value["caseId"],
                "baselineSession": pinned,
                "initialTarget": targets["initial"],
                "freshTarget": targets["fresh"],
                "maxElapsedSeconds": value["maxElapsedSeconds"],
                "maxDiskBytes": value["maxDiskBytes"],
            }
        )
        carrier._once(plan_path, queue.canonical(plan))
    plan = m4.validate_plan(json.loads(carrier._read(plan_path)))
    if (
        plan["baselineSession"] != pinned
        or plan["initialTarget"] != targets["initial"]
        or plan["freshTarget"] != targets["fresh"]
        or plan["caseId"] != value["caseId"]
    ):
        raise queue.QueueError("Test Bench plan changed after preparation")
    plan_sha = hashlib.sha256(carrier._read(plan_path)).hexdigest()
    job_id = _find_job(store, plan_sha)
    if job_id is None:
        job_id = m4.enqueue(store, plan_path)
    return store, job_id, pinned


def _worker_once(store: queue.Store) -> bool:
    lock_path = store.root / "worker.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return m4.worker_tick(store)


def _submit_original(
    store: queue.Store,
    job_id: str,
    stage: str,
    result: dict[str, Any],
) -> None:
    report = m4.publish(store, job_id)
    expected = next((item for item in report["stages"] if item["name"] == stage), None)
    if expected is None or expected["state"] not in {"awaiting_operator", "verified"}:
        raise queue.QueueError("M4 stage not enrolled before native host result")
    receipt = {
        "schema": m4.RECEIPT_SCHEMA,
        "stage": stage,
        "operationId": expected["operation_id"],
        "session": result["session"],
        "capture": result["capture"],
    }
    path = store.root / job_id / f"receipt-{stage}.json"
    raw = queue.canonical(receipt)
    if not path.exists():
        carrier._once(path, raw)
    elif carrier._read(path, m4.MAX_RECEIPT_BYTES) != raw:
        raise queue.QueueError("immutable enrolled M4 receipt differs")
    if expected["state"] == "awaiting_operator":
        m4.submit(store, job_id)


def _blocked_after_pristine(
    store: queue.Store, job_id: str, root: Path, report: dict[str, Any]
) -> dict[str, Any]:
    """Read-only SDK capability inspection; never claims the edit is qualified."""
    receipt = m4._stage_receipt(store, job_id, 0)
    inspection = edit_probe.inspect_pristine(
        root / "edit-capability",
        session_path=Path(receipt["session"]["path"]),
        session_sha256=receipt["session"]["sha256"],
        capture_path=Path(receipt["capture"]["path"]),
        capture_sha256=receipt["capture"]["sha256"],
    )
    return {
        "state": "blocked_unattended_native_roll_edit_not_proven",
        "jobId": job_id,
        "verifiedStages": [
            row["name"] for row in report["stages"] if row["state"] == "verified"
        ],
        "next": "edited",
        "editCapability": {
            "resolveVersion": inspection["resolveVersion"],
            "supportsDocumentedOffsetMethods": inspection[
                "supportsDocumentedOffsetMethods"
            ],
            "leftItemUid": inspection["leftItemUid"],
            "rightItemUid": inspection["rightItemUid"],
            "unqualified": True,
        },
    }


def start(config: dict[str, Any]) -> dict[str, Any]:
    value = validate_config(config)
    _merged_472(value["merged472Commit"])
    root = _absolute(value["root"], "root")
    carrier._private(root, create=True)
    # One unattended start owns this run's preparation and queue transition.
    # A restart may inspect and resume after the original controller exits,
    # but two starts cannot race to create native or queue intents.
    with carrier._lock(root):
        _preflight_before_native(value)
        return _start_locked(value)


def _start_locked(value: dict[str, Any]) -> dict[str, Any]:
    store, job_id, pristine = _one_start_setup(value)
    report = m4.publish(store, job_id)
    pristine_already_verified = any(
        row["name"] == "pristine" and row["state"] == "verified"
        for row in report["stages"]
    )
    # No reviewed same-UID roll-edit carrier exists yet. Do not claim the next
    # one-use queue stage merely because the caller retried this launcher.
    if pristine_already_verified and report["state"] == "queued":
        return _blocked_after_pristine(
            store, job_id, _absolute(value["root"], "root"), report
        )
    if report["state"] == "queued":
        _worker_once(store)
        report = m4.publish(store, job_id)
    if report["state"] == "verifying":
        m4.reconcile(store, job_id)
        report = m4.publish(store, job_id)
    if report["state"] in {"unknown", "blocked", "canceled", "completed_verified"}:
        return {"state": report["state"], "jobId": job_id}
    if report["stage"] == "pristine":
        baseline = Path(pristine["path"])
        controller = output._session(baseline, pristine["sha256"])
        result = output.drive(
            _absolute(value["root"], "root") / "pristine-actions",
            session_path=baseline,
            session_sha256=pristine["sha256"],
            installed=controller.release_root,
            consent_reference=value["consentReference"],
            consent_instruction=value["consentInstruction"],
            max_seconds=value["maxElapsedSeconds"],
            minimum_free_bytes=value["maxDiskBytes"],
        )
        _submit_original(store, job_id, "pristine", result)
        report = m4.publish(store, job_id)
    # SDK 21.1.2 added offset setters, but empirical reports show destructive
    # behavior with successful return values. Capability presence is NOT
    # permission to mutate the only actual pristine M4 target.
    if report["state"] == "queued":
        return _blocked_after_pristine(
            store, job_id, _absolute(value["root"], "root"), report
        )
    return {"state": report["state"], "jobId": job_id}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "inspect"))
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = validate_config(json.loads(carrier._read(args.config, 16 * 1024)))
        if args.action == "start":
            outcome = start(config)
        else:
            store = queue.Store(_absolute(config["queueRoot"], "queueRoot"))
            plan = _absolute(config["root"], "root") / "m4-plan.json"
            job_id = _find_job(store, hashlib.sha256(carrier._read(plan)).hexdigest())
            outcome = (
                {"state": "not_enrolled"}
                if job_id is None
                else m4.publish(store, job_id)
            )
        print(json.dumps(outcome, sort_keys=True))
        return 0 if outcome["state"] == "completed_verified" else 2
    except (OSError, ValueError, TypeError, RuntimeError, KeyError) as error:
        print(json.dumps({"state": "unknown", "verified": False, "detail": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
