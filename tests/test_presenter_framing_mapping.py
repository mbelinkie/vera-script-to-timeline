from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import vera_timeline_agent.review_proxy as review_proxy
from vera_timeline_agent.build_jobs import BuildJobStore
from vera_timeline_agent.media_preparation import (
    MediaInspection,
    MediaTools,
    file_hash,
)
from vera_timeline_agent.narration.models import identity_hash
from vera_timeline_agent.presenter_framing import ValidatedSourceTimeInterval
from vera_timeline_agent.presenter_framing_mapping import (
    PresenterFramingMappingError,
    map_review_frame_interval,
)
from vera_timeline_agent.review_ingest import (
    RegisteredMaster,
    ReviewIngestAdapter,
)
from vera_timeline_agent.review_proxy import ReviewProfile, ReviewProxyError


class FixtureMediaTools(MediaTools):
    ffmpeg = "fixture-ffmpeg"
    ffprobe = "fixture-ffprobe"

    def fingerprint(self) -> dict[str, Any]:
        return {"fixture": "review-media-tools/v1"}

    def run(self, command: list[str], *, timeout: float = 600) -> bytes:
        del timeout
        self.check_cancel()
        if "-show_streams" in command:
            return json.dumps(
                {"streams": [{"index": 0, "codec_type": "video"}]}
            ).encode()
        if command[0] == self.ffmpeg:
            Path(command[-1]).write_bytes(b"synthetic proxy bytes")
        return b"{}"


def _inspection(
    path: Path,
    *,
    origin: Fraction,
    profile: str,
    width: int,
    height: int,
    frame_count: int = 8,
) -> MediaInspection:
    rate = Fraction(25)
    time_base = Fraction(1, 1000)
    first_pts = int(origin / time_base)
    frames = [
        {
            "stream_index": 0,
            "pts": first_pts + index * 40,
            "duration": 40,
            "width": width,
            "height": height,
            "pix_fmt": "yuv420p",
            "sample_aspect_ratio": "1:1",
            "interlaced_frame": 0,
        }
        for index in range(frame_count)
    ]
    video: dict[str, Any] = {
        "index": 0,
        "codec_type": "video",
        "codec_name": "h264",
        "profile": profile,
        "pix_fmt": "yuv420p",
        "field_order": "progressive",
        "sample_aspect_ratio": "1:1",
        "width": width,
        "height": height,
        "avg_frame_rate": "25/1",
        "r_frame_rate": "25/1",
        "time_base": "1/1000",
        "color_range": "tv",
        "color_space": "bt709",
        "color_primaries": "bt709",
        "color_transfer": "bt709",
        "bit_rate": "1000000",
    }
    probe: dict[str, Any] = {
        "streams": [video],
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "tags": {"major_brand": "isom"},
            "bit_rate": "1000000",
            "duration": str(Fraction(frame_count, 1) / rate),
        },
        "frames": frames,
    }
    return MediaInspection(
        probe=probe,
        probe_hash=identity_hash(probe),
        content_hash=file_hash(path),
        video=video,
        video_frames=frames,
        rate=rate,
        time_base=time_base,
        pts_origin=origin,
        audio=None,
        audio_frames=[],
        audio_origin=None,
        audio_samples=0,
        audio_hash=None,
        audio_timestamp_residual=Fraction(0),
        audio_timestamp_drift=Fraction(0),
    )


