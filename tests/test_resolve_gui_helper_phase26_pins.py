"""Issue #499: zero-Resolve regression checks for the frozen helper pin installer."""

from __future__ import annotations

import hashlib
import importlib.util
import plistlib
import stat
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent.roundtrip_v2_records import ROOT

HELPER = ROOT / "macos/vera-gui-helper"


def module() -> ModuleType:
    path = HELPER / "pin-launch-agent.py"
    spec = importlib.util.spec_from_file_location("vera_pin_installer_phase26", path)
    assert spec and spec.loader
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def actor() -> dict[str, Any]:
    return {
        "schema": "vera.gui-helper-actor/v1",
        "sourceManifestSha256": "f" * 64,
        "binary": {
            "executablePath": (
                "/Users/test/Library/Application Support/VERA/GUI Helper/"
                "VERA GUI Helper.app/Contents/MacOS/VERAGUIHelper"
            ),
            "sha256": "a" * 64,
            "codeDirectoryHash": "b" * 40,
            "designatedRequirement": (
                'identifier "org.vera.resolve-test-bench.gui" and anchor apple generic '
                'and certificate leaf[subject.OU] = "EXAMPLE1234"'
            ),
            "teamIdentifier": "EXAMPLE1234",
            "bundleIdentifier": "org.vera.resolve-test-bench.gui",
        },
    }


def test_source_template_has_just_three_authorized_signed_helper_env_values() -> None:
    source = plistlib.loads((HELPER / "LaunchAgent.plist.in").read_bytes())
    assert source["ProgramArguments"] == ["@VERA_GUI_HELPER_EXECUTABLE@"]
    assert source["EnvironmentVariables"] == {
        "VERA_GUI_HELPER_SPOOL": "@VERA_GUI_HELPER_SPOOL@",
        "VERA_GUI_HELPER_ACTOR_PIN_SHA256": "@VERA_GUI_HELPER_ACTOR_PIN_SHA256@",
        "VERA_GUI_HELPER_SOURCE_GRAPH_SHA256": "@VERA_GUI_HELPER_SOURCE_GRAPH_SHA256@",
    }
    assert "KeepAlive" in source and source["KeepAlive"] is True
    assert "StartInterval" not in source


def test_installer_renders_only_computed_sha256_pins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = module()
    sample = actor()
    monkeypatch.setattr(value, "EXE", Path(sample["binary"]["executablePath"]))
    monkeypatch.setattr(
        value,
        "SPOOL",
        Path("/Users/test/Library/Application Support/VERA/GUI Helper/spool"),
    )
    graph = "d" * 64
    raw = value.render(sample, graph)
    plist = plistlib.loads(raw)
    assert plist["ProgramArguments"] == [sample["binary"]["executablePath"]]
    assert plist["EnvironmentVariables"] == {
        "VERA_GUI_HELPER_SPOOL": str(value.SPOOL),
        "VERA_GUI_HELPER_ACTOR_PIN_SHA256": hashlib.sha256(
            queue.canonical(sample)
        ).hexdigest(),
        "VERA_GUI_HELPER_SOURCE_GRAPH_SHA256": graph,
    }
    assert raw == plistlib.dumps(plist, sort_keys=True)


def test_legacy_plist_migration_requires_exact_bytes_not_tolerant_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = module()
    source = plistlib.loads(value.TEMPLATE.read_bytes())
    source["ProgramArguments"] = [
        "/Users/test/VERA GUI Helper.app/Contents/MacOS/VERAGUIHelper"
    ]
    source["EnvironmentVariables"] = {"VERA_GUI_HELPER_SPOOL": "/Users/test/spool"}
    exact = plistlib.dumps(source, sort_keys=True)
    assert value.legacy_exact(exact, source["ProgramArguments"][0], "/Users/test/spool")
    changed = source.copy()
    changed["EnvironmentVariables"] = {
        "VERA_GUI_HELPER_SPOOL": "/Users/test/spool",
        "EXTRA": "unsafe",
    }
    assert not value.legacy_exact(
        plistlib.dumps(changed), source["ProgramArguments"][0], "/Users/test/spool"
    )
    changed = source.copy()
    changed["KeepAlive"] = False
    assert not value.legacy_exact(
        plistlib.dumps(changed), source["ProgramArguments"][0], "/Users/test/spool"
    )
    assert not value.legacy_exact(
        exact + b" ", source["ProgramArguments"][0], "/Users/test/spool"
    )
    assert not value.legacy_exact(exact, "/different/helper", "/Users/test/spool")


def test_owner_only_atomic_replace_never_follows_symlink(tmp_path: Path) -> None:
    value = module()
    target = tmp_path / "pinned.plist"
    old = b"old exact evidence"
    target.write_bytes(old)
    target.chmod(0o600)
    value.safe_replace(target, b"new pin contract")
    assert target.read_bytes() == b"new pin contract"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".vera-pinned-*"))
    outside = tmp_path / "outside"
    outside.write_bytes(b"must never change")
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises((ValueError, RuntimeError, OSError)):
        value.private_file(target)
    assert outside.read_bytes() == b"must never change"


