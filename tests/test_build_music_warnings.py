from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from vera_timeline_agent.build_music_warnings import (
    publish_latest_music_warnings,
    report_music_warnings,
)


def report(project_id: str, document_id: str, build_id: str) -> dict[str, Any]:
    return {
        "schemaVersion": "build-report/v2",
        "status": "ready",
        "buildId": build_id,
        "document": {
            "projectId": project_id,
            "documentId": document_id,
            "revision": 4,
        },
        "diagnostics": [
            {
                "code": "MUSIC_SOURCE_SHORTER",
                "severity": "warning",
                "message": "Music file ambient.wav ends before the cue; "
                "no loop was used.",
            },
            {"code": "SOURCE_INSUFFICIENT", "message": "not a music warning"},
        ],
    }


def test_music_warning_projection_keeps_only_build_identity_and_music_warnings(
    tmp_path: Path,
) -> None:
    project_id, document_id, build_id = (str(uuid.uuid4()) for _ in range(3))
    report_path = tmp_path / "build-report.json"
    report_path.write_text(json.dumps(report(project_id, document_id, build_id)))

    assert report_music_warnings(report_path) == {
        "projectId": project_id,
        "documentId": document_id,
        "documentRevision": 4,
        "buildId": build_id,
        "musicWarnings": [
            {
                "code": "MUSIC_SOURCE_SHORTER",
                "message": "Music file ambient.wav ends before the cue; "
                "no loop was used.",
            }
        ],
    }


def test_publish_uses_local_authoring_token_and_fixed_loopback_service(
    tmp_path: Path,
) -> None:
    project_id, document_id, build_id = (str(uuid.uuid4()) for _ in range(3))
    report_path = tmp_path / "build-report.json"
    report_path.write_text(json.dumps(report(project_id, document_id, build_id)))
    calls: list[tuple[str, int, str, dict[str, Any]]] = []

    def send(request: Any, timeout: int) -> int:
        calls.append(
            (
                request.full_url,
                timeout,
                request.get_header("Authorization"),
                json.loads(request.data),
            )
        )
        return 201

    published, reason = publish_latest_music_warnings(
        report_path,
        {"VERA_STT_QA_AUTHORING_TOKEN": "a" * 64, "VERA_STT_QA_PORT": "38430"},
        send,
    )

    assert published
    assert reason == ""
    assert calls == [
        (
            f"http://127.0.0.1:38430/v1/projects/{project_id}/music-warnings",
            10,
            f"Bearer {'a' * 64}",
            report_music_warnings(report_path),
        )
    ]


def test_publish_without_authoring_token_is_explicit_and_does_not_connect(
    tmp_path: Path,
) -> None:
    sent = False

    def send(_request: Any, _timeout: int) -> int:
        nonlocal sent
        sent = True
        return 201

    published, reason = publish_latest_music_warnings(
        tmp_path / "missing-report.json", {}, send
    )

    assert not published
    assert "VERA_STT_QA_AUTHORING_TOKEN" in reason
    assert not sent
