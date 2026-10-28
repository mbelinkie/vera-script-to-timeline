"""Exact, target-only Resolve adapter for paired presenter framing profiles.

This module checks the profile pin and native readback. It does not qualify
visible crop semantics, Resolve units, source-time mapping, or Inspector UI.
"""

from __future__ import annotations

import copy
import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from .narration.models import sha256_bytes

FramingKey = Literal["wide", "tight"]
_PROFILE_SCHEMA = "presenter-framing-profile-snapshot/v1"
_PROFILE_KEYS = {
    "schemaVersion",
    "id",
    "version",
    "profileHash",
    "context",
    "invariants",
    "wide",
    "tight",
}
_PROFILE_CONTENT_KEYS = {"schemaVersion", "context", "invariants", "wide", "tight"}
_TRANSFORM_KEYS = {"ZoomX", "ZoomY", "Pan", "Tilt"}
_INVARIANTS: dict[str, bool | int] = {
    "TransformEnabled": True,
    "DynamicZoomEnabled": False,
    "RotationAngle": 0,
    "AnchorPointX": 0,
    "AnchorPointY": 0,
    "FlipX": False,
    "FlipY": False,
}
_COLORS = {"wide": "Blue", "tight": "Orange"}
_MAX_SAFE_INTEGER = 9_007_199_254_740_991
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z",
    re.IGNORECASE,
)
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_PLACEHOLDERS = {"unknown", "unspecified", "guessed", "n/a"}


class PresenterFramingError(ValueError):
    """A framing target, profile pin, or native readback is not trustworthy."""


@dataclass(frozen=True)
class ValidatedSourceTimeInterval:
    """Caller-validated half-open source-frame interval [start_frame, end_frame)."""

    start_frame: int
    end_frame: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.start_frame, bool)
            or not isinstance(self.start_frame, int)
            or self.start_frame < 0
            or self.start_frame > _MAX_SAFE_INTEGER
            or isinstance(self.end_frame, bool)
            or not isinstance(self.end_frame, int)
            or self.end_frame <= self.start_frame
            or self.end_frame > _MAX_SAFE_INTEGER
        ):
            raise PresenterFramingError("source-time interval is invalid")


@dataclass(frozen=True)
class PresenterPictureTarget:
    """One explicitly selected generated presenter picture item."""

    event_id: str
    key: FramingKey
    source_interval: ValidatedSourceTimeInterval
    timeline_item_uid: str
    media_id: str
    item: Any


@dataclass(frozen=True)
class PresenterFramingIntent:
    """Pure authored target metadata for a possible Free manual handoff."""

    event_id: str
    key: FramingKey
    name: str


@dataclass(frozen=True)
class FramingResult:
    status: Literal["applied_verified", "pending", "blocked"]
    message: str
    event_ids: tuple[str, ...] = ()
    color_limitations: tuple[str, ...] = ()
    observed_properties: dict[str, dict[str, bool | int | float]] | None = None
    profile_pin: dict[str, Any] | None = None


@dataclass(frozen=True)
class CalibrationResult:
    """Sample readback output; it does not qualify visible transform behavior."""

    status: Literal["sample_readback_complete", "pending", "blocked"]
    message: str
    context: dict[str, Any] | None = None
    observed_transforms: dict[str, dict[str, int | float]] | None = None
    color_limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProfileRevisionCandidate:
    """A new profile identity body; the prior snapshot remains byte-pinned."""

    prior_snapshot: dict[str, Any]
    prior_content_json: bytes
    prior_pin: dict[str, Any]
    calibration: CalibrationResult
    content: dict[str, Any]


@dataclass(frozen=True)
class ProfileRevision:
    prior_snapshot: dict[str, Any]
    prior_content_json: bytes
    snapshot: dict[str, Any]
    content_json: bytes
    pin: dict[str, Any]


@dataclass(frozen=True)
class _CycleResult:
    status: Literal["complete", "pending", "blocked"]
    message: str
    event_ids: tuple[str, ...] = ()
    color_limitations: tuple[str, ...] = ()
    observed_properties: dict[str, dict[str, bool | int | float]] | None = None


