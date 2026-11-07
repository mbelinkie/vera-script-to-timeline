"""Shared v2 paired-direction token projection for narration consumers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _plain_direction(block: Mapping[str, Any]) -> bool:
    """Validate persisted whole-row intent before any direct Python consumer uses it."""

    if "plainDirection" not in block:
        return False
    if block["plainDirection"] is not True:
        raise ValueError("plainDirection must be true when present")
    text = block.get("text")
    tokens = block.get("tokens")
    if not isinstance(text, str) or not isinstance(tokens, list):
        raise ValueError("plain direction requires text and frozen tokens")
    try:
        encoded = text.encode("utf-16-le")
    except UnicodeEncodeError as error:
        raise ValueError("plain direction contains an unpaired surrogate") from error
    prior_end = 0
    for token in tokens:
        if not isinstance(token, Mapping) or token.get("spoken") is not False:
            raise ValueError("plain direction tokens must all be nonspoken")
        start, end, value = (
            token.get("startOffset"),
            token.get("endOffset"),
            token.get("value"),
        )
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or not isinstance(value, str)
            or not value
            or start < prior_end
            or start >= end
            or end > len(encoded) // 2
        ):
            raise ValueError("plain direction token range is invalid")
        try:
            quoted = encoded[start * 2 : end * 2].decode("utf-16-le")
        except UnicodeDecodeError as error:
            raise ValueError("plain direction token splits a surrogate pair") from error
        if quoted != value:
            raise ValueError("plain direction frozen token differs from text")
        prior_end = end
    return True


def spoken_tokens(block: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if _plain_direction(block):
        return []
    tokens = block.get("tokens")
    if not isinstance(tokens, list):
        raise ValueError("narration tokens are required")
    return [
        token
        for token in tokens
        if isinstance(token, Mapping) and token.get("spoken") is not False
    ]


def is_direction_only(block: Mapping[str, Any]) -> bool:
    if _plain_direction(block):
        return True
    tokens = block.get("tokens")
    return (
        isinstance(tokens, list)
        and any(
            isinstance(token, Mapping) and token.get("spoken") is False
            for token in tokens
        )
        and not any(
            isinstance(token, Mapping) and token.get("spoken") is not False
            for token in tokens
        )
    )


def masked_text(block: Mapping[str, Any]) -> str:
    """Return provider text with recognized directions blanked at equal UTF-16 width."""

    text = block.get("text")
    tokens = block.get("tokens")
    if not isinstance(text, str) or not isinstance(tokens, list):
        raise ValueError("narration text and tokens are required")
    if _plain_direction(block):
        # No brackets are structural here. Preserve provider UTF-16 offsets,
        # including a surrogate pair's two code units, without leaking text.
        return "".join(" " * (len(char.encode("utf-16-le")) // 2) for char in text)
    for token in tokens:
        if (
            isinstance(token, Mapping)
            and "spoken" in token
            and not isinstance(token["spoken"], bool)
        ):
            raise ValueError("narration token spoken classification must be boolean")

    direction = [
        index
        for index, token in enumerate(tokens)
        if isinstance(token, Mapping) and token.get("spoken") is False
    ]
    if not direction:
        return text

    def offset_to_index(offset: object) -> int | None:
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            return None
        units = 0
        for index, character in enumerate(text):
            if units == offset:
                return index
            units += len(character.encode("utf-16-le")) // 2
            if units > offset:
                return None
        return len(text) if units == offset else None

    groups: list[list[Mapping[str, Any]]] = []
    for index in direction:
        token = tokens[index]
        if not isinstance(token, Mapping):
            raise ValueError("direction token is invalid")
        if groups:
            prior = groups[-1][-1]
            prior_index = tokens.index(prior)
            gap_start = offset_to_index(prior.get("endOffset"))
            gap_end = offset_to_index(token.get("startOffset"))
            gap = (
                text[gap_start:gap_end]
                if gap_start is not None
                and gap_end is not None
                and gap_start <= gap_end
                else "[invalid]"
            )
            if index == prior_index + 1 and "[" not in gap and "]" not in gap:
                groups[-1].append(token)
                continue
        groups.append([token])

    spans: list[tuple[int, int]] = []
    for group in groups:
        first, last = group[0], group[-1]
        start = first.get("startOffset")
        end = last.get("endOffset")
        content_start = offset_to_index(start)
        content_end = offset_to_index(end)
        if (
            content_start is None
            or content_end is None
            or content_start <= 0
            or content_end >= len(text)
        ):
            raise ValueError("direction tokens need complete UTF-16 ranges")
        if text[content_start - 1] != "[" or text[content_end] != "]":
            raise ValueError(
                "direction tokens must have one complete square-bracket pair"
            )
        if (
            "[" in text[content_start:content_end]
            or "]" in text[content_start:content_end]
            or (content_start > 1 and text[content_start - 2] == "[")
            or (content_end + 1 < len(text) and text[content_end + 1] == "]")
        ):
            raise ValueError(
                "nested or literal brackets inside a direction pair are unsupported"
            )
        if any(
            not isinstance(token, Mapping)
            or not isinstance(token.get("startOffset"), int)
            or not isinstance(token.get("endOffset"), int)
            or offset_to_index(token.get("startOffset")) is None
            or offset_to_index(token.get("endOffset")) is None
            or text[
                offset_to_index(token["startOffset"]) : offset_to_index(
                    token["endOffset"]
                )
            ]
            != token.get("value")
            for token in group
        ):
            raise ValueError("direction token offsets do not match authored text")
        spans.append((content_start - 1, content_end + 1))

    chars: list[str] = []
    cursor = 0
    for start, end in spans:
        chars.append(text[cursor:start])
        chars.append(
            "".join(
                " " * (len(character.encode("utf-16-le")) // 2)
                for character in text[start:end]
            )
        )
        cursor = end
    chars.append(text[cursor:])
    result = "".join(chars)
    if len(result.encode("utf-16-le")) != len(text.encode("utf-16-le")):
        raise ValueError("direction masking changed authored UTF-16 offsets")
    return result
