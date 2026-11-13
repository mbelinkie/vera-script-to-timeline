"""Pure, read-only script side of VERA's three-way regeneration comparison.

Inputs are *verified* v2 build artifacts and successful compiler output. This
module does not compile, read Resolve, or authorize an outbound update. The
offline adapter is responsible for attestation and for checking the saved map
against the delivery view before calling this function.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from .row_timeline_map import SCHEMA_VERSION_V2

MAX_FRAME = 2**53 - 1  # The v2 compiler uses JavaScript safe integers.

# No native-update preservation route is qualified for #102. In particular,
# a readable edit is not evidence that #104 can preserve it.
COMPATIBLE_RESOLVE_FIELDS: frozenset[str] = frozenset()
KNOWN_OBSERVATION_STATUSES = frozenset(
    {"unchanged", "moved", "trimmed", "removed", "added", "cannot tell"}
)
ROW_STATES = frozenset(
    {
        "unchanged",
        "script_changed",
        "resolve_changed",
        "both_compatible",
        "both_conflict",
    }
)


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
            if item["kind"] == "music":
                music = _object(item.get("music"), "compiled music span")
                if "requestedEndFrame" in music:
                    local_event["music"] = {
                        **music,
                        "requestedEndFrame": _frame(
                            music["requestedEndFrame"], "music requested end frame"
                        )
                        - origin,
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


def _statuses(item: Mapping[str, Any]) -> tuple[str, ...]:
    statuses = _array(item.get("status"), "observed status")
    if (
        not statuses
        or any(
            not isinstance(status, str) or status not in KNOWN_OBSERVATION_STATUSES
            for status in statuses
        )
        or len(set(statuses)) != len(statuses)
        or ("unchanged" in statuses and len(statuses) != 1)
        or ("added" in statuses and len(statuses) != 1)
        or ("removed" in statuses and len(statuses) != 1)
    ):
        raise ValueError("invalid #101 item status")
    changes = item.get("changes", {})
    if not isinstance(changes, Mapping) or any(
        not isinstance(key, str)
        or not key
        or not isinstance(value, Mapping)
        or set(value) != {"before", "after"}
        for key, value in changes.items()
    ):
        raise ValueError("invalid #101 item changes")
    if "cannotRead" in item:
        unknown = _array(item["cannotRead"], "observed cannotRead")
        if any(not isinstance(field, str) or not field for field in unknown):
            raise ValueError("invalid #101 cannotRead field")
    return tuple(statuses)


def classify_row(
    script_changed: bool,
    observed_items: Sequence[Mapping[str, Any]],
    *,
    compatible_fields: frozenset[str] = COMPATIBLE_RESOLVE_FIELDS,
    script_fields: frozenset[str] | None = None,
) -> tuple[str, str]:
    """Classify the five product states, never assuming native preservation.

    A synthetic caller can inject qualified fields to exercise the positive
    branch. Production always uses the empty envelope. Future callers must
    additionally prove the script's changed fields are disjoint; missing
    script-field evidence can never authorize compatibility.
    """
    if type(script_changed) is not bool:
        raise ValueError("script_changed must be a boolean")
    changed, uncertain = False, False
    touched: set[str] = set()
    for raw in observed_items:
        item = _object(raw, "observed item")
        statuses = _statuses(item)
        unknown = bool(item.get("cannotRead")) or "cannot tell" in statuses
        uncertain |= unknown
        changed |= statuses != ("unchanged",) or bool(item.get("changes")) or unknown
        touched.update(item.get("changes", {}))
        if set(statuses) & {"added", "removed", "moved", "trimmed"}:
            touched.add("clip_identity_or_geometry")
    if not script_changed and not changed:
        return "unchanged", "The compiled row and readable Resolve clips are unchanged."
    if script_changed and not changed:
        return (
            "script_changed",
            "The script changed; no Resolve clip edit was reported.",
        )
    if changed and not script_changed:
        return "resolve_changed", (
            "Resolve clips changed or could not be fully read; the script is unchanged."
        )
    if uncertain:
        return (
            "both_conflict",
            "Both sides changed and some Resolve clip facts are unreadable.",
        )
    if (
        touched
        and touched <= compatible_fields
        and script_fields is not None
        and touched.isdisjoint(script_fields)
    ):
        return "both_compatible", "Both sides changed in qualified, separate fields."
    return "both_conflict", (
        "Both sides changed; Resolve preservation or field separation is not qualified."
    )


def shifted_rows(
    old_starts: Mapping[str, int], proposed_starts: Mapping[str, int]
) -> dict[str, int]:
    """Signed frame deltas for surviving rows; never accept unsafe geometry."""
    for name, starts in (("baseline", old_starts), ("current", proposed_starts)):
        for row_id, start in starts.items():
            _id(row_id, f"{name} row ID")
            _frame(start, f"{name} row start frame")
    return {
        row_id: proposed_starts[row_id] - old_starts[row_id]
        for row_id in sorted(old_starts.keys() & proposed_starts.keys())
        if proposed_starts[row_id] != old_starts[row_id]
    }


def _observed_rows(
    report: Mapping[str, Any], saved_map: Mapping[str, Any]
) -> dict[str | None, list[Mapping[str, Any]]]:
    """Validate one complete #101 observation against each saved native UID."""
    for field in (
        "buildId",
        "documentId",
        "documentRevision",
        "timelineId",
        "timelineName",
    ):
        if (
            type(report.get(field)) is not type(saved_map.get(field))
            or report.get(field) != saved_map[field]
        ):
            raise ValueError(f"observation {field} differs from verified baseline")
    for field in ("cannotRead", "notCompared"):
        if field in report and any(
            not isinstance(value, str) for value in _array(report[field], field)
        ):
            raise ValueError(f"invalid observation {field}")
    expected: dict[str | None, dict[str, str]] = {}
    for row in saved_map["rows"]:
        expected[row["rowId"]] = {
            item["resolveItemId"]: item["eventId"] for item in row["items"]
        }
    observed: dict[str | None, list[Mapping[str, Any]]] = {}
    seen_uids: set[str] = set()
    seen_baseline: set[str] = set()
    for raw in _array(report.get("rows"), "observed rows"):
        row = _object(raw, "observed row")
        row_id = row.get("rowId")
        if row_id is not None:
            _id(row_id, "observed row ID")
        if row_id in observed or (row_id is not None and row_id not in expected):
            raise ValueError("duplicate or unknown observed row ID")
        items = _array(row.get("items"), "observed row items")
        observed[row_id] = []
        for raw_item in items:
            item = _object(raw_item, "observed item")
            uid = _id(item.get("resolveItemId"), "observed Resolve item UID")
            if uid in seen_uids:
                raise ValueError("duplicate observed Resolve item UID")
            seen_uids.add(uid)
            statuses = _statuses(item)
            expected_event = expected.get(row_id, {}).get(uid)
            if statuses == ("added",):
                if expected_event is not None or "eventId" in item:
                    raise ValueError("editor addition claims a managed event")
                if "trackKind" in item and item["trackKind"] not in {
                    "video",
                    "audio",
                    "subtitle",
                }:
                    raise ValueError("invalid editor clip track kind")
                if "trackIndex" in item and item["trackIndex"] is not None:
                    _frame(item["trackIndex"], "editor clip track index", positive=True)
                if "startFrame" in item and item["startFrame"] is not None:
                    _frame(item["startFrame"], "editor clip start frame")
                if "durationFrames" in item and item["durationFrames"] is not None:
                    _frame(
                        item["durationFrames"], "editor clip duration", positive=True
                    )
            else:
                if expected_event is None or item.get("eventId") != expected_event:
                    raise ValueError("observed managed event/row differs from baseline")
                seen_baseline.add(uid)
            observed[row_id].append(item)
    missing = set().union(*(set(items) for items in expected.values())) - seen_baseline
    if missing:
        raise ValueError("observation omitted a baseline managed clip")
    return observed


