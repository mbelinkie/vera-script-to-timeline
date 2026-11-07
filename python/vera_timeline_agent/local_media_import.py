"""Trusted-local, fail-closed #381 media materialization (no browser authority).

Callers must supply an independently authenticated authorization callback and
private state directory. No path/string from a web request grants filesystem
access. Only regular files below descriptor-pinned, no-symlink roots are read.
"""

from __future__ import annotations

import ctypes
import errno
import fcntl
import hashlib
import json
import os
import stat
import subprocess
import sys
import uuid
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

from .local_media_import_model import (
    CompletedMode,
    DecodedMediaFacts,
    ImportModelError,
    LocalImportApproval,
    MediaKind,
    PortableImportResult,
)

_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_READ = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
_NEW = os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
_CHUNK = 1024 * 1024
_UNSUPPORTED_CLONE = {
    errno.EOPNOTSUPP,
    errno.ENOTSUP,
    errno.ENOTTY,
    errno.ENOSYS,
    errno.EXDEV,
    errno.EINVAL,
}


class Decoder(Protocol):
    """A bounded *real* decoder of a verified, project-owned open descriptor."""

    def decode(self, fd: int, kind: str) -> DecodedMediaFacts: ...


class FFmpegDecoder:
    """Fail-closed FFmpeg/FFprobe decoder for a previously verified stage fd.

    Only magic-selected, forced-demuxer PNG/JPEG and MOV/MP4/Matroska files;
    in particular never auto-probe URL, playlist, manifest or concat formats.
    Both probes and full video decode are bounded by time, pixels and frames.
    Unsupported installations/media refuse rather than becoming ready assets.
    """

    def __init__(
        self,
        *,
        ffprobe: str = "ffprobe",
        ffmpeg: str = "ffmpeg",
        timeout_seconds: int = 30,
        max_pixels: int = 16_777_216,
        max_frames: int = 100_000,
    ) -> None:
        self.ffprobe = ffprobe
        self.ffmpeg = ffmpeg
        self.timeout_seconds = timeout_seconds
        self.max_pixels = max_pixels
        self.max_frames = max_frames

    @staticmethod
    def _demuxer(fd: int, kind: str) -> tuple[str, list[str]]:
        magic = os.pread(fd, 32, 0)
        if kind == "image":
            if magic.startswith(b"\x89PNG\r\n\x1a\n"):
                return "image2pipe", ["-c:v", "png"]
            if magic.startswith(b"\xff\xd8\xff"):
                return "image2pipe", ["-c:v", "mjpeg"]
        if kind == "clip":
            if len(magic) >= 12 and magic[4:8] == b"ftyp":
                return "mov", []
            if magic.startswith(b"\x1a\x45\xdf\xa3"):
                return "matroska", []
        raise ImportModelError("unsupported_media")

    def _invoke(self, args: list[str], fd: int) -> str:
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                pass_fds=(fd,),
            )
        except FileNotFoundError as error:
            raise ImportModelError("unsupported_media") from error
        except (subprocess.TimeoutExpired, OSError) as error:
            raise ImportModelError("undecodable_media") from error
        if proc.returncode != 0 or len(proc.stdout) > 65536:
            raise ImportModelError("undecodable_media")
        # Never return or log stderr: it can contain local/private data.
        return proc.stdout

    def decode(self, fd: int, kind: str) -> DecodedMediaFacts:
        if kind not in ("image", "clip"):
            raise ImportModelError("unsupported_media")
        demuxer, codec_option = self._demuxer(fd, kind)
        location = f"/dev/fd/{fd}"
        base = ["-protocol_whitelist", "file,pipe", "-f", demuxer, *codec_option]
        output = self._invoke(
            [
                self.ffprobe,
                "-v",
                "error",
                "-probesize",
                "1048576",
                "-analyzeduration",
                "5000000",
                "-count_frames",
                "-select_streams",
                "v",
                *base,
                "-show_entries",
                "stream=codec_type,codec_name,width,height,nb_read_frames",
                "-of",
                "json",
                location,
            ],
            fd,
        )
        try:
            streams = json.loads(output)["streams"]
            if not isinstance(streams, list) or len(streams) != 1:
                raise ValueError("ambiguous video streams")
            stream = streams[0]
            if stream["codec_type"] != "video":
                raise ValueError("not video")
            codec = stream["codec_name"]
            width, height = stream["width"], stream["height"]
            count = int(stream["nb_read_frames"])
            if (
                type(width) is not int
                or type(height) is not int
                or width <= 0
                or height <= 0
                or width * height > self.max_pixels
                or not 0 < count <= self.max_frames
            ):
                raise ValueError("unbounded video")
            if kind == "image" and (codec not in ("png", "mjpeg") or count != 1):
                raise ValueError("not a single still")
            if kind == "clip" and codec not in (
                "h264",
                "hevc",
                "prores",
                "mpeg4",
                "vp8",
                "vp9",
                "av1",
            ):
                raise ValueError("unsupported video codec")
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise ImportModelError("unsupported_media") from error
        decoded = self._invoke(
            [
                self.ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-v",
                "error",
                "-threads",
                "1",
                "-max_alloc",
                "134217728",
                *base,
                "-i",
                location,
                "-map",
                "0:v:0",
                "-an",
                "-sn",
                "-dn",
                "-frames:v",
                str(self.max_frames + 1),
                "-f",
                "null",
                "-",
                "-progress",
                "pipe:1",
            ],
            fd,
        )
        try:
            counts = [
                int(line.split("=", 1)[1])
                for line in decoded.splitlines()
                if line.startswith("frame=")
            ]
        except ValueError as error:
            raise ImportModelError("undecodable_media") from error
        if not counts or counts[-1] != count:
            raise ImportModelError("undecodable_media")
        proof = json.dumps(
            {
                "kind": kind,
                "demuxer": demuxer,
                "codec": codec,
                "width": width,
                "height": height,
                "frames": count,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return DecodedMediaFacts(
            kind=cast(MediaKind, kind),
            probe_hash="sha256:" + hashlib.sha256(proof).hexdigest(),
            width=width,
            height=height,
            decoded_frame_count=count if kind == "clip" else None,
        )


Clone = Callable[[int, int], bool]
Authorize = Callable[[LocalImportApproval], bool]
FreeBytes = Callable[[int], int]


@dataclass(frozen=True)
class ImportExecution:
    status: str  # completed | duplicate | recovered
    result: PortableImportResult

    def to_portable_dict(self) -> dict[str, object]:
        return {**self.result.to_portable_dict(), "status": self.status}


def _close(fd: int) -> None:
    os.close(fd)


def _open_root(root: Path, stack: ExitStack) -> tuple[int, frozenset[tuple[int, int]]]:
    """Walk from /; even an intermediate trusted-root symlink is refused."""
    if not isinstance(root, Path) or not root.is_absolute() or ".." in root.parts:
        raise ImportModelError("invalid_approval")
    fd = os.open("/", _DIRECTORY)
    stack.callback(_close, fd)
    ids = {(os.fstat(fd).st_dev, os.fstat(fd).st_ino)}
    for part in root.parts[1:]:
        fd = os.open(part, _DIRECTORY, dir_fd=fd)
        stack.callback(_close, fd)
        info = os.fstat(fd)
        ids.add((info.st_dev, info.st_ino))
    return fd, frozenset(ids)


def _child_dir(parent: int, name: str, stack: ExitStack, *, create: bool) -> int:
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=parent)
            os.fsync(parent)
        except FileExistsError:
            pass
    fd = os.open(name, _DIRECTORY, dir_fd=parent)
    stack.callback(_close, fd)
    if not stat.S_ISDIR(os.fstat(fd).st_mode):
        raise ImportModelError("unsafe_filesystem")
    return fd


def _source_fd(root_fd: int, segments: tuple[str, ...], stack: ExitStack) -> int:
    parent = root_fd
    for part in segments[:-1]:
        parent = _child_dir(parent, part, stack, create=False)
    fd = os.open(segments[-1], _READ, dir_fd=parent)
    stack.callback(_close, fd)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ImportModelError("source_unsafe")
    return fd


def _identity(fd: int) -> tuple[int, int, int, int, int]:
    s = os.fstat(fd)
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _digest(fd: int, maximum: int) -> tuple[str, int]:
    sha = hashlib.sha256()
    pos = 0
    while True:
        data = os.pread(fd, min(_CHUNK, maximum - pos + 1), pos)
        if not data:
            break
        pos += len(data)
        if pos > maximum:
            raise ImportModelError("size_limit")
        sha.update(data)
    return "sha256:" + sha.hexdigest(), pos


def _verified_source(
    fd: int, approval: LocalImportApproval
) -> tuple[int, int, int, int, int]:
    original = _identity(fd)
    if original[2] > approval.max_size_bytes:
        raise ImportModelError("size_limit")
    if original[2] != approval.expected_size_bytes:
        raise ImportModelError("content_mismatch")
    digest, size = _digest(fd, approval.max_size_bytes)
    if _identity(fd) != original:
        raise ImportModelError("source_changed")
    if size != approval.expected_size_bytes or digest != approval.expected_content_hash:
        raise ImportModelError("content_mismatch")
    return original


def _check_source_locator(
    root_fd: int,
    approval: LocalImportApproval,
    pinned_fd: int,
    identity: tuple[int, int, int, int, int],
) -> None:
    """Re-resolve only via approved no-follow dir fds, detect pathname swaps."""
    if _identity(pinned_fd) != identity:
        raise ImportModelError("source_changed")
    try:
        with ExitStack() as stack:
            current = _source_fd(root_fd, approval.source_segments, stack)
            if _identity(current) != identity:
                raise ImportModelError("source_changed")
    except OSError as error:
        raise ImportModelError("source_changed") from error


def _verify_target(fd: int, approval: LocalImportApproval) -> None:
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
    ):
        raise ImportModelError("publication_conflict")
    before = _identity(fd)
    digest, size = _digest(fd, approval.max_size_bytes)
    if (
        _identity(fd) != before
        or digest != approval.expected_content_hash
        or size != approval.expected_size_bytes
    ):
        raise ImportModelError("needs_inspection")


