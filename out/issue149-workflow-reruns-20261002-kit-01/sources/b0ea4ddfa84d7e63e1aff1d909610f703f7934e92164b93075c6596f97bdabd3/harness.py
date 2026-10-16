"""Bounded Issue 149 Workflow Integration probe.

Resolve injects an already-connected ``resolve`` object.  This module never
creates a connection and never falls back to an external scripting bridge.
The caller stages one hash-pinned configuration per action; ``run`` returns a
JSON-safe result and keeps partial captures in the action evidence directory.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "issue-149-workflow-reruns-v1"
PROJECT_NAME = "VERA Issue 149 Workflow Reruns 20261002-kit-01"
STARTUP_PROJECT_NAME = "Untitled Project"
OUTPUT_NAME = "issue149-workflow-reruns-20261002-kit-01"
MEDIA_DIR_NAME = "media"
ACTION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
PHASES = frozenset(
    {
        "context",
        "prepare",
        "build",
        "w1-subtitle-request",
        "w1-subtitle-poll",
        "w2-export",
        "w3-mapping-mute",
        "w3-mapping-restore",
        "w4-speed",
        "w5-context-read",
        "w6-before-swap",
        "w6-after-swap",
        "w6-relink-render",
        "w7-lock-setter",
        "w7-unlock",
        "render-poll",
    }
)
TRACK_KINDS = ("video", "audio", "subtitle")
TIMELINE_GETTERS = (
    "GetName",
    "GetUniqueId",
    "GetStartFrame",
    "GetEndFrame",
    "GetStartTimecode",
    "GetCurrentTimecode",
    "GetMarkInOut",
    "GetMarkers",
)
ITEM_GETTERS = (
    "GetName",
    "GetUniqueId",
    "GetStart",
    "GetEnd",
    "GetDuration",
    "GetLeftOffset",
    "GetRightOffset",
    "GetSourceStartFrame",
    "GetSourceEndFrame",
    "GetSourceStartTime",
    "GetSourceEndTime",
    "GetClipEnabled",
    "GetSpeed",
    "GetMarkers",
    "GetFlagList",
    "GetClipColor",
    "GetSourceAudioChannelMapping",
    "GetVoiceIsolationState",
    "GetTrackTypeAndIndex",
)


class HarnessError(RuntimeError):
    """A guarded refusal or a retained native operation failure."""


def _error(error: BaseException) -> dict[str, str]:
    return {"type": type(error).__name__, "message": str(error)}


def _json_value(value: Any, seen: set[int] | None = None) -> Any:
    """Keep JSON-native values intact and represent native proxies explicitly."""
    if value is None or type(value) in (str, bool, int, float):
        return value
    if seen is None:
        seen = set()
    identity = id(value)
    if identity in seen:
        return {"__native_type__": type(value).__name__, "__repr__": "<cycle>"}
    seen.add(identity)
    try:
        # Resolve may expose proxy objects with a non-class ``__class__``.
        # ABC ``Mapping`` checks inspect that attribute and can raise before
        # the proxy is represented as native evidence; exact JSON containers
        # avoid invoking the proxy's ABC machinery.
        if type(value) is dict:
            return {str(key): _json_value(item, seen) for key, item in value.items()}
        if type(value) in (list, tuple):
            return [_json_value(item, seen) for item in value]
        return {"__native_type__": type(value).__name__, "__repr__": repr(value)}
    finally:
        seen.discard(identity)


def _write_json(path: Path, value: Any, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if exclusive else "w"
    with path.open(mode, encoding="utf-8") as stream:
        json.dump(_json_value(value), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _status(value: Any, **extra: Any) -> dict[str, Any]:
    return {"status": "ok", "value": _json_value(value), **extra}


class Journal:
    """Exclusive action journal; requests are written before API dispatch."""

    def __init__(self, output: Path, action_id: str):
        self.action_id = action_id
        evidence_root = output / "evidence"
        evidence_root.mkdir(parents=True, exist_ok=True)
        self.directory = evidence_root / action_id
        self.directory.mkdir(exist_ok=False)
        self.path = self.directory / "journal.jsonl"
        self.path.touch(exist_ok=False)
        self.write("harness", "started", {"schemaVersion": SCHEMA_VERSION})

    def write(self, method: str, phase: str, value: Any) -> None:
        record = {
            "at": datetime.now(UTC).isoformat(),
            "actionId": self.action_id,
            "method": method,
            "phase": phase,
            "value": _json_value(value),
        }
        with self.path.open("a", encoding="utf-8") as stream:
            json.dump(record, stream, sort_keys=True, allow_nan=False)
            stream.write("\n")

    def api_request(self, method: str, args: tuple[Any, ...]) -> None:
        self.write(method, "request", {"args": _json_value(args)})


def _getter(
    journal: Journal, obj: Any, method: str, *args: Any
) -> tuple[Any, dict[str, Any]]:
    """Read a native getter while distinguishing missing, error, and None."""
    journal.api_request(method, args)
    try:
        function = getattr(obj, method)
    except Exception as error:
        value = {"status": "missing", "error": _error(error)}
        journal.write(method, "missing", value)
        return None, value
    try:
        raw = function(*args)
    except Exception as error:
        value = {"status": "error", "error": _error(error)}
        journal.write(method, "error", value)
        return None, value
    value = _status(raw)
    journal.write(method, "return", value)
    return raw, value


def _required(journal: Journal, obj: Any, method: str, *args: Any) -> Any:
    raw, value = _getter(journal, obj, method, *args)
    if value["status"] != "ok":
        raise HarnessError(f"{method} unavailable: {value}")
    return raw


def _dispatch(journal: Journal, obj: Any, method: str, *args: Any) -> Any:
    """Mutating/native dispatch with a pre-call journal record and no retry."""
    journal.api_request(method, args)
    try:
        function = getattr(obj, method)
    except Exception as error:
        journal.write(method, "missing", {"error": _error(error)})
        raise HarnessError(f"{method} is missing") from error
    try:
        returned = function(*args)
    except Exception as error:
        journal.write(method, "failure", _error(error))
        raise
    journal.write(method, "return", returned)
    return returned


def _constant(journal: Journal, obj: Any, name: str) -> Any:
    journal.write(name, "attribute-request", {})
    try:
        value = getattr(obj, name)
    except Exception as error:
        journal.write(name, "attribute-missing", _error(error))
        raise HarnessError(f"Resolve constant {name} is missing") from error
    journal.write(name, "attribute-return", value)
    return value


def _path(config: Mapping[str, Any], key: str) -> Path:
    value = config.get(key)
    if not isinstance(value, str):
        raise HarnessError(f"{key} must be an absolute path")
    result = Path(value)
    if not result.is_absolute() or result.is_symlink():
        raise HarnessError(f"{key} must be an absolute non-symlink path")
    return result


def _validate_config(config: Mapping[str, Any]) -> None:
    if not isinstance(config, Mapping):
        raise HarnessError("configuration must be an object")
    if config.get("schemaVersion") != SCHEMA_VERSION:
        raise HarnessError("configuration schema version differs")
    if config.get("externalScriptingSetting") != "None":
        raise HarnessError("External Scripting must be None; no fallback is allowed")
    if config.get("projectName") != PROJECT_NAME:
        raise HarnessError("the exact synthetic project name is required")
    action = config.get("action")
    if action not in PHASES:
        raise HarnessError("unknown or disarmed action")
    action_id = config.get("actionId")
    if not isinstance(action_id, str) or not ACTION_RE.fullmatch(action_id):
        raise HarnessError("actionId must be a unique safe filename component")
    phase = config.get("phase")
    if not isinstance(phase, str) or not phase:
        raise HarnessError("phase is required")
    probe = _path(config, "probePath")
    digest = config.get("probeSha256")
    if (
        not probe.is_file()
        or not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
    ):
        raise HarnessError("hash-pinned probePath is required")
    output = _path(config, "outputDir")
    if output.name != OUTPUT_NAME or output.parent.name != "out":
        raise HarnessError("only the named owned output directory is allowed")
    media = _path(config, "mediaDir")
    if media != output / MEDIA_DIR_NAME:
        raise HarnessError("mediaDir must be outputDir/media")
    if action != "context" and not isinstance(config.get("stateId"), str):
        raise HarnessError("every non-context phase must bind a stateId")
    if action == "prepare" and config.get("allowEmptyUntitled") is not True:
        raise HarnessError("prepare requires allowEmptyUntitled=true")
    owned = config.get("owned", {})
    if not isinstance(owned, Mapping):
        raise HarnessError("owned state must be an object")
    if action not in {"context", "prepare"}:
        if not isinstance(owned.get("projectUid"), str) or not owned["projectUid"]:
            raise HarnessError("owned project UID is required after prepare")


def _context_only(resolve: Any, journal: Journal) -> dict[str, Any]:
    """Read only Resolve version and current project name."""
    version = _getter(journal, resolve, "GetVersion")[1]
    manager = _required(journal, resolve, "GetProjectManager")
    current = _required(journal, manager, "GetCurrentProject")
    name = _status(None)
    if current is not None:
        name = _getter(journal, current, "GetName")[1]
    return {"version": version, "currentProjectName": name}


def _empty_startup_project(journal: Journal, manager: Any) -> Any:
    """Require Resolve's untouched startup project before preparation."""
    project = _required(journal, manager, "GetCurrentProject")
    if project is None or _required(journal, project, "GetName") != STARTUP_PROJECT_NAME:
        raise HarnessError(
            f"prepare requires the untouched {STARTUP_PROJECT_NAME!r} project"
        )
    timeline_count = _required(journal, project, "GetTimelineCount")
    if type(timeline_count) is not int or timeline_count != 0:
        raise HarnessError("startup project must contain no timelines")
    if _required(journal, project, "GetCurrentTimeline") is not None:
        raise HarnessError("startup project must have no current timeline")
    render_jobs = _required(journal, project, "GetRenderJobList")
    if type(render_jobs) not in (list, tuple, dict) or render_jobs:
        raise HarnessError("startup project must contain no render jobs")
    if _required(journal, project, "IsRenderingInProgress") is not False:
        raise HarnessError("startup project must not be rendering")
    media_pool = _required(journal, project, "GetMediaPool")
    root = _required(journal, media_pool, "GetRootFolder")
    clips = _required(journal, root, "GetClipList")
    folders = _required(journal, root, "GetSubFolderList")
    if type(clips) not in (list, tuple, dict) or clips:
        raise HarnessError("startup media pool must contain no clips")
    if type(folders) not in (list, tuple, dict) or folders:
        raise HarnessError("startup media pool must contain no subfolders")
    return project


