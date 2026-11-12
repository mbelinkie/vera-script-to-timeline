"""Line up a separately recorded audio file with a video's own camera sound (#45).

The two recordings hear the same performance, so their waveforms match at one
offset. A coarse pass over the whole recording finds that offset; a fine pass
then measures it again in several independent windows spread across the video.
The answer is accepted only when the coarse match clearly stands out and the
windows agree with each other to within half a frame. Otherwise `SyncRefused`
is raised: the caller must stop, never guess.

Both inputs are mono float arrays at the same sample rate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Samples = NDArray[np.float32]

COARSE_RATE_HZ = 2000
WINDOW_S = 20.0
WINDOWS = 10
SEARCH_S = 0.1  # the fine pass looks this far either side of the coarse answer
MIN_PEAK_RATIO = 3.0  # coarse match versus the best match anywhere else
MIN_WINDOW_MATCH = 0.1  # normalised correlation below this is "no evidence"
MIN_WINDOWS = 5
MAX_SPREAD_S = 0.015  # under half a frame at 30 fps
MIN_OVERLAP_S = 10.0


class SyncRefused(Exception):
    """The separate audio could not be confidently lined up with the video."""


@dataclass(frozen=True)
class SyncWindow:
    video_s: float
    offset_s: float
    match: float


@dataclass(frozen=True)
class SyncResult:
    """`offset_s` is the separate-audio time at which the video starts.

    Positive: the separate recording started first. A moment at video time
    `t` is at `t + offset_s` in the separate audio.
    """

    offset_s: float
    spread_s: float
    peak_ratio: float
    windows: tuple[SyncWindow, ...]


def _correlate(a: NDArray[np.float64], b: NDArray[np.float64]) -> NDArray[np.float64]:
    """c[k] = sum(a[t + k] * b[t]); negative k wraps to the end of the array."""
    size = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    spectrum = np.fft.rfft(a, size) * np.conj(np.fft.rfft(b, size))
    return np.asarray(np.fft.irfft(spectrum, size), dtype=np.float64)


def _decimate(x: Samples, factor: int) -> NDArray[np.float64]:
    usable = len(x) // factor * factor
    out = x[:usable].astype(np.float64).reshape(-1, factor).mean(axis=1)
    out -= out.mean()
    deviation = float(out.std())
    if deviation > 0:
        out /= deviation
    return np.asarray(out, dtype=np.float64)


def find_offset(camera: Samples, separate: Samples, rate: int) -> SyncResult:
    if rate < COARSE_RATE_HZ or min(len(camera), len(separate)) < MIN_OVERLAP_S * rate:
        raise SyncRefused(
            f"Both recordings must be at least {MIN_OVERLAP_S:.0f} seconds long."
        )
    factor = max(1, rate // COARSE_RATE_HZ)
    cam, sep = _decimate(camera, factor), _decimate(separate, factor)
    if not cam.any() or not sep.any():
        raise SyncRefused("One of the recordings is silent.")
    c = _correlate(sep, cam)
    lags = np.arange(len(c))
    lags[lags > len(c) // 2] -= len(c)
    best = int(np.argmax(c))
    coarse = int(lags[best]) * factor  # in samples at `rate`
    elsewhere = c[np.abs(lags - lags[best]) > SEARCH_S * rate / factor]
    runner_up = float(elsewhere.max()) if len(elsewhere) else 0.0
    ratio = float(c[best]) / runner_up if runner_up > 0 else float("inf")
    if c[best] <= 0 or ratio < MIN_PEAK_RATIO:
        raise SyncRefused(
            "The separate audio does not clearly match the camera sound "
            f"(best match is only {ratio:.1f} times the next best; "
            f"{MIN_PEAK_RATIO:.0f} times is required)."
        )

    # Fine pass: independent windows across the part both recordings cover.
    reach = round(SEARCH_S * rate)
    first = max(0, reach - coarse)
    last = min(len(camera), len(separate) - coarse - reach)
    if last - first < MIN_OVERLAP_S * rate:
        raise SyncRefused(
            "The two recordings overlap for less than "
            f"{MIN_OVERLAP_S:.0f} seconds at the best match."
        )
    length = min(round(WINDOW_S * rate), last - first)
    windows: list[SyncWindow] = []
    for start in np.linspace(first, last - length, WINDOWS).astype(int):
        x = camera[start : start + length].astype(np.float64)
        y = separate[start + coarse - reach : start + coarse + length + reach].astype(
            np.float64
        )
        x -= x.mean()
        y -= y.mean()
        local = _correlate(y, x)[: 2 * reach + 1]
        shift = int(np.argmax(local))
        matched = y[shift : shift + length]
        energy = float(np.sqrt((x * x).sum() * (matched * matched).sum()))
        if energy <= 0:
            continue
        match = float(local[shift]) / energy
        if match >= MIN_WINDOW_MATCH:
            offset = (coarse - reach + shift) / rate
            windows.append(SyncWindow(float(start) / rate, offset, match))
    if len(windows) < MIN_WINDOWS:
        raise SyncRefused(
            f"Only {len(windows)} of {WINDOWS} check points matched; "
            f"{MIN_WINDOWS} are required."
        )
    offsets = [w.offset_s for w in windows]
    offset = float(np.median(offsets))
    spread = max(offsets) - min(offsets)
    if max(abs(o - offset) for o in offsets) > MAX_SPREAD_S:
        raise SyncRefused(
            "The two recordings do not stay lined up: the offset changes by "
            f"{spread * 1000:.0f} ms across the recording."
        )
    return SyncResult(offset, spread, ratio, tuple(windows))
