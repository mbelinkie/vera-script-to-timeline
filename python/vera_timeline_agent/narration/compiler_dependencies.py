"""Project-boundary projection of immutable narration cache records.

This module deliberately reads only already-verified values.  It does not open
or mutate a cache, and it does not promote the complete cache record into the
cross-language compiler contract.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any, cast

from vera_timeline_agent.narration.models import NarrationAudioAsset, sha256_bytes

_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ASSET_ID = re.compile(r"[0-9a-f]{64}\Z")
_PRECISIONS = {"word_start_with_derived_end", "sentence_start", "none"}
_MARK_KINDS = {"word", "sentence"}


class NarrationDependencyError(ValueError):
    """A cached narration record cannot honestly cross the compiler boundary."""


def narration_dependency_from_asset(
    asset: NarrationAudioAsset, provider_timing_json: bytes
) -> dict[str, Any]:
    """Map a verified cache asset and its exact timing record to contract JSON.

    ``provider_timing_json`` is passed as bytes so its content hash can be
    checked against the immutable asset record before any compiler sees it.
    """

    _validate_asset(asset)
    timing = _parse_timing(asset, provider_timing_json)
    dependency: dict[str, Any] = {
        "blockId": asset.block_id,
        "blockRevision": asset.block_revision,
        "assetId": asset.asset_id,
        "status": asset.status,
        "textHash": asset.text_hash,
        "audioHash": asset.normalized_audio_hash,
        "audio": {
            "locator": asset.locators["audio"],
            "durationSamples": asset.duration_samples,
            "sampleRate": asset.sample_rate,
            "channels": asset.channels,
        },
        "timing": timing,
    }
    if asset.status == "failed":
        dependency["failureReason"] = cast(str, asset.failure_reason)
    return dependency


def _validate_asset(asset: NarrationAudioAsset) -> None:
    if asset.record_version != "narration-audio-asset/v1":
        raise NarrationDependencyError("unsupported narration asset record version")
    if _ASSET_ID.fullmatch(asset.asset_id) is None:
        raise NarrationDependencyError(
            "asset ID must be 64 lowercase hexadecimal characters"
        )
    if asset.block_revision < 1:
        raise NarrationDependencyError("block revision must be positive")
    if asset.status not in {"ready", "failed"}:
        raise NarrationDependencyError("asset status must be ready or failed")
    for name, value in (
        ("text hash", asset.text_hash),
        ("audio hash", asset.normalized_audio_hash),
    ):
        if not isinstance(value, str) or _HASH.fullmatch(value) is None:
            raise NarrationDependencyError(f"{name} must be a sha256 hash")
    if asset.status == "ready" and (
        not isinstance(asset.raw_timing_hash, str)
        or _HASH.fullmatch(asset.raw_timing_hash) is None
    ):
        raise NarrationDependencyError("ready asset timing hash must be a sha256 hash")
    if asset.duration_samples < 1 or asset.sample_rate < 1 or asset.channels < 1:
        raise NarrationDependencyError(
            "audio duration, sample rate, and channels must be positive"
        )
    locator = asset.locators.get("audio")
    if not isinstance(locator, str) or not _is_project_relative(locator):
        raise NarrationDependencyError("audio locator must be project-relative")
    if asset.status == "failed":
        if not isinstance(asset.failure_reason, str) or not asset.failure_reason:
            raise NarrationDependencyError("failed asset requires a failure reason")
    elif asset.failure_reason is not None:
        raise NarrationDependencyError("ready asset may not carry a failure reason")


def _parse_timing(
    asset: NarrationAudioAsset, provider_timing_json: bytes
) -> dict[str, Any]:
    content_hash = sha256_bytes(provider_timing_json)
    if asset.status == "ready" and content_hash != asset.raw_timing_hash:
        raise NarrationDependencyError(
            "provider timing content hash differs from asset"
        )
    try:
        value = json.loads(provider_timing_json)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise NarrationDependencyError("provider timing JSON is unreadable") from error
    if not isinstance(value, Mapping):
        raise NarrationDependencyError("provider timing JSON must be an object")

    record_version = value.get("recordVersion")
    precision = value.get("precision")
    marks = value.get("marks")
    if not isinstance(record_version, str) or not record_version:
        raise NarrationDependencyError("provider timing record version is required")
    if not isinstance(precision, str) or precision not in _PRECISIONS:
        raise NarrationDependencyError("provider timing precision is unsupported")
    if precision != asset.timing_precision:
        raise NarrationDependencyError("provider timing precision differs from asset")
    if not isinstance(marks, list):
        raise NarrationDependencyError("provider timing marks must be an array")
    if asset.status == "failed" and (precision != "none" or marks):
        raise NarrationDependencyError(
            "failed asset timing must use none precision with no marks"
        )

    return {
        "recordVersion": record_version,
        "contentHash": content_hash,
        # The cache record is already the source-alignment artifact; do not
        # pretend a new transformation occurred at this boundary.
        "alignmentVersion": record_version,
        "precision": precision,
        "marks": [_map_mark(mark) for mark in marks],
    }


def _map_mark(mark: object) -> dict[str, Any]:
    if not isinstance(mark, Mapping):
        raise NarrationDependencyError("provider timing mark must be an object")
    kind = mark.get("kind")
    time_ms = mark.get("time_ms")
    start_utf16 = mark.get("start_utf16")
    end_utf16 = mark.get("end_utf16")
    value = mark.get("value")
    if kind not in _MARK_KINDS:
        raise NarrationDependencyError("provider timing mark kind is unsupported")
    if not _nonnegative_int(time_ms):
        raise NarrationDependencyError("provider timing mark time must be nonnegative")
    if not _nonnegative_int(start_utf16) or not _positive_int(end_utf16):
        raise NarrationDependencyError("provider timing mark UTF-16 range is invalid")
    if cast(int, start_utf16) >= cast(int, end_utf16):
        raise NarrationDependencyError("provider timing mark UTF-16 range is empty")
    if not isinstance(value, str) or not value:
        raise NarrationDependencyError("provider timing mark value is required")
    return {
        "kind": kind,
        "timeMs": time_ms,
        "startUtf16": start_utf16,
        "endUtf16": end_utf16,
        "value": value,
    }


def _nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _positive_int(value: object) -> bool:
    return _nonnegative_int(value) and cast(int, value) > 0


def _is_project_relative(locator: str) -> bool:
    if not locator or "\\" in locator or locator.startswith("/"):
        return False
    if re.match(r"^[A-Za-z]:", locator) is not None:
        return False
    return all(part not in {"", ".", ".."} for part in locator.split("/"))