def _current_project(resolve: Any, journal: Journal, config: Mapping[str, Any]) -> Any:
    manager = _required(journal, resolve, "GetProjectManager")
    project = _required(journal, manager, "GetCurrentProject")
    if project is None:
        raise HarnessError("the named synthetic project is not loaded")
    name = _required(journal, project, "GetName")
    if name != PROJECT_NAME:
        raise HarnessError("current project is not the named synthetic project")
    owned = config.get("owned", {})
    project_uid = _required(journal, project, "GetUniqueId")
    if isinstance(owned, Mapping) and owned.get("projectUid") not in {
        None,
        project_uid,
    }:
        raise HarnessError("current project UID differs from owned state")
    return project


def _current_timeline(project: Any, journal: Journal) -> Any:
    return _required(journal, project, "GetCurrentTimeline")


def _timeline_handles(project: Any, journal: Journal) -> list[Any]:
    count = _required(journal, project, "GetTimelineCount")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise HarnessError("timeline count is unreadable")
    return [
        _required(journal, project, "GetTimelineByIndex", index)
        for index in range(1, count + 1)
    ]


def _timeline_uid(journal: Journal, timeline: Any) -> Any:
    return _required(journal, timeline, "GetUniqueId")


def _owned_guard(
    project: Any, journal: Journal, config: Mapping[str, Any]
) -> dict[str, Any]:
    handles = _timeline_handles(project, journal)
    owned = config.get("owned", {})
    expected = (
        set(owned.get("timelineUids", ())) if isinstance(owned, Mapping) else set()
    )
    found = {
        uid
        for uid in (_timeline_uid(journal, row) for row in handles)
        if isinstance(uid, str)
    }
    if expected and found != expected:
        raise HarnessError("owned timeline inventory differs from the new project")
    return {str(_timeline_uid(journal, row)): row for row in handles}


def _item_rows(journal: Journal, timeline: Any, kind: str, index: int) -> list[Any]:
    raw = _required(journal, timeline, "GetItemListInTrack", kind, index)
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise HarnessError(f"{kind} track {index} item list is unreadable")
    return list(raw)


def _media_snapshot(journal: Journal, media: Any) -> dict[str, Any]:
    return {
        "GetName": _getter(journal, media, "GetName")[1],
        "GetUniqueId": _getter(journal, media, "GetUniqueId")[1],
        "GetClipProperty": _getter(journal, media, "GetClipProperty")[1],
        "GetMarkers": _getter(journal, media, "GetMarkers")[1],
        "GetAudioMapping": _getter(journal, media, "GetAudioMapping")[1],
        "GetMarkInOut": _getter(journal, media, "GetMarkInOut")[1],
    }


def _item_snapshot(journal: Journal, item: Any) -> dict[str, Any]:
    values = {method: _getter(journal, item, method)[1] for method in ITEM_GETTERS}
    for label, args in (
        ("GetStart(True)", (True,)),
        ("GetEnd(True)", (True,)),
        ("GetDuration(True)", (True,)),
        ("GetLeftOffset(True)", (True,)),
        ("GetRightOffset(True)", (True,)),
        ("GetProperty()", ()),
        ('GetProperty("Text")', ("Text",)),
    ):
        values[label] = _getter(
            journal,
            item,
            "GetProperty" if label.startswith("GetProperty") else label.split("(")[0],
            *args,
        )[1]
    linked, linked_value = _getter(journal, item, "GetLinkedItems")
    values["GetLinkedItems"] = linked_value
    if linked_value["status"] == "ok" and isinstance(linked, (list, tuple)):
        values["linkedUniqueIds"] = [
            _getter(journal, link, "GetUniqueId")[1] for link in linked
        ]
    media, media_value = _getter(journal, item, "GetMediaPoolItem")
    values["GetMediaPoolItem"] = media_value
    if media_value["status"] == "ok" and media is not None:
        values["mediaSnapshot"] = _media_snapshot(journal, media)
    return values


def _context_only_track(active_uid: Any, kind: str, index: int) -> dict[str, Any]:
    return {
        "status": "context-only",
        "activeTimelineUid": _json_value(active_uid),
        "captured": False,
        "kind": kind,
        "index": index,
    }