def _clip_interval(item: Mapping[str, Any]) -> tuple[int, int] | None:
    """A current editor clip may be unreadable; do not fabricate its extent."""
    start, duration = item.get("startFrame"), item.get("durationFrames")
    if start is None or duration is None:
        return None
    start = _frame(start, "editor clip start frame")
    duration = _frame(duration, "editor clip duration", positive=True)
    if start + duration > MAX_FRAME:
        raise ValueError("editor clip interval exceeds safe frame range")
    return start, start + duration


def _dependency_facts(
    manifest: Mapping[str, Any], document: Mapping[str, Any]
) -> dict[tuple[str, str], dict[str, Any]]:
    """Normalize paired transitions and complete A5 spans as atomic facts.

    A dependency is anchored to its first row, not to the absolute timeline.
    Pure upstream displacement cannot rewrite its semantic identity.
    """
    order = _document_rows(document)
    positions = {row: index for index, row in enumerate(order)}
    _, envelopes, _ = _manifest(manifest, document)
    facts: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in _array(manifest.get("transitions", []), "compiled transitions"):
        transition = _object(raw, "compiled transition")
        transition_id = _id(transition.get("id"), "transition ID")
        left = _id(transition.get("fromRowId"), "transition from-row ID")
        right = _id(transition.get("toRowId"), "transition to-row ID")
        if left not in positions or right not in positions or left == right:
            raise ValueError("transition references missing or identical script rows")
        if left not in envelopes:
            raise ValueError("transition has no outgoing row geometry")
        origin = envelopes[left][0]
        normalized = dict(transition)
        for field in ("boundaryFrame", "startFrame", "endFrame"):
            normalized[field] = (
                _frame(transition.get(field), f"transition {field}") - origin
            )
        if normalized["endFrame"] <= normalized["startFrame"]:
            raise ValueError("invalid transition interval")
        adjacent = positions[right] == positions[left] + 1
        normalized["adjacentInScript"] = adjacent
        key = ("transition", transition_id)
        if key in facts:
            raise ValueError("duplicate transition ID")
        facts[key] = {
            "members": (left, right),
            "signature": json.dumps(normalized, sort_keys=True, separators=(",", ":")),
            "adjacent": adjacent,
        }

    for raw in _array(manifest.get("events"), "compiled events"):
        event = _object(raw, "compiled event")
        if event.get("kind") != "music":
            continue
        music = _object(event.get("music"), "compiled music span")
        span_id = _id(music.get("spanId"), "music span ID")
        first = _id(music.get("startRowId"), "music start row ID")
        last = _id(music.get("endRowId"), "music end row ID")
        if (
            first not in positions
            or last not in positions
            or positions[first] > positions[last]
            or _object(event.get("provenance"), "music provenance").get("blockId")
            != first
            or first not in envelopes
        ):
            raise ValueError("music span has contradictory row identity or ordering")
        members = order[positions[first] : positions[last] + 1]
        origin = envelopes[first][0]
        normalized = dict(event)
        record = _object(event["recordRange"], "music record range")
        normalized["recordRange"] = {
            **record,
            "startFrame": _frame(record["startFrame"], "music start frame") - origin,
            "endFrame": _frame(record["endFrame"], "music end frame") - origin,
        }
        normalized["music"] = dict(music)
        if "requestedEndFrame" in music:
            normalized["music"]["requestedEndFrame"] = (
                _frame(music["requestedEndFrame"], "music requested end frame") - origin
            )
        key = ("music", span_id)
        if key in facts:
            raise ValueError("duplicate music span ID")
        facts[key] = {
            "members": members,
            "signature": json.dumps(normalized, sort_keys=True, separators=(",", ":")),
            "adjacent": True,
        }
    return facts


