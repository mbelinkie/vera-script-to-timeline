"""Installed stdlib-only native boundary for bounded output qualification.

This module deliberately has no dependency on the host controller, compiler,
predictor, decoder, or package builder. It accepts only closed immutable
records, verifies a one-use operator approval and executes a finite sequence
against the already-open, already-saved disposable target.
"""

from __future__ import annotations

import getpass
import hashlib
import hmac
import json
import os
import pwd
import stat
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .qualification_output_records_v2 import (
    COMMITMENT_FIELDS,
    CONTEXT_HASH_FIELDS,
    EMPTY_HEAD,
    LANE,
    RESERVATION_FIELDS,
    SOURCE_FIELDS,
    OutputConsistencyError,
    _canonical,
    _context,
    _digest,
    _identity,
    _integer,
    _list,
    _parse,
    _shape,
)

REQUEST_SCHEMA = "qualification-output-native-request/v1"
AUTHORITY_SCHEMA = "qualification-output-native-authority/v1"
INTENT_SCHEMA = "qualification-output-native-intent/v1"
RESULT_SCHEMA = "qualification-output-native-result/v1"
ADMISSION_SCHEMA = "qualification-output-package-admission/v1"
APPROVAL_SCHEMA = "qualification-output-operator-approval/v1"
RENDER_INTENT_SCHEMA = "qualification-output-render-intent/v1"
INVENTORY_SCHEMA = "qualification-output-package-inventory/v1"
SYNTHETIC_PROFILE = "verified-v2-package/v1"
R16_PROFILE = "qualification-output-r16-presenter-override/v1"
PROFILES = frozenset({SYNTHETIC_PROFILE, R16_PROFILE})
ACTIONS = frozenset(
    {
        "construct",
        "capture_pre",
        "save_reopen",
        "queue_render",
        "start_render",
        "poll_render",
        "capture_post",
    }
)
CONFIRMATIONS = {
    "savedDisposableNonproduction": True,
    "externalScripting": "None",
    "installReviewedRelease": True,
    "connectInjectedOnly": True,
}
MAX_BYTES = 8 * 1024 * 1024
MAX_LIFETIME_SECONDS = 1800
POLL_INTERVAL_SECONDS = 0.25
MAX_POLL_SECONDS = 180
MAX_POLL_COUNT = int(MAX_POLL_SECONDS / POLL_INTERVAL_SECONDS) + 1
MAX_NATIVE_EXTENT_FRAMES = 1498
MAX_ITEMS = 2048
MAX_TRACKS = 64
NATIVE_STATE_ROOT = (
    Path.home() / "Library/Application Support/VERA/qualification-output-native/v1"
)
HOST_STATE_ROOT = (
    Path.home()
    / "Library/Application Support/VERA/qualification-output-host/v1/attempts"
)
_R16_PRIVATE_ROOT = Path(
    "/Users/matthewbelinkie/Library/Application Support/VERA/private-preparation"
)
_R16_CANDIDATE_ROOT = (
    _R16_PRIVATE_ROOT / "issue-148/2026-10-11-r16-producer-review/candidate-inputs"
)
_R16_ORIGINAL_TARGET_ROOT = (
    _R16_PRIVATE_ROOT
    / "issue-148/2026-10-11-r15-heroes-base-binding/attempt-01/candidate-inputs"
)
_R16_DELTA_PATH = (
    _R16_PRIVATE_ROOT
    / "issue-145/advance-inputs/issue209-r16-preparation-cn209p1-attempt02"
    / "execution-dependency-delta.json"
)
_R16_DELTA_SHA256 = "2b15ad7400c8220fe726215eedd35c276ece95c68fbcff8966ce54ed57219c7d"
_R16_ORIGINALS = {
    "script-document-v2.json": (
        "27b9d5ddfb097f254d44ce0b6428e461f9e948010e95e1a4c817a8c71e76fa71"
    ),
    "compiler-dependencies-v2.json": (
        "19c4e7f4777afbd756a67dbb558d73bd87a705c38c1d1dc3d2e330436f8876a9"
    ),
}
_R16_ORIGINAL_TARGET_MODES = {
    "script-document-v2.json": stat.S_IFREG | 0o644,
    "compiler-dependencies-v2.json": stat.S_IFREG | 0o644,
}
_R16_EXECUTION_DOCUMENT_SHA256 = _R16_ORIGINALS["script-document-v2.json"]
_R16_EXECUTION_DEPENDENCIES_SHA256 = (
    "ca837b3d46b07d3c431bf923c3c99629f21777872ff1bbabd0bbca6834f48780"
)
_R16_PARENT_PINS = {
    "timeline-manifest-v2.json": (
        "89c83891dd5835e73495996a5357ff13d20e2dd4353f201b193c04bd04542e9b"
    ),
    "build-report-v2.json": (
        "8171995f062c039c4323015015fe7e603d43d8eededc063115982388132501b5"
    ),
    "compile-1.json": (
        "ef13c26c16862f0a5e3a1606f70110833bf381fb5fbe91f9fc2086fe72a02dac"
    ),
    "compile-2.json": (
        "ef13c26c16862f0a5e3a1606f70110833bf381fb5fbe91f9fc2086fe72a02dac"
    ),
}
NATIVE_RELEASE_ROOT = Path(__file__).resolve().parents[2]
APPROVAL_ACTION_PLAN = (
    "construct",
    "save_reopen",
    "capture_pre",
    "queue_render",
    "start_render",
    "poll_render",
    "capture_post",
)
APPROVAL_FIELDS = frozenset(
    {
        "schemaVersion",
        "lane",
        "approvalId",
        "operator",
        "issuedAt",
        "expiresAt",
        "invocationId",
        "context",
        "target",
        "profile",
        "releaseManifestSha256",
        "installedReleaseSha256",
        "packageRoot",
        "packageSha256",
        "admissionSha256",
        "sourceGraphSha256",
        "outputPath",
        "settings",
        "actionPlan",
        "maxPolls",
        "confirmations",
        "oneUse",
    }
)
APPROVED_SETTINGS_FIELDS = frozenset(
    {
        "container",
        "videoCodec",
        "audioCodec",
        "audioBitDepth",
        "sampleRate",
        "channels",
        "width",
        "height",
        "rate",
        "startFrame",
        "endFrame",
    }
)
RENDER_SETTINGS = {
    "container": "mov",
    "videoCodec": "prores422",
    "audioCodec": "lpcm",
    "audioBitDepth": 24,
    "sampleRate": 48000,
    "channels": 2,
}
ACTION_PLAN = APPROVAL_ACTION_PLAN
EFFECT_SCHEMA = "qualification-output-native-effect-intent/v1"
EFFECT_OBSERVATION_SCHEMA = "qualification-output-native-effect-observation/v1"
NATIVE_IDENTITY_FIELDS = frozenset({"product", "version", "python"})
EFFECT_OBSERVATION_FIELDS = frozenset(
    {
        "schemaVersion",
        "lane",
        "chainKey",
        "context",
        "operationId",
        "operationSequence",
        "effectIndex",
        "effectId",
        "intentSha256",
        "observedAt",
        "observation",
    }
)
_MARKER_COLORS = {
    "BLUE": "Blue",
    "CYAN": "Cyan",
    "GREEN": "Green",
    "ORANGE": "Orange",
    "PINK": "Pink",
    "PURPLE": "Purple",
    "RED": "Red",
    "YELLOW": "Yellow",
}
NATIVE_ENTRY_SCHEMA = "qualification-output-native-operation/v1"
NATIVE_ENTRY_FIELDS = frozenset(
    {
        "schemaVersion",
        "lane",
        "sequence",
        "priorResultSha256",
        "requestSha256",
        "context",
        "action",
        "operationId",
        "resultSha256",
        "status",
        "entrySha256",
    }
)
EFFECT_FIELDS = frozenset(
    {
        "schemaVersion",
        "lane",
        "chainKey",
        "context",
        "operationId",
        "operationSequence",
        "effectIndex",
        "effectId",
        "method",
        "argumentsSha256",
        "authoritySha256",
        "parentIntentSha256",
        "createdAt",
    }
)
ALLOWED_EFFECT_METHODS = frozenset(
    {
        "Project.SetSetting",
        "Timeline.SetStartTimecode",
        "MediaPool.ImportMedia",
        "Timeline.AddTrack",
        "Timeline.SetTrackName",
        "MediaPoolItem.SetMarkInOut",
        "MediaPool.AppendToTimeline",
        "MediaPoolItem.ClearMarkInOut",
        "TimelineItem.AddMarker",
        "TimelineItem.SetProperties",
        "Timeline.AddMarker",
        "ProjectManager.SaveProject",
        "ProjectManager.CloseProject",
        "ProjectManager.LoadProject",
        "Project.SetCurrentRenderFormatAndCodec",
        "Project.SetCurrentRenderMode",
        "Project.SetRenderSettings",
        "Project.AddRenderJob",
        "Project.StartRendering",
    }
)

CONTEXT_FIELDS = CONTEXT_HASH_FIELDS | frozenset(
    {"lane", "invocationId", "caseId", "phase", "target", "binding"}
)
TARGET_FIELDS = frozenset({"projectUid", "timelineUid", "projectName", "timelineName"})
PACKAGE_FIELDS = frozenset(
    {
        "profile",
        "packageRoot",
        "attestationPath",
        "attestationSha256",
        "admissionPath",
        "admissionSha256",
    }
)
PATH_HASH_FIELDS = frozenset({"path", "sha256"})
REQUEST_FIELDS = frozenset(
    {
        "schemaVersion",
        "lane",
        "profile",
        "action",
        "operationId",
        "sequence",
        "priorResultSha256",
        "context",
        "target",
        "package",
        "inputs",
        "sourceGraph",
        "release",
        "releaseManifestSha256",
        "renderIntent",
        "authority",
        "intent",
        "reservation",
        "payload",
        "resultPath",
    }
)
INPUT_FIELDS = frozenset(
    {
        "originalDocumentPath",
        "originalDependenciesPath",
        "executionDocumentPath",
        "executionDependenciesPath",
    }
)
AUTHORITY_FIELDS = frozenset(
    {
        "schemaVersion",
        "lane",
        "profile",
        "authorityId",
        "operator",
        "issuedAt",
        "expiresAt",
        "invocationId",
        "context",
        "target",
        "action",
        "payloadSha256",
        "packageSha256",
        "admissionSha256",
        "sourceGraphSha256",
        "releaseSha256",
        "releaseManifestSha256",
        "originalDocumentSha256",
        "originalDependenciesSha256",
        "executionDocumentSha256",
        "executionDependenciesSha256",
        "approvalPath",
        "approvalSha256",
        "permissions",
        "confirmations",
        "oneUse",
    }
)
INTENT_FIELDS = frozenset(
    {
        "schemaVersion",
        "lane",
        "context",
        "action",
        "operationId",
        "effectId",
        "sequence",
        "priorResultSha256",
        "payloadSha256",
        "authoritySha256",
        "reservationSha256",
        "createdAt",
    }
)
RENDER_INTENT_FIELDS = frozenset(
    {
        "schemaVersion",
        "lane",
        "context",
        "commitmentRawSha256",
        "outputPath",
        "settings",
        "profile",
        "authorityPath",
        "authoritySha256",
    }
)
RESERVATION_REF_FIELDS = frozenset({"path", "sha256", "receiptPath", "receiptSha256"})
RESULT_FIELDS = frozenset(
    {
        "schemaVersion",
        "lane",
        "profile",
        "action",
        "operationId",
        "sequence",
        "priorResultSha256",
        "requestSha256",
        "authoritySha256",
        "intentSha256",
        "reservationSha256",
        "context",
        "target",
        "status",
        "reason",
        "observedGeometrySha256",
        "jobId",
        "outputPath",
        "requestPath",
        "authorityPath",
        "intentPath",
        "reservationReceiptSha256",
        "approvalPath",
        "releaseManifestSha256",
        "sourceGraphSha256",
        "nativeGeometry",
        "geometryEnvelope",
        "settings",
        "commitmentRawSha256",
        "renderIntentSha256",
        "queuedResultSha256",
        "startedResultSha256",
        "startedAt",
        "completedAt",
        "completionResultSha256",
        "renderLineageSha256",
        "sourceOutputRawSha256",
        "priorResultPath",
        "effectLedger",
        "nativeIdentity",
        "admissionPath",
        "admissionSha256",
        "packageInventorySha256",
        "releasePath",
        "sourceGraphPath",
        "inputBindingPath",
        "inputBindingSha256",
        "renderStatus",
        "capturedAt",
        "expiresAt",
    }
)


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise OutputConsistencyError(message)


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hash_file(
    path: Path, *, maximum: int = 32 * 1024 * 1024 * 1024
) -> tuple[str, int]:
    _path(str(path), "file")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    digest = hashlib.sha256()
    total = 0
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        _require(stat.S_ISREG(before.st_mode), "regular file required")
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            _require(total <= maximum, "file exceeds bounded inventory size")
            digest.update(block)
        after = os.fstat(stream.fileno())
    current = path.stat(follow_symlinks=False)

    def signature(item: os.stat_result) -> tuple[int, int, int, int, int]:
        return (
            item.st_dev,
            item.st_ino,
            item.st_size,
            item.st_mtime_ns,
            item.st_ctime_ns,
        )

    _require(
        signature(before) == signature(after) == signature(current)
        and total == before.st_size,
        "file changed while hashing",
    )
    return digest.hexdigest(), total


def _path(value: Any, label: str) -> Path:
    _require(type(value) is str and bool(value), f"{label} path required")
    result = Path(value)
    _require(result.is_absolute(), f"absolute {label} path required")
    _require(
        not any(parent.is_symlink() for parent in (result, *result.parents)),
        f"symlink in {label} path",
    )
    return result


def _read(path: Path, label: str, *, maximum: int = MAX_BYTES) -> bytes:
    _path(str(path), label)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        _require(stat.S_ISREG(before.st_mode), f"regular {label} file required")
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    current = path.stat(follow_symlinks=False)

    def signature(item: os.stat_result) -> tuple[int, int, int, int, int]:
        return (
            item.st_dev,
            item.st_ino,
            item.st_size,
            item.st_mtime_ns,
            item.st_ctime_ns,
        )

    _require(
        signature(before) == signature(after) == signature(current),
        f"{label} changed while reading",
    )
    _require(len(raw) <= maximum, f"{label} exceeds size bound")
    return raw


def _read_ref(value: Any, label: str) -> tuple[bytes, str, Path]:
    ref = _shape(value, PATH_HASH_FIELDS, f"{label} reference")
    path = _path(ref["path"], label)
    expected = _digest(ref["sha256"])
    raw = _read(path, label)
    _require(_hash(raw) == expected, f"{label} digest differs")
    _require(stat.S_IMODE(path.stat().st_mode) == 0o400, f"{label} must be immutable")
    return raw, expected, path


def _time(value: Any, label: str) -> datetime:
    _identity(value)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise OutputConsistencyError(f"invalid {label}") from error
    _require(result.tzinfo is not None, f"timezone required for {label}")
    return result.astimezone(UTC)


def _context_equal(value: Any, expected: Any, label: str) -> dict[str, Any]:
    context = _context(value)
    _require(context == expected, f"{label} context differs")
    return context


def _immutable(path: Path, label: str) -> None:
    info = path.stat(follow_symlinks=False)
    _require(stat.S_ISREG(info.st_mode), f"regular {label} required")
    _require(stat.S_IMODE(info.st_mode) == 0o400, f"immutable {label} required")
    if hasattr(os, "getuid"):
        _require(info.st_uid == os.getuid(), f"current-user-owned {label} required")


def _settings_for_timeline(timeline: dict[str, Any]) -> dict[str, Any]:
    rate = timeline["frameRate"]
    _shape(rate, "numerator denominator", "frame rate")
    numerator = _integer(rate["numerator"], 1)
    denominator = _integer(rate["denominator"], 1)
    start = _integer(timeline["startFrame"])
    duration = _integer(timeline["durationFrames"], 1, MAX_NATIVE_EXTENT_FRAMES)
    return {
        **RENDER_SETTINGS,
        "width": _integer(timeline["width"], 1, 16384),
        "height": _integer(timeline["height"], 1, 16384),
        "rate": {"numerator": numerator, "denominator": denominator},
        "startFrame": start,
        "endFrame": start + duration - 1,
    }


def _expected_settings(package_root: Path, profile: str) -> dict[str, Any]:
    del profile  # Both independently admitted profiles use the same render tuple.
    path = package_root / "Compiler" / "timeline-manifest-v2.json"
    manifest = _parse(_read(path, "admitted timeline manifest"))
    timeline = manifest.get("timeline")
    if type(timeline) is not dict:
        raise OutputConsistencyError("admitted timeline required")
    return _settings_for_timeline(timeline)


def _verify_admitted_extent(manifest: dict[str, Any]) -> int:
    timeline = manifest.get("timeline")
    _require(type(timeline) is dict, "admitted timeline required")
    assert type(timeline) is dict
    return _integer(timeline.get("durationFrames"), 1, MAX_NATIVE_EXTENT_FRAMES)


def _verify_r16_parent_pins(root: Path, admission: dict[str, Any]) -> None:
    if admission["profile"] != R16_PROFILE:
        return
    _require(
        admission["manifestSha256"] == _R16_PARENT_PINS["timeline-manifest-v2.json"],
        "R16 parent manifest pin differs",
    )
    _require(
        admission["reportSha256"] == _R16_PARENT_PINS["build-report-v2.json"],
        "R16 parent report pin differs",
    )
    for name, expected in _R16_PARENT_PINS.items():
        if name in {"timeline-manifest-v2.json", "build-report-v2.json"}:
            continue
        raw = _read(root / "Compiler" / name, f"R16 parent {name}")
        _require(_hash(raw) == expected, f"R16 parent {name} pin differs")


