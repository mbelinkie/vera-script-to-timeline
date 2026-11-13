"""Report clip changes on the currently open Resolve timeline against a VERA build."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .build_jobs import NeedsAction
from .build_timeline_once import _external_resolve, exclusive_resolve_build
from .readback_timeline_cli import _load_readback_package, _read_saved_row_map
from .row_timeline_map import (
    SCHEMA_VERSION_V2,
    observe_item_details,
    validate_saved_row_map,
)
from .workflow_v2 import (
    _assert_readback_target,
    _current_readback_target,
    _read_track_items,
    _regular_absolute,
    _stamp,
)

_SOURCE_RANGE = ("sourceStartFrame", "sourceEndFrame")
_DETAILS = ("name", "mediaId", *_SOURCE_RANGE)
_GEOMETRY = ("trackKind", "trackIndex", "startFrame", "durationFrames")
_FIELDS = (*_GEOMETRY, *_DETAILS)


def _vera_stamps(item: Any) -> list[str]:
    markers = item.GetMarkers()
    if not isinstance(markers, Mapping):
        raise ValueError("clip marker inventory is unreadable")
    stamps = []
    for frame, marker in markers.items():
        if not isinstance(marker, Mapping):
            raise ValueError("clip marker inventory is unreadable")
        value = marker.get("customData")
        if "customData" not in marker:
            value = item.GetMarkerCustomData(frame)
        if isinstance(value, str) and value:
            try:
                data = json.loads(value)
            except ValueError:
                continue
            if isinstance(data, dict) and "v2EventId" in data:
                stamps.append(value)
    return stamps


def _read_items(
    timeline: Any,
    saved_items: Mapping[str, Mapping[str, Any]],
    stamps_by_event: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    current: dict[str, dict[str, Any]] = {}
    seen_uids: set[str] = set()
    for kind in ("video", "audio", "subtitle"):
        count = timeline.GetTrackCount(kind)
        if type(count) is not int or count < 0:
            raise ValueError(f"{kind} track inventory is unreadable")
        for index in range(1, count + 1):
            for item in _read_track_items(timeline, kind, index):
                uid = item.GetUniqueId()
                if not isinstance(uid, str) or not uid.strip() or uid in seen_uids:
                    raise ValueError(
                        f"ambiguous or unreadable clip ID on {kind} {index}"
                    )
                seen_uids.add(uid)
                if kind == "video" and item.GetType() == "transition":
                    if uid in saved_items:
                        raise ValueError(
                            "a baseline clip ID now identifies a transition"
                        )
                    continue
                before = saved_items.get(uid)
                stamps = _vera_stamps(item)
                if stamps and (
                    before is None or stamps != [stamps_by_event[before["eventId"]]]
                ):
                    raise ValueError(
                        f"ambiguous VERA clip identity on {kind} {index}: "
                        "a clip marker conflicts with the saved Resolve clip ID"
                    )
                start = item.GetStart(False)
                duration = item.GetDuration(False)
                current[uid] = {
                    "resolveItemId": uid,
                    "trackKind": kind,
                    "trackIndex": index,
                    "startFrame": start if type(start) is int and start >= 0 else None,
                    "durationFrames": (
                        duration if type(duration) is int and duration > 0 else None
                    ),
                    **observe_item_details(item),
                }
    return current


def _item_change(
    before: Mapping[str, Any], after: Mapping[str, Any] | None
) -> dict[str, Any]:
    result = {"eventId": before["eventId"], "resolveItemId": before["resolveItemId"]}
    if after is None:
        return {**result, "status": ["removed"], "before": dict(before)}

    unknown = [key for key in _FIELDS if before[key] is None or after[key] is None]
    changes = {
        key: {"before": before[key], "after": after[key]}
        for key in _FIELDS
        if key not in unknown and before[key] != after[key]
    }
    statuses = []
    if (
        "durationFrames" in changes
        and "mediaId" not in changes
        and not any(key in unknown for key in _SOURCE_RANGE)
        and after["durationFrames"] - before["durationFrames"]
        == (after["sourceEndFrame"] - after["sourceStartFrame"])
        - (before["sourceEndFrame"] - before["sourceStartFrame"])
    ):
        statuses.append("trimmed")
    if (
        "trackKind" in changes
        or "trackIndex" in changes
        or (
            "startFrame" in changes
            and "durationFrames" not in unknown
            and (
                "durationFrames" not in changes
                or (
                    "sourceStartFrame" not in unknown
                    and after["startFrame"] - before["startFrame"]
                    != after["sourceStartFrame"] - before["sourceStartFrame"]
                )
            )
        )
    ):
        statuses.append("moved")
    if unknown or (
        changes
        and (
            not statuses
            or ("durationFrames" in changes and "trimmed" not in statuses)
            or "mediaId" in changes
            or "name" in changes
            or (
                "trimmed" not in statuses
                and any(key in changes for key in _SOURCE_RANGE)
            )
        )
    ):
        statuses.append("cannot tell")
    result["status"] = statuses or ["unchanged"]
    if changes:
        result["changes"] = changes
    if unknown:
        result["cannotRead"] = unknown
    return result


def _row_for_addition(
    item: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    current: Mapping[str, Mapping[str, Any]],
    event_kinds: Mapping[str, str],
) -> str | None:
    start, duration = item["startFrame"], item["durationFrames"]
    if start is None or duration is None:
        return None
    end = start + duration
    overlaps: set[str | None] = set()
    contains: set[str | None] = set()
    for row in rows:
        for saved in row["items"]:
            # A spanning music bed belongs to its first row for build provenance.
            if event_kinds.get(saved.get("eventId", "")) == "music":
                continue
            clip = current.get(saved["resolveItemId"])
            if clip is None:
                continue
            clip_start, clip_duration = clip["startFrame"], clip["durationFrames"]
            if clip_start is None or clip_duration is None:
                return None
            clip_end = clip_start + clip_duration
            if clip_start < end and start < clip_end:
                overlaps.add(row["rowId"])
            if clip_start <= start and end <= clip_end:
                contains.add(row["rowId"])
    if len(overlaps) != 1:
        return None
    row_id = next(iter(overlaps))
    return row_id if isinstance(row_id, str) and row_id in contains else None


def observe_output(
    output: Path, *, resolve_factory: Callable[[], Any] | None = None
) -> dict[str, Any]:
    """Read the active timeline and compare its clips with the verified baseline."""
    root = _regular_absolute(output.absolute(), "build output", directory=True)
    saved = _read_saved_row_map(root)
    if saved is None:
        raise ValueError("this build output has no row-timeline-map.json baseline")
    if saved.get("version") == 1:
        raise ValueError(
            "this build has a version 1 row map. Observe needs a new baseline"
        )
    if saved.get("schemaVersion") != SCHEMA_VERSION_V2:
        raise ValueError("unrecognized Resolve baseline format")
    package = _load_readback_package(root)
    validate_saved_row_map(package.manifest, package.view, saved)
    if saved["timelineName"] != package.attestation["timelineName"]:
        raise ValueError("baseline timeline name differs from the verified build")
    saved_items = {
        item["resolveItemId"]: item for row in saved["rows"] for item in row["items"]
    }
    stamps = {event["id"]: _stamp(event) for event in package.view["events"]}
    with exclusive_resolve_build():
        manager, timeline, project_uid, timeline_uid = _current_readback_target(
            (resolve_factory or _external_resolve)(),
            project_name=saved["projectName"],
            timeline_name=saved["timelineName"],
            project_uid=saved["resolveProjectId"],
            timeline_uid=saved["timelineId"],
        )
        current = _read_items(timeline, saved_items, stamps)
        _assert_readback_target(manager, project_uid, timeline_uid)

    rows = [
        {
            "rowId": row["rowId"],
            "items": [
                _item_change(item, current.get(item["resolveItemId"]))
                for item in row["items"]
            ],
        }
        for row in saved["rows"]
    ]
    rows_by_id = {row["rowId"]: row["items"] for row in rows}
    event_kinds = {
        event["id"]: event["v2Event"]["kind"] for event in package.view["events"]
    }
    for uid, item in current.items():
        if uid in saved_items:
            continue
        added = {"status": ["added"], **item}
        unknown = [key for key in _FIELDS if item[key] is None]
        if unknown:
            added["cannotRead"] = unknown
        row_id = _row_for_addition(item, saved["rows"], current, event_kinds)
        if row_id is None:
            added["rowAttribution"] = "cannot tell from the current row boundaries"
            if None not in rows_by_id:
                unassigned: list[dict[str, Any]] = []
                rows.append({"rowId": None, "items": unassigned})
                rows_by_id[None] = unassigned
        rows_by_id[row_id].append(added)

    return {
        "buildId": saved["buildId"],
        "documentId": saved["documentId"],
        "documentRevision": saved["documentRevision"],
        "timelineId": timeline_uid,
        "timelineName": saved["timelineName"],
        "differenceCount": sum(
            bool(item.get("changes") or set(item["status"]) & {"added", "removed"})
            for row in rows
            for item in row["items"]
        ),
        "cannotRead": ["grades", "effects", "media availability and source bytes"],
        "notCompared": [
            "timeline markers",
            "track settings",
            "clip inspector settings",
        ],
        "rows": rows,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, required=True, help="checked build results"
    )
    args = parser.parse_args(argv)
    try:
        print(json.dumps(observe_output(args.output), indent=2))
    except (ValueError, OSError, NeedsAction) as error:
        print(f"Cannot observe: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(
            f"Cannot observe: Resolve readback unavailable ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
