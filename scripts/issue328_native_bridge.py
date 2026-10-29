"""Cut-only synthetic native bridge for the bounded #328 proof."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict, cast

SCHEMA = "vera-issue-328-native-command/v1"
SOURCE_REVISION = "issue328-public-synthetic-v1"
PROJECT_PREFIX = "VERA_328_"
SETTINGS = {
    "timelineFrameRate": "24",
    "timelineResolutionWidth": "640",
    "timelineResolutionHeight": "360",
}


class NativeChange(TypedDict):
    id: str
    kind: str
    sourceId: str
    recordFrame: int
    durationFrames: int


CHANGES: tuple[NativeChange, NativeChange] = (
    {
        "id": "append-blue",
        "kind": "cut",
        "sourceId": "blue",
        "recordFrame": 24,
        "durationFrames": 24,
    },
    {
        "id": "append-red",
        "kind": "cut",
        "sourceId": "red",
        "recordFrame": 48,
        "durationFrames": 24,
    },
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _fingerprint(geometry: list[dict[str, Any]]) -> str:
    return _sha256(_canonical(geometry).encode("utf-8"))


def _string(value: Any, label: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{label} is missing")
    return value


def _integer(value: Any, label: str) -> int:
    _require(type(value) in {int, float}, f"{label} must be a whole frame")
    if type(value) is float:
        _require(
            math.isfinite(value) and value.is_integer(),
            f"{label} must be a whole frame",
        )
    return int(value)


def _request_integer(value: Any, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer")
    return int(value)


def _source_specs(value: Any) -> list[dict[str, Any]]:
    _require(
        type(value) is list and len(value) == 2,
        "exactly red and blue sources are required",
    )
    specs: dict[str, dict[str, Any]] = {}
    for item in value:
        _require(type(item) is dict, "source must be an object")
        _require(
            set(item) == {"id", "path", "sha256", "sourceInFrame", "durationFrames"},
            "source fields differ",
        )
        source_id = _string(item.get("id"), "source id")
        _require(
            source_id in {"red", "blue"} and source_id not in specs,
            "source id must be unique red or blue",
        )
        path = Path(_string(item.get("path"), f"{source_id} path"))
        _require(
            path.is_absolute() and path.is_file(),
            f"{source_id} path must be an existing absolute file",
        )
        digest = _string(item.get("sha256"), f"{source_id} sha256").lower()
        _require(
            re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            f"{source_id} sha256 is invalid",
        )
        _require(
            _request_integer(item.get("sourceInFrame"), f"{source_id} sourceInFrame")
            == 0,
            "source must begin at frame zero",
        )
        _require(
            _request_integer(item.get("durationFrames"), f"{source_id} durationFrames")
            == 24,
            "source must be 24 frames",
        )
        _require(
            _sha256(path.read_bytes()) == digest, f"{source_id} source bytes changed"
        )
        specs[source_id] = {
            "id": source_id,
            "path": str(path.resolve()),
            "sha256": digest,
            "sourceInFrame": 0,
            "durationFrames": 24,
        }
    _require(set(specs) == {"red", "blue"}, "source ids must be red and blue")
    return [specs[source_id] for source_id in ("red", "blue")]


def _props(item: Any) -> dict[str, Any]:
    props = item.GetClipProperty()
    if type(props) is not dict:
        raise ValueError("media properties are unreadable")
    return cast(dict[str, Any], props)


def _validate_media_format(props: dict[str, Any], source_id: str) -> None:
    fps = props.get("FPS")
    try:
        fps_value = float(str(fps).strip())
    except (TypeError, ValueError):
        fps_value = -1
    _require(fps_value == 24, f"{source_id} media is not 24 fps")
    resolution = props.get("Resolution")
    dimensions = re.findall(r"\d+", str(resolution))
    if len(dimensions) < 2:
        dimensions = [str(props.get("Width", "")), str(props.get("Height", ""))]
    _require(dimensions[:2] == ["640", "360"], f"{source_id} media is not 640x360")
    duration = props.get("Duration")
    if type(duration) is not str:
        raise ValueError(f"{source_id} duration is unreadable")
    parts = duration.split(":")
    _require(
        len(parts) == 4 and all(part.isdigit() for part in parts),
        f"{source_id} duration is not frame timecode",
    )
    hours, minutes, seconds, frames = (int(part) for part in parts)
    _require(
        ((hours * 3600 + minutes * 60 + seconds) * 24 + frames) == 24,
        f"{source_id} media is not 24 frames",
    )


def _pool_items(project: Any, expected: list[dict[str, Any]]) -> dict[str, Any]:
    pool = project.GetMediaPool()
    _require(pool is not None, "project media pool is missing")
    root = pool.GetRootFolder()
    _require(root is not None, "project root media folder is missing")
    clips = root.GetClipList()
    _require(type(clips) in {list, tuple}, "root media inventory is unreadable")
    timeline_pool_uids: set[str] = set()
    for timeline in _timeline_rows(project):
        timeline_media = timeline.GetMediaPoolItem()
        _require(
            timeline_media is not None, "timeline media-pool identity is unreadable"
        )
        uid = _string(timeline_media.GetUniqueId(), "timeline media-pool id")
        _require(
            uid not in timeline_pool_uids, "duplicate timeline media-pool identity"
        )
        timeline_pool_uids.add(uid)
    expected_paths = {str(Path(source["path"]).resolve()) for source in expected}
    result: dict[str, Any] = {}
    timeline_seen: set[str] = set()
    source_paths: set[str] = set()
    for item in clips:
        uid = _string(item.GetUniqueId(), "media-pool item id")
        if uid in timeline_pool_uids:
            _require(uid not in timeline_seen, "duplicate timeline media-pool entry")
            timeline_seen.add(uid)
            continue
        props = _props(item)
        path = props.get("File Path")
        if type(path) is not str:
            raise ValueError("unexpected media-pool item")
        path = str(Path(path).resolve())
        _require(path in expected_paths, "unexpected media-pool source")
        _require(path not in source_paths, "duplicate media-pool source")
        source_paths.add(path)
        media_id = _string(item.GetMediaId(), "media id")
        _require(media_id not in result, "duplicate media identity")
        result[media_id] = item
    _require(
        timeline_seen == timeline_pool_uids, "timeline media-pool entries are missing"
    )
    _require(source_paths == expected_paths, "media-pool source inventory changed")
    return result


def _source_readback(project: Any, expected: list[dict[str, Any]]) -> dict[str, Any]:
    media_by_id = _pool_items(project, expected)
    _require(len(media_by_id) == len(expected), "media pool contents changed")
    rows: list[dict[str, Any]] = []
    by_source: dict[str, Any] = {}
    seen_ids: set[str] = set()
    for source in expected:
        source_id = source["id"]
        path = Path(source["path"]).resolve()
        _require(
            path.is_file() and _sha256(path.read_bytes()) == source["sha256"],
            f"{source_id} source bytes changed",
        )
        matches = []
        for media in media_by_id.values():
            props = _props(media)
            observed_path = props.get("File Path")
            if type(observed_path) is str and Path(observed_path).resolve() == path:
                matches.append((media, props))
        _require(
            len(matches) == 1,
            f"{source_id} media pool identity is missing or ambiguous",
        )
        media, props = matches[0]
        media_id = _string(media.GetMediaId(), f"{source_id} media id")
        media_uid = _string(media.GetUniqueId(), f"{source_id} media unique id")
        if "mediaId" in source:
            _require(media_id == source["mediaId"], f"{source_id} media id changed")
        if "mediaUid" in source:
            _require(
                media_uid == source["mediaUid"], f"{source_id} media unique id changed"
            )
        _require(media_id not in seen_ids, "source media identity is duplicated")
        seen_ids.add(media_id)
        _validate_media_format(props, source_id)
        rows.append(
            {
                "id": source_id,
                "mediaId": media_id,
                "mediaUid": media_uid,
                "sha256": source["sha256"],
                "sourceInFrame": source["sourceInFrame"],
                "durationFrames": source["durationFrames"],
            }
        )
        by_source[source_id] = media
    _require(seen_ids == set(media_by_id), "unexpected media pool identity")
    return {"bySource": by_source, "rows": rows}


def _project_settings(project: Any) -> None:
    for name, expected in SETTINGS.items():
        _require(
            str(project.GetSetting(name)) == expected, f"project setting {name} differs"
        )


def _timeline_rows(project: Any) -> list[Any]:
    count = _integer(project.GetTimelineCount(), "timeline count")
    if count < 0:
        raise ValueError("timeline count is invalid")
    timelines: list[Any] = []
    ids: set[str] = set()
    for index in range(1, count + 1):
        timeline = project.GetTimelineByIndex(index)
        if timeline is None:
            raise ValueError("timeline inventory is incomplete")
        uid = _string(timeline.GetUniqueId(), "timeline id")
        _require(uid not in ids, "duplicate timeline identity")
        ids.add(uid)
        timelines.append(timeline)
    return timelines


def _timeline(project: Any, uid: str, name: str) -> Any:
    matches = [
        item
        for item in _timeline_rows(project)
        if item.GetUniqueId() == uid and item.GetName() == name
    ]
    if len(matches) != 1:
        raise ValueError(f"timeline identity changed: {name}")
    _require(
        matches[0].GetStartFrame() == 0,
        f"timeline does not start at frame zero: {name}",
    )
    return matches[0]


def _set_current(project: Any, timeline: Any) -> None:
    _require(
        project.SetCurrentTimeline(timeline) is True,
        "Resolve refused timeline selection",
    )
    current = project.GetCurrentTimeline()
    _require(
        current is not None and current.GetUniqueId() == timeline.GetUniqueId(),
        "current timeline selection did not stick",
    )


def _geometry(
    project: Any, timeline: Any, media_by_source: dict[str, Any]
) -> list[dict[str, Any]]:
    _require(
        project.GetCurrentTimeline() is not None
        and project.GetCurrentTimeline().GetUniqueId() == timeline.GetUniqueId(),
        "timeline must be selected before active readback",
    )
    rows: list[dict[str, Any]] = []
    item_ids: set[str] = set()
    for track_kind in ("video", "audio"):
        count = _integer(
            timeline.GetTrackCount(track_kind), f"{track_kind} track count"
        )
        _require(count >= 0, f"{track_kind} track count is invalid")
        for track_index in range(1, count + 1):
            items = timeline.GetItemListInTrack(track_kind, track_index)
            _require(
                type(items) in {list, tuple},
                f"{track_kind} track {track_index} readback is unavailable",
            )
            for item in items:
                item_uid = _string(item.GetUniqueId(), "timeline item id")
                _require(item_uid not in item_ids, "duplicate timeline item identity")
                item_ids.add(item_uid)
                media = item.GetMediaPoolItem()
                _require(media is not None, "timeline item source is unavailable")
                media_id = _string(media.GetMediaId(), "timeline source media id")
                source_matches = [
                    source_id
                    for source_id, value in media_by_source.items()
                    if value.GetMediaId() == media_id
                ]
                _require(
                    len(source_matches) == 1, "timeline item has an unexpected source"
                )
                source_id = source_matches[0]
                record_frame = _integer(item.GetStart(False), "record start")
                duration = _integer(item.GetDuration(False), "record duration")
                record_end = _integer(item.GetEnd(False), "record end")
                source_start = _integer(item.GetSourceStartFrame(), "source start")
                source_end = _integer(item.GetSourceEndFrame(), "source end")
                left_offset = _integer(item.GetLeftOffset(), "source left offset")
                _require(
                    duration > 0 and record_frame >= 0, "timeline range is invalid"
                )
                _require(
                    record_end - record_frame in {duration, duration - 1},
                    "record end and duration disagree",
                )
                _require(
                    source_start == 0 and source_end - source_start + 1 == duration,
                    "source bounds differ from the admitted 24-frame range",
                )
                _require(left_offset == 0, "source left offset differs from frame zero")
                rows.append(
                    {
                        "trackKind": track_kind,
                        "trackIndex": track_index,
                        "sourceId": source_id,
                        "sourceInFrame": source_start,
                        "recordFrame": record_frame,
                        "durationFrames": duration,
                    }
                )
    rows.sort(
        key=lambda row: (
            row["trackKind"],
            row["trackIndex"],
            row["recordFrame"],
            row["sourceId"],
        )
    )
    return rows


def _expected_geometry(session: dict[str, Any], applied: int) -> list[dict[str, Any]]:
    baseline = session.get("originalGeometry")
    if type(baseline) is not list:
        raise ValueError("session original geometry changed")
    rows = cast(list[dict[str, Any]], baseline)
    _require(
        rows
        == [
            {
                "trackKind": "video",
                "trackIndex": 1,
                "sourceId": "red",
                "sourceInFrame": 0,
                "recordFrame": 0,
                "durationFrames": 24,
            }
        ],
        "session original geometry changed",
    )
    rows = list(rows)
    rows.extend(
        {
            "trackKind": "video",
            "trackIndex": 1,
            "sourceId": change["sourceId"],
            "sourceInFrame": 0,
            "recordFrame": change["recordFrame"],
            "durationFrames": change["durationFrames"],
        }
        for change in CHANGES[:applied]
    )
    return sorted(
        rows,
        key=lambda row: (
            row["trackKind"],
            row["trackIndex"],
            row["recordFrame"],
            row["sourceId"],
        ),
    )


def _prefix(session: dict[str, Any], geometry: list[dict[str, Any]]) -> int | None:
    for count in range(len(CHANGES) + 1):
        if geometry == _expected_geometry(session, count):
            return count
    return None


def _source_string(session: dict[str, Any], readback: dict[str, Any]) -> str:
    return _canonical(
        {"revision": session["sourceRevision"], "sources": readback["rows"]}
    )


def _observation(
    session: dict[str, Any], geometry: list[dict[str, Any]], readback: dict[str, Any]
) -> dict[str, str]:
    target = f"{session['projectUid']}:{session['targetUid']}"
    return {
        "source": _source_string(session, readback),
        "target": target,
        "fingerprint": _fingerprint(geometry),
    }


def _session(value: Any) -> dict[str, Any]:
    _require(type(value) is dict, "session is missing")
    required = {
        "projectUid",
        "projectName",
        "originalUid",
        "originalName",
        "targetUid",
        "targetName",
        "sourceRevision",
        "sources",
        "originalGeometry",
        "operationDir",
    }
    _require(set(value) == required, "session fields differ")
    _require(
        _string(value.get("projectName"), "project name").startswith(PROJECT_PREFIX),
        "project is outside the #328 namespace",
    )
    for key in ("projectUid", "originalUid", "targetUid", "originalName", "targetName"):
        _string(value.get(key), key)
    _require(value["sourceRevision"] == SOURCE_REVISION, "source revision changed")
    _require(
        value["originalUid"] != value["targetUid"],
        "original and target timeline identities collide",
    )
    _require(
        type(value["sources"]) is list
        and [item.get("id") for item in value["sources"]] == ["red", "blue"],
        "session sources changed",
    )
    for source in value["sources"]:
        _request_integer(source.get("sourceInFrame"), "session sourceInFrame")
        _request_integer(source.get("durationFrames"), "session durationFrames")
    operation_dir = Path(_string(value.get("operationDir"), "operation directory"))
    _require(
        operation_dir.is_absolute()
        and operation_dir.is_dir()
        and not operation_dir.is_symlink(),
        "operation directory is unavailable",
    )
    for source in value["sources"]:
        source_path = Path(source["path"]).resolve()
        _require(
            operation_dir.resolve() not in source_path.parents
            and source_path not in operation_dir.resolve().parents,
            "operation directory overlaps a source",
        )
    _expected_geometry(value, 0)
    return cast(dict[str, Any], value)


def _plan_hash(value: Any) -> str:
    plan = _string(value, "plan sha256").lower()
    _require(re.fullmatch(r"[0-9a-f]{64}", plan) is not None, "plan sha256 is invalid")
    return plan


def _journal_paths(
    session: dict[str, Any], plan: str, change_id: str
) -> tuple[Path, Path]:
    root = Path(session["operationDir"]).resolve()
    _require(root.is_dir() and not root.is_symlink(), "operation directory changed")
    for source in session["sources"]:
        source_path = Path(source["path"]).resolve()
        _require(
            root not in source_path.parents and source_path not in root.parents,
            "operation directory overlaps a source",
        )
    stem = f"{plan}-{change_id}"
    return root / f"{stem}.started.json", root / f"{stem}.finished.json"


def _read_journal(path: Path) -> dict[str, Any] | None:
    if not path.exists() and not path.is_symlink():
        return None
    _require(
        path.is_file() and not path.is_symlink(),
        "native attempt record is not a regular file",
    )
    _require(path.stat().st_mode & 0o077 == 0, "native attempt record is not private")
    raw = path.read_text(encoding="utf-8")
    value = json.loads(raw)
    if type(value) is not dict or _canonical(value) + "\n" != raw:
        raise ValueError("native attempt record is malformed")
    return cast(dict[str, Any], value)


def _write_journal(path: Path, value: dict[str, Any]) -> None:
    payload = (_canonical(value) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _change(value: Any) -> tuple[int, NativeChange]:
    _require(
        type(value) is dict
        and set(value) == {"id", "kind", "sourceId", "recordFrame", "durationFrames"},
        "change fields differ",
    )
    _require(value.get("kind") == "cut", "only cut changes are supported")
    _request_integer(value.get("recordFrame"), "change recordFrame")
    _request_integer(value.get("durationFrames"), "change durationFrames")
    value = cast(NativeChange, value)
    for index, expected in enumerate(CHANGES):
        if value == expected:
            return index, expected
    raise ValueError("change is outside the fixed two-append plan")


def _guard(
    resolve: Any, session: dict[str, Any]
) -> tuple[Any, Any, Any, Any, dict[str, Any]]:
    manager = resolve.GetProjectManager()
    project = manager.GetCurrentProject()
    _require(project is not None, "no current project")
    _require(
        project.IsRenderingInProgress() is False,
        "Resolve is rendering or render state is unknown",
    )
    _require(
        project.GetUniqueId() == session["projectUid"]
        and project.GetName() == session["projectName"],
        "current project identity changed",
    )
    _project_settings(project)
    timelines = _timeline_rows(project)
    _require(
        {item.GetUniqueId() for item in timelines}
        == {session["originalUid"], session["targetUid"]},
        "project timeline inventory changed",
    )
    original = _timeline(project, session["originalUid"], session["originalName"])
    target = _timeline(project, session["targetUid"], session["targetName"])
    current = project.GetCurrentTimeline()
    _require(
        current is not None and current.GetUniqueId() == session["originalUid"],
        "original timeline must be current at command start",
    )
    readback = _source_readback(project, session["sources"])
    original_geometry = _geometry(project, original, readback["bySource"])
    _require(
        original_geometry == session["originalGeometry"], "original timeline changed"
    )
    return manager, project, original, target, readback


def _restore_original(
    project: Any,
    original: Any,
    media_by_source: dict[str, Any],
    baseline: list[dict[str, Any]],
) -> None:
    _set_current(project, original)
    _require(
        _geometry(project, original, media_by_source) == baseline,
        "original timeline changed during command",
    )


def _with_target[WorkResult](
    resolve: Any,
    session: dict[str, Any],
    work: Callable[[Any, Any, dict[str, Any], list[dict[str, Any]]], WorkResult],
) -> WorkResult:
    _manager, project, original, target, readback = _guard(resolve, session)
    try:
        _set_current(project, target)
        geometry = _geometry(project, target, readback["bySource"])
        return work(project, target, readback, geometry)
    finally:
        _restore_original(
            project, original, readback["bySource"], session["originalGeometry"]
        )


def _connect() -> Any:
    default_module = Path(
        "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/"
        "Scripting/Modules/DaVinciResolveScript.py"
    )
    if default_module.is_file() and str(default_module.parent) not in sys.path:
        sys.path.insert(0, str(default_module.parent))
    dvr = importlib.import_module("DaVinciResolveScript")
    scriptapp = getattr(dvr, "scriptapp", None)
    if not callable(scriptapp):
        raise ValueError("Resolve scripting module has no scriptapp")
    resolve = scriptapp("Resolve")
    if resolve is None:
        raise ValueError("Resolve scripting connection is unavailable")
    return resolve


def _setup(request: dict[str, Any], resolve: Any) -> dict[str, Any]:
    operation_id = _string(request.get("operationId"), "operation id")
    _require(
        re.fullmatch(r"[0-9a-fA-F-]{36}", operation_id) is not None,
        "operation id is invalid",
    )
    project_name = _string(request.get("projectName"), "project name")
    _require(
        re.fullmatch(r"VERA_328_[0-9a-f]{8}", project_name) is not None,
        "project name is outside the unique #328 namespace",
    )
    _require(
        request.get("sourceRevision") == SOURCE_REVISION,
        "source revision is unsupported",
    )
    operation_dir = Path(_string(request.get("operationDir"), "operation directory"))
    _require(
        operation_dir.is_absolute()
        and operation_dir.is_dir()
        and not operation_dir.is_symlink(),
        "operation directory is unavailable",
    )
    sources = _source_specs(request.get("sources"))
    for source in sources:
        source_path = Path(source["path"]).resolve()
        _require(
            operation_dir.resolve() not in source_path.parents
            and source_path not in operation_dir.resolve().parents,
            "operation directory overlaps a source",
        )
    manager = resolve.GetProjectManager()
    prior = manager.GetCurrentProject()
    _require(
        prior is None or prior.IsRenderingInProgress() is False,
        "prior project is rendering or render state is unknown",
    )
    names = manager.GetProjectListInCurrentFolder()
    _require(
        type(names) in {list, tuple} and project_name not in names,
        "project name already exists or inventory is unreadable",
    )
    project = manager.CreateProject(project_name)
    _require(project is not None, "Resolve could not create the unique #328 project")
    _require(project.GetName() == project_name, "created project name differs")
    for name, value in SETTINGS.items():
        _require(project.SetSetting(name, value) is True, f"could not set {name}")
    _project_settings(project)
    pool = project.GetMediaPool()
    _require(pool is not None, "created project has no media pool")
    imported = pool.ImportMedia([source["path"] for source in sources])
    _require(
        type(imported) in {list, tuple} and len(imported) == 2,
        "ImportMedia did not return both synthetic sources",
    )
    readback = _source_readback(project, sources)
    original_name = project_name + "_ORIGINAL"
    target_name = project_name + "_TARGET"
    original = pool.CreateEmptyTimeline(original_name)
    _require(
        original is not None and original.GetName() == original_name,
        "could not create the original timeline",
    )
    _require(
        original.SetStartTimecode("00:00:00:00") is True
        and original.GetStartFrame() == 0,
        "original timeline does not start at frame zero",
    )
    _require(
        original.GetTrackCount("video") == 1,
        "original timeline must have one video track",
    )
    _set_current(project, original)
    red = readback["bySource"]["red"]
    placed = pool.AppendToTimeline(
        [
            {
                "mediaPoolItem": red,
                "startFrame": 0,
                "endFrame": 23,
                "recordFrame": 0,
                "trackIndex": 1,
                "mediaType": 1,
            }
        ]
    )
    _require(
        type(placed) in {list, tuple} and len(placed) == 1,
        "original red occurrence did not append once",
    )
    original_geometry = _geometry(project, original, readback["bySource"])
    _require(
        original_geometry
        == [
            {
                "trackKind": "video",
                "trackIndex": 1,
                "sourceId": "red",
                "sourceInFrame": 0,
                "recordFrame": 0,
                "durationFrames": 24,
            }
        ],
        "original timeline is not one exact 24-frame red video occurrence",
    )
    target = original.DuplicateTimeline(target_name)
    _require(
        target is not None and target.GetUniqueId() != original.GetUniqueId(),
        "DuplicateTimeline did not create an independent target",
    )
    _set_current(project, original)
    _require(
        target.GetName() == target_name,
        "duplicated target name differs",
    )
    _require(len(_timeline_rows(project)) == 2, "setup created an unexpected timeline")
    _set_current(project, target)
    try:
        target_geometry = _geometry(project, target, readback["bySource"])
    finally:
        _restore_original(project, original, readback["bySource"], original_geometry)
    _require(
        target_geometry == original_geometry,
        "duplicate target differs from original baseline",
    )
    _require(
        not any(row["trackKind"] == "audio" for row in target_geometry),
        "target contains audio",
    )
    session: dict[str, Any] = {
        "projectUid": _string(project.GetUniqueId(), "project id"),
        "projectName": project_name,
        "originalUid": _string(original.GetUniqueId(), "original timeline id"),
        "originalName": original_name,
        "targetUid": _string(target.GetUniqueId(), "target timeline id"),
        "targetName": target_name,
        "sourceRevision": SOURCE_REVISION,
        "operationDir": str(operation_dir.resolve()),
        "sources": [
            {
                **source,
                "mediaId": _string(
                    readback["bySource"][source["id"]].GetMediaId(),
                    f"{source['id']} media id",
                ),
                "mediaUid": _string(
                    readback["bySource"][source["id"]].GetUniqueId(),
                    f"{source['id']} media uid",
                ),
            }
            for source in sources
        ],
        "originalGeometry": original_geometry,
    }
    session = _session(session)
    readback = _source_readback(project, session["sources"])
    return {
        "session": session,
        "observation": _observation(session, target_geometry, readback),
    }


def _apply(
    resolve: Any, session: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    plan = _plan_hash(request.get("planSha256"))
    index, change = _change(request.get("change"))
    current_fingerprint = _string(
        request.get("currentTargetFingerprint"), "current target fingerprint"
    )
    before_geometry = _expected_geometry(session, index)
    after_geometry = _expected_geometry(session, index + 1)
    before_fingerprint = _fingerprint(before_geometry)

    def work(
        project: Any,
        target: Any,
        readback: dict[str, Any],
        current: list[dict[str, Any]],
    ) -> dict[str, Any]:
        _require(
            current == before_geometry and _fingerprint(current) == current_fingerprint,
            "apply requires the exact known-before target geometry",
        )
        started_path, finished_path = _journal_paths(session, plan, change["id"])
        _require(
            _read_journal(started_path) is None
            and _read_journal(finished_path) is None,
            "native change already has an attempt record; reconcile before retry",
        )
        _write_journal(
            started_path,
            {
                "schemaVersion": "vera-issue-328-native-attempt/v1",
                "plan": plan,
                "change": change["id"],
                "target": f"{session['projectUid']}:{session['targetUid']}",
                "before": before_fingerprint,
                "after": _fingerprint(after_geometry),
            },
        )
        pool = project.GetMediaPool()
        media = readback["bySource"][change["sourceId"]]
        placed = pool.AppendToTimeline(
            [
                {
                    "mediaPoolItem": media,
                    "startFrame": 0,
                    "endFrame": change["durationFrames"] - 1,
                    "recordFrame": change["recordFrame"],
                    "trackIndex": 1,
                    "mediaType": 1,
                }
            ]
        )
        _require(
            type(placed) in {list, tuple} and len(placed) == 1,
            "AppendToTimeline did not return exactly one video item",
        )
        after = _geometry(project, target, readback["bySource"])
        _require(
            after == after_geometry,
            "AppendToTimeline readback differs from the exact expected append",
        )
        receipt = {
            "plan": plan,
            "change": change["id"],
            "target": f"{session['projectUid']}:{session['targetUid']}",
            "before": before_fingerprint,
            "after": _fingerprint(after),
        }
        _write_journal(
            finished_path,
            {"schemaVersion": "vera-issue-328-native-result/v1", **receipt},
        )
        return {"receipt": receipt}

    return _with_target(resolve, session, work)


def _receipt(
    value: Any, plan: str, session: dict[str, Any], index: int
) -> dict[str, str]:
    _require(
        type(value) is dict
        and set(value) == {"plan", "change", "target", "before", "after"},
        "receipt fields differ",
    )
    receipt = {
        key: _string(value.get(key), f"receipt {key}")
        for key in ("plan", "change", "target", "before", "after")
    }
    expected_before = _fingerprint(_expected_geometry(session, index))
    expected_after = _fingerprint(_expected_geometry(session, index + 1))
    _require(
        receipt
        == {
            "plan": plan,
            "change": CHANGES[index]["id"],
            "target": f"{session['projectUid']}:{session['targetUid']}",
            "before": expected_before,
            "after": expected_after,
        },
        "receipt is not bound to this exact planned geometry",
    )
    return receipt


def _verify(
    resolve: Any, session: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    plan = _plan_hash(request.get("planSha256"))
    index, _change_value = _change(request.get("change"))
    receipt = _receipt(request.get("receipt"), plan, session, index)

    def work(
        _project: Any,
        _target: Any,
        _readback: dict[str, Any],
        current: list[dict[str, Any]],
    ) -> dict[str, Any]:
        started_path, finished_path = _journal_paths(
            session, plan, CHANGES[index]["id"]
        )
        started, finished = _read_journal(started_path), _read_journal(finished_path)
        expected_started = {
            "schemaVersion": "vera-issue-328-native-attempt/v1",
            "plan": plan,
            "change": CHANGES[index]["id"],
            "target": receipt["target"],
            "before": receipt["before"],
            "after": receipt["after"],
        }
        expected_finished = {
            "schemaVersion": "vera-issue-328-native-result/v1",
            **receipt,
        }
        if started != expected_started or finished != expected_finished:
            return {"verified": False}
        prefix = _prefix(session, current)
        return {
            "verified": prefix is not None
            and prefix >= index + 1
            and receipt["after"] == _fingerprint(_expected_geometry(session, index + 1))
        }

    return _with_target(resolve, session, work)


def _reconcile(
    resolve: Any, session: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    plan = _plan_hash(request.get("planSha256"))
    index, change = _change(request.get("change"))
    current_fingerprint = _string(
        request.get("currentTargetFingerprint"), "current target fingerprint"
    )
    before = _fingerprint(_expected_geometry(session, index))
    after = _fingerprint(_expected_geometry(session, index + 1))

    def work(
        _project: Any,
        _target: Any,
        _readback: dict[str, Any],
        current: list[dict[str, Any]],
    ) -> dict[str, Any]:
        started_path, finished_path = _journal_paths(session, plan, change["id"])
        try:
            started, finished = (
                _read_journal(started_path),
                _read_journal(finished_path),
            )
        except (OSError, ValueError, json.JSONDecodeError):
            return {"reconciliation": "unknown"}
        expected_started = {
            "schemaVersion": "vera-issue-328-native-attempt/v1",
            "plan": plan,
            "change": change["id"],
            "target": f"{session['projectUid']}:{session['targetUid']}",
            "before": before,
            "after": after,
        }
        expected_finished = {
            "schemaVersion": "vera-issue-328-native-result/v1",
            "plan": plan,
            "change": change["id"],
            "target": f"{session['projectUid']}:{session['targetUid']}",
            "before": before,
            "after": after,
        }
        if (
            started is None
            and finished is None
            and current == _expected_geometry(session, index)
            and current_fingerprint == before
        ):
            return {"reconciliation": "not-applied"}
        prefix = _prefix(session, current)
        if (
            started == expected_started
            and finished == expected_finished
            and current_fingerprint == before
            and prefix is not None
            and prefix >= index + 1
        ):
            return {
                "reconciliation": {
                    "plan": plan,
                    "change": change["id"],
                    "target": f"{session['projectUid']}:{session['targetUid']}",
                    "before": before,
                    "after": after,
                }
            }
        return {"reconciliation": "unknown"}

    _manager, project, original, target, readback = _guard(resolve, session)
    try:
        try:
            _set_current(project, target)
            current = _geometry(project, target, readback["bySource"])
        except Exception:
            return {"reconciliation": "unknown"}
        return work(project, target, readback, current)
    finally:
        _restore_original(
            project,
            original,
            readback["bySource"],
            session["originalGeometry"],
        )


def _reopen(resolve: Any, session: dict[str, Any]) -> dict[str, Any]:
    manager, project, original, target, readback = _guard(resolve, session)
    try:
        _set_current(project, target)
        before_target = _geometry(project, target, readback["bySource"])
        _require(
            _prefix(session, before_target) is not None,
            "target geometry is not a known append prefix",
        )
        _set_current(project, original)
        _require(manager.SaveProject() is True, "SaveProject failed")
        _require(manager.CloseProject(project) is True, "CloseProject failed")
        reopened = manager.LoadProject(session["projectName"])
        _require(reopened is not None, "LoadProject failed")
        _require(
            reopened.GetUniqueId() == session["projectUid"]
            and reopened.GetName() == session["projectName"],
            "reopened project identity changed",
        )
        _project_settings(reopened)
        timelines = _timeline_rows(reopened)
        _require(
            {item.GetUniqueId() for item in timelines}
            == {session["originalUid"], session["targetUid"]},
            "reopened timeline identities changed",
        )
        reopened_original = _timeline(
            reopened, session["originalUid"], session["originalName"]
        )
        reopened_target = _timeline(
            reopened, session["targetUid"], session["targetName"]
        )
        reopened_sources = _source_readback(reopened, session["sources"])
        _require(
            {
                row["id"]: (row["mediaId"], row["mediaUid"])
                for row in reopened_sources["rows"]
            }
            == {
                source["id"]: (source["mediaId"], source["mediaUid"])
                for source in session["sources"]
            },
            "reopened media identities changed",
        )
        _set_current(reopened, reopened_original)
        original_geometry = _geometry(
            reopened, reopened_original, reopened_sources["bySource"]
        )
        _require(
            original_geometry == session["originalGeometry"],
            "reopened original timeline changed",
        )
        _set_current(reopened, reopened_target)
        target_geometry = _geometry(
            reopened, reopened_target, reopened_sources["bySource"]
        )
        _require(
            target_geometry == before_target
            and _prefix(session, target_geometry) is not None,
            "reopened target geometry changed",
        )
        _set_current(reopened, reopened_original)
        _require(
            reopened.GetCurrentTimeline().GetUniqueId() == session["originalUid"],
            "original timeline is not current after reopen",
        )
        return {
            "verified": True,
            "observation": _observation(session, target_geometry, reopened_sources),
            "originalUnchanged": True,
            "originalCurrent": True,
        }
    except BaseException:
        current_project = manager.GetCurrentProject()
        if (
            current_project is not None
            and current_project.GetUniqueId() == session["projectUid"]
        ):
            try:
                current_original = _timeline(
                    current_project, session["originalUid"], session["originalName"]
                )
                _set_current(current_project, current_original)
            except Exception:
                pass
        raise


def handle_command(request: Any, resolve: Any | None = None) -> dict[str, Any]:
    _require(
        type(request) is dict and request.get("schemaVersion") == SCHEMA,
        "unsupported command schema",
    )
    action = _string(request.get("action"), "action")
    resolve = resolve if resolve is not None else _connect()
    if action == "setup":
        return _setup(request, resolve)
    session = _session(request.get("session"))
    if action == "observe":

        def observe(
            _project: Any,
            _target: Any,
            readback: dict[str, Any],
            geometry: list[dict[str, Any]],
        ) -> dict[str, Any]:
            _require(
                _prefix(session, geometry) is not None,
                "target contains unexpected geometry",
            )
            return {"observation": _observation(session, geometry, readback)}

        return _with_target(resolve, session, observe)
    if action == "apply":
        return _apply(resolve, session, request)
    if action == "verify":
        return _verify(resolve, session, request)
    if action == "reconcile":
        return _reconcile(resolve, session, request)
    if action == "reopen":
        _plan_hash(request.get("planSha256"))
        return _reopen(resolve, session)
    raise ValueError("unsupported native bridge action")


def main() -> None:
    try:
        request = json.loads(sys.stdin.read())
        result = handle_command(request)
        sys.stdout.write(_canonical(result) + "\n")
    except Exception as error:
        sys.stderr.write(f"{type(error).__name__}: {error}\n")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
