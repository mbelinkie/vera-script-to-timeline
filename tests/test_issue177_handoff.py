"""Versioned handoff/release regressions; no real Studio or media tools."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from issue177_package_fixture import make_package_case
from vera_timeline_agent.workflow_package import (
    read_object,
    sha256,
    write_immutable_json,
)
from vera_timeline_agent.workflow_v2 import load_verified_package_v2
from vera_timeline_agent.workflow_v2_cli import (
    LAUNCHER_NAME,
    RELEASE_NAME,
    attest_package_v2,
    build_release_v2,
    main,
)
from vera_timeline_agent.workflow_v2_launcher import run_installed_request_v2


def request_value(release: Path, evidence: Path, package: Path) -> dict[str, Any]:
    return {
        "schemaVersion": "vera-injected-delivery-request/v2",
        "releaseSha256": sha256(release / RELEASE_NAME / "release.json"),
        "attestationPath": str(package.parent / "missing-attestation.json"),
        "attestationSha256": "0" * 64,
        "packageDir": str(package),
        "projectName": "missing-target",
        "timelineName": "missing-target",
        "evidenceDir": str(evidence),
        "action": "preflight",
        "authorizeNewNonproduction": False,
        "externalScripting": "None",
    }


def launch(release: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-S", str(release / LAUNCHER_NAME)],
        check=True,
        capture_output=True,
        text=True,
    )


def test_independent_attestation_roundtrip_and_media_drift(tmp_path: Path) -> None:
    case = make_package_case(tmp_path)
    built = case.build()
    attestation = attest_package_v2(case.project_root, tmp_path / "attestation.json")
    digest = sha256(attestation)
    loaded = load_verified_package_v2(attestation, digest)
    assert loaded.root == case.project_root
    assert loaded.manifest["schemaVersion"] == "timeline-manifest/v2"
    assert loaded.attestation["buildId"] == built.build_id
    assert loaded.attestation["verification"]["eventCount"] == len(
        loaded.view["events"]
    )
    assert loaded.attestation["verification"]["mediaCount"] == len(
        loaded.view["sources"]
    )
    with pytest.raises(ValueError, match="new"):
        attest_package_v2(case.project_root, attestation)
    assert sha256(attestation) == digest
    media = case.project_root / loaded.view["sources"][0]["path"]
    media.chmod(0o600)
    media.write_bytes(b"changed after attestation")
    with pytest.raises(ValueError):
        load_verified_package_v2(attestation, digest)


def test_v2_handoff_does_not_accept_v1_attestation(tmp_path: Path) -> None:
    attestation = write_immutable_json(
        tmp_path / "v1.json", {"schemaVersion": "vera-injected-delivery-attestation/v1"}
    )
    with pytest.raises(ValueError):
        load_verified_package_v2(attestation, sha256(attestation))


@pytest.mark.parametrize(
    "attack", [None, "local-scripting", "tampered", "rehashed", "unauthorized-build"]
)
def test_cli_request_binds_verified_package_and_owned_release(
    tmp_path: Path, attack: str | None
) -> None:
    case = make_package_case(tmp_path)
    case.build()
    attestation = attest_package_v2(case.project_root, tmp_path / "attestation.json")
    release = tmp_path / "release"
    manifest = build_release_v2(release)
    if attack in {"tampered", "rehashed"}:
        runtime = release / RELEASE_NAME / "python/vera_timeline_agent/workflow_v2.py"
        runtime.write_text("raise RuntimeError('untrusted runtime')\n")
        if attack == "rehashed":
            value = read_object(manifest)
            for item in value["files"]:
                if item["path"] == runtime.relative_to(release).as_posix():
                    item.update(
                        sha256=sha256(runtime), sizeBytes=runtime.stat().st_size
                    )
            manifest.chmod(0o600)
            manifest.write_text(json.dumps(value))
    output = tmp_path / "request.json"
    arguments = [
        "request",
        str(attestation),
        "--release",
        str(release),
        "--output",
        str(output),
        "--evidence-dir",
        str(tmp_path / "evidence"),
    ]
    if attack == "unauthorized-build":
        arguments += ["--action", "build"]
    elif attack == "local-scripting":
        arguments += ["--external-scripting-local"]
    result = main(arguments)
    if attack in {"tampered", "rehashed", "unauthorized-build"}:
        assert result == 2
        assert not output.exists()
    else:
        assert result == 0
        request = read_object(output)
        assert request["releaseSha256"] == sha256(manifest)
        assert request["attestationSha256"] == sha256(attestation)
        assert request["packageDir"] == str(case.project_root)
        assert request["action"] == "preflight"
        assert request["externalScripting"] == (
            "Local" if attack == "local-scripting" else None
        )


def test_release_reproducible_and_refuses_overwrite(tmp_path: Path) -> None:
    one = build_release_v2(tmp_path / "one")
    two = build_release_v2(tmp_path / "two")
    assert one.read_bytes() == two.read_bytes()
    manifest = read_object(one)
    assert manifest["schemaVersion"] == "vera-injected-delivery-release/v2"
    assert manifest["deliveryVersion"] == "2"
    inventory = {item["path"] for item in manifest["files"]}
    assert any(item.endswith("workflow_v2.py") for item in inventory)
    assert not any(item.endswith("v2_package.py") for item in inventory)
    with pytest.raises(FileExistsError):
        build_release_v2(tmp_path / "one")
    assert one.read_bytes() == two.read_bytes()


def test_release_output_refuses_ancestor_symlink(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic link"):
        build_release_v2(link / "release")
    assert list(actual.iterdir()) == []


def test_stdlib_bootstrap_retains_unique_refusals(tmp_path: Path) -> None:
    release = tmp_path / "release"
    build_release_v2(release)
    evidence = tmp_path / "evidence"
    package = tmp_path / "package"
    package.mkdir()
    write_immutable_json(
        release / RELEASE_NAME / "request.json",
        request_value(release, evidence, package),
    )
    first, second, third = launch(release), launch(release), launch(release)
    assert first.stdout != second.stdout != third.stdout
    assert len(list(evidence.glob("started-*.json"))) == 1
    assert len(list(evidence.glob("bootstrap-refusal-*.json"))) == 2
    for replay in (second, third):
        assert json.loads(replay.stdout)["status"] == "workflow_v2_launcher_failed"
    reports = list(evidence.glob("result-*.json"))
    assert len(reports) == 1
    for report in reports:
        value = read_object(report)
        assert value["schemaVersion"] == "vera-injected-delivery-result/v2"
        assert value["status"] == "stopped_safely"
        assert value["verified"] is False
        assert value["partialTargetRetained"] is False
    hashes = [read_object(path) for path in evidence.glob("hashes-*.json")]
    assert {item["resultSha256"] for item in hashes} == {
        sha256(path) for path in reports
    }
    assert list(package.iterdir()) == []


@pytest.mark.parametrize(
    "attack", ["wrong-bytes", "extra-code", "symlink", "v1-release"]
)
def test_bootstrap_refuses_changed_release_before_loading_runtime(
    tmp_path: Path, attack: str
) -> None:
    release = tmp_path / "release"
    manifest = build_release_v2(release)
    evidence = tmp_path / "evidence"
    package = tmp_path / "package"
    package.mkdir()
    runtime = release / RELEASE_NAME / "python/vera_timeline_agent"
    value = request_value(release, evidence, package)
    if attack == "wrong-bytes":
        (runtime / "workflow_v2.py").write_text(
            "raise RuntimeError('unverified-code-loaded')\n"
        )
    elif attack == "extra-code":
        (runtime / "unverified.py").write_text(
            "raise RuntimeError('unverified-code-loaded')\n"
        )
    elif attack == "symlink":
        (runtime / "escape.py").symlink_to(tmp_path / "outside.py")
    else:
        changed = read_object(manifest)
        changed["schemaVersion"] = "vera-injected-delivery-release/v1"
        manifest.chmod(0o600)
        manifest.write_text(json.dumps(changed))
        value["releaseSha256"] = sha256(manifest)
    write_immutable_json(release / RELEASE_NAME / "request.json", value)
    result = json.loads(launch(release).stdout)
    assert result["status"] == "workflow_v2_launcher_failed"
    assert "unverified-code-loaded" not in result["detail"]
    assert list(package.iterdir()) == []


@pytest.mark.parametrize(
    "attack",
    [
        "hash",
        "v1",
        "extra-field",
        "boolean",
        "evidence-in-package",
        "digest",
        "scripting",
    ],
)
def test_operator_request_refuses_before_native_or_package_mutation(
    tmp_path: Path, attack: str
) -> None:
    release = tmp_path / "release"
    build_release_v2(release)
    package = tmp_path / "package"
    package.mkdir()
    value = request_value(release, tmp_path / "evidence", package)
    if attack == "v1":
        value["schemaVersion"] = "vera-injected-delivery-request/v1"
    elif attack == "extra-field":
        value["overrideTarget"] = True
    elif attack == "boolean":
        value["authorizeNewNonproduction"] = "true"
    elif attack == "evidence-in-package":
        value["evidenceDir"] = str(package / "evidence")
    elif attack == "digest":
        value["releaseSha256"] = "invalid"
    elif attack == "scripting":
        value["externalScripting"] = "Network"
    request = write_immutable_json(release / RELEASE_NAME / "request.json", value)
    with pytest.raises(ValueError):
        run_installed_request_v2(
            object(),
            request,
            expected_request_sha256="0" * 64 if attack == "hash" else sha256(request),
        )
    assert list(package.iterdir()) == []


def test_declared_package_cannot_hide_protected_attestation_package(
    tmp_path: Path,
) -> None:
    release = tmp_path / "release"
    build_release_v2(release)
    actual = tmp_path / "actual-package"
    actual.mkdir()
    value = request_value(release, actual / "evidence", tmp_path / "wrong-package")
    write_immutable_json(Path(value["attestationPath"]), {"packageDir": str(actual)})
    request = write_immutable_json(release / RELEASE_NAME / "request.json", value)
    with pytest.raises(ValueError, match="evidence"):
        run_installed_request_v2(
            object(), request, expected_request_sha256=sha256(request)
        )
    assert list(actual.iterdir()) == []
