"""M4 native tests never start Resolve or accept synthetic evidence as proof."""

from __future__ import annotations

import copy
import json
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import vera_timeline_agent.resolve_test_queue as queue
import vera_timeline_agent.resolve_test_queue_m4 as m4


def _target() -> dict[str, str]:
    name = f"VERA Delivery {uuid.uuid4()} {uuid.uuid4().hex[:12]}"
    return {
        "projectUid": uuid.uuid4().hex,
        "timelineUid": uuid.uuid4().hex,
        "projectName": name,
        "timelineName": name,
    }


def _plan() -> dict[str, Any]:
    return {
        "schema": m4.SCHEMA,
        "name": "reverse-312",
        "caseId": "synthetic-312",
        "baselineSession": {"path": "/host/baseline/session.json", "sha256": "a" * 64},
        "initialTarget": _target(),
        "freshTarget": _target(),
        "maxElapsedSeconds": 3600,
        "maxDiskBytes": 1024 * 1024,
    }


def _enroll(
    store: queue.Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, dict[str, Any]]:
    from vera_timeline_agent import qualification_output_controller_v2 as controller
    from vera_timeline_agent import qualification_output_native_v2 as native

    plan = m4.validate_plan(_plan())
    monkeypatch.setattr(
        controller,
        "load_output_session",
        lambda path, sha: SimpleNamespace(
            context={
                "phase": "pristine",
                "caseId": plan["caseId"],
                "target": plan["initialTarget"],
            }
        ),
    )
    monkeypatch.setattr(
        native,
        "native_request_paths",
        lambda context, seq: (tmp_path / "nonexistent-native-result",) * 4,
    )
    file = tmp_path / "m4-plan.json"
    file.write_bytes(queue.canonical(plan))
    job_id = m4.enqueue(store, file)
    monkeypatch.setattr(
        m4, "preflight_selected_disposable", lambda _target, *, require_empty: None
    )
    return job_id, plan


def _write_receipt(store: queue.Store, job_id: str, *, corrupt: bool = False) -> None:
    with store.connect() as db:
        stage = db.execute(
            "SELECT * FROM reverse_stages WHERE job_id=? AND state='awaiting_operator'",
            (job_id,),
        ).fetchone()
    assert stage is not None
    ref = {"path": "/private/host/result.json", "sha256": "b" * 64}
    receipt = {
        "schema": m4.RECEIPT_SCHEMA,
        "stage": stage["name"],
        "operationId": "bad-id" if corrupt else stage["operation_id"],
    }
    if stage["name"] == "revision":
        receipt["proof"] = ref
    else:
        receipt["session"] = ref
        receipt["capture"] = {"path": "/private/host/capture.json", "sha256": "c" * 64}
    queue.atomic_write(
        store.root / job_id / f"receipt-{stage['name']}.json",
        queue.canonical(receipt),
    )


@pytest.mark.parametrize(
    "edit",
    [
        lambda p: p.update(schema="old"),
        lambda p: p.update(extra="unreviewed"),
        lambda p: p.update(maxDiskBytes=1023),
        lambda p: p.update(maxElapsedSeconds=999999),
        lambda p: p["freshTarget"].update(projectUid=p["initialTarget"]["projectUid"]),
        lambda p: p["freshTarget"].update(
            projectName=p["initialTarget"]["projectName"]
        ),
        lambda p: p["initialTarget"].update(projectName="real producer project"),
        lambda p: p["baselineSession"].update(path="../../actual/media"),
        lambda p: p["baselineSession"].update(sha256="not-a-hash"),
        lambda p: p.update(caseId="../other"),
    ],
)
def test_closed_plan_refuses_unsafe_identities(
    edit: Callable[[dict[str, Any]], object],
) -> None:
    plan = _plan()
    edit(plan)
    with pytest.raises(queue.QueueError):
        m4.validate_plan(plan)


