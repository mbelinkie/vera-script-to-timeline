from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from vera_timeline_agent.studio_graphics import (
    StudioGraphicError,
    _strict_controls,
    build_studio_graphic_package,
    graphic_controls,
    validate_graphics,
    verify_studio_graphic_package,
)

DATA = Path(__file__).parent / "data/issue_7"


def manifest() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((DATA / "otis.studio.manifest.golden.json").read_text()),
    )


def test_semantic_mapping_preserves_null_autofill_and_omits_otis_year() -> None:
    values = {
        "country": "otis",
        "topLineOverride": None,
        "bottomLineOverride": None,
        "badgeOverrideAssetId": None,
    }
    assert graphic_controls(values) == {"Country": 53, "TopLine": "", "BottomLine": ""}
    assert "Year" not in graphic_controls(values)
    assert graphic_controls(
        {**values, "country": "finland", "year": 2024, "topLineOverride": "The Code"}
    ) == {"Country": 16, "Year": 2024, "TopLine": "The Code", "BottomLine": ""}


@pytest.mark.parametrize("value", ["asset_custom", "/private/tmp/badge.png"])
def test_custom_badge_fails_before_any_occurrence_is_placed(value: str) -> None:
    values = {
        "country": "otis",
        "topLineOverride": None,
        "bottomLineOverride": None,
        "badgeOverrideAssetId": value,
    }
    with pytest.raises(StudioGraphicError, match="BADGE_OVERRIDE_DEFERRED"):
        graphic_controls(values)


def test_snapshot_hash_and_v4_minimum_are_independently_verified() -> None:
    original = manifest()
    validate_graphics(original)
    cases: list[tuple[Callable[[dict[str, Any]], Any], str]] = [
        (
            lambda m: m["events"][0]["semanticSnapshot"]["values"].update(
                country="finland"
            ),
            "snapshot",
        ),
        (lambda m: m["events"][0]["recordRange"].update(durationFrames=63), "64"),
        (lambda m: m["events"][0].update(trackId="video-3"), "V4"),
        (
            lambda m: m["sources"][1].update(entryAssetHash="sha256:" + "0" * 64),
            "template",
        ),
    ]
    for mutate, message in cases:
        changed = copy.deepcopy(original)
        mutate(changed)
        with pytest.raises(StudioGraphicError, match=message):
            validate_graphics(changed)


class Control:
    def __init__(self, name: str, datatype: str) -> None:
        self.name = name
        self.datatype = datatype

    def GetAttrs(self, attribute: str) -> str:
        return self.name if attribute == "INPS_ID" else self.datatype


class Root:
    def __init__(self) -> None:
        self.inputs = {
            index: Control(name, datatype)
            for index, (name, datatype) in enumerate(
                [
                    ("Country", "Number"),
                    ("Year", "Number"),
                    ("TopLine", "Text"),
                    ("BottomLine", "Text"),
                    ("BadgeOverride", "Clip"),
                ]
            )
        }

    def GetInputList(self) -> dict[int, Control]:
        return self.inputs


@pytest.mark.parametrize("failure", ["missing", "renamed", "duplicated", "type"])
def test_trusted_controls_never_fall_back_to_similar_controls(failure: str) -> None:
    root = Root()
    _strict_controls(root)
    if failure == "missing":
        del root.inputs[0]
    elif failure == "renamed":
        root.inputs[0].name = "Country2"
    elif failure == "duplicated":
        root.inputs[10] = Control("Country", "Number")
    else:
        root.inputs[0].datatype = "Text"
    with pytest.raises(StudioGraphicError, match="trusted control Country"):
        _strict_controls(root)


