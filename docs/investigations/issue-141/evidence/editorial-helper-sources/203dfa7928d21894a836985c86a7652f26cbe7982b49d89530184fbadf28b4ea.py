"""Prepare, position, or restore the fixed Issue 141 editorial cases."""

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
R4_UID = "64de8a4c-86bd-4f19-9d20-47b8940f610b"
R4_NAME = "VERA 141 R4 availability"
READER_SHA = "06eff080c45e5c520a1c8c31787e4d4f1604198a3a98a9e3c8e025917fcf455b"
FRAME_RATE = 25
LOCKS = (("video", 2), ("video", 3), ("audio", 2), ("audio", 3))
ALL_LOCKS = (("video", 1), *LOCKS[:2], ("audio", 1), *LOCKS[2:])
CASES = {
    "R1-trim": {"start": 500, "end": 699, "sourceStart": 0, "sourceEnd": 199},
    "R1-move": {"start": 1000, "end": 1199, "sourceStart": 0, "sourceEnd": 199},
    "R1-copy": {
        "start": 2000,
        "end": 2199,
        "sourceStart": 0,
        "sourceEnd": 199,
        "pasteStart": 2250,
        "pasteEnd": 2449,
    },
    "R2-linked": {"start": 2500, "end": 2699, "sourceStart": 0, "sourceEnd": 199},
}


def _reader(probe):
    path = Path(__file__).with_name("r4-range-repair.py")
    if path.is_symlink() or probe.sha256(path) != READER_SHA:
        raise RuntimeError("Pinned full-state reader changed")
    spec = importlib.util.spec_from_file_location("editorial_cases_reader", path)
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


def _pin(reader, output, relative, digest, probe):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise RuntimeError("A relative approved-output evidence pin is required")
    path, cursor = output / relative, output
    for part in Path(relative).parts:
        if part in {".", ".."}:
            raise RuntimeError("Evidence pin may not traverse output")
        cursor /= part
        if cursor.is_symlink() or not cursor.resolve().is_relative_to(output.resolve()):
            raise RuntimeError("Evidence pin escapes or links outside output")
    return reader._pin(path, path.name, digest, probe)


def _timeline_map(state):
    return {
        row.get("GetUniqueId", {}).get("value"): row.get("GetName", {}).get("value")
        for row in state.get("timelines", [])
    }


def _timeline(state, reader):
    row = reader._timeline(state, MATRIX_UID)
    expected = {
        MATRIX_UID: MATRIX_NAME,
        R4_UID: R4_NAME,
        BASELINE_UID: "VERA 141 Baseline",
        R1_UID: "VERA 141 R1 identity",
    }
    if _timeline_map(state) != expected:
        raise RuntimeError("Exact four-timeline project inventory changed")
    return row


def _track(timeline, kind, index):
    rows = [
        row
        for row in timeline.get("tracks", [])
        if row.get("type") == kind and row.get("index") == index
    ]
    if len(rows) != 1:
        raise RuntimeError(f"Exact {kind}{index} track is missing or duplicated")
    return rows[0]


def _target_pair(state, reader, case):
    spec = CASES[case]
    timeline, found = _timeline(state, reader), {}
    for kind, index, filename in (
        ("video", 1, "base.mov"),
        ("audio", 1, "repeated.wav"),
    ):
        candidates = []
        for item in _track(timeline, kind, index).get("items", []):
            markers = item.get("GetMarkers", {}).get("value", {})
            tagged = False
            for marker in markers.values():
                try:
                    data = json.loads(marker.get("customData", ""))
                except (json.JSONDecodeError, TypeError):
                    continue
                if data.get("issue") == 141 and data.get("section") == case:
                    tagged = True
            props = (
                item.get("GetMediaPoolItem", {})
                .get("GetClipProperty", {})
                .get("value", {})
            )
            if (
                tagged
                and item.get("GetStart") == {"value": spec["start"]}
                and props.get("File Name") == filename
            ):
                candidates.append(item)
        if len(candidates) != 1:
            raise RuntimeError(
                f"Exact {case} {kind} occurrence is missing or duplicated"
            )
        found[kind] = candidates[0]
    video, audio = found["video"], found["audio"]
    start, end = (
        video.get("GetStart", {}).get("value"),
        video.get("GetEnd", {}).get("value"),
    )
    source_ranges = {
        (
            item.get("GetSourceStartFrame", {}).get("value"),
            item.get("GetSourceEndFrame", {}).get("value"),
        )
        for item in found.values()
    }
    if (
        not isinstance(start, int)
        or not isinstance(end, int)
        or end - 25 < start
        or (start, end) != (spec["start"], spec["end"])
        or source_ranges != {(spec["sourceStart"], spec["sourceEnd"])}
        or audio.get("GetStart") != {"value": start}
        or audio.get("GetEnd") != {"value": end}
        or audio.get("GetUniqueId", {}).get("value")
        not in [row.get("value") for row in video.get("GetLinkedItems", [])]
        or video.get("GetUniqueId", {}).get("value")
        not in [row.get("value") for row in audio.get("GetLinkedItems", [])]
    ):
        raise RuntimeError(f"{case} linked pair or current bounds are inconsistent")
    return found, start, end


