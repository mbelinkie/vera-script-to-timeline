"""One-command product entry: offline compile, source identity and refusal guards."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from issue177_package_fixture import make_package_case
from vera_timeline_agent import build_timeline_cli, build_timeline_once, studio_spike
from vera_timeline_agent.build_compiler_bridge import BridgeOutput
from vera_timeline_agent.build_jobs import BuildJobError, NeedsAction, UncertainResult
from vera_timeline_agent.build_stage_receipt import hash_file
from vera_timeline_agent.build_timeline_once import (
    BuildOptions,
    CompileResult,
    DeliveryResult,
    PreparedInputs,
    StageTimings,
    compile_prepared,
    deliver_compiled,
    exclusive_resolve_build,
    select_prepared_inputs,
)
from vera_timeline_agent.workflow_v2 import load_verified_package_v2
from vera_timeline_agent.workflow_v2_cli import attest_package_v2

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
    result = compile_prepared(options, bridge=_fake_bridge(calls=calls))
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
        compile_prepared(options, bridge=_fake_bridge())
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
        compile_prepared(options, bridge=_fake_bridge())


def test_malformed_prepared_media_identity_has_clear_refusal(tmp_path: Path) -> None:
    options = _inputs(tmp_path / "inputs")
    deps = options.inputs / "compiler-dependencies.json"  # type: ignore[operator]
    value = json.loads(deps.read_bytes())
    value["preparedMedia"][0]["requirementKey"] = ["not-a-key"]
    deps.write_text(json.dumps(value))
    with pytest.raises(BuildJobError, match="invalid prepared media binding"):
        compile_prepared(options, bridge=_fake_bridge())


def test_saved_media_plan_cannot_drift_from_compiler(tmp_path: Path) -> None:
    options = _inputs(tmp_path / "inputs")
    (options.inputs / "media-needs.json").write_text(  # type: ignore[operator]
        json.dumps({"ok": True, "requirements": []})
    )
    with pytest.raises(BuildJobError, match="saved media-needs"):
        compile_prepared(options, bridge=_fake_bridge())


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
        compile_prepared(options, bridge=changed)
    assert [name for name, _, _ in calls] == ["needs", "needs"]


def test_compiler_input_hash_mismatch_never_publishes_results(tmp_path: Path) -> None:
    options = _inputs(tmp_path / "inputs")
    with pytest.raises(BuildJobError, match="inputs changed"):
        compile_prepared(options, bridge=_fake_bridge(bad_hash=True))
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


def test_cli_reports_delivery_failure_as_non_success(
    tmp_path: Path, capsys: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    options = _inputs(tmp_path / "inputs")

    def fail(_options: BuildOptions, *, timings: StageTimings) -> None:
        with timings.span("Resolve step + check"):
            timings.run("build", lambda: (_ for _ in ()).throw(NeedsAction("offline")))

    monkeypatch.setattr(build_timeline_cli, "build_once", fail)
    exit_code = build_timeline_cli.main(
        ["--script", str(options.script), "--output", str(options.output)]
    )
    assert exit_code != 0
    output = capsys.readouterr()
    assert "Build refused: offline" in output.err
    assert "build: FAIL" in output.out
    assert "Resolve step + check: FAIL" in output.out
    assert "FAIL: timeline was not delivered" in output.out


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


def test_timing_span_records_elapsed_on_success_and_failure() -> None:
    now = [0.0]
    lines: list[str] = []
    reporter = StageTimings(clock=lambda: now[0], emit=lines.append)
    now[0] = 3.0
    with reporter.span("Resolve step + check"):
        now[0] = 15.5
    assert lines == ["Resolve step + check: PASS (12.50s)"]
    assert reporter.stages == [("Resolve step + check", 12.5)]

    with (
        pytest.raises(UncertainResult, match="unknown native write"),
        reporter.span("Resolve step + check"),
    ):
        now[0] = 18.0
        raise UncertainResult("unknown native write")
    assert lines[-1] == "Resolve step + check: FAIL (2.50s)"

    with pytest.raises(KeyboardInterrupt), reporter.span("Resolve step + check"):
        now[0] = 20.0
        raise KeyboardInterrupt
    assert lines[-1] == "Resolve step + check: FAIL (2.00s)"


def _package_inputs(tmp_path: Path) -> CompileResult:
    case = make_package_case(tmp_path / "fixture", rate="25fps")
    companions = tmp_path / "companions"
    companions.mkdir()
    preparation_file = companions / "preparation-paths.json"
    media_file = companions / "media-paths.json"
    preparation_file.write_text(
        json.dumps({key: str(path) for key, path in case.preparation_paths.items()})
    )
    media_file.write_text(
        json.dumps({key: str(path) for key, path in case.media_paths.items()})
    )
    output = tmp_path / "compiled"
    output.mkdir()
    return CompileResult(
        inputs=PreparedInputs(
            script=case.document_path,
            dependencies=case.dependencies_path,
            needs_input=None,
            recorded_needs=None,
            preparation_paths=preparation_file,
            media_paths=media_file,
        ),
        output=output,
        manifest=case.manifest_path,
        report=case.report_path,
        needs={},
    )


def test_real_package_and_attestation_precede_external_preflight_and_native_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compiled = _package_inputs(tmp_path)
    resolve = object()
    calls: list[str] = []
    created: dict[str, tuple[str, ...]] = {}
    monkeypatch.setattr(build_timeline_once, "_external_resolve", lambda: resolve)

    def fake_workflow(
        connected: Any, attestation: Path, digest: str, **kwargs: Any
    ) -> dict[str, Any]:
        assert connected is resolve
        checked = load_verified_package_v2(attestation, digest)
        name = checked.attestation["projectName"]
        assert kwargs["external_scripting"] == "Local"
        if kwargs.get("action") != "build":
            calls.append("preflight")
            assert name not in created
            return {"status": "preflight_passed"}
        calls.append("build")
        assert kwargs["authorize_new_nonproduction"] is True
        assert name not in created
        before = dict(created)
        created[name] = (name,)
        assert all(created[key] == value for key, value in before.items())
        for stage in ("build", "save/reopen", "verify"):
            kwargs["stage_observer"](stage, 0.1, True)
        return {
            "status": "verified",
            "verified": True,
            "discrepancies": [],
            "partialTargetRetained": False,
        }

    monkeypatch.setattr(build_timeline_once, "run_workflow_delivery_v2", fake_workflow)
    reporter = StageTimings(emit=lambda line: calls.append(line.split(":")[0]))
    first = deliver_compiled(compiled, timings=reporter)
    assert first.project_name == first.timeline_name
    assert calls == [
        "package",
        "attest",
        "connect",
        "preflight",
        "preflight",
        "build",
        "build",
        "save/reopen",
        "verify",
        "Resolve step + check",
    ]
    first_snapshot = dict(created)
    compiled2 = CompileResult(
        compiled.inputs,
        tmp_path / "compiled-second",
        compiled.manifest,
        compiled.report,
        compiled.needs,
    )
    result2 = deliver_compiled(compiled2, timings=StageTimings(emit=lambda _: None))
    assert first.project_name != result2.project_name
    assert {key: created[key] for key in first_snapshot} == first_snapshot


def test_resolve_step_plus_check_includes_preflight_and_readback_not_packaging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compiled = _package_inputs(tmp_path)
    now = [0.0]
    lines: list[str] = []
    original_attest = attest_package_v2

    def slow_attest(*args: Any, **kwargs: Any) -> Any:
        now[0] += 20.0  # Upstream package work is not part of the Resolve speed bar.
        return original_attest(*args, **kwargs)

    def connect() -> object:
        now[0] += 2.0
        return object()

    def fake_workflow(
        _resolve: Any, _attestation: Path, _digest: str, **kwargs: Any
    ) -> dict[str, Any]:
        if kwargs.get("action") != "build":
            now[0] += 3.0  # Separate read-only preflight also takes time.
            return {"status": "preflight_passed"}
        for label, elapsed in (("build", 4.0), ("save/reopen", 5.0), ("verify", 1.0)):
            now[0] += elapsed
            kwargs["stage_observer"](label, elapsed, True)
        return {
            "status": "verified",
            "verified": True,
            "discrepancies": [],
            "partialTargetRetained": False,
        }

    monkeypatch.setattr(build_timeline_once, "attest_package_v2", slow_attest)
    monkeypatch.setattr(build_timeline_once, "_external_resolve", connect)
    monkeypatch.setattr(build_timeline_once, "run_workflow_delivery_v2", fake_workflow)
    reporter = StageTimings(clock=lambda: now[0], emit=lines.append)
    result = deliver_compiled(compiled, timings=reporter)
    reporter.finish(
        frames=result.frames,
        numerator=result.numerator,
        denominator=result.denominator,
        passed=True,
    )
    assert "attest: PASS (20.00s)" in lines
    assert "Resolve step + check: PASS (15.00s)" in lines
    assert lines.index("Resolve step + check: PASS (15.00s)") > next(
        i for i, line in enumerate(lines) if line.startswith("verify: PASS")
    )
    assert lines[-1].endswith("total 35.00s")


@pytest.mark.parametrize(
    ("failure_at", "exception", "expected_seconds"),
    [("preflight", NeedsAction, 5.0), ("native", UncertainResult, 14.0)],
)
def test_resolve_step_plus_check_fails_on_refusal_or_uncertain_native_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_at: str,
    exception: type[Exception],
    expected_seconds: float,
) -> None:
    compiled = _package_inputs(tmp_path)
    now = [0.0]
    lines: list[str] = []

    def connect() -> object:
        now[0] += 2.0
        return object()

    def fake_workflow(
        _resolve: Any, _attestation: Path, _digest: str, **kwargs: Any
    ) -> dict[str, Any]:
        if kwargs.get("action") != "build":
            now[0] += 3.0
            if failure_at == "preflight":
                return {"status": "stopped_safely", "refusal": "wrong project"}
            return {"status": "preflight_passed"}
        now[0] += 9.0
        kwargs["stage_observer"]("build", 9.0, False)
        return {"status": "mutation_failed", "partialTargetRetained": True}

    monkeypatch.setattr(build_timeline_once, "_external_resolve", connect)
    monkeypatch.setattr(build_timeline_once, "run_workflow_delivery_v2", fake_workflow)
    reporter = StageTimings(clock=lambda: now[0], emit=lines.append)
    with pytest.raises(exception):
        deliver_compiled(compiled, timings=reporter)
    reporter.fail()
    assert f"Resolve step + check: FAIL ({expected_seconds:.2f}s)" in lines
    assert lines[-1].startswith("FAIL: timeline was not delivered")


def test_named_existing_project_is_used_only_by_explicit_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compiled = _package_inputs(tmp_path)
    monkeypatch.setattr(build_timeline_once, "_external_resolve", object)
    calls: list[tuple[str, str | None]] = []

    def fake_workflow(
        _resolve: Any, _attestation: Path, _digest: str, **kwargs: Any
    ) -> dict[str, Any]:
        calls.append(
            (kwargs.get("action", "preflight"), kwargs.get("existing_project"))
        )
        if kwargs.get("action") != "build":
            return {"status": "preflight_passed"}
        for stage in ("build", "save/reopen", "verify"):
            kwargs["stage_observer"](stage, 0.01, True)
        return {
            "status": "verified",
            "verified": True,
            "discrepancies": [],
            "partialTargetRetained": False,
        }

    monkeypatch.setattr(build_timeline_once, "run_workflow_delivery_v2", fake_workflow)
    result = deliver_compiled(
        compiled,
        timings=StageTimings(emit=lambda _: None),
        existing_project="Review Project",
    )
    assert result.project_name == "Review Project"
    assert result.timeline_name != result.project_name
    assert calls == [("preflight", "Review Project"), ("build", "Review Project")]


def test_cli_existing_project_output_and_bad_name(
    tmp_path: Path, capsys: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    options = _inputs(tmp_path / "inputs")
    observed: list[BuildOptions] = []

    def fake_build(submitted: BuildOptions, *, timings: StageTimings) -> DeliveryResult:
        observed.append(submitted)
        return DeliveryResult("Review Project", "VERA New", 250, 25, 1)

    monkeypatch.setattr(build_timeline_cli, "build_once", fake_build)
    arguments = ["--script", str(options.script), "--output", str(options.output)]
    assert (
        build_timeline_cli.main([*arguments, "--existing-project", "Review Project"])
        == 0
    )
    output = capsys.readouterr()
    assert "New timeline in named Studio project" in output.out
    assert "PASS: 250 frames" in output.out
    assert observed[0].existing_project == "Review Project"
    assert (
        build_timeline_cli.main([*arguments, "--existing-project", " Review Project "])
        == 2
    )
    assert len(observed) == 1
    assert "invalid existing project name" in capsys.readouterr().err


def test_issue88_cli_prints_exact_named_cut_without_claiming_a_dissolve(
    tmp_path: Path, capsys: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    options = _inputs(tmp_path / "inputs")

    def fake_build(
        _submitted: BuildOptions, *, timings: StageTimings
    ) -> DeliveryResult:
        return DeliveryResult(
            "New Studio",
            "Rough Cut",
            192,
            24,
            1,
            ("Transition pair-88 (row-A -> row-B) at frame 96: short handles",),
        )

    monkeypatch.setattr(build_timeline_cli, "build_once", fake_build)
    assert (
        build_timeline_cli.main(
            ["--script", str(options.script), "--output", str(options.output)]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "cut_insufficient_handles" in output
    assert "row-A -> row-B" in output and "frame 96" in output
    assert "verified" in output


def test_absent_resolve_refuses_after_packaging_without_any_native_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compiled = _package_inputs(tmp_path)
    monkeypatch.setattr(
        build_timeline_once,
        "_external_resolve",
        lambda: (_ for _ in ()).throw(
            NeedsAction(
                "DaVinci Resolve Studio is not running or external scripting "
                "is unavailable"
            )
        ),
    )
    monkeypatch.setattr(
        build_timeline_once,
        "run_workflow_delivery_v2",
        lambda *_args, **_kwargs: pytest.fail("closed Resolve must not reach workflow"),
    )
    with pytest.raises(NeedsAction, match="not running"):
        deliver_compiled(compiled, timings=StageTimings(emit=lambda _: None))


def test_exclusive_native_lock_rejects_contention_and_releases(tmp_path: Path) -> None:
    lock_path = tmp_path / "resolve.lock"
    with (
        exclusive_resolve_build(lock_path),
        pytest.raises(NeedsAction, match="already building"),
        exclusive_resolve_build(lock_path),
    ):
        pytest.fail("contending call acquired native lock")
    with exclusive_resolve_build(lock_path):
        pass


def test_native_partial_write_uncertainty_never_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compiled = _package_inputs(tmp_path)
    monkeypatch.setattr(build_timeline_once, "_external_resolve", object)
    calls: list[str] = []

    def fake_workflow(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "preflight")
        calls.append(action)
        if action == "build":
            kwargs["stage_observer"]("build", 0.1, False)
            return {"status": "mutation_failed", "partialTargetRetained": True}
        return {"status": "preflight_passed"}

    monkeypatch.setattr(build_timeline_once, "run_workflow_delivery_v2", fake_workflow)
    with pytest.raises(UncertainResult, match="partial disposable project retained"):
        deliver_compiled(compiled, timings=StageTimings(emit=lambda _: None))
    assert calls == ["preflight", "build"]


def test_external_adapter_uses_raw_sdk_resolve_and_closed_app_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk_resolve = object()
    facts = SimpleNamespace(app_installed=True, scripting_module_installed=True)
    monkeypatch.setattr(studio_spike, "detect_local_capabilities", lambda: facts)
    monkeypatch.setattr(
        studio_spike,
        "load_resolve_adapter",
        lambda observed: (
            SimpleNamespace(resolve=sdk_resolve) if observed is facts else None
        ),
    )
    assert build_timeline_once._external_resolve() is sdk_resolve
    monkeypatch.setattr(
        studio_spike,
        "load_resolve_adapter",
        lambda _facts: (_ for _ in ()).throw(RuntimeError("closed SDK")),
    )
    with pytest.raises(NeedsAction, match="DaVinci Resolve Studio is not running"):
        build_timeline_once._external_resolve()


def test_only_real_audio_and_fractional_refusals_get_specific_messages() -> None:
    refused = {
        "status": "stopped_safely",
        "failureStage": "package validation",
        "sourceAudioPresent": True,
        "sourceAudioNativeQualified": False,
        "nativeRateQualified": True,
    }
    with pytest.raises(NeedsAction, match="source-audio"):
        build_timeline_once._require_workflow_status(refused, "verified")
    refused["sourceAudioPresent"] = False
    with pytest.raises(BuildJobError, match="package validation refused"):
        build_timeline_once._require_workflow_status(refused, "verified")
    refused["nativeRateQualified"] = False
    with pytest.raises(NeedsAction, match="fractional"):
        build_timeline_once._require_workflow_status(refused, "verified")
    with pytest.raises(NeedsAction, match="project rate or settings"):
        build_timeline_once._require_workflow_status(
            {
                "status": "stopped_safely",
                "refusal": "existing project rate or settings differ from script",
            },
            "preflight_passed",
        )
    with pytest.raises(UncertainResult, match="named existing project retained"):
        build_timeline_once._require_workflow_status(
            {"status": "mutation_failed", "partialTargetRetained": True},
            "verified",
            existing_project=True,
        )


def test_native_verified_status_without_independent_verification_is_uncertain() -> None:
    with pytest.raises(UncertainResult, match="verification is incomplete"):
        build_timeline_once._require_workflow_status(
            {
                "status": "verified",
                "verified": False,
                "discrepancies": [],
                "partialTargetRetained": False,
            },
            "verified",
        )