def _track_snapshot(
    journal: Journal,
    timeline: Any,
    kind: str,
    index: int,
    active: bool,
    active_uid: Any,
) -> dict[str, Any]:
    row = {
        "kind": kind,
        "index": index,
        "GetTrackName": _getter(journal, timeline, "GetTrackName", kind, index)[1],
        "GetTrackType": _getter(journal, timeline, "GetTrackType", kind, index)[1],
        "GetItemListInTrack": None,
    }
    if active:
        row.update(
            {
                "GetIsTrackEnabled": _getter(
                    journal, timeline, "GetIsTrackEnabled", kind, index
                )[1],
                "GetIsTrackLocked": _getter(
                    journal, timeline, "GetIsTrackLocked", kind, index
                )[1],
            }
        )
        if kind == "audio":
            row["GetTrackSubType"] = _getter(
                journal, timeline, "GetTrackSubType", kind, index
            )[1]
            row["GetVoiceIsolationState"] = _getter(
                journal, timeline, "GetVoiceIsolationState", index
            )[1]
    else:
        row["GetIsTrackEnabled"] = _context_only_track(active_uid, kind, index)
        row["GetIsTrackLocked"] = _context_only_track(active_uid, kind, index)
        if kind == "audio":
            row["GetTrackSubType"] = _getter(
                journal, timeline, "GetTrackSubType", kind, index
            )[1]
            row["GetVoiceIsolationState"] = _context_only_track(active_uid, kind, index)
    items = _item_rows(journal, timeline, kind, index)
    row["GetItemListInTrack"] = {
        "status": "ok",
        "value": [_item_snapshot(journal, item) for item in items],
    }
    return row


def _timeline_snapshot(
    journal: Journal, timeline: Any, project: Any, current_uid: Any
) -> dict[str, Any]:
    uid = _timeline_uid(journal, timeline)
    active = uid == current_uid
    row = {
        "getters": {
            method: _getter(journal, timeline, method)[1] for method in TIMELINE_GETTERS
        },
        "isCurrent": active,
        "activeContext": {"timelineUid": _json_value(current_uid), "captured": active},
        "tracks": {},
    }
    for kind in TRACK_KINDS:
        count = _getter(journal, timeline, "GetTrackCount", kind)[1]
        row["tracks"][kind] = []
        if count.get("status") == "ok" and isinstance(count.get("value"), int):
            for index in range(1, count["value"] + 1):
                row["tracks"][kind].append(
                    _track_snapshot(journal, timeline, kind, index, active, current_uid)
                )
    if active:
        selected, selected_value = _getter(journal, timeline, "GetSelectedClips")
        row["selectedClips"] = selected_value
        if selected_value["status"] == "ok" and isinstance(selected, (list, tuple)):
            row["selectedClipSnapshots"] = [
                _item_snapshot(journal, item) for item in selected
            ]
    else:
        row["selectedClips"] = _context_only_track(current_uid, "selection", 0)
        row["selectedClipSnapshots"] = []
    return row


def _pool_snapshot(journal: Journal, media_pool: Any) -> list[dict[str, Any]]:
    root = _required(journal, media_pool, "GetRootFolder")
    result: list[dict[str, Any]] = []

    def walk(folder: Any, path: str) -> None:
        clips = _required(journal, folder, "GetClipList") or []
        if not isinstance(clips, (list, tuple)):
            raise HarnessError("media-pool clip list is unreadable")
        for clip in clips:
            row = _media_snapshot(journal, clip)
            row["path"] = path
            result.append(row)
        children = _required(journal, folder, "GetSubFolderList") or []
        if not isinstance(children, (list, tuple)):
            raise HarnessError("media-pool folder list is unreadable")
        for child in children:
            child_name = _getter(journal, child, "GetName")[1].get("value")
            walk(child, f"{path}/{child_name}")

    walk(root, "")
    return result


def snapshot(
    resolve: Any, journal: Journal, project: Any | None = None
) -> dict[str, Any]:
    """Capture one complete pair member without switching timelines."""
    page = _getter(journal, resolve, "GetCurrentPage")[1]
    manager = _required(journal, resolve, "GetProjectManager")
    if project is None:
        project = _required(journal, manager, "GetCurrentProject")
    if project is None:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "page": page,
            "project": None,
            "currentTimeline": _status(None),
            "pool": [],
            "complete": True,
        }
    project_uid = _getter(journal, project, "GetUniqueId")[1]
    project_name = _getter(journal, project, "GetName")[1]
    current = _required(journal, project, "GetCurrentTimeline")
    current_uid = (
        _getter(journal, current, "GetUniqueId")[1].get("value")
        if current is not None
        else None
    )
    current_name = (
        _getter(journal, current, "GetName")[1]
        if current is not None
        else _status(None)
    )
    settings = _getter(journal, project, "GetSettings")[1]
    queue = _getter(journal, project, "GetRenderJobList")[1]
    rendering = _getter(journal, project, "IsRenderingInProgress")[1]
    media_pool = _required(journal, project, "GetMediaPool")
    timelines = _timeline_handles(project, journal)
    timeline_rows = [
        _timeline_snapshot(journal, row, project, current_uid) for row in timelines
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "page": page,
        "project": {
            "GetName": project_name,
            "GetUniqueId": project_uid,
            "GetSettings": settings,
            "GetRenderJobList": queue,
            "IsRenderingInProgress": rendering,
            "timelines": timeline_rows,
        },
        "currentTimeline": {
            "GetName": current_name,
            "GetUniqueId": _status(current_uid),
            "selected": next(
                (
                    row.get("selectedClips")
                    for row in timeline_rows
                    if row.get("isCurrent")
                ),
                _status(None),
            ),
        },
        "pool": _pool_snapshot(journal, media_pool),
        "complete": True,
    }


def _snapshot_project_uid(value: Mapping[str, Any]) -> Any:
    return (
        value.get("project", {}).get("GetUniqueId", {}).get("value")
        if isinstance(value.get("project"), Mapping)
        else None
    )


def _state(value: Mapping[str, Any]) -> dict[str, Any]:
    project = (
        value.get("project", {}) if isinstance(value.get("project"), Mapping) else {}
    )
    timelines = project.get("timelines", []) if isinstance(project, Mapping) else []
    rows = []
    item_uids: list[Any] = []
    for timeline in timelines:
        getters = timeline.get("getters", {})
        uid = getters.get("GetUniqueId", {}).get("value")
        name = getters.get("GetName", {}).get("value")
        tids = []
        for track in sum(
            (timeline.get("tracks", {}).get(kind, []) for kind in TRACK_KINDS), []
        ):
            for item in track.get("GetItemListInTrack", {}).get("value", []):
                item_uid = item.get("GetUniqueId", {}).get("value")
                if item_uid is not None:
                    tids.append(item_uid)
                    item_uids.append(item_uid)
        rows.append({"uid": uid, "name": name, "itemUids": tids})
    media_uids = [
        row.get("GetUniqueId", {}).get("value") for row in value.get("pool", [])
    ]
    return {
        "projectUid": _snapshot_project_uid(value),
        "timelineUids": [row["uid"] for row in rows if row["uid"] is not None],
        "timelines": rows,
        "itemUids": item_uids,
        "mediaUids": [uid for uid in media_uids if uid is not None],
    }


