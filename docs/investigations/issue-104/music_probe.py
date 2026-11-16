"""Measure moving and resizing a music bed that spans rows, on Resolve 21.2.

Two 96-frame picture rows on V1. A bed on A2 starts in the middle of row 1
and ends in the middle of row 2, with a level and fades. Row 1 then gets 48
frames longer: row 2 moves, and the bed is first extended at its tail and
then, as a second case, moved without changing length. Saves, closes,
reopens and reads back.

Usage: music_probe.py <media-directory> <result.json>
"""

import json
import sys
import uuid
from pathlib import Path
from typing import Any

from move_probe import GROW, HANDLE, ROW, attempt, bmd, log, need, read, step


def main(media_dir: Path, result: Path) -> None:
    resolve = bmd.scriptapp("Resolve")
    log["version"] = need(resolve.GetVersionString(), "version")
    manager = resolve.GetProjectManager()
    name = f"VERA 104 move probe {uuid.uuid4().hex[:8]}"
    project = need(manager.CreateProject(name), f"create project {name}")
    need(project.SetSetting("timelineFrameRate", "24"), "24 fps")
    resolve.OpenPage("edit")
    pool = project.GetMediaPool()
    files = ["A.mp4", "B.mp4", "B-144.wav"]
    clip = {
        item.GetName(): item
        for item in need(
            pool.ImportMedia([str(media_dir / f) for f in files]), "import"
        )
    }
    timeline = need(pool.CreateEmptyTimeline("probe"), "timeline")
    need(timeline.AddTrack("audio"), "second audio track")
    origin = timeline.GetStartFrame()

    def place(media: str, kind: int, track: int, at: int, src: int, length: int) -> Any:
        return need(
            pool.AppendToTimeline(
                [
                    {
                        "mediaPoolItem": clip[media],
                        "mediaType": kind,
                        "trackIndex": track,
                        "recordFrame": origin + at,
                        "startFrame": src,
                        "endFrame": src + length,
                    }
                ]
            ),
            f"place {media} at {at}",
        )[0]

    pictures = [
        place(m, 1, 1, i * ROW, HANDLE, ROW) for i, m in enumerate(("A.mp4", "B.mp4"))
    ]
    bed = place("B-144.wav", 2, 2, 48, 0, ROW)  # Frames 48 to 144, across the cut.
    step("bed level", bed.SetProperty("AudioVolume", -18.0))
    attempt("bed fades", lambda: bed.SetFades({"FadeIn": 6, "FadeOut": 12}))
    need(manager.SaveProject(), "save original")
    log["before"] = read(timeline, origin)

    attempt(
        "move row 2 right",
        lambda: timeline.MoveItems(
            [pictures[1]], {"startFrame": float(pictures[1].GetStart() + GROW)}, False
        ),
    )
    attempt(
        "extend row 1 picture",
        lambda: pictures[0].SetRightOffset(pictures[0].GetRightOffset() - GROW),
    )
    step("bed right handle", attempt("GetRightOffset", bed.GetRightOffset))
    attempt("extend bed tail", lambda: bed.SetRightOffset(bed.GetRightOffset() - GROW))
    log["afterExtend"] = read(timeline, origin)
    attempt(
        "move bed later, same length",
        lambda: timeline.MoveItems(
            [bed], {"startFrame": float(bed.GetStart() + 24)}, False
        ),
    )
    attempt("shorten bed tail", lambda: bed.SetRightOffset(bed.GetRightOffset() + 24))
    log["afterMove"] = read(timeline, origin)
    need(manager.SaveProject(), "save")
    need(manager.CloseProject(project), "close")
    project = need(manager.LoadProject(name), "reopen")
    timeline = project.GetCurrentTimeline() or project.GetTimelineByIndex(1)
    log["reopened"] = read(timeline, timeline.GetStartFrame())
    result.write_text(json.dumps(log, indent=2, default=str))
    step("wrote", str(result))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