def _copy(source: int, target: int, maximum: int) -> None:
    pos = 0
    while True:
        data = os.pread(source, min(_CHUNK, maximum - pos + 1), pos)
        if not data:
            break
        pos += len(data)
        if pos > maximum:
            raise ImportModelError("size_limit")
        written = 0
        while written < len(data):
            count = os.write(target, data[written:])
            if count <= 0:
                raise ImportModelError("io_failure")
            written += count


def _platform_clone(source: int, target: int) -> bool:
    """Linux FICLONE only. Unsupported (including macOS) means full copy.

    An alternate independently qualified macOS fd clone port may be injected.
    Never clone using a caller-controlled source *path* or use a hard link.
    """
    if sys.platform != "linux":
        return False
    try:
        fcntl.ioctl(target, 0x40049409, source)  # FICLONE, linux/fs.h
    except OSError as error:
        if error.errno in _UNSUPPORTED_CLONE:
            return False
        raise
    return True


def _rename_exclusive(directory: int, source: str, target: str) -> None:
    """Atomic no-replace rename; NEVER fall back to overwriting os.rename."""
    libc = ctypes.CDLL(None, use_errno=True)
    src, dst = os.fsencode(source), os.fsencode(target)
    if sys.platform == "linux":
        function = getattr(libc, "renameat2", None)
        flag = 1  # RENAME_NOREPLACE
    elif sys.platform == "darwin":
        function = getattr(libc, "renameatx_np", None)
        flag = 4  # RENAME_EXCL
    else:
        function = None
        flag = 0
    if function is None:
        raise ImportModelError("unsafe_filesystem")
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    function.restype = ctypes.c_int
    if function(directory, src, directory, dst, flag) != 0:
        code = ctypes.get_errno()
        if code in (errno.EEXIST, errno.ENOTEMPTY):
            raise ImportModelError("publication_conflict")
        if code in (errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EINVAL):
            raise ImportModelError("unsafe_filesystem")
        raise OSError(code, "exclusive publication failed")
    os.fsync(directory)