def _media_entries(
    config: Mapping[str, Any], output: Path
) -> list[tuple[str, Path, str]]:
    entries = config.get("media", [])
    if not isinstance(entries, list) or not entries:
        raise HarnessError("prepare requires hash-pinned media entries")
    media_dir = output / MEDIA_DIR_NAME
    result = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise HarnessError("media entry is malformed")
        relative = Path(str(entry.get("relative", "")))
        digest = entry.get("sha256")
        name = entry.get("name")
        if (
            not name
            or relative.is_absolute()
            or ".." in relative.parts
            or not isinstance(digest, str)
        ):
            raise HarnessError("media entry path/hash/name is unsafe")
        path = media_dir / relative
        if (
            path.is_symlink()
            or not path.is_file()
            or not _inside(path, media_dir)
            or sha256(path) != digest
        ):
            raise HarnessError(f"media hash differs: {relative}")
        result.append((str(name), path, digest))
    if len({name for name, _, _ in result}) != len(result):
        raise HarnessError("media names must be unique")
    return result


def _prepare(
    resolve: Any, config: Mapping[str, Any], journal: Journal
) -> dict[str, Any]:
    output = _path(config, "outputDir")
    entries = _media_entries(config, output)
    settings = config.get(
        "settings",
        {
            "timelineFrameRate": "25",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
            "timelineSampleRate": "48000",
        },
    )
    if not isinstance(settings, Mapping):
        raise HarnessError("settings must be an object")
    if "timelinePlaybackFrameRate" in settings:
        raise HarnessError(
            "timelinePlaybackFrameRate is read-only; retain it for manual operator review"
        )
    manager = _required(journal, resolve, "GetProjectManager")
    _empty_startup_project(journal, manager)
    created = _dispatch(journal, manager, "CreateProject", PROJECT_NAME)
    if created is False or created is None:
        raise HarnessError("CreateProject refused the new synthetic project")
    project = _current_project(resolve, journal, config)
    returned = _dispatch(journal, project, "SetSettings", dict(settings))
    if returned is not True:
        raise HarnessError("SetSettings refused the configured synthetic settings")
    observed_settings = _required(journal, project, "GetSettings")
    if not isinstance(observed_settings, Mapping):
        raise HarnessError("GetSettings returned no settings object after preparation")
    observed_playback = observed_settings.get("timelinePlaybackFrameRate")
    try:
        if float(observed_playback) != 25.0:
            raise HarnessError(
                "prepared timelinePlaybackFrameRate differs: "
                f"{observed_playback!r}, expected 25"
            )
    except (TypeError, ValueError):
        raise HarnessError(
            "prepared timelinePlaybackFrameRate is missing or non-numeric"
        ) from None
    for key, expected in settings.items():
        actual = observed_settings.get(key)
        try:
            if float(actual) != float(expected):
                raise HarnessError(
                    f"prepared setting differs: {key}={actual!r}, expected {expected!r}"
                )
        except (TypeError, ValueError):
            if actual != expected:
                raise HarnessError(
                    f"prepared setting differs: {key}={actual!r}, expected {expected!r}"
                ) from None
    media_pool = _required(journal, project, "GetMediaPool")
    imported = _dispatch(
        journal, media_pool, "ImportMedia", [str(path) for _, path, _ in entries]
    )
    if not isinstance(imported, (list, tuple)) or len(imported) != len(entries):
        raise HarnessError("ImportMedia did not return exactly the hash-pinned files")
    media = []
    for (expected_name, path, digest), item in zip(entries, imported, strict=True):
        name = _required(journal, item, "GetName")
        if name != expected_name:
            raise HarnessError(f"imported media name differs: {expected_name} / {name}")
        uid = _required(journal, item, "GetUniqueId")
        media.append({"name": name, "uid": uid, "path": str(path), "sha256": digest})
    _dispatch(journal, manager, "SaveProject")
    return {
        "state": {
            "projectUid": _required(journal, project, "GetUniqueId"),
            "timelineUids": [],
            "itemUids": [],
            "mediaUids": [row["uid"] for row in media],
        },
        "media": media,
    }


def _media_by_name(project: Any, journal: Journal) -> dict[str, Any]:
    pool = _required(journal, project, "GetMediaPool")
    rows = _pool_snapshot(journal, pool)
    clips = _required(journal, pool, "GetRootFolder")
    result: dict[str, Any] = {}

    def walk(folder: Any) -> None:
        for clip in _required(journal, folder, "GetClipList") or []:
            name = _required(journal, clip, "GetName")
            if name in result:
                raise HarnessError(f"duplicate media name: {name}")
            result[name] = clip
        for child in _required(journal, folder, "GetSubFolderList") or []:
            walk(child)

    walk(clips)
    return result


def _build(
    resolve: Any, config: Mapping[str, Any], project: Any, journal: Journal
) -> dict[str, Any]:
    specs = config.get("timelineSpecs")
    if not isinstance(specs, list) or not specs:
        raise HarnessError("build requires timelineSpecs")
    existing = _timeline_handles(project, journal)
    existing_names = {_required(journal, row, "GetName") for row in existing}
    media = _media_by_name(project, journal)
    created = []
    pool = _required(journal, project, "GetMediaPool")
    for spec in specs:
        if not isinstance(spec, Mapping) or not isinstance(spec.get("name"), str):
            raise HarnessError("timeline spec is malformed")
        name = spec["name"]
        if name in existing_names:
            raise HarnessError(f"timeline already exists: {name}")
        timeline = _dispatch(journal, pool, "CreateEmptyTimeline", name)
        if timeline is None:
            raise HarnessError(f"CreateEmptyTimeline returned no timeline: {name}")
        if _required(journal, timeline, "GetName") != name:
            raise HarnessError("created timeline name differs")
        if not _dispatch(journal, project, "SetCurrentTimeline", timeline) is True:
            raise HarnessError("SetCurrentTimeline refused a new timeline")
        if not _dispatch(journal, timeline, "SetStartTimecode", "00:00:00:00") is True:
            raise HarnessError("SetStartTimecode refused the zero start")
        # Create the two explicit A2/A3 mono tracks.  The embedded A1 track
        # is supplied by the AV source and its native subtype is evidence.
        audio_count = spec.get("audioTracks", 2)
        video_count = spec.get("videoTracks", 1)
        if (
            not isinstance(audio_count, int)
            or audio_count < 2
            or not isinstance(video_count, int)
            or video_count < 1
        ):
            raise HarnessError(
                "every synthetic timeline requires two explicit mono audio tracks"
            )
        for _ in range(audio_count):
            if not _dispatch(journal, timeline, "AddTrack", "audio", "mono") is True:
                raise HarnessError("AddTrack(audio, mono) refused")
        for _ in range(video_count):
            if not _dispatch(journal, timeline, "AddTrack", "video") is True:
                raise HarnessError("AddTrack(video) refused")
        items = []
        placements = spec.get("placements", [])
        if not isinstance(placements, list):
            raise HarnessError("timeline placements must be a list")
        for placement in placements:
            if not isinstance(placement, Mapping):
                raise HarnessError("timeline placement is malformed")
            source_name = placement.get("mediaName")
            start = placement.get("sourceStart", placement.get("startFrame"))
            end = placement.get("sourceEndExclusive", placement.get("endExclusive"))
            record = placement.get("recordFrame")
            kind = placement.get("trackType", "video")
            track = placement.get("trackIndex", 1)
            if (
                source_name not in media
                or not all(
                    isinstance(value, int) for value in (start, end, record, track)
                )
                or end <= start
                or end <= 0
            ):
                raise HarnessError("placement source/range/track is malformed")
            info: dict[str, Any] = {
                "mediaPoolItem": media[source_name],
                "startFrame": start,
                "endFrame": end - 1,
                "recordFrame": record,
                "trackIndex": track,
            }
            if kind == "video":
                info["mediaType"] = 1
            elif kind == "audio":
                info["mediaType"] = 2
            elif kind != "av":
                raise HarnessError("trackType must be video, audio, or av")
            appended = _dispatch(journal, pool, "AppendToTimeline", [info])
            if not isinstance(appended, (list, tuple)):
                raise HarnessError("AppendToTimeline return is unreadable")
            for item in appended:
                items.append(_required(journal, item, "GetUniqueId"))
        created.append(
            {
                "uid": _required(journal, timeline, "GetUniqueId"),
                "name": name,
                "itemUids": items,
            }
        )
        existing_names.add(name)
    _dispatch(journal, _required(journal, resolve, "GetProjectManager"), "SaveProject")
    return {"createdTimelines": created}


