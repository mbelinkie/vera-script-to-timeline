"""Issue-owned fictional cases; no private Run A data or accepted fixture edits."""

from copy import deepcopy
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from experiments.issue53.cli import write_private
from experiments.issue53.takes import discover, evaluate, evaluate_words, tokens


def packet(reads: list[str], rows: list[str] | None = None) -> dict[str, Any]:
    words = []
    t = 2.0
    for read in reads:
        for word in read.split():
            words.append(
                {
                    "text": word,
                    "start": t,
                    "end": t + 0.25,
                    "precision": "acoustic",
                    "provenance": "fictional",
                }
            )
            t += 0.3
        t += 2
    return {
        "version": "take-experiment/1",
        "source": {"alias": "fictional", "duration": t + 2, "fps": [24000, 1001]},
        "rows": [
            {"id": f"row-{i + 1}", "text": s, "beat_ids": []}
            for i, s in enumerate(
                rows or ["Open the blue gate. Walk toward the beacon."]
            )
        ],
        "words": words,
        "provenance": {"adapter": "fake", "version": "1"},
        "audio_activity": [],
        "decisions": {},
    }


ROW = "Open the blue gate. Walk toward the beacon."


def test_last_whole_row_and_earlier_alternatives() -> None:
    p = packet([ROW, ROW, "Open the blue"])
    before = deepcopy(p)
    report = discover(p)
    g = report["groups"][0]
    assert [c["kind"] for c in report["candidates"]] == [
        "complete",
        "complete",
        "partial",
    ]
    assert g["default"] == "candidate-002"
    assert g["alternatives"] == ["candidate-001"]
    assert report["candidates"][0]["word_range"] == [0, 8]
    assert p == before
    assert not report["keeper_approved"]


def test_partial_assembly_is_only_review_proposal() -> None:
    report = discover(packet(["Open the blue gate", "Walk toward the beacon"]))
    g = report["groups"][0]
    assert g["default"] is None
    assert g["assembly"]["status"] == "review_needed"
    assert len(g["assembly"]["pieces"]) == 2
    assert g["assembly"]["uncovered_token_indices"] == []


def test_restart_is_not_a_complete_read() -> None:
    r = discover(packet(["Open the blue Open the blue gate Walk toward the beacon"]))
    assert [c["kind"] for c in r["candidates"]] == ["partial", "complete"]
    assert r["groups"][0]["default"] == "candidate-002"


def test_repeated_phrase_inside_the_row_is_not_a_restart() -> None:
    row = "We go now and we go now again"
    r = discover(packet([row, row], [row]))
    assert [c["kind"] for c in r["candidates"]] == ["complete", "complete"]
    assert r["groups"][0]["default"] == "candidate-002"


@pytest.mark.parametrize(
    "read", ["Actually open the blue gate", "Open the blue gate today"]
)
def test_exact_substring_inside_an_adlib_is_not_a_clean_take(read: str) -> None:
    r = discover(packet([read], ["Open the blue gate"]))
    assert len(r["candidates"]) == 1
    assert r["candidates"][0]["match"] == "approximate"
    assert r["candidates"][0]["kind"] == "modified_read"
    assert r["groups"][0]["default"] is None


def test_adlib_flub_uncovered_and_every_word_visible() -> None:
    r = discover(
        packet(
            [ROW, "Open the red gate Walk toward the beacon", "Please stop now"],
            [ROW, "Bring a lantern before midnight"],
        )
    )
    assert r["groups"][1]["state"] == "uncovered"
    assert any(c["match"] == "approximate" for c in r["candidates"])
    assert any(c["kind"] == "unmatched" for c in r["candidates"])
    assert r["coverage"]["word_accounting_complete"]
    for c in r["candidates"]:
        if c["match"] == "exact":
            assert all(op["op"] == "equal" for op in c["diff"])


def test_ambiguous_rows_do_not_receive_defaults() -> None:
    r = discover(packet([ROW], [ROW, ROW]))
    assert len(r["candidates"][0]["row_options"]) == 2
    assert all(g["default"] is None and g["state"] == "ambiguous" for g in r["groups"])


@pytest.mark.parametrize("precision", ["acoustic", "cue", "missing", "derived"])
def test_same_logic_preserves_missing_and_coarse_timing(precision: str) -> None:
    p = packet([ROW, ROW])
    for w in p["words"]:
        w["precision"] = precision
        if precision == "missing":
            w["start"] = w["end"] = None
    r = discover(p)
    assert len(r["candidates"]) == 2
    assert r["coverage"]["word_accounting_complete"]
    assert all(c["handles"]["status"] == "review_needed" for c in r["candidates"])
    if precision != "acoustic":
        assert all(
            "unproven_word_timing" in c["handles"]["reasons"] for c in r["candidates"]
        )


def test_bad_timing_is_visible_not_silently_reordered() -> None:
    p = packet([ROW])
    p["words"][2]["end"] = -1
    r = discover(p)
    assert r["candidates"][0]["timing_issues"]
    assert r["groups"][0]["default"] is None


