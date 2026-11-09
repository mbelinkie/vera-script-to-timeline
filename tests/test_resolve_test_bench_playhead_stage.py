"""Mock-only official SDK 327 playhead navigation after original M4 pristine."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import resolve_test_bench_playhead_stage as playhead
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import resolve_test_queue_m4 as m4

INITIAL = {
    "projectUid": "uid-initial-project",
    "timelineUid": "uid-initial-timeline",
    "projectName": "VERA Delivery original-sacrificial-only",
    "timelineName": "VERA Delivery original-sacrificial-only",
}
FRESH = {
    "projectUid": "uid-fresh-project",
    "timelineUid": "uid-fresh-timeline",
    "projectName": "VERA Delivery different-sacrificial-only",
    "timelineName": "VERA Delivery different-sacrificial-only",
}
JOB = "resolve-reverse-" + "b" * 32
PRISTINE = {"path": "/fake/pristine-session", "sha256": "a" * 64}
CAPTURE = {"path": "/fake/signed-capture", "sha256": "b" * 64}


class FakeTimeline:
    def __init__(self) -> None:
        self.start = "00:00:00:00"
        self.current = self.start
        self.setter_calls: list[str] = []
        self.admit_setter = True
        self.admit_readback = True

    def GetCurrentTimecode(self) -> str:
        return self.current

    def GetStartTimecode(self) -> str:
        return self.start

    def GetStartFrame(self) -> int:
        return 0

    def GetName(self) -> str:
        return INITIAL["timelineName"]

    def GetUniqueId(self) -> str:
        return INITIAL["timelineUid"]

    def SetCurrentTimecode(self, value: str) -> bool:
        self.setter_calls.append(value)
        if self.admit_readback:
            self.current = value
        return self.admit_setter


@pytest.fixture
def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE reverse_jobs (id TEXT, state TEXT)")
    db.execute(
        "CREATE TABLE reverse_stages (job_id TEXT, ordinal INTEGER, state TEXT, "
        "receipt_sha TEXT, intent_at TEXT)"
    )
    db.execute("INSERT INTO reverse_jobs VALUES (?, 'awaiting_operator')", (JOB,))
    for ordinal in range(4):
        db.execute(
            "INSERT INTO reverse_stages VALUES (?,?,?,?,?)",
            (
                JOB,
                ordinal,
                "verified"
                if ordinal == 0
                else "awaiting_operator"
                if ordinal == 1
                else "pending",
                "c" * 64 if ordinal == 0 else None,
                "2026-11-08T00:00:00Z" if ordinal == 1 else None,
            ),
        )

    @contextmanager
    def connect() -> Iterator[sqlite3.Connection]:
        yield db

    store = SimpleNamespace(connect=connect)
    plan = {
        "caseId": "synthetic-312",
        "initialTarget": INITIAL,
        "freshTarget": FRESH,
        "baselineSession": PRISTINE,
    }
    monkeypatch.setattr(m4, "_load_plan", lambda *_: plan)
    monkeypatch.setattr(
        m4, "_stage_receipt", lambda *_: {"session": PRISTINE, "capture": CAPTURE}
    )
    monkeypatch.setattr(playhead.roll, "_require_owner_lock", lambda: None)
    session = SimpleNamespace(
        context={"phase": "pristine", "target": INITIAL, "caseId": "synthetic-312"}
    )
    monkeypatch.setattr(playhead, "load_output_session", lambda *_: session)
    monkeypatch.setattr(
        playhead, "_load_terminal_output_with_comparison", lambda *_: object()
    )
    monkeypatch.setattr(
        playhead,
        "verify_native_result",
        lambda *_: {
            "status": "complete",
            "action": "capture_post",
            "context": session.context,
            "target": INITIAL,
            "nativeGeometry": {"signed": "native-11-UID inventory"},
        },
    )
    inspections: list[dict[str, Any]] = []

    def inspect(
        _resolve: Any, _target: Any, geometry: dict[str, Any]
    ) -> dict[str, Any]:
        inspections.append(geometry)
        return {
            "disposition": "read_only_no_edit_authorized",
            "resolveVersion": [21, 1, 1, 10, ""],
            "geometry": geometry,
        }

    monkeypatch.setattr(playhead, "inspect_selected", inspect)
    timeline = FakeTimeline()
    project = SimpleNamespace(
        GetUniqueId=lambda: INITIAL["projectUid"],
        GetName=lambda: INITIAL["projectName"],
        GetCurrentTimeline=lambda: timeline,
        IsRenderingInProgress=lambda: False,
    )
    resolve = SimpleNamespace(
        GetProjectManager=lambda: SimpleNamespace(GetCurrentProject=lambda: project)
    )
    return {
        "db": db,
        "store": store,
        "timeline": timeline,
        "project": project,
        "resolve": resolve,
        "inspections": inspections,
        "plan": plan,
    }


@pytest.mark.parametrize("start", ["00:00:00:00", "01:00:00:00"])
def test_bounded_sdk_navigation_only_on_authenticated_original_target(
    fake: dict[str, Any],
    start: str,
) -> None:
    timeline = fake["timeline"]
    timeline.start = start
    timeline.current = start
    playhead.position_owned_327(fake["store"], JOB, fake["resolve"])
    assert timeline.setter_calls == [
        "00:00:13:15" if start == "00:00:00:00" else "01:00:13:15"
    ]
    assert timeline.current == timeline.setter_calls[0]
    assert len(fake["inspections"]) == 2
    assert fake["inspections"][0] == fake["inspections"][1]


def test_already_on_boundary_does_not_repeat_navigation(fake: dict[str, Any]) -> None:
    timeline = fake["timeline"]
    timeline.current = "00:00:13:15"
    playhead.position_owned_327(fake["store"], JOB, fake["resolve"])
    assert timeline.setter_calls == []


@pytest.mark.parametrize(
    "mutate",
    [
        "unknown_state",
        "no_original_intent",
        "unverified_pristine",
        "unexpected_next",
        "wrong_baseline",
        "wrong_sdk",
        "wrong_target",
        "wrong_native_capture",
        "stale_graph",
        "setter_failed",
        "setter_no_readback",
        "geometry_drift",
        "invalid_tc",
        "timecode_overflow",
    ],
)
def test_refuses_unsafe_navigation_and_never_claims_edit_receipt(
    fake: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    mutate: str,
) -> None:
    fixture = fake
    db = fixture["db"]
    timeline = fixture["timeline"]
    if mutate == "unknown_state":
        db.execute("UPDATE reverse_jobs SET state='unknown' WHERE id=?", (JOB,))
    elif mutate == "no_original_intent":
        db.execute("UPDATE reverse_stages SET intent_at=NULL WHERE ordinal=1")
    elif mutate == "unverified_pristine":
        db.execute("UPDATE reverse_stages SET state='unknown' WHERE ordinal=0")
    elif mutate == "unexpected_next":
        db.execute(
            "UPDATE reverse_stages SET state='awaiting_operator' WHERE ordinal=2"
        )
    elif mutate == "wrong_baseline":
        fixture["plan"]["baselineSession"] = {"path": "swapped", "sha256": "c" * 64}
    elif mutate == "wrong_sdk":
        monkeypatch.setattr(
            playhead,
            "inspect_selected",
            lambda *_: {
                "disposition": "read_only_no_edit_authorized",
                "resolveVersion": [21, 1, 2, 10, ""],
            },
        )
    elif mutate == "wrong_target":
        fixture["project"].GetUniqueId = lambda: FRESH["projectUid"]
    elif mutate == "wrong_native_capture":
        monkeypatch.setattr(
            playhead,
            "verify_native_result",
            lambda *_: {
                "status": "UNKNOWN",
                "action": "capture_post",
                "target": INITIAL,
                "nativeGeometry": {},
            },
        )
    elif mutate == "stale_graph":
        monkeypatch.setattr(
            playhead,
            "load_output_session",
            lambda *_: (_ for _ in ()).throw(ValueError("source graph changed")),
        )
    elif mutate == "setter_failed":
        timeline.admit_setter = False
    elif mutate == "setter_no_readback":
        timeline.admit_readback = False
    elif mutate == "geometry_drift":
        observations = [0]

        def drifting(*_: Any) -> dict[str, Any]:
            observations[0] += 1
            return {
                "disposition": "read_only_no_edit_authorized",
                "resolveVersion": [21, 1, 1, 10, ""],
                "geometry": observations[0],
            }

        monkeypatch.setattr(playhead, "inspect_selected", drifting)
    elif mutate == "invalid_tc":
        timeline.start = "00:00:00;00"
    elif mutate == "timecode_overflow":
        timeline.start = "23:59:59:23"
        timeline.current = timeline.start
    with pytest.raises((queue.QueueError, ValueError)):
        playhead.position_owned_327(fixture["store"], JOB, fixture["resolve"])
    if mutate not in {"setter_failed", "setter_no_readback", "geometry_drift"}:
        assert timeline.setter_calls == []


@pytest.mark.parametrize("tc", ["00:00:00;00", "abc", "00:00:00:24", "24:00:00:00", -1])
def test_strict_no_drop_timecode_parse_refuses_guess(tc: Any) -> None:
    with pytest.raises(queue.QueueError):
        playhead._frames(tc)
