from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import opentimelineio as otio  # type: ignore[import-untyped]
import pytest
from vera_timeline_agent.resolve_import_package import ResolveImportPackageError
from vera_timeline_agent.resolve_import_package.baked_graphics import (
    build_baked_graphic_package,
    verify_baked_graphic_package,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests/data/issue_7/normal.free.manifest.golden.json"
REPORT = ROOT / "tests/data/issue_7/normal.free.report.golden.json"
AUDIO = ROOT / "fixtures/media/audio-ambient-bed.wav"


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _alpha_mov(
    path: Path, frames: int = 120, rate: str = "24000/1001", size: str = "64x36"
) -> None:
    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black@0.0:s={size}:r={rate},format=yuva444p10le",
            "-frames:v",
            str(frames),
            "-vf",
            "format=yuva444p10le",
            "-c:v",
            "prores_ks",
            "-profile:v",
            "4",
            "-pix_fmt",
            "yuva444p10le",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "input"
    root.mkdir(parents=True)
    manifest = _load(MANIFEST)
    report = _load(REPORT)
    manifest["timeline"]["width"] = 64
    manifest["timeline"]["height"] = 36
    report["timeline"] = manifest["timeline"]
    audio = root / "narration.wav"
    shutil.copyfile(AUDIO, audio)
    audio_source = next(
        source for source in manifest["sources"] if source["kind"] == "audio"
    )
    audio_source["contentHash"] = f"sha256:{_sha256(audio)}"
    audio_source["channels"] = 2
    manifest_path = root / "manifest.json"
    _write(manifest_path, manifest)
    report["manifest"]["contentHash"] = f"sha256:{_sha256(manifest_path)}"
    report_path = root / "report.json"
    _write(report_path, report)
    materialization = root / "materialization.json"
    _write(
        materialization,
        {
            audio_source["id"]: {
                "artifactId": "narration-v1",
                "origin": audio.name,
                "policy": "copy",
            }
        },
    )
    candidate = root / "candidate.mov"
    _alpha_mov(candidate)
    event = next(
        event for event in manifest["events"] if event["kind"] == "fusion_graphic"
    )
    source = next(
        source for source in manifest["sources"] if source["id"] == event["sourceId"]
    )
    manual = next(
        item
        for item in report["manualCompletionItems"]
        if item["entity"]["id"] == event["id"]
    )
    plan = root / "baked.json"
    _write(
        plan,
        {
            "schemaVersion": "resolve-free-baked-graphic-candidate/v1",
            "bakes": [
                {
                    "eventId": event["id"],
                    "artifactId": "ev24-studio-render-1",
                    "origin": candidate.name,
                    "renderer": {
                        "name": "DaVinci Resolve Studio",
                        "version": "21.1.0.0014",
                    },
                    "template": {
                        key: source[key]
                        for key in (
                            "templateKey",
                            "projectRevisionId",
                            "packageDigest",
                            "entryAssetHash",
                        )
                    },
                    "semanticSnapshotHash": event["semanticSnapshotHash"],
                    "manualCompletionItemId": manual["id"],
                    "expected": {
                        "width": 64,
                        "height": 36,
                        "frameRate": manifest["timeline"]["frameRate"],
                        "durationFrames": 120,
                        "alpha": True,
                    },
                }
            ],
        },
    )
    return manifest_path, report_path, materialization, plan


def test_baked_graphic_adapter_is_importable() -> None:
    assert callable(build_baked_graphic_package)


def test_packages_exact_ev24_candidate_with_placeholder_report_and_otio_provenance(
    tmp_path: Path,
) -> None:
    manifest, report, materialization, plan = _inputs(tmp_path)
    result = build_baked_graphic_package(
        manifest, report, materialization, plan, tmp_path / "Authoring Project"
    )
    receipt = _load(result.verification_path)
    timeline = otio.adapters.read_from_file(str(result.otio_path))
    clip = next(
        child
        for track in timeline.tracks
        for child in track
        if isinstance(child, otio.schema.Clip)
        and child.metadata["vera"]["event_kind"] == "fusion_graphic"
    )
    assert result.reused is False
    assert receipt["status"] == "ready_for_external_acceptance"
    assert receipt["graphicBakeCandidates"][0]["mediaFacts"]["alpha"] is True
    assert (
        receipt["graphicBakeCandidates"][0]["semanticSnapshotHash"]
        == _load(manifest)["events"][0]["semanticSnapshotHash"]
    )
    assert clip.media_reference.target_url.endswith(
        "Media/Graphics/70000000-0000-4000-8000-000000000001.mov"
    )
    assert clip.metadata["vera"]["graphic_bake"] == receipt["graphicBakeCandidates"][0]
    assert (
        "unchanged Free placeholder outcome"
        in result.build_root.joinpath("IMPORT_INSTRUCTIONS.md").read_text()
    )
    verify_baked_graphic_package(result.project_root)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda plan: plan["bakes"][0]["expected"].update({"alpha": False}),
            "invalid expected media facts",
        ),
        (
            lambda plan: plan["bakes"][0].update(
                {"semanticSnapshotHash": "sha256:" + "d" * 64}
            ),
            "stale template or semantic identity",
        ),
        (
            lambda plan: plan["bakes"][0].update({"manualCompletionItemId": "missing"}),
            "silently replace",
        ),
        (
            lambda plan: plan["bakes"][0]["expected"].update({"durationFrames": 119}),
            "invalid expected media facts",
        ),
        (
            lambda plan: plan["bakes"][0]["expected"].update(
                {"frameRate": {"numerator": 24, "denominator": 1}}
            ),
            "invalid expected media facts",
        ),
    ],
)
def test_rejects_stale_or_silent_baked_candidate_plans(
    tmp_path: Path, mutate: Any, match: str
) -> None:
    manifest, report, materialization, plan_path = _inputs(tmp_path)
    plan = _load(plan_path)
    mutate(plan)
    _write(plan_path, plan)
    with pytest.raises(ResolveImportPackageError, match=match):
        build_baked_graphic_package(
            manifest, report, materialization, plan_path, tmp_path / "rejected"
        )


def test_rejects_missing_alpha_corrupt_output_and_tampering(tmp_path: Path) -> None:
    manifest, report, materialization, plan_path = _inputs(tmp_path)
    plan = _load(plan_path)
    opaque = plan_path.parent / "opaque.mp4"
    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=s=64x36:r=24000/1001",
            "-frames:v",
            "120",
            str(opaque),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    plan["bakes"][0]["origin"] = opaque.name
    _write(plan_path, plan)
    with pytest.raises(ResolveImportPackageError, match="missing alpha"):
        build_baked_graphic_package(
            manifest, report, materialization, plan_path, tmp_path / "no-alpha"
        )
    opaque.write_bytes(b"not media")
    with pytest.raises(ResolveImportPackageError, match="FFprobe rejected"):
        build_baked_graphic_package(
            manifest, report, materialization, plan_path, tmp_path / "corrupt"
        )
    manifest, report, materialization, plan_path = _inputs(tmp_path / "fresh")
    result = build_baked_graphic_package(
        manifest, report, materialization, plan_path, tmp_path / "project"
    )
    graphic = next((result.project_root / "Media/Graphics").glob("*.mov"))
    graphic.write_bytes(graphic.read_bytes() + b"tamper")
    with pytest.raises(ResolveImportPackageError, match="candidate media hash differs"):
        verify_baked_graphic_package(result.project_root)
