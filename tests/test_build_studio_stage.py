"""No real Resolve mutation: fake connected results and retained target identity."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from issue177_package_fixture import make_package_case
from vera_timeline_agent.build_composition import (
    EffectState,
    FrozenBuildSnapshot,
    SnapshotRepository,
)
from vera_timeline_agent.build_jobs import (
    NeedsAction,
    StageContext,
    UncertainResult,
)
from vera_timeline_agent.build_studio_stage import (
    BuildStudioStagePort,
    NativeAuthorization,
    VerifyStudioStagePort,
    _HostReservation,
)
from vera_timeline_agent.workflow_package import sha256
from vera_timeline_agent.workflow_v2_cli import attest_package_v2


@dataclass
class FakeConnectedStudio:
    target: dict[str, Any]
    digest: str
    preflight_ok: bool = True
    unknown: bool = False
    starts: int = 0
    readbacks: int = 0
    external_verified: bool = False

    def verified(self) -> dict[str, Any]:
        return {
            "status": "verified",
            "verified": True,
            "discrepancies": [],
            "attestationSha256": self.digest,
            "buildId": self.target["buildId"],
            "projectName": self.target["projectName"],
            "timelineName": self.target["timelineName"],
        }

    def preflight(
        self, attestation: Path, digest: str, request_id: str
    ) -> dict[str, Any]:
        return {
            "status": "preflight_passed" if self.preflight_ok else "stopped_safely",
            "attestationSha256": digest,
        }

    def start(self, attestation: Path, digest: str, request_id: str) -> dict[str, Any]:
        self.starts += 1
        return self.verified()

    def inspect_build(
        self, attestation: Path, digest: str, request_id: str
    ) -> dict[str, Any]:
        return (
            {"status": "unknown", "verified": False}
            if self.unknown or not (self.starts or self.external_verified)
            else self.verified()
        )

    def readback(
        self, attestation: Path, digest: str, request_id: str
    ) -> dict[str, Any]:
        self.readbacks += 1
        return (
            {"status": "unknown", "verified": False}
            if self.unknown
            else self.verified()
        )


StudioCase = tuple[
    FrozenBuildSnapshot,
    NativeAuthorization,
    FakeConnectedStudio,
    Callable[[str], StageContext],
    Path,
]


@pytest.fixture
def setup(tmp_path: Path) -> StudioCase:
    case = make_package_case(tmp_path / "fixture")
    from json import loads

    frozen_deps = loads(case.dependencies_path.read_bytes())
    project = frozen_deps["document"]["projectId"]
    build = frozen_deps["build"]["buildId"]
    repo = SnapshotRepository(
        tmp_path / "snapshots",
        read_roots=(case.document_path.parent,),
        write_root=tmp_path / "build-outputs",
        live_head=lambda _: (1, "a" * 64, "rev-1"),
        live_settings=lambda _: "c" * 64,
    )
    snap = repo.freeze(
        project_id=project,
        mode="studio",
        build_id=build,
        build_class="preview",
        settings_hash="c" * 64,
        inputs={"document": case.document_path, "dependencies": case.dependencies_path},
        adapter_versions={
            "resolve-v2": "injected-none/v2",
            "resolve-v2-readback": "injected-none-readback/v2",
        },
    )
    job = "studio-job"
    case.project_root = snap.write_root / job / "package"
    case.build()
    att = attest_package_v2(
        case.project_root, snap.write_root / job / "v2-attestation.json"
    )
    digest = sha256(att)
    target = loads(att.read_bytes())
    auth = NativeAuthorization(
        project,
        snap.snapshot_id,
        digest,
        "one-time-request-1",
        approved_nonproduction=True,
        route="None",
    )
    driver = FakeConnectedStudio(target, digest)

    def context(stage: str) -> StageContext:
        return StageContext(
            project,
            job,
            snap.snapshot_id,
            stage,
            hashlib.sha256(f"{project}\0{job}\0{stage}".encode()).hexdigest(),
            tmp_path / "job-receipts" / stage / "output",
            1,
            1,
            lambda _: None,
            lambda: None,
        )

    return snap, auth, driver, context, tmp_path / "host-lock"


def test_native_studio_preflight_explicit_one_use_then_separate_readback(
    setup: StudioCase,
) -> None:
    snapshot, auth, driver, ctx, host = setup
    build = BuildStudioStagePort(auth, driver, host_state=host)
    assert (
        build.inspect(ctx("building_resolve_timeline"), snapshot).state
        == EffectState.ABSENT
    )
    build.execute(ctx("building_resolve_timeline"), snapshot)
    assert driver.starts == 1
    finished = host / f"composition-finished-{auth.request_id}.json"
    assert not finished.exists(), "native build alone cannot release reservation"
    assert (
        build.inspect(ctx("building_resolve_timeline"), snapshot).state
        == EffectState.VERIFIED
    )
    with pytest.raises(UncertainResult, match="one-use"):
        build.execute(ctx("building_resolve_timeline"), snapshot)
    assert driver.starts == 1
    verify = VerifyStudioStagePort(auth, driver, host_state=host)
    assert (
        verify.inspect(ctx("verifying_timeline"), snapshot).state == EffectState.ABSENT
    )
    verify.execute(ctx("verifying_timeline"), snapshot)
    assert (
        verify.inspect(ctx("verifying_timeline"), snapshot).state
        == EffectState.VERIFIED
    )
    assert finished.is_file(), "independent native readback releases reservation"
    assert driver.readbacks >= 2


def test_native_no_authorization_or_failed_preflight_never_mutates(
    setup: StudioCase,
) -> None:
    from dataclasses import replace

    snapshot, auth, driver, ctx, host = setup
    blocked = BuildStudioStagePort(
        replace(auth, approved_nonproduction=False), driver, host_state=host
    )
    with pytest.raises(NeedsAction, match="explicit"):
        blocked.execute(ctx("building_resolve_timeline"), snapshot)
    assert driver.starts == 0
    driver.preflight_ok = False
    build = BuildStudioStagePort(auth, driver, host_state=host)
    with pytest.raises(NeedsAction, match="preflight"):
        build.execute(ctx("building_resolve_timeline"), snapshot)
    assert driver.starts == 0
    assert (
        build.inspect(ctx("building_resolve_timeline"), snapshot).state
        == EffectState.UNCERTAIN
    )


def test_lost_native_response_recovers_only_on_independent_connected_readback(
    setup: StudioCase,
) -> None:

    snapshot, auth, driver, ctx, host = setup
    build = BuildStudioStagePort(auth, driver, host_state=host)
    context = ctx("building_resolve_timeline")
    intent = snapshot.write_root / context.job_id / context.stage / "intent.json"
    from vera_timeline_agent.build_jobs import publish_immutable_output
    from vera_timeline_agent.build_stage_receipt import canonical_json

    publish_immutable_output(
        intent,
        canonical_json(
            {
                "schemaVersion": "vera-native-build-intent/v1",
                "stageKey": context.stage_key,
                "requestId": auth.request_id,
                "attestationSha256": auth.attestation_sha256,
                "snapshotSha256": snapshot.snapshot_id,
                "projectName": driver.target["projectName"],
            }
        ),
    )
    driver.unknown = True
    assert build.inspect(context, snapshot).state == EffectState.UNCERTAIN
    assert driver.starts == 0
    with pytest.raises(UncertainResult):
        build.execute(context, snapshot)
    driver.unknown = False
    driver.external_verified = True
    assert build.inspect(context, snapshot).state == EffectState.VERIFIED
    assert driver.starts == 0
    assert (
        snapshot.write_root / context.job_id / context.stage / "native-result.json"
    ).is_file()


def test_partial_native_readback_is_never_a_verified_result(
    setup: StudioCase,
) -> None:
    snap, auth, driver, ctx, host = setup
    build = BuildStudioStagePort(auth, driver, host_state=host)
    build.execute(ctx("building_resolve_timeline"), snap)
    driver.unknown = True
    assert (
        build.inspect(ctx("building_resolve_timeline"), snap).state
        == EffectState.UNCERTAIN
    )
    with pytest.raises(NeedsAction, match="save/reopen discrepancy"):
        VerifyStudioStagePort(auth, driver, host_state=host).execute(
            ctx("verifying_timeline"), snap
        )
    assert not (host / f"composition-finished-{auth.request_id}.json").exists()
    with pytest.raises(NeedsAction, match="unresolved effects"):
        _HostReservation(host).reserve("different-target", "f" * 64)


def test_finished_native_request_id_cannot_be_reused_for_another_target(
    tmp_path: Path,
) -> None:
    reservation = _HostReservation(tmp_path / "host-lock")
    reservation.reserve("single-use", "a" * 64)
    reservation.finish("single-use", "a" * 64)
    with pytest.raises(NeedsAction, match="already consumed"):
        reservation.reserve("single-use", "b" * 64)
    with pytest.raises(NeedsAction, match="already consumed"):
        reservation.reserve("single-use", "a" * 64)
    from vera_timeline_agent.build_stage_receipt import canonical_json

    assert (
        tmp_path / "host-lock" / "composition-finished-single-use.json"
    ).read_bytes() == canonical_json(
        {"requestId": "single-use", "attestationSha256": "a" * 64, "status": "verified"}
    )


def test_previous_verified_request_reinspection_does_not_release_new_host_slot(
    tmp_path: Path,
) -> None:
    reservation = _HostReservation(tmp_path / "host-lock")
    reservation.reserve("first", "a" * 64)
    reservation.finish("first", "a" * 64)
    reservation.reserve("second", "b" * 64)
    reservation.finish("first", "a" * 64)
    with pytest.raises(NeedsAction, match="unresolved effects"):
        reservation.reserve("third", "c" * 64)
    with pytest.raises(UncertainResult, match="differs"):
        reservation.finish("first", "c" * 64)
