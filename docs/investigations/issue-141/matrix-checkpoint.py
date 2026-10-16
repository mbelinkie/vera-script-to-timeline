"""Select the saved Matrix timeline after the pinned R4 state is saved."""

import hashlib
import json
import types
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
PROJECT_NAME_PREFIX = "VERA Issue 141 Synthetic Probe "
BUILD = [21, 1, 0, 14, ""]
R4_UID = "64de8a4c-86bd-4f19-9d20-47b8940f610b"
R4_NAME = "VERA 141 R4 availability"
MATRIX_UID = "29ae8331-b86e-4041-a548-960695cc7b24"
MATRIX_NAME = "VERA 141 Batched Matrix"
BASELINE_UID = "88f7923d-55a7-471f-b09b-cf10f9fae8ad"
R1_UID = "aa2b8e36-83bd-4292-9e33-217c00ca192f"

R4_CAPTURE_NAME = "capture-20261001T003310.397326Z.json"
R4_CAPTURE_SHA256 = "f3a321fcd5ae47c90e25b3dcf254a0d983ff0bdde8862700b2411c710b3fe0fa"
R4_POOL_NAME = "r4-pool-read-only-20261001T003310.397326Z.json"
R4_POOL_SHA256 = "ac6f4661f59f910029dae51dcc758bd1d766e8f810fb4996fcee1b18c681e751"
MATRIX_CAPTURE_NAME = "capture-20260930T223313.312609Z-saved.json"
MATRIX_CAPTURE_SHA256 = (
    "a29402d405ab8cf1bc1abedd4c1ed0c479e983e2ef3ba6fc41d1c2389d6d36d2"
)
R4_FINALIZER_SHA256 = "4e9587bcb5d78258fabf50de57d0c14b6ae9769de3c06281d4fc05f5971ab420"
FINALIZE_JOURNAL_NAME = "r4-finalize-20261001T005016.518644Z.jsonl"
FINALIZE_JOURNAL_SHA256 = (
    "82c3bfbf88497bc110a2198e5a685086e6a6f61cb7ec35af4314e95cb4ebf894"
)
FINALIZE_RESULT_NAME = "vera-issue-141-observation-result-20261001T005016.027177Z.json"
FINALIZE_RESULT_SHA256 = (
    "e9bfe830d653e706d8be7e6a601e139655e53adff55b30c8eb4346071050b9b3"
)
FINALIZE_RESULT_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)


class CheckpointRefused(RuntimeError):
    """A refusal already has a retained result record."""


def _r4_module():
    path = Path(__file__).with_name("r4-finalize.py")
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != R4_FINALIZER_SHA256:
        raise RuntimeError("Pinned R4 finalizer validator source changed")
    module = types.ModuleType("issue141_r4_finalize")
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


def _canonical(value):
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


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


def _differences(expected, actual, path=""):
    if expected == actual:
        return []
    if isinstance(expected, dict) and isinstance(actual, dict):
        rows = []
        for key in sorted(expected.keys() | actual.keys()):
            child = f"{path}/{str(key).replace('~', '~0').replace('/', '~1')}"
            if key not in expected:
                rows.append(
                    {
                        "path": child,
                        "expected": {"$missing": True},
                        "actual": actual[key],
                    }
                )
            elif key not in actual:
                rows.append(
                    {
                        "path": child,
                        "expected": expected[key],
                        "actual": {"$missing": True},
                    }
                )
            else:
                rows.extend(_differences(expected[key], actual[key], child))
        return rows
    if isinstance(expected, list) and isinstance(actual, list):
        rows = []
        for index in range(max(len(expected), len(actual))):
            child = f"{path}/{index}"
            if index >= len(expected):
                rows.append(
                    {
                        "path": child,
                        "expected": {"$missing": True},
                        "actual": actual[index],
                    }
                )
            elif index >= len(actual):
                rows.append(
                    {
                        "path": child,
                        "expected": expected[index],
                        "actual": {"$missing": True},
                    }
                )
            else:
                rows.extend(_differences(expected[index], actual[index], child))
        return rows
    return [{"path": path or "/", "expected": expected, "actual": actual}]


