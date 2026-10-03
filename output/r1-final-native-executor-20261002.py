#!/usr/bin/env python3
"""Prepare and run the one authorized R1 restoration/final-duplicate sequence.

Preparation is offline.  ``--restore`` and ``--final-duplicate`` are separate
terminal operations so a refusal or pending native result cannot be retried.
"""

import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/issue-141-observation-20260930-01a0f318"
OUTPUT = ROOT / "output"
LOCAL_READINESS = OUTPUT / "r1-selection-restoration-local.json"
READINESS = OUTPUT / "r1-final-native-executor-20261002-readiness.json"
STATE = OUTPUT / "r1-final-native-executor-20261002-state.json"
CONFIG = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins/vera-issue-141-observation.json"
)
PROBE = ROOT / "docs/investigations/issue-141/probe.py"
CALLER = OUT / "independent-native-call.py"
HELPER = ROOT / "docs/investigations/issue-141/r1-repeat-six.py"
READBACK = ROOT / "docs/investigations/issue-141/editorial-readback.py"
DRIVER = OUTPUT / "r1-next-execution.py"
WRAPPER_DIR = OUT / "r1-repeat-duplicate-20261002T122220.047704Z"
WRAPPERS = {
    "r1": (WRAPPER_DIR / "pair-03.json", "21327670e17a48675c466d9c1f3e7f63b751e45b6fc26b4f8e382934c698c486", "aa2b8e36-83bd-4292-9e33-217c00ca192f"),
    "matrix": (WRAPPER_DIR / "pair-01.json", "b5d2b291be801f65be762d813e76335223f2bde83701c95a56882f919180e519", "29ae8331-b86e-4041-a548-960695cc7b24"),
}

PROJECT = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
PROJECT_NAME = "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
R1 = WRAPPERS["r1"][2]
MATRIX = WRAPPERS["matrix"][2]
CASE = "R1-repeat-six"
BUILD = [21, 1, 0, 14, ""]
TIMELINES = {
    "88f7923d-55a7-471f-b09b-cf10f9fae8ad": "VERA 141 Baseline",
    R1: "VERA 141 R1 identity",
    MATRIX: "VERA 141 Batched Matrix",
    "64de8a4c-86bd-4f19-9d20-47b8940f610b": "VERA 141 R4 availability",
    "21436b8f-057c-49e6-80ba-5f733abe87b2": "transcription test 1",
    "2db0b2d1-6d81-48d4-b49c-360f56e012cd": "transcription test 2",
}

# These are the pins produced by the reviewed registration transform.  The
# caller's own dispatch table remains the final authority at invocation time.
PINS = {
    "probe": "2a5113df4c64eed13b812ea99c923633827ee77bdf3398c70e9df9b8361de47d",
    "caller": "ead091ca81673a8924bac58e247d9c41b705580f951be851ccbe739e90a98562",
    "helper": "1948ec4339cc92ca949db9be4f554806f237614a4ee9ad886467e6d3b77475c3",
    "readback": "d9df76229ead502b2d9ff31a1847eb9b858aa8931d25d279b560244e93690354",
}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def file_digest(path):
    return digest(path.read_bytes())


def fail(message):
    raise RuntimeError(message)


def regular(path, parent=None):
    if path.is_symlink() or not path.is_file():
        fail(f"Expected regular non-symlink file: {path}")
    if parent is not None and path.resolve().parent != parent.resolve():
        fail(f"File must be directly inside {parent}: {path}")


def has_error(value):
    if isinstance(value, dict):
        return bool(value.get("error")) or any(has_error(item) for item in value.values())
    if isinstance(value, list):
        return any(has_error(item) for item in value)
    return False


