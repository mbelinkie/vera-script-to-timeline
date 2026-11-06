"""Compiler v2 bridge consumes prepared media and preserves golden behavior."""

import json
from pathlib import Path

import pytest
from vera_timeline_agent.build_compiler_bridge import invoke_bridge
from vera_timeline_agent.build_jobs import BuildJobError

ROOT = Path(__file__).parent / "data/authoring_v2/issue_173/compiler"


@pytest.mark.parametrize(
    "name",
    ["selected-clip-ntsc", "narrated-image-still-holds", "reuse-nonzero-inpoint"],
)
def test_actual_v2_compile_bridge_produces_ready_manifest_and_report(
    tmp_path: Path, name: str
) -> None:
    fixture = json.loads((ROOT / f"{name}.input.golden.json").read_bytes())
    document, dependencies = tmp_path / "document.json", tmp_path / "dependencies.json"
    document.write_text(json.dumps(fixture["document"]))
    dependencies.write_text(json.dumps(fixture["dependencies"]))
    compile = invoke_bridge("compile", document, dependencies)
    requirements = invoke_bridge("needs", document, dependencies)
    assert compile.needs == requirements.needs
    assert compile.result["report"]["status"] == "ready"
    assert json.loads(compile.result["manifestJson"]) == compile.result["manifest"]
    assert json.loads(compile.result["reportJson"]) == compile.result["report"]
    assert len(compile.needs["requirements"]) >= 1


def test_blocked_compiler_never_becomes_a_usable_package(tmp_path: Path) -> None:
    fixture = json.loads((ROOT / "selected-clip-ntsc.input.golden.json").read_bytes())
    fixture["dependencies"]["preparedMedia"] = []
    doc, deps = tmp_path / "doc.json", tmp_path / "deps.json"
    doc.write_text(json.dumps(fixture["document"]))
    deps.write_text(json.dumps(fixture["dependencies"]))
    with pytest.raises(
        BuildJobError, match=r"compiler report is not ready|v2 compile refused"
    ):
        invoke_bridge("compile", doc, deps)
    assert invoke_bridge("needs", doc, deps).needs["ok"] is True
