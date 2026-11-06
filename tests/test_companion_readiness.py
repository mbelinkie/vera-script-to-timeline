from __future__ import annotations

import json
from pathlib import Path

import pytest
from vera_timeline_agent import companion_readiness_cli
from vera_timeline_agent.companion_readiness import (
    ACTIONS,
    inspect_readiness,
    retain_report,
)
from vera_timeline_agent.workflow_delivery_cli import build_release
from vera_timeline_agent.workflow_package import (
    SOURCE_PINS,
    sha256,
    write_immutable_json,
)
from vera_timeline_agent.workflow_v2_cli import build_release_v2


def _installed(tmp_path: Path, version: str = "1") -> tuple[Path, str]:
    """Create a synthetic versioned install; it never claims native success."""
    (tmp_path / "approved" / "package").mkdir(parents=True, exist_ok=True)
    root = tmp_path / "installed"
    script = root / f"VERA Delivery v{version}.py"
    module = root / f"vera-delivery-v{version}/python/vera_timeline_agent/__init__.py"
    module.parent.mkdir(parents=True)
    script.write_text("# installed launcher\n", encoding="utf-8")
    module.write_text("# runtime\n", encoding="utf-8")
    files = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256(path),
            "sizeBytes": path.stat().st_size,
        }
        for path in (script, module)
    ]
    manifest = root / f"vera-delivery-v{version}/release.json"
    manifest.write_text(
        json.dumps(
            {
                "schemaVersion": f"vera-injected-delivery-release/v{version}",
                "deliveryVersion": version,
                "sourcePins": SOURCE_PINS,
                "files": files,
            }
        ),
        encoding="utf-8",
    )
    return root, sha256(manifest)


def _policy(tmp_path: Path, digest: str, version: str = "1") -> dict[str, object]:
    return {
        "schemaVersion": "vera-companion-policy/v1",
        "releaseVersion": version,
        "releaseSha256": digest,
        "approvedRoots": [str(tmp_path / "approved")],
        "approvedTools": ["resolve:injected"],
    }


def _observation(tmp_path: Path) -> dict[str, object]:
    return {
        "packageRoot": str(tmp_path / "approved" / "package"),
        "pairingState": "paired",
        "serviceState": "connected",
        "restartRequired": False,
    }


