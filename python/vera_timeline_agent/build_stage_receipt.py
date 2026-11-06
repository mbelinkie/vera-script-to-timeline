"""Closed canonical receipts for locally verified v2 build-stage effects.

The receipt is a binding, never an authority for an external effect.  Its
consumer must independently inspect every referenced artifact and any native
or provider effect before trusting the stage as complete.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .build_jobs import BuildJobError, StageContext

VERSION = "vera-build-stage-receipt/v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}\Z")
_VERSION_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")
_FIELDS = {
    "schemaVersion",
    "projectId",
    "jobId",
    "snapshotId",
    "snapshotSha256",
    "stage",
    "stageKey",
    "adapter",
    "inputs",
    "outputs",
    "packageAttestationSha256",
}


def require_hash(value: str, label: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise BuildJobError(f"{label} must be a lowercase SHA-256")
    return value


def hash_file(path: Path) -> str:
    """Hash a real regular file; never follow symbolic links in its ancestry."""
    if not path.is_absolute() or any(
        part.is_symlink() for part in (path, *path.parents)
    ):
        raise BuildJobError(f"untrusted or symlink artifact: {path}")
    if not path.is_file():
        raise BuildJobError(f"missing regular artifact: {path}")
    import stat

    if not stat.S_ISREG(path.stat(follow_symlinks=False).st_mode):
        raise BuildJobError(f"not a regular artifact: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _named_hashes(value: Mapping[str, str], label: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise BuildJobError(f"stage must bind {label} hashes")
    result: dict[str, str] = {}
    for key, digest in value.items():
        if not isinstance(key, str) or _NAME.fullmatch(key) is None:
            raise BuildJobError(f"invalid {label} hash label")
        result[key] = require_hash(digest, f"{label} {key}")
    return result


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def receipt_bytes(
    context: StageContext,
    *,
    snapshot_sha256: str,
    adapter_id: str,
    adapter_version: str,
    input_hashes: Mapping[str, str],
    output_hashes: Mapping[str, str],
    attestation_sha256: str | None = None,
) -> bytes:
    if context.job_kind != "build":
        raise BuildJobError("build receipt cannot attest an ingest job")
    if any(
        not isinstance(v, str) or not v or "\x00" in v or len(v) > 256
        for v in (
            context.project_id,
            context.job_id,
            context.snapshot_id,
            context.stage,
        )
    ):
        raise BuildJobError("invalid stage identity")
    require_hash(context.stage_key, "stage key")
    expected = hashlib.sha256(
        f"{context.project_id}\0{context.job_id}\0{context.stage}".encode()
    ).hexdigest()
    if context.stage_key != expected:
        raise BuildJobError("stage key does not match job and stage")
    require_hash(snapshot_sha256, "snapshot")
    if not isinstance(adapter_id, str) or _NAME.fullmatch(adapter_id) is None:
        raise BuildJobError("invalid adapter ID")
    if (
        not isinstance(adapter_version, str)
        or _VERSION_NAME.fullmatch(adapter_version) is None
        or ".." in adapter_version
    ):
        raise BuildJobError("invalid adapter version")
    if attestation_sha256 is not None:
        require_hash(attestation_sha256, "package attestation")
    return canonical_json(
        {
            "schemaVersion": VERSION,
            "projectId": context.project_id,
            "jobId": context.job_id,
            "snapshotId": context.snapshot_id,
            "snapshotSha256": snapshot_sha256,
            "stage": context.stage,
            "stageKey": context.stage_key,
            "adapter": {"id": adapter_id, "version": adapter_version},
            "inputs": _named_hashes(input_hashes, "input"),
            "outputs": _named_hashes(output_hashes, "output"),
            "packageAttestationSha256": attestation_sha256,
        }
    )


def read_receipt(raw: bytes) -> dict[str, Any]:
    """Reject noncanonical, duplicate-key and extension fields, even if valid JSON."""
    if not isinstance(raw, bytes) or len(raw) > 64 * 1024:
        raise BuildJobError("stage receipt is missing or oversized")

    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            if key in result:
                raise BuildJobError("duplicate stage receipt key")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
    except (UnicodeError, ValueError, TypeError) as error:
        raise BuildJobError("invalid stage receipt JSON") from error
    if (
        not isinstance(value, dict)
        or set(value) != _FIELDS
        or value.get("schemaVersion") != VERSION
    ):
        raise BuildJobError("invalid stage receipt schema")
    adapter = value.get("adapter")
    if not isinstance(adapter, dict) or set(adapter) != {"id", "version"}:
        raise BuildJobError("invalid stage receipt adapter")
    if raw != canonical_json(value):
        raise BuildJobError("stage receipt is not canonical")
    return value


def exact_receipt_matches(context: StageContext, raw: bytes, **expected: Any) -> bool:
    """Pure comparison; does NOT verify an external effect or file hash."""
    read_receipt(raw)
    return raw == receipt_bytes(context, **expected)
