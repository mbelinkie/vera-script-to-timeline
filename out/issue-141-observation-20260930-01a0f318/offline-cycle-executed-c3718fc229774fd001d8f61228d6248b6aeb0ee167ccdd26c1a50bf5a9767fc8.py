"""Bounded online/offline picture cycle for the isolated R4 occurrence."""

import importlib.util
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

CAPTURE_NAME = "capture-20261001T034129.233236Z.json"
CAPTURE_SHA = "690bac86a68ca1ba7a168071bf7df3fe01d172e7f258303183163c1bf25e90da"
POOL_NAME = "r4-pool-read-only-20261001T034129.233236Z.json"
POOL_SHA = "4b9fd9ba0f6bc006ceabf6d6658f1e971369de68d6042ad7042b3b25e0ec8437"
R4_UID = "64de8a4c-86bd-4f19-9d20-47b8940f610b"
MEDIA_UID = "81d81dc0-4c37-478b-8079-03debba5e780"
ITEM_UID = "65a7bcd1-f211-4dee-9726-8c7e0b89cc84"
RANGE_REPAIR_SHA = "06eff080c45e5c520a1c8c31787e4d4f1604198a3a98a9e3c8e025917fcf455b"
TRANSITIONS_SHA = "12798b1288d41e70b01226202b5ee723b70219b90a6067405c816ac02e800af6"
CHECKPOINT_CAPTURE_NAME = "capture-20261001T032801.656424Z.json"
CHECKPOINT_CAPTURE_SHA = (
    "6d70868e701b3c011372d3f06ff26236d6c8fffed5d2fea552280d22cbace98b"
)
CHECKPOINT_POOL_NAME = "r4-pool-read-only-20261001T032801.656424Z.json"
CHECKPOINT_POOL_SHA = "635495c35afa3ba128bf7fae8e57a7d0beeaed754ad431b3822b5dbe1e95f5b7"


def _module(filename, name, digest, probe):
    path = Path(__file__).with_name(filename)
    if path.is_symlink() or probe.sha256(path) != digest:
        raise RuntimeError(f"Pinned helper changed: {filename}")
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


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


def _normalize_offline(actual, baseline, allowed_path):
    actual, baseline = deepcopy(actual), deepcopy(baseline)
    media_props = {"File Path", "Online Status", "Clip Directory"}

    def uid_paths(value, path=()):
        found = []
        if isinstance(value, dict):
            if value.get("GetUniqueId") == {"value": MEDIA_UID}:
                found.append(path)
            for key, child in value.items():
                found.extend(uid_paths(child, (*path, key)))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                found.extend(uid_paths(child, (*path, index)))
        return found

    actual_sources, baseline_sources = uid_paths(actual), uid_paths(baseline)
    if len(actual_sources) != 1 or actual_sources != baseline_sources:
        return False
    props_path = (*actual_sources[0], "GetClipProperty", "value")
    bytes_path = (*actual_sources[0], "sourceBytes")

    def walk(a, b, path=()):
        if isinstance(a, dict) and isinstance(b, dict):
            if path == bytes_path:
                a.clear()
                a.update(deepcopy(b))
                return True
            if a.keys() != b.keys():
                return False
            if path == props_path:
                for key in media_props:
                    if key in b and a[key] != b[key]:
                        allowed = {
                            "File Path": {"", allowed_path},
                            "Online Status": {"Offline"},
                            "Clip Directory": {"", str(Path(allowed_path).parent)},
                        }
                        if key not in allowed or a[key] not in allowed[key]:
                            return False
                        a[key] = b[key]
            return all(walk(a[k], b[k], (*path, k)) for k in a)
        if isinstance(a, list) and isinstance(b, list):
            return len(a) == len(b) and all(
                walk(x, y, (*path, i))
                for i, (x, y) in enumerate(zip(a, b, strict=True))
            )
        return a == b

    return walk(actual, baseline)


def _verified_offline(state, pool, path):
    timeline = next(
        row for row in state["timelines"] if row.get("GetUniqueId") == {"value": R4_UID}
    )
    items = [item for track in timeline["tracks"] for item in track["items"]]
    rows = [row for row in pool["items"] if row.get("uid") == MEDIA_UID]
    if len(items) != 1 or len(rows) != 1:
        return False
    sources = (
        items[0]
        .get("GetMediaPoolItem", {})
        .get("GetClipProperty", {})
        .get("value", {}),
        rows[0].get("evidence", {}).get("GetClipProperty", {}).get("value", {}),
    )
    return all(
        value.get("Online Status") == "Offline"
        and value.get("File Name") == "base.mov"
        and value.get("File Path") in {"", path}
        for value in sources
    )


