"""Separate output release closure; no installation or native application use."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from vera_timeline_agent.workflow_v2_cli import (
    OUTPUT_RUNTIME_FILES,
    RELEASE_NAME,
    RUNTIME_FILES,
    _verify_output_release,
    _verify_release,
    build_output_release_v2,
    build_release_v2,
)


def test_output_release_is_distinct_reproducible_and_closed(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    one, two = tmp_path / "one", tmp_path / "two"
    build_release_v2(legacy)
    first = build_output_release_v2(one)
    second = build_output_release_v2(two)
    assert first.read_bytes() == second.read_bytes()
    assert set(OUTPUT_RUNTIME_FILES) - set(RUNTIME_FILES) == {
        "qualification_output_native_v2.py",
        "qualification_output_records_v2.py",
    }
    for name in (
        "qualification_output_controller_v2.py",
        "qualification_output_decode_v2.py",
        "qualification_output_package_v2.py",
        "qualification_output_v2.py",
    ):
        assert name not in OUTPUT_RUNTIME_FILES
    assert _verify_output_release(one) == first
    _verify_release(legacy)
    with pytest.raises(ValueError, match="repository-owned runtime"):
        _verify_release(one)
    with pytest.raises(ValueError, match="repository-owned runtime"):
        _verify_output_release(legacy)


def test_shared_runtime_declarations_include_recorder() -> None:
    from vera_timeline_agent.native_qualification_v2 import RUNTIME_FILES as preflight
    from vera_timeline_agent.qualification_output_native_v2 import (
        _OUTPUT_RUNTIME_FILES,
    )
    from vera_timeline_agent.sample_precision_probe_v2 import RELEASE_RUNTIME_FILES
    from vera_timeline_agent.target_identity_v2 import TI_RUNTIME_FILES

    assert set(preflight) == set(TI_RUNTIME_FILES) == set(RUNTIME_FILES)
    assert "performance_v2.py" in RUNTIME_FILES
    assert set(_OUTPUT_RUNTIME_FILES) == set(OUTPUT_RUNTIME_FILES)
    assert set(RELEASE_RUNTIME_FILES) == {
        *RUNTIME_FILES,
        "sample_precision_probe_v2.py",
    }


def test_installed_output_import_has_no_host_dependencies(tmp_path: Path) -> None:
    release = tmp_path / "output"
    build_output_release_v2(release)
    runtime = release / RELEASE_NAME / "python"
    code = """
import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
from vera_timeline_agent import qualification_output_native_v2
for forbidden in ('qualification_output_controller_v2',
                  'qualification_output_decode_v2',
                  'qualification_output_package_v2', 'qualification_output_v2',
                  'v2_package', 'media_preparation', 'jsonschema', 'opentimelineio'):
    matches = [name for name in sys.modules
               if name == forbidden or name.endswith('.' + forbidden)]
    assert not matches, forbidden
