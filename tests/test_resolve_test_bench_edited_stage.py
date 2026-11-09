"""Mock-only F1 -> original M4 edited native-host continuation regressions."""

from __future__ import annotations

import copy
import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import resolve_gui_roll as gui
from vera_timeline_agent import resolve_native_owner as owner
from vera_timeline_agent import resolve_test_bench_campaign as campaign
from vera_timeline_agent import resolve_test_bench_carrier as carrier
from vera_timeline_agent import resolve_test_bench_edited_stage as edited
from vera_timeline_agent import resolve_test_bench_m4_runner as runner
from vera_timeline_agent import resolve_test_bench_output as output
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import resolve_test_queue_m4 as m4
from vera_timeline_agent import workflow_v2_cli as workflow


def _geometry(phase: str = "pristine") -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for i in range(11):
        items.append(
            {
                "itemUid": f"item-{i}",
                "kind": "video" if i < 5 else "audio",
                "trackId": "V1" if i < 2 else f"track-{i % 6}",
                "eventId": f"event-{i}",
                "mediaUid": f"media-{i}",
                "sourceId": f"source-{i}",
                "sourceStart": 0,
                "sourceDuration": 327 if i == 0 else 151 if i == 1 else 100,
                "recordStart": 0 if i == 0 else 327 if i == 1 else 600 + i * 20,
                "recordDuration": 327 if i == 0 else 151 if i == 1 else 100,
                "linkedItemUids": [],
            }
        )
    return {
        "context": {"target": TARGET, "phase": phase},
        "rate": {"numerator": 24000, "denominator": 1001},
        "extentFrames": 1407,
        "tracks": [{"trackId": f"track-{i}"} for i in range(6)],
        "sourceMappings": [{"sourceId": f"source-{i}"} for i in range(11)],
        "items": items,
    }


def _changed(before: dict[str, Any]) -> dict[str, Any]:
    after = copy.deepcopy(before)
    after["context"]["phase"] = "edited"
    after["items"][0]["recordDuration"] += 24
    after["items"][0]["sourceDuration"] += 24
    after["items"][1]["recordStart"] += 24
    after["items"][1]["recordDuration"] -= 24
    after["items"][1]["sourceDuration"] -= 24
    return after


NAME = "VERA Delivery 123e4567-e89b-12d3-a456-426614174000 012345abcdef"
TARGET = {
    "projectUid": "pristine-project",
    "projectName": NAME,
    "timelineUid": "pristine-timeline",
    "timelineName": NAME,
}
REF = {"path": "/signed/pristine.json", "sha256": "a" * 64}
SESSION = {"path": "/signed/edited.json", "sha256": "b" * 64}
CAPTURE = {"path": "/signed/capture.json", "sha256": "c" * 64}
JOB = "resolve-reverse-" + "f" * 32
OPERATION = "original-edited-operation"


class Store:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir()
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute(
            "CREATE TABLE reverse_jobs (id TEXT, state TEXT, "
            "started_at TEXT, deadline_at REAL)"
        )
        self.db.execute(
            "CREATE TABLE reverse_stages (job_id TEXT, ordinal INTEGER, name TEXT, "
            "state TEXT, operation_id TEXT, intent_at TEXT, receipt_sha TEXT)"
        )

    def connect(self) -> sqlite3.Connection:
        return self.db


