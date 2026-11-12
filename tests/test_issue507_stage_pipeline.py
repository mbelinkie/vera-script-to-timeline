"""#507 phase 2: mode-preserving one-stage dispatch, with zero real effects."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_issue382_build_agent import (
    JOB,
    PROJECT,
    SNAPSHOT,
    FakeInputAuthority,
    FakePort,
    FakeTransport,
    _job,
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
    assert not (tmp_path / "private" / "snapshots").exists()
    assert transport.reports == [
        ("transport", "needs_action", None, "native_or_adapter_authorization_required")
    ]


def test_studio_requires_exact_frozen_snapshot_before_first_effect(
    tmp_path: Path,
) -> None:
    transport = FakeTransport(data=manifest("studio"))
    port = FakePort()
    wrong = NativeAuthorization(PROJECT, "0" * 64, "f" * 64, "request-one", True)
    agent = fake_agent(tmp_path, transport, port, native=wrong)
    assert agent.run_one(JOB) == "needs_action"
    assert port.calls == 0
    snapshots = list((tmp_path / "private" / "snapshots").glob("*.json"))
    assert len(snapshots) == 1
    snapshot_id = snapshots[0].stem
    assert agent.store.database.exists()

    approved = NativeAuthorization(PROJECT, snapshot_id, "f" * 64, "request-one", True)
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
