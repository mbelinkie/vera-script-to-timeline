"""Pure #381 identity/approval/result contracts; no filesystem/media operations."""

from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.local_media_import_model import (
    ClipUse,
    DecodedMediaFacts,
    ImportModelError,
    LocalImportApproval,
    PortableImportResult,
    PrivateAttemptRecord,
)

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
SOURCE = Path("/private-fixtures/producer-ROOT-CANARY/sources")
PROJECT = Path("/private-fixtures/producer-PROJECT-CANARY/project")
VERIFIED_AT = datetime(2026, 11, 7, 13, 0, tzinfo=UTC)


def _id(num: int) -> str:
    return str(uuid.UUID(int=num, version=4))


def _approval(**overrides: Any) -> LocalImportApproval:
    data: dict[str, Any] = {
        "project_id": _id(1),
        "import_id": _id(2),
        "asset_id": _id(3),
        "media_reference_id": _id(4),
        "source_root_id": "operator_approved_fixture",
        "source_root": SOURCE,
        "project_root": PROJECT,
        "source_segments": ("clips", "Shot 01.png"),
        "expected_content_hash": HASH_A,
        "expected_size_bytes": 1234,
        "max_size_bytes": 1_000_000,
        "minimum_free_bytes": 512,
        "kind": "image",
    }
    data.update(overrides)
    return LocalImportApproval(**data)


def _decoded(**overrides: Any) -> DecodedMediaFacts:
    data: dict[str, Any] = {
        "kind": "image",
        "probe_hash": HASH_B,
        "width": 800,
        "height": 600,
    }
    data.update(overrides)
    return DecodedMediaFacts(**data)


def _refused(code: str, callable_: Any, *args: Any, **kwargs: Any) -> None:
    with pytest.raises(ImportModelError) as raised:
        callable_(*args, **kwargs)
    assert raised.value.code == code
    safe = json.dumps(raised.value.to_portable_dict())
    assert '"status": "refused"' in safe
    assert "CANARY" not in safe
    assert "/private-fixtures/" not in safe


def test_portable_still_result_has_only_allowlisted_fields_and_no_private_paths() -> (
    None
):
    approval = _approval()
    assert approval.project_relative_locator == (
        f"Media/Local Images/{_id(3)}/Shot 01.png"
    )
    result = PortableImportResult.from_verified(
        approval, "clone", _decoded(), VERIFIED_AT
    )
    assert result.to_portable_dict() == {
        "schemaVersion": "vera-local-import-result/v1",
        "status": "completed",
        "projectId": _id(1),
        "importId": _id(2),
        "assetId": _id(3),
        "mediaReferenceId": _id(4),
        "kind": "image",
        "displayName": "Shot 01.png",
        "contentHash": HASH_A,
        "sizeBytes": 1234,
        "probeHash": HASH_B,
        "width": 800,
        "height": 600,
        "requestedMode": "clone",
        "completedMode": "clone",
        "originalRemovalStatus": "not_requested",
        "projectRelativeLocator": f"Media/Local Images/{_id(3)}/Shot 01.png",
        "verifiedAt": "2026-11-07T13:00:00Z",
        "buildQualification": "unqualified",
    }
    for data in (dataclasses.asdict(result), result.to_portable_dict()):
        wire = json.dumps(data, sort_keys=True, default=str)
        assert "CANARY" not in wire
        assert "sourceRoot" not in wire
        assert "sourceSegments" not in wire
        assert "operator_approved_fixture" not in wire
        assert "sourceLocator" not in wire
        assert "token" not in wire.lower()
    assert "CANARY" not in repr(result)
    assert "CANARY" not in repr(approval)


