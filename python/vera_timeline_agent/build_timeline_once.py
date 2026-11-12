"""Foreground v2 compile inputs for the one-command Studio delivery path.

Compilation is intentionally independent of the native Resolve effect. The
subsequent phases consume these exact published manifest/report bytes.
"""

from __future__ import annotations

import json
import stat
from collections.abc import Callable
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, TypeVar

from .build_compiler_bridge import BridgeOutput, invoke_bridge
from .build_jobs import BuildJobError, NeedsAction, publish_immutable_output
from .build_stage_receipt import hash_file

T = TypeVar("T")
Bridge = Callable[[Literal["needs", "compile"], Path, Path], BridgeOutput]


@dataclass(frozen=True)
class BuildOptions:
    script: Path
    output: Path
    inputs: Path | None = None
    existing_project: str | None = None


@dataclass(frozen=True)
class PreparedInputs:
    script: Path
    dependencies: Path
    needs_input: Path | None
    recorded_needs: Path | None
    preparation_paths: Path | None


@dataclass(frozen=True)
class CompileResult:
    inputs: PreparedInputs
    output: Path
    manifest: Path
    report: Path
    needs: dict[str, Any]


@dataclass
class StageTimings:
    clock: Callable[[], float] = perf_counter
    emit: Callable[[str], None] = print
    stages: list[tuple[str, float]] = field(default_factory=list)
    started: float = field(init=False)

    def __post_init__(self) -> None:
        self.started = self.clock()

    def run(self, name: str, work: Callable[[], T]) -> T:
        before = self.clock()
        try:
            value = work()
        except Exception:
            elapsed = max(0.0, self.clock() - before)
            self.stages.append((name, elapsed))
            self.emit(f"{name}: FAIL ({elapsed:.2f}s)")
            raise
        elapsed = max(0.0, self.clock() - before)
        self.stages.append((name, elapsed))
        self.emit(f"{name}: PASS ({elapsed:.2f}s)")
        return value

    def finish(
        self, *, frames: int, numerator: int, denominator: int, passed: bool
    ) -> str:
        if frames < 0 or numerator <= 0 or denominator <= 0:
            raise ValueError("invalid timeline duration/frame rate")
        seconds = Fraction(frames * denominator, numerator)
        total = max(0.0, self.clock() - self.started)
        message = (
            f"{'PASS' if passed else 'FAIL'}: {frames} frames "
            f"({float(seconds):.3f}s timeline); total {total:.2f}s"
        )
        self.emit(message)
        return message


def _plain_path(path: Path, *, directory: bool = False) -> Path:
    """Refuse symlink traversal before a source or output is used."""
    absolute = path.absolute()
    if any(p.is_symlink() for p in (absolute, *absolute.parents)):
        raise BuildJobError("symbolic links are unsupported in build input paths")
    if directory:
        if not absolute.is_dir():
            raise BuildJobError("prepared inputs directory is unavailable")
    elif not absolute.is_file() or not stat.S_ISREG(absolute.stat().st_mode):
        raise BuildJobError("required prepared input is not a regular file")
    return absolute


