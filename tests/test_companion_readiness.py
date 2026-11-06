"""Read-only checks over actual v1/v2 prepared release inventories."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from vera_timeline_agent.companion_readiness import inspect_readiness, retain_report
from vera_timeline_agent.companion_readiness_cli import main
from vera_timeline_agent.workflow_delivery_cli import build_release
from vera_timeline_agent.workflow_package import sha256
from vera_timeline_agent.workflow_v2_cli import build_release_v2


def _case(
    tmp_path: Path, version: str
) -> tuple[Path, dict[str, object], dict[str, object]]:
    root = tmp_path / "installed"
    manifest = build_release(root) if version == "1" else build_release_v2(root)
    package = tmp_path / "approved" / "package"
    package.mkdir(parents=True)
    policy: dict[str, object] = {
        "schemaVersion": "vera-companion-policy/v1",
        "releaseVersion": version,
        "releaseSha256": sha256(manifest),
        "approvedRoots": [str(package.parent)],
        "approvedTools": ["resolve:injected"],
    }
    observation: dict[str, object] = {
        "packageRoot": str(package),
        "pairingState": "paired",
        "serviceState": "connected",
        "restartRequired": False,
    }
    return root, policy, observation


@pytest.mark.parametrize("version", ["1", "2"])
def test_real_release_smoke_is_non_authorizing(tmp_path: Path, version: str) -> None:
    root, policy, observed = _case(tmp_path, version)
    result = inspect_readiness(root, policy, observed)
    assert result["state"] == "native_preflight_required"
    assert result["deliveryVersion"] == version
    assert result["nativeVerified"] is False
    assert result["canBuild"] is False


def test_no_install_never_claims_readiness(tmp_path: Path) -> None:
    _, policy, observed = _case(tmp_path, "1")
    result = inspect_readiness(tmp_path / "never-installed", policy, observed)
    assert result["state"] == "first_run"
    assert result["canBuild"] is False


@pytest.mark.parametrize("version", ["1", "2"])
def test_source_drift_is_repair_required(tmp_path: Path, version: str) -> None:
    root, policy, observed = _case(tmp_path, version)
    launcher = root / f"VERA Delivery v{version}.py"
    launcher.write_bytes(launcher.read_bytes() + b"# altered after release\n")
    assert inspect_readiness(root, policy, observed)["state"] == "repair_required"


def test_trusted_manifest_digest_mismatch_is_repair_required(tmp_path: Path) -> None:
    root, policy, observed = _case(tmp_path, "1")
    policy["releaseSha256"] = "0" * 64
    assert inspect_readiness(root, policy, observed)["state"] == "repair_required"


def test_report_is_immutable_private_and_does_not_modify_release(
    tmp_path: Path,
) -> None:
    root, policy, observed = _case(tmp_path, "2")
    before = {
        path.relative_to(root): sha256(path)
        for path in root.rglob("*")
        if path.is_file()
    }
    output = tmp_path / "private" / "readiness.json"
    assert retain_report(output, root, policy, observed) == output
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["state"] == "native_preflight_required"
    assert report["canBuild"] is False
    assert report["nativeVerified"] is False
    assert str(root) not in output.read_text(encoding="utf-8")
    assert str(observed["packageRoot"]) not in output.read_text(encoding="utf-8")
    assert "pairingState" not in report
    assert "serviceState" not in report
    assert before == {
        path.relative_to(root): sha256(path)
        for path in root.rglob("*")
        if path.is_file()
    }
    assert not list((tmp_path / "approved" / "package").iterdir())
    with pytest.raises(FileExistsError):
        retain_report(output, root, policy, observed)
    with pytest.raises(ValueError, match="outside the ready package"):
        retain_report(
            tmp_path / "approved" / "package" / "report.json", root, policy, observed
        )
    with pytest.raises(ValueError, match="outside the installed release"):
        retain_report(root / "report.json", root, policy, observed)


def test_cli_writes_one_private_report_and_refuses_overwrite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, policy, observed = _case(tmp_path, "1")
    policy_file = tmp_path / "policy.json"
    observed_file = tmp_path / "observation.json"
    policy_file.write_text(json.dumps(policy), encoding="utf-8")
    observed_file.write_text(json.dumps(observed), encoding="utf-8")
    output = tmp_path / "private" / "report.json"
    args = [
        "--installed-root",
        str(root),
        "--policy",
        str(policy_file),
        "--observation",
        str(observed_file),
        "--output",
        str(output),
    ]
    assert main(args) == 0
    assert "sha256:" in capsys.readouterr().out
    assert json.loads(output.read_text(encoding="utf-8"))["canBuild"] is False
    assert main(args) == 2
    assert "refused" in capsys.readouterr().err
