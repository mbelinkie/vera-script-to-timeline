"""No second effect on retry; opaque snapshot IDs never authorize effects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from vera_timeline_agent.build_composition import (
    BuildComposition,
    EffectState,
    FrozenBuildSnapshot,
    Inspection,
    SnapshotRepository,
    StageEvidence,
)
from vera_timeline_agent.build_jobs import (
    BuildJobError,
    BuildJobStore,
    BuildRequest,
    StageContext,
    UncertainResult,
    publish_immutable_output,
)


@dataclass
class FakePort:
    name: str
    calls: int = 0
    unsure: bool = False
    missing_authorization: bool = False
    abort_after_publish: bool = False
    manipulated: bool = False

    def path(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> Path:
        return snapshot.write_root / context.job_id / context.stage / "effect.bin"

    def inspect(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> Inspection:
        if self.unsure:
            return Inspection(
                EffectState.UNCERTAIN, reason="in-flight external request"
            )
        if self.missing_authorization:
            return Inspection(EffectState.NEEDS_ACTION, reason="no provider consent")
        path = self.path(context, snapshot)
        if not path.exists():
            return Inspection(EffectState.ABSENT)
        if self.manipulated:
            return Inspection(EffectState.ABSENT)
        if path.read_bytes() != context.stage_key.encode():
            return Inspection(EffectState.UNCERTAIN, reason="unexpected effect bytes")
        return Inspection(
            EffectState.VERIFIED,
            StageEvidence(
                adapter_id="fake",
                adapter_version="v1",
                inputs={"document": snapshot.file("document")},
                outputs={"effect": path},
            ),
        )

    def execute(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> None:
        self.calls += 1
        publish_immutable_output(
            self.path(context, snapshot), context.stage_key.encode()
        )
        if self.abort_after_publish:
            self.abort_after_publish = False
            raise UncertainResult("connection dropped immediately after effect")


@dataclass
class Case:
    store: BuildJobStore
    repo: SnapshotRepository
    snapshot_id: str
    head: dict
    ports: dict[str, FakePort] = field(default_factory=dict)

    def adapter(self) -> BuildComposition:
        return BuildComposition(self.repo, self.ports)

    def request(self, mode: str = "free") -> BuildRequest:
        return BuildRequest(
            project_id="project",
            snapshot_id=self.snapshot_id,
            idempotency_key="submission",
            mode=mode,
        )


@pytest.fixture
def case(tmp_path: Path) -> Case:
    source = tmp_path / "source"
    source.mkdir()
    (source / "document.json").write_text("{}")
    (source / "dependencies.json").write_text("{}")
    head = {"value": (1, "e" * 64, "rev-1")}
    repo = SnapshotRepository(
        tmp_path / "snapshots",
        read_roots=(source,),
        write_root=tmp_path / "built",
        live_head=lambda _: head["value"],
        live_settings=lambda _: head.get("settings", "b" * 64),
    )
    frozen = repo.freeze(
        project_id="project",
        mode="free",
        build_id="build-1",
        build_class="preview",
        settings_hash="b" * 64,
        inputs={
            "document": source / "document.json",
            "dependencies": source / "dependencies.json",
        },
        adapter_versions={"fake": "v1"},
    )
    return Case(
        BuildJobStore(tmp_path / "jobs"),
        repo,
        frozen.snapshot_id,
        head,
        {
            stage: FakePort(stage)
            for stage in (
                "generating_speech",
                "resolving_media",
                "compiling",
                "writing_interchange",
                "verifying_import_package",
            )
        },
    )


def run_all(case: Case, job: str) -> None:
    for _ in range(12):
        if not case.store.run_one("project", job, "worker", case.adapter()):
            return
    raise AssertionError("did not finish")


def test_free_composition_preserves_job_graph_and_exact_retry(case: Case) -> None:
    adapter = case.adapter()
    request = case.request()
    job = adapter.submit(case.store, request)
    assert adapter.submit(case.store, request) == job
    with pytest.raises(BuildJobError, match="build mode differs"):
        adapter.submit(
            case.store,
            BuildRequest("project", case.snapshot_id, "submission", "studio"),
        )
    run_all(case, job)
    assert case.store.status("project", job)["status"] == "ready_to_import"
    assert [port.calls for port in case.ports.values()] == [1] * 5
    assert not case.store.run_one("project", job, "worker", case.adapter())
    assert case.store.confirm_import("project", job) == "import_confirmed"


def test_lost_response_reconciles_verified_bytes_without_repeating_effect(
    case: Case,
) -> None:
    job = case.adapter().submit(case.store, case.request())
    first = case.ports["generating_speech"]
    first.abort_after_publish = True
    assert not case.store.run_one("project", job, "worker", case.adapter())
    assert case.store.status("project", job)["status"] == "waiting"
    case.store.resume("project", job)
    run_all(case, job)
    assert case.store.status("project", job)["status"] == "ready_to_import"
    assert first.calls == 1


def test_uncertain_or_unapproved_external_state_must_not_run(case: Case) -> None:
    job = case.adapter().submit(case.store, case.request())
    port = case.ports["generating_speech"]
    port.unsure = True
    assert not case.store.run_one("project", job, "worker", case.adapter())
    assert case.store.status("project", job)["status"] == "waiting"
    assert port.calls == 0
    case.store.resume("project", job)
    port.unsure = False
    port.missing_authorization = True
    assert not case.store.run_one("project", job, "worker", case.adapter())
    assert port.calls == 0


def test_edited_source_or_head_refuses_frozen_snapshot(case: Case) -> None:
    request = case.request()
    assert case.adapter().submit(case.store, request)
    case.head["value"] = (2, "f" * 64, "rev-2")
    with pytest.raises(BuildJobError, match="stale project"):
        case.adapter().submit(case.store, request)
    case.head["value"] = (1, "e" * 64, "rev-1")
    case.repo.load("project", case.snapshot_id).file("document").write_text(
        '{"mutated":true}'
    )
    with pytest.raises(BuildJobError, match="stale frozen input"):
        case.repo.load("project", case.snapshot_id)


def test_forged_receipt_and_missing_effect_cannot_advance(case: Case) -> None:
    job = case.adapter().submit(case.store, case.request())
    ctx_path = case.store.artifacts / job / "generating_speech" / "output"
    publish_immutable_output(ctx_path, b"a forged proof\n")
    assert not case.store.run_one("project", job, "worker", case.adapter())
    assert case.store.status("project", job)["status"] in ("waiting", "failed")
    assert case.ports["generating_speech"].calls == 0


def test_tampered_previous_effect_refuses_downstream_stage(case: Case) -> None:
    job = case.adapter().submit(case.store, case.request())
    assert case.store.run_one("project", job, "worker", case.adapter())
    frozen = case.repo.load("project", case.snapshot_id)
    effect = frozen.write_root / job / "generating_speech" / "effect.bin"
    effect.write_bytes(b"tampered")
    assert not case.store.run_one("project", job, "worker", case.adapter())
    assert case.store.status("project", job)["status"] in ("waiting", "failed")
    assert case.ports["resolving_media"].calls == 0


def test_cross_project_and_missing_render_port_refuse(case: Case) -> None:
    with pytest.raises(BuildJobError, match="project"):
        case.repo.load("wrong-project", case.snapshot_id)
    with pytest.raises(BuildJobError, match="Free jobs cannot"):
        case.adapter().submit(
            case.store,
            BuildRequest(
                "project", case.snapshot_id, "render-key", "free", render=True
            ),
        )
