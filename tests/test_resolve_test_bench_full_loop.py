"""Injected four-stage Conductor owner, freeze, negative and replay tests.

No native SDK, GUI, user permission, Resolve project, or Provider service is
invoked. The companion revision-stage suite exercises REAL M4 SQLite writes.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from _actor_pin import actor_pin
from vera_timeline_agent import resolve_gui_roll as native_roll
from vera_timeline_agent import resolve_test_bench_carrier as carrier
from vera_timeline_agent import resolve_test_bench_edited_stage as edited
from vera_timeline_agent import resolve_test_bench_full_loop as loop
from vera_timeline_agent import resolve_test_bench_gui_stage as gui
from vera_timeline_agent import resolve_test_bench_helper_stage as helper_stage
from vera_timeline_agent import resolve_test_bench_helper_transport as helper_transport
from vera_timeline_agent import resolve_test_bench_m4_runner as runner
from vera_timeline_agent import resolve_test_bench_page_stage as page
from vera_timeline_agent import resolve_test_bench_playhead_stage as playhead
from vera_timeline_agent import resolve_test_bench_revision_stage as revision
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import resolve_test_queue_m4 as m4
from vera_timeline_agent import resolve_test_queue_m4_provision as provision

FROZEN = "c" * 40
SOURCE_GRAPH = "d" * 64
ORIGINAL_JOB = "resolve-reverse-" + "1" * 32


def _target(name: str, uid: str) -> dict[str, str]:
    return {
        "projectUid": f"project-{uid}",
        "timelineUid": f"timeline-{uid}",
        "projectName": name,
        "timelineName": name,
    }


@pytest.fixture
def prepared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    root = tmp_path / "fresh-rehearsal"
    root.mkdir(mode=0o700)
    first = _target(
        "VERA Delivery 123e4567-e89b-12d3-a456-426614174000 012345abcdef", "original"
    )
    second = _target(
        "VERA Delivery 123e4567-e89b-12d3-a456-426614174001 012345abcdee", "fresh"
    )
    targets = {"initial": first, "fresh": second}
    monkeypatch.setattr(provision, "completed", lambda *_: targets)
    monkeypatch.setattr(loop, "_frozen_source", lambda *_: SOURCE_GRAPH)
    config = runner.validate_config(
        {
            "schema": runner.SCHEMA,
            "root": str(root),
            "queueRoot": str(root / "queue"),
            "name": "new-312-sacrificial",
            "caseId": "synthetic-312",
            "packageRoot": str(tmp_path / "source-package"),
            "narrationEvidenceRoot": str(tmp_path / "narration-evidence"),
            "profile": "qualification-output-studio-matrix/v1",
            "maxElapsedSeconds": 7200,
            "maxDiskBytes": 1048576,
            "consentReference": "actual-new-producer-message-ref",
            "consentInstruction": (
                "Actual producer explicitly approved unique new one-use trial"
            ),
            "merged472Commit": "a" * 40,
        }
    )
    config_path = root / "config.json"
    carrier._once(config_path, queue.canonical(config))
    auth = {
        "schema": loop.AUTHORITY_SCHEMA,
        "caseId": config["caseId"],
        "configSha256": hashlib.sha256(queue.canonical(config)).hexdigest(),
        "frozenCommit": FROZEN,
        "sourceGraphSha256": SOURCE_GRAPH,
        "approvalReference": config["consentReference"],
        "approvalInstruction": config["consentInstruction"],
        "issuedAt": datetime.now(UTC).isoformat(),
        "expiresAt": (datetime.now(UTC) + timedelta(minutes=15)).isoformat(),
        "initialTarget": first,
        "freshTarget": second,
        "operation": "M4.edited.one-use-gui-roll",
        "fromFrame": 327,
        "toFrame": 351,
        "actorPin": actor_pin(),
        "authorizationBasis": "standing-producer-instruction",
        "authorityIssuedBy": "VERA Conductor",
    }
    auth_path = root / "producer-approval.json"
    carrier._once(auth_path, queue.canonical(auth))
    return {
        "root": root,
        "config": config,
        "config_path": config_path,
        "authority": auth,
        "auth_path": auth_path,
        "targets": targets,
    }


@pytest.mark.parametrize(
    "change",
    [
        "frozenCommit",
        "sourceGraphSha256",
        "configSha256",
        "approvalReference",
        "approvalInstruction",
        "issuedAt",
        "expiresAt",
        "caseId",
        "operation",
        "fromFrame",
        "toFrame",
        "actorPin",
        "authorizationBasis",
        "authorityIssuedBy",
        "initialTarget",
        "freshTarget",
        "newField",
    ],
)
def test_new_authority_is_exactly_bound_before_first_native_effect(
    prepared: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    fixture = prepared
    auth = copy.deepcopy(fixture["authority"])
    if change in {"initialTarget", "freshTarget"}:
        auth[change]["projectUid"] = "historical-project"
    elif change == "newField":
        auth[change] = "bypass"
    elif change == "toFrame":
        auth[change] = 352
    elif change == "fromFrame":
        auth[change] = 326
    else:
        auth[change] = "tampered"
    # The new authorization is immutable once issued. Test the *proposed*
    # mutated document before persisting an effect rather than overwrite one.
    with pytest.raises(
        queue.QueueError,
        match=r"authority|authorization|source|target|Producer|native|config|GUI",
    ):
        loop._authority(queue.canonical(auth), fixture["config"], FROZEN, SOURCE_GRAPH)
    assert not (fixture["root"] / "complete-loop-intent.json").exists()


def test_noncanonical_or_truncated_authority_is_not_a_signature(
    prepared: dict[str, Any],
) -> None:
    fixture = prepared
    auth = copy.deepcopy(fixture["authority"])
    raw = json.dumps(auth).encode()  # not canonical
    with pytest.raises(queue.QueueError, match="canonical"):
        loop._authority(raw, fixture["config"], FROZEN, SOURCE_GRAPH)
    with pytest.raises(queue.QueueError, match="not JSON"):
        loop._authority(b"{", fixture["config"], FROZEN, SOURCE_GRAPH)


@pytest.mark.parametrize("invalid", ["expired", "future", "too_long", "old_491"])
def test_503_d_old_or_recycled_authority_never_starts_native(
    prepared: dict[str, Any], invalid: str
) -> None:
    authority = copy.deepcopy(prepared["authority"])
    now = datetime.now(UTC)
    if invalid == "expired":
        authority["issuedAt"] = (now - timedelta(hours=2)).isoformat()
        authority["expiresAt"] = (now - timedelta(hours=1)).isoformat()
    elif invalid == "future":
        authority["issuedAt"] = (now + timedelta(minutes=2)).isoformat()
        authority["expiresAt"] = (now + timedelta(minutes=12)).isoformat()
    elif invalid == "too_long":
        authority["expiresAt"] = (now + timedelta(hours=3)).isoformat()
    else:
        config = {**prepared["config"], "consentReference": "issue-491"}
        authority["approvalReference"] = config["consentReference"]
        authority["configSha256"] = hashlib.sha256(queue.canonical(config)).hexdigest()
        with pytest.raises(queue.QueueError, match="491"):
            loop._authority(queue.canonical(authority), config, FROZEN, SOURCE_GRAPH)
        return
    with pytest.raises(queue.QueueError, match="authorization"):
        loop._authority(
            queue.canonical(authority), prepared["config"], FROZEN, SOURCE_GRAPH
        )
    assert not (prepared["root"] / "complete-loop-intent.json").exists()


def _assert_test_actor(job: str, actor: object, fixture: dict[str, Any]) -> None:
    """Stub only the persistent queue in otherwise synthetic orchestration."""
    assert job == ORIGINAL_JOB
    assert actor == fixture["authority"]["actorPin"]


def test_full_one_start_fake_injected_four_stage_host_single_owner_and_no_replay(
    prepared: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = prepared
    events: list[str] = []
    lock_held = [False]

    def fake_pristine(config: dict[str, Any]) -> dict[str, Any]:
        assert not lock_held[0]
        assert config == fixture["config"]
        events.append("pristine:verified")
        return {
            "state": "blocked_unattended_native_roll_edit_not_proven",
            "jobId": ORIGINAL_JOB,
        }

    actor_seals: list[tuple[str, object]] = []

    def seal_actor(_store: Any, job: str, actor: object) -> None:
        assert job == ORIGINAL_JOB and actor == fixture["authority"]["actorPin"]
        actor_seals.append((job, actor))

    monkeypatch.setattr(gui, "seal_case_actor_pin", seal_actor)
    monkeypatch.setattr(runner, "start", fake_pristine)
    monkeypatch.setattr(queue, "Store", lambda _root: SimpleNamespace(root="injected"))

    def claim(_store: Any, job: str, name: str) -> None:
        assert job == ORIGINAL_JOB
        assert not lock_held[0]
        events.append("claim:" + name)

    monkeypatch.setattr(loop, "_advance", claim)

    @contextmanager
    def fake_owner(*, output_lane: bool) -> Iterator[None]:
        assert output_lane
        assert not lock_held[0]
        lock_held[0] = True
        events.append("owner:acquire")
        try:
            yield
        finally:
            lock_held[0] = False
            events.append("owner:release")

    monkeypatch.setattr(loop, "native_owner", fake_owner)
    monkeypatch.setattr(loop, "_local_resolve_connection", lambda: object())

    def prepare_edited(*_args: Any) -> dict[str, str]:
        events.append("edited:prepared-authenticated")
        return {"path": "edited", "sha256": "a" * 64}

    monkeypatch.setattr(edited, "prepare_before_gui", prepare_edited)
    monkeypatch.setattr(
        edited,
        "verify_prepared_identity",
        lambda *_: events.append("edited:pre-dispatch-rechecked"),
    )
    monkeypatch.setattr(
        helper_transport,
        "SignedHelperDesktop",
        lambda _pin: SimpleNamespace(readiness=lambda: events.append("helper:ready")),
    )
    monkeypatch.setattr(
        page,
        "open_owned_edit_page",
        lambda *_args, **_kwargs: events.append("SDK:edit-page"),
    )
    monkeypatch.setattr(
        playhead, "position_owned_351", lambda *_: events.append("SDK:playhead-351")
    )

    def gui_attempt(_store: Any, job: str, _resolve: Any, **_kwargs: Any) -> Any:
        assert job == ORIGINAL_JOB and lock_held[0]
        events.append("GUI:unknown:not-verified")
        return SimpleNamespace(
            state="unknown", native_verified=False, receipt_issued=False
        )

    monkeypatch.setattr(helper_stage, "dispatch_owned_helper_f1_once", gui_attempt)
    monkeypatch.setattr(
        helper_stage,
        "observe_settled_edited_geometry",
        lambda *_: events.append("SDK:roll-settled"),
    )

    def edited_host(_store: Any, job: str, _value: Any, _session: Any) -> None:
        assert job == ORIGINAL_JOB and not lock_held[0]
        events.append("edited:SDK-MOV-PCM-verified")

    monkeypatch.setattr(edited, "continue_prepared_after_gui", edited_host)
    monkeypatch.setattr(
        revision, "revision", lambda *_: events.append("revision:proof")
    )
    monkeypatch.setattr(
        provision,
        "select",
        lambda _root, stage: events.append(f"SDK:select-{stage}"),
    )
    monkeypatch.setattr(
        revision, "rebuild", lambda *_: events.append("rebuild:SDK-MOV-PCM")
    )
    monkeypatch.setattr(
        m4,
        "publish",
        lambda *_: {
            "state": "completed_verified",
            "readyFor312Phase2": True,
            "stages": [{"state": "verified"} for _ in range(4)],
        },
    )
    result = loop.start(
        fixture["config_path"], fixture["auth_path"], frozen_commit=FROZEN
    )
    assert result == {
        "state": "original_M4_four_stages_verified",
        "jobId": ORIGINAL_JOB,
        "frozenCommit": FROZEN,
        "sourceGraphSha256": SOURCE_GRAPH,
    }
    assert actor_seals == [(ORIGINAL_JOB, fixture["authority"]["actorPin"])]
    assert events == [
        "pristine:verified",
        "claim:edited",
        "edited:prepared-authenticated",
        "helper:ready",
        "owner:acquire",
        "SDK:edit-page",
        "SDK:playhead-351",
        "edited:pre-dispatch-rechecked",
        "GUI:unknown:not-verified",
        "SDK:roll-settled",
        "owner:release",
        "edited:SDK-MOV-PCM-verified",
        "claim:revision",
        "revision:proof",
        "SDK:select-fresh",
        "claim:rebuild",
        "rebuild:SDK-MOV-PCM",
    ]
    original_intent = carrier._read(fixture["root"] / "complete-loop-intent.json")
    record = json.loads(original_intent)
    assert record["frozenCommit"] == FROZEN
    assert record["sourceGraphSha256"] == SOURCE_GRAPH
    assert (
        record["authority"]["sha256"]
        == hashlib.sha256(carrier._read(fixture["auth_path"])).hexdigest()
    )
    with pytest.raises(queue.QueueError, match=r"already used|already|root"):
        loop.start(fixture["config_path"], fixture["auth_path"], frozen_commit=FROZEN)
    assert events == [
        "pristine:verified",
        "claim:edited",
        "edited:prepared-authenticated",
        "helper:ready",
        "owner:acquire",
        "SDK:edit-page",
        "SDK:playhead-351",
        "edited:pre-dispatch-rechecked",
        "GUI:unknown:not-verified",
        "SDK:roll-settled",
        "owner:release",
        "edited:SDK-MOV-PCM-verified",
        "claim:revision",
        "revision:proof",
        "SDK:select-fresh",
        "claim:rebuild",
        "rebuild:SDK-MOV-PCM",
    ]
    assert (
        carrier._read(fixture["root"] / "complete-loop-intent.json") == original_intent
    )


def test_denied_edit_page_never_positions_playhead_or_dispatches_gui(
    prepared: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = prepared
    events: list[str] = []
    monkeypatch.setattr(
        runner,
        "start",
        lambda *_: {
            "state": "blocked_unattended_native_roll_edit_not_proven",
            "jobId": ORIGINAL_JOB,
        },
    )
    monkeypatch.setattr(
        gui,
        "seal_case_actor_pin",
        lambda _store, job, actor: _assert_test_actor(job, actor, fixture),
    )
    monkeypatch.setattr(queue, "Store", lambda *_: object())
    monkeypatch.setattr(loop, "_advance", lambda *_: events.append("stage-claimed"))

    @contextmanager
    def owner(*, output_lane: bool) -> Iterator[None]:
        assert output_lane
        events.append("owner-held")
        yield

    monkeypatch.setattr(loop, "native_owner", owner)
    monkeypatch.setattr(loop, "_local_resolve_connection", lambda: object())
    monkeypatch.setattr(
        edited, "prepare_before_gui", lambda *_: {"path": "edited", "sha256": "a" * 64}
    )
    monkeypatch.setattr(edited, "verify_prepared_identity", lambda *_: None)
    monkeypatch.setattr(
        helper_transport,
        "SignedHelperDesktop",
        lambda _pin: SimpleNamespace(readiness=lambda: None),
    )

    def refuse(*_args: Any, **_kwargs: Any) -> None:
        events.append("page-refused")
        raise queue.QueueError("signed new target mismatched")

    monkeypatch.setattr(page, "open_owned_edit_page", refuse)
    monkeypatch.setattr(
        playhead, "position_owned_351", lambda *_: pytest.fail("playhead moved")
    )
    monkeypatch.setattr(
        helper_stage,
        "dispatch_owned_helper_f1_once",
        lambda *_args, **_kwargs: pytest.fail("GUI roll dispatched"),
    )
    with pytest.raises(queue.QueueError, match="signed new target mismatched"):
        loop.start(fixture["config_path"], fixture["auth_path"], frozen_commit=FROZEN)
    assert events == ["stage-claimed", "owner-held", "page-refused"]
    assert (fixture["root"] / "complete-loop-intent.json").is_file()


@pytest.mark.parametrize(
    "stop",
    [
        "pristine_unverified",
        "gui_uncertain",
        "geometry_unknown",
        "edited_unknown",
        "revision_unknown",
        "rebuild_unknown",
    ],
)
def test_pipeline_stops_after_first_unverified_or_unknown_effect(
    prepared: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    stop: str,
) -> None:
    fixture = prepared
    events: list[str] = []

    def beginning(_config: Any) -> dict[str, Any]:
        events.append("pristine")
        return {
            "state": "unknown"
            if stop == "pristine_unverified"
            else "blocked_unattended_native_roll_edit_not_proven",
            "jobId": ORIGINAL_JOB,
        }

    monkeypatch.setattr(runner, "start", beginning)
    monkeypatch.setattr(
        gui,
        "seal_case_actor_pin",
        lambda _store, job, actor: _assert_test_actor(job, actor, fixture),
    )
    monkeypatch.setattr(queue, "Store", lambda _root: object())
    monkeypatch.setattr(
        loop, "_advance", lambda _store, _job, name: events.append("claim:" + name)
    )

    @contextmanager
    def fake_owner(*, output_lane: bool) -> Iterator[None]:
        assert output_lane
        yield

    monkeypatch.setattr(loop, "native_owner", fake_owner)
    monkeypatch.setattr(loop, "_local_resolve_connection", lambda: object())
    monkeypatch.setattr(
        edited, "prepare_before_gui", lambda *_: {"path": "edited", "sha256": "a" * 64}
    )
    monkeypatch.setattr(edited, "verify_prepared_identity", lambda *_: None)
    monkeypatch.setattr(
        helper_transport,
        "SignedHelperDesktop",
        lambda _pin: SimpleNamespace(readiness=lambda: None),
    )
    monkeypatch.setattr(page, "open_owned_edit_page", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(playhead, "position_owned_351", lambda *_: None)

    def attempt(*_: Any, **_kwargs: Any) -> Any:
        events.append("gui")
        return SimpleNamespace(
            state="unknown",
            native_verified=stop == "gui_uncertain",
            receipt_issued=False,
        )

    monkeypatch.setattr(helper_stage, "dispatch_owned_helper_f1_once", attempt)

    def observe_geometry(*_args: Any) -> None:
        if stop == "geometry_unknown":
            raise native_roll.GuiRollUnknown(
                "unexpected geometry; no edited receipt or retry"
            )

    monkeypatch.setattr(
        helper_stage, "observe_settled_edited_geometry", observe_geometry
    )

    def edited_host(*_: Any) -> None:
        events.append("edited")
        if stop == "edited_unknown":
            raise queue.QueueError("native edited chain UNKNOWN; do not replay")

    monkeypatch.setattr(edited, "continue_prepared_after_gui", edited_host)

    def revised(*_: Any) -> None:
        events.append("revision")
        if stop == "revision_unknown":
            raise queue.QueueError("accepted revision source UNKNOWN")

    monkeypatch.setattr(revision, "revision", revised)
    monkeypatch.setattr(
        provision,
        "select",
        lambda *_: events.append("SDK:select-fresh"),
    )

    def rebuilt(*_: Any) -> None:
        events.append("rebuild")
        if stop == "rebuild_unknown":
            raise queue.QueueError("fresh render UNKNOWN")

    monkeypatch.setattr(revision, "rebuild", rebuilt)
    monkeypatch.setattr(
        m4, "publish", lambda *_: pytest.fail("false final M4 acceptance")
    )
    with pytest.raises((queue.QueueError, native_roll.GuiRollUnknown)):
        loop.start(fixture["config_path"], fixture["auth_path"], frozen_commit=FROZEN)
    assert (fixture["root"] / "complete-loop-intent.json").is_file()
    assert events[:1] == ["pristine"]
    if stop == "geometry_unknown":
        assert events == ["pristine", "claim:edited", "gui"]
    assert "rebuild" in events if stop == "rebuild_unknown" else "rebuild" not in events


@pytest.mark.parametrize("git_result", ["wrong_head", "dirty", "error"])
def test_frozen_sha_refuses_wrong_checkout_and_modified_seal_graph(
    monkeypatch: pytest.MonkeyPatch,
    git_result: str,
) -> None:
    def git(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        if git_result == "error":
            return subprocess.CompletedProcess(args, 128, stdout="", stderr="denied")
        if "rev-parse" in args:
            value = "b" * 40 if git_result == "wrong_head" else FROZEN
        else:
            value = (
                " M python/vera_timeline_agent/qual.py" if git_result == "dirty" else ""
            )
        return subprocess.CompletedProcess(args, 0, stdout=value, stderr="")

    monkeypatch.setattr(subprocess, "run", git)
    monkeypatch.setattr(loop, "_source_hash", lambda: SOURCE_GRAPH)
    with pytest.raises(queue.QueueError, match=r"git|frozen|dirty"):
        loop._frozen_source(FROZEN)


def test_freeze_rejects_non_sha_without_touching_git() -> None:
    with pytest.raises(queue.QueueError, match="exact Phase-4 commit"):
        loop._frozen_source("main")


def test_inspect_never_creates_queue_or_restarts_unverified_native(
    prepared: dict[str, Any],
) -> None:
    fixture = prepared
    root = fixture["root"]
    assert loop.inspect(fixture["config_path"]) == {
        "state": "not_started",
        "verified": False,
    }
    assert not (root / "queue").exists()
    carrier._once(
        root / "complete-loop-intent.json",
        queue.canonical(
            {
                "schema": loop.INTENT_SCHEMA,
                "config": {
                    "path": str(fixture["config_path"]),
                    "sha256": hashlib.sha256(
                        queue.canonical(fixture["config"])
                    ).hexdigest(),
                },
                "authority": {
                    "path": str(fixture["auth_path"]),
                    "sha256": hashlib.sha256(
                        carrier._read(fixture["auth_path"])
                    ).hexdigest(),
                },
                "frozenCommit": FROZEN,
                "sourceGraphSha256": SOURCE_GRAPH,
            }
        ),
    )
    assert loop.inspect(fixture["config_path"]) == {
        "state": "unknown_after_intent",
        "verified": False,
    }
    assert not (root / "queue").exists()
    (root / "m4-plan.json").write_bytes(b"original M4 enrollment interrupted")
    with pytest.raises(queue.QueueError, match="original queue absent"):
        loop.inspect(fixture["config_path"])
    assert not (root / "queue").exists()


def test_advance_claims_original_operation_only_once_and_rejects_partial_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = ["queued"]
    calls: list[str] = []

    def report(*_: Any) -> dict[str, Any]:
        return {
            "state": state[0],
            "stage": "revision" if state[0] == "awaiting_operator" else None,
            "stages": [
                {"name": name, "state": "pending" if name == "revision" else "verified"}
                for name in m4.STAGES
            ],
        }

    monkeypatch.setattr(m4, "publish", report)

    def worker(_: Any) -> bool:
        state[0] = "awaiting_operator"
        calls.append("enrolled revision")
        return True

    monkeypatch.setattr(runner, "_worker_once", worker)
    loop._advance(object(), ORIGINAL_JOB, "revision")  # type: ignore[arg-type]
    assert calls == ["enrolled revision"]
    with pytest.raises(queue.QueueError, match="prior original M4 stage"):
        loop._advance(object(), ORIGINAL_JOB, "revision")  # type: ignore[arg-type]
    assert calls == ["enrolled revision"]


@pytest.mark.parametrize("refuse_at", ["admission", "pre-dispatch"])
def test_phase24_fail_closed_before_any_roll_and_without_legacy_fallback(
    prepared: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    refuse_at: str,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        runner,
        "start",
        lambda *_: {
            "state": "blocked_unattended_native_roll_edit_not_proven",
            "jobId": ORIGINAL_JOB,
        },
    )
    monkeypatch.setattr(gui, "seal_case_actor_pin", lambda *_: None)
    monkeypatch.setattr(queue, "Store", lambda *_: SimpleNamespace(root="fake"))
    monkeypatch.setattr(loop, "_advance", lambda *_: None)

    @contextmanager
    def owner(*, output_lane: bool) -> Iterator[None]:
        assert output_lane
        yield

    monkeypatch.setattr(loop, "native_owner", owner)
    monkeypatch.setattr(loop, "_local_resolve_connection", lambda: object())

    def admission(*_args: Any) -> dict[str, str]:
        events.append("admission")
        if refuse_at == "admission":
            raise queue.QueueError("edited-session admission invalid")
        return {"path": "original-edited", "sha256": "a" * 64}

    monkeypatch.setattr(edited, "prepare_before_gui", admission)
    monkeypatch.setattr(
        helper_transport,
        "SignedHelperDesktop",
        lambda _pin: SimpleNamespace(readiness=lambda: events.append("helper-ready")),
    )
    monkeypatch.setattr(
        page, "open_owned_edit_page", lambda *_args, **_kwargs: events.append("page")
    )
    monkeypatch.setattr(playhead, "position_owned_351", lambda *_: events.append("351"))

    def reauthenticate(*_args: Any) -> None:
        events.append("session-recheck")
        raise queue.QueueError("pre-Roll edited-session pin changed")

    monkeypatch.setattr(edited, "verify_prepared_identity", reauthenticate)
    monkeypatch.setattr(
        helper_stage,
        "dispatch_owned_helper_f1_once",
        lambda *_args, **_kwargs: pytest.fail("unexpected Roll after refusal"),
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("legacy subprocess fallback"),
    )
    with pytest.raises(queue.QueueError, match=r"admission invalid|pin changed"):
        loop.start(prepared["config_path"], prepared["auth_path"], frozen_commit=FROZEN)
    if refuse_at == "admission":
        assert events == ["admission"]
    else:
        assert events == ["admission", "helper-ready", "page", "351", "session-recheck"]
