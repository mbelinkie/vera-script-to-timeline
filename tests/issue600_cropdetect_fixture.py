"""Tiny generated clips for #600 cropdetect characterization.

Run with ``uv run python tests/issue600_cropdetect_fixture.py`` and
``--output-dir /tmp/issue600``. The clips use lossless FFV1 and are disposable
synthetic media, never Resolve inputs.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

from vera_timeline_agent.cropdetect import CropDetection, analyze_media

_GRAPHS = {
    "letterbox": "testsrc2=size=320x140:rate=10:duration=2,pad=320:180:0:20:black",
    "pillarbox": "testsrc2=size=272x180:rate=10:duration=2,pad=320:180:24:0:black",
    "asymmetric": "testsrc2=size=320x130:rate=10:duration=2,pad=320:180:0:20:black",
    "near_black": "color=c=0x101010:s=320x180:r=10:d=2,format=yuv420p",
    "changing": (
        "testsrc2=size=320x140:rate=10:duration=1,pad=320:180:0:20:black[a];"
        "testsrc2=size=320x180:rate=10:duration=1[b];[a][b]concat=n=2:v=1:a=0"
    ),
    "dark_title": (
        "color=c=0x080808:s=320x180:r=10:d=2,"
        "drawbox=x=120:y=60:w=80:h=60:color=white:t=fill,format=yuv420p"
    ),
}

# Reuse the letterbox clip as an explicit-framing control for downstream
# integration tests. This does not prove Resolve's transform conventions.
OVERRIDE_CONTROL = {
    "source_fixture": "letterbox",
    "framing_override": {"zoom": 180 / 140, "center_x": 0.5, "center_y": 0.5},
    "expected_action": "preserve-explicit-framing",
}


def _run(ffmpeg: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [ffmpeg, *args], check=True, capture_output=True, text=True, timeout=30
    )


def generate_issue600_cropdetect_fixtures(
    output_dir: Path, ffmpeg: str | None = None
) -> dict[str, Path]:
    """Generate short 320x180 FFV1 clips under ``output_dir``."""
    executable = ffmpeg or shutil.which("ffmpeg")
    if executable is None:
        raise FileNotFoundError("ffmpeg is required to generate issue #600 fixtures")
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, graph in _GRAPHS.items():
        path = output_dir / f"issue600-{name}.mkv"
        _run(
            executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            graph,
            "-frames:v",
            "20",
            "-an",
            "-c:v",
            "ffv1",
            "-level",
            "3",
            "-pix_fmt",
            "yuv420p",
            str(path),
        )
        paths[name] = path
    return paths


def _detection_report(detection: CropDetection) -> dict[str, object]:
    return {
        "source_size": detection.source_size,
        "used_range": detection.used_range,
        "active_rect": (
            asdict(detection.active_rect) if detection.active_rect is not None else None
        ),
        "accepted": detection.accepted,
        "refusal_reason": detection.refusal_reason,
        "samples": [asdict(sample) for sample in detection.samples],
    }


def _report(output_dir: Path, ffmpeg: str) -> dict[str, object]:
    fixtures = generate_issue600_cropdetect_fixtures(output_dir, ffmpeg)
    detections = {
        name: analyze_media(path, (0.0, 2.0), ffmpeg=ffmpeg)
        for name, path in fixtures.items()
    }
    return {
        "ffmpeg": _run(ffmpeg, "-version").stdout.splitlines()[0],
        "fixtures": {
            name: {
                "path": str(fixtures[name]),
                **_detection_report(detections[name]),
            }
            for name in fixtures
        },
        "override_control": OVERRIDE_CONTROL,
        "note": (
            "cropdetect geometry and temporal agreement cannot distinguish all "
            "edge-aligned graphics from baked-in bars"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        parser.error("ffmpeg was not found on PATH")
    print(json.dumps(_report(args.output_dir, ffmpeg), indent=2))


if __name__ == "__main__":
    main()
