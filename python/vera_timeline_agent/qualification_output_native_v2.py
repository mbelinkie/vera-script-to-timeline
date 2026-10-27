"""Installed stdlib-only native boundary for bounded output qualification.

This module deliberately has no dependency on the host controller, compiler,
predictor, decoder, or package builder. It accepts only closed immutable
records, verifies a one-use operator approval and executes a finite sequence
against the already-open, already-saved disposable target.
"""

from __future__ import annotations

import dataclasses
import getpass
import hashlib
import hmac
import json
import math
import os
import pwd
import stat
import struct
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from fractions import Fraction
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
    validate_temporary_presenter_report,
)


@dataclasses.dataclass
class _VerificationTraversal:
    results: dict[tuple[Path, str], dict[str, Any]] = dataclasses.field(
        default_factory=dict
    )
    histories: dict[str, list[dict[str, Any]]] = dataclasses.field(default_factory=dict)


_VERIFICATION: ContextVar[_VerificationTraversal | None] = ContextVar(
    "native_result_verification", default=None
)


@contextmanager
def _verification_scope() -> Iterator[_VerificationTraversal]:
    traversal = _VERIFICATION.get()
    if traversal is not None:
        yield traversal
        return
    traversal = _VerificationTraversal()
    token = _VERIFICATION.set(traversal)
    try:
        yield traversal
    finally:
        _VERIFICATION.reset(token)


