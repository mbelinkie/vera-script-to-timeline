"""Still credit graphics: frozen topmost lane and deterministic transparent PNG."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .build_jobs import BuildJobError
from .placeholder_slate import MAX_DIMENSION, MAX_PIXELS, MIN_DIMENSION

TRACK_ID = "still-credit"
# Match the ECMAScript trim used by the compiler.
_TRIM = (
    "\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004"
    "\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
)


def credit_text(payload: dict[str, Any]) -> str:
    if payload.get("showResearchStillCredit") is not True:
        return ""
    credit = payload.get("researchStill", {}).get("credit", "")
    return credit.strip(_TRIM) if isinstance(credit, str) else ""


def freeze_still_credit_inputs(
    document: dict[str, Any], dependencies: dict[str, Any]
) -> bool:
    for block in document.get("activeDraft", {}).get("blocks", []):
        if block.get("type") != "narration" or block.get("state") != "active":
            continue
        placements = [
            *(block.get("primaryVisualSequence") or {}).get("slots", []),
            *block.get("overlayEvents", []),
        ]
        if any(credit_text(placement.get("payload", {})) for placement in placements):
            break
    else:
        return False
    tracks = dependencies["tracks"]
    overlays = dependencies["roles"]["overlayTrackIds"]
    videos = [track for track in tracks if track["kind"] == "video"]
    existing = next((track for track in tracks if track["id"] == TRACK_ID), None)
    if existing:
        if (
            existing not in videos
            or TRACK_ID not in overlays
            or existing["index"] != max(track["index"] for track in videos)
        ):
            raise BuildJobError(
                "Still credit track conflicts with the configured track layout"
            )
        return True
    index = max((track["index"] for track in videos), default=0) + 1
    tracks.append(
        {"id": TRACK_ID, "kind": "video", "index": index, "name": "Still Credits"}
    )
    overlays.append(TRACK_ID)
    return True


def render_credit(text: str, width: int, height: int) -> bytes:
    """Use Pillow's bundled font, avoiding workstation-dependent font selection."""
    if (
        not MIN_DIMENSION <= width <= MAX_DIMENSION
        or not MIN_DIMENSION <= height <= MAX_DIMENSION
        or width * height > MAX_PIXELS
    ):
        raise ValueError("still credit canvas dimensions are unsupported")
    if not text or len(text) > 2000 or not text.strip():
        raise ValueError("still credit text is missing or too long")
    image = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(image)
    margin = max(1, round(min(width, height) * 0.04))
    available = width - 2 * margin
    # Wrap without dropping any non-whitespace characters; shrink only as needed.
    for size in range(max(8, round(height * 0.035)), 7, -1):
        font = ImageFont.load_default(size=size)
        missing = bytes(font.getmask("\uffff"))
        if any(
            not char.isspace() and bytes(font.getmask(char)) == missing for char in text
        ):
            raise ValueError(
                "still credit includes characters unsupported by the bundled font"
            )
        lines = []
        line = ""
        for char in text:
            if char == "\n" or (
                line and draw.textlength(line + char, font=font) > available
            ):
                lines.append(line)
                line = ""
            if char != "\n":
                line += char
        lines.append(line)
        leading = round(size * 1.4)
        if len(lines) * leading + 2 * margin <= height * 0.45:
            break
    else:
        raise ValueError("still credit is too long for the output frame")
    y = height - margin - len(lines) * leading
    for line in lines:
        right = width - margin
        left = round(right - draw.textlength(line, font=font))
        if line:
            draw.rectangle(
                (max(0, left - 3), y, right + 3, y + leading), fill=(0, 0, 0, 190)
            )
            draw.text((left, y), line, font=font, fill=(255, 255, 255, 255))
        y += leading
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()
