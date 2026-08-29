from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import opentimelineio as otio  # type: ignore[import-untyped]
import pytest
from vera_timeline_agent.resolve_import_package import (
    ResolveImportPackageError,
    build_resolve_import_package,
    verify_resolve_import_package,
)

ROOT = Path(__file__).resolve().parents[1]
BASE_MANIFEST = ROOT / "tests/data/slice_1_3/minimal.manifest.golden.json"
BASE_REPORT = ROOT / "tests/data/slice_1_3/minimal.report.golden.json"
FIXTURE_AUDIO = ROOT / "fixtures/media/audio-ambient-bed.wav"


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    input_root = tmp_path / "input"
    input_root.mkdir()
    origin = input_root / "narration.wav"
    shutil.copyfile(FIXTURE_AUDIO, origin)

    manifest = copy.deepcopy(_load(BASE_MANIFEST))
    report = copy.deepcopy(_load(BASE_REPORT))
    manifest["timeline"].update(
        {
            "frameRate": {"numerator": 24, "denominator": 1},
            "durationFrames": 72,
            "width": 320,
            "height": 180,
        }
    )
    audio_source = next(
        source for source in manifest["sources"] if source["kind"] == "audio"
    )
    audio_source.update(
        {
            "channels": 2,
            "contentHash": f"sha256:{_sha256(origin)}",
            "durationFrames": 72,
        }
    )
    for event in manifest["events"]:
        event["recordRange"]["durationFrames"] = 72
        if event["kind"] == "audio":
            event["sourceRange"]["durationFrames"] = 72
    report["timeline"] = copy.deepcopy(manifest["timeline"])
    for result in report["eventResults"]:
        result["recordRange"]["durationFrames"] = 72

    manifest_path = input_root / "manifest.json"
    report_path = input_root / "report.json"
    plan_path = input_root / "plan.json"
    manifest_bytes = _canonical(manifest)
    manifest_path.write_bytes(manifest_bytes)
    report["manifest"]["contentHash"] = (
        f"sha256:{hashlib.sha256(manifest_bytes).hexdigest()}"
    )
    report_path.write_bytes(_canonical(report))
    plan_path.write_bytes(
        _canonical(
            {
                audio_source["id"]: {
                    "artifactId": "narration-artifact-v1",
                    "origin": origin.name,
                    "policy": "copy",
                }
            }
        )
    )
    return manifest_path, report_path, plan_path


def test_builds_verifies_and_exactly_reuses_one_project(tmp_path: Path) -> None:
    manifest_path, report_path, plan_path = _inputs(tmp_path)
    project = tmp_path / "Authoring Project"

    first = build_resolve_import_package(manifest_path, report_path, plan_path, project)
    verification = verify_resolve_import_package(project)
    second = build_resolve_import_package(
        manifest_path, report_path, plan_path, project
    )

    manifest = _load(manifest_path)
    report = _load(report_path)
    receipt = _load(first.verification_path)
    assert first.reused is False
    assert second.reused is True
    assert verification.event_count == 2
    assert first.manifest_path.read_bytes() == manifest_path.read_bytes()
    assert first.report_path.read_bytes() == report_path.read_bytes()
    assert receipt["status"] == "ready_to_import"
    assert receipt["manualCompletionItemIds"] == [
        item["id"] for item in report["manualCompletionItems"]
    ]
    assert receipt["materializations"][0]["mediaFacts"] == {
        "channels": 2,
        "durationFrames": 72,
        "sampleRate": 48000,
    }

    timeline = otio.adapters.read_from_file(str(first.otio_path))
    references = [
        child.media_reference.target_url
        for track in timeline.tracks
        for child in track
        if isinstance(child, otio.schema.Clip)
    ]
    assert set(references) == {
        "../../Media/Narration/minimal.wav",
        f"../../Media/Placeholders/{manifest['sources'][0]['id']}.png",
    }
    assert (project / "Media/Narration/minimal.wav").stat().st_nlink == 1


@pytest.mark.parametrize("status", ["blocked", "failed"])
def test_refuses_unready_report_without_publication(
    tmp_path: Path, status: str
) -> None:
    manifest_path, report_path, plan_path = _inputs(tmp_path)
    report = _load(report_path)
    report["status"] = status
    report_path.write_bytes(_canonical(report))
    project = tmp_path / "project"

    with pytest.raises(ResolveImportPackageError, match="cannot be published"):
        build_resolve_import_package(manifest_path, report_path, plan_path, project)

    assert not project.exists()


def test_refuses_noncanonical_or_inconsistent_compiler_artifacts(
    tmp_path: Path,
) -> None:
    manifest_path, report_path, plan_path = _inputs(tmp_path)
    report = _load(report_path)
    report["summary"]["eventCount"] = 999
    report_path.write_bytes(_canonical(report))

    with pytest.raises(ResolveImportPackageError, match="summary counts"):
        build_resolve_import_package(
            manifest_path, report_path, plan_path, tmp_path / "project"
        )

    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ResolveImportPackageError, match="not canonical JSON"):
        build_resolve_import_package(
            manifest_path, report_path, plan_path, tmp_path / "project"
        )


def test_refuses_linked_origins_and_detects_package_tampering(tmp_path: Path) -> None:
    manifest_path, report_path, plan_path = _inputs(tmp_path)
    plan = _load(plan_path)
    source_id = next(iter(plan))
    linked = plan_path.parent / "linked.wav"
    linked.symlink_to("narration.wav")
    plan[source_id]["origin"] = linked.name
    plan_path.write_bytes(_canonical(plan))

    with pytest.raises(ResolveImportPackageError, match="symbolic link"):
        build_resolve_import_package(
            manifest_path, report_path, plan_path, tmp_path / "rejected"
        )

    plan[source_id]["origin"] = "narration.wav"
    plan_path.write_bytes(_canonical(plan))
    result = build_resolve_import_package(
        manifest_path, report_path, plan_path, tmp_path / "project"
    )
    placeholder = next((tmp_path / "project/Media/Placeholders").glob("*.png"))
    placeholder.write_bytes(placeholder.read_bytes() + b"tamper")
    with pytest.raises(ResolveImportPackageError, match="receipt placeholder differs"):
        verify_resolve_import_package(result.project_root)


def test_cli_reports_ready_to_import_json(tmp_path: Path) -> None:
    manifest_path, report_path, plan_path = _inputs(tmp_path)
    project = tmp_path / "cli-project"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "vera_timeline_agent.resolve_import_package",
            str(manifest_path),
            str(report_path),
            str(plan_path),
            "--output",
            str(project),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "ready_to_import"
