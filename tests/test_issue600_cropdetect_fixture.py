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
def test_ffmpeg_whole_range_evidence_rejects_ambiguous_or_unsafe_frames(
    tmp_path,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("ffmpeg and ffprobe are required for synthetic cropdetect fixtures")

    paths = generate_issue600_cropdetect_fixtures(tmp_path, ffmpeg)
    before = paths["letterbox"].read_bytes()
    detections = {
        name: analyze_media(
            path,
            (1.0, 5.0) if name == "outside_range" else (0.0, 4.0),
            timeline_size=(320, 180),
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
        )
        for name, path in paths.items()
    }

    assert detections["letterbox"].active_rect == CropRect(0, 22, 320, 134)
    assert detections["letterbox"].zoom == 1.3637
    assert detections["pillarbox"].active_rect == CropRect(40, 0, 240, 180)
    assert detections["pillarbox"].zoom == 1.3334
    assert detections["odd_bars"].active_rect == CropRect(0, 20, 320, 138)
    assert detections["pc_letterbox"].active_rect == CropRect(0, 22, 320, 134)
    assert detections["pc_letterbox"].color_range == "pc"
    assert detections["outside_range"].active_rect == CropRect(0, 22, 320, 134)

    expected_refusals = {
        "asymmetric": "invalid_geometry",
        "near_black": "insufficient_evidence",
        "changing": "changing",
        "dark_title": "invalid_geometry",
        "noisy_bars": "not_flat_black",
        "subtitle": "changing",
        "fade": "insufficient_evidence",
        "portrait": "zoom_exceeds_limit",
        "offset_pts": "range_clock_mismatch",
    }
    for name, reason in expected_refusals.items():
        assert detections[name].active_rect is None, name
        assert detections[name].refusal_reason == reason, name

    for name, detection in detections.items():
        if detection.refusal_reason in {
            "insufficient_evidence",
            "range_clock_mismatch",
        }:
            continue
        assert len(detection.samples) >= 12, name
        assert detection.sample_stride == 2, name
        assert all(
            left.pts_seconds < right.pts_seconds
            for left, right in pairwise(detection.samples)
        )
    assert detections["outside_range"].used_range == (1.0, 5.0)
    assert paths["letterbox"].read_bytes() == before
    assert OVERRIDE_CONTROL["source_fixture"] == "letterbox"
    assert OVERRIDE_CONTROL["expected_action"] == "preserve-explicit-framing"