def _dependency_impacts(
    baseline_manifest: Mapping[str, Any],
    baseline_document: Mapping[str, Any],
    current_manifest: Mapping[str, Any],
    current_document: Mapping[str, Any],
    directly_changed: set[str],
    shifted: set[str],
    resolve_changed: set[str],
) -> dict[str, list[dict[str, Any]]]:
    before = _dependency_facts(baseline_manifest, baseline_document)
    after = _dependency_facts(current_manifest, current_document)
    impacts: dict[str, list[dict[str, Any]]] = {}
    for kind, identity in sorted(before.keys() | after.keys()):
        old, new = before.get((kind, identity)), after.get((kind, identity))
        members = tuple(
            sorted(
                set((old or {}).get("members", ()))
                | set((new or {}).get("members", ()))
            )
        )
        if (
            old == new
            and not directly_changed.intersection(members)
            and not (
                shifted.intersection(members) and resolve_changed.intersection(members)
            )
        ):
            continue
        reason = (
            f"{kind.capitalize()} {identity} affects multiple script rows; "
            "the coupled edit must be reviewed together."
        )
        if new is not None and not new["adjacent"]:
            reason = f"Transition {identity} is no longer between adjacent script rows."
        impact = {
            "kind": kind,
            "id": identity,
            "members": list(members),
            "reason": reason,
        }
        for row_id in members:
            impacts.setdefault(row_id, []).append(impact)
    return impacts