def test_physical_no_edit_probe_and_roll_inputs_use_separate_swift_protocol() -> None:
    roll = (HELPER / "Sources/VERAGUIHelper/RollActuator.swift").read_text()
    spool = (HELPER / "Sources/VERAGUIHelper/RollSpool.swift").read_text()
    main = (HELPER / "Sources/VERAGUIHelper/main.swift").read_text()
    assert (
        'pinProbeOnly ? "M4.edited.verify-actor-no-edit"' in roll
        and '"M4.edited.roll-start-to-playhead"' in roll
    )
    assert "func pollPinProbe() -> Bool" in spool
    assert "try NativeRollPins().verify(request)" in spool
    probe = spool.split("func pollPinProbe() -> Bool", 1)[1].split(
        "    func poll()", 1
    )[0]
    assert "FixedRoll.execute" not in probe
    assert "accessibility.press" not in probe
    assert "AXUIElementPerformAction" not in probe
    assert "claimPinProbe" in probe
    assert "journal.claimAdmission" not in probe
    assert "if self.rollSpool?.pollPinProbe() == true { return }" in main
    assert "intent-" in spool and ".roll-admission-consumed.json" in spool
    assert "roll-consumed.json" in spool
    assert '".reply.json"' in spool


def test_install_path_requires_frozen_checkout_and_separate_live_probe() -> None:
    installer = (HELPER / "pin-launch-agent.py").read_text()
    shell = (HELPER / "install-launch-agent.sh").read_text()
    assert "full._frozen_source(commit)" in installer
    assert "protocol.validate_actor_pin(actor, installed=True)" in installer
    assert "native_owner(output_lane=True)" in installer
    assert 'launch_ctl("bootout", label)' in installer
    assert 'launch_ctl("bootstrap", domain, str(PLIST))' in installer
    assert 'probe_id + ".pin-probe-request.json"' in installer
    assert 'reply["status"] == "pin-verified"' in installer
    assert "previous_pid=old_pid" in installer
    assert "verify_pin_probe(" in installer
    assert 'exec "$python" "$root/pin-launch-agent.py"' in shell
    assert "kickstart -k" not in shell
    assert "rm -rf" not in installer
    assert "rm -rf" not in shell
    assert 'rm -rf "$previous"' not in (HELPER / "build.sh").read_text()


def test_python_swift_shared_actor_json_sha256_golden() -> None:
    swift_actor = {
        "schema": "vera.gui-helper-actor/v1",
        "sourceManifestSha256": "b" * 64,
        "binary": {
            "executablePath": "/tmp/VERA GUI Helper.app/Contents/MacOS/VERAGUIHelper",
            "sha256": "c" * 64,
            "codeDirectoryHash": "d" * 40,
            "designatedRequirement": (
                'identifier "org.vera.resolve-test-bench.gui" and anchor apple generic'
            ),
            "teamIdentifier": "D3Z8Y24NKY",
            "bundleIdentifier": "org.vera.resolve-test-bench.gui",
        },
    }
    digest = "9cbc933da7d23e0cb76b0996eeac3913ace4906e25423e1cd9da82c842e27f3c"
    assert hashlib.sha256(queue.canonical(swift_actor)).hexdigest() == digest
    assert (
        digest
        in (HELPER / "Sources/VERAGUIHelper/RollActuatorSelfTest.swift").read_text()
    )


def test_signed_binary_must_have_a_clean_frozen_build_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = module()
    monkeypatch.setattr(value, "BASE", tmp_path)
    sha256 = "a" * 64
    expected = {
        "schema": "vera.gui-helper-signed-build-source/v1",
        "binarySha256": sha256,
        "frozenCommit": "b" * 40,
        "sourceGraphSha256": "c" * 64,
        "sourceManifestSha256": "d" * 64,
    }
    target = tmp_path / ("built-source-pins-" + sha256 + ".json")
    with pytest.raises((FileNotFoundError, ValueError, RuntimeError)):
        value.verified_build_provenance(
            expected["frozenCommit"],
            expected["sourceGraphSha256"],
            expected["sourceManifestSha256"],
            sha256,
        )
    target.write_bytes(queue.canonical(expected))
    target.chmod(0o600)
    value.verified_build_provenance(
        expected["frozenCommit"],
        expected["sourceGraphSha256"],
        expected["sourceManifestSha256"],
        sha256,
    )
    with pytest.raises((ValueError, RuntimeError), match="not proved built"):
        value.verified_build_provenance(
            expected["frozenCommit"], "0" * 64, expected["sourceManifestSha256"], sha256
        )
    with pytest.raises((ValueError, RuntimeError), match="not proved built"):
        value.verified_build_provenance(
            "e" * 40,
            expected["sourceGraphSha256"],
            expected["sourceManifestSha256"],
            sha256,
        )


def test_roll_boundary_refuses_unicode_before_any_one_use_gui_claim() -> None:
    from vera_timeline_agent import resolve_gui_helper_protocol as protocol

    assert protocol._name("VERA disposable M4 native")
    assert not protocol._name("VERA Café disposable")
    assert not protocol._name("A—B")
    binary = dict(actor()["binary"])
    binary["designatedRequirement"] = binary["designatedRequirement"] + " é"
    with pytest.raises(protocol.HelperProtocolError):
        protocol.validate_binary_pin(binary)
    binary = dict(actor()["binary"])
    binary["executablePath"] = binary["executablePath"].replace("/Users/", "/Usérs/")
    with pytest.raises(protocol.HelperProtocolError):
        protocol.validate_binary_pin(binary)
    assert (
        "s.utf8.allSatisfy { $0 >= 32 && $0 < 127 }"
        in (HELPER / "Sources/VERAGUIHelper/RollActuator.swift").read_text()
    )


def test_signing_build_requires_clean_git_head_and_records_exact_source() -> None:
    build = (HELPER / "build.sh").read_text()
    installer = (HELPER / "pin-launch-agent.py").read_text()
    assert "freeze_pins()" in build and "_frozen_source(head)" in build
    assert "source_manifest_sha256()" in build
    assert "helper source changed during build or signing" in build
    assert "built-source-pins-" in build and "built-source-pins-" in installer
    assert "verified_build_provenance" in installer
    assert "signed_actor(commit, graph)" in installer
