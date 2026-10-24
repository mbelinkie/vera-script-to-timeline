"""Map retained issue #289 provider timing to frozen tokens, offline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import unicodedata
import wave
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

OUTPUT_NAME = "native-analysis.private.json"
CSV_NAME = "native-points.private.csv"
CSV_HEADER = ("Name", "Start", "Duration", "Time Format", "Type", "Description")
NOT_VERIFIED = "NOT HUMAN VERIFIED"


@dataclass(frozen=True)
class Token:
    id: str
    value: str
    start_offset: int
    end_offset: int
    start_cp: int
    end_cp: int


@dataclass(frozen=True)
class TimedSpan:
    start_cp: int
    end_cp: int
    native_start: float | None
    native_end: float | None
    lexical: bool
    non_finite: int = 0
    missing: int = 0


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _time_value(value: Any) -> tuple[float | None, int, int]:
    result = _finite_number(value)
    if result is not None:
        return result, 0, 0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return None, 1, 0
    return None, 0, 1


def _is_lexical(char: str) -> bool:
    return unicodedata.category(char)[0] in {"L", "M", "N"}


def _utf16_boundaries(text: str) -> dict[int, int]:
    result = {0: 0}
    offset = 0
    for index, char in enumerate(text, start=1):
        offset += 2 if ord(char) > 0xFFFF else 1
        result[offset] = index
    return result


def _frozen_tokens(row: Any) -> tuple[str, list[Token], bool]:
    if not isinstance(row, dict) or not isinstance(row.get("text"), str):
        return "", [], False
    text = row["text"]
    raw_tokens = row.get("tokens")
    if not isinstance(raw_tokens, list) or not raw_tokens:
        return text, [], False

    try:
        boundaries = _utf16_boundaries(text)
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    except UnicodeEncodeError:
        return text, [], False
    hash_valid = row.get("textHash") in (None, text_hash, f"sha256:{text_hash}")

    tokens: list[Token] = []
    ids: set[str] = set()
    previous_end = 0
    valid = hash_valid
    for raw in raw_tokens:
        if not isinstance(raw, dict):
            valid = False
            continue
        token_id = raw.get("id")
        value = raw.get("value")
        start = raw.get("startOffset")
        end = raw.get("endOffset")
        if (
            not isinstance(token_id, str)
            or token_id in ids
            or not isinstance(value, str)
            or isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
            or start < previous_end
            or start not in boundaries
            or end not in boundaries
            or end <= start
        ):
            valid = False
            continue
        start_cp, end_cp = boundaries[start], boundaries[end]
        if text[start_cp:end_cp] != value:
            valid = False
            continue
        ids.add(token_id)
        previous_end = end
        tokens.append(Token(token_id, value, start, end, start_cp, end_cp))
    return text, tokens, valid and len(tokens) == len(raw_tokens)


def _edit_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def _characters(value: Any) -> list[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return None
    return value


def _timed_spans(
    text: str,
    units: list[str],
    starts: Any,
    ends: Any,
    *,
    allow_punctuation_variants: bool = False,
) -> tuple[list[TimedSpan], str, int | None, bool]:
    """Project ordered provider units onto source code points without fuzzy edits."""
    joined = "".join(units)
    mismatch = _edit_distance(joined, text)
    if not isinstance(starts, list) or not isinstance(ends, list):
        return [], "array_length_mismatch", mismatch, False
    if len(units) != len(starts) or len(units) != len(ends):
        return [], "array_length_mismatch", mismatch, False

    spans: list[TimedSpan] = []
    if joined == text:
        cursor = 0
        for unit, start, end in zip(units, starts, ends, strict=True):
            finish = cursor + len(unit)
            first, first_bad, first_missing = _time_value(start)
            last, last_bad, last_missing = _time_value(end)
            spans.append(
                TimedSpan(
                    cursor,
                    finish,
                    first,
                    last,
                    any(_is_lexical(char) for char in unit),
                    first_bad + last_bad,
                    first_missing + last_missing,
                )
            )
            cursor = finish
        return spans, "exact", mismatch, True

    if not allow_punctuation_variants:
        return [], "provider_text_mismatch", mismatch, False

    source_lexical = [
        (index, char) for index, char in enumerate(text) if _is_lexical(char)
    ]
    unit_lexical = [
        (unit_index, char)
        for unit_index, unit in enumerate(units)
        for char in unit
        if _is_lexical(char)
    ]
    if [char for _, char in source_lexical] != [char for _, char in unit_lexical]:
        return [], "provider_text_mismatch", mismatch, False

    by_unit: dict[int, list[int]] = {}
    for (unit_index, _), (source_index, _) in zip(
        unit_lexical, source_lexical, strict=True
    ):
        by_unit.setdefault(unit_index, []).append(source_index)
    for unit_index, (unit, start, end) in enumerate(
        zip(units, starts, ends, strict=True)
    ):
        first, first_bad, first_missing = _time_value(start)
        last, last_bad, last_missing = _time_value(end)
        positions = by_unit.get(unit_index, [])
        if positions:
            spans.append(
                TimedSpan(
                    min(positions),
                    max(positions) + 1,
                    first,
                    last,
                    True,
                    first_bad + last_bad,
                    first_missing + last_missing,
                )
            )
        elif not any(_is_lexical(char) for char in unit):
            spans.append(
                TimedSpan(
                    -1,
                    -1,
                    first,
                    last,
                    False,
                    first_bad + last_bad,
                    first_missing + last_missing,
                )
            )
    return spans, "exact_lexical", mismatch, True


def _snapshot_spans(text: str, snapshots: Any) -> tuple[list[TimedSpan], str, bool]:
    if not isinstance(snapshots, list) or not snapshots:
        return [], "missing_snapshots", False
    spans: list[TimedSpan] = []
    source_cursor = 0
    status = "exact"
    for expected_seq, snapshot in enumerate(snapshots):
        if not isinstance(snapshot, dict) or snapshot.get("seq") != expected_seq:
            return spans, "snapshot_sequence_mismatch", False
        content = snapshot.get("content")
        if not isinstance(content, str) or not content:
            return spans, "snapshot_content_mismatch", False
        chunk_start = text.find(content, source_cursor)
        if chunk_start < 0 or text[source_cursor:chunk_start].strip():
            return spans, "snapshot_content_mismatch", False
        chunk_end = chunk_start + len(content)
        segment_cursor = chunk_start
        alignment = snapshot.get("alignment")
        segments = alignment.get("segments") if isinstance(alignment, dict) else None
        offset = _finite_number(snapshot.get("offset"))
        if not isinstance(segments, list) or not segments:
            return spans, "missing_segments", False
        for segment in segments:
            if not isinstance(segment, dict) or not isinstance(
                segment.get("text"), str
            ):
                return spans, "invalid_segment", False
            piece = segment["text"].strip()
            if not piece:
                continue
            local = (
                text[segment_cursor:chunk_end]
                .replace("\u2019", "'")
                .find(piece.replace("\u2019", "'"))
            )
            left = segment_cursor + local if local >= 0 else -1
            if left < 0 or any(_is_lexical(c) for c in text[segment_cursor:left]):
                return spans, "segment_text_mismatch", False
            right = left + len(piece)
            if right > chunk_end:
                return spans, "segment_text_mismatch", False
            local_start = _finite_number(segment.get("start"))
            local_end = _finite_number(segment.get("end"))
            first = (
                offset + local_start
                if offset is not None and local_start is not None
                else None
            )
            last = (
                offset + local_end
                if offset is not None and local_end is not None
                else None
            )
            raw_values = (
                snapshot.get("offset"),
                segment.get("start"),
                segment.get("end"),
            )
            bad = sum(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and not math.isfinite(float(value))
                for value in raw_values
            )
            missing = sum(_finite_number(value) is None for value in raw_values) - bad
            spans.append(
                TimedSpan(
                    left,
                    right,
                    first,
                    last,
                    any(_is_lexical(char) for char in piece),
                    bad,
                    missing,
                )
            )
            segment_cursor = right
        if any(_is_lexical(c) for c in text[segment_cursor:chunk_end]):
            status = "incomplete_segment_coverage"
        source_cursor = chunk_end
    if any(_is_lexical(c) for c in text[source_cursor:]):
        status = "incomplete_segment_coverage"
    return spans, status, True


def _mark_spans(text: str, marks: Any) -> tuple[list[TimedSpan], str, bool]:
    if not isinstance(marks, list):
        return [], "missing_timing_marks", False
    boundaries = _utf16_boundaries(text)
    spans: list[TimedSpan] = []
    mismatch = False
    for mark in marks:
        if not isinstance(mark, dict) or mark.get("kind") != "word":
            continue
        start = mark.get("start_utf16")
        end = mark.get("end_utf16")
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
            or start not in boundaries
            or end not in boundaries
            or end <= start
        ):
            mismatch = True
            continue
        left, right = boundaries[start], boundaries[end]
        value = mark.get("value")
        if not isinstance(value, str) or text[left:right] != value:
            mismatch = True
            continue
        first_raw = mark.get("time_sample")
        first, first_bad, first_missing = _time_value(first_raw)
        rate = _finite_number(mark.get("sample_rate"))
        if first is not None and rate is not None and rate > 0:
            first /= rate
        else:
            first_ms, fallback_bad, fallback_missing = _time_value(mark.get("time_ms"))
            first = first_ms / 1000 if first_ms is not None else None
            first_bad, first_missing = fallback_bad, fallback_missing
        last_sample, last_bad, last_missing = _time_value(mark.get("end_sample"))
        last = (
            last_sample / rate
            if last_sample is not None and rate is not None and rate > 0
            else None
        )
        spans.append(
            TimedSpan(
                left,
                right,
                first,
                last,
                any(_is_lexical(char) for char in value),
                first_bad + last_bad,
                first_missing + last_missing,
            )
        )
    return spans, "invalid_timing_mark_span" if mismatch else "exact", not mismatch


def _project_tokens(
    tokens: list[Token], spans: list[TimedSpan], source_valid: bool, span_status: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    token_rows: list[dict[str, Any]] = []
    lexical_starts: list[float] = []
    raw_non_finite = 0
    raw_missing = 0
    lexical_non_finite = 0
    lexical_missing = 0
    punctuation_non_finite = 0
    punctuation_missing = 0
    raw_lexical_starts: list[float] = []

    # Native bounds are applied later, once the WAV duration is known.
    assignments: list[list[TimedSpan]] = [[] for _ in tokens]
    ambiguous: set[int] = set()
    token_positions: list[dict[int, int]] = []
    cp_to_token: dict[int, int] = {}
    for index, token in enumerate(tokens):
        positions = {
            cp
            for cp in range(token.start_cp, token.end_cp)
            if _is_lexical(token.value[cp - token.start_cp])
        }
        token_positions.append({cp: 0 for cp in positions})
        for cp in positions:
            cp_to_token[cp] = index

    for span in spans:
        lexical = span.lexical
        raw_non_finite += span.non_finite
        raw_missing += span.missing
        if lexical:
            lexical_non_finite += span.non_finite
            lexical_missing += span.missing
        else:
            punctuation_non_finite += span.non_finite
            punctuation_missing += span.missing
        if lexical and span.native_start is not None:
            raw_lexical_starts.append(span.native_start)
        if span.start_cp < 0 or span.end_cp <= span.start_cp:
            continue
        affected = sorted(
            {
                cp_to_token[cp]
                for cp in range(span.start_cp, span.end_cp)
                if cp in cp_to_token
            }
        )
        if len(affected) > 1:
            ambiguous.update(affected)
            continue
        if len(affected) != 1:
            continue
        index = affected[0]
        assignments[index].append(span)
        for cp in range(
            max(span.start_cp, tokens[index].start_cp),
            min(span.end_cp, tokens[index].end_cp),
        ):
            if cp in token_positions[index]:
                token_positions[index][cp] += 1

    for index, token in enumerate(tokens):
        positions = token_positions[index]
        count_values = list(positions.values())
        if not source_valid:
            status = "invalid_source"
        elif span_status not in {"exact", "exact_lexical"}:
            status = span_status
        elif index in ambiguous or any(count > 1 for count in count_values):
            status = "ambiguous"
        elif not positions:
            status = "no_spoken_characters"
        elif any(count == 0 for count in count_values):
            status = "incomplete"
        else:
            status = "exact"
        matching = assignments[index]
        first_cp = min(positions) if positions else None
        last_cp = max(positions) if positions else None
        first_spans = [
            span
            for span in matching
            if first_cp is not None and span.start_cp <= first_cp < span.end_cp
        ]
        last_spans = [
            span
            for span in matching
            if last_cp is not None and span.start_cp <= last_cp < span.end_cp
        ]
        starts = [span.native_start for span in first_spans]
        ends = [span.native_end for span in last_spans]
        native_start = starts[0] if starts else None
        native_end = ends[-1] if ends else None
        if status != "exact":
            native_start = native_end = None
        token_rows.append(
            {
                "id": token.id,
                "value": token.value,
                "startOffset": token.start_offset,
                "endOffset": token.end_offset,
                "nativeStart": native_start,
                "nativeEnd": native_end,
                "mappingStatus": status,
            }
        )
        if native_start is not None:
            lexical_starts.append(native_start)
        else:
            lexical_starts.append(math.nan)

    return token_rows, {
        "rawNonFinite": raw_non_finite,
        "rawMissing": raw_missing,
        "lexicalNonFinite": lexical_non_finite,
        "lexicalMissing": lexical_missing,
        "punctuationNonFinite": punctuation_non_finite,
        "punctuationMissing": punctuation_missing,
        "rawOutOfBounds": 0,
        "lexicalOutOfBounds": 0,
        "punctuationOutOfBounds": 0,
        "rawLexicalStarts": raw_lexical_starts,
        "tokenStarts": lexical_starts,
    }


def _audio_duration(
    take_dir: Path, request: dict[str, Any]
) -> tuple[float | None, str]:
    path = take_dir / "audio.wav"
    try:
        with wave.open(str(path), "rb") as audio:
            rate = audio.getframerate()
            if rate > 0:
                return audio.getnframes() / rate, "audio.wav"
    except (OSError, wave.Error):
        pass
    audio_meta = request.get("audio")
    duration = (
        _finite_number(audio_meta.get("durationSeconds"))
        if isinstance(audio_meta, dict)
        else None
    )
    return (
        (duration, "request.audio")
        if duration is not None and duration > 0
        else (None, "unavailable")
    )


def _add_bounds(
    spans: list[TimedSpan],
    token_rows: list[dict[str, Any]],
    duration: float | None,
    metrics: dict[str, Any],
) -> None:
    if duration is None:
        metrics.update(
            {
                "rawOutOfBounds": None,
                "lexicalOutOfBounds": None,
                "punctuationOutOfBounds": None,
                "outOfBounds": None,
            }
        )
        return

    def outside(value: float | None) -> bool:
        return value is not None and (value < 0 or value > duration)

    raw = lexical = punctuation = 0
    for span in spans:
        count = sum(outside(value) for value in (span.native_start, span.native_end))
        raw += count
        if span.lexical:
            lexical += count
        else:
            punctuation += count
    token_boundaries = 0
    for token in token_rows:
        token_boundaries += sum(
            outside(token[field]) for field in ("nativeStart", "nativeEnd")
        )
    metrics.update(
        {
            "rawOutOfBounds": raw,
            "lexicalOutOfBounds": lexical,
            "punctuationOutOfBounds": punctuation,
            "outOfBounds": token_boundaries,
        }
    )


def _consecutive_counts(values: list[float | None]) -> tuple[int, int, bool]:
    ties = decreases = 0
    strictly_increasing = True
    previous: float | None = None
    for value in values:
        if value is None or not math.isfinite(value):
            strictly_increasing = False
            previous = None
            continue
        if previous is not None:
            if value == previous:
                ties += 1
                strictly_increasing = False
            elif value < previous:
                decreases += 1
                strictly_increasing = False
        previous = value
    return ties, decreases, strictly_increasing


def _time_text(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    minutes, remainder = divmod(milliseconds, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    return f"{minutes}:{whole_seconds:02d}.{millis:03d}"


def _write_points(
    path: Path, tokens: list[dict[str, Any]], duration: float | None
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\r\n")
        writer.writerow(CSV_HEADER)
        for token in tokens:
            start = token.get("nativeStart")
            if (
                token.get("mappingStatus") != "exact"
                or not isinstance(start, (int, float))
                or isinstance(start, bool)
                or not math.isfinite(start)
                or start < 0
                or (duration is not None and start > duration)
            ):
                continue
            writer.writerow(
                (
                    token["value"],
                    _time_text(start),
                    "0:00.000",
                    "decimal",
                    "Cue",
                    NOT_VERIFIED,
                )
            )


def analyze_take(take_dir: Path) -> dict[str, Any]:
    request_path = take_dir / "request.private.json"
    response_path = take_dir / "response.raw.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    response = (
        json.loads(response_path.read_text(encoding="utf-8"))
        if response_path.exists()
        else {}
    )
    if not isinstance(request, dict):
        raise ValueError("request is not an object")
    provider = str(request.get("provider", "unknown")).lower()
    text, tokens, source_valid = _frozen_tokens(request.get("row"))
    duration, duration_source = _audio_duration(take_dir, request)
    expected_audio = request.get("audio", {}).get("sha256")
    actual_audio = (
        hashlib.sha256((take_dir / "audio.wav").read_bytes()).hexdigest()
        if (take_dir / "audio.wav").exists()
        else None
    )
    audio_valid = expected_audio is None or expected_audio in (
        actual_audio,
        f"sha256:{actual_audio}",
    )

    spans: list[TimedSpan] = []
    span_status = "missing_alignment"
    text_mismatch_counts: dict[str, int | None] = {}
    mapping_method = "unavailable"
    if provider == "elevenlabs":
        alignment = response.get("alignment")
        normalized = response.get("normalized_alignment")
        if isinstance(alignment, dict):
            chars = _characters(alignment.get("characters"))
            if chars is None:
                span_status = "invalid_characters"
            else:
                spans, span_status, mismatch, _ = _timed_spans(
                    text,
                    chars,
                    alignment.get("character_start_times_seconds"),
                    alignment.get("character_end_times_seconds"),
                )
                text_mismatch_counts["original"] = mismatch
                mapping_method = "original_character_alignment"
        normalized_mismatch: int | None = None
        if isinstance(normalized, dict):
            normalized_chars = _characters(normalized.get("characters"))
            if normalized_chars is not None:
                normalized_mismatch = _edit_distance("".join(normalized_chars), text)
        text_mismatch_counts["normalized"] = normalized_mismatch
    elif provider == "inworld":
        timestamp_info = response.get("timestampInfo")
        word_alignment = (
            timestamp_info.get("wordAlignment")
            if isinstance(timestamp_info, dict)
            else None
        )
        if isinstance(word_alignment, dict):
            words = _characters(word_alignment.get("words"))
            if words is None:
                span_status = "invalid_words"
            else:
                spans, span_status, mismatch, _ = _timed_spans(
                    text,
                    words,
                    word_alignment.get("wordStartTimeSeconds"),
                    word_alignment.get("wordEndTimeSeconds"),
                    allow_punctuation_variants=True,
                )
                text_mismatch_counts["inworld"] = mismatch
                mapping_method = "ordered_lexical_alignment"
    elif isinstance(response.get("timingMarks"), list):
        spans, span_status, _ = _mark_spans(text, response.get("timingMarks"))
        mapping_method = "exact_utf16_word_marks"
    elif isinstance(response.get("alignmentSnapshots"), list):
        spans, span_status, _ = _snapshot_spans(
            text, response.get("alignmentSnapshots")
        )
        mapping_method = "sequential_fish_segments"

    token_rows, metrics = _project_tokens(tokens, spans, source_valid, span_status)
    _add_bounds(spans, token_rows, duration, metrics)
    raw_ties, raw_decreases, raw_increasing = _consecutive_counts(
        metrics.pop("rawLexicalStarts")
    )
    token_ties, token_decreases, token_increasing = _consecutive_counts(
        metrics.pop("tokenStarts")
    )

    total = len(tokens)
    exact_count = sum(token["mappingStatus"] == "exact" for token in token_rows)
    exact_coverage = total > 0 and exact_count == total
    finite_starts = all(
        isinstance(token["nativeStart"], (int, float))
        and not isinstance(token["nativeStart"], bool)
        and math.isfinite(token["nativeStart"])
        for token in token_rows
    )
    token_ends_finite = all(
        token["nativeEnd"] is None
        or (
            isinstance(token["nativeEnd"], (int, float))
            and not isinstance(token["nativeEnd"], bool)
            and math.isfinite(token["nativeEnd"])
        )
        for token in token_rows
    )
    ends_available = all(token["nativeEnd"] is not None for token in token_rows)
    invalid_intervals = sum(
        span.lexical
        and span.native_start is not None
        and span.native_end is not None
        and span.native_end < span.native_start
        for span in spans
    ) + sum(
        token["nativeStart"] is not None
        and token["nativeEnd"] is not None
        and token["nativeEnd"] <= token["nativeStart"]
        for token in token_rows
    )
    in_bounds = (
        duration is not None
        and metrics["outOfBounds"] == 0
        and metrics["lexicalOutOfBounds"] == 0
    )
    structural_pass = (
        exact_coverage
        and audio_valid
        and finite_starts
        and token_ends_finite
        and token_increasing
        and in_bounds
        and metrics["lexicalNonFinite"] == 0
        and not invalid_intervals
    )
    collapsed = (
        sum(
            token["nativeStart"] == token["nativeEnd"]
            for token in token_rows
            if token["nativeStart"] is not None and token["nativeEnd"] is not None
        )
        if ends_available
        else None
    )
    overlaps = (
        sum(
            current["nativeStart"] < previous["nativeEnd"]
            for previous, current in pairwise(token_rows)
            if previous["nativeEnd"] is not None and current["nativeStart"] is not None
        )
        if ends_available
        else None
    )
    result = {
        "schemaVersion": "issue289-native-analysis/v1",
        "provider": provider,
        "takeId": request.get("takeId", take_dir.name),
        "humanVerified": False,
        "acousticVerified": False,
        "verificationLabel": NOT_VERIFIED,
        "mappingMethod": mapping_method,
        "sourceTextHashValid": source_valid,
        "audioHashValid": audio_valid,
        "audioDurationSeconds": duration,
        "audioDurationSource": duration_source,
        "textMismatchCounts": text_mismatch_counts,
        "tokens": token_rows,
        "coverage": {
            "totalTokens": total,
            "exactTokens": exact_count,
            "missingTokens": total - exact_count,
            "percent": (100.0 * exact_count / total) if total else 0.0,
        },
        "ties": token_ties,
        "decreases": token_decreases,
        "rawTies": raw_ties,
        "rawDecreases": raw_decreases,
        "strictlyIncreasingStarts": token_increasing,
        "rawStrictlyIncreasingStarts": raw_increasing,
        "nonFinite": metrics["rawNonFinite"],
        "missingTimingValues": metrics["rawMissing"],
        "lexicalNonFinite": metrics["lexicalNonFinite"],
        "lexicalMissingTimingValues": metrics["lexicalMissing"],
        "punctuationNonFinite": metrics["punctuationNonFinite"],
        "outOfBounds": metrics["outOfBounds"],
        "rawOutOfBounds": metrics["rawOutOfBounds"],
        "lexicalOutOfBounds": metrics["lexicalOutOfBounds"],
        "punctuationOutOfBounds": metrics["punctuationOutOfBounds"],
        "collapsed": collapsed,
        "invalidIntervals": invalid_intervals,
        "overlaps": overlaps,
        "endsAvailable": ends_available,
        "structuralPass": structural_pass,
        "structuralPassCriteria": [
            "100% exact token coverage",
            "finite in-bounds native starts",
            "strictly increasing native starts",
            "all reported lexical timing values finite and in bounds",
        ],
        "limitations": [
            "Native structure only; no human or acoustic verification was performed.",
            "Punctuation is excluded from lexical token edges "
            "where the provider exposes separate units.",
        ],
    }
    if provider == "elevenlabs":
        result["limitations"].append(
            "Native punctuation timing can extend past the WAV edge "
            "and is reported separately from word timing."
        )
    _write_points(take_dir / CSV_NAME, token_rows, duration)
    (take_dir / OUTPUT_NAME).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return result


def analyze_directory(takes_dir: Path) -> dict[str, int]:
    if (takes_dir / "request.private.json").exists():
        take_dirs = [takes_dir]
    else:
        take_dirs = sorted(
            path
            for path in takes_dir.iterdir()
            if path.is_dir() and (path / "request.private.json").exists()
        )
    provider_counts: dict[str, int] = {}
    pass_count = 0
    failed_count = 0
    for take_dir in take_dirs:
        try:
            result = analyze_take(take_dir)
        except (OSError, ValueError, TypeError, json.JSONDecodeError, wave.Error):
            failed_count += 1
            continue
        provider = str(result.get("provider", "unknown"))
        provider_counts[provider] = provider_counts.get(provider, 0) + 1
        pass_count += bool(result.get("structuralPass"))
    return {
        "takeCount": len(take_dirs),
        "structuralPassCount": pass_count,
        "unreadableTakeCount": failed_count,
        **{
            f"provider_{name}_count": count
            for name, count in sorted(provider_counts.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "takes_dir", type=Path, help="offline take directory or its parent"
    )
    args = parser.parse_args()
    summary = analyze_directory(args.takes_dir)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
