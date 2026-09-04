"""Fictional regressions from Producer review; no private transcript or labels."""

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from experiments.issue53.takes import discover
from experiments.issue53.timing_links import link_word_timing


def sample(reads: list[str], rows: list[str]) -> dict[str, Any]:
    return {
        "version": "take-experiment/1",
        "source": {"alias": "fictional", "duration": 120, "fps": [24, 1]},
        "rows": [
            {"id": f"row-{i}", "text": row, "beat_ids": []}
            for i, row in enumerate(rows)
        ],
        "words": [
            {
                "text": word,
                "start": None,
                "end": None,
                "precision": "missing",
                "provenance": "accurate-fictional",
            }
            for read in reads
            for word in read.split()
        ],
        "audio_activity": [],
        "provenance": {"variant": "unlabelled"},
        "decisions": {},
    }


def test_changed_opening_name_stays_a_whole_approximate_read() -> None:
    row = "Orion brings the lantern across the frozen lake tonight"
    r = discover(sample([row.replace("Orion", "Orian")] * 2, [row]))
    assert len(r["candidates"]) == 2
    assert all(
        c["kind"] == "complete" and c["match"] == "approximate" for c in r["candidates"]
    )
    assert r["groups"][0]["default"] == r["candidates"][-1]["id"]


def test_restart_of_second_sentence_produces_reviewable_pieces() -> None:
    first = "We sail toward the distant island."
    second = "Then the old beacon lights our way."
    r = discover(
        sample([first, "Then the old", second, second], [first + " " + second])
    )
    g = r["groups"][0]
    assert g["default"] is None
    assert g["assembly"]["uncovered_token_indices"] == []
    assert [len(piece["row_token_indices"]) for piece in g["assembly"]["pieces"]] == [
        6,
        7,
    ]
    assert len(g["partial_alternatives"]) >= 3
    assert not r["keeper_approved"]


def test_partial_alternate_survives_complete_default() -> None:
    row = "Open the blue gate. Walk toward the beacon."
    r = discover(sample(["Open the blue gate.", row, row], [row]))
    g = r["groups"][0]
    assert g["default"]
    assert len(g["alternatives"]) == 1
    assert len(g["partial_alternatives"]) == 1
    partial = g["partial_alternatives"][0]
    assert partial["covered_token_indices"] == [0, 1, 2, 3]
    assert partial["missing_token_indices"] == [4, 5, 6, 7]


def test_spoken_first_take_reference_is_a_flag_not_a_command() -> None:
    row = "The beacon glows above the quiet harbor."
    p = sample([row, row, "I think the first take was the one."], [row])
    before = deepcopy(p)
    r = discover(p)
    flag = r["editorial_signals"][0]
    g = r["groups"][0]
    assert flag["target"] == "first"
    assert flag["earlier_candidate_options"] == [r["candidates"][0]["id"]]
    assert flag["status"] == "producer_choice_required"
    assert g["suggested_last_complete"] == r["candidates"][1]["id"]
    assert g["default"] is None
    assert p == before and not r["keeper_approved"]


def test_take_reference_in_script_does_not_create_editorial_signal() -> None:
    row = "We describe how the first take changed the ending."
    r = discover(sample([row, row], [row]))
    assert r["editorial_signals"] == []
    assert r["groups"][0]["default"]


def test_negative_or_ambiguous_reference_never_auto_selects() -> None:
    row = "The beacon glows above the quiet harbor."
    r = discover(sample([row, row, "Do not use the earlier take."], [row]))
    flag = r["editorial_signals"][0]
    assert flag["negation_detected"]
    assert flag["status"] == "producer_choice_required"
    assert r["groups"][0]["default"] is None


def test_existing_producer_choice_survives_spoken_reference() -> None:
    row = "The beacon glows above the quiet harbor."
    p = sample([row, row, "The first take was better."], [row])
    p["decisions"] = {"row-0": {"locked": True, "candidate": "prior-version"}}
    r = discover(p)
    assert r["decisions"] == p["decisions"]
    assert r["groups"][0]["default"] is None


def test_continuous_delivery_crossing_rows_does_not_merge_their_defaults() -> None:
    rows = [
        "The beacon glows above the quiet harbor.",
        "We leave before the morning storm.",
    ]
    r = discover(sample([" ".join(rows)], rows))
    assert all(g["default"] for g in r["groups"])
    assert r["coverage"]["word_accounting_complete"]


