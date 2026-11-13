"""One command lists every take in a presenter recording (#45)."""

from __future__ import annotations

import io
import zipfile
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
    "(on) KAJ [kai] is three Finns singing in Swedish. They really like saunas.\n"
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


def test_each_script_line_is_a_row_and_camera_marks_never_split_it() -> None:
    marked = pt.script_passages(SCRIPT, DICTIONARY)
    assert [(p.id, p.camera) for p in marked] == [("row-1", "on"), ("row-2", "off")]
    assert marked[0].text == (
        "kaj is three finns singing in swedish. they really like saunas."
    )
    mixed = pt.script_passages(
        "(on) They really like saunas. (off) The band wanted, (on) to embrace it.",
        DICTIONARY,
    )
    assert len(mixed) == 1 and mixed[0].camera == "mixed"
    assert mixed[0].cameras == ("on",) * 4 + ("off",) * 3 + ("on",) * 3
    plain = pt.script_passages("One line here.\n\nAnother line here.", set())
    assert [p.camera for p in plain] == ["unknown", "unknown"]
    with pytest.raises(pt.TakesError):
        pt.script_passages("  \n", set())


def test_every_take_is_listed_and_the_last_complete_one_is_suggested() -> None:
    takes = _takes(SESSION)
    first, second = takes["rows"]
    assert [t["complete"] for t in first["takes"]] == [True, False, True]
    assert first["suggestedTakes"] == ["row-1-take-3"]
    assert first["takes"][1]["said"] == "kaj is three Finns"
    assert second["suggestedTakes"] == ["row-2-take-1"]
    # Ten frames clear of speech on both sides, on whole frames.
    cut = first["takes"][2]["cut"]
    assert cut["startFrame"] == 15 * 30 - 10
    assert cut["framesClearOfSpeech"] == [10, 10]
    assert takes["approved"] is False if "approved" in takes else True