@pytest.fixture
def evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    store = Store(tmp_path / "queue")
    current = queue.now_utc()
    start = queue.iso(current)
    deadline = queue.iso(current + timedelta(hours=2))
    plan = {
        "caseId": "synthetic-312",
        "baselineSession": REF,
        "initialTarget": TARGET,
        "freshTarget": {**TARGET, "projectUid": "new", "timelineUid": "new-timeline"},
        "maxElapsedSeconds": 7200,
        "maxDiskBytes": 1048576,
        "runAt": start,
        "deadlineAt": deadline,
    }
    store.db.execute(
        "INSERT INTO reverse_jobs VALUES (?,?,?,?)",
        (JOB, "awaiting_operator", start, queue.dt(deadline).timestamp()),
    )
    for ordinal, name in enumerate(m4.STAGES):
        store.db.execute(
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
                "pristine-op" if ordinal == 0 else OPERATION,
                start if ordinal <= 1 else None,
                "signed" if ordinal == 0 else None,
            ),
        )
    monkeypatch.setattr(m4, "_load_plan", lambda *_: plan)
    monkeypatch.setattr(
        m4, "_stage_receipt", lambda *_: {"session": REF, "capture": REF}
    )
    monkeypatch.setattr(m4, "_jobdir", lambda *_: store.root / JOB)
    monkeypatch.setattr(gui, "_require_owner_lock", lambda: None)
    monkeypatch.setattr(
        edited,
        "verify_native_result",
        lambda *_: {
            "status": "complete",
            "action": "capture_post",
            "target": TARGET,
            "nativeGeometry": _geometry(),
        },
    )
    # The original F1 journal already exists before this host ever starts.
    root = store.root / JOB / "f1-gui-edit"
    carrier._private(root, create=True)
    intent = {
        "schema": "vera.issue473-one-use-f1-gui/v1",
        "jobId": JOB,
        "operationId": OPERATION,
        "actuatorClass": gui.ACTUATOR_CLASS,
        "target": TARGET,
        "scriptSha256": gui.ROLL_SCRIPT_SHA256,
        "captureSha256": REF["sha256"],
        "itemUids": [f"item-{i}" for i in range(11)],
        "expiresAt": queue.iso(current + timedelta(minutes=4)),
        "m4DeadlineAt": deadline,
        "m4PlanSha256": hashlib.sha256(queue.canonical(plan)).hexdigest(),
    }
    carrier._once(root / "gui-intent.json", queue.canonical(intent))
    return {"store": store, "plan": plan, "intent": intent, "root": root}


def test_consumed_f1_is_not_evidence_of_success(evidence: dict[str, Any]) -> None:
    store = evidence["store"]
    deadline, operation = edited._deadline(store, JOB, evidence["plan"])
    assert deadline > queue.now_utc().timestamp()
    pristine, original = edited._consumed_gui(store, JOB, evidence["plan"], operation)
    assert pristine["capture"] == REF
    assert original["nativeGeometry"]["items"][0]["recordDuration"] == 327


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("operationId", "other-operation"),
        ("scriptSha256", "0" * 64),
        ("captureSha256", "0" * 64),
        ("itemUids", [f"replacement-{i}" for i in range(11)]),
        ("m4DeadlineAt", "2999-01-01T00:00:00Z"),
        ("m4PlanSha256", "0" * 64),
        ("target", {**TARGET, "projectUid": "wrong"}),
    ],
)
def test_journal_wrong_identity_refused(
    evidence: dict[str, Any], field: str, replacement: Any
) -> None:
    (evidence["root"] / "gui-intent.json").write_bytes(
        queue.canonical({**evidence["intent"], field: replacement})
    )
    with pytest.raises(queue.QueueError, match=r"GUI journal|extends original|UID set"):
        edited._consumed_gui(evidence["store"], JOB, evidence["plan"], OPERATION)


@pytest.mark.parametrize("state", ["pending", "verified", "unknown"])
def test_only_awaiting_original_stage_can_proceed(
    evidence: dict[str, Any], state: str
) -> None:
    evidence["store"].db.execute(
        "UPDATE reverse_stages SET state=? WHERE ordinal=1", (state,)
    )
    with pytest.raises(queue.QueueError, match="not awaiting"):
        edited._deadline(evidence["store"], JOB, evidence["plan"])


def test_source_freeze_or_uid_loss_cannot_start_host(
    evidence: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        edited,
        "verify_native_result",
        lambda *_: {
            "status": "complete",
            "action": "capture_post",
            "target": TARGET,
            "nativeGeometry": {**_geometry(), "items": _geometry()["items"][:-1]},
        },
    )
    with pytest.raises(queue.QueueError, match="UID set"):
        edited._consumed_gui(evidence["store"], JOB, evidence["plan"], OPERATION)


