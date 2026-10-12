"""Immutable authoring-cfr/v1 preparation, without acquisition or gain processing."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import jsonschema  # type: ignore[import-untyped]
from referencing import Registry, Resource

from vera_timeline_agent.generated.contracts.compiler_dependencies_v2_schema import (
    OccurrenceMediaResolutionV2,
    PreparedMediaBindingV1,
    RationalRate,
    RequestedPreparationRangeV1,
)
from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash

Json = dict[str, Any]
TARGET = Fraction(24000, 1001)
SOURCE_RATES = {TARGET, Fraction(24), Fraction(25), Fraction(30000, 1001), Fraction(30)}
POLICY = {
    "version": "cfr_sample/v1",
    "sampling": "I+floor(j*Fs/T)",
    "endpoints": "half-open/ceil",
    "audio": "pcm24-48000/no-processing",
}
PROFILE = {
    "version": "authoring-cfr/v1",
    "codec": "libx264",
    "profile": "high",
    "pix_fmt": "yuv420p",
    "crf": 18,
    "preset": "medium",
    "threads": 1,
    "timestamps": "verified-frame-index-rational/v1",
    "metadata": "qualified-SDR-only",
}
POLICY_HASH = identity_hash(POLICY)
PROFILE_HASH = identity_hash(PROFILE)
MAX_SAFE = 2**53 - 1


class MediaPreparationError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def wire(value: Fraction) -> Json:
    if abs(value.numerator) > MAX_SAFE or value.denominator > MAX_SAFE:
        raise MediaPreparationError(
            "invalid_mapping", "rational exceeds safe wire bounds"
        )
    return {"numerator": value.numerator, "denominator": value.denominator}


def rational(value: Json | RationalRate, *, positive: bool = False) -> Fraction:
    n, d = value["numerator"], value["denominator"]
    if (
        type(n) is not int
        or type(d) is not int
        or abs(n) > MAX_SAFE
        or not 0 < d <= MAX_SAFE
        or n < 0
        or math.gcd(n, d) != 1
        or (positive and n == 0)
    ):
        raise MediaPreparationError("invalid_mapping", "expected reduced safe rational")
    return Fraction(n, d)


def safe_integer(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= MAX_SAFE:
        raise MediaPreparationError(
            "invalid_mapping", "expected nonnegative safe frame index"
        )
    return value


def _validate(value: object, definition: str) -> None:
    directory = Path(__file__).resolve().parents[2] / "contracts"
    schemas = [
        json.loads((directory / name).read_bytes())
        for name in (
            "script-document-v2.schema.json",
            "compiler-dependencies-v2.schema.json",
        )
    ]
    registry: Registry[Any] = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )
    schema = {
        "$id": schemas[1]["$id"],
        "$defs": schemas[1]["$defs"],
        "$ref": f"#/$defs/{definition}",
    }
    error = next(
        jsonschema.Draft202012Validator(
            schema, registry=registry, format_checker=jsonschema.FormatChecker()
        ).iter_errors(value),
        None,
    )
    if error:
        raise MediaPreparationError(
            "invalid_mapping", f"{definition} at {error.json_path}: {error.message}"
        )


def file_hash(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise MediaPreparationError(
            "missing_media", f"regular immutable file required: {path}"
        )
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise MediaPreparationError("changed_media", f"changed while hashing: {path}")
    return "sha256:" + digest.hexdigest()


@dataclass(frozen=True)
class PreparationGeometry:
    source_rate: Fraction
    target_rate: Fraction
    start: Fraction
    end: Fraction
    first_package_frame: int
    required_end_frame: int
    frame_count: int
    cover_surplus: Fraction
    terminal_quantization: Fraction

    def selected_package_frame(self, output_frame: int) -> int:
        return math.floor(
            (self.start + output_frame / self.target_rate) * self.source_rate
        )


def preparation_geometry(
    *,
    source_rate: Fraction,
    target_rate: Fraction,
    origin_frame: int,
    lower_frame: int,
    upper_frame: int,
    in_frame: int,
    duration: Fraction,
    pre_handle: Fraction = Fraction(0),
    post_handle: Fraction = Fraction(0),
) -> PreparationGeometry:
    for index in (origin_frame, lower_frame, upper_frame, in_frame):
        safe_integer(index)
    if (
        source_rate <= 0
        or target_rate <= 0
        or duration <= 0
        or min(pre_handle, post_handle) < 0
    ):
        raise MediaPreparationError(
            "invalid_mapping", "positive rates/duration required"
        )
    if source_rate != target_rate and (
        target_rate != TARGET or source_rate not in SOURCE_RATES
    ):
        raise MediaPreparationError(
            "unsupported_conversion", "only qualified rates into 24000/1001"
        )
    if any(
        (handle * target_rate).denominator != 1 for handle in (pre_handle, post_handle)
    ):
        raise MediaPreparationError(
            "unsupported_handles", "handles must be whole target frames"
        )
    start = Fraction(in_frame - origin_frame, 1) / source_rate - pre_handle
    end = Fraction(in_frame - origin_frame, 1) / source_rate + duration + post_handle
    first = math.floor(start * source_rate)
    exclusive = math.ceil(end * source_rate)
    if not (
        origin_frame <= lower_frame <= in_frame < upper_frame
        and origin_frame + first >= lower_frame
        and origin_frame + exclusive <= upper_frame
    ):
        raise MediaPreparationError(
            "source_shortage", "requested interval/handles exceed authorized bounds"
        )
    count = math.ceil((end - start) * target_rate)
    safe_integer(count)
    return PreparationGeometry(
        source_rate,
        target_rate,
        start,
        end,
        first,
        origin_frame + exclusive,
        count,
        Fraction(exclusive, 1) / source_rate - end,
        Fraction(count, 1) / target_rate - (end - start),
    )


def verify_video_cadence(
    frames: list[Json], rate: Fraction, time_base: Fraction
) -> Fraction:
    if not frames or rate <= 0 or not 0 < time_base < 1 / rate / 2:
        raise MediaPreparationError(
            "unsupported_vfr_or_timebase", "missing frames or coarse timebase"
        )
    try:
        origin = int(frames[0]["pts"]) * time_base
        previous = origin - 1 / rate
        for index, frame in enumerate(frames):
            pts = int(frame["pts"]) * time_base
            duration = (
                int(frame.get("duration") or frame.get("pkt_duration") or 0) * time_base
            )
            if (
                pts <= previous
                or abs(pts - origin - index / rate) > time_base
                or abs(duration - 1 / rate) > time_base
            ):
                raise ValueError("cadence/duration")
            if frame.get("interlaced_frame") != 0:
                raise MediaPreparationError(
                    "unsupported_profile", "interlaced decoded picture"
                )
            previous = pts
        if origin < 0:
            raise ValueError("negative origin")
        return origin
    except (KeyError, TypeError, ValueError) as error:
        raise MediaPreparationError(
            "unsupported_vfr_or_timebase", "decoded PTS/duration is not CFR"
        ) from error


class MediaTools:
    def __init__(
        self,
        ffmpeg: str = "ffmpeg",
        ffprobe: str = "ffprobe",
        cancel: threading.Event | None = None,
    ) -> None:
        self.ffmpeg, self.ffprobe, self.cancel = ffmpeg, ffprobe, cancel
        self.commands: list[list[str]] = []

    def check_cancel(self) -> None:
        if self.cancel is not None and self.cancel.is_set():
            raise MediaPreparationError(
                "cancelled", "attempt retained without publication"
            )

    def run(self, command: list[str], *, timeout: float = 600) -> bytes:
        self.check_cancel()
        self.commands.append(command)
        try:
            with subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            ) as process:
                elapsed = 0.0
                while True:
                    try:
                        stdout, stderr = process.communicate(timeout=0.1)
                        break
                    except subprocess.TimeoutExpired:
                        elapsed += 0.1
                        if elapsed >= timeout or (
                            self.cancel is not None and self.cancel.is_set()
                        ):
                            process.terminate()
                            try:
                                process.communicate(timeout=2)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.communicate()
                            self.check_cancel()
                            raise MediaPreparationError(
                                "tool_timeout", command[0]
                            ) from None
                if process.returncode != 0 or ("-v" in command and stderr.strip()):
                    raise MediaPreparationError(
                        "decode_or_tool_failure",
                        stderr.decode(errors="replace")[-4000:],
                    )
                self.check_cancel()
                return stdout
        except OSError as error:
            raise MediaPreparationError("tool_unavailable", command[0]) from error

    def fingerprint(self) -> Json:
        outputs = [
            self.run([self.ffmpeg, "-version"]).decode(),
            self.run([self.ffprobe, "-version"]).decode(),
            self.run([self.ffmpeg, "-hide_banner", "-encoders"]).decode(),
            self.run([self.ffmpeg, "-hide_banner", "-filters"]).decode(),
        ]
        if any(
            name not in "\n".join(outputs)
            for name in ("libx264", "pcm_s24le", "fps", "settb", "atrim", "aresample")
        ):
            raise MediaPreparationError(
                "unsupported_tools", "missing required codecs/filters"
            )
        binaries = []
        libraries: dict[str, str] = {}
        for executable in (self.ffmpeg, self.ffprobe):
            located = shutil.which(executable)
            if not located:
                raise MediaPreparationError("tool_unavailable", executable)
            binary = Path(located).resolve()
            binaries.append(file_hash(binary))
            if platform.system() == "Darwin":
                linked = self.run(["otool", "-L", str(binary)]).decode()
                names = [
                    line.strip().split(" (", 1)[0] for line in linked.splitlines()[1:]
                ]
            elif platform.system() == "Linux":
                linked = self.run(["ldd", str(binary)]).decode()
                names = [part for part in linked.split() if part.startswith("/")]
            else:
                raise MediaPreparationError(
                    "unsupported_tools", "unqualified platform linker"
                )
            for name in names:
                library = Path(name).resolve()
                if library.is_file():
                    libraries[str(library)] = file_hash(library)
                elif not name.startswith(("/System/Library/", "/usr/lib/")):
                    raise MediaPreparationError(
                        "unsupported_tools", "unresolved linked library"
                    )
        return {
            "adapterSourceHash": file_hash(Path(__file__).resolve()),
            "versionsAndCapabilities": outputs,
            "binaryHashes": binaries,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "linkedLibraryHashes": libraries,
        }


@dataclass(frozen=True)
class MediaInspection:
    probe: Json
    probe_hash: str
    content_hash: str
    video: Json
    video_frames: list[Json]
    rate: Fraction
    time_base: Fraction
    pts_origin: Fraction
    audio: Json | None
    audio_frames: list[Json]
    audio_origin: Fraction | None
    audio_samples: int
    audio_hash: str | None
    audio_timestamp_residual: Fraction
    audio_timestamp_drift: Fraction


def inspect_media(
    path: Path,
    *,
    video_stream_index: int,
    audio_stream_index: int | None,
    tools: MediaTools,
) -> MediaInspection:
    content_hash = file_hash(path)
    probe = cast(
        Json,
        json.loads(
            tools.run(
                [
                    tools.ffprobe,
                    "-v",
                    "error",
                    "-show_streams",
                    "-show_frames",
                    "-show_format",
                    "-of",
                    "json",
                    str(path),
                ]
            )
        ),
    )
    probe["format"].pop("filename", None)
    container = probe["format"]["format_name"].split(",")
    if not (set(container) & {"mov", "mp4", "matroska"}) or path.suffix.lower() not in {
        ".mp4",
        ".mov",
        ".mkv",
    }:
        raise MediaPreparationError("unsupported_profile", "MP4/MOV/MKV required")
    streams = {stream["index"]: stream for stream in probe["streams"]}
    video = streams.get(video_stream_index)
    audio = streams.get(audio_stream_index) if audio_stream_index is not None else None
    if (
        not video
        or video["codec_type"] != "video"
        or (
            audio_stream_index is not None
            and (not audio or audio["codec_type"] != "audio")
        )
    ):
        raise MediaPreparationError(
            "ambiguous_streams", "explicit selected stream indices do not resolve"
        )
    if audio is None and any(s["codec_type"] == "audio" for s in streams.values()):
        raise MediaPreparationError(
            "ambiguous_streams", "select the audio stream explicitly"
        )
    frames = [f for f in probe["frames"] if f["stream_index"] == video_stream_index]
    video = dict(video)
    # Matroska can omit stream colour fields while the decoded bitstream retains them.
    for field, allowed in (
        ("color_space", {"bt709", "bt470bg", "smpte170m"}),
        ("color_primaries", {"bt709", "bt470bg", "smpte170m"}),
        ("color_transfer", {"bt709", "smpte170m", "gamma22", "gamma28"}),
        ("color_range", {"tv", "pc"}),
    ):
        values = {frame.get(field) for frame in frames}
        if len(values) != 1 or not values <= allowed:
            raise MediaPreparationError(
                "unsupported_profile", "decoded SDR metadata missing or changes"
            )
        value = next(iter(values))
        if video.get(field) not in {None, "unknown", value}:
            raise MediaPreparationError(
                "unsupported_profile", "stream/decoded colour metadata conflict"
            )
        video[field] = value
    if (
        video.get("codec_name") not in {"h264", "hevc"}
        or video.get("pix_fmt") not in {"yuv420p", "yuvj420p"}
        or video.get("field_order") != "progressive"
        or video.get("sample_aspect_ratio") != "1:1"
        or not 0 < video["width"] <= 3840
        or not 0 < video["height"] <= 2160
        or video["width"] % 2
        or video["height"] % 2
        or video.get("color_space") not in {"bt709", "bt470bg", "smpte170m"}
        or video.get("color_primaries") not in {"bt709", "bt470bg", "smpte170m"}
        or video.get("color_transfer")
        not in {"bt709", "smpte170m", "gamma22", "gamma28"}
        or video.get("color_range") not in {"tv", "pc"}
        or video.get("side_data_list")
        or "timecode" in video.get("tags", {})
        or "timecode" in probe["format"].get("tags", {})
    ):
        raise MediaPreparationError(
            "unsupported_profile",
            "progressive 8-bit square-pixel qualified SDR required",
        )
    if any(
        frame.get("width") != video["width"]
        or frame.get("height") != video["height"]
        or frame.get("pix_fmt") != video["pix_fmt"]
        or frame.get("sample_aspect_ratio") != "1:1"
        for frame in frames
    ):
        raise MediaPreparationError(
            "unsupported_profile", "decoded geometry/profile changes"
        )
    if any(
        f.get("side_data_list")
        and any(
            s.get("side_data_type") != "H.26[45] User Data Unregistered SEI message"
            for s in f["side_data_list"]
        )
        for f in frames
    ):
        raise MediaPreparationError(
            "unsupported_profile", "unhandled decoded picture side data"
        )
    try:
        rate = Fraction(video["avg_frame_rate"])
        time_base = Fraction(video["time_base"])
        if rate != Fraction(video["r_frame_rate"]):
            raise ValueError("conflicting rate labels")
    except (KeyError, ValueError, ZeroDivisionError) as error:
        raise MediaPreparationError(
            "unsupported_vfr_or_timebase", "invalid rate/timebase labels"
        ) from error
    origin = verify_video_cadence(frames, rate, time_base)
    audio_frames = [
        f for f in probe["frames"] if f["stream_index"] == audio_stream_index
    ]
    audio_origin, samples, audio_hash = None, 0, None
    audio_residual, audio_drift = Fraction(0), Fraction(0)
    if audio is not None:
        if (
            audio.get("codec_name")
            not in {
                "aac",
                "pcm_s16le",
                "pcm_s24le",
                "pcm_s32le",
                "pcm_f32le",
                "pcm_s16be",
                "pcm_s24be",
            }
            or int(audio.get("sample_rate", 0)) not in {44100, 48000}
            or audio.get("channels") not in {1, 2}
            or audio.get("channel_layout") not in {"mono", "stereo"}
            or not audio_frames
        ):
            raise MediaPreparationError(
                "unsupported_profile", "selected AAC/PCM mono/stereo 44.1/48k required"
            )
        sample_rate = int(audio["sample_rate"])
        audio_base = Fraction(audio["time_base"])
        if not 0 < audio_base <= Fraction(1, 1000):
            raise MediaPreparationError(
                "unsupported_audio_offset", "audio timestamp precision exceeds 1ms"
            )
        audio_origin = int(audio_frames[0]["pts"]) * audio_base
        residuals = []
        for frame in audio_frames:
            pts = int(frame["pts"]) * audio_base
            residual = pts - audio_origin - Fraction(samples, sample_rate)
            residuals.append(residual)
            if abs(residual) > audio_base:
                raise MediaPreparationError(
                    "unsupported_audio_offset", "decoded audio discontinuity/drift"
                )
            samples += int(frame["nb_samples"])
        if max(residuals) - min(residuals) > Fraction(1, 1000):
            raise MediaPreparationError(
                "unsupported_audio_offset", "decoded audio drift exceeds 1ms"
            )
        audio_residual = max(abs(value) for value in residuals)
        audio_drift = max(residuals) - min(residuals)
        if audio_origin < 0:
            raise MediaPreparationError(
                "unsupported_audio_offset", "negative decoded audio origin"
            )
        hashed = (
            tools.run(
                [
                    tools.ffmpeg,
                    "-v",
                    "error",
                    "-nostdin",
                    "-i",
                    str(path),
                    "-map",
                    f"0:{audio_stream_index}",
                    "-vn",
                    "-c:a",
                    "pcm_s24le",
                    "-f",
                    "hash",
                    "-hash",
                    "sha256",
                    "-",
                ]
            )
            .decode()
            .strip()
        )
        audio_hash = "sha256:" + hashed.removeprefix("SHA256=")
    if file_hash(path) != content_hash:
        raise MediaPreparationError("changed_media", "source changed during inspection")
    return MediaInspection(
        probe,
        identity_hash(probe),
        content_hash,
        video,
        frames,
        rate,
        time_base,
        origin,
        audio,
        audio_frames,
        audio_origin,
        samples,
        audio_hash,
        audio_residual,
        audio_drift,
    )


@dataclass(frozen=True)
class PreparationAuthorization:
    reference: str
    read_roots: tuple[Path, ...]
    write_root: Path
    tool_hash: str
    profile_hash: str = PROFILE_HASH
    policy_hash: str = POLICY_HASH
    allow_conversion: bool = True
    minimum_free_bytes: int = 64 * 1024 * 1024


@dataclass(frozen=True)
class PreparedMedia:
    binding: PreparedMediaBindingV1
    receipt_path: Path
    video_path: Path
    audio_path: Path | None
    reused: bool


def _assert_under(path: Path, roots: tuple[Path, ...]) -> Path:
    resolved = path.resolve()
    if not any(resolved.is_relative_to(root.resolve()) for root in roots):
        raise MediaPreparationError("unauthorized_path", str(path))
    # Refuse symlinks on source and managed path components, even inside the root.
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise MediaPreparationError(
            "unauthorized_path", "symbolic links are not authorized"
        )
    return resolved


def _verify_descriptor(
    inspection: MediaInspection, descriptor: OccurrenceMediaResolutionV2
) -> None:
    frame_map, snapshot = descriptor["sourceFrameMap"], descriptor["sourceSnapshot"]
    if (
        inspection.content_hash != snapshot["contentHash"]
        or inspection.probe_hash != snapshot["probeHash"]
        or frame_map["probeHash"] != inspection.probe_hash
    ):
        raise MediaPreparationError(
            "source_hash_mismatch", "stale content/probe descriptor"
        )
    if (
        rational(frame_map["decodedPackageFrameRate"], positive=True) != inspection.rate
        or rational(descriptor["logicalSourceBounds"]["frameRate"], positive=True)
        != inspection.rate
        or safe_integer(frame_map["decodedPackageFrameCount"])
        != len(inspection.video_frames)
        or rational(frame_map["packageVideoTimeBase"], positive=True)
        != inspection.time_base
        or rational(frame_map["packageVideoPtsOrigin"]) != inspection.pts_origin
    ):
        raise MediaPreparationError(
            "invalid_mapping", "O/P0/H descriptor differs from decoded package"
        )
    rational(frame_map["loggedTimeAtPackageFrameZero"])
    mappings = frame_map["sourceAudioStreamMappings"]
    if inspection.audio is None:
        if mappings:
            raise MediaPreparationError(
                "invalid_mapping", "audio mapping without audio"
            )
    elif (
        len(mappings) != 1
        or mappings[0]["streamIndex"] != inspection.audio["index"]
        or mappings[0]["sampleRate"] != int(inspection.audio["sample_rate"])
        or mappings[0]["audioHash"] != inspection.audio_hash
        or mappings[0]["probeHash"] != inspection.probe_hash
        or rational(mappings[0]["packagePtsOrigin"]) != inspection.audio_origin
        or rational(mappings[0]["loggedTimeAtPackageOrigin"])
        != rational(frame_map["loggedTimeAtPackageFrameZero"])
        + inspection.audio_origin
        - inspection.pts_origin
    ):
        raise MediaPreparationError(
            "unsupported_audio_offset",
            "selected audio mapping differs from decoded origin",
        )


def _video_filter(geometry: PreparationGeometry) -> str:
    # Exact verified cadence avoids round=up misselection from container tick rounding.
    ticks = math.lcm(geometry.source_rate.numerator, geometry.start.denominator)
    step = ticks * geometry.source_rate.denominator // geometry.source_rate.numerator
    origin = int(geometry.start * ticks)
    end = math.ceil(geometry.end * geometry.source_rate)
    return (
        f"trim=start_frame={geometry.first_package_frame}:end_frame={end},"
        f"settb=expr=1/{ticks},setpts=(N+{geometry.first_package_frame})*{step}-{origin},"
        f"fps=fps={geometry.target_rate}:start_time=0:round=up:eof_action=pass"
    )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_record(path: Path, record: Json) -> None:
    with path.open("xb") as stream:
        stream.write(canonical_json_bytes(record))
        stream.flush()
        os.fsync(stream.fileno())


def prepare_media(
    source_path: Path,
    descriptor: OccurrenceMediaResolutionV2,
    requested_range: RequestedPreparationRangeV1,
    target_rate: RationalRate,
    *,
    authorization: PreparationAuthorization,
    video_stream_index: int,
    audio_stream_index: int | None,
    tools: MediaTools | None = None,
    checkpoint: Callable[[str, Path], None] | None = None,
) -> PreparedMedia:
    """Return the frozen P2 binding and a verified immutable pair receipt for P6/P7."""
    tools = tools or MediaTools()
    _validate(descriptor, "OccurrenceMediaResolutionV2")
    _validate(requested_range, "RequestedPreparationRangeV1")
    _validate(target_rate, "RationalRate")
    safe_integer(video_stream_index)
    if audio_stream_index is not None:
        safe_integer(audio_stream_index)
    if (
        type(authorization.allow_conversion) is not bool
        or type(authorization.minimum_free_bytes) is not int
        or authorization.minimum_free_bytes < 0
    ):
        raise MediaPreparationError(
            "invalid_authorization", "invalid conversion/disk policy"
        )
    source = _assert_under(source_path, authorization.read_roots)
    root = _assert_under(authorization.write_root, (authorization.write_root,))
    if (
        not authorization.reference
        or authorization.profile_hash != PROFILE_HASH
        or authorization.policy_hash != POLICY_HASH
    ):
        raise MediaPreparationError(
            "invalidated_profile", "authorization must pin this exact policy/profile"
        )
    fingerprint = tools.fingerprint()
    if identity_hash(fingerprint) != authorization.tool_hash:
        raise MediaPreparationError(
            "invalidated_tools", "installed tool/platform fingerprint changed"
        )
    inspected = inspect_media(
        source,
        video_stream_index=video_stream_index,
        audio_stream_index=audio_stream_index,
        tools=tools,
    )
    _verify_descriptor(inspected, descriptor)
    frame_map = descriptor["sourceFrameMap"]
    bounds = descriptor["logicalSourceBounds"]
    origin_frame = safe_integer(frame_map["packageFrameZeroLogicalFrame"])
    if not (
        0
        <= bounds["startFrame"] - origin_frame
        < bounds["endFrame"] - origin_frame
        <= len(inspected.video_frames)
    ):
        raise MediaPreparationError(
            "invalid_mapping", "logical bounds exceed decoded package"
        )
    target = rational(target_rate, positive=True)
    geometry = preparation_geometry(
        source_rate=inspected.rate,
        target_rate=target,
        origin_frame=origin_frame,
        lower_frame=bounds["startFrame"],
        upper_frame=bounds["endFrame"],
        in_frame=safe_integer(requested_range["sourceInFrame"]),
        duration=rational(requested_range["duration"], positive=True),
        pre_handle=rational(requested_range["preHandle"]),
        post_handle=rational(requested_range["postHandle"]),
    )
    mode = "verified_reuse" if inspected.rate == target else "derived_cfr"
    logged_origin = rational(frame_map["loggedTimeAtPackageFrameZero"])
    source_origin = (
        logged_origin if mode == "verified_reuse" else logged_origin + geometry.start
    )
    wire(source_origin)
    profile = {
        "policyHash": POLICY_HASH,
        "profileHash": PROFILE_HASH,
        "toolHash": authorization.tool_hash,
        "profileVersion": PROFILE["version"],
    }
    key_inputs = {
        "mediaReferenceId": descriptor["mediaReferenceId"],
        "sourceSnapshot": descriptor["sourceSnapshot"],
        "sourceFrameMap": frame_map,
        "videoStreamIndex": video_stream_index,
        "audioStreamIndex": audio_stream_index,
        "requestedRange": requested_range,
        "targetRate": wire(target),
        "profile": profile,
    }
    key = identity_hash(key_inputs)
    root.mkdir(parents=True, exist_ok=True)
    for name in ("attempts", "published", "locks"):
        _assert_under(root / name, (root,)).mkdir(exist_ok=True)
    _fsync_directory(root)
    published = root / "published" / key.removeprefix("sha256:")
    _assert_under(published, (root,))
    lock = root / "locks" / (key.removeprefix("sha256:") + ".lock")
    lock_fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise MediaPreparationError(
                "preparation_busy", "retry after requirement owner releases lease"
            ) from error
        if published.exists():
            return _reuse(published, source, key_inputs, authorization, tools)
        for previous_attempt in sorted(
            (root / "attempts").glob(key.removeprefix("sha256:") + "-*")
        ):
            _assert_under(previous_attempt, (root,))
            if (previous_attempt / "receipt-checksum.json").exists():
                _reuse(previous_attempt, source, key_inputs, authorization, tools)
                for path in previous_attempt.iterdir():
                    with path.open("rb") as stream:
                        os.fsync(stream.fileno())
                _fsync_directory(previous_attempt)
                tools.check_cancel()
                os.rename(previous_attempt, published)
                _fsync_directory(root / "published")
                _fsync_directory(root / "attempts")
                return _reuse(published, source, key_inputs, authorization, tools)
        if mode == "derived_cfr" and not authorization.allow_conversion:
            raise MediaPreparationError(
                "conversion_needed",
                "reuse-only authorization has no exact published derivative",
            )
        # Reserve a raw-picture upper bound and whole-source PCM before writes.
        required_bytes = (
            inspected.video["width"]
            * inspected.video["height"]
            * 3
            * geometry.frame_count
            + inspected.audio_samples * (inspected.audio or {}).get("channels", 0) * 6
        )
        if (
            shutil.disk_usage(root).free
            < required_bytes + authorization.minimum_free_bytes
        ):
            raise MediaPreparationError(
                "insufficient_disk",
                f"need at least {required_bytes} new bytes plus free-space reserve",
            )
        attempt = Path(
            tempfile.mkdtemp(
                prefix=key.removeprefix("sha256:") + "-", dir=root / "attempts"
            )
        )
        _write_record(
            attempt / "request.json",
            {
                "requirementKey": key,
                "inputs": key_inputs,
                "authorizationReference": authorization.reference,
            },
        )
        _fsync_directory(attempt)
        _fsync_directory(root / "attempts")
        if checkpoint:
            checkpoint("staged", attempt)
        command_start = len(tools.commands)
        video_path = source
        if mode == "derived_cfr":
            video_path = attempt / "picture.mp4"
            video = inspected.video
            tools.run(
                [
                    tools.ffmpeg,
                    "-v",
                    "error",
                    "-nostdin",
                    "-n",
                    "-i",
                    str(source),
                    "-map",
                    f"0:{video_stream_index}",
                    "-an",
                    "-sn",
                    "-dn",
                    "-vf",
                    _video_filter(geometry),
                    "-frames:v",
                    str(geometry.frame_count),
                    "-fps_mode",
                    "passthrough",
                    "-c:v",
                    "libx264",
                    "-profile:v",
                    "high",
                    "-pix_fmt",
                    "yuv420p",
                    "-crf",
                    "18",
                    "-preset",
                    "medium",
                    "-threads",
                    "1",
                    "-map_metadata",
                    "-1",
                    "-map_chapters",
                    "-1",
                    "-color_range",
                    video["color_range"],
                    "-colorspace",
                    video["color_space"],
                    "-color_primaries",
                    video["color_primaries"],
                    "-color_trc",
                    video["color_transfer"],
                    "-video_track_timescale",
                    str(target.numerator),
                    "-fflags",
                    "+bitexact",
                    str(video_path),
                ]
            )
            delivered = inspect_media(
                video_path, video_stream_index=0, audio_stream_index=None, tools=tools
            )
            if (
                len(delivered.video_frames) != geometry.frame_count
                or delivered.rate != target
                or delivered.pts_origin != 0
                or delivered.video["profile"] != "High"
                or any(
                    delivered.video.get(k) != video.get(k)
                    for k in (
                        "width",
                        "height",
                        "sample_aspect_ratio",
                        "color_range",
                        "color_space",
                        "color_transfer",
                        "color_primaries",
                    )
                )
            ):
                raise MediaPreparationError(
                    "output_verification_failed",
                    "picture count/cadence/profile mismatch",
                )
        else:
            delivered = inspected
        audio_record = _prepare_audio(source, attempt, inspected, geometry, mode, tools)
        if (
            file_hash(source) != inspected.content_hash
            or identity_hash(tools.fingerprint()) != authorization.tool_hash
        ):
            raise MediaPreparationError(
                "changed_media_or_tools", "source/tools changed during attempt"
            )
        mapping: Json = {
            "sourceOrigin": wire(source_origin),
            "deliveredOrigin": wire(Fraction(0)),
            "sourceRate": wire(inspected.rate),
            "deliveredRate": wire(target),
            "sourceFrameMap": frame_map,
        }
        mapping["mappingHash"] = identity_hash(mapping)
        audio_verification: Json = {
            "status": "absent",
            "offset": None,
            "maxDrift": None,
            "sampleRate": None,
        }
        if audio_record:
            audio_verification = {
                "status": "aligned",
                "offset": audio_record["boundaryOffset"],
                "maxDrift": wire(
                    max(
                        inspected.audio_timestamp_drift,
                        rational(audio_record["endpointError"]),
                    )
                ),
                "sampleRate": int(inspected.audio["sample_rate"])
                if inspected.audio
                else None,
            }
        binding: Json = {
            "requirementKey": key,
            "mode": mode,
            "originalSource": {
                "mediaReferenceId": descriptor["mediaReferenceId"],
                "contentHash": inspected.content_hash,
                "probeHash": inspected.probe_hash,
            },
            "targetRate": wire(target),
            "requestedRange": requested_range,
            "profile": profile,
            "timeMapping": mapping,
            "verification": {
                "deliveredHash": delivered.content_hash,
                "probeHash": delivered.probe_hash,
                "decodedFrameCount": len(delivered.video_frames),
                "decodedFrameRate": wire(delivered.rate),
                "videoTimeBase": wire(delivered.time_base),
                "sourceAudio": audio_verification,
            },
            "authorizationReference": authorization.reference,
            "artifactLocator": (
                source if mode == "verified_reuse" else published / "picture.mp4"
            ).as_uri(),
        }
        commands = tools.commands[command_start:]
        if mode == "derived_cfr":
            binding["derivation"] = {
                "method": "cfr_sample/v1",
                "sourceHash": inspected.content_hash,
                "outputHash": delivered.content_hash,
                "toolHash": authorization.tool_hash,
                "profileHash": PROFILE_HASH,
                "commandHash": identity_hash(commands),
            }
        _validate(binding, "PreparedMediaBindingV1")
        record = {
            "recordVersion": "authoring-media-preparation/v1",
            "requirementKey": key,
            "inputs": key_inputs,
            "binding": binding,
            "sourceProbe": inspected.probe,
            "deliveredProbe": delivered.probe,
            "tools": fingerprint,
            "profile": PROFILE,
            "policy": POLICY,
            "commands": commands,
            "audio": audio_record,
            "geometry": {
                "packageStart": wire(geometry.start),
                "packageEnd": wire(geometry.end),
                "requiredExclusiveLogicalFrame": geometry.required_end_frame,
                "sourceCoverSurplus": wire(geometry.cover_surplus),
                "terminalQuantization": wire(geometry.terminal_quantization),
                "selectedPackageFrames": [
                    geometry.selected_package_frame(j)
                    for j in range(geometry.frame_count)
                ],
            },
        }
        _write_record(attempt / "receipt.json", record)
        _write_record(
            attempt / "receipt-checksum.json",
            {"receiptHash": file_hash(attempt / "receipt.json")},
        )
        for path in attempt.iterdir():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
        _fsync_directory(attempt)
        if checkpoint:
            checkpoint("verified", attempt)
        tools.check_cancel()
        os.rename(attempt, published)
        _fsync_directory(root / "published")
        _fsync_directory(root / "attempts")
        if checkpoint:
            checkpoint("published", published)
        return _reuse(published, source, key_inputs, authorization, tools, reused=False)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _prepare_audio(
    source: Path,
    attempt: Path,
    inspection: MediaInspection,
    geometry: PreparationGeometry,
    mode: str,
    tools: MediaTools,
) -> Json | None:
    if inspection.audio is None:
        return None
    audio, origin = inspection.audio, inspection.audio_origin
    if origin is None:
        raise MediaPreparationError("invalid_mapping", "missing decoded audio origin")
    sample_rate = int(audio["sample_rate"])
    # Reused picture preserves the package timeline; retain all decoded PCM.
    start = (
        Fraction(0)
        if mode == "verified_reuse"
        else inspection.pts_origin + geometry.start - origin
    )
    end = (
        Fraction(inspection.audio_samples, sample_rate)
        if mode == "verified_reuse"
        else inspection.pts_origin + geometry.end - origin
    )
    first, exclusive = math.ceil(start * 48000), math.ceil(end * 48000)
    if start < 0 or end > Fraction(inspection.audio_samples, sample_rate):
        raise MediaPreparationError(
            "source_shortage",
            "selected audio does not cover exact picture interval/handles",
        )
    offset = Fraction(first, 48000) - start
    expected_samples = exclusive - first
    output = attempt / "audio.wav"
    tools.run(
        [
            tools.ffmpeg,
            "-v",
            "error",
            "-nostdin",
            "-n",
            "-i",
            str(source),
            "-map",
            f"0:{audio['index']}",
            "-vn",
            "-sn",
            "-dn",
            "-af",
            f"aresample=48000:async=0,atrim=start_sample={first}:end_sample={exclusive},"
            "asetpts=PTS-STARTPTS",
            "-c:a",
            "pcm_s24le",
            "-ar",
            "48000",
            "-map_metadata",
            "-1",
            "-fflags",
            "+bitexact",
            str(output),
        ]
    )
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
                    str(output),
                ]
            )
        ),
    )
    stream = probe["streams"][0]
    samples = int(stream["duration_ts"])
    endpoint_error = abs(Fraction(samples, 48000) - (end - start))
    if (
        stream["codec_name"] != "pcm_s24le"
        or int(stream["sample_rate"]) != 48000
        or stream["channels"] != audio["channels"]
        or abs(samples - expected_samples) > 1
        or endpoint_error > Fraction(1, 48000)
    ):
        raise MediaPreparationError(
            "output_verification_failed",
            "PCM profile or endpoint differs by more than one sample",
        )
    return {
        "filename": "audio.wav",
        "contentHash": file_hash(output),
        "probe": probe,
        "probeHash": identity_hash(probe),
        "decodedSamples": samples,
        "channels": audio["channels"],
        "sourceAudioHash": inspection.audio_hash,
        "sourceFirstSample": math.ceil(start * sample_rate),
        "sourceExclusiveSample": math.ceil(end * sample_rate),
        "resampledFirstSample": first,
        "resampledExclusiveSample": exclusive,
        "sourcePtsOrigin": wire(origin),
        "decodedSourceTimestampResidual": wire(inspection.audio_timestamp_residual),
        "decodedSourceTimestampDrift": wire(inspection.audio_timestamp_drift),
        "deliveredTimeAtFirstSample": wire(
            origin - inspection.pts_origin if mode == "verified_reuse" else offset
        ),
        "boundaryOffset": wire(offset),
        "endpointError": wire(endpoint_error),
    }


def _reuse(
    published: Path,
    source: Path,
    key_inputs: Json,
    authorization: PreparationAuthorization,
    tools: MediaTools,
    *,
    reused: bool = True,
) -> PreparedMedia:
    try:
        if published.is_symlink():
            raise ValueError("symlink")
        receipt_path = published / "receipt.json"
        checksum = json.loads((published / "receipt-checksum.json").read_bytes())
        if checksum["receiptHash"] != file_hash(receipt_path):
            raise ValueError("receipt checksum conflict")
        record = cast(Json, json.loads(receipt_path.read_bytes()))
        key = identity_hash(key_inputs)
        if record["inputs"] != key_inputs or record["requirementKey"] != key:
            raise ValueError("requirement conflict")
        binding = cast(PreparedMediaBindingV1, record["binding"])
        _validate(binding, "PreparedMediaBindingV1")
        if (
            binding["requirementKey"] != key
            or binding["profile"] != key_inputs["profile"]
            or binding["targetRate"] != key_inputs["targetRate"]
            or binding["requestedRange"] != key_inputs["requestedRange"]
            or binding["originalSource"]["mediaReferenceId"]
            != key_inputs["mediaReferenceId"]
            or binding["originalSource"]["probeHash"]
            != key_inputs["sourceSnapshot"]["probeHash"]
            or binding["originalSource"]["contentHash"] != file_hash(source)
            or record["profile"] != PROFILE
            or record["policy"] != POLICY
            or identity_hash(record["tools"]) != authorization.tool_hash
        ):
            raise ValueError("identity conflict")
        mapping = cast(Json, binding["timeMapping"])
        if mapping["sourceFrameMap"] != key_inputs["sourceFrameMap"] or mapping[
            "mappingHash"
        ] != identity_hash({k: v for k, v in mapping.items() if k != "mappingHash"}):
            raise ValueError("mapping conflict")
        video_path = (
            source if binding["mode"] == "verified_reuse" else published / "picture.mp4"
        )
        verified = inspect_media(
            video_path,
            video_stream_index=key_inputs["videoStreamIndex"]
            if binding["mode"] == "verified_reuse"
            else 0,
            audio_stream_index=key_inputs["audioStreamIndex"]
            if binding["mode"] == "verified_reuse"
            else None,
            tools=tools,
        )
        if (
            verified.content_hash != binding["verification"]["deliveredHash"]
            or verified.probe_hash != binding["verification"]["probeHash"]
            or len(verified.video_frames)
            != binding["verification"]["decodedFrameCount"]
            or wire(verified.rate) != binding["verification"]["decodedFrameRate"]
            or wire(verified.time_base) != binding["verification"]["videoTimeBase"]
        ):
            raise ValueError("picture hash/probe conflict")
        audio_record = record["audio"]
        audio_path = published / "audio.wav" if audio_record else None
        if audio_record and audio_path is not None:
            if file_hash(audio_path) != audio_record["contentHash"]:
                raise ValueError("audio hash conflict")
            probe = json.loads(
                tools.run(
                    [
                        tools.ffprobe,
                        "-v",
                        "error",
                        "-show_streams",
                        "-of",
                        "json",
                        str(audio_path),
                    ]
                )
            )
            if identity_hash(probe) != audio_record["probeHash"]:
                raise ValueError("audio probe conflict")
        # Bind authorization per invocation; keep build IDs out of reusable media keys.
        projected = cast(
            PreparedMediaBindingV1,
            {
                **binding,
                "authorizationReference": authorization.reference,
                "artifactLocator": video_path.as_uri(),
            },
        )
        return PreparedMedia(projected, receipt_path, video_path, audio_path, reused)
    except (OSError, KeyError, ValueError, TypeError) as error:
        raise MediaPreparationError(
            "published_conflict",
            "preserve artifact; audited quarantine/repair required",
        ) from error
