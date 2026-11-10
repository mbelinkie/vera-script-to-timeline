"""Linux-safe Phase 3 checks; live signed macOS checks are separate evidence."""

from __future__ import annotations

import importlib.util
import json
import os
import plistlib
from pathlib import Path
from types import ModuleType

import pytest
from vera_timeline_agent import resolve_gui_helper_protocol as helper
from vera_timeline_agent.roundtrip_v2_records import ROOT, proof_source_hashes_v2

HELPER = ROOT / "macos/vera-gui-helper"


def _probe() -> ModuleType:
    path = HELPER / "focus-probe.py"
    spec = importlib.util.spec_from_file_location("vera_focus_probe_phase3", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _request() -> dict[str, object]:
    return {
        "schema": "vera.gui-helper-focus-request/v1",
        "requestId": "phase3-test-001",
        "deadlineAt": "2026-11-10T19:00:00Z",
        "operation": "inspect",
        "resolvePid": 5182,
        "resolveBundleIdentifier": "com.blackmagic-design.DaVinciResolve",
        "windowName": "VERA Delivery disposable test",
    }


def test_focus_spool_publish_is_private_exclusive_and_fsynced(tmp_path: Path) -> None:
    probe = _probe()
    tmp_path.chmod(0o700)
    request = _request()
    raw = probe.publish(tmp_path, request)
    target = tmp_path / "phase3-test-001.focus-request.json"
    assert raw == probe.canonical(request)
    assert json.loads(raw) == request
    assert target.read_bytes() == raw
    assert target.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        probe.publish(tmp_path, request)
    assert target.read_bytes() == raw


def test_focus_spool_refuses_public_dir_or_alias(tmp_path: Path) -> None:
    probe = _probe()
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    symlink = tmp_path / "alias"
    symlink.symlink_to(private, target_is_directory=True)
    with pytest.raises(ValueError, match="non-private"):
        probe.publish(symlink, _request())
    private.chmod(0o755)
    with pytest.raises(ValueError, match="non-private"):
        probe.publish(private, _request())


def test_focus_spool_refuses_existing_symlink_request_file(tmp_path: Path) -> None:
    probe = _probe()
    tmp_path.chmod(0o700)
    existing = tmp_path / "existing"
    existing.write_bytes(b"not a request")
    request_alias = tmp_path / "phase3-test-001.focus-request.json"
    request_alias.symlink_to(existing)
    with pytest.raises(FileExistsError):
        probe.publish(tmp_path, _request())
    assert existing.read_bytes() == b"not a request"


def test_direct_aqua_launchagent_is_no_edit_and_no_python_worker() -> None:
    template = (HELPER / "LaunchAgent.plist.in").read_bytes()
    plist = plistlib.loads(template)
    assert plist["Label"] == "org.vera.resolve-test-bench.gui"
    assert plist["ProgramArguments"] == ["@VERA_GUI_HELPER_EXECUTABLE@"]
    assert plist["LimitLoadToSessionType"] == "Aqua"
    assert plist["KeepAlive"] is True
    assert plist["RunAtLoad"] is True
    assert plist["EnvironmentVariables"] == {
        "VERA_GUI_HELPER_SPOOL": "@VERA_GUI_HELPER_SPOOL@"
    }
    assert not any("python" in value.lower() for value in plist["ProgramArguments"])
    assert "StartInterval" not in plist


def test_phase3_build_and_source_never_expose_menu_press() -> None:
    # The later Phase 4 intentionally adds the separately authorized Roll
    # actuator to TargetInspection. The Phase 3 focus/inspection entrypoint
    # must stay incapable of executing a menu leaf.
    focus_source = (HELPER / "Sources/VERAGUIHelper/FocusProtocol.swift").read_text()
    inspection_source = (
        HELPER / "Sources/VERAGUIHelper/TargetInspection.swift"
    ).read_text()
    focus_entrypoint = inspection_source.split("    static func perform(", 1)[1]
    source = "\n".join(
        line
        for line in (focus_source + focus_entrypoint).splitlines()
        if not line.lstrip().startswith("//")
    )
    assert "AXUIElementPerformAction" not in source
    assert "AXPress" not in source
    assert "osascript" not in source
    assert '"roll"' not in (HELPER / "focus-probe.py").read_text()
    assert "AXIsProcessTrusted" in source
    assert (
        "SetFrontProcessWithOptions"
        in (HELPER / "Sources/VERAGUIHelper/LegacyForeground.c").read_text()
    )
    build = (HELPER / "build.sh").read_text()
    assert "security find-identity -v -p codesigning" in build
    assert "codesign --verify --strict" in build
    assert '"$identity"' in build
    assert "Developer ID Application" not in build
    assert os.path.isabs(str(HELPER))


def test_generated_probe_bytecode_does_not_drift_sealed_helper_or_proof_graph() -> None:
    before = helper.source_manifest_sha256()
    previous_graph = proof_source_hashes_v2()
    cache = HELPER / "__pycache__"
    cache.mkdir(exist_ok=True)
    pyc = cache / "phase3-tmp-probe-test.pyc"
    pyc.write_bytes(b"synthetic bytecode; not source")
    try:
        assert helper.source_manifest_sha256() == before
        assert proof_source_hashes_v2() == previous_graph
        assert not any(
            "__pycache__" in name for name in helper.source_manifest()["files"]
        )
    finally:
        pyc.unlink()
