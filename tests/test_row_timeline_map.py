"""Fast, SDK-free checks for post-verify row-to-timeline snapshots."""

from __future__ import annotations

import ast
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.row_timeline_map import (
    SCHEMA_VERSION,
    SCHEMA_VERSION_V2,
    compare_reopened_row_map,
    make_row_timeline_map,
    observe_item_details,
    validate_saved_row_map,
)

COMPILER_FIXTURES = Path(__file__).parent / "data/authoring_v2/issue_173/compiler"


def test_row_map_is_in_the_complete_verified_resolve_runtime(tmp_path: Path) -> None:
    from vera_timeline_agent.workflow_v2_cli import RUNTIME_FILES, build_release_v2

    assert "row_timeline_map.py" in RUNTIME_FILES
    source = Path(__file__).parents[1] / "integrations/resolve/VERA Delivery v2.py"
    tree = ast.parse(source.read_text())
    inventory = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "TI_RUNTIME_FILES"
            for target in node.targets
        )
    )
    assert tuple(RUNTIME_FILES) == tuple(inventory)
    release = tmp_path / "release"
    build_release_v2(release)
    bundled = (
        release / "vera-delivery-v2/python/vera_timeline_agent/row_timeline_map.py"
    )
    source = Path(__file__).parents[1] / "python" / "vera_timeline_agent"
    assert bundled.read_bytes() == (source / "row_timeline_map.py").read_bytes()


def _event(
    event_id: str,
    track_id: str,
    kind: str,
    start: int,
    duration: int,
    block: str | None,
) -> dict[str, Any]:
    original = {
        "eventId": event_id,
        "kind": "narration" if kind == "audio" else "primary_visual",
        "recordRange": {"startFrame": start, "endFrame": start + duration},
        "provenance": {"blockId": block},
    }
    return {
        "id": event_id,
        "trackId": track_id,
        "trackKind": kind,
        "recordRange": {"startFrame": start, "durationFrames": duration},
        "v2Event": original,
    }


def _sample() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    view = {
        "tracks": [
            {"id": "v", "kind": "video", "index": 1, "name": "Primary"},
            {"id": "a", "kind": "audio", "index": 2, "name": "Narration"},
            {"id": "overlay", "kind": "video", "index": 2, "name": "Overlay"},
        ],
        "events": [
            _event("e3", "a", "audio", 10, 5, "row-A"),
            _event("e2", "v", "video", 30, 5, "row-A"),
            _event("e5", "overlay", "video", 41, 7, None),
            _event("e1", "v", "video", 10, 5, "row-A"),
            _event("e4", "v", "video", 37, 4, "row-Z"),
        ],
    }
    manifest = {
        "buildId": "b1",
        "id": "m1",
        "document": {"documentId": "d1", "revision": 3},
        "events": [deepcopy(event["v2Event"]) for event in view["events"]],
    }
    tracks = {track["id"]: track for track in view["tracks"]}
    observed = [
        {
            "eventId": event["id"],
            "resolveItemId": "native-" + event["id"],
            "trackId": event["trackId"],
            "trackKind": event["trackKind"],
            "trackIndex": tracks[event["trackId"]]["index"],
            "startFrame": event["recordRange"]["startFrame"],
            "durationFrames": event["recordRange"]["durationFrames"],
        }
        for event in view["events"]
    ]
    return manifest, view, observed


def _make(
    manifest: dict[str, Any],
    view: dict[str, Any],
    observed: list[dict[str, Any]],
    **overrides: Any,
) -> dict[str, Any]:
    options: dict[str, Any] = dict(
        project_name="Producer's Project",
        resolve_project_id="resolve-project-UID",
        timeline_name="New VERA timeline",
        timeline_id="resolve-timeline-UID",
    )
    options.update(overrides)
    return make_row_timeline_map(manifest, view, observed, **options)


def _v2_observed(observed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **item,
            "name": f"Clip {item['eventId']}",
            "mediaId": None,
            "sourceStartFrame": 0,
            "sourceEndFrame": item["durationFrames"] - 1,
        }
        for item in observed
    ]


