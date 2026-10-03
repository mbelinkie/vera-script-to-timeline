"""Reversibly replace only the generated R4 relink copy with wrong bytes."""

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
BUILD = [21, 1, 0, 14, ""]
R4_UID = "64de8a4c-86bd-4f19-9d20-47b8940f610b"
R4_POOL_UID = "91853c24-9e0c-435c-8550-209a76425270"
MEDIA_UID = "81d81dc0-4c37-478b-8079-03debba5e780"
ORIGINAL_UID = "9202163a-8381-43e6-9157-3a60f35c6f79"
OCCURRENCE_UID = "65a7bcd1-f211-4dee-9726-8c7e0b89cc84"
MEDIA_SHA256 = "c54ed675ded4e6e7665965680c4991e274058862f7ad8a2d95831c9ec07b7942"
MEDIA_SIZE = 792_989
WRONG_SHA256 = "771b4bbbe771b980831e0a7b6d93ef11e1315cd995df22c5c7fbf7c2bf62c88b"
WRONG_SIZE = 790_489
CHECKPOINT_NAME = "capture-20261001T034129.233236Z.json"
CHECKPOINT_SHA256 = "690bac86a68ca1ba7a168071bf7df3fe01d172e7f258303183163c1bf25e90da"
POOL_CHECKPOINT_NAME = "r4-pool-read-only-20261001T034129.233236Z.json"
POOL_CHECKPOINT_SHA256 = (
    "4b9fd9ba0f6bc006ceabf6d6658f1e971369de68d6042ad7042b3b25e0ec8437"
)
OFFLINE_CYCLE_DIR = "offline-cycle-continuation-20261001T041700.891099Z"
OFFLINE_RESULT_NAME = "result.json"
OFFLINE_RESULT_SHA256 = (
    "a1d4bf77152ebd403ed3b296763ca634c150718ee89a645c42ce32a1f150fc45"
)
OFFLINE_JOURNAL_NAME = "journal.jsonl"
OFFLINE_JOURNAL_SHA256 = (
    "f00572d3b5c23dfb3eaa5b6751b16dab62520ebb84850f611489549b05c580ff"
)
PLUGIN_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)
ORIGINAL_TIMELINES = {
    "29ae8331-b86e-4041-a548-960695cc7b24": "VERA 141 Batched Matrix",
    "88f7923d-55a7-471f-b09b-cf10f9fae8ad": "VERA 141 Baseline",
    "aa2b8e36-83bd-4292-9e33-217c00ca192f": "VERA 141 R1 identity",
}


def _json(value):
    return json.loads(json.dumps(value, allow_nan=False))


def _write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _record(journal, method, phase, value):
    with Path(journal).open("a", encoding="utf-8") as stream:
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


def _pin(path, name, digest, probe):
    if not isinstance(digest, str) or not name or name.startswith("PENDING"):
        raise RuntimeError(f"Required accepted evidence pin is pending: {name}")
    target = Path(path) / name
    if target.is_symlink() or not target.is_file() or probe.sha256(target) != digest:
        raise RuntimeError(f"Required evidence pin changed or is missing: {name}")
    return json.loads(target.read_text(encoding="utf-8"))


def _timeline(state, uid):
    rows = [
        row
        for row in state.get("timelines", [])
        if row.get("GetUniqueId", {}).get("value") == uid
    ]
    if len(rows) != 1:
        raise RuntimeError(f"Timeline {uid} is missing or duplicated")
    return rows[0]


def _pool_item(inventory, uid):
    rows = [row for row in inventory.get("items", []) if row.get("uid") == uid]
    if len(rows) != 1:
        raise RuntimeError(f"Pool item {uid} is missing or duplicated")
    return rows[0]


def _occurrence(timeline):
    found = [
        (track, item)
        for track in timeline.get("tracks", [])
        for item in track.get("items", [])
    ]
    if len(found) != 1:
        raise RuntimeError("R4 must retain exactly one timeline occurrence")
    track, item = found[0]
    if (
        (track.get("type"), track.get("index")) != ("video", 1)
        or item.get("GetUniqueId") != {"value": OCCURRENCE_UID}
        or item.get("GetTrackTypeAndIndex") != {"value": ["video", 1]}
        or item.get("GetStart") != {"value": 0}
        or item.get("GetEnd") != {"value": 199}
        or item.get("GetDuration") != {"value": 199}
        or item.get("GetSourceStartFrame") != {"value": 0}
        or item.get("GetSourceEndFrame") != {"value": 199}
        or item.get("GetMediaPoolItem", {}).get("GetUniqueId") != {"value": MEDIA_UID}
    ):
        raise RuntimeError("R4 occurrence identity/source/range differs")
    return item


def _source_map(media, manifest, probe):
    expected, entries = {}, {}
    if manifest.get("kind") != "generated-synthetic-inputs-not-Resolve-evidence":
        raise RuntimeError("Synthetic media manifest kind differs")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise RuntimeError("Complete synthetic manifest is unreadable")
    for entry in files:
        relative = Path(entry.get("path", ""))
        digest = entry.get("sha256")
        size = entry.get("sizeBytes")
        if (
            not relative.parts
            or relative.is_absolute()
            or ".." in relative.parts
            or not isinstance(digest, str)
            or isinstance(size, bool)
            or not isinstance(size, int)
            or str(relative) in entries
        ):
            raise RuntimeError("Manifest path/hash/size is unsafe or duplicated")
        path = media / relative
        if (
            path.is_symlink()
            or not path.is_file()
            or not path.resolve(strict=True).is_relative_to(media.resolve())
            or path.stat().st_size != size
            or probe.sha256(path) != digest
        ):
            raise RuntimeError(f"Manifest candidate differs: {relative}")
        entries[str(relative)] = {"path": path, "sha256": digest, "size": size}
        expected[str(path)] = digest
    if (
        entries.get("relink/base.mov", {}).get("sha256") != MEDIA_SHA256
        or entries.get("relink/base.mov", {}).get("size") != MEDIA_SIZE
        or entries.get("wrong/base.mov", {}).get("sha256") != WRONG_SHA256
        or entries.get("wrong/base.mov", {}).get("size") != WRONG_SIZE
        or entries.get("base.mov", {}).get("sha256") != MEDIA_SHA256
        or entries.get("base.mov", {}).get("size") != MEDIA_SIZE
    ):
        raise RuntimeError(
            "Approved, wrong-byte, or shared-source manifest pin differs"
        )
    return expected, entries


