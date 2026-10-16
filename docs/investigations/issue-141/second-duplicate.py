"""One guarded second native duplicate of the exact R1 identity timeline."""

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
BUILD = [21, 1, 0, 14, ""]
MATRIX_UID = "29ae8331-b86e-4041-a548-960695cc7b24"
R4_UID = "64de8a4c-86bd-4f19-9d20-47b8940f610b"
BASELINE_UID = "88f7923d-55a7-471f-b09b-cf10f9fae8ad"
R1_UID = "aa2b8e36-83bd-4292-9e33-217c00ca192f"
TIMELINES = {
    MATRIX_UID: "VERA 141 Batched Matrix",
    R4_UID: "VERA 141 R4 availability",
    BASELINE_UID: "VERA 141 Baseline",
    R1_UID: "VERA 141 R1 identity",
}
DUPLICATE_NAME = "VERA 141 R1 identity repeat"
R4_PIN_NAME = "PENDING-second-duplicate-selected-r4-pair.json"
R4_PIN_SHA256 = None


def _write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _record(path, method, phase, value):
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


def _timeline_rows(state):
    rows = state.get("timelines")
    if not isinstance(rows, list):
        raise RuntimeError("Timeline inventory is unreadable")
    found = {}
    for row in rows:
        uid = row.get("GetUniqueId", {}).get("value")
        name = row.get("GetName", {}).get("value")
        if not isinstance(uid, str) or not isinstance(name, str) or uid in found:
            raise RuntimeError("Timeline identity is missing or duplicated")
        found[uid] = row
    return found


def _usage_free(value):
    if isinstance(value, dict):
        return {
            key: _usage_free(child) for key, child in value.items() if key != "Usage"
        }
    if isinstance(value, list):
        return [_usage_free(child) for child in value]
    return value


def _usage_values(value, path="$", found=None):
    found = {} if found is None else found
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}/{key}"
            if key == "Usage":
                found[child_path] = child
            else:
                _usage_values(child, child_path, found)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _usage_values(child, f"{path}/{index}", found)
    return found


def _pool_by_uid(inventory):
    rows = inventory.get("items")
    if not isinstance(rows, list):
        raise RuntimeError("Media-pool inventory is unreadable")
    result = {}
    for row in rows:
        uid = row.get("uid")
        if not isinstance(uid, str) or not uid or uid in result:
            raise RuntimeError("Media-pool UID is missing or duplicated")
        result[uid] = row
    return result


def _usage_delta_rows(before, after):
    before_rows, after_rows = _timeline_rows(before), _timeline_rows(after)
    changes = []
    for uid in sorted(set(before_rows) & set(after_rows)):
        old_usage = _usage_values(before_rows[uid])
        new_usage = _usage_values(after_rows[uid])
        for path in sorted(set(old_usage) | set(new_usage)):
            if old_usage.get(path) != new_usage.get(path):
                changes.append(
                    {
                        "timelineUid": uid,
                        "path": path,
                        "before": old_usage.get(path),
                        "after": new_usage.get(path),
                    }
                )
    return changes


def _marker_and_range_signature(track, item):
    media = item.get("GetMediaPoolItem", {})
    return {
        "track": {
            "type": track.get("type"),
            "index": track.get("index"),
            "name": track.get("GetTrackName"),
        },
        "item": {
            key: item.get(key)
            for key in (
                "GetName",
                "GetType",
                "GetTrackTypeAndIndex",
                "GetMarkers",
                "GetProperties",
                "GetClipEnabled",
                "GetSourceStartFrame",
                "GetSourceEndFrame",
                "GetSourceStartTime",
                "GetSourceEndTime",
                "GetStart",
                "GetEnd",
                "GetDuration",
                "GetStart(True)",
                "GetEnd(True)",
                "GetDuration(True)",
                "GetLeftOffset",
                "GetRightOffset",
            )
        },
        "mediaUid": media.get("GetUniqueId"),
    }


