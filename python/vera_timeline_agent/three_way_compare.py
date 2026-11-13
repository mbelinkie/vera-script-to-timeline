"""Pure, read-only script side of VERA's three-way regeneration comparison.

Inputs are *verified* v2 build artifacts and successful compiler output. This
module does not compile, read Resolve, or authorize an outbound update. The
offline adapter is responsible for attestation and for checking the saved map
against the delivery view before calling this function.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .row_timeline_map import SCHEMA_VERSION_V2

MAX_FRAME = 2**53 - 1  # The v2 compiler uses JavaScript safe integers.


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing or invalid {label}")
    return value


def _frame(value: Any, label: str, *, positive: bool = False) -> int:
    if type(value) is not int or not (int(positive) <= value <= MAX_FRAME):
        raise ValueError(f"invalid {label}")
    return value


def _document_rows(document: Mapping[str, Any]) -> tuple[str, ...]:
    if document.get("schemaVersion") != "script-document/v2":
        raise ValueError("expected a v2 script document")
    _id(document.get("id"), "script document ID")
    _id(document.get("projectId"), "script project ID")
    blocks = _array(
        _object(document.get("activeDraft"), "active draft").get("blocks"),
        "active draft blocks",
    )
    seen: set[str] = set()
    eligible: list[str] = []
    for value in blocks:
        block = _object(value, "draft block")
        block_id = _id(block.get("id"), "draft block ID")
        if block_id in seen:
            raise ValueError(f"duplicate draft block ID: {block_id}")
        seen.add(block_id)
        kind = _id(block.get("type"), "draft block type")
        if kind == "narration":
            if block.get("state") not in {"active", "excluded"}:
                raise ValueError(f"invalid narration state: {block_id}")
            if block["state"] == "active":
                eligible.append(block_id)
        elif kind == "visual_only":
            eligible.append(block_id)
        elif kind not in {"section", "direction", "note_draft"}:
            raise ValueError(f"invalid draft block type: {kind}")
    return tuple(eligible)


def _manifest(
    manifest: Mapping[str, Any], document: Mapping[str, Any]
) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[int, int]], tuple[str, ...]]:
    """Return row-local semantic events, absolute envelopes and unowned events.

    Only `recordRange` is translated. Every other compiled event field (source
    hashes, track, treatment, audio, marker, provenance) participates in the
    comparison. Unowned events are deliberately retained for phase-2 hazards.
    """
    if manifest.get("schemaVersion") != "timeline-manifest/v2":
        raise ValueError("expected a v2 timeline manifest")
    _id(manifest.get("id"), "manifest ID")
    _id(manifest.get("buildId"), "build ID")
    binding = _object(manifest.get("document"), "manifest document")
    if binding.get("documentId") != document["id"]:
        raise ValueError("manifest document ID differs from script")
    if binding.get("projectId") != document["projectId"]:
        raise ValueError("manifest project ID differs from script")
    _frame(binding.get("revision"), "manifest document revision")
    _id(binding.get("contentHash"), "manifest document content hash")

    tracks = _array(manifest.get("tracks"), "manifest tracks")
    track_ids: set[str] = set()
    for raw in tracks:
        track_id = _id(_object(raw, "manifest track").get("id"), "manifest track ID")
        if track_id in track_ids:
            raise ValueError(f"duplicate manifest track ID: {track_id}")
        track_ids.add(track_id)

    eligible = set(_document_rows(document))
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    unowned: list[str] = []
    seen_events: set[str] = set()
    for raw in _array(manifest.get("events"), "manifest events"):
        event = _object(raw, "compiled event")
        event_id = _id(event.get("eventId"), "compiled event ID")
        if event_id in seen_events:
            raise ValueError(f"duplicate compiled event ID: {event_id}")
        seen_events.add(event_id)
        _id(event.get("kind"), "compiled event kind")
        if _id(event.get("trackId"), "compiled event track") not in track_ids:
            raise ValueError(f"unknown track for compiled event: {event_id}")
        provenance = _object(event.get("provenance"), "compiled provenance")
        if provenance.get("documentId") != document["id"]:
            raise ValueError(f"compiled event document differs: {event_id}")
        row_id = provenance.get("blockId")
        if row_id is not None:
            _id(row_id, "compiled row ID")
            if row_id not in eligible:
                raise ValueError(
                    f"compiled event has unknown/ineligible row ID: {row_id}"
                )
        record = _object(event.get("recordRange"), "compiled record range")
        start = _frame(record.get("startFrame"), "compiled start frame")
        end = _frame(record.get("endFrame"), "compiled end frame")
        if end <= start:
            raise ValueError(f"compiled event has empty record range: {event_id}")
        if row_id is None:
            unowned.append(json.dumps(event, sort_keys=True, separators=(",", ":")))
        else:
            grouped.setdefault(row_id, []).append(event)

    normalized: dict[str, tuple[str, ...]] = {}
    envelopes: dict[str, tuple[int, int]] = {}
    for row_id, items in sorted(grouped.items()):
        origin = min(item["recordRange"]["startFrame"] for item in items)
        end = max(item["recordRange"]["endFrame"] for item in items)
        serialized: list[str] = []
        for item in items:
            record = item["recordRange"]
            local_event = dict(item)
            local_event["recordRange"] = {
                **record,
                "startFrame": record["startFrame"] - origin,
                "endFrame": record["endFrame"] - origin,
            }
            serialized.append(
                json.dumps(local_event, sort_keys=True, separators=(",", ":"))
            )
        normalized[row_id] = tuple(sorted(serialized))
        envelopes[row_id] = origin, end
    return normalized, envelopes, tuple(sorted(unowned))


def _validate_baseline_map(
    saved: Mapping[str, Any], manifest: Mapping[str, Any]
) -> None:
    """Check the shape/binding; the offline loader also verifies the full view."""
    if saved.get("schemaVersion") != SCHEMA_VERSION_V2 or saved.get("version") != 2:
        raise ValueError("a verified v2 row map is required")
    binding = _object(manifest["document"], "manifest document")
    for field, expected in (
        ("buildId", manifest["buildId"]),
        ("manifestId", manifest["id"]),
        ("documentId", binding["documentId"]),
        ("documentRevision", binding["revision"]),
        ("documentContentHash", binding["contentHash"]),
    ):
        if type(saved.get(field)) is not type(expected) or saved.get(field) != expected:
            raise ValueError(f"baseline row map {field} differs from manifest")
    _id(saved.get("timelineId"), "baseline timeline ID")
    _id(saved.get("resolveProjectId"), "baseline Resolve project UID")
    _id(saved.get("timelineName"), "baseline timeline name")

    source_events: dict[str, Mapping[str, Any]] = {}
    for value in manifest["events"]:
        event = _object(value, "manifest event")
        if event["kind"] != "script_marker":
            source_events[event["eventId"]] = event
    seen_ids: set[str] = set()
    seen_rows: set[str | None] = set()
    seen_uids: set[str] = set()
    for raw in _array(saved.get("rows"), "baseline rows"):
        row = _object(raw, "baseline row")
        row_id = row.get("rowId")
        if row_id is not None:
            _id(row_id, "baseline row ID")
        if row_id in seen_rows:
            raise ValueError("duplicate baseline row ID")
        seen_rows.add(row_id)
        if row.get("timelineId") != saved["timelineId"]:
            raise ValueError("baseline row has different timeline ID")
        start = _frame(row.get("startFrame"), "baseline row start")
        length = _frame(row.get("lengthFrames"), "baseline row length", positive=True)
        if start + length > MAX_FRAME:
            raise ValueError("baseline row envelope overflow")
        items = _array(row.get("items"), "baseline row items")
        if not items:
            raise ValueError("baseline row has no items")
        starts: list[int] = []
        ends: list[int] = []
        for raw_item in items:
            item = _object(raw_item, "baseline row item")
            event_id = _id(item.get("eventId"), "baseline event ID")
            native_id = _id(item.get("resolveItemId"), "Resolve item UID")
            if event_id in seen_ids or native_id in seen_uids:
                raise ValueError("duplicate baseline item identity")
            seen_ids.add(event_id)
            seen_uids.add(native_id)
            source_event = source_events.get(event_id)
            if source_event is None or source_event["provenance"]["blockId"] != row_id:
                raise ValueError(f"baseline item event/row differs: {event_id}")
            if item.get("trackId") != source_event["trackId"]:
                raise ValueError(f"baseline item track differs: {event_id}")
            position = _frame(item.get("startFrame"), "baseline item start")
            duration = _frame(
                item.get("durationFrames"), "baseline duration", positive=True
            )
            if position + duration > MAX_FRAME:
                raise ValueError("baseline item range overflow")
            if (position, position + duration) != (
                source_event["recordRange"]["startFrame"],
                source_event["recordRange"]["endFrame"],
            ):
                raise ValueError(f"baseline item record range differs: {event_id}")
            starts.append(position)
            ends.append(position + duration)
        if (start, start + length) != (min(starts), max(ends)):
            raise ValueError("baseline row envelope differs from its items")
    if seen_ids != set(source_events):
        raise ValueError("baseline row map event inventory differs from manifest")


def compare_script_rows(
    baseline_manifest: Mapping[str, Any],
    baseline_map: Mapping[str, Any],
    baseline_document: Mapping[str, Any],
    current_manifest: Mapping[str, Any],
    current_document: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify only script-side row deltas; Resolve changes come in phase 2.

    A row's content is compared on its *own* time axis. Reordering is detected
    by changes in relative order of surviving row IDs, not by inserted rows or
    global start shifts. Removed rows are appended in their original order.
    """
    baseline_document = _object(baseline_document, "baseline script")
    current_document = _object(current_document, "current script")
    if current_document.get("id") != baseline_document.get("id"):
        raise ValueError("current script belongs to a different document")
    if current_document.get("projectId") != baseline_document.get("projectId"):
        raise ValueError("current script belongs to a different project")
    old_order = _document_rows(baseline_document)
    new_order = _document_rows(current_document)
    old_events, old_envelopes, old_unowned = _manifest(
        baseline_manifest, baseline_document
    )
    new_events, new_envelopes, new_unowned = _manifest(
        current_manifest, current_document
    )
    _validate_baseline_map(baseline_map, baseline_manifest)

    old_set, new_set = set(old_order), set(new_order)
    survivors = old_set & new_set
    old_preceding = {
        row: frozenset(old_order[:index]) & survivors
        for index, row in enumerate(old_order)
    }
    new_preceding = {
        row: frozenset(new_order[:index]) & survivors
        for index, row in enumerate(new_order)
    }
    rows: list[dict[str, Any]] = []
    for row_id in (*new_order, *(row for row in old_order if row not in new_set)):
        added, removed = row_id not in old_set, row_id not in new_set
        content_changed = old_events.get(row_id, ()) != new_events.get(row_id, ())
        reordered = (
            not (added or removed) and old_preceding[row_id] != new_preceding[row_id]
        )
        if added:
            change, reason = "added", "Script row was added."
        elif removed:
            change, reason = "removed", "Script row was removed."
        elif content_changed:
            change = "changed"
            reason = "Compiled row contents changed."
        elif reordered:
            change, reason = "reordered", "Script row order changed."
        else:
            change, reason = (
                "unchanged",
                "Compiled row contents and relative order are unchanged.",
            )
        if reordered and content_changed:
            reason = "Compiled row contents and relative order changed."
        before = old_envelopes.get(row_id)
        after = new_envelopes.get(row_id)
        rows.append(
            {
                "rowId": row_id,
                "scriptChange": change,
                "contentChanged": content_changed,
                "reordered": reordered,
                "reason": reason,
                "baselineStartFrame": before[0] if before else None,
                "baselineEndFrame": before[1] if before else None,
                "currentStartFrame": after[0] if after else None,
                "currentEndFrame": after[1] if after else None,
            }
        )
    binding = _object(baseline_manifest["document"], "baseline binding")
    current_binding = _object(current_manifest["document"], "current binding")
    return {
        "baseline": {
            "buildId": baseline_manifest["buildId"],
            "documentId": binding["documentId"],
            "documentRevision": binding["revision"],
            "documentContentHash": binding["contentHash"],
            "timelineId": baseline_map["timelineId"],
        },
        "current": {
            "documentRevision": current_binding["revision"],
            "documentContentHash": current_binding["contentHash"],
        },
        "rows": rows,
        "unownedCompiledEvents": {"baseline": old_unowned, "current": new_unowned},
    }
