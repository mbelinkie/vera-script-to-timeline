"""Read-only transcript observation for the producer's two Resolve timelines."""

from __future__ import annotations

import json
import platform
import re
from datetime import UTC, datetime
from pathlib import Path


ACTION = "producer-transcript-probe"
PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
PROJECT_NAME = "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
EXPECTED_VERSION = (21, 1, 0, 14)
TARGET_TEXTS = {
    "transcription test 1": (
        "KAJ is three Finns, singing in Swedish, playing up the stereotypes "
        "that Swedes have for Finns. Namely that Finns really like saunas."
    ),
    "transcription test 2": (
        "KAJ is three Finns, playing up the stereotypes that Swedes have for "
        "Finns. Namely that Finns really like saunas."
    ),
}
TRANSCRIPTION_ARGUMENTS = (False, True)
GEOMETRY_METHODS = (
    "GetStart",
    "GetEnd",
    "GetSourceStartFrame",
    "GetSourceEndFrame",
    "GetSourceStartTime",
    "GetSourceEndTime",
    "GetSpeed",
    "GetClipEnabled",
    "GetTrackTypeAndIndex",
)
PROPERTY_KEYS = ("FPS", "Start TC")


def _jsonable(value):
    """Keep ordinary Resolve values raw while making odd fakes retainable."""
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except Exception as serialization_error:
        try:
            rendered = repr(value)
        except Exception:  # pragma: no cover - opaque remote proxy fallback
            rendered = "<opaque>"
        try:
            type_name = getattr(type(value), "__name__", None) or "opaque"
        except Exception:  # pragma: no cover - pathological proxy type
            type_name = "opaque"
        return {
            "unserializableType": type_name,
            "repr": rendered,
            "serializationError": f"{type(serialization_error).__name__}: {serialization_error}",
        }


def _error(error):
    return f"{type(error).__name__}: {error}"


def _call(obj, method, *args):
    """Return a serializable read record and the live returned object."""
    try:
        function = getattr(obj, method)
    except AttributeError as exc:
        return {"state": "missing", "error": _error(exc)}, None
    except Exception as exc:  # pragma: no cover - defensive API boundary
        return {"state": "error", "error": _error(exc)}, None
    try:
        value = function(*args)
    except AttributeError as exc:
        return {"state": "missing", "error": _error(exc)}, None
    except Exception as exc:
        return {"state": "error", "error": _error(exc)}, None
    return {"state": "value", "value": _jsonable(value)}, value


