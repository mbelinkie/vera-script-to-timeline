"""#261: completed-render finalization across a measured host wall-clock step.

The A11 refusal followed a real macOS ``timed`` settimeofday step of
-0.063833714 s about 1.5 s after a fresh proof controller sampled its clock.
These tests replay that sampling with a fake clock; nothing changes host time.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_issue209_controller import commit, context, reserve
from vera_timeline_agent import qualification_output_controller_v2 as controller_v2
from vera_timeline_agent.qualification_output_controller_v2 import (
    FINALIZE_CLOCK_SCHEMA,
    FINALIZE_CLOCK_STEP_ALLOWANCE_SECONDS,
    HostClockRegression,
    OutputAttemptJournal,
    QualificationOutputController,
    _ControllerTrust,
)
from vera_timeline_agent.qualification_output_records_v2 import (
    OutputConsistencyError,
    _canonical,
)

MEASURED_A11_STEP_SECONDS = -0.063833714


class ReplayClock:
    """Monotonic and wall time advance together unless a wall step is replayed."""

    def __init__(self) -> None:
        self.monotonic_value = 208_000.0
        self.wall_value = datetime(2026, 10, 19, 4, 8, 16, tzinfo=UTC)

    def monotonic(self) -> float:
        self.advance(0.000001)
        return self.monotonic_value

    def now(self) -> datetime:
        return self.wall_value

    def advance(self, seconds: float) -> None:
        self.monotonic_value += seconds
        self.wall_value += timedelta(seconds=seconds)

    def step_wall(self, seconds: float) -> None:
        self.wall_value += timedelta(seconds=seconds)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> ReplayClock:
    replay = ReplayClock()

    class ReplayDatetime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            assert tz is UTC
            return replay.now()

    monkeypatch.setattr(controller_v2, "datetime", ReplayDatetime)
    monkeypatch.setattr(time, "monotonic", replay.monotonic)
    monkeypatch.setattr(time, "sleep", replay.advance)
    return replay


def test_replayed_a11_step_is_measured_as_wall_lag(clock: ReplayClock) -> None:
    trust = _ControllerTrust(None, None)  # type: ignore[arg-type]
    clock.advance(1.5)
    clock.step_wall(MEASURED_A11_STEP_SECONDS)
    with pytest.raises(
        HostClockRegression, match="host clock rollback/uncertainty"
    ) as caught:
        trust.checked_now()
    diagnostics = caught.value.diagnostics
    assert diagnostics["classification"] == "wall_lag"
    assert diagnostics["lagSeconds"] == pytest.approx(0.063833714, abs=0.00001)
    assert diagnostics["monotonicElapsedSeconds"] == pytest.approx(1.5, abs=0.00001)
    assert diagnostics["lagPartsPerMillion"] > 40_000
    assert diagnostics["wallBeforePriorSample"] is False
    assert caught.value.recheckable
    # The refused sample never becomes the trusted high-water mark.
    assert trust.wall == datetime(2026, 10, 19, 4, 8, 16, tzinfo=UTC)


def test_sampling_quantization_and_slew_within_bound_still_pass(
    clock: ReplayClock,
) -> None:
    trust = _ControllerTrust(None, None)  # type: ignore[arg-type]
    for _ in range(100):
        clock.advance(10.0)
        clock.step_wall(-10.0 * 0.0004)  # 400 ppm slew, inside 500 ppm
        trust.checked_now()
    clock.advance(0.0005)
    clock.step_wall(-0.0000015)  # sub-quantum wall lag
    trust.checked_now()


def test_large_backward_wall_step_is_not_recheckable(clock: ReplayClock) -> None:
    trust = _ControllerTrust(None, None)  # type: ignore[arg-type]
    clock.advance(1.0)
    clock.step_wall(-3600.0)
    with pytest.raises(HostClockRegression) as caught:
        trust.checked_now()
    assert caught.value.diagnostics["wallBeforePriorSample"] is True
    assert not caught.value.recheckable


def test_monotonic_regression_is_not_recheckable(
    clock: ReplayClock,
) -> None:
    trust = _ControllerTrust(None, None)  # type: ignore[arg-type]
    clock.monotonic_value -= 5.0
    with pytest.raises(HostClockRegression) as caught:
        trust.checked_now()
    assert caught.value.diagnostics["classification"] == "monotonic_regression"
    assert not caught.value.recheckable


class FinalizeHarness:
    """Real journal/trust; native readers and decode are fixed local stand-ins."""

    def __init__(self, tmp_path: Path, clock: ReplayClock) -> None:
        self.clock = clock
        self.ctx = context()
        self.journal = OutputAttemptJournal(tmp_path / "private", self.ctx)
        reserve(self.journal, commit(self.journal, self.ctx))
        self.environment_hooks: list[Any] = []
        self.capture_failures: list[str | None] = []
        self.calls: list[str] = []
        controller = object.__new__(QualificationOutputController)
        controller.context = self.ctx
        controller.journal = self.journal
        controller.vault = None  # type: ignore[assignment]
        controller.admission = None
        controller.trust = _ControllerTrust(None, None)  # type: ignore[arg-type]
        controller._verified_final_capture = self.verified_final_capture  # type: ignore[method-assign]
        controller._environment_current = self.environment_current  # type: ignore[method-assign]
        controller._pre_capture_inputs = self.pre_capture_inputs  # type: ignore[method-assign,assignment]
        controller._attempt_materials = self.attempt_materials  # type: ignore[method-assign]
        controller._render_lineage = lambda: b"lineage"  # type: ignore[method-assign]
        controller.capture_inputs = self.capture_inputs  # type: ignore[method-assign]
        controller._native_result = lambda sequence: (Path("r"), "c" * 64, {})  # type: ignore[method-assign]
        controller.decode_output = self.decode_output  # type: ignore[method-assign]
        controller.compare = self.compare  # type: ignore[method-assign]
        self.controller = controller

    def verified_final_capture(self, result_path: Path, result_sha256: str) -> int:
        self.calls.append("verify_result")
        failure = self.capture_failures.pop(0) if self.capture_failures else None
        if failure:
            raise OutputConsistencyError(failure)
        return 5

    def fresh_proof_trust(self) -> None:
        """Replay a fresh proof controller sampling across the measured step."""
        pristine = _ControllerTrust(None, None)  # type: ignore[arg-type]
        self.clock.advance(1.5)
        self.clock.step_wall(MEASURED_A11_STEP_SECONDS)
        pristine.checked_now()

    def environment_current(self) -> None:
        self.calls.append("environment")
        hook = self.environment_hooks.pop(0) if self.environment_hooks else None
        if hook is not None:
            hook()
        self.controller.trust.checked_now()

    def pre_capture_inputs(self, *, validate_prediction: bool) -> Any:
        assert validate_prediction is False
        self.calls.append("inputs")
        return SimpleNamespace(input_binding=b"binding")

    def attempt_materials(self, attempt: dict[str, Any]) -> dict[str, bytes]:
        self.calls.append("materials")
        return dict.fromkeys(
            (
                "commitment",
                "commitment_receipt",
                "prediction",
                "reservation",
                "reservation_receipt",
            ),
            b"material",
        )

    def capture_inputs(self, *args: Any, **kwargs: Any) -> tuple[bytes, bytes]:
        self.calls.append("geometry")
        return b"post", b"post-receipt"

    def decode_output(self, **kwargs: Any) -> tuple[bytes, bytes, bytes]:
        self.calls.append("decode")
        return b"decode", b"decode-receipt", b"samples"

    def compare(self, completed: Any) -> tuple[bytes, bytes]:
        self.calls.append("compare")
        self.controller.trust.checked_now()
        row = self.journal.history()[-1]
        result = _canonical(
            {
                "context": self.ctx,
                "status": "compared_consistent",
                "priorLedgerHeadSha256": row["entrySha256"],
                "commitmentRawSha256": row["commitmentRawSha256"],
                "reservationRawSha256": row["reservationRawSha256"],
            }
        )
        self.journal.transition(
            self.ctx,
            "compared_consistent",
            expected_head=row["entrySha256"],
            result=result,
        )
        return result, b""

    def finalize(self) -> Path:
        return self.controller.finalize_output(Path("capture-post.json"), "f" * 64)

    def state(self) -> str:
        return str(self.journal.history()[-1]["state"])

    def records(self, prefix: str) -> list[dict[str, Any]]:
        return [
            json.loads(path.read_bytes())
            for path in sorted(self.journal.directory.glob(f"{prefix}-*.json"))
        ]


def test_measured_step_during_finalize_rechecks_once_and_compares(
    tmp_path: Path, clock: ReplayClock
) -> None:
    harness = FinalizeHarness(tmp_path, clock)
    harness.environment_hooks = [harness.fresh_proof_trust]
    first_trust = harness.controller.trust

    path = harness.finalize()

    assert harness.state() == "compared_consistent"
    assert path.parent == harness.journal.artifacts
    assert harness.calls == [
        "verify_result",
        "environment",
        "verify_result",
        "environment",
        "inputs",
        "materials",
        "geometry",
        "decode",
        "compare",
    ]
    assert harness.controller.trust is not first_trust
    assert harness.records("finalize-refusal") == []
    (record,) = harness.records("finalize-clock")
    assert record["schemaVersion"] == FINALIZE_CLOCK_SCHEMA
    assert record["outcome"] == "recheck"
    assert record["stage"] == "post_capture_authentication"
    assert record["capturePostResultSha256"] == "f" * 64
    assert record["diagnostics"]["lagSeconds"] == pytest.approx(0.063833714, abs=1e-5)
    assert record["diagnostics"]["controllerLagSeconds"] == pytest.approx(
        0.063833714, abs=1e-3
    )


def test_main_trust_step_rechecks_after_wall_regains_high_water(
    tmp_path: Path, clock: ReplayClock
) -> None:
    harness = FinalizeHarness(tmp_path, clock)

    def step_main() -> None:
        clock.advance(0.01)
        clock.step_wall(-0.5)

    harness.environment_hooks = [step_main]
    prior_wall = harness.controller.trust.wall
    harness.finalize()
    assert harness.state() == "compared_consistent"
    assert harness.controller.trust.wall >= prior_wall


def test_actual_backward_wall_time_beyond_allowance_quarantines(
    tmp_path: Path, clock: ReplayClock
) -> None:
    harness = FinalizeHarness(tmp_path, clock)

    def rollback() -> None:
        clock.advance(1.0)
        clock.step_wall(-(FINALIZE_CLOCK_STEP_ALLOWANCE_SECONDS + 0.5))

    harness.environment_hooks = [rollback]
    with pytest.raises(HostClockRegression):
        harness.finalize()
    assert harness.state() == "uncertain"
    assert harness.calls == ["verify_result", "environment"]
    (refusal,) = harness.records("finalize-refusal")
    assert refusal["reason"] == "host clock rollback/uncertainty"
    (record,) = harness.records("finalize-clock")
    assert record["outcome"] == "terminal"


def test_hidden_controller_lag_beyond_allowance_quarantines(
    tmp_path: Path, clock: ReplayClock
) -> None:
    """A step only the long-lived controller spans cannot be re-anchored away."""
    harness = FinalizeHarness(tmp_path, clock)

    def hidden_then_measured() -> None:
        clock.advance(2.0)
        clock.step_wall(-2.5)
        harness.fresh_proof_trust()

    harness.environment_hooks = [hidden_then_measured]
    first_trust = harness.controller.trust
    with pytest.raises(HostClockRegression):
        harness.finalize()
    assert harness.state() == "uncertain"
    assert harness.controller.trust is first_trust
    (record,) = harness.records("finalize-clock")
    assert record["outcome"] == "terminal"
    assert record["diagnostics"]["controllerLagSeconds"] > 2.5


def test_monotonic_regression_before_fresh_proof_step_quarantines(
    tmp_path: Path, clock: ReplayClock
) -> None:
    """A fresh controller's bounded step cannot re-anchor away a main-trust
    monotonic regression (its negative controller lag is not a valid reading)."""
    harness = FinalizeHarness(tmp_path, clock)

    def regress_then_measured() -> None:
        clock.monotonic_value -= 10.0
        harness.fresh_proof_trust()

    harness.environment_hooks = [regress_then_measured]
    first_trust = harness.controller.trust
    with pytest.raises(HostClockRegression):
        harness.finalize()
    assert harness.state() == "uncertain"
    assert harness.controller.trust is first_trust
    (record,) = harness.records("finalize-clock")
    assert record["outcome"] == "terminal"
    assert record["diagnostics"]["controllerLagSeconds"] < 0


def test_wall_that_never_regains_high_water_quarantines(
    tmp_path: Path, clock: ReplayClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = FinalizeHarness(tmp_path, clock)

    def stalled_wall_sleep(seconds: float) -> None:
        clock.monotonic_value += seconds

    def step_main() -> None:
        clock.advance(0.01)
        clock.step_wall(-0.5)
        monkeypatch.setattr(time, "sleep", stalled_wall_sleep)

    harness.environment_hooks = [step_main]
    with pytest.raises(HostClockRegression):
        harness.finalize()
    assert harness.state() == "uncertain"
    assert harness.calls == ["verify_result", "environment"]
    (record,) = harness.records("finalize-clock")
    assert record["outcome"] == "terminal"


def test_rollback_during_recheck_bookkeeping_stays_detectable(
    tmp_path: Path, clock: ReplayClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The re-anchor uses the validated readings, not a later unchecked one."""
    harness = FinalizeHarness(tmp_path, clock)
    harness.environment_hooks = [harness.fresh_proof_trust]
    record = QualificationOutputController._retain_finalize_clock_record

    def record_then_rollback(self: Any, **kwargs: Any) -> None:
        record(self, **kwargs)
        clock.step_wall(-2.0)

    monkeypatch.setattr(
        QualificationOutputController,
        "_retain_finalize_clock_record",
        record_then_rollback,
    )
    with pytest.raises(HostClockRegression):
        harness.finalize()
    assert harness.state() == "uncertain"
    assert "compare" not in harness.calls


