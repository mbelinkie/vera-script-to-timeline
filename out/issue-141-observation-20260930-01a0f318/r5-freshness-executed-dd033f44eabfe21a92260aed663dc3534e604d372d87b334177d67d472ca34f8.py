"""Controlled marker metadata change between two real observation reads."""

import importlib.util
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

CAPTURE_NAME = "capture-20261001T034129.233236Z.json"
CAPTURE_SHA = "690bac86a68ca1ba7a168071bf7df3fe01d172e7f258303183163c1bf25e90da"
POOL_NAME = "r4-pool-read-only-20261001T034129.233236Z.json"
POOL_SHA = "4b9fd9ba0f6bc006ceabf6d6658f1e971369de68d6042ad7042b3b25e0ec8437"
READER_SHA = "06eff080c45e5c520a1c8c31787e4d4f1604198a3a98a9e3c8e025917fcf455b"


def run(resolve, config, *, probe):
    path = Path(__file__).with_name("r4-range-repair.py")
    if path.is_symlink() or probe.sha256(path) != READER_SHA:
        raise RuntimeError("Pinned complete reader changed")
    spec = importlib.util.spec_from_file_location("freshness_reader", path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    if (
        config.get("action") != "r5-freshness"
        or config.get("externalScriptingSetting") != "None"
    ):
        raise RuntimeError("Exact controlled R5 action required")
    output = Path(config["outputDir"])
    if (
        not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != Path(probe.ROOT).resolve() / "out"
        or not output.name.startswith("issue-141-observation-")
        or resolve.GetProductName() != "DaVinci Resolve Studio"
        or resolve.GetVersion() != reader.BUILD
    ):
        raise RuntimeError("Exact synthetic output/build required")
    _, sources = reader._manifest(config, Path(probe.ROOT).resolve(), probe)
    cap = reader._pin(output / CAPTURE_NAME, CAPTURE_NAME, CAPTURE_SHA, probe)
    pool = reader._pin(output / POOL_NAME, POOL_NAME, POOL_SHA, probe)
    if (
        cap.get("consistency") != "equal-adjacent-reads"
        or pool.get("status") != "equal-read-only-pool-inventory"
        or pool.get("capture", {}).get("sha256") != CAPTURE_SHA
    ):
        raise RuntimeError("Complete paired checkpoint binding required")
    baseline = reader._equal_pair(cap["passes"], probe, "Pinned timeline")
    inventory = reader._equal_pair(pool["passes"], probe, "Pinned pool")
    identity = {"projectId": reader.PROJECT_ID, "projectName": config["projectName"]}
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    directory = output / f"r5-freshness-{stamp}"
    directory.mkdir()
    journal = directory / "journal.jsonl"
    journal.touch()

    def context():
        project = reader._context(resolve, config, identity, probe, reader.R4_UID)
        if (
            resolve.GetCurrentPage() != "edit"
            or project.GetCurrentRenderFormatAndCodec()
            != {"format": "mov", "codec": "H264"}
            or project.GetRenderJobList() != []
        ):
            raise RuntimeError("Pinned Edit/known format/idle queue required")
        return project

    def snapshot(label):
        context()
        pair = reader._read_pair(
            resolve, config, identity, sources, reader.R4_UID, probe
        )
        reader._write(directory / f"{label}.json", pair)
        reader._append(journal, "Capture", label, {"path": f"{label}.json"})
        context()
        return reader._validate_read_pair(pair, probe)

    first, first_pool = snapshot("preflight")
    if first != baseline or first_pool != inventory:
        raise RuntimeError("Fresh full state differs from pinned checkpoint")
    markers = reader._timeline(first, reader.MATRIX_UID)["GetMarkers"]["value"]
    if "0" not in markers or not isinstance(markers["0"].get("customData"), str):
        raise RuntimeError("Exact existing marker customData is unreadable")
    original = markers["0"]["customData"]
    project = context()
    handles = [
        project.GetTimelineByIndex(index)
        for index in range(1, project.GetTimelineCount() + 1)
        if project.GetTimelineByIndex(index).GetUniqueId() == reader.MATRIX_UID
    ]
    if len(handles) != 1 or handles[0].GetMarkerCustomData(0) != original:
        raise RuntimeError("Exact existing Matrix marker handle changed")
    marker = handles[0]
    temporary = original + f" | issue141 controlled interpass {stamp}"

    def update(value, label):
        context()
        reader._append(
            journal,
            "UpdateMarkerCustomData",
            "request",
            {
                "timelineUid": reader.MATRIX_UID,
                "frame": 0,
                "customData": value,
                "label": label,
            },
        )
        returned, error = None, None
        try:
            returned = marker.UpdateMarkerCustomData(0, value)
        except Exception as failure:
            error = f"{type(failure).__name__}: {failure}"
        reader._append(
            journal,
            "UpdateMarkerCustomData",
            "return",
            {
                "value": returned,
                "error": error,
                "label": label,
            },
        )
        return returned, error

    returned, error = update(temporary, "interpass-edit")
    second, second_pool = snapshot("after-edit")
    refusal = probe.consistency(first, second, probe.errors([first, second]))
    anticipated = deepcopy(first)
    reader._timeline(anticipated, reader.MATRIX_UID)["GetMarkers"]["value"]["0"][
        "customData"
    ] = temporary
    exact = second == anticipated and second_pool == first_pool
    restored = second == first and second_pool == first_pool
    restore_return, restore_error = None, None
    if exact and marker.GetMarkerCustomData(0) == temporary:
        restore_return, restore_error = update(original, "exact-restoration")
        third, third_pool = snapshot("restored")
        restored = third == first and third_pool == first_pool
    result = {
        "status": "controlled-change-refused-and-restored"
        if returned is True
        and error is None
        and exact
        and refusal == "inconsistent-refused"
        and restore_return is True
        and restore_error is None
        and restored
        else "freshness-outcome-review-required",
        "interpassReturn": returned,
        "interpassError": error,
        "comparisonStatus": refusal,
        "onlyMarkerCustomDataChanged": exact,
        "restoreReturn": restore_return,
        "restoreError": restore_error,
        "originalFullStateRestored": restored,
        "journal": str(journal),
        "directory": str(directory),
        "limits": [
            "Controlled metadata change between reads, not a simultaneous UI race.",
            "No atomic revision token or exclusion of ABA changes is established.",
            "Marker note/name and clip movement remain separate untested cases.",
        ],
    }
    reader._write(directory / "result.json", result)
    return result
