"""Subprocess coverage for one-use native queue recovery without Resolve."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from vera_timeline_agent import resolve_test_queue as queue

BUILD_ID = "12345678-1234-1234-1234-123456789abc"
PROJECT = f"VERA Delivery {BUILD_ID} abcdef012345"
INVOCATION_ID = "abcdef0123456789abcdef0123456789"

_CHILD = r"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from vera_timeline_agent import resolve_test_queue as q
from vera_timeline_agent import workflow_v2_parent as parent
from vera_timeline_agent import resolve_test_queue_native as native

root, plan_path, request_path, count_path, release_gate = map(Path, sys.argv[2:7])
job_id = sys.argv[7]
request = json.loads(request_path.read_bytes())
expected_request_sha = hashlib.sha256(request_path.read_bytes()).hexdigest()
evidence = Path(request["evidenceDir"])
invocation = "abcdef0123456789abcdef0123456789"
native.preflight = lambda _plan: request
q.preflight_independent_disposable = lambda _target: None
held_lock = None

def immutable(path: Path, value: dict[str, object]) -> None:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o400)

def fake_start(
    path: Path,
    expected: str,
    _python: Path,
    *,
    independent_disposable: bool = False,
) -> dict[str, object]:
    global held_lock
    assert independent_disposable is True
    with count_path.open("a", encoding="utf-8") as stream:
        stream.write("dispatch\n")
        stream.flush()
        os.fsync(stream.fileno())
    evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
    held_lock = (evidence / "parent.lock").open("a+")
    fcntl.flock(held_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    session = {
        "schemaVersion": "vera-delivery-parent/v1",
        "requestPath": str(path.absolute()),
        "requestSha256": expected,
        "startedAt": datetime.now(UTC).isoformat(),
        "monotonicStarted": time.monotonic(),
        "invocationId": invocation,
    }
    immutable(evidence / "parent.json", session)
    context = {
        "requestSha256": expected,
        "releaseSha256": request["releaseSha256"],
        "attestationSha256": request["attestationSha256"],
        "requestedProjectName": request["projectName"],
        "requestedTimelineName": request["timelineName"],
        "parentInvocationId": invocation,
    }
    immutable(evidence / f"started-{expected}.json", context)
    result = {
        "schemaVersion": "vera-injected-delivery-result/v2",
        "deliveryVersion": "2",
        "status": "verified",
        "verified": True,
        "discrepancies": [],
        "action": "build",
        "projectName": request["projectName"],
        "timelineName": request["timelineName"],
        "nativeRateQualified": True,
        "verification": {"eventCount": 1, "markerCount": 0, "mediaCount": 1},
        **context,
    }
    result_path = evidence / f"result-{expected}.json"
    immutable(result_path, result)
    immutable(
        evidence / f"hashes-{expected}.json",
        {
            "resultPath": str(result_path),
            "resultSha256": parent._digest(result_path),
            **context,
        },
    )
    immutable(
        evidence / "parent-exit.json",
        {
            "returncode": 0,
            "monotonicFinished": time.monotonic(),
            "finishedAt": datetime.now(UTC).isoformat(),
            "requestSha256": expected,
            "parentInvocationId": invocation,
        },
    )
    if not release_gate.exists():
        deadline = time.monotonic() + 10
        while not release_gate.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not release_gate.exists():
            raise TimeoutError("test did not release fake parent")
    return {"state": "live", "verified": False}

parent.start = fake_start
worked = q.worker_once(q.Store(root))
row = q.Store(root).get(job_id)
print(json.dumps({"worked": worked, "state": row["state"], "attempt": row["attempt"]}))
"""


