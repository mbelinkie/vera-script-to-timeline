"""Phase 3: synthetic #302 Local parent and exact Studio permission fences."""

from __future__ import annotations

import json
import os
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_build_studio_stage import (
    StudioCase,
    setup,  # noqa: F401 - imported pytest fixture
)
from vera_timeline_agent import build_studio_parent_driver as parent_driver
from vera_timeline_agent import (
    resolve_native_owner,
    workflow_v2_cli,
    workflow_v2_parent,
)
from vera_timeline_agent.build_composition import EffectState
from vera_timeline_agent.build_jobs import BuildJobError, NeedsAction, UncertainResult
from vera_timeline_agent.build_studio_parent_driver import ParentStudioDriver
from vera_timeline_agent.build_studio_stage import (
    BuildStudioStagePort,
    VerifyStudioStagePort,
)
from vera_timeline_agent.workflow_package import sha256, write_immutable_json


@pytest.fixture
def local(
    request: pytest.FixtureRequest, tmp_path: Path
) -> tuple[StudioCase, ParentStudioDriver]:
    snapshot, auth, fake, context, host = request.getfixturevalue("setup")
    attestation = (
        snapshot.write_root
        / context("building_resolve_timeline").job_id
        / "v2-attestation.json"
    )
    request_path = tmp_path / "release" / "vera-delivery-v2" / "request.json"
    request_path.parent.mkdir(parents=True)
    write_immutable_json(
        request_path,
        {
            "schemaVersion": "vera-injected-delivery-request/v2",
            "releaseSha256": "a" * 64,
            "attestationPath": str(attestation),
            "attestationSha256": sha256(attestation),
            "packageDir": str(
                snapshot.write_root
                / context("building_resolve_timeline").job_id
                / "package"
            ),
            "projectName": fake.target["projectName"],
            "timelineName": fake.target["timelineName"],
            "action": "build",
            "authorizeNewNonproduction": True,
            "externalScripting": "Local",
            "evidenceDir": str(tmp_path / "parent-evidence"),
        },
    )
    local_auth = replace(
        auth,
        route="Local",
        job_id=snapshot.build_id,
        target_id="fresh-target",
        expires_at=time.time() + 3600,
        current_authority=lambda: True,
    )
    driver = ParentStudioDriver(
        request_path,
        sha256(request_path),
        local_auth.request_id,
        Path("/synthetic/ResolvePython"),
    )
    return (snapshot, local_auth, fake, context, host), driver


