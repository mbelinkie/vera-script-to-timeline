"""Fail-closed identity, history and persistence for human presenter approvals (#46).

The #45 report is an analysis input, never a human decision. The original
video's SHA-256 must be supplied by a caller that has read the actual file.
All ranges here are *source-video* frames, not audio samples or rounded seconds.
Only explicit choose/undo transactions write a separate approvals.json sidecar.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Any

from vera_word_timing.artifacts import file_hash

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


# The decision file is an audit log, not an output of the take analyzer. In
# particular, none of its keys is a ranked suggestion or a #45 take ordinal.
APPROVAL_SCHEMA = "presenter-approvals/1"
PERFORMANCE_SCHEMA = "approved-performance/1"
STATES = ("take", "temp_voice", "needs_pickup", "no_spoken_line")


def read_key(read: Json) -> str:
    """A source-frame key displayed alongside #45's ephemeral take IDs."""
    cut = read["cut"]
    return f"{cut['startFrame']}:{cut['endFrame']}"


def available_choices(takes: Json) -> list[Json]:
    """Show candidate IDs without treating ranked suggestions as approvals."""
    validate_takes(takes)
    return [
        {
            "rowId": row["id"],
            "script": row["script"],
            "reads": [
                {
                    "key": read_key(read),
                    "takes": read["takes"],
                    "said": read["said"],
                    "startFrame": read["cut"]["startFrame"],
                    "endFrame": read["cut"]["endFrame"],
                }
                for read in full_reads(row, takes["video"])
            ],
        }
        for row in takes["rows"]
    ]


def _empty_approvals() -> Json:
    return {
        "schemaVersion": APPROVAL_SCHEMA,
        "revision": 0,
        "source": None,
        "decisions": {},
        "history": [],
    }


def _check_source(saved: Any) -> Json:
    if not isinstance(saved, dict) or set(saved) != {
        "sha256",
        "fps",
        "durationS",
        "file",
    }:
        raise ApprovalError("invalid saved source identity")
    try:
        normalized = source_identity(saved, saved["sha256"])
    except (ApprovalError, TypeError) as error:
        raise ApprovalError("invalid saved source identity") from error
    if normalized != saved:
        raise ApprovalError("noncanonical saved source identity")
    return saved


def _check_snapshot(snapshot: Any, source: Json, row_id: str) -> None:
    if not isinstance(snapshot, dict) or set(snapshot) != {
        "rowId",
        "rowNumber",
        "script",
        "rowContext",
        "source",
        "originalCut",
        "effectiveCut",
        "said",
        "speechStartS",
        "speechEndS",
    }:
        raise ApprovalError("invalid saved take snapshot")
    _check_passage(snapshot, row_id)
    snapshot_source = _check_source(snapshot["source"])
    if any(
        snapshot_source[field] != source[field]
        for field in ("sha256", "fps", "durationS")
    ):
        raise ApprovalError("take snapshot has mismatched source identity")
    if not isinstance(snapshot["said"], str) or not snapshot["said"].strip():
        raise ApprovalError("saved take is missing spoken words")
    cuts: list[tuple[int, int]] = []
    for key in ("originalCut", "effectiveCut"):
        value = snapshot[key]
        if not isinstance(value, dict) or set(value) != {"startFrame", "endFrame"}:
            raise ApprovalError("invalid saved source-frame cut")
        start = _integer(value["startFrame"], "saved startFrame")
        end = _integer(value["endFrame"], "saved endFrame")
        if start >= end or Fraction(end, 1) / frame_rate(source) > video_duration(
            source
        ):
            raise ApprovalError("saved source-frame cut outside recording")
        cuts.append((start, end))
    original, effective = cuts
    if effective[0] < original[0] or effective[1] > original[1]:
        raise ApprovalError("saved trim extends outside original cut")
    first = _seconds(snapshot["speechStartS"], "saved speechStartS")
    last = _seconds(snapshot["speechEndS"], "saved speechEndS")
    original_a, original_b = (
        Fraction(frame, 1) / frame_rate(source) for frame in original
    )
    effective_a, effective_b = (
        Fraction(frame, 1) / frame_rate(source) for frame in effective
    )
    if not (original_a <= first < last <= original_b):
        raise ApprovalError("saved original cut excludes speech")
    if effective != original and not (effective_a < first < last < effective_b):
        raise ApprovalError("saved trim touches measured speech")


