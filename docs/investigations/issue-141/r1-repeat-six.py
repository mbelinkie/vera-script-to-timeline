"""Locally callable, hash-bound R1 reopen, restore, and duplicate actions.

No Resolve connection is created here. A producer supplies the already-bound
Resolve objects and a two-pass observer only after reviewing a fresh checkpoint.
"""

import hashlib
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

PROJECT = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
R1 = "aa2b8e36-83bd-4292-9e33-217c00ca192f"
R1_NAME = "VERA 141 R1 identity"
REPEAT_NAME = "VERA 141 R1 identity repeat"
MATRIX = "29ae8331-b86e-4041-a548-960695cc7b24"
REFERENCE_PAIR = (
    Path(__file__).resolve().parents[3] / "out/issue-141-observation-20260930-01a0f318/"
    "protected-six-r4-pool-20261001T180848.009764Z/pair.json"
)
REFERENCE_PAIR_SHA256 = (
    "5131589527428829afe6e1503e245609a4f17bb3207a2fe61a874db4289601b3"
)
TIMELINES = {
    "88f7923d-55a7-471f-b09b-cf10f9fae8ad": "VERA 141 Baseline",
    R1: R1_NAME,
    "29ae8331-b86e-4041-a548-960695cc7b24": "VERA 141 Batched Matrix",
    "64de8a4c-86bd-4f19-9d20-47b8940f610b": "VERA 141 R4 availability",
    "21436b8f-057c-49e6-80ba-5f733abe87b2": "transcription test 1",
    "2db0b2d1-6d81-48d4-b49c-360f56e012cd": "transcription test 2",
}
PROBE_SNAPSHOT = (
    Path(__file__).resolve().parents[3]
    / "out/issue-141-observation-20260930-01a0f318/"
    "r1-repeat-six-probe-snapshot-54bbbeee926a.py"
)
PROBE_SNAPSHOT_SHA256 = (
    "54bbbeee926a5ef423615b1f981ec8ebe6586e91f938a8aad05db441ecc53310"
)
READER_SHA256 = "9b6977747a1f3decf957ead6134f10fc4f597bf9d0c3dc5c081b7bf2671879a4"
ACTION_REOPEN = "r1-repeat-reopen"
ACTION_DUPLICATE = "r1-repeat-duplicate"
ACTION_RESTORE_SELECTION = "r1-repeat-restore-selection"
BUILD = [21, 1, 0, 14, ""]
PROTECTED_SEVEN = "protected-seven"


def digest(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _journal(path, action, phase, value):
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "action": action,
                    "phase": phase,
                    "value": value,
                },
                sort_keys=True,
            )
            + "\n"
        )


def _exclusive_journal(path):
    with Path(path).open("x", encoding="utf-8"):
        pass


def _load_private(path, expected_hash, name):
    if path.is_symlink() or digest(path) != expected_hash:
        raise RuntimeError(f"Pinned {name} changed")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _private_reader(here):
    repository_root = Path(__file__).resolve().parents[3]
    probe = _load_private(PROBE_SNAPSHOT, PROBE_SNAPSHOT_SHA256, "probe snapshot")
    probe.ROOT = repository_root
    reader = _load_private(here / "r4-range-repair.py", READER_SHA256, "reader")
    return probe, reader


def _native_context(resolve, project, selected_uid, probe, expected):
    current = project.GetCurrentTimeline()
    return {
        "product": resolve.GetProductName(),
        "version": resolve.GetVersion(),
        "projectUid": project.GetUniqueId(),
        "projectName": project.GetName(),
        "page": resolve.GetCurrentPage(),
        "idle": project.IsRenderingInProgress() is False,
        "queue": project.GetRenderJobList(),
        "selectedTimelineUid": None if current is None else current.GetUniqueId(),
        "playhead": None if current is None else current.GetCurrentTimecode(),
        "selection": None if current is None else [
            probe.item_evidence(item, expected) for item in current.GetSelectedClips()
        ],
        "trackLocks": None if current is None else [
            [kind, i, current.GetIsTrackLocked(kind, i)]
            for kind in ("video", "audio", "subtitle")
            for i in range(1, current.GetTrackCount(kind) + 1)
        ],
        "expectedSelectionUid": selected_uid,
    }


