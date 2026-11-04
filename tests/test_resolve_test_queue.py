"""Deterministic tests for the M1 offline-only test queue."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import threading
import time
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import resolve_test_queue as queue_module
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

DiskUsage = namedtuple("DiskUsage", "total used free")


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
    assert fresh["planIntegrity"] == "verified"
    assert fresh["plan"]["fixtureId"] == "synthetic-fixed"
    assert fresh["plan"]["fixtureSha256"] == "a" * 64
    assert fresh["plan"]["targetId"] == "disposable-synthetic"
    assert fresh["plan"]["category"] == "queue"
    assert fresh["status"]["attempt"] == 1
    assert isinstance(fresh["status"]["workerId"], str)
    assert fresh["status"]["deadlineAt"] > fresh["status"]["scheduledAt"]
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


@pytest.mark.parametrize(
    ("adapter", "expected_state"),
    [("mock.fail", "failed_simulated"), ("mock.block", "blocked_simulated")],
)
def test_mock_failure_and_block_are_classified(
    tmp_path: Path, adapter: str, expected_state: str
) -> None:
    value = plan()
    value["cases"] = [{"id": "case", "adapter": adapter, "iterations": 2, "delayMs": 0}]
    store = Store(tmp_path / "q")
    job = enqueue(store, write_plan(tmp_path, value))
    assert worker_once(store)
    assert store.get(job)["state"] == expected_state
    report = store.publish(job)
    assert len(report["trials"]) == 1
    assert report["trials"][0]["outcome"] == (
        adapter.removeprefix("mock.") + "_simulated"
    )
    assert report["nativeVerified"] is False
    assert report["verifiedStatistics"] is None
    assert not worker_once(store)


def test_derived_reports_are_rebuilt_from_the_database(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    job = enqueue(store, write_plan(tmp_path, plan()))
    assert worker_once(store)
    folder = store.jobdir(job)
    for name in ("status.json", "report.json", "report.md"):
        (folder / name).unlink()
    rebuilt = Store(store.root).publish(job)
    assert rebuilt["status"]["state"] == "completed_simulated"
    for name in ("status.json", "report.json", "report.md"):
        assert (folder / name).is_file()
    shutil.rmtree(folder)
    without_folder = Store(store.root).publish(job)
    assert without_folder["status"]["state"] == "completed_simulated"
    assert without_folder["plan"] is None
    for name in ("status.json", "report.json", "report.md"):
        assert (folder / name).is_file()


def test_reports_do_not_expose_absolute_paths(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    job = enqueue(store, write_plan(tmp_path, plan()))
    assert worker_once(store)
    folder = store.jobdir(job)
    published = "".join(
        (folder / name).read_text(encoding="utf-8")
        for name in ("status.json", "report.json", "report.md")
    )
    assert str(tmp_path) not in published
    assert str(store.root) not in published
    assert str(Path.home()) not in published


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


def test_overdue_job_starts_late_with_truthful_times(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    value = plan()
    value["runAt"] = iso(now_utc() - timedelta(minutes=30))
    value["deadlineAt"] = iso(now_utc() + timedelta(minutes=30))
    job = enqueue(store, write_plan(tmp_path, value))
    assert worker_once(store)
    status = store.publish(job)["status"]
    assert status["state"] == "completed_simulated"
    assert status["scheduledAt"] < status["startedAt"]


def test_at_argument_overrides_plan_schedule(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    future = iso(now_utc() + timedelta(hours=3))
    job = enqueue(store, write_plan(tmp_path, plan()), at=future)
    assert store.publish(job)["status"]["scheduledAt"] == future


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
                {
                    "id": "x",
                    "adapter": "native.resolve",
                    "iterations": 1,
                    "delayMs": 0,
                }
            ]
        },
        {
            "cases": [
                {
                    "id": "x",
                    "adapter": "mock.pass",
                    "iterations": 99,
                    "delayMs": 0,
                }
            ]
        },
        {"sourceCommit": "secret"},
        {"schema": "vera.resolve-test-plan/v2"},
        {"unexpectedKey": True},
        {"cases": []},
        {
            "cases": [
                {"id": "same", "adapter": "mock.pass", "iterations": 1, "delayMs": 0},
                {"id": "same", "adapter": "mock.pass", "iterations": 1, "delayMs": 0},
            ]
        },
        {"runAt": "2026-11-05T23:00:00"},
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


def test_missing_required_plan_key_is_refused(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    value = plan()
    del value["fixtureSha256"]
    with pytest.raises(QueueError, match="missing"):
        enqueue(store, write_plan(tmp_path, value))
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_deadline_must_follow_run_at(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    value = plan()
    value["runAt"] = iso(now_utc())
    value["deadlineAt"] = iso(now_utc() - timedelta(minutes=1))
    with pytest.raises(QueueError, match="deadlineAt"):
        enqueue(store, write_plan(tmp_path, value))


def test_symlinked_plan_refused(tmp_path: Path) -> None:
    source = write_plan(tmp_path, plan())
    (tmp_path / "link.json").symlink_to(source)
    with pytest.raises(QueueError, match="symlinks"):
        enqueue(Store(tmp_path / "q"), tmp_path / "link.json")


def test_changed_plan_blocks_without_replay(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    job = enqueue(store, write_plan(tmp_path, plan()))
    frozen = store.jobdir(job) / "plan.json"
    frozen.chmod(0o600)
    frozen.write_text("{}", encoding="utf-8")
    assert worker_once(store)
    assert store.get(job)["state"] == "unknown"
    changed = Store(store.root).publish(job)
    assert changed["trials"] == []
    assert changed["plan"] is None
    assert changed["planIntegrity"] == "unavailable_or_changed"
    assert not worker_once(store)


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read mode-000 files")
def test_unreadable_frozen_plan_is_unknown(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    job = enqueue(store, write_plan(tmp_path, plan()))
    frozen = store.jobdir(job) / "plan.json"
    frozen.chmod(0o000)
    try:
        assert worker_once(store)
        unreadable = Store(store.root).publish(job)
    finally:
        frozen.chmod(0o600)
    assert store.get(job)["state"] == "unknown"
    assert store.get(job)["reason"] == "unreadable_frozen_plan"
    assert unreadable["trials"] == []
    assert unreadable["plan"] is None
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


@pytest.mark.slow
def test_killed_worker_is_unknown_and_never_replayed(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    value = plan()
    value["maxElapsedSeconds"] = 10
    value["cases"][0]["delayMs"] = 5000
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
    process = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        for _ in range(500):
            if store.get(job)["state"] == "running":
                break
            time.sleep(0.01)
        else:
            pytest.fail("worker never claimed the job")
        process.terminate()
        process.communicate(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
    assert store.get(job)["state"] == "running"
    assert worker_once(store)
    assert store.get(job)["state"] == "unknown"
    assert store.get(job)["reason"] == "interrupted_worker_no_replay"
    assert Store(store.root).publish(job)["trials"] == []
    assert not worker_once(store)


def test_in_flight_cancel_cooperates(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    value = plan()
    value["cases"][0]["delayMs"] = 2000
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


def test_in_flight_absolute_deadline_expires(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    value = plan()
    value["runAt"] = iso(now_utc() - timedelta(seconds=1))
    value["deadlineAt"] = iso(now_utc() + timedelta(seconds=1))
    value["maxElapsedSeconds"] = 10
    value["cases"][0]["delayMs"] = 5000
    job = enqueue(store, write_plan(tmp_path, value))
    assert worker_once(store)
    assert store.get(job)["state"] == "expired"
    assert store.get(job)["reason"] == "absolute_deadline_reached"
    assert store.publish(job)["trials"] == []


def test_insufficient_free_space_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path / "q")
    job = enqueue(store, write_plan(tmp_path, plan()))
    monkeypatch.setattr(
        queue_module,
        "shutil",
        SimpleNamespace(disk_usage=lambda _: DiskUsage(3_000_000, 2_500_000, 500_000)),
    )
    assert worker_once(store)
    assert store.get(job)["state"] == "blocked_simulated"
    assert store.get(job)["reason"] == "disk_budget_or_space"
    assert store.publish(job)["trials"] == []


def test_per_job_disk_budget_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path / "q")
    job = enqueue(store, write_plan(tmp_path, plan()))
    monkeypatch.setattr(queue_module, "folder_bytes", lambda _: 2_000_000)
    assert worker_once(store)
    assert store.get(job)["state"] == "blocked_simulated"
    assert store.get(job)["reason"] == "disk_budget_or_space"
    assert store.publish(job)["trials"] == []


def test_many_simultaneous_enqueue_ids(tmp_path: Path) -> None:
    store = Store(tmp_path / "q")
    source = write_plan(tmp_path, plan())
    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(lambda _: enqueue(Store(store.root), source), range(12)))
    assert len(set(ids)) == 12
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 12
    assert all((store.jobdir(job_id) / "plan.json").is_file() for job_id in ids)
    with store.connect() as db:
        digests = {
            row["id"]: row["plan_sha"]
            for row in db.execute("SELECT id,plan_sha FROM jobs")
        }
    for job_id in ids:
        content = (store.jobdir(job_id) / "plan.json").read_bytes()
        assert json.loads(content)["fixtureSha256"] == "a" * 64
        assert hashlib.sha256(content).hexdigest() == digests[job_id]


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
    report = subprocess.run(
        [*command, "report", job, "--format", "markdown"],
        capture_output=True,
        text=True,
    )
    assert report.returncode == 0, report.stderr
    assert "Native proof: NO" in report.stdout


def test_plist_is_readable_and_opt_in(tmp_path: Path) -> None:
    definition = plistlib.loads(agent_plist(tmp_path / "q", "/usr/bin/python3"))
    assert definition["RunAtLoad"] is True
    assert definition["StartInterval"] == 60
    assert definition["ProgramArguments"][-2:] == ["worker", "once"]
    assert definition["Label"] == "org.vera.resolve-test-queue.m1"


def test_launchd_installation_is_macos_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    with pytest.raises(QueueError, match="macOS"):
        queue_module.install_agent(Store(tmp_path / "q"))


def test_input_copy_does_not_change_when_enqueued(tmp_path: Path) -> None:
    value = plan()
    original = copy.deepcopy(value)
    store = Store(tmp_path / "q")
    enqueue(store, write_plan(tmp_path, value))
    assert value == original


def test_fifo_plan_is_refused_without_waiting_for_writer(tmp_path: Path) -> None:
    source = tmp_path / "plan.fifo"
    os.mkfifo(source)
    with pytest.raises(QueueError, match="regular JSON file"):
        queue_module.read_plan_file(source)


def test_trial_duration_uses_monotonic_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path / "q")
    job = enqueue(store, write_plan(tmp_path, plan()))
    timestamp = now_utc()
    calls = 0

    def clock() -> Any:
        nonlocal calls
        calls += 1
        return timestamp - timedelta(seconds=calls)

    monkeypatch.setattr(queue_module, "now_utc", clock)
    assert worker_once(store)
    report = store.publish(job)
    assert report["status"]["state"] == "completed_simulated"
    assert all(row["wall_seconds"] >= 0 for row in report["trials"])


@pytest.mark.parametrize("loaded", [True, False])
def test_matching_launch_agent_is_started_if_unloaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loaded: bool
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    store = Store(tmp_path / "q")
    target = (
        tmp_path / "Library" / "LaunchAgents" / f"{queue_module.LAUNCH_LABEL}.plist"
    )
    target.parent.mkdir(parents=True)
    payload = agent_plist(store.root, sys.executable)
    target.write_bytes(payload)
    calls: list[list[str]] = []

    def launchctl(args: list[str], **kwargs: Any) -> Any:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0 if loaded else 1)

    monkeypatch.setattr(subprocess, "run", launchctl)
    queue_module.install_agent(store)
    assert [args[1] for args in calls] == (
        ["print"] if loaded else ["print", "bootstrap"]
    )
    assert target.read_bytes() == payload


def test_dangling_launch_agent_symlink_is_not_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    target = (
        tmp_path / "Library" / "LaunchAgents" / f"{queue_module.LAUNCH_LABEL}.plist"
    )
    target.parent.mkdir(parents=True)
    target.symlink_to(tmp_path / "absent")
    with pytest.raises(QueueError, match="refusing overwrite"):
        queue_module.install_agent(Store(tmp_path / "q"))
    assert target.is_symlink()


def test_cancel_during_final_trial_publication_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path / "q")
    job = enqueue(store, write_plan(tmp_path, plan()))
    publish = store.publish
    canceled = False

    def publish_and_cancel(job_id: str) -> dict[str, Any]:
        nonlocal canceled
        report = publish(job_id)
        if (
            not canceled
            and report["status"]["state"] == "running"
            and len(report["trials"]) == 2
        ):
            canceled = True
            cancel(store, job_id)
        return report

    monkeypatch.setattr(store, "publish", publish_and_cancel)
    assert worker_once(store)
    assert store.get(job)["state"] == "canceled"
    assert len(publish(job)["trials"]) == 2


def test_enqueue_syncs_job_directory_entry_before_committing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path / "q")
    sync = queue_module.sync_directory
    synced = False

    def observe_sync(path: Path) -> None:
        nonlocal synced
        if path == store.root:
            with store.connect() as db:
                assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
            synced = True
        sync(path)

    monkeypatch.setattr(queue_module, "sync_directory", observe_sync)
    enqueue(store, write_plan(tmp_path, plan()))
    assert synced