def _timecode(frame):
    h, frame = divmod(frame, FRAME_RATE * 3600)
    m, frame = divmod(frame, FRAME_RATE * 60)
    s, f = divmod(frame, FRAME_RATE)
    return f"{h:02}:{m:02}:{s:02}:{f:02}"


def _context(resolve, config, identity, probe, reader):
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
    return timeline


def _base(resolve, config, probe, reader, case):
    root, output = Path(probe.ROOT).resolve(), Path(config.get("outputDir", ""))
    if (
        case not in CASES
        or config.get("case") != case
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != root / "out"
        or not output.name.startswith("issue-141-observation-")
        or resolve.GetProductName() != "DaVinci Resolve Studio"
        or resolve.GetVersion() != BUILD
    ):
        raise RuntimeError("Exact approved editorial synthetic context required")
    media, sources = reader._manifest(config, root, probe)
    if media.parent.resolve() != output.parent.resolve():
        raise RuntimeError("Synthetic source/output roots differ")
    identity = {"projectId": PROJECT_ID, "projectName": config["projectName"]}
    return output, sources, identity


def _read(reader, resolve, config, identity, sources, probe):
    pair = reader._read_pair(resolve, config, identity, sources, MATRIX_UID, probe)
    state, pool = reader._validate_read_pair(pair, probe)
    if (
        state.get("projectId") != PROJECT_ID
        or state.get("projectName") != config["projectName"]
    ):
        raise RuntimeError("Full readback project identity changed")
    _timeline(state, reader)
    return pair, state, pool


def _prepared_state(reader, output, preparation, probe):
    prepared_ref = preparation.get("preparedPair", {})
    initial = _pin(
        reader,
        output,
        preparation.get("priorPair", {}).get("path"),
        preparation.get("priorPair", {}).get("sha256"),
        probe,
    )
    prepared = _pin(
        reader,
        output,
        prepared_ref.get("path"),
        prepared_ref.get("sha256"),
        probe,
    )
    initial_state, initial_pool = reader._validate_read_pair(initial, probe)
    prepared_state, prepared_pool = reader._validate_read_pair(prepared, probe)
    expected = deepcopy(initial_state)
    for kind, index in LOCKS:
        _track(_timeline(expected, reader), kind, index)["GetIsTrackLocked"] = {
            "value": True
        }
    if (
        prepared_state != expected
        or prepared_pool != initial_pool
        or preparation.get("originalPlayhead") is None
    ):
        raise RuntimeError(
            "Editorial prepared evidence does not verify against its prior pin"
        )
    return initial_state, initial_pool, prepared_state, prepared_pool


def _evidence_dir(output):
    directory = output / datetime.now(UTC).strftime("editorial-case-%Y%m%dT%H%M%S.%fZ")
    directory.mkdir(exist_ok=False)
    journal = directory / "journal.jsonl"
    journal.touch()
    return directory, journal


