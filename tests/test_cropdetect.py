from __future__ import annotations

import pytest
from vera_timeline_agent.cropdetect import (
    CropRect,
    CropWindowSample,
    crop_to_fill_transform,
    select_stable_active_rect,
)


def _samples(*rects: CropRect, luma: float = 64.0) -> list[CropWindowSample]:
    return [
        CropWindowSample(f"window-{index}", rect, luma)
        for index, rect in enumerate(rects)
    ]


def test_selects_stable_bounds_from_three_windows_and_computes_minimum_zoom() -> None:
    samples = _samples(
        CropRect(0, 90, 1920, 900),
        CropRect(0, 91, 1920, 898),
        CropRect(0, 90, 1920, 900),
    )

    active = select_stable_active_rect((1920, 1080), samples)

    assert active == CropRect(0, 90, 1920, 900)
    transform = crop_to_fill_transform((1920, 1080), (1920, 1080), active)
    assert transform.zoom == pytest.approx(1.2)
    assert (transform.center_x, transform.center_y) == pytest.approx((0.5, 0.5))
    assert (transform.offset_x, transform.offset_y) == pytest.approx((-192, -108))
    active_center_x = (active.x + active.width / 2) * transform.output_scale
    assert active_center_x + transform.offset_x == pytest.approx(960)
    assert active.bottom * transform.output_scale + transform.offset_y == pytest.approx(
        1080
    )


@pytest.mark.parametrize(
    "samples",
    [
        _samples(CropRect(0, 90, 1920, 900), CropRect(0, 90, 1920, 900)),
        [
            CropWindowSample("same", CropRect(0, 90, 1920, 900), 64),
            CropWindowSample("same", CropRect(0, 90, 1920, 900), 64),
            CropWindowSample("same", CropRect(0, 90, 1920, 900), 64),
        ],
        _samples(
            CropRect(0, 90, 1920, 900),
            CropRect(0, 90, 1920, 900),
            CropRect(0, 90, 1920, 900),
            luma=17.9,
        ),
        _samples(
            CropRect(0, 90, 1920, 900),
            CropRect(0, 90, 1920, 900),
            CropRect(0, 95, 1920, 890),
        ),
    ],
    ids=["too-few-windows", "duplicate-window", "dark-picture", "changing-bounds"],
)
def test_refuses_insufficient_dark_or_changing_evidence(
    samples: list[CropWindowSample],
) -> None:
    assert select_stable_active_rect((1920, 1080), samples) is None


def test_transform_recenters_asymmetric_active_picture() -> None:
    active = CropRect(0, 100, 1920, 890)

    transform = crop_to_fill_transform((1920, 1080), (1920, 1080), active)

    assert transform.zoom == pytest.approx(1080 / 890)
    assert transform.center_y == pytest.approx(545 / 1080)
    assert active.y * transform.output_scale + transform.offset_y == pytest.approx(0)
    assert active.bottom * transform.output_scale + transform.offset_y == pytest.approx(
        1080
    )
    assert (
        (active.y + active.height / 2) * transform.output_scale + transform.offset_y
    ) == pytest.approx(540)


def test_rejects_small_inset_title_like_region_but_accepts_letterbox_bounds() -> None:
    title_samples = _samples(
        CropRect(120, 60, 80, 60),
        CropRect(120, 60, 80, 60),
        CropRect(120, 60, 80, 60),
    )
    letterbox_samples = _samples(
        CropRect(0, 22, 320, 136),
        CropRect(0, 22, 320, 136),
        CropRect(0, 22, 320, 136),
    )

    assert select_stable_active_rect((320, 180), title_samples) is None
    assert select_stable_active_rect((320, 180), letterbox_samples) == CropRect(
        0, 22, 320, 136
    )


def test_refuses_nearly_full_but_all_sides_inset_region() -> None:
    samples = _samples(
        CropRect(2, 20, 316, 140),
        CropRect(2, 20, 316, 140),
        CropRect(2, 20, 316, 140),
    )

    # The bounds cover over 98% of the width but could still describe an inset graphic.
    assert select_stable_active_rect((320, 180), samples) is None


def test_transform_rejects_out_of_bounds_crop() -> None:
    with pytest.raises(ValueError, match="inside source_size"):
        crop_to_fill_transform((1920, 1080), (1920, 1080), CropRect(0, 90, 1920, 1000))
