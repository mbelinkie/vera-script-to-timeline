"""Prefilled Audition review markers; machine agreement never implies review."""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Mapping, Sequence
from typing import Any

from vera_timeline_agent.narration.models import sha256_bytes

HEADERS = ("Name", "Start", "Duration", "Time Format", "Type", "Description")


def _decimal(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    minutes, remainder = divmod(milliseconds, 60_000)
    return f"{minutes}:{remainder // 1000:02d}.{remainder % 1000:03d}"


def _csv_bytes(rows: Sequence[Sequence[str]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter="\t", lineterminator="\r\n")
    writer.writerow(HEADERS)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def audition_timing_review(
    *,
    audio_bytes: bytes,
    duration_seconds: float,
    tokens: Sequence[Mapping[str, Any]],
    candidate: Sequence[tuple[float, float] | None],
    partner: Sequence[tuple[float, float] | None],
    native: Sequence[float | None],
    required_indices: Sequence[int] = (),
    threshold_ms: int = 70,
) -> tuple[bytes, bytes, dict[str, Any]]:
    """Return word ranges, disputed onset alternatives, and private correspondence.

    All inputs use original untrimmed audio seconds. Missing or collapsed machine
    intervals remain explicit abstentions, rather than fabricated range markers.
    The zero-duration alternatives are point markers, never word-end evidence.
    """
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("positive finite original audio duration required")
    if not len(tokens) == len(candidate) == len(partner) == len(native):
        raise ValueError("one observation per frozen token is required")
    if threshold_ms <= 0 or any(i < 0 or i >= len(tokens) for i in required_indices):
        raise ValueError("review scope is invalid")
    ranges, alternatives, correspondence = [], [], []
    seen: set[str] = set()
    for index, (token, primary, second, reported) in enumerate(
        zip(tokens, candidate, partner, native, strict=True)
    ):
        token_id, text = token["id"], token["value"]
        if not isinstance(token_id, str) or token_id in seen or not text:
            raise ValueError("review tokens need unique identities and nonempty text")
        seen.add(token_id)
        for interval in (primary, second):
            if interval is not None and (
                len(interval) != 2
                or any(not math.isfinite(t) for t in interval)
                or not 0 <= interval[0] <= interval[1] <= duration_seconds
            ):
                raise ValueError("machine interval is outside original audio")
        if reported is not None and (
            not math.isfinite(reported) or not 0 <= reported < duration_seconds
        ):
            raise ValueError("native onset is outside original audio")
        reasons = []
        if index in required_indices:
            reasons.append("required boundary / retained native tie")
        if primary is None or primary[0] >= primary[1]:
            reasons.append("MFA abstained or collapsed")
        if second is None or second[0] >= second[1]:
            reasons.append("Qwen abstained or collapsed")
        if reported is None:
            reasons.append("native source mapping unavailable")
        if primary is not None:
            if (
                reported is not None
                and abs(primary[0] - reported) * 1000 > threshold_ms
            ):
                reasons.append(
                    "native/MFA onset difference "
                    f"{abs(primary[0] - reported) * 1000:.0f} ms"
                )
            if second is not None and abs(primary[0] - second[0]) * 1000 > threshold_ms:
                reasons.append(
                    "MFA/Qwen onset difference "
                    f"{abs(primary[0] - second[0]) * 1000:.0f} ms"
                )
        label = f"{index + 1:03d} {text}"
        status = "REVIEW" if reasons else "CONTEXT"
        observations = {
            "native": reported,
            "MFA": primary[0] if primary else None,
            "Qwen": second[0] if second else None,
        }
        detail = "; ".join(
            f"{key}={value:.3f}s" if value is not None else f"{key}=absent"
            for key, value in observations.items()
        )
        reason_text = "; ".join(reasons) if reasons else "no flagged disagreement"
        description = (
            f"{status}: {reason_text}; {detail}; machine prefill, NOT human verified; "
            "review onset; range end is not audible-end evidence"
        )
        if primary is not None and primary[1] > primary[0]:
            ranges.append(
                [
                    f"{status} {label}",
                    _decimal(primary[0]),
                    _decimal(primary[1] - primary[0]),
                    "decimal",
                    "Cue",
                    description,
                ]
            )
        if reasons:
            for method, onset in observations.items():
                if onset is not None:
                    alternatives.append(
                        [
                            f"{method} {label}",
                            _decimal(onset),
                            "0:00.000",
                            "decimal",
                            "Cue",
                            description,
                        ]
                    )
        correspondence.append(
            {
                "tokenId": token_id,
                "ordinal": index + 1,
                "quotedText": text,
                "startOffset": token["startOffset"],
                "endOffset": token["endOffset"],
                "candidate": primary,
                "partner": second,
                "nativeOnset": reported,
                "needsReview": bool(reasons),
                "reasons": reasons,
                "reviewed": False,
            }
        )
    markers, points = _csv_bytes(ranges), _csv_bytes(alternatives)
    return (
        markers,
        points,
        {
            "schemaVersion": "audition-timing-review-prefill/v1",
            "audioHash": sha256_bytes(audio_bytes),
            "prefilledMarkersHash": sha256_bytes(markers),
            "alternativeMarkersHash": sha256_bytes(points),
            "thresholdMs": threshold_ms,
            "requiredOrdinals": [i + 1 for i in required_indices],
            "tokens": correspondence,
        },
    )
