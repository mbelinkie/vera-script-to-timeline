"""Real pure Node requirements precede #174; source/path guards are explicit."""

import json
import os
import subprocess
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest
from test_issue603_still_preparation import _descriptor
from vera_timeline_agent import prep_media_inputs
from vera_timeline_agent.build_compile_stage import CompileStagePort
from vera_timeline_agent.build_compiler_bridge import invoke_bridge
from vera_timeline_agent.build_composition import EffectState, FrozenBuildSnapshot
from vera_timeline_agent.build_jobs import BuildJobError, NeedsAction, StageContext
from vera_timeline_agent.build_media_stage import (
    MediaStageAuthorization,
    MediaStagePort,
)
from vera_timeline_agent.build_package_stage import PackageStagePort
from vera_timeline_agent.build_stage_receipt import canonical_json
from vera_timeline_agent.local_media_import import FFmpegDecoder
from vera_timeline_agent.media_preparation import (
    MediaPreparationError,
    MediaTools,
    PreparationAuthorization,
)
from vera_timeline_agent.narration.models import identity_hash
from vera_timeline_agent.v2_package import _compiler_hash

from scripts.issue336_studio_qualify import png

ROOT = Path(__file__).parent / "data/authoring_v2/issue_173/compiler"


@pytest.fixture
def fixture_inputs(tmp_path: Path) -> tuple[Path, Path]:
    data = json.loads((ROOT / "selected-clip-ntsc.input.golden.json").read_bytes())
    document, dependencies = tmp_path / "document.json", tmp_path / "dependencies.json"
    document.write_text(json.dumps(data["document"]))
    dependencies.write_text(json.dumps(data["dependencies"]))
    return document, dependencies


def test_pure_media_requirements_before_preparation(
    fixture_inputs: tuple[Path, Path],
) -> None:
    doc, deps = fixture_inputs
    result = invoke_bridge("needs", doc, deps)
    assert result.needs["ok"] is True
    assert result.document_sha256 and result.dependencies_sha256
    assert result.needs["requirements"][0]["requirementKey"] == "prep:occurrence-1"
    assert result.needs["requirements"][0]["sourceSufficiency"] == "sufficient"
    assert result.needs["requirements"][0]["requestedRange"]["duration"] == {
        "denominator": 1,
        "numerator": 10,
    }


def test_requirements_refuse_stale_range_and_conflicting_occurrence(
    fixture_inputs: tuple[Path, Path],
) -> None:
    doc, deps = fixture_inputs
    value = json.loads(deps.read_bytes())
    value["occurrenceResolutions"][0]["logicalSourceBounds"]["endFrame"] = 1
    deps.write_text(json.dumps(value))
    with pytest.raises(BuildJobError, match="v2 needs refused"):
        invoke_bridge("needs", doc, deps)


def test_stage_req_matching_refuses_duplicate_conflict_and_missing_source() -> None:
    row = dict(
        requirementKey="prep:x",
        mediaReferenceId="asset",
        sourceSufficiency="sufficient",
        requestedRange={"sourceInFrame": 0},
        occurrenceKey="occ:1",
    )
    descriptor = {"preparedMediaRequirementKey": "prep:x", "mediaReferenceId": "asset"}
    assert len(MediaStagePort._reqs({"requirements": [row, row]}, [descriptor])) == 1
    with pytest.raises(BuildJobError, match="conflicting repeated"):
        MediaStagePort._reqs(
            {"requirements": [row, {**row, "occurrenceKey": "occ:2"}]}, [descriptor]
        )
    with pytest.raises(BuildJobError, match="one frozen source"):
        MediaStagePort._reqs({"requirements": [row]}, [])


