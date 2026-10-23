"""Static package admission for the bounded output qualification lane.

The ordinary profile is only a wrapper around the unchanged public v2 package
verifier.  The R16 profile is a separate, qualification-only exception whose
input, compiler output, media preparation and diagnostics are pinned here.
The current Presenter profile separately reproduces its fixed issue-owned
fixture with fresh current-compiler execution inputs.
This module never contacts Resolve and never grants native operator authority.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import io
import json
import os
import re
import stat
import struct
import subprocess
import wave
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from fractions import Fraction
from functools import wraps
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from . import v2_package
from .qualification_output_records_v2 import (
    OutputConsistencyError,
    _canonical,
    _parse,
    validate_temporary_presenter_report,
)
from .qualification_output_v2 import SourceProof
from .roundtrip_build import ProofBuildError
from .roundtrip_v2_audio import (
    narration_evidence_method,
    verify_measured_narration_evidence,
)
from .source_audio_endpoint import endpoint_plan, endpoint_wav

Json = dict[str, Any]

SYNTHETIC_PROFILE = "verified-v2-package/v1"
MATRIX_PROFILE = "qualification-output-studio-matrix/v1"
MATRIX_PREPARATION_ROOT = (
    Path.home()
    / "Library/Application Support/VERA/qualification-output-preparation"
    / "issue178-20261016-01/cases"
)
_PUBLIC_PROFILES = frozenset({SYNTHETIC_PROFILE, MATRIX_PROFILE})
R16_PROFILE = "qualification-output-r16-presenter-override/v1"
PRESENTER_PROFILE = "qualification-output-current-presenter/v1"
ADMISSION_SCHEMA = "qualification-output-package-admission/v1"
INVENTORY_SCHEMA = "qualification-output-package-inventory/v1"
CREATIVE_UNQUALIFIED = "unqualified_temporary_presenter"
_PROFILES = frozenset({*_PUBLIC_PROFILES, R16_PROFILE, PRESENTER_PROFILE})
_PRESENTER_ROOT = MATRIX_PREPARATION_ROOT / "presenter-alpha-01"
_PRESENTER_INPUT_PINS = {
    "script-document-v2.json": (
        "a9b0c63b823dd22f0f4e187d0ec5b2a528115fa065a89106123734957b813681"
    ),
    "compiler-dependencies-v2.json": (
        "d0f6b7e595e7d5fd4cf5b8216f299fc601f46d3766e47d9e6601af6ffd336aca"
    ),
}
_PRESENTER_PNG_SHA256 = (
    "928d034d15389a5a5891c435c6318fd8c48c4ae9c8db4cda67f3d359714d1f91"
)
_PRESENTER_SLOT = "8ef61d23-9625-5b03-a046-e3f1051bbd75"
_EXPECTED_ORIGINAL_DOCUMENT = (
    "27b9d5ddfb097f254d44ce0b6428e461f9e948010e95e1a4c817a8c71e76fa71"
)
_EXPECTED_ORIGINAL_DEPENDENCIES = (
    "19c4e7f4777afbd756a67dbb558d73bd87a705c38c1d1dc3d2e330436f8876a9"
)
_EXPECTED_EXECUTION_DEPENDENCIES = (
    "ca837b3d46b07d3c431bf923c3c99629f21777872ff1bbabd0bbca6834f48780"
)
_EXPECTED_DELTA = "2b15ad7400c8220fe726215eedd35c276ece95c68fbcff8966ce54ed57219c7d"
_MAX_JSON = 8 * 1024 * 1024
_MAX_WAV = 128 * 1024 * 1024
_FRAME_SAMPLES = 2002

_PRIVATE = Path(
    "/Users/matthewbelinkie/Library/Application Support/VERA/private-preparation"
)
_R16 = _PRIVATE / "issue-148/2026-10-11-r16-producer-review"
_R12 = _PRIVATE / "issue-148/2026-10-11-r12-still-bindings"
_CANDIDATE = _R16 / "candidate-inputs"
_PARENT = (
    _PRIVATE / "issue-145/advance-inputs/issue209-r16-preparation-cn209p1-attempt02"
)
_ORIGINAL_DOCUMENT = _CANDIDATE / "script-document-v2.json"
_ORIGINAL_DEPENDENCIES = _CANDIDATE / "compiler-dependencies-v2.json"
_EXECUTION_DOCUMENT = (
    _PARENT / "parent-admission/original-script-document-byte-identical.json"
)
_EXECUTION_DEPENDENCIES = _PARENT / "execution-compiler-dependencies-v2.json"
_MANIFEST = _PARENT / "parent-admission/timeline-manifest-v2.json"
_REPORT = _PARENT / "parent-admission/build-report-v2.json"
_COMPILE_ONE = _PARENT / "parent-admission/compile-1.json"
_COMPILE_TWO = _PARENT / "parent-admission/compile-2.json"
_DELTA = _PARENT / "execution-dependency-delta.json"
_HOST_ACCEPTANCE = (
    _PRIVATE / "issue-145/advance-inputs/cn209p1r2-producer-acceptance.json"
)
_PREPARED_ROOT = _PARENT / "media-preparation/published"
_R14 = _CANDIDATE / "Receipts/r14-boundary-binding-receipt.json"
_R6 = _CANDIDATE / "Receipts/r6-boundary-review-receipt.json"
_R6_TARGET = _R12 / "candidate-inputs/Receipts/r6-boundary-review-receipt.json"
_NODE = Path(
    "/Users/matthewbelinkie/.local/share/vera/toolchains/node-v24.19.0-darwin-x64/bin/node"
)
_COMPILER = (
    Path(__file__).resolve().parents[2]
    / "packages/contracts/src/issue-190-compile-cli.ts"
)
_GENERIC_TORSO = (
    Path(__file__).resolve().parents[2]
    / "packages/contracts/src/assets/generic-torso-v1.json"
)
_FFMPEG = Path("/usr/local/Cellar/ffmpeg/8.1.2_1/bin/ffmpeg")
_FFPROBE = Path("/usr/local/Cellar/ffmpeg/8.1.2_1/bin/ffprobe")
_FFMPEG_SHA256 = "284023fbfa0480733ac83087f3afdb9ddb0bcdfe75191c20c8cefc034255e65c"
_FFPROBE_SHA256 = "e5c6567171b5af525de016d1a7907553bbdc86a81b7d25d91046c0aa25361eb2"
_APPROVAL_SHA256 = "c48d6d4632c3e87eb6933ebe350e0b7c9334870f8f1dc90c3beb13cfff190e88"
_R14_SHA256 = "25a366ab72f4d4a1f0419f0777046cd7b71294a2dc4dfa5a09c766b71f7fa374"
_R6_SHA256 = "a67fb8880fa6b88471fb85ef590bff8c557b9a79e3d0f679d7ab0cc4780adf22"
_R12_STILLS_SHA256 = "dc7fc12d1fb24bed52f5099aaf7d9a8b090779a2500f94df9d7627f1585a758f"
_R12_STILLS_SCHEMA = "issue-148-r12-still-binding-evidence/v1"
_R12_IMPLEMENTATION = "4c92884665629b283ce679f9ffc51859a32239e6"
_MAX_R16_DURATION_FRAMES = 1498
_R16_MANIFEST_SHA256 = (
    "89c83891dd5835e73495996a5357ff13d20e2dd4353f201b193c04bd04542e9b"
)
_R16_REPORT_SHA256 = "8171995f062c039c4323015015fe7e603d43d8eededc063115982388132501b5"
_R16_COMPILE_ONE_SHA256 = (
    "ef13c26c16862f0a5e3a1606f70110833bf381fb5fbe91f9fc2086fe72a02dac"
)
_R16_COMPILE_TWO_SHA256 = _R16_COMPILE_ONE_SHA256
# Names used by the native sibling when it checks the same raw-vector domain.
_R16_TIMELINE_MANIFEST_SHA256 = _R16_MANIFEST_SHA256
_R16_BUILD_REPORT_SHA256 = _R16_REPORT_SHA256
_R16_COMPILE_1_SHA256 = _R16_COMPILE_ONE_SHA256
_R16_COMPILE_2_SHA256 = _R16_COMPILE_TWO_SHA256
_VERIFIED_ADMISSION_SCHEMA = "qualification-output-verified-admission/v2"
_VERIFIED_ADMISSION_RELATIVE_PATH = "Qualification/verified-admission.json"
_VERIFICATION_PROOF_RELATIVE_ROOT = "Verification/proofs"
_VERIFICATION_PROOF_BYTE_FIELDS = (
    "record",
    "receipt",
    "timing",
    "review",
    "originRecord",
    "originReceipt",
)
_ADMISSION_CACHE_ROOT = (
    Path.home()
    / "Library/Application Support/VERA/qualification-output-host/v1/admission-cache"
)
_ADMISSION_CACHE_KEY = _ADMISSION_CACHE_ROOT / "hmac-key"
_ADMISSION_SEAL_FILENAME = "qualification-output-package-seal.json"
_ADMISSION_SEAL_SCHEMA = "qualification-output-package-seal/v1"
_NARRATION_TIMING_HASHES = {
    "76b27ed5-28c8-5200-ac4c-95a8769c3b4b": (
        "ab6fd274468ab5fdd628c00e126006afd4a599cffc6a3456903f5f9852c4da83"
    ),
    "c8bf89a1-f73a-5ba2-abaf-30feb8007945": (
        "d89eaa30be0d91209e00407ee7aa012079cf5497672ecbd34803d061c2ae1b67"
    ),
}
_PREPARED_Q = {
    "sha256:209c82565fdb3da873cae06f872bca30f6698b97036908dc7ba051735fe178ec": 1549548,
    "sha256:d5de45ebbb30d42ac16f255403c9208231a4ddf80d99cd9c50449beb24bce012": 11629618,
    "sha256:72415e7047e1e1e91010c9a847cc2947de6a9e11d7bef33b2bf6fe04e9581b8f": 5333328,
    "sha256:6b2101b8c2209e50c088ec174b6f559a6fb6f7e567f2b8b3855320ae8b07fb74": 792792,
}
_PREPARED_FIELDS = frozenset(
    {
        "authorizationReference",
        "originalSource.probeHash",
        "profile.policyHash",
        "profile.profileHash",
        "profile.profileVersion",
        "profile.toolHash",
        "requirementKey",
        "timeMapping.mappingHash",
        "timeMapping.sourceFrameMap.descriptorHash",
        "timeMapping.sourceFrameMap.probeHash",
        "timeMapping.sourceFrameMap.sourceAudioStreamMappings[0].probeHash",
        "verification.probeHash",
    }
)
_OCCURRENCE_FIELDS = frozenset(
    {
        "preparedMediaRequirementKey",
        "sourceFrameMap.descriptorHash",
        "sourceFrameMap.probeHash",
        "sourceFrameMap.sourceAudioStreamMappings[0].probeHash",
        "sourceSnapshot.probeHash",
        "sourceSnapshot.snapshotId",
    }
)


class QualificationPackageError(ValueError):
    """The package or one of its exact provenance inputs cannot be admitted."""


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise QualificationPackageError(message)


def _object(value: object, message: str) -> Json:
    _need(type(value) is dict, message)
    assert isinstance(value, dict)
    return value


def _array(value: object, message: str) -> list[Any]:
    _need(type(value) is list, message)
    assert isinstance(value, list)
    return value


def _text(value: object, message: str) -> str:
    _need(type(value) is str, message)
    assert isinstance(value, str)
    return value


def _admission_boundary[**P, T](function: Callable[P, T]) -> Callable[P, T]:
    @wraps(function)
    def bounded(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return function(*args, **kwargs)
        except QualificationPackageError:
            raise
        except (
            OSError,
            KeyError,
            IndexError,
            TypeError,
            AttributeError,
            ValueError,
            subprocess.SubprocessError,
            v2_package.V2PackageError,
        ) as error:
            raise QualificationPackageError(
                f"package admission refused: {error}"
            ) from error

    return bounded


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    before = path.lstat()
    _need(stat.S_ISREG(before.st_mode), f"regular file required: {path.name}")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        _need(
            (before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
            f"file changed before hashing: {path.name}",
        )
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        after = os.fstat(stream.fileno())
    _need(
        (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        )
        == (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ),
        f"file changed while hashing: {path.name}",
    )
    return digest.hexdigest()


def _read(path: Path, *, maximum: int = _MAX_JSON, regular: bool = True) -> bytes:
    _need(path.is_absolute(), "absolute admission input path required")
    info = path.lstat()
    if regular:
        _need(stat.S_ISREG(info.st_mode), f"regular input required: {path.name}")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        _need(
            (info.st_dev, info.st_ino, info.st_mode)
            == (before.st_dev, before.st_ino, before.st_mode),
            f"input was replaced before reading: {path.name}",
        )
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    final = path.lstat()
    _need(
        (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        == (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ),
        f"input changed while reading: {path.name}",
    )
    _need(
        (
            final.st_dev,
            final.st_ino,
            final.st_mode,
            final.st_size,
            final.st_mtime_ns,
            final.st_ctime_ns,
        )
        == (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ),
        f"input was replaced after reading: {path.name}",
    )
    _need(len(raw) <= maximum, f"input exceeds the fixed bound: {path.name}")
    return raw


def _json(raw: bytes, label: str) -> Json:
    try:
        return _parse(raw)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise QualificationPackageError(f"invalid {label} JSON") from error


def _identity_delta(raw: bytes) -> Json:
    """The pinned filesystem receipt includes nanosecond integers, not frames."""
    _need(
        _sha(raw) == _EXPECTED_DELTA,
        "retained original-identity/delta evidence changed",
    )

    def pairs(items: list[tuple[str, Any]]) -> Json:
        result: Json = {}
        for key, value in items:
            _need(key not in result, "duplicate key in identity evidence")
            result[key] = value
        return result

    def invalid(value: str) -> Any:
        raise QualificationPackageError(f"nonfinite identity evidence: {value}")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    _need(type(value) is dict, "identity evidence object required")
    assert isinstance(value, dict)
    return value


def _compiler_json_hash(value: object) -> str:
    return v2_package._compiler_hash(value)


def _state(path: Path) -> tuple[int, int, int, int, int]:
    info = path.stat(follow_symlinks=False)
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _file_identity(path: Path) -> dict[str, int]:
    info = path.stat(follow_symlinks=False)
    return {
        "device": info.st_dev,
        "inode": info.st_ino,
        "mode": stat.S_IFMT(info.st_mode),
        "mtimeNs": info.st_mtime_ns,
        "size": info.st_size,
    }


def _cache_state(state: tuple[int, int, int, int, int]) -> list[str]:
    """Encode filesystem integers as text; mtimeNs is outside JSON's safe range."""
    return [str(value) for value in state]


def _parse_cache_state(value: object) -> tuple[int, int, int, int, int]:
    _need(
        type(value) is list
        and len(value) == 5
        and all(
            type(item) is str and re.fullmatch(r"[0-9]+", item) is not None
            for item in value
        ),
        "verified-admission filesystem state is malformed",
    )
    assert isinstance(value, list)
    return tuple(int(item) for item in value)  # type: ignore[return-value]


def _verification_blob_ref(
    package_root: Path, raw: bytes, suffix: str, label: str
) -> Json:
    _need(len(raw) <= _MAX_JSON, f"{label} exceeds the fixed bound")
    digest = _sha(raw)
    return {
        "path": f"{_VERIFICATION_PROOF_RELATIVE_ROOT}/{digest}{suffix}",
        "sha256": digest,
    }


def _read_verification_blob(
    package_root: Path, value: object, suffix: str, label: str
) -> bytes:
    row = _object(value, f"{label} reference is malformed")
    _need(
        set(row) == {"path", "sha256"},
        f"{label} reference shape differs",
    )
    relative = _text(row["path"], f"{label} path is malformed")
    digest = _text(row["sha256"], f"{label} hash is malformed")
    _need(
        re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
        f"{label} hash is malformed",
    )
    expected_relative = f"{_VERIFICATION_PROOF_RELATIVE_ROOT}/{digest}{suffix}"
    _need(relative == expected_relative, f"{label} path is not content addressed")
    path = package_root / relative
    _need(
        path.is_relative_to(package_root) and path.name == f"{digest}{suffix}",
        f"{label} path escapes package",
    )
    v2_package._require_path_components_no_symlink(path, label)
    raw = _read(path, maximum=_MAX_JSON)
    _need(_sha(raw) == digest, f"{label} bytes differ")
    return raw


def _retain_verification_blobs(
    package_root: Path,
    source_proofs: Mapping[str, SourceProof],
    proof_payloads: Mapping[tuple[str, str], tuple[Json, ...]],
    *,
    existing: bool,
) -> None:
    retained: set[Path] = set()
    for source_id, proof in source_proofs.items():
        for proof_field in _VERIFICATION_PROOF_BYTE_FIELDS:
            field_name = {
                "originRecord": "origin_record",
                "originReceipt": "origin_receipt",
            }.get(proof_field, proof_field)
            raw = getattr(proof, field_name)
            if raw is not None:
                reference = _verification_blob_ref(
                    package_root,
                    raw,
                    ".bin",
                    f"source {source_id} {proof_field}",
                )
                path = package_root / reference["path"]
                if path not in retained:
                    _retain(path, raw, existing=existing)
                    retained.add(path)
    for (kind, receipt_hash), payloads in proof_payloads.items():
        for payload in payloads:
            raw = _canonical(payload)
            reference = _verification_blob_ref(
                package_root,
                raw,
                ".json",
                f"proof payload {kind}/{receipt_hash}",
            )
            path = package_root / reference["path"]
            if path not in retained:
                _retain(path, raw, existing=existing)
                retained.add(path)


def _require_private_directory(path: Path, label: str) -> None:
    """Require a fixed local directory that cannot be redirected by a link."""
    _need(path.is_absolute(), f"{label} must be absolute")
    v2_package._require_path_components_no_symlink(path, label)
    try:
        info = path.stat(follow_symlinks=False)
    except OSError as error:
        raise QualificationPackageError(f"could not inspect {label}") from error
    _need(stat.S_ISDIR(info.st_mode), f"{label} must be a directory")
    _need(info.st_uid == os.getuid(), f"{label} owner differs")
    _need(stat.S_IMODE(info.st_mode) == 0o700, f"{label} must be private")


def _require_private_record(path: Path, label: str) -> os.stat_result:
    info = v2_package._require_regular(path, label)
    _need(info.st_uid == os.getuid(), f"{label} owner differs")
    _need(
        stat.S_IMODE(info.st_mode) == 0o400 and info.st_nlink == 1,
        f"{label} permissions differ",
    )
    return info


def _admission_hmac_key(*, create: bool = False) -> bytes:
    """Open or create the one fixed-root key without following any link."""
    root = _ADMISSION_CACHE_ROOT
    v2_package._require_path_components_no_symlink(root, "admission cache root")
    if create:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
    _require_private_directory(root, "admission cache root")
    key_path = _ADMISSION_CACHE_KEY
    v2_package._require_path_components_no_symlink(key_path, "admission cache key")
    descriptor = None
    if create:
        with suppress(FileExistsError):
            descriptor = os.open(
                key_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o400,
            )
    if descriptor is not None:
        key = os.urandom(32)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(key)
                stream.flush()
                os.fsync(stream.fileno())
                os.fchmod(stream.fileno(), 0o400)
        except BaseException:
            key_path.unlink(missing_ok=True)
            raise
    _require_private_record(key_path, "admission cache key")
    key = _read(key_path, maximum=64)
    _need(len(key) == 32, "admission cache key length differs")
    return key


def _admission_source_profiles_raw(record: Json) -> bytes:
    return _canonical(
        {"profile": record["profile"], "sourceProofs": record["sourceProofs"]}
    )


def _admission_code_source_graph_raw() -> bytes:
    from .roundtrip_v2_records import proof_source_hashes_v2

    return _canonical(proof_source_hashes_v2())


def _admission_seal_metadata(
    *,
    profile: str,
    admission_path: Path,
    cache_path: Path,
    admission_raw: bytes,
    cache_raw: bytes,
    source_profiles_raw: bytes,
    code_source_graph_raw: bytes,
) -> Json:
    return {
        "schemaVersion": _ADMISSION_SEAL_SCHEMA,
        "profile": profile,
        "admissionPath": str(admission_path.resolve(strict=True)),
        "cachePath": str(cache_path.resolve(strict=True)),
        "admissionSha256": _sha(admission_raw),
        "cacheSha256": _sha(cache_raw),
        "sourceProfilesSha256": _sha(source_profiles_raw),
        "codeSourceGraphSha256": _sha(code_source_graph_raw),
    }


