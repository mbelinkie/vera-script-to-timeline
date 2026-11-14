"""Pure, fail-closed identity and safety checks for human presenter approvals (#46).

The #45 report is an analysis input, never a human decision. The original
video's SHA-256 must be supplied by a caller that has read the actual file.
All ranges here are *source-video* frames, not audio samples or rounded seconds.
This module deliberately does not write to disk; sidecars/commands follow in
phase 2.
"""

from __future__ import annotations

import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

Json = dict[str, Any]
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")


class ApprovalError(ValueError):
    """Invalid or unsafe approval/report input; do not modify any decision."""


def _object(pairs: list[tuple[str, Any]]) -> Json:
    obj: Json = {}
    for key, value in pairs:
        if key in obj:
            raise ApprovalError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def _bad_constant(value: str) -> None:
    raise ApprovalError(f"non-finite JSON number: {value}")


def load_takes(path: Path) -> Json:
    """Read an untrusted #45 report; never turn corruption into empty choices."""
    try:
        raw = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object,
            parse_constant=_bad_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ApprovalError(f"cannot read takes.json: {error}") from error
    return validate_takes(raw)


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ApprovalError(f"{label} must be an integer >= {minimum}")
    return value


def _seconds(value: Any, label: str, *, positive: bool = False) -> Fraction:
    if type(value) not in (int, float, str):
        raise ApprovalError(f"{label} must be finite seconds")
    try:
        parsed = Fraction(str(value))
    except (ValueError, ZeroDivisionError, OverflowError) as error:
        raise ApprovalError(f"{label} must be finite seconds") from error
    if parsed < 0 or (positive and parsed == 0):
        raise ApprovalError(
            f"{label} must be {'positive' if positive else 'nonnegative'}"
        )
    return parsed


def frame_rate(video: Json) -> Fraction:
    rate = video.get("fps") if isinstance(video, dict) else None
    if not isinstance(rate, list) or len(rate) != 2:
        raise ApprovalError("video fps must be two positive integers")
    numerator = _integer(rate[0], "video fps numerator", 1)
    denominator = _integer(rate[1], "video fps denominator", 1)
    return Fraction(numerator, denominator)


def video_duration(video: Json) -> Fraction:
    if not isinstance(video, dict):
        raise ApprovalError("missing video")
    if not isinstance(video.get("file"), str) or not video["file"].strip():
        raise ApprovalError("missing video filename")
    return _seconds(video.get("durationS"), "video durationS", positive=True)


def _cut_frames(video: Json, read: Json) -> tuple[int, int] | None:
    cut = read.get("cut")
    if cut is None:
        return None
    if not isinstance(cut, dict):
        raise ApprovalError("read cut must be an object or null")
    a = _integer(cut.get("startFrame"), "cut startFrame")
    b = _integer(cut.get("endFrame"), "cut endFrame")
    if b <= a or Fraction(b, 1) / frame_rate(video) > video_duration(video):
        raise ApprovalError("read cut is outside recording bounds")
    for field in ("startS", "endS"):
        if field in cut:
            _seconds(cut[field], f"cut {field}")
    return a, b


def _timing(read: Json, video: Json) -> tuple[Fraction, Fraction] | None:
    a = read.get("speechStartS")
    b = read.get("speechEndS")
    if a is None or b is None:
        if a is not None or b is not None:
            raise ApprovalError("incomplete speech timing")
        return None
    first = _seconds(a, "speechStartS")
    last = _seconds(b, "speechEndS")
    if not first < last or last > video_duration(video):
        raise ApprovalError("speech timing is outside recording or unordered")
    return first, last


def _read_metadata(video: Json, read: Json) -> None:
    if not isinstance(read.get("said"), str) or not read["said"].strip():
        raise ApprovalError("read needs spoken words")
    for flag in ("approximateStart", "approximateEnd"):
        if type(read.get(flag)) is not bool:
            raise ApprovalError(f"read {flag} must be a boolean")
    cut = _cut_frames(video, read)
    speech = _timing(read, video)
    if cut is not None and speech is None:
        raise ApprovalError("clean cut requires measured speech timing")
    if cut is not None and speech is not None:
        first, last = speech
        start, end = (Fraction(frame, 1) / frame_rate(video) for frame in cut)
        if not start <= first < last <= end:
            raise ApprovalError("speech is outside its proposed cut")