@pytest.fixture(scope="module")
def inputs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("studio-graphic-compiled")
    environment = {**os.environ, "VERA_ISSUE8_INPUTS": str(directory)}
    result = subprocess.run(
        [
            "npm",
            "run",
            "test",
            "--workspace",
            "@vera/contracts",
            "--",
            "test/studio-graphics-inputs.test.ts",
        ],
        cwd=DATA.parents[2],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        pytest.fail(result.stdout + result.stderr)
    return directory


@pytest.mark.slow
@pytest.mark.parametrize(
    "case",
    [
        "standard-64",
        "standard-120",
        "overrides-64",
        "overrides-120",
        "otis-64",
        "otis-120",
        "revised-120",
    ],
)
def test_package_retains_exact_compiler_bytes_and_registered_assets(
    inputs: Path,
    tmp_path: Path,
    case: str,
) -> None:
    folder = inputs / case
    package = build_studio_graphic_package(
        folder / "timeline-manifest.json",
        folder / "build-report.json",
        folder / "materialization-plan.json",
        inputs / "registered-template",
        tmp_path / "package",
    )
    for name in ("timeline-manifest.json", "build-report.json"):
        assert (package.root / name).read_bytes() == (folder / name).read_bytes()
    graphic = package.manifest["events"][0]
    assert graphic["kind"] == "fusion_graphic"
    assert graphic["recordRange"]["durationFrames"] == int(case.split("-")[-1])
    assert graphic["trackId"] == "video-4"
    assert verify_studio_graphic_package(package.root).manifest == package.manifest
    assert "year" in graphic["semanticSnapshot"]["values"] or case.startswith("otis")


@pytest.mark.slow
@pytest.mark.parametrize(
    "failure", ["missing", "mismatched", "extra", "semantic", "transport"]
)
def test_tampered_package_cannot_reach_the_application(
    inputs: Path,
    tmp_path: Path,
    failure: str,
) -> None:
    folder = inputs / "standard-64"
    root = tmp_path / "package"
    build_studio_graphic_package(
        folder / "timeline-manifest.json",
        folder / "build-report.json",
        folder / "materialization-plan.json",
        inputs / "registered-template",
        root,
    )
    atlas = root / "Templates/Edit/Titles/Eurovision/ev24_badges_atlas.png"
    if failure == "missing":
        atlas.unlink()
    elif failure == "mismatched":
        atlas.write_bytes(b"wrong badge")
    elif failure == "extra":
        (root / "other.setting").write_text("untrusted")
    elif failure == "semantic":
        path = root / "timeline-manifest.json"
        path.write_bytes(path.read_bytes().replace(b'"finland"', b'"sweden"'))
    else:
        receipt = next((root / "Transport/Builds").glob("*/package-verification.json"))
        receipt.write_bytes(b"{}\n")
    with pytest.raises((RuntimeError, ValueError)):
        verify_studio_graphic_package(root)


@pytest.mark.slow
def test_deferred_badge_is_rejected_before_publishing_any_output(
    inputs: Path,
    tmp_path: Path,
) -> None:
    from vera_timeline_agent.resolve_import_package.package import _canonical_json
    from vera_timeline_agent.studio_graphics import _hash

    folder = tmp_path / "inputs"
    shutil.copytree(inputs / "standard-64", folder)
    path = folder / "timeline-manifest.json"
    data = json.loads(path.read_text())
    data["events"][0]["semanticSnapshot"]["values"]["badgeOverrideAssetId"] = (
        "asset_custom"
    )
    data["events"][0]["semanticSnapshotHash"] = _hash(
        _canonical_json(data["events"][0]["semanticSnapshot"])
    )
    raw = _canonical_json(data)
    path.write_bytes(raw)
    report_path = folder / "build-report.json"
    report = json.loads(report_path.read_text())
    report["manifest"]["contentHash"] = _hash(raw)
    report_path.write_bytes(_canonical_json(report))
    with pytest.raises(StudioGraphicError, match="BADGE_OVERRIDE_DEFERRED"):
        build_studio_graphic_package(
            path,
            report_path,
            folder / "materialization-plan.json",
            inputs / "registered-template",
            tmp_path / "output",
        )
    assert not (tmp_path / "output").exists()


def test_free_compiler_plan_fails_before_materialization(tmp_path: Path) -> None:
    with pytest.raises(StudioGraphicError, match="live Studio"):
        build_studio_graphic_package(
            DATA / "normal.free.manifest.golden.json",
            DATA / "normal.free.report.golden.json",
            tmp_path / "missing-media-plan.json",
            tmp_path / "missing-template",
            tmp_path / "output",
        )
    assert not (tmp_path / "output").exists()


@pytest.mark.slow
def test_independently_valid_transport_must_match_original_compiler_occurrences(
    inputs: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vera_timeline_agent.studio_graphics as module

    folder = inputs / "standard-64"
    root = tmp_path / "package"
    build_studio_graphic_package(
        folder / "timeline-manifest.json",
        folder / "build-report.json",
        folder / "materialization-plan.json",
        inputs / "registered-template",
        root,
    )
    original = module.transport_artifacts

    def changed(
        manifest: dict[str, Any], report: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        media, result = original(manifest, report)
        media["events"][0]["recordRange"]["durationFrames"] += 1
        return media, result

    monkeypatch.setattr(module, "transport_artifacts", changed)
    with pytest.raises(StudioGraphicError, match="internal transport differs"):
        verify_studio_graphic_package(root)
