"""One-command product entry: offline compile, source identity and refusal guards."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import build_timeline_cli
from vera_timeline_agent.build_compiler_bridge import BridgeOutput
from vera_timeline_agent.build_jobs import BuildJobError, NeedsAction
from vera_timeline_agent.build_stage_receipt import hash_file
from vera_timeline_agent.build_timeline_once import (
    BuildOptions,
    StageTimings,
    compile_prepared,
    select_prepared_inputs,
)

FIXTURES = Path(__file__).parent / "data/authoring_v2/issue_173/compiler"


def _inputs(root: Path, name: str = "selected-clip-ntsc") -> BuildOptions:
    fixture = json.loads((FIXTURES / f"{name}.input.golden.json").read_bytes())
    root.mkdir(parents=True)
    (root / "script-document.json").write_text(json.dumps(fixture["document"]))
    (root / "compiler-dependencies.json").write_text(
        json.dumps(fixture["dependencies"])
    )
    return BuildOptions(
        script=root / "script-document.json",
        inputs=root,
        output=root.parent / "compiled",
    )


def _fake_bridge(
    *,
    needs: dict[str, Any] | None = None,
    calls: list[tuple[str, Path, Path]] | None = None,
    bad_hash: bool = False,
) -> Callable[[str, Path, Path], BridgeOutput]:
    requirements = needs or {
        "ok": True,
        "requirements": [
            {"requirementKey": "prep:occurrence-1", "sourceSufficiency": "sufficient"}
        ],
    }

    def bridge(kind: str, document: Path, dependencies: Path) -> BridgeOutput:
        if calls is not None:
            calls.append((kind, document, dependencies))
        manifest = {"schemaVersion": "timeline-manifest/v2", "events": []}
        report = {"status": "ready"}
        return BridgeOutput(
            kind,
            "0" * 64 if bad_hash else hash_file(document),
            hash_file(dependencies),
            {
                "needs": requirements,
                "result": {
                    "ok": True,
                    "manifest": manifest,
                    "report": report,
                    "manifestJson": json.dumps(manifest, sort_keys=True),
                    "reportJson": json.dumps(report, sort_keys=True),
                },
            },
        )

    return bridge


def test_compiles_prepared_input_offline_without_provider_or_resolve(
    tmp_path: Path,
) -> None:
    options = _inputs(tmp_path / "inputs")
    calls: list[tuple[str, Path, Path]] = []
    result = compile_prepared(options, bridge=_fake_bridge(calls=calls))  # type: ignore[arg-type]
    assert [name for name, _, _ in calls] == ["needs", "compile"]
    assert all(path == result.inputs.dependencies for _, _, path in calls)
    assert json.loads(result.manifest.read_bytes())["events"] == []
    assert json.loads(result.report.read_bytes()) == {"status": "ready"}
    assert result.output.is_dir()


@pytest.mark.parametrize("name", ["selected-clip-ntsc", "narrated-image-still-holds"])
def test_actual_pinned_compiler_fixture_preserves_golden_manifest_and_report(
    tmp_path: Path, name: str
) -> None:
    options = _inputs(tmp_path / "inputs", name)
    result = compile_prepared(options)
    assert json.loads(result.manifest.read_bytes()) == json.loads(
        (FIXTURES / f"{name}.manifest.golden.json").read_bytes()
    )
    assert json.loads(result.report.read_bytes()) == json.loads(
        (FIXTURES / f"{name}.report.golden.json").read_bytes()
    )


def test_absent_prepared_companion_refuses_before_output(tmp_path: Path) -> None:
    options = _inputs(tmp_path / "inputs")
    options.inputs.joinpath("compiler-dependencies.json").unlink()  # type: ignore[union-attr]
    with pytest.raises(NeedsAction, match="prepared compiler-dependencies"):
        compile_prepared(options, bridge=_fake_bridge())  # type: ignore[arg-type]
    assert not options.output.exists()


def test_malformed_or_unprepared_companion_refuses(tmp_path: Path) -> None:
    options = _inputs(tmp_path / "inputs")
    deps = options.inputs / "compiler-dependencies.json"  # type: ignore[operator]
    deps.write_text(
        '{"schemaVersion":"compiler-dependencies/v2","preparedMedia":[],"preparedMedia":[]}'
    )
    with pytest.raises(BuildJobError, match="duplicate key"):
        select_prepared_inputs(options)
    assert not options.output.exists()
    fixture = json.loads(
        (FIXTURES / "selected-clip-ntsc.input.golden.json").read_bytes()
    )
    fixture["dependencies"]["preparedMedia"] = []
    deps.write_text(json.dumps(fixture["dependencies"]))
    with pytest.raises(NeedsAction, match="prepared media does not match"):
        compile_prepared(options, bridge=_fake_bridge())  # type: ignore[arg-type]


def test_malformed_prepared_media_identity_has_clear_refusal(tmp_path: Path) -> None:
    options = _inputs(tmp_path / "inputs")
    deps = options.inputs / "compiler-dependencies.json"  # type: ignore[operator]
    value = json.loads(deps.read_bytes())
    value["preparedMedia"][0]["requirementKey"] = ["not-a-key"]
    deps.write_text(json.dumps(value))
    with pytest.raises(BuildJobError, match="invalid prepared media binding"):
        compile_prepared(options, bridge=_fake_bridge())  # type: ignore[arg-type]


def test_saved_media_plan_cannot_drift_from_compiler(tmp_path: Path) -> None:
    options = _inputs(tmp_path / "inputs")
    (options.inputs / "media-needs.json").write_text(  # type: ignore[operator]
        json.dumps({"ok": True, "requirements": []})
    )
    with pytest.raises(BuildJobError, match="saved media-needs"):
        compile_prepared(options, bridge=_fake_bridge())  # type: ignore[arg-type]


def test_preparation_needs_input_cannot_change_temporal_plan(tmp_path: Path) -> None:
    options = _inputs(tmp_path / "inputs")
    (options.inputs / "media-needs.dependencies.json").write_text(  # type: ignore[operator]
        (options.inputs / "compiler-dependencies.json").read_text()  # type: ignore[operator]
    )
    calls: list[tuple[str, Path, Path]] = []
    original = _fake_bridge(calls=calls)

    def changed(kind: str, doc: Path, deps: Path) -> BridgeOutput:
        value = original(kind, doc, deps)
        if deps.name == "media-needs.dependencies.json":
            value.data["needs"] = {"ok": True, "requirements": []}
        return value

    with pytest.raises(BuildJobError, match="temporal plan"):
        compile_prepared(options, bridge=changed)  # type: ignore[arg-type]
    assert [name for name, _, _ in calls] == ["needs", "needs"]


def test_compiler_input_hash_mismatch_never_publishes_results(tmp_path: Path) -> None:
    options = _inputs(tmp_path / "inputs")
    with pytest.raises(BuildJobError, match="inputs changed"):
        compile_prepared(options, bridge=_fake_bridge(bad_hash=True))  # type: ignore[arg-type]
    assert not (options.output / "timeline-manifest.json").exists()


def test_output_collision_is_refused_without_invoking_compiler(tmp_path: Path) -> None:
    options = _inputs(tmp_path / "inputs")
    options.output.mkdir()
    sentinel = options.output / "leave-untouched"
    sentinel.write_text("saved")

    def forbidden(*_: Any) -> BridgeOutput:
        pytest.fail("no compiler call is permitted on output collision")

    with pytest.raises(BuildJobError, match="output already exists"):
        compile_prepared(options, bridge=forbidden)
    assert sentinel.read_text() == "saved"


def test_symlink_and_ambiguous_companion_refused(tmp_path: Path) -> None:
    options = _inputs(tmp_path / "inputs")
    nested = options.inputs / "resolving_media"  # type: ignore[operator]
    nested.mkdir()
    (nested / "compiler-dependencies.json").write_text(
        (options.inputs / "compiler-dependencies.json").read_text()  # type: ignore[operator]
    )
    with pytest.raises(BuildJobError, match="ambiguous"):
        select_prepared_inputs(options)
    (nested / "compiler-dependencies.json").unlink()
    (nested / "compiler-dependencies.json").symlink_to(
        options.inputs / "compiler-dependencies.json"  # type: ignore[operator]
    )
    with pytest.raises(BuildJobError, match="ambiguous"):
        select_prepared_inputs(options)


def test_cli_reports_compilation_only_as_non_success(
    tmp_path: Path, capsys: Any
) -> None:
    options = _inputs(tmp_path / "inputs")
    original = build_timeline_cli.compile_prepared

    def fake(options: BuildOptions) -> None:
        original(options, bridge=_fake_bridge())  # type: ignore[arg-type]

    build_timeline_cli.compile_prepared = fake  # type: ignore[assignment]
    try:
        exit_code = build_timeline_cli.main(
            ["--script", str(options.script), "--output", str(options.output)]
        )
    finally:
        build_timeline_cli.compile_prepared = original
    assert exit_code != 0
    assert "Resolve delivery is not yet connected" in capsys.readouterr().err
    assert (options.output / "timeline-manifest.json").is_file()


def test_timing_tracks_fractional_duration_and_failed_stage() -> None:
    times = iter([0.0, 2.0, 2.25, 3.0])
    lines: list[str] = []
    timing = StageTimings(clock=lambda: next(times), emit=lines.append)
    assert timing.run("compile", lambda: 11) == 11
    assert timing.finish(
        frames=1107, numerator=24000, denominator=1001, passed=True
    ) == ("PASS: 1107 frames (46.171s timeline); total 3.00s")
    assert lines[0] == "compile: PASS (0.25s)"
    times = iter([0.0, 1.0, 1.75])
    failures: list[str] = []
    reporter = StageTimings(clock=lambda: next(times), emit=failures.append)
    with pytest.raises(RuntimeError, match="uncertain"):
        reporter.run("build", lambda: (_ for _ in ()).throw(RuntimeError("uncertain")))
    assert failures == ["build: FAIL (0.75s)"]