def test_groups_multitrack_events_and_explicit_null_block_with_exact_native_ids() -> (
    None
):
    manifest, view, observed = _sample()
    result = _make(manifest, view, observed)

    assert result["schemaVersion"] == SCHEMA_VERSION
    assert result["version"] == 1
    assert result["buildId"] == "b1"
    assert result["manifestId"] == "m1"
    assert result["documentId"] == "d1"
    assert result["documentRevision"] == 3
    assert result["projectName"] == "Producer's Project"
    assert result["resolveProjectId"] == "resolve-project-UID"
    assert result["timelineName"] == "New VERA timeline"
    assert result["timelineId"] == "resolve-timeline-UID"

    rows = result["rows"]
    assert [row["rowId"] for row in rows] == ["row-A", "row-Z", None]
    assert all(row["timelineId"] == "resolve-timeline-UID" for row in rows)
    assert (rows[0]["startFrame"], rows[0]["lengthFrames"]) == (10, 25)
    assert [item["eventId"] for item in rows[0]["items"]] == ["e3", "e1", "e2"]
    assert (rows[1]["startFrame"], rows[1]["lengthFrames"]) == (37, 4)
    assert (rows[2]["startFrame"], rows[2]["lengthFrames"]) == (41, 7)
    assert rows[2]["items"][0]["resolveItemId"] == "native-e5"
    assert rows[0]["items"][0] == {
        "eventId": "e3",
        "resolveItemId": "native-e3",
        "trackId": "a",
        "trackKind": "audio",
        "trackIndex": 2,
        "startFrame": 10,
        "durationFrames": 5,
    }
    assert {item["resolveItemId"] for row in rows for item in row["items"]} == {
        "native-e1",
        "native-e2",
        "native-e3",
        "native-e4",
        "native-e5",
    }
    assert len(json.loads(json.dumps(result))["rows"]) == 3


def test_observation_and_delivery_order_cannot_change_map_bytes() -> None:
    manifest, view, observed = _sample()
    expected = json.dumps(_make(manifest, view, observed), sort_keys=True)
    view["events"].reverse()
    observed.reverse()
    manifest["events"].reverse()
    assert json.dumps(_make(manifest, view, observed), sort_keys=True) == expected


def test_v2_map_preserves_nullable_details_and_document_hash_binding() -> None:
    manifest, view, observed = _sample()
    manifest["document"].update(
        contentHash="sha256:" + "a" * 64,
    )
    result = _make(manifest, view, _v2_observed(observed), version=2)

    assert result["schemaVersion"] == SCHEMA_VERSION_V2
    assert result["version"] == 2
    assert result["buildId"] == "b1"
    assert result["manifestId"] == "m1"
    assert result["documentId"] == "d1"
    assert result["documentRevision"] == 3
    assert result["documentContentHash"] == "sha256:" + "a" * 64
    first = result["rows"][0]["items"][0]
    assert first["name"] == "Clip e3"
    assert first["mediaId"] is None
    assert first["sourceStartFrame"] == 0
    assert first["sourceEndFrame"] == 4


def test_v2_item_detail_observation_preserves_unavailable_getters_as_null() -> None:
    class NativeItem:
        def GetName(self) -> str:
            return "Interview"

        def GetMediaPoolItem(self) -> object:
            return object()

        def GetSourceStartFrame(self) -> int:
            return 10

    assert observe_item_details(NativeItem()) == {
        "name": "Interview",
        "mediaId": None,
        "sourceStartFrame": 10,
        "sourceEndFrame": None,
    }

    class MalformedOptionalDetails:
        def GetName(self) -> str:
            return "  "

        def GetMediaPoolItem(self) -> MalformedOptionalDetails:
            return self

        def GetMediaId(self) -> int:
            return 5

        def GetSourceStartFrame(self) -> int:
            return 10

        def GetSourceEndFrame(self) -> int:
            return 9

    assert observe_item_details(MalformedOptionalDetails()) == {
        "name": None,
        "mediaId": None,
        "sourceStartFrame": None,
        "sourceEndFrame": None,
    }


@pytest.mark.parametrize(
    ("field", "replacement", "error"),
    [
        ("name", 7, "invalid reopened item name"),
        ("mediaId", [], "invalid reopened item mediaId"),
        ("sourceStartFrame", True, "invalid reopened item sourceStartFrame"),
        ("sourceEndFrame", -1, "invalid reopened item source range"),
    ],
)
def test_v2_requires_and_validates_nullable_item_details(
    field: str, replacement: Any, error: str
) -> None:
    manifest, view, observed = _sample()
    detailed = _v2_observed(observed)
    if field == "sourceEndFrame":
        detailed[0]["sourceStartFrame"] = 2
    detailed[0][field] = replacement
    with pytest.raises(ValueError, match=error):
        _make(manifest, view, detailed, version=2)


