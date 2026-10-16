"""Prepare the exact linked R1-razor case for a separately approved menu test."""

import importlib.util
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
BUILD = [21, 1, 0, 14, ""]
R4_UID = "64de8a4c-86bd-4f19-9d20-47b8940f610b"
MATRIX_UID = "29ae8331-b86e-4041-a548-960695cc7b24"
R4_CAPTURE = "capture-20261001T034129.233236Z.json"
R4_CAPTURE_SHA = "690bac86a68ca1ba7a168071bf7df3fe01d172e7f258303183163c1bf25e90da"
R4_POOL = "r4-pool-read-only-20261001T034129.233236Z.json"
R4_POOL_SHA = "4b9fd9ba0f6bc006ceabf6d6658f1e971369de68d6042ad7042b3b25e0ec8437"
RESTORED_PAIR = "r4-wrong-bytes-20261001T042632.944184Z-restored.json"
RESTORED_PAIR_SHA = "cb12248c97637f21c355e069cd416f508e052d409d90a9136ece13e4507cbce6"
MATRIX_CAPTURE = "capture-20260930T223313.312609Z-saved.json"
MATRIX_CAPTURE_SHA = "a29402d405ab8cf1bc1abedd4c1ed0c479e983e2ef3ba6fc41d1c2389d6d36d2"
READER_SHA = "06eff080c45e5c520a1c8c31787e4d4f1604198a3a98a9e3c8e025917fcf455b"
MATRIX_NAME = "VERA 141 Batched Matrix"
BASELINE_UID = "88f7923d-55a7-471f-b09b-cf10f9fae8ad"
R1_UID = "aa2b8e36-83bd-4292-9e33-217c00ca192f"
R1_CASE = ("R1-razor", 1500, 1699, 0, 199)
TARGET_LOCKS = (("video", 2), ("video", 3), ("audio", 2), ("audio", 3))
FRAME_RATE = 25
PLAYHEAD_FRAME = 1600