def _write_once(parent: int, name: str, record: dict[str, object]) -> None:
    # Exclusive private staging also prevents a crash leaving a truncated
    # *final* JSON. An incomplete stage remains for operator inspection.
    stage_name = f".{name}.{uuid.uuid4().hex}.partial"
    fd = os.open(stage_name, os.O_WRONLY | _NEW, 0o600, dir_fd=parent)
    try:
        raw = (
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        view = memoryview(raw)
        while view:
            n = os.write(fd, view)
            if n <= 0:
                raise ImportModelError("io_failure")
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    _rename_exclusive(parent, stage_name, name)


def _read_record(parent: int, name: str) -> dict[str, object] | None:
    try:
        fd = os.open(name, _READ, dir_fd=parent)
    except FileNotFoundError:
        return None
    try:
        s = os.fstat(fd)
        if (
            not stat.S_ISREG(s.st_mode)
            or s.st_nlink != 1
            or s.st_size > 16_384
            or s.st_mode & 0o077
            or s.st_uid != os.getuid()
        ):
            raise ImportModelError("needs_inspection")
        raw = os.read(fd, 16_385)
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("non-object receipt")
        return parsed
    except (ValueError, UnicodeError) as error:
        raise ImportModelError("needs_inspection") from error
    finally:
        os.close(fd)


def _read_final(parent: int, filename: str, stack: ExitStack) -> int:
    try:
        fd = os.open(filename, _READ, dir_fd=parent)
    except FileNotFoundError as error:
        raise ImportModelError("needs_inspection") from error
    stack.callback(_close, fd)
    return fd


def _asset_directory(
    project_fd: int, approval: LocalImportApproval, stack: ExitStack, *, create: bool
) -> int:
    parent = project_fd
    category = "Local Images" if approval.kind == "image" else "Local Clips"
    for name in ("Media", category, approval.asset_id):
        parent = _child_dir(parent, name, stack, create=create)
    info = os.fstat(parent)
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ImportModelError("permission_denied")
    return parent


def _decoded(
    decoder: Decoder, fd: int, approval: LocalImportApproval
) -> DecodedMediaFacts:
    try:
        value = decoder.decode(fd, approval.kind)
    except ImportModelError:
        raise
    except (ValueError, OSError, TimeoutError) as error:
        raise ImportModelError("undecodable_media") from error
    if not isinstance(value, DecodedMediaFacts) or value.kind != approval.kind:
        raise ImportModelError("unsupported_media")
    if approval.clip_use is not None:
        assert value.decoded_frame_count is not None
        approval.clip_use.check_decoded_frames(value.decoded_frame_count)
    return value


def _read_and_validate_receipt(
    approval: LocalImportApproval,
    receipt_fd: int,
    asset_fd: int,
    decoder: Decoder,
    stack: ExitStack,
) -> PortableImportResult:
    record = _read_record(receipt_fd, approval.import_id + ".json")
    if record is None:
        raise ImportModelError("incomplete_attempt")
    if record.get("fingerprint") != approval.request_fingerprint():
        raise ImportModelError("import_conflict")
    existing = record.get("result")
    if not isinstance(existing, dict):
        raise ImportModelError("needs_inspection")
    fd = _read_final(asset_fd, approval.display_name, stack)
    _verify_target(fd, approval)
    if record.get("destinationIdentity") != list(_identity(fd)):
        # Same bytes at a different inode or with altered file metadata is
        # a replacement, not a trusted replay of the original publication.
        raise ImportModelError("needs_inspection")
    decoded = _decoded(decoder, fd, approval)
    completed_mode = existing.get("completedMode")
    if completed_mode not in ("clone", "copy"):
        raise ImportModelError("needs_inspection")
    result = PortableImportResult.from_verified(
        approval, completed_mode, decoded, datetime.now(UTC)
    )
    # Ignore only the original verification timestamp (not fresh byte evidence).
    expected = result.to_portable_dict()
    expected["verifiedAt"] = existing.get("verifiedAt")
    if expected != existing:
        raise ImportModelError("needs_inspection")
    timestamp = existing.get("verifiedAt")
    if not isinstance(timestamp, str):
        raise ImportModelError("needs_inspection")
    try:
        verified_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return PortableImportResult.from_verified(
            approval, completed_mode, decoded, verified_at
        )
    except (ValueError, TypeError, ImportModelError) as error:
        raise ImportModelError("needs_inspection") from error


@contextmanager
def _guarded_roots(
    approval: LocalImportApproval, state_root: Path
) -> Iterator[tuple[int, int, int, int, int]]:
    if not isinstance(approval, LocalImportApproval):
        raise ImportModelError("approval_required")
    with ExitStack() as stack:
        src, src_ids = _open_root(approval.source_root, stack)
        project, project_ids = _open_root(approval.project_root, stack)
        private, private_ids = _open_root(state_root, stack)
        src_id = _identity(src)[:2]
        project_id = _identity(project)[:2]
        private_id = _identity(private)[:2]
        if (
            src_id in project_ids
            or project_id in src_ids
            or private_id in src_ids
            or private_id in project_ids
            or project_id in private_ids
            or src_id in private_ids
        ):
            raise ImportModelError("root_overlap")
        p = os.fstat(private)
        if p.st_mode & 0o077 or p.st_uid != os.getuid():
            raise ImportModelError("permission_denied")
        # A project-level OS lock is shared even if two workers supply
        # different private-state paths. It never authorizes the operation.
        lock_fd = os.open(
            ".vera-local-import.lock",
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=project,
        )
        stack.callback(_close, lock_fd)
        info = os.fstat(lock_fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
        ):
            raise ImportModelError("unsafe_filesystem")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        attempts = _child_dir(private, "attempts", stack, create=True)
        receipts = _child_dir(private, "receipts", stack, create=True)
        for directory in (attempts, receipts):
            info = os.fstat(directory)
            if info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ImportModelError("permission_denied")
        yield src, project, attempts, receipts, private


def _run(
    approval: LocalImportApproval | None,
    *,
    state_root: Path,
    authorize: Authorize,
    decoder: Decoder,
    clone: Clone | None,
    free_bytes: FreeBytes | None,
    inspected_recovery: bool,
) -> ImportExecution:
    if (
        not isinstance(approval, LocalImportApproval)
        or not callable(authorize)
        or not callable(getattr(decoder, "decode", None))
    ):
        raise ImportModelError("approval_required")
    try:
        permitted = authorize(approval)
    except Exception as error:
        raise ImportModelError("permission_denied") from error
    if permitted is not True:
        raise ImportModelError("permission_denied")
    try:
        with (
            _guarded_roots(approval, state_root) as (
                source_root,
                project,
                attempts,
                receipts,
                _,
            ),
            ExitStack() as stack,
        ):
            attempt = _read_record(attempts, approval.import_id + ".json")
            if (
                attempt is not None
                and attempt.get("fingerprint") != approval.request_fingerprint()
            ):
                raise ImportModelError("import_conflict")
            if _read_record(receipts, approval.import_id + ".json") is not None:
                if attempt is None:
                    raise ImportModelError("needs_inspection")
                asset_fd = _asset_directory(project, approval, stack, create=False)
                result = _read_and_validate_receipt(
                    approval, receipts, asset_fd, decoder, stack
                )
                return ImportExecution("duplicate", result)
            if attempt is not None and not inspected_recovery:
                raise ImportModelError("incomplete_attempt")
            if inspected_recovery and attempt is None:
                raise ImportModelError("incomplete_attempt")
            source = _source_fd(source_root, approval.source_segments, stack)
            source_identity = _verified_source(source, approval)
            if inspected_recovery:
                asset_fd = _asset_directory(project, approval, stack, create=False)
                target_fd = _read_final(asset_fd, approval.display_name, stack)
                _verify_target(target_fd, approval)
                recorded_fd = target_fd
                decoded = _decoded(decoder, target_fd, approval)
                _check_source_locator(source_root, approval, source, source_identity)
                mode_record = _read_record(attempts, approval.import_id + ".mode.json")
                if (
                    mode_record is None
                    or mode_record.get("fingerprint") != approval.request_fingerprint()
                ):
                    raise ImportModelError("needs_inspection")
                mode = mode_record.get("completedMode")
                if mode not in ("clone", "copy"):
                    raise ImportModelError("needs_inspection")
            else:
                if (
                    free_bytes
                    or (lambda fd: os.statvfs(fd).f_bavail * os.statvfs(fd).f_frsize)
                )(project) < approval.expected_size_bytes + approval.minimum_free_bytes:
                    raise ImportModelError("insufficient_space")
                _write_once(
                    attempts,
                    approval.import_id + ".json",
                    {
                        "fingerprint": approval.request_fingerprint(),
                        "importId": approval.import_id,
                        "sourceRootId": approval.source_root_id,
                        "sourceSegments": list(approval.source_segments),
                        "state": "pending",
                    },
                )
                asset_fd = _asset_directory(project, approval, stack, create=True)
                # Existing target is never adopted during a regular import.
                try:
                    existing = os.open(approval.display_name, _READ, dir_fd=asset_fd)
                except FileNotFoundError:
                    pass
                else:
                    os.close(existing)
                    raise ImportModelError("publication_conflict")
                stage_name = f".{approval.import_id}.{uuid.uuid4().hex}.partial"
                stage = os.open(stage_name, os.O_RDWR | _NEW, 0o600, dir_fd=asset_fd)
                stack.callback(_close, stage)
                impl = clone or _platform_clone
                try:
                    cloned = impl(source, stage)
                except OSError as error:
                    if error.errno not in _UNSUPPORTED_CLONE:
                        raise
                    cloned = False
                if not cloned:
                    os.ftruncate(stage, 0)
                    os.lseek(stage, 0, os.SEEK_SET)
                    _copy(source, stage, approval.max_size_bytes)
                os.fsync(stage)
                _check_source_locator(source_root, approval, source, source_identity)
                _verify_target(stage, approval)
                if _identity(stage)[:2] == source_identity[:2]:
                    raise ImportModelError("unsafe_filesystem")
                decoded = _decoded(decoder, stage, approval)
                if _verified_source(source, approval) != source_identity:
                    raise ImportModelError("source_changed")
                _check_source_locator(source_root, approval, source, source_identity)
                # Check again immediately before publication, after decode.
                _verify_target(stage, approval)
                mode = "clone" if cloned else "copy"
                _write_once(
                    attempts,
                    approval.import_id + ".mode.json",
                    {
                        "fingerprint": approval.request_fingerprint(),
                        "completedMode": mode,
                    },
                )
                _rename_exclusive(asset_fd, stage_name, approval.display_name)
                published = _read_final(asset_fd, approval.display_name, stack)
                _verify_target(published, approval)
                if _identity(published)[:2] != _identity(stage)[:2]:
                    raise ImportModelError("needs_inspection")
                recorded_fd = published
                _check_source_locator(source_root, approval, source, source_identity)
            result = PortableImportResult.from_verified(
                approval, cast(CompletedMode, mode), decoded, datetime.now(UTC)
            )
            _write_once(
                receipts,
                approval.import_id + ".json",
                {
                    "fingerprint": approval.request_fingerprint(),
                    "result": result.to_portable_dict(),
                    "destinationIdentity": list(_identity(recorded_fd)),
                },
            )
            return ImportExecution(
                "recovered" if inspected_recovery else "completed", result
            )
    except ImportModelError:
        raise
    except (OSError, TypeError, ValueError) as error:
        if isinstance(error, OSError):
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise ImportModelError("source_unsafe") from error
            if error.errno in (errno.ENOENT,):
                raise ImportModelError("source_unavailable") from error
            if error.errno in (errno.ENOSPC, errno.EDQUOT):
                raise ImportModelError("insufficient_space") from error
            if error.errno in (errno.EACCES, errno.EPERM):
                raise ImportModelError("permission_denied") from error
        raise ImportModelError("io_failure") from error


def import_local_media(
    approval: LocalImportApproval | None,
    *,
    state_root: Path,
    authorize: Authorize,
    decoder: Decoder,
    clone: Clone | None = None,
    free_bytes: FreeBytes | None = None,
) -> ImportExecution:
    """Import approved source bytes; duplicates are read-only reverified.

    Source and private state roots must already exist. No ambient auto-approval,
    cleanup of partials, source deletion, network endpoint or public path output.
    """
    return _run(
        approval,
        state_root=state_root,
        authorize=authorize,
        decoder=decoder,
        clone=clone,
        free_bytes=free_bytes,
        inspected_recovery=False,
    )


def reconcile_inspected_import(
    approval: LocalImportApproval | None,
    *,
    state_root: Path,
    authorize: Authorize,
    decoder: Decoder,
) -> ImportExecution:
    """Explicit inspected adoption, only with exact existing bytes + mode evidence.

    Never calls import for pending attempts, never removes/overwrites leftovers.
    This is a trusted operator action; do not expose it in the browser/CLI.
    """
    return _run(
        approval,
        state_root=state_root,
        authorize=authorize,
        decoder=decoder,
        clone=None,
        free_bytes=None,
        inspected_recovery=True,
    )
