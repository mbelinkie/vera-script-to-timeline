"""Slice 1.7 recovery tests use only fake effects and temporary storage."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pytest
from vera_timeline_agent.build_jobs import (
    BuildJobError,
    BuildJobStore,
    BuildRequest,
    NeedsAction,
    StageContext,
    UncertainResult,
    publish_immutable_output,
)


@dataclass
class Clock:
    value: float = 100.0

    def __call__(self) -> float:
        return self.value


@dataclass
class FakeStages:
    effects: dict[str, int] = field(default_factory=dict)
    interrupt_once: str | None = None
    uncertain_once: str | None = None
    wait_once: str | None = None

    def reconcile(self, context: StageContext) -> bool:
        return context.output_path.is_file()

    def execute(self, context: StageContext) -> None:
        if self.wait_once == context.stage:
            self.wait_once = None
            raise NeedsAction("stage needs its local service")
        if not context.output_path.exists():
            publish_immutable_output(context.output_path, context.stage_key.encode())
            self.effects[context.stage] = self.effects.get(context.stage, 0) + 1
        if self.interrupt_once == context.stage:
            self.interrupt_once = None
            raise KeyboardInterrupt
        if self.uncertain_once == context.stage:
            self.uncertain_once = None
            raise UncertainResult("response lost")


def request(
    mode: Literal["free", "studio"] = "free",
    *,
    render: bool = False,
    delivery: bool = False,
) -> BuildRequest:
    return BuildRequest(
        project_id="project-a",
        snapshot_id="frozen-snapshot-1",
        idempotency_key="submit-1",
        mode=mode,
        render=render,
        delivery=delivery,
    )


def stage_map(status: dict[str, object]) -> dict[str, dict[str, object]]:
    stages = status["stages"]
    assert isinstance(stages, list)
    return {str(stage["name"]): stage for stage in stages}


def drain(store: BuildJobStore, job_id: str, fake: FakeStages) -> None:
    for _ in range(12):
        if not store.run_one("project-a", job_id, "worker-a", fake, lease_seconds=5):
            return
    pytest.fail("job did not reach a boundary")


def test_duplicate_submission_and_free_stage_graph(tmp_path: Path) -> None:
    store = BuildJobStore(tmp_path)
    job_id = store.submit(request())
    assert store.submit(request()) == job_id
    with pytest.raises(BuildJobError, match="different request"):
        store.submit(request(mode="studio"))

    initial = store.status("project-a", job_id)
    stages = stage_map(initial)
    assert initial["status"] == "queued"
    assert stages["generating_speech"]["status"] == "requested"
    assert stages["building_resolve_timeline"]["status"] == "skipped"
    assert stages["uploading"]["status"] == "skipped"

    fake = FakeStages()
    drain(store, job_id, fake)
    ready = store.status("project-a", job_id)
    assert ready["status"] == "ready_to_import"
    assert all(count == 1 for count in fake.effects.values())
    assert len(fake.effects) == 5
    assert store.submit(request()) == job_id
    assert not store.run_one("project-a", job_id, "worker-a", fake)
    assert store.confirm_import("project-a", job_id) == "import_confirmed"
    assert store.status("project-a", job_id)["status"] == "import_confirmed"


def test_studio_optional_stages_are_explicit(tmp_path: Path) -> None:
    store = BuildJobStore(tmp_path)
    job_id = store.submit(request(mode="studio", render=True, delivery=False))
    fake = FakeStages()
    drain(store, job_id, fake)
    status = store.status("project-a", job_id)
    stages = stage_map(status)
    assert status["status"] == "complete"
    assert stages["rendering_mp4"]["status"] == "complete"
    assert stages["verifying_mp4"]["status"] == "complete"
    assert stages["uploading"]["status"] == "skipped"
    assert len(fake.effects) == 9


def test_interruption_and_uncertain_response_reconcile_without_repeat(
    tmp_path: Path,
) -> None:
    clock = Clock()
    store = BuildJobStore(tmp_path, clock=clock)
    job_id = store.submit(request())
    fake = FakeStages(interrupt_once="generating_speech")
    with pytest.raises(KeyboardInterrupt):
        store.run_one("project-a", job_id, "worker-a", fake, lease_seconds=5)
    assert store.status("project-a", job_id)["status"] == "running"
    clock.value += 6
    assert store.run_one("project-a", job_id, "worker-b", fake, lease_seconds=5)
    assert fake.effects["generating_speech"] == 1
    attempts = store.status("project-a", job_id)["attempts"]
    assert [attempt["status"] for attempt in attempts] == ["expired", "complete"]

    fake.uncertain_once = "resolving_media"
    assert not store.run_one("project-a", job_id, "worker-b", fake)
    assert store.status("project-a", job_id)["status"] == "waiting"
    store.resume("project-a", job_id)
    assert store.run_one("project-a", job_id, "worker-c", fake)
    assert fake.effects["resolving_media"] == 1
    drain(store, job_id, fake)
    assert store.status("project-a", job_id)["status"] == "ready_to_import"


def test_late_lease_holder_cannot_publish_or_report_progress(tmp_path: Path) -> None:
    clock = Clock()
    store = BuildJobStore(tmp_path, clock=clock)
    job_id = store.submit(request())
    entered = threading.Event()
    release = threading.Event()

    class Slow(FakeStages):
        context: StageContext | None = None

        def execute(self, context: StageContext) -> None:
            super().execute(context)
            self.context = context
            entered.set()
            assert release.wait(5)

    slow = Slow()
    result: list[bool] = []
    thread = threading.Thread(
        target=lambda: result.append(
            store.run_one("project-a", job_id, "worker-a", slow, lease_seconds=5)
        )
    )
    thread.start()
    assert entered.wait(5)
    clock.value += 6
    fast = FakeStages()
    assert store.run_one("project-a", job_id, "worker-b", fast, lease_seconds=5)
    release.set()
    thread.join(timeout=5)
    assert result == [False]
    assert slow.context is not None
    with pytest.raises(BuildJobError, match="lease"):
        slow.context.report_progress("late progress")
    status = store.status("project-a", job_id)
    assert stage_map(status)["generating_speech"]["status"] == "complete"
    assert fast.effects == {}
    assert [attempt["status"] for attempt in status["attempts"]] == [
        "expired",
        "complete",
    ]


def test_cancellation_waiting_and_corruption_preserve_completed_artifacts(
    tmp_path: Path,
) -> None:
    store = BuildJobStore(tmp_path)
    job_id = store.submit(request())
    fake = FakeStages(wait_once="resolving_media")
    assert store.run_one("project-a", job_id, "worker-a", fake)
    speech = stage_map(store.status("project-a", job_id))["generating_speech"]
    assert not store.run_one("project-a", job_id, "worker-a", fake)
    assert store.status("project-a", job_id)["status"] == "waiting"
    store.resume("project-a", job_id)
    assert store.run_one("project-a", job_id, "worker-a", fake)
    store.cancel("project-a", job_id)
    status = store.status("project-a", job_id)
    assert status["status"] == "canceled"
    assert stage_map(status)["generating_speech"] == speech
    assert stage_map(status)["compiling"]["status"] == "canceled"

    other = store.submit(
        BuildRequest("project-a", "frozen-snapshot-2", "submit-2", "free")
    )
    assert store.run_one("project-a", other, "worker-a", FakeStages())
    path = Path(
        str(stage_map(store.status("project-a", other))["generating_speech"]["path"])
    )
    path.write_bytes(b"tampered")
    assert not store.run_one("project-a", other, "worker-a", FakeStages())
    failed = store.status("project-a", other)
    assert failed["status"] == "failed"
    assert stage_map(failed)["generating_speech"]["status"] == "complete"


def test_project_scope_and_active_cancellation_boundary(tmp_path: Path) -> None:
    store = BuildJobStore(tmp_path)
    job_id = store.submit(request())
    with pytest.raises(BuildJobError, match="not found"):
        store.status("another-project", job_id)

    class CancelDuring(FakeStages):
        def execute(self, context: StageContext) -> None:
            super().execute(context)
            context.report_progress("artifact complete")
            store.cancel(context.project_id, context.job_id)

    assert store.run_one("project-a", job_id, "worker-a", CancelDuring())
    status = store.status("project-a", job_id)
    assert status["status"] == "canceled"
    assert stage_map(status)["generating_speech"]["status"] == "complete"
    assert stage_map(status)["resolving_media"]["status"] == "canceled"
    assert any(event["kind"] == "progress" for event in status["events"])


def test_process_kill_resumes_finished_speech_blocks(tmp_path: Path) -> None:
    store = BuildJobStore(tmp_path)
    job_id = store.submit(request())
    command = [
        sys.executable,
        "-m",
        "vera_timeline_agent.build_jobs_cli",
        "--root",
        str(tmp_path),
        "run",
        "--project",
        "project-a",
        "--job",
        job_id,
    ]
    process = subprocess.Popen(
        [*command, "--lease-seconds", "1", "--delay-speech-block", "5"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if any(
                event["kind"] == "progress"
                for event in store.status("project-a", job_id)["events"]
            ):
                break
            time.sleep(0.05)
        else:
            pytest.fail("worker never published its first speech block")
    finally:
        process.kill()
        process.communicate(timeout=5)

    block = tmp_path / "artifacts" / job_id / "generating_speech" / "speech-block-1"
    original = (block.read_bytes(), block.stat().st_mtime_ns)
    restarted = subprocess.run(
        [*command, "--wait-for-lease"], capture_output=True, text=True, timeout=15
    )
    assert restarted.returncode == 0, restarted.stderr
    assert (block.read_bytes(), block.stat().st_mtime_ns) == original
    status = store.status("project-a", job_id)
    assert status["status"] == "ready_to_import"
    speech_attempts = [
        attempt
        for attempt in status["attempts"]
        if attempt["stage"] == "generating_speech"
    ]
    assert [attempt["status"] for attempt in speech_attempts] == ["expired", "complete"]


def test_renewed_lease_and_failed_stage_retry(tmp_path: Path) -> None:
    clock = Clock()
    store = BuildJobStore(tmp_path, clock=clock)
    job_id = store.submit(request())

    class Renewing(FakeStages):
        def execute(self, context: StageContext) -> None:
            clock.value += 4
            context.renew_lease()
            clock.value += 4
            super().execute(context)

    assert store.run_one("project-a", job_id, "worker-a", Renewing(), lease_seconds=5)
    assert (
        stage_map(store.status("project-a", job_id))["generating_speech"]["status"]
        == "complete"
    )

    class Failing(FakeStages):
        def execute(self, context: StageContext) -> None:
            raise ValueError("fake stage failure")

    assert not store.run_one("project-a", job_id, "worker-a", Failing())
    failed = store.status("project-a", job_id)
    assert failed["status"] == "failed"
    assert stage_map(failed)["resolving_media"]["status"] == "failed"
    assert stage_map(failed)["generating_speech"]["status"] == "complete"
    store.resume("project-a", job_id)
    drain(store, job_id, FakeStages())
    assert store.status("project-a", job_id)["status"] == "ready_to_import"


def test_changed_prior_artifact_revokes_running_worker(tmp_path: Path) -> None:
    store = BuildJobStore(tmp_path)
    job_id = store.submit(request())
    assert store.run_one("project-a", job_id, "worker-a", FakeStages())
    entered = threading.Event()
    release = threading.Event()

    class Slow(FakeStages):
        def execute(self, context: StageContext) -> None:
            super().execute(context)
            entered.set()
            assert release.wait(5)

    result: list[bool] = []
    thread = threading.Thread(
        target=lambda: result.append(
            store.run_one("project-a", job_id, "worker-a", Slow())
        )
    )
    thread.start()
    assert entered.wait(5)
    speech = stage_map(store.status("project-a", job_id))["generating_speech"]
    Path(str(speech["path"])).write_bytes(b"changed")
    assert not store.run_one("project-a", job_id, "worker-b", FakeStages())
    release.set()
    thread.join(timeout=5)
    assert result == [False]
    status = store.status("project-a", job_id)
    assert status["status"] == "failed"
    assert stage_map(status)["generating_speech"]["status"] == "complete"
    assert stage_map(status)["resolving_media"]["status"] == "requested"
    assert [attempt["status"] for attempt in status["attempts"]] == [
        "complete",
        "revoked",
    ]
