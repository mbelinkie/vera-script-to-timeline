"""Imported still ranges retain their requested timeline duration."""

from __future__ import annotations

from typing import Any

import pytest
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent.qualification_output_records_v2 import OutputConsistencyError


@pytest.mark.parametrize(
    ("start", "duration", "source_fps", "timeline_rate", "expected_end"),
    [
        (0, 122, "24", {"numerator": 24000, "denominator": 1001}, 123),
        (17, 148, "24.0", {"numerator": 24000, "denominator": 1001}, 166),
        (0, 100, 24.0, {"numerator": 24000, "denominator": 1001}, 101),
        (7, 122, 24, {"numerator": 24, "denominator": 1}, 129),
        (7, 100, "25", {"numerator": 24, "denominator": 1}, 112),
        (7, 100, "25", {"numerator": 25, "denominator": 1}, 107),
    ],
)
def test_still_append_converts_timeline_duration_to_source_frames(
    start: int,
    duration: int,
    source_fps: Any,
    timeline_rate: dict[str, int],
    expected_end: int,
) -> None:
    assert native._native_append_source_range(
        start, duration, source_fps, timeline_rate, still=True
    ) == (start, expected_end)


def test_non_still_append_keeps_admitted_source_span() -> None:
    assert native._native_append_source_range(
        7,
        100,
        "not a frame rate",
        {"numerator": 24000, "denominator": 1001},
        still=False,
    ) == (7, 107)


@pytest.mark.parametrize("source_fps", [None, "unknown", "0"])
def test_still_append_requires_a_positive_imported_frame_rate(
    source_fps: Any,
) -> None:
    with pytest.raises(OutputConsistencyError, match="still frame rate"):
        native._native_append_source_range(
            0,
            122,
            source_fps,
            {"numerator": 24000, "denominator": 1001},
            still=True,
        )