def _context_guard(value, expected_uid):
    if (
        value["product"] != "DaVinci Resolve Studio"
        or value["version"] != BUILD
        or value["projectUid"] != PROJECT
        or value["projectName"] != "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
        or value["page"] != "edit"
        or value["idle"] is not True
        or value["queue"] != []
        or value["selectedTimelineUid"] != expected_uid
        or not isinstance(value["playhead"], str)
        or not isinstance(value["selection"], list)
        or not isinstance(value["trackLocks"], list)
    ):
        raise RuntimeError("Observed Resolve context differs from the exact R1 preflight")


def run(resolve, config, *, probe):
    """Dispatcher entry point for the separately selected R1 actions."""
    here = Path(__file__).resolve().parent
    output = Path(config.get("outputDir", ""))
    action = config.get("action")
    if (
        action not in {ACTION_REOPEN, ACTION_DUPLICATE, ACTION_RESTORE_SELECTION}
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute() or output.is_symlink() or not output.is_dir()
        or output.parent.resolve() != Path(probe.ROOT).resolve() / "out"
        or not output.name.startswith("issue-141-observation-")
    ):
        raise RuntimeError("Exact isolated R1 repeat action and output directory required")
    checkpoint = Path(config.get("repeatCheckpoint", ""))
    if (
        not checkpoint.is_absolute()
        or checkpoint.is_symlink()
        or not checkpoint.is_file()
        or checkpoint.resolve().parent != output.resolve()
    ):
        raise RuntimeError("R1 checkpoint must be directly inside outputDir")
    target_pair_path = None
    target_pair_sha256 = None
    target_context_pin = None
    if action == ACTION_RESTORE_SELECTION:
        target_pair_path = Path(config.get("restoreTargetPair", ""))
        target_pair_sha256 = config.get("restoreTargetPairSha256")
        target_context_pin = config.get("restoreTargetContext")
        if (
            not target_pair_path.is_absolute()
            or target_pair_path.is_symlink()
            or not target_pair_path.is_file()
            or target_pair_path.resolve().parent != output.resolve()
            or not isinstance(target_pair_sha256, str)
            or len(target_pair_sha256) != 64
            or not isinstance(target_context_pin, dict)
        ):
            raise RuntimeError(
                "Restore target pair/hash/context pins must be directly inside outputDir"
            )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence = output / f"{action}-{stamp}"
    evidence.mkdir(exist_ok=False)
    journal = evidence / "journal.jsonl"
    journal.touch(exist_ok=False)
    raw = evidence / "raw.json"
    status = evidence / "result.json"
    def retain(phase, value):
        _journal(journal, action, phase, value)
    try:
        expected_hash = config.get("repeatCheckpointSha256")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise RuntimeError("Checkpoint SHA-256 pin is required")
        private_probe, reader = _private_reader(here)
        _, expected = reader._manifest(config, Path(probe.ROOT).resolve(), private_probe)
        identity = {"projectId": PROJECT, "projectName": config.get("projectName")}
        selected = R1 if action == ACTION_RESTORE_SELECTION else MATRIX
        project = private_probe.require_current(resolve, config, identity)
        capture_index = 0
        def observe(selected_uid):
            nonlocal capture_index
            capture_index += 1
            retain("capture-request", {"index": capture_index, "selectedTimelineUid": selected_uid})
            current_project = resolve.GetProjectManager().GetCurrentProject()
            if current_project is None:
                raise RuntimeError("Named project is not currently loaded")
            native = _native_context(resolve, current_project, selected_uid, private_probe, expected)
            _context_guard(native, selected_uid)
            retain("native-context", native)
            count = current_project.GetTimelineCount()
            extended = count == 7
            if count not in {6, 7}:
                raise RuntimeError("Unknown or incomplete timeline inventory")
            if extended:
                duplicate_rows = [current_project.GetTimelineByIndex(i) for i in range(1, 8)]
                extras = [row for row in duplicate_rows if row.GetUniqueId() not in TIMELINES]
                if len(extras) != 1 or extras[0].GetName() != REPEAT_NAME:
                    raise RuntimeError("Unexpected seventh timeline identity")
                seven = {**TIMELINES, extras[0].GetUniqueId(): REPEAT_NAME}
                private_probe.PROTECTED_INVENTORY = PROTECTED_SEVEN
                private_probe.PROTECTED_TIMELINE_IDENTITIES = seven
                reader.PROTECTED_INVENTORY = PROTECTED_SEVEN
                reader.PROTECTED_TIMELINE_IDENTITIES = seven
            mode = PROTECTED_SEVEN if extended else "protected-six"
            pair = reader._read_pair(resolve, {**config, "timelineInventory": mode}, identity,
                                     expected, selected_uid, private_probe)
            capture_path = evidence / f"pair-{capture_index:02d}.json"
            capture_path.write_text(json.dumps({"nativeContext": native, "pair": pair}, indent=2, sort_keys=True), encoding="utf-8")
            retain("capture-return", {"path": str(capture_path), "pair": pair})
            return pair

        observed = observe(selected)
        contexts = [_native_context(resolve, project, selected, private_probe, expected) for _ in range(2)]
        context = contexts[0]
        payload = {"checkpointPath": str(checkpoint), "checkpointSha256": expected_hash,
                   "contextPasses": contexts, "beforePair": observed}
        if action == ACTION_RESTORE_SELECTION:
            payload.update(
                {
                    "restoreTargetPairPath": str(target_pair_path),
                    "restoreTargetPairSha256": target_pair_sha256,
                    "restoreTargetContext": target_context_pin,
                }
            )
        raw.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        retain("preflight-capture", payload)
        _context_guard(context, selected)
        if contexts[0] != contexts[1]:
            raise RuntimeError("Native context changed between adjacent reads")
        if config.get("repeatExpectedContext") != context:
            raise RuntimeError("Native context differs from its explicit request pin")
        _pair(checkpoint, expected_hash, lambda: observed, selected)
        rows = {r.get("GetUniqueId", {}).get("value"): r.get("GetName", {}).get("value")
                for r in observed["timelinePasses"][0].get("timelines", [])}
        if rows != TIMELINES or observed.get("timelineInventory") != "protected-six":
            raise RuntimeError("Checkpoint/current state must contain exactly the original six")
        action_args = dict(idle=context["idle"], controls_unchanged=contexts[0]["trackLocks"] == contexts[1]["trackLocks"],
                           context_unchanged=contexts[0] == contexts[1], resolve_build="21.1.0 build 14",
                           external_scripting="None")
        if action == ACTION_REOPEN:
            result = repeat_reopen(resolve, project, checkpoint, expected_hash,
                                   lambda: observe(MATRIX),
                                   journal, **action_args)
        elif action == ACTION_DUPLICATE:
            result = second_duplicate(project, checkpoint, expected_hash,
                                      lambda: observe(project.GetCurrentTimeline().GetUniqueId()),
                                      journal, **action_args)
        else:
            target_pair = _restore_target_pair(
                target_pair_path, target_pair_sha256, target_context_pin
            )
            result = restore_selection(
                project,
                checkpoint,
                expected_hash,
                lambda: observe(R1),
                lambda: observe(MATRIX),
                lambda: _native_context(
                    resolve, project, MATRIX, private_probe, expected
                ),
                target_pair,
                target_context_pin,
                journal,
                **action_args,
            )
        status.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        return result
    except Exception as error:
        retain("failure", f"{type(error).__name__}: {error}")
        status.write_text(json.dumps({"status": "refused", "error": f"{type(error).__name__}: {error}",
                                      "rawCapture": str(raw) if raw.exists() else None}, indent=2), encoding="utf-8")
        raise


