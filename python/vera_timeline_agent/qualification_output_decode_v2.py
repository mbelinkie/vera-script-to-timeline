"""Pinned host decoder for the exact MOV delivered by the #209 native job."""

from __future__ import annotations

import hashlib
import json
import os
import re
import selectors
import stat
import struct
import subprocess
import time
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, NoReturn

from vera_timeline_agent import qualification_output_records_v2 as records

JsonObject = dict[str, Any]

_FRAME_SAMPLES = 2002
_MAX_EXTENT_FRAMES = 1498
_MAX_SAMPLE_COUNT = _FRAME_SAMPLES * _MAX_EXTENT_FRAMES
_MAX_DECODE_BYTES = _MAX_SAMPLE_COUNT * 2 * 4
_MAX_PROBE_BYTES = 64 * 1024
_MAX_TOOL_OUTPUT_BYTES = 16 * 1024
_PROCESS_TIMEOUT_SECONDS = 120
_READ_CHUNK_BYTES = 64 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_RATE = re.compile(r"[0-9]{1,6}/[0-9]{1,6}\Z")
_DECIMAL_TIME = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
_TIMECODE = re.compile(r"[0-9]{2}:[0-9]{2}:[0-9]{2}[:;][0-9]{2}\Z")

FFMPEG_PATH = Path("/usr/local/Cellar/ffmpeg/8.1.2_1/bin/ffmpeg")
FFPROBE_PATH = Path("/usr/local/Cellar/ffmpeg/8.1.2_1/bin/ffprobe")
FFMPEG_VERSION = "ffmpeg version 8.1.2"
FFPROBE_VERSION = "ffprobe version 8.1.2"
FFMPEG_SHA256 = "284023fbfa0480733ac83087f3afdb9ddb0bcdfe75191c20c8cefc034255e65c"
FFPROBE_SHA256 = "e5c6567171b5af525de016d1a7907553bbdc86a81b7d25d91046c0aa25361eb2"
_PROCESS_ENV = {"LANG": "C", "LC_ALL": "C"}
_LINEAGE_FIELDS = frozenset(
    {
        "schemaVersion",
        "lane",
        "context",
        "commitmentRawSha256",
        "reservationRawSha256",
        "renderIntentSha256",
        "effectReceiptSha256",
        "startReceiptSha256",
        "completionReceiptSha256",
        "jobId",
        "sourceOutputRawSha256",
    }
)
_LINEAGE_HASH_FIELDS = frozenset(
    {
        "commitmentRawSha256",
        "reservationRawSha256",
        "renderIntentSha256",
        "effectReceiptSha256",
        "startReceiptSha256",
        "completionReceiptSha256",
        "sourceOutputRawSha256",
    }
)
_PROBE_ENTRIES = (
    "stream=index,start_pts,start_time,codec_type,codec_name,codec_tag_string,profile,width,height,"
    "r_frame_rate,avg_frame_rate,nb_read_frames,sample_rate,channels,"
    "channel_layout,sample_fmt,bits_per_raw_sample,bits_per_sample,time_base,"
    "duration_ts,nb_frames:stream_disposition=attached_pic:stream_tags=timecode:"
    "format=format_name,format_long_name,start_time:"
    "format_tags=major_brand"
)


class DecodeError(records.OutputConsistencyError):
    """The exact delivered MOV cannot be decoded under the pinned profile."""


@dataclass(frozen=True)
class VerifiedRenderLineage:
    """Closed native lineage already authenticated by the trusted controller."""

    record: Mapping[str, Any]


@dataclass(frozen=True)
class DecodedMov:
    """Normalized signed-24-domain PCM and the unsigned #214 decode payload."""

    decoded_samples: bytes
    record: JsonObject


@dataclass(frozen=True)
class _FileState:
    device: int
    inode: int
    size: int
    modified_ns: int
    changed_ns: int


@dataclass(frozen=True)
class _ToolPin:
    path: Path
    version: str
    sha256: str


@dataclass(frozen=True)
class _ToolIdentity:
    path: str
    version: str
    sha256: str
    state: _FileState


