"""M3 campaign worker: one durable M2 child at a time; never replay native effects."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_resolve_test_campaign import example_campaign, example_trial, write_campaign
from vera_timeline_agent import resolve_test_campaign as campaign
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import resolve_test_queue_native as native
from vera_timeline_agent import workflow_v2_parent as parent
from vera_timeline_agent.resolve_native_owner import NativeOwnerError


class FakeParent:
    def __init__(self) -> None:
        self.starts: list[str] = []
        self.responses: dict[str, str] = {}
        self.lost_reply = False
        self.start_gate: threading.Event | None = None
        self.entered = threading.Event()

    def start(
        self, path: Path, request_sha: str, _python: Path, **kw: Any
    ) -> dict[str, Any]:
        assert kw == {"independent_disposable": True}
        request = json.loads(path.read_bytes())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == request_sha
        self.starts.append(request_sha)
        evidence = Path(request["evidenceDir"])
        parent._write(
            evidence / "parent.json",
            {
                "invocationId": f"invocation-{request_sha[:12]}",
                "requestPath": str(path),
                "requestSha256": request_sha,
            },
        )
        self.entered.set()
        if self.start_gate is not None:
            assert self.start_gate.wait(4), "test failed to release fake start"
        if self.lost_reply:
            raise OSError("lost start reply")
        return {"state": "live"}

    def status(self, _path: Path, request_sha: str) -> dict[str, Any]:
        state = self.responses.get(request_sha, "live")
        result: dict[str, Any] = {"state": state}
        if state in {"verified", "failed", "blocked"}:
            result.update(elapsedSeconds=1.0, completedAt=queue.iso(queue.now_utc()))
        return result


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
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

    def enqueue(count: int = 2) -> str:
        plan = example_campaign(tmp_path, count)
        return campaign.enqueue_campaign(store, write_campaign(tmp_path, plan))

    return SimpleNamespace(store=store, fake=fake, enqueue=enqueue, tmp_path=tmp_path)


def rows(store: queue.Store, campaign_id: str) -> list[dict[str, Any]]:
    with store.connect() as db:
        return [
            dict(x)
            for x in db.execute(
                "SELECT * FROM campaign_trials WHERE campaign_id=? ORDER BY ordinal",
                (campaign_id,),
            )
        ]


def state(store: queue.Store, campaign_id: str) -> str:
    with store.connect() as db:
        return str(
            db.execute(
                "SELECT state FROM campaigns WHERE id=?", (campaign_id,)
            ).fetchone()[0]
        )


def verify(fake: FakeParent, request_sha: str) -> None:
    fake.responses[request_sha] = "verified"


def test_serial_children_are_immutable_and_each_started_once(setup: Any) -> None:
    cid = setup.enqueue(3)
    store, fake = setup.store, setup.fake
    assert campaign.campaign_worker_once(store)
    assert len(fake.starts) == 1
    assert [r["state"] for r in rows(store, cid)] == ["running", "pending", "pending"]
    for index in range(3):
        assert len(fake.starts) == index + 1
        child = rows(store, cid)[index]
        assert (
            queue.load_frozen_plan(store, child["child_job_id"])["native"][
                "requestSha256"
            ]
            == child["request_sha"]
        )
        verify(fake, fake.starts[-1])
        assert campaign.campaign_worker_once(
            queue.Store(store.root)
        )  # read-only reconcile
        assert rows(store, cid)[index]["state"] == "completed_verified"
        if index < 2:
            assert campaign.campaign_worker_once(queue.Store(store.root))
    assert campaign.campaign_worker_once(store)  # terminal aggregate
    assert state(store, cid) == "completed_verified"
    assert len(fake.starts) == len(set(fake.starts)) == 3
    with store.connect() as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM native_attempts WHERE job_id IN "
                "(SELECT child_job_id FROM campaign_trials WHERE campaign_id=?)",
                (cid,),
            ).fetchone()[0]
            == 3
        )


def test_unknown_parent_halts_and_keeps_same_native_request(setup: Any) -> None:
    cid = setup.enqueue()
    assert campaign.campaign_worker_once(setup.store)
    sha = setup.fake.starts[0]
    setup.fake.responses[sha] = "unknown"
    assert campaign.campaign_worker_once(queue.Store(setup.store.root))
    assert state(setup.store, cid) == "unknown"
    assert not campaign.campaign_worker_once(queue.Store(setup.store.root))
    assert setup.fake.starts == [sha]
    assert rows(setup.store, cid)[1]["child_job_id"] is None


def test_read_only_reconcile_updates_unknown_child_without_restart(setup: Any) -> None:
    cid = setup.enqueue()
    assert campaign.campaign_worker_once(setup.store)
    sha = setup.fake.starts[0]
    setup.fake.responses[sha] = "unknown"
    assert campaign.campaign_worker_once(setup.store)
    assert rows(setup.store, cid)[0]["state"] == "unknown"
    assert state(setup.store, cid) == "unknown"
    verify(setup.fake, sha)
    assert campaign.reconcile_campaign(setup.store, cid)
    assert rows(setup.store, cid)[0]["state"] == "completed_verified"
    # Unknown campaign remains stopped; proof must not become dispatch permission.
    assert state(setup.store, cid) == "unknown"
    assert setup.fake.starts == [sha]


def test_terminal_native_intent_does_not_wedge_new_campaign(setup: Any) -> None:
    cid = setup.enqueue()
    foreign_plan = example_trial(setup.tmp_path, 995, "foreign")["plan"]
    foreign_path = setup.tmp_path / "terminal-foreign.json"
    foreign_path.write_bytes(queue.canonical(foreign_plan))
    foreign = queue.enqueue(setup.store, foreign_path)
    assert queue.worker_once(setup.store)
    assert len(setup.fake.starts) == 1
    with setup.store.connect() as db:
        db.execute("UPDATE jobs SET state='blocked_native' WHERE id=?", (foreign,))
        assert db.execute(
            "SELECT intent_at FROM native_attempts WHERE job_id=?", (foreign,)
        ).fetchone()[0]
    assert not campaign._native_slot_busy(setup.store)
    assert campaign.campaign_worker_once(setup.store)
    assert len(setup.fake.starts) == 2
    assert rows(setup.store, cid)[0]["state"] == "running"


def test_final_verified_child_completes_despite_pause(setup: Any) -> None:
    cid = setup.enqueue(1)
    assert campaign.campaign_worker_once(setup.store)
    assert campaign.control_campaign(
        setup.store,
        cid,
        action="pause",
        command_id="pause-final",
        actor="operator",
        authorized=True,
    )
    verify(setup.fake, setup.fake.starts[0])
    assert campaign.campaign_worker_once(setup.store)
    assert campaign.campaign_worker_once(setup.store)
    assert state(setup.store, cid) == "completed_verified"


def test_no_intent_bound_child_obeys_deadline_after_restart(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = setup.enqueue(1)

    def abort_before_start(*_args: Any, **_kwargs: Any) -> None:
        raise SystemExit("before first intent")

    monkeypatch.setattr(queue, "run_native", abort_before_start)
    with pytest.raises(SystemExit, match="before first intent"):
        campaign.campaign_worker_once(setup.store)
    child = rows(setup.store, cid)[0]["child_job_id"]
    with setup.store.connect() as db:
        db.execute("UPDATE jobs SET deadline_at=0 WHERE id=?", (child,))
    assert campaign.campaign_worker_once(setup.store)
    assert state(setup.store, cid) == "blocked"
    with setup.store.connect() as db:
        assert (
            db.execute(
                "SELECT intent_at FROM native_attempts WHERE job_id=?", (child,)
            ).fetchone()[0]
            is None
        )
    assert not setup.fake.starts


def test_unverified_m2_terminal_is_never_promoted_to_campaign_pass(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = setup.enqueue()
    assert campaign.campaign_worker_once(setup.store)
    verify(setup.fake, setup.fake.starts[0])
    # Regression against a classifier/receipt that claims a terminal result
    # without authenticating native save/reopen/readback proof.
    monkeypatch.setattr(
        native,
        "classify_parent_status",
        lambda *_args, **_kwargs: SimpleNamespace(
            disposition="verified", reason="false_positive", native_verified=False
        ),
    )
    assert campaign.campaign_worker_once(setup.store)
    assert state(setup.store, cid) == "unknown"
    assert rows(setup.store, cid)[1]["state"] == "canceled"
    assert len(setup.fake.starts) == 1


def test_foreign_live_native_occupies_slot_until_verified(setup: Any) -> None:
    cid = setup.enqueue()
    separate = example_trial(setup.tmp_path, 98, "foreign")["plan"]
    path = setup.tmp_path / "foreign.json"
    path.write_bytes(queue.canonical(separate))
    foreign = queue.enqueue(setup.store, path)
    assert queue.worker_once(setup.store)
    assert len(setup.fake.starts) == 1
    assert not campaign.campaign_worker_once(setup.store)
    assert rows(setup.store, cid)[0]["child_job_id"] is None
    verify(setup.fake, setup.fake.starts[0])
    assert not campaign.campaign_worker_once(
        setup.store
    )  # reconciles foreign, no start
    assert setup.store.get(foreign)["state"] == "completed_verified"
    assert campaign.campaign_worker_once(setup.store)
    assert len(setup.fake.starts) == 2


def test_preflight_owner_busy_stops_without_native_intent(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = setup.enqueue()

    def busy(_name: str) -> None:
        raise NativeOwnerError("owner_busy", "foreign native operation")

    monkeypatch.setattr(queue, "preflight_independent_disposable", busy)
    assert campaign.campaign_worker_once(setup.store)
    assert not setup.fake.starts
    assert state(setup.store, cid) == "blocked"
    child = rows(setup.store, cid)[0]["child_job_id"]
    with setup.store.connect() as db:
        assert (
            db.execute(
                "SELECT intent_at FROM native_attempts WHERE job_id=?", (child,)
            ).fetchone()[0]
            is None
        )


def test_crash_before_intent_reuses_reserved_child_not_a_second_job(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = setup.enqueue()
    real_run = queue.run_native

    def crash(*_args: Any, **_kwargs: Any) -> None:
        raise SystemExit("killed after child transaction")

    monkeypatch.setattr(queue, "run_native", crash)
    with pytest.raises(SystemExit, match="killed"):
        campaign.campaign_worker_once(setup.store)
    child = rows(setup.store, cid)[0]["child_job_id"]
    assert child
    assert setup.store.get(child)["state"] == "running"
    assert queue.worker_once(setup.store) is False  # M2 cannot orphan campaign child
    monkeypatch.setattr(queue, "run_native", real_run)
    assert campaign.campaign_worker_once(queue.Store(setup.store.root))
    assert rows(setup.store, cid)[0]["child_job_id"] == child
    assert len(setup.fake.starts) == 1
    assert setup.store.get(child)["attempt"] == 1


def test_crash_before_intent_yields_to_new_foreign_native_owner(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = setup.enqueue()
    real_run = queue.run_native
    monkeypatch.setattr(
        queue,
        "run_native",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(SystemExit(12)),
    )
    with pytest.raises(SystemExit):
        campaign.campaign_worker_once(setup.store)
    child_id = rows(setup.store, cid)[0]["child_job_id"]
    foreign_plan = example_trial(setup.tmp_path, 90, "foreign")["plan"]
    foreign_path = setup.tmp_path / "foreign.json"
    foreign_path.write_bytes(queue.canonical(foreign_plan))
    foreign_id = queue.enqueue(setup.store, foreign_path)
    monkeypatch.setattr(queue, "run_native", real_run)
    assert queue.worker_once(setup.store)
    foreign_sha = setup.fake.starts[0]
    assert not campaign.campaign_worker_once(setup.store)
    assert setup.store.get(child_id)["state"] == "running"
    assert len(setup.fake.starts) == 1
    verify(setup.fake, foreign_sha)
    assert not campaign.campaign_worker_once(setup.store)
    assert setup.store.get(foreign_id)["state"] == "completed_verified"
    assert campaign.campaign_worker_once(setup.store)
    assert len(setup.fake.starts) == 2
    assert rows(setup.store, cid)[0]["child_job_id"] == child_id


def test_foreign_unknown_native_intent_never_lends_slot_to_campaign(
    setup: Any,
) -> None:
    cid = setup.enqueue()
    foreign_plan = example_trial(setup.tmp_path, 90, "foreign")["plan"]
    foreign_path = setup.tmp_path / "foreign.json"
    foreign_path.write_bytes(queue.canonical(foreign_plan))
    foreign_id = queue.enqueue(setup.store, foreign_path)
    assert queue.worker_once(setup.store)
    setup.fake.responses[setup.fake.starts[0]] = "unknown"
    assert queue.worker_once(setup.store)
    assert setup.store.get(foreign_id)["state"] == "unknown"
    assert not campaign.campaign_worker_once(setup.store)
    assert state(setup.store, cid) == "queued"
    assert len(setup.fake.starts) == 1


def test_crash_after_intent_and_lost_reply_never_start_again(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = setup.enqueue()
    setup.fake.lost_reply = True
    original_reconcile = queue.reconcile_native

    def crash(*_args: Any, **_kwargs: Any) -> None:
        raise SystemExit("killed after start, before observation")

    monkeypatch.setattr(queue, "reconcile_native", crash)
    with pytest.raises(SystemExit, match="killed"):
        campaign.campaign_worker_once(setup.store)
    child = rows(setup.store, cid)[0]["child_job_id"]
    with setup.store.connect() as db:
        assert db.execute(
            "SELECT intent_at FROM native_attempts WHERE job_id=?", (child,)
        ).fetchone()[0]
    monkeypatch.setattr(queue, "reconcile_native", original_reconcile)
    assert campaign.campaign_worker_once(queue.Store(setup.store.root))
    assert len(setup.fake.starts) == 1
    verify(setup.fake, setup.fake.starts[0])
    assert campaign.campaign_worker_once(queue.Store(setup.store.root))
    assert rows(setup.store, cid)[0]["state"] == "completed_verified"
    assert len(setup.fake.starts) == 1


def test_cancel_pending_before_and_during_native_does_not_claim_native_stopped(
    setup: Any,
) -> None:
    cid = setup.enqueue()
    with setup.store.connect() as db:
        db.execute("UPDATE campaigns SET cancel_pending=1 WHERE id=?", (cid,))
    assert campaign.campaign_worker_once(setup.store)
    assert state(setup.store, cid) == "canceled"
    assert not setup.fake.starts
    assert all(r["state"] == "canceled" for r in rows(setup.store, cid))

    second_root = setup.tmp_path / "second"
    second_plan = example_campaign(second_root, 2)
    for trial in second_plan["trials"]:
        trial["plan"]["targetId"] += "-second"
        trial["planSha256"] = hashlib.sha256(queue.canonical(trial["plan"])).hexdigest()
    cid2 = campaign.enqueue_campaign(
        setup.store,
        write_campaign(second_root, second_plan),
    )
    assert campaign.campaign_worker_once(setup.store)
    sha = setup.fake.starts[0]
    with setup.store.connect() as db:
        db.execute("UPDATE campaigns SET cancel_pending=1 WHERE id=?", (cid2,))
    assert campaign.campaign_worker_once(setup.store)
    assert state(setup.store, cid2) == "running"
    assert (
        setup.store.get(rows(setup.store, cid2)[0]["child_job_id"])["state"]
        == "running"
    )
    verify(setup.fake, sha)
    assert campaign.campaign_worker_once(setup.store)
    assert campaign.campaign_worker_once(setup.store)
    assert state(setup.store, cid2) == "canceled"
    assert rows(setup.store, cid2)[1]["state"] == "canceled"
    assert setup.fake.starts == [sha]


def test_pause_after_active_never_starts_next(setup: Any) -> None:
    cid = setup.enqueue()
    assert campaign.campaign_worker_once(setup.store)
    with setup.store.connect() as db:
        db.execute("UPDATE campaigns SET pause_after_active=1 WHERE id=?", (cid,))
    verify(setup.fake, setup.fake.starts[0])
    assert campaign.campaign_worker_once(setup.store)
    assert campaign.campaign_worker_once(setup.store)
    assert state(setup.store, cid) == "paused"
    assert rows(setup.store, cid)[1]["state"] == "pending"
    assert len(setup.fake.starts) == 1


def test_concurrent_worker_uses_exclusive_queue_lock(setup: Any) -> None:
    cid = setup.enqueue()
    fake = setup.fake
    fake.start_gate = threading.Event()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(campaign.campaign_worker_once, setup.store)
        assert fake.entered.wait(4)
        second = pool.submit(
            campaign.campaign_worker_once, queue.Store(setup.store.root)
        )
        assert second.result(timeout=4) is False
        fake.start_gate.set()
        assert first.result(timeout=4) is True
    assert len(fake.starts) == 1
    assert campaign.campaign_worker_once(setup.store)
    assert len(fake.starts) == 1
    assert rows(setup.store, cid)[0]["state"] == "running"


def test_future_campaign_does_not_starve_due_one(setup: Any) -> None:
    future = example_campaign(setup.tmp_path / "future")
    future["runAt"] = queue.iso(queue.now_utc() + timedelta(minutes=1))
    future["deadlineAt"] = queue.iso(queue.now_utc() + timedelta(minutes=56))
    for trial in future["trials"]:
        trial["plan"]["runAt"] = future["runAt"]
        trial["plan"]["targetId"] += "-future"
        trial["planSha256"] = hashlib.sha256(queue.canonical(trial["plan"])).hexdigest()
    path = setup.tmp_path / "future.json"
    path.write_bytes(queue.canonical(future))
    future_id = campaign.enqueue_campaign(setup.store, path)
    due_id = setup.enqueue()
    assert campaign.campaign_worker_once(setup.store)
    assert state(setup.store, future_id) == "queued"
    assert state(setup.store, due_id) == "running"


# Separate Python processes prove the restart path does not depend on a live
# agent, a thread-local fake or an inherited coordinator connection.
_PROCESS = r"""
import json, sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from vera_timeline_agent import resolve_test_campaign as campaign
from vera_timeline_agent import resolve_test_queue as q
from vera_timeline_agent import resolve_test_queue_native as native
from vera_timeline_agent import workflow_v2_parent as parent
root, count_path, mode = Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
native.preflight = lambda plan: json.loads(
    Path(plan["native"]["requestPath"]).read_bytes())
