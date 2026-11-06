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
from typing import Any, cast

import pytest
from vera_timeline_agent import resolve_test_queue as q
from vera_timeline_agent import resolve_test_queue_native as native
from vera_timeline_agent import workflow_v2
from vera_timeline_agent import workflow_v2_parent as parent
from vera_timeline_agent.resolve_native_owner import NativeOwnerError


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
    monkeypatch.setattr(q, "preflight_independent_disposable", lambda _name: None)
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

    def start(*args: Any, **kwargs: Any) -> dict[str, Any]:
        assert kwargs == {"independent_disposable": True}
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


def mark_verified(case: Any, *, elapsed: float = 2.0, completed_at: Any = None) -> None:
    case.response.update(
        state="verified",
        elapsedSeconds=elapsed,
        completedAt=q.iso(completed_at or q.now_utc()),
    )


def _record_status(
    calls: list[tuple[Any, ...]], args: tuple[Any, ...], response: dict[str, Any]
) -> dict[str, Any]:
    calls.append(args)
    return response


def test_new_worker_reads_same_live_operation_then_verified(native_case: Any) -> None:
    case = native_case
    assert q.worker_once(case.store)
    assert case.store.get(case.job)["state"] == "running"
    q.worker_once(q.Store(case.store.root))
    assert case.calls == ["dispatch"]
    mark_verified(case)
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

    def lost(*args: Any, **kwargs: Any) -> None:
        case.start(*args, **kwargs)
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


def test_old_unknown_without_intent_does_not_hide_live_native_attempt(
    native_case: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = native_case
    second_plan = dict(case.plan)
    second_plan["native"] = {
        **case.plan["native"],
        "requestPath": str(case.path.parent / "second-request/request.json"),
        "requestSha256": "d" * 64,
    }
    second_plan_path = case.path.parent / "second-plan.json"
    second_plan_path.write_text(json.dumps(second_plan))
    second_job = q.enqueue(case.store, second_plan_path)
    evidence = case.path.parent / "second-private-evidence"
    request = {"evidenceDir": str(evidence)}
    monkeypatch.setattr(
        native,
        "preflight",
        lambda plan: (
            request
            if plan["native"]["requestSha256"] == "d" * 64
            else {"evidenceDir": str(case.evidence)}
        ),
    )
    started_at = q.iso(q.now_utc() - timedelta(seconds=1))
    intent_at = q.iso(q.now_utc())
    with case.store.connect() as db:
        db.execute(
            "UPDATE jobs SET state='unknown',reason='interrupted',ended_at=? "
            "WHERE id=?",
            (q.iso(q.now_utc()), case.job),
        )
        db.execute(
            "UPDATE jobs SET state='running',started_at=?,worker_id=?,attempt=1 "
            "WHERE id=?",
            (started_at, "test-worker", second_job),
        )
        plan_sha = db.execute(
            "SELECT plan_sha FROM jobs WHERE id=?", (second_job,)
        ).fetchone()[0]
        db.execute(
            "UPDATE native_attempts SET intent_at=? WHERE job_id=?",
            (intent_at, second_job),
        )
    evidence.mkdir()
    parent._write(
        evidence / "queue-intent.json",
        {
            "jobId": second_job,
            "attempt": 1,
            "planSha256": plan_sha,
            "requestSha256": "d" * 64,
        },
    )
    parent._write(
        evidence / "parent.json",
        {
            "invocationId": "live-second-parent",
            "requestPath": second_plan["native"]["requestPath"],
            "requestSha256": "d" * 64,
        },
    )
    status_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        parent,
        "status",
        lambda *args: _record_status(status_calls, args, case.response),
    )

    assert q.worker_once(case.store)
    assert case.store.get(case.job)["state"] == "unknown"
    assert case.store.get(second_job)["state"] == "running"
    assert len(status_calls) == 1
    assert status_calls[0][1] == "d" * 64
    assert case.calls == []