def _validate_pair(pair, selected_uid, description):
    if (
        pair.get("selectedTimelineUid") != selected_uid
        or pair.get("timelineConsistency") != "equal-adjacent-reads"
        or pair.get("poolConsistency") != "equal-adjacent-reads"
        or len(pair.get("timelinePasses", [])) != 2
        or len(pair.get("poolPasses", [])) != 2
        or pair["timelinePasses"][0] != pair["timelinePasses"][1]
        or pair["poolPasses"][0] != pair["poolPasses"][1]
    ):
        raise RuntimeError(f"{description} is not a stable selected six-timeline pair")
    state = pair["timelinePasses"][0]
    if (
        state.get("projectId") != PROJECT
        or state.get("projectName")
        != "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
    ):
        raise RuntimeError(f"{description} project UID differs")
    if pair.get("timelineInventory") != "protected-six":
        raise RuntimeError(f"{description} is not explicitly marked protected-six")
    rows = {
        r.get("GetUniqueId", {}).get("value"): r.get("GetName", {}).get("value")
        for r in state.get("timelines", [])
    }
    if rows != TIMELINES or len(pair["poolPasses"][0].get("items", [])) < 1:
        raise RuntimeError(f"{description} protected-six inventory differs")
    if digest(REFERENCE_PAIR) != REFERENCE_PAIR_SHA256:
        raise RuntimeError("retained R1 signature reference hash differs")
    reference = json.loads(REFERENCE_PAIR.read_text(encoding="utf-8"))
    if _r1_signature(reference) != _r1_signature(pair):
        raise RuntimeError(f"{description} R1 content/source/range signature differs")