def _read_json(path: Path) -> dict[str, Any]:
    regular = _plain_path(path)
    if regular.stat().st_size > 16 * 1024 * 1024:
        raise BuildJobError("prepared JSON exceeds 16 MiB")

    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise BuildJobError("duplicate key in prepared JSON")
            result[key] = value
        return result

    try:
        parsed = json.loads(
            regular.read_bytes(),
            object_pairs_hook=unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (UnicodeError, ValueError) as error:
        raise BuildJobError("invalid prepared JSON") from error
    if not isinstance(parsed, dict):
        raise BuildJobError("prepared JSON must be an object")
    return parsed


def _companion(root: Path, filename: str) -> Path | None:
    candidates = (root / filename, root / "resolving_media" / filename)
    found = [path for path in candidates if path.exists() or path.is_symlink()]
    if len(found) > 1:
        raise BuildJobError(f"ambiguous prepared input: {filename}")
    return _plain_path(found[0]) if found else None


def select_prepared_inputs(options: BuildOptions) -> PreparedInputs:
    script = _plain_path(options.script)
    root = _plain_path(options.inputs or script.parent, directory=True)
    dependencies = _companion(root, "compiler-dependencies.json")
    if dependencies is None:
        raise NeedsAction("prepared compiler-dependencies.json is required")
    if _read_json(script).get("schemaVersion") != "script-document/v2":
        raise BuildJobError("script must be a v2 script document")
    deps = _read_json(dependencies)
    if deps.get("schemaVersion") != "compiler-dependencies/v2":
        raise BuildJobError("v2 prepared compiler dependencies are required")
    if not isinstance(deps.get("preparedMedia"), list) or not isinstance(
        deps.get("narrationTimingMaps"), list
    ):
        raise NeedsAction(
            "ready prepared media and narration timing inputs are required"
        )
    preparation_paths = _companion(root, "preparation-paths.json")
    if preparation_paths is not None:
        paths = _read_json(preparation_paths)
        if any(
            not isinstance(key, str)
            or not key
            or not isinstance(locator, str)
            or not Path(locator).is_absolute()
            for key, locator in paths.items()
        ):
            raise BuildJobError("invalid prepared media receipt mapping")
    return PreparedInputs(
        script=script,
        dependencies=dependencies,
        needs_input=_companion(root, "media-needs.dependencies.json"),
        recorded_needs=_companion(root, "media-needs.json"),
        preparation_paths=preparation_paths,
    )


def allocate_output(options: BuildOptions, inputs: PreparedInputs) -> Path:
    output = options.output.absolute()
    if any(
        path.is_relative_to(output) for path in (inputs.script, inputs.dependencies)
    ):
        raise BuildJobError("output cannot contain the input document or dependencies")
    if any(part.is_symlink() for part in (output, *output.parents)):
        raise BuildJobError("symbolic links are unsupported in output paths")
    if output.exists():
        raise BuildJobError("output already exists; choose a fresh output directory")
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir(exist_ok=False)
    except FileExistsError as error:
        raise BuildJobError(
            "output already exists; choose a fresh output directory"
        ) from error
    return output


def _check_requirements(needs: dict[str, Any], inputs: PreparedInputs) -> None:
    requirements = needs.get("requirements")
    if not isinstance(requirements, list):
        raise BuildJobError("compiler returned invalid media requirements")
    required: set[str] = set()
    for row in requirements:
        if not isinstance(row, dict):
            raise BuildJobError("compiler returned invalid media requirement")
        if row.get("sourceSufficiency") not in (None, "sufficient"):
            raise NeedsAction("a selected source cannot satisfy the requested range")
        key = row.get("requirementKey")
        if key is not None:
            if not isinstance(key, str):
                raise BuildJobError("compiler returned invalid media requirement key")
            required.add(key)
    deps = _read_json(inputs.dependencies)
    bindings = deps["preparedMedia"]
    keys: list[str] = []
    for row in bindings:
        if not isinstance(row, dict) or not isinstance(row.get("requirementKey"), str):
            raise BuildJobError("invalid prepared media binding identity")
        keys.append(row["requirementKey"])
    if len(set(keys)) != len(keys):
        raise BuildJobError("duplicate prepared media binding identity")
    if set(keys) != required:
        raise NeedsAction(
            "prepared media does not match the script's media requirements"
        )
    if (
        inputs.preparation_paths is not None
        and set(_read_json(inputs.preparation_paths)) != required
    ):
        raise BuildJobError("prepared receipt mapping differs from media requirements")


def compile_prepared(
    options: BuildOptions,
    *,
    bridge: Bridge = invoke_bridge,
    timings: StageTimings | None = None,
) -> CompileResult:
    """Compile pinned inputs; never acquire media, spend money, or call Resolve."""
    inputs = select_prepared_inputs(options)
    output = allocate_output(options, inputs)
    reporter = timings or StageTimings()
    source_hash = hash_file(inputs.script)
    deps_hash = hash_file(inputs.dependencies)

    def check_needs() -> dict[str, Any]:
        result = bridge("needs", inputs.script, inputs.dependencies)
        needs = result.needs
        if inputs.needs_input is not None:
            original = bridge("needs", inputs.script, inputs.needs_input)
            if original.needs != needs:
                raise BuildJobError("preparation changed the media-needs temporal plan")
        if (
            inputs.recorded_needs is not None
            and _read_json(inputs.recorded_needs) != needs
        ):
            raise BuildJobError("saved media-needs do not match this script")
        _check_requirements(needs, inputs)
        return needs

    needs = reporter.run("media needs", check_needs)

    def compile_once() -> BridgeOutput:
        result = bridge("compile", inputs.script, inputs.dependencies)
        if result.needs != needs:
            raise BuildJobError("compiler temporal plan differs from prepared media")
        if (
            result.document_sha256 != source_hash
            or result.dependencies_sha256 != deps_hash
            or hash_file(inputs.script) != source_hash
            or hash_file(inputs.dependencies) != deps_hash
        ):
            raise BuildJobError("compiler inputs changed during this build")
        compiled = result.result
        try:
            if (
                json.loads(compiled["manifestJson"]) != compiled["manifest"]
                or json.loads(compiled["reportJson"]) != compiled["report"]
            ):
                raise BuildJobError("compiler JSON differs from its parsed result")
        except (KeyError, TypeError, ValueError) as error:
            raise BuildJobError(
                "compiler did not produce canonical manifest/report"
            ) from error
        if compiled["report"].get("status") != "ready":
            raise BuildJobError("compiler report is not ready")
        return result

    result = reporter.run("compile", compile_once)
    manifest = output / "timeline-manifest.json"
    report = output / "build-report.json"
    publish_immutable_output(manifest, result.result["manifestJson"].encode("utf-8"))
    publish_immutable_output(report, result.result["reportJson"].encode("utf-8"))
    return CompileResult(inputs, output, manifest, report, needs)
