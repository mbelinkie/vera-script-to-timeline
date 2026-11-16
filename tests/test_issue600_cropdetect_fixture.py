from __future__ import annotations

import shutil
from itertools import pairwise

import pytest
from issue600_cropdetect_fixture import (
    OVERRIDE_CONTROL,
    generate_issue600_cropdetect_fixtures,
)
from vera_timeline_agent.cropdetect import CropRect, analyze_media


@pytest.mark.slow
def test_ffmpeg_sampler_accepts_only_stable_symmetric_bars_without_mutating_media(
    tmp_path,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg is required for synthetic cropdetect fixtures")

    paths = generate_issue600_cropdetect_fixtures(tmp_path, ffmpeg)
    before = paths["letterbox"].read_bytes()
    detections = {
        name: analyze_media(path, (0.2, 1.8), ffmpeg=ffmpeg)
        for name, path in paths.items()
    }

    assert detections["letterbox"].source_size == (320, 180)
    assert detections["letterbox"].active_rect == CropRect(0, 20, 320, 140)
    assert detections["pillarbox"].active_rect == CropRect(24, 0, 272, 180)
    assert detections["asymmetric"].active_rect is None
    assert detections["near_black"].active_rect is None
    assert detections["changing"].active_rect is None
    assert detections["dark_title"].active_rect is None

    for detection in detections.values():
        assert len(detection.samples) == 3
        assert all(
            sample.frame_count is not None and sample.frame_count >= 2
            for sample in detection.samples
        )
        assert all(
            sample.start_seconds is not None
            and sample.end_seconds is not None
            and 0.2 <= sample.start_seconds < sample.end_seconds <= 1.8
            for sample in detection.samples
        )
        assert all(
            left.end_seconds <= right.start_seconds
            for left, right in pairwise(detection.samples)
        )

    assert detections["letterbox"].accepted
    assert (
        detections["asymmetric"].refusal_reason == "unstable_or_ambiguous_crop_evidence"
    )
    assert detections["near_black"].refusal_reason == "no_bars_detected"
    assert paths["letterbox"].read_bytes() == before
    assert OVERRIDE_CONTROL["source_fixture"] == "letterbox"
    assert OVERRIDE_CONTROL["expected_action"] == "preserve-explicit-framing"
