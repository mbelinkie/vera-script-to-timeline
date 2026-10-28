"""Frame-exact, immutable review derivatives for local ingest jobs.

The BuildJobStore adapter owns source lookup and job authorization. This module
owns source/tool identity, per-stage cache publication, and derivative checks.
"""

from __future__ import annotations

import array
import fcntl
import json
import math
import os
import sys
import tempfile
import uuid
import wave
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal, cast

from vera_timeline_agent.media_preparation import (
    MediaInspection,
    MediaPreparationError,
    MediaTools,
    file_hash,
    inspect_media,
)
from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash

Json = dict[str, Any]
ReviewStage = Literal["proxy", "audio", "waveform"]
ProxyMode = Literal["never", "threshold", "always"]

_PROFILE_VERSION = "browser-review-media/v1"
_GENERATOR_VERSION = "review-proxy/v1"
_MAX_WIDTH = 1280
_MAX_HEIGHT = 720
_SOURCE_BITRATE_THRESHOLD = 12_000_000
_PROXY_MAX_BITRATE = 8_000_000
_AUDIO_WINDOW_MS = 100


class ReviewProxyError(MediaPreparationError):
    """A review derivative is unsupported, incomplete, or conflicts with cache."""


@dataclass(frozen=True)
class ReviewProfile:
    mode: ProxyMode = "threshold"

    def document(self) -> Json:
        if self.mode not in {"never", "threshold", "always"}:
            raise ReviewProxyError("invalid_profile", "unknown proxy mode")
        return {
            "version": _PROFILE_VERSION,
            "mode": self.mode,
            "threshold": {
                "maxWidth": _MAX_WIDTH,
                "maxHeight": _MAX_HEIGHT,
                "maxSourceBitrateBps": _SOURCE_BITRATE_THRESHOLD,
            },
            "proxy": {
                "container": "mp4",
                "videoCodec": "h264",
                "videoProfile": "baseline",
                "pixelFormat": "yuv420p",
                "maxWidth": _MAX_WIDTH,
                "maxHeight": _MAX_HEIGHT,
                "maxBitrateBps": _PROXY_MAX_BITRATE,
                "crf": 24,
                "preset": "veryfast",
                "threads": 1,
                "ratePolicy": "source-rate-no-resampling/v1",
                "timePolicy": "frame-index-identity/v1",
            },
            "audio": {
                "container": "wav",
                "codec": "pcm_s16le",
                "sampleRate": "source",
                "channels": "source",
                "alignment": "master-video-origin-with-exact-sample-offset/v1",
            },
            "waveform": {"version": "peak/v1", "windowMs": _AUDIO_WINDOW_MS},
        }


DEFAULT_REVIEW_PROFILE = ReviewProfile()


@dataclass(frozen=True)
class ReviewSource:
    path: Path = field(repr=False)
    inspection: MediaInspection = field(repr=False)
    video_stream_index: int
    audio_stream_index: int | None
    profile: ReviewProfile
    profile_document: Json = field(repr=False)
    profile_hash: str
    tool_identity: Json = field(repr=False)
    tool_hash: str
    generator_hash: str
    generation_identity: str
    tools: MediaTools = field(repr=False, compare=False)


@dataclass(frozen=True)
class StageResult:
    stage: ReviewStage
    generation_identity: str
    bundle_path: Path
    receipt_path: Path
    artifact_path: Path | None
    output_path: Path
    reused: bool
    receipt: Json = field(repr=False)


