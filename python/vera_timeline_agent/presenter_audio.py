"""Produce a cleaned, video-length presenter audio sidecar locally."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time

from .presenter_sync import SyncRefused, find_offset
from .presenter_takes import RATE, TakesError, decode_audio, probe_video

OUTPUT_RATE = 48_000


def run(command: list[str]) -> None:
    try:
        result = subprocess.run(command, capture_output=True, check=False)
    except OSError as error:
        raise TakesError(f"Could not run {command[0]}: {error.strerror}") from error
    if result.returncode:
        raise TakesError(
            f"{command[0]} failed: {result.stderr.decode(errors='replace').strip()}"
        )


def clean(video: Path, output: Path, separate: Path | None = None) -> None:
    started = time.monotonic()
    command = shlex.split(os.environ.get("VERA_DEEPFILTER_COMMAND", ""))
    if not command:
        raise TakesError(
            "Set VERA_DEEPFILTER_COMMAND to the DeepFilterNet 0.5.6 program."
        )
    if output.exists():
        raise TakesError("Output already exists; choose a new output file.")
    duration, fps = probe_video(video)
    frame = fps[1] / fps[0]
    camera = decode_audio(video)
    offset = 0.0
    if separate is not None:
        sync = find_offset(camera, decode_audio(separate), RATE)
        if sync.spread_s > frame:
            raise SyncRefused(
                "Separate audio alignment varies by more than one video frame."
            )
        offset = sync.offset_s
        print(
            f"Separate audio offset: {offset * 1000:.1f} ms; spread: {sync.spread_s * 1000:.1f} ms."
        )
    count = round(duration * OUTPUT_RATE)
    shift = round(offset * OUTPUT_RATE)
    with tempfile.TemporaryDirectory(
        prefix="vera-presenter-audio-", dir=output.parent
    ) as work:
        root = Path(work)
        source = root / "input.wav"
        filtered = root / "filtered"
        filtered.mkdir()
        filters = ["pan=mono|c0=c0", f"aresample={OUTPUT_RATE}:async=1:first_pts=0"]
        if shift >= 0:
            filters.append(f"atrim=start_sample={shift}")
        else:
            filters.append(f"adelay={-shift}S:all=1")
        filters.extend(["asetpts=PTS-STARTPTS", "apad", f"atrim=end_sample={count}"])
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-i",
                str(separate or video),
                "-map",
                "0:a:0",
                "-af",
                ",".join(filters),
                "-ar",
                str(OUTPUT_RATE),
                "-c:a",
                "pcm_s24le",
                str(source),
            ]
        )
        run([*command, "-a", "30", "-D", "-o", str(filtered), str(source)])
        files = list(filtered.glob("*.wav"))
        if len(files) != 1:
            raise TakesError("DeepFilterNet did not produce exactly one WAV file.")
        staged = root / "result.wav"
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-i",
                str(files[0]),
                "-af",
                f"pan=mono|c0=c0,aresample={OUTPUT_RATE},apad,atrim=end_sample={count}",
                "-ar",
                str(OUTPUT_RATE),
                "-c:a",
                "pcm_s24le",
                str(staged),
            ]
        )
        measured = find_offset(camera, decode_audio(staged), RATE)
        if abs(measured.offset_s) > frame or measured.spread_s > frame:
            raise SyncRefused("Cleaned audio is not aligned within one video frame.")
        try:
            os.link(staged, output)
        except FileExistsError as error:
            raise TakesError(
                "Output already exists; choose a new output file."
            ) from error
    print(
        f"Measured cleaned audio sync: {measured.offset_s * 1000:.1f} ms; "
        f"spread: {measured.spread_s * 1000:.1f} ms. Time: {time.monotonic() - started:.1f} s."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--audio", type=Path, help="separate recording, if present")
    parser.add_argument("--out", type=Path, required=True, help="new WAV file")
    args = parser.parse_args()
    try:
        clean(args.video, args.out, args.audio)
    except (TakesError, SyncRefused, OSError, ValueError) as error:
        parser.exit(1, f"Presenter audio: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
