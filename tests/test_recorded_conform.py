"""#47 invented three-row approval, source-word, and frozen-script fixtures."""

from __future__ import annotations

import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.presenter_approvals import (
    freeze_read,
    full_reads,
    row_context,
    source_identity,
)
from vera_timeline_agent.recorded_conform import (
    ConformRefused,
    approval_blockers,
    approved_interval,
    ceil_frames,
    conform_snapshot,
    local_onset,
    row_impact,
)
from vera_timeline_agent.recorded_word_evidence import canonical_json

SHA = "sha256:" + "a" * 64
WORDS = ("Three spoken words", "Other short passage", "Third recorded words")
_ROOT = Path(__file__).resolve().parents[1]


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def _raw(
    row_number: int, start: int, end: int, speech_a: float, speech_b: float
) -> dict:
    row_id = f"row-{row_number}"
    return {
        "takes": [f"{row_id}-take-1"],
        "scriptWords": [0, 3],
        "cut": {
            "startFrame": start,
            "endFrame": end,
            "startS": start / 30,
            "endS": end / 30,
            "framesClearOfSpeech": [8, 8],
        },
        "speechStartS": speech_a,
        "speechEndS": speech_b,
        "approximateStart": False,
        "approximateEnd": False,
        "said": WORDS[row_number - 1],
        "differences": {"moved": [], "substituted": [], "added": [], "omitted": []},
    }