def test_portable_clip_copy_fallback_records_handles_without_build_qualification() -> (
    None
):
    selection = ClipUse(12, 48, 12, 8)
    approval = _approval(
        kind="clip", source_segments=("season", "broll.mp4"), clip_use=selection
    )
    decoded = _decoded(kind="clip", decoded_frame_count=70)
    result = PortableImportResult.from_verified(approval, "copy", decoded, VERIFIED_AT)
    wire = result.to_portable_dict()
    assert wire["projectRelativeLocator"] == f"Media/Local Clips/{_id(3)}/broll.mp4"
    assert wire["completedMode"] == "copy"
    assert wire["requestedMode"] == "clone"
    assert wire["originalRemovalStatus"] == "not_requested"
    assert wire["decodedFrameCount"] == 70
    assert wire["requestedClipUse"] == {
        "startFrame": 12,
        "endFrame": 48,
        "handleBeforeFrames": 12,
        "handleAfterFrames": 8,
    }
    assert wire["buildQualification"] == "unqualified"
    assert "frameMap" not in json.dumps(wire)
    assert "preparedMedia" not in json.dumps(wire)


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("project_id", "not-a-uuid", "invalid_identity"),
        ("asset_id", "00000000-0000-0000-0000-000000000000", "invalid_identity"),
        ("media_reference_id", _id(3).upper(), "invalid_identity"),
        ("media_reference_id", _id(3), "invalid_identity"),
        ("import_id", _id(1), "invalid_identity"),
        ("source_root_id", "../../bad", "invalid_approval"),
        ("source_root_id", "", "invalid_approval"),
        ("source_root", Path("./relative"), "invalid_approval"),
        ("project_root", Path("/private-fixtures/../another"), "invalid_approval"),
        ("project_root", SOURCE, "root_overlap"),
        ("source_root", PROJECT / "nested", "root_overlap"),
        ("expected_content_hash", "a" * 64, "invalid_approval"),
        ("expected_content_hash", "sha256:" + "A" * 64, "invalid_approval"),
        ("expected_content_hash", "sha256:" + "a" * 63, "invalid_approval"),
        ("expected_size_bytes", True, "invalid_approval"),
        ("expected_size_bytes", 0, "invalid_approval"),
        ("expected_size_bytes", 10**30, "invalid_approval"),
        ("max_size_bytes", 12, "size_limit"),
        ("minimum_free_bytes", -1, "invalid_approval"),
        ("kind", "audio", "unsupported_media"),
        ("requested_mode", "move", "unsupported_mode"),
        ("requested_mode", "reference", "unsupported_mode"),
        ("requested_mode", "copy", "unsupported_mode"),
        ("clip_use", ClipUse(0, 12), "invalid_bounds"),
        ("kind", "clip", "invalid_bounds"),
    ],
)
def test_approval_refusal_matrix(field: str, value: Any, code: str) -> None:
    _refused(code, _approval, **{field: value})


@pytest.mark.parametrize(
    "segments",
    [
        (),
        ("..", "image.png"),
        (".", "image.png"),
        ("dir/sub", "image.png"),
        ("file\\name.png",),
        ("C:trick.png",),
        ("/etc/passwd",),
        ("ftp://host/file",),
        ("\u2215etc.png",),
        ("\uff0fetc.png",),
        ("bad\u202etxt.png",),
        ("bad\x00name.png",),
        ("bad\nname.png",),
        ("bad\rname.png",),
        ("bad\tname.png",),
        ("bad\u2028name.png",),
        (" hidden.png",),
        ("hidden.png ",),
        (".hidden",),
        ("x" * 241 + ".png",),
        ("e\u0301.png",),  # non-normalized, ambiguous bytes
        ("\ud800",),  # unpaired surrogate
        ("normal.png",) * 33,
    ],
)
def test_relative_only_safe_source_segments(segments: tuple[str, ...]) -> None:
    _refused("invalid_locator", _approval, source_segments=segments)


def test_source_segments_are_not_a_raw_path_or_dynamic_url() -> None:
    _refused("invalid_locator", _approval, source_segments="/private/media.png")
    _refused("invalid_locator", _approval, source_segments=["file.png"])


def test_request_fingerprint_is_stable_but_binds_project_roots_bytes_and_bounds() -> (
    None
):
    approval = _approval()
    first = approval.request_fingerprint()
    assert first == _approval().request_fingerprint()
    assert first.startswith("sha256:") and len(first) == 71
    assert (
        first != _approval(source_root=Path("/another/private")).request_fingerprint()
    )
    assert (
        first != _approval(project_root=Path("/another/project")).request_fingerprint()
    )
    assert first != _approval(expected_content_hash=HASH_B).request_fingerprint()
    assert first != _approval(media_reference_id=_id(5)).request_fingerprint()
    assert (
        first
        != _approval(source_segments=("clips", "Shot 02.png")).request_fingerprint()
    )
    assert first != _approval(minimum_free_bytes=1).request_fingerprint()
    assert "CANARY" not in first
    clip = _approval(kind="clip", clip_use=ClipUse(2, 8))
    assert (
        clip.request_fingerprint()
        != _approval(kind="clip", clip_use=ClipUse(2, 8, 1, 0)).request_fingerprint()
    )


