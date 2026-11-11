"""Closed, non-authoritative Test Bench diagnostic records (contract only).

This module has no native/Resolve imports, file writes, or retry capabilities.
Phase 2 will publish validated records as separate immutable files.  A record
is evidence ABOUT a verifier/operation, never a receipt FROM that verifier.
"""

from __future__ import annotations

import json
import os
import re
import time
import traceback
from datetime import UTC, datetime
from typing import Any

SCHEMA = "vera.test-bench-diagnostic/v1"
MAX_RECORD_BYTES = 8192
MAX_MESSAGE_CHARS = 512
MAX_FRAMES = 16
MAX_EVIDENCE_REFS = 12

EVENTS = frozenset(
    {
        "claim",
        "admission",
        "preparation",
        "native_dispatch",
        "carrier_result",
        "verification",
        "ingestion",
        "render_queue",
        "render_start",
        "render_poll",
        "render_capture",
        "mov_pcm",
        "inference",
        "m4_receipt",
        "strict_312",
        "handoff",
        "origin_thread_ack",
        "exception",
    }
)
PHASES = frozenset({"launch", "pristine", "edited", "revision", "rebuild", "handoff"})
PROOF_LAYERS = frozenset(
    {
        "none",
        "process_exit",
        "os_effect",
        "authenticated_native_result",
        "signed_m4_receipt",
        "origin_thread_ack",
    }
)
STATUSES = frozenset({"observed", "pending", "unknown", "refused"})
BOUNDARIES = frozenset(
    {
        "before_claim",
        "after_claim",
        "before_admission",
        "after_admission",
        "before_preparation",
        "after_preparation",
        "before_dispatch",
        "after_dispatch",
        "after_carrier",
        "before_ingest",
        "after_ingest",
        "before_finalize",
        "after_finalize",
        "before_receipt",
        "after_receipt",
        "before_handoff",
        "after_handoff",
        "before_thread_ack",
        "after_thread_ack",
    }
)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[a-zA-Z0-9_-]{1,100}\Z")
_NAME = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]{0,79}\Z")
_FILE = re.compile(
    r"(?:resolve_test_bench_[a-z0-9_]+|qualification_output_[a-z0-9_]+)\.py\Z"
)
_URL = re.compile(r"(?i)\b(?:https?|ftp)://[^\s<>\"']+")
_SECRET = re.compile(
    r"(?i)\b(?:authorization|password|passwd|token|secret|api[_-]?key|"
    r"cookie|session[_-]?id|client[_-]?secret)\b\s*[:=]\s*"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_EMAIL = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
_WINDOWS_PATH = re.compile(r"(?i)\b[a-z]:\\[^\s,;\"']+")
_ABSOLUTE_PATH = re.compile(r"(?<![a-zA-Z0-9])/(?:[^\s,;\"'<>])+", re.ASCII)
_LONG_TOKEN = re.compile(r"\b[A-Za-z0-9_+/=-]{32,}\b")
_CONTROLS = re.compile(r"[\x00-\x1f\x7f]")


class DiagnosticContractError(ValueError):
    """A proposed diagnostic could leak data or misstate its evidence tier."""


def redact(value: object) -> str:
    """Best-effort bounded display text, never a raw exception dump.

    Producers must supply only class/message, not environment, locals, or
    credentials.  Sensitive file paths are never exposed in frame records.
    """
    try:
        message = str(value)
    except BaseException:
        message = "[unprintable exception]"
    message = _CONTROLS.sub(" ", message)
    for pattern, replacement in (
        (_URL, "[url-redacted]"),
        (_BEARER, "[secret-redacted]"),
        (_SECRET, "[secret-redacted]"),
        (_EMAIL, "[email-redacted]"),
        (_WINDOWS_PATH, "[path-redacted]"),
        (_ABSOLUTE_PATH, "[path-redacted]"),
        (_LONG_TOKEN, "[token-redacted]"),
    ):
        message = pattern.sub(replacement, message)
    if len(message) > MAX_MESSAGE_CHARS:
        message = message[: MAX_MESSAGE_CHARS - len(" [truncated]")] + " [truncated]"
    return message


def exception_details(error: BaseException) -> dict[str, Any]:
    """Bounded exception metadata; no absolute paths, source, or frame locals."""
    name = type(error).__name__
    if not _NAME.fullmatch(name):
        name = "RedactedException"
    frames = []
    for frame in traceback.extract_tb(error.__traceback__)[-MAX_FRAMES:]:
        filename = frame.filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        function = frame.name if _NAME.fullmatch(frame.name) else "redacted"
        line = frame.lineno if isinstance(frame.lineno, int) else 0
        frames.append(
            {
                "file": filename if _FILE.fullmatch(filename) else "redacted.py",
                "function": function,
                "line": max(0, min(line, 2**31 - 1)),
            }
        )
    return {"className": name, "message": redact(error), "frames": frames}


def timestamp() -> dict[str, Any]:
    """Time evidence only: wall-clock ordering must not override monotonic time."""
    return {
        "utc": datetime.now(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
        "monotonicNs": time.monotonic_ns(),
        "pid": os.getpid(),
    }


def _require(ok: bool, why: str) -> None:
    if not ok:
        raise DiagnosticContractError("Test Bench diagnostic refused: " + why)


def _digest(value: object, *, optional: bool = False) -> None:
    _require(
        (optional and value is None)
        or (type(value) is str and _SHA.fullmatch(value) is not None),
        "SHA-256 pin invalid",
    )


def _id(value: object, *, optional: bool = False) -> None:
    _require(
        (optional and value is None)
        or (type(value) is str and _ID.fullmatch(value) is not None),
        "unsafe or missing identity",
    )


def _native_step(value: object, *, result: bool) -> None:
    if value is None:
        return
    expected = (
        {"nativeSequence", "action", "resultSha256"}
        if result
        else {
            "nativeSequence",
            "action",
        }
    )
    _require(type(value) is dict and set(value) == expected, "native step fields")
    assert isinstance(value, dict)
    _require(
        type(value["nativeSequence"]) is int and 0 <= value["nativeSequence"] <= 1000,
        "native step sequence",
    )
    _id(value["action"])
    if result:
        _digest(value["resultSha256"])


def validate_record(value: object) -> dict[str, Any]:
    """Strict closed v1 contract; never interprets records as authorizations."""
    expected = {
        "schema",
        "recordIndex",
        "previousRecordSha256",
        "kind",
        "event",
        "boundary",
        "status",
        "proofLayer",
        "proofSha256",
        "clock",
        "identity",
        "pins",
        "lastVerified",
        "nextPending",
        "evidence",
        "exception",
    }
    _require(type(value) is dict and set(value) == expected, "closed v1 fields")
    assert isinstance(value, dict)
    _require(value["schema"] == SCHEMA, "schema version")
    index = value["recordIndex"]
    _require(type(index) is int and 0 <= index <= 999999, "record index")
    _digest(value["previousRecordSha256"], optional=index == 0)
    _require((index == 0) == (value["previousRecordSha256"] is None), "chain anchor")
    _require(
        type(value["kind"]) is str and value["kind"] in ("stage", "exception"),
        "record kind",
    )
    _require(
        type(value["event"]) is str
        and value["event"] in EVENTS
        and type(value["boundary"]) is str
        and value["boundary"] in BOUNDARIES
        and type(value["status"]) is str
        and value["status"] in STATUSES,
        "event/status",
    )
    _require(
        type(value["proofLayer"]) is str and value["proofLayer"] in PROOF_LAYERS,
        "proof layer",
    )
    _digest(value["proofSha256"], optional=value["proofLayer"] == "none")
    _require(
        (value["proofLayer"] == "none") == (value["proofSha256"] is None),
        "proof pin must match proof tier",
    )
    if value["proofLayer"] == "signed_m4_receipt":
        _require(
            value["event"] == "m4_receipt" and value["status"] == "observed",
            "signed M4 proof event",
        )
    if value["proofLayer"] == "origin_thread_ack":
        _require(
            value["event"] == "origin_thread_ack" and value["status"] == "observed",
            "thread ACK proof event",
        )
    clock = value["clock"]
    _require(
        type(clock) is dict and set(clock) == {"utc", "monotonicNs", "pid"},
        "closed clock",
    )
    _require(
        type(clock["utc"]) is str
        and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z", clock["utc"])
        is not None,
        "UTC timestamp",
    )
    try:
        datetime.fromisoformat(clock["utc"].replace("Z", "+00:00"))
    except ValueError as error:
        raise DiagnosticContractError("invalid UTC timestamp") from error
    _require(
        type(clock["monotonicNs"]) is int
        and clock["monotonicNs"] >= 0
        and type(clock["pid"]) is int
        and clock["pid"] > 0,
        "clock/PID values",
    )
    identity = value["identity"]
    _require(
        type(identity) is dict
        and set(identity)
        == {
            "caseId",
            "jobId",
            "operationId",
            "phase",
            "stage",
            "action",
            "nativeSequence",
        },
        "closed identity",
    )
    for field in ("caseId", "jobId", "operationId", "stage", "action"):
        _id(identity[field], optional=field != "caseId")
    _require(
        type(identity["phase"]) is str and identity["phase"] in PHASES, "phase identity"
    )
    native = identity["nativeSequence"]
    _require(
        native is None or (type(native) is int and 0 <= native <= 1000), "sequence"
    )
    pins = value["pins"]
    _require(
        type(pins) is dict
        and set(pins)
        == {"frozenSourceSha256", "actorSha256", "targetSha256", "authorizationSha256"},
        "closed hashes",
    )
    for digest in pins.values():
        _digest(digest, optional=True)
    _native_step(value["lastVerified"], result=True)
    _native_step(value["nextPending"], result=False)
    evidence = value["evidence"]
    _require(
        type(evidence) is list and len(evidence) <= MAX_EVIDENCE_REFS, "evidence quota"
    )
    for ref in evidence:
        _require(
            type(ref) is dict
            and set(ref) == {"role", "sha256", "sizeBytes", "locatorSha256"},
            "closed evidence reference",
        )
        _id(ref["role"])
        _digest(ref["sha256"])
        _digest(ref["locatorSha256"], optional=True)
        _require(
            type(ref["sizeBytes"]) is int and 0 <= ref["sizeBytes"] < 2**63, "size"
        )
    details = value["exception"]
    if value["kind"] == "exception":
        _require(
            value["event"] == "exception"
            and value["status"] == "unknown"
            and value["proofLayer"] == "none"
            and type(details) is dict
            and set(details) == {"className", "message", "frames"},
            "exception never certifies a native outcome",
        )
        _require(
            type(details["className"]) is str
            and _NAME.fullmatch(details["className"]) is not None,
            "exception class",
        )
        _require(
            type(details["message"]) is str
            and len(details["message"]) <= MAX_MESSAGE_CHARS
            and details["message"] == redact(details["message"]),
            "unredacted exception text",
        )
        frames = details["frames"]
        _require(type(frames) is list and len(frames) <= MAX_FRAMES, "frame quota")
        for frame in frames:
            _require(
                type(frame) is dict
                and set(frame) == {"file", "function", "line"}
                and type(frame["file"]) is str
                and (
                    frame["file"] == "redacted.py"
                    or _FILE.fullmatch(frame["file"]) is not None
                )
                and type(frame["function"]) is str
                and _NAME.fullmatch(frame["function"]) is not None
                and type(frame["line"]) is int
                and 0 <= frame["line"] <= 2**31 - 1,
                "unsafe traceback frame",
            )
    else:
        _require(
            value["event"] != "exception" and details is None,
            "stage cannot carry exception",
        )
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()
    _require(len(raw) + 1 <= MAX_RECORD_BYTES, "record byte quota")
    return value


def canonical_bytes(value: object) -> bytes:
    """Canonical validated payload, for a future O_EXCL/fsync-only publisher."""
    return (
        json.dumps(
            validate_record(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode()