def _occurrences(timeline):
    occurrences = []
    for track in timeline.get("tracks", []):
        items = track.get("items")
        if not isinstance(items, list):
            raise RuntimeError("Timeline track items are unreadable")
        for item in items:
            uid = item.get("GetUniqueId", {}).get("value")
            media_uid = (
                item.get("GetMediaPoolItem", {}).get("GetUniqueId", {}).get("value")
            )
            if (
                not isinstance(uid, str)
                or not uid
                or not isinstance(media_uid, str)
                or not media_uid
            ):
                raise RuntimeError("Occurrence or source identity is unreadable")
            occurrences.append(
                (uid, media_uid, _marker_and_range_signature(track, item))
            )
    return occurrences


def _validate_copy(source_state, after_state, source_uid, duplicate_uid):
    before_rows = _timeline_rows(source_state)
    after_rows = _timeline_rows(after_state)
    source = before_rows.get(source_uid)
    duplicate = after_rows.get(duplicate_uid)
    if source is None or duplicate is None:
        raise RuntimeError("Exact source or returned duplicate UID is absent")
    for field in (
        "GetStartFrame",
        "GetEndFrame",
        "GetStartTimecode",
        "GetSettings",
        "GetMarkers",
    ):
        if source.get(field) != duplicate.get(field):
            raise RuntimeError(f"Copied timeline {field} differs")
    before_items = _occurrences(source)
    after_items = _occurrences(duplicate)
    old_uids = {uid for uid, _, _ in before_items}
    new_uids = {uid for uid, _, _ in after_items}
    if (
        len(before_items) != 6
        or len(old_uids) != 6
        or len(after_items) != 6
        or len(new_uids) != 6
    ):
        raise RuntimeError(
            "R1 duplicate must contain six uniquely identified occurrences"
        )
    if old_uids & new_uids:
        raise RuntimeError("Duplicate reused an original occurrence UID")
    if {media for _, media, _ in before_items} != {
        media for _, media, _ in after_items
    }:
        raise RuntimeError("Duplicate source-media UID set differs")
    before_signatures = Counter(
        json.dumps(signature, sort_keys=True, allow_nan=False)
        for _, _, signature in before_items
    )
    after_signatures = Counter(
        json.dumps(signature, sort_keys=True, allow_nan=False)
        for _, _, signature in after_items
    )
    if before_signatures != after_signatures:
        raise RuntimeError(
            "Copied ranges, markers, track facts, or source bindings differ"
        )
    ambiguous = sum(count for count in before_signatures.values() if count > 1)
    return {
        "sourceOccurrenceUids": sorted(old_uids),
        "duplicateOccurrenceUids": sorted(new_uids),
        "sharedSourceUids": sorted({media for _, media, _ in before_items}),
        "matchingOccurrenceSignatures": 6,
        "ambiguousSignatureOccurrences": ambiguous,
        "lineageClaim": "none; identical signatures are not occurrence bindings",
    }