def validate_pair(pair, selected):
    if not isinstance(pair, dict) or pair.get("selectedTimelineUid") != selected:
        fail("Pair selection is not the requested timeline")
    if pair.get("timelineInventory") != "protected-six":
        fail("Pair is not explicitly protected-six")
    if pair.get("timelineConsistency") != "equal-adjacent-reads" or pair.get("poolConsistency") != "equal-adjacent-reads":
        fail("Pair is not stable equal-adjacent-reads")
    timelines = pair.get("timelinePasses")
    pools = pair.get("poolPasses")
    if not isinstance(timelines, list) or len(timelines) != 2 or timelines[0] != timelines[1]:
        fail("Pair timeline passes are incomplete or changed")
    if not isinstance(pools, list) or len(pools) != 2 or pools[0] != pools[1]:
        fail("Pair pool passes are incomplete or changed")
    if has_error(pair):
        fail("Pair contains a getter error")
    state = timelines[0]
    if state.get("projectId") != PROJECT or state.get("projectName") != PROJECT_NAME:
        fail("Pair project identity differs")
    rows = {
        row.get("GetUniqueId", {}).get("value"): row.get("GetName", {}).get("value")
        for row in state.get("timelines", [])
    }
    if rows != TIMELINES:
        fail("Pair does not contain exactly the protected six timelines")
    if not isinstance(pools[0].get("items"), list) or not pools[0]["items"]:
        fail("Pair has no media-pool evidence")


def validate_context(context, selected):
    if not isinstance(context, dict):
        fail("Wrapper native context is missing")
    expected = {
        "product": "DaVinci Resolve Studio",
        "version": BUILD,
        "projectUid": PROJECT,
        "projectName": PROJECT_NAME,
        "page": "edit",
        "idle": True,
        "queue": [],
        "selectedTimelineUid": selected,
        "expectedSelectionUid": selected,
    }
    if any(context.get(key) != value for key, value in expected.items()):
        fail("Wrapper native context differs from the reviewed context")
    if not isinstance(context.get("selection"), list) or not isinstance(context.get("trackLocks"), list):
        fail("Wrapper native context lacks selection/track-lock evidence")
    if has_error(context):
        fail("Wrapper native context contains a getter error")


def read_wrapper(label):
    path, expected_sha, selected = WRAPPERS[label]
    regular(path, WRAPPER_DIR)
    actual_sha = file_digest(path)
    if actual_sha != expected_sha:
        fail(f"Reviewed {label} wrapper changed: {actual_sha}")
    wrapper = json.loads(path.read_text(encoding="utf-8"))
    pair, context = wrapper.get("pair"), wrapper.get("nativeContext")
    validate_pair(pair, selected)
    validate_context(context, selected)
    return {
        "sourcePath": str(path),
        "sourceSha256": actual_sha,
        "selectedTimelineUid": selected,
        "pair": pair,
        "nativeContext": context,
        "pairBytes": json.dumps(pair, indent=2, sort_keys=True).encode("utf-8"),
        "contextSha256": digest(json.dumps(context, sort_keys=True, separators=(",", ":")).encode("utf-8")),
    }


def load_local_readiness():
    regular(LOCAL_READINESS, OUTPUT)
    record = json.loads(LOCAL_READINESS.read_text(encoding="utf-8"))
    if record.get("kind") != "r1-selection-restoration-local" or record.get("nativeDispatchPerformed") is not False:
        fail("Local restoration readiness record is not the reviewed offline record")
    return record


def ensure_output_root():
    if OUT.is_symlink() or OUT.resolve().parent != (ROOT / "out").resolve() or not OUT.is_dir():
        fail("Issue output directory changed")


