"""Compare a verified saved build, offline #101 observation and freshly compiled script.

This command never opens Resolve or creates, modifies or delivers a timeline.
Its output is review evidence, NOT permission to apply changes.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from .build_compiler_bridge import BridgeOutput, invoke_bridge
from .build_jobs import BuildJobError, NeedsAction
from .build_stage_receipt import canonical_json
from .readback_timeline_cli import _load_readback_package, _read_saved_row_map
from .row_timeline_map import SCHEMA_VERSION_V2, validate_saved_row_map
from .three_way_compare import compare_three_way_rows
from .v2_package import _compiler_hash
from .workflow_v2 import _read_regular, _regular_absolute, _strict_object

_MAX_JSON = 16 * 1024 * 1024
_EXAMPLE = (
    Path(__file__).resolve().parents[2] / "tests/data/three_way_compare/example.json"
)
Bridge = Callable[[Literal["compile"], Path, Path], BridgeOutput]


def _json_file(path: Path, label: str) -> dict[str, Any]:
    return _strict_object(_read_regular(path, label, max_bytes=_MAX_JSON), label)


def _assert_current_compiler(
    document: Mapping[str, Any],
    dependencies: Mapping[str, Any],
    manifest: Mapping[str, Any],
    report: Mapping[str, Any],
) -> None:
    """Pin the new manifest to the exact document and prepared dependencies."""
    if document.get("schemaVersion") != "script-document/v2":
        raise ValueError("current script must be a v2 document")
    if dependencies.get("schemaVersion") != "compiler-dependencies/v2":
        raise ValueError("current dependencies must be prepared v2 inputs")
    if manifest.get("schemaVersion") != "timeline-manifest/v2":
        raise ValueError("compiler did not return a v2 manifest")
    if (
        report.get("schemaVersion") != "build-report/v2"
        or report.get("status") != "ready"
    ):
        raise ValueError("compiler report is not ready")
    binding = dependencies.get("document")
    m_binding = manifest.get("document")
    r_binding = report.get("document")
    if (
        not isinstance(binding, Mapping)
        or not isinstance(m_binding, Mapping)
        or not isinstance(r_binding, Mapping)
    ):
        raise ValueError("compiler document identity is missing")
    document_hash = document.get("liveContentHash")
    if document_hash != _compiler_hash(
        {k: v for k, v in document.items() if k != "liveContentHash"}
    ):
        raise ValueError("current script content hash is stale")
    identity = (
        document.get("id"),
        document.get("projectId"),
        document_hash,
        document.get("liveHeadSequence"),
    )
    for source in (binding, m_binding, r_binding):
        if (
            source.get("documentId"),
            source.get("projectId"),
            source.get("contentHash"),
            source.get("liveHeadSequence"),
        ) != identity:
            raise ValueError("compiler document identity differs from current script")
        if (
            source.get("revision"),
            source.get("textHash"),
            source.get("settingsHash"),
        ) != (
            binding.get("revision"),
            binding.get("textHash"),
            binding.get("settingsHash"),
        ):
            raise ValueError(
                "compiler revision or source hashes differ from dependencies"
            )
    build = dependencies.get("build")
    if not isinstance(build, Mapping) or (
        manifest.get("buildId") != build.get("buildId")
        or manifest.get("id") != build.get("manifestId")
        or report.get("buildId") != build.get("buildId")
        or report.get("id") != build.get("reportId")
        or not isinstance(report.get("manifest"), Mapping)
        or report["manifest"].get("id") != manifest.get("id")
        or report["manifest"].get("contentHash") != _compiler_hash(manifest)
    ):
        raise ValueError(
            "compiled build/manifest/report identity differs from prepared inputs"
        )
    if report.get("dependenciesHash") != _compiler_hash(dependencies):
        raise ValueError(
            "compiled report dependencies hash differs from prepared inputs"
        )


def compare_offline(
    baseline_output: Path,
    observation: Path,
    script: Path,
    dependencies: Path,
    *,
    bridge: Bridge = invoke_bridge,
) -> dict[str, Any]:
    """Classify without acquiring any native lock or contacting Resolve."""
    root = _regular_absolute(baseline_output, "verified build output", directory=True)
    saved = _read_saved_row_map(root)
    if (
        saved is None
        or saved.get("schemaVersion") != SCHEMA_VERSION_V2
        or saved.get("version") != 2
    ):
        raise ValueError("a verified v2 row-timeline-map.json baseline is required")
    package = _load_readback_package(root)
    validate_saved_row_map(package.manifest, package.view, saved)
    if saved.get("timelineName") != package.attestation.get(
        "timelineName"
    ) or saved.get("projectName") != package.attestation.get("projectName"):
        raise ValueError("baseline target differs from attested delivery")
    baseline_document = _json_file(
        package.root / "Builds" / package.manifest["buildId"] / "script-document.json",
        "attested original script",
    )
    observed = _json_file(observation, "saved #101 observation")
    if "status" in observed or observed.get("rows") is None:
        raise ValueError(
            "expected a complete #101 observation, not a build/readback status"
        )
    current_path = _regular_absolute(script, "current script", directory=False)
    dependencies_path = _regular_absolute(
        dependencies, "current compiler dependencies", directory=False
    )
    current_bytes = _read_regular(current_path, "current script", max_bytes=_MAX_JSON)
    dep_bytes = _read_regular(
        dependencies_path, "current compiler dependencies", max_bytes=_MAX_JSON
    )
    current = _strict_object(current_bytes, "current script")
    prepared = _strict_object(dep_bytes, "current compiler dependencies")
    if current.get("id") != baseline_document.get("id") or current.get(
        "projectId"
    ) != baseline_document.get("projectId"):
        raise ValueError(
            "current script belongs to a different baseline document/project"
        )
    if observed.get("buildId") != saved.get("buildId") or observed.get(
        "timelineId"
    ) != saved.get("timelineId"):
        raise ValueError("observation is for a different build or original timeline")
    result = bridge("compile", current_path, dependencies_path)
    if (
        result.document_sha256 != hashlib.sha256(current_bytes).hexdigest()
        or result.dependencies_sha256 != hashlib.sha256(dep_bytes).hexdigest()
    ):
        raise ValueError("compiler did not pin the supplied current inputs")
    if (
        _read_regular(current_path, "current script", max_bytes=_MAX_JSON)
        != current_bytes
        or _read_regular(
            dependencies_path, "current compiler dependencies", max_bytes=_MAX_JSON
        )
        != dep_bytes
    ):
        raise ValueError("current compiler inputs changed while being compiled")
    compiled = result.result
    manifest = compiled.get("manifest")
    report = compiled.get("report")
    if not isinstance(manifest, dict) or not isinstance(report, dict):
        raise ValueError("compiler did not return manifest and report objects")
    if (
        _strict_object(compiled["manifestJson"].encode("utf-8"), "compiler manifest")
        != manifest
        or _strict_object(compiled["reportJson"].encode("utf-8"), "compiler report")
        != report
    ):
        raise ValueError("compiler JSON bytes differ from the returned objects")
    _assert_current_compiler(current, prepared, manifest, report)
    return compare_three_way_rows(
        package.manifest, saved, baseline_document, manifest, current, observed
    )


def example_comparison() -> dict[str, Any]:
    """Fabricated fixture only: not an attested build or live observation."""
    case = _json_file(_EXAMPLE, "synthetic example fixture")
    result = compare_three_way_rows(
        case["baselineManifest"],
        case["baselineMap"],
        case["baselineDocument"],
        case["currentManifest"],
        case["currentDocument"],
        case["observation"],
    )
    result["exampleOnly"] = (
        "Fabricated offline demonstration, NOT a verified build. "
        "both_compatible is testable only by synthetic injection; "
        "the production #327 preservation allow-list is empty."
    )
    return result


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument(
        "--baseline-output", type=Path, help="checked previous build result directory"
    )
    command.add_argument("--observation", type=Path, help="saved #101 observation JSON")
    command.add_argument("--script", type=Path, help="current script-document-v2 JSON")
    command.add_argument(
        "--dependencies",
        type=Path,
        help="current prepared compiler-dependencies-v2 JSON",
    )
    command.add_argument(
        "--example",
        action="store_true",
        help="show fabricated SDK-free sample (no verified package)",
    )
    return command


def main(argv: Sequence[str] | None = None) -> int:
    command = parser()
    args = command.parse_args(argv)
    inputs = (args.baseline_output, args.observation, args.script, args.dependencies)
    if (args.example and any(value is not None for value in inputs)) or (
        not args.example and any(value is None for value in inputs)
    ):
        command.error("use --example alone or supply all four offline file options")
    try:
        output = (
            example_comparison()
            if args.example
            else compare_offline(*(cast(Path, path) for path in inputs))
        )
        sys.stdout.buffer.write(canonical_json(output))
    except (
        ValueError,
        OSError,
        BuildJobError,
        NeedsAction,
        KeyError,
        TypeError,
        UnicodeError,
    ) as error:
        print(f"Cannot compare: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