def _validate_additive_pool(before, after, duplicate_uid, duplicate_name):
    if before.get("folders") != after.get("folders"):
        raise RuntimeError("Media-pool folder inventory changed")
    old_items, new_items = _pool_by_uid(before), _pool_by_uid(after)
    added = set(new_items) - set(old_items)
    if len(added) != 1:
        raise RuntimeError("Expected exactly one new timeline proxy pool item")
    mappings_before = {
        row["timelineUid"]["value"]: row for row in before.get("timelineMappings", [])
    }
    mappings_after = {
        row["timelineUid"]["value"]: row for row in after.get("timelineMappings", [])
    }
    if len(mappings_before) != 4 or set(mappings_after) != set(mappings_before) | {
        duplicate_uid
    }:
        raise RuntimeError("Timeline-to-pool proxy mapping inventory differs")
    new_mapping = mappings_after[duplicate_uid]
    proxy_uid = new_mapping.get("poolItemUid", {}).get("value")
    if (
        proxy_uid not in added
        or new_mapping.get("timelineName", {}).get("value") != duplicate_name
    ):
        raise RuntimeError("Returned duplicate does not own the unique new pool proxy")
    for uid, row in old_items.items():
        if _usage_free(row) != _usage_free(new_items.get(uid)):
            raise RuntimeError(
                f"Existing media-pool identity changed beyond Usage: {uid}"
            )
    for uid, row in mappings_before.items():
        if _usage_free(row) != _usage_free(mappings_after[uid]):
            raise RuntimeError(f"Existing timeline proxy mapping changed: {uid}")
    proxy = new_items[proxy_uid]
    if proxy.get("name", {}).get("value") != duplicate_name:
        raise RuntimeError("New proxy name differs from the returned duplicate")
    usage_changes = []
    for uid, row in old_items.items():
        old_usage, new_usage = _usage_values(row), _usage_values(new_items[uid])
        for path in sorted(set(old_usage) | set(new_usage)):
            if old_usage.get(path) != new_usage.get(path):
                usage_changes.append(
                    {
                        "poolUid": uid,
                        "path": path,
                        "before": old_usage.get(path),
                        "after": new_usage.get(path),
                    }
                )
    return {"addedTimelineProxyUid": proxy_uid, "usageChanges": usage_changes}


