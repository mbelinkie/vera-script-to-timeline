"""#382: fake server and fake #157 stages, never real Resolve or providers."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pytest
from vera_timeline_agent.build_agent_service import (
    AgentCredentials,
    AgentTransportRefusal,
    LocalBuildAgentService,
    LoopbackBuildTransport,
)
from vera_timeline_agent.build_composition import (
    EffectState,
    FrozenBuildSnapshot,
    Inspection,
    StageEvidence,
)
from vera_timeline_agent.build_jobs import (
    CORE_STAGES,
    StageContext,
    publish_immutable_output,
)
from vera_timeline_agent.build_submission_inputs import AcceptedSourceFile

PROJECT = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
JOB = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
TARGET = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
SNAPSHOT = "sha256:" + "f" * 64
FIXTURE = Path(__file__).parent / "data/authoring_v2/compiler-dependencies-v2.json"


def digest(raw: str) -> str:
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def manifest(mode: str = "free") -> dict[str, Any]:
    document = json.dumps({"projectId": PROJECT, "id": JOB})
    settings = json.dumps({"projectId": PROJECT, "profile": "synthetic"})
    return {
        "projectId": PROJECT,
        "jobId": JOB,
        "targetId": TARGET,
        "snapshotDigest": SNAPSHOT,
        "documentJson": document,
        "documentDigest": digest(document),
        "documentRevision": 2,
        "settingsJson": settings,
        "settingsDigest": digest(settings),
        "settingsRevision": 1,
        "selectedSources": [],
        "buildClass": "preview",
        "mode": mode,
    }


def complete_dependencies(value: dict[str, Any]) -> dict[str, Any]:
    """An explicit complete synthetic fixture, not a production default."""
    result = cast(dict[str, Any], json.loads(FIXTURE.read_text()))
    result["build"]["buildId"] = value["jobId"]
    result["build"]["buildClass"] = value["buildClass"]
    result["document"].update(
        {
            "documentId": json.loads(value["documentJson"])["id"],
            "projectId": value["projectId"],
            "revision": value["documentRevision"],
            "contentHash": value["documentDigest"],
            "settingsHash": value["settingsDigest"],
        }
    )
    result["authoringDefaults"]["settingsHash"] = value["settingsDigest"]
    result["occurrenceResolutions"] = []
    result["preparedMedia"] = []
    return result


@dataclass
class FakeInputAuthority:
    transport: FakeTransport
    dependencies: dict[str, Any] | None = None
    accepted: dict[str, AcceptedSourceFile] = field(default_factory=dict)

    def accepted_source(
        self, project_id: str, source_id: str, revision: str
    ) -> AcceptedSourceFile | None:
        return self.accepted.get(source_id)

    def frozen_dependencies(
        self, project_id: str, job_id: str
    ) -> dict[str, Any] | None:
        return (
            self.dependencies
            if self.dependencies is not None
            else complete_dependencies(self.transport.data)
        )


@dataclass
class FakeTransport:
    data: dict[str, Any] = field(default_factory=manifest)
    reports: list[tuple[str, str, str | None, str | None]] = field(default_factory=list)
    inspections: list[tuple[str, str]] = field(default_factory=list)
    claims: int = 0
    reads: int = 0
    fail_on_read: int = -1

    def poll(self) -> list[str]:
        return [JOB]

    def claim(self, job_id: str) -> tuple[int, str]:
        assert job_id == JOB
        self.claims += 1
        return 1, SNAPSHOT

    def frozen(self, job_id: str, epoch: int) -> dict[str, Any]:
        assert (job_id, epoch) == (JOB, 1)
        self.reads += 1
        if self.reads == self.fail_on_read:
            raise AgentTransportRefusal("revoked lease")
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
        assert (job_id, epoch) == (JOB, 1)
        self.reports.append((stage, status, receipt_digest, reason))

    def inspect(self, job_id: str, epoch: int, stage: str, digest: str) -> None:
        assert (job_id, epoch) == (self.data["jobId"], 1)
        self.inspections.append((stage, digest))


@dataclass
class FakePort:
    calls: int = 0
    uncertain: bool = False

    def _effect(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> Path:
        return (
            snapshot.write_root / context.job_id / context.stage / "synthetic-only.txt"
        )

    def inspect(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> Inspection:
        if self.uncertain:
            return Inspection(
                EffectState.UNCERTAIN, reason="synthetic uncertain result"
            )
        path = self._effect(context, snapshot)
        if not path.exists():
            return Inspection(EffectState.ABSENT)
        if path.read_bytes() != context.stage_key.encode():
            return Inspection(EffectState.UNCERTAIN, reason="synthetic mismatch")
        return Inspection(
            EffectState.VERIFIED,
            StageEvidence(
                adapter_id="synthetic",
                adapter_version="v1",
                inputs={"document": snapshot.file("document")},
                outputs={"synthetic": path},
            ),
        )

    def execute(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> None:
        self.calls += 1
        publish_immutable_output(
            self._effect(context, snapshot), context.stage_key.encode()
        )


def service(
    tmp_path: Path,
    transport: FakeTransport,
    port: FakePort | None = None,
    *,
    input_authority: FakeInputAuthority | None = None,
    accepted_source_roots: tuple[Path, ...] = (),
) -> LocalBuildAgentService:
    ports = {stage: port for stage in CORE_STAGES} if port else {}
    return LocalBuildAgentService(
        tmp_path / "private",
        PROJECT,
        transport,
        ports,
        {"synthetic": "v1"} if port else {},
        input_authority=input_authority or FakeInputAuthority(transport),
        accepted_source_roots=accepted_source_roots,
    )


def test_one_local_stage_is_durable_on_restart_without_duplicate_effect(
    tmp_path: Path,
) -> None:
    transport, port = FakeTransport(), FakePort()
    first = service(tmp_path, transport, port)
    assert first.run_one(JOB) == "queued"
    assert port.calls == 1
    assert transport.reports[0] == (CORE_STAGES[0], "running", None, None)
    assert transport.reports[1][0:2] == (CORE_STAGES[0], "running")
    assert transport.reports[1][2] is not None
    assert transport.reports[1][2].startswith("sha256:")
    restarted = service(tmp_path, transport, port)
    assert restarted.run_one(JOB, resumed_epoch=1, resumed_digest=SNAPSHOT) == "queued"
    assert port.calls == 2  # next stage, no replay of the first stage
    assert restarted.store.status(PROJECT, _job(restarted))["status"] == "queued"
    assert transport.claims == 1


def _job(agent: LocalBuildAgentService) -> str:
    # The local job ID is durable and distinct from the server submission UUID.
    with agent.store._connection() as conn:
        return str(conn.execute("SELECT id FROM jobs").fetchone()[0])


def test_uncertain_port_retains_waiting_with_no_effect_or_native_success(
    tmp_path: Path,
) -> None:
    transport, port = FakeTransport(), FakePort(uncertain=True)
    agent = service(tmp_path, transport, port)
    assert agent.run_one(JOB) == "waiting"
    assert port.calls == 0
    assert agent.store.status(PROJECT, _job(agent))["status"] == "waiting"
    assert transport.reports[-1] == (
        CORE_STAGES[0],
        "waiting_reconcile",
        None,
        "local_stage_unverified",
    )
    assert agent.run_one(JOB, resumed_epoch=1, resumed_digest=SNAPSHOT) == "waiting"
    assert port.calls == 0


def test_no_adapter_or_studio_never_run_native_or_provider(tmp_path: Path) -> None:
    transport = FakeTransport()
    agent = service(tmp_path, transport)
    assert agent.run_one(JOB) == "needs_action"
    assert transport.reports == [
        ("transport", "needs_action", None, "native_or_adapter_authorization_required")
    ]
    transport.data = manifest("studio")
    port = FakePort()
    with_port = service(tmp_path, transport, port)
    assert (
        with_port.run_one(JOB, resumed_epoch=1, resumed_digest=SNAPSHOT)
        == "needs_action"
    )
    assert port.calls == 0


@pytest.mark.parametrize(
    "fault", ["document", "settings", "digest", "project", "pins", "claim"]
)
def test_corrupt_or_unapproved_manifest_refused_before_any_effect(
    tmp_path: Path, fault: str
) -> None:
    transport, port = FakeTransport(), FakePort()
    if fault == "document":
        transport.data["documentJson"] += " "
    elif fault == "settings":
        transport.data["settingsJson"] += " "
    elif fault == "digest":
        transport.data["snapshotDigest"] = digest("altered")
    elif fault == "project":
        transport.data["projectId"] = TARGET
    elif fault == "pins":
        transport.data["selectedSources"] = [{"sourceId": TARGET}]
    else:
        transport.data["targetId"] = "not-a-uuid"
    with pytest.raises(AgentTransportRefusal):
        service(tmp_path, transport, port).run_one(JOB)
    assert port.calls == 0
    assert transport.reports == []


def test_expired_or_revoked_remote_lease_fails_closed_on_restart(
    tmp_path: Path,
) -> None:
    transport, port = FakeTransport(fail_on_read=2), FakePort()
    with pytest.raises(AgentTransportRefusal):
        service(tmp_path, transport, port).run_one(JOB)
    assert port.calls == 0
    assert transport.reports == []


def test_private_paths_and_credential_shape(tmp_path: Path) -> None:
    token = "sttag_" + "A" * 43
    credential = AgentCredentials(PROJECT, token)
    assert token not in repr(credential)
    for url in (
        "http://localhost:4000",
        "https://127.0.0.1:4000",
        "http://127.0.0.2:4000",
        "http://127.0.0.1:4000/path",
        "http://127.0.0.1:4000@attacker.test:4000",
        "http://127.0.0.1:80",
    ):
        with pytest.raises(AgentTransportRefusal):
            LoopbackBuildTransport(url, credential)
    assert LoopbackBuildTransport("http://127.0.0.1:4500", credential).poll is not None
    directory = tmp_path / "private"
    directory.mkdir(mode=0o755)
    os.chmod(directory, 0o755)
    with pytest.raises(AgentTransportRefusal):
        service(tmp_path, FakeTransport())
    directory.chmod(0o700)
    link = tmp_path / "linked"
    link.symlink_to(directory, target_is_directory=True)
    with pytest.raises(AgentTransportRefusal):
        LocalBuildAgentService(link, PROJECT, FakeTransport())


def test_mismatched_restart_receipt_does_not_claim_or_mutate(tmp_path: Path) -> None:
    transport, port = FakeTransport(), FakePort()
    with pytest.raises(AgentTransportRefusal):
        service(tmp_path, transport, port).run_one(
            JOB, resumed_epoch=1, resumed_digest=digest("different")
        )
    assert port.calls == 0
    assert transport.claims == 0


def test_missing_compiler_metadata_cannot_fall_back_to_placeholder(
    tmp_path: Path,
) -> None:
    transport, port = FakeTransport(), FakePort()
    agent = LocalBuildAgentService(
        tmp_path / "private",
        PROJECT,
        transport,
        {stage: port for stage in CORE_STAGES},
        {"synthetic": "v1"},
    )
    with pytest.raises(AgentTransportRefusal, match="trusted compiler metadata"):
        agent.run_one(JOB)
    assert port.calls == 0