def _admission_seal_message(
    metadata: Json,
    *,
    admission_raw: bytes,
    cache_raw: bytes,
    source_profiles_raw: bytes,
    code_source_graph_raw: bytes,
) -> bytes:
    def part(label: str, value: bytes) -> bytes:
        return label.encode("ascii") + len(value).to_bytes(8, "big") + value

    return (
        b"qualification-output-package-seal\x00"
        + b"metadata"
        + _canonical(metadata)
        + part("cache", cache_raw)
        + part("admission", admission_raw)
        + part("source-profiles", source_profiles_raw)
        + part("code-source-graph", code_source_graph_raw)
    )


def _admission_seal_raw(
    *,
    profile: str,
    admission_path: Path,
    cache_path: Path,
    admission_raw: bytes,
    cache_raw: bytes,
    source_profiles_raw: bytes,
    code_source_graph_raw: bytes,
) -> bytes:
    _need(
        _canonical(_json(cache_raw, "verified admission cache")) == cache_raw,
        "verified admission cache is not canonical",
    )
    metadata = _admission_seal_metadata(
        profile=profile,
        admission_path=admission_path,
        cache_path=cache_path,
        admission_raw=admission_raw,
        cache_raw=cache_raw,
        source_profiles_raw=source_profiles_raw,
        code_source_graph_raw=code_source_graph_raw,
    )
    mac = hmac.new(
        _admission_hmac_key(create=True),
        _admission_seal_message(
            metadata,
            admission_raw=admission_raw,
            cache_raw=cache_raw,
            source_profiles_raw=source_profiles_raw,
            code_source_graph_raw=code_source_graph_raw,
        ),
        hashlib.sha256,
    ).hexdigest()
    return _canonical({**metadata, "mac": mac})


def _publish_admission_seal(
    *,
    profile: str,
    admission_path: Path,
    cache_path: Path,
    admission_raw: bytes,
    cache_raw: bytes,
    record: Json,
    existing: bool,
) -> tuple[Path, bytes]:
    v2_package._require_path_components_no_symlink(
        admission_path.parent, "qualification admission parent"
    )
    parent_info = admission_path.parent.stat(follow_symlinks=False)
    _need(
        stat.S_ISDIR(parent_info.st_mode) and parent_info.st_uid == os.getuid(),
        "qualification admission parent owner differs",
    )
    if stat.S_IMODE(parent_info.st_mode) != 0o700:
        os.chmod(admission_path.parent, 0o700)
    _require_private_directory(admission_path.parent, "qualification admission parent")
    source_profiles_raw = _admission_source_profiles_raw(record)
    code_source_graph_raw = _admission_code_source_graph_raw()
    seal_raw = _admission_seal_raw(
        profile=profile,
        admission_path=admission_path,
        cache_path=cache_path,
        admission_raw=admission_raw,
        cache_raw=cache_raw,
        source_profiles_raw=source_profiles_raw,
        code_source_graph_raw=code_source_graph_raw,
    )
    seal_path = admission_path.parent / _ADMISSION_SEAL_FILENAME
    v2_package._require_path_components_no_symlink(seal_path, "admission seal")
    if existing:
        _require_private_record(seal_path, "admission seal")
        _need(_read(seal_path) == seal_raw, "retained admission seal differs")
    else:
        _write_exclusive(seal_path, seal_raw)
        _require_private_record(seal_path, "admission seal")
    return seal_path, seal_raw


def _verify_admission_seal(
    admission_path: Path, admission_raw: bytes, record: Json
) -> bytes:
    """Verify the fixed-root seal before reading any cached proof objects."""
    _require_private_directory(admission_path.parent, "qualification admission parent")
    _need(_canonical(record) == admission_raw, "package admission is not canonical")
    root = admission_path.parent / "package"
    cache_path = root / _VERIFIED_ADMISSION_RELATIVE_PATH
    v2_package._require_path_components_no_symlink(
        cache_path, "verified admission cache"
    )
    cache_raw = _read(cache_path)
    _need(
        _canonical(_json(cache_raw, "verified admission cache")) == cache_raw,
        "verified admission cache is not canonical",
    )
    source_profiles_raw = _admission_source_profiles_raw(record)
    code_source_graph_raw = _admission_code_source_graph_raw()
    expected_metadata = _admission_seal_metadata(
        profile=record["profile"],
        admission_path=admission_path,
        cache_path=cache_path,
        admission_raw=admission_raw,
        cache_raw=cache_raw,
        source_profiles_raw=source_profiles_raw,
        code_source_graph_raw=code_source_graph_raw,
    )
    seal_path = admission_path.parent / _ADMISSION_SEAL_FILENAME
    v2_package._require_path_components_no_symlink(seal_path, "admission seal")
    _require_private_record(seal_path, "admission seal")
    seal_raw = _read(seal_path)
    seal = _json(seal_raw, "admission seal")
    _need(
        set(seal) == {*expected_metadata, "mac"}
        and all(seal.get(key) == value for key, value in expected_metadata.items())
        and type(seal.get("mac")) is str
        and re.fullmatch(r"[0-9a-f]{64}", seal["mac"]) is not None,
        "admission seal metadata differs",
    )
    _need(_canonical(seal) == seal_raw, "admission seal is not canonical")
    expected_mac = hmac.new(
        _admission_hmac_key(),
        _admission_seal_message(
            expected_metadata,
            admission_raw=admission_raw,
            cache_raw=cache_raw,
            source_profiles_raw=source_profiles_raw,
            code_source_graph_raw=code_source_graph_raw,
        ),
        hashlib.sha256,
    ).hexdigest()
    assert isinstance(seal["mac"], str)
    _need(
        hmac.compare_digest(seal["mac"], expected_mac),
        "admission seal authentication failed",
    )
    return cache_raw


@dataclass(frozen=True)
class QualificationOutputAdmissionV2:
    """Frozen, statically authenticated bytes passed to the pure #214 parent."""

    profile: str
    disposition: str
    view: Json
    manifest: Json
    report: Json
    diagnostics: tuple[Json, ...]
    recovery_actions: tuple[Json, ...]
    blobs: Mapping[str, bytes]
    source_wavs: Mapping[str, bytes]
    source_proofs: Mapping[str, SourceProof]
    source_entries: list[Json]
    source_paths: Mapping[str, Path]
    package_root: Path
    admission_path: Path
    attestation_path: Path
    attestation_sha256: str
    original_document_path: Path
    original_dependencies_path: Path
    execution_document_path: Path
    execution_dependencies_path: Path
    raw_snapshots: Mapping[str, bytes]
    admission: Json
    view_raw: bytes
    manifest_raw: bytes
    report_raw: bytes
    _tracked_paths: Mapping[Path, tuple[int, int, int, int, int]] = field(repr=False)
    _tracked_hashes: Mapping[Path, str] = field(repr=False)
    _tracked_links: Mapping[Path, tuple[str, Path]] = field(repr=False)
    _proof_payloads: Mapping[tuple[str, str], tuple[Json, ...]] = field(repr=False)

    def assert_current(self) -> None:
        """Reject stale or replaced inputs before the controller issues authority."""
        for path, state in self._tracked_paths.items():
            try:
                current_state = _state(path)
            except OSError as error:
                raise QualificationPackageError(
                    f"admitted source path changed: {path.name}"
                ) from error
            _need(
                current_state == state, f"admitted source identity changed: {path.name}"
            )
            if path in self._tracked_links:
                link_text, target = self._tracked_links[path]
                _need(
                    path.is_symlink()
                    and os.readlink(path) == link_text
                    and path.resolve(strict=True) == target,
                    f"admitted source link changed: {path.name}",
                )
            else:
                _need(
                    not path.is_symlink(),
                    f"admitted source path became a link: {path.name}",
                )
        inventory, inventory_raw = _inventory(self.package_root)
        inventory_hashes = {
            self.package_root / row["path"]: row["sha256"] for row in inventory["files"]
        }
        for path, expected in self._tracked_hashes.items():
            observed = (
                inventory_hashes[path] if path in inventory_hashes else _hash_file(path)
            )
            _need(
                observed == expected,
                f"admitted source bytes changed: {path.name}",
            )
        _need(
            inventory_raw == _read(self.package_root / "package-inventory.json")
            and _sha(inventory_raw) == self.admission["packageInventorySha256"],
            "admitted package inventory changed",
        )
        _need(type(inventory["files"]) is list, "admitted package inventory is invalid")
        _need(
            self.admission_path.is_file() and not self.admission_path.is_symlink(),
            "admission file changed",
        )
        raw = _read(self.admission_path)
        _need(
            _json(raw, "package admission") == self.admission,
            "admission record changed",
        )

    def verify_source_payload(self, kind: str, receipt: bytes, expected: Json) -> None:
        """Authenticate only exact retained R16 producer receipts; never a callback."""
        _need(
            type(receipt) is bytes and type(expected) is dict,
            "bounded source proof required",
        )
        receipt_hash = _sha(receipt)
        candidates = self._proof_payloads.get((kind, receipt_hash), ())
        _need(bool(candidates), "source provenance is not the admitted receipt")
        if kind == "private_preparation":
            actual = next(
                (
                    item
                    for item in candidates
                    if set(expected) == set(item) | {"context"}
                    and {
                        key: value
                        for key, value in expected.items()
                        if key != "context"
                    }
                    == item
                ),
                None,
            )
            _need(
                actual is not None,
                "prepared provenance differs from the admitted receipt",
            )
            try:
                from .qualification_output_records_v2 import _context

                context = _context(expected["context"])
            except (KeyError, TypeError, ValueError) as error:
                raise QualificationPackageError(
                    "source proof context is invalid"
                ) from error
            _need(
                all(
                    context.get(field) == _sha(self.blobs[blob_key])
                    for field, blob_key in (
                        ("originalDocumentSha256", "originalDocumentSha256"),
                        ("originalDependenciesSha256", "originalDependenciesSha256"),
                        ("executionDocumentSha256", "executionDocumentSha256"),
                        ("executionDependenciesSha256", "executionDependenciesSha256"),
                        ("manifestSha256", "manifestSha256"),
                        ("reportSha256", "reportSha256"),
                        ("packageSha256", "packageSha256"),
                        ("preflightSha256", "preflightSha256"),
                        ("preparationSha256", "preparationSha256"),
                    )
                ),
                "source proof context does not bind the admitted package inputs",
            )
        else:
            _need(
                expected in candidates,
                "narration provenance differs from the admitted receipt",
            )

    def serialize_native_admission(self) -> tuple[Path, str]:
        """Return the immutable native handoff path and its raw digest."""
        self.assert_current()
        raw = _read(self.admission_path)
        return self.admission_path, _sha(raw)

    def native_package_ref(self) -> Json:
        path, digest = self.serialize_native_admission()
        return {
            "packageRoot": str(self.package_root),
            "attestationPath": str(self.attestation_path),
            "attestationSha256": self.attestation_sha256,
            "admissionPath": str(path),
            "admissionSha256": digest,
            "profile": self.profile,
        }


# Compatibility name used by the installed controller.
Admission = QualificationOutputAdmissionV2


def _verification_cache_raw(
    *,
    profile: str,
    package_root: Path,
    tracked_paths: Mapping[Path, tuple[int, int, int, int, int]],
    tracked_hashes: Mapping[Path, str],
    tracked_links: Mapping[Path, tuple[str, Path]],
    source_paths: Mapping[str, Path],
    source_proofs: Mapping[str, SourceProof],
    source_entries: list[Json],
    source_wavs: Mapping[str, bytes],
    proof_payloads: Mapping[tuple[str, str], tuple[Json, ...]],
) -> bytes:
    """Persist the verified projection needed for a cheap, currentness-only reopen.

    This envelope is discovered at a fixed wrapper path and is bound by the
    admission's package inventory plus the fixed-root HMAC sidecar. It contains
    no caller-selected path or executable; all source/tool identities are
    rechecked by ``assert_current``.
    """
    tracked = []
    for path in sorted(tracked_paths, key=lambda item: str(item)):
        if path.is_dir():
            continue
        tracked.append(
            {
                "path": str(path),
                "state": _cache_state(tracked_paths[path]),
                "sha256": tracked_hashes.get(path),
            }
        )
    links = [
        {"path": str(path), "linkText": link, "target": str(target)}
        for path, (link, target) in sorted(
            tracked_links.items(), key=lambda item: str(item[0])
        )
    ]
    source_rows = []
    for source_id, path in sorted(source_paths.items()):
        _need(
            path.is_relative_to(package_root),
            "verified source path must remain inside the package wrapper",
        )
        source_rows.append(
            {
                "sourceId": source_id,
                "relativePath": path.relative_to(package_root).as_posix(),
            }
        )
    proof_rows = []
    for source_id, proof in sorted(source_proofs.items()):
        refs: Json = {"sourceId": source_id}
        for proof_field in _VERIFICATION_PROOF_BYTE_FIELDS:
            field_name = {
                "originRecord": "origin_record",
                "originReceipt": "origin_receipt",
            }.get(proof_field, proof_field)
            raw = getattr(proof, field_name)
            refs[proof_field] = (
                _verification_blob_ref(
                    package_root,
                    raw,
                    ".bin",
                    f"source {source_id} {proof_field}",
                )
                if raw is not None
                else None
            )
        proof_rows.append(refs)
    payload_rows = [
        {
            "kind": kind,
            "receiptSha256": receipt_hash,
            "payloads": [
                _verification_blob_ref(
                    package_root,
                    _canonical(payload),
                    ".json",
                    f"proof payload {kind}/{receipt_hash}",
                )
                for payload in payloads
            ],
        }
        for (kind, receipt_hash), payloads in sorted(proof_payloads.items())
    ]
    return _canonical(
        {
            "schemaVersion": _VERIFIED_ADMISSION_SCHEMA,
            "profile": profile,
            "tracked": tracked,
            "links": links,
            "sourcePaths": source_rows,
            "sourceProofs": proof_rows,
            "sourceEntries": copy.deepcopy(source_entries),
            "sourceWavSha256": [
                {"sourceId": source_id, "sha256": _sha(raw)}
                for source_id, raw in sorted(source_wavs.items())
            ],
            "proofPayloads": payload_rows,
        }
    )


def _parse_verification_cache(
    raw: bytes, *, profile: str, package_root: Path
) -> tuple[
    dict[Path, tuple[int, int, int, int, int]],
    dict[Path, str],
    dict[Path, tuple[str, Path]],
    dict[str, Path],
    dict[str, SourceProof],
    list[Json],
    dict[str, str],
    dict[tuple[str, str], tuple[Json, ...]],
]:
    value = _json(raw, "verified admission")
    expected_keys = {
        "schemaVersion",
        "profile",
        "tracked",
        "links",
        "sourcePaths",
        "sourceProofs",
        "sourceEntries",
        "sourceWavSha256",
        "proofPayloads",
    }
    _need(
        set(value) == expected_keys
        and value["schemaVersion"] == _VERIFIED_ADMISSION_SCHEMA
        and value["profile"] == profile,
        "unsupported verified-admission envelope",
    )
    tracked_paths: dict[Path, tuple[int, int, int, int, int]] = {}
    tracked_hashes: dict[Path, str] = {}
    for candidate in _array(value["tracked"], "verified tracked paths"):
        row = _object(candidate, "verified tracked path")
        _need(
            set(row) == {"path", "state", "sha256"},
            "verified tracked path shape differs",
        )
        path = Path(_text(row["path"], "verified tracked path required"))
        _need(path.is_absolute() and path not in tracked_paths, "invalid tracked path")
        tracked_paths[path] = _parse_cache_state(row["state"])
        digest = row["sha256"]
        if digest is not None:
            _need(
                type(digest) is str
                and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
                "verified tracked hash is malformed",
            )
            assert isinstance(digest, str)
            tracked_hashes[path] = digest
    tracked_links: dict[Path, tuple[str, Path]] = {}
    for candidate in _array(value["links"], "verified tracked links"):
        row = _object(candidate, "verified tracked link")
        _need(
            set(row) == {"path", "linkText", "target"},
            "verified tracked link shape differs",
        )
        path = Path(_text(row["path"], "verified link path required"))
        target = Path(_text(row["target"], "verified link target required"))
        link_text = _text(row["linkText"], "verified link text required")
        _need(
            path.is_absolute()
            and target.is_absolute()
            and path in tracked_paths
            and path not in tracked_links,
            "invalid verified tracked link",
        )
        tracked_links[path] = (link_text, target)
    source_paths: dict[str, Path] = {}
    for candidate in _array(value["sourcePaths"], "verified source paths"):
        row = _object(candidate, "verified source path")
        _need(
            set(row) == {"sourceId", "relativePath"},
            "verified source path shape differs",
        )
        source_id = _text(row["sourceId"], "verified source id required")
        relative = _text(row["relativePath"], "verified source relative path required")
        path = package_root / relative
        _need(
            source_id not in source_paths
            and path.is_relative_to(package_root)
            and bool(relative)
            and "\\" not in relative
            and all(part not in {"", ".", ".."} for part in Path(relative).parts),
            "invalid verified source path",
        )
        source_paths[source_id] = path
    source_proofs: dict[str, SourceProof] = {}
    proof_fields = {
        "sourceId",
        "record",
        "receipt",
        "timing",
        "review",
        "originRecord",
        "originReceipt",
    }
    for candidate in _array(value["sourceProofs"], "verified source proofs"):
        row = _object(candidate, "verified source proof")
        _need(set(row) == proof_fields, "verified source proof shape differs")
        source_id = _text(row["sourceId"], "verified source id required")
        _need(source_id not in source_proofs, "duplicate verified source proof")
        fields = {
            key: (
                None
                if row[key] is None
                else _read_verification_blob(
                    package_root, row[key], ".bin", f"source {source_id} {key}"
                )
            )
            for key in _VERIFICATION_PROOF_BYTE_FIELDS[2:]
        }
        source_proofs[source_id] = SourceProof(
            _read_verification_blob(
                package_root, row["record"], ".bin", f"source {source_id} record"
            ),
            _read_verification_blob(
                package_root, row["receipt"], ".bin", f"source {source_id} receipt"
            ),
            timing=fields["timing"],
            review=fields["review"],
            origin_record=fields["originRecord"],
            origin_receipt=fields["originReceipt"],
        )
    source_entries = copy.deepcopy(
        _array(value["sourceEntries"], "verified source entries")
    )
    source_wavs: dict[str, str] = {}
    for candidate in _array(value["sourceWavSha256"], "verified source WAVs"):
        row = _object(candidate, "verified source WAV")
        _need(set(row) == {"sourceId", "sha256"}, "verified source WAV shape differs")
        source_id = _text(row["sourceId"], "verified source id required")
        digest = row["sha256"]
        _need(
            source_id in source_paths
            and source_id not in source_wavs
            and type(digest) is str
            and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            "verified source WAV hash is malformed",
        )
        assert isinstance(digest, str)
        source_wavs[source_id] = digest
    proof_payloads: dict[tuple[str, str], tuple[Json, ...]] = {}
    for candidate in _array(value["proofPayloads"], "verified proof payloads"):
        row = _object(candidate, "verified proof payload")
        _need(
            set(row) == {"kind", "receiptSha256", "payloads"},
            "verified proof payload shape differs",
        )
        kind = _text(row["kind"], "verified proof kind required")
        receipt_hash = _text(
            row["receiptSha256"], "verified proof receipt hash required"
        )
        _need(
            re.fullmatch(r"[0-9a-f]{64}", receipt_hash) is not None
            and (kind, receipt_hash) not in proof_payloads,
            "verified proof receipt hash is malformed",
        )
        payloads = []
        for reference in _array(row["payloads"], "verified proof payload rows"):
            payload_raw = _read_verification_blob(
                package_root,
                reference,
                ".json",
                f"proof payload {kind}/{receipt_hash}",
            )
            payload_value = _json(payload_raw, "verified proof payload")
            _need(
                _canonical(payload_value) == payload_raw,
                "verified proof payload is not canonical",
            )
            payloads.append(
                _object(payload_value, "verified proof payload object required")
            )
        proof_payloads[(kind, receipt_hash)] = tuple(payloads)
    return (
        tracked_paths,
        tracked_hashes,
        tracked_links,
        source_paths,
        source_proofs,
        source_entries,
        source_wavs,
        proof_payloads,
    )


