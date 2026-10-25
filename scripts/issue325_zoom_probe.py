"""Bounded #325 probe preflight; this does not implement production motion."""

import hashlib
from collections.abc import Mapping
from pathlib import Path

PROFILE = "studio-21.1.1.10-dynamic-zoom-api-v1"
RUNTIME = ("DaVinci Resolve Studio", "21.1.1.10")


def probe_properties(
    request: Mapping[str, object], source: Path, runtime: tuple[str, str]
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
    if hashlib.sha256(source.read_bytes()).hexdigest() != request["sourceSha256"]:
        raise ValueError("stale source bytes")
    duration = request["durationFrames"]
    if type(duration) is not int or duration not in (24, 48, 96, 144):
        raise ValueError("duration outside the tested reconstruction matrix")
    if request["motion"] not in ("native-default", "None"):
        raise ValueError("unqualified motion; no preset substitution")
    ease = request["ease"]
    if type(ease) is not int or ease != 0:
        raise ValueError("only linear ease has distinct output qualification")
    framing = request["framing"]
    if framing not in ("fit", "fill") or request["background"] != "black":
        raise ValueError("unqualified framing/background")
    return {
        "DynamicZoomEnabled": request["motion"] == "native-default",
        "DynamicZoomEase": ease,
        "Scaling": 2 if framing == "fit" else 3,
    }
