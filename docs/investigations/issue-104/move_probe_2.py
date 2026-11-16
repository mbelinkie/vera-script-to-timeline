"""Second 21.2 measurement: co-moving dissolve, swap plus extend, and shrink.

Four 96-frame rows. A dissolve sits on cut 3|4. Rows 3 and 4 move right
together, row 2's picture is swapped through the take selector and then
extended, then everything is undone in the other direction (shrink, move
left). Saves, closes, reopens and reads back.

Usage: move_probe_2.py <media-directory> <result.json>
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
    files = ["A.mp4", "B.mp4", "C.mp4", "A-96.wav", "B-96.wav"]
    clip = {
        item.GetName(): item
        for item in need(
            pool.ImportMedia([str(media_dir / f) for f in files]), "import"
        )
    }
    timeline = need(pool.CreateEmptyTimeline("probe"), "timeline")
    origin = timeline.GetStartFrame()

    def place(media: str, kind: int, at: int, src: int) -> Any:
        return need(
            pool.AppendToTimeline(
                [
                    {
                        "mediaPoolItem": clip[media],
                        "mediaType": kind,
                        "trackIndex": 1,
                        "recordFrame": origin + at,
                        "startFrame": src,
                        "endFrame": src + ROW,
                    }
                ]
            ),
            f"place {media} at {at}",
        )[0]

    order = ("A.mp4", "B.mp4", "C.mp4", "A.mp4")
    pictures = [place(m, 1, i * ROW, HANDLE) for i, m in enumerate(order)]
    tones = [place("A-96.wav", 2, i * ROW, 0) for i in range(4)]
    pictures[1].SetProperty("ZoomX", 1.25)
    pictures[1].AddMarker(10, "Red", "hand note", "", 1, "")
    attempt(
        "grade row 2",
        lambda: pictures[1].SetCDL(
            {
                "NodeIndex": "1",
                "Slope": "1 1 1",
                "Offset": "0 0 0",
                "Power": "1 1 1",
                "Saturation": "0",
            }
        ),
    )
    attempt(
        "dissolve at cut 3|4",
        lambda: pictures[2].AddTransition(
            {
                "type": "Cross Dissolve",
                "category": "simple",
                "position": "end",
                "alignment": "center",
                "duration": 12,
            }
        ),
    )
    need(manager.SaveProject(), "save original")
    log["before"] = read(timeline, origin)

    later = [pictures[2], tones[2], pictures[3], tones[3]]
    attempt(
        "move rows 3+4 right",
        lambda: timeline.MoveItems(
            later, {"startFrame": float(pictures[2].GetStart() + GROW)}
        ),
    )
    log["afterMoveRight"] = read(timeline, origin)
    attempt(
        "swap row 2 picture (old length)",
        lambda: (
            pictures[1].AddTake(clip["C.mp4"], HANDLE, HANDLE + ROW),
            pictures[1].SelectTakeByIndex(pictures[1].GetTakesCount()),
            pictures[1].FinalizeTake(),
        ),
    )
    log["afterSwap"] = read(timeline, origin)
    attempt(
        "extend swapped picture",
        lambda: pictures[1].SetRightOffset(pictures[1].GetRightOffset() - GROW),
    )
    log["afterExtend"] = read(timeline, origin)
    attempt(
        "shrink it again",
        lambda: pictures[1].SetRightOffset(pictures[1].GetRightOffset() + GROW),
    )
    attempt(
        "move rows 3+4 left",
        lambda: timeline.MoveItems(
            later, {"startFrame": float(pictures[2].GetStart() - GROW)}
        ),
    )
    attempt(
        "move one tone alone and back",
        lambda: (
            tones[3].SetPosition({"startFrame": float(tones[3].GetStart() + 10)}),
            tones[3].SetPosition({"startFrame": float(tones[3].GetStart() - 10)}),
        ),
    )
    log["afterUndo"] = read(timeline, origin)
    need(manager.SaveProject(), "save")
    need(manager.CloseProject(project), "close")
    project = need(manager.LoadProject(name), "reopen")
    timeline = project.GetCurrentTimeline() or project.GetTimelineByIndex(1)
    log["reopened"] = read(timeline, timeline.GetStartFrame())
    log["project"] = name
    result.write_text(json.dumps(log, indent=2, default=str))
    step("wrote", str(result))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
