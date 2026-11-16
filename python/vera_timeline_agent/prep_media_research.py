"""Acquire one logged clip through the authenticated local Research agent."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import stat
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from http.client import HTTPException
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

DEFAULT_RESEARCH_ORIGIN = "http://127.0.0.1:43110"
DEFAULT_CATALOG_ORIGIN = "http://127.0.0.1:43111"
REQUEST_TIMEOUT_SECONDS = 35 * 60
MAX_RESPONSE_BYTES = 256 * 1024

Json = dict[str, Any]


class ResearchCutError(ValueError):
    """A Research transport, authorization, or response-integrity refusal."""


@dataclass(frozen=True)
class ResearchAcquisitionFailure:
    """The one recoverable Research result: yt-dlp could not acquire this source."""

    clip_id: str
    message: str


@dataclass(frozen=True)
class _FrozenClip:
    clip_id: str
    project_id: str
    catalog_video_id: str
    video_id: str
    clip_version: int
    track_id: str
    transcript_version: int
    export_start_ms: int
    export_end_ms: int


@dataclass(frozen=True)
class _Response:
    status: int
    body: bytes
    oversized: bool


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def acquire_research_cut(
    snapshot: Mapping[str, Any],
    research_export_root: Path,
    *,
    research_origin: str = DEFAULT_RESEARCH_ORIGIN,
    catalog_origin: str = DEFAULT_CATALOG_ORIGIN,
) -> Path | ResearchAcquisitionFailure:
    """Return the authorized package path for one frozen logged clip.

    Existing packages are returned for the caller's independent manifest and
    byte verification. Missing packages are cut only after the authenticated
    catalog matches the frozen selection, and are rechecked after the request.
    """
    clip = _frozen_clip(snapshot)
    root = _export_root(research_export_root)
    package = root / clip.clip_id

    if _existing_package(package, root):
        return package

    research_base = _loopback_origin(research_origin, "Research origin")
    catalog_base = _loopback_origin(catalog_origin, "catalog origin")
    token = _bearer_token()
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    catalog_path = (
        f"/api/projects/{quote(clip.project_id, safe='')}/clips/"
        f"{quote(clip.clip_id, safe='')}"
    )
    _assert_current_catalog(opener, catalog_base, catalog_path, token, clip)

    cut_path = f"/api/projects/{quote(clip.project_id, safe='')}/clips/cut"
    response = _request(
        opener,
        "POST",
        research_base + cut_path,
        token,
        {"clipIds": [clip.clip_id], "authorizationConfirmed": True},
    )

    # A completed HTTP response is always followed by an exact catalog check,
    # including a recognized source-download failure.
    _assert_current_catalog(opener, catalog_base, catalog_path, token, clip)

    if response.oversized:
        raise ResearchCutError("Research cut response exceeded its size limit.")
    result = _json_object(response.body, "Research cut response")
    if response.status != 200:
        failure = _known_download_failure(response.status, result, clip.video_id)
        if failure is not None:
            return ResearchAcquisitionFailure(clip.clip_id, failure)
        if response.status in (401, 403):
            raise ResearchCutError("Research cut authorization was refused.")
        raise ResearchCutError(f"Research cut request failed (HTTP {response.status}).")

    _verify_cut_result(result, clip, root, package)
    _require_package_directory(root, package)
    return package


def _frozen_clip(snapshot: Mapping[str, Any]) -> _FrozenClip:
    try:
        selection = snapshot["loggedSelection"]
        video = snapshot["video"]
        if not isinstance(selection, Mapping) or not isinstance(video, Mapping):
            raise TypeError
        frozen = _FrozenClip(
            clip_id=_canonical_uuid(snapshot["clipId"], "clip ID"),
            project_id=_canonical_uuid(
                snapshot["researchProjectId"], "Research project ID"
            ),
            catalog_video_id=_canonical_uuid(
                snapshot["catalogVideoId"], "catalog video ID"
            ),
            video_id=_required_string(video["youtubeVideoId"], "YouTube video ID"),
            clip_version=_positive_int(snapshot["clipVersion"], "clip version"),
            track_id=_canonical_uuid(selection["trackId"], "selection track ID"),
            transcript_version=_positive_int(
                selection["transcriptVersion"], "transcript version"
            ),
            export_start_ms=_nonnegative_int(
                selection["exportStartMs"], "selection start"
            ),
            export_end_ms=_positive_int(selection["exportEndMs"], "selection end"),
        )
    except (KeyError, TypeError) as error:
        raise ResearchCutError(
            "Frozen Research clip selection is incomplete."
        ) from error
    if (
        not re.fullmatch(r"[A-Za-z0-9_-]{11}", frozen.video_id)
        or frozen.export_end_ms <= frozen.export_start_ms
    ):
        raise ResearchCutError("Frozen Research clip selection is invalid.")
    return frozen


def _canonical_uuid(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ResearchCutError(f"Frozen {label} is invalid.")
    try:
        canonical = str(uuid.UUID(value))
    except ValueError as error:
        raise ResearchCutError(f"Frozen {label} is invalid.") from error
    if value != canonical:
        raise ResearchCutError(f"Frozen {label} is not canonical.")
    return canonical


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ResearchCutError(f"Frozen {label} is invalid.")
    return value


def _positive_int(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ResearchCutError(f"Frozen {label} is invalid.")
    return value


def _nonnegative_int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ResearchCutError(f"Frozen {label} is invalid.")
    return value


def _export_root(value: Path) -> Path:
    root = Path(value)
    if not root.is_absolute() or "\0" in str(root):
        raise ResearchCutError("Research export root must be an absolute path.")
    normalized = Path(os.path.abspath(root))
    if (
        normalized == Path(normalized.anchor)
        or normalized.resolve(strict=False) != normalized
    ):
        raise ResearchCutError("Research export root must be a real trusted directory.")
    try:
        info = normalized.lstat()
    except FileNotFoundError:
        return normalized
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise ResearchCutError("Research export root is not a real directory.")
    return normalized


def _existing_package(package: Path, root: Path) -> bool:
    try:
        info = package.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise ResearchCutError("Existing Research clip package is not a directory.")
    _require_package_directory(root, package)
    return True


def _require_package_directory(root: Path, package: Path) -> None:
    try:
        root_info = root.lstat()
        package_info = package.lstat()
    except OSError as error:
        raise ResearchCutError(
            "Research clip package is missing or inaccessible."
        ) from error
    if (
        not stat.S_ISDIR(root_info.st_mode)
        or stat.S_ISLNK(root_info.st_mode)
        or not stat.S_ISDIR(package_info.st_mode)
        or stat.S_ISLNK(package_info.st_mode)
    ):
        raise ResearchCutError("Research clip package path is not trusted.")


def _loopback_origin(value: str, label: str) -> str:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
        if (
            parsed.scheme != "http"
            or host is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or port is None
            or not 1024 <= port <= 65535
        ):
            raise ValueError
        if host.lower() == "localhost":
            authority = f"localhost:{port}"
        else:
            address = ipaddress.ip_address(host)
            if not address.is_loopback:
                raise ValueError
            authority = (
                f"[{address.compressed}]:{port}"
                if address.version == 6
                else f"{address.compressed}:{port}"
            )
    except ValueError as error:
        raise ResearchCutError(
            f"{label} must be a bare HTTP loopback origin."
        ) from error
    return f"http://{authority}"


def _bearer_token() -> str:
    token = os.environ.get("VERA_RESEARCH_BEARER", "")
    if not token or len(token) > 4096 or not re.fullmatch(r"[\x21-\x7e]+", token):
        raise ResearchCutError("VERA_RESEARCH_BEARER is missing or invalid.")
    return token


def _request(
    opener: Any,
    method: str,
    url: str,
    token: str,
    payload: Json | None = None,
) -> _Response:
    data = (
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
        if payload is not None
        else None
    )
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return _read_response(response.status, response)
    except HTTPError as error:
        try:
            return _read_response(error.code, error)
        finally:
            error.close()
    except (URLError, TimeoutError, OSError, HTTPException):
        raise ResearchCutError("Research local service request failed.") from None


def _read_response(status: int, response: Any) -> _Response:
    body = response.read(MAX_RESPONSE_BYTES + 1)
    return _Response(
        status=status,
        body=body[:MAX_RESPONSE_BYTES],
        oversized=len(body) > MAX_RESPONSE_BYTES,
    )


def _json_object(raw: bytes, label: str) -> Json:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ResearchCutError(f"{label} is not valid JSON.") from error
    if not isinstance(value, dict):
        raise ResearchCutError(f"{label} must be a JSON object.")
    return cast(Json, value)


def _assert_current_catalog(
    opener: Any,
    catalog_origin: str,
    path: str,
    token: str,
    clip: _FrozenClip,
) -> None:
    response = _request(opener, "GET", catalog_origin + path, token)
    if response.oversized:
        raise ResearchCutError("Research catalog response exceeded its size limit.")
    if response.status in (401, 403):
        raise ResearchCutError("Research catalog authorization was refused.")
    if response.status != 200:
        raise ResearchCutError(
            f"Research catalog request failed (HTTP {response.status})."
        )
    record = _json_object(response.body, "Research catalog response")
    selection = record.get("selection")
    video = record.get("video")
    if not isinstance(selection, Mapping) or not isinstance(video, Mapping):
        raise ResearchCutError("Current Research catalog clip is incomplete.")
    if (
        record.get("id") != clip.clip_id
        or record.get("projectId") != clip.project_id
        or record.get("catalogVideoId") != clip.catalog_video_id
        or record.get("version") != clip.clip_version
        or type(record.get("version")) is not int
        or video.get("youtubeVideoId") != clip.video_id
        or selection.get("trackId") != clip.track_id
        or selection.get("transcriptVersion") != clip.transcript_version
        or type(selection.get("transcriptVersion")) is not int
        or selection.get("exportStartMs") != clip.export_start_ms
        or type(selection.get("exportStartMs")) is not int
        or selection.get("exportEndMs") != clip.export_end_ms
        or type(selection.get("exportEndMs")) is not int
    ):
        raise ResearchCutError(
            "Research catalog no longer matches the frozen clip selection."
        )


def _known_download_failure(status: int, body: Json, video_id: str) -> str | None:
    if status != 422:
        return None
    error = body.get("error")
    if not isinstance(error, Mapping):
        return None
    message = error.get("message")
    if (
        error.get("code") != "clip_cut_failed"
        or error.get("retryable") is not False
        or not isinstance(message, str)
    ):
        return None
    prefix = f"Media provider exited with code 1: ERROR: [youtube] {video_id}: "
    if message.startswith(prefix) and len(message) > len(prefix):
        return message
    return None


def _verify_cut_result(
    body: Json, clip: _FrozenClip, root: Path, package: Path
) -> None:
    results = body.get("clips")
    if not isinstance(results, list) or len(results) != 1:
        raise ResearchCutError("Research cut response did not contain one clip.")
    item = results[0]
    if not isinstance(item, Mapping):
        raise ResearchCutError("Research cut response clip is invalid.")
    expected_folder = str(package)
    expected_media = str(package / f"{clip.clip_id}.mp4")
    expected_manifest = str(package / f"{clip.clip_id}.json")
    subtitles = item.get("subtitlePaths")
    if (
        item.get("clipId") != clip.clip_id
        or item.get("videoId") != clip.video_id
        or item.get("folder") != expected_folder
        or item.get("mediaPath") != expected_media
        or item.get("manifestPath") != expected_manifest
        or not isinstance(subtitles, list)
        or not 1 <= len(subtitles) <= 2
        or any(not isinstance(path, str) for path in subtitles)
    ):
        raise ResearchCutError("Research cut response path or identity is invalid.")
    subtitle_names = [Path(path).name for path in subtitles]
    if any(
        Path(path).parent != package
        or not re.fullmatch(
            re.escape(clip.clip_id) + r"\.[a-zA-Z0-9-]{2,35}\.srt", Path(path).name
        )
        for path in subtitles
    ):
        raise ResearchCutError("Research cut response subtitle path is invalid.")
    if (
        len(subtitles) != len(set(subtitles))
        or f"{clip.clip_id}.en.srt" not in subtitle_names
    ):
        raise ResearchCutError("Research cut response subtitle set is invalid.")
