"""Headless DaVinci Resolve Studio transcription (no GUI, no user action).

Launches Resolve with `-nogui` when it is not already running and connects
through the scripting API (Preferences > System > General > External
scripting = Local). It then creates a throwaway project at 120 fps (8.3 ms
word resolution), imports the audio, runs TranscribeAudio, polls until done
and saves GetTranscription() in the same shape as the GUI run
(`raw-resolve.json`, read by resolve_to_tc.py). Finally it deletes the project
and quits Resolve if this script started it.

Usage: resolve_headless.py --audio X.wav --out raw-resolve.json [--keep-running]
Run with a Python that Resolve's fusionscript supports (3.12 works).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

APP = "/Applications/DaVinci Resolve/DaVinci Resolve.app"
SCRIPT_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
SCRIPT_LIB = f"{APP}/Contents/Libraries/Fusion/fusionscript.so"


def connect(timeout: float) -> object | None:
    os.environ.setdefault("RESOLVE_SCRIPT_API", SCRIPT_API)
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", SCRIPT_LIB)
    sys.path.append(f"{SCRIPT_API}/Modules")
    import DaVinciResolveScript as dvr  # noqa: PLC0415

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resolve = dvr.scriptapp("Resolve")
        if resolve and resolve.GetProjectManager():
            return resolve
        time.sleep(2)
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--keep-running", action="store_true")
    args = parser.parse_args()
    timings: dict[str, float] = {}
    t0 = time.monotonic()

    resolve = connect(5)
    launched = None
    if resolve is None:
        launched = subprocess.Popen([f"{APP}/Contents/MacOS/Resolve", "-nogui"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        resolve = connect(240)
        if resolve is None:
            launched.terminate()
            raise SystemExit("could not connect to Resolve (is External scripting set to Local?)")
    timings["startAndConnect"] = time.monotonic() - t0

    pm = resolve.GetProjectManager()
    name = f"VERA headless transcription {int(time.time())}"
    project = pm.CreateProject(name)
    if not project:
        raise SystemExit("CreateProject failed")
    project.SetSetting("timelineFrameRate", "120")
    project.SetSetting("transcriptionLanguage", "en")
    t1 = time.monotonic()
    items = project.GetMediaPool().ImportMedia([str(args.audio.resolve())])
    if not items:
        raise SystemExit("ImportMedia failed")
    clip = items[0]
    timings["import"] = time.monotonic() - t1

    t2 = time.monotonic()
    if not clip.TranscribeAudio(False):
        raise SystemExit("TranscribeAudio refused to start")
    status: dict = {}
    while True:
        status = project.GetTranscribeAudioStatus() or {}
        if status.get("JobStatus") in ("Complete", "Cancelled") or status.get("Error"):
            break
        time.sleep(3)
    timings["transcribe"] = time.monotonic() - t2
    if status.get("JobStatus") != "Complete":
        raise SystemExit(f"transcription did not complete: {status}")

    transcription = clip.GetTranscription()
    args.out.write_text(json.dumps({
        "clipProps": {k: clip.GetClipProperty(k) for k in ("FPS", "Start TC", "Duration")},
        "projectFps": project.GetSetting("timelineFrameRate"),
        "transcriptionLanguage": project.GetSetting("transcriptionLanguage"),
        "resolveVersion": resolve.GetVersionString(), "headless": launched is not None,
        "timingsSec": timings, "transcription": transcription}, indent=1))

    pm.CloseProject(project)
    deleted = pm.DeleteProject(name)
    if launched is not None and not args.keep_running:
        resolve.Quit()
        try:
            launched.wait(60)
        except subprocess.TimeoutExpired:
            launched.terminate()
    timings["total"] = time.monotonic() - t0
    words = sum(len(s.get("words", [])) for s in (transcription or {}).get("segments", []))
    print(json.dumps({"headless": launched is not None, "projectDeleted": deleted, "items": words,
                      "timingsSec": {k: round(v, 1) for k, v in timings.items()}}))


if __name__ == "__main__":
    main()
