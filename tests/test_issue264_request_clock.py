"""Replay measured macOS wall steps through terminal proof and request checks."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import test_issue209_seam as seam
from test_issue209_controller import commit, reserve
from test_issue215_proof import controller_fixture
from test_issue261_clock_finalization import ReplayClock
from test_issue261_clock_finalization import clock as clock_fixture
from vera_timeline_agent import qualification_output_controller_v2 as controllers
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent import qualification_output_proof_v2 as proof
from vera_timeline_agent.qualification_output_records_v2 import (
    OutputConsistencyError,
    _canonical,
    _parse,
)

clock = clock_fixture


class RequestHarness:
    """Real request/authority checks and terminal recomputation; no native effects."""

    def __init__(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replay: ReplayClock
    ) -> None:
        monkeypatch.setattr(native, "datetime", controllers.datetime)  # type: ignore[attr-defined]
        monkeypatch.setattr(seam, "datetime", controllers.datetime)  # type: ignore[attr-defined]
        controller, self.approval, _, self.context, _, _ = seam._runtime_fixture(
            tmp_path, monkeypatch
        )
        self.controller: controllers.QualificationOutputController = controller
        self.controller.vault = controllers._ReceiptVault(tmp_path / "vault")
        self.controller.trust = controllers._ControllerTrust(
            self.controller.vault, self.controller.admission
        )
        self.replay = replay
        self.monkeypatch = monkeypatch
        self.tmp_path = tmp_path
        self.checks = 0
        self.steps: list[float] = []
        self.elapsed = 1.5
        self.mutation: str | None = None
        self.empty_terminal = False
        self.high_waters: list[datetime] = []
        self.sequence = 0
        self.action = "construct"
        self.payload: dict[str, Any] = {}
        self.materials: dict[str, bytes] = {}
        monkeypatch.setattr(self.controller, "_environment_current", self.environment)

    def queue_stage(self) -> None:
        """Real reserved host slot; preceding native results are fixed I/O doubles."""
        journal = self.controller.journal
        reserved = reserve(journal, commit(journal, self.context))
        reservation = (
            journal.artifacts / reserved["reservationRawSha256"]
        ).read_bytes()
        receipt = self.controller.vault._issue(
            "output_render_reservation", _parse(reservation), (reservation,)
        )
        self.materials = {
            "reservation": reservation,
            "reservation_receipt": receipt,
            "render_intent": _canonical({"context": self.context}),
        }
        self.sequence, self.action = 3, "queue_render"
        self.monkeypatch.setattr(
            native, "next_native_operation", lambda _: (3, "1" * 64)
        )
        approval = _parse(self.approval.read_bytes())
        self.payload = {
            "settings": approval["settings"],
            "outputPath": approval["outputPath"],
            "outputFilename": Path(approval["outputPath"]).name,
        }

    def environment(self) -> None:
        self.checks += 1
        root = self.tmp_path / f"terminal-{self.checks}"
        root.mkdir()
        terminal, sealed = controller_fixture(root, self.monkeypatch)
        if self.empty_terminal:
            terminal.journal.history = lambda: []
        if self.checks > 1 and self.mutation == "source":
            inputs = sealed.output.inputs
            wavs = dict(inputs.source_wavs)
            wavs[next(iter(wavs))] += b"changed"
            terminal._pre_capture_inputs = lambda **_: replace(inputs, source_wavs=wavs)
        if self.checks > 1 and self.mutation == "output":
            path = terminal.journal.artifacts / controllers._hash(
                sealed.output.decoded_samples
            )
            path.write_bytes(b"changed")
        # Keep the independently sealed receipts; use the real checked clock.
        terminal.trust = controllers._ControllerTrust(
            terminal.trust,
            SimpleNamespace(verify_source_payload=terminal.trust.authenticate),
        )
        self.high_waters.append(terminal.trust.wall)
        if self.steps:
            self.replay.advance(self.elapsed)
            self.replay.step_wall(self.steps.pop(0))
        proof.load_terminal_output(terminal)

    def prepare(self) -> Path:
        return self.controller.prepare_native_request(
            self.action, self.payload, approval_path=self.approval, **self.materials
        )

    def records(self) -> list[dict[str, Any]]:
        return [
            json.loads(path.read_bytes())
            for path in self.controller.journal.directory.glob("request-clock-*.json")
        ]

    def assert_no_slot(self) -> None:
        assert not native.native_request_paths(self.context, self.sequence)[
            -1
        ].parent.exists()


@pytest.mark.parametrize(
    ("action", "step"), [("construct", -0.0309), ("queue_render", -0.0512)]
)
def test_measured_step_rechecks_full_terminal_chain_before_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clock: ReplayClock,
    action: str,
    step: float,
) -> None:
    harness = RequestHarness(tmp_path, monkeypatch, clock)
    if action == "queue_render":
        harness.queue_stage()
    history = harness.controller.journal.history()
    harness.steps = [step]
    path = harness.prepare()
    raw = path.read_bytes()
    request = native.verify_native_request(
        raw, expected_request_sha256=controllers._hash(raw), current=True
    )
    native._verify_authority(request, current=True)
    assert request["sequence"] == harness.sequence
    assert request["action"] == action
    assert harness.controller.journal.history() == history
    assert harness.checks == 2
    assert harness.controller.trust.wall >= max(harness.high_waters)
    (record,) = harness.records()
    assert record["outcome"] == "recheck"
    assert record["diagnostics"]["lagSeconds"] == pytest.approx(-step, abs=1e-5)
    # Publishing the request still consumes the exact fixed operation slot.
    with pytest.raises((OutputConsistencyError, FileExistsError)):
        harness.prepare()
    assert len(list(path.parent.parent.iterdir())) == 1


@pytest.mark.parametrize("step", [-0.0309, -0.0512])
def test_terminal_loader_itself_remains_strict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: ReplayClock, step: float
) -> None:
    harness = RequestHarness(tmp_path, monkeypatch, clock)
    harness.steps = [step]
    with pytest.raises(controllers.HostClockRegression) as caught:
        harness.environment()
    assert caught.value.recheckable
    assert caught.value.diagnostics["lagSeconds"] == pytest.approx(-step, abs=1e-5)
    harness.assert_no_slot()


def test_request_waits_for_previously_trusted_wall_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: ReplayClock
) -> None:
    harness = RequestHarness(tmp_path, monkeypatch, clock)
    harness.elapsed = 0.01
    harness.steps = [-0.5]
    prior = harness.controller.trust.wall
    harness.prepare()
    assert harness.controller.trust.wall >= max(prior, *harness.high_waters)
    assert harness.checks == 2


def test_fresh_proof_step_cannot_hide_main_monotonic_regression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: ReplayClock
) -> None:
    harness = RequestHarness(tmp_path, monkeypatch, clock)
    harness.controller.trust.monotonic += 5
    harness.steps = [-0.0309]
    first = harness.controller.trust
    with pytest.raises(controllers.HostClockRegression):
        harness.prepare()
    assert harness.controller.trust is first
    assert harness.checks == 1
    assert harness.records()[0]["outcome"] == "terminal"
    harness.assert_no_slot()


@pytest.mark.parametrize(
    ("mutation", "reason"), [("source", "source"), ("output", "decoded")]
)
def test_currentness_error_on_recheck_never_writes_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clock: ReplayClock,
    mutation: str,
    reason: str,
) -> None:
    harness = RequestHarness(tmp_path, monkeypatch, clock)
    harness.steps = [-0.0512]
    harness.mutation = mutation
    with pytest.raises(OutputConsistencyError, match=reason):
        harness.prepare()
    assert harness.checks == 2
    harness.assert_no_slot()


def test_real_approval_expiry_during_recheck_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: ReplayClock
) -> None:
    harness = RequestHarness(tmp_path, monkeypatch, clock)
    approval = _parse(harness.approval.read_bytes())
    approval["expiresAt"] = (clock.wall_value + timedelta(seconds=1)).isoformat()
    harness.approval.chmod(0o600)
    harness.approval.write_bytes(_canonical(approval))
    harness.approval.chmod(0o400)
    harness.steps = [-0.0309]
    with pytest.raises(OutputConsistencyError, match="approval expired"):
        harness.prepare()
    assert harness.checks == 2
    harness.assert_no_slot()


@pytest.mark.parametrize("steps", [[-2.0], [-0.0309, -0.0512]])
def test_large_or_repeated_step_stays_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clock: ReplayClock,
    steps: list[float],
) -> None:
    harness = RequestHarness(tmp_path, monkeypatch, clock)
    harness.steps = steps.copy()
    with pytest.raises(controllers.HostClockRegression):
        harness.prepare()
    assert harness.checks == len(steps)
    assert "terminal" in [record["outcome"] for record in harness.records()]
    harness.assert_no_slot()


def test_unrelated_terminal_error_does_not_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: ReplayClock
) -> None:
    harness = RequestHarness(tmp_path, monkeypatch, clock)

    harness.empty_terminal = True
    with pytest.raises(OutputConsistencyError, match="consistent terminal"):
        harness.prepare()
    assert harness.checks == 1
    assert harness.records() == []
    harness.assert_no_slot()


def test_clock_refusal_after_intent_publication_is_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: ReplayClock
) -> None:
    harness = RequestHarness(tmp_path, monkeypatch, clock)
    verify = native.verify_native_request

    def verify_then_revalidate(raw: bytes, **kwargs: Any) -> dict[str, Any]:
        request = verify(raw, **kwargs)
        harness.steps = [-0.0309]
        harness.environment()
        return request

    monkeypatch.setattr(native, "verify_native_request", verify_then_revalidate)
    with pytest.raises(controllers.HostClockRegression):
        harness.prepare()
    _, authority, intent, request = native.native_request_paths(harness.context, 0)
    assert authority.exists() and intent.exists()
    assert not request.exists()
    assert harness.checks == 2
    assert harness.records() == []
