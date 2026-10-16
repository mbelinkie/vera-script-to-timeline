"""Waveform-supported preview cuts; no claim that low energy proves absent speech."""

from __future__ import annotations

import math
from collections.abc import Sequence
from fractions import Fraction
from typing import Any


def find_quiet_intervals(
    pcm16: Sequence[int],
    sample_rate: int,
    channels: int,
    *,
    threshold_db: float = -40,
    minimum_seconds: float = 0.12,
) -> list[list[float]]:
    """10ms windows, all-channel RMS and transient peak gates, 16-bit PCM scale.

    This measures the decoded original without treating audio. A crossing of zero
    is insufficient: sustained low energy is required in every audio channel.
    """
    if sample_rate < 100 or channels < 1 or len(pcm16) % channels:
        raise ValueError("Invalid PCM layout")
    window = max(1, round(sample_rate * 0.01))
    count = len(pcm16) // channels
    rms_limit = 32768 * 10 ** (threshold_db / 20)
    peak_limit = 32768 * 10 ** ((threshold_db + 12) / 20)
    quiet: list[list[float]] = []
    start: int | None = None
    for a in range(0, count, window):
        b = min(count, a + window)
        sums = [0.0] * channels
        peak = 0
        for i in range(a * channels, b * channels):
            value = pcm16[i]
            sums[i % channels] += value * value
            peak = max(peak, abs(value))
        low = peak <= peak_limit and all(
            s / (b - a) <= rms_limit * rms_limit for s in sums
        )
        if low and start is None:
            start = a
        if start is not None and (not low or b == count):
            end = a if not low else b
            if (end - start) / sample_rate >= minimum_seconds - 1e-9:
                quiet.append([start / sample_rate, end / sample_rate])
            start = None
    return quiet


def propose_quiet_cuts(
    speech: list[float],
    fps_pair: list[int],
    duration: float,
    quiet: list[list[float]],
    adjacent_speech: list[list[float]],
    *,
    padding_frames: int = 10,
    maximum_search_seconds: float = 0.8,
    allow_reduced_padding: bool = False,
) -> dict[str, Any]:
    """Add padding, then move outward to a frame inside a measured quiet window.

    Never shrink to a transcript edge if quiet cannot be found. Review-only
    padded preview bounds are separate from waveform-supported bounds. Both
    remain unapproved. Cuts sit at least 20ms inside a sustained quiet interval.
    """
    if (
        len(speech) != 2
        or not all(math.isfinite(x) for x in speech)
        or not 0 <= speech[0] < speech[1] <= duration
        or len(fps_pair) != 2
        or any(type(x) is not int or x <= 0 for x in fps_pair)
        or type(padding_frames) is not int
        or padding_frames < 0
        or not math.isfinite(maximum_search_seconds)
        or maximum_search_seconds < 0
    ):
        raise ValueError("Invalid boundary input")
    if any(
        len(x) != 2
        or not all(math.isfinite(t) for t in x)
        or not 0 <= x[0] < x[1] <= duration
        for x in quiet + adjacent_speech
    ):
        raise ValueError("Invalid evidence interval")
    fps = Fraction(*fps_pair)
    speech_frames = [
        math.floor(Fraction(str(speech[0])) * fps),
        math.ceil(Fraction(str(speech[1])) * fps),
    ]
    target = [speech_frames[0] - padding_frames, speech_frames[1] + padding_frames]
    reasons = ["producer_playback_required", "low_energy_is_not_proof_of_absent_speech"]
    result: dict[str, Any] = {
        "frame_range": None,
        "preview_frame_range": None,
        "quiet_edges_found": [False, False],
        "requested_padding_frames": padding_frames,
        "added_frames": None,
        "status": "review_needed",
        "safe": False,
        "reasons": reasons,
    }
    if target[0] < 0 or float(target[1] / fps) > duration:
        reasons.append("source_limit")
        return result

    def crosses(frame: int, side: int) -> bool:
        a, b = (
            (float(frame / fps), speech[0])
            if side == 0
            else (speech[1], float(frame / fps))
        )
        return any(x < b and y > a for x, y in adjacent_speech)

    blocked_padding = any(crosses(target[side], side) for side in [0, 1])
    if blocked_padding and not allow_reduced_padding:
        reasons.append("adjacent_speech_blocks_padding")
        return result
    if not blocked_padding:
        result["preview_frame_range"] = target
    selected = []
    evidence = []
    for side in [0, 1]:
        sign = -1 if side == 0 else 1
        chosen = None
        for offset in range(math.floor(maximum_search_seconds * fps) + 1):
            frame = target[side] + sign * offset
            t = float(frame / fps)
            if not 0 <= t <= duration or crosses(frame, side):
                break
            interval = next(
                (span for span in quiet if span[0] + 0.02 <= t <= span[1] - 0.02), None
            )
            if interval is not None:
                chosen = frame
                evidence.append(interval)
                break
        if chosen is None and allow_reduced_padding:
            # Prefer a shorter verified quiet gap over crossing another read.
            # Keep at least two frames outside the transcript estimate and make
            # the reduction explicit; never silently fall back to the word edge.
            for padding in range(padding_frames - 1, 1, -1):
                frame = speech_frames[side] + sign * padding
                t = float(frame / fps)
                if not 0 <= t <= duration or crosses(frame, side):
                    continue
                interval = next(
                    (span for span in quiet if span[0] + 0.02 <= t <= span[1] - 0.02),
                    None,
                )
                if interval is not None:
                    chosen = frame
                    evidence.append(interval)
                    reasons.append("reduced_padding_to_fit_quiet_gap")
                    break
        result["quiet_edges_found"][side] = chosen is not None
        selected.append(chosen)
    if all(frame is not None for frame in selected):
        start_frame, end_frame = selected
        assert start_frame is not None and end_frame is not None
        result["frame_range"] = selected
        result["quiet_intervals"] = evidence
        result["added_frames"] = [
            speech_frames[0] - start_frame,
            end_frame - speech_frames[1],
        ]
    else:
        reasons.append("quiet_boundary_not_found")
    return result
