"""Conservative FFmpeg cropdetect sampling and crop-to-fill geometry.

Analysis reads source media and returns evidence only. It never writes to or
modifies the input file. Symmetric bar geometry is accepted; edge-aligned
graphics can still resemble bars and require human/native-editor judgment.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

MIN_SAMPLE_WINDOWS = 3
MIN_FRAMES_PER_WINDOW = 2
MAX_EDGE_JITTER_PX = 2
MIN_ACTIVE_MEAN_LUMA = 18.0
MIN_DIMENSION_COVERAGE = 0.5
DEFAULT_WINDOW_SECONDS = 0.5
_CROP_RE = re.compile(r"\bcrop=(\d+):(\d+):(\d+):(\d+)")
_YAVG_RE = re.compile(r"\blavfi\.signalstats\.YAVG=([0-9]+(?:\.[0-9]+)?)")


class CropAnalysisError(RuntimeError):
    """Raised when FFmpeg/ffprobe cannot inspect a source file."""


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
    start_seconds: float | None = None
    end_seconds: float | None = None
    frame_count: int | None = None


@dataclass(frozen=True)
class CropDetection:
    """Read-only crop analysis result, with refusal details when unsafe."""

    source_size: tuple[int, int]
    used_range: tuple[float, float]
    samples: tuple[CropWindowSample, ...]
    active_rect: CropRect | None
    refusal_reason: str | None = None

    @property
    def accepted(self) -> bool:
        return self.active_rect is not None


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

    At least three distinct, non-overlapping windows must agree within two
    pixels on every edge. Crops must be symmetric on exactly one axis.
    Dark candidate regions are rejected because crop detectors can mistake dark
    content for bars. The union of agreeing candidates is selected, preserving any
    pixels that appeared active in at least one window. A full-frame result is
    treated as no crop. This intentionally favors leaving a sliver of bar over
    cutting into picture content. To reject inset graphics, each bound must
    cover at least half of both source dimensions and span one full source axis.
    This reduces inset-graphic false detections; it cannot distinguish a
    sufficiently large edge-aligned graphic from baked-in bars.

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
        if (sample.start_seconds is not None or sample.end_seconds is not None) and (
            sample.start_seconds is None
            or sample.end_seconds is None
            or isinstance(sample.start_seconds, bool)
            or isinstance(sample.end_seconds, bool)
            or not isinstance(sample.start_seconds, (int, float))
            or not isinstance(sample.end_seconds, (int, float))
            or not math.isfinite(sample.start_seconds)
            or not math.isfinite(sample.end_seconds)
            or sample.start_seconds < 0
            or sample.start_seconds >= sample.end_seconds
            or type(sample.frame_count) is not int
            or sample.frame_count < MIN_FRAMES_PER_WINDOW
        ):
            return None
        window_ids.add(sample.window_id)
        rects.append(rect)

    intervals = [
        (sample.start_seconds, sample.end_seconds)
        for sample in samples
        if sample.start_seconds is not None and sample.end_seconds is not None
    ]
    if intervals:
        if len(intervals) != len(samples):
            return None
        intervals.sort()
        if any(end > next_start for (_, end), (next_start, _) in pairwise(intervals)):
            return None

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
    ):
        return None
    spans_width = selected.x == 0 and selected.right == source_width
    spans_height = selected.y == 0 and selected.bottom == source_height
    if spans_width == spans_height:
        return None
    if spans_width:
        if (
            selected.y == 0
            or selected.bottom == source_height
            or abs(selected.y - (source_height - selected.bottom)) > MAX_EDGE_JITTER_PX
        ):
            return None
    elif (
        selected.x == 0
        or selected.right == source_width
        or abs(selected.x - (source_width - selected.right)) > MAX_EDGE_JITTER_PX
    ):
        return None
    return selected


def analyze_media(
    path: str | Path,
    used_range: tuple[float, float],
    *,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    window_count: int = MIN_SAMPLE_WINDOWS,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
) -> CropDetection:
    """Sample independent windows in source seconds with FFmpeg cropdetect.

    Each window runs cropdetect with ``reset=0`` so evidence accumulates across
    its frames. Window rectangles are unioned conservatively, then FFmpeg
    measures mean luma inside that candidate region. The used range is
    zero-based, end-exclusive source-media time. Ambiguous evidence is returned
    as a refusal instead of a crop suggestion.
    """
    start, end, window_count, window_seconds = _validate_analysis_args(
        used_range, window_count, window_seconds
    )
    executable = ffmpeg or shutil.which("ffmpeg")
    probe_executable = ffprobe or shutil.which("ffprobe")
    if executable is None or probe_executable is None:
        raise CropAnalysisError("ffmpeg and ffprobe are required for crop analysis")
    media_path = Path(path)
    source_size = _probe_source_size(media_path, probe_executable)
    normalized_range = (float(start), float(end))
    windows = _sample_windows(start, end, window_count, window_seconds)
    samples: list[CropWindowSample] = []
    for index, (window_start, window_end) in enumerate(windows, start=1):
        rects = _detect_window(
            media_path, window_start, window_end, source_size, executable
        )
        if len(rects) < MIN_FRAMES_PER_WINDOW:
            return CropDetection(
                source_size,
                normalized_range,
                tuple(samples),
                None,
                "insufficient_frame_evidence",
            )
        candidate = _union_rects(rects)
        luma_values = _measure_mean_luma(
            media_path, window_start, window_end, candidate, executable
        )
        if len(luma_values) < MIN_FRAMES_PER_WINDOW:
            return CropDetection(
                source_size,
                normalized_range,
                tuple(samples),
                None,
                "insufficient_luma_evidence",
            )
        samples.append(
            CropWindowSample(
                window_id=f"window-{index}",
                active_rect=candidate,
                active_mean_luma=sum(luma_values) / len(luma_values),
                start_seconds=window_start,
                end_seconds=window_end,
                frame_count=min(len(rects), len(luma_values)),
            )
        )

    selected = select_stable_active_rect(source_size, samples)
    return CropDetection(
        source_size,
        normalized_range,
        tuple(samples),
        selected,
        None if selected is not None else _refusal_reason(source_size, samples),
    )


def _validate_analysis_args(
    used_range: tuple[float, float], window_count: int, window_seconds: float
) -> tuple[float, float, int, float]:
    if (
        not isinstance(used_range, tuple)
        or len(used_range) != 2
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in used_range
        )
    ):
        raise ValueError("used_range must be a pair of finite source-second values")
    start, end = float(used_range[0]), float(used_range[1])
    if start < 0 or start >= end:
        raise ValueError("used_range must have a non-negative start before its end")
    if type(window_count) is not int or window_count < MIN_SAMPLE_WINDOWS:
        raise ValueError(f"window_count must be at least {MIN_SAMPLE_WINDOWS}")
    if (
        isinstance(window_seconds, bool)
        or not isinstance(window_seconds, (int, float))
        or not math.isfinite(window_seconds)
        or window_seconds <= 0
    ):
        raise ValueError("window_seconds must be a positive finite number")
    return start, end, window_count, float(window_seconds)


def _probe_source_size(path: Path, ffprobe: str) -> tuple[int, int]:
    result = _run_process(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(path),
        ],
        "ffprobe source dimensions",
    )
    try:
        streams = json.loads(result.stdout)["streams"]
        width, height = streams[0]["width"], streams[0]["height"]
        return _positive_size((width, height), "source_size")
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise CropAnalysisError("ffprobe returned invalid video dimensions") from exc


def _sample_windows(
    start: float, end: float, count: int, requested_width: float
) -> tuple[tuple[float, float], ...]:
    segment_width = (end - start) / count
    width = min(requested_width, segment_width)
    return tuple(
        (
            start + index * segment_width + (segment_width - width) / 2,
            start + index * segment_width + (segment_width + width) / 2,
        )
        for index in range(count)
    )


def _detect_window(
    path: Path,
    start: float,
    end: float,
    source_size: tuple[int, int],
    ffmpeg: str,
) -> list[CropRect]:
    result = _run_process(
        _window_command(
            path,
            start,
            end,
            ffmpeg,
            "cropdetect=limit=0.0941176:round=2:reset=0",
        ),
        "FFmpeg cropdetect",
    )
    rectangles = [
        CropRect(int(x), int(y), int(width), int(height))
        for width, height, x, y in _CROP_RE.findall(result.stderr)
    ]
    source_width, source_height = source_size
    if any(not _valid_rect(rect, source_width, source_height) for rect in rectangles):
        return []
    return rectangles


def _measure_mean_luma(
    path: Path, start: float, end: float, rect: CropRect, ffmpeg: str
) -> list[float]:
    crop = f"crop={rect.width}:{rect.height}:{rect.x}:{rect.y}"
    filters = f"{crop},scale=32:32:flags=area,signalstats,metadata=mode=print"
    result = _run_process(
        _window_command(path, start, end, ffmpeg, filters),
        "FFmpeg active-picture luma measurement",
    )
    return [float(value) for value in _YAVG_RE.findall(result.stderr)]


def _window_command(
    path: Path, start: float, end: float, ffmpeg: str, filters: str
) -> list[str]:
    return [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "info",
        "-ss",
        f"{start:.9f}",
        "-i",
        str(path),
        "-t",
        f"{end - start:.9f}",
        "-map",
        "0:v:0",
        "-vf",
        filters,
        "-an",
        "-sn",
        "-dn",
        "-f",
        "null",
        "-",
    ]


def _run_process(
    command: list[str], operation: str
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CropAnalysisError(f"{operation} could not complete") from exc
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()
        suffix = f": {detail[-1][:300]}" if detail else ""
        raise CropAnalysisError(f"{operation} failed{suffix}")
    return result


def _union_rects(rectangles: Sequence[CropRect]) -> CropRect:
    left = min(rect.x for rect in rectangles)
    top = min(rect.y for rect in rectangles)
    right = max(rect.right for rect in rectangles)
    bottom = max(rect.bottom for rect in rectangles)
    return CropRect(left, top, right - left, bottom - top)


def _refusal_reason(
    source_size: tuple[int, int], samples: Sequence[CropWindowSample]
) -> str:
    if any(sample.active_mean_luma < MIN_ACTIVE_MEAN_LUMA for sample in samples):
        return "active_picture_too_dark"
    width, height = source_size
    if samples and all(
        sample.active_rect == CropRect(0, 0, width, height) for sample in samples
    ):
        return "no_bars_detected"
    return "unstable_or_ambiguous_crop_evidence"


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
    if len(size) != 2 or any(type(value) is not int or value <= 0 for value in size):
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
