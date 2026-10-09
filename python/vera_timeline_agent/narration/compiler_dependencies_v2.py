"""Pure projection of a verified narration asset onto frozen v2 tokens."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from fractions import Fraction
from typing import Any, cast

from vera_timeline_agent.generated.contracts.compiler_dependencies_v2_schema import (
    NarrationTokenTimingMapV2,
    TokenTimingV2,
)
from vera_timeline_agent.generated.contracts.script_document_v2_schema import (
    NarrationBlockV2,
    NarrationToken,
)
from vera_timeline_agent.narration.compiler_dependencies import (
    NarrationDependencyError,
    narration_dependency_from_asset,
)
from vera_timeline_agent.narration.models import NarrationAudioAsset, sha256_bytes

_MAX_SAFE_INTEGER = 9_007_199_254_740_991
_TOKENIZATION_VERSION = "script-document/v2-frozen-tokens"
_ASSET_ID_NAMESPACE = uuid.NAMESPACE_URL
_ASSET_ID_PREFIX = "vera:narration-cache-asset:"


def narration_v2_dependency_from_asset(
    asset: NarrationAudioAsset,
    provider_timing_json: bytes,
    frozen_block: NarrationBlockV2,
) -> NarrationTokenTimingMapV2:
    """Bind verified word-start marks to the exact frozen v2 token snapshot.

    Provider timing is already mapped to original-text UTF-16 offsets by its
    adapter. This function preserves those offsets and the supplied token IDs;
    it does not retokenize, normalize, read files, or contact the provider.
    """

    projected = narration_dependency_from_asset(asset, provider_timing_json)
    if asset.status != "ready":
        raise NarrationDependencyError("ready narration asset is required")
    if not isinstance(frozen_block, Mapping) or frozen_block.get("type") != "narration":
        raise NarrationDependencyError("frozen narration block is invalid")

    block_id = frozen_block.get("id")
    revision = frozen_block.get("version")
    text = frozen_block.get("text")
    tokens = frozen_block.get("tokens")
    if not isinstance(block_id, str) or not _is_entity_id(block_id):
        raise NarrationDependencyError("frozen narration block ID is invalid")
    if block_id != asset.block_id:
        raise NarrationDependencyError("frozen narration block ID differs from asset")
    if not _positive_safe_integer(revision) or revision != asset.block_revision:
        raise NarrationDependencyError(
            "frozen narration block revision differs from asset"
        )
    if not isinstance(text, str) or not text:
        raise NarrationDependencyError("frozen narration text is required")
    try:
        text_utf8 = text.encode("utf-8")
        text_utf16 = text.encode("utf-16-le")
    except UnicodeEncodeError as error:
        raise NarrationDependencyError(
            "frozen narration text contains an unpaired surrogate"
        ) from error
    text_hash = sha256_bytes(text_utf8)
    if text_hash != asset.text_hash:
        raise NarrationDependencyError("frozen narration text hash differs from asset")
    if not isinstance(tokens, list) or not tokens:
        raise NarrationDependencyError("frozen narration tokens are required")

    audio = projected["audio"]
    locator = audio["locator"]
    if not isinstance(locator, str) or "\r" in locator or "\n" in locator:
        raise NarrationDependencyError("audio locator must be project-relative")
    for name in ("durationSamples", "sampleRate", "channels"):
        if not _positive_safe_integer(audio[name]):
            raise NarrationDependencyError(
                f"audio {name} must be a positive safe integer"
            )
    audio_duration = Fraction(audio["durationSamples"], audio["sampleRate"])

    timing = projected["timing"]
    if timing["precision"] != "word_start_with_derived_end":
        raise NarrationDependencyError(
            "word_timing_required: provider has no word starts"
        )

    token_rows = _validated_tokens(text_utf16, tokens)
    word_marks = [mark for mark in timing["marks"] if mark["kind"] == "word"]
    mark_by_range: dict[tuple[int, int], dict[str, Any]] = {}
    for mark in word_marks:
        start = cast(int, mark["startUtf16"])
        end = cast(int, mark["endUtf16"])
        key = (start, end)
        if key in mark_by_range:
            raise NarrationDependencyError("provider word timing range is duplicated")
        mark_by_range[key] = mark
    if len(mark_by_range) != len(token_rows) or any(
        (token["startOffset"], token["endOffset"]) not in mark_by_range
        for token in token_rows
    ):
        raise NarrationDependencyError(
            "provider word timing does not exactly cover frozen tokens"
        )

    timing_tokens: list[TokenTimingV2] = []
    previous_start = -1
    for index, token in enumerate(token_rows):
        mark = mark_by_range[(token["startOffset"], token["endOffset"])]
        time_value = mark["timeMs"]
        if not _nonnegative_safe_integer(time_value):
            raise NarrationDependencyError(
                "provider word time must be a nonnegative safe integer"
            )
        time_ms = cast(int, time_value)
        if time_ms < previous_start:
            raise NarrationDependencyError("provider word timing is out of order")
        previous_start = time_ms
        seconds = Fraction(time_ms, 1000)
        if seconds >= audio_duration:
            raise NarrationDependencyError(
                "provider word start is at or beyond narration audio duration"
            )
        timing_token: TokenTimingV2 = {
            "tokenId": token["id"],
            "startOffset": token["startOffset"],
            "endOffset": token["endOffset"],
            "quotedText": token["value"],
            "startTime": {
                "numerator": seconds.numerator,
                "denominator": seconds.denominator,
            },
            "endBasis": "next_word_derived"
            if index + 1 < len(token_rows)
            else "unknown",
        }
        timing_tokens.append(timing_token)

    narration_asset_id = str(
        uuid.uuid5(_ASSET_ID_NAMESPACE, _ASSET_ID_PREFIX + asset.asset_id)
    )
    return {
        "blockId": block_id,
        "blockRevision": revision,
        "textHash": text_hash,
        "tokenizationVersion": _TOKENIZATION_VERSION,
        "narrationAssetId": narration_asset_id,
        "audioHash": asset.normalized_audio_hash,
        "timingHash": timing["contentHash"],
        "alignmentVersion": timing["alignmentVersion"],
        "precision": "next_word_derived",
        "audio": {
            "narrationAssetId": narration_asset_id,
            "audioHash": asset.normalized_audio_hash,
            "timingHash": timing["contentHash"],
            "cacheAssetId": asset.asset_id,
            "locator": audio["locator"],
            "durationSamples": audio["durationSamples"],
            "sampleRate": audio["sampleRate"],
            "channels": audio["channels"],
        },
        "tokens": timing_tokens,
    }


def _validated_tokens(
    text_utf16: bytes, tokens: list[NarrationToken]
) -> list[NarrationToken]:
    text_length = len(text_utf16) // 2
    validated: list[NarrationToken] = []
    seen_ids: set[str] = set()
    previous_end = 0
    for token in tokens:
        if not isinstance(token, Mapping):
            raise NarrationDependencyError("frozen narration token is invalid")
        raw_token = cast(Mapping[str, object], token)
        token_id = raw_token.get("id")
        value = raw_token.get("value")
        start = raw_token.get("startOffset")
        end = raw_token.get("endOffset")
        if (
            not isinstance(token_id, str)
            or not _is_entity_id(token_id)
            or token_id in seen_ids
        ):
            raise NarrationDependencyError(
                "frozen narration token ID is invalid or duplicated"
            )
        if not isinstance(value, str) or not value:
            raise NarrationDependencyError("frozen narration token text is required")
        if not _nonnegative_safe_integer(start) or not _positive_safe_integer(end):
            raise NarrationDependencyError(
                "frozen narration token UTF-16 range is invalid"
            )
        start_offset = cast(int, start)
        end_offset = cast(int, end)
        if (
            start_offset < previous_end
            or start_offset >= end_offset
            or end_offset > text_length
        ):
            raise NarrationDependencyError(
                "frozen narration token UTF-16 range is invalid"
            )
        try:
            quoted = text_utf16[start_offset * 2 : end_offset * 2].decode("utf-16-le")
        except UnicodeDecodeError as error:
            raise NarrationDependencyError(
                "frozen narration token range splits a UTF-16 surrogate pair"
            ) from error
        if quoted != value:
            raise NarrationDependencyError(
                "frozen narration token text differs from UTF-16 slice"
            )
        seen_ids.add(token_id)
        previous_end = end_offset
        validated.append(
            {
                "id": token_id,
                "value": value,
                "startOffset": start_offset,
                "endOffset": end_offset,
            }
        )
    return validated


def _nonnegative_safe_integer(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= _MAX_SAFE_INTEGER
    )


def _positive_safe_integer(value: object) -> bool:
    return _nonnegative_safe_integer(value) and cast(int, value) > 0


def _is_entity_id(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return False
    return str(parsed) == value.lower()