def _load_pair(path, sha256, selected_uid, description):
    if digest(path) != sha256:
        raise RuntimeError("checkpoint SHA-256 differs")
    pin = json.loads(Path(path).read_text(encoding="utf-8"))
    _validate_pair(pin, selected_uid, description)
    return pin


def _restore_target_pair(path, sha256, context):
    pair = _load_pair(path, sha256, MATRIX, "restore target pair")
    _context_guard(context, MATRIX)
    return pair


def _pair(path, sha256, observe, selected_uid):
    pin = _load_pair(path, sha256, selected_uid, "checkpoint")
    state = pin["timelinePasses"][0]
    current = observe()
    if (
        current.get("timelineConsistency") != "equal-adjacent-reads"
        or current.get("poolConsistency") != "equal-adjacent-reads"
        or current.get("selectedTimelineUid") != selected_uid
    ):
        raise RuntimeError("fresh before pair is inconsistent or wrong selection")
    if (
        current["timelinePasses"][0] != state
        or current["poolPasses"][0] != pin["poolPasses"][0]
    ):
        raise RuntimeError("fresh pair differs from hash-bound checkpoint")
    return pin, current


def _postload_guard(pair):
    if (
        pair.get("selectedTimelineUid") != MATRIX
        or pair.get("timelineInventory") != "protected-six"
        or pair.get("timelineConsistency") != "equal-adjacent-reads"
        or pair.get("poolConsistency") != "equal-adjacent-reads"
        or len(pair.get("timelinePasses", [])) != 2
        or len(pair.get("poolPasses", [])) != 2
        or pair["timelinePasses"][0] != pair["timelinePasses"][1]
        or pair["poolPasses"][0] != pair["poolPasses"][1]
    ):
        raise RuntimeError(
            "post-load pair is inconsistent, incomplete, or wrongly selected"
        )
    state = pair["timelinePasses"][0]
    rows = {
        row.get("GetUniqueId", {}).get("value"): row.get("GetName", {}).get("value")
        for row in state.get("timelines", [])
    }
    if (
        state.get("projectId") != PROJECT
        or state.get("projectName")
        != "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
        or rows != TIMELINES
    ):
        raise RuntimeError(
            "post-load project identity or protected-six inventory differs"
        )
    reference = json.loads(REFERENCE_PAIR.read_text(encoding="utf-8"))
    if _r1_signature(reference) != _r1_signature(pair):
        raise RuntimeError("post-load R1 content/source/range signature differs")


def _postduplicate_guard(pair, duplicate_uid, allowed_selection):
    if (
        pair.get("selectedTimelineUid") not in allowed_selection
        or pair.get("timelineInventory") != PROTECTED_SEVEN
        or pair.get("timelineConsistency") != "equal-adjacent-reads"
        or pair.get("poolConsistency") != "equal-adjacent-reads"
        or len(pair.get("timelinePasses", [])) != 2
        or len(pair.get("poolPasses", [])) != 2
        or pair["timelinePasses"][0] != pair["timelinePasses"][1]
        or pair["poolPasses"][0] != pair["poolPasses"][1]
    ):
        raise RuntimeError(
            "post-duplicate seven-timeline pair inconsistent or incomplete"
        )
    state = pair["timelinePasses"][0]
    rows = {
        row.get("GetUniqueId", {}).get("value"): row.get("GetName", {}).get("value")
        for row in state.get("timelines", [])
    }
    if (
        state.get("projectId") != PROJECT
        or state.get("projectName")
        != "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
        or rows != {**TIMELINES, duplicate_uid: REPEAT_NAME}
    ):
        raise RuntimeError(
            "post-duplicate identity or seven-timeline inventory differs"
        )


def _guard(project, selected_uid, idle, controls_unchanged, context_unchanged):
    if not idle or not controls_unchanged or not context_unchanged:
        raise RuntimeError("job, controls, or operator context guard refused")
    if project is None or project.GetUniqueId() != PROJECT:
        raise RuntimeError("current project UID differs")
    selected = project.GetCurrentTimeline()
    if selected is None or selected.GetUniqueId() != selected_uid:
        raise RuntimeError("selected timeline UID differs")


