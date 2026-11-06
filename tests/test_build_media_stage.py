"""Real pure Node requirements precede #174; source/path guards are explicit."""

import json
from pathlib import Path

import pytest
from vera_timeline_agent.build_compiler_bridge import invoke_bridge
from vera_timeline_agent.build_jobs import BuildJobError
from vera_timeline_agent.build_media_stage import MediaStagePort

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