@dataclass(frozen=True)
class _Toolchain:
    ffmpeg: _ToolIdentity
    ffprobe: _ToolIdentity


_FFMPEG_PIN = _ToolPin(FFMPEG_PATH, FFMPEG_VERSION, FFMPEG_SHA256)
_FFPROBE_PIN = _ToolPin(FFPROBE_PATH, FFPROBE_VERSION, FFPROBE_SHA256)


def _refuse(message: str) -> NoReturn:
    raise DecodeError(message)


def _state(info: os.stat_result) -> _FileState:
    return _FileState(
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _open_regular(
    path: Path, label: str, *, executable: bool = False
) -> tuple[int, _FileState]:
    if not path.is_absolute():
        _refuse(f"{label} path must be absolute")
    try:
        if path.resolve(strict=True) != path:
            _refuse(f"{label} path contains a symlink")
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            _refuse(f"{label} must be a regular file")
        if executable and before.st_mode & 0o111 == 0:
            _refuse(f"{label} is not executable")
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        if nofollow == 0:
            _refuse("platform lacks no-follow file opening")
        fd = os.open(path, os.O_RDONLY | nofollow)
        opened = os.fstat(fd)
        after = path.lstat()
        if (
            not stat.S_ISREG(opened.st_mode)
            or _state(before) != _state(opened)
            or _state(opened) != _state(after)
        ):
            os.close(fd)
            _refuse(f"{label} changed while opening")
        return fd, _state(opened)
    except DecodeError:
        raise
    except OSError as error:
        raise DecodeError(f"cannot open pinned {label}") from error


def _hash_fd(fd: int) -> str:
    digest = hashlib.sha256()
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        while chunk := os.read(fd, _READ_CHUNK_BYTES):
            digest.update(chunk)
        os.lseek(fd, 0, os.SEEK_SET)
    except OSError as error:
        raise DecodeError("cannot hash pinned input") from error
    return digest.hexdigest()


def _hash_path(
    path: Path, label: str, *, executable: bool = False
) -> tuple[str, _FileState]:
    fd, opened_state = _open_regular(path, label, executable=executable)
    try:
        result = _hash_fd(fd)
        if _state(os.fstat(fd)) != opened_state:
            _refuse(f"{label} changed while hashing")
        return result, opened_state
    finally:
        os.close(fd)


def _run_bounded(
    argv: Sequence[str],
    *,
    max_output_bytes: int,
    pass_fds: tuple[int, ...] = (),
) -> bytes:
    try:
        process = subprocess.Popen(
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd="/",
            env=_PROCESS_ENV,
            close_fds=True,
            pass_fds=pass_fds,
        )
    except OSError as error:
        raise DecodeError("pinned media tool could not start") from error

    output = bytearray()
    try:
        if process.stdout is None:
            _refuse("pinned media tool has no output pipe")
        deadline = time.monotonic() + _PROCESS_TIMEOUT_SECONDS
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    _refuse("pinned media tool timed out")
                room = max_output_bytes + 1 - len(output)
                chunk = os.read(process.stdout.fileno(), min(_READ_CHUNK_BYTES, room))
                if not chunk:
                    selector.unregister(process.stdout)
                    break
                output.extend(chunk)
                if len(output) > max_output_bytes:
                    _refuse("pinned media tool output exceeds its bound")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _refuse("pinned media tool timed out")
        try:
            return_code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as error:
            raise DecodeError("pinned media tool timed out") from error
        if return_code != 0:
            _refuse("pinned media tool refused the input")
        return bytes(output)
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise
    finally:
        if process.stdout is not None:
            process.stdout.close()


def _verify_tool(pin: _ToolPin, executable_name: str) -> _ToolIdentity:
    digest, before = _hash_path(pin.path, executable_name, executable=True)
    if digest != pin.sha256:
        _refuse(f"{executable_name} binary hash drifted")
    try:
        raw_version = _run_bounded(
            (str(pin.path), "-version"), max_output_bytes=_MAX_TOOL_OUTPUT_BYTES
        ).decode("utf-8", errors="strict")
    except UnicodeError as error:
        raise DecodeError(f"{executable_name} version output is invalid") from error
    first_line = raw_version.splitlines()[0] if raw_version.splitlines() else ""
    if first_line.split()[:3] != pin.version.split():
        _refuse(f"{executable_name} version drifted")
    after_digest, after = _hash_path(pin.path, executable_name, executable=True)
    if digest != after_digest or before != after:
        _refuse(f"{executable_name} changed during verification")
    return _ToolIdentity(str(pin.path), first_line, digest, after)


def _verify_toolchain() -> _Toolchain:
    return _Toolchain(
        _verify_tool(_FFMPEG_PIN, "ffmpeg"),
        _verify_tool(_FFPROBE_PIN, "ffprobe"),
    )


def _assert_toolchain_current(toolchain: _Toolchain) -> None:
    for identity, pin, name in (
        (toolchain.ffmpeg, _FFMPEG_PIN, "ffmpeg"),
        (toolchain.ffprobe, _FFPROBE_PIN, "ffprobe"),
    ):
        digest, state = _hash_path(pin.path, name, executable=True)
        if digest != identity.sha256 or state != identity.state:
            _refuse(f"{name} changed during decode")


def _source_graph_sha256() -> str:
    package_dir = Path(__file__).parent
    modules = (
        ("qualification_output_decode_v2.py", Path(__file__)),
        (
            "qualification_output_records_v2.py",
            Path(records.__file__ or ""),
        ),
    )
    hashes: dict[str, str] = {}
    for name, path in modules:
        if path.parent != package_dir:
            _refuse("decoder source graph escaped its package")
        hashes[name], _ = _hash_path(path, "decoder source")
    return hashlib.sha256(_canonical_json(hashes)).hexdigest()


def _canonical_json(value: Any) -> bytes:
    try:
        raw = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise DecodeError("invalid bounded decode record") from error
    if len(raw) > 8 * 1024 * 1024:
        _refuse("decode record exceeds its bound")
    return raw


def _snapshot_object(value: Mapping[str, Any], label: str) -> JsonObject:
    if not isinstance(value, Mapping):
        _refuse(f"{label} must be a closed object")
    raw = _canonical_json(dict(value))
    try:
        result = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise DecodeError(f"{label} is invalid JSON") from error
    if type(result) is not dict:
        _refuse(f"{label} must be an object")
    return result


def _digest(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _refuse(f"{label} must be a lowercase SHA256")
    return value


def _lineage_record(
    verified: VerifiedRenderLineage,
    *,
    context: JsonObject,
    output_sha256: str,
) -> JsonObject:
    lineage = _snapshot_object(verified.record, "verified render lineage")
    if lineage.keys() != _LINEAGE_FIELDS:
        _refuse("render lineage shape differs")
    if (
        lineage["schemaVersion"] != "qualification-output-lineage/v1"
        or lineage["lane"] != records.LANE
        or lineage["context"] != context
    ):
        _refuse("render lineage context or version differs")
    job_id = lineage["jobId"]
    if (
        type(job_id) is not str
        or not 0 < len(job_id) <= 512
        or any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in job_id)
    ):
        _refuse("render lineage has no valid native job identity")
    for field in _LINEAGE_HASH_FIELDS:
        _digest(lineage[field], f"render lineage {field}")
    if lineage["sourceOutputRawSha256"] != output_sha256:
        _refuse("render lineage does not identify the delivered MOV")
    return lineage


def _input_fd(path: Path) -> tuple[int, _FileState]:
    if path.suffix.lower() != ".mov":
        _refuse("delivered output must be a MOV file")
    return _open_regular(path, "delivered MOV")


def _probe_command(input_ref: str) -> tuple[str, ...]:
    return (
        str(FFPROBE_PATH),
        "-v",
        "error",
        # Pin MOV edit-list interpretation so probing and decoding share one timeline.
        "-ignore_editlist",
        "0",
        "-advanced_editlist",
        "1",
        "-count_frames",
        "-show_entries",
        _PROBE_ENTRIES,
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        "-i",
        input_ref,
    )


def _decode_command(input_ref: str) -> tuple[str, ...]:
    return (
        str(FFMPEG_PATH),
        "-nostdin",
        "-hide_banner",
        "-v",
        "error",
        "-xerror",
        # Pin MOV edit-list interpretation so probing and decoding share one timeline.
        "-ignore_editlist",
        "0",
        "-advanced_editlist",
        "1",
        "-i",
        input_ref,
        "-map",
        "0:a:0",
        "-vn",
        "-sn",
        "-dn",
        "-c:a",
        "pcm_s32le",
        "-f",
        "s32le",
        "pipe:1",
    )


def _probe_mov(fd: int, input_ref: str) -> JsonObject:
    try:
        os.lseek(fd, 0, os.SEEK_SET)
    except OSError as error:
        raise DecodeError("cannot rewind delivered MOV for profile probing") from error
    raw = _run_bounded(
        _probe_command(input_ref),
        max_output_bytes=_MAX_PROBE_BYTES,
        pass_fds=(fd,),
    )
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise DecodeError("ffprobe returned invalid profile data") from error
    if type(value) is not dict:
        _refuse("ffprobe profile must be an object")
    return value


def _decode_mov(fd: int, input_ref: str, sample_count: int) -> bytes:
    byte_count = sample_count * 2 * 4
    if byte_count > _MAX_DECODE_BYTES:
        _refuse("decoded sample bound exceeded")
    try:
        os.lseek(fd, 0, os.SEEK_SET)
    except OSError as error:
        raise DecodeError("cannot rewind delivered MOV for decoding") from error
    return _run_bounded(
        _decode_command(input_ref),
        max_output_bytes=byte_count,
        pass_fds=(fd,),
    )


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is int:
        result = value
    elif (
        type(value) is str
        and value.isascii()
        and value.isdecimal()
        and len(value) <= 12
    ):
        result = int(value)
    else:
        _refuse(f"ffprobe {label} is not an integer")
    if result < minimum:
        _refuse(f"ffprobe {label} is outside its range")
    return result


def _fraction(value: Any, label: str) -> Fraction:
    if type(value) is not str or _RATE.fullmatch(value) is None:
        _refuse(f"ffprobe {label} is not an exact rational")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise DecodeError(f"ffprobe {label} is not an exact rational") from error


def _time(value: Any, label: str) -> Fraction:
    if (
        type(value) is not str
        or len(value) > 64
        or _DECIMAL_TIME.fullmatch(value) is None
    ):
        _refuse(f"ffprobe {label} is not an exact decimal time")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise DecodeError(f"ffprobe {label} is not an exact decimal time") from error


def _validate_profile(
    probe: JsonObject,
    *,
    extent_frames: int,
    width: int,
    height: int,
) -> None:
    streams = probe.get("streams")
    fmt = probe.get("format")
    if type(streams) is not list or not 2 <= len(streams) <= 3 or type(fmt) is not dict:
        _refuse("MOV needs one video, one audio, and at most one timecode stream")
    if any(type(stream) is not dict for stream in streams):
        _refuse("MOV stream inventory is invalid")
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
    metadata = [stream for stream in streams if stream.get("codec_type") == "data"]
    if len(videos) != 1 or len(audios) != 1 or len(metadata) != len(streams) - 2:
        _refuse("MOV has an unexpected stream layout")
    video, audio = videos[0], audios[0]
    for stream, label in ((video, "video"), (audio, "audio")):
        if (
            _integer(stream.get("start_pts"), f"{label} start PTS") != 0
            or _time(stream.get("start_time"), f"{label} start time") != 0
        ):
            _refuse(f"MOV {label} timestamp origin differs")
    if _time(fmt.get("start_time"), "container start time") != 0:
        _refuse("MOV container timestamp origin differs")
    if len(
        {_integer(stream.get("index"), "stream index") for stream in streams}
    ) != len(streams):
        _refuse("MOV stream indexes are not unique")
    if metadata:
        timecode = metadata[0]
        timecode_tags = timecode.get("tags")
        if (
            timecode.get("codec_tag_string") != "tmcd"
            or _integer(timecode.get("nb_frames"), "timecode metadata frame count") != 1
            or type(timecode_tags) is not dict
            or type(timecode_tags.get("timecode")) is not str
            or _TIMECODE.fullmatch(timecode_tags["timecode"]) is None
        ):
            _refuse("MOV timecode metadata stream differs")
    format_names = fmt.get("format_name")
    tags = fmt.get("tags")
    if (
        type(format_names) is not str
        or "mov" not in format_names.split(",")
        or fmt.get("format_long_name") != "QuickTime / MOV"
        or type(tags) is not dict
        or tags.get("major_brand") != "qt  "
    ):
        _refuse("MOV container profile differs")
    if (
        video.get("codec_name") != "prores"
        or video.get("codec_tag_string") != "apcn"
        or video.get("profile") != "Standard"
        or _integer(video.get("width"), "video width", 1) != width
        or _integer(video.get("height"), "video height", 1) != height
        or _fraction(video.get("r_frame_rate"), "video frame rate")
        != Fraction(24000, 1001)
        or _fraction(video.get("avg_frame_rate"), "average video frame rate")
        != Fraction(24000, 1001)
        or _integer(video.get("nb_read_frames"), "video frame count") != extent_frames
    ):
        _refuse("MOV video profile or extent differs")
    disposition = video.get("disposition")
    if (
        type(disposition) is not dict
        or _integer(disposition.get("attached_pic"), "attached-picture flag") != 0
    ):
        _refuse("MOV video stream is not a picture sequence")
    # #211 retained codec enumeration, not a delivered MOV proving tag aliases.
    if (
        audio.get("codec_name") != "pcm_s24le"
        or audio.get("codec_tag_string") != "lpcm"
        or _integer(audio.get("bits_per_raw_sample"), "audio bit depth") != 24
        or _integer(audio.get("sample_rate"), "audio sample rate") != 48000
        or _integer(audio.get("channels"), "audio channel count") != 2
        or audio.get("channel_layout") != "stereo"
        or audio.get("sample_fmt") not in {"s32", "s32p"}
        or _fraction(audio.get("time_base"), "audio time base") != Fraction(1, 48000)
        or _integer(audio.get("duration_ts"), "audio sample extent")
        != extent_frames * _FRAME_SAMPLES
    ):
        _refuse("MOV audio profile or exact sample extent differs")
    bits_per_sample = audio.get("bits_per_sample")
    if (
        bits_per_sample is not None
        and _integer(bits_per_sample, "audio storage depth") != 24
    ):
        _refuse("MOV audio storage depth differs")


def _signed24_domain(raw_s32le: bytes, sample_count: int) -> bytes:
    value_count = sample_count * 2
    if len(raw_s32le) != value_count * 4:
        _refuse("decoded MOV sample count differs")
    normalized = bytearray(len(raw_s32le))
    for index, (wide_sample,) in enumerate(struct.iter_unpack("<i", raw_s32le)):
        if wide_sample & 0xFF:
            _refuse("ffmpeg s32le sample is not left-aligned signed 24-bit PCM")
        sample = wide_sample >> 8
        if not -(1 << 23) <= sample < (1 << 23):
            _refuse("decoded sample exceeds signed 24-bit range")
        struct.pack_into("<i", normalized, index * 4, sample)
    return bytes(normalized)


def _command_sha256(
    input_ref: str,
    toolchain: _Toolchain,
) -> str:
    commands = {
        "environment": _PROCESS_ENV,
        "workingDirectory": "/",
        "inputFd": input_ref,
        "execution": {
            "stdin": "DEVNULL",
            "stdout": "bounded_pipe",
            "stderr": "DEVNULL",
            "timeoutSeconds": _PROCESS_TIMEOUT_SECONDS,
            "passFds": [int(input_ref.rsplit("/", 1)[1])],
        },
        "ffmpegVersion": [toolchain.ffmpeg.path, "-version"],
        "ffprobeVersion": [toolchain.ffprobe.path, "-version"],
        "probe": list(_probe_command(input_ref)),
        "decode": list(_decode_command(input_ref)),
    }
    return hashlib.sha256(_canonical_json(commands)).hexdigest()


def _decoder_identity_sha256(
    toolchain: _Toolchain,
    *,
    width: int,
    height: int,
) -> str:
    identity = {
        "ffmpeg": {
            "path": toolchain.ffmpeg.path,
            "version": toolchain.ffmpeg.version,
            "sha256": toolchain.ffmpeg.sha256,
        },
        "ffprobe": {
            "path": toolchain.ffprobe.path,
            "version": toolchain.ffprobe.version,
            "sha256": toolchain.ffprobe.sha256,
        },
        "profile": {
            "container": "mov",
            "editListPolicy": "apply-advanced",
            "timestampOrigin": "zero",
            "videoCodec": "prores422",
            "audioCodec": "lpcm",
            "audioBitDepth": 24,
            "audioSampleRate": 48000,
            "audioChannels": 2,
            "rate": {"numerator": 24000, "denominator": 1001},
            "width": width,
            "height": height,
        },
    }
    return hashlib.sha256(_canonical_json(identity)).hexdigest()


def decode_delivered_mov(
    mov_path: Path,
    *,
    context: Mapping[str, Any],
    expected_output_sha256: str,
    expected_extent_frames: int,
    expected_width: int,
    expected_height: int,
    render_lineage: VerifiedRenderLineage,
) -> DecodedMov:
    """Decode only the already-authenticated native job's exact delivered MOV.

    The trusted controller must authenticate render intent, effect, start,
    completion, job and output records before constructing `render_lineage`.
    This function rechecks the closed record and delivered-file hash, but it
    cannot establish native provenance from caller-provided hashes alone.
    """
    context_value = _snapshot_object(context, "decode context")
    output_sha256 = _digest(expected_output_sha256, "delivered MOV hash")
    if (
        type(expected_extent_frames) is not int
        or not 1 <= expected_extent_frames <= _MAX_EXTENT_FRAMES
        or type(expected_width) is not int
        or type(expected_height) is not int
        or expected_width < 1
        or expected_height < 1
    ):
        _refuse("expected MOV profile bounds are invalid")
    _lineage_record(
        render_lineage,
        context=context_value,
        output_sha256=output_sha256,
    )
    path = Path(mov_path)
    fd, input_state = _input_fd(path)
    try:
        input_sha256 = _hash_fd(fd)
        if input_sha256 != output_sha256:
            _refuse("delivered MOV hash differs from authenticated native output")
        source_graph_sha256 = _source_graph_sha256()
        toolchain = _verify_toolchain()
        input_ref = f"/dev/fd/{fd}"
        probe = _probe_mov(fd, input_ref)
        _validate_profile(
            probe,
            extent_frames=expected_extent_frames,
            width=expected_width,
            height=expected_height,
        )
        sample_count = expected_extent_frames * _FRAME_SAMPLES
        raw_s32le = _decode_mov(fd, input_ref, sample_count)
        decoded_samples = _signed24_domain(raw_s32le, sample_count)
        if _hash_fd(fd) != input_sha256 or _state(os.fstat(fd)) != input_state:
            _refuse("delivered MOV changed during decode")
        try:
            path_state = _state(path.lstat())
            if path.resolve(strict=True) != path or path_state != input_state:
                _refuse("delivered MOV path changed during decode")
        except OSError as error:
            raise DecodeError("delivered MOV path changed during decode") from error
        _assert_toolchain_current(toolchain)
        if _source_graph_sha256() != source_graph_sha256:
            _refuse("decoder source graph changed during decode")
        record = {
            "schemaVersion": "qualification-output-decode/v1",
            "lane": records.LANE,
            "context": context_value,
            "sourceOutputRawSha256": input_sha256,
            "container": "mov",
            "videoCodec": "prores422",
            "audioCodec": "lpcm",
            "audioBitDepth": 24,
            "audioSampleRate": 48000,
            "audioChannels": 2,
            "sampleCount": sample_count,
            "decodedSamplesSha256": hashlib.sha256(decoded_samples).hexdigest(),
            "decoderIdentitySha256": _decoder_identity_sha256(
                toolchain,
                width=expected_width,
                height=expected_height,
            ),
            "decoderSourceGraphSha256": source_graph_sha256,
            "decoderCommandSha256": _command_sha256(input_ref, toolchain),
        }
        return DecodedMov(decoded_samples, record)
    finally:
        os.close(fd)