def verify_operator_approval(
    raw: bytes,
    *,
    context: dict[str, Any],
    profile: str,
    admission_sha256: str,
    release_manifest_sha256: str,
    require_live: bool = True,
    require_output_absent: bool = True,
) -> dict[str, Any]:
    """Verify exact human-reviewed approval content, not a free-form hash."""
    _require(type(raw) is bytes, "approval bytes required")
    parsed = _parse(raw)
    _require(raw == _canonical(parsed), "canonical approval bytes required")
    approval = _shape(parsed, APPROVAL_FIELDS, "operator approval")
    _require(
        approval["schemaVersion"] == APPROVAL_SCHEMA and approval["lane"] == LANE,
        "unsupported operator approval",
    )
    approved_context = _context(approval["context"])
    _require(approved_context == _context(context), "approval context differs")
    _require(
        approval["target"] == approved_context["target"], "approval target differs"
    )
    _require(
        approval["profile"] == profile and profile in PROFILES,
        "approval profile differs",
    )
    _require(
        approval["releaseManifestSha256"] == _digest(release_manifest_sha256),
        "raw release manifest pin differs",
    )
    _require(
        approval["installedReleaseSha256"]
        == approved_context["installedReleaseSha256"],
        "normalized release pin differs",
    )
    _require(
        approval["packageSha256"] == approved_context["packageSha256"],
        "approval package pin differs",
    )
    _require(
        approval["sourceGraphSha256"] == approved_context["nativeSourceGraphSha256"],
        "approval source graph differs",
    )
    _require(
        approval["admissionSha256"] == _digest(admission_sha256),
        "approval admission pin differs",
    )
    _require(
        approval["actionPlan"] == list(APPROVAL_ACTION_PLAN),
        "approval action plan differs",
    )
    _require(approval["maxPolls"] == MAX_POLL_COUNT, "approval poll bound differs")
    _require(
        approval["confirmations"] == CONFIRMATIONS and approval["oneUse"] is True,
        "explicit one-use nonproduction approval required",
    )
    _identity(approval["approvalId"])
    _identity(approval["operator"])
    current_operator = (
        pwd.getpwuid(os.getuid()).pw_name
        if hasattr(os, "getuid")
        else getpass.getuser()
    )
    _require(
        approval["operator"] == current_operator,
        "approval operator differs from current OS user",
    )
    _require(
        approval["invocationId"] == approved_context["invocationId"],
        "approval invocation differs",
    )
    issued, expires = (
        _time(approval["issuedAt"], "approval issue time"),
        _time(approval["expiresAt"], "approval expiry"),
    )
    _require(
        issued < expires
        and expires - issued <= timedelta(seconds=MAX_LIFETIME_SECONDS),
        "approval lifetime exceeds bound",
    )
    if require_live:
        now = datetime.now(UTC)
        _require(issued <= now < expires, "operator approval expired or not yet live")
    root = _path(approval["packageRoot"], "approved package root")
    _require(root.is_dir(), "approved package root unavailable")
    admission_path = root.parent / "qualification-output-package-admission.json"
    admission_raw = _read(admission_path, "approved package admission")
    _require(
        _hash(admission_raw) == approval["admissionSha256"],
        "approved package admission changed",
    )
    settings = _shape(
        approval["settings"], APPROVED_SETTINGS_FIELDS, "approved render settings"
    )
    _require(
        settings == _expected_settings(root, profile),
        "approved settings differ from admitted timeline",
    )
    output = _path(approval["outputPath"], "approved MOV output")
    target_key = {
        "projectUid": approved_context["target"]["projectUid"],
        "timelineUid": approved_context["target"]["timelineUid"],
        "caseId": approved_context["caseId"],
        "phase": approved_context["phase"],
    }
    expected_parent = NATIVE_STATE_ROOT / "renders" / _hash(_canonical(target_key))
    _require(
        output.parent == expected_parent and output.suffix.lower() == ".mov",
        "output must use the private per-case MOV location",
    )
    if require_live and require_output_absent:
        _require(not output.exists(), "approved output already exists")
    _require(
        _path(approval["packageRoot"], "approved package root") == root,
        "package root path changed",
    )
    for field in (
        "packageSha256",
        "admissionSha256",
        "sourceGraphSha256",
        "releaseManifestSha256",
        "installedReleaseSha256",
    ):
        _digest(approval[field])
    return approval


def verify_render_intent(
    raw: bytes,
    *,
    context: dict[str, Any],
    commitment_sha256: str,
    require_output_absent: bool = True,
) -> dict[str, Any]:
    """Check the exact approved MOV tuple before the host reserves it."""
    _require(type(raw) is bytes, "render intent bytes required")
    value = _shape(_parse(raw), RENDER_INTENT_FIELDS, "render intent")
    _require(
        value["schemaVersion"] == RENDER_INTENT_SCHEMA and value["lane"] == LANE,
        "unsupported render intent",
    )
    _context_equal(value["context"], _context(context), "render intent")
    _require(
        value["commitmentRawSha256"] == _digest(commitment_sha256),
        "render intent commitment differs",
    )
    _require(value["profile"] in PROFILES, "render intent profile unsupported")
    approval_path = _path(value["authorityPath"], "render intent approval")
    approval_raw = _read(approval_path, "render intent approval")
    _immutable(approval_path, "render intent approval")
    _require(
        _hash(approval_raw) == _digest(value["authoritySha256"]),
        "render intent approval pin differs",
    )
    approval_value = _parse(approval_raw)
    approval = verify_operator_approval(
        approval_raw,
        context=_context(context),
        profile=value["profile"],
        admission_sha256=_digest(approval_value["admissionSha256"]),
        release_manifest_sha256=_digest(approval_value["releaseManifestSha256"]),
        require_live=True,
        require_output_absent=require_output_absent,
    )
    settings = _shape(
        value["settings"], APPROVED_SETTINGS_FIELDS, "render intent settings"
    )
    _require(
        settings == approval["settings"], "render intent settings differ from approval"
    )
    output = _path(value["outputPath"], "render intent output")
    _require(
        value["outputPath"] == approval["outputPath"],
        "render intent output differs from approval",
    )
    if require_output_absent:
        _require(not output.exists(), "render output already exists")
    return value


def _target(value: Any) -> dict[str, str]:
    result = _shape(value, TARGET_FIELDS, "native target")
    return {key: _identity(result[key]) for key in TARGET_FIELDS}


def _chain_key(context: dict[str, Any]) -> str:
    target = context["target"]
    return _hash(
        _canonical(
            {
                "projectUid": target["projectUid"],
                "timelineUid": target["timelineUid"],
                "caseId": context["caseId"],
                "phase": context["phase"],
            }
        )
    )


def native_request_paths(
    context: dict[str, Any], sequence: int
) -> tuple[Path, Path, Path, Path]:
    """Return fixed native-ledger paths for a host-prepared operation."""
    checked = _context(context)
    _require(type(sequence) is int and sequence >= 0, "invalid operation sequence")
    operation = (
        NATIVE_STATE_ROOT
        / "targets"
        / _chain_key(checked)
        / "operations"
        / f"{sequence:08d}"
    )
    return (
        operation / "result.json",
        operation / "authority.json",
        operation / "intent.json",
        operation / "request.json",
    )


def _payload_hash(payload: Any) -> str:
    return _hash(_canonical(payload))


def _request_projection(request: dict[str, Any]) -> dict[str, Any]:
    # Authority and intent are separate records, so this projection is acyclic.
    return {
        key: value
        for key, value in request.items()
        if key not in {"authority", "intent", "resultPath"}
    }


def verify_native_request(
    raw: bytes, *, expected_request_sha256: str, current: bool = True
) -> dict[str, Any]:
    """Validate a closed request; historical callers skip live source pins."""
    _require(
        type(raw) is bytes and len(raw) <= MAX_BYTES, "bounded request bytes required"
    )
    _require(_hash(raw) == _digest(expected_request_sha256), "request digest differs")
    request = _shape(_parse(raw), REQUEST_FIELDS, "native request")
    _require(
        request["schemaVersion"] == REQUEST_SCHEMA and request["lane"] == LANE,
        "unsupported native request version/lane",
    )
    _require(request["profile"] in PROFILES, "unsupported native package profile")
    _require(request["action"] in ACTIONS, "unsupported native action")
    _identity(request["operationId"])
    _identity(request["context"]["invocationId"])
    _require(
        type(request["sequence"]) is int and request["sequence"] >= 0,
        "invalid native sequence",
    )
    _digest(request["priorResultSha256"])
    context = _context(request["context"])
    target = _target(request["target"])
    _require(target == context["target"], "request/context target differs")
    package = _shape(request["package"], PACKAGE_FIELDS, "native package")
    _require(package["profile"] == request["profile"], "package profile differs")
    package_root = _path(package["packageRoot"], "package root")
    _path(package["attestationPath"], "package attestation")
    _digest(package["attestationSha256"])
    admission_path = _path(package["admissionPath"], "package admission")
    _digest(package["admissionSha256"])
    _require(
        admission_path
        == package_root.parent / "qualification-output-package-admission.json",
        "admission must use the closed sibling package location",
    )
    inputs = _shape(request["inputs"], INPUT_FIELDS, "native input paths")
    expected_inputs = {
        "originalDocumentPath": package_root / "Original" / "script-document-v2.json",
        "originalDependenciesPath": package_root
        / "Original"
        / "compiler-dependencies-v2.json",
        "executionDocumentPath": package_root / "Execution" / "script-document-v2.json",
        "executionDependenciesPath": package_root
        / "Execution"
        / "compiler-dependencies-v2.json",
    }
    for name in INPUT_FIELDS:
        _require(
            _path(inputs[name], name) == expected_inputs[name],
            f"{name} must use the closed package path",
        )
    for name, field in (
        ("sourceGraph", "nativeSourceGraphSha256"),
        ("release", "installedReleaseSha256"),
    ):
        ref = _shape(request[name], PATH_HASH_FIELDS, f"{name} reference")
        _path(ref["path"], name)
        _require(
            _digest(ref["sha256"]) == context[field], f"{name} context pin differs"
        )
        if current:
            ref_raw, digest, _ = _read_ref(ref, name)
            _require(
                digest == context[field] and bool(ref_raw),
                f"current {name} pin differs",
            )
    _digest(request["releaseManifestSha256"])
    authority = _shape(
        request["authority"], PATH_HASH_FIELDS, "native authority reference"
    )
    _path(authority["path"], "native authority")
    _digest(authority["sha256"])
    intent = _shape(request["intent"], PATH_HASH_FIELDS, "native intent reference")
    _path(intent["path"], "native intent")
    _digest(intent["sha256"])
    reservation = request["reservation"]
    if reservation is not None:
        _shape(reservation, RESERVATION_REF_FIELDS, "native reservation reference")
        _path(reservation["path"], "render reservation")
        _digest(reservation["sha256"])
        _path(reservation["receiptPath"], "render reservation receipt")
        _digest(reservation["receiptSha256"])
    render_intent = request["renderIntent"]
    if render_intent is not None:
        _shape(render_intent, PATH_HASH_FIELDS, "host render intent reference")
        _path(render_intent["path"], "host render intent")
        _digest(render_intent["sha256"])
    if request["action"] in {
        "queue_render",
        "start_render",
        "poll_render",
        "capture_post",
    }:
        _require(
            render_intent is not None,
            "render stage requires the reviewed render intent",
        )
    result_path = _path(request["resultPath"], "native result")
    _require(result_path.parent.exists(), "native result directory must exist")
    _shape(
        request["payload"], _payload_fields(request["action"]), "native action payload"
    )
    if current:
        for field, digest in (
            ("originalDocumentPath", context["originalDocumentSha256"]),
            ("originalDependenciesPath", context["originalDependenciesSha256"]),
            ("executionDocumentPath", context["executionDocumentSha256"]),
            ("executionDependenciesPath", context["executionDependenciesSha256"]),
        ):
            _require(
                _hash(_read(_path(inputs[field], field), field)) == digest,
                f"current {field} pin differs",
            )
    return request


def _payload_fields(action: str) -> frozenset[str]:
    fields = {
        "construct": frozenset(),
        "capture_pre": frozenset({"inputBindingPath", "inputBindingSha256"}),
        "save_reopen": frozenset(),
        "queue_render": frozenset({"settings", "outputPath", "outputFilename"}),
        "start_render": frozenset({"jobId", "queuedResultPath", "queuedResultSha256"}),
        "poll_render": frozenset({"jobId", "startedResultPath", "startedResultSha256"}),
        "capture_post": frozenset(
            {
                "inputBindingPath",
                "inputBindingSha256",
                "renderLineagePath",
                "renderLineageSha256",
                "completionResultPath",
                "completionResultSha256",
            }
        ),
    }
    return fields[action]


def _verify_admission(request: dict[str, Any]) -> dict[str, Any]:
    package = request["package"]
    root = _path(package["packageRoot"], "package root")
    raw = _read(
        _path(package["admissionPath"], "package admission"), "package admission"
    )
    _require(
        _hash(raw) == package["admissionSha256"], "package admission digest differs"
    )
    admission = _shape(
        _parse(raw),
        frozenset(
            {
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
            }
        ),
        "package admission",
    )
    _require(
        admission["schemaVersion"] == ADMISSION_SCHEMA, "unsupported package admission"
    )
    _require(admission["profile"] == request["profile"], "admission profile differs")
    _require(
        admission["packageInventorySha256"]
        == _digest(admission["packageInventorySha256"]),
        "invalid package inventory pin",
    )
    _require(
        admission["originalDocumentSha256"]
        == request["context"]["originalDocumentSha256"]
        and admission["originalDependenciesSha256"]
        == request["context"]["originalDependenciesSha256"]
        and admission["executionDocumentSha256"]
        == request["context"]["executionDocumentSha256"]
        and admission["executionDependenciesSha256"]
        == request["context"]["executionDependenciesSha256"],
        "admission input pins differ",
    )
    _require(
        admission["manifestSha256"] == request["context"]["manifestSha256"]
        and admission["reportSha256"] == request["context"]["reportSha256"],
        "admission manifest/report pins differ",
    )
    for name in INPUT_FIELDS:
        raw_input = _read(_path(request["inputs"][name], name), name, maximum=MAX_BYTES)
        field = name.removesuffix("Path") + "Sha256"
        _require(_hash(raw_input) == admission[field], f"current {name} pin differs")
    if request["profile"] == SYNTHETIC_PROFILE:
        _require(
            admission["disposition"] == "verified_synthetic"
            and admission["creativeQualification"] == "qualified_synthetic_only",
            "ordinary package is not a verified synthetic",
        )
        _require(
            admission["diagnostics"] == [] and admission["recoveryActions"] == [],
            "ordinary package diagnostics refuse",
        )
    else:
        _require(
            admission["disposition"] == "qualification_only"
            and admission["creativeQualification"] == "unqualified_temporary_presenter",
            "R16 profile lacks qualification-only disposition",
        )
        _require(
            type(admission["diagnostics"]) is list
            and len(admission["diagnostics"]) == 3,
            "R16 warning inventory is incomplete",
        )
        _require(
            type(admission["recoveryActions"]) is list
            and len(admission["recoveryActions"]) == 1,
            "R16 recovery inventory is incomplete",
        )
    for field in (
        "manifestSha256",
        "reportSha256",
        "viewSha256",
        "packageInventorySha256",
        "preflightSha256",
        "preparationSha256",
    ):
        _digest(admission[field])
    source_fields = frozenset(
        {
            "sourceId",
            "kind",
            "recordSha256",
            "receiptSha256",
            "timingSha256",
            "reviewSha256",
            "wavSha256",
        }
    )
    _require(type(admission["sourceProofs"]) is list, "source proof inventory required")
    proof_ids: set[str] = set()
    for proof in admission["sourceProofs"]:
        row = _shape(proof, source_fields, "admitted source proof")
        source_id = _identity(row["sourceId"])
        _require(source_id not in proof_ids, "duplicate admitted source proof")
        proof_ids.add(source_id)
        _identity(row["kind"])
        for key in source_fields - {"sourceId", "kind"}:
            if row[key] is not None:
                _digest(row[key])
    inventory_path = root / "package-inventory.json"
    inventory_raw = _read(inventory_path, "package inventory")
    _require(
        _hash(inventory_raw) == admission["packageInventorySha256"],
        "package inventory hash differs",
    )
    inventory = _shape(
        _parse(inventory_raw),
        frozenset({"schemaVersion", "files"}),
        "package inventory",
    )
    _require(
        inventory["schemaVersion"] == INVENTORY_SCHEMA
        and type(inventory["files"]) is list,
        "unsupported package inventory",
    )
    listed: dict[str, tuple[str, int]] = {}
    previous = ""
    for row in inventory["files"]:
        entry = _shape(
            row, frozenset({"path", "sha256", "size"}), "package inventory file"
        )
        rel = entry["path"]
        _require(
            type(rel) is str
            and bool(rel)
            and "\\" not in rel
            and not Path(rel).is_absolute()
            and all(part not in {"", ".", ".."} for part in rel.split("/")),
            "unsafe package inventory path",
        )
        _require(
            rel > previous
            and rel
            not in {
                "package-inventory.json",
                "qualification-output-package-admission.json",
            },
            "package inventory is unordered or self-referential",
        )
        previous = rel
        digest = _digest(entry["sha256"])
        size = _integer(entry["size"])
        path = _path(str(root / rel), "package inventory file")
        file_digest, actual_size = _hash_file(path)
        _require(
            (file_digest, actual_size) == (digest, size),
            "package inventory file changed",
        )
        listed[rel] = (digest, size)
    actual_files: set[str] = set()
    for candidate in root.rglob("*"):
        info = candidate.lstat()
        _require(not stat.S_ISLNK(info.st_mode), "symbolic link in package")
        if stat.S_ISREG(info.st_mode):
            relative = candidate.relative_to(root).as_posix()
            if relative not in {
                "package-inventory.json",
                "qualification-output-package-admission.json",
            }:
                actual_files.add(relative)
        else:
            _require(stat.S_ISDIR(info.st_mode), "unsupported package entry")
    _require(
        actual_files == set(listed),
        "package inventory is incomplete or includes absent files",
    )
    report_raw = _read(
        root / "Compiler" / "build-report-v2.json", "admitted build report"
    )
    _require(_hash(report_raw) == admission["reportSha256"], "admitted report changed")
    report = _parse(report_raw)
    _require(
        admission["manifestSha256"] == request["context"]["manifestSha256"],
        "admission manifest context pin differs",
    )
    manifest_raw = _read(
        root / "Compiler" / "timeline-manifest-v2.json", "admitted timeline manifest"
    )
    _require(
        _hash(manifest_raw) == admission["manifestSha256"], "admitted manifest changed"
    )
    manifest = _parse(manifest_raw)
    _require(type(manifest) is dict, "admitted manifest must be an object")
    _verify_admitted_extent(manifest)
    _verify_r16_parent_pins(root, admission)
    _require(type(report) is dict, "admitted report must be an object")
    if request["profile"] == R16_PROFILE:
        # These rows are retained from the exact hashed report, never synthesized
        # into the installed request. The package builder records their canonical
        # full rows in its admission projection.
        report_warnings = report.get("diagnostics")
        report_recovery = report.get("recoveryActions")
        _require(
            type(report_warnings) is list
            and admission["diagnostics"] == report_warnings,
            "R16 warning rows differ from the full report",
        )
        _require(
            type(report_recovery) is list
            and admission["recoveryActions"] == report_recovery,
            "R16 recovery rows differ from the full report",
        )
        assert type(report_warnings) is list
        assert type(report_recovery) is list
        _require(
            all(
                row.get("code") == "TEMPORARY_PRESENTER_STILL"
                for row in report_warnings
                if type(row) is dict
            ),
            "unexpected R16 diagnostic code",
        )
        _require(
            len(report_warnings) == 3
            and all(type(row) is dict for row in report_warnings),
            "exact three R16 warnings required",
        )
        _require(
            len(report_recovery) == 1
            and all(
                type(row) is dict and row.get("kind") == "REPLACE_TEMPORARY_PRESENTER"
                for row in report_recovery
            ),
            "exact R16 recovery row required",
        )
    return admission


