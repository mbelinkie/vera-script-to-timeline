"""Pure row grouping for a structurally verified VERA v2 Resolve build.

The caller supplies the *reopened* item inventory, after checking each native
item's VERA event stamp. This module cannot establish native item identity on
its own; it refuses to serialize incomplete or contradictory observations.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SCHEMA_VERSION = "vera-row-timeline-map/v1"


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing or invalid {label}")
    return value


def _frame(value: Any, label: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError(f"invalid {label}")
    return value


def make_row_timeline_map(
    manifest: Mapping[str, Any],
    view: Mapping[str, Any],
    observed: Sequence[Mapping[str, Any]],
    *,
    project_name: str,
    resolve_project_id: str,
    timeline_name: str,
    timeline_id: str,
) -> dict[str, Any]:
    """Group delivered non-marker events by their actual script block ID.

    ``observed`` has one verified reopened TimelineItem per delivery view event:
    eventId, resolveItemId, trackId, trackKind, trackIndex, startFrame, and
    durationFrames. The caller must have checked each item's marker stamp and
    resolved its identity *after* save/close/reopen. Row extents are envelopes,
    not uninterrupted clip coverage; null blockId means explicitly unassigned.
    """
    for label, value in (
        ("project name", project_name),
        ("Resolve project UID", resolve_project_id),
        ("timeline name", timeline_name),
        ("timeline UID", timeline_id),
    ):
        _identifier(value, label)
    build_id = _identifier(manifest.get("buildId"), "build ID")
    manifest_id = _identifier(manifest.get("id"), "manifest ID")
    document = _object(manifest.get("document"), "manifest document")
    document_id = _identifier(document.get("documentId"), "document ID")
    revision = document.get("revision")
    if revision is not None and (type(revision) is not int or revision < 0):
        raise ValueError("invalid document revision")

    track_values = view.get("tracks")
    event_values = view.get("events")
    if not isinstance(track_values, list) or not isinstance(event_values, list):
        raise ValueError("delivery view tracks and events must be arrays")
    tracks: dict[str, Mapping[str, Any]] = {}
    slots: set[tuple[str, int]] = set()
    for value in track_values:
        track = _object(value, "delivery track")
        track_id = _identifier(track.get("id"), "track ID")
        kind = track.get("kind")
        index = _frame(track.get("index"), "track index", positive=True)
        if kind not in {"video", "audio", "subtitle"}:
            raise ValueError("invalid track kind")
        if track_id in tracks or (kind, index) in slots:
            raise ValueError("duplicate track ID or slot")
        tracks[track_id] = track
        slots.add((kind, index))

    events: dict[str, Mapping[str, Any]] = {}
    for value in event_values:
        event = _object(value, "delivery event")
        event_id = _identifier(event.get("id"), "VERA event ID")
        if event_id in events:
            raise ValueError("duplicate VERA event ID")
        events[event_id] = event

    # Real manifests include marker events; they never become TimelineItems.
    # Minimal synthetic workflow fakes may omit the manifest event inventory.
    if "events" in manifest:
        source_events = manifest["events"]
        if not isinstance(source_events, list):
            raise ValueError("manifest events must be an array")
        manifest_events: dict[str, Mapping[str, Any]] = {}
        for value in source_events:
            original = _object(value, "manifest event")
            event_id = _identifier(original.get("eventId"), "manifest event ID")
            if event_id in manifest_events:
                raise ValueError("duplicate manifest event ID")
            if original.get("kind") != "script_marker":
                manifest_events[event_id] = original
        if set(manifest_events) != set(events):
            raise ValueError("manifest and view event inventory differs")
        for event_id, event in events.items():
            if event.get("v2Event") != manifest_events[event_id]:
                raise ValueError(f"manifest and view event differs: {event_id}")

    by_event: dict[str, Mapping[str, Any]] = {}
    for observed_value in observed:
        item = _object(observed_value, "reopened item")
        event_id = _identifier(item.get("eventId"), "observed event ID")
        if event_id in by_event:
            raise ValueError("duplicate observed event ID")
        by_event[event_id] = item
    if set(by_event) != set(events):
        raise ValueError("observed item inventory differs from delivery view")

    grouped: dict[str | None, list[dict[str, Any]]] = {}
    seen_native_ids: set[str] = set()
    for event_id, event in events.items():
        original = _object(event.get("v2Event"), "v2 event")
        if (
            original.get("eventId") != event_id
            or original.get("kind") == "script_marker"
        ):
            raise ValueError(f"invalid v2 event identity or marker: {event_id}")
        provenance = _object(original.get("provenance"), "v2 event provenance")
        block_id = provenance.get("blockId")
        if block_id is not None:
            _identifier(block_id, "script block ID")
        track_id = _identifier(event.get("trackId"), "event track ID")
        matched_track = tracks.get(track_id)
        if matched_track is None or matched_track["kind"] not in {"video", "audio"}:
            raise ValueError(f"missing or unsupported event track: {event_id}")
        if event.get("trackKind", matched_track["kind"]) != matched_track["kind"]:
            raise ValueError(f"event track kind differs from view: {event_id}")
        record = _object(event.get("recordRange"), "delivery record range")
        start = _frame(record.get("startFrame"), "view start frame")
        duration = _frame(record.get("durationFrames"), "view duration", positive=True)
        original_range = original.get("recordRange")
        if original_range is not None:
            source_range = _object(original_range, "v2 manifest record range")
            if (
                source_range.get("startFrame") != start
                or source_range.get("endFrame") != start + duration
            ):
                raise ValueError(f"v2 event record range differs from view: {event_id}")
        item = by_event[event_id]
        native_id = _identifier(item.get("resolveItemId"), "reopened TimelineItem UID")
        if native_id in seen_native_ids:
            raise ValueError("duplicate reopened TimelineItem UID")
        seen_native_ids.add(native_id)
        if (
            item.get("trackId") != track_id
            or item.get("trackKind") != matched_track["kind"]
            or type(item.get("trackIndex")) is not int
            or item["trackIndex"] != matched_track["index"]
            or type(item.get("startFrame")) is not int
            or item["startFrame"] != start
            or type(item.get("durationFrames")) is not int
            or item["durationFrames"] != duration
        ):
            raise ValueError(f"reopened item differs from view: {event_id}")
        grouped.setdefault(block_id, []).append(
            {
                "eventId": event_id,
                "resolveItemId": native_id,
                "trackId": track_id,
                "trackKind": matched_track["kind"],
                "trackIndex": matched_track["index"],
                "startFrame": start,
                "durationFrames": duration,
            }
        )

    rows: list[dict[str, Any]] = []
    for block_id in sorted(grouped, key=lambda row_id: (row_id is None, row_id or "")):
        items = sorted(
            grouped[block_id],
            key=lambda item: (
                item["startFrame"],
                item["trackKind"],
                item["trackIndex"],
                item["eventId"],
            ),
        )
        start_frame = min(item["startFrame"] for item in items)
        end_frame = max(item["startFrame"] + item["durationFrames"] for item in items)
        rows.append(
            {
                "rowId": block_id,
                "timelineId": timeline_id,
                "startFrame": start_frame,
                "lengthFrames": end_frame - start_frame,
                "items": items,
            }
        )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "version": 1,
        "buildId": build_id,
        "manifestId": manifest_id,
        "documentId": document_id,
        "documentRevision": revision,
        "projectName": project_name,
        "resolveProjectId": resolve_project_id,
        "timelineName": timeline_name,
        "timelineId": timeline_id,
        "rows": rows,
    }


def compare_reopened_row_map(
    manifest: Mapping[str, Any],
    view: Mapping[str, Any],
    observed: Sequence[Mapping[str, Any]],
    *,
    project_name: str,
    resolve_project_id: str,
    timeline_name: str,
    timeline_id: str,
    saved_map: Mapping[str, Any] | None,
) -> str:
    """Compare fresh, independently stamped readback to the saved v1 map.

    With no map, the *current* item UIDs only support unique item inventory;
    there is no prior UID baseline and no claim of UID continuity.
    """
    current = make_row_timeline_map(
        manifest,
        view,
        observed,
        project_name=project_name,
        resolve_project_id=resolve_project_id,
        timeline_name=timeline_name,
        timeline_id=timeline_id,
    )
    if saved_map is None:
        return "structural-only"
    if current != saved_map:
        raise ValueError(
            "saved row map differs from current target, row, item UID or geometry"
        )
    return "saved-uid-match"