def test_queue_stages_are_one_use_and_end_only_after_four_authentications(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = queue.Store(tmp_path / "queue")
    job_id, _ = _enroll(store, tmp_path, monkeypatch)
    verified: list[int] = []

    def check(
        _store: queue.Store,
        _job: str,
        ordinal: int,
        _receipt: dict[str, Any],
        _intent_at: str,
    ) -> None:
        verified.append(ordinal)

    monkeypatch.setattr(m4, "_verify_stage", check)
    for index in range(4):
        assert m4.worker_tick(store) is True
        status = m4.publish(store, job_id)
        assert status["humanRequired"] is True
        assert status["stage"] == m4.STAGES[index]
        assert m4.worker_tick(store) is False
        _write_receipt(store, job_id)
        m4.submit(store, job_id)
        with pytest.raises(queue.QueueError, match="duplicate or uncertain"):
            m4.submit(store, job_id)
    assert verified == list(range(4))
    final = m4.publish(store, job_id)
    assert final["state"] == "completed_verified"
    assert final["readyFor312Phase2"] is True
    assert final["nativeVerified"] is True
    assert (store.root / job_id / "handoff-private.json").exists()
    assert m4.worker_tick(store) is False


def test_m4_uses_selected_real_uids_at_each_stage_not_m2_absent_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = queue.Store(tmp_path / "queue")
    job_id, plan = _enroll(store, tmp_path, monkeypatch)
    checks: list[tuple[dict[str, str], bool]] = []
    monkeypatch.setattr(
        m4,
        "preflight_selected_disposable",
        lambda target, *, require_empty: checks.append((target, require_empty)),
    )
    monkeypatch.setattr(m4, "_verify_stage", lambda *_: None)
    for _ in range(4):
        assert m4.worker_tick(store)
        _write_receipt(store, job_id)
        m4.submit(store, job_id)
    assert checks == [
        (plan["initialTarget"], True),
        (plan["initialTarget"], False),
        (plan["initialTarget"], False),
        (plan["freshTarget"], True),
    ]


def test_malformed_one_use_receipt_is_unknown_and_cannot_be_replaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = queue.Store(tmp_path / "queue")
    job_id, _ = _enroll(store, tmp_path, monkeypatch)
    assert m4.worker_tick(store)
    _write_receipt(store, job_id, corrupt=True)
    m4.submit(store, job_id)
    status = m4.publish(store, job_id)
    assert status["state"] == "unknown"
    assert status["readyFor312Phase2"] is False
    (store.root / job_id / "receipt-pristine.json").write_bytes(b"replaced\n")
    with pytest.raises(queue.QueueError):
        m4.submit(store, job_id)
    m4.reconcile(store, job_id)
    assert m4.publish(store, job_id)["state"] == "unknown"


def test_crash_rechecks_only_pinned_receipt_without_reissuing_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = queue.Store(tmp_path / "queue")
    job_id, _ = _enroll(store, tmp_path, monkeypatch)
    assert m4.worker_tick(store)
    _write_receipt(store, job_id)
    path = store.root / job_id / "receipt-pristine.json"
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "UPDATE reverse_stages SET state='verifying',receipt_path=?,receipt_sha=? "
            "WHERE job_id=? AND ordinal=0",
            (str(path), m4._sha(path.read_bytes()), job_id),
        )
        db.execute("UPDATE reverse_jobs SET state='verifying' WHERE id=?", (job_id,))
    checked: list[int] = []
    monkeypatch.setattr(m4, "_verify_stage", lambda *args: checked.append(args[2]))
    m4.reconcile(store, job_id)
    assert checked == [0]
    assert m4.publish(store, job_id)["state"] == "queued"
    m4.reconcile(store, job_id)
    assert checked == [0]


def test_tampering_after_durable_receipt_pin_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = queue.Store(tmp_path / "queue")
    job_id, _ = _enroll(store, tmp_path, monkeypatch)
    assert m4.worker_tick(store)
    _write_receipt(store, job_id)
    path = store.root / job_id / "receipt-pristine.json"
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "UPDATE reverse_stages SET state='verifying',receipt_path=?,receipt_sha=? "
            "WHERE job_id=? AND ordinal=0",
            (str(path), m4._sha(path.read_bytes()), job_id),
        )
    # A valid, canonical replacement must still fail before the downstream
    # verifier sees it. Malformed JSON would not prove the digest guard.
    receipt = json.loads(path.read_bytes())
    receipt["capture"]["sha256"] = "d" * 64
    path.write_bytes(queue.canonical(receipt))
    monkeypatch.setattr(m4, "_verify_stage", lambda *_: None)
    m4.reconcile(store, job_id)
    assert m4.publish(store, job_id)["state"] == "unknown"


