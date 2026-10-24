from __future__ import annotations

import math
import unicodedata
from collections.abc import Mapping
from fractions import Fraction
from typing import Any

from vera_timeline_agent.narration.fish import _source_words
from vera_timeline_agent.narration.models import ProviderTimingMark

SAMPLE_RATE = 48_000


class InworldTimingError(ValueError):
    """Inworld word timestamps cannot be mapped safely to authored text."""


def timing_marks(
    text: str, response: dict[str, Any], audio_frames: int
) -> tuple[ProviderTimingMark, ...]:
    """Map exact native WORD timing onto contiguous source tokens.

    Native pieces may split one source token; their first and last lexical
    timestamps become that token's structural bounds. A piece that covers
    lexical characters from multiple tokens is ambiguous and is rejected.
    """
    if not isinstance(text, str) or not text:
        raise InworldTimingError("authored text must be a non-empty string")
    if isinstance(audio_frames, bool) or not isinstance(audio_frames, int):
        raise InworldTimingError("audio frame count must be an integer")
    if audio_frames <= 0:
        raise InworldTimingError("audio frame count must be positive")
    if not isinstance(response, Mapping):
        raise InworldTimingError("native response must be an object")

    timestamp_info = response.get("timestampInfo")
    if not isinstance(timestamp_info, Mapping):
        raise InworldTimingError("timestamp info is missing")
    alignment = timestamp_info.get("wordAlignment")
    if not isinstance(alignment, Mapping):
        raise InworldTimingError("native word alignment is missing")
    words = alignment.get("words")
    starts = alignment.get("wordStartTimeSeconds")
    ends = alignment.get("wordEndTimeSeconds")
    if (
        not isinstance(words, list)
        or not words
        or any(not isinstance(word, str) for word in words)
    ):
        raise InworldTimingError("native word pieces are missing or invalid")
    if "".join(words) != text:
        raise InworldTimingError("native word pieces do not exactly cover text")
    if not isinstance(starts, list) or not isinstance(ends, list):
        raise InworldTimingError("native timing arrays are missing")
    if len(words) != len(starts) or len(words) != len(ends):
        raise InworldTimingError("native timing arrays have different lengths")

    native_starts = [_finite_fraction(value, "word start") for value in starts]
    native_ends = [_finite_fraction(value, "word end") for value in ends]

    # Frozen token inventories are carried by script rows; use the narration
    # source-word boundaries, which trim punctuation at word edges.
    tokens = _source_words(text)
    if not tokens:
        raise InworldTimingError("text has no source tokens")
    cp_to_token: dict[int, int] = {}
    for index, (first, last) in enumerate(tokens):
        for cp in range(first, last):
            if _is_lexical(text[cp]):
                cp_to_token[cp] = index
    duration = Fraction(audio_frames, SAMPLE_RATE)
    piece_spans: list[tuple[int, int, Fraction, Fraction, int]] = []
    cursor = 0
    previous_start: Fraction | None = None
    previous_end: Fraction | None = None
    previous_sample_start = -1
    previous_sample_end = -1
    for word, start, end in zip(words, native_starts, native_ends, strict=True):
        lexical_positions = [
            cursor + offset for offset, char in enumerate(word) if _is_lexical(char)
        ]
        if lexical_positions:
            affected = {cp_to_token.get(cp) for cp in lexical_positions}
            if None in affected or len(affected) != 1:
                raise InworldTimingError(
                    "native word piece spans multiple source tokens"
                )
            token_index = next(iter(affected))
            assert token_index is not None
            if start < 0 or end <= start or end > duration:
                raise InworldTimingError(
                    "native lexical interval is collapsed or outside audio"
                )
            if previous_start is not None and (
                start <= previous_start or previous_end is None or start < previous_end
            ):
                raise InworldTimingError(
                    "native lexical intervals tie, decrease, or overlap"
                )
            start_sample, end_sample = (
                round(start * SAMPLE_RATE),
                round(end * SAMPLE_RATE),
            )
            if (
                start_sample <= previous_sample_start
                or start_sample < previous_sample_end
                or end_sample <= start_sample
                or end_sample > audio_frames
            ):
                raise InworldTimingError(
                    "native lexical interval collapses on the audio sample grid"
                )
            piece_spans.append(
                (
                    lexical_positions[0],
                    lexical_positions[-1] + 1,
                    start,
                    end,
                    token_index,
                )
            )
            previous_start, previous_end = start, end
            previous_sample_start, previous_sample_end = start_sample, end_sample
        cursor += len(word)

    by_token: list[list[tuple[int, Fraction, Fraction]]] = [[] for _ in tokens]
    for first_cp, _last_cp, start, end, token_index in piece_spans:
        by_token[token_index].append((first_cp, start, end))
    utf16_offsets = [0]
    byte_offsets = [0]
    try:
        for char in text:
            utf16_offsets.append(utf16_offsets[-1] + (2 if ord(char) > 0xFFFF else 1))
            byte_offsets.append(byte_offsets[-1] + len(char.encode("utf-8")))
    except UnicodeEncodeError as error:
        raise InworldTimingError("authored text is not valid Unicode") from error

    marks: list[ProviderTimingMark] = []
    for (first_cp, last_cp), spans in zip(tokens, by_token, strict=True):
        if not spans:
            raise InworldTimingError("native timing does not cover every source word")
        token_value = text[first_cp:last_cp]
        if not token_value:
            raise InworldTimingError("source token is empty")
        first_span = min(spans, key=lambda span: span[0])
        last_span = max(spans, key=lambda span: span[0])
        start_sample = round(first_span[1] * SAMPLE_RATE)
        end_sample = round(last_span[2] * SAMPLE_RATE)
        start_utf16, end_utf16 = utf16_offsets[first_cp], utf16_offsets[last_cp]
        start_byte, end_byte = byte_offsets[first_cp], byte_offsets[last_cp]
        marks.append(
            ProviderTimingMark(
                kind="word",
                time_ms=round(Fraction(start_sample * 1000, SAMPLE_RATE)),
                start_byte=start_byte,
                end_byte=end_byte,
                start_utf16=start_utf16,
                end_utf16=end_utf16,
                value=token_value,
                time_sample=start_sample,
                end_sample=end_sample,
                sample_rate=SAMPLE_RATE,
            )
        )
    if not marks:
        raise InworldTimingError("native word alignment has no lexical tokens")
    return tuple(marks)


def _finite_fraction(value: Any, label: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InworldTimingError(f"native {label} must be a finite number")
    try:
        if not math.isfinite(float(value)):
            raise InworldTimingError(f"native {label} must be a finite number")
        return Fraction(str(value))
    except (OverflowError, ValueError, ZeroDivisionError) as error:
        raise InworldTimingError(f"native {label} must be a finite number") from error


def _is_lexical(char: str) -> bool:
    return unicodedata.category(char)[0] in {"L", "M", "N", "S"}
