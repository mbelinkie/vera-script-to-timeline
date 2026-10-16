"""Decoded installed-tool refusals, including false CFR container labels."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from issue174_media_fixture import generate_synthetic_media
from vera_timeline_agent.media_preparation import (
    MediaPreparationError,
    MediaTools,
    inspect_media,
)

pytestmark = pytest.mark.slow


@pytest.mark.parametrize(
    "case",
    [
        "unknown_color",
        "hdr",
        "interlace",
        "aspect",
        "codec",
        "dimensions",
        "timecode",
        "rotation",
        "vfr",
    ],
)
def test_real_unsupported_source_refuses(tmp_path: Path, case: str) -> None:
    fixture = generate_synthetic_media(tmp_path / "source", frame_count=60)
    output = tmp_path / ("refused.mkv" if case == "vfr" else "refused.mp4")
    options = ["-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p"]
    if case == "unknown_color":
        options += [
            "-vf",
            "setparams=color_primaries=unknown:color_trc=unknown:colorspace=unknown",
        ]
    elif case == "hdr":
        options += [
            "-color_trc",
            "smpte2084",
            "-color_primaries",
            "bt2020",
            "-colorspace",
            "bt2020nc",
        ]
    elif case == "interlace":
        options += ["-flags", "+ilme+ildct", "-x264-params", "tff=1"]
    elif case == "aspect":
        options += ["-vf", "setsar=2/1"]
    elif case == "codec":
        options = ["-c:v", "mpeg4", "-threads", "1"]
    elif case == "dimensions":
        options += ["-vf", "scale=3842:64"]
    elif case == "timecode":
        options += ["-timecode", "01:00:00:00"]
    elif case == "rotation":
        options = ["-c:v", "copy"]
    elif case == "vfr":
        options += [
            "-vf",
            "settb=1/1000,setpts=PTS+if(eq(N\\,17)\\,20\\,0)",
            "-enc_time_base",
            "1:1000",
            "-fps_mode",
            "passthrough",
        ]
    tools = MediaTools()
    tools.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-n",
            *(["-display_rotation:v:0", "90"] if case == "rotation" else []),
            "-i",
            str(fixture.path),
            "-an",
            *options,
            str(output),
        ]
    )
    if case == "vfr":
        probe = json.loads(
            tools.run(
                ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)]
            )
        )
        stream = probe["streams"][0]
        assert stream["avg_frame_rate"] == stream["r_frame_rate"] == "25/1"
    with pytest.raises(MediaPreparationError) as refused:
        inspect_media(
            output, video_stream_index=0, audio_stream_index=None, tools=tools
        )
    assert refused.value.code == (
        "unsupported_vfr_or_timebase" if case == "vfr" else "unsupported_profile"
    )


def test_real_decode_failure_and_ambiguous_selection(tmp_path: Path) -> None:
    fixture = generate_synthetic_media(
        tmp_path / "source", frame_count=60, mux_aac=True
    )
    assert fixture.muxed_path is not None
    tools = MediaTools()
    with pytest.raises(MediaPreparationError, match="ambiguous_streams"):
        inspect_media(
            fixture.muxed_path,
            video_stream_index=0,
            audio_stream_index=None,
            tools=tools,
        )
    with pytest.raises(MediaPreparationError, match="ambiguous_streams"):
        inspect_media(
            fixture.path, video_stream_index=99, audio_stream_index=None, tools=tools
        )
    damaged = tmp_path / "truncated.mp4"
    damaged.write_bytes(fixture.path.read_bytes()[:500])
    with pytest.raises(MediaPreparationError, match="decode_or_tool_failure"):
        inspect_media(
            damaged, video_stream_index=0, audio_stream_index=None, tools=tools
        )


@pytest.mark.parametrize("options", [["-ar", "32000"], ["-ac", "6"], ["-c:a", "alac"]])
def test_real_unsupported_audio(tmp_path: Path, options: list[str]) -> None:
    fixture = generate_synthetic_media(tmp_path / "source", frame_count=60)
    output = tmp_path / "audio-profile.mov"
    tools = MediaTools()
    tools.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-n",
            "-i",
            str(fixture.path),
            "-i",
            str(fixture.audio_path),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "copy",
            "-c:a",
            "pcm_s24le",
            *options,
            str(output),
        ]
    )
    with pytest.raises(MediaPreparationError, match="unsupported_profile"):
        inspect_media(output, video_stream_index=0, audio_stream_index=1, tools=tools)