def _inventory(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_every_state_has_its_own_bounded_operator_action() -> None:
    assert set(ACTIONS) == {
        "first_run",
        "incompatible_version",
        "repair_required",
        "approval_required",
        "restart_required",
        "unpaired",
        "disconnected",
        "native_preflight_required",
    }
    assert len(set(ACTIONS.values())) == len(ACTIONS)
    assert "without replaying" in ACTIONS["disconnected"]
    assert "manually" in ACTIONS["first_run"]


def test_first_run_refuses_without_installation(tmp_path: Path) -> None:
    result = inspect_readiness(
        tmp_path / "missing", _policy(tmp_path, "0" * 64), _observation(tmp_path)
    )
    assert result["state"] == "first_run"
    assert result["canBuild"] is False


def test_report_never_authorizes_even_with_connected_observation(
    tmp_path: Path,
) -> None:
    root, digest = _installed(tmp_path)
    result = inspect_readiness(root, _policy(tmp_path, digest), _observation(tmp_path))
    assert result["state"] == "native_preflight_required"
    assert result["nativeVerified"] is False
    assert result["canBuild"] is False
    assert result["evidenceKind"].endswith("untrusted")
    assert "packageRoot" not in result
    assert "pairingState" not in result


@pytest.mark.parametrize(
    ("change", "state"),
    [
        ("version", "incompatible_version"),
        ("hash", "repair_required"),
        ("extra", "repair_required"),
        ("extra-directory", "repair_required"),
        ("edited", "repair_required"),
        ("missing", "repair_required"),
        ("malformed", "repair_required"),
        ("unapproved", "approval_required"),
        ("unapproved-existing", "approval_required"),
        ("restart", "restart_required"),
        ("unpaired", "unpaired"),
        ("unknown-pairing", "unpaired"),
        ("disconnected", "disconnected"),
        ("unknown-service", "disconnected"),
    ],
)
def test_refusal_matrix(tmp_path: Path, change: str, state: str) -> None:
    root, digest = _installed(tmp_path)
    policy = _policy(tmp_path, digest)
    observed = _observation(tmp_path)
    if change == "version":
        policy["releaseVersion"] = "2"
    elif change == "hash":
        policy["releaseSha256"] = "0" * 64
    elif change == "extra":
        (root / "vera-delivery-v1" / "extra.txt").write_text("extra", encoding="utf-8")
    elif change == "extra-directory":
        (root / "vera-delivery-v1" / "unexpected").mkdir()
    elif change == "edited":
        (root / "VERA Delivery v1.py").write_text("tampered", encoding="utf-8")
    elif change == "missing":
        (root / "vera-delivery-v1/python/vera_timeline_agent/__init__.py").unlink()
    elif change == "malformed":
        (root / "vera-delivery-v1" / "release.json").write_text("{", encoding="utf-8")
    elif change == "unapproved":
        observed["packageRoot"] = str(tmp_path / "unapproved" / "package")
    elif change == "unapproved-existing":
        (tmp_path / "unapproved" / "package").mkdir(parents=True)
        observed["packageRoot"] = str(tmp_path / "unapproved" / "package")
    elif change == "restart":
        observed["restartRequired"] = True
    elif change == "unpaired":
        observed["pairingState"] = "unpaired"
    elif change == "unknown-pairing":
        observed["pairingState"] = "unknown"
    elif change == "disconnected":
        observed["serviceState"] = "disconnected"
    elif change == "unknown-service":
        observed["serviceState"] = "unknown"
    result = inspect_readiness(root, policy, observed)
    assert result["state"] == state
    assert result["canBuild"] is False
    assert result["nativeVerified"] is False


def test_other_plugins_in_shared_root_are_not_owned(tmp_path: Path) -> None:
    root, digest = _installed(tmp_path)
    (root / "some-other-plugin").mkdir()
    (root / "Some Other Plugin.py").write_text("other", encoding="utf-8")
    result = inspect_readiness(root, _policy(tmp_path, digest), _observation(tmp_path))
    assert result["state"] == "native_preflight_required"


def test_partial_install_is_repair_required(tmp_path: Path) -> None:
    root = tmp_path / "installed"
    (root / "vera-delivery-v1").mkdir(parents=True)
    result = inspect_readiness(
        root, _policy(tmp_path, "0" * 64), _observation(tmp_path)
    )
    assert result["state"] == "repair_required"


def test_stray_launcher_without_release_is_repair_required(tmp_path: Path) -> None:
    root = tmp_path / "installed"
    root.mkdir()
    (root / "VERA Delivery v1.py").write_text("partial", encoding="utf-8")
    result = inspect_readiness(
        root, _policy(tmp_path, "0" * 64), _observation(tmp_path)
    )
    assert result["state"] == "repair_required"


@pytest.mark.parametrize("version", ["1", "2"])
def test_real_repository_release_inventory_is_recognised(
    tmp_path: Path, version: str
) -> None:
    release = tmp_path / "release"
    manifest = build_release(release) if version == "1" else build_release_v2(release)
    package = tmp_path / "ready-package"
    package.mkdir()
    policy = {
        "schemaVersion": "vera-companion-policy/v1",
        "releaseVersion": version,
        "releaseSha256": sha256(manifest),
        "approvedRoots": [str(tmp_path)],
        "approvedTools": ["resolve:injected"],
    }
    observation = {
        "packageRoot": str(package),
        "pairingState": "unknown",
        "serviceState": "unknown",
        "restartRequired": False,
    }
    before = _inventory(release)
    unknown = inspect_readiness(release, policy, observation)
    assert unknown["state"] == "unpaired"
    observation["pairingState"] = "paired"
    observation["serviceState"] = "connected"
    result = inspect_readiness(release, policy, observation)
    assert result["state"] == "native_preflight_required"
    assert result["canBuild"] is False
    assert result["nativeVerified"] is False
    assert _inventory(release) == before


def test_symlinked_package_path_is_refused(tmp_path: Path) -> None:
    root, digest = _installed(tmp_path)
    real_package = tmp_path / "approved" / "real-package"
    real_package.mkdir()
    (tmp_path / "approved" / "package").rmdir()
    (tmp_path / "approved" / "package").symlink_to(
        real_package, target_is_directory=True
    )
    result = inspect_readiness(root, _policy(tmp_path, digest), _observation(tmp_path))
    assert result["state"] == "approval_required"


def test_symlinked_approved_root_is_refused(tmp_path: Path) -> None:
    root, digest = _installed(tmp_path)
    real_root = tmp_path / "approved"
    (tmp_path / "approved" / "package").rmdir()
    real_root.rename(tmp_path / "real-approved")
    (tmp_path / "real-approved" / "package").mkdir()
    real_root.symlink_to(tmp_path / "real-approved", target_is_directory=True)
    observed = _observation(tmp_path)
    observed["packageRoot"] = str(tmp_path / "real-approved" / "package")
    result = inspect_readiness(root, _policy(tmp_path, digest), observed)
    assert result["state"] == "approval_required"


def test_symlink_inside_release_is_repair_required(tmp_path: Path) -> None:
    root, digest = _installed(tmp_path)
    target = tmp_path / "outside.py"
    target.write_text("outside", encoding="utf-8")
    (root / "vera-delivery-v1" / "linked.py").symlink_to(target)
    result = inspect_readiness(root, _policy(tmp_path, digest), _observation(tmp_path))
    assert result["state"] == "repair_required"


def test_declared_release_file_replaced_by_symlink_is_repair_required(
    tmp_path: Path,
) -> None:
    root, digest = _installed(tmp_path)
    module = root / "vera-delivery-v1/python/vera_timeline_agent/__init__.py"
    copy = tmp_path / "identical-copy.py"
    copy.write_bytes(module.read_bytes())
    module.unlink()
    module.symlink_to(copy)
    result = inspect_readiness(root, _policy(tmp_path, digest), _observation(tmp_path))
    assert result["state"] == "repair_required"


def test_symlinked_installed_ancestor_is_repair_required(tmp_path: Path) -> None:
    real = tmp_path / "real-install"
    _, digest = _installed(real)
    link = tmp_path / "linked-install"
    link.symlink_to(real, target_is_directory=True)
    result = inspect_readiness(
        link / "installed", _policy(real, digest), _observation(real)
    )
    assert result["state"] == "repair_required"


def test_symlinked_release_folder_is_repair_required(tmp_path: Path) -> None:
    root, digest = _installed(tmp_path)
    actual = tmp_path / "actual-release"
    (root / "vera-delivery-v1").rename(actual)
    (root / "vera-delivery-v1").symlink_to(actual, target_is_directory=True)
    result = inspect_readiness(root, _policy(tmp_path, digest), _observation(tmp_path))
    assert result["state"] == "repair_required"


def test_symlinked_installed_root_is_refused(tmp_path: Path) -> None:
    root, digest = _installed(tmp_path)
    link = tmp_path / "installed-link"
    link.symlink_to(root, target_is_directory=True)
    result = inspect_readiness(link, _policy(tmp_path, digest), _observation(tmp_path))
    assert result["state"] == "repair_required"


@pytest.mark.parametrize(
    "mutation",
    [
        "tool",
        "relative-root",
        "dotdot-root",
        "version",
        "digest",
        "extra-key",
        "missing-key",
        "restart-type",
        "observation-extra-key",
        "pairing-state",
        "relative-package",
    ],
)
def test_invalid_policy_or_observation_is_refused(
    tmp_path: Path, mutation: str
) -> None:
    root, digest = _installed(tmp_path)
    policy = _policy(tmp_path, digest)
    observed = _observation(tmp_path)
    if mutation == "tool":
        policy["approvedTools"] = ["resolve:external"]
    elif mutation == "relative-root":
        policy["approvedRoots"] = ["relative/path"]
    elif mutation == "dotdot-root":
        policy["approvedRoots"] = [str(tmp_path / "approved" / ".." / "approved")]
    elif mutation == "version":
        policy["releaseVersion"] = "3"
    elif mutation == "digest":
        policy["releaseSha256"] = "not-a-digest"
    elif mutation == "extra-key":
        policy["extra"] = True
    elif mutation == "missing-key":
        del policy["approvedTools"]
    elif mutation == "restart-type":
        observed["restartRequired"] = "false"
    elif mutation == "observation-extra-key":
        observed["extra"] = "value"
    elif mutation == "pairing-state":
        observed["pairingState"] = "probably-paired"
    elif mutation == "relative-package":
        observed["packageRoot"] = "approved/package"
    with pytest.raises(ValueError):
        inspect_readiness(root, policy, observed)


def test_evidence_is_immutable_and_never_inside_package(tmp_path: Path) -> None:
    root, digest = _installed(tmp_path)
    policy = _policy(tmp_path, digest)
    observation = _observation(tmp_path)
    (tmp_path / "evidence").mkdir()
    output = tmp_path / "evidence" / "readiness.json"
    retain_report(output, root, policy, observation)
    retained = json.loads(output.read_text(encoding="utf-8"))
    assert retained["state"] == "native_preflight_required"
    assert "packageRoot" not in retained
    assert "pairingState" not in retained
    assert str(tmp_path) not in output.read_text(encoding="utf-8")
    assert output.stat().st_mode & 0o777 == 0o400
    with pytest.raises(FileExistsError):
        retain_report(output, root, policy, observation)
    with pytest.raises(ValueError, match="outside the ready package"):
        retain_report(
            Path(str(observation["packageRoot"])) / "report.json",
            root,
            policy,
            observation,
        )


def test_report_refused_inside_installed_release(tmp_path: Path) -> None:
    root, digest = _installed(tmp_path)
    with pytest.raises(ValueError, match="installed release"):
        retain_report(
            root / "evidence.json",
            root,
            _policy(tmp_path, digest),
            _observation(tmp_path),
        )


def test_relative_report_path_is_refused(tmp_path: Path) -> None:
    root, digest = _installed(tmp_path)
    with pytest.raises(ValueError, match="absolute"):
        retain_report(
            Path("evidence.json"),
            root,
            _policy(tmp_path, digest),
            _observation(tmp_path),
        )


def test_report_parent_must_already_exist(tmp_path: Path) -> None:
    root, digest = _installed(tmp_path)
    with pytest.raises(ValueError, match="parent directory"):
        retain_report(
            tmp_path / "missing-evidence-dir" / "report.json",
            root,
            _policy(tmp_path, digest),
            _observation(tmp_path),
        )
    assert not (tmp_path / "missing-evidence-dir").exists()


def test_report_path_traversal_cannot_create_directories_in_release(
    tmp_path: Path,
) -> None:
    root, digest = _installed(tmp_path)
    (tmp_path / "evidence").mkdir()
    output = (
        root / "vera-delivery-v1" / "newdir" / ".." / ".." / "evidence" / "report.json"
    )
    with pytest.raises(ValueError, match="must not contain"):
        retain_report(output, root, _policy(tmp_path, digest), _observation(tmp_path))
    assert not (root / "vera-delivery-v1" / "newdir").exists()


def test_installed_root_with_parent_traversal_is_refused(tmp_path: Path) -> None:
    root, digest = _installed(tmp_path)
    with pytest.raises(ValueError, match="must not contain"):
        inspect_readiness(
            root / ".." / "installed",
            _policy(tmp_path, digest),
            _observation(tmp_path),
        )


def test_cli_writes_immutable_report_and_refuses_replay(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, digest = _installed(tmp_path)
    policy_path = tmp_path / "policy.json"
    observation_path = tmp_path / "observation.json"
    policy_path.write_text(json.dumps(_policy(tmp_path, digest)), encoding="utf-8")
    observation_path.write_text(json.dumps(_observation(tmp_path)), encoding="utf-8")
    (tmp_path / "evidence").mkdir()
    output = tmp_path / "evidence" / "readiness.json"
    arguments = [
        "--installed-root",
        str(root),
        "--policy",
        str(policy_path),
        "--observation",
        str(observation_path),
        "--output",
        str(output),
    ]
    assert companion_readiness_cli.main(arguments) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["state"] == (
        "native_preflight_required"
    )
    assert "sha256:" + sha256(output) in capsys.readouterr().out
    assert companion_readiness_cli.main(arguments) == 2
    assert not list(output.parent.glob(".vera-handoff-*"))


def test_cli_refuses_invalid_policy_without_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    policy_path = tmp_path / "policy.json"
    observation_path = tmp_path / "observation.json"
    policy_path.write_text(
        json.dumps({**_policy(tmp_path, "0" * 64), "approvedTools": []}),
        encoding="utf-8",
    )
    observation_path.write_text(json.dumps(_observation(tmp_path)), encoding="utf-8")
    output = tmp_path / "evidence" / "readiness.json"
    code = companion_readiness_cli.main(
        [
            "--installed-root",
            str(tmp_path / "missing"),
            "--policy",
            str(policy_path),
            "--observation",
            str(observation_path),
            "--output",
            str(output),
        ]
    )
    assert code == 2
    assert not output.exists()
    assert "refused" in capsys.readouterr().err


def test_cli_refuses_unparseable_policy_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    policy_path = tmp_path / "policy.json"
    observation_path = tmp_path / "observation.json"
    policy_path.write_text("[" * 2000 + "]" * 2000, encoding="utf-8")
    observation_path.write_text(json.dumps(_observation(tmp_path)), encoding="utf-8")
    (tmp_path / "evidence").mkdir()
    output = tmp_path / "evidence" / "readiness.json"
    code = companion_readiness_cli.main(
        [
            "--installed-root",
            str(tmp_path / "missing"),
            "--policy",
            str(policy_path),
            "--observation",
            str(observation_path),
            "--output",
            str(output),
        ]
    )
    assert code == 2
    assert not output.exists()
    assert "refused" in capsys.readouterr().err


def test_malformed_manifest_with_matching_digest_is_repair_required(
    tmp_path: Path,
) -> None:
    root, _ = _installed(tmp_path)
    manifest_path = root / "vera-delivery-v1" / "release.json"
    manifest_path.write_text("{", encoding="utf-8")
    result = inspect_readiness(
        root, _policy(tmp_path, sha256(manifest_path)), _observation(tmp_path)
    )
    assert result["state"] == "repair_required"


def test_unknown_release_schema_with_matching_digest_is_incompatible(
    tmp_path: Path,
) -> None:
    root, _ = _installed(tmp_path)
    manifest_path = root / "vera-delivery-v1" / "release.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schemaVersion"] = "vera-injected-delivery-release/v3"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = inspect_readiness(
        root, _policy(tmp_path, sha256(manifest_path)), _observation(tmp_path)
    )
    assert result["state"] == "incompatible_version"


def test_other_supported_version_installed_is_incompatible(tmp_path: Path) -> None:
    root, _ = _installed(tmp_path, "2")
    result = inspect_readiness(
        root, _policy(tmp_path, "0" * 64, version="1"), _observation(tmp_path)
    )
    assert result["state"] == "incompatible_version"


def test_unknown_versioned_install_is_incompatible(tmp_path: Path) -> None:
    root, _ = _installed(tmp_path)
    future = root / "vera-delivery-v3"
    future.mkdir()
    (future / "release.json").write_text("{}", encoding="utf-8")
    (root / "vera-delivery-v1").rename(tmp_path / "archived-v1")
    result = inspect_readiness(
        root, _policy(tmp_path, "0" * 64, version="1"), _observation(tmp_path)
    )
    assert result["state"] == "incompatible_version"


def test_unrelated_version_named_archive_is_not_an_install(tmp_path: Path) -> None:
    root = tmp_path / "installed"
    root.mkdir()
    (root / "vera-delivery-v1.zip").write_text("archive", encoding="utf-8")
    result = inspect_readiness(
        root, _policy(tmp_path, "0" * 64), _observation(tmp_path)
    )
    assert result["state"] == "first_run"


def test_stale_unused_approved_root_does_not_block_selected_root(
    tmp_path: Path,
) -> None:
    root, digest = _installed(tmp_path)
    policy = _policy(tmp_path, digest)
    policy["approvedRoots"] = [
        str(tmp_path / "unmounted-archive"),
        str(tmp_path / "approved"),
    ]
    result = inspect_readiness(root, policy, _observation(tmp_path))
    assert result["state"] == "native_preflight_required"


def test_manifest_with_undeclared_path_prefix_is_refused(tmp_path: Path) -> None:
    root, _ = _installed(tmp_path)
    manifest_path = root / "vera-delivery-v1" / "release.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"].append(
        {"path": "some-other-plugin.py", "sha256": "0" * 64, "sizeBytes": 0}
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = inspect_readiness(
        root,
        _policy(tmp_path, sha256(manifest_path)),
        _observation(tmp_path),
    )
    assert result["state"] == "repair_required"


def test_request_file_is_not_part_of_the_release_inventory(tmp_path: Path) -> None:
    root, digest = _installed(tmp_path)
    write_immutable_json(
        root / "vera-delivery-v1" / "request.json",
        {"schemaVersion": "vera-injected-delivery-request/v1"},
    )
    result = inspect_readiness(root, _policy(tmp_path, digest), _observation(tmp_path))
    assert result["state"] == "native_preflight_required"