def sample() -> dict[str, Any]:
    video = {"file": "made-up.mov", "durationS": 12.0, "fps": [30, 1]}
    first = _raw(1, 60, 120, 2.2, 3.7)
    third = _raw(3, 180, 270, 6.2, 8.7)
    rows = []
    for i, read in enumerate((first, None, third), 1):
        row = {
            "id": f"row-{i}",
            "number": i,
            "row": i,
            "script": WORDS[i - 1],
            "takes": [],
            "suggested": None,
            "alternateReads": [],
            "suggestedCoverage": [],
            "gaps": [],
        }
        if read is not None:
            row["suggested"] = copy.deepcopy(read)
            row["takes"] = [
                {
                    **copy.deepcopy(read),
                    "id": f"row-{i}-take-1",
                    "number": 1,
                    "complete": True,
                    "wholePassage": True,
                    "scriptWords": 3,
                    "scriptWordsCovered": 3,
                }
            ]
        rows.append(row)
    takes = {
        "schemaVersion": "presenter-takes/1",
        "video": video,
        "script": {"file": "prompter.txt"},
        "approved": False,
        "allowJumpCuts": False,
        "jumpCutChoice": None,
        "rows": rows,
        "suggestedEdit": [],
        "offScript": [],
    }
    source = source_identity(video, SHA)
    decisions = {}
    for i, state in enumerate(("take", "temp_voice", "take"), 1):
        if state == "take":
            frozen = freeze_read(
                takes, f"row-{i}", full_reads(rows[i - 1], video)[0], SHA
            )
            decision = {"state": "take", "active": frozen, "alternates": []}
        else:
            decision = {
                "state": state,
                "passage": {
                    "rowId": f"row-{i}",
                    "rowNumber": i,
                    "script": WORDS[i - 1],
                    "rowContext": row_context(takes),
                },
            }
        decisions[f"row-{i}"] = decision
    approvals = {
        "schemaVersion": "presenter-approvals/1",
        "revision": 3,
        "source": source,
        "decisions": decisions,
        "history": [
            {
                "revision": i,
                "at": "2026-11-14T12:00:00Z",
                "operation": "choose",
                "rowId": f"row-{i}",
                "before": None,
                "after": decisions[f"row-{i}"],
            }
            for i in (1, 2, 3)
        ],
    }
    script_text = "\n".join(WORDS) + "\n"
    evidence_rows = []
    for i, read in enumerate((first, None, third), 1):
        full = []
        if read:
            base = 2 if i == 1 else 6
            marks = []
            for j, word in enumerate(WORDS[i - 1].casefold().split()):
                a = base + [0.3, 0.7, 1.2][j]
                marks.append(
                    {
                        "scriptWordIndex": j,
                        "scriptWord": word,
                        "recordedWordIndex": j + (10 if i == 1 else 20),
                        "recordedWord": word,
                        "startS": str(a),
                        "endS": str(a + 0.2),
                        "precision": "acoustic",
                    }
                )
            full = [
                {
                    "takes": read["takes"],
                    "said": read["said"],
                    "sourceCut": {
                        "startFrame": read["cut"]["startFrame"],
                        "endFrame": read["cut"]["endFrame"],
                    },
                    "spoken": [0, 3],
                    "marks": marks,
                }
            ]
        evidence_rows.append(
            {
                "rowId": f"row-{i}",
                "script": WORDS[i - 1],
                "scriptWords": WORDS[i - 1].casefold().split(),
                "fullReads": full,
            }
        )
    evidence = {
        "schemaVersion": "take-word-marks/1",
        "video": {
            "file": video["file"],
            "durationS": "12",
            "fps": [30, 1],
            "sha256": SHA,
        },
        "sourceScript": {
            "file": "prompter.txt",
            "sha256": hashlib.sha256(script_text.encode()).hexdigest(),
            "textSha256": hashlib.sha256(script_text.encode()).hexdigest(),
        },
        "rows": evidence_rows,
    }
    # Start with the upstream, real compiler's known-good frozen document and
    # dependencies. Clone narration IDs/tokens and source descriptors, never
    # private audio/media. The CLI unit tests inject a compiler response; a
    # separate adapter test invokes the real compiler on the original fixture.
    fixture = json.loads(
        (
            _ROOT / "tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json"
        ).read_text()
    )
    doc, deps = fixture["document"], fixture["dependencies"]
    original_block = doc["activeDraft"]["blocks"][0]
    original_map = deps["narrationTimingMaps"][0]
    original_descriptor = deps["occurrenceResolutions"][0]
    blocks, maps, descriptors = [], [], []
    for i, text in enumerate(WORDS, 1):
        block = copy.deepcopy(original_block)
        mapping = copy.deepcopy(original_map)
        descriptor = copy.deepcopy(original_descriptor)
        block["id"] = f"00000000-0000-4000-8000-{100 + i:012d}"
        block["text"] = text
        cursor = 0
        frozen_tokens = []
        timing_tokens = []
        for j, word in enumerate(text.split(), 1):
            start = text.index(word, cursor)
            end = start + len(word)
            tid = f"00000000-0000-4000-8000-{i * 10 + j:012d}"
            frozen_tokens.append(
                {"id": tid, "value": word, "startOffset": start, "endOffset": end}
            )
            timing_tokens.append(
                {
                    "tokenId": tid,
                    "startOffset": start,
                    "endOffset": end,
                    "quotedText": word,
                    "startTime": {
                        "numerator": Fraction(j - 1, 2).numerator,
                        "denominator": Fraction(j - 1, 2).denominator,
                    },
                    "endBasis": "next_word_derived",
                }
            )
            cursor = end
        block["tokens"] = frozen_tokens
        seq = block["primaryVisualSequence"]
        seq["id"] = f"00000000-0000-4000-8000-{200 + i:012d}"
        slot = seq["slots"][0]
        slot["id"] = f"00000000-0000-4000-8000-{300 + i:012d}"
        slot["payload"]["payloadId"] = f"00000000-0000-4000-8000-{400 + i:012d}"
        descriptor["payloadId"] = slot["payload"]["payloadId"]
        descriptor["owner"]["slotId"] = slot["id"]
        descriptor["owner"]["sequenceId"] = seq["id"]
        descriptor["logicalSourceBounds"]["endFrame"] = 240
        mapping["blockId"] = block["id"]
        mapping["textHash"] = _digest(text)
        mapping["tokens"] = timing_tokens
        mapping["narrationAssetId"] = f"00000000-0000-4000-8000-{500 + i:012d}"
        mapping["audio"]["narrationAssetId"] = mapping["narrationAssetId"]
        mapping["audio"]["durationSamples"] = 4 * 48000
        blocks.append(block)
        maps.append(mapping)
        descriptors.append(descriptor)
    doc["activeDraft"]["blocks"] = blocks
    deps["narrationTimingMaps"] = maps
    deps["occurrenceResolutions"] = descriptors
    deps["document"]["textHash"] = _digest("\n".join(WORDS))
    deps["preparedMedia"] = []
    return dict(
        takes=takes,
        approvals=approvals,
        evidence=evidence,
        sourceScript=script_text.encode(),
        analyzedText=script_text,
        document=doc,
        dependencies=deps,
        videoSha=SHA,
    )


def _snapshot(data: dict) -> dict:
    return conform_snapshot(
        data["takes"],
        data["approvals"],
        data["videoSha"],
        data["evidence"],
        data["sourceScript"],
        data["analyzedText"],
        data["document"],
        data["dependencies"],
    )


