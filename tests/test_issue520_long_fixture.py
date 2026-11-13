from __future__ import annotations

from fractions import Fraction
from types import SimpleNamespace
from typing import Any

from vera_timeline_agent.issue312_fixture import placement_plan
from vera_timeline_agent.issue520_long_fixture import RATE, _block_payload


def test_long_fixture_uses_source_clips_for_the_two_inherited_slates() -> None:
    plan = placement_plan()
    slates = [
        item
        for item in plan["pictures"]
        if item["pictureKind"] == "intentional_placeholder"
    ]
    assert [(item["id"], item["source"], item["sourceInFrame"]) for item in slates] == [
        ("picture-00", "source-00", 24),
        ("picture-01", "source-01", 24),
    ]

    sources = {source["id"]: source for source in plan["sources"]}
    inspections: dict[str, Any] = {
        item["source"]: SimpleNamespace(
            rate=RATE,
            pts_origin=Fraction(0),
            time_base=Fraction(1, 24),
            video_frames=[{} for _ in range(30 * 24)],
            content_hash="sha256:" + "1" * 64,
            probe_hash="sha256:" + "2" * 64,
        )
        for item in slates
    }

    for item in slates:
        descriptors: list[dict[str, Any]] = []
        payload = _block_payload(
            item,
            {"kind": "primary_slot", "sequenceId": "sequence", "slotId": "slot"},
            sources,
            inspections,
            descriptors,
        )

        assert item["pictureKind"] == "intentional_placeholder"
        assert payload["pictureKind"] == "clip"
        assert payload["sourceUsage"] == {"sourceInFrame": 24}
        assert len(descriptors) == 1
        descriptor = descriptors[0]
        assert payload["source"]["mediaReferenceId"] == descriptor["mediaReferenceId"]
        assert descriptor["logicalSourceBounds"]["endFrame"] == 30 * 24
        assert descriptor["occurrenceSourceInFrame"] == 24
