from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import prep_media_research as adapter

CLIP_ID = "00000000-0000-4000-8000-000000000011"
PROJECT_ID = "00000000-0000-4000-8000-000000000022"
CATALOG_VIDEO_ID = "00000000-0000-4000-8000-000000000033"
TRACK_ID = "00000000-0000-4000-8000-000000000044"
VIDEO_ID = "dQw4w9WgXcQ"


def _snapshot() -> dict[str, Any]:
    return {
        "clipId": CLIP_ID,
        "researchProjectId": PROJECT_ID,
        "catalogVideoId": CATALOG_VIDEO_ID,
        "clipVersion": 7,
        "video": {"youtubeVideoId": VIDEO_ID},
        "loggedSelection": {
            "trackId": TRACK_ID,
            "transcriptVersion": 4,
            "exportStartMs": 12000,
            "exportEndMs": 15000,
        },
    }


def _catalog_record(snapshot: dict[str, Any]) -> dict[str, Any]:
    selection = snapshot["loggedSelection"]
    return {
        "id": snapshot["clipId"],
        "projectId": snapshot["researchProjectId"],
        "catalogVideoId": snapshot["catalogVideoId"],
        "version": snapshot["clipVersion"],
        "video": {"youtubeVideoId": snapshot["video"]["youtubeVideoId"]},
        "selection": {
            "trackId": selection["trackId"],
            "transcriptVersion": selection["transcriptVersion"],
            "exportStartMs": selection["exportStartMs"],
            "exportEndMs": selection["exportEndMs"],
        },
    }


def _cut_response(root: Path) -> dict[str, Any]:
    folder = root / CLIP_ID
    return {
        "clips": [
            {
                "clipId": CLIP_ID,
                "videoId": VIDEO_ID,
                "folder": str(folder),
                "mediaPath": str(folder / f"{CLIP_ID}.mp4"),
                "subtitlePaths": [
                    str(folder / f"{CLIP_ID}.en.srt"),
                    str(folder / f"{CLIP_ID}.es.srt"),
                ],
                "manifestPath": str(folder / f"{CLIP_ID}.json"),
            }
        ]
    }


@dataclass
class _ServerState:
    catalog_records: list[dict[str, Any]]
    cut_status: int = 200
    cut_body: dict[str, Any] = field(default_factory=dict)
    package_path: Path | None = None
    requests: list[dict[str, Any]] = field(default_factory=list)
    catalog_reads: int = 0