def test_busy_parent_reply_blocks_without_status_or_retry(
    native_case: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = native_case
    starts: list[str] = []
    status_calls: list[tuple[Any, ...]] = []

    def busy(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        assert kwargs == {"independent_disposable": True}
        starts.append("busy")
        return {"state": "busy", "verified": False}

    monkeypatch.setattr(parent, "start", busy)
    monkeypatch.setattr(
        parent,
        "status",
        lambda *args: _record_status(status_calls, args, case.response),
    )

    assert q.worker_once(case.store)
    row = case.store.get(case.job)
    assert row["state"] == "blocked_native"
    assert row["reason"] == "blocked_resource_owner"
    with case.store.connect() as db:
        attempt = db.execute(
            "SELECT intent_at,parent_state,native_verified FROM native_attempts "
            "WHERE job_id=?",
            (case.job,),
        ).fetchone()
    assert attempt["intent_at"]
    assert attempt["parent_state"] == "busy"
    assert attempt["native_verified"] == 0
    assert starts == ["busy"]
    assert status_calls == []
    assert not (case.evidence / "parent.json").exists()
    assert not q.worker_once(q.Store(case.store.root))
    assert starts == ["busy"]


def _set_attempt_clock(
    case: Any, *, started_at: Any, intent_at: Any, deadline_at: Any
) -> None:
    deadline_timestamp = (
        deadline_at.timestamp()
        if callable(getattr(deadline_at, "timestamp", None))
        else deadline_at
    )
    with case.store.connect() as db:
        db.execute(
            "UPDATE jobs SET started_at=?,deadline_at=? WHERE id=?",
            (q.iso(started_at), deadline_timestamp, case.job),
        )
        db.execute(
            "UPDATE native_attempts SET intent_at=? WHERE job_id=?",
            (q.iso(intent_at), case.job),
        )


def test_on_time_native_completion_stays_verified_when_observed_after_deadline(
    native_case: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = native_case
    q.worker_once(case.store)
    completed_at = q.now_utc() - timedelta(seconds=10)
    intent_at = completed_at - timedelta(seconds=2)
    started_at = intent_at - timedelta(seconds=3)
    deadline_at = completed_at + timedelta(seconds=1)
    _set_attempt_clock(
        case, started_at=started_at, intent_at=intent_at, deadline_at=deadline_at
    )
    mark_verified(case, elapsed=2.0, completed_at=completed_at)
    monkeypatch.setattr(
        shutil,
        "disk_usage",
        lambda _path: pytest.fail("terminal parent must not be checked for free space"),
    )

    assert q.worker_once(q.Store(case.store.root))
    report = q.Store(case.store.root).publish(case.job)
    assert report["status"]["state"] == "completed_verified"
    assert report["nativeVerified"] is True


def test_completed_native_evidence_still_obeys_its_disk_budget(
    native_case: Any,
) -> None:
    case = native_case
    q.worker_once(case.store)
    (case.evidence / "oversized.log").write_bytes(b"x" * case.plan["maxDiskBytes"])
    mark_verified(case)
    q.worker_once(q.Store(case.store.root))
    report = case.store.publish(case.job)
    assert report["status"]["state"] == "blocked_native"
    assert report["status"]["reason"] == "disk_budget_exceeded_native_completed"
    assert report["nativeVerified"] is False


def test_authenticated_completion_after_deadline_cannot_pass(
    native_case: Any,
) -> None:
    case = native_case
    q.worker_once(case.store)
    completed_at = q.now_utc() - timedelta(seconds=10)
    intent_at = completed_at - timedelta(seconds=2)
    started_at = intent_at - timedelta(seconds=3)
    deadline_at = completed_at - timedelta(seconds=1)
    _set_attempt_clock(
        case, started_at=started_at, intent_at=intent_at, deadline_at=deadline_at
    )
    mark_verified(case, elapsed=2.0, completed_at=completed_at)

    assert q.worker_once(q.Store(case.store.root))
    report = case.store.publish(case.job)
    assert report["status"]["state"] == "timed_out"
    assert report["status"]["reason"] == "deadline_exceeded_native_completed"
    assert report["nativeVerified"] is False


def test_predispatch_time_counts_against_authenticated_elapsed_budget(
    native_case: Any,
) -> None:
    case = native_case
    q.worker_once(case.store)
    completed_at = q.now_utc()
    started_at = completed_at - timedelta(seconds=610)
    intent_at = started_at + timedelta(seconds=1)
    _set_attempt_clock(
        case,
        started_at=started_at,
        intent_at=intent_at,
        deadline_at=case.store.get(case.job)["deadline_at"],
    )
    mark_verified(case, elapsed=599.5, completed_at=completed_at)

    assert q.worker_once(q.Store(case.store.root))
    row = case.store.get(case.job)
    assert row["state"] == "timed_out"
    assert row["reason"] == "elapsed_budget_exceeded_native_completed"
    assert case.store.publish(case.job)["nativeVerified"] is False


@pytest.mark.parametrize(
    "clock_fields",
    [
        {},
        {"elapsedSeconds": 2.0},
        {"completedAt": "not-a-timestamp", "elapsedSeconds": 2.0},
        {"completedAt": "2026-11-04T12:00:00+00:00", "elapsedSeconds": float("nan")},
    ],
)
def test_missing_or_malformed_authenticated_completion_clock_cannot_pass(
    native_case: Any, clock_fields: dict[str, Any]
) -> None:
    case = native_case
    q.worker_once(case.store)
    case.response.clear()
    case.response.update(state="verified", **clock_fields)

    assert q.worker_once(q.Store(case.store.root))
    row = case.store.get(case.job)
    assert row["state"] == "unknown"
    assert row["reason"] == "native_identity_input_or_completion_clock_unavailable"
    assert case.store.publish(case.job)["nativeVerified"] is False


def test_negative_predispatch_clock_blocks_before_intent(
    native_case: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = native_case
    now = q.now_utc()
    queued_times = [now + timedelta(seconds=1), now + timedelta(seconds=1), now]
    real_now = q.now_utc
    monkeypatch.setattr(
        q,
        "now_utc",
        lambda: queued_times.pop(0) if queued_times else real_now(),
    )

    assert q.worker_once(case.store)
    row = case.store.get(case.job)
    assert row["state"] == "blocked_native"
    assert row["reason"] == "clock_uncertain_before_native_dispatch"
    assert case.calls == []
    with case.store.connect() as db:
        assert (
            db.execute(
                "SELECT intent_at FROM native_attempts WHERE job_id=?", (case.job,)
            ).fetchone()[0]
            is None
        )


def test_status_command_skips_reconciliation_during_dispatch(
    native_case: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case = native_case
    entered = threading.Event()
    release = threading.Event()
    status_calls: list[tuple[Any, ...]] = []
    original_start = case.start

    def blocked_start(*args: Any, **kwargs: Any) -> dict[str, Any]:
        entered.set()
        assert release.wait(timeout=5)
        return cast(dict[str, Any], original_start(*args, **kwargs))

    monkeypatch.setattr(parent, "start", blocked_start)
    monkeypatch.setattr(
        parent,
        "status",
        lambda *args: _record_status(status_calls, args, case.response),
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        worker = pool.submit(q.worker_once, case.store)
        try:
            assert entered.wait(timeout=5)
            case.response["state"] = "unknown"
            assert q.main(["--root", str(case.store.root), "status", case.job]) == 0
            observed = json.loads(capsys.readouterr().out)
            assert observed["state"] == "running"
            assert status_calls == []
            case.response["state"] = "live"
        finally:
            release.set()
        assert worker.result(timeout=5)
    assert case.store.get(case.job)["state"] == "running"
    assert len(status_calls) == 1


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


def test_foreign_native_owner_blocks_before_intent(
    native_case: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = native_case
    monkeypatch.setattr(
        q,
        "preflight_independent_disposable",
        lambda _name: (_ for _ in ()).throw(
            NativeOwnerError("owner_busy", "private owner path")
        ),
    )
    q.worker_once(case.store)
    assert case.store.get(case.job)["state"] == "blocked_native"
    assert case.store.get(case.job)["reason"] == "blocked_resource_owner"
    assert case.calls == []
    with case.store.connect() as db:
        assert db.execute("SELECT intent_at FROM native_attempts").fetchone()[0] is None
    assert "private owner path" not in json.dumps(case.store.publish(case.job))


def test_owner_race_is_blocked_without_retry(
    native_case: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = native_case
    monkeypatch.setattr(
        parent,
        "start",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            NativeOwnerError("owner_busy", "another route acquired the host")
        ),
    )
    q.worker_once(case.store)
    assert case.store.get(case.job)["state"] == "blocked_native"
    assert case.store.get(case.job)["reason"] == "blocked_resource_owner"
    q.worker_once(q.Store(case.store.root))
    assert case.calls == []


def test_missing_receipt_retains_unknown_and_reconciles_same(native_case: Any) -> None:
    case = native_case
    q.worker_once(case.store)
    case.response["state"] = "unknown"
    q.worker_once(q.Store(case.store.root))
    assert case.store.get(case.job)["state"] == "unknown"
    mark_verified(case)
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
            "schemaVersion": "resolve-native-view/v2",
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
