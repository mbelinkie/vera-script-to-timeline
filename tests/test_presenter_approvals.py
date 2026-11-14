"""Invented #45 reports: no recordings, transcripts or private file paths."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.presenter_approvals import (
    ApprovalError,
    approved_performance,
    approved_performance_text,
    available_choices,
    checked_trim,
    choose_approval,
    frame_rate,
    freeze_read,
    full_reads,
    load_approvals,
    load_takes,
    match_frozen_read,
    row_context,
    source_identity,
    undo_approval,
    validate_approvals,
    validate_takes,
    write_performance_reports,
)
from vera_timeline_agent.presenter_approvals_cli import main as approval_main
from vera_word_timing.artifacts import file_hash

Json = dict[str, Any]
SHA = "sha256:" + "a" * 64
OTHER_SHA = "sha256:" + "b" * 64
VIDEO = {"file": "made-up.mov", "durationS": 12.0, "fps": [30, 1]}
DIFFERENCES: Json = {"moved": [], "substituted": [], "added": [], "omitted": []}


def _read(
    start: int = 60,
    end: int = 120,
    *,
    ids: list[str] | None = None,
    said: str = "Three spoken words",
    word_range: list[int] | None = None,
    speech: tuple[float, float] = (2.4, 3.6),
) -> Json:
    return {
        "takes": ids if ids is not None else ["row-1-take-1"],
        "scriptWords": word_range if word_range is not None else [0, 3],
        "cut": {
            "startFrame": start,
            "endFrame": end,
            "startS": start / 30,
            "endS": end / 30,
            "framesClearOfSpeech": [8, 8],
        },
        "speechStartS": speech[0],
        "speechEndS": speech[1],
        "approximateStart": False,
        "approximateEnd": False,
        "said": said,
        "differences": copy.deepcopy(DIFFERENCES),
    }


def _raw(
    ident: str = "row-1-take-1",
    *,
    covered: int = 3,
    whole: bool = False,
    **kwargs: Any,
) -> Json:
    read = _read(**kwargs)
    return {
        **read,
        "id": ident,
        "number": 1,
        "scriptWordsCovered": covered,
        "scriptWords": 3,
        "complete": True,
        "wholePassage": whole,
    }


def _report() -> Json:
    return {
        "schemaVersion": "presenter-takes/1",
        "video": copy.deepcopy(VIDEO),
        "script": {"file": "invented.txt"},
        "approved": False,
        "allowJumpCuts": False,
        "jumpCutChoice": None,
        "rows": [
            {
                "id": "row-1",
                "number": 1,
                "row": 1,
                "script": "Three spoken words",
                "takes": [_raw()],
                "suggested": _read(),
                "alternateReads": [],
                "suggestedCoverage": [],
                "gaps": [],
            },
            {
                "id": "row-2",
                "number": 2,
                "row": 2,
                "script": "Other short passage",
                "takes": [],
                "suggested": None,
                "alternateReads": [],
                "suggestedCoverage": [],
                "gaps": [],
            },
        ],
        "offScript": [],
        "suggestedEdit": [],
    }


def _frozen(takes: Json | None = None, *, trim: tuple[int, int] | None = None) -> Json:
    document = takes or _report()
    return freeze_read(
        document,
        "row-1",
        full_reads(document["rows"][0], document["video"])[0],
        SHA,
        trim,
    )


def test_strict_version_order_and_raw_take_identity() -> None:
    data = _report()
    assert validate_takes(data) is data
    assert row_context(data) == [
        ["row-1", "Three spoken words"],
        ["row-2", "Other short passage"],
    ]
    assert len(full_reads(data["rows"][0], data["video"])) == 1
    data["rows"][1]["id"] = "row-1"
    with pytest.raises(ApprovalError, match="passage IDs"):
        validate_takes(data)
    data["rows"][1]["id"] = "row-2"
    data["rows"][0]["takes"].append(copy.deepcopy(data["rows"][0]["takes"][0]))
    with pytest.raises(ApprovalError, match="duplicate raw take"):
        validate_takes(data)


def test_compound_continuous_read_is_eligible_but_assembled_coverage_is_not() -> None:
    data = _report()
    first = data["rows"][0]
    first["takes"] = [
        _raw("row-1-take-1", covered=2),
        _raw("row-1-take-2", covered=1),
    ]
    first["suggested"] = _read(ids=["row-1-take-1", "row-1-take-2"])
    assert len(full_reads(first, data["video"])) == 1
    assert full_reads(first, data["video"])[0]["takes"] == [
        "row-1-take-1",
        "row-1-take-2",
    ]
    first["suggestedCoverage"] = [
        _read(word_range=[0, 1]),
        _read(word_range=[1, 3]),
    ]
    first["suggested"] = None
    assert full_reads(first, data["video"]) == []
    with pytest.raises(ApprovalError, match="eligible complete"):
        freeze_read(data, "row-1", first["suggestedCoverage"][0], SHA)


def test_partial_uncuttable_approximate_and_raw_fragment_are_not_promoted() -> None:
    data = _report()
    row = data["rows"][0]
    row["suggested"] = _read(word_range=[0, 2])
    assert full_reads(row, data["video"]) == []
    row["suggested"] = _read()
    row["suggested"]["cut"] = None
    row["suggested"]["speechStartS"] = None
    assert validate_takes(data) == data  # normal #45 unplaced first word
    assert available_choices(data)[0]["reads"] == []
    row["suggested"]["speechStartS"] = 2.4
    assert full_reads(row, data["video"]) == []
    row["suggested"] = _read()
    row["takes"][0]["wholePassage"] = True
    row["takes"][0]["scriptWordsCovered"] = 2
    assert len(full_reads(row, data["video"])) == 1
    row["suggested"]["approximateStart"] = True
    assert len(full_reads(row, data["video"])) == 1
    with pytest.raises(ApprovalError, match="roughly timed"):
        checked_trim(data["video"], row["suggested"], 70, 110)


def test_raw_full_read_only_when_all_script_words_covered() -> None:
    data = _report()
    row = data["rows"][0]
    row["suggested"] = None
    row["takes"][0]["wholePassage"] = True
    row["takes"][0]["scriptWordsCovered"] = 2
    assert full_reads(row, data["video"]) == []
    row["takes"][0]["scriptWordsCovered"] = 3
    assert len(full_reads(row, data["video"])) == 1


def test_alternates_are_not_rank_approvals_and_ambiguous_anchors_refuse() -> None:
    data = _report()
    row = data["rows"][0]
    row["takes"].append(
        _raw("row-1-take-2", covered=2, start=150, end=240, speech=(5.3, 7.1))
    )
    row["alternateReads"] = [
        _read(start=150, end=240, ids=["row-1-take-2"], speech=(5.3, 7.1))
    ]
    assert len(full_reads(row, data["video"])) == 2
    row["alternateReads"][0]["cut"] = copy.deepcopy(row["suggested"]["cut"])
    row["alternateReads"][0]["speechStartS"] = 2.4
    row["alternateReads"][0]["speechEndS"] = 3.6
    row["alternateReads"][0]["said"] = "Three other words"
    with pytest.raises(ApprovalError, match="conflicting reads"):
        full_reads(row, data["video"])


def test_bad_source_rate_duration_sha_and_bounds_are_rejected() -> None:
    data = _report()
    assert str(frame_rate(data["video"])) == "30"
    assert source_identity(data["video"], SHA)["sha256"] == SHA
    for rate in ([0, 1], [30, 0], [True, 1], [29.97, 1], [30], "30"):
        data["video"]["fps"] = rate
        with pytest.raises(ApprovalError):
            validate_takes(data)
    data["video"]["fps"] = [30, 1]
    for duration in (-1, 0, True, float("nan"), float("inf")):
        data["video"]["durationS"] = duration
        with pytest.raises(ApprovalError):
            validate_takes(data)
    data["video"]["durationS"] = 12.0
    for digest in ("bad", "sha256:abc", "sha256:" + "Z" * 64):
        with pytest.raises(ApprovalError, match="sha256"):
            source_identity(data["video"], digest)
    data["rows"][0]["suggested"]["cut"]["endFrame"] = 500
    with pytest.raises(ApprovalError, match="outside recording"):
        validate_takes(data)


def test_invalid_json_never_falls_back_to_empty_report(tmp_path: Path) -> None:
    path = tmp_path / "takes.json"
    path.write_text('{"schemaVersion":"presenter-takes/1","video":{},"video":{}}')
    with pytest.raises(ApprovalError, match="duplicate JSON key"):
        load_takes(path)
    path.write_text('{"durationS":NaN}')
    with pytest.raises(ApprovalError, match="non-finite"):
        load_takes(path)
    path.write_text('{"schemaVersion":')
    with pytest.raises(ApprovalError, match="cannot read"):
        load_takes(path)
    path.write_text(json.dumps(_report()))
    assert load_takes(path)["schemaVersion"] == "presenter-takes/1"


def test_trim_rejects_speech_edges_original_handles_and_bad_types() -> None:
    read = _read()
    assert checked_trim(VIDEO, read, 70, 110) == (70, 110)
    for a, b, reason in (
        (73, 110, "speech"),
        (70, 108, "speech"),
        (-1, 110, "integer"),
        (70, 121, "outside"),
        (True, 110, "integer"),
        (70, 70, "outside"),
    ):
        with pytest.raises(ApprovalError, match=reason):
            checked_trim(VIDEO, read, a, b)
    read["approximateEnd"] = True
    with pytest.raises(ApprovalError, match="roughly"):
        checked_trim(VIDEO, read, 70, 110)
    read["approximateEnd"] = False
    read["speechStartS"] = None
    read["speechEndS"] = None
    with pytest.raises(ApprovalError, match="missing speech"):
        checked_trim(VIDEO, read, 70, 110)


def test_frozen_read_matches_reanalysis_without_rebinding_ids_or_basename() -> None:
    data = _report()
    frozen = _frozen(data)
    original = copy.deepcopy(frozen)
    assert match_frozen_read(data, frozen, SHA)[1] is None
    reanalyzed = copy.deepcopy(data)
    reanalyzed["video"]["file"] = "renamed-original.mov"
    reanalyzed["rows"][0]["takes"][0]["id"] = "row-1-take-9"
    reanalyzed["rows"][0]["suggested"]["takes"] = ["row-1-take-9"]
    assert match_frozen_read(reanalyzed, frozen, SHA)[1] is None
    assert frozen == original  # original source frame and source SHA never drift
    assert match_frozen_read(reanalyzed, frozen, OTHER_SHA)[1] == (
        "source recording or video timing changed"
    )


def test_frozen_cut_shift_words_context_and_ambiguous_read_fail_closed() -> None:
    data = _report()
    frozen = _frozen(data)
    widened = copy.deepcopy(data)
    widened["rows"][0]["suggested"]["cut"]["startFrame"] -= 2
    widened["rows"][0]["suggested"]["cut"]["endFrame"] += 2
    assert match_frozen_read(widened, frozen, SHA)[1] is None
    too_wide = copy.deepcopy(data)
    too_wide["rows"][0]["suggested"]["cut"]["startFrame"] -= 3
    too_wide["rows"][0]["suggested"]["cut"]["endFrame"] += 3
    assert "shifted" in (match_frozen_read(too_wide, frozen, SHA)[1] or "")
    shift = copy.deepcopy(data)
    shift["rows"][0]["suggested"]["cut"]["startFrame"] += 2
    shift["rows"][0]["suggested"]["cut"]["endFrame"] += 2
    assert "fresh clean-cut" in (match_frozen_read(shift, frozen, SHA)[1] or "")
    shift["rows"][0]["suggested"]["cut"]["startFrame"] += 1
    shift["rows"][0]["suggested"]["cut"]["endFrame"] += 1
    assert "shifted" in (match_frozen_read(shift, frozen, SHA)[1] or "")
    changed = copy.deepcopy(data)
    changed["rows"][0]["suggested"]["said"] = "Some other words"
    assert "changed words" in (match_frozen_read(changed, frozen, SHA)[1] or "")
    changed = copy.deepcopy(data)
    changed["rows"][1]["script"] = "Inserted words now"
    assert "order or wording" in (match_frozen_read(changed, frozen, SHA)[1] or "")
    changed = copy.deepcopy(data)
    changed["rows"][0]["script"], changed["rows"][1]["script"] = (
        changed["rows"][1]["script"],
        changed["rows"][0]["script"],
    )
    assert match_frozen_read(changed, frozen, SHA)[0] is None
    ambiguous = copy.deepcopy(data)
    ambiguous["rows"][0]["takes"].append(_raw("row-1-take-2", covered=2))
    ambiguous["rows"][0]["alternateReads"] = [_read(61, 121, ids=["row-1-take-2"])]
    assert "ambiguous" in (match_frozen_read(ambiguous, frozen, SHA)[1] or "")


def test_saved_manual_trim_is_rechecked_on_fresh_speech_evidence() -> None:
    data = _report()
    frozen = _frozen(data, trim=(71, 110))
    assert match_frozen_read(data, frozen, SHA)[1] is None
    rerun = copy.deepcopy(data)
    rerun["rows"][0]["suggested"]["speechStartS"] = 2.35
    assert match_frozen_read(rerun, frozen, SHA)[1] == (
        "saved trim no longer speech-safe"
    )
    rerun["rows"][0]["suggested"]["speechStartS"] = 2.1
    assert match_frozen_read(rerun, frozen, SHA)[1] == "source speech timing changed"
    corrupted = copy.deepcopy(frozen)
    corrupted["effectiveCut"]["startFrame"] = 73
    assert match_frozen_read(data, corrupted, SHA)[0] is None


def test_phase_one_logic_against_actual_generated_45_take_shape() -> None:
    # The #45 tests' fabricated audio timing exercises the real report builder.
    from test_presenter_takes import SESSION, _coverage_case, _said, _takes

    data = _takes(SESSION)
    data.update({"schemaVersion": "presenter-takes/1", "approved": False})
    assert len(full_reads(data["rows"][0], data["video"])) >= 1
    assert len(full_reads(data["rows"][1], data["video"])) >= 1
    merged = _coverage_case(
        "(on) In fact the band was kind of wanted to embrace the weirdness.",
        _said("In fact the band was kinda wanted to embrace the weirdness.", 2.0),
    )
    merged.update({"schemaVersion": "presenter-takes/1", "approved": False})
    compound = full_reads(merged["rows"][0], merged["video"])
    assert len(compound) == 1
    assert compound[0]["said"].endswith("weirdness.")
    assert (
        match_frozen_read(
            merged,
            freeze_read(merged, "row-1", compound[0], SHA),
            SHA,
        )[1]
        is None
    )


@pytest.fixture
def fake_media(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    from vera_timeline_agent import presenter_approvals as store

    # #45 uses ffprobe; inject only media metadata for invented file bytes.
    monkeypatch.setattr(store, "_inspect_original_metadata", lambda _: (12.0, [30, 1]))
    takes_path = tmp_path / "takes.json"
    video_path = tmp_path / str(VIDEO["file"])
    takes_path.write_text(json.dumps(_report()), encoding="utf-8")
    # Deliberately NOT a real recording: approval code reads its hash only.
    video_path.write_bytes(b"fictional local camera content")
    return takes_path, video_path


def test_choices_show_frame_keys_and_not_partial_or_automatic_approvals() -> None:
    takes = _report()
    candidates = available_choices(takes)
    assert candidates[0]["reads"] == [
        {
            "key": "60:120",
            "takes": ["row-1-take-1"],
            "said": "Three spoken words",
            "startFrame": 60,
            "endFrame": 120,
        }
    ]
    assert candidates[1]["reads"] == []
    takes["rows"][0]["suggested"] = None
    takes["rows"][0]["suggestedCoverage"] = [_read(word_range=[0, 2])]
    assert available_choices(takes)[0]["reads"] == []


def test_choose_is_byte_idempotent_and_records_previous_and_next(
    fake_media: tuple[Path, Path],
) -> None:
    takes_path, video_path = fake_media
    approvals_path = takes_path.with_name("approvals.json")
    assert not approvals_path.exists()
    before = choose_approval(takes_path, video_path, "row-1", "take", take="60:120")
    assert before["revision"] == 1
    assert before["source"]["sha256"] == file_hash(video_path)
    assert before["decisions"]["row-1"]["active"]["originalCut"] == {
        "startFrame": 60,
        "endFrame": 120,
    }
    first_bytes = approvals_path.read_bytes()
    first_inode = approvals_path.stat().st_ino
    duplicate = choose_approval(
        takes_path, video_path, "row-1", "take", take="row-1-take-1"
    )
    assert duplicate == before
    assert approvals_path.read_bytes() == first_bytes
    assert approvals_path.stat().st_ino == first_inode  # no atomic rewrite
    revised = choose_approval(takes_path, video_path, "row-1", "needs_pickup")
    assert revised["revision"] == 2
    assert revised["history"][0]["before"] is None
    assert revised["history"][0]["after"] == before["decisions"]["row-1"]
    assert revised["history"][1]["before"] == before["decisions"]["row-1"]
    assert revised["history"][1]["after"] == revised["decisions"]["row-1"]
    assert revised["history"][1]["after"]["state"] == "needs_pickup"
    assert revised["history"][1]["after"]["passage"] == {
        "rowId": "row-1",
        "rowNumber": 1,
        "script": "Three spoken words",
        "rowContext": row_context(_report()),
    }
    assert all(e["at"].endswith("Z") for e in revised["history"])
    assert validate_approvals(revised) == revised
    assert first_bytes != approvals_path.read_bytes()
    # A report re-run/read cannot change the human sidecar.
    takes_path.write_text(json.dumps(_report()), encoding="utf-8")
    after_reanalysis = approvals_path.read_bytes()
    assert load_approvals(approvals_path) == revised
    assert approvals_path.read_bytes() == after_reanalysis


def test_undo_appends_instead_of_erasing_and_can_restore_absent_decision(
    fake_media: tuple[Path, Path],
) -> None:
    takes_path, video_path = fake_media
    original = choose_approval(takes_path, video_path, "row-1", "temp_voice")
    choose_approval(takes_path, video_path, "row-1", "no_spoken_line")
    undone = undo_approval(takes_path, video_path, "row-1")
    assert undone["revision"] == 3
    assert undone["history"][2]["operation"] == "undo"
    assert undone["history"][2]["before"]["state"] == "no_spoken_line"
    assert (
        undone["history"][2]["before"]["passage"]
        == (original["decisions"]["row-1"]["passage"])
    )
    assert undone["history"][2]["after"] == original["decisions"]["row-1"]
    assert undone["decisions"]["row-1"] == original["decisions"]["row-1"]
    # A different row has its own independent event chain.
    choose_approval(takes_path, video_path, "row-2", "needs_pickup")
    undone_other = undo_approval(takes_path, video_path, "row-2")
    assert "row-2" not in undone_other["decisions"]
    assert undone_other["history"][-1]["after"] is None
    assert len(undone_other["history"]) == undone_other["revision"] == 5
    assert validate_approvals(undone_other) == undone_other
    with pytest.raises(ApprovalError, match="no prior"):
        undo_approval(takes_path, video_path, "row-3")


def test_repeated_undo_walks_back_choices_without_redo(
    fake_media: tuple[Path, Path],
) -> None:
    takes_path, video_path = fake_media
    path = takes_path.with_name("approvals.json")
    first = choose_approval(takes_path, video_path, "row-1", "temp_voice")
    choose_approval(takes_path, video_path, "row-1", "needs_pickup")
    back_to_first = undo_approval(takes_path, video_path, "row-1")
    assert back_to_first["decisions"]["row-1"] == first["decisions"]["row-1"]
    back_to_undecided = undo_approval(takes_path, video_path, "row-1")
    assert "row-1" not in back_to_undecided["decisions"]
    assert back_to_undecided["revision"] == 4
    original = path.read_bytes()
    with pytest.raises(ApprovalError, match="no prior"):
        undo_approval(takes_path, video_path, "row-1")
    assert path.read_bytes() == original
    assert validate_approvals(back_to_undecided) == back_to_undecided
    # A new choice after undo starts a new, independently undoable branch.
    choose_approval(takes_path, video_path, "row-1", "no_spoken_line")
    assert "row-1" not in undo_approval(takes_path, video_path, "row-1")["decisions"]


def test_active_and_alternate_are_frozen_by_frames_not_ephemeral_take_ids(
    fake_media: tuple[Path, Path],
) -> None:
    takes_path, video_path = fake_media
    report = _report()
    report["rows"][0]["takes"].append(
        _raw("row-1-take-2", covered=2, start=150, end=240, speech=(5.3, 7.1))
    )
    report["rows"][0]["alternateReads"] = [
        _read(start=150, end=240, ids=["row-1-take-2"], speech=(5.3, 7.1))
    ]
    takes_path.write_text(json.dumps(report), encoding="utf-8")
    approved = choose_approval(
        takes_path,
        video_path,
        "row-1",
        "take",
        take="row-1-take-1",
        alternates=["150:240"],
    )
    decision = approved["decisions"]["row-1"]
    assert decision["active"]["originalCut"]["startFrame"] == 60
    assert decision["alternates"][0]["originalCut"]["startFrame"] == 150
    assert "row-1-take-2" not in json.dumps(approved)
    with pytest.raises(ApprovalError, match="duplicate"):
        choose_approval(
            takes_path,
            video_path,
            "row-1",
            "take",
            take="60:120",
            alternates=["row-1-take-2", "150:240"],
        )


@pytest.mark.parametrize(
    "broken",
    [
        "{",
        '{"schemaVersion":"presenter-approvals/1","revision":NaN}',
        '{"schemaVersion":"presenter-approvals/1","revision":1,"revision":2}',
    ],
)
def test_corrupt_history_is_not_reset_or_overwritten(
    fake_media: tuple[Path, Path], broken: str
) -> None:
    takes_path, video_path = fake_media
    path = takes_path.with_name("approvals.json")
    choose_approval(takes_path, video_path, "row-1", "temp_voice")
    path.write_text(broken, encoding="utf-8")
    raw = path.read_bytes()
    with pytest.raises(ApprovalError):
        choose_approval(takes_path, video_path, "row-1", "needs_pickup")
    with pytest.raises(ApprovalError):
        undo_approval(takes_path, video_path, "row-1")
    assert path.read_bytes() == raw


def test_corrupt_audit_chain_blocks_undo_and_choose(
    fake_media: tuple[Path, Path],
) -> None:
    takes_path, video_path = fake_media
    path = takes_path.with_name("approvals.json")
    choose_approval(takes_path, video_path, "row-1", "temp_voice")
    data = load_approvals(path)
    data["history"][0]["after"] = {"state": "needs_pickup"}
    path.write_text(json.dumps(data), encoding="utf-8")
    corrupted = path.read_bytes()
    with pytest.raises(ApprovalError, match="disagree with history"):
        undo_approval(takes_path, video_path, "row-1")
    with pytest.raises(ApprovalError, match="disagree with history"):
        choose_approval(takes_path, video_path, "row-1", "temp_voice")
    assert path.read_bytes() == corrupted


def test_history_previous_snapshot_must_match_prior_event(
    fake_media: tuple[Path, Path],
) -> None:
    takes_path, video_path = fake_media
    path = takes_path.with_name("approvals.json")
    choose_approval(takes_path, video_path, "row-1", "temp_voice")
    choose_approval(takes_path, video_path, "row-1", "needs_pickup")
    document = load_approvals(path)
    # An attacker can forge the second before-image without changing the
    # final decision. Final-state checking alone must not accept this history.
    document["history"][1]["before"] = None
    path.write_text(json.dumps(document), encoding="utf-8")
    corrupted = path.read_bytes()
    with pytest.raises(ApprovalError, match="history before/after chain"):
        choose_approval(takes_path, video_path, "row-1", "temp_voice")
    with pytest.raises(ApprovalError, match="history before/after chain"):
        undo_approval(takes_path, video_path, "row-1")
    assert path.read_bytes() == corrupted


def test_invalid_trim_and_source_sha_preserve_existing_decision(
    fake_media: tuple[Path, Path],
) -> None:
    takes_path, video_path = fake_media
    path = takes_path.with_name("approvals.json")
    choose_approval(
        takes_path,
        video_path,
        "row-1",
        "take",
        take="60:120",
        start_frame=70,
        end_frame=110,
        hash_video=lambda _: SHA,
    )
    baseline = path.read_bytes()
    for left, right in ((73, 110), (-1, 110), (70, 121), (70, 108)):
        with pytest.raises(ApprovalError):
            choose_approval(
                takes_path,
                video_path,
                "row-1",
                "take",
                take="60:120",
                start_frame=left,
                end_frame=right,
                hash_video=lambda _: SHA,
            )
        assert path.read_bytes() == baseline
    with pytest.raises(ApprovalError, match="SHA"):
        choose_approval(
            takes_path,
            video_path,
            "row-1",
            "needs_pickup",
            hash_video=lambda _: OTHER_SHA,
        )
    with pytest.raises(ApprovalError, match="SHA"):
        undo_approval(takes_path, video_path, "row-1", hash_video=lambda _: OTHER_SHA)
    assert path.read_bytes() == baseline
    # Same basename and plausible metadata must not disguise replaced video bytes.
    video_path.write_bytes(b"different video bytes but same basename")
    with pytest.raises(ApprovalError, match="SHA"):
        choose_approval(takes_path, video_path, "row-1", "temp_voice")
    assert path.read_bytes() == baseline


def test_corrupt_report_and_invalid_request_leave_prior_sidecar_untouched(
    fake_media: tuple[Path, Path],
) -> None:
    takes_path, video_path = fake_media
    path = takes_path.with_name("approvals.json")
    choose_approval(takes_path, video_path, "row-1", "needs_pickup")
    baseline = path.read_bytes()
    for state, options in (
        ("take", {"take": "not-a-read"}),
        ("take", {"take": "60:120", "alternates": ["60:120"]}),
        ("needs_pickup", {"take": "60:120"}),
    ):
        with pytest.raises(ApprovalError):
            choose_approval(takes_path, video_path, "row-1", state, **options)
        assert path.read_bytes() == baseline
    takes_path.write_text('{"rows":', encoding="utf-8")
    with pytest.raises(ApprovalError):
        choose_approval(takes_path, video_path, "row-1", "temp_voice")
    assert path.read_bytes() == baseline


def test_rename_same_video_content_is_allowed_only_after_source_pin(
    fake_media: tuple[Path, Path],
) -> None:
    takes_path, video_path = fake_media
    renamed = video_path.with_name("moved.mov")
    video_path.rename(renamed)
    with pytest.raises(ApprovalError, match="filename"):
        choose_approval(takes_path, renamed, "row-1", "temp_voice")
    renamed.rename(video_path)
    choose_approval(takes_path, video_path, "row-1", "temp_voice")
    video_path.rename(renamed)
    doc = choose_approval(takes_path, renamed, "row-2", "needs_pickup")
    assert doc["revision"] == 2
    assert doc["source"]["file"] == "made-up.mov"


def test_initial_video_fps_duration_must_match_report_even_with_same_name(
    fake_media: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import presenter_approvals as store

    takes_path, video_path = fake_media
    path = takes_path.with_name("approvals.json")
    for metadata in ((12.0, [24, 1]), (13.0, [30, 1])):
        monkeypatch.setattr(
            store, "_inspect_original_metadata", lambda _, value=metadata: value
        )
        with pytest.raises(ApprovalError, match="fps/duration"):
            choose_approval(takes_path, video_path, "row-1", "temp_voice")
        assert not path.exists()
    monkeypatch.setattr(store, "_inspect_original_metadata", lambda _: (12.02, [30, 1]))
    accepted = choose_approval(takes_path, video_path, "row-1", "temp_voice")
    assert accepted["revision"] == 1  # decoded audio can end before the picture


def test_cli_parses_all_four_verbs_and_never_writes_takes(
    fake_media: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    takes_path, video_path = fake_media
    original = takes_path.read_bytes()
    args = ["--takes", str(takes_path)]
    video_arg = [*args, "--video", str(video_path)]
    assert approval_main(["choices", *args]) == 0
    assert json.loads(capsys.readouterr().out)["rows"][0]["reads"][0]["key"] == "60:120"
    assert (
        approval_main(
            [
                "choose",
                *video_arg,
                "--row",
                "row-1",
                "--state",
                "take",
                "--take",
                "row-1-take-1",
                "--start-frame",
                "70",
                "--end-frame",
                "110",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["revision"] == 1
    sidecar = takes_path.with_name("approvals.json")
    before_list = sidecar.read_bytes()
    assert approval_main(["list", *video_arg]) == 0
    assert json.loads(capsys.readouterr().out)["rows"][0]["state"] == "take"
    assert takes_path.with_name("approved-performance.json").is_file()
    assert takes_path.with_name("approved-performance.txt").is_file()
    assert sidecar.read_bytes() == before_list
    assert approval_main(["undo", *video_arg, "--row", "row-1"]) == 0
    assert json.loads(capsys.readouterr().out)["decision"] is None
    assert takes_path.read_bytes() == original
    assert (
        approval_main(
            [
                "choose",
                *video_arg,
                "--row",
                "row-1",
                "--state",
                "no-spoken-line",
                "--take",
                "60:120",
            ]
        )
        == 1
    )
    assert "non-take" in capsys.readouterr().err


def _performance_fixture() -> Json:
    """Entirely invented six-passage recording for ordered output goldens."""
    data = _report()
    data["rows"][0]["script"] = "Three spoken words"
    second = {
        "id": "row-2",
        "number": 2,
        "row": 2,
        "script": "Second spoken passage",
        "takes": [
            _raw(
                "row-2-take-1",
                start=130,
                end=170,
                speech=(4.6, 5.3),
                said="Second spoken passage",
            ),
            _raw(
                "row-2-take-2",
                start=180,
                end=220,
                speech=(6.3, 7.0),
                said="Second spoken passage",
            ),
        ],
        "suggested": _read(
            130,
            170,
            ids=["row-2-take-1"],
            speech=(4.6, 5.3),
            said="Second spoken passage",
        ),
        "alternateReads": [
            _read(
                180,
                220,
                ids=["row-2-take-2"],
                speech=(6.3, 7.0),
                said="Second spoken passage",
            )
        ],
        "suggestedCoverage": [],
        "gaps": [],
    }
    data["rows"][1] = second
    for ordinal, script in enumerate(
        (
            "Third sentence for temporary voice",
            "Fourth sentence needing pickup",
            "Fifth sentence is silent",
            "Sixth sentence remains undecided",
        ),
        3,
    ):
        data["rows"].append(
            {
                "id": f"row-{ordinal}",
                "number": ordinal,
                "row": ordinal,
                "script": script,
                "takes": [],
                "suggested": None,
                "alternateReads": [],
                "suggestedCoverage": [],
                "gaps": [],
            }
        )
    return data


def _approved_fixture(
    fake_media: tuple[Path, Path],
) -> tuple[Path, Path, Json, Json]:
    takes_path, video_path = fake_media
    takes = _performance_fixture()
    takes_path.write_text(json.dumps(takes), encoding="utf-8")
    choose_approval(
        takes_path,
        video_path,
        "row-1",
        "take",
        take="60:120",
        start_frame=70,
        end_frame=110,
        hash_video=lambda _: SHA,
    )
    choose_approval(
        takes_path,
        video_path,
        "row-2",
        "take",
        take="130:170",
        alternates=["180:220"],
        hash_video=lambda _: SHA,
    )
    choose_approval(
        takes_path,
        video_path,
        "row-3",
        "temp_voice",
        hash_video=lambda _: SHA,
    )
    choose_approval(
        takes_path,
        video_path,
        "row-4",
        "needs_pickup",
        hash_video=lambda _: SHA,
    )
    choose_approval(
        takes_path,
        video_path,
        "row-5",
        "no_spoken_line",
        hash_video=lambda _: SHA,
    )
    return (
        takes_path,
        video_path,
        takes,
        load_approvals(takes_path.with_name("approvals.json")),
    )


def test_ordered_performance_all_states_and_golden_outputs(
    fake_media: tuple[Path, Path],
) -> None:
    takes_path, _, takes, approvals = _approved_fixture(fake_media)
    before_takes = takes_path.read_bytes()
    before_approvals = takes_path.with_name("approvals.json").read_bytes()
    report = approved_performance(takes, approvals, SHA)
    assert [r["state"] for r in report["rows"]] == [
        "take",
        "take",
        "temp_voice",
        "needs_pickup",
        "no_spoken_line",
        "undecided",
    ]
    assert report["rows"][0]["active"]["startFrame"] == 70  # human trim
    assert report["rows"][0]["active"]["endFrame"] == 110
    assert report["rows"][1]["alternates"][0]["startFrame"] == 180
    assert report["possibleAbruptJoins"] == [
        {
            "fromRowId": "row-1",
            "toRowId": "row-2",
            "kind": "possible_abrupt_join",
            "reason": "less than 10 frames clear of speech at a cut edge",
        }
    ]
    assert report["orphanedDecisions"] == []
    assert "NEEDS PICKUP" in approved_performance_text(report)
    assert "POSSIBLE ABRUPT JOIN" in approved_performance_text(report)
    write_performance_reports(takes_path, report)
    goldens = Path(__file__).parent / "data" / "presenter_approvals"
    assert (
        takes_path.with_name("approved-performance.json").read_text()
        == (goldens / "approved-performance.json").read_text()
    )
    assert (
        takes_path.with_name("approved-performance.txt").read_text()
        == (goldens / "approved-performance.txt").read_text()
    )
    assert takes_path.read_bytes() == before_takes
    assert takes_path.with_name("approvals.json").read_bytes() == before_approvals


def test_reanalysis_preserves_bytes_and_freezes_saved_cut(
    fake_media: tuple[Path, Path],
) -> None:
    takes_path, _, takes, approvals = _approved_fixture(fake_media)
    approvals_path = takes_path.with_name("approvals.json")
    baseline = approvals_path.read_bytes()
    rerun = copy.deepcopy(takes)
    rerun["rows"][0]["suggested"]["cut"]["startFrame"] += 1
    rerun["rows"][0]["suggested"]["cut"]["endFrame"] += 1
    rerun["rows"][0]["takes"][0]["id"] = "row-1-take-99"
    rerun["rows"][0]["suggested"]["takes"] = ["row-1-take-99"]
    rerun["video"]["file"] = "renamed-original.mov"
    takes_path.write_text(json.dumps(rerun), encoding="utf-8")
    report = approved_performance(load_takes(takes_path), approvals, SHA)
    assert report["rows"][0]["state"] == "take"
    assert report["rows"][0]["active"]["file"] == "renamed-original.mov"
    assert report["rows"][0]["active"]["startFrame"] == 70
    assert approvals_path.read_bytes() == baseline
    write_performance_reports(takes_path, report)
    assert approvals_path.read_bytes() == baseline


def test_stale_alternate_source_and_orphans_never_expose_build_ready_range(
    fake_media: tuple[Path, Path],
) -> None:
    _, _, takes, approvals = _approved_fixture(fake_media)
    altered = copy.deepcopy(takes)
    altered["rows"][1]["alternateReads"][0]["cut"]["startFrame"] += 3
    altered["rows"][1]["alternateReads"][0]["cut"]["endFrame"] += 3
    stale = approved_performance(altered, approvals, SHA)
    assert stale["rows"][1]["state"] == "needs_another_look"
    assert stale["rows"][1]["previousState"] == "take"
    assert "alternate 1:" in stale["rows"][1]["reason"]
    assert "active" not in stale["rows"][1]
    assert "savedApproval" in stale["rows"][1]

    source_changed = approved_performance(takes, approvals, OTHER_SHA)
    assert source_changed["rows"][0]["state"] == "needs_another_look"
    assert source_changed["rows"][2]["state"] == "needs_another_look"
    assert source_changed["rows"][2]["previousState"] == "temp_voice"
    assert source_changed["possibleAbruptJoins"] == []

    shortened = copy.deepcopy(takes)
    shortened["rows"] = shortened["rows"][:4]
    missing = approved_performance(shortened, approvals, SHA)
    assert len(missing["rows"]) == 4
    assert missing["orphanedDecisions"] == [
        {
            "rowId": "row-5",
            "state": "needs_another_look",
            "previousState": "no_spoken_line",
            "reason": "approved script passage is missing from the current analysis",
            "savedScript": "Fifth sentence is silent",
        }
    ]
    assert "ORPHANED DECISION" in approved_performance_text(missing)
    only_first = copy.deepcopy(takes)
    only_first["rows"] = only_first["rows"][:1]
    vanished_take = approved_performance(only_first, approvals, SHA)[
        "orphanedDecisions"
    ][0]
    assert vanished_take["rowId"] == "row-2"
    assert vanished_take["state"] == "needs_another_look"
    assert vanished_take["savedApproval"]["effectiveCut"] == {
        "startFrame": 130,
        "endFrame": 170,
    }
    assert "active" not in vanished_take


def test_join_warning_uses_actual_approved_trim_and_not_jump_cut_preference(
    fake_media: tuple[Path, Path],
) -> None:
    takes_path, video_path, takes, approvals = _approved_fixture(fake_media)
    takes["allowJumpCuts"] = True
    # The existing tight selected trim remains suspect, even if on-camera
    # jump cuts have been allowed by the upstream analyzer.
    assert len(approved_performance(takes, approvals, SHA)["possibleAbruptJoins"]) == 1

    # Reapprove wider, still speech-safe handles after a reanalysis with a
    # different speech onset. Only >=10 frames on BOTH sides avoids a warning.
    takes["rows"][1]["suggested"]["speechStartS"] = 4.8
    takes_path.write_text(json.dumps(takes), encoding="utf-8")
    choose_approval(
        takes_path,
        video_path,
        "row-1",
        "take",
        take="60:120",
        start_frame=70,
        end_frame=120,
        hash_video=lambda _: SHA,
    )
    latest = choose_approval(
        takes_path,
        video_path,
        "row-2",
        "take",
        take="130:170",
        alternates=["180:220"],
        hash_video=lambda _: SHA,
    )
    refreshed = approved_performance(takes, latest, SHA)
    assert refreshed["rows"][0]["state"] == "take"
    assert refreshed["rows"][1]["state"] == "take"
    assert refreshed["possibleAbruptJoins"] == []


def test_script_edit_stale_take_and_invalid_sidecar_cannot_rewrite_reports(
    fake_media: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    takes_path, video_path, takes, approvals = _approved_fixture(fake_media)
    edited = copy.deepcopy(takes)
    edited["rows"][0]["script"] = "Now very different words"
    result = approved_performance(edited, approvals, SHA)
    assert result["rows"][0]["state"] == "needs_another_look"
    assert "wording changed" in result["rows"][0]["reason"]
    assert "active" not in result["rows"][0]

    list_args = ["list", "--takes", str(takes_path), "--video", str(video_path)]
    assert approval_main(list_args) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["schemaVersion"] == "approved-performance/1"
    json_path = takes_path.with_name("approved-performance.json")
    txt_path = takes_path.with_name("approved-performance.txt")
    before_json, before_txt = json_path.read_bytes(), txt_path.read_bytes()
    approvals_path = takes_path.with_name("approvals.json")
    valid = approvals_path.read_bytes()
    approvals_path.write_text("{", encoding="utf-8")
    assert approval_main(list_args) == 1
    assert "cannot read approvals.json" in capsys.readouterr().err
    assert json_path.read_bytes() == before_json
    assert txt_path.read_bytes() == before_txt
    assert approvals_path.read_bytes() == b"{"
    approvals_path.write_bytes(valid)


def test_non_take_decision_is_not_retargeted_after_script_edit_and_legacy_is_stale(
    fake_media: tuple[Path, Path],
) -> None:
    takes_path, video_path, takes, approvals = _approved_fixture(fake_media)
    sidecar = takes_path.with_name("approvals.json")
    before = sidecar.read_bytes()
    edited = copy.deepcopy(takes)
    edited["rows"][2]["script"] = "Different paragraph inserted here"
    report = approved_performance(edited, approvals, SHA)
    assert report["rows"][2]["state"] == "needs_another_look"
    assert report["rows"][2]["previousState"] == "temp_voice"
    assert report["rows"][2]["reason"] == "script passage order or wording changed"
    assert "active" not in report["rows"][2]
    assert sidecar.read_bytes() == before

    # Legacy state-only decisions remain readable but must not silently
    # attach to an arbitrary passage without frozen wording/context.
    legacy = copy.deepcopy(approvals)
    legacy["decisions"]["row-3"] = {"state": "temp_voice"}
    next(e for e in legacy["history"] if e["rowId"] == "row-3")["after"] = {
        "state": "temp_voice"
    }
    assert validate_approvals(legacy) == legacy
    old = approved_performance(takes, legacy, SHA)
    assert old["rows"][2]["state"] == "needs_another_look"
    assert "legacy decision" in old["rows"][2]["reason"]

    # Only a *new explicit choose* may anchor the edited passage; analysis
    # and listing leave the original audit sidecar byte-identical.
    takes_path.write_text(json.dumps(edited), encoding="utf-8")
    updated = choose_approval(
        takes_path, video_path, "row-3", "temp_voice", hash_video=lambda _: SHA
    )
    assert updated["revision"] == approvals["revision"] + 1
    assert updated["history"][-1]["operation"] == "choose"
    assert updated["history"][-1]["before"] == approvals["decisions"]["row-3"]
    assert (
        approved_performance(edited, updated, SHA)["rows"][2]["state"] == "temp_voice"
    )


def test_two_writers_cannot_lose_each_others_history(
    fake_media: tuple[Path, Path],
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    takes_path, video_path = fake_media
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(
                choose_approval,
                takes_path,
                video_path,
                row,
                "needs_pickup" if row == "row-1" else "temp_voice",
            )
            for row in ("row-1", "row-2", "row-1", "row-2")
        ]
        for future in futures:
            future.result()
    result = load_approvals(takes_path.with_name("approvals.json"))
    assert result["revision"] == 2
    assert [event["revision"] for event in result["history"]] == [1, 2]
    assert {
        row_id: decision["state"] for row_id, decision in result["decisions"].items()
    } == {"row-1": "needs_pickup", "row-2": "temp_voice"}
    assert result["decisions"]["row-1"]["passage"]["script"] == "Three spoken words"
    assert result["decisions"]["row-2"]["passage"]["script"] == "Other short passage"


def test_atomic_write_failure_does_not_replace_valid_decision(
    fake_media: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    takes_path, video_path = fake_media
    path = takes_path.with_name("approvals.json")
    choose_approval(takes_path, video_path, "row-1", "temp_voice")
    baseline = path.read_bytes()

    def broken_replace(_src: str, _dst: Path) -> None:
        raise OSError("deliberate replace failure")

    monkeypatch.setattr(os, "replace", broken_replace)
    with pytest.raises(ApprovalError, match="cannot commit"):
        choose_approval(takes_path, video_path, "row-1", "needs_pickup")
    assert path.read_bytes() == baseline
    assert list(takes_path.parent.glob(".approvals-*")) == []
