"""Slow, real-ffmpeg evidence for issue #174 media preparation."""

from __future__ import annotations

import hashlib
import io
import json
import math
import subprocess
import wave
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal, cast

import pytest
from issue174_media_fixture import (
    SUPPORTED_RATES,
    SyntheticMedia,
    assert_decoded_ordinals,
    decode_frame_ordinals,
    generate_synthetic_media,
)
from vera_timeline_agent.generated.contracts.compiler_dependencies_v2_schema import (
    RationalRate,
    RequestedPreparationRangeV1,
)
from vera_timeline_agent.media_preparation import (
    TARGET,
    MediaInspection,
    MediaTools,
    PreparationAuthorization,
    PreparedMedia,
    inspect_media,
    preparation_geometry,
    prepare_media,
)
from vera_timeline_agent.narration.models import identity_hash

CONVERSION_RATES = tuple(
    rate
    for rate in SUPPORTED_RATES
    if rate in {Fraction(24), Fraction(25), Fraction(30000, 1001), Fraction(30)}
)
MARKERS = (0, 165, 329)
ORIGIN_FRAME = 3000
VIDEO_PTS_ORIGIN = Fraction(2)
LOGGED_ORIGIN = Fraction(7)
SOURCE_FRAME_COUNT = 330
SOURCE_ID = "00000000-0000-4000-8000-000000000174"
PACKAGE_ID = "00000000-0000-4000-8000-000000000175"


