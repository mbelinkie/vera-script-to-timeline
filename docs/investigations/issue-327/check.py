"""Run the disposable #327 finishing check through the installed Local SDK."""

import argparse
import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from vera_timeline_agent.build_timeline_once import (
    _external_resolve,
    exclusive_resolve_build,
)
from vera_timeline_agent.resolve_native_owner import (
    acquire_native_owner,
    preflight_independent_disposable,
    release_native_owner,
)

ARCHIVE = "327 - Archive"
CASES = {
    "same": "327 - Same length",
    "longer": "327 - Longer second row",
    "swap": "327 - Rows swapped",
}


@contextmanager
def idle_resolve(build_id: str) -> Iterator[None]:
    """Hold the shared lock and check the live slot for an independent project."""
    descriptor = acquire_native_owner()
    try:
        with exclusive_resolve_build():
            preflight_independent_disposable(f"VERA Delivery {build_id} 000000000000")
        yield
    finally:
        release_native_owner(descriptor)


def require(condition: Any, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def current(project: Any, timeline: Any) -> None:
    require(
        project.GetCurrentTimeline().GetUniqueId() == timeline.GetUniqueId(),
        "Resolve switched away from the expected timeline",
    )


def items(timeline: Any) -> list[tuple[str, int, Any]]:
    return [
        (kind, index, item)
        for kind in ("video", "audio", "subtitle")
        for index in range(1, timeline.GetTrackCount(kind) + 1)
        for item in timeline.GetItemListInTrack(kind, index)
    ]


def one(matches: list[Any], label: str) -> Any:
    require(len(matches) == 1, f"Expected one {label}, found {len(matches)}")
    return matches[0]


def snapshot(
    project: Any, timeline: Any, folder: Path, lut_type: Any
) -> dict[str, Any]:
    require(project.SetCurrentTimeline(timeline), "Could not select observation target")
    current(project, timeline)
    observed = []
    folder.mkdir()
    for kind, index, item in items(timeline):
        item_type = item.GetType()
        row = {
            "kind": kind,
            "track": index,
            "id": item.GetUniqueId(),
            "type": item_type,
            "name": item.GetName(),
            "start": item.GetStart(),
            "end": item.GetEnd(),
        }
        if item_type != "transition":
            media = item.GetMediaPoolItem()
            row.update(
                media=media.GetUniqueId() if media else None,
                sourceIn=item.GetSourceStartFrame(),
                sourceOut=item.GetSourceEndFrame(),
                markers=item.GetMarkers(),
            )
            if kind == "audio":
                properties = item.GetProperties() or {}
                row["volume"] = {
                    key: properties.get(key)
                    for key in ("AudioVolume", "AudioVolumeEnabled")
                }
            if kind == "video":
                graph = item.GetNodeGraph()
                row["colorNodes"] = (
                    [graph.GetNodeLabel(i) for i in range(1, graph.GetNumNodes() + 1)]
                    if graph
                    else None
                )
                cube = folder / f"{row['id']}.cube"
                if item.ExportLUT(lut_type, str(cube)) and cube.is_file():
                    # Exclude headers (which can include clip names).
                    values = [
                        line.split()
                        for line in cube.read_text().splitlines()
                        if line.strip() and line.lstrip()[0] in "+-.0123456789"
                    ]
                    row["lutSamples"] = (
                        hashlib.sha256(json.dumps(values).encode()).hexdigest()
                        if values
                        else None
                    )
                comp = (
                    item.GetFusionCompByIndex(1) if item.GetFusionCompCount() else None
                )
                row["blur"] = (
                    [
                        tool.GetInput("XBlurSize")
                        for tool in comp.GetToolList(False, "Blur").values()
                    ]
                    if comp
                    else []
                )
        observed.append(row)
    return {
        "timelineId": timeline.GetUniqueId(),
        "bounds": [timeline.GetStartFrame(), timeline.GetEndFrame()],
        "items": sorted(
            observed,
            key=lambda row: (row["kind"], row["track"], row["start"], row["id"]),
        ),
    }


def project_from_map(manager: Any, row_map: dict[str, Any]) -> Any:
    project = manager.GetCurrentProject()
    require(
        project and project.GetName() == row_map["projectName"],
        "Open the #327 disposable project",
    )
    require(
        project.GetUniqueId() == row_map["resolveProjectId"],
        "Resolve project identity differs",
    )
    require(not project.IsRenderingInProgress(), "Resolve has an active render")
    return project


def timeline_by_id(project: Any, uid: str) -> Any:
    timelines = [
        project.GetTimelineByIndex(i) for i in range(1, project.GetTimelineCount() + 1)
    ]
    return one(
        [timeline for timeline in timelines if timeline.GetUniqueId() == uid],
        "timeline UID",
    )


def duplicate(project: Any, source: Any, name: str) -> Any:
    require(project.SetCurrentTimeline(source), "Could not select duplicate source")
    copy = source.DuplicateTimeline(name)
    require(copy and copy.GetName() == name, f"Could not duplicate {name}")
    require(copy.GetUniqueId() != source.GetUniqueId(), "Duplicate reused source UID")
    require(project.SetCurrentTimeline(copy), "Could not select duplicate")
    current(project, copy)
    return copy


def append(project: Any, timeline: Any, plan: dict[str, Any], media: Any) -> None:
    current(project, timeline)
    placed = project.GetMediaPool().AppendToTimeline(
        [
            {
                "mediaPoolItem": media,
                "mediaType": 1 if plan["kind"] == "video" else 2,
                "trackIndex": plan["track"],
                "recordFrame": plan["start"],
                "startFrame": plan["sourceIn"],
                "endFrame": plan["sourceIn"] + plan["end"] - plan["start"],
            }
        ]
    )
    require(len(placed or []) == 1, "Append did not return one clip")


def plans(
    root: Path, row_map: dict[str, Any], variant: str
) -> dict[str, dict[str, Any]]:
    manifest = load(root / variant / "expected-manifest.json")
    paths = load(root / variant / "media-paths.json")
    rows = {item["eventId"]: item for row in row_map["rows"] for item in row["items"]}
    result = {}
    for event in manifest["events"]:
        if event["kind"] == "script_marker":
            continue
        event_id = event["eventId"]
        slot = rows[event_id]
        result[event_id] = {
            "kind": slot["trackKind"],
            "track": slot["trackIndex"],
            "start": event["recordRange"]["startFrame"],
            "end": event["recordRange"]["endFrame"],
            "sourceIn": (event["sourceRange"] or {"startFrame": 0})["startFrame"],
            "path": paths[f"source:{event['provenance']['sourceId']}"],
        }
    require(
        len(result) == 4 and result.keys() == rows.keys(),
        "Expected two picture and tone pairs",
    )
    return result


def run(root: Path, action: str, row_map: dict[str, Any]) -> None:
    with idle_resolve(row_map["buildId"]), exclusive_resolve_build():
        resolve = _external_resolve()
        require(
            resolve.IsStudio() and resolve.GetVersion()[:4] == [21, 1, 1, 10],
            "Expected Studio 21.1.1 build 10",
        )
        manager = resolve.GetProjectManager()
        lut_type = resolve.EXPORT_LUT_17PTCUBE
        project = project_from_map(manager, row_map)
        original = timeline_by_id(project, row_map["timelineId"])
        pool = project.GetMediaPool()
        if action == "setup":
            require(project.GetTimelineCount() == 1, "Expected one disposable timeline")
            require(not (root / "setup").exists(), "Setup was already attempted")
            (root / "setup").mkdir()
            require(project.SetCurrentTimeline(original), "Could not select original")
            log(
                root / "setup" / "ungraded.json",
                snapshot(project, original, root / "setup" / "ungraded", lut_type),
            )
            require(
                len(pool.ImportMedia([str(root / "media" / "Spare.mp4")]) or []) == 1,
                "Could not import spare clip",
            )
            require(manager.SaveProject(), "Could not save spare clip import")
            print(f"Ready for hand finishing in {project.GetName()}")
            print(f"Timeline: {original.GetName()}")
            return

        result = root / "native"
        require(
            project.GetTimelineCount() == 1,
            "Expected only the finished original timeline",
        )
        require((root / "setup").is_dir(), "Setup has not run")
        result.mkdir()
        before = snapshot(project, original, result / "original", lut_type)
        log(result / "original.json", before)
        original_items = {
            item["eventId"]: one(
                [row for row in before["items"] if row["id"] == item["resolveItemId"]],
                "mapped original item",
            )
            for row in row_map["rows"]
            for item in row["items"]
        }
        initial_plan = plans(root, row_map, "original")
        for event_id, row in original_items.items():
            require(
                all(
                    row[key] == initial_plan[event_id][key]
                    for key in ("kind", "track", "start", "end", "sourceIn")
                ),
                "Hand finishing changed a mapped clip's geometry",
            )
        picture = one(
            [
                row
                for row in original_items.values()
                if row["kind"] == "video" and row["start"] == 0
            ],
            "first picture",
        )
        tone = one(
            [
                row
                for row in original_items.values()
                if row["kind"] == "audio" and row["start"] == 0
            ],
            "first tone",
        )
        ungraded = one(
            [
                row
                for row in load(root / "setup" / "ungraded.json")["items"]
                if row["id"] == picture["id"]
            ],
            "ungraded first picture",
        )
        require(
            picture.get("lutSamples")
            and ungraded.get("lutSamples")
            and picture["lutSamples"] != ungraded["lutSamples"],
            "The first picture needs a readable saturation grade",
        )
        require(picture["blur"], "The first picture needs a Fusion Blur")
        require(
            tone["volume"]["AudioVolume"] == -12,
            "The first tone needs a -12 dB Inspector level",
        )
        require(
            len(before["items"]) == 6,
            "Expected four mapped clips, one transition and one spare",
        )
        require(
            sum(row["type"] == "transition" for row in before["items"]) == 1,
            "Expected one hand transition",
        )
        one(
            [
                row
                for row in before["items"]
                if row["name"] == "Spare.mp4"
                and row["kind"] == "video"
                and row["track"] > 1
                and 0 <= row["start"] < row["end"] <= 96
            ],
            "hand-placed Spare clip on an upper track inside row 1",
        )
        require(manager.SaveProject(), "Could not save the finished original")
        archive = duplicate(project, original, ARCHIVE)
        archive_id = archive.GetUniqueId()
        archive_before = snapshot(project, archive, result / "archive-before", lut_type)
        log(result / "archive-before.json", archive_before)
        # Check each authored plan before changing a trial timeline.
        compiled_plans = {variant: plans(root, row_map, variant) for variant in CASES}
        for variant, name in CASES.items():
            trial = duplicate(project, original, name)
            trial_id = trial.GetUniqueId()
            expected = compiled_plans[variant]
            native_items = items(trial)
            matched = {
                event_id: one(
                    [
                        item
                        for kind, index, item in native_items
                        if item.GetType() != "transition"
                        and (kind, index, item.GetStart())
                        == (row["kind"], row["track"], row["start"])
                    ],
                    "duplicate row clip",
                )
                for event_id, row in original_items.items()
            }
            changed = {
                event_id: plan
                for event_id, plan in expected.items()
                if variant == "swap"
                or (
                    original_items[event_id]["start"] == 96
                    and (variant == "longer" or plan["kind"] == "video")
                )
            }
            media = {}
            for event_id, plan in expected.items():
                if original_items[event_id]["start"] == 96 and (
                    (variant == "same" and plan["kind"] == "video")
                    or (variant == "longer" and plan["kind"] == "audio")
                ):
                    current(project, trial)
                    media[event_id] = one(
                        pool.ImportMedia([plan["path"]]) or [], "imported replacement"
                    )
                else:
                    media[event_id] = matched[event_id].GetMediaPoolItem()
            media_ids = {
                event_id: item.GetUniqueId() for event_id, item in media.items()
            }
            log(
                result / f"{variant}-before.json",
                snapshot(project, trial, result / f"{variant}-before", lut_type),
            )
            current(project, trial)
            if variant == "same":
                event_id, plan = one(list(changed.items()), "same-length replacement")
                clip = matched[event_id]
                require(clip.GetTakesCount() == 0, "Expected no existing takes")
                require(
                    clip.AddTake(
                        media[event_id],
                        plan["sourceIn"],
                        plan["sourceIn"] + plan["end"] - plan["start"],
                    ),
                    "Could not add replacement take",
                )
                take = one(
                    [
                        index
                        for index in range(1, clip.GetTakesCount() + 1)
                        if clip.GetTakeByIndex(index)["mediaPoolItem"].GetUniqueId()
                        == media_ids[event_id]
                    ],
                    "replacement take",
                )
                require(
                    clip.SelectTakeByIndex(take), "Could not select replacement take"
                )
                require(clip.FinalizeTake(), "Could not finalize replacement take")
            else:
                require(
                    trial.DeleteClips([matched[key] for key in changed], False),
                    "Delete without ripple failed",
                )
                for event_id, plan in changed.items():
                    append(project, trial, plan, media[event_id])

            require(manager.SaveProject(), "Could not save trial")
            require(manager.CloseProject(project), "Could not close trial project")
            require(
                manager.LoadProject(row_map["projectName"]),
                "Could not reopen trial project",
            )
            project = project_from_map(manager, row_map)
            pool = project.GetMediaPool()
            original = timeline_by_id(project, row_map["timelineId"])
            trial = timeline_by_id(project, trial_id)
            after = snapshot(project, trial, result / f"{variant}-after", lut_type)
            log(result / f"{variant}-after.json", after)
            archive = timeline_by_id(project, archive_id)
            archive_after = snapshot(
                project, archive, result / f"{variant}-archive", lut_type
            )
            log(result / f"{variant}-archive.json", archive_after)
            require(
                archive_after == archive_before,
                "Archive observation differs after reopen",
            )
            for event_id, plan in expected.items():
                one(
                    [
                        row
                        for row in after["items"]
                        if row.get("media") == media_ids[event_id]
                        and all(
                            row[field] == plan[field]
                            for field in ("kind", "track", "start", "end", "sourceIn")
                        )
                    ],
                    f"reopened {variant} clip {event_id}",
                )
            print(f"{variant}: expected clip geometry and archive verified", flush=True)
        require(
            project.SetCurrentTimeline(original),
            "Could not return to the finished original",
        )


def log(path: Path, observation: dict[str, Any]) -> None:
    with path.open("x") as output:
        json.dump(observation, output, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("setup", "compare"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    run(root, args.action, load(root / "built" / "row-timeline-map.json"))
