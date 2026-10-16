"""Guarded readback of documented audio channel mapping getters."""

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

ACTION = "audio-mapping-readonly"
CASE = "R2-mapping"
MATRIX_UID = "29ae8331-b86e-4041-a548-960695cc7b24"
PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
BUILD = [21, 1, 0, 14, ""]
READER_SHA = "9b6977747a1f3decf957ead6134f10fc4f597bf9d0c3dc5c081b7bf2671879a4"
AV_SHA = "fcdb385cca504f8dac25665fef75ddc15c9f0f9cf8c55b1b8a6d591af8cb3fa1"
PROTECTED_UID = "be5f1584-f0c4-4dd9-988b-73f3167e77d1"
PROTECTED_NAME = "semi1b.mp4"


def _load(name, path, digest, probe):
    if path.is_symlink() or probe.sha256(path) != digest:
        raise RuntimeError(f"Pinned helper changed: {name}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse(raw):
    if raw is None or raw is False:
        return None, None
    if isinstance(raw, str):
        try:
            return json.loads(raw), None
        except (TypeError, ValueError) as error:
            return None, f"{type(error).__name__}: {error}"
    return None, "getter returned a non-string value"


def _occurrences(matrix):
    timeline = next(
        row for row in matrix["timelines"]
        if row.get("GetUniqueId", {}).get("value") == MATRIX_UID
    )
    result = {}
    for track in timeline.get("tracks", []):
        if track.get("type") != "audio":
            continue
        for item in track.get("items", []):
            uid = item.get("GetUniqueId", {}).get("value")
            media = item.get("GetMediaPoolItem", {})
            source_uid = media.get("GetUniqueId", {}).get("value")
            source_name = media.get("GetClipProperty", {}).get("value", {}).get("File Name")
            if source_uid == PROTECTED_UID or source_name == PROTECTED_NAME:
                raise RuntimeError("Protected source refused before mapping getter")
            if not uid or not source_uid or uid in result:
                raise RuntimeError("Audio occurrence identity is incomplete or duplicated")
            result[uid] = {
                "occurrenceUid": uid,
                "trackType": "audio",
                "trackIndex": track.get("index"),
                "enabled": item.get("GetClipEnabled"),
                "sourceUid": source_uid,
                "sourceName": source_name,
            }
    return result


def _collect(items, media_sources):
    rows = []
    seen_sources = set()
    for uid, binding in sorted(items.items()):
        occurrence = binding["object"]
        source = binding["sourceObject"]
        source_uid = binding["sourceUid"]
        row = {key: value for key, value in binding.items() if key not in {"object", "sourceObject"}}
        row["GetSourceAudioChannelMapping"] = _getter(occurrence, "GetSourceAudioChannelMapping")
        if source_uid not in seen_sources:
            row["GetAudioMapping"] = _getter(source, "GetAudioMapping")
            seen_sources.add(source_uid)
        rows.append(row)
    return rows


def _getter(obj, method):
    try:
        raw = getattr(obj, method)()
        parsed, parse_error = _parse(raw)
        return {"raw": raw, "parsed": parsed, "parseError": parse_error}
    except Exception as error:
        return {"raw": None, "parsed": None, "error": f"{type(error).__name__}: {error}"}


def _bind_objects(pinned, tracks):
    actual = {}
    for track_index, track_items in tracks:
        for item in track_items:
            uid = item.GetUniqueId()
            source = item.GetMediaPoolItem()
            source_uid = source.GetUniqueId() if source is not None else None
            source_name = source.GetName() if source is not None else None
            if uid not in pinned or source_uid != pinned[uid]["sourceUid"]:
                raise RuntimeError("Unexpected audio source refused before getter")
            if source_uid == PROTECTED_UID or source_name == PROTECTED_NAME:
                raise RuntimeError("Protected source refused before getter")
            actual[uid] = {
                **pinned[uid], "object": item, "sourceObject": source,
                "sourceUid": source_uid, "trackIndex": track_index,
            }
    if set(actual) != set(pinned):
        raise RuntimeError("Current audio occurrence set differs from checkpoint")
    return actual


def _context(resolve, config, identity, reader, probe):
    project = reader._context(resolve, config, identity, probe, MATRIX_UID)
    if (
        resolve.GetProductName() != "DaVinci Resolve Studio"
        or resolve.GetVersion() != BUILD
        or resolve.GetCurrentPage() != "edit"
        or project.GetCurrentTimeline().GetUniqueId() != MATRIX_UID
        or project.GetRenderJobList() != []
    ):
        raise RuntimeError("Exact current Matrix/project/build context required")
    timeline = project.GetCurrentTimeline()
    return project, timeline.GetCurrentTimecode()


def run(resolve, config, *, probe):
    here = Path(__file__).resolve().parent
    reader = _load("audio_mapping_reader", here / "r4-range-repair.py", READER_SHA, probe)
    av = _load("audio_mapping_av", here / "av-output.py", AV_SHA, probe)
    output = Path(config.get("outputDir", ""))
    if (
        config.get("action") != ACTION
        or config.get("case") != CASE
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or output.parent.resolve() != Path(probe.ROOT).resolve() / "out"
        or not output.is_dir()
    ):
        raise RuntimeError("Exact read-only audio mapping request required")
    identity = {"projectId": PROJECT_ID, "projectName": config["projectName"]}
    checkpoint = Path(config.get("mappingCheckpoint", ""))
    if not checkpoint.is_absolute() or checkpoint.resolve().parent != output.resolve():
        raise RuntimeError("Pinned mapping checkpoint must be directly inside outputDir")
    pin = reader._pin(
        checkpoint, checkpoint.name, config.get("mappingCheckpointSha256"), probe
    )
    baseline, _pool = reader._validate_read_pair(pin, probe)
    project, playhead = _context(resolve, config, identity, reader, probe)
    if project.GetUniqueId() != PROJECT_ID:
        raise RuntimeError("Exact Issue 141 project required")
    _, expected = reader._manifest(config, Path(probe.ROOT).resolve(), probe)
    before = reader._read_pair(resolve, config, identity, expected, MATRIX_UID, probe)
    current, _ = reader._validate_read_pair(before, probe)
    if current != baseline:
        raise RuntimeError("Fresh full pair differs from pinned Matrix checkpoint")
    if av._protected_source_in_matrix(current):
        raise RuntimeError("Protected source occurs in Matrix evidence")
    pinned = _occurrences(current)
    timeline = project.GetCurrentTimeline()
    tracks = []
    for track_index in range(1, timeline.GetTrackCount("audio") + 1):
        track_items = timeline.GetItemListInTrack("audio", track_index)
        if not isinstance(track_items, (list, tuple)):
            raise RuntimeError("Audio track occurrence list unreadable")
        tracks.append((track_index, track_items))
    actual = _bind_objects(pinned, tracks)
    passes = [_collect(actual, set()) for _ in range(2)]
    after = reader._read_pair(resolve, config, identity, expected, MATRIX_UID, probe)
    after_state, _ = reader._validate_read_pair(after, probe)
    _, after_playhead = _context(resolve, config, identity, reader, probe)
    if after_state != current or after_playhead != playhead:
        raise RuntimeError("Full state, selection context, or playhead changed")
    consistent = passes[0] == passes[1]
    any_valid = any(
        row.get("GetSourceAudioChannelMapping", {}).get("parsed") is not None
        or row.get("GetAudioMapping", {}).get("parsed") is not None
        for row in passes[0]
    )
    getter_error = any(
        "error" in entry
        for row in passes[0]
        for entry in (row.get("GetSourceAudioChannelMapping", {}), row.get("GetAudioMapping", {}))
    )
    status = (
        "stable-valid-documented-data" if consistent and any_valid
        else "getter-errors" if getter_error and consistent
        else "ambiguous-inconsistent-or-no-data"
    )
    directory = output / f"audio-mapping-readonly-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S.%fZ')}"
    directory.mkdir()
    evidence = {
        "status": status,
        "case": CASE,
        "getterPasses": passes,
        "getterConsistency": "equal-adjacent-passes" if consistent else "inconsistent",
        "beforeFullPair": before,
        "afterFullPair": after,
        "sourcePins": sorted(pinned.values(), key=lambda row: row["occurrenceUid"]),
        "projectId": PROJECT_ID,
        "projectBuild": BUILD,
        "selectedTimelineUid": MATRIX_UID,
        "playheadBefore": playhead,
        "playheadAfter": after_playhead,
        "limits": ["Mapping strings do not establish final Fairlight routing or audibility."],
    }
    reader._write(directory / "evidence.json", evidence)
    return evidence