def _check_passage(snapshot: Json, row_id: str) -> None:
    """Validate wording and full row context for takes and non-take decisions."""
    if snapshot.get("rowId") != row_id:
        raise ApprovalError("saved passage has mismatched row identity")
    row_number = _integer(snapshot.get("rowNumber"), "saved row number", 1)
    script = snapshot.get("script")
    if not isinstance(script, str) or not script.strip():
        raise ApprovalError("saved passage is missing script wording")
    context = snapshot.get("rowContext")
    if (
        not isinstance(context, list)
        or row_number > len(context)
        or any(
            not isinstance(entry, list)
            or len(entry) != 2
            or not all(isinstance(item, str) and item for item in entry)
            or entry[0] != f"row-{index}"
            for index, entry in enumerate(context, 1)
        )
        or context[row_number - 1] != [row_id, script]
    ):
        raise ApprovalError("invalid saved script passage context")


def _check_decision(decision: Any, source: Json, row_id: str) -> None:
    if not isinstance(decision, dict) or decision.get("state") not in STATES:
        raise ApprovalError("invalid approval decision state")
    if decision["state"] != "take":
        if set(decision) == {"state"}:
            return  # legacy phase-2 decision; report must flag unknown identity
        if set(decision) != {"state", "passage"}:
            raise ApprovalError("non-take decision includes a take or trim")
        passage = decision["passage"]
        if not isinstance(passage, dict) or set(passage) != {
            "rowId",
            "rowNumber",
            "script",
            "rowContext",
        }:
            raise ApprovalError("invalid saved non-take passage")
        _check_passage(passage, row_id)
        return
    if set(decision) != {"state", "active", "alternates"}:
        raise ApprovalError("invalid saved active-take decision")
    _check_snapshot(decision["active"], source, row_id)
    alternates = decision["alternates"]
    if not isinstance(alternates, list):
        raise ApprovalError("invalid saved alternates")
    anchors: set[tuple[int, int]] = set()
    for item in [decision["active"], *alternates]:
        _check_snapshot(item, source, row_id)
        cut = item["originalCut"]
        anchor = (cut["startFrame"], cut["endFrame"])
        if anchor in anchors:
            raise ApprovalError("duplicate saved active/alternate read")
        anchors.add(anchor)


def validate_approvals(data: Any) -> Json:
    """Replay the audit chain; malformed histories must not be overwritten."""
    if (
        not isinstance(data, dict)
        or set(data) != {"schemaVersion", "revision", "source", "decisions", "history"}
        or data["schemaVersion"] != APPROVAL_SCHEMA
    ):
        raise ApprovalError("unrecognized approvals.json schemaVersion or fields")
    revision = _integer(data["revision"], "approvals revision")
    source = data["source"]
    decisions = data["decisions"]
    history = data["history"]
    if not isinstance(decisions, dict) or not isinstance(history, list):
        raise ApprovalError("invalid approvals decisions/history")
    if len(history) != revision or (revision == 0) != (source is None):
        raise ApprovalError("approvals revision/source/history mismatch")
    if source is not None:
        _check_source(source)
    replay: Json = {}
    for index, event in enumerate(history, 1):
        if not isinstance(event, dict) or set(event) != {
            "revision",
            "at",
            "operation",
            "rowId",
            "before",
            "after",
        }:
            raise ApprovalError("invalid approval history event")
        row_id = event["rowId"]
        if (
            type(row_id) is not str
            or re.fullmatch(r"row-[1-9][0-9]*", row_id) is None
            or type(event["revision"]) is not int
            or event["revision"] != index
            or event["operation"] not in ("choose", "undo")
        ):
            raise ApprovalError("invalid approval history revision or row")
        try:
            instant = datetime.fromisoformat(event["at"].replace("Z", "+00:00"))
        except (TypeError, ValueError, AttributeError) as error:
            raise ApprovalError("invalid UTC history timestamp") from error
        offset = instant.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ApprovalError("invalid UTC history timestamp")
        before, after = event["before"], event["after"]
        if before != replay.get(row_id) or before == after:
            raise ApprovalError("broken approvals history before/after chain")
        if before is not None:
            _check_decision(before, source, row_id)
        if after is not None:
            _check_decision(after, source, row_id)
            replay[row_id] = after
        else:
            replay.pop(row_id, None)
    if replay != decisions:
        raise ApprovalError("approvals decisions disagree with history")
    return data