def _apply(
    resolve,
    config,
    probe,
    reader,
    output,
    sources,
    identity,
    case,
    before,
    before_pool,
    expected_state,
    operations,
    expected_playhead,
    result_fields,
    success_status,
    evidence_key,
):
    directory, journal = _evidence_dir(output)
    reader._write(directory / "before.json", before)
    _append(journal, "FullReadback", "before", {"path": "before.json"})
    result = {
        "status": "refused-partial-state-retained",
        "case": case,
        "directory": str(directory),
        "journal": str(journal),
        **result_fields,
        "setters": [],
        "failure": None,
        "environment": {
            "productName": resolve.GetProductName(),
            "version": resolve.GetVersion(),
            "python": platform.python_version(),
        },
        "saveDispatched": False,
    }

    try:
        for method, target, call, readback in operations:
            _context(resolve, config, identity, probe, reader)
            result["setters"].append(method)
            _append(journal, method, "request", target)
            try:
                returned = call()
            except Exception as error:
                _append(journal, method, "failure", f"{type(error).__name__}: {error}")
                raise
            _append(journal, method, "return", returned)
            if returned is not True:
                raise RuntimeError(f"{method} did not return true")
            _context(resolve, config, identity, probe, reader)
            if readback() != target.get("locked", target.get("timecode")):
                raise RuntimeError(f"{method} did not read back")
    except Exception as error:
        result["failure"] = f"{type(error).__name__}: {error}"

    try:
        after, after_state, after_pool = _read(
            reader, resolve, config, identity, sources, probe
        )
        reader._write(directory / "after.json", after)
        result[evidence_key] = {
            "path": str(directory.relative_to(output) / "after.json"),
            "sha256": probe.sha256(directory / "after.json"),
        }
        playhead = _context(
            resolve, config, identity, probe, reader
        ).GetCurrentTimecode()
        result["playheadAfter"] = playhead
        if (
            result["failure"] is None
            and after_state == expected_state
            and after_pool == before_pool
            and playhead == expected_playhead
        ):
            result["status"] = success_status
        elif result["failure"] is None:
            result["failure"] = (
                "Full postflight differs from the bounded case operation"
            )
    except Exception as error:
        result["postflightFailure"] = f"{type(error).__name__}: {error}"
    reader._write(directory / "result.json", result)
    return result


def prepare(resolve, config, *, probe, reader=None):
    reader = reader or _reader(probe)
    case = config.get("case")
    output, sources, identity = _base(resolve, config, probe, reader, case)
    pin = _pin(
        reader, output, config.get("priorPair"), config.get("priorPairSha256"), probe
    )
    before_state, before_pool = reader._validate_read_pair(pin, probe)
    if (
        pin.get("selectedTimelineUid") != MATRIX_UID
        or before_state.get("projectId") != PROJECT_ID
        or before_state.get("projectName") != config["projectName"]
    ):
        raise RuntimeError(
            "Pinned readback does not bind the exact selected Matrix project"
        )
    matrix = _timeline(before_state, reader)
    items, start, end = _target_pair(before_state, reader, case)
    if (
        float(
            matrix.get("GetSettings", {}).get("value", {}).get("timelineFrameRate", 0)
        )
        != FRAME_RATE
    ):
        raise RuntimeError("Editorial case requires the 25 fps Matrix timeline")
    original_locks = {}
    for kind, index in ALL_LOCKS:
        locked = _track(matrix, kind, index).get("GetIsTrackLocked", {}).get("value")
        if not isinstance(locked, bool):
            raise RuntimeError("Pinned track-lock state is unreadable")
        original_locks[f"{kind}:{index}"] = locked
    if any(original_locks.values()):
        raise RuntimeError("Editorial preparation requires the unlocked Matrix")
    original_playhead = _context(
        resolve, config, identity, probe, reader
    ).GetCurrentTimecode()
    if not isinstance(original_playhead, str) or not original_playhead:
        raise RuntimeError("Original Matrix playhead is unreadable")
    current, state, pool = _read(reader, resolve, config, identity, sources, probe)
    if state != before_state or pool != before_pool:
        raise RuntimeError(
            "Fresh complete state/source evidence differs from prior pin"
        )

    if case == "R1-trim":
        frame, playhead_label = end - 25, "trimPlayhead"
    elif case == "R2-linked":
        frame, playhead_label = start + 60, "splitPlayhead"
    else:
        frame, playhead_label = start + 100, "selection"
    tc = _timecode(frame)
    expected = deepcopy(state)
    expected_matrix = _timeline(expected, reader)
    for kind, index in LOCKS:
        _track(expected_matrix, kind, index)["GetIsTrackLocked"] = {"value": True}
    timeline = _context(resolve, config, identity, probe, reader)
    operations = [
        (
            "SetTrackLock",
            {"trackType": kind, "trackIndex": index, "locked": True},
            lambda kind=kind, index=index, timeline=timeline: timeline.SetTrackLock(
                kind, index, True
            ),
            lambda kind=kind, index=index, timeline=timeline: timeline.GetIsTrackLocked(
                kind, index
            ),
        )
        for kind, index in LOCKS
    ]
    operations.append(
        (
            "SetCurrentTimecode",
            {"timecode": tc},
            lambda timeline=timeline: timeline.SetCurrentTimecode(tc),
            lambda timeline=timeline: timeline.GetCurrentTimecode(),
        )
    )
    fields = {
        "priorPair": {"path": config["priorPair"], "sha256": config["priorPairSha256"]},
        "originalLocks": original_locks,
        "originalPlayhead": original_playhead,
        "target": {
            "uids": {
                kind: item["GetUniqueId"]["value"] for kind, item in items.items()
            },
            "sourceUids": {
                kind: item.get("GetMediaPoolItem", {})
                .get("GetUniqueId", {})
                .get("value")
                for kind, item in items.items()
            },
            "startFrame": start,
            "endFrame": end,
            f"{playhead_label}Frame": frame,
            f"{playhead_label}Timecode": tc,
            "frameRate": FRAME_RATE,
        },
        "menuCommandDispatched": False,
    }
    return _apply(
        resolve,
        config,
        probe,
        reader,
        output,
        sources,
        identity,
        case,
        current,
        pool,
        expected,
        operations,
        tc,
        fields,
        "case-prepared",
        "preparedPair",
    )


