"""Read-only evidence extraction for an After Effects project binary.

This is deliberately an inspector, not an AEP converter.  It reads the
project bytes without opening or rewriting the source and reports only facts
whose evidence is present in the serialized project.  It does not claim to
evaluate expressions, render frames, or decode opaque keyframe timing.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any


class AfterEffectsInspectionError(ValueError):
    """Raised when the requested source is not a readable AEP project."""


_COMPOSITION_PATTERN = re.compile(r"\b[^\x00]{0,80}\blower third[^\x00]{0,80}\b", re.I)
_FONT_PATTERN = re.compile(r'fontEditValue\\?"\s*:\s*\\?"([^"\\]+)')
_MEDIA_PATTERN = re.compile(r"\b[^\x00/\\]{1,120}\.(?:png|jpe?g)\b", re.I)


def inspect_after_effects_project(
    project: Path, *, collection_report: Path | None = None
) -> dict[str, Any]:
    """Return structured, read-only evidence from one big-endian AEP binary."""
    data = project.read_bytes()
    if data[:4] != b"RIFX":
        raise AfterEffectsInspectionError(
            "expected a big-endian After Effects RIFX project; no inspection ran"
        )
    text = data.decode("latin-1")
    report: dict[str, Any] = {
        "schema_version": "vera-after-effects-inspection-v1",
        "source": {
            "file_name": project.name,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "format": "After Effects big-endian RIFX project",
            "access": "read-only",
        },
        "compositions": _compositions(text),
        "relevant_layers": _relevant_layers(text),
        "source_controls": _source_controls(text),
        "semantic_controls": _semantic_controls(text),
        "dropdowns": _dropdowns(text),
        "expressions": _expressions(text),
        "keyframes_and_easing": _keyframes_and_easing(data, text),
        "fonts": sorted(set(_FONT_PATTERN.findall(text))),
        "footage": sorted(set(_MEDIA_PATTERN.findall(text))),
        "effects": _present(
            text,
            {
                "checkbox_control": "ADBE Checkbox Control",
                "color_control": "ADBE Color Control",
                "layer_control": "ADBE Layer Control",
                "set_matte": "ADBE Set Matte3",
                "slider_control": "ADBE Slider Control",
                "stroke": "ADBE Stroke",
                "tint": "ADBE Tint",
            },
        ),
        "protected_timing_regions": {
            "status": "not_extractable_from_binary_strings",
            "evidence": [],
            "required_manual_check": "Identify protected holds and transition "
            "boundaries from a producer-supervised reference render.",
        },
        "limitations": [
            "This inspector does not evaluate After Effects expressions.",
            "This inspector cannot decode exact keyframe times, values, or "
            "interpolation from opaque AEP records.",
            "This inspector cannot establish protected timing regions without a "
            "reference render or an After Effects scripting export.",
            "This inspector does not render, open, modify, move, or copy source "
            "materials.",
        ],
    }
    if collection_report is not None:
        report["collection_report"] = _collection_report_summary(collection_report)
    return report


def _compositions(text: str) -> list[str]:
    values = []
    for value in _COMPOSITION_PATTERN.findall(text):
        cleaned = value.strip().replace("Utf8", "").strip()
        if cleaned and cleaned not in values:
            values.append(cleaned)
    return values


def _source_controls(text: str) -> list[dict[str, str]]:
    controls = {
        "Main Text": "text",
        "Sub-Text": "text",
        "Country": "dropdown",
        "year": "text",
        "circle text": "boolean",
        "full circle": "boolean",
        "override": "boolean",
        "override text": "text",
        "color": "color",
        "textshift1": "number",
        "boxheight1": "number",
        "boxshift1": "number",
        "textshift2": "number",
        "boxheight2": "number",
        "boxshift2": "number",
        "finetune": "number",
    }
    return [
        {"source_name": name, "source_type": kind}
        for name, kind in controls.items()
        if name in text
    ]


def _relevant_layers(text: str) -> list[dict[str, str]]:
    layers = {
        "controller": "Holds source controls and drives country/icon expressions.",
        "Main Text": "Primary editable text layer.",
        "Sub-Text": "Secondary editable text layer.",
        "COUNTRY 2022": "Country label driven by the country/year/override expression.",
        "year": "Editable year text layer.",
        "override": "Editable override text layer.",
        "Circle Motion": "Shape-layer motion treatment.",
    }
    return [
        {"source_name": name, "role": role}
        for name, role in layers.items()
        if name in text
    ]


def _semantic_controls(text: str) -> list[dict[str, str]]:
    candidates = (
        ("Main Text", "primary_text", "text", "Required primary label."),
        ("Sub-Text", "secondary_text", "text", "Optional supporting label."),
        (
            "Country",
            "country_identity",
            "choice",
            "Country or approved custom identity.",
        ),
        ("year", "year_label", "text", "Year shown with the country identity."),
        (
            "circle text",
            "country_name_in_icon_enabled",
            "boolean",
            "Whether country-name text appears in the icon treatment.",
        ),
        (
            "full circle",
            "icon_style",
            "choice",
            "Heart-flag versus full-circle treatment; producer must confirm labels.",
        ),
        (
            "override",
            "country_name_override_enabled",
            "boolean",
            "Use an explicit country-name override instead of the selected "
            "country label.",
        ),
        (
            "override text",
            "country_name_override",
            "text",
            "Explicit country-name override when enabled.",
        ),
    )
    return [
        {
            "source_name": source_name,
            "semantic_id": semantic_id,
            "type": kind,
            "meaning": meaning,
        }
        for source_name, semantic_id, kind, meaning in candidates
        if source_name in text
    ]


def _dropdowns(text: str) -> list[dict[str, Any]]:
    match = re.search(
        r"(Albania(?:\|[A-Za-z /()\-]+)*\|Otis / Custom \(w full\))", text
    )
    if match is None:
        return []
    options = match.group(1).split("|")
    return [
        {
            "source_name": "Country",
            "semantic_id": "country_identity",
            "option_count": len(options),
            "options": options,
            "index_independent_requirement": "Persist a stable semantic value, never "
            "the After Effects dropdown index.",
        }
    ]


def _expressions(text: str) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    if "Ease and Wizz 2.0.6 : inOutExpo" in text:
        values.append(
            {
                "easing": "ease_and_wizz_in_out_expo",
                "source": "Ease and Wizz 2.0.6",
                "evidence": "inOutExpo expression text is serialized in the project",
            }
        )
    if 'effect("country")("Menu")' in text:
        values.append(
            {
                "easing": "none",
                "source": "country-layer-selector",
                "evidence": "expression selects layers from country and full-circle "
                "controls",
            }
        )
    return values


def _keyframes_and_easing(data: bytes, text: str) -> dict[str, Any]:
    animated_surfaces = [
        name
        for name in (
            "ADBE Vector Trim Start",
            "ADBE Vector Trim End",
            "ADBE Scale",
            "ADBE Opacity",
        )
        if name in text
    ]
    return {
        "keyframe_records_detected": b"listlhd3" in data,
        "animated_surfaces_detected": animated_surfaces,
        "exact_times_values_and_interpolation": "not_extractable",
        "easing_evidence": "See expressions; inOutExpo is present when reported.",
    }


def _present(text: str, candidates: dict[str, str]) -> list[str]:
    return [name for name, marker in candidates.items() if marker in text]


def _collection_report_summary(path: Path) -> dict[str, Any]:
    report_text = path.read_text(encoding="utf-8", errors="replace")
    count_match = re.search(r"Number of collected files:\s*(\d+)", report_text)
    fonts = re.findall(r"Font family: “([^”]+)”", report_text)
    effects = re.findall(r"^Effect:\s+(.+?)\s*$", report_text, re.MULTILINE)
    return {
        "file_name": path.name,
        "collected_file_count": int(count_match.group(1)) if count_match else None,
        "declared_fonts": sorted(set(fonts)),
        "declared_effects": sorted(set(effects)),
    }


def iter_semantic_ids(report: dict[str, Any]) -> Iterable[str]:
    """Expose semantic IDs for migration-brief validation without AEP paths."""
    for control in report["semantic_controls"]:
        yield str(control["semantic_id"])
