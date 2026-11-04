from __future__ import annotations

import copy
import json
import os
import plistlib
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent.resolve_test_queue import (
    PLAN_SCHEMA,
    QueueError,
    Store,
    agent_plist,
    cancel,
    enqueue,
    iso,
    now_utc,
    worker_once,
)


def plan() -> dict[str, Any]:
    return {
        "schema": PLAN_SCHEMA,
        "name": "offline-m1",
        "fixtureId": "synthetic-fixed",
        "fixtureSha256": "a" * 64,
        "targetId": "disposable-synthetic",
        "targetPolicy": "synthetic_only",
        "category": "queue",
        "maxElapsedSeconds": 4,
        "maxDiskBytes": 1048576,
        "cases": [
            {"id": "first", "adapter": "mock.pass", "iterations": 2, "delayMs": 0}
        ],
    }


def write_plan(folder: Path, value: dict[str, Any]) -> Path:
    path = folder / "plan.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_reopened_store_and_reports_are_simulated(tmp_path: Path) -> None:
    root = tmp_path / "queue"
    job = enqueue(Store(root), write_plan(tmp_path, plan()))
    assert Store(root).get(job)["state"] == "queued"
    assert worker_once(Store(root))
    fresh = Store(root).publish(job)
    assert fresh["status"]["state"] == "completed_simulated"
    assert fresh["nativeVerified"] is False
    assert fresh["verifiedStatistics"] is None
    assert len(fresh["trials"]) == 2
    assert all(trial["native_verified"] == 0 for trial in fresh["trials"])
    assert [entry["kind"] for entry in fresh["journal"]] == [
        "enqueued",
        "running",
        "trial",
        "trial",
        "completed_simulated",
    ]
    folder = root / job
    assert (folder / "status.json").exists()
    assert (folder / "report.json").exists()
    assert "Native proof: NO" in (folder / "report.md").read_text(encoding="utf-8")
    assert not worker_once(Store(root))