def paste_position(resolve, config, *, probe, reader=None):
    reader = reader or _reader(probe)
    case = config.get("case")
    if case != "R1-copy":
        raise RuntimeError("Paste positioning is limited to the fixed R1-copy case")
    output, sources, identity = _base(resolve, config, probe, reader, case)
    preparation = _pin(
        reader,
        output,
        config.get("preparationResult"),
        config.get("preparationResultSha256"),
        probe,
    )
    post_copy = _pin(
        reader,
        output,
        config.get("postCopyPair"),
        config.get("postCopyPairSha256"),
        probe,
    )
    selection = _pin(
        reader,
        output,
        config.get("selectionResult"),
        config.get("selectionResultSha256"),
        probe,
    )
    if (
        preparation.get("status") != "case-prepared"
        or preparation.get("case") != case
        or selection.get("status") != "editorial-readback-retained"
        or selection.get("label") != "r1-copy-selected"
        or selection.get("readOnly") is not True
        or selection.get("failure") is not None
        or post_copy.get("selectedTimelineUid") != MATRIX_UID
    ):
        raise RuntimeError(
            "Exact R1-copy preparation, selection, and post-copy pins required"
        )
    _, _, prepared_state, prepared_pool = _prepared_state(
        reader, output, preparation, probe
    )
    copy_state, copy_pool = reader._validate_read_pair(post_copy, probe)
    if copy_state != prepared_state or copy_pool != prepared_pool:
        raise RuntimeError(
            "Copy command changed the guarded timeline before paste positioning"
        )
    _target_pair(copy_state, reader, case)
    target = preparation.get("target", {})
    selection_pair = selection.get("pair", {})
    selection_pair_path = Path(selection_pair.get("path", ""))
    if (
        selection_pair.get("sha256") != config.get("postCopyPairSha256")
        or selection_pair_path.is_symlink()
        or not selection_pair_path.is_file()
        or selection_pair_path.resolve() != (output / config["postCopyPair"]).resolve()
    ):
        raise RuntimeError(
            "Selected-item readback is not bound to the pinned post-copy pair"
        )
    passes = selection.get("selectionPasses")
    target_uids, source_uids = target.get("uids", {}), target.get("sourceUids", {})
    if (
        not isinstance(passes, list)
        or len(passes) != 2
        or passes[0] != passes[1]
        or passes[0].get("playhead") != "00:01:24:00"
        or [row.get("type") for row in selection.get("selectionShapes", [])]
        != ["list", "list"]
    ):
        raise RuntimeError(
            "Fresh R1-copy selection is incomplete or at the wrong playhead"
        )
    selected = passes[0].get("items", [])
    selected_by_uid = {
        item.get("GetUniqueId", {}).get("value"): item for item in selected
    }
    if (
        len(selected) != 2
        or set(selected_by_uid) != set(target_uids.values())
        or set(source_uids) != {"video", "audio"}
        or any(not isinstance(uid, str) or not uid for uid in source_uids.values())
    ):
        raise RuntimeError("Selected clips are not the exact retained R1-copy sources")
    for kind, uid in target_uids.items():
        item = selected_by_uid[uid]
        media_uid = item.get("GetMediaPoolItem", {}).get("GetUniqueId", {}).get("value")
        linked = [row.get("value") for row in item.get("GetLinkedItems", [])]
        peer_uid = target_uids["audio" if kind == "video" else "video"]
        if media_uid != source_uids[kind] or peer_uid not in linked:
            raise RuntimeError("Selected R1-copy item/source/link identity changed")

    matrix = _timeline(copy_state, reader)
    for kind, index in (("video", 1), ("audio", 1)):
        track = _track(matrix, kind, index)
        if track.get("GetIsTrackLocked") != {"value": False}:
            raise RuntimeError(f"R1-copy destination {kind}1 is locked")
        for item in track.get("items", []):
            start = item.get("GetStart", {}).get("value")
            end = item.get("GetEnd", {}).get("value")
            if not isinstance(start, int) or not isinstance(end, int):
                raise RuntimeError(f"R1-copy destination {kind}1 has unreadable bounds")
            if start <= CASES[case]["pasteEnd"] and end >= CASES[case]["pasteStart"]:
                raise RuntimeError(f"Reserved R1-copy {kind}1 paste range is occupied")
    timeline = _context(resolve, config, identity, probe, reader)
    _, live_state, live_pool = _read(reader, resolve, config, identity, sources, probe)
    if (
        live_state != copy_state
        or live_pool != copy_pool
        or timeline.GetCurrentTimecode() != "00:01:24:00"
    ):
        raise RuntimeError(
            "Fresh full state/playhead differs from the R1-copy selection pin"
        )

    playhead = _timecode(CASES[case]["pasteStart"])
    result = {
        "case": case,
        "status": "paste-position-refused-partial-state-retained",
        "preparationResult": {
            "path": config["preparationResult"],
            "sha256": config["preparationResultSha256"],
        },
        "postCopyPair": {
            "path": config["postCopyPair"],
            "sha256": config["postCopyPairSha256"],
        },
        "selectionResult": {
            "path": config["selectionResult"],
            "sha256": config["selectionResultSha256"],
        },
        "target": target,
        "pasteRange": {
            "startFrame": CASES[case]["pasteStart"],
            "endFrame": CASES[case]["pasteEnd"],
            "timecode": playhead,
        },
        "failure": None,
        "menuCommandDispatched": False,
        "saveDispatched": False,
        "environment": {
            "productName": resolve.GetProductName(),
            "version": resolve.GetVersion(),
            "python": platform.python_version(),
        },
    }
    directory, journal = _evidence_dir(output)
    result.update({"directory": str(directory), "journal": str(journal)})
    reader._write(directory / "before.json", post_copy)
    _append(journal, "FullReadback", "before", {"path": "before.json"})
    try:
        timeline = _context(resolve, config, identity, probe, reader)
        _append(journal, "SetCurrentTimecode", "request", playhead)
        returned = timeline.SetCurrentTimecode(playhead)
        _append(journal, "SetCurrentTimecode", "return", returned)
        if returned is not True or timeline.GetCurrentTimecode() != playhead:
            raise RuntimeError("Paste playhead did not set and read back")
    except Exception as error:
        result["failure"] = f"{type(error).__name__}: {error}"
    try:
        after, after_state, after_pool = _read(
            reader, resolve, config, identity, sources, probe
        )
        reader._write(directory / "after.json", after)
        result["positionedPair"] = {
            "path": str(directory.relative_to(output) / "after.json"),
            "sha256": probe.sha256(directory / "after.json"),
        }
        timeline = _context(resolve, config, identity, probe, reader)
        if (
            result["failure"] is None
            and after_state == copy_state
            and after_pool == copy_pool
            and timeline.GetCurrentTimecode() == playhead
        ):
            result["status"] = "paste-position-ready"
        elif result["failure"] is None:
            result["failure"] = "Full postflight differs from bounded paste positioning"
    except Exception as error:
        result["postflightFailure"] = f"{type(error).__name__}: {error}"
    reader._write(directory / "result.json", result)
    return result


