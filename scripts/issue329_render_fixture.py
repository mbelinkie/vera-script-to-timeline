"""Generate or check the synthetic media for the #329 Resolve investigation."""

import argparse
import json
import subprocess
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

LABEL_X = tuple(range(128, 489, 72))
LABEL_Y = 296
SOURCE_WIDTH, SOURCE_HEIGHT = 640, 360


def generate(root: Path) -> None:
    font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 56)
    for section, first, tone in (("A", 0, 440), ("B", 24, 660)):
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-n",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            "640x360",
            "-r",
            "24",
            "-i",
            "-",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={tone}:sample_rate=48000:duration=1",
            "-c:v",
            "prores_ks",
            "-profile:v",
            "2",
            "-pix_fmt",
            "yuv422p10le",
            "-c:a",
            "pcm_s16le",
            "-shortest",
            str(root / f"{section}.mov"),
        ]
        frames = bytearray()
        for index in range(first, first + 24):
            frame = Image.new("RGB", (SOURCE_WIDTH, SOURCE_HEIGHT), (64, 80, 104))
            draw = ImageDraw.Draw(frame)
            draw.text((320, 128), f"SECTION {section}", "white", font, anchor="mm")
            draw.text((320, 202), f"FRAME {index:02d}", "white", font, anchor="mm")
            for bit, x in enumerate(LABEL_X):
                color = "white" if index & (1 << bit) else "black"
                draw.rectangle((x - 18, LABEL_Y - 22, x + 18, LABEL_Y + 22), fill=color)
            frames.extend(frame.tobytes())
        subprocess.run(command, input=bytes(frames), check=True)


def check(path: Path, expected: range) -> None:
    info = json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ]
        )
    )
    video, audio, timecode = info["streams"]
    if (
        info["format"]["tags"]["major_brand"] != "isom"
        or (video["codec_type"], video["codec_name"], video["profile"])
        != ("video", "h264", "High")
        or (video["width"], video["height"]) != (1280, 720)
        or (video["r_frame_rate"], video["avg_frame_rate"]) != ("24/1", "24/1")
        or (audio["codec_type"], audio["codec_name"]) != ("audio", "aac")
        or (audio["sample_rate"], audio["channels"]) != ("48000", 2)
        or (timecode["codec_type"], timecode["codec_tag_string"]) != ("data", "tmcd")
    ):
        raise ValueError(f"Unexpected streams or container in {path.name}")
    duration = Fraction(video["time_base"]) * int(video["duration_ts"])
    if duration != Fraction(len(expected), 24):
        raise ValueError(f"Unexpected video duration in {path.name}: {duration}")

    width, height = SOURCE_WIDTH // 2, SOURCE_HEIGHT // 2
    raw = subprocess.check_output(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-vf",
            f"scale={width}:{height}:flags=area,format=gray",
            "-f",
            "rawvideo",
            "-",
        ]
    )
    size = width * height
    if len(raw) != size * len(expected):
        raise ValueError(f"Unexpected decoded frame count in {path.name}")
    # Read the center of each binary marker. The printed label uses the same index.
    centers = [LABEL_Y // 2 * width + x // 2 for x in LABEL_X]
    labels = [
        sum((raw[offset + center] > 128) << bit for bit, center in enumerate(centers))
        for offset in range(0, len(raw), size)
    ]
    if labels != list(expected):
        raise ValueError(f"Frame labels disagree in {path.name}: {labels}")
    print(
        f"{path.name}: {len(labels)} frames, labels {labels[0]}-{labels[-1]}, "
        f"{duration} s video"
    )
    print(f"  H.264 High 1280x720 at 24 fps, {video['bit_rate']} b/s observed")
    print(
        f"  AAC {audio['sample_rate']} Hz stereo, {audio['duration']} s, plus timecode"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["generate", "check"])
    parser.add_argument("scratch", type=Path)
    args = parser.parse_args()
    if args.operation == "generate":
        generate(args.scratch)
    else:
        check(args.scratch / "whole" / "entire.mp4", range(48))
        check(args.scratch / "range" / "section-b.mp4", range(24, 48))


if __name__ == "__main__":
    main()
