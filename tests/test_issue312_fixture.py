"""Cheap fixture topology checks; no media or native process starts."""

from collections import Counter
from pathlib import Path

import pytest
from vera_timeline_agent.issue312_fixture import (
    generate_sources,
    placement_plan,
    reverse_window_plan,
    source_command,
    source_specs,
)


def test_full_density_and_source_distribution() -> None:
    plan = placement_plan()
    assert plan == placement_plan()
    assert plan["narrationRows"] == 30
    assert len(plan["pictures"]) == 60
    assert len(plan["overlays"]) == 12
    assert plan["expectedEvents"] == 102
    assert Counter(s["width"] for s in plan["sources"]) == {1920: 20, 3840: 4}
    assert Counter(s["rate"]["numerator"] for s in plan["sources"]) == {
        24000: 16,
        30000: 8,
    }
    assert len({p["source"] for p in plan["pictures"]}) == 24
    assert Counter(p["row"] for p in plan["pictures"]) == dict.fromkeys(range(30), 2)
    assert plan["edit"] == {"pictureId": "picture-01", "boundaryDeltaFrames": 24}
    assert [p["id"] for p in plan["pictures"] if p["pictureKind"] != "clip"] == [
        "picture-00",
        "picture-01",
    ]
    assert (
        len({p["source"] for p in plan["pictures"] if p["pictureKind"] == "clip"}) == 24
    )


def test_six_row_rehearsal_has_all_source_classes_and_edit() -> None:
    plan = placement_plan(rehearsal=True)
    assert plan["narrationRows"] == 6
    assert len(plan["pictures"]) == 12
    assert len(plan["overlays"]) == 3
    assert {(s["width"], s["rate"]["numerator"]) for s in plan["sources"]} == {
        (1920, 24000),
        (3840, 24000),
        (1920, 30000),
        (3840, 30000),
    }
    assert all(p["audioPolicy"] == "mute" for p in plan["pictures"] + plan["overlays"])
    assert {p["source"] for p in plan["pictures"] if p["pictureKind"] == "clip"} == {
        s["id"] for s in plan["sources"]
    }


def test_source_command_is_silent_bounded_and_refuses_overwrite() -> None:
    spec = source_specs()[0]
    command = source_command(
        spec, Path("source.mp4"), source_seconds=30, ffmpeg="ffmpeg"
    )
    assert "-an" in command and "-n" in command and "-y" not in command
    assert command[command.index("-frames:v") + 1] == "720"
    assert command[command.index("-pix_fmt") + 1] == "yuv420p"
    assert command[command.index("-threads") + 1] == "2"
    with pytest.raises(ValueError, match="duration"):
        source_command(spec, Path("source.mp4"), source_seconds=0, ffmpeg="ffmpeg")


def test_reverse_window_preserves_video_classes_and_measured_boundary_anchors() -> None:
    plan = reverse_window_plan()
    assert plan["narrationRows"] == 3
    assert plan["expectedEvents"] == 11
    assert plan["pictures"][1]["start"]["tokenIndex"] == 30
    assert plan["boundaryWordAnchors"] == {
        "beforeTokenIndex": 30,
        "afterTokenIndex": 32,
    }
    placed_videos = {
        p["source"] for p in plan["pictures"] if p["pictureKind"] == "clip"
    } | {p["source"] for p in plan["overlays"]}
    assert {
        (s["width"], s["rate"]["numerator"])
        for s in plan["sources"]
        if s["id"] in placed_videos
    } == {(1920, 24000), (3840, 24000), (1920, 30000), (3840, 30000)}


def test_generation_refuses_existing_and_symlink_outputs(tmp_path: Path) -> None:
    with pytest.raises(FileExistsError):
        generate_sources(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic"):
        generate_sources(link / "new")
