"""Bounded injected #326 music probe; never a production delivery adapter."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import time
from pathlib import Path
from typing import Any

PRODUCT = "DaVinci Resolve Studio"
VERSION = "21.1.1.10"
PROJECT_PREFIX = "VERA326_MUSIC_"
SIDECAR_SCHEMA = "issue326-music-probe/v1"
MAX_RENDER_FRAMES = 240  # Ten seconds at the pinned 24 fps project rate.
MIN_FREE_BYTES = 40 * 1024**3
RENDER_TIMEOUT_SECONDS = 45
_TERMINAL_JOBS = {"Complete", "Failed", "Cancelled"}


class ProbeFailure(ValueError):
    """A refusal after a native mutation attempt, with the calls retained."""

    def __init__(self, message: str, native_mutation_attempts: list[str]) -> None:
        super().__init__(message)
        self.native_mutation_attempts = list(native_mutation_attempts)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_value(value: Any, label: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{label} is not a SHA-256 digest")
    raw = value.removeprefix("sha256:")
    if len(raw) != 64 or any(c not in "0123456789abcdef" for c in raw.lower()):
        raise ValueError(f"{label} is not a SHA-256 digest")
    return raw.lower()


def _absolute_file(value: Any, label: str) -> Path:
    if type(value) is not str:
        raise ValueError(f"{label} path is missing")
    path = Path(value)
    if not path.is_absolute() or not path.is_file():
        raise ValueError(f"{label} is not an existing absolute file")
    return path


def _pinned_file(path_value: Any, hash_value: Any, label: str) -> Path:
    path = _absolute_file(path_value, label)
    if _sha256(path) != _hash_value(hash_value, label):
        raise ValueError(f"{label} bytes changed")
    return path


def _attempt(
    attempts: list[str], label: str, target: Any, method: str, *args: Any
) -> Any:
    attempts.append(f"{label}.{method}")
    return getattr(target, method)(*args)


def _context(resolve: Any, request: dict[str, Any]) -> tuple[Any, Any, Any]:
    for key in ("action", "operationId", "projectName", "projectId"):
        if type(request.get(key)) is not str or not request[key]:
            raise ValueError(f"request is missing {key}")
    operation_id = request["operationId"]
    if len(operation_id) > 80 or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in operation_id
    ):
        raise ValueError("invalid operation identifier")
    if resolve.GetProductName() != PRODUCT or resolve.GetVersionString() != VERSION:
        raise ValueError("Resolve product/build is outside the qualified probe runtime")
    manager = resolve.GetProjectManager()
    project = manager.GetCurrentProject()
    if project is None or project.GetName() != request["projectName"]:
        raise ValueError("current project is not the issue-owned disposable target")
    if not project.GetName().startswith(PROJECT_PREFIX):
        raise ValueError("target project is outside the issue namespace")
    if project.GetUniqueId() != request["projectId"]:
        raise ValueError("project identity changed")
    return manager, project, resolve


def _timeline_inventory(project: Any) -> list[dict[str, str]]:
    count = project.GetTimelineCount()
    if type(count) is not int or count < 0:
        raise ValueError("timeline count is unreadable")
    rows: list[dict[str, str]] = []
    ids: set[str] = set()
    names: set[str] = set()
    for index in range(1, count + 1):
        timeline = project.GetTimelineByIndex(index)
        uid, name = timeline.GetUniqueId(), timeline.GetName()
        if type(uid) is not str or not uid or type(name) is not str or not name:
            raise ValueError("existing timeline identity is unreadable")
        if uid in ids or name in names:
            raise ValueError("existing project contains duplicate timeline identities")
        ids.add(uid)
        names.add(name)
        rows.append({"timelineId": uid, "timelineName": name})
    return rows


def _sidecar(request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    sidecar_path = _pinned_file(
        request.get("sidecarPath"), request.get("sidecarSha256"), "sidecar"
    )
    try:
        payload = json.loads(sidecar_path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("pinned sidecar is unreadable JSON") from error
    if type(payload) is not dict:
        raise ValueError("pinned sidecar root is not an object")
    if payload.get("schemaVersion") != SIDECAR_SCHEMA:
        raise ValueError("sidecar schema is outside the #326 probe")
    if payload.get("evidenceLevel") != "probe_only":
        raise ValueError("sidecar is not marked probe-only")
    if request.get("caseId") not in (None, payload.get("caseId")):
        raise ValueError("request case does not match the pinned sidecar")
    if (
        type(payload.get("base")) is not dict
        or type(payload.get("base", {}).get("verification")) is not dict
    ):
        raise ValueError("sidecar does not pin a verified base package")
    base = payload["base"]
    snapshot = payload.get("authoringSnapshot")
    effective_snapshot = payload.get("effectiveAuthoringSnapshot")
    manifest = base.get("manifest")
    base_otio = base.get("otio")
    derived = payload.get("derivedOtio")
    music = payload.get("music")
    if any(
        type(row) is not dict
        for row in (snapshot, effective_snapshot, manifest, base_otio, derived, music)
    ):
        raise ValueError("sidecar is missing pinned source, manifest, or OTIO records")

    otio_path = _pinned_file(
        request.get("otioPath"), request.get("otioSha256"), "derived OTIO"
    )
    if str(otio_path) != derived.get("path") or _hash_value(
        request.get("otioSha256"), "derived OTIO"
    ) != _hash_value(derived.get("sha256"), "sidecar derived OTIO"):
        raise ValueError("request OTIO does not match the sidecar-derived timeline")

    required: dict[str, str] = {
        str(sidecar_path): _sha256(sidecar_path),
        str(otio_path): _hash_value(derived.get("sha256"), "sidecar derived OTIO"),
    }
    for row, hash_key, label in (
        (snapshot, "rawSha256", "authoring snapshot"),
        (effective_snapshot, "rawSha256", "effective authoring snapshot"),
        (manifest, "sha256", "base manifest"),
        (base_otio, "sha256", "base OTIO"),
    ):
        path = _pinned_file(row.get("path"), row.get(hash_key), label)
        required[str(path)] = _hash_value(row[hash_key], label)

    package_root_value = base.get("packageRoot")
    if (
        type(package_root_value) is not str
        or not Path(package_root_value).is_absolute()
        or not Path(package_root_value).is_dir()
    ):
        raise ValueError("base package root is not an absolute directory")
    verification_files = base["verification"].get("fileHashes")
    if type(verification_files) is not dict or not verification_files:
        raise ValueError("base package verification has no file inventory")
    package_root = Path(package_root_value)
    for relative, digest in verification_files.items():
        if type(relative) is not str or not relative:
            raise ValueError("base package verification path is invalid")
        path = (package_root / relative).resolve()
        if not path.is_relative_to(package_root.resolve()):
            raise ValueError("base package verification path escapes its package")
        pinned = _pinned_file(str(path), digest, "base package")
        required[str(pinned)] = _hash_value(digest, "base package")

    expected = (
        music.get("expectedNative", {}).get("events")
        if type(music.get("expectedNative")) is dict
        else None
    )
    if type(expected) is not list or not expected:
        raise ValueError("sidecar has no native event expectation")
    music_events = [
        row for row in expected if type(row) is dict and row.get("kind") == "music"
    ]
    if len(music_events) != 1:
        raise ValueError("sidecar must identify exactly one music occurrence")
    event_ids: set[str] = set()
    for row in expected:
        if type(row) is not dict:
            raise ValueError("native event expectation is malformed")
        event_id = row.get("eventId")
        if type(event_id) is not str or not event_id or event_id in event_ids:
            raise ValueError("native event identifiers are missing or duplicated")
        event_ids.add(event_id)
        if row.get("kind") not in {"narration", "placeholder", "music"}:
            raise ValueError("native event kind is not qualified")
        if row.get("trackKind") not in {"audio", "video"}:
            raise ValueError("native event track kind is invalid")
        if (
            type(row.get("sourcePath")) is not str
            or not Path(row["sourcePath"]).is_absolute()
        ):
            raise ValueError(f"native event {event_id} has no absolute source path")
        for key in (
            "trackIndex",
            "sourceInFrame",
            "recordStartFrame",
            "durationFrames",
        ):
            if type(row.get(key)) is not int:
                raise ValueError(f"native event {event_id} has invalid {key}")
        if (
            row["trackIndex"] < 1
            or row["sourceInFrame"] < 0
            or row["recordStartFrame"] < 0
            or row["durationFrames"] <= 0
        ):
            raise ValueError(f"native event {event_id} has an invalid extent")
        if (
            row["kind"] == "placeholder"
            and Path(row["sourcePath"]).suffix.lower() == ".png"
            and row["sourceInFrame"] != 0
        ):
            raise ValueError("PNG placeholder must begin at its single source frame")
        if row.get("kind") == "music" and (row["trackKind"], row["trackIndex"]) != (
            "audio",
            2,
        ):
            raise ValueError(
                "music occurrence is not bound to the expected A2 audio track"
            )
        source = _pinned_file(
            row.get("sourcePath"), row.get("sourceSha256"), f"source for {event_id}"
        )
        required[str(source)] = _hash_value(
            row["sourceSha256"], f"source for {event_id}"
        )

    music_event = music_events[0]
    source_record = music.get("source")
    range_samples = music.get("sourceRangeSamples")
    record_range = music.get("recordRange")
    fade = music.get("fade")
    if any(
        type(row) is not dict
        for row in (source_record, range_samples, record_range, fade)
    ):
        raise ValueError("music source, record range, or fade is malformed")
    if (
        source_record.get("path") != music_event["sourcePath"]
        or _hash_value(source_record.get("sha256"), "music source")
        != _hash_value(music_event["sourceSha256"], "music event source")
        or music.get("gainDb") != -12
        or fade.get("curve") != "linear"
        or fade.get("fadeInFrames") != 6
        or fade.get("fadeOutFrames") != 6
    ):
        raise ValueError(
            "music sidecar does not match the qualified gain/fade/source profile"
        )
    music_source = _pinned_file(
        source_record.get("path"), source_record.get("sha256"), "music source"
    )
    required[str(music_source)] = _hash_value(source_record["sha256"], "music source")
    if music.get("sourcePath") != source_record.get("path") or _hash_value(
        music.get("sourceSha256"), "music source"
    ) != _hash_value(source_record.get("sha256"), "music source"):
        raise ValueError("top-level music source does not match its pinned identity")
    start_sample, end_sample = (
        range_samples.get("startSample"),
        range_samples.get("endSample"),
    )
    if (
        type(start_sample) is not int
        or type(end_sample) is not int
        or end_sample <= start_sample
    ):
        raise ValueError("music source sample range is invalid")
    duration = music_event["durationFrames"]
    if (
        start_sample != music.get("sourceTrimSamples")
        or start_sample != music_event["sourceInFrame"] * 2000
        or end_sample - start_sample != duration * 2000
        or record_range.get("startFrame") != music_event["recordStartFrame"]
        or record_range.get("durationFrames") != duration
        or record_range.get("endFrame") != music_event["recordStartFrame"] + duration
        or music.get("recordStartFrame") != music_event["recordStartFrame"]
        or music.get("recordEndFrame") != music_event["recordStartFrame"] + duration
        or music.get("durationFrames") != duration
    ):
        raise ValueError(
            "music source and record extents do not match the 24 fps event"
        )
    timeline = payload.get("timeline")
    if (
        type(timeline) is not dict
        or timeline.get("frameRate") != {"numerator": 24, "denominator": 1}
        or timeline.get("audioSampleRate") != 48000
        or max(row["recordStartFrame"] + row["durationFrames"] for row in expected)
        > MAX_RENDER_FRAMES
    ):
        raise ValueError(
            "sidecar timeline is outside the bounded 24 fps / ten-second probe"
        )

    inventory = request.get("fileInventory")
    if inventory is not None:
        if type(inventory) is not list:
            raise ValueError("fileInventory must be a list")
        pinned: dict[str, str] = {}
        for row in inventory:
            if type(row) is not dict:
                raise ValueError("fileInventory row is malformed")
            path = _absolute_file(row.get("path"), "inventory")
            digest = _hash_value(row.get("sha256"), f"inventory {path}")
            if str(path) in pinned:
                raise ValueError("fileInventory contains a duplicate path")
            if _sha256(path) != digest:
                raise ValueError(f"fileInventory bytes changed: {path}")
            pinned[str(path)] = digest
        if any(pinned.get(path) != digest for path, digest in required.items()):
            raise ValueError(
                "fileInventory omits or changes a sidecar-referenced input"
            )
    return payload, {
        "sidecarPath": str(sidecar_path),
        "sidecarSha256": _sha256(sidecar_path),
        "otioPath": str(otio_path),
        "otioSha256": _sha256(otio_path),
        "verifiedFiles": [
            {"path": path, "sha256": "sha256:" + digest}
            for path, digest in sorted(required.items())
        ],
    }


def _frame(value: Any, label: str) -> int:
    if type(value) is int:
        return value
    if type(value) is float and math.isfinite(value) and value.is_integer():
        return int(value)
    raise ValueError(f"{label} is not an exact frame value")


def _seconds_frame(value: Any, label: str) -> int:
    if (
        type(value) not in {int, float}
        or type(value) is bool
        or not math.isfinite(value)
    ):
        raise ValueError(f"{label} is not a finite source time")
    frames = value * 24
    nearest = round(frames)
    if not math.isclose(frames, nearest, rel_tol=0.0, abs_tol=1e-6):
        raise ValueError(f"{label} is off the 24 fps source grid")
    return int(nearest)


def _expected_source_duration(event: dict[str, Any]) -> int:
    explicit = event.get("sourceDurationFrames")
    if explicit is not None:
        if type(explicit) is not int or explicit <= 0:
            raise ValueError(
                f"native event {event['eventId']} has an invalid source duration"
            )
        return explicit
    if (
        event["kind"] == "placeholder"
        and Path(event["sourcePath"]).suffix.lower() == ".png"
    ):
        return 1
    return event["durationFrames"]


def _file_path(item: Any, event_id: str) -> str:
    media = item.GetMediaPoolItem()
    properties = media.GetClipProperty()
    path = properties.get("File Path") if type(properties) is dict else None
    if (
        type(path) is not str
        or not Path(path).is_absolute()
        or not Path(path).is_file()
    ):
        raise ValueError(f"native event {event_id} has no absolute source path")
    return str(Path(path))


def _readback(
    project: Any, timeline: Any, sidecar: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = sidecar["music"]["expectedNative"]["events"]
    actual: list[dict[str, Any]] = []
    hash_cache: dict[str, str] = {}
    for kind in ("audio", "video"):
        count = timeline.GetTrackCount(kind)
        if type(count) is not int or count < 0:
            raise ValueError(f"{kind} track count is unreadable")
        for index in range(1, count + 1):
            items = timeline.GetItemListInTrack(kind, index)
            if type(items) not in {list, tuple}:
                raise ValueError(f"{kind} track {index} items are unreadable")
            for item in items:
                uid = item.GetUniqueId()
                if type(uid) is not str or not uid:
                    raise ValueError("timeline event identity is unreadable")
                raw_source_start = item.GetSourceStartFrame()
                raw_source_end = item.GetSourceEndFrame()
                source_start_time = item.GetSourceStartTime()
                source_end_time = item.GetSourceEndTime()
                source_start = _seconds_frame(source_start_time, f"{uid} source start")
                source_end = _seconds_frame(source_end_time, f"{uid} source end")
                record_start = _frame(item.GetStart(), f"{uid} record start")
                native_record_end = _frame(item.GetEnd(), f"{uid} record end")
                record_duration = _frame(item.GetDuration(), f"{uid} record duration")
                record_end = record_start + record_duration
                if native_record_end != record_end:
                    raise ValueError(f"{uid} record end and duration disagree")
                source_path = _file_path(item, uid)
                if source_path not in hash_cache:
                    hash_cache[source_path] = _sha256(Path(source_path))
                source_hash = hash_cache[source_path]
                row: dict[str, Any] = {
                    "timelineItemId": uid,
                    "trackKind": kind,
                    "trackIndex": index,
                    "sourcePath": source_path,
                    "sourceInFrame": source_start,
                    "sourceOutFrame": source_end,
                    "nativeSourceStartFrame": raw_source_start,
                    "nativeSourceEndFrame": raw_source_end,
                    "sourceStartTimeSeconds": source_start_time,
                    "sourceEndTimeSeconds": source_end_time,
                    "recordStartFrame": record_start,
                    "recordEndFrame": record_end,
                    "durationFrames": record_end - record_start,
                    "sourceSha256": "sha256:" + source_hash,
                }
                if kind == "audio":
                    clip_enabled_getter = getattr(item, "GetClipEnabled", None)
                    if not callable(clip_enabled_getter):
                        expected = next(
                            (
                                event
                                for event in sidecar["music"]["expectedNative"][
                                    "events"
                                ]
                                if event["eventId"] == uid
                            ),
                            None,
                        )
                        if expected is not None and expected["kind"] == "music":
                            raise ValueError(
                                "Resolve music occurrence enable control is unavailable"
                            )
                        raise ValueError(
                            f"audio event {uid} enable state is unreadable"
                        )
                    clip_enabled = clip_enabled_getter()
                    if type(clip_enabled) is not bool:
                        raise ValueError(
                            f"audio event {uid} enable state is unreadable"
                        )
                    row["clipEnabled"] = clip_enabled
                    properties = item.GetProperties()
                    fades = item.GetFades()
                    if type(properties) is not dict or type(fades) is not dict:
                        raise ValueError(
                            f"audio event {uid} properties/fades are unreadable"
                        )
                    row["audioProperties"] = {
                        key: properties.get(key)
                        for key in ("AudioVolumeEnabled", "AudioVolume")
                        if key in properties
                    }
                    row["fades"] = dict(fades)
                actual.append(row)

    unmatched = list(actual)
    matched: list[dict[str, Any]] = []
    handles: dict[str, Any] = {}
    for item in expected:
        source_path = str(Path(item["sourcePath"]))
        expected_key = (
            item["trackKind"],
            item["trackIndex"],
            source_path,
            item["sourceSha256"],
            item["sourceInFrame"],
            item["recordStartFrame"],
            item["durationFrames"],
        )
        candidates = [
            row
            for row in unmatched
            if (
                row["trackKind"],
                row["trackIndex"],
                row["sourcePath"],
                row["sourceSha256"],
                row["sourceInFrame"],
                row["recordStartFrame"],
                row["durationFrames"],
            )
            == expected_key
            and row["sourceOutFrame"]
            == item["sourceInFrame"] + _expected_source_duration(item)
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"native event geometry/source mismatch for {item['eventId']}"
            )
        row = candidates[0]
        unmatched.remove(row)
        row["eventId"] = item["eventId"]
        matched.append(row)
        if item["trackKind"] == "audio":
            current = timeline.GetItemListInTrack("audio", item["trackIndex"])
            handles[item["eventId"]] = next(
                entry
                for entry in current
                if entry.GetUniqueId() == row["timelineItemId"]
            )
    if unmatched or len(matched) != len(expected):
        raise ValueError("native timeline contains unexpected or missing events")
    matched.sort(
        key=lambda row: (
            row["trackKind"],
            row["trackIndex"],
            row["recordStartFrame"],
            row["eventId"],
        )
    )
    music_row = next(
        row
        for row in matched
        if row["eventId"]
        == next(item["eventId"] for item in expected if item["kind"] == "music")
    )
    narration_ids = {
        item["eventId"] for item in expected if item["kind"] == "narration"
    }
    return {
        "timelineName": timeline.GetName(),
        "timelineId": timeline.GetUniqueId(),
        "events": matched,
        "narration": [row for row in matched if row["eventId"] in narration_ids],
        "musicEventId": music_row["eventId"],
    }, handles


def _diagnostic_readback(
    project: Any, timeline: Any, sidecar: dict[str, Any]
) -> dict[str, Any]:
    """Return raw native getters so an API convention can be qualified explicitly."""
    tracks: dict[str, int] = {}
    events: list[dict[str, Any]] = []
    track_enable_getter = getattr(timeline, "GetIsTrackEnabled", None)
    for kind in ("audio", "video"):
        count = timeline.GetTrackCount(kind)
        if type(count) is not int or count < 0:
            raise ValueError(f"{kind} track count is unreadable")
        tracks[kind] = count
        for index in range(1, count + 1):
            items = timeline.GetItemListInTrack(kind, index)
            if type(items) not in {list, tuple}:
                raise ValueError(f"{kind} track {index} items are unreadable")
            for item in items:
                uid = item.GetUniqueId()
                media = item.GetMediaPoolItem()
                clip_properties = media.GetClipProperty()
                source_path = (
                    clip_properties.get("File Path")
                    if type(clip_properties) is dict
                    else None
                )
                getters: dict[str, Any] = {}
                for name, args in (
                    ("GetSourceStartFrame", ()),
                    ("GetSourceEndFrame", ()),
                    ("GetSourceStartTime", ()),
                    ("GetSourceEndTime", ()),
                    ("GetStart", ()),
                    ("GetEnd", ()),
                    ("GetDuration", ()),
                    ("GetStart", (True,)),
                    ("GetEnd", (True,)),
                ):
                    key = name if not args else f"{name}(True)"
                    try:
                        getters[key] = getattr(item, name)(*args)
                    except Exception as error:
                        getters[key] = {"error": f"{type(error).__name__}: {error}"}
                row: dict[str, Any] = {
                    "timelineItemId": uid,
                    "trackKind": kind,
                    "trackIndex": index,
                    "clipProperties": clip_properties,
                    "getters": getters,
                }
                if type(source_path) is str and Path(source_path).is_file():
                    row["sourcePath"] = source_path
                    row["sourceSha256"] = "sha256:" + _sha256(Path(source_path))
                if kind == "audio":
                    try:
                        row["clipEnabled"] = item.GetClipEnabled()
                    except Exception as error:
                        row["clipEnabledError"] = (
                            f"{type(error).__name__}: {error}"
                        )
                    try:
                        row["audioProperties"] = item.GetProperties()
                    except Exception as error:
                        row["audioPropertiesError"] = f"{type(error).__name__}: {error}"
                    try:
                        row["fades"] = item.GetFades()
                    except Exception as error:
                        row["fadesError"] = f"{type(error).__name__}: {error}"
                events.append(row)
    track_enable_states: list[dict[str, Any]] = []
    if callable(track_enable_getter):
        for index in range(1, tracks.get("audio", 0) + 1):
            try:
                value = track_enable_getter("audio", index)
                track_enable_states.append({"trackIndex": index, "value": value})
            except Exception as error:
                track_enable_states.append(
                    {
                        "trackIndex": index,
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
    return {
        "status": "diagnostic_readback",
        "timelineId": timeline.GetUniqueId(),
        "timelineName": timeline.GetName(),
        "trackCounts": tracks,
        "trackEnableControl": {
            "getterAvailable": callable(track_enable_getter),
            "setterAvailable": callable(getattr(timeline, "SetTrackEnable", None)),
            "audioTracks": track_enable_states,
        },
        "expectedEvents": sidecar["music"]["expectedNative"]["events"],
        "events": events,
    }


def _timeline(project: Any, request: dict[str, Any]) -> Any:
    timeline_id = request.get("timelineId")
    if type(timeline_id) is not str or not timeline_id:
        raise ValueError("request is missing timelineId")
    rows = _timeline_inventory(project)
    matches = [row for row in rows if row["timelineId"] == timeline_id]
    if len(matches) != 1:
        raise ValueError("pinned timeline identity is absent or duplicated")
    if request.get("timelineName") not in (None, matches[0]["timelineName"]):
        raise ValueError("pinned timeline name changed")
    for index in range(1, project.GetTimelineCount() + 1):
        timeline = project.GetTimelineByIndex(index)
        if timeline.GetUniqueId() == timeline_id:
            return timeline
    raise ValueError("pinned timeline disappeared")


def _same_narration(before: dict[str, Any], after: dict[str, Any]) -> None:
    if before["narration"] != after["narration"]:
        raise ValueError("narration source, extent, gain, fade, or identity changed")


def _import(
    resolve: Any,
    project: Any,
    request: dict[str, Any],
    sidecar: dict[str, Any],
    pins: dict[str, Any],
    attempts: list[str],
) -> dict[str, Any]:
    name = request.get("timelineName")
    if type(name) is not str or not name.startswith(PROJECT_PREFIX):
        raise ValueError("new timeline name must use the issue-owned namespace")
    before = _timeline_inventory(project)
    if any(row["timelineName"] == name for row in before):
        raise ValueError("target timeline name already exists; refusing collision")
    pool = project.GetMediaPool()
    imported = _attempt(
        attempts,
        "mediaPool",
        pool,
        "ImportTimelineFromFile",
        request["otioPath"],
        {"timelineName": name, "importSourceClips": True},
    )
    if imported is None:
        raise ValueError("Resolve returned no imported timeline")
    after = _timeline_inventory(project)
    old_ids = {row["timelineId"] for row in before}
    new_rows = [row for row in after if row["timelineId"] not in old_ids]
    if (
        len(after) != len(before) + 1
        or not old_ids.issubset({row["timelineId"] for row in after})
        or len(new_rows) != 1
        or new_rows[0]["timelineName"] != name
        or imported.GetUniqueId() != new_rows[0]["timelineId"]
    ):
        return {
            "evidenceLevel": "probe_only",
            "status": "import_topology_mismatch",
            "operationId": request["operationId"],
            "projectName": project.GetName(),
            "projectId": project.GetUniqueId(),
            "importedTimelineId": imported.GetUniqueId(),
            "timelineInventory": after,
            "inputs": pins,
        }
    try:
        evidence, _ = _readback(project, imported, sidecar)
    except Exception as error:
        return {
            "evidenceLevel": "probe_only",
            "status": "import_readback_mismatch",
            "operationId": request["operationId"],
            "projectName": project.GetName(),
            "projectId": project.GetUniqueId(),
            "timelineName": name,
            "timelineId": imported.GetUniqueId(),
            "readbackError": str(error),
            "timelineInventory": after,
            "inputs": pins,
        }
    return {
        "evidenceLevel": "probe_only",
        "status": "imported",
        "operationId": request["operationId"],
        "projectName": project.GetName(),
        "projectId": project.GetUniqueId(),
        "timelineName": name,
        "timelineId": imported.GetUniqueId(),
        "inputs": pins,
        "readback": evidence,
    }


def _configure(
    project: Any, request: dict[str, Any], sidecar: dict[str, Any], attempts: list[str]
) -> dict[str, Any]:
    timeline = _timeline(project, request)
    before, handles = _readback(project, timeline, sidecar)
    music_id = before["musicEventId"]
    item = handles.get(music_id)
    if item is None:
        raise ValueError("sidecar music occurrence is not a bound audio item")
    music_before = next(row for row in before["events"] if row["eventId"] == music_id)
    old_properties = dict(music_before["audioProperties"])
    if set(old_properties) != {"AudioVolumeEnabled", "AudioVolume"}:
        raise ValueError("music gain properties are not fully readable")
    current_gain = old_properties["AudioVolume"]
    if type(current_gain) not in {int, float} or type(current_gain) is bool:
        raise ValueError("music gain readback is not numeric")
    invalid_gain = next(
        value for value in (0.0, -24.0, -36.0, 6.0) if value != current_gain
    )
    try:
        rejected = _attempt(
            attempts,
            "musicItem",
            item,
            "SetProperties",
            {"AudioVolume": invalid_gain, "VERA326InvalidProbeProperty": 1},
        )
    except Exception:
        rejected = False
    after_invalid = item.GetProperties()
    unchanged = (
        type(after_invalid) is dict
        and after_invalid.get("AudioVolumeEnabled")
        == old_properties["AudioVolumeEnabled"]
        and after_invalid.get("AudioVolume") == old_properties["AudioVolume"]
    )
    if rejected is not False or not unchanged:
        raise ValueError("SetProperties invalid-key probe was not atomic")
    gain = sidecar["music"]["gainDb"]
    applied = _attempt(
        attempts,
        "musicItem",
        item,
        "SetProperties",
        {"AudioVolumeEnabled": True, "AudioVolume": gain},
    )
    if applied is not True:
        raise ValueError("Resolve refused the valid audio gain properties")
    fade = sidecar["music"]["fade"]
    fade_values = {"FadeIn": fade["fadeInFrames"], "FadeOut": fade["fadeOutFrames"]}
    fade_applied = _attempt(attempts, "musicItem", item, "SetFades", fade_values)
    if fade_applied is not True:
        raise ValueError("Resolve refused the valid music fades")
    after, _ = _readback(project, timeline, sidecar)
    _same_narration(before, after)
    music_after = next(row for row in after["events"] if row["eventId"] == music_id)
    if (
        music_after["audioProperties"].get("AudioVolumeEnabled") is not True
        or music_after["audioProperties"].get("AudioVolume") != gain
        or music_after["fades"].get("FadeIn") != fade_values["FadeIn"]
        or music_after["fades"].get("FadeOut") != fade_values["FadeOut"]
    ):
        raise ValueError("music gain/fade readback does not match the pinned request")
    for before_row, after_row in zip(before["events"], after["events"], strict=True):
        if before_row["eventId"] != music_id and {
            key: before_row[key]
            for key in (
                "sourcePath",
                "sourceSha256",
                "sourceInFrame",
                "sourceOutFrame",
                "recordStartFrame",
                "recordEndFrame",
                "durationFrames",
            )
        } != {
            key: after_row[key]
            for key in (
                "sourcePath",
                "sourceSha256",
                "sourceInFrame",
                "sourceOutFrame",
                "recordStartFrame",
                "recordEndFrame",
                "durationFrames",
            )
        }:
            raise ValueError(
                "non-music event source or extent changed during configuration"
            )
    return {
        "evidenceLevel": "probe_only",
        "status": "configured",
        "operationId": request["operationId"],
        "timelineId": timeline.GetUniqueId(),
        "atomicInvalidKey": {
            "returnedFalse": rejected is False,
            "unchanged": unchanged,
        },
        "gain": music_after["audioProperties"],
        "fades": music_after["fades"],
        "narrationBefore": before["narration"],
        "narrationAfter": after["narration"],
        "readback": after,
    }


def _save_reopen(
    manager: Any,
    project: Any,
    request: dict[str, Any],
    sidecar: dict[str, Any],
    attempts: list[str],
) -> dict[str, Any]:
    timeline = _timeline(project, request)
    before, _ = _readback(project, timeline, sidecar)
    project_id, project_name = project.GetUniqueId(), project.GetName()
    saved = _attempt(attempts, "projectManager", manager, "SaveProject")
    if saved is not True:
        raise ValueError("Resolve did not confirm SaveProject")
    closed = _attempt(attempts, "projectManager", manager, "CloseProject", project)
    if closed is not True:
        raise ValueError("Resolve did not confirm CloseProject")
    loaded = _attempt(attempts, "projectManager", manager, "LoadProject", project_name)
    current = manager.GetCurrentProject()
    if loaded is None or current is None or current.GetUniqueId() != project_id:
        raise ValueError("Resolve did not reopen the same project identity")
    reopened = _timeline(current, request)
    after, _ = _readback(current, reopened, sidecar)
    if before["events"] != after["events"]:
        raise ValueError(
            "timeline event source, extent, gain, or fade changed after reopen"
        )
    _same_narration(before, after)
    return {
        "evidenceLevel": "probe_only",
        "status": "reopened",
        "operationId": request["operationId"],
        "projectId": current.GetUniqueId(),
        "timelineId": reopened.GetUniqueId(),
        "narrationBefore": before["narration"],
        "narrationAfter": after["narration"],
        "readback": after,
    }


def _job_id(row: Any) -> str | None:
    if type(row) is not dict:
        return None
    value = row.get("JobId", row.get("jobId"))
    return value if type(value) is str and value else None


def _render(
    resolve: Any,
    project: Any,
    request: dict[str, Any],
    sidecar: dict[str, Any],
    attempts: list[str],
) -> dict[str, Any]:
    timeline = _timeline(project, request)
    before, handles = _readback(project, timeline, sidecar)
    include_music = request.get("includeMusic")
    if type(include_music) is not bool:
        raise ValueError("render request must say whether music is included")
    music_id = before["musicEventId"]
    music_event = next(row for row in before["events"] if row["eventId"] == music_id)
    track_index = music_event["trackIndex"]
    music_item = handles.get(music_id)
    if music_item is None:
        raise ValueError("bound music occurrence is not available for the render")
    clip_enabled_getter = getattr(music_item, "GetClipEnabled", None)
    clip_enabled_setter = getattr(music_item, "SetClipEnabled", None)
    if not callable(clip_enabled_getter) or not callable(clip_enabled_setter):
        raise ValueError("Resolve music occurrence enable control is unavailable")
    original_clip_enabled = clip_enabled_getter()
    if type(original_clip_enabled) is not bool or original_clip_enabled is not True:
        raise ValueError("bound music occurrence is not enabled before the render")

    render_dir = request.get("renderDirectory")
    if type(render_dir) is not str or not Path(render_dir).is_absolute():
        raise ValueError("renderDirectory must be an absolute new directory")
    output_dir = Path(render_dir)
    if output_dir.name != request["operationId"] or output_dir.exists():
        raise ValueError("render directory must be new and named for this operation")
    if not output_dir.parent.is_dir():
        raise ValueError("render directory parent must already exist")
    if shutil.disk_usage(output_dir.parent).free < MIN_FREE_BYTES:
        raise ValueError("render refused because less than 40 GiB remains free")
    bit_depth = request.get("bitDepth", 16)
    if type(bit_depth) is not int or bit_depth not in (16, 24):
        raise ValueError("audio WAV render bit depth must be 16 or 24")
    formats = project.GetAudioRenderFormats()
    codecs = project.GetAudioRenderCodecs("wav")
    if type(formats) is not dict or "wav" not in formats.values():
        raise ValueError("Resolve does not report WAV in its audio render formats")
    if type(codecs) is not dict or "lpcm" not in codecs.values():
        raise ValueError("Resolve does not report Linear PCM for WAV")
    if project.IsRenderingInProgress() is not False:
        raise ValueError("Resolve already has a render in progress")
    prior_jobs = project.GetRenderJobList()
    if type(prior_jobs) not in {list, tuple}:
        raise ValueError("render queue is unreadable")
    prior_ids = {_job_id(row) for row in prior_jobs}
    if None in prior_ids:
        raise ValueError("existing render job identity is unreadable")
    retained_ready_jobs: list[dict[str, Any]] = []
    for job_id in prior_ids:
        status = project.GetRenderJobStatus(job_id)
        if type(status) is not dict:
            raise ValueError("existing render job status is unreadable")
        if status.get("JobStatus") in _TERMINAL_JOBS:
            continue
        old_job = next(row for row in prior_jobs if _job_id(row) == job_id)
        old_target = Path(str(old_job.get("TargetDir", ""))).resolve()
        owned_ready_wav = (
            status.get("JobStatus") == "Ready"
            and old_job.get("TimelineName") == timeline.GetName()
            and old_job.get("IsExportVideo") is False
            and old_job.get("IsExportAudio") is True
            and old_target.parent == output_dir.parent.resolve()
            and str(old_job.get("OutputFilename", "")).startswith(
                f"vera326-{sidecar['caseId']}-"
            )
            and str(old_job.get("OutputFilename", "")).endswith(".wav")
        )
        if not owned_ready_wav:
            raise ValueError("an existing render job is not terminal")
        retained_ready_jobs.append({"job": old_job, "status": status})

    current_format = project.GetCurrentRenderFormatAndCodec()
    current_mode = project.GetCurrentRenderMode()
    preset_name = f"VERA326_RESTORE_{request['operationId']}"
    presets = project.GetRenderPresetList()
    if type(presets) not in {list, tuple} or preset_name in presets:
        raise ValueError("unique render-settings recovery preset is unavailable")
    output_dir.mkdir(mode=0o700)
    render_label = "mixed" if include_music else "narration"
    custom_name = f"vera326-{sidecar['caseId']}-{render_label}-{request['operationId']}"
    output_path = output_dir / f"{custom_name}.wav"
    clip_disable_attempted = False
    clip_disable_return: Any = None
    clip_enabled_after_disable: Any = None
    clip_enabled_after_restore: Any = None
    preset_saved = False
    active = False
    job_id: str | None = None
    job: dict[str, Any] | None = None
    status: dict[str, Any] | None = None
    start_return: Any = None
    format_after_settings: Any = None
    mode_after_settings: Any = None
    failure: Exception | None = None
    evidence: dict[str, Any] = {}
    try:
        saved_preset = _attempt(
            attempts, "project", project, "SaveAsNewRenderPreset", preset_name
        )
        preset_saved = (
            saved_preset is True
            and project.GetRenderPresetList().count(preset_name) == 1
        )
        if not preset_saved:
            raise ValueError(
                "Resolve did not save the unique render-settings recovery preset"
            )
        if not include_music:
            clip_disable_attempted = True
            clip_disable_return = _attempt(
                attempts,
                "musicItem",
                music_item,
                "SetClipEnabled",
                False,
            )
            clip_enabled_after_disable = clip_enabled_getter()
            if clip_enabled_after_disable is not False:
                raise ValueError("music occurrence disable did not read back")
        settings = {
            "ExportVideo": False,
            "ExportAudio": True,
            "AudioFormat": "wav",
            "AudioCodec": "lpcm",
            "AudioSampleRate": 48000,
            "AudioBitDepth": bit_depth,
            "SelectAllFrames": True,
            "TargetDir": str(output_dir),
            "CustomName": custom_name,
        }
        applied = _attempt(attempts, "project", project, "SetRenderSettings", settings)
        if applied is not True:
            raise ValueError("Resolve refused bounded audio-only WAV settings")
        format_after_settings = project.GetCurrentRenderFormatAndCodec()
        mode_after_settings = project.GetCurrentRenderMode()
        job_id = _attempt(attempts, "project", project, "AddRenderJob")
        if type(job_id) is not str or not job_id:
            raise ValueError(
                "Resolve returned no new render job ID; queue was retained"
            )
        jobs = project.GetRenderJobList()
        new_ids = {_job_id(row) for row in jobs} - prior_ids
        if new_ids != {job_id}:
            raise ValueError("render queue did not add exactly the requested job")
        job = next(row for row in jobs if _job_id(row) == job_id)
        if (
            job.get("TimelineName") != timeline.GetName()
            or job.get("IsExportVideo") is not False
            or job.get("IsExportAudio") is not True
            or job.get("AudioSampleRate") != 48000
            or job.get("AudioBitDepth") != bit_depth
            or job.get("AudioCodec") != "lpcm"
            or job.get("TargetDir") != str(output_dir)
            or job.get("OutputFilename") != f"{custom_name}.wav"
        ):
            raise ValueError(
                "queued render job does not read back the bounded WAV profile"
            )
        if output_path.exists():
            raise ValueError("render output appeared before the exact job started")
        start_return = _attempt(
            attempts, "project", project, "StartRendering", [job_id], False
        )
        if start_return is not True:
            status = project.GetRenderJobStatus(job_id)
            raise ValueError(
                f"Resolve refused the exact new render job; status={status!r}"
            )
        deadline = time.monotonic() + RENDER_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            status = project.GetRenderJobStatus(job_id)
            if type(status) is not dict or type(status.get("JobStatus")) is not str:
                raise ValueError("render job status is unreadable")
            if status["JobStatus"] in _TERMINAL_JOBS:
                break
            time.sleep(0.25)
        else:
            active = project.IsRenderingInProgress() is True
            raise ValueError("exact WAV render did not finish within 45 seconds")
        if status is None or status.get("JobStatus") != "Complete":
            raise ValueError("exact WAV render ended without Complete status")
        active = project.IsRenderingInProgress() is True
        if active:
            raise ValueError("Resolve still reports rendering after job completion")
        if not output_path.is_file() or output_path.stat().st_size <= 44:
            raise ValueError("completed render has no non-empty WAV output")
        with output_path.open("rb") as stream:
            header = stream.read(12)
        if header[:4] not in {b"RIFF", b"RF64"} or header[8:12] != b"WAVE":
            raise ValueError("render output is not a WAV container")
        evidence = {
            "status": "rendered",
            "operationId": request["operationId"],
            "timelineId": timeline.GetUniqueId(),
            "includeMusic": include_music,
            "musicTrackIndex": track_index,
            "retainedReadyJobs": retained_ready_jobs,
            "currentRenderFormatAndCodecBefore": current_format,
            "currentRenderModeBefore": current_mode,
            "currentRenderFormatAndCodecAfterSettings": format_after_settings,
            "currentRenderModeAfterSettings": mode_after_settings,
            "musicClipEnabledBefore": original_clip_enabled,
            "musicClipDisableReturn": clip_disable_return,
            "musicClipEnabledAfterDisable": clip_enabled_after_disable,
            "musicClipEnabledAfterRender": None,
            "outputPath": str(output_path),
            "outputBytes": output_path.stat().st_size,
            "outputSha256": _sha256(output_path),
            "renderJobId": job_id,
            "renderJob": job,
            "renderJobStatus": status,
            "startRenderingReturn": start_return,
            "settings": settings,
            "restorePresetName": preset_name,
            "restorePresetRetained": True,
        }
    except Exception as error:
        failure = error
        active = active or project.IsRenderingInProgress() is True
        evidence = {
            "status": "failed",
            "operationId": request["operationId"],
            "includeMusic": include_music,
            "renderJobId": job_id,
            "renderJob": job,
            "renderJobStatus": status,
            "startRenderingReturn": start_return,
            "renderDirectory": str(output_dir),
            "retainedReadyJobs": retained_ready_jobs,
            "currentRenderFormatAndCodecBefore": current_format,
            "currentRenderModeBefore": current_mode,
            "currentRenderFormatAndCodecAfterSettings": format_after_settings,
            "currentRenderModeAfterSettings": mode_after_settings,
            "musicClipEnabledBefore": original_clip_enabled,
            "musicClipDisableReturn": clip_disable_return,
            "musicClipEnabledAfterDisable": clip_enabled_after_disable,
            "musicClipEnabledAfterRestore": clip_enabled_after_restore,
            "restorePresetName": preset_name if preset_saved else None,
            "error": str(error),
            "renderStillActive": active,
        }
    if not active:
        restore_errors: list[str] = []
        if clip_disable_attempted:
            try:
                _attempt(
                    attempts,
                    "musicItem",
                    music_item,
                    "SetClipEnabled",
                    original_clip_enabled,
                )
                clip_enabled_after_restore = clip_enabled_getter()
                if clip_enabled_after_restore is not original_clip_enabled:
                    raise ValueError("music occurrence enable state did not restore")
            except Exception as error:
                restore_errors.append(f"music occurrence restore failed: {error}")
        if restore_errors:
            failure = ValueError(
                "; ".join(restore_errors)
                + (f"; original failure: {failure}" if failure else "")
            )
        if failure is None:
            after, _ = _readback(project, timeline, sidecar)
            _same_narration(before, after)
            if before["events"] != after["events"]:
                failure = ValueError("timeline events changed during render/restore")
            elif clip_enabled_getter() is not original_clip_enabled:
                failure = ValueError(
                    "music occurrence enable state changed after render"
                )
            else:
                evidence["musicClipEnabledAfterRender"] = clip_enabled_getter()
                evidence["narrationBefore"] = before["narration"]
                evidence["narrationAfter"] = after["narration"]
                evidence["musicClipEnabledAfterRestore"] = clip_enabled_after_restore
    if failure is not None:
        if attempts:
            raise ProbeFailure(str(failure), attempts) from failure
        raise failure
    return evidence


def run(resolve: Any, request: dict[str, Any]) -> dict[str, Any]:
    """Execute exactly one hash-bound operation against the named test project."""
    attempts: list[str] = []
    try:
        manager, project, _ = _context(resolve, request)
        action = request["action"]
        if action == "inspect":
            timelines = _timeline_inventory(project)
            render_jobs = project.GetRenderJobList()
            render_job_statuses = []
            if type(render_jobs) in {list, tuple}:
                for row in render_jobs:
                    render_job_id = _job_id(row)
                    if render_job_id is not None:
                        render_job_statuses.append(
                            {
                                "jobId": render_job_id,
                                "status": project.GetRenderJobStatus(render_job_id),
                            }
                        )
            return {
                "evidenceLevel": "probe_only",
                "status": "inspected",
                "operationId": request["operationId"],
                "product": resolve.GetProductName(),
                "version": resolve.GetVersionString(),
                "projectName": project.GetName(),
                "projectId": project.GetUniqueId(),
                "timelines": timelines,
                "audioRenderFormats": project.GetAudioRenderFormats(),
                "audioRenderCodecsWav": project.GetAudioRenderCodecs("wav"),
                "currentRenderFormatAndCodec": project.GetCurrentRenderFormatAndCodec(),
                "currentRenderMode": project.GetCurrentRenderMode(),
                "rendering": project.IsRenderingInProgress(),
                "renderJobs": render_jobs,
                "renderJobStatuses": render_job_statuses,
            }
        if action not in {
            "import",
            "readback",
            "diagnose",
            "save_reopen",
            "configure",
            "render",
        }:
            raise ValueError("unsupported probe action")
        sidecar, pins = _sidecar(request)
        if action == "import":
            result = _import(resolve, project, request, sidecar, pins, attempts)
        else:
            timeline = _timeline(project, request)
            if action == "diagnose":
                result = {
                    "evidenceLevel": "probe_only",
                    "operationId": request["operationId"],
                    "inputs": pins,
                    **_diagnostic_readback(project, timeline, sidecar),
                }
            elif action == "readback":
                evidence, _ = _readback(project, timeline, sidecar)
                result = {
                    "evidenceLevel": "probe_only",
                    "status": "readback",
                    "operationId": request["operationId"],
                    "inputs": pins,
                    "readback": evidence,
                }
            elif action == "save_reopen":
                result = _save_reopen(manager, project, request, sidecar, attempts)
            elif action == "configure":
                result = _configure(project, request, sidecar, attempts)
            else:
                result = _render(resolve, project, request, sidecar, attempts)
        result["nativeMutationAttempts"] = attempts
        return result
    except ProbeFailure:
        raise
    except Exception as error:
        if attempts:
            raise ProbeFailure(str(error), attempts) from error
        raise
