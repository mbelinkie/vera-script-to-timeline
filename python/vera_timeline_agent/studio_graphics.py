"""Verified EV24 Studio packages; compiler artifacts remain byte-for-byte intact."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from .ev24_fusion_spike import (
    EV24_COUNTRIES,
    EV24_SETTING_SHA256,
    _local_ev24_stop,
)
from .resolve_import_package import (
    build_resolve_import_package,
    verify_resolve_import_package,
)
from .resolve_import_package.package import (
    _canonical_json,
    _load_json,
    _require_canonical,
    _safe_existing_regular,
    _validate_contracts,
    _validate_report_linkage,
)
from .studio_assembly import StudioAssemblyResult, run_studio_assembly
from .studio_graphics_runtime import (
    ATLAS,
    ATLAS_REFERENCE,
    FILE_HASHES,
    SETTING,
    TEMPLATE_REL,
    JsonObject,
    _package_digest,
    _require_live_plan,
)
from .studio_graphics_runtime import (
    ATLAS_SHA256 as ATLAS_SHA256,
)
from .studio_graphics_runtime import (
    PublicStudioGraphicAdapter as PublicStudioGraphicAdapter,
)
from .studio_graphics_runtime import (
    StudioGraphicError as StudioGraphicError,
)
from .studio_graphics_runtime import (
    StudioGraphicPackage as StudioGraphicPackage,
)
from .studio_graphics_runtime import (
    _hash as _hash,
)
from .studio_graphics_runtime import (
    _strict_controls as _strict_controls,
)
from .studio_graphics_runtime import (
    graphic_controls as graphic_controls,
)
from .studio_graphics_runtime import (
    transport_artifacts as transport_artifacts,
)
from .studio_graphics_runtime import (
    validate_graphics as validate_graphics,
)
from .studio_spike import LocalFacts, load_resolve_adapter


def _verify_template(root: Path, manifest: JsonObject) -> JsonObject:
    package, raw = _load_json(
        root / "package-manifest.json", "registered EV24 manifest"
    )
    _require_canonical(package, raw, "registered EV24 manifest")
    digest = _package_digest(package)
    project_id = manifest["sourceDocument"]["projectId"]
    expected_revision = (
        "revision_"
        + hashlib.sha256(f"{project_id}\0{digest}".encode()).hexdigest()[:24]
    )
    profile = package.get("ev24", {})
    expected_controls = {
        "country": {"tool": "ControlHub", "input": "Country", "exposed": "Country"},
        "year": {"tool": "ControlHub", "input": "Year", "exposed": "Year"},
        "topLineOverride": {
            "tool": "ControlHub",
            "input": "SongTitle",
            "exposed": "TopLine",
        },
        "bottomLineOverride": {
            "tool": "ControlHub",
            "input": "Singer",
            "exposed": "BottomLine",
        },
        "badgeOverrideAsset": {
            "tool": "BadgeOverride",
            "input": "Clip",
            "exposed": "BadgeOverride",
        },
    }
    if (
        package.get("externalLineageKey") != "ev24-lower-third"
        or package.get("entryPoint") != SETTING
        or profile.get("graphFingerprint") != "sha256:" + EV24_SETTING_SHA256
        or profile.get("atlasReference") != ATLAS_REFERENCE
        or profile.get("countryIds") != list(EV24_COUNTRIES)
        or profile.get("semanticControls") != expected_controls
        or profile.get("timing")
        != {
            "entranceFrames": 48,
            "exitFrames": 16,
            "minimumFrames": 64,
            "hold": "flexible",
        }
    ):
        raise StudioGraphicError("registered EV24 profile identity differs")
    if project_id not in package["rights"]["allowedProjectIds"]:
        raise StudioGraphicError("registered template is not approved for this project")
    declarations = package["files"]
    if len(declarations) != 3 or {item["path"] for item in declarations} != set(
        FILE_HASHES
    ):
        raise StudioGraphicError("registered package file inventory differs")
    for item in declarations:
        path = _safe_existing_regular(root / item["path"], "package-owned asset")
        raw = path.read_bytes()
        if (
            item["sha256"] != "sha256:" + FILE_HASHES[item["path"]]
            or _hash(raw) != item["sha256"]
            or len(raw) != item["byteLength"]
        ):
            raise StudioGraphicError("package-owned asset hash or length differs")
    for source in manifest["sources"]:
        if source["kind"] == "fusion_template" and (
            source["packageDigest"] != digest
            or source["projectRevisionId"] != expected_revision
        ):
            raise StudioGraphicError(
                "registered package digest or project revision differs"
            )
    return package


def verify_studio_graphic_package(root: Path | str) -> StudioGraphicPackage:
    directory = Path(root).absolute()
    manifest, raw = _load_json(
        directory / "timeline-manifest.json", "compiler manifest"
    )
    report, report_raw = _load_json(directory / "build-report.json", "compiler report")
    _require_canonical(manifest, raw, "compiler manifest")
    _require_canonical(report, report_raw, "compiler report")
    _validate_contracts(manifest, report)
    _require_live_plan(manifest, report)
    _validate_report_linkage(manifest, report, raw)
    validate_graphics(manifest)
    template = _verify_template(directory / TEMPLATE_REL, manifest)
    transport, transport_report = transport_artifacts(manifest, report)
    verified = verify_resolve_import_package(directory / "Transport")
    build = directory / "Transport/Builds" / verified.build_id
    for name, expected in (
        ("timeline-manifest.json", transport),
        ("build-report.json", transport_report),
    ):
        if (build / name).read_bytes() != _canonical_json(expected):
            raise StudioGraphicError(
                "internal transport differs from compiled occurrences"
            )
    expected_files = {
        "timeline-manifest.json",
        "build-report.json",
        "studio-package.json",
        (TEMPLATE_REL / "package-manifest.json").as_posix(),
    } | {(TEMPLATE_REL / name).as_posix() for name in FILE_HASHES}
    expected_files |= {
        "Transport/" + path.relative_to(directory / "Transport").as_posix()
        for path in (directory / "Transport").rglob("*")
        if path.is_file()
    }
    actual_files: set[str] = set()
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise StudioGraphicError("Studio package contains a symbolic link")
        if path.is_file():
            _safe_existing_regular(path, "Studio package file")
            actual_files.add(path.relative_to(directory).as_posix())
    if actual_files != expected_files:
        raise StudioGraphicError("Studio package inventory differs")
    receipt, receipt_raw = _load_json(
        directory / "studio-package.json", "Studio receipt"
    )
    expected_receipt = {
        "schemaVersion": "studio-graphic-package/v1",
        "status": "ready_for_studio",
        "buildId": manifest["buildId"],
        "manifestHash": _hash(raw),
        "reportHash": _hash(report_raw),
        "packageDigest": _package_digest(template),
    }
    if receipt_raw != _canonical_json(expected_receipt) or receipt != expected_receipt:
        raise StudioGraphicError("Studio receipt differs")
    return StudioGraphicPackage(directory, manifest, report, template, transport)


def build_studio_graphic_package(
    manifest_path: Path,
    report_path: Path,
    materialization_plan: Path,
    registered_template: Path,
    output: Path,
) -> StudioGraphicPackage:
    """Publish a new Studio-only envelope around the unchanged compiler artifacts."""
    manifest, raw = _load_json(manifest_path, "compiler manifest")
    report, report_raw = _load_json(report_path, "compiler report")
    _require_canonical(manifest, raw, "compiler manifest")
    _require_canonical(report, report_raw, "compiler report")
    _validate_contracts(manifest, report)
    _require_live_plan(manifest, report)
    _validate_report_linkage(manifest, report, raw)
    validate_graphics(manifest)
    template = _verify_template(registered_template, manifest)
    if output.exists():
        raise StudioGraphicError("Studio output already exists; refusing to overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".studio-graphics-", dir=output.parent))
    try:
        templates = staging / TEMPLATE_REL
        templates.mkdir(parents=True)
        for name in ["package-manifest.json", *FILE_HASHES]:
            shutil.copyfile(registered_template / name, templates / name)
        (staging / "timeline-manifest.json").write_bytes(raw)
        (staging / "build-report.json").write_bytes(report_raw)
        media, media_report = transport_artifacts(manifest, report)
        plan, _ = _load_json(materialization_plan, "media materialization plan")
        # Only the trusted package atlas seeds graphics; author data supplies no path.
        expected_media = {
            source["id"]
            for source in manifest["sources"]
            if source["kind"] not in {"placeholder", "fusion_template"}
        }
        if set(plan) != expected_media:
            raise StudioGraphicError(
                "media plan must contain exactly non-graphic media"
            )
        for entry in plan.values():
            origin = Path(entry["origin"])
            entry["origin"] = str((materialization_plan.parent / origin).absolute())
        for source in manifest["sources"]:
            if source["kind"] == "fusion_template":
                plan[source["id"]] = {
                    "artifactId": "ev24-package-atlas",
                    "origin": str((templates / ATLAS).absolute()),
                    "policy": "copy",
                }
        with tempfile.TemporaryDirectory(prefix="vera-studio-inputs-") as temp:
            inputs = Path(temp)
            for name, value in (
                ("manifest.json", media),
                ("report.json", media_report),
                ("plan.json", plan),
            ):
                (inputs / name).write_bytes(_canonical_json(value))
            build_resolve_import_package(
                inputs / "manifest.json",
                inputs / "report.json",
                inputs / "plan.json",
                staging / "Transport",
            )
        receipt = {
            "schemaVersion": "studio-graphic-package/v1",
            "status": "ready_for_studio",
            "buildId": manifest["buildId"],
            "manifestHash": _hash(raw),
            "reportHash": _hash(report_raw),
            "packageDigest": _package_digest(template),
        }
        (staging / "studio-package.json").write_bytes(_canonical_json(receipt))
        verify_studio_graphic_package(staging)
        # rename refuses a pre-existing nonempty target; never merge inventories.
        if output.exists():
            raise StudioGraphicError("Studio output appeared during publication")
        staging.rename(output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return verify_studio_graphic_package(output)


@dataclass(frozen=True)
class StudioGraphicAssemblyResult(StudioAssemblyResult):
    graphic_observations: tuple[JsonObject, ...] = ()
    compiler_manifest_hash: str = ""


def run_studio_graphics(
    root: Path | str, *, action: str = "preflight"
) -> StudioGraphicAssemblyResult:
    package = verify_studio_graphic_package(root)
    adapters: list[PublicStudioGraphicAdapter] = []

    def factory(local: LocalFacts) -> PublicStudioGraphicAdapter:
        stop = _local_ev24_stop(local)
        if stop is not None:
            raise StudioGraphicError(stop)
        base = load_resolve_adapter(local)
        adapter = PublicStudioGraphicAdapter(getattr(base, "resolve", None), package)
        adapters.append(adapter)
        return adapter

    result = run_studio_assembly(
        package.root / "Transport", action=action, adapter_factory=factory
    )
    # The base report describes media only; graphic success needs the additional proof.
    result = replace(
        result,
        manual_completion=tuple(
            item
            for item in result.manual_completion
            if not item.startswith("No Fusion graphic")
        ),
    )
    observations = tuple(adapters[0].graphic_observations) if adapters else ()
    return StudioGraphicAssemblyResult(
        **vars(result),
        graphic_observations=observations,
        compiler_manifest_hash=_hash(_canonical_json(package.manifest)),
    )
