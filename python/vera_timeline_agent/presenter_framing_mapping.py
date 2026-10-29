"""Bridge verified review frame ranges to presenter master-frame intervals."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .presenter_framing import ValidatedSourceTimeInterval

if TYPE_CHECKING:
    from .review_ingest import ReviewIngestAdapter

Json = dict[str, Any]
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_IDENTITY = re.compile(r"[0-9a-f]{64}\Z")


class PresenterFramingMappingError(ValueError):
    """The verified review mapping does not match the registered request."""


@dataclass(frozen=True)
class VerifiedPresenterFrameInterval:
    """Master-frame interval plus the #44 evidence that resolved it."""

    source_interval: ValidatedSourceTimeInterval
    mapping_evidence: Json


def map_review_frame_interval(
    adapter: ReviewIngestAdapter,
    project_id: str,
    job_id: str,
    review_interval: ValidatedSourceTimeInterval,
    *,
    expected_source_id: str,
    expected_source_content_hash: str,
) -> VerifiedPresenterFrameInterval:
    """Resolve a review frame range through #44's verified ingest handoff.

    `review_interval` is already expressed as an exact half-open frame range.
    This bridge deliberately leaves time-to-frame conversion to its caller and
    the public #44 mapper.
    """
    if not isinstance(review_interval, ValidatedSourceTimeInterval):
        raise PresenterFramingMappingError("review frame interval is not validated")
    if not isinstance(expected_source_id, str) or not expected_source_id.strip():
        raise PresenterFramingMappingError("expected registered source id is required")
    if (
        not isinstance(expected_source_content_hash, str)
        or _HASH.fullmatch(expected_source_content_hash) is None
    ):
        raise PresenterFramingMappingError("expected registered source hash is invalid")

    # This public #44 method reopens the verified review session, checks the
    # registered master and receipts, and returns the mapper's actual evidence.
    evidence = adapter.map_proxy_frame_range(
        project_id,
        job_id,
        review_interval.start_frame,
        review_interval.end_frame,
    )
    _validate_mapping_evidence(
        evidence,
        project_id=project_id,
        expected_source_id=expected_source_id,
        expected_source_content_hash=expected_source_content_hash,
        review_interval=review_interval,
    )
    frame_range = evidence["frameRange"]
    start_frame = evidence["startBoundary"]["sourceFrameIndex"]
    end_frame = evidence["endBoundary"]["sourceFrameIndex"]
    try:
        source_interval = ValidatedSourceTimeInterval(start_frame, end_frame)
    except (TypeError, ValueError) as error:
        raise PresenterFramingMappingError(
            "verified mapping returned invalid master frame bounds"
        ) from error
    if source_interval.start_frame >= source_interval.end_frame:
        raise PresenterFramingMappingError(
            "verified mapping returned an empty master frame interval"
        )
    if (
        frame_range["startInclusive"] != source_interval.start_frame
        or frame_range["endExclusive"] != source_interval.end_frame
    ):
        raise PresenterFramingMappingError(
            "verified mapping frame range differs from its source boundaries"
        )
    return VerifiedPresenterFrameInterval(source_interval, copy.deepcopy(evidence))


def _validate_mapping_evidence(
    evidence: object,
    *,
    project_id: str,
    expected_source_id: str,
    expected_source_content_hash: str,
    review_interval: ValidatedSourceTimeInterval,
) -> None:
    if not isinstance(evidence, dict):
        raise PresenterFramingMappingError("review mapper returned no evidence")
    if evidence.get("method") != "frame-index-identity/v1":
        raise PresenterFramingMappingError("review mapper returned an unknown method")
    if evidence.get("projectId") != project_id:
        raise PresenterFramingMappingError("review mapping belongs to another project")
    if evidence.get("sourceId") != expected_source_id:
        raise PresenterFramingMappingError("review mapping belongs to another source")
    if evidence.get("sourceContentHash") != expected_source_content_hash:
        raise PresenterFramingMappingError("review mapping master hash does not match")
    if (
        not isinstance(evidence.get("generationIdentity"), str)
        or _IDENTITY.fullmatch(evidence["generationIdentity"]) is None
    ):
        raise PresenterFramingMappingError("review mapping generation is invalid")
    video_source = evidence.get("videoSource")
    if video_source not in {"proxy", "master"}:
        raise PresenterFramingMappingError(
            "review mapping has no verified video source"
        )
    mapping_hash = evidence.get("mappingHash")
    if video_source == "proxy":
        if not isinstance(mapping_hash, str) or _HASH.fullmatch(mapping_hash) is None:
            raise PresenterFramingMappingError("proxy mapping identity is invalid")
    elif mapping_hash is not None:
        raise PresenterFramingMappingError(
            "master playback unexpectedly has a proxy map"
        )

    frame_range = evidence.get("frameRange")
    if not isinstance(frame_range, dict) or frame_range != {
        "startInclusive": review_interval.start_frame,
        "endExclusive": review_interval.end_frame,
    }:
        raise PresenterFramingMappingError(
            "review mapper changed the requested frame range"
        )
    start_boundary = evidence.get("startBoundary")
    end_boundary = evidence.get("endBoundary")
    if not isinstance(start_boundary, dict) or not isinstance(end_boundary, dict):
        raise PresenterFramingMappingError("review mapping boundaries are missing")
    for boundary, expected_index in (
        (start_boundary, review_interval.start_frame),
        (end_boundary, review_interval.end_frame),
    ):
        if (
            type(boundary.get("reviewFrameIndex")) is not int
            or boundary["reviewFrameIndex"] != expected_index
            or type(boundary.get("sourceFrameIndex")) is not int
            or boundary["sourceFrameIndex"] < 0
            or not isinstance(boundary.get("reviewPtsSeconds"), dict)
            or not isinstance(boundary.get("sourcePtsSeconds"), dict)
        ):
            raise PresenterFramingMappingError(
                "review mapper returned invalid frame boundary evidence"
            )