def serialize_native_admission(
    admission: QualificationOutputAdmissionV2,
) -> tuple[Path, str]:
    _need(
        type(admission) is QualificationOutputAdmissionV2,
        "concrete package admission required",
    )
    return admission.serialize_native_admission()


@_admission_boundary
def admit_qualification_package_v2(
    output_root: Path,
    *,
    profile: str = R16_PROFILE,
    package_root: Path | None = None,
    preparation_paths: Mapping[str, Path] | None = None,
    narration_evidence_paths: Mapping[str, Mapping[str, Path]] | None = None,
) -> QualificationOutputAdmissionV2:
    """Admit a fixed qualification fixture or an unchanged verified public package.

    The profile is a closed enum selected by the caller.  R16 always loads the
    pinned private vector; Presenter uses its fixed RGBA fixture and current
    compiler. Ordinary admission delegates the public v2 gate unchanged.
    """
    _need(type(profile) is str and profile in _PROFILES, "unsupported package profile")
    _need(
        profile == MATRIX_PROFILE or preparation_paths is None,
        "published preparation paths are only accepted by the matrix profile",
    )
    _need(
        profile == MATRIX_PROFILE or narration_evidence_paths is None,
        "measured narration evidence is only accepted by the matrix profile",
    )
    _need(
        isinstance(output_root, Path) and output_root.is_absolute(),
        "absolute output root required",
    )
    v2_package._require_path_components_no_symlink(
        output_root, "qualification output root"
    )
    _need(
        not output_root.exists() and not output_root.is_symlink(),
        "output root must be new",
    )
    if profile == R16_PROFILE:
        return _admit_r16(output_root)
    if profile == PRESENTER_PROFILE:
        _need(package_root is None, "Presenter profile uses only its pinned fixture")
        return _admit_presenter(output_root)
    synthetic_root = package_root
    _need(
        synthetic_root is not None and isinstance(synthetic_root, Path),
        "verified synthetic package root required",
    )
    assert isinstance(synthetic_root, Path)
    return _admit_synthetic(
        output_root,
        synthetic_root,
        profile=profile,
        preparation_paths=preparation_paths,
        narration_evidence_paths=narration_evidence_paths,
    )


@_admission_boundary
def admit_qualification_revision_v2(
    output_root: Path,
    *,
    package_root: Path,
    preparation_paths: Mapping[str, Path],
    revised_preflight_path: Path,
    revised_preflight_sha256: str,
    narration_evidence_paths: Mapping[str, Mapping[str, Path]] | None = None,
) -> QualificationOutputAdmissionV2:
    """Admit a fresh public matrix build while retaining its pinned originals."""
    _need(
        isinstance(output_root, Path) and output_root.is_absolute(),
        "absolute qualification output root required",
    )
    v2_package._require_path_components_no_symlink(
        output_root, "qualification output root"
    )
    _need(
        not output_root.exists() and not output_root.is_symlink(),
        "output root must be new",
    )
    _need(
        isinstance(package_root, Path) and package_root.is_absolute(),
        "absolute revised public package root required",
    )
    _need(
        isinstance(preparation_paths, Mapping),
        "published matrix preparation paths required",
    )
    _need(
        isinstance(revised_preflight_path, Path)
        and revised_preflight_path.is_absolute()
        and type(revised_preflight_sha256) is str
        and re.fullmatch(r"[0-9a-f]{64}", revised_preflight_sha256) is not None,
        "revised preflight path and lowercase raw hash required",
    )
    v2_package._require_path_components_no_symlink(
        revised_preflight_path, "revised preflight"
    )

    # This verifier owns the decision/evidence chain.  The package lane only
    # consumes its current, file-pinned output and binds it to #177 bytes.
    from .qualification_output_proof_v2 import verify_revised_preflight_v2

    preflight = _object(
        verify_revised_preflight_v2(revised_preflight_path, revised_preflight_sha256),
        "verified revised preflight object required",
    )
    original_inputs = _object(
        preflight.get("originalInputs"), "revised original input pins required"
    )
    baseline_inputs = _object(
        preflight.get("baselineInputs"), "revised baseline input pins required"
    )
    execution_inputs = _object(
        preflight.get("executionInputs"), "revised execution input pins required"
    )
    original_document_path, original_document, _ = _read_revised_pin(
        original_inputs.get("document"), "original document"
    )
    original_dependencies_path, original_dependencies, _ = _read_revised_pin(
        original_inputs.get("dependencies"), "original dependencies"
    )
    _baseline_document_path, _baseline_document, _ = _read_revised_pin(
        baseline_inputs.get("document"), "baseline document"
    )
    _baseline_dependencies_path, baseline_dependencies_raw, _ = _read_revised_pin(
        baseline_inputs.get("dependencies"), "baseline dependencies"
    )
    execution_document = _read_revised_pin(
        execution_inputs.get("document"), "execution document"
    )[1]
    execution_dependencies = _read_revised_pin(
        execution_inputs.get("dependencies"), "execution dependencies"
    )[1]
    manifest_raw = _read_revised_pin(preflight.get("manifest"), "manifest")[1]
    report_raw = _read_revised_pin(preflight.get("report"), "report")[1]
    baseline_build_id = _object(
        _json(baseline_dependencies_raw, "baseline dependencies").get("build"),
        "baseline build identity required",
    ).get("buildId")
    execution_build_id = _object(
        _json(execution_dependencies, "execution dependencies").get("build"),
        "execution build identity required",
    ).get("buildId")
    _need(
        type(baseline_build_id) is str
        and type(execution_build_id) is str
        and baseline_build_id != execution_build_id,
        "revised execution build id must be fresh from the baseline",
    )

    verified = v2_package.verify_v2_package(package_root)
    build = package_root / "Builds" / verified.build_id
    package_bytes = {
        "document": _read(build / v2_package.DOCUMENT_FILENAME),
        "dependencies": _read(build / v2_package.DEPENDENCIES_FILENAME),
        "manifest": _read(build / v2_package.MANIFEST_FILENAME),
        "report": _read(build / v2_package.REPORT_FILENAME),
    }
    _need(
        package_bytes
        == {
            "document": execution_document,
            "dependencies": execution_dependencies,
            "manifest": manifest_raw,
            "report": report_raw,
        },
        "revised public package bytes differ from the verified preflight pins",
    )
    return _admit_synthetic(
        output_root,
        package_root,
        profile=MATRIX_PROFILE,
        preparation_paths=preparation_paths,
        narration_evidence_paths=narration_evidence_paths,
        revision_originals=(
            (original_document_path, original_document),
            (original_dependencies_path, original_dependencies),
        ),
        revision_execution_pins=package_bytes,
    )


def _parse_original_link(
    path: Path, expected_sha256: str, final_state: Json
) -> tuple[bytes, dict[Path, tuple[int, int, int, int, int]], dict[Path, str]]:
    _need(
        path.is_symlink(), f"approved original input must remain a symlink: {path.name}"
    )
    expected_target = (
        _PRIVATE
        / "issue-148/2026-10-11-r15-heroes-base-binding/attempt-01/candidate-inputs"
        / path.name
    )
    _need(
        path.resolve(strict=True) == expected_target,
        f"approved target changed: {path.name}",
    )
    link = path.lstat()
    target = expected_target.stat()
    recorded = final_state.get("regularFiles", {}).get(str(path))
    _need(
        type(recorded) is dict,
        "original link identity is missing from the retained delta",
    )
    identity = recorded.get("identity")
    _need(type(identity) is dict, "original target identity is missing")
    _need(
        identity.get("resolvedTarget") == str(expected_target)
        and identity.get("linkText") == os.readlink(path)
        and identity.get("path") == str(path)
        and identity.get("linkIdentity") == _file_identity(path)
        and identity.get("targetIdentity") == _file_identity(expected_target)
        and recorded.get("rawSha256") == f"sha256:{expected_sha256}",
        f"approved original link/target identity changed: {path.name}",
    )
    raw = _read(expected_target, maximum=16 * 1024 * 1024)
    _need(_sha(raw) == expected_sha256, f"original {path.name} raw hash differs")
    states = {
        path: (
            link.st_dev,
            link.st_ino,
            link.st_size,
            link.st_mtime_ns,
            link.st_ctime_ns,
        ),
        expected_target: (
            target.st_dev,
            target.st_ino,
            target.st_size,
            target.st_mtime_ns,
            target.st_ctime_ns,
        ),
    }
    hashes = {expected_target: expected_sha256}
    return raw, states, hashes


def _tokens(path: str) -> list[str | int]:
    result: list[str | int] = []
    for match in re.finditer(r"([^.[\]]+)|\[([0-9]+)\]", path):
        result.append(
            match.group(1) if match.group(1) is not None else int(match.group(2))
        )
    _need(
        len(result) > 0 and all(isinstance(x, (str, int)) for x in result),
        "malformed delta path",
    )
    return result


def _get_path(root: Json, path: str) -> Any:
    value: Any = root
    for token in _tokens(path.removeprefix("dependencies.")):
        if isinstance(value, dict):
            value = value[token]
        elif isinstance(value, list):
            _need(isinstance(token, int), "array delta path requires an index")
            assert isinstance(token, int)
            value = value[token]
        else:
            raise QualificationPackageError("delta path traverses a scalar")
    return value


def _set_path(root: Json, path: str, replacement: Any) -> None:
    tokens = _tokens(path.removeprefix("dependencies."))
    value: Any = root
    for token in tokens[:-1]:
        if isinstance(value, dict):
            value = value[token]
        elif isinstance(value, list):
            _need(isinstance(token, int), "array delta path requires an index")
            assert isinstance(token, int)
            value = value[token]
        else:
            raise QualificationPackageError("delta path traverses a scalar")
    if isinstance(value, dict):
        value[tokens[-1]] = replacement
    elif isinstance(value, list):
        _need(isinstance(tokens[-1], int), "array delta path requires an index")
        assert isinstance(tokens[-1], int)
        value[tokens[-1]] = replacement
    else:
        raise QualificationPackageError("delta path parent is a scalar")


def _authenticate_dependency_delta(
    original: Json, execution: Json, delta: Json, acceptance: bytes
) -> None:
    _need(
        _sha(acceptance) == _APPROVAL_SHA256,
        "producer host-preparation acceptance pin differs",
    )
    accepted = _json(acceptance, "producer acceptance")
    _need(
        accepted.get("accepted") is True
        and accepted.get("boundedHostPreparationAuthorized") is True
        and accepted.get("noCodeNativeInstallOperatorProviderMergeOrNewTaskAuthority")
        is True,
        "producer acceptance does not authorize this bounded preparation",
    )
    _need(
        delta.get("changedFieldCount") == 72
        and delta.get("originalDependenciesRawSha256")
        == f"sha256:{_EXPECTED_ORIGINAL_DEPENDENCIES}"
        and delta.get("executionDependenciesRawSha256")
        == f"sha256:{_EXPECTED_EXECUTION_DEPENDENCIES}"
        and delta.get("originalScriptDocumentRawSha256")
        == f"sha256:{_EXPECTED_ORIGINAL_DOCUMENT}"
        and delta.get("preparedMediaReplacedIndices") == [0, 1, 2, 5]
        and delta.get("occurrenceRowsChanged") == [5, 2, 3, 4]
        and delta.get("unchangedStillBindingCount") == 2,
        "retained dependency delta is not the approved four-binding/six-field change",
    )
    public_bindings = _PREPARED_Q.keys()
    media = execution.get("preparedMedia")
    original_media = original.get("preparedMedia")
    _need(
        type(media) is list
        and type(original_media) is list
        and len(media) == len(original_media) == 6,
        "six dependency preparation rows required",
    )
    media_rows = _array(media, "six dependency preparation rows required")
    original_media_rows = _array(
        original_media, "six original dependency preparation rows required"
    )
    _need(
        {row.get("requirementKey") for row in media_rows if type(row) is dict}
        - {
            row.get("requirementKey")
            for row in original_media_rows
            if type(row) is dict
        }
        == set(public_bindings),
        "execution dependencies do not contain exactly the four approved "
        "public bindings",
    )
    changed = delta.get("fieldByFieldChanges")
    _need(
        type(changed) is list and len(changed) == 72,
        "complete exact dependency change inventory required",
    )
    changed_rows = _array(
        changed, "complete exact dependency change inventory required"
    )
    expected_occurrence_paths = {
        f"dependencies.occurrenceResolutions[{index}].{field}"
        for index in (2, 3, 4, 5)
        for field in _OCCURRENCE_FIELDS
    }
    seen_prepared: dict[int, set[str]] = {}
    seen_occurrences: dict[int, set[str]] = {}
    reversed_execution = copy.deepcopy(execution)
    for candidate in changed_rows:
        row = _object(candidate, "closed delta change row required")
        _need(
            set(row) == {"authorization", "execution", "original", "path"},
            "closed delta change row required",
        )
        path = _text(row["path"], "delta path must be text")
        current = _get_path(execution, path)
        _need(
            current == row["execution"] and current != row["original"],
            "delta row does not match execution bytes",
        )
        if path.startswith("dependencies.preparedMedia["):
            match = re.fullmatch(r"dependencies\.preparedMedia\[([0-9]+)\]\.(.+)", path)
            _need(match is not None, "unapproved preparedMedia delta path")
            assert match is not None
            index, suffix = int(match.group(1)), match.group(2)
            _need(
                index in {0, 1, 2, 5} and suffix in _PREPARED_FIELDS,
                "unapproved preparedMedia field",
            )
            _need(
                row["authorization"]
                == "one of four actual public #174 binding replacements",
                "preparedMedia field lacks the approved R2 authority",
            )
            seen_prepared.setdefault(index, set()).add(suffix)
        elif path.startswith("dependencies.occurrenceResolutions["):
            match = re.fullmatch(
                r"dependencies\.occurrenceResolutions\[([0-9]+)\]\.(.+)", path
            )
            _need(match is not None, "unapproved occurrence delta path")
            assert match is not None
            index, suffix = int(match.group(1)), match.group(2)
            _need(
                index in {2, 3, 4, 5} and suffix in _OCCURRENCE_FIELDS,
                "unapproved occurrence field",
            )
            _need(
                row["authorization"] == "CN-209-P1 r2 occurrence field allowlist",
                "occurrence field lacks the exact R2 allowlist",
            )
            seen_occurrences.setdefault(index, set()).add(suffix)
        else:
            _need(False, "dependency delta changed an unapproved section")
        _set_path(reversed_execution, path, row["original"])
    _need(
        set(seen_prepared) == {0, 1, 2, 5}
        and all(seen_prepared[index] == _PREPARED_FIELDS for index in (0, 1, 2, 5)),
        "preparedMedia replacement fields are incomplete or extra",
    )
    _need(
        set(seen_occurrences) == {2, 3, 4, 5}
        and all(seen_occurrences[index] == _OCCURRENCE_FIELDS for index in (2, 3, 4, 5))
        and set(delta.get("allowedOccurrencePaths", [])) == expected_occurrence_paths,
        "occurrence replacement fields are incomplete or extra",
    )
    _need(
        reversed_execution == original,
        "reversing the approved delta does not recover original dependencies",
    )
    _need(
        {
            row["requirementKey"]
            for row in media_rows
            if row["requirementKey"] in public_bindings
        }
        == set(public_bindings),
        "public binding inventory differs",
    )


def _canonical_r16_report(
    document: Json,
    dependencies: Json,
    manifest: Json,
    report: Json,
    compiler_result: Json,
) -> tuple[tuple[Json, ...], tuple[Json, ...]]:
    result = _object(
        compiler_result.get("result"), "canonical compiler result required"
    )
    compiler_report = _object(
        result.get("report"), "canonical compiler report required"
    )
    _need(
        result.get("manifest") == manifest and compiler_report == report,
        "compiler vectors differ from retained manifest/report",
    )
    diagnostics = _array(
        report.get("diagnostics"), "R16 requires exactly three Presenter warnings"
    )
    _need(
        diagnostics == compiler_report.get("diagnostics"),
        "retained diagnostics are not canonical compiler output",
    )
    recoveries = _array(
        report.get("recoveryActions"), "R16 requires exactly one Presenter recovery"
    )
    _need(
        type(diagnostics) is list and len(diagnostics) == 3,
        "R16 requires exactly three Presenter warnings",
    )
    _need(
        type(recoveries) is list and len(recoveries) == 1,
        "R16 requires exactly one Presenter recovery",
    )
    _need(
        all(
            type(row) is dict
            and row.get("code") == "TEMPORARY_PRESENTER_STILL"
            and row.get("severity") == "warning"
            and row.get("entity", {}).get("kind") == "slot"
            and row.get("entity", {}).get("path") == "presenterStill"
            and row.get("recoveryActionKinds") == ["REPLACE_TEMPORARY_PRESENTER"]
            for row in diagnostics
        ),
        "R16 report contains an extra or non-allowlisted diagnostic",
    )
    ids = [row["entity"]["id"] for row in diagnostics]
    _need(len(set(ids)) == 3, "Presenter warning slots must be distinct")
    _need(
        recoveries[0]
        == {
            "documentId": document["id"],
            "instruction": (
                "Replace the temporary still with an accepted presenter source "
                "when available."
            ),
            "kind": "REPLACE_TEMPORARY_PRESENTER",
            "slotId": ids[0],
        },
        "R16 recovery action differs from the retained canonical report",
    )
    summary = _object(report.get("summary", {}), "R16 report summary must be an object")
    manual_items_value = report.get("manualCompletionItems")
    _need(
        report.get("status") == "ready"
        and summary.get("diagnosticCount") == 3
        and summary.get("recoveryActionCount") == 1
        and type(manual_items_value) is list
        and len(manual_items_value) > 0,
        "R16 report does not exactly retain the three unqualified Presenter "
        "completions",
    )
    manual_items = _array(
        manual_items_value,
        "R16 report does not exactly retain the three unqualified Presenter "
        "completions",
    )
    _need(
        [row.get("entity", {}).get("id") for row in manual_items] == ids,
        "R16 report manual-completion locations differ",
    )
    defaults = _object(
        dependencies.get("authoringDefaults"),
        "R16 dependency default mismatch changed",
    )
    _need(
        defaults.get("presenterStill") is None,
        "R16 dependency default mismatch changed",
    )
    settings = _object(
        document.get("scriptSettings", {}), "script settings must be an object"
    )
    override = settings.get("presenterStillOverride")
    generic = _json(_GENERIC_TORSO.read_bytes(), "generic torso source")
    inherited = defaults.get("presenterStill")
    effective = (
        override
        if override is not None
        else inherited
        if inherited is not None
        else generic
    )
    manifest_defaults = _object(
        manifest.get("authoringDefaults", {}),
        "manifest authoring defaults must be an object",
    )
    _need(
        manifest_defaults.get("presenterStill") == effective,
        "effective Presenter still is not independently derived from frozen "
        "document defaults",
    )
    manifest_events = _array(
        manifest.get("events", []), "manifest events must be an array"
    )
    _need(
        any(
            row.get("pictureTreatment", {}).get("kind") == "still"
            or row.get("pictureTreatment", {}).get("kind") == "still_frame"
            for row in manifest_events
        ),
        "R16 temporary Presenter picture is not visibly retained",
    )
    return tuple(copy.deepcopy(diagnostics)), tuple(copy.deepcopy(recoveries))


def _validate_r16_duration(manifest: Json) -> None:
    """Reject over-bound programmes before compiler/media verification work."""
    timeline = _object(manifest.get("timeline"), "R16 timeline is required")
    duration = timeline.get("durationFrames")
    _need(
        type(duration) is int and 1 <= duration <= _MAX_R16_DURATION_FRAMES,
        f"R16 durationFrames exceeds {_MAX_R16_DURATION_FRAMES}-frame bound",
    )


def _pin_r16_vector(raw: bytes, expected: str, label: str) -> None:
    _need(_sha(raw) == expected, f"R16 {label} raw pin differs")


