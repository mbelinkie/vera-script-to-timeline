"""Fast, SDK-free checks for the script half of the three-way comparison."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.three_way_compare import (
    COMPATIBLE_RESOLVE_FIELDS,
    ROW_STATES,
    classify_row,
    compare_script_rows,
    compare_three_way_rows,
    shifted_rows,
)

FIXTURE = Path(__file__).parent / "data/three_way_compare/baseline.json"
OBSERVATION = Path(__file__).parent / "data/three_way_compare/observation.json"


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


def _three_way(
    case: dict[str, Any], observation: dict[str, Any] | None = None
) -> dict[str, Any]:
    return compare_three_way_rows(
        case["baselineManifest"],
        case["baselineMap"],
        case["baselineDocument"],
        case["currentManifest"],
        case["currentDocument"],
        deepcopy(
            observation
            if observation is not None
            else json.loads(OBSERVATION.read_text())
        ),
    )


def _observation() -> dict[str, Any]:
    observation: dict[str, Any] = json.loads(OBSERVATION.read_text())
    return observation


def _edit_item(observation: dict[str, Any], index: int, status: str = "moved") -> None:
    item = observation["rows"][index]["items"][0]
    item["status"] = [status]
    if status == "moved":
        item["changes"] = {
            "startFrame": {"before": index * 10, "after": index * 10 + 2}
        }
    elif status == "cannot tell":
        item["cannotRead"] = ["sourceStartFrame"]


def _editor_addition(
    observation: dict[str, Any], start: int | None, duration: int | None
) -> None:
    observation["rows"].append(
        {
            "rowId": None,
            "items": [
                {
                    "resolveItemId": "editor-clip-1",
                    "status": ["added"],
                    "trackKind": "video",
                    "trackIndex": 1,
                    "startFrame": start,
                    "durationFrames": duration,
                    "rowAttribution": "cannot tell from the current row boundaries",
                }
            ],
        }
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


def test_five_states_are_exhaustive_but_positive_is_synthetic_only() -> None:
    untouched = [{"status": ["unchanged"]}]
    moved = [
        {"status": ["moved"], "changes": {"startFrame": {"before": 10, "after": 12}}}
    ]
    named = [{"status": ["cannot tell"], "cannotRead": ["mediaId"]}]
    synthetic = [
        {"status": ["unchanged"], "changes": {"gainDb": {"before": -12, "after": -6}}}
    ]
    states = [
        classify_row(False, untouched)[0],
        classify_row(True, untouched)[0],
        classify_row(False, moved)[0],
        classify_row(
            True,
            synthetic,
            compatible_fields=frozenset({"gainDb"}),
            script_fields=frozenset(),
        )[0],
        classify_row(True, moved)[0],
    ]
    assert set(states) == ROW_STATES
    assert not COMPATIBLE_RESOLVE_FIELDS
    assert classify_row(True, synthetic)[0] == "both_conflict"
    assert (
        classify_row(True, synthetic, compatible_fields=frozenset({"gainDb"}))[0]
        == "both_conflict"
    )
    assert (
        classify_row(
            True,
            synthetic,
            compatible_fields=frozenset({"gainDb"}),
            script_fields=frozenset({"gainDb"}),
        )[0]
        == "both_conflict"
    )
    assert (
        classify_row(
            True,
            named,
            compatible_fields=frozenset({"mediaId"}),
            script_fields=frozenset(),
        )[0]
        == "both_conflict"
    )
    assert all(
        reason.strip()
        for flag in (False, True)
        for _, reason in (classify_row(flag, untouched), classify_row(flag, moved))
    )


def test_three_way_readback_coverage_is_not_a_row_edit_and_is_repeatable() -> None:
    case, observation = _case(), _observation()
    original = deepcopy((case, observation))
    first = _three_way(case, observation)
    assert first == _three_way(case, observation)
    assert (case, observation) == original
    assert [row["state"] for row in first["rows"]] == ["unchanged"] * 3
    assert first["unassignedEditorClips"] == []
    assert first["observationCoverage"]["cannotRead"] == [
        "grades",
        "effects",
        "media availability and source bytes",
    ]


def test_three_way_production_both_changes_remain_blocked() -> None:
    case, observation = _case(), _observation()
    b = _rows(case)[1]
    case["currentManifest"]["events"][1]["sourceRange"]["endFrame"] = 9
    _edit_item(observation, 1)
    result = _by_row(_three_way(case, observation))
    assert result[b]["state"] == "both_conflict"
    assert result[b]["blocked"]
    assert "not qualified" in result[b]["reason"]
    assert result[_rows(case)[0]]["state"] == "unchanged"


def test_unknown_clip_and_script_edit_conflict_without_edit_is_resolve() -> None:
    case, observation = _case(), _observation()
    a = _rows(case)[0]
    _edit_item(observation, 0, "cannot tell")
    assert _by_row(_three_way(case, observation))[a]["state"] == "resolve_changed"
    case["currentManifest"]["events"][0]["sourceRange"]["endFrame"] = 9
    row = _by_row(_three_way(case, observation))[a]
    assert row["state"] == "both_conflict"
    assert "unreadable" in row["reason"]


@pytest.mark.parametrize("growth", [25, -5])
def test_downstream_shift_signed_and_not_mistaken_for_content_edit(growth: int) -> None:
    case = _case()
    a, b, c = _rows(case)
    case["currentManifest"]["events"][0]["recordRange"]["endFrame"] += growth
    _shift_event(case, 1, 10 + growth)
    _shift_event(case, 2, 20 + growth)
    rows = _by_row(_three_way(case))
    assert rows[a]["scriptChange"] == "changed"
    assert rows[b]["scriptChange"] == rows[c]["scriptChange"] == "unchanged"
    assert rows[b]["shiftFrames"] == rows[c]["shiftFrames"] == growth
    assert rows[b]["state"] == rows[c]["state"] == "script_changed"
    assert ("later" if growth > 0 else "earlier") in rows[b]["reason"]
    assert shifted_rows(
        {a: 0, b: 10, c: 20}, {a: 0, b: 10 + growth, c: 20 + growth}
    ) == {b: growth, c: growth}


@pytest.mark.parametrize("invalid", [True, -1, 2**53, 1.5])
def test_shifted_rows_rejects_unsafe_frames(invalid: Any) -> None:
    with pytest.raises(ValueError, match="frame"):
        shifted_rows({"row": 10}, {"row": invalid})


def test_unassigned_clip_is_visible_and_blocks_only_overlapping_proposed_rows() -> None:
    case, observation = _case(), _observation()
    a, b, c = _rows(case)
    case["currentManifest"]["events"][0]["recordRange"]["endFrame"] = 35
    _shift_event(case, 1, 35)
    _shift_event(case, 2, 45)
    _editor_addition(observation, 37, 3)
    result = _three_way(case, observation)
    assert result["unassignedEditorClips"][0]["resolveItemId"] == "editor-clip-1"
    rows = _by_row(result)
    assert rows[a]["state"] == "script_changed"
    assert rows[b]["state"] == "both_conflict"
    assert rows[b]["editorOverlaps"] == ["editor-clip-1"]
    assert rows[b]["blocked"]
    assert rows[c]["state"] == "script_changed"
    assert rows[c]["editorOverlaps"] == []


def test_unassigned_editor_clip_at_old_shifted_position_blocks_row() -> None:
    case, observation = _case(), _observation()
    _, _, c = _rows(case)
    case["currentManifest"]["events"][0]["recordRange"]["endFrame"] = 5
    _shift_event(case, 1, 5)
    _shift_event(case, 2, 15)
    _editor_addition(observation, 26, 3)  # C's original 20-30, not new 15-25.
    row = _by_row(_three_way(case, observation))[c]
    assert row["shiftFrames"] == -5
    assert row["editorOverlaps"] == ["editor-clip-1"]
    assert row["state"] == "both_conflict" and row["blocked"]


def test_gap_in_row_envelope_does_not_fabricate_editor_overlap() -> None:
    case, observation = _case(), _observation()
    a = _rows(case)[0]
    second = deepcopy(case["currentManifest"]["events"][0])
    second["eventId"] = "new-clip-in-same-row"
    second["recordRange"] = {"startFrame": 30, "endFrame": 40}
    case["currentManifest"]["events"].append(second)
    _editor_addition(observation, 15, 3)
    row = _by_row(_three_way(case, observation))[a]
    assert row["currentEndFrame"] == 40
    assert row["editorOverlaps"] == []
    assert row["state"] == "script_changed"


def test_unassigned_editor_with_unknown_geometry_blocks_any_script_update() -> None:
    case, observation = _case(), _observation()
    case["currentManifest"]["events"][1]["sourceRange"]["endFrame"] = 9
    _editor_addition(observation, None, 4)
    b = _rows(case)[1]
    row = _by_row(_three_way(case, observation))[b]
    assert row["state"] == "both_conflict"
    assert "unreadable timing" in " ".join(row["hazards"])


def test_attributed_editor_clip_changes_only_its_row() -> None:
    case, observation = _case(), _observation()
    b = _rows(case)[1]
    observation["rows"][1]["items"].append(
        {
            "resolveItemId": "editor-inside-b",
            "status": ["added"],
            "trackKind": "video",
            "trackIndex": 2,
            "startFrame": 12,
            "durationFrames": 2,
        }
    )
    result = _three_way(case, observation)
    assert _by_row(result)[b]["state"] == "resolve_changed"
    assert result["otherEditorClips"][0]["rowId"] == b
    assert result["unassignedEditorClips"] == []


def test_unassigned_baseline_managed_clip_is_not_dropped_from_observation() -> None:
    case, observation = _case(), _observation()
    event = deepcopy(case["baselineManifest"]["events"][0])
    event["eventId"] = "unowned-compiled-event"
    event["provenance"]["blockId"] = None
    for side in ("baselineManifest", "currentManifest"):
        case[side]["events"].append(deepcopy(event))
    case["baselineMap"]["rows"].append(
        {
            "rowId": None,
            "timelineId": "native-timeline-1",
            "startFrame": 0,
            "lengthFrames": 10,
            "items": [
                {
                    "eventId": "unowned-compiled-event",
                    "resolveItemId": "native-unowned-item",
                    "trackId": "video-root",
                    "startFrame": 0,
                    "durationFrames": 10,
                }
            ],
        }
    )
    observation["rows"].append(
        {
            "rowId": None,
            "items": [
                {
                    "eventId": "unowned-compiled-event",
                    "resolveItemId": "native-unowned-item",
                    "status": ["moved"],
                    "changes": {"startFrame": {"before": 0, "after": 3}},
                }
            ],
        }
    )
    result = _three_way(case, observation)
    assert result["unassignedManagedClips"][0]["status"] == ["moved"]
    assert result["unassignedEditorClips"] == []
    assert result["unownedManagedComparison"]["state"] == "resolve_changed"
    # Even when its own event is unchanged, a row update could destroy this
    # unattributed native edit; there is no safe ownership inference.
    first = _rows(case)[0]
    case["currentManifest"]["events"][0]["sourceRange"]["endFrame"] = 9
    row = _by_row(_three_way(case, observation))[first]
    assert row["state"] == "both_conflict" and row["blocked"]
    # A changed *unowned* compiled event must also be classified, not merely
    # copied into an inventory that a future planner might ignore.
    case["currentManifest"]["events"][0]["sourceRange"]["endFrame"] = 10
    case["currentManifest"]["events"][-1]["sourceRange"]["endFrame"] = 9
    conflicting = _three_way(case, observation)
    assert conflicting["unownedManagedComparison"]["state"] == "both_conflict"
    assert conflicting["unownedManagedComparison"]["blocked"]
    assert all(row["blocked"] for row in conflicting["rows"])


def test_new_unowned_compiled_event_conflicts_with_unassigned_editor_clip() -> None:
    case, observation = _case(), _observation()
    global_event = deepcopy(case["currentManifest"]["events"][0])
    global_event["eventId"] = "new-unowned-compiled-event"
    global_event["provenance"]["blockId"] = None
    global_event["recordRange"] = {"startFrame": 31, "endFrame": 41}
    case["currentManifest"]["events"].append(global_event)
    _editor_addition(observation, 34, 4)
    result = _three_way(case, observation)
    global_comparison = result["unownedManagedComparison"]
    assert global_comparison["state"] == "both_conflict"
    assert global_comparison["blocked"]
    assert (
        global_comparison["unassignedEditorClips"][0]["resolveItemId"]
        == "editor-clip-1"
    )
    assert all(
        row["state"] == "both_conflict" and row["blocked"] for row in result["rows"]
    )


def _transition(case: dict[str, Any]) -> None:
    a, b, _ = _rows(case)
    transition = {
        "id": "transition-a-b",
        "fromRowId": a,
        "toRowId": b,
        "boundaryFrame": 10,
        "startFrame": 9,
        "endFrame": 11,
        "effectIdentity": {"kind": "cross_dissolve"},
        "disposition": "apply",
    }
    for side in ("baselineManifest", "currentManifest"):
        case[side]["transitions"] = [deepcopy(transition)]


def test_transition_is_paired_and_changed_boundary_affects_both_sides() -> None:
    case = _case()
    a, b, c = _rows(case)
    _transition(case)
    case["currentManifest"]["events"][0]["recordRange"]["endFrame"] = 35
    _shift_event(case, 1, 35)
    _shift_event(case, 2, 45)
    current = case["currentManifest"]["transitions"][0]
    for field in ("boundaryFrame", "startFrame", "endFrame"):
        current[field] += 25
    result = _by_row(_three_way(case))
    assert [item["kind"] for item in result[a]["dependencyImpacts"]] == ["transition"]
    assert [item["kind"] for item in result[b]["dependencyImpacts"]] == ["transition"]
    assert not result[c]["dependencyImpacts"]


def test_upstream_shift_alone_does_not_change_transition_signature() -> None:
    case = _case()
    _transition(case)
    a, b, c = _rows(case)
    # Transition B->C survives an unrelated growth of A unchanged relative to B.
    for side in ("baselineManifest", "currentManifest"):
        trans = side == "currentManifest"
        transition = case[side]["transitions"][0]
        transition["fromRowId"], transition["toRowId"] = b, c
        transition["boundaryFrame"] = 20 + (25 if trans else 0)
        transition["startFrame"] = 19 + (25 if trans else 0)
        transition["endFrame"] = 21 + (25 if trans else 0)
    case["currentManifest"]["events"][0]["recordRange"]["endFrame"] = 35
    _shift_event(case, 1, 35)
    _shift_event(case, 2, 45)
    rows = _by_row(_three_way(case))
    assert rows[a]["dependencyImpacts"] == []
    assert rows[b]["dependencyImpacts"] == rows[c]["dependencyImpacts"] == []


def test_shifted_transition_partner_is_blocked_by_resolve_edit() -> None:
    case, observation = _case(), _observation()
    _transition(case)
    a, b, c = _rows(case)
    for side in ("baselineManifest", "currentManifest"):
        transition = case[side]["transitions"][0]
        transition["fromRowId"], transition["toRowId"] = b, c
        shift = 25 if side == "currentManifest" else 0
        transition.update(
            boundaryFrame=20 + shift, startFrame=19 + shift, endFrame=21 + shift
        )
    case["currentManifest"]["events"][0]["recordRange"]["endFrame"] = 35
    _shift_event(case, 1, 35)
    _shift_event(case, 2, 45)
    _edit_item(observation, 2)
    rows = _by_row(_three_way(case, observation))
    assert rows[a]["dependencyImpacts"] == []
    assert rows[b]["scriptChange"] == "unchanged"
    assert rows[b]["shiftFrames"] == 25
    assert rows[b]["state"] == "both_conflict" and rows[b]["blocked"]
    assert rows[b]["dependencyImpacts"][0]["kind"] == "transition"
    assert rows[c]["state"] == "both_conflict"


def test_reordering_transition_endpoint_is_an_explicit_boundary_hazard() -> None:
    case = _case()
    a, b, _ = _rows(case)
    _transition(case)
    blocks = case["currentDocument"]["activeDraft"]["blocks"]
    blocks[1], blocks[2] = blocks[2], blocks[1]
    _shift_event(case, 1, 20)
    _shift_event(case, 2, 10)
    rows = _by_row(_three_way(case))
    assert "no longer between adjacent" in rows[a]["dependencyImpacts"][0]["reason"]
    assert rows[b]["scriptChange"] == "reordered"


def test_editor_at_transition_boundary_blocks_both_without_clip_overlap() -> None:
    case, observation = _case(), _observation()
    a, b, c = _rows(case)
    _transition(case)
    case["currentManifest"]["events"][0]["recordRange"]["endFrame"] = 8
    case["currentManifest"]["events"][1]["recordRange"] = {
        "startFrame": 12,
        "endFrame": 20,
    }
    case["currentManifest"]["transitions"][0].update(startFrame=8, endFrame=12)
    _editor_addition(observation, 9, 2)  # Only the transition, not A/B's clips.
    rows = _by_row(_three_way(case, observation))
    for row_id in (a, b):
        assert rows[row_id]["editorOverlaps"] == ["editor-clip-1"]
        assert rows[row_id]["state"] == "both_conflict"
    assert rows[c]["editorOverlaps"] == []


def _music_span(case: dict[str, Any], first: str, last: str) -> None:
    music = {
        "eventId": "music-event-id",
        "kind": "music",
        "trackId": "music-a5",
        "provenance": {"documentId": case["baselineDocument"]["id"], "blockId": first},
        "recordRange": {"startFrame": 0, "endFrame": 30},
        "music": {
            "spanId": "music-span-id",
            "startRowId": first,
            "endRowId": last,
            "requestedEndFrame": 30,
            "gainDb": -12,
        },
    }
    case["baselineManifest"]["tracks"].append({"id": "music-a5"})
    case["currentManifest"]["tracks"].append({"id": "music-a5"})
    for side in ("baselineManifest", "currentManifest"):
        case[side]["events"].append(deepcopy(music))
    first_row = next(
        row for row in case["baselineMap"]["rows"] if row["rowId"] == first
    )
    first_row["lengthFrames"] = 30
    first_row["items"].append(
        {
            "eventId": "music-event-id",
            "resolveItemId": "native-music-item",
            "trackId": "music-a5",
            "startFrame": 0,
            "durationFrames": 30,
        }
    )


def test_music_span_propagates_change_atomically_to_every_participating_row() -> None:
    case, observation = _case(), _observation()
    a, b, c = _rows(case)
    _music_span(case, a, c)
    observation["rows"][0]["items"].append(
        {
            "eventId": "music-event-id",
            "resolveItemId": "native-music-item",
            "status": ["unchanged"],
        }
    )
    case["currentManifest"]["events"][1]["sourceRange"]["endFrame"] = 9
    rows = _by_row(_three_way(case, observation))
    assert all(rows[row]["state"] == "script_changed" for row in (a, b, c))
    assert all(
        [entry["kind"] for entry in rows[row]["dependencyImpacts"]] == ["music"]
        for row in (a, b, c)
    )
    assert rows[c]["scriptChange"] == "unchanged"


def test_shifted_music_requested_end_does_not_change_own_row_contents() -> None:
    case, observation = _case(), _observation()
    a, b, c = _rows(case)
    _music_span(case, b, c)
    for side in ("baselineManifest", "currentManifest"):
        event = case[side]["events"][-1]
        event["recordRange"] = {"startFrame": 10, "endFrame": 30}
        event["music"]["requestedEndFrame"] = 30
    b_map = next(row for row in case["baselineMap"]["rows"] if row["rowId"] == b)
    b_map["startFrame"] = 10
    b_map["lengthFrames"] = 20
    b_map["items"][-1].update(startFrame=10, durationFrames=20)
    observation["rows"][1]["items"].append(
        {
            "eventId": "music-event-id",
            "resolveItemId": "native-music-item",
            "status": ["unchanged"],
        }
    )
    case["currentManifest"]["events"][0]["recordRange"]["endFrame"] = 15
    _shift_event(case, 1, 15)
    _shift_event(case, 2, 25)
    music = case["currentManifest"]["events"][-1]
    music["recordRange"] = {"startFrame": 15, "endFrame": 35}
    music["music"]["requestedEndFrame"] = 35
    rows = _by_row(_three_way(case, observation))
    assert rows[a]["scriptChange"] == "changed"
    assert rows[b]["scriptChange"] == rows[c]["scriptChange"] == "unchanged"
    assert rows[b]["shiftFrames"] == rows[c]["shiftFrames"] == 5
    assert rows[b]["dependencyImpacts"] == rows[c]["dependencyImpacts"] == []


def test_editor_in_music_only_gap_blocks_all_rows_of_changed_span() -> None:
    case, observation = _case(), _observation()
    a, b, c = _rows(case)
    _music_span(case, a, c)
    observation["rows"][0]["items"].append(
        {
            "eventId": "music-event-id",
            "resolveItemId": "native-music-item",
            "status": ["unchanged"],
        }
    )
    case["currentManifest"]["events"][1]["recordRange"]["endFrame"] = 12
    _editor_addition(observation, 14, 2)  # Between B and C clips, within A5.
    rows = _by_row(_three_way(case, observation))
    assert all(rows[row]["editorOverlaps"] == ["editor-clip-1"] for row in (a, b, c))
    assert all(rows[row]["state"] == "both_conflict" for row in (a, b, c))


def test_music_and_transition_cross_row_resolve_edit_requires_review() -> None:
    case, observation = _case(), _observation()
    a, b, c = _rows(case)
    _music_span(case, a, c)
    observation["rows"][0]["items"].append(
        {
            "eventId": "music-event-id",
            "resolveItemId": "native-music-item",
            "status": ["unchanged"],
        }
    )
    _transition(case)
    case["currentManifest"]["events"][0]["sourceRange"]["endFrame"] = 9
    _edit_item(observation, 2)
    rows = _by_row(_three_way(case, observation))
    assert all(
        rows[row]["blocked"] and rows[row]["state"] == "both_conflict"
        for row in (a, b, c)
    )
    assert len(rows[a]["dependencyImpacts"]) == 2


def test_changed_music_span_endpoint_with_no_valid_ancestry_is_refused() -> None:
    case, observation = _case(), _observation()
    a, _, c = _rows(case)
    _music_span(case, a, c)
    observation["rows"][0]["items"].append(
        {
            "eventId": "music-event-id",
            "resolveItemId": "native-music-item",
            "status": ["unchanged"],
        }
    )
    case["currentManifest"]["events"][-1]["music"]["endRowId"] = "missing-row"
    with pytest.raises(ValueError, match="contradictory row identity"):
        _three_way(case, observation)


def test_observation_identity_status_inventory_and_duplicate_guards() -> None:
    case, observation = _case(), _observation()
    observation["timelineId"] = "copy-of-original"
    with pytest.raises(ValueError, match="observation timelineId"):
        _three_way(case, observation)
    observation = _observation()
    observation["rows"][0]["items"][0]["status"] = ["future-status"]
    with pytest.raises(ValueError, match="item status"):
        _three_way(case, observation)
    observation = _observation()
    observation["rows"][1]["items"][0]["resolveItemId"] = "native-item-1"
    with pytest.raises(ValueError, match="duplicate observed"):
        _three_way(case, observation)
    observation = _observation()
    observation["rows"].pop()
    with pytest.raises(ValueError, match="omitted a baseline"):
        _three_way(case, observation)
