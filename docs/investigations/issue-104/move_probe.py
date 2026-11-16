"""Measure in-place row lengthening on Resolve Studio 21.2 (throwaway project).

Builds three 96-frame rows (picture on V1, tone on A1), finishes rows 1 and 3
by script, adds an editor clip on V2 over row 3, then makes row 2 longer by 48
frames without recreating row 3: move row 3 and the editor clip right, then
extend row 2's picture into the gap. Saves, closes, reopens and reads back.

Usage: move_probe.py <media-directory> <result.json>
The media directory needs A.mp4, B.mp4, C.mp4, Spare.mp4 (24 fps, 192 frames;
Spare 24) and A-96.wav, B-96.wav, B-144.wav, as #327's prepare.py writes them.
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

APP = "/Applications/DaVinci Resolve 21.2/DaVinci Resolve.app"
API = (
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
)
os.environ["RESOLVE_SCRIPT_LIB"] = f"{APP}/Contents/Libraries/Fusion/fusionscript.so"
os.environ["RESOLVE_SCRIPT_API"] = API
sys.path.insert(0, f"{API}/Modules")
import DaVinciResolveScript as bmd  # noqa: E402

ROW, GROW, HANDLE = 96, 48, 24
log: dict[str, Any] = {"steps": []}


def step(name: str, value: Any) -> Any:
    log["steps"].append({"step": name, "result": repr(value)[:400]})
    print(f"{name}: {repr(value)[:200]}", flush=True)
    return value


def need(value: Any, name: str) -> Any:
    step(name, value)
    if not value:
        raise SystemExit(f"stopped at: {name}")
    return value


def attempt(name: str, call: Any) -> Any:
    try:
        return step(name, call())
    except Exception as error:  # A probe records what the SDK does.
        return step(name, f"EXCEPTION {type(error).__name__}: {error}")


def attempt_quiet(call: Any) -> Any:
    try:
        return call()
    except Exception as error:
        return f"EXCEPTION {type(error).__name__}"


def read(timeline: Any, origin: int) -> list[dict[str, Any]]:
    rows = []
    for kind in ("video", "audio"):
        for index in range(1, timeline.GetTrackCount(kind) + 1):
            for item in timeline.GetItemListInTrack(kind, index):
                if kind == "video" and item.GetType() == "transition":
                    rows.append(
                        {
                            "id": item.GetUniqueId(),
                            "kind": kind,
                            "track": index,
                            "type": "transition",
                            "name": item.GetName(),
                            "start": item.GetStart() - origin,
                            "end": item.GetEnd() - origin,
                            "markers": {},
                        }
                    )
                    continue
                media = item.GetMediaPoolItem()
                row: dict[str, Any] = {
                    "id": item.GetUniqueId(),
                    "kind": kind,
                    "track": index,
                    "type": item.GetType() if kind == "video" else "clip",
                    "name": item.GetName(),
                    "start": item.GetStart() - origin,
                    "end": item.GetEnd() - origin,
                    "sourceIn": item.GetSourceStartFrame(),
                    "media": media.GetName() if media else None,
                    "markers": item.GetMarkers(),
                    "color": item.GetClipColor(),
                }
                if kind == "audio":
                    row["volume"] = item.GetProperty("AudioVolume")
                else:
                    row["zoom"] = item.GetProperty("ZoomX")
                    row["fusionComps"] = item.GetFusionCompCount()
                    for name, call in (
                        ("cdl", lambda item=item: item.GetCDL(1)),
                        ("fusionFx", lambda item=item: len(item.GetEffects("fusion"))),
                        ("ofxFx", lambda item=item: len(item.GetEffects("ofx"))),
                        ("nodes", lambda item=item: item.GetNodeGraph().GetNumNodes()),
                    ):
                        try:
                            row[name] = call()
                        except Exception as error:
                            row[name] = f"EXCEPTION {type(error).__name__}"
                row["fades"] = attempt_quiet(item.GetFades)
                rows.append(row)
    return sorted(rows, key=lambda r: (r["kind"], r["track"], r["start"]))


def main(media_dir: Path, result: Path) -> None:
    resolve = bmd.scriptapp("Resolve")
    version = need(resolve.GetVersionString(), "version")
    log["version"] = version
    manager = resolve.GetProjectManager()
    name = f"VERA 104 move probe {uuid.uuid4().hex[:8]}"
    project = need(manager.CreateProject(name), f"create project {name}")
    need(project.SetSetting("timelineFrameRate", "24"), "24 fps")
    resolve.OpenPage("edit")
    pool = project.GetMediaPool()
    files = [
        "A.mp4",
        "B.mp4",
        "C.mp4",
        "Spare.mp4",
        "A-96.wav",
        "B-96.wav",
        "B-144.wav",
    ]
    imported = need(pool.ImportMedia([str(media_dir / f) for f in files]), "import")
    clip = {item.GetName(): item for item in imported}
    timeline = need(pool.CreateEmptyTimeline("probe"), "timeline")
    timeline.AddTrack("video")
    origin = timeline.GetStartFrame()
    step("origin", origin)

    def place(media: str, kind: int, track: int, at: int, src: int, length: int) -> Any:
        placed = pool.AppendToTimeline(
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
        )
        return need(placed, f"place {media} at {at}")[0]

    pictures = [
        place(m, 1, 1, i * ROW, HANDLE, ROW)
        for i, m in enumerate(("A.mp4", "B.mp4", "C.mp4"))
    ]
    tones = [
        place(m, 2, 1, i * ROW, 0, ROW)
        for i, m in enumerate(("A-96.wav", "B-96.wav", "A-96.wav"))
    ]
    editor = place("Spare.mp4", 1, 2, 2 * ROW + 24, 0, 24)

    # Finishing that a script can both set and read back on 21.2.
    for picture in (pictures[0], pictures[2]):
        step(
            "zoom",
            picture.SetProperty("ZoomX", 1.25) and picture.SetProperty("ZoomY", 1.25),
        )
        step("clip color", picture.SetClipColor("Orange"))
        attempt(
            "grade (saturation 0)",
            lambda p=picture: p.SetCDL(
                {
                    "NodeIndex": "1",
                    "Slope": "1 1 1",
                    "Offset": "0 0 0",
                    "Power": "1 1 1",
                    "Saturation": "0",
                }
            ),
        )
        step("hand marker", picture.AddMarker(10, "Red", "hand note", "", 1, ""))
    for tone in (tones[0], tones[2]):
        step("volume", tone.SetProperty("AudioVolume", -12.0))
    effects = attempt("effects list", lambda: resolve.GetEffectsList("video")) or []
    blur = next(
        (e for e in effects if isinstance(e, dict) and "blur" in str(e).lower()), None
    )
    step("chosen effect", blur)
    if blur:
        attempt(
            "add effect to row 3",
            lambda: pictures[2].AddEffect(
                blur.get("category") or blur.get("Category"),
                blur.get("id") or blur.get("Id"),
            ),
        )
    step("row 2 tone volume", tones[1].SetProperty("AudioVolume", -6.0))
    attempt("row 2 tone fades", lambda: tones[1].SetFades({"FadeIn": 4, "FadeOut": 4}))
    for label, outgoing in (
        ("dissolve at cut 1|2", pictures[0]),
        ("dissolve at cut 2|3", pictures[1]),
    ):
        attempt(
            label,
            lambda o=outgoing: o.AddTransition(
                {
                    "type": "Cross Dissolve",
                    "category": "simple",
                    "position": "end",
                    "alignment": "center",
                    "duration": 12,
                }
            ),
        )
    need(manager.SaveProject(), "save finished original")
    before = read(timeline, origin)
    log["before"] = before

    # Row 2 grows by GROW frames. Later clips move first, then row 2 fills the gap.
    movers = [pictures[2], tones[2], editor]
    target = {"startFrame": float(pictures[2].GetStart() + GROW)}
    step("row 3 position", attempt("GetPosition", pictures[2].GetPosition))
    moved = attempt(
        "MoveItems row 3 + editor clip", lambda: timeline.MoveItems(movers, target)
    )
    log["afterMove"] = read(timeline, origin)
    right = attempt("row 2 right handle", pictures[1].GetRightOffset)
    if isinstance(right, (int, float)):
        attempt(
            "extend row 2 picture", lambda: pictures[1].SetRightOffset(right - GROW)
        )
    log["afterExtend"] = read(timeline, origin)
    # Narration is a different, longer file and audio has no take selector:
    # place the new recording on a spare track, copy the old clip's settings
    # onto it, delete the old clip, then move the new one into its place.
    need(timeline.AddTrack("audio"), "spare audio track")
    spare = timeline.GetTrackCount("audio")
    new_tone = place("B-144.wav", 2, spare, ROW, 0, ROW + GROW)
    attempt(
        "copy settings old tone -> new",
        lambda: tones[1].CopyAttributes(
            [new_tone], {"allAudioAttributes": True, "allClipAttributes": True}
        ),
    )
    attempt(
        "new tone fades (not in copy options)",
        lambda: new_tone.SetFades(tones[1].GetFades()),
    )
    attempt("delete old tone", lambda: timeline.DeleteClips([tones[1]], False))
    attempt(
        "move new tone to A1",
        lambda: new_tone.SetPosition(
            {"trackIndex": 1, "startFrame": float(origin + ROW)}
        ),
    )
    attempt("delete spare track", lambda: timeline.DeleteTrack("audio", spare))
    log["afterEdit"] = read(timeline, origin)
    log["moved"] = repr(moved)

    need(manager.SaveProject(), "save")
    need(manager.CloseProject(project), "close")
    project = need(manager.LoadProject(name), "reopen")
    timeline = project.GetCurrentTimeline() or project.GetTimelineByIndex(1)
    log["reopened"] = read(timeline, timeline.GetStartFrame())
    log["project"] = name
    result.write_text(json.dumps(log, indent=2, default=str))
    print("wrote", result)


if __name__ == "__main__":
    started = time.time()
    try:
        main(Path(sys.argv[1]), Path(sys.argv[2]))
    finally:
        Path(sys.argv[2]).with_suffix(".partial.json").write_text(
            json.dumps(log, indent=2, default=str)
        )
        print(f"{time.time() - started:.1f}s")
