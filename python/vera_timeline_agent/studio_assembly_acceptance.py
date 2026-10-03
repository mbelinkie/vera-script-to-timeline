"""Build the slice-owned synthetic package used for Studio assembly acceptance."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, cast

from vera_timeline_agent.resolve_import_package import (
    ResolveImportPackageResult,
    build_resolve_import_package,
)

_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _ROOT / "tests/data/slice_1_3/minimal.manifest.golden.json"
_REPORT = _ROOT / "tests/data/slice_1_3/minimal.report.golden.json"
_AUDIO = _ROOT / "fixtures/media/audio-ambient-bed.wav"
_BUILD_ID = "13000000-0000-4000-8000-000000000036"


def build_studio_assembly_acceptance_package(
    output: Path | str,
) -> ResolveImportPackageResult:
    """Materialize one retained, synthetic package without touching frozen inputs."""
    output_path = Path(output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    inputs = Path(
        tempfile.mkdtemp(prefix=".vera-studio-assembly-inputs-", dir=output_path.parent)
    )
    try:
        audio = inputs / "narration.wav"
        shutil.copyfile(_AUDIO, audio)
        manifest = copy.deepcopy(_load(_MANIFEST))
        report = copy.deepcopy(_load(_REPORT))
        manifest["timeline"].update(
            {
                "frameRate": {"numerator": 24, "denominator": 1},
                "durationFrames": 72,
                "width": 1920,
                "height": 1080,
            }
        )
        manifest["buildId"] = _BUILD_ID
        report["buildId"] = _BUILD_ID
        source = next(item for item in manifest["sources"] if item["kind"] == "audio")
        source.update(
            {
                "channels": 2,
                "contentHash": f"sha256:{_sha256(audio)}",
                "durationFrames": 72,
            }
        )
        for event in manifest["events"]:
            event["recordRange"]["durationFrames"] = 72
            if event["kind"] == "audio":
                event["sourceRange"]["durationFrames"] = 72
        report["timeline"] = copy.deepcopy(manifest["timeline"])
        for item in report["eventResults"]:
            item["recordRange"]["durationFrames"] = 72
        manifest_path = inputs / "timeline-manifest.json"
        report_path = inputs / "build-report.json"
        plan_path = inputs / "materialization-plan.json"
        manifest_bytes = _canonical(manifest)
        manifest_path.write_bytes(manifest_bytes)
        report["manifest"]["contentHash"] = (
            f"sha256:{hashlib.sha256(manifest_bytes).hexdigest()}"
        )
        report_path.write_bytes(_canonical(report))
        plan_path.write_bytes(
            _canonical(
                {
                    source["id"]: {
                        "artifactId": "issue-34-synthetic-narration",
                        "origin": audio.name,
                        "policy": "copy",
                    }
                }
            )
        )
        return build_resolve_import_package(
            manifest_path, report_path, plan_path, output_path
        )
    finally:
        shutil.rmtree(inputs, ignore_errors=True)


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
