"""One-use recovery of a synthetic #336 OTIO import after a bridge timeout.

This is an investigation helper, not a product route.  It never reimports or
places any clip, and refuses if the active Resolve project or source is not
the exact disposable test target.  Do not replay an uncertain render request.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2, default=str) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def context(root: Path, name: str, manager: Any) -> tuple[Any, Any, Any, dict]:
    project = manager.GetCurrentProject()
    if project is None or project.GetName() != "VERA336-SYN-" + root.name:
        raise RuntimeError("refuse: active project is not the exact disposable target")
    if project.GetTimelineCount() != 1:
        raise RuntimeError("refuse: synthetic project has unexpected timelines")
    timeline = project.GetCurrentTimeline()
    if timeline is None or timeline.GetName() != name:
        raise RuntimeError("refuse: wrong native timeline")
    clips = timeline.GetItemListInTrack("video", 1)
    if len(clips) != 1 or clips[0].GetDuration() != 48:
        raise RuntimeError("refuse: native occurrence duration/count changed")
    item = clips[0].GetMediaPoolItem()
    if item is None:
        raise RuntimeError("refuse: no media-pool source")
    actual = item.GetClipProperty("File Path")
    source = root / "square.png"
    if not isinstance(actual, str) or Path(actual).resolve() != source.resolve():
        raise RuntimeError(
            f"refuse: media source does not equal public grid: {actual!r}"
        )
    evidence = json.loads((root / "evidence.json").read_text())
    if (
        evidence.get("project") != project.GetName()
        or evidence["cases"].get(name, {}).get("status") != "starting"
        or evidence["sourceHashes"].get("square") != sha(source)
    ):
        raise RuntimeError("refuse: prior interrupted case/source does not match")
    return project, timeline, clips[0], evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--phase", choices=("start", "inspect", "decode", "reopen"), required=True
    )
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("explicit --execute required")
    root = args.root.resolve()
    case = "square-none-48"
    import DaVinciResolveScript  # type: ignore[import-not-found]

    resolve = DaVinciResolveScript.scriptapp("Resolve")
    if resolve is None or resolve.GetVersionString() != "21.1.1.10":
        raise RuntimeError("refuse: unqualified Studio runtime")
    manager = resolve.GetProjectManager()
    project, timeline, _clip, _evidence = context(root, case, manager)
    state_path = root / "recovery.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else None

    if args.phase == "start":
        if state is not None:
            raise RuntimeError("refuse: render attempt already reserved; no replay")
        if project.IsRenderingInProgress() is not False or project.GetRenderJobList():
            raise RuntimeError("refuse: existing render activity or jobs")
        if list(root.glob(case + "*.mov")):
            raise RuntimeError("refuse: output already exists")
        profile = {
            key: timeline.GetSetting(key)
            for key in (
                "timelineResolutionWidth",
                "timelineResolutionHeight",
                "timelineFrameRate",
            )
        }
        state = {
            "status": "reserved",
            "case": case,
            "project": project.GetName(),
            "profileReadback": profile,
            "sourceSha256": sha(root / "square.png"),
        }
        save_json(state_path, state)  # reserve before any native render effects
        if not project.SetCurrentRenderFormatAndCodec("mov", "ProRes422"):
            raise RuntimeError("refuse: ProRes 422 render codec")
        settings = {
            "TargetDir": str(root),
            "CustomName": case,
            "ExportVideo": True,
            "ExportAudio": False,
            "SelectAllFrames": True,
            "RenderMode": "Single clip",
            "FormatWidth": 1280,
            "FormatHeight": 720,
        }
        if not project.SetRenderSettings(settings):
            raise RuntimeError("refuse: render settings rejected")
        job = project.AddRenderJob()
        if not isinstance(job, str) or not job:
            raise RuntimeError("refuse: no native render job identity")
        state.update(status="job-added", jobId=job)
        save_json(state_path, state)
        if not project.StartRendering([job], False):
            raise RuntimeError("refuse: native rendering did not start")
        state["status"] = "render-started"
        save_json(state_path, state)
        print("RENDER_STARTED", job)
        return 0

    if (
        state is None
        or state.get("case") != case
        or state.get("project") != project.GetName()
    ):
        raise RuntimeError("refuse: no exact recovery reservation")
    if args.phase == "inspect":
        job = state.get("jobId")
        if not isinstance(job, str):
            raise RuntimeError("refuse: reservation has no job ID; inspect manually")
        status = project.GetRenderJobStatus(job)
        state["lastRenderStatus"] = status
        if status.get("JobStatus") == "Complete":
            videos = list(root.glob(case + "*.mov"))
            if len(videos) != 1 or videos[0].stat().st_size == 0:
                raise RuntimeError("Complete but no unique nonempty output movie")
            state.update(
                status="render-complete",
                movie=videos[0].name,
                movieSha256=sha(videos[0]),
            )
        save_json(state_path, state)
        print(json.dumps({"status": state["status"], "job": status}, default=str))
        return 0

    if args.phase == "decode":
        if state.get("status") != "render-complete":
            raise RuntimeError("refuse: render not independently complete")
        movie = root / state["movie"]
        if sha(movie) != state["movieSha256"]:
            raise RuntimeError("refuse: rendered movie has changed")
        from qualify import video_pixels

        decoded = video_pixels(movie, [0, 12, 24, 36, 47])
        if decoded["frames"] != 48:
            raise RuntimeError("rendered duration not 48 frames")
        state.update(status="decoded", decoded=decoded)
        save_json(state_path, state)
        print(
            json.dumps(
                {
                    "frames": decoded["frames"],
                    "size": decoded["size"],
                    "samples": decoded["samples"],
                }
            )
        )
        return 0

    if state.get("status") != "decoded":
        raise RuntimeError("refuse: save/reopen requires decoded output")
    if manager.SaveProject() is not True:
        raise RuntimeError("save refused; preserve current target and evidence")
    if not manager.CloseProject(project):
        raise RuntimeError("close refused; no replay")
    reopened = manager.LoadProject(state["project"])
    if reopened is None:
        raise RuntimeError("reopen refused; no replay")
    state.update(
        status="reopened",
        reopenedName=reopened.GetName(),
        reopenedTimelines=reopened.GetTimelineCount(),
    )
    save_json(state_path, state)
    print("REOPENED", state["reopenedName"], state["reopenedTimelines"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
