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
    "R2-unlinked": {"start": 3000, "end": 3199, "sourceStart": 0, "sourceEnd": 199},
    "R2-picture": {"start": 3500, "end": 3699, "sourceStart": 0, "sourceEnd": 199},
    "R2-partial": {"start": 4000, "end": 4199, "sourceStart": 0, "sourceEnd": 199},
    "R2-residual": {"start": 4500, "end": 4699, "sourceStart": 0, "sourceEnd": 199},
    "R2-offset": {"start": 5000, "end": 5199, "sourceStart": 0, "sourceEnd": 199},
    "R3-Graphic": {"start": 8500, "end": 8699, "sourceStart": 0, "sourceEnd": 199},
    "R3-boundary": {"start": 9000, "end": 9199, "sourceStart": 0, "sourceEnd": 199},
    "R3-boundary-A3": {"start": 9000, "end": 9199, "sourceStart": 0, "sourceEnd": 199},
}
R2_LINKED_SPLITS = {
    "R2-residual": (60, 70),
    "R3-Graphic": (100,),
    "R3-boundary": (100,),
    "R3-boundary-A3": (100,),
}
R2_LINKED_MARKERS = {
    "R3-boundary-A3": "R3-boundary",
}
R2_SINGLE = {
    "R2-unlinked": {
        "marker": "R2-unlinked",
        "track": "audio",
        "cutStart": 60,
        "cutEnd": 70,
    },
    "R2-picture": {
        "marker": "R2-picture-only",
        "track": "video",
        "cutStart": 60,
        "cutEnd": 70,
    },
    "R2-partial": {
        "marker": "R2-partial",
        "track": "audio",
        "cutStart": 65,
        "cutEnd": 70,
    },
    "R2-offset": {"marker": "R2-offset", "track": "audio", "selection": 100},
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


def _marker_case(case):
    return R2_SINGLE.get(case, {"marker": R2_LINKED_MARKERS.get(case, case)})["marker"]


def _marked_item(state, reader, kind, index, marker):
    matches = []
    for item in _track(_timeline(state, reader), kind, index).get("items", []):
        for value in item.get("GetMarkers", {}).get("value", {}).values():
            try:
                data = json.loads(value.get("customData", ""))
            except (json.JSONDecodeError, TypeError):
                continue
            if data.get("issue") == 141 and data.get("section") == marker:
                matches.append(item)
                break
    if len(matches) != 1:
        raise RuntimeError(f"Exact {marker} {kind}{index} occurrence changed")
    return matches[0]


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
                marker_case = _marker_case(case)
                if data.get("issue") == 141 and data.get("section") == marker_case:
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


def _context(resolve, config, identity, probe, reader, page="edit"):
    project = reader._context(resolve, config, identity, probe, MATRIX_UID)
    if (
        resolve.GetProductName() != "DaVinci Resolve Studio"
        or resolve.GetVersion() != BUILD
        or (page is not None and resolve.GetCurrentPage() != page)
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
    protected = preparation.get("protectedTracks", [list(row) for row in LOCKS])
    for kind, index in protected:
        _track(_timeline(expected, reader), kind, index)["GetIsTrackLocked"] = {
            "value": True
        }
    if preparation.get("target", {}).get("unlinkPrepared") is True:
        target_uids = preparation["target"].get("uids", {})
        for kind, uid in target_uids.items():
            track = _track(_timeline(expected, reader), kind, 1)
            item = next(
                (
                    item
                    for item in track["items"]
                    if item.get("GetUniqueId", {}).get("value") == uid
                ),
                None,
            )
            if item is None:
                raise RuntimeError("Prepared unlinked pair UID is missing")
            item["GetLinkedItems"] = []
    for row in preparation.get("target", {}).get("enabledClips", []):
        item = _marked_item(expected, reader, row["kind"], row["index"], row["section"])
        if item.get("GetUniqueId", {}).get("value") != row["uid"]:
            raise RuntimeError("Prepared enabled clip UID changed")
        item["GetClipEnabled"] = {"value": row["enabled"]}
    marker = preparation.get("target", {}).get("addedMarker")
    if marker is not None:
        markers = _timeline(expected, reader).get("GetMarkers", {}).get("value", {})
        if markers.get(str(marker["frame"])) is not None:
            raise RuntimeError(
                "Prepared authored marker already existed in prior state"
            )
        markers[str(marker["frame"])] = deepcopy(marker["value"])
    if (
        prepared_state != expected
        or prepared_pool != initial_pool
        or preparation.get("originalPlayhead") is None
    ):
        raise RuntimeError(
            "Editorial prepared evidence does not verify against its prior pin"
        )
    return initial_state, initial_pool, prepared_state, prepared_pool


def _r2_children(state, reader, source_uids, markers, ranges, case="R2-linked"):
    found = {}
    for kind in ("video", "audio"):
        track = _track(_timeline(state, reader), kind, 1)
        candidates = [
            item
            for item in track.get("items", [])
            if item.get("GetMediaPoolItem", {}).get("GetUniqueId", {}).get("value")
            == source_uids[kind]
            and CASES[case]["start"]
            <= item.get("GetStart", {}).get("value", -1)
            <= CASES[case]["end"]
        ]
        actual = [
            (
                item.get("GetStart", {}).get("value"),
                item.get("GetEnd", {}).get("value"),
                item.get("GetSourceStartFrame", {}).get("value"),
                item.get("GetSourceEndFrame", {}).get("value"),
            )
            for item in candidates
        ]
        if sorted(actual) != sorted(ranges) or len(candidates) != len(ranges):
            raise RuntimeError(f"R2-linked {kind} child ranges changed")
        by_range = dict(zip(actual, candidates, strict=True))
        if len(by_range) != len(ranges):
            raise RuntimeError(f"R2-linked {kind} child range is duplicated")
        found[kind] = [by_range[interval] for interval in ranges]
        if any(
            item.get("GetMarkers") != markers[kind]
            or not isinstance(item.get("GetUniqueId", {}).get("value"), str)
            or not item["GetUniqueId"]["value"]
            for item in found[kind]
        ):
            raise RuntimeError(f"R2-linked {kind} child identity or markers changed")
    for position in range(len(ranges)):
        video, audio = found["video"][position], found["audio"][position]
        video_uid = video["GetUniqueId"]["value"]
        audio_uid = audio["GetUniqueId"]["value"]
        if (
            video_uid == audio_uid
            or [row.get("value") for row in video.get("GetLinkedItems", [])]
            != [audio_uid]
            or [row.get("value") for row in audio.get("GetLinkedItems", [])]
            != [video_uid]
        ):
            raise RuntimeError("R2-linked split child links are not reciprocal")
    all_uids = {
        item["GetUniqueId"]["value"]
        for kind in ("video", "audio")
        for item in found[kind]
    }
    if len(all_uids) != len(ranges) * 2:
        raise RuntimeError("R2-linked split child UIDs are not unique")
    return found


def _razor_child(parent, observed, record_start, record_end, source_start, source_end):
    expected = deepcopy(parent)
    parent_source_start = parent["GetSourceStartFrame"]["value"]
    parent_source_end = parent["GetSourceEndFrame"]["value"]
    derived = {
        "GetStart": record_start,
        "GetStart(True)": float(record_start),
        "GetEnd": record_end,
        "GetEnd(True)": float(record_end),
        "GetDuration": record_end - record_start,
        "GetDuration(True)": float(record_end - record_start),
        "GetSourceStartFrame": source_start,
        "GetSourceStartTime": source_start / 25,
        "GetSourceEndFrame": source_end,
        "GetSourceEndTime": source_end / 25,
    }
    if "GetLeftOffset" in parent:
        left_offset = (
            parent["GetLeftOffset"]["value"] + source_start - parent_source_start
        )
        derived["GetLeftOffset"] = left_offset
        derived["GetLeftOffset(True)"] = float(left_offset)
    if "GetRightOffset" in parent:
        right_offset = (
            parent["GetRightOffset"]["value"] + parent_source_end - source_end
        )
        derived["GetRightOffset"] = right_offset
        derived["GetRightOffset(True)"] = float(right_offset)
    for field, value in derived.items():
        if field in parent:
            expected[field] = {"value": value}
    for field in ("GetUniqueId", "GetLinkedItems"):
        if field in observed:
            expected[field] = deepcopy(observed[field])
    return expected


def _r2_replace(state, reader, prior_ids, children, parents, ranges):
    expected = deepcopy(state)
    matrix = _timeline(expected, reader)
    for kind in ("video", "audio"):
        track = _track(matrix, kind, 1)
        items = track["items"]
        if sum(
            item.get("GetUniqueId", {}).get("value") in prior_ids[kind]
            for item in items
        ) != len(prior_ids[kind]):
            raise RuntimeError(f"R2-linked prior {kind} children are missing")
        items[:] = [
            item
            for item in items
            if item.get("GetUniqueId", {}).get("value") not in prior_ids[kind]
        ] + [
            _razor_child(parents[kind][position], child, *ranges[position])
            for position, child in enumerate(children[kind])
        ]
        items.sort(key=lambda item: json.dumps(item["GetUniqueId"], sort_keys=True))
    return expected


def _usage_delta(pool, source_uids, delta):
    expected = deepcopy(pool)
    changed = set()

    inventory = expected.get("items")
    if isinstance(inventory, list) and all(
        isinstance(row, dict) and "uid" in row for row in inventory
    ):
        counts = {uid: 0 for uid in source_uids}
        for row in inventory:
            uid = row.get("uid")
            if uid not in source_uids:
                continue
            counts[uid] += 1
            props = row.get("evidence", {}).get("GetClipProperty", {}).get("value", {})
            usage = props.get("Usage")
            if (
                not isinstance(usage, str)
                or not usage.isdigit()
                or int(usage) + delta < 0
            ):
                raise RuntimeError("R2 source pool Usage delta is unreadable")
            props["Usage"] = str(int(usage) + delta)
            changed.add(uid)
        if changed != set(source_uids) or any(count != 1 for count in counts.values()):
            raise RuntimeError("R2 source pool UIDs are missing or duplicated")
        return expected

    def visit(value):
        if isinstance(value, dict):
            uid = value.get("GetUniqueId", {}).get("value")
            props = value.get("GetClipProperty", {}).get("value")
            if uid in source_uids and isinstance(props, dict):
                usage = props.get("Usage")
                if (
                    not isinstance(usage, str)
                    or not usage.isdigit()
                    or int(usage) + delta < 0
                ):
                    raise RuntimeError("R2 source Usage delta is unreadable")
                props["Usage"] = str(int(usage) + delta)
                changed.add(uid)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(expected)
    if changed != set(source_uids):
        raise RuntimeError("R2 source UIDs are missing from Usage evidence")
    return expected


def _r2_pin(reader, output, relative, digest, probe, label):
    pair = _pin(reader, output, relative, digest, probe)
    if (
        pair.get("selectedTimelineUid") != MATRIX_UID
        or pair.get("timelineConsistency") != "equal-adjacent-reads"
        or pair.get("poolConsistency") != "equal-adjacent-reads"
    ):
        raise RuntimeError(f"Pinned {label} must be a complete stable Matrix pair")
    return pair


def _selected_uids(
    reader, output, probe, config, expected_pair, expected_pair_sha, label, targets
):
    selection = _pin(
        reader,
        output,
        config.get("selectionResult"),
        config.get("selectionResultSha256"),
        probe,
    )
    pair_ref = selection.get("pair", {})
    pair_path = Path(pair_ref.get("path", ""))
    if (
        selection.get("status") != "editorial-readback-retained"
        or selection.get("label") != label
        or selection.get("readOnly") is not True
        or selection.get("failure") is not None
        or pair_ref.get("sha256") != expected_pair_sha
        or pair_path.is_symlink()
        or not pair_path.is_file()
        or not pair_path.resolve().is_relative_to(output.resolve())
    ):
        raise RuntimeError(f"{label} exact selected-item readback is required")
    selected_pair = _pin(
        reader,
        output,
        str(pair_path.resolve().relative_to(output.resolve())),
        pair_ref["sha256"],
        probe,
    )
    if selected_pair != expected_pair:
        raise RuntimeError(f"{label} selected-item pair differs from its state pin")
    passes = selection.get("selectionPasses")
    shapes = selection.get("selectionShapes")
    if (
        not isinstance(passes, list)
        or len(passes) != 2
        or passes[0] != passes[1]
        or not isinstance(shapes, list)
        or [row.get("type") for row in shapes] != ["list", "list"]
        or [row.get("count") for row in shapes] != [len(targets), len(targets)]
    ):
        raise RuntimeError(f"{label} selected-item readback is incomplete")
    selected = passes[0].get("items", [])
    by_uid = {item.get("GetUniqueId", {}).get("value"): item for item in selected}
    expected_uids = {row[2] for row in targets}
    if len(selected) != len(targets) or set(by_uid) != expected_uids:
        raise RuntimeError(f"{label} selected UIDs are not the exact split targets")
    for kind, index, uid, source_uid, linked_uids in targets:
        item = by_uid[uid]
        if (
            item.get("GetMediaPoolItem", {}).get("GetUniqueId", {}).get("value")
            != source_uid
            or [row.get("value") for row in item.get("GetLinkedItems", [])]
            != linked_uids
        ):
            raise RuntimeError(f"{label} selected {kind}{index} source/link changed")
    return selected


def _r2_first_split(
    preparation, prepared_state, split_state, split_pool, prepared_pool, reader
):
    spec = CASES["R2-linked"]
    target = preparation.get("target", {})
    source_uids = target.get("sourceUids", {})
    if (
        preparation.get("case") != "R2-linked"
        or preparation.get("status") != "case-prepared"
        or target.get("startFrame") != spec["start"]
        or target.get("endFrame") != spec["end"]
        or target.get("splitPlayheadFrame") != 2560
        or target.get("splitPlayheadTimecode") != "00:01:42:10"
        or set(source_uids) != {"video", "audio"}
        or len(set(source_uids.values())) != 2
        or any(not isinstance(uid, str) or not uid for uid in source_uids.values())
    ):
        raise RuntimeError("R2-linked preparation/source binding changed")
    original_items, _, _ = _target_pair(prepared_state, reader, "R2-linked")
    markers = {kind: item.get("GetMarkers") for kind, item in original_items.items()}
    originals = {
        kind: item["GetUniqueId"]["value"] for kind, item in original_items.items()
    }
    prior_uids = {
        item["GetUniqueId"]["value"]
        for timeline_row in prepared_state["timelines"]
        for track in timeline_row.get("tracks", [])
        for item in track.get("items", [])
    }
    if any(
        original_items[kind]
        .get("GetMediaPoolItem", {})
        .get("GetUniqueId", {})
        .get("value")
        != source_uids[kind]
        for kind in ("video", "audio")
    ):
        raise RuntimeError("R2-linked prepared source UIDs changed")
    children = _r2_children(
        split_state,
        reader,
        source_uids,
        markers,
        [(2500, 2560, 0, 60), (2560, 2699, 60, 199)],
    )
    all_uids = {
        item["GetUniqueId"]["value"]
        for kind in ("video", "audio")
        for item in children[kind]
    }
    if len(all_uids) != 4 or any(
        children[kind][0]["GetUniqueId"]["value"] != originals[kind]
        or children[kind][1]["GetUniqueId"]["value"] in originals.values()
        or children[kind][1]["GetUniqueId"]["value"] in prior_uids
        for kind in ("video", "audio")
    ):
        raise RuntimeError(
            "R2-linked razor UID lineage differs from observed split behavior"
        )
    expected = _r2_replace(
        prepared_state,
        reader,
        {kind: (uid,) for kind, uid in originals.items()},
        children,
        {kind: [original_items[kind]] * len(children[kind]) for kind in children},
        [(2500, 2560, 0, 60), (2560, 2699, 60, 199)],
    )
    expected = _usage_delta(expected, set(source_uids.values()), 1)
    expected_pool = _usage_delta(prepared_pool, set(source_uids.values()), 1)
    if expected != split_state or expected_pool != split_pool:
        raise RuntimeError("First R2-linked split changed unrelated full state")
    for kind, index in LOCKS:
        if _track(_timeline(split_state, reader), kind, index).get(
            "GetIsTrackLocked"
        ) != {"value": True}:
            raise RuntimeError("R2-linked split changed a protected track lock")
    return children


def _named_linked_children(
    preparation, before_state, before_pool, after_state, after_pool, reader, case, stage
):
    if case not in R2_LINKED_SPLITS or case == "R3-boundary-A3":
        raise RuntimeError("A named linked split case is required")
    start, end = CASES[case]["start"], CASES[case]["end"]
    target = preparation.get("target", {})
    source_uids = target.get("sourceUids", {})
    target_uids = target.get("uids", {})
    if (
        preparation.get("case") != case
        or preparation.get("status") != "case-prepared"
        or target.get("startFrame") != start
        or target.get("endFrame") != end
        or set(source_uids) != {"video", "audio"}
        or set(target_uids) != {"video", "audio"}
    ):
        raise RuntimeError(f"{case} preparation/source bindings changed")
    if stage == "first":
        parents, pinned_start, pinned_end = _target_pair(before_state, reader, case)
        if (start, end) != (pinned_start, pinned_end) or any(
            parents[kind]
            .get("GetMediaPoolItem", {})
            .get("GetUniqueId", {})
            .get("value")
            != source_uids[kind]
            or parents[kind].get("GetUniqueId", {}).get("value") != target_uids[kind]
            for kind in ("video", "audio")
        ):
            raise RuntimeError(f"{case} preparation/source bindings changed")
    elif stage == "second" and case == "R2-residual":
        markers = {}
        for kind in ("video", "audio"):
            track = _track(_timeline(before_state, reader), kind, 1)
            left = [
                item
                for item in track.get("items", [])
                if item.get("GetMediaPoolItem", {}).get("GetUniqueId", {}).get("value")
                == source_uids[kind]
                and item.get("GetStart", {}).get("value") == start
            ]
            if len(left) != 1:
                raise RuntimeError(f"{case} retained left child is missing")
            markers[kind] = left[0].get("GetMarkers")
        ranges = [
            (start, start + 60, 0, 60),
            (start + 60, end, 60, 199),
        ]
        parents = _r2_children(
            before_state,
            reader,
            source_uids,
            markers,
            ranges,
            case,
        )
        parents = {kind: [items[0], items[1]] for kind, items in parents.items()}
    else:
        raise RuntimeError(f"Unsupported {case} split stage")
    marker = _marker_case(case)
    if stage == "first" and case == "R2-residual":
        residual = _marked_item(before_state, reader, "audio", 2, marker)
        if residual.get("GetClipEnabled") != {"value": True} or _track(
            _timeline(before_state, reader), "audio", 2
        ).get("GetIsTrackEnabled") != {"value": True}:
            raise RuntimeError("R2-residual A2 must remain enabled")
    elif stage == "first" and case == "R3-Graphic":
        graphic_track = _track(_timeline(before_state, reader), "video", 3)
        if graphic_track.get("GetIsTrackEnabled") != {"value": True}:
            raise RuntimeError("R3-Graphic V3 track must remain enabled")
        _marked_item(before_state, reader, "video", 3, marker)
    elif stage == "first" and case == "R3-boundary":
        bed = _marked_item(before_state, reader, "audio", 3, marker)
        if bed.get("GetClipEnabled") != {"value": True} or _track(
            _timeline(before_state, reader), "audio", 3
        ).get("GetIsTrackEnabled") != {"value": True}:
            raise RuntimeError("R3-boundary A3 crossing bed must remain enabled")

    cuts = R2_LINKED_SPLITS[case]
    if stage == "first":
        ranges = [
            (start, start + cuts[0], 0, cuts[0]),
            (start + cuts[0], end, cuts[0], 199),
        ]
    else:
        ranges = [
            (start, start + cuts[0], 0, cuts[0]),
            (start + cuts[0], start + cuts[1], cuts[0], cuts[1]),
            (start + cuts[1], end, cuts[1], 199),
        ]
    children = _r2_children(
        after_state,
        reader,
        source_uids,
        {
            kind: (
                parents[kind].get("GetMarkers")
                if stage == "first"
                else parents[kind][1].get("GetMarkers")
            )
            for kind in parents
        },
        ranges,
        case,
    )
    expected_split = deepcopy(before_state)
    existing = {
        item["GetUniqueId"]["value"]
        for timeline in before_state["timelines"]
        for track in timeline.get("tracks", [])
        for item in track.get("items", [])
    }
    if stage == "first":
        prior = {kind: (parents[kind]["GetUniqueId"]["value"],) for kind in parents}
        derivation_parents = {kind: [parents[kind]] * 2 for kind in parents}
    else:
        prior = {kind: (parents[kind][1]["GetUniqueId"]["value"],) for kind in parents}
        derivation_parents = {kind: [parents[kind][1]] * 2 for kind in parents}
    expected_split = _r2_replace(
        before_state,
        reader,
        prior,
        {
            kind: children[kind] if stage == "first" else children[kind][1:]
            for kind in children
        },
        derivation_parents,
        ranges if stage == "first" else ranges[1:],
    )
    expected_split = _usage_delta(expected_split, set(source_uids.values()), 1)
    expected_pool = _usage_delta(before_pool, set(source_uids.values()), 1)
    for kind in ("video", "audio"):
        if stage == "first":
            retained_uid = parents[kind]["GetUniqueId"]["value"]
            if children[kind][0]["GetUniqueId"]["value"] != retained_uid:
                raise RuntimeError(f"{case} split retained-child UID changed")
            new_uid = children[kind][1]["GetUniqueId"]["value"]
        else:
            left_uid = parents[kind][0]["GetUniqueId"]["value"]
            right_uid = parents[kind][1]["GetUniqueId"]["value"]
            if (
                children[kind][0]["GetUniqueId"]["value"] != left_uid
                or children[kind][1]["GetUniqueId"]["value"] != right_uid
            ):
                raise RuntimeError("R2-residual split UID lineage changed")
            new_uid = children[kind][2]["GetUniqueId"]["value"]
        if new_uid in existing:
            raise RuntimeError(f"{case} new child UID is not unique")
    if expected_split != after_state or expected_pool != after_pool:
        raise RuntimeError(f"{case} split changed unrelated state or source Usage")
    return children


def second_position(resolve, config, *, probe, reader=None):
    reader = reader or _reader(probe)
    case = config.get("case")
    if case in R2_LINKED_SPLITS and case == "R2-residual":
        return _named_second_position(resolve, config, probe=probe, reader=reader)
    if case in R2_SINGLE and case != "R2-offset":
        return _single_second_position(resolve, config, probe=probe, reader=reader)
    if config.get("case") != "R2-linked":
        raise RuntimeError("Second positioning is limited to the fixed R2-linked case")
    output, sources, identity = _base(resolve, config, probe, reader, "R2-linked")
    preparation = _pin(
        reader,
        output,
        config.get("preparationResult"),
        config.get("preparationResultSha256"),
        probe,
    )
    first_pair = _r2_pin(
        reader,
        output,
        config.get("firstSplitPair"),
        config.get("firstSplitPairSha256"),
        probe,
        "first-split pair",
    )
    _, _, prepared_state, prepared_pool = _prepared_state(
        reader, output, preparation, probe
    )
    first_state, first_pool = reader._validate_read_pair(first_pair, probe)
    children = _r2_first_split(
        preparation, prepared_state, first_state, first_pool, prepared_pool, reader
    )
    timeline = _context(resolve, config, identity, probe, reader)
    live, live_state, live_pool = _read(
        reader, resolve, config, identity, sources, probe
    )
    if (
        live_state != first_state
        or live_pool != first_pool
        or timeline.GetCurrentTimecode() != "00:01:42:10"
    ):
        raise RuntimeError(
            "Fresh R2 first-split state/playhead differs from pinned readback"
        )
    playhead = _timecode(2570)
    expected = deepcopy(first_state)
    target = {
        "firstSplitChildUids": {
            kind: [item["GetUniqueId"]["value"] for item in items]
            for kind, items in children.items()
        },
        "splitFrame": 2570,
        "timecode": playhead,
    }
    return _apply(
        resolve,
        config,
        probe,
        reader,
        output,
        sources,
        identity,
        "R2-linked",
        live,
        live_pool,
        expected,
        [
            (
                "SetCurrentTimecode",
                {"timecode": playhead},
                lambda: timeline.SetCurrentTimecode(playhead),
                timeline.GetCurrentTimecode,
            )
        ],
        playhead,
        {
            "preparationResult": {
                "path": config["preparationResult"],
                "sha256": config["preparationResultSha256"],
            },
            "firstSplitPair": {
                "path": config["firstSplitPair"],
                "sha256": config["firstSplitPairSha256"],
            },
            "target": target,
            "menuCommandDispatched": False,
        },
        "second-position-ready",
        "secondPositionPair",
    )


def _named_second_position(resolve, config, *, probe, reader):
    case = "R2-residual"
    output, sources, identity = _base(resolve, config, probe, reader, case)
    preparation = _pin(
        reader,
        output,
        config.get("preparationResult"),
        config.get("preparationResultSha256"),
        probe,
    )
    first_pair = _r2_pin(
        reader,
        output,
        config.get("firstSplitPair"),
        config.get("firstSplitPairSha256"),
        probe,
        "R2-residual first-split pair",
    )
    _, _, prepared_state, prepared_pool = _prepared_state(
        reader, output, preparation, probe
    )
    first_state, first_pool = reader._validate_read_pair(first_pair, probe)
    children = _named_linked_children(
        preparation,
        prepared_state,
        prepared_pool,
        first_state,
        first_pool,
        reader,
        case,
        "first",
    )
    timeline = _context(resolve, config, identity, probe, reader)
    live_pair, live_state, live_pool = _read(
        reader, resolve, config, identity, sources, probe
    )
    if (
        live_state != first_state
        or live_pool != first_pool
        or timeline.GetCurrentTimecode() != _timecode(4560)
    ):
        raise RuntimeError("Fresh R2-residual first-split state or playhead changed")
    target_tc = _timecode(4570)
    return _apply(
        resolve,
        config,
        probe,
        reader,
        output,
        sources,
        identity,
        case,
        live_pair,
        live_pool,
        deepcopy(first_state),
        [
            (
                "SetCurrentTimecode",
                {"timecode": target_tc},
                lambda: timeline.SetCurrentTimecode(target_tc),
                timeline.GetCurrentTimecode,
            )
        ],
        target_tc,
        {
            "preparationResult": {
                "path": config["preparationResult"],
                "sha256": config["preparationResultSha256"],
            },
            "firstSplitPair": {
                "path": config["firstSplitPair"],
                "sha256": config["firstSplitPairSha256"],
            },
            "target": {
                "firstSplitUids": {
                    kind: [item["GetUniqueId"]["value"] for item in rows]
                    for kind, rows in children.items()
                },
                "splitFrame": 4570,
                "timecode": target_tc,
            },
            "menuCommandDispatched": False,
        },
        "second-position-ready",
        "secondPositionPair",
    )


def _linked_selection_targets(preparation, uids):
    return [
        (
            kind,
            1,
            uids[kind],
            preparation["target"]["sourceUids"][kind],
            [uids["audio" if kind == "video" else "video"]],
        )
        for kind in ("video", "audio")
    ]


def named_split_ready(resolve, config, *, probe, reader=None):
    """Gate the next named R2/R3 razor command on the exact selected clips."""
    reader = reader or _reader(probe)
    case = config.get("case")
    if case not in {"R2-residual", "R3-Graphic", "R3-boundary"}:
        raise RuntimeError("A fixed linked R2/R3 split-ready case is required")
    output, sources, identity = _base(resolve, config, probe, reader, case)
    preparation = _pin(
        reader,
        output,
        config.get("preparationResult"),
        config.get("preparationResultSha256"),
        probe,
    )
    _, _, prepared_state, prepared_pool = _prepared_state(
        reader, output, preparation, probe
    )
    if preparation.get("status") != "case-prepared" or preparation.get("case") != case:
        raise RuntimeError(f"{case} exact preparation result is required")

    stage = config.get("stage", "first")
    if stage == "first":
        pair_ref = preparation.get("preparedPair", {})
        selection_pair = _pin(
            reader, output, pair_ref.get("path"), pair_ref.get("sha256"), probe
        )
        pair, pool = reader._validate_read_pair(selection_pair, probe)
        selection_key, digest_key = "firstSelectionResult", "firstSelectionResultSha256"
        label = {
            "R2-residual": "r2-residual-selected",
            "R3-Graphic": "r3-graphic-selected",
            "R3-boundary": "r3-boundary-selected",
        }[case]
        uids = preparation["target"]["uids"]
        cut = R2_LINKED_SPLITS[case][0]
    elif stage == "second" and case == "R2-residual":
        first_pair = _r2_pin(
            reader,
            output,
            config.get("firstSplitPair"),
            config.get("firstSplitPairSha256"),
            probe,
            "R2-residual first-split pair",
        )
        selection_pair = first_pair
        pair, pool = reader._validate_read_pair(first_pair, probe)
        first_children = _named_linked_children(
            preparation,
            prepared_state,
            prepared_pool,
            pair,
            pool,
            reader,
            case,
            "first",
        )
        position = _pin(
            reader,
            output,
            config.get("secondPositionResult"),
            config.get("secondPositionResultSha256"),
            probe,
        )
        pair_ref = position.get("secondPositionPair", {})
        if (
            position.get("status") != "second-position-ready"
            or position.get("case") != case
            or position.get("target", {}).get("splitFrame") != 4570
            or position.get("target", {}).get("firstSplitUids")
            != {
                kind: [item["GetUniqueId"]["value"] for item in rows]
                for kind, rows in first_children.items()
            }
            or position.get("preparationResult", {}).get("sha256")
            != config.get("preparationResultSha256")
            or position.get("firstSplitPair", {}).get("sha256")
            != config.get("firstSplitPairSha256")
            or _r2_pin(
                reader,
                output,
                pair_ref.get("path"),
                pair_ref.get("sha256"),
                probe,
                "R2-residual second-position pair",
            )
            != first_pair
        ):
            raise RuntimeError("Exact R2-residual second-position result is required")
        pair_ref = {"path": pair_ref.get("path"), "sha256": pair_ref.get("sha256")}
        selection_key, digest_key = "selectionResult", "selectionResultSha256"
        label = "r2-residual-second-selected"
        uids = {
            kind: first_children[kind][1]["GetUniqueId"]["value"]
            for kind in ("video", "audio")
        }
        cut = 70
    else:
        raise RuntimeError("Unsupported named split stage")

    selection_config = {
        **config,
        "selectionResult": config.get(selection_key),
        "selectionResultSha256": config.get(digest_key),
    }
    _selected_uids(
        reader,
        output,
        probe,
        selection_config,
        selection_pair,
        pair_ref.get("sha256"),
        label,
        _linked_selection_targets(preparation, uids),
    )
    _, live_state, live_pool = _read(
        resolve=resolve,
        config=config,
        identity=identity,
        sources=sources,
        probe=probe,
        reader=reader,
    )
    timeline = _context(resolve, config, identity, probe, reader)
    expected_tc = _timecode(CASES[case]["start"] + cut)
    if (
        live_state != pair
        or live_pool != pool
        or timeline.GetCurrentTimecode() != expected_tc
    ):
        raise RuntimeError(f"Fresh {case} split-ready state or playhead changed")
    return {
        "status": "split-ready",
        "case": case,
        "stage": stage,
        "selectionResult": {
            "path": config.get(selection_key),
            "sha256": config.get(digest_key),
        },
        "selectionLabel": label,
        "selectedUids": [uids["video"], uids["audio"]],
        "splitFrame": CASES[case]["start"] + cut,
        "menuCommandDispatched": False,
    }


def named_split_review(resolve, config, *, probe, reader=None):
    reader = reader or _reader(probe)
    case = config.get("case")
    if case not in {"R2-residual", "R3-Graphic", "R3-boundary"}:
        raise RuntimeError("A fixed linked R2/R3 split-review case is required")
    output, sources, identity = _base(resolve, config, probe, reader, case)
    preparation = _pin(
        reader,
        output,
        config.get("preparationResult"),
        config.get("preparationResultSha256"),
        probe,
    )
    _, _, prepared_state, prepared_pool = _prepared_state(
        reader, output, preparation, probe
    )
    prepared_ref = preparation.get("preparedPair", {})
    prepared_pair = _pin(
        reader,
        output,
        prepared_ref.get("path"),
        prepared_ref.get("sha256"),
        probe,
    )
    first_selection_config = {
        **config,
        "selectionResult": config.get("firstSelectionResult"),
        "selectionResultSha256": config.get("firstSelectionResultSha256"),
    }
    first_selection_label = {
        "R2-residual": "r2-residual-selected",
        "R3-Graphic": "r3-graphic-selected",
        "R3-boundary": "r3-boundary-selected",
    }[case]
    original = {
        kind: preparation["target"]["uids"][kind] for kind in ("video", "audio")
    }
    _selected_uids(
        reader,
        output,
        probe,
        first_selection_config,
        prepared_pair,
        prepared_ref.get("sha256"),
        first_selection_label,
        _linked_selection_targets(preparation, original),
    )
    first_pair = _r2_pin(
        reader,
        output,
        config.get("firstSplitPair"),
        config.get("firstSplitPairSha256"),
        probe,
        f"{case} first-split pair",
    )
    first_state, first_pool = reader._validate_read_pair(first_pair, probe)
    first_children = _named_linked_children(
        preparation,
        prepared_state,
        prepared_pool,
        first_state,
        first_pool,
        reader,
        case,
        "first",
    )
    if case == "R2-residual":
        position = _pin(
            reader,
            output,
            config.get("secondPositionResult"),
            config.get("secondPositionResultSha256"),
            probe,
        )
        position_ref = position.get("secondPositionPair", {})
        positioned_pair = _r2_pin(
            reader,
            output,
            position_ref.get("path"),
            position_ref.get("sha256"),
            probe,
            "R2-residual second-position pair",
        )
        if (
            position.get("status") != "second-position-ready"
            or position.get("case") != case
            or position.get("target", {}).get("splitFrame") != 4570
            or position.get("target", {}).get("firstSplitUids")
            != {
                kind: [item["GetUniqueId"]["value"] for item in rows]
                for kind, rows in first_children.items()
            }
            or position.get("preparationResult", {}).get("sha256")
            != config.get("preparationResultSha256")
            or position.get("firstSplitPair", {}).get("sha256")
            != config.get("firstSplitPairSha256")
            or reader._validate_read_pair(positioned_pair, probe)
            != (first_state, first_pool)
        ):
            raise RuntimeError("Hash-pinned R2-residual second position changed")
        second_selection_config = {
            **config,
            "selectionResult": config.get("selectionResult"),
            "selectionResultSha256": config.get("selectionResultSha256"),
        }
        second_uids = {
            kind: first_children[kind][1]["GetUniqueId"]["value"]
            for kind in ("video", "audio")
        }
        _selected_uids(
            reader,
            output,
            probe,
            second_selection_config,
            positioned_pair,
            position_ref.get("sha256"),
            "r2-residual-second-selected",
            _linked_selection_targets(preparation, second_uids),
        )
        final_pair = _r2_pin(
            reader,
            output,
            config.get("secondSplitPair"),
            config.get("secondSplitPairSha256"),
            probe,
            "R2-residual second-split pair",
        )
        final_state, final_pool = reader._validate_read_pair(final_pair, probe)
        final_children = _named_linked_children(
            preparation,
            first_state,
            first_pool,
            final_state,
            final_pool,
            reader,
            case,
            "second",
        )
        result_pair = final_pair
        result_children = final_children
        result_ranges = [
            [4500, 4560, 0, 60],
            [4560, 4570, 60, 70],
            [4570, 4699, 70, 199],
        ]
    else:
        result_pair = first_pair
        result_children = first_children
        result_ranges = [
            [CASES[case]["start"], CASES[case]["start"] + 100, 0, 100],
            [CASES[case]["start"] + 100, CASES[case]["end"], 100, 199],
        ]
    timeline = _context(resolve, config, identity, probe, reader)
    _, live_state, live_pool = _read(reader, resolve, config, identity, sources, probe)
    desired_cut = (
        R2_LINKED_SPLITS[case][-1]
        if case == "R2-residual"
        else R2_LINKED_SPLITS[case][0]
    )
    desired_playhead = _timecode(CASES[case]["start"] + desired_cut)
    if (
        live_state != reader._validate_read_pair(result_pair, probe)[0]
        or live_pool != reader._validate_read_pair(result_pair, probe)[1]
        or timeline.GetCurrentTimecode() != desired_playhead
    ):
        raise RuntimeError(f"Fresh {case} split state/source/playhead differs")
    return {
        "status": "split-readback-retained",
        "case": case,
        "preparationResult": {
            "path": config["preparationResult"],
            "sha256": config["preparationResultSha256"],
        },
        "selectionResult": {
            "path": config.get("firstSelectionResult"),
            "sha256": config.get("firstSelectionResultSha256"),
        },
        "firstSplitPair": {
            "path": config["firstSplitPair"],
            "sha256": config["firstSplitPairSha256"],
        },
        "splitPair": {
            "path": config.get("secondSplitPair")
            if case == "R2-residual"
            else config["firstSplitPair"],
            "sha256": config.get("secondSplitPairSha256")
            if case == "R2-residual"
            else config["firstSplitPairSha256"],
        },
        "childUids": {
            kind: [item["GetUniqueId"]["value"] for item in items]
            for kind, items in result_children.items()
        },
        "ranges": result_ranges,
        "menuCommandDispatched": False,
        "saveDispatched": False,
    }


def interval_delete(resolve, config, *, probe, reader=None):
    reader = reader or _reader(probe)
    if config.get("case") == "R2-residual":
        return _residual_interval_delete(resolve, config, probe=probe, reader=reader)
    if config.get("case") in R2_SINGLE and config.get("case") != "R2-offset":
        return _single_interval_delete(resolve, config, probe=probe, reader=reader)
    if config.get("case") != "R2-linked":
        raise RuntimeError("Interval deletion is limited to the fixed R2-linked case")
    output, sources, identity = _base(resolve, config, probe, reader, "R2-linked")
    preparation = _pin(
        reader,
        output,
        config.get("preparationResult"),
        config.get("preparationResultSha256"),
        probe,
    )
    position = _pin(
        reader,
        output,
        config.get("secondPositionResult"),
        config.get("secondPositionResultSha256"),
        probe,
    )
    first_pair = _r2_pin(
        reader,
        output,
        config.get("firstSplitPair"),
        config.get("firstSplitPairSha256"),
        probe,
        "first-split pair",
    )
    second_pair = _r2_pin(
        reader,
        output,
        config.get("secondSplitPair"),
        config.get("secondSplitPairSha256"),
        probe,
        "second-split pair",
    )
    if (
        position.get("status") != "second-position-ready"
        or position.get("case") != "R2-linked"
        or position.get("target", {}).get("timecode") != "00:01:42:20"
        or position.get("target", {}).get("splitFrame") != 2570
        or position.get("firstSplitPair", {}).get("sha256")
        != config.get("firstSplitPairSha256")
        or position.get("preparationResult", {}).get("sha256")
        != config.get("preparationResultSha256")
    ):
        raise RuntimeError("Exact hash-bound R2 second-position result required")
    _, _, prepared_state, prepared_pool = _prepared_state(
        reader, output, preparation, probe
    )
    first_state, first_pool = reader._validate_read_pair(first_pair, probe)
    first_children = _r2_first_split(
        preparation, prepared_state, first_state, first_pool, prepared_pool, reader
    )
    if position.get("target", {}).get("firstSplitChildUids") != {
        kind: [item["GetUniqueId"]["value"] for item in items]
        for kind, items in first_children.items()
    }:
        raise RuntimeError(
            "Second-position result does not bind actual first-split UIDs"
        )
    second_state, second_pool = reader._validate_read_pair(second_pair, probe)
    positioned_ref = position.get("secondPositionPair", {})
    positioned_pair = _r2_pin(
        reader,
        output,
        positioned_ref.get("path"),
        positioned_ref.get("sha256"),
        probe,
        "second-position pair",
    )
    positioned_state, positioned_pool = reader._validate_read_pair(
        positioned_pair, probe
    )
    if positioned_state != first_state or positioned_pool != first_pool:
        raise RuntimeError(
            "Pinned second-position readback differs from the first-split state"
        )
    markers = {
        kind: first_children[kind][1].get("GetMarkers") for kind in ("video", "audio")
    }
    source_uids = preparation["target"]["sourceUids"]
    final_children = _r2_children(
        second_state,
        reader,
        source_uids,
        markers,
        [(2500, 2560, 0, 60), (2560, 2570, 60, 70), (2570, 2699, 70, 199)],
    )
    expected_split = _r2_replace(
        first_state,
        reader,
        {
            kind: (item[1]["GetUniqueId"]["value"],)
            for kind, item in first_children.items()
        },
        {kind: final_children[kind][1:] for kind in ("video", "audio")},
        {kind: [first_children[kind][1]] * 2 for kind in ("video", "audio")},
        [(2560, 2570, 60, 70), (2570, 2699, 70, 199)],
    )
    prior_rights = {
        kind: (items[1]["GetUniqueId"]["value"],)
        for kind, items in first_children.items()
    }
    if any(
        final_children[kind][1]["GetUniqueId"]["value"] != prior_rights[kind][0]
        for kind in ("video", "audio")
    ):
        raise RuntimeError("R2 second split did not retain the left interval UIDs")
    new_uids = {
        final_children[kind][2]["GetUniqueId"]["value"] for kind in ("video", "audio")
    }
    prior_uids = {
        item["GetUniqueId"]["value"]
        for timeline_row in first_state["timelines"]
        for track in timeline_row.get("tracks", [])
        for item in track.get("items", [])
    }
    if len(new_uids) != 2 or not new_uids.isdisjoint(prior_uids):
        raise RuntimeError("R2 second split child UIDs are not new and unique")
    expected_split = _usage_delta(expected_split, set(source_uids.values()), 1)
    expected_pool = _usage_delta(first_pool, set(source_uids.values()), 1)
    if expected_split != second_state or expected_pool != second_pool:
        raise RuntimeError("Second R2 split changed unrelated full state")
    interval = {kind: final_children[kind][1] for kind in ("video", "audio")}
    interval_uids = {
        kind: item["GetUniqueId"]["value"] for kind, item in interval.items()
    }
    timeline = _context(resolve, config, identity, probe, reader)
    live, live_state, live_pool = _read(
        reader, resolve, config, identity, sources, probe
    )
    if (
        live_state != second_state
        or live_pool != second_pool
        or timeline.GetCurrentTimecode() != "00:01:42:20"
    ):
        raise RuntimeError("Fresh R2 interval deletion state/source/playhead differs")
    handles = {}
    for kind in ("video", "audio"):
        rows = timeline.GetItemListInTrack(kind, 1)
        matches = [
            handle
            for handle in rows or []
            if handle.GetUniqueId() == interval_uids[kind]
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"Exact R2 {kind} interval handle is missing or duplicated"
            )
        handles[kind] = matches[0]
        if handles[kind].GetMediaPoolItem().GetUniqueId() != source_uids[kind]:
            raise RuntimeError(f"Exact R2 {kind} interval source handle changed")
    directory, journal = _evidence_dir(output)
    reader._write(directory / "before.json", live)
    _append(journal, "FullReadback", "before", {"path": "before.json"})
    result = {
        "status": "interval-delete-review-required",
        "case": "R2-linked",
        "directory": str(directory),
        "journal": str(journal),
        "preparationResult": {
            "path": config["preparationResult"],
            "sha256": config["preparationResultSha256"],
        },
        "firstSplitPair": {
            "path": config["firstSplitPair"],
            "sha256": config["firstSplitPairSha256"],
        },
        "secondPositionResult": {
            "path": config["secondPositionResult"],
            "sha256": config["secondPositionResultSha256"],
        },
        "secondPositionPair": positioned_ref,
        "secondSplitPair": {
            "path": config["secondSplitPair"],
            "sha256": config["secondSplitPairSha256"],
        },
        "intervalUids": interval_uids,
        "sourceUids": source_uids,
        "interval": {
            "recordStart": 2560,
            "recordEndRaw": 2570,
            "sourceStart": 60,
            "sourceEndRaw": 70,
        },
        "deleteReturn": None,
        "deleteError": None,
        "saveDispatched": False,
    }
    timeline = _context(resolve, config, identity, probe, reader)
    _append(
        journal,
        "Timeline.DeleteClips",
        "request",
        {"uids": [interval_uids["video"], interval_uids["audio"]], "ripple": False},
    )
    try:
        result["deleteReturn"] = timeline.DeleteClips(
            [handles["video"], handles["audio"]], False
        )
        _append(journal, "Timeline.DeleteClips", "return", result["deleteReturn"])
    except Exception as error:
        result["deleteError"] = f"{type(error).__name__}: {error}"
        _append(journal, "Timeline.DeleteClips", "failure", result["deleteError"])
    try:
        after, after_state, after_pool = _read(
            reader, resolve, config, identity, sources, probe
        )
        reader._write(directory / "after.json", after)
        expected_state = deepcopy(second_state)
        for kind in ("video", "audio"):
            track = _track(_timeline(expected_state, reader), kind, 1)
            track["items"] = [
                item
                for item in track["items"]
                if item["GetUniqueId"]["value"] != interval_uids[kind]
            ]
        expected_state = _usage_delta(expected_state, set(source_uids.values()), -1)
        expected_pool = _usage_delta(second_pool, set(source_uids.values()), -1)
        if (
            result["deleteReturn"] is True
            and result["deleteError"] is None
            and after_state == expected_state
            and after_pool == expected_pool
        ):
            result["status"] = "interval-deleted-unsaved"
        else:
            result["postflightFailure"] = (
                "Postflight differs from exact interval removal and "
                "source Usage decrement"
            )
        result["afterPair"] = {
            "path": str(directory.relative_to(output) / "after.json"),
            "sha256": probe.sha256(directory / "after.json"),
        }
    except Exception as error:
        result["postflightFailure"] = f"{type(error).__name__}: {error}"
        _append(
            journal, "FullReadback", "postflight-failure", result["postflightFailure"]
        )
    reader._write(directory / "result.json", result)
    return result


def _residual_interval_delete(resolve, config, *, probe, reader):
    case = "R2-residual"
    output, sources, identity = _base(resolve, config, probe, reader, case)
    preparation = _pin(
        reader,
        output,
        config.get("preparationResult"),
        config.get("preparationResultSha256"),
        probe,
    )
    first_pair = _r2_pin(
        reader,
        output,
        config.get("firstSplitPair"),
        config.get("firstSplitPairSha256"),
        probe,
        "R2-residual first-split pair",
    )
    position = _pin(
        reader,
        output,
        config.get("secondPositionResult"),
        config.get("secondPositionResultSha256"),
        probe,
    )
    second_pair = _r2_pin(
        reader,
        output,
        config.get("secondSplitPair"),
        config.get("secondSplitPairSha256"),
        probe,
        "R2-residual second-split pair",
    )
    _, _, prepared_state, prepared_pool = _prepared_state(
        reader, output, preparation, probe
    )
    first_state, first_pool = reader._validate_read_pair(first_pair, probe)
    first_children = _named_linked_children(
        preparation,
        prepared_state,
        prepared_pool,
        first_state,
        first_pool,
        reader,
        case,
        "first",
    )
    expected_uids = {
        kind: [item["GetUniqueId"]["value"] for item in rows]
        for kind, rows in first_children.items()
    }
    position_ref = position.get("secondPositionPair", {})
    positioned = _r2_pin(
        reader,
        output,
        position_ref.get("path"),
        position_ref.get("sha256"),
        probe,
        "R2-residual second-position pair",
    )
    positioned_state, positioned_pool = reader._validate_read_pair(positioned, probe)
    if (
        position.get("status") != "second-position-ready"
        or position.get("case") != case
        or position.get("target", {}).get("splitFrame") != 4570
        or position.get("target", {}).get("timecode") != _timecode(4570)
        or position.get("target", {}).get("firstSplitUids") != expected_uids
        or position.get("preparationResult", {}).get("sha256")
        != config.get("preparationResultSha256")
        or position.get("firstSplitPair", {}).get("sha256")
        != config.get("firstSplitPairSha256")
        or positioned_state != first_state
        or positioned_pool != first_pool
    ):
        raise RuntimeError("Exact R2-residual second-position result required")
    second_state, second_pool = reader._validate_read_pair(second_pair, probe)
    final_children = _named_linked_children(
        preparation,
        first_state,
        first_pool,
        second_state,
        second_pool,
        reader,
        case,
        "second",
    )
    interval = {kind: rows[1] for kind, rows in final_children.items()}
    interval_uids = {
        kind: row["GetUniqueId"]["value"] for kind, row in interval.items()
    }
    source_uids = preparation["target"]["sourceUids"]
    pair_ref = {
        "path": config.get("secondSplitPair"),
        "sha256": config.get("secondSplitPairSha256"),
    }
    selection_config = {
        **config,
        "selectionResult": config.get("selectionResult"),
        "selectionResultSha256": config.get("selectionResultSha256"),
    }
    _selected_uids(
        reader,
        output,
        probe,
        selection_config,
        second_pair,
        pair_ref["sha256"],
        "r2-residual-interval-selected",
        _linked_selection_targets(preparation, interval_uids),
    )
    timeline = _context(resolve, config, identity, probe, reader)
    live, live_state, live_pool = _read(
        reader, resolve, config, identity, sources, probe
    )
    if (
        live_state != second_state
        or live_pool != second_pool
        or timeline.GetCurrentTimecode() != _timecode(4570)
    ):
        raise RuntimeError("Fresh R2-residual interval state/source/playhead differs")
    handles = {
        kind: _native_item(timeline, kind, interval_uids[kind], source_uids[kind])
        for kind in ("video", "audio")
    }
    directory, journal = _evidence_dir(output)
    reader._write(directory / "before.json", live)
    _append(journal, "FullReadback", "before", {"path": "before.json"})
    result = {
        "status": "interval-delete-review-required",
        "case": case,
        "directory": str(directory),
        "journal": str(journal),
        "preparationResult": {
            "path": config["preparationResult"],
            "sha256": config["preparationResultSha256"],
        },
        "firstSplitPair": {
            "path": config["firstSplitPair"],
            "sha256": config["firstSplitPairSha256"],
        },
        "secondPositionResult": {
            "path": config["secondPositionResult"],
            "sha256": config["secondPositionResultSha256"],
        },
        "secondSplitPair": pair_ref,
        "selectionResult": {
            "path": config["selectionResult"],
            "sha256": config["selectionResultSha256"],
        },
        "intervalUids": interval_uids,
        "sourceUids": source_uids,
        "interval": {
            "recordStart": 4560,
            "recordEndRaw": 4570,
            "sourceStart": 60,
            "sourceEndRaw": 70,
        },
        "deleteReturn": None,
        "deleteError": None,
        "saveDispatched": False,
    }
    _append(
        journal,
        "Timeline.DeleteClips",
        "request",
        {"uids": [interval_uids["video"], interval_uids["audio"]], "ripple": False},
    )
    try:
        result["deleteReturn"] = timeline.DeleteClips(
            [handles["video"], handles["audio"]], False
        )
        _append(journal, "Timeline.DeleteClips", "return", result["deleteReturn"])
    except Exception as error:
        result["deleteError"] = f"{type(error).__name__}: {error}"
        _append(journal, "Timeline.DeleteClips", "failure", result["deleteError"])
    try:
        after, after_state, after_pool = _read(
            reader, resolve, config, identity, sources, probe
        )
        reader._write(directory / "after.json", after)
        expected_state = deepcopy(second_state)
        for kind in ("video", "audio"):
            track = _track(_timeline(expected_state, reader), kind, 1)
            track["items"] = [
                item
                for item in track["items"]
                if item["GetUniqueId"]["value"] != interval_uids[kind]
            ]
        expected_state = _usage_delta(expected_state, set(source_uids.values()), -1)
        expected_pool = _usage_delta(second_pool, set(source_uids.values()), -1)
        if (
            result["deleteReturn"] is True
            and result["deleteError"] is None
            and after_state == expected_state
            and after_pool == expected_pool
        ):
            result["status"] = "interval-deleted-unsaved"
        else:
            result["postflightFailure"] = (
                "Postflight differs from exact linked residual interval removal "
                "and source Usage decrement"
            )
        result["afterPair"] = {
            "path": str(directory.relative_to(output) / "after.json"),
            "sha256": probe.sha256(directory / "after.json"),
        }
    except Exception as error:
        result["postflightFailure"] = f"{type(error).__name__}: {error}"
    reader._write(directory / "result.json", result)
    return result


def _single_parent(preparation, state, reader, case):
    spec, case_spec = CASES[case], R2_SINGLE[case]
    target, found = preparation.get("target", {}), {}
    for kind in ("video", "audio"):
        uid = target.get("uids", {}).get(kind)
        source_uid = target.get("sourceUids", {}).get(kind)
        track = _track(_timeline(state, reader), kind, 1)
        matches = [
            item
            for item in track.get("items", [])
            if item.get("GetUniqueId", {}).get("value") == uid
        ]
        if len(matches) != 1:
            raise RuntimeError(f"Exact {case} prepared {kind} UID changed")
        item = matches[0]
        markers = item.get("GetMarkers", {}).get("value", {})
        tagged = False
        for marker in markers.values():
            try:
                data = json.loads(marker.get("customData", ""))
            except (json.JSONDecodeError, TypeError):
                continue
            tagged |= (
                data.get("issue") == 141 and data.get("section") == case_spec["marker"]
            )
        if (
            item.get("GetMediaPoolItem", {}).get("GetUniqueId", {}).get("value")
            != source_uid
            or item.get("GetStart") != {"value": spec["start"]}
            or item.get("GetEnd") != {"value": spec["end"]}
            or item.get("GetSourceStartFrame") != {"value": 0}
            or item.get("GetSourceEndFrame") != {"value": 199}
            or item.get("GetLinkedItems") != []
            or not tagged
        ):
            raise RuntimeError(f"Exact unlinked {case} pair/source/marker changed")
        found[kind] = item
    return found


def _single_children(state, case, source_uid, marker, ranges, reader):
    spec, target_kind = CASES[case], R2_SINGLE[case]["track"]
    track = _track(_timeline(state, reader), target_kind, 1)
    candidates = [
        item
        for item in track.get("items", [])
        if item.get("GetMediaPoolItem", {}).get("GetUniqueId", {}).get("value")
        == source_uid
        and spec["start"] <= item.get("GetStart", {}).get("value", -1) <= spec["end"]
    ]
    actual = [
        (
            item.get("GetStart", {}).get("value"),
            item.get("GetEnd", {}).get("value"),
            item.get("GetSourceStartFrame", {}).get("value"),
            item.get("GetSourceEndFrame", {}).get("value"),
        )
        for item in candidates
    ]
    if sorted(actual) != sorted(ranges) or len(actual) != len(ranges):
        raise RuntimeError(f"{case} target-track child ranges changed")
    children = dict(zip(actual, candidates, strict=True))
    if len(children) != len(ranges):
        raise RuntimeError(f"{case} target-track child range is duplicated")
    ordered = [children[span] for span in ranges]
    if any(
        item.get("GetMarkers") != marker
        or item.get("GetLinkedItems") != []
        or not item.get("GetUniqueId", {}).get("value")
        for item in ordered
    ):
        raise RuntimeError(f"{case} child markers, links, or UIDs changed")
    if len({item["GetUniqueId"]["value"] for item in ordered}) != len(ordered):
        raise RuntimeError(f"{case} child UIDs are not unique")
    return ordered


def _single_expected(state, case, prior_uid, children, parent, reader):
    expected = deepcopy(state)
    target_kind = R2_SINGLE[case]["track"]
    items = _track(_timeline(expected, reader), target_kind, 1)["items"]
    if (
        sum(item.get("GetUniqueId", {}).get("value") == prior_uid for item in items)
        != 1
    ):
        raise RuntimeError(f"{case} prior target child UID changed")
    items[:] = [
        item for item in items if item.get("GetUniqueId", {}).get("value") != prior_uid
    ]
    spans = [
        (
            child["GetStart"]["value"],
            child["GetEnd"]["value"],
            child["GetSourceStartFrame"]["value"],
            child["GetSourceEndFrame"]["value"],
        )
        for child in children
    ]
    items.extend(
        _razor_child(parent, child, *span)
        for child, span in zip(children, spans, strict=True)
    )
    items.sort(key=lambda item: json.dumps(item["GetUniqueId"], sort_keys=True))
    return expected


def _single_first_split(
    preparation, prepared_state, split_state, split_pool, prepared_pool, reader, case
):
    parent = _single_parent(preparation, prepared_state, reader, case)
    kind = R2_SINGLE[case]["track"]
    local = R2_SINGLE[case]["cutStart"]
    start, end = CASES[case]["start"], CASES[case]["end"]
    source_uid = preparation["target"]["sourceUids"][kind]
    children = _single_children(
        split_state,
        case,
        source_uid,
        parent[kind].get("GetMarkers"),
        [(start, start + local, 0, local), (start + local, end, local, 199)],
        reader,
    )
    old_uid = parent[kind]["GetUniqueId"]["value"]
    existing_uids = {
        item["GetUniqueId"]["value"]
        for timeline_row in prepared_state["timelines"]
        for track in timeline_row.get("tracks", [])
        for item in track.get("items", [])
    }
    if (
        children[0]["GetUniqueId"]["value"] != old_uid
        or children[1]["GetUniqueId"]["value"] in existing_uids
    ):
        raise RuntimeError(
            f"{case} split UID lineage differs from observed razor behavior"
        )
    expected = _single_expected(
        prepared_state, case, old_uid, children, parent[kind], reader
    )
    expected = _usage_delta(expected, {source_uid}, 1)
    expected_pool = _usage_delta(prepared_pool, {source_uid}, 1)
    if expected != split_state or expected_pool != split_pool:
        raise RuntimeError(
            f"{case} first split changed unrelated state or source Usage"
        )
    _single_locks(split_state, case, preparation, reader)
    return parent, children


def _single_locks(state, case, preparation, reader):
    protected = [tuple(row) for row in preparation.get("protectedTracks", [])]
    if not protected:
        raise RuntimeError(f"{case} protected-track record is missing")
    target = (R2_SINGLE[case]["track"], 1)
    for row in ALL_LOCKS:
        want_locked = row != target
        if _track(_timeline(state, reader), *row).get("GetIsTrackLocked") != {
            "value": want_locked
        }:
            raise RuntimeError(f"{case} unrelated/target track lock changed")


def _single_second_position(resolve, config, *, probe, reader):
    case = config.get("case")
    if case not in R2_SINGLE or case == "R2-offset":
        raise RuntimeError("A named fixed single-track R2 cut case is required")
    output, sources, identity = _base(resolve, config, probe, reader, case)
    preparation = _pin(
        reader,
        output,
        config.get("preparationResult"),
        config.get("preparationResultSha256"),
        probe,
    )
    first_pair = _r2_pin(
        reader,
        output,
        config.get("firstSplitPair"),
        config.get("firstSplitPairSha256"),
        probe,
        "first-split pair",
    )
    _, _, prepared_state, prepared_pool = _prepared_state(
        reader, output, preparation, probe
    )
    first_state, first_pool = reader._validate_read_pair(first_pair, probe)
    _parent, children = _single_first_split(
        preparation,
        prepared_state,
        first_state,
        first_pool,
        prepared_pool,
        reader,
        case,
    )
    target_frame = CASES[case]["start"] + R2_SINGLE[case]["cutEnd"]
    target_tc = _timecode(target_frame)
    timeline = _context(resolve, config, identity, probe, reader)
    live, live_state, live_pool = _read(
        reader, resolve, config, identity, sources, probe
    )
    if (
        live_state != first_state
        or live_pool != first_pool
        or timeline.GetCurrentTimecode()
        != _timecode(CASES[case]["start"] + R2_SINGLE[case]["cutStart"])
    ):
        raise RuntimeError(f"Fresh {case} first-split state/playhead differs")
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
        live_pool,
        deepcopy(first_state),
        [
            (
                "SetCurrentTimecode",
                {"timecode": target_tc},
                lambda: timeline.SetCurrentTimecode(target_tc),
                timeline.GetCurrentTimecode,
            )
        ],
        target_tc,
        {
            "preparationResult": {
                "path": config["preparationResult"],
                "sha256": config["preparationResultSha256"],
            },
            "firstSplitPair": {
                "path": config["firstSplitPair"],
                "sha256": config["firstSplitPairSha256"],
            },
            "target": {
                "track": R2_SINGLE[case]["track"],
                "firstSplitUid": children[0]["GetUniqueId"]["value"],
                "secondSplitUid": children[1]["GetUniqueId"]["value"],
                "splitFrame": target_frame,
                "timecode": target_tc,
            },
            "menuCommandDispatched": False,
        },
        "second-position-ready",
        "secondPositionPair",
    )


def _single_interval_delete(resolve, config, *, probe, reader):
    case = config.get("case")
    if case not in R2_SINGLE or case == "R2-offset":
        raise RuntimeError("A named fixed single-track R2 cut case is required")
    output, sources, identity = _base(resolve, config, probe, reader, case)
    preparation = _pin(
        reader,
        output,
        config.get("preparationResult"),
        config.get("preparationResultSha256"),
        probe,
    )
    position = _pin(
        reader,
        output,
        config.get("secondPositionResult"),
        config.get("secondPositionResultSha256"),
        probe,
    )
    first_pair = _r2_pin(
        reader,
        output,
        config.get("firstSplitPair"),
        config.get("firstSplitPairSha256"),
        probe,
        "first-split pair",
    )
    second_pair = _r2_pin(
        reader,
        output,
        config.get("secondSplitPair"),
        config.get("secondSplitPairSha256"),
        probe,
        "second-split pair",
    )
    if (
        position.get("status") != "second-position-ready"
        or position.get("case") != case
        or position.get("target", {}).get("splitFrame")
        != CASES[case]["start"] + R2_SINGLE[case]["cutEnd"]
        or position.get("preparationResult", {}).get("sha256")
        != config.get("preparationResultSha256")
        or position.get("firstSplitPair", {}).get("sha256")
        != config.get("firstSplitPairSha256")
    ):
        raise RuntimeError(f"Hash-pinned {case} second-position result required")
    _, _, prepared_state, prepared_pool = _prepared_state(
        reader, output, preparation, probe
    )
    first_state, first_pool = reader._validate_read_pair(first_pair, probe)
    parent, first_children = _single_first_split(
        preparation,
        prepared_state,
        first_state,
        first_pool,
        prepared_pool,
        reader,
        case,
    )
    if (
        position.get("target", {}).get("firstSplitUid")
        != first_children[0]["GetUniqueId"]["value"]
        or position.get("target", {}).get("secondSplitUid")
        != first_children[1]["GetUniqueId"]["value"]
    ):
        raise RuntimeError(f"{case} position result does not bind first-split UIDs")
    positioned_pair = _r2_pin(
        reader,
        output,
        position.get("secondPositionPair", {}).get("path"),
        position.get("secondPositionPair", {}).get("sha256"),
        probe,
        "position pair",
    )
    positioned_state, positioned_pool = reader._validate_read_pair(
        positioned_pair, probe
    )
    if (
        positioned_state != first_state
        or positioned_pool != first_pool
        or position.get("firstSplitPair", {}).get("sha256")
        != config.get("firstSplitPairSha256")
    ):
        raise RuntimeError(
            f"{case} second-position result is not bound to the first split"
        )
    kind = R2_SINGLE[case]["track"]
    source_uid = preparation["target"]["sourceUids"][kind]
    cut_start, cut_end = R2_SINGLE[case]["cutStart"], R2_SINGLE[case]["cutEnd"]
    start, end = CASES[case]["start"], CASES[case]["end"]
    first_right_uid = first_children[1]["GetUniqueId"]["value"]
    children = _single_children(
        reader._validate_read_pair(second_pair, probe)[0],
        case,
        source_uid,
        parent[kind].get("GetMarkers"),
        [
            (start, start + cut_start, 0, cut_start),
            (start + cut_start, start + cut_end, cut_start, cut_end),
            (start + cut_end, end, cut_end, 199),
        ],
        reader,
    )
    if (
        children[0]["GetUniqueId"]["value"] != parent[kind]["GetUniqueId"]["value"]
        or children[1]["GetUniqueId"]["value"] != first_right_uid
    ):
        raise RuntimeError(f"{case} split child UID lineage changed")
    prior_uids = {
        item["GetUniqueId"]["value"]
        for t in first_state["timelines"]
        for tr in t.get("tracks", [])
        for item in tr.get("items", [])
    }
    if children[2]["GetUniqueId"]["value"] in prior_uids:
        raise RuntimeError(f"{case} final split UID is not new")
    expected_state = _single_expected(
        first_state, case, first_right_uid, children[1:], first_children[1], reader
    )
    expected_state = _usage_delta(expected_state, {source_uid}, 1)
    expected_pool = _usage_delta(first_pool, {source_uid}, 1)
    second_state, second_pool = reader._validate_read_pair(second_pair, probe)
    if expected_state != second_state or expected_pool != second_pool:
        raise RuntimeError(
            f"{case} second split changed unrelated state or source Usage"
        )
    interval = children[1]
    interval_uid = interval["GetUniqueId"]["value"]
    timeline = _context(resolve, config, identity, probe, reader)
    live, live_state, live_pool = _read(
        reader, resolve, config, identity, sources, probe
    )
    target_tc = _timecode(start + cut_end)
    if (
        live_state != second_state
        or live_pool != second_pool
        or timeline.GetCurrentTimecode() != target_tc
    ):
        raise RuntimeError(f"Fresh {case} interval state/source/playhead differs")
    handle = _native_item(timeline, kind, interval_uid, source_uid)
    directory, journal = _evidence_dir(output)
    reader._write(directory / "before.json", live)
    _append(journal, "FullReadback", "before", {"path": "before.json"})
    result = {
        "status": "interval-delete-review-required",
        "case": case,
        "directory": str(directory),
        "journal": str(journal),
        "intervalUid": interval_uid,
        "sourceUid": source_uid,
        "interval": {
            "recordStart": start + cut_start,
            "recordEnd": start + cut_end,
            "sourceStart": cut_start,
            "sourceEnd": cut_end,
        },
        "deleteReturn": None,
        "deleteError": None,
        "saveDispatched": False,
    }
    _append(
        journal,
        "Timeline.DeleteClips",
        "request",
        {"uids": [interval_uid], "ripple": False},
    )
    try:
        result["deleteReturn"] = timeline.DeleteClips([handle], False)
        _append(journal, "Timeline.DeleteClips", "return", result["deleteReturn"])
    except Exception as error:
        result["deleteError"] = f"{type(error).__name__}: {error}"
        _append(journal, "Timeline.DeleteClips", "failure", result["deleteError"])
    try:
        after, after_state, after_pool = _read(
            reader, resolve, config, identity, sources, probe
        )
        reader._write(directory / "after.json", after)
        expected_state = deepcopy(second_state)
        track = _track(_timeline(expected_state, reader), kind, 1)
        track["items"] = [
            item
            for item in track["items"]
            if item["GetUniqueId"]["value"] != interval_uid
        ]
        expected_state = _usage_delta(expected_state, {source_uid}, -1)
        expected_pool = _usage_delta(second_pool, {source_uid}, -1)
        if (
            result["deleteReturn"] is True
            and result["deleteError"] is None
            and after_state == expected_state
            and after_pool == expected_pool
        ):
            result["status"] = "interval-deleted-unsaved"
        else:
            result["postflightFailure"] = (
                "Postflight differs from exact single-track interval removal"
            )
        result["afterPair"] = {
            "path": str(directory.relative_to(output) / "after.json"),
            "sha256": probe.sha256(directory / "after.json"),
        }
    except Exception as error:
        result["postflightFailure"] = f"{type(error).__name__}: {error}"
        _append(
            journal, "FullReadback", "postflight-failure", result["postflightFailure"]
        )
    reader._write(directory / "result.json", result)
    return result


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
        initial_state, initial_pool = reader._validate_read_pair(before, probe)
        for method, target, call, readback in operations:
            _context(
                resolve,
                config,
                identity,
                probe,
                reader,
                page=None if method == "OpenPage" else "edit",
            )
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
            expected_readback = (
                True
                if method == "AddMarker"
                else target.get(
                    "locked",
                    target.get(
                        "timecode",
                        target.get(
                            "page",
                            target.get(
                                "unlinked",
                                target.get("linked", target.get("enabled")),
                            ),
                        ),
                    ),
                )
            )
            if readback() != expected_readback:
                raise RuntimeError(f"{method} did not read back")
            if method == "OpenPage":
                _, page_state, page_pool = _read(
                    reader, resolve, config, identity, sources, probe
                )
                if page_state != initial_state or page_pool != initial_pool:
                    raise RuntimeError(
                        "Edit page switch changed full timeline/source state"
                    )
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


def _native_item(timeline, kind, uid, source_uid):
    rows = timeline.GetItemListInTrack(kind, 1)
    matches = [item for item in rows or [] if item.GetUniqueId() == uid]
    if len(matches) != 1 or matches[0].GetMediaPoolItem().GetUniqueId() != source_uid:
        raise RuntimeError(f"Exact {kind} occurrence handle changed")
    return matches[0]


def _native_track_item(timeline, kind, index, uid, source_uid):
    rows = timeline.GetItemListInTrack(kind, index)
    matches = [item for item in rows or [] if item.GetUniqueId() == uid]
    if len(matches) != 1 or matches[0].GetMediaPoolItem().GetUniqueId() != source_uid:
        raise RuntimeError(f"Exact {kind}{index} occurrence handle changed")
    return matches[0]


def _target_boundary_a3(state, reader):
    item = _marked_item(state, reader, "audio", 3, "R3-boundary")
    source = item.get("GetMediaPoolItem", {})
    if (
        source.get("GetUniqueId", {}).get("value")
        != "0438f3a0-b58f-4d6f-a36d-81e02cdeaf3f"
        or source.get("GetName", {}).get("value") != "bed.wav"
        or item.get("GetStart") != {"value": 9000}
        or item.get("GetEnd") != {"value": 9199}
        or item.get("GetSourceStartFrame") != {"value": 0}
        or item.get("GetSourceEndFrame") != {"value": 199}
        or item.get("GetClipEnabled") != {"value": True}
        or item.get("GetLinkedItems") != []
        or _track(_timeline(state, reader), "audio", 3).get("GetIsTrackEnabled")
        != {"value": True}
    ):
        raise RuntimeError("Exact enabled R3-boundary A3 crossing bed changed")
    return item


def _boundary_marker_value():
    return {
        "color": "Blue",
        "duration": 1,
        "name": "141 R3 exact section boundary",
        "note": "Synthetic authored boundary at local frame 100",
        "customData": json.dumps(
            {"issue": 141, "section": "R3-boundary", "boundaryLocalFrame": 100},
            sort_keys=True,
        ),
    }


def _boundary_marker(state, reader):
    markers = _timeline(state, reader).get("GetMarkers", {}).get("value", {})
    if markers.get("9100") != _boundary_marker_value():
        raise RuntimeError(
            "Exact authored R3-boundary marker at frame 9100 is required"
        )
    return markers["9100"]


def _base_boundary_split(reader, output, config, probe):
    result = _pin(
        reader,
        output,
        config.get("baseSplitResult"),
        config.get("baseSplitResultSha256"),
        probe,
    )
    if (
        result.get("status") != "split-readback-retained"
        or result.get("case") != "R3-boundary"
        or result.get("ranges") != [[9000, 9100, 0, 100], [9100, 9199, 100, 199]]
    ):
        raise RuntimeError("Pinned preceding R3-boundary base split review is required")
    prep_ref = result.get("preparationResult", {})
    base_prep = _pin(
        reader, output, prep_ref.get("path"), prep_ref.get("sha256"), probe
    )
    if (
        base_prep.get("status") != "case-prepared"
        or base_prep.get("case") != "R3-boundary"
    ):
        raise RuntimeError("Preceding base split preparation pin changed")
    _, _, before, before_pool = _prepared_state(reader, output, base_prep, probe)
    split_ref = result.get("splitPair", {})
    pair = _r2_pin(
        reader,
        output,
        split_ref.get("path"),
        split_ref.get("sha256"),
        probe,
        "R3-boundary base split pair",
    )
    state, pool = reader._validate_read_pair(pair, probe)
    children = _named_linked_children(
        base_prep, before, before_pool, state, pool, reader, "R3-boundary", "first"
    )
    actual_uids = {
        kind: [item["GetUniqueId"]["value"] for item in rows]
        for kind, rows in children.items()
    }
    if result.get("childUids") != actual_uids:
        raise RuntimeError("Pinned R3-boundary base split child UIDs changed")
    _boundary_marker(state, reader)
    return result, base_prep, pair, state, pool


def _verify_a3_base_binding(reader, output, config, probe, preparation, state, pool):
    result, base_preparation, _, base_state, base_pool = _base_boundary_split(
        reader, output, config, probe
    )
    target = preparation.get("target", {})
    if target.get("baseSplitResult", {}).get("sha256") != config.get(
        "baseSplitResultSha256"
    ) or target.get("baseRestoreResult", {}).get("sha256") != config.get(
        "baseRestoreResultSha256"
    ):
        raise RuntimeError("A3 preparation is not bound to its preceding base split")
    expected = deepcopy(base_state)
    original_locks = base_preparation.get("originalLocks", {})
    for kind, index in base_preparation.get("protectedTracks", []):
        value = original_locks.get(f"{kind}:{index}")
        if not isinstance(value, bool):
            raise RuntimeError("Base-split original lock state is unreadable")
        _track(_timeline(expected, reader), kind, index)["GetIsTrackLocked"] = {
            "value": value
        }
    for kind, index in preparation.get("protectedTracks", []):
        _track(_timeline(expected, reader), kind, index)["GetIsTrackLocked"] = {
            "value": True
        }
    if state != expected or pool != base_pool:
        raise RuntimeError("A3 prepared state differs from the pinned base split")
    _boundary_marker(state, reader)
    return result


def prepare_boundary_a3(resolve, config, *, probe, reader=None):
    reader = reader or _reader(probe)
    case = "R3-boundary-A3"
    output, sources, identity = _base(resolve, config, probe, reader, case)
    pin = _pin(
        reader, output, config.get("priorPair"), config.get("priorPairSha256"), probe
    )
    before_state, before_pool = reader._validate_read_pair(pin, probe)
    base_result, base_preparation, _, base_state, base_pool = _base_boundary_split(
        reader, output, config, probe
    )
    restore_result = _pin(
        reader,
        output,
        config.get("baseRestoreResult"),
        config.get("baseRestoreResultSha256"),
        probe,
    )
    restored_ref = restore_result.get("restoredPair", {})
    restored_pair = _r2_pin(
        reader,
        output,
        restored_ref.get("path"),
        restored_ref.get("sha256"),
        probe,
        "R3-boundary post-restore pair",
    )
    restored_state, restored_pool = reader._validate_read_pair(restored_pair, probe)
    expected_restored = deepcopy(base_state)
    original_locks = base_preparation.get("originalLocks", {})
    for kind, index in base_preparation.get("protectedTracks", []):
        value = original_locks.get(f"{kind}:{index}")
        if not isinstance(value, bool):
            raise RuntimeError("Preceding R3-boundary original locks are unreadable")
        _track(_timeline(expected_restored, reader), kind, index)[
            "GetIsTrackLocked"
        ] = {"value": value}
    if (
        restore_result.get("status") != "restored-unsaved"
        or restore_result.get("case") != "R3-boundary"
        or restore_result.get("preparationResult", {}).get("sha256")
        != base_result.get("preparationResult", {}).get("sha256")
        or restore_result.get("postEditPair", {}).get("sha256")
        != base_result.get("splitPair", {}).get("sha256")
        or restore_result.get("originalPlayhead")
        != base_preparation.get("originalPlayhead")
        or config.get("priorPairSha256") != restored_ref.get("sha256")
        or restored_state != expected_restored
        or restored_pool != base_pool
    ):
        raise RuntimeError("A3 preparation must follow the exact restored base split")
    _boundary_marker(before_state, reader)
    if (
        pin.get("selectedTimelineUid") != MATRIX_UID
        or before_state.get("projectId") != PROJECT_ID
        or before_state.get("projectName") != config["projectName"]
    ):
        raise RuntimeError("Pinned readback does not bind the selected Matrix")
    matrix = _timeline(before_state, reader)
    item = _target_boundary_a3(before_state, reader)
    if (
        float(
            matrix.get("GetSettings", {}).get("value", {}).get("timelineFrameRate", 0)
        )
        != FRAME_RATE
    ):
        raise RuntimeError("R3-boundary A3 requires the 25 fps Matrix")
    original_locks = {}
    for kind, index in ALL_LOCKS:
        locked = _track(matrix, kind, index).get("GetIsTrackLocked", {}).get("value")
        if not isinstance(locked, bool):
            raise RuntimeError("Pinned track-lock state is unreadable")
        original_locks[f"{kind}:{index}"] = locked
    if any(original_locks.values()):
        raise RuntimeError("A3 preparation requires the unlocked Matrix")
    timeline = _context(resolve, config, identity, probe, reader, page=None)
    original_playhead = timeline.GetCurrentTimecode()
    original_page = resolve.GetCurrentPage()
    if original_page not in {"edit", "deliver"} or not original_playhead:
        raise RuntimeError("A3 preparation page/playhead is unreadable")
    current, state, pool = _read(reader, resolve, config, identity, sources, probe)
    if state != before_state or pool != before_pool:
        raise RuntimeError("Fresh state/source evidence differs from prior pin")

    protected = [row for row in ALL_LOCKS if row != ("audio", 3)]
    expected = deepcopy(state)
    expected_matrix = _timeline(expected, reader)
    timeline = _context(resolve, config, identity, probe, reader, page=None)
    operations = [
        (
            "SetTrackLock",
            {"trackType": kind, "trackIndex": index, "locked": True},
            lambda kind=kind, index=index: timeline.SetTrackLock(kind, index, True),
            lambda kind=kind, index=index: timeline.GetIsTrackLocked(kind, index),
        )
        for kind, index in protected
    ]
    for kind, index in protected:
        _track(expected_matrix, kind, index)["GetIsTrackLocked"] = {"value": True}
    if original_page == "deliver":
        operations.insert(
            0,
            (
                "OpenPage",
                {"page": "edit"},
                lambda: resolve.OpenPage("edit"),
                resolve.GetCurrentPage,
            ),
        )
    target_timecode = _timecode(9100)
    operations.append(
        (
            "SetCurrentTimecode",
            {"timecode": target_timecode},
            lambda: timeline.SetCurrentTimecode(target_timecode),
            timeline.GetCurrentTimecode,
        )
    )
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
        target_timecode,
        {
            "priorPair": {
                "path": config["priorPair"],
                "sha256": config["priorPairSha256"],
            },
            "originalLocks": original_locks,
            "originalPlayhead": original_playhead,
            "target": {
                "uid": item["GetUniqueId"]["value"],
                "sourceUid": item["GetMediaPoolItem"]["GetUniqueId"]["value"],
                "track": ["audio", 3],
                "startFrame": 9000,
                "endFrame": 9199,
                "splitPlayheadFrame": 9100,
                "splitPlayheadTimecode": target_timecode,
                "frameRate": FRAME_RATE,
                "baseSplitResult": {
                    "path": config["baseSplitResult"],
                    "sha256": config["baseSplitResultSha256"],
                },
                "baseRestoreResult": {
                    "path": config["baseRestoreResult"],
                    "sha256": config["baseRestoreResultSha256"],
                },
            },
            "protectedTracks": [list(row) for row in protected],
            "menuCommandDispatched": False,
            "originalPage": original_page,
        },
        "case-prepared",
        "preparedPair",
    )


