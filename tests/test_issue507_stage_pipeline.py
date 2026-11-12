"""#507: staged dispatch and isolated frozen revisions, no real effects."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_issue382_build_agent import (
    JOB,
    PROJECT,
    SNAPSHOT,
    TARGET,
    FakeInputAuthority,
    FakePort,
    FakeTransport,
    _job,
    complete_dependencies,
    digest,
    manifest,
)
from vera_timeline_agent.build_agent_service import (
    AgentTransportRefusal,
    LocalBuildAgentService,
    QualifiedStagePipeline,
)
from vera_timeline_agent.build_jobs import CORE_STAGES, STUDIO_STAGES
from vera_timeline_agent.build_media_stage import (
    MediaStageAuthorization,
    MediaStagePort,
)
from vera_timeline_agent.build_narration_stage import NarrationStagePort
from vera_timeline_agent.build_package_stage import PackageStagePort
from vera_timeline_agent.build_studio_stage import (
    BuildStudioStagePort,
    NativeAuthorization,
    NativeDriver,
    VerifyStudioStagePort,
)
from vera_timeline_agent.build_submission_inputs import AcceptedSourceFile
from vera_timeline_agent.narration.service import NarrationService


def fake_agent(
    tmp_path: Path,
    transport: FakeTransport,
    port: FakePort,
    *,
    native: NativeAuthorization | None = None,
) -> LocalBuildAgentService:
    return LocalBuildAgentService(
        tmp_path / "private",
        PROJECT,
        transport,
        {stage: port for stage in CORE_STAGES + STUDIO_STAGES[:2]},
        {"synthetic": "v1"},
        input_authority=FakeInputAuthority(transport),
        native_authorization=native,
    )


def test_studio_without_native_permission_refuses_before_local_effect(
    tmp_path: Path,
) -> None:
    transport = FakeTransport(data=manifest("studio"))
    port = FakePort()
    agent = fake_agent(tmp_path, transport, port)
    assert agent.run_one(JOB) == "needs_action"
    assert port.calls == 0
    # Immutable input freeze is safe without native permission. An owner can
    # inspect its exact local snapshot ID before authorizing any native write.
    assert len(list((tmp_path / "private" / "snapshots").glob("*.json"))) == 1
    assert transport.reports == [
        ("transport", "running", None, "native_authorization_pending")
    ]


def test_studio_requires_exact_frozen_snapshot_before_first_effect(
    tmp_path: Path,
) -> None:
    transport = FakeTransport(data=manifest("studio"))
    port = FakePort()
    wrong = NativeAuthorization(
        PROJECT,
        "0" * 64,
        "f" * 64,
        "request-one",
        True,
        job_id=JOB,
        target_id=transport.data["targetId"],
    )
    agent = fake_agent(tmp_path, transport, port, native=wrong)
    assert agent.run_one(JOB) == "needs_action"
    assert port.calls == 0
    snapshots = list((tmp_path / "private" / "snapshots").glob("*.json"))
    assert len(snapshots) == 1
    assert transport.reports[-1] == (
        "transport",
        "running",
        None,
        "native_authorization_pending",
    )
    snapshot_id = snapshots[0].stem
    assert agent.store.database.exists()

    approved = NativeAuthorization(
        PROJECT,
        snapshot_id,
        "f" * 64,
        "request-one",
        True,
        job_id=JOB,
        target_id=transport.data["targetId"],
    )
    restarted = fake_agent(tmp_path, transport, port, native=approved)
    assert restarted.run_one(JOB, resumed_epoch=1, resumed_digest=SNAPSHOT) == "queued"
    assert port.calls == 1
    job = restarted.store.status(PROJECT, _job(restarted))
    assert job["mode"] == "studio"
    assert job["stages"][0]["status"] == "complete"
    assert [row["status"] for row in job["stages"][-3:]] == [
        "skipped",
        "skipped",
        "skipped",
    ]
    assert [row["status"] for row in job["stages"][5:7]] == ["requested", "requested"]
    frozen = restarted.root / "snapshots" / f"{snapshot_id}.json"
    assert json.loads(frozen.read_text())["mode"] == "studio"
    assert transport.claims == 1
    for index, stage in enumerate(CORE_STAGES[1:] + STUDIO_STAGES[:2], start=2):
        assert restarted.run_one(JOB, resumed_epoch=1, resumed_digest=SNAPSHOT) == (
            "complete" if index == 7 else "queued"
        )
        assert transport.reports[-2][0] == stage
        assert port.calls == index
    assert [
        row["status"]
        for row in restarted.store.status(PROJECT, _job(restarted))["stages"][:7]
    ] == ["complete"] * 7
    assert [stage for stage, _ in transport.inspections] == [
        "verifying_import_package",
        "verifying_timeline",
    ]


def test_free_pipeline_skips_native_even_when_ports_are_present(tmp_path: Path) -> None:
    transport, port = FakeTransport(), FakePort()
    agent = fake_agent(tmp_path, transport, port)
    assert agent.run_one(JOB) == "queued"
    assert port.calls == 1
    job = agent.store.status(PROJECT, _job(agent))
    assert job["mode"] == "free"
    assert [row["status"] for row in job["stages"][5:]] == ["skipped"] * 5
    assert agent.run_one(JOB, resumed_epoch=1, resumed_digest=SNAPSHOT) == "queued"
    assert port.calls == 2
    assert transport.claims == 1
    for index in range(3, 6):
        assert agent.run_one(JOB, resumed_epoch=1, resumed_digest=SNAPSHOT) == (
            "ready_to_import" if index == 5 else "queued"
        )
        assert port.calls == index
    assert agent.store.status(PROJECT, _job(agent))["status"] == "ready_to_import"
    assert len(transport.inspections) == 1
    assert transport.inspections[0][0] == "verifying_import_package"
    assert transport.inspections[0][1].startswith("sha256:")


def test_missing_studio_readback_port_refuses_without_native_effect(
    tmp_path: Path,
) -> None:
    transport, port = FakeTransport(data=manifest("studio")), FakePort()
    agent = LocalBuildAgentService(
        tmp_path / "private",
        PROJECT,
        transport,
        {stage: port for stage in CORE_STAGES + STUDIO_STAGES[:1]},
        {"synthetic": "v1"},
        input_authority=FakeInputAuthority(transport),
        native_authorization=NativeAuthorization(
            PROJECT, "f" * 64, "f" * 64, "request-one", True
        ),
    )
    assert agent.run_one(JOB) == "needs_action"
    assert port.calls == 0


def test_service_refuses_a_different_native_port_permission_or_driver(
    tmp_path: Path,
) -> None:
    transport = FakeTransport(data=manifest("studio"))
    fake = FakePort()
    approved = NativeAuthorization(
        PROJECT,
        "a" * 64,
        "b" * 64,
        "request",
        True,
        job_id=JOB,
        target_id=transport.data["targetId"],
    )
    changed = NativeAuthorization(
        PROJECT,
        "a" * 64,
        "b" * 64,
        "substituted",
        True,
        job_id=JOB,
        target_id=transport.data["targetId"],
    )
    first_driver = cast(NativeDriver, object())
    other_driver = cast(NativeDriver, object())
    for authorization, verifier_driver in (
        (changed, first_driver),
        (approved, other_driver),
    ):
        ports: dict[str, Any] = {stage: fake for stage in CORE_STAGES}
        ports["building_resolve_timeline"] = BuildStudioStagePort(
            approved, first_driver, host_state=tmp_path / "host"
        )
        ports["verifying_timeline"] = VerifyStudioStagePort(
            authorization, verifier_driver, host_state=tmp_path / "host"
        )
        service = LocalBuildAgentService(
            tmp_path / f"service-{authorization.request_id}-{id(verifier_driver)}",
            PROJECT,
            transport,
            ports,
            {"synthetic": "v1"},
            input_authority=FakeInputAuthority(transport),
            native_authorization=approved,
        )
        assert service.run_one(JOB) == "needs_action"
    assert fake.calls == 0


def test_qualified_real_ports_pin_only_accepted_versions(tmp_path: Path) -> None:
    provider = SimpleNamespace(adapter_version="synthetic-narration/v1")
    narrator = NarrationStagePort(
        cast(NarrationService, SimpleNamespace(provider=provider))
    )
    media = MediaStagePort(cast(MediaStageAuthorization, object()))
    pipeline = QualifiedStagePipeline(narrator, media, PackageStagePort())
    ports, versions, native = pipeline.resolved()
    assert set(ports) == set(CORE_STAGES)
    assert versions == {
        "narration-v2": "synthetic-narration/v1",
        "prepare-media-v2": "authoring-media-preparation/v1",
        "compiler-v2": "compiler/v2",
        "v2-package": "v2-package/v1",
        "v2-attestation": "vera-injected-delivery-attestation/v2",
    }
    assert native is None
    with pytest.raises(AgentTransportRefusal, match="qualified core"):
        QualifiedStagePipeline(
            cast(Any, object()), media, PackageStagePort()
        ).resolved()

    permit = NativeAuthorization(PROJECT, "a" * 64, "b" * 64, "request", True)
    driver = cast(NativeDriver, object())  # No method may be called in this phase.
    build = BuildStudioStagePort(permit, driver, host_state=tmp_path / "host")
    verify = VerifyStudioStagePort(permit, driver, host_state=tmp_path / "host")
    ports, versions, native = QualifiedStagePipeline(
        narrator, media, PackageStagePort(), build, verify
    ).resolved()
    assert set(ports) == set(CORE_STAGES + STUDIO_STAGES[:2])
    assert native == permit
    assert versions["resolve-v2"] == "injected-none/v2"
    assert versions["resolve-v2-readback"] == "injected-none-readback/v2"
    with pytest.raises(AgentTransportRefusal, match="both native"):
        QualifiedStagePipeline(narrator, media, PackageStagePort(), build).resolved()
    with pytest.raises(AgentTransportRefusal, match="ambiguous"):
        LocalBuildAgentService(
            tmp_path / "other", PROJECT, FakeTransport(), ports={}, pipeline=pipeline
        )


@dataclass
class RevisionTransport(FakeTransport):
    """Fixture backend with per-job identity and a revocable role."""

    requested_job: str = JOB
    role_revoked: bool = False

    def claim(self, job_id: str) -> tuple[int, str]:
        assert job_id == self.requested_job
        if self.role_revoked:
            raise AgentTransportRefusal("revoked producer role")
        self.claims += 1
        return 1, SNAPSHOT

    def frozen(self, job_id: str, epoch: int) -> dict[str, Any]:
        assert (job_id, epoch) == (self.requested_job, 1)
        if self.role_revoked:
            raise AgentTransportRefusal("revoked producer role")
        self.reads += 1
        return dict(self.data)

    def progress(
        self,
        job_id: str,
        epoch: int,
        stage: str,
        status: str,
        receipt_digest: str | None,
        reason: str | None,
    ) -> None:
        assert (job_id, epoch) == (self.requested_job, 1)
        self.reports.append((stage, status, receipt_digest, reason))


def _revision(
    tmp_path: Path,
    job_id: str,
    target_id: str,
    doc_revision: int,
    source_revision: str,
) -> tuple[RevisionTransport, FakeInputAuthority, Path]:
    doc = json.dumps(
        {"projectId": PROJECT, "id": job_id, "revision": doc_revision},
        sort_keys=True,
    )
    data = manifest("studio")
    data.update(
        jobId=job_id,
        targetId=target_id,
        documentRevision=doc_revision,
        documentJson=doc,
        documentDigest=digest(doc),
    )
    raw = f"public synthetic source bytes {source_revision}".encode()
    source_digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    data["selectedSources"] = [
        {"sourceId": TARGET, "revision": source_revision, "sha256": source_digest}
    ]
    accepted = tmp_path / source_revision
    accepted.mkdir(mode=0o700)
    path = accepted / "public-fixture.mov"
    path.write_bytes(raw)
    transport = RevisionTransport(data=data, requested_job=job_id)
    authority = FakeInputAuthority(transport, complete_dependencies(data))
    authority.accepted[TARGET] = AcceptedSourceFile(
        PROJECT, TARGET, source_revision, source_digest, path
    )
    return transport, authority, accepted


def _revision_agent(
    root: Path,
    transport: RevisionTransport,
    authority: FakeInputAuthority,
    accepted: Path,
    port: FakePort,
    native: NativeAuthorization,
) -> LocalBuildAgentService:
    return LocalBuildAgentService(
        root / "private",
        PROJECT,
        transport,
        {stage: port for stage in CORE_STAGES + STUDIO_STAGES[:2]},
        {"synthetic": "v1"},
        input_authority=authority,
        accepted_source_roots=(accepted,),
        native_authorization=native,
    )


def _start_revision(
    root: Path,
    transport: RevisionTransport,
    authority: FakeInputAuthority,
    accepted: Path,
    port: FakePort,
) -> tuple[LocalBuildAgentService, str]:
    existing = {p.stem for p in (root / "private" / "snapshots").glob("*.json")}
    prior_calls = port.calls
    denied = NativeAuthorization(
        PROJECT,
        "0" * 64,
        "f" * 64,
        f"synthetic-{transport.requested_job}",
        True,
        job_id=transport.requested_job,
        target_id=transport.data["targetId"],
    )
    assert (
        _revision_agent(root, transport, authority, accepted, port, denied).run_one(
            transport.requested_job
        )
        == "needs_action"
    )
    assert port.calls == prior_calls
    snapshots = {p.stem for p in (root / "private" / "snapshots").glob("*.json")}
    created = snapshots - existing
    assert len(created) == 1
    snapshot_id = created.pop()
    approved = NativeAuthorization(
        PROJECT,
        snapshot_id,
        "f" * 64,
        f"synthetic-{transport.requested_job}",
        True,
        job_id=transport.requested_job,
        target_id=transport.data["targetId"],
    )
    agent = _revision_agent(root, transport, authority, accepted, port, approved)
    return agent, snapshot_id


def test_two_studio_revisions_retain_old_target_and_frozen_source_bytes(
    tmp_path: Path,
) -> None:
    """The local staged chain proves isolation, NOT a real Resolve readback."""
    job_b = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
    target_b = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    port = FakePort()
    first, authority_a, accepted_a = _revision(tmp_path, JOB, TARGET, 2, "v1")
    agent_a, snapshot_a = _start_revision(
        tmp_path, first, authority_a, accepted_a, port
    )
    for stage_index in range(7):
        assert agent_a.run_one(JOB, resumed_epoch=1, resumed_digest=SNAPSHOT) == (
            "complete" if stage_index == 6 else "queued"
        )
    assert port.calls == 7
    root = tmp_path / "private"
    bytes_a = {
        str(path.relative_to(root)): path.read_bytes()
        for parent in (root / "outputs" / JOB, root / "inputs" / JOB)
        for path in parent.rglob("*")
        if path.is_file()
    }
    assert bytes_a
    assert (root / "inputs" / JOB / f"source-{TARGET}.bin").read_bytes() == (
        b"public synthetic source bytes v1"
    )

    second, authority_b, accepted_b = _revision(tmp_path, job_b, target_b, 3, "v2")
    agent_b, snapshot_b = _start_revision(
        tmp_path, second, authority_b, accepted_b, port
    )
    assert snapshot_b != snapshot_a
    for stage_index in range(7):
        assert agent_b.run_one(job_b, resumed_epoch=1, resumed_digest=SNAPSHOT) == (
            "complete" if stage_index == 6 else "queued"
        )
    assert port.calls == 14
    assert (root / "inputs" / job_b / f"source-{TARGET}.bin").read_bytes() == (
        b"public synthetic source bytes v2"
    )
    assert (
        json.loads((root / "inputs" / job_b / "submission.json").read_text())[
            "targetId"
        ]
        == target_b
    )
    assert {
        str(path.relative_to(root)): path.read_bytes()
        for parent in (root / "outputs" / JOB, root / "inputs" / JOB)
        for path in parent.rglob("*")
        if path.is_file()
    } == bytes_a
    for transport in (first, second):
        assert transport.claims == 1
        assert all(status != "verified_native" for _, status, _, _ in transport.reports)


def test_next_studio_stage_refuses_revoked_role_or_source(tmp_path: Path) -> None:
    transport, authority, accepted = _revision(tmp_path, JOB, TARGET, 2, "v1")
    port = FakePort()
    agent, _snapshot = _start_revision(tmp_path, transport, authority, accepted, port)
    assert agent.run_one(JOB, resumed_epoch=1, resumed_digest=SNAPSHOT) == "queued"
    assert port.calls == 1
    transport.role_revoked = True
    with pytest.raises(AgentTransportRefusal, match="revoked producer role"):
        agent.run_one(JOB, resumed_epoch=1, resumed_digest=SNAPSHOT)
    transport.role_revoked = False
    authority.accepted.clear()
    with pytest.raises(AgentTransportRefusal, match="accepted source"):
        agent.run_one(JOB, resumed_epoch=1, resumed_digest=SNAPSHOT)
    assert port.calls == 1
