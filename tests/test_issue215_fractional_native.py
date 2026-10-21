"""Fractional generated-narration EOF readback checks."""

from __future__ import annotations

import hashlib
import wave
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import test_issue209_native as fixtures
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent.qualification_output_records_v2 import OutputConsistencyError

SAMPLE_COUNT = 262_200
SAMPLE_RATE = 48_000
FRAME_COUNT = 131


def _fractional_narration_case(
    tmp_path: Path, phase: str = "pristine"
) -> tuple[Any, dict[str, Any], dict[str, Any], Any]:
    resolve, request, admitted, item, timeline = fixtures._geometry_case(
        tmp_path, source_audio=True
    )
    source = admitted["view"]["sources"][0]
    source["kind"] = "audio"
    source["path"] = "media/narration.wav"
    source_path = admitted["sourceRoot"] / source["path"]
    source_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(source_path), "wb") as audio_file:
        audio_file.setnchannels(1)
        audio_file.setsampwidth(2)
        audio_file.setframerate(SAMPLE_RATE)
        audio_file.writeframes(b"\0\0" * SAMPLE_COUNT)
    audio_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    source["contentHash"] = audio_hash
    item.media.path = source_path

    event = admitted["view"]["events"][0]
    event["kind"] = "narration"
    event.pop("gainDb", None)
    event["recordRange"] = {"startFrame": 0, "durationFrames": FRAME_COUNT}
    event["sourceRange"] = None
    event["v2Event"] = {
        "id": event["id"],
        "description": "fractional narration EOF",
    }
    item.stamp = native._event_stamp(event)
    item.source_start_frame = 0
    item.source_end_frame = FRAME_COUNT - 2
    item.__dict__.update(
        {
            "GetDuration": lambda _in_frames: FRAME_COUNT,
            "GetEnd": lambda _in_frames: FRAME_COUNT,
            "GetSourceStartTime": lambda: 0.0,
            "GetSourceEndTime": lambda: SAMPLE_COUNT / SAMPLE_RATE,
        }
    )
    timeline.__dict__["GetEndFrame"] = lambda: FRAME_COUNT
    admitted["manifest"]["timeline"]["durationFrames"] = FRAME_COUNT
    admitted["manifest"]["sources"] = [
        {
            "id": source["id"],
            "narrationAudio": {
                "audioHash": f"sha256:{audio_hash}",
                "durationSamples": SAMPLE_COUNT,
                "sampleRate": SAMPLE_RATE,
            },
        }
    ]
    request["profile"] = native.MATRIX_PROFILE
    request["context"]["phase"] = phase
    return resolve, request, admitted, item


def _one_sample_tail_eof(item: Any, admitted: dict[str, Any]) -> None:
    sample_count = (FRAME_COUNT - 1) * 2002 + 1
    media_path = item.media.path
    with wave.open(str(media_path), "wb") as audio_file:
        audio_file.setnchannels(1)
        audio_file.setsampwidth(2)
        audio_file.setframerate(SAMPLE_RATE)
        audio_file.writeframes(b"\0\0" * sample_count)
    audio_hash = hashlib.sha256(media_path.read_bytes()).hexdigest()
    admitted["view"]["sources"][0]["contentHash"] = audio_hash
    narration_audio = admitted["manifest"]["sources"][0]["narrationAudio"]
    narration_audio["audioHash"] = f"sha256:{audio_hash}"
    narration_audio["durationSamples"] = sample_count
    item.__dict__["GetSourceEndTime"] = lambda: (sample_count - 1) / SAMPLE_RATE


@pytest.mark.parametrize("phase", ["pristine", "rebuild"])
def test_unobserved_fractional_narration_uses_verified_sample_eof(
    tmp_path: Path, phase: str
) -> None:
    resolve, request, admitted, item = _fractional_narration_case(tmp_path, phase)

    geometry = native._capture_geometry(resolve, request, admitted, None)

    assert item.GetSourceStartFrame() == 0
    assert item.GetSourceEndFrame() == FRAME_COUNT - 2
    assert item.__dict__["GetSourceStartTime"]() == 0.0
    assert item.__dict__["GetSourceEndTime"]() == SAMPLE_COUNT / SAMPLE_RATE
    assert (
        geometry["items"][0]["sourceStart"],
        geometry["items"][0]["sourceDuration"],
    ) == (0, FRAME_COUNT)