def test_second_clock_refusal_during_recheck_quarantines(
    tmp_path: Path, clock: ReplayClock
) -> None:
    harness = FinalizeHarness(tmp_path, clock)
    harness.environment_hooks = [harness.fresh_proof_trust, harness.fresh_proof_trust]
    with pytest.raises(HostClockRegression):
        harness.finalize()
    assert harness.state() == "uncertain"
    outcomes = sorted(r["outcome"] for r in harness.records("finalize-clock"))
    assert outcomes == ["recheck", "terminal"]
    assert len(harness.records("finalize-refusal")) == 1


def test_source_mutation_during_recheck_quarantines(
    tmp_path: Path, clock: ReplayClock
) -> None:
    harness = FinalizeHarness(tmp_path, clock)

    def mutated() -> None:
        raise OutputConsistencyError("current host source graph differs")

    harness.environment_hooks = [harness.fresh_proof_trust, mutated]
    with pytest.raises(OutputConsistencyError, match="source graph differs"):
        harness.finalize()
    assert harness.state() == "uncertain"
    (refusal,) = harness.records("finalize-refusal")
    assert refusal["reason"] == "current host source graph differs"
    assert "compare" not in harness.calls


def test_output_or_job_change_during_recheck_quarantines(
    tmp_path: Path, clock: ReplayClock
) -> None:
    harness = FinalizeHarness(tmp_path, clock)
    harness.environment_hooks = [harness.fresh_proof_trust]
    harness.capture_failures = [
        None,
        "complete final native capture for this session required",
    ]
    with pytest.raises(OutputConsistencyError, match="complete final native capture"):
        harness.finalize()
    assert harness.state() == "uncertain"
    assert "compare" not in harness.calls


