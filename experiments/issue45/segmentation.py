"""VAD-region grouping and unit-to-segment assignment (pure; ported from the study).

The aligner works on segments of at most MAX_SEGMENT_S whose edges sit in
silence. Speech regions come from a VAD engine (Silero, run outside the repo
environment). Recogniser anchors only decide which segment a unit belongs to,
so coarse anchor error does not move segment edges.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from experiments.issue45.normalize import Unit

PAD_S = 0.300
MAX_SEGMENT_S = 30.0


def group_regions(
    regions: list[tuple[float, float]], duration: float
) -> list[tuple[float, float]]:
    """Merge speech regions into padded segments of at most MAX_SEGMENT_S.

    Over-long groups split at their widest internal silence, recursively.
    Padding never crosses the midpoint of the gap to a neighbouring group.
    """
    if not regions:
        return []
    pending = [regions]
    done: list[list[tuple[float, float]]] = []
    while pending:
        group = pending.pop()
        if len(group) == 1 or (group[-1][1] - group[0][0]) + 2 * PAD_S <= MAX_SEGMENT_S:
            done.append(group)
            continue
        cut = max(range(1, len(group)), key=lambda k: group[k][0] - group[k - 1][1])
        pending.extend([group[:cut], group[cut:]])
    spans = sorted((g[0][0], g[-1][1]) for g in done)
    padded = []
    for index, (start, end) in enumerate(spans):
        low = 0.0 if index == 0 else (spans[index - 1][1] + start) / 2
        high = duration if index == len(spans) - 1 else (end + spans[index + 1][0]) / 2
        padded.append(
            (round(max(low, start - PAD_S), 3), round(min(high, end + PAD_S), 3))
        )
    return padded


@dataclass
class Segment:
    start: float
    end: float
    units: list[Unit] = field(default_factory=list)


def assign_units(
    units: list[Unit],
    anchors: list[tuple[float, float] | None],
    segments: list[tuple[float, float]],
) -> list[Segment]:
    """Give each unit to the segment holding its anchor midpoint.

    Assignment never moves backwards.

    `anchors[n]` is the (start, end) of unit n's recognised token, or None;
    unanchored units stay in the current segment. Empty segments are dropped.
    """
    if len(units) != len(anchors):
        raise ValueError("one anchor per unit is required")
    out = [Segment(s, e) for s, e in segments]
    if not out:
        return []
    floor = 0
    for unit, anchor in zip(units, anchors, strict=True):
        target = floor
        if anchor is not None:
            mid = (anchor[0] + anchor[1]) / 2

            def distance(n: int, mid: float = mid) -> float:
                s, e = segments[n]
                return 0.0 if s <= mid <= e else min(abs(mid - s), abs(mid - e))

            target = min(range(len(segments)), key=distance)
        floor = max(floor, target)
        out[floor].units.append(unit)
    return [seg for seg in out if seg.units]
