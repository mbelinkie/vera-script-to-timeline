"""One non-ripple removal of the exact retained R4 occurrence."""

import importlib.util
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

CAPTURE_NAME = "capture-20261001T030157.768476Z.json"
CAPTURE_SHA = "75b854b050493a5179e2e2a5a5bf14964866efa31def9e59c22dd58cb49d26da"
POOL_NAME = "r4-pool-read-only-20261001T030157.768476Z.json"
POOL_SHA = "15c190c39212f29e159614c5805f5ed9a9319d943b159a98d4c243d003fb474a"
RANGE_SHA = "06eff080c45e5c520a1c8c31787e4d4f1604198a3a98a9e3c8e025917fcf455b"


def run(resolve, config, *, probe):
    path = Path(__file__).with_name("r4-range-repair.py")
    if path.is_symlink() or probe.sha256(path) != RANGE_SHA:
        raise RuntimeError("Pinned R4 reader changed")
    spec = importlib.util.spec_from_file_location("issue141_removal_reader", path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    root, output = Path(probe.ROOT).resolve(), Path(config.get("outputDir", ""))
    if (
        config.get("action") != "r4-occurrence-remove"
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != root / "out"
        or not output.name.startswith("issue-141-observation-")
        or resolve.GetProductName() != "DaVinci Resolve Studio"
        or resolve.GetVersion() != reader.BUILD
    ):
        raise RuntimeError("Exact owned R4 action/project/build required")
    _, expected = reader._manifest(config, root, probe)
    cap = reader._pin(output / CAPTURE_NAME, CAPTURE_NAME, CAPTURE_SHA, probe)
    pool = reader._pin(output / POOL_NAME, POOL_NAME, POOL_SHA, probe)
    pinned = reader._equal_pair(cap.get("passes"), probe, "Timeline pin")
    pinned_pool = reader._equal_pair(pool.get("passes"), probe, "Pool pin")
    if (
        cap.get("consistency") != "equal-adjacent-reads"
        or pool.get("status") != "equal-read-only-pool-inventory"
        or pool.get("capture", {}).get("sha256") != CAPTURE_SHA
        or pinned.get("projectId") != reader.PROJECT_ID
        or pinned.get("projectName") != config.get("projectName")
    ):
        raise RuntimeError("Incomplete or wrong native removal checkpoint")
    identity = {"projectId": reader.PROJECT_ID, "projectName": config["projectName"]}
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence = output / f"r4-removal-{stamp}"
    evidence.mkdir()
    journal = evidence / "journal.jsonl"
    journal.touch(exist_ok=False)

    def context():
        project = reader._context(resolve, config, identity, probe, reader.R4_UID)
        if (
            resolve.GetCurrentPage() != "deliver"
            or project.GetCurrentRenderFormatAndCodec()
            != {"format": "mov", "codec": "H264"}
            or project.GetRenderJobList() != []
        ):
            raise RuntimeError("R4/Deliver/known-format/idle empty queue required")
        return project

    def capture(label):
        context()
        value = reader._read_pair(
            resolve, config, identity, expected, reader.R4_UID, probe
        )
        reader._write(evidence / f"{label}.json", value)
        reader._append(journal, "Capture", label, value)
        context()
        return value

    before = capture("preflight")
    state, inventory = reader._validate_read_pair(before, probe)
    if state != pinned or inventory != pinned_pool:
        raise RuntimeError("Fresh full R4 removal preflight differs")
    target = reader._timeline(state, reader.R4_UID)
    items = [(t, i) for t in target.get("tracks", []) for i in t.get("items", [])]
    if len(items) != 1:
        raise RuntimeError("Exact sole R4 occurrence required")
    track, item = items[0]
    if (
        (track.get("type"), track.get("index")) != ("video", 1)
        or item.get("GetUniqueId") != {"value": reader.ITEM_UID}
        or item.get("GetMediaPoolItem", {}).get("GetUniqueId")
        != {"value": reader.MEDIA_UID}
        or item.get("GetStart") != {"value": -90000}
        or item.get("GetEnd") != {"value": -89801}
    ):
        raise RuntimeError("Exact retained R4 occurrence binding changed")
    reader._pool_matches(inventory, expected)
    timeline = context().GetCurrentTimeline()
    handles = timeline.GetItemListInTrack("video", 1)
    if (
        not isinstance(handles, list)
        or len(handles) != 1
        or handles[0].GetUniqueId() != reader.ITEM_UID
        or handles[0].GetMediaPoolItem().GetUniqueId() != reader.MEDIA_UID
    ):
        raise RuntimeError("Native delete handle does not match the pinned occurrence")
    context()
    reader._append(
        journal,
        "Timeline.DeleteClips",
        "request",
        {"uids": [reader.ITEM_UID], "ripple": False},
    )
    returned, failure = None, None
    try:
        returned = timeline.DeleteClips(handles, False)
        reader._append(journal, "Timeline.DeleteClips", "return", returned)
    except Exception as error:
        failure = f"{type(error).__name__}: {error}"
        reader._append(journal, "Timeline.DeleteClips", "failure", failure)
    # Post-mutation failures retain raw evidence without rollback.
    after = capture("postflight")
    after_state, after_pool = reader._validate_read_pair(after, probe)
    reader._manifest(config, root, probe)
    reader._pool_matches(after_pool, expected)
    expected_state = deepcopy(state)
    for row in reader._timeline(expected_state, reader.R4_UID)["tracks"]:
        row["items"] = []
    compared_pool = deepcopy(after_pool)
    old_source = next(r for r in inventory["items"] if r["uid"] == reader.MEDIA_UID)
    new_source = next(r for r in compared_pool["items"] if r["uid"] == reader.MEDIA_UID)
    old_props = old_source["evidence"]["GetClipProperty"]["value"]
    new_props = new_source["evidence"]["GetClipProperty"]["value"]
    usage_changed = old_props.get("Usage") == "1" and new_props.get("Usage") == "0"
    if usage_changed:
        new_props["Usage"] = old_props["Usage"]
    absent = not any(
        i.get("GetUniqueId") == {"value": reader.ITEM_UID}
        for t in after_state["timelines"]
        for tr in t.get("tracks", [])
        for i in tr.get("items", [])
    )
    verified = (
        returned is True
        and failure is None
        and absent
        and after_state == expected_state
        and usage_changed
        and compared_pool == inventory
    )
    result = {
        "status": "removed-source-retained"
        if verified
        else "removal-outcome-review-required",
        "deleteReturn": returned,
        "deleteError": failure,
        "removedOccurrenceUid": reader.ITEM_UID,
        "occurrenceAbsent": absent,
        "sourcePoolUid": reader.MEDIA_UID,
        "sourcePoolPresentAndOnline": True,
        "anticipatedContentAndUsageOnly": verified,
        "journal": str(journal),
        "before": str(evidence / "preflight.json"),
        "after": str(evidence / "postflight.json"),
        "limits": [
            "No asset deletion inferred. Restoration and output remain pending."
        ],
    }
    reader._write(evidence / "result.json", result)
    reader._append(journal, "R4Removal", "complete", result)
    return result
