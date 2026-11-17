"""Read-only, whole-range detection of symmetric black bars in video clips."""

from __future__ import annotations

import hashlib
import json
import math
import queue
import re
import shutil
import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from statistics import median
from typing import IO

import numpy as np

DETECTOR_VERSION = "cropdetect-v2"
MIN_ANALYZED_FRAMES = 12
SAMPLE_RATE_FPS = 6
MIN_INFORMATIVE_PERCENT = 0.8
INFORMATIVE_LUMA_DELTA = 24
MAX_BAR_LUMA_DELTA = 8
MAX_BAR_STDDEV = 1.5
BAR_GUARD_PX = 2
MAX_EDGE_JITTER_PX = 2
MAX_EDGE_JITTER_RATIO = 0.005
MIN_BAR_SIZE_PX = 4
MIN_BAR_SIZE_RATIO = 0.01
MIN_DIMENSION_COVERAGE = 0.5
MAX_ZOOM = 1.40
ZOOM_DECIMAL_PLACES = 4
MAX_SOURCE_TIMELINE_ASPECT_ERROR = 0.005
CROPDETECT_LIMIT_TV = 40 / 255
CROPDETECT_LIMIT_PC = 24 / 255
_CROP_RE = re.compile(r"\bt:([+-]?[0-9.]+).*?\bcrop=(\d+):(\d+):(\d+):(\d+)")
_CROP_MARKER_RE = re.compile(r"\bcrop=")
_SHOWINFO_RE = re.compile(r"\bn:\s*(\d+)\s+pts:\s*\S+\s+pts_time:([+-]?[0-9.]+)")
_THRESHOLDS = {
    "detectorVersion": DETECTOR_VERSION,
    "minAnalyzedFrames": MIN_ANALYZED_FRAMES,
    "sampleRateFps": SAMPLE_RATE_FPS,
    "minInformativePercent": MIN_INFORMATIVE_PERCENT,
    "informativeLumaDelta": INFORMATIVE_LUMA_DELTA,
    "maxBarLumaDelta": MAX_BAR_LUMA_DELTA,
    "maxBarStddev": MAX_BAR_STDDEV,
    "barGuardPx": BAR_GUARD_PX,
    "maxEdgeJitterPx": MAX_EDGE_JITTER_PX,
    "maxEdgeJitterRatio": MAX_EDGE_JITTER_RATIO,
    "minBarSizePx": MIN_BAR_SIZE_PX,
    "minBarSizeRatio": MIN_BAR_SIZE_RATIO,
    "minDimensionCoverage": MIN_DIMENSION_COVERAGE,
    "maxZoom": MAX_ZOOM,
    "zoomDecimalPlaces": ZOOM_DECIMAL_PLACES,
    "maxSourceTimelineAspectError": MAX_SOURCE_TIMELINE_ASPECT_ERROR,
    "cropdetectMode": "black",
    "cropdetectRound": 1,
    "cropdetectReset": 1,
    "cropdetectSkip": 0,
    "cropdetectLimitTv": CROPDETECT_LIMIT_TV,
    "cropdetectLimitPc": CROPDETECT_LIMIT_PC,
}