def _row_clip_ranges(manifest: Mapping[str, Any], row_id: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for raw in manifest["events"]:
        event = _object(raw, "compiled event")
        if event["kind"] in {"script_marker", "music"}:
            continue  # Music is coupled explicitly, not a fake row-wide clip.
        if event["provenance"]["blockId"] != row_id:
            continue
        interval = _object(event["recordRange"], "compiled record range")
        ranges.append((interval["startFrame"], interval["endFrame"]))
    return ranges


def _dependency_clip_ranges(
    manifest: Mapping[str, Any], impact: Mapping[str, Any]
) -> list[tuple[int, int]]:
    """Actual span/boundary intervals, not a fictional filled row envelope."""
    kind, identity = impact["kind"], impact["id"]
    if kind == "transition":
        return [
            (item["startFrame"], item["endFrame"])
            for item in manifest.get("transitions", [])
            if item["id"] == identity
        ]
    return [
        (item["recordRange"]["startFrame"], item["recordRange"]["endFrame"])
        for item in manifest["events"]
        if item["kind"] == "music" and item["music"]["spanId"] == identity
    ]


def compare_three_way_rows(
    baseline_manifest: Mapping[str, Any],
    baseline_map: Mapping[str, Any],
    baseline_document: Mapping[str, Any],
    current_manifest: Mapping[str, Any],
    current_document: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    """Read-only classification with ripple, unknowns and cross-row hazards.

    Reports are review evidence, never an authorized outbound selection. The
    #101 observation identifies exactly the original target; a future executor
    must independently re-observe under ownership before writing.
    """
    script = compare_script_rows(
        baseline_manifest,
        baseline_map,
        baseline_document,
        current_manifest,
        current_document,
    )
    observed = _observed_rows(_object(observation, "#101 observation"), baseline_map)
    old_starts = {
        row["rowId"]: row["baselineStartFrame"]
        for row in script["rows"]
        if row["baselineStartFrame"] is not None
    }
    new_starts = {
        row["rowId"]: row["currentStartFrame"]
        for row in script["rows"]
        if row["currentStartFrame"] is not None
    }
    shifts = shifted_rows(old_starts, new_starts)
    direct = {
        row["rowId"] for row in script["rows"] if row["scriptChange"] != "unchanged"
    }
    resolved_edits = {
        row_id: classify_row(False, items)[0] == "resolve_changed"
        for row_id, items in observed.items()
        if row_id is not None
    }
    dependencies = _dependency_impacts(
        baseline_manifest,
        baseline_document,
        current_manifest,
        current_document,
        direct,
        set(shifts),
        {row_id for row_id, changed in resolved_edits.items() if changed},
    )
    all_additions = [
        {"rowId": row_id, **dict(item)}
        for row_id, items in observed.items()
        for item in items
        if _statuses(item) == ("added",)
    ]
    all_additions.sort(key=lambda item: (item["resolveItemId"], item["rowId"] or ""))
    unassigned = [item for item in all_additions if item["rowId"] is None]
    unknown_additions = [item for item in unassigned if _clip_interval(item) is None]
    global_managed = [
        item for item in observed.get(None, []) if _statuses(item) != ("added",)
    ]
    unowned_events = script["unownedCompiledEvents"]
    global_script_changed = unowned_events["baseline"] != unowned_events["current"]
    # An editor addition cannot safely be separated from a new unowned script
    # event either: neither side supplies a row identity to prove independence.
    global_observed = [
        *global_managed,
        *(unassigned if global_script_changed else []),
    ]
    global_state, global_reason = classify_row(global_script_changed, global_observed)
    global_resolve_edited = global_state in {"resolve_changed", "both_conflict"}
    global_conflict = global_state == "both_conflict"
    results: list[dict[str, Any]] = []
    for original in script["rows"]:
        row_id = original["rowId"]
        shift = shifts.get(row_id, 0)
        impacts = dependencies.get(row_id, [])
        script_affected = bool(
            original["scriptChange"] != "unchanged"
            or shift
            or impacts
            or global_conflict
        )
        clips = _row_clip_ranges(current_manifest, row_id)
        # Both positions matter: a moved row can collide with an editor clip
        # left behind at the original location, even if its new range is clear.
        clips.extend(_row_clip_ranges(baseline_manifest, row_id))
        for impact in impacts:
            # An editor clip may intersect only a transition boundary or A5
            # span even when it lies between this row's actual clips.
            clips.extend(_dependency_clip_ranges(baseline_manifest, impact))
            clips.extend(_dependency_clip_ranges(current_manifest, impact))
        overlaps = sorted(
            item["resolveItemId"]
            for item in unassigned
            if (interval := _clip_interval(item)) is not None
            and any(start < interval[1] and interval[0] < end for start, end in clips)
        )
        local = observed.get(row_id, [])
        state, reason = classify_row(script_affected, local)
        linked_resolve = any(
            resolved_edits.get(member, False)
            for impact in impacts
            for member in impact["members"]
        )
        hazards: list[str] = []
        if shift:
            direction = "later" if shift > 0 else "earlier"
            reason += (
                f" This row moves {abs(shift)} frames {direction} on the timeline."
            )
        if impacts:
            hazards.extend(impact["reason"] for impact in impacts)
        if overlaps and script_affected:
            hazards.append(
                "An unassigned editor clip overlaps row clips or a linked "
                "transition/music span."
            )
        if unknown_additions and script_affected:
            hazards.append(
                "An unassigned editor clip has unreadable timing; "
                "overlap cannot be excluded."
            )
        if linked_resolve and script_affected:
            hazards.append(
                "A Resolve edit affects another row in the same atomic dependency."
            )
        if global_resolve_edited and script_affected:
            hazards.append(
                "A managed Resolve edit without row attribution cannot be safely "
                "separated from the proposed script update."
            )
        if script_affected and (
            overlaps or unknown_additions or linked_resolve or global_resolve_edited
        ):
            state = "both_conflict"
            reason = (
                "The script update overlaps unassigned, globally owned or "
                "coupled Resolve work; review is required. " + reason
            )
        results.append(
            {
                **original,
                "state": state,
                "reason": reason,
                "shiftFrames": shift,
                "dependencyImpacts": impacts,
                "editorOverlaps": overlaps,
                "hazards": sorted(set(hazards)),
                "blocked": state == "both_conflict",
            }
        )
    result: dict[str, Any] = {
        **{key: value for key, value in script.items() if key != "rows"},
        "rows": results,
        "observationCoverage": {
            "cannotRead": list(observation.get("cannotRead", [])),
            "notCompared": list(observation.get("notCompared", [])),
        },
        "unassignedEditorClips": unassigned,
        "unassignedManagedClips": [
            dict(item)
            for item in observed.get(None, [])
            if _statuses(item) != ("added",)
        ],
        "otherEditorClips": [
            item for item in all_additions if item["rowId"] is not None
        ],
    }
    if global_managed or unowned_events["baseline"] or unowned_events["current"]:
        # No invented row identity: globally owned native clips must be visible
        # as independent comparison evidence, not silently treated as safe.
        result["unownedManagedComparison"] = {
            "state": global_state,
            "reason": global_reason,
            "scriptChanged": global_script_changed,
            "blocked": global_conflict,
            "observedManagedClips": [dict(item) for item in global_managed],
            "unassignedEditorClips": [dict(item) for item in unassigned],
            "baselineEvents": unowned_events["baseline"],
            "currentEvents": unowned_events["current"],
        }
    return result
