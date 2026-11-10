"""Phase25 Conductor boundary; only simulated operations, no Mac native edit."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from _actor_pin import actor_pin
from vera_timeline_agent import resolve_gui_helper_protocol as helper
from vera_timeline_agent import resolve_test_bench_carrier as carrier
from vera_timeline_agent import resolve_test_bench_conductor_launch as launch
from vera_timeline_agent import resolve_test_bench_full_loop as full_loop
from vera_timeline_agent import resolve_test_bench_helper_transport as transport
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import resolve_test_queue_m4 as m4

FROZEN = "c" * 40
GRAPH = "d" * 64
JOB = "resolve-reverse-" + "1" * 32


@pytest.fixture
def prepared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    root = tmp_path / "conductor-25"
    root.mkdir(mode=0o700)
    actor = actor_pin()
    monkeypatch.setattr(helper, "validate_actor_pin", lambda *_a, **_k: actor)
    monkeypatch.setattr(
        helper,
        "source_manifest_sha256",
        lambda: actor["sourceManifestSha256"],
    )
    monkeypatch.setattr(full_loop, "_frozen_source", lambda _commit: GRAPH)
    now = datetime.now(UTC)
    request: dict[str, Any] = {
        "schema": launch.SCHEMA,
        "requestId": "conductor25test0001",
        "mode": "focus-only",
        "frozenCommit": FROZEN,
        "sourceGraphSha256": GRAPH,
        "config": None,
        "authority": None,
        "actorPin": actor,
        "resolvePid": 12345,
        "windowName": "VERA Delivery disposable signed target",
        "issuedAt": queue.iso(now),
        "expiresAt": queue.iso(now + timedelta(minutes=3)),
    }
    return {"root": root, "path": root / "launch-request.json", "request": request}


def _write(path: Path, data: dict[str, Any]) -> None:
    carrier._once(path, queue.canonical(data))


def _observation() -> dict[str, Any]:
    return {
        "resolvePid": 12345,
        "bundleIdentifier": "com.blackmagic-design.DaVinciResolve",
        "windowName": "VERA Delivery disposable signed target",
        "mainWindow": True,
        "foreground": True,
        "noModalOrSheet": True,
        "rollEnabled": True,
    }


def test_focus_launch_is_one_use_and_no_native_or_manual_stage(
    prepared: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[Any, ...]] = []

    class FakeHelper:
        def __init__(self, actor: Any) -> None:
            assert actor == prepared["request"]["actorPin"]

        def focus(self, *args: Any) -> dict[str, Any]:
            calls.append(args)
            return _observation()

    monkeypatch.setattr(transport, "SignedHelperDesktop", FakeHelper)
    monkeypatch.setattr(
        full_loop,
        "start",
        lambda *_a, **_k: pytest.fail("focus-only tried to launch native M4"),
    )
    _write(prepared["path"], prepared["request"])
    result = launch.start(prepared["path"])
    assert result["state"] == "focus-ready"
    assert len(calls) == 1
    assert calls[0] == (
        "conductor25test0001",
        "no-edit-rehearsal",
        12345,
        "VERA Delivery disposable signed target",
    )
    assert launch.verify(prepared["path"]) == result
    intent = (prepared["root"] / "launch-intent.json").read_bytes()
    with pytest.raises(queue.QueueError, match="already claimed"):
        launch.start(prepared["path"])
    assert (prepared["root"] / "launch-intent.json").read_bytes() == intent
    assert len(calls) == 1


def test_completed_focus_audit_survives_launch_expiry_and_helper_uninstall(
    prepared: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        transport,
        "SignedHelperDesktop",
        lambda *_: SimpleNamespace(focus=lambda *_args: _observation()),
    )
    _write(prepared["path"], prepared["request"])
    result = launch.start(prepared["path"])
    assert result["state"] == "focus-ready"

    class LaterClock:
        @classmethod
        def now(cls, _: Any) -> datetime:
            return datetime.now(UTC) + timedelta(days=9)

    monkeypatch.setattr(launch, "datetime", LaterClock)
    monkeypatch.setattr(
        helper,
        "validate_actor_pin",
        lambda *_a, **_k: pytest.fail("audit probed an installed helper"),
    )
    assert launch.verify(prepared["path"]) == result


def test_claimed_without_result_stays_unknown_and_never_relaunches(
    prepared: dict[str, Any],
) -> None:
    _write(prepared["path"], prepared["request"])
    carrier._once(
        prepared["root"] / "launch-intent.json",
        queue.canonical(
            {
                "schema": launch.SCHEMA,
                "requestSha256": hashlib.sha256(
                    queue.canonical(prepared["request"])
                ).hexdigest(),
            }
        ),
    )
    lock_root = prepared["root"] / ".conductor-launch"
    carrier._private(lock_root, create=True)
    with carrier._lock(lock_root):
        live = launch.verify(prepared["path"])
        assert live["state"] == "in-progress"
        assert live["verified"] is False
    result = launch.verify(prepared["path"])
    assert result["state"] == "unknown-after-claim"
    assert result["verified"] is False
    with pytest.raises(queue.QueueError, match="already claimed"):
        launch.start(prepared["path"])


def test_mac_aqua_dispatcher_exits_before_separate_runner_focus_claim(
    prepared: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual launchctl argv, nonblocking return, separate one-use worker."""
    monkeypatch.setattr(sys, "platform", "darwin")
    launched: list[list[str]] = []

    def fake_submit(
        command: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        assert kwargs["timeout"] in {8, 20}
        if command[1] == "print":
            return subprocess.CompletedProcess(
                command, 0, stdout="active aqua", stderr=""
            )
        launched.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_submit)
    monkeypatch.setattr(
        transport,
        "SignedHelperDesktop",
        lambda *_: SimpleNamespace(focus=lambda *_args: _observation()),
    )
    _write(prepared["path"], prepared["request"])
    dispatched = launch.dispatch(prepared["path"])
    assert dispatched["state"] == "submitted-not-verified"
    assert launched == [
        [
            "/bin/launchctl",
            "bootstrap",
            f"gui/{os.getuid()}",
            str(prepared["root"] / "runner.launchagent.plist"),
        ]
    ]
    plist = plistlib.loads((prepared["root"] / "runner.launchagent.plist").read_bytes())
    assert plist["RunAtLoad"] is True and plist["KeepAlive"] is False
    assert plist["LimitLoadToSessionType"] == "Aqua"
    assert plist["ProgramArguments"][-3:] == [
        "start",
        "--request",
        str(prepared["path"]),
    ]
    assert plist["EnvironmentVariables"]["PYTHONPATH"].endswith("/python")
    assert plist["WorkingDirectory"]
    assert not (prepared["root"] / "launch-intent.json").exists()
    assert launch.verify(prepared["path"])["state"] == "submitted-unclaimed"
    with pytest.raises(queue.QueueError, match="already submitted"):
        launch.dispatch(prepared["path"])
    assert len(launched) == 1
    worker_result = launch.start(prepared["path"])
    assert worker_result["state"] == "focus-ready"
    assert launch.verify(prepared["path"]) == worker_result