def test_partial_or_wrong_job_before_recheck_refuses_without_recheck(
    tmp_path: Path, clock: ReplayClock
) -> None:
    harness = FinalizeHarness(tmp_path, clock)
    harness.capture_failures = [
        "complete final native capture for this session required"
    ]
    with pytest.raises(OutputConsistencyError, match="complete final native capture"):
        harness.finalize()
    # Unchanged #209 behaviour: an unauthenticated result never touches the slot.
    assert harness.state() == "reserved_by_render_intent"
    assert harness.calls == ["verify_result"]
    assert harness.records("finalize-clock") == []


def test_consumed_reservation_replay_refuses_even_after_clock_step(
    tmp_path: Path, clock: ReplayClock
) -> None:
    harness = FinalizeHarness(tmp_path, clock)
    harness.finalize()
    assert harness.state() == "compared_consistent"
    harness.environment_hooks = [harness.fresh_proof_trust]
    with pytest.raises(
        OutputConsistencyError, match="reserved output attempt required"
    ):
        harness.finalize()
    assert harness.state() == "compared_consistent"
    assert harness.calls.count("compare") == 1


def test_unrelated_finalization_error_remains_terminal_without_recheck(
    tmp_path: Path, clock: ReplayClock
) -> None:
    harness = FinalizeHarness(tmp_path, clock)

    def geometry() -> None:
        raise OutputConsistencyError("post-render geometry differs")

    harness.environment_hooks = [geometry]
    with pytest.raises(OutputConsistencyError, match="geometry differs"):
        harness.finalize()
    assert harness.state() == "uncertain"
    assert harness.calls == ["verify_result", "environment"]
    assert harness.records("finalize-clock") == []
