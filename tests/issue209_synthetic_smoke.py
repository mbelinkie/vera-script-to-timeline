"""Build one real-media, public-package input for the #209 synthetic smoke.

The helper reads the approved R16 inputs, writes a one-block derivative under a
caller-owned temporary root, recompiles it with the pinned compiler runtime,
and admits it only through the unchanged ordinary v2 package writer.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from vera_timeline_agent.v2_package import (
    V2PackageResult,
    _compiler_hash,
    build_v2_package,
    verify_v2_package,
)

Json = dict[str, Any]

_PRIVATE = Path(
    "/Users/matthewbelinkie/Library/Application Support/VERA/private-preparation"
)
_CANDIDATE = _PRIVATE / "issue-148/2026-10-11-r16-producer-review/candidate-inputs"
_PARENT = (
    _PRIVATE / "issue-145/advance-inputs/issue209-r16-preparation-cn209p1-attempt02"
)
_MEDIA_PREPARATION = _PARENT / "media-preparation/published"
_ORIGINAL_DOCUMENT = _CANDIDATE / "script-document-v2.json"
_ORIGINAL_DOCUMENT_TARGET = (
    _PRIVATE
    / "issue-148/2026-10-11-r15-heroes-base-binding/attempt-01/candidate-inputs"
    / "script-document-v2.json"
)
_ORIGINAL_DEPENDENCIES = _CANDIDATE / "compiler-dependencies-v2.json"
_ORIGINAL_DEPENDENCIES_TARGET = _ORIGINAL_DOCUMENT_TARGET.with_name(
    "compiler-dependencies-v2.json"
)
_EXECUTION_DOCUMENT = (
    _PARENT / "parent-admission/original-script-document-byte-identical.json"
)
_EXECUTION_DEPENDENCIES = _PARENT / "execution-compiler-dependencies-v2.json"
_CONTRACTS = Path(__file__).resolve().parents[1] / "packages/contracts/src"
_COMPILER_CORE = _CONTRACTS / "compiler-core-v2.ts"
_COMPILER_CLI = _CONTRACTS / "issue-190-compile-cli.ts"
_NODE = Path(
    "/Users/matthewbelinkie/.local/share/vera/toolchains/node-v24.19.0-darwin-x64/bin/node"
)

_ORIGINAL_DOCUMENT_SHA256 = (
    "27b9d5ddfb097f254d44ce0b6428e461f9e948010e95e1a4c817a8c71e76fa71"
)
_ORIGINAL_DEPENDENCIES_SHA256 = (
    "19c4e7f4777afbd756a67dbb558d73bd87a705c38c1d1dc3d2e330436f8876a9"
)
_EXECUTION_DEPENDENCIES_SHA256 = (
    "ca837b3d46b07d3c431bf923c3c99629f21777872ff1bbabd0bbca6834f48780"
)
_PREPARATION_KEY = (
    "sha256:d5de45ebbb30d42ac16f255403c9208231a4ddf80d99cd9c50449beb24bce012"
)
_PREPARATION_SHA256 = "4a122af7bfcce381c46b914bed78bf05146aafc6cc69663a0d1c4fd7ee3b98f9"
_CHECKSUM_SHA256 = "7e98cccefc1d476bf88ccdc7ad9bde3746afd319b041d95d4564aeb13afba286"
_REQUEST_SHA256 = "ca4600d2fb52ed67a2d38229d90cb1d89e6ccd414f85af748d7f34b18d73e39a"
_PREPARED_AUDIO_SHA256 = (
    "3b8b7b75145c5b2e3a2fe6243f057076197e846c8329c9c415cdbfb1e401b909"
)
_SOURCE_VIDEO_SHA256 = (
    "8a39e2e1b72658aa21db549e8953b9df81c54996bd6ae155d0756adb0d848027"
)
_SOURCE_AUDIO_SHA256 = (
    "4f437ffcd062f754ea45e0ea91178c2df032359e046357dbd5a7fccab3c347cf"
)
_PRESENTER_STILL_SHA256 = (
    "cdf03e55adafd244e6d5bd926c1510b19cf327d3d29052ec283f2298e4db6c36"
)
_COMPILER_SOURCE_SHA256 = (
    "9fdf3929143a2f3787f94ae9878c607dcc08381265b65bda825807d8f8bd06ea"
)
_COMPILER_PROFILE_SHA256 = (
    "3b3d1c42548531eb0448cedf504e140316b9e318e4a18bee805d77a48f7fecf6"
)
_VISUAL_BLOCK_ID = "e0bdf8f4-c3f0-5aa3-a17d-a21c5623b15a"
_PAYLOAD_ID = "a087d3f2-626d-59a5-a4a8-6540ffbf3ade"
_SOURCE_REFERENCE_ID = "08df60e1-a34f-58ce-a6cf-f647b0dd288f"
_FRAME_COUNT = 111
_SAMPLE_COUNT = 222222


@dataclass(frozen=True)
class SyntheticSmokeCase:
    """Paths and identity for one freshly compiled ordinary v2 package."""

    original_document_path: Path
    original_dependencies_path: Path
    execution_document_path: Path
    execution_dependencies_path: Path
    document_path: Path
    dependencies_path: Path
    manifest_path: Path
    report_path: Path
    package_root: Path
    preparation_paths: dict[str, Path]
    media_paths: dict[str, Path]
    build: V2PackageResult


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        info.st_mode,
    )


def _read_pinned(
    path: Path,
    expected_sha256: str,
    *,
    symlink_target: Path | None = None,
    maximum: int = 8 * 1024 * 1024,
) -> bytes:
    """Read one exact retained input while checking its filesystem identity."""
    try:
        path_before = path.lstat()
        if symlink_target is None:
            if not stat.S_ISREG(path_before.st_mode):
                raise ValueError("regular retained input required")
            read_path = path
        else:
            if (
                not stat.S_ISLNK(path_before.st_mode)
                or Path(os.readlink(path)) != symlink_target
                or path.resolve(strict=True) != symlink_target
            ):
                raise ValueError("approved original link changed")
            read_path = symlink_target
        descriptor = os.open(read_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            raw = stream.read(maximum + 1)
            after = os.fstat(stream.fileno())
        path_after = path.lstat()
        if _identity(before) != _identity(after) or _identity(path_before) != _identity(
            path_after
        ):
            raise ValueError("retained input changed while being read")
        if len(raw) > maximum or _hash(raw) != expected_sha256:
            raise ValueError("retained input hash differs from its approved pin")
        if symlink_target is not None and path.resolve(strict=True) != symlink_target:
            raise ValueError("approved original link target changed")
        return raw
    except (OSError, RuntimeError) as error:
        raise ValueError(f"approved input is unavailable: {path.name}") from error


def _verify_pinned_file(path: Path, expected_sha256: str) -> None:
    """Verify a large media input without loading it all into memory."""
    try:
        path_before = path.lstat()
        if not stat.S_ISREG(path_before.st_mode) or path_before.st_size > 1024**3:
            raise ValueError("approved media input is not a bounded regular file")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        digest = hashlib.sha256()
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
            after = os.fstat(stream.fileno())
        path_after = path.lstat()
        if (
            _identity(before) != _identity(after)
            or _identity(path_before) != _identity(path_after)
            or digest.hexdigest() != expected_sha256
        ):
            raise ValueError("approved media input changed or differs from its pin")
    except (OSError, RuntimeError) as error:
        raise ValueError(f"approved media input is unavailable: {path.name}") from error


def _json(raw: bytes, label: str) -> Json:
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label} JSON") from error
    if type(value) is not dict:
        raise ValueError(f"invalid {label} object")
    return value


def _write_exclusive(path: Path, raw: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _uuid(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"vera:#209-synthetic-smoke:v1:{label}"))


def _source_path(binding: Json) -> Path:
    locator = binding.get("artifactLocator")
    parsed = urlparse(locator) if isinstance(locator, str) else None
    if (
        parsed is None
        or parsed.scheme != "file"
        or parsed.netloc not in ("", "localhost")
    ):
        raise ValueError("approved prepared source must use its local file locator")
    path = Path(unquote(parsed.path))
    approved = _PRIVATE / "issue-148/2026-10-08-r1/conversions"
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ValueError("approved prepared source is unavailable") from error
    if resolved.parent != approved or path.is_symlink() or not resolved.is_file():
        raise ValueError("prepared source is outside the approved source directory")
    return resolved


def _run_compiler(document_path: Path, dependencies_path: Path) -> bytes:
    if not _NODE.is_file() or _NODE.is_symlink() or not _COMPILER_CLI.is_file():
        raise ValueError("pinned compiler runtime is unavailable")
    version = subprocess.run(
        [str(_NODE), "--version"],
        capture_output=True,
        timeout=5,
        check=False,
        env={"LANG": "C", "LC_ALL": "C", "PATH": str(_NODE.parent)},
    )
    if (
        version.returncode != 0
        or version.stdout.strip() != b"v24.19.0"
        or version.stderr
    ):
        raise ValueError("pinned Node 24.19.0 runtime check failed")
    result = subprocess.run(
        [str(_NODE), str(_COMPILER_CLI), str(document_path), str(dependencies_path)],
        capture_output=True,
        timeout=45,
        check=False,
        env={"LANG": "C", "LC_ALL": "C", "PATH": str(_NODE.parent)},
    )
    if result.returncode != 0 or result.stderr:
        raise ValueError("pinned compiler refused the fresh synthetic inputs")
    return result.stdout


def prepare_synthetic_smoke(output_root: Path) -> SyntheticSmokeCase:
    """Build a 111-frame package from one authenticated #174 clip occurrence.

    The function never writes into the retained candidate or parent-admission
    directories. Its output root must be new and outside the repository.
    """
    if not isinstance(output_root, Path) or not output_root.is_absolute():
        raise ValueError("absolute synthetic output root required")
    resolved_root = output_root.resolve(strict=False)
    repository_root = Path(__file__).resolve().parents[1]
    if repository_root == resolved_root or repository_root in resolved_root.parents:
        raise ValueError("synthetic output root must be outside the repository")
    if resolved_root == _PRIVATE or _PRIVATE in resolved_root.parents:
        raise ValueError(
            "synthetic output root must be outside retained private inputs"
        )
    if output_root.exists() or output_root.is_symlink():
        raise ValueError("synthetic output root must be new")

    original_document_raw = _read_pinned(
        _ORIGINAL_DOCUMENT,
        _ORIGINAL_DOCUMENT_SHA256,
        symlink_target=_ORIGINAL_DOCUMENT_TARGET,
    )
    original_dependencies_raw = _read_pinned(
        _ORIGINAL_DEPENDENCIES,
        _ORIGINAL_DEPENDENCIES_SHA256,
        symlink_target=_ORIGINAL_DEPENDENCIES_TARGET,
    )
    execution_document_raw = _read_pinned(
        _EXECUTION_DOCUMENT, _ORIGINAL_DOCUMENT_SHA256
    )
    execution_dependencies_raw = _read_pinned(
        _EXECUTION_DEPENDENCIES, _EXECUTION_DEPENDENCIES_SHA256
    )
    if execution_document_raw != original_document_raw:
        raise ValueError("retained execution document differs from its original")

    original = _json(original_document_raw, "original document")
    original_dependencies = _json(original_dependencies_raw, "original dependencies")
    execution_dependencies = _json(execution_dependencies_raw, "execution dependencies")
    if original_dependencies.get("schemaVersion") != "compiler-dependencies/v2":
        raise ValueError("approved original dependency schema changed")
    compiler = execution_dependencies.get("compiler")
    if (
        compiler
        != {
            "version": "compiler/v2",
            "sourceHash": f"sha256:{_COMPILER_SOURCE_SHA256}",
            "profileHash": f"sha256:{_COMPILER_PROFILE_SHA256}",
        }
        or _hash(_COMPILER_CORE.read_bytes()) != _COMPILER_SOURCE_SHA256
    ):
        raise ValueError("pinned compiler source or profile changed")

    block_rows = original.get("activeDraft", {}).get("blocks")
    if not isinstance(block_rows, list):
        raise ValueError("approved document has no active block list")
    selected_blocks = [
        row
        for row in block_rows
        if isinstance(row, dict) and row.get("id") == _VISUAL_BLOCK_ID
    ]
    if len(selected_blocks) != 1:
        raise ValueError("approved visual-only source block is missing or duplicated")
    block = copy.deepcopy(selected_blocks[0])
    if (
        block.get("type") != "visual_only"
        or block.get("payload", {}).get("payloadId") != _PAYLOAD_ID
        or block.get("payload", {}).get("source", {}).get("mediaReferenceId")
        != _SOURCE_REFERENCE_ID
        or block.get("payload", {}).get("audioPolicy") != "full"
        or block.get("visualOnlyTiming", {}).get("selectedSourceRange")
        != {"startFrame": 5809, "durationFrames": _FRAME_COUNT}
    ):
        raise ValueError("approved single-clip source selection changed")

    prepared_rows = execution_dependencies.get("preparedMedia")
    occurrence_rows = execution_dependencies.get("occurrenceResolutions")
    if not isinstance(prepared_rows, list) or not isinstance(occurrence_rows, list):
        raise ValueError("approved source dependency rows are missing")
    bindings = [
        row
        for row in prepared_rows
        if isinstance(row, dict) and row.get("requirementKey") == _PREPARATION_KEY
    ]
    occurrences = [
        row
        for row in occurrence_rows
        if isinstance(row, dict)
        and row.get("preparedMediaRequirementKey") == _PREPARATION_KEY
        and row.get("payloadId") == _PAYLOAD_ID
    ]
    if len(bindings) != 1 or len(occurrences) != 1:
        raise ValueError(
            "approved source binding or occurrence is missing or duplicated"
        )
    binding, occurrence = copy.deepcopy(bindings[0]), copy.deepcopy(occurrences[0])
    audio_streams = occurrence.get("sourceFrameMap", {}).get(
        "sourceAudioStreamMappings"
    )
    if (
        binding.get("mode") != "verified_reuse"
        or binding.get("originalSource", {}).get("contentHash")
        != f"sha256:{_SOURCE_VIDEO_SHA256}"
        or binding.get("verification", {}).get("deliveredHash")
        != f"sha256:{_SOURCE_VIDEO_SHA256}"
        or binding.get("requestedRange", {}).get("sourceInFrame") != 5809
        or binding.get("requestedRange", {}).get("duration")
        != {"numerator": 37037, "denominator": 8000}
        or occurrence.get("owner")
        != {"kind": "visual_only_block", "blockId": _VISUAL_BLOCK_ID}
        or occurrence.get("mediaReferenceId") != _SOURCE_REFERENCE_ID
        or occurrence.get("selectedSourceRange")
        != {"startFrame": 5809, "endFrame": 5920}
        or not isinstance(audio_streams, list)
        or len(audio_streams) != 1
        or audio_streams[0].get("audioHash") != f"sha256:{_SOURCE_AUDIO_SHA256}"
    ):
        raise ValueError(
            "approved binding does not match the exact 111-frame source range"
        )

    preparation_root = _MEDIA_PREPARATION / _PREPARATION_KEY.removeprefix("sha256:")
    receipt_path = preparation_root / "receipt.json"
    checksum_path = preparation_root / "receipt-checksum.json"
    request_path = preparation_root / "request.json"
    audio_path = preparation_root / "audio.wav"
    receipt_raw = _read_pinned(receipt_path, _PREPARATION_SHA256)
    checksum_raw = _read_pinned(checksum_path, _CHECKSUM_SHA256)
    request_raw = _read_pinned(request_path, _REQUEST_SHA256)
    _read_pinned(audio_path, _PREPARED_AUDIO_SHA256, maximum=128 * 1024 * 1024)
    checksum_record = _json(checksum_raw, "preparation checksum")
    receipt_record = _json(receipt_raw, "preparation receipt")
    request_record = _json(request_raw, "preparation request")
    if (
        checksum_record.get("receiptHash") != f"sha256:{_hash(receipt_raw)}"
        or receipt_record.get("requirementKey") != _PREPARATION_KEY
        or receipt_record.get("binding") != binding
        or receipt_record.get("audio", {}).get("contentHash")
        != f"sha256:{_PREPARED_AUDIO_SHA256}"
        or receipt_record.get("audio", {}).get("decodedSamples") != _SAMPLE_COUNT
        or request_record.get("requirementKey") != _PREPARATION_KEY
        or request_record.get("authorizationReference")
        != binding.get("authorizationReference")
    ):
        raise ValueError("approved #174 receipt, checksum, request, or audio differs")

    source_path = _source_path(binding)
    _verify_pinned_file(source_path, _SOURCE_VIDEO_SHA256)
    presenter_still = original.get("scriptSettings", {}).get("presenterStillOverride")
    still_path = _CANDIDATE / "Media/base-picture.jpg"
    _read_pinned(still_path, _PRESENTER_STILL_SHA256)
    if presenter_still != {
        "artifactId": "5d866b35-7b13-55e6-a6d3-55f69626de3a",
        "artifactVersion": 1,
        "contentHash": f"sha256:{_PRESENTER_STILL_SHA256}",
        "height": 2160,
        "mediaReferenceId": "c6dc3a2a-b338-5119-a42d-55ae7c9475af",
        "projectRelativeLocator": "Media/base-picture.jpg",
        "provenance": {
            "origin": "local_import",
            "originalFilename": "base-picture.jpg",
        },
        "width": 3840,
    }:
        raise ValueError("approved explicit presenter still changed")

    document = copy.deepcopy(original)
    document["id"] = _uuid("document")
    document["projectId"] = _uuid("project")
    document["title"] = "Issue 209 verified source-audio smoke"
    document["activeDraft"]["blocks"] = [block]
    document["activeDraft"]["supportingItems"] = []
    document["extras"] = []
    document["ideaOutline"] = []
    document["liveContentHash"] = _compiler_hash(
        {key: value for key, value in document.items() if key != "liveContentHash"}
    )

    dependencies = copy.deepcopy(execution_dependencies)
    dependencies["preparedMedia"] = [binding]
    dependencies["occurrenceResolutions"] = [occurrence]
    dependencies["narrationBoundaryEvidence"] = []
    dependencies["narrationTimingMaps"] = []
    dependencies["presenterAlignmentResolutions"] = []
    dependencies["authoringDefaults"]["presenterStill"] = presenter_still
    dependencies["authoringDefaults"]["settingsHash"] = _compiler_hash(
        document["scriptSettings"]
    )
    dependencies["timeline"]["durationFrames"] = _FRAME_COUNT
    dependencies["build"]["buildId"] = _uuid("build")
    dependencies["build"]["manifestId"] = _uuid("manifest")
    dependencies["build"]["reportId"] = _uuid("report")
    text_hash = f"sha256:{_hash(b'')}"
    dependencies["document"].update(
        {
            "documentId": document["id"],
            "projectId": document["projectId"],
            "liveHeadSequence": document["liveHeadSequence"],
            "contentHash": document["liveContentHash"],
            "textHash": text_hash,
            "settingsHash": dependencies["authoringDefaults"]["settingsHash"],
        }
    )

    output_root.mkdir(mode=0o700, parents=True)
    input_root = output_root / "compiler-inputs"
    document_path = input_root / "script-document-v2.json"
    dependencies_path = input_root / "compiler-dependencies-v2.json"
    document_raw = json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    dependencies_raw = json.dumps(
        dependencies,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    _write_exclusive(document_path, document_raw)
    _write_exclusive(dependencies_path, dependencies_raw)

    first = _run_compiler(document_path, dependencies_path)
    second = _run_compiler(document_path, dependencies_path)
    if first != second:
        raise ValueError("fresh synthetic compiler output is not byte-identical")
    envelope = _json(first, "compiler output")
    result = envelope.get("result")
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise ValueError("pinned compiler did not produce a ready synthetic timeline")
    manifest_json = result.get("manifestJson")
    report_json = result.get("reportJson")
    if not isinstance(manifest_json, str) or not isinstance(report_json, str):
        raise ValueError(
            "pinned compiler output is missing canonical manifest or report"
        )
    manifest = _json(manifest_json.encode("utf-8"), "compiler manifest")
    report = _json(report_json.encode("utf-8"), "compiler report")
    if (
        manifest.get("timeline", {}).get("durationFrames") != _FRAME_COUNT
        or manifest.get("timeline", {}).get("frameRate")
        != {"numerator": 24000, "denominator": 1001}
        or manifest.get("timeline", {}).get("audioSampleRate") != 48000
        or len(manifest.get("events", [])) != 2
        or {event.get("kind") for event in manifest.get("events", [])}
        != {"primary_visual", "source_audio"}
        or report.get("status") != "ready"
        or report.get("diagnostics") != []
        or report.get("recoveryActions") != []
    ):
        raise ValueError("fresh compile differs from the bounded source-audio profile")
    source_audio = next(
        event for event in manifest["events"] if event["kind"] == "source_audio"
    )
    if (
        source_audio.get("audio", {}).get("audioPolicy") != "full"
        or source_audio.get("audio", {}).get("gainDb") != 0
        or source_audio.get("audio", {}).get("sampleRange")
        != {"startFrame": 11629618, "endFrame": 11851840}
    ):
        raise ValueError(
            "fresh source-audio event is not the approved full-gain sample range"
        )

    manifest_path = input_root / "timeline-manifest-v2.json"
    report_path = input_root / "build-report-v2.json"
    _write_exclusive(manifest_path, manifest_json.encode("utf-8"))
    _write_exclusive(report_path, report_json.encode("utf-8"))
    source_id = manifest["sources"][0]["id"]
    source_audio_events = [
        event for event in manifest["events"] if event["kind"] == "source_audio"
    ]
    if len(source_audio_events) != 1:
        raise ValueError("fresh compile did not emit one source-audio event")
    media_paths = {
        f"source:{source_id}": source_path,
        f"original:{source_id}": source_path,
        f"event:{source_audio_events[0]['eventId']}": audio_path,
    }
    preparation_paths = {_PREPARATION_KEY: receipt_path}
    package_root = output_root / "public-package"
    built = build_v2_package(
        manifest_path,
        report_path,
        document_path,
        dependencies_path,
        package_root,
        media_paths=media_paths,
        preparation_paths=preparation_paths,
    )
    if verify_v2_package(package_root).build_id != built.build_id:
        raise ValueError("ordinary v2 package verification returned a different build")

    for path, expected, target in (
        (_ORIGINAL_DOCUMENT, _ORIGINAL_DOCUMENT_SHA256, _ORIGINAL_DOCUMENT_TARGET),
        (
            _ORIGINAL_DEPENDENCIES,
            _ORIGINAL_DEPENDENCIES_SHA256,
            _ORIGINAL_DEPENDENCIES_TARGET,
        ),
        (_EXECUTION_DOCUMENT, _ORIGINAL_DOCUMENT_SHA256, None),
        (_EXECUTION_DEPENDENCIES, _EXECUTION_DEPENDENCIES_SHA256, None),
        (receipt_path, _PREPARATION_SHA256, None),
        (checksum_path, _CHECKSUM_SHA256, None),
        (request_path, _REQUEST_SHA256, None),
        (audio_path, _PREPARED_AUDIO_SHA256, None),
        (still_path, _PRESENTER_STILL_SHA256, None),
    ):
        _read_pinned(path, expected, symlink_target=target, maximum=128 * 1024 * 1024)
    _verify_pinned_file(source_path, _SOURCE_VIDEO_SHA256)

    return SyntheticSmokeCase(
        original_document_path=_ORIGINAL_DOCUMENT,
        original_dependencies_path=_ORIGINAL_DEPENDENCIES,
        execution_document_path=_EXECUTION_DOCUMENT,
        execution_dependencies_path=_EXECUTION_DEPENDENCIES,
        document_path=document_path,
        dependencies_path=dependencies_path,
        manifest_path=manifest_path,
        report_path=report_path,
        package_root=package_root,
        preparation_paths=preparation_paths,
        media_paths=media_paths,
        build=built,
    )
