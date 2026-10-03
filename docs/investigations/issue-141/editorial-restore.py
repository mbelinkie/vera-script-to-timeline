"""Restore only the approved R1-razor track locks and original playhead."""

import importlib.util
import json
import platform
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
BUILD = [21, 1, 0, 14, ""]
MATRIX_UID = "29ae8331-b86e-4041-a548-960695cc7b24"
MATRIX_NAME = "VERA 141 Batched Matrix"
BASELINE_UID = "88f7923d-55a7-471f-b09b-cf10f9fae8ad"
R1_UID = "aa2b8e36-83bd-4292-9e33-217c00ca192f"
SPLIT_PAIR = "r1-razor-split-20261001T051603.732674Z/pair.json"
SPLIT_PAIR_SHA = "5eabacdb141908d6bc5aa805136d5148913c3ab63936e19fc1dc9801fa448fba"
PREPARATION = "r1-razor-20261001T050302.404809Z/result.json"
PREPARATION_SHA = "1e8d9f8d9b6a0eb2f042ccf9ffd6be48afe8cca0e45d90b32e8f297985ff7d82"
READER_SHA = "06eff080c45e5c520a1c8c31787e4d4f1604198a3a98a9e3c8e025917fcf455b"
TARGET_LOCKS = (("video", 2), ("video", 3), ("audio", 2), ("audio", 3))
ORIGINAL_LOCKS = {
    "video:1": False,
    "video:2": False,
    "video:3": False,
    "audio:1": False,
    "audio:2": False,
    "audio:3": False,
}


