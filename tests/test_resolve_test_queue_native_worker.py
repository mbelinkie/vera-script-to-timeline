"""Native orchestration: uncertain effects stay one-use across new workers."""

from __future__ import annotations

import json
import shutil
import threading
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import resolve_test_queue as q
from vera_timeline_agent import resolve_test_queue_native as native
from vera_timeline_agent import workflow_v2
from vera_timeline_agent import workflow_v2_parent as parent


@pytest.fixture
def native_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    evidence = tmp_path / "private-evidence"
    request = {"evidenceDir": str(evidence)}
    locator = {
        "requestPath": str(tmp_path / "private-release/request.json"),
        "requestSha256": "a" * 64,
        "releaseSha256": "b" * 64,
        "attestationSha256": "c" * 64,
        "projectName": "private-target",
        "timelineName": "private-target",
        "expected": {},
    }
    plan = {
        "schema": "vera.resolve-test-plan/v2",
        "name": "native-test",
        "fixtureId": "synthetic-test",
        "fixtureSha256": "c" * 64,
        "targetId": "disposable-test",
        "targetPolicy": "new_disposable_native",
        "category": "queue",
        "maxElapsedSeconds": 600,
        "maxDiskBytes": 1048576,
        "runAt": q.iso(q.now_utc() - timedelta(seconds=1)),
        "deadlineAt": q.iso(q.now_utc() + timedelta(minutes=10)),
        "cases": [
            {
                "id": "native",
                "adapter": "native.v2.guarded_build",
                "iterations": 1,
                "delayMs": 0,
            }
        ],
        "native": locator,
    }
    monkeypatch.setattr(
        native, "validate_native_plan", lambda source, at=None: dict(source)
    )
    monkeypatch.setattr(native, "preflight", lambda plan: request)
    # Authentication is covered separately; exercise persistence here.
    monkeypatch.setattr(
        native,
        "classify_parent_status",
        lambda response, **kwargs: SimpleNamespace(
            disposition=response["state"],
            reason="parent_" + response["state"],
            native_verified=response["state"] == "verified",
        ),
    )
    calls: list[str] = []
    response = {"state": "live"}

    def start(*args: Any) -> dict[str, Any]:
        calls.append("dispatch")
        evidence.mkdir(exist_ok=True)
        (evidence / "parent.json").write_text(
            json.dumps(
                {
                    "invocationId": "one-parent",
                    "requestPath": locator["requestPath"],
                    "requestSha256": locator["requestSha256"],
                }
            )
        )
        return response

    monkeypatch.setattr(parent, "start", start)
    monkeypatch.setattr(parent, "status", lambda *args: response)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    store = q.Store(tmp_path / "queue")
    job = q.enqueue(store, path)
    return SimpleNamespace(
        store=store,
        job=job,
        plan=plan,
        path=path,
        calls=calls,
        response=response,
        start=start,
        evidence=evidence,
    )


def test_new_worker_reads_same_live_operation_then_verified(native_case: Any) -> None:
    case = native_case
    assert q.worker_once(case.store)
    assert case.store.get(case.job)["state"] == "running"
    q.worker_once(q.Store(case.store.root))
    assert case.calls == ["dispatch"]
    case.response["state"] = "verified"
    q.worker_once(q.Store(case.store.root))
    report = q.Store(case.store.root).publish(case.job)
    assert report["status"]["state"] == "completed_verified"
    assert report["nativeVerified"] is True
    assert len(report["trials"]) == 1
    assert case.calls == ["dispatch"]
    assert str(case.path.parent) not in json.dumps(report)
    assert "private-target" not in json.dumps(report)