def test_reverse_receipt_read_refuses_symlinks_and_hardlinks(
    tmp_path: Path,
) -> None:
    original = tmp_path / "receipt.json"
    original.write_bytes(b"safe\n")
    assert m4._read_bounded(original, limit=16) == b"safe\n"
    symlink = tmp_path / "receipt-link.json"
    symlink.symlink_to(original)
    with pytest.raises(queue.QueueError, match="symbolic-link"):
        m4._read_bounded(symlink, limit=16)
    hardlink = tmp_path / "receipt-hardlink.json"
    hardlink.hardlink_to(original)
    with pytest.raises(queue.QueueError, match="single-linked"):
        m4._read_bounded(hardlink, limit=16)


def test_native_slot_owner_remains_reserved_through_human_required_pause(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vera_timeline_agent.resolve_test_campaign as campaign

    store = queue.Store(tmp_path / "queue")
    job_id, plan = _enroll(store, tmp_path, monkeypatch)
    assert not m4.any_unresolved(store)
    assert m4.worker_tick(store)
    assert m4.any_unresolved(store)
    assert campaign._native_slot_busy(store)
    with store.connect() as db:
        assert m4.target_reserved(db, plan["initialTarget"]["projectName"])
    m4.cancel(store, job_id)
    assert m4.publish(store, job_id)["state"] == "unknown"
    assert m4.any_unresolved(store)


def test_pre_intent_cancellation_does_not_claim_native_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = queue.Store(tmp_path / "queue")
    job_id, _ = _enroll(store, tmp_path, monkeypatch)
    m4.cancel(store, job_id)
    assert m4.publish(store, job_id)["state"] == "canceled"
    assert m4.worker_tick(store) is False


def test_cancellation_during_read_only_preflight_cannot_create_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A simultaneous cancel wins even if it lands after worker selection."""
    store = queue.Store(tmp_path / "queue")
    job_id, _ = _enroll(store, tmp_path, monkeypatch)
    monkeypatch.setattr(
        m4,
        "preflight_selected_disposable",
        lambda _target, *, require_empty: m4.cancel(store, job_id),
    )
    m4.worker_tick(store)
    with store.connect() as db:
        stage = db.execute(
            "SELECT state,intent_at FROM reverse_stages WHERE job_id=? AND ordinal=0",
            (job_id,),
        ).fetchone()
    assert m4.publish(store, job_id)["state"] == "canceled"
    assert stage["state"] == "pending"
    assert stage["intent_at"] is None
    assert not m4.any_unresolved(store)


def test_actual_free_space_check_has_no_forty_gib_threshold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = queue.Store(tmp_path / "queue")
    job_id, plan = _enroll(store, tmp_path, monkeypatch)
    # Ten GiB is below the Producer's overridden 40-GiB threshold but above
    # the real budget reserved for this synthetic test plan.
    monkeypatch.setattr(
        shutil, "disk_usage", lambda _: SimpleNamespace(free=10 * 1024**3)
    )
    assert m4.worker_tick(store)
    assert m4.publish(store, job_id)["state"] == "awaiting_operator"
    assert plan["maxDiskBytes"] < 10 * 1024**3


def test_insufficient_actual_space_blocks_before_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = queue.Store(tmp_path / "queue")
    job_id, _ = _enroll(store, tmp_path, monkeypatch)
    monkeypatch.setattr(shutil, "disk_usage", lambda _: SimpleNamespace(free=1))
    assert m4.worker_tick(store)
    assert m4.publish(store, job_id)["state"] == "blocked"
    assert not m4.any_unresolved(store)


def test_unresolved_native_owner_blocks_without_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vera_timeline_agent.resolve_native_owner import NativeOwnerError

    store = queue.Store(tmp_path / "queue")
    job_id, _ = _enroll(store, tmp_path, monkeypatch)

    def blocked(_target: dict[str, str], *, require_empty: bool) -> None:
        raise NativeOwnerError("owner_busy", "private detail")

    monkeypatch.setattr(m4, "preflight_selected_disposable", blocked)
    assert m4.worker_tick(store)
    report = m4.publish(store, job_id)
    assert report["state"] == "blocked"
    assert "private detail" not in json.dumps(report)


def test_stage_receipt_requires_exact_canonical_pins(tmp_path: Path) -> None:
    ref = {"path": str(tmp_path / "ref.json"), "sha256": "a" * 64}
    proper = {
        "schema": m4.RECEIPT_SCHEMA,
        "stage": "revision",
        "operationId": "once",
        "proof": ref,
    }
    assert m4._parse_receipt(queue.canonical(proper), "revision", "once") == proper
    for wrong in (
        {**proper, "operationId": "replayed"},
        {**proper, "unapproved": True},
        {**proper, "proof": {**ref, "path": "../wrong"}},
    ):
        with pytest.raises(queue.QueueError):
            m4._parse_receipt(queue.canonical(wrong), "revision", "once")
    with pytest.raises(queue.QueueError):
        m4._parse_receipt(b'{"schema":1,"schema":2}\n', "revision", "once")


def test_wrong_target_context_cannot_count_as_native_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vera_timeline_agent import qualification_output_controller_v2 as controller

    target = _target()
    wrong = copy.deepcopy(target)
    wrong["timelineUid"] = "wrong"
    monkeypatch.setattr(
        controller,
        "load_output_session",
        lambda *_: SimpleNamespace(
            context={"phase": "pristine", "caseId": "case", "target": wrong}
        ),
    )
    receipt = {
        "session": {"path": str(tmp_path / "session"), "sha256": "a" * 64},
        "capture": {"path": str(tmp_path / "capture"), "sha256": "b" * 64},
    }
    with pytest.raises(queue.QueueError, match="context/UID"):
        m4._verified_output(
            receipt, "pristine", target, "case", queue.iso(queue.now_utc())
        )


def test_actual_native_rational_geometry_accepted_without_string_coercion() -> None:
    geometry: dict[str, Any] = {
        "rate": {"numerator": 24000, "denominator": 1001},
        "extentFrames": 1407,
        "items": [{} for _ in range(11)],
        "tracks": [{} for _ in range(6)],
    }
    m4._assert_qualified_output_geometry(geometry)
    for mutation in (
        {"rate": "24000/1001"},
        {"rate": {"numerator": 24, "denominator": 1}},
        {"rate": {"numerator": 24000, "denominator": 1001, "extra": 1}},
        {"extentFrames": True},
        {"extentFrames": 1406},
        {"items": geometry["items"][:-1]},
        {"tracks": geometry["tracks"][:-1]},
    ):
        changed = {**geometry, **mutation}
        with pytest.raises(queue.QueueError, match="qualified native"):
            m4._assert_qualified_output_geometry(changed)


def test_accepted_revision_must_bind_both_pinned_sessions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vera_timeline_agent import qualification_output_proof_v2 as output_proof

    initial = _target()
    pristine = {"session": {"path": "/host/pristine", "sha256": "a" * 64}}
    edited = {"session": {"path": "/host/edited", "sha256": "b" * 64}}
    proof_ref = {"path": "/host/proof", "sha256": "c" * 64}
    proof = SimpleNamespace(
        session={
            "baselineSession": pristine["session"],
            "editedSession": edited["session"],
        },
        baseline=SimpleNamespace(context={"target": initial}),
        edited=SimpleNamespace(context={"target": initial}),
        accepted_revision=lambda: ({"outcome": "accept"}, {}),
    )
    monkeypatch.setattr(output_proof, "QualificationOutputProofV2", lambda *_: proof)
    monkeypatch.setattr(m4, "_load_plan", lambda *_: {"initialTarget": initial})
    monkeypatch.setattr(m4, "_stage_receipt", lambda _, __, n: (pristine, edited)[n])
    receipt = {"proof": proof_ref}
    m4._verify_stage(queue.Store(tmp_path / "queue"), "unused", 2, receipt, "now")
    proof.session["editedSession"] = {"path": "/host/unrelated", "sha256": "b" * 64}
    with pytest.raises(queue.QueueError, match="accepted inferred revision"):
        m4._verify_stage(queue.Store(tmp_path / "queue"), "unused", 2, receipt, "now")


def test_success_cannot_be_claimed_without_host_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = queue.Store(tmp_path / "queue")
    job_id, _ = _enroll(store, tmp_path, monkeypatch)
    assert m4.worker_tick(store)
    _write_receipt(store, job_id)
    # The input is syntactically valid, but contains fabricated host locators.
    m4.submit(store, job_id)
    assert m4.publish(store, job_id)["nativeVerified"] is False
    assert m4.publish(store, job_id)["state"] == "unknown"