def _guard_paths(config, root, probe):
    output = Path(config.get("outputDir", ""))
    media = Path(config.get("mediaDir", ""))
    out_root = root / "out"
    if (
        not output.is_absolute()
        or output.is_symlink()
        or output.parent.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != out_root.resolve()
        or not output.name.startswith("issue-141-observation-")
        or out_root.is_symlink()
        or not media.is_absolute()
        or media.is_symlink()
        or media.parent.is_symlink()
        or not media.is_dir()
        or media.parent.resolve() != out_root.resolve()
        or not media.name.startswith("issue-141-media-")
    ):
        raise RuntimeError(
            "Only existing slice-owned observation/media paths are allowed"
        )
    manifest_path = media / "manifest.json"
    if (
        manifest_path.is_symlink()
        or not manifest_path.is_file()
        or probe.sha256(manifest_path) != config.get("manifestSha256")
    ):
        raise RuntimeError("Synthetic manifest pin differs")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected, entries = _source_map(media, manifest, probe)
    relink_folder = media / "relink"
    locator = entries["relink/base.mov"]["path"]
    wrong = entries["wrong/base.mov"]["path"]
    shared = entries["base.mov"]["path"]
    if (
        relink_folder.is_symlink()
        or not relink_folder.is_dir()
        or {entry.name for entry in relink_folder.iterdir()} != {"base.mov"}
        or wrong.parent.is_symlink()
        or not wrong.parent.is_dir()
        or {entry.name for entry in wrong.parent.iterdir()} != {"base.mov"}
        or shared.is_symlink()
    ):
        raise RuntimeError("Approved or wrong-byte directory contents differ")
    return (
        output,
        media,
        manifest,
        expected,
        entries,
        relink_folder,
        locator,
        wrong,
        shared,
    )


def _pool_inventory(project, probe, expected, *, wrong_bytes=False):
    """Use the shared complete inventory, preserving only this target mismatch."""
    inventory_expected = dict(expected)
    if wrong_bytes:
        target_path = next(
            path for path in expected if Path(path).parts[-2:] == ("relink", "base.mov")
        )
        inventory_expected[target_path] = WRONG_SHA256
    inventory = probe._r4_pool_inventory(project, inventory_expected)
    if wrong_bytes:
        target = _pool_item(inventory, MEDIA_UID)["evidence"]["sourceBytes"]
        target["expectedSha256"] = MEDIA_SHA256
        target["hashMatches"] = False
    return inventory


def _observe_state(resolve, config, identity, expected, probe, *, wrong_bytes=False):
    observed_expected = dict(expected)
    target_path = None
    if wrong_bytes:
        target_path = next(
            path for path in expected if Path(path).parts[-2:] == ("relink", "base.mov")
        )
        observed_expected[target_path] = WRONG_SHA256
    state = _json(probe.observe(resolve, config, identity, observed_expected))
    if wrong_bytes:
        item = _occurrence(_timeline(state, R4_UID))["GetMediaPoolItem"]
        bytes_evidence = item.get("sourceBytes", {})
        if (
            bytes_evidence.get("sha256") != WRONG_SHA256
            or item.get("GetClipProperty", {}).get("value", {}).get("File Path")
            != target_path
        ):
            raise RuntimeError("Wrong-byte timeline source binding differs")
        bytes_evidence.update(expectedSha256=MEDIA_SHA256, hashMatches=False)
    return state


def _validate_state(state, inventory, locator, *, wrong_bytes=False):
    timeline_ids = {
        row.get("GetUniqueId", {}).get("value"): row
        for row in state.get("timelines", [])
    }
    if set(timeline_ids) != set(ORIGINAL_TIMELINES) | {R4_UID}:
        raise RuntimeError("Timeline identity set differs from the accepted R4 setup")
    for uid, name in ORIGINAL_TIMELINES.items():
        if timeline_ids[uid].get("GetName") != {"value": name}:
            raise RuntimeError("An original timeline identity/name changed")
    timeline = _timeline(state, R4_UID)
    if timeline.get("GetName") != {"value": "VERA 141 R4 availability"}:
        raise RuntimeError("Selected R4 timeline identity differs")
    if timeline.get("GetStartFrame") != {"value": 0} or timeline.get("GetEndFrame") != {
        "value": 199
    }:
        raise RuntimeError("R4 timeline bounds differ from the pinned 199-end case")
    occurrence = _occurrence(timeline)
    media = occurrence["GetMediaPoolItem"]
    pool_item = _pool_item(inventory, MEDIA_UID)
    for evidence in (media, pool_item["evidence"]):
        props = evidence.get("GetClipProperty", {}).get("value", {})
        if (
            evidence.get("GetUniqueId") != {"value": MEDIA_UID}
            or props.get("File Name") != "base.mov"
            or props.get("Online Status") != "Online"
            or props.get("File Path") != str(locator)
        ):
            raise RuntimeError("Distinct imported item locator/status/UID differs")
        byte_evidence = evidence.get("sourceBytes", {})
        if wrong_bytes:
            if (
                byte_evidence.get("sha256") != WRONG_SHA256
                or byte_evidence.get("status") != "reachable"
                or byte_evidence.get("hashMatches") is not False
                or byte_evidence.get("expectedSha256") != MEDIA_SHA256
            ):
                raise RuntimeError("Wrong-byte mismatch was not retained exactly")
        elif (
            byte_evidence.get("sha256") != MEDIA_SHA256
            or byte_evidence.get("hashMatches") is not True
        ):
            raise RuntimeError("Restored imported item source hash differs")
    if pool_item.get("name", {}).get("value") != "base.mov":
        raise RuntimeError("Imported pool item name differs")
    mappings = [
        row
        for row in inventory.get("timelineMappings", [])
        if row.get("timelineUid") == {"value": R4_UID}
    ]
    if len(mappings) != 1 or mappings[0].get("poolItemUid") != {"value": R4_POOL_UID}:
        raise RuntimeError("R4 timeline pool-proxy UID differs")
    original = _pool_item(inventory, ORIGINAL_UID)
    if original.get("uid") != ORIGINAL_UID:
        raise RuntimeError("Original shared source UID disappeared")
    return timeline, occurrence, pool_item