@pytest.mark.parametrize(
    "args",
    [
        (0, 0, 0, 0),
        (20, 15, 0, 0),
        (-1, 15, 0, 0),
        (0, 10, True, 0),
        (0, 10, 0, -1),
        (0, 10**20, 0, 0),
    ],
)
def test_selected_clip_range_rejects_invalid_frames(
    args: tuple[int, int, int, int],
) -> None:
    _refused("invalid_bounds", ClipUse, *args)


@pytest.mark.parametrize(
    "total,code",
    [
        (19, "invalid_bounds"),
        (20, "invalid_bounds"),
        (0, "invalid_bounds"),
        (True, "invalid_bounds"),
    ],
)
def test_clip_handles_require_verified_decoded_bounds(total: int, code: str) -> None:
    use = ClipUse(4, 18, 3, 3)
    _refused(code, use.check_decoded_frames, total)


def test_decoded_range_exact_edge_is_allowed_no_silent_extension() -> None:
    use = ClipUse(3, 17, 3, 3)
    use.check_decoded_frames(20)
    _refused("invalid_bounds", use.check_decoded_frames, 19)
    _refused("invalid_bounds", ClipUse(2, 17, 3, 3).check_decoded_frames, 20)


def test_invalid_probe_and_portable_combinations_refuse() -> None:
    _refused("invalid_approval", _decoded, probe_hash="bad")
    _refused("invalid_approval", _decoded, width=True)
    _refused("invalid_bounds", _decoded, decoded_frame_count=20)
    _refused("invalid_bounds", _decoded, kind="clip")
    _refused(
        "unsupported_media",
        PortableImportResult.from_verified,
        _approval(),
        "clone",
        _decoded(kind="clip", decoded_frame_count=20),
        VERIFIED_AT,
    )
    _refused(
        "unsupported_mode",
        PortableImportResult.from_verified,
        _approval(),
        "move",
        _decoded(),
        VERIFIED_AT,
    )
    _refused(
        "invalid_approval",
        PortableImportResult.from_verified,
        _approval(),
        "copy",
        _decoded(),
        datetime(2026, 11, 7),
    )
    _refused(
        "invalid_approval",
        PortableImportResult.from_verified,
        _approval(),
        "copy",
        _decoded(),
        VERIFIED_AT.astimezone(timezone(timedelta(hours=-5))),
    )


def test_private_record_has_no_accidental_public_serializer() -> None:
    approval = _approval()
    private = PrivateAttemptRecord(
        import_id=approval.import_id,
        request_fingerprint=approval.request_fingerprint(),
        source_root_id=approval.source_root_id,
        source_segments=approval.source_segments,
        state="pending",
    )
    assert private.state == "pending"
    assert not hasattr(private, "to_portable_dict")
    assert "CANARY" not in repr(private)
    _refused(
        "invalid_approval",
        dataclasses.replace,
        private,
        state="failed",
    )
    _refused(
        "invalid_approval",
        dataclasses.replace,
        private,
        state="completed",
        refusal_code="content_mismatch",
    )
    failed = dataclasses.replace(
        private, state="failed", refusal_code="content_mismatch"
    )
    assert failed.state == "failed"
    _refused("invalid_locator", dataclasses.replace, private, source_segments=("../",))
    _refused("invalid_approval", dataclasses.replace, private, refusal_code=[])


def test_no_input_files_or_folders_are_needed_to_construct_pure_models() -> None:
    # Neither root exists. A model constructor must not inspect or create them;
    # all fd, device/inode, hash and decode checks belong in the next phase.
    approval = _approval()
    assert not SOURCE.exists()
    assert not PROJECT.exists()
    PortableImportResult.from_verified(approval, "copy", _decoded(), VERIFIED_AT)
    assert not SOURCE.exists()
    assert not PROJECT.exists()
