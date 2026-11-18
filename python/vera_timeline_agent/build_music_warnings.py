"""Publish the music-warning projection of a completed local build report."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler

MUSIC_CODES = frozenset(
    {
        "MUSIC_FILE_MISSING",
        "MUSIC_SOURCE_SHORTER",
        "MUSIC_SPAN_INVALID",
        "MUSIC_SETTINGS_UNSUPPORTED",
    }
)
UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
TOKEN = re.compile(r"^[0-9a-f]{64}$")


def _record(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, dict) else None


def report_music_warnings(report_path: Path) -> dict[str, Any]:
    """Read and bound the report fields the authoring service is allowed to retain."""
    if report_path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("build report is too large")
    report = _record(json.loads(report_path.read_text(encoding="utf-8")))
    document = _record(report.get("document")) if report else None
    diagnostics = report.get("diagnostics") if report else None
    if (
        not report
        or report.get("schemaVersion") != "build-report/v2"
        or report.get("status") != "ready"
        or not document
        or not isinstance(diagnostics, list)
    ):
        raise ValueError("build report is not a completed v2 report")

    project_id = document.get("projectId")
    document_id = document.get("documentId")
    build_id = report.get("buildId")
    revision = document.get("revision")
    if (
        not isinstance(project_id, str)
        or not UUID.fullmatch(project_id)
        or not isinstance(document_id, str)
        or not UUID.fullmatch(document_id)
        or not isinstance(build_id, str)
        or not UUID.fullmatch(build_id)
        or not isinstance(revision, int)
        or isinstance(revision, bool)
        or revision < 0
        or revision > 9_007_199_254_740_991
    ):
        raise ValueError("build report has invalid project or build identity")

    warnings: list[dict[str, str]] = []
    for diagnostic_value in diagnostics:
        diagnostic = _record(diagnostic_value)
        if not diagnostic or diagnostic.get("code") not in MUSIC_CODES:
            continue
        message = diagnostic.get("message")
        if not isinstance(message, str) or not message or len(message) > 1000:
            raise ValueError("build report has an invalid music warning")
        if any(ord(char) < 32 or ord(char) == 127 for char in message):
            raise ValueError("build report has an invalid music warning")
        warnings.append({"code": diagnostic["code"], "message": message})
        if len(warnings) > 32:
            raise ValueError("build report has too many music warnings")

    return {
        "projectId": project_id.lower(),
        "documentId": document_id.lower(),
        "documentRevision": revision,
        "buildId": build_id.lower(),
        "musicWarnings": warnings,
    }


def _send(request: Request, timeout: float) -> int:
    # The token must never reach an environment-configured proxy.
    opener = build_opener(ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        return response.status


def publish_latest_music_warnings(
    report_path: Path,
    env: Mapping[str, str] | None = None,
    send: Any = _send,
) -> tuple[bool, str]:
    """Publish through the already-authenticated local service."""
    environment = os.environ if env is None else env
    token = environment.get("VERA_STT_QA_AUTHORING_TOKEN", "")
    if not TOKEN.fullmatch(token):
        return (
            False,
            "VERA_STT_QA_AUTHORING_TOKEN is not set to the "
            "local authoring token",
        )
    port_text = environment.get("VERA_STT_QA_PORT", "38429")
    if not re.fullmatch(r"\d{4,5}", port_text) or not 1024 <= int(port_text) <= 65535:
        return False, "VERA_STT_QA_PORT is invalid"
    try:
        payload = report_music_warnings(report_path)
        request = Request(
            f"http://127.0.0.1:{port_text}/v1/projects/{payload['projectId']}/music-warnings",
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        if send(request, 10) != 201:
            return (
                False,
                "the local service did not accept the warning report",
            )
    except (OSError, ValueError, UnicodeError, HTTPError, URLError, TimeoutError):
        return False, "the local service could not receive the warning report"
    return True, ""