def _original_projection(state, inventory):
    timelines = {uid: _timeline(state, uid) for uid in ORIGINAL_TIMELINES}
    original = _pool_item(inventory, ORIGINAL_UID)
    return {"timelines": timelines, "originalSharedItem": original}


def _matches_wrong_only(state, inventory, baseline_state, baseline_inventory):
    actual_state, expected_state = _json(state), _json(baseline_state)
    actual_pool, expected_pool = _json(inventory), _json(baseline_inventory)
    actual_occurrence = _occurrence(_timeline(actual_state, R4_UID))
    expected_occurrence = _occurrence(_timeline(expected_state, R4_UID))
    actual_occurrence["GetMediaPoolItem"]["sourceBytes"] = _json(
        expected_occurrence["GetMediaPoolItem"]["sourceBytes"]
    )
    _pool_item(actual_pool, MEDIA_UID)["evidence"]["sourceBytes"] = _json(
        _pool_item(expected_pool, MEDIA_UID)["evidence"]["sourceBytes"]
    )
    return actual_state == expected_state and actual_pool == expected_pool


def _sample(
    resolve,
    config,
    identity,
    expected,
    output,
    stamp,
    probe,
    *,
    wrong_bytes,
    baseline_timecode,
    frame=0,
):
    def guard(expected_timecode=None, expected_page=None):
        project = probe.require_current(resolve, config, identity)
        timeline = project.GetCurrentTimeline()
        if (
            timeline is None
            or timeline.GetUniqueId() != R4_UID
            or resolve.GetCurrentPage() != "edit"
            or (expected_page is not None and resolve.GetCurrentPage() != expected_page)
            or project.GetRenderJobList() != []
            or (
                expected_timecode is not None
                and timeline.GetCurrentTimecode() != expected_timecode
            )
        ):
            raise RuntimeError("R4 must remain selected before still sample")
        state = _observe_state(
            resolve, config, identity, expected, probe, wrong_bytes=wrong_bytes
        )
        inventory = _pool_inventory(project, probe, expected, wrong_bytes=wrong_bytes)
        _validate_state(
            state,
            inventory,
            Path(config["mediaDir"]) / "relink/base.mov",
            wrong_bytes=wrong_bytes,
        )
        return project, timeline

    project, timeline = guard(baseline_timecode, "edit")

    def native(method, target, call):
        _record(
            output / f"r4-wrong-bytes-{stamp}.jsonl",
            method,
            "request",
            target,
        )
        try:
            value = call()
            if value is None or value is False:
                raise RuntimeError(f"{method} returned no successful result")
            _record(
                output / f"r4-wrong-bytes-{stamp}.jsonl",
                method,
                "return",
                value,
            )
            return value
        except Exception as caught:
            _record(
                output / f"r4-wrong-bytes-{stamp}.jsonl",
                method,
                "failure",
                f"{type(caught).__name__}: {caught}",
            )
            raise

    timecode = native(
        "GetCurrentTimecode", {"timelineUid": R4_UID}, timeline.GetCurrentTimecode
    )
    page = native("GetCurrentPage", {}, resolve.GetCurrentPage)
    if not isinstance(timecode, str) or not isinstance(page, str) or not page:
        raise RuntimeError("Initial still timecode/page is unreadable")
    if timecode != baseline_timecode or page != "edit":
        raise RuntimeError("Still sample preflight differs from the pinned context")
    target = f"00:00:00:{frame:02d}"
    record = {"initialTimecode": timecode, "initialPage": page, "frame": frame}
    error = None
    destination = output / f"r4-wrong-bytes-{stamp}-frame-{frame:03d}.png"
    try:
        project, timeline = guard(timecode, page)
        if (
            resolve.GetCurrentPage() != page
            or timeline.GetCurrentTimecode() != timecode
        ):
            raise RuntimeError("R4 context/page changed before still sample")
        project, timeline = guard(timecode, page)
        native(
            "SetCurrentTimecode",
            {"timelineUid": R4_UID, "timecode": target},
            lambda: timeline.SetCurrentTimecode(target),
        )
        actual_timecode, actual_page = (
            native(
                "GetCurrentTimecode",
                {"timelineUid": R4_UID},
                timeline.GetCurrentTimecode,
            ),
            native("GetCurrentPage", {}, resolve.GetCurrentPage),
        )
        if actual_timecode != target or actual_page != page:
            raise RuntimeError("Requested still playhead/page readback differs")
        record.update({"requestedTimecode": target, "readbackPage": actual_page})
        project, timeline = guard(target, page)
        if timeline.GetCurrentTimecode() != target or resolve.GetCurrentPage() != page:
            raise RuntimeError("Playhead/page changed before still export")
        native(
            "ExportCurrentFrameAsStill",
            {"destination": str(destination), "timelineUid": R4_UID},
            lambda: project.ExportCurrentFrameAsStill(str(destination)),
        )
        project, timeline = guard(target, page)
        if (
            native(
                "GetCurrentTimecode",
                {"timelineUid": R4_UID},
                timeline.GetCurrentTimecode,
            )
            != target
            or native("GetCurrentPage", {}, resolve.GetCurrentPage) != page
        ):
            raise RuntimeError("Still export changed selected timeline/playhead/page")
        if destination.is_symlink() or not destination.is_file():
            raise RuntimeError("Still export did not create a regular file")
        with destination.open("rb") as stream:
            header = stream.read(8)
        record.update(
            {
                "path": str(destination),
                "bytes": destination.stat().st_size,
                "sha256": probe.sha256(destination),
                "pngHeaderHex": header.hex(),
                "pngHeaderMatches": header == b"\x89PNG\r\n\x1a\n",
            }
        )
        if record["bytes"] <= 8 or not record["pngHeaderMatches"]:
            raise RuntimeError("Still output is empty or not PNG")
    except Exception as caught:
        error = f"{type(caught).__name__}: {caught}"
        record["failure"] = error
    try:
        project, timeline = guard(expected_page=page)
        current_timecode = timeline.GetCurrentTimecode()
        if current_timecode not in {timecode, target}:
            raise RuntimeError("Playhead drifted to an unknown value; preserve it")
        if current_timecode != timecode:
            native(
                "SetCurrentTimecode",
                {"timelineUid": R4_UID, "timecode": timecode},
                lambda: timeline.SetCurrentTimecode(timecode),
            )
        project, timeline = guard(timecode, page)
        record["restoredTimecode"] = native(
            "GetCurrentTimecode", {"timelineUid": R4_UID}, timeline.GetCurrentTimecode
        )
        record["restoredPage"] = native("GetCurrentPage", {}, resolve.GetCurrentPage)
        record["restored"] = (
            record["restoredTimecode"] == timecode and record["restoredPage"] == page
        )
        if not record["restored"]:
            raise RuntimeError("Initial still playhead/page was not restored")
    except Exception as caught:
        record["restoreFailure"] = f"{type(caught).__name__}: {caught}"
        record["restored"] = False
    _record(
        output / f"r4-wrong-bytes-{stamp}.jsonl",
        "ExportCurrentFrameAsStill",
        "readback",
        record,
    )
    if error or not record["restored"]:
        raise RuntimeError(
            "Still sample or playhead restoration failed: "
            + str(error or record.get("restoreFailure"))
        )
    return record


