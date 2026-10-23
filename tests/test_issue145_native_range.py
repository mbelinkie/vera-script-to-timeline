"""Imported still ranges retain their requested timeline duration."""

from __future__ import annotations

import math
import struct
from typing import Any

import pytest
import test_issue209_native as native_fixtures
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent.qualification_output_records_v2 import OutputConsistencyError


@pytest.mark.parametrize(
    ("start", "duration", "source_fps", "timeline_rate", "expected_end"),
    [
        (0, 122, "24", {"numerator": 24000, "denominator": 1001}, 123),
        (17, 148, "24.0", {"numerator": 24000, "denominator": 1001}, 166),
        (0, 100, 24.0, {"numerator": 24000, "denominator": 1001}, 101),
        (7, 122, 24, {"numerator": 24, "denominator": 1}, 129),
        (7, 100, "25", {"numerator": 24, "denominator": 1}, 112),
        (7, 100, "25", {"numerator": 25, "denominator": 1}, 107),
    ],
)
def test_still_append_converts_timeline_duration_to_source_frames(
    start: int,
    duration: int,
    source_fps: Any,
    timeline_rate: dict[str, int],
    expected_end: int,
) -> None:
    assert native._native_append_source_range(
        start, duration, source_fps, timeline_rate, still=True
    ) == (start, expected_end)


def test_non_still_append_keeps_admitted_source_span() -> None:
    assert native._native_append_source_range(
        7,
        100,
        "not a frame rate",
        {"numerator": 24000, "denominator": 1001},
        still=False,
    ) == (7, 107)


@pytest.mark.parametrize("source_fps", [None, "unknown", "0"])
def test_still_append_requires_a_positive_imported_frame_rate(
    source_fps: Any,
) -> None:
    with pytest.raises(OutputConsistencyError, match="still frame rate"):
        native._native_append_source_range(
            0,
            122,
            source_fps,
            {"numerator": 24000, "denominator": 1001},
            still=True,
        )


def _still_geometry_case(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, dict[str, Any], dict[str, Any], Any]:
    resolve, request, admitted, item, timeline = native_fixtures._geometry_case(
        tmp_path
    )
    request["profile"] = native.MATRIX_PROFILE
    admitted["manifest"]["timeline"]["durationFrames"] = 122
    admitted["view"]["timeline"]["durationFrames"] = 122
    admitted["view"]["sources"][0]["kind"] = "still"
    event = admitted["view"]["events"][0]
    event["recordRange"]["durationFrames"] = 122
    event["sourceRange"] = {"startFrame": 0, "durationFrames": 122}
    item.stamp = native._event_stamp(event)
    item.source_start_frame = item.source_end_frame = 4
    item.media.frame_count = 1
    monkeypatch.setattr(item, "GetDuration", lambda _in_frames: 122)
    monkeypatch.setattr(item, "GetEnd", lambda _in_frames: 122)
    monkeypatch.setattr(timeline, "GetEndFrame", lambda: 122)
    media_path = item.media.path
    monkeypatch.setattr(
        item.media,
        "GetClipProperty",
        lambda: {
            "Online Status": "Online",
            "File Path": str(media_path),
            "Frames": str(item.media.frame_count),
            "FPS": "24",
        },
    )
    monkeypatch.setattr(item, "GetSourceStartTime", lambda: 0.0, raising=False)
    monkeypatch.setattr(item, "GetSourceEndTime", lambda: 1 / 24, raising=False)
    return resolve, request, admitted, item


