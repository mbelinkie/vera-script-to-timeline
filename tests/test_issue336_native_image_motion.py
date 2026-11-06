"""Pure qualification tests: synthetic proofs are NOT native Resolve evidence."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.native_image_motion import (
    MotionBinding,
    MotionRefusal,
    Qualification,
    admit_motion,
    motion_hash,
    native_effect_records,
    production_qualification,
)

from scripts.issue336_studio_qualify import png

H = "sha256:" + "a" * 64
P = "sha256:" + "b" * 64
MOTION = {
    "mode": "native_dynamic_zoom",
    "start": {"focusX": 0.5, "focusY": 0.5, "scale": 1.25},
    "end": {"focusX": 0.53, "focusY": 0.52, "scale": 1.2},
    "easing": "linear",
}
BINDING = MotionBinding(
    source_hash=H,
    original_hash=H,
    source_probe_hash=H,
    delivered_probe_hash=H,
    compiler_profile_hash=P,
    preparation_profile_hash=P,
    tool_hash=P,
    settings_hash=P,
    preparation_binding_hash=P,
    record_start=0,
    record_end=48,
    source_start=0,
    source_end=1,
    timeline_width=1280,
    timeline_height=720,
)
PROOF = Qualification(
    edition="studio",
    version="21.1.1.10",
    route="native_otio",
    binding=BINDING,
    motion_hash=motion_hash(MOTION),
    framing="cover",
    background="#000000",
    source_width=1920,
    source_height=1080,
    focus_proven=True,
    native_start_center=(0.0, 0.0),
    native_end_center=(0.03, -0.02),
    native_start_scale=0.8,
    native_end_scale=1 / 1.2,
)


def test_runtime_has_no_unearned_production_qualification() -> None:
    assert production_qualification(MOTION, BINDING, "cover") is None
    with pytest.raises(MotionRefusal, match="no qualified output"):
        admit_motion(MOTION, BINDING, None, framing="cover")


def _verified_png_case(
    tmp_path: Path, width: int, height: int, frames: int
) -> tuple[Path, MotionBinding, dict[str, Any]]:
    source = tmp_path / f"public-{width}x{height}.png"
    png(source, width, height)
    digest = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
    binding = replace(
        BINDING,
        source_hash=digest,
        original_hash=digest,
        timeline_width=1920,
        timeline_height=1080,
        record_end=frames,
    )
    probe = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "png",
                "width": width,
                "height": height,
            }
        ],
        "frames": [{"pts": 0}],
    }
    return source, binding, probe


@pytest.mark.parametrize("frames", [24, 48, 96, 144])
def test_bounded_verified_png_has_reusable_real_source_bound_proof(
    tmp_path: Path, frames: int
) -> None:
    source, binding, probe = _verified_png_case(tmp_path, 1600, 900, frames)
    proof = production_qualification(
        MOTION,
        binding,
        "cover",
        verified_asset=source,
        delivered_probe=probe,
        frame_rate=(24, 1),
    )
    assert proof is not None
    assert proof.binding == binding
    assert (proof.source_width, proof.source_height) == (1600, 900)
    assert admit_motion(MOTION, binding, proof, framing="cover") == proof
    assert len(native_effect_records(MOTION, proof)) == 2


def test_verified_png_none_supports_measured_static_contain(
    tmp_path: Path,
) -> None:
    source, binding, probe = _verified_png_case(tmp_path, 1000, 1000, 48)
    motion = {"mode": "none"}
    proof = production_qualification(
        motion,
        binding,
        "contain",
        verified_asset=source,
        delivered_probe=probe,
        frame_rate=(24, 1),
    )
    assert proof is not None
    assert admit_motion(motion, binding, proof, framing="contain") == proof
    assert native_effect_records(motion, proof)[0]["Enabled"] is False


@pytest.mark.parametrize(
    "change",
    [
        "wrong-rate",
        "wrong-resolution",
        "unmeasured-duration",
        "unmeasured-framing",
        "unmeasured-easing",
        "different-probe",
        "stale-source-bytes",
        "derived-source",
        "unmeasured-resolution",
    ],
)
def test_unqualified_png_profile_source_and_motion_remain_fail_closed(
    tmp_path: Path, change: str
) -> None:
    source, binding, probe = _verified_png_case(tmp_path, 1600, 900, 48)
    motion = dict(MOTION)
    framing = "cover"
    frame_rate = (24, 1)
    if change == "wrong-rate":
        frame_rate = (25, 1)
    elif change == "wrong-resolution":
        binding = replace(binding, timeline_width=1280)
    elif change == "unmeasured-duration":
        binding = replace(binding, record_end=72)
    elif change == "unmeasured-framing":
        framing = "contain"
    elif change == "unmeasured-easing":
        motion["easing"] = "ease_in"
    elif change == "different-probe":
        probe["streams"][0]["width"] = 1000
    elif change == "stale-source-bytes":
        source.write_bytes(source.read_bytes() + b"tampered")
    elif change == "derived-source":
        binding = replace(binding, original_hash=P)
    elif change == "unmeasured-resolution":
        source, binding, probe = _verified_png_case(tmp_path, 800, 450, 48)
    assert (
        production_qualification(
            motion,
            binding,
            framing,
            verified_asset=source,
            delivered_probe=probe,
            frame_rate=frame_rate,
        )
        is None
    )


def test_synthetic_qualified_dynamic_metadata_is_exact_and_duration_independent() -> (
    None
):
    assert admit_motion(MOTION, BINDING, PROOF, framing="cover") == PROOF
    effects = native_effect_records(MOTION, PROOF)
    assert [item["Type"] for item in effects] == [59, 22]
    assert effects[0]["Parameters"][0]["Key Frames"] == {
        "-86400": {"Value": [0.0, 0.0], "Variant Type": "POINTF"},
        "-85400": {"Value": [0.03, -0.02], "Variant Type": "POINTF"},
    }
    assert effects[0]["Parameters"][1]["Key Frames"] == {
        "-86400": {"Value": 0.8, "Variant Type": "Double"},
        "-85400": {"Value": 1 / 1.2, "Variant Type": "Double"},
    }
    assert effects[1]["Parameters"][0]["Parameter Value"] == 3
    # Same literal key labels at another *independently qualified* rebuilt length.
    longer = replace(BINDING, record_end=144)
    assert (
        native_effect_records(
            MOTION,
            admit_motion(
                MOTION, longer, replace(PROOF, binding=longer), framing="cover"
            ),
        )
        == effects
    )


def test_explicit_none_is_not_a_fake_dynamic_request() -> None:
    none = {"mode": "none"}
    proof = replace(
        PROOF,
        motion_hash=motion_hash(none),
        focus_proven=False,
        native_start_center=None,
        native_end_center=None,
        native_start_scale=None,
        native_end_scale=None,
    )
    assert admit_motion(none, BINDING, proof, framing="cover") == proof
    effects = native_effect_records(none, proof)
    assert effects[0]["Enabled"] is False
    assert effects[0]["Parameters"][1]["Key Frames"]["-86400"]["Value"] == 0.8


@pytest.mark.parametrize(
    "change",
    [
        {"source_hash": P},
        {"original_hash": P},
        {"source_probe_hash": P},
        {"delivered_probe_hash": P},
        {"compiler_profile_hash": H},
        {"preparation_profile_hash": H},
        {"tool_hash": H},
        {"settings_hash": H},
        {"preparation_binding_hash": H},
        {"record_end": 47},
        {"record_end": 0},
        {"source_end": 2},
        {"timeline_width": 1920},
    ],
)
def test_stale_bytes_profile_duration_or_extent_refuses(change: dict[str, Any]) -> None:
    with pytest.raises(MotionRefusal):
        admit_motion(MOTION, replace(BINDING, **change), PROOF, framing="cover")


@pytest.mark.parametrize(
    "overrides",
    [
        {"edition": "free"},
        {"version": "21.1.1.9"},
        {"route": "manual"},
        {"framing": "contain"},
        {"background": "#204080"},
    ],
)
def test_unqualified_runtime_and_background_refuse(overrides: dict[str, Any]) -> None:
    with pytest.raises(MotionRefusal):
        admit_motion(MOTION, BINDING, PROOF, **{"framing": "cover", **overrides})


@pytest.mark.parametrize(
    "motion_request",
    [
        {**MOTION, "easing": "ease_in"},
        {**MOTION, "end": {"focusX": 0.7, "focusY": 0.35, "scale": 1.1}},
        {**MOTION, "end": {"focusX": 0.65, "focusY": 0.35, "scale": 100.0}},
        {"mode": "none"},
    ],
)
def test_unqualified_setting_change_refuses(motion_request: dict[str, Any]) -> None:
    with pytest.raises(MotionRefusal):
        admit_motion(motion_request, BINDING, PROOF, framing="cover")


@pytest.mark.parametrize(
    "proof_change",
    [
        {"focus_proven": False},
        {"native_end_center": (180.0, -144.0)},
        {"native_end_center": (-0.02, -0.02)},
        {"native_end_center": (0.12, -0.08)},
        {"native_end_center": (0.03, -0.02), "native_end_scale": 1.05},
        {"native_start_scale": 0.5},
        {"native_end_scale": 1.08},
        {"native_end_scale": float("nan")},
        {"native_end_center": None},
        {"source_width": 0},
    ],
)
def test_unqualified_geometry_never_silently_clamps(
    proof_change: dict[str, Any],
) -> None:
    with pytest.raises(MotionRefusal):
        admit_motion(MOTION, BINDING, replace(PROOF, **proof_change), framing="cover")