def run(resolve, config, *, probe):
    if (
        config.get("action") != "second-native-duplicate"
        or config.get("externalScriptingSetting") != "None"
        or config.get("projectName")
        != "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
        or not isinstance(R4_PIN_SHA256, str)
        or not R4_PIN_SHA256
        or R4_PIN_NAME.startswith("PENDING")
    ):
        raise RuntimeError(
            "Reviewed selected-R4 state pin is pending or action identity differs"
        )
    output = Path(config.get("outputDir", ""))
    root = Path(probe.ROOT).resolve()
    if (
        not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.resolve().parent != root / "out"
        or not output.name.startswith("issue-141-observation-")
        or resolve.GetProductName() != "DaVinci Resolve Studio"
        or resolve.GetVersion() != BUILD
    ):
        raise RuntimeError("Exact owned Issue 141 Studio project/build/output required")
    pin_path = output / R4_PIN_NAME
    if (
        pin_path.is_symlink()
        or not pin_path.is_file()
        or probe.sha256(pin_path) != R4_PIN_SHA256
    ):
        raise RuntimeError("Reviewed selected-R4 pair pin is missing or changed")
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    identity = {"projectId": PROJECT_ID, "projectName": config["projectName"]}
    media_dir = Path(config.get("mediaDir", ""))
    if (
        not media_dir.is_absolute()
        or media_dir.is_symlink()
        or media_dir.resolve().parent != root / "out"
        or not media_dir.name.startswith("issue-141-media-")
    ):
        raise RuntimeError("Only generated Issue 141 media under out is allowed")
    manifest_path = media_dir / "manifest.json"
    if (
        not manifest_path.is_file()
        or manifest_path.is_symlink()
        or probe.sha256(manifest_path) != config.get("manifestSha256")
    ):
        raise RuntimeError("Generated media manifest is missing or changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {}
    for entry in manifest.get("files", []):
        relative = Path(entry.get("path", ""))
        path = media_dir / relative
        if (
            not relative.parts
            or relative.is_absolute()
            or ".." in relative.parts
            or path.is_symlink()
            or not path.is_file()
            or probe.sha256(path) != entry.get("sha256")
            or path.stat().st_size != entry.get("sizeBytes")
        ):
            raise RuntimeError("Synthetic media differs from its pinned manifest")
        expected[str(path.resolve())] = entry["sha256"]
    if (
        manifest.get("kind") != "generated-synthetic-inputs-not-Resolve-evidence"
        or not expected
    ):
        raise RuntimeError("Only the manifest-bound synthetic media set is permitted")

    def context(selected_uid, timeline_uids):
        project = probe.require_current(resolve, config, identity)
        selected = project.GetCurrentTimeline()
        if selected is None or selected.GetUniqueId() != selected_uid:
            raise RuntimeError(
                "Current timeline differs from the exact selected context"
            )
        if project.GetTimelineCount() != len(timeline_uids):
            raise RuntimeError("Timeline count differs from the guarded inventory")
        observed = {}
        for index in range(1, project.GetTimelineCount() + 1):
            timeline = project.GetTimelineByIndex(index)
            uid, name = timeline.GetUniqueId(), timeline.GetName()
            if (
                uid in observed
                or uid not in timeline_uids
                or name != TIMELINES.get(uid, DUPLICATE_NAME)
            ):
                raise RuntimeError("Timeline UID/name inventory differs")
            observed[uid] = name
        if set(observed) != set(timeline_uids):
            raise RuntimeError("Timeline UID inventory differs")
        return project

    def pair(selected_uid, timeline_uids, label, evidence_dir):
        observations, inventories = [], []
        for _ in range(2):
            try:
                context(selected_uid, timeline_uids)
                observations.append(probe.observe(resolve, config, identity, expected))
            except Exception as error:
                observations.append({"error": f"{type(error).__name__}: {error}"})
            try:
                project = context(selected_uid, timeline_uids)
                inventories.append(probe._r4_pool_inventory(project, expected))
            except Exception as error:
                inventories.append({"error": f"{type(error).__name__}: {error}"})
        payload = {
            "selectedTimelineUid": selected_uid,
            "timelinePasses": observations,
            "poolPasses": inventories,
            "timelineConsistency": "equal-adjacent-reads"
            if observations[0] == observations[1] and not probe.errors(observations)
            else "incomplete-or-inconsistent-refused",
            "poolConsistency": "equal-adjacent-reads"
            if inventories[0] == inventories[1] and not probe.errors(inventories)
            else "incomplete-or-inconsistent-refused",
        }
        _write(evidence_dir / f"{label}.json", payload)
        _record(evidence_dir / "journal.jsonl", "Capture", label, payload)
        if (
            payload["timelineConsistency"] != "equal-adjacent-reads"
            or payload["poolConsistency"] != "equal-adjacent-reads"
        ):
            raise RuntimeError(f"{label} complete timeline/pool pair refused")
        return payload

    if (
        pin.get("selectedTimelineUid") != R4_UID
        or pin.get("timelineConsistency") != "equal-adjacent-reads"
        or pin.get("poolConsistency") != "equal-adjacent-reads"
        or len(pin.get("timelinePasses", [])) != 2
        or len(pin.get("poolPasses", [])) != 2
        or pin["timelinePasses"][0] != pin["timelinePasses"][1]
        or pin["poolPasses"][0] != pin["poolPasses"][1]
        or probe.errors(pin)
    ):
        raise RuntimeError("Selected-R4 pin is incomplete or inconsistent")
    pinned_state, pinned_pool = pin["timelinePasses"][0], pin["poolPasses"][0]
    if (
        pinned_state.get("projectId") != PROJECT_ID
        or pinned_state.get("projectName") != config["projectName"]
    ):
        raise RuntimeError("Selected-R4 pin belongs to another project")
    if {
        row.get("GetUniqueId", {}).get("value"): row.get("GetName", {}).get("value")
        for row in pinned_state.get("timelines", [])
    } != TIMELINES:
        raise RuntimeError("Selected-R4 pin does not contain the exact four timelines")

    selected = probe.require_current(resolve, config, identity).GetCurrentTimeline()
    if selected is None or selected.GetUniqueId() != R4_UID:
        raise RuntimeError("Start only with the pinned R4 timeline selected")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence_dir = output / f"second-duplicate-{timestamp}"
    evidence_dir.mkdir(exist_ok=False)
    journal = evidence_dir / "journal.jsonl"
    journal.touch(exist_ok=False)
    _record(
        journal,
        "SecondDuplicate",
        "start",
        {"sourceTimelineUid": R1_UID, "duplicateName": DUPLICATE_NAME},
    )

    initial = pair(R4_UID, set(TIMELINES), "selected-r4-preflight", evidence_dir)
    if (
        initial["timelinePasses"][0] != pinned_state
        or initial["poolPasses"][0] != pinned_pool
    ):
        raise RuntimeError("Fresh selected-R4 state differs from its reviewed pin")
    project = context(R4_UID, set(TIMELINES))
    source_handles = [
        project.GetTimelineByIndex(i)
        for i in range(1, 5)
        if project.GetTimelineByIndex(i).GetUniqueId() == R1_UID
    ]
    if len(source_handles) != 1 or source_handles[0].GetName() != TIMELINES[R1_UID]:
        raise RuntimeError("Exact six-item R1 source handle is missing")
    if any(
        row.get("GetName", {}).get("value") == DUPLICATE_NAME
        for row in initial["timelinePasses"][0]["timelines"]
    ):
        raise RuntimeError("Second-duplicate name already exists")

    def select(uid, expected_set):
        current_project = context(
            project.GetCurrentTimeline().GetUniqueId(), expected_set
        )
        handles = [
            current_project.GetTimelineByIndex(i)
            for i in range(1, current_project.GetTimelineCount() + 1)
            if current_project.GetTimelineByIndex(i).GetUniqueId() == uid
        ]
        if len(handles) != 1:
            raise RuntimeError("Exact selection handle is missing")
        _record(journal, "Project.SetCurrentTimeline", "request", uid)
        returned = current_project.SetCurrentTimeline(handles[0])
        _record(journal, "Project.SetCurrentTimeline", "return", returned)
        if returned is not True:
            raise RuntimeError("SetCurrentTimeline refused")

    select(R1_UID, set(TIMELINES))
    source_before = pair(
        R1_UID, set(TIMELINES), "selected-r1-before-duplicate", evidence_dir
    )
    source_state = source_before["timelinePasses"][0]
    source_timeline = _timeline_rows(source_state).get(R1_UID)
    if source_timeline is None or len(_occurrences(source_timeline)) != 6:
        raise RuntimeError("Selected R1 source no longer has six readable occurrences")
    source_handles = [
        project.GetTimelineByIndex(index)
        for index in range(1, project.GetTimelineCount() + 1)
        if project.GetTimelineByIndex(index).GetUniqueId() == R1_UID
    ]
    source = source_handles[0] if len(source_handles) == 1 else None
    if (
        source is None
        or source.GetUniqueId() != R1_UID
        or source.GetName() != TIMELINES[R1_UID]
    ):
        raise RuntimeError("Source handle changed before duplication")

    _record(journal, "Timeline.DuplicateTimeline", "request", DUPLICATE_NAME)
    duplicate, duplicate_error = None, None
    try:
        duplicate = source.DuplicateTimeline(DUPLICATE_NAME)
        _record(
            journal,
            "Timeline.DuplicateTimeline",
            "return",
            {
                "GetName": duplicate.GetName() if duplicate else None,
                "GetUniqueId": duplicate.GetUniqueId() if duplicate else None,
            },
        )
    except Exception as error:
        duplicate_error = f"{type(error).__name__}: {error}"
        _record(journal, "Timeline.DuplicateTimeline", "failure", duplicate_error)
        raise
    if duplicate is None or duplicate.GetName() != DUPLICATE_NAME:
        raise RuntimeError(
            "DuplicateTimeline did not return the uniquely named timeline"
        )
    duplicate_uid = duplicate.GetUniqueId()
    if (
        not isinstance(duplicate_uid, str)
        or not duplicate_uid
        or duplicate_uid in TIMELINES
    ):
        raise RuntimeError(
            "DuplicateTimeline returned an invalid or reused timeline UID"
        )
    expected_uids = set(TIMELINES) | {duplicate_uid}
    if project.GetTimelineCount() != 5:
        raise RuntimeError("Expected one new timeline after DuplicateTimeline")
    selected_after_call = project.GetCurrentTimeline()
    if selected_after_call is None or selected_after_call.GetUniqueId() not in {
        R1_UID,
        duplicate_uid,
    }:
        raise RuntimeError("Resolve selected an unexpected timeline after duplication")
    immediate = pair(
        selected_after_call.GetUniqueId(),
        expected_uids,
        "post-duplicate-immediate",
        evidence_dir,
    )
    if set(_timeline_rows(immediate["timelinePasses"][0])) != expected_uids:
        raise RuntimeError("Immediate post-duplicate timeline inventory differs")
    select(duplicate_uid, expected_uids)
    duplicate_context = pair(
        duplicate_uid, expected_uids, "selected-duplicate-postflight", evidence_dir
    )
    after_state = duplicate_context["timelinePasses"][0]
    after_rows = _timeline_rows(after_state)
    if (
        set(after_rows) != expected_uids
        or after_rows[duplicate_uid].get("GetName", {}).get("value") != DUPLICATE_NAME
    ):
        raise RuntimeError(
            "Postflight inventory does not contain exactly the returned duplicate"
        )
    copy_summary = _validate_copy(source_state, after_state, R1_UID, duplicate_uid)
    pool_summary = _validate_additive_pool(
        source_before["poolPasses"][0],
        duplicate_context["poolPasses"][0],
        duplicate_uid,
        DUPLICATE_NAME,
    )

    select(R4_UID, expected_uids)
    final = pair(R4_UID, expected_uids, "restored-r4-postflight", evidence_dir)
    final_state, final_pool = final["timelinePasses"][0], final["poolPasses"][0]
    final_rows = _timeline_rows(final_state)
    expected_names = {**TIMELINES, duplicate_uid: DUPLICATE_NAME}
    if {
        uid: row.get("GetName", {}).get("value") for uid, row in final_rows.items()
    } != expected_names:
        raise RuntimeError("Final timeline UID/name inventory differs")
    pinned_rows = _timeline_rows(pinned_state)
    for uid in TIMELINES:
        if _usage_free(final_rows[uid]) != _usage_free(pinned_rows[uid]):
            raise RuntimeError(f"Original timeline changed beyond Usage: {uid}")
    final_copy_summary = _validate_copy(
        source_state, final_state, R1_UID, duplicate_uid
    )
    final_pool_delta = _validate_additive_pool(
        pinned_pool, final_pool, duplicate_uid, DUPLICATE_NAME
    )
    result = {
        "status": "second-native-duplicate-observed",
        "projectId": PROJECT_ID,
        "sourceTimelineUid": R1_UID,
        "duplicateTimelineUid": duplicate_uid,
        "duplicateName": DUPLICATE_NAME,
        "returnedHandleVerified": True,
        "copiedContent": copy_summary,
        "copiedContentAfterSelectionRestore": final_copy_summary,
        "poolDelta": {**pool_summary, **final_pool_delta},
        "timelineUsageChanges": _usage_delta_rows(pinned_state, final_state),
        "restoredSelectedTimelineUid": R4_UID,
        "journal": str(journal),
        "captures": sorted(path.name for path in evidence_dir.glob("*.json")),
        "limits": [
            "No save/close/reopen or editorial edit; "
            "full R1-repeat lifecycle remains pending.",
            "Copied identical signatures are not occurrence lineage or binding proof.",
            "Equal adjacent reads do not prove atomicity or exclude ABA changes.",
            "Usage and selected-context getter deltas remain observations only.",
        ],
    }
    _write(evidence_dir / "result.json", result)
    _record(journal, "SecondDuplicate", "complete", result)
    return result
