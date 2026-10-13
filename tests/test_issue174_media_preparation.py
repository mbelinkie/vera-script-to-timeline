from fractions import Fraction
from pathlib import Path

import pytest
from issue174_media_fixture import generate_synthetic_media
from vera_timeline_agent.media_preparation import (
    MediaPreparationError,
    MediaTools,
    inspect_media,
    preparation_geometry,
    verify_video_cadence,
)


@pytest.mark.slow
def test_real_source_inspection(tmp_path: Path) -> None:
    fixture = generate_synthetic_media(tmp_path, frame_count=60)
    inspected = inspect_media(
        fixture.path, video_stream_index=0, audio_stream_index=None, tools=MediaTools()
    )
    assert inspected.rate == 25
    assert inspected.pts_origin == 0
    assert len(inspected.video_frames) == 60


def test_exact_geometry_and_nonzero_origins() -> None:
    geometry = preparation_geometry(
        source_rate=Fraction(25),
        target_rate=Fraction(24000, 1001),
        origin_frame=3000,
        lower_frame=3000,
        upper_frame=3300,
        in_frame=3010,
        duration=Fraction(1001, 100),
    )
    assert geometry.start == Fraction(2, 5)
    assert geometry.end == Fraction(1041, 100)
    assert geometry.required_end_frame == 3261
    assert geometry.frame_count == 240
    assert geometry.selected_package_frame(239) == 259
    assert geometry.cover_surplus == Fraction(3, 100)


@pytest.mark.parametrize("rate,count", [(25, 250), (30, 300)])
def test_complete_clip_endpoint(rate: int, count: int) -> None:
    geometry = preparation_geometry(
        source_rate=Fraction(rate),
        target_rate=Fraction(24000, 1001),
        origin_frame=0,
        lower_frame=0,
        upper_frame=count,
        in_frame=0,
        duration=Fraction(count, rate),
    )
    assert geometry.frame_count == 240
    assert geometry.terminal_quantization == Fraction(1, 100)
    assert geometry.cover_surplus == 0
    assert Fraction(geometry.selected_package_frame(239), rate) < geometry.end


def test_short_source_and_missing_handles_refuse() -> None:
    with pytest.raises(MediaPreparationError, match="source_shortage"):
        preparation_geometry(
            source_rate=Fraction(25),
            target_rate=Fraction(24000, 1001),
            origin_frame=0,
            lower_frame=0,
            upper_frame=250,
            in_frame=0,
            duration=Fraction(1001, 100),
        )
    with pytest.raises(MediaPreparationError, match="source_shortage"):
        preparation_geometry(
            source_rate=Fraction(25),
            target_rate=Fraction(24000, 1001),
            origin_frame=0,
            lower_frame=0,
            upper_frame=100,
            in_frame=0,
            duration=Fraction(1),
            pre_handle=Fraction(1001, 24000),
        )


def test_tick_bounded_cfr_but_false_labels_vfr_and_duplicates_refuse() -> None:
    # Matroska can quantize a true 23.976 cadence to millisecond ticks.
    times = [round(n * Fraction(1001, 24)) for n in range(60)]
    frames = [{"pts": pts, "duration": 42, "interlaced_frame": 0} for pts in times]
    verify_video_cadence(frames, Fraction(24000, 1001), Fraction(1, 1000))
    for replacement in (times[12] + 10, times[11]):
        changed = [dict(frame) for frame in frames]
        changed[12]["pts"] = replacement
        with pytest.raises(MediaPreparationError, match="unsupported_vfr_or_timebase"):
            verify_video_cadence(changed, Fraction(24000, 1001), Fraction(1, 1000))


def test_unqualified_conversion_and_fractional_target_handle_refuse() -> None:
    with pytest.raises(MediaPreparationError, match="unsupported_conversion"):
        preparation_geometry(
            source_rate=Fraction(50),
            target_rate=Fraction(24000, 1001),
            origin_frame=0,
            lower_frame=0,
            upper_frame=100,
            in_frame=0,
            duration=Fraction(1),
        )
    with pytest.raises(MediaPreparationError, match="unsupported_handles"):
        preparation_geometry(
            source_rate=Fraction(25),
            target_rate=Fraction(24000, 1001),
            origin_frame=0,
            lower_frame=0,
            upper_frame=100,
            in_frame=5,
            duration=Fraction(1),
            pre_handle=Fraction(1, 100),
        )