@pytest.mark.slow
@pytest.mark.parametrize(
    ("suffix", "prior_key"),
    [(".png", None), (".png", "sha256:" + "1" * 64), (".jpg", None)],
)
def test_frozen_still_preparation_and_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str, prior_key: str | None
) -> None:
    fixture = json.loads(
        (ROOT / "visual-only-image-still-25fps-default.input.golden.json").read_bytes()
    )
    deps = fixture["dependencies"]
    original = deps["occurrenceResolutions"][0]
    source = tmp_path / "source.png"
    png(source, 32, 24)
    tools = MediaTools()
    if suffix == ".jpg":
        jpeg = source.with_suffix(suffix)
        subprocess.run(
            [
                tools.ffmpeg,
                "-v",
                "error",
                "-i",
                str(source),
                "-frames:v",
                "1",
                str(jpeg),
            ],
            check=True,
        )
        source = jpeg
        authored = fixture["document"]
        authored["activeDraft"]["blocks"][0]["payload"].pop("framingPolicy")
        authored.pop("liveContentHash")
        authored["liveContentHash"] = deps["document"]["contentHash"] = _compiler_hash(
            authored
        )
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        facts = FFmpegDecoder(ffprobe=tools.ffprobe, ffmpeg=tools.ffmpeg).decode(
            fd, "image"
        )
    finally:
        os.close(fd)
    descriptor = _descriptor(source, facts, Fraction(25))
    descriptor.update(
        payloadId=original["payloadId"],
        owner=original["owner"],
        mediaReferenceId=original["mediaReferenceId"],
    )
    descriptor["preparedMediaRequirementKey"] = prior_key
    deps["occurrenceResolutions"] = [descriptor]
    deps["preparedMedia"] = []
    document = tmp_path / "document.json"
    dependencies = tmp_path / "dependencies.json"
    document.write_text(json.dumps(fixture["document"]))
    dependencies.write_text(json.dumps(deps))
    output = tmp_path / "output"
    output.mkdir()
    timing = output / "job" / "generating_speech" / "timing-maps.json"
    timing.parent.mkdir(parents=True)
    timing.write_text("[]")
    snapshot = FrozenBuildSnapshot(
        "snap",
        b"",
        "project",
        "studio",
        deps["build"]["buildId"],
        "test",
        "rev",
        0,
        "head",
        "settings",
        {
            "document": document,
            "dependencies": dependencies,
            f"source:{descriptor['mediaReferenceId']}": source,
        },
        {},
        {},
        output,
    )
    context = StageContext(
        "project",
        "job",
        "snap",
        "resolving_media",
        "stage",
        output,
        1,
        1,
        lambda _: None,
        lambda: None,
    )
    auth = PreparationAuthorization(
        "frozen",
        (tmp_path,),
        output,
        identity_hash(tools.fingerprint()),
        minimum_free_bytes=0,
    )
    port = MediaStagePort(
        MediaStageAuthorization("project", "snap", auth, {}), tools=tools
    )
    monkeypatch.setattr(prep_media_inputs, "_qualified_tools", lambda _: None)
    port.execute(context, snapshot)
    assert port.inspect(context, snapshot).state == EffectState.VERIFIED
    compiled = CompileStagePort()._checked_compile(context, snapshot)
    assert compiled.result["report"]["status"] == "ready"
    CompileStagePort().execute(context, snapshot)
    package = PackageStagePort()
    media = package._media(context, snapshot, package._preparations(context, snapshot))
    (compiled_source,) = compiled.result["manifest"]["sources"]
    source_id = compiled_source["id"]
    assert media[f"original:{source_id}"] == source
    delivered = media[f"source:{source_id}"]
    assert delivered.suffix == ".png"
    if suffix == ".jpg":
        assert delivered.is_relative_to(output)
        assert compiled_source["deliveredHash"] != compiled_source["originalHash"]
        packaging = replace(context, stage="writing_interchange")
        package.execute(packaging, snapshot)
        assert package.inspect(packaging, snapshot).state == EffectState.VERIFIED
    else:
        assert delivered == source
    paths = port.paths(context, snapshot)
    result = json.loads(paths["dependencies"].read_bytes())
    assert result["timeline"]["durationFrames"] == 75
    if prior_key is not None:
        prepared_bytes = paths["dependencies"].read_bytes()
        legacy = json.loads(prepared_bytes)
        legacy["timeline"]["durationFrames"] = deps["timeline"]["durationFrames"]
        paths["dependencies"].write_bytes(canonical_json(legacy))
        assert port.inspect(context, snapshot).state == EffectState.VERIFIED
        paths["dependencies"].write_bytes(prepared_bytes)
    key = result["occurrenceResolutions"][0]["preparedMediaRequirementKey"]
    assert result["preparedMedia"][0]["requirementKey"] == key
    assert (
        json.loads(paths["needsInput"].read_bytes())["occurrenceResolutions"][0][
            "preparedMediaRequirementKey"
        ]
        == prior_key
    )
    receipt = Path(json.loads(paths["preparations"].read_bytes())[key])
    original_bytes = source.read_bytes()
    source.write_bytes(b"changed")
    with pytest.raises(MediaPreparationError):
        port.inspect(context, snapshot)
    source.write_bytes(original_bytes)
    receipt.unlink()
    with pytest.raises(MediaPreparationError, match="missing_receipt"):
        port.inspect(context, snapshot)
    assert not receipt.exists()
    unauthorized = PreparationAuthorization(
        "frozen",
        (output,),
        output,
        identity_hash(tools.fingerprint()),
        minimum_free_bytes=0,
    )
    refused = MediaStagePort(
        MediaStageAuthorization("project", "snap", unauthorized, {}), tools=tools
    )
    with pytest.raises(NeedsAction, match="excludes frozen source"):
        refused.inspect(context, snapshot)


@pytest.mark.parametrize("rate", [25, 30])
def test_qualified_geometry_retains_real_rational_rate(rate: int) -> None:
    from fractions import Fraction

    from vera_timeline_agent.media_preparation import preparation_geometry

    geo = preparation_geometry(
        source_rate=Fraction(rate),
        target_rate=Fraction(24000, 1001),
        origin_frame=0,
        lower_frame=0,
        upper_frame=rate * 11,
        in_frame=0,
        duration=Fraction(10),
    )
    assert geo.frame_count == 240
    assert geo.selected_package_frame(239) < rate * 10
