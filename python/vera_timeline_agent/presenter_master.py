"""Build a protected Presenter Master and a separate framing target."""

from __future__ import annotations

import json
import math
import re
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Literal

from .narration.models import sha256_bytes
from .presenter_framing import (
    PresenterFramingError,
    PresenterPictureTarget,
    ValidatedSourceTimeInterval,
    _json_equal,
    _strict_json_object,
    validate_profile_snapshot,
)
from .presenter_framing_mapping import (
    PresenterFramingMappingError,
    _validate_mapping_evidence,
)

_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RESOLVE_NTSC_RATES = {
    "23.976": Fraction(24_000, 1_001),
    "29.97": Fraction(30_000, 1_001),
    "47.952": Fraction(48_000, 1_001),
    "59.94": Fraction(60_000, 1_001),
    "119.88": Fraction(120_000, 1_001),
}


class PresenterMasterError(RuntimeError):
    """Input or native operation failed; created timelines are never removed."""

    def __init__(
        self, message: str, created_timeline_names: Sequence[str] = ()
    ) -> None:
        super().__init__(message)
        self.created_timeline_names = tuple(created_timeline_names)


@dataclass(frozen=True)
class ResolvedPresenterMedia:
    """Media-pool handle already resolved by the registered-source caller."""

    project_id: str
    source_id: str
    media_hash: str
    path: str
    media_id: str
    source_frame_rate: tuple[int, int]
    source_frame_count: int
    kind: Literal["video", "audio"]
    item: Any


@dataclass(frozen=True)
class PresenterMasterBuild:
    master_timeline: Any
    master_timeline_uid: str
    generated_timeline: Any
    generated_timeline_uid: str
    presenter_targets: tuple[PresenterPictureTarget, ...]
    master_picture_uid: str
    master_dialogue_uid: str
    generated_dialogue_item: Any
    generated_dialogue_uid: str
    generated_dialogue_media_id: str
    protected_master_tracks: tuple[tuple[str, int], ...]
    reviewed_color: dict[str, str]
    processed_dialogue: dict[str, str | int]
    profile_pin: dict[str, Any]
    request_hash: str


def _hash(value: object, label: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise PresenterMasterError(f"{label} must be a lowercase SHA-256 hash")
    return value


def _frame(value: object, label: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= 9_007_199_254_740_991
    ):
        raise PresenterMasterError(f"{label} must be a non-negative safe integer")
    return value


def _rate(value: object, label: str) -> Fraction:
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or any(
            isinstance(part, bool) or not isinstance(part, int) or part <= 0
            for part in value
        )
    ):
        raise PresenterMasterError(
            f"{label} frame rate must be an exact positive rational"
        )
    return Fraction(*value)


def _positive_frame_count(value: object, label: str) -> int:
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        value = int(value)
    count = _frame(value, label)
    if count == 0:
        raise PresenterMasterError(f"{label} must be positive")
    return count