def _historical_approval(raw: bytes, request: dict[str, Any]) -> dict[str, Any]:
    _require(raw == _canonical(_parse(raw)), "historical approval is not canonical")
    approval = _shape(_parse(raw), APPROVAL_FIELDS, "historical operator approval")
    _require(
        approval["schemaVersion"] == APPROVAL_SCHEMA and approval["lane"] == LANE,
        "unsupported historical approval",
    )
    _require(
        _context(approval["context"]) == request["context"]
        and approval["target"] == request["target"],
        "historical approval target/context differs",
    )
    _require(
        approval["profile"] == request["profile"]
        and approval["packageSha256"] == request["context"]["packageSha256"]
        and approval["admissionSha256"] == request["package"]["admissionSha256"],
        "historical approval package differs",
    )
    _require(
        approval["installedReleaseSha256"]
        == request["context"]["installedReleaseSha256"]
        and approval["sourceGraphSha256"]
        == request["context"]["nativeSourceGraphSha256"]
        and approval["releaseManifestSha256"] == request["releaseManifestSha256"],
        "historical approval release/source differs",
    )
    _require(
        approval["actionPlan"] == list(APPROVAL_ACTION_PLAN)
        and approval["maxPolls"] == MAX_POLL_COUNT
        and approval["confirmations"] == CONFIRMATIONS
        and approval["oneUse"] is True,
        "historical approval plan differs",
    )
    _identity(approval["operator"])
    issued, expires = (
        _time(approval["issuedAt"], "historical approval issue"),
        _time(approval["expiresAt"], "historical approval expiry"),
    )
    _require(
        issued < expires
        and expires - issued <= timedelta(seconds=MAX_LIFETIME_SECONDS),
        "historical approval window invalid",
    )
    _require(
        approval["packageRoot"] == request["package"]["packageRoot"],
        "historical approval package root differs",
    )
    return approval