def _reader(probe):
    path = Path(__file__).with_name("r4-range-repair.py")
    if path.is_symlink() or probe.sha256(path) != READER_SHA:
        raise RuntimeError("Pinned full-state reader changed")
    spec = importlib.util.spec_from_file_location("editorial_restore_reader", path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    return reader


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


def _inventory(state):
    return {
        row.get("GetUniqueId", {}).get("value"): row.get("GetName", {}).get("value")
        for row in state.get("timelines", [])
    }


def _track(timeline, kind, index):
    rows = [
        row
        for row in timeline.get("tracks", [])
        if row.get("type") == kind and row.get("index") == index
    ]
    if len(rows) != 1:
        raise RuntimeError(f"Exact {kind}{index} track is missing or duplicated")
    return rows[0]


def _pin(reader, output, relative, digest, probe):
    path = output / relative
    cursor = output
    for part in Path(relative).parts:
        cursor /= part
        if cursor.is_symlink() or not cursor.resolve().is_relative_to(output.resolve()):
            raise RuntimeError("Pinned evidence path escapes or links outside output")
    return reader._pin(path, path.name, digest, probe)


def _exact_context(resolve, config, identity, probe, reader):
    project = reader._context(resolve, config, identity, probe, MATRIX_UID)
    if (
        resolve.GetProductName() != "DaVinci Resolve Studio"
        or resolve.GetVersion() != BUILD
        or resolve.GetCurrentPage() != "edit"
        or project.GetCurrentRenderFormatAndCodec()
        != {"format": "mov", "codec": "H264"}
        or project.GetRenderJobList() != []
    ):
        raise RuntimeError("Exact Resolve Edit/MOV-H264/idle context required")
    timeline = project.GetCurrentTimeline()
    if timeline is None or timeline.GetUniqueId() != MATRIX_UID:
        raise RuntimeError("Matrix selection changed")
    return project, timeline


def run(resolve, config, *, probe):
    reader = _reader(probe)
    root = Path(probe.ROOT).resolve()
    output = Path(config.get("outputDir", ""))
    if (
        config.get("action") != "editorial-restore"
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != root / "out"
        or not output.name.startswith("issue-141-observation-")
        or resolve.GetProductName() != "DaVinci Resolve Studio"
        or resolve.GetVersion() != BUILD
    ):
        raise RuntimeError("Exact synthetic editorial restoration/build required")
    media, sources = reader._manifest(config, root, probe)
    if media.parent.resolve() != output.parent.resolve():
        raise RuntimeError("Synthetic source/output roots differ")

    pair_pin = _pin(reader, output, SPLIT_PAIR, SPLIT_PAIR_SHA, probe)
    preparation = _pin(reader, output, PREPARATION, PREPARATION_SHA, probe)
    if (
        pair_pin.get("selectedTimelineUid") != MATRIX_UID
        or pair_pin.get("timelineConsistency") != "equal-adjacent-reads"
        or pair_pin.get("poolConsistency") != "equal-adjacent-reads"
        or preparation.get("status") != "prepared-for-editorial-selection"
        or preparation.get("noEditorialCommandDispatched") is not True
        or preparation.get("originalLocks") != ORIGINAL_LOCKS
        or preparation.get("originalPlayhead") != "00:06:07:24"
        or preparation.get("split", {}).get("timecode") != "00:01:04:00"
    ):
        raise RuntimeError("Pinned split pair or restoration precondition is invalid")
    before_state, before_pool = reader._validate_read_pair(pair_pin, probe)
    expected_inventory = {
        MATRIX_UID: MATRIX_NAME,
        reader.R4_UID: reader.R4_NAME,
        BASELINE_UID: "VERA 141 Baseline",
        R1_UID: "VERA 141 R1 identity",
    }
    if (
        before_state.get("projectId") != PROJECT_ID
        or before_state.get("projectName") != config.get("projectName")
        or _inventory(before_state) != expected_inventory
    ):
        raise RuntimeError(
            "Pinned split pair does not bind the exact four-timeline project"
        )
    matrix_pin = reader._timeline(before_state, MATRIX_UID)
    for kind, index in TARGET_LOCKS:
        if _track(matrix_pin, kind, index).get("GetIsTrackLocked") != {"value": True}:
            raise RuntimeError(
                "Pinned split pair does not show the protected tracks locked"
            )
    expected_state = deepcopy(before_state)
    matrix_expected = reader._timeline(expected_state, MATRIX_UID)
    for kind, index in TARGET_LOCKS:
        _track(matrix_expected, kind, index)["GetIsTrackLocked"] = {"value": False}

    identity = {"projectId": PROJECT_ID, "projectName": config["projectName"]}
    _, timeline = _exact_context(resolve, config, identity, probe, reader)
    live_before = reader._read_pair(
        resolve, config, identity, sources, MATRIX_UID, probe
    )
    live_state, live_pool = reader._validate_read_pair(live_before, probe)
    if live_state != before_state or live_pool != before_pool:
        raise RuntimeError(
            "Fresh complete state/source evidence differs from split pin"
        )
    if timeline.GetCurrentTimecode() != preparation["split"]["timecode"]:
        raise RuntimeError("Split playhead moved before the bounded restoration")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    directory = output / f"editorial-restore-{stamp}"
    directory.mkdir(exist_ok=False)
    journal = directory / "journal.jsonl"
    journal.touch()
    reader._write(directory / "before.json", live_before)
    _append(journal, "FullReadback", "before", {"path": "before.json"})
    before_evidence = {
        "path": "before.json",
        "sha256": probe.sha256(directory / "before.json"),
    }
    result = {
        "status": "refused-partial-state-retained",
        "directory": str(directory),
        "journal": str(journal),
        "pins": {
            "splitPair": {"path": SPLIT_PAIR, "sha256": SPLIT_PAIR_SHA},
            "preparationResult": {"path": PREPARATION, "sha256": PREPARATION_SHA},
        },
        "originalLocks": ORIGINAL_LOCKS,
        "originalPlayhead": preparation["originalPlayhead"],
        "setters": [],
        "failure": None,
        "beforePair": before_evidence,
        "environment": {
            "productName": resolve.GetProductName(),
            "version": resolve.GetVersion(),
            "python": platform.python_version(),
        },
        "noEditorialCommandDispatched": True,
        "saveDispatched": False,
    }

    def setter(method, target, call):
        _exact_context(resolve, config, identity, probe, reader)
        result["setters"].append(method)
        _append(journal, method, "request", target)
        try:
            returned = call()
        except Exception as error:
            _append(
                journal,
                method,
                "failure",
                f"{type(error).__name__}: {error}",
            )
            raise
        _append(journal, method, "return", returned)
        if returned is not True:
            raise RuntimeError(f"{method} did not return true")
        _exact_context(resolve, config, identity, probe, reader)

    try:
        for kind, index in TARGET_LOCKS:
            _, timeline = _exact_context(resolve, config, identity, probe, reader)
            setter(
                "SetTrackLock",
                {"trackType": kind, "trackIndex": index, "locked": False},
                lambda kind=kind, index=index, timeline=timeline: timeline.SetTrackLock(
                    kind, index, False
                ),
            )
            if timeline.GetIsTrackLocked(kind, index) is not False:
                raise RuntimeError(f"{kind}{index} unlock did not read back")
        _, timeline = _exact_context(resolve, config, identity, probe, reader)
        setter(
            "SetCurrentTimecode",
            preparation["originalPlayhead"],
            lambda timeline=timeline: timeline.SetCurrentTimecode(
                preparation["originalPlayhead"]
            ),
        )
        if timeline.GetCurrentTimecode() != preparation["originalPlayhead"]:
            raise RuntimeError("Original Matrix playhead did not read back")
    except Exception as error:
        result["failure"] = f"{type(error).__name__}: {error}"

    try:
        after = reader._read_pair(resolve, config, identity, sources, MATRIX_UID, probe)
        reader._write(directory / "after.json", after)
        _append(journal, "FullReadback", "after", {"path": "after.json"})
        result["afterPair"] = {
            "path": "after.json",
            "sha256": probe.sha256(directory / "after.json"),
        }
        after_state, after_pool = reader._validate_read_pair(after, probe)
        _, current_timeline = _exact_context(
            resolve, config, identity, probe, reader
        )
        result["playheadAfter"] = current_timeline.GetCurrentTimecode()
        if (
            result["failure"] is None
            and after_state == expected_state
            and after_pool == before_pool
            and result["playheadAfter"] == preparation["originalPlayhead"]
            and result["setters"]
            == ["SetTrackLock"] * len(TARGET_LOCKS) + ["SetCurrentTimecode"]
        ):
            result["status"] = "restored-unsaved"
        elif result["failure"] is None:
            result["failure"] = "Full postflight differs from the bounded restoration"
    except Exception as error:
        result["postflightFailure"] = f"{type(error).__name__}: {error}"
    reader._write(directory / "result.json", result)
    return result
