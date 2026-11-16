"""Tiny generated clips for #600 cropdetect characterization.

Run with ``uv run python tests/issue600_cropdetect_fixture.py`` and
``--output-dir /tmp/issue600``.
The clips use lossless FFV1 so the test exercises cropdetect rather than encoder
ringing. They are disposable synthetic media, never Resolve inputs.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from vera_timeline_agent.cropdetect import CropRect


@dataclass(frozen=True)
class CropObservation:
    time_seconds: float
    rect: CropRect


_GRAPHS = {
    "letterbox": "testsrc2=size=320x140:rate=10:duration=2,pad=320:180:0:20:black",
    "pillarbox": "testsrc2=size=272x180:rate=10:duration=2,pad=320:180:24:0:black",
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
# integration tests. This is fixture metadata; it does not claim to test the
# caller's override precedence or Resolve's transform conventions.
OVERRIDE_CONTROL = {
    "source_fixture": "letterbox",
    "framing_override": {"zoom": 180 / 140, "center_x": 0.5, "center_y": 0.5},
    "expected_action": "preserve-explicit-framing",
}

_CROP_RE = re.compile(
    r"\bt:([0-9.]+).*?\bcrop=(\d+):(\d+):(\d+):(\d+)"
)


def _run(ffmpeg: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [ffmpeg, *args], check=True, capture_output=True, text=True, timeout=30
    )


def generate_issue600_cropdetect_fixtures(
    output_dir: Path, ffmpeg: str | None = None
) -> dict[str, Path]:
    """Generate five short 320x180 FFV1 clips under ``output_dir``."""
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


def observe_issue600_cropdetect(
    path: Path, ffmpeg: str | None = None
) -> list[CropObservation]:
    """Return cropdetect's per-frame rectangles using its default black mode."""
    executable = ffmpeg or shutil.which("ffmpeg")
    if executable is None:
        raise FileNotFoundError("ffmpeg is required to inspect issue #600 fixtures")
    result = _run(
        executable,
        "-hide_banner",
        "-loglevel",
        "info",
        "-i",
        str(path),
        "-vf",
        "cropdetect=limit=0.0941176:round=2:reset=0",
        "-an",
        "-f",
        "null",
        "-",
    )
    observations = []
    for match in _CROP_RE.finditer(result.stderr):
        time_seconds, width, height, x, y = match.groups()
        observations.append(
            CropObservation(
                float(time_seconds), CropRect(int(x), int(y), int(width), int(height))
            )
        )
    if not observations:
        raise RuntimeError(f"cropdetect produced no observations for {path}")
    return observations


def sampled_windows(
    observations: list[CropObservation], count: int = 3
) -> list[CropObservation]:
    """Choose first, middle, and last observations from the analyzed range."""
    if len(observations) < count:
        return observations
    indices = sorted(
        {
            round(index * (len(observations) - 1) / (count - 1))
            for index in range(count)
        }
    )
    return [observations[index] for index in indices]


def _report(output_dir: Path, ffmpeg: str) -> dict[str, object]:
    fixtures = generate_issue600_cropdetect_fixtures(output_dir, ffmpeg)
    observations = {
        name: observe_issue600_cropdetect(path, ffmpeg)
        for name, path in fixtures.items()
    }
    return {
        "ffmpeg": _run(ffmpeg, "-version").stdout.splitlines()[0],
        "fixtures": {
            name: {
                "path": str(fixtures[name]),
                "observations": [
                    {"time_seconds": item.time_seconds, "rect": asdict(item.rect)}
                    for item in observations[name]
                ],
                "sampled_windows": [
                    {"time_seconds": item.time_seconds, "rect": asdict(item.rect)}
                    for item in sampled_windows(observations[name])
                ],
            }
            for name in fixtures
        },
        "override_control": OVERRIDE_CONTROL,
        "note": (
            "cropdetect bounds alone do not establish that dark edges are "
            "baked-in bars"
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
