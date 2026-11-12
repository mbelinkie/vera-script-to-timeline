"""One command lists every take in a presenter recording (#45)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from vera_timeline_agent import presenter_takes as pt

from experiments.issue45.take_rules import refine
from experiments.issue53.takes import discover

Json = dict[str, Any]
FPS = [30, 1]
DURATION = 60.0
SCRIPT = (
    "(on) KAJ [kai] is three Finns singing in Swedish. They really like saunas. "
    "(off) The band wanted to embrace the weirdness."
)
DICTIONARY = {
    "is", "three", "finns", "singing", "in", "swedish", "they", "really", "like",
    "saunas", "the", "band", "wanted", "to", "embrace", "weirdness",
}  # fmt: skip


def _artifacts(spoken: list[tuple[str, float]]) -> tuple[Json, Json]:
    """Recognition and alignment for words said at the given start times."""
    tokens, units = [], []
    for index, (word, start) in enumerate(spoken):
        a, b = round(start * 1000), round(start * 1000) + 250
        tokens.append(
            {"index": index, "display": word, "anchorStartMs": a, "anchorEndMs": b}
        )
        units.append(
            {
                "tokenIndex": index,
                "sub": 0,
                "text": word.strip(".,").casefold(),
                "startMs": a,
                "endMs": b,
                "status": "acoustic",
            }
        )
    return {"tokens": tokens}, {"artifactId": "test", "words": units}


def _said(text: str, start: float) -> list[tuple[str, float]]:
    return [(word, start + 0.3 * n) for n, word in enumerate(text.split())]


def _takes(
    spoken: list[tuple[str, float]],
    *,
    quiet: list[list[float]] | None = None,
    alignment_edit: Any = None,
) -> Json:
    recognition, alignment = _artifacts(spoken)
    if alignment_edit:
        alignment_edit(alignment)
    passages = pt.script_passages(SCRIPT, DICTIONARY)
    words = pt.timed_words(recognition, alignment)
    report = refine(discover(pt.take_packet(words, alignment, passages, DURATION, FPS)))
    body = pt.build_takes(
        report,
        words,
        recognition,
        alignment,
        passages,
        [[0.0, DURATION]] if quiet is None else quiet,
        DURATION,
        FPS,
    )
    return {
        "video": {"file": "clip.mov", "durationS": DURATION, "fps": FPS},
        "script": {"file": "script.txt"},
        "sync": None,
        **body,
        "secondsTaken": 1.0,
    }


FIRST = "kaj is three Finns singing in Swedish. They really like saunas."
SECOND = "The band wanted to embrace the weirdness."
SESSION = [
    *_said(FIRST, 2.0),
    *_said("kaj is three Finns", 10.0),  # abandoned
    *_said("Sorry.", 13.0),
    *_said(FIRST, 15.0),
    *_said(SECOND, 25.0),
]


def test_rtf_script_becomes_plain_text() -> None:
    u = chr(92) + "u"  # RTF's Unicode escape, each followed by a fallback character
    rtf = (
        r"{\rtf1\ansi\uc1{\fonttbl{\f0 Helvetica;}}{\*\generator x;}"
        rf"\f0 (on) It wasn\'92t K{u}228 a {u}8220 ?quoted{u}8221 ?.\par (off) Next.}}"
    )
    expected = f"(on) It wasn{chr(8217)}t K{chr(228)} {chr(8220)}quoted{chr(8221)}."
    assert pt.rtf_to_text(rtf) == expected + "\n(off) Next."


def test_passages_are_marker_blocks_or_paragraphs() -> None:
    marked = pt.script_passages(SCRIPT, DICTIONARY)
    assert [p.script for p in marked] == [
        "KAJ is three Finns singing in Swedish. They really like saunas.",
        "The band wanted to embrace the weirdness.",
    ]
    assert (
        marked[0].text
        == "kaj is three finns singing in swedish. they really like saunas."
    )
    plain = pt.script_passages("One line here.\n\nAnother line here.", set())
    assert [p.script for p in plain] == ["One line here.", "Another line here."]
    with pytest.raises(pt.TakesError):
        pt.script_passages("  \n", set())


def test_every_take_is_listed_and_the_last_complete_one_is_suggested() -> None:
    takes = _takes(SESSION)
    first, second = takes["passages"]
    assert [t["complete"] for t in first["takes"]] == [True, False, True]
    assert first["suggestedTakes"] == ["passage-1-take-3"]
    assert first["takes"][1]["said"] == "kaj is three Finns"
    assert second["suggestedTakes"] == ["passage-2-take-1"]
    # Ten frames clear of speech on both sides, on whole frames.
    cut = first["takes"][2]["cut"]
    assert cut["startFrame"] == 15 * 30 - 10
    assert cut["framesClearOfSpeech"] == [10, 10]
    assert takes["approved"] is False if "approved" in takes else True


def test_off_script_speech_is_listed_never_dropped() -> None:
    takes = _takes(SESSION)
    assert [item["said"] for item in takes["offScript"]] == ["Sorry."]
    said = " ".join(
        [t["said"] for p in takes["passages"] for t in p["takes"]]
        + [o["said"] for o in takes["offScript"]]
    )
    assert sorted(said.split()) == sorted(word for word, _ in SESSION)
    report = pt.render_report(takes)
    assert "OFF-SCRIPT" in report and "Said: Sorry." in report
    assert "Time taken: 1 seconds" in report
    assert "<- SUGGESTED" in report


def test_unrelated_speech_is_off_script_not_a_take_full_of_substitutions() -> None:
    # Real case: the wrong script for a recording. Nothing may be matched.
    unrelated = (
        "In March the New Yorker published an essay by a novelist. She talks "
        "about how popular art seems to be abandoning anything ambiguous in "
        "favor of clear definitive statements about the world we live in."
    )
    takes = _takes(_said(unrelated, 2.0))
    assert all(p["takes"] == [] and not p["suggestedTakes"] for p in takes["passages"])
    said = " ".join(item["said"] for item in takes["offScript"])
    assert said.split() == unrelated.split()


def test_a_misread_word_is_reported_as_a_difference() -> None:
    misread = FIRST.replace("really", "truly")
    takes = _takes(_said(misread, 2.0))
    take = takes["passages"][0]["takes"][0]
    assert take["complete"]
    assert take["differences"]["substituted"] == [{"script": "really", "said": "truly"}]
    assert 'Differs: said "truly" for "really"' in pt.render_report(takes)


def test_a_passage_nobody_read_says_so() -> None:
    takes = _takes(_said(FIRST, 2.0))
    assert takes["passages"][1]["takes"] == []
    assert "NO TAKE FOUND" in pt.render_report(takes)


def test_no_quiet_next_to_the_speech_means_no_cut_not_a_guess() -> None:
    takes = _takes(_said(FIRST, 2.0), quiet=[])
    take = takes["passages"][0]["takes"][0]
    assert take["cut"] is None
    assert take["cutProblem"] == "no quiet gap next to the speech"
    assert "NO CLEAN CUT" in pt.render_report(takes)


def test_a_word_the_aligner_could_not_place_has_no_time() -> None:
    def unplace_first(alignment: Json) -> None:
        alignment["words"][0].update(startMs=None, endMs=None, status="unaligned")

    recognition, alignment = _artifacts(_said(FIRST, 2.0))
    recognition["tokens"][0].update(anchorStartMs=None, anchorEndMs=None)
    unplace_first(alignment)
    words = pt.timed_words(recognition, alignment)
    assert words[0]["start"] is None and words[0]["precision"] == "missing"
    assert words[1]["precision"] == "acoustic"


def test_aligner_dragged_onto_a_noise_falls_back_to_the_recogniser_time() -> None:
    # The aligner puts the take's first word two seconds early (on a sniff).
    def drag(alignment: Json) -> None:
        alignment["words"][0].update(startMs=0, endMs=100)

    takes = _takes(_said(FIRST, 2.0), alignment_edit=drag)
    take = takes["passages"][0]["takes"][0]
    assert take["speechStartS"] == 2.0
    assert take["approximateStart"] is True and take["approximateEnd"] is False
    assert takes["words"]["recogniserTimed"] == 1
    assert "CHECK BY EAR: start timed roughly" in pt.render_report(takes)


def test_quiet_intervals_need_sustained_low_level() -> None:
    rng = np.random.default_rng(0)
    sound = (rng.standard_normal(3 * pt.RATE) * 0.2).astype(np.float32)
    sound[pt.RATE : 2 * pt.RATE] = 0.0  # one silent second
    sound[int(2.5 * pt.RATE) : int(2.55 * pt.RATE)] = 0.0  # too short to count
    assert pt.quiet_intervals(sound, 3.0) == [[1.0, 2.0]]


def test_quiet_past_the_end_of_the_picture_does_not_lose_the_cuts() -> None:
    # The sound runs a little longer than the picture and ends in silence.
    sound = np.zeros(round(60.4 * pt.RATE), dtype=np.float32)
    quiet = pt.quiet_intervals(sound, DURATION)
    assert quiet == [[0.0, DURATION]]
    take = _takes(_said(FIRST, 2.0), quiet=quiet)["passages"][0]["takes"][0]
    assert take["cut"] is not None


def test_separate_audio_is_moved_onto_the_video_clock() -> None:
    separate = np.arange(100, 1100, dtype=np.float32)
    camera = np.zeros(400, dtype=np.float32)
    sound, uncovered = pt.shift_to_video(separate, 200 / pt.RATE, camera)
    assert sound[0] == 300 and sound[-1] == 699 and uncovered == []


def test_camera_sound_is_kept_where_the_separate_audio_does_not_reach() -> None:
    # The recorder started 0.1 s after the camera and stopped 0.2 s early.
    camera = np.full(pt.RATE, 7.0, dtype=np.float32)
    separate = np.ones(round(0.7 * pt.RATE), dtype=np.float32)
    sound, uncovered = pt.shift_to_video(separate, -0.1, camera)
    assert uncovered == [[0.0, 0.1], [0.8, 1.0]]
    assert sound[0] == 7.0 and sound[pt.RATE // 2] == 1.0 and sound[-1] == 7.0
    nothing, all_of_it = pt.shift_to_video(separate, 5.0, camera)
    assert all_of_it == [[0.0, 1.0]] and (nothing == camera).all()


def test_an_edit_note_withholds_the_plain_suggestion() -> None:
    session = [
        *_said(FIRST, 2.0),
        *_said(FIRST, 10.0),
        *_said("Actually the first take was better.", 16.0),
    ]
    takes = _takes(session)
    passage = takes["passages"][0]
    assert passage["choiceNeeded"] is True
    report = pt.render_report(takes)
    assert "<- LAST COMPLETE TAKE, but see the note below" in report
    assert "<- SUGGESTED" not in report
    assert "The choice is yours." in report


def test_unreadable_script_stops_with_a_plain_reason(tmp_path: Path) -> None:
    with pytest.raises(pt.TakesError, match="could not be read"):
        pt.read_script(tmp_path / "missing.rtf")
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(pt.TakesError, match="RTF or UTF-8"):
        pt.read_script(bad)
