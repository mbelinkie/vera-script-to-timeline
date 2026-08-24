#!/usr/bin/env python3
"""Regenerate the canonical Slice 0.1 synthetic media kit."""

from __future__ import annotations

import json
import re
import struct
import subprocess
import tempfile
import wave
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fixtures.validate_fixtures import (
    CANONICAL_SETTINGS,
    DESCRIPTOR_PATH,
    FIXTURES_DIR,
    MEDIA_DIR,
    probe_asset,
    sha256_file,
)

EXPECTED_FFMPEG_VERSION = "8.1.2"
WIDTH = 1920
HEIGHT = 1080
FRAME_RATE = "24000/1001"
FRAME_COUNT = 48
SAMPLE_RATE = 48000
AUDIO_SAMPLE_COUNT = SAMPLE_RATE * 3


def _tool_version(tool: str) -> str:
    try:
        result = subprocess.run(
            [tool, "-version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(
            f"{tool} is required to regenerate fixtures: {error}"
        ) from error
    first_line = result.stdout.splitlines()[0] if result.stdout else ""
    match = re.match(rf"{tool} version ([^ ]+)", first_line)
    if match is None:
        raise SystemExit(f"could not parse {tool} version from: {first_line!r}")
    return match.group(1)


def _generate_video(path: Path, background: str, box_filter: str) -> None:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-fflags",
        "+bitexact",
        "-f",
        "lavfi",
        "-i",
        f"color=c={background}:s={WIDTH}x{HEIGHT}:r={FRAME_RATE}",
        "-vf",
        box_filter,
        "-frames:v",
        str(FRAME_COUNT),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryslow",
        "-crf",
        "32",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-level:v",
        "4.0",
        "-g",
        str(FRAME_COUNT),
        "-keyint_min",
        str(FRAME_COUNT),
        "-sc_threshold",
        "0",
        "-bf",
        "0",
        "-threads",
        "1",
        "-flags:v",
        "+bitexact",
        "-map_metadata",
        "-1",
        "-metadata",
        "creation_time=1970-01-01T00:00:00Z",
        "-movflags",
        "+faststart",
        str(path),
    ]
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"video generation failed for {path.name}") from error


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type)
    checksum = zlib.crc32(payload, checksum)
    return (
        struct.pack(">I", len(payload))
        + chunk_type
        + payload
        + struct.pack(">I", checksum)
    )


def _generate_png(
    path: Path,
    row_factory: Callable[[int], bytes],
) -> None:
    raw = bytearray()
    for y in range(HEIGHT):
        row = row_factory(y)
        if len(row) != WIDTH * 3:
            raise ValueError("PNG row factory returned the wrong width")
        raw.append(0)
        raw.extend(row)
    ihdr = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", ihdr)
    png += _png_chunk(b"IDAT", zlib.compress(bytes(raw), level=9))
    png += _png_chunk(b"IEND", b"")
    path.write_bytes(png)


def _reference_grid_row(y: int) -> bytes:
    background = (49, 46, 129)
    accent = (196, 181, 253)
    highlight = (255, 255, 255)
    row = bytearray(bytes(background) * WIDTH)
    if y % 180 < 6:
        row[:] = bytes(accent) * WIDTH
    for x in range(0, WIDTH, 240):
        row[x * 3 : (x + 6) * 3] = bytes(accent) * 6
    if 360 <= y < 720:
        row[720 * 3 : 1200 * 3] = bytes(highlight) * 480
    return bytes(row)


def _reference_bars_row(y: int) -> bytes:
    colors = (
        (8, 145, 178),
        (6, 182, 212),
        (34, 211, 238),
        (103, 232, 249),
    )
    row = bytearray()
    band_width = WIDTH // len(colors)
    for color in colors:
        row.extend(bytes(color) * band_width)
    if 500 <= y < 580:
        row[:] = bytes((15, 23, 42)) * WIDTH
    return bytes(row)


def _triangle_sample(index: int, frequency: int, amplitude: int) -> int:
    phase = (index * frequency) % SAMPLE_RATE
    centered = abs((phase * 2) - SAMPLE_RATE)
    return ((centered * 2 - SAMPLE_RATE) * amplitude) // SAMPLE_RATE


def _generate_audio_bed(path: Path) -> None:
    fade_samples = SAMPLE_RATE // 10
    frames = bytearray()
    for index in range(AUDIO_SAMPLE_COUNT):
        envelope = min(index, AUDIO_SAMPLE_COUNT - 1 - index, fade_samples)
        left = _triangle_sample(index, 220, 5000)
        right = _triangle_sample(index, 330, 4200)
        left = (left * envelope) // fade_samples
        right = (right * envelope) // fade_samples
        frames.extend(struct.pack("<hh", left, right))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.setnframes(AUDIO_SAMPLE_COUNT)
        output.writeframes(frames)


def _provenance(recipe: str) -> dict[str, object]:
    return {
        "sourceType": "procedurally_generated_synthetic",
        "generatedBy": f"fixtures/generate_fixtures.py::{recipe}",
        "containsThirdPartyMedia": False,
        "containsProductionMedia": False,
    }