REQUEST_SCHEMA = "qualification-output-native-request/v1"
AUTHORITY_SCHEMA = "qualification-output-native-authority/v1"
INTENT_SCHEMA = "qualification-output-native-intent/v1"
RESULT_SCHEMA = "qualification-output-native-result/v1"
ADMISSION_SCHEMA = "qualification-output-package-admission/v1"
APPROVAL_SCHEMA = "qualification-output-operator-approval/v1"
RENDER_INTENT_SCHEMA = "qualification-output-render-intent/v1"
INVENTORY_SCHEMA = "qualification-output-package-inventory/v1"
SYNTHETIC_PROFILE = "verified-v2-package/v1"
MATRIX_PROFILE = "qualification-output-studio-matrix/v1"
PUBLIC_PROFILES = frozenset({SYNTHETIC_PROFILE, MATRIX_PROFILE})
R16_PROFILE = "qualification-output-r16-presenter-override/v1"
PRESENTER_PROFILE = "qualification-output-current-presenter/v1"
CONSTRUCTOR_LINK_PROFILES = frozenset({MATRIX_PROFILE, PRESENTER_PROFILE})
PRESENTER_SLOT_ID = "8ef61d23-9625-5b03-a046-e3f1051bbd75"
PRESENTER_WARNING_ID = "5e77b270-31bf-5ab0-8a99-4698599c131e"
PRESENTER_WARNING_MESSAGE = "On Camera uses the effective temporary presenter still."
PRESENTER_RECOVERY_INSTRUCTION = (
    "Replace the temporary still with an accepted presenter source when available."
)
PROFILES = frozenset({*PUBLIC_PROFILES, R16_PROFILE, PRESENTER_PROFILE})
ACTIONS = frozenset(
    {
        "construct",
        "observe_edited",
        "capture_pre",
        "retry_capture",
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
MAX_REOPEN_MEDIA_POOL_READY_SECONDS = 5.0
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
_PRESENTER_INPUT_ROOT = (
    Path.home()
    / "Library/Application Support/VERA/qualification-output-preparation"
    / "issue178-20261016-01/cases/presenter-alpha-01/inputs"
)
_PRESENTER_ORIGINALS = {
    "script-document-v2.json": (
        "a9b0c63b823dd22f0f4e187d0ec5b2a528115fa065a89106123734957b813681"
    ),
    "compiler-dependencies-v2.json": (
        "d0f6b7e595e7d5fd4cf5b8216f299fc601f46d3766e47d9e6601af6ffd336aca"
    ),
}
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
OBSERVED_ACTION_PLAN = (
    "observe_edited",
    "save_reopen",
    "capture_pre",
    "queue_render",
    "start_render",
    "poll_render",
    "capture_post",
)
RETRY_ACTION_PLAN = (
    "retry_capture",
    "queue_render",
    "start_render",
    "poll_render",
    "capture_post",
)


def _approval_plan_for_request(request: dict[str, Any]) -> tuple[str, ...]:
    context = request.get("context", {})
    plan = action_plan_for_context(context)
    if context.get("phase") == "edited":
        return plan
    if request["sequence"] > len(plan) - 1 or (
        request["sequence"] == len(plan) - 1 and request["action"] == "retry_capture"
    ):
        return RETRY_ACTION_PLAN
    return plan


def action_plan_for_context(context: dict[str, Any]) -> tuple[str, ...]:
    """Return the one reviewed native plan statically selected by phase."""
    return (
        OBSERVED_ACTION_PLAN
        if context.get("phase") == "edited"
        else APPROVAL_ACTION_PLAN
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
        "Timeline.SetClipsLinked",
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
REVISED_PREFLIGHT_REQUEST_FIELDS = REQUEST_FIELDS | frozenset({"revisedPreflight"})
REVISED_PREFLIGHT_FIELDS = frozenset(
    {
        "schemaVersion",
        "lane",
        "status",
        "sourceHashes",
        "proofSession",
        "originalInputs",
        "baselineInputs",
        "executionInputs",
        "manifest",
        "report",
        "evidence",
        "proposal",
        "decision",
        "result",
        "revisionLedger",
        "acceptedDecisionReceipt",
        "proofFiles",
        "verifiedFiles",
        "receipt",
    }
)
REVISED_PREFLIGHT_PROOF_FILE_FIELDS = frozenset(
    {
        "evidenceReceipt",
        "inferenceDecision",
        "inferenceDecisionReceipt",
        "stage",
        "inferenceClaim",
        "revisionClaim",
        "omissionSupport",
        "omissionSourceReviewReceipt",
        "omissionSourceReview",
    }
)
REVISED_PREFLIGHT_REQUIRED_PROOF_FILES = (
    "evidenceReceipt",
    "inferenceDecision",
    "inferenceDecisionReceipt",
    "stage",
    "inferenceClaim",
    "revisionClaim",
)
REVISED_PREFLIGHT_OMISSION_PROOF_FILES = (
    "omissionSupport",
    "omissionSourceReviewReceipt",
    "omissionSourceReview",
)
REVISED_PREFLIGHT_LEDGER_FIELDS = frozenset(
    {
        "schemaVersion",
        "lane",
        "proofSessionSha256",
        "evidenceSha256",
        "inferenceDecisionSha256",
        "candidateSha256",
        "decisionSha256",
        "resultSha256",
        "outcome",
        "history",
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


def render_parent(context: dict[str, Any]) -> Path:
    """Resolve a private per-target output location; old targets keep their root."""
    key = _chain_key(_context(context))
    location = NATIVE_STATE_ROOT / "targets" / key / "render-location.json"
    root = NATIVE_STATE_ROOT / "renders"
    if location.exists() or location.is_symlink():
        value = _shape(
            _parse(_read(location, "render location", maximum=8192)),
            frozenset({"schemaVersion", "chainKey", "root"}),
            "render location",
        )
        info = location.stat()
        _require(
            info.st_uid == os.getuid()
            and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o400
            and value["schemaVersion"] == "qualification-output-render-location/v1"
            and value["chainKey"] == key,
            "immutable owned per-target render location required",
        )
        root = _path(value["root"], "render root")
        _require(
            root.is_dir()
            and root.stat().st_uid == os.getuid()
            and stat.S_IMODE(root.stat().st_mode) == 0o700,
            "private owned render root required",
        )
    return root / key


def register_render_root(context: dict[str, Any], root: Path) -> None:
    """Pin a new target's explicitly selected local volume before approval."""
    key = _chain_key(_context(context))
    _path(str(root), "render root")
    _require(
        root.is_dir()
        and root.stat().st_uid == os.getuid()
        and stat.S_IMODE(root.stat().st_mode) == 0o700,
        "private owned render root required",
    )
    directory = NATIVE_STATE_ROOT / "targets" / key
    _path(str(directory), "native target")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    _require(not (directory / "operations").exists(), "native operation already exists")
    location = directory / "render-location.json"
    if location.exists() or location.is_symlink():
        _require(render_parent(context).parent == root, "render root differs")
        return
    _publish(
        location,
        {
            "schemaVersion": "qualification-output-render-location/v1",
            "chainKey": key,
            "root": str(root),
        },
    )


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


def _verify_presenter_report_rows(
    admission: dict[str, Any], report: dict[str, Any], document_id: str
) -> None:
    """Bind the one accepted Presenter warning and recovery to compiler output."""
    report_warnings = report.get("diagnostics")
    report_recovery = report.get("recoveryActions")
    _require(
        type(report_warnings) is list and admission["diagnostics"] == report_warnings,
        "Presenter warning rows differ from the full report",
    )
    _require(
        type(report_recovery) is list
        and admission["recoveryActions"] == report_recovery,
        "Presenter recovery rows differ from the full report",
    )
    assert type(report_warnings) is list
    assert type(report_recovery) is list
    _require(
        len(report_warnings) == 1 and type(report_warnings[0]) is dict,
        "exactly one Presenter warning is required",
    )
    _require(
        len(report_recovery) == 1 and type(report_recovery[0]) is dict,
        "exactly one Presenter recovery is required",
    )
    warning = report_warnings[0]
    recovery = report_recovery[0]
    _require(
        warning
        == {
            "id": PRESENTER_WARNING_ID,
            "code": "TEMPORARY_PRESENTER_STILL",
            "severity": "warning",
            "message": PRESENTER_WARNING_MESSAGE,
            "entity": {
                "id": PRESENTER_SLOT_ID,
                "kind": "slot",
                "path": "presenterStill",
            },
            "evidence": {"kind": "details", "message": PRESENTER_WARNING_MESSAGE},
            "recoveryActionKinds": ["REPLACE_TEMPORARY_PRESENTER"],
        },
        "unexpected current Presenter warning",
    )
    _require(
        recovery
        == {
            "documentId": document_id,
            "instruction": PRESENTER_RECOVERY_INSTRUCTION,
            "kind": "REPLACE_TEMPORARY_PRESENTER",
            "slotId": PRESENTER_SLOT_ID,
        },
        "unexpected current Presenter recovery",
    )


def _verify_presenter_admission(
    admission: dict[str, Any], report: dict[str, Any], document_id: str
) -> None:
    _require(
        admission["disposition"] == "qualification_only"
        and admission["creativeQualification"] == "unqualified_temporary_presenter",
        "current Presenter profile lacks qualification-only disposition",
    )
    _require(
        type(admission["diagnostics"]) is list and len(admission["diagnostics"]) == 1,
        "current Presenter warning inventory is incomplete",
    )
    _require(
        type(admission["recoveryActions"]) is list
        and len(admission["recoveryActions"]) == 1,
        "current Presenter recovery inventory is incomplete",
    )
    _verify_presenter_report_rows(admission, report, document_id)


def _verify_public_package_diagnostics(
    profile: str,
    admission: dict[str, Any],
    document: dict[str, Any],
    manifest: dict[str, Any],
    report: dict[str, Any],
) -> None:
    """Keep synthetic packages empty; validate Matrix rows against compiler output."""
    _require(profile in PUBLIC_PROFILES, "public package profile required")
    report_warnings = report.get("diagnostics")
    report_recovery = report.get("recoveryActions")
    _require(
        type(report_warnings) is list and type(report_recovery) is list,
        "public report diagnostic and recovery arrays required",
    )
    _require(
        type(admission.get("diagnostics")) is list
        and type(admission.get("recoveryActions")) is list
        and admission["diagnostics"] == report_warnings
        and admission["recoveryActions"] == report_recovery,
        "public diagnostic rows differ from the full report",
    )
    if profile == SYNTHETIC_PROFILE:
        _require(
            report_warnings == [] and report_recovery == [],
            "ordinary synthetic package diagnostics refuse",
        )
        return

    validate_temporary_presenter_report(document, manifest, report)


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
    valid_plans = [list(action_plan_for_context(approved_context))]
    if approved_context["phase"] != "edited":
        valid_plans.append(list(RETRY_ACTION_PLAN))
    _require(approval["actionPlan"] in valid_plans, "approval action plan differs")
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
    expected_parent = render_parent(approved_context)
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


def _revised_preflight_route(context: dict[str, Any]) -> bool:
    return bool(
        context["phase"] == "rebuild" and context["binding"]["kind"] == "revised"
    )


def _verify_revised_preflight_currentness(request: dict[str, Any]) -> None:
    """Check host-pinned revised proof files immediately before native work.

    The host verifier owns proof semantics and receipt authentication. This
    stdlib-only boundary rechecks the exact closed record and all of its
    referenced bytes against the operator-bound context so a previously
    verified decision or input cannot go stale between request preparation
    and the first native effect.
    """
    reference = _shape(
        request["revisedPreflight"], PATH_HASH_FIELDS, "revised preflight reference"
    )
    preflight_raw, preflight_sha256, preflight_path = _read_ref(
        reference, "revised preflight"
    )
    preflight_info = preflight_path.stat(follow_symlinks=False)
    _require(preflight_info.st_nlink == 1, "aliased revised preflight refused")
    record = _shape(
        _parse(preflight_raw), REVISED_PREFLIGHT_FIELDS, "revised preflight"
    )
    _require(
        record["schemaVersion"] == "qualification-output-revised-preflight/v1"
        and record["lane"] == LANE
        and record["status"] == "prepared",
        "prepared revised preflight required",
    )
    context = request["context"]
    binding = context["binding"]
    source_hashes = record["sourceHashes"]
    _require(
        type(source_hashes) is dict
        and _hash(_canonical(source_hashes)) == context["hostSourceGraphSha256"],
        "revised preflight source graph differs",
    )

    pin_groups: dict[str, dict[str, dict[str, Any]]] = {}
    for group_name in ("originalInputs", "baselineInputs", "executionInputs"):
        pin_groups[group_name] = _shape(
            record[group_name], frozenset({"document", "dependencies"}), group_name
        )
    single_names = (
        "manifest",
        "report",
        "evidence",
        "proposal",
        "decision",
        "result",
        "revisionLedger",
        "acceptedDecisionReceipt",
    )
    proof_files = _shape(
        record["proofFiles"],
        REVISED_PREFLIGHT_PROOF_FILE_FIELDS,
        "revised preflight proof files",
    )
    omission_values = [
        proof_files[name] for name in REVISED_PREFLIGHT_OMISSION_PROOF_FILES
    ]
    _require(
        all(value is None for value in omission_values)
        or all(value is not None for value in omission_values),
        "revised omission proof pins must be all present or all absent",
    )
    pins = {
        "proofSession": record["proofSession"],
        **{
            f"{group_name}.{name}": pin
            for group_name, group in pin_groups.items()
            for name, pin in group.items()
        },
        **{name: record[name] for name in single_names},
        **{
            f"proofFiles.{name}": proof_files[name]
            for name in REVISED_PREFLIGHT_REQUIRED_PROOF_FILES
        },
        **{
            f"proofFiles.{name}": proof_files[name]
            for name in REVISED_PREFLIGHT_OMISSION_PROOF_FILES
            if proof_files[name] is not None
        },
    }
    verified_files = {
        pin["path"]: pin["sha256"]
        for pin in pins.values()
        if type(pin) is dict and set(pin) == PATH_HASH_FIELDS
    }
    _require(
        len(verified_files) == len(pins) and record["verifiedFiles"] == verified_files,
        "revised verified-file inventory differs",
    )

    current: dict[str, bytes] = {}
    for name, pin_value in pins.items():
        pin = _shape(pin_value, PATH_HASH_FIELDS, f"revised {name} pin")
        path = _path(pin["path"], f"revised {name}")
        expected = _digest(pin["sha256"])
        raw = _read(path, f"revised {name}")
        info = path.stat(follow_symlinks=False)
        _require(info.st_nlink == 1, f"aliased revised {name} refused")
        _require(_hash(raw) == expected, f"current revised {name} pin differs")
        current[name] = raw

    receipt_pin = _shape(
        record["receipt"], PATH_HASH_FIELDS, "revised preflight receipt"
    )
    receipt_path = _path(receipt_pin["path"], "revised preflight receipt")
    receipt_sha256 = _digest(receipt_pin["sha256"])
    receipt_raw = _read(receipt_path, "revised preflight receipt")
    _require(
        receipt_path.stat(follow_symlinks=False).st_nlink == 1
        and _hash(receipt_raw) == receipt_sha256,
        "current revised preflight receipt differs",
    )

    for name, context_field in (
        ("originalInputs.document", "originalDocumentSha256"),
        ("originalInputs.dependencies", "originalDependenciesSha256"),
        ("executionInputs.document", "executionDocumentSha256"),
        ("executionInputs.dependencies", "executionDependenciesSha256"),
        ("manifest", "manifestSha256"),
        ("report", "reportSha256"),
    ):
        pin = (
            pin_groups[name.split(".")[0]][name.split(".")[1]]
            if "." in name
            else record[name]
        )
        _require(
            pin["sha256"] == context[context_field],
            f"revised {name} context pin differs",
        )
    for binding_field, pin_name in (
        ("acceptedDecisionReceiptSha256", "acceptedDecisionReceipt"),
        ("revisionLedgerSha256", "revisionLedger"),
        ("proposalEvidenceSha256", "evidence"),
    ):
        _require(
            binding[binding_field] == record[pin_name]["sha256"],
            f"revised {binding_field} pin differs",
        )

    decision = _parse(current["decision"])
    result = _parse(current["result"])
    _require(
        type(decision) is dict
        and decision.get("outcome") == "accept"
        and type(result) is dict
        and result.get("outcome") == "accept",
        "accepted revised decision and result required",
    )
    ledger = _shape(
        _parse(current["revisionLedger"]),
        REVISED_PREFLIGHT_LEDGER_FIELDS,
        "revised revision ledger",
    )
    _require(
        ledger["schemaVersion"] == "qualification-output-revision-ledger/v1"
        and ledger["lane"] == LANE
        and ledger["outcome"] == "accept"
        and ledger["proofSessionSha256"] == record["proofSession"]["sha256"]
        and ledger["evidenceSha256"] == record["evidence"]["sha256"]
        and ledger["candidateSha256"] == record["proposal"]["sha256"]
        and ledger["decisionSha256"] == record["decision"]["sha256"]
        and ledger["resultSha256"] == record["result"]["sha256"],
        "accepted revised ledger lineage differs",
    )
    _digest(preflight_sha256)


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
    parsed_request = _parse(raw)
    _require(
        type(parsed_request) is dict
        and frozenset(parsed_request)
        in {frozenset(REQUEST_FIELDS), frozenset(REVISED_PREFLIGHT_REQUEST_FIELDS)},
        "closed native request shape",
    )
    request = parsed_request
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
    revised_route = _revised_preflight_route(context)
    _require(
        set(request)
        == (REVISED_PREFLIGHT_REQUEST_FIELDS if revised_route else REQUEST_FIELDS),
        "native request fields differ for context",
    )
    _require(
        request["sequence"]
        < len(action_plan_for_context(request["context"]))
        + (
            len(RETRY_ACTION_PLAN) - 1
            if request["context"].get("phase") != "edited"
            else 0
        )
        and request["action"] == native_action(context, request["sequence"]),
        "native action order differs",
    )
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
    if revised_route:
        _shape(
            request["revisedPreflight"],
            PATH_HASH_FIELDS,
            "revised preflight reference",
        )
        _path(request["revisedPreflight"]["path"], "revised preflight")
        _digest(request["revisedPreflight"]["sha256"])
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
        if revised_route:
            _verify_revised_preflight_currentness(request)
    return request


def _payload_fields(action: str) -> frozenset[str]:
    fields = {
        "construct": frozenset(),
        "observe_edited": frozenset(),
        "capture_pre": frozenset({"inputBindingPath", "inputBindingSha256"}),
        "retry_capture": frozenset({"inputBindingPath", "inputBindingSha256"}),
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
    input_bytes: dict[str, bytes] = {}
    for name in INPUT_FIELDS:
        raw_input = _read(_path(request["inputs"][name], name), name, maximum=MAX_BYTES)
        field = name.removesuffix("Path") + "Sha256"
        _require(_hash(raw_input) == admission[field], f"current {name} pin differs")
        input_bytes[name] = raw_input
    if request["profile"] in PUBLIC_PROFILES:
        _require(
            admission["disposition"]
            == (
                "verified_matrix_inputs"
                if request["profile"] == MATRIX_PROFILE
                else "verified_synthetic"
            )
            and admission["creativeQualification"]
            == (
                "unqualified_studio_matrix"
                if request["profile"] == MATRIX_PROFILE
                else "qualified_synthetic_only"
            ),
            "ordinary package is not a verified synthetic",
        )
    elif request["profile"] == R16_PROFILE:
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
    else:
        _require(request["profile"] == PRESENTER_PROFILE, "unsupported package profile")
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
    if request["profile"] in PUBLIC_PROFILES:
        execution_document = _parse(input_bytes["executionDocumentPath"])
        _require(
            type(execution_document) is dict,
            "admitted execution document must be an object",
        )
        _verify_public_package_diagnostics(
            request["profile"], admission, execution_document, manifest, report
        )
    if request["profile"] in {R16_PROFILE, PRESENTER_PROFILE}:
        # These rows are retained from the exact hashed report, never synthesized
        # into the installed request. The package builder records their canonical
        # full rows in its admission projection.
        report_warnings = report.get("diagnostics")
        report_recovery = report.get("recoveryActions")
        _require(
            type(report_warnings) is list
            and admission["diagnostics"] == report_warnings,
            "Presenter warning rows differ from the full report",
        )
        _require(
            type(report_recovery) is list
            and admission["recoveryActions"] == report_recovery,
            "Presenter recovery rows differ from the full report",
        )
        assert type(report_warnings) is list
        assert type(report_recovery) is list
        if request["profile"] == R16_PROFILE:
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
                    type(row) is dict
                    and row.get("kind") == "REPLACE_TEMPORARY_PRESENTER"
                    for row in report_recovery
                ),
                "exact R16 recovery row required",
            )
        else:
            original_document = _parse(input_bytes["originalDocumentPath"])
            _require(
                type(original_document) is dict,
                "current Presenter original document must be an object",
            )
            document_id = _identity(original_document.get("id"))
            _verify_presenter_admission(admission, report, document_id)
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
        approval["actionPlan"] == list(_approval_plan_for_request(request))
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
            in {
                "construct",
                "observe_edited",
                "save_reopen",
                "capture_pre",
                "retry_capture",
                "queue_render",
            },
        )
        if current
        else _historical_approval(approval_raw, request)
    )
    _require(
        request["action"] in approval["actionPlan"]
        and approval["actionPlan"] == list(_approval_plan_for_request(request)),
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
    traversal = _VERIFICATION.get()
    key = _chain_key(context)
    if traversal is not None and key in traversal.histories:
        return traversal.histories[key]
    rows = _verify_host_attempt_history(context)
    if traversal is not None:
        traversal.histories[key] = rows
    return rows


def _verify_host_attempt_history(context: dict[str, Any]) -> list[dict[str, Any]]:
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
    verified_artifacts: set[str] = set()
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
                "render_failed",
                "uncertain",
                "compared_consistent",
                "compared_refused",
            },
            "unknown host attempt state",
        )
        if state == "committed":
            _require(
                prior is None or prior["state"] in {"expired_unused", "render_failed"},
                "host commitment replayed",
            )
            if prior is not None:
                _require(
                    row["context"] == prior["context"]
                    and row["predictionBytesSha256"] == prior["predictionBytesSha256"],
                    "host recommit changed context or prediction bytes",
                )
            if prior is not None:
                failed_renders = sum(
                    item["state"] == "render_failed"
                    and item["context"]["binding"]["bindingSha256"] == binding
                    for item in rows
                )
                _require(
                    failed_renders == (1 if prior["state"] == "render_failed" else 0),
                    "host render retry budget exhausted",
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
            elif state == "render_failed":
                result_sha = row["resultRawSha256"]
                _require(
                    prior["state"] == "reserved_by_render_intent"
                    and row["reservationRawSha256"] == prior["reservationRawSha256"]
                    and result_sha is not None,
                    "invalid host failed-render transition",
                )
                result_raw = _read(
                    directory / "artifacts" / result_sha,
                    "retained native failed poll",
                    maximum=48_000_000,
                )
                failed = _shape(_parse(result_raw), RESULT_FIELDS, "failed poll result")
                retry_poll_sequence = (
                    len(APPROVAL_ACTION_PLAN)
                    - 1
                    + RETRY_ACTION_PLAN.index("poll_render")
                )
                _require(
                    type(failed["sequence"]) is int
                    and failed["sequence"]
                    in {
                        len(APPROVAL_ACTION_PLAN) - 2,
                        retry_poll_sequence,
                    },
                    "host failed result is outside the reviewed poll slots",
                )
                failed_path = native_request_paths(row_context, failed["sequence"])[0]
                _require(
                    result_raw == _canonical(failed)
                    and failed["action"] == "poll_render"
                    and _terminal_failed_render(failed)
                    and failed["context"] == row["context"]
                    and failed["reservationSha256"] == row["reservationRawSha256"]
                    and failed["commitmentRawSha256"] == row["commitmentRawSha256"]
                    and _hash(result_raw) == result_sha,
                    "host failed-render result lineage differs",
                )
                _immutable(failed_path, "native failed poll result")
                _require(
                    _read(failed_path, "canonical native failed poll") == result_raw,
                    "host failed-render result is not the canonical native poll",
                )
            else:
                _require(
                    state in {"uncertain", "compared_consistent", "compared_refused"}
                    and prior["state"] == "reserved_by_render_intent"
                    and row["reservationRawSha256"] == prior["reservationRawSha256"],
                    "invalid host terminal transition",
                )
                _require(
                    row["resultRawSha256"] is None
                    if state == "uncertain"
                    else row["resultRawSha256"] is not None,
                    "invalid host terminal result reference",
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
            if digest is not None and digest not in verified_artifacts:
                artifact = _read(
                    artifact_root / digest,
                    "host retained attempt artifact",
                    maximum=48_000_000,
                )
                _require(_hash(artifact) == digest, "host retained artifact changed")
                verified_artifacts.add(digest)
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
            not in {
                "queue_render",
                "start_render",
                "poll_render",
                "capture_post",
            },
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
            require_output_absent=request["action"]
            in {"retry_capture", "queue_render"},
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
    if request["profile"] in PUBLIC_PROFILES:
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
    elif request["profile"] == R16_PROFILE:
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
    elif request["profile"] == PRESENTER_PROFILE:
        _require(
            admission["disposition"] == "qualification_only"
            and admission["creativeQualification"] == "unqualified_temporary_presenter",
            "current Presenter package is not qualification-only",
        )
        _verify_presenter_input_scope(root, admission, manifest)
        source_root = root
    else:
        raise OutputConsistencyError("unsupported native package profile")
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


def _verify_presenter_original_currentness() -> dict[str, bytes]:
    """Read only the two pinned issue-owned Presenter fixture inputs."""
    try:
        snapshots: dict[str, bytes] = {}
        for name, expected_sha256 in _PRESENTER_ORIGINALS.items():
            path = _PRESENTER_INPUT_ROOT / name
            raw = _read(
                path, f"current Presenter original {name}", maximum=16 * 1024 * 1024
            )
            _require(
                _hash(raw) == expected_sha256,
                f"current Presenter original bytes changed: {name}",
            )
            snapshots[name] = raw
        return snapshots
    except OutputConsistencyError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise OutputConsistencyError(
            "current Presenter original inputs are unavailable"
        ) from error


def _verify_presenter_input_scope(
    root: Path, admission: dict[str, Any], manifest: dict[str, Any]
) -> None:
    originals = _verify_presenter_original_currentness()
    original_document = originals["script-document-v2.json"]
    original_dependencies = originals["compiler-dependencies-v2.json"]
    _require(
        admission["originalDocumentSha256"]
        == _PRESENTER_ORIGINALS["script-document-v2.json"]
        and admission["originalDependenciesSha256"]
        == _PRESENTER_ORIGINALS["compiler-dependencies-v2.json"],
        "current Presenter original input pins differ",
    )
    original_document_copy = _read(
        root / "Original/script-document-v2.json", "Presenter package original document"
    )
    original_dependencies_copy = _read(
        root / "Original/compiler-dependencies-v2.json",
        "Presenter package original dependencies",
    )
    execution_document = _read(
        root / "Execution/script-document-v2.json", "Presenter execution document"
    )
    execution_dependencies_raw = _read(
        root / "Execution/compiler-dependencies-v2.json",
        "Presenter execution dependencies",
    )
    _require(
        original_document_copy == original_document
        and original_dependencies_copy == original_dependencies
        and execution_document == original_document,
        "current Presenter original/execution document bytes differ",
    )
    _require(
        admission["executionDocumentSha256"]
        == _PRESENTER_ORIGINALS["script-document-v2.json"]
        and admission["executionDependenciesSha256"]
        == _hash(execution_dependencies_raw),
        "current Presenter execution input pins differ",
    )
    original_dependencies_value = _parse(original_dependencies)
    execution_dependencies_value = _parse(execution_dependencies_raw)
    _require(
        type(original_dependencies_value) is dict
        and type(execution_dependencies_value) is dict,
        "current Presenter dependency inputs must be JSON objects",
    )
    original_compiler = original_dependencies_value.get("compiler")
    execution_compiler = execution_dependencies_value.get("compiler")
    _require(
        type(original_compiler) is dict and type(execution_compiler) is dict,
        "current Presenter compiler identity is missing",
    )
    assert type(original_compiler) is dict
    assert type(execution_compiler) is dict
    _source_hash(execution_compiler.get("sourceHash"))
    expected_execution_dependencies = dict(original_dependencies_value)
    expected_execution_dependencies["compiler"] = dict(original_compiler)
    expected_execution_dependencies["compiler"]["sourceHash"] = execution_compiler[
        "sourceHash"
    ]
    _require(
        execution_dependencies_value == expected_execution_dependencies,
        "current Presenter execution dependencies changed beyond compiler.sourceHash",
    )
    _require(
        manifest.get("compiler") == execution_compiler,
        "current Presenter manifest compiler identity differs from execution inputs",
    )


_OUTPUT_RUNTIME_FILES = (
    "__init__.py",
    "studio_spike.py",
    "text_plus_template.py",
    "workflow_package.py",
    "workflow_delivery.py",
    "workflow_launcher.py",
    "workflow_v2.py",
    "performance_v2.py",
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
    if method == "Timeline.SetClipsLinked":
        request = state["request"]
        _require(
            request.get("action") == "construct"
            and request.get("profile") in CONSTRUCTOR_LINK_PROFILES,
            "qualification AV linking is limited to MATRIX/PRESENTER construction",
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


def _native_append_source_range(
    source_start: int,
    duration: int,
    source_frame_rate: Any,
    timeline_rate: dict[str, Any],
    *,
    still: bool,
) -> tuple[int, int]:
    """Return the source-frame half-open range passed to AppendToTimeline."""
    start = _integer(source_start)
    duration = _integer(duration, 1, MAX_NATIVE_EXTENT_FRAMES)
    if not still:
        return start, start + duration

    _require(
        type(source_frame_rate) in {str, int, float},
        "imported still frame rate is unavailable",
    )
    try:
        source_rate_decimal = Decimal(str(source_frame_rate))
    except InvalidOperation as error:
        raise OutputConsistencyError("imported still frame rate is invalid") from error
    _require(
        source_rate_decimal.is_finite() and source_rate_decimal > 0,
        "imported still frame rate is invalid",
    )
    source_rate = Fraction(source_rate_decimal)

    _shape(timeline_rate, "numerator denominator", "timeline frame rate")
    target_rate = Fraction(
        _integer(timeline_rate["numerator"], 1),
        _integer(timeline_rate["denominator"], 1),
    )
    source_duration = math.ceil(Fraction(duration) * source_rate / target_rate)
    return start, start + source_duration


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


def _validate_observed_event_geometry(
    events: dict[str, dict[str, Any]],
    items: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    raw_links: dict[str, list[str]],
    *,
    timeline_end: int,
    expected_end: int,
) -> int:
    """Admit unchanged items or one bounded still, AV-ripple, or narration edit.

    Returns the authenticated ripple trim in frames: positive only for one
    linked AV end trim whose uniform downstream shift shortened the programme.
    """
    by_event: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        by_event.setdefault(item["eventId"], []).append(item)
    _require(set(by_event) == set(events), "native event inventory is incomplete")

    def parent_ranges(event: dict[str, Any]) -> tuple[int, int, int, int]:
        record = event["recordRange"]
        record_start = _integer(record["startFrame"])
        record_duration = _integer(record["durationFrames"], 1)
        source_range = event.get("sourceRange")
        if source_range is None:
            source_start, source_duration = 0, record_duration
        else:
            source_range = _shape(
                source_range,
                frozenset({"startFrame", "durationFrames"}),
                "observed parent source range",
            )
            source_start = _integer(source_range["startFrame"])
            source_duration = _integer(source_range["durationFrames"], 1)
        return record_start, record_duration, source_start, source_duration

    moved_pictures: list[dict[str, Any]] = []
    trimmed: list[dict[str, Any]] = []
    ripple_shifted: set[str] = set()
    split_events: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    changed: set[str] = set()
    for event_id, group in by_event.items():
        event = events[event_id]
        record_start, record_duration, source_start, source_duration = parent_ranges(
            event
        )
        if len(group) == 2:
            _require(
                event["kind"] == "narration",
                "only an admitted narration event may split",
            )
            segments = sorted(group, key=lambda row: row["recordStart"])
            first, second = segments
            first_source_end = first["sourceStart"] + first["sourceDuration"]
            second_source_end = second["sourceStart"] + second["sourceDuration"]
            omitted = second["sourceStart"] - first_source_end
            record_gap = second["recordStart"] - (
                first["recordStart"] + first["recordDuration"]
            )
            _require(
                first["recordStart"] == record_start
                and first["sourceStart"] == source_start
                and first["recordDuration"] == first["sourceDuration"]
                and second["recordStart"] > first["recordStart"]
                and second["recordDuration"] == second["sourceDuration"]
                and omitted > 0
                and record_gap == omitted
                and second_source_end == source_start + source_duration
                and first_source_end < second["sourceStart"]
                and second["recordStart"] + second["recordDuration"]
                == record_start + record_duration
                and first["sourceStart"] - first["recordStart"]
                == source_start - record_start
                and second["sourceStart"] - second["recordStart"]
                == source_start - record_start,
                "narration split does not map two unique segments around one omission",
            )
            split_events.append((event, segments))
            changed.add(event_id)
            continue
        _require(len(group) == 1, "native event has an unsupported item multiplicity")
        item = group[0]
        record_exact = (
            item["recordStart"] == record_start
            and item["recordDuration"] == record_duration
        )
        source_exact = (
            item["sourceStart"] == source_start
            and item["sourceDuration"] == source_duration
        )
        if record_exact and source_exact:
            continue

        source = sources[event["sourceId"]]
        if (
            event["kind"]
            in {
                "primary_visual",
                "overlay_visual",
                "source_audio",
                "narration",
                "placeholder",
            }
            and item["recordDuration"] == record_duration
            and item["sourceStart"] == source_start
            and item["sourceDuration"] == source_duration
            and item["recordStart"] < record_start
        ):
            ripple_shifted.add(event_id)
            continue

        is_static_picture = event["kind"] in {
            "primary_visual",
            "overlay_visual",
            "placeholder",
        } and source["kind"] in {"still", "placeholder"}
        if (
            is_static_picture
            and item["sourceStart"] == source_start
            and item["sourceDuration"] == item["recordDuration"]
        ):
            moved_pictures.append(item)
            changed.add(event_id)
            continue
        if (
            event["kind"] in {"primary_visual", "overlay_visual", "source_audio"}
            and record_duration == source_duration
            and item["recordStart"] == record_start
            and item["recordDuration"] < record_duration
            and item["sourceStart"] == source_start
            and item["sourceDuration"] == item["recordDuration"]
        ):
            trimmed.append(item)
            changed.add(event_id)
            continue
        _require(False, "native edited item differs outside the observed edit rules")

    _require(
        len(moved_pictures) in {0, 2}
        and len(trimmed) in {0, 2}
        and len(split_events) <= 1,
        "observed edit multiplicity is outside the reviewed A/B/split cases",
    )
    _require(
        not (moved_pictures and trimmed)
        and not (split_events and (moved_pictures or trimmed)),
        "observed edit cases cannot be combined in one native capture",
    )
    _require(
        not ripple_shifted or bool(trimmed),
        "downstream shift is only admitted with a linked AV end trim",
    )
    if moved_pictures:
        moved_pictures.sort(key=lambda row: parent_ranges(events[row["eventId"]])[0])
        left, right = moved_pictures
        left_event, right_event = events[left["eventId"]], events[right["eventId"]]
        left_parent = parent_ranges(left_event)
        right_parent = parent_ranges(right_event)
        left_source = sources[left_event["sourceId"]]
        right_source = sources[right_event["sourceId"]]
        original_boundary = left_parent[0] + left_parent[1]
        observed_boundary = left["recordStart"] + left["recordDuration"]
        hold_frames = observed_boundary - original_boundary
        _require(
            left_source["kind"] in {"still", "placeholder"}
            and right_source["kind"] in {"still", "placeholder"}
            and left_event["kind"]
            in {"primary_visual", "overlay_visual", "placeholder"}
            and right_event["kind"]
            in {"primary_visual", "overlay_visual", "placeholder"}
            and left_parent[0] + left_parent[1] == right_parent[0]
            and left["recordStart"] == left_parent[0]
            and right["recordStart"] == observed_boundary
            and hold_frames > 0
            and left["recordDuration"] == left_parent[1] + hold_frames
            and right["recordDuration"] == right_parent[1] - hold_frames
            and right["recordDuration"] > 0
            and right["recordStart"] + right["recordDuration"]
            == right_parent[0] + right_parent[1]
            and left["sourceStart"] == left_parent[2]
            and right["sourceStart"] == right_parent[2]
            and left["sourceDuration"] == left["recordDuration"]
            and right["sourceDuration"] == right["recordDuration"],
            "held-picture boundary edit is not an adjacent hold transfer",
        )
        _require(
            timeline_end == expected_end,
            "held-picture boundary edit changed the original programme end",
        )
    if trimmed:
        trimmed.sort(key=lambda row: row["itemUid"])
        left, right = trimmed
        left_event, right_event = events[left["eventId"]], events[right["eventId"]]
        left_parent = parent_ranges(left_event)
        right_parent = parent_ranges(right_event)
        trim_frames = left_parent[1] - left["recordDuration"]
        _require(
            {left_event["kind"], right_event["kind"]}
            in (
                {"source_audio", "primary_visual"},
                {"source_audio", "overlay_visual"},
            )
            and {left["kind"], right["kind"]} == {"audio", "video"}
            and left_parent[:2] == right_parent[:2]
            and left["recordStart"] == right["recordStart"]
            and left["recordDuration"] == right["recordDuration"]
            and trim_frames > 0
            and right_parent[1] - right["recordDuration"] == trim_frames
            and right["sourceDuration"] == right["recordDuration"]
            and left["sourceDuration"] == left["recordDuration"]
            and right["itemUid"] in raw_links[left["itemUid"]]
            and left["itemUid"] in raw_links[right["itemUid"]],
            "AV trim is not one linked pair with matching source and record cuts",
        )
        original_end = left_parent[0] + left_parent[1]
        downstream = 0
        for event_id, group in by_event.items():
            if event_id in changed:
                continue
            event = events[event_id]
            start, duration, source_start, source_duration = parent_ranges(event)
            item = group[0]
            shift = trim_frames if start >= original_end else 0
            _require(
                item["recordStart"] == start - shift
                and item["recordDuration"] == duration
                and item["sourceStart"] == source_start
                and item["sourceDuration"] == source_duration,
                "linked AV end trim has an unpaired or nonuniform downstream shift",
            )
            downstream += shift > 0
        _require(downstream > 0, "linked AV end trim lacks its downstream ripple shift")
        _require(
            timeline_end == expected_end - trim_frames,
            "linked AV trim end differs from the admitted ripple extent",
        )
    if split_events:
        _require(
            timeline_end == expected_end,
            "narration split changed the original programme end",
        )
    if not (moved_pictures or trimmed or split_events):
        _require(
            timeline_end == expected_end,
            "unchanged edited target differs from the admitted programme end",
        )
    return expected_end - timeline_end


def _source_time_error_samples(
    value: Any, frame: int, rate_seconds: Fraction, sample_rate: int = 48_000
) -> Fraction | None:
    if type(value) is int:
        seconds = Fraction(value)
    elif type(value) is float and math.isfinite(value):
        seconds = Fraction(str(value))
    else:
        return None
    return (seconds - frame * rate_seconds) * sample_rate


def _verified_fractional_narration_eof(
    audio: Any,
    source_hash: str,
    rate: dict[str, Any],
    source_start: int,
    timeline_sample_rate: int,
    range_times: dict[str, Any],
) -> int | None:
    if (
        type(audio) is not dict
        or type(audio.get("audioHash")) is not str
        or _source_hash(audio["audioHash"]) != _source_hash(source_hash)
    ):
        return None
    sample_count, sample_rate = audio.get("durationSamples"), audio.get("sampleRate")
    if (
        type(sample_count) is not int
        or sample_count <= 0
        or type(sample_rate) is not int
        or sample_rate != timeline_sample_rate
    ):
        return None
    exact_frames = Fraction(
        sample_count * rate["numerator"], sample_rate * rate["denominator"]
    )
    expected_end = math.ceil(exact_frames)
    expected_duration = expected_end - source_start
    start_error = _source_time_error_samples(
        range_times.get("GetSourceStartTime"),
        source_start,
        Fraction(rate["denominator"], rate["numerator"]),
        sample_rate,
    )
    end_error = _source_time_error_samples(
        range_times.get("GetSourceEndTime"),
        sample_count,
        Fraction(1, sample_rate),
        sample_rate,
    )
    return (
        expected_duration
        if (
            exact_frames.denominator != 1
            and source_start >= 0
            and expected_duration > 0
            and start_error is not None
            and abs(start_error) <= 1
            and end_error is not None
            and abs(end_error) <= 1
        )
        else None
    )


def _verified_video_start_frame_rounding(
    *,
    event: dict[str, Any],
    manifest_event: dict[str, Any] | None,
    manifest_source: dict[str, Any] | None,
    verification: dict[str, Any] | None,
    source_hash: str,
    media_frames: Any,
    source_start: int,
    source_end: int,
    source_duration: int,
    expected_source_start: int,
    expected_source_end: int,
    expected_source_duration: int,
    record_duration: int,
    range_times: dict[str, Any],
    rate: dict[str, Any],
) -> bool:
    """Authenticate Resolve's one-frame integer in-point floor on a CFR source."""
    if (
        source_start != expected_source_start - 1
        or expected_source_start <= 0
        or expected_source_end != expected_source_start + expected_source_duration
        or not 0 < record_duration <= expected_source_duration
        or source_end != expected_source_start + record_duration
        or source_duration != record_duration + 1
        or type(verification) is not dict
        or type(manifest_event) is not dict
        or type(manifest_source) is not dict
    ):
        return False

    source_frame_map = manifest_source.get("sourceFrameMap")
    manifest_mapping = manifest_event.get("sourceTimeMapping")
    source_mapping = manifest_source.get("sourceTimeMapping")
    view_event = event.get("v2Event")
    expected_range = {
        "startFrame": expected_source_start,
        "endFrame": expected_source_end,
    }
    view_mapping = (
        view_event.get("sourceTimeMapping") if type(view_event) is dict else None
    )
    if (
        type(source_frame_map) is not dict
        or type(manifest_mapping) is not dict
        or type(source_mapping) is not dict
        or type(view_event) is not dict
        or type(view_mapping) is not dict
        or manifest_event.get("sourceRange") != expected_range
        or view_event.get("sourceRange") != expected_range
        or manifest_mapping != source_mapping
        or manifest_mapping != view_mapping
        or manifest_mapping.get("sourceFrameMap") != source_frame_map
        or manifest_mapping.get("sourceOrigin") != {"numerator": 0, "denominator": 1}
        or manifest_mapping.get("deliveredOrigin") != {"numerator": 0, "denominator": 1}
    ):
        return False

    frame_count = verification.get("decodedFrameCount")
    probe_hash = verification.get("probeHash")
    delivered_hash = verification.get("deliveredHash")
    frame_rate = verification.get("decodedFrameRate")
    mapped_count = source_frame_map.get("decodedPackageFrameCount")
    mapped_rate = source_frame_map.get("decodedPackageFrameRate")
    mapped_probe_hash = source_frame_map.get("probeHash")
    timeline_rate = {
        "numerator": rate["numerator"],
        "denominator": rate["denominator"],
    }
    if (
        type(frame_count) is not int
        or frame_count <= 0
        or type(mapped_count) is not int
        or frame_count != mapped_count
        or frame_rate != timeline_rate
        or mapped_rate != timeline_rate
        or manifest_mapping.get("sourceRate") != timeline_rate
        or manifest_mapping.get("deliveredRate") != timeline_rate
        or type(delivered_hash) is not str
        or _source_hash(delivered_hash) != _source_hash(source_hash)
        or type(manifest_source.get("deliveredHash")) is not str
        or _source_hash(manifest_source["deliveredHash"]) != _source_hash(source_hash)
        or type(probe_hash) is not str
        or probe_hash != mapped_probe_hash
        or probe_hash != manifest_source.get("deliveredProbeHash")
        or probe_hash != source_frame_map.get("descriptorHash")
        or type(media_frames) is not str
        or media_frames != str(frame_count)
        or expected_source_end > frame_count
        or source_frame_map.get("packageFrameZeroLogicalFrame") != 0
        or source_frame_map.get("packageVideoPtsOrigin")
        != {"numerator": 0, "denominator": 1}
        or source_frame_map.get("loggedTimeAtPackageFrameZero")
        != {"numerator": 0, "denominator": 1}
    ):
        return False

    frame_seconds = Fraction(rate["denominator"], rate["numerator"])
    start_error = _source_time_error_samples(
        range_times.get("GetSourceStartTime"), expected_source_start, frame_seconds
    )
    end_error = _source_time_error_samples(
        range_times.get("GetSourceEndTime"), source_end, frame_seconds
    )
    return (
        start_error is not None
        and abs(start_error) <= 1
        and end_error is not None
        and abs(end_error) <= 1
    )


def _native_record_frame_getter_matches(expected: int, actual: Any) -> bool:
    if type(expected) is not int:
        return False
    if type(actual) is int:
        return actual == expected
    if type(actual) is not float or not math.isfinite(actual):
        return False
    try:
        expected_float = float(expected)
    except OverflowError:
        return False
    if expected_float != expected:
        return False
    return actual in {
        expected_float,
        math.nextafter(expected_float, -math.inf),
        math.nextafter(expected_float, math.inf),
    }


def _native_audio_gain_readback_matches(expected: Any, actual: Any) -> bool:
    """Accept the declared gain or its exact IEEE-754 float32 representation."""
    if type(expected) not in {int, float} or type(actual) not in {int, float}:
        return False
    try:
        expected_float = float(expected)
        actual_float = float(actual)
    except OverflowError:
        return False
    if not math.isfinite(expected_float) or not math.isfinite(actual_float):
        return False
    try:
        float32_expected = struct.unpack("!f", struct.pack("!f", expected_float))[0]
    except (OverflowError, struct.error):
        return False
    return actual in (expected, float32_expected)


def _capture_geometry(
    resolve: Any,
    request: dict[str, Any],
    admitted: dict[str, Any],
    input_binding: dict[str, Any] | None,
    *,
    _observed_edit: bool = False,
) -> dict[str, Any]:
    _, project, timeline = _project_timeline(resolve, request)
    manifest, view = admitted["manifest"], admitted["view"]
    expected_timeline = manifest["timeline"]
    _verify_admitted_extent(manifest)
    rate = expected_timeline["frameRate"]
    _rate_float(rate)
    actual_rate = timeline.GetSetting("timelineFrameRate")
    _require(
        _setting_matches("timelineFrameRate", "23.976", actual_rate),
        "native timeline rate getter differs "
        f"(actual {_setting_readback_description(actual_rate)})",
    )
    for key, expected in (
        ("timelineResolutionWidth", expected_timeline["width"]),
        ("timelineResolutionHeight", expected_timeline["height"]),
    ):
        actual = timeline.GetSetting(key)
        _require(
            type(actual) in {str, int}
            and str(actual).isdigit()
            and int(actual) == expected,
            f"native timeline setting {key} differs or is unreadable",
        )
    sample_rate = project.GetSetting("timelineSampleRate")
    _require(
        type(sample_rate) in {str, int}
        and str(sample_rate).isdigit()
        and int(sample_rate) == expected_timeline["audioSampleRate"],
        "native project setting timelineSampleRate differs or is unreadable",
    )
    timeline_start = timeline.GetStartFrame()
    timeline_end = timeline.GetEndFrame()
    expected_end = timeline_start + expected_timeline["durationFrames"]
    _require(
        type(timeline_start) is int
        and timeline_start == expected_timeline["startFrame"],
        "native timeline start differs",
    )
    if _observed_edit:
        _require(
            request["context"].get("phase") == "edited"
            and type(timeline_end) is int
            and timeline_start < timeline_end <= expected_end,
            "observed edited timeline end is outside the admitted programme",
        )
    else:
        _require(
            type(timeline_end) is int and timeline_end == expected_end,
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
    manifest_events = {row["eventId"]: row for row in manifest.get("events", [])}
    manifest_sources = {row["id"]: row for row in manifest.get("sources", [])}
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
                _require(event is not None, "missing/unadmitted native event stamp")
                assert event is not None
                manifest_event = manifest_events.get(event_id)
                if not _observed_edit:
                    _require(
                        event_id not in event_ids,
                        "missing/duplicate/unadmitted native event stamp",
                    )
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
                    source_id == event["sourceId"],
                    "native event is bound to a different admitted source",
                )
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
                static_picture = kind == "video" and source.get("kind") in {
                    "still",
                    "placeholder",
                }
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
                    and (
                        source_end > source_start
                        or (
                            (kind == "audio" or static_picture)
                            and source_end == source_start
                        )
                    ),
                    "unsupported native range getter "
                    f"(kind={kind}, record="
                    f"({record_start!r},{duration!r},{record_end!r}), "
                    f"source=({source_start!r},{source_end!r}), "
                    f"static={static_picture})",
                )
                record_getters = {
                    "GetStart(False)": record_start,
                    "GetDuration(False)": duration,
                    "GetEnd(False)": record_end,
                }
                frame_getters = {
                    method: getattr(item, method)(True)
                    for method in ("GetStart", "GetDuration", "GetEnd")
                }
                _require(
                    all(
                        _native_record_frame_getter_matches(
                            observed, frame_getters[method]
                        )
                        for method, observed in (
                            ("GetStart", record_start),
                            ("GetDuration", duration),
                            ("GetEnd", record_end),
                        )
                    ),
                    "unsupported fractional native record geometry "
                    f"(track={kind}:{index}, itemUid={uid}, eventId={event_id}, "
                    f"recordGetters={record_getters!r}, "
                    f"frameGetters={frame_getters!r})",
                )
                _require(
                    timeline_start
                    <= record_start
                    < record_start + duration
                    <= timeline_end,
                    "native item lies outside programme extent",
                )
                speed = item.GetSpeed()
                allowed_speed_options = frozenset(
                    {
                        "Percentage",
                        "PitchCorrection",
                        "StretchKeyframesToFit",
                        "RippleTimeline",
                    }
                )
                _require(
                    type(speed) is dict
                    and "Percentage" in speed
                    and speed.keys() <= allowed_speed_options,
                    "closed native speed options shape",
                )
                # Static images may report a frozen 0% source clock.
                _require(
                    type(speed["Percentage"]) in {int, float}
                    and (
                        speed["Percentage"] == 100
                        or (
                            request.get("profile")
                            in {MATRIX_PROFILE, PRESENTER_PROFILE}
                            and static_picture
                            and speed["Percentage"] == 0
                        )
                    )
                    and (
                        "PitchCorrection" not in speed
                        or type(speed["PitchCorrection"]) is bool
                    )
                    and all(
                        option not in speed
                        or (type(speed[option]) is bool and speed[option] is False)
                        for option in ("StretchKeyframesToFit", "RippleTimeline")
                    ),
                    f"non-unit/unreadable native speed (static={static_picture}, "
                    f"speed={speed!r})",
                )
                _require(item.GetClipEnabled() is True, "disabled native item")
                record = event["recordRange"]
                if not _observed_edit:
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
                # Video end getters are exclusive in the clip interior, but Studio
                # saturates them at the last source frame when the clip reaches EOF.
                expected_source_end = expected_source_start + expected_source_duration
                verified_video_frames = None
                verified_video_verification = None
                verified_video_binding = None
                manifest_source = manifest_sources.get(source_id)
                if kind == "video":
                    for manifest_source_row in manifest.get("sources", []):
                        if manifest_source_row["id"] != source_id:
                            continue
                        for binding in manifest.get("preparationBindings", []):
                            if binding["requirementKey"] == manifest_source_row.get(
                                "preparationRequirementKey"
                            ):
                                verification = binding["verification"]
                                if _source_hash(
                                    verification["deliveredHash"]
                                ) == _source_hash(source["contentHash"]):
                                    verified_video_frames = verification[
                                        "decodedFrameCount"
                                    ]
                                    verified_video_verification = verification
                                    verified_video_binding = binding
                video_end_saturated_at_eof = (
                    kind == "video"
                    and type(verified_video_frames) is int
                    and verified_video_frames == expected_source_end
                    and props.get("Frames") == str(expected_source_end)
                    and source_end == expected_source_end - 1
                    and expected_source_duration == duration
                )
                source_duration = (
                    source_end
                    - source_start
                    + (kind == "audio" or video_end_saturated_at_eof)
                )
                # A still has no advancing source clock; its held extent is the
                # exact record duration, while the single source frame stays zero.
                if (
                    static_picture
                    and source_start == source_end == expected_source_start == 0
                    and expected_source_duration == duration
                ):
                    source_duration = duration
                range_times = {}
                if (
                    source_start != expected_source_start
                    or source_duration != expected_source_duration
                    or (
                        _observed_edit
                        and request.get("profile")
                        in {MATRIX_PROFILE, PRESENTER_PROFILE}
                        and kind == "audio"
                    )
                ):
                    for method_name in ("GetSourceStartTime", "GetSourceEndTime"):
                        method = getattr(item, method_name, None)
                        if callable(method):
                            range_times[method_name] = method()
                if (
                    request.get("profile") == MATRIX_PROFILE
                    and kind == "video"
                    and source.get("kind") == "video"
                    and not static_picture
                    and verified_video_binding is not None
                    and verified_video_binding.get("mode") == "derived_cfr"
                ):
                    from .workflow_v2 import _fractional_source_range_matches

                    if _fractional_source_range_matches(
                        event=event,
                        source=source,
                        manifest_source=manifest_source or {},
                        preparation_bindings={
                            verified_video_binding[
                                "requirementKey"
                            ]: verified_video_binding
                        },
                        timeline=expected_timeline,
                        actual_start=source_start,
                        actual_end=source_end,
                        source_times=range_times,
                        speed=speed,
                        media_properties=props,
                        record_duration=duration,
                    ):
                        # Reuse the byte/rate/derivation-bound delivered-clock
                        # check; retain the raw integer getters in the capture.
                        source_start = expected_source_start
                        source_duration = expected_source_duration
                if (
                    request.get("profile") in {MATRIX_PROFILE, PRESENTER_PROFILE}
                    and request["context"].get("phase")
                    in {"pristine", "edited", "rebuild"}
                    and kind == "video"
                    and source.get("kind") == "video"
                    and not static_picture
                    and _verified_video_start_frame_rounding(
                        event=event,
                        manifest_event=manifest_event,
                        manifest_source=manifest_source,
                        verification=verified_video_verification,
                        source_hash=source["contentHash"],
                        media_frames=props.get("Frames"),
                        source_start=source_start,
                        source_end=source_end,
                        source_duration=source_duration,
                        expected_source_start=expected_source_start,
                        expected_source_end=expected_source_end,
                        expected_source_duration=expected_source_duration,
                        record_duration=duration,
                        range_times=range_times,
                        rate=rate,
                    )
                ):
                    # Resolve's integer getter can floor this boundary by one
                    # frame. Exact authenticated source times preserve the actual
                    # outpoint, including an admitted end trim.
                    source_start = expected_source_start
                    source_duration = duration
                fractional_narration_eof = False
                if (
                    not _observed_edit
                    and request.get("profile") == MATRIX_PROFILE
                    and request["context"].get("phase") in {"pristine", "rebuild"}
                    and kind == "audio"
                    and source.get("kind") == "audio"
                    and event.get("kind") == "narration"
                    and manifest_event is not None
                    and manifest_event.get("kind") == "narration"
                    and "sourceRange" in manifest_event
                    and manifest_event["sourceRange"] is None
                    and source_start == expected_source_start == 0
                    and expected_source_duration == duration
                    and source_end == expected_source_end - 2
                    and source_duration == expected_source_duration - 1
                ):
                    expected_narration_duration = _verified_fractional_narration_eof(
                        manifest_sources.get(source_id, {}).get("narrationAudio"),
                        source["contentHash"],
                        rate,
                        source_start,
                        expected_timeline["audioSampleRate"],
                        range_times,
                    )
                    fractional_narration_eof = (
                        expected_narration_duration == expected_source_duration
                    )
                if fractional_narration_eof:
                    # Keep raw getters; normalize only the proven comparison extent.
                    source_duration = expected_source_duration
                still_frame_seconds = None
                still_fps = props.get("FPS")
                if static_picture and type(still_fps) in {str, int, float}:
                    try:
                        fps_decimal = Decimal(str(still_fps))
                        if fps_decimal.is_finite() and fps_decimal > 0:
                            still_frame_seconds = Fraction(1, 1) / Fraction(fps_decimal)
                    except (InvalidOperation, ZeroDivisionError):
                        pass
                still_start_error = _source_time_error_samples(
                    range_times.get("GetSourceStartTime"), 0, Fraction(1)
                )
                timeline_end_error = _source_time_error_samples(
                    range_times.get("GetSourceEndTime"),
                    1,
                    Fraction(rate["denominator"], rate["numerator"]),
                )
                still_end_error = (
                    _source_time_error_samples(
                        range_times.get("GetSourceEndTime"),
                        1,
                        still_frame_seconds,
                    )
                    if still_frame_seconds is not None
                    else None
                )
                still_time_edges_match = (
                    still_start_error is not None
                    and abs(still_start_error) <= 1
                    and (
                        (
                            timeline_end_error is not None
                            and abs(timeline_end_error) <= 1
                        )
                        or (still_end_error is not None and abs(still_end_error) <= 1)
                    )
                )
                # Studio can expose its arbitrary held-frame counter for a still.
                # Its source clock can use the imported still FPS, not timeline FPS.
                if (
                    request.get("profile") in {MATRIX_PROFILE, PRESENTER_PROFILE}
                    and static_picture
                    and source_start == source_end
                    and source_start >= 0
                    and expected_source_start == 0
                    and (expected_source_duration == duration or _observed_edit)
                    and props.get("Frames") == "1"
                    and still_time_edges_match
                ):
                    source_start = 0
                    source_duration = duration
                if (
                    _observed_edit
                    and static_picture
                    and source_start == source_end == expected_source_start
                    and source_start >= 0
                    and props.get("Frames") == "1"
                    and expected_source_duration == record["durationFrames"]
                ):
                    source_duration = duration
                if (
                    request.get("profile") in {MATRIX_PROFILE, PRESENTER_PROFILE}
                    and kind == "audio"
                    and (
                        _observed_edit
                        or (
                            source_start == expected_source_start
                            and source_end == expected_source_end
                        )
                    )
                ):
                    sample_tolerance = Fraction(1, 48000)
                    rate_seconds = Fraction(1001, 24000)
                    start_frame = (
                        source_start if _observed_edit else expected_source_start
                    )
                    end_frame = source_end if _observed_edit else expected_source_end
                    edges = (
                        ("GetSourceStartTime", start_frame),
                        ("GetSourceEndTime", end_frame),
                    )
                    if _observed_edit:
                        start_time = range_times.get("GetSourceStartTime")
                        end_time = range_times.get("GetSourceEndTime")
                        start_error = _source_time_error_samples(
                            start_time, start_frame, rate_seconds
                        )
                        exclusive_end_error = _source_time_error_samples(
                            end_time, source_end, rate_seconds
                        )
                        inclusive_end_error = _source_time_error_samples(
                            end_time, source_end + 1, rate_seconds
                        )
                        sample_errors = {
                            "start": start_error,
                            "exclusiveEnd": exclusive_end_error,
                            "inclusiveEnd": inclusive_end_error,
                        }
                        matching_end_frames = [
                            frame
                            for frame, error in (
                                (source_end, exclusive_end_error),
                                (source_end + 1, inclusive_end_error),
                            )
                            if error is not None and abs(error) <= 1
                        ]
                        narration_eof_duration = None
                        if (
                            request.get("profile") == MATRIX_PROFILE
                            and request["context"].get("phase") == "edited"
                            and kind == "audio"
                            and source.get("kind") == "audio"
                            and event.get("kind") == "narration"
                        ):
                            narration_eof_duration = _verified_fractional_narration_eof(
                                manifest_sources.get(source_id, {}).get(
                                    "narrationAudio"
                                ),
                                source["contentHash"],
                                rate,
                                source_start,
                                expected_timeline["audioSampleRate"],
                                range_times,
                            )
                            if (
                                narration_eof_duration is not None
                                and duration == narration_eof_duration
                                and source_end
                                == source_start + narration_eof_duration - 2
                                and source_duration == narration_eof_duration - 1
                            ):
                                source_duration = narration_eof_duration
                            else:
                                narration_eof_duration = None
                        exact_frame_edges = (
                            start_error is not None
                            and abs(start_error) <= 1
                            and (
                                narration_eof_duration is not None
                                or len(matching_end_frames) == 1
                            )
                        )
                        _require(
                            exact_frame_edges,
                            "edited audio source range lacks sample-accurate edges "
                            f"(track={kind}:{index}, itemUid={uid}, "
                            f"sourceId={source_id}, "
                            f"sourceFrames=({source_start},{source_end}), "
                            f"GetSourceStartTime={start_time!r}, "
                            f"GetSourceEndTime={end_time!r}, "
                            "expectedSourceTimes="
                            f"(start={start_frame * rate_seconds!r}, "
                            f"endExclusive={source_end * rate_seconds!r}, "
                            f"endInclusive={(source_end + 1) * rate_seconds!r}), "
                            f"sampleErrors={sample_errors!r}, "
                            "toleranceSamples=1)",
                        )
                        if narration_eof_duration is None:
                            assert len(matching_end_frames) == 1
                            source_duration = matching_end_frames[0] - start_frame
                    else:
                        exact_frame_edges = all(
                            type(range_times.get(method)) in {int, float}
                            and math.isfinite(range_times[method])
                            and abs(
                                Fraction(str(range_times[method]))
                                - frame * rate_seconds
                            )
                            <= sample_tolerance
                            for method, frame in edges
                        )
                    if exact_frame_edges and not _observed_edit:
                        source_duration = source_end - source_start
                if not _observed_edit:
                    _require(
                        source_start == expected_source_start
                        and source_duration == expected_source_duration,
                        "native source range differs "
                        f"(track={kind}:{index}, itemUid={uid}, eventId={event_id}, "
                        f"start={source_start}, end={source_end}, "
                        f"expectedStart={expected_source_start}, "
                        f"expectedDuration={expected_source_duration}, "
                        f"mediaFrames={props.get('Frames')!r}, "
                        f"sourceTimes={range_times!r})",
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
                        and _native_audio_gain_readback_matches(
                            gain, properties.get("AudioVolume")
                        ),
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
                        "sourceDuration": source_duration,
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
    if _observed_edit:
        _require(bool(items), "observed native event inventory is empty")
        observed_end = max(
            item["recordStart"] + item["recordDuration"] for item in items
        )
        _require(
            timeline_end == observed_end,
            "observed timeline end differs from the captured item extent",
        )
        ripple_trim = _validate_observed_event_geometry(
            expected_events,
            items,
            sources,
            raw_links,
            timeline_end=timeline_end,
            expected_end=expected_end,
        )
    else:
        ripple_trim = 0
    extent_frames = expected_timeline["durationFrames"] - ripple_trim
    _require(
        0 < extent_frames <= expected_timeline["durationFrames"],
        "authenticated programme extent is outside the admitted interval",
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
        # The admitted interval, shortened only by an authenticated linked AV
        # ripple trim; render marks, decode and prediction all bind this extent.
        "extentFrames": extent_frames,
        "rate": rate,
        "tracks": tracks,
        "items": items,
        "sourceMappings": source_mappings,
    }
    return geometry


def _capture_observed_geometry(
    resolve: Any,
    request: dict[str, Any],
    admitted: dict[str, Any],
    input_binding: dict[str, Any] | None,
) -> dict[str, Any]:
    """Read an edited target through the bounded observation-only geometry rules."""
    _require(
        request["context"].get("phase") == "edited",
        "observed edit capture requires an edited context",
    )
    return _capture_geometry(
        resolve, request, admitted, input_binding, _observed_edit=True
    )


def _setting_matches(key: str, expected: str, actual: Any) -> bool:
    if key != "timelineFrameRate":
        return type(actual) is str and actual == expected
    if type(expected) is not str or type(actual) not in {str, float}:
        return False
    try:
        actual_rate = Decimal(str(actual))
        expected_rate = Decimal(expected)
    except (InvalidOperation, ValueError):
        return False
    return (
        actual_rate.is_finite()
        and expected_rate.is_finite()
        and actual_rate == expected_rate
    )


def _setting_readback_description(actual: Any) -> str:
    actual_type = type(actual).__name__
    if type(actual) is str:
        rendered = repr(actual[:160] + ("…" if len(actual) > 160 else ""))
    elif actual is None or type(actual) in {bool, int, float}:
        rendered = repr(actual)
    else:
        rendered = f"<{actual_type}>"
    return f"{rendered} ({actual_type})"


def _set_project_settings(
    project: Any, settings: dict[str, str], state: dict[str, Any]
) -> None:
    for key, value in settings.items():
        current = project.GetSetting(key)
        if _setting_matches(key, value, current):
            continue
        row = _private_effect(state, "Project.SetSetting", {"key": key, "value": value})
        returned = project.SetSetting(key, value)
        _require(returned is True, f"Resolve refused project setting {key}")
        readback = project.GetSetting(key)
        _require(
            _setting_matches(key, value, readback),
            "project setting "
            f"{key} did not read back "
            f"(actual {_setting_readback_description(readback)})",
        )
        _effect_observed(state, row, {"return": returned, "value": readback})


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


def _unbound_geometry_projection(geometry: dict[str, Any]) -> dict[str, Any]:
    return {
        **geometry,
        "sourceMappings": [],
        "items": [{**item, "sourceMappingSha256": None} for item in geometry["items"]],
    }


def _constructor_av_link_pairs(
    view: dict[str, Any], profile: str
) -> list[tuple[str, str]]:
    """Select only authored, same-occurrence AV pairs for qualification targets."""
    if profile not in CONSTRUCTOR_LINK_PROFILES:
        return []

    sources = {source["id"]: source for source in view["sources"]}
    groups: dict[tuple[Any, ...], dict[str, list[dict[str, Any]]]] = {}
    for event in view["events"]:
        kind = event["kind"]
        if kind not in {"primary_visual", "overlay_visual", "source_audio"}:
            continue
        authored = event.get("v2Event")
        provenance = authored.get("provenance") if type(authored) is dict else None
        if type(provenance) is not dict:
            continue
        source_id = event.get("sourceId")
        source = sources.get(source_id) if type(source_id) is str else None
        authored_source_id = provenance.get("sourceId")
        delivered_hash = provenance.get("deliveredSourceHash")
        if (
            type(source) is not dict
            or type(source.get("contentHash")) is not str
            or type(authored_source_id) is not str
            or type(delivered_hash) is not str
        ):
            continue
        _identity(source_id)
        _source_hash(source["contentHash"])
        authored_source_id = _identity(authored_source_id)
        authored_source = sources.get(authored_source_id)
        if (
            type(authored_source) is not dict
            or type(authored_source.get("contentHash")) is not str
            or _source_hash(authored_source["contentHash"])
            != _source_hash(delivered_hash)
        ):
            continue
        authored_source_hash = _source_hash(delivered_hash)
        identity_fields = ("documentId", "blockId", "payloadId")
        if any(type(provenance.get(field)) is not str for field in identity_fields):
            continue
        authored_identity = tuple(
            _identity(provenance[field]) for field in identity_fields
        )
        occurrence_fields = ("sequenceId", "slotId", "overlayEventId")
        occurrence = tuple(provenance.get(field) for field in occurrence_fields)
        if any(value is not None and type(value) is not str for value in occurrence):
            continue
        occurrence = tuple(
            None if value is None else _identity(value) for value in occurrence
        )
        record = event.get("recordRange")
        if (
            type(record) is not dict
            or type(record.get("startFrame")) is not int
            or type(record.get("durationFrames")) is not int
            or record["startFrame"] < 0
            or record["durationFrames"] <= 0
        ):
            continue
        key = (
            *authored_identity,
            authored_source_id,
            authored_source_hash,
            *occurrence,
            record["startFrame"],
            record["durationFrames"],
        )
        group = groups.setdefault(key, {"visual": [], "audio": []})
        group["audio" if kind == "source_audio" else "visual"].append(event)

    pairs: list[tuple[str, str]] = []
    for group in groups.values():
        if group["visual"] and group["audio"]:
            _require(
                len(group["visual"]) == len(group["audio"]) == 1,
                "ambiguous qualification constructor AV link pair",
            )
            visual, audio = group["visual"][0], group["audio"][0]
            pairs.append((_identity(visual["id"]), _identity(audio["id"])))
    return pairs


def _link_constructed_av_pairs(
    timeline: Any,
    pairs: list[tuple[str, str]],
    items_by_event: dict[str, Any],
    state: dict[str, Any],
) -> None:
    if not pairs:
        return
    _require_api(timeline, ("SetClipsLinked",), "qualification timeline")
    used_events: set[str] = set()
    for visual_id, audio_id in pairs:
        _require(
            visual_id != audio_id
            and visual_id not in used_events
            and audio_id not in used_events
            and visual_id in items_by_event
            and audio_id in items_by_event,
            "qualification AV constructor pair is incomplete",
        )
        used_events.update((visual_id, audio_id))
        visual, audio = items_by_event[visual_id], items_by_event[audio_id]
        visual_uid, audio_uid = (
            _identity(visual.GetUniqueId()),
            _identity(audio.GetUniqueId()),
        )
        _require(visual_uid != audio_uid, "qualification AV items share a native UID")
        row = _private_effect(
            state,
            "Timeline.SetClipsLinked",
            {"itemUids": [visual_uid, audio_uid], "linked": True},
        )
        linked = timeline.SetClipsLinked([visual, audio], True)
        _require(linked is True, "Resolve did not confirm qualification AV linking")
        observed_links: dict[str, list[str]] = {}
        for item, uid, peer_uid in (
            (visual, visual_uid, audio_uid),
            (audio, audio_uid, visual_uid),
        ):
            linked_items = item.GetLinkedItems()
            _require(
                type(linked_items) in {list, tuple},
                "qualification AV link readback is unavailable",
            )
            linked_uids = sorted(_identity(peer.GetUniqueId()) for peer in linked_items)
            _require(
                linked_uids == [peer_uid],
                "qualification AV link readback differs from the exact pair",
            )
            observed_links[uid] = linked_uids
        _effect_observed(
            state,
            row,
            {"return": linked, "linkedItemUids": observed_links},
        )


def _construct(
    resolve: Any,
    request: dict[str, Any],
    admitted: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    connected = _connected(resolve)
    _, project, timeline = _project_timeline(resolve, request)
    manifest, view = admitted["manifest"], admitted["view"]
    av_link_pairs = _constructor_av_link_pairs(view, request.get("profile", ""))
    required_track_counts = _required_track_counts(view)
    start_frame = _check_empty_target(project, timeline, required_track_counts)
    settings = _project_settings(manifest)
    expected_rate = settings.pop("timelineFrameRate")
    _require(
        _setting_matches(
            "timelineFrameRate", expected_rate, project.GetSetting("timelineFrameRate")
        ),
        "target project timeline frame rate differs; configure it before "
        "creating the timeline",
    )
    _normalize_target_start_timecode(timeline, start_frame, state)
    pool = project.GetMediaPool()
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
    media_properties_by_path: dict[str, dict[str, Any]] = {}
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
        media_properties_by_path[resolved] = props
    _require(
        set(media_by_path) == set(source_paths),
        "Resolve imported different source files",
    )
    source_by_id = {source["id"]: source for source in sources}
    media_by_source = {
        source["id"]: media_by_path[path]
        for source, path in zip(sources, source_paths, strict=True)
    }
    media_properties_by_source = {
        source["id"]: media_properties_by_path[path]
        for source, path in zip(sources, source_paths, strict=True)
    }
    items_by_event: dict[str, Any] = {}
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
    still_source_ids = {
        event["sourceId"]
        for event in view["events"]
        if source_by_id[event["sourceId"]]["kind"] in {"still", "placeholder"}
        or event.get("kind") in {"still", "placeholder"}
    }
    for source_id in still_source_ids:
        _native_append_source_range(
            0,
            1,
            media_properties_by_source[source_id].get("FPS"),
            manifest["timeline"]["frameRate"],
            still=True,
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
        append_source_start, append_source_end = _native_append_source_range(
            source_start,
            duration,
            media_properties_by_source[event["sourceId"]].get("FPS"),
            manifest["timeline"]["frameRate"],
            still=still,
        )
        append_source_duration = append_source_end - append_source_start
        marked = False
        if still:
            row = _private_effect(
                state,
                "MediaPoolItem.SetMarkInOut",
                {
                    "sourceId": event["sourceId"],
                    "start": append_source_start,
                    "end": append_source_end,
                    "mediaType": "video",
                },
            )
            marked_ok = media.SetMarkInOut(
                append_source_start, append_source_end, "video"
            )
            _require(marked_ok is True, "still source mark range was refused")
            marked = True
            _effect_observed(state, row, {"return": marked_ok})
        append_row: dict[str, Any] | None = None
        try:
            # Resolve's exclusive endFrame is in the imported source frame domain.
            info = {
                "mediaPoolItem": media,
                "startFrame": append_source_start,
                "endFrame": append_source_end,
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
                    "sourceStart": append_source_start,
                    "sourceDuration": append_source_duration,
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
        items_by_event[_identity(event["id"])] = item
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
                and _native_audio_gain_readback_matches(
                    gain, actual.get("AudioVolume")
                ),
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
    _link_constructed_av_pairs(timeline, av_link_pairs, items_by_event, state)
    geometry = _capture_geometry(resolve, request, admitted, None)
    return {"nativeGeometry": geometry, "nativeIdentity": connected}


def _previous_result(
    request: dict[str, Any], action: str
) -> tuple[dict[str, Any], str, Path]:
    sequence = request["sequence"] - 1
    _require(
        sequence >= 0 and native_action(request["context"], sequence) == action,
        "native action order differs",
    )
    result_path = native_request_paths(request["context"], sequence)[0]
    raw = _read(result_path, "native predecessor")
    digest = _hash(raw)
    _require(digest == request["priorResultSha256"], "native predecessor hash differs")
    result = verify_native_result(result_path, digest)
    _require(
        result["action"] == action
        and (
            result["status"] == "complete"
            or (action == "poll_render" and _terminal_failed_render(result))
        ),
        "complete native predecessor or authenticated failed render required",
    )
    if action == "poll_render" and _terminal_failed_render(result):
        verified_render_failure(request["context"])
    return result, digest, result_path


def _verify_readonly_native_lineage(request: dict[str, Any]) -> None:
    if request["action"] == "poll_render":
        _previous_result(request, "start_render")
    elif request["action"] in {"capture_post", "retry_capture"}:
        _previous_result(request, "poll_render")


def _terminal_failed_render(result: dict[str, Any]) -> bool:
    render_status = result.get("renderStatus")
    return (
        result.get("action") == "poll_render"
        and result.get("status") == "partial"
        and type(render_status) is dict
        and render_status.get("JobStatus") in {"Failed", "Cancelled"}
    )


def _verify_retry_capture_geometry(
    result: dict[str, Any], original_capture: dict[str, Any]
) -> None:
    _require(
        original_capture["action"] == "capture_pre"
        and original_capture["status"] == "complete",
        "original complete geometry/input binding is unavailable",
    )
    if result["status"] == "complete":
        _require(
            result["nativeGeometry"] == original_capture["nativeGeometry"]
            and result["inputBindingSha256"] == original_capture["inputBindingSha256"],
            "retry capture differs from original complete geometry/input binding",
        )


def _wait_for_reopened_media_pool_items(
    resolve: Any,
    request: dict[str, Any],
    admitted: dict[str, Any],
    expected_geometry: dict[str, Any],
) -> None:
    """Wait for the prior item inventory and its media handles after reload."""
    tracks = admitted["view"]["tracks"]
    _require(type(tracks) is list, "admitted native track inventory is unavailable")
    expected_counts: dict[str, int] = {}
    for track in tracks:
        _require(type(track) is dict, "admitted native track row is unavailable")
        track_id = _identity(track.get("id"))
        _require(track_id not in expected_counts, "duplicate admitted native track")
        expected_counts[track_id] = 0
    expected_items = expected_geometry.get("items")
    _require(
        type(expected_items) is list
        and len(expected_items) <= MAX_ITEMS * max(1, len(tracks)),
        "prior native item inventory is unavailable/oversized",
    )
    assert type(expected_items) is list
    for item in expected_items:
        _require(type(item) is dict, "prior native item row is unavailable")
        track_id = _identity(item.get("trackId"))
        _require(
            track_id in expected_counts,
            "prior native item is outside the admitted track inventory",
        )
        expected_counts[track_id] += 1

    deadline = time.monotonic() + MAX_REOPEN_MEDIA_POOL_READY_SECONDS
    while True:
        _, _, timeline = _project_timeline(resolve, request)
        ready = True
        unavailable_reason = "native item inventory is incomplete"
        for track in tracks:
            items = timeline.GetItemListInTrack(track["kind"], track["index"])
            if items is None:
                ready = False
                unavailable_reason = "native item inventory is unavailable"
                break
            _require(
                type(items) in {list, tuple} and len(items) <= MAX_ITEMS,
                "native item inventory unavailable/oversized",
            )
            expected_count = expected_counts[track["id"]]
            if len(items) < expected_count:
                ready = False
                unavailable_reason = "native item inventory is incomplete"
                break
            _require(
                len(items) == expected_count,
                "reopened native item inventory differs",
            )
            for item in items:
                _require_api(item, ("GetMediaPoolItem",), "TimelineItem")
                if item.GetMediaPoolItem() is None:
                    ready = False
                    unavailable_reason = "MediaPoolItem is unavailable"
                    break
            if not ready:
                break
        if ready:
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OutputConsistencyError(unavailable_reason)
        time.sleep(min(POLL_INTERVAL_SECONDS, remaining))


def _save_reopen(
    resolve: Any,
    request: dict[str, Any],
    admitted: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    observed_edit = request["context"].get("phase") == "edited"
    previous_action = "observe_edited" if observed_edit else "construct"
    previous, _, _ = _previous_result(request, previous_action)
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
    _wait_for_reopened_media_pool_items(
        resolve, request, admitted, previous["nativeGeometry"]
    )
    geometry = (
        _capture_observed_geometry(resolve, request, admitted, None)
        if observed_edit
        else _capture_geometry(resolve, request, admitted, None)
    )
    _require(
        geometry == previous["nativeGeometry"],
        "saved/reopened native geometry differs from the prior readback",
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
        and request["sequence"]
        in {
            len(APPROVAL_ACTION_PLAN) - 1,
            len(APPROVAL_ACTION_PLAN) + len(RETRY_ACTION_PLAN) - 2,
        },
        "render lineage is only valid at the fixed post-render stage",
    )
    queue_path = native_request_paths(request["context"], request["sequence"] - 3)[0]
    start_path = native_request_paths(request["context"], request["sequence"] - 2)[0]
    queue_raw = _read(queue_path, "native queue receipt")
    start_raw = _read(start_path, "native start receipt")
    queue_sha, start_sha = _hash(queue_raw), _hash(start_raw)
    with _verification_scope():
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
    geometry = (
        _capture_observed_geometry(resolve, request, admitted, binding)
        if request["context"].get("phase") == "edited"
        else _capture_geometry(resolve, request, admitted, binding)
    )
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


def _edited_render_marks(
    settings: dict[str, Any], geometry: dict[str, Any]
) -> tuple[int, int, bool]:
    """Bind edited marks to the authenticated geometry extent.

    The approved settings remain the admitted interval and bound the marks; a
    shorter extent exists only after an authenticated linked ripple trim.
    """
    start, end = settings.get("startFrame"), settings.get("endFrame")
    extent = geometry.get("extentFrames")
    _require(
        type(start) is int
        and type(end) is int
        and type(extent) is int
        and 0 < extent <= end - start + 1,
        "edited render extent is outside the approved interval",
    )
    assert type(start) is int and type(end) is int and type(extent) is int
    return start, start + extent - 1, extent < end - start + 1


def _verify_render_job_marks_if_reported(
    job: dict[str, Any], marks: tuple[int, int, bool]
) -> None:
    mark_in, mark_out, shortened = marks
    has_mark_in = "MarkIn" in job
    has_mark_out = "MarkOut" in job
    _require(
        has_mark_in == has_mark_out,
        "queued render job mark range is incomplete",
    )
    # A shortened programme's only output-length binding is the queued range.
    _require(
        has_mark_in or not shortened,
        "shortened render job does not report its mark range",
    )
    if not has_mark_in:
        return
    _require(
        type(job.get("MarkIn")) is int
        and type(job.get("MarkOut")) is int
        and job["MarkIn"] == mark_in
        and job["MarkOut"] == mark_out,
        "queued render job mark range differs from the edited render extent",
    )


def _queue_render(
    request: dict[str, Any],
    resolve: Any,
    admitted: dict[str, Any],
    state: dict[str, Any],
    reservation_sha: str | None,
) -> dict[str, Any]:
    retrying = request.get("sequence") == len(APPROVAL_ACTION_PLAN)
    observed_edit = request["context"].get("phase") == "edited"
    if retrying:
        pre_capture, _, _ = _previous_result(request, "retry_capture")
    elif observed_edit:
        pre_capture, _, _ = _previous_result(request, "capture_pre")
    else:
        _previous_result(request, "capture_pre")
        pre_capture = None
    _, project, _ = _project_timeline(resolve, request)
    if retrying:
        _, _, failure = _native_result_at(request["context"], 5)
        verified_render_failure(request["context"])
        _verify_retry_job_quiescent(project, failure)
        if type(pre_capture) is not dict:
            raise OutputConsistencyError("retry capture result is unavailable")
        _, _, original_capture = _native_result_at(request["context"], 2)
        binding_request = {
            **request,
            "payload": {
                "inputBindingPath": pre_capture["inputBindingPath"],
                "inputBindingSha256": pre_capture["inputBindingSha256"],
            },
        }
        binding, _, binding_sha, _ = _input_binding(binding_request)
        geometry = _capture_geometry(resolve, request, admitted, binding)
        _require(
            binding_sha == original_capture["inputBindingSha256"]
            and geometry == pre_capture["nativeGeometry"]
            and geometry == original_capture["nativeGeometry"],
            "retry geometry or input binding changed before render queueing",
        )
    elif observed_edit:
        assert type(pre_capture) is dict
        binding_request = {
            **request,
            "payload": {
                "inputBindingPath": pre_capture["inputBindingPath"],
                "inputBindingSha256": pre_capture["inputBindingSha256"],
            },
        }
        binding, _, binding_sha, _ = _input_binding(binding_request)
        geometry = _capture_observed_geometry(resolve, request, admitted, binding)
        _require(
            binding_sha == pre_capture["inputBindingSha256"]
            and geometry == pre_capture["nativeGeometry"],
            "edited geometry or UID binding changed before render queueing",
        )
    settings = request["payload"]["settings"]
    _require(
        settings
        == _expected_settings(
            _path(request["package"]["packageRoot"], "package root"), request["profile"]
        ),
        "render settings differ from admitted package",
    )
    marks = (
        _edited_render_marks(settings, pre_capture["nativeGeometry"])
        if observed_edit and type(pre_capture) is dict
        else None
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
    if retrying:
        _require(
            _path(render["outputPath"], "retry MOV output")
            == _retry_output_path(request["context"]),
            "retry output must use the one-use retry filename",
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
    codec_label = "Apple ProRes 422"
    codec_token = "ProRes422"
    _require(
        type(codecs) is dict and codecs.get(codec_label) == codec_token,
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
        {"format": "mov", "codec": codec_token},
    )
    selected = project.SetCurrentRenderFormatAndCodec("mov", codec_token)
    _require(selected is True, "Resolve refused MOV/ProRes 422 selection")
    selected_format_codec = project.GetCurrentRenderFormatAndCodec()
    _require(
        selected_format_codec == {"format": "mov", "codec": codec_token},
        "MOV/ProRes 422 selection did not read back",
    )
    _effect_observed(
        state,
        row,
        {"return": selected, "formatCodec": selected_format_codec},
    )
    row = _private_effect(state, "Project.SetCurrentRenderMode", {"mode": 1})
    mode = project.SetCurrentRenderMode(1)
    mode_readback = project.GetCurrentRenderMode()
    _require(
        mode is True and mode_readback == 1,
        "single-job render mode did not read back",
    )
    _effect_observed(state, row, {"return": mode, "renderMode": mode_readback})
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
        "SelectAllFrames": not observed_edit,
        "UseUniqueFilenames": False,
        "TargetDir": str(output_path.parent),
        "CustomName": output_path.stem,
    }
    if marks is not None:
        render_settings["MarkIn"], render_settings["MarkOut"] = marks[:2]
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
        job.get("RenderMode") == "Single clip",
        "queued render job is not a single clip",
    )
    _require(
        job.get("IsExportVideo") is True
        and job.get("IsExportAudio") is True
        and job.get("AudioBitDepth") == 24
        and job.get("AudioSampleRate") == 48000
        and job.get("FormatWidth") == timeline_info["width"]
        and job.get("FormatHeight") == timeline_info["height"],
        "queued render job settings differ",
    )
    _require(
        job.get("VideoCodec") in {codec_label, codec_token}
        and job.get("AudioCodec") in {"Linear PCM", "lpcm"}
        and job.get("VideoFormat") in {"QuickTime", "mov"},
        "queued render job codec/container differ",
    )
    if marks is not None:
        _verify_render_job_marks_if_reported(job, marks)
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
    if request["context"].get("phase") == "edited":
        # Marks bind the extent this edited attempt authenticated at capture_pre.
        _, _, capture = _native_result_at(request["context"], 2)
        _require(capture["action"] == "capture_pre", "edited pre-capture required")
        marks = _edited_render_marks(previous["settings"], capture["nativeGeometry"])
        _verify_render_job_marks_if_reported(rows[0], marks)
    get_status = getattr(project, "GetRenderJobStatus", None)
    if not callable(get_status):
        raise OutputConsistencyError("render job status unavailable before start")
    try:
        status = get_status(previous["jobId"])
    except Exception:
        raise OutputConsistencyError(
            "render job status unreadable before start"
        ) from None
    _require(
        type(status) is dict and type(status.get("JobStatus")) is str,
        "render job status unreadable before start",
    )
    _require(
        status["JobStatus"] == "Ready",
        "queued render job is not locally ready",
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
        terminal_failure = status.get("JobStatus") in {"Failed", "Cancelled"}
        output_path = _path(previous["outputPath"], "failed MOV")
        source_hash = (
            _hash_file(output_path)[0]
            if terminal_failure and output_path.exists()
            else None
        )
        return {
            "status": "partial",
            "reason": (
                "render job reached a terminal failure"
                if terminal_failure
                else "render job did not reach Complete within the bounded poll window"
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
            "sourceOutputRawSha256": source_hash,
            "renderStatus": status,
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
    captured = _capture(request, resolve, admitted, phase="post_render")
    if request["context"].get("phase") == "edited":
        _, _, pre_capture = _native_result_at(request["context"], 2)
        _require(
            captured["nativeGeometry"] == pre_capture["nativeGeometry"]
            and captured["inputBindingSha256"] == pre_capture["inputBindingSha256"],
            "post-render observed geometry or UID binding changed",
        )
    return captured


def _verify_retry_job_quiescent(project: Any, failure: dict[str, Any]) -> None:
    is_rendering = getattr(project, "IsRenderingInProgress", None)
    if not callable(is_rendering):
        raise OutputConsistencyError("Resolve render state unavailable for retry")
    try:
        rendering = is_rendering()
    except Exception:
        raise OutputConsistencyError(
            "Resolve render state is unreadable for retry"
        ) from None
    _require(rendering is False, "Resolve is still rendering")
    jobs = project.GetRenderJobList()
    _require(type(jobs) in {list, tuple}, "render job list unavailable for retry")
    get_status = getattr(project, "GetRenderJobStatus", None)
    if not callable(get_status):
        raise OutputConsistencyError("render job status unavailable for retry")
    statuses: dict[str, str] = {}
    for job in jobs:
        _require(type(job) is dict, "render job list is unreadable for retry")
        job_id = job.get("JobId")
        _require(type(job_id) is str and bool(job_id), "render job ID unreadable")
        _require(job_id not in statuses, "duplicate render job in retry queue")
        status = get_status(job_id)
        _require(
            type(status) is dict and type(status.get("JobStatus")) is str,
            "render job status unreadable for retry",
        )
        statuses[job_id] = status["JobStatus"]
    failed_job_id = failure["jobId"]
    _require(
        statuses.get(failed_job_id) in {"Failed", "Cancelled"},
        "original render job is no longer failed or cancelled",
    )
    _require(
        all(
            status in {"Complete", "Failed", "Cancelled"}
            for status in statuses.values()
        ),
        "Resolve has a render job that is not terminal",
    )


def _retry_output_path(context: dict[str, Any]) -> Path:
    _, _, queue = _native_result_at(context, 3)
    _require(
        queue["action"] == "queue_render"
        and queue["status"] == "complete"
        and queue["sequence"] == 3,
        "original native render queue result is unavailable",
    )
    original = _path(queue["outputPath"], "original render output")
    return original.with_name(f"{original.stem}-retry-1.mov")


def _retry_capture(
    request: dict[str, Any], resolve: Any, admitted: dict[str, Any]
) -> dict[str, Any]:
    failure, _, _ = _previous_result(request, "poll_render")
    verified_render_failure(request["context"])
    failed_output = _path(failure["outputPath"], "failed MOV output")
    if failure["sourceOutputRawSha256"] is None:
        _require(
            not failed_output.exists(), "failed render output appeared before retry"
        )
    else:
        _require(
            failed_output.is_file() and not failed_output.is_symlink(),
            "failed render output disappeared before retry",
        )
        failed_output_sha, _ = _hash_file(failed_output)
        _require(
            failed_output_sha == failure["sourceOutputRawSha256"],
            "failed render output changed before retry",
        )
    _, _, original_capture = _native_result_at(request["context"], 2)
    _require(
        original_capture["action"] == "capture_pre"
        and original_capture["status"] == "complete",
        "original pre-render geometry is unavailable",
    )
    _, _binding_raw, binding_sha, _binding_path = _input_binding(request)
    _require(
        binding_sha == original_capture["inputBindingSha256"],
        "retry input binding differs from the original capture",
    )
    _, project, _ = _project_timeline(resolve, request)
    _verify_retry_job_quiescent(project, failure)
    approval = _verify_authority(request, current=True)[2]
    _require(
        _path(approval["outputPath"], "retry MOV output")
        == _retry_output_path(request["context"]),
        "retry output must use the one-use retry filename",
    )
    captured = _capture(request, resolve, admitted, phase="pre_render")
    _require(
        captured["nativeGeometry"] == original_capture["nativeGeometry"]
        and captured["inputBindingSha256"] == original_capture["inputBindingSha256"],
        "saved target geometry or input binding changed since the original capture",
    )
    return captured


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
        if row["method"] == "Timeline.SetClipsLinked":
            _require(
                result["action"] == "construct"
                and result["profile"] in CONSTRUCTOR_LINK_PROFILES,
                "qualification AV link effect is outside its fixed constructor scope",
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
    # Only completed checks are shared; every later operation starts fresh.
    with _verification_scope() as traversal:
        key = (_path(str(result_path), "native result"), _digest(expected_sha256))
        if key not in traversal.results:
            traversal.results[key] = _verify_native_result(*key)
        return traversal.results[key]


def _verify_native_result(result_path: Path, expected_sha256: str) -> dict[str, Any]:
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
        result["profile"] in PROFILES and result["action"] in ACTIONS,
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
        and 0
        <= result["sequence"]
        < len(action_plan_for_context(context))
        + (0 if context["phase"] == "edited" else len(RETRY_ACTION_PLAN) - 1),
        "native result sequence out of range",
    )
    _require(
        result["action"] == native_action(context, result["sequence"]),
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
            prior["status"] == "complete"
            or (result["action"] == "retry_capture" and _terminal_failed_render(prior)),
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
            queue_path = native_request_paths(context, result["sequence"] - 2)[0]
            queue_raw = _read(queue_path, "native queue result")
            queue_sha = _hash(queue_raw)
            queue = verify_native_result(queue_path, queue_sha)
            _require(
                prior["action"] == "start_render"
                and result["startedResultSha256"] == result["priorResultSha256"]
                and result["queuedResultSha256"] == prior["queuedResultSha256"]
                and result["queuedResultSha256"] == queue_sha
                and queue["action"] == "queue_render"
                and queue["status"] == "complete"
                and all(
                    queue[field] == prior[field] == result[field]
                    for field in (
                        "jobId",
                        "outputPath",
                        "settings",
                        "commitmentRawSha256",
                        "reservationSha256",
                        "renderIntentSha256",
                    )
                ),
                "poll result is not bound to its exact queued/started predecessors",
            )
        elif result["action"] == "capture_post":
            _require(
                prior["action"] == "poll_render"
                and result["completionResultSha256"] == result["priorResultSha256"],
                "post-render capture is not bound to its exact completion predecessor",
            )
        elif result["action"] == "retry_capture":
            failure_path, failure_sha, _ = verified_render_failure(context)
            _require(
                failure_path == prior_path
                and failure_sha == result["priorResultSha256"],
                "retry capture is not bound to the authenticated original failure",
            )
            original_capture_path = native_request_paths(context, 2)[0]
            original_capture_raw = _read(
                original_capture_path, "original pre-render geometry"
            )
            original_capture = verify_native_result(
                original_capture_path, _hash(original_capture_raw)
            )
            _verify_retry_capture_geometry(result, original_capture)
        elif result["action"] == "queue_render" and result["sequence"] == len(
            APPROVAL_ACTION_PLAN
        ):
            _require(
                prior["action"] == "retry_capture" and prior["status"] == "complete",
                "retry queue is not bound to the completed retry capture",
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
            and type(result["renderStatus"]) is dict
            and result["renderStatus"].get("JobStatus") == "Complete"
            and result["sourceOutputRawSha256"] is not None
            and result["queuedResultSha256"] is not None
            and result["startedResultSha256"] is not None,
            "complete render lacks verified output/time/stage lineage",
        )
    if result["action"] == "poll_render" and result["status"] == "partial":
        _require(
            type(result["renderStatus"]) is dict
            and type(result["renderStatus"].get("JobStatus")) is str,
            "partial render result must retain its observed job status",
        )
        if _terminal_failed_render(result):
            if result["sourceOutputRawSha256"] is None:
                _require(
                    not _path(result["outputPath"], "failed MOV output").exists(),
                    "existing failed render output requires a retained digest",
                )
            else:
                output_sha, _ = _hash_file(
                    _path(result["outputPath"], "failed MOV output")
                )
                _require(
                    output_sha == result["sourceOutputRawSha256"],
                    "failed render output changed after the terminal poll",
                )
    return result


def _native_result_at(
    context: dict[str, Any], sequence: int
) -> tuple[Path, str, dict[str, Any]]:
    path = native_request_paths(context, sequence)[0]
    raw = _read(path, "native history result")
    digest = _hash(raw)
    return path, digest, verify_native_result(path, digest)


def verified_render_failure(
    context: dict[str, Any],
) -> tuple[Path, str, dict[str, Any]]:
    """Authenticate the one original terminal failure and its queue/start lineage."""
    with _verification_scope():
        return _verified_render_failure(context)


def _verified_render_failure(
    context: dict[str, Any],
) -> tuple[Path, str, dict[str, Any]]:
    path, digest, result = _native_result_at(context, len(APPROVAL_ACTION_PLAN) - 2)
    _require(
        result["sequence"] == len(APPROVAL_ACTION_PLAN) - 2
        and _terminal_failed_render(result),
        "native history has no authenticated terminal render failure",
    )
    queue_path, queue_sha, queue = _native_result_at(context, 3)
    start_path, start_sha, start = _native_result_at(context, 4)
    _require(
        queue["action"] == "queue_render"
        and queue["status"] == "complete"
        and start["action"] == "start_render"
        and start["status"] == "complete"
        and result["queuedResultSha256"] == queue_sha
        and result["startedResultSha256"] == start_sha
        and start["queuedResultSha256"] == queue_sha
        and all(
            queue[field] == start[field] == result[field]
            for field in (
                "jobId",
                "outputPath",
                "settings",
                "commitmentRawSha256",
                "reservationSha256",
                "renderIntentSha256",
            )
        ),
        "terminal failure is not bound to the original queue/start lineage",
    )
    del queue_path, start_path
    return path, digest, result


def _routing_result_at(context: dict[str, Any], sequence: int) -> dict[str, Any]:
    """Read a closed retained result for action routing without recursive verification.

    This view is only a selector. Operations that can authorize work authenticate the
    complete predecessor chain through ``_native_operation_tail`` or
    ``verify_native_result`` before continuing.
    """
    path = native_request_paths(context, sequence)[0]
    raw = _read(path, "native routing result")
    _immutable(path, "native routing result")
    result = _shape(_parse(raw), RESULT_FIELDS, "native routing result")
    _require(
        raw == _canonical(result)
        and result["context"] == context
        and result["sequence"] == sequence,
        "native routing result identity differs",
    )
    return result


def native_action(context: dict[str, Any], sequence: int) -> str:
    """Resolve the fixed action at a sequence, including the one retry branch."""
    _require(type(sequence) is int and sequence >= 0, "invalid native sequence")
    plan = action_plan_for_context(context)
    if context.get("phase") == "edited":
        _require(sequence < len(plan), "native action plan is exhausted")
        return plan[sequence]
    if sequence < len(plan) - 1:
        return plan[sequence]
    _require(
        sequence < len(plan) + len(RETRY_ACTION_PLAN) - 1,
        "native action plan is exhausted",
    )
    if sequence == len(plan) - 1:
        poll = _routing_result_at(context, sequence - 1)
        _require(
            poll["action"] == "poll_render" and poll["sequence"] == sequence - 1,
            "original render poll is unavailable",
        )
        if poll["status"] == "complete":
            _require(
                type(poll["renderStatus"]) is dict
                and poll["renderStatus"].get("JobStatus") == "Complete",
                "complete original poll lacks a completed Resolve status",
            )
            return "capture_post"
        _require(
            _terminal_failed_render(poll),
            "only a terminal Failed/Cancelled poll enables retry",
        )
        return "retry_capture"
    poll = _routing_result_at(context, len(plan) - 2)
    _require(
        poll["action"] == "poll_render" and _terminal_failed_render(poll),
        "retry action requires a terminal failed original poll",
    )
    retry_sequence = len(plan) - 1
    retry_capture = _routing_result_at(context, retry_sequence)
    _require(
        retry_capture["action"] == "retry_capture"
        and retry_capture["sequence"] == retry_sequence
        and retry_capture["status"] == "complete",
        "retry action requires one complete retry capture",
    )
    return RETRY_ACTION_PLAN[sequence - (len(plan) - 1)]


def _native_operation_tail(
    context: dict[str, Any],
    *,
    prepared_sequence: int | None = None,
    allow_retry: bool = False,
) -> tuple[int, str]:
    with _verification_scope():
        return _verify_native_operation_tail(
            context, prepared_sequence=prepared_sequence, allow_retry=allow_retry
        )


def _verify_native_operation_tail(
    context: dict[str, Any],
    *,
    prepared_sequence: int | None = None,
    allow_retry: bool = False,
) -> tuple[int, str]:
    checked = _context(context)
    plan = action_plan_for_context(checked)
    max_operations = len(plan) + (
        0 if checked.get("phase") == "edited" else len(RETRY_ACTION_PLAN) - 1
    )
    first = native_request_paths(checked, 0)[0]
    root = first.parent.parent
    if not root.exists():
        _require(prepared_sequence is None, "prepared native operation is absent")
        return 0, EMPTY_HEAD
    directories = sorted(root.iterdir())
    _require(
        len(directories) <= max_operations,
        "native operation history exceeds the reviewed plans",
    )
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
            if (
                sequence == len(plan) - 1
                and native_action(checked, sequence) == "retry_capture"
            ):
                _require(
                    allow_retry,
                    "failed render requires the explicit retry entrypoint",
                )
            return sequence, prior
        _require(
            result_path.is_file(),
            "native operation has an immutable intent without a terminal result; "
            "read-only recovery required",
        )
        raw = _read(result_path, "native operation result")
        result = verify_native_result(result_path, _hash(raw))
        _require(result["sequence"] == sequence, "native operation sequence differs")
        if result["status"] != "complete":
            _require(
                sequence == len(plan) - 2
                and _terminal_failed_render(result)
                and (allow_retry or sequence + 1 < len(directories)),
                "native operation history is partial/uncertain and cannot be replayed",
            )
            verified_render_failure(checked)
            if sequence + 1 == len(directories):
                return sequence + 1, _hash(raw)
        prior = _hash(raw)
    _require(
        prepared_sequence is None,
        "prepared native operation is absent from the native history tail",
    )
    _require(
        len(directories) < max_operations,
        "reviewed native action plan is exhausted",
    )
    next_sequence = len(directories)
    if next_sequence == len(plan) and checked["phase"] != "edited":
        _, _, last = _native_result_at(checked, next_sequence - 1)
        _require(
            last["action"] == "retry_capture" and last["status"] == "complete",
            "reviewed native action plan is exhausted",
        )
    return len(directories), prior


def next_native_operation(
    context: dict[str, Any], *, retry: bool = False
) -> tuple[int, str]:
    """Return the next one-use stage only after authenticating the full chain."""
    next_operation = _native_operation_tail(context, allow_retry=retry)
    if retry:
        _require(
            context.get("phase") != "edited"
            and next_operation[0] == len(APPROVAL_ACTION_PLAN) - 1
            and native_action(context, next_operation[0]) == "retry_capture",
            "explicit retry entrypoint requires the authenticated failed poll",
        )
    return next_operation


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
        type(sequence) is int
        and 0
        <= sequence
        < len(action_plan_for_context(request["context"]))
        + (
            0
            if request["context"].get("phase") == "edited"
            else len(RETRY_ACTION_PLAN) - 1
        ),
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
        request["action"] == native_action(context, sequence)
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
    tail, prior = _native_operation_tail(
        context,
        prepared_sequence=sequence,
        allow_retry=request["action"] == "retry_capture",
    )
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
            prior["status"] == "complete"
            or (action == "retry_capture" and _terminal_failed_render(prior)),
            "native runtime predecessor is incomplete",
        )
        _verify_native_identity_continuity(prior["nativeIdentity"], current_identity)
    if action == "observe_edited":
        geometry = _capture_observed_geometry(resolve, request, admitted, None)
        return {"nativeGeometry": geometry, "nativeIdentity": current_identity}
    if action == "construct":
        return _construct(resolve, request, admitted, state)
    if action == "save_reopen":
        return _save_reopen(resolve, request, admitted, state)
    if action == "capture_pre":
        previous, _, _ = _previous_result(request, "save_reopen")
        captured = _capture(request, resolve, admitted, phase="pre_render")
        if request["context"].get("phase") == "edited":
            _require(
                _unbound_geometry_projection(captured["nativeGeometry"])
                == previous["nativeGeometry"],
                "edited input binding differs from the saved/reopened readback",
            )
        return captured
    if action == "retry_capture":
        return _retry_capture(request, resolve, admitted)
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
        if request["action"] in {"capture_pre", "retry_capture", "capture_post"}:
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