def boundary_a3_split_review(resolve, config, *, probe, reader=None):
    reader = reader or _reader(probe)
    case = "R3-boundary-A3"
    output, sources, identity = _base(resolve, config, probe, reader, case)
    preparation = _pin(
        reader,
        output,
        config.get("preparationResult"),
        config.get("preparationResultSha256"),
        probe,
    )
    _, _, prepared_state, prepared_pool = _prepared_state(
        reader, output, preparation, probe
    )
    _verify_a3_base_binding(
        reader, output, config, probe, preparation, prepared_state, prepared_pool
    )
    parent = _target_boundary_a3(prepared_state, reader)
    uid = preparation.get("target", {}).get("uid")
    source_uid = preparation.get("target", {}).get("sourceUid")
    if (
        preparation.get("case") != case
        or preparation.get("status") != "case-prepared"
        or parent.get("GetUniqueId", {}).get("value") != uid
        or parent.get("GetMediaPoolItem", {}).get("GetUniqueId", {}).get("value")
        != source_uid
    ):
        raise RuntimeError("R3-boundary A3 preparation/source binding changed")
    prepared_ref = preparation.get("preparedPair", {})
    prepared_pair = _pin(
        reader,
        output,
        prepared_ref.get("path"),
        prepared_ref.get("sha256"),
        probe,
    )
    _selected_uids(
        reader,
        output,
        probe,
        config,
        prepared_pair,
        prepared_ref.get("sha256"),
        "r3-boundary-a3-selected",
        [("audio", 3, uid, source_uid, [])],
    )
    split_pair = _r2_pin(
        reader,
        output,
        config.get("splitPair"),
        config.get("splitPairSha256"),
        probe,
        "R3-boundary A3 split pair",
    )
    split_state, split_pool = reader._validate_read_pair(split_pair, probe)
    ranges = [(9000, 9100, 0, 100), (9100, 9199, 100, 199)]
    track = _track(_timeline(split_state, reader), "audio", 3)
    candidates = [
        item
        for item in track.get("items", [])
        if item.get("GetMediaPoolItem", {}).get("GetUniqueId", {}).get("value")
        == source_uid
        and 9000 <= item.get("GetStart", {}).get("value", -1) <= 9199
    ]
    actual_ranges = [
        (
            item.get("GetStart", {}).get("value"),
            item.get("GetEnd", {}).get("value"),
            item.get("GetSourceStartFrame", {}).get("value"),
            item.get("GetSourceEndFrame", {}).get("value"),
        )
        for item in candidates
    ]
    if sorted(actual_ranges) != ranges or len(candidates) != 2:
        raise RuntimeError("R3-boundary A3 child ranges changed")
    by_range = dict(zip(actual_ranges, candidates, strict=True))
    if len(by_range) != 2:
        raise RuntimeError("R3-boundary A3 child range is duplicated")
    children = [by_range[row] for row in ranges]
    if any(
        child.get("GetMarkers") != parent.get("GetMarkers")
        or child.get("GetLinkedItems") != []
        for child in children
    ):
        raise RuntimeError("R3-boundary A3 child marker/link changed")
    all_before_uids = {
        item["GetUniqueId"]["value"]
        for timeline in prepared_state["timelines"]
        for track_row in timeline.get("tracks", [])
        for item in track_row.get("items", [])
    }
    if (
        children[0].get("GetUniqueId", {}).get("value") != uid
        or children[1].get("GetUniqueId", {}).get("value") in all_before_uids
    ):
        raise RuntimeError("R3-boundary A3 split UID lineage changed")
    expected = deepcopy(prepared_state)
    items = _track(_timeline(expected, reader), "audio", 3)["items"]
    items[:] = [
        item for item in items if item.get("GetUniqueId", {}).get("value") != uid
    ]
    items.extend(
        _razor_child(parent, child, *bounds)
        for child, bounds in zip(children, ranges, strict=True)
    )
    items.sort(key=lambda item: json.dumps(item["GetUniqueId"], sort_keys=True))
    expected = _usage_delta(expected, {source_uid}, 1)
    expected_pool = _usage_delta(prepared_pool, {source_uid}, 1)
    if expected != split_state or expected_pool != split_pool:
        raise RuntimeError("R3-boundary A3 split changed unrelated state or Usage")
    _, live_state, live_pool = _read(reader, resolve, config, identity, sources, probe)
    timeline = _context(resolve, config, identity, probe, reader)
    if (
        live_state != split_state
        or live_pool != split_pool
        or timeline.GetCurrentTimecode() != _timecode(9100)
    ):
        raise RuntimeError("Fresh R3-boundary A3 split state/source/playhead differs")
    return {
        "status": "split-readback-retained",
        "case": case,
        "preparationResult": {
            "path": config["preparationResult"],
            "sha256": config["preparationResultSha256"],
        },
        "selectionResult": {
            "path": config["selectionResult"],
            "sha256": config["selectionResultSha256"],
        },
        "splitPair": {"path": config["splitPair"], "sha256": config["splitPairSha256"]},
        "childUids": [child["GetUniqueId"]["value"] for child in children],
        "ranges": [list(row) for row in ranges],
        "menuCommandDispatched": False,
        "saveDispatched": False,
    }