def _canonical_bytes(value: bytes | str, label: str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        try:
            return value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise PresenterFramingError(f"{label} is not valid UTF-8 text") from error
    raise PresenterFramingError(f"{label} must be exact canonical JSON bytes or text")


def _finite_number(value: int | float) -> bool:
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _json_equal(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is bool and type(right) is bool and left is right
    if isinstance(left, (int, float)) or isinstance(right, (int, float)):
        return (
            isinstance(left, (int, float))
            and not isinstance(left, bool)
            and isinstance(right, (int, float))
            and not isinstance(right, bool)
            and _finite_number(left)
            and _finite_number(right)
            and left == right
        )
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        return (
            isinstance(left, Mapping)
            and isinstance(right, Mapping)
            and set(left) == set(right)
            and all(_json_equal(left[key], right[key]) for key in left)
        )
    if isinstance(left, list) or isinstance(right, list):
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and len(left) == len(right)
            and all(_json_equal(a, b) for a, b in zip(left, right, strict=True))
        )
    return type(left) is type(right) and left == right


def _strict_json_object(payload: bytes, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise PresenterFramingError(f"{label} has duplicate JSON keys")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise PresenterFramingError(f"{label} has a non-finite value: {value}")

    def finite_float(value: str) -> float:
        result = float(value)
        if not math.isfinite(result):
            raise PresenterFramingError(f"{label} has a non-finite number")
        return result

    try:
        result = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
            parse_float=finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PresenterFramingError(f"{label} is not UTF-8 JSON") from error
    if not isinstance(result, dict):
        raise PresenterFramingError(f"{label} must be a JSON object")
    return result


def _object(value: object, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise PresenterFramingError(f"{label} has missing or unexpected fields")
    return value


def _positive_integer(value: object, label: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not _finite_number(value)
        or value != int(value)
        or value <= 0
        or value > _MAX_SAFE_INTEGER
    ):
        raise PresenterFramingError(f"{label} must be a positive integer")


def _context_string(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PresenterFramingError(f"{label} must be a nonblank string")
    if value.strip().casefold() in _PLACEHOLDERS:
        raise PresenterFramingError(f"{label} cannot be a placeholder")


def _validate_rational(value: object, label: str) -> None:
    rational = _object(value, {"numerator", "denominator"}, label)
    _positive_integer(rational["numerator"], f"{label} numerator")
    _positive_integer(rational["denominator"], f"{label} denominator")


def _validate_context(value: object) -> Mapping[str, Any]:
    context = _object(
        value,
        {"sourceRaster", "timelineRaster", "resolve", "adapter"},
        "profile context",
    )
    source = _object(
        context["sourceRaster"],
        {
            "width",
            "height",
            "pixelAspect",
            "orientation",
            "scalingContext",
            "frameRate",
        },
        "source raster context",
    )
    timeline = _object(
        context["timelineRaster"],
        {"width", "height", "pixelAspect", "frameRate"},
        "timeline raster context",
    )
    for raster_name, raster in (("source", source), ("timeline", timeline)):
        _positive_integer(raster["width"], f"{raster_name} raster width")
        _positive_integer(raster["height"], f"{raster_name} raster height")
        _validate_rational(raster["pixelAspect"], f"{raster_name} pixel aspect")
        _validate_rational(raster["frameRate"], f"{raster_name} frame rate")
    for field in ("orientation", "scalingContext"):
        _context_string(source[field], f"source raster {field}")
    resolve = _object(
        context["resolve"],
        {"product", "version", "build", "apiContext"},
        "Resolve context",
    )
    adapter = _object(
        context["adapter"], {"release", "sourceIdentity"}, "adapter context"
    )
    for label, fields in (
        ("Resolve context", resolve.items()),
        ("adapter context", adapter.items()),
    ):
        for field_name, field_value in fields:
            _context_string(field_value, f"{label} {field_name}")
    return context


def _validate_transform(value: object, label: str) -> Mapping[str, int | float]:
    transform = _object(value, _TRANSFORM_KEYS, label)
    numbers: dict[str, int | float] = {}
    for name, number in transform.items():
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not _finite_number(number)
        ):
            raise PresenterFramingError(f"{label} {name} must be finite numeric data")
        numbers[name] = number
    if numbers["ZoomX"] <= 0 or numbers["ZoomX"] != numbers["ZoomY"]:
        raise PresenterFramingError(f"{label} zoom axes must be positive and equal")
    return numbers


def validate_profile_snapshot(
    snapshot: Mapping[str, Any],
    *,
    canonical_content_json: bytes | str,
    expected_pin: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify TS-canonical profile bytes, snapshot semantics, and settings pin."""
    canonical_bytes = _canonical_bytes(
        canonical_content_json, "canonical profile content"
    )
    if set(snapshot) != _PROFILE_KEYS:
        raise PresenterFramingError("profile snapshot has missing or unexpected fields")
    if snapshot["schemaVersion"] != _PROFILE_SCHEMA:
        raise PresenterFramingError("unsupported presenter framing profile schema")
    profile_id = snapshot["id"]
    if not isinstance(profile_id, str) or _UUID.fullmatch(profile_id) is None:
        raise PresenterFramingError("profile id is not a UUID")
    _positive_integer(snapshot["version"], "profile version")
    profile_hash = snapshot["profileHash"]
    if not isinstance(profile_hash, str) or _HASH.fullmatch(profile_hash) is None:
        raise PresenterFramingError("profile hash is malformed")
    context = _validate_context(snapshot["context"])
    invariants = _object(snapshot["invariants"], set(_INVARIANTS), "profile invariants")
    if not all(
        _json_equal(invariants[key], expected) for key, expected in _INVARIANTS.items()
    ):
        raise PresenterFramingError("profile neutral invariants differ")
    wide = _validate_transform(snapshot["wide"], "wide transform")
    tight = _validate_transform(snapshot["tight"], "tight transform")

    pin = _object(expected_pin, {"id", "version", "profileHash"}, "profile reference")
    _positive_integer(pin["version"], "profile reference version")
    if (
        pin["id"] != profile_id
        or not _json_equal(pin["version"], snapshot["version"])
        or pin["profileHash"] != profile_hash
    ):
        raise PresenterFramingError("profile snapshot differs from its settings pin")

    content = _strict_json_object(canonical_bytes, "canonical profile content")
    if set(content) != _PROFILE_CONTENT_KEYS:
        raise PresenterFramingError("canonical profile content fields differ")
    expected_content = {
        "schemaVersion": _PROFILE_SCHEMA,
        "context": context,
        "invariants": invariants,
        "wide": wide,
        "tight": tight,
    }
    if not _json_equal(content, expected_content):
        raise PresenterFramingError("canonical profile content differs from snapshot")
    if sha256_bytes(canonical_bytes) != profile_hash:
        raise PresenterFramingError("profile content hash differs")
    return copy.deepcopy(dict(snapshot))


def prepare_profile_revision(
    prior_snapshot: Mapping[str, Any],
    *,
    prior_content_json: bytes | str,
    prior_pin: Mapping[str, Any],
    calibration: CalibrationResult,
) -> ProfileRevisionCandidate:
    """Prepare a same-id, next-version profile from a completed sample readback."""
    prior_bytes = _canonical_bytes(prior_content_json, "prior profile content")
    prior = validate_profile_snapshot(
        prior_snapshot,
        canonical_content_json=prior_bytes,
        expected_pin=prior_pin,
    )
    if (
        calibration.status != "sample_readback_complete"
        or calibration.context is None
        or calibration.observed_transforms is None
        or set(calibration.observed_transforms) != {"wide", "tight"}
    ):
        raise PresenterFramingError("both framing samples need exact reopened readback")
    content = {
        "schemaVersion": _PROFILE_SCHEMA,
        "id": prior["id"],
        "version": prior["version"] + 1,
        "context": copy.deepcopy(calibration.context),
        "invariants": copy.deepcopy(prior["invariants"]),
        "wide": copy.deepcopy(
            dict(
                _validate_transform(
                    calibration.observed_transforms["wide"], "wide readback"
                )
            )
        ),
        "tight": copy.deepcopy(
            dict(
                _validate_transform(
                    calibration.observed_transforms["tight"], "tight readback"
                )
            )
        ),
    }
    _validate_context(content["context"])
    prepared_calibration = CalibrationResult(
        calibration.status,
        calibration.message,
        copy.deepcopy(calibration.context),
        copy.deepcopy(calibration.observed_transforms),
        tuple(calibration.color_limitations),
    )
    return ProfileRevisionCandidate(
        copy.deepcopy(prior),
        prior_bytes,
        copy.deepcopy(dict(prior_pin)),
        prepared_calibration,
        content,
    )


def finalize_profile_revision(
    candidate: ProfileRevisionCandidate,
    *,
    canonical_content_json: bytes | str,
) -> ProfileRevision:
    """Pin TS-canonical bytes and preserve the old profile without rewriting it."""
    prior_bytes = _canonical_bytes(
        candidate.prior_content_json, "prior profile content"
    )
    canonical_bytes = _canonical_bytes(
        canonical_content_json, "canonical profile content"
    )
    prior = validate_profile_snapshot(
        candidate.prior_snapshot,
        canonical_content_json=prior_bytes,
        expected_pin=candidate.prior_pin,
    )
    content = candidate.content
    if set(content) != _PROFILE_KEYS - {"profileHash"}:
        raise PresenterFramingError(
            "new profile revision has missing or unexpected fields"
        )
    if content["schemaVersion"] != _PROFILE_SCHEMA or content["id"] != prior["id"]:
        raise PresenterFramingError("new profile revision must increment the same id")
    _positive_integer(content["version"], "new profile version")
    if not _json_equal(content["version"], prior["version"] + 1):
        raise PresenterFramingError("new profile revision must increment the same id")
    _validate_context(content["context"])
    invariants = _object(content["invariants"], set(_INVARIANTS), "profile invariants")
    if not all(
        _json_equal(invariants[key], expected) for key, expected in _INVARIANTS.items()
    ):
        raise PresenterFramingError("new profile neutral invariants differ")
    wide = _validate_transform(content["wide"], "wide transform")
    tight = _validate_transform(content["tight"], "tight transform")
    calibration = candidate.calibration
    if (
        calibration.status != "sample_readback_complete"
        or calibration.context is None
        or calibration.observed_transforms is None
        or not _json_equal(content["context"], calibration.context)
        or not _json_equal(wide, calibration.observed_transforms.get("wide"))
        or not _json_equal(tight, calibration.observed_transforms.get("tight"))
    ):
        raise PresenterFramingError(
            "new profile differs from calibrated sample readback"
        )
    parsed_content = _strict_json_object(canonical_bytes, "canonical profile content")
    if set(parsed_content) != _PROFILE_CONTENT_KEYS:
        raise PresenterFramingError("canonical profile content fields differ")
    expected_content = {
        "schemaVersion": _PROFILE_SCHEMA,
        "context": content["context"],
        "invariants": invariants,
        "wide": wide,
        "tight": tight,
    }
    if not _json_equal(parsed_content, expected_content):
        raise PresenterFramingError("canonical profile content differs from revision")
    profile_hash = sha256_bytes(canonical_bytes)
    snapshot = {
        **copy.deepcopy(content),
        "profileHash": profile_hash,
    }
    pin = {
        "id": snapshot["id"],
        "version": snapshot["version"],
        "profileHash": profile_hash,
    }
    verified = validate_profile_snapshot(
        snapshot,
        canonical_content_json=canonical_bytes,
        expected_pin=pin,
    )
    return ProfileRevision(
        prior,
        prior_bytes,
        verified,
        canonical_bytes,
        copy.deepcopy(pin),
    )


def _validate_targets(
    targets: Sequence[PresenterPictureTarget],
) -> tuple[PresenterPictureTarget, ...]:
    if (
        not isinstance(targets, Sequence)
        or isinstance(targets, (str, bytes))
        or not targets
    ):
        raise PresenterFramingError("explicit presenter targets are required")
    result = tuple(targets)
    seen_ids: set[str] = set()
    seen_items: set[int] = set()
    for target in result:
        if not isinstance(target, PresenterPictureTarget):
            raise PresenterFramingError(
                "target is not an explicit presenter picture item"
            )
        if target.key not in {"wide", "tight"}:
            raise PresenterFramingError("target framing key is invalid")
        if (
            not target.event_id
            or target.event_id != target.event_id.strip()
            or any(character.isspace() for character in target.event_id)
        ):
            raise PresenterFramingError("target event id is invalid")
        if (
            not isinstance(target.timeline_item_uid, str)
            or not target.timeline_item_uid
            or not isinstance(target.media_id, str)
            or not target.media_id
        ):
            raise PresenterFramingError("target item and media ids are required")
        if not isinstance(target.source_interval, ValidatedSourceTimeInterval):
            raise PresenterFramingError("target source-time interval is not validated")
        if target.event_id in seen_ids or id(target.item) in seen_items:
            raise PresenterFramingError("presenter target is duplicated")
        seen_ids.add(target.event_id)
        seen_items.add(id(target.item))
    return result


def _target_properties(
    transform: Mapping[str, int | float],
) -> dict[str, bool | int | float]:
    return {**_INVARIANTS, **dict(transform)}


def _property_matches(actual: object, expected: bool | int | float) -> bool:
    if isinstance(expected, bool):
        return type(actual) is bool and actual is expected
    return (
        isinstance(actual, (int, float))
        and not isinstance(actual, bool)
        and _finite_number(actual)
        and actual == expected
    )


class PresenterFramingAdapter:
    """Mutate only labeled, explicitly passed presenter items with exact readback."""

    def __init__(
        self,
        *,
        current_target_check: Callable[[], None],
        context_reader: Callable[[], Mapping[str, Any]],
        edition: Literal["studio", "free", "unknown"],
    ) -> None:
        if not callable(current_target_check) or not callable(context_reader):
            raise PresenterFramingError("live target and context checks are required")
        if edition not in {"studio", "free", "unknown"}:
            raise PresenterFramingError("Resolve edition is unknown")
        self._current_target_check = current_target_check
        self._context_reader = context_reader
        self._edition = edition

    def _require_context(self, expected: Mapping[str, Any]) -> None:
        live = _validate_context(self._context_reader())
        if dict(live) != dict(expected):
            raise PresenterFramingError("live Resolve context differs from profile")

    @staticmethod
    def _require_item_identity(item: Any, target: PresenterPictureTarget) -> None:
        item_uid_method = getattr(item, "GetUniqueId", None)
        item_type_method = getattr(item, "GetType", None)
        media_pool_method = getattr(item, "GetMediaPoolItem", None)
        get_name = getattr(item, "GetName", None)
        set_name = getattr(item, "SetName", None)
        if (
            not callable(item_uid_method)
            or not callable(item_type_method)
            or not callable(media_pool_method)
            or not callable(get_name)
            or not callable(set_name)
        ):
            raise PresenterFramingError("presenter item identity is unavailable")
        media_item = media_pool_method()
        media_id_method = getattr(media_item, "GetMediaId", None)
        if (
            item_uid_method() != target.timeline_item_uid
            or item_type_method() != "video"
            or not callable(media_id_method)
            or media_id_method() != target.media_id
        ):
            raise PresenterFramingError("presenter item or media identity differs")

        start_method = getattr(item, "GetSourceStartFrame", None)
        end_method = getattr(item, "GetSourceEndFrame", None)
        if not callable(start_method) or not callable(end_method):
            raise PresenterFramingError(
                "presenter target source interval is unavailable"
            )
        actual_start = start_method()
        actual_end = end_method()
        interval = target.source_interval
        # Resolve's public item end is inclusive; the caller supplies [start, end).
        if (
            isinstance(actual_start, bool)
            or not isinstance(actual_start, int)
            or isinstance(actual_end, bool)
            or not isinstance(actual_end, int)
            or actual_start != interval.start_frame
            or actual_end != interval.end_frame - 1
        ):
            raise PresenterFramingError("presenter target source interval differs")

    @staticmethod
    def _require_label(item: Any, target: PresenterPictureTarget) -> None:
        getter = getattr(item, "GetName", None)
        expected = f"OC {target.key.upper()} {target.event_id}"
        if not callable(getter) or getter() != expected:
            raise PresenterFramingError(f"authoritative item name differs: {expected}")

    @staticmethod
    def _color_is_limited(item: Any, target: PresenterPictureTarget) -> bool:
        getter = getattr(item, "GetClipColor", None)
        if not callable(getter):
            return True
        try:
            return bool(getter() != _COLORS[target.key])
        except Exception:
            return True

    @staticmethod
    def _capture_sample_transform(item: Any, label: str) -> dict[str, int | float]:
        getter = getattr(item, "GetProperties", None)
        if not callable(getter):
            raise PresenterFramingError("calibration sample properties are unavailable")
        properties = getter()
        if not isinstance(properties, Mapping) or any(
            key not in properties or not _property_matches(properties[key], value)
            for key, value in _INVARIANTS.items()
        ):
            raise PresenterFramingError(
                f"{label} sample neutral invariants differ before calibration"
            )
        if any(key not in properties for key in _TRANSFORM_KEYS):
            raise PresenterFramingError(f"{label} sample raw transform is incomplete")
        return dict(
            _validate_transform(
                {key: properties[key] for key in _TRANSFORM_KEYS},
                f"{label} sample transform",
            )
        )

    @staticmethod
    def _require_properties(
        item: Any, expected: Mapping[str, bool | int | float]
    ) -> dict[str, bool | int | float]:
        getter = getattr(item, "GetProperties", None)
        if not callable(getter):
            raise PresenterFramingError("Resolve property readback is unavailable")
        actual = getter()
        if not isinstance(actual, Mapping) or any(
            key not in actual or not _property_matches(actual[key], value)
            for key, value in expected.items()
        ):
            raise PresenterFramingError("Resolve property readback differs")
        return {key: actual[key] for key in expected}

    def _write_reopen_verify(
        self,
        *,
        targets: tuple[PresenterPictureTarget, ...],
        expected_context: Mapping[str, Any],
        properties_by_id: Mapping[str, Mapping[str, bool | int | float]],
        save_close_reopen: Callable[[], None],
        lookup_reopened: Callable[[tuple[str, ...]], Mapping[str, Any]],
    ) -> _CycleResult:
        event_ids = tuple(target.event_id for target in targets)
        try:
            if not callable(save_close_reopen) or not callable(lookup_reopened):
                raise PresenterFramingError(
                    "save/reopen and lookup callbacks are required"
                )
            self._current_target_check()
            self._require_context(expected_context)
            for target in targets:
                self._require_item_identity(target.item, target)
        except Exception as error:
            return _CycleResult("blocked", f"Preflight blocked: {error}", event_ids)

        mutation_started = False
        color_limitations: list[str] = []
        try:
            for target in targets:
                self._current_target_check()
                self._require_item_identity(target.item, target)
                expected_name = f"OC {target.key.upper()} {target.event_id}"
                name_setter = target.item.SetName
                mutation_started = True
                if name_setter(expected_name) is not True:
                    raise PresenterFramingError("Resolve rejected presenter item name")
                self._require_label(target.item, target)

                color_setter = getattr(target.item, "SetClipColor", None)
                if callable(color_setter):
                    self._current_target_check()
                    mutation_started = True
                    try:
                        if color_setter(_COLORS[target.key]) is not True:
                            color_limitations.append(
                                f"{target.event_id}: {target.key} clip color "
                                "was not retained"
                            )
                    except Exception:
                        color_limitations.append(
                            f"{target.event_id}: {target.key} clip color "
                            "was not retained"
                        )
                if self._color_is_limited(target.item, target) and not any(
                    message.startswith(f"{target.event_id}:")
                    for message in color_limitations
                ):
                    color_limitations.append(
                        f"{target.event_id}: {target.key} clip color was not retained"
                    )

                self._current_target_check()
                item_properties = properties_by_id[target.event_id]
                setter = getattr(target.item, "SetProperties", None)
                if not callable(setter):
                    raise PresenterFramingError(
                        "Resolve property setter is unavailable"
                    )
                mutation_started = True
                if setter(dict(item_properties)) is not True:
                    raise PresenterFramingError("Resolve rejected presenter properties")
                self._require_properties(target.item, item_properties)

            self._current_target_check()
            mutation_started = True
            save_close_reopen()
            self._current_target_check()
            reopened = lookup_reopened(event_ids)
            if not isinstance(reopened, Mapping) or set(reopened) != set(event_ids):
                raise PresenterFramingError("reopened presenter lookup differs")
            self._require_context(expected_context)
            observed: dict[str, dict[str, bool | int | float]] = {}
            for target in targets:
                item = reopened[target.event_id]
                self._require_item_identity(item, target)
                self._require_label(item, target)
                if self._color_is_limited(item, target) and not any(
                    message.startswith(f"{target.event_id}:")
                    for message in color_limitations
                ):
                    color_limitations.append(
                        f"{target.event_id}: {target.key} clip color was not retained"
                    )
                observed[target.event_id] = self._require_properties(
                    item, properties_by_id[target.event_id]
                )
            return _CycleResult(
                "complete",
                "Exact presenter properties survived save, reopen, and lookup.",
                event_ids,
                tuple(color_limitations),
                observed,
            )
        except Exception as error:
            status: Literal["pending", "blocked"] = (
                "pending" if mutation_started else "blocked"
            )
            return _CycleResult(
                status, f"Presenter framing {status}: {error}", event_ids
            )

    def apply(
        self,
        *,
        profile: Mapping[str, Any],
        canonical_content_json: bytes | str,
        expected_pin: Mapping[str, Any],
        targets: Sequence[PresenterPictureTarget],
        save_close_reopen: Callable[[], None],
        lookup_reopened: Callable[[tuple[str, ...]], Mapping[str, Any]],
    ) -> FramingResult:
        """Apply the pinned pair to explicit labeled items; never alter placement."""
        profile_pin: dict[str, Any] | None = None
        try:
            if self._edition != "studio":
                raise PresenterFramingError(
                    "automatic framing requires a Studio target"
                )
            checked_profile = validate_profile_snapshot(
                profile,
                canonical_content_json=canonical_content_json,
                expected_pin=expected_pin,
            )
            profile_pin = copy.deepcopy(dict(expected_pin))
            checked_targets = _validate_targets(targets)
            properties = {
                target.event_id: _target_properties(checked_profile[target.key])
                for target in checked_targets
            }
        except Exception as error:
            return FramingResult("blocked", f"Presenter framing blocked: {error}")

        cycle = self._write_reopen_verify(
            targets=checked_targets,
            expected_context=checked_profile["context"],
            properties_by_id=properties,
            save_close_reopen=save_close_reopen,
            lookup_reopened=lookup_reopened,
        )
        status: Literal["applied_verified", "pending", "blocked"] = (
            "applied_verified" if cycle.status == "complete" else cycle.status
        )
        return FramingResult(
            status,
            cycle.message,
            cycle.event_ids,
            cycle.color_limitations,
            cycle.observed_properties,
            profile_pin=profile_pin,
        )

    def calibrate_disposable_samples(
        self,
        *,
        is_disposable_timeline: bool,
        samples: Mapping[str, PresenterPictureTarget],
        save_close_reopen: Callable[[], None],
        lookup_reopened: Callable[[tuple[str, ...]], Mapping[str, Any]],
        transforms: Mapping[str, Mapping[str, int | float]] | None = None,
    ) -> CalibrationResult:
        """Capture authored tuples, or set explicit synthetic-check values."""
        try:
            if self._edition != "studio" or is_disposable_timeline is not True:
                raise PresenterFramingError(
                    "calibration requires disposable Studio samples"
                )
            if set(samples) != {"wide", "tight"}:
                raise PresenterFramingError("both wide and tight samples are required")
            targets = _validate_targets((samples["wide"], samples["tight"]))
            if (
                targets[0].key != "wide"
                or targets[1].key != "tight"
                or targets[0].item is targets[1].item
                or targets[0].source_interval != targets[1].source_interval
                or targets[0].media_id != targets[1].media_id
            ):
                raise PresenterFramingError(
                    "wide and tight samples must share one source and exact interval"
                )
            context = copy.deepcopy(dict(_validate_context(self._context_reader())))
            if transforms is None:
                checked_transforms: dict[str, Mapping[str, int | float]] = {}
                for target in targets:
                    self._current_target_check()
                    self._require_context(context)
                    self._require_item_identity(target.item, target)
                    checked_transforms[target.key] = self._capture_sample_transform(
                        target.item, target.key
                    )
            else:
                if set(transforms) != {"wide", "tight"}:
                    raise PresenterFramingError(
                        "both wide and tight transforms are required"
                    )
                checked_transforms = {
                    key: _validate_transform(transforms[key], f"{key} calibration")
                    for key in ("wide", "tight")
                }
            properties = {
                target.event_id: _target_properties(checked_transforms[target.key])
                for target in targets
            }
        except Exception as error:
            return CalibrationResult("blocked", f"Calibration blocked: {error}")

        cycle = self._write_reopen_verify(
            targets=targets,
            expected_context=context,
            properties_by_id=properties,
            save_close_reopen=save_close_reopen,
            lookup_reopened=lookup_reopened,
        )
        if cycle.status != "complete":
            return CalibrationResult(
                cycle.status,
                cycle.message,
                color_limitations=cycle.color_limitations,
            )
        observed = cycle.observed_properties or {}
        return CalibrationResult(
            "sample_readback_complete",
            "Both raw tuples survived exact sample readback and save/reopen; "
            "visual behavior remains unqualified.",
            context,
            {
                key: {
                    property_name: observed[target.event_id][property_name]
                    for property_name in _TRANSFORM_KEYS
                }
                for key, target in (("wide", targets[0]), ("tight", targets[1]))
            },
            cycle.color_limitations,
        )


def free_manual_handoff(
    *,
    profile: Mapping[str, Any],
    canonical_content_json: bytes | str,
    expected_pin: Mapping[str, Any],
    observed_context: Mapping[str, Any],
    targets: Sequence[PresenterFramingIntent],
) -> FramingResult:
    """Keep Free handoff blocked until a usable Inspector map is qualified.

    This path is pure: Resolve Free does not expose the scripting API used by
    the automatic adapter, and no Inspector conversion has been qualified.
    """
    try:
        checked_profile = validate_profile_snapshot(
            profile,
            canonical_content_json=canonical_content_json,
            expected_pin=expected_pin,
        )
        if not _json_equal(
            _validate_context(observed_context), checked_profile["context"]
        ):
            raise PresenterFramingError("Free handoff context differs from profile")
        if not isinstance(targets, Sequence) or not targets:
            raise PresenterFramingError("authored Free framing targets are required")
        event_ids: list[str] = []
        for target in targets:
            if (
                not isinstance(target, PresenterFramingIntent)
                or target.key not in {"wide", "tight"}
                or not target.event_id
                or any(character.isspace() for character in target.event_id)
                or target.name != f"OC {target.key.upper()} {target.event_id}"
            ):
                raise PresenterFramingError("Free framing target metadata differs")
            event_ids.append(target.event_id)
        if len(event_ids) != len(set(event_ids)):
            raise PresenterFramingError("Free framing event identity is repeated")
    except Exception as error:
        return FramingResult("blocked", f"Free presenter handoff blocked: {error}")
    return FramingResult(
        "blocked",
        "Free handoff remains blocked until a separately qualified Inspector "
        "mapping supplies controls and values for this exact context and raw "
        "ZoomX/ZoomY/Pan/Tilt properties.",
        tuple(event_ids),
        profile_pin=copy.deepcopy(dict(expected_pin)),
    )