def _find_media_handle(project, uid):
    found = []

    def visit(folder, seen):
        folder_uid = folder.GetUniqueId()
        if folder_uid in seen:
            raise RuntimeError("Media-pool folder cycle or repeated UID")
        seen.add(folder_uid)
        items, children = folder.GetClipList(), folder.GetSubFolderList()
        if not isinstance(items, (list, tuple)) or not isinstance(
            children, (list, tuple)
        ):
            raise RuntimeError("Media-pool folder contents are unreadable")
        for item in items:
            if item is not None and item.GetUniqueId() == uid:
                found.append(item)
        for child in children:
            visit(child, seen)

    visit(project.GetMediaPool().GetRootFolder(), set())
    if len(found) != 1:
        raise RuntimeError(f"Exact imported media UID {uid} is missing or duplicated")
    return found[0]


def _refresh(
    resolve,
    config,
    identity,
    expected,
    output,
    stamp,
    probe,
    locator,
    wrong_bytes,
    context,
):
    """Relink only the imported UID to its existing folder and retain readbacks."""
    project = context()
    before_state = _observe_state(
        resolve, config, identity, expected, probe, wrong_bytes=wrong_bytes
    )
    before_pool = _pool_inventory(project, probe, expected, wrong_bytes=wrong_bytes)
    _validate_state(before_state, before_pool, locator, wrong_bytes=wrong_bytes)
    handle = _find_media_handle(project, MEDIA_UID)
    if handle.GetUniqueId() != MEDIA_UID:
        raise RuntimeError("Relink handle UID differs from the isolated source")
    journal = output / f"r4-wrong-bytes-{stamp}.jsonl"
    _record(
        journal,
        "RelinkClips",
        "request",
        {
            "uids": [MEDIA_UID],
            "folderPath": str(locator.parent),
            "wrongBytes": wrong_bytes,
        },
    )
    result = project.GetMediaPool().RelinkClips([handle], str(locator.parent))
    _record(journal, "RelinkClips", "return", result)
    if result is not True:
        raise RuntimeError("Exact-source RelinkClips refresh did not return true")
    project = context()
    after_state = _observe_state(
        resolve, config, identity, expected, probe, wrong_bytes=wrong_bytes
    )
    after_pool = _pool_inventory(project, probe, expected, wrong_bytes=wrong_bytes)
    _validate_state(after_state, after_pool, locator, wrong_bytes=wrong_bytes)
    if before_state != after_state or before_pool != after_pool:
        raise RuntimeError("Relink refresh changed guarded source/timeline evidence")
    return {
        "result": result,
        "before": {"timeline": before_state, "pool": before_pool},
        "after": {"timeline": after_state, "pool": after_pool},
    }