def test_future_schedule_and_queued_cancellation(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    future = plan()
    future["runAt"] = iso(now_utc() + timedelta(hours=2))
    job = enqueue(store, write_plan(tmp_path, future))
    assert not worker_once(store)
    assert store.get(job)["state"] == "queued"
    cancel(store, job)
    assert store.get(job)["state"] == "canceled"
    assert not worker_once(store)


@pytest.mark.parametrize(
    "schedule",
    [
        {"runAt": "tomorrow"},
        {"runAt": "2026-11-05T12:00:00"},
        {"deadlineAt": "tomorrow"},
        {"deadlineAt": "2026-11-05T12:00:00"},
        {
            "runAt": "2026-11-06T12:00:00Z",
            "deadlineAt": "2026-11-05T12:00:00Z",
        },
        {
            "runAt": "2026-11-05T12:00:00Z",
            "deadlineAt": "2026-11-05T12:00:00Z",
        },
    ],
)
def test_malformed_or_inverted_schedule_is_refused(
    tmp_path: Path, schedule: dict[str, str]
) -> None:
    store = Store(tmp_path / "q")
    value = plan()
    value.update(schedule)
    with pytest.raises(QueueError):
        enqueue(store, write_plan(tmp_path, value))
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_malformed_schedule_override_is_refused(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    with pytest.raises(QueueError, match="ISO-8601"):
        enqueue(store, write_plan(tmp_path, plan()), at="after lunch")
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_expired_before_claim(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    value = plan()
    value["runAt"] = iso(now_utc() - timedelta(hours=2))
    value["deadlineAt"] = iso(now_utc() - timedelta(hours=1))
    job = enqueue(store, write_plan(tmp_path, value))
    assert worker_once(store)
    assert store.get(job)["state"] == "expired"
    assert Store(store.root).publish(job)["trials"] == []


@pytest.mark.parametrize(
    "change",
    [
        {"targetPolicy": "existing_project"},
        {"fixtureId": "../private"},
        {"fixtureSha256": "not-a-hash"},
        {"maxElapsedSeconds": 0},
        {
            "cases": [
                {"id": "x", "adapter": "native.resolve", "iterations": 1, "delayMs": 0}
            ]
        },
        {
            "cases": [
                {"id": "x", "adapter": "mock.pass", "iterations": 99, "delayMs": 0}
            ]
        },
        {"sourceCommit": "secret"},
    ],
)
def test_plan_refusals(tmp_path: Path, change: dict[str, Any]) -> None:
    store = Store(tmp_path / "q")
    value = plan()
    value.update(change)
    with pytest.raises(QueueError):
        enqueue(store, write_plan(tmp_path, value))
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_symlinked_plan_refused(tmp_path: Path) -> None:
    source = write_plan(tmp_path, plan())
    (tmp_path / "link.json").symlink_to(source)
    with pytest.raises(QueueError, match="symlinks"):
        enqueue(Store(tmp_path / "q"), tmp_path / "link.json")


def test_fifo_plan_refused_without_blocking(tmp_path: Path) -> None:
    fifo = tmp_path / "plan.fifo"
    os.mkfifo(fifo)
    with pytest.raises(QueueError, match="regular JSON file"):
        enqueue(Store(tmp_path / "q"), fifo)


def test_changed_plan_blocks_without_replay(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    job = enqueue(store, write_plan(tmp_path, plan()))
    frozen = store.jobdir(job) / "plan.json"
    frozen.chmod(0o600)
    frozen.write_text("{}", encoding="utf-8")
    assert worker_once(store)
    assert store.get(job)["state"] == "unknown"
    assert Store(store.root).publish(job)["trials"] == []
    assert not worker_once(store)


def test_orphan_running_is_unknown_not_replayed(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    job = enqueue(store, write_plan(tmp_path, plan()))
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "UPDATE jobs SET state='running',worker_id='dead' WHERE id=?", (job,)
        )
        store.append(db, job, "running", "worker:dead")
    assert worker_once(store)
    assert store.get(job)["state"] == "unknown"
    assert Store(store.root).publish(job)["trials"] == []
    assert not worker_once(store)


def test_in_flight_cancel_cooperates(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    value = plan()
    value["cases"][0]["delayMs"] = 800
    job = enqueue(store, write_plan(tmp_path, value))
    thread = threading.Thread(target=worker_once, args=(Store(store.root),))
    thread.start()
    for _ in range(100):
        if store.get(job)["state"] == "running":
            break
        time.sleep(0.01)
    else:
        pytest.fail("worker never started")
    cancel(store, job)
    thread.join(timeout=4)
    assert not thread.is_alive()
    assert store.get(job)["state"] == "canceled"
    assert store.publish(job)["trials"] == []


def test_elapsed_timeout(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    value = plan()
    value["maxElapsedSeconds"] = 1
    value["cases"][0]["delayMs"] = 1400
    job = enqueue(store, write_plan(tmp_path, value))
    assert worker_once(store)
    assert store.get(job)["state"] == "timed_out"
    assert store.publish(job)["trials"] == []


def test_wall_clock_jump_consumes_elapsed_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path / "q")
    value = plan()
    value["maxElapsedSeconds"] = 1
    job = enqueue(store, write_plan(tmp_path, value))

    real_time = time.time
    calls = 0

    def jump_after_first_trial() -> float:
        nonlocal calls
        calls += 1
        if calls >= 6:
            return real_time() + 2
        return real_time()

    monkeypatch.setattr(
        "vera_timeline_agent.resolve_test_queue.time.time", jump_after_first_trial
    )
    assert worker_once(store)

    report = store.publish(job)
    assert report["status"]["state"] == "timed_out"
    assert report["status"]["reason"] == "job_elapsed_budget_exhausted"
    assert len(report["trials"]) == 1
    assert calls >= 6


@pytest.mark.parametrize(
    ("adapter", "state", "outcome"),
    [
        ("mock.fail", "failed_simulated", "fail_simulated"),
        ("mock.block", "blocked_simulated", "block_simulated"),
    ],
)
def test_mock_fail_or_block_stops_remaining_cases(
    tmp_path: Path, adapter: str, state: str, outcome: str
) -> None:
    store = Store(tmp_path / "q")
    value = plan()
    value["cases"] = [
        {"id": "stop-here", "adapter": adapter, "iterations": 2, "delayMs": 0},
        {
            "id": "must-not-run",
            "adapter": "mock.pass",
            "iterations": 1,
            "delayMs": 0,
        },
    ]
    job = enqueue(store, write_plan(tmp_path, value))

    assert worker_once(store)
    report = store.publish(job)

    assert report["status"]["state"] == state
    assert report["status"]["reason"] == "case:stop-here"
    assert [(trial["case_id"], trial["outcome"]) for trial in report["trials"]] == [
        ("stop-here", outcome)
    ]
    assert report["nativeVerified"] is False
    assert report["journal"][-1]["kind"] == state


def test_reports_are_rebuilt_from_authoritative_store(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    job = enqueue(store, write_plan(tmp_path, plan()))
    assert worker_once(store)

    folder = store.jobdir(job)
    (folder / "status.json").unlink()
    (folder / "report.json").write_text('{"tampered": true}', encoding="utf-8")
    (folder / "report.md").unlink()

    rebuilt = Store(store.root).publish(job)

    assert (
        json.loads((folder / "status.json").read_text(encoding="utf-8"))
        == rebuilt["status"]
    )
    assert json.loads((folder / "report.json").read_text(encoding="utf-8")) == rebuilt
    assert "State: completed_simulated" in (folder / "report.md").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("exhaustion", ["job_budget", "free_space"])
def test_disk_exhaustion_blocks_before_recording_trial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exhaustion: str,
) -> None:
    store = Store(tmp_path / "q")
    job = enqueue(store, write_plan(tmp_path, plan()))
    if exhaustion == "job_budget":
        (store.jobdir(job) / "filler.bin").write_bytes(b"x" * (1048576 + 1))
    else:
        monkeypatch.setattr(
            "vera_timeline_agent.resolve_test_queue.shutil.disk_usage",
            lambda _path: SimpleNamespace(free=1048575),
        )

    assert worker_once(store)
    report = store.publish(job)
    assert report["status"]["state"] == "blocked_simulated"
    assert report["status"]["reason"] == "disk_budget_or_space"
    assert report["trials"] == []


def test_many_simultaneous_enqueue_ids(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    source = write_plan(tmp_path, plan())
    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(lambda _: enqueue(Store(store.root), source), range(12)))
    assert len(set(ids)) == 12
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 12


@pytest.mark.slow
def test_worker_process_race_no_duplicate(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    value = plan()
    value["cases"][0]["delayMs"] = 300
    job = enqueue(store, write_plan(tmp_path, value))
    args = [
        sys.executable,
        "-m",
        "vera_timeline_agent.resolve_test_queue",
        "--root",
        str(store.root),
        "worker",
        "once",
    ]
    one = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    two = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    _, error_one = one.communicate(timeout=8)
    _, error_two = two.communicate(timeout=8)
    assert one.returncode == 0, error_one
    assert two.returncode == 0, error_two
    result = store.publish(job)
    assert result["status"]["state"] == "completed_simulated"
    assert len(result["trials"]) == 2
    assert [event["kind"] for event in result["journal"]].count("running") == 1


@pytest.mark.slow
def test_cli_is_independent_new_process(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    job = enqueue(store, write_plan(tmp_path, plan()))
    command = [
        sys.executable,
        "-m",
        "vera_timeline_agent.resolve_test_queue",
        "--root",
        str(store.root),
    ]
    worker = subprocess.run(
        [*command, "worker", "once"], capture_output=True, text=True
    )
    assert worker.returncode == 0, worker.stderr
    status = subprocess.run([*command, "status", job], capture_output=True, text=True)
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)["state"] == "completed_simulated"


@pytest.mark.slow
def test_killed_worker_restart_marks_unknown_without_replay(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    value = plan()
    value["cases"][0]["delayMs"] = 300000
    job = enqueue(store, write_plan(tmp_path, value))
    args = [
        sys.executable,
        "-m",
        "vera_timeline_agent.resolve_test_queue",
        "--root",
        str(store.root),
        "worker",
        "once",
    ]
    worker = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if store.get(job)["state"] == "running":
                break
            if worker.poll() is not None:
                _, error = worker.communicate(timeout=1)
                pytest.fail(f"worker exited before starting: {error}")
            time.sleep(0.02)
        else:
            pytest.fail("worker never started")

        worker.kill()
        _, error = worker.communicate(timeout=8)
        assert worker.returncode != 0, error
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.communicate(timeout=8)

    restarted = subprocess.run(args, capture_output=True, text=True, timeout=8)
    assert restarted.returncode == 0, restarted.stderr
    result = Store(store.root).publish(job)
    assert result["status"]["state"] == "unknown"
    assert result["status"]["reason"] == "interrupted_worker_no_replay"
    assert [event["kind"] for event in result["journal"]].count("running") == 1
    assert [event["kind"] for event in result["journal"]].count("unknown") == 1
    assert result["trials"] == []
    assert not worker_once(Store(store.root))


def test_plist_is_readable_and_opt_in(tmp_path: Path) -> None:
    definition = plistlib.loads(agent_plist(tmp_path / "q", "/usr/bin/python3"))
    assert definition["RunAtLoad"] is True
    assert definition["StartInterval"] == 60
    assert definition["ProgramArguments"][-2:] == ["worker", "once"]
    assert definition["Label"] == "org.vera.resolve-test-queue.m1"


def test_input_copy_does_not_change_when_enqueued(tmp_path: Path) -> None:
    value = plan()
    original = copy.deepcopy(value)
    store = Store(tmp_path / "q")
    enqueue(store, write_plan(tmp_path, value))
    assert value == original
