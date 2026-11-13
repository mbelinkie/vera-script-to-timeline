"""Read-only checks over actual v1/v2 prepared release inventories."""

from __future__ import annotations

import json
import stat
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


def test_partial_install_and_dangling_root_link_require_repair(tmp_path: Path) -> None:
    root, policy, observed = _case(tmp_path, "1")
    # A missing selected release with a leftover launcher is not a first run.
    (root / "vera-delivery-v1" / "release.json").unlink()
    assert inspect_readiness(root, policy, observed)["state"] == "repair_required"
    empty_root = tmp_path / "empty-root"
    empty_root.mkdir()
    (empty_root / "VERA Delivery v1.py").write_text("partial", encoding="utf-8")
    assert inspect_readiness(empty_root, policy, observed)["state"] == "repair_required"
    dangling = tmp_path / "dangling-installed-root"
    dangling.symlink_to(tmp_path / "no-such-directory", target_is_directory=True)
    assert inspect_readiness(dangling, policy, observed)["state"] == "repair_required"


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


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"packageRoot": None}, "approval_required"),
        ({"restartRequired": True}, "restart_required"),
        ({"pairingState": "unpaired"}, "unpaired"),
        ({"pairingState": "unknown"}, "unpaired"),
        ({"serviceState": "disconnected"}, "disconnected"),
        ({"serviceState": "unknown"}, "disconnected"),
        (
            {
                "restartRequired": True,
                "pairingState": "unpaired",
                "serviceState": "disconnected",
            },
            "restart_required",
        ),
        (
            {"pairingState": "unpaired", "serviceState": "disconnected"},
            "unpaired",
        ),
    ],
)
def test_observed_state_matrix_is_non_authorizing(
    tmp_path: Path, change: dict[str, object], expected: str
) -> None:
    root, policy, observed = _case(tmp_path, "2")
    observed.update(change)
    result = inspect_readiness(root, policy, observed)
    assert result["state"] == expected
    assert result["canBuild"] is False
    assert result["nativeVerified"] is False
    assert isinstance(result["nextAction"], str) and result["nextAction"]
    assert result["evidenceKind"].endswith("observations_untrusted")


@pytest.mark.parametrize("version", ["1", "2"])
def test_empty_install_and_only_other_version(tmp_path: Path, version: str) -> None:
    root, policy, observed = _case(tmp_path, version)
    assert inspect_readiness(tmp_path / "empty", policy, observed)["state"] == (
        "first_run"
    )
    other = "2" if version == "1" else "1"
    policy["releaseVersion"] = other
    assert inspect_readiness(root, policy, observed)["state"] == (
        "incompatible_version"
    )


@pytest.mark.parametrize("version", ["1", "2"])
def test_release_manifest_incompatible_version_and_pins(
    tmp_path: Path, version: str
) -> None:
    root, policy, observed = _case(tmp_path, version)
    manifest = root / f"vera-delivery-v{version}" / "release.json"
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["sourcePins"]["issue107"] = "0" * 40
    manifest.chmod(0o600)
    manifest.write_text(json.dumps(value), encoding="utf-8")
    policy["releaseSha256"] = sha256(manifest)
    assert inspect_readiness(root, policy, observed)["state"] == (
        "incompatible_version"
    )


@pytest.mark.parametrize("version", ["1", "2"])
def test_release_rejects_extra_manifest_properties_even_with_matching_digest(
    tmp_path: Path, version: str
) -> None:
    root, policy, observed = _case(tmp_path, version)
    manifest = root / f"vera-delivery-v{version}" / "release.json"
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["unexpectedNativeField"] = "not part of the accepted release format"
    manifest.chmod(0o600)
    manifest.write_text(json.dumps(value), encoding="utf-8")
    policy["releaseSha256"] = sha256(manifest)
    assert inspect_readiness(root, policy, observed)["state"] == "repair_required"


@pytest.mark.parametrize(
    ("policy_change", "expected"),
    [
        ({"approvedTools": []}, "approval_required"),
        ({"approvedRoots": []}, "approval_required"),
        ({"approvedRoots": ["/definitely-not-an-approved-root"]}, "approval_required"),
    ],
)
def test_missing_tool_or_root_approval(
    tmp_path: Path, policy_change: dict[str, object], expected: str
) -> None:
    root, policy, observed = _case(tmp_path, "1")
    policy.update(policy_change)
    observed["restartRequired"] = True
    assert inspect_readiness(root, policy, observed)["state"] == expected


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("approvedTools", ["shell"]),
        ("approvedTools", ["resolve:injected", "shell"]),
        ("approvedRoots", ["relative"]),
        ("releaseVersion", "3"),
        ("releaseSha256", "not-a-digest"),
        ("schemaVersion", "vera-companion-policy/v2"),
    ],
)
def test_unsupported_policy_is_refused(tmp_path: Path, key: str, value: object) -> None:
    root, policy, observed = _case(tmp_path, "1")
    policy[key] = value
    with pytest.raises(ValueError):
        inspect_readiness(root, policy, observed)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("pairingState", "authenticated"),
        ("serviceState", "online"),
        ("restartRequired", "false"),
        ("packageRoot", "relative/path"),
    ],
)
def test_unsupported_observation_is_refused(
    tmp_path: Path, key: str, value: object
) -> None:
    root, policy, observed = _case(tmp_path, "1")
    observed[key] = value
    with pytest.raises(ValueError):
        inspect_readiness(root, policy, observed)