def thresholds_hash() -> str:
    """Return the stable SHA-256 of all crop decision thresholds/settings."""
    payload = json.dumps(_THRESHOLDS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
class CropFrameSample:
    """Deterministic evidence for one sampled source frame."""

    frame_index: int
    pts_seconds: float
    active_rect: CropRect
    active_mean_luma: float
    informative: bool
    bar_max_luma: int | None
    bar_stddev_luma: float | None
    cropdetect_rect: CropRect | None = None


# Kept as a compatibility alias for existing draft callers; samples are now
# per-frame evidence rather than independent-window summaries.
CropWindowSample = CropFrameSample


@dataclass(frozen=True)
class CropDetection:
    """Read-only analysis result; ``active_rect`` is set only on full acceptance."""

    source_size: tuple[int, int]
    used_range: tuple[float, float]
    samples: tuple[CropFrameSample, ...]
    active_rect: CropRect | None
    refusal_reason: str | None = None
    zoom: float | None = None
    color_range: str | None = None
    frame_rate: tuple[int, int] | None = None
    sample_stride: int | None = None
    source_frame_count: int | None = None

    @property
    def accepted(self) -> bool:
        return self.active_rect is not None


@dataclass(frozen=True)
class CropAssessment:
    """Pure decision from sampled frame evidence."""

    active_rect: CropRect | None
    refusal_reason: str | None
    zoom: float | None

    @property
    def accepted(self) -> bool:
        return self.active_rect is not None


@dataclass(frozen=True)
class CropTransform:
    """Uniform source-to-output transform centered on an active-picture rect."""

    active_rect: CropRect
    zoom: float
    center_x: float
    center_y: float
    output_scale: float
    offset_x: float
    offset_y: float


@dataclass(frozen=True)
class _Probe:
    size: tuple[int, int]
    sample_aspect: Fraction | None
    color_range: str | None
    frame_rate: Fraction | None
    start_time: float | None


def analyze_media(
    path: str | Path,
    used_range: tuple[float, float],
    *,
    timeline_size: tuple[int, int] | None = None,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> CropDetection:
    """Analyze the whole source-time range at about six frames per second.

    Times are zero-based, end-exclusive source-media seconds. Every selected
    frame must produce one cropdetect record, land on the expected PTS, and have
    corresponding luma evidence. The input is read only. Uncertain media
    evidence is returned as a refusal; tool/probe failures raise
    :class:`CropAnalysisError`.
    """
    start, end = _validate_used_range(used_range)
    source_range = (start, end)
    if timeline_size is not None:
        _positive_size(timeline_size, "timeline_size")
    ffmpeg_path = ffmpeg or shutil.which("ffmpeg")
    ffprobe_path = ffprobe or shutil.which("ffprobe")
    if ffmpeg_path is None or ffprobe_path is None:
        raise CropAnalysisError("ffmpeg and ffprobe are required for crop analysis")

    media_path = Path(path)
    probe = _probe_media(media_path, ffprobe_path)
    if probe.sample_aspect != 1:
        return _refused(probe, source_range, "non_square_pixels")
    if probe.color_range not in {"tv", "pc"}:
        return _refused(probe, source_range, "unsupported_color_range")
    if probe.frame_rate is None or probe.frame_rate <= 0:
        return _refused(probe, source_range, "insufficient_evidence")

    exact_frame_count = (end - start) * float(probe.frame_rate)
    frame_count = round(exact_frame_count)
    if abs(exact_frame_count - frame_count) > 1e-4:
        return _refused(probe, source_range, "range_not_frame_aligned")
    stride = max(1, round(float(probe.frame_rate) / SAMPLE_RATE_FPS))
    expected_sample_count = math.ceil(frame_count / stride)
    rate_pair = (probe.frame_rate.numerator, probe.frame_rate.denominator)
    if expected_sample_count < MIN_ANALYZED_FRAMES:
        return _refused(
            probe,
            source_range,
            "insufficient_evidence",
            sample_stride=stride,
            source_frame_count=frame_count,
        )

    limit = CROPDETECT_LIMIT_TV if probe.color_range == "tv" else CROPDETECT_LIMIT_PC
    frame_records = _read_crop_records(
        media_path,
        start,
        end,
        stride,
        probe.size,
        ffmpeg_path,
        limit,
    )
    if len(frame_records) != expected_sample_count:
        reason = "insufficient_evidence"
        if (
            frame_records
            and abs(frame_records[0][0] - start) > (1 / float(probe.frame_rate) / 2)
        ) or (
            probe.start_time is not None
            and abs(probe.start_time) > (1 / float(probe.frame_rate) / 2)
        ):
            reason = "range_clock_mismatch"
        return _refused(
            probe,
            source_range,
            reason,
            (),
            rate_pair,
            stride,
            frame_count,
        )

    frame_period = 1 / float(probe.frame_rate)
    for index, (pts, rect) in enumerate(frame_records):
        expected_pts = start + index * stride * frame_period
        if (
            abs(pts - expected_pts) > frame_period / 2
            or pts < start - frame_period / 2
            or pts >= end
            or not _valid_rect(rect, *probe.size)
        ):
            return _refused(
                probe,
                source_range,
                "range_clock_mismatch",
                (),
                rate_pair,
                stride,
                frame_count,
            )

    samples = _read_luma_samples(
        media_path,
        start,
        end,
        stride,
        probe.size,
        probe.color_range,
        frame_records,
        ffmpeg_path,
    )
    if len(samples) != expected_sample_count:
        return _refused(
            probe,
            source_range,
            "insufficient_evidence",
            samples,
            rate_pair,
            stride,
            frame_count,
        )

    assessment = evaluate_crop_samples(
        probe.size, timeline_size, probe.color_range, samples
    )
    if not assessment.accepted:
        return _refused(
            probe,
            source_range,
            assessment.refusal_reason or "insufficient_evidence",
            samples,
            rate_pair,
            stride,
            frame_count,
            zoom=assessment.zoom,
        )

    return CropDetection(
        source_size=probe.size,
        used_range=source_range,
        samples=tuple(samples),
        active_rect=assessment.active_rect,
        zoom=assessment.zoom,
        color_range=probe.color_range,
        frame_rate=rate_pair,
        sample_stride=stride,
        source_frame_count=frame_count,
    )


class CropAnalysisError(RuntimeError):
    """Raised when FFmpeg/ffprobe cannot inspect a source file."""


def evaluate_crop_samples(
    source_size: tuple[int, int],
    timeline_size: tuple[int, int] | None,
    color_range: str,
    samples: Sequence[CropFrameSample],
) -> CropAssessment:
    """Apply the deterministic R3-R8 confidence rules to frame evidence."""
    width, height = _positive_size(source_size, "source_size")
    if color_range not in {"tv", "pc"}:
        return CropAssessment(None, "unsupported_color_range", None)
    if len(samples) < MIN_ANALYZED_FRAMES:
        return CropAssessment(None, "insufficient_evidence", None)
    if any(
        not isinstance(sample, CropFrameSample)
        or not _valid_rect(sample.active_rect, width, height)
        or not math.isfinite(sample.active_mean_luma)
        for sample in samples
    ):
        return CropAssessment(None, "insufficient_evidence", None)

    reference_rect = _median_rect([sample.active_rect for sample in samples])
    informative = [sample for sample in samples if sample.informative]
    if len(informative) / len(samples) < MIN_INFORMATIVE_PERCENT:
        return CropAssessment(None, "too_dark", None)
    if not _informative_rects_stable(informative, reference_rect, source_size):
        return CropAssessment(None, "changing", None)
    if _has_bars(reference_rect, source_size) and any(
        sample.bar_max_luma is None
        or sample.bar_stddev_luma is None
        or sample.bar_max_luma > _black_level(color_range) + MAX_BAR_LUMA_DELTA
        or sample.bar_stddev_luma > MAX_BAR_STDDEV
        for sample in samples
    ):
        return CropAssessment(None, "not_flat_black", None)

    geometry_reason = _geometry_refusal(
        reference_rect, source_size, check_coverage=False
    )
    if geometry_reason is not None:
        return CropAssessment(None, geometry_reason, None)
    zoom = _zoom_for_samples(informative, reference_rect, source_size)
    if zoom > MAX_ZOOM:
        return CropAssessment(None, "zoom_exceeds_limit", zoom)
    if (
        reference_rect.width / width < MIN_DIMENSION_COVERAGE
        or reference_rect.height / height < MIN_DIMENSION_COVERAGE
    ):
        return CropAssessment(None, "invalid_geometry", zoom)
    if timeline_size is None or not _same_aspect(source_size, timeline_size):
        return CropAssessment(None, "route_unproven", zoom)
    return CropAssessment(reference_rect, None, zoom)


def _validate_used_range(used_range: tuple[float, float]) -> tuple[float, float]:
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
    return start, end


def _probe_media(path: Path, ffprobe: str) -> _Probe:
    result = _run_process(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,sample_aspect_ratio,color_range,avg_frame_rate,r_frame_rate:format=start_time",
            "-of",
            "json",
            str(path),
        ],
        "ffprobe source metadata",
    )
    try:
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
        size = _positive_size((stream["width"], stream["height"]), "source_size")
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise CropAnalysisError("ffprobe returned invalid video metadata") from exc
    return _Probe(
        size=size,
        sample_aspect=_parse_fraction(stream.get("sample_aspect_ratio"), ":"),
        color_range=stream.get("color_range"),
        frame_rate=_parse_fraction(stream.get("avg_frame_rate"), "/")
        or _parse_fraction(stream.get("r_frame_rate"), "/"),
        start_time=_parse_float(payload.get("format", {}).get("start_time")),
    )


def _parse_fraction(value: object, separator: str) -> Fraction | None:
    if not isinstance(value, str) or separator not in value:
        return None
    numerator, denominator = value.split(separator, 1)
    try:
        fraction = Fraction(int(numerator), int(denominator))
    except (ValueError, ZeroDivisionError):
        return None
    return fraction if fraction > 0 else None


def _parse_float(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _read_crop_records(
    path: Path,
    start: float,
    end: float,
    stride: int,
    size: tuple[int, int],
    ffmpeg: str,
    limit: float,
) -> list[tuple[float, CropRect]]:
    selection = _select_filter(stride)
    filtergraph = f"{selection},cropdetect=limit={limit:.9f}:round=1:reset=1:skip=0"
    command = _ffmpeg_prefix(path, start, end, ffmpeg)
    command.extend(["-vf", filtergraph, "-fps_mode", "passthrough", "-f", "null", "-"])
    result = _run_process(command, "FFmpeg cropdetect")
    lines = [
        line for line in result.stderr.splitlines() if _CROP_MARKER_RE.search(line)
    ]
    records: list[tuple[float, CropRect]] = []
    for line in lines:
        match = _CROP_RE.search(line)
        if match is None:
            return []
        pts, width, height, x, y = match.groups()
        try:
            rect = CropRect(int(x), int(y), int(width), int(height))
            if not _valid_rect(rect, *size):
                return []
            records.append((float(pts), rect))
        except ValueError:
            return []
    return records


def _read_luma_samples(
    path: Path,
    start: float,
    end: float,
    stride: int,
    size: tuple[int, int],
    color_range: str,
    crop_records: Sequence[tuple[float, CropRect]],
    ffmpeg: str,
) -> list[CropFrameSample]:
    width, height = size
    luma_bytes = width * height
    chroma_bytes = 2 * ((width + 1) // 2) * ((height + 1) // 2)
    frame_bytes = luma_bytes + chroma_bytes
    pixel_format = "yuv420p" if color_range == "tv" else "yuvj420p"
    command = _ffmpeg_prefix(path, start, end, ffmpeg)
    filtergraph = f"{_select_filter(stride)},showinfo,format={pixel_format}"
    command.extend(
        [
            "-vf",
            filtergraph,
            "-fps_mode",
            "passthrough",
            "-pix_fmt",
            pixel_format,
            "-f",
            "rawvideo",
            "-",
        ]
    )
    return _run_raw_frames(
        command,
        frame_bytes,
        size,
        luma_bytes,
        color_range,
        crop_records,
    )


def _run_raw_frames(
    command: list[str],
    frame_bytes: int,
    size: tuple[int, int],
    luma_bytes: int,
    color_range: str,
    crop_records: Sequence[tuple[float, CropRect]],
) -> list[CropFrameSample]:
    width, height = size
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
    except OSError as exc:
        raise CropAnalysisError("FFmpeg could not start for luma analysis") from exc
    stdout_pipe, stderr_pipe = process.stdout, process.stderr
    assert stdout_pipe is not None and stderr_pipe is not None
    events: queue.Queue[tuple[int, float] | None] = queue.Queue()
    stderr_tail: list[str] = []

    def consume_stderr() -> None:
        for raw_line in stderr_pipe:
            line = raw_line.decode("utf-8", errors="replace")
            stderr_tail.append(line.rstrip())
            if len(stderr_tail) > 20:
                del stderr_tail[0]
            match = _SHOWINFO_RE.search(line)
            if match is not None:
                events.put((int(match.group(1)), float(match.group(2))))
        events.put(None)

    reader = threading.Thread(target=consume_stderr, daemon=True)
    reader.start()
    samples: list[CropFrameSample] = []
    black = _black_level(color_range)
    clock_mismatch = False
    try:
        while True:
            chunk = _read_exact(stdout_pipe, frame_bytes)
            if not chunk:
                break
            if len(chunk) != frame_bytes:
                process.kill()
                raise CropAnalysisError("FFmpeg returned an incomplete decoded frame")
            try:
                event = events.get(timeout=300)
            except queue.Empty as exc:
                process.kill()
                raise CropAnalysisError("FFmpeg luma metadata timed out") from exc
            if event is None:
                process.kill()
                raise CropAnalysisError("FFmpeg omitted per-frame luma timestamps")
            frame_index, pts = event
            if frame_index != len(samples) or frame_index >= len(crop_records):
                process.kill()
                raise CropAnalysisError("FFmpeg luma frame sequence was incomplete")
            crop_pts, rect = crop_records[frame_index]
            if abs(pts - crop_pts) > 1e-6:
                clock_mismatch = True
                process.kill()
                break
            raw_y = np.frombuffer(chunk[:luma_bytes], dtype=np.uint8).reshape(
                height, width
            )
            active_rect = _scan_active_rect(raw_y, black + INFORMATIVE_LUMA_DELTA)
            active = raw_y[
                active_rect.y : active_rect.bottom,
                active_rect.x : active_rect.right,
            ]
            mean_luma = float(np.mean(active, dtype=np.float64))
            bar_values = _bar_values(raw_y, active_rect, size)
            samples.append(
                CropFrameSample(
                    frame_index=frame_index,
                    pts_seconds=round(pts, 9),
                    active_rect=active_rect,
                    active_mean_luma=round(mean_luma, 6),
                    informative=mean_luma >= black + INFORMATIVE_LUMA_DELTA,
                    bar_max_luma=(int(np.max(bar_values)) if bar_values.size else None),
                    bar_stddev_luma=(
                        round(float(np.std(bar_values, dtype=np.float64)), 6)
                        if bar_values.size
                        else None
                    ),
                    cropdetect_rect=rect,
                )
            )
        return_code = process.wait(timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        process.kill()
        raise CropAnalysisError("FFmpeg luma analysis could not complete") from exc
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        stdout_pipe.close()
        reader.join(timeout=5)
        if reader.is_alive():
            process.kill()
        stderr_pipe.close()
    if return_code != 0:
        tail = " | ".join(stderr_tail[-3:])
        raise CropAnalysisError(f"FFmpeg luma analysis failed: {tail[-600:]}")
    if clock_mismatch:
        return []
    queued_events = []
    while not events.empty():
        queued_events.append(events.get_nowait())
    if any(event is not None for event in queued_events):
        raise CropAnalysisError("FFmpeg emitted extra luma timestamps")
    return samples


def _read_exact(stream: IO[bytes], size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        part = stream.read(size - len(chunks))
        if not part:
            break
        chunks.extend(part)
    return bytes(chunks)


def _select_filter(stride: int) -> str:
    return f"select=not(mod(n\\,{stride}))"


def _ffmpeg_prefix(path: Path, start: float, end: float, ffmpeg: str) -> list[str]:
    return [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "info",
        "-copyts",
        "-ss",
        f"{start:.9f}",
        "-i",
        str(path),
        "-to",
        f"{end:.9f}",
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
    ]


def _run_process(
    command: list[str], operation: str
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=300
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CropAnalysisError(f"{operation} could not complete") from exc
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()
        suffix = f": {detail[-1][:300]}" if detail else ""
        raise CropAnalysisError(f"{operation} failed{suffix}")
    return result


def _bar_values(luma: np.ndarray, rect: CropRect, size: tuple[int, int]) -> np.ndarray:
    width, height = size
    top_end = max(0, rect.y - BAR_GUARD_PX)
    bottom_start = min(height, rect.bottom + BAR_GUARD_PX)
    left_end = max(0, rect.x - BAR_GUARD_PX)
    right_start = min(width, rect.right + BAR_GUARD_PX)
    middle_start = min(height, rect.y + BAR_GUARD_PX)
    middle_end = max(middle_start, rect.bottom - BAR_GUARD_PX)
    bars = []
    if top_end:
        bars.append(luma[:top_end, :].reshape(-1))
    if bottom_start < height:
        bars.append(luma[bottom_start:, :].reshape(-1))
    if middle_end > middle_start and left_end:
        bars.append(luma[middle_start:middle_end, :left_end].reshape(-1))
    if middle_end > middle_start and right_start < width:
        bars.append(luma[middle_start:middle_end, right_start:].reshape(-1))
    return np.concatenate(bars) if bars else np.empty(0, dtype=np.uint8)


def _scan_active_rect(luma: np.ndarray, threshold: int) -> CropRect:
    active_rows = np.flatnonzero(np.any(luma > threshold, axis=1))
    active_columns = np.flatnonzero(np.any(luma > threshold, axis=0))
    if active_rows.size == 0 or active_columns.size == 0:
        height, width = luma.shape
        return CropRect(0, 0, width, height)
    left, right = int(active_columns[0]), int(active_columns[-1]) + 1
    top, bottom = int(active_rows[0]), int(active_rows[-1]) + 1
    return CropRect(left, top, right - left, bottom - top)


def _median_rect(rects: Sequence[CropRect]) -> CropRect:
    if not rects:
        raise ValueError("at least one crop rectangle is required")

    def edge_median(values: Sequence[int]) -> int:
        return math.floor(float(median(values)) + 0.5)

    left = edge_median([rect.x for rect in rects])
    top = edge_median([rect.y for rect in rects])
    right = edge_median([rect.right for rect in rects])
    bottom = edge_median([rect.bottom for rect in rects])
    return CropRect(left, top, right - left, bottom - top)


def _informative_rects_stable(
    samples: Sequence[CropFrameSample], reference: CropRect, size: tuple[int, int]
) -> bool:
    width, height = size
    tolerance_x = max(MAX_EDGE_JITTER_PX, math.ceil(width * MAX_EDGE_JITTER_RATIO))
    tolerance_y = max(MAX_EDGE_JITTER_PX, math.ceil(height * MAX_EDGE_JITTER_RATIO))
    for sample in samples:
        rect = sample.active_rect
        if (
            abs(rect.x - reference.x) > tolerance_x
            or abs(rect.right - reference.right) > tolerance_x
            or abs(rect.y - reference.y) > tolerance_y
            or abs(rect.bottom - reference.bottom) > tolerance_y
        ):
            return False
    return True


def _geometry_refusal(
    rect: CropRect, size: tuple[int, int], *, check_coverage: bool = True
) -> str | None:
    width, height = size
    spans_width = rect.x == 0 and rect.right == width
    spans_height = rect.y == 0 and rect.bottom == height
    if spans_width == spans_height:
        return "no_bars_detected" if spans_width else "invalid_geometry"
    if check_coverage and (
        rect.width / width < MIN_DIMENSION_COVERAGE
        or rect.height / height < MIN_DIMENSION_COVERAGE
    ):
        return "invalid_geometry"
    if spans_width:
        first_bar, second_bar, dimension = rect.y, height - rect.bottom, height
    else:
        first_bar, second_bar, dimension = rect.x, width - rect.right, width
    symmetry_tolerance = max(
        MAX_EDGE_JITTER_PX, math.ceil(dimension * MAX_EDGE_JITTER_RATIO)
    )
    minimum_bar = max(MIN_BAR_SIZE_PX, math.ceil(dimension * MIN_BAR_SIZE_RATIO))
    if min(first_bar, second_bar) < minimum_bar:
        return "invalid_geometry"
    if abs(first_bar - second_bar) > symmetry_tolerance:
        return "invalid_geometry"
    return None


def _has_bars(rect: CropRect, size: tuple[int, int]) -> bool:
    width, height = size
    return rect != CropRect(0, 0, width, height)


def _zoom_for_bars(rect: CropRect, size: tuple[int, int]) -> float:
    width, height = size
    if rect.x == 0 and rect.right == width:
        dimension = height
        maximum_bar = max(rect.y, height - rect.bottom)
    else:
        dimension = width
        maximum_bar = max(rect.x, width - rect.right)
    raw_zoom = dimension / (dimension - 2 * maximum_bar)
    return _round_zoom_up(raw_zoom)


def _zoom_for_samples(
    samples: Sequence[CropFrameSample], rect: CropRect, size: tuple[int, int]
) -> float:
    width, height = size
    if rect.x == 0 and rect.right == width:
        dimension = height
        maximum_bar = max(
            max(sample.active_rect.y, height - sample.active_rect.bottom)
            for sample in samples
        )
    else:
        dimension = width
        maximum_bar = max(
            max(sample.active_rect.x, width - sample.active_rect.right)
            for sample in samples
        )
    return _round_zoom_up(dimension / (dimension - 2 * maximum_bar))


def _round_zoom_up(raw_zoom: float) -> float:
    factor = 10**ZOOM_DECIMAL_PLACES
    return float(math.ceil(raw_zoom * factor - 1e-12) / factor)


def _same_aspect(source_size: tuple[int, int], timeline_size: tuple[int, int]) -> bool:
    source_aspect = source_size[0] / source_size[1]
    timeline_aspect = timeline_size[0] / timeline_size[1]
    return abs(source_aspect / timeline_aspect - 1) <= MAX_SOURCE_TIMELINE_ASPECT_ERROR


def _black_level(color_range: str) -> int:
    return 16 if color_range == "tv" else 0


def _refused(
    probe: _Probe,
    source_range: tuple[float, float],
    reason: str,
    samples: Sequence[CropFrameSample] = (),
    frame_rate: tuple[int, int] | None = None,
    sample_stride: int | None = None,
    source_frame_count: int | None = None,
    *,
    zoom: float | None = None,
) -> CropDetection:
    return CropDetection(
        source_size=probe.size,
        used_range=source_range,
        samples=tuple(samples),
        active_rect=None,
        refusal_reason=reason,
        zoom=zoom,
        color_range=probe.color_range,
        frame_rate=frame_rate,
        sample_stride=sample_stride,
        source_frame_count=source_frame_count,
    )


def crop_to_fill_transform(
    source_size: tuple[int, int],
    output_size: tuple[int, int],
    active_rect: CropRect,
) -> CropTransform:
    """Compute uniform zoom and translation relative to a contain-fit baseline."""
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