def test_ten_frames_fractional_rate_and_source_limit() -> None:
    p = packet([ROW])
    c = discover(p)["candidates"][0]
    assert c["handles"]["requested_frames"] == 10
    assert c["handles"]["range"][0] <= c["speech_range"][0] - 10 * 1001 / 24000
    p["words"][0]["start"] = 0.1
    c = discover(p)["candidates"][0]
    assert "source_limit" in c["handles"]["reasons"]
    assert c["handles"]["range"] is None


def test_adjacent_take_blocks_handles() -> None:
    p = packet([ROW, "Stop now"], [ROW, "Stop now"])
    start = p["words"][7]["end"] + 0.1
    for i, w in enumerate(p["words"][8:]):
        w["start"] = start + i * 0.3
        w["end"] = w["start"] + 0.25
    c = discover(p)["candidates"][0]
    assert "adjacent_speech" in c["handles"]["reasons"]
    assert c["handles"]["range"] is None


def test_audio_activity_does_not_certify_silence() -> None:
    p = packet([ROW])
    p["audio_activity"] = [{"start": 1.7, "end": 1.9, "method": "energy"}]
    c = discover(p)["candidates"][0]
    assert "audio_activity_in_handle" in c["handles"]["reasons"]
    assert c["handles"]["status"] == "review_needed"


def test_existing_producer_decision_is_preserved() -> None:
    p = packet([ROW, ROW])
    p["decisions"] = {"row-1": {"locked": True, "candidate": "previous-version"}}
    r = discover(p)
    assert r["decisions"] == p["decisions"]
    assert r["groups"][0]["default"] is None
    assert r["groups"][0]["suggested_last_complete"] == "candidate-002"


def test_reference_not_accepted_by_discovery_and_evaluation_cannot_change_it() -> None:
    p = packet([ROW])
    p["reference"] = {"times": [1, 8]}
    with pytest.raises(ValueError, match="reference"):
        discover(p)
    del p["reference"]
    r = discover(p)
    before = deepcopy(r)
    e = evaluate(
        r,
        [
            {"id": "truth-1", "start": 1, "end": 6},
            {"id": "truth-2", "start": 9, "end": 10},
            {"id": "truth-3", "start": None, "end": None},
        ],
    )
    assert e["reference_cases"] == 3
    assert e["missed"] == ["truth-2"]
    assert e["uncertain"] == ["truth-3"]
    assert r == before


def test_normalization_is_lexical_not_semantic() -> None:
    assert tokens("THE blue-gate, isn\u2019t closed.") == [
        "the",
        "blue",
        "gate",
        "isn't",
        "closed",
    ]
    assert tokens("twenty") != tokens("20")


def test_missing_word_time_does_not_discard_last_complete_row() -> None:
    p = packet([ROW, ROW])
    p["words"][10]["start"] = p["words"][10]["end"] = None
    p["words"][10]["precision"] = "missing"
    r = discover(p)
    assert r["groups"][0]["default"] == "candidate-002"
    assert r["candidates"][1]["handles"]["range"] is None
    assert r["groups"][0]["assembly"] is None


def test_backward_timing_between_candidates_prevents_default() -> None:
    p = packet([ROW, ROW])
    for w in p["words"][8:]:
        w["start"] -= 4
        w["end"] -= 4
    r = discover(p)
    assert r["groups"][0]["default"] is None
    assert all("source_order_conflict" in c["timing_issues"] for c in r["candidates"])


def test_whole_recording_accounting_includes_unrecognized_audio() -> None:
    p = packet([ROW])
    r = discover(p)
    intervals = r["coverage"]["source_intervals"]
    assert intervals[0]["range"][0] == 0
    assert intervals[-1]["range"][1] == p["source"]["duration"]
    assert all(a["range"][1] == b["range"][0] for a, b in pairwise(intervals))
    assert intervals[0]["state"] == "unassigned_audio_review"


def test_evaluation_reports_splits_merges_and_recognition_separately() -> None:
    r = discover(packet([ROW, ROW]))
    e = evaluate(
        r,
        [
            {"id": "coarse", "start": 1, "end": 10},
            {"id": "overlap", "start": 2, "end": 4},
        ],
    )
    assert e["possible_false_splits"]
    assert e["possible_merges"]
    lexical = evaluate_words(
        r, tokens(ROW + " " + ROW), [{"id": "both", "indices": list(range(16))}]
    )
    assert lexical["operation_counts"]["equal"] == 16
    assert len(lexical["cases"][0]["candidates"]) == 2


def test_exclusive_private_outputs_and_git_boundary(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    write_private(output, {"safe": False})
    assert output.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_private(output, {"overwrite": True})
    (tmp_path / ".git").mkdir()
    with pytest.raises(ValueError, match="outside Git"):
        write_private(tmp_path / "other.json", {})
