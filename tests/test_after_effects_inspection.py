from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from vera_timeline_agent.after_effects_inspection import (
    AfterEffectsInspectionError,
    inspect_after_effects_project,
)


def _project_bytes() -> bytes:
    return b"".join(
        (
            b"RIFX\x00\x00\x00\x00",
            b"EV23 lower third 2-2-24\x00",
            b"Main Text\x00Sub-Text\x00Country\x00year\x00",
            b"country\x00full circle\x00circle text\x00override\x00",
            b"Albania|Luxembourg|Otis / Custom (w full)\x00",
            b"ADBE Checkbox Control\x00ADBE Slider Control\x00",
            b'fontEditValue":"FranklinGothicLTPro-DmCm"\x00',
            b'fontEditValue":"FranklinGothicLTPro-BkXCm"\x00',
            b"// Ease and Wizz 2.0.6 : inOutExpo : All keyframes\x00",
            b'thisComp.layer("controller").effect("country")("Menu")\x00',
            b"ESC-HEART-LUXEMBOURG-BLACK.png\x00Luxembourg.png\x00Matt-Belinkie.jpg\x00",
            b"ADBE Vector Trim Start\x00ADBE Vector Trim End\x00",
        )
    )


def test_inspection_reports_semantic_controls_and_explicit_limits(
    tmp_path: Path,
) -> None:
    project = tmp_path / "lower-third.aep"
    contents = _project_bytes()
    project.write_bytes(contents)

    report = inspect_after_effects_project(project)

    assert report["source"]["sha256"] == hashlib.sha256(contents).hexdigest()
    assert report["compositions"] == ["EV23 lower third 2-2-24"]
    assert report["relevant_layers"][0]["source_name"] == "controller"
    assert {control["semantic_id"] for control in report["semantic_controls"]} >= {
        "primary_text",
        "secondary_text",
        "country_identity",
        "year_label",
        "icon_style",
        "country_name_override_enabled",
        "custom_identity_media",
    }
    assert report["dropdowns"][0]["option_count"] == 3
    assert report["expressions"][0]["easing"] == "ease_and_wizz_in_out_expo"
    assert report["footage"] == [
        "ESC-HEART-LUXEMBOURG-BLACK.png",
        "Luxembourg.png",
        "Matt-Belinkie.jpg",
    ]
    assert any("exact keyframe times" in value for value in report["limitations"])
    assert any("protected timing regions" in value for value in report["limitations"])


def test_inspection_rejects_non_aep_riff_input(tmp_path: Path) -> None:
    project = tmp_path / "not-a-project.aep"
    project.write_bytes(b"RIFF\x00\x00\x00\x00not an After Effects project")

    with pytest.raises(AfterEffectsInspectionError, match="RIFX"):
        inspect_after_effects_project(project)
