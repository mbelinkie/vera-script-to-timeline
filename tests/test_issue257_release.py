"""The precision probe is selected explicitly and cannot enter strict releases."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from vera_timeline_agent.workflow_package import sha256
from vera_timeline_agent.workflow_v2_cli import (
    OUTPUT_RUNTIME_FILES,
    RELEASE_NAME,
    RUNTIME_FILES,
    SAMPLE_PRECISION_RUNTIME_FILES,
    _verify_output_release,
    _verify_release_files,
    build_sample_precision_release_v2,
)
from vera_timeline_agent.workflow_v2_launcher import run_installed_request_v2


def test_precision_release_is_separate_and_tamper_evident(tmp_path: Path) -> None:
    root = tmp_path / "release"
    manifest = build_sample_precision_release_v2(root)
    assert set(SAMPLE_PRECISION_RUNTIME_FILES) - set(RUNTIME_FILES) == {
        "sample_precision_probe_v2.py"
    }
    assert "sample_precision_probe_v2.py" not in OUTPUT_RUNTIME_FILES
    assert _verify_release_files(root, SAMPLE_PRECISION_RUNTIME_FILES) == manifest
    with pytest.raises(ValueError, match="repository-owned runtime"):
        _verify_output_release(root)
    module = (
        root / RELEASE_NAME / "python/vera_timeline_agent/sample_precision_probe_v2.py"
    )
    module.write_bytes(module.read_bytes() + b"\n# changed\n")
    with pytest.raises(ValueError, match="repository-owned runtime"):
        _verify_release_files(root, SAMPLE_PRECISION_RUNTIME_FILES)


def test_probe_dispatch_retains_request_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import sample_precision_probe_v2 as probe

    request = tmp_path / "request.json"
    request.write_text(json.dumps({"schemaVersion": probe.REQUEST_SCHEMA}))
    pin = sha256(request)
    calls: list[tuple[object, Path, str]] = []

    def run(resolve: object, path: Path, *, expected_request_sha256: str) -> Path:
        calls.append((resolve, path, expected_request_sha256))
        return tmp_path / "result.json"

    monkeypatch.setattr(probe, "run_sample_precision_probe", run)
    resolve = object()
    run_installed_request_v2(resolve, request, expected_request_sha256=pin)
    assert calls == [(resolve, request, pin)]
    request.write_text(request.read_text() + " ")
    with pytest.raises(ValueError, match="changed"):
        run_installed_request_v2(resolve, request, expected_request_sha256=pin)
    assert len(calls) == 1