def test_uncertain_launchctl_submission_is_not_retried(
    prepared: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    submissions = [0]

    def fail(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        command = _args[0]
        if command[1] == "print":
            return subprocess.CompletedProcess(
                command, 0, stdout="active aqua", stderr=""
            )
        submissions[0] += 1
        raise subprocess.TimeoutExpired("launchctl bootstrap", timeout=20)

    monkeypatch.setattr(subprocess, "run", fail)
    _write(prepared["path"], prepared["request"])
    assert launch.dispatch(prepared["path"])["state"] == "unknown-dispatch"
    with pytest.raises(queue.QueueError, match="already submitted"):
        launch.dispatch(prepared["path"])
    assert submissions == [1]


@pytest.mark.parametrize("fault", ["refusal", "interruption", "wrong-window"])
def test_focus_failure_consumes_claim_without_retry(
    prepared: dict[str, Any], monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    attempts = [0]

    class FakeHelper:
        def __init__(self, _actor: Any) -> None:
            pass

        def focus(self, *_a: Any) -> dict[str, Any]:
            attempts[0] += 1
            if fault in {"refusal", "interruption"}:
                raise RuntimeError(fault)
            return {**_observation(), "windowName": "other project"}

    monkeypatch.setattr(transport, "SignedHelperDesktop", FakeHelper)
    _write(prepared["path"], prepared["request"])
    result = launch.start(prepared["path"])
    assert result["state"] == "unknown-after-claim"
    assert launch.verify(prepared["path"]) == result
    with pytest.raises(queue.QueueError, match="already claimed"):
        launch.start(prepared["path"])
    assert attempts == [1]


@pytest.mark.parametrize(
    "tamper",
    [
        "additional_field",
        "noncanonical",
        "expired",
        "future",
        "target",
        "native-payload",
        "unsafe-window",
    ],
)
def test_conductor_rejects_invalid_request_before_launch_claim(
    prepared: dict[str, Any], tamper: str
) -> None:
    value = copy.deepcopy(prepared["request"])
    if tamper == "additional_field":
        value["shell"] = "osascript"
    elif tamper == "expired":
        value["issuedAt"] = queue.iso(datetime.now(UTC) - timedelta(minutes=8))
    elif tamper == "future":
        value["issuedAt"] = queue.iso(datetime.now(UTC) + timedelta(minutes=1))
    elif tamper == "target":
        value["resolvePid"] = -1
    elif tamper == "native-payload":
        value["authority"] = {"path": "/tmp/replay", "sha256": "a" * 64}
    elif tamper == "unsafe-window":
        value["windowName"] = "control\x00character"
    raw = queue.canonical(value)
    if tamper == "noncanonical":
        raw = json.dumps(value).encode()
    carrier._once(prepared["path"], raw)
    with pytest.raises((queue.QueueError, ValueError, TypeError)):
        launch.start(prepared["path"])
    assert not (prepared["root"] / "launch-intent.json").exists()


def _native_fixture(prepared: dict[str, Any]) -> tuple[dict[str, Any], Path, Path]:
    root: Path = prepared["root"]
    config = {
        "root": str(root),
        "queueRoot": str(root / "queue"),
        "caseId": "synthetic-312",
    }
    authority = {
        "actorPin": prepared["request"]["actorPin"],
        "frozenCommit": FROZEN,
        "sourceGraphSha256": GRAPH,
    }
    config_path, auth_path = root / "config.json", root / "producer-approval.json"
    _write(config_path, config)
    _write(auth_path, authority)
    request = {
        **prepared["request"],
        "mode": "complete-m4",
        "config": {
            "path": str(config_path),
            "sha256": hashlib.sha256(queue.canonical(config)).hexdigest(),
        },
        "authority": {
            "path": str(auth_path),
            "sha256": hashlib.sha256(queue.canonical(authority)).hexdigest(),
        },
        "resolvePid": None,
        "windowName": None,
    }
    return request, config_path, auth_path


def test_conductor_full_launch_auto_advances_and_verifies_original_receipts(
    prepared: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    request, config_path, auth_path = _native_fixture(prepared)
    _write(prepared["path"], request)
    calls: list[str] = []

    def full(
        config: Path,
        authority: Path,
        *,
        frozen_commit: str,
        expected_config_sha256: str,
        expected_authority_sha256: str,
    ) -> dict[str, Any]:
        assert (config, authority, frozen_commit) == (config_path, auth_path, FROZEN)
        assert expected_config_sha256 == request["config"]["sha256"]
        assert expected_authority_sha256 == request["authority"]["sha256"]
        calls.append("full-loop")
        carrier._once(
            prepared["root"] / "complete-loop-intent.json",
            queue.canonical(
                {
                    "schema": full_loop.INTENT_SCHEMA,
                    "config": request["config"],
                    "authority": request["authority"],
                    "frozenCommit": FROZEN,
                    "sourceGraphSha256": GRAPH,
                }
            ),
        )
        return {"state": "original_M4_four_stages_verified", "jobId": JOB}

    monkeypatch.setattr(full_loop, "start", full)
    from vera_timeline_agent import resolve_test_bench_m4_runner as runner

    monkeypatch.setattr(runner, "validate_config", lambda value: value)
    monkeypatch.setattr(
        full_loop,
        "inspect",
        lambda path: {
            "state": "completed_verified",
            "verified": True,
            "jobId": JOB,
        },
    )

    def published(_store: Any, job: str) -> dict[str, Any]:
        assert job == JOB
        calls.append("authenticated-handoff")
        return {
            "state": "completed_verified",
            "readyFor312Phase2": True,
            "stages": [{"state": "verified"} for _ in range(4)],
        }

    monkeypatch.setattr(m4, "publish", published)
    result = launch.start(prepared["path"])
    assert result["state"] == "four-stages-verified"
    assert result["authoritySha256"] == request["authority"]["sha256"]
    assert launch.verify(prepared["path"]) == result
    assert calls == ["full-loop", "authenticated-handoff", "authenticated-handoff"]
    monkeypatch.setattr(
        full_loop,
        "inspect",
        lambda _path: {
            "state": "completed_verified",
            "verified": True,
            "jobId": "resolve-reverse-" + "2" * 32,
        },
    )
    with pytest.raises(queue.QueueError, match="foreign"):
        launch.verify(prepared["path"])
    with pytest.raises(queue.QueueError, match="already claimed"):
        launch.start(prepared["path"])
    assert calls.count("full-loop") == 1


@pytest.mark.parametrize("stage", ["edited", "revision", "rebuild"])
def test_stage_interruption_is_never_resubmitted(
    prepared: dict[str, Any], monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    request, _, _ = _native_fixture(prepared)
    _write(prepared["path"], request)
    from vera_timeline_agent import resolve_test_bench_m4_runner as runner

    monkeypatch.setattr(runner, "validate_config", lambda value: value)
    calls: list[str] = []

    def interrupted(*_a: Any, **_k: Any) -> dict[str, Any]:
        calls.append(stage)
        raise RuntimeError(f"interrupted in {stage}; effect may have happened")

    monkeypatch.setattr(full_loop, "start", interrupted)
    result = launch.start(prepared["path"])
    assert result["state"] == "unknown-after-claim"
    assert launch.verify(prepared["path"]) == result
    with pytest.raises(queue.QueueError, match="already claimed"):
        launch.start(prepared["path"])
    assert calls == [stage]


@pytest.mark.parametrize("drift", ["config", "authority"])
def test_full_loop_rechecks_conductor_digest_before_any_native_effect(
    prepared: dict[str, Any], monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    request, config_path, authority_path = _native_fixture(prepared)
    from vera_timeline_agent import resolve_test_bench_m4_runner as runner

    monkeypatch.setattr(runner, "validate_config", lambda value: value)
    changed = config_path if drift == "config" else authority_path
    changed.write_bytes(changed.read_bytes() + b" ")
    with pytest.raises(queue.QueueError, match="Conductor immutable"):
        full_loop.start(
            config_path,
            authority_path,
            frozen_commit=FROZEN,
            expected_config_sha256=request["config"]["sha256"],
            expected_authority_sha256=request["authority"]["sha256"],
        )
    assert not (prepared["root"] / "complete-loop-intent.json").exists()


def test_conductor_refuses_outside_case_authority_before_launch_claim(
    prepared: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    request, _, auth_path = _native_fixture(prepared)
    from vera_timeline_agent import resolve_test_bench_m4_runner as runner

    monkeypatch.setattr(runner, "validate_config", lambda value: value)
    other = prepared["root"].parent / "foreign-producer-approval.json"
    other.write_bytes(auth_path.read_bytes())
    request["authority"] = {
        "path": str(other),
        "sha256": hashlib.sha256(other.read_bytes()).hexdigest(),
    }
    _write(prepared["path"], request)
    with pytest.raises(queue.QueueError, match="private case root"):
        launch.start(prepared["path"])
    assert not (prepared["root"] / "launch-intent.json").exists()


def test_tampered_conductor_result_cannot_be_accepted(
    prepared: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        transport,
        "SignedHelperDesktop",
        lambda *_: SimpleNamespace(focus=lambda *_a: _observation()),
    )
    _write(prepared["path"], prepared["request"])
    launch.start(prepared["path"])
    path = prepared["root"] / "launch-result.json"
    fake = json.loads(path.read_bytes())
    fake["requestSha256"] = "0" * 64
    path.write_bytes(queue.canonical(fake))
    with pytest.raises(queue.QueueError, match="bound to claimed"):
        launch.verify(prepared["path"])


@pytest.mark.slow
def test_synthetic_A_uses_genuine_product_inference_and_closed_acceptance(
    tmp_path: Path,
) -> None:
    """Only native receipts are simulated; inference/acceptance are real TS."""
    from vera_timeline_agent import qualification_output_proof_v2 as proof
    from vera_timeline_agent import resolve_test_bench_revision_stage as revision
    from vera_timeline_agent.qualification_output_records_v2 import _canonical
    from vera_timeline_agent.roundtrip_v2_records import ROOT

    node = shutil.which("node")
    assert node is not None
    specimen = subprocess.run(
        [node, str(ROOT / "packages/contracts/test/issue-215-public-observation.ts")],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    fixture = json.loads(specimen.stdout)
    real_host: Any = object.__new__(proof.QualificationOutputProofV2)
    real_host.root = tmp_path / "actual-product-inference"
    real_host.baseline = SimpleNamespace(
        blobs={
            "executionDocumentSha256": _canonical(fixture["document"]),
            "executionDependenciesSha256": _canonical(fixture["dependencies"]),
        }
    )
    real_host._current = lambda: None

    class LivePolicyAdapter:
        def observe(self, case: str) -> None:
            assert case == "synthetic-312"

        def infer(self) -> dict[str, Any]:
            return dict(
                real_host._pure({"mode": "infer", "evidence": fixture["evidence"]})
            )

        def decide_inference(self, decision: dict[str, Any]) -> dict[str, Any]:
            self.inference_decision = decision
            return dict(
                real_host._pure(
                    {
                        "mode": "stage",
                        "evidence": fixture["evidence"],
                        "inferenceDecision": decision,
                    }
                )
            )

        def proposal(self) -> dict[str, Any]:
            self.candidate = real_host._pure(
                {
                    "mode": "proposal",
                    "evidence": fixture["evidence"],
                    "inferenceDecision": self.inference_decision,
                    "preparedMedia": [],
                    "handoff": None,
                }
            )
            return dict(self.candidate)

        def decide(self, decision: dict[str, Any]) -> dict[str, Any]:
            return dict(
                real_host._pure(
                    {
                        "mode": "decide",
                        "evidence": fixture["evidence"],
                        "inferenceDecision": self.inference_decision,
                        "candidate": self.candidate,
                        "decision": decision,
                        "history": [],
                    }
                )
            )

    revision._accept_synthetic_a(LivePolicyAdapter())
