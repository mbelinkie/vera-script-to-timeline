"""Transparent review signals from unlabelled speech and authored script only."""

from __future__ import annotations

import re
from typing import Any

Record = dict[str, Any]


def sentence_spans(text: str, tokenize: Any) -> list[tuple[int, int]]:
    """Experimental sentence coverage; decimal points do not delimit sentences."""
    parts = re.split(r"(?<=[.!?])\s+(?=[^\d])", text)
    spans, offset = [], 0
    for part in parts:
        length = len(tokenize(part))
        if length:
            spans.append((offset, offset + length))
            offset += length
    return spans


def editorial_signals(words: list[Record], candidates: list[Record]) -> list[Record]:
    """Off-script take references are untrusted evidence, never executable commands.

    Deliberately flag mentions without claiming that the speaker prefers a take.
    Negation, quotation, joking, and an unclear antecedent all need human judgment.
    """
    signals: list[Record] = []
    for i in range(len(words) - 1):
        target = words[i]["token"]
        if target not in {"first", "earlier", "previous", "last"}:
            continue
        if words[i + 1]["token"] != "take":
            continue
        owner = next(
            c for c in candidates if c["word_range"][0] <= i < c["word_range"][1]
        )
        # Scripted wording is not editorial direction, including partial readings.
        scripted_positions = {
            owner["word_range"][0] + op["actual"]
            for op in owner["diff"]
            if op["op"] == "equal"
        }
        if i in scripted_positions and i + 1 in scripted_positions:
            continue
        before = [c for c in candidates if c["row"] and c["word_range"][1] <= i]
        nearest = before[-1] if before else None
        rows = nearest["row_options"] if nearest else []
        related = [c for c in before if any(row in c["row_options"] for row in rows)]
        # A partial's covered span is the relevant repeat unit, not the whole row.
        if nearest:
            extent = {
                op["expected"]
                for op in nearest["diff"]
                if op["op"] in {"equal", "substitute"}
            }
            related = [
                c
                for c in related
                if extent
                and len(
                    extent
                    & {
                        op["expected"]
                        for op in c["diff"]
                        if op["op"] in {"equal", "substitute"}
                    }
                )
                / len(extent)
                >= 0.7
            ]
        choices = related[:-1]
        if target == "first":
            choices = choices[:1]
        elif target in {"previous", "last"}:
            choices = related[-2:-1]
        lo, hi = max(owner["word_range"][0], i - 6), min(owner["word_range"][1], i + 7)
        context = [w["token"] for w in words[lo:hi]]
        signals.append(
            {
                "id": f"editorial-{len(signals) + 1:03}",
                "word_range": [lo, hi],
                "mention_range": [i, i + 2],
                "target": target,
                "row_options": rows,
                "related_candidates": [c["id"] for c in related],
                "earlier_candidate_options": [c["id"] for c in choices],
                "negation_detected": any(
                    w in {"not", "don't", "wasn't", "never"} for w in context
                ),
                "status": "producer_choice_required",
                "speaker_verified": False,
                "interpretation": "Possible edit note; meaning/target unverified",
                "automatically_applied": False,
            }
        )
    return signals