def _locators(
    path_value: object,
    label: str,
    *,
    tracked_states: dict[Path, tuple[int, int, int, int, int]] | None = None,
    tracked_links: dict[Path, tuple[str, Path]] | None = None,
) -> Path:
    locator = _text(path_value, f"{label} locator required")
    _need(bool(locator), f"{label} locator required")
    parsed = urlparse(locator)
    if parsed.scheme == "file":
        _need(
            parsed.netloc in {"", "localhost"}
            and not parsed.query
            and not parsed.fragment,
            f"local {label} locator required",
        )
        path = Path(unquote(parsed.path))
    else:
        _need(
            not parsed.scheme and not locator.startswith("/") and "\\" not in locator,
            f"unsafe {label} locator",
        )
        path = _CANDIDATE / locator
    _need(path.exists(), f"{label} source is missing")
    resolved = path.resolve(strict=True)
    _need(
        resolved.is_file() and not resolved.is_symlink(),
        f"{label} source is not a regular file",
    )
    if path.is_symlink():
        _need(
            tracked_states is not None and tracked_links is not None,
            "linked source tracking is required",
        )
        assert tracked_states is not None and tracked_links is not None
        tracked_states[path] = _state(path)
        tracked_links[path] = (os.readlink(path), resolved)
    return resolved


def _r12_still_evidence() -> tuple[bytes, Json]:
    path = _R12 / "Receipts/r12-prepared-media-binding-evidence.json"
    raw = _read(path, maximum=4 * 1024 * 1024)
    _need(
        _sha(raw) == _R12_STILLS_SHA256,
        "retained R12 still-preparation evidence changed",
    )
    evidence = _json(raw, "retained R12 still-preparation evidence")
    _need(
        evidence.get("schemaVersion") == _R12_STILLS_SCHEMA
        and evidence.get("acceptedImplementation") == _R12_IMPLEMENTATION
        and evidence.get("noDeliveryOrProviderQualificationClaim") is True
        and evidence.get("noP5Claim") is True
        and type(evidence.get("candidates")) is list
        and len(evidence["candidates"]) == 2,
        "retained R12 still evidence is incomplete",
    )
    return raw, evidence


def _r12_delivered_path(locator: str) -> Path:
    parsed = urlparse(locator)
    if parsed.scheme == "file":
        _need(
            parsed.netloc in {"", "localhost"}
            and not parsed.query
            and not parsed.fragment,
            "R12 output locator must remain local",
        )
        path = Path(unquote(parsed.path))
    else:
        _need(
            not parsed.scheme
            and locator.startswith("Media/")
            and ".." not in Path(locator).parts
            and "\\" not in locator,
            "unsafe R12 output locator",
        )
        path = _R12 / "candidate-inputs" / locator
    _need(
        path.is_absolute() and path.resolve(strict=True).is_relative_to(_R12.resolve()),
        "R12 output is outside its retained root",
    )
    return path


def _r16_media_paths(
    manifest: Json,
    prepared: Mapping[str, v2_package._Preparation],
    prepared_sidecars: Mapping[str, Path],
) -> tuple[
    dict[str, Path],
    dict[Path, tuple[int, int, int, int, int]],
    dict[Path, str],
    dict[Path, tuple[str, Path]],
]:
    media: dict[str, Path] = {}
    tracked_states: dict[Path, tuple[int, int, int, int, int]] = {}
    tracked_hashes: dict[Path, str] = {}
    tracked_links: dict[Path, tuple[str, Path]] = {}
    _, still_evidence = _r12_still_evidence()
    still_candidates = _array(
        still_evidence.get("candidates"), "R12 still evidence candidates required"
    )
    stills = {row["requirement"]["requirementKey"]: row for row in still_candidates}
    for source in manifest["sources"]:
        sid = source["id"]
        if "narrationAudio" in source:
            audio = source["narrationAudio"]
            path = _locators(
                audio.get("locator"),
                f"narration source {sid}",
                tracked_states=tracked_states,
                tracked_links=tracked_links,
            )
            expected = audio["audioHash"].removeprefix("sha256:")
            _need(
                _hash_file(path) == expected, f"narration source {sid} WAV hash differs"
            )
            media[f"source:{sid}"] = path
            tracked_states[path] = _state(path)
            tracked_hashes[path] = expected
            continue
        key = source["preparationRequirementKey"]
        if key in prepared:
            binding = prepared[key].record["binding"]
            _need(
                binding["mode"] == "verified_reuse",
                "R16 public source must retain its approved verified-reuse binding",
            )
            delivered = _locators(
                binding["artifactLocator"],
                f"public source {sid}",
                tracked_states=tracked_states,
                tracked_links=tracked_links,
            )
            original = delivered
        else:
            _need(key in stills, "R16 visual source lacks an authenticated preparation")
            candidate = stills[key]
            original = Path(candidate["originalSource"]["path"])
            delivered = _r12_delivered_path(candidate["delivered"]["artifactLocator"])
            for path in (original, delivered):
                if path.is_symlink():
                    tracked_states[path] = _state(path)
                    tracked_links[path] = (os.readlink(path), path.resolve(strict=True))
            original, delivered = (
                original.resolve(strict=True),
                delivered.resolve(strict=True),
            )
        _need(
            _hash_file(delivered) == source["deliveredHash"].removeprefix("sha256:"),
            f"delivered source {sid} hash differs",
        )
        media[f"source:{sid}"] = delivered
        _need(
            _hash_file(original) == source["originalHash"].removeprefix("sha256:"),
            f"original source {sid} hash differs",
        )
        media[f"original:{sid}"] = original
        for path, digest in (
            (delivered, source["deliveredHash"].removeprefix("sha256:")),
            (original, source["originalHash"].removeprefix("sha256:")),
        ):
            tracked_states[path] = _state(path)
            tracked_hashes[path] = digest
    events = {row["eventId"]: row for row in manifest["events"]}
    by_binding_hash = {
        v2_package._compiler_hash(item.record["binding"]): key
        for key, item in prepared.items()
    }
    for event in events.values():
        kind = event["kind"]
        event_id = event["eventId"]
        if kind == "placeholder":
            reference = event["pictureTreatment"].get("reference", {})
            locator = reference.get("projectRelativeLocator") or reference.get(
                "locator"
            )
            path = _locators(
                locator,
                f"placeholder {event_id}",
                tracked_states=tracked_states,
                tracked_links=tracked_links,
            )
            expected = reference["contentHash"].removeprefix("sha256:")
        elif kind == "source_audio":
            requirement = by_binding_hash.get(event.get("preparationBindingHash"))
            _need(
                requirement is not None and requirement in prepared_sidecars,
                f"source audio event {event_id} lacks its admitted #174 sidecar",
            )
            assert requirement is not None
            path = prepared_sidecars[requirement]
            expected = (
                prepared[requirement]
                .record["audio"]["contentHash"]
                .removeprefix("sha256:")
            )
        else:
            continue
        _need(_hash_file(path) == expected, f"event {event_id} media hash differs")
        media[f"event:{event_id}"] = path
        tracked_states[path] = _state(path)
        tracked_hashes[path] = expected
    return media, tracked_states, tracked_hashes, tracked_links


def _verify_wav(
    raw: bytes, expected_hash: str, audio: Json, label: str
) -> tuple[int, int, bytes]:
    _need(
        len(raw) <= _MAX_WAV and _sha(raw) == expected_hash.removeprefix("sha256:"),
        f"{label} WAV content hash differs",
    )
    try:
        with wave.open(io.BytesIO(raw), "rb") as stream:
            rate, channels, width, frames, compression = (
                stream.getframerate(),
                stream.getnchannels(),
                stream.getsampwidth(),
                stream.getnframes(),
                stream.getcomptype(),
            )
            pcm = stream.readframes(frames + 1)
    except (wave.Error, EOFError) as error:
        raise QualificationPackageError(f"{label} is not a valid PCM WAV") from error
    _need(
        (rate, channels, width, frames, compression)
        == (48000, audio["channels"], 3, audio["decodedSamples"], "NONE")
        and len(pcm) == frames * channels * width,
        f"{label} PCM extent/profile differs from its #174 receipt",
    )
    decoded = b"".join(
        struct.pack(
            "<i",
            int.from_bytes(pcm[index : index + 3], "little", signed=True),
        )
        for index in range(0, len(pcm), 3)
    )
    return frames, channels, decoded


def _compiler_bytes(document_path: Path, dependency_path: Path) -> bytes:
    _need(
        _NODE.is_file() and not _NODE.is_symlink() and bool(_hash_file(_NODE)),
        "pinned Node 24.19 runtime is unavailable",
    )
    version = subprocess.run(
        [str(_NODE), "--version"],
        capture_output=True,
        timeout=5,
        check=False,
        env={"LANG": "C", "LC_ALL": "C", "PATH": str(_NODE.parent)},
    )
    _need(
        version.returncode == 0 and version.stdout.strip() == b"v24.19.0",
        "Node 24.19.0 is required for canonical compile",
    )
    _need(
        _COMPILER.is_file() and _GENERIC_TORSO.is_file(),
        "locked compiler sources are unavailable",
    )
    result = subprocess.run(
        [str(_NODE), str(_COMPILER), str(document_path), str(dependency_path)],
        capture_output=True,
        timeout=45,
        check=False,
        env={"LANG": "C", "LC_ALL": "C", "PATH": str(_NODE.parent)},
    )
    _need(
        result.returncode == 0 and not result.stderr,
        "locked compiler refused the retained execution inputs",
    )
    return result.stdout


def _locked_compiler(
    document_path: Path, dependency_path: Path, expected_one: bytes, expected_two: bytes
) -> Json:
    raw = _compiler_bytes(document_path, dependency_path)
    _need(
        raw == expected_one == expected_two,
        "recomputed compiler bytes differ from either retained exact run",
    )
    return _json(raw, "canonical issue-190 compiler envelope")


