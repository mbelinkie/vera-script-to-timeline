"""Freeze the workstation title revision and its graphics lane for a quote build."""

from __future__ import annotations

from typing import Any

from .build_jobs import BuildJobError
from .quote_box_native import (
    QUOTE_BOX_TEMPLATE_REVISION,
    QuoteBoxNativeError,
    verify_installed_quote_box_setting,
)


def freeze_quote_box_inputs(
    document: dict[str, Any], dependencies: dict[str, Any]
) -> bool:
    """Update an in-memory dependency copy only for a document using quote boxes."""
    if not any(
        "quoteBox" in event
        for block in document.get("activeDraft", {}).get("blocks", [])
        if block.get("type") == "narration" and block.get("state") == "active"
        for event in block.get("overlayEvents", [])
    ):
        return False

    try:
        verify_installed_quote_box_setting()
    except QuoteBoxNativeError:
        dependencies["quoteBoxTemplateRevision"] = None
    else:
        dependencies["quoteBoxTemplateRevision"] = QUOTE_BOX_TEMPLATE_REVISION

    tracks = dependencies["tracks"]
    overlays = dependencies["roles"]["overlayTrackIds"]
    occupied = [
        track for track in tracks if track["kind"] == "video" and track["index"] == 4
    ]
    if len(occupied) == 1 and occupied[0]["id"] in overlays:
        return True
    if any(track["id"] == "quote-graphics" for track in tracks):
        raise BuildJobError(
            "The quote graphics track conflicts with another configured track"
        )

    # A fresh build can insert a lane. Keep other tracks in the same relative order.
    if occupied:
        for track in tracks:
            if track["kind"] == "video" and track["index"] >= 4:
                track["index"] += 1
    tracks.append(
        {"id": "quote-graphics", "kind": "video", "index": 4, "name": "Quote Graphics"}
    )
    overlays.append("quote-graphics")
    return True