def test_lost_start_reply_reconciles_without_another_start(
    native_case: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = native_case

    def lost(*args: Any) -> None:
        case.start(*args)
        raise OSError("lost reply containing private path")

    monkeypatch.setattr(parent, "start", lost)
    q.worker_once(case.store)
    q.worker_once(q.Store(case.store.root))
    assert case.calls == ["dispatch"]
    assert case.store.get(case.job)["state"] == "running"


def test_crash_after_intent_before_start_is_unknown_no_retry(
    native_case: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = native_case
    monkeypatch.setattr(
        parent,
        "start",
        lambda *args: (_ for _ in ()).throw(OSError("spawn uncertain")),
    )
    case.response["state"] = "unknown"
    q.worker_once(case.store)
    q.worker_once(q.Store(case.store.root))
    assert case.calls == []
    assert case.store.get(case.job)["state"] == "unknown"
    assert case.store.publish(case.job)["nativeVerified"] is False


def test_cancel_and_deadline_leave_native_live(native_case: Any) -> None:
    case = native_case
    q.worker_once(case.store)
    q.cancel(case.store, case.job)
    with case.store.connect() as db:
        db.execute("UPDATE jobs SET deadline_at=0 WHERE id=?", (case.job,))
    q.worker_once(q.Store(case.store.root))
    row = case.store.get(case.job)
    assert row["state"] == "running"
    assert row["cancel_requested"] == 1
    assert row["reason"] == "deadline_exceeded_native_live"
    assert row["ended_at"] is None
    assert case.calls == ["dispatch"]


def test_changed_frozen_plan_after_dispatch_retains_unknown(native_case: Any) -> None:
    case = native_case
    q.worker_once(case.store)
    frozen = case.store.jobdir(case.job) / "plan.json"
    frozen.chmod(0o600)
    frozen.write_text("{}")
    case.response["state"] = "verified"
    q.worker_once(q.Store(case.store.root))
    assert case.store.get(case.job)["state"] == "unknown"
    assert case.store.publish(case.job)["nativeVerified"] is False
    assert case.calls == ["dispatch"]


def test_two_workers_cannot_dispatch_twice(native_case: Any) -> None:
    case = native_case
    barrier = threading.Barrier(2)

    def worker() -> bool:
        barrier.wait()
        return q.worker_once(q.Store(case.store.root))

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert any(pool.map(lambda _: worker(), range(2)))
    assert case.calls == ["dispatch"]


def test_replay_enqueue_rejected(native_case: Any) -> None:
    with pytest.raises(Exception, match="UNIQUE"):
        q.enqueue(native_case.store, native_case.path)


def test_parent_invocation_cannot_change(native_case: Any) -> None:
    case = native_case
    q.worker_once(case.store)
    record = case.evidence / "parent.json"
    value = json.loads(record.read_text())
    value["invocationId"] = "foreign-parent"
    record.write_text(json.dumps(value))
    case.response["state"] = "verified"
    q.worker_once(q.Store(case.store.root))
    assert case.store.get(case.job)["state"] == "unknown"
    assert not case.store.publish(case.job)["nativeVerified"]


def test_other_queue_root_cannot_reuse_request(native_case: Any) -> None:
    case = native_case
    other = q.Store(case.path.parent / "second-queue")
    other_job = q.enqueue(other, case.path)
    q.worker_once(case.store)
    q.worker_once(other)
    assert other.get(other_job)["state"] == "blocked_native"
    assert case.calls == ["dispatch"]


def test_no_space_prevents_native_intent(
    native_case: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = native_case
    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda path: Usage(100, 100, 0))
    q.worker_once(case.store)
    assert case.store.get(case.job)["state"] == "blocked_native"
    assert case.store.get(case.job)["reason"] == "insufficient_space"
    assert case.calls == []
    with case.store.connect() as db:
        assert db.execute("SELECT intent_at FROM native_attempts").fetchone()[0] is None


def test_stale_input_prevents_dispatch(
    native_case: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = native_case
    monkeypatch.setattr(
        native,
        "preflight",
        lambda plan: (_ for _ in ()).throw(ValueError("changed bytes")),
    )
    q.worker_once(case.store)
    assert case.store.get(case.job)["state"] == "blocked_native"
    assert case.calls == []


def test_missing_receipt_retains_unknown_and_reconciles_same(native_case: Any) -> None:
    case = native_case
    q.worker_once(case.store)
    case.response["state"] = "unknown"
    q.worker_once(q.Store(case.store.root))
    assert case.store.get(case.job)["state"] == "unknown"
    case.response["state"] = "verified"
    q.worker_once(q.Store(case.store.root))
    assert case.store.get(case.job)["state"] == "completed_verified"
    assert case.calls == ["dispatch"]


def test_prepare_native_derives_private_plan_without_dispatch(
    native_case: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = native_case
    request_path = Path(case.plan["native"]["requestPath"])
    request_path.parent.mkdir()
    request = {
        **case.plan["native"],
        "attestationPath": str(case.path.parent / "attest.json"),
    }
    request_path.write_text(json.dumps(request))
    view: dict[str, Any] = {
        "timeline": {},
        "tracks": [],
        "sources": [],
        "events": [],
        "markers": [],
        "composition": {},
    }
    monkeypatch.setattr(
        workflow_v2,
        "load_verified_package_v2",
        lambda *args: SimpleNamespace(attestation={"buildId": "fresh"}, view=view),
    )
    output = case.path.parent / "private-native-plan.json"
    assert (
        q.main(
            [
                "--root",
                str(case.store.root),
                "prepare-native",
                "--request",
                str(request_path),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    plan = json.loads(output.read_text())
    assert plan["native"]["expected"] == native.expected_for_package(
        SimpleNamespace(view=view)
    )
    assert plan["fixtureId"] == "synthetic-fresh"
    assert case.calls == []
    assert (
        q.main(
            [
                "--root",
                str(case.store.root),
                "prepare-native",
                "--request",
                str(request_path),
                "--output",
                str(output),
            ]
        )
        == 2
    )  # Never overwrite a prepared private plan.