q.preflight_independent_disposable = lambda _target: None
native.classify_parent_status = lambda response, **kw: SimpleNamespace(
    disposition=response["state"], reason="fake_" + response["state"],
    native_verified=response["state"] == "verified")
def start(path, request_sha, _exe, *, independent_disposable):
    assert independent_disposable is True
    with count_path.open("a") as f:
        f.write("start\n")
        f.flush()
    request = json.loads(path.read_bytes())
    parent._write(Path(request["evidenceDir"]) / "parent.json", {
        "invocationId": "process-invocation", "requestPath": str(path),
        "requestSha256": request_sha,
    })
    return {"state": "live"}
parent.start = start
parent.status = lambda *_args: (
    {"state": "verified", "elapsedSeconds": 0.1,
     "completedAt": q.iso(q.now_utc())}
    if mode == "reconcile" else {"state": "live"}
)
if mode == "crash":
    q.reconcile_native = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        SystemExit(11))
worked = campaign.campaign_worker_once(q.Store(root))
print(json.dumps({"worked": worked}))
"""


@pytest.mark.slow
def test_process_exit_after_native_start_reconciles_without_second_start(
    setup: Any,
) -> None:
    cid = setup.enqueue(1)
    root = setup.store.root
    count_path = setup.tmp_path / "process-starts.log"
    python_root = Path(__file__).resolve().parents[1] / "python"

    def run(mode: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-c",
                _PROCESS,
                str(python_root),
                str(root),
                str(count_path),
                mode,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

    crashed = run("crash")
    assert crashed.returncode == 11, crashed.stderr
    first_child = rows(setup.store, cid)[0]["child_job_id"]
    assert first_child is not None
    with setup.store.connect() as db:
        attempt = db.execute(
            "SELECT intent_at FROM native_attempts WHERE job_id=?", (first_child,)
        ).fetchone()
        assert attempt["intent_at"]
    assert count_path.read_text().splitlines() == ["start"]
    restarted = run("reconcile")
    assert restarted.returncode == 0, restarted.stderr
    assert json.loads(restarted.stdout)["worked"] is True
    assert rows(setup.store, cid)[0]["child_job_id"] == first_child
    assert rows(setup.store, cid)[0]["state"] == "completed_verified"
    assert count_path.read_text().splitlines() == ["start"]
    finished = run("reconcile")
    assert finished.returncode == 0, finished.stderr
    assert state(setup.store, cid) == "completed_verified"
    assert count_path.read_text().splitlines() == ["start"]