def test_off_script_speech_is_listed_never_dropped() -> None:
    takes = _takes(SESSION)
    assert [item["said"] for item in takes["offScript"]] == ["Sorry."]
    said = " ".join(
        [t["said"] for p in takes["rows"] for t in p["takes"]]
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
    assert all(p["takes"] == [] and not p["suggestedTakes"] for p in takes["rows"])
    said = " ".join(item["said"] for item in takes["offScript"])
    assert said.split() == unrelated.split()


def test_a_misread_word_is_reported_as_a_difference() -> None:
    misread = FIRST.replace("really", "truly")
    takes = _takes(_said(misread, 2.0))
    take = takes["rows"][0]["takes"][0]
    assert take["complete"]
    assert take["differences"]["substituted"] == [{"script": "really", "said": "truly"}]
    assert 'Differs: said "truly" for "really"' in pt.render_report(takes)


def test_a_passage_nobody_read_says_so() -> None:
    takes = _takes(_said(FIRST, 2.0))
    assert takes["rows"][1]["takes"] == []
    assert "NOT COVERED: nothing in the recording" in pt.render_report(takes)


def test_no_quiet_next_to_the_speech_means_no_cut_not_a_guess() -> None:
    takes = _takes(_said(FIRST, 2.0), quiet=[])
    take = takes["rows"][0]["takes"][0]
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
    take = takes["rows"][0]["takes"][0]
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
    take = _takes(_said(FIRST, 2.0), quiet=quiet)["rows"][0]["takes"][0]
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
    passage = takes["rows"][0]
    assert passage["choiceNeeded"] is True
    report = pt.render_report(takes)
    assert "<- SUGGESTED, but see the note below" in report
    assert "The choice is yours." in report


def test_unreadable_script_stops_with_a_plain_reason(tmp_path: Path) -> None:
    with pytest.raises(pt.TakesError, match="could not be read"):
        pt.read_script(tmp_path / "missing.rtf")
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(pt.TakesError, match="RTF or UTF-8"):
        pt.read_script(bad)


def _docx(rows: list[list[tuple[bool, str]]]) -> bytes:
    """A two-column Word table: narration runs (bold or not), then a notes cell."""
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = ""
    for row in rows:
        runs = "".join(
            f"<w:r><w:rPr>{'<w:b/>' if bold else ''}</w:rPr>"
            f'<w:t xml:space="preserve">{text}</w:t></w:r>'
            for bold, text in row
        )
        notes = "<w:tc><w:p><w:r><w:t>footage note</w:t></w:r></w:p></w:tc>"
        body += f"<w:tr><w:tc><w:p>{runs}</w:p></w:tc>{notes}</w:tr>"
    xml = (
        f'<w:document xmlns:w="{w}"><w:body><w:p><w:r><w:t>Title</w:t></w:r></w:p>'
        f"<w:tbl>{body}</w:tbl></w:body></w:document>"
    )
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return data.getvalue()


def test_word_script_rows_are_table_rows_and_bold_is_on_camera(
    tmp_path: Path,
) -> None:
    path = tmp_path / "script.docx"
    path.write_bytes(
        _docx(
            [
                [(True, "They really like saunas.")],
                [],  # a footage-only row has no narration
                [
                    (False, "The band wanted this. "),
                    (True, "But this was "),
                    (True, "Sweden."),
                ],
            ]
        )
    )
    assert pt.read_script(path) == (
        "(on) They really like saunas.\n"
        "(off) The band wanted this. (on) But this was Sweden.\n"
    )
    passages = pt.script_passages(pt.read_script(path), DICTIONARY)
    assert [(p.row, p.camera) for p in passages] == [(1, "on"), (2, "mixed")]


def test_word_script_without_bold_does_not_claim_a_camera_state() -> None:
    text = pt.docx_to_script(_docx([[(False, "One line here.")], [(False, "Two.")]]))
    assert text == "One line here.\nTwo.\n"
    assert [p.camera for p in pt.script_passages(text, set())] == ["unknown"] * 2
    with pytest.raises(pt.TakesError, match="Word document"):
        pt.docx_to_script(b"PK not a zip")


ON_CAMERA = "(on) They really like saunas. The band wanted to embrace the weirdness."


def _coverage_case(
    script: str, spoken: list[tuple[str, float]], last_take: bool = False
) -> Json:
    recognition, alignment = _artifacts(spoken)
    passages = pt.script_passages(script, DICTIONARY)
    words = pt.timed_words(recognition, alignment)
    report = refine(discover(pt.take_packet(words, alignment, passages, DURATION, FPS)))
    quiet = [[0.0, DURATION]]
    body = pt.build_takes(
        report, words, recognition, alignment, passages, quiet, DURATION, FPS, last_take
    )
    return {
        "video": {"file": "clip.mov", "durationS": DURATION, "fps": FPS},
        "script": {"file": "script.txt"},
        "sync": None,
        **body,
        "secondsTaken": 1.0,
    }


def test_no_whole_take_suggests_coverage_sentence_by_sentence() -> None:
    # Each sentence was read on its own; nobody read the passage straight through.
    takes = _coverage_case(
        ON_CAMERA,
        [
            *_said("They really like saunas.", 2.0),
            *_said("The band wanted to embrace the weirdness.", 10.0),
            *_said("The band wanted to embrace the weirdness.", 20.0),
        ],
    )
    passage = takes["rows"][0]
    assert passage["suggestedTakes"] == [] and passage["gaps"] == []
    first, second = passage["suggestedCoverage"]
    assert (first["takes"], first["scriptWords"]) == (["row-1-take-1"], [0, 4])
    assert (second["takes"], second["scriptWords"]) == (["row-1-take-3"], [4, 11])
    assert second["alternates"] == ["row-1-take-2"]
    assert second["cut"]["startFrame"] == 20 * 30 - 10
    report_text = pt.render_report(takes)
    assert "No single take covers this row. SUGGESTED CLIPS:" in report_text
    assert second["join"] == "visible" and "(JUMP CUT ON CAMERA)" in report_text
    # A project that allows jump cuts gets the same clips with no warning.
    allowed = pt.render_report({**takes, "allowJumpCuts": True})
    assert "JUMP CUT" not in allowed
    assert "Jump cuts: allowed" in allowed and "Jump cuts" not in report_text
    assert [line for line in allowed.splitlines() if "Script words" in line] == [
        line.replace("(JUMP CUT ON CAMERA) ", "")
        for line in report_text.splitlines()
        if "Script words" in line
    ]


def test_jump_cut_choice_long_takes_or_last_take_keeps_the_other_as_an_option() -> None:
    script = ON_CAMERA + " Three Finns singing in Swedish."
    spoken = [
        *_said(
            "They really like saunas. The band wanted to embrace the weirdness.", 2.0
        ),
        *_said(
            "The band wanted to embrace the weirdness. Three Finns singing in Swedish.",
            20.0,
        ),
    ]
    long_takes = _coverage_case(script, spoken)["rows"][0]["suggestedCoverage"]
    last_take = _coverage_case(script, spoken, last_take=True)["rows"][0][
        "suggestedCoverage"
    ]
    # Long takes: stay in the first take until it runs out.
    assert [(p["takes"], p["scriptWords"]) for p in long_takes] == [
        (["row-1-take-1", "row-1-take-2"], [0, 11]),
        (["row-1-take-3", "row-1-take-4"], [11, 16]),
    ]
    # Last take: the later read of the middle sentence wins.
    assert [(p["takes"], p["scriptWords"]) for p in last_take] == [
        (["row-1-take-1", "row-1-take-2"], [0, 4]),
        (["row-1-take-3", "row-1-take-4"], [4, 16]),
    ]
    # Either way the read not chosen is still offered.
    middle = [4, 11]
    assert long_takes[0]["otherReads"] == [
        {"scriptWords": middle, "takes": ["row-1-take-3", "row-1-take-4"]}
    ]
    assert last_take[1]["otherReads"] == [
        {"scriptWords": middle, "takes": ["row-1-take-1", "row-1-take-2"]}
    ]


def test_last_take_uses_a_one_sentence_pickup_after_a_whole_read() -> None:
    whole = "They really like saunas. The band wanted to embrace the weirdness."
    spoken = [*_said(whole, 2.0), *_said("They really like saunas.", 20.0)]
    kept = _coverage_case(ON_CAMERA, spoken)
    row = kept["rows"][0]
    # By default the whole read stays whole and the pickup is only on record.
    assert row["suggested"] and row["suggestedCoverage"] == []
    assert [o["scriptWords"] for o in row["suggested"]["otherReads"]] == [[0, 4]]
    chopped = _coverage_case(ON_CAMERA, spoken, last_take=True)
    row = chopped["rows"][0]
    assert row["suggested"] is None and row["gaps"] == []
    pickup, rest = row["suggestedCoverage"]
    assert (
        pickup["scriptWords"] == [0, 4] and pickup["cut"]["startFrame"] > 20 * 30 - 15
    )
    assert rest["scriptWords"] == [4, 11] and rest["join"] == "visible"
    assert rest["takes"] == row["alternateReads"][0]["takes"]  # the whole read
    assert [(c["row"], c["join"]) for c in chopped["suggestedEdit"]] == [
        (1, None),
        (1, "visible"),
    ]
    assert "reads the whole row" in pt.render_report(chopped)
    # With no pickup, last take leaves the whole read alone.
    alone = _coverage_case(ON_CAMERA, _said(whole, 2.0), last_take=True)["rows"][0]
    assert alone["suggested"] and alone["suggestedCoverage"] == []


def test_a_whole_off_camera_take_is_never_cut_up_by_sentence() -> None:
    script = "(off) They really like saunas. The band wanted to embrace the weirdness."
    read = "They really like saunas. The band wanted to embrace the weirdness."
    takes = _coverage_case(script, _said(read, 2.0))
    passage = takes["rows"][0]
    assert len(passage["takes"]) == 1 and passage["takes"][0]["complete"]
    assert passage["suggestedTakes"] == ["row-1-take-1"]
    assert passage["suggestedCoverage"] == []


def test_a_sentence_nobody_finished_is_a_gap_with_the_unsaid_words() -> None:
    takes = _coverage_case(
        ON_CAMERA,
        [
            *_said("They really like saunas.", 2.0),
            *_said("The band wanted to", 10.0),
        ],
    )
    passage = takes["rows"][0]
    assert [p["scriptWords"] for p in passage["suggestedCoverage"]] == [[0, 4]]
    (gap,) = passage["gaps"]
    assert gap["scriptWords"] == [4, 11]
    assert gap["notCovered"] == ["embrace", "the", "weirdness"]
    assert "NOT COVERED: embrace the weirdness" in pt.render_report(takes)


def test_a_few_changed_words_are_differences_not_an_incomplete_passage() -> None:
    # The presenter changes one word and adds another; strict matching refuses.
    altered = "The group wanted to really embrace the weirdness."
    takes = _takes(_said(altered, 2.0))
    passage = takes["rows"][1]
    take = passage["takes"][0]
    assert take["complete"] is False and take["wholePassage"] is True
    assert passage["suggestedTakes"] == [take["id"]]
    assert passage["suggestedCoverage"] == [] and passage["gaps"] == []
    changes = passage["suggested"]["differences"]
    assert changes["substituted"] == [{"script": "band", "said": "group"}]
    assert changes["added"] == ["really"] and changes["omitted"] == []
    assert 'Differs: said "group" for "band"' in pt.render_report(takes)
    assert "complete, with wording changes" in pt.render_report(takes)


def test_a_later_take_with_no_clean_cut_is_passed_over_for_one_that_has() -> None:
    # Quiet surrounds the first read only; the second runs straight into noise.
    takes = _takes(
        [*_said(FIRST, 2.0), *_said(FIRST, 10.0)], quiet=[[0.0, 1.9], [5.0, 9.5]]
    )
    passage = takes["rows"][0]
    assert passage["takes"][1]["cut"] is None
    assert passage["suggestedTakes"] == ["row-1-take-1"]
    assert [r["takes"] for r in passage["alternateReads"]] == [["row-1-take-2"]]
    assert passage["takes"][1]["alternate"] is True
    assert "Take 2 is later, but it changes or drops an end word or has no clean" in (
        pt.render_report(takes)
    )


def test_a_read_split_at_an_unmatched_word_is_put_back_together() -> None:
    # "kinda" for "kind of": the take rules split the read there.
    script = "(on) In fact the band was kind of wanted to embrace the weirdness."
    takes = _coverage_case(
        script,
        _said("In fact the band was kinda wanted to embrace the weirdness.", 2.0),
    )
    passage = takes["rows"][0]
    read = passage["suggested"]
    assert read is not None and passage["gaps"] == []
    assert read["speechStartS"] == 2.0 and read["said"].endswith("weirdness.")
    assert read["differences"]["added"] == ["kinda"]
    assert read["differences"]["omitted"] == ["kind", "of"]


def test_a_countdown_before_the_read_is_left_out_of_the_suggested_cut() -> None:
    spoken = [*_said("Three two", 2.0), *_said(SECOND, 2.6)]
    takes = _takes(spoken)
    read = takes["rows"][1]["suggested"]
    assert read["said"] == SECOND and read["speechStartS"] == 2.6


def test_a_dropped_last_word_is_a_difference_not_a_gap() -> None:
    script = "(off) They really like saunas a lot okay."
    takes = _coverage_case(script, _said("They really like saunas a lot.", 2.0))
    passage = takes["rows"][0]
    assert passage["gaps"] == [] and passage["suggested"] is not None
    assert passage["suggested"]["differences"]["omitted"] == ["okay"]
    assert passage["suggested"]["exact"] is False


CUTAWAY = (
    "(on) They really like saunas. (off) The band wanted to embrace, "
    "(on) the weirdness in Swedish."
)
CUTAWAY_READ = (
    "They really like saunas. The band wanted to embrace the weirdness in Swedish."
)


def test_a_cutaway_inside_a_continuous_take_is_one_clip_with_a_voiceover_range() -> (
    None
):
    takes = _coverage_case(CUTAWAY, _said(CUTAWAY_READ, 2.0))
    (row,) = takes["rows"]
    assert row["suggestedCoverage"] == [] and row["suggested"]["takes"] == [
        "row-1-take-1"
    ]
    (clip,) = takes["suggestedEdit"]
    assert clip["join"] is None and clip["cleanCut"] is True
    # Footage covers "The band wanted to embrace": words five to nine.
    assert clip["voiceover"] == [[pytest.approx(3.2), pytest.approx(4.7)]]


def test_a_restart_inside_voiceover_is_joined_where_footage_hides_it() -> None:
    spoken = [
        *_said("They really like saunas. The band wanted", 2.0),
        *_said("The band wanted to embrace the weirdness in Swedish.", 10.0),
    ]
    takes = _coverage_case(CUTAWAY, spoken)
    first, second = takes["suggestedEdit"]
    assert first["takes"] == ["row-1-take-1", "row-1-take-2"]
    assert first["endS"] < 3.3  # stops before the abandoned restart
    assert second["takes"] == ["row-1-take-3"]
    assert second["join"] == "hidden"
    report = pt.render_report(takes)
    assert "(join hidden by footage)" in report and "JUMP CUT" not in report


def test_a_whole_row_with_no_marks_has_no_voiceover_and_no_join_claim() -> None:
    takes = _coverage_case(CUTAWAY_READ, _said(CUTAWAY_READ, 2.0))
    (clip,) = takes["suggestedEdit"]
    assert clip["voiceover"] == [] and takes["rows"][0]["camera"] == "unknown"