def _classify(left, right):
    """Report deltas verbatim by timeline; Usage is labeled, never discarded."""
    a = {r.get("GetUniqueId", {}).get("value"): r for r in left.get("timelines", [])}
    b = {r.get("GetUniqueId", {}).get("value"): r for r in right.get("timelines", [])}
    deltas, usage_paths, other_paths = [], [], []

    def walk(a_value, b_value, path):
        if isinstance(a_value, dict) and isinstance(b_value, dict):
            for key in sorted(set(a_value) | set(b_value)):
                walk(a_value.get(key), b_value.get(key), f"{path}/{key}")
        elif isinstance(a_value, list) and isinstance(b_value, list):
            for index in range(max(len(a_value), len(b_value))):
                walk(
                    a_value[index] if index < len(a_value) else None,
                    b_value[index] if index < len(b_value) else None,
                    f"{path}/{index}",
                )
        elif a_value != b_value:
            (usage_paths if path.endswith("/Usage") else other_paths).append(path)

    for uid in sorted(set(a) | set(b)):
        if a.get(uid) != b.get(uid):
            start = len(usage_paths), len(other_paths)
            walk(a.get(uid), b.get(uid), f"timeline/{uid}")
            deltas.append(
                {
                    "timelineUid": uid,
                    "usagePaths": usage_paths[start[0] :],
                    "otherPaths": other_paths[start[1] :],
                    "before": a.get(uid),
                    "after": b.get(uid),
                }
            )
    return {
        "deltas": deltas,
        "usageOnly": bool(deltas) and bool(usage_paths) and not other_paths,
        "usagePaths": usage_paths,
        "otherPaths": other_paths,
        "unchangedIdentities": set(a) == set(b),
    }


def _without_usage(value):
    if isinstance(value, dict):
        return {
            key: _without_usage(child) for key, child in value.items() if key != "Usage"
        }
    if isinstance(value, list):
        return [_without_usage(child) for child in value]
    return value


def _r1_signature(pair):
    row = next(
        row
        for row in pair["timelinePasses"][0]["timelines"]
        if row.get("GetUniqueId", {}).get("value") == R1
    )
    signature = _without_usage(
        {key: value for key, value in row.items() if key != "GetSettings"}
    )
    # ponytail: these getters vary with active timeline; retain raw captures,
    # and use same-context pairs for control/effect preservation decisions.
    for track in signature.get("tracks", []):
        track.pop("GetIsTrackEnabled", None)
        track.pop("GetIsTrackLocked", None)
        if track.get("type") == "audio":
            for item in track.get("items", []):
                properties = item.get("GetProperties", {}).get("value", {})
                if isinstance(properties, dict):
                    for key in (
                        "AudioDialogueLevelerBackgroundReduction",
                        "AudioDialogueLevelerEnabled",
                        "AudioDialogueLevelerLiftSoftDialogue",
                        "AudioDialogueLevelerMode",
                        "AudioDialogueLevelerOutputGain",
                        "AudioDialogueLevelerReduceLoudDialogue",
                        "AudioVoiceIsolationAmount",
                        "AudioVoiceIsolationEnabled",
                    ):
                        properties.pop(key, None)
    return signature


def _occurrences(row):
    values = []
    for track in row.get("tracks", []):
        for item in track.get("items", []):
            uid = item.get("GetUniqueId", {}).get("value")
            media = item.get("GetMediaPoolItem", {}).get("GetUniqueId", {}).get("value")
            if not isinstance(uid, str) or not isinstance(media, str):
                raise RuntimeError("occurrence/source UID unavailable")
            signature = {
                "trackType": track.get("type"),
                "trackIndex": track.get("index"),
                "trackName": track.get("GetTrackName"),
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
                "mediaUid": media,
            }
            values.append((uid, media, signature))
    return values


