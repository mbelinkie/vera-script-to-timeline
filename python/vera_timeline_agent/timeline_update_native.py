"""Resolve-side steps of the changed-rows update: read, archive, swap, reopen.

Every write here is one the #327 experiment measured on Studio 21.1.1 build
10. Nothing in this module retries a native call.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .observe_timeline_cli import _vera_stamps
from .workflow_v2 import _read_track_items

MEASURED_VERSION = [21, 1, 1, 10]
# What the snapshot can compare, and what no scripting call exposes (#327).
READABLE = (
    "clip position, length, track and source",
    "clip markers",
    "Inspector settings such as volume, zoom and position",
    "number of Fusion compositions and colour nodes on each clip",
    "transitions and their spans",
    "clips you added yourself",
)
UNREADABLE = (
    "the content of colour grades (only the node count is compared)",
    "the settings inside Fusion compositions and effects",
)
_REPLACED_FIELDS = frozenset(
    {"name", "mediaId", "sourceStart", "sourceEnd", "markers", "takes"}
)


class NativeUpdateError(RuntimeError):
    """A Resolve read or write did not do what was asked."""


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise NativeUpdateError(message)


def _try(target: Any, method: str, *arguments: Any) -> Any:
    """Read an optional fact; an unavailable one is recorded as ``None``."""
    try:
        call = getattr(target, method, None)
        return call(*arguments) if callable(call) else None
    except Exception:
        return None


def _plain(value: Any) -> Any:
    """Reduce SDK values to JSON-comparable ones without inventing detail."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return repr(type(value))


def live_items(timeline: Any) -> dict[str, tuple[str, int, Any]]:
    """Every item on the timeline by its Resolve ID, with its track."""
    found: dict[str, tuple[str, int, Any]] = {}
    for kind in ("video", "audio", "subtitle"):
        count = timeline.GetTrackCount(kind)
        _require(type(count) is int and count >= 0, f"{kind} tracks are unreadable")
        for index in range(1, count + 1):
            for item in _read_track_items(timeline, kind, index):
                uid = item.GetUniqueId()
                _require(
                    isinstance(uid, str) and uid and uid not in found,
                    "a clip has no usable Resolve ID",
                )
                found[uid] = (kind, index, item)
    return found


def snapshot(timeline: Any) -> dict[str, Any]:
    """Everything VERA can read about a timeline, for before/after comparison."""
    items = []
    for uid, (kind, index, item) in live_items(timeline).items():
        media = _try(item, "GetMediaPoolItem")
        graph = _try(item, "GetNodeGraph")
        items.append(
            {
                "id": uid,
                "kind": kind,
                "track": index,
                "type": _try(item, "GetType"),
                "name": _try(item, "GetName"),
                "start": item.GetStart(False),
                "duration": item.GetDuration(False),
                "mediaId": _try(media, "GetMediaId") if media is not None else None,
                "sourceStart": _try(item, "GetSourceStartFrame"),
                "sourceEnd": _try(item, "GetSourceEndFrame"),
                "markers": _plain(_try(item, "GetMarkers")),
                "properties": _plain(_try(item, "GetProperties")),
                "fusionComps": _try(item, "GetFusionCompCount"),
                "colorNodes": (
                    _try(graph, "GetNumNodes") if graph is not None else None
                ),
                "takes": _try(item, "GetTakesCount"),
                "clipColor": _try(item, "GetClipColor"),
                "enabled": _try(item, "GetClipEnabled"),
            }
        )
    return {
        "timelineId": timeline.GetUniqueId(),
        "bounds": [timeline.GetStartFrame(), timeline.GetEndFrame()],
        "markers": _plain(_try(timeline, "GetMarkers")),
        "items": sorted(
            items, key=lambda row: (row["kind"], row["track"], row["start"], row["id"])
        ),
    }


def content(value: Mapping[str, Any]) -> dict[str, Any]:
    """A snapshot without Resolve IDs, which a duplicate is given afresh."""
    return {
        "bounds": value["bounds"],
        "markers": value["markers"],
        "items": [
            {key: item for key, item in row.items() if key != "id"}
            for row in value["items"]
        ],
    }


