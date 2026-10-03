"""One guarded append of the retained R4 source after verified removal."""

import importlib.util
import json
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

REMOVAL_DIR = "r4-removal-20261001T031304.352470Z"
REMOVAL_RESULT = "result.json"
REMOVAL_RESULT_SHA = "ea3b12ee502d458338756b56a1f4480f1cd4b994aa33c05887b23622aaca6b19"
REMOVAL_POST = "postflight.json"
REMOVAL_POST_SHA = "3a2b243dd238da5161546388f925a2b362ed75dd3ee44d5a70c625a7e307db2f"
REMOVAL_JOURNAL = "journal.jsonl"
REMOVAL_JOURNAL_SHA = "0e38af596d84be9fa482343dff33c456387eac7f0aefbc69d1e16a799d1a8c7f"
REMOVAL_PRE = "preflight.json"
REMOVAL_PRE_SHA = "663990e2b372bbe713365b14430d218cb25943c68b8be52c5c81b8c3415ece3b"
RANGE_REPAIR_SHA = "06eff080c45e5c520a1c8c31787e4d4f1604198a3a98a9e3c8e025917fcf455b"


def _reader(probe):
    path = Path(__file__).with_name("r4-range-repair.py")
    if path.is_symlink() or probe.sha256(path) != RANGE_REPAIR_SHA:
        raise RuntimeError("Pinned R4 full-state reader changed")
    spec = importlib.util.spec_from_file_location("issue141_reprepare_reader", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def _source_handle(folder, uid):
    found = []
    seen = set()

    def visit(node):
        key = node.GetUniqueId()
        if key in seen:
            raise RuntimeError("Media-pool folder cycle or duplicate folder UID")
        seen.add(key)
        for item in node.GetClipList() or []:
            if item is not None and item.GetUniqueId() == uid:
                found.append(item)
        for child in node.GetSubFolderList() or []:
            visit(child)

    visit(folder)
    if len(found) != 1:
        raise RuntimeError("Exact retained source UID is missing or duplicated")
    return found[0]


def _items(state, reader):
    timeline = reader._timeline(state, reader.R4_UID)
    return [
        (track, item)
        for track in timeline.get("tracks", [])
        for item in track.get("items", [])
    ]


def _return_evidence(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_return_evidence(item) for item in value]
    uid = getattr(value, "GetUniqueId", None)
    if callable(uid):
        try:
            return {"type": type(value).__name__, "uid": uid()}
        except Exception:
            pass
    return {"type": type(value).__name__}


def _changed_paths(before, after, prefix=""):
    if isinstance(before, dict) and isinstance(after, dict):
        paths = []
        for key in sorted(before.keys() | after.keys()):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in before or key not in after:
                paths.append(path)
            else:
                paths.extend(_changed_paths(before[key], after[key], path))
        return paths
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            return [f"{prefix}.length"]
        paths = []
        for index, (left, right) in enumerate(zip(before, after, strict=True)):
            paths.extend(_changed_paths(left, right, f"{prefix}[{index}]"))
        return paths
    return [] if before == after else [prefix]


def run(resolve, config, *, probe):
    reader = _reader(probe)
    root = Path(probe.ROOT).resolve()
    output = Path(config.get("outputDir", ""))
    if (
        config.get("action") != "r4-reprepare"
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != root / "out"
        or not output.name.startswith("issue-141-observation-")
        or resolve.GetProductName() != "DaVinci Resolve Studio"
        or resolve.GetVersion() != reader.BUILD
    ):
        raise RuntimeError("Exact owned Issue 141 R4 action/build required")

    media_root, expected = reader._manifest(config, root, probe)
    source_path = media_root / "relink" / "base.mov"
    source = str(source_path)
    if (
        source not in expected
        or probe.source_evidence(source, expected).get("sha256") != expected[source]
    ):
        raise RuntimeError("Exact isolated source bytes are not verified")

    pinned_dir = output / REMOVAL_DIR
    result = reader._pin(
        pinned_dir / REMOVAL_RESULT, REMOVAL_RESULT, REMOVAL_RESULT_SHA, probe
    )
    pre = reader._pin(pinned_dir / REMOVAL_PRE, REMOVAL_PRE, REMOVAL_PRE_SHA, probe)
    post = reader._pin(pinned_dir / REMOVAL_POST, REMOVAL_POST, REMOVAL_POST_SHA, probe)
    journal_path = pinned_dir / REMOVAL_JOURNAL
    if journal_path.is_symlink() or probe.sha256(journal_path) != REMOVAL_JOURNAL_SHA:
        raise RuntimeError("Pinned native removal journal is missing or changed")
    if (
        result.get("status") != "removed-source-retained"
        or result.get("deleteReturn") is not True
        or result.get("deleteError") is not None
        or result.get("occurrenceAbsent") is not True
        or result.get("removedOccurrenceUid") != reader.ITEM_UID
        or result.get("sourcePoolUid") != reader.MEDIA_UID
        or result.get("sourcePoolPresentAndOnline") is not True
    ):
        raise RuntimeError("Pinned native removal was not verified")
    old_state, old_pool = reader._validate_read_pair(post, probe)
    reader._validate_read_pair(pre, probe)
    if (
        post.get("selectedTimelineUid") != reader.R4_UID
        or pre.get("selectedTimelineUid") != reader.R4_UID
        or result.get("after") != str(pinned_dir / REMOVAL_POST)
        or not any(
            row.get("method") == "Timeline.DeleteClips"
            and row.get("phase") == "request"
            for row in map(json.loads, journal_path.read_text().splitlines())
        )
    ):
        raise RuntimeError("Removal evidence binding or native delete journal invalid")
    timeline = reader._timeline(old_state, reader.R4_UID)
    if (
        _items(old_state, reader)
        or timeline.get("GetStartFrame") != {"value": 0}
        or timeline.get("GetEndFrame") != {"value": 0}
        or old_state.get("projectId") != reader.PROJECT_ID
        or old_state.get("projectName") != config.get("projectName")
    ):
        raise RuntimeError("Pinned post-removal R4 is not exactly empty at frame zero")
    reader._pool_matches(old_pool, expected)
    for locator, digest in expected.items():
        if probe.source_evidence(locator, expected).get("sha256") != digest:
            raise RuntimeError("A manifest source changed before the native append")

    identity = {"projectId": reader.PROJECT_ID, "projectName": config["projectName"]}

    def context():
        project = reader._context(resolve, config, identity, probe, reader.R4_UID)
        if (
            resolve.GetCurrentPage() != "deliver"
            or project.GetCurrentRenderFormatAndCodec()
            != {"format": "mov", "codec": "H264"}
            or project.GetRenderJobList() != []
        ):
            raise RuntimeError("Exact R4/Deliver/MOV-H264/idle queue context required")
        return project

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence = output / f"r4-reprepare-{stamp}"
    evidence.mkdir(exist_ok=False)
    journal = evidence / "journal.jsonl"
    journal.touch(exist_ok=False)

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
    before_state, before_pool = reader._validate_read_pair(before, probe)
    if before_state != old_state or before_pool != old_pool:
        raise RuntimeError("Fresh persisted checkpoint changed before append")
    project = context()
    pool = project.GetMediaPool()
    handle = _source_handle(pool.GetRootFolder(), reader.MEDIA_UID)
    context()
    reader._append(
        journal,
        "MediaPool.AppendToTimeline",
        "request",
        {
            "uid": reader.MEDIA_UID,
            "startFrame": 0,
            "endFrame": 199,
            "mediaType": 1,
            "trackIndex": 1,
            "recordFrame": 0,
        },
    )
    returned, failure = None, None
    try:
        returned = pool.AppendToTimeline(
            [
                {
                    "mediaPoolItem": handle,
                    "startFrame": 0,
                    "endFrame": 199,
                    "mediaType": 1,
                    "trackIndex": 1,
                    "recordFrame": 0,
                }
            ]
        )
        reader._append(
            journal, "MediaPool.AppendToTimeline", "return", _return_evidence(returned)
        )
    except Exception as error:
        failure = f"{type(error).__name__}: {error}"
        reader._append(journal, "MediaPool.AppendToTimeline", "failure", failure)

    after = capture("postflight")
    report = {
        "status": "reprepare-review-required",
        "appendReturn": _return_evidence(returned),
        "appendError": failure,
        "oldOccurrenceUid": reader.ITEM_UID,
        "sourcePoolUid": reader.MEDIA_UID,
        "before": str(evidence / "preflight.json"),
        "after": str(evidence / "postflight.json"),
        "journal": str(journal),
        "nativeDeltas": None,
        "limits": [
            "No save, delete, relink, render, rollback, or retry was performed."
        ],
    }
    try:
        after_state, after_pool = reader._validate_read_pair(after, probe)
        old_all = {
            i.get("GetUniqueId", {}).get("value")
            for _, i in _items(before_state, reader)
        }
        new_items = _items(after_state, reader)
        rows = [
            (t, i)
            for t, i in new_items
            if i.get("GetUniqueId", {}).get("value") not in old_all
        ]
        source_rows = [
            (t, i)
            for t, i in rows
            if i.get("GetMediaPoolItem", {}).get("GetUniqueId")
            == {"value": reader.MEDIA_UID}
        ]
        report["nativeDeltas"] = {
            "timelineChangedPaths": _changed_paths(before_state, after_state),
            "poolChangedPaths": _changed_paths(before_pool, after_pool),
        }
        report["newOccurrenceUid"] = (
            source_rows[0][1].get("GetUniqueId", {}).get("value")
            if len(source_rows) == 1
            else None
        )
        after_timeline = reader._timeline(after_state, reader.R4_UID)
        start_bound = after_timeline.get("GetStartFrame", {}).get("value")
        end_bound = after_timeline.get("GetEndFrame", {}).get("value")
        report["timelineBounds"] = {"startFrame": start_bound, "endFrame": end_bound}
        reader._pool_matches(after_pool, expected)
        report["poolSourceVerified"] = True
        report["boundsVerified"] = (
            isinstance(start_bound, int)
            and isinstance(end_bound, int)
            and start_bound == 0
            and end_bound >= 199
        )
        returned_handles = returned if isinstance(returned, (list, tuple)) else []
        returned_uids = []
        for value in returned_handles:
            getter = getattr(value, "GetUniqueId", None)
            if callable(getter):
                with suppress(Exception):
                    returned_uids.append(getter())
        report["sourceAndRangeVerified"] = bool(
            failure is None
            and len(returned_uids) == 1
            and len(source_rows) == 1
            and returned_uids[0]
            == source_rows[0][1].get("GetUniqueId", {}).get("value")
            and report["newOccurrenceUid"] != reader.ITEM_UID
            and (source_rows[0][0].get("type"), source_rows[0][0].get("index"))
            == ("video", 1)
            and source_rows[0][1].get("GetStart") == {"value": 0}
            and source_rows[0][1].get("GetEnd") == {"value": 199}
            and source_rows[0][1].get("GetDuration") == {"value": 199}
            and source_rows[0][1].get("GetSourceStartFrame") == {"value": 0}
            and source_rows[0][1].get("GetSourceEndFrame") == {"value": 199}
            and report["boundsVerified"]
        )
    except Exception as error:
        report["postflightError"] = f"{type(error).__name__}: {error}"
    reader._write(evidence / "result.json", report)
    reader._append(
        journal,
        "R4Reprepare",
        "complete",
        {k: v for k, v in report.items() if k not in {"nativeDeltas"}},
    )
    return report