def run(resolve, config, *, probe):
    reader = _module(
        "r4-range-repair.py", "offline_cycle_reader", RANGE_REPAIR_SHA, probe
    )
    transitions = _module(
        "r4-transitions.py", "offline_cycle_transitions", TRANSITIONS_SHA, probe
    )
    root = Path(probe.ROOT).resolve()
    output = Path(config.get("outputDir", ""))
    if (
        config.get("action") != "offline-cycle"
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != root / "out"
        or not output.name.startswith("issue-141-observation-")
        or resolve.GetProductName() != "DaVinci Resolve Studio"
        or resolve.GetVersion() != reader.BUILD
    ):
        raise RuntimeError("Exact owned Issue 141 action/build/output required")
    media, expected = reader._manifest(config, root, probe)
    relink, source = media / "relink", media / "relink/base.mov"
    if (
        relink.is_symlink()
        or not relink.is_dir()
        or {p.name for p in relink.iterdir()} != {"base.mov"}
        or source.is_symlink()
        or not source.is_file()
        or source not in [Path(x) for x in expected]
        or probe.sha256(source) != expected[str(source)]
    ):
        raise RuntimeError("Exact allowlisted same-byte relink source required")

    cap = reader._pin(output / CAPTURE_NAME, CAPTURE_NAME, CAPTURE_SHA, probe)
    pool_pin = reader._pin(output / POOL_NAME, POOL_NAME, POOL_SHA, probe)
    checkpoint_cap = reader._pin(
        output / CHECKPOINT_CAPTURE_NAME,
        CHECKPOINT_CAPTURE_NAME,
        CHECKPOINT_CAPTURE_SHA,
        probe,
    )
    checkpoint_pool = reader._pin(
        output / CHECKPOINT_POOL_NAME,
        CHECKPOINT_POOL_NAME,
        CHECKPOINT_POOL_SHA,
        probe,
    )
    baseline = reader._equal_pair(cap.get("passes"), probe, "Pinned online timeline")
    baseline_pool = reader._equal_pair(pool_pin.get("passes"), probe, "Pinned R4 pool")
    saved_state = reader._equal_pair(
        checkpoint_cap.get("passes"), probe, "Saved 03:28 R4 timeline"
    )
    saved_pool = reader._equal_pair(
        checkpoint_pool.get("passes"), probe, "Saved 03:28 R4 pool"
    )
    if (
        cap.get("consistency") != "equal-adjacent-reads"
        or cap.get("captureFailure") is not None
        or pool_pin.get("status") != "equal-read-only-pool-inventory"
        or pool_pin.get("capture", {}).get("sha256") != CAPTURE_SHA
        or pool_pin.get("capture", {}).get("capturePath", "").split("/")[-1]
        != CAPTURE_NAME
        or checkpoint_cap.get("consistency") != "equal-adjacent-reads"
        or checkpoint_pool.get("status") != "equal-read-only-pool-inventory"
        or checkpoint_pool.get("capture", {}).get("sha256") != CHECKPOINT_CAPTURE_SHA
        or checkpoint_pool.get("capture", {}).get("capturePath", "").split("/")[-1]
        != CHECKPOINT_CAPTURE_NAME
        or baseline != saved_state
        or baseline_pool != saved_pool
        or cap.get("passes", [None])[0].get("projectId") != reader.PROJECT_ID
    ):
        raise RuntimeError("Immutable full online capture/pool pair binding is invalid")
    pin_state = reader._equal_pair(cap.get("passes"), probe, "Online capture")
    if baseline != pin_state:
        raise RuntimeError("Online capture timeline pin is inconsistent")
    reader._pool_matches(baseline_pool, expected)
    timeline = reader._timeline(baseline, R4_UID)
    items = [
        (track, item)
        for track in timeline.get("tracks", [])
        for item in track.get("items", [])
    ]
    if (
        len(items) != 1
        or (items[0][0].get("type"), items[0][0].get("index")) != ("video", 1)
        or items[0][1].get("GetUniqueId") != {"value": ITEM_UID}
        or items[0][1].get("GetMediaPoolItem", {}).get("GetUniqueId")
        != {"value": MEDIA_UID}
        or items[0][1].get("GetStart") != {"value": 0}
        or items[0][1].get("GetEnd") != {"value": 199}
        or items[0][1].get("GetSourceStartFrame") != {"value": 0}
        or items[0][1].get("GetSourceEndFrame") != {"value": 199}
        or timeline.get("GetStartFrame") != {"value": 0}
        or timeline.get("GetEndFrame") != {"value": 199}
    ):
        raise RuntimeError("Pinned R4 occurrence/program range differs")
    identity = {"projectId": reader.PROJECT_ID, "projectName": config["projectName"]}

    def context():
        project = reader._context(resolve, config, identity, probe, R4_UID)
        if (
            resolve.GetCurrentPage() != "edit"
            or project.GetCurrentRenderFormatAndCodec()
            != {"format": "mov", "codec": "H264"}
            or project.GetRenderJobList() != []
        ):
            raise RuntimeError("Exact R4/Edit/MOV-H264/idle queue context required")
        return project

    def snapshot(label, evidence, journal):
        value = reader._read_pair(resolve, config, identity, expected, R4_UID, probe)
        reader._write(evidence / f"{label}.json", value)
        reader._append(journal, "Capture", label, value)
        state, inventory = reader._validate_read_pair(value, probe)
        return value, state, inventory

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence = output / f"offline-cycle-{stamp}"
    evidence.mkdir(exist_ok=False)
    journal = evidence / "journal.jsonl"
    journal.touch(exist_ok=False)
    result = {
        "status": "offline-cycle-review-required",
        "samples": [],
        "journal": str(journal),
        "resultPath": str(evidence / "result.json"),
        "phases": [],
    }
    safe_restore = False

    def verify_baseline(label):
        _, state, inventory = snapshot(label, evidence, journal)
        if state != baseline or inventory != baseline_pool:
            raise RuntimeError(f"Full online checkpoint drifted at {label}")
        reader._pool_matches(inventory, expected)
        context()

    def export_pair(kind, page):
        samples = []
        for frame, tc in ((0, "00:00:00:00"), (50, "00:00:02:00")):
            project = context()
            timeline = project.GetCurrentTimeline()
            if timeline.GetCurrentTimecode() != tc:
                _append(
                    journal,
                    "SetCurrentTimecode",
                    "request",
                    {"timelineUid": R4_UID, "timecode": tc},
                )
                try:
                    set_result = timeline.SetCurrentTimecode(tc)
                    _append(journal, "SetCurrentTimecode", "return", set_result)
                except Exception as error:
                    _append(
                        journal,
                        "SetCurrentTimecode",
                        "failure",
                        f"{type(error).__name__}: {error}",
                    )
                    raise
                if set_result is not True or timeline.GetCurrentTimecode() != tc:
                    raise RuntimeError("Requested still playhead did not read back")
            if resolve.GetCurrentPage() != page or timeline.GetCurrentTimecode() != tc:
                raise RuntimeError("Page/playhead changed before still export")
            dest = evidence / f"{kind}-frame-{frame:03d}.png"
            _append(
                journal,
                "ExportCurrentFrameAsStill",
                "request",
                {"frame": frame, "timecode": tc, "path": str(dest)},
            )
            value = project.ExportCurrentFrameAsStill(str(dest))
            _append(journal, "ExportCurrentFrameAsStill", "return", value)
            if value is not True:
                raise RuntimeError("Still export did not return literal True")
            context()
            if timeline.GetCurrentTimecode() != tc or resolve.GetCurrentPage() != page:
                raise RuntimeError("Page/playhead changed during still export")
            if (
                dest.is_symlink()
                or not dest.is_file()
                or dest.stat().st_size <= 8
                or dest.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n"
            ):
                raise RuntimeError("Still output is not a regular PNG")
            sample = {
                "phase": kind,
                "frame": frame,
                "timecode": tc,
                "path": str(dest),
                "bytes": dest.stat().st_size,
                "sha256": probe.sha256(dest),
            }
            samples.append(sample)
            _append(journal, "StillSample", "readback", sample)
        return samples

    try:
        verify_baseline("online-preflight")
        project = context()
        timeline = project.GetCurrentTimeline()
        initial_tc = timeline.GetCurrentTimecode()
        if not isinstance(initial_tc, str) or not initial_tc:
            raise RuntimeError("Initial playhead is unreadable")
        initial_page = resolve.GetCurrentPage()
        result["initialPlayhead"] = initial_tc
        result["initialPage"] = initial_page
        safe_restore = True
        result["samples"].extend(export_pair("online", "edit"))
        verify_baseline("online-stills-postflight")
        project = context()
        handle = transitions._find_media_handle(project, MEDIA_UID)
        if handle.GetUniqueId() != MEDIA_UID:
            raise RuntimeError("Exact source pool handle changed")
        context()
        safe_restore = False
        _append(journal, "MediaPool.UnlinkClips", "request", {"uids": [MEDIA_UID]})
        unlink_return, unlink_error = None, None
        try:
            unlink_return = project.GetMediaPool().UnlinkClips([handle])
            _append(journal, "MediaPool.UnlinkClips", "return", unlink_return)
        except Exception as error:
            unlink_error = f"{type(error).__name__}: {error}"
            _append(journal, "MediaPool.UnlinkClips", "failure", unlink_error)
        result["unlinkReturn"] = unlink_return
        result["unlinkError"] = unlink_error
        offline_capture, offline_state, offline_pool = snapshot(
            "offline-postflight", evidence, journal
        )
        if (
            not _normalize_offline(offline_state, baseline, str(source))
            or not _normalize_offline(offline_pool, baseline_pool, str(source))
            or not _verified_offline(offline_state, offline_pool, str(source))
        ):
            safe_restore = offline_state == baseline and offline_pool == baseline_pool
            raise RuntimeError("Offline full-state delta exceeded approved leaves")
        result["phases"].append(
            {
                "phase": "offline",
                "capture": str(evidence / "offline-postflight.json"),
                "status": "verified-offline",
            }
        )
        try:
            result["samples"].extend(export_pair("offline", "edit"))
        except Exception as error:
            result["offlineStillFailure"] = f"{type(error).__name__}: {error}"
            offline_capture2, offline_state2, offline_pool2 = snapshot(
                "offline-still-refusal-check", evidence, journal
            )
            if offline_state2 != offline_state or offline_pool2 != offline_pool:
                raise RuntimeError(
                    "Offline still refusal coincided with native state drift"
                ) from error
        _, relink_state, relink_pool = snapshot(
            "offline-relink-preflight", evidence, journal
        )
        if (
            relink_state != offline_state
            or relink_pool != offline_pool
            or not _normalize_offline(relink_state, baseline, str(source))
            or not _normalize_offline(relink_pool, baseline_pool, str(source))
            or not _verified_offline(relink_state, relink_pool, str(source))
        ):
            safe_restore = False
            raise RuntimeError("Fresh offline full-state relink preflight drifted")
        project = context()
        live_handle = transitions._find_media_handle(project, MEDIA_UID)
        context()
        _append(
            journal,
            "MediaPool.RelinkClips",
            "request",
            {"uids": [MEDIA_UID], "folderPath": str(relink)},
        )
        relink_return, relink_error = None, None
        try:
            relink_return = project.GetMediaPool().RelinkClips(
                [live_handle], str(relink)
            )
            _append(journal, "MediaPool.RelinkClips", "return", relink_return)
        except Exception as error:
            relink_error = f"{type(error).__name__}: {error}"
            _append(journal, "MediaPool.RelinkClips", "failure", relink_error)
        result["relinkReturn"] = relink_return
        result["relinkError"] = relink_error
        _, online_state, online_pool = snapshot(
            "relinked-postflight", evidence, journal
        )
        if online_state != baseline or online_pool != baseline_pool:
            raise RuntimeError(
                "Relinked full state differs from pinned online checkpoint"
            )
        safe_restore = True
        result["phases"].append(
            {
                "phase": "relink",
                "capture": str(evidence / "relinked-postflight.json"),
                "status": "verified-online",
            }
        )
    except Exception as error:
        result["failure"] = f"{type(error).__name__}: {error}"
    finally:
        try:
            if "initial_tc" in locals() and safe_restore:
                project = context()
                timeline = project.GetCurrentTimeline()
                if timeline.GetCurrentTimecode() != initial_tc:
                    _append(
                        journal, "SetCurrentTimecode", "request-restore", initial_tc
                    )
                    value = timeline.SetCurrentTimecode(initial_tc)
                    _append(journal, "SetCurrentTimecode", "return-restore", value)
                if timeline.GetCurrentTimecode() != initial_tc:
                    raise RuntimeError("Original playhead failed readback")
                _, final_state, final_pool = snapshot(
                    "final-postflight", evidence, journal
                )
                if final_state != baseline or final_pool != baseline_pool:
                    raise RuntimeError("Final online state differs from original pin")
                result["restoredPlayhead"] = True
        except Exception as error:
            result["restoreFailure"] = f"{type(error).__name__}: {error}"
    if (
        "failure" not in result
        and result.get("unlinkReturn") is True
        and result.get("unlinkError") is None
        and result.get("relinkReturn") is True
        and result.get("relinkError") is None
        and result.get("restoredPlayhead") is True
        and len(result["samples"]) == 4
    ):
        result["status"] = "offline-cycle-candidates-retained"
    _write(evidence / "result.json", result)
    _append(journal, "OfflineCycle", "complete", result)
    return result