def _run_pinned_ffprobe(path: Path) -> Json:
    _need(
        _FFPROBE.is_file() and not _FFPROBE.is_symlink(),
        "pinned ffprobe is unavailable",
    )
    _need(_hash_file(_FFPROBE) == _FFPROBE_SHA256, "pinned ffprobe executable changed")
    result = subprocess.run(
        [str(_FFPROBE), "-v", "error", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        timeout=30,
        check=False,
        env={"LANG": "C", "LC_ALL": "C", "PATH": str(_FFPROBE.parent)},
    )
    _need(
        result.returncode == 0 and not result.stderr,
        f"pinned ffprobe refused {path.name}",
    )
    return _json(result.stdout, "pinned ffprobe output")


def _run_pinned_frame_probe(path: Path) -> Json:
    _need(
        _FFPROBE.is_file() and _hash_file(_FFPROBE) == _FFPROBE_SHA256,
        "pinned ffprobe executable changed",
    )
    result = subprocess.run(
        [
            str(_FFPROBE),
            "-v",
            "error",
            "-count_frames",
            "-show_streams",
            "-show_frames",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        timeout=120,
        check=False,
        env={"LANG": "C", "LC_ALL": "C", "PATH": str(_FFPROBE.parent)},
    )
    _need(
        result.returncode == 0 and not result.stderr,
        "pinned ffprobe could not verify retained still probe",
    )
    probe = _json(result.stdout, "pinned full frame probe")
    return probe


def _probe_content(probe: Json) -> Json:
    content = copy.deepcopy(probe)
    content.get("format", {}).pop("filename", None)
    return content


def _verify_public_receipt(
    requirement_key: str,
    receipt_path: Path,
    tracked_states: dict[Path, tuple[int, int, int, int, int]],
    tracked_hashes: dict[Path, str],
    *,
    matrix: bool = False,
) -> tuple[Json, bytes, Path | None, bytes, bytes]:
    from .narration.models import identity_hash

    key_hex = requirement_key.removeprefix("sha256:")
    _need(
        re.fullmatch(r"[0-9a-f]{64}", key_hex) is not None,
        "public preparation key is malformed",
    )
    expected_dir = receipt_path.parent if matrix else _PREPARED_ROOT / key_hex
    if matrix:
        _need(
            receipt_path.is_absolute() and ".." not in receipt_path.parts,
            "canonical matrix published receipt path required",
        )
        v2_package._require_path_components_no_symlink(receipt_path, "matrix receipt")
        _need(
            receipt_path.is_relative_to(MATRIX_PREPARATION_ROOT)
            and expected_dir.parent.name == "published"
            and receipt_path.name == "receipt.json",
            "matrix receipt is outside its approved published root",
        )
    _need(expected_dir.name == key_hex, "published preparation directory differs")
    _need(
        receipt_path == expected_dir / "receipt.json",
        "preparation receipt path differs from the approved published tree",
    )
    for path in (
        receipt_path,
        expected_dir / "receipt-checksum.json",
        expected_dir / "request.json",
    ):
        _need(
            path.is_file() and not path.is_symlink(),
            f"public preparation file is unavailable: {path.name}",
        )
        tracked_states[path] = _state(path)
    raw = _read(receipt_path, maximum=8 * 1024 * 1024)
    checksum_raw = _read(expected_dir / "receipt-checksum.json")
    checksum = _json(checksum_raw, "public preparation checksum")
    _need(
        set(checksum) == {"receiptHash"}
        and checksum["receiptHash"] == "sha256:" + _sha(raw),
        "public preparation checksum does not bind its receipt bytes",
    )
    record = _json(raw, "public preparation receipt")
    request_raw = _read(expected_dir / "request.json")
    request = _json(request_raw, "public preparation request")
    record_binding = _object(
        record.get("binding"), "public preparation has no approved binding"
    )
    request_inputs = request.get("inputs")
    _need(
        set(request) == {"authorizationReference", "inputs", "requirementKey"}
        and request_inputs == record.get("inputs")
        and request.get("requirementKey") == requirement_key
        and record.get("requirementKey") == requirement_key
        and request.get("authorizationReference")
        == record_binding.get("authorizationReference"),
        "public preparation request/receipt identity differs",
    )
    request_inputs_object = _object(
        request_inputs, "public preparation inputs must be an object"
    )
    _need(
        requirement_key == identity_hash(request_inputs_object)
        and record.get("recordVersion") == "authoring-media-preparation/v1",
        "public preparation identity differs",
    )
    if matrix and record.get("audio") is None:
        _need(
            request_inputs_object.get("audioStreamIndex") is None
            and record_binding["timeMapping"]["sourceFrameMap"][
                "sourceAudioStreamMappings"
            ]
            == [],
            "silent preparation retains an audio stream mapping",
        )
        for path, digest in (
            (receipt_path, _sha(raw)),
            (expected_dir / "receipt-checksum.json", _sha(checksum_raw)),
            (expected_dir / "request.json", _sha(request_raw)),
        ):
            tracked_hashes[path] = digest
        return record, raw, None, b"", b""
    audio_path = expected_dir / "audio.wav"
    _need(
        audio_path.is_file() and not audio_path.is_symlink(),
        "public preparation file is unavailable: audio.wav",
    )
    tracked_states[audio_path] = _state(audio_path)
    audio_raw = _read(audio_path, maximum=_MAX_WAV)
    audio_record = _object(
        record.get("audio"), "public preparation has no actual audio receipt"
    )
    content_hash = _text(
        audio_record.get("contentHash"), "public preparation audio hash required"
    )
    frames, channels, decoded = _verify_wav(
        audio_raw,
        content_hash,
        audio_record,
        f"public preparation {key_hex[:8]}",
    )
    probe = _object(audio_record.get("probe"), "public preparation probe required")
    _need(
        frames == audio_record["decodedSamples"]
        and channels == audio_record["channels"]
        and _run_pinned_ffprobe(audio_path) == probe,
        "public preparation WAV, packed probe or decoded extent differs",
    )
    resampled_first = audio_record.get("resampledFirstSample")
    source_first = audio_record.get("sourceFirstSample")
    source_exclusive = audio_record.get("sourceExclusiveSample")
    resampled_exclusive = audio_record.get("resampledExclusiveSample")
    _need(
        type(resampled_first) is int
        and type(source_first) is int
        and type(source_exclusive) is int
        and type(resampled_exclusive) is int
        and (matrix or resampled_first == _PREPARED_Q[requirement_key])
        and source_first >= 0
        and source_exclusive > source_first
        and resampled_exclusive == resampled_first + frames,
        "public preparation q/sample coordinates differ from the retained R16 vector",
    )
    assert type(resampled_first) is int
    assert type(source_first) is int
    assert type(source_exclusive) is int
    assert type(resampled_exclusive) is int
    _need(
        requirement_key == identity_hash(request_inputs_object)
        and record.get("recordVersion") == "authoring-media-preparation/v1"
        and audio_record.get("probeHash") == identity_hash(probe),
        "public preparation identity or audio probe hash differs",
    )
    for path, digest in (
        (receipt_path, _sha(raw)),
        (expected_dir / "receipt-checksum.json", _sha(checksum_raw)),
        (expected_dir / "request.json", _sha(request_raw)),
        (audio_path, _sha(audio_raw)),
    ):
        tracked_hashes[path] = digest
    return record, raw, audio_path, audio_raw, decoded


def _validate_scoped_r16_inputs(
    document: Json, dependencies: Json, manifest: Json, report: Json
) -> None:
    """Validate actual objects; exact compiler reproduction supplies semantics.

    The public all-ready validator deliberately refuses this profile. Its
    inputs are never normalized to manufacture a public-package success.
    """
    for value, schema in (
        (document, "script-document-v2"),
        (dependencies, "compiler-dependencies-v2"),
        (manifest, "timeline-manifest-v2"),
        (report, "build-report-v2"),
    ):
        v2_package._walk_rationals(value)
        v2_package._validate_schema(value, schema, schema)
    _need(
        report["dependenciesHash"] == _compiler_json_hash(dependencies),
        "R16 dependency identity differs",
    )
    _need(
        report["manifest"]["contentHash"] == _compiler_json_hash(manifest),
        "R16 manifest identity differs",
    )


def _run_ffmpeg_raw(path: Path, *, still: bool) -> bytes:
    _need(
        _FFMPEG.is_file() and not _FFMPEG.is_symlink(), "pinned ffmpeg is unavailable"
    )
    _need(_hash_file(_FFMPEG) == _FFMPEG_SHA256, "pinned ffmpeg executable changed")
    command = [str(_FFMPEG), "-v", "error", "-nostdin", "-i", str(path)]
    if still:
        command += ["-frames:v", "1"]
    command += ["-f", "rawvideo", "-pix_fmt", "rgba", "-"]
    result = subprocess.run(
        command,
        capture_output=True,
        timeout=120,
        check=False,
        env={"LANG": "C", "LC_ALL": "C", "PATH": str(_FFMPEG.parent)},
    )
    _need(
        result.returncode == 0 and not result.stderr,
        "pinned ffmpeg could not verify approved still pixels",
    )
    return result.stdout


def _authenticate_r12_stills(
    dependencies: Json,
    tracked_states: dict[Path, tuple[int, int, int, int, int]],
    tracked_hashes: dict[Path, str],
) -> tuple[bytes, Json]:
    raw, evidence = _r12_still_evidence()
    tracked_states[_R12 / "Receipts/r12-prepared-media-binding-evidence.json"] = _state(
        _R12 / "Receipts/r12-prepared-media-binding-evidence.json"
    )
    tracked_hashes[_R12 / "Receipts/r12-prepared-media-binding-evidence.json"] = (
        _R12_STILLS_SHA256
    )
    rows = dependencies.get("preparedMedia")
    _need(
        type(rows) is list and len(rows) == 6,
        "exact six R16 dependency preparations required",
    )
    prepared_rows = _array(rows, "exact six R16 dependency preparations required")
    by_key = {
        row.get("requirementKey"): row for row in prepared_rows if type(row) is dict
    }
    expected_keys = {
        "r12-png-still-cfr:b08c8abb-83d1-5711-9d85-e2d2b89878a9",
        "r12-png-still-cfr:60202b61-cf36-5bbb-829c-0341b3ffeb7d",
    }
    _need(
        expected_keys <= by_key.keys(), "R16 unchanged R12 still bindings are missing"
    )
    still_candidates = _array(
        evidence.get("candidates"), "R12 still evidence candidates required"
    )
    for candidate_value in still_candidates:
        candidate = _object(candidate_value, "R12 still evidence candidate required")
        requirement = candidate["requirement"]
        key = requirement["requirementKey"]
        binding_value = by_key.get(key)
        _need(
            type(binding_value) is dict,
            "R12 still candidate does not map to its exact dependency row",
        )
        binding = _object(
            binding_value,
            "R12 still candidate does not map to its exact dependency row",
        )
        original = candidate["originalSource"]
        delivered = candidate["delivered"]
        derivation = candidate["derivation"]
        mapping = candidate["logicalMapping"]
        _need(
            candidate["owner"].get("kind") == "primary_slot"
            and requirement.get("occurrenceKey")
            and binding.get("mode") == "derived_cfr"
            and binding.get("requirementKey") == key
            and binding.get("originalSource", {}).get("contentHash")
            == original.get("contentHash")
            and binding.get("originalSource", {}).get("probeHash")
            == original.get("originalProbeHash")
            and binding.get("verification", {}).get("deliveredHash")
            == delivered.get("contentHash")
            and binding.get("verification", {}).get("probeHash")
            == delivered.get("outputProbeHash")
            and binding.get("derivation") == derivation
            and binding.get("timeMapping") == mapping,
            "R12 derived still source/output binding differs from frozen dependencies",
        )
        source_path = Path(original["path"]).resolve(strict=True)
        output_path = _r12_delivered_path(delivered["artifactLocator"]).resolve(
            strict=True
        )
        for path, digest in (
            (source_path, original["contentHash"].removeprefix("sha256:")),
            (output_path, delivered["contentHash"].removeprefix("sha256:")),
        ):
            _need(
                _hash_file(path) == digest,
                "R12 still source/output bytes differ from accepted evidence",
            )
            tracked_states[path] = _state(path)
            tracked_hashes[path] = digest
        source_rgba = _run_ffmpeg_raw(source_path, still=True)
        output_rgba = _run_ffmpeg_raw(output_path, still=True)
        _need(
            len(source_rgba) == delivered.get("decodedRgbaBytes")
            and "sha256:" + _sha(source_rgba)
            == original.get(
                "decodedRgbaPixelHash", delivered.get("originalDecodedRgbaPixelHash")
            )
            and len(output_rgba) == delivered.get("decodedRgbaBytes")
            and "sha256:" + _sha(output_rgba) == delivered.get("decodedRgbaPixelHash")
            and source_rgba == output_rgba,
            "R12 PNG-derived still does not retain its exact decoded source pixels",
        )
        _need(
            _probe_content(_run_pinned_frame_probe(source_path))
            == _probe_content(original["originalProbe"])
            and _probe_content(_run_pinned_frame_probe(output_path))
            == _probe_content(delivered["outputProbe"]),
            "R12 still source/output probes differ from retained accepted evidence",
        )
    return raw, evidence


def _audio_source_entries(
    manifest: Json,
    dependencies: Json,
    view: Json,
    prepared: Mapping[str, v2_package._Preparation],
    wavs: Mapping[str, bytes],
    proofs: Mapping[str, SourceProof],
    *,
    matrix_profile: bool = False,
) -> tuple[list[Json], dict[tuple[str, str], tuple[Json, ...]]]:

    manifest_sources = {row["id"]: row for row in manifest["sources"]}
    view_events = {row["id"]: row for row in view["events"]}
    prepared_by_binding = {
        _compiler_json_hash(item.record["binding"]): (key, item)
        for key, item in prepared.items()
    }
    boundaries = _array(
        dependencies.get("narrationBoundaryEvidence", []),
        "narration boundary evidence must be an array",
    )
    timing_root = _CANDIDATE / "TimingSources"
    has_narration = any(
        event.get("kind") == "narration" for event in manifest["events"]
    )
    review_raw = (
        _read(_R14, maximum=4 * 1024 * 1024)
        if has_narration and not matrix_profile
        else b""
    )
    timing_by_block = {
        path.stem: _read(path, maximum=4 * 1024 * 1024)
        for path in timing_root.glob("*.json")
        if path.stem in _NARRATION_TIMING_HASHES
    }
    if has_narration and not matrix_profile:
        _need(
            _sha(review_raw) == _R14_SHA256 and _sha(_r6_review()) == _R6_SHA256,
            "R14/R6 narration review receipt pins differ",
        )
    proof_payloads: dict[tuple[str, str], list[Json]] = {}
    entries: list[Json] = []
    for event in manifest["events"]:
        if event.get("kind") not in {"narration", "source_audio"}:
            continue
        event_id = event["eventId"]
        view_event = view_events[event_id]
        source_id = view_event["sourceId"]
        source_record = (
            manifest_sources[source_id] if event["kind"] == "narration" else None
        )
        proof = proofs[source_id]
        record = _json(proof.record, "authenticated source proof")
        wav_raw = wavs[source_id]
        delivery = {
            "eventId": event_id,
            "kind": event["kind"],
            "recordRange": view_event["recordRange"],
            "sourceRange": view_event["sourceRange"],
        }
        record_range = view_event["recordRange"]
        frames = record_range["durationFrames"]
        if event["kind"] == "narration":
            narration_source = _object(
                source_record, "narration manifest source required"
            )
            provenance = event["provenance"]
            block_id = provenance["blockId"]
            matching = [row for row in boundaries if row.get("blockId") == block_id]
            _need(
                len(matching) == 1 and _canonical(matching[0]) == _canonical(record),
                "narration proof row differs from exact boundary dependency",
            )
            timing_raw: bytes | None
            measured = matrix_profile and _narration_method(record) == "measured"
            if measured:
                # Measured (#182) evidence is admitted by self-consistent hash
                # pins rather than the statically pinned reviewed inventory.
                _need(
                    proof.timing is not None
                    and proof.review is not None
                    and proof.review == proof.receipt,
                    "measured narration proof must retain its timing and "
                    "measurement artifact bytes",
                )
                assert proof.timing is not None and proof.review is not None
                timing_raw = proof.timing
                _verify_measured_narration(
                    record, timing_raw, proof.review, _sha(wav_raw)
                )
                review_bytes = proof.review
            else:
                timing_raw = timing_by_block.get(block_id)
                _need(
                    timing_raw is not None
                    and _sha(timing_raw) == _NARRATION_TIMING_HASHES[block_id],
                    "narration timing source is not the pinned actual file",
                )
                assert timing_raw is not None
                _need(
                    proof.timing == timing_raw,
                    "narration proof does not retain the actual TIMING bytes",
                )
            if measured:
                pass  # review bytes already bound above
            elif matrix_profile:
                declared_review_hash = _allowed_narration_review_hash(
                    _object(
                        record.get("verification"),
                        "narration listening review required",
                    ).get("reviewArtifactHash")
                )
                _need(
                    proof.review is not None
                    and proof.review == proof.receipt
                    and _sha(proof.review) == declared_review_hash,
                    "narration proof review/receipt differs from "
                    "declared pinned artifact",
                )
                assert proof.review is not None
                review_bytes = proof.review
            else:
                _need(
                    _sha(proof.receipt) == _R14_SHA256 and proof.review == review_raw,
                    "narration proof does not retain the actual R14 "
                    "review/receipt bytes",
                )
                review_bytes = review_raw
            audio = narration_source["narrationAudio"]
            count = audio["durationSamples"]
            expected_wav_hash = audio["audioHash"].removeprefix("sha256:")
            _need(
                view_event["sourceRange"]
                == {"startFrame": 0, "durationFrames": frames},
                "narration delivery range must begin at source zero",
            )
            pins = {
                "timing": _sha(timing_raw),
                "review": _sha(review_bytes),
                "receipt": _sha(proof.receipt),
            }
            source_rate, q, start_sample, end_sample = 48000, 0, 0, count
            native_hash = expected_wav_hash
            channels = audio["channels"]
            entries_kind = "narration_preparation"
            proof_payload = {
                "row": record,
                "timingHash": "sha256:" + pins["timing"],
                "reviewHash": "sha256:" + pins["review"],
                "audioHash": record["audioHash"],
            }
            proof_payloads.setdefault((entries_kind, _sha(proof.receipt)), []).append(
                proof_payload
            )
        else:
            binding_hash = event["preparationBindingHash"]
            item = prepared_by_binding.get(binding_hash)
            _need(
                item is not None,
                "source-audio event has no retained exact public preparation",
            )
            assert item is not None
            requirement_key, preparation = item
            audio = preparation.record["audio"]
            source_stream = event["sourceTimeMapping"]["sourceFrameMap"][
                "sourceAudioStreamMappings"
            ]
            _need(
                type(source_stream) is list and len(source_stream) == 1,
                "source-audio mapping must select one authenticated stream",
            )
            source_rate = source_stream[0]["sampleRate"]
            q = audio["resampledFirstSample"]
            sample_range = event["audio"]["sampleRange"]
            start_fraction = (
                Fraction(sample_range["startFrame"] * 48000, source_rate) - q
            )
            end_fraction = Fraction(sample_range["endFrame"] * 48000, source_rate) - q
            _need(
                start_fraction.denominator == end_fraction.denominator == 1,
                "fractional source-audio sample mapping",
            )
            start_sample, end_sample = int(start_fraction), int(end_fraction)
            plan = endpoint_plan(event, audio, Fraction(24000, 1001))
            _need(
                plan is not None
                or (
                    start_sample % _FRAME_SAMPLES == end_sample % _FRAME_SAMPLES == 0
                    and end_sample - start_sample == frames * _FRAME_SAMPLES
                ),
                "source-audio sample interval is off-grid or not unit-speed",
            )
            _need(
                0 <= start_sample < end_sample <= audio["decodedSamples"],
                "source-audio interval exceeds authenticated PCM sidecar",
            )
            pins = preparation.record["binding"]
            native_hash = audio["contentHash"].removeprefix("sha256:")
            if plan is not None:
                native_hash = _sha(endpoint_wav(wav_raw, plan, audio))
            channels = audio["channels"]
            expected_wav_hash = audio["contentHash"].removeprefix("sha256:")
            entries_kind = "private_preparation"
            proof_payload = {
                "preparationBindingHash": binding_hash,
                "recordSha256": _sha(proof.record),
                "binding": preparation.record["binding"],
            }
            proof_payloads.setdefault((entries_kind, _sha(proof.receipt)), []).append(
                proof_payload
            )
            _need(
                requirement_key == preparation.requirement_key
                and proof.record == preparation.raw == proof.receipt,
                "source-audio proof receipt is not the exact actual #174 record",
            )
        pcm_frames, pcm_channels, decoded = _verify_wav(
            wav_raw,
            expected_wav_hash,
            {
                "channels": channels,
                "decodedSamples": count
                if event["kind"] == "narration"
                else audio["decodedSamples"],
            },
            f"audio source {source_id}",
        )
        _need(
            pcm_frames
            == (count if event["kind"] == "narration" else audio["decodedSamples"])
            and pcm_channels == channels,
            "authenticated PCM extent differs",
        )
        mapping = {
            "sourceId": source_id,
            "nativeFrameOrigin": 0,
            "pcmSampleOrigin": 0,
            "sourceSampleRate": source_rate,
            "sampleRate": 48000,
            "resampledFirstSample": q,
            "startSample": start_sample,
            "endSample": end_sample,
            "provenanceRecordSha256": _sha(proof.record),
        }
        entries.append(
            {
                "sourceId": source_id,
                "nativeSourceSha256": native_hash,
                "pcmMode": "wav-direct"
                if event["kind"] == "narration"
                else "prepared-audio",
                "provenanceReceiptSha256": _sha(proof.receipt),
                "provenancePinsSha256": _sha(_canonical(pins)),
                "deliveryDerivationSha256": _sha(_canonical(delivery)),
                "pcmFileSha256": _sha(wav_raw),
                "decodedSamplesSha256": _sha(decoded),
                "originalBitDepth": 24,
                "channels": pcm_channels,
                "durationSamples": pcm_frames,
                "sampleRate": 48000,
                "pcmMappingSha256": _sha(_canonical(mapping)),
                "nativeFrameOrigin": 0,
                "pcmSampleOrigin": 0,
            }
        )
    entries.sort(key=lambda row: row["sourceId"])
    _need(
        len({row["nativeSourceSha256"] for row in entries}) == len(entries),
        "audio source hashes alias",
    )
    return entries, {key: tuple(value) for key, value in proof_payloads.items()}


def _verify_actual_174_source(
    record: Json,
    source_path: Path,
    tracked_states: dict[Path, tuple[int, int, int, int, int]],
    tracked_hashes: dict[Path, str],
) -> None:
    """Re-inspect the four actually prepared source MOVs, without rerunning prep."""
    from .media_preparation import MediaTools, inspect_media

    for tool, digest in ((_FFMPEG, _FFMPEG_SHA256), (_FFPROBE, _FFPROBE_SHA256)):
        _need(_hash_file(tool) == digest, "source verification executable changed")
    inputs = record["inputs"]
    original = record["binding"]["originalSource"]
    source_state = _state(source_path)
    source_hash = _hash_file(source_path)
    _need(
        source_hash == original["contentHash"].removeprefix("sha256:"),
        "#174 source media hash differs",
    )
    inspection = inspect_media(
        source_path,
        video_stream_index=inputs["videoStreamIndex"],
        audio_stream_index=inputs.get("audioStreamIndex"),
        tools=MediaTools(str(_FFMPEG), str(_FFPROBE)),
    )
    _need(
        inspection.probe == record["sourceProbe"]
        and inspection.probe_hash == original["probeHash"]
        and inspection.content_hash == original["contentHash"],
        "#174 source probe does not reproduce from the actual original media",
    )
    mappings = record["binding"]["timeMapping"]["sourceFrameMap"][
        "sourceAudioStreamMappings"
    ]
    if mappings:
        _need(
            len(mappings) == 1
            and inspection.audio_hash == mappings[0]["audioHash"]
            and inspection.audio is not None
            and inspection.audio["index"] == inputs.get("audioStreamIndex"),
            "#174 source audio probe/hash differs from the actual selected stream",
        )
    else:
        _need(inspection.audio is None, "unexpected source audio stream")
    _need(_state(source_path) == source_state, "source changed during reinspection")
    tracked_states[source_path] = source_state
    tracked_hashes[source_path] = source_hash
    for path, digest in ((_FFMPEG, _FFMPEG_SHA256), (_FFPROBE, _FFPROBE_SHA256)):
        tracked_states[path] = _state(path)
        tracked_hashes[path] = digest


def _source_proof_inventory(
    entries: list[Json], proofs: Mapping[str, SourceProof], wavs: Mapping[str, bytes]
) -> list[Json]:
    rows = []
    for entry in entries:
        proof = proofs[entry["sourceId"]]
        rows.append(
            {
                "sourceId": entry["sourceId"],
                "kind": entry["pcmMode"],
                "recordSha256": _sha(proof.record),
                "receiptSha256": _sha(proof.receipt),
                "timingSha256": _sha(proof.timing)
                if proof.timing is not None
                else None,
                "reviewSha256": _sha(proof.review)
                if proof.review is not None
                else None,
                "wavSha256": _sha(wavs[entry["sourceId"]]),
            }
        )
    return rows


def _copy_exact_file(path: Path, destination: Path, expected_sha256: str) -> None:
    _copy_exclusive(path, destination, expected_sha256)


def _retain(path: Path, raw: bytes, *, existing: bool) -> None:
    if existing:
        _need(
            _read(path, maximum=max(_MAX_JSON, len(raw))) == raw,
            f"retained artifact differs: {path.name}",
        )
    else:
        _write_exclusive(path, raw)


def _track(
    path: Path,
    states: dict[Path, tuple[int, int, int, int, int]],
    hashes: dict[Path, str],
    *,
    maximum: int = _MAX_JSON,
) -> bytes:
    raw = _read(path, maximum=maximum)
    states[path] = _state(path)
    hashes[path] = _sha(raw)
    return raw


def _narration_method(row: object) -> str:
    """``reviewed`` or ``measured`` evidence; unknown methods refuse."""
    try:
        return narration_evidence_method(row)
    except ProofBuildError as error:
        raise QualificationPackageError(str(error)) from error


def _verify_measured_narration(
    row: object, timing: bytes, artifact: bytes, audio_sha256: str | None
) -> None:
    try:
        verify_measured_narration_evidence(
            row, timing=timing, artifact=artifact, audio_sha256=audio_sha256
        )
    except ProofBuildError as error:
        raise QualificationPackageError(str(error)) from error


def _track_measured_narration(
    row: Json,
    paths: Mapping[str, Path] | None,
    wav: bytes,
    frozen_block: Mapping[str, Any],
    states: dict[Path, tuple[int, int, int, int, int]],
    hashes: dict[Path, str],
) -> tuple[bytes, bytes]:
    """Read measured evidence's timing and measurement artifact from the inputs.

    The caller declares the two files; each must end in the locator the
    evidence itself pins, so the evidence cannot be satisfied by other bytes.
    """
    _need(
        isinstance(paths, Mapping) and set(paths) == {"timing", "measurement"},
        "measured narration requires its timing and measurement artifact paths",
    )
    assert paths is not None
    verification = _object(row.get("verification"), "measured verification required")
    audio = _object(row.get("audio"), "measured audio binding required")
    locator = _text(
        verification.get("measurementArtifactLocator"),
        "measurement artifact locator required",
    )
    audio_locator = _text(audio.get("locator"), "narration audio locator required")
    timing_locator = audio_locator.rsplit("/", 1)[0] + "/timing.json"
    for key, expected in (("timing", timing_locator), ("measurement", locator)):
        path = paths[key]
        _need(
            isinstance(path, Path)
            and path.is_absolute()
            and not path.is_symlink()
            and ("/" + path.as_posix().lstrip("/")).endswith("/" + expected)
            and ".." not in expected.split("/"),
            f"measured narration {key} path is not inside the evidence locator",
        )
    timing = _track(paths["timing"], states, hashes)
    artifact = _track(paths["measurement"], states, hashes)
    _verify_measured_narration(row, timing, artifact, _sha(wav))

    from .narration.cache import CacheError, NarrationCache
    from .narration.measure import MeasurementError, load_asset, measure_asset

    block_id = _text(row.get("blockId"), "measured narration block id required")
    audio = _object(row.get("audio"), "measured narration audio binding required")
    asset_id = _text(audio.get("cacheAssetId"), "cache asset id required")
    audio_locator_parts = _text(
        audio.get("locator"), "narration audio locator required"
    ).split("/")
    _need(
        len(audio_locator_parts) == 5
        and audio_locator_parts[:2] == ["v1", "assets"]
        and audio_locator_parts[2] == block_id
        and audio_locator_parts[3] == asset_id
        and audio_locator_parts[4] == "narration.wav"
        and re.fullmatch(r"[A-Za-z0-9-]{1,128}", block_id) is not None
        and re.fullmatch(r"[0-9a-f]{64}", asset_id) is not None,
        "measured narration locator must identify its local cache asset",
    )
    timing_path = paths["timing"]
    _need(
        ".." not in timing_path.parts
        and timing_path.parts[-5:]
        == ("v1", "assets", block_id, asset_id, "timing.json"),
        "measured narration timing path must identify its local cache asset",
    )
    v2_package._require_path_components_no_symlink(
        timing_path, "measured narration cache input"
    )
    cache_root = timing_path.parents[4]
    version_root = cache_root / "v1"
    _need(
        all(
            (version_root / name).is_dir() and not (version_root / name).is_symlink()
            for name in ("assets", "synthesis", "normalization", "locks")
        ),
        "measured narration cache is incomplete",
    )
    try:
        cache = NarrationCache(cache_root)
        asset_key = f"{block_id}/{asset_id}"
        asset_entry = cache.read("assets", asset_key, "asset.json")
        _need(asset_entry is not None, "measured narration cache asset is missing")
        assert asset_entry is not None
        loaded = load_asset(cache, f"{block_id}/{asset_id}")
        asset_dir = cache.root / "assets" / block_id / asset_id
        _need(
            asset_dir.resolve(strict=True) == timing_path.parent.resolve(strict=True),
            "measured narration timing path differs from its cache asset",
        )
        _track_measured_cache_entry(
            asset_dir,
            asset_entry,
            "asset.json",
            states,
            hashes,
        )
        expected_asset = loaded.asset.as_json()
        expected_asset["request_ids"] = list(loaded.asset.request_ids)
        _need(
            asset_entry.metadata.get("asset") == expected_asset
            and asset_entry.files.get("narration.wav") == loaded.wav_bytes == wav
            and asset_entry.files.get("timing.json") == loaded.timing_bytes == timing,
            "measured narration cache asset differs from package inputs",
        )
        synthesis_key = loaded.asset.request_hash.removeprefix("sha256:")
        synthesis_dir = cache.root / "synthesis" / synthesis_key
        synthesis_entry = cache.read("synthesis", synthesis_key, "synthesis.json")
        _need(
            synthesis_entry is not None,
            "measured narration synthesis cache entry is missing",
        )
        assert synthesis_entry is not None
        _track_measured_cache_entry(
            synthesis_dir,
            synthesis_entry,
            "synthesis.json",
            states,
            hashes,
        )
        _need(
            synthesis_entry.metadata.get("audioFormat") == "pcm_s16le"
            and synthesis_entry.metadata.get("sampleRate") == loaded.raw_sample_rate
            and synthesis_entry.metadata.get("channels") == 1
            and synthesis_entry.files.get("provider-audio.pcm") == loaded.raw_pcm,
            "measured narration raw PCM differs from its cache entry",
        )
        verification = _object(
            row.get("verification"), "measured verification required"
        )
        result = measure_asset(
            loaded,
            frozen_block,
            artifact_locator=_text(
                verification.get("measurementArtifactLocator"),
                "measurement artifact locator required",
            ),
        )
    except (
        CacheError,
        MeasurementError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        if isinstance(error, QualificationPackageError):
            raise
        raise QualificationPackageError(
            f"measured narration cache remeasurement refused: {error}"
        ) from error
    _need(
        result.artifact_bytes == artifact,
        "measured narration artifact differs from local cache remeasurement",
    )
    _need(
        _canonical(result.evidence) == _canonical(row),
        "measured narration evidence differs from local cache remeasurement",
    )
    return timing, artifact


def _track_measured_cache_entry(
    path: Path,
    entry: Any,
    metadata_name: str,
    states: dict[Path, tuple[int, int, int, int, int]],
    hashes: dict[Path, str],
) -> None:
    _need(path.is_dir() and not path.is_symlink(), "narration cache entry required")
    tracked = {
        child.name: _track(
            child,
            states,
            hashes,
            maximum=_MAX_JSON if child.name == metadata_name else _MAX_WAV,
        )
        for child in sorted(path.iterdir())
    }
    metadata_raw = tracked.get(metadata_name)
    _need(metadata_raw is not None, "narration cache metadata required")
    assert metadata_raw is not None
    _need(
        set(tracked) == set(entry.files) | {metadata_name}
        and {name: raw for name, raw in tracked.items() if name != metadata_name}
        == entry.files
        and _json(metadata_raw, "narration cache metadata") == entry.metadata,
        "narration cache entry changed while being admitted",
    )


def _document_narration_block(document: Json | None, block_id: str) -> Json:
    _need(document is not None, "measured narration requires the compiled document")
    assert document is not None
    draft = _object(document.get("activeDraft"), "active narration draft required")
    blocks = _array(draft.get("blocks"), "active narration blocks required")
    matches = [
        block
        for block in blocks
        if isinstance(block, dict)
        and block.get("type") == "narration"
        and block.get("id") == block_id
    ]
    _need(len(matches) == 1, "measured narration must bind to one compiled block")
    return matches[0]


def _allowed_narration_review_hash(value: object) -> str:
    declared = _text(value, "narration review artifact hash required")
    digest = declared.removeprefix("sha256:")
    _need(
        declared in {digest, "sha256:" + digest}
        and digest in {_R6_SHA256, _R14_SHA256},
        "narration review artifact is outside the statically pinned inventory",
    )
    return digest


def _track_narration_review(
    value: object,
    states: dict[Path, tuple[int, int, int, int, int]],
    hashes: dict[Path, str],
) -> bytes:
    digest = _allowed_narration_review_hash(value)
    if digest == _R6_SHA256:
        expected = _r6_review()
        path = _R6_TARGET
    else:
        expected = None
        path = _R14
    raw = _track(path, states, hashes)
    _need(
        _sha(raw) == digest and (expected is None or raw == expected),
        "narration review bytes differ from the statically pinned artifact",
    )
    return raw


def _read_revised_pin(value: object, label: str) -> tuple[Path, bytes, str]:
    pin = _object(value, f"{label} pin required")
    _need(set(pin) == {"path", "sha256"}, f"{label} pin shape differs")
    path = Path(_text(pin["path"], f"{label} pin path required"))
    digest = _text(pin["sha256"], f"{label} pin hash required")
    _need(
        path.is_absolute() and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
        f"{label} pin is malformed",
    )
    raw = _read(path)
    _need(_sha(raw) == digest, f"{label} pin bytes differ")
    return path, raw, digest


def _r6_review() -> bytes:
    _need(_R6.resolve(strict=True) == _R6_TARGET, "R6 review target changed")
    raw = _read(_R6_TARGET)
    _need(_sha(raw) == _R6_SHA256, "R6 review bytes changed")
    return raw


def _track_compiler(
    dependencies: Json,
    states: dict[Path, tuple[int, int, int, int, int]],
    hashes: dict[Path, str],
) -> None:
    repository = Path(__file__).resolve().parents[2]
    core = repository / "packages/contracts/src/compiler-core-v2.ts"
    core_raw = _track(core, states, hashes)
    _need(
        dependencies["compiler"]["sourceHash"] == "sha256:" + _sha(core_raw),
        "compiler source differs from the dependency pin",
    )
    for path in (
        _COMPILER,
        _GENERIC_TORSO,
        repository / "packages/contracts/src/compiler-core.ts",
        repository / "package-lock.json",
        repository / "uv.lock",
    ):
        _track(path, states, hashes)
    states[_NODE] = _state(_NODE)
    hashes[_NODE] = _hash_file(_NODE)


def _prepared_public(
    document: Json,
    dependencies: Json,
    manifest: Json,
    report: Json,
    states: dict[Path, tuple[int, int, int, int, int]],
    hashes: dict[Path, str],
) -> tuple[dict[str, v2_package._Preparation], dict[str, Path]]:
    """Use #177's unchanged receipt validator on only the public #174 rows."""
    bindings = [
        row
        for row in manifest["preparationBindings"]
        if row["requirementKey"] in _PREPARED_Q
    ]
    _need(bool(bindings), "actual public #174 audio preparation required")
    paths: dict[str, Path] = {}
    sidecars: dict[str, Path] = {}
    for binding in bindings:
        key = binding["requirementKey"]
        path = _PREPARED_ROOT / key.removeprefix("sha256:") / "receipt.json"
        record, _raw, audio_path, _wav, _pcm = _verify_public_receipt(
            key, path, states, hashes
        )
        _need(
            record["binding"] == binding,
            "actual public receipt binding differs from compiler",
        )
        _need(audio_path is not None, "first smoke requires prepared audio")
        assert audio_path is not None
        paths[key] = path
        sidecars[key] = audio_path
    public_manifest = {**manifest, "preparationBindings": bindings}
    prepared = v2_package._validate_preparations(
        document, dependencies, public_manifest, report, paths
    )
    return prepared, sidecars


def _prediction_audio_path(
    manifest: Json, event: Json, audio: Json, native_path: Path
) -> Path:
    if endpoint_plan(event, audio, Fraction(24000, 1001)) is None:
        return native_path
    return native_path.parents[2] / v2_package._original_audio_path(
        manifest, event["eventId"]
    )


def _audio_proofs(
    manifest: Json,
    dependencies: Json,
    view: Json,
    source_paths: Mapping[str, Path],
    prepared: Mapping[str, v2_package._Preparation],
    states: dict[Path, tuple[int, int, int, int, int]],
    hashes: dict[Path, str],
    *,
    allow_silent: bool = False,
    matrix_profile: bool = False,
    narration_evidence_paths: Mapping[str, Mapping[str, Path]] | None = None,
    narration_document: Json | None = None,
) -> tuple[
    dict[str, bytes],
    dict[str, SourceProof],
    list[Json],
    dict[tuple[str, str], tuple[Json, ...]],
]:
    wavs: dict[str, bytes] = {}
    proofs: dict[str, SourceProof] = {}
    by_binding = {
        _compiler_json_hash(item.record["binding"]): item for item in prepared.values()
    }
    view_events = {row["id"]: row for row in view["events"]}
    for event in manifest["events"]:
        if event["kind"] not in {"narration", "source_audio"}:
            continue
        sid = view_events[event["eventId"]]["sourceId"]
        path = source_paths[sid]
        if event["kind"] == "source_audio":
            item = by_binding[event["preparationBindingHash"]]
            path = _prediction_audio_path(manifest, event, item.record["audio"], path)
        raw = _read(path, maximum=_MAX_WAV)
        states[path] = _state(path)
        hashes[path] = _sha(raw)
        wavs[sid] = raw
        if event["kind"] == "source_audio":
            item = by_binding[event["preparationBindingHash"]]
            proofs[sid] = SourceProof(item.raw, item.raw)
        else:
            block_id = event["provenance"]["blockId"]
            rows = [
                row
                for row in dependencies["narrationBoundaryEvidence"]
                if row["blockId"] == block_id
            ]
            _need(len(rows) == 1, "exact narration boundary row required")
            if matrix_profile and _narration_method(rows[0]) == "measured":
                timing, review = _track_measured_narration(
                    rows[0],
                    (narration_evidence_paths or {}).get(block_id),
                    raw,
                    _document_narration_block(narration_document, block_id),
                    states,
                    hashes,
                )
                proofs[sid] = SourceProof(
                    _canonical(rows[0]), review, timing=timing, review=review
                )
                continue
            timing = _track(
                _CANDIDATE / "TimingSources" / f"{block_id}.json", states, hashes
            )
            if matrix_profile:
                review = _track_narration_review(
                    _object(
                        _object(rows[0], "narration boundary record required").get(
                            "verification"
                        ),
                        "narration listening review required",
                    ).get("reviewArtifactHash"),
                    states,
                    hashes,
                )
            else:
                review = _track(_R14, states, hashes)
                _r6_review()
                _track(_R6_TARGET, states, hashes)
            proofs[sid] = SourceProof(
                _canonical(rows[0]), review, timing=timing, review=review
            )
    entries, payloads = _audio_source_entries(
        manifest,
        dependencies,
        view,
        prepared,
        wavs,
        proofs,
        matrix_profile=matrix_profile,
    )
    _need(
        bool(entries)
        or (
            allow_silent
            and not any(
                event["kind"] in {"source_audio", "narration"}
                for event in manifest["events"]
            )
        ),
        "qualification requires actual programme audio",
    )
    return wavs, proofs, entries, payloads


def _snapshots(
    *,
    profile: str,
    originals: tuple[bytes, bytes],
    execution: tuple[bytes, bytes],
    manifest_raw: bytes,
    report_raw: bytes,
    view_raw: bytes,
    source_entries: list[Json],
    proofs: Mapping[str, SourceProof],
    wavs: Mapping[str, bytes],
    public_verified: bool,
) -> tuple[bytes, bytes]:
    preflight = {
        "schemaVersion": "qualification-output-package-preflight/v1",
        "lane": "bounded_output_residual_consistency",
        "profile": profile,
        "status": "host_admitted",
        "inputHashes": {
            "originalDocumentSha256": _sha(originals[0]),
            "originalDependenciesSha256": _sha(originals[1]),
            "executionDocumentSha256": _sha(execution[0]),
            "executionDependenciesSha256": _sha(execution[1]),
            "manifestSha256": _sha(manifest_raw),
            "reportSha256": _sha(report_raw),
            "viewSha256": _sha(view_raw),
        },
        "ordinaryPublicPackageVerified": public_verified,
        "unchecked": [
            "native_geometry",
            "render",
            "same_output_decode",
            "internal_controls",
            "creative_acceptance",
        ],
    }
    preparation = {
        "schemaVersion": "qualification-output-source-preparation/v1",
        "lane": "bounded_output_residual_consistency",
        "profile": profile,
        "sourceEntries": source_entries,
        "sourceProofs": _source_proof_inventory(source_entries, proofs, wavs),
        "nativeAuthority": False,
    }
    return _canonical(preflight), _canonical(preparation)


def _admit_r16(
    output_root: Path, *, existing: bool = False
) -> QualificationOutputAdmissionV2:
    states: dict[Path, tuple[int, int, int, int, int]] = {}
    hashes: dict[Path, str] = {}
    links: dict[Path, tuple[str, Path]] = {}
    delta_raw = _track(_DELTA, states, hashes)
    _need(
        _sha(delta_raw) == _EXPECTED_DELTA,
        "retained original-identity/delta evidence changed",
    )
    delta = _identity_delta(delta_raw)
    originals: list[bytes] = []
    for path, expected in (
        (_ORIGINAL_DOCUMENT, _EXPECTED_ORIGINAL_DOCUMENT),
        (_ORIGINAL_DEPENDENCIES, _EXPECTED_ORIGINAL_DEPENDENCIES),
    ):
        raw, input_states, input_hashes = _parse_original_link(
            path, expected, delta["finalInputState"]
        )
        originals.append(raw)
        states.update(input_states)
        hashes.update(input_hashes)
        links[path] = (os.readlink(path), path.resolve(strict=True))
    execution_document = _track(_EXECUTION_DOCUMENT, states, hashes)
    execution_dependencies = _track(_EXECUTION_DEPENDENCIES, states, hashes)
    _need(
        execution_document == originals[0]
        and _sha(execution_dependencies) == _EXPECTED_EXECUTION_DEPENDENCIES,
        "R16 execution input pins differ",
    )
    document = _json(execution_document, "R16 document")
    dependencies = _json(execution_dependencies, "R16 execution dependencies")
    _track_compiler(dependencies, states, hashes)
    acceptance = _track(_HOST_ACCEPTANCE, states, hashes)
    _authenticate_dependency_delta(
        _json(originals[1], "original dependencies"), dependencies, delta, acceptance
    )
    manifest_raw, report_raw = (
        _track(_MANIFEST, states, hashes),
        _track(_REPORT, states, hashes),
    )
    _pin_r16_vector(manifest_raw, _R16_MANIFEST_SHA256, "manifest")
    _pin_r16_vector(report_raw, _R16_REPORT_SHA256, "report")
    manifest, report = (
        _json(manifest_raw, "R16 manifest"),
        _json(report_raw, "R16 report"),
    )
    _validate_r16_duration(manifest)
    one, two = (
        _track(_COMPILE_ONE, states, hashes),
        _track(_COMPILE_TWO, states, hashes),
    )
    _pin_r16_vector(one, _R16_COMPILE_ONE_SHA256, "compile-1")
    _pin_r16_vector(two, _R16_COMPILE_TWO_SHA256, "compile-2")
    compiled = _locked_compiler(_EXECUTION_DOCUMENT, _EXECUTION_DEPENDENCIES, one, two)
    _need(
        compiled["result"]["manifestJson"].encode() == manifest_raw
        and compiled["result"]["reportJson"].encode() == report_raw,
        "R16 canonical emitted bytes differ",
    )
    diagnostics, recoveries = _canonical_r16_report(
        document, dependencies, manifest, report, compiled
    )
    _validate_scoped_r16_inputs(document, dependencies, manifest, report)
    prepared, sidecars = _prepared_public(
        document, dependencies, manifest, report, states, hashes
    )
    _need(
        set(prepared) == set(_PREPARED_Q),
        "R16 requires all four exact public preparations",
    )
    _authenticate_r12_stills(dependencies, states, hashes)
    _r6_review()
    if _R6.is_symlink():
        states[_R6] = _state(_R6)
        links[_R6] = (os.readlink(_R6), _R6_TARGET)
    media, media_states, media_hashes, media_links = _r16_media_paths(
        manifest, prepared, sidecars
    )
    states.update(media_states)
    hashes.update(media_hashes)
    links.update(media_links)
    for item in prepared.values():
        source = next(
            row
            for row in manifest["sources"]
            if row.get("preparationRequirementKey") == item.requirement_key
        )
        _verify_actual_174_source(
            item.record, media[f"original:{source['id']}"], states, hashes
        )
    artifacts = v2_package._media_artifacts(manifest, prepared, media)
    view = v2_package._delivery_view(manifest, dependencies, prepared, artifacts)
    view_raw = v2_package._canonical_json(view)
    root = output_root / "package"
    if not existing:
        output_root.mkdir(mode=0o700, parents=True, exist_ok=False)
        root.mkdir(mode=0o700)
    for artifact in artifacts.values():
        destination = root / artifact.relative_path
        digest = artifact.content_hash.removeprefix("sha256:")
        if existing:
            _need(_hash_file(destination) == digest, "retained R16 media differs")
        else:
            v2_package._copy_artifact(artifact, root)
    source_paths = {row["id"]: root / row["path"] for row in view["sources"]}
    wavs, proofs, entries, payloads = _audio_proofs(
        manifest, dependencies, view, source_paths, prepared, states, hashes
    )
    preflight, preparation = _snapshots(
        profile=R16_PROFILE,
        originals=(originals[0], originals[1]),
        execution=(execution_document, execution_dependencies),
        manifest_raw=manifest_raw,
        report_raw=report_raw,
        view_raw=view_raw,
        source_entries=entries,
        proofs=proofs,
        wavs=wavs,
        public_verified=False,
    )
    return _finish_admission(
        output_root,
        profile=R16_PROFILE,
        disposition="qualification_only",
        creative_qualification=CREATIVE_UNQUALIFIED,
        original_document=originals[0],
        original_dependencies=originals[1],
        execution_document=execution_document,
        execution_dependencies=execution_dependencies,
        manifest=manifest,
        manifest_raw=manifest_raw,
        report=report,
        report_raw=report_raw,
        compiler_runs=(one, two),
        view=view,
        view_raw=view_raw,
        diagnostics=list(diagnostics),
        recoveries=list(recoveries),
        preflight_raw=preflight,
        preparation_raw=preparation,
        source_entries=entries,
        source_proofs=proofs,
        source_wavs=wavs,
        source_paths=source_paths,
        tracked_paths=states,
        tracked_hashes=hashes,
        tracked_links=links,
        proof_payloads=payloads,
        existing=existing,
    )


def _presenter_report(document: Json, manifest: Json, report: Json) -> None:
    message = "On Camera uses the effective temporary presenter still."
    diagnostics = _array(report.get("diagnostics"), "Presenter warnings required")
    _need(
        len(diagnostics) == 1
        and diagnostics[0]
        == {
            "id": "5e77b270-31bf-5ab0-8a99-4698599c131e",
            "code": "TEMPORARY_PRESENTER_STILL",
            "severity": "warning",
            "message": message,
            "entity": {"id": _PRESENTER_SLOT, "kind": "slot", "path": "presenterStill"},
            "evidence": {"kind": "details", "message": message},
            "recoveryActionKinds": ["REPLACE_TEMPORARY_PRESENTER"],
        },
        "Presenter profile requires its exact single temporary-still warning",
    )
    _need(
        report.get("status") == "ready"
        and report.get("migrationIssues") == []
        and report.get("recoveryActions")
        == [
            {
                "documentId": document["id"],
                "instruction": (
                    "Replace the temporary still with an accepted presenter source "
                    "when available."
                ),
                "kind": "REPLACE_TEMPORARY_PRESENTER",
                "slotId": _PRESENTER_SLOT,
            }
        ],
        "Presenter qualification readiness/recovery differs",
    )
    _validate_r16_duration(manifest)
    pictures = [event for event in manifest["events"] if event["kind"] == "placeholder"]
    reference = (
        pictures[0]["pictureTreatment"]["reference"] if len(pictures) == 1 else {}
    )
    _need(
        len(pictures) == 1
        and pictures[0]["provenance"]["slotId"] == _PRESENTER_SLOT
        and pictures[0]["pictureTreatment"]["kind"] == "still"
        and pictures[0]["pictureTreatment"]["composition"]["framingPolicy"] == "contain"
        and reference.get("contentHash") == "sha256:" + _PRESENTER_PNG_SHA256
        and (reference.get("width"), reference.get("height")) == (320, 720),
        "Presenter image identity/contain geometry differs",
    )


def _presenter_pixels(
    path: Path,
    states: dict[Path, tuple[int, int, int, int, int]],
    hashes: dict[Path, str],
) -> None:
    raw = _track(path, states, hashes)
    _need(_sha(raw) == _PRESENTER_PNG_SHA256, "Presenter PNG bytes differ")
    _need(
        raw[:16] == b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        and struct.unpack(">IIBBBBB", raw[16:29]) == (320, 720, 8, 6, 0, 0, 0),
        "Presenter requires the exact 320x720 RGBA image",
    )
    pixels = _run_ffmpeg_raw(path, still=True)
    _need(
        len(pixels) == 320 * 720 * 4 and set(pixels[3::4]) == {0, 255},
        "Presenter pixels must contain transparent and opaque regions",
    )
    states[_FFMPEG] = _state(_FFMPEG)
    hashes[_FFMPEG] = _FFMPEG_SHA256


def _admit_presenter(output_root: Path) -> QualificationOutputAdmissionV2:
    """Fresh versioned execution of the issue-owned fixture, never an R16 waiver."""
    states: dict[Path, tuple[int, int, int, int, int]] = {}
    hashes: dict[Path, str] = {}
    links: dict[Path, tuple[str, Path]] = {}
    originals = tuple(
        _track(_PRESENTER_ROOT / "inputs" / name, states, hashes)
        for name in _PRESENTER_INPUT_PINS
    )
    _need(
        all(
            _sha(raw) == pin
            for raw, pin in zip(originals, _PRESENTER_INPUT_PINS.values(), strict=True)
        ),
        "Presenter original fixture inputs differ",
    )
    image = _PRESENTER_ROOT / "presenter.png"
    _presenter_pixels(image, states, hashes)
    document = _json(originals[0], "Presenter original document")
    dependencies = _json(originals[1], "Presenter original dependencies")
    # A new execution input changes only this consumed compiler identity; all
    # original private inputs and the older R16 source pin remain untouched.
    core = (
        Path(__file__).resolve().parents[2]
        / "packages/contracts/src/compiler-core-v2.ts"
    )
    dependencies["compiler"]["sourceHash"] = "sha256:" + _sha(
        _track(core, states, hashes)
    )
    execution_dependencies = _canonical(dependencies)
    _track_compiler(dependencies, states, hashes)
    root = output_root / "package"
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    document_path = root / "Execution/script-document-v2.json"
    dependencies_path = root / "Execution/compiler-dependencies-v2.json"
    _write_exclusive(document_path, originals[0])
    _write_exclusive(dependencies_path, execution_dependencies)
    one = _compiler_bytes(document_path, dependencies_path)
    compiled = _locked_compiler(document_path, dependencies_path, one, one)
    result = _object(compiled.get("result"), "Presenter compiler result required")
    _need(result.get("ok") is True, "current compiler refused Presenter fixture")
    manifest_raw = result["manifestJson"].encode()
    report_raw = result["reportJson"].encode()
    manifest = _json(manifest_raw, "Presenter manifest")
    report = _json(report_raw, "Presenter report")
    _need(
        result["manifest"] == manifest and result["report"] == report,
        "Presenter compiler envelope differs",
    )
    _validate_scoped_r16_inputs(document, dependencies, manifest, report)
    _presenter_report(document, manifest, report)
    paths: dict[str, Path] = {}
    media: dict[str, Path] = {}
    for binding in manifest["preparationBindings"]:
        key = binding["requirementKey"]
        delivered = _locators(binding["artifactLocator"], "Presenter prepared picture")
        receipt = delivered.parent / "receipt.json"
        record, _raw, _audio, _wav, _pcm = _verify_public_receipt(
            key, receipt, states, hashes, matrix=True
        )
        _need(record["binding"] == binding, "Presenter preparation binding differs")
        paths[key] = receipt
    prepared = v2_package._validate_preparations(
        document, dependencies, manifest, report, paths
    )
    original_picture = (
        MATRIX_PREPARATION_ROOT
        / "mixed-01/sources/clip-1-25fps/issue174-media/source-pcm_s24le.mov"
    )
    for source in manifest["sources"]:
        sid = source["id"]
        if "narrationAudio" in source:
            media[f"source:{sid}"] = _locators(
                source["narrationAudio"]["locator"],
                "Presenter narration",
                tracked_states=states,
                tracked_links=links,
            )
        else:
            item = prepared[source["preparationRequirementKey"]]
            _verify_actual_174_source(item.record, original_picture, states, hashes)
            media[f"source:{sid}"] = _locators(
                item.record["binding"]["artifactLocator"], "Presenter delivered picture"
            )
            media[f"original:{sid}"] = original_picture
    for event in manifest["events"]:
        if event["kind"] == "placeholder":
            media[f"event:{event['eventId']}"] = image
        elif event["kind"] == "source_audio":
            item = next(
                item
                for item in prepared.values()
                if _compiler_json_hash(item.record["binding"])
                == event["preparationBindingHash"]
            )
            media[f"event:{event['eventId']}"] = (
                paths[item.requirement_key].parent / "audio.wav"
            )
    artifacts = v2_package._media_artifacts(manifest, prepared, media)
    for artifact in artifacts.values():
        digest = artifact.content_hash.removeprefix("sha256:")
        states[artifact.origin] = _state(artifact.origin)
        hashes[artifact.origin] = digest
        _copy_exclusive(artifact.origin, root / artifact.relative_path, digest)
    view = v2_package._delivery_view(manifest, dependencies, prepared, artifacts)
    view_raw = v2_package._canonical_json(view)
    source_paths = {row["id"]: root / row["path"] for row in view["sources"]}
    wavs, proofs, entries, payloads = _audio_proofs(
        manifest, dependencies, view, source_paths, prepared, states, hashes
    )
    preflight, preparation = _snapshots(
        profile=PRESENTER_PROFILE,
        originals=(originals[0], originals[1]),
        execution=(originals[0], execution_dependencies),
        manifest_raw=manifest_raw,
        report_raw=report_raw,
        view_raw=view_raw,
        source_entries=entries,
        proofs=proofs,
        wavs=wavs,
        public_verified=False,
    )
    return _finish_admission(
        output_root,
        profile=PRESENTER_PROFILE,
        disposition="qualification_only",
        creative_qualification=CREATIVE_UNQUALIFIED,
        original_document=originals[0],
        original_dependencies=originals[1],
        execution_document=originals[0],
        execution_dependencies=execution_dependencies,
        manifest=manifest,
        manifest_raw=manifest_raw,
        report=report,
        report_raw=report_raw,
        compiler_runs=(one, one),
        view=view,
        view_raw=view_raw,
        diagnostics=report["diagnostics"],
        recoveries=report["recoveryActions"],
        preflight_raw=preflight,
        preparation_raw=preparation,
        source_entries=entries,
        source_proofs=proofs,
        source_wavs=wavs,
        source_paths=source_paths,
        tracked_paths=states,
        tracked_hashes=hashes,
        tracked_links=links,
        proof_payloads=payloads,
    )


def _prepared_matrix(
    document: Json,
    dependencies: Json,
    manifest: Json,
    report: Json,
    build: Path,
    preparation_paths: Mapping[str, Path],
    states: dict[Path, tuple[int, int, int, int, int]],
    hashes: dict[Path, str],
) -> dict[str, v2_package._Preparation]:
    """Authenticate each real published preparation and its packaged original."""
    _need(
        set(preparation_paths)
        == {row["requirementKey"] for row in manifest["preparationBindings"]},
        "matrix preparation path inventory differs",
    )
    paths: dict[str, Path] = {}
    for binding in manifest["preparationBindings"]:
        key = binding["requirementKey"]
        embedded = (
            build
            / "Preparation/receipts"
            / hashlib.sha256(key.encode()).hexdigest()
            / "receipt.json"
        )
        _track(embedded, states, hashes)
        receipt = preparation_paths[key]
        _need(receipt.is_absolute(), "absolute matrix preparation path required")
        actual, raw, _, _, _ = _verify_public_receipt(
            key, receipt, states, hashes, matrix=True
        )
        _need(
            raw == _read(embedded) and actual["binding"] == binding,
            "matrix published receipt differs from package",
        )
        paths[key] = receipt
    prepared = v2_package._validate_preparations(
        document, dependencies, manifest, report, paths
    )
    for key, item in prepared.items():
        sources = [
            row
            for row in manifest["sources"]
            if row.get("preparationRequirementKey") == key
        ]
        _need(bool(sources), "matrix preparation has no manifest source")
        for source in sources:
            originals = list((build / "Preparation/original").glob(source["id"] + ".*"))
            _need(len(originals) == 1, "matrix original source inventory differs")
            _verify_actual_174_source(item.record, originals[0], states, hashes)
    return prepared


def _admit_synthetic(
    output_root: Path,
    public_root: Path,
    *,
    existing: bool = False,
    profile: str = SYNTHETIC_PROFILE,
    preparation_paths: Mapping[str, Path] | None = None,
    narration_evidence_paths: Mapping[str, Mapping[str, Path]] | None = None,
    revision_originals: tuple[tuple[Path, bytes], tuple[Path, bytes]] | None = None,
    revision_execution_pins: Mapping[str, bytes] | None = None,
) -> QualificationOutputAdmissionV2:
    from .workflow_v2 import load_verified_package_v2
    from .workflow_v2_cli import attest_package_v2

    _need(public_root.is_absolute(), "absolute public package root required")
    _need(
        (revision_originals is None) == (revision_execution_pins is None),
        "complete revised input pins required",
    )
    if revision_originals is not None:
        _need(profile == MATRIX_PROFILE, "revised originals require the matrix profile")
        _need(
            type(revision_originals) is tuple
            and len(revision_originals) == 2
            and all(
                isinstance(path, Path) and path.is_absolute() and type(raw) is bytes
                for path, raw in revision_originals
            ),
            "revised original bytes and paths required",
        )
        _need(
            type(revision_execution_pins) is dict
            and set(revision_execution_pins)
            == {"document", "dependencies", "manifest", "report"}
            and all(type(raw) is bytes for raw in revision_execution_pins.values()),
            "revised execution pin set differs",
        )
    verified = v2_package.verify_v2_package(public_root)
    states: dict[Path, tuple[int, int, int, int, int]] = {}
    hashes: dict[Path, str] = {}
    revision_original_bytes: tuple[bytes, bytes] | None = None
    if revision_originals is not None:
        original_raw = tuple(
            _track(path, states, hashes) for path, _expected in revision_originals
        )
        _need(
            original_raw == tuple(expected for _path, expected in revision_originals),
            "revised original input changed after preflight verification",
        )
        revision_original_bytes = (original_raw[0], original_raw[1])
    if revision_execution_pins is not None:
        public_build = public_root / "Builds" / verified.build_id
        _need(
            {
                "document": _read(public_build / v2_package.DOCUMENT_FILENAME),
                "dependencies": _read(public_build / v2_package.DEPENDENCIES_FILENAME),
                "manifest": _read(public_build / v2_package.MANIFEST_FILENAME),
                "report": _read(public_build / v2_package.REPORT_FILENAME),
            }
            == revision_execution_pins,
            "revised public package differs from its preflight pins",
        )
    root = output_root / "package"
    inner = root / "PublicPackage"
    if not existing:
        before = _directory_states(public_root)
        inventory, _ = _inventory(public_root)
        output_root.mkdir(mode=0o700, parents=True, exist_ok=False)
        inner.mkdir(mode=0o700, parents=True)
        for row in inventory["files"]:
            _copy_exclusive(
                public_root / row["path"], inner / row["path"], row["sha256"]
            )
        _need(
            _directory_states(public_root) == before,
            "public package changed while cloning",
        )
    _need(
        v2_package.verify_v2_package(inner) == verified,
        "cloned public verification differs",
    )
    attestation_path = output_root / "attestation.json"
    if not existing:
        attest_package_v2(inner, attestation_path)
    loaded = load_verified_package_v2(attestation_path, _sha(_read(attestation_path)))
    _need(loaded.root == inner, "attestation targets another package")
    build = inner / "Builds" / verified.build_id
    document_raw = _track(build / v2_package.DOCUMENT_FILENAME, states, hashes)
    dependencies_raw = _track(build / v2_package.DEPENDENCIES_FILENAME, states, hashes)
    manifest_raw = _track(build / v2_package.MANIFEST_FILENAME, states, hashes)
    report_raw = _track(build / v2_package.REPORT_FILENAME, states, hashes)
    if revision_execution_pins is not None:
        _need(
            {
                "document": document_raw,
                "dependencies": dependencies_raw,
                "manifest": manifest_raw,
                "report": report_raw,
            }
            == revision_execution_pins,
            "cloned revised package bytes differ from the verified preflight pins",
        )
    original_documents = (
        revision_original_bytes
        if revision_original_bytes is not None
        else (document_raw, dependencies_raw)
    )
    view_raw = _track(build / v2_package.DELIVERY_VIEW_FILENAME, states, hashes)
    document, dependencies = (
        _json(document_raw, "synthetic document"),
        _json(dependencies_raw, "synthetic dependencies"),
    )
    manifest, report, view = (
        _json(manifest_raw, "synthetic manifest"),
        _json(report_raw, "synthetic report"),
        _json(view_raw, "synthetic view"),
    )
    _track_compiler(dependencies, states, hashes)
    first = _compiler_bytes(
        build / v2_package.DOCUMENT_FILENAME, build / v2_package.DEPENDENCIES_FILENAME
    )
    compiled = _locked_compiler(
        build / v2_package.DOCUMENT_FILENAME,
        build / v2_package.DEPENDENCIES_FILENAME,
        first,
        first,
    )
    _need(
        compiled["result"].get("ok") is True
        and compiled["result"]["manifestJson"].encode() == manifest_raw
        and compiled["result"]["reportJson"].encode() == report_raw,
        "synthetic package differs from exact current compiler output",
    )
    if profile == SYNTHETIC_PROFILE:
        _need(
            len(manifest["events"]) == 2
            and {row["kind"] for row in manifest["events"]}
            == {"primary_visual", "source_audio"},
            "first smoke profile requires one actual picture/source-audio pair",
        )
        prepared, _sidecars = _prepared_public(
            document, dependencies, manifest, report, states, hashes
        )
        _need(
            len(prepared) == 1 and len(manifest["preparationBindings"]) == 1,
            "single public preparation required for first smoke",
        )
        for item in prepared.values():
            originals = list((build / "Preparation" / "original").iterdir())
            _need(len(originals) == 1, "synthetic original source inventory differs")
            _verify_actual_174_source(item.record, originals[0], states, hashes)
    else:
        _need(profile == MATRIX_PROFILE, "unsupported public qualification profile")
        _need(
            1 <= manifest["timeline"]["durationFrames"] <= 1498
            and all(
                event["kind"]
                in {
                    "primary_visual",
                    "source_audio",
                    "overlay_visual",
                    "placeholder",
                    "narration",
                }
                for event in manifest["events"]
            ),
            "matrix requires bounded picture/source-audio events",
        )
        _need(
            preparation_paths is not None,
            "matrix requires exact published preparation paths",
        )
        assert preparation_paths is not None
        prepared = _prepared_matrix(
            document,
            dependencies,
            manifest,
            report,
            build,
            preparation_paths,
            states,
            hashes,
        )
    source_paths = {row["id"]: inner / row["path"] for row in view["sources"]}
    wavs, proofs, entries, payloads = _audio_proofs(
        manifest,
        dependencies,
        view,
        source_paths,
        prepared,
        states,
        hashes,
        allow_silent=profile == MATRIX_PROFILE,
        matrix_profile=profile == MATRIX_PROFILE,
        narration_evidence_paths=narration_evidence_paths,
        narration_document=document,
    )
    preflight, preparation = _snapshots(
        profile=profile,
        originals=original_documents,
        execution=(document_raw, dependencies_raw),
        manifest_raw=manifest_raw,
        report_raw=report_raw,
        view_raw=view_raw,
        source_entries=entries,
        proofs=proofs,
        wavs=wavs,
        public_verified=True,
    )
    return _finish_admission(
        output_root,
        profile=profile,
        disposition="verified_matrix_inputs"
        if profile == MATRIX_PROFILE
        else "verified_synthetic",
        creative_qualification="unqualified_studio_matrix"
        if profile == MATRIX_PROFILE
        else "qualified_synthetic_only",
        original_document=original_documents[0],
        original_dependencies=original_documents[1],
        execution_document=document_raw,
        execution_dependencies=dependencies_raw,
        manifest=manifest,
        manifest_raw=manifest_raw,
        report=report,
        report_raw=report_raw,
        compiler_runs=(first, first),
        view=view,
        view_raw=view_raw,
        diagnostics=copy.deepcopy(report["diagnostics"]),
        recoveries=copy.deepcopy(report["recoveryActions"]),
        preflight_raw=preflight,
        preparation_raw=preparation,
        source_entries=entries,
        source_proofs=proofs,
        source_wavs=wavs,
        source_paths=source_paths,
        tracked_paths=states,
        tracked_hashes=hashes,
        tracked_links={},
        proof_payloads=payloads,
        attestation_path=attestation_path,
        existing=existing,
    )


def _load_verified_admission_cache(
    admission_path: Path, admission_raw: bytes, record: Json
) -> QualificationOutputAdmissionV2:
    """Reopen a fixed verified projection without rerunning compiler/media tools."""
    _need(
        set(record)
        == {
            "schemaVersion",
            "profile",
            "disposition",
            "originalDocumentSha256",
            "originalDependenciesSha256",
            "executionDocumentSha256",
            "executionDependenciesSha256",
            "manifestSha256",
            "reportSha256",
            "viewSha256",
            "packageInventorySha256",
            "preflightSha256",
            "preparationSha256",
            "sourceProofs",
            "diagnostics",
            "recoveryActions",
            "creativeQualification",
        },
        "closed package admission required",
    )
    root = admission_path.parent / "package"
    _need(
        root.is_dir() and not root.is_symlink(),
        "materialized wrapper package missing",
    )
    cache_raw = _verify_admission_seal(admission_path, admission_raw, record)
    inventory_path = root / "package-inventory.json"
    inventory_raw = _read(inventory_path)
    inventory, recalculated_inventory_raw = _inventory(root)
    _need(
        inventory_raw == recalculated_inventory_raw
        and _sha(inventory_raw) == record["packageInventorySha256"],
        "admitted package inventory changed",
    )
    listed = {
        row["path"]: row
        for row in _array(inventory["files"], "package inventory files")
        if type(row) is dict and type(row.get("path")) is str
    }
    cache_path = root / _VERIFIED_ADMISSION_RELATIVE_PATH
    cache_row = listed.get(_VERIFIED_ADMISSION_RELATIVE_PATH)
    _need(
        type(cache_row) is dict and cache_row.get("sha256") == _sha(cache_raw),
        "verified admission cache is not inventory-bound",
    )
    (
        tracked_paths,
        tracked_hashes,
        tracked_links,
        cached_source_paths,
        source_proofs,
        source_entries,
        source_wav_hashes,
        proof_payloads,
    ) = _parse_verification_cache(
        cache_raw, profile=record["profile"], package_root=root
    )
    fixed_paths = {
        "Original/script-document-v2.json": "originalDocumentSha256",
        "Original/compiler-dependencies-v2.json": "originalDependenciesSha256",
        "Execution/script-document-v2.json": "executionDocumentSha256",
        "Execution/compiler-dependencies-v2.json": "executionDependenciesSha256",
        "Compiler/timeline-manifest-v2.json": "manifestSha256",
        "Compiler/build-report-v2.json": "reportSha256",
        "Compiler/compile-1.json": None,
        "Compiler/compile-2.json": None,
        "Delivery/delivery-view.json": "viewSha256",
        "Qualification/preflight.json": "preflightSha256",
        "Qualification/preparation-snapshot.json": "preparationSha256",
    }
    retained: dict[str, bytes] = {}
    for relative, admission_field in fixed_paths.items():
        raw = _read(root / relative)
        if admission_field is not None:
            _need(
                _sha(raw) == record[admission_field],
                f"retained {relative} hash differs",
            )
        retained[relative] = raw
    if record["profile"] == R16_PROFILE:
        _pin_r16_vector(
            retained["Compiler/timeline-manifest-v2.json"],
            _R16_MANIFEST_SHA256,
            "manifest",
        )
        _pin_r16_vector(
            retained["Compiler/build-report-v2.json"],
            _R16_REPORT_SHA256,
            "report",
        )
        _pin_r16_vector(
            retained["Compiler/compile-1.json"],
            _R16_COMPILE_ONE_SHA256,
            "compile-1",
        )
        _pin_r16_vector(
            retained["Compiler/compile-2.json"],
            _R16_COMPILE_TWO_SHA256,
            "compile-2",
        )
    document = _json(retained["Execution/script-document-v2.json"], "R16 document")
    dependencies = _json(
        retained["Execution/compiler-dependencies-v2.json"],
        "R16 execution dependencies",
    )
    manifest = _json(retained["Compiler/timeline-manifest-v2.json"], "R16 manifest")
    report = _json(retained["Compiler/build-report-v2.json"], "R16 report")
    view = _json(retained["Delivery/delivery-view.json"], "delivery view")
    compile_one = _json(retained["Compiler/compile-1.json"], "compile-1")
    compile_two = _json(retained["Compiler/compile-2.json"], "compile-2")
    if record["profile"] in _PUBLIC_PROFILES:
        report_diagnostics = report.get("diagnostics")
        report_recoveries = report.get("recoveryActions")
        _need(
            type(report_diagnostics) is list
            and type(report_recoveries) is list
            and record["diagnostics"] == report_diagnostics
            and record["recoveryActions"] == report_recoveries,
            "public admission diagnostic rows differ from the full report",
        )
        if record["profile"] == SYNTHETIC_PROFILE:
            _need(
                report_diagnostics == [] and report_recoveries == [],
                "ordinary synthetic package diagnostics refuse",
            )
        else:
            try:
                validate_temporary_presenter_report(document, manifest, report)
            except OutputConsistencyError as error:
                raise QualificationPackageError(str(error)) from error
    if record["profile"] == R16_PROFILE:
        _validate_r16_duration(manifest)
        _need(compile_one == compile_two, "retained compiler runs differ")
        _canonical_r16_report(document, dependencies, manifest, report, compile_one)
        _validate_scoped_r16_inputs(document, dependencies, manifest, report)
    elif record["profile"] == PRESENTER_PROFILE:
        _need(compile_one == compile_two, "retained Presenter compiler runs differ")
        _need(
            compile_one.get("result", {}).get("manifest") == manifest
            and compile_one.get("result", {}).get("report") == report
            and compile_one["result"].get("manifestJson", "").encode()
            == retained["Compiler/timeline-manifest-v2.json"]
            and compile_one["result"].get("reportJson", "").encode()
            == retained["Compiler/build-report-v2.json"],
            "retained Presenter compiler envelope differs from emitted output",
        )
        _presenter_report(document, manifest, report)
        _validate_scoped_r16_inputs(document, dependencies, manifest, report)
    _need(
        type(view.get("sources")) is list
        and set(cached_source_paths)
        == {row.get("id") for row in view["sources"] if type(row) is dict},
        "verified source path inventory differs",
    )
    source_paths: dict[str, Path] = {}
    source_root = (
        root / "PublicPackage" if record["profile"] in _PUBLIC_PROFILES else root
    )
    for source in view["sources"]:
        row = _object(source, "delivery source")
        source_id = _text(row.get("id"), "delivery source id required")
        relative = _text(row.get("path"), "delivery source path required")
        expected = source_root / relative
        _need(
            cached_source_paths[source_id] == expected
            and expected.is_file()
            and not expected.is_symlink(),
            "verified source path differs from delivery view",
        )
        source_paths[source_id] = expected
    source_wavs: dict[str, bytes] = {}
    source_audio_events = {
        row["eventId"]: row
        for row in manifest["events"]
        if row["kind"] == "source_audio"
    }
    for source_id, expected_hash in source_wav_hashes.items():
        path = source_paths[source_id]
        event = source_audio_events.get(source_id)
        if event is not None:
            proof_record = _json(source_proofs[source_id].record, "source audio proof")
            path = _prediction_audio_path(manifest, event, proof_record["audio"], path)
        raw = _read(path, maximum=_MAX_WAV)
        _need(
            _sha(raw) == expected_hash,
            f"verified source WAV changed: {source_id}",
        )
        source_wavs[source_id] = raw
    proof_inventory = {
        row["sourceId"]: row
        for row in _array(record["sourceProofs"], "admitted source proofs")
        if type(row) is dict and type(row.get("sourceId")) is str
    }
    _need(
        set(proof_inventory) == set(source_proofs),
        "verified source proof inventory differs",
    )
    for source_id, proof in source_proofs.items():
        row = proof_inventory[source_id]
        _need(
            row["recordSha256"] == _sha(proof.record)
            and row["receiptSha256"] == _sha(proof.receipt)
            and row["timingSha256"]
            == (_sha(proof.timing) if proof.timing is not None else None)
            and row["reviewSha256"]
            == (_sha(proof.review) if proof.review is not None else None)
            and row["wavSha256"] == _sha(source_wavs[source_id]),
            "verified source proof bytes differ",
        )
    _need(
        {row.get("sourceId") for row in source_entries if type(row) is dict}
        == set(source_proofs),
        "verified source entries differ",
    )
    for (_kind, receipt_hash), payloads in proof_payloads.items():
        _need(
            any(_sha(proof.receipt) == receipt_hash for proof in source_proofs.values())
            and all(type(payload) is dict for payload in payloads),
            "verified proof payloads are not receipt-bound",
        )
    blobs = {
        "originalDocumentSha256": retained["Original/script-document-v2.json"],
        "originalDependenciesSha256": retained[
            "Original/compiler-dependencies-v2.json"
        ],
        "executionDocumentSha256": retained["Execution/script-document-v2.json"],
        "executionDependenciesSha256": retained[
            "Execution/compiler-dependencies-v2.json"
        ],
        "manifestSha256": retained["Compiler/timeline-manifest-v2.json"],
        "reportSha256": retained["Compiler/build-report-v2.json"],
        "packageSha256": retained["Delivery/delivery-view.json"],
        "preflightSha256": retained["Qualification/preflight.json"],
        "preparationSha256": retained["Qualification/preparation-snapshot.json"],
    }
    tracked_paths[cache_path] = _state(cache_path)
    tracked_hashes[cache_path] = _sha(cache_raw)
    tracked_paths[inventory_path] = _state(inventory_path)
    tracked_hashes[inventory_path] = _sha(inventory_raw)
    tracked_paths[admission_path] = _state(admission_path)
    tracked_hashes[admission_path] = _sha(admission_raw)
    seal_path = admission_path.parent / _ADMISSION_SEAL_FILENAME
    seal_raw = _read(seal_path)
    tracked_paths[seal_path] = _state(seal_path)
    tracked_hashes[seal_path] = _sha(seal_raw)
    if record["profile"] in {R16_PROFILE, PRESENTER_PROFILE}:
        attestation_path = admission_path
        attestation_sha256 = _sha(admission_raw)
    else:
        attestation_path = admission_path.parent / "attestation.json"
        _need(
            attestation_path.is_file() and not attestation_path.is_symlink(),
            "#177 attestation is not a regular file",
        )
        attestation_sha256 = _sha(_read(attestation_path, maximum=16 * 1024 * 1024))
        _need(
            tracked_hashes.get(attestation_path) == attestation_sha256,
            "#177 attestation currentness is not retained",
        )
    return QualificationOutputAdmissionV2(
        profile=record["profile"],
        disposition=record["disposition"],
        view=copy.deepcopy(view),
        manifest=copy.deepcopy(manifest),
        report=copy.deepcopy(report),
        diagnostics=tuple(copy.deepcopy(record["diagnostics"])),
        recovery_actions=tuple(copy.deepcopy(record["recoveryActions"])),
        blobs=blobs,
        source_wavs=source_wavs,
        source_proofs=source_proofs,
        source_entries=source_entries,
        source_paths=source_paths,
        package_root=root,
        admission_path=admission_path,
        attestation_path=attestation_path,
        attestation_sha256=attestation_sha256,
        original_document_path=root / "Original/script-document-v2.json",
        original_dependencies_path=root / "Original/compiler-dependencies-v2.json",
        execution_document_path=root / "Execution/script-document-v2.json",
        execution_dependencies_path=root / "Execution/compiler-dependencies-v2.json",
        raw_snapshots=blobs,
        admission=copy.deepcopy(record),
        view_raw=retained["Delivery/delivery-view.json"],
        manifest_raw=retained["Compiler/timeline-manifest-v2.json"],
        report_raw=retained["Compiler/build-report-v2.json"],
        _tracked_paths=tracked_paths,
        _tracked_hashes=tracked_hashes,
        _tracked_links=tracked_links,
        _proof_payloads=proof_payloads,
    )


@_admission_boundary
def _load_qualification_package_v2(
    admission_path: Path, expected_sha256: str
) -> QualificationOutputAdmissionV2:
    """Reauthenticate the fixed package projection without a currentness scan."""
    _need(
        admission_path.is_absolute()
        and admission_path.name == "qualification-output-package-admission.json",
        "owned admission path required",
    )
    v2_package._require_path_components_no_symlink(
        admission_path, "qualification admission"
    )
    raw = _read(admission_path)
    _need(_sha(raw) == expected_sha256, "admission raw pin differs")
    record = _json(raw, "package admission")
    _need(
        record.get("schemaVersion") == ADMISSION_SCHEMA
        and record.get("profile") in _PROFILES,
        "unsupported package admission",
    )
    admission = _load_verified_admission_cache(admission_path, raw, record)
    _need(
        _read(admission.admission_path) == raw and admission.admission == record,
        "reconstructed admission differs",
    )
    return admission


@_admission_boundary
def load_qualification_package_v2(
    admission_path: Path, expected_sha256: str
) -> QualificationOutputAdmissionV2:
    """Reauthenticate fixed wrapper/currentness bytes and reopen its proof cache."""
    admission = _load_qualification_package_v2(admission_path, expected_sha256)
    admission.assert_current()
    return admission


def _finish_admission(
    output_root: Path,
    *,
    profile: str,
    disposition: str,
    creative_qualification: str,
    original_document: bytes,
    original_dependencies: bytes,
    execution_document: bytes,
    execution_dependencies: bytes,
    manifest: Json,
    manifest_raw: bytes,
    report: Json,
    report_raw: bytes,
    compiler_runs: tuple[bytes, bytes],
    view: Json,
    view_raw: bytes,
    diagnostics: list[Json],
    recoveries: list[Json],
    preflight_raw: bytes,
    preparation_raw: bytes,
    source_entries: list[Json],
    source_proofs: Mapping[str, SourceProof],
    source_wavs: Mapping[str, bytes],
    source_paths: Mapping[str, Path],
    tracked_paths: dict[Path, tuple[int, int, int, int, int]],
    tracked_hashes: dict[Path, str],
    tracked_links: dict[Path, tuple[str, Path]],
    proof_payloads: Mapping[tuple[str, str], tuple[Json, ...]],
    attestation_path: Path | None = None,
    existing: bool = False,
) -> QualificationOutputAdmissionV2:
    root = output_root / "package"
    _need(
        root.is_dir() and not root.is_symlink(),
        "materialized wrapper package root required",
    )
    _need(_json(view_raw, "delivery view") == view, "delivery view bytes differ")
    fixed = {
        "Original/script-document-v2.json": original_document,
        "Original/compiler-dependencies-v2.json": original_dependencies,
        "Execution/script-document-v2.json": execution_document,
        "Execution/compiler-dependencies-v2.json": execution_dependencies,
        "Compiler/timeline-manifest-v2.json": manifest_raw,
        "Compiler/build-report-v2.json": report_raw,
        "Compiler/compile-1.json": compiler_runs[0],
        "Compiler/compile-2.json": compiler_runs[1],
        "Delivery/delivery-view.json": view_raw,
        "Qualification/preflight.json": preflight_raw,
        "Qualification/preparation-snapshot.json": preparation_raw,
    }
    for relative, raw in fixed.items():
        _retain(
            root / relative,
            raw,
            existing=existing
            or (profile == PRESENTER_PROFILE and relative.startswith("Execution/")),
        )
    for source_id, source_path in source_paths.items():
        view_source = next(item for item in view["sources"] if item["id"] == source_id)
        _need(
            source_path.is_file() and not source_path.is_symlink(),
            "source media path must be a regular materialized file",
        )
        _need(
            _hash_file(source_path)
            == view_source["contentHash"].removeprefix("sha256:"),
            "materialized source media hash differs",
        )
    if profile in {R16_PROFILE, PRESENTER_PROFILE}:
        _need(
            attestation_path is None,
            "R16 admission is its native attestation reference",
        )
        chosen_attestation = output_root / "qualification-output-package-admission.json"
    elif profile in _PUBLIC_PROFILES:
        _need(
            attestation_path is not None,
            "ordinary profile requires an authentic #177 attestation",
        )
        assert attestation_path is not None
        chosen_attestation = attestation_path
    else:
        raise QualificationPackageError("unsupported package profile")
    _retain_verification_blobs(
        root,
        source_proofs,
        proof_payloads,
        existing=existing,
    )
    package_states = {
        path: state
        for path, state in _directory_states(root).items()
        if not path.is_dir()
    }
    package_hashes = {
        path: _hash_file(path)
        for path in package_states
        if path.is_file() and not path.is_symlink()
    }
    tracked_paths.update(package_states)
    tracked_hashes.update(package_hashes)
    if profile in _PUBLIC_PROFILES:
        _need(
            chosen_attestation.is_file() and not chosen_attestation.is_symlink(),
            "#177 attestation is not a regular file",
        )
        tracked_paths[chosen_attestation] = _state(chosen_attestation)
        tracked_hashes[chosen_attestation] = _sha(
            _read(chosen_attestation, maximum=16 * 1024 * 1024)
        )
    cache_path = root / _VERIFIED_ADMISSION_RELATIVE_PATH
    cache_raw = _verification_cache_raw(
        profile=profile,
        package_root=root,
        tracked_paths=tracked_paths,
        tracked_hashes=tracked_hashes,
        tracked_links=tracked_links,
        source_paths=source_paths,
        source_proofs=source_proofs,
        source_entries=source_entries,
        source_wavs=source_wavs,
        proof_payloads=proof_payloads,
    )
    _retain(cache_path, cache_raw, existing=existing)
    tracked_paths[cache_path] = _state(cache_path)
    tracked_hashes[cache_path] = _sha(cache_raw)
    _, inventory_raw = _inventory(root)
    _retain(root / "package-inventory.json", inventory_raw, existing=existing)
    inventory_sha = _sha(inventory_raw)
    proof_inventory = _source_proof_inventory(
        source_entries, source_proofs, source_wavs
    )
    record = {
        "schemaVersion": ADMISSION_SCHEMA,
        "profile": profile,
        "disposition": disposition,
        "originalDocumentSha256": _sha(original_document),
        "originalDependenciesSha256": _sha(original_dependencies),
        "executionDocumentSha256": _sha(execution_document),
        "executionDependenciesSha256": _sha(execution_dependencies),
        "manifestSha256": _sha(manifest_raw),
        "reportSha256": _sha(report_raw),
        "viewSha256": _sha(view_raw),
        "packageInventorySha256": inventory_sha,
        "preflightSha256": _sha(preflight_raw),
        "preparationSha256": _sha(preparation_raw),
        "sourceProofs": proof_inventory,
        "diagnostics": diagnostics,
        "recoveryActions": recoveries,
        "creativeQualification": creative_qualification,
    }
    admission_path = output_root / "qualification-output-package-admission.json"
    admission_raw = _canonical(record)
    _retain(admission_path, admission_raw, existing=existing)
    if profile in _PUBLIC_PROFILES:
        _need(
            chosen_attestation.is_file() and not chosen_attestation.is_symlink(),
            "#177 attestation is not a regular file",
        )
        attestation_sha256 = _sha(_read(chosen_attestation, maximum=16 * 1024 * 1024))
    else:
        attestation_sha256 = _sha(admission_raw)
    blobs = {
        "originalDocumentSha256": original_document,
        "originalDependenciesSha256": original_dependencies,
        "executionDocumentSha256": execution_document,
        "executionDependenciesSha256": execution_dependencies,
        "manifestSha256": manifest_raw,
        "reportSha256": report_raw,
        "packageSha256": view_raw,
        "preflightSha256": preflight_raw,
        "preparationSha256": preparation_raw,
    }
    tracked_paths[admission_path] = _state(admission_path)
    tracked_hashes[admission_path] = _sha(admission_raw)
    if profile in _PUBLIC_PROFILES:
        tracked_paths[chosen_attestation] = _state(chosen_attestation)
        tracked_hashes[chosen_attestation] = attestation_sha256
    admission = QualificationOutputAdmissionV2(
        profile=profile,
        disposition=disposition,
        view=copy.deepcopy(view),
        manifest=copy.deepcopy(manifest),
        report=copy.deepcopy(report),
        diagnostics=tuple(copy.deepcopy(diagnostics)),
        recovery_actions=tuple(copy.deepcopy(recoveries)),
        blobs=blobs,
        source_wavs=dict(source_wavs),
        source_proofs=dict(source_proofs),
        source_entries=copy.deepcopy(source_entries),
        source_paths=dict(source_paths),
        package_root=root,
        admission_path=admission_path,
        attestation_path=chosen_attestation,
        attestation_sha256=attestation_sha256,
        original_document_path=root / "Original/script-document-v2.json",
        original_dependencies_path=root / "Original/compiler-dependencies-v2.json",
        execution_document_path=root / "Execution/script-document-v2.json",
        execution_dependencies_path=root / "Execution/compiler-dependencies-v2.json",
        raw_snapshots=blobs,
        admission=record,
        view_raw=view_raw,
        manifest_raw=manifest_raw,
        report_raw=report_raw,
        _tracked_paths=tracked_paths,
        _tracked_hashes=tracked_hashes,
        _tracked_links=tracked_links,
        _proof_payloads=proof_payloads,
    )
    tracked_paths[output_root] = _state(output_root)
    admission.assert_current()
    seal_path, seal_raw = _publish_admission_seal(
        profile=profile,
        admission_path=admission_path,
        cache_path=cache_path,
        admission_raw=admission_raw,
        cache_raw=cache_raw,
        record=record,
        existing=existing,
    )
    tracked_paths[seal_path] = _state(seal_path)
    tracked_hashes[seal_path] = _sha(seal_raw)
    # Publishing the sidecar changes the private output directory identity.
    tracked_paths[output_root] = _state(output_root)
    admission.assert_current()
    return admission


def _copy_exclusive(source: Path, destination: Path, expected_hash: str) -> int:
    _need(
        source.is_absolute() and source.is_file() and not source.is_symlink(),
        "regular materialization source required",
    )
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    source_fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    destination_fd = os.open(
        destination,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with (
            os.fdopen(source_fd, "rb") as incoming,
            os.fdopen(destination_fd, "wb") as outgoing,
        ):
            before = os.fstat(incoming.fileno())
            for block in iter(lambda: incoming.read(1024 * 1024), b""):
                digest.update(block)
                size += len(block)
                outgoing.write(block)
            outgoing.flush()
            os.fsync(outgoing.fileno())
            after = os.fstat(incoming.fileno())
            _need(
                (
                    before.st_dev,
                    before.st_ino,
                    before.st_size,
                    before.st_mtime_ns,
                    before.st_ctime_ns,
                )
                == (
                    after.st_dev,
                    after.st_ino,
                    after.st_size,
                    after.st_mtime_ns,
                    after.st_ctime_ns,
                ),
                "materialized source changed during copy",
            )
            _need(
                digest.hexdigest() == expected_hash,
                f"materialized source hash differs: {source.name}",
            )
            os.fchmod(outgoing.fileno(), 0o400)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return size


def _write_exclusive(path: Path, raw: bytes) -> int:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
        os.fchmod(stream.fileno(), 0o400)
    return len(raw)


def _inventory(root: Path) -> tuple[Json, bytes]:
    rows: list[Json] = []
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        here = Path(current)
        for name in dirs:
            _need(
                not (here / name).is_symlink(),
                "package directory symlinks are forbidden",
            )
        for name in files:
            path = here / name
            _need(
                not path.is_symlink() and path.is_file(),
                "package files must be regular",
            )
            rel = path.relative_to(root).as_posix()
            if rel == "package-inventory.json":
                continue
            rows.append(
                {"path": rel, "sha256": _hash_file(path), "size": path.stat().st_size}
            )
    rows.sort(key=lambda row: row["path"])
    value = {"schemaVersion": INVENTORY_SCHEMA, "files": rows}
    raw = _canonical(value)
    return value, raw


def _directory_states(root: Path) -> dict[Path, tuple[int, int, int, int, int]]:
    result: dict[Path, tuple[int, int, int, int, int]] = {}
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        here = Path(current)
        for name in dirs:
            path = here / name
            _need(
                not path.is_symlink(),
                "materialized package contains a symlink directory",
            )
            result[path] = _state(path)
        for name in files:
            path = here / name
            _need(not path.is_symlink(), "materialized package contains a symlink file")
            result[path] = _state(path)
    return result
