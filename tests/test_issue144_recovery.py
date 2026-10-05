from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_issue144_proof_session import _visual_inputs
from vera_timeline_agent.roundtrip_driver import main
from vera_timeline_agent.roundtrip_wi import file_hash

WORLDS: dict[str, Any] = {}


def boundary_file(directory: Path, mode: str = "normal") -> Path:
    source = directory / "boundary.py"
    source.write_text(
        "from test_issue144_proof_session import Boundary\n"
        "from test_issue144_recovery import WORLDS\n"
        "from vera_timeline_agent.build_jobs import NeedsAction\n"
        "FILE_PINS = {}\n"
        "def make_boundary(root):\n"
        "    boundary = WORLDS.setdefault(str(root), Boundary())\n"
        "    def native(build):\n"
        "        stages = boundary.native(build)\n"
        "        factory, execute = stages.adapter_factory, stages.execute\n"
        "        def counted(manifest):\n"
        "            with (root / 'factory-calls.txt').open('a') as log:\n"
        "                log.write('called\\n')\n"
        "            studio = factory(manifest)\n"
        f"            studio.lost_response = {mode == 'lost_response'!r}\n"
        "            return studio\n"
        "        def interrupted(context):\n"
        "            execute(context)\n"
        f"            if ({mode == 'verified_wait'!r}\n"
        "                and context.stage == 'building_resolve_timeline'\n"
        "                and not (root / 'interrupted.txt').exists()):\n"
        "                (root / 'interrupted.txt').write_text('interrupted')\n"
        "                raise NeedsAction('synthetic wait after verified receipt')\n"
        "        stages.adapter_factory = counted\n"
        "        stages.execute = interrupted\n"
        "        return stages\n"
        "    return {'native_provider': native, 'capture': boundary.capture}\n"
    )
    return source


def invoke(
    root: Path,
    action: str,
    capsys: pytest.CaptureFixture[str],
    source: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    args = [action, "--proof-root", str(root)]
    if source is not None:
        args += ["--boundary-file", str(source), "--boundary-sha256", file_hash(source)]
    result = main(args)
    return result, json.loads(capsys.readouterr().out)


def test_preflight_validates_without_job_or_boundary_effect(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proof"
    _visual_inputs(root)
    source = boundary_file(tmp_path)
    code, result = invoke(root, "preflight", capsys)
    assert code == 0 and result["status"] == "prepared"
    assert result["evidenceLevel"] == "local_prepared"
    assert not (root / "jobs").exists()
    assert not (root / "operator-boundary.json").exists()
    assert not (root / "factory-calls.txt").exists()
    assert not (root / "baseline.json").exists()
    code, result = invoke(root, "build", capsys, source)
    assert code == 0 and result["status"] == "complete"
    assert (root / "factory-calls.txt").read_text().splitlines() == ["called"]


def test_explicit_resume_build_after_missing_boundary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proof"
    _visual_inputs(root)
    source = boundary_file(tmp_path)
    original = (root / "script-document.json").read_bytes()
    code, result = invoke(root, "build", capsys)
    assert code == 2 and result["status"] == "waiting"
    code, result = invoke(root, "build", capsys, source)
    assert code == 2 and result["status"] == "waiting"
    assert not (root / "factory-calls.txt").exists()
    code, result = invoke(root, "resume-build", capsys, source)
    assert code == 0 and result["status"] == "complete"
    assert (root / "script-document.json").read_bytes() == original
    assert (root / "factory-calls.txt").read_text().splitlines() == ["called"]
    assert not (root / "baseline.json").exists()


@pytest.mark.parametrize(
    "damage", ["empty_intent", "foreign_intent", "stopped", "integrity"]
)
def test_recovery_never_recreates_damaged_or_unverified_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], damage: str
) -> None:
    root = tmp_path / "proof"
    _visual_inputs(root)
    source = boundary_file(tmp_path, "verified_wait")
    code, result = invoke(root, "build", capsys, source)
    assert code == 2 and result["status"] == "waiting"
    run = next((root / "runs").iterdir())
    if damage == "empty_intent":
        (run / "native-intent.json").write_bytes(b"")
    elif damage == "foreign_intent":
        (run / "native-intent.json").write_text('{"foreign":true}')
    elif damage == "stopped":
        path = run / "native-result.json"
        receipt = json.loads(path.read_bytes())
        receipt.update(status="stopped_safely", verified=False)
        path.write_text(json.dumps(receipt))
    else:
        stage = next(s for s in result["stages"] if s["name"] == "compiling")
        Path(stage["path"]).write_text("changed")
    before = {str(p): p.read_bytes() for p in run.rglob("*") if p.is_file()}
    code, result = invoke(root, "resume-build", capsys, source)
    assert code == 2 and result["status"] == "recovery_blocked"
    assert {str(p): p.read_bytes() for p in run.rglob("*") if p.is_file()} == before
    assert (root / "factory-calls.txt").read_text().splitlines() == ["called"]
    assert not (root / "baseline.json").exists()


@pytest.mark.parametrize("mode", ["verified_wait", "lost_response"])
def test_explicit_resume_reconciles_verified_result_and_blocks_uncertain_creation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mode: str
) -> None:
    root = tmp_path / "proof"
    _visual_inputs(root)
    source = boundary_file(tmp_path, mode)
    code, result = invoke(root, "build", capsys, source)
    assert code == 2 and result["status"] == (
        "waiting" if mode == "verified_wait" else "recovery_blocked"
    )
    code, result = invoke(root, "resume-build", capsys, source)
    if mode == "verified_wait":
        assert code == 0 and result["status"] == "complete"
    else:
        assert code == 2 and result["status"] == "recovery_blocked"
        assert result["evidenceLevel"] == "synthetic_injected"
    assert (root / "factory-calls.txt").read_text().splitlines() == ["called"]
    assert not (root / "baseline.json").exists()