def _find_timeline(project: Any, journal: Journal, uid: str) -> Any:
    for timeline in _timeline_handles(project, journal):
        if _timeline_uid(journal, timeline) == uid:
            return timeline
    raise HarnessError(f"timeline UID is missing: {uid}")


def _find_item(journal: Journal, timeline: Any, uid: str) -> Any:
    for kind in TRACK_KINDS:
        count = _required(journal, timeline, "GetTrackCount", kind)
        for index in range(1, count + 1):
            for item in _item_rows(journal, timeline, kind, index):
                if _required(journal, item, "GetUniqueId") == uid:
                    return item
    raise HarnessError(f"item UID is missing: {uid}")


def _w1_request(
    resolve: Any, project: Any, config: Mapping[str, Any], journal: Journal
) -> dict[str, Any]:
    requests = config.get("duplicates")
    if not isinstance(requests, list) or len(requests) != 1:
        raise HarnessError("w1 subtitle request requires exactly one source/duplicate")
    names = {
        _required(journal, row, "GetName")
        for row in _timeline_handles(project, journal)
    }
    created = []
    for request in requests:
        if (
            not isinstance(request, Mapping)
            or not isinstance(request.get("sourceTimelineUid"), str)
            or not isinstance(request.get("duplicateName"), str)
        ):
            raise HarnessError("duplicate request is malformed")
        if request["duplicateName"] in names:
            raise HarnessError("duplicate name already exists; refusing second request")
        source = _find_timeline(project, journal, request["sourceTimelineUid"])
        if not _dispatch(journal, project, "SetCurrentTimeline", source) is True:
            raise HarnessError("could not select the W1 source")
        duplicate = _dispatch(
            journal, source, "DuplicateTimeline", request["duplicateName"]
        )
        if duplicate is None:
            raise HarnessError("DuplicateTimeline returned no timeline")
        duplicate_uid = _required(journal, duplicate, "GetUniqueId")
        if (
            duplicate_uid in {request["sourceTimelineUid"]}
            or _required(journal, duplicate, "GetName") != request["duplicateName"]
        ):
            raise HarnessError("duplicate identity differs")
        if not _dispatch(journal, project, "SetCurrentTimeline", duplicate) is True:
            raise HarnessError("could not select the subtitle duplicate")
        requested = _dispatch(journal, duplicate, "CreateSubtitlesFromAudio")
        if requested is not True:
            raise HarnessError("CreateSubtitlesFromAudio refused the exact duplicate")
        names.add(request["duplicateName"])
        created.append(
            {
                "sourceTimelineUid": request["sourceTimelineUid"],
                "duplicateTimelineUid": duplicate_uid,
                "duplicateName": request["duplicateName"],
                "requestReturn": requested,
            }
        )
    _dispatch(journal, _required(journal, resolve, "GetProjectManager"), "SaveProject")
    return {"duplicates": created, "subtitleRequests": len(created)}


def _subtitle_done(status: Any, items: Any) -> bool:
    if not isinstance(items, list) or not items:
        return False
    if status is True:
        return True
    if isinstance(status, str):
        return status.strip().lower() in {
            "complete",
            "completed",
            "done",
            "finished",
            "success",
            "succeeded",
        }
    if isinstance(status, Mapping):
        state = status.get("status", status.get("state", status.get("Status")))
        return isinstance(state, str) and state.strip().lower() in {
            "complete",
            "completed",
            "done",
            "finished",
            "success",
            "succeeded",
        }
    return False


def _w1_poll(
    project: Any, config: Mapping[str, Any], journal: Journal
) -> dict[str, Any]:
    ids = config.get("duplicateTimelineUids")
    if (
        not isinstance(ids, list)
        or not ids
        or not all(isinstance(uid, str) for uid in ids)
    ):
        raise HarnessError("w1 subtitle poll requires duplicateTimelineUids")
    timeout = min(float(config.get("pollTimeoutSec", 120)), 180.0)
    interval = min(max(float(config.get("pollIntervalSec", 0.25)), 0.05), 5.0)
    deadline = time.monotonic() + timeout
    observations = []
    complete = False
    while True:
        observations = []
        complete = True
        for uid in ids:
            timeline = _find_timeline(project, journal, uid)
            status = _getter(journal, timeline, "GetCreateSubtitlesFromAudioStatus")[1]
            subtitle_tracks = _getter(journal, timeline, "GetTrackCount", "subtitle")[1]
            items: list[Any] = []
            if subtitle_tracks.get("status") == "ok" and isinstance(
                subtitle_tracks.get("value"), int
            ):
                for index in range(1, subtitle_tracks["value"] + 1):
                    item_list = _getter(
                        journal, timeline, "GetItemListInTrack", "subtitle", index
                    )[1]
                    if item_list.get("status") == "ok" and isinstance(
                        item_list.get("value"), list
                    ):
                        items.extend(item_list["value"])
            ready = (
                _subtitle_done(status.get("value"), items)
                if status.get("status") == "ok"
                else False
            )
            complete = complete and ready
            observations.append(
                {
                    "timelineUid": uid,
                    "status": status,
                    "subtitleItemCount": len(items),
                    "complete": ready,
                }
            )
        if complete or time.monotonic() >= deadline:
            break
        time.sleep(min(interval, max(0.0, deadline - time.monotonic())))
    return {
        "subtitlePoll": observations,
        "status": "complete" if complete else "pending",
        "pollReadOnly": True,
    }


def _export_otio(
    resolve: Any, timeline: Any, config: Mapping[str, Any], journal: Journal
) -> dict[str, Any]:
    export = config.get("export", {})
    if not isinstance(export, Mapping):
        raise HarnessError("export must be an object")
    path = _path({"exportPath": export.get("path")}, "exportPath")
    output = _path(config, "outputDir")
    if not _inside(path, output) or path.exists() or path.parent.name != "exports":
        raise HarnessError("export path must be a new file under outputDir/exports")
    export_type = _constant(journal, resolve, "EXPORT_OTIO")
    export_subtype = _constant(journal, resolve, "EXPORT_NONE")
    returned = _dispatch(
        journal, timeline, "Export", str(path), export_type, export_subtype
    )
    if returned is not True or not path.is_file():
        raise HarnessError("OTIO export failed or produced no file")
    return {"path": str(path), "sha256": sha256(path), "return": returned}