def test_still_geometry_normalizes_one_frame_hold_using_imported_fps(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolve, request, admitted, _item = _still_geometry_case(tmp_path, monkeypatch)

    geometry = native._capture_geometry(resolve, request, admitted, None)

    assert geometry["items"][0]["recordDuration"] == 122
    assert geometry["items"][0]["sourceStart"] == 0
    assert geometry["items"][0]["sourceDuration"] == 122


@pytest.mark.parametrize(
    "failure",
    ["trimmed source time", "multi-frame source", "invalid imported FPS"],
)
def test_still_geometry_rejects_unproven_source_range(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    resolve, request, admitted, item = _still_geometry_case(tmp_path, monkeypatch)
    if failure == "trimmed source time":
        monkeypatch.setattr(item, "GetSourceStartTime", lambda: 1 / 24)
        monkeypatch.setattr(item, "GetSourceEndTime", lambda: 2 / 24)
    elif failure == "multi-frame source":
        item.media.frame_count = 2
    else:
        get_properties = item.media.GetClipProperty
        monkeypatch.setattr(
            item.media,
            "GetClipProperty",
            lambda: {**get_properties(), "FPS": "0"},
        )

    with pytest.raises(OutputConsistencyError, match="native source range differs"):
        native._capture_geometry(resolve, request, admitted, None)


def test_still_geometry_rejects_media_with_different_image_bytes(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolve, request, admitted, item = _still_geometry_case(tmp_path, monkeypatch)
    item.media.path.write_bytes(b"different image bytes")

    with pytest.raises(
        OutputConsistencyError, match="native media source bytes differ"
    ):
        native._capture_geometry(resolve, request, admitted, None)


def _video_rounding_geometry_case(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, dict[str, Any], dict[str, Any], Any]:
    resolve, request, admitted, item, timeline = native_fixtures._geometry_case(
        tmp_path
    )
    request["profile"] = native.MATRIX_PROFILE
    timeline_manifest = admitted["manifest"]["timeline"]
    timeline_manifest["durationFrames"] = 63
    event = admitted["view"]["events"][0]
    event["recordRange"] = {"startFrame": 0, "durationFrames": 63}
    event["sourceRange"] = {"startFrame": 396, "durationFrames": 63}
    item.stamp = native._event_stamp(event)
    item.source_start_frame = 395
    item.source_end_frame = 459
    item.media.frame_count = 2857
    monkeypatch.setattr(item, "GetDuration", lambda _in_frames: 63)
    monkeypatch.setattr(item, "GetEnd", lambda _in_frames: 63)
    monkeypatch.setattr(timeline, "GetEndFrame", lambda: 63)
    monkeypatch.setattr(
        item, "GetSourceStartTime", lambda: 16.516499999999997, raising=False
    )
    monkeypatch.setattr(
        item, "GetSourceEndTime", lambda: 19.144124999999995, raising=False
    )

    frame_rate = {"numerator": 24000, "denominator": 1001}
    probe_hash = "sha256:" + "b" * 64
    frame_map = {
        "decodedPackageFrameCount": 2857,
        "decodedPackageFrameRate": frame_rate,
        "descriptorHash": probe_hash,
        "loggedTimeAtPackageFrameZero": {"numerator": 0, "denominator": 1},
        "packageFrameZeroLogicalFrame": 0,
        "packageVideoPtsOrigin": {"numerator": 0, "denominator": 1},
        "packageVideoTimeBase": {"numerator": 1, "denominator": 24000},
        "probeHash": probe_hash,
        "sourceAudioStreamMappings": [],
    }
    mapping = {
        "deliveredOrigin": {"numerator": 0, "denominator": 1},
        "deliveredRate": frame_rate,
        "mappingHash": "sha256:" + "c" * 64,
        "sourceFrameMap": frame_map,
        "sourceOrigin": {"numerator": 0, "denominator": 1},
        "sourceRate": frame_rate,
    }
    event["v2Event"]["sourceRange"] = {"startFrame": 396, "endFrame": 459}
    event["v2Event"]["sourceTimeMapping"] = mapping
    item.stamp = native._event_stamp(event)

    source = admitted["view"]["sources"][0]
    requirement_key = "prepared-mov"
    admitted["manifest"]["events"] = [
        {
            "eventId": event["id"],
            "sourceRange": {"startFrame": 396, "endFrame": 459},
            "sourceTimeMapping": mapping,
        }
    ]
    admitted["manifest"]["sources"] = [
        {
            "id": source["id"],
            "deliveredHash": source["contentHash"],
            "deliveredProbeHash": probe_hash,
            "preparationRequirementKey": requirement_key,
            "sourceFrameMap": frame_map,
            "sourceTimeMapping": mapping,
        }
    ]
    admitted["manifest"]["preparationBindings"] = [
        {
            "requirementKey": requirement_key,
            "verification": {
                "decodedFrameCount": 2857,
                "decodedFrameRate": frame_rate,
                "deliveredHash": source["contentHash"],
                "probeHash": probe_hash,
            },
        }
    ]
    return resolve, request, admitted, item


def test_video_geometry_normalizes_authenticated_one_frame_start_getter_floor(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolve, request, admitted, _item = _video_rounding_geometry_case(
        tmp_path, monkeypatch
    )

    geometry = native._capture_geometry(resolve, request, admitted, None)

    assert geometry["items"][0]["sourceStart"] == 396
    assert geometry["items"][0]["sourceDuration"] == 63


def test_observed_geometry_normalizes_authenticated_unchanged_cfr_getter_floor(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolve, request, admitted, _item = _video_rounding_geometry_case(
        tmp_path, monkeypatch
    )
    request["context"]["phase"] = "edited"

    geometry = native._capture_observed_geometry(resolve, request, admitted, None)

    assert geometry["items"][0]["sourceStart"] == 396
    assert geometry["items"][0]["sourceDuration"] == 63


def test_observed_geometry_still_refuses_a_genuine_cfr_source_start_change(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolve, request, admitted, item = _video_rounding_geometry_case(
        tmp_path, monkeypatch
    )
    request["context"]["phase"] = "edited"
    monkeypatch.setattr(
        item, "GetSourceStartTime", lambda: 395 * 1001 / 24000, raising=False
    )

    with pytest.raises(
        OutputConsistencyError,
        match="native edited item differs outside the observed edit rules",
    ):
        native._capture_observed_geometry(resolve, request, admitted, None)


def _trimmed_cfr_geometry_case(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    resolve, request, admitted, video = _video_rounding_geometry_case(
        tmp_path, monkeypatch
    )
    request["context"]["phase"] = "edited"
    admitted["manifest"]["timeline"]["durationFrames"] = 73
    admitted["view"]["timeline"]["durationFrames"] = 73
    video.source_end_frame = 456
    monkeypatch.setattr(video, "GetDuration", lambda _in_frames: 60)
    monkeypatch.setattr(video, "GetEnd", lambda _in_frames: 60)
    monkeypatch.setattr(
        video, "GetSourceEndTime", lambda: 456 * 1001 / 24000, raising=False
    )

    source = admitted["view"]["sources"][0]
    audio_path = admitted["sourceRoot"] / "media/audio.wav"
    audio_path.write_bytes(video.media.path.read_bytes())
    admitted["view"]["sources"].append(
        {
            **source,
            "id": "audio-source",
            "kind": "audio",
            "path": "media/audio.wav",
        }
    )
    audio_event = {
        "id": "audio-event",
        "kind": "source_audio",
        "trackId": "audio-main",
        "trackKind": "audio",
        "sourceId": "audio-source",
        "gainDb": -0.1,
        "recordRange": {"startFrame": 0, "durationFrames": 63},
        "sourceRange": {"startFrame": 396, "durationFrames": 63},
        "v2Event": {"id": "audio-event", "description": "linked audio"},
    }
    audio = native_fixtures._Item(
        native_fixtures._Media(audio_path), native._event_stamp(audio_event)
    )
    audio.source_start_frame = 396
    audio.source_end_frame = 455
    audio.properties["AudioVolume"] = -0.1
    monkeypatch.setattr(audio, "GetStart", lambda _in_frames: 0)
    monkeypatch.setattr(audio, "GetDuration", lambda _in_frames: 60)
    monkeypatch.setattr(audio, "GetEnd", lambda _in_frames: 60)
    monkeypatch.setattr(
        audio, "GetSourceStartTime", lambda: 396 * 1001 / 24000, raising=False
    )
    monkeypatch.setattr(
        audio, "GetSourceEndTime", lambda: 456 * 1001 / 24000, raising=False
    )

    downstream_event = {
        "id": "downstream-event",
        "kind": "primary_visual",
        "trackId": "video-main",
        "trackKind": "video",
        "sourceId": source["id"],
        "recordRange": {"startFrame": 63, "durationFrames": 10},
        "sourceRange": {"startFrame": 100, "durationFrames": 10},
        "v2Event": {"id": "downstream-event", "description": "ripple item"},
    }
    downstream = native_fixtures._Item(
        video.media, native._event_stamp(downstream_event)
    )
    downstream.true_start = 60
    downstream.source_start_frame = 100
    downstream.source_end_frame = 110
    monkeypatch.setattr(downstream, "GetUniqueId", lambda: "timeline-item-downstream")

    video.GetLinkedItems = lambda: [audio]
    audio.GetUniqueId = lambda: "timeline-item-audio"  # type: ignore[method-assign]
    audio.GetLinkedItems = lambda: [video]  # type: ignore[method-assign]
    downstream.GetLinkedItems = lambda: []  # type: ignore[method-assign]
    admitted["view"]["events"].extend([audio_event, downstream_event])
    admitted["view"]["tracks"].append(
        {"id": "audio-main", "kind": "audio", "index": 1, "name": "A1"}
    )

    timeline = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
    tracks = {"video": [video, downstream], "audio": [audio]}
    monkeypatch.setattr(timeline, "GetTrackCount", lambda kind: int(kind in tracks))
    monkeypatch.setattr(
        timeline,
        "GetTrackName",
        lambda kind, index: {"video": "V1", "audio": "A1"}[kind],
    )
    monkeypatch.setattr(
        timeline,
        "GetItemListInTrack",
        lambda kind, index: tracks[kind],
    )
    monkeypatch.setattr(timeline, "GetIsTrackEnabled", lambda _kind, _index: True)
    monkeypatch.setattr(timeline, "GetIsTrackLocked", lambda _kind, _index: False)
    monkeypatch.setattr(timeline, "GetEndFrame", lambda: 70)
    return resolve, request, admitted


def test_observed_geometry_accepts_authenticated_cfr_floor_with_linked_end_trim(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolve, request, admitted = _trimmed_cfr_geometry_case(tmp_path, monkeypatch)

    geometry = native._capture_observed_geometry(resolve, request, admitted, None)

    video = next(item for item in geometry["items"] if item["eventId"] == "event-one")
    assert video["sourceStart"] == 396
    assert video["sourceDuration"] == 60
    assert geometry["extentFrames"] == 70


@pytest.mark.parametrize(
    ("expected", "actual", "matches"),
    [
        (-0.1, -0.1, True),
        (
            -0.1,
            struct.unpack("!f", struct.pack("!f", -0.1))[0],
            True,
        ),
        (-0.1, -0.10000001, False),
        (-0.1, True, False),
        (-0.1, math.nan, False),
        (-0.1, math.inf, False),
        (True, -0.1, False),
    ],
)
def test_native_audio_gain_readback_accepts_only_exact_or_float32_value(
    expected: Any, actual: Any, matches: bool
) -> None:
    assert native._native_audio_gain_readback_matches(expected, actual) is matches


def test_geometry_reopens_approved_gain_after_float32_readback(
    tmp_path: Any,
) -> None:
    resolve, request, admitted, item, _timeline = native_fixtures._geometry_case(
        tmp_path, source_audio=True
    )
    event = admitted["view"]["events"][0]
    event["gainDb"] = -0.1
    item.stamp = native._event_stamp(event)
    item.properties["AudioVolume"] = struct.unpack("!f", struct.pack("!f", -0.1))[0]

    geometry = native._capture_geometry(resolve, request, admitted, None)

    assert geometry["items"][0]["eventId"] == event["id"]


@pytest.mark.parametrize(
    "failure",
    [
        "trimmed in-point",
        "trimmed out-point",
        "multi-frame offset",
        "frame count mismatch",
        "probe mismatch",
    ],
)
def test_video_geometry_rejects_unproven_one_frame_start_getter_floor(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    resolve, request, admitted, item = _video_rounding_geometry_case(
        tmp_path, monkeypatch
    )
    if failure == "trimmed in-point":
        monkeypatch.setattr(item, "GetSourceStartTime", lambda: 395 * 1001 / 24000)
    elif failure == "trimmed out-point":
        item.source_end_frame = 458
        monkeypatch.setattr(item, "GetSourceEndTime", lambda: 458 * 1001 / 24000)
    elif failure == "multi-frame offset":
        item.source_start_frame = 394
    elif failure == "frame count mismatch":
        item.media.frame_count = 2856
    else:
        admitted["manifest"]["preparationBindings"][0]["verification"]["probeHash"] = (
            "sha256:" + "d" * 64
        )

    with pytest.raises(OutputConsistencyError, match="native source range differs"):
        native._capture_geometry(resolve, request, admitted, None)


def test_video_geometry_rejects_source_bytes_outside_admitted_hash(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolve, request, admitted, item = _video_rounding_geometry_case(
        tmp_path, monkeypatch
    )
    item.media.path.write_bytes(b"different movie bytes")

    with pytest.raises(
        OutputConsistencyError, match="native media source bytes differ"
    ):
        native._capture_geometry(resolve, request, admitted, None)


def test_video_geometry_accepts_resolve_one_ulp_duration_readback(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolve, request, admitted, item = _video_rounding_geometry_case(
        tmp_path, monkeypatch
    )
    monkeypatch.setattr(
        item,
        "GetDuration",
        lambda in_frames: 62.99999999999999 if in_frames else 63,
    )

    geometry = native._capture_geometry(resolve, request, admitted, None)

    assert geometry["items"][0]["recordDuration"] == 63


def test_record_frame_getter_accepts_at_most_one_finite_float_ulp() -> None:
    expected = 63
    one_ulp_below = math.nextafter(float(expected), -math.inf)
    two_ulps_below = math.nextafter(one_ulp_below, -math.inf)

    assert native._native_record_frame_getter_matches(expected, one_ulp_below)
    for value in (two_ulps_below, 63.5, math.nan, math.inf, -math.inf, True):
        assert not native._native_record_frame_getter_matches(expected, value)


@pytest.mark.parametrize(
    ("method", "frame_value"),
    [
        ("GetStart", 0.5),
        ("GetDuration", 10.5),
        ("GetEnd", 10.5),
    ],
)
def test_fractional_record_getter_refusal_reports_exact_geometry(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    frame_value: float,
) -> None:
    resolve, request, admitted, item, _timeline = native_fixtures._geometry_case(
        tmp_path
    )
    original_getter = getattr(item, method)
    monkeypatch.setattr(
        item,
        method,
        lambda in_frames, original=original_getter, value=frame_value: (
            value if in_frames else original(False)
        ),
    )

    with pytest.raises(
        OutputConsistencyError,
        match="unsupported fractional native record geometry",
    ) as error:
        native._capture_geometry(resolve, request, admitted, None)

    message = str(error.value)
    assert "track=video:1" in message
    assert "itemUid=timeline-item-one" in message
    assert "eventId=event-one" in message
    assert (
        "recordGetters={'GetStart(False)': 0, 'GetDuration(False)': 10, "
        "'GetEnd(False)': 10}"
    ) in message
    assert f"'{method}': {frame_value}" in message