def test_selected_package_must_be_within_real_approved_root(
    tmp_path: Path,
) -> None:
    root, policy, observed = _case(tmp_path, "2")
    outside = tmp_path / "approved-elsewhere" / "package"
    outside.mkdir(parents=True)
    observed["packageRoot"] = str(outside)
    assert inspect_readiness(root, policy, observed)["state"] == ("approval_required")
    observed["packageRoot"] = str(tmp_path / "approved" / "missing")
    assert inspect_readiness(root, policy, observed)["state"] == ("approval_required")
    selected_link = tmp_path / "approved" / "linked-package"
    selected_link.symlink_to(outside, target_is_directory=True)
    observed["packageRoot"] = str(selected_link)
    assert inspect_readiness(root, policy, observed)["state"] == ("approval_required")
    policy["approvedRoots"] = [str(tmp_path / "approved" / "linked-root")]
    (tmp_path / "approved" / "linked-root").symlink_to(
        tmp_path / "approved", target_is_directory=True
    )
    observed["packageRoot"] = str(tmp_path / "approved" / "package")
    assert inspect_readiness(root, policy, observed)["state"] == ("approval_required")


@pytest.mark.parametrize("version", ["1", "2"])
def test_installed_release_tamper_missing_extra_and_empty_dir(
    tmp_path: Path, version: str
) -> None:
    root, policy, observed = _case(tmp_path, version)
    folder = root / f"vera-delivery-v{version}"
    launcher = root / f"VERA Delivery v{version}.py"
    launcher.unlink()
    assert inspect_readiness(root, policy, observed)["state"] == "repair_required"
    # Restore from the actual builder and then add undeclared content.
    other, _, _ = _case(tmp_path / "fresh", version)
    launcher.write_bytes((other / launcher.name).read_bytes())
    (folder / "python" / "unexpected.pyc").write_bytes(b"cache")
    assert inspect_readiness(root, policy, observed)["state"] == "repair_required"
    (folder / "python" / "unexpected.pyc").unlink()
    (folder / "empty").mkdir()
    assert inspect_readiness(root, policy, observed)["state"] == "repair_required"


@pytest.mark.parametrize("version", ["1", "2"])
@pytest.mark.parametrize(
    "target", ["installed-root", "release-dir", "launcher", "runtime"]
)
def test_installed_symlinks_are_never_accepted(
    tmp_path: Path, version: str, target: str
) -> None:
    root, policy, observed = _case(tmp_path, version)
    if target == "installed-root":
        link = tmp_path / "linked-installed"
        link.symlink_to(root, target_is_directory=True)
        check = link
    else:
        folder = root / f"vera-delivery-v{version}"
        if target == "release-dir":
            path = folder
        elif target == "launcher":
            path = root / f"VERA Delivery v{version}.py"
        else:
            path = next((folder / "python").rglob("*.py"))
        original = path.with_name(path.name + ".saved")
        path.rename(original)
        path.symlink_to(original, target_is_directory=target == "release-dir")
        check = root
    assert inspect_readiness(check, policy, observed)["state"] == ("repair_required")


@pytest.mark.parametrize("version", ["1", "2"])
def test_unrelated_plugins_do_not_impair_selected_release(
    tmp_path: Path, version: str
) -> None:
    root, policy, observed = _case(tmp_path, version)
    (root / "Different Plugin.py").write_text("# unrelated\n", encoding="utf-8")
    other = root / "another-plugin" / "nested"
    other.mkdir(parents=True)
    (other / "source.py").write_text("# unrelated\n", encoding="utf-8")
    (root / "other-empty-directory").mkdir()
    (root / "another-plugin" / "unrelated-link").symlink_to(
        tmp_path, target_is_directory=True
    )
    assert inspect_readiness(root, policy, observed)["state"] == (
        "native_preflight_required"
    )
    folder = root / f"vera-delivery-v{version}"
    (folder / ".DS_Store").write_bytes(b"finder")
    (folder / "request.json").write_text("{}", encoding="utf-8")
    assert inspect_readiness(root, policy, observed)["state"] == (
        "native_preflight_required"
    )


def test_report_collision_and_symlink_output_refuse_without_replacement(
    tmp_path: Path,
) -> None:
    root, policy, observed = _case(tmp_path, "1")
    output = tmp_path / "private" / "readiness.json"
    output.parent.mkdir()
    output.write_text("keep previous report\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        retain_report(output, root, policy, observed)
    assert output.read_text(encoding="utf-8") == "keep previous report\n"
    linked_parent = tmp_path / "linked-evidence"
    linked_parent.symlink_to(output.parent, target_is_directory=True)
    with pytest.raises(ValueError, match="non-symlinked"):
        retain_report(linked_parent / "another.json", root, policy, observed)
    assert not (output.parent / "another.json").exists()
    with pytest.raises(ValueError, match="non-symlinked"):
        retain_report(
            linked_parent / "../private/readiness-2.json", root, policy, observed
        )


def test_private_report_permissions_and_recovery_action_no_paths(
    tmp_path: Path,
) -> None:
    root, policy, observed = _case(tmp_path, "2")
    observed["serviceState"] = "disconnected"
    output = tmp_path / "private" / "report.json"
    retain_report(output, root, policy, observed)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["state"] == "disconnected"
    assert "reconnect" in report["nextAction"].lower()
    assert stat.S_IMODE(output.stat().st_mode) == 0o400
    assert all(
        private not in output.read_text(encoding="utf-8")
        for private in (str(root), str(observed["packageRoot"]), str(tmp_path))
    )