def _completed_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    profile: ReviewProfile,
    master_dimensions: tuple[int, int] = (1920, 1080),
) -> tuple[ReviewIngestAdapter, str, Path, str]:
    master = tmp_path / "registered-master.mp4"
    master.write_bytes(b"synthetic master bytes")
    content_hash = file_hash(master)
    source_width, source_height = master_dimensions

    def inspect_fixture(
        path: Path,
        *,
        video_stream_index: int,
        audio_stream_index: int | None,
        tools: MediaTools,
    ) -> MediaInspection:
        del video_stream_index, audio_stream_index, tools
        if path.resolve() == master.resolve():
            return _inspection(
                path,
                origin=Fraction(3),
                profile="High",
                width=source_width,
                height=source_height,
            )
        return _inspection(
            path,
            origin=Fraction(0),
            profile="Baseline",
            width=min(source_width, 1280),
            height=min(source_height, 720),
        )

    monkeypatch.setattr(review_proxy, "inspect_media", inspect_fixture)
    store = BuildJobStore(tmp_path / "jobs")
    adapter = ReviewIngestAdapter(
        store,
        cache_root=tmp_path / "review-cache",
        resolve_master=lambda project_id, source_id: RegisteredMaster(
            project_id,
            source_id,
            master,
            content_hash,
            video_stream_index=0,
        ),
        profile=profile,
        tools=FixtureMediaTools(),
    )
    job_id = adapter.submit_ingest("project-a", "source-a", "fixture-ingest")
    for _ in range(3):
        assert store.run_one("project-a", job_id, "fixture-worker", adapter)
    return adapter, job_id, master, content_hash


def test_review_interval_uses_verified_frame_map_and_registered_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter, job_id, _, content_hash = _completed_adapter(
        tmp_path, monkeypatch, profile=ReviewProfile(mode="always")
    )

    result = map_review_frame_interval(
        adapter,
        "project-a",
        job_id,
        ValidatedSourceTimeInterval(2, 5),
        expected_source_id="source-a",
        expected_source_content_hash=content_hash,
    )

    assert result.source_interval == ValidatedSourceTimeInterval(2, 5)
    assert result.mapping_evidence["videoSource"] == "proxy"
    assert result.mapping_evidence["mappingHash"]
    assert result.mapping_evidence["sourceId"] == "source-a"
    assert result.mapping_evidence["sourceContentHash"] == content_hash
    assert result.mapping_evidence["frameRange"] == {
        "startInclusive": 2,
        "endExclusive": 5,
    }
    assert result.mapping_evidence["startBoundary"]["sourceFrameIndex"] == 2
    assert result.mapping_evidence["endBoundary"]["sourceFrameIndex"] == 5
    assert result.mapping_evidence["startBoundary"]["sourcePtsSeconds"] == {
        "numerator": 77,
        "denominator": 25,
    }
    assert result.mapping_evidence["endBoundary"]["sourcePtsSeconds"] == {
        "numerator": 16,
        "denominator": 5,
    }


def test_review_interval_does_not_invent_proxy_hash_for_master_playback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter, job_id, _, content_hash = _completed_adapter(
        tmp_path,
        monkeypatch,
        profile=ReviewProfile(mode="never"),
        master_dimensions=(640, 360),
    )

    result = map_review_frame_interval(
        adapter,
        "project-a",
        job_id,
        ValidatedSourceTimeInterval(1, 3),
        expected_source_id="source-a",
        expected_source_content_hash=content_hash,
    )

    assert result.source_interval == ValidatedSourceTimeInterval(1, 3)
    assert result.mapping_evidence["videoSource"] == "master"
    assert result.mapping_evidence["mappingHash"] is None


def test_mismatched_registered_source_is_rejected_after_verified_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter, job_id, _, content_hash = _completed_adapter(
        tmp_path, monkeypatch, profile=ReviewProfile(mode="always")
    )

    with pytest.raises(PresenterFramingMappingError, match="another source"):
        map_review_frame_interval(
            adapter,
            "project-a",
            job_id,
            ValidatedSourceTimeInterval(2, 5),
            expected_source_id="source-b",
            expected_source_content_hash=content_hash,
        )


def test_corrupt_proxy_receipt_is_refused_before_interval_is_returned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter, job_id, _, content_hash = _completed_adapter(
        tmp_path, monkeypatch, profile=ReviewProfile(mode="always")
    )
    handoff = adapter.verified_handoff("project-a", job_id)
    assert handoff.proxy_path is not None
    handoff.proxy_path.write_bytes(b"tampered synthetic proxy")

    with pytest.raises(ReviewProxyError, match="corrupt"):
        map_review_frame_interval(
            adapter,
            "project-a",
            job_id,
            ValidatedSourceTimeInterval(2, 5),
            expected_source_id="source-a",
            expected_source_content_hash=content_hash,
        )