def _current_uid(project):
    timeline = project.GetCurrentTimeline()
    uid = None if timeline is None else timeline.GetUniqueId()
    if not isinstance(uid, str) or not uid:
        raise RuntimeError("Current timeline identity is unreadable")
    return uid


def _require_project(resolve, config, identity, probe):
    project = probe.require_current(resolve, config, identity)
    if (
        project.GetUniqueId() != PROJECT_ID
        or project.GetName() != config["projectName"]
    ):
        raise RuntimeError("Exact Issue 141 project identity changed")
    ids = {}
    count = project.GetTimelineCount()
    if not isinstance(count, int) or count < 1:
        raise RuntimeError("Timeline inventory is unreadable")
    for index in range(1, count + 1):
        timeline = project.GetTimelineByIndex(index)
        if timeline is None:
            raise RuntimeError("Timeline identity is unreadable")
        uid, name = timeline.GetUniqueId(), timeline.GetName()
        if (
            not isinstance(uid, str)
            or not uid
            or not isinstance(name, str)
            or uid in ids
        ):
            raise RuntimeError("Timeline identity is missing or duplicated")
        ids[uid] = name
    expected = {
        R4_UID: R4_NAME,
        MATRIX_UID: MATRIX_NAME,
        BASELINE_UID: "VERA 141 Baseline",
        R1_UID: "VERA 141 R1 identity",
    }
    if ids != expected:
        raise RuntimeError("Named timeline UID/name inventory changed")
    return project


def _timeline_handle(project, uid, name):
    matches = []
    for index in range(1, project.GetTimelineCount() + 1):
        timeline = project.GetTimelineByIndex(index)
        if timeline is not None and timeline.GetUniqueId() == uid:
            matches.append(timeline)
    if len(matches) != 1 or matches[0].GetName() != name:
        raise RuntimeError("Exact target timeline handle is missing or duplicated")
    return matches[0]