def restore_selection(
    project,
    checkpoint,
    checkpoint_sha256,
    observe_current,
    observe_matrix,
    observe_context,
    target_pair,
    target_context,
    journal,
    *,
    idle,
    controls_unchanged,
    context_unchanged,
    resolve_build,
    external_scripting,
):
    """Restore Matrix once from a retained, hash-bound selected-R1 refusal."""
    if resolve_build != "21.1.0 build 14" or external_scripting != "None":
        raise RuntimeError("Resolve build or External Scripting setting differs")
    _validate_pair(target_pair, MATRIX, "restore target pair")
    _context_guard(target_context, MATRIX)
    pin, before = _pair(checkpoint, checkpoint_sha256, observe_current, R1)
    _guard(project, R1, idle, controls_unchanged, context_unchanged)
    matrix_handles = [
        project.GetTimelineByIndex(index)
        for index in range(1, project.GetTimelineCount() + 1)
        if project.GetTimelineByIndex(index).GetUniqueId() == MATRIX
    ]
    if len(matrix_handles) != 1:
        raise RuntimeError("exact Matrix selection handle unavailable")
    _journal(journal, "SetCurrentTimeline", "request", MATRIX)
    try:
        if project.SetCurrentTimeline(matrix_handles[0]) is not True:
            raise RuntimeError("selection restoration refused; no retry")
    except Exception as error:
        try:
            _journal(journal, "selectionFailureCapture", "return", observe_current())
        except Exception as capture_error:
            _journal(
                journal,
                "selectionFailureCapture",
                "failure",
                f"{type(capture_error).__name__}: {capture_error}",
            )
        _journal(
            journal, "SetCurrentTimeline", "failure", f"{type(error).__name__}: {error}"
        )
        raise
    _journal(journal, "SetCurrentTimeline", "return", MATRIX)
    after = observe_matrix()
    _journal(journal, "restoredSelectionPair", "return", after)
    after_context = observe_context()
    _journal(journal, "restoredSelectionContext", "return", after_context)
    _context_guard(after_context, MATRIX)
    if after != target_pair:
        raise RuntimeError("restored Matrix pair differs from pinned original Matrix pair")
    if after_context != target_context:
        raise RuntimeError("restored Matrix context differs from pinned original context")
    result = {
        "kind": "local-r1-selection-restoration-result",
        "projectUid": PROJECT,
        "fromSelectedTimelineUid": R1,
        "targetTimelineUid": MATRIX,
        "before": before,
        "retainedCheckpoint": pin,
        "targetPair": target_pair,
        "targetContext": target_context,
        "after": after,
        "afterContext": after_context,
        "pairExactlyEqual": True,
        "contextExactlyEqual": True,
        "selectedTimelineUid": after.get("selectedTimelineUid"),
        "status": "restored-selection",
        "nativeMutation": "SetCurrentTimeline",
        "mutationCount": 1,
        "noSaveRenderClipLockOrPlayheadMutation": True,
    }
    _journal(journal, ACTION_RESTORE_SELECTION, "result", result)
    return result


def repeat_reopen(
    resolve,
    project,
    checkpoint,
    checkpoint_sha256,
    observe,
    journal,
    *,
    idle,
    controls_unchanged,
    context_unchanged,
    resolve_build,
    external_scripting,
):
    """One guarded Save/Close/Load and two retained post-load observations."""
    selected_uid = MATRIX
    if resolve_build != "21.1.0 build 14" or external_scripting != "None":
        raise RuntimeError("Resolve build or External Scripting setting differs")
    pin, before = _pair(checkpoint, checkpoint_sha256, observe, selected_uid)
    _guard(project, selected_uid, idle, controls_unchanged, context_unchanged)
    manager = resolve.GetProjectManager()
    _journal(journal, "SaveProject", "request", PROJECT)
    try:
        if manager.SaveProject() is not True:
            raise RuntimeError("SaveProject refused; no retry")
    except Exception as error:
        _journal(journal, "SaveProject", "failure", f"{type(error).__name__}: {error}")
        raise
    _journal(journal, "SaveProject", "return", True)
    _journal(journal, "CloseProject", "request", PROJECT)
    try:
        if manager.CloseProject(project) is not True:
            raise RuntimeError("CloseProject refused; no retry")
    except Exception as error:
        _journal(journal, "CloseProject", "failure", f"{type(error).__name__}: {error}")
        raise
    _journal(journal, "CloseProject", "return", True)
    _journal(
        journal,
        "LoadProject",
        "request",
        "VERA Issue 141 Synthetic Probe 20260930-01a0f318",
    )
    try:
        loaded = manager.LoadProject("VERA Issue 141 Synthetic Probe 20260930-01a0f318")
    except Exception as error:
        _journal(journal, "LoadProject", "failure", f"{type(error).__name__}: {error}")
        raise
    _journal(
        journal,
        "LoadProject",
        "return",
        None
        if loaded is None
        else {"projectUid": loaded.GetUniqueId(), "projectName": loaded.GetName()},
    )
    current_project = manager.GetCurrentProject()
    if (
        loaded is None
        or current_project is None
        or loaded.GetUniqueId() != PROJECT
        or loaded.GetName() != "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
        or current_project.GetUniqueId() != PROJECT
        or current_project.GetName()
        != "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
    ):
        raise RuntimeError("LoadProject refused; no retry")
    first, second = observe(), observe()
    _journal(journal, "postLoadPair", "first", first)
    _journal(journal, "postLoadPair", "second", second)
    _postload_guard(first)
    _postload_guard(second)
    result = {
        "kind": "local-r1-repeat-reopen-result",
        "projectUid": PROJECT,
        "before": before,
        "retainedCheckpoint": pin,
        "postLoadObservations": [first, second],
        "passClassification": _classify(
            first.get("timelinePasses", [{}])[0], second.get("timelinePasses", [{}])[0]
        ),
        "consistent": first == second,
        "status": "stable-pair" if first == second else "inconsistent-retained",
    }
    _journal(journal, "reopen", "result", result)
    return result


