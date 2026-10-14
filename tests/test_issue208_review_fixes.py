"""Synthetic reproductions of the four independent #208 review blockers."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_issue208_target_identity import (
    consume,
    identity_result,
    inputs,
    native,
    rewrite,
    run,
)
from vera_timeline_agent import native_qualification_v2 as capability
from vera_timeline_agent import target_identity_v2 as identity
from vera_timeline_agent.workflow_v2_cli import main


def test_shared_installed_root_preserves_other_plugins(tmp_path: Path) -> None:
    request, _, _, installed = inputs(tmp_path)
    (installed / "VERA Delivery v1.py").write_text("preserved v1")
    other = installed / "other-vendor"
    other.mkdir(mode=0o700)
    (other / "plugin.py").write_text("preserved unrelated plugin")
    (installed / "vera-delivery-v1").mkdir()
    (installed / ".DS_Store").write_bytes(b"finder")
    (installed / "vera-delivery-v2/.DS_Store").write_bytes(b"finder")
    resolve, _, _, _, calls = native()
    result = run(request, resolve)
    assert result["status"] == "identity_observed"
    assert (other / "plugin.py").read_text() == "preserved unrelated plugin"
    assert not any(c.startswith("FORBIDDEN:") for c in calls)
    (installed / "vera-delivery-v2/undeclared.py").write_text("bad")
    with pytest.raises(ValueError, match="undeclared"):
        identity.ti_binding(result["binding"])


@pytest.mark.parametrize("ppm", [-50, 50])
def test_normal_clock_rate_skew_over_thirty_minutes(ppm: int) -> None:
    start = datetime.now(UTC)
    clock = identity.TIClock(start, 100.0)
    clock.check(start + timedelta(seconds=1800 * (1 + ppm / 1_000_000)), 1900.0)


def test_real_clock_stepback_and_excess_rate_uncertainty_refuse() -> None:
    start = datetime.now(UTC)
    with pytest.raises(ValueError, match="rollback"):
        identity.TIClock(start, 100.0).check(start - timedelta(microseconds=1), 101.0)
    with pytest.raises(ValueError, match="rollback"):
        identity.TIClock(start, 100.0).check(start + timedelta(seconds=1798), 1900.0)


def test_completed_receipt_lifetime_starts_at_finish_not_authority_issue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"offset": 0.0}
    actual_now = datetime.now
    actual_monotonic = time.monotonic

    class Clock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> Clock:
            instant = actual_now(UTC) + timedelta(seconds=state["offset"])
            return cls.fromtimestamp(instant.timestamp(), tz=UTC)

    monkeypatch.setattr(identity, "datetime", Clock)
    monkeypatch.setattr(time, "monotonic", lambda: actual_monotonic() + state["offset"])
    request, _, _, _ = inputs(tmp_path)
    state["offset"] = 480.0
    resolve, _, _, _, _ = native()
    observed = run(request, resolve)
    assert observed["status"] == "identity_observed"
    result = tmp_path / "evidence" / f"result-{observed['invocationId']}.json"
    digest = identity.ti_digest(identity.ti_read(result))
    # Original authority expired at T0+1800; completed receipt remains current.
    state["offset"] = 1860.0
    authority = consume(tmp_path, result, digest)
    value, _ = identity.ti_cap_authority(authority)
    assert identity.ti_time(value["expiresAt"]) == (
        identity.ti_time(observed["finishedAt"]) + timedelta(seconds=1800)
    )
    monkeypatch.setattr(capability, "datetime", Clock)
    host = capability.prepare_capability_request(
        tmp_path / "cap-request.json", authority_path=authority
    )
    installed_request = tmp_path / "installed/vera-delivery-v2/request.json"
    installed_request.rename(tmp_path / "archived-request.json")
    shutil.copyfile(host, installed_request)
    installed_request.chmod(0o400)
    expected = identity.ti_digest(identity.ti_read(installed_request))
    identity.ti_cap_reserve(installed_request, expected)
    from test_issue204_native_preflight import native as capability_native

    resolve_cap, timeline, _, calls = capability_native()
    project = resolve_cap.values["GetProjectManager"].values["GetCurrentProject"]
    project.values.update(GetName="Synthetic project", GetUniqueId="opaque-p")
    timeline.values.update(GetName="Synthetic timeline", GetUniqueId="opaque-t")
    report = capability.run_capability_preflight(
        resolve_cap, installed_request, expected_request_sha256=expected
    )
    assert (
        identity.ti_object(identity.ti_read(report))["status"]
        == "capability_gaps_observed"
    )
    assert not any(c.startswith("FORBIDDEN:") for c in calls)
    state["offset"] = 2281.0
    with pytest.raises(ValueError, match="stale"):
        identity.ti_cap_authority(authority)
    previous = list(calls)
    with pytest.raises(ValueError, match="stale"):
        capability.run_capability_preflight(
            resolve_cap, installed_request, expected_request_sha256=expected
        )
    assert calls == previous


def capability_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    result, digest, installed = identity_result(tmp_path)
    authority = consume(tmp_path, result, digest)
    host = capability.prepare_capability_request(
        tmp_path / "cap-request.json",
        authority_path=authority,
    )
    request = installed / "vera-delivery-v2/request.json"
    request.rename(tmp_path / "archived-identity-request.json")
    shutil.copyfile(host, request)
    request.chmod(0o400)
    return request, authority, installed


BOOTSTRAP_FAKE = """
import json,runpy,sys,types
calls=[]
class Fake:
    def __init__(self,label,values): self.label,self.values=label,values
    def __getattr__(self,method):
        if not method.startswith("Get"):
            calls.append("FORBIDDEN:"+self.label+"."+method)
            raise AssertionError(method)
        if method not in self.values: raise AttributeError(method)
        def getter(*args):
            calls.append(self.label+"."+method)
            return self.values[method]
        return getter