def _word_count(row: Json) -> int:
    takes = row.get("takes")
    if not isinstance(takes, list):
        raise ApprovalError("passage takes must be a list")
    count: int | None = None
    seen: set[str] = set()
    for take in takes:
        if not isinstance(take, dict):
            raise ApprovalError("invalid raw take")
        ident = take.get("id")
        if not isinstance(ident, str) or not ident or ident in seen:
            raise ApprovalError("missing or duplicate raw take ID")
        seen.add(ident)
        size = _integer(take.get("scriptWords"), "raw scriptWords", 1)
        covered = _integer(take.get("scriptWordsCovered"), "raw scriptWordsCovered")
        if covered > size:
            raise ApprovalError("raw coverage exceeds script word count")
        if count is not None and count != size:
            raise ApprovalError("inconsistent script word counts")
        count = size
    return count or 0


def validate_takes(data: Any) -> Json:
    """Validate the essential #45 report envelope and stable row ordering.

    Analysis-only fields are retained without interpretation. A full read is
    separately checked by :func:`full_reads` before approval or matching.
    """
    if not isinstance(data, dict) or data.get("schemaVersion") != "presenter-takes/1":
        raise ApprovalError("unrecognized takes schemaVersion")
    if data.get("approved") is not False:
        raise ApprovalError("takes report must not assert human approval")
    video = data.get("video")
    if not isinstance(video, dict):
        raise ApprovalError("takes report needs video metadata")
    frame_rate(video)
    video_duration(video)
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ApprovalError("takes report needs ordered rows")
    for ordinal, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ApprovalError("invalid script passage")
        if (
            row.get("id") != f"row-{ordinal}"
            or row.get("number") != ordinal
            or row.get("row") != ordinal
        ):
            raise ApprovalError("duplicate, reordered or malformed passage IDs")
        if not isinstance(row.get("script"), str) or not row["script"].strip():
            raise ApprovalError("empty script passage")
        if not isinstance(row.get("alternateReads"), list):
            raise ApprovalError("alternateReads must be a list")
        if not isinstance(row.get("suggestedCoverage"), list):
            raise ApprovalError("suggestedCoverage must be a list")
        _word_count(row)
        # Detect corrupt candidate identity even if this row is not selected.
        full_reads(row, video)
    return data


def row_context(takes: Json) -> list[list[str]]:
    """Freeze *all* ordered scripts: ordinal IDs alone can be reused after edits."""
    return [[row["id"], row["script"]] for row in takes["rows"]]


def _candidate(
    read: Json, video: Json, word_count: int, known: set[str]
) -> Json | None:
    words = read.get("scriptWords")
    if (
        not isinstance(words, list)
        or len(words) != 2
        or any(type(n) is not int for n in words)
        or words != [0, word_count]
    ):
        # Explicit partial intervals are never full-row approvals.
        return None
    ids = read.get("takes")
    if (
        not isinstance(ids, list)
        or not ids
        or any(not isinstance(i, str) or i not in known for i in ids)
        or len(ids) != len(set(ids))
    ):
        raise ApprovalError("read refers to missing or repeated constituent takes")
    _read_metadata(video, read)
    if _cut_frames(video, read) is None:
        return None  # no clean cut, no approval
    return read


