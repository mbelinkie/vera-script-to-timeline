"""Durable ingest jobs use the build store's recovery and integrity boundary."""

from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pytest
from vera_timeline_agent.build_jobs import (
    BuildJobError,
    BuildJobStore,
    BuildRequest,
    IngestRequest,
    StageContext,
    publish_immutable_output,
)


@dataclass
class Clock:
    value: float = 100.0

    def __call__(self) -> float:
        return self.value


def request(
    *,
    source_id: str = "source-a",
    generation_identity: str = "a" * 64,
    idempotency_key: str = "ingest-1",
) -> IngestRequest:
    return IngestRequest(
        project_id="project-a",
        source_id=source_id,
        generation_identity=generation_identity,
        idempotency_key=idempotency_key,
    )


def create_old_build_database(root: Path) -> None:
    with sqlite3.connect(root / "build-jobs.sqlite3") as connection:
        connection.execute(
            """CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                snapshot_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                lease_epoch INTEGER NOT NULL DEFAULT 0,
                lease_worker TEXT,
                lease_until REAL,
                active_stage TEXT,
                last_error TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                UNIQUE(project_id, idempotency_key)
            )"""
        )
        connection.execute(
            """INSERT INTO jobs(
                id, project_id, snapshot_id, idempotency_key, request_hash,
                mode, status, created_at, updated_at
            ) VALUES('old-job', 'project-a', 'snapshot-a', 'old-key', 'hash',
                    'free', 'queued', 1, 1)"""
        )


class FakeMediaAdapter:
    def __init__(
        self,
        executed: list[str],
        *,
        interrupt_once: str | None = None,
        contexts: list[tuple[str, str | None, str | None]] | None = None,
    ) -> None:
        self.executed = executed
        self.interrupt_once = interrupt_once
        self.contexts = contexts

    def reconcile(self, context: StageContext) -> bool:
        return (
            context.output_path.is_file()
            and context.output_path.read_bytes() == context.stage_key.encode()
        )

    def execute(self, context: StageContext) -> None:
        self.executed.append(context.stage)
        if self.contexts is not None:
            self.contexts.append(
                (context.job_kind, context.source_id, context.generation_identity)
            )
        publish_immutable_output(context.output_path, context.stage_key.encode())
        if self.interrupt_once == context.stage:
            self.interrupt_once = None
            raise KeyboardInterrupt


def stage_map(status: dict[str, object]) -> dict[str, dict[str, object]]:
    stages = status["stages"]
    assert isinstance(stages, list)
    return {str(stage["name"]): stage for stage in stages}


def test_ingest_identity_and_stage_graph_are_separate_from_builds(
    tmp_path: Path,
) -> None:
    store = BuildJobStore(tmp_path)
    job_id = store.submit_ingest(request())

    assert store.submit_ingest(request()) == job_id
    with pytest.raises(BuildJobError, match="different request"):
        store.submit_ingest(request(generation_identity="b" * 64))
    with pytest.raises(BuildJobError, match="different request"):
        store.submit_ingest(request(source_id="source-b"))

    status = store.status("project-a", job_id)
    assert status["kind"] == "ingest"
    assert status["sourceId"] == "source-a"
    assert status["generationIdentity"] == "a" * 64
    assert [stage["name"] for stage in status["stages"]] == [
        "proxy",
        "audio",
        "waveform",
    ]
    assert all(stage["status"] == "requested" for stage in status["stages"])


def test_old_build_database_migrates_without_changing_build_submission(
    tmp_path: Path,
) -> None:
    create_old_build_database(tmp_path)
    store = BuildJobStore(tmp_path)
    old = store.status("project-a", "old-job")
    assert old["kind"] == "build"
    assert old["sourceId"] is None
    assert old["generationIdentity"] is None
    new_job_id = store.submit(
        BuildRequest("project-a", "snapshot-b", "new-key", "free")
    )
    assert store.status("project-a", new_job_id)["kind"] == "build"


def test_concurrent_store_initialization_serializes_old_database_migration(
    tmp_path: Path,
) -> None:
    create_old_build_database(tmp_path)
    ready = threading.Barrier(4)

    def initialize() -> BuildJobStore:
        ready.wait(timeout=5)
        return BuildJobStore(tmp_path)

    with ThreadPoolExecutor(max_workers=4) as pool:
        stores = [pool.submit(initialize) for _ in range(4)]
        opened = [future.result(timeout=10) for future in stores]

    assert all(
        store.status("project-a", "old-job")["kind"] == "build" for store in opened
    )
    job_id = opened[0].submit(
        BuildRequest("project-a", "snapshot-b", "new-key", "free")
    )
    assert opened[-1].status("project-a", job_id)["kind"] == "build"


@pytest.mark.parametrize(
    "value",
    ["", "A" * 64, "a" * 63, "g" * 64],
)
def test_ingest_generation_identity_must_be_a_canonical_sha256(
    tmp_path: Path, value: str
) -> None:
    with pytest.raises(BuildJobError, match="lowercase SHA-256"):
        BuildJobStore(tmp_path).submit_ingest(request(generation_identity=value))


def test_ingest_restart_reconciles_effect_and_verifies_completed_receipts(
    tmp_path: Path,
) -> None:
    clock = Clock()
    store = BuildJobStore(tmp_path, clock=clock)
    job_id = store.submit_ingest(request())
    executed: list[str] = []
    contexts: list[tuple[str, str | None, str | None]] = []
    with pytest.raises(KeyboardInterrupt):
        store.run_one(
            "project-a",
            job_id,
            "worker-a",
            FakeMediaAdapter(executed, interrupt_once="proxy", contexts=contexts),
            lease_seconds=5,
        )
    assert executed == ["proxy"]
    assert store.status("project-a", job_id)["status"] == "running"

    clock.value += 6
    restarted = BuildJobStore(tmp_path, clock=clock)
    assert restarted.submit_ingest(request()) == job_id
    adapter = FakeMediaAdapter(executed, contexts=contexts)
    assert restarted.run_one("project-a", job_id, "worker-b", adapter, lease_seconds=5)
    for _ in range(2):
        assert restarted.run_one(
            "project-a", job_id, "worker-b", adapter, lease_seconds=5
        )

    complete = restarted.status("project-a", job_id)
    assert complete["status"] == "complete"
    assert [attempt["status"] for attempt in complete["attempts"]] == [
        "expired",
        "complete",
        "complete",
        "complete",
    ]
    assert executed == ["proxy", "audio", "waveform"]
    assert contexts == [("ingest", "source-a", "a" * 64)] * 3

    proxy = Path(str(stage_map(complete)["proxy"]["path"]))
    proxy.write_bytes(b"changed")
    assert not restarted.run_one(
        "project-a", job_id, "worker-b", FakeMediaAdapter(executed)
    )
    failed = restarted.status("project-a", job_id)
    assert failed["status"] == "failed"
    assert stage_map(failed)["proxy"]["status"] == "complete"
