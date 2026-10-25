"""Bounded #325 probe preflight; this does not implement production motion."""

import hashlib
from collections.abc import Mapping
from pathlib import Path

PROFILE = "studio-21.1.1.10-otio-occurrence-properties-v1"
RUNTIME = ("DaVinci Resolve Studio", "21.1.1.10")
SOURCE_SHA256 = "c52450d978e472ddc4d9835308f38c5d1c1be15c3c99ff3e5d8e2027fcfed36b"


def probe_properties(
    request: Mapping[str, object],
    source: Path,
    runtime: tuple[str, str],
    occurrence_frames: int,
) -> dict[str, object]:
    """Refuse before native mutation; custom focus needs a separate OTIO proof."""
    if set(request) != {
        "profile",
        "sourceSha256",
        "durationFrames",
        "motion",
        "ease",
        "framing",
        "background",
    }:
        raise ValueError("unknown or missing request fields, including custom framing")
    if request["profile"] != PROFILE or runtime != RUNTIME:
        raise ValueError("stale or unqualified runtime/profile")
    try:
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    except OSError as error:
        raise ValueError("stale source bytes") from error
    if source_hash != SOURCE_SHA256 or request["sourceSha256"] != SOURCE_SHA256:
        raise ValueError("stale source bytes")
    duration = request["durationFrames"]
    if type(duration) is not int or duration not in (24, 48, 96, 144):
        raise ValueError("duration outside the tested reconstruction matrix")
    if type(occurrence_frames) is not int or occurrence_frames != duration:
        raise ValueError("existing OTIO occurrence does not have requested duration")
    if request["motion"] not in ("native-default", "None"):
        raise ValueError("unqualified motion; no preset substitution")
    ease = request["ease"]
    if type(ease) is not int or ease != 0:
        raise ValueError("only linear ease has distinct output qualification")
    framing = request["framing"]
    if framing not in ("fit", "fill") or request["background"] != "black":
        raise ValueError("unqualified framing/background")
    if duration != 48 and (request["motion"], framing) != ("native-default", "fit"):
        raise ValueError("combination outside the rendered matrix")
    return {
        "DynamicZoomEnabled": request["motion"] == "native-default",
        "DynamicZoomEase": ease,
        "Scaling": 2 if framing == "fit" else 3,
    }
