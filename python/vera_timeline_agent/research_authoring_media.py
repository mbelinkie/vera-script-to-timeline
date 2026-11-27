"""Read verified project-local Research media for the local authoring host."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .build_jobs import BuildJobError
from .build_stage_receipt import hash_file
from .media_preparation import MediaTools
from .research_cut_binding import (
    bind_research_cut,
    copy_cut,
    find_cached_research_cut,
    research_clip_folder,
    verified_transcript_clock,
)


def resolve(root: Path, export_root: Path | None, request: dict[str, Any]) -> None:
    pin = request["pin"]
    directory = research_clip_folder(root, pin)
    cut = find_cached_research_cut(directory, pin)
    if cut is None and export_root is not None and request["action"] == "resolve":
        candidate = export_root / directory.parent.name
        if candidate.exists():
            cut = (
                copy_cut(candidate, pin, directory)
                if request["materialize"]
                else candidate
            )
    if cut is None:
        raise FileNotFoundError("Verified project cut is missing")
    row = {
        "id": request["rowId"],
        "payload": {"payloadId": request["payloadId"]},
        "researchClip": pin,
        "visualOnlyTiming": {"kind": "visual_only"},
    }
    source, media, descriptor = bind_research_cut(row, cut, MediaTools())
    if request["action"] == "resolve":
        print(
            json.dumps(
                {
                    "binding": row["frameBinding"],
                    "sourceFrameMap": descriptor["sourceFrameMap"],
                    **(
                        {"transcriptClock": verified_transcript_clock(cut, pin, media)}
                        if request.get("includeTranscriptClock")
                        else {}
                    ),
                }
            )
        )
        return
    if row["frameBinding"] != request["binding"]:
        raise ValueError("Saved binding differs from verified cut")
    start, end = request["startFrame"], request["endFrame"]
    if not 0 <= start < end <= len(media.video_frames):
        raise ValueError("Preview is outside verified frames")

    # FFmpeg opens only a private copy whose bytes matched the verified cut.
    with tempfile.TemporaryDirectory(prefix="vera-research-preview-") as staging:
        path = Path(staging).resolve(strict=True) / "cut.mp4"
        shutil.copyfile(source, path)
        if hash_file(path) != media.content_hash.removeprefix("sha256:"):
            raise ValueError("Cut changed before preview")
        if request["action"] == "frame":
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-nostdin",
                    "-i",
                    str(path),
                    "-vf",
                    f"select=eq(n\\,{start})",
                    "-frames:v",
                    "1",
                    "-an",
                    "-c:v",
                    "png",
                    "-threads",
                    "1",
                    "-f",
                    "image2pipe",
                    "pipe:1",
                ],
                check=True,
                timeout=90,
            )
            return
        audio_origin = media.audio_origin
        if audio_origin is None or media.audio is None:
            raise ValueError("Cut has no verified audio clock")
        offset = audio_origin - media.pts_origin
        # aresample first aligns audio to video frame zero, including silence for
        # a late start. Both boundaries are computed on the decoded frame clock.
        sample_rate = int(media.audio["sample_rate"])
        audio = (
            f"asetpts=PTS-STARTPTS+({offset.numerator}/{offset.denominator})/TB,"
            "aresample=async=1:first_pts=0,"
            f"atrim=start_sample={math.ceil(start * sample_rate / media.rate)}:"
            f"end_sample={math.ceil(end * sample_rate / media.rate)},"
            "asetpts=PTS-STARTPTS"
        )
        output = path.with_name("preview.mp4")
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-i",
                str(path),
                "-vf",
                f"trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS",
                "-af",
                audio,
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                "-c:v",
                "libx264",
                "-threads",
                "1",
                "-bf",
                "0",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-fps_mode",
                "passthrough",
                "-movflags",
                "+faststart",
                str(output),
            ],
            check=True,
            timeout=90,
        )
        with output.open("rb") as stream:
            shutil.copyfileobj(stream, sys.stdout.buffer)


def main() -> int:
    try:
        resolve(
            Path(sys.argv[1]),
            Path(sys.argv[2]) if len(sys.argv) == 3 else None,
            json.load(sys.stdin),
        )
    except FileNotFoundError:
        return 3
    except (BuildJobError, ValueError, OSError, subprocess.SubprocessError):
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