names = [name for name in sys.modules if name.startswith('vera_timeline_agent')]
print(json.dumps(sorted(names)))
"""
    result = subprocess.run(
        [sys.executable, "-S", "-c", code, str(runtime)],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    assert "vera_timeline_agent.qualification_output_native_v2" in json.loads(
        result.stdout
    )
    _verify_output_release(release)


@pytest.mark.parametrize(
    "module", ["qualification_output_native_v2.py", "performance_v2.py"]
)
def test_output_inventory_tamper_refuses_before_operator_use(
    tmp_path: Path, module: str
) -> None:
    root = tmp_path / "output"
    build_output_release_v2(root)
    native = root / RELEASE_NAME / "python/vera_timeline_agent" / module
    native.write_bytes(native.read_bytes() + b"\n# tampered\n")
    with pytest.raises(ValueError, match="repository-owned runtime"):
        _verify_output_release(root)


def test_output_stage_cli_uses_explicit_host_methods_without_issuing_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from vera_timeline_agent import qualification_output_controller_v2 as controller
    from vera_timeline_agent.workflow_package import sha256
    from vera_timeline_agent.workflow_v2_cli import main

    session = tmp_path / "session.json"
    approval = tmp_path / "approval.json"
    result = tmp_path / "result.json"
    request = tmp_path / "request.json"
    handoff = tmp_path / "host-artifacts" / "operator-handoff.json"
    comparison = tmp_path / "comparison.json"
    for path in (session, approval, result, request, comparison):
        path.write_bytes(b"retained")

    calls: list[tuple[object, ...]] = []

    class HostStages:
        def prepare_next_native_request(self, approval_path: Path) -> Path:
            calls.append(("next", approval_path))
            handoff.parent.mkdir()
            handoff.write_bytes(b"handoff")
            return request

        def native_operator_handoff_path(self, _request_path: Path) -> Path:
            return handoff

        def inspect_recovery(self) -> dict[str, str]:
            calls.append(("recover",))
            return {
                "reportType": "inventory_only_not_qualified_receipts",
                "status": "empty",
            }

        def ingest_native_result(
            self, result_path: Path, result_sha256: str
        ) -> dict[str, str]:
            calls.append(("ingest", result_path, result_sha256))
            return {"hostStage": "prediction_committed"}

        def finalize_output(self, result_path: Path, result_sha256: str) -> Path:
            calls.append(("finalize", result_path, result_sha256))
            return comparison

    stages = HostStages()
    monkeypatch.setattr(
        controller, "load_output_session", lambda _path, _sha256: stages
    )

    def forbidden_issuer(*_args: object, **_kwargs: object) -> Path:
        raise AssertionError("stage preparation must never issue human authority")

    monkeypatch.setattr(controller, "issue_operator_approval", forbidden_issuer)

    assert (
        main(
            [
                "output-next",
                "--session",
                str(session),
                "--session-sha256",
                "a" * 64,
                "--approval",
                str(approval),
            ]
        )
        == 0
    )
    next_output = capsys.readouterr().out
    assert str(request.absolute()) in next_output
    assert str(handoff.absolute()) in next_output
    assert f"sha256:{sha256(request)}" in next_output
    assert f"sha256:{sha256(handoff)}" in next_output
    assert (
        main(
            [
                "output-recover",
                "--session",
                str(session),
                "--session-sha256",
                "a" * 64,
            ]
        )
        == 0
    )
    recovery_output = json.loads(capsys.readouterr().out)
    assert recovery_output["reportType"] == "inventory_only_not_qualified_receipts"
    assert recovery_output["status"] == "empty"
    assert (
        main(
            [
                "output-ingest",
                "--session",
                str(session),
                "--session-sha256",
                "a" * 64,
                "--result",
                str(result),
                "--result-sha256",
                "b" * 64,
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "output-finalize",
                "--session",
                str(session),
                "--session-sha256",
                "a" * 64,
                "--result",
                str(result),
                "--result-sha256",
                "b" * 64,
            ]
        )
        == 0
    )
    assert calls == [
        ("next", approval.absolute()),
        ("recover",),
        ("ingest", result.absolute(), "b" * 64),
        ("finalize", result.absolute(), "b" * 64),
    ]

    with pytest.raises(SystemExit):
        main(
            [
                "output-next",
                "--session",
                str(session),
                "--session-sha256",
                "a" * 64,
                "--approval",
                str(approval),
                "--action",
                "construct",
            ]
        )


def test_output_replan_cli_uses_exact_session_without_issuing_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from vera_timeline_agent import qualification_output_controller_v2 as controller
    from vera_timeline_agent.workflow_v2_cli import main

    session = tmp_path / "session.json"
    plan = tmp_path / "replan.json"
    session.write_bytes(b"retained session")
    calls: list[tuple[object, ...]] = []

    class HostStages:
        def prepare_operator_replan(self, output: Path) -> Path:
            calls.append(("replan", output))
            output.write_bytes(b"review-only proposal")
            return output

    stages = HostStages()
    monkeypatch.setattr(
        controller, "load_output_session", lambda _path, _sha256: stages
    )
    assert (
        main(
            [
                "output-replan",
                "--session",
                str(session),
                "--session-sha256",
                "a" * 64,
                "--output",
                str(plan),
            ]
        )
        == 0
    )
    assert calls == [("replan", plan.absolute())]
    assert str(plan.absolute()) in capsys.readouterr().out