def _write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _journal(path, method, phase, value):
    with Path(path).open("a", encoding="utf-8") as stream:
        json.dump(
            {
                "at": datetime.now(UTC).isoformat(),
                "method": method,
                "phase": phase,
                "value": _jsonable(value),
            },
            stream,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")


def _identity(obj):
    uid, uid_value = _call(obj, "GetUniqueId")
    name, name_value = _call(obj, "GetName")
    return {
        "GetUniqueId": uid,
        "GetName": name,
    }, uid_value, name_value


def _context(resolve, project):
    project_id, _ = _call(project, "GetUniqueId")
    project_name, _ = _call(project, "GetName")
    timeline_read, current_timeline = _call(project, "GetCurrentTimeline")
    if timeline_read.get("state") == "value" and current_timeline is not None:
        timeline_identity, _, _ = _identity(current_timeline)
    else:
        timeline_identity = None
    page, _ = _call(resolve, "GetCurrentPage")
    return {
        "project": {
            "GetUniqueId": project_id,
            "GetName": project_name,
        },
        "currentTimeline": {
            "getter": timeline_read,
            "identity": timeline_identity,
        },
        "page": page,
    }


def _context_key(context):
    """Compare stable identities, never an opaque proxy's repr/address."""
    current = context.get("currentTimeline", {})
    return {
        "project": context.get("project"),
        "currentTimelineIdentity": current.get("identity"),
        "page": context.get("page"),
    }


def _value(read):
    return read.get("value") if read.get("state") == "value" else None


def _version_ok(read):
    value = _value(read)
    if not isinstance(value, (list, tuple)) or len(value) < 4:
        return False
    try:
        return tuple(int(part) for part in value[:4]) == EXPECTED_VERSION
    except (TypeError, ValueError):
        return False


def _target_name(name):
    return name.casefold() if isinstance(name, str) else None


def _discover_timelines(project):
    count_read, count = _call(project, "GetTimelineCount")
    rows = []
    handles = {}
    if count_read.get("state") != "value" or not isinstance(count, int):
        return rows, handles, {
            "state": "refused",
            "reason": "GetTimelineCount is unreadable",
            "count": count_read,
        }
    for index in range(1, count + 1):
        timeline_read, timeline = _call(project, "GetTimelineByIndex", index)
        row = {"index": index, "timeline": timeline_read}
        if timeline_read.get("state") == "value" and timeline is not None:
            identity, uid, name = _identity(timeline)
            row["identity"] = identity
            key = _target_name(name)
            if key in TARGET_TEXTS and isinstance(uid, str) and uid:
                handles.setdefault(key, []).append((timeline, uid, name))
        rows.append(row)
    duplicate_targets = {
        key: len(values) for key, values in handles.items() if len(values) != 1
    }
    missing_targets = sorted(set(TARGET_TEXTS) - set(handles))
    if duplicate_targets or missing_targets:
        return rows, handles, {
            "state": "refused",
            "reason": "target timelines are not exactly unique",
            "missing": missing_targets,
            "duplicates": duplicate_targets,
        }
    return rows, handles, {"state": "ready"}


def _transcription_state(value):
    if value is None:
        return "missing"
    if value in ({}, [], ""):
        return "empty"
    if isinstance(value, dict) and value.get("segments") == []:
        return "empty"
    return "value"


def _transcriptions(item):
    result = {}
    for nested in TRANSCRIPTION_ARGUMENTS:
        passes = []
        for _ in range(2):
            read, _ = _call(item, "GetTranscription", nested)
            if read.get("state") == "value":
                read["transcriptionState"] = _transcription_state(read.get("value"))
            passes.append(read)
        equal = passes[0] == passes[1]
        stable = passes[0] if equal else {"state": "unstable"}
        result[str(nested)] = {
            "argument": nested,
            "passes": passes,
            "repeatConsistency": "equal-adjacent-reads" if equal else "unstable",
            "state": stable.get("transcriptionState", stable.get("state")),
            "getterMissing": any(read.get("state") == "missing" for read in passes),
        }
    return result


def _targeted_property(item, key):
    read, value = _call(item, "GetClipProperty", key)
    if read.get("state") == "value" and isinstance(value, dict):
        # A fake or old binding may ignore the key. Never retain a full property map.
        read["value"] = _jsonable(value.get(key))
        read["returnedMapping"] = True
    return read


def _occurrence_candidates(timeline, timeline_key):
    candidates = []
    for track_type in ("video", "audio"):
        count_read, count = _call(timeline, "GetTrackCount", track_type)
        track_row = {"trackType": track_type, "count": count_read}
        if count_read.get("state") != "value" or not isinstance(count, int):
            candidates.append({"track": track_row, "items": []})
            continue
        items = []
        for index in range(1, count + 1):
            list_read, listed = _call(timeline, "GetItemListInTrack", track_type, index)
            item_rows = []
            if list_read.get("state") == "value" and isinstance(listed, (list, tuple)):
                for item_index, item in enumerate(listed):
                    media_read, media = _call(item, "GetMediaPoolItem")
                    row = {
                        "itemIndex": item_index,
                        "track": [track_type, index],
                        "mediaPoolItem": media_read,
                        "_item": item,
                    }
                    if media_read.get("state") == "value" and media is not None:
                        identity, uid, name = _identity(media)
                        row["mediaIdentity"] = identity
                        row["_media"] = media
                        row["_uid"] = uid
                        row["_name"] = name
                    item_rows.append(row)
            items.append({"index": index, "list": list_read, "items": item_rows})
        candidates.append({"track": track_row, "items": items})
    return {"timeline": timeline_key, "tracks": candidates}


def _identity_public(row):
    return {
        key: value
        for key, value in row.items()
        if not key.startswith("_")
    }


def _choose_source(candidates, config):
    identities = []
    objects = {}
    configured_uid = config.get("sourceUid")
    configured_name = config.get("sourceName")
    for timeline_row in candidates:
        for track_row in timeline_row["tracks"]:
            for list_row in track_row["items"]:
                for row in list_row["items"]:
                    uid = row.get("_uid")
                    name = row.get("_name")
                    if not isinstance(uid, str) or not uid:
                        continue
                    if configured_uid is not None and uid != configured_uid:
                        continue
                    if (
                        configured_name is not None
                        and _target_name(name) != _target_name(configured_name)
                    ):
                        continue
                    identities.append(
                        {
                            "uid": uid,
                            "name": name,
                            "timeline": timeline_row["timeline"],
                            "track": row["track"],
                            "itemIndex": row["itemIndex"],
                        }
                    )
                    objects.setdefault(uid, row.get("_media"))
    unique = sorted(objects)
    if len(unique) != 1 or objects[unique[0]] is None:
        return None, identities, {
            "state": "unavailable",
            "reason": (
                "source handle is not uniquely identifiable from targeted "
                "timeline occurrences"
            ),
            "candidateUids": unique,
        }
    uid = unique[0]
    return objects[uid], identities, {"state": "ready", "uid": uid}


def _geometry(item, track):
    result = {"trackRequested": list(track), "getters": {}}
    for method in GEOMETRY_METHODS:
        if method == "GetTrackTypeAndIndex":
            read, _ = _call(item, method)
        elif method in {"GetStart", "GetEnd"}:
            read, _ = _call(item, method)
        else:
            read, _ = _call(item, method)
        result["getters"][method] = read
    return result


def _collect_occurrences(candidates, source_uid):
    rows = []
    for timeline_row in candidates:
        occurrences = []
        for track_row in timeline_row["tracks"]:
            for list_row in track_row["items"]:
                for row in list_row["items"]:
                    if row.get("_uid") == source_uid and row.get("_media") is not None:
                        item = row.get("_item")
                        if item is None:
                            continue
                        occurrence = _identity_public(row)
                        occurrence["geometry"] = _geometry(item, row["track"])
                        occurrences.append(occurrence)
        rows.append({"timeline": timeline_row["timeline"], "occurrences": occurrences})
    return rows


def _word_tokens(text):
    return [token.casefold() for token in re.findall(r"[^\W_]+", text or "")]


def _word_raw_tokens(text):
    return re.findall(r"[^\W_]+", text or "")


def _extract_words(transcription):
    if not isinstance(transcription, dict):
        return {"state": "unavailable", "reason": "transcription is not a mapping"}
    segments = transcription.get("segments")
    if not isinstance(segments, list):
        return {"state": "unavailable", "reason": "segments list is missing"}
    words = []
    segment_text = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        if isinstance(segment.get("text"), str):
            segment_text.append(segment["text"])
        segment_words = segment.get("words")
        if isinstance(segment_words, list):
            words.extend(word for word in segment_words if isinstance(word, dict))
    if not words:
        return {
            "state": "unavailable",
            "reason": "word-level entries are absent",
            "segmentText": segment_text,
            "rawWords": [],
        }
    raw_texts = [word.get("text", "") for word in words if isinstance(word.get("text"), str)]
    raw_tokens = []
    for text in raw_texts:
        raw_tokens.extend(_word_raw_tokens(text))
    return {
        "state": "ready",
        "rawWords": words,
        "rawText": " ".join(raw_texts),
        "rawTokens": raw_tokens,
        "tokens": [token.casefold() for token in raw_tokens],
        "wordTimingAvailable": all(
            isinstance(word.get("start"), str) and isinstance(word.get("end"), str)
            for word in words
        ),
    }


def _differences(expected_raw, observed_raw):
    expected = [token.casefold() for token in expected_raw]
    observed = [token.casefold() for token in observed_raw]
    differences = []
    for index in range(max(len(expected), len(observed))):
        expected_token = expected[index] if index < len(expected) else None
        observed_token = observed[index] if index < len(observed) else None
        if expected_token != observed_token:
            differences.append(
                {
                    "index": index,
                    "expectedRaw": expected_raw[index] if index < len(expected_raw) else None,
                    "observedRaw": observed_raw[index] if index < len(observed_raw) else None,
                    "expectedToken": expected_token,
                    "observedToken": observed_token,
                }
            )
    return differences


def _comparison(transcription_read, expected_text, scope):
    expected_raw = _word_raw_tokens(expected_text)
    result = {"scope": scope, "expectedText": expected_text, "modes": {}}
    for mode, mode_read in transcription_read.items():
        passes = mode_read.get("passes", [])
        comparisons = []
        for pass_index, passed in enumerate(passes):
            words = (
                _extract_words(passed.get("value"))
                if passed.get("state") == "value"
                else {"state": "unavailable", "reason": passed.get("state")}
            )
            if words.get("state") != "ready":
                comparisons.append(
                    {
                        "pass": pass_index,
                        "status": "unavailable",
                        "words": words,
                    }
                )
                continue
            raw_observed = words["rawTokens"]
            comparisons.append(
                {
                    "pass": pass_index,
                    "status": "match" if _differences(expected_raw, raw_observed) == [] else "mismatch",
                    "words": words,
                    "differences": _differences(expected_raw, raw_observed),
                }
            )
        result["modes"][mode] = {
            "repeatConsistency": mode_read.get("repeatConsistency"),
            "state": mode_read.get("state"),
            "passes": comparisons,
        }
    return result


def _source_timing_summary(source_transcriptions, metadata, occurrence_rows):
    word_timing = False
    for mode in source_transcriptions.values():
        for passed in mode.get("passes", []):
            if passed.get("state") == "value":
                words = _extract_words(passed.get("value"))
                word_timing = word_timing or words.get("wordTimingAvailable", False)
    geometry_complete = bool(occurrence_rows)
    for timeline_row in occurrence_rows:
        for occurrence in timeline_row["occurrences"]:
            for read in occurrence["geometry"]["getters"].values():
                if read.get("state") != "value":
                    geometry_complete = False
    fps_read = metadata.get("FPS", {})
    fps = _value(fps_read)
    try:
        fps_available = float(fps) > 0
    except (TypeError, ValueError):
        fps_available = False
    candidate = word_timing and geometry_complete and fps_available
    return {
        "wordTimingAvailable": word_timing,
        "geometryComplete": geometry_complete,
        "fpsAvailable": fps_available,
        "candidateSourceRangeDerivable": candidate,
        "safeToDeriveEditedRanges": False,
        "boundaryAmbiguity": (
            "Source words and occurrence geometry do not expose a guaranteed "
            "timeline-specific boundary; clipping or frame rounding at a word "
            "edge remains ambiguous."
        ),
    }


def _public_candidates(candidates):
    return [
        {
            "timeline": row["timeline"],
            "tracks": [
                {
                    "track": track["track"],
                    "items": [
                        {
                            key: value
                            for key, value in item.items()
                            if not key.startswith("_")
                        }
                        for listed in track["items"]
                        for item in listed["items"]
                    ],
                }
                for track in row["tracks"]
            ],
        }
        for row in candidates
    ]


def _finalize(evidence, journal, raw, comparison, report):
    raw_path = evidence / "raw-readback.json"
    comparison_path = evidence / "comparison.json"
    result_path = evidence / "result.json"
    _write(raw_path, raw)
    _write(comparison_path, comparison)
    report = dict(report)
    report["artifacts"] = {
        "rawReadback": raw_path.name,
        "comparison": comparison_path.name,
        "result": result_path.name,
        "journal": journal.name,
    }
    _write(result_path, report)
    _journal(journal, ACTION, "complete", report)
    return report


def _new_evidence(output):
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence = output / f"producer-transcript-probe-{stamp}"
    evidence.mkdir(exist_ok=False)
    journal = evidence / "journal.jsonl"
    journal.touch()
    return evidence, journal


def run(resolve, config):
    """Read only the named project, timelines, their pool transcripts and source occurrences."""
    output = Path(config.get("outputDir", ""))
    if (
        config.get("action") != ACTION
        or config.get("projectName") != PROJECT_NAME
        or config.get("projectId", PROJECT_ID) != PROJECT_ID
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
    ):
        raise RuntimeError("Exact read-only producer transcript probe is required")
    evidence, journal = _new_evidence(output)
    _journal(journal, ACTION, "start", {"config": config, "python": platform.python_version()})

    runtime = {
        "productName": _call(resolve, "GetProductName")[0],
        "version": _call(resolve, "GetVersion")[0],
        "externalScriptingSetting": "None",
    }
    manager_read, manager = _call(resolve, "GetProjectManager")
    project_read, project = _call(manager, "GetCurrentProject") if manager is not None else (
        {"state": "error", "error": "project manager is unavailable"},
        None,
    )
    context_before = _context(resolve, project) if project is not None else {}
    raw = {
        "runtime": runtime,
        "projectManager": manager_read,
        "currentProject": project_read,
        "contextBefore": context_before,
    }
    _journal(journal, "preflight", "read", raw)
    identity = context_before.get("project", {})
    project_uid = _value(identity.get("GetUniqueId", {}))
    project_name = _value(identity.get("GetName", {}))
    guard_reasons = []
    if _value(runtime["productName"]) != "DaVinci Resolve Studio":
        guard_reasons.append("Resolve Studio product name mismatch")
    if not _version_ok(runtime["version"]):
        guard_reasons.append("Resolve 21.1 build 14 mismatch")
    if project_uid != PROJECT_ID or project_name != PROJECT_NAME:
        guard_reasons.append("current project identity mismatch")
    if guard_reasons:
        report = {
            "kind": ACTION,
            "status": "refused",
            "readOnly": True,
            "guardReasons": guard_reasons,
            "rawReadback": raw,
            "limitations": ["No transcript getter was invoked after the guard refusal."],
        }
        return _finalize(evidence, journal, raw, {"status": "not-run"}, report)

    catalog, handles, discovery = _discover_timelines(project)
    raw["timelineCatalog"] = catalog
    _journal(journal, "GetTimelineByIndex", "read", catalog)
    if discovery.get("state") != "ready":
        report = {
            "kind": ACTION,
            "status": "refused",
            "readOnly": True,
            "guardReasons": [discovery.get("reason")],
            "discovery": discovery,
            "rawReadback": raw,
        }
        return _finalize(evidence, journal, raw, {"status": "not-run"}, report)

    target_rows = {}
    candidates = []
    for key in TARGET_TEXTS:
        timeline, uid, actual_name = handles[key][0]
        pool_read, pool_item = _call(timeline, "GetMediaPoolItem")
        target = {
            "requestedName": key,
            "actualName": actual_name,
            "timelineUid": uid,
            "timelinePoolItem": pool_read,
            "timelineTranscriptions": _transcriptions(pool_item)
            if pool_read.get("state") == "value" and pool_item is not None
            else {},
        }
        target_rows[key] = target
        candidate = _occurrence_candidates(timeline, key)
        candidates.append(candidate)
    raw["targets"] = target_rows
    raw["occurrenceCandidates"] = _public_candidates(candidates)
    _journal(journal, "GetTranscription", "read", target_rows)

    source, source_identities, source_selection = _choose_source(candidates, config)
    raw["sourceSelection"] = {
        "selection": source_selection,
        "candidateIdentities": source_identities,
    }
    source_transcriptions = _transcriptions(source) if source is not None else {}
    source_metadata = (
        {key: _targeted_property(source, key) for key in PROPERTY_KEYS}
        if source is not None and config.get("readSourceMetadata", True)
        else {}
    )
    raw["source"] = {
        "identity": _identity(source)[0] if source is not None else None,
        "transcriptions": source_transcriptions,
        "metadata": source_metadata,
    }
    source_uid = source_selection.get("uid")
    occurrence_rows = _collect_occurrences(candidates, source_uid) if source_uid else []
    raw["targetedOccurrences"] = occurrence_rows
    _journal(journal, "GetTranscription", "source-read", raw["source"])
    _journal(journal, "TimelineItemGeometry", "read", occurrence_rows)

    comparisons = {}
    for key, target in target_rows.items():
        comparisons[key] = {
            "timeline": _comparison(target["timelineTranscriptions"], TARGET_TEXTS[key], "timeline"),
            "source": _comparison(source_transcriptions, TARGET_TEXTS[key], "source-only"),
        }
    direct_available = any(
        mode.get("state") == "value" and mode.get("repeatConsistency") == "equal-adjacent-reads"
        for target in target_rows.values()
        for mode in target["timelineTranscriptions"].values()
    )
    range_summary = _source_timing_summary(source_transcriptions, source_metadata, occurrence_rows)
    context_after = _context(resolve, project)
    raw["contextAfter"] = context_after
    context_unchanged = _context_key(context_before) == _context_key(context_after)
    _journal(journal, "context", "after", context_after)
    report = {
        "kind": ACTION,
        "status": "complete" if context_unchanged else "refused",
        "readOnly": True,
        "identity": {"projectId": PROJECT_ID, "projectName": PROJECT_NAME},
        "runtime": runtime,
        "timelineNames": {key: target_rows[key]["actualName"] for key in target_rows},
        "timelineUids": {key: target_rows[key]["timelineUid"] for key in target_rows},
        "comparisons": comparisons,
        "directTimelineTranscriptAvailable": direct_available,
        "sourceOnlyRangeAssessment": range_summary,
        "contextUnchanged": context_unchanged,
        "limits": [
            "Missing GetTranscription getters are retained as missing and are not a capability-failure conclusion.",
            "Source comparisons are labeled source-only when timeline-specific words are unavailable.",
            "No timeline selection, setter, transcription, save, render, export, or source-file read was performed.",
        ],
    }
    if not context_unchanged:
        report["guardReasons"] = ["project, current timeline, or Resolve page drifted during readback"]
    comparison = {
        "producerTexts": TARGET_TEXTS,
        "comparisons": comparisons,
        "sourceOnlyRangeAssessment": range_summary,
        "contextUnchanged": context_unchanged,
    }
    return _finalize(evidence, journal, raw, comparison, report)