t=Fake("timeline",{"GetName":"Synthetic timeline","GetUniqueId":"opaque-t"})
p=Fake("project",{"GetName":"Synthetic project","GetUniqueId":"opaque-p",
                  "GetCurrentTimeline":t})
m=Fake("manager",{"GetCurrentProject":p})
r=Fake("resolve",{"GetProductName":"DaVinci Resolve Studio",
                  "GetVersion":[21,1,1,10,""],"GetProjectManager":m})
if sys.argv[2]=="loaded":
    sys.modules["vera_timeline_agent.residue"]=types.ModuleType("residue")
runpy.run_path(sys.argv[1],init_globals={"resolve":r})
print("RETURNED_CALLS="+json.dumps(calls))
"""


def bootstrap(installed: Path, attack: str = "clean") -> tuple[str, list[str]]:
    completed = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            BOOTSTRAP_FAKE,
            str(installed / "VERA Delivery v2.py"),
            attack,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert not completed.stderr
    suffix = completed.stdout.split("RETURNED_CALLS=", 1)[1]
    calls = json.loads(suffix)
    assert not any(c.startswith("FORBIDDEN:") for c in calls)
    return completed.stdout, calls


@pytest.mark.parametrize("attack", ["clean", "loaded", "replay"])
def test_actual_capability_bootstrap_returns_and_retains_refusal(
    tmp_path: Path,
    attack: str,
) -> None:
    _, _, installed = capability_inputs(tmp_path)
    # Prove actual shared-plugin context also reaches the capability branch.
    (installed / "VERA Delivery v1.py").write_text("preserved")
    output, calls = bootstrap(installed, "loaded" if attack == "loaded" else "clean")
    evidence = tmp_path / "cap-evidence"
    if attack == "loaded":
        assert calls == [] and "already loaded" in output
        refusal = next(evidence.glob("bootstrap-refusal-*"))
        assert identity.ti_object(identity.ti_read(refusal))["verified"] is False
        assert not list(evidence.glob("bootstrap-started-*"))
    else:
        report = next(evidence.glob("result-*"))
        assert (
            identity.ti_object(identity.ti_read(report))["status"]
            == "capability_gaps_observed"
        )
        assert calls and "timeline.GetUniqueId" in calls
        if attack == "replay":
            output, calls = bootstrap(installed)
            assert calls == [] and "collision" in output
            assert list(evidence.glob("bootstrap-refusal-*"))
            assert len(list(evidence.glob("result-*"))) == 1


def rebind_request(request: Path, authority: Path) -> None:
    value = identity.ti_object(identity.ti_read(request))
    auth = identity.ti_object(identity.ti_read(authority))
    value.update(
        authoritySha256=identity.ti_digest(identity.ti_read(authority)),
        binding=auth["binding"],
    )
    rewrite(request, value)
    evidence = Path(auth["binding"]["evidenceDir"])
    prepared_path = evidence / f"prepared-{auth['invocationId']}.json"
    prepared = identity.ti_object(identity.ti_read(prepared_path))
    host = Path(prepared["requestPath"])
    rewrite(host, value)
    prepared["requestSha256"] = identity.ti_digest(identity.ti_read(request))
    rewrite(prepared_path, prepared)


@pytest.mark.parametrize(
    "attack,reason",
    [
        ("target", "target drift"),
        ("expiry", "stale receipt-backed"),
        ("receipt-hash", "result hash drift"),
        ("invocation", "invocation drift"),
        ("approval", "approval/invocation drift"),
        ("confirmation", "confirmation"),
        ("marker-missing", "unavailable"),
        ("marker-different", "consumption lineage"),
        ("source", "source drift"),
        ("release", "release drift"),
        ("v2-with-v1", "authority fields"),
        ("v1-with-v2", "operator authority fields"),
    ],
)
def test_capability_tampering_reaches_intended_gate_before_getters(
    tmp_path: Path,
    attack: str,
    reason: str,
) -> None:
    request, authority, _ = capability_inputs(tmp_path)
    auth = identity.ti_object(identity.ti_read(authority))
    if attack == "target":
        auth["binding"]["target"]["timelineUid"] = "guessed"
    elif attack == "expiry":
        auth["expiresAt"] = (
            identity.ti_time(auth["expiresAt"]) + timedelta(seconds=1)
        ).isoformat()
    elif attack == "receipt-hash":
        auth["identityReceipt"]["resultSha256"] = "0" * 64
    elif attack == "invocation":
        auth["identityReceipt"]["invocationId"] = "00000000-0000-0000-0000-000000000000"
    elif attack == "approval":
        auth["identityReceipt"]["identityApprovalSha256"] = "0" * 64
    elif attack == "confirmation":
        auth["confirmations"]["readOnly"] = 1
    elif attack.startswith("marker"):
        marker = (
            tmp_path
            / "evidence"
            / f"consumed-{auth['identityReceipt']['resultSha256']}.json"
        )
        if attack == "marker-missing":
            marker.rename(tmp_path / "retained-consumption.json")
        else:
            rewrite(marker, {"changed": True})
    elif attack == "source":
        source = (
            Path(auth["binding"]["repositoryRoot"])
            / "python/vera_timeline_agent/target_identity_v2.py"
        )
        source.write_text("source drift")
    elif attack == "release":
        manifest = (
            Path(auth["binding"]["releaseRoot"]) / "vera-delivery-v2/release.json"
        )
        manifest.chmod(0o600)
        manifest.write_text("{}")
    elif attack == "v2-with-v1":
        auth["schemaVersion"] = capability.AUTHORITY_SCHEMA
        del auth["identityReceipt"]
        del auth["expiresAt"]
    if attack not in {
        "source",
        "release",
        "marker-missing",
        "marker-different",
        "v1-with-v2",
    }:
        rewrite(authority, auth)
        rebind_request(request, authority)
    if attack == "v1-with-v2":
        req = identity.ti_object(identity.ti_read(request))
        req["schemaVersion"] = capability.REQUEST_SCHEMA
        rewrite(request, req)
    resolve, _, _, _, calls = native()
    digest = identity.ti_digest(identity.ti_read(request))
    with pytest.raises(ValueError, match=reason):
        capability.run_capability_preflight(
            resolve, request, expected_request_sha256=digest
        )
    assert calls == []


@pytest.mark.parametrize("where", ["repository", "release", "installed", "approval"])
def test_matching_unsafe_bootstrap_binding_retention_is_unavailable(
    tmp_path: Path,
    where: str,
) -> None:
    request, authority, repo, installed = inputs(tmp_path)
    auth = identity.ti_object(identity.ti_read(authority))
    paths = {
        "repository": repo / "evidence",
        "release": tmp_path / "release/evidence",
        "installed": installed / "evidence",
        "approval": tmp_path / "identity-approval.json",
    }
    output = paths[where]
    auth["binding"]["evidenceDir"] = str(output)
    rewrite(authority, auth)
    req = identity.ti_object(identity.ti_read(request))
    req.update(
        binding=auth["binding"],
        authoritySha256=identity.ti_digest(identity.ti_read(authority)),
    )
    rewrite(request, req)
    before = {
        str(p): p.read_bytes()
        for root in (repo, tmp_path / "release", installed)
        for p in root.rglob("*")
        if p.is_file()
    }
    console, calls = bootstrap(installed)
    after = {
        str(p): p.read_bytes()
        for root in (repo, tmp_path / "release", installed)
        for p in root.rglob("*")
        if p.is_file()
    }
    assert calls == [] and "unavailable" in console
    assert before == after
    assert not list((tmp_path / "evidence").glob("bootstrap-started-*"))


def test_exact_identity_getter_order_and_blank_uid(tmp_path: Path) -> None:
    request, _, _, _ = inputs(tmp_path)
    resolve, _, _, timeline, calls = native()
    result = run(request, resolve)
    context = [
        "resolve.GetProjectManager",
        "manager.GetCurrentProject",
        "project.GetName",
        "project.GetUniqueId",
        "project.GetCurrentTimeline",
        "timeline.GetName",
        "timeline.GetUniqueId",
    ]
    product = ["resolve.GetProductName", "resolve.GetVersion"]
    assert calls == [*product, *context, *product, *context, *product]
    assert result["status"] == "identity_observed"
    # Fresh authority and invocation; never reuse the completed one.
    other = tmp_path / "fresh"
    other.mkdir(mode=0o700)
    request, _, _, _ = inputs(other)
    resolve, _, _, timeline, calls = native()
    timeline.values["GetUniqueId"] = " "
    result = run(request, resolve)
    assert result["target"] is None and result["reason"] == "invalid bounded string"
    assert calls == [*product, *context]


@pytest.mark.parametrize(
    "flag",
    [
        "--confirm-saved-disposable-nonproduction",
        "--confirm-read-only",
        "--external-scripting-none",
    ],
)
def test_identity_cli_missing_individual_confirmation_never_issues(
    tmp_path: Path,
    flag: str,
) -> None:
    _, _, _, installed = inputs(tmp_path)
    argv = [
        "identity-authorize",
        "--release",
        str(tmp_path / "release"),
        "--installed-root",
        str(installed),
        "--approval",
        str(tmp_path / "identity-approval.json"),
        "--operator",
        "Synthetic",
        "--project-name",
        "Synthetic project",
        "--timeline-name",
        "Synthetic timeline",
        "--output",
        str(tmp_path / "other-authority.json"),
        "--evidence-dir",
        str(tmp_path / "other-evidence"),
        "--confirm-saved-disposable-nonproduction",
        "--confirm-read-only",
        "--external-scripting-none",
    ]
    argv.remove(flag)
    assert main(argv) == 2
    assert not (tmp_path / "other-authority.json").exists()


@pytest.mark.parametrize(
    "answer,ack,omit",
    [
        ("no", None, None),
        ("CONFIRM", "wrong", None),
        ("CONFIRM", None, "--confirm-displayed-target"),
        ("CONFIRM", None, "--confirm-read-only"),
        ("CONFIRM", None, "--external-scripting-none"),
        ("CONFIRM", None, "--confirm-saved-disposable-nonproduction"),
    ],
)
def test_capability_cli_requires_each_confirmation_and_exact_ack(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    answer: str,
    ack: str | None,
    omit: str | None,
) -> None:
    from test_issue208_target_identity import cap_approval

    result, digest, _ = identity_result(tmp_path)
    argv = [
        "capability-authorize-from-identity",
        str(result),
        "--result-sha256",
        digest,
        "--acknowledge-result-sha256",
        digest if ack is None else "0" * 64,
        "--approval",
        str(cap_approval(tmp_path)),
        "--operator",
        "Synthetic",
        "--output",
        str(tmp_path / "cli-authority.json"),
        "--evidence-dir",
        str(tmp_path / "cli-evidence"),
        "--confirm-displayed-target",
        "--confirm-saved-disposable-nonproduction",
        "--confirm-read-only",
        "--external-scripting-none",
    ]
    if omit:
        argv.remove(omit)
    monkeypatch.setattr("builtins.input", lambda _: answer)
    assert main(argv) == 2
    assert not (tmp_path / "cli-authority.json").exists()
    assert not list((tmp_path / "evidence").glob("consumed-*"))


def test_identity_cli_request_cannot_issue_authority(tmp_path: Path) -> None:
    output = tmp_path / "request.json"
    assert (
        main(
            [
                "identity-request",
                str(tmp_path / "missing.json"),
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()


def test_identity_cli_authority_and_request_are_separate(tmp_path: Path) -> None:
    from vera_timeline_agent.workflow_v2_cli import build_release_v2

    release = tmp_path / "release"
    build_release_v2(release)
    approval = (
        Path(__file__).resolve().parents[1]
        / "docs/verification/issue-207/acceptance.json"
    )
    authority = tmp_path / "authority.json"
    evidence = tmp_path / "evidence"
    argv = [
        "identity-authorize",
        "--release",
        str(release),
        "--installed-root",
        str(tmp_path / "installed"),
        "--approval",
        str(approval),
        "--operator",
        "Synthetic CLI operator",
        "--project-name",
        "Synthetic project",
        "--timeline-name",
        "Synthetic timeline",
        "--output",
        str(authority),
        "--evidence-dir",
        str(evidence),
        "--confirm-saved-disposable-nonproduction",
        "--confirm-read-only",
        "--external-scripting-none",
    ]
    assert main(argv) == 0
    assert authority.exists() and not evidence.exists()
    request = tmp_path / "request.json"
    assert main(["identity-request", str(authority), "--output", str(request)]) == 0
    assert request.stat().st_mode & 0o777 == 0o400
    assert not list(evidence.glob("bootstrap-started-*"))


def test_real_identity_bootstrap_shared_folder_preserves_neighbors(
    tmp_path: Path,
) -> None:
    _, _, _, installed = inputs(tmp_path)
    (installed / "VERA Delivery v1.py").write_text("v1 preserved")
    neighbor = installed / "vendor"
    neighbor.mkdir()
    (neighbor / "plugin.py").write_text("neighbor preserved")
    (installed / ".DS_Store").write_bytes(b"finder")
    (installed / "vera-delivery-v2/.DS_Store").write_bytes(b"finder")
    console, calls = bootstrap(installed)
    assert "identity_observed" in console and calls
    assert (neighbor / "plugin.py").read_text() == "neighbor preserved"
