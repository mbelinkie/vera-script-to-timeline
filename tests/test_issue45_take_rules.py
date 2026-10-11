"""Take rules v2 on top of the accepted #53 discover() (Producer, 2026-10-10)."""

from __future__ import annotations

from typing import Any

from experiments.issue45.take_rules import refine
from experiments.issue53.takes import discover

ROW = (
    "But first off I can overthink anything. "
    "I watched a long talk on The Boss Baby, okay? Secondly trust nothing."
)


def packet(spoken: list[tuple[str, float]]) -> dict[str, Any]:
    words = [
        {
            "text": w,
            "start": t,
            "end": t + 0.25,
            "precision": "acoustic",
            "provenance": "test",
        }
        for w, t in spoken
    ]
    return {
        "version": "take-experiment/1",
        "source": {"alias": "test", "duration": 120.0, "fps": [30, 1]},
        "rows": [{"id": "row-1", "text": ROW, "beat_ids": []}],
        "words": words,
        "audio_activity": [],
        "decisions": {},
        "provenance": {"variant": "test"},
        "options": {"include_partial_alternates": True},
    }


def said(text: str, start: float) -> list[tuple[str, float]]:
    return [(w, start + 0.3 * n) for n, w in enumerate(text.split())]


def test_moved_word_read_is_one_complete_delivery() -> None:
    # The presenter moves "okay" earlier than written and does not re-read it.
    take = said(
        "But first off I can overthink anything okay "
        "I watched a long talk on The Boss Baby "
        "Secondly trust nothing",
        10.0,
    )
    report = refine(discover(packet(take)))
    info = report["take_rules_v2"]["rows"][0]
    assert info["selected"] in (
        "last complete read (discover)",
        "continuous delivery run (complete)",
    )
    moved = [m["word"] for m in info["differences"]["moved"]]
    assert moved == ["okay"]
    assert info["differences"]["differs_from_script"] is True


def test_earlier_full_read_is_a_usable_alternate_and_last_is_default() -> None:
    first = said(
        "But first off I can overthink anything "
        "I watched a long talk on The Boss Baby okay "
        "Secondly trust nothing",
        5.0,
    )
    abandoned = said("But first off I can", 20.0)
    last = said(
        "But first off I can overthink anything "
        "I watched a long talk on The Boss Baby okay "
        "Secondly trust nothing",
        30.0,
    )
    report = refine(discover(packet(first + abandoned + last)))
    info = report["take_rules_v2"]["rows"][0]
    by_id = {c["id"]: c for c in report["candidates"]}
    default = by_id[report["groups"][0]["suggested_last_complete"]]
    assert report["words"][default["word_range"][0]]["start"] >= 30.0  # the last read
    assert info["differences"]["differs_from_script"] is False
    alternates = info["alternates"]
    assert len(alternates) == 1  # the abandoned restart is not offered
    assert report["words"][alternates[0]["source_word_range"][0]]["start"] == 5.0