@pytest.mark.parametrize(
    "mutation",
    [
        "uid",
        "extra",
        "source",
        "audio",
        "links",
        "track",
        "source_in",
        "extent",
        "boundary",
    ],
)
def test_independent_host_geometry_rejects_false_edited_proof(
    evidence: dict[str, Any], monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    before = _geometry()
    after = _changed(before)
    if mutation == "uid":
        after["items"][0]["itemUid"] = "replacement"
    elif mutation == "extra":
        after["items"].append(copy.deepcopy(after["items"][0]))
    elif mutation == "source":
        after["sourceMappings"] = []
    elif mutation == "audio":
        after["items"][7]["recordDuration"] += 1
    elif mutation == "links":
        after["items"][0]["linkedItemUids"] = ["item-1"]
    elif mutation == "track":
        after["tracks"][0]["trackId"] = "wrong"
    elif mutation == "source_in":
        after["items"][1]["sourceStart"] += 24
    elif mutation == "extent":
        after["extentFrames"] = 1406
    elif mutation == "boundary":
        after["items"][0]["recordDuration"] = 350
    monkeypatch.setattr(m4, "_intent", lambda *_: "durable-original-stage-intent")
    monkeypatch.setattr(
        m4,
        "_verified_output",
        lambda _receipt, phase, *_: (
            None,
            {"nativeGeometry": before if phase == "pristine" else after},
        ),
    )
    with pytest.raises((ValueError, queue.QueueError)):
        edited._prove_edited(
            evidence["store"],
            JOB,
            evidence["plan"],
            {"session": REF, "capture": REF},
            {"nativeGeometry": before},
            SESSION,
            CAPTURE,
        )


def test_same_uids_and_only_327_to_351_pass_signed_geometry(
    evidence: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _geometry()
    after = _changed(before)
    monkeypatch.setattr(m4, "_intent", lambda *_: "durable-original-stage-intent")
    monkeypatch.setattr(
        m4,
        "_verified_output",
        lambda _receipt, phase, *_: (
            None,
            {"nativeGeometry": before if phase == "pristine" else after},
        ),
    )
    edited._prove_edited(
        evidence["store"],
        JOB,
        evidence["plan"],
        {"session": REF, "capture": REF},
        {"nativeGeometry": before},
        SESSION,
        CAPTURE,
    )


def test_continuation_refuses_inherited_gui_owner_before_native_preflight(
    evidence: dict[str, Any], tmp_path: Path
) -> None:
    token = owner._HELD_OWNER_FD.set(42)
    try:
        with pytest.raises(queue.QueueError, match="GUI owner must be released"):
            edited.continue_from_session(
                evidence["store"],
                JOB,
                session=SESSION,
                stage_root=tmp_path / "unstarted-host",
                consent_reference="case-specific approval",
                consent_instruction="one new sacrificial edit",
            )
    finally:
        owner._HELD_OWNER_FD.reset(token)
    assert not (tmp_path / "unstarted-host").exists()


@pytest.mark.parametrize(
    "host_state", ["unknown", "partial", "terminal_native_verified"]
)
def test_no_original_m4_receipt_without_true_terminal_and_independent_proof(
    evidence: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    host_state: str,
) -> None:
    store = evidence["store"]
    admitted = SimpleNamespace(package_root=tmp_path / "package", profile="studio")
    controller = SimpleNamespace(
        context={"phase": "edited", "caseId": "synthetic-312", "target": TARGET},
        release_root=tmp_path / "release",
        admission=admitted,
    )
    monkeypatch.setattr(output, "_session", lambda path, sha: controller)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("trusted-manifest")
    monkeypatch.setattr(workflow, "_verify_output_release", lambda path: manifest)
    calls: list[str] = []
    held = False

    @contextmanager
    def fake_owner(*, output_lane: bool = False) -> Any:
        nonlocal held
        assert output_lane
        assert not held
        held = True
        try:
            yield 42
        finally:
            held = False

    monkeypatch.setattr(owner, "native_owner", fake_owner)

    def fake_host(_plan: dict[str, Any]) -> dict[str, Any]:
        assert not held  # carrier's own preflight must never self-deadlock
        calls.append("host")
        return {
            "state": host_state,
            "verified": host_state == "terminal_native_verified",
            "session": SESSION,
            "capture": CAPTURE,
        }

    monkeypatch.setattr(campaign, "start", fake_host)
    monkeypatch.setattr(runner, "_submit_original", lambda *_: calls.append("receipt"))
    monkeypatch.setattr(
        m4, "publish", lambda *_: {"stages": [{"name": "edited", "state": "verified"}]}
    )

    # Terminal alone is insufficient. Must independently reverify signed SDK
    # source, exact 11 UIDs, the boundary and the full MOV/PCM lineage.
    def bad_proof(*_args: Any) -> None:
        calls.append("proof")
        raise queue.QueueError("fake render rejected")

    monkeypatch.setattr(edited, "_prove_edited", bad_proof)
    with pytest.raises(queue.QueueError):
        edited.continue_from_session(
            store,
            JOB,
            session=SESSION,
            stage_root=tmp_path / "edited-stage",
            consent_reference="new case-specific Producer authority",
            consent_instruction="one new sacrificial GUI edit and native verification",
        )
    assert calls == (
        ["host", "proof"] if host_state == "terminal_native_verified" else ["host"]
    )
    assert "receipt" not in calls


def test_signed_host_and_exact_boundary_promote_one_original_edited_receipt(
    evidence: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = evidence["store"]
    admitted = SimpleNamespace(package_root=tmp_path / "package", profile="studio")
    controller = SimpleNamespace(
        context={"phase": "edited", "caseId": "synthetic-312", "target": TARGET},
        release_root=tmp_path / "release",
        admission=admitted,
    )
    monkeypatch.setattr(output, "_session", lambda *_: controller)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("pinned installed release")
    monkeypatch.setattr(workflow, "_verify_output_release", lambda *_: manifest)
    events: list[str] = []

    @contextmanager
    def fake_owner(*, output_lane: bool = False) -> Any:
        assert output_lane
        events.append("owner acquired")
        try:
            yield 42
        finally:
            events.append("owner released")

    monkeypatch.setattr(owner, "native_owner", fake_owner)
    before = _geometry()
    after = _changed(before)
    monkeypatch.setattr(m4, "_intent", lambda *_: "durable-original-intent")

    def verified_host(
        _receipt: dict[str, Any], phase: str, *_args: Any
    ) -> tuple[None, dict[str, Any]]:
        events.append(f"authentic {phase} and MOV/PCM")
        return None, {"nativeGeometry": before if phase == "pristine" else after}

    monkeypatch.setattr(m4, "_verified_output", verified_host)

    def fake_native_chain(launch: dict[str, Any]) -> dict[str, Any]:
        assert events[-1] == "owner released"
        assert launch["deadlineUnix"] > queue.now_utc().timestamp()
        assert launch["phase"] == "edited" and launch["target"] == TARGET
        events.append("official SDK observe/save/reopen/render/PCM")
        return {
            "state": "terminal_native_verified",
            "verified": True,
            "session": SESSION,
            "capture": CAPTURE,
        }

    monkeypatch.setattr(campaign, "start", fake_native_chain)

    def signed_receipt(
        _store: Any, _job: str, stage: str, result: dict[str, Any]
    ) -> None:
        assert stage == "edited" and _job == JOB
        assert result == {"session": SESSION, "capture": CAPTURE}
        events.append("original immutable M4 edited receipt")

    monkeypatch.setattr(runner, "_submit_original", signed_receipt)
    monkeypatch.setattr(
        m4,
        "publish",
        lambda *_: {"stages": [{"name": "edited", "state": "verified"}]},
    )
    result = edited.continue_from_session(
        store,
        JOB,
        session=SESSION,
        stage_root=tmp_path / "edited-stage",
        consent_reference="fresh exact authority",
        consent_instruction="fresh edited trial",
    )
    assert result["state"] == "original_M4_edited_verified"
    assert result["operationId"] == OPERATION
    assert events == [
        "owner acquired",
        "owner released",
        "official SDK observe/save/reopen/render/PCM",
        "authentic pristine and MOV/PCM",
        "authentic edited and MOV/PCM",
        "original immutable M4 edited receipt",
    ]


def test_missing_gui_journal_never_creates_native_stage(
    evidence: dict[str, Any],
) -> None:
    (evidence["root"] / "gui-intent.json").rename(evidence["root"] / "elsewhere.json")
    with pytest.raises((ValueError, OSError)):
        edited._consumed_gui(evidence["store"], JOB, evidence["plan"], OPERATION)
