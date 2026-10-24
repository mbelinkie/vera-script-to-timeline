from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from vera_timeline_agent.narration.inworld_timing import (
    SAMPLE_RATE,
    InworldTimingError,
    timing_marks,
)


def _response(
    words: list[str], starts: Sequence[object], ends: Sequence[object]
) -> dict[str, Any]:
    return {
        "timestampInfo": {
            "wordAlignment": {
                "words": words,
                "wordStartTimeSeconds": list(starts),
                "wordEndTimeSeconds": list(ends),
            }
        }
    }


def test_split_unicode_word_maps_exact_sample_and_source_offsets() -> None:
    marks = timing_marks(
        "Måns says go.",
        _response(
            ["M", "å", "ns", " ", "says", " ", "go", "."],
            [0.1, 0.12, 0.14, 0.2, 0.25, 0.45, 0.5, 0.8],
            [0.11, 0.13, 0.18, 0.21, 0.4, 0.46, 0.7, 0.81],
        ),
        SAMPLE_RATE,
    )

    assert [mark.value for mark in marks] == ["Måns", "says", "go"]
    assert [(mark.start_utf16, mark.end_utf16) for mark in marks] == [
        (0, 4),
        (5, 9),
        (10, 12),
    ]
    assert [(mark.start_byte, mark.end_byte) for mark in marks] == [
        (0, 5),
        (6, 10),
        (11, 13),
    ]
    assert [(mark.time_sample, mark.end_sample) for mark in marks] == [
        (4800, 8640),
        (12000, 19200),
        (24000, 33600),
    ]
    assert [mark.time_ms for mark in marks] == [100, 250, 500]
    assert all(mark.sample_rate == SAMPLE_RATE for mark in marks)


def test_internal_apostrophe_stays_in_token_and_boundary_punctuation_does_not() -> None:
    marks = timing_marks(
        "can\u2019t go!",
        _response(
            ["can", "\u2019", "t", " ", "go", "!"],
            [0.1, 0.2, 0.21, 0.3, 0.4, 2.0],
            [0.18, 0.205, 0.25, 0.31, 0.6, 3.0],
        ),
        SAMPLE_RATE,
    )

    assert [mark.value for mark in marks] == ["can\u2019t", "go"]
    assert [(mark.start_utf16, mark.end_utf16) for mark in marks] == [(0, 5), (6, 8)]
    # Punctuation timestamps are finite-checked, but do not extend lexical bounds.
    assert marks[-1].end_sample == 28_800


@pytest.mark.parametrize(
    ("words", "starts", "ends", "message"),
    [
        (["wrong"], [0.1], [0.2], "exactly cover"),
        (["go!"], [0.1], None, "arrays are missing"),
        (["go", "!"], [0.1], [0.2, 0.3], "different lengths"),
        (["go", "!"], [0.1, float("nan")], [0.2, 0.3], "finite number"),
    ],
)
def test_rejects_mismatch_missing_arrays_and_nonfinite_punctuation(
    words: list[str],
    starts: list[object],
    ends: list[object] | None,
    message: str,
) -> None:
    response = _response(words, starts, ends or [])
    if ends is None:
        del response["timestampInfo"]["wordAlignment"]["wordEndTimeSeconds"]

    with pytest.raises(InworldTimingError, match=message):
        timing_marks("go!", response, SAMPLE_RATE)


@pytest.mark.parametrize(
    ("starts", "ends", "message"),
    [
        ([0.1, 0.1], [0.15, 0.2], "tie, decrease, or overlap"),
        ([0.2, 0.1], [0.25, 0.3], "tie, decrease, or overlap"),
        ([0.1, 0.2], [0.3, 0.25], "tie, decrease, or overlap"),
    ],
)
def test_rejects_tied_decreasing_and_overlapping_lexical_intervals(
    starts: list[float], ends: list[float], message: str
) -> None:
    with pytest.raises(InworldTimingError, match=message):
        timing_marks("ab", _response(["a", "b"], starts, ends), SAMPLE_RATE)


def test_rejects_phrase_piece_that_crosses_source_words() -> None:
    with pytest.raises(InworldTimingError, match="multiple source tokens"):
        timing_marks("one two", _response(["one two"], [0.1], [0.8]), SAMPLE_RATE)


@pytest.mark.parametrize(
    ("start", "end"),
    [(-0.01, 0.1), (0.9, 1.01)],
)
def test_rejects_lexical_intervals_outside_audio(start: float, end: float) -> None:
    with pytest.raises(InworldTimingError, match="outside audio"):
        timing_marks("go", _response(["go"], [start], [end]), SAMPLE_RATE)


def test_rejects_positive_interval_that_collapses_on_sample_grid() -> None:
    with pytest.raises(InworldTimingError, match="sample grid"):
        timing_marks("go", _response(["go"], [0.100001], [0.100004]), SAMPLE_RATE)


def test_symbols_receive_timing_instead_of_being_silently_skipped() -> None:
    marks = timing_marks(
        "5 + 3 🙂",
        _response(
            ["5", " ", "+", " ", "3", " ", "🙂"],
            [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
            [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
        ),
        SAMPLE_RATE,
    )
    assert [mark.value for mark in marks] == ["5", "+", "3", "🙂"]
    assert (marks[-1].start_utf16, marks[-1].end_utf16) == (6, 8)
    with pytest.raises(InworldTimingError, match="finite number"):
        timing_marks("🙂", _response(["🙂"], [float("nan")], [0.2]), SAMPLE_RATE)