def _positive_index(value: int, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ReviewProxyError("ambiguous_streams", f"invalid {label} index")
    return value


def _resolve_streams(
    source: Path,
    tools: MediaTools,
    video_stream_index: int | None,
    audio_stream_index: int | None,
) -> tuple[int, int | None]:
    try:
        probe = cast(
            Json,
            json.loads(
                tools.run(
                    [
                        tools.ffprobe,
                        "-v",
                        "error",
                        "-show_streams",
                        "-of",
                        "json",
                        str(source),
                    ]
                )
            ),
        )
        streams = probe["streams"]
        videos = [s for s in streams if s.get("codec_type") == "video"]
        audios = [s for s in streams if s.get("codec_type") == "audio"]
        video = (
            next(s for s in videos if s.get("index") == video_stream_index)
            if video_stream_index is not None
            else videos[0]
            if len(videos) == 1
            else None
        )
        if video is None or (video_stream_index is None and len(videos) != 1):
            raise ValueError("video stream selection is ambiguous")
        selected_video = _positive_index(video["index"], "video")
        if audio_stream_index is not None:
            audio = next(s for s in audios if s.get("index") == audio_stream_index)
        elif len(audios) == 1:
            audio = audios[0]
        elif not audios:
            audio = None
        else:
            raise ValueError("audio stream selection is ambiguous")
        selected_audio = (
            _positive_index(audio["index"], "audio") if audio is not None else None
        )
        return selected_video, selected_audio
    except (KeyError, TypeError, ValueError, StopIteration) as error:
        raise ReviewProxyError(
            "ambiguous_streams", "select one video and at most one audio stream"
        ) from error


def _wire_fraction(value: Fraction) -> Json:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _video_frames(inspection: MediaInspection) -> list[Json]:
    if not inspection.video_frames:
        raise ReviewProxyError("unsupported_vfr_or_timebase", "no decoded video frames")
    rate, time_base = inspection.rate, inspection.time_base
    if rate <= 0 or time_base <= 0:
        raise ReviewProxyError("unsupported_vfr_or_timebase", "invalid source cadence")
    origin = inspection.pts_origin
    for index, frame in enumerate(inspection.video_frames):
        try:
            pts = int(frame["pts"]) * time_base
            duration = int(frame.get("duration") or frame.get("pkt_duration") or 0)
            actual_duration = duration * time_base
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
            raise ReviewProxyError(
                "unsupported_vfr_or_timebase", "missing decoded frame timestamps"
            ) from error
        if pts != origin + Fraction(index, 1) / rate or actual_duration != 1 / rate:
            raise ReviewProxyError(
                "unsupported_vfr_or_timebase",
                "source timestamps do not prove exact constant frame cadence",
            )
    return inspection.video_frames


def inspect_review_source(
    source_path: Path,
    *,
    profile: ReviewProfile = DEFAULT_REVIEW_PROFILE,
    video_stream_index: int | None = None,
    audio_stream_index: int | None = None,
    tools: MediaTools | None = None,
) -> ReviewSource:
    """Inspect one stable source and produce its immutable generation identity."""
    if source_path.is_symlink() or not source_path.is_file():
        raise ReviewProxyError("missing_media", "regular source file required")
    source = source_path.resolve(strict=True)
    media_tools = tools or MediaTools()
    profile_document = profile.document()
    fingerprint = media_tools.fingerprint()
    tool_hash = identity_hash(fingerprint)
    video_index, audio_index = _resolve_streams(
        source, media_tools, video_stream_index, audio_stream_index
    )
    inspection = inspect_media(
        source,
        video_stream_index=video_index,
        audio_stream_index=audio_index,
        tools=media_tools,
    )
    _video_frames(inspection)
    if file_hash(source) != inspection.content_hash:
        raise ReviewProxyError("changed_media", "source changed during inspection")
    if identity_hash(media_tools.fingerprint()) != tool_hash:
        raise ReviewProxyError("changed_tools", "media tools changed during inspection")
    profile_hash = identity_hash(profile_document)
    generator_hash = file_hash(Path(__file__).resolve())
    generation_identity = identity_hash(
        {
            "version": "review-generation/v1",
            "sourceContentHash": inspection.content_hash,
            "sourceProbeHash": inspection.probe_hash,
            "videoStreamIndex": video_index,
            "audioStreamIndex": audio_index,
            "profileHash": profile_hash,
            "toolHash": tool_hash,
            "generatorHash": generator_hash,
        }
    )
    return ReviewSource(
        source,
        inspection,
        video_index,
        audio_index,
        profile,
        profile_document,
        profile_hash,
        fingerprint,
        tool_hash,
        generator_hash,
        generation_identity,
        media_tools,
    )


def _bitrate(inspection: MediaInspection) -> int | None:
    candidates: list[int] = []
    for value in (
        inspection.video.get("bit_rate"),
        inspection.probe.get("format", {}).get("bit_rate"),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            candidates.append(parsed)
    return max(candidates) if candidates else None


def _browser_safe_source(source: ReviewSource) -> bool:
    return _browser_safe_video(source) and _browser_safe_audio(source)


def _browser_safe_video(source: ReviewSource) -> bool:
    video = source.inspection.video
    container = set(
        str(source.inspection.probe.get("format", {}).get("format_name", "")).split(",")
    )
    profile = str(video.get("profile", "")).lower()
    return (
        source.path.suffix.lower() == ".mp4"
        and "mp4" in container
        and video.get("codec_name") == "h264"
        and any(name in profile for name in ("baseline", "main", "high"))
    ) and (
        video.get("pix_fmt") == "yuv420p"
        and video.get("field_order") == "progressive"
        and video.get("sample_aspect_ratio") == "1:1"
        and int(video.get("width", 0)) <= _MAX_WIDTH
        and int(video.get("height", 0)) <= _MAX_HEIGHT
    )


def _browser_safe_audio(source: ReviewSource) -> bool:
    audio = source.inspection.audio
    if audio is None:
        return True
    try:
        sample_rate = int(audio.get("sample_rate", 0))
        channels = int(audio.get("channels", 0))
    except (TypeError, ValueError):
        return False
    return (
        audio.get("codec_name") == "aac"
        and str(audio.get("profile", "")).strip().lower() == "lc"
        and sample_rate in {44100, 48000}
        and channels in {1, 2}
        and audio.get("channel_layout") in {"mono", "stereo"}
    )


def profile_decision(source: ReviewSource) -> Json:
    """Return the bounded profile's proxy choice and its observable reason."""
    mode = source.profile.mode
    video = source.inspection.video
    width, height = int(video["width"]), int(video["height"])
    bitrate = _bitrate(source.inspection)
    video_browser_safe = _browser_safe_video(source)
    audio_browser_safe = _browser_safe_audio(source)
    browser_safe = video_browser_safe and audio_browser_safe
    if mode == "never":
        required, reason = False, "profile_never"
    elif mode == "always":
        required, reason = True, "profile_always"
    else:
        above = (
            width > _MAX_WIDTH
            or height > _MAX_HEIGHT
            or bitrate is None
            or bitrate > _SOURCE_BITRATE_THRESHOLD
        )
        required = above or not browser_safe
        reason = (
            "browser_compatibility"
            if not browser_safe
            else "above_threshold"
            if above
            else "below_threshold"
        )
    return {
        "mode": mode,
        "required": required,
        "reason": reason,
        "masterBrowserSafe": browser_safe,
        "masterVideoBrowserSafe": video_browser_safe,
        "masterAudioBrowserSafe": audio_browser_safe,
        "sourceWidth": width,
        "sourceHeight": height,
        "sourceBitrateBps": bitrate,
    }


def _review_playback(source: ReviewSource, decision: Json) -> Json:
    required = bool(decision["required"])
    master_browser_safe = bool(decision["masterBrowserSafe"])
    video_source = "proxy" if required else "master" if master_browser_safe else None
    audio_required = source.inspection.audio is not None
    return {
        "videoSource": video_source,
        "videoUsable": video_source is not None,
        "masterBrowserSafe": master_browser_safe,
        "videoMuted": True,
        "proxyHasAudio": False,
        "audioSource": "audio-stage" if audio_required else "absent",
        "audioRequired": audio_required,
        "audioSynchronization": (
            "aligned-audio-stage-at-video-origin/v1" if audio_required else "none"
        ),
    }


def _fraction_field(frame: Json, key: str, time_base: Fraction) -> Fraction:
    raw = frame.get(key)
    if raw is None:
        raw = frame.get("pkt_" + key)
    value = int(raw or 0)
    return value * time_base


def _verify_frame_mapping(source: ReviewSource, proxy: MediaInspection) -> Json:
    source_frames = _video_frames(source.inspection)
    proxy_frames = _video_frames(proxy)
    original = source.inspection
    if len(proxy_frames) != len(source_frames) or proxy.rate != original.rate:
        raise ReviewProxyError(
            "output_verification_failed",
            "proxy frame count or rate differs from source",
        )
    proxy_offset = original.pts_origin - proxy.pts_origin
    for source_frame, proxy_frame in zip(source_frames, proxy_frames, strict=True):
        source_pts = _fraction_field(source_frame, "pts", original.time_base)
        proxy_pts = _fraction_field(proxy_frame, "pts", proxy.time_base)
        source_duration = _fraction_field(source_frame, "duration", original.time_base)
        proxy_duration = _fraction_field(proxy_frame, "duration", proxy.time_base)
        if proxy_pts + proxy_offset != source_pts or proxy_duration != source_duration:
            raise ReviewProxyError(
                "output_verification_failed",
                "proxy timestamps do not map to source frames exactly",
            )
    return {
        "method": "frame-index-identity/v1",
        "sourceFrameCount": len(source_frames),
        "proxyFrameCount": len(proxy_frames),
        "sourceRate": _wire_fraction(original.rate),
        "proxyRate": _wire_fraction(proxy.rate),
        "sourcePtsOrigin": _wire_fraction(original.pts_origin),
        "proxyPtsOrigin": _wire_fraction(proxy.pts_origin),
        "proxyToMasterOffset": _wire_fraction(proxy_offset),
        "sourceProbeHash": original.probe_hash,
        "proxyProbeHash": proxy.probe_hash,
        "mappingHash": identity_hash(
            {
                "method": "frame-index-identity/v1",
                "sourceProbeHash": original.probe_hash,
                "proxyProbeHash": proxy.probe_hash,
                "offset": _wire_fraction(proxy_offset),
                "rate": _wire_fraction(original.rate),
                "frameCount": len(source_frames),
            }
        ),
    }


def _proxy_dimensions(width: int, height: int) -> tuple[int, int]:
    scale = min(1.0, _MAX_WIDTH / width, _MAX_HEIGHT / height)
    return max(2, int(width * scale) // 2 * 2), max(2, int(height * scale) // 2 * 2)


def _proxy_command(source: ReviewSource, output: Path) -> list[str]:
    video = source.inspection.video
    width, height = _proxy_dimensions(int(video["width"]), int(video["height"]))
    return [
        source.tools.ffmpeg,
        "-v",
        "error",
        "-nostdin",
        "-n",
        "-copyts",
        "-start_at_zero",
        "-i",
        str(source.path),
        "-map",
        f"0:{source.video_stream_index}",
        "-an",
        "-sn",
        "-dn",
        "-vf",
        f"scale={width}:{height}:flags=lanczos",
        "-frames:v",
        str(len(source.inspection.video_frames)),
        "-fps_mode",
        "passthrough",
        "-c:v",
        "libx264",
        "-profile:v",
        "baseline",
        "-level:v",
        "3.1",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "24",
        "-preset",
        "veryfast",
        "-threads",
        "1",
        "-maxrate",
        "8M",
        "-bufsize",
        "16M",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-color_range",
        str(video["color_range"]),
        "-colorspace",
        str(video["color_space"]),
        "-color_primaries",
        str(video["color_primaries"]),
        "-color_trc",
        str(video["color_transfer"]),
        "-video_track_timescale",
        str(source.inspection.rate.numerator),
        "-movflags",
        "+faststart",
        "-fflags",
        "+bitexact",
        "-f",
        "mp4",
        str(output),
    ]


def _verify_proxy(source: ReviewSource, proxy_path: Path) -> Json:
    proxy = inspect_media(
        proxy_path,
        video_stream_index=0,
        audio_stream_index=None,
        tools=source.tools,
    )
    video = proxy.video
    if (
        proxy_path.suffix.lower() != ".mp4"
        or video.get("codec_name") != "h264"
        or "baseline" not in str(video.get("profile", "")).lower()
        or video.get("pix_fmt") != "yuv420p"
        or video.get("field_order") != "progressive"
        or video.get("sample_aspect_ratio") != "1:1"
    ):
        raise ReviewProxyError(
            "output_verification_failed", "proxy is not a browser-safe H.264 MP4"
        )
    width, height = int(video["width"]), int(video["height"])
    if width > _MAX_WIDTH or height > _MAX_HEIGHT:
        raise ReviewProxyError(
            "output_verification_failed", "proxy exceeds bounded browser dimensions"
        )
    expected_dimensions = _proxy_dimensions(
        int(source.inspection.video["width"]), int(source.inspection.video["height"])
    )
    if (width, height) != expected_dimensions:
        raise ReviewProxyError(
            "output_verification_failed", "proxy dimensions do not match profile"
        )
    return _verify_frame_mapping(source, proxy)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_exclusive(path: Path, content: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _atomic_no_replace(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ReviewProxyError("published_conflict", "symbolic link at immutable path")
    descriptor, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
                raise ReviewProxyError(
                    "published_conflict", "immutable output already has different bytes"
                ) from None
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _fsync_tree(directory: Path) -> None:
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ReviewProxyError(
                "published_conflict", "symbolic link in staged bundle"
            )
        if path.is_file():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
    for path in sorted(
        (p for p in directory.rglob("*") if p.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        _fsync_directory(path)
    _fsync_directory(directory)


@contextmanager
def _cache_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ReviewProxyError("published_conflict", "symbolic cache lock")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _bundle_paths(
    source: ReviewSource, stage: ReviewStage, cache_root: Path
) -> tuple[Path, Path, Path]:
    if stage not in {"proxy", "audio", "waveform"}:
        raise ReviewProxyError("invalid_stage", "unknown review stage")
    if cache_root.is_symlink():
        raise ReviewProxyError("unauthorized_path", "cache root cannot be a symlink")
    root = cache_root.resolve()
    generation = source.generation_identity.removeprefix("sha256:")
    stage_root = root / generation / stage
    bundles = stage_root / "bundles"
    lock = root / ".locks" / f"{generation}-{stage}.lock"
    for path in (root, root / generation, stage_root, bundles, lock.parent):
        if path.is_symlink():
            raise ReviewProxyError("unauthorized_path", "cache path contains a symlink")
        path.mkdir(parents=True, exist_ok=True)
    return stage_root, bundles, lock


def _json_file(path: Path, code: str) -> Json:
    try:
        if path.is_symlink() or not path.is_file():
            raise ValueError("not a regular file")
        raw = path.read_bytes()
        value = cast(Json, json.loads(raw))
        if canonical_json_bytes(value) != raw or not isinstance(value, dict):
            raise ValueError("not canonical JSON object")
        return value
    except (OSError, ValueError, TypeError) as error:
        raise ReviewProxyError(code, "published JSON is missing or invalid") from error


def _artifact_record(path: Path) -> Json:
    if path.is_symlink() or not path.is_file():
        raise ReviewProxyError(
            "output_verification_failed", "stage artifact is missing"
        )
    return {
        "name": path.name,
        "contentHash": file_hash(path),
        "sizeBytes": path.stat().st_size,
    }


def _audio_shape(path: Path) -> tuple[int, int, int, int]:
    try:
        with wave.open(str(path), "rb") as reader:
            shape = (
                reader.getframerate(),
                reader.getnchannels(),
                reader.getsampwidth(),
                reader.getnframes(),
            )
    except (OSError, wave.Error) as error:
        raise ReviewProxyError(
            "output_verification_failed", "invalid derived WAV"
        ) from error
    if shape[0] not in {44100, 48000} or shape[1] not in {1, 2} or shape[2] != 2:
        raise ReviewProxyError(
            "output_verification_failed", "unsupported derived WAV profile"
        )
    return shape


def _write_silence(writer: wave.Wave_write, frames: int, channels: int) -> None:
    chunk_frames = 32768
    while frames:
        count = min(frames, chunk_frames)
        writer.writeframesraw(bytes(count * channels * 2))
        frames -= count


def _audio_alignment(
    inspection: MediaInspection,
) -> tuple[int, int, int, int, int, int, int, Json]:
    audio = inspection.audio
    if audio is None or inspection.audio_origin is None:
        raise ReviewProxyError(
            "unsupported_audio_offset", "selected audio has no decoded origin"
        )
    sample_rate = int(audio["sample_rate"])
    channels = int(audio["channels"])
    offset = inspection.audio_origin - inspection.pts_origin
    offset_samples = offset * sample_rate
    if offset_samples.denominator != 1:
        raise ReviewProxyError(
            "unsupported_audio_offset",
            "audio origin is not on an exact sample boundary",
        )
    audio_length = inspection.audio_samples
    video_frames = len(inspection.video_frames)
    output_frames = math.ceil(Fraction(video_frames, 1) / inspection.rate * sample_rate)
    prefix = max(0, int(offset_samples))
    source_skip = max(0, -int(offset_samples))
    if prefix >= output_frames or source_skip >= audio_length:
        raise ReviewProxyError(
            "unsupported_audio_offset", "audio does not overlap video"
        )
    copy_frames = min(audio_length - source_skip, output_frames - prefix)
    suffix = output_frames - prefix - copy_frames
    evidence = {
        "status": "aligned",
        "sampleRate": sample_rate,
        "channels": channels,
        "sampleWidthBytes": 2,
        "sourceAudioFrames": audio_length,
        "outputAudioFrames": output_frames,
        "sourceVideoFrameCount": video_frames,
        "sourceAudioOrigin": _wire_fraction(inspection.audio_origin),
        "sourceVideoOrigin": _wire_fraction(inspection.pts_origin),
        "audioOffsetFromVideo": _wire_fraction(offset),
        "audioOffsetSamples": int(offset_samples),
        "sourceSamplesSkipped": source_skip,
        "leadingSilenceSamples": prefix,
        "sourceSamplesCopied": copy_frames,
        "trailingSilenceSamples": suffix,
        "sourceTimestampResidual": _wire_fraction(inspection.audio_timestamp_residual),
        "sourceTimestampDrift": _wire_fraction(inspection.audio_timestamp_drift),
    }
    return (
        sample_rate,
        channels,
        output_frames,
        source_skip,
        prefix,
        copy_frames,
        suffix,
        evidence,
    )


def _derive_audio(source: ReviewSource, directory: Path) -> tuple[str | None, Json]:
    inspection = source.inspection
    if inspection.audio is None:
        return None, {"status": "absent"}
    if source.audio_stream_index is None:
        raise ReviewProxyError(
            "unsupported_audio_offset", "selected audio stream index is missing"
        )
    (
        sample_rate,
        channels,
        output_frames,
        source_skip,
        prefix,
        copy_frames,
        suffix,
        evidence,
    ) = _audio_alignment(inspection)
    audio_length = inspection.audio_samples
    raw = directory / "decoded-audio.wav"
    output = directory / "audio.wav"
    source.tools.run(
        [
            source.tools.ffmpeg,
            "-v",
            "error",
            "-nostdin",
            "-n",
            "-i",
            str(source.path),
            "-map",
            f"0:{source.audio_stream_index}",
            "-vn",
            "-sn",
            "-dn",
            "-c:a",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            "-map_metadata",
            "-1",
            "-fflags",
            "+bitexact",
            "-f",
            "wav",
            str(raw),
        ]
    )
    try:
        with wave.open(str(raw), "rb") as reader:
            if (
                reader.getframerate() != sample_rate
                or reader.getnchannels() != channels
                or reader.getsampwidth() != 2
                or reader.getnframes() != audio_length
            ):
                raise ReviewProxyError(
                    "output_verification_failed",
                    "decoded audio sample count differs from probe",
                )
            with output.open("xb") as stream, wave.open(stream, "wb") as writer:
                writer.setnchannels(channels)
                writer.setsampwidth(2)
                writer.setframerate(sample_rate)
                _write_silence(writer, prefix, channels)
                reader.setpos(source_skip)
                remaining = copy_frames
                while remaining:
                    count = min(remaining, 32768)
                    data = reader.readframes(count)
                    frame_bytes = channels * 2
                    if not data or len(data) % frame_bytes:
                        raise ReviewProxyError(
                            "output_verification_failed",
                            "decoded audio ended early",
                        )
                    writer.writeframesraw(data)
                    remaining -= len(data) // frame_bytes
                _write_silence(writer, suffix, channels)
    except (OSError, wave.Error) as error:
        raise ReviewProxyError(
            "output_verification_failed", "audio extraction is invalid"
        ) from error
    raw.unlink(missing_ok=True)
    rate, out_channels, width, frames = _audio_shape(output)
    if (rate, out_channels, width, frames) != (sample_rate, channels, 2, output_frames):
        raise ReviewProxyError(
            "output_verification_failed", "aligned audio WAV has wrong shape"
        )
    return output.name, evidence


def _read_audio_peaks(path: Path) -> Json:
    before = file_hash(path)
    try:
        with wave.open(str(path), "rb") as reader:
            sample_rate, channels, width = (
                reader.getframerate(),
                reader.getnchannels(),
                reader.getsampwidth(),
            )
            if width != 2:
                raise ReviewProxyError(
                    "output_verification_failed", "waveform expects PCM16"
                )
            window_samples = sample_rate * _AUDIO_WINDOW_MS // 1000
            if window_samples < 1 or sample_rate * _AUDIO_WINDOW_MS % 1000:
                raise ReviewProxyError(
                    "invalid_profile", "waveform window is not sample exact"
                )
            peaks: list[list[int]] = []
            current = [0] * channels
            in_window = 0
            remaining = reader.getnframes()
            while remaining:
                data = reader.readframes(min(32768, remaining))
                remaining -= len(data) // (channels * width)
                samples = array.array("h")
                samples.frombytes(data)
                if sys.byteorder != "little":
                    samples.byteswap()
                for offset in range(0, len(samples), channels):
                    for channel in range(channels):
                        current[channel] = max(
                            current[channel], abs(samples[offset + channel])
                        )
                    in_window += 1
                    if in_window == window_samples:
                        peaks.append(current)
                        current = [0] * channels
                        in_window = 0
                if not data and remaining:
                    raise ReviewProxyError(
                        "output_verification_failed", "truncated audio WAV"
                    )
            if in_window:
                peaks.append(current)
            result = {
                "version": "peak/v1",
                "audioHash": before,
                "sampleRate": sample_rate,
                "channels": channels,
                "sampleWidthBytes": width,
                "windowSamples": window_samples,
                "windowMs": _AUDIO_WINDOW_MS,
                "frameCount": reader.getnframes(),
                "peaks": peaks,
            }
    except (OSError, wave.Error) as error:
        raise ReviewProxyError(
            "output_verification_failed", "invalid audio for waveform"
        ) from error
    if file_hash(path) != before:
        raise ReviewProxyError(
            "changed_media", "audio derivative changed during waveform generation"
        )
    return result


def _base_receipt(source: ReviewSource, stage: ReviewStage) -> Json:
    return {
        "schemaVersion": 1,
        "stage": stage,
        "generatorVersion": _GENERATOR_VERSION,
        "generatorHash": source.generator_hash,
        "generationIdentity": source.generation_identity,
        "source": {
            "contentHash": source.inspection.content_hash,
            "probeHash": source.inspection.probe_hash,
            "videoStreamIndex": source.video_stream_index,
            "audioStreamIndex": source.audio_stream_index,
        },
        "profile": source.profile_document,
        "profileHash": source.profile_hash,
        "toolIdentity": source.tool_identity,
        "toolHash": source.tool_hash,
    }


def _verify_current(source: ReviewSource) -> None:
    if file_hash(source.path) != source.inspection.content_hash:
        raise ReviewProxyError("changed_media", "source changed since inspection")
    if identity_hash(source.tools.fingerprint()) != source.tool_hash:
        raise ReviewProxyError(
            "changed_tools", "tool identity changed since inspection"
        )
    if file_hash(Path(__file__).resolve()) != source.generator_hash:
        raise ReviewProxyError(
            "changed_generator", "review generator changed during stage"
        )


def _verify_audio_bundle(
    source: ReviewSource, bundle: Path, receipt: Json
) -> Path | None:
    artifact = receipt.get("artifact")
    evidence = receipt.get("evidence")
    if source.inspection.audio is None:
        if artifact is not None or evidence != {"status": "absent"}:
            raise ReviewProxyError(
                "published_conflict", "audio absence receipt differs"
            )
        return None
    if not isinstance(evidence, dict):
        raise ReviewProxyError("published_conflict", "audio evidence is missing")
    if not isinstance(artifact, dict) or artifact.get("name") != "audio.wav":
        raise ReviewProxyError("published_conflict", "audio artifact record is missing")
    path = bundle / "audio.wav"
    actual = _artifact_record(path)
    if actual != artifact:
        raise ReviewProxyError(
            "published_conflict", "audio derivative is missing or corrupt"
        )
    rate, channels, width, frames = _audio_shape(path)
    expected = _audio_alignment(source.inspection)
    if (rate, channels, width, frames) != (
        expected[0],
        expected[1],
        2,
        expected[2],
    ) or evidence != expected[-1]:
        raise ReviewProxyError("published_conflict", "audio alignment evidence differs")
    return path


def _verify_waveform_bundle(
    source: ReviewSource, bundle: Path, receipt: Json, cache_root: Path
) -> Path | None:
    artifact = receipt.get("artifact")
    if source.inspection.audio is None:
        if artifact is not None or receipt.get("evidence") != {"status": "absent"}:
            raise ReviewProxyError(
                "published_conflict", "waveform absence receipt differs"
            )
        return None
    if not isinstance(artifact, dict) or artifact.get("name") != "waveform.json":
        raise ReviewProxyError(
            "published_conflict", "waveform artifact record is missing"
        )
    audio_root = (
        cache_root.resolve()
        / source.generation_identity.removeprefix("sha256:")
        / "audio"
    )
    audio = _load_bundle(
        source, "audio", audio_root, audio_root / "bundles", cache_root.resolve()
    )
    if audio is None:
        raise ReviewProxyError(
            "published_conflict", "audio dependency is not published"
        )
    audio_path = audio.artifact_path
    if audio_path is None:
        raise ReviewProxyError("published_conflict", "waveform has no audio dependency")
    waveform_path = bundle / "waveform.json"
    actual = _artifact_record(waveform_path)
    if actual != artifact:
        raise ReviewProxyError(
            "published_conflict", "waveform derivative is missing or corrupt"
        )
    waveform = _json_file(waveform_path, "published_conflict")
    if (
        waveform.get("version") != "peak/v1"
        or waveform.get("audioHash") != file_hash(audio_path)
        or receipt.get("evidence")
        != {
            "status": "ready",
            "audioHash": file_hash(audio_path),
            "windowMs": _AUDIO_WINDOW_MS,
        }
    ):
        raise ReviewProxyError(
            "published_conflict", "waveform does not match audio derivative"
        )
    return waveform_path


def _receipt_hash(receipt: Json) -> str:
    return identity_hash(receipt)


def _load_bundle(
    source: ReviewSource,
    stage: ReviewStage,
    stage_root: Path,
    bundles_root: Path,
    cache_root: Path,
    *,
    bundle_id: str | None = None,
) -> StageResult | None:
    pointer_path = stage_root / "published.json"
    if bundle_id is None:
        if not pointer_path.exists():
            return None
        pointer = _json_file(pointer_path, "published_conflict")
        bundle_id = pointer.get("bundleId")
        if (
            not isinstance(bundle_id, str)
            or len(bundle_id) != 32
            or any(character not in "0123456789abcdef" for character in bundle_id)
        ):
            raise ReviewProxyError(
                "published_conflict", "invalid published bundle pointer"
            )
    bundle = bundles_root / bundle_id
    if bundle.is_symlink() or not bundle.is_dir():
        raise ReviewProxyError("published_conflict", "published bundle is missing")
    receipt_path = bundle / "receipt.json"
    receipt = _json_file(receipt_path, "published_conflict")
    if (
        receipt.get("stage") != stage
        or receipt.get("generationIdentity") != source.generation_identity
        or receipt.get("generatorVersion") != _GENERATOR_VERSION
        or receipt.get("generatorHash") != source.generator_hash
        or receipt.get("source") != _base_receipt(source, stage)["source"]
        or receipt.get("profile") != source.profile_document
        or receipt.get("profileHash") != source.profile_hash
        or receipt.get("toolIdentity") != source.tool_identity
        or receipt.get("toolHash") != source.tool_hash
    ):
        raise ReviewProxyError(
            "published_conflict", "bundle identity differs from request"
        )
    evidence = receipt.get("evidence")
    if not isinstance(evidence, dict):
        raise ReviewProxyError("published_conflict", "stage evidence is missing")
    if pointer_path.exists():
        pointer = _json_file(pointer_path, "published_conflict")
        if pointer.get("bundleId") != bundle_id or pointer.get(
            "receiptHash"
        ) != _receipt_hash(receipt):
            raise ReviewProxyError(
                "published_conflict", "published pointer checksum differs"
            )
    artifact: Path | None
    if stage == "proxy":
        decision = profile_decision(source)
        if (
            evidence.get("decision") != decision
            or evidence.get("proxyHasAudio") is not False
            or evidence.get("reviewPlayback") != _review_playback(source, decision)
        ):
            raise ReviewProxyError(
                "published_conflict", "proxy profile decision differs"
            )
        record = receipt.get("artifact")
        if decision["required"]:
            if not isinstance(record, dict) or record.get("name") != "proxy.mp4":
                raise ReviewProxyError(
                    "published_conflict", "proxy artifact record is missing"
                )
            artifact = bundle / "proxy.mp4"
            if _artifact_record(artifact) != record:
                raise ReviewProxyError(
                    "published_conflict", "proxy artifact is missing or corrupt"
                )
            mapping = _verify_proxy(source, artifact)
            if evidence.get("frameMap") != mapping:
                raise ReviewProxyError(
                    "published_conflict", "proxy frame mapping evidence differs"
                )
        else:
            if evidence.get("frameMap") is not None:
                raise ReviewProxyError(
                    "published_conflict", "skipped proxy has frame mapping evidence"
                )
            if record is not None:
                raise ReviewProxyError(
                    "published_conflict", "skipped proxy has a derivative"
                )
            artifact = None
    elif stage == "audio":
        artifact = _verify_audio_bundle(source, bundle, receipt)
    else:
        artifact = _verify_waveform_bundle(source, bundle, receipt, cache_root)
    output_bytes = 0 if artifact is None else artifact.stat().st_size
    if receipt.get("totalOutputBytes") != output_bytes:
        raise ReviewProxyError(
            "published_conflict", "stage output space accounting differs"
        )
    _verify_current(source)
    return StageResult(
        stage,
        source.generation_identity,
        bundle,
        receipt_path,
        artifact,
        Path(),
        True,
        receipt,
    )


def _scan_recoverable(
    source: ReviewSource,
    stage: ReviewStage,
    stage_root: Path,
    bundles_root: Path,
    cache_root: Path,
) -> StageResult | None:
    candidates: list[StageResult] = []
    for candidate in sorted(bundles_root.iterdir()):
        if candidate.name.startswith(".pending-") or not candidate.is_dir():
            continue
        if not (candidate / "receipt.json").exists():
            continue
        result = _load_bundle(
            source,
            stage,
            stage_root,
            bundles_root,
            cache_root,
            bundle_id=candidate.name,
        )
        if result is not None:
            candidates.append(result)
    if len(candidates) > 1:
        hashes = {
            None if item.artifact_path is None else file_hash(item.artifact_path)
            for item in candidates
        }
        if len(hashes) > 1:
            raise ReviewProxyError(
                "published_conflict", "multiple valid but different cache bundles exist"
            )
    return candidates[0] if candidates else None


def _publish_pointer(stage_root: Path, result: StageResult) -> Json:
    receipt_hash = _receipt_hash(result.receipt)
    pointer = {"bundleId": result.bundle_path.name, "receiptHash": receipt_hash}
    _atomic_no_replace(stage_root / "published.json", canonical_json_bytes(pointer))
    return pointer


def _job_marker(source: ReviewSource, stage: ReviewStage, pointer: Json) -> bytes:
    return canonical_json_bytes(
        {
            "generationIdentity": source.generation_identity,
            "stage": stage,
            "bundleId": pointer["bundleId"],
            "receiptHash": pointer["receiptHash"],
        }
    )


def _result_with_output(
    result: StageResult, output_path: Path, *, reused: bool
) -> StageResult:
    return StageResult(
        result.stage,
        result.generation_identity,
        result.bundle_path,
        result.receipt_path,
        result.artifact_path,
        output_path,
        reused,
        result.receipt,
    )


def _proxy_stage(source: ReviewSource, directory: Path) -> tuple[str | None, Json]:
    decision = profile_decision(source)
    evidence = {
        "decision": decision,
        "frameMap": None,
        "proxyHasAudio": False,
        "reviewPlayback": _review_playback(source, decision),
    }
    if not decision["required"]:
        return None, evidence
    output = directory / "proxy.mp4"
    source.tools.run(_proxy_command(source, output))
    mapping = _verify_proxy(source, output)
    evidence["frameMap"] = mapping
    return output.name, evidence


def _audio_stage(source: ReviewSource, directory: Path) -> tuple[str | None, Json]:
    return _derive_audio(source, directory)


def _waveform_stage(
    source: ReviewSource, directory: Path, cache_root: Path
) -> tuple[str | None, Json]:
    if source.inspection.audio is None:
        return None, {"status": "absent"}
    audio_root = (
        cache_root.resolve()
        / source.generation_identity.removeprefix("sha256:")
        / "audio"
    )
    audio = _load_bundle(
        source, "audio", audio_root, audio_root / "bundles", cache_root.resolve()
    )
    if audio is None:
        raise ReviewProxyError(
            "audio_dependency_missing", "audio stage is not published"
        )
    audio_path = audio.artifact_path
    if audio_path is None:
        return None, {"status": "absent"}
    waveform = _read_audio_peaks(audio_path)
    output = directory / "waveform.json"
    _write_exclusive(output, canonical_json_bytes(waveform))
    return output.name, {
        "status": "ready",
        "audioHash": file_hash(audio_path),
        "windowMs": _AUDIO_WINDOW_MS,
    }


def _execute_stage(
    source: ReviewSource,
    stage: ReviewStage,
    directory: Path,
    cache_root: Path,
) -> tuple[str | None, Json]:
    if stage == "proxy":
        return _proxy_stage(source, directory)
    if stage == "audio":
        return _audio_stage(source, directory)
    return _waveform_stage(source, directory, cache_root)


def run_review_stage(
    source: ReviewSource,
    stage: ReviewStage,
    *,
    cache_root: Path,
    output_path: Path,
) -> StageResult:
    """Create or verify one stage, then publish its BuildJobStore marker."""
    _verify_current(source)
    stage_root, bundles_root, lock_path = _bundle_paths(source, stage, cache_root)
    if output_path.resolve() == source.path:
        raise ReviewProxyError("unauthorized_path", "stage output cannot be the source")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with _cache_lock(lock_path):
        if output_path.is_symlink():
            raise ReviewProxyError(
                "published_conflict", "stage marker is a symbolic link"
            )
        if output_path.exists() and not output_path.is_file():
            raise ReviewProxyError(
                "published_conflict", "stage marker is not a regular file"
            )
        result = _load_bundle(
            source, stage, stage_root, bundles_root, cache_root.resolve()
        )
        if result is None:
            result = _scan_recoverable(
                source, stage, stage_root, bundles_root, cache_root.resolve()
            )
            if result is None:
                attempt = Path(tempfile.mkdtemp(prefix=".pending-", dir=bundles_root))
                artifact_name, evidence = _execute_stage(
                    source, stage, attempt, cache_root.resolve()
                )
                _verify_current(source)
                artifact = (
                    _artifact_record(attempt / artifact_name)
                    if artifact_name is not None
                    else None
                )
                receipt = _base_receipt(source, stage)
                receipt.update(
                    {
                        "artifact": artifact,
                        "evidence": evidence,
                        "totalOutputBytes": 0
                        if artifact is None
                        else artifact["sizeBytes"],
                    }
                )
                _write_exclusive(
                    attempt / "receipt.json", canonical_json_bytes(receipt)
                )
                _fsync_tree(attempt)
                bundle_id = uuid.uuid4().hex
                bundle = bundles_root / bundle_id
                if bundle.exists() or bundle.is_symlink():
                    raise ReviewProxyError("published_conflict", "bundle ID collision")
                os.rename(attempt, bundle)
                _fsync_directory(bundles_root)
                result = StageResult(
                    stage,
                    source.generation_identity,
                    bundle,
                    bundle / "receipt.json",
                    None if artifact is None else bundle / str(artifact["name"]),
                    output_path,
                    False,
                    receipt,
                )
            pointer = _publish_pointer(stage_root, result)
            # Verify the newly committed bundle through the same path used on retry.
            verified = _load_bundle(
                source, stage, stage_root, bundles_root, cache_root.resolve()
            )
            if verified is None:
                raise ReviewProxyError(
                    "published_conflict", "cache commit pointer is missing"
                )
            result = _result_with_output(verified, output_path, reused=result.reused)
        else:
            pointer = _json_file(stage_root / "published.json", "published_conflict")
            result = _result_with_output(result, output_path, reused=True)
        _verify_current(source)
        _atomic_no_replace(output_path, _job_marker(source, stage, pointer))
        return result


def verify_review_stage(
    source: ReviewSource,
    stage: ReviewStage,
    *,
    cache_root: Path,
    output_path: Path,
) -> StageResult | None:
    """Return a verified completed stage, None when absent, and refuse corruption."""
    stage_root, bundles_root, lock_path = _bundle_paths(source, stage, cache_root)
    if output_path.is_symlink():
        raise ReviewProxyError("published_conflict", "stage marker is a symbolic link")
    with _cache_lock(lock_path):
        if not output_path.exists():
            return None
        result = _load_bundle(
            source, stage, stage_root, bundles_root, cache_root.resolve()
        )
        if result is None:
            raise ReviewProxyError(
                "published_conflict", "stage marker has no cache bundle"
            )
        pointer = _json_file(stage_root / "published.json", "published_conflict")
        expected = _job_marker(source, stage, pointer)
        if not output_path.is_file() or output_path.read_bytes() != expected:
            raise ReviewProxyError(
                "published_conflict", "BuildJobStore marker is corrupt"
            )
        _verify_current(source)
        return _result_with_output(result, output_path, reused=True)
