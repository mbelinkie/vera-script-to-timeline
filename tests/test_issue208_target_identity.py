"""Synthetic boundary evidence only; never an installed/operator qualification."""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import target_identity_v2 as identity
from vera_timeline_agent.workflow_v2_cli import build_release_v2


@pytest.mark.parametrize(
    "payload",
    [b"[]", b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b"{"],
)
def test_closed_parser_refuses_ambiguous_records(payload: bytes) -> None:
    with pytest.raises(ValueError):
        identity.ti_object(payload)


@pytest.mark.parametrize("value", ["", " ", "Name\x00", "Name\n", 1, True, None])
def test_names_and_uids_are_exact_bounded_native_strings(value: Any) -> None:
    with pytest.raises(ValueError):
        identity.ti_text(value)


def test_opaque_uid_is_not_normalized_or_uuid_parsed() -> None:
    assert identity.ti_text(" opaque uid ") == " opaque uid "
    assert identity.ti_text("Å") != identity.ti_text("A\u030a")


@pytest.mark.parametrize("attack", ["symlink", "hardlink", "directory", "oversize"])
def test_bounded_descriptor_reads(tmp_path: Path, attack: str) -> None:
    source = tmp_path / "record.json"
    source.write_bytes(b"{}")
    if attack == "symlink":
        alias = tmp_path / "alias.json"
        alias.symlink_to(source)
        source = alias
    elif attack == "hardlink":
        os.link(source, tmp_path / "alias.json")
    elif attack == "directory":
        source = tmp_path
    else:
        source.write_bytes(b"x" * (identity.TI_MAX_BYTES + 1))
    with pytest.raises(ValueError):
        identity.ti_read(source)