def _same_properties(first: Any, second: Any) -> bool:
    """Compare Inspector settings as Resolve reports them.

    Measured on Studio 21.1.1 build 10: a freshly duplicated timeline omits
    audio settings that are at their off or zero default (dialogue leveler,
    voice isolation) until the project is reopened. A missing setting is
    therefore equal only to an off or zero one, never to a set value.
    """
    if not isinstance(first, Mapping) or not isinstance(second, Mapping):
        return bool(first == second)
    return all(
        first[key] == second[key]
        if key in first and key in second
        else not first.get(key) and not second.get(key)
        for key in first.keys() | second.keys()
    )


def same_content(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    """Whether two timelines hold the same clips, ignoring Resolve IDs."""
    one, two = content(first), content(second)
    return (
        one["bounds"] == two["bounds"]
        and one["markers"] == two["markers"]
        and len(one["items"]) == len(two["items"])
        and all(
            _same_properties(left["properties"], right["properties"])
            and {k: v for k, v in left.items() if k != "properties"}
            == {k: v for k, v in right.items() if k != "properties"}
            for left, right in zip(one["items"], two["items"], strict=True)
        )
    )


def fingerprint(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hand_markers(markers: Any) -> Any:
    """A clip's markers without VERA's own stamp, which an update replaces."""
    if not isinstance(markers, Mapping):
        return markers
    kept = {}
    for frame, marker in markers.items():
        data = marker.get("customData") if isinstance(marker, Mapping) else None
        try:
            parsed = json.loads(data) if isinstance(data, str) and data else None
        except ValueError:
            parsed = None
        if not (isinstance(parsed, dict) and "v2EventId" in parsed):
            kept[frame] = marker
    return kept


def unread_facts(value: Mapping[str, Any]) -> list[str]:
    """Readable-in-principle facts Resolve did not return for some clip."""
    names = {
        "markers": "clip markers",
        "properties": "Inspector settings",
        "fusionComps": "the number of Fusion compositions",
        "colorNodes": "the number of colour nodes",
    }
    missing = {
        names[key]
        for row in value["items"]
        if row["type"] != "transition"
        for key in names
        if row[key] is None and not (key == "colorNodes" and row["kind"] != "video")
    }
    return sorted(missing)


def unexpected_changes(
    before: Mapping[str, Any], after: Mapping[str, Any], replaced: Mapping[str, bool]
) -> list[str]:
    """Differences the update did not intend. Empty means hand work was kept.

    ``replaced`` maps each clip the update touched to whether its picture was
    swapped (``True``) or only its VERA marker replaced (``False``).
    """
    problems: list[str] = []
    if before["bounds"] != after["bounds"]:
        problems.append("timeline length changed")
    if before["markers"] != after["markers"]:
        problems.append("timeline markers changed")
    old = {row["id"]: row for row in before["items"]}
    new = {row["id"]: row for row in after["items"]}
    if old.keys() != new.keys():
        problems.append("clips or transitions were added or removed")
    for uid in sorted(old.keys() & new.keys()):
        skip: frozenset[str] = frozenset()
        if uid in replaced:
            skip = _REPLACED_FIELDS if replaced[uid] else frozenset({"markers"})
        changed = sorted(
            key
            for key in old[uid]
            if key not in skip
            and (
                not _same_properties(old[uid][key], new[uid].get(key))
                if key == "properties"
                else old[uid][key] != new[uid].get(key)
            )
        )
        if uid in replaced and _hand_markers(old[uid]["markers"]) != _hand_markers(
            new[uid].get("markers")
        ):
            changed.append("your markers")
        if changed:
            where = f"{old[uid]['kind']} {old[uid]['track']} at {old[uid]['start']}"
            problems.append(f"clip on {where} changed: {', '.join(changed)}")
    return problems


def timeline_by_uid(project: Any, uid: str) -> Any:
    count = project.GetTimelineCount()
    _require(type(count) is int and count > 0, "timeline list is unreadable")
    matches = [
        timeline
        for timeline in (project.GetTimelineByIndex(i) for i in range(1, count + 1))
        if timeline is not None and timeline.GetUniqueId() == uid
    ]
    _require(len(matches) == 1, "the timeline can no longer be found by its ID")
    return matches[0]


def timeline_names(project: Any) -> set[str]:
    count = project.GetTimelineCount()
    _require(type(count) is int and count > 0, "timeline list is unreadable")
    return {project.GetTimelineByIndex(i).GetName() for i in range(1, count + 1)}


def select(project: Any, timeline: Any) -> None:
    _require(project.SetCurrentTimeline(timeline), "could not select the timeline")
    current = project.GetCurrentTimeline()
    _require(
        current is not None and current.GetUniqueId() == timeline.GetUniqueId(),
        "Resolve switched to a different timeline",
    )


def duplicate_archive(project: Any, original: Any, name: str) -> Any:
    """Duplicate the finished timeline and hand the original back as current."""
    _require(name not in timeline_names(project), "archive name is already in use")
    select(project, original)
    archive = original.DuplicateTimeline(name)
    _require(
        archive is not None
        and archive.GetName() == name
        and archive.GetUniqueId() != original.GetUniqueId(),
        "Resolve did not create the archive copy",
    )
    select(project, original)
    return archive


def import_sources(
    project: Any, bin_name: str, paths: Mapping[str, Path]
) -> dict[str, Any]:
    """Import each replacement source once, into its own Media Pool bin."""
    pool = project.GetMediaPool()
    _require(pool is not None, "the Media Pool is unavailable")
    folder = pool.AddSubFolder(pool.GetRootFolder(), bin_name)
    _require(
        folder is not None and pool.SetCurrentFolder(folder),
        "could not create the Media Pool bin for the new pictures",
    )
    imported: dict[str, Any] = {}
    for source_id, path in paths.items():
        result = pool.ImportMedia([str(path)])
        _require(
            isinstance(result, (list, tuple)) and len(result) == 1,
            "Resolve did not import a replacement picture",
        )
        imported[source_id] = result[0]
    return imported


def swap_picture(item: Any, media: Any, start: int, duration: int) -> None:
    """Replace a clip's picture through the take selector, keeping the clip."""
    uid, position, length = (
        item.GetUniqueId(),
        item.GetStart(False),
        item.GetDuration(False),
    )
    _require(length == duration, "the clip is not the length the script expects")
    _require(item.GetTakesCount() == 0, "the clip already has takes")
    media_uid = media.GetUniqueId()
    _require(item.AddTake(media, start, start + duration), "could not add the take")
    matches = [
        index
        for index in range(1, item.GetTakesCount() + 1)
        if item.GetTakeByIndex(index)["mediaPoolItem"].GetUniqueId() == media_uid
    ]
    _require(len(matches) == 1, "the new take could not be identified")
    _require(item.SelectTakeByIndex(matches[0]), "could not select the new take")
    _require(item.FinalizeTake(), "could not finalize the new take")
    now = item.GetMediaPoolItem()
    _require(
        item.GetUniqueId() == uid
        and item.GetStart(False) == position
        and item.GetDuration(False) == length
        and now is not None
        and now.GetUniqueId() == media_uid
        and item.GetSourceStartFrame() == start,
        "the clip did not keep its place or take the new picture",
    )


def restamp(item: Any, event_id: str, stamp: str) -> None:
    """Replace the clip's VERA marker so the new baseline can identify it."""
    markers = item.GetMarkers()
    _require(isinstance(markers, Mapping), "clip markers are unreadable")
    for frame, marker in dict(markers).items():
        value = marker.get("customData") if isinstance(marker, Mapping) else None
        if value is None:
            value = item.GetMarkerCustomData(frame)
        try:
            data = json.loads(value) if isinstance(value, str) and value else None
        except ValueError:
            data = None
        if isinstance(data, dict) and "v2EventId" in data:
            _require(
                item.DeleteMarkerAtFrame(frame), "could not remove the old VERA marker"
            )
    _require(
        item.AddMarker(0, "Cyan", "VERA v2 event", event_id, 1, stamp),
        "could not add the new VERA marker",
    )
    _require(_vera_stamps(item) == [stamp], "the new VERA marker did not read back")


def save_close_reopen(manager: Any, project: Any, name: str, uid: str) -> Any:
    _require(manager.SaveProject(), "Resolve could not save the project")
    _require(manager.CloseProject(project), "Resolve could not close the project")
    reopened = manager.LoadProject(name)
    _require(
        reopened is not None and reopened.GetUniqueId() == uid,
        "Resolve did not reopen the same project",
    )
    return reopened
