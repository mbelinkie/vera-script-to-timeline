"""One-use, exact-target Resolve proof for static #600 Transform scale.

The script only connects to Resolve when passed ``--execute``. It refuses any
project, timeline, item, media, build, or prior-evidence mismatch. It captures
three positions per generated clip before/after/reopen, changes ZoomX/ZoomY
once, then saves and reopens the exact target. Pan/Tilt must remain centered.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

from vera_timeline_agent.resolve_native_owner import native_owner
from vera_timeline_agent.row_timeline_map import validate_saved_row_map
from vera_timeline_agent.workflow_package import sha256
from vera_timeline_agent.workflow_v2 import load_verified_package_v2

_SAMPLES = (0, 36, 71)
_TRANSFORMS = {"letterbox": 180 / 140, "pillarbox": 320 / 272}
_EXPECTED_NAMES = {
    "letterbox": "e4b5d7d3-6f6d-5f41-804c-5b7f338b6354.mp4",
    "pillarbox": "36db527b-49d0-55f9-844f-edd6dfae50a2.mp4",
}
_RESOLVE_MODULE_PATH = (
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Developer/Scripting/Modules"
)


def _read(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"required build artifact unavailable: {path}")
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"build artifact root is not an object: {path}")
    return value


def _require_plain(path: Path, *, exists: bool) -> Path:
    absolute = path.absolute()
    if any(part.is_symlink() for part in (absolute, *absolute.parents)):
        raise ValueError(f"symbolic-link path refused: {absolute}")
    if exists and not absolute.is_dir():
        raise ValueError(f"directory unavailable: {absolute}")
    if not exists and absolute.exists():
        raise ValueError(f"one-use evidence directory already exists: {absolute}")
    return absolute


def _digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"expected regular file: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _save_state(path: Path, state: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    if temporary.exists() or temporary.is_symlink():
        raise ValueError("evidence state temporary already exists")
    temporary.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n")
    temporary.replace(path)


def _build(build_dir: Path) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    attestation_path = build_dir / "v2-attestation.json"
    attestation = _read(attestation_path)
    verified = load_verified_package_v2(attestation_path, sha256(attestation_path))
    if verified.root != Path(attestation["packageDir"]):
        raise ValueError("attested package path differs from the build result")
    for filename, digest in attestation["files"].items():
        if (
            filename in {"timeline-manifest.json", "build-report.json"}
            and _digest(build_dir / filename) != digest
        ):
            raise ValueError(f"top-level build copy differs: {filename}")
    manifest = verified.manifest
    report = _read(build_dir / "build-report.json")
    view_path = verified.root / "Builds" / attestation["buildId"] / "delivery-view.json"
    view = _read(view_path)
    row_map = _read(build_dir / "row-timeline-map.json")
    validate_saved_row_map(manifest, view, row_map)
    if (
        attestation.get("status") != "ready_to_import"
        or report.get("status") != "ready"
        or report.get("buildId") != attestation.get("buildId")
        or row_map.get("buildId") != attestation.get("buildId")
        or row_map.get("projectName") != attestation.get("projectName")
        or row_map.get("timelineName") != attestation.get("timelineName")
        or len(manifest.get("events", [])) != 2
    ):
        raise ValueError("build artifacts do not describe the expected two-clip target")
    return verified, row_map, view


def _expected_items(
    build_dir: Path, verified: Any, row_map: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    manifest = verified.manifest
    build_id = verified.attestation["buildId"]
    package_build = verified.root / "Builds" / build_id
    media_by_source = {
        source["id"]: package_build.parent.parent
        / "Media"
        / "Resolved"
        / f"{source['id']}.mp4"
        for source in manifest["sources"]
    }
    event_by_id = {event["eventId"]: event for event in manifest["events"]}
    by_name: dict[str, dict[str, Any]] = {}
    for row in row_map["rows"]:
        for item in row["items"]:
            event = event_by_id[item["eventId"]]
            source_id = event["provenance"]["sourceId"]
            source_path = media_by_source[source_id]
            name = source_path.name
            if name not in _EXPECTED_NAMES.values() or name in by_name:
                raise ValueError("row map contains an unexpected/duplicate source")
            if (
                item["name"] != name
                or item["trackKind"] != "video"
                or item["trackIndex"] != 1
                or item["sourceStartFrame"] != 0
                or item["sourceEndFrame"] != 71
                or item["durationFrames"] != 72
            ):
                raise ValueError(
                    "row map differs from the pinned generated clip geometry"
                )
            expected_name = next(
                kind for kind, expected in _EXPECTED_NAMES.items() if expected == name
            )
            expected_hash = event["provenance"]["deliveredSourceHash"].removeprefix(
                "sha256:"
            )
            if _digest(source_path) != expected_hash:
                raise ValueError("packaged generated media hash differs from the event")
            by_name[expected_name] = {
                **item,
                "sourcePath": str(source_path.resolve()),
                "sourceSha256": expected_hash,
                "eventId": event["eventId"],
            }
    if set(by_name) != set(_EXPECTED_NAMES):
        raise ValueError("build does not contain exactly the expected clips")
    return by_name


def _timeline_items(timeline: Any) -> list[tuple[str, int, Any]]:
    result = []
    for kind in ("video", "audio", "subtitle"):
        count = timeline.GetTrackCount(kind)
        if type(count) is not int or count < 0:
            raise ValueError(f"{kind} track inventory is unreadable")
        for index in range(1, count + 1):
            items = timeline.GetItemListInTrack(kind, index)
            if not isinstance(items, (list, tuple)):
                raise ValueError(f"{kind} track {index} inventory is unreadable")
            for item in items:
                result.append((kind, index, item))
    return result


def _find_exact_items(
    timeline: Any, expected: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    all_items = _timeline_items(timeline)
    if len(all_items) != 2:
        raise ValueError("target timeline has unexpected or missing items")
    handles: dict[str, Any] = {}
    for name, row in expected.items():
        matches = [
            (kind, index, item)
            for kind, index, item in all_items
            if item.GetUniqueId() == row["resolveItemId"]
        ]
        if len(matches) != 1:
            raise ValueError(f"exact TimelineItem UID is absent or duplicated: {name}")
        kind, index, item = matches[0]
        media = item.GetMediaPoolItem()
        if media is None:
            raise ValueError(f"target item has no MediaPoolItem: {name}")
        clip_properties = media.GetClipProperty()
        actual_path = (
            clip_properties.get("File Path")
            if isinstance(clip_properties, dict)
            else None
        )
        if (
            kind != "video"
            or index != row["trackIndex"]
            or media.GetMediaId() != row["mediaId"]
            or not isinstance(actual_path, str)
            or Path(actual_path).resolve() != Path(row["sourcePath"])
            or _digest(Path(actual_path)) != row["sourceSha256"]
            or item.GetName() != row["name"]
            or item.GetStart(False) != row["startFrame"]
            or item.GetDuration(False) != row["durationFrames"]
            or item.GetSourceStartFrame() != row["sourceStartFrame"]
            or item.GetSourceEndFrame() != row["sourceEndFrame"]
        ):
            raise ValueError(
                f"target item differs from its saved row-map identity: {name}"
            )
        handles[name] = item
    return handles


def _property(item: Any, name: str) -> float:
    value = item.GetProperty(name)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"Transform property is unreadable: {name}")
    return float(value)


def _properties(items: dict[str, Any]) -> dict[str, dict[str, float]]:
    return {
        name: {key: _property(item, key) for key in ("ZoomX", "ZoomY", "Pan", "Tilt")}
        for name, item in items.items()
    }


def _matches(actual: float, expected: float) -> bool:
    return abs(actual - expected) <= 1e-6


def _timecode(frame: int) -> str:
    hours, frame = divmod(frame, 24 * 60 * 60)
    minutes, frame = divmod(frame, 24 * 60)
    seconds, frames = divmod(frame, 24)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def _still(project: Any, timeline: Any, target: Path, frame: int) -> dict[str, Any]:
    timecode = _timecode(frame)
    if timeline.SetCurrentTimecode(timecode) is not True:
        raise ValueError(f"Resolve refused timeline seek to {timecode}")
    if timeline.GetCurrentTimecode() != timecode:
        raise ValueError("timeline timecode readback differs from requested frame")
    if target.exists() or target.is_symlink():
        raise ValueError(f"frame evidence path already exists: {target}")
    if project.ExportCurrentFrameAsStill(str(target)) is not True:
        raise ValueError("Resolve refused current-frame still export")
    if not target.is_file() or target.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("frame export is not a regular PNG still")
    raw = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(target),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        check=True,
        capture_output=True,
        timeout=30,
    ).stdout
    width = int.from_bytes(target.read_bytes()[16:20], "big")
    height = int.from_bytes(target.read_bytes()[20:24], "big")
    if (width, height) != (1920, 1080) or len(raw) != width * height * 3:
        raise ValueError("exported still dimensions differ from the 1920x1080 timeline")
    kind = "letterbox" if frame < 72 else "pillarbox"
    if kind == "letterbox":
        pixels = [
            raw[(y * width + x) * 3 : (y * width + x) * 3 + 3]
            for y in range(0, 120, 4)
            for x in range(0, width, 8)
        ]
    else:
        pixels = [
            raw[(y * width + x) * 3 : (y * width + x) * 3 + 3]
            for y in range(0, height, 8)
            for x in range(0, 144, 4)
        ]
    mean_luma = sum(
        0.2126 * pixel[0] + 0.7152 * pixel[1] + 0.0722 * pixel[2] for pixel in pixels
    ) / len(pixels)
    return {
        "timelineFrame": frame,
        "timecode": timecode,
        "path": str(target),
        "sha256": _digest(target),
        "pixelSha256": hashlib.sha256(raw).hexdigest(),
        "size": [width, height],
        "barRegionMeanLuma": mean_luma,
    }


def _capture(
    phase: str,
    project: Any,
    timeline: Any,
    expected: dict[str, dict[str, Any]],
    evidence: Path,
) -> dict[str, list[dict[str, Any]]]:
    captured: dict[str, list[dict[str, Any]]] = {}
    for name, row in expected.items():
        if row["startFrame"] not in (0, 72):
            raise ValueError("saved clip start differs from the two-row fixture")
        points = [row["startFrame"] + offset for offset in _SAMPLES]
        captured[name] = [
            _still(
                project, timeline, evidence / f"{phase}-{name}-{frame:03d}.png", frame
            )
            for frame in points
        ]
    return captured


def _check_frames(
    baseline: dict[str, list[dict[str, Any]]],
    after: dict[str, list[dict[str, Any]]],
    reopened: dict[str, list[dict[str, Any]]],
) -> None:
    for name in _EXPECTED_NAMES:
        if not (len(baseline[name]) == len(after[name]) == len(reopened[name]) == 3):
            raise ValueError(f"incomplete frame evidence for {name}")
        for before, changed, loaded in zip(
            baseline[name], after[name], reopened[name], strict=True
        ):
            if changed["pixelSha256"] == before["pixelSha256"]:
                raise ValueError(f"Transform did not change decoded pixels: {name}")
            if loaded["pixelSha256"] != changed["pixelSha256"]:
                raise ValueError(f"decoded frame changed after reopen: {name}")
            if (
                before["barRegionMeanLuma"] > 35
                or changed["barRegionMeanLuma"] < before["barRegionMeanLuma"] + 20
            ):
                raise ValueError(f"generated bar region did not fill visibly: {name}")


def execute(build_dir: Path, evidence_dir: Path) -> Path:
    build_dir = _require_plain(build_dir, exists=True)
    evidence_dir = _require_plain(evidence_dir, exists=False)
    verified, row_map, _view = _build(build_dir)
    expected = _expected_items(build_dir, verified, row_map)
    if evidence_dir.resolve().is_relative_to(verified.root.resolve()):
        raise ValueError("evidence directory must be outside the verified package")

    state_path: Path | None = None
    state: dict[str, Any] | None = None
    try:
        with native_owner():
            import sys

            if sys.modules.get("DaVinciResolveScript") is None:
                sys.path.append(_RESOLVE_MODULE_PATH)
            import DaVinciResolveScript  # type: ignore[import-not-found]

            resolve = DaVinciResolveScript.scriptapp("Resolve")
            if (
                resolve is None
                or resolve.GetProductName() != "DaVinci Resolve Studio"
                or resolve.GetVersionString() != "21.2.0.6"
                or resolve.GetCurrentPage() != "edit"
            ):
                raise ValueError("qualified Resolve Studio application is unavailable")
            manager = resolve.GetProjectManager()
            project = manager.GetCurrentProject() if manager is not None else None
            if (
                project is None
                or project.GetName() != verified.attestation["projectName"]
                or project.GetUniqueId() != row_map["resolveProjectId"]
                or manager.GetProjectListInCurrentFolder().count(project.GetName()) != 1
                or project.GetTimelineCount() != 1
                or project.IsRenderingInProgress() is not False
                or project.GetRenderJobList() != []
            ):
                raise ValueError(
                    "current project is not the exact idle #600 build target"
                )
            timeline = project.GetCurrentTimeline()
            only_timeline = project.GetTimelineByIndex(1)
            if (
                timeline is None
                or only_timeline is None
                or timeline.GetUniqueId() != row_map["timelineId"]
                or only_timeline.GetUniqueId() != row_map["timelineId"]
                or timeline.GetName() != verified.attestation["timelineName"]
            ):
                raise ValueError("current timeline is not the exact attested target")
            items = _find_exact_items(timeline, expected)
            original_timecode = timeline.GetCurrentTimecode()
            baseline_properties = _properties(items)
            if any(
                not _matches(baseline_properties[name][key], value)
                for name in _EXPECTED_NAMES
                for key, value in {
                    "ZoomX": 1.0,
                    "ZoomY": 1.0,
                    "Pan": 0.0,
                    "Tilt": 0.0,
                }.items()
            ):
                raise ValueError(
                    "target Transform no longer has its clean build defaults"
                )

            evidence_dir.mkdir(parents=True, exist_ok=False)
            state_path = evidence_dir / "state.json"
            state = {
                "status": "reserved",
                "buildId": verified.attestation["buildId"],
                "projectName": project.GetName(),
                "projectId": project.GetUniqueId(),
                "timelineName": timeline.GetName(),
                "timelineId": timeline.GetUniqueId(),
                "resolveVersion": resolve.GetVersionString(),
                "attestationSha256": sha256(build_dir / "v2-attestation.json"),
                "rowMapSha256": _digest(build_dir / "row-timeline-map.json"),
                "items": expected,
                "baselineProperties": baseline_properties,
                "originalTimecode": original_timecode,
                "nativeMutationAttempted": False,
            }
            _save_state(state_path, state)

            baseline_frames = _capture(
                "baseline", project, timeline, expected, evidence_dir
            )
            state["baselineFrames"] = baseline_frames
            state["status"] = "baseline_captured"
            _save_state(state_path, state)

            state["status"] = "transform_write_started"
            state["nativeMutationAttempted"] = True
            _save_state(state_path, state)
            for name, item in items.items():
                zoom = _TRANSFORMS[name]
                if item.SetProperty("ZoomX", zoom) is not True:
                    raise ValueError(f"Resolve refused ZoomX setter: {name}")
                if item.SetProperty("ZoomY", zoom) is not True:
                    raise ValueError(f"Resolve refused ZoomY setter: {name}")
            _find_exact_items(timeline, expected)
            after_properties = _properties(items)
            for name, values in after_properties.items():
                zoom = _TRANSFORMS[name]
                if not _matches(values["ZoomX"], zoom) or not _matches(
                    values["ZoomY"], zoom
                ):
                    raise ValueError(
                        f"immediate Transform scale readback differs: {name}"
                    )
                if not _matches(values["Pan"], 0) or not _matches(values["Tilt"], 0):
                    raise ValueError(f"centered Transform position changed: {name}")
            state["afterProperties"] = after_properties
            state["status"] = "transform_set"
            _save_state(state_path, state)
            after_frames = _capture("after", project, timeline, expected, evidence_dir)
            state["afterFrames"] = after_frames
            state["status"] = "after_captured"
            _save_state(state_path, state)

            state["status"] = "save_started"
            _save_state(state_path, state)
            if manager.SaveProject() is not True:
                raise ValueError("Resolve refused SaveProject")
            if manager.GetCurrentProject().GetUniqueId() != row_map["resolveProjectId"]:
                raise ValueError("current project changed during save")
            state["status"] = "close_started"
            _save_state(state_path, state)
            if manager.CloseProject(project) is not True:
                raise ValueError("Resolve refused CloseProject; do not retry")
            state["status"] = "closed"
            _save_state(state_path, state)
            project = manager.LoadProject(verified.attestation["projectName"])
            if project is None or project.GetUniqueId() != row_map["resolveProjectId"]:
                raise ValueError("exact target project did not reopen; do not retry")
            timeline = project.GetTimelineByIndex(1)
            if (
                project.GetTimelineCount() != 1
                or timeline is None
                or timeline.GetUniqueId() != row_map["timelineId"]
                or timeline.GetName() != verified.attestation["timelineName"]
                or project.SetCurrentTimeline(timeline) is not True
                or project.GetCurrentTimeline().GetUniqueId() != row_map["timelineId"]
            ):
                raise ValueError("reopened project/timeline identity differs")
            items = _find_exact_items(timeline, expected)
            reopened_properties = _properties(items)
            for name, values in reopened_properties.items():
                zoom = _TRANSFORMS[name]
                if not _matches(values["ZoomX"], zoom) or not _matches(
                    values["ZoomY"], zoom
                ):
                    raise ValueError(
                        f"Transform scale did not persist after reopen: {name}"
                    )
                if not _matches(values["Pan"], 0) or not _matches(values["Tilt"], 0):
                    raise ValueError(f"centered position differs after reopen: {name}")
            state["reopenedProperties"] = reopened_properties
            state["status"] = "reopened_verified"
            _save_state(state_path, state)
            reopened_frames = _capture(
                "reopened", project, timeline, expected, evidence_dir
            )
            _check_frames(baseline_frames, after_frames, reopened_frames)
            state["reopenedFrames"] = reopened_frames
            state["status"] = "complete"
            _save_state(state_path, state)
            return state_path
    except BaseException as error:
        if state_path is not None and state is not None:
            state["status"] = "stopped"
            state["failure"] = f"{type(error).__name__}: {error}"
            _save_state(state_path, state)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("explicit --execute required for native target writes")
    try:
        path = execute(args.build_dir, args.evidence_dir)
    except Exception as error:
        print(f"Stopped safely: {type(error).__name__}: {error}")
        return 2
    print(f"Verified save/close/reopen proof: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
