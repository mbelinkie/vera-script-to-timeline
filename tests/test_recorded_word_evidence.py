"""Synthetic measured-word identity and timing safety for #47."""

from fractions import Fraction
from typing import Any

import pytest
from vera_timeline_agent.recorded_word_evidence import (
    WordEvidenceError,
    canonical_json,
    full_read_evidence,
    validated_marks,
)


def _read() -> dict[str, Any]:
    return {
        "rowId": "row-1",
        "takes": ["take-1", "take-2"],
        "spoken": [10, 13],
        "said": "one two three",
        "cut": {"startFrame": 250, "endFrame": 350},
    }


def _delivery() -> dict[str, Any]:
    return {
        "takes": ["take-1", "take-2"],
        "range": [10, 13],
        "pairs": [(0, 10), (1, 11), (2, 12)],
    }


def _words() -> list[dict[str, Any]]:
    return [{"token": "else", "start": 0, "end": 0, "precision": "missing"}] * 10 + [
        {"token": word, "start": i + 10.1, "end": i + 10.3, "precision": "acoustic"}
        for i, word in enumerate(("one", "two", "three"))
    ]


def test_compound_full_read_has_exact_source_word_pairs() -> None:
    read, expected = _read(), ["one", "two", "three"]
    result = full_read_evidence(read, [_delivery()], _words(), expected)
    marks = validated_marks(
        {"rowId": "row-1", "fullReads": [result]},
        {"rowId": "row-1", "sourceCut": result["sourceCut"], "said": read["said"]},
        expected,
    )
    assert [mark["recordedWordIndex"] for mark in marks] == [10, 11, 12]
    assert Fraction(marks[0]["startS"]) == Fraction(101, 10)
    assert canonical_json(result) == canonical_json(result)


def test_partial_and_unmapped_script_word_refuse_without_invention() -> None:
    expected = ["one", "two", "three"]
    delivery = _delivery()
    delivery["pairs"] = [(0, 10), (2, 12)]
    result = full_read_evidence(_read(), [delivery], _words(), expected)
    assert result["marks"][1]["startS"] is None
    with pytest.raises(WordEvidenceError, match="unmeasured"):
        validated_marks(
            {"rowId": "row-1", "fullReads": [result]},
            {
                "rowId": "row-1",
                "sourceCut": result["sourceCut"],
                "said": result["said"],
            },
            expected,
        )


def test_ambiguous_compound_and_repeated_source_indices_refuse() -> None:
    with pytest.raises(WordEvidenceError, match="ambiguous"):
        full_read_evidence(
            _read(), [_delivery(), _delivery()], _words(), ["one", "two", "three"]
        )
    delivery = _delivery()
    delivery["pairs"][1] = (1, 10)
    with pytest.raises(WordEvidenceError, match="duplicate"):
        full_read_evidence(_read(), [delivery], _words(), ["one", "two", "three"])


def test_missing_or_derived_acoustic_timing_refuses() -> None:
    marks = full_read_evidence(
        _read(), [_delivery()], _words(), ["one", "two", "three"]
    )
    marks["marks"][2]["precision"] = "derived"
    with pytest.raises(WordEvidenceError, match="acoustic"):
        validated_marks(
            {"rowId": "row-1", "fullReads": [marks]},
            {"rowId": "row-1", "sourceCut": marks["sourceCut"], "said": marks["said"]},
            ["one", "two", "three"],
        )
    marks["marks"][2]["precision"] = "acoustic"
    marks["marks"][2]["startS"] = marks["marks"][1]["startS"]
    with pytest.raises(WordEvidenceError, match="overlapping"):
        validated_marks(
            {"rowId": "row-1", "fullReads": [marks]},
            {"rowId": "row-1", "sourceCut": marks["sourceCut"], "said": marks["said"]},
            ["one", "two", "three"],
        )
