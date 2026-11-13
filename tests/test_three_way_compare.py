"""Fast, SDK-free checks for the script half of the three-way comparison."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.three_way_compare import compare_script_rows

FIXTURE = Path(__file__).parent / "data/three_way_compare/baseline.json"


def _case() -> dict[str, Any]:
    case: dict[str, Any] = json.loads(FIXTURE.read_text())
    case["currentDocument"] = deepcopy(case["baselineDocument"])
    case["currentManifest"] = deepcopy(case["baselineManifest"])
    return case


def _compare(case: dict[str, Any]) -> dict[str, Any]:
    return compare_script_rows(
        case["baselineManifest"],
        case["baselineMap"],
        case["baselineDocument"],
        case["currentManifest"],
        case["currentDocument"],
    )


def _rows(case: dict[str, Any]) -> list[str]:
    return [block["id"] for block in case["currentDocument"]["activeDraft"]["blocks"]]


def _by_row(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["rowId"]: row for row in result["rows"]}


def _shift_event(case: dict[str, Any], index: int, start: int) -> None:
    record = case["currentManifest"]["events"][index]["recordRange"]
    length = record["endFrame"] - record["startFrame"]
    record.update(startFrame=start, endFrame=start + length)


def test_unchanged_accepts_new_build_identity_without_mutating_inputs() -> None:
    case = _case()
    case["currentManifest"]["buildId"] = "different-build"
    case["currentManifest"]["id"] = "different-manifest"
    case["currentManifest"]["document"]["revision"] = 2
    case["currentManifest"]["document"]["contentHash"] = (
        "sha256:different-compiled-revision"
    )
    frozen = deepcopy(case)
    first = _compare(case)
    assert case == frozen
    assert first == _compare(case)
    assert json.dumps(first, sort_keys=True) == json.dumps(
        _compare(case), sort_keys=True
    )
    assert [row["scriptChange"] for row in first["rows"]] == ["unchanged"] * 3
    assert first["baseline"]["timelineId"] == "native-timeline-1"
    assert first["current"]["documentRevision"] == 2


def test_only_changed_event_semantics_mark_own_row() -> None:
    case = _case()
    b = _rows(case)[1]
    case["currentManifest"]["events"][1]["provenance"]["deliveredSourceHash"] = (
        "sha256:changed"
    )
    result = _by_row(_compare(case))
    assert result[b]["scriptChange"] == "changed"
    assert [
        result[row]["scriptChange"] for row in (_rows(case)[0], _rows(case)[2])
    ] == [
        "unchanged",
        "unchanged",
    ]


def test_shifted_downstream_rows_are_not_false_positive_content_edits() -> None:
    case = _case()
    a, b, c = _rows(case)
    # Row A becomes five frames longer; B and C simply move downstream.
    case["currentManifest"]["events"][0]["recordRange"]["endFrame"] = 15
    _shift_event(case, 1, 15)
    _shift_event(case, 2, 25)
    rows = _by_row(_compare(case))
    assert rows[a]["scriptChange"] == "changed"
    assert rows[b]["scriptChange"] == rows[c]["scriptChange"] == "unchanged"
    assert (rows[b]["baselineStartFrame"], rows[b]["currentStartFrame"]) == (10, 15)
    assert (rows[c]["baselineStartFrame"], rows[c]["currentStartFrame"]) == (20, 25)


def test_insertion_does_not_falsely_reorder_survivors() -> None:
    case = _case()
    a, b, c = _rows(case)
    new = "00000000-0000-4000-8000-000000000014"
    case["currentDocument"]["activeDraft"]["blocks"].insert(
        1, {"type": "visual_only", "id": new}
    )
    new_event = deepcopy(case["currentManifest"]["events"][1])
    new_event["eventId"] = "00000000-0000-4000-8000-000000000034"
    new_event["provenance"]["blockId"] = new
    new_event["recordRange"] = {"startFrame": 10, "endFrame": 15}
    case["currentManifest"]["events"].append(new_event)
    _shift_event(case, 1, 15)
    _shift_event(case, 2, 25)
    result = _compare(case)
    assert [row["rowId"] for row in result["rows"]] == [a, new, b, c]
    assert [row["scriptChange"] for row in result["rows"]] == [
        "unchanged",
        "added",
        "unchanged",
        "unchanged",
    ]
    assert not any(row["reordered"] for row in result["rows"])


def test_removal_is_visible_and_downstream_row_stays_unchanged() -> None:
    case = _case()
    a, b, c = _rows(case)
    case["currentDocument"]["activeDraft"]["blocks"].pop(1)
    case["currentManifest"]["events"].pop(1)
    _shift_event(case, 1, 10)
    result = _compare(case)
    assert [row["rowId"] for row in result["rows"]] == [a, c, b]
    assert [row["scriptChange"] for row in result["rows"]] == [
        "unchanged",
        "unchanged",
        "removed",
    ]
    assert result["rows"][-1]["currentStartFrame"] is None


def test_swap_marks_only_inverted_survivors_as_reordered() -> None:
    case = _case()
    a, b, c = _rows(case)
    blocks = case["currentDocument"]["activeDraft"]["blocks"]
    blocks[0], blocks[1] = blocks[1], blocks[0]
    _shift_event(case, 0, 10)
    _shift_event(case, 1, 0)
    result = _by_row(_compare(case))
    assert (result[a]["scriptChange"], result[b]["scriptChange"]) == (
        "reordered",
        "reordered",
    )
    assert result[c]["scriptChange"] == "unchanged"
    assert not any(row["contentChanged"] for row in result.values())


def test_moved_marker_is_compared_without_requiring_a_native_map_item() -> None:
    case = _case()
    b = _rows(case)[1]
    marker = {
        "eventId": "00000000-0000-4000-8000-000000000035",
        "kind": "script_marker",
        "trackId": "markers",
        "provenance": {
            "documentId": case["baselineDocument"]["id"],
            "blockId": b,
        },
        "recordRange": {"startFrame": 10, "endFrame": 11},
        "marker": {"text": "Check pronunciation"},
    }
    for side in ("baselineManifest", "currentManifest"):
        case[side]["tracks"].append({"id": "markers"})
        case[side]["events"].append(deepcopy(marker))
    assert all(row["scriptChange"] == "unchanged" for row in _compare(case)["rows"])
    case["currentManifest"]["events"][-1]["marker"]["text"] = "Check names"
    assert _by_row(_compare(case))[b]["scriptChange"] == "changed"


def test_excluded_narration_and_zero_event_rows_are_not_dropped() -> None:
    case = _case()
    excluded = "00000000-0000-4000-8000-000000000015"
    empty = "00000000-0000-4000-8000-000000000016"
    for side in ("baselineDocument", "currentDocument"):
        case[side]["activeDraft"]["blocks"].append(
            {"type": "narration", "id": excluded, "state": "excluded"}
        )
        case[side]["activeDraft"]["blocks"].append(
            {"type": "note_draft", "id": "00000000-0000-4000-8000-000000000017"}
        )
        case[side]["activeDraft"]["blocks"].append({"type": "visual_only", "id": empty})
    results = _compare(case)["rows"]
    assert excluded not in {row["rowId"] for row in results}
    assert results[-1]["rowId"] == empty
    assert results[-1]["scriptChange"] == "unchanged"
    assert results[-1]["currentStartFrame"] is None


def test_unowned_compiled_events_are_retained_separately() -> None:
    case = _case()
    unowned = deepcopy(case["baselineManifest"]["events"][0])
    unowned["eventId"] = "00000000-0000-4000-8000-000000000036"
    unowned["provenance"]["blockId"] = None
    case["baselineManifest"]["events"].append(unowned)
    # The v2 row map also owns non-marker events with null row attribution.
    case["baselineMap"]["rows"].append(
        {
            "rowId": None,
            "timelineId": "native-timeline-1",
            "startFrame": 0,
            "lengthFrames": 10,
            "items": [
                {
                    "eventId": unowned["eventId"],
                    "resolveItemId": "native-unowned",
                    "trackId": "video-root",
                    "startFrame": 0,
                    "durationFrames": 10,
                }
            ],
        }
    )
    result = _compare(case)
    assert len(result["unownedCompiledEvents"]["baseline"]) == 1
    assert len(result["unownedCompiledEvents"]["current"]) == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("blockId", ""),
        ("blockId", 123),
        ("blockId", "does-not-exist"),
        ("documentId", "different-document"),
    ],
)
def test_invalid_or_unrecognized_compiled_row_identity_is_refused(
    field: str, value: Any
) -> None:
    case = _case()
    case["currentManifest"]["events"][0]["provenance"][field] = value
    with pytest.raises(ValueError):
        _compare(case)


@pytest.mark.parametrize("value", [True, 1.5, -1, 2**53, None])
def test_non_integer_or_unsafe_frame_is_refused(value: Any) -> None:
    case = _case()
    case["currentManifest"]["events"][0]["recordRange"]["startFrame"] = value
    with pytest.raises(ValueError, match="frame"):
        _compare(case)


def test_duplicate_event_and_row_ids_are_refused() -> None:
    case = _case()
    case["currentManifest"]["events"].append(
        deepcopy(case["currentManifest"]["events"][0])
    )
    with pytest.raises(ValueError, match="duplicate compiled event ID"):
        _compare(case)
    case = _case()
    case["currentDocument"]["activeDraft"]["blocks"].append(
        deepcopy(case["currentDocument"]["activeDraft"]["blocks"][0])
    )
    with pytest.raises(ValueError, match="duplicate draft block ID"):
        _compare(case)


def test_wrong_document_project_and_baseline_bindings_are_refused() -> None:
    case = _case()
    case["currentDocument"]["id"] = "wrong-document"
    with pytest.raises(ValueError, match="different document"):
        _compare(case)
    case = _case()
    case["currentDocument"]["projectId"] = "wrong-project"
    with pytest.raises(ValueError, match="different project"):
        _compare(case)
    case = _case()
    case["baselineMap"]["documentRevision"] += 1
    with pytest.raises(ValueError, match="documentRevision"):
        _compare(case)
    case = _case()
    case["baselineMap"]["rows"][0]["items"][0]["eventId"] = "unknown-event"
    with pytest.raises(ValueError, match="event/row differs"):
        _compare(case)
