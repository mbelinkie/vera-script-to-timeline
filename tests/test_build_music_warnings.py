from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from http.client import BadStatusLine
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.build_music_warnings import (
    publish_latest_music_warnings,
    report_music_warnings,
)
from vera_timeline_agent.v2_package import _compiler_hash


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


def _write_report(path: Path, project_id: str, document_id: str, build_id: str) -> None:
    snapshot = {"projectId": project_id, "id": document_id}
    packaged = path.parent / "package" / "Builds" / build_id
    packaged.mkdir(parents=True)
    raw = json.dumps(report(project_id, document_id, build_id))
    path.write_text(raw)
    (packaged / path.name).write_text(raw)
    (packaged / "script-document.json").write_text(json.dumps(snapshot))
    (path.parent / "row-timeline-map.json").write_text(
        json.dumps({"buildId": build_id, "documentId": document_id})
    )


def test_music_warning_projection_keeps_only_build_identity_and_music_warnings(
    tmp_path: Path,
) -> None:
    project_id, document_id, build_id = (str(uuid.uuid4()) for _ in range(3))
    report_path = tmp_path / "build-report.json"
    _write_report(report_path, project_id, document_id, build_id)

    assert report_music_warnings(report_path) == {
        "projectId": project_id,
        "documentId": document_id,
        "documentDigest": _compiler_hash({"projectId": project_id, "id": document_id}),
        "builtAt": datetime.fromtimestamp(
            (report_path.parent / "row-timeline-map.json").stat().st_mtime, UTC
        )
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
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
    _write_report(report_path, project_id, document_id, build_id)
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


def test_unverified_offline_report_cannot_replace_the_latest_build(
    tmp_path: Path,
) -> None:
    ids = [str(uuid.uuid4()) for _ in range(3)]
    report_path = tmp_path / "build-report.json"
    _write_report(report_path, *ids)
    (tmp_path / "row-timeline-map.json").unlink()

    with pytest.raises(FileNotFoundError):
        report_music_warnings(report_path)


def test_oversized_warning_list_can_still_replace_the_latest_build(
    tmp_path: Path,
) -> None:
    ids = [str(uuid.uuid4()) for _ in range(3)]
    report_path = tmp_path / "build-report.json"
    _write_report(report_path, *ids)
    raw = report(*ids)
    raw["diagnostics"] = raw["diagnostics"][:1] * 33
    report_path.write_text(json.dumps(raw))
    packaged = tmp_path / "package" / "Builds" / ids[2] / report_path.name
    packaged.write_bytes(report_path.read_bytes())

    warnings = report_music_warnings(report_path)["musicWarnings"]
    assert len(warnings) == 32
    assert warnings[-1] == {
        "code": "MORE_MUSIC_WARNINGS",
        "message": "2 more in the build report.",
    }


def test_malformed_http_response_is_an_optional_publish_failure(tmp_path: Path) -> None:
    ids = [str(uuid.uuid4()) for _ in range(3)]
    report_path = tmp_path / "build-report.json"
    _write_report(report_path, *ids)

    def send(_request: Any, _timeout: int) -> int:
        raise BadStatusLine("not HTTP")

    published, message = publish_latest_music_warnings(
        report_path, {"VERA_STT_QA_AUTHORING_TOKEN": "a" * 64}, send
    )
    assert not published and "could not receive" in message
