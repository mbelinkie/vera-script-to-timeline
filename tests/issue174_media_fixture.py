"""Deterministic synthetic media for the verified-CFR preparation slice.

The video carries a twelve-bit frame ordinal in large black/white blocks.  The
blocks are drawn after an optional flash background so the ordinal survives
lossy H.264 encoding.  Audio is independent PCM-24 with clicks at the exact
source-frame times; an AAC mux is available for stream-selection cases.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import wave
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

WIDTH = 64
HEIGHT = 64
MAX_ORDINAL = (1 << 12) - 1
SUPPORTED_RATES = (
    Fraction(24000, 1001),
    Fraction(24, 1),
    Fraction(25, 1),
    Fraction(30000, 1001),
    Fraction(30, 1),
    Fraction(50, 1),
)


@dataclass(frozen=True)
class SyntheticMedia:
    """Generated source paths, exact subprocess commands, and byte hashes."""

    path: Path
    audio_path: Path
    muxed_path: Path | None
    rate: Fraction
    frame_count: int
    start_pts: Fraction
    flash_frames: tuple[int, ...]
    click_samples: tuple[int, ...]
    commands: tuple[tuple[str, ...], ...]
    hashes: dict[str, str]
    probe_hashes: dict[str, str]


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _hash_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _run(command: Sequence[str], *, output: bool = False) -> bytes:
    completed = subprocess.run(
        list(command),
        check=True,
        capture_output=True,
        text=False,
    )
    if output:
        return completed.stdout
    return b""


def _rate_text(rate: Fraction) -> str:
    return f"{rate.numerator}/{rate.denominator}"


def _decimal_seconds(value: Fraction) -> str:
    return f"{float(value):.12f}"


def _container_start_correction(start_pts: Fraction, rate: Fraction) -> Fraction:
    """Return the fractional correction for muxers that ceil a first frame."""
    frame_position = start_pts * rate
    next_frame = (
        frame_position.numerator + frame_position.denominator - 1
    ) // frame_position.denominator
    return Fraction(next_frame, 1) / rate - start_pts


def _validate_rate(rate: Fraction) -> None:
    if rate not in SUPPORTED_RATES:
        raise ValueError(f"unsupported synthetic rate: {rate}")


def _frame_ordinal(frame: int) -> bytes:
    if not 0 <= frame <= MAX_ORDINAL:
        raise ValueError(f"frame ordinal must fit twelve bits: {frame}")
    bits = [(frame >> bit) & 1 for bit in range(12)]
    pixels = bytearray(WIDTH * HEIGHT * 3)
    background = (230, 230, 230)
    for offset in range(0, len(pixels), 3):
        pixels[offset : offset + 3] = bytes(background)

    # Four columns by three rows, deliberately separated from the bar/flash.
    block_width = 11
    block_height = 11
    x0, y0 = 4, 4
    x_step, y_step = 15, 14
    for index, bit in enumerate(bits):
        row, column = divmod(index, 4)
        left = x0 + column * x_step
        top = y0 + row * y_step
        colour = 250 if bit else 4
        for y in range(top, top + block_height):
            for x in range(left, left + block_width):
                position = (y * WIDTH + x) * 3
                pixels[position : position + 3] = bytes((colour, colour, colour))

    # A central moving bar remains visibly distinct from the ordinal blocks.
    bar_x = 26 + (frame % 13)
    for y in range(44, 60):
        for x in range(bar_x, bar_x + 5):
            position = (y * WIDTH + x) * 3
            pixels[position : position + 3] = bytes((30, 190, 30))
    return bytes(pixels)


def _write_video_frames(path: Path, frame_count: int, flash_frames: set[int]) -> None:
    payload = bytearray()
    for frame in range(frame_count):
        pixels = bytearray(_frame_ordinal(frame))
        if frame in flash_frames:
            # Flash the field around the identity blocks; the blocks remain
            # black/white and therefore remain decodable after H.264 encoding.
            bar_x = 26 + (frame % 13)
            for y in range(0, HEIGHT):
                for x in range(WIDTH):
                    in_identity = 4 <= x < 56 and 4 <= y < 39
                    in_bar = bar_x <= x < bar_x + 5 and 44 <= y < 60
                    if not in_identity and not in_bar:
                        position = (y * WIDTH + x) * 3
                        pixels[position : position + 3] = b"\xff\xff\xff"
        payload.extend(pixels)
    path.write_bytes(payload)


def _click_samples(
    rate: Fraction, sample_rate: int, flash_frames: Sequence[int]
) -> tuple[int, ...]:
    return tuple(
        (frame * sample_rate * rate.denominator + rate.numerator // 2) // rate.numerator
        for frame in flash_frames
    )


def _write_pcm24(
    path: Path,
    *,
    rate: Fraction,
    frame_count: int,
    sample_rate: int,
    channels: int,
    flash_frames: Sequence[int],
) -> tuple[int, ...]:
    if sample_rate not in (44100, 48000):
        raise ValueError("synthetic audio sample rate must be 44100 or 48000")
    if channels not in (1, 2):
        raise ValueError("synthetic audio must be mono or stereo")
    clicks = _click_samples(rate, sample_rate, flash_frames)
    total_samples = (
        frame_count * sample_rate * rate.denominator + rate.numerator - 1
    ) // rate.numerator + 2048
    click_values = (0x500000, -0x500000, 0x500000, -0x500000, 0)
    raw = bytearray()
    for sample in range(total_samples):
        value = 0
        for click in clicks:
            relative = sample - click
            if 0 <= relative < len(click_values):
                value = click_values[relative]
                break
        packed = int(value).to_bytes(3, "little", signed=True)
        raw.extend(packed * channels)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(3)
        output.setframerate(sample_rate)
        output.writeframes(bytes(raw))
    return clicks


def _probe(path: Path, ffprobe: str) -> tuple[dict[str, object], str, tuple[str, ...]]:
    command = (
        ffprobe,
        "-v",
        "error",
        "-count_frames",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
    )
    raw = _run(command, output=True)
    decoded = json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError(f"ffprobe result is not an object: {path}")
    return decoded, _hash_bytes(raw), command


def _fraction_text(value: object) -> Fraction:
    if not isinstance(value, str):
        raise ValueError(f"expected rational text, got {value!r}")
    return Fraction(value)


def _validate_video_probe(
    probe: dict[str, object],
    rate: Fraction,
    frame_count: int,
    start_pts: Fraction,
    *,
    codec: Literal["h264", "hevc"],
) -> None:
    streams = probe.get("streams")
    if not isinstance(streams, list):
        raise ValueError("ffprobe omitted streams")
    video = [
        item
        for item in streams
        if isinstance(item, dict) and item.get("codec_type") == "video"
    ]
    if len(video) != 1:
        raise ValueError("synthetic source must contain one video stream")
    stream = video[0]
    tags = stream.get("tags")
    stream_tags = tags if isinstance(tags, dict) else {}

    def colour(field: str, tag: str) -> object:
        return stream.get(field) or stream_tags.get(tag)

    expected_codec = "h264" if codec == "h264" else "hevc"
    expected_profile = "High" if codec == "h264" else "Main"
    if (
        stream.get("codec_name") != expected_codec
        or stream.get("profile") != expected_profile
        or stream.get("pix_fmt") != "yuv420p"
        or stream.get("width") != WIDTH
        or stream.get("height") != HEIGHT
        or stream.get("sample_aspect_ratio") != "1:1"
        or stream.get("color_range") != "tv"
        or stream.get("color_space") != "bt709"
        or colour("color_transfer", "COLOR_TRANSFER") != "bt709"
        or colour("color_primaries", "COLOR_PRIMARIES") != "bt709"
    ):
        raise ValueError(f"synthetic video profile mismatch: {stream}")
    if _fraction_text(stream.get("avg_frame_rate")) != rate:
        raise ValueError("synthetic video frame rate mismatch")
    if int(stream.get("nb_read_frames", -1)) != frame_count:
        raise ValueError("synthetic video frame count mismatch")
    actual_start = _fraction_text(stream.get("start_time", "0"))
    if actual_start != start_pts:
        raise ValueError(
            f"synthetic video start PTS mismatch: {actual_start} != {start_pts}"
        )


def _mux_audio(
    video: Path,
    audio: Path,
    output: Path,
    *,
    start_pts: Fraction,
    codec: Literal["aac", "pcm_s24le"],
    ffmpeg: str,
) -> tuple[str, ...]:
    offset = _decimal_seconds(start_pts)
    command_list = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-copyts",
        "-i",
        str(video),
        "-itsoffset",
        offset,
        "-i",
        str(audio),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        codec,
        "-avoid_negative_ts",
        "disabled",
        str(output),
    ]
    if codec == "aac":
        command_list[-1:-1] = ["-b:a", "192k"]
    command = tuple(command_list)
    _run(command)
    return command


def generate_synthetic_media(
    root: Path,
    *,
    extension: str = ".mp4",
    rate: Fraction = Fraction(25, 1),
    frame_count: int = 330,
    start_pts: Fraction = Fraction(0, 1),
    flash_frames: Sequence[int] = (),
    audio_sample_rate: int = 48000,
    audio_channels: int = 1,
    mux_aac: bool = False,
    mux_audio: Literal["aac", "pcm_s24le"] | None = None,
    video_codec: Literal["h264", "hevc"] = "h264",
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> SyntheticMedia:
    """Create one issue-owned synthetic source under ``root``."""
    _validate_rate(rate)
    if video_codec not in {"h264", "hevc"}:
        raise ValueError("synthetic video codec must be h264 or hevc")
    if mux_aac and mux_audio is not None:
        raise ValueError("choose mux_aac or mux_audio, not both")
    if mux_aac:
        mux_audio = "aac"
    if frame_count < 1 or frame_count > MAX_ORDINAL + 1:
        raise ValueError("frame_count must fit the twelve-bit frame ordinal")
    if start_pts < 0 or (start_pts * rate.numerator).denominator != 1:
        raise ValueError("start_pts must be nonnegative and frame-rate representable")
    markers = tuple(sorted(set(flash_frames)))
    if any(frame < 0 or frame >= frame_count for frame in markers):
        raise ValueError("flash frame is outside the generated source")
    suffix = extension.lower()
    if suffix not in {".mov", ".mp4", ".mkv"}:
        raise ValueError("synthetic video extension must be .mov, .mp4, or .mkv")
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    work = root / "issue174-media"
    work.mkdir(exist_ok=True)
    raw_video = work / "frames.rgb24"
    video = work / f"source{suffix}"
    audio = work / "source.pcm24.wav"
    _write_video_frames(raw_video, frame_count, set(markers))
    clicks = _write_pcm24(
        audio,
        rate=rate,
        frame_count=frame_count,
        sample_rate=audio_sample_rate,
        channels=audio_channels,
        flash_frames=markers,
    )
    start_ticks = int(start_pts * rate.numerator)
    start_correction = _container_start_correction(start_pts, rate)
    video_filter = (
        f"settb=1/{rate.numerator},setpts=N*{rate.denominator}+{start_ticks},"
        "setsar=1/1,format=yuv420p"
    )
    video_codec_name = "libx264" if video_codec == "h264" else "libx265"
    video_profile = "high" if video_codec == "h264" else "main"
    encoder_params = "colorprim=bt709:transfer=bt709:colormatrix=bt709"
    encoder_option = "-x264-params" if video_codec == "h264" else "-x265-params"
    video_command_list = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s:v",
        f"{WIDTH}x{HEIGHT}",
        "-framerate",
        _rate_text(rate),
        "-i",
        str(raw_video),
        "-vf",
        video_filter,
        "-copyts",
        "-fps_mode",
        "passthrough",
        "-c:v",
        video_codec_name,
        "-profile:v",
        video_profile,
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        "-preset",
        "medium",
        "-threads",
        "1",
        "-color_range",
        "tv",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        encoder_option,
        encoder_params,
        "-metadata:s:v:0",
        "color_primaries=bt709",
        "-metadata:s:v:0",
        "color_transfer=bt709",
        "-metadata:s:v:0",
        "colorspace=bt709",
        "-output_ts_offset",
        _decimal_seconds(-start_correction),
        "-frames:v",
        str(frame_count),
    ]
    if suffix in {".mov", ".mp4"}:
        # The adapter rejects time bases at or above half a frame; integer-rate
        # containers therefore need a finer track clock than 1/rate.
        track_timescale = rate.numerator * (1000 if rate.denominator == 1 else 1)
        video_command_list.extend(("-video_track_timescale", str(track_timescale)))
    video_command_list.append(str(video))
    video_command = tuple(video_command_list)
    _run(video_command)
    video_probe, video_probe_hash, video_probe_command = _probe(video, ffprobe)
    _validate_video_probe(video_probe, rate, frame_count, start_pts, codec=video_codec)

    commands: list[tuple[str, ...]] = [video_command, video_probe_command]
    muxed: Path | None = None
    hashes = {"video": _hash_file(video), "audio": _hash_file(audio)}
    probe_hashes = {"video": video_probe_hash}
    if mux_audio is not None:
        muxed = work / f"source-{mux_audio}{suffix}"
        mux_command = _mux_audio(
            video,
            audio,
            muxed,
            start_pts=start_pts,
            codec=mux_audio,
            ffmpeg=ffmpeg,
        )
        mux_probe, mux_probe_hash, mux_probe_command = _probe(muxed, ffprobe)
        _validate_video_probe(
            mux_probe, rate, frame_count, start_pts, codec=video_codec
        )
        commands.extend((mux_command, mux_probe_command))
        hashes["muxed"] = _hash_file(muxed)
        probe_hashes["muxed"] = mux_probe_hash
    return SyntheticMedia(
        path=video,
        audio_path=audio,
        muxed_path=muxed,
        rate=rate,
        frame_count=frame_count,
        start_pts=start_pts,
        flash_frames=markers,
        click_samples=clicks,
        commands=tuple(commands),
        hashes=hashes,
        probe_hashes=probe_hashes,
    )


def decode_frame_ordinals(path: Path, *, ffmpeg: str = "ffmpeg") -> tuple[int, ...]:
    """Decode all video frames and recover their twelve-bit ordinals."""
    command = (
        ffmpeg,
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
    )
    raw = _run(command, output=True)
    frame_size = WIDTH * HEIGHT * 3
    if len(raw) % frame_size:
        raise ValueError("decoded video has a partial RGB frame")
    ordinals: list[int] = []
    for start in range(0, len(raw), frame_size):
        frame = raw[start : start + frame_size]
        value = 0
        for index in range(12):
            row, column = divmod(index, 4)
            x = 4 + column * 15 + 5
            y = 4 + row * 14 + 5
            position = (y * WIDTH + x) * 3
            if sum(frame[position : position + 3]) >= 384:
                value |= 1 << index
        ordinals.append(value)
    return tuple(ordinals)


def assert_decoded_ordinals(
    path: Path, expected: Sequence[tuple[int, int]], *, ffmpeg: str = "ffmpeg"
) -> None:
    """Assert ``(decoded_index, source_ordinal)`` pairs after a real decode."""
    observed = decode_frame_ordinals(path, ffmpeg=ffmpeg)
    for index, ordinal in expected:
        if index < 0 or index >= len(observed) or observed[index] != ordinal:
            raise AssertionError(
                f"decoded ordinal mismatch at {index}: "
                f"expected {ordinal}, observed "
                f"{observed[index] if index < len(observed) else None}"
            )


@contextmanager
def temporary_media_directory() -> Iterator[Path]:
    """Yield an owned temporary directory for callers that need cleanup."""
    with TemporaryDirectory(prefix="vera-issue174-") as directory:
        yield Path(directory)


if __name__ == "__main__":
    with TemporaryDirectory(prefix="vera-issue174-self-check-") as directory:
        fixture = generate_synthetic_media(
            Path(directory),
            frame_count=30,
            flash_frames=(3, 15, 29),
            start_pts=Fraction(2, 1),
        )
        assert_decoded_ordinals(
            fixture.path,
            ((0, 0), (3, 3), (15, 15), (29, 29)),
        )
        print(
            json.dumps(
                {"path": str(fixture.path), "hashes": fixture.hashes},
                sort_keys=True,
            )
        )
