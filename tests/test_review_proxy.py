from __future__ import annotations

import json
import wave
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest
import vera_timeline_agent.review_proxy as review_proxy
from vera_timeline_agent.media_preparation import MediaInspection, MediaTools, file_hash
from vera_timeline_agent.narration.models import identity_hash
from vera_timeline_agent.review_proxy import (
    ReviewProfile,
    ReviewProxyError,
    inspect_review_source,
    profile_decision,
    run_review_stage,
    verify_review_stage,
)


class _FakeTools:
    ffmpeg = "fixture-ffmpeg"
    ffprobe = "fixture-ffprobe"

    def __init__(self, *, audio: bool = False, audio_frames: int = 2400) -> None:
        self.audio = audio
        self.audio_frames = audio_frames
        self.version = "v1"
        self.proxy_calls = 0
        self.commands: list[list[str]] = []

    def fingerprint(self) -> dict[str, Any]:
        return {"fixtureTool": "ffmpeg/ffprobe-v1", "version": self.version}

    def run(self, command: list[str], *, timeout: float = 600) -> bytes:
        del timeout
        self.commands.append(command)
        if "-show_streams" in command:
            streams: list[dict[str, Any]] = [{"index": 0, "codec_type": "video"}]
            if self.audio:
                streams.append({"index": 1, "codec_type": "audio"})
            return json.dumps({"streams": streams}).encode()
        if command[0] == self.ffmpeg:
            output = Path(command[-1])
            if "wav" in command:
                self._write_wav(output)
            else:
                self.proxy_calls += 1
                output.write_bytes(f"synthetic-proxy-{self.proxy_calls}".encode())
        return b""

    def _write_wav(self, path: Path) -> None:
        with wave.open(str(path), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(48000)
            writer.writeframes(b"\xe8\x03" * self.audio_frames)


def _inspection(
    path: Path,
    *,
    rate: Fraction = Fraction(25),
    time_base: Fraction = Fraction(1, 1000),
    origin: Fraction = Fraction(0),
    frame_count: int = 3,
    width: int = 1920,
    height: int = 1080,
    codec: str = "h264",
    profile: str = "High",
    bitrate: int | None = 2_000_000,
    audio: bool = False,
    audio_codec: str = "aac",
    audio_profile: str = "LC",
    audio_channels: int = 1,
    audio_layout: str = "mono",
    audio_origin: Fraction = Fraction(0),
    audio_frames_count: int = 2400,
    major_brand: str = "isom",
    frames_override: list[dict[str, Any]] | None = None,
) -> MediaInspection:
    pts_step = Fraction(1, 1) / rate / time_base
    duration_step = pts_step
    if frames_override is None and pts_step.denominator != 1:
        raise AssertionError("fixture cadence must fit its time base")
    frames = frames_override or [
        {
            "stream_index": 0,
            "pts": int(origin / time_base) + index * int(pts_step),
            "duration": int(duration_step),
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
        "codec_name": codec,
        "profile": profile,
        "pix_fmt": "yuv420p",
        "field_order": "progressive",
        "sample_aspect_ratio": "1:1",
        "width": width,
        "height": height,
        "avg_frame_rate": f"{rate.numerator}/{rate.denominator}",
        "r_frame_rate": f"{rate.numerator}/{rate.denominator}",
        "time_base": f"{time_base.numerator}/{time_base.denominator}",
        "color_range": "tv",
        "color_space": "bt709",
        "color_primaries": "bt709",
        "color_transfer": "bt709",
    }
    if bitrate is not None:
        video["bit_rate"] = str(bitrate)
    probe_frames = list(frames)
    selected_audio = None
    selected_audio_frames: list[dict[str, Any]] = []
    selected_audio_origin: Fraction | None = None
    selected_audio_samples = 0
    if audio:
        selected_audio = {
            "index": 1,
            "codec_type": "audio",
            "codec_name": audio_codec,
            "profile": audio_profile,
            "sample_rate": "48000",
            "channels": audio_channels,
            "channel_layout": audio_layout,
        }
        selected_audio_origin = audio_origin
        selected_audio_samples = audio_frames_count
        selected_audio_frames = [
            {
                "stream_index": 1,
                "pts": int(audio_origin * 48000),
                "duration": audio_frames_count,
                "nb_samples": audio_frames_count,
            }
        ]
        probe_frames += selected_audio_frames
    probe = {
        "streams": [video] + ([selected_audio] if selected_audio else []),
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "tags": {"major_brand": major_brand},
            "bit_rate": str(bitrate or 0),
            "duration": str(float(Fraction(frame_count, 1) / rate)),
        },
        "frames": probe_frames,
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
        audio=selected_audio,
        audio_frames=selected_audio_frames,
        audio_origin=selected_audio_origin,
        audio_samples=selected_audio_samples,
        audio_hash="sha256:" + "1" * 64 if audio else None,
        audio_timestamp_residual=Fraction(0),
        audio_timestamp_drift=Fraction(0),
    )


def _review_source(
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tools: _FakeTools,
    *,
    profile: ReviewProfile = review_proxy.DEFAULT_REVIEW_PROFILE,
    source_spec: dict[str, Any] | None = None,
    proxy_spec: dict[str, Any] | None = None,
) -> review_proxy.ReviewSource:
    path.write_bytes(b"synthetic-master")

    def fake_inspect(
        inspected_path: Path,
        *,
        video_stream_index: int,
        audio_stream_index: int | None,
        tools: MediaTools,
    ) -> MediaInspection:
        del video_stream_index, audio_stream_index, tools
        spec = source_spec if inspected_path.resolve() == path.resolve() else proxy_spec
        if spec is None and inspected_path.resolve() != path.resolve():
            raise AssertionError(f"unexpected inspection: {inspected_path}")
        return _inspection(inspected_path, **(spec or {}))

    monkeypatch.setattr(review_proxy, "inspect_media", fake_inspect)
    return inspect_review_source(path, profile=profile, tools=cast(MediaTools, tools))


def test_profile_modes_thresholds_and_browser_safety(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = _FakeTools()
    safe = _review_source(
        tmp_path / "safe.mp4",
        monkeypatch,
        tools,
        source_spec={"width": 640, "height": 360, "bitrate": 1_000_000},
    )
    assert profile_decision(safe)["required"] is False
    assert profile_decision(safe)["masterBrowserSafe"] is True

    high_bitrate = _review_source(
        tmp_path / "high-bitrate.mp4",
        monkeypatch,
        tools,
        source_spec={"width": 640, "height": 360, "bitrate": 20_000_000},
    )
    assert profile_decision(high_bitrate)["reason"] == "above_threshold"

    unsafe = _review_source(
        tmp_path / "unsafe.mp4",
        monkeypatch,
        tools,
        source_spec={"width": 640, "height": 360, "codec": "hevc"},
    )
    assert profile_decision(unsafe)["reason"] == "browser_compatibility"

    never = _review_source(
        tmp_path / "never.mp4",
        monkeypatch,
        tools,
        profile=ReviewProfile(mode="never"),
    )
    always = _review_source(
        tmp_path / "always.mp4",
        monkeypatch,
        tools,
        profile=ReviewProfile(mode="always"),
    )
    assert profile_decision(never)["required"] is False
    assert profile_decision(always)["required"] is True


def test_master_container_check_and_identity_ignore_path_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = _FakeTools()
    source_spec = {"width": 640, "height": 360, "bitrate": 1_000_000}
    mp4 = _review_source(
        tmp_path / "master.mp4", monkeypatch, tools, source_spec=source_spec
    )
    mov = _review_source(
        tmp_path / "relocated.mov", monkeypatch, tools, source_spec=source_spec
    )

    assert mp4.inspection.content_hash == mov.inspection.content_hash
    assert mp4.inspection.probe_hash == mov.inspection.probe_hash
    assert mp4.generation_identity == mov.generation_identity
    assert profile_decision(mp4) == profile_decision(mov)
    assert profile_decision(mov)["masterBrowserSafe"] is True
    assert profile_decision(mov)["required"] is False

    quicktime = _review_source(
        tmp_path / "quicktime.mp4",
        monkeypatch,
        tools,
        source_spec={**source_spec, "major_brand": "qt  "},
    )
    decision = profile_decision(quicktime)
    assert decision["required"] is True
    assert decision["reason"] == "browser_compatibility"
    assert decision["masterVideoBrowserSafe"] is False


def test_review_playback_gates_unsafe_master_and_accounts_for_safe_master(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    safe_tools = _FakeTools(audio=True)
    safe = _review_source(
        tmp_path / "browser-safe.mp4",
        monkeypatch,
        safe_tools,
        source_spec={
            "width": 640,
            "height": 360,
            "bitrate": 1_000_000,
            "audio": True,
        },
    )
    safe_result = run_review_stage(
        safe,
        "proxy",
        cache_root=tmp_path / "safe-cache",
        output_path=tmp_path / "safe-job" / "proxy",
    )
    safe_playback = safe_result.receipt["evidence"]["reviewPlayback"]
    assert safe_playback["videoUsable"] is True
    assert safe_playback["videoSource"] == "master"
    assert safe_playback["audioSource"] == "audio-stage"
    assert safe_playback["audioRequired"] is True
    assert safe_playback["proxyHasAudio"] is False
    assert safe_result.artifact_path is None
    assert safe_result.receipt["totalOutputBytes"] == 0

    never = _review_source(
        tmp_path / "never-unsafe.mp4",
        monkeypatch,
        safe_tools,
        profile=ReviewProfile(mode="never"),
        source_spec={
            "width": 640,
            "height": 360,
            "bitrate": 1_000_000,
            "audio": True,
            "audio_codec": "pcm_s16le",
        },
    )
    never_result = run_review_stage(
        never,
        "proxy",
        cache_root=tmp_path / "never-cache",
        output_path=tmp_path / "never-job" / "proxy",
    )
    never_playback = never_result.receipt["evidence"]["reviewPlayback"]
    assert never_playback["videoUsable"] is False
    assert never_playback["videoSource"] is None
    assert never_playback["masterBrowserSafe"] is False
    assert profile_decision(never)["masterVideoBrowserSafe"] is True
    assert profile_decision(never)["masterAudioBrowserSafe"] is False


def test_coarse_source_timestamps_refuse_exact_frame_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = _FakeTools()
    path = tmp_path / "coarse.mp4"
    # 23.976 cadence quantized to 1 ms is close, but cannot prove exact frames.
    frames = [
        {"pts": 0, "duration": 42},
        {"pts": 42, "duration": 41},
        {"pts": 83, "duration": 42},
    ]
    with pytest.raises(ReviewProxyError, match="exact constant frame cadence"):
        _review_source(
            path,
            monkeypatch,
            tools,
            source_spec={
                "rate": Fraction(24000, 1001),
                "time_base": Fraction(1, 1000),
                "frames_override": frames,
            },
        )


def test_proxy_with_non_cfr_decoded_frames_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = _FakeTools()
    source = _review_source(
        tmp_path / "master.mp4",
        monkeypatch,
        tools,
        profile=ReviewProfile(mode="always"),
        proxy_spec={
            "rate": Fraction(25),
            "time_base": Fraction(1, 1000),
            "width": 1280,
            "height": 720,
            "profile": "Constrained Baseline",
            "frames_override": [
                {"pts": 0, "duration": 40},
                {"pts": 40, "duration": 39},
                {"pts": 80, "duration": 40},
            ],
        },
    )
    with pytest.raises(ReviewProxyError, match="exact constant frame cadence"):
        run_review_stage(
            source,
            "proxy",
            cache_root=tmp_path / "cache",
            output_path=tmp_path / "job" / "proxy",
        )
    assert not list((tmp_path / "cache").glob("**/published.json"))


def test_source_identity_and_changed_source_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = _FakeTools()
    path = tmp_path / "master.mp4"
    threshold = _review_source(path, monkeypatch, tools)
    always = _review_source(
        path, monkeypatch, tools, profile=ReviewProfile(mode="always")
    )
    assert threshold.generation_identity != always.generation_identity

    tools.version = "v2"
    new_tool_identity = _review_source(path, monkeypatch, tools)
    assert new_tool_identity.generation_identity != threshold.generation_identity
    with pytest.raises(ReviewProxyError, match="tool identity changed"):
        run_review_stage(
            threshold,
            "proxy",
            cache_root=tmp_path / "cache",
            output_path=tmp_path / "job" / "proxy",
        )

    path.write_bytes(b"changed synthetic master")
    with pytest.raises(ReviewProxyError, match="source changed"):
        run_review_stage(
            new_tool_identity,
            "proxy",
            cache_root=tmp_path / "cache",
            output_path=tmp_path / "job" / "proxy",
        )
    assert tools.proxy_calls == 0
    assert not (tmp_path / "cache").exists()


def test_proxy_mapping_reuse_and_corruption_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = _FakeTools()
    source_path = tmp_path / "master.mp4"
    source_bytes = b"synthetic-master"
    proxy_spec = {
        "rate": Fraction(25),
        "time_base": Fraction(1, 1000),
        "origin": Fraction(0),
        "frame_count": 3,
        "width": 1280,
        "height": 720,
        "profile": "Constrained Baseline",
        "bitrate": 5_000_000,
    }
    source = _review_source(
        source_path,
        monkeypatch,
        tools,
        profile=ReviewProfile(mode="always"),
        source_spec={"origin": Fraction(10), "frame_count": 3},
        proxy_spec=proxy_spec,
    )
    source_path.write_bytes(source_bytes)
    cache = tmp_path / "cache"
    marker = tmp_path / "job" / "proxy" / "output"

    first = run_review_stage(
        source,
        "proxy",
        cache_root=cache,
        output_path=marker,
    )
    assert first.reused is False
    assert first.artifact_path is not None
    mapping = first.receipt["evidence"]["frameMap"]
    assert mapping["sourceFrameCount"] == mapping["proxyFrameCount"] == 3
    assert mapping["proxyToMasterOffset"] == {"numerator": 10, "denominator": 1}
    assert first.receipt["artifact"]["sizeBytes"] == first.artifact_path.stat().st_size
    assert first.receipt["totalOutputBytes"] == first.artifact_path.stat().st_size
    assert source_path.read_bytes() == source_bytes
    assert (
        verify_review_stage(source, "proxy", cache_root=cache, output_path=marker)
        is not None
    )

    second = run_review_stage(
        source,
        "proxy",
        cache_root=cache,
        output_path=marker,
    )
    assert second.reused is True
    assert tools.proxy_calls == 1

    pointer = first.bundle_path.parent.parent / "published.json"
    pointer.unlink()
    resumed = run_review_stage(
        source,
        "proxy",
        cache_root=cache,
        output_path=tmp_path / "job" / "proxy" / "resumed",
    )
    assert resumed.reused is True
    assert resumed.bundle_path == first.bundle_path
    assert tools.proxy_calls == 1

    conflict_marker = tmp_path / "job" / "proxy" / "do-not-replace"
    conflict_marker.write_bytes(b"preserve me")
    with pytest.raises(ReviewProxyError, match="different bytes"):
        run_review_stage(
            source,
            "proxy",
            cache_root=cache,
            output_path=conflict_marker,
        )
    assert conflict_marker.read_bytes() == b"preserve me"

    first.artifact_path.write_bytes(b"tampered derivative")
    with pytest.raises(ReviewProxyError, match="missing or corrupt"):
        verify_review_stage(source, "proxy", cache_root=cache, output_path=marker)
    with pytest.raises(ReviewProxyError, match="missing or corrupt"):
        run_review_stage(source, "proxy", cache_root=cache, output_path=marker)
    assert tools.proxy_calls == 1


def test_audio_before_video_is_trimmed_and_subsample_offset_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = _FakeTools(audio=True)
    source = _review_source(
        tmp_path / "audio-before-video.mp4",
        monkeypatch,
        tools,
        source_spec={
            "frame_count": 2,
            "origin": Fraction(1, 100),
            "audio": True,
            "audio_origin": Fraction(0),
            "audio_frames_count": 2400,
        },
    )
    result = run_review_stage(
        source,
        "audio",
        cache_root=tmp_path / "trim-cache",
        output_path=tmp_path / "trim-job" / "audio",
    )
    assert result.artifact_path is not None
    evidence = result.receipt["evidence"]
    assert evidence["audioOffsetSamples"] == -480
    assert evidence["sourceSamplesSkipped"] == 480
    assert evidence["leadingSilenceSamples"] == 0
    assert evidence["sourceSamplesCopied"] == 1920
    assert evidence["trailingSilenceSamples"] == 1920
    with wave.open(str(result.artifact_path), "rb") as reader:
        assert reader.getnframes() == 3840
        assert reader.readframes(1) == b"\xe8\x03"

    sub_sample = _review_source(
        tmp_path / "subsample-offset.mp4",
        monkeypatch,
        tools,
        source_spec={
            "frame_count": 2,
            "audio": True,
            "audio_origin": Fraction(1, 96000),
        },
    )
    calls_before = len(tools.commands)
    with pytest.raises(ReviewProxyError, match="exact sample boundary"):
        run_review_stage(
            sub_sample,
            "audio",
            cache_root=tmp_path / "subsample-cache",
            output_path=tmp_path / "subsample-job" / "audio",
        )
    assert len(tools.commands) == calls_before


def test_audio_offset_and_waveform_derivatives_are_bound_and_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = _FakeTools(audio=True)
    source_path = tmp_path / "audio-master.mp4"
    source = _review_source(
        source_path,
        monkeypatch,
        tools,
        source_spec={
            "frame_count": 2,
            "audio": True,
            "audio_origin": Fraction(1, 100),
            "audio_frames_count": 2400,
        },
        proxy_spec={
            "frame_count": 2,
            "width": 1280,
            "height": 720,
            "profile": "Constrained Baseline",
            "bitrate": 5_000_000,
        },
    )
    cache = tmp_path / "cache-audio"
    audio_marker = tmp_path / "job-audio" / "audio" / "output"
    waveform_marker = tmp_path / "job-audio" / "waveform" / "output"

    proxy = run_review_stage(
        source,
        "proxy",
        cache_root=cache,
        output_path=tmp_path / "job-audio" / "proxy" / "output",
    )
    playback = proxy.receipt["evidence"]["reviewPlayback"]
    assert proxy.receipt["evidence"]["proxyHasAudio"] is False
    assert playback["videoUsable"] is True
    assert playback["videoSource"] == "proxy"
    assert playback["videoMuted"] is True
    assert playback["proxyHasAudio"] is False
    assert playback["audioSource"] == "audio-stage"
    assert playback["audioSynchronization"] == "aligned-audio-stage-at-video-origin/v1"
    assert "-an" in tools.commands[-1]
    assert proxy.artifact_path is not None
    assert proxy.receipt["totalOutputBytes"] == proxy.artifact_path.stat().st_size

    audio = run_review_stage(
        source, "audio", cache_root=cache, output_path=audio_marker
    )
    assert audio.artifact_path is not None
    assert audio.receipt["evidence"]["audioOffsetSamples"] == 480
    assert audio.receipt["evidence"]["leadingSilenceSamples"] == 480
    assert audio.receipt["evidence"]["trailingSilenceSamples"] == 960
    assert audio.receipt["artifact"]["sizeBytes"] == audio.artifact_path.stat().st_size
    assert audio.receipt["totalOutputBytes"] == audio.artifact_path.stat().st_size
    with wave.open(str(audio.artifact_path), "rb") as reader:
        assert reader.getnframes() == 3840
        assert reader.readframes(480) == bytes(960)

    waveform = run_review_stage(
        source, "waveform", cache_root=cache, output_path=waveform_marker
    )
    assert waveform.artifact_path is not None
    peaks = json.loads(waveform.artifact_path.read_bytes())
    assert peaks["audioHash"] == file_hash(audio.artifact_path)
    assert peaks["windowMs"] == 100
    assert peaks["peaks"] == [[1000]]
    assert waveform.receipt["totalOutputBytes"] == waveform.artifact_path.stat().st_size
    assert (
        verify_review_stage(source, "audio", cache_root=cache, output_path=audio_marker)
        is not None
    )
    assert (
        verify_review_stage(
            source, "waveform", cache_root=cache, output_path=waveform_marker
        )
        is not None
    )
    audio.artifact_path.write_bytes(b"tampered aligned audio")
    with pytest.raises(ReviewProxyError, match="missing or corrupt"):
        verify_review_stage(source, "audio", cache_root=cache, output_path=audio_marker)
    with pytest.raises(ReviewProxyError, match="missing or corrupt"):
        verify_review_stage(
            source, "waveform", cache_root=cache, output_path=waveform_marker
        )