def _atomic_replace_from(
    source, destination, expected_source, expected_destination, probe
):
    if (
        source.parent.is_symlink()
        or destination.parent.is_symlink()
        or source.is_symlink()
        or not source.is_file()
        or probe.sha256(source) != expected_source
    ):
        raise RuntimeError("Replacement source changed before copy")
    if (
        destination.is_symlink()
        or not destination.is_file()
        or probe.sha256(destination) != expected_destination
    ):
        raise RuntimeError("Replacement destination changed before atomic replace")
    fd, temp_name = tempfile.mkstemp(prefix=".r4-wrong-bytes-", dir=destination.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        shutil.copyfile(source, temp)
        if (
            temp.is_symlink()
            or probe.sha256(temp) != expected_source
            or temp.stat().st_size != source.stat().st_size
        ):
            raise RuntimeError("Atomic replacement staging copy differs")
        if probe.sha256(destination) != expected_destination:
            raise RuntimeError(
                "Replacement destination changed immediately before replace"
            )
        os.replace(temp, destination)
        if destination.is_symlink() or probe.sha256(destination) != expected_source:
            raise RuntimeError("Atomic replacement readback hash differs")
    finally:
        if temp.exists() and not temp.is_symlink():
            temp.unlink()


def run(resolve, config, *, probe):
    """Run only the reversible locator-byte mismatch and restoration phase."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    output = Path(config.get("outputDir", ""))
    journal = output / f"r4-wrong-bytes-{stamp}.jsonl"
    if (
        config.get("action") != "r4-wrong-bytes"
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or not output.name.startswith("issue-141-observation-")
    ):
        raise RuntimeError("Only a slice-owned R4 observation may run this action")
    journal.touch(exist_ok=False)
    _record(
        journal,
        "R4WrongBytes",
        "start",
        {
            "checkpoint": {"name": CHECKPOINT_NAME, "sha256": CHECKPOINT_SHA256},
            "poolCheckpoint": {
                "name": POOL_CHECKPOINT_NAME,
                "sha256": POOL_CHECKPOINT_SHA256,
            },
            "offlineCycleResult": {
                "directory": OFFLINE_CYCLE_DIR,
                "name": OFFLINE_RESULT_NAME,
                "sha256": OFFLINE_RESULT_SHA256,
            },
            "offlineCycleJournal": {
                "name": OFFLINE_JOURNAL_NAME,
                "sha256": OFFLINE_JOURNAL_SHA256,
            },
            "version": resolve.GetVersion(),
        },
    )
    original_projection = None
    recovery_copy = None
    replaced = False
    mismatch = None
    restored = False
    error = None
    evidence_path = output / f"r4-wrong-bytes-{stamp}.json"
    try:
        if (
            resolve.GetProductName() != "DaVinci Resolve Studio"
            or resolve.GetVersion() != BUILD
        ):
            raise RuntimeError("Exact Resolve Studio 21.1.0 build 14 required")
        if (
            not isinstance(CHECKPOINT_SHA256, str)
            or CHECKPOINT_NAME.startswith("PENDING")
            or not isinstance(POOL_CHECKPOINT_SHA256, str)
            or POOL_CHECKPOINT_NAME.startswith("PENDING")
            or not isinstance(OFFLINE_RESULT_SHA256, str)
            or OFFLINE_CYCLE_DIR.startswith("PENDING")
            or not isinstance(OFFLINE_JOURNAL_SHA256, str)
        ):
            raise RuntimeError(
                "Accepted offline-cycle and fresh checkpoint pins are pending"
            )
        checkpoint = _pin(output, CHECKPOINT_NAME, CHECKPOINT_SHA256, probe)
        pool_checkpoint = _pin(
            output, POOL_CHECKPOINT_NAME, POOL_CHECKPOINT_SHA256, probe
        )
        offline_dir = output / OFFLINE_CYCLE_DIR
        if offline_dir.is_symlink() or not offline_dir.is_dir():
            raise RuntimeError("Pinned offline-cycle evidence directory is missing")
        transition_result = _pin(
            offline_dir, OFFLINE_RESULT_NAME, OFFLINE_RESULT_SHA256, probe
        )
        transition_journal = offline_dir / OFFLINE_JOURNAL_NAME
        if (
            transition_journal.is_symlink()
            or not transition_journal.is_file()
            or probe.sha256(transition_journal) != OFFLINE_JOURNAL_SHA256
        ):
            raise RuntimeError("Accepted transition journal pin differs")
        transition_rows = [
            json.loads(line)
            for line in transition_journal.read_text(encoding="utf-8").splitlines()
        ]
        prior_dir = Path(transition_result.get("priorCheckpoint", ""))
        if (
            prior_dir.parent != output
            or prior_dir.is_symlink()
            or not prior_dir.is_dir()
            or not prior_dir.name.startswith("offline-cycle-")
        ):
            raise RuntimeError("Offline prior checkpoint is outside the owned output")
        prior_result = _pin(
            prior_dir, "result.json", transition_result.get("priorResultSha256"), probe
        )
        prior_journal = prior_dir / "journal.jsonl"
        if prior_journal.is_symlink() or probe.sha256(
            prior_journal
        ) != transition_result.get("priorJournalSha256"):
            raise RuntimeError("Prior offline journal differs")
        prior_rows = [
            json.loads(line) for line in prior_journal.read_text().splitlines()
        ]
        unlinks = [
            row for row in prior_rows if row.get("method") == "MediaPool.UnlinkClips"
        ]
        relinks = [
            row
            for row in transition_rows
            if row.get("method") == "MediaPool.RelinkClips"
        ]
        if (
            transition_result.get("status") != "offline-cycle-candidates-retained"
            or transition_result.get("fullOriginalStateRestored") is not True
            or transition_result.get("restoredPlayhead") != "00:00:07:24"
            or transition_result.get("relinkReturn") is not True
            or transition_result.get("relinkError") is not None
            or transition_result.get("failure") is not None
            or prior_result.get("unlinkReturn") is not True
            or prior_result.get("unlinkError") is not None
            or [row.get("phase") for row in unlinks] != ["request", "return"]
            or unlinks[1].get("value") is not True
            or any(row.get("method") == "MediaPool.RelinkClips" for row in prior_rows)
            or any(
                row.get("method") == "MediaPool.UnlinkClips" for row in transition_rows
            )
            or [row.get("phase") for row in relinks] != ["request", "return"]
            or relinks[1].get("value") is not True
        ):
            raise RuntimeError(
                "Accepted offline continuation and restoration are absent"
            )
        for phase, directory in (("online", prior_dir), ("offline", offline_dir)):
            samples = transition_result.get(f"{phase}Samples", [])
            if len(samples) != 2 or {row.get("frame") for row in samples} != {0, 50}:
                raise RuntimeError("Offline-cycle sample set is incomplete")
            for sample in samples:
                path = directory / f"{phase}-frame-{sample['frame']:03d}.png"
                if (
                    sample.get("phase") != phase
                    or Path(sample.get("path", "")) != path
                    or path.is_symlink()
                    or not path.is_file()
                    or path.stat().st_size != sample.get("bytes")
                    or probe.sha256(path) != sample.get("sha256")
                    or path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n"
                ):
                    raise RuntimeError("Offline-cycle sample bytes or path differ")
        restored_pair = json.loads(
            (offline_dir / "restored-postflight.json").read_text()
        )
        if (
            restored_pair.get("timelineConsistency") != "equal-adjacent-reads"
            or restored_pair.get("poolConsistency") != "equal-adjacent-reads"
            or restored_pair.get("timelinePasses") != checkpoint.get("passes")
            or restored_pair.get("poolPasses") != pool_checkpoint.get("passes")
        ):
            raise RuntimeError("Offline final full checkpoint differs")
        (
            output,
            media,
            manifest,
            expected,
            entries,
            relink_folder,
            locator,
            wrong,
            shared,
        ) = _guard_paths(config, Path(probe.ROOT).resolve(), probe)
        checkpoint_passes = checkpoint.get("passes", [])
        checkpoint_pools = pool_checkpoint.get("passes", [])
        if (
            checkpoint.get("consistency") != "equal-adjacent-reads"
            or checkpoint.get("captureFailure") is not None
            or len(checkpoint_passes) != 2
            or checkpoint_passes[0] != checkpoint_passes[1]
            or probe.errors(checkpoint_passes)
            or checkpoint_passes[0].get("projectId") != PROJECT_ID
            or checkpoint_passes[0].get("projectName") != config.get("projectName")
            or checkpoint.get("environment", {}).get("version") != BUILD
            or pool_checkpoint.get("status") != "equal-read-only-pool-inventory"
            or len(checkpoint_pools) != 2
            or checkpoint_pools[0] != checkpoint_pools[1]
            or probe.errors(checkpoint_pools)
            or Path(pool_checkpoint.get("capture", {}).get("capturePath", "")).name
            != CHECKPOINT_NAME
            or pool_checkpoint.get("capture", {}).get("sha256") != CHECKPOINT_SHA256
        ):
            raise RuntimeError("Fresh R4 two-pass checkpoint is incomplete or differs")
        pinned_state = checkpoint_passes[0]
        project_name = config.get("projectName")
        identity = {"projectId": PROJECT_ID, "projectName": project_name}
        config_live = dict(config, stage="R4-wrong-bytes-replacement")

        initial_page = resolve.GetCurrentPage()
        initial_project = probe.require_current(resolve, config_live, identity)
        initial_timeline = initial_project.GetCurrentTimeline()
        initial_timecode = (
            initial_timeline.GetCurrentTimecode()
            if initial_timeline is not None
            else None
        )
        if (
            initial_page != "edit"
            or not isinstance(initial_timecode, str)
            or initial_project.GetRenderJobList() != []
        ):
            raise RuntimeError("R4 page, playhead, or idle render-queue guard differs")

        def context():
            if (
                resolve.GetProductName() != "DaVinci Resolve Studio"
                or resolve.GetVersion() != BUILD
            ):
                raise RuntimeError("Resolve product/build changed")
            project = probe.require_current(resolve, config_live, identity)
            timeline = project.GetCurrentTimeline()
            if (
                timeline is None
                or timeline.GetUniqueId() != R4_UID
                or resolve.GetCurrentPage() != initial_page
                or project.GetRenderJobList() != []
                or timeline.GetCurrentTimecode() != initial_timecode
            ):
                raise RuntimeError("Exact isolated R4 timeline must remain selected")
            return project

        def read_pair(*, mismatch_expected=False):
            state_pairs, pools = [], []
            for _ in range(2):
                project = context()
                state_pairs.append(
                    _observe_state(
                        resolve,
                        config_live,
                        identity,
                        expected,
                        probe,
                        wrong_bytes=mismatch_expected,
                    )
                )
                project = context()
                pools.append(
                    _pool_inventory(
                        project, probe, expected, wrong_bytes=mismatch_expected
                    )
                )
                context()
            return state_pairs, pools

        before_states, before_pools = read_pair()
        baseline_pool_pair = before_pools
        if before_states != [pinned_state, pinned_state]:
            raise RuntimeError("Fresh selected-R4 state differs from checkpoint")
        if baseline_pool_pair != checkpoint_pools:
            raise RuntimeError("Fresh complete pool inventories differ from checkpoint")
        baseline_pool = baseline_pool_pair[0]
        _, occurrence, pool_target = _validate_state(
            pinned_state, baseline_pool, locator
        )
        if (
            len(
                [
                    row
                    for row in baseline_pool.get("items", [])
                    if row.get("uid") == MEDIA_UID
                ]
            )
            != 1
        ):
            raise RuntimeError("Distinct imported media UID is missing or duplicated")
        original_projection = _original_projection(pinned_state, baseline_pool)
        original_props = (
            _pool_item(baseline_pool, ORIGINAL_UID)
            .get("evidence", {})
            .get("GetClipProperty", {})
            .get("value", {})
        )
        if (
            original_props.get("File Path") != str(shared)
            or probe.sha256(shared) != MEDIA_SHA256
        ):
            raise RuntimeError("Shared original item path/hash differs")
        if (
            occurrence.get("GetMediaPoolItem", {})
            .get("GetClipProperty", {})
            .get("value", {})
            .get("File Path")
            != str(locator)
            or pool_target.get("uid") != MEDIA_UID
        ):
            raise RuntimeError(
                "R4 occurrence does not identify the approved generated locator"
            )

        recovery_dir = output / f"r4-wrong-bytes-recovery-{stamp}"
        recovery_dir.mkdir(mode=0o700, exist_ok=False)
        recovery_copy = recovery_dir / "original-base.mov"
        with locator.open("rb") as source, recovery_copy.open("xb") as destination:
            shutil.copyfileobj(source, destination)
            destination.flush()
            os.fsync(destination.fileno())
        if (
            recovery_copy.is_symlink()
            or recovery_copy.stat().st_size != MEDIA_SIZE
            or probe.sha256(recovery_copy) != MEDIA_SHA256
        ):
            raise RuntimeError("Owned recovery copy does not match original bytes")
        _record(
            journal,
            "recovery-copy",
            "readback",
            {
                "path": str(recovery_copy),
                "sha256": probe.sha256(recovery_copy),
                "bytes": recovery_copy.stat().st_size,
            },
        )

        context()
        if (
            probe.sha256(locator) != MEDIA_SHA256
            or probe.sha256(wrong) != WRONG_SHA256
            or probe.sha256(shared) != MEDIA_SHA256
        ):
            raise RuntimeError("Source bytes changed immediately before replacement")
        _record(
            journal,
            "atomic-replace-wrong-bytes",
            "request",
            {
                "destination": str(locator),
                "expectedBeforeSha256": MEDIA_SHA256,
                "source": str(wrong),
                "sourceSha256": WRONG_SHA256,
                "sourceBytes": WRONG_SIZE,
            },
        )
        replaced = True
        _atomic_replace_from(wrong, locator, WRONG_SHA256, MEDIA_SHA256, probe)
        _record(
            journal,
            "atomic-replace-wrong-bytes",
            "return",
            {
                "destinationSha256": probe.sha256(locator),
                "destinationBytes": locator.stat().st_size,
            },
        )
        wrong_states, wrong_pools = read_pair(mismatch_expected=True)
        for state, pool in zip(wrong_states, wrong_pools, strict=True):
            _validate_state(state, pool, locator, wrong_bytes=True)
            if not _matches_wrong_only(state, pool, pinned_state, baseline_pool):
                raise RuntimeError(
                    "Wrong-byte phase changed unrelated state or inventory"
                )
        if _original_projection(wrong_states[0], wrong_pools[0]) != original_projection:
            raise RuntimeError("Original shared item or original timeline changed")
        mismatch = {
            "timelinePasses": wrong_states,
            "poolPasses": wrong_pools,
            "expectedSha256": MEDIA_SHA256,
            "actualSha256": probe.sha256(locator),
            "actualBytes": locator.stat().st_size,
        }
        _write(output / f"r4-wrong-bytes-{stamp}-mismatch.json", mismatch)
        wrong_refresh = _refresh(
            resolve,
            config_live,
            identity,
            expected,
            output,
            stamp,
            probe,
            locator,
            True,
            context,
        )
        sample = _sample(
            resolve,
            config_live,
            identity,
            expected,
            output,
            stamp,
            probe,
            wrong_bytes=True,
            baseline_timecode=initial_timecode,
            frame=0,
        )

        # Restore only while the selected target and wrong-byte path remain pinned.
        context()
        if (
            probe.sha256(locator) != WRONG_SHA256
            or locator.stat().st_size != WRONG_SIZE
            or probe.sha256(recovery_copy) != MEDIA_SHA256
            or probe.sha256(shared) != MEDIA_SHA256
            or probe.sha256(wrong) != WRONG_SHA256
        ):
            raise RuntimeError("Restoration guards changed; preserve wrong-byte state")
        now_states, now_pools = read_pair(mismatch_expected=True)
        if now_states != wrong_states or now_pools != wrong_pools:
            raise RuntimeError("Full wrong-byte readback changed before restoration")
        _record(
            journal,
            "atomic-restore-original-bytes",
            "request",
            {
                "destination": str(locator),
                "expectedBeforeSha256": WRONG_SHA256,
                "recoveryCopy": str(recovery_copy),
                "recoverySha256": MEDIA_SHA256,
                "recoveryBytes": MEDIA_SIZE,
            },
        )
        _atomic_replace_from(recovery_copy, locator, MEDIA_SHA256, WRONG_SHA256, probe)
        replaced = False
        _record(
            journal,
            "atomic-restore-original-bytes",
            "return",
            {
                "destinationSha256": probe.sha256(locator),
                "destinationBytes": locator.stat().st_size,
            },
        )
        restored_refresh = _refresh(
            resolve,
            config_live,
            identity,
            expected,
            output,
            stamp,
            probe,
            locator,
            False,
            context,
        )
        restored_states, restored_pools = read_pair()
        if restored_states != [pinned_state, pinned_state]:
            raise RuntimeError("Restored selected-R4 captures differ from checkpoint")
        for state, pool in zip(restored_states, restored_pools, strict=True):
            _validate_state(state, pool, locator)
        if (
            _original_projection(restored_states[0], restored_pools[0])
            != original_projection
        ):
            raise RuntimeError(
                "Restoration changed the shared source or original timelines"
            )
        if restored_pools != [baseline_pool, baseline_pool]:
            raise RuntimeError("Restored full pool inventory differs from checkpoint")
        if (
            probe.sha256(locator) != MEDIA_SHA256
            or probe.sha256(shared) != MEDIA_SHA256
            or probe.sha256(wrong) != WRONG_SHA256
        ):
            raise RuntimeError("Final source/shared/wrong-byte hashes differ")
        restored = True
        _write(
            output / f"r4-wrong-bytes-{stamp}-restored.json",
            {
                "timelinePasses": restored_states,
                "poolPasses": restored_pools,
                "refresh": restored_refresh,
            },
        )
        restored_sample = _sample(
            resolve,
            config_live,
            identity,
            expected,
            output,
            stamp + "-restored",
            probe,
            wrong_bytes=False,
            baseline_timecode=initial_timecode,
            frame=0,
        )
        restored = True
    except Exception as caught:
        error = f"{type(caught).__name__}: {caught}"
        _record(journal, "R4WrongBytes", "failure", error)
        if replaced and recovery_copy is not None:
            try:
                if (
                    resolve.GetProductName() != "DaVinci Resolve Studio"
                    or resolve.GetVersion() != BUILD
                ):
                    raise RuntimeError("Resolve product/build changed before recovery")
                recovery_identity = {
                    "projectId": PROJECT_ID,
                    "projectName": config.get("projectName"),
                }
                project = probe.require_current(resolve, config, recovery_identity)
                selected = project.GetCurrentTimeline()
                context_ok = (
                    selected is not None
                    and selected.GetUniqueId() == R4_UID
                    and resolve.GetCurrentPage() == initial_page
                    and project.GetRenderJobList() == []
                    and selected.GetCurrentTimecode() == initial_timecode
                    and locator.is_file()
                    and not locator.is_symlink()
                    and probe.sha256(locator) == WRONG_SHA256
                    and recovery_copy.is_file()
                    and not recovery_copy.is_symlink()
                    and probe.sha256(recovery_copy) == MEDIA_SHA256
                    and probe.sha256(shared) == MEDIA_SHA256
                )
                if context_ok:
                    recovery_states, recovery_pools = read_pair(mismatch_expected=True)
                    _write(
                        output / f"r4-wrong-bytes-{stamp}-recovery-before.json",
                        {
                            "timelinePasses": recovery_states,
                            "poolPasses": recovery_pools,
                        },
                    )
                    for current_state, current_pool in zip(
                        recovery_states, recovery_pools, strict=True
                    ):
                        _validate_state(
                            current_state,
                            current_pool,
                            locator,
                            wrong_bytes=True,
                        )
                    context_ok = (
                        recovery_states[0] == recovery_states[1]
                        and recovery_pools[0] == recovery_pools[1]
                        and _matches_wrong_only(
                            recovery_states[0],
                            recovery_pools[0],
                            pinned_state,
                            baseline_pool,
                        )
                        and _original_projection(recovery_states[0], recovery_pools[0])
                        == original_projection
                    )
                if context_ok:
                    _record(
                        journal,
                        "atomic-restore-original-bytes",
                        "recovery-request",
                        {
                            "destination": str(locator),
                            "recoveryCopy": str(recovery_copy),
                            "recoverySha256": MEDIA_SHA256,
                        },
                    )
                    _atomic_replace_from(
                        recovery_copy, locator, MEDIA_SHA256, WRONG_SHA256, probe
                    )
                    replaced = False
                    _record(
                        journal,
                        "atomic-restore-original-bytes",
                        "recovery-return",
                        {"destinationSha256": probe.sha256(locator)},
                    )
                    restored = True
                    post_states, post_pools = read_pair()
                    if post_states != [pinned_state, pinned_state] or (
                        post_pools != [baseline_pool, baseline_pool]
                    ):
                        raise RuntimeError(
                            "Recovery replace completed but full postflight differs"
                        )
                    _write(
                        output / f"r4-wrong-bytes-{stamp}-recovery-after.json",
                        {"timelinePasses": post_states, "poolPasses": post_pools},
                    )
                else:
                    _record(
                        journal,
                        "atomic-restore-original-bytes",
                        "recovery-refusal",
                        {
                            "reason": (
                                "project/selection/locator/recovery/shared-source "
                                "guard failed"
                            )
                        },
                    )
            except Exception as recovery_error:
                _record(
                    journal,
                    "atomic-restore-original-bytes",
                    "recovery-failure",
                    f"{type(recovery_error).__name__}: {recovery_error}",
                )
    result = {
        "kind": "same-locator-wrong-bytes-observation-not-asset-identity-proof",
        "status": "restored-original-bytes"
        if error is None and restored
        else "partial-state-retained",
        "expectedSha256": MEDIA_SHA256,
        "wrongSha256": WRONG_SHA256,
        "wrongMismatch": mismatch,
        "restored": restored,
        "stillSample": locals().get("sample"),
        "restoredStillSample": locals().get("restored_sample"),
        "wrongBytesRefresh": locals().get("wrong_refresh"),
        "restoredBytesRefresh": locals().get("restored_refresh"),
        "recoveryCopy": None if recovery_copy is None else str(recovery_copy),
        "failure": error,
        "limits": [
            "The locator hash establishes only byte mismatch, not displayed media.",
            "A RelinkClips return and matching getters do not prove displayed "
            "substitution.",
            "No save, close, reopen, or output substitution claim is included.",
        ],
    }
    _write(evidence_path, result)
    _record(
        journal,
        "R4WrongBytes",
        "complete" if error is None and restored else "retained-partial",
        {"status": result["status"], "evidence": str(evidence_path)},
    )
    if error is not None or not restored:
        raise RuntimeError(
            f"R4 wrong-bytes action retained partial evidence: {evidence_path}: {error}"
        )
    return {
        "status": result["status"],
        "journal": str(journal),
        "evidence": str(evidence_path),
    }