def test_observed_untouched_fractional_narration_uses_verified_sample_eof(
    tmp_path: Path,
) -> None:
    resolve, request, admitted, item = _fractional_narration_case(tmp_path, "edited")

    geometry = native._capture_observed_geometry(resolve, request, admitted, None)

    assert item.GetSourceEndFrame() == FRAME_COUNT - 2
    assert item.__dict__["GetSourceEndTime"]() == SAMPLE_COUNT / SAMPLE_RATE
    assert geometry["items"][0]["sourceDuration"] == FRAME_COUNT


def test_observed_fractional_narration_accepts_split_right_segment_at_eof(
    tmp_path: Path,
) -> None:
    resolve, request, admitted, right = _fractional_narration_case(tmp_path, "edited")
    timeline = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
    left = type(right)(right.media, right.stamp)
    left.source_start_frame, left.source_end_frame = 0, 69
    left.__dict__.update(
        {
            "GetDuration": lambda _in_frames: 70,
            "GetEnd": lambda _in_frames: 70,
            "GetSourceStartTime": lambda: 0.0,
            "GetSourceEndTime": lambda: float(Fraction(70 * 1001, 24000)),
        }
    )
    right.true_start = 72
    right.source_start_frame, right.source_end_frame = 72, FRAME_COUNT - 2
    right.__dict__.update(
        {
            "GetDuration": lambda _in_frames: 59,
            "GetEnd": lambda _in_frames: FRAME_COUNT,
            "GetSourceStartTime": lambda: float(Fraction(72 * 1001, 24000)),
            "GetUniqueId": lambda: "timeline-item-two",
        }
    )
    timeline.__dict__["GetItemListInTrack"] = lambda _kind, _index: [left, right]

    geometry = native._capture_observed_geometry(resolve, request, admitted, None)

    assert [row["sourceDuration"] for row in geometry["items"]] == [70, 59]


def test_fractional_narration_rejects_inexact_native_eof(
    tmp_path: Path,
) -> None:
    resolve, request, admitted, item = _fractional_narration_case(tmp_path)
    item.__dict__["GetSourceEndTime"] = lambda: (SAMPLE_COUNT + 2) / SAMPLE_RATE

    with pytest.raises(OutputConsistencyError, match="native source range differs"):
        native._capture_geometry(resolve, request, admitted, None)


def test_fractional_narration_rejects_inexact_native_start(
    tmp_path: Path,
) -> None:
    resolve, request, admitted, item = _fractional_narration_case(tmp_path)
    item.__dict__["GetSourceStartTime"] = lambda: 2 / SAMPLE_RATE

    with pytest.raises(OutputConsistencyError, match="native source range differs"):
        native._capture_geometry(resolve, request, admitted, None)


def test_fractional_narration_rejects_unbound_sample_metadata(
    tmp_path: Path,
) -> None:
    resolve, request, admitted, _item = _fractional_narration_case(tmp_path)
    admitted["manifest"]["sources"][0]["narrationAudio"]["audioHash"] = (
        "sha256:" + "0" * 64
    )

    with pytest.raises(OutputConsistencyError, match="native source range differs"):
        native._capture_geometry(resolve, request, admitted, None)


def test_fractional_narration_rejects_larger_frame_underflow(
    tmp_path: Path,
) -> None:
    resolve, request, admitted, item = _fractional_narration_case(tmp_path)
    item.source_end_frame = FRAME_COUNT - 3

    with pytest.raises(OutputConsistencyError, match="native source range differs"):
        native._capture_geometry(resolve, request, admitted, None)


def test_source_audio_does_not_use_narration_eof_rule(
    tmp_path: Path,
) -> None:
    resolve, request, admitted, item = _fractional_narration_case(tmp_path)
    event = admitted["view"]["events"][0]
    event["kind"] = "source_audio"
    event["gainDb"] = -6.0
    item.stamp = native._event_stamp(event)

    with pytest.raises(OutputConsistencyError, match="native source range differs"):
        native._capture_geometry(resolve, request, admitted, None)