def full_reads(row: Json, video: Json) -> list[Json]:
    """Clean continuous full-passage reads, irrespective of ranked suggestion.

    A read may have multiple constituent take IDs. suggestedCoverage is an
    *edit assembled from partial reads*, so it is deliberately never visited.
    Raw takes are eligible on their own only with complete literal script-word
    coverage; a raw take's `wholePassage` flag alone can mean it is a fragment
    of a valid compound read.
    """
    size = _word_count(row)
    raw = row["takes"]
    known = {take["id"] for take in raw}
    candidates: list[tuple[Json, bool]] = []
    suggestion = row.get("suggested")
    if suggestion is not None:
        if not isinstance(suggestion, dict):
            raise ApprovalError("suggested read must be an object or null")
        candidates.append((suggestion, False))
    for alternate in row["alternateReads"]:
        if not isinstance(alternate, dict):
            raise ApprovalError("invalid alternate read")
        candidates.append((alternate, False))
    # A raw take might be a full read even when not the suggested edit. Do not
    # promote fractional coverage or ambiguous compound membership.
    for take in raw:
        if take.get("wholePassage") is True and take.get("scriptWordsCovered") == size:
            candidates.append(
                (
                    {
                        **take,
                        "takes": [take["id"]],
                        "scriptWords": [0, size],
                    },
                    True,
                )
            )

    found: list[Json] = []
    anchors: dict[tuple[int, int], Json] = {}
    for read, raw_take in candidates:
        accepted = _candidate(read, video, size, known)
        if accepted is None:
            continue
        anchor = _cut_frames(video, accepted)
        assert anchor is not None
        previous = anchors.get(anchor)
        if previous is not None:
            if raw_take and read["takes"][0] in previous["takes"]:
                # #45 derives read.differences and raw.differences through
                # different routes (raw adds differs_from_script). Trust the
                # full-passage projection, not the redundant raw annotation.
                # Exact interval and constituent membership were checked.
                continue
            safety_fields = (
                "said",
                "speechStartS",
                "speechEndS",
                "approximateStart",
                "approximateEnd",
                "differences",
            )
            if any(
                previous.get(field) != accepted.get(field) for field in safety_fields
            ):
                raise ApprovalError("conflicting reads share one source-frame interval")
            # Same continuous recording interval, maybe different #45 take IDs.
            continue
        anchors[anchor] = accepted
        found.append(accepted)
    return found


def checked_trim(
    video: Json, read: Json, start_frame: int, end_frame: int
) -> tuple[int, int]:
    """Refuse a manual trim unless measured speech stays strictly inside it."""
    start = _integer(start_frame, "trim startFrame")
    end = _integer(end_frame, "trim endFrame")
    original = _cut_frames(video, read)
    if original is None:
        raise ApprovalError("cannot trim a read without a clean cut")
    if (
        start >= end
        or start < original[0]
        or end > original[1]
        or Fraction(end, 1) / frame_rate(video) > video_duration(video)
    ):
        raise ApprovalError("trim is outside the original clean cut or recording")
    if read.get("approximateStart") or read.get("approximateEnd"):
        raise ApprovalError("roughly timed speech edge cannot be manually trimmed")
    timing = _timing(read, video)
    if timing is None:
        raise ApprovalError("missing speech timing: trim is unsafe")
    first, last = timing
    if not (
        Fraction(start, 1) / frame_rate(video) < first
        and last < Fraction(end, 1) / frame_rate(video)
    ):
        raise ApprovalError("trim would touch or cut into speech")
    return start, end


def source_identity(video: Json, video_sha256: str) -> Json:
    """Produce a content-pinned source descriptor; filename is display-only."""
    rate = frame_rate(video)
    duration = video_duration(video)
    if not isinstance(video_sha256, str) or not _SHA256.fullmatch(video_sha256):
        raise ApprovalError("invalid original-video sha256")
    return {
        "sha256": video_sha256,
        "fps": [rate.numerator, rate.denominator],
        "durationS": str(duration),
        "file": video["file"],
    }


def freeze_read(
    takes: Json,
    row_id: str,
    read: Json,
    video_sha256: str,
    trim: tuple[int, int] | None = None,
) -> Json:
    """Snapshot immutable source+passage+read identity for a future human choice.

    This is not an approval or persistence operation. Callers must explicitly
    choose a read returned by full_reads, not merely suggested by #45.
    """
    validate_takes(takes)
    row = next((item for item in takes["rows"] if item["id"] == row_id), None)
    if row is None:
        raise ApprovalError("unknown script passage")
    anchor = _cut_frames(takes["video"], read)
    if anchor is None or not any(
        candidate is read or candidate == read
        for candidate in full_reads(row, takes["video"])
    ):
        raise ApprovalError("read is not an eligible complete clean read")
    effective = trim if trim is not None else anchor
    if trim is not None:
        checked_trim(takes["video"], read, *trim)
    timing = _timing(read, takes["video"])
    return {
        "rowId": row_id,
        "rowNumber": row["number"],
        "script": row["script"],
        "rowContext": row_context(takes),
        "source": source_identity(takes["video"], video_sha256),
        "originalCut": {"startFrame": anchor[0], "endFrame": anchor[1]},
        "effectiveCut": {"startFrame": effective[0], "endFrame": effective[1]},
        "said": read["said"],
        "speechStartS": str(timing[0]) if timing else None,
        "speechEndS": str(timing[1]) if timing else None,
    }