def prepare():
    ensure_output_root()
    local = load_local_readiness()
    r1, matrix = read_wrapper("r1"), read_wrapper("matrix")
    if local["retainedSources"]["currentR1WrapperSha256"] != r1["sourceSha256"] or local["retainedSources"]["targetMatrixWrapperSha256"] != matrix["sourceSha256"]:
        fail("Local readiness wrapper pins differ")
    if READINESS.exists() or STATE.exists():
        fail("Final executor preparation already exists; preserve it and do not overwrite")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    checkpoint = OUT / f"r1-final-executor-{stamp}-repeat-checkpoint.json"
    target = OUT / f"r1-final-executor-{stamp}-restore-target.json"
    for path in (checkpoint, target):
        if path.exists():
            fail(f"Unexpected prepared pair collision: {path}")
    checkpoint.write_bytes(r1["pairBytes"])
    target.write_bytes(matrix["pairBytes"])
    checkpoint_sha, target_sha = file_digest(checkpoint), file_digest(target)
    if checkpoint_sha != local["canonicalExtractedPins"]["currentR1PairSha256"] or target_sha != local["canonicalExtractedPins"]["targetMatrixPairSha256"]:
        fail("Extracted pair hash differs from reviewed canonical serialization")
    record = {
        "kind": "issue-141-r1-final-native-executor-readiness",
        "status": "awaiting-root-authorization",
        "nativeDispatchPerformed": False,
        "driver": {"path": str(Path(__file__).resolve()), "sha256": file_digest(Path(__file__))},
        "localReadiness": str(LOCAL_READINESS),
        "wrappers": {
            "r1": {key: r1[key] for key in ("sourcePath", "sourceSha256", "selectedTimelineUid", "contextSha256")},
            "matrix": {key: matrix[key] for key in ("sourcePath", "sourceSha256", "selectedTimelineUid", "contextSha256")},
        },
        "extracted": {
            "repeatCheckpoint": {"path": str(checkpoint), "sha256": checkpoint_sha},
            "restoreTargetPair": {"path": str(target), "sha256": target_sha},
        },
        "contexts": {
            "repeatExpectedContext": r1["nativeContext"],
            "restoreTargetContext": matrix["nativeContext"],
        },
        "registrationPinsRequired": PINS,
        "sequence": [
            "one r1-repeat-restore-selection with one SetCurrentTimeline(Matrix)",
            "one editorial-context readback and exact comparison with restoreTargetPair",
            "one r1-repeat-duplicate; terminal native action",
        ],
        "prohibitions": ["no reopen", "no retry after refusal/pending", "no post-duplicate native action"],
    }
    READINESS.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    STATE.write_text(json.dumps({"kind": "issue-141-r1-final-native-executor-state", "restoreAttempted": False, "finalDuplicateAttempted": False}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": record["status"], "nativeDispatchPerformed": False, "readiness": str(READINESS), "repeatCheckpoint": str(checkpoint), "restoreTargetPair": str(target), "repeatCheckpointSha256": checkpoint_sha, "restoreTargetPairSha256": target_sha}, sort_keys=True))


def load_prepared():
    regular(READINESS, OUTPUT)
    regular(STATE, OUTPUT)
    record = json.loads(READINESS.read_text(encoding="utf-8"))
    if record.get("kind") != "issue-141-r1-final-native-executor-readiness":
        fail("Unexpected final executor readiness record")
    state = json.loads(STATE.read_text(encoding="utf-8"))
    extracted = record["extracted"]
    pairs = {}
    for key, selected in (("repeatCheckpoint", R1), ("restoreTargetPair", MATRIX)):
        entry = extracted[key]
        path = Path(entry["path"])
        regular(path, OUT)
        if file_digest(path) != entry["sha256"]:
            fail(f"Prepared {key} hash changed")
        pair = json.loads(path.read_text(encoding="utf-8"))
        validate_pair(pair, selected)
        pairs[key] = (path, entry["sha256"], pair)
    r1, matrix = read_wrapper("r1"), read_wrapper("matrix")
    if pairs["repeatCheckpoint"][2] != r1["pair"] or pairs["restoreTargetPair"][2] != matrix["pair"]:
        fail("Prepared pair differs from its reviewed wrapper")
    if record["contexts"]["repeatExpectedContext"] != r1["nativeContext"] or record["contexts"]["restoreTargetContext"] != matrix["nativeContext"]:
        fail("Prepared context differs from its reviewed wrapper")
    return record, state, pairs


def load_registered_caller():
    ensure_output_root()
    if CONFIG.is_symlink() or not CONFIG.is_file():
        fail("Installed observation config is missing or a symlink")
    for name, path in (("probe", PROBE), ("caller", CALLER), ("helper", HELPER), ("readback", READBACK)):
        regular(path)
        if file_digest(path) != PINS[name]:
            fail(f"Reviewed registration pin not installed for {name}")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if (
        config.get("action") != "observe"
        or config.get("timelineInventory") != "protected-six"
        or config.get("externalScriptingSetting") != "None"
        or config.get("projectName") != PROJECT_NAME
        or config.get("outputDir") != str(OUT)
        or config.get("probePath") != str(PROBE)
        or config.get("probeSha256") != PINS["probe"]
    ):
        fail("Installed config is not the reviewed observe/protected-six state")
    spec = importlib.util.spec_from_file_location("issue141_registered_native_caller", CALLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if "r1-repeat-restore-selection" not in module.ACTIONS or "r1-repeat-duplicate" not in module.ACTIONS:
        fail("Registered caller lacks the reviewed R1 routes")
    for action in ("r1-repeat-restore-selection", "r1-repeat-duplicate"):
        if module.DISPATCH_MODULES.get(action) != ("r1-repeat-six.py", PINS["helper"]):
            fail(f"Registered caller pin differs for {action}")
    return module


def load_execution_driver():
    regular(DRIVER, OUTPUT)
    spec = importlib.util.spec_from_file_location("issue141_existing_execution_driver", DRIVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "expected_context", None)):
        fail("Existing expected_context helper is unavailable")
    return module


def update_state(state, **updates):
    state.update(updates)
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def result_reference(result):
    if not isinstance(result, dict):
        return None
    path = Path(result.get("_nativeResultPath", ""))
    if path.is_symlink() or not path.is_file():
        return None
    return {"path": str(path), "sha256": file_digest(path)}


def invoke_once(native, updates, action, directory):
    native.validate(updates, None)
    request = directory / "request.json"
    request.write_text(json.dumps(updates, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        result = native.invoke(updates)
    except Exception as error:
        (directory / "terminal-error.json").write_text(json.dumps({"action": action, "error": f"{type(error).__name__}: {error}", "nativeDispatchPerformed": True}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise
    payload = {"action": action, "nativeDispatchPerformed": True, "result": result, "nativeResult": result_reference(result)}
    (directory / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def restore():
    record, state, pairs = load_prepared()
    if state.get("restoreAttempted") or state.get("finalDuplicateAttempted"):
        fail("Restoration sequence is already terminal; do not retry")
    native = load_registered_caller()
    updates = {
        "action": "r1-repeat-restore-selection",
        "case": CASE,
        "repeatCheckpoint": str(pairs["repeatCheckpoint"][0]),
        "repeatCheckpointSha256": pairs["repeatCheckpoint"][1],
        "repeatExpectedContext": record["contexts"]["repeatExpectedContext"],
        "restoreTargetPair": str(pairs["restoreTargetPair"][0]),
        "restoreTargetPairSha256": pairs["restoreTargetPair"][1],
        "restoreTargetContext": record["contexts"]["restoreTargetContext"],
    }
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    directory = OUT / f"r1-final-executor-restore-{stamp}"
    directory.mkdir()
    update_state(state, restoreAttempted=True, restoreStartedAt=stamp, restoreAuditDirectory=str(directory), restoreRequest=updates)
    try:
        result = invoke_once(native, updates, updates["action"], directory)
        if result.get("status") != "restored-selection" or result.get("pairExactlyEqual") is not True or result.get("contextExactlyEqual") is not True or result.get("selectedTimelineUid") != MATRIX:
            fail("Restoration result did not prove exact Matrix pair/context")
    except Exception as error:
        update_state(state, restoreStatus="terminal-failure", restoreError=f"{type(error).__name__}: {error}")
        raise
    update_state(state, restoreStatus="restored-selection", restoreResult=str(directory / "result.json"), restoreResultSha256=file_digest(directory / "result.json"))
    print(json.dumps({"status": "restored-selection", "nativeDispatchPerformed": True, "auditDirectory": str(directory)}, sort_keys=True))


def final_duplicate():
    record, state, pairs = load_prepared()
    if state.get("restoreStatus") != "restored-selection" or state.get("finalDuplicateAttempted"):
        fail("Final duplicate requires one successful restoration and is terminal")
    native = load_registered_caller()
    driver = load_execution_driver()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    directory = OUT / f"r1-final-executor-duplicate-{stamp}"
    directory.mkdir()
    update_state(state, finalDuplicateAttempted=True, finalDuplicateStartedAt=stamp, finalDuplicateAuditDirectory=str(directory))
    readback_updates = {"action": "editorial-readback", "editorialReadbackLabel": "editorial-context"}
    try:
        readback = invoke_once(native, readback_updates, readback_updates["action"], directory)
        if not isinstance(readback, dict) or readback.get("status") != "editorial-readback-retained":
            fail("Editorial context readback refused; duplicate is permanently skipped")
        reference = readback.get("pair", {})
        fresh_path = Path(reference.get("path", ""))
        regular(fresh_path)
        if OUT.resolve() not in fresh_path.resolve().parents or file_digest(fresh_path) != reference.get("sha256"):
            fail("Editorial pair path/hash is unsafe or changed")
        fresh_pair = json.loads(fresh_path.read_text(encoding="utf-8"))
        validate_pair(fresh_pair, MATRIX)
        if fresh_pair != pairs["restoreTargetPair"][2]:
            fail("Editorial pair differs from the exact restored Matrix target")
        context = driver.expected_context(readback, fresh_pair)
        if context != record["contexts"]["restoreTargetContext"]:
            fail("Derived editorial context differs from the restored Matrix context")
        checkpoint = OUT / f"r1-final-executor-{stamp}-duplicate-checkpoint.json"
        checkpoint.write_bytes(fresh_path.read_bytes())
        checkpoint_sha = file_digest(checkpoint)
        if checkpoint_sha != reference.get("sha256"):
            fail("Copied duplicate checkpoint hash differs")
        updates = {"action": "r1-repeat-duplicate", "case": CASE, "repeatCheckpoint": str(checkpoint), "repeatCheckpointSha256": checkpoint_sha, "repeatExpectedContext": context}
        result = invoke_once(native, updates, updates["action"], directory)
    except Exception as error:
        update_state(state, finalDuplicateStatus="terminal-failure", finalDuplicateError=f"{type(error).__name__}: {error}")
        raise
    update_state(state, finalDuplicateStatus="terminal-result", finalDuplicateResult=str(directory / "result.json"), finalDuplicateResultSha256=file_digest(directory / "result.json"))
    print(json.dumps({"status": "terminal-result", "nativeDispatchPerformed": True, "auditDirectory": str(directory), "nativeResult": result_reference(result)}, sort_keys=True))


def check():
    ensure_output_root()
    load_local_readiness()
    r1, matrix = read_wrapper("r1"), read_wrapper("matrix")
    prepared = READINESS.is_file() and STATE.is_file()
    if prepared:
        load_prepared()
    observed_pins = {name: file_digest(path) if path.is_file() and not path.is_symlink() else None for name, path in (("probe", PROBE), ("caller", CALLER), ("helper", HELPER), ("readback", READBACK))}
    registered = observed_pins == PINS
    print(json.dumps({"status": "offline-check-passed", "nativeDispatchPerformed": False, "wrapperPairHashes": {"r1": digest(r1["pairBytes"]), "matrix": digest(matrix["pairBytes"])}, "prepared": prepared, "reviewedRegistrationInstalled": registered, "next": "--restore only after root authorization" if registered and prepared else "await reviewed registration and/or --prepare"}, sort_keys=True))


def main():
    args = sys.argv[1:]
    if args == ["--check"]:
        check()
    elif args == ["--prepare"]:
        prepare()
    elif args == ["--restore"]:
        restore()
    elif args == ["--final-duplicate"]:
        final_duplicate()
    else:
        raise SystemExit("Usage: r1-final-native-executor-20261002.py [--check|--prepare|--restore|--final-duplicate]")


if __name__ == "__main__":
    main()