def _load_reader(probe):
    path = Path(__file__).with_name("r4-range-repair.py")
    if path.is_symlink() or probe.sha256(path) != READER_SHA:
        raise RuntimeError("Pinned full-state reader changed")
    spec = importlib.util.spec_from_file_location("r1_razor_reader", path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    return reader


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


def _item_rows(timeline, track_type, index):
    tracks = [
        track
        for track in timeline.get("tracks", [])
        if track.get("type") == track_type and track.get("index") == index
    ]
    if len(tracks) != 1:
        raise RuntimeError(f"Exact {track_type} track {index} is missing or duplicated")
    return tracks[0]["items"]


def _razor_pair(timeline):
    found = []
    for kind, index, filename in (
        ("video", 1, "base.mov"),
        ("audio", 1, "repeated.wav"),
    ):
        candidates = []
        for item in _item_rows(timeline, kind, index):
            props = (
                item.get("GetMediaPoolItem", {})
                .get("GetClipProperty", {})
                .get("value", {})
            )
            markers = item.get("GetMarkers", {}).get("value", {})
            tags = []
            for marker in markers.values():
                try:
                    data = json.loads(marker.get("customData", ""))
                except (json.JSONDecodeError, TypeError):
                    continue
                if data.get("issue") == 141 and data.get("section") == R1_CASE[0]:
                    tags.append(data)
            if (
                props.get("File Name") == filename
                and item.get("GetStart", {}).get("value") == R1_CASE[1]
                and item.get("GetEnd", {}).get("value") == R1_CASE[2]
                and item.get("GetSourceStartFrame", {}).get("value") == R1_CASE[3]
                and item.get("GetSourceEndFrame", {}).get("value") == R1_CASE[4]
                and any(isinstance(tag.get("occurrence"), int) for tag in tags)
            ):
                candidates.append(item)
        if len(candidates) != 1:
            raise RuntimeError(
                f"Exact R1-razor {kind} occurrence is missing or duplicated"
            )
        item = candidates[0]
        found.append((kind, item))
    video_id = found[0][1]["GetUniqueId"]["value"]
    audio_id = found[1][1]["GetUniqueId"]["value"]
    if audio_id not in [
        row.get("value") for row in found[0][1].get("GetLinkedItems", [])
    ] or video_id not in [
        row.get("value") for row in found[1][1].get("GetLinkedItems", [])
    ]:
        raise RuntimeError("R1-razor linked-item relationship is not reciprocal")
    return {kind: item for kind, item in found}


def _uid_map(state):
    return {
        row["GetUniqueId"]["value"]: row["GetName"]["value"]
        for row in state.get("timelines", [])
    }


def _get_timeline(project, uid, name):
    matches = []
    for index in range(1, project.GetTimelineCount() + 1):
        timeline = project.GetTimelineByIndex(index)
        if timeline is not None and timeline.GetUniqueId() == uid:
            matches.append(timeline)
    if len(matches) != 1 or matches[0].GetName() != name:
        raise RuntimeError("Exact Matrix timeline handle is missing or duplicated")
    return matches[0]


def _require_context(resolve, config, identity, probe, reader, selected_uid):
    project = reader._context(resolve, config, identity, probe, selected_uid)
    if (
        resolve.GetCurrentPage() != "edit"
        or project.GetCurrentRenderFormatAndCodec()
        != {"format": "mov", "codec": "H264"}
        or project.GetRenderJobList() != []
    ):
        raise RuntimeError("Pinned Edit/known format/idle queue context required")
    return project


def run(resolve, config, *, probe):
    reader = _load_reader(probe)
    root = Path(probe.ROOT).resolve()
    output = Path(config.get("outputDir", ""))
    if (
        config.get("action") != "r1-razor-prepare"
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != root / "out"
        or not output.name.startswith("issue-141-observation-")
        or resolve.GetProductName() != "DaVinci Resolve Studio"
        or resolve.GetVersion() != BUILD
    ):
        raise RuntimeError("Exact synthetic R1-razor preparation/build required")
    media, source_hashes = reader._manifest(config, root, probe)
    if media.parent.resolve() != output.parent.resolve():
        raise RuntimeError("Synthetic source/output roots differ")

    capture = reader._pin(output / R4_CAPTURE, R4_CAPTURE, R4_CAPTURE_SHA, probe)
    pool = reader._pin(output / R4_POOL, R4_POOL, R4_POOL_SHA, probe)
    restored = reader._pin(
        output / RESTORED_PAIR, RESTORED_PAIR, RESTORED_PAIR_SHA, probe
    )
    matrix_path = output / MATRIX_CAPTURE
    matrix_capture = reader._pin(
        matrix_path, matrix_path.name, MATRIX_CAPTURE_SHA, probe
    )
    if (
        capture.get("consistency") != "equal-adjacent-reads"
        or pool.get("status") != "equal-read-only-pool-inventory"
        or pool.get("capture", {}).get("sha256") != R4_CAPTURE_SHA
    ):
        raise RuntimeError("Pinned selected-R4 timeline/pool pair is incomplete")
    r4_state = reader._equal_pair(capture["passes"], probe, "Selected-R4 timeline")
    r4_pool = reader._equal_pair(pool["passes"], probe, "Selected-R4 pool")
    restored_state = reader._equal_pair(
        restored.get("timelinePasses"), probe, "04:32 restored timeline"
    )
    restored_pool = reader._equal_pair(
        restored.get("poolPasses"), probe, "04:32 restored pool"
    )
    if (
        restored.get("refresh", {}).get("result") is not True
        or restored.get("refresh", {}).get("after", {}).get("timeline")
        != restored_state
        or restored.get("refresh", {}).get("after", {}).get("pool") != restored_pool
    ):
        raise RuntimeError("04:32 restored checkpoint refresh does not verify")
    matrix_state = reader._equal_pair(
        matrix_capture.get("passes"), probe, "Saved Matrix"
    )
    matrix_timeline = reader._timeline(matrix_state, MATRIX_UID)
    expected_r4_ids = {
        MATRIX_UID: MATRIX_NAME,
        R4_UID: "VERA 141 R4 availability",
        BASELINE_UID: "VERA 141 Baseline",
        R1_UID: "VERA 141 R1 identity",
    }
    expected_matrix_ids = {
        MATRIX_UID: MATRIX_NAME,
        BASELINE_UID: "VERA 141 Baseline",
        R1_UID: "VERA 141 R1 identity",
    }
    if (
        r4_state.get("projectId") != PROJECT_ID
        or r4_state.get("projectName") != config.get("projectName")
        or restored_state != r4_state
        or restored_pool != r4_pool
        or matrix_state.get("projectId") != PROJECT_ID
        or matrix_state.get("projectName") != config.get("projectName")
        or matrix_capture.get("environment", {}).get("version") != BUILD
        or _uid_map(r4_state) != expected_r4_ids
        or _uid_map(matrix_state) != expected_matrix_ids
    ):
        raise RuntimeError(
            "Current/restored/selected-Matrix pins do not bind one project"
        )
    reader._pool_matches(r4_pool, source_hashes)
    pinned_pair = _razor_pair(matrix_timeline)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    directory = output / f"r1-razor-{stamp}"
    directory.mkdir()
    journal = directory / "journal.jsonl"
    journal.touch()
    identity = {"projectId": PROJECT_ID, "projectName": config["projectName"]}
    result = {
        "status": "partial-state-review-required",
        "directory": str(directory),
        "journal": str(journal),
        "pins": {
            "currentR4Capture": {"name": R4_CAPTURE, "sha256": R4_CAPTURE_SHA},
            "currentR4Pool": {"name": R4_POOL, "sha256": R4_POOL_SHA},
            "restoredPair": {"name": RESTORED_PAIR, "sha256": RESTORED_PAIR_SHA},
            "selectedMatrix": {"name": MATRIX_CAPTURE, "sha256": MATRIX_CAPTURE_SHA},
        },
        "setters": [],
        "failure": None,
    }

    project = None

    def native(method, target, call):
        _require_context(
            resolve,
            config,
            identity,
            probe,
            reader,
            R4_UID if method == "SetCurrentTimeline" else MATRIX_UID,
        )
        result["setters"].append(method)
        _append(journal, method, "request", target)
        try:
            returned = call()
        except Exception as error:
            _append(
                journal,
                method,
                "return",
                {"error": f"{type(error).__name__}: {error}"},
            )
            raise
        _append(journal, method, "return", returned)
        if returned is not True:
            raise RuntimeError(f"{method} did not return true")
        return returned

    try:
        project = _require_context(resolve, config, identity, probe, reader, R4_UID)
        before_r4 = reader._read_pair(
            resolve, config, identity, source_hashes, R4_UID, probe
        )
        before_state, before_pool = reader._validate_read_pair(before_r4, probe)
        if before_state != r4_state or before_pool != r4_pool:
            raise RuntimeError(
                "Fresh selected-R4 state differs from both retained pins"
            )
        _write(directory / "r4-preflight.json", before_r4)
        _append(journal, "R4Preflight", "readback", {"path": "r4-preflight.json"})

        matrix_handle = _get_timeline(project, MATRIX_UID, MATRIX_NAME)
        native(
            "SetCurrentTimeline",
            MATRIX_UID,
            lambda: project.SetCurrentTimeline(matrix_handle),
        )
        project = _require_context(resolve, config, identity, probe, reader, MATRIX_UID)
        matrix_handle = _get_timeline(project, MATRIX_UID, MATRIX_NAME)
        before_matrix = reader._read_pair(
            resolve, config, identity, source_hashes, MATRIX_UID, probe
        )
        matrix_before, before_pool = reader._validate_read_pair(before_matrix, probe)
        current_matrix = reader._timeline(matrix_before, MATRIX_UID)
        selected_expected = deepcopy(before_state)
        matrix_index = next(
            index
            for index, row in enumerate(selected_expected["timelines"])
            if row["GetUniqueId"]["value"] == MATRIX_UID
        )
        selected_expected["timelines"][matrix_index] = deepcopy(matrix_timeline)
        # Selected-context evidence reports inactive tracks as False. This is
        # a getter-context comparison, never a change to actual track enables.
        for track in reader._timeline(selected_expected, R4_UID)["tracks"]:
            track["GetIsTrackEnabled"] = {"value": False}
        if (
            matrix_before != selected_expected
            or before_pool != r4_pool
            or _uid_map(matrix_before) != expected_r4_ids
        ):
            raise RuntimeError(
                "Selected Matrix content differs from the saved Matrix pin"
            )
        pair = _razor_pair(current_matrix)
        if {kind: item["GetUniqueId"]["value"] for kind, item in pair.items()} != {
            kind: item["GetUniqueId"]["value"] for kind, item in pinned_pair.items()
        }:
            raise RuntimeError(
                "Live R1-razor target identities differ from saved Matrix"
            )
        _write(directory / "matrix-preflight.json", before_matrix)

        original_locks = {}
        for kind, index in (
            ("video", 1),
            ("video", 2),
            ("video", 3),
            ("audio", 1),
            ("audio", 2),
            ("audio", 3),
        ):
            value = matrix_handle.GetIsTrackLocked(kind, index)
            if not isinstance(value, bool) or value is not False:
                raise RuntimeError("Selected-Matrix original track-lock state differs")
            original_locks[f"{kind}:{index}"] = value
        original_playhead = matrix_handle.GetCurrentTimecode()
        if not isinstance(original_playhead, str) or not original_playhead:
            raise RuntimeError("Original Matrix playhead is unreadable")
        result.update(
            {
                "targetUids": {
                    "video": pair["video"]["GetUniqueId"]["value"],
                    "audio": pair["audio"]["GetUniqueId"]["value"],
                },
                "originalLocks": original_locks,
                "originalPlayhead": original_playhead,
                "split": {
                    "case": R1_CASE[0],
                    "localFrame": 100,
                    "absoluteFrame": PLAYHEAD_FRAME,
                    "timecode": "00:01:04:00",
                    "frameRate": FRAME_RATE,
                },
            }
        )
        expected = deepcopy(matrix_before)
        expected_matrix = reader._timeline(expected, MATRIX_UID)
        for kind, index in TARGET_LOCKS:
            native(
                "SetTrackLock",
                {"trackType": kind, "trackIndex": index, "locked": True},
                lambda kind=kind, index=index: matrix_handle.SetTrackLock(
                    kind, index, True
                ),
            )
            if matrix_handle.GetIsTrackLocked(kind, index) is not True:
                raise RuntimeError(
                    f"Selected Matrix {kind}{index} lock did not read back"
                )
            track = next(
                row
                for row in expected_matrix["tracks"]
                if row["type"] == kind and row["index"] == index
            )
            track["GetIsTrackLocked"]["value"] = True
        native(
            "SetCurrentTimecode",
            "00:01:04:00",
            lambda: matrix_handle.SetCurrentTimecode("00:01:04:00"),
        )
        if matrix_handle.GetCurrentTimecode() != "00:01:04:00":
            raise RuntimeError("R1-razor playhead did not read back at frame1600")
        after = reader._read_pair(
            resolve, config, identity, source_hashes, MATRIX_UID, probe
        )
        after_state, after_pool = reader._validate_read_pair(after, probe)
        if (
            after_state != expected
            or after_pool != r4_pool
            or _razor_pair(reader._timeline(after_state, MATRIX_UID))
            != _razor_pair(reader._timeline(matrix_before, MATRIX_UID))
        ):
            raise RuntimeError(
                "Preparation changed content or an unapproved state field"
            )
        _write(directory / "prepared.json", after)
        _append(journal, "PreparedReadback", "complete", {"path": "prepared.json"})
        result["status"] = "prepared-for-editorial-selection"
        result["preparedPair"] = "prepared.json"
        result["preparedPairSha256"] = probe.sha256(directory / "prepared.json")
        result["noEditorialCommandDispatched"] = True
    except Exception as error:
        result["failure"] = f"{type(error).__name__}: {error}"
        try:
            selected = None if project is None else project.GetCurrentTimeline()
            selected_uid = selected.GetUniqueId() if selected else None
            if selected_uid in {R4_UID, MATRIX_UID}:
                partial = reader._read_pair(
                    resolve, config, identity, source_hashes, selected_uid, probe
                )
                _write(directory / "partial-readback.json", partial)
                result["partialReadback"] = "partial-readback.json"
        except Exception as evidence_error:
            result["partialReadbackFailure"] = (
                f"{type(evidence_error).__name__}: {evidence_error}"
            )
    _write(directory / "result.json", result)
    return result