def test_substitution_in_partial_assembly_is_retained_and_flagged() -> None:
    first = "We sail toward the distant island."
    second = "Then the old beacon lights our way."
    r = discover(
        sample(
            [first, "Then the old", second.replace("beacon", "lantern")],
            [first + " " + second],
        )
    )
    assembly = r["groups"][0]["assembly"]
    assert assembly["status"] == "review_needed"
    assert assembly["uncovered_token_indices"] == []
    assert any(piece["transcript_diff"] for piece in assembly["pieces"])


def test_partial_setting_hides_list_without_dropping_evidence() -> None:
    row = "Open the blue gate. Walk toward the beacon."
    p = sample(["Open the blue gate", row], [row])
    visible = discover(p)
    p["options"] = {"include_partial_alternates": False}
    hidden = discover(p)
    assert hidden["groups"][0]["partial_alternatives"] == []
    assert hidden["groups"][0]["hidden_partial_count"] == 1
    assert hidden["candidates"] == visible["candidates"]
    assert hidden["groups"][0]["default"] == visible["groups"][0]["default"]


def test_partial_setting_does_not_disable_missing_row_assembly() -> None:
    p = sample(
        [
            "Open the blue gate",
            "Let me restart the next sentence",
            "Walk toward the beacon",
        ],
        ["Open the blue gate. Walk toward the beacon."],
    )
    p["options"] = {"include_partial_alternates": False}
    r = discover(p)
    assert r["groups"][0]["assembly"]["pieces"]
    assert r["groups"][0]["partial_alternatives"] == []


def test_cli_partial_setting(tmp_path: Path) -> None:
    p = sample(
        ["Open the blue gate", "Open the blue gate. Walk toward the beacon."],
        ["Open the blue gate. Walk toward the beacon."],
    )
    source = tmp_path / "input.json"
    source.write_text(json.dumps(p))
    for setting in ["hide", "include"]:
        output = tmp_path / f"{setting}.json"
        run = subprocess.run(
            [
                sys.executable,
                "-m",
                "experiments.issue53.cli",
                "--input",
                str(source),
                "--output",
                str(output),
                "--partial-takes",
                setting,
            ],
            capture_output=True,
        )
        assert run.returncode == 0
        report = json.loads(output.read_text())
        assert bool(report["groups"][0]["partial_alternatives"]) == (
            setting == "include"
        )


def test_quoted_offscript_preference_is_never_automatically_applied() -> None:
    row = "The beacon glows above the quiet harbor."
    r = discover(sample([row, row, 'Someone said "the first take" as a joke.'], [row]))
    assert r["editorial_signals"][0]["automatically_applied"] is False
    assert r["groups"][0]["default"] is None


def test_word_timing_uses_unique_retained_words_without_clock_interpolation() -> None:
    retained = [
        {"token": w, "start": i, "end": i + 0.5, "precision": "acoustic"}
        for i, w in enumerate(["open", "the", "gate"])
    ]
    linked = link_word_timing(["open", "the", "blue", "gate"], retained)
    assert linked[0]["start"] == 0
    assert linked[2]["start"] is None
    assert linked[3]["start"] == 2
    assert not any(x["acoustically_verified"] for x in linked)


def test_repeated_word_mapping_ambiguity_never_borrows_a_timestamp() -> None:
    retained = [
        {"token": w, "start": i, "end": i + 0.5, "precision": "acoustic"}
        for i, w in enumerate(["go", "go", "now"])
    ]
    linked = link_word_timing(["go", "now"], retained)
    assert linked[0]["start"] is None
    assert linked[1]["start"] == 2


def test_changed_word_does_not_inherit_other_words_timestamp() -> None:
    retained = [{"token": "red", "start": 2, "end": 3, "precision": "acoustic"}]
    assert link_word_timing(["blue"], retained)[0]["start"] is None


def test_spoken_edit_note_is_not_attached_to_the_row_even_without_a_pause() -> None:
    row = "The beacon glows above the quiet harbor."
    p = sample([row, row, "The first take was better."], [row])
    for i, w in enumerate(p["words"]):
        w.update(start=2 + i * 0.3, end=2 + i * 0.3 + 0.25, precision="acoustic")
    r = discover(p)
    assert [c["kind"] for c in r["candidates"]] == ["complete", "complete", "unmatched"]
    assert r["editorial_signals"][0]["earlier_candidate_options"] == ["candidate-001"]