def _render_stage(
    resolve: Any, project: Any, config: Mapping[str, Any], journal: Journal
) -> dict[str, Any] | None:
    render = config.get("render")
    if render is None:
        return None
    if not isinstance(render, Mapping) or not isinstance(
        render.get("settings"), Mapping
    ):
        raise HarnessError("render settings are malformed")
    output = _path(config, "outputDir")
    target_dir = Path(str(render.get("targetDir", output / "renders")))
    if not target_dir.is_absolute() or not _inside(target_dir, output):
        raise HarnessError("render target directory is outside the owned output")
    target_dir.mkdir(parents=True, exist_ok=True)
    settings = dict(render["settings"])
    settings.setdefault("TargetDir", str(target_dir))
    _dispatch(journal, project, "SetRenderSettings", settings)
    returned_id = _dispatch(journal, project, "AddRenderJob")
    if not isinstance(returned_id, str) or not returned_id:
        raise HarnessError("AddRenderJob did not return an owned job ID")
    queue = _required(journal, project, "GetRenderJobList")
    if not isinstance(queue, list):
        raise HarnessError("render queue is unreadable")
    owned = [
        job
        for job in queue
        if isinstance(job, Mapping) and job.get("JobId") == returned_id
    ]
    if len(owned) != 1:
        raise HarnessError("returned render job is not attributable in the owned queue")
    started = _dispatch(journal, project, "StartRendering", [returned_id])
    if started is not True:
        raise HarnessError("StartRendering refused the exact returned job ID")
    return {
        "jobId": returned_id,
        "startReturn": started,
        "queuedJob": owned[0],
        "startedExactlyOnce": True,
    }


def _render_poll(
    project: Any, config: Mapping[str, Any], journal: Journal
) -> dict[str, Any]:
    job_id = config.get("jobId")
    if not isinstance(job_id, str) or not job_id:
        raise HarnessError("render-poll requires an owned jobId")
    queue = _required(journal, project, "GetRenderJobList")
    if not isinstance(queue, list) or not any(
        isinstance(job, Mapping) and job.get("JobId") == job_id for job in queue
    ):
        raise HarnessError("render-poll job is absent from the current queue")
    timeout = min(float(config.get("pollTimeoutSec", 180)), 300.0)
    interval = min(max(float(config.get("pollIntervalSec", 0.25)), 0.05), 5.0)
    terminal = {"complete", "completed", "failed", "error", "cancelled", "canceled"}
    deadline = time.monotonic() + timeout
    latest = None
    while True:
        latest = _getter(journal, project, "GetRenderJobStatus", job_id)[1]
        state = (
            latest.get("value", {}).get("JobStatus")
            if latest.get("status") == "ok" and isinstance(latest.get("value"), Mapping)
            else None
        )
        if isinstance(state, str) and state.strip().lower() in terminal:
            return {
                "jobId": job_id,
                "jobStatus": latest,
                "renderPoll": "terminal",
                "startRenderingCalled": False,
            }
        if time.monotonic() >= deadline:
            return {
                "jobId": job_id,
                "jobStatus": latest,
                "renderPoll": "pending",
                "startRenderingCalled": False,
            }
        time.sleep(min(interval, max(0.0, deadline - time.monotonic())))


def _w2_export(
    resolve: Any, project: Any, config: Mapping[str, Any], journal: Journal
) -> dict[str, Any]:
    timeline = _current_timeline(project, journal)
    expected = config.get("timelineUid")
    if isinstance(expected, str) and _timeline_uid(journal, timeline) != expected:
        raise HarnessError("W2 operator-selected timeline differs")
    return {
        "otio": _export_otio(resolve, timeline, config, journal),
        "operatorStateReadOnly": True,
    }


def _mapping_muted(raw: Any, track_key: str) -> Any:
    original = deepcopy(raw)
    if isinstance(raw, str):
        try:
            mapping = json.loads(raw)
        except (TypeError, ValueError) as error:
            raise HarnessError("source mapping string is not JSON") from error
    elif isinstance(raw, Mapping):
        mapping = deepcopy(raw)
    else:
        raise HarnessError("source mapping must be a JSON object or JSON string")
    track_mapping = (
        mapping.get("track_mapping") if isinstance(mapping, Mapping) else None
    )
    target = (
        track_mapping.get(track_key) if isinstance(track_mapping, Mapping) else None
    )
    if not isinstance(target, Mapping):
        raise HarnessError(f"source mapping track {track_key} is missing")
    target["mute"] = True
    if isinstance(raw, str):
        return original, json.dumps(mapping, sort_keys=True)
    return original, mapping


def _w3_mute(
    resolve: Any, project: Any, config: Mapping[str, Any], journal: Journal
) -> dict[str, Any]:
    timeline = _current_timeline(project, journal)
    timeline_uid = _timeline_uid(journal, timeline)
    if timeline_uid != config.get("timelineUid"):
        raise HarnessError("W3 mapping target timeline is not current")
    item = _find_item(journal, timeline, config["itemUid"])
    original = _required(journal, item, "GetSourceAudioChannelMapping")
    original, muted = _mapping_muted(original, str(config.get("mappingTrackKey", "1")))
    returned = _dispatch(journal, item, "SetSourceAudioChannelMapping", muted)
    if returned is False:
        raise HarnessError("mapping mute setter refused")
    readback = _required(journal, item, "GetSourceAudioChannelMapping")
    if readback != muted:
        raise HarnessError("mapping mute readback differs")
    render = _render_stage(resolve, project, config, journal)
    return {
        "originalMapping": original,
        "mutedMapping": muted,
        "render": render,
        "mappingMute": True,
    }


def _diff_paths(before: Any, after: Any, prefix: str = "") -> list[str]:
    if type(before) is not type(after):
        return [prefix or "$type"]
    if isinstance(before, Mapping):
        paths = []
        for key in sorted(set(before) | set(after), key=str):
            child = f"{prefix}.{key}" if prefix else str(key)
            if key not in before or key not in after:
                paths.append(child)
            else:
                paths.extend(_diff_paths(before[key], after[key], child))
        return paths
    if isinstance(before, list):
        paths = []
        for index in range(max(len(before), len(after))):
            child = f"{prefix}[{index}]"
            if index >= len(before) or index >= len(after):
                paths.append(child)
            else:
                paths.extend(_diff_paths(before[index], after[index], child))
        return paths
    return [] if before == after else [prefix]


def _mapping_paths(snapshot_value: Mapping[str, Any], item_uid: str) -> list[str]:
    paths = []
    project = snapshot_value.get("project", {})
    for timeline_index, timeline in enumerate(project.get("timelines", [])):
        for kind in TRACK_KINDS:
            for track_index, track in enumerate(
                timeline.get("tracks", {}).get(kind, [])
            ):
                for item_index, item in enumerate(
                    track.get("GetItemListInTrack", {}).get("value", [])
                ):
                    if item.get("GetUniqueId", {}).get("value") == item_uid:
                        paths.append(
                            f"project.timelines[{timeline_index}].tracks.{kind}[{track_index}]"
                            f".GetItemListInTrack.value[{item_index}].GetSourceAudioChannelMapping"
                        )
    return paths


