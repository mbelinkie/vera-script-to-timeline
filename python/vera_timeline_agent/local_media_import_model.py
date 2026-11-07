"""Pure, local-only #381 import approval and sanitized receipt contracts.

Constructing these values NEVER authenticates a caller, reads a file, verifies a
probe, or authorizes a side effect. The #381 engine must receive a separately
trusted operator approval and independently verify every claimed observation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

MediaKind = Literal["image", "clip"]
CompletedMode = Literal["clone", "copy"]
AttemptState = Literal["pending", "failed", "needs_inspection", "completed"]
RefusalCode = Literal[
    "approval_required",
    "invalid_approval",
    "invalid_identity",
    "invalid_locator",
    "invalid_bounds",
    "unsupported_mode",
    "source_unavailable",
    "source_unsafe",
    "source_changed",
    "content_mismatch",
    "size_limit",
    "root_overlap",
    "unsafe_filesystem",
    "unsupported_media",
    "undecodable_media",
    "insufficient_space",
    "permission_denied",
    "publication_conflict",
    "import_conflict",
    "incomplete_attempt",
    "needs_inspection",
    "io_failure",
]

MAX_SAFE_INTEGER = 9_007_199_254_740_991
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ROOT_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\Z")
_CONFUSABLE_SEPARATORS = frozenset("\u2044\u2215\u2216\u29f8\u29f9\uff0f\uff3c\ufe68")
_ERROR_MESSAGES: dict[RefusalCode, str] = {
    "approval_required": "Trusted local import approval is required.",
    "invalid_approval": "The import approval is invalid.",
    "invalid_identity": "The import identity is invalid.",
    "invalid_locator": "The requested local file name or locator is unsafe.",
    "invalid_bounds": "The selected media range is not verified as playable.",
    "unsupported_mode": "This import mode is not supported.",
    "source_unavailable": "The selected source is unavailable.",
    "source_unsafe": "The selected source is not a safe regular file.",
    "source_changed": "The selected source changed during verification.",
    "content_mismatch": "The selected source does not match approved bytes.",
    "size_limit": "The selected source exceeds approved size limits.",
    "root_overlap": "The source and project roots must be separate.",
    "unsafe_filesystem": "The filesystem cannot guarantee a safe import.",
    "unsupported_media": "The selected media format is unsupported.",
    "undecodable_media": "The selected media could not be decoded safely.",
    "insufficient_space": "Insufficient verified project storage is available.",
    "permission_denied": "The import is not permitted.",
    "publication_conflict": "The project destination already exists or is unsafe.",
    "import_conflict": "This import identity belongs to another request.",
    "incomplete_attempt": "An incomplete import requires inspection.",
    "needs_inspection": "The existing import requires manual inspection.",
    "io_failure": "The local import could not be completed.",
}


class ImportModelError(ValueError):
    """Fixed, path-free refusal safe for CLI output; never include input data."""

    def __init__(self, code: RefusalCode) -> None:
        self.code = code
        super().__init__(_ERROR_MESSAGES[code])

    def to_portable_dict(self) -> dict[str, str]:
        return {
            "status": "refused",
            "code": self.code,
            "message": _ERROR_MESSAGES[self.code],
        }


def _uuid(value: object) -> str:
    if not isinstance(value, str):
        raise ImportModelError("invalid_identity")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as error:
        raise ImportModelError("invalid_identity") from error
    if str(parsed) != value or parsed.variant != uuid.RFC_4122 or parsed.int == 0:
        raise ImportModelError("invalid_identity")
    return value


def _hash(value: object) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ImportModelError("invalid_approval")
    return value


def _safe_int(value: object, *, positive: bool = False) -> int:
    if (
        type(value) is not int
        or not 0 <= value <= MAX_SAFE_INTEGER
        or (positive and value == 0)
    ):
        raise ImportModelError("invalid_approval")
    return value


def _safe_component(value: object) -> str:
    try:
        byte_length = len(value.encode("utf-8")) if isinstance(value, str) else 0
    except UnicodeError as error:
        raise ImportModelError("invalid_locator") from error
    if (
        not isinstance(value, str)
        or not value
        or value != unicodedata.normalize("NFC", value)
        or byte_length > 240
        or value[0] in {".", " "}
        or value[-1] in {".", " "}
        or ":" in value
        or "/" in value
        or "\\" in value
        or any(
            c in _CONFUSABLE_SEPARATORS
            or unicodedata.category(c) in {"Cc", "Cf", "Zl", "Zp"}
            for c in value
        )
    ):
        raise ImportModelError("invalid_locator")
    return value


def _root(path: object) -> Path:
    # These are *trusted config inputs*, not source strings from a browser.
    # Resolving or checking symlinks here would race; the engine opens roots by
    # descriptor and checks its actual device/inode and approved boundaries.
    if (
        not isinstance(path, Path)
        or not path.is_absolute()
        or ".." in path.parts
        or any(unicodedata.category(c) in {"Cc", "Cf"} for c in str(path))
    ):
        raise ImportModelError("invalid_approval")
    return path


def _frame(value: object, *, positive: bool = False) -> int:
    try:
        return _safe_int(value, positive=positive)
    except ImportModelError as error:
        raise ImportModelError("invalid_bounds") from error


@dataclass(frozen=True)
class ClipUse:
    """Half-open original-source frames; handles must fit *decoded* bounds."""

    start_frame: int
    end_frame: int
    handle_before_frames: int = 0
    handle_after_frames: int = 0

    def __post_init__(self) -> None:
        for value in (
            self.start_frame,
            self.end_frame,
            self.handle_before_frames,
            self.handle_after_frames,
        ):
            _frame(value)
        if self.start_frame >= self.end_frame:
            raise ImportModelError("invalid_bounds")

    def check_decoded_frames(self, total_frames: int) -> None:
        if (
            type(total_frames) is not int
            or not 0 < total_frames <= MAX_SAFE_INTEGER
            or self.start_frame < self.handle_before_frames
            or self.end_frame + self.handle_after_frames > total_frames
        ):
            raise ImportModelError("invalid_bounds")


@dataclass(frozen=True, repr=False)
class LocalImportApproval:
    """Explicit trusted local request; the receipt is never authorization."""

    project_id: str
    import_id: str
    asset_id: str
    media_reference_id: str
    source_root_id: str
    source_root: Path
    project_root: Path
    source_segments: tuple[str, ...]
    expected_content_hash: str
    expected_size_bytes: int
    max_size_bytes: int
    minimum_free_bytes: int
    kind: MediaKind
    clip_use: ClipUse | None = None
    requested_mode: Literal["clone"] = "clone"

    def __post_init__(self) -> None:
        ids = (
            _uuid(self.project_id),
            _uuid(self.import_id),
            _uuid(self.asset_id),
            _uuid(self.media_reference_id),
        )
        if len(set(ids)) != len(ids):
            raise ImportModelError("invalid_identity")
        if not isinstance(self.source_root_id, str) or not _ROOT_ID.fullmatch(
            self.source_root_id
        ):
            raise ImportModelError("invalid_approval")
        source, project = _root(self.source_root), _root(self.project_root)
        # Lexical overlap is an *early* check, never a substitute for engine
        # descriptor and actual-root overlap checks (including symlink aliases).
        if os.path.commonpath((source, project)) in {str(source), str(project)}:
            raise ImportModelError("root_overlap")
        if (
            not isinstance(self.source_segments, tuple)
            or not 1 <= len(self.source_segments) <= 32
        ):
            raise ImportModelError("invalid_locator")
        for segment in self.source_segments:
            _safe_component(segment)
        _hash(self.expected_content_hash)
        _safe_int(self.expected_size_bytes, positive=True)
        _safe_int(self.max_size_bytes, positive=True)
        _safe_int(self.minimum_free_bytes)
        if self.expected_size_bytes > self.max_size_bytes:
            raise ImportModelError("size_limit")
        if self.requested_mode != "clone":
            raise ImportModelError("unsupported_mode")
        if self.kind not in ("image", "clip"):
            raise ImportModelError("unsupported_media")
        if (self.kind == "clip") != isinstance(self.clip_use, ClipUse):
            raise ImportModelError("invalid_bounds")

    @property
    def display_name(self) -> str:
        return self.source_segments[-1]

    @property
    def project_relative_locator(self) -> str:
        category = "Local Images" if self.kind == "image" else "Local Clips"
        return f"Media/{category}/{self.asset_id}/{self.display_name}"

    def request_fingerprint(self) -> str:
        """Private only: includes root paths to reject cross-root replay."""
        fields = {
            "version": "vera-local-import-request/v1",
            "projectId": self.project_id,
            "importId": self.import_id,
            "assetId": self.asset_id,
            "mediaReferenceId": self.media_reference_id,
            "sourceRootId": self.source_root_id,
            "sourceRoot": str(self.source_root),
            "projectRoot": str(self.project_root),
            "sourceSegments": self.source_segments,
            "expectedContentHash": self.expected_content_hash,
            "expectedSizeBytes": self.expected_size_bytes,
            "maxSizeBytes": self.max_size_bytes,
            "minimumFreeBytes": self.minimum_free_bytes,
            "kind": self.kind,
            "clipUse": (
                None
                if self.clip_use is None
                else (
                    self.clip_use.start_frame,
                    self.clip_use.end_frame,
                    self.clip_use.handle_before_frames,
                    self.clip_use.handle_after_frames,
                )
            ),
            "requestedMode": self.requested_mode,
        }
        encoded = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class DecodedMediaFacts:
    """Input from *independent verified decoder*, NOT an import success claim."""

    kind: MediaKind
    probe_hash: str
    width: int
    height: int
    decoded_frame_count: int | None = None

    def __post_init__(self) -> None:
        _hash(self.probe_hash)
        _safe_int(self.width, positive=True)
        _safe_int(self.height, positive=True)
        if self.kind == "image" and self.decoded_frame_count is not None:
            raise ImportModelError("invalid_bounds")
        if self.kind == "clip":
            _frame(self.decoded_frame_count, positive=True)
        if self.kind not in ("image", "clip"):
            raise ImportModelError("unsupported_media")


@dataclass(frozen=True, repr=False)
class PrivateAttemptRecord:
    """Only stored in protected local receipt state; never exported as JSON."""

    import_id: str
    request_fingerprint: str
    source_root_id: str
    source_segments: tuple[str, ...]
    state: AttemptState
    refusal_code: RefusalCode | None = None

    def __post_init__(self) -> None:
        _uuid(self.import_id)
        _hash(self.request_fingerprint)
        if not isinstance(self.source_root_id, str) or not _ROOT_ID.fullmatch(
            self.source_root_id
        ):
            raise ImportModelError("invalid_approval")
        if (
            not isinstance(self.source_segments, tuple)
            or not 1 <= len(self.source_segments) <= 32
        ):
            raise ImportModelError("invalid_locator")
        for segment in self.source_segments:
            _safe_component(segment)
        if self.state not in ("pending", "failed", "needs_inspection", "completed"):
            raise ImportModelError("invalid_approval")
        if self.refusal_code is not None and (
            not isinstance(self.refusal_code, str)
            or self.refusal_code not in _ERROR_MESSAGES
        ):
            raise ImportModelError("invalid_approval")
        if (self.refusal_code is not None) != (self.state == "failed"):
            raise ImportModelError("invalid_approval")


@dataclass(frozen=True)
class PortableImportResult:
    """Portable type contains no private approval or source-root fields."""

    project_id: str
    import_id: str
    asset_id: str
    media_reference_id: str
    kind: MediaKind
    display_name: str
    content_hash: str
    size_bytes: int
    probe_hash: str
    width: int
    height: int
    completed_mode: CompletedMode
    verified_at: datetime
    decoded_frame_count: int | None = None
    clip_use: ClipUse | None = None

    @classmethod
    def from_verified(
        cls,
        approval: LocalImportApproval,
        completed_mode: CompletedMode,
        decoded: DecodedMediaFacts,
        verified_at: datetime,
    ) -> PortableImportResult:
        """Format evidence supplied *after* the engine has verified it.

        This is not a verifier; only an engine with separately trusted roots,
        opened-byte comparison and decoded proof may publish the result.
        """
        if decoded.kind != approval.kind:
            raise ImportModelError("unsupported_media")
        return cls(
            project_id=approval.project_id,
            import_id=approval.import_id,
            asset_id=approval.asset_id,
            media_reference_id=approval.media_reference_id,
            kind=approval.kind,
            display_name=approval.display_name,
            content_hash=approval.expected_content_hash,
            size_bytes=approval.expected_size_bytes,
            probe_hash=decoded.probe_hash,
            width=decoded.width,
            height=decoded.height,
            completed_mode=completed_mode,
            verified_at=verified_at,
            decoded_frame_count=decoded.decoded_frame_count,
            clip_use=approval.clip_use,
        )

    def __post_init__(self) -> None:
        ids = (
            _uuid(self.project_id),
            _uuid(self.import_id),
            _uuid(self.asset_id),
            _uuid(self.media_reference_id),
        )
        if len(set(ids)) != len(ids):
            raise ImportModelError("invalid_identity")
        _safe_component(self.display_name)
        _hash(self.content_hash)
        _hash(self.probe_hash)
        _safe_int(self.size_bytes, positive=True)
        _safe_int(self.width, positive=True)
        _safe_int(self.height, positive=True)
        if self.completed_mode not in ("clone", "copy"):
            raise ImportModelError("unsupported_mode")
        if self.kind not in ("image", "clip"):
            raise ImportModelError("unsupported_media")
        if not isinstance(self.verified_at, datetime) or (
            self.verified_at.utcoffset() != timedelta(0)
        ):
            raise ImportModelError("invalid_approval")
        if self.kind == "image":
            if self.clip_use is not None or self.decoded_frame_count is not None:
                raise ImportModelError("invalid_bounds")
        elif not isinstance(self.clip_use, ClipUse):
            raise ImportModelError("invalid_bounds")
        else:
            decoded = _frame(self.decoded_frame_count, positive=True)
            self.clip_use.check_decoded_frames(decoded)

    @property
    def project_relative_locator(self) -> str:
        category = "Local Images" if self.kind == "image" else "Local Clips"
        return f"Media/{category}/{self.asset_id}/{self.display_name}"

    def to_portable_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "schemaVersion": "vera-local-import-result/v1",
            "status": "completed",
            "projectId": self.project_id,
            "importId": self.import_id,
            "assetId": self.asset_id,
            "mediaReferenceId": self.media_reference_id,
            "kind": self.kind,
            "displayName": self.display_name,
            "contentHash": self.content_hash,
            "sizeBytes": self.size_bytes,
            "probeHash": self.probe_hash,
            "width": self.width,
            "height": self.height,
            "requestedMode": "clone",
            "completedMode": self.completed_mode,
            "originalRemovalStatus": "not_requested",
            "projectRelativeLocator": self.project_relative_locator,
            "verifiedAt": self.verified_at.isoformat().replace("+00:00", "Z"),
            "buildQualification": "unqualified",
        }
        if self.clip_use is not None:
            data["decodedFrameCount"] = self.decoded_frame_count
            data["requestedClipUse"] = {
                "startFrame": self.clip_use.start_frame,
                "endFrame": self.clip_use.end_frame,
                "handleBeforeFrames": self.clip_use.handle_before_frames,
                "handleAfterFrames": self.clip_use.handle_after_frames,
            }
        return data
