"""Offline harness tests: do not confuse with installed Studio raster proof."""

from __future__ import annotations

import copy
import json
import struct
import zlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts.issue336_studio_qualify import (
    empty_disposable_project,
    png,
    write_otio,
)


def _pixel(path: Path, x: int, y: int) -> tuple[int, int, int]:
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    payload = bytearray()
    while offset < len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        chunk = data[offset + 4 : offset + 8]
        if chunk == b"IDAT":
            payload.extend(data[offset + 8 : offset + 8 + length])
        offset += length + 12
    stride = 1 + 3 * struct.unpack_from(">I", data, 16)[0]
    uncompressed = zlib.decompress(payload)
    assert uncompressed[stride * y] == 0
    at = stride * y + 1 + 3 * x
    return tuple(uncompressed[at : at + 3])  # type: ignore[return-value]


def test_public_synthetic_grid_has_distinct_edge_and_focus_witnesses(
    tmp_path: Path,
) -> None:
    for name, width, height in (
        ("square", 1000, 1000),
        ("wide", 1600, 900),
        ("tall", 900, 1600),
    ):
        target = tmp_path / (name + ".png")
        png(target, width, height)
        assert struct.unpack_from(">II", target.read_bytes(), 16) == (width, height)
        assert _pixel(target, 10, 10) == (245, 24, 20)
        assert _pixel(target, width - 10, 10) == (20, 240, 25)
        assert _pixel(target, 10, height - 10) == (24, 35, 245)
        assert _pixel(target, width - 10, height - 10) == (245, 240, 15)
        assert _pixel(target, int(width * 0.75), int(height * 0.3)) == (
            245,
            25,
            245,
        )


def _fixture() -> dict[str, Any]:
    return {
        "name": "public-test",
        "tracks": {
            "children": [
                {
                    "name": "Video 1",
                    "children": [
                        {
                            "name": "first",
                            "source_range": {"duration": {"value": 24}},
                            "media_references": {
                                "DEFAULT_MEDIA": {
                                    "target_url": "/old/image.png",
                                    "name": "image.png",
                                }
                            },
                            "effects": [
                                {
                                    "metadata": {
                                        "Resolve_OTIO": {
                                            "Type": 59,
                                            "Enabled": True,
                                            "Parameters": [
                                                {
                                                    "Parameter ID": "dynamicZoomCenter",
                                                    "Parameter Value": [0, 0],
                                                    "Key Frames": {
                                                        "-86400": {"Value": [0, 0]},
                                                        "-85400": {"Value": [0, 0]},
                                                    },
                                                },
                                                {
                                                    "Parameter ID": "dynamicZoomScale",
                                                    "Parameter Value": 1.0,
                                                    "Key Frames": {
                                                        "-86400": {"Value": 0.8},
                                                        "-85400": {"Value": 1.0},
                                                    },
                                                },
                                            ],
                                        }
                                    }
                                },
                                {
                                    "metadata": {
                                        "Resolve_OTIO": {
                                            "Type": 22,
                                            "Parameters": [
                                                {
                                                    "Parameter ID": "scale",
                                                    "Parameter Value": 3,
                                                }
                                            ],
                                        }
                                    }
                                },
                            ],
                        },
                        {"name": "unrelated-old-target"},
                    ],
                },
                {"name": "Audio 1", "children": [{"name": "legacy-audio"}]},
            ]
        },
    }


def test_standalone_otio_probe_never_mutates_prior_template_or_imports_audio(
    tmp_path: Path,
) -> None:
    original = _fixture()
    expected = copy.deepcopy(original)
    source = tmp_path / "public.png"
    for motion, framing, frames in ((True, "fit", 48), (False, "fill", 144)):
        out = tmp_path / f"{motion}-{framing}-{frames}.otio"
        write_otio(
            original, out, source, frames, motion=motion, ease=0, framing=framing
        )
        parsed = json.loads(out.read_text())
        assert len(parsed["tracks"]["children"]) == 1
        clips = parsed["tracks"]["children"][0]["children"]
        assert len(clips) == 1
        assert clips[0]["source_range"]["duration"]["value"] == frames
        assert clips[0]["media_references"]["DEFAULT_MEDIA"]["target_url"] == str(
            source.resolve()
        )
        effects = [effect["metadata"]["Resolve_OTIO"] for effect in clips[0]["effects"]]
        assert effects[0]["Type"] == 59
        assert effects[0]["Enabled"] is motion
        assert effects[0]["Parameters"][0]["Key Frames"]["-85400"]["Value"] == [
            0.12,
            -0.08,
        ]
        assert effects[0]["Parameters"][1]["Key Frames"]["-85400"]["Value"] == 1.05
        assert effects[1]["Parameters"][0]["Parameter Value"] == (
            2 if framing == "fit" else 3
        )
    assert original == expected


@pytest.mark.parametrize(
    ("timeline_count", "clips", "folders", "jobs", "rendering", "is_empty"),
    [
        (0, [], [], [], False, True),
        (1, [], [], [], False, False),
        (0, [object()], [], [], False, False),
        (0, [], [object()], [], False, False),
        (0, [], [], [{"JobId": "prior"}], False, False),
        (0, [], [], [], True, False),
        (0, [], [], [], None, False),
    ],
)
def test_adoption_refuses_any_nonempty_or_uncertain_existing_project(
    timeline_count: int,
    clips: list[Any],
    folders: list[Any],
    jobs: list[Any],
    rendering: bool | None,
    is_empty: bool,
) -> None:
    folder = SimpleNamespace(
        GetClipList=lambda: clips, GetSubFolderList=lambda: folders
    )
    media = SimpleNamespace(GetRootFolder=lambda: folder)
    project = SimpleNamespace(
        GetMediaPool=lambda: media,
        GetTimelineCount=lambda: timeline_count,
        GetRenderJobList=lambda: jobs,
        IsRenderingInProgress=lambda: rendering,
    )
    assert empty_disposable_project(project) is is_empty