def _w3_restore(
    project: Any, config: Mapping[str, Any], journal: Journal
) -> dict[str, Any]:
    timeline = _current_timeline(project, journal)
    if _timeline_uid(journal, timeline) != config.get("timelineUid"):
        raise HarnessError("W3 restore timeline is not current")
    item = _find_item(journal, timeline, config["itemUid"])
    expected_muted = config.get("mutedMapping")
    current = _required(journal, item, "GetSourceAudioChannelMapping")
    if expected_muted is not None and current != expected_muted:
        raise HarnessError("W3 current mapping differs from the held muted mapping")
    original = config.get("originalMapping")
    if original is None:
        raise HarnessError("W3 restore requires the exact held original mapping")
    returned = _dispatch(journal, item, "SetSourceAudioChannelMapping", original)
    if returned is False:
        raise HarnessError("mapping restore setter refused")
    restored = _required(journal, item, "GetSourceAudioChannelMapping")
    if restored != original:
        raise HarnessError(
            "mapping restore readback differs from exact original raw value"
        )
    return {"restoredMapping": restored, "mappingRestore": True}


def _w4_speed(
    resolve: Any, project: Any, config: Mapping[str, Any], journal: Journal
) -> dict[str, Any]:
    timeline = _current_timeline(project, journal)
    if _timeline_uid(journal, timeline) != config.get("timelineUid"):
        raise HarnessError("W4 speed target timeline is not current")
    item = _find_item(journal, timeline, config["itemUid"])
    original = _required(journal, item, "GetSpeed")
    options = config.get("speedOptions")
    if not isinstance(options, Mapping):
        raise HarnessError("W4 speedOptions must be an object")
    returned = _dispatch(journal, item, "SetSpeed", dict(options))
    if returned is False:
        raise HarnessError("SetSpeed refused the configured options")
    readback = _required(journal, item, "GetSpeed")
    render = _render_stage(resolve, project, config, journal)
    export = (
        _export_otio(resolve, timeline, config, journal)
        if config.get("export")
        else None
    )
    return {
        "originalSpeed": original,
        "speedOptions": dict(options),
        "speedReadback": readback,
        "render": render,
        "otio": export,
    }


def _w5_context_read(
    project: Any, config: Mapping[str, Any], journal: Journal
) -> dict[str, Any]:
    current = _current_timeline(project, journal)
    current_uid = _timeline_uid(journal, current)
    if current_uid != config.get("currentTimelineUid"):
        raise HarnessError("W5 current timeline differs")
    inactive_uid = config.get("inactiveTimelineUid")
    if not isinstance(inactive_uid, str) or inactive_uid == current_uid:
        raise HarnessError("W5 requires a distinct inactive timeline")
    kind = config.get("trackKind", "audio")
    if kind != "audio":
        raise HarnessError("W5 explicitly compares the audio track getter")

    def enabled_rows(timeline: Any) -> list[dict[str, Any]]:
        count = _required(journal, timeline, "GetTrackCount", "audio")
        return [
            {
                "index": index,
                "GetIsTrackEnabled": _getter(
                    journal, timeline, "GetIsTrackEnabled", "audio", index
                )[1],
            }
            for index in range(1, count + 1)
        ]

    current_read = enabled_rows(current)
    inactive = _find_timeline(project, journal, inactive_uid)
    if not _dispatch(journal, project, "SetCurrentTimeline", inactive) is True:
        raise HarnessError("W5 inactive timeline selection refused")
    inactive_read = enabled_rows(inactive)
    target_while_inactive = enabled_rows(current)
    if not _dispatch(journal, project, "SetCurrentTimeline", current) is True:
        raise HarnessError("W5 current timeline restoration refused")
    return {
        "xCurrent": current_read,
        "yCurrent": inactive_read,
        "xWhileYCurrent": target_while_inactive,
        "getterContext": {
            "activeTimelineUid": current_uid,
            "inactiveTimelineUid": inactive_uid,
        },
    }