def _asset_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": "clip.establishing-blue.v1",
            "role": "establishing-picture",
            "kind": "video",
            "filename": "clip-establishing-blue.mp4",
            "description": "Blue full-frame clip with a left-edge white locator block.",
            "recipe": "video_establishing_blue",
            "generate": lambda path: _generate_video(
                path,
                "0x1D4ED8",
                "drawbox=x=120:y=180:w=300:h=720:color=white:t=fill",
            ),
        },
        {
            "id": "clip.cutaway-orange.v1",
            "role": "research-cutaway",
            "kind": "video",
            "filename": "clip-cutaway-orange.mp4",
            "description": (
                "Orange full-frame clip with a centered white locator block."
            ),
            "recipe": "video_cutaway_orange",
            "generate": lambda path: _generate_video(
                path,
                "0xC2410C",
                "drawbox=x=720:y=360:w=480:h=360:color=white:t=fill",
            ),
        },
        {
            "id": "clip.detail-green.v1",
            "role": "detail-broll",
            "kind": "video",
            "filename": "clip-detail-green.mp4",
            "description": (
                "Green full-frame clip with a right-edge white locator block."
            ),
            "recipe": "video_detail_green",
            "generate": lambda path: _generate_video(
                path,
                "0x15803D",
                "drawbox=x=1500:y=180:w=300:h=720:color=white:t=fill",
            ),
        },
        {
            "id": "still.reference-grid.v1",
            "role": "full-frame-still",
            "kind": "still",
            "filename": "still-reference-grid.png",
            "description": "Purple grid still with a centered white reference panel.",
            "recipe": "still_reference_grid",
            "generate": lambda path: _generate_png(path, _reference_grid_row),
        },
        {
            "id": "still.reference-bars.v1",
            "role": "alternate-still",
            "kind": "still",
            "filename": "still-reference-bars.png",
            "description": "Cyan four-band still with a dark horizontal reference bar.",
            "recipe": "still_reference_bars",
            "generate": lambda path: _generate_png(path, _reference_bars_row),
        },
        {
            "id": "audio.ambient-bed.v1",
            "role": "timeline-audio-bed",
            "kind": "audio",
            "filename": "audio-ambient-bed.wav",
            "description": "Three-second stereo synthetic triangle-wave audio bed.",
            "recipe": "audio_ambient_bed",
            "generate": _generate_audio_bed,
        },
    ]


def _build_descriptor(staging_media: Path) -> dict[str, object]:
    assets: list[dict[str, object]] = []
    for spec in _asset_specs():
        path = staging_media / spec["filename"]
        generate = spec["generate"]
        generate(path)
        assets.append(
            {
                "id": spec["id"],
                "role": spec["role"],
                "kind": spec["kind"],
                "path": f"media/{spec['filename']}",
                "description": spec["description"],
                "provenance": _provenance(spec["recipe"]),
                "sha256": sha256_file(path),
                "sizeBytes": path.stat().st_size,
                "media": probe_asset(path, spec["kind"]),
            }
        )
    return {
        "schemaVersion": 1,
        "kitId": "vera.slice-0.1.synthetic-media-kit.v1",
        "description": (
            "Canonical compact synthetic media for Slice 0.2 "
            "handcrafted-timeline tests."
        ),
        "canonicalSettings": CANONICAL_SETTINGS,
        "provenance": _provenance("canonical_kit"),
        "generation": {
            "command": "uv run --frozen python -m fixtures.generate_fixtures",
            "ffmpegVersion": EXPECTED_FFMPEG_VERSION,
            "ffprobeVersion": EXPECTED_FFMPEG_VERSION,
            "versionCaveat": (
                "Checked-in bytes are canonical; exact regeneration also requires "
                "the same linked libx264, FFmpeg build configuration, Python, and "
                "zlib behavior."
            ),
        },
        "assets": assets,
    }


def main() -> int:
    """Generate into staging, then replace only the six declared fixture outputs."""
    actual_versions = {tool: _tool_version(tool) for tool in ("ffmpeg", "ffprobe")}
    wrong_versions = {
        tool: version
        for tool, version in actual_versions.items()
        if version != EXPECTED_FFMPEG_VERSION
    }
    if wrong_versions:
        raise SystemExit(
            f"canonical regeneration requires FFmpeg/FFprobe "
            f"{EXPECTED_FFMPEG_VERSION}; found {wrong_versions}. "
            "Checked-in fixture bytes remain authoritative."
        )

    expected_names = {spec["filename"] for spec in _asset_specs()}
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    undeclared = {path.name for path in MEDIA_DIR.iterdir()} - expected_names
    if undeclared:
        raise SystemExit(
            "refusing to replace media while undeclared files exist: "
            f"{sorted(undeclared)}"
        )

    with tempfile.TemporaryDirectory(
        prefix="fixture-generation-", dir=FIXTURES_DIR
    ) as temporary:
        staging_media = Path(temporary) / "media"
        staging_media.mkdir()
        descriptor = _build_descriptor(staging_media)
        for path in staging_media.iterdir():
            path.replace(MEDIA_DIR / path.name)
        temporary_descriptor = Path(temporary) / DESCRIPTOR_PATH.name
        temporary_descriptor.write_text(
            json.dumps(descriptor, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary_descriptor.replace(DESCRIPTOR_PATH)
    print(f"generated {len(expected_names)} canonical synthetic assets in {MEDIA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