def test_exact_rational_math_and_cumulative_shifts() -> None:
    interval = approved_interval(
        {
            "state": "take",
            "active": {
                "startFrame": 70,
                "endFrame": 110,
                "startS": "7/3",
                "endS": "11/3",
            },
        },
        [30, 1],
    )
    assert local_onset("5/2", *interval) == Fraction(1, 6)
    with pytest.raises(ConformRefused, match="outside"):
        local_onset("11/3", *interval)
    assert ceil_frames(Fraction(1001, 30000), [30000, 1001]) == 1
    assert [
        r["shiftAfterFrames"]
        for r in row_impact(
            [("row-1", 100, 130), ("row-2", 120, 90), ("row-3", 100, 140)]
        )
    ] == [30, 0, 40]


def test_three_row_approved_snapshot_freezes_exact_source_tokens() -> None:
    data = sample()
    result = _snapshot(data)
    assert result == _snapshot(data)
    assert result["rows"][0]["framing"] == "wide"
    assert result["rows"][0]["effectiveCut"] == {"startFrame": 60, "endFrame": 120}
    assert result["rows"][0]["wordTiming"][0]["onset"] == {
        "numerator": 3,
        "denominator": 10,
    }
    assert [r["state"] for r in result["rows"]] == ["take", "temp_voice", "take"]
    golden = _ROOT / "tests/data/recorded_conform/approved.snapshot.golden.json"
    assert canonical_json(result) == golden.read_bytes()


def test_collects_unresolved_and_orphan_row_ids() -> None:
    report = {
        "schemaVersion": "approved-performance/1",
        "rows": [
            {"rowId": "row-1", "rowNumber": 1, "state": "undecided"},
            {"rowId": "row-2", "rowNumber": 2, "state": "needs_pickup"},
            {"rowId": "row-3", "rowNumber": 3, "state": "needs_another_look"},
        ],
        "orphanedDecisions": [{"rowId": "row-4"}],
    }
    issues = approval_blockers(report)
    assert all(f"row-{i}" in " ".join(issues) for i in range(1, 5))


@pytest.mark.parametrize(
    "corrupt,reason",
    [
        (
            lambda d: d["evidence"]["sourceScript"].update(sha256="f" * 64),
            "script changed",
        ),
        (
            lambda d: d["evidence"]["rows"][0]["fullReads"][0]["marks"][0].update(
                precision="derived"
            ),
            "acoustic",
        ),
        (lambda d: d["document"]["activeDraft"]["blocks"].reverse(), "text hash"),
        (
            lambda d: d["document"]["activeDraft"]["blocks"][1].update(text=WORDS[0]),
            "text hash",
        ),
        (
            lambda d: d["dependencies"]["narrationTimingMaps"][0].update(
                audioHash="sha256:" + "e" * 64
            ),
            "audio binding",
        ),
        (
            lambda d: d["document"]["activeDraft"]["blocks"][0]["tokens"][0].update(
                id="wrong"
            ),
            "token",
        ),
    ],
)
def test_identity_mutations_are_not_silently_accepted(
    corrupt: Any, reason: str
) -> None:
    data = sample()
    corrupt(data)
    with pytest.raises(ConformRefused, match=reason):
        _snapshot(data)


def test_recorded_word_end_must_fit_inside_approved_source_trim() -> None:
    data = sample()
    # This word starts within the human cut, but its acoustic END is outside.
    data["evidence"]["rows"][0]["fullReads"][0]["marks"][2]["endS"] = "5"
    with pytest.raises(
        ConformRefused, match="measured word end outside approved source cut"
    ):
        _snapshot(data)


def test_word_evidence_video_frame_rate_must_match_approved_source() -> None:
    data = sample()
    data["evidence"]["video"]["fps"] = [24, 1]
    with pytest.raises(ConformRefused, match="source frame rate or duration differs"):
        _snapshot(data)


def test_word_marks_must_pin_original_camera_sha256() -> None:
    data = sample()
    data["evidence"]["video"]["sha256"] = "sha256:" + "f" * 64
    with pytest.raises(ConformRefused, match="camera SHA-256 differs"):
        _snapshot(data)


def test_word_marks_must_match_analyzed_script_tokens() -> None:
    data = sample()
    data["evidence"]["rows"][0]["scriptWords"] = ["other", "script", "words"]
    with pytest.raises(ConformRefused, match="words differ from analyzed script"):
        _snapshot(data)


def test_word_marks_must_identify_exact_approved_read_group() -> None:
    data = sample()
    data["evidence"]["rows"][0]["fullReads"][0]["takes"] = ["wrong-take"]
    with pytest.raises(
        ConformRefused, match="missing or ambiguous approved word evidence"
    ):
        _snapshot(data)


def test_frozen_token_offsets_must_quote_the_actual_word() -> None:
    data = sample()
    data["document"]["activeDraft"]["blocks"][0]["tokens"][0]["startOffset"] = 1
    with pytest.raises(ConformRefused, match="frozen token"):
        _snapshot(data)