def test_busy_native_owner_allows_fresh_authorization_but_killed_worker_does_not(
    local: tuple[StudioCase, ParentStudioDriver],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (snapshot, auth, _fake, ctx, host), driver = local
    monkeypatch.setattr(workflow_v2_parent, "PARENT_STATE_ROOT", host)
    monkeypatch.setattr(
        resolve_native_owner, "OWNER_LOCK_PATH", host / "native-owner.lock"
    )
    manifest = tmp_path / "release.json"
    manifest.write_bytes(b"synthetic release manifest")
    request = json.loads(driver.request_path.read_bytes())
    request["releaseSha256"] = sha256(manifest)
    request_path = tmp_path / "fresh-release" / "vera-delivery-v2" / "request.json"
    request_path.parent.mkdir(parents=True)
    write_immutable_json(request_path, request)
    fresh_auth = replace(auth, request_id="fresh-request")
    fresh_driver = ParentStudioDriver(
        request_path, sha256(request_path), fresh_auth.request_id, driver.resolve_python
    )
    monkeypatch.setattr(workflow_v2_cli, "_verify_release", lambda _release: manifest)
    monkeypatch.setattr(
        resolve_native_owner, "preflight_independent_disposable", lambda _target: None
    )
    context = ctx("building_resolve_timeline")
    intent = snapshot.write_root / context.job_id / context.stage / "intent.json"
    evidence = Path(request["evidenceDir"])
    child_fds: list[int] = []

    def spawn(_args: list[str], *, pass_fds: tuple[int, ...], **_kwargs: Any) -> object:
        assert json.loads(intent.read_bytes())["requestId"] == fresh_auth.request_id
        assert (evidence / "parent.json").is_file()
        child_fds.extend(os.dup(fd) for fd in pass_fds)
        return object()

    monkeypatch.setattr(workflow_v2_parent.subprocess, "Popen", spawn)
    build = BuildStudioStagePort(auth, driver, host_state=host)
    holder = resolve_native_owner.acquire_native_owner()
    try:
        with pytest.raises(NeedsAction, match="Resolve is busy"):
            build.execute(context, snapshot)
        with pytest.raises(resolve_native_owner.NativeOwnerError) as blocked:
            resolve_native_owner.acquire_native_owner()
        assert blocked.value.reason == "owner_busy"
    finally:
        resolve_native_owner.release_native_owner(holder)
    assert build.inspect(context, snapshot).state == EffectState.ABSENT
    assert not (host / "composition-active.json").exists()
    assert not (evidence / "parent.json").exists()
    assert not child_fds

    fresh = BuildStudioStagePort(fresh_auth, fresh_driver, host_state=host)
    try:
        with pytest.raises(UncertainResult, match="never restart"):
            fresh.execute(context, snapshot)
        assert len(child_fds) == 2
        with pytest.raises(resolve_native_owner.NativeOwnerError) as blocked:
            resolve_native_owner.acquire_native_owner()
        assert blocked.value.reason == "owner_busy"
    finally:
        for fd in child_fds:
            os.close(fd)
    assert (
        workflow_v2_parent.status(request_path, sha256(request_path))["state"]
        == "unknown"
    )
    assert fresh.inspect(context, snapshot).state == EffectState.UNCERTAIN
    with pytest.raises(UncertainResult, match="one-use"):
        fresh.execute(context, snapshot)
    with pytest.raises(BuildJobError, match="identity changed"):
        build.inspect(context, snapshot)


def test_parent_live_is_one_dispatch_and_read_only_resume(
    local: tuple[StudioCase, ParentStudioDriver], monkeypatch: pytest.MonkeyPatch
) -> None:
    (snapshot, auth, fake, ctx, host), driver = local
    calls: list[str] = []
    status = {"state": "live", "verified": False}

    def start(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append("start")
        assert kwargs["independent_disposable"] is True
        host.mkdir()
        kwargs["before_dispatch"](host)
        return dict(status)

    def read(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append("read")
        return dict(status)

    def resume(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append("resume")
        return dict(status)

    monkeypatch.setattr(parent_driver, "start", start)
    monkeypatch.setattr(parent_driver, "status", read)
    monkeypatch.setattr(parent_driver, "wait", resume)
    build = BuildStudioStagePort(auth, driver, host_state=host)
    with pytest.raises(UncertainResult, match="never restart"):
        build.execute(ctx("building_resolve_timeline"), snapshot)
    assert calls == ["start"]
    assert (
        build.inspect(ctx("building_resolve_timeline"), snapshot).state
        == EffectState.UNCERTAIN
    )
    assert (
        driver.resume(
            snapshot.write_root
            / ctx("building_resolve_timeline").job_id
            / "v2-attestation.json",
            fake.digest,
            auth.request_id,
        )["verified"]
        is False
    )
    with pytest.raises(UncertainResult, match="one-use"):
        build.execute(ctx("building_resolve_timeline"), snapshot)
    assert calls.count("start") == 1
    assert not (host / f"composition-finished-{auth.request_id}.json").exists()

    status.update(state="terminal", verified=True, result=fake.verified())
    assert (
        build.inspect(ctx("building_resolve_timeline"), snapshot).state
        == EffectState.VERIFIED
    )
    verify = VerifyStudioStagePort(auth, driver, host_state=host)
    with pytest.raises(NeedsAction, match="independent connected"):
        verify.execute(ctx("verifying_timeline"), snapshot)
    assert not (host / f"composition-finished-{auth.request_id}.json").exists()
    driver.reopened_readback = lambda _path, _digest, _id: fake.verified()
    verify.execute(ctx("verifying_timeline"), snapshot)
    assert (
        verify.inspect(ctx("verifying_timeline"), snapshot).state
        == EffectState.VERIFIED
    )
    assert (host / f"composition-finished-{auth.request_id}.json").is_file()
    assert calls.count("start") == 1


@pytest.mark.parametrize(
    "alter, reason",
    [
        ("wrong_job", "job/snapshot"),
        ("wrong_target", "target"),
        ("expired", "expired"),
        ("stale", "stale"),
        ("missing_current", "current job/target"),
        ("missing_expiry", "current job/target"),
    ],
)
def test_local_authority_refuses_before_native_dispatch(
    local: tuple[StudioCase, ParentStudioDriver],
    alter: str,
    reason: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (snapshot, auth, _fake, ctx, host), driver = local
    monkeypatch.setattr(
        parent_driver, "start", lambda *_a, **_k: pytest.fail("must not start")
    )
    changes: dict[str, Any] = {
        "wrong_job": {"job_id": "different-job"},
        "wrong_target": {"target_id": "another-target"},
        "expired": {"expires_at": time.time() - 1},
        "stale": {"current_authority": lambda: False},
        "missing_current": {"current_authority": None},
        "missing_expiry": {"expires_at": None},
    }
    wrong = replace(auth, **changes[alter])
    with pytest.raises(NeedsAction, match=reason):
        BuildStudioStagePort(wrong, driver, host_state=host).execute(
            ctx("building_resolve_timeline"), snapshot
        )
    assert not host.exists()


def test_local_expired_or_unknown_lease_refuses_before_reservation(
    local: tuple[StudioCase, ParentStudioDriver],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (snapshot, auth, _fake, ctx, host), driver = local
    monkeypatch.setattr(
        parent_driver, "start", lambda *_a, **_k: pytest.fail("dispatched")
    )

    def revoked() -> None:
        raise BuildJobError("renewal rejected: lease is stale")

    lost = replace(ctx("building_resolve_timeline"), renew_lease=revoked)
    with pytest.raises(BuildJobError, match="lease is stale"):
        BuildStudioStagePort(auth, driver, host_state=host).execute(lost, snapshot)
    assert not host.exists()


def test_unresolved_host_parent_blocks_a_second_native_target(
    local: tuple[StudioCase, ParentStudioDriver], monkeypatch: pytest.MonkeyPatch
) -> None:
    (snapshot, auth, _fake, ctx, host), driver = local
    host.mkdir()
    (host / "active.json").write_text(
        json.dumps(
            {
                "requestPath": str(host / "missing-request.json"),
                "requestSha256": "a" * 64,
            }
        )
    )
    monkeypatch.setattr(workflow_v2_parent, "PARENT_STATE_ROOT", host)
    monkeypatch.setattr(
        resolve_native_owner,
        "acquire_native_owner",
        lambda: pytest.fail("unresolved parent must block before native acquisition"),
    )
    with pytest.raises(NeedsAction, match="another native parent"):
        BuildStudioStagePort(auth, driver, host_state=host).execute(
            ctx("building_resolve_timeline"), snapshot
        )
    assert not (
        snapshot.write_root / "studio-job" / "building_resolve_timeline" / "intent.json"
    ).exists()


def test_parent_request_target_or_digest_swap_is_refused(
    local: tuple[StudioCase, ParentStudioDriver], monkeypatch: pytest.MonkeyPatch
) -> None:
    (snapshot, auth, fake, ctx, host), driver = local
    monkeypatch.setattr(
        parent_driver, "start", lambda *_a, **_k: pytest.fail("dispatched")
    )
    attestation = (
        snapshot.write_root
        / ctx("building_resolve_timeline").job_id
        / "v2-attestation.json"
    )
    request = json.loads(driver.request_path.read_text())
    assert (
        driver.preflight(attestation, fake.digest, auth.request_id)["status"]
        == "preflight_passed"
    )
    with pytest.raises(NeedsAction, match="identity changed"):
        driver.preflight(attestation, fake.digest, "another-request")
    wrong = driver.request_path.parent / "wrong.json"
    request["timelineName"] = "another target"
    write_immutable_json(wrong, request)
    altered = ParentStudioDriver(
        wrong, sha256(wrong), auth.request_id, driver.resolve_python
    )
    with pytest.raises(NeedsAction, match="exact disposable"):
        altered.preflight(attestation, fake.digest, auth.request_id)
    with pytest.raises(ValueError, match="changed"):
        ParentStudioDriver(
            driver.request_path, "b" * 64, auth.request_id, driver.resolve_python
        ).preflight(attestation, fake.digest, auth.request_id)
    assert not host.exists()


def test_reused_completed_parent_request_cannot_be_credited_as_new_start(
    local: tuple[StudioCase, ParentStudioDriver], monkeypatch: pytest.MonkeyPatch
) -> None:
    (snapshot, auth, fake, _ctx, _host), driver = local
    request = json.loads(driver.request_path.read_text())
    evidence = Path(request["evidenceDir"])
    evidence.mkdir()
    (evidence / "parent.json").write_text("{}")
    monkeypatch.setattr(
        parent_driver, "start", lambda *_a, **_k: pytest.fail("old parent replayed")
    )
    attestation = snapshot.write_root / "studio-job" / "v2-attestation.json"
    with pytest.raises(UncertainResult, match="already consumed"):
        driver.start(attestation, fake.digest, auth.request_id)


def test_parent_result_without_this_dispatch_intent_is_refused(
    local: tuple[StudioCase, ParentStudioDriver], monkeypatch: pytest.MonkeyPatch
) -> None:
    (snapshot, auth, fake, ctx, host), driver = local
    # A standalone parent can consume the request between the adapter's
    # initial existence check and taking the shared dispatch lock.
    monkeypatch.setattr(
        parent_driver,
        "start",
        lambda *_a, **_k: {
            "state": "terminal",
            "verified": True,
            "result": fake.verified(),
        },
    )
    context = ctx("building_resolve_timeline")
    build = BuildStudioStagePort(auth, driver, host_state=host)
    with pytest.raises(UncertainResult, match="without this attempt's intent"):
        build.execute(context, snapshot)
    assert build.inspect(context, snapshot).state == EffectState.ABSENT
    assert not (host / "composition-active.json").exists()


@pytest.mark.parametrize(
    "state,verified",
    [
        ("busy", False),
        ("unknown", False),
        ("failed", False),
        ("not_started", False),
        ("terminal", False),
    ],
)
def test_parent_ambiguous_response_never_forges_verified_native_result(
    local: tuple[StudioCase, ParentStudioDriver],
    monkeypatch: pytest.MonkeyPatch,
    state: str,
    verified: bool,
) -> None:
    (snapshot, auth, fake, ctx, host), driver = local
    response: dict[str, Any] = {"state": state, "verified": verified}
    if state == "terminal":
        response["result"] = fake.verified()

    def start(*args: Any, **kwargs: Any) -> dict[str, Any]:
        host.mkdir()
        kwargs["before_dispatch"](host)
        return response

    monkeypatch.setattr(parent_driver, "start", start)
    monkeypatch.setattr(parent_driver, "status", lambda *_a, **_k: response)
    with pytest.raises(UncertainResult, match="never restart"):
        BuildStudioStagePort(auth, driver, host_state=host).execute(
            ctx("building_resolve_timeline"), snapshot
        )
    # Every ambiguous attempt has only its own immutable intent, never a
    # synthetic "verified" native-result file or a released host slot.
    status_dir = (
        snapshot.write_root
        / ctx("building_resolve_timeline").job_id
        / "building_resolve_timeline"
    )
    assert (status_dir / "intent.json").exists()
    assert not (status_dir / "native-result.json").exists()
    assert not (host / f"composition-finished-{auth.request_id}.json").exists()