def load_approvals(path: Path) -> Json:
    if not path.exists():
        return _empty_approvals()
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object,
            parse_constant=_bad_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ApprovalError(f"cannot read approvals.json: {error}") from error
    return validate_approvals(data)


def _record(doc: Json, row_id: str, next_decision: Json | None, operation: str) -> bool:
    previous = doc["decisions"].get(row_id)
    if previous == next_decision:
        return False
    doc["revision"] += 1
    doc["history"].append(
        {
            "revision": doc["revision"],
            "at": datetime.now(UTC)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z"),
            "operation": operation,
            "rowId": row_id,
            "before": previous,
            "after": next_decision,
        }
    )
    if next_decision is None:
        doc["decisions"].pop(row_id, None)
    else:
        doc["decisions"][row_id] = next_decision
    return True


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    """Serialize readers-modifiers-writers using a stable, never-replaced lock."""
    lock_path = path.with_name(path.name + ".lock")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as error:
        raise ApprovalError(f"cannot open approval lock: {error}") from error
    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    raise ApprovalError(
                        "approval file locked by another writer"
                    ) from error
                time.sleep(0.05)
        yield
    finally:
        os.close(descriptor)


def _atomic_save(path: Path, data: Json) -> None:
    """Commit in one replace; leave prior file intact if serialization fails."""
    try:
        payload = (
            json.dumps(
                validate_approvals(data),
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        descriptor, name = tempfile.mkstemp(prefix=".approvals-", dir=path.parent)
    except (OSError, ValueError, TypeError) as error:
        raise ApprovalError(f"cannot prepare approval write: {error}") from error
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        parent_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except OSError as error:
        raise ApprovalError(f"cannot commit approval write: {error}") from error
    finally:
        if os.path.exists(name):
            os.unlink(name)


def observed_video(
    video_path: Path, hash_video: Callable[[Path], str] | None = None
) -> str:
    """Hash the actual original source, never a derived audio surrogate."""
    if not video_path.is_file():
        raise ApprovalError(f"original video missing: {video_path}")
    try:
        digest = (hash_video or file_hash)(video_path)
    except OSError as error:
        raise ApprovalError(f"cannot read original video: {error}") from error
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise ApprovalError("invalid original-video sha256")
    return digest


def _inspect_original_metadata(path: Path) -> tuple[float, list[int]]:
    """Reuse #45's real ffprobe interpretation without importing at startup."""
    from vera_timeline_agent.presenter_takes import TakesError, probe_video

    try:
        return probe_video(path)
    except TakesError as error:
        raise ApprovalError(f"cannot inspect original video: {error}") from error


def _source_for_change(takes: Json, doc: Json, video_path: Path, sha: str) -> Json:
    current = source_identity(takes["video"], sha)
    if doc["source"] is None:
        if video_path.name != takes["video"]["file"]:
            raise ApprovalError("initial video filename does not match takes.json")
        duration, fps = _inspect_original_metadata(video_path)
        observed = {"file": video_path.name, "durationS": duration, "fps": fps}
        if frame_rate(observed) != frame_rate(takes["video"]) or video_duration(
            observed
        ) != video_duration(takes["video"]):
            raise ApprovalError("original video fps/duration differs from takes.json")
    elif any(
        doc["source"][key] != current[key] for key in ("sha256", "fps", "durationS")
    ):
        raise ApprovalError("original video SHA or timing differs from approvals")
    return current


def _selected_read(row: Json, video: Json, identifier: str) -> Json:
    matches = [
        candidate
        for candidate in full_reads(row, video)
        if identifier == read_key(candidate) or identifier in candidate["takes"]
    ]
    if len(matches) != 1:
        raise ApprovalError("take key/ID is missing or ambiguous; run choices")
    return matches[0]


def choose_approval(
    takes_path: Path,
    video_path: Path,
    row_id: str,
    state: str,
    *,
    take: str | None = None,
    alternates: list[str] | None = None,
    start_frame: int | None = None,
    end_frame: int | None = None,
    hash_video: Callable[[Path], str] | None = None,
) -> Json:
    """One atomic human decision; repeats produce no disk write or revision."""
    path = takes_path.with_name("approvals.json")
    with _locked(path):
        takes = load_takes(takes_path)
        doc = load_approvals(path)
        sha = observed_video(video_path, hash_video)
        current = _source_for_change(takes, doc, video_path, sha)
        row = next((r for r in takes["rows"] if r["id"] == row_id), None)
        if row is None:
            raise ApprovalError("unknown script passage")
        if state not in STATES:
            raise ApprovalError("unknown approval state")
        extra = alternates or []
        if state != "take":
            if (
                take is not None
                or extra
                or start_frame is not None
                or end_frame is not None
            ):
                raise ApprovalError("non-take state cannot have take/alternates/trims")
            decision: Json = {
                "state": state,
                "passage": {
                    "rowId": row_id,
                    "rowNumber": row["number"],
                    "script": row["script"],
                    "rowContext": row_context(takes),
                },
            }
        else:
            if take is None:
                raise ApprovalError("take state requires --take")
            read = _selected_read(row, takes["video"], take)
            cut = read["cut"]
            trim = None
            if start_frame is not None or end_frame is not None:
                trim = checked_trim(
                    takes["video"],
                    read,
                    cut["startFrame"] if start_frame is None else start_frame,
                    cut["endFrame"] if end_frame is None else end_frame,
                )
            active = freeze_read(takes, row_id, read, sha, trim)
            saved_alternates = []
            anchors = {read_key(read)}
            for identifier in extra:
                alternate = _selected_read(row, takes["video"], identifier)
                key = read_key(alternate)
                if key in anchors:
                    raise ApprovalError("duplicate active or alternate read")
                anchors.add(key)
                saved_alternates.append(freeze_read(takes, row_id, alternate, sha))
            decision = {
                "state": state,
                "active": active,
                "alternates": saved_alternates,
            }
        # Preserve all previous decisions/history on no-op, including their
        # original display basename and timestamps.
        if doc["decisions"].get(row_id) == decision:
            return doc
        if doc["source"] is None:
            doc["source"] = current
        _record(doc, row_id, decision, "choose")
        _atomic_save(path, doc)
        return doc


def undo_approval(
    takes_path: Path,
    video_path: Path,
    row_id: str,
    *,
    hash_video: Callable[[Path], str] | None = None,
) -> Json:
    """Reverse the latest event for this row by appending another event."""
    path = takes_path.with_name("approvals.json")
    with _locked(path):
        takes = load_takes(takes_path)
        doc = load_approvals(path)
        sha = observed_video(video_path, hash_video)
        _source_for_change(takes, doc, video_path, sha)
        event = next(
            (e for e in reversed(doc["history"]) if e["rowId"] == row_id),
            None,
        )
        if event is None:
            raise ApprovalError("no prior human change to undo for this row")
        # load_approvals has already replay-checked the complete audit chain.
        if doc["decisions"].get(row_id) != event["after"]:
            raise ApprovalError("cannot recover previous approval decision")
        _record(doc, row_id, event["before"], "undo")
        _atomic_save(path, doc)
        return doc


def _approved_range(frozen: Json, filename: str, rate: Fraction) -> Json:
    """Display *saved* effective frames, never reanalysis' nearby candidate cut."""
    start = frozen["effectiveCut"]["startFrame"]
    end = frozen["effectiveCut"]["endFrame"]
    return {
        "file": filename,
        "startFrame": start,
        "endFrame": end,
        "startS": str(Fraction(start, 1) / rate),
        "endS": str(Fraction(end, 1) / rate),
        "said": frozen["said"],
    }


def _saved_reference(frozen: Json) -> Json:
    """A review-only reference, deliberately not a build-ready range."""
    return {
        "originalFile": frozen["source"]["file"],
        "originalCut": frozen["originalCut"].copy(),
        "effectiveCut": frozen["effectiveCut"].copy(),
        "said": frozen["said"],
    }


def approved_performance(takes: Json, approvals: Json, sha: str) -> Json:
    """Render a script-ordered, fail-closed #47 handoff without mutating inputs.

    Only rows with state=take and validated active *and* alternate reads expose
    usable source ranges. Orphaned decisions are kept visible but never usable.
    """
    validate_takes(takes)
    validate_approvals(approvals)
    current_source = source_identity(takes["video"], sha)
    pinned = approvals["source"]
    source_mismatch = pinned is not None and any(
        current_source[key] != pinned[key] for key in ("sha256", "fps", "durationS")
    )
    rate = frame_rate(takes["video"])
    entries: list[Json] = []
    visible = {row["id"] for row in takes["rows"]}
    # Retain the fresh matched speech edges for the conservative join signal.
    timing: dict[str, tuple[Json, Json]] = {}
    for row in takes["rows"]:
        row_id = row["id"]
        decision = approvals["decisions"].get(row_id)
        item: Json = {
            "rowId": row_id,
            "rowNumber": row["number"],
            "script": row["script"],
            "state": "undecided" if decision is None else decision["state"],
        }
        if decision is None:
            entries.append(item)
            continue
        if decision["state"] != "take":
            passage = decision.get("passage")
            reason: str | None = None
            if source_mismatch:
                reason = "source recording or video timing changed"
            elif passage is None:
                reason = "legacy decision lacks script passage identity; reapprove"
            elif passage["rowContext"] != row_context(takes) or (
                passage["rowId"] != row_id
                or passage["rowNumber"] != row["number"]
                or passage["script"] != row["script"]
            ):
                reason = "script passage order or wording changed"
            if reason is not None:
                item.update(
                    state="needs_another_look",
                    previousState=decision["state"],
                    reason=reason,
                )
            entries.append(item)
            continue

        snapshots = [decision["active"], *decision["alternates"]]
        matched = [match_frozen_read(takes, snapshot, sha) for snapshot in snapshots]
        problems = [
            ("active" if i == 0 else f"alternate {i}") + f": {reason}"
            for i, (_, reason) in enumerate(matched)
            if reason is not None
        ]
        if problems:
            item.update(
                state="needs_another_look",
                previousState="take",
                reason="; ".join(problems),
                savedApproval=_saved_reference(decision["active"]),
            )
        else:
            item["active"] = _approved_range(
                decision["active"], takes["video"]["file"], rate
            )
            item["alternates"] = [
                _approved_range(snapshot, takes["video"]["file"], rate)
                for snapshot in decision["alternates"]
            ]
            # All matched reads exist when there are no problems.
            active_read = matched[0][0]
            assert active_read is not None
            timing[row_id] = (decision["active"], active_read)
        entries.append(item)

    joins: list[Json] = []
    for left, right in pairwise(entries):
        if left["state"] != "take" or right["state"] != "take":
            continue
        left_saved, left_read = timing[left["rowId"]]
        right_saved, right_read = timing[right["rowId"]]
        left_edge = (
            Fraction(left_saved["effectiveCut"]["endFrame"], 1)
            - _seconds(left_read["speechEndS"], "speechEndS") * rate
        )
        right_edge = _seconds(
            right_read["speechStartS"], "speechStartS"
        ) * rate - Fraction(right_saved["effectiveCut"]["startFrame"], 1)
        # Less than ten source frames of measured quiet on either edge is
        # suspicious, not evidence of a definitely audible jump cut.
        if left_edge < 10 or right_edge < 10:
            joins.append(
                {
                    "fromRowId": left["rowId"],
                    "toRowId": right["rowId"],
                    "kind": "possible_abrupt_join",
                    "reason": "less than 10 frames clear of speech at a cut edge",
                }
            )

    orphaned: list[Json] = []
    for row_id, decision in sorted(
        approvals["decisions"].items(),
        key=lambda entry: int(entry[0].split("-")[1]),
    ):
        if row_id in visible:
            continue
        orphan: Json = {
            "rowId": row_id,
            "state": "needs_another_look",
            "previousState": decision["state"],
            "reason": "approved script passage is missing from the current analysis",
        }
        if decision["state"] == "take":
            orphan["savedApproval"] = _saved_reference(decision["active"])
            orphan["savedScript"] = decision["active"]["script"]
        elif "passage" in decision:
            orphan["savedScript"] = decision["passage"]["script"]
        orphaned.append(orphan)
    return {
        "schemaVersion": PERFORMANCE_SCHEMA,
        "approvalRevision": approvals["revision"],
        "source": current_source,
        "rows": entries,
        "possibleAbruptJoins": joins,
        "orphanedDecisions": orphaned,
    }


def approved_performance_text(report: Json) -> str:
    """Human review text; never state a stale snapshot as an approved cut."""

    def line(value: str) -> str:
        return " ".join(value.split())

    lines = [
        "APPROVED PRESENTER PERFORMANCE",
        f"Approval revision: {report['approvalRevision']}",
        f"Recording: {line(report['source']['file'])}",
        "",
    ]
    for row in report["rows"]:
        lines.append(f"{row['rowNumber']}. {row['rowId']}: {line(row['script'])}")
        state = row["state"]
        if state == "take":
            active = row["active"]
            lines.append(
                f"   APPROVED TAKE: {line(active['file'])} "
                f"frames {active['startFrame']}-{active['endFrame']} "
                f"({active['startS']}s-{active['endS']}s)"
            )
            lines.append(f"   Said: {line(active['said'])}")
            for alt in row["alternates"]:
                lines.append(
                    f"   Alternate: {line(alt['file'])} "
                    f"frames {alt['startFrame']}-{alt['endFrame']} — "
                    f"{line(alt['said'])}"
                )
        elif state == "needs_another_look":
            lines.append(
                f"   NEEDS ANOTHER LOOK ({row['previousState']}): {line(row['reason'])}"
            )
        else:
            lines.append(f"   {state.replace('_', ' ').upper()}")
        lines.append("")
    for join in report["possibleAbruptJoins"]:
        lines.append(
            f"POSSIBLE ABRUPT JOIN: {join['fromRowId']} → {join['toRowId']} "
            f"— {join['reason']} (check by ear)"
        )
    for orphan in report["orphanedDecisions"]:
        lines.append(
            f"ORPHANED DECISION {orphan['rowId']} "
            f"({orphan['previousState']}): {orphan['reason']}"
        )
    if not report["possibleAbruptJoins"] and not report["orphanedDecisions"]:
        lines.append("No possible abrupt joins or orphaned decisions detected.")
    return "\n".join(lines) + "\n"


def write_performance_reports(takes_path: Path, report: Json) -> None:
    """Write outputs beside takes.json, never changing approvals.json or takes.json.

    Both payloads are fully rendered before either replace; JSON is published
    last so the structured consumer sees the newest completed text preview.
    """
    outputs = (
        (
            takes_path.with_name("approved-performance.txt"),
            approved_performance_text(report).encode("utf-8"),
        ),
        (
            takes_path.with_name("approved-performance.json"),
            (
                json.dumps(
                    report,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                    allow_nan=False,
                )
                + "\n"
            ).encode("utf-8"),
        ),
    )
    for path, payload in outputs:
        name: str | None = None
        try:
            descriptor, name = tempfile.mkstemp(
                prefix=".approved-performance-", dir=path.parent
            )
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, path)
        except OSError as error:
            raise ApprovalError(
                f"cannot write approved performance: {error}"
            ) from error
        finally:
            if name is not None and os.path.exists(name):
                os.unlink(name)