def restore(resolve, config, *, probe, reader=None):
    reader = reader or _reader(probe)
    case = config.get("case")
    output, sources, identity = _base(resolve, config, probe, reader, case)
    preparation = _pin(
        reader,
        output,
        config.get("preparationResult"),
        config.get("preparationResultSha256"),
        probe,
    )
    post_edit = _pin(
        reader,
        output,
        config.get("postEditPair"),
        config.get("postEditPairSha256"),
        probe,
    )
    if (
        preparation.get("status") != "case-prepared"
        or preparation.get("case") != case
        or post_edit.get("selectedTimelineUid") != MATRIX_UID
        or not isinstance(preparation.get("target"), dict)
    ):
        raise RuntimeError("Exact case preparation and post-edit pins are required")
    _, _, _, _ = _prepared_state(reader, output, preparation, probe)
    state, pool = reader._validate_read_pair(post_edit, probe)
    _timeline(state, reader)
    if (
        state.get("projectId") != PROJECT_ID
        or state.get("projectName") != config["projectName"]
    ):
        raise RuntimeError("Post-edit pair project identity changed")
    for kind, index in LOCKS:
        if _track(_timeline(state, reader), kind, index).get("GetIsTrackLocked") != {
            "value": True
        }:
            raise RuntimeError("Protected editorial tracks are not all locked")
    timeline = _context(resolve, config, identity, probe, reader)
    live, live_state, live_pool = _read(
        reader, resolve, config, identity, sources, probe
    )
    if case == "R1-copy":
        target_tc = _timecode(CASES[case]["pasteStart"])
    else:
        target_key = {
            "R1-trim": "trimPlayheadTimecode",
            "R2-linked": "splitPlayheadTimecode",
        }.get(case, "selectionTimecode")
        target_tc = preparation["target"][target_key]
    if (
        live_state != state
        or live_pool != pool
        or timeline.GetCurrentTimecode() != target_tc
    ):
        raise RuntimeError(
            "Fresh post-edit state/source/playhead differs from supplied pin"
        )
    original_locks = preparation.get("originalLocks", {})
    expected = deepcopy(state)
    for kind, index in LOCKS:
        key = f"{kind}:{index}"
        if not isinstance(original_locks.get(key), bool):
            raise RuntimeError("Recorded original lock state is unreadable")
        _track(_timeline(expected, reader), kind, index)["GetIsTrackLocked"] = {
            "value": original_locks[key]
        }
    timeline = _context(resolve, config, identity, probe, reader)
    operations = [
        (
            "SetTrackLock",
            {
                "trackType": kind,
                "trackIndex": index,
                "locked": original_locks[f"{kind}:{index}"],
            },
            lambda kind=kind, index=index, timeline=timeline: timeline.SetTrackLock(
                kind, index, original_locks[f"{kind}:{index}"]
            ),
            lambda kind=kind, index=index, timeline=timeline: timeline.GetIsTrackLocked(
                kind, index
            ),
        )
        for kind, index in LOCKS
    ]
    original_playhead = preparation["originalPlayhead"]
    operations.append(
        (
            "SetCurrentTimecode",
            {"timecode": original_playhead},
            lambda timeline=timeline: timeline.SetCurrentTimecode(original_playhead),
            lambda timeline=timeline: timeline.GetCurrentTimecode(),
        )
    )
    fields = {
        "preparationResult": {
            "path": config["preparationResult"],
            "sha256": config["preparationResultSha256"],
        },
        "postEditPair": {
            "path": config["postEditPair"],
            "sha256": config["postEditPairSha256"],
        },
        "originalLocks": original_locks,
        "originalPlayhead": original_playhead,
    }
    return _apply(
        resolve,
        config,
        probe,
        reader,
        output,
        sources,
        identity,
        case,
        live,
        pool,
        expected,
        operations,
        original_playhead,
        fields,
        "restored-unsaved",
        "restoredPair",
    )


def run(resolve, config, *, probe):
    if config.get("action") == "editorial-case-prepare":
        return prepare(resolve, config, probe=probe)
    if config.get("action") == "editorial-case-restore":
        return restore(resolve, config, probe=probe)
    if config.get("action") == "editorial-copy-paste-position":
        return paste_position(resolve, config, probe=probe)
    raise RuntimeError("Only the fixed Issue 141 editorial actions are supported")