def second_duplicate(
    project,
    checkpoint,
    checkpoint_sha256,
    observe,
    journal,
    *,
    idle,
    controls_unchanged,
    context_unchanged,
    resolve_build,
    external_scripting,
):
    """One additive duplicate; retains six originals and never cleans up."""
    if resolve_build != "21.1.0 build 14" or external_scripting != "None":
        raise RuntimeError("Resolve build or External Scripting setting differs")
    pin, before = _pair(checkpoint, checkpoint_sha256, observe, MATRIX)
    _guard(project, MATRIX, idle, controls_unchanged, context_unchanged)
    if any(
        r.get("GetName", {}).get("value") == REPEAT_NAME
        for r in before["timelinePasses"][0]["timelines"]
    ):
        raise RuntimeError("repeat name already exists")
    source = [
        project.GetTimelineByIndex(i)
        for i in range(1, 7)
        if project.GetTimelineByIndex(i).GetUniqueId() == R1
    ]
    if len(source) != 1 or source[0].GetName() != R1_NAME:
        raise RuntimeError("exact R1 source handle unavailable")
    _journal(journal, "SetCurrentTimeline", "request", R1)
    try:
        if project.SetCurrentTimeline(source[0]) is not True:
            raise RuntimeError("exact R1 selection refused; no duplicate attempted")
    except Exception as error:
        try:
            _journal(journal, "selectionFailureCapture", "return", observe())
        except Exception as capture_error:
            _journal(journal, "selectionFailureCapture", "failure", f"{type(capture_error).__name__}: {capture_error}")
        _journal(
            journal, "SetCurrentTimeline", "failure", f"{type(error).__name__}: {error}"
        )
        raise
    _journal(journal, "SetCurrentTimeline", "return", R1)
    selected_pair = observe()
    _journal(journal, "selectedSourcePair", "return", selected_pair)
    if (
        selected_pair.get("selectedTimelineUid") != R1
        or selected_pair.get("timelineConsistency") != "equal-adjacent-reads"
        or selected_pair.get("poolConsistency") != "equal-adjacent-reads"
    ):
        raise RuntimeError("selected R1 capture refused; no duplicate attempted")
    if _r1_signature(pin) != _r1_signature(selected_pair):
        raise RuntimeError(
            "selected R1 source signature changed; no duplicate attempted"
        )
    _journal(
        journal, "DuplicateTimeline", "request", {"sourceUid": R1, "name": REPEAT_NAME}
    )
    try:
        duplicate = source[0].DuplicateTimeline(REPEAT_NAME)
    except Exception as error:
        try:
            _journal(journal, "duplicateFailureCapture", "return", observe())
        except Exception as capture_error:
            _journal(journal, "duplicateFailureCapture", "failure", f"{type(capture_error).__name__}: {capture_error}")
        _journal(
            journal, "DuplicateTimeline", "failure", f"{type(error).__name__}: {error}"
        )
        raise
    if duplicate is None:
        _journal(journal, "DuplicateTimeline", "return", None)
        raise RuntimeError("duplicate returned no timeline; preserve state, no retry")
    duplicate_uid, duplicate_name = duplicate.GetUniqueId(), duplicate.GetName()
    _journal(journal, "DuplicateTimeline", "return", {"uid": duplicate_uid, "name": duplicate_name})
    if duplicate_name != REPEAT_NAME:
        raise RuntimeError("duplicate return/name invalid; preserve state, no retry")
    if not duplicate_uid or duplicate_uid in TIMELINES:
        raise RuntimeError("duplicate UID invalid or reused")
    immediate = observe()
    _journal(journal, "immediateAfterPair", "return", immediate)
    _postduplicate_guard(immediate, duplicate_uid, {R1, duplicate_uid})
    current_uids = [
        project.GetTimelineByIndex(i).GetUniqueId()
        for i in range(1, project.GetTimelineCount() + 1)
    ]
    matrix_handles = [
        project.GetTimelineByIndex(i)
        for i in range(1, project.GetTimelineCount() + 1)
        if project.GetTimelineByIndex(i).GetUniqueId() == MATRIX
    ]
    if len(matrix_handles) != 1 or MATRIX not in current_uids:
        raise RuntimeError(
            "original Matrix selection handle unavailable after duplicate"
        )
    _journal(journal, "SetCurrentTimeline", "request", MATRIX)
    try:
        if project.SetCurrentTimeline(matrix_handles[0]) is not True:
            raise RuntimeError("selection restoration refused; duplicate preserved")
    except Exception as error:
        try:
            _journal(journal, "selectionRestoreFailureCapture", "return", observe())
        except Exception as capture_error:
            _journal(journal, "selectionRestoreFailureCapture", "failure", f"{type(capture_error).__name__}: {capture_error}")
        _journal(
            journal, "SetCurrentTimeline", "failure", f"{type(error).__name__}: {error}"
        )
        raise
    _journal(journal, "SetCurrentTimeline", "return", MATRIX)
    after = observe()
    _journal(journal, "restoredSelectionPair", "return", after)
    _postduplicate_guard(after, duplicate_uid, {MATRIX})
    old_rows = {
        r.get("GetUniqueId", {}).get("value"): r
        for r in before["timelinePasses"][0]["timelines"]
    }
    new_rows = {
        r.get("GetUniqueId", {}).get("value"): r
        for r in after["timelinePasses"][0]["timelines"]
    }
    if any(
        _without_usage(old_rows[uid]) != _without_usage(new_rows[uid])
        for uid in TIMELINES
    ):
        raise RuntimeError("original timeline changed; retain full before/after")
    source_row, duplicate_row = old_rows[R1], new_rows[duplicate_uid]
    source_occurrences = _occurrences(source_row)
    duplicate_occurrences = _occurrences(duplicate_row)
    if (
        len(source_occurrences) != len(duplicate_occurrences)
        or {media for _, media, _ in source_occurrences}
        != {media for _, media, _ in duplicate_occurrences}
        or {uid for uid, _, _ in source_occurrences}
        & {uid for uid, _, _ in duplicate_occurrences}
        or sorted(json.dumps(sig, sort_keys=True) for _, _, sig in source_occurrences)
        != sorted(
            json.dumps(sig, sort_keys=True) for _, _, sig in duplicate_occurrences
        )
    ):
        raise RuntimeError(
            "duplicate occurrence/source identities differ; preserve captures"
        )
    result = {
        "kind": "local-r1-second-duplicate-result",
        "projectUid": PROJECT,
        "sourceUid": R1,
        "duplicateUid": duplicate_uid,
        "duplicateName": REPEAT_NAME,
        "before": before,
        "selectedSourcePair": selected_pair,
        "immediateAfter": immediate,
        "after": after,
        "retainedCheckpoint": pin,
        "oldSixPreserved": True,
        "sourceSignature": source_row,
        "duplicateSignature": duplicate_row,
        "sourceOccurrenceIds": [uid for uid, _, _ in source_occurrences],
        "newOccurrenceIds": [uid for uid, _, _ in duplicate_occurrences],
        "sourceSharedMediaUids": sorted({media for _, media, _ in source_occurrences}),
        "identicalSignatureAmbiguity": True,
        "selectedTimelineUid": after.get("selectedTimelineUid"),
        "usageDeltas": _classify(
            before["timelinePasses"][0], after["timelinePasses"][0]
        ),
        "limits": [
            "Occurrence signatures do not establish lineage.",
            "This result makes no broad identity-lineage claim.",
        ],
    }
    _journal(journal, "DuplicateTimeline", "result", result)
    return result
