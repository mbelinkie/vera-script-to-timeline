"""Conservative, offline crop selection and crop-to-fill geometry.

The caller supplies candidate active-picture bounds and mean 8-bit luma for
independent time windows. This unintegrated draft does not inspect media or
apply edits; fixture evidence and native save/reopen proof are still required.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

MIN_SAMPLE_WINDOWS = 3
MAX_EDGE_JITTER_PX = 2
MIN_ACTIVE_MEAN_LUMA = 18.0
MIN_DIMENSION_COVERAGE = 0.5
MIN_FULL_AXIS_COVERAGE = 0.98
# shortcut: static edge-aligned title cards can still resemble active picture.


@dataclass(frozen=True)
class CropRect:
    """An integer rectangle in source-pixel coordinates."""

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass(frozen=True)
class CropWindowSample:
    """Candidate active bounds and their mean luma for one independent window."""

    window_id: str
    active_rect: CropRect
    active_mean_luma: float


@dataclass(frozen=True)
class CropTransform:
    """Uniform source-to-output transform that centers and fills the active area.

    ``zoom`` is magnification relative to contain-fitting the full source.
    Pixel coordinates map as ``(x * output_scale + offset_x,
    y * output_scale + offset_y)``.
    """

    active_rect: CropRect
    zoom: float
    center_x: float
    center_y: float
    output_scale: float
    offset_x: float
    offset_y: float


def select_stable_active_rect(
    source_size: tuple[int, int], samples: Sequence[CropWindowSample]
) -> CropRect | None:
    """Return stable bounds, or ``None`` when the evidence is unsafe to use.

    At least three distinct windows must agree within two pixels on every edge.
    Dark candidate regions are rejected because crop detectors can mistake dark
    content for bars. The union of agreeing candidates is selected, preserving any
    pixels that appeared active in at least one window. A full-frame result is
    treated as no crop. This intentionally favors leaving a sliver of bar over
    cutting into picture content. To reject small inset graphics, each bound
    must cover at least half of both source dimensions and nearly all of one.

    ``active_mean_luma`` is an upstream measurement on an 8-bit 0..255 scale.
    """
    source_width, source_height = _positive_size(source_size, "source_size")
    if len(samples) < MIN_SAMPLE_WINDOWS:
        return None

    window_ids: set[str] = set()
    rects: list[CropRect] = []
    for sample in samples:
        if not isinstance(sample, CropWindowSample) or not isinstance(
            sample.active_rect, CropRect
        ):
            return None
        rect = sample.active_rect
        luma = sample.active_mean_luma
        if (
            not isinstance(sample.window_id, str)
            or not sample.window_id
            or sample.window_id in window_ids
            or not _valid_rect(rect, source_width, source_height)
            or isinstance(luma, bool)
            or not isinstance(luma, (int, float))
            or not math.isfinite(luma)
            or not MIN_ACTIVE_MEAN_LUMA <= luma <= 255
        ):
            return None
        window_ids.add(sample.window_id)
        rects.append(rect)

    edges = (
        [rect.x for rect in rects],
        [rect.y for rect in rects],
        [rect.right for rect in rects],
        [rect.bottom for rect in rects],
    )
    if any(max(edge) - min(edge) > MAX_EDGE_JITTER_PX for edge in edges):
        return None

    x_edges, y_edges, right_edges, bottom_edges = edges
    selected = CropRect(
        min(x_edges),
        min(y_edges),
        max(right_edges) - min(x_edges),
        max(bottom_edges) - min(y_edges),
    )
    if selected == CropRect(0, 0, source_width, source_height):
        return None
    if (
        selected.width / source_width < MIN_DIMENSION_COVERAGE
        or selected.height / source_height < MIN_DIMENSION_COVERAGE
        or max(
            selected.width / source_width,
            selected.height / source_height,
        )
        < MIN_FULL_AXIS_COVERAGE
    ):
        return None
    return selected


def crop_to_fill_transform(
    source_size: tuple[int, int],
    output_size: tuple[int, int],
    active_rect: CropRect,
) -> CropTransform:
    """Compute minimum uniform zoom and translation to center ``active_rect``.

    The baseline is a contain-fit of the full source. The returned multiplier
    increases that baseline only enough for the active rectangle to cover the
    output. This is geometry only; it does not account for an editor's native
    coordinate conventions or a separately authored framing transform.
    """
    source_width, source_height = _positive_size(source_size, "source_size")
    output_width, output_height = _positive_size(output_size, "output_size")
    if not _valid_rect(active_rect, source_width, source_height):
        raise ValueError("active_rect must be positive and inside source_size")

    contain_scale = min(output_width / source_width, output_height / source_height)
    output_scale = max(
        output_width / active_rect.width,
        output_height / active_rect.height,
    )
    center_x = (active_rect.x + active_rect.width / 2) / source_width
    center_y = (active_rect.y + active_rect.height / 2) / source_height
    return CropTransform(
        active_rect=active_rect,
        zoom=output_scale / contain_scale,
        center_x=center_x,
        center_y=center_y,
        output_scale=output_scale,
        offset_x=output_width / 2 - center_x * source_width * output_scale,
        offset_y=output_height / 2 - center_y * source_height * output_scale,
    )


def _positive_size(size: tuple[int, int], label: str) -> tuple[int, int]:
    if (
        len(size) != 2
        or any(type(value) is not int or value <= 0 for value in size)
    ):
        raise ValueError(f"{label} must contain two positive integers")
    return size


def _valid_rect(rect: CropRect, width: int, height: int) -> bool:
    return (
        type(rect.x) is int
        and type(rect.y) is int
        and type(rect.width) is int
        and type(rect.height) is int
        and rect.x >= 0
        and rect.y >= 0
        and rect.width > 0
        and rect.height > 0
        and rect.right <= width
        and rect.bottom <= height
    )
