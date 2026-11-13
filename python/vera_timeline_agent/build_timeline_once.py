"""Foreground v2 compile inputs for the one-command Studio delivery path.

Compilation is intentionally independent of the native Resolve effect. The
subsequent phases consume these exact published manifest/report bytes.
"""

from __future__ import annotations

import fcntl
import json
import os
import stat
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, TypeVar, cast

from . import studio_spike
from .build_compiler_bridge import BridgeOutput, invoke_bridge
from .build_jobs import (
    BuildJobError,
    NeedsAction,
    UncertainResult,
    publish_immutable_output,
)
from .build_stage_receipt import hash_file
from .package_cache import default_cache_root
from .v2_package import V2PackageError, build_v2_package, verify_v2_package
from .workflow_package import sha256
from .workflow_v2 import load_verified_package_v2, run_workflow_delivery_v2
from .workflow_v2_cli import attest_package_v2

T = TypeVar("T")
Bridge = Callable[[Literal["needs", "compile"], Path, Path], BridgeOutput]


@dataclass(frozen=True)
class BuildOptions:
    script: Path
    output: Path
    inputs: Path | None = None
    existing_project: str | None = None
    package_cache: Path | None = None


@dataclass(frozen=True)
class PreparedInputs:
    script: Path
    dependencies: Path
    needs_input: Path | None
    recorded_needs: Path | None
    preparation_paths: Path | None
    media_paths: Path | None


@dataclass(frozen=True)
class CompileResult:
    inputs: PreparedInputs
    output: Path
    manifest: Path
    report: Path
    needs: dict[str, Any]


@dataclass(frozen=True)
class DeliveryResult:
    project_name: str
    timeline_name: str
    frames: int
    numerator: int
    denominator: int


@dataclass
class StageTimings:
    clock: Callable[[], float] = perf_counter
    emit: Callable[[str], None] = print
    package_detail: bool = False
    stages: list[tuple[str, float]] = field(default_factory=list)
    started: float = field(init=False)

    def __post_init__(self) -> None:
        self.started = self.clock()

    def run(self, name: str, work: Callable[[], T]) -> T:
        before = self.clock()
        try:
            value = work()
        except Exception:
            self.record(name, max(0.0, self.clock() - before), passed=False)
            raise
        self.record(name, max(0.0, self.clock() - before), passed=True)
        return value

    @contextmanager
    def span(self, name: str) -> Iterator[None]:
        """Report full wall time for a grouped step, including any failed exit."""
        started = self.clock()
        try:
            yield
        except BaseException:
            self.record(name, max(0.0, self.clock() - started), passed=False)
            raise
        else:
            self.record(name, max(0.0, self.clock() - started), passed=True)

    def record(self, name: str, elapsed: float, *, passed: bool) -> None:
        self.stages.append((name, elapsed))
        self.emit(f"{name}: {'PASS' if passed else 'FAIL'} ({elapsed:.2f}s)")

    def fail(self) -> None:
        total = max(0.0, self.clock() - self.started)
        self.emit(f"FAIL: timeline was not delivered; total {total:.2f}s")

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
        media_paths=_companion(root, "media-paths.json"),
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
    reporter = timings or StageTimings()
    inputs = reporter.run("preparation", lambda: select_prepared_inputs(options))
    output = allocate_output(options, inputs)
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


def _checked_path_mapping(path: Path | None, label: str) -> dict[str, Path]:
    if path is None:
        raise NeedsAction(f"prepared {label}.json is required for packaging")
    rows = _read_json(path)
    paths: dict[str, Path] = {}
    for key, value in rows.items():
        if not isinstance(key, str) or not key or not isinstance(value, str):
            raise BuildJobError(f"invalid prepared {label} mapping")
        if not Path(value).is_absolute():
            raise BuildJobError(f"prepared {label} paths must be absolute")
        paths[key] = _plain_path(Path(value))
        hash_file(paths[key])
    return paths


@contextmanager
def exclusive_resolve_build(
    lock_path: Path | None = None,
) -> Iterator[None]:
    """One foreground writer per host; never remove the common lock file."""
    lock_path = lock_path or Path("/tmp/vera-resolve-v2-build.lock")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as error:
        raise NeedsAction("Resolve build lock is unavailable") from error
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise NeedsAction("Resolve build lock is not a regular file")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise NeedsAction("Resolve is already building a timeline") from error
        yield
    finally:
        os.close(descriptor)


def _external_resolve() -> Any:
    """Use the installed external Local SDK, not an injected Resolve runtime."""
    facts = studio_spike.detect_local_capabilities()
    if not facts.app_installed or not facts.scripting_module_installed:
        raise NeedsAction(
            "DaVinci Resolve Studio is not running or external scripting is unavailable"
        )
    try:
        adapter = studio_spike.load_resolve_adapter(facts)
    except Exception as error:
        # The closed vendor scriptapp may raise rather than return None.
        raise NeedsAction(
            "DaVinci Resolve Studio is not running or external scripting is unavailable"
        ) from error
    if getattr(adapter, "resolve", None) is None:
        raise NeedsAction(
            "DaVinci Resolve Studio is not running or external scripting is unavailable"
        )
    return cast(Any, adapter).resolve