def test_fractional_narration_eof_rule_does_not_cover_edited_split(
    tmp_path: Path,
) -> None:
    resolve, request, admitted, item = _fractional_narration_case(tmp_path)
    request["context"]["phase"] = "edited"
    event = admitted["view"]["events"][0]
    event["sourceRange"] = {"startFrame": 0, "durationFrames": FRAME_COUNT}
    item.stamp = native._event_stamp(event)

    with pytest.raises(OutputConsistencyError, match="native source range differs"):
        native._capture_geometry(resolve, request, admitted, None)


@pytest.mark.parametrize("drift", ["partial", "eof"])
def test_observed_fractional_narration_rejects_partial_or_drifting_ends(
    tmp_path: Path, drift: str
) -> None:
    resolve, request, admitted, item = _fractional_narration_case(tmp_path, "edited")
    if drift == "partial":
        item.source_end_frame = FRAME_COUNT - 3
    else:
        item.__dict__["GetSourceEndTime"] = lambda: (SAMPLE_COUNT + 2) / SAMPLE_RATE

    with pytest.raises(OutputConsistencyError):
        native._capture_observed_geometry(resolve, request, admitted, None)


def test_observed_source_audio_does_not_use_narration_eof_rule(
    tmp_path: Path,
) -> None:
    resolve, request, admitted, item = _fractional_narration_case(tmp_path, "edited")
    event = admitted["view"]["events"][0]
    event["kind"] = "source_audio"
    event["gainDb"] = -6.0
    item.stamp = native._event_stamp(event)

    with pytest.raises(OutputConsistencyError):
        native._capture_observed_geometry(resolve, request, admitted, None)


def test_observed_one_sample_eof_tail_does_not_normalize_a_trimmed_row(
    tmp_path: Path,
) -> None:
    resolve, request, admitted, item = _fractional_narration_case(tmp_path, "edited")
    _one_sample_tail_eof(item, admitted)
    item.__dict__["GetDuration"] = lambda _in_frames: FRAME_COUNT - 1
    item.__dict__["GetEnd"] = lambda _in_frames: FRAME_COUNT - 1
    timeline = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
    timeline.__dict__["GetEndFrame"] = lambda: FRAME_COUNT - 1

    with pytest.raises(
        OutputConsistencyError,
        match="native edited item differs outside the observed edit rules",
    ):
        native._capture_observed_geometry(resolve, request, admitted, None)


def test_observed_one_sample_eof_tail_does_not_normalize_trimmed_split_right(
    tmp_path: Path,
) -> None:
    resolve, request, admitted, right = _fractional_narration_case(tmp_path, "edited")
    _one_sample_tail_eof(right, admitted)
    timeline = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
    left = type(right)(right.media, right.stamp)
    left.source_start_frame, left.source_end_frame = 0, 69
    left.__dict__.update(
        {
            "GetDuration": lambda _in_frames: 70,
            "GetEnd": lambda _in_frames: 70,
            "GetSourceStartTime": lambda: 0.0,
            "GetSourceEndTime": lambda: float(Fraction(70 * 1001, 24000)),
        }
    )
    right.true_start = 72
    right.source_start_frame, right.source_end_frame = 72, FRAME_COUNT - 2
    right.__dict__.update(
        {
            "GetDuration": lambda _in_frames: FRAME_COUNT - 72 - 1,
            "GetEnd": lambda _in_frames: FRAME_COUNT - 1,
            "GetSourceStartTime": lambda: float(Fraction(72 * 1001, 24000)),
            "GetUniqueId": lambda: "timeline-item-two",
        }
    )
    timeline.__dict__["GetItemListInTrack"] = lambda _kind, _index: [left, right]
    timeline.__dict__["GetEndFrame"] = lambda: FRAME_COUNT - 1

    with pytest.raises(
        OutputConsistencyError,
        match="narration split does not map two unique segments around one omission",
    ):
        native._capture_observed_geometry(resolve, request, admitted, None)