def test_v2_saved_map_revalidates_and_compares_v1_structural_readback() -> None:
    manifest, view, observed = _sample()
    saved = _make(manifest, view, _v2_observed(observed), version=2)
    validate_saved_row_map(manifest, view, saved)
    assert (
        compare_reopened_row_map(
            manifest,
            view,
            observed,
            project_name=saved["projectName"],
            resolve_project_id=saved["resolveProjectId"],
            timeline_name=saved["timelineName"],
            timeline_id=saved["timelineId"],
            saved_map=saved,
        )
        == "saved-uid-match"
    )
    with pytest.raises(ValueError, match="saved row map differs"):
        compare_reopened_row_map(
            manifest,
            view,
            [{**observed[0], "resolveItemId": "changed-uid"}, *observed[1:]],
            project_name=saved["projectName"],
            resolve_project_id=saved["resolveProjectId"],
            timeline_name=saved["timelineName"],
            timeline_id=saved["timelineId"],
            saved_map=saved,
        )


@pytest.mark.parametrize(
    ("change", "error"),
    [
        (lambda m, v, o: o.pop(), "observed item inventory differs"),
        (lambda m, v, o: o.append({**o[0], "eventId": "extra"}), "inventory differs"),
        (lambda m, v, o: o.append(o[0].copy()), "duplicate observed event ID"),
        (lambda m, v, o: o[0].update(eventId=""), "observed event ID"),
        (lambda m, v, o: o[0].update(resolveItemId=""), "TimelineItem UID"),
        (lambda m, v, o: o[0].update(resolveItemId="   "), "TimelineItem UID"),
        (lambda m, v, o: o[0].update(resolveItemId=77), "TimelineItem UID"),
        (
            lambda m, v, o: o[1].update(resolveItemId=o[0]["resolveItemId"]),
            "duplicate reopened TimelineItem UID",
        ),
        (lambda m, v, o: o[0].update(trackId="overlay"), "differs from view"),
        (lambda m, v, o: o[0].update(trackKind="video"), "differs from view"),
        (lambda m, v, o: o[0].update(trackIndex=1), "differs from view"),
        (lambda m, v, o: o[0].update(trackIndex=True), "differs from view"),
        (lambda m, v, o: o[0].update(startFrame=9), "differs from view"),
        (lambda m, v, o: o[0].update(startFrame=True), "differs from view"),
        (lambda m, v, o: o[0].update(durationFrames=6), "differs from view"),
        (lambda m, v, o: o[0].update(durationFrames=5.0), "differs from view"),
        (
            lambda m, v, o: v["events"].append(v["events"][0].copy()),
            "duplicate VERA event ID",
        ),
        (lambda m, v, o: v["tracks"].append(v["tracks"][0].copy()), "duplicate track"),
        (
            lambda m, v, o: v["tracks"].append(
                {"id": "alt", "kind": "video", "index": 1}
            ),
            "duplicate track",
        ),
        (lambda m, v, o: v["tracks"][0].update(index=True), "invalid track index"),
        (
            lambda m, v, o: v["events"][0].update(trackId="missing"),
            "missing or unsupported",
        ),
        (
            lambda m, v, o: v["events"][0].update(trackKind="video"),
            "track kind differs",
        ),
        (
            lambda m, v, o: v["events"][0]["recordRange"].update(startFrame=-1),
            "invalid view start",
        ),
        (
            lambda m, v, o: v["events"][0]["recordRange"].update(durationFrames=0),
            "invalid view duration",
        ),
        (
            lambda m, v, o: v["events"][0]["v2Event"].update(eventId="wrong"),
            "manifest and view event differs",
        ),
        (
            lambda m, v, o: v["events"][0]["v2Event"].pop("provenance"),
            "manifest and view event differs",
        ),
        (
            lambda m, v, o: v["events"][0]["v2Event"]["provenance"].update(blockId=""),
            "manifest and view event differs",
        ),
        (
            lambda m, v, o: v["events"][0]["v2Event"]["recordRange"].update(
                endFrame=14
            ),
            "manifest and view event differs",
        ),
        (
            lambda m, v, o: m["events"].pop(),
            "manifest and view event inventory differs",
        ),
        (
            lambda m, v, o: m["events"].append(m["events"][0].copy()),
            "duplicate manifest event",
        ),
    ],
)
def test_rejects_missing_duplicate_ambiguous_or_mismatched_items(
    change: Any, error: str
) -> None:
    manifest, view, observed = _sample()
    manifest, view, observed = deepcopy((manifest, view, observed))
    change(manifest, view, observed)
    with pytest.raises(ValueError, match=error):
        _make(manifest, view, observed)