def _wire(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def issue174_descriptor(
    inspection: MediaInspection,
    *,
    rate: Fraction,
    audio: bool,
    in_frame: int = ORIGIN_FRAME + 10,
) -> dict[str, Any]:
    """Build the schema-valid descriptor from one real ffprobe inspection."""
    mappings: list[dict[str, Any]] = []
    if audio:
        assert inspection.audio is not None
        assert inspection.audio_origin is not None
        mappings.append(
            {
                "streamIndex": inspection.audio["index"],
                "sampleRate": int(inspection.audio["sample_rate"]),
                "packagePtsOrigin": _wire(inspection.audio_origin),
                "loggedTimeAtPackageOrigin": _wire(
                    LOGGED_ORIGIN + inspection.audio_origin - inspection.pts_origin
                ),
                "audioHash": inspection.audio_hash,
                "probeHash": inspection.probe_hash,
            }
        )
    frame_map = {
        "packageFrameZeroLogicalFrame": ORIGIN_FRAME,
        "packageVideoPtsOrigin": _wire(inspection.pts_origin),
        "loggedTimeAtPackageFrameZero": _wire(LOGGED_ORIGIN),
        "decodedPackageFrameRate": _wire(rate),
        "decodedPackageFrameCount": len(inspection.video_frames),
        "packageVideoTimeBase": _wire(inspection.time_base),
        "sourceAudioStreamMappings": mappings,
        "descriptorHash": inspection.probe_hash,
        "probeHash": inspection.probe_hash,
    }
    return {
        "payloadId": SOURCE_ID,
        "owner": {"kind": "visual_only_block", "blockId": SOURCE_ID},
        "mediaReferenceId": SOURCE_ID,
        "sourceSnapshot": {
            "system": "local_import",
            "snapshotId": SOURCE_ID,
            "version": 1,
            "packageId": PACKAGE_ID,
            "contentHash": inspection.content_hash,
            "probeHash": inspection.probe_hash,
        },
        "logicalSourceBounds": {
            "startFrame": ORIGIN_FRAME,
            "endFrame": ORIGIN_FRAME + len(inspection.video_frames),
            "frameRate": _wire(rate),
        },
        "sourceFrameMap": frame_map,
        "occurrenceSourceInFrame": in_frame,
        "selectedSourceRange": None,
        "preparedMediaRequirementKey": None,
    }


def _request(
    *,
    in_frame: int = ORIGIN_FRAME + 10,
    duration: Fraction = Fraction(1),
    pre_handle: Fraction = Fraction(0),
    post_handle: Fraction = Fraction(0),
) -> dict[str, Any]:
    return {
        "sourceInFrame": in_frame,
        "duration": _wire(duration),
        "preHandle": _wire(pre_handle),
        "postHandle": _wire(post_handle),
    }


def assert_compiler_binding(
    descriptor: dict[str, Any], binding: dict[str, Any]
) -> dict[str, Any]:
    probe = (
        Path(__file__).resolve().parents[1]
        / "docs/verification/issue-174/compiler-binding-probe.mjs"
    )
    result = subprocess.run(
        ["node", str(probe)],
        input=json.dumps({"descriptor": descriptor, "binding": binding}).encode(),
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr.decode()
    return cast(dict[str, Any], json.loads(result.stdout))


def _prepared(
    source: Path,
    root: Path,
    *,
    rate: Fraction,
    target_rate: Fraction,
    audio: bool,
    request: dict[str, Any] | None = None,
) -> tuple[PreparedMedia, MediaInspection, MediaTools]:
    tools = MediaTools()
    inspection = inspect_media(
        source,
        video_stream_index=0,
        audio_stream_index=1 if audio else None,
        tools=tools,
    )
    descriptor = cast(Any, issue174_descriptor(inspection, rate=rate, audio=audio))
    authorization = PreparationAuthorization(
        reference="issue-174-real-media",
        read_roots=(source.parents[1],),
        write_root=root,
        tool_hash=identity_hash(tools.fingerprint()),
        minimum_free_bytes=0,
    )
    prepared = prepare_media(
        source,
        descriptor,
        cast(RequestedPreparationRangeV1, request or _request()),
        cast(RationalRate, _wire(target_rate)),
        authorization=authorization,
        video_stream_index=0,
        audio_stream_index=1 if audio else None,
        tools=tools,
    )
    return prepared, inspection, tools


def _source(
    root: Path,
    *,
    rate: Fraction,
    frame_count: int = SOURCE_FRAME_COUNT,
    flash_frames: tuple[int, ...] = MARKERS,
    audio_sample_rate: int | None = None,
    audio_channels: int = 1,
    mux_aac: bool = False,
    mux_audio: Literal["aac", "pcm_s24le"] | None = None,
    extension: str = ".mp4",
    video_codec: Literal["h264", "hevc"] = "h264",
) -> SyntheticMedia:
    return generate_synthetic_media(
        root,
        extension=extension,
        rate=rate,
        frame_count=frame_count,
        start_pts=VIDEO_PTS_ORIGIN,
        flash_frames=flash_frames,
        audio_sample_rate=audio_sample_rate or 48000,
        audio_channels=audio_channels,
        mux_aac=mux_aac,
        mux_audio=mux_audio,
        video_codec=video_codec,
    )


def _decoded_flash_indices(path: Path) -> tuple[int, ...]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-an",
        "-fps_mode",
        "passthrough",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-",
    ]
    raw = subprocess.run(command, check=True, capture_output=True).stdout
    frame_size = 64 * 64 * 3
    assert len(raw) % frame_size == 0
    indices = []
    for index in range(len(raw) // frame_size):
        frame = raw[index * frame_size : (index + 1) * frame_size]
        corner_luma = []
        for y in (0, 1, 2, 61, 62, 63):
            for x in (0, 1, 2, 61, 62, 63):
                position = (y * 64 + x) * 3
                corner_luma.append(sum(frame[position : position + 3]) / 3)
        if sum(corner_luma) / len(corner_luma) > 245:
            indices.append(index)
    return tuple(indices)


def _pcm_click_starts(path: Path) -> tuple[int, ...]:
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        assert stream.getsampwidth() == 3
        payload = stream.readframes(stream.getnframes())
    width = 3 * channels
    values = []
    for offset in range(0, len(payload), width):
        samples = [
            int.from_bytes(
                payload[offset + 3 * channel : offset + 3 * channel + 3],
                "little",
                signed=True,
            )
            for channel in range(channels)
        ]
        values.append(max(abs(sample) for sample in samples))
    return tuple(
        index
        for index, value in enumerate(values)
        if value and (index == 0 or not values[index - 1])
    )


def _wave_samples(path: Path) -> tuple[int, int, list[int]]:
    with wave.open(str(path), "rb") as stream:
        sample_rate = stream.getframerate()
        channels = stream.getnchannels()
        assert stream.getsampwidth() == 3
        payload = stream.readframes(stream.getnframes())
    return sample_rate, channels, _interleaved_samples(payload, channels)


def _interleaved_samples(payload: bytes, channels: int) -> list[int]:
    width = 3 * channels
    return [
        max(
            abs(
                int.from_bytes(
                    payload[offset + 3 * channel : offset + 3 * channel + 3],
                    "little",
                    signed=True,
                )
            )
            for channel in range(channels)
        )
        for offset in range(0, len(payload), width)
    ]


def _decoded_audio_samples(
    path: Path, *, stream_index: int, sample_rate: int
) -> list[int]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        str(path),
        "-map",
        f"0:{stream_index}",
        "-vn",
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s24le",
        "-f",
        "wav",
        "-",
    ]
    payload = subprocess.run(command, check=True, capture_output=True).stdout
    with wave.open(io.BytesIO(payload), "rb") as stream:
        assert stream.getframerate() == sample_rate
        channels = stream.getnchannels()
        return _interleaved_samples(stream.readframes(stream.getnframes()), channels)


def _peak_near(samples: Sequence[int], center: int, radius: int) -> int:
    lower = max(0, center - radius)
    upper = min(len(samples), center + radius + 1)
    return max(range(lower, upper), key=lambda index: samples[index])


def measure_issue174_sync(
    *,
    source_samples: Sequence[int],
    source_sample_rate: int,
    source_audio_origin: Fraction,
    output_start: Fraction,
    output_audio_path: Path,
    click_samples: Sequence[int],
    source_path: Path | None = None,
) -> dict[str, Any]:
    """Return JSON-safe source/output peak times and residuals in milliseconds."""
    output_rate, _, output_samples = _wave_samples(output_audio_path)
    source_radius = max(1, source_sample_rate // 20)
    output_radius = max(1, output_rate // 20)
    first_retained = max(
        0, math.ceil((output_start - source_audio_origin) * source_sample_rate)
    )
    exclusive_retained = min(
        len(source_samples),
        math.ceil(
            (
                output_start
                - source_audio_origin
                + Fraction(len(output_samples), output_rate)
            )
            * source_sample_rate
        ),
    )
    source_peaks = tuple(
        max(
            range(
                max(first_retained, sample - source_radius),
                min(exclusive_retained, sample + source_radius + 1),
            ),
            key=lambda index: source_samples[index],
        )
        for sample in click_samples
    )
    expected_output = tuple(
        Fraction(source_peak, source_sample_rate) + source_audio_origin - output_start
        for source_peak in source_peaks
    )
    output_peaks = tuple(
        _peak_near(
            output_samples,
            round(expected * output_rate),
            output_radius,
        )
        for expected in expected_output
    )
    residuals = tuple(
        (Fraction(actual, output_rate) - expected) * 1000
        for actual, expected in zip(output_peaks, expected_output, strict=True)
    )
    result = {
        "sourcePath": str(source_path) if source_path else None,
        "outputPath": str(output_audio_path),
        "outputHash": "sha256:"
        + hashlib.sha256(output_audio_path.read_bytes()).hexdigest(),
        "sourcePeaks": list(source_peaks),
        "expectedOutputSamples": [
            float(expected * output_rate) for expected in expected_output
        ],
        "outputPeaks": list(output_peaks),
        "residualMilliseconds": [float(residual) for residual in residuals],
        "maxResidualMilliseconds": float(
            max((abs(value) for value in residuals), default=Fraction(0))
        ),
        "driftMilliseconds": float(max(residuals) - min(residuals)),
        "sourceRetainedSampleInterval": [first_retained, exclusive_retained],
    }
    if source_path is not None:
        result["sourceHash"] = (
            "sha256:" + hashlib.sha256(source_path.read_bytes()).hexdigest()
        )
    return result


@pytest.mark.slow
@pytest.mark.parametrize("source_rate", CONVERSION_RATES, ids=str)
def test_real_media_derives_every_verified_source_ordinal(
    tmp_path: Path, source_rate: Fraction
) -> None:
    fixture = _source(tmp_path / "source", rate=source_rate)
    prepared, inspection, _ = _prepared(
        fixture.path,
        tmp_path / "prepared",
        rate=source_rate,
        target_rate=TARGET,
        audio=False,
    )
    geometry = preparation_geometry(
        source_rate=source_rate,
        target_rate=TARGET,
        origin_frame=ORIGIN_FRAME,
        lower_frame=ORIGIN_FRAME,
        upper_frame=ORIGIN_FRAME + SOURCE_FRAME_COUNT,
        in_frame=ORIGIN_FRAME + 10,
        duration=Fraction(1),
    )
    assert prepared.binding["mode"] == "derived_cfr"
    assert prepared.binding["verification"]["decodedFrameRate"] == _wire(TARGET)
    assert len(inspection.video_frames) == SOURCE_FRAME_COUNT
    assert prepared.video_path != fixture.path
    observed = decode_frame_ordinals(prepared.video_path)
    expected = tuple(
        geometry.selected_package_frame(index) for index in range(geometry.frame_count)
    )
    assert observed == expected


@pytest.mark.slow
@pytest.mark.parametrize("source_rate", (TARGET, Fraction(50)), ids=str)
def test_same_rate_reuses_source_without_video_encode(
    tmp_path: Path, source_rate: Fraction
) -> None:
    tmp_path = tmp_path / "reuse with spaces"
    fixture = _source(tmp_path / "source", rate=source_rate)
    prepared, _, tools = _prepared(
        fixture.path,
        tmp_path / "prepared",
        rate=source_rate,
        target_rate=source_rate,
        audio=False,
    )
    assert prepared.binding["mode"] == "verified_reuse"
    assert prepared.video_path == fixture.path
    assert "%20" in prepared.binding["artifactLocator"]
    assert fixture.hashes["video"] == prepared.binding["verification"]["deliveredHash"]
    assert not any("libx264" in command for command in tools.commands)


@pytest.mark.slow
@pytest.mark.parametrize(
    ("extension", "video_codec"),
    ((".mov", "h264"), (".mkv", "h264"), (".mov", "hevc"), (".mkv", "hevc")),
)
def test_real_mov_mkv_h264_and_hevc_profiles_are_inspectable(
    tmp_path: Path, extension: str, video_codec: Literal["h264", "hevc"]
) -> None:
    markers = (0, 15, 29)
    fixture = _source(
        tmp_path / "source",
        rate=Fraction(25),
        frame_count=30,
        flash_frames=markers,
        extension=extension,
        video_codec=video_codec,
    )
    prepared, inspection, _ = _prepared(
        fixture.path,
        tmp_path / "prepared",
        rate=Fraction(25),
        target_rate=Fraction(25),
        audio=False,
        request=_request(in_frame=ORIGIN_FRAME, duration=Fraction(6, 5)),
    )
    assert inspection.video["codec_name"] == video_codec
    assert prepared.binding["mode"] == "verified_reuse"
    assert prepared.video_path == fixture.path
    assert_decoded_ordinals(
        fixture.path,
        tuple((frame, frame) for frame in markers),
    )
    derived, _, _ = _prepared(
        fixture.path,
        tmp_path / "derived",
        rate=Fraction(25),
        target_rate=TARGET,
        audio=False,
        request=_request(in_frame=ORIGIN_FRAME, duration=Fraction(6, 5)),
    )
    assert decode_frame_ordinals(derived.video_path) == tuple(
        (j * 25 * 1001) // 24000 for j in range(math.ceil(Fraction(6, 5) * TARGET))
    )


@pytest.mark.slow
def test_repeated_generation_and_derivation_are_byte_identical(tmp_path: Path) -> None:
    first = _source(tmp_path / "first", rate=Fraction(25))
    second = _source(tmp_path / "second", rate=Fraction(25))
    assert first.hashes == second.hashes
    first_prepared, _, _ = _prepared(
        first.path,
        tmp_path / "first-prepared",
        rate=Fraction(25),
        target_rate=TARGET,
        audio=False,
    )
    second_prepared, _, _ = _prepared(
        second.path,
        tmp_path / "second-prepared",
        rate=Fraction(25),
        target_rate=TARGET,
        audio=False,
    )
    assert (
        first_prepared.binding["verification"]["deliveredHash"]
        == second_prepared.binding["verification"]["deliveredHash"]
    )
    assert (
        first_prepared.video_path.read_bytes()
        == second_prepared.video_path.read_bytes()
    )


@pytest.mark.slow
@pytest.mark.parametrize(
    ("audio_sample_rate", "audio_channels"),
    ((44100, 1), (44100, 2), (48000, 1), (48000, 2)),
)
def test_pcm_clicks_and_derived_waveform_stay_aligned(
    tmp_path: Path, audio_sample_rate: int, audio_channels: int
) -> None:
    tmp_path = tmp_path / "package with spaces"
    marker_frames = (10, 135, 259)
    fixture = _source(
        tmp_path / "source",
        rate=Fraction(25),
        flash_frames=marker_frames,
        audio_sample_rate=audio_sample_rate,
        audio_channels=audio_channels,
        extension=".mov",
        mux_audio="pcm_s24le",
    )
    assert _pcm_click_starts(fixture.audio_path) == fixture.click_samples
    for frame, sample in zip(marker_frames, fixture.click_samples, strict=True):
        residual = abs(Fraction(sample, audio_sample_rate) - Fraction(frame, 25))
        assert residual <= Fraction(1, 1000)
    assert fixture.muxed_path is not None
    prepared, inspection, _ = _prepared(
        fixture.muxed_path,
        tmp_path / "prepared",
        rate=Fraction(25),
        target_rate=TARGET,
        audio=True,
        request=_request(duration=Fraction(10)),
    )
    assert inspection.pts_origin == VIDEO_PTS_ORIGIN
    assert inspection.audio_origin is not None and inspection.audio_origin > 0
    assert inspection.audio is not None
    assert inspection.audio["sample_rate"] == str(audio_sample_rate)
    assert inspection.audio["channels"] == audio_channels
    assert prepared.audio_path is not None
    geometry = preparation_geometry(
        source_rate=Fraction(25),
        target_rate=TARGET,
        origin_frame=ORIGIN_FRAME,
        lower_frame=ORIGIN_FRAME,
        upper_frame=ORIGIN_FRAME + SOURCE_FRAME_COUNT,
        in_frame=ORIGIN_FRAME + 10,
        duration=Fraction(10),
    )
    observed = decode_frame_ordinals(prepared.video_path)
    expected = tuple(
        geometry.selected_package_frame(index) for index in range(geometry.frame_count)
    )
    assert observed == expected
    marker_output_indices = tuple(expected.index(frame) for frame in marker_frames)
    assert _decoded_flash_indices(prepared.video_path) == marker_output_indices
    source_sample_rate, _, source_samples = _wave_samples(fixture.audio_path)
    assert source_sample_rate == audio_sample_rate
    assert inspection.audio_origin is not None
    measurements = measure_issue174_sync(
        source_samples=source_samples,
        source_sample_rate=source_sample_rate,
        source_audio_origin=inspection.audio_origin,
        output_start=inspection.pts_origin + geometry.start,
        output_audio_path=prepared.audio_path,
        click_samples=fixture.click_samples,
        source_path=fixture.audio_path,
    )
    assert json.dumps(measurements)
    assert measurements["maxResidualMilliseconds"] <= 1.0
    with wave.open(str(prepared.audio_path), "rb") as output:
        assert output.getframerate() == 48000
        assert output.getnchannels() == audio_channels
        assert output.getsampwidth() == 3
        delivered_samples = output.getnframes()
    record = cast(dict[str, Any], json.loads(prepared.receipt_path.read_bytes()))
    assert prepared.binding["verification"]["sourceAudio"]["sampleRate"] == (
        audio_sample_rate
    )
    assert_compiler_binding(
        issue174_descriptor(inspection, rate=Fraction(25), audio=True),
        cast(dict[str, Any], prepared.binding),
    )
    assert "%20" in prepared.binding["artifactLocator"]
    assert delivered_samples == record["audio"]["decodedSamples"]
    endpoint_error = record["audio"]["endpointError"]
    assert abs(
        Fraction(endpoint_error["numerator"], endpoint_error["denominator"])
    ) <= Fraction(1, 1000)


@pytest.mark.slow
@pytest.mark.parametrize(
    ("audio_sample_rate", "audio_channels"),
    ((44100, 1), (44100, 2), (48000, 1), (48000, 2)),
)
def test_aac_derived_waveform_tracks_decoded_source_origin(
    tmp_path: Path, audio_sample_rate: int, audio_channels: int
) -> None:
    marker_frames = (10, 135, 259)
    fixture = _source(
        tmp_path / "source",
        rate=Fraction(25),
        flash_frames=marker_frames,
        audio_sample_rate=audio_sample_rate,
        audio_channels=audio_channels,
        mux_aac=True,
    )
    assert fixture.muxed_path is not None
    prepared, inspection, _ = _prepared(
        fixture.muxed_path,
        tmp_path / "prepared",
        rate=Fraction(25),
        target_rate=TARGET,
        audio=True,
        request=_request(duration=Fraction(10)),
    )
    assert inspection.audio_origin is not None
    assert prepared.audio_path is not None
    geometry = preparation_geometry(
        source_rate=Fraction(25),
        target_rate=TARGET,
        origin_frame=ORIGIN_FRAME,
        lower_frame=ORIGIN_FRAME,
        upper_frame=ORIGIN_FRAME + SOURCE_FRAME_COUNT,
        in_frame=ORIGIN_FRAME + 10,
        duration=Fraction(10),
    )
    source_samples = _decoded_audio_samples(
        fixture.muxed_path,
        stream_index=1,
        sample_rate=audio_sample_rate,
    )
    measurements = measure_issue174_sync(
        source_samples=source_samples,
        source_sample_rate=audio_sample_rate,
        source_audio_origin=inspection.audio_origin,
        output_start=inspection.pts_origin + geometry.start,
        output_audio_path=prepared.audio_path,
        click_samples=fixture.click_samples,
        source_path=fixture.muxed_path,
    )
    assert json.dumps(measurements)
    assert measurements["maxResidualMilliseconds"] <= 1.0
    assert measurements["driftMilliseconds"] <= 1.0
    assert_compiler_binding(
        issue174_descriptor(inspection, rate=Fraction(25), audio=True),
        cast(dict[str, Any], prepared.binding),
    )
    if audio_sample_rate == 48000:
        first, exclusive = measurements["sourceRetainedSampleInterval"]
        assert _wave_samples(prepared.audio_path)[2] == source_samples[first:exclusive]


@pytest.mark.slow
def test_shared_grid_flash_and_aac_clicks_stay_aligned(tmp_path: Path) -> None:
    marker_frames = (0, 1001, 2002)
    frame_count = 2003
    fixture = _source(
        tmp_path / "source",
        rate=Fraction(25),
        frame_count=frame_count,
        flash_frames=marker_frames,
        audio_sample_rate=48000,
        audio_channels=1,
        mux_aac=True,
    )
    assert fixture.muxed_path is not None
    request = _request(
        in_frame=ORIGIN_FRAME,
        duration=Fraction(frame_count, 25),
    )
    prepared, inspection, _ = _prepared(
        fixture.muxed_path,
        tmp_path / "prepared",
        rate=Fraction(25),
        target_rate=TARGET,
        audio=True,
        request=request,
    )
    assert inspection.audio_origin is not None
    geometry = preparation_geometry(
        source_rate=Fraction(25),
        target_rate=TARGET,
        origin_frame=ORIGIN_FRAME,
        lower_frame=ORIGIN_FRAME,
        upper_frame=ORIGIN_FRAME + frame_count,
        in_frame=ORIGIN_FRAME,
        duration=Fraction(frame_count, 25),
    )
    observed = decode_frame_ordinals(prepared.video_path)
    expected = tuple(
        geometry.selected_package_frame(index) for index in range(geometry.frame_count)
    )
    assert observed == expected
    marker_output_indices = tuple(expected.index(frame) for frame in marker_frames)
    assert marker_output_indices == (0, 960, 1920)
    assert _decoded_flash_indices(prepared.video_path) == marker_output_indices
    source_samples = _decoded_audio_samples(
        fixture.muxed_path,
        stream_index=1,
        sample_rate=48000,
    )
    assert prepared.audio_path is not None
    measurements = measure_issue174_sync(
        source_samples=source_samples,
        source_sample_rate=48000,
        source_audio_origin=inspection.audio_origin,
        output_start=inspection.pts_origin + geometry.start,
        output_audio_path=prepared.audio_path,
        click_samples=fixture.click_samples,
        source_path=fixture.muxed_path,
    )
    assert json.dumps(measurements)
    residuals = measurements["residualMilliseconds"]
    assert measurements["maxResidualMilliseconds"] <= 1.0
    assert max(residuals) - min(residuals) <= 1.0


@pytest.mark.slow
def test_exact_three_frame_and_ten_second_ranges_preserve_handles_and_endpoints(
    tmp_path: Path,
) -> None:
    fixture = _source(
        tmp_path / "source",
        rate=Fraction(25),
        audio_sample_rate=48000,
        audio_channels=1,
        mux_aac=True,
    )
    assert fixture.muxed_path is not None
    tools = MediaTools()
    inspection = inspect_media(
        fixture.muxed_path,
        video_stream_index=0,
        audio_stream_index=1,
        tools=tools,
    )
    descriptor = cast(
        Any, issue174_descriptor(inspection, rate=Fraction(25), audio=True)
    )
    authorization = PreparationAuthorization(
        reference="issue-174-endpoints",
        read_roots=(fixture.muxed_path.parents[1],),
        write_root=tmp_path / "prepared",
        tool_hash=identity_hash(tools.fingerprint()),
        minimum_free_bytes=0,
    )
    cases = (
        ("three-source-frames", Fraction(3, 25), Fraction(0), Fraction(0), 3),
        ("250-source-frames", Fraction(10), Fraction(0), Fraction(0), 240),
        (
            "250-source-frames-with-handles",
            Fraction(10),
            Fraction(1, 1) / TARGET,
            Fraction(1, 1) / TARGET,
            242,
        ),
    )
    for name, duration, pre_handle, post_handle, expected_count in cases:
        request = _request(
            duration=duration,
            pre_handle=pre_handle,
            post_handle=post_handle,
        )
        prepared = prepare_media(
            fixture.muxed_path,
            descriptor,
            cast(RequestedPreparationRangeV1, request),
            cast(RationalRate, _wire(TARGET)),
            authorization=authorization,
            video_stream_index=0,
            audio_stream_index=1,
            tools=tools,
        )
        record = cast(dict[str, Any], json.loads(prepared.receipt_path.read_bytes()))
        assert record["geometry"]["terminalQuantization"]["denominator"] > 0
        assert prepared.binding["verification"]["decodedFrameCount"] == expected_count
        assert len(decode_frame_ordinals(prepared.video_path)) == expected_count
        assert record["audio"]["decodedSamples"] == (
            record["audio"]["resampledExclusiveSample"]
            - record["audio"]["resampledFirstSample"]
        ), name
        endpoint_error = record["audio"]["endpointError"]
        assert abs(
            Fraction(endpoint_error["numerator"], endpoint_error["denominator"])
        ) <= Fraction(1, 1000)


@pytest.mark.slow
def test_source_flashes_remain_distinct_from_expected_click_times(
    tmp_path: Path,
) -> None:
    fixture = _source(
        tmp_path / "source",
        rate=Fraction(25),
        audio_sample_rate=48000,
        audio_channels=1,
    )
    assert _decoded_flash_indices(fixture.path) == MARKERS
    for frame, sample in zip(MARKERS, fixture.click_samples, strict=True):
        assert abs(Fraction(sample, 48000) - Fraction(frame, 25)) <= Fraction(1, 1000)
    assert_decoded_ordinals(fixture.path, tuple((frame, frame) for frame in MARKERS))
