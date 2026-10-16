"""Bounded per-occurrence source-mapping mute probe for Issue 141.

This module is deliberately narrower than the audio output and Fairlight
questions.  It exercises only the documented TimelineItem mapping setter for
one marker-bound Matrix audio occurrence.  The native launcher is not part of
this file; a later registration must provide a fresh, hash-bound full pair.
"""

import copy
import importlib.util
import json
import hashlib
from datetime import UTC, datetime
from pathlib import Path


ACTION = "audio-mapping-mute"
CASE = "R2-disable-mute"
PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
MATRIX_UID = "29ae8331-b86e-4041-a548-960695cc7b24"
MATRIX_NAME = "VERA 141 Batched Matrix"
BUILD = [21, 1, 0, 14, ""]
PROTECTED_INVENTORY = "protected-six"
PROTECTED_SOURCE_UID = "be5f1584-f0c4-4dd9-988b-73f3167e77d1"
PROTECTED_SOURCE_NAME = "semi1b.mp4"
READER_NAME = "r4-range-repair"
READER_FILE = "r4-range-repair.py"
READER_SHA256 = "9b6977747a1f3decf957ead6134f10fc4f597bf9d0c3dc5c081b7bf2671879a4"

# Existing Matrix markers use the "141 " prefix.  Accepting the unprefixed
# spelling as well keeps the guard exact for the named case while handling the
# same marker if the UI omits the issue prefix.
TARGET_MARKER_NAMES = {"141 R2-residual item 2"}
TARGET_UID = "f4e9f649-894a-42f2-9f54-a8321ae7c163"
TARGET_SOURCE_UID = "a7ad9e19-d49b-428b-9fd5-95c90d60e6f8"
TARGET_TRACK = ["audio", 2]
TARGET_RANGE = [4500, 4699]


def _canonical(value):
    return json.loads(json.dumps(value, allow_nan=False))


