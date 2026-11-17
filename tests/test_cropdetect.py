from __future__ import annotations

import math

import pytest
from vera_timeline_agent.cropdetect import (
    DETECTOR_VERSION,
    CropFrameSample,
    CropRect,
    crop_to_fill_transform,
    evaluate_crop_samples,
    thresholds_hash,
)

SOURCE_SIZE = (320, 180)
LETTERBOX = CropRect(0, 23, 320, 134)


def _samples(
    rect: CropRect = LETTERBOX,
    *,
    count: int = 20,
    mean_luma: float = 100,
    informative_count: int | None = None,
    bar_max: int | None = 16,
    bar_stddev: float | None = 0,
) -> list[CropFrameSample]:
    informative_count = count if informative_count is None else informative_count
    return [
        CropFrameSample(
            frame_index=index,
            pts_seconds=index / 6,
            active_rect=rect,
            active_mean_luma=mean_luma,
            informative=index < informative_count,
            bar_max_luma=bar_max,
            bar_stddev_luma=bar_stddev,
        )
        for index in range(count)
    ]


def test_accepts_flat_symmetric_tv_bars_and_rounds_zoom_up() -> None:
    result = evaluate_crop_samples(SOURCE_SIZE, SOURCE_SIZE, "tv", _samples())

    assert result.active_rect == LETTERBOX
    assert result.refusal_reason is None
    assert result.zoom == 1.3433


def test_requires_twelve_frames_and_eighty_percent_informative_frames() -> None:
    too_few = evaluate_crop_samples(SOURCE_SIZE, SOURCE_SIZE, "tv", _samples(count=11))
    too_dark = evaluate_crop_samples(
        SOURCE_SIZE,
        SOURCE_SIZE,
        "tv",
        _samples(count=20, informative_count=15),
    )

    assert too_few.refusal_reason == "insufficient_evidence"
    assert too_dark.refusal_reason == "too_dark"


def test_refuses_informative_frame_geometry_outlier_but_allows_two_pixels() -> None:
    at_limit = _samples()
    at_limit[-1] = CropFrameSample(
        frame_index=19,
        pts_seconds=19 / 6,
        active_rect=CropRect(0, 25, 320, 130),
        active_mean_luma=100,
        informative=True,
        bar_max_luma=16,
        bar_stddev_luma=0,
    )
    over_limit = _samples()
    over_limit[-1] = CropFrameSample(
        frame_index=19,
        pts_seconds=19 / 6,
        active_rect=CropRect(0, 26, 320, 128),
        active_mean_luma=100,
        informative=True,
        bar_max_luma=16,
        bar_stddev_luma=0,
    )

    assert evaluate_crop_samples(SOURCE_SIZE, SOURCE_SIZE, "tv", at_limit).accepted
    assert (
        evaluate_crop_samples(SOURCE_SIZE, SOURCE_SIZE, "tv", over_limit).refusal_reason
        == "changing"
    )


@pytest.mark.parametrize(
    ("color_range", "maximum", "stddev"),
    [("tv", 25, 0), ("pc", 9, 0), ("tv", 16, 1.51)],
    ids=["tv-bar-not-black", "pc-bar-not-black", "bar-noise"],
)
def test_rejects_non_black_or_noisy_bars(
    color_range: str, maximum: int, stddev: float
) -> None:
    result = evaluate_crop_samples(
        SOURCE_SIZE,
        SOURCE_SIZE,
        color_range,
        _samples(bar_max=maximum, bar_stddev=stddev),
    )

    assert result.refusal_reason == "not_flat_black"


@pytest.mark.parametrize(
    "rect",
    [
        CropRect(0, 10, 320, 134),  # asymmetric top and bottom bars
        CropRect(0, 0, 320, 172),  # bar is too thin
        CropRect(2, 23, 316, 134),  # windowboxed on both axes
    ],
    ids=["asymmetric", "thin-bars", "inset"],
)
def test_rejects_unsafe_geometry(rect: CropRect) -> None:
    result = evaluate_crop_samples(SOURCE_SIZE, SOURCE_SIZE, "tv", _samples(rect))

    assert result.refusal_reason == "invalid_geometry"


def test_caps_zoom_and_refuses_aspect_or_timeline_mismatch() -> None:
    portrait = CropRect(110, 0, 100, 180)
    over_zoom = evaluate_crop_samples(
        SOURCE_SIZE, SOURCE_SIZE, "tv", _samples(portrait)
    )
    unsupported_aspect = evaluate_crop_samples(
        SOURCE_SIZE,
        SOURCE_SIZE,
        "tv",
        _samples(CropRect(0, 20, 320, 140)),
    )
    route_unproven = evaluate_crop_samples(SOURCE_SIZE, (320, 240), "tv", _samples())

    assert over_zoom.refusal_reason == "zoom_exceeds_limit"
    assert over_zoom.zoom == 3.2
    assert unsupported_aspect.refusal_reason == "nonstandard_aspect"
    assert route_unproven.refusal_reason == "route_unproven"


def test_threshold_hash_and_crop_to_fill_geometry_are_stable() -> None:
    transform = crop_to_fill_transform(
        (1920, 1080), (1920, 1080), CropRect(0, 90, 1920, 900)
    )

    assert DETECTOR_VERSION == "cropdetect-v2"
    assert thresholds_hash() == thresholds_hash()
    assert len(thresholds_hash()) == 64
    assert transform.zoom == pytest.approx(1.2)
    assert (transform.center_x, transform.center_y) == pytest.approx((0.5, 0.5))
    assert (transform.offset_x, transform.offset_y) == pytest.approx((-192, -108))
    assert not math.isnan(transform.zoom)


def test_transform_rejects_out_of_bounds_crop() -> None:
    with pytest.raises(ValueError, match="inside source_size"):
        crop_to_fill_transform((1920, 1080), (1920, 1080), CropRect(0, 90, 1920, 1000))
