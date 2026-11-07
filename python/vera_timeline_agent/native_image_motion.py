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
import re
import struct
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class MotionRefusal(ValueError):
    """The requested native image effect has no exact verified output proof."""


_HEX_TO_LETTERS = str.maketrans("0123456789abcdef", "abcdefghijklmnop")
_SOURCE_ID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")


def native_still_stem(source_id: str) -> str:
    """Encode a UUID as a collision-free alphabetic still basename.

    Installed Studio 21.1.1.10 recognizes numeric runs anywhere in a PNG
    filename as an image sequence, even with a `-still.png` suffix. There
    must be NO decimal digits anywhere in the delivered still filename.
    """
    if not isinstance(source_id, str) or _SOURCE_ID.fullmatch(source_id) is None:
        raise MotionRefusal("native still source id must be a canonical UUID")
    return "still-" + source_id.translate(_HEX_TO_LETTERS)


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
    motion: dict[str, Any],
    binding: MotionBinding,
    framing: str,
    *,
    verified_asset: Path | None = None,
    delivered_probe: dict[str, Any] | None = None,
    frame_rate: tuple[int, int] | None = None,
) -> Qualification | None:
    """Admit only hash-verified, untransformed RGB PNGs in the measured Studio lane.

    The caller must supply a verified package asset and its independently
    validated preparation receipt. A standalone authored motion dictionary
    cannot grant a qualification. The deliberately narrow 16:9/24fps route
    excludes unmeasured codecs, color transforms, aspect ratios, durations,
    backgrounds, and moving contain (which needs a proven derived matte).
    """
    if (
        verified_asset is None
        or delivered_probe is None
        or frame_rate != (24, 1)
        or (binding.timeline_width, binding.timeline_height) != (1920, 1080)
        or binding.original_hash != binding.source_hash
        or binding.record_end - binding.record_start not in {24, 48, 96, 144}
        or framing not in {"contain", "cover"}
    ):
        return None
    dimensions = _verified_rgb_png_dimensions(
        verified_asset, binding.source_hash, delivered_probe
    )
    if dimensions is None:
        return None
    width, height = dimensions
    # Do not generalize a handful of decoded public aspect/size fixtures into
    # native raster proof for every resolution sharing the same aspect ratio.
    if (width, height) not in {(1000, 1000), (1600, 900), (900, 1600)}:
        return None
    if motion == {"mode": "none"}:
        return Qualification(
            edition="studio",
            version="21.1.1.10",
            route="native_otio",
            binding=binding,
            motion_hash=motion_hash(motion),
            framing=framing,
            background="#000000",
            source_width=width,
            source_height=height,
        )
    if (
        framing != "cover"
        or not isinstance(motion, dict)
        or set(motion) != {"mode", "start", "end", "easing"}
        or motion.get("mode") != "native_dynamic_zoom"
        or motion.get("easing") != "linear"
    ):
        return None
    try:
        start_center, start_scale = native_endpoint_from_focus(motion["start"])
        end_center, end_scale = native_endpoint_from_focus(motion["end"])
    except (KeyError, MotionRefusal, TypeError, ValueError, ZeroDivisionError):
        return None
    if not all(
        measured_framing_preserves_intent(
            source_size=dimensions,
            timeline_size=(binding.timeline_width, binding.timeline_height),
            framing="cover",
            center=center,
            native_scale=scale,
        )
        for center, scale in ((start_center, start_scale), (end_center, end_scale))
    ):
        return None
    return Qualification(
        edition="studio",
        version="21.1.1.10",
        route="native_otio",
        binding=binding,
        motion_hash=motion_hash(motion),
        framing=framing,
        background="#000000",
        source_width=width,
        source_height=height,
        focus_proven=True,
        native_start_center=start_center,
        native_end_center=end_center,
        native_start_scale=start_scale,
        native_end_scale=end_scale,
    )


def _verified_rgb_png_dimensions(
    asset: Path, expected_hash: str, probe: dict[str, Any]
) -> tuple[int, int] | None:
    """Strict lossless PNG decoder admission (not a substitute for Studio proof).

    Only non-animated, non-interlaced, metadata-free 8-bit RGB is accepted.
    Bounds cap the decoded size; the verified media receipt independently pins
    codec, geometry, and single-frame identity. Never trust a PNG extension or
    header alone for an effect write.
    """
    if not isinstance(asset, Path) or asset.suffix.lower() != ".png":
        return None
    try:
        if asset.stat().st_size > 24 * 1024 * 1024:
            return None
        raw = asset.read_bytes()
    except OSError:
        return None
    if "sha256:" + hashlib.sha256(
        raw
    ).hexdigest() != expected_hash or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    pos = 8
    dimensions: tuple[int, int] | None = None
    idat = bytearray()
    finished = False
    while pos + 12 <= len(raw):
        size = struct.unpack_from(">I", raw, pos)[0]
        if size > len(raw) - pos - 12:
            return None
        tag = raw[pos + 4 : pos + 8]
        data = raw[pos + 8 : pos + 8 + size]
        crc = struct.unpack_from(">I", raw, pos + 8 + size)[0]
        if zlib.crc32(tag + data) != crc:
            return None
        pos += size + 12
        if dimensions is None:
            if tag != b"IHDR" or size != 13:
                return None
            width, height, depth, kind, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", data)
            )
            if (
                not (1 <= width <= 4096 and 1 <= height <= 4096)
                or width * height > 8_000_000
                or (depth, kind, compression, filtering, interlace) != (8, 2, 0, 0, 0)
            ):
                return None
            dimensions = (width, height)
        elif tag == b"IDAT" and not finished:
            idat.extend(data)
        elif tag == b"IEND" and size == 0 and idat:
            finished = True
            break
        else:
            # No color profiles, EXIF orientation, gamma, animation, or unknown
            # ancillary chunks. Such variants require their own native proof.
            return None
    if dimensions is None or not finished or pos != len(raw):
        return None
    width, height = dimensions
    expected_size = (1 + 3 * width) * height
    try:
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(bytes(idat), expected_size + 1)
        if (
            len(pixels) != expected_size
            or not decoder.eof
            or decoder.unused_data
            or decoder.unconsumed_tail
            or any(pixels[row * (1 + 3 * width)] > 4 for row in range(height))
        ):
            return None
    except zlib.error:
        return None
    streams = probe.get("streams")
    frames = probe.get("frames")
    if (
        not isinstance(streams, list)
        or len(streams) != 1
        or not isinstance(streams[0], dict)
        or streams[0].get("codec_type") != "video"
        or streams[0].get("codec_name") != "png"
        or streams[0].get("width") != width
        or streams[0].get("height") != height
        or not isinstance(frames, list)
        or len(frames) != 1
    ):
        return None
    return dimensions


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
    # Native OTIO serializes these through a separate numeric representation.
    # Canonicalize beyond raster-visible precision so independently rebuilt
    # effects do not differ only by 1-ULP subtraction noise (0.52 vs 0.5).
    center = (
        round(float(frame["focusX"] - 0.5), 12),
        round(float(0.5 - frame["focusY"]), 12),
    )
    inverse_scale = round(1.0 / frame["scale"], 12)
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