def _audio_duration_frame_count(value: object, rate: Fraction) -> int:
    match = (
        re.fullmatch(r"([0-9]+):([0-9]{2}):([0-9]{2})([:;])([0-9]{2,3})", value)
        if isinstance(value, str)
        else None
    )
    if match is None or (
        rate.denominator != 1 and rate not in _RESOLVE_NTSC_RATES.values()
    ):
        raise PresenterMasterError(
            "Resolve audio duration cannot independently confirm its source frame count"
        )
    hours, minutes, seconds = (int(part) for part in match.groups()[:3])
    separator, frame_label = match.groups()[3:]
    frames = int(frame_label)
    nominal_rate = math.ceil(rate)
    if minutes >= 60 or seconds >= 60 or frames >= nominal_rate:
        raise PresenterMasterError("Resolve audio duration is invalid")
    total_minutes = hours * 60 + minutes
    count = (total_minutes * 60 + seconds) * nominal_rate + frames
    if separator == ";":
        if rate != Fraction(nominal_rate * 1000, 1001) or nominal_rate % 30:
            raise PresenterMasterError("Resolve drop-frame duration rate is invalid")
        dropped = nominal_rate // 15
        if minutes % 10 and seconds == 0 and frames < dropped:
            raise PresenterMasterError("Resolve audio duration uses a dropped label")
        count -= dropped * (total_minutes - total_minutes // 10)
    return count


def _strict_json_value(payload: bytes, label: str) -> Any:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise PresenterMasterError(f"{label} has duplicate JSON keys")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise PresenterMasterError(f"{label} has a non-finite value: {value}")

    def finite_float(value: str) -> float:
        result = float(value)
        if not math.isfinite(result):
            raise PresenterMasterError(f"{label} has a non-finite number")
        return result

    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
            parse_float=finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PresenterMasterError(f"{label} is not UTF-8 JSON") from error


def _preflight(
    request: Mapping[str, Any],
    *,
    registered_project_id: str,
    picture: ResolvedPresenterMedia,
    dialogue: ResolvedPresenterMedia,
    observed_context: Mapping[str, Any],
    expected_profile_pin: Mapping[str, Any],
    expected_request_hash: str,
) -> tuple[
    dict[str, Any], list[dict[str, Any]], ValidatedSourceTimeInterval, dict[str, Any]
]:
    if (
        request.get("schemaVersion") != "presenter-framing-request/v1"
        or request.get("status") != "requested"
        or request.get("masterPolicy") != "create_new_protected_master"
    ):
        raise PresenterMasterError("unsupported presenter framing request")
    request_hash = _hash(request.get("requestHash"), "request hash")
    if request_hash != _hash(expected_request_hash, "expected request hash"):
        raise PresenterMasterError("request differs from its independent hash pin")
    content_json = request.get("requestContentJson")
    if not isinstance(content_json, str):
        raise PresenterMasterError(
            "exact TypeScript request-content bytes are required"
        )
    try:
        content_bytes = content_json.encode("utf-8")
    except UnicodeEncodeError as error:
        raise PresenterMasterError("request content is not valid UTF-8") from error
    content = _strict_json_object(content_bytes, "canonical presenter request")
    payload = {
        key: value
        for key, value in request.items()
        if key not in {"requestHash", "requestContentJson"}
    }
    if not _json_equal(content, payload) or sha256_bytes(content_bytes) != request_hash:
        raise PresenterMasterError(
            "canonical request bytes, fields, or request hash differ"
        )

    project_id = request.get("projectId")
    if (
        not isinstance(project_id, str)
        or not project_id
        or project_id != registered_project_id
        or picture.project_id != project_id
        or dialogue.project_id != project_id
    ):
        raise PresenterMasterError(
            "resolved media does not belong to the registered request project"
        )
    if (
        picture.kind != "video"
        or dialogue.kind != "audio"
        or picture.source_id != request.get("sourceId")
    ):
        raise PresenterMasterError(
            "a registered presenter video and separate dialogue audio are required"
        )
    picture_frame_count = _positive_frame_count(
        picture.source_frame_count, "registered presenter source frame count"
    )
    dialogue_frame_count = _positive_frame_count(
        dialogue.source_frame_count, "registered dialogue source frame count"
    )
    dialogue_request = request.get("dialogue")
    if not isinstance(dialogue_request, Mapping):
        raise PresenterMasterError(
            "independent processed-dialogue evidence is required"
        )
    if picture.media_hash != request.get("sourceHash") or dialogue.media_hash != (
        dialogue_request.get("mediaHash")
    ):
        raise PresenterMasterError(
            "resolved media hashes differ from the prepared request"
        )
    _hash(picture.media_hash, "presenter media hash")
    _hash(dialogue.media_hash, "dialogue media hash")
    if (
        picture.media_hash == dialogue.media_hash
        or picture.media_id == dialogue.media_id
    ):
        raise PresenterMasterError(
            "processed dialogue must be an independent immutable audio artifact"
        )
    if not all(
        (
            picture.path,
            picture.media_id,
            dialogue.source_id,
            dialogue.path,
            dialogue.media_id,
        )
    ):
        raise PresenterMasterError(
            "registered media handles, paths, and identities are required"
        )

    raw_profile = request.get("profile")
    if not isinstance(raw_profile, Mapping):
        raise PresenterMasterError("paired framing profile is required")
    profile_content = request.get("profileContentJson")
    if not isinstance(profile_content, (str, bytes)):
        raise PresenterMasterError("exact profile content bytes are required")
    try:
        profile = validate_profile_snapshot(
            raw_profile,
            canonical_content_json=profile_content,
            expected_pin=expected_profile_pin,
        )
    except PresenterFramingError as error:
        raise PresenterMasterError(str(error)) from error
    if not _json_equal(profile["context"], observed_context):
        raise PresenterMasterError(
            "live source/timeline/Resolve context differs from the pinned profile"
        )
    source_rate = profile["context"]["sourceRaster"]["frameRate"]
    timeline_rate = profile["context"]["timelineRaster"]["frameRate"]
    if Fraction(source_rate["numerator"], source_rate["denominator"]) != Fraction(
        timeline_rate["numerator"], timeline_rate["denominator"]
    ):
        raise PresenterMasterError(
            "this presenter route requires an exact source/timeline frame-rate match"
        )
    if _rate(picture.source_frame_rate, "presenter") != Fraction(
        source_rate["numerator"], source_rate["denominator"]
    ):
        raise PresenterMasterError(
            "registered presenter frame rate differs from profile context"
        )

    color = request.get("reviewedColor")
    if not isinstance(color, Mapping):
        raise PresenterMasterError(
            "reviewed upstream synthetic color evidence is required"
        )
    reviewed_color = {
        "profileHash": _hash(color.get("profileHash"), "color profile hash"),
        "reviewEvidenceHash": _hash(
            color.get("reviewEvidenceHash"), "color review hash"
        ),
    }

    intervals = request.get("intervals")
    mappings = request.get("mappingEvidence")
    mapping_content_json = request.get("mappingEvidenceContentJson")
    if (
        not isinstance(intervals, list)
        or not intervals
        or not isinstance(mappings, list)
        or len(mappings) != len(intervals)
        or not isinstance(mapping_content_json, str)
    ):
        raise PresenterMasterError(
            "exact presenter intervals and mapping handoffs are required"
        )
    mapping_hash = _hash(request.get("mappingEvidenceHash"), "mapping evidence hash")
    try:
        mapping_bytes = mapping_content_json.encode("utf-8")
    except UnicodeEncodeError as error:
        raise PresenterMasterError(
            "mapping evidence content is not valid UTF-8"
        ) from error
    canonical_mappings = _strict_json_value(
        mapping_bytes, "canonical presenter mapping evidence"
    )
    if (
        not isinstance(canonical_mappings, list)
        or not _json_equal(canonical_mappings, mappings)
        or sha256_bytes(mapping_bytes) != mapping_hash
    ):
        raise PresenterMasterError(
            "canonical mapping bytes, evidence, or mapping hash differ"
        )
    mappings = canonical_mappings
    normalized: list[dict[str, Any]] = []
    ids: set[str] = set()
    generation: str | None = None
    first_mapping_identity: tuple[str, str, object] | None = None
    source_rate = profile["context"]["sourceRaster"]["frameRate"]
    for index, (value, evidence) in enumerate(zip(intervals, mappings, strict=True)):
        if not isinstance(value, Mapping) or not isinstance(evidence, Mapping):
            raise PresenterMasterError("presenter interval mapping evidence is absent")
        event_id, key = value.get("eventId"), value.get("framingKey")
        record_start = _frame(value.get("recordStart"), "record start")
        record_end = _frame(value.get("recordEnd"), "record end")
        source_start = _frame(value.get("sourceStart"), "source start")
        source_end = _frame(value.get("sourceEnd"), "source end")
        if (
            not isinstance(event_id, str)
            or not event_id
            or any(ch.isspace() for ch in event_id)
            or event_id in ids
            or key not in {"wide", "tight"}
            or not isinstance(value.get("visible"), bool)
            or value.get("name") != f"OC {str(key).upper()} {event_id}"
            or value.get("color") != ("Blue" if key == "wide" else "Orange")
            or record_end <= record_start
            or source_end <= source_start
            or record_end - record_start != source_end - source_start
        ):
            raise PresenterMasterError(
                "presenter interval identity or exact range is invalid"
            )
        if source_end > picture_frame_count:
            raise PresenterMasterError(
                "presenter interval exceeds its registered source frame count"
            )
        if index and (
            normalized[-1]["recordEnd"] != record_start
            or normalized[-1]["sourceEnd"] != source_start
        ):
            raise PresenterMasterError(
                "presenter intervals are not source/record contiguous"
            )
        try:
            _validate_mapping_evidence(
                evidence,
                project_id=project_id,
                expected_source_id=request["sourceId"],
                expected_source_content_hash=request["sourceHash"],
                review_interval=ValidatedSourceTimeInterval(source_start, source_end),
            )
        except (PresenterFramingMappingError, KeyError) as error:
            raise PresenterMasterError(
                "prepared mapping evidence differs from the interval identity/range"
            ) from error
        if (
            evidence["startBoundary"]["sourceFrameIndex"] != source_start
            or evidence["endBoundary"]["sourceFrameIndex"] != source_end
            or not _json_equal(evidence.get("sourceRate"), source_rate)
            or not isinstance(evidence.get("sourceProbeHash"), str)
            or not _HASH.fullmatch(evidence["sourceProbeHash"])
            or "mappingHash" not in evidence
        ):
            raise PresenterMasterError(
                "prepared mapping source boundaries, rate, or probe are invalid"
            )
        if generation is None:
            generation = evidence["generationIdentity"]
        elif evidence["generationIdentity"] != generation:
            raise PresenterMasterError(
                "presenter intervals use different mapping generations"
            )
        identity = (
            evidence["sourceProbeHash"],
            evidence["generationIdentity"],
            evidence["mappingHash"],
        )
        if first_mapping_identity is None:
            first_mapping_identity = identity
        elif identity != first_mapping_identity:
            raise PresenterMasterError(
                "presenter intervals use different mapping generations"
            )
        ids.add(event_id)
        normalized.append(
            {
                "eventId": event_id,
                "framingKey": key,
                "recordStart": record_start,
                "recordEnd": record_end,
                "sourceStart": source_start,
                "sourceEnd": source_end,
            }
        )
    dialogue_hashes = {
        "mediaHash": dialogue.media_hash,
        "processingProfileHash": _hash(
            dialogue_request.get("processingProfileHash"),
            "dialogue processing profile hash",
        ),
        "synchronizationEvidenceHash": _hash(
            dialogue_request.get("synchronizationEvidenceHash"),
            "dialogue synchronization hash",
        ),
    }
    first, last = normalized[0], normalized[-1]
    start, end = (
        _frame(dialogue_request.get("recordStart"), "dialogue record start"),
        _frame(dialogue_request.get("recordEnd"), "dialogue record end"),
    )
    sample_start = _frame(
        dialogue_request.get("sourceStartSample"), "dialogue source start sample"
    )
    sample_end = _frame(
        dialogue_request.get("sourceEndSample"), "dialogue source end sample"
    )
    sample_rate = _frame(dialogue_request.get("sampleRate"), "dialogue sample rate")
    if (
        not isinstance(dialogue_request.get("eventId"), str)
        or not dialogue_request["eventId"]
        or dialogue_request["eventId"] in ids
        or start != first["recordStart"]
        or end != last["recordEnd"]
        or sample_rate == 0
        or sample_end <= sample_start
    ):
        raise PresenterMasterError(
            "one synchronized dialogue placement must span the full presenter range"
        )
    timeline_rate = profile["context"]["timelineRaster"]["frameRate"]
    if (sample_end - sample_start) * timeline_rate["numerator"] != (
        end - start
    ) * sample_rate * timeline_rate["denominator"]:
        raise PresenterMasterError(
            "dialogue sample duration differs from the exact timeline range"
        )
    audio_rate = _rate(dialogue.source_frame_rate, "dialogue source")
    timeline_fps = Fraction(timeline_rate["numerator"], timeline_rate["denominator"])
    if audio_rate != timeline_fps:
        raise PresenterMasterError(
            "this presenter route requires an exact dialogue/timeline frame-rate match"
        )
    source_start_frame = Fraction(sample_start, sample_rate) * audio_rate
    source_end_frame = Fraction(sample_end, sample_rate) * audio_rate
    if source_start_frame.denominator != 1 or source_end_frame.denominator != 1:
        raise PresenterMasterError(
            "dialogue sample boundaries do not map to exact source frames"
        )
    source_interval = ValidatedSourceTimeInterval(
        source_start_frame.numerator, source_end_frame.numerator
    )
    if source_interval.end_frame > dialogue_frame_count:
        raise PresenterMasterError(
            "dialogue interval exceeds its registered source frame count"
        )
    try:
        native_sample_rate = _positive_frame_count(
            dialogue.item.GetClipProperty("Sample Rate"),
            "Resolve dialogue sample rate",
        )
    except (AttributeError, TypeError) as error:
        raise PresenterMasterError(
            "Resolve dialogue sample rate is unavailable"
        ) from error
    if native_sample_rate != sample_rate:
        raise PresenterMasterError(
            "Resolve dialogue sample rate differs from its synchronization evidence"
        )
    provenance = {
        "reviewedColor": reviewed_color,
        "dialogueHashes": dialogue_hashes,
        "dialogue": dict(dialogue_request),
        "dialogueSourceInterval": source_interval,
    }
    return profile, normalized, source_interval, provenance


def _identity(media: ResolvedPresenterMedia) -> tuple[str, str]:
    item = media.item
    get_id = getattr(item, "GetMediaId", None)
    get_uid = getattr(item, "GetUniqueId", None)
    get_prop = getattr(item, "GetClipProperty", None)
    if not callable(get_id) or not callable(get_uid) or not callable(get_prop):
        raise PresenterMasterError(
            "resolved media-pool handle lacks public identity methods"
        )
    if get_id() != media.media_id or get_prop("File Path") != media.path:
        raise PresenterMasterError(
            "resolved media-pool identity/path differs from registration"
        )
    try:
        fps_label = str(get_prop("FPS"))
        resolve_rate = (
            _RESOLVE_NTSC_RATES[fps_label]
            if fps_label in _RESOLVE_NTSC_RATES
            else Fraction(fps_label)
        )
        if resolve_rate != _rate(media.source_frame_rate, media.kind):
            raise PresenterMasterError(
                "Resolve media frame rate differs from its independent registration"
            )
    except (ValueError, ZeroDivisionError) as error:
        raise PresenterMasterError("Resolve media frame rate is unavailable") from error
    source_frame_count = _positive_frame_count(
        media.source_frame_count, "registered source frame count"
    )
    if media.kind == "video":
        native_frame_count = _positive_frame_count(
            get_prop("Frames"), "Resolve video frame count"
        )
    elif media.kind == "audio":
        native_frame_count = _audio_duration_frame_count(
            get_prop("Duration"), resolve_rate
        )
    else:
        raise PresenterMasterError("resolved media kind is unsupported")
    if native_frame_count != source_frame_count:
        raise PresenterMasterError(
            "Resolve source frame count differs from independent registration"
        )
    uid = get_uid()
    if not isinstance(uid, str) or not uid:
        raise PresenterMasterError("resolved media-pool unique identity is unavailable")
    return media.media_id, uid


def _uid(value: Any | None) -> str | None:
    if value is None:
        return None
    uid = value.GetUniqueId()
    if not isinstance(uid, str) or not uid:
        raise PresenterMasterError("native target unique identity is unavailable")
    return uid


def _guard(
    project: Any,
    project_uid: str,
    timeline_uid: str | None,
    guard: Callable[[str | None], None],
) -> None:
    guard(timeline_uid)
    if (
        project.GetUniqueId() != project_uid
        or _uid(project.GetCurrentTimeline()) != timeline_uid
    ):
        raise PresenterMasterError(
            "live project/timeline changed; refusing native mutation"
        )


def _names(project: Any) -> set[str]:
    return {
        project.GetTimelineByIndex(i).GetName()
        for i in range(1, project.GetTimelineCount() + 1)
    }


def _select(
    project: Any, timeline: Any, project_uid: str, guard: Callable[[str | None], None]
) -> str:
    uid = _uid(timeline)
    current_uid = _uid(project.GetCurrentTimeline())
    if current_uid != uid:
        _guard(project, project_uid, current_uid, guard)
        if (
            project.SetCurrentTimeline(timeline) is not True
            or _uid(project.GetCurrentTimeline()) != uid
        ):
            raise PresenterMasterError("Resolve could not select the new timeline")
    return uid  # type: ignore[return-value]


def _prepare_empty(
    project: Any,
    timeline: Any,
    project_uid: str,
    expected_context: Mapping[str, Any],
    context_reader: Callable[[Any | None], Mapping[str, Any]],
    guard: Callable[[str | None], None],
) -> str:
    uid = _select(project, timeline, project_uid, guard)
    if not _json_equal(context_reader(timeline), expected_context):
        raise PresenterMasterError(
            "new timeline context differs from the pinned profile"
        )
    _guard(project, project_uid, uid, guard)
    if (
        timeline.SetStartTimecode("00:00:00:00") is not True
        or timeline.GetStartFrame() != 0
    ):
        raise PresenterMasterError("new timeline did not retain its frame-zero start")
    for kind in ("video", "audio"):
        if timeline.GetTrackCount(kind) == 0:
            _guard(project, project_uid, uid, guard)
            if timeline.AddTrack(kind) is not True:
                raise PresenterMasterError(f"could not create new {kind} track")
        for index in range(1, timeline.GetTrackCount(kind) + 1):
            if timeline.GetItemListInTrack(kind, index):
                raise PresenterMasterError("Resolve did not create an empty timeline")
    return uid


def _append(
    pool: Any,
    project: Any,
    project_uid: str,
    timeline_uid: str,
    guard: Callable[[str | None], None],
    infos: list[dict[str, Any]],
) -> list[Any]:
    _guard(project, project_uid, timeline_uid, guard)
    items = pool.AppendToTimeline(infos)
    if not isinstance(items, (list, tuple)) or len(items) != len(infos):
        raise PresenterMasterError("Resolve did not append the exact requested items")
    return list(items)


def _read_item(
    item: Any,
    kind: str,
    media: ResolvedPresenterMedia,
    record: ValidatedSourceTimeInterval,
    source: ValidatedSourceTimeInterval,
) -> str:
    native_media = item.GetMediaPoolItem()
    start, duration = item.GetStart(False), item.GetDuration(False)
    if (
        item.GetType() != kind
        or native_media is None
        or native_media.GetMediaId() != media.media_id
        or isinstance(start, bool)
        or not isinstance(start, (int, float))
        or not math.isfinite(start)
        or start != record.start_frame
        or isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration != record.end_frame - record.start_frame
        or item.GetSourceStartFrame() != source.start_frame
        or item.GetSourceEndFrame()
        != min(source.end_frame, media.source_frame_count - 1)
    ):
        raise PresenterMasterError(
            "Resolve item identity or source/record range readback differs"
        )
    uid = item.GetUniqueId()
    if not isinstance(uid, str) or not uid:
        raise PresenterMasterError("timeline item unique identity is unavailable")
    return uid


def _items(timeline: Any, kind: str) -> list[Any]:
    result: list[Any] = []
    for index in range(1, timeline.GetTrackCount(kind) + 1):
        items = list(timeline.GetItemListInTrack(kind, index))
        if index == 1:
            result = items
        elif items:
            raise PresenterMasterError(f"unexpected items on extra {kind} track")
    return result


def _lock_master(
    project: Any,
    timeline: Any,
    project_uid: str,
    uid: str,
    guard: Callable[[str | None], None],
) -> tuple[tuple[str, int], ...]:
    tracks: list[tuple[str, int]] = []
    for kind in ("video", "audio"):
        for index in range(1, timeline.GetTrackCount(kind) + 1):
            _guard(project, project_uid, uid, guard)
            if (
                timeline.SetTrackLock(kind, index, True) is not True
                or timeline.GetIsTrackLocked(kind, index) is not True
            ):
                raise PresenterMasterError(
                    f"master {kind} track {index} did not lock and read back"
                )
            tracks.append((kind, index))
    if not tracks:
        raise PresenterMasterError("Presenter Master has no picture/audio tracks")
    return tuple(tracks)


def prepare_presenter_master(
    project: Any,
    media_pool: Any,
    request: Mapping[str, Any],
    *,
    registered_project_id: str,
    picture_media: ResolvedPresenterMedia,
    dialogue_media: ResolvedPresenterMedia,
    upstream_color_operation: Literal["identity_synthetic_reviewed"],
    current_target_guard: Callable[[str | None], None],
    context_reader: Callable[[Any | None], Mapping[str, Any]],
    expected_profile_pin: Mapping[str, Any],
    expected_request_hash: str,
) -> PresenterMasterBuild:
    """Create new locked source and separate unlocked framing timelines.

    No source is imported or processed. #43 registration and #44 mapping remain
    caller-owned; non-neutral application and save/reopen verification follow.
    """
    if upstream_color_operation != "identity_synthetic_reviewed":
        raise PresenterMasterError(
            "only already-treated synthetic color sources are supported"
        )
    if (
        project is None
        or media_pool is None
        or not callable(current_target_guard)
        or not callable(context_reader)
    ):
        raise PresenterMasterError(
            "live project, media pool, target guard, and context reader are required"
        )
    project_uid = project.GetUniqueId()
    if not isinstance(project_uid, str) or not project_uid or not registered_project_id:
        raise PresenterMasterError(
            "live native and registered project identities are required"
        )
    original = project.GetCurrentTimeline()
    original_uid = _uid(original)
    _guard(project, project_uid, original_uid, current_target_guard)
    profile, intervals, dialogue_source, provenance = _preflight(
        request,
        registered_project_id=registered_project_id,
        picture=picture_media,
        dialogue=dialogue_media,
        observed_context=context_reader(original),
        expected_profile_pin=expected_profile_pin,
        expected_request_hash=expected_request_hash,
    )
    picture_id, _ = _identity(picture_media)
    dialogue_id, _ = _identity(dialogue_media)
    first, last = intervals[0], intervals[-1]
    record_all = ValidatedSourceTimeInterval(first["recordStart"], last["recordEnd"])
    picture_all = ValidatedSourceTimeInterval(first["sourceStart"], last["sourceEnd"])
    picture_ranges = [
        ValidatedSourceTimeInterval(row["sourceStart"], row["sourceEnd"])
        for row in intervals
    ]
    picture_records = [
        ValidatedSourceTimeInterval(row["recordStart"], row["recordEnd"])
        for row in intervals
    ]
    dialogue_record = record_all

    token = uuid.uuid4().hex
    master_name, generated_name = (
        f"VERA Presenter Master {token}",
        f"VERA Presenter Framing {token}",
    )
    if master_name in _names(project) or generated_name in _names(project):
        raise PresenterMasterError("new timeline name already exists")
    created: list[str] = []
    try:
        _guard(project, project_uid, original_uid, current_target_guard)
        master = media_pool.CreateEmptyTimeline(master_name)
        if master is None:
            raise PresenterMasterError("Resolve did not create a new Presenter Master")
        created.append(master.GetName())
        if master.GetName() != master_name:
            raise PresenterMasterError(
                "Resolve changed the unique Presenter Master name"
            )
        master_uid = _prepare_empty(
            project,
            master,
            project_uid,
            profile["context"],
            context_reader,
            current_target_guard,
        )
        master_video = _append(
            media_pool,
            project,
            project_uid,
            master_uid,
            current_target_guard,
            [
                {
                    "mediaPoolItem": picture_media.item,
                    "startFrame": picture_all.start_frame,
                    "endFrame": picture_all.end_frame,
                    "mediaType": 1,
                    "trackIndex": 1,
                    "recordFrame": record_all.start_frame,
                }
            ],
        )
        master_audio = _append(
            media_pool,
            project,
            project_uid,
            master_uid,
            current_target_guard,
            [
                {
                    "mediaPoolItem": dialogue_media.item,
                    "startFrame": dialogue_source.start_frame,
                    "endFrame": dialogue_source.end_frame,
                    "mediaType": 2,
                    "trackIndex": 1,
                    "recordFrame": dialogue_record.start_frame,
                }
            ],
        )
        master_v = _items(master, "video")
        master_a = _items(master, "audio")
        if len(master_v) != 1 or len(master_a) != 1:
            raise PresenterMasterError(
                "Presenter Master must have one picture and one dialogue item"
            )
        master_picture_uid = _read_item(
            master_v[0], "video", picture_media, record_all, picture_all
        )
        master_dialogue_uid = _read_item(
            master_a[0], "audio", dialogue_media, dialogue_record, dialogue_source
        )
        if (
            master_picture_uid != master_video[0].GetUniqueId()
            or master_dialogue_uid != master_audio[0].GetUniqueId()
        ):
            raise PresenterMasterError(
                "Presenter Master readback differs from appended items"
            )
        protected = _lock_master(
            project, master, project_uid, master_uid, current_target_guard
        )

        active_uid = _uid(project.GetCurrentTimeline())
        _guard(project, project_uid, active_uid, current_target_guard)
        generated = media_pool.CreateEmptyTimeline(generated_name)
        if generated is None:
            raise PresenterMasterError(
                "Resolve did not create the separate framing target"
            )
        created.append(generated.GetName())
        if generated.GetName() != generated_name:
            raise PresenterMasterError("Resolve changed the unique framing-target name")
        generated_uid = _prepare_empty(
            project,
            generated,
            project_uid,
            profile["context"],
            context_reader,
            current_target_guard,
        )
        generated_video = _append(
            media_pool,
            project,
            project_uid,
            generated_uid,
            current_target_guard,
            [
                {
                    "mediaPoolItem": picture_media.item,
                    "startFrame": row["sourceStart"],
                    "endFrame": row["sourceEnd"],
                    "mediaType": 1,
                    "trackIndex": 1,
                    "recordFrame": row["recordStart"],
                }
                for row in intervals
            ],
        )
        generated_audio = _append(
            media_pool,
            project,
            project_uid,
            generated_uid,
            current_target_guard,
            [
                {
                    "mediaPoolItem": dialogue_media.item,
                    "startFrame": dialogue_source.start_frame,
                    "endFrame": dialogue_source.end_frame,
                    "mediaType": 2,
                    "trackIndex": 1,
                    "recordFrame": dialogue_record.start_frame,
                }
            ],
        )
        target_items, audio_items = (
            _items(generated, "video"),
            _items(generated, "audio"),
        )
        target_items.sort(key=lambda item: item.GetStart(False))
        if len(target_items) != len(intervals) or len(audio_items) != 1:
            raise PresenterMasterError(
                "framing target needs picture intervals and one dialogue item"
            )
        if {item.GetUniqueId() for item in target_items} != {
            item.GetUniqueId() for item in generated_video
        }:
            raise PresenterMasterError(
                "generated picture track differs from the appended handles"
            )
        targets: list[PresenterPictureTarget] = []
        for row, source_range, record_range, item in zip(
            intervals, picture_ranges, picture_records, target_items, strict=True
        ):
            item_uid = _read_item(
                item, "video", picture_media, record_range, source_range
            )
            targets.append(
                PresenterPictureTarget(
                    event_id=row["eventId"],
                    owning_timeline_uid=generated_uid,
                    key=row["framingKey"],
                    source_interval=source_range,
                    record_interval=record_range,
                    source_frame_count=picture_media.source_frame_count,
                    timeline_item_uid=item_uid,
                    media_id=picture_id,
                    item=item,
                )
            )
        dialogue_uid = _read_item(
            audio_items[0], "audio", dialogue_media, dialogue_record, dialogue_source
        )
        if dialogue_uid != generated_audio[0].GetUniqueId():
            raise PresenterMasterError(
                "generated dialogue differs from the appended handle"
            )
        _guard(project, project_uid, generated_uid, current_target_guard)
        _select(project, master, project_uid, current_target_guard)
        try:
            if not _json_equal(context_reader(master), profile["context"]):
                raise PresenterMasterError(
                    "Presenter Master context changed before lock verification"
                )
            for kind, index in protected:
                if master.GetIsTrackLocked(kind, index) is not True:
                    raise PresenterMasterError(
                        "Presenter Master track lock did not persist"
                    )
        finally:
            _select(project, generated, project_uid, current_target_guard)
        _guard(project, project_uid, generated_uid, current_target_guard)
        if not _json_equal(context_reader(generated), profile["context"]):
            raise PresenterMasterError(
                "generated framing context changed during lock verification"
            )
        return PresenterMasterBuild(
            master,
            master_uid,
            generated,
            generated_uid,
            tuple(targets),
            master_picture_uid,
            master_dialogue_uid,
            audio_items[0],
            dialogue_uid,
            dialogue_id,
            protected,
            {
                **provenance["reviewedColor"],
                "operation": upstream_color_operation,
                "application": "pretreated source; no color operation applied here",
            },
            {
                **provenance["dialogueHashes"],
                "eventId": provenance["dialogue"]["eventId"],
                "sourceStartSample": provenance["dialogue"]["sourceStartSample"],
                "sourceEndSample": provenance["dialogue"]["sourceEndSample"],
                "sampleRate": provenance["dialogue"]["sampleRate"],
                "processing": "registered processed source; no audio operation applied",
            },
            {key: profile[key] for key in ("id", "version", "profileHash")},
            request["requestHash"],
        )
    except Exception as error:
        names = tuple(created)
        message = str(error)
        if names:
            message = (
                f"workflow stopped after creating {', '.join(names)}; "
                f"timelines were preserved: {message}"
            )
        raise PresenterMasterError(message, names) from error
