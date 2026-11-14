"""Durable, fail-closed script-to-recorded-word evidence for recorded conform.

The #45 analyzer has the alignment *while* it builds whole-passage reads;
`takes.json` deliberately doesn't publish the ephemeral recognition indices.
This sidecar preserves those indices and exact measured times before they go
away. It is evidence, never an approval or permission to choose another take.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from typing import Any

Json = dict[str, Any]
SCHEMA = "take-word-marks/1"


class WordEvidenceError(ValueError):
    """Word-to-script identity or measured timing could not be established."""


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def exact_seconds(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise WordEvidenceError("non-numeric recorded word boundary")
    try:
        number = Fraction(str(value))
    except (ValueError, ZeroDivisionError) as exc:
        raise WordEvidenceError("invalid recorded word boundary") from exc
    if number < 0:
        raise WordEvidenceError("negative recorded word boundary")
    return str(number)


def full_read_evidence(
    read: Json, deliveries: list[Json], words: list[Json], expected: list[str]
) -> Json:
    """Pin an entire continuous read, including unmeasured/mismatched words.

    A missing or substituted token is represented explicitly, never guessed by
    ordinal, text similarity or a neighbouring word's timestamp.
    """
    candidates = [d for d in deliveries if d["takes"] == read["takes"]
                  and d["range"][0] <= read["spoken"][0]
                  and d["range"][1] >= read["spoken"][1]]
    if len(candidates) != 1:
        raise WordEvidenceError("ambiguous full continuous read")
    delivery = candidates[0]
    mappings: dict[int, int] = {}
    used: set[int] = set()
    for script_index, heard_index in delivery["pairs"]:
        if not (0 <= script_index < len(expected)):
            continue
        if not (read["spoken"][0] <= heard_index < read["spoken"][1]):
            continue
        if script_index in mappings or heard_index in used:
            raise WordEvidenceError("duplicate script-to-recording word mapping")
        mappings[script_index] = heard_index
        used.add(heard_index)
    marks: list[Json] = []
    for index, expected_word in enumerate(expected):
        heard_index = mappings.get(index)
        observed = words[heard_index] if heard_index is not None else None
        # Aligned token equality is necessary, not a fuzzy replacement match.
        matching = observed is not None and observed["token"] == expected_word
        precision = observed["precision"] if matching else "missing"
        marks.append({
            "scriptWordIndex": index,
            "scriptWord": expected_word,
            "recordedWordIndex": heard_index if matching else None,
            "recordedWord": observed["token"] if matching else None,
            "startS": exact_seconds(observed["start"]) if matching else None,
            "endS": exact_seconds(observed["end"]) if matching else None,
            "precision": precision,
        })
    cut = read.get("cut")
    return {
        "takes": list(read["takes"]),
        "said": read["said"],
        "sourceCut": ({"startFrame": cut["startFrame"], "endFrame": cut["endFrame"]}
                      if cut else None),
        "spoken": list(read["spoken"]),
        "marks": marks,
    }


def validated_marks(row: Json, read: Json, expected: list[str]) -> list[Json]:
    """Require exactly one complete measured word map for the approved read."""
    if row.get("rowId") != read.get("rowId"):
        raise WordEvidenceError("recorded word row identity differs")
    matches = [item for item in row.get("fullReads", []) if
               item.get("sourceCut") == read.get("sourceCut") and
               item.get("said") == read.get("said")]
    if len(matches) != 1:
        raise WordEvidenceError(f"{row['rowId']}: missing or ambiguous approved word evidence")
    marks = matches[0].get("marks")
    if not isinstance(marks, list) or len(marks) != len(expected):
        raise WordEvidenceError(f"{row['rowId']}: incomplete script word evidence")
    previous_end = Fraction(0)
    used: set[int] = set()
    for index, (mark, text) in enumerate(zip(marks, expected, strict=True)):
        if not isinstance(mark, dict) or mark.get("scriptWordIndex") != index or mark.get("scriptWord") != text:
            raise WordEvidenceError(f"{row['rowId']}: changed script token identity")
        heard = mark.get("recordedWordIndex")
        if type(heard) is not int or heard < 0 or heard in used or mark.get("recordedWord") != text:
            raise WordEvidenceError(f"{row['rowId']}: unmeasured or ambiguous script word {index + 1}")
        used.add(heard)
        if mark.get("precision") != "acoustic":
            raise WordEvidenceError(f"{row['rowId']}: word {index + 1} has no acoustic timing")
        try:
            start, end = Fraction(mark["startS"]), Fraction(mark["endS"])
        except (KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
            raise WordEvidenceError(f"{row['rowId']}: invalid measured time") from exc
        if start < previous_end or end <= start:
            raise WordEvidenceError(f"{row['rowId']}: overlapping or reversed word timing")
        previous_end = end
    return marks
