#!/usr/bin/env python3
"""Prepare and optionally run exactly one reviewed R1 reopen repeat."""

import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/issue-141-observation-20260930-01a0f318"
HERE = ROOT / "docs/investigations/issue-141"
CONFIG = Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins/vera-issue-141-observation.json")
PROBE = HERE / "probe.py"
NATIVE_CALLER = OUT / "independent-native-call.py"
HELPER = HERE / "r1-repeat-six.py"
REFERENCE = OUT / "av-output-20261001T231540.921062Z/outer-restore-20261002T011949.373431Z/final-pair.json"
PROBE_SHA256 = "fdd2d31024a005489564e99bb4916e190e5830e26705b87ea6e56adbcf9e918b"
CALLER_SHA256 = "395805068e96517bfe67aa32497229226b6c7fad431790e1cac94f4ecaf5cd03"
HELPER_SHA256 = "4aece3d8ab7c7e0ab215fc9eb841fc95b56b85fb0809859e7f587ce83b0e2c28"
REFERENCE_SHA256 = "d8cf8bdc6b1a9f52266dfa076fcdf63cdcaa2557d966389c8f1cd49f621e0b14"
PROJECT = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
PROJECT_NAME = "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
MATRIX = "29ae8331-b86e-4041-a548-960695cc7b24"
BUILD = [21, 1, 0, 14, ""]
TIMELINES = {
    "88f7923d-55a7-471f-b09b-cf10f9fae8ad": "VERA 141 Baseline",
    "aa2b8e36-83bd-4292-9e33-217c00ca192f": "VERA 141 R1 identity",
    MATRIX: "VERA 141 Batched Matrix",
    "64de8a4c-86bd-4f19-9d20-47b8940f610b": "VERA 141 R4 availability",
    "21436b8f-057c-49e6-80ba-5f733abe87b2": "transcription test 1",
    "2db0b2d1-6d81-48d4-b49c-360f56e012cd": "transcription test 2",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def has_error(value):
    if isinstance(value, dict):
        return bool(value.get("error")) or any(has_error(v) for v in value.values())
    if isinstance(value, list):
        return any(has_error(v) for v in value)
    return False


def validate_pair(pair):
    if (
        not isinstance(pair, dict)
        or pair.get("selectedTimelineUid") != MATRIX
        or pair.get("timelineInventory") != "protected-six"
        or pair.get("timelineConsistency") != "equal-adjacent-reads"
        or pair.get("poolConsistency") != "equal-adjacent-reads"
    ):
        raise ValueError("Fresh pair is incomplete, unstable, or not selected Matrix")
    timelines = pair.get("timelinePasses")
    pools = pair.get("poolPasses")
    if (
        not isinstance(timelines, list) or len(timelines) != 2
        or timelines[0] != timelines[1]
        or not isinstance(pools, list) or len(pools) != 2
        or pools[0] != pools[1]
        or has_error(pair)
    ):
        raise ValueError("Fresh pair passes are incomplete, changed, or contain getter errors")
    state = timelines[0]
    if state.get("projectId") != PROJECT or state.get("projectName") != PROJECT_NAME:
        raise ValueError("Fresh pair project identity differs")
    rows = {
        row.get("GetUniqueId", {}).get("value"): row.get("GetName", {}).get("value")
        for row in state.get("timelines", [])
    }
    if rows != TIMELINES:
        raise ValueError("Fresh pair does not contain exactly the protected six timelines")
    matrix_rows = [row for row in state["timelines"]
                   if row.get("GetUniqueId", {}).get("value") == MATRIX]
    if len(matrix_rows) != 1:
        raise ValueError("Fresh pair Matrix row is missing or duplicated")
    locks = []
    for track in matrix_rows[0].get("tracks", []):
        kind, index = track.get("type"), track.get("index")
        raw = track.get("GetIsTrackLocked")
        if kind not in {"video", "audio", "subtitle"} or not isinstance(index, int):
            raise ValueError("Fresh pair contains an invalid Matrix track identity")
        if not isinstance(raw, dict) or type(raw.get("value")) is not bool:
            raise ValueError("Fresh pair has a missing/error Matrix track-lock read")
        locks.append([kind, index, raw["value"]])
    locks.sort(key=lambda row: ({"video": 0, "audio": 1, "subtitle": 2}[row[0]], row[1]))
    return state, locks


def expected_context(readback, pair):
    if (
        not isinstance(readback, dict)
        or readback.get("status") != "editorial-readback-retained"
        or readback.get("label") != "editorial-context"
        or readback.get("readOnly") is not True
        or readback.get("failure") is not None
    ):
        raise ValueError("The fresh editorial-context readback did not pass")
    state, locks = validate_pair(pair)
    environment = readback.get("environment")
    selections = readback.get("selectionPasses")
    if (
        not isinstance(environment, dict)
        or environment.get("productName") != "DaVinci Resolve Studio"
        or environment.get("version") != BUILD
        or not isinstance(selections, list) or len(selections) != 2
        or selections[0] != selections[1]
        or not isinstance(selections[0].get("playhead"), str)
        or not isinstance(selections[0].get("items"), list)
        or has_error(selections)
    ):
        raise ValueError("Editorial environment/selection evidence is incomplete or changed")
    if pair.get("selectedTimelineUid") != MATRIX:
        raise ValueError("Editorial pair selection is not Matrix")
    # The editorial reader only returns success after Edit-page, idle-renderer,
    # empty-queue, and stable full-pair guards all pass.
    context = {
        "product": environment["productName"],
        "version": environment["version"],
        "projectUid": state["projectId"],
        "projectName": state["projectName"],
        "page": "edit",
        "idle": True,
        "queue": [],
        "selectedTimelineUid": MATRIX,
        "playhead": selections[0]["playhead"],
        "selection": selections[0]["items"],
        "trackLocks": locks,
        "expectedSelectionUid": MATRIX,
    }
    return context


def check_demo():
    timeline_rows = []
    for uid, name in TIMELINES.items():
        track = {"type": "video", "index": 1, "GetIsTrackLocked": {"value": False}}
        timeline_rows.append({"GetUniqueId": {"value": uid}, "GetName": {"value": name},
                              "tracks": [track] if uid == MATRIX else []})
    state = {"projectId": PROJECT, "projectName": PROJECT_NAME, "timelines": timeline_rows}
    pair = {"selectedTimelineUid": MATRIX, "timelineInventory": "protected-six",
            "timelineConsistency": "equal-adjacent-reads", "poolConsistency": "equal-adjacent-reads",
            "timelinePasses": [state, state], "poolPasses": [{"items": []}, {"items": []}]}
    readback = {"status": "editorial-readback-retained", "label": "editorial-context",
                "readOnly": True, "failure": None,
                "environment": {"productName": "DaVinci Resolve Studio", "version": BUILD},
                "selectionPasses": [{"playhead": "00:00:00:00", "items": []}] * 2}
    got = expected_context(readback, pair)
    assert got["page"] == "edit" and got["idle"] is True and got["queue"] == []
    assert got["trackLocks"] == [["video", 1, False]]
    def refuses(result=readback, candidate=pair):
        try:
            expected_context(result, candidate)
        except (ValueError, TypeError, KeyError):
            return
        raise AssertionError("unsafe readback/context was accepted")
    changed = json.loads(json.dumps(pair))
    changed["timelinePasses"][1]["projectName"] = "changed"
    refuses(candidate=changed)
    changed = json.loads(json.dumps(pair))
    changed["selectedTimelineUid"] = "wrong"
    refuses(candidate=changed)
    changed = json.loads(json.dumps(pair))
    changed["timelinePasses"][0]["timelines"][2]["tracks"][0]["GetIsTrackLocked"] = {"error": "getter"}
    refuses(candidate=changed)
    changed = json.loads(json.dumps(readback))
    changed["selectionPasses"][1]["playhead"] = "00:00:01:00"
    refuses(result=changed)
    changed = json.loads(json.dumps(readback))
    changed["status"] = "refused"
    refuses(result=changed)
    return {"status": "offline-check-passed", "refusals": 5,
            "nativeDispatchPerformed": False, "filesWritten": False}


def _load_native():
    for path, expected in ((PROBE, PROBE_SHA256), (NATIVE_CALLER, CALLER_SHA256),
                           (HELPER, HELPER_SHA256), (REFERENCE, REFERENCE_SHA256)):
        if path.is_symlink() or not path.is_file() or sha(path.read_bytes()) != expected:
            raise RuntimeError(f"Reviewed R1 pin changed: {path}")
    spec = importlib.util.spec_from_file_location("issue141_native_caller", NATIVE_CALLER)
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    return native


def run_reopen():
    if OUT.is_symlink() or OUT.resolve().parent != (ROOT / "out").resolve():
        raise RuntimeError("Issue output directory changed")
    if CONFIG.is_symlink() or not CONFIG.is_file():
        raise RuntimeError("Installed config is missing or a symlink")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if (config.get("action") != "observe" or config.get("timelineInventory") != "protected-six"
            or config.get("externalScriptingSetting") != "None"
            or config.get("probePath") != str(PROBE)
            or config.get("probeSha256") != PROBE_SHA256
            or config.get("outputDir") != str(OUT)
            or config.get("projectName") != PROJECT_NAME):
        raise RuntimeError("Installed config is not the reviewed observe/protected-six state")
    native = _load_native()
    # A refusal or pending result is terminal for this invocation; never relaunch.
    readback = native.invoke({"action": "editorial-readback", "editorialReadbackLabel": "editorial-context"})
    if not isinstance(readback, dict) or readback.get("status") != "editorial-readback-retained":
        raise RuntimeError(
            "Editorial readback refused; inspect retained audit "
            f"{readback.get('_auditDirectory')} and result {readback.get('_nativeResultPath')}; stop"
        )
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    validate_pair(reference)
    ref = readback.get("pair", {})
    fresh_path = Path(ref.get("path", ""))
    if (fresh_path.is_symlink() or not fresh_path.is_file()
            or OUT.resolve() not in fresh_path.resolve().parents
            or sha(fresh_path.read_bytes()) != ref.get("sha256")):
        raise RuntimeError(
            "Fresh editorial pair pin/path is invalid; retained audit "
            f"{readback.get('_auditDirectory')} result {readback.get('_nativeResultPath')}"
        )
    fresh_pair = json.loads(fresh_path.read_text(encoding="utf-8"))
    context = expected_context(readback, fresh_pair)
    if fresh_pair != reference:
        raise RuntimeError("Fresh readback differs from the exact A2-restored checkpoint; stop")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    checkpoint = OUT / f"r1-repeat-checkpoint-{stamp}.json"
    checkpoint.write_bytes(fresh_path.read_bytes())
    checkpoint_sha = sha(checkpoint.read_bytes())
    if checkpoint_sha != ref["sha256"]:
        raise RuntimeError("Copied R1 checkpoint hash differs; stop without native repeat")
    updates = {
        "action": "r1-repeat-reopen",
        "case": "R1-repeat-six",
        "repeatCheckpoint": str(checkpoint),
        "repeatCheckpointSha256": checkpoint_sha,
        "repeatExpectedContext": context,
    }
    result = native.invoke(updates)
    print(json.dumps({"status": result.get("status", "returned"),
                      "readbackPairSha256": ref["sha256"],
                      "checkpointPath": str(checkpoint), "checkpointSha256": checkpoint_sha,
                      "resultAuditDirectory": result.get("_auditDirectory"),
                      "nativeResultPath": result.get("_nativeResultPath"),
                      "nativeDispatchPerformed": True,
                      "note": "Inspect this result; never relaunch after refusal or pending result."}, sort_keys=True))


def main():
    args = sys.argv[1:]
    if args not in ([], ["--check"], ["--reopen"]):
        raise SystemExit("Usage: r1-next-execution.py [--check|--reopen]")
    if args != ["--reopen"]:
        print(json.dumps(check_demo(), sort_keys=True))
        return
    run_reopen()


if __name__ == "__main__":
    main()
