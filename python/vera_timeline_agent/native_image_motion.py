"""Fail-closed native Resolve image-motion admission and OTIO effect records.

The qualification is trusted runtime evidence, NEVER authored JSON. Phase 3
decoded 11 synthetic Studio timelines and measured a bounded source-to-pixel
mapping, but not a production source/profile attestation or contain matte.
Production geometry remains deliberately unqualified. Native key labels below
are opaque exported Resolve metadata, never timeline-frame coordinates.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any


class MotionRefusal(ValueError):
    """The requested native image effect has no exact verified output proof."""


@dataclass(frozen=True)
class MotionBinding:
    """Immutable identity read from independently verified compiler/media records."""

    source_hash: str
    original_hash: str
    source_probe_hash: str
    delivered_probe_hash: str
    compiler_profile_hash: str
    preparation_profile_hash: str
    tool_hash: str
    settings_hash: str
    preparation_binding_hash: str
    record_start: int
    record_end: int
    source_start: int
    source_end: int
    timeline_width: int
    timeline_height: int


@dataclass(frozen=True)
class Qualification:
    """One proven source, build configuration, motion and duration envelope.

    A proof must be produced by native output qualification, not by a script
    document or an import caller.  Pinned exact endpoints deliberately avoid
    pretending that the native center/scale mapping has been calibrated.
    """

    edition: str
    version: str
    route: str
    binding: MotionBinding
    motion_hash: str
    framing: str
    background: str
    source_width: int
    source_height: int
    focus_proven: bool = False
    native_start_center: tuple[float, float] | None = None
    native_end_center: tuple[float, float] | None = None
    native_start_scale: float | None = None
    native_end_scale: float | None = None


def motion_hash(motion: dict[str, Any]) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            (
                json.dumps(
                    motion, sort_keys=True, separators=(",", ":"), allow_nan=False
                )
                + "\n"
            ).encode()
        ).hexdigest()
    )


def qualification_hash(proof: Qualification) -> str:
    return motion_hash(asdict(proof))


def production_qualification(
    _motion: dict[str, Any], _binding: MotionBinding, _framing: str
) -> Qualification | None:
    """Measured raster geometry alone cannot authorize arbitrary source bytes."""
    return None


def native_endpoint_from_focus(
    frame: dict[str, Any],
) -> tuple[tuple[float, float], float]:
    """Candidate raw center/scale for a source-normalized point at frame center.

    #336's public Studio grid measured center X sign positive toward the left,
    center Y sign positive toward the bottom, and native scale reciprocal to
    the requested magnification. This *calculation* does not create trusted
    runtime proof: only ``admit_motion`` with independently obtained evidence
    may emit the effect. Do not clamp a request outside the tested raw range.
    """
    if not isinstance(frame, dict) or set(frame) != {"focusX", "focusY", "scale"}:
        raise MotionRefusal("focus endpoint requires exact normalized fields")
    if any(
        type(frame[key]) not in (int, float) or not math.isfinite(frame[key])
        for key in ("focusX", "focusY", "scale")
    ):
        raise MotionRefusal("focus endpoint has non-finite or invalid values")
    if not (0 <= frame["focusX"] <= 1 and 0 <= frame["focusY"] <= 1):
        raise MotionRefusal("focus outside normalized source")
    if frame["scale"] <= 0:
        raise MotionRefusal("zoom scale must be positive")
    center = (float(frame["focusX"] - 0.5), float(0.5 - frame["focusY"]))
    inverse_scale = 1.0 / frame["scale"]
    # These are the measured raw key endpoints, NOT a general pan allowance.
    # #325 observed that larger native centers could expose black; the three
    # #336 aspect-ratio renders only establish +X/negative-Y movement.
    epsilon = 1e-12
    if (
        not -epsilon <= center[0] <= 0.12 + epsilon
        or not -0.08 - epsilon <= center[1] <= epsilon
        or not 0.8 - epsilon <= inverse_scale <= 1.05 + epsilon
    ):
        raise MotionRefusal("requested focus/scale outside measured native envelope")
    return center, float(inverse_scale)


def native_projected_point(
    *,
    source_size: tuple[int, int],
    timeline_size: tuple[int, int],
    framing: str,
    source_point: tuple[float, float],
    center: tuple[float, float],
    native_scale: float,
) -> tuple[float, float]:
    """Predict source point in rendered pixels for the measured Studio route.

    On the 1280x720/24fps #336 render, native center X pans by *negative*
    fitted source width, center Y by *positive* fitted source height, both
    divided by raw native scale. Zoom scale itself is reciprocal to magnification.
    Fit uses the minimum aspect-preserving multiplier; fill uses the maximum.
    This is not a pixel renderer or a substitute for independent raster proof.
    """
    if (
        any(type(v) is not int or v <= 0 for v in (*source_size, *timeline_size))
        or framing not in {"contain", "cover"}
        or len(source_point) != 2
        or len(center) != 2
        or any(
            type(v) not in (int, float) or not math.isfinite(v)
            for v in (*source_point, *center, native_scale)
        )
        or native_scale <= 0
    ):
        raise MotionRefusal("invalid dimensions or native projection")
    source_width, source_height = source_size
    width, height = timeline_size
    factors = (width / source_width, height / source_height)
    multiplier = min(factors) if framing == "contain" else max(factors)
    fit_width = source_width * multiplier
    fit_height = source_height * multiplier
    source_x, source_y = source_point
    center_x, center_y = center
    return (
        width / 2 + (source_x - 0.5 - center_x) * fit_width / native_scale,
        height / 2 + (source_y - 0.5 + center_y) * fit_height / native_scale,
    )


def measured_framing_preserves_intent(
    *,
    source_size: tuple[int, int],
    timeline_size: tuple[int, int],
    framing: str,
    center: tuple[float, float],
    native_scale: float,
) -> bool:
    """Conservatively reject clipped contain or black-exposed cover endpoints.

    Every edge of a contain image must stay in-frame. Cover must extend past
    every frame edge; its intentional crop is a distinct authoring request.
    Linear interpolation of native center and raw scale makes projected corner
    coordinates fractional-linear in time, hence each axis is monotonic
    between two endpoints. Check both endpoints in the caller, never clamp.
    """
    a = native_projected_point(
        source_size=source_size,
        timeline_size=timeline_size,
        framing=framing,
        source_point=(0.0, 0.0),
        center=center,
        native_scale=native_scale,
    )
    b = native_projected_point(
        source_size=source_size,
        timeline_size=timeline_size,
        framing=framing,
        source_point=(1.0, 1.0),
        center=center,
        native_scale=native_scale,
    )
    width, height = timeline_size
    epsilon = 1e-6
    if framing == "contain":
        return (
            a[0] >= -epsilon
            and a[1] >= -epsilon
            and b[0] <= width + epsilon
            and b[1] <= height + epsilon
        )
    return (
        a[0] <= epsilon
        and a[1] <= epsilon
        and b[0] >= width - epsilon
        and b[1] >= height - epsilon
    )


def admit_motion(
    motion: dict[str, Any],
    binding: MotionBinding,
    proof: Qualification | None,
    *,
    framing: str,
    background: str = "#000000",
    edition: str = "studio",
    version: str = "21.1.1.10",
    route: str = "native_otio",
) -> Qualification:
    """Check all pinned source/profile/duration/effect inputs before any write."""
    if proof is None:
        raise MotionRefusal("native image geometry has no qualified output profile")
    if (
        (edition, version, route) != (proof.edition, proof.version, proof.route)
        or edition != "studio"
        or route != "native_otio"
    ):
        raise MotionRefusal("unqualified Resolve edition/version/import route")
    if binding != proof.binding:
        raise MotionRefusal(
            "stale source, probe, settings, preparation or profile binding"
        )
    hashes = (
        binding.source_hash,
        binding.original_hash,
        binding.source_probe_hash,
        binding.delivered_probe_hash,
        binding.compiler_profile_hash,
        binding.preparation_profile_hash,
        binding.tool_hash,
        binding.settings_hash,
        binding.preparation_binding_hash,
    )
    if any(
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in value[7:])
        for value in hashes
    ):
        raise MotionRefusal("invalid frozen motion source/profile hash")
    if (
        any(
            type(v) is not int
            for v in (
                binding.record_start,
                binding.record_end,
                binding.source_start,
                binding.source_end,
                binding.timeline_width,
                binding.timeline_height,
            )
        )
        or binding.record_start < 0
        or binding.record_end <= binding.record_start
        or binding.source_start < 0
        or binding.source_end != binding.source_start + 1
        or binding.timeline_width <= 0
        or binding.timeline_height <= 0
    ):
        raise MotionRefusal("invalid exact still source or occurrence duration")
    if (
        type(proof.source_width) is not int
        or type(proof.source_height) is not int
        or min(proof.source_width, proof.source_height) <= 0
    ):
        raise MotionRefusal("unqualified source geometry")
    if proof.motion_hash != motion_hash(motion):
        raise MotionRefusal("motion endpoints or easing differ from qualified output")
    if framing != proof.framing or background != proof.background:
        raise MotionRefusal("unqualified framing or background; no silent crop")
    if framing not in {"contain", "cover"} or background != "#000000":
        raise MotionRefusal("framing/background has no native output qualification")
    if motion == {"mode": "none"}:
        if any(
            value is not None
            for value in (
                proof.native_start_center,
                proof.native_end_center,
                proof.native_start_scale,
                proof.native_end_scale,
            )
        ):
            raise MotionRefusal(
                "None qualification unexpectedly includes motion geometry"
            )
        return proof
    if (
        set(motion) != {"mode", "start", "end", "easing"}
        or motion.get("mode") != "native_dynamic_zoom"
    ):
        raise MotionRefusal("unknown native motion mode or settings")
    if motion.get("easing") != "linear":
        raise MotionRefusal("requested nonlinear ease lacks decoded output proof")
    if not proof.focus_proven:
        raise MotionRefusal("normalized focus mapping has no decoded output proof")
    for name in ("start", "end"):
        point = motion[name]
        if not isinstance(point, dict) or set(point) != {"focusX", "focusY", "scale"}:
            raise MotionRefusal("invalid normalized focus or scale")
        for axis in ("focusX", "focusY"):
            value = point[axis]
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not 0 <= value <= 1
            ):
                raise MotionRefusal("focus outside the normalized source")
        value = point["scale"]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise MotionRefusal("invalid source-relative scale")
    if (
        proof.native_start_center is None
        or proof.native_end_center is None
        or proof.native_start_scale is None
        or proof.native_end_scale is None
    ):
        raise MotionRefusal("native center/scale endpoints are not qualified")
    for center in (proof.native_start_center, proof.native_end_center):
        if (
            len(center) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in center)
            or not (0 <= center[0] <= 0.12 and -0.08 <= center[1] <= 0)
        ):
            raise MotionRefusal("raw native center outside observed bounded envelope")
    for scale in (proof.native_start_scale, proof.native_end_scale):
        if (
            type(scale) not in (int, float)
            or not math.isfinite(scale)
            or not 0.8 <= scale <= 1.05
        ):
            raise MotionRefusal("raw native scale outside observed bounded envelope")
    for name, center, scale in (
        ("start", proof.native_start_center, proof.native_start_scale),
        ("end", proof.native_end_center, proof.native_end_scale),
    ):
        requested_center, requested_scale = native_endpoint_from_focus(motion[name])
        if (
            any(
                abs(a - b) > 1e-9 for a, b in zip(center, requested_center, strict=True)
            )
            or abs(scale - requested_scale) > 1e-9
        ):
            raise MotionRefusal(
                "qualified native geometry differs from requested focus"
            )
        if not measured_framing_preserves_intent(
            source_size=(proof.source_width, proof.source_height),
            timeline_size=(binding.timeline_width, binding.timeline_height),
            framing=framing,
            center=center,
            native_scale=scale,
        ):
            raise MotionRefusal(
                "qualified native endpoint would clip contain or expose cover"
            )
    return proof


def native_effect_records(
    motion: dict[str, Any], proof: Qualification
) -> list[dict[str, Any]]:
    """Produce two exact native Resolve OTIO effects, never a guessed fallback."""
    enabled = motion["mode"] == "native_dynamic_zoom"
    start_center = proof.native_start_center if enabled else (0.0, 0.0)
    end_center = proof.native_end_center if enabled else (0.0, 0.0)
    start_scale = proof.native_start_scale if enabled else 0.8
    end_scale = proof.native_end_scale if enabled else 1.0
    if (
        start_center is None
        or end_center is None
        or start_scale is None
        or end_scale is None
    ):
        raise MotionRefusal("missing native effect endpoints")
    return [
        {
            "Type": 59,
            "Name": "Dynamic Zoom",
            "Effect Name": "Dynamic Zoom",
            "Display Type": 1,
            "Enabled": enabled,
            "Parameters": [
                {
                    "Parameter ID": "dynamicZoomCenter",
                    "Variant Type": "POINTF",
                    "Default Parameter Value": [0.0, 0.0],
                    "Parameter Value": list(end_center),
                    "Key Frames": {
                        "-86400": {
                            "Value": list(start_center),
                            "Variant Type": "POINTF",
                        },
                        "-85400": {"Value": list(end_center), "Variant Type": "POINTF"},
                    },
                },
                {
                    "Parameter ID": "dynamicZoomScale",
                    "Variant Type": "Double",
                    "Default Parameter Value": 1.0,
                    "Parameter Value": end_scale,
                    "minValue": 0.01,
                    "maxValue": 100.0,
                    "Key Frames": {
                        "-86400": {"Value": start_scale, "Variant Type": "Double"},
                        "-85400": {"Value": end_scale, "Variant Type": "Double"},
                    },
                },
            ],
        },
        {
            "Type": 22,
            "Name": "Retime and Scaling",
            "Effect Name": "Retime and Scaling",
            "Display Type": 1,
            "Enabled": True,
            "Parameters": [
                {
                    "Parameter ID": "scale",
                    "Variant Type": "UInt",
                    "Default Parameter Value": 0,
                    "Parameter Value": 2 if proof.framing == "contain" else 3,
                }
            ],
        },
    ]