@contextmanager
def _serve(state: _ServerState) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            state.requests.append(
                {
                    "method": "GET",
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                }
            )
            expected = f"/api/projects/{PROJECT_ID}/clips/{CLIP_ID}"
            if self.path != expected:
                self._send(404, {"error": {"message": "missing"}})
                return
            index = min(state.catalog_reads, len(state.catalog_records) - 1)
            state.catalog_reads += 1
            self._send(200, state.catalog_records[index])

        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            state.requests.append(
                {
                    "method": "POST",
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "body": json.loads(body),
                }
            )
            if state.package_path is not None and state.cut_status == 200:
                state.package_path.mkdir(parents=True, exist_ok=True)
            self._send(state.cut_status, state.cut_body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{int(server.server_address[1])}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_existing_package_returns_without_auth_or_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "research"
    package = root / CLIP_ID
    package.mkdir(parents=True)
    monkeypatch.delenv("VERA_RESEARCH_BEARER", raising=False)
    state = _ServerState([_catalog_record(_snapshot())])

    with _serve(state) as origin:
        result = adapter.acquire_research_cut(
            _snapshot(), package.parent, research_origin=origin, catalog_origin=origin
        )

    assert result == package
    assert state.requests == []


def test_cut_uses_one_authenticated_clip_and_checks_catalog_before_and_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = _snapshot()
    root = tmp_path / "research"
    state = _ServerState(
        [_catalog_record(snapshot)],
        cut_body=_cut_response(root),
        package_path=root / CLIP_ID,
    )
    monkeypatch.setenv("VERA_RESEARCH_BEARER", "fake-test-token")

    with _serve(state) as origin:
        result = adapter.acquire_research_cut(
            snapshot, root, research_origin=origin, catalog_origin=origin
        )

    assert result == root / CLIP_ID
    assert [request["method"] for request in state.requests] == ["GET", "POST", "GET"]
    assert [request["path"] for request in state.requests] == [
        f"/api/projects/{PROJECT_ID}/clips/{CLIP_ID}",
        f"/api/projects/{PROJECT_ID}/clips/cut",
        f"/api/projects/{PROJECT_ID}/clips/{CLIP_ID}",
    ]
    assert all(
        request["authorization"] == "Bearer fake-test-token"
        for request in state.requests
    )
    assert state.requests[1]["body"] == {
        "clipIds": [CLIP_ID],
        "authorizationConfirmed": True,
    }


def test_only_known_yt_dlp_failure_returns_typed_failure_after_catalog_recheck(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = _snapshot()
    message = (
        f"Media provider exited with code 1: ERROR: [youtube] {VIDEO_ID}: "
        "Video unavailable."
    )
    state = _ServerState(
        [_catalog_record(snapshot)],
        cut_status=422,
        cut_body={
            "error": {
                "code": "clip_cut_failed",
                "message": message,
                "retryable": False,
            }
        },
    )
    monkeypatch.setenv("VERA_RESEARCH_BEARER", "fake-test-token")

    with _serve(state) as origin:
        result = adapter.acquire_research_cut(
            snapshot,
            tmp_path / "research",
            research_origin=origin,
            catalog_origin=origin,
        )

    assert result == adapter.ResearchAcquisitionFailure(CLIP_ID, message)
    assert [request["method"] for request in state.requests] == ["GET", "POST", "GET"]


def test_catalog_must_match_frozen_clip_version_before_post(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = _snapshot()
    changed = _catalog_record(snapshot)
    changed["version"] += 1
    state = _ServerState([changed], cut_body=_cut_response(tmp_path / "research"))
    monkeypatch.setenv("VERA_RESEARCH_BEARER", "fake-test-token")

    with (
        _serve(state) as origin,
        pytest.raises(adapter.ResearchCutError, match="no longer matches"),
    ):
        adapter.acquire_research_cut(
            snapshot,
            tmp_path / "research",
            research_origin=origin,
            catalog_origin=origin,
        )

    assert [request["method"] for request in state.requests] == ["GET"]


def test_catalog_must_still_match_after_cut_before_returning_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = _snapshot()
    changed = _catalog_record(snapshot)
    changed["version"] += 1
    root = tmp_path / "research"
    state = _ServerState(
        [_catalog_record(snapshot), changed],
        cut_body=_cut_response(root),
        package_path=root / CLIP_ID,
    )
    monkeypatch.setenv("VERA_RESEARCH_BEARER", "fake-test-token")

    with (
        _serve(state) as origin,
        pytest.raises(adapter.ResearchCutError, match="no longer matches"),
    ):
        adapter.acquire_research_cut(
            snapshot, root, research_origin=origin, catalog_origin=origin
        )

    assert [request["method"] for request in state.requests] == ["GET", "POST", "GET"]


def test_auth_and_renderer_failures_are_not_downgraded_to_download_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = _snapshot()
    state = _ServerState(
        [_catalog_record(snapshot)],
        cut_status=422,
        cut_body={
            "error": {
                "code": "clip_cut_failed",
                "message": "Logged clip range is beyond the available source video.",
                "retryable": False,
            }
        },
    )
    monkeypatch.setenv("VERA_RESEARCH_BEARER", "fake-test-token")

    with (
        _serve(state) as origin,
        pytest.raises(adapter.ResearchCutError, match="HTTP 422"),
    ):
        adapter.acquire_research_cut(
            snapshot,
            tmp_path / "research",
            research_origin=origin,
            catalog_origin=origin,
        )

    assert [request["method"] for request in state.requests] == ["GET", "POST", "GET"]


def test_authorization_failure_is_not_downgraded_to_download_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = _snapshot()
    state = _ServerState(
        [_catalog_record(snapshot)],
        cut_status=401,
        cut_body={"error": {"code": "authentication_required", "message": "no"}},
    )
    monkeypatch.setenv("VERA_RESEARCH_BEARER", "fake-test-token")

    with (
        _serve(state) as origin,
        pytest.raises(adapter.ResearchCutError, match="authorization was refused"),
    ):
        adapter.acquire_research_cut(
            snapshot,
            tmp_path / "research",
            research_origin=origin,
            catalog_origin=origin,
        )

    assert [request["method"] for request in state.requests] == ["GET", "POST", "GET"]


def test_cut_path_must_match_the_trusted_clip_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = _snapshot()
    root = tmp_path / "research"
    body = _cut_response(root)
    body["clips"][0]["folder"] = str(tmp_path / "outside")
    state = _ServerState(
        [_catalog_record(snapshot)],
        cut_body=body,
        package_path=root / CLIP_ID,
    )
    monkeypatch.setenv("VERA_RESEARCH_BEARER", "fake-test-token")

    with (
        _serve(state) as origin,
        pytest.raises(adapter.ResearchCutError, match="path or identity"),
    ):
        adapter.acquire_research_cut(
            snapshot, root, research_origin=origin, catalog_origin=origin
        )


def test_timeout_is_a_transport_error_not_a_typed_download_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Response:
        status = 200

        def __init__(self, value: dict[str, Any]) -> None:
            self._body = json.dumps(value).encode("utf-8")

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def read(self, _length: int) -> bytes:
            return self._body

    class _TimeoutOnCut:
        calls = 0

        def open(self, request: Any, timeout: int) -> _Response:
            self.calls += 1
            if request.get_method() == "GET":
                return _Response(_catalog_record(_snapshot()))
            raise TimeoutError

    opener = _TimeoutOnCut()
    monkeypatch.setattr(adapter, "build_opener", lambda *_args: opener)
    monkeypatch.setenv("VERA_RESEARCH_BEARER", "fake-test-token")

    with pytest.raises(adapter.ResearchCutError, match="service request failed"):
        adapter.acquire_research_cut(
            _snapshot(),
            tmp_path / "research",
            research_origin=adapter.DEFAULT_RESEARCH_ORIGIN,
            catalog_origin=adapter.DEFAULT_CATALOG_ORIGIN,
        )

    assert opener.calls == 2


def test_non_loopback_origins_are_refused() -> None:
    with pytest.raises(adapter.ResearchCutError, match="loopback origin"):
        adapter._loopback_origin("http://example.com:43110", "Research origin")
