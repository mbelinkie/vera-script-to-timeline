"""One guarded start-timecode repair for the existing Issue 141 R4 timeline."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
BUILD = [21, 1, 0, 14, ""]
MATRIX_UID = "29ae8331-b86e-4041-a548-960695cc7b24"
MATRIX_NAME = "VERA 141 Batched Matrix"
R4_UID = "64de8a4c-86bd-4f19-9d20-47b8940f610b"
R4_NAME = "VERA 141 R4 availability"
PROTECTED_INVENTORY = "protected-six"
TIMELINE_IDENTITIES = {
    MATRIX_UID: MATRIX_NAME,
    R4_UID: R4_NAME,
    "88f7923d-55a7-471f-b09b-cf10f9fae8ad": "VERA 141 Baseline",
    "aa2b8e36-83bd-4292-9e33-217c00ca192f": "VERA 141 R1 identity",
}
PROTECTED_TIMELINE_IDENTITIES = {
    **TIMELINE_IDENTITIES,
    "21436b8f-057c-49e6-80ba-5f733abe87b2": "transcription test 1",
    "2db0b2d1-6d81-48d4-b49c-360f56e012cd": "transcription test 2",
}
R4_POOL_UID = "91853c24-9e0c-435c-8550-209a76425270"
MEDIA_UID = "81d81dc0-4c37-478b-8079-03debba5e780"
ITEM_UID = "af55478a-0ba3-458a-a6e1-e47b2544111d"
ORIGINAL_TIMECODE = "01:00:00:00"
TARGET_TIMECODE = "00:00:00:00"
MATRIX_PIN = "matrix-checkpoint-20261001T015209.473668Z-matrix-observation.json"
MATRIX_SHA256 = "0220a23be312aea5906900dd094c8e21b363294bb11f9b0f1201ab23f40c4cbf"
R4_CAPTURE_PIN = "capture-20261001T003310.397326Z.json"
R4_CAPTURE_SHA256 = "f3a321fcd5ae47c90e25b3dcf254a0d983ff0bdde8862700b2411c710b3fe0fa"
R4_POOL_PIN = "r4-pool-read-only-20261001T003310.397326Z.json"
R4_POOL_SHA256 = "ac6f4661f59f910029dae51dcc758bd1d766e8f810fb4996fcee1b18c681e751"


def _sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


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


def _canonical(value):
    return json.loads(json.dumps(value, allow_nan=False))


def _timeline(state, uid):
    rows = [
        row
        for row in state.get("timelines", [])
        if row.get("GetUniqueId", {}).get("value") == uid
    ]
    if len(rows) != 1:
        raise RuntimeError("Pinned timeline identity is missing or duplicated")
    return rows[0]


def _pin(path, name, digest, probe):
    if (
        path.name != name
        or path.is_symlink()
        or not path.is_file()
        or probe.sha256(path) != digest
    ):
        raise RuntimeError(f"Exact pinned evidence is missing or changed: {name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _equal_pair(rows, probe, label):
    if (
        not isinstance(rows, list)
        or len(rows) != 2
        or rows[0] != rows[1]
        or probe.errors(rows)
    ):
        raise RuntimeError(f"{label} pair is incomplete or inconsistent")
    return rows[0]


def _manifest(config, root, probe):
    media = Path(config.get("mediaDir", ""))
    if (
        not media.is_absolute()
        or media.is_symlink()
        or media.parent.resolve() != (root / "out").resolve()
        or not media.name.startswith("issue-141-media-")
    ):
        raise RuntimeError("Only generated issue-141 media under out is allowed")
    manifest_path = media / "manifest.json"
    if (
        manifest_path.is_symlink()
        or not manifest_path.is_file()
        or probe.sha256(manifest_path) != config.get("manifestSha256")
    ):
        raise RuntimeError("Synthetic media manifest is missing or changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("kind") != "generated-synthetic-inputs-not-Resolve-evidence":
        raise RuntimeError("Only generated synthetic inputs are allowed")
    expected = {}
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("Synthetic media manifest has no file list")
    for entry in entries:
        relative = Path(entry.get("path", ""))
        path = media / relative
        cursor = media
        symlinked = False
        for part in relative.parts:
            cursor /= part
            symlinked = symlinked or cursor.is_symlink()
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or symlinked
            or not path.is_file()
            or not path.resolve().is_relative_to(media.resolve())
        ):
            raise RuntimeError("Unsafe or missing synthetic media path")
        digest = entry.get("sha256")
        if (
            not isinstance(digest, str)
            or _sha256(path) != digest
            or path.stat().st_size != entry.get("sizeBytes")
        ):
            raise RuntimeError("Synthetic media bytes differ from manifest")
        expected[str(path)] = digest
    if len(expected) != len(entries):
        raise RuntimeError("Synthetic media manifest contains duplicate paths")
    return media, expected


def _context(resolve, config, identity, probe, selected_uid, *, idle=True):
    project = probe.require_current(resolve, config, identity)
    if (
        project.GetUniqueId() != PROJECT_ID
        or project.GetName() != config["projectName"]
    ):
        raise RuntimeError("Exact Issue 141 project identity changed")
    if idle and project.IsRenderingInProgress() is not False:
        raise RuntimeError("Project is rendering or idle state is unreadable")
    selected = project.GetCurrentTimeline()
    if selected is None or selected.GetUniqueId() != selected_uid:
        raise RuntimeError("Selected timeline changed")
    protected = config.get("timelineInventory") == PROTECTED_INVENTORY
    expected = PROTECTED_TIMELINE_IDENTITIES if protected else TIMELINE_IDENTITIES
    found = {}
    count = project.GetTimelineCount()
    if count != len(expected):
        raise RuntimeError(
            "Exact protected timeline inventory changed"
            if protected
            else "Exact four-timeline inventory changed"
        )
    for index in range(1, count + 1):
        timeline = project.GetTimelineByIndex(index)
        if timeline is None:
            raise RuntimeError("Timeline inventory is incomplete")
        uid, name = timeline.GetUniqueId(), timeline.GetName()
        if not isinstance(uid, str) or uid in found:
            raise RuntimeError("Timeline UID is missing or duplicated")
        found[uid] = name
    if found != expected:
        raise RuntimeError(
            "Protected timeline UID/name inventory changed"
            if protected
            else "Timeline UID/name inventory changed"
        )
    return project


def _read_pair(resolve, config, identity, expected, selected_uid, probe):
    observations, inventories = [], []
    for _ in range(2):
        try:
            _context(resolve, config, identity, probe, selected_uid)
            observations.append(
                _canonical(probe.observe(resolve, config, identity, expected))
            )
        except Exception as error:
            observations.append({"error": f"{type(error).__name__}: {error}"})
        try:
            project = _context(resolve, config, identity, probe, selected_uid)
            inventories.append(_canonical(probe._r4_pool_inventory(project, expected)))
            _context(resolve, config, identity, probe, selected_uid)
        except Exception as error:
            inventories.append({"error": f"{type(error).__name__}: {error}"})
    result = {
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
    if config.get("timelineInventory") == PROTECTED_INVENTORY:
        result["timelineInventory"] = PROTECTED_INVENTORY
    return result


def _validate_read_pair(value, probe):
    if (
        value.get("timelineConsistency") != "equal-adjacent-reads"
        or value.get("poolConsistency") != "equal-adjacent-reads"
    ):
        raise RuntimeError("Full timeline/pool pair is incomplete or inconsistent")
    states = value.get("timelinePasses", [])
    if any(
        isinstance(state, dict)
        and state.get("timelineInventory") == PROTECTED_INVENTORY
        for state in states
    ) and value.get("timelineInventory") != PROTECTED_INVENTORY:
        raise RuntimeError("Protected timeline pair metadata is missing")
    if value.get("timelineInventory") == PROTECTED_INVENTORY:
        for state in states:
            if state.get("timelineInventory") != PROTECTED_INVENTORY:
                raise RuntimeError("Protected timeline metadata is incomplete")
    return (
        _equal_pair(value.get("timelinePasses"), probe, "Timeline"),
        _equal_pair(value.get("poolPasses"), probe, "Pool"),
    )


def _only_range_changed(before, after):
    expected = _canonical(after)
    target = _timeline(expected, R4_UID)
    original = _timeline(before, R4_UID)
    for field in ("GetStartTimecode", "GetStartFrame", "GetEndFrame"):
        target[field] = original[field]
    return expected == before


def _occurrence(state):
    timeline = _timeline(state, R4_UID)
    items = [
        (track, item)
        for track in timeline.get("tracks", [])
        for item in track.get("items", [])
    ]
    if len(items) != 1:
        raise RuntimeError("R4 must retain its single existing occurrence")
    track, item = items[0]
    if (track.get("type"), track.get("index")) != ("video", 1):
        raise RuntimeError("R4 occurrence is not on V1")
    if (
        item.get("GetUniqueId") != {"value": ITEM_UID}
        or item.get("GetMediaPoolItem", {}).get("GetUniqueId") != {"value": MEDIA_UID}
        or item.get("GetStart") != {"value": 0}
        or item.get("GetEnd") != {"value": 199}
        or item.get("GetDuration") != {"value": 199}
        or item.get("GetSourceStartFrame") != {"value": 0}
        or item.get("GetSourceEndFrame") != {"value": 199}
        or item.get("GetTrackTypeAndIndex") != {"value": ["video", 1]}
    ):
        raise RuntimeError("R4 occurrence identity/source/record range changed")
    return timeline, item


def _pool_matches(pool, expected):
    rows = [row for row in pool.get("items", []) if row.get("uid") == MEDIA_UID]
    if len(rows) != 1:
        raise RuntimeError("R4 source pool identity is missing or duplicated")
    evidence = rows[0].get("evidence", {})
    props = evidence.get("GetClipProperty", {}).get("value", {})
    source = props.get("File Path")
    source_bytes = evidence.get("sourceBytes", {})
    if (
        props.get("Online Status") != "Online"
        or props.get("File Name") != "base.mov"
        or evidence.get("GetUniqueId") != {"value": MEDIA_UID}
        or source not in expected
        or source_bytes.get("sha256") != expected.get(source)
        or source_bytes.get("hashMatches") is not True
    ):
        raise RuntimeError("Pinned R4 pool source is not online with exact UID")
    mapping = [
        row
        for row in pool.get("timelineMappings", [])
        if row.get("timelineUid") == {"value": R4_UID}
    ]
    if len(mapping) != 1 or mapping[0].get("poolItemUid") != {"value": R4_POOL_UID}:
        raise RuntimeError("R4 timeline proxy mapping changed")


def run(resolve, config, *, probe):
    """Set the R4 start timecode once, retaining complete evidence and rollback."""
    root = Path(probe.ROOT).resolve()
    output = Path(config.get("outputDir", ""))
    if (
        config.get("action") != "r4-range-repair"
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != (root / "out").resolve()
        or not output.name.startswith("issue-141-observation-")
        or not config.get("projectName", "").startswith(
            "VERA Issue 141 Synthetic Probe "
        )
    ):
        raise RuntimeError("Only the exact synthetic Issue 141 observation is allowed")
    _, expected = _manifest(config, root, probe)
    matrix_pin = _pin(output / MATRIX_PIN, MATRIX_PIN, MATRIX_SHA256, probe)
    matrix_obs = _equal_pair(
        matrix_pin.get("timelinePasses"), probe, "Matrix timeline pin"
    )
    matrix_pool = _equal_pair(matrix_pin.get("poolPasses"), probe, "Matrix pool pin")
    if (
        matrix_pin.get("selectedTimelineUid") != MATRIX_UID
        or matrix_pin.get("timelineConsistency") != "equal-adjacent-reads"
        or matrix_pin.get("poolConsistency") != "equal-adjacent-reads"
        or matrix_obs.get("projectId") != PROJECT_ID
        or matrix_obs.get("projectName") != config["projectName"]
    ):
        raise RuntimeError("Exact immutable selected-Matrix pair is invalid")
    r4_capture = _pin(output / R4_CAPTURE_PIN, R4_CAPTURE_PIN, R4_CAPTURE_SHA256, probe)
    r4_pool_file = _pin(output / R4_POOL_PIN, R4_POOL_PIN, R4_POOL_SHA256, probe)
    r4_pin = _equal_pair(r4_capture.get("passes"), probe, "Online R4 capture")
    r4_pool = _equal_pair(r4_pool_file.get("passes"), probe, "Online R4 pool")
    if (
        r4_capture.get("consistency") != "equal-adjacent-reads"
        or r4_capture.get("captureFailure") is not None
        or r4_pool_file.get("status") != "equal-read-only-pool-inventory"
        or Path(r4_pool_file.get("capture", {}).get("capturePath", "")).name
        != R4_CAPTURE_PIN
        or r4_pool_file.get("capture", {}).get("sha256") != R4_CAPTURE_SHA256
        or r4_pin.get("projectId") != PROJECT_ID
    ):
        raise RuntimeError("Original online R4 evidence pair is invalid")
    _occurrence(r4_pin)
    _pool_matches(r4_pool, expected)
    for locator, digest in expected.items():
        if probe.source_evidence(locator, expected).get("sha256") != digest:
            raise RuntimeError("Synthetic media byte check failed")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence = output / f"r4-range-repair-{stamp}"
    evidence.mkdir(exist_ok=False)
    journal = evidence / "journal.jsonl"
    journal.open("x", encoding="utf-8").close()
    identity = {"projectId": PROJECT_ID, "projectName": config["projectName"]}
    stamps = {
        "Resolve": resolve.GetVersion(),
        "projectId": PROJECT_ID,
        "matrixPin": MATRIX_PIN,
        "r4CapturePin": R4_CAPTURE_PIN,
        "r4PoolPin": R4_POOL_PIN,
        "manifestSources": expected,
    }
    if (
        "studio" not in str(resolve.GetProductName()).casefold()
        or stamps["Resolve"] != BUILD
    ):
        raise RuntimeError("Exact Resolve Studio 21.1 build 14 is required")
    _append(journal, "R4RangeRepair", "start", stamps)

    def capture(label, selected_uid):
        value = _read_pair(resolve, config, identity, expected, selected_uid, probe)
        _write(evidence / f"{label}.json", value)
        _append(journal, "Capture", label, value)
        return value

    def select(uid, previous_uid):
        project = _context(resolve, config, identity, probe, previous_uid)
        matches = [
            project.GetTimelineByIndex(i)
            for i in range(1, project.GetTimelineCount() + 1)
            if project.GetTimelineByIndex(i).GetUniqueId() == uid
        ]
        if len(matches) != 1:
            raise RuntimeError("Exact target timeline handle is missing or duplicated")
        _append(journal, "SetCurrentTimeline", "request", uid)
        returned = project.SetCurrentTimeline(matches[0])
        _append(journal, "SetCurrentTimeline", "return", returned)
        if returned is not True:
            raise RuntimeError("SetCurrentTimeline refused")
        _context(resolve, config, identity, probe, uid)

    def record_result(status, before=None, after=None, error=None, rollback=None):
        project = probe.require_current(resolve, config, identity)
        selected = project.GetCurrentTimeline()
        current = None if selected is None else selected.GetUniqueId()
        if current not in {MATRIX_UID, R4_UID}:
            raise RuntimeError("Selection changed before result could be retained")
        _context(resolve, config, identity, probe, current)
        report = {
            "status": status,
            "projectId": PROJECT_ID,
            "selectedTimelineUid": current,
            "before": before,
            "after": after,
            "error": error,
            "rollback": rollback,
            "journal": str(journal),
        }
        _write(evidence / "report.json", report)
        _append(journal, "R4RangeRepair", "complete", report)
        return report

    # Establish the exact immutable selected-Matrix checkpoint before changing context.
    before_matrix = capture("matrix-preflight", MATRIX_UID)
    live_matrix, live_matrix_pool = _validate_read_pair(before_matrix, probe)
    if live_matrix != matrix_obs or live_matrix_pool != matrix_pool:
        raise RuntimeError("Fresh selected-Matrix state differs from immutable pin")
    select(R4_UID, MATRIX_UID)
    before = capture("r4-preflight", R4_UID)
    before_state, before_pool = _validate_read_pair(before, probe)
    if before_state != r4_pin or before_pool != r4_pool:
        # Restore only the selection; no timeline mutation has been attempted.
        select(MATRIX_UID, R4_UID)
        raise RuntimeError("Fresh selected-R4 state differs from original online pin")
    _occurrence(before_state)
    _pool_matches(before_pool, expected)
    original_timeline = _timeline(before_state, R4_UID)
    if (
        original_timeline.get("GetStartFrame") != {"value": 90000}
        or original_timeline.get("GetEndFrame") != {"value": 90000}
        or original_timeline.get("GetStartTimecode") != {"value": ORIGINAL_TIMECODE}
    ):
        raise RuntimeError("Original R4 range differs from the reviewed precondition")
    target = next(project_uid_timeline(resolve, config, identity, probe, R4_UID))
    _append(journal, "SetStartTimecode", "request", TARGET_TIMECODE)
    returned, setter_error = None, None
    try:
        returned = target.SetStartTimecode(TARGET_TIMECODE)
        _append(journal, "SetStartTimecode", "return", returned)
    except Exception as error:
        setter_error = f"{type(error).__name__}: {error}"
        _append(journal, "SetStartTimecode", "failure", setter_error)
    after = capture("r4-postflight", R4_UID)
    try:
        after_state, after_pool = _validate_read_pair(after, probe)
    except Exception as error:
        reason = f"Postflight incomplete: {type(error).__name__}: {error}"
        _append(journal, "R4RangeRepair", "postflight-refused", reason)
        _write(
            evidence / "report.json",
            {
                "status": "postflight-incomplete",
                "selectedTimelineUid": R4_UID,
                "before": before,
                "after": after,
                "error": reason,
                "rollback": "unsafe without complete readback",
                "journal": str(journal),
            },
        )
        raise RuntimeError("R4 postflight is incomplete; evidence retained") from error
    _pool_matches(after_pool, expected)
    timeline = _timeline(after_state, R4_UID)
    start, end, timecode = (
        timeline.get("GetStartFrame", {}).get("value"),
        timeline.get("GetEndFrame", {}).get("value"),
        timeline.get("GetStartTimecode", {}).get("value"),
    )
    success = (
        setter_error is None
        and returned is True
        and after_pool == before_pool
        and _only_range_changed(before_state, after_state)
        and timecode == TARGET_TIMECODE
        and start == 0
        and isinstance(end, int)
        and 50 < end <= 200
    )
    if success:
        _occurrence(after_state)
        return record_result("repaired-unsaved", before, after)

    reason = (
        setter_error
        or f"setter returned {returned!r}; range/readback did not satisfy invariants"
    )
    _append(journal, "R4RangeRepair", "postcondition-refused", reason)
    rollback = {"status": "not-safe", "reason": "Postflight includes non-range drift"}
    if _only_range_changed(before_state, after_state) and after_pool == before_pool:
        current_tc = timeline.get("GetStartTimecode", {}).get("value")
        if current_tc != ORIGINAL_TIMECODE:
            _append(journal, "SetStartTimecode", "restore-request", ORIGINAL_TIMECODE)
            restore_return, restore_error = None, None
            try:
                restore_return = target.SetStartTimecode(ORIGINAL_TIMECODE)
                _append(journal, "SetStartTimecode", "restore-return", restore_return)
            except Exception as error:
                restore_error = f"{type(error).__name__}: {error}"
                _append(journal, "SetStartTimecode", "restore-failure", restore_error)
            restored = capture("r4-rollback", R4_UID)
            restored_state, restored_pool = _validate_read_pair(restored, probe)
            if (
                restore_error is None
                and restore_return is True
                and restored_state == before_state
                and restored_pool == before_pool
            ):
                select(MATRIX_UID, R4_UID)
                matrix_after = capture("matrix-restored-selection", MATRIX_UID)
                obs, pool = _validate_read_pair(matrix_after, probe)
                rollback = {
                    "status": "restored",
                    "timeline": restored,
                    "matrixSelection": matrix_after,
                    "exactMatrixPin": obs == matrix_obs and pool == matrix_pool,
                }
                if not rollback["exactMatrixPin"]:
                    rollback["status"] = "restore-unverified"
            else:
                rollback = {
                    "status": "restore-unverified",
                    "timeline": restored,
                    "setterReturn": restore_return,
                    "error": restore_error,
                }
        else:
            select(MATRIX_UID, R4_UID)
            rollback = {
                "status": "unchanged",
                "matrixSelection": capture("matrix-restored-selection", MATRIX_UID),
            }
    record_result("refused-partial-state-retained", before, after, reason, rollback)
    raise RuntimeError(
        "R4 range repair failed or violated postconditions; evidence retained"
    )


def project_uid_timeline(resolve, config, identity, probe, uid):
    project = _context(resolve, config, identity, probe, uid)
    for index in range(1, project.GetTimelineCount() + 1):
        timeline = project.GetTimelineByIndex(index)
        if timeline.GetUniqueId() == uid:
            yield timeline