def _write_json(path: Path, value: dict[str, Any]) -> bytes:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(payload)
    return payload


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    release = tmp_path / "release"
    installed = release / "vera-delivery-v2"
    installed.mkdir(parents=True)
    (installed / "release.json").write_text("{}", encoding="utf-8")
    package = tmp_path / "package"
    package.mkdir()
    attestation = tmp_path / "attestation.json"
    attestation.write_text("{}", encoding="utf-8")
    evidence = tmp_path / "native-evidence"
    request_path = installed / "request.json"
    request = {
        "schemaVersion": "vera-injected-delivery-request/v2",
        "releaseSha256": hashlib.sha256(
            (installed / "release.json").read_bytes()
        ).hexdigest(),
        "attestationPath": str(attestation),
        "attestationSha256": "c" * 64,
        "packageDir": str(package),
        "projectName": PROJECT,
        "timelineName": PROJECT,
        "action": "build",
        "authorizeNewNonproduction": True,
        "externalScripting": "Local",
        "evidenceDir": str(evidence),
    }
    request_bytes = _write_json(request_path, request)
    request_path.chmod(0o400)
    request_sha = hashlib.sha256(request_bytes).hexdigest()
    expected = {
        "viewSha256": "d" * 64,
        "eventsSha256": "e" * 64,
        "settingsSha256": "f" * 64,
        "mediaSha256": "0" * 64,
        "eventCount": 1,
        "markerCount": 0,
        "mediaCount": 1,
    }
    plan = {
        "schema": "vera.resolve-test-plan/v2",
        "name": "native-process-recovery",
        "fixtureId": f"synthetic-{BUILD_ID}",
        "fixtureSha256": "c" * 64,
        "targetId": f"disposable-{BUILD_ID}",
        "targetPolicy": "new_disposable_native",
        "category": "native-process-test",
        "maxElapsedSeconds": 600,
        "maxDiskBytes": 67_108_864,
        "runAt": queue.iso(queue.now_utc() - timedelta(seconds=2)),
        "deadlineAt": queue.iso(queue.now_utc() + timedelta(minutes=5)),
        "cases": [
            {
                "id": "native-build",
                "adapter": "native.v2.guarded_build",
                "iterations": 1,
                "delayMs": 0,
            }
        ],
        "native": {
            "requestPath": str(request_path),
            "requestSha256": request_sha,
            "releaseSha256": request["releaseSha256"],
            "attestationSha256": request["attestationSha256"],
            "projectName": PROJECT,
            "timelineName": PROJECT,
            "expected": expected,
        },
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    return plan_path, request_path, evidence, tmp_path / "dispatch-count"


def _child_args(
    store_root: Path,
    plan_path: Path,
    request_path: Path,
    count_path: Path,
    release_gate: Path,
    job_id: str,
) -> list[str]:
    repo_root = Path(__file__).resolve().parents[1]
    python_root = repo_root / "python"
    return [
        sys.executable,
        "-c",
        _CHILD,
        str(python_root),
        str(store_root),
        str(plan_path),
        str(request_path),
        str(count_path),
        str(release_gate),
        job_id,
    ]


def _run_worker(
    store_root: Path,
    plan_path: Path,
    request_path: Path,
    count_path: Path,
    release_gate: Path,
    job_id: str,
) -> dict[str, Any]:
    result = subprocess.run(
        _child_args(
            store_root, plan_path, request_path, count_path, release_gate, job_id
        ),
        check=False,
        capture_output=True,
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    return cast(dict[str, Any], json.loads(result.stdout.strip().splitlines()[-1]))


def _wait_for_file(path: Path, timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert path.exists(), f"child process did not create {path.name}"


@pytest.mark.slow
def test_native_intent_reconciles_authenticated_parent_after_process_exit(
    tmp_path: Path,
) -> None:
    plan_path, request_path, evidence, count_path = _fixture(tmp_path)
    store_root = tmp_path / "queue"
    store = queue.Store(store_root)
    job_id = queue.enqueue(store, plan_path)
    release_gate = tmp_path / "release-parent"
    args = _child_args(
        store_root, plan_path, request_path, count_path, release_gate, job_id
    )
    first = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).resolve().parents[1],
        text=True,
    )
    try:
        _wait_for_file(count_path)
        assert count_path.read_text(encoding="utf-8").splitlines() == ["dispatch"]

        # A second OS process cannot pass the queue-root worker lock while the
        # first process has a persisted native intent and the fake parent live.
        second = _run_worker(
            store_root, plan_path, request_path, count_path, release_gate, job_id
        )
        assert second["worked"] is False
        assert count_path.read_text(encoding="utf-8").splitlines() == ["dispatch"]
        assert store.get(job_id)["state"] == "running"
    finally:
        release_gate.touch()
    stdout, stderr = first.communicate(timeout=10)
    assert first.returncode == 0, stderr
    first_result = json.loads(stdout.strip().splitlines()[-1])
    assert first_result == {"worked": True, "state": "running", "attempt": 1}

    # The original worker process is gone. A fresh process authenticates the
    # retained status/result/hash records through the real parent.status path.
    third = _run_worker(
        store_root, plan_path, request_path, count_path, release_gate, job_id
    )
    assert third == {"worked": True, "state": "completed_verified", "attempt": 1}
    assert count_path.read_text(encoding="utf-8").splitlines() == ["dispatch"]
    with queue.Store(store_root).connect() as db:
        attempt = db.execute(
            "SELECT request_sha,intent_at,invocation_id,parent_state,native_verified "
            "FROM native_attempts WHERE job_id=?",
            (job_id,),
        ).fetchone()
    frozen_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert attempt["request_sha"] == frozen_plan["native"]["requestSha256"]
    assert attempt["intent_at"]
    assert attempt["invocation_id"] == INVOCATION_ID
    assert attempt["parent_state"] == "terminal"
    assert attempt["native_verified"] == 1
    assert (evidence / "queue-intent.json").exists()
    assert store.publish(job_id)["nativeVerified"] is True
    assert str(evidence) not in json.dumps(store.publish(job_id))