def _require_workflow_status(
    result: dict[str, Any], expected: str, *, existing_project: bool = False
) -> None:
    if result.get("status") == expected and (
        expected != "verified"
        or (
            result.get("verified") is True
            and result.get("discrepancies") == []
            and result.get("partialTargetRetained") is False
        )
    ):
        return
    if result.get("partialTargetRetained"):
        raise UncertainResult(
            "Resolve native write is uncertain; named existing project retained; "
            "inspect it before another attempt"
            if existing_project
            else (
                "Resolve native write is uncertain; partial disposable project retained"
            )
        )
    if isinstance(result.get("refusal"), str):
        raise NeedsAction(result["refusal"])
    if (
        result.get("sourceAudioPresent") is True
        and result.get("sourceAudioNativeQualified") is False
        and result.get("failureStage") == "package validation"
    ):
        raise NeedsAction("native source-audio delivery awaits qualification")
    if result.get("nativeRateQualified") is False:
        raise NeedsAction("native fractional frame-rate delivery is unsupported")
    if expected == "verified" and result.get("status") == "verified":
        raise UncertainResult("Resolve verification is incomplete; target retained")
    raise BuildJobError(
        f"Resolve {result.get('failureStage', 'preflight')} refused before mutation"
    )


def deliver_compiled(
    compiled: CompileResult,
    *,
    timings: StageTimings,
    existing_project: str | None = None,
    package_cache: Path | None = None,
) -> DeliveryResult:
    """Package immutable bytes and create one new Studio timeline target."""
    if package_cache is not None and compiled.output.absolute() in (
        package_cache.absolute(),
        *package_cache.absolute().parents,
    ):
        raise BuildJobError("package cache must be outside the build output")
    if compiled.inputs.preparation_paths is None:
        raise NeedsAction("prepared preparation-paths.json is required for packaging")
    media = _checked_path_mapping(compiled.inputs.media_paths, "media-paths")
    preparations = _checked_path_mapping(
        compiled.inputs.preparation_paths, "preparation-paths"
    )
    package_root = compiled.output / "package"

    def package_once() -> None:
        detail = (
            {
                "stage_observer": lambda label, elapsed, passed: timings.record(
                    f"package/{label}", elapsed, passed=passed
                )
            }
            if timings.package_detail
            else {}
        )
        built = build_v2_package(
            compiled.manifest,
            compiled.report,
            compiled.inputs.script,
            compiled.inputs.dependencies,
            package_root,
            media_paths=media,
            preparation_paths=preparations,
            package_cache=package_cache,
            cache_observer=(
                lambda reused, processed: (
                    timings.emit(
                        f"package cache: reused={reused} processed={processed}"
                    )
                    if package_cache is not None
                    else None
                )
            ),
            **detail,
        )
        verified = (
            timings.run(
                "package/outer verification", lambda: verify_v2_package(package_root)
            )
            if timings.package_detail
            else verify_v2_package(package_root)
        )
        manifest = _read_json(compiled.manifest)
        if verified.build_id != built.build_id or verified.build_id != manifest.get(
            "buildId"
        ):
            raise BuildJobError("package build identity differs from compiler")

    try:
        timings.run("package", package_once)
    except V2PackageError as error:
        raise BuildJobError(
            "package could not be built from prepared local inputs"
        ) from error
    attestation = compiled.output / "v2-attestation.json"
    timings.run("attest", lambda: attest_package_v2(package_root, attestation))
    digest = sha256(attestation)
    checked = load_verified_package_v2(attestation, digest)
    if checked.root != package_root or checked.manifest != _read_json(
        compiled.manifest
    ):
        raise BuildJobError("attested package does not match compiled manifest")

    with timings.span("Resolve step + check"), exclusive_resolve_build():
        resolve = timings.run("connect", _external_resolve)
        preflight = timings.run(
            "preflight",
            lambda: run_workflow_delivery_v2(
                resolve,
                attestation,
                digest,
                external_scripting="Local",
                existing_project=existing_project,
            ),
        )
        _require_workflow_status(
            preflight, "preflight_passed", existing_project=existing_project is not None
        )
        native = run_workflow_delivery_v2(
            resolve,
            attestation,
            digest,
            action="build",
            authorize_new_nonproduction=True,
            external_scripting="Local",
            existing_project=existing_project,
            stage_observer=lambda label, elapsed, passed: timings.record(
                label, elapsed, passed=passed
            ),
        )
        _require_workflow_status(
            native, "verified", existing_project=existing_project is not None
        )

    timeline = checked.manifest["timeline"]
    return DeliveryResult(
        project_name=existing_project or checked.attestation["projectName"],
        timeline_name=checked.attestation["timelineName"],
        frames=timeline["durationFrames"],
        numerator=timeline["frameRate"]["numerator"],
        denominator=timeline["frameRate"]["denominator"],
    )


def build_once(options: BuildOptions, *, timings: StageTimings) -> DeliveryResult:
    return deliver_compiled(
        compile_prepared(options, timings=timings),
        timings=timings,
        existing_project=options.existing_project,
        package_cache=options.package_cache or default_cache_root(),
    )