def boundary_a3_split_ready(resolve, config, *, probe, reader=None):
    reader = reader or _reader(probe)
    case = "R3-boundary-A3"
    output, sources, identity = _base(resolve, config, probe, reader, case)
    preparation = _pin(
        reader,
        output,
        config.get("preparationResult"),
        config.get("preparationResultSha256"),
        probe,
    )
    _, _, prepared_state, prepared_pool = _prepared_state(
        reader, output, preparation, probe
    )
    _verify_a3_base_binding(
        reader, output, config, probe, preparation, prepared_state, prepared_pool
    )
    if preparation.get("status") != "case-prepared" or preparation.get("case") != case:
        raise RuntimeError("Exact R3-boundary A3 preparation result is required")
    uid, source_uid = (
        preparation.get("target", {}).get("uid"),
        preparation.get("target", {}).get("sourceUid"),
    )
    prepared_ref = preparation.get("preparedPair", {})
    pair = _pin(
        reader, output, prepared_ref.get("path"), prepared_ref.get("sha256"), probe
    )
    _selected_uids(
        reader,
        output,
        probe,
        config,
        pair,
        prepared_ref.get("sha256"),
        "r3-boundary-a3-selected",
        [("audio", 3, uid, source_uid, [])],
    )
    _, live_state, live_pool = _read(reader, resolve, config, identity, sources, probe)
    timeline = _context(resolve, config, identity, probe, reader)
    if (
        live_state != prepared_state
        or live_pool != prepared_pool
        or timeline.GetCurrentTimecode() != _timecode(9100)
    ):
        raise RuntimeError("Fresh R3-boundary A3 split-ready state or playhead changed")
    return {
        "status": "split-ready",
        "case": case,
        "stage": "first",
        "selectionResult": {
            "path": config.get("selectionResult"),
            "sha256": config.get("selectionResultSha256"),
        },
        "selectionLabel": "r3-boundary-a3-selected",
        "selectedUids": [uid],
        "splitFrame": 9100,
        "menuCommandDispatched": False,
    }