def test_publication_is_exclusive_private_and_never_overwrites(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    identity.ti_private(root)
    path = root / "result.json"
    identity.ti_publish(path, {"ok": True})
    before = path.read_bytes()
    assert path.stat().st_mode & 0o777 == 0o400
    with pytest.raises(ValueError, match="collision"):
        identity.ti_publish(path, {"ok": False})
    assert path.read_bytes() == before


@pytest.mark.parametrize("offset", [-1, 1800, 1801])
def test_future_or_expired_authority_refuses(offset: int) -> None:
    now = datetime.now(UTC)
    issued = now - timedelta(seconds=offset)
    with pytest.raises(ValueError):
        identity.ti_window(
            issued.isoformat(), (issued + timedelta(seconds=1800)).isoformat(), now
        )


def test_wrong_window_and_timezone_refuse() -> None:
    now = datetime.now(UTC)
    for expiry in (now - timedelta(seconds=1), now + timedelta(seconds=1801)):
        with pytest.raises(ValueError):
            identity.ti_window(now.isoformat(), expiry.isoformat(), now)
    with pytest.raises(ValueError):
        identity.ti_time("2026-10-14T12:00:00")


def test_wallclock_rollback_refuses_without_native_calls() -> None:
    now = datetime.now(UTC)
    clock = identity.TIClock(now, 100.0)
    with pytest.raises(ValueError, match="rollback"):
        clock.check(now - timedelta(seconds=1), 101.0)


def test_bootstrap_provenance_is_independent_and_matches_closed_validator() -> None:
    repo = Path(__file__).resolve().parents[1]
    blocks = []
    for path in (
        repo / "python/vera_timeline_agent/target_identity_v2.py",
        repo / "integrations/resolve/VERA Delivery v2.py",
    ):
        text = path.read_text()
        start = text.index("# BEGIN IDENTITY PROVENANCE")
        end = text.index("# END IDENTITY PROVENANCE")
        blocks.append(ast.dump(ast.parse(text[start:end])))
    assert blocks[0] == blocks[1]


def inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Explicit synthetic operator/installed preparation; no real authority."""
    real = Path(__file__).resolve().parents[1]
    repo = tmp_path / "repository"
    for name in identity.TI_SOURCE_FILES:
        dest = repo / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(real / name, dest)
    release = tmp_path / "release"
    build_release_v2(release)
    installed = tmp_path / "installed"
    shutil.copytree(release, installed)
    approval = tmp_path / "identity-approval.json"
    shutil.copyfile(real / "docs/verification/issue-207/acceptance.json", approval)
    authority = identity.create_identity_authority(
        tmp_path / "authority.json",
        release_root=release,
        installed_root=installed,
        repository_root=repo,
        evidence_dir=tmp_path / "evidence",
        approval_path=approval,
        target={
            "projectName": "Synthetic project",
            "timelineName": "Synthetic timeline",
        },
        operator="Synthetic operator (test only)",
        confirm_saved_disposable=True,
        confirm_read_only=True,
        external_scripting_none=True,
    )
    host = identity.prepare_identity_request(
        tmp_path / "request.json", authority_path=authority
    )
    request = installed / "vera-delivery-v2/request.json"
    shutil.copyfile(host, request)
    request.chmod(0o400)
    return request, authority, repo, installed


class Native:
    def __init__(self, source: str, calls: list[str], values: dict[str, Any]) -> None:
        self.source, self.calls, self.values = source, calls, values

    def __getattr__(self, name: str) -> Any:
        if name not in identity._FiniteReads.ALLOWED:
            self.calls.append(f"FORBIDDEN:{self.source}.{name}")
            raise AssertionError(f"forbidden attempt: {name}")

        def getter() -> Any:
            self.calls.append(f"{self.source}.{name}")
            value = self.values[name]
            return value() if callable(value) else value

        return getter


def native() -> tuple[Native, Native, Native, Native, list[str]]:
    calls: list[str] = []
    timeline = Native(
        "timeline", calls, {"GetName": "Synthetic timeline", "GetUniqueId": "opaque-t"}
    )
    project = Native(
        "project",
        calls,
        {
            "GetName": "Synthetic project",
            "GetUniqueId": "opaque-p",
            "GetCurrentTimeline": timeline,
        },
    )
    manager = Native("manager", calls, {"GetCurrentProject": project})
    resolve = Native(
        "resolve",
        calls,
        {
            "GetProductName": "DaVinci Resolve Studio",
            "GetVersion": [21, 1, 1, 10, ""],
            "GetProjectManager": manager,
        },
    )
    return resolve, manager, project, timeline, calls


def run(request: Path, resolve: Any) -> dict[str, Any]:
    digest = identity.ti_digest(identity.ti_read(request))
    identity.ti_reserve(
        request, digest
    )  # Synthetic bootstrap, never actual WI evidence.
    report = identity.run_target_identity(
        resolve, request, expected_request_sha256=digest
    )
    return identity.ti_object(identity.ti_read(report))


def test_two_complete_finite_reads_are_unqualified(tmp_path: Path) -> None:
    request, _, _, _ = inputs(tmp_path)
    resolve, _, _, _, calls = native()
    result = run(request, resolve)
    assert result["status"] == "identity_observed"
    assert (
        result["qualified"]
        is result["verified"]
        is result["futureEffectsAuthorized"]
        is False
    )
    assert len(result["reads"]) == 2
    assert (
        result["reads"][0]["target"] == result["reads"][1]["target"] == result["target"]
    )
    assert result["target"]["projectUid"] == "opaque-p"
    assert calls.count("manager.GetCurrentProject") == 2
    assert not any(c.startswith("FORBIDDEN:") for c in calls)


@pytest.mark.parametrize(
    "attack",
    [
        "project-name",
        "project-absent",
        "timeline-name",
        "timeline-absent",
        "uid",
        "drift",
        "version",
        "product",
    ],
)
def test_source_tagged_target_refusals(tmp_path: Path, attack: str) -> None:
    request, _, _, _ = inputs(tmp_path)
    resolve, manager, project, timeline, calls = native()
    if attack == "project-name":
        project.values["GetName"] = "Wrong project"
    elif attack == "project-absent":
        manager.values["GetCurrentProject"] = None
    elif attack == "timeline-name":
        timeline.values["GetName"] = "Wrong timeline"
    elif attack == "timeline-absent":
        project.values["GetCurrentTimeline"] = None
    elif attack == "uid":
        timeline.values["GetUniqueId"] = True
    elif attack == "drift":
        values = iter(["opaque-t", "replacement-t"])
        timeline.values["GetUniqueId"] = lambda: next(values)
    elif attack == "version":
        resolve.values["GetVersion"] = [21, True, 1, 10, ""]
    else:
        resolve.values["GetProductName"] = "DaVinci Resolve"
    result = run(request, resolve)
    assert result["status"] == "stopped_safely" and result["target"] is None
    assert result["reason"]
    assert not any(c.startswith("FORBIDDEN:") for c in calls)
    if attack.startswith("project"):
        assert "project.GetCurrentTimeline" not in calls
        assert "project.GetUniqueId" not in calls
    if attack == "timeline-name":
        assert "timeline.GetUniqueId" not in calls
    if attack in {"version", "product"}:
        assert "resolve.GetProjectManager" not in calls


def test_source_drift_between_reads_has_no_usable_target(tmp_path: Path) -> None:
    request, _, repo, _ = inputs(tmp_path)
    resolve, _, _, timeline, calls = native()

    def drift() -> str:
        (repo / "python/vera_timeline_agent/target_identity_v2.py").write_text(
            "changed"
        )
        return "opaque-t"

    timeline.values["GetUniqueId"] = drift
    result = run(request, resolve)
    assert result["target"] is None and result["reason"] == "source drift"
    assert len(result["reads"]) == 1
    assert calls.count("manager.GetCurrentProject") == 1
    assert not any(c.startswith("FORBIDDEN:") for c in calls)


def test_replay_and_partial_invocations_never_resume(tmp_path: Path) -> None:
    request, _, _, _ = inputs(tmp_path)
    digest = identity.ti_digest(identity.ti_read(request))
    identity.ti_reserve(request, digest)
    with pytest.raises(ValueError, match="collision"):
        identity.ti_reserve(request, digest)
    resolve, _, _, _, calls = native()
    identity.run_target_identity(resolve, request, expected_request_sha256=digest)
    before = list(calls)
    with pytest.raises(ValueError, match="collision"):
        identity.run_target_identity(resolve, request, expected_request_sha256=digest)
    assert calls == before


@pytest.mark.parametrize(
    "attack", ["source", "approval", "authority", "request", "inventory"]
)
def test_drift_before_bootstrap_has_zero_native_attempts(
    tmp_path: Path, attack: str
) -> None:
    request, authority, repo, installed = inputs(tmp_path)
    digest = identity.ti_digest(identity.ti_read(request))
    resolve, _, _, _, calls = native()
    path = {
        "source": repo / "python/vera_timeline_agent/target_identity_v2.py",
        "approval": tmp_path / "identity-approval.json",
        "authority": authority,
        "request": request,
        "inventory": installed / "vera-delivery-v2/extra.py",
    }[attack]
    path.chmod(0o600) if path.exists() else None
    path.write_text("{}")
    with pytest.raises(ValueError):
        identity.ti_reserve(request, digest)
    assert calls == []
    assert not list((tmp_path / "evidence").glob("bootstrap-started-*"))
    assert resolve is not None


def identity_result(tmp_path: Path) -> tuple[Path, str, Path]:
    request, _, _, installed = inputs(tmp_path)
    resolve, _, _, _, _ = native()
    result = run(request, resolve)
    assert result["status"] == "identity_observed", result["reason"]
    path = tmp_path / "evidence" / f"result-{result['invocationId']}.json"
    return path, identity.ti_digest(identity.ti_read(path)), installed


def cap_approval(tmp_path: Path) -> Path:
    from vera_timeline_agent import native_qualification_v2 as capability

    path = tmp_path / "capability-approval.json"
    path.write_text(
        json.dumps(
            {
                "changeNote": "CN-178-Q1",
                "producerQuote": "Approve staged CN-178-Q1",
                "noteSha256": capability.APPROVED_NOTE_HASH,
                "scope": capability.APPROVED_SCOPE,
                "recordedAt": datetime.now(UTC).isoformat(),
                "ordinaryGuardsRetained": True,
            }
        )
    )
    return path


def consume(tmp_path: Path, result: Path, digest: str, **overrides: Any) -> Path:
    options: dict[str, Any] = {
        "result_path": result,
        "result_sha256": digest,
        "approval_path": cap_approval(tmp_path),
        "evidence_dir": tmp_path / "cap-evidence",
        "operator": "Synthetic consumer",
        "acknowledge_result_sha256": digest,
        "confirm_displayed_target": True,
        "confirm_saved_disposable": True,
        "confirm_read_only": True,
        "external_scripting_none": True,
    }
    options.update(overrides)
    return identity.create_capability_authority_from_identity(
        tmp_path / "cap-authority.json", **options
    )


def test_receipt_confirmation_is_separate_and_single_use(tmp_path: Path) -> None:
    result, digest, _ = identity_result(tmp_path)
    authority = consume(tmp_path, result, digest)
    value, _ = identity.ti_cap_authority(authority)
    assert value["schemaVersion"] == identity.TI_CAP_AUTHORITY
    assert (
        value["binding"]["target"]
        == identity.ti_object(identity.ti_read(result))["target"]
    )
    assert value["identityReceipt"]["resultSha256"] == digest
    expiry = identity.ti_time(value["expiresAt"])
    assert expiry == min(
        identity.ti_time(value["issuedAt"]) + timedelta(seconds=1800),
        identity.ti_time(identity.ti_object(identity.ti_read(result))["finishedAt"])
        + timedelta(seconds=1800),
    )
    with pytest.raises(ValueError, match="collision"):
        consume(tmp_path, result, digest)


@pytest.mark.parametrize(
    "override",
    [
        "acknowledge_result_sha256",
        "confirm_displayed_target",
        "confirm_saved_disposable",
        "confirm_read_only",
        "external_scripting_none",
    ],
)
def test_missing_or_wrong_receipt_acknowledgement_never_consumes(
    tmp_path: Path, override: str
) -> None:
    result, digest, _ = identity_result(tmp_path)
    replacement: Any = "0" * 64 if override == "acknowledge_result_sha256" else 1
    with pytest.raises(ValueError):
        consume(tmp_path, result, digest, **{override: replacement})
    assert not list((tmp_path / "evidence").glob("consumed-*"))
    assert not (tmp_path / "cap-authority.json").exists()


@pytest.mark.parametrize(
    "attack",
    [
        "failed",
        "qualified",
        "target",
        "reads",
        "version",
        "extra",
        "copied",
        "hashes",
        "controller",
    ],
)
def test_forged_or_missing_identity_lineage_is_not_authority(
    tmp_path: Path, attack: str
) -> None:
    path, digest, _ = identity_result(tmp_path)
    value = identity.ti_object(identity.ti_read(path))
    if attack == "copied":
        copied = tmp_path / "copied.json"
        shutil.copyfile(path, copied)
        copied.chmod(0o400)
        path = copied
    elif attack in {"hashes", "controller"}:
        prefix = "hashes" if attack == "hashes" else "controller-started"
        marker = tmp_path / "evidence" / f"{prefix}-{value['invocationId']}.json"
        marker.rename(tmp_path / f"removed-{attack}.json")
    else:
        if attack == "failed":
            value["status"] = "stopped_safely"
        elif attack == "qualified":
            value["verified"] = 0
        elif attack == "target":
            value["target"]["projectUid"] = "guessed"
        elif attack == "reads":
            value["reads"][1]["target"]["timelineUid"] = "changed"
        elif attack == "version":
            value["runtime"]["version"] = [21, True, 1, 10, ""]
        else:
            value["extra"] = True
        path.chmod(0o600)
        path.write_text(json.dumps(value))
        path.chmod(0o400)
        digest = identity.ti_digest(identity.ti_read(path))
        hashes_path = tmp_path / "evidence" / f"hashes-{value['invocationId']}.json"
        hashes = identity.ti_object(identity.ti_read(hashes_path))
        hashes["resultSha256"] = digest
        hashes_path.chmod(0o600)
        hashes_path.write_text(json.dumps(hashes))
        hashes_path.chmod(0o400)
    with pytest.raises(ValueError):
        consume(tmp_path, path, digest)
    assert not list((tmp_path / "evidence").glob("consumed-*"))


def test_completed_identity_survives_request_transition_and_capability_uid_guard(
    tmp_path: Path,
) -> None:
    from test_issue204_native_preflight import native as capability_native
    from vera_timeline_agent import native_qualification_v2 as capability

    result, digest, installed = identity_result(tmp_path)
    authority = consume(tmp_path, result, digest)
    host = capability.prepare_capability_request(
        tmp_path / "cap-request.json", authority_path=authority
    )
    request = installed / "vera-delivery-v2/request.json"
    request.rename(
        tmp_path / "archived-identity-request.json"
    )  # Synthetic manual transition.
    shutil.copyfile(host, request)
    request.chmod(0o400)
    expected = identity.ti_digest(identity.ti_read(request))
    identity.ti_cap_reserve(request, expected)
    resolve, timeline, _, calls = capability_native()
    project = resolve.values["GetProjectManager"].values["GetCurrentProject"]
    project.values.update(GetName="Synthetic project", GetUniqueId="opaque-p")
    timeline.values.update(GetName="Synthetic timeline", GetUniqueId="opaque-t")
    report = capability.run_capability_preflight(
        resolve, request, expected_request_sha256=expected
    )
    assert (
        identity.ti_object(identity.ti_read(report))["status"]
        == "capability_gaps_observed"
    )
    assert not any(c.startswith("FORBIDDEN:") for c in calls)
    before = list(calls)
    with pytest.raises(ValueError, match="collision"):
        capability.run_capability_preflight(
            resolve, request, expected_request_sha256=expected
        )
    assert calls == before


def test_wrong_live_uid_refuses_before_capability_reads(tmp_path: Path) -> None:
    from test_issue204_native_preflight import native as capability_native
    from vera_timeline_agent import native_qualification_v2 as capability

    result, digest, installed = identity_result(tmp_path)
    authority = consume(tmp_path, result, digest)
    host = capability.prepare_capability_request(
        tmp_path / "cap-request.json", authority_path=authority
    )
    request = installed / "vera-delivery-v2/request.json"
    request.rename(tmp_path / "archived-identity-request.json")
    shutil.copyfile(host, request)
    request.chmod(0o400)
    expected = identity.ti_digest(identity.ti_read(request))
    identity.ti_cap_reserve(request, expected)
    resolve, timeline, _, calls = capability_native()
    project = resolve.values["GetProjectManager"].values["GetCurrentProject"]
    project.values.update(GetName="Synthetic project", GetUniqueId="opaque-p")
    timeline.values.update(GetName="Synthetic timeline", GetUniqueId="wrong-live-t")
    report = capability.run_capability_preflight(
        resolve, request, expected_request_sha256=expected
    )
    value = identity.ti_object(identity.ti_read(report))
    assert value["status"] == "stopped_safely"
    assert value["reason"] == "current timeline differs from operator target"
    assert "GetSettings" not in calls and "GetTrackCount" not in calls
    assert not any(c.startswith("FORBIDDEN:") for c in calls)


def rewrite(path: Path, value: dict[str, Any]) -> None:
    """Deliberate synthetic hostile edit; never a production recovery operation."""
    path.chmod(0o600)
    path.write_text(json.dumps(value))
    path.chmod(0o400)


@pytest.mark.parametrize(
    "attack",
    [
        "confirmation",
        "extra",
        "missing",
        "unknown-action",
        "expired",
        "future",
        "issuer",
    ],
)
def test_closed_authority_refusals_reach_intended_gate(
    tmp_path: Path, attack: str
) -> None:
    request, authority, _, _ = inputs(tmp_path)
    value = identity.ti_object(identity.ti_read(authority))
    reasons = {
        "confirmation": "confirmations",
        "extra": "fields",
        "missing": "fields",
        "unknown-action": "unsupported",
        "expired": "expired",
        "future": "future",
        "issuer": "issuer",
    }
    if attack == "confirmation":
        value["confirmations"]["readOnly"] = 1
    elif attack == "extra":
        value["extra"] = "unknown"
    elif attack == "missing":
        del value["operator"]
    elif attack == "unknown-action":
        value["action"] = "build"
    elif attack in {"expired", "future"}:
        issued = datetime.now(UTC) + timedelta(
            seconds=-1801 if attack == "expired" else 10
        )
        value.update(
            issuedAt=issued.isoformat(),
            expiresAt=(issued + timedelta(seconds=1800)).isoformat(),
        )
    else:
        value["issuer"]["pythonVersion"] = "3.14.4"
    rewrite(authority, value)
    with pytest.raises(ValueError, match=reasons[attack]):
        identity.ti_reserve(request, identity.ti_digest(identity.ti_read(request)))
    assert not list((tmp_path / "evidence").glob("bootstrap-started-*"))


@pytest.mark.parametrize(
    "where",
    [
        "repository",
        "release",
        "installed",
        "approval",
        "authority",
        "request",
        "reverse",
        "alias",
    ],
)
def test_otherwise_bound_unsafe_evidence_never_publishes(
    tmp_path: Path, where: str
) -> None:
    request, authority, repo, installed = inputs(tmp_path)
    value = identity.ti_object(identity.ti_read(authority))
    destinations = {
        "repository": repo / "output",
        "release": tmp_path / "release" / "output",
        "installed": installed / "output",
        "approval": tmp_path / "identity-approval.json",
        "authority": authority,
        "request": request,
        "reverse": tmp_path,
    }
    if where == "alias":
        alias = tmp_path / "alias"
        alias.symlink_to(repo, target_is_directory=True)
        output = alias / "output"
    else:
        output = destinations[where]
    value["binding"]["evidenceDir"] = str(output)
    rewrite(authority, value)
    with pytest.raises(ValueError, match=r"overlap|symbolic"):
        identity.ti_authority(authority)
    assert not output.is_dir() or not list(output.glob("bootstrap-started-*"))


def test_only_one_concurrent_launch_reserves_before_getters(tmp_path: Path) -> None:
    request, _, _, _ = inputs(tmp_path)
    digest = identity.ti_digest(identity.ti_read(request))

    def claim() -> bool:
        try:
            identity.ti_reserve(request, digest)
            return True
        except ValueError as error:
            assert "collision" in str(error)
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: claim(), range(2))) == [False, True]
    assert len(list((tmp_path / "evidence").glob("bootstrap-started-*"))) == 1


def test_only_one_concurrent_receipt_consumer_issues_authority(tmp_path: Path) -> None:
    result, digest, _ = identity_result(tmp_path)
    approval = cap_approval(tmp_path)

    def claim(index: int) -> bool:
        try:
            identity.create_capability_authority_from_identity(
                tmp_path / f"cap-authority-{index}.json",
                result_path=result,
                result_sha256=digest,
                approval_path=approval,
                evidence_dir=tmp_path / f"cap-evidence-{index}",
                operator="Synthetic race operator",
                acknowledge_result_sha256=digest,
                confirm_displayed_target=True,
                confirm_saved_disposable=True,
                confirm_read_only=True,
                external_scripting_none=True,
            )
            return True
        except ValueError as error:
            assert "collision" in str(error)
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(claim, range(2))) == [False, True]
    assert len(list(tmp_path.glob("cap-authority-*.json"))) == 1


def test_uncertain_capability_publication_consumes_receipt_permanently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, digest, _ = identity_result(tmp_path)
    publish = identity.ti_publish

    def crash(
        path: Path, value: dict[str, Any], protected: list[Path] | None = None
    ) -> Path:
        if path.name == "cap-authority.json":
            raise ValueError("simulated crash after consumption reservation")
        return publish(path, value, protected)

    monkeypatch.setattr(identity, "ti_publish", crash)
    with pytest.raises(ValueError, match="simulated crash"):
        consume(tmp_path, result, digest)
    assert (tmp_path / "evidence" / f"consumed-{digest}.json").exists()
    monkeypatch.setattr(identity, "ti_publish", publish)
    with pytest.raises(ValueError, match="collision"):
        consume(tmp_path, result, digest)
    assert not (tmp_path / "cap-authority.json").exists()


def test_uncertain_identity_hash_publication_never_supplies_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, _, _, _ = inputs(tmp_path)
    digest = identity.ti_digest(identity.ti_read(request))
    identity.ti_reserve(request, digest)
    resolve, _, _, _, calls = native()
    publish = identity.ti_publish

    def crash(
        path: Path, value: dict[str, Any], protected: list[Path] | None = None
    ) -> Path:
        if path.name.startswith("hashes-"):
            raise ValueError("simulated uncertain hash publication")
        return publish(path, value, protected)

    monkeypatch.setattr(identity, "ti_publish", crash)
    with pytest.raises(ValueError, match="uncertain hash"):
        identity.run_target_identity(resolve, request, expected_request_sha256=digest)
    path = next((tmp_path / "evidence").glob("result-*.json"))
    with pytest.raises(ValueError):
        identity.ti_receipt(path, identity.ti_digest(identity.ti_read(path)))
    assert not any(c.startswith("FORBIDDEN:") for c in calls)


@pytest.mark.parametrize("attack", ["clean", "loaded", "wrong-name", "unknown-action"])
def test_actual_bootstrap_code_with_fake_injected_object(
    tmp_path: Path, attack: str
) -> None:
    request, authority, _, installed = inputs(tmp_path)
    if attack == "unknown-action":
        value = identity.ti_object(identity.ti_read(request))
        value["action"] = "build"
        rewrite(request, value)
    code = """
import json, runpy, sys, types
calls=[]
class Fake:
    def __init__(self, label, values): self.label,self.values=label,values
    def __getattr__(self, method):
        allowed={"GetProductName","GetVersion","GetProjectManager",
                 "GetCurrentProject","GetCurrentTimeline","GetName","GetUniqueId"}
        if method not in allowed:
            calls.append("FORBIDDEN:"+method)
            raise AssertionError(method)
        def getter():
            calls.append(self.label+"."+method)
            return self.values[method]
        return getter
t=Fake("timeline", {"GetName":"Synthetic timeline","GetUniqueId":"opaque-t"})
pname="Wrong" if sys.argv[2]=="wrong-name" else "Synthetic project"
p=Fake("project", {"GetName":pname,"GetUniqueId":"opaque-p",
                   "GetCurrentTimeline":t})
m=Fake("manager", {"GetCurrentProject":p})
r=Fake("resolve", {"GetProductName":"DaVinci Resolve Studio",
                   "GetVersion":[21,1,1,10,""],"GetProjectManager":m})
if sys.argv[2]=="loaded":
    sys.modules["vera_timeline_agent.residue"]=types.ModuleType("residue")
try: runpy.run_path(sys.argv[1], init_globals={"resolve":r})
except SystemExit: pass
print("CALLS="+json.dumps(calls))
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            code,
            str(installed / "VERA Delivery v2.py"),
            attack,
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    assert "FORBIDDEN:" not in completed.stdout
    evidence = tmp_path / "evidence"
    if attack == "clean":
        report = next(evidence.glob("result-*.json"))
        observed = identity.ti_object(identity.ti_read(report))
        assert observed["status"] == "identity_observed"
        identity.ti_receipt(report, identity.ti_digest(identity.ti_read(report)))
    elif attack == "wrong-name":
        report = next(evidence.glob("result-*.json"))
        observed = identity.ti_object(identity.ti_read(report))
        assert (
            observed["target"] is None
            and observed["reason"] == "current project name mismatch"
        )
        assert "project.GetCurrentTimeline" not in completed.stdout
    else:
        assert not list(evidence.glob("bootstrap-started-*"))
        assert "CALLS=[]" in completed.stdout
    assert authority.exists()


@pytest.mark.parametrize("attack", ["extent", "replacement"])
def test_read_descriptor_and_ancestry_swaps_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attack: str
) -> None:
    path = tmp_path / "record.json"
    path.write_bytes(b"original")
    reader = os.read
    changed = False

    def swap(fd: int, count: int) -> bytes:
        nonlocal changed
        payload = reader(fd, count)
        if not changed:
            changed = True
            if attack == "extent":
                path.write_bytes(b"different length")
            else:
                path.rename(tmp_path / "original-retained.json")
                path.write_bytes(b"original")
        return payload

    monkeypatch.setattr(os, "read", swap)
    with pytest.raises(ValueError, match="changed"):
        identity.ti_read(path)