def _verify_authority(
    request: dict[str, Any], *, current: bool = True
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    raw, digest, _ = _read_ref(request["authority"], "native authority")
    authority = _shape(_parse(raw), AUTHORITY_FIELDS, "native authority")
    _require(
        authority["schemaVersion"] == AUTHORITY_SCHEMA and authority["lane"] == LANE,
        "unsupported native authority",
    )
    _require(authority["profile"] == request["profile"], "authority profile differs")
    _context_equal(authority["context"], request["context"], "authority")
    _require(authority["target"] == request["target"], "authority target differs")
    _require(authority["action"] == request["action"], "authority action differs")
    _require(
        authority["payloadSha256"] == _payload_hash(request["payload"]),
        "authority payload differs",
    )
    for field, expected in (
        ("packageSha256", request["context"]["packageSha256"]),
        ("admissionSha256", request["package"]["admissionSha256"]),
        ("sourceGraphSha256", request["context"]["nativeSourceGraphSha256"]),
        ("releaseSha256", request["context"]["installedReleaseSha256"]),
        ("releaseManifestSha256", request["releaseManifestSha256"]),
        ("originalDocumentSha256", request["context"]["originalDocumentSha256"]),
        (
            "originalDependenciesSha256",
            request["context"]["originalDependenciesSha256"],
        ),
        ("executionDocumentSha256", request["context"]["executionDocumentSha256"]),
        (
            "executionDependenciesSha256",
            request["context"]["executionDependenciesSha256"],
        ),
    ):
        _require(authority[field] == expected, f"authority {field} differs")
    _identity(authority["authorityId"])
    _identity(authority["operator"])
    _require(
        authority["invocationId"] == request["context"]["invocationId"],
        "authority invocation differs",
    )
    issued, expires = (
        _time(authority["issuedAt"], "authority issue time"),
        _time(authority["expiresAt"], "authority expiry"),
    )
    if current:
        now = datetime.now(UTC)
        _require(
            issued <= now < expires
            and expires - issued <= timedelta(seconds=MAX_LIFETIME_SECONDS),
            "native authority expired or exceeds its finite window",
        )
    else:
        _require(
            issued < expires
            and expires - issued <= timedelta(seconds=MAX_LIFETIME_SECONDS),
            "historical native authority window invalid",
        )
    _require(authority["oneUse"] is True, "one-use authority required")
    _require(
        authority["permissions"] == [request["action"]],
        "authority permission is not exact",
    )
    _require(
        authority["confirmations"] == CONFIRMATIONS,
        "saved disposable target and ExternalScripting None confirmations required",
    )
    approval_path = _path(authority["approvalPath"], "reviewed approval")
    approval_raw = _read(approval_path, "reviewed approval")
    _immutable(approval_path, "reviewed approval")
    _require(
        _hash(approval_raw) == _digest(authority["approvalSha256"]),
        "reviewed approval digest differs",
    )
    approval = (
        verify_operator_approval(
            approval_raw,
            context=request["context"],
            profile=request["profile"],
            admission_sha256=request["package"]["admissionSha256"],
            release_manifest_sha256=request["releaseManifestSha256"],
            require_live=True,
            require_output_absent=request["action"]
            in {"construct", "save_reopen", "capture_pre", "queue_render"},
        )
        if current
        else _historical_approval(approval_raw, request)
    )
    _require(
        request["action"] in approval["actionPlan"],
        "action is outside the reviewed approval plan",
    )
    _require(
        approval["packageRoot"] == request["package"]["packageRoot"],
        "approval package root differs",
    )
    _require(
        approval["outputPath"]
        == request["payload"].get("outputPath", approval["outputPath"]),
        "request output differs from approval",
    )
    _require(
        authority["issuedAt"] == approval["issuedAt"]
        and authority["expiresAt"] == approval["expiresAt"],
        "authority window differs from approval",
    )
    _require(
        authority["operator"] == approval["operator"]
        and authority["approvalSha256"] == _hash(approval_raw),
        "authority approval actor/content differs",
    )
    _require(
        authority["approvalPath"] == str(approval_path),
        "authority approval path differs",
    )
    return authority, digest, approval


def _verify_intent(
    request: dict[str, Any], authority_sha256: str, reservation_sha256: str | None
) -> tuple[dict[str, Any], str]:
    raw, digest, _ = _read_ref(request["intent"], "native intent")
    intent = _shape(_parse(raw), INTENT_FIELDS, "native intent")
    _require(
        intent["schemaVersion"] == INTENT_SCHEMA and intent["lane"] == LANE,
        "unsupported native intent",
    )
    _context_equal(intent["context"], request["context"], "intent")
    for field in ("action", "operationId", "sequence", "priorResultSha256"):
        _require(intent[field] == request[field], f"intent {field} differs")
    _require(
        intent["payloadSha256"] == _payload_hash(request["payload"]),
        "intent payload differs",
    )
    _require(intent["authoritySha256"] == authority_sha256, "intent authority differs")
    _require(
        intent["reservationSha256"] == reservation_sha256, "intent reservation differs"
    )
    _time(intent["createdAt"], "intent time")
    _identity(intent["effectId"])
    return intent, digest


def _host_attempt_history(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Authenticate the fixed complete host attempt chain for this UID case."""
    chain = {
        "projectUid": context["target"]["projectUid"],
        "timelineUid": context["target"]["timelineUid"],
        "caseId": context["caseId"],
        "phase": context["phase"],
    }
    directory = HOST_STATE_ROOT / _hash(_canonical(chain))
    _require(
        _parse(_read(directory / "chain.json", "host chain marker")) == chain,
        "host journal target/case/phase differs",
    )
    entries = sorted(directory.glob("entry-*.json"))
    pending = sorted(directory.glob("pending-*.json"))
    heads = sorted(directory.glob("head-*.json"))
    _require(
        len(entries) == len(pending) == len(heads) <= 4096,
        "partial or oversized host journal",
    )
    fields = frozenset(
        {
            "schemaVersion",
            "lane",
            "context",
            "sequence",
            "priorHeadSha256",
            "state",
            "commitmentRawSha256",
            "commitmentPayloadSha256",
            "predictionBytesSha256",
            "reservationRawSha256",
            "resultRawSha256",
            "entrySha256",
        }
    )
    rows: list[dict[str, Any]] = []
    previous = EMPTY_HEAD
    last: dict[str, dict[str, Any]] = {}
    for sequence, (entry_path, pending_path, head_path) in enumerate(
        zip(entries, pending, heads, strict=True)
    ):
        _require(
            entry_path.name == f"entry-{sequence:04d}.json"
            and pending_path.name == f"pending-{sequence:04d}.json"
            and head_path.name == f"head-{sequence:04d}.json",
            "host journal sequence gap",
        )
        raw = _read(entry_path, "host attempt entry")
        _require(
            raw == _read(pending_path, "host pending entry"),
            "host journal partial publication",
        )
        row = _shape(_parse(raw), fields, "host attempt entry")
        _require(
            row["schemaVersion"] == "qualification-output-attempt/v1"
            and row["lane"] == LANE
            and type(row["sequence"]) is int
            and row["sequence"] == sequence
            and row["priorHeadSha256"] == previous,
            "host attempt chain ordering differs",
        )
        row_context = _context(row["context"])
        row_chain = {
            "projectUid": row_context["target"]["projectUid"],
            "timelineUid": row_context["target"]["timelineUid"],
            "caseId": row_context["caseId"],
            "phase": row_context["phase"],
        }
        _require(row_chain == chain, "host attempt crossed UID/case/phase chain")
        _require(
            row["entrySha256"]
            == _hash(
                _canonical(
                    {key: value for key, value in row.items() if key != "entrySha256"}
                )
            ),
            "host entry hash differs",
        )
        _require(
            _parse(_read(head_path, "host journal head"))
            == {"sequence": sequence, "entrySha256": row["entrySha256"]},
            "host journal head anchor differs",
        )
        for field in (
            "commitmentRawSha256",
            "commitmentPayloadSha256",
            "predictionBytesSha256",
            "reservationRawSha256",
            "resultRawSha256",
        ):
            if row[field] is not None:
                _digest(row[field])
        binding = row_context["binding"]["bindingSha256"]
        prior = last.get(binding)
        state = row["state"]
        _require(
            state
            in {
                "committed",
                "expired_unused",
                "reserved_by_render_intent",
                "uncertain",
                "compared_consistent",
                "compared_refused",
            },
            "unknown host attempt state",
        )
        if state == "committed":
            _require(
                prior is None or prior["state"] == "expired_unused",
                "host commitment replayed",
            )
            _require(
                row["reservationRawSha256"] is None and row["resultRawSha256"] is None,
                "host commitment has future references",
            )
        else:
            _require(
                prior is not None
                and all(
                    row[key] == prior[key]
                    for key in (
                        "context",
                        "commitmentRawSha256",
                        "commitmentPayloadSha256",
                        "predictionBytesSha256",
                    )
                ),
                "host attempt lineage differs",
            )
            assert prior is not None
            if state == "expired_unused":
                _require(
                    prior["state"] == "committed"
                    and row["reservationRawSha256"] is None
                    and row["resultRawSha256"] is None,
                    "invalid expired transition",
                )
            elif state == "reserved_by_render_intent":
                _require(
                    prior["state"] == "committed"
                    and row["reservationRawSha256"] is not None
                    and row["resultRawSha256"] is None,
                    "invalid host reservation transition",
                )
            else:
                _require(
                    prior["state"] == "reserved_by_render_intent"
                    and row["reservationRawSha256"] == prior["reservationRawSha256"],
                    "invalid host terminal transition",
                )
        previous = row["entrySha256"]
        last[binding] = row
        artifact_root = directory / "artifacts"
        for field in (
            "commitmentRawSha256",
            "predictionBytesSha256",
            "reservationRawSha256",
            "resultRawSha256",
        ):
            digest = row[field]
            if digest is not None:
                artifact = _read(
                    artifact_root / digest,
                    "host retained attempt artifact",
                    maximum=48_000_000,
                )
                _require(_hash(artifact) == digest, "host retained artifact changed")
        rows.append(row)
    return rows


def _authenticate_host_receipt(
    receipt_raw: bytes,
    receipt_path: Path,
    *,
    kind: str,
    expected_payload: dict[str, Any],
    context: dict[str, Any],
) -> tuple[dict[str, Any], list[bytes]]:
    vault = HOST_STATE_ROOT / _chain_key(context) / "receipts"
    _require(
        receipt_path == vault / _hash(receipt_raw),
        "host receipt is outside the fixed vault",
    )
    _immutable(receipt_path, "retained host receipt")
    _require(
        _read(receipt_path, "retained host receipt") == receipt_raw,
        "host receipt is not retained",
    )
    key_path = vault / "key"
    key = _read(key_path, "host receipt key", maximum=32)
    _immutable(key_path, "host receipt key")
    _require(len(key) == 32, "host receipt key length differs")
    receipt = _shape(
        _parse(receipt_raw),
        frozenset(
            {"schemaVersion", "lane", "kind", "payload", "evidenceSha256", "mac"}
        ),
        "host receipt",
    )
    _require(
        receipt["schemaVersion"] == "qualification-output-host-receipt/v1"
        and receipt["lane"] == LANE
        and receipt["kind"] == kind,
        "host receipt domain differs",
    )
    _require(receipt_raw == _canonical(receipt), "host receipt is not canonical")
    _require(receipt["payload"] == expected_payload, "host receipt payload differs")
    unsigned = {key: value for key, value in receipt.items() if key != "mac"}
    _require(
        type(receipt["mac"]) is str
        and hmac.compare_digest(
            receipt["mac"], hmac.digest(key, _canonical(unsigned), "sha256").hex()
        ),
        "host receipt MAC differs",
    )
    hashes = _list(receipt["evidenceSha256"], 64, minimum=1)
    evidence: list[bytes] = []
    for digest in hashes:
        _digest(digest)
        raw = _read(vault / digest, "host receipt evidence", maximum=48_000_000)
        _require(_hash(raw) == digest, "host receipt evidence changed")
        evidence.append(raw)
    return receipt, evidence


def _verify_reservation(request: dict[str, Any], *, current: bool = True) -> str | None:
    ref = request["reservation"]
    if ref is None:
        _require(
            request["action"]
            not in {"queue_render", "start_render", "poll_render", "capture_post"},
            "render action requires an owned reservation",
        )
        return None
    raw = _read(_path(ref["path"], "render reservation"), "render reservation")
    digest = _digest(ref["sha256"])
    _require(_hash(raw) == digest, "render reservation digest differs")
    _immutable(_path(ref["path"], "render reservation"), "render reservation")
    reservation = _shape(
        _parse(raw), frozenset(RESERVATION_FIELDS.split()), "render reservation"
    )
    _require(raw == _canonical(reservation), "render reservation is not canonical")
    _require(
        reservation["schemaVersion"] == "qualification-output-reservation/v1",
        "unsupported render reservation",
    )
    _context_equal(reservation["context"], request["context"], "reservation")
    receipt_raw = _read(
        _path(ref["receiptPath"], "reservation receipt"), "reservation receipt"
    )
    _require(
        reservation["reservationReceiptSha256"] == ref["receiptSha256"],
        "reservation receipt reference differs",
    )
    receipt_path = _path(ref["receiptPath"], "reservation receipt")
    _immutable(receipt_path, "reservation receipt")
    _require(
        _hash(receipt_raw) == _digest(ref["receiptSha256"]),
        "reservation receipt digest differs",
    )
    render_ref = request["renderIntent"]
    render_raw, render_sha, _ = _read_ref(render_ref, "host render intent")
    _require(
        render_sha == reservation["renderIntentSha256"],
        "reservation/render intent differs",
    )
    if current:
        render_intent = verify_render_intent(
            render_raw,
            context=request["context"],
            commitment_sha256=reservation["commitmentRawSha256"],
            require_output_absent=request["action"] == "queue_render",
        )
    else:
        render_intent = _shape(
            _parse(render_raw), RENDER_INTENT_FIELDS, "historical render intent"
        )
        _require(
            render_intent["schemaVersion"] == RENDER_INTENT_SCHEMA
            and render_intent["lane"] == LANE
            and render_intent["context"] == request["context"]
            and render_intent["commitmentRawSha256"]
            == reservation["commitmentRawSha256"],
            "historical render intent differs",
        )
        approval_raw_for_render = _read(
            _path(render_intent["authorityPath"], "render approval"), "render approval"
        )
        approval_for_render = _historical_approval(approval_raw_for_render, request)
        _require(
            _hash(approval_raw_for_render) == render_intent["authoritySha256"]
            and render_intent["settings"] == approval_for_render["settings"]
            and render_intent["outputPath"] == approval_for_render["outputPath"],
            "historical render intent approval differs",
        )
    payload = request["payload"]
    approval_raw = _read(
        _path(render_intent["authorityPath"], "render approval"), "render approval"
    )
    approval = _parse(approval_raw)
    _require(
        render_intent["outputPath"] == approval["outputPath"],
        "reserved output differs from render intent",
    )
    _require(
        render_intent["settings"] == approval["settings"],
        "reserved settings differ from render intent",
    )
    if request["action"] == "queue_render":
        _require(
            payload["outputPath"] == render_intent["outputPath"],
            "queue output differs from approved intent",
        )
        _require(
            payload["settings"] == render_intent["settings"],
            "queue settings differ from approved intent",
        )
        _require(
            payload["outputFilename"] == Path(render_intent["outputPath"]).stem,
            "queue filename differs from approved output",
        )
    rows = _host_attempt_history(request["context"])
    binding = request["context"]["binding"]["bindingSha256"]
    matching = [
        row for row in rows if row["context"]["binding"]["bindingSha256"] == binding
    ]
    if current:
        _require(
            bool(matching) and matching[-1]["state"] == "reserved_by_render_intent",
            "reservation is not latest host attempt for this binding",
        )
        latest = matching[-1]
    else:
        retained = [
            row
            for row in matching
            if row["state"] == "reserved_by_render_intent"
            and row["reservationRawSha256"] == digest
        ]
        _require(bool(retained), "reservation is absent from fixed host history")
        latest = retained[-1]
    _require(
        latest["context"] == request["context"]
        and latest["reservationRawSha256"] == digest,
        "reservation differs from fixed host history",
    )
    _require(
        latest["commitmentRawSha256"] == reservation["commitmentRawSha256"]
        and latest["commitmentPayloadSha256"] == reservation["commitmentPayloadSha256"],
        "reservation commitment differs from host history",
    )
    receipt, evidence = _authenticate_host_receipt(
        receipt_raw,
        receipt_path,
        kind="output_render_reservation",
        expected_payload={
            key: value
            for key, value in reservation.items()
            if key != "reservationReceiptSha256"
        },
        context=request["context"],
    )
    _require(
        len(evidence) == 3
        and _hash(evidence[0]) == reservation["commitmentRawSha256"]
        and _hash(evidence[2]) == render_sha,
        "reservation receipt evidence differs",
    )
    commit = _parse(evidence[0])
    _require(
        evidence[0] == _canonical(commit)
        and commit.get("context") == request["context"]
        and commit.get("commitmentReceiptSha256") is not None,
        "reservation lacks committed prediction lineage",
    )
    commitment_receipt_raw = evidence[1]
    commitment_receipt_sha = _hash(commitment_receipt_raw)
    _require(
        commitment_receipt_sha
        == _digest(receipt["evidenceSha256"][1])
        == _digest(commit["commitmentReceiptSha256"]),
        "commitment receipt pin differs",
    )
    commitment_vault = HOST_STATE_ROOT / _chain_key(request["context"]) / "receipts"
    _, commitment_evidence = _authenticate_host_receipt(
        commitment_receipt_raw,
        commitment_vault / commitment_receipt_sha,
        kind="output_prediction_commitment",
        expected_payload={
            key: value
            for key, value in commit.items()
            if key != "commitmentReceiptSha256"
        },
        context=request["context"],
    )
    _require(
        len(commitment_evidence) == 5,
        "commitment receipt evidence differs",
    )
    binding_raw, geometry_raw, geometry_receipt, payload_raw, prediction = (
        commitment_evidence
    )
    commit_fields = frozenset(COMMITMENT_FIELDS.split())
    commit = _shape(commit, commit_fields, "committed prediction")
    commitment_payload = {
        key: value for key, value in commit.items() if key != "commitmentReceiptSha256"
    }
    _require(
        _canonical(commitment_payload) == payload_raw
        and _parse(payload_raw) == commitment_payload
        and _hash(payload_raw) == reservation["commitmentPayloadSha256"],
        "commitment payload evidence differs",
    )
    binding = _parse(binding_raw)
    _require(
        binding_raw == _canonical(binding)
        and binding.get("context") == request["context"] == commit["context"]
        and binding.get("sourceEntries") == commit["sourceEntries"],
        "prediction input-binding evidence differs",
    )
    geometry_envelope = _parse(geometry_raw)
    _require(
        geometry_raw == _canonical(geometry_envelope)
        and type(geometry_envelope.get("geometry")) is dict
        and geometry_envelope.get("inputBindingSha256") == _hash(binding_raw)
        and geometry_envelope.get("geometry", {}).get("context") == request["context"]
        and geometry_envelope.get("receiptSha256") == _hash(geometry_receipt)
        and commit["geometryCaptureRawSha256"] == _hash(geometry_raw)
        and commit["geometryReceiptSha256"] == _hash(geometry_receipt)
        and commit["geometrySha256"]
        == _hash(_canonical(geometry_envelope["geometry"])),
        "prediction geometry evidence differs",
    )
    _require(
        type(prediction) is bytes
        and _hash(prediction) == commit["predictionBytesSha256"]
        and len(prediction) == commit["predictionByteLength"],
        "prediction PCM evidence differs",
    )
    return digest


def _admission_profile(request: dict[str, Any]) -> dict[str, Any]:
    admission = _verify_admission(request)
    root = _path(request["package"]["packageRoot"], "package root")
    manifest_raw = _read(
        root / "Compiler" / "timeline-manifest-v2.json", "admitted timeline manifest"
    )
    view_raw = _read(root / "Delivery" / "delivery-view.json", "admitted delivery view")
    manifest, view = _parse(manifest_raw), _parse(view_raw)
    _require(
        _hash(manifest_raw) == admission["manifestSha256"], "manifest snapshot differs"
    )
    _require(
        _hash(view_raw) == admission["viewSha256"], "delivery view snapshot differs"
    )
    _require(
        type(manifest.get("timeline")) is dict
        and view.get("timeline") == manifest["timeline"],
        "view timeline differs from manifest",
    )
    _require(
        view.get("tracks") == manifest.get("tracks"), "view tracks differ from manifest"
    )
    if request["profile"] == SYNTHETIC_PROFILE:
        # Existing #177 verifier is stdlib-only and consumes the exact admitted
        # package. It never connects to Resolve or invokes compiler behavior.
        from .workflow_v2 import load_verified_package_v2

        loaded = load_verified_package_v2(
            _path(request["package"]["attestationPath"], "package attestation"),
            request["package"]["attestationSha256"],
        )
        _require(
            loaded.manifest is not None and loaded.view is not None,
            "ordinary package verifier returned no manifest/view",
        )
        _require(
            _hash(
                _read(
                    _path(request["package"]["attestationPath"], "package attestation"),
                    "package attestation",
                )
            )
            == request["package"]["attestationSha256"],
            "ordinary package attestation changed",
        )
        _require(
            loaded.manifest == manifest and loaded.view == view,
            "ordinary verified package differs from native snapshots",
        )
        source_root = _path(str(loaded.root), "verified public package root")
    else:
        _require(
            admission["disposition"] == "qualification_only"
            and admission["creativeQualification"] == "unqualified_temporary_presenter",
            "R16 package is not qualification-only",
        )
        original_inputs = _verify_r16_original_currentness()
        _require(
            _hash(original_inputs["script-document-v2.json"])
            == admission["originalDocumentSha256"]
            == _R16_ORIGINALS["script-document-v2.json"]
            and _hash(original_inputs["compiler-dependencies-v2.json"])
            == admission["originalDependenciesSha256"]
            == _R16_ORIGINALS["compiler-dependencies-v2.json"]
            and admission["executionDocumentSha256"] == _R16_EXECUTION_DOCUMENT_SHA256
            and admission["executionDependenciesSha256"]
            == _R16_EXECUTION_DEPENDENCIES_SHA256,
            "R16 package no longer matches the pinned original/execution inputs",
        )
        source_root = root
    return {
        "admission": admission,
        "manifest": manifest,
        "view": view,
        "sourceRoot": source_root,
    }


def _r16_file_identity(path: Path) -> dict[str, int]:
    info = path.stat(follow_symlinks=False)
    return {
        "device": info.st_dev,
        "inode": info.st_ino,
        "mode": stat.S_IFMT(info.st_mode),
        "mtimeNs": info.st_mtime_ns,
        "size": info.st_size,
    }


def _r16_stat_signature(path: Path) -> tuple[int, int, int, int, int, int]:
    info = path.stat(follow_symlinks=False)
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _r16_path_parents_are_real(path: Path, label: str) -> None:
    for parent in path.parents:
        _require(
            parent.is_dir() and not parent.is_symlink(), f"R16 {label} parent changed"
        )


def _verify_r16_original_currentness() -> dict[str, bytes]:
    """Recheck the pinned R16 original symlinks/targets at each live operation."""
    try:
        return _verify_r16_original_currentness_inner()
    except OutputConsistencyError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise OutputConsistencyError(
            "R16 original link/target currentness is unavailable"
        ) from error


def _verify_r16_original_currentness_inner() -> dict[str, bytes]:
    delta_raw = _read(
        _R16_DELTA_PATH, "pinned R16 dependency delta", maximum=16 * 1024 * 1024
    )
    _require(
        _hash(delta_raw) == _R16_DELTA_SHA256, "pinned R16 dependency delta changed"
    )

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, child in pairs:
            _require(key not in value, "pinned R16 dependency delta has duplicate keys")
            value[key] = child
        return value

    def reject_constant(value: str) -> None:
        raise ValueError(f"invalid JSON constant: {value}")

    delta = json.loads(
        delta_raw,
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )
    _require(type(delta) is dict, "pinned R16 dependency delta must be an object")
    final_state = delta.get("finalInputState")
    _require(type(final_state) is dict, "pinned R16 final input state is missing")
    regular_files = final_state.get("regularFiles")
    _require(
        type(regular_files) is dict, "pinned R16 regular input inventory is missing"
    )

    snapshots: dict[str, bytes] = {}
    for name, expected_sha256 in _R16_ORIGINALS.items():
        link_path = _R16_CANDIDATE_ROOT / name
        target_path = _R16_ORIGINAL_TARGET_ROOT / name
        _r16_path_parents_are_real(link_path, "original link")
        _r16_path_parents_are_real(target_path, "original target")

        link_info = link_path.lstat()
        _require(
            stat.S_ISLNK(link_info.st_mode),
            f"R16 original input is not the approved symlink: {name}",
        )
        target_info = target_path.lstat()
        _require(
            stat.S_ISREG(target_info.st_mode),
            f"R16 original target is not a regular file: {name}",
        )
        _require(
            target_info.st_mode == _R16_ORIGINAL_TARGET_MODES[name],
            "R16 original target mode differs from the pinned currentness mode: "
            f"{name}",
        )
        link_text = os.readlink(link_path)
        _require(
            link_path.resolve(strict=True) == target_path
            and link_text == str(target_path),
            f"R16 original link target/text changed: {name}",
        )

        recorded = regular_files.get(str(link_path))
        _require(
            type(recorded) is dict,
            f"R16 original input identity is absent from the pinned delta: {name}",
        )
        identity = recorded.get("identity")
        _require(
            type(identity) is dict,
            f"R16 original link/target identity is absent: {name}",
        )
        _require(
            recorded.get("rawSha256") == f"sha256:{expected_sha256}"
            and identity.get("path") == str(link_path)
            and identity.get("resolvedTarget") == str(target_path)
            and identity.get("linkText") == link_text
            and identity.get("linkIdentity") == _r16_file_identity(link_path)
            and identity.get("targetIdentity") == _r16_file_identity(target_path),
            f"R16 original link/target identity differs from the pinned delta: {name}",
        )

        before_link = _r16_stat_signature(link_path)
        before_target = _r16_stat_signature(target_path)
        raw = _read(
            target_path, f"R16 original target {name}", maximum=16 * 1024 * 1024
        )
        _require(
            _hash(raw) == expected_sha256, f"R16 original target bytes changed: {name}"
        )
        _require(
            _r16_stat_signature(link_path) == before_link
            and _r16_stat_signature(target_path) == before_target
            and os.readlink(link_path) == link_text
            and link_path.resolve(strict=True) == target_path,
            f"R16 original link/target changed while being checked: {name}",
        )
        snapshots[name] = raw
    return snapshots


_OUTPUT_RUNTIME_FILES = (
    "__init__.py",
    "studio_spike.py",
    "text_plus_template.py",
    "workflow_package.py",
    "workflow_delivery.py",
    "workflow_launcher.py",
    "workflow_v2.py",
    "workflow_v2_launcher.py",
    "native_qualification_v2.py",
    "target_identity_v2.py",
    "qualification_output_native_v2.py",
    "qualification_output_records_v2.py",
)


def _verify_installed_release(
    request: dict[str, Any], *, current: bool
) -> dict[str, Any]:
    release_raw, release_sha, _ = _read_ref(
        request["release"], "normalized installed release"
    )
    release = _shape(
        _parse(release_raw),
        frozenset({"schemaVersion", "lane", "files"}),
        "normalized release",
    )
    _require(
        release["schemaVersion"] == "qualification-output-release/v1"
        and release["lane"] == LANE,
        "unsupported normalized installed release",
    )
    _require(type(release["files"]) is dict, "installed release file map required")
    source_raw, source_sha, _ = _read_ref(request["sourceGraph"], "native source graph")
    source_graph = _parse(source_raw)
    _require(
        type(source_graph) is dict and source_graph == release["files"],
        "source graph/release inventory differs",
    )
    expected_paths = {
        f"vera-delivery-v2/python/vera_timeline_agent/{name}"
        for name in _OUTPUT_RUNTIME_FILES
    } | {"VERA Delivery v2.py"}
    _require(
        set(release["files"]) == expected_paths,
        "installed sibling runtime closure differs",
    )
    for path, digest in release["files"].items():
        _identity(path)
        _digest(digest)
    if current:
        root = NATIVE_RELEASE_ROOT.parent
        manifest_path = NATIVE_RELEASE_ROOT / "release.json"
        raw_manifest = _read(manifest_path, "installed release manifest")
        _require(
            _hash(raw_manifest) == request["releaseManifestSha256"],
            "raw installed release manifest differs",
        )
        manifest = _shape(
            _parse(raw_manifest),
            frozenset({"schemaVersion", "deliveryVersion", "sourcePins", "files"}),
            "installed release manifest",
        )
        _require(
            manifest["schemaVersion"] == "vera-injected-delivery-release/v2"
            and manifest["deliveryVersion"] == "2",
            "unsupported installed release manifest",
        )
        rows = manifest["files"]
        _require(type(rows) is list, "installed release inventory required")
        observed: dict[str, str] = {}
        for row in rows:
            entry = _shape(
                row,
                frozenset({"path", "sha256", "sizeBytes"}),
                "installed release row",
            )
            path = entry["path"]
            _require(path not in observed, "duplicate installed release path")
            _digest(entry["sha256"])
            file_path = _path(str(root / path), "installed release source")
            file_digest, size = _hash_file(file_path)
            _require(
                (file_digest, size) == (entry["sha256"], entry["sizeBytes"]),
                "installed source bytes differ from release manifest",
            )
            observed[path] = file_digest
        _require(observed == release["files"], "raw/normalized release maps differ")
    _require(
        release_sha == request["context"]["installedReleaseSha256"]
        and source_sha == request["context"]["nativeSourceGraphSha256"],
        "installed release/source graph context differs",
    )
    return release


def _publish(path: Path, value: dict[str, Any]) -> Path:
    path = _path(str(path), "native record")
    raw = _canonical(value)
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
        os.fchmod(stream.fileno(), 0o400)
    directory = os.open(path.parent, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return path


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _private_effect(
    state: dict[str, Any], method: str, arguments: Any
) -> dict[str, Any]:
    _require(
        method in ALLOWED_EFFECT_METHODS,
        "native effect is outside the closed method set",
    )
    index = len(state["effects"])
    directory = Path(state["request"]["resultPath"]).parent / "effects"
    directory.mkdir(mode=0o700, exist_ok=True)
    _require(not directory.is_symlink(), "native effects directory is a symlink")
    argument_hash = _payload_hash(arguments)
    effect_id = _hash(
        _canonical(
            {
                "operationId": state["request"]["operationId"],
                "index": index,
                "method": method,
                "argumentsSha256": argument_hash,
            }
        )
    )
    value = {
        "schemaVersion": EFFECT_SCHEMA,
        "lane": LANE,
        "chainKey": _chain_key(state["request"]["context"]),
        "context": state["request"]["context"],
        "operationId": state["request"]["operationId"],
        "operationSequence": state["request"]["sequence"],
        "effectIndex": index,
        "effectId": effect_id,
        "method": method,
        "argumentsSha256": argument_hash,
        "authoritySha256": state["authoritySha256"],
        "parentIntentSha256": state["intentSha256"],
        "createdAt": _timestamp(),
    }
    path = directory / f"{index:04d}-intent.json"
    _publish(path, value)
    row = {
        "index": index,
        "path": str(path),
        "sha256": _hash(_canonical(value)),
        "method": method,
        "argumentsSha256": argument_hash,
        "outcome": "unknown",
        "observedSha256": None,
    }
    state["effects"].append(row)
    return row


def _effect_observed(
    state: dict[str, Any], row: dict[str, Any], observation: Any
) -> None:
    request = state["request"]
    effects = state["effects"]
    index = row["index"]
    _require(
        type(effects) is list
        and type(index) is int
        and 0 <= index < len(effects)
        and effects[index] is row
        and row["outcome"] == "unknown"
        and row["observedSha256"] is None,
        "native effect observation is out of order or already recorded",
    )
    directory = Path(request["resultPath"]).parent / "effects"
    intent_path = _path(row["path"], "native effect intent")
    _require(
        intent_path == directory / f"{index:04d}-intent.json",
        "native effect observation intent path differs",
    )
    intent_raw = _read(intent_path, "native effect intent")
    _immutable(intent_path, "native effect intent")
    _require(_hash(intent_raw) == row["sha256"], "native effect intent changed")
    effect = _shape(_parse(intent_raw), EFFECT_FIELDS, "native effect intent")
    _require(
        effect["chainKey"] == _chain_key(request["context"])
        and effect["context"] == request["context"]
        and effect["operationId"] == request["operationId"]
        and effect["operationSequence"] == request["sequence"]
        and effect["effectIndex"] == index
        and effect["method"] == row["method"]
        and effect["argumentsSha256"] == row["argumentsSha256"]
        and effect["authoritySha256"] == state["authoritySha256"]
        and effect["parentIntentSha256"] == state["intentSha256"],
        "native effect observation intent lineage differs",
    )
    observation_sha256 = _payload_hash(observation)
    observed_path = directory / f"{index:04d}-observed.json"
    _publish(
        observed_path,
        {
            "schemaVersion": EFFECT_OBSERVATION_SCHEMA,
            "lane": LANE,
            "chainKey": effect["chainKey"],
            "context": effect["context"],
            "operationId": effect["operationId"],
            "operationSequence": effect["operationSequence"],
            "effectIndex": index,
            "effectId": effect["effectId"],
            "intentSha256": row["sha256"],
            "observedAt": _timestamp(),
            "observation": observation,
        },
    )
    row["observedSha256"] = observation_sha256
    row["outcome"] = "observed"


def _require_api(value: Any, names: tuple[str, ...], label: str) -> None:
    _require(value is not None, f"{label} is unavailable")
    for name in names:
        _require(
            callable(getattr(value, name, None)),
            f"required native getter/setter {label}.{name} unavailable",
        )


def _native_identity(value: Any) -> dict[str, Any]:
    identity = _shape(value, NATIVE_IDENTITY_FIELDS, "native runtime identity")
    version = identity["version"]
    _require(
        type(identity["product"]) is str
        and 0 < len(identity["product"]) <= 256
        and "studio" in identity["product"].casefold()
        and type(version) is list
        and version == [21, 1, 1, 10, ""]
        and all(type(part) is int for part in version[:4])
        and type(version[4]) is str
        and type(identity["python"]) is str
        and 0 < len(identity["python"].strip()) <= 128,
        "unsupported or incomplete native runtime identity",
    )
    return identity


def _verify_native_identity_continuity(previous: Any, current: Any) -> None:
    _require(
        _native_identity(previous) == _native_identity(current),
        "native runtime identity changed between native stages",
    )


def _connected(resolve: Any) -> dict[str, Any]:
    _require_api(
        resolve, ("GetProductName", "GetVersion", "GetProjectManager"), "Resolve"
    )
    product = resolve.GetProductName()
    version = resolve.GetVersion()
    _require(
        type(product) is str and "studio" in product.casefold(),
        "Resolve Studio identity unavailable",
    )
    _require(
        type(version) in {tuple, list} and len(version) == 5,
        "Resolve version identity unavailable",
    )
    _require(
        tuple(version) == (21, 1, 1, 10, ""),
        "unsupported Resolve build; expected Studio 21.1.1 build 10",
    )
    identity = {
        "product": product,
        "version": list(version),
        "python": sys.version.split()[0],
    }
    return _native_identity(identity)


def _project_timeline(resolve: Any, request: dict[str, Any]) -> tuple[Any, Any, Any]:
    manager = resolve.GetProjectManager()
    _require_api(
        manager,
        ("GetCurrentProject", "SaveProject", "CloseProject", "LoadProject"),
        "ProjectManager",
    )
    project = manager.GetCurrentProject()
    _require_api(
        project,
        (
            "GetUniqueId",
            "GetName",
            "GetCurrentTimeline",
            "GetMediaPool",
            "GetSetting",
            "SetSetting",
        ),
        "Project",
    )
    timeline = project.GetCurrentTimeline()
    _require_api(
        timeline,
        (
            "GetUniqueId",
            "GetName",
            "GetStartFrame",
            "GetEndFrame",
            "GetTrackCount",
            "GetTrackName",
            "GetItemListInTrack",
            "GetIsTrackEnabled",
            "GetIsTrackLocked",
            "GetMarkers",
            "GetMarkerCustomData",
            "GetSetting",
            "SetStartTimecode",
            "AddTrack",
            "SetTrackName",
            "AddMarker",
        ),
        "Timeline",
    )
    target = request["target"]
    _require(
        project.GetUniqueId() == target["projectUid"]
        and timeline.GetUniqueId() == target["timelineUid"],
        "current project/timeline UID differs from the reviewed target",
    )
    _require(
        project.GetName() == target["projectName"]
        and timeline.GetName() == target["timelineName"],
        "current project/timeline name differs from the reviewed target",
    )
    return manager, project, timeline


def _required_track_counts(view: dict[str, Any]) -> dict[str, int]:
    tracks = view.get("tracks")
    _require(type(tracks) is list, "admitted track inventory is unavailable")
    assert type(tracks) is list
    counts = {"video": 0, "audio": 0, "subtitle": 0}
    slots: set[tuple[str, int]] = set()
    for track in tracks:
        _require(type(track) is dict, "admitted track row is unavailable")
        kind = track.get("kind")
        index = track.get("index")
        _require(
            kind in {"video", "audio"}
            and type(index) is int
            and 1 <= index <= MAX_TRACKS,
            "unsupported admitted track",
        )
        assert type(kind) is str and type(index) is int
        slot = (kind, index)
        _require(slot not in slots, "duplicate admitted track slot")
        slots.add(slot)
        counts[kind] = max(counts[kind], index)
    for kind in ("video", "audio"):
        _require(
            {index for track_kind, index in slots if track_kind == kind}
            == set(range(1, counts[kind] + 1)),
            "admitted track indices are not contiguous",
        )
    return counts


def _check_empty_target(
    project: Any, timeline: Any, required_track_counts: dict[str, int]
) -> int:
    start_frame = timeline.GetStartFrame()
    _require(
        type(start_frame) is int and start_frame >= 0,
        "target timeline start frame is unreadable or invalid",
    )
    assert type(start_frame) is int
    _require_api(project.GetMediaPool(), ("ImportMedia", "GetRootFolder"), "MediaPool")
    for kind in ("video", "audio", "subtitle"):
        count = timeline.GetTrackCount(kind)
        _require(
            type(count) is int and 0 <= count <= MAX_TRACKS,
            "target timeline track inventory is unreadable",
        )
        _require(
            (kind == "subtitle" and count == 0)
            or (kind != "subtitle" and count <= required_track_counts[kind]),
            "target timeline has unexpected or unsupported tracks",
        )
        for index in range(1, count + 1):
            items = timeline.GetItemListInTrack(kind, index)
            _require(
                type(items) in {list, tuple} and len(items) <= MAX_ITEMS,
                "target timeline track item inventory is unreadable",
            )
            _require(
                not items,
                "target timeline already contains items; refusing to overwrite",
            )
    markers = timeline.GetMarkers()
    _require(
        type(markers) is dict and not markers,
        "target timeline already has markers; refusing to overwrite",
    )
    _require_api(timeline, ("GetMediaPoolItem",), "target timeline")
    timeline_pool_item = timeline.GetMediaPoolItem()
    _require_api(
        timeline_pool_item, ("GetUniqueId",), "target timeline media-pool item"
    )
    timeline_pool_uid = timeline_pool_item.GetUniqueId()
    _require(
        type(timeline_pool_uid) is str and bool(timeline_pool_uid.strip()),
        "target timeline media-pool item identity is unreadable",
    )
    pool = project.GetMediaPool()
    root = pool.GetRootFolder()
    _require_api(root, ("GetClipList", "GetSubFolderList"), "MediaPool root folder")
    pending = [root]
    seen: set[str] = set()
    seen_media: set[str] = set()
    timeline_pool_item_count = 0
    while pending:
        folder = pending.pop()
        uid = folder.GetUniqueId()
        _require(
            type(uid) is str and bool(uid.strip()) and uid not in seen,
            "invalid/cyclic target media folders",
        )
        seen.add(uid)
        clips = folder.GetClipList()
        children = folder.GetSubFolderList()
        _require(
            type(clips) in {list, tuple},
            "incomplete target media item inventory",
        )
        _require(
            type(children) in {list, tuple}, "incomplete target media folder inventory"
        )
        for item in clips:
            _require_api(item, ("GetUniqueId",), "target media-pool item")
            item_uid = item.GetUniqueId()
            _require(
                type(item_uid) is str and bool(item_uid.strip()),
                "target media-pool item identity is unreadable",
            )
            _require(
                item_uid not in seen_media,
                "duplicate target media-pool item identity",
            )
            seen_media.add(item_uid)
            _require(
                item_uid == timeline_pool_uid,
                "target project already contains media; refusing to overwrite",
            )
            timeline_pool_item_count += 1
        pending.extend(children)
    _require(
        timeline_pool_item_count == 1,
        "target timeline media-pool item is missing from project inventory",
    )
    return start_frame


def _source_hash(value: Any) -> str:
    _require(type(value) is str, "source content hash required")
    return _digest(value.removeprefix("sha256:"))


def _admitted_media_path(admitted: dict[str, Any], source: dict[str, Any]) -> Path:
    root = _path(str(admitted["sourceRoot"]), "admitted media root")
    relative = source["path"]
    _require(
        type(relative) is str
        and bool(relative)
        and "\\" not in relative
        and not Path(relative).is_absolute()
        and all(part not in {"", ".", ".."} for part in relative.split("/")),
        "admitted media path must be a safe package-relative path",
    )
    candidate = _path(str(root / relative), "admitted media source")
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve(strict=True)
    _require(
        resolved.is_relative_to(resolved_root) and resolved.is_file(),
        "admitted media source escaped its verified package",
    )
    return resolved


def _rate_float(rate: dict[str, Any]) -> float:
    _shape(rate, "numerator denominator", "timeline rate")
    numerator = _integer(rate["numerator"], 1)
    denominator = _integer(rate["denominator"], 1)
    _require(
        (numerator, denominator) == (24000, 1001),
        "only the exact 24000/1001 qualification rate is admitted",
    )
    return 23.976


def _project_settings(manifest: dict[str, Any]) -> dict[str, str]:
    timeline = manifest["timeline"]
    return {
        "timelineFrameRate": "23.976",
        "timelineResolutionWidth": str(_integer(timeline["width"], 1, 16384)),
        "timelineResolutionHeight": str(_integer(timeline["height"], 1, 16384)),
        "timelineSampleRate": str(_integer(timeline["audioSampleRate"], 1)),
    }


def _event_stamp(event: dict[str, Any]) -> str:
    _require(type(event.get("v2Event")) is dict, "accepted v2 event stamp unavailable")
    digest = _hash(_canonical(event["v2Event"]))
    return json.dumps(
        {"v2EventId": event["id"], "v2EventSha256": digest},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _marker_stamp(marker: dict[str, Any]) -> str:
    _require(
        type(marker.get("provenance")) is dict,
        "accepted v2 marker provenance unavailable",
    )
    digest = _hash(_canonical(marker["provenance"]))
    return json.dumps(
        {"v2EventId": marker["id"], "v2EventSha256": digest},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _capture_geometry(
    resolve: Any,
    request: dict[str, Any],
    admitted: dict[str, Any],
    input_binding: dict[str, Any] | None,
) -> dict[str, Any]:
    _, _, timeline = _project_timeline(resolve, request)
    manifest, view = admitted["manifest"], admitted["view"]
    expected_timeline = manifest["timeline"]
    _verify_admitted_extent(manifest)
    rate = expected_timeline["frameRate"]
    _rate_float(rate)
    _require(
        timeline.GetSetting("timelineFrameRate") == "23.976",
        "native timeline rate getter differs",
    )
    for key, expected in (
        ("timelineResolutionWidth", expected_timeline["width"]),
        ("timelineResolutionHeight", expected_timeline["height"]),
        ("timelineSampleRate", expected_timeline["audioSampleRate"]),
    ):
        actual = timeline.GetSetting(key)
        _require(
            type(actual) in {str, int}
            and str(actual).isdigit()
            and int(actual) == expected,
            f"native timeline setting {key} differs or is unreadable",
        )
    timeline_start = timeline.GetStartFrame()
    timeline_end = timeline.GetEndFrame()
    _require(
        type(timeline_start) is int
        and timeline_start == expected_timeline["startFrame"],
        "native timeline start differs",
    )
    _require(
        type(timeline_end) is int
        and timeline_end == timeline_start + expected_timeline["durationFrames"],
        "native timeline extent differs",
    )

    track_by_slot = {(row["kind"], row["index"]): row for row in view["tracks"]}
    tracks: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    sources = {row["id"]: row for row in view["sources"]}
    source_paths = {
        str(_admitted_media_path(admitted, row)): row for row in view["sources"]
    }
    expected_events = {row["id"]: row for row in view["events"]}
    event_ids: set[str] = set()
    item_objects: dict[str, Any] = {}
    raw_links: dict[str, list[str]] = {}
    source_entries: dict[str, dict[str, Any]] = {}
    native_sources: dict[str, str] = {}
    if input_binding is not None:
        for row in input_binding["sourceEntries"]:
            entry = _shape(row, SOURCE_FIELDS, "input source entry")
            source_entries[entry["sourceId"]] = entry
        for row in input_binding["nativeSources"]:
            entry = _shape(
                row,
                frozenset({"sourceId", "nativeSourceSha256"}),
                "native source pin",
            )
            native_sources[entry["sourceId"]] = _digest(entry["nativeSourceSha256"])
        _require(
            set(native_sources) == set(sources),
            "native source binding inventory differs",
        )
        _require(
            input_binding["context"] == request["context"],
            "input binding context differs",
        )

    for kind in ("video", "audio", "subtitle"):
        count = timeline.GetTrackCount(kind)
        _require(
            type(count) is int and 0 <= count <= 32,
            "unsupported/incomplete track count",
        )
        _require(
            kind != "subtitle" or count == 0, "subtitle track inventory is not admitted"
        )
        expected_count = max(
            (index for k, index in track_by_slot if k == kind), default=0
        )
        _require(count == expected_count, f"native {kind} track inventory differs")
        for index in range(1, count + 1):
            spec = track_by_slot.get((kind, index))
            _require(spec is not None, "unmapped native track")
            assert spec is not None
            enabled, locked = (
                timeline.GetIsTrackEnabled(kind, index),
                timeline.GetIsTrackLocked(kind, index),
            )
            _require(
                enabled is True and type(locked) is bool,
                "disabled/unreadable native track state",
            )
            name = timeline.GetTrackName(kind, index)
            _require(name == spec["name"], "native track name differs")
            tracks.append(
                {
                    "trackId": spec["id"],
                    "kind": kind,
                    "index": index,
                    "name": name,
                    "enabled": enabled,
                    "locked": locked,
                }
            )
            actual_items = timeline.GetItemListInTrack(kind, index)
            _require(
                type(actual_items) in {list, tuple} and len(actual_items) <= MAX_ITEMS,
                "native item inventory unavailable/oversized",
            )
            for item in actual_items:
                _require_api(
                    item,
                    (
                        "GetUniqueId",
                        "GetStart",
                        "GetDuration",
                        "GetEnd",
                        "GetSourceStartFrame",
                        "GetSourceEndFrame",
                        "GetLinkedItems",
                        "GetClipEnabled",
                        "GetSpeed",
                        "GetMediaPoolItem",
                        "GetMarkerCustomData",
                        "GetProperties",
                    ),
                    "TimelineItem",
                )
                uid = item.GetUniqueId()
                _identity(uid)
                _require(uid not in item_objects, "duplicate native item UID")
                custom = item.GetMarkerCustomData(0)
                _require(type(custom) is str, "native event stamp is unreadable")
                stamp = _shape(
                    _parse(custom.encode("utf-8")),
                    frozenset({"v2EventId", "v2EventSha256"}),
                    "native event stamp",
                )
                event_id = _identity(stamp["v2EventId"])
                event = expected_events.get(event_id)
                _require(
                    event is not None and event_id not in event_ids,
                    "missing/duplicate/unadmitted native event stamp",
                )
                assert event is not None
                event_ids.add(event_id)
                _require(
                    custom == _event_stamp(event), "native event stamp digest differs"
                )
                _require(
                    event["trackId"] == spec["id"] and event["trackKind"] == kind,
                    "native event landed on wrong track",
                )
                media = item.GetMediaPoolItem()
                _require_api(
                    media,
                    ("GetUniqueId", "GetMediaId", "GetClipProperty"),
                    "MediaPoolItem",
                )
                media_uid = _identity(media.GetUniqueId())
                props = media.GetClipProperty()
                _require(
                    type(props) is dict and props.get("Online Status") == "Online",
                    "native source is offline or online status getter is missing",
                )
                assert type(props) is dict
                media_path = props.get("File Path")
                _require(type(media_path) is str, "native source path is unreadable")
                assert type(media_path) is str
                source = source_paths.get(str(Path(media_path).resolve()))
                _require(
                    source is not None,
                    "native source path is outside the admitted package",
                )
                assert source is not None
                source_id = source["id"]
                _require(
                    _hash_file(Path(media_path))[0]
                    == _source_hash(source["contentHash"]),
                    "native media source bytes differ",
                )
                record_start = item.GetStart(False)
                duration = item.GetDuration(False)
                record_end = item.GetEnd(False)
                source_start = item.GetSourceStartFrame()
                source_end = item.GetSourceEndFrame()
                _require(
                    all(
                        type(value) is int
                        for value in (
                            record_start,
                            duration,
                            record_end,
                            source_start,
                            source_end,
                        )
                    )
                    and duration > 0
                    and record_end - record_start in {duration, duration - 1}
                    and source_end >= source_start,
                    "unsupported native range getter",
                )
                _require(
                    all(
                        getattr(item, method)(True) == observed
                        for method, observed in (
                            ("GetStart", record_start),
                            ("GetDuration", duration),
                            ("GetEnd", record_end),
                        )
                    ),
                    "unsupported fractional native record geometry",
                )
                _require(
                    timeline_start
                    <= record_start
                    < record_start + duration
                    <= timeline_end,
                    "native item lies outside programme extent",
                )
                speed = item.GetSpeed()
                speed = _shape(
                    speed,
                    "Percentage PitchCorrection StretchKeyframesToFit RippleTimeline",
                    "native speed options",
                )
                _require(
                    type(speed["Percentage"]) in {int, float}
                    and speed["Percentage"] == 100
                    and type(speed["PitchCorrection"]) is bool
                    and type(speed["StretchKeyframesToFit"]) is bool
                    and speed["StretchKeyframesToFit"] is False
                    and type(speed["RippleTimeline"]) is bool
                    and speed["RippleTimeline"] is False,
                    "non-unit/unreadable native speed",
                )
                _require(item.GetClipEnabled() is True, "disabled native item")
                record = event["recordRange"]
                _require(
                    record_start == record["startFrame"]
                    and duration == record["durationFrames"],
                    "native record range differs",
                )
                source_range = event.get("sourceRange")
                if source_range is None:
                    expected_source_start = 0
                    expected_source_duration = duration
                else:
                    source_range = _shape(
                        source_range,
                        frozenset({"startFrame", "durationFrames"}),
                        "native source range",
                    )
                    expected_source_start = source_range["startFrame"]
                    expected_source_duration = source_range["durationFrames"]
                _require(
                    source_start == expected_source_start
                    and source_end + 1 - source_start == expected_source_duration,
                    "native source range differs",
                )
                if event.get("kind") == "source_audio":
                    gain = event.get("gainDb")
                    properties = item.GetProperties()
                    _require(
                        type(properties) is dict,
                        "native source-audio properties are unreadable",
                    )
                    assert type(properties) is dict
                    _require(
                        type(gain) in {int, float}
                        and properties.get("AudioVolumeEnabled") is True
                        and type(properties.get("AudioVolume")) in {int, float}
                        and properties["AudioVolume"] == gain,
                        "reopened source-audio controls differ",
                    )
                linked = item.GetLinkedItems()
                _require(
                    type(linked) in {list, tuple}, "native link getter unavailable"
                )
                linked_uids = sorted(_identity(peer.GetUniqueId()) for peer in linked)
                _require(
                    len(linked_uids) == len(set(linked_uids))
                    and uid not in linked_uids,
                    "invalid native link inventory",
                )
                mapping_sha = None
                if input_binding is not None:
                    mapping_sha = (
                        source_entries.get(source_id, {}).get("pcmMappingSha256")
                        if kind == "audio"
                        else native_sources[source_id]
                    )
                    _require(
                        mapping_sha is not None, "audio source mapping unavailable"
                    )
                item_objects[uid] = item
                raw_links[uid] = linked_uids
                items.append(
                    {
                        "itemUid": uid,
                        "eventId": event_id,
                        "sourceId": source_id,
                        "mediaUid": media_uid,
                        "kind": kind,
                        "trackId": spec["id"],
                        "recordStart": record_start,
                        "recordDuration": duration,
                        "sourceStart": source_start,
                        "sourceDuration": source_end + 1 - source_start,
                        "linkedItemUids": linked_uids,
                        "online": True,
                        "enabled": True,
                        "speed": {"numerator": 1, "denominator": 1},
                        "sourceMappingSha256": mapping_sha,
                    }
                )
    _require(event_ids == set(expected_events), "native event inventory is incomplete")
    known_uids = set(item_objects)
    _require(
        all(set(values) <= known_uids for values in raw_links.values()),
        "native link points outside the timeline inventory",
    )
    for uid, values in raw_links.items():
        _require(
            all(uid in raw_links[peer] for peer in values),
            "native links are not reciprocal",
        )
    expected_markers: dict[int, dict[str, Any]] = {}
    for marker in view["markers"]:
        frame = _integer(marker["frame"])
        color = _MARKER_COLORS.get(str(marker["color"]).upper())
        _require(
            color is not None and frame not in expected_markers,
            "unsupported/duplicate admitted timeline marker",
        )
        expected_markers[frame] = {
            "color": color,
            "name": marker["name"],
            "note": marker["note"],
            "duration": 1,
            "customData": _marker_stamp(marker),
        }
    actual_markers = timeline.GetMarkers()
    _require(
        type(actual_markers) is dict and set(actual_markers) == set(expected_markers),
        "native timeline marker inventory differs",
    )
    for frame, expected in expected_markers.items():
        props = actual_markers[frame]
        _require(
            type(props) is dict
            and all(
                props.get(key) == value
                for key, value in expected.items()
                if key != "customData"
            )
            and timeline.GetMarkerCustomData(frame) == expected["customData"],
            "native timeline marker readback differs",
        )
    tracks.sort(key=lambda row: row["trackId"])
    items.sort(key=lambda row: (row["recordStart"], row["itemUid"]))
    source_mappings = []
    if input_binding is not None:
        source_mappings = sorted(
            [
                {
                    "sourceId": row["sourceId"],
                    "nativeSourceSha256": native_sources[row["sourceId"]],
                    "sourceEntrySha256": _hash(_canonical(row)),
                }
                for row in source_entries.values()
            ],
            key=lambda row: row["sourceId"],
        )
        _require(
            tracks == input_binding["tracks"],
            "native tracks differ from immutable input binding",
        )
        mappings = sorted(
            [
                {
                    "itemUid": row["itemUid"],
                    "eventId": row["eventId"],
                    "sourceId": row["sourceId"],
                    "mediaUid": row["mediaUid"],
                }
                for row in items
            ],
            key=lambda row: row["itemUid"],
        )
        _require(
            mappings == input_binding["itemMappings"],
            "native item UID mapping differs from immutable input binding",
        )
        _require(
            source_mappings
            == [
                {
                    "sourceId": row["sourceId"],
                    "nativeSourceSha256": row["nativeSourceSha256"],
                    "sourceEntrySha256": _hash(_canonical(row)),
                }
                for row in input_binding["sourceEntries"]
            ],
            "native source mapping differs from immutable input binding",
        )
    else:
        # Construction readback only supplies the mapping that the host needs to
        # freeze the later input binding; audio mapping provenance arrives there.
        items = [{**row, "sourceMappingSha256": None} for row in items]
    geometry = {
        "context": request["context"],
        "extentFrames": expected_timeline["durationFrames"],
        "rate": rate,
        "tracks": tracks,
        "items": items,
        "sourceMappings": source_mappings,
    }
    return geometry


def _set_project_settings(
    project: Any, settings: dict[str, str], state: dict[str, Any]
) -> None:
    for key, value in settings.items():
        current = project.GetSetting(key)
        if current == value:
            continue
        row = _private_effect(state, "Project.SetSetting", {"key": key, "value": value})
        returned = project.SetSetting(key, value)
        _require(returned is True, f"Resolve refused project setting {key}")
        _require(
            project.GetSetting(key) == value,
            f"project setting {key} did not read back",
        )
        _effect_observed(
            state, row, {"return": returned, "value": project.GetSetting(key)}
        )


def _normalize_target_start_timecode(
    timeline: Any, start_frame: int, state: dict[str, Any]
) -> None:
    if start_frame == 0:
        return
    row = _private_effect(
        state, "Timeline.SetStartTimecode", {"timecode": "00:00:00:00"}
    )
    returned = timeline.SetStartTimecode("00:00:00:00")
    _require(returned is True, "Resolve refused target timeline start timecode")
    readback = timeline.GetStartFrame()
    _require(
        type(readback) is int and readback == 0,
        "target timeline start timecode did not reset to frame zero",
    )
    _effect_observed(state, row, {"return": returned, "startFrame": readback})


def _construct(
    resolve: Any,
    request: dict[str, Any],
    admitted: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    connected = _connected(resolve)
    _, project, timeline = _project_timeline(resolve, request)
    manifest, view = admitted["manifest"], admitted["view"]
    required_track_counts = _required_track_counts(view)
    start_frame = _check_empty_target(project, timeline, required_track_counts)
    _normalize_target_start_timecode(timeline, start_frame, state)
    pool = project.GetMediaPool()
    settings = _project_settings(manifest)
    _set_project_settings(project, settings, state)
    sources = view["sources"]
    source_paths = [str(_admitted_media_path(admitted, source)) for source in sources]
    row = _private_effect(state, "MediaPool.ImportMedia", {"paths": source_paths})
    imported = pool.ImportMedia(source_paths)
    _require(
        type(imported) in {list, tuple} and len(imported) == len(sources),
        "Resolve did not import one item per admitted source",
    )
    media_by_path: dict[str, Any] = {}
    for item in imported:
        props = item.GetClipProperty()
        _require(
            type(props) is dict and props.get("Online Status") == "Online",
            "imported media is offline or incomplete",
        )
        item_path = props.get("File Path")
        _require(type(item_path) is str, "imported media path getter unavailable")
        resolved = str(Path(item_path).resolve())
        _require(resolved not in media_by_path, "duplicate imported source path")
        media_by_path[resolved] = item
    _require(
        set(media_by_path) == set(source_paths),
        "Resolve imported different source files",
    )
    source_by_id = {source["id"]: source for source in sources}
    media_by_source = {
        source["id"]: media_by_path[path]
        for source, path in zip(sources, source_paths, strict=True)
    }
    media_uids: dict[str, str] = {}
    for source_id, media in media_by_source.items():
        uid = _identity(media.GetUniqueId())
        _require(
            _hash_file(Path(media.GetClipProperty()["File Path"]))[0]
            == _source_hash(source_by_id[source_id]["contentHash"]),
            "imported source bytes differ",
        )
        media_uids[source_id] = uid
    _effect_observed(
        state, row, {"paths": sorted(media_by_path), "mediaUids": media_uids}
    )
    track_ids: dict[str, dict[str, Any]] = {}
    for track in view["tracks"]:
        _identity(track["id"])
        _require(
            track["kind"] in {"video", "audio"}
            and type(track["index"]) is int
            and track["index"] >= 1,
            "unsupported admitted track",
        )
        track_ids[track["id"]] = track
    _require(len(track_ids) == len(view["tracks"]), "duplicate admitted track")
    for kind in ("video", "audio"):
        for track in sorted(
            (t for t in view["tracks"] if t["kind"] == kind), key=lambda t: t["index"]
        ):
            while timeline.GetTrackCount(kind) < track["index"]:
                args = {"kind": kind, "subtype": "stereo" if kind == "audio" else None}
                row = _private_effect(state, "Timeline.AddTrack", args)
                created = (
                    timeline.AddTrack(kind, "stereo")
                    if kind == "audio"
                    else timeline.AddTrack(kind)
                )
                _require(created is True, f"Resolve refused {kind} track creation")
                _effect_observed(
                    state,
                    row,
                    {"return": created, "trackCount": timeline.GetTrackCount(kind)},
                )
            row = _private_effect(
                state,
                "Timeline.SetTrackName",
                {"kind": kind, "index": track["index"], "name": track["name"]},
            )
            named = timeline.SetTrackName(kind, track["index"], track["name"])
            _require(
                named is True
                and timeline.GetTrackName(kind, track["index"]) == track["name"],
                "native track name was not retained",
            )
            _effect_observed(
                state,
                row,
                {"return": named, "name": timeline.GetTrackName(kind, track["index"])},
            )
    for event in view["events"]:
        track = track_ids[event["trackId"]]
        source = source_by_id[event["sourceId"]]
        media = media_by_source[event["sourceId"]]
        record = event["recordRange"]
        source_range = event.get("sourceRange")
        source_start = 0 if source_range is None else source_range["startFrame"]
        duration = (
            record["durationFrames"]
            if source_range is None
            else source_range["durationFrames"]
        )
        still = source.get("kind") in {"still", "placeholder"} or event.get("kind") in {
            "still",
            "placeholder",
        }
        marked = False
        if still:
            row = _private_effect(
                state,
                "MediaPoolItem.SetMarkInOut",
                {
                    "sourceId": event["sourceId"],
                    "start": source_start,
                    "end": source_start + duration,
                    "mediaType": "video",
                },
            )
            marked_ok = media.SetMarkInOut(
                source_start, source_start + duration, "video"
            )
            _require(marked_ok is True, "still source mark range was refused")
            marked = True
            _effect_observed(state, row, {"return": marked_ok})
        append_row: dict[str, Any] | None = None
        try:
            # The pinned 21.1.1/10 workflow uses zero still compensation; readback
            # below must prove the authored duration before this stage completes.
            info = {
                "mediaPoolItem": media,
                "startFrame": source_start,
                "endFrame": source_start + duration,
                "mediaType": 2 if track["kind"] == "audio" else 1,
                "trackIndex": track["index"],
                "recordFrame": record["startFrame"],
            }
            append_row = _private_effect(
                state,
                "MediaPool.AppendToTimeline",
                {
                    "eventId": event["id"],
                    "sourceId": event["sourceId"],
                    "trackId": event["trackId"],
                    "recordFrame": record["startFrame"],
                    "sourceStart": source_start,
                    "sourceDuration": duration,
                },
            )
            placed = pool.AppendToTimeline([info])
        finally:
            if marked:
                row = _private_effect(
                    state,
                    "MediaPoolItem.ClearMarkInOut",
                    {"sourceId": event["sourceId"], "mediaType": "video"},
                )
                cleared = media.ClearMarkInOut("video")
                _require(cleared is True, "still media mark range could not be cleared")
                _effect_observed(state, row, {"return": cleared})
        _require(
            type(placed) in {list, tuple} and len(placed) == 1,
            "Resolve did not append exactly one admitted event",
        )
        item = placed[0]
        _require(append_row is not None, "native append intent is missing")
        _effect_observed(
            state,
            append_row,
            {"itemUid": _identity(item.GetUniqueId()), "returnCount": len(placed)},
        )
        stamp = _event_stamp(event)
        row = _private_effect(
            state,
            "TimelineItem.AddMarker",
            {
                "itemUid": item.GetUniqueId(),
                "eventId": event["id"],
                "frame": 0,
                "stampSha256": _hash(stamp.encode("utf-8")),
            },
        )
        stamped = item.AddMarker(0, "Cyan", "VERA v2 event", event["id"], 1, stamp)
        _require(
            stamped is True and item.GetMarkerCustomData(0) == stamp,
            "event provenance marker did not read back",
        )
        _effect_observed(
            state,
            row,
            {
                "return": stamped,
                "customDataSha256": _hash(item.GetMarkerCustomData(0).encode("utf-8")),
            },
        )
        if event.get("kind") == "source_audio":
            gain = event.get("gainDb")
            _require(type(gain) in {int, float}, "source-audio gain is missing")
            properties = {"AudioVolumeEnabled": True, "AudioVolume": gain}
            row = _private_effect(
                state,
                "TimelineItem.SetProperties",
                {"eventId": event["id"], "properties": properties},
            )
            updated = item.SetProperties(properties)
            actual = item.GetProperties()
            _require(
                updated is True
                and type(actual) is dict
                and actual.get("AudioVolumeEnabled") is True
                and actual.get("AudioVolume") == gain,
                "source-audio controls did not read back",
            )
            _effect_observed(
                state,
                row,
                {
                    "return": updated,
                    "properties": {key: actual.get(key) for key in properties},
                },
            )
    for marker in view["markers"]:
        color = _MARKER_COLORS.get(str(marker["color"]).upper())
        _require(color is not None, "unsupported admitted timeline marker color")
        custom = _marker_stamp(marker)
        row = _private_effect(
            state,
            "Timeline.AddMarker",
            {
                "frame": marker["frame"],
                "id": marker["id"],
                "stampSha256": _hash(custom.encode("utf-8")),
            },
        )
        added = timeline.AddMarker(
            marker["frame"], color, marker["name"], marker["note"], 1, custom
        )
        _require(
            added is True and timeline.GetMarkerCustomData(marker["frame"]) == custom,
            "timeline marker did not read back",
        )
        _effect_observed(
            state,
            row,
            {
                "return": added,
                "customDataSha256": _hash(
                    timeline.GetMarkerCustomData(marker["frame"]).encode("utf-8")
                ),
            },
        )
    geometry = _capture_geometry(resolve, request, admitted, None)
    return {"nativeGeometry": geometry, "nativeIdentity": connected}


def _previous_result(
    request: dict[str, Any], action: str
) -> tuple[dict[str, Any], str, Path]:
    sequence = request["sequence"] - 1
    _require(
        sequence >= 0 and APPROVAL_ACTION_PLAN[sequence] == action,
        "native action order differs",
    )
    result_path = native_request_paths(request["context"], sequence)[0]
    raw = _read(result_path, "native predecessor")
    digest = _hash(raw)
    _require(digest == request["priorResultSha256"], "native predecessor hash differs")
    result = verify_native_result(result_path, digest)
    _require(
        result["status"] == "complete" and result["action"] == action,
        "complete native predecessor required",
    )
    return result, digest, result_path


def _verify_readonly_native_lineage(request: dict[str, Any]) -> None:
    if request["action"] == "poll_render":
        _previous_result(request, "start_render")
    elif request["action"] == "capture_post":
        _previous_result(request, "poll_render")


def _save_reopen(
    resolve: Any,
    request: dict[str, Any],
    admitted: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    previous, _, _ = _previous_result(request, "construct")
    manager, project, _ = _project_timeline(resolve, request)
    row = _private_effect(state, "ProjectManager.SaveProject", {})
    saved = manager.SaveProject()
    _require(saved is True, "Resolve did not save the populated qualification target")
    _effect_observed(state, row, {"return": saved})
    row = _private_effect(
        state,
        "ProjectManager.CloseProject",
        {"projectUid": request["target"]["projectUid"]},
    )
    closed = manager.CloseProject(project)
    _require(closed is True, "Resolve did not close the saved qualification target")
    _effect_observed(state, row, {"return": closed})
    row = _private_effect(
        state,
        "ProjectManager.LoadProject",
        {"projectName": request["target"]["projectName"]},
    )
    reopened = manager.LoadProject(request["target"]["projectName"])
    _require(
        reopened is not None, "Resolve did not reopen the saved qualification target"
    )
    _effect_observed(
        state,
        row,
        {"projectUid": reopened.GetUniqueId(), "projectName": reopened.GetName()},
    )
    geometry = _capture_geometry(resolve, request, admitted, None)
    _require(
        geometry == previous["nativeGeometry"],
        "saved/reopened native geometry differs from construction readback",
    )
    return {"nativeGeometry": geometry, "nativeIdentity": _connected(resolve)}


def _host_artifact(
    context: dict[str, Any], path_value: Any, sha_value: Any, label: str
) -> tuple[bytes, str, Path]:
    digest = _digest(sha_value)
    path = _path(path_value, label)
    expected = HOST_STATE_ROOT / _chain_key(context) / "artifacts" / digest
    _require(path == expected, f"{label} is outside the fixed host evidence vault")
    raw = _read(path, label, maximum=48_000_000)
    _require(_hash(raw) == digest, f"{label} digest differs")
    _immutable(path, label)
    return raw, digest, path


def _input_binding(request: dict[str, Any]) -> tuple[dict[str, Any], bytes, str, Path]:
    payload = request["payload"]
    raw, digest, path = _host_artifact(
        request["context"],
        payload["inputBindingPath"],
        payload["inputBindingSha256"],
        "input binding",
    )
    value = _shape(
        _parse(raw),
        frozenset(
            {
                "schemaVersion",
                "lane",
                "context",
                "delivery",
                "sourceEntries",
                "tracks",
                "itemMappings",
                "nativeSources",
            }
        ),
        "input binding",
    )
    _require(
        value["schemaVersion"] == "qualification-output-inputs/v1"
        and value["lane"] == LANE
        and value["context"] == request["context"],
        "input binding context/schema differs",
    )
    return value, raw, digest, path


def _verify_render_lineage(
    request: dict[str, Any],
    lineage: dict[str, Any],
    completion: dict[str, Any],
    completion_sha: str,
) -> None:
    _require(
        request["action"] == "capture_post"
        and request["sequence"] == len(APPROVAL_ACTION_PLAN) - 1,
        "render lineage is only valid at the fixed post-render stage",
    )
    queue_path = native_request_paths(request["context"], request["sequence"] - 3)[0]
    start_path = native_request_paths(request["context"], request["sequence"] - 2)[0]
    queue_raw = _read(queue_path, "native queue receipt")
    start_raw = _read(start_path, "native start receipt")
    queue_sha, start_sha = _hash(queue_raw), _hash(start_raw)
    queue = verify_native_result(queue_path, queue_sha)
    start = verify_native_result(start_path, start_sha)
    _require(
        all(
            result["status"] == "complete"
            and result["context"] == request["context"]
            and result["action"] == action
            for result, action in (
                (queue, "queue_render"),
                (start, "start_render"),
                (completion, "poll_render"),
            )
        ),
        "complete native queue/start/completion lineage required",
    )
    _require(
        lineage["effectReceiptSha256"] == queue_sha
        and lineage["startReceiptSha256"] == start_sha
        and lineage["completionReceiptSha256"] == completion_sha
        and start["queuedResultSha256"] == queue_sha
        and completion["queuedResultSha256"] == queue_sha
        and completion["startedResultSha256"] == start_sha,
        "render lineage receipt hashes differ from the fixed native chain",
    )
    for field in (
        "jobId",
        "outputPath",
        "settings",
        "commitmentRawSha256",
        "reservationSha256",
        "renderIntentSha256",
    ):
        _require(
            queue[field] == start[field] == completion[field],
            "native render stage binding differs",
        )
    _require(
        type(request["reservation"]) is dict
        and _digest(request["reservation"]["sha256"]) == lineage["reservationRawSha256"]
        and type(request["renderIntent"]) is dict
        and _digest(request["renderIntent"]["sha256"]) == lineage["renderIntentSha256"]
        and lineage["commitmentRawSha256"] == queue["commitmentRawSha256"]
        and lineage["reservationRawSha256"] == queue["reservationSha256"]
        and lineage["renderIntentSha256"] == queue["renderIntentSha256"]
        and lineage["jobId"] == queue["jobId"]
        and lineage["sourceOutputRawSha256"] == completion["sourceOutputRawSha256"],
        "host render lineage differs from the owned native reservation/job/output",
    )


def _capture(
    request: dict[str, Any], resolve: Any, admitted: dict[str, Any], *, phase: str
) -> dict[str, Any]:
    binding, _raw_binding, binding_sha, binding_path = _input_binding(request)
    geometry = _capture_geometry(resolve, request, admitted, binding)
    captured = _timestamp()
    envelope = {
        "schemaVersion": "qualification-output-geometry/v1",
        "lane": LANE,
        "geometry": geometry,
        "inputBindingSha256": binding_sha,
        "capturePhase": phase,
        "capturedAt": captured,
        "expiresAt": (datetime.now(UTC) + timedelta(seconds=MAX_LIFETIME_SECONDS))
        .isoformat()
        .replace("+00:00", "Z"),
    }
    extra: dict[str, Any] = {
        "inputBindingPath": str(binding_path),
        "inputBindingSha256": binding_sha,
    }
    if phase == "post_render":
        payload = request["payload"]
        lineage_raw, lineage_sha, lineage_path = _host_artifact(
            request["context"],
            payload["renderLineagePath"],
            payload["renderLineageSha256"],
            "render lineage",
        )
        lineage = _shape(
            _parse(lineage_raw),
            frozenset(
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
            ),
            "render lineage",
        )
        _require(
            lineage["schemaVersion"] == "qualification-output-lineage/v1"
            and lineage["lane"] == LANE
            and lineage["context"] == request["context"],
            "render lineage context differs",
        )
        completion_path = _path(
            payload["completionResultPath"], "render completion result"
        )
        expected_path = native_request_paths(
            request["context"], request["sequence"] - 1
        )[0]
        _require(
            completion_path == expected_path,
            "post-render capture must follow the fixed completion operation",
        )
        completion_raw = _read(completion_path, "native render completion")
        completion_sha = _hash(completion_raw)
        _require(
            completion_sha
            == _digest(payload["completionResultSha256"])
            == lineage["completionReceiptSha256"],
            "render completion lineage differs",
        )
        completion = verify_native_result(completion_path, completion_sha)
        _require(
            completion["action"] == "poll_render"
            and completion["status"] == "complete"
            and completion["context"] == request["context"],
            "actual completed native render required",
        )
        _verify_render_lineage(request, lineage, completion, completion_sha)
        _require(
            _time(captured, "post-render capture")
            >= _time(completion["completedAt"], "render completion"),
            "post-render capture precedes completion",
        )
        output_path = _path(completion["outputPath"], "rendered MOV")
        output_sha, _ = _hash_file(output_path)
        _require(
            output_sha == completion["sourceOutputRawSha256"],
            "rendered MOV changed before post-render capture",
        )
        extra.update(
            {
                "renderLineagePath": str(lineage_path),
                "renderLineageSha256": lineage_sha,
                "completionResultSha256": completion_sha,
                "sourceOutputRawSha256": output_sha,
                "jobId": completion["jobId"],
                "outputPath": str(output_path),
                "completedAt": completion["completedAt"],
            }
        )
    return {
        "nativeGeometry": geometry,
        "geometryEnvelope": envelope,
        "capturedAt": captured,
        "expiresAt": envelope["expiresAt"],
        **extra,
    }


def _queue_render(
    request: dict[str, Any],
    resolve: Any,
    admitted: dict[str, Any],
    state: dict[str, Any],
    reservation_sha: str | None,
) -> dict[str, Any]:
    _previous_result(request, "capture_pre")
    _, project, _ = _project_timeline(resolve, request)
    settings = request["payload"]["settings"]
    _require(
        settings
        == _expected_settings(
            _path(request["package"]["packageRoot"], "package root"), request["profile"]
        ),
        "render settings differ from admitted package",
    )
    render_ref = request["renderIntent"]
    render_raw, render_sha, _ = _read_ref(render_ref, "host render intent")
    render = verify_render_intent(
        render_raw,
        context=request["context"],
        commitment_sha256=_parse(
            _read(_path(request["reservation"]["path"], "reservation"), "reservation")
        )["commitmentRawSha256"],
        require_output_absent=True,
    )
    output_path = _path(request["payload"]["outputPath"], "MOV output")
    _require(
        str(output_path) == render["outputPath"]
        and request["payload"]["outputFilename"] == output_path.stem,
        "queue target differs from reviewed MOV output",
    )
    _require(not output_path.exists(), "render output already exists")
    formats = project.GetRenderFormats()
    _require(
        type(formats) is dict and formats.get("QuickTime") == "mov",
        "Resolve lacks the reviewed MOV container",
    )
    codecs = project.GetRenderCodecs("mov")
    _require(
        type(codecs) is dict
        and "ProRes 422" in codecs
        and str(codecs["ProRes 422"]).casefold() in {"prores422", "prores 422"},
        "Resolve lacks the exact ProRes 422 codec",
    )
    audio_codecs = project.GetAudioRenderCodecs("mov")
    _require(
        type(audio_codecs) is dict and audio_codecs.get("Linear PCM") == "lpcm",
        "Resolve lacks Linear PCM audio for MOV",
    )
    before = project.GetRenderJobList()
    _require(type(before) in {list, tuple}, "render queue readback is unavailable")
    before_ids = {row.get("JobId") for row in before if type(row) is dict}
    row = _private_effect(
        state,
        "Project.SetCurrentRenderFormatAndCodec",
        {"format": "mov", "codec": "prores422"},
    )
    selected = project.SetCurrentRenderFormatAndCodec("mov", "prores422")
    _require(
        selected is True
        and project.GetCurrentRenderFormatAndCodec()
        == {"format": "mov", "codec": "prores422"},
        "MOV/ProRes 422 selection did not read back",
    )
    _effect_observed(
        state,
        row,
        {"return": selected, "formatCodec": project.GetCurrentRenderFormatAndCodec()},
    )
    row = _private_effect(state, "Project.SetCurrentRenderMode", {"mode": 0})
    mode = project.SetCurrentRenderMode(0)
    _require(
        mode is True and project.GetCurrentRenderMode() == 0,
        "single-job render mode did not read back",
    )
    _effect_observed(
        state, row, {"return": mode, "renderMode": project.GetCurrentRenderMode()}
    )
    timeline_info = admitted["manifest"]["timeline"]
    render_settings = {
        "ExportVideo": True,
        "ExportAudio": True,
        "AudioCodec": "lpcm",
        "AudioSampleRate": 48000,
        "AudioBitDepth": 24,
        "FormatWidth": timeline_info["width"],
        "FormatHeight": timeline_info["height"],
        "FrameRate": _rate_float(timeline_info["frameRate"]),
        "SelectAllFrames": True,
        "TargetDir": str(output_path.parent),
        "CustomName": output_path.stem,
    }
    row = _private_effect(state, "Project.SetRenderSettings", render_settings)
    applied = project.SetRenderSettings(render_settings)
    _require(applied is True, "Resolve refused the exact render settings")
    _effect_observed(
        state,
        row,
        {"return": applied, "settingsSha256": _payload_hash(render_settings)},
    )
    row = _private_effect(
        state,
        "Project.AddRenderJob",
        {
            "settingsSha256": _payload_hash(render_settings),
            "outputPath": str(output_path),
        },
    )
    job_id = project.AddRenderJob()
    _identity(job_id)
    jobs = project.GetRenderJobList()
    _require(type(jobs) in {list, tuple}, "queued render job list unavailable")
    matches = [job for job in jobs if type(job) is dict and job.get("JobId") == job_id]
    _require(
        len(matches) == 1 and job_id not in before_ids,
        "new render job is not uniquely attributable",
    )
    job = matches[0]
    _require(
        job.get("TargetDir") == str(output_path.parent)
        and job.get("OutputFilename") == output_path.name,
        "queued render output path differs",
    )
    _require(
        job.get("IsExportVideo") is True
        and job.get("IsExportAudio") is True
        and job.get("AudioCodec") == "lpcm"
        and job.get("AudioBitDepth") == 24
        and job.get("AudioSampleRate") == 48000
        and job.get("FormatWidth") == timeline_info["width"]
        and job.get("FormatHeight") == timeline_info["height"],
        "queued render job settings differ",
    )
    _require(
        job.get("VideoCodec") in {"prores422", "ProRes 422"}
        and job.get("VideoFormat") in {"QuickTime", "mov"},
        "queued render job codec/container differ",
    )
    _effect_observed(state, row, {"jobId": job_id, "job": job})
    return {
        "jobId": job_id,
        "outputPath": str(output_path),
        "settings": settings,
        "commitmentRawSha256": _parse(
            _read(_path(request["reservation"]["path"], "reservation"), "reservation")
        )["commitmentRawSha256"],
        "reservationSha256": reservation_sha,
        "renderIntentSha256": render_sha,
    }


def _start_render(
    request: dict[str, Any],
    resolve: Any,
    state: dict[str, Any],
    reservation_sha: str | None,
) -> dict[str, Any]:
    previous, queued_sha, queued_path = _previous_result(request, "queue_render")
    payload = request["payload"]
    _require(
        _path(payload["queuedResultPath"], "queued result") == queued_path
        and _digest(payload["queuedResultSha256"]) == queued_sha,
        "start request is not bound to the fixed queued result",
    )
    _require(payload["jobId"] == previous["jobId"], "start job ID differs from queue")
    _, project, _ = _project_timeline(resolve, request)
    jobs = project.GetRenderJobList()
    _require(type(jobs) in {list, tuple}, "render job list unavailable before start")
    rows = [
        job
        for job in jobs
        if type(job) is dict and job.get("JobId") == previous["jobId"]
    ]
    _require(len(rows) == 1, "exact queued render job unavailable")
    _require(
        rows[0].get("JobStatus") not in {"Rendering", "Complete"},
        "queued render job already started or completed",
    )
    row = _private_effect(
        state, "Project.StartRendering", {"jobIds": [previous["jobId"]]}
    )
    started = project.StartRendering([previous["jobId"]])
    _require(started is True, "Resolve refused the exact queued job")
    started_at = _timestamp()
    _effect_observed(
        state,
        row,
        {"return": started, "jobId": previous["jobId"], "startedAt": started_at},
    )
    return {
        "jobId": previous["jobId"],
        "outputPath": previous["outputPath"],
        "settings": previous["settings"],
        "commitmentRawSha256": previous["commitmentRawSha256"],
        "reservationSha256": reservation_sha,
        "renderIntentSha256": previous["renderIntentSha256"],
        "queuedResultSha256": queued_sha,
        "startedAt": started_at,
    }


def _poll_render(
    request: dict[str, Any],
    resolve: Any,
    state: dict[str, Any],
    reservation_sha: str | None,
) -> dict[str, Any]:
    previous, started_sha, started_path = _previous_result(request, "start_render")
    payload = request["payload"]
    _require(
        _path(payload["startedResultPath"], "started result") == started_path
        and _digest(payload["startedResultSha256"]) == started_sha
        and payload["jobId"] == previous["jobId"],
        "poll request is not bound to the fixed started result",
    )
    _, project, _ = _project_timeline(resolve, request)
    deadline = time.monotonic() + MAX_POLL_SECONDS
    status: Any = None
    for _poll_index in range(MAX_POLL_COUNT):
        status = project.GetRenderJobStatus(previous["jobId"])
        _require(
            type(status) is dict and type(status.get("JobStatus")) is str,
            "render job status getter unavailable",
        )
        if status["JobStatus"] in {"Complete", "Failed", "Cancelled"}:
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(POLL_INTERVAL_SECONDS, remaining))
    _require(type(status) is dict, "render status unavailable")
    if status.get("JobStatus") != "Complete":
        return {
            "status": "partial",
            "reason": (
                "render job did not reach Complete within the bounded poll window"
            ),
            "jobId": previous["jobId"],
            "outputPath": previous["outputPath"],
            "settings": previous["settings"],
            "commitmentRawSha256": previous["commitmentRawSha256"],
            "reservationSha256": reservation_sha,
            "renderIntentSha256": previous["renderIntentSha256"],
            "queuedResultSha256": previous["queuedResultSha256"],
            "startedResultSha256": started_sha,
            "startedAt": previous["startedAt"],
            "completedAt": None,
            "sourceOutputRawSha256": None,
        }
    output_path = _path(previous["outputPath"], "completed MOV")
    source_hash, _ = _hash_file(output_path)
    completed_at = _timestamp()
    return {
        "jobId": previous["jobId"],
        "outputPath": str(output_path),
        "settings": previous["settings"],
        "commitmentRawSha256": previous["commitmentRawSha256"],
        "reservationSha256": reservation_sha,
        "renderIntentSha256": previous["renderIntentSha256"],
        "queuedResultSha256": previous["queuedResultSha256"],
        "startedResultSha256": started_sha,
        "startedAt": previous["startedAt"],
        "completedAt": completed_at,
        "sourceOutputRawSha256": source_hash,
        "renderStatus": status,
    }


def _capture_post(
    request: dict[str, Any], resolve: Any, admitted: dict[str, Any]
) -> dict[str, Any]:
    _previous_result(request, "poll_render")
    return _capture(request, resolve, admitted, phase="post_render")


def _base_result(
    request: dict[str, Any],
    request_sha: str,
    authority_sha: str,
    intent_sha: str,
    reservation_sha: str | None,
) -> dict[str, Any]:
    sequence = request["sequence"]
    prior_path = (
        None
        if sequence == 0
        else str(native_request_paths(request["context"], sequence - 1)[0])
    )
    return {
        "schemaVersion": RESULT_SCHEMA,
        "lane": LANE,
        "profile": request["profile"],
        "action": request["action"],
        "operationId": request["operationId"],
        "sequence": sequence,
        "priorResultSha256": request["priorResultSha256"],
        "requestSha256": request_sha,
        "authoritySha256": authority_sha,
        "intentSha256": intent_sha,
        "reservationSha256": reservation_sha,
        "context": request["context"],
        "target": request["target"],
        "status": "complete",
        "reason": "",
        "observedGeometrySha256": None,
        "jobId": None,
        "outputPath": None,
        "requestPath": str(native_request_paths(request["context"], sequence)[3]),
        "authorityPath": request["authority"]["path"],
        "intentPath": request["intent"]["path"],
        "reservationReceiptSha256": None
        if request["reservation"] is None
        else request["reservation"]["receiptSha256"],
        "approvalPath": None,
        "releaseManifestSha256": request["releaseManifestSha256"],
        "sourceGraphSha256": request["context"]["nativeSourceGraphSha256"],
        "nativeGeometry": None,
        "geometryEnvelope": None,
        "settings": None,
        "commitmentRawSha256": None,
        "renderIntentSha256": None,
        "queuedResultSha256": None,
        "startedResultSha256": None,
        "startedAt": None,
        "completedAt": None,
        "completionResultSha256": None,
        "renderLineageSha256": None,
        "sourceOutputRawSha256": None,
        "priorResultPath": prior_path,
        "effectLedger": [],
        "capturedAt": None,
        "expiresAt": None,
        "nativeIdentity": None,
        "admissionPath": request["package"]["admissionPath"],
        "admissionSha256": request["package"]["admissionSha256"],
        "packageInventorySha256": None,
        "releasePath": request["release"]["path"],
        "sourceGraphPath": request["sourceGraph"]["path"],
        "inputBindingPath": None,
        "inputBindingSha256": None,
        "renderStatus": None,
    }


def _apply_stage_result(result: dict[str, Any], value: dict[str, Any]) -> None:
    for key, child in value.items():
        if key in result:
            result[key] = child
    geometry = value.get("nativeGeometry")
    if type(geometry) is dict:
        result["observedGeometrySha256"] = _payload_hash(geometry)
    envelope = value.get("geometryEnvelope")
    if type(envelope) is dict:
        result["expiresAt"] = envelope["expiresAt"]


def _failed_stage_status(effects: list[dict[str, Any]]) -> str:
    if any(row["outcome"] == "unknown" for row in effects):
        return "uncertain"
    return "partial" if effects else "refused"


def _verify_effect_ledger(result: dict[str, Any]) -> None:
    _require(
        type(result["effectLedger"]) is list and len(result["effectLedger"]) <= 4096,
        "bounded native effect ledger required",
    )
    for index, row_value in enumerate(result["effectLedger"]):
        row = _shape(
            row_value,
            frozenset(
                {
                    "index",
                    "path",
                    "sha256",
                    "method",
                    "argumentsSha256",
                    "outcome",
                    "observedSha256",
                }
            ),
            "native effect ledger row",
        )
        _require(
            row["index"] == index
            and row["method"] in ALLOWED_EFFECT_METHODS
            and row["outcome"] in {"observed", "unknown"},
            "native effect order/outcome differs",
        )
        _digest(row["sha256"])
        _digest(row["argumentsSha256"])
        if row["outcome"] == "observed":
            _digest(row["observedSha256"])
        else:
            _require(
                row["observedSha256"] is None,
                "uncertain effect has fabricated readback",
            )
        intent_path = _path(row["path"], "native effect intent")
        _require(
            intent_path
            == Path(result["requestPath"]).parent
            / "effects"
            / f"{index:04d}-intent.json",
            "native effect intent path differs",
        )
        raw = _read(intent_path, "native effect intent")
        _require(_hash(raw) == row["sha256"], "native effect intent changed")
        effect = _shape(_parse(raw), EFFECT_FIELDS, "native effect intent")
        _require(
            effect["schemaVersion"] == EFFECT_SCHEMA
            and effect["lane"] == LANE
            and effect["chainKey"] == _chain_key(result["context"])
            and effect["context"] == result["context"]
            and effect["operationId"] == result["operationId"]
            and type(effect["operationSequence"]) is int
            and effect["operationSequence"] == result["sequence"]
            and type(effect["effectIndex"]) is int
            and effect["effectIndex"] == index
            and effect["method"] == row["method"]
            and effect["argumentsSha256"] == row["argumentsSha256"]
            and effect["authoritySha256"] == result["authoritySha256"]
            and effect["parentIntentSha256"] == result["intentSha256"],
            "native effect intent lineage differs",
        )
        expected_effect_id = _hash(
            _canonical(
                {
                    "operationId": result["operationId"],
                    "index": index,
                    "method": row["method"],
                    "argumentsSha256": row["argumentsSha256"],
                }
            )
        )
        _require(
            effect["effectId"] == expected_effect_id, "native effect identity differs"
        )
        _time(effect["createdAt"], "native effect timestamp")
        observed_path = intent_path.parent / f"{index:04d}-observed.json"
        if row["outcome"] == "observed":
            observed_raw = _read(observed_path, "native effect observation")
            _immutable(observed_path, "native effect observation")
            observed = _shape(
                _parse(observed_raw),
                EFFECT_OBSERVATION_FIELDS,
                "native effect observation",
            )
            _require(
                observed_raw == _canonical(observed)
                and observed["schemaVersion"] == EFFECT_OBSERVATION_SCHEMA
                and observed["lane"] == LANE
                and observed["chainKey"] == _chain_key(result["context"])
                and observed["context"] == result["context"]
                and observed["operationId"] == result["operationId"]
                and observed["operationSequence"] == result["sequence"]
                and observed["effectIndex"] == index
                and observed["effectId"] == effect["effectId"]
                and observed["intentSha256"] == row["sha256"]
                and _payload_hash(observed["observation"]) == row["observedSha256"],
                "native effect observation differs from its retained ledger hash",
            )
            _time(observed["observedAt"], "native effect observation timestamp")
        else:
            _require(
                not observed_path.exists() and not observed_path.is_symlink(),
                "unknown native effect has an observation artifact",
            )
    if result["status"] == "complete":
        _require(
            all(row["outcome"] == "observed" for row in result["effectLedger"]),
            "complete native operation contains an uncertain effect",
        )


def verify_native_result(result_path: Path, expected_sha256: str) -> dict[str, Any]:
    """Verify historical native evidence through its retained request/effect chain."""
    path = _path(str(result_path), "native result")
    raw = _read(path, "native result")
    _require(_hash(raw) == _digest(expected_sha256), "native result digest differs")
    _immutable(path, "native result")
    result = _shape(_parse(raw), RESULT_FIELDS, "native result")
    _require(
        result["schemaVersion"] == RESULT_SCHEMA and result["lane"] == LANE,
        "unsupported native result",
    )
    _require(
        result["profile"] in PROFILES and result["action"] in APPROVAL_ACTION_PLAN,
        "unsupported native result profile/action",
    )
    _require(
        result["status"] in {"complete", "partial", "uncertain", "refused"},
        "invalid native result status",
    )
    _require(
        type(result["reason"]) is str and len(result["reason"]) <= 1024,
        "bounded native result reason required",
    )
    if result["nativeIdentity"] is not None:
        result["nativeIdentity"] = _native_identity(result["nativeIdentity"])
    context = _context(result["context"])
    _require(
        _target(result["target"]) == context["target"], "native result target differs"
    )
    _require(
        type(result["sequence"]) is int
        and 0 <= result["sequence"] < len(APPROVAL_ACTION_PLAN),
        "native result sequence out of range",
    )
    _require(
        result["action"] == APPROVAL_ACTION_PLAN[result["sequence"]],
        "native action order differs",
    )
    expected_result, expected_authority, expected_intent, expected_request = (
        native_request_paths(context, result["sequence"])
    )
    _require(
        path == expected_result and result["requestPath"] == str(expected_request),
        "native result is outside the fixed UID/case/phase operation chain",
    )
    for field in (
        "requestSha256",
        "authoritySha256",
        "intentSha256",
        "releaseManifestSha256",
        "sourceGraphSha256",
        "admissionSha256",
    ):
        _digest(result[field])
    _digest(result["priorResultSha256"])
    _require(
        result["authorityPath"] == str(expected_authority)
        and result["intentPath"] == str(expected_intent),
        "native authority/intent path differs",
    )
    request_raw = _read(expected_request, "retained native request")
    _immutable(expected_request, "retained native request")
    request_sha = _hash(request_raw)
    _require(
        request_sha == result["requestSha256"], "retained native request digest differs"
    )
    request = verify_native_request(
        request_raw, expected_request_sha256=request_sha, current=False
    )
    _require(
        request["resultPath"] == str(path)
        and request["context"] == context
        and request["action"] == result["action"]
        and request["operationId"] == result["operationId"]
        and request["priorResultSha256"] == result["priorResultSha256"],
        "native request/result identity differs",
    )
    start_path = _native_start_path(context, result["sequence"])
    start_raw = _read(start_path, "native operation start marker")
    _immutable(start_path, "native operation start marker")
    start = _shape(_parse(start_raw), NATIVE_START_FIELDS, "native operation start")
    _require(
        start_raw == _canonical(start)
        and start["schemaVersion"] == NATIVE_START_SCHEMA
        and start["lane"] == LANE
        and start["chainKey"] == _chain_key(context)
        and start["context"] == context
        and start["sequence"] == request["sequence"]
        and start["operationId"] == request["operationId"]
        and start["action"] == request["action"]
        and start["priorResultSha256"] == request["priorResultSha256"]
        and start["requestPath"] == str(expected_request)
        and start["requestSha256"] == request_sha
        and start["authoritySha256"] == request["authority"]["sha256"]
        and start["intentSha256"] == request["intent"]["sha256"],
        "native start marker does not bind the retained current request/UID chain",
    )
    _time(start["claimedAt"], "native start marker")
    authority, authority_sha, approval = _verify_authority(request, current=False)
    _require(
        authority_sha == result["authoritySha256"]
        and request["intent"]["sha256"] == result["intentSha256"],
        "native authority/intent hash differs",
    )
    reservation_sha = _verify_reservation(request, current=False)
    _require(
        reservation_sha == result["reservationSha256"],
        "native reservation lineage differs",
    )
    _intent, intent_sha = _verify_intent(request, authority_sha, reservation_sha)
    _require(
        intent_sha == result["intentSha256"]
        and approval["operator"] == authority["operator"],
        "native intent/actor lineage differs",
    )
    _verify_effect_ledger(result)
    if result["sequence"] == 0:
        _require(
            result["priorResultSha256"] == EMPTY_HEAD
            and result["priorResultPath"] is None,
            "first native result must start an empty chain",
        )
    else:
        prior_path = native_request_paths(context, result["sequence"] - 1)[0]
        _require(
            result["priorResultPath"] == str(prior_path),
            "native predecessor path differs",
        )
        prior_raw = _read(prior_path, "native predecessor")
        _require(
            _hash(prior_raw) == result["priorResultSha256"],
            "native predecessor digest differs",
        )
        prior = verify_native_result(prior_path, result["priorResultSha256"])
        _require(
            prior["status"] == "complete",
            "native operation follows an incomplete predecessor",
        )
        _require(
            result["nativeIdentity"] is not None
            and prior["nativeIdentity"] is not None,
            "nonfirst native result lacks runtime identity",
        )
        _verify_native_identity_continuity(
            prior["nativeIdentity"], result["nativeIdentity"]
        )
        if result["action"] == "start_render":
            _require(
                prior["action"] == "queue_render"
                and result["queuedResultSha256"] == result["priorResultSha256"],
                "start result is not bound to its exact queued predecessor",
            )
        elif result["action"] == "poll_render":
            _require(
                prior["action"] == "start_render"
                and result["startedResultSha256"] == result["priorResultSha256"]
                and result["queuedResultSha256"] == prior["queuedResultSha256"],
                "poll result is not bound to its exact queued/started predecessors",
            )
        elif result["action"] == "capture_post":
            _require(
                prior["action"] == "poll_render"
                and result["completionResultSha256"] == result["priorResultSha256"],
                "post-render capture is not bound to its exact completion predecessor",
            )
    if result["nativeGeometry"] is not None:
        geometry = result["nativeGeometry"]
        _require(
            type(geometry) is dict
            and geometry.get("context") == context
            and result["observedGeometrySha256"] == _payload_hash(geometry),
            "retained native geometry digest/context differs",
        )
    if result["geometryEnvelope"] is not None:
        envelope = _shape(
            result["geometryEnvelope"],
            frozenset(
                {
                    "schemaVersion",
                    "lane",
                    "geometry",
                    "inputBindingSha256",
                    "capturePhase",
                    "capturedAt",
                    "expiresAt",
                }
            ),
            "native geometry envelope",
        )
        _require(
            envelope["schemaVersion"] == "qualification-output-geometry/v1"
            and envelope["lane"] == LANE
            and envelope["geometry"] == result["nativeGeometry"]
            and envelope["inputBindingSha256"] == result["inputBindingSha256"],
            "native geometry envelope differs",
        )
        _time(envelope["capturedAt"], "native geometry capture")
        _require(
            _time(envelope["expiresAt"], "native geometry expiry")
            > _time(envelope["capturedAt"], "native geometry capture"),
            "native geometry expiry invalid",
        )
    if result["status"] == "complete":
        _require(
            result["reason"] == "" and result["nativeIdentity"] is not None,
            "complete native result lacks observed runtime identity",
        )
    for field in (
        "jobId",
        "outputPath",
        "sourceOutputRawSha256",
        "commitmentRawSha256",
        "renderIntentSha256",
        "queuedResultSha256",
        "startedResultSha256",
        "completionResultSha256",
        "renderLineageSha256",
        "inputBindingSha256",
        "packageInventorySha256",
    ):
        if result[field] is not None and field not in {"jobId", "outputPath"}:
            _digest(result[field])
    if result["outputPath"] is not None:
        _path(result["outputPath"], "native output")
    if result["status"] == "complete" and result["action"] == "poll_render":
        _time(result["startedAt"], "render start")
        _time(result["completedAt"], "render completion")
        _require(
            _time(result["startedAt"], "render start")
            <= _time(result["completedAt"], "render completion")
            and result["sourceOutputRawSha256"] is not None
            and result["queuedResultSha256"] is not None
            and result["startedResultSha256"] is not None,
            "complete render lacks verified output/time/stage lineage",
        )
    return result


def _native_operation_tail(
    context: dict[str, Any], *, prepared_sequence: int | None = None
) -> tuple[int, str]:
    checked = _context(context)
    first = native_request_paths(checked, 0)[0]
    root = first.parent.parent
    if not root.exists():
        _require(prepared_sequence is None, "prepared native operation is absent")
        return 0, EMPTY_HEAD
    directories = sorted(root.iterdir())
    if prepared_sequence is not None:
        _require(
            type(prepared_sequence) is int
            and prepared_sequence >= 0
            and len(directories) == prepared_sequence + 1,
            "prepared native request is not the exact native history tail",
        )
    prior = EMPTY_HEAD
    for sequence, directory in enumerate(directories):
        _require(
            directory.is_dir()
            and not directory.is_symlink()
            and directory.name == f"{sequence:08d}",
            "native operation directory sequence differs",
        )
        result_path = directory / "result.json"
        if sequence == prepared_sequence:
            _require(
                not result_path.exists(),
                "prepared native operation already has a result",
            )
            return sequence, prior
        _require(
            result_path.is_file(),
            "native operation has an immutable intent without a terminal result; "
            "read-only recovery required",
        )
        raw = _read(result_path, "native operation result")
        result = verify_native_result(result_path, _hash(raw))
        _require(
            result["status"] == "complete" and result["sequence"] == sequence,
            "native operation history is partial/uncertain and cannot be replayed",
        )
        prior = _hash(raw)
    _require(
        prepared_sequence is None,
        "prepared native operation is absent from the native history tail",
    )
    _require(
        len(directories) < len(APPROVAL_ACTION_PLAN),
        "reviewed native action plan is exhausted",
    )
    return len(directories), prior


def next_native_operation(context: dict[str, Any]) -> tuple[int, str]:
    """Return the next one-use stage only after authenticating the full chain."""
    return _native_operation_tail(context)


NATIVE_START_SCHEMA = "qualification-output-native-start/v1"
NATIVE_START_FIELDS = frozenset(
    {
        "schemaVersion",
        "lane",
        "chainKey",
        "context",
        "sequence",
        "operationId",
        "action",
        "priorResultSha256",
        "requestPath",
        "requestSha256",
        "authoritySha256",
        "intentSha256",
        "claimedAt",
    }
)


def _native_start_path(context: dict[str, Any], sequence: int) -> Path:
    result_path = native_request_paths(context, sequence)[0]
    return result_path.parent / "native-start.json"


def _claim_prepared_native_operation(
    request: dict[str, Any], request_raw: bytes, request_sha256: str
) -> Path:
    """Atomically claim the host-prepared current operation before Resolve calls."""
    context = _context(request["context"])
    sequence = request["sequence"]
    _require(
        type(sequence) is int and 0 <= sequence < len(APPROVAL_ACTION_PLAN),
        "prepared native sequence is out of range",
    )
    result_path, authority_path, intent_path, request_path = native_request_paths(
        context, sequence
    )
    directory = request_path.parent
    _require(
        type(request_raw) is bytes
        and request_raw == _canonical(request)
        and _hash(request_raw) == _digest(request_sha256),
        "prepared native request bytes are not canonical/current",
    )
    _require(
        request["action"] == APPROVAL_ACTION_PLAN[sequence]
        and request["priorResultSha256"] == _digest(request["priorResultSha256"])
        and request["resultPath"] == str(result_path)
        and request["authority"]["path"] == str(authority_path)
        and request["intent"]["path"] == str(intent_path)
        and request_path.is_file()
        and _read(request_path, "prepared native request") == request_raw,
        "prepared native request differs from its fixed operation slot",
    )
    _immutable(request_path, "prepared native request")
    _immutable(authority_path, "prepared native authority")
    _immutable(intent_path, "prepared native intent")
    tail, prior = _native_operation_tail(context, prepared_sequence=sequence)
    _require(
        tail == sequence and prior == request["priorResultSha256"],
        "prepared native request does not extend the complete operation history",
    )
    _require(
        _hash(_read(authority_path, "prepared native authority"))
        == request["authority"]["sha256"]
        and _hash(_read(intent_path, "prepared native intent"))
        == request["intent"]["sha256"],
        "prepared native authority/intent changed",
    )
    start_path = _native_start_path(context, sequence)
    effects_path = directory / "effects"
    _require(
        not start_path.exists(),
        "prepared native operation has already been claimed",
    )
    children = {item.name for item in directory.iterdir()}
    _require(
        children == {"request.json", "authority.json", "intent.json"}
        and not result_path.exists()
        and not effects_path.exists(),
        "prepared native operation contains an unexpected or prior start artifact",
    )
    marker = {
        "schemaVersion": NATIVE_START_SCHEMA,
        "lane": LANE,
        "chainKey": _chain_key(context),
        "context": context,
        "sequence": sequence,
        "operationId": request["operationId"],
        "action": request["action"],
        "priorResultSha256": prior,
        "requestPath": str(request_path),
        "requestSha256": request_sha256,
        "authoritySha256": request["authority"]["sha256"],
        "intentSha256": request["intent"]["sha256"],
        "claimedAt": _timestamp(),
    }
    try:
        _publish(start_path, marker)
    except FileExistsError as error:
        raise OutputConsistencyError(
            "prepared native operation has already been claimed"
        ) from error
    return start_path


def _native_stage(
    resolve: Any,
    request: dict[str, Any],
    admitted: dict[str, Any],
    state: dict[str, Any],
    reservation_sha: str | None,
) -> dict[str, Any]:
    action = request["action"]
    current_identity = _connected(resolve)
    if request["sequence"] > 0:
        prior_path = native_request_paths(request["context"], request["sequence"] - 1)[
            0
        ]
        prior_raw = _read(prior_path, "native runtime predecessor")
        _require(
            _hash(prior_raw) == request["priorResultSha256"],
            "native runtime predecessor digest differs",
        )
        prior = verify_native_result(prior_path, _hash(prior_raw))
        _require(
            prior["status"] == "complete",
            "native runtime predecessor is incomplete",
        )
        _verify_native_identity_continuity(prior["nativeIdentity"], current_identity)
    if action == "construct":
        return _construct(resolve, request, admitted, state)
    if action == "save_reopen":
        return _save_reopen(resolve, request, admitted, state)
    if action == "capture_pre":
        _previous_result(request, "save_reopen")
        return _capture(request, resolve, admitted, phase="pre_render")
    if action == "queue_render":
        return _queue_render(request, resolve, admitted, state, reservation_sha)
    if action == "start_render":
        return _start_render(request, resolve, state, reservation_sha)
    if action == "poll_render":
        return _poll_render(request, resolve, state, reservation_sha)
    if action == "capture_post":
        return _capture_post(request, resolve, admitted)
    raise OutputConsistencyError("native action is not in the fixed reviewed plan")


def run_qualification_output_request(
    resolve: Any, request_path: Path, *, expected_request_sha256: str
) -> Path:
    """Run one reviewed static operation from the fixed installed request slot."""
    path = _path(str(request_path), "installed native request")
    _require(
        path == NATIVE_RELEASE_ROOT / "request.json",
        "launcher request must use the fixed reviewed installation slot",
    )
    raw = _read(path, "installed native request")
    request = verify_native_request(
        raw, expected_request_sha256=expected_request_sha256
    )
    canonical_result, _, _, canonical_request = native_request_paths(
        request["context"], request["sequence"]
    )
    _require(
        request["resultPath"] == str(canonical_result),
        "native result path is not the fixed operation slot",
    )
    retained_request = _read(canonical_request, "canonical host native request")
    _require(
        retained_request == raw,
        "installed launcher request differs from the immutable host request",
    )
    admitted = _admission_profile(request)
    readonly_after_start = request["action"] in {"poll_render", "capture_post"}
    if readonly_after_start:
        _verify_readonly_native_lineage(request)
    reservation_sha = _verify_reservation(request, current=not readonly_after_start)
    authority, authority_sha, _approval = _verify_authority(
        request, current=not readonly_after_start
    )
    _, intent_sha = _verify_intent(request, authority_sha, reservation_sha)
    _verify_installed_release(request, current=True)
    _require(resolve is not None, "Resolve must be injected by the reviewed launcher")
    _claim_prepared_native_operation(request, raw, expected_request_sha256)
    result = _base_result(
        request, expected_request_sha256, authority_sha, intent_sha, reservation_sha
    )
    result["approvalPath"] = authority["approvalPath"]
    result["packageInventorySha256"] = admitted["admission"]["packageInventorySha256"]
    result["commitmentRawSha256"] = (
        None
        if request["reservation"] is None
        else _shape(
            _parse(
                _read(
                    _path(request["reservation"]["path"], "reservation"), "reservation"
                )
            ),
            frozenset(RESERVATION_FIELDS.split()),
            "reservation",
        )["commitmentRawSha256"]
    )
    result["renderIntentSha256"] = (
        None if request["renderIntent"] is None else request["renderIntent"]["sha256"]
    )
    state: dict[str, Any] = {
        "request": request,
        "authoritySha256": authority_sha,
        "intentSha256": intent_sha,
        "effects": [],
    }
    try:
        result["nativeIdentity"] = _connected(resolve)
        value = _native_stage(resolve, request, admitted, state, reservation_sha)
        _apply_stage_result(result, value)
        if value.get("status") is not None:
            result["status"] = value["status"]
        result["effectLedger"] = state["effects"]
        if request["action"] == "capture_pre" or request["action"] == "capture_post":
            result["inputBindingPath"] = value["inputBindingPath"]
            result["inputBindingSha256"] = value["inputBindingSha256"]
        if request["action"] == "capture_post":
            result["completionResultSha256"] = value["completionResultSha256"]
            result["renderLineageSha256"] = value["renderLineageSha256"]
        if request["action"] == "poll_render":
            result["renderStatus"] = value.get("renderStatus")
        if request["action"] == "queue_render":
            result["settings"] = request["payload"]["settings"]
        elif request["action"] in {"start_render", "poll_render"}:
            prior_result, _, _ = _previous_result(
                request,
                "queue_render"
                if request["action"] == "start_render"
                else "start_render",
            )
            result["settings"] = prior_result["settings"]
        result["reason"] = value.get("reason", "")
    except OutputConsistencyError as error:
        result["status"] = _failed_stage_status(state["effects"])
        result["reason"] = str(error)[:1024]
        result["effectLedger"] = state["effects"]
    except Exception as error:
        result["status"] = _failed_stage_status(state["effects"])
        reason = (
            f"{type(error).__name__}: native stage stopped; "
            "retained effects are not retried"
        )
        result["reason"] = reason[:1024]
        result["effectLedger"] = state["effects"]
    return _publish(canonical_result, result)
