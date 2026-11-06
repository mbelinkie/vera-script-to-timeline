"""M3 aggregate projections: proof-only timing and data-private durable controls."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_resolve_test_campaign import example_campaign, write_campaign
from test_resolve_test_campaign_worker import FakeParent, rows, state, verify
from vera_timeline_agent import resolve_test_campaign as campaign
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import resolve_test_queue_native as native
from vera_timeline_agent import workflow_v2_parent as parent


@pytest.fixture
def native_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    fake = FakeParent()
    monkeypatch.setattr(
        native,
        "preflight",
        lambda plan: json.loads(Path(plan["native"]["requestPath"]).read_bytes()),
    )
    monkeypatch.setattr(queue, "preflight_independent_disposable", lambda _name: None)
    monkeypatch.setattr(parent, "start", fake.start)
    monkeypatch.setattr(parent, "status", fake.status)
    monkeypatch.setattr(
        native,
        "classify_parent_status",
        lambda response, **_kw: SimpleNamespace(
            disposition=response["state"],
            reason="parent_" + response["state"],
            native_verified=response["state"] == "verified",
        ),
    )
    store = queue.Store(tmp_path / "queue")

    def enqueue(count: int) -> str:
        plan = example_campaign(tmp_path, count)
        return campaign.enqueue_campaign(store, write_campaign(tmp_path, plan))

    return SimpleNamespace(store=store, fake=fake, enqueue=enqueue)


@pytest.fixture
def campaign_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[queue.Store, str, dict[str, Any]]:
    monkeypatch.setattr(native, "preflight", lambda _plan: {})
    store = queue.Store(tmp_path / "store")
    plan = example_campaign(tmp_path, 2)
    cid = campaign.enqueue_campaign(store, write_campaign(tmp_path, plan))
    return store, cid, plan


def command(store: queue.Store, cid: str, action: str, identity: str) -> dict[str, Any]:
    return campaign.control_campaign(
        store,
        cid,
        action=action,
        command_id=identity,
        actor="producer",
        authorized=True,
    )


def test_100_case_report_is_bounded_and_private(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setattr(native, "preflight", lambda _plan: {})
    store = queue.Store(tmp_path / "store")
    plan = example_campaign(tmp_path / "synthetic", 100, paired=True)
    cid = campaign.enqueue_campaign(store, write_campaign(tmp_path / "inputs", plan))
    with store.connect() as db:
        db.execute(
            "INSERT INTO campaign_events(campaign_id,at,kind,detail) VALUES(?,?,?,?)",
            (
                cid,
                queue.iso(queue.now_utc()),
                "external",
                str(tmp_path / "private.mov"),
            ),
        )
    result = campaign.publish_campaign(store, cid)
    assert result["status"]["totalTrials"] == 200
    assert result["status"]["verifiedTrials"] == 0
    assert len(result["observations"]) == 200
    assert result["statistics"] == []
    assert result["regressions"] == []
    assert result["journal"][-1]["detail"] == "redacted"
    directory = store.root / cid
    for name in ("status.json", "report.json", "report.md"):
        assert (directory / name).is_file()
        raw = (directory / name).read_text()
        assert str(tmp_path) not in raw
        assert "private.mov" not in raw
        assert "evidenceDir" not in raw
    assert json.loads((directory / "report.json").read_bytes()) == result
    snapshot = {
        name: (directory / name).read_bytes()
        for name in ("status.json", "report.json", "report.md")
    }
    assert result["status"]["budget"]["ownedBytes"] == campaign._owned_bytes(store, cid)
    assert campaign.publish_campaign(store, cid) == result
    assert all(
        (directory / name).read_bytes() == data for name, data in snapshot.items()
    )


def test_controls_are_authorized_audited_idempotent_and_versioned(
    campaign_store: tuple[queue.Store, str, dict[str, Any]],
) -> None:
    store, cid, _ = campaign_store
    with pytest.raises(queue.QueueError, match="authenticated"):
        campaign.control_campaign(
            store, cid, action="cancel", command_id="cmd-1", actor="producer"
        )
    paused = command(store, cid, "pause", "cmd-1")
    assert paused["outcome"] == "accepted"
    assert state(store, cid) == "paused"
    assert not campaign.campaign_worker_once(store)
    assert command(store, cid, "pause", "cmd-1") == {**paused, "replayed": True}
    with pytest.raises(queue.QueueError, match="replay"):
        command(store, cid, "cancel", "cmd-1")
    with pytest.raises(queue.QueueError, match="replay"):
        campaign.control_campaign(
            store,
            cid,
            action="pause",
            command_id="cmd-1",
            actor="somebody-else",
            authorized=True,
        )
    resumed = command(store, cid, "resume", "cmd-2")
    assert resumed["version"] > paused["version"]
    assert state(store, cid) == "queued"
    stopped = command(store, cid, "cancel", "cmd-3")
    assert stopped["version"] > resumed["version"]
    assert state(store, cid) == "canceled"
    assert [step["state"] for step in rows(store, cid)] == ["canceled", "canceled"]
    assert command(store, cid, "cancel", "cmd-3")["replayed"] is True
    with pytest.raises(queue.QueueError, match="canceled"):
        command(store, cid, "resume", "cmd-4")
    report = campaign.publish_campaign(store, cid)
    assert len(report["commands"]) == 3
    assert [e["action"] for e in report["commands"]] == ["pause", "resume", "cancel"]
    assert report["status"]["version"] == stopped["version"]


def test_running_pause_and_cancel_never_stop_live_native(native_setup: Any) -> None:
    setup = native_setup
    cid = setup.enqueue(3)
    assert campaign.campaign_worker_once(setup.store)
    first_sha = setup.fake.starts[0]
    assert state(setup.store, cid) == "running"
    assert command(setup.store, cid, "pause", "pause-1")["outcome"] == "accepted"
    assert state(setup.store, cid) == "running"
    assert command(setup.store, cid, "pause", "pause-1")["replayed"] is True
    verify(setup.fake, first_sha)
    assert campaign.campaign_worker_once(setup.store)
    assert campaign.campaign_worker_once(setup.store)
    assert state(setup.store, cid) == "paused"
    assert len(setup.fake.starts) == 1
    assert command(setup.store, cid, "resume", "resume-1")
    assert campaign.campaign_worker_once(setup.store)
    assert len(setup.fake.starts) == 2
    assert command(setup.store, cid, "cancel", "cancel-1")
    assert campaign.campaign_worker_once(setup.store)
    assert state(setup.store, cid) == "running"
    assert len(setup.fake.starts) == 2  # no mid-native stop or new start
    verify(setup.fake, setup.fake.starts[-1])
    assert campaign.campaign_worker_once(setup.store)
    assert campaign.campaign_worker_once(setup.store)
    assert state(setup.store, cid) == "canceled"
    assert rows(setup.store, cid)[2]["state"] == "canceled"


def test_reconcile_command_never_calls_parent_start(
    native_setup: Any, monkeypatch: Any
) -> None:
    setup = native_setup
    cid = setup.enqueue(2)
    assert campaign.campaign_worker_once(setup.store)
    original = setup.fake.starts[:]
    monkeypatch.setattr(
        parent,
        "start",
        lambda *_args, **_kw: (_ for _ in ()).throw(AssertionError("dispatch")),
    )
    result = command(setup.store, cid, "reconcile", "observe-1")
    assert result["outcome"] == "read_only_observation_requested"
    assert setup.fake.starts == original
    assert campaign.publish_campaign(setup.store, cid)["status"]["heartbeat"]
    assert command(setup.store, cid, "reconcile", "observe-1")["replayed"]


def test_stats_only_authenticated_with_compatible_env(native_setup: Any) -> None:
    setup = native_setup
    cid = setup.enqueue(2)
    for index in range(2):
        if not index:
            assert campaign.campaign_worker_once(setup.store)
        else:
            assert campaign.campaign_worker_once(setup.store)
        verify(setup.fake, setup.fake.starts[-1])
        assert campaign.campaign_worker_once(setup.store)
    if state(setup.store, cid) == "running":
        assert campaign.campaign_worker_once(setup.store)
    assert state(setup.store, cid) == "completed_verified"
    report = campaign.publish_campaign(setup.store, cid)
    assert report["status"]["verifiedTrials"] == 0  # fake parent != authenticated
    assert report["statistics"] == []
    # Simulate the *persisted* metadata of a native-authenticated M2 terminal
    # receipt, and prove the reporter checks all four independent DB guards.
    with setup.store.connect() as db:
        for i, step in enumerate(rows(setup.store, cid)):
            db.execute(
                "UPDATE native_attempts SET parent_state='terminal' WHERE job_id=?",
                (step["child_job_id"],),
            )
            db.execute(
                "UPDATE campaign_trials SET environment_sha=?,timing_spans_json=? "
                "WHERE campaign_id=? AND ordinal=?",
                ("a" * 64, '{"save":0.25}', cid, i),
            )
            db.execute(
                "UPDATE trials SET wall_seconds=? WHERE job_id=?",
                (10.0 if i == 0 else 14.0, step["child_job_id"]),
            )
    result = campaign.publish_campaign(setup.store, cid)
    assert result["status"]["verifiedTrials"] == 2
    assert result["status"]["comparableTrials"] == 2
    assert len(result["statistics"]) == 2  # separate cases, no invented pairing
    assert result["regressions"] == []
    assert result["statistics"][0]["medianSeconds"] == 10.0
    assert result["observations"][0]["namedOverheadSeconds"] == {"save": 0.25}
    assert result["observations"][0]["nativeWaitSeconds"] is None
    with setup.store.connect() as db:
        first = rows(setup.store, cid)[0]
        db.execute(
            "UPDATE native_attempts SET native_verified=0 WHERE job_id=?",
            (first["child_job_id"],),
        )
    excluded = campaign.publish_campaign(setup.store, cid)
    assert excluded["status"]["verifiedTrials"] == 1
    assert len(excluded["statistics"]) == 1


def test_paired_regression_requires_same_authenticated_environment(
    native_setup: Any,
) -> None:
    setup = native_setup
    plan = example_campaign(setup.store.root.parent / "paired", 1, paired=True)
    cid = campaign.enqueue_campaign(
        setup.store,
        write_campaign(setup.store.root.parent / "paired-input", plan),
    )
    assert campaign.campaign_worker_once(setup.store)
    for i in range(2):
        verify(setup.fake, setup.fake.starts[-1])
        assert campaign.campaign_worker_once(setup.store)
        if i == 0:
            assert campaign.campaign_worker_once(setup.store)
    if state(setup.store, cid) == "running":
        assert campaign.campaign_worker_once(setup.store)
    assert state(setup.store, cid) == "completed_verified"
    for i, trial in enumerate(rows(setup.store, cid)):
        with setup.store.connect() as db:
            db.execute(
                "UPDATE native_attempts SET parent_state='terminal' WHERE job_id=?",
                (trial["child_job_id"],),
            )
            db.execute(
                "UPDATE campaign_trials SET environment_sha=?,timing_spans_json=? "
                "WHERE campaign_id=? AND ordinal=?",
                ("a" * 64, "{}", cid, i),
            )
            db.execute(
                "UPDATE trials SET wall_seconds=? WHERE job_id=?",
                (10.0 + i * 2.0, trial["child_job_id"]),
            )
    report = campaign.publish_campaign(setup.store, cid)
    assert report["status"]["comparableTrials"] == 2
    assert len(report["statistics"]) == 2
    assert report["regressions"][0]["regressionPercent"] == pytest.approx(20.0)
    assert report["regressions"][0]["deltaSeconds"] == pytest.approx(2.0)
    with setup.store.connect() as db:
        db.execute(
            "UPDATE campaign_trials SET environment_sha=? "
            "WHERE campaign_id=? AND ordinal=1",
            ("b" * 64, cid),
        )
    assert campaign.publish_campaign(setup.store, cid)["regressions"] == []


def test_limits_tamper_refuses_next_dispatch(campaign_store: Any) -> None:
    store, cid, plan = campaign_store
    with store.connect() as db:
        db.execute(
            "UPDATE campaigns SET max_disk_bytes=? WHERE id=?",
            (plan["maxDiskBytes"] * 2, cid),
        )
    assert campaign.publish_campaign(store, cid)["status"]["planIntegrity"] == (
        "unavailable_or_changed"
    )
    assert campaign.campaign_worker_once(store)
    status = campaign.publish_campaign(store, cid)["status"]
    assert status["state"] == "unknown"
    assert status["reason"] == "campaign_frozen_limits_changed"
    assert all(row["child_job_id"] is None for row in rows(store, cid))


def test_parent_clock_forgery_excludes_observation(native_setup: Any) -> None:
    setup = native_setup
    cid = setup.enqueue(1)
    assert campaign.campaign_worker_once(setup.store)
    verify(setup.fake, setup.fake.starts[0])
    assert campaign.campaign_worker_once(setup.store)
    child = rows(setup.store, cid)[0]["child_job_id"]
    with setup.store.connect() as db:
        db.execute(
            "UPDATE native_attempts SET parent_state='terminal' WHERE job_id=?",
            (child,),
        )
        db.execute(
            "UPDATE campaign_trials SET environment_sha=?,timing_spans_json='{}' "
            "WHERE campaign_id=?",
            ("a" * 64, cid),
        )
        db.execute(
            "UPDATE jobs SET started_at=? WHERE id=?",
            (queue.iso(queue.now_utc() + timedelta(minutes=3)), child),
        )
    report = campaign.publish_campaign(setup.store, cid)
    assert report["status"]["verifiedTrials"] == 0
    assert report["statistics"] == []


def test_clock_and_byte_caps_block_next_native_child(
    campaign_store: tuple[queue.Store, str, dict[str, Any]],
    monkeypatch: Any,
) -> None:
    store, cid, _ = campaign_store
    with store.connect() as db:
        db.execute(
            "UPDATE campaigns SET state='running',started_at=? WHERE id=?",
            (queue.iso(queue.now_utc() + timedelta(minutes=2)), cid),
        )
    assert campaign.campaign_worker_once(store)
    assert campaign.publish_campaign(store, cid)["status"]["reason"] == (
        "campaign_clock_uncertain"
    )
    other_store = queue.Store(store.root.parent / "other-queue")
    second_plan = example_campaign(store.root / "bytes", 2)
    second_plan["maxDiskBytes"] = 1048576
    cid2 = campaign.enqueue_campaign(
        other_store, write_campaign(store.root / "second", second_plan)
    )
    (other_store.root / cid2 / "large.bin").write_bytes(b"0" * 1048577)
    assert campaign.campaign_worker_once(other_store)
    report = campaign.publish_campaign(other_store, cid2)
    assert report["status"]["reason"] == "campaign_disk_budget_exceeded"
    assert all(row["childJobId"] is None for row in report["observations"])


def test_unsafe_tree_or_corrupt_plan_excludes_stats(campaign_store: Any) -> None:
    store, cid, _ = campaign_store
    (store.root / cid / "unsafe-link").symlink_to(store.root / "queue.sqlite3")
    assert (
        campaign.publish_campaign(store, cid)["status"]["budget"]["accountingVerified"]
        is False
    )
    assert campaign.campaign_worker_once(store)
    assert campaign.publish_campaign(store, cid)["status"]["reason"] == (
        "campaign_resources_unverifiable"
    )
    plan = store.root / cid / "plan.json"
    plan.chmod(0o600)
    plan.write_bytes(b"not the immutable plan")
    plan.chmod(0o400)
    assert campaign.publish_campaign(store, cid)["status"]["planIntegrity"] == (
        "unavailable_or_changed"
    )