def match_frozen_read(
    takes: Json, frozen: Json, observed_sha256: str, tolerance_frames: int = 2
) -> tuple[Json | None, str | None]:
    """Resolve a frozen choice without ever retargeting it to another read.

    Missing/modified source, row order, wording, read interval, spoken words,
    or safety evidence returns a precise stale reason. A close read is not
    allowed to rewrite the frozen original/effective cut.
    """
    validate_takes(takes)
    _integer(tolerance_frames, "frame tolerance")
    current_source = source_identity(takes["video"], observed_sha256)
    previous_source = frozen.get("source")
    if not isinstance(previous_source, dict) or (
        current_source["sha256"] != previous_source.get("sha256")
        or current_source["fps"] != previous_source.get("fps")
        or current_source["durationS"] != previous_source.get("durationS")
    ):
        return None, "source recording or video timing changed"
    if frozen.get("rowContext") != row_context(takes):
        return None, "script passage order or wording changed"
    row = next(
        (item for item in takes["rows"] if item["id"] == frozen.get("rowId")), None
    )
    if (
        row is None
        or row["script"] != frozen.get("script")
        or row["number"] != frozen.get("rowNumber")
    ):
        return None, "script passage changed"
    original = frozen.get("originalCut")
    effective = frozen.get("effectiveCut")
    if not isinstance(original, dict) or not isinstance(effective, dict):
        return None, "missing saved source-frame cut"
    try:
        before = (
            _integer(original.get("startFrame"), "original startFrame"),
            _integer(original.get("endFrame"), "original endFrame"),
        )
        trim = (
            _integer(effective.get("startFrame"), "effective startFrame"),
            _integer(effective.get("endFrame"), "effective endFrame"),
        )
    except ApprovalError:
        return None, "invalid saved source-frame cut"
    matches = [
        read
        for read in full_reads(row, takes["video"])
        if abs(read["cut"]["startFrame"] - before[0]) <= tolerance_frames
        and abs(read["cut"]["endFrame"] - before[1]) <= tolerance_frames
        and read["said"] == frozen.get("said")
    ]
    if len(matches) != 1:
        return None, "approved read missing, shifted, changed words or ambiguous"
    read = matches[0]
    fresh = _timing(read, takes["video"])
    if (
        fresh is None
        or frozen.get("speechStartS") is None
        or frozen.get("speechEndS") is None
    ):
        return None, "missing fresh or frozen speech timing"
    try:
        first = _seconds(frozen["speechStartS"], "saved speechStartS")
        last = _seconds(frozen["speechEndS"], "saved speechEndS")
    except ApprovalError:
        return None, "invalid saved speech timing"
    allowance = Fraction(tolerance_frames, 1) / frame_rate(takes["video"])
    if abs(fresh[0] - first) > allowance or abs(fresh[1] - last) > allowance:
        return None, "source speech timing changed"
    # Even an untrimmed frozen cut needs to remain within the recording and
    # retain the speech after a nearby reanalysis shift. Never adopt the new
    # candidate cut as the approved range.
    rate = frame_rate(takes["video"])
    if (
        trim[0] >= trim[1]
        or Fraction(trim[1], 1) / rate > video_duration(takes["video"])
        or Fraction(trim[0], 1) / rate > fresh[0]
        or fresh[1] > Fraction(trim[1], 1) / rate
    ):
        return None, (
            "saved trim no longer speech-safe"
            if trim != before
            else "saved cut no longer encloses speech safely"
        )
    # A saved *human* trim must still be safe according to fresh quiet bounds.
    if trim != before:
        try:
            checked_trim(takes["video"], read, *trim)
        except ApprovalError:
            return None, "saved trim no longer speech-safe"
    elif _cut_frames(takes["video"], read) is None:
        return None, "missing clean cut"
    return read, None
