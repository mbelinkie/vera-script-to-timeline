"""Injected-only Studio Edit-page setup; never connects to a real Mac/Resolve."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from _actor_pin import actor_pin
from vera_timeline_agent import resolve_gui_roll as roll
from vera_timeline_agent import resolve_test_bench_carrier as carrier
from vera_timeline_agent import resolve_test_bench_full_loop as loop
from vera_timeline_agent import resolve_test_bench_page_stage as page
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import resolve_test_queue_m4 as m4
from vera_timeline_agent import resolve_test_queue_m4_provision as provision

JOB = "resolve-reverse-" + "f" * 32
INITIAL = {
    "projectUid": "unique-new-project",
    "timelineUid": "unique-new-timeline",
    "projectName": "VERA Delivery 123e4567-e89b-12d3-a456-426614174000 012345abcdef",
    "timelineName": "VERA Delivery 123e4567-e89b-12d3-a456-426614174000 012345abcdef",
}
FRESH = {
    "projectUid": "distinct-new-project",
    "timelineUid": "distinct-new-timeline",
    "projectName": "VERA Delivery 123e4567-e89b-12d3-a456-426614174001 012345abcdee",
    "timelineName": "VERA Delivery 123e4567-e89b-12d3-a456-426614174001 012345abcdee",
}


class FakeResolve:
    def __init__(self) -> None:
        self.current_page = "deliver"
        self.project_uid = INITIAL["projectUid"]
        self.timeline_uid = INITIAL["timelineUid"]
        self.inventory_generation = 0
        self.calls: list[str] = []
        self.result: object = True
        self.change_page = True
        self.drift = False

    def GetCurrentPage(self) -> str:
        return self.current_page

    def OpenPage(self, value: str) -> object:
        self.calls.append(value)
        if self.change_page:
            self.current_page = value
        if self.drift:
            self.inventory_generation += 1
        return self.result


@pytest.fixture
def prepared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[dict[str, Any]]:
    case_root = tmp_path / "new-case"
    case_root.mkdir(mode=0o700)
    store_root = tmp_path / "queue"
    (store_root / JOB / "f1-gui-edit").mkdir(mode=0o700, parents=True)
    now = datetime.now(UTC)
    started = now - timedelta(minutes=1)
    deadline = now + timedelta(minutes=9)
    plan: dict[str, Any] = {
        "caseId": "synthetic-312",
        "initialTarget": dict(INITIAL),
        "freshTarget": dict(FRESH),
        "baselineSession": {"path": "/synthetic/session", "sha256": "a" * 64},
        "runAt": queue.iso(started),
        "deadlineAt": queue.iso(deadline),
        "maxElapsedSeconds": 1200,
    }
    auth: dict[str, Any] = {
        "schema": loop.AUTHORITY_SCHEMA,
        "caseId": "synthetic-312",
        "configSha256": "c" * 64,
        "frozenCommit": "e" * 40,
        "sourceGraphSha256": "f" * 64,
        "operation": "M4.edited.one-use-gui-roll",
        "fromFrame": 327,
        "toFrame": 351,
        "actorPin": actor_pin(),
        "initialTarget": dict(INITIAL),
        "freshTarget": dict(FRESH),
    }
    record = {
        "schema": loop.INTENT_SCHEMA,
        "authority": {"sha256": hashlib.sha256(queue.canonical(auth)).hexdigest()},
        "config": {"sha256": auth["configSha256"]},
        "frozenCommit": auth["frozenCommit"],
        "sourceGraphSha256": auth["sourceGraphSha256"],
    }
    carrier._once(case_root / "complete-loop-intent.json", queue.canonical(record))
    monkeypatch.setattr(
        provision, "completed", lambda _root: {"initial": INITIAL, "fresh": FRESH}
    )
    monkeypatch.setattr(m4, "_load_plan", lambda *_: plan)
    receipt = {
        "session": plan["baselineSession"],
        "capture": {"path": "/synthetic/capture", "sha256": "b" * 64},
    }
    monkeypatch.setattr(m4, "_stage_receipt", lambda *_: receipt)
    monkeypatch.setattr(roll, "_require_owner_lock", lambda: None)
    session = SimpleNamespace(
        context={"caseId": "synthetic-312", "phase": "pristine", "target": INITIAL}
    )
    monkeypatch.setattr(page, "load_output_session", lambda *_: session)
    monkeypatch.setattr(page, "_load_terminal_output_with_comparison", lambda *_: None)
    signed = {
        "status": "complete",
        "action": "capture_post",
        "context": session.context,
        "target": INITIAL,
        "nativeGeometry": {"signed": "eleven UIDs and six tracks"},
    }
    monkeypatch.setattr(page, "verify_native_result", lambda *_: signed)
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        "CREATE TABLE reverse_jobs (id TEXT,state TEXT,started_at TEXT,"
        "deadline_at REAL)"
    )
    db.execute(
        "INSERT INTO reverse_jobs VALUES (?,?,?,?)",
        (
            JOB,
            "awaiting_operator",
            queue.iso(started),
            queue.dt(plan["deadlineAt"]).timestamp(),
        ),
    )
    db.execute(
        "CREATE TABLE reverse_stages (job_id TEXT,ordinal INTEGER,name TEXT,state TEXT,"
        "operation_id TEXT,receipt_sha TEXT,intent_at TEXT)"
    )
    for ordinal, name in enumerate(("pristine", "edited", "revision", "rebuild")):
        db.execute(
            "INSERT INTO reverse_stages VALUES (?,?,?,?,?,?,?)",
            (
                JOB,
                ordinal,
                name,
                "verified"
                if ordinal == 0
                else "awaiting_operator"
                if ordinal == 1
                else "pending",
                "unique-operation-" + name,
                "a" * 64 if ordinal == 0 else None,
                queue.iso(now) if ordinal == 1 else None,
            ),
        )

    @contextmanager
    def connect() -> Iterator[sqlite3.Connection]:
        yield db

    resolve = FakeResolve()
    inspections: list[str] = []

    def inspect(
        sdk: FakeResolve, target: dict[str, str], geometry: dict[str, Any]
    ) -> dict[str, Any]:
        inspections.append(sdk.current_page)
        if (
            sdk.project_uid != target["projectUid"]
            or sdk.timeline_uid != target["timelineUid"]
            or geometry != signed["nativeGeometry"]
        ):
            raise queue.QueueError("existing producer project or wrong signed UID")
        return {
            "disposition": "read_only_no_edit_authorized",
            "resolveVersion": [21, 1, 1, 10, ""],
            "target": dict(target),
            "inventorySha": f"eleven-clips-six-tracks-{sdk.inventory_generation}",
        }

    monkeypatch.setattr(page, "inspect_selected", inspect)
    fixture = {
        "store": SimpleNamespace(root=store_root, connect=connect),
        "case_root": case_root,
        "authority": auth,
        "plan": plan,
        "record": record,
        "receipt": receipt,
        "signed": signed,
        "db": db,
        "resolve": resolve,
        "inspections": inspections,
    }
    yield fixture
    db.close()


def run(fixture: dict[str, Any]) -> None:
    page.open_owned_edit_page(
        fixture["store"],
        JOB,
        fixture["resolve"],
        case_root=fixture["case_root"],
        authority=fixture["authority"],
    )


def test_edit_page_only_after_authenticated_new_target_and_rechecks_sdk(
    prepared: dict[str, Any],
) -> None:
    run(prepared)
    assert prepared["resolve"].calls == ["edit"]
    assert prepared["resolve"].current_page == "edit"
    assert prepared["inspections"] == ["deliver", "edit"]
    assert not (
        prepared["store"].root / JOB / "f1-gui-edit" / "gui-intent.json"
    ).exists()


def test_already_edit_page_makes_no_navigation_request(
    prepared: dict[str, Any],
) -> None:
    prepared["resolve"].current_page = "edit"
    run(prepared)
    assert prepared["resolve"].calls == []
    assert prepared["inspections"] == ["edit", "edit"]


@pytest.mark.parametrize(
    "invalid",
    [
        "wrong_authority",
        "wrong_authority_target",
        "wrong_source_graph",
        "wrong_provision",
        "producer_project_selected",
        "wrong_timeline",
        "unknown_parent",
        "queued_parent",
        "unknown_stage",
        "pending_stage",
        "no_stage_intent",
        "future_stage_intent",
        "edited_receipt",
        "prior_gui_intent",
        "prior_gui_symlink",
        "unverified_pristine",
        "revision_in_progress",
        "wrong_pristine_session",
        "wrong_signed_target",
        "expired_deadline",
        "no_owner",
        "wrong_studio_version",
    ],
)
def test_all_unsafe_cases_refuse_before_sdk_open_page(
    prepared: dict[str, Any], monkeypatch: pytest.MonkeyPatch, invalid: str
) -> None:
    f = prepared
    db, sdk = f["db"], f["resolve"]
    if invalid == "wrong_authority":
        f["authority"]["operation"] = "unapproved"
    elif invalid == "wrong_authority_target":
        f["authority"]["initialTarget"] = FRESH
    elif invalid == "wrong_source_graph":
        f["authority"]["sourceGraphSha256"] = "0" * 64
    elif invalid == "wrong_provision":
        monkeypatch.setattr(
            provision, "completed", lambda *_: {"initial": FRESH, "fresh": INITIAL}
        )
    elif invalid == "producer_project_selected":
        sdk.project_uid = "real-producer-project"
    elif invalid == "wrong_timeline":
        sdk.timeline_uid = "other-timeline"
    elif invalid == "unknown_parent":
        db.execute("UPDATE reverse_jobs SET state='unknown'")
    elif invalid == "queued_parent":
        db.execute("UPDATE reverse_jobs SET state='queued'")
    elif invalid == "unknown_stage":
        db.execute("UPDATE reverse_stages SET state='unknown' WHERE ordinal=1")
    elif invalid == "pending_stage":
        db.execute("UPDATE reverse_stages SET state='pending' WHERE ordinal=1")
    elif invalid == "no_stage_intent":
        db.execute("UPDATE reverse_stages SET intent_at=NULL WHERE ordinal=1")
    elif invalid == "future_stage_intent":
        db.execute(
            "UPDATE reverse_stages SET intent_at='2099-11-09T12:00:00Z' WHERE ordinal=1"
        )
    elif invalid == "edited_receipt":
        db.execute(
            "UPDATE reverse_stages SET receipt_sha=? WHERE ordinal=1", ("a" * 64,)
        )
    elif invalid == "prior_gui_intent":
        (f["store"].root / JOB / "f1-gui-edit" / "gui-intent.json").write_text(
            "unknown"
        )
    elif invalid == "prior_gui_symlink":
        (f["store"].root / JOB / "f1-gui-edit" / "gui-intent.json").symlink_to(
            "missing"
        )
    elif invalid == "unverified_pristine":
        db.execute("UPDATE reverse_stages SET state='unknown' WHERE ordinal=0")
    elif invalid == "revision_in_progress":
        db.execute("UPDATE reverse_stages SET state='verifying' WHERE ordinal=2")
    elif invalid == "wrong_pristine_session":
        f["receipt"]["session"] = {"path": "other", "sha256": "b" * 64}
    elif invalid == "wrong_signed_target":
        f["signed"]["target"] = FRESH
    elif invalid == "expired_deadline":
        f["plan"]["deadlineAt"] = queue.iso(datetime.now(UTC) - timedelta(seconds=1))
    elif invalid == "no_owner":
        monkeypatch.setattr(
            roll,
            "_require_owner_lock",
            lambda: (_ for _ in ()).throw(queue.QueueError("no owner")),
        )
    elif invalid == "wrong_studio_version":
        monkeypatch.setattr(
            page,
            "inspect_selected",
            lambda *_: {
                "disposition": "read_only_no_edit_authorized",
                "resolveVersion": [21, 1, 2, 0, ""],
                "target": INITIAL,
            },
        )
    with pytest.raises((queue.QueueError, ValueError, OSError)):
        run(f)
    assert sdk.calls == [], f"OpenPage on unauthorized target: {invalid}"


@pytest.mark.parametrize(
    "invalid",
    [
        "sdk_refused",
        "page_not_changed",
        "sdk_exception",
        "sdk_timeout",
        "inventory_drift",
        "uid_drift",
        "deadline_after_open",
    ],
)
def test_failed_page_change_never_retries_or_dispatches_gui(
    prepared: dict[str, Any], monkeypatch: pytest.MonkeyPatch, invalid: str
) -> None:
    f = prepared
    sdk = f["resolve"]
    if invalid == "sdk_refused":
        sdk.result = False
    elif invalid == "page_not_changed":
        sdk.change_page = False
    elif invalid == "sdk_exception":

        def denied(_page: str) -> None:
            sdk.calls.append("edit")
            raise OSError("SDK transport interrupted")

        sdk.OpenPage = denied
    elif invalid == "sdk_timeout":
        times = iter((1.0, 6.01))
        monkeypatch.setattr(page, "monotonic", lambda: next(times))
    elif invalid == "inventory_drift":
        sdk.drift = True
    elif invalid == "uid_drift":

        def changed(_page: str) -> bool:
            sdk.calls.append("edit")
            sdk.current_page = "edit"
            sdk.project_uid = "producer-project-after-navigation"
            return True

        sdk.OpenPage = changed
    elif invalid == "deadline_after_open":

        def late(_page: str) -> bool:
            sdk.calls.append("edit")
            sdk.current_page = "edit"
            return True

        sdk.OpenPage = late
        # Simulated wall-clock jump only AFTER the SDK page request, proving
        # the post-effect cumulative deadline is independently checked.
        monkeypatch.setattr(
            page,
            "datetime",
            type(
                "LateClock",
                (),
                {
                    "now": staticmethod(
                        lambda _zone: (
                            datetime.now(UTC)
                            + (timedelta(hours=1) if sdk.calls else timedelta())
                        )
                    ),
                },
            ),
        )
    with pytest.raises((queue.QueueError, OSError)):
        run(f)
    assert sdk.calls == ["edit"]


def test_one_start_failure_cannot_be_run_again_after_spent_gui_intent(
    prepared: dict[str, Any],
) -> None:
    run(prepared)
    spent = prepared["store"].root / JOB / "f1-gui-edit" / "gui-intent.json"
    spent.write_text("spent original operation: status UNKNOWN")
    prepared["resolve"].current_page = "deliver"
    with pytest.raises(queue.QueueError, match="prior GUI intent"):
        run(prepared)
    assert prepared["resolve"].calls == ["edit"]