def test_unassigned_event_with_minimal_v2_provenance_is_not_invented() -> None:
    manifest, view, observed = _sample()
    manifest.pop("events")  # minimal workflow fake, with no separate manifest inventory
    view["events"][0]["v2Event"]["provenance"].pop("blockId")
    row_map = _make(manifest, view, observed)
    assert {item["eventId"] for item in row_map["rows"][-1]["items"]} == {"e3", "e5"}


@pytest.mark.parametrize(
    ("field", "replacement", "error"),
    [
        ("eventId", "wrong", "v2 event identity"),
        ("provenance", None, "v2 event provenance"),
        ("provenance", {"blockId": ""}, "script block ID"),
        ("recordRange", {"startFrame": 10, "endFrame": 16}, "record range differs"),
        ("kind", "script_marker", "invalid v2 event identity or marker"),
    ],
)
def test_minimal_manifest_still_refuses_bad_source_rows(
    field: str, replacement: Any, error: str
) -> None:
    manifest, view, observed = _sample()
    manifest.pop("events")
    view["events"][0]["v2Event"][field] = replacement
    with pytest.raises(ValueError, match=error):
        _make(manifest, view, observed)


@pytest.mark.parametrize(
    "override", ["project_name", "resolve_project_id", "timeline_name", "timeline_id"]
)
def test_requires_real_project_and_timeline_identifiers(override: str) -> None:
    manifest, view, observed = _sample()
    with pytest.raises(ValueError, match="missing or invalid"):
        _make(manifest, view, observed, **{override: "  "})


def _compiler_map(fixture: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Derive just the delivery-view fields from an actual compiler golden."""
    manifest = json.loads(
        (COMPILER_FIXTURES / f"{fixture}.manifest.golden.json").read_text()
    )
    by_track = {track["id"]: track for track in manifest["tracks"]}
    events = [event for event in manifest["events"] if event["kind"] != "script_marker"]
    view = {
        "tracks": manifest["tracks"],
        "events": [
            {
                "id": event["eventId"],
                "trackId": event["trackId"],
                "trackKind": by_track[event["trackId"]]["kind"],
                "recordRange": {
                    "startFrame": event["recordRange"]["startFrame"],
                    "durationFrames": event["recordRange"]["endFrame"]
                    - event["recordRange"]["startFrame"],
                },
                "v2Event": event,
            }
            for event in events
        ],
    }
    observed = [
        {
            "eventId": event["id"],
            "resolveItemId": "fake-post-reopen-" + event["id"],
            "trackId": event["trackId"],
            "trackKind": event["trackKind"],
            "trackIndex": by_track[event["trackId"]]["index"],
            "startFrame": event["recordRange"]["startFrame"],
            "durationFrames": event["recordRange"]["durationFrames"],
        }
        for event in view["events"]
    ]
    return manifest, _make(manifest, view, observed)


def test_compiler_golden_preserves_source_audio_and_fractional_frame_geometry() -> None:
    manifest, row_map = _compiler_map("selected-clip-ntsc")
    events = [event for event in manifest["events"] if event["kind"] != "script_marker"]
    assert len(row_map["rows"]) == 1
    row = row_map["rows"][0]
    assert row["rowId"] == events[0]["provenance"]["blockId"]
    assert row["startFrame"] == 0
    assert row["lengthFrames"] == 240
    assert len(row["items"]) == 2
    assert {item["trackKind"] for item in row["items"]} == {"audio", "video"}
    assert {item["eventId"] for item in row["items"]} == {
        event["eventId"] for event in events
    }


def test_compiler_marker_is_not_mistaken_for_a_timeline_item() -> None:
    manifest, row_map = _compiler_map("editor-note-marker")
    marker_ids = {
        event["eventId"]
        for event in manifest["events"]
        if event["kind"] == "script_marker"
    }
    item_ids = {item["eventId"] for row in row_map["rows"] for item in row["items"]}
    assert len(marker_ids) == 1
    assert not item_ids.intersection(marker_ids)
    assert len(item_ids) == 2
    assert row_map["rows"][0]["lengthFrames"] == 96


def test_compiler_multi_block_golden_retains_each_row_extent() -> None:
    manifest, row_map = _compiler_map("editor-note-between-unknown-duration")
    assert len(manifest["events"]) == 3
    assert len(row_map["rows"]) == 2
    assert [(row["startFrame"], row["lengthFrames"]) for row in row_map["rows"]] == [
        (0, 96),
        (96, 72),
    ]
    assert [len(row["items"]) for row in row_map["rows"]] == [2, 1]
    assert {row["rowId"] for row in row_map["rows"]} == {
        event["provenance"]["blockId"] for event in manifest["events"]
    }