def _swap_guard(config: Mapping[str, Any]) -> tuple[dict[str, Any], Path]:
    swap = config.get("swap")
    if not isinstance(swap, Mapping):
        raise HarnessError("W6 swap guard is required")
    path = Path(str(swap.get("path", "")))
    media = _path(config, "mediaDir")
    if (
        not path.is_absolute()
        or path.is_symlink()
        or not path.is_file()
        or not _inside(path, media)
    ):
        raise HarnessError("W6 external swap path is unsafe")
    if (
        swap.get("replacementHasAudio") is not True
        or swap.get("replacementAudioChannels") != 1
    ):
        raise HarnessError(
            "W6 requires a same-layout replacement with one mono audio stream"
        )
    expected = swap.get("expectedSha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise HarnessError("W6 expected hash is required")
    return dict(swap), path


def _w6_guard(
    config: Mapping[str, Any], journal: Journal, *, replacement: bool
) -> dict[str, Any]:
    swap, path = _swap_guard(config)
    digest = sha256(path)
    expected_key = "expectedSha256" if replacement else "originalSha256"
    if digest != swap.get(expected_key):
        raise HarnessError(f"W6 external file hash differs for {expected_key}")
    return {
        "externalSwap": {
            "path": str(path),
            "sha256": digest,
            "phase": "replacement" if replacement else "original",
            "restoreOwner": "root",
            "sameLayoutAudio": "mono",
        }
    }


def _w6_relink(
    resolve: Any, project: Any, config: Mapping[str, Any], journal: Journal
) -> dict[str, Any]:
    swap_info = _w6_guard(config, journal, replacement=True)
    media_pool = _required(journal, project, "GetMediaPool")
    media_uid = config.get("mediaUid")
    pool_item = None
    root = _required(journal, media_pool, "GetRootFolder")

    def walk(folder: Any) -> None:
        nonlocal pool_item
        for clip in _required(journal, folder, "GetClipList") or []:
            if _required(journal, clip, "GetUniqueId") == media_uid:
                pool_item = clip
        for child in _required(journal, folder, "GetSubFolderList") or []:
            walk(child)

    walk(root)
    if pool_item is None:
        raise HarnessError("W6 pool media UID is missing")
    folder = Path(str(config.get("relinkFolder", "")))
    media = _path(config, "mediaDir")
    if not folder.is_dir() or folder.is_symlink() or not _inside(folder, media):
        raise HarnessError("W6 relink folder is unsafe")
    returned = _dispatch(journal, media_pool, "RelinkClips", [pool_item], str(folder))
    if returned is False:
        raise HarnessError("RelinkClips refused the externally guarded replacement")
    render = _render_stage(resolve, project, config, journal)
    return {"relinkReturn": returned, **swap_info, "render": render}


def _lock_tracks(timeline: Any, journal: Journal, locked: bool) -> list[dict[str, Any]]:
    calls = []
    for kind in TRACK_KINDS:
        count = _required(journal, timeline, "GetTrackCount", kind)
        for index in range(1, count + 1):
            returned = _dispatch(journal, timeline, "SetTrackLock", kind, index, locked)
            if returned is False:
                raise HarnessError(f"SetTrackLock refused {kind} {index}={locked}")
            calls.append(
                {"kind": kind, "index": index, "locked": locked, "return": returned}
            )
    return calls


def _timeline_item_uids(timeline: Any, journal: Journal) -> list[str]:
    result = []
    for kind in TRACK_KINDS:
        count = _required(journal, timeline, "GetTrackCount", kind)
        for index in range(1, count + 1):
            for item in _item_rows(journal, timeline, kind, index):
                uid = _required(journal, item, "GetUniqueId")
                if isinstance(uid, str):
                    result.append(uid)
    return result


def _w7_lock(
    project: Any, config: Mapping[str, Any], journal: Journal
) -> dict[str, Any]:
    timeline = _current_timeline(project, journal)
    if _timeline_uid(journal, timeline) != config.get("timelineUid"):
        raise HarnessError("W7 lock timeline is not current")
    before_items = _timeline_item_uids(timeline, journal)
    locks = _lock_tracks(timeline, journal, True)
    item = _find_item(journal, timeline, config["itemUid"])
    setter = _dispatch(journal, item, "SetClipEnabled", False)
    if setter is not False:
        raise HarnessError(f"locked SetClipEnabled must return False, got {setter!r}")
    after_items = _timeline_item_uids(timeline, journal)
    if before_items != after_items:
        raise HarnessError("locked SetClipEnabled changed timeline items")
    return {
        "locks": locks,
        "setClipEnabledReturn": setter,
        "itemCountBefore": len(before_items),
        "itemCountAfter": len(after_items),
        "itemUidsBefore": before_items,
        "itemUidsAfter": after_items,
        "menuDeleteOwner": "root",
    }


def _w7_unlock(
    project: Any, config: Mapping[str, Any], journal: Journal
) -> dict[str, Any]:
    timeline = _current_timeline(project, journal)
    if _timeline_uid(journal, timeline) != config.get("timelineUid"):
        raise HarnessError("W7 unlock timeline is not current")
    return {"locks": _lock_tracks(timeline, journal, False), "menuDeleteOwner": "root"}


def _action(
    resolve: Any, project: Any | None, config: Mapping[str, Any], journal: Journal
) -> dict[str, Any]:
    action = config["action"]
    if action == "context":
        return {"context": _context_only(resolve, journal)}
    if action == "prepare":
        return _prepare(resolve, config, journal)
    if project is None:
        raise HarnessError("action requires the named current project")
    if action == "build":
        return _build(resolve, config, project, journal)
    if action == "w1-subtitle-request":
        return _w1_request(resolve, project, config, journal)
    if action == "w1-subtitle-poll":
        return _w1_poll(project, config, journal)
    if action == "w2-export":
        return _w2_export(resolve, project, config, journal)
    if action == "w3-mapping-mute":
        return _w3_mute(resolve, project, config, journal)
    if action == "w3-mapping-restore":
        return _w3_restore(project, config, journal)
    if action == "w4-speed":
        return _w4_speed(resolve, project, config, journal)
    if action == "w5-context-read":
        return _w5_context_read(project, config, journal)
    if action == "w6-before-swap":
        return _w6_guard(config, journal, replacement=False)
    if action == "w6-after-swap":
        result = _w6_guard(config, journal, replacement=True)
        result["render"] = _render_stage(resolve, project, config, journal)
        return result
    if action == "w6-relink-render":
        return _w6_relink(resolve, project, config, journal)
    if action == "w7-lock-setter":
        return _w7_lock(project, config, journal)
    if action == "w7-unlock":
        return _w7_unlock(project, config, journal)
    if action == "render-poll":
        return _render_poll(project, config, journal)
    raise HarnessError(f"unimplemented action {action}")


def _capture(
    journal: Journal, resolve: Any, project: Any | None, label: str
) -> dict[str, Any]:
    journal.write("snapshot", "request", {"label": label})
    try:
        value = snapshot(resolve, journal, project)
        path = journal.directory / f"{label}.json"
        _write_json(path, value, exclusive=True)
        journal.write("snapshot", "return", {"label": label, "path": str(path)})
        return value
    except Exception as error:
        journal.write("snapshot", "failure", _error(error))
        raise


def run(
    resolve: Any, config: Mapping[str, Any], *, configSha256: str | None = None
) -> dict[str, Any]:
    """Execute exactly one configured phase and retain a complete pair when possible."""
    _validate_config(config)
    output = _path(config, "outputDir")
    journal = Journal(output, config["actionId"])
    result: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "action": config["action"],
        "phase": config["phase"],
        "actionId": config["actionId"],
        "stateId": config.get("stateId"),
        "configSha256": configSha256,
        "journal": str(journal.path),
    }
    pre = post = None
    project = None
    try:
        if config["action"] == "context":
            result.update(_action(resolve, None, config, journal))
            result["status"] = "ok"
            return result
        if config["action"] == "prepare":
            manager = _required(journal, resolve, "GetProjectManager")
            current = _empty_startup_project(journal, manager)
            pre = _capture(journal, resolve, current, "pre")
            result.update(_action(resolve, None, config, journal))
            project = _current_project(resolve, journal, config)
        else:
            project = _current_project(resolve, journal, config)
            _owned_guard(project, journal, config)
            pre = _capture(journal, resolve, project, "pre")
            result.update(_action(resolve, project, config, journal))
        if project is None:
            project = _current_project(resolve, journal, config)
        post = _capture(journal, resolve, project, "post")
        if config["action"] == "w3-mapping-restore":
            differences = _diff_paths(pre, post)
            configured_allowed = config.get("allowedRestoreDifferencePaths", [])
            if not isinstance(configured_allowed, list) or not all(
                isinstance(path, str) for path in configured_allowed
            ):
                raise HarnessError("W3 allowedRestoreDifferencePaths must be a list")
            allowed = (
                _mapping_paths(pre, str(config.get("itemUid"))) + configured_allowed
            )
            unexpected = [
                path
                for path in differences
                if not any(
                    path == prefix
                    or path.startswith(prefix + ".")
                    or path.startswith(prefix + "[")
                    for prefix in allowed
                )
            ]
            result["snapshotDifferences"] = {
                "all": differences,
                "allowed": allowed,
                "unexpected": unexpected,
            }
            if unexpected:
                raise HarnessError(
                    f"W3 restore changed unapproved snapshot paths: {unexpected}"
                )
        result["state"] = _state(post)
        result["status"] = result.get("status", "ok")
        return result
    except Exception as error:
        result.update({"status": "failure", "error": _error(error)})
        if pre is not None:
            result["preSnapshot"] = str(journal.directory / "pre.json")
        try:
            if post is None and config["action"] != "context":
                # A failed prepare with an old project loaded must retain only
                # the name guard; never walk that project's pool or timelines.
                if project is None and config["action"] == "prepare":
                    manager = _required(journal, resolve, "GetProjectManager")
                    candidate = _required(journal, manager, "GetCurrentProject")
                    if candidate is not None:
                        candidate_name = _getter(journal, candidate, "GetName")[1]
                        if (
                            candidate_name.get("status") == "ok"
                            and candidate_name.get("value") == PROJECT_NAME
                        ):
                            project = candidate
                        else:
                            result["postCapture"] = "skipped-old-project-guard"
                            raise StopIteration
                    else:
                        result["postCapture"] = "skipped-no-project"
                        raise StopIteration
                if project is None:
                    manager = _required(journal, resolve, "GetProjectManager")
                    project = _required(journal, manager, "GetCurrentProject")
                if project is not None:
                    post = _capture(journal, resolve, project, "post-partial")
                    result["partialState"] = _state(post)
        except StopIteration:
            pass
        except Exception as capture_error:
            result["postCaptureError"] = _error(capture_error)
        journal.write("harness", "failure", result)
        return result
    finally:
        journal.write("harness", "finished", {"status": result.get("status")})
