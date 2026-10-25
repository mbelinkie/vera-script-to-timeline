"""Public synthetic picture sources and placement plan for the #312 rehearsal.

This generates inputs only. It never manufactures narration timing, preparation
receipts, compiler output, native evidence or benchmark results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

from .narration.models import canonical_json_bytes

RATE = Fraction(24000, 1001)
MAX_BYTES = 2 * 1024**3
REHEARSAL_SOURCES = (0, 1, 8, 16, 17, 20)


def source_specs(*, rehearsal: bool = False) -> list[dict[str, Any]]:
    """Retain all four size/rate classes in the six-source rehearsal."""
    indices = REHEARSAL_SOURCES if rehearsal else tuple(range(24))
    return [
        {
            "id": f"source-{index:02d}",
            "width": 3840 if index in {0, 8, 16, 20} else 1920,
            "height": 2160 if index in {0, 8, 16, 20} else 1080,
            "rate": {"numerator": 24000 if index < 16 else 30000, "denominator": 1001},
            "audio": False,
            "codec": "h264",
            "pixelFormat": "yuv420p",
        }
        for index in indices
    ]


def placement_plan(*, rehearsal: bool = False) -> dict[str, Any]:
    """Specify density and token anchors; actual accepted timing sets frames."""
    sources = source_specs(rehearsal=rehearsal)
    row_count, overlay_count = (6, 3) if rehearsal else (30, 12)
    pictures = [
        {
            "id": f"picture-{index:02d}",
            "row": index // 2,
            "source": sources[index % len(sources)]["id"],
            "start": {"kind": "row_start"}
            if index % 2 == 0
            else {"kind": "spoken_word", "tokenIndex": 22},
            "sourceInFrame": 24,
            "framingPolicy": "contain",
            "audioPolicy": "mute",
        }
        for index in range(row_count * 2)
    ]
    overlays = [
        {
            "id": f"overlay-{index:02d}",
            "row": index * row_count // overlay_count,
            "source": sources[(index * 5 + 1) % len(sources)]["id"],
            "tokenIndex": 8,
            "durationMs": 2000,
            "sourceInFrame": 24,
            "framingPolicy": "contain",
            "audioPolicy": "mute",
        }
        for index in range(overlay_count)
    ]
    return {
        "schemaVersion": "issue-312-fixture-plan/v1",
        "mode": "rehearsal" if rehearsal else "representative",
        "timeline": {
            "width": 1920,
            "height": 1080,
            "rate": {"numerator": RATE.numerator, "denominator": RATE.denominator},
        },
        "narrationRows": row_count,
        "approximateWordsPerRow": 45,
        "nominalFramesPerRow": 480,
        "durationAuthority": "accepted narration timing and compiled manifest",
        "sources": sources,
        "pictures": pictures,
        "overlays": overlays,
        "expectedEvents": row_count + len(pictures) + len(overlays),
        "edit": {"pictureId": "picture-01", "boundaryDeltaFrames": 24},
    }


def source_command(
    spec: dict[str, Any], output: Path, *, source_seconds: int, ffmpeg: str
) -> list[str]:
    if type(source_seconds) is not int or not 3 <= source_seconds <= 120:
        raise ValueError("source duration must be 3-120 seconds")
    rate = Fraction(spec["rate"]["numerator"], spec["rate"]["denominator"])
    frames = (
        source_seconds * rate.numerator + rate.denominator - 1
    ) // rate.denominator
    # Only mathematical patterns; no fonts, recorded footage or external assets.
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-n",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={spec['width']}x{spec['height']}:rate={rate}",
        "-frames:v",
        str(frames),
        "-an",
        "-c:v",
        "libx264",
        "-threads",
        "2",
        "-preset",
        "ultrafast",
        "-crf",
        "28",
        "-pix_fmt",
        "yuv420p",
        "-vf",
        f"hue=h={int(spec['id'].split('-')[1]) * 13}",
        "-color_range",
        "tv",
        "-colorspace",
        "bt709",
        "-color_trc",
        "bt709",
        "-color_primaries",
        "bt709",
        "-flags",
        "+bitexact",
        str(output),
    ]


def _digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return "sha256:" + result.hexdigest()


def generate_sources(
    output_root: Path,
    *,
    rehearsal: bool = False,
    source_seconds: int = 30,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> Path:
    """Write a new retained source set; never overwrite or delete an old one."""
    root = output_root.absolute()
    if any(part.is_symlink() for part in (root, *root.parents)):
        raise ValueError("symbolic-link output refused")
    root.mkdir(parents=True, exist_ok=False)
    plan = placement_plan(rehearsal=rehearsal)
    manifest: dict[str, Any] = {
        "schemaVersion": "issue-312-source-set/v1",
        "plan": plan,
        "generatorHash": _digest(Path(__file__)),
        "sourceSeconds": source_seconds,
        "rights": "CC0-1.0; generated mathematical video patterns",
        "sources": [],
        "complete": False,
    }
    manifest_path = root / "source-set.json"
    total = 0
    for spec in plan["sources"]:
        path = root / f"{spec['id']}.mp4"
        command = source_command(
            spec, path, source_seconds=source_seconds, ffmpeg=ffmpeg
        )
        subprocess.run(command, check=True, capture_output=True, timeout=1800)
        total += path.stat().st_size
        if total > MAX_BYTES:
            raise ValueError("source set exceeds 2 GiB; retain this failed attempt")
        probe_command = [
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ]
        raw = subprocess.run(
            probe_command, check=True, capture_output=True, timeout=600
        ).stdout
        streams = json.loads(raw)["streams"]
        if len(streams) != 1:
            raise ValueError("one silent video stream required")
        stream = streams[0]
        expected_rate = Fraction(spec["rate"]["numerator"], spec["rate"]["denominator"])
        expected_frames = -(
            -source_seconds * expected_rate.numerator // expected_rate.denominator
        )
        if (
            stream["codec_type"] != "video"
            or stream["codec_name"] != "h264"
            or stream["pix_fmt"] != "yuv420p"
            or stream["width"] != spec["width"]
            or stream["height"] != spec["height"]
            or Fraction(stream["avg_frame_rate"]) != expected_rate
            or int(stream["nb_read_frames"]) != expected_frames
            or any(
                stream.get(key) != value
                for key, value in {
                    "color_range": "tv",
                    "color_space": "bt709",
                    "color_transfer": "bt709",
                    "color_primaries": "bt709",
                    "field_order": "progressive",
                }.items()
            )
        ):
            raise ValueError(f"source profile mismatch: {spec['id']}")
        manifest["sources"].append(
            {
                **spec,
                "file": path.name,
                "sizeBytes": path.stat().st_size,
                "sha256": _digest(path),
                "decodedFrames": expected_frames,
                "probeHash": "sha256:" + hashlib.sha256(raw).hexdigest(),
                "command": command,
                "probeCommand": probe_command,
            }
        )
    manifest["complete"] = True
    manifest["totalSourceBytes"] = total
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rehearsal", action="store_true")
    parser.add_argument("--source-seconds", type=int, default=30)
    parser.add_argument("--generate-video", action="store_true")
    args = parser.parse_args()
    if args.generate_video:
        path = generate_sources(
            args.output, rehearsal=args.rehearsal, source_seconds=args.source_seconds
        )
    else:
        path = args.output.absolute()
        with path.open("xb") as stream:
            stream.write(canonical_json_bytes(placement_plan(rehearsal=args.rehearsal)))
    print(path)


if __name__ == "__main__":
    main()