def _read_pair(resolve, config, identity, expected, selected_uid, probe):
    observations, inventories = [], []
    for _ in range(2):
        project = _require_project(resolve, config, identity, probe)
        if _current_uid(project) != selected_uid:
            raise RuntimeError("Selected timeline changed during checkpoint read")
        observation = _canonical(probe.observe(resolve, config, identity, expected))
        project = _require_project(resolve, config, identity, probe)
        if _current_uid(project) != selected_uid:
            raise RuntimeError("Selected timeline changed during observation")
        inventory = _canonical(probe._r4_pool_inventory(project, expected))
        project = _require_project(resolve, config, identity, probe)
        if _current_uid(project) != selected_uid:
            raise RuntimeError("Selected timeline changed during pool inventory")
        observations.append(observation)
        inventories.append(inventory)
    return {
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


def _matrix_differences(observation, matrix_pin):
    rows = []
    for field in ("projectId", "projectName", "GetSettings"):
        rows.extend(
            _differences(matrix_pin.get(field), observation.get(field), f"/{field}")
        )
    expected = {
        row.get("GetUniqueId", {}).get("value"): row for row in matrix_pin["timelines"]
    }
    actual = {
        row.get("GetUniqueId", {}).get("value"): row
        for row in observation.get("timelines", [])
    }
    if set(expected) != {MATRIX_UID, BASELINE_UID, R1_UID}:
        raise RuntimeError("Saved Matrix pin lacks its exact historical timelines")
    for uid, timeline in expected.items():
        if uid not in actual:
            rows.append(
                {
                    "path": f"/timelines/{uid}",
                    "expected": timeline,
                    "actual": {"$missing": True},
                }
            )
        else:
            rows.extend(_differences(timeline, actual[uid], f"/timelines/{uid}"))
    return rows


def _restore_r4(resolve, config, identity, expected, probe, journal, stamp, reason):
    """Restore only the prior selection after exact project/timeline checks."""
    try:
        project = _require_project(resolve, config, identity, probe)
        current = _current_uid(project)
        if current == R4_UID:
            _append(journal, "RestoreR4Selection", "already-selected", R4_UID)
            return _read_pair(
                resolve, config, identity, expected["sourceHashes"], R4_UID, probe
            )
        if current != MATRIX_UID:
            raise RuntimeError("Current selection is not the exact prior or target UID")
        target = _timeline_handle(project, R4_UID, R4_NAME)
        _append(journal, "SetCurrentTimeline", "restore-request", R4_UID)
        returned = project.SetCurrentTimeline(target)
        _append(journal, "SetCurrentTimeline", "restore-return", returned)
        if returned is not True:
            raise RuntimeError("Restoring prior R4 selection did not return true")
        project = _require_project(resolve, config, identity, probe)
        if _current_uid(project) != R4_UID:
            raise RuntimeError("Prior R4 selection did not read back")
        payload = _read_pair(
            resolve, config, identity, expected["sourceHashes"], R4_UID, probe
        )
        if (
            payload["timelineConsistency"] != "equal-adjacent-reads"
            or payload["poolConsistency"] != "equal-adjacent-reads"
            or payload["poolPasses"][0] != expected["poolPass"]
            or payload["timelinePasses"][0] != expected["r4Pass"]
        ):
            raise RuntimeError("Restored R4 observations differ from pinned state")
        _write(
            Path(config["outputDir"]) / f"matrix-checkpoint-{stamp}-restored-r4.json",
            payload,
        )
        _append(
            journal,
            "RestoreR4Selection",
            "complete",
            {"reason": reason, "selectedTimelineUid": R4_UID},
        )
        return payload
    except Exception as error:
        _append(
            journal, "RestoreR4Selection", "refused", f"{type(error).__name__}: {error}"
        )
        return {"error": f"{type(error).__name__}: {error}"}


def _verify_finalizer_completion(output, probe):
    """Require the pinned successful save request before selection is allowed."""
    journal_path = output / FINALIZE_JOURNAL_NAME
    result_path = FINALIZE_RESULT_ROOT / FINALIZE_RESULT_NAME
    if (
        journal_path.is_symlink()
        or not journal_path.is_file()
        or probe.sha256(journal_path) != FINALIZE_JOURNAL_SHA256
        or result_path.is_symlink()
        or not result_path.is_file()
        or probe.sha256(result_path) != FINALIZE_RESULT_SHA256
    ):
        raise RuntimeError(
            "Pinned successful R4 save-finalization evidence is absent or changed"
        )
    try:
        rows = [
            json.loads(line)
            for line in journal_path.read_text(encoding="utf-8").splitlines()
        ]
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "Pinned successful R4 finalization evidence is unreadable"
        ) from error
    requests = [
        row
        for row in rows
        if row.get("method") == "SaveProject" and row.get("phase") == "request"
    ]
    returns = [
        row
        for row in rows
        if row.get("method") == "SaveProject" and row.get("phase") == "return"
    ]
    complete = any(
        row.get("method") == "R4Finalize"
        and row.get("phase") == "complete"
        and row.get("value", {}).get("status") == "saved-pinned-r4-state"
        for row in rows
    )
    if (
        not complete
        or result.get("status") != "saved-pinned-r4-state"
        or len(requests) != 1
        or len(returns) != 1
        or returns[0].get("value") is not True
    ):
        raise RuntimeError(
            "Pinned successful R4 finalization completion is not evidenced"
        )


