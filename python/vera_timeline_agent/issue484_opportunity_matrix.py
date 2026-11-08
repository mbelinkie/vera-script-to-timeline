"""Offline, read-only validation of #484 proposed Resolve API opportunities.

This module never imports or connects to the Resolve SDK. A validated proposal
is not a native test authorization, runtime capability or execution manifest.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path, PurePosixPath
from typing import Any

MAX_MATRIX_BYTES = 1_000_000
RANKS = {
    "high-impact-near-term",
    "worth-testing",
    "defer",
    "unsupported",
}
VERSIONS = {"21.1.2", "21.2"}


class MatrixError(ValueError):
    """Malformed, ungrounded or overclaimed documentation-only matrix."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise MatrixError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MatrixError(f"{label} must be nonempty text")
    return value


def _texts(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise MatrixError(f"{label} must be a nonempty list")
    result = [_text(item, label) for item in value]
    if len(result) != len(set(result)):
        raise MatrixError(f"{label} has repeated entries")
    return result


def validate_matrix(data: Any, *, repo_root: Path) -> dict[str, Any]:
    """Verify static evidence and code links; never promote native execution.

    Paths are repository-relative and checked for existence only; no import of
    any source or platform-specific Resolve package occurs.
    """

    if not isinstance(data, dict):
        raise MatrixError("matrix must be a JSON object")
    if data.get("schemaVersion") != "vera-resolve-opportunity-input/v1":
        raise MatrixError("unsupported matrix schemaVersion")
    if type(data.get("issue")) is not int or data["issue"] != 484:
        raise MatrixError("matrix must be for issue #484")
    policy = data.get("evidencePolicy")
    if not isinstance(policy, dict):
        raise MatrixError("missing evidence policy")
    if policy.get("noNativeExecution") is not True:
        raise MatrixError("noNativeExecution must remain true")
    if policy.get("noAutomaticInstallation") is not True:
        raise MatrixError("noAutomaticInstallation must remain true")
    if policy.get("noPermissionPromotion") is not True:
        raise MatrixError("noPermissionPromotion must remain true")

    sources = data.get("sourceLedger")
    if not isinstance(sources, dict) or not sources:
        raise MatrixError("missing source ledger")
    for key, value in sources.items():
        _text(key, "source identifier")
        if not isinstance(value, dict):
            raise MatrixError(f"{key}: bad source record")
        _text(value.get("kind"), f"{key}.kind")
        _text(value.get("version"), f"{key}.version")
        _text(value.get("provenance"), f"{key}.provenance")
        if "url" in value and not str(value["url"]).startswith("https://"):
            raise MatrixError(f"{key}: source URL must be HTTPS")
        if value.get("kind") == "community-transcription-of-vendor-sdk":
            if value.get("sha256") is not None:
                raise MatrixError(f"{key}: unverified mirror cannot claim SDK SHA")
        elif value.get("kind") == "installed-vendor-sdk":
            digest = _text(value.get("sha256"), f"{key}.sha256")
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise MatrixError(f"{key}: invalid installed vendor SHA")

    rows = data.get("opportunities")
    if not isinstance(rows, list) or not rows:
        raise MatrixError("missing opportunity rows")
    seen: set[str] = set()
    root = repo_root.resolve(strict=True)
    for row in rows:
        if not isinstance(row, dict):
            raise MatrixError("opportunity row must be an object")
        key = _text(row.get("id"), "opportunity.id")
        if key in seen:
            raise MatrixError(f"duplicate opportunity id: {key}")
        seen.add(key)
        if row.get("rank") not in RANKS:
            raise MatrixError(f"{key}: unknown rank")
        if row.get("introduced") not in VERSIONS:
            raise MatrixError(f"{key}: wrong introduced version")
        for field in (
            "capability",
            "workaround",
            "replacement",
            "newBehavior",
            "risk",
            "testBench",
            "effort",
            "provenance",
            "releaseGate",
        ):
            _text(row.get(field), f"{key}.{field}")
        for field in (
            "declaredApis",
            "benefits",
            "prerequisites",
            "codeRefs",
            "sourceIds",
        ):
            _texts(row.get(field), f"{key}.{field}")
        if row.get("confidence") != "SDK declared":
            raise MatrixError(
                f"{key}: no native/fake-tested promotion in offline report"
            )
        for field, expectation in (
            ("newerVersionRequired", True),
            ("productQualified", False),
            ("realNativeProven", False),
        ):
            if row.get(field) is not expectation:
                raise MatrixError(f"{key}: {field} violates read-only evidence gate")
        if not any(
            sources[source_id]["version"] in (row["introduced"], "21.2")
            for source_id in row["sourceIds"]
            if source_id in sources
        ):
            raise MatrixError(f"{key}: no version-matched published source")
        for source_id in row["sourceIds"]:
            if source_id not in sources:
                raise MatrixError(f"{key}: missing source ledger entry {source_id}")
        for path_text in row["codeRefs"]:
            candidate = PurePosixPath(path_text)
            if (
                candidate.is_absolute()
                or not candidate.parts
                or any(part in ("..", ".") for part in candidate.parts)
                or path_text.startswith(".")
            ):
                raise MatrixError(f"{key}: unsafe VERA reference {path_text}")
            path = root.joinpath(*candidate.parts)
            if not path.is_file() or not path.resolve().is_relative_to(root):
                raise MatrixError(
                    f"{key}: nonexistent/escaping VERA reference {path_text}"
                )
        proof = row.get("nativeProbe")
        if not isinstance(proof, dict) or proof.get("status") != "NOT EXECUTED":
            raise MatrixError(f"{key}: future native probe must be NOT EXECUTED")
        if proof.get("mustNotOperateExistingTargets") is not True:
            raise MatrixError(f"{key}: existing targets not protected")
        for field in ("fixture", "procedure", "negativeControl", "saveReopen"):
            _text(proof.get(field), f"{key}.nativeProbe.{field}")
    return data


def read_matrix(path: Path, *, repo_root: Path) -> dict[str, Any]:
    """Read a regular bounded JSON file, reject duplicate keys, validate only."""

    if path.is_symlink():
        raise MatrixError("matrix file must not be a symlink")
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_MATRIX_BYTES:
        raise MatrixError("matrix must be a bounded regular file")
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise MatrixError("invalid UTF-8 JSON matrix") from error
    return validate_matrix(payload, repo_root=repo_root)