def prepare(resolve, config, *, probe, reader=None):
    reader = reader or _reader(probe)
    case = config.get("case")
    if case == "R3-boundary-A3":
        return prepare_boundary_a3(resolve, config, probe=probe, reader=reader)
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
    if case == "R2-residual":
        residual = _marked_item(before_state, reader, "audio", 2, case)
        if residual.get("GetClipEnabled") != {"value": False} or _track(
            matrix, "audio", 2
        ).get("GetIsTrackEnabled") != {"value": True}:
            raise RuntimeError("R2-residual A2 must be disabled on an enabled track")
    elif case == "R3-Graphic":
        graphic = _marked_item(before_state, reader, "video", 3, case)
        if graphic.get("GetClipEnabled") != {"value": False}:
            raise RuntimeError("R3-Graphic clip must be disabled before preparation")
        if _track(matrix, "video", 3).get("GetIsTrackEnabled") != {"value": True}:
            raise RuntimeError("R3-Graphic V3 track must be enabled before preparation")
    elif case == "R3-boundary":
        _target_boundary_a3(before_state, reader)
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
        resolve, config, identity, probe, reader, page=None
    ).GetCurrentTimecode()
    original_page = resolve.GetCurrentPage()
    if original_page not in {"edit", "deliver"}:
        raise RuntimeError("Editorial preparation requires Edit or Deliver page")
    if not isinstance(original_playhead, str) or not original_playhead:
        raise RuntimeError("Original Matrix playhead is unreadable")
    current, state, pool = _read(reader, resolve, config, identity, sources, probe)
    if state != before_state or pool != before_pool:
        raise RuntimeError(
            "Fresh complete state/source evidence differs from prior pin"
        )

    if case in R2_SINGLE:
        local = R2_SINGLE[case].get("cutStart", R2_SINGLE[case].get("selection"))
        frame, playhead_label = (
            start + local,
            ("splitPlayhead" if case != "R2-offset" else "selection"),
        )
    elif case == "R1-trim":
        frame, playhead_label = end - 25, "trimPlayhead"
    elif case == "R2-linked":
        frame, playhead_label = start + 60, "splitPlayhead"
    elif case in R2_LINKED_SPLITS:
        frame, playhead_label = start + R2_LINKED_SPLITS[case][0], "splitPlayhead"
    else:
        frame, playhead_label = start + 100, "selection"
    tc = _timecode(frame)
    expected = deepcopy(state)
    expected_matrix = _timeline(expected, reader)
    target_track = R2_SINGLE.get(case, {}).get("track")
    protected = (
        [row for row in ALL_LOCKS if row != (target_track, 1)]
        if target_track
        else list(LOCKS)
    )
    timeline = _context(resolve, config, identity, probe, reader, page=None)
    operations = []
    enabled_clip_rows = []
    if case in {"R2-residual", "R3-Graphic"}:
        layer = (
            _marked_item(before_state, reader, "audio", 2, case)
            if case == "R2-residual"
            else _marked_item(before_state, reader, "video", 3, case)
        )
        kind, index = ("audio", 2) if case == "R2-residual" else ("video", 3)
        uid = layer["GetUniqueId"]["value"]
        source_uid = layer["GetMediaPoolItem"]["GetUniqueId"]["value"]
        handle = _native_track_item(timeline, kind, index, uid, source_uid)
        operations.append(
            (
                "SetClipEnabled",
                {"trackType": kind, "trackIndex": index, "uid": uid, "enabled": True},
                lambda handle=handle: handle.SetClipEnabled(True),
                lambda handle=handle: handle.GetClipEnabled(),
            )
        )
        expected_layer = _marked_item(expected, reader, kind, index, case)
        expected_layer["GetClipEnabled"] = {"value": True}
        enabled_clip_rows.append(
            {"kind": kind, "index": index, "uid": uid, "section": case, "enabled": True}
        )
    added_marker = None
    if case == "R3-boundary":
        frame = 9100
        marker_value = {
            "color": "Blue",
            "duration": 1,
            "name": "141 R3 exact section boundary",
            "note": "Synthetic authored boundary at local frame 100",
            "customData": json.dumps(
                {"issue": 141, "section": "R3-boundary", "boundaryLocalFrame": 100},
                sort_keys=True,
            ),
        }
        marker_map = matrix.get("GetMarkers", {}).get("value", {})
        if str(frame) in marker_map:
            raise RuntimeError("R3-boundary frame 9100 marker must be absent initially")
        expected_markers = _timeline(expected, reader).setdefault(
            "GetMarkers", {"value": {}}
        )["value"]
        if str(frame) in expected_markers:
            raise RuntimeError("R3-boundary frame 9100 marker must be absent initially")
        expected_markers[str(frame)] = deepcopy(marker_value)
        added_marker = {"frame": frame, "value": marker_value}
        operations.append(
            (
                "AddMarker",
                {
                    "frame": frame,
                    "color": "Blue",
                    "name": marker_value["name"],
                    "note": marker_value["note"],
                    "duration": 1,
                    "custom": marker_value["customData"],
                    "marker": marker_value,
                },
                lambda timeline=timeline: timeline.AddMarker(
                    frame,
                    "Blue",
                    marker_value["name"],
                    marker_value["note"],
                    1,
                    marker_value["customData"],
                ),
                lambda timeline=timeline: (
                    timeline.GetMarkers().get(str(frame)) == marker_value
                ),
            )
        )
    if target_track:
        handles = [
            _native_item(
                timeline,
                kind,
                items[kind]["GetUniqueId"]["value"],
                items[kind]
                .get("GetMediaPoolItem", {})
                .get("GetUniqueId", {})
                .get("value"),
            )
            for kind in ("video", "audio")
        ]
        operations.append(
            (
                "SetClipsLinked",
                {
                    "uids": [item.GetUniqueId() for item in handles],
                    "linked": False,
                    "unlinked": True,
                },
                lambda timeline=timeline, handles=handles: timeline.SetClipsLinked(
                    handles, False
                ),
                lambda handles=handles: all(
                    not item.GetLinkedItems() for item in handles
                ),
            )
        )
        for kind in ("video", "audio"):
            track = _track(expected_matrix, kind, 1)
            item_uid = items[kind]["GetUniqueId"]["value"]
            next(
                row for row in track["items"] if row["GetUniqueId"]["value"] == item_uid
            )["GetLinkedItems"] = []
    for kind, index in protected:
        _track(expected_matrix, kind, index)["GetIsTrackLocked"] = {"value": True}
    operations.extend(
        [
            (
                "SetTrackLock",
                {"trackType": kind, "trackIndex": index, "locked": True},
                lambda kind=kind, index=index, timeline=timeline: timeline.SetTrackLock(
                    kind, index, True
                ),
                lambda kind=kind, index=index, timeline=timeline: (
                    timeline.GetIsTrackLocked(kind, index)
                ),
            )
            for kind, index in protected
        ]
    )
    if original_page == "deliver":
        operations.insert(
            0,
            (
                "OpenPage",
                {"page": "edit"},
                lambda: resolve.OpenPage("edit"),
                resolve.GetCurrentPage,
            ),
        )
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
            **(
                {"targetTrack": target_track, "unlinkPrepared": True}
                if target_track
                else {}
            ),
            **({"enabledClips": enabled_clip_rows} if enabled_clip_rows else {}),
            **({"addedMarker": added_marker} if added_marker else {}),
        },
        "protectedTracks": [list(row) for row in protected],
        "menuCommandDispatched": False,
        "originalPage": original_page,
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
        or not selection_pair_path.resolve().is_relative_to(output.resolve())
    ):
        raise RuntimeError(
            "Selected-item readback is not bound to the pinned post-copy pair"
        )
    selected_pair = _pin(
        reader,
        output,
        str(selection_pair_path.relative_to(output)),
        selection_pair["sha256"],
        probe,
    )
    if selected_pair != post_copy:
        raise RuntimeError("Selected-item full pair differs from post-copy evidence")
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
    protected = preparation.get("protectedTracks", [list(row) for row in LOCKS])
    for kind, index in protected:
        if _track(_timeline(state, reader), kind, index).get("GetIsTrackLocked") != {
            "value": True
        }:
            raise RuntimeError("Protected editorial tracks are not all locked")
    timeline = _context(resolve, config, identity, probe, reader)
    live, live_state, live_pool = _read(
        reader, resolve, config, identity, sources, probe
    )
    position = None
    if config.get("secondPositionResult") is not None:
        position = _pin(
            reader,
            output,
            config.get("secondPositionResult"),
            config.get("secondPositionResultSha256"),
            probe,
        )
        if (
            case not in {"R2-linked", *R2_SINGLE}
            or position.get("status") != "second-position-ready"
            or position.get("case") != case
            or position.get("target", {}).get("splitFrame")
            != (
                2570
                if case == "R2-linked"
                else CASES[case]["start"] + R2_SINGLE[case]["cutEnd"]
            )
            or position.get("target", {}).get("timecode")
            != _timecode(position["target"]["splitFrame"])
            or position.get("preparationResult", {}).get("sha256")
            != config.get("preparationResultSha256")
            or position.get("firstSplitPair", {}).get("sha256")
            != config.get("firstSplitPairSha256")
        ):
            raise RuntimeError("Hash-pinned R2 second-position result is invalid")
    if case == "R1-copy":
        target_tc = _timecode(CASES[case]["pasteStart"])
    elif position is not None:
        target_tc = position["target"]["timecode"]
    else:
        target_key = {
            "R1-trim": "trimPlayheadTimecode",
            "R2-linked": "splitPlayheadTimecode",
            "R2-residual": "splitPlayheadTimecode",
            "R3-Graphic": "splitPlayheadTimecode",
            "R3-boundary": "splitPlayheadTimecode",
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
    for kind, index in protected:
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
        for kind, index in protected
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
    if config.get("action") == "r3-boundary-a3-prepare":
        return prepare_boundary_a3(resolve, config, probe=probe)
    if config.get("action") == "r2-named-split-review":
        return named_split_review(resolve, config, probe=probe)
    if config.get("action") == "r2-named-split-ready":
        return named_split_ready(resolve, config, probe=probe)
    if config.get("action") == "r3-boundary-a3-split-review":
        return boundary_a3_split_review(resolve, config, probe=probe)
    if config.get("action") == "r3-boundary-a3-split-ready":
        return boundary_a3_split_ready(resolve, config, probe=probe)
    if config.get("action") == "editorial-case-restore":
        return restore(resolve, config, probe=probe)
    if config.get("action") == "editorial-copy-paste-position":
        return paste_position(resolve, config, probe=probe)
    if config.get("action") == "r2-linked-second-position":
        return second_position(resolve, config, probe=probe)
    if config.get("action") == "r2-linked-interval-delete":
        return interval_delete(resolve, config, probe=probe)
    raise RuntimeError("Only the fixed Issue 141 editorial actions are supported")