def run(resolve, config, *, probe):
    """Select Matrix once, retain complete reads, and restore R4 on refusal."""
    output = Path(config.get("outputDir", ""))
    root = Path(probe.ROOT).resolve()
    if (
        config.get("action") != "matrix-checkpoint"
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != (root / "out").resolve()
        or not output.name.startswith("issue-141-observation-")
    ):
        raise RuntimeError("Only the existing named Issue 141 output may be checked")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    journal = output / f"matrix-checkpoint-{stamp}.jsonl"
    journal.open("x", encoding="utf-8").close()
    r4 = _r4_module()
    identity = {"projectId": PROJECT_ID, "projectName": config.get("projectName")}
    try:
        if (
            resolve.GetProductName() != "DaVinci Resolve Studio"
            or resolve.GetVersion() != BUILD
        ):
            raise RuntimeError("Exact Resolve Studio 21.1.0 build 14 required")
        if not isinstance(identity["projectName"], str) or not identity[
            "projectName"
        ].startswith(PROJECT_NAME_PREFIX):
            raise RuntimeError("Named Issue 141 project is required")
        r4_capture_path = output / R4_CAPTURE_NAME
        r4_capture = r4._load_pin(r4_capture_path, R4_CAPTURE_SHA256, probe)
        r4_pool_file = r4._load_pin(output / R4_POOL_NAME, R4_POOL_SHA256, probe)
        r4_pass = r4._validate_capture(r4_capture, probe)
        r4_pool_pass = r4._validate_pool(r4_pool_file, r4_capture_path, probe)
        if (
            r4_pass.get("projectId") != PROJECT_ID
            or r4_pass.get("projectName") != identity["projectName"]
            or r4_capture.get("environment", {}).get("version") != BUILD
            or r4_capture.get("stage") != "R4-post-append-partial-state-read-only"
        ):
            raise RuntimeError("Pinned R4 read-only capture identity differs")
        matrix_path = output / MATRIX_CAPTURE_NAME
        matrix_capture = r4._load_pin(matrix_path, MATRIX_CAPTURE_SHA256, probe)
        matrix_pass = r4._validate_capture(matrix_capture, probe)
        if (
            matrix_pass.get("projectId") != PROJECT_ID
            or matrix_pass.get("projectName") != identity["projectName"]
            or matrix_capture.get("environment", {}).get("version") != BUILD
        ):
            raise RuntimeError("Saved Matrix capture identity differs")
        expected = r4._validate_media(config, root, r4_pass, r4_pool_pass, probe)
        r4._timeline(r4_pass, R4_UID)
        if matrix_pass.get("timelines") is None:
            raise RuntimeError("Saved Matrix timeline records are missing")
        expected = {
            "sourceHashes": expected,
            "r4Pass": r4_pass,
            "poolPass": r4_pool_pass,
        }
        _verify_finalizer_completion(output, probe)
    except Exception as error:
        _append(
            journal, "MatrixCheckpoint", "refusal", f"{type(error).__name__}: {error}"
        )
        refusal = {"status": "refused", "reason": f"{type(error).__name__}: {error}"}
        _write(output / f"matrix-checkpoint-{stamp}-result.json", refusal)
        raise

    stamps = {
        "action": config["action"],
        "projectId": PROJECT_ID,
        "projectName": identity["projectName"],
        "r4Capture": {"filename": R4_CAPTURE_NAME, "sha256": R4_CAPTURE_SHA256},
        "r4Pool": {"filename": R4_POOL_NAME, "sha256": R4_POOL_SHA256},
        "matrixCapture": {
            "filename": MATRIX_CAPTURE_NAME,
            "sha256": MATRIX_CAPTURE_SHA256,
        },
        "externalScriptingSetting": config["externalScriptingSetting"],
    }
    _append(journal, "MatrixCheckpoint", "start", stamps)

    def refuse(reason, evidence, *, restore=False):
        restored = None
        if restore:
            restored = _restore_r4(
                resolve, config, identity, expected, probe, journal, stamp, reason
            )
        result = {
            "status": "refused",
            "reason": reason,
            "evidence": evidence,
            "restoredR4": restored,
            "stamps": stamps,
        }
        _append(
            journal,
            "MatrixCheckpoint",
            "refusal",
            {"reason": reason, "restoredR4": restored is not None},
        )
        _write(output / f"matrix-checkpoint-{stamp}-result.json", result)
        raise CheckpointRefused(reason)

    probe_config = dict(config, stage="R4-to-Matrix-selection-checkpoint")
    try:
        before = _read_pair(
            resolve, probe_config, identity, expected["sourceHashes"], R4_UID, probe
        )
        _write(output / f"matrix-checkpoint-{stamp}-r4-preflight.json", before)
        _append(journal, "R4Preflight", "readback", before)
        if (
            before["timelineConsistency"] != "equal-adjacent-reads"
            or before["poolConsistency"] != "equal-adjacent-reads"
            or before["timelinePasses"] != [r4_pass, r4_pass]
            or before["poolPasses"] != [r4_pool_pass, r4_pool_pass]
        ):
            refuse(
                "Fresh selected-R4 observation or pool inventory differs from pins",
                before,
            )
    except CheckpointRefused:
        raise
    except Exception as error:
        refuse(
            f"R4 preflight refused: {type(error).__name__}: {error}",
            locals().get("before"),
        )

    try:
        project = _require_project(resolve, probe_config, identity, probe)
        if _current_uid(project) != R4_UID:
            refuse(
                "Exact R4 timeline must remain selected before Matrix selection", before
            )
        matrix_handle = _timeline_handle(project, MATRIX_UID, MATRIX_NAME)
        _append(journal, "SetCurrentTimeline", "request", MATRIX_UID)
        returned = project.SetCurrentTimeline(matrix_handle)
        _append(journal, "SetCurrentTimeline", "return", returned)
        if returned is not True:
            refuse(
                "SetCurrentTimeline(Matrix) did not return true",
                {"before": before},
                restore=True,
            )
        project = _require_project(resolve, probe_config, identity, probe)
        if _current_uid(project) != MATRIX_UID:
            refuse(
                "Exact Matrix timeline selection did not read back",
                {"before": before},
                restore=True,
            )
    except CheckpointRefused:
        raise
    except Exception as error:
        refuse(
            f"Matrix selection failed: {type(error).__name__}: {error}",
            {"before": before},
            restore=True,
        )

    try:
        after = _read_pair(
            resolve, probe_config, identity, expected["sourceHashes"], MATRIX_UID, probe
        )
        _write(output / f"matrix-checkpoint-{stamp}-matrix-observation.json", after)
        _append(journal, "MatrixObservation", "readback", after)
        if (
            after["timelineConsistency"] != "equal-adjacent-reads"
            or after["poolConsistency"] != "equal-adjacent-reads"
        ):
            refuse(
                "Matrix-selected full observation or pool inventory is inconsistent",
                {"before": before, "after": after},
                restore=True,
            )
        if after["poolPasses"] != [r4_pool_pass, r4_pool_pass]:
            refuse(
                "Complete R4 pool inventory changed after selection",
                {"before": before, "after": after},
                restore=True,
            )
        for observation in after["timelinePasses"]:
            differences = _matrix_differences(observation, matrix_pass)
            if differences:
                refuse(
                    "Historical Matrix/Baseline/R1 timeline or settings differ",
                    {"before": before, "after": after, "differences": differences},
                    restore=True,
                )
            r4._validate_media(config, root, observation, r4_pool_pass, probe)
    except CheckpointRefused:
        raise
    except Exception as error:
        refuse(
            f"Matrix-context verification refused: {type(error).__name__}: {error}",
            {"before": before, "after": locals().get("after")},
            restore=True,
        )

    result = {
        "status": "selected-matrix-checkpoint",
        "selectedTimelineUid": MATRIX_UID,
        "preflight": f"matrix-checkpoint-{stamp}-r4-preflight.json",
        "matrixObservation": f"matrix-checkpoint-{stamp}-matrix-observation.json",
        "journal": journal.name,
        "stamps": stamps,
        "limits": [
            "Selection-only observation; "
            "no content/source/settings/save/render mutation.",
            "Equal adjacent reads do not establish atomicity or exclude ABA changes.",
        ],
    }
    _append(journal, "MatrixCheckpoint", "complete", result)
    result_path = output / f"matrix-checkpoint-{stamp}-result.json"
    _write(result_path, result)
    result["result"] = result_path.name
    return result
