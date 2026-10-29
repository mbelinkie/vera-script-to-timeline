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


class NativeSaveReopen:
    """Save, close, and reopen one exact native Resolve project and timeline."""

    def __init__(
        self,
        *,
        project_manager: Any,
        project_uid: str,
        project_name: str,
        timeline_uid: str,
        empty_handoff_name: str | None = None,
    ) -> None:
        if any(
            not isinstance(value, str) or not value or value != value.strip()
            for value in (project_uid, project_name, timeline_uid)
        ):
            raise PresenterFramingError("native reopen identity is required")
        self._project_manager = project_manager
        self._project_uid = project_uid
        self._project_name = project_name
        self._timeline_uid = timeline_uid
        if empty_handoff_name is not None and (
            not isinstance(empty_handoff_name, str)
            or not empty_handoff_name
            or empty_handoff_name != empty_handoff_name.strip()
        ):
            raise PresenterFramingError("empty handoff name is invalid")
        self._empty_handoff_name = empty_handoff_name
        self._used = False
        self._reopened = False

    def _current_project(self) -> Any:
        get_current = getattr(self._project_manager, "GetCurrentProject", None)
        if not callable(get_current):
            raise PresenterFramingError("native project manager is unavailable")
        project = get_current()
        get_uid = getattr(project, "GetUniqueId", None)
        get_name = getattr(project, "GetName", None)
        get_timeline = getattr(project, "GetCurrentTimeline", None)
        if (
            project is None
            or not callable(get_uid)
            or not callable(get_name)
            or not callable(get_timeline)
            or get_uid() != self._project_uid
            or get_name() != self._project_name
        ):
            raise PresenterFramingError("current native project identity differs")
        timeline = get_timeline()
        get_timeline_uid = getattr(timeline, "GetUniqueId", None)
        if (
            timeline is None
            or not callable(get_timeline_uid)
            or get_timeline_uid() != self._timeline_uid
        ):
            raise PresenterFramingError("current native timeline identity differs")
        return project

    def _empty_handoff_identity(self, project: Any) -> tuple[str, str] | None:
        expected_name = self._empty_handoff_name
        if expected_name is None:
            return None
        try:
            handoff_uid = project.GetUniqueId()
            timeline_count = project.GetTimelineCount()
            if (
                not isinstance(handoff_uid, str)
                or not handoff_uid
                or handoff_uid == self._project_uid
                or project.GetName() != expected_name
                or project.GetCurrentTimeline() is not None
                or isinstance(timeline_count, bool)
                or not isinstance(timeline_count, int)
                or timeline_count != 0
            ):
                return None
            pool = project.GetMediaPool()
            root = pool.GetRootFolder()
            clips = root.GetClipList()
            folders = root.GetSubFolderList()
            jobs = project.GetRenderJobList()
            empty = all(
                isinstance(values, (list, tuple)) and not values
                for values in (clips, folders, jobs)
            )
            return (handoff_uid, expected_name) if empty else None
        except Exception:
            return None

    def require_available(self, timeline_uid: str) -> None:
        """Validate one-use admission and the expected live target before writes."""
        if self._used:
            raise PresenterFramingError("native save/reopen has already been used")
        if timeline_uid != self._timeline_uid:
            raise PresenterFramingError("native reopen timeline binding differs")
        if not all(
            callable(getattr(self._project_manager, name, None))
            for name in (
                "GetCurrentProject",
                "SaveProject",
                "CloseProject",
                "LoadProject",
            )
        ):
            raise PresenterFramingError("native save/reopen methods are unavailable")
        self._current_project()

    def __call__(self) -> None:
        if self._used:
            raise PresenterFramingError("native save/reopen has already been used")
        self._used = True

        project = self._current_project()
        save_project = getattr(self._project_manager, "SaveProject", None)
        close_project = getattr(self._project_manager, "CloseProject", None)
        load_project = getattr(self._project_manager, "LoadProject", None)
        if (
            not callable(save_project)
            or not callable(close_project)
            or not callable(load_project)
        ):
            raise PresenterFramingError("native save/reopen methods are unavailable")
        if save_project() is not True:
            raise PresenterFramingError("Resolve SaveProject failed")

        project = self._current_project()
        if close_project(project) is not True:
            raise PresenterFramingError("Resolve CloseProject failed")
        get_current = self._project_manager.GetCurrentProject
        current_after_close = get_current()
        if current_after_close is not None:
            handoff_identity = self._empty_handoff_identity(current_after_close)
            if handoff_identity is None:
                raise PresenterFramingError(
                    "Resolve left an unverified current project after close"
                )
            if self._empty_handoff_identity(get_current()) != handoff_identity:
                raise PresenterFramingError(
                    "Resolve changed the empty handoff project before reopen"
                )

        reopened = load_project(self._project_name)
        if reopened is None:
            raise PresenterFramingError("Resolve LoadProject failed")
        if (
            reopened.GetUniqueId() != self._project_uid
            or reopened.GetName() != self._project_name
        ):
            raise PresenterFramingError("reopened native project identity differs")
        current = get_current()
        if (
            current is None
            or current.GetUniqueId() != self._project_uid
            or current.GetName() != self._project_name
        ):
            raise PresenterFramingError("manager current project identity differs")

        current_timeline = current.GetCurrentTimeline()
        get_timeline_uid = getattr(current_timeline, "GetUniqueId", None)
        if not callable(get_timeline_uid) or get_timeline_uid() != self._timeline_uid:
            count_method = getattr(current, "GetTimelineCount", None)
            timeline_method = getattr(current, "GetTimelineByIndex", None)
            set_current = getattr(current, "SetCurrentTimeline", None)
            if (
                not callable(count_method)
                or not callable(timeline_method)
                or not callable(set_current)
            ):
                raise PresenterFramingError("reopened target timeline is unavailable")
            count = count_method()
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise PresenterFramingError("reopened timeline list is invalid")
            matches = []
            for index in range(1, count + 1):
                timeline = timeline_method(index)
                timeline_uid = getattr(timeline, "GetUniqueId", lambda: None)()
                if timeline_uid == self._timeline_uid:
                    matches.append(timeline)
            if len(matches) != 1 or set_current(matches[0]) is not True:
                raise PresenterFramingError(
                    "Resolve could not select the target timeline"
                )
        self._current_project()
        self._reopened = True

    def reopened_items_for(
        self, targets: Sequence[PresenterPictureTarget]
    ) -> dict[str, Any]:
        """Read exact target handles from this reopened timeline's video tracks."""
        if not self._reopened:
            raise PresenterFramingError("native project has not been reopened")
        expected = {target.timeline_item_uid: target for target in targets}
        if not targets or len(expected) != len(targets):
            raise PresenterFramingError("reopened target item UIDs are invalid")
        if any(target.owning_timeline_uid != self._timeline_uid for target in targets):
            raise PresenterFramingError("reopened target timeline binding differs")

        project = self._current_project()
        timeline = project.GetCurrentTimeline()
        get_track_count = getattr(timeline, "GetTrackCount", None)
        get_track_items = getattr(timeline, "GetItemListInTrack", None)
        if not callable(get_track_count) or not callable(get_track_items):
            raise PresenterFramingError("reopened video tracks are unavailable")
        track_count = get_track_count("video")
        if (
            isinstance(track_count, bool)
            or not isinstance(track_count, int)
            or track_count < 0
        ):
            raise PresenterFramingError("reopened video track count is invalid")

        items_by_uid: dict[str, Any] = {}
        for index in range(1, track_count + 1):
            for item in get_track_items("video", index) or []:
                get_uid = getattr(item, "GetUniqueId", None)
                uid = get_uid() if callable(get_uid) else None
                if not isinstance(uid, str) or not uid:
                    raise PresenterFramingError(
                        "reopened presenter item UID is unavailable"
                    )
                if uid in items_by_uid:
                    raise PresenterFramingError("reopened video item UID is duplicated")
                items_by_uid[uid] = item
        if not set(expected).issubset(items_by_uid):
            raise PresenterFramingError("reopened video item UID set differs")
        if any(items_by_uid[uid] is target.item for uid, target in expected.items()):
            raise PresenterFramingError("reopened timeline returned a pre-close item")
        self._current_project()
        return {
            target.event_id: items_by_uid[target.timeline_item_uid]
            for target in targets
        }


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
    owning_timeline_uid: str
    key: FramingKey
    source_interval: ValidatedSourceTimeInterval
    record_interval: ValidatedSourceTimeInterval
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
    seen_item_uids: set[str] = set()
    seen_items: set[int] = set()
    owner_uids: set[str] = set()
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
            or not isinstance(target.owning_timeline_uid, str)
            or not target.owning_timeline_uid.strip()
            or target.owning_timeline_uid != target.owning_timeline_uid.strip()
            or not isinstance(target.media_id, str)
            or not target.media_id
        ):
            raise PresenterFramingError(
                "target timeline, item, and media ids are required"
            )
        if target.timeline_item_uid in seen_item_uids:
            raise PresenterFramingError("presenter target item UID is duplicated")
        if not isinstance(target.source_interval, ValidatedSourceTimeInterval):
            raise PresenterFramingError("target source-time interval is not validated")
        if not isinstance(target.record_interval, ValidatedSourceTimeInterval):
            raise PresenterFramingError("target record interval is not validated")
        if target.source_interval.end_frame - target.source_interval.start_frame != (
            target.record_interval.end_frame - target.record_interval.start_frame
        ):
            raise PresenterFramingError(
                "target source/record intervals require exact 1:1 frames"
            )
        if target.event_id in seen_ids or id(target.item) in seen_items:
            raise PresenterFramingError("presenter target is duplicated")
        seen_ids.add(target.event_id)
        seen_item_uids.add(target.timeline_item_uid)
        seen_items.add(id(target.item))
        owner_uids.add(target.owning_timeline_uid)
    if len(owner_uids) != 1:
        raise PresenterFramingError("presenter targets must share one owning timeline")
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
        current_timeline_uid_reader: Callable[[], str | None],
        context_reader: Callable[[], Mapping[str, Any]],
        edition: Literal["studio", "free", "unknown"],
    ) -> None:
        if (
            not callable(current_target_check)
            or not callable(current_timeline_uid_reader)
            or not callable(context_reader)
        ):
            raise PresenterFramingError("live target and context checks are required")
        if edition not in {"studio", "free", "unknown"}:
            raise PresenterFramingError("Resolve edition is unknown")
        self._current_target_check = current_target_check
        self._current_timeline_uid_reader = current_timeline_uid_reader
        self._context_reader = context_reader
        self._edition = edition

    def _require_context(self, expected: Mapping[str, Any]) -> None:
        live = _validate_context(self._context_reader())
        if dict(live) != dict(expected):
            raise PresenterFramingError("live Resolve context differs from profile")

    def _require_timeline_owner(self, target: PresenterPictureTarget) -> None:
        self._current_target_check()
        if self._current_timeline_uid_reader() != target.owning_timeline_uid:
            raise PresenterFramingError(
                "presenter target belongs to a different current timeline"
            )

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
        # Studio 21.1.1.10 readback from AppendToTimeline is half-open here.
        if (
            isinstance(actual_start, bool)
            or not isinstance(actual_start, int)
            or isinstance(actual_end, bool)
            or not isinstance(actual_end, int)
            or actual_start != interval.start_frame
            or actual_end != interval.end_frame
        ):
            raise PresenterFramingError("presenter target source interval differs")
        start = item.GetStart(False)
        duration = item.GetDuration(False)
        record = target.record_interval
        if not _property_matches(start, record.start_frame) or not _property_matches(
            duration, record.end_frame - record.start_frame
        ):
            raise PresenterFramingError("presenter target record interval differs")

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
        save_close_reopen: NativeSaveReopen,
    ) -> _CycleResult:
        event_ids = tuple(target.event_id for target in targets)
        try:
            if type(save_close_reopen) is not NativeSaveReopen:
                raise PresenterFramingError("native save/reopen is required")
            save_close_reopen.require_available(targets[0].owning_timeline_uid)
            self._require_timeline_owner(targets[0])
            self._require_context(expected_context)
            for target in targets:
                self._require_item_identity(target.item, target)
        except Exception as error:
            return _CycleResult("blocked", f"Preflight blocked: {error}", event_ids)

        mutation_started = False
        color_limitations: list[str] = []
        try:
            for target in targets:
                self._require_item_identity(target.item, target)
                expected_name = f"OC {target.key.upper()} {target.event_id}"
                name_setter = target.item.SetName
                self._require_timeline_owner(target)
                mutation_started = True
                if name_setter(expected_name) is not True:
                    raise PresenterFramingError("Resolve rejected presenter item name")
                self._require_label(target.item, target)

                color_setter = getattr(target.item, "SetClipColor", None)
                if callable(color_setter):
                    self._require_timeline_owner(target)
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

                self._require_timeline_owner(target)
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

            self._require_timeline_owner(targets[0])
            mutation_started = True
            save_close_reopen()
            self._require_timeline_owner(targets[0])
            reopened = save_close_reopen.reopened_items_for(targets)
            self._require_timeline_owner(targets[0])
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
                "Exact presenter properties survived native save, reopen, "
                "and UID lookup.",
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
        save_close_reopen: NativeSaveReopen,
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
        save_close_reopen: NativeSaveReopen,
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