def test_inode_ancestry_catches_nontextual_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protected = tmp_path / "protected"
    protected.mkdir()
    alias = tmp_path / "different-text" / "child"
    info = protected.stat()
    ancestry = identity.ti_ancestry

    def mapped(path: Path) -> list[tuple[str, int, int]]:
        if path == alias:
            return [(str(tmp_path / "different-text"), info.st_dev, info.st_ino)]
        return ancestry(path)

    monkeypatch.setattr(identity, "ti_ancestry", mapped)
    with pytest.raises(ValueError, match="overlap"):
        identity.ti_separate(alias, [protected])


def test_swapped_output_ancestry_never_returns_published_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "evidence"
    identity.ti_private(root)
    writer = os.write

    def swap(fd: int, payload: Any) -> int:
        root.rename(tmp_path / "retained-original-evidence")
        root.mkdir(mode=0o700)
        return writer(fd, payload)

    monkeypatch.setattr(os, "write", swap)
    with pytest.raises(ValueError, match="ancestry"):
        identity.ti_publish(root / "result.json", {"ok": True})
    assert not (root / "result.json").exists()


def test_expired_completed_receipt_requires_fresh_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, digest, _ = identity_result(tmp_path)
    future = datetime.now(UTC) + timedelta(seconds=1801)

    class ExpiredClock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> ExpiredClock:
            return cls.fromtimestamp(future.timestamp(), tz=UTC)

    monkeypatch.setattr(identity, "datetime", ExpiredClock)
    with pytest.raises(ValueError, match="expired"):
        consume(tmp_path, result, digest)
    assert not list((tmp_path / "evidence").glob("consumed-*"))


def test_monotonic_reset_between_bootstrap_and_controller_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    request, _, _, _ = inputs(tmp_path)
    digest = identity.ti_digest(identity.ti_read(request))
    identity.ti_reserve(request, digest)
    resolve, _, _, _, calls = native()
    monkeypatch.setattr(time, "monotonic", lambda: 0.0)
    with pytest.raises(ValueError, match="rollback"):
        identity.run_target_identity(resolve, request, expected_request_sha256=digest)
    assert calls == []