def _write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _append(path, method, phase, value):
    with Path(path).open("a", encoding="utf-8") as stream:
        json.dump(
            {
                "at": datetime.now(UTC).isoformat(),
                "method": method,
                "phase": phase,
                "value": value,
            },
            stream,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")


def _error(error):
    return f"{type(error).__name__}: {error}"


def _value(entry):
    return entry.get("value") if isinstance(entry, dict) else None


def _load_reader(here, probe):
    path = here / READER_FILE
    if path.is_symlink() or probe.sha256(path) != READER_SHA256:
        raise RuntimeError("Pinned full-pair reader changed or is a symlink")
    spec = importlib.util.spec_from_file_location(READER_NAME, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Pinned full-pair reader could not be loaded")
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    return reader


def _marker_names(item):
    markers = _value(item.get("GetMarkers"))
    if not isinstance(markers, dict):
        return []
    return [
        marker.get("name")
        for marker in markers.values()
        if isinstance(marker, dict) and isinstance(marker.get("name"), str)
    ]


def _mapping_entry(item):
    entry = item.get("GetSourceAudioChannelMapping")
    if not isinstance(entry, dict) or not isinstance(entry.get("value"), str):
        raise RuntimeError("Target mapping getter is missing or not a JSON string")
    try:
        mapping = json.loads(entry["value"])
    except (TypeError, ValueError) as error:
        raise RuntimeError("Target mapping getter returned invalid JSON") from error
    if not isinstance(mapping, dict):
        raise RuntimeError("Target mapping is not an object")
    return entry["value"], mapping


def _target_from_state(state, probe):
    """Find exactly one marker-bound audio occurrence in the selected Matrix."""
    timeline = probe._pass_timeline(state, MATRIX_UID)
    matches = []
    for track in timeline.get("tracks", []):
        for item in track.get("items", []):
            marker_names = [name for name in _marker_names(item) if name in TARGET_MARKER_NAMES]
            if not marker_names:
                continue
            if len(marker_names) != 1:
                raise RuntimeError("R2-disable-mute marker is duplicated on one item")
            track_value = _value(item.get("GetTrackTypeAndIndex"))
            if not isinstance(track_value, list) or len(track_value) != 2:
                raise RuntimeError("R2-disable-mute target track identity is incomplete")
            if track_value[0] != "audio":
                raise RuntimeError("R2-disable-mute marker is not on an audio TimelineItem")
            uid = _value(item.get("GetUniqueId"))
            media = item.get("GetMediaPoolItem")
            source_uid = _value(media.get("GetUniqueId")) if isinstance(media, dict) else None
            clip = _value(media.get("GetClipProperty")) if isinstance(media, dict) else None
            source_name = clip.get("File Name") if isinstance(clip, dict) else None
            if not isinstance(uid, str) or not isinstance(source_uid, str):
                raise RuntimeError("R2-disable-mute target UID/source binding is incomplete")
            if uid != TARGET_UID or source_uid != TARGET_SOURCE_UID:
                raise RuntimeError("R2-disable-mute target UID/source binding changed")
            if track_value != TARGET_TRACK or [
                _value(item.get("GetStart")), _value(item.get("GetEnd"))
            ] != TARGET_RANGE:
                raise RuntimeError("R2-disable-mute target track/range changed")
            if source_uid == PROTECTED_SOURCE_UID or source_name == PROTECTED_SOURCE_NAME:
                raise RuntimeError("Protected source refused before mapping mutation")
            raw, mapping = _mapping_entry(item)
            tracks = mapping.get("track_mapping")
            if not isinstance(tracks, dict) or set(tracks) != {"1"}:
                raise RuntimeError("R2-disable-mute target must expose exactly track_mapping 1")
            track_mapping = tracks["1"]
            if not isinstance(track_mapping, dict) or track_mapping.get("mute") is not False:
                raise RuntimeError("R2-disable-mute target must begin unmuted")
            matches.append(
                {
                    "occurrenceUid": uid,
                    "sourceUid": source_uid,
                    "sourceName": source_name,
                    "track": {"type": track_value[0], "index": track_value[1]},
                    "markerName": marker_names[0],
                    "markerNames": marker_names,
                    "originalRawMapping": raw,
                    "originalMapping": _canonical(mapping),
                }
            )
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one R2-disable-mute audio occurrence; found {len(matches)}"
        )
    return matches[0]


def _muted_mapping(original_raw):
    """Return a mapping that changes only track_mapping[1].mute."""
    try:
        original = json.loads(original_raw)
    except (TypeError, ValueError) as error:
        raise RuntimeError("Original mapping is not valid JSON") from error
    changed = _canonical(original)
    tracks = changed.get("track_mapping")
    if not isinstance(tracks, dict) or set(tracks) != {"1"}:
        raise RuntimeError("Original mapping does not have exactly track_mapping 1")
    track = tracks["1"]
    if not isinstance(track, dict) or track.get("mute") is not False:
        raise RuntimeError("Original mapping is not unmuted")
    track["mute"] = True
    return json.dumps(changed, separators=(",", ":"), sort_keys=True)


def _mapping_delta_is_only_mute(before_raw, after_raw):
    try:
        before = json.loads(before_raw)
        after = json.loads(after_raw)
    except (TypeError, ValueError):
        return False
    expected = _canonical(before)
    try:
        expected["track_mapping"]["1"]["mute"] = True
    except (KeyError, TypeError):
        return False
    if before.get("track_mapping", {}).get("1", {}).get("mute") is not False:
        return False
    return after == expected


def _item_in_live_timeline(timeline, target, probe):
    kind = target["track"]["type"]
    index = target["track"]["index"]
    items = timeline.GetItemListInTrack(kind, index)
    if not isinstance(items, (list, tuple)):
        raise RuntimeError("Target audio track item list is unreadable")
    matches = [item for item in items if item.GetUniqueId() == target["occurrenceUid"]]
    if len(matches) != 1:
        raise RuntimeError("R2-disable-mute target UID is missing or duplicated")
    item = matches[0]
    source = item.GetMediaPoolItem()
    if source is None or source.GetUniqueId() != target["sourceUid"]:
        raise RuntimeError("R2-disable-mute source binding changed")
    source_name = source.GetName()
    if source_name == PROTECTED_SOURCE_NAME or source.GetUniqueId() == PROTECTED_SOURCE_UID:
        raise RuntimeError("Protected source refused before mapping mutation")
    actual_track = item.GetTrackTypeAndIndex()
    if actual_track != [kind, index]:
        raise RuntimeError("R2-disable-mute track location changed")
    if item.GetStart() != TARGET_RANGE[0] or item.GetEnd() != TARGET_RANGE[1]:
        raise RuntimeError("R2-disable-mute target range changed")
    marker_names = [
        marker.get("name")
        for marker in (item.GetMarkers() or {}).values()
        if isinstance(marker, dict) and marker.get("name") in TARGET_MARKER_NAMES
    ]
    if marker_names != [target["markerName"]]:
        raise RuntimeError("R2-disable-mute marker binding changed")
    return item


def _set_mapping(item, raw, *, journal=None, operation="mapping"):
    if journal is not None:
        _append(
            journal,
            "SetSourceAudioChannelMapping",
            "request",
            {"operation": operation, "raw": raw, "mapping": json.loads(raw)},
        )
    try:
        result = item.SetSourceAudioChannelMapping(raw)
    except Exception as error:
        if journal is not None:
            _append(
                journal,
                "SetSourceAudioChannelMapping",
                "failure",
                {"operation": operation, "error": _error(error)},
            )
        raise
    if journal is not None:
        _append(
            journal,
            "SetSourceAudioChannelMapping",
            "return",
            {"operation": operation, "value": result},
        )
    if result is not True:
        error = RuntimeError("SetSourceAudioChannelMapping refused the exact mapping")
        if journal is not None:
            _append(
                journal,
                "SetSourceAudioChannelMapping",
                "failure",
                {"operation": operation, "error": _error(error)},
            )
        raise error
    return result


def _pair_with_only_target_mapping_change(before, after, target_uid, probe):
    """Compare all full pair data while allowing only the target mapping value."""
    if before.get("selectedTimelineUid") != MATRIX_UID or after.get("selectedTimelineUid") != MATRIX_UID:
        raise RuntimeError("Selected Matrix changed")
    if before.get("timelineInventory") != PROTECTED_INVENTORY or after.get("timelineInventory") != PROTECTED_INVENTORY:
        raise RuntimeError("Protected-six inventory metadata is missing")
    if before.get("poolPasses") != after.get("poolPasses"):
        raise RuntimeError("Pool state changed during mapping mutation")
    if before.get("poolConsistency") != after.get("poolConsistency"):
        raise RuntimeError("Pool consistency metadata changed")
    before_passes = before.get("timelinePasses")
    after_passes = after.get("timelinePasses")
    if not isinstance(before_passes, list) or not isinstance(after_passes, list):
        raise RuntimeError("Full timeline pair is missing")
    if len(before_passes) != 2 or len(after_passes) != 2:
        raise RuntimeError("Full timeline pair does not contain two passes")
    for before_state, after_state in zip(before_passes, after_passes):
        expected = copy.deepcopy(before_state)
        before_timeline = probe._pass_timeline(before_state, MATRIX_UID)
        after_timeline = probe._pass_timeline(after_state, MATRIX_UID)
        before_item = _state_item(before_timeline, target_uid)
        after_item = _state_item(after_timeline, target_uid)
        before_raw, _ = _mapping_entry(before_item)
        after_raw, _ = _mapping_entry(after_item)
        if not _mapping_delta_is_only_mute(before_raw, after_raw):
            raise RuntimeError("Target mapping changed beyond mute false-to-true")
        expected_item = _state_item(probe._pass_timeline(expected, MATRIX_UID), target_uid)
        expected_item["GetSourceAudioChannelMapping"] = copy.deepcopy(
            after_item["GetSourceAudioChannelMapping"]
        )
        if after_state != expected:
            raise RuntimeError("State changed outside the target mapping getter")
    return True


def _state_item(timeline, uid):
    matches = [
        item
        for track in timeline.get("tracks", [])
        for item in track.get("items", [])
        if _value(item.get("GetUniqueId")) == uid
    ]
    if len(matches) != 1:
        raise RuntimeError("Target occurrence is missing or duplicated in full state")
    return matches[0]


def _exact_pair(before, after, probe):
    if before != after:
        raise RuntimeError("Restored full pair differs from the stable before pair")
    if probe.errors(after.get("timelinePasses")) or probe.errors(after.get("poolPasses")):
        raise RuntimeError("Restored pair contains getter errors")
    return True


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _held_result(config, output):
    path = Path(config.get("heldResult", ""))
    digest = config.get("heldResultSha256")
    if (not path.is_absolute() or path.is_symlink() or path.name != "result.json"
            or path.parent.parent.resolve() != output.resolve()
            or not path.parent.name.startswith("audio-mapping-mute-")
            or not isinstance(digest, str) or _file_sha256(path) != digest):
        raise RuntimeError("Exact hash-bound held mapping result is required")
    try:
        held = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError("Held mapping result is unreadable") from error
    if held.get("action") != ACTION or held.get("case") != CASE or held.get("mappingPhase") != "hold" or held.get("status") != "mapping-muted-held-for-output":
        raise RuntimeError("Held result has wrong phase or status")
    if not isinstance(held.get("beforeFullPair"), dict) or not isinstance(held.get("afterMutedFullPair"), dict):
        raise RuntimeError("Held result is missing complete before/muted pairs")
    target = held.get("target")
    if not isinstance(target, dict) or target.get("occurrenceUid") != TARGET_UID or target.get("sourceUid") != TARGET_SOURCE_UID:
        raise RuntimeError("Held result target binding is invalid")
    if held.get("projectId") != PROJECT_ID or held.get("selectedTimelineUid") != MATRIX_UID:
        raise RuntimeError("Held result project or Matrix binding is invalid")
    if not isinstance(held.get("mutedMapping"), dict) or held["mutedMapping"].get("track_mapping", {}).get("1", {}).get("mute") is not True:
        raise RuntimeError("Held result muted status is malformed")
    return held, path


def run(resolve, config, *, probe):
    """Run one guarded mapping mute transition and exact restoration."""
    here = Path(__file__).resolve().parent
    output = Path(config.get("outputDir", ""))
    root = Path(probe.ROOT).resolve()
    if (
        config.get("action") != ACTION
        or config.get("case") != CASE
        or config.get("externalScriptingSetting") != "None"
        or config.get("timelineInventory") != PROTECTED_INVENTORY
        or config.get("projectName", "") != "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
        or not output.is_absolute()
        or output.is_symlink()
        or output.parent.resolve() != (root / "out").resolve()
        or not output.is_dir()
    ):
        raise RuntimeError("Exact synthetic audio-mapping mute request required")
    checkpoint = Path(config.get("mappingCheckpoint", ""))
    if (
        not checkpoint.is_absolute()
        or checkpoint.parent.resolve() != output.resolve()
        or checkpoint.is_symlink()
        or not isinstance(config.get("mappingCheckpointSha256"), str)
    ):
        raise RuntimeError("Fresh full Matrix checkpoint is required")
    phase = config.get("mappingPhase", "roundtrip")
    if phase not in {"roundtrip", "hold", "restore"}:
        raise RuntimeError("Unsupported mappingPhase")
    held = None
    held_path = None
    if phase == "restore":
        held, held_path = _held_result(config, output)
    reader = _load_reader(here, probe)
    identity = {"projectId": PROJECT_ID, "projectName": config["projectName"]}
    pinned = reader._pin(
        checkpoint,
        checkpoint.name,
        config["mappingCheckpointSha256"],
        probe,
    )
    reader._validate_read_pair(pinned, probe)
    _media, expected = reader._manifest(config, root, probe)
    project = reader._context(resolve, config, identity, probe, MATRIX_UID)
    if resolve.GetProductName() != "DaVinci Resolve Studio" or resolve.GetVersion() != BUILD:
        raise RuntimeError("Exact Resolve Studio 21.1 build 14 required")
    if resolve.GetCurrentPage() != "edit":
        raise RuntimeError("Edit page is required")
    before = reader._read_pair(resolve, config, identity, expected, MATRIX_UID, probe)
    reader._validate_read_pair(before, probe)
    if phase == "restore":
        reader._validate_read_pair(held["beforeFullPair"], probe)
        reader._validate_read_pair(held["afterMutedFullPair"], probe)
        _pair_with_only_target_mapping_change(
            held["beforeFullPair"], held["afterMutedFullPair"], TARGET_UID, probe
        )
        if before != held["afterMutedFullPair"]:
            raise RuntimeError("Fresh current pair differs from exact held after pair")
        if pinned != before:
            raise RuntimeError("Fresh restore checkpoint differs from held current pair")
    elif before != pinned:
        raise RuntimeError("Fresh stable before pair differs from the supplied checkpoint")
    target = _target_from_state(before["timelinePasses"][0], probe) if phase != "restore" else copy.deepcopy(held["target"])
    timeline = project.GetCurrentTimeline()
    playhead_before = timeline.GetCurrentTimecode()
    item = _item_in_live_timeline(timeline, target, probe)
    live_original = item.GetSourceAudioChannelMapping()
    if phase == "restore":
        expected_muted = _muted_mapping(target["originalRawMapping"])
        if live_original != expected_muted:
            raise RuntimeError("Live mapping is not the exact held mute state")
        held_target = _target_from_state(held["beforeFullPair"]["timelinePasses"][0], probe)
        if held_target != target:
            raise RuntimeError("Held original target descriptor is inconsistent")
        if held.get("mutedMapping") != json.loads(expected_muted):
            raise RuntimeError("Held muted mapping differs from exact target delta")
    elif live_original != target["originalRawMapping"]:
        raise RuntimeError("Live target mapping differs from the stable before pair")
    if phase == "restore":
        original_before = held["beforeFullPair"]
        muted_raw = target["originalRawMapping"]
    else:
        original_before = before
        muted_raw = _muted_mapping(live_original)
    evidence_dir = output / f"audio-mapping-mute-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S.%fZ')}"
    evidence_dir.mkdir()
    journal = evidence_dir / "journal.jsonl"
    _write(evidence_dir / "before-full-pair.json", before)
    _write(evidence_dir / "target.json", target)
    _append(
        journal,
        "Evidence",
        "pre-mutation",
        {"beforeFullPair": "before-full-pair.json", "target": "target.json"},
    )
    mutation_attempted = False
    after = None
    restored = None
    operation_error = None
    restore_error = None
    if phase == "restore":
        try:
            mutation_attempted = True
            _set_mapping(item, muted_raw, journal=journal, operation="restore-held")
            restored = reader._read_pair(resolve, config, identity, expected, MATRIX_UID, probe)
            _write(evidence_dir / "restored-full-pair.json", restored)
            _exact_pair(original_before, restored, probe)
            if timeline.GetCurrentTimecode() != playhead_before:
                raise RuntimeError("Playhead changed during held mapping restoration")
        except Exception as error:
            operation_error = error
            _append(journal, "MappingRestore", "failure", _error(error))
            try:
                restored = reader._read_pair(resolve, config, identity, expected, MATRIX_UID, probe)
                _write(evidence_dir / "restored-full-pair.json", restored)
                _append(journal, "ReadPair", "after-restore-failure", {"path": "restored-full-pair.json", "equalsBefore": restored == original_before})
            except Exception as capture_error:
                _append(journal, "ReadPair", "final-capture-failure", _error(capture_error))
    else:
      try:
        mutation_attempted = True
        _set_mapping(item, muted_raw, journal=journal, operation="mute")
        try:
            after = reader._read_pair(
                resolve, config, identity, expected, MATRIX_UID, probe
            )
            _write(evidence_dir / "after-muted-full-pair.json", after)
            _append(
                journal,
                "ReadPair",
                "return",
                {"operation": "mute", "path": "after-muted-full-pair.json"},
            )
        except Exception as error:
            _append(
                journal,
                "ReadPair",
                "failure",
                {"operation": "mute", "error": _error(error)},
            )
            raise
        try:
            reader._validate_read_pair(after, probe)
            _pair_with_only_target_mapping_change(
                before, after, target["occurrenceUid"], probe
            )
        except Exception as error:
            _append(
                journal,
                "ReadPair",
                "failure",
                {"operation": "mute-validation", "error": _error(error)},
            )
            raise
      except Exception as error:
        operation_error = error
        _append(journal, "MappingMutation", "failure", _error(error))
      finally:
        if mutation_attempted and (phase == "roundtrip" or (phase == "hold" and operation_error is not None)):
            _append(
                journal,
                "SetSourceAudioChannelMapping",
                "restore-request",
                {
                    "operation": "restore",
                    "raw": target["originalRawMapping"],
                    "mapping": json.loads(target["originalRawMapping"]),
                },
            )
            try:
                project = reader._context(resolve, config, identity, probe, MATRIX_UID)
                timeline = project.GetCurrentTimeline()
                item = _item_in_live_timeline(timeline, target, probe)
                _set_mapping(
                    item,
                    target["originalRawMapping"],
                    journal=journal,
                    operation="restore",
                )
                try:
                    restored = reader._read_pair(
                        resolve, config, identity, expected, MATRIX_UID, probe
                    )
                    _write(evidence_dir / "restored-full-pair.json", restored)
                    _append(
                        journal,
                        "ReadPair",
                        "return",
                        {"operation": "restore", "path": "restored-full-pair.json"},
                    )
                except Exception as error:
                    _append(
                        journal,
                        "ReadPair",
                        "failure",
                        {"operation": "restore", "error": _error(error)},
                    )
                    raise
                reader._validate_read_pair(restored, probe)
                _exact_pair(before, restored, probe)
                if timeline.GetCurrentTimecode() != playhead_before:
                    raise RuntimeError(
                        "Playhead changed during mapping mutation/restoration"
                    )
            except Exception as error:
                restore_error = error
                _append(journal, "MappingRestore", "failure", _error(error))
                # A false setter can leave state unchanged or partially applied.
                # Retain a read-only final observation even when restoration refuses.
                try:
                    restored = reader._read_pair(
                        resolve, config, identity, expected, MATRIX_UID, probe
                    )
                    _write(evidence_dir / "restored-full-pair.json", restored)
                    _append(journal, "ReadPair", "after-restore-failure", {
                        "path": "restored-full-pair.json",
                        "equalsBefore": restored == before,
                    })
                except Exception as capture_error:
                    _append(journal, "ReadPair", "final-capture-failure", _error(capture_error))
    result = {
        "status": (
            ("mapping-muted-held-for-output" if phase == "hold" else "mapping-muted-and-exactly-restored")
            if operation_error is None and restore_error is None
            else "mapping-operation-failed-evidence-retained"
        ),
        "action": ACTION,
        "case": CASE,
        "mappingPhase": phase,
        "projectId": PROJECT_ID,
        "selectedTimelineUid": MATRIX_UID,
        "target": target,
        "mutedMapping": held["mutedMapping"] if phase == "restore" else json.loads(muted_raw),
        "playheadBefore": playhead_before,
        "beforeFullPair": original_before,
        "afterMutedFullPair": after if phase != "restore" else held["afterMutedFullPair"],
        "restoredFullPair": restored,
        "evidence": {
            "directory": str(evidence_dir),
            "journal": str(journal),
            "beforeFullPair": str(evidence_dir / "before-full-pair.json"),
            "target": str(evidence_dir / "target.json"),
            "afterMutedFullPair": str(evidence_dir / "after-muted-full-pair.json")
            if after is not None
            else None,
            "restoredFullPair": str(evidence_dir / "restored-full-pair.json")
            if restored is not None
            else None,
            "result": str(evidence_dir / "result.json"),
        },
        "limits": [
            "This observes source-channel mapping mute state only; it does not establish Fairlight Solo, bus routing, or final program audibility.",
            "No protected source is eligible for this mutation.",
            "A setter refusal or partial readback remains diagnostic evidence; no unlock or retry is attempted.",
        ],
    }
    if operation_error is not None:
        result["failure"] = _error(operation_error)
    if restore_error is not None:
        result["restoreFailure"] = _error(restore_error)
    if phase == "restore" and held_path is not None:
        result["restoresHeldResult"] = str(held_path)
        result["restoresHeldResultSha256"] = config["heldResultSha256"]
    _write(evidence_dir / "result.json", result)
    if operation_error is not None:
        raise operation_error
    if restore_error is not None:
        raise restore_error
    return result
