"""One-use native Resolve sample-precision probe for issue #257.

This is a separate, explicitly selected probe. It does not share the strict
qualification-output construction path: the point is to retain and render the
fractional sample-derived arguments so a host-side PCM verifier can decide what
Resolve actually persisted.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import stat
import tempfile
import time
import uuid
import wave
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

REQUEST_SCHEMA = "vera-sample-precision-probe-request/v1"
RESULT_SCHEMA = "vera-sample-precision-probe-result/v1"
AUTHORIZATION_SECONDS = 1800
RENDER_TIMEOUT_SECONDS = 180

SOURCE_SHA256 = "6aea860f3587385225e0fad8d0c2260c9fc4e2fa8f41d89b33453e7d219bb412"
SOURCE_PCM_SHA256 = "3c50c3132006a611f71be916d7ff8480148f730beca8992e0b157fb40ee53e97"
REVIEW_SHA256 = "e9e875d2dba341ffdb920bc2748a0a5d9676a6c782451b913b489d04ede35937"
MARKER_SHA256 = "37df28f5889038bc7adc556371020dd93f832bbc15ef94c06b9470f6cec47760"
PROBE_STATE_ROOT = (
    Path.home()
    / "Library"
    / "Application Support"
    / "VERA"
    / "sample-precision-probe-v1"
)

SUPPORTS = [
    {"word": "to", "onsetSample": 225600, "endSample": 232320},
    {"word": "this", "onsetSample": 232320, "endSample": 241440},
    {"word": "cute", "onsetSample": 241440, "endSample": 255360},
]
TARGET_GAP = {"startSample": 232320, "endSample": 241440}
PROGRAMME = {
    "frameSamples": 2002,
    "sampleRate": 48000,
    "channels": 1,
    "bitDepth": 24,
    "sourceSamples": 400400,
    "programmeSamples": 400400,
}
PROFILE = {
    "frameRateNumerator": 24000,
    "frameRateDenominator": 1001,
    "frameRate": 23.976,
    "width": 1920,
    "height": 1080,
    "timelineSampleRate": 48000,
    "timecodeStart": "00:00:00:00",
    "timelineFrames": 200,
    "markIn": 0,
    "markOut": 199,
}
TARGET_KEYS = {"projectUid", "timelineUid", "projectName", "timelineName"}
REQUEST_KEYS = {
    "schemaVersion",
    "requestId",
    "releaseRoot",
    "releaseSha256",
    "outputDir",
    "sourcePath",
    "sourceSha256",
    "sourcePcmSha256",
    "reviewPath",
    "reviewSha256",
    "markerPath",
    "markerSha256",
    "frameSamples",
    "sampleRate",
    "channels",
    "bitDepth",
    "sourceSamples",
    "programmeSamples",
    "targetGap",
    "supports",
    "profile",
    "target",
    "taskId",
    "producerAuthorization",
    "issuedAt",
    "expiresAt",
}
RELEASE_RUNTIME_FILES = (
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
    "sample_precision_probe_v2.py",
)
_MAX_RECORD_BYTES = 4 * 1024 * 1024


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _no_symlink_ancestry(path: Path) -> None:
    _require(
        path.is_absolute() and str(path) == os.path.abspath(path),
        "path must be canonical absolute",
    )
    _require(
        not any(part.is_symlink() for part in (path, *path.parents)),
        "symbolic link in protected path",
    )


def _read(path: Path, *, limit: int = _MAX_RECORD_BYTES) -> bytes:
    _no_symlink_ancestry(path)
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise ValueError("probe input is unavailable") from error
    try:
        before = os.fstat(fd)
        _require(
            stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
            "probe input must be an unlinked regular file",
        )
        _require(before.st_size <= limit, "probe input exceeds size bound")
        chunks: list[bytes] = []
        size = 0
        while chunk := os.read(fd, 1024 * 1024):
            size += len(chunk)
            _require(size <= limit, "probe input grew beyond size bound")
            chunks.append(chunk)
        after = os.fstat(fd)
        _require(
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            and size == before.st_size,
            "probe input changed during read",
        )
        return b"".join(chunks)
    finally:
        os.close(fd)


def _json_object(payload: bytes) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            _require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def invalid(value: str) -> None:
        raise ValueError(f"nonfinite JSON number: {value}")

    value = json.loads(payload, object_pairs_hook=pairs, parse_constant=invalid)
    _require(type(value) is dict, "probe record must be a JSON object")
    json.dumps(value, allow_nan=False)
    return cast(dict[str, Any], value)


def _text(value: Any, label: str, *, limit: int = 1024) -> str:
    _require(
        type(value) is str and bool(value.strip()) and len(value) <= limit,
        f"invalid {label}",
    )
    return cast(str, value)


def _hash(value: Any, label: str) -> str:
    _require(
        type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        f"invalid {label}",
    )
    return cast(str, value)


def _closed(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == keys, f"invalid {label} fields")
    return cast(dict[str, Any], value)


def _path(value: Any, label: str) -> Path:
    path = Path(_text(value, label))
    _no_symlink_ancestry(path)
    return path


def _timestamp(value: Any) -> datetime:
    text = _text(value, "UTC timestamp", limit=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("invalid probe authorization timestamp") from error
    _require(parsed.utcoffset() is not None, "probe timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _now() -> datetime:
    return datetime.now(UTC)


def _check_live_window(request: dict[str, Any], *, now: datetime | None = None) -> None:
    issued, expires = _timestamp(request["issuedAt"]), _timestamp(request["expiresAt"])
    instant = now or _now()
    _require(
        issued <= instant < expires
        and timedelta(0) < expires - issued <= timedelta(seconds=AUTHORIZATION_SECONDS),
        "probe authorization is expired or outside its 30-minute window",
    )


def _write_immutable(path: Path, value: object) -> Path:
    _no_symlink_ancestry(path.parent)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()
    fd, name = tempfile.mkstemp(prefix=".sample-probe-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o400)
        os.link(temporary, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _validate_source(
    source_path: Path, *, expected_sha: str | None = None
) -> tuple[str, int]:
    if expected_sha is None:
        expected_sha = SOURCE_SHA256
    payload = _read(source_path, limit=64 * 1024 * 1024)
    source_sha = _sha(payload)
    _require(source_sha == expected_sha, "original PCM24 source bytes changed")
    try:
        with wave.open(io.BytesIO(payload), "rb") as audio:
            _require(
                audio.getcomptype() == "NONE"
                and audio.getnchannels() == 1
                and audio.getsampwidth() == 3
                and audio.getframerate() == 48000
                and audio.getnframes() == 400400,
                "source must remain the reviewed mono PCM24/48 kHz 400400-sample WAV",
            )
            pcm = audio.readframes(audio.getnframes())
            _require(
                audio.readframes(1) == b"", "unexpected WAV frames after programme"
            )
    except (wave.Error, EOFError) as error:
        raise ValueError("source WAV is not readable PCM") from error
    pcm_sha = _sha(pcm)
    _require(
        pcm_sha == SOURCE_PCM_SHA256 and len(pcm) == 400400 * 3,
        "source raw PCM bytes changed",
    )
    return pcm_sha, 400400


def _verify_review(review_path: Path) -> tuple[str, Path]:
    payload = _read(review_path)
    review_sha = _sha(payload)
    _require(review_sha == REVIEW_SHA256, "review confirmation bytes changed")
    review = _json_object(payload)
    _require(
        review.get("schemaVersion") == "issue215-c-reviewed-source/v1"
        and review.get("frameSamples") == 2002
        and review.get("originalSourceAudioHash") == f"sha256:{SOURCE_SHA256}"
        and review.get("sourcePcmSha256") == f"sha256:{SOURCE_PCM_SHA256}"
        and review.get("supports") == SUPPORTS
        and review.get("confirmationSource", "").startswith(
            "direct user message in Codex task "
        )
        and isinstance(review.get("confirmation"), str)
        and "I confirm" in review["confirmation"],
        "review does not contain the pinned direct-user source confirmation",
    )
    marker_path = _path(review.get("reviewedMarkerFile"), "reviewed marker path")
    marker_sha = _sha(_read(marker_path))
    _require(
        marker_sha == MARKER_SHA256
        and review.get("reviewedMarkerFileHash") == f"sha256:{MARKER_SHA256}",
        "reviewed marker bytes changed",
    )
    return marker_sha, marker_path


def _verify_release(
    release_root: Path,
    expected_sha: str | None = None,
    *,
    installed: bool = False,
    runtime_files: tuple[str, ...] | None = None,
) -> str:
    # A sibling probe (issue 259) pins its own, larger closed inventory.
    declared_runtime = RELEASE_RUNTIME_FILES if runtime_files is None else runtime_files
    _no_symlink_ancestry(Path(os.path.abspath(release_root)))
    manifest_path = release_root / "vera-delivery-v2" / "release.json"
    payload = _read(manifest_path)
    digest = _sha(payload)
    if expected_sha is not None:
        _require(digest == expected_sha, "installed precision release manifest changed")
    manifest = _closed(
        _json_object(payload),
        {"schemaVersion", "deliveryVersion", "sourcePins", "files"},
        "release manifest",
    )
    _require(
        manifest["schemaVersion"] == "vera-injected-delivery-release/v2"
        and manifest["deliveryVersion"] == "2"
        and type(manifest["files"]) is list,
        "unsupported precision release manifest",
    )
    expected_paths = {
        "VERA Delivery v2.py",
        *(
            f"vera-delivery-v2/python/vera_timeline_agent/{name}"
            for name in declared_runtime
        ),
    }
    seen: set[str] = set()
    for raw in manifest["files"]:
        entry = _closed(raw, {"path", "sha256", "sizeBytes"}, "release entry")
        name = _text(entry["path"], "release entry path")
        _require(
            name in expected_paths and name not in seen,
            "undeclared precision release file",
        )
        file_path = release_root / name
        data = _read(file_path, limit=64 * 1024 * 1024)
        _require(
            type(entry["sizeBytes"]) is int
            and len(data) == entry["sizeBytes"]
            and _sha(data) == _hash(entry["sha256"], "release file hash"),
            "precision release file changed",
        )
        seen.add(name)
    _require(seen == expected_paths, "precision release inventory is incomplete")
    allowed = expected_paths | {"vera-delivery-v2/release.json"}
    if installed:
        allowed.add("vera-delivery-v2/request.json")
    declared_dirs = {
        parent.as_posix()
        for name in expected_paths
        for parent in Path(name).parents
        if parent != Path(".")
    }
    if installed:
        declared_dirs.add("vera-delivery-v2")
    # The Workflow Integration Plugins folder intentionally contains other
    # installed products. An installed precision verification owns only its
    # delivery subtree and the launcher script that dispatches into it.
    inventory_roots = (
        (release_root / "vera-delivery-v2",) if installed else (release_root,)
    )
    inventory_items = [item for root in inventory_roots for item in root.rglob("*")]
    if installed:
        inventory_items.append(release_root / "VERA Delivery v2.py")
    for item in inventory_items:
        _no_symlink_ancestry(item.absolute())
        if item.name == ".DS_Store" and item.is_file():
            continue
        relative = item.relative_to(release_root).as_posix()
        _require(
            relative in (declared_dirs if item.is_dir() else allowed)
            and (item.is_dir() or item.is_file()),
            "undeclared file or directory in precision release",
        )
    _require(
        (release_root / "vera-delivery-v2").is_dir(),
        "precision runtime directory unavailable",
    )
    return digest


def _validate_request(request: Any, *, require_live: bool = True) -> dict[str, Any]:
    value = _closed(request, REQUEST_KEYS, "sample-precision request")
    _require(
        value["schemaVersion"] == REQUEST_SCHEMA, "unsupported sample-precision request"
    )
    _text(value["requestId"], "request ID", limit=64)
    _hash(value["releaseSha256"], "release hash")
    _text(value["taskId"], "task ID", limit=256)
    _text(value["producerAuthorization"], "producer authorization", limit=4096)
    _require(
        value["frameSamples"] == PROGRAMME["frameSamples"]
        and value["sampleRate"] == PROGRAMME["sampleRate"]
        and value["channels"] == PROGRAMME["channels"]
        and value["bitDepth"] == PROGRAMME["bitDepth"]
        and value["sourceSamples"] == PROGRAMME["sourceSamples"]
        and value["programmeSamples"] == PROGRAMME["programmeSamples"]
        and value["targetGap"] == TARGET_GAP
        and value["supports"] == SUPPORTS
        and value["profile"] == PROFILE,
        "sample-precision request differs from the fixed reviewed experiment",
    )
    _closed(value["target"], TARGET_KEYS, "target")
    for item in value["target"].values():
        _text(item, "target identity")
    for key in ("sourceSha256", "sourcePcmSha256", "reviewSha256", "markerSha256"):
        _hash(value[key], key)
    _require(
        value["sourceSha256"] == SOURCE_SHA256
        and value["sourcePcmSha256"] == SOURCE_PCM_SHA256
        and value["reviewSha256"] == REVIEW_SHA256
        and value["markerSha256"] == MARKER_SHA256,
        "sample-precision source or review binding differs",
    )
    for key in ("releaseRoot", "outputDir", "sourcePath", "reviewPath", "markerPath"):
        value[key] = str(_path(value[key], key))
    output = Path(value["outputDir"])
    protected = (
        Path(value["releaseRoot"]),
        Path(value["sourcePath"]).parent,
        Path(value["reviewPath"]).parent,
        Path(value["markerPath"]).parent,
    )
    _require(
        all(
            not output.is_relative_to(path) and not path.is_relative_to(output)
            for path in protected
        ),
        "probe output overlaps release or reviewed media/evidence",
    )
    if require_live:
        _check_live_window(value)
    else:
        issued, expires = _timestamp(value["issuedAt"]), _timestamp(value["expiresAt"])
        _require(
            timedelta(0) < expires - issued <= timedelta(seconds=AUTHORIZATION_SECONDS),
            "probe authorization exceeded its 30-minute window",
        )
    return value


def load_probe_request(
    path: Path, expected_sha256: str, *, require_live: bool = True
) -> dict[str, Any]:
    """Read the exact immutable probe request after checking its caller pin."""
    _hash(expected_sha256, "expected request hash")
    payload = _read(path)
    _require(_sha(payload) == expected_sha256, "sample-precision request changed")
    return _validate_request(_json_object(payload), require_live=require_live)


def prepare_probe_request(
    *,
    release_root: Path,
    output: Path,
    source: Path,
    review: Path,
    target: dict[str, str],
    producer_authorization: str,
    task_id: str,
) -> Path:
    """Create a one-use, 30-minute request for this explicitly selected probe."""
    release_root = Path(os.path.abspath(release_root))
    source = Path(os.path.abspath(source))
    review = Path(os.path.abspath(review))
    output = Path(os.path.abspath(output))
    _no_symlink_ancestry(release_root)
    _no_symlink_ancestry(source)
    _no_symlink_ancestry(review)
    _no_symlink_ancestry(output)
    _require(
        type(target) is dict and set(target) == TARGET_KEYS, "invalid target identity"
    )
    target = {key: _text(target[key], key) for key in sorted(TARGET_KEYS)}
    producer_authorization = _text(
        producer_authorization, "producer authorization", limit=4096
    )
    task_id = _text(task_id, "task ID", limit=256)
    release_sha = _verify_release(release_root)
    source_pcm_sha, sample_count = _validate_source(source)
    review_sha = _sha(_read(review))
    marker_sha, marker_path = _verify_review(review)
    _require(
        review_sha == REVIEW_SHA256
        and source_pcm_sha == SOURCE_PCM_SHA256
        and sample_count == PROGRAMME["sourceSamples"],
        "source review does not match pinned source",
    )
    protected = (release_root, source, review, marker_path)
    _require(
        all(
            not output.is_relative_to(path) and not path.is_relative_to(output)
            for path in protected
        ),
        "probe output overlaps release or reviewed input",
    )
    now = _now()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    request_path = output / "request.json"
    value = {
        "schemaVersion": REQUEST_SCHEMA,
        "requestId": str(uuid.uuid4()),
        "releaseRoot": str(release_root),
        "releaseSha256": release_sha,
        "outputDir": str(output),
        "sourcePath": str(source),
        "sourceSha256": SOURCE_SHA256,
        "sourcePcmSha256": source_pcm_sha,
        "reviewPath": str(review),
        "reviewSha256": review_sha,
        "markerPath": str(marker_path),
        "markerSha256": marker_sha,
        **PROGRAMME,
        "targetGap": dict(TARGET_GAP),
        "supports": SUPPORTS,
        "profile": dict(PROFILE),
        "target": target,
        "taskId": task_id,
        "producerAuthorization": producer_authorization,
        "issuedAt": now.isoformat(),
        "expiresAt": (now + timedelta(seconds=AUTHORIZATION_SECONDS)).isoformat(),
    }
    _validate_request(value)
    path = _write_immutable(request_path, value)
    return path


def _native_value(value: Any, *, depth: int = 0) -> Any:
    """Keep getter values raw when JSON-safe, tagging opaque API handles."""
    if depth > 6:
        return {"pythonType": type(value).__name__, "value": "depth-limit"}
    if value is None or type(value) in {str, int, bool}:
        return value
    if type(value) is float:
        return (
            value
            if math.isfinite(value)
            else {"pythonType": "float", "value": repr(value)}
        )
    if type(value) is list:
        return [_native_value(item, depth=depth + 1) for item in value]
    if type(value) is tuple:
        return {
            "pythonType": "tuple",
            "value": [_native_value(item, depth=depth + 1) for item in value],
        }
    if type(value) is dict:
        if all(type(key) is str for key in value):
            return {
                key: _native_value(item, depth=depth + 1) for key, item in value.items()
            }
        return {"pythonType": "dict", "value": repr(value)}
    getter = getattr(value, "GetUniqueId", None)
    uid = None
    if callable(getter):
        with suppress(Exception):
            uid = getter()
    return {"pythonType": type(value).__name__, "uniqueId": uid}


def _invoke(owner: Any, method: str, *args: Any) -> Any:
    function = getattr(owner, method, None)
    if not callable(function):
        raise ValueError(f"Resolve API {method} is unavailable")
    return function(*args)


def _context(resolve: Any, target: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    manager = _invoke(resolve, "GetProjectManager")
    project = _invoke(manager, "GetCurrentProject")
    timeline = _invoke(project, "GetCurrentTimeline")
    _require(
        _invoke(project, "GetUniqueId") == target["projectUid"]
        and _invoke(project, "GetName") == target["projectName"]
        and _invoke(timeline, "GetUniqueId") == target["timelineUid"]
        and _invoke(timeline, "GetName") == target["timelineName"],
        "current Resolve target differs from the explicitly authorized target",
    )
    pool = _invoke(project, "GetMediaPool")
    return manager, project, timeline, pool


def _assert_target_settings(project: Any, timeline: Any) -> dict[str, Any]:
    settings = {
        "frameRate": _invoke(timeline, "GetSetting", "timelineFrameRate"),
        "width": _invoke(timeline, "GetSetting", "timelineResolutionWidth"),
        "height": _invoke(timeline, "GetSetting", "timelineResolutionHeight"),
        "sampleRate": _invoke(project, "GetSetting", "timelineSampleRate"),
        "startFrame": _invoke(timeline, "GetStartFrame"),
        "startTimecode": _invoke(timeline, "GetStartTimecode"),
    }
    _require(
        str(settings["frameRate"]) == "23.976"
        and str(settings["width"]) == "1920"
        and str(settings["height"]) == "1080"
        and str(settings["sampleRate"]) == "48000"
        and settings["startFrame"] == 0
        and settings["startTimecode"] == PROFILE["timecodeStart"],
        "target timeline settings differ from the fixed sample-precision profile",
    )
    return settings


def _check_empty_target(project: Any, timeline: Any, pool: Any) -> dict[str, Any]:
    _require(_invoke(timeline, "GetMarkers") == {}, "target timeline has markers")
    track_counts: dict[str, int] = {}
    for kind in ("video", "audio", "subtitle"):
        count = _invoke(timeline, "GetTrackCount", kind)
        _require(
            type(count) is int and 0 <= count <= 32,
            "target track inventory is unreadable",
        )
        track_counts[kind] = count
        for index in range(1, count + 1):
            items = _invoke(timeline, "GetItemListInTrack", kind, index)
            _require(
                type(items) in {list, tuple} and len(items) == 0,
                "target timeline is not empty",
            )
    _require(
        track_counts["audio"] == 1, "probe requires exactly one empty audio track (A1)"
    )
    _require(
        callable(getattr(timeline, "DeleteClips", None)),
        "Timeline.DeleteClips non-ripple API is unavailable",
    )
    root = _invoke(pool, "GetRootFolder")
    media_items = _invoke(root, "GetClipList")
    folders = _invoke(root, "GetSubFolderList")
    timeline_media = _invoke(timeline, "GetMediaPoolItem")
    timeline_media_uid = _invoke(timeline_media, "GetUniqueId")
    _require(
        type(media_items) in {list, tuple}
        and len(media_items) == 1
        and _invoke(media_items[0], "GetUniqueId") == timeline_media_uid
        and type(folders) in {list, tuple}
        and len(folders) == 0,
        "target media pool contains media other than its empty timeline",
    )
    _require(
        _invoke(project, "IsRenderingInProgress") is False,
        "Resolve is currently rendering",
    )
    jobs = _invoke(project, "GetRenderJobList")
    _require(
        type(jobs) in {list, tuple} and len(jobs) == 0,
        "target render queue is not empty",
    )
    _require(
        callable(getattr(pool, "ImportMedia", None)),
        "MediaPool.ImportMedia is unavailable",
    )
    _require(
        callable(getattr(pool, "AppendToTimeline", None)),
        "MediaPool.AppendToTimeline is unavailable",
    )
    _require(
        all(
            callable(getattr(project, name, None))
            for name in (
                "GetRenderFormats",
                "GetRenderCodecs",
                "GetAudioRenderCodecs",
                "SetCurrentRenderFormatAndCodec",
                "GetCurrentRenderFormatAndCodec",
                "SetCurrentRenderMode",
                "GetCurrentRenderMode",
                "SetRenderSettings",
                "AddRenderJob",
                "StartRendering",
                "GetRenderJobList",
                "GetRenderJobStatus",
                "IsRenderingInProgress",
            )
        ),
        "required bounded render API is unavailable",
    )
    _require(
        _invoke(project, "GetRenderFormats").get("QuickTime") == "mov"
        and _invoke(project, "GetRenderCodecs", "mov").get("Apple ProRes 422")
        == "ProRes422"
        and _invoke(project, "GetAudioRenderCodecs", "mov").get("Linear PCM") == "lpcm",
        "Resolve lacks the fixed MOV/ProRes422/lpcm render profile",
    )
    return {"trackCounts": track_counts, "renderQueue": list(jobs), "markers": {}}


def _claim_once(request: dict[str, Any], request_sha: str) -> tuple[Path, str]:
    identity = "\0".join(
        (request["target"]["projectUid"], request["target"]["timelineUid"])
    )
    target_key = _sha(identity.encode())
    intent_root = PROBE_STATE_ROOT / "intents"
    _no_symlink_ancestry(Path(os.path.abspath(intent_root)))
    target_path = intent_root / f"target-{target_key}.json"
    invocation_path = intent_root / f"request-{request_sha}.json"
    record = {
        "schemaVersion": "vera-sample-precision-probe-intent/v1",
        "requestSha256": request_sha,
        "target": request["target"],
        "claimedAt": _now().isoformat(),
    }
    _write_immutable(target_path, record)
    # Retain target ownership if invocation publication is uncertain.
    _write_immutable(invocation_path, record)
    return target_path, _sha(_read(target_path))


def _journal_effect(
    state: dict[str, Any],
    stage: str,
    owner: Any,
    method: str,
    arguments: Any,
    *,
    current_required: bool = True,
    call_arguments: list[Any] | None = None,
) -> Any:
    _require(
        current_required or method == "LoadProject",
        "only the authorized named-project reopen may run "
        "without current-target context",
    )
    if current_required:
        _context(state["resolve"], state["request"]["target"])
    _check_live_window(state["request"])
    sequence = len(state["effects"]) + 1
    journal_path = (
        state["journalDir"] / f"effect-{sequence:02d}-{uuid.uuid4().hex}.json"
    )
    prepared = {
        "schemaVersion": "vera-sample-precision-probe-effect/v1",
        "requestSha256": state["requestSha256"],
        "target": state["request"]["target"],
        "stage": stage,
        "method": method,
        "arguments": arguments,
        "preparedAt": _now().isoformat(),
        "status": "prepared_before_native_call",
    }
    _write_immutable(journal_path, prepared)
    row = {
        "stage": stage,
        "method": method,
        "arguments": arguments,
        "journalPath": str(journal_path),
        "journalSha256": _sha(_read(journal_path)),
        "returnValue": None,
        "status": "ambiguous",
    }
    state["effects"].append(row)
    try:
        if current_required:
            _context(state["resolve"], state["request"]["target"])
        _check_live_window(state["request"])
        value = _invoke(
            owner, method, *(arguments if call_arguments is None else call_arguments)
        )
        row["returnValue"] = _native_value(value)
        row["status"] = "returned"
        return value
    except Exception as error:
        row["error"] = {"type": type(error).__name__, "message": str(error)[:1000]}
        raise


def _snapshot(stage: str, timeline: Any, expected_count: int) -> dict[str, Any]:
    items = _invoke(timeline, "GetItemListInTrack", "audio", 1)
    _require(
        type(items) in {list, tuple} and len(items) == expected_count,
        f"{stage}: unexpected A1 item count",
    )
    captured: list[dict[str, Any]] = []
    getters = (
        ("GetStart", ()),
        ("GetEnd", ()),
        ("GetStart", (True,)),
        ("GetEnd", (True,)),
        ("GetStartTime", ()),
        ("GetEndTime", ()),
        ("GetDuration", (False,)),
        ("GetDuration", (True,)),
        ("GetSourceStartFrame", ()),
        ("GetSourceEndFrame", ()),
        ("GetSourceStartTime", ()),
        ("GetSourceEndTime", ()),
    )
    for item in items:
        get_uid = getattr(item, "GetUniqueId", None)
        uid: Any = None
        with suppress(Exception):
            uid = get_uid() if callable(get_uid) else None
        raw: dict[str, Any] = {}
        for name, args in getters:
            key = name if not args else f"{name}({','.join(map(str, args))})"
            method = getattr(item, name, None)
            if not callable(method):
                raw[key] = {
                    "status": "unsupported",
                    "pythonType": None,
                    "value": None,
                    "arguments": list(args),
                }
                continue
            try:
                value = method(*args)
                raw[key] = {
                    "status": "supported",
                    "pythonType": type(value).__name__,
                    "value": _native_value(value),
                    "arguments": list(args),
                }
            except Exception as error:
                raw[key] = {
                    "status": "ambiguous",
                    "pythonType": None,
                    "value": None,
                    "arguments": list(args),
                    "error": {
                        "type": type(error).__name__,
                        "message": str(error)[:500],
                    },
                }
        media_uid: Any = None
        source_uid: Any = None
        with suppress(Exception):
            media = _invoke(item, "GetMediaPoolItem")
            media_uid = _invoke(media, "GetUniqueId")
            getter = getattr(item, "GetMediaId", None)
            if callable(getter):
                source_uid = getter()
        captured.append(
            {
                "timelineItemUid": uid,
                "sourceUID": _native_value(source_uid),
                "mediaUID": _native_value(media_uid),
                "rawGetters": raw,
            }
        )
    return {"stage": stage, "items": captured}


def _numeric_getter(item: dict[str, Any], key: str) -> int | float:
    raw_value = item.get("rawGetters")
    _require(type(raw_value) is dict, f"missing {key}")
    raw = cast(dict[str, Any], raw_value)
    row_value = raw.get(key)
    _require(type(row_value) is dict, f"missing {key}")
    row = cast(dict[str, Any], row_value)
    value = row.get("value")
    _require(
        row.get("status") == "supported"
        and row.get("pythonType") in {"int", "float"}
        and type(value) in {int, float}
        and type(value).__name__ == row.get("pythonType"),
        f"{key} is not a raw finite numeric getter",
    )
    number = cast(int | float, value)
    _require(math.isfinite(number), f"{key} is not finite")
    return number


def _calibrate_baseline(
    before: dict[str, Any], after: dict[str, Any]
) -> dict[str, Any]:
    """Derive AppendToTimeline end semantics from the persisted control clip."""
    before_items = before.get("items")
    after_items = after.get("items")
    if not (
        before.get("stage") == "baseline"
        and after.get("stage") == "baseline_after_reopen"
        and type(before_items) is list
        and type(after_items) is list
        and len(before_items) == len(after_items) == 1
    ):
        raise ValueError("baseline calibration snapshots are incomplete")
    first = before_items[0]
    reopened = after_items[0]
    _require(
        first.get("timelineItemUid") == reopened.get("timelineItemUid"),
        "baseline item identity changed across save/reopen",
    )
    before_duration = _numeric_getter(first, "GetDuration(True)")
    observed_duration = _numeric_getter(reopened, "GetDuration(True)")
    expected_frames = [
        frames
        for frames in (100, 101)
        if abs(before_duration - frames) * PROGRAMME["frameSamples"] < 0.5
        and abs(observed_duration - frames) * PROGRAMME["frameSamples"] < 0.5
    ]
    _require(
        len(expected_frames) == 1,
        "AppendToTimeline baseline end semantics are not uniquely 100 or 101 frames",
    )
    for snapshot_item, duration in (
        (first, before_duration),
        (reopened, observed_duration),
    ):
        start = _numeric_getter(snapshot_item, "GetStart(True)")
        end = _numeric_getter(snapshot_item, "GetEnd(True)")
        _require(
            abs(start) * PROGRAMME["frameSamples"] < 0.5
            and (
                abs((end - start) - duration) * PROGRAMME["frameSamples"] < 0.5
                or abs((end - start + 1) - duration) * PROGRAMME["frameSamples"] < 0.5
            ),
            "baseline raw timeline start/end/duration getters disagree",
        )
    return {
        "inputEndFrame": 100,
        "observedDurationFrames": observed_duration,
        "appendEndFrameAdjustment": -1 if expected_frames[0] == 101 else 0,
    }


def _current_project(manager: Any, target: dict[str, Any]) -> tuple[Any, Any]:
    project = _invoke(manager, "GetCurrentProject")
    timeline = _invoke(project, "GetCurrentTimeline")
    _require(
        _invoke(project, "GetUniqueId") == target["projectUid"]
        and _invoke(project, "GetName") == target["projectName"]
        and _invoke(timeline, "GetUniqueId") == target["timelineUid"]
        and _invoke(timeline, "GetName") == target["timelineName"],
        "reopened target identity differs",
    )
    return project, timeline


def _find_media(pool: Any, expected_uid: str, source_path: str) -> Any:
    """Resolve source afresh after reload; native media handles go stale."""
    root = _invoke(pool, "GetRootFolder")
    pending = [root]
    seen: set[str] = set()
    found: list[Any] = []
    while pending:
        folder = pending.pop()
        folder_uid = _invoke(folder, "GetUniqueId")
        _require(
            type(folder_uid) is str and folder_uid not in seen and len(seen) < 64,
            "source media folder inventory is invalid",
        )
        seen.add(folder_uid)
        clips = _invoke(folder, "GetClipList")
        children = _invoke(folder, "GetSubFolderList")
        _require(
            type(clips) in {list, tuple} and type(children) in {list, tuple},
            "source media pool inventory is unreadable",
        )
        for item in clips:
            if _invoke(item, "GetUniqueId") == expected_uid:
                found.append(item)
        pending.extend(children)
    _require(
        len(found) == 1, "imported source UID is absent or duplicated after reopen"
    )
    item = found[0]
    props = _invoke(item, "GetClipProperty")
    _require(
        type(props) is dict
        and props.get("Online Status") == "Online"
        and props.get("File Path") == source_path,
        "reopened media UID no longer binds to the pinned original source",
    )
    return item


def _save_reopen(state: dict[str, Any], stage: str) -> tuple[Any, Any]:
    manager, project, _, _ = _context(state["resolve"], state["request"]["target"])
    saved = _journal_effect(state, f"{stage}_save", manager, "SaveProject", [])
    _require(saved is True, f"{stage}: Resolve did not confirm SaveProject")
    closed = _journal_effect(
        state,
        f"{stage}_close",
        manager,
        "CloseProject",
        [_invoke(project, "GetUniqueId")],
        call_arguments=[project],
    )
    _require(closed is True, f"{stage}: Resolve did not confirm CloseProject")
    loaded = _journal_effect(
        state,
        f"{stage}_reopen",
        manager,
        "LoadProject",
        [state["request"]["target"]["projectName"]],
        call_arguments=[state["request"]["target"]["projectName"]],
        current_required=False,
    )
    _require(loaded is not None, f"{stage}: Resolve did not reopen saved project")
    project, timeline = _current_project(manager, state["request"]["target"])
    _assert_target_settings(project, timeline)
    return project, timeline


def _render_settings(output_path: Path) -> dict[str, Any]:
    return {
        "SelectAllFrames": False,
        "MarkIn": 0,
        "MarkOut": 199,
        "TargetDir": str(output_path.parent),
        "CustomName": output_path.stem,
        "UseUniqueFilenames": False,
        "ExportVideo": True,
        "ExportAudio": True,
        "AudioCodec": "lpcm",
        "AudioBitDepth": 24,
        "AudioSampleRate": 48000,
        "FormatWidth": 1920,
        "FormatHeight": 1080,
        "FrameRate": 23.976,
    }


def _job_for(project: Any, job_id: str) -> dict[str, Any]:
    jobs = _invoke(project, "GetRenderJobList")
    _require(type(jobs) in {list, tuple}, "render queue is unreadable")
    matches = [row for row in jobs if type(row) is dict and row.get("JobId") == job_id]
    _require(len(matches) == 1, "exact render job is absent or duplicated")
    return cast(dict[str, Any], matches[0])


def _verify_job(job: dict[str, Any], job_id: str, output_path: Path) -> None:
    _require(
        job.get("JobId") == job_id
        and job.get("TargetDir") == str(output_path.parent)
        and job.get("OutputFilename") == output_path.name
        and job.get("RenderMode") == "Single clip"
        and job.get("IsExportVideo") is True
        and job.get("IsExportAudio") is True
        and job.get("AudioBitDepth") == 24
        and job.get("AudioSampleRate") == 48000
        and ("FrameRate" not in job or job.get("FrameRate") == 23.976)
        and job.get("MarkIn") == 0
        and job.get("MarkOut") == 199
        and job.get("FormatWidth") == 1920
        and job.get("FormatHeight") == 1080
        and job.get("VideoCodec") in {"Apple ProRes 422", "ProRes422"}
        and job.get("AudioCodec") in {"Linear PCM", "lpcm"}
        and job.get("VideoFormat") in {"QuickTime", "mov"},
        "queued job differs from the fixed MOV/ProRes422/PCM profile",
    )
    for key in ("AudioChannels", "AudioChannelCount"):
        if key in job:
            _require(
                job[key] in {2, "2", "Stereo", "stereo"},
                f"queued job {key} is not stereo",
            )
    for key in ("AudioChannelFormat", "AudioChannelLayout"):
        if key in job:
            _require(
                job[key] in {"Stereo", "stereo", "2.0", "L R"},
                f"queued job {key} is not stereo",
            )


def _render(state: dict[str, Any], project: Any, output_path: Path) -> dict[str, Any]:
    _no_symlink_ancestry(output_path.parent)
    output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _require(not output_path.exists(), "probe render output already exists")
    formats = _invoke(project, "GetRenderFormats")
    codecs = _invoke(project, "GetRenderCodecs", "mov")
    audio_codecs = _invoke(project, "GetAudioRenderCodecs", "mov")
    _require(
        type(formats) is dict and formats.get("QuickTime") == "mov",
        "Resolve MOV renderer is unavailable",
    )
    _require(
        type(codecs) is dict and codecs.get("Apple ProRes 422") == "ProRes422",
        "Resolve ProRes422 renderer is unavailable",
    )
    _require(
        type(audio_codecs) is dict and audio_codecs.get("Linear PCM") == "lpcm",
        "Resolve lpcm renderer is unavailable",
    )
    prior_jobs = _invoke(project, "GetRenderJobList")
    _require(
        type(prior_jobs) in {list, tuple} and len(prior_jobs) == 0,
        "render queue changed before probe render",
    )
    _require(
        _invoke(project, "IsRenderingInProgress") is False,
        "render started before probe",
    )

    selected = _journal_effect(
        state,
        "render_select_format",
        project,
        "SetCurrentRenderFormatAndCodec",
        ["mov", "ProRes422"],
    )
    _require(selected is True, "Resolve refused MOV/ProRes422 selection")
    format_codec = _invoke(project, "GetCurrentRenderFormatAndCodec")
    _require(
        format_codec == {"format": "mov", "codec": "ProRes422"},
        "MOV/ProRes422 selection did not read back",
    )

    mode = _journal_effect(
        state, "render_select_single_clip", project, "SetCurrentRenderMode", [1]
    )
    _require(
        mode is True and _invoke(project, "GetCurrentRenderMode") == 1,
        "single-clip render mode did not read back",
    )
    settings = _render_settings(output_path)
    applied = _journal_effect(
        state, "render_set_settings", project, "SetRenderSettings", [settings]
    )
    _require(applied is True, "Resolve refused fixed MOV render settings")
    settings_readback: Any = None
    getter = getattr(project, "GetRenderSettings", None)
    if callable(getter):
        try:
            raw_settings = getter()
            _require(
                type(raw_settings) is dict, "render settings readback is not an object"
            )
            expected = settings
            _require(
                all(raw_settings.get(key) == value for key, value in expected.items()),
                "render settings readback differs from the fixed profile",
            )
            settings_readback = _native_value(raw_settings)
        except Exception as error:
            settings_readback = {"status": "ambiguous", "error": str(error)[:500]}
    else:
        settings_readback = {
            "status": "unsupported",
            "method": "Project.GetRenderSettings",
        }

    job_id = _journal_effect(state, "render_add_job", project, "AddRenderJob", [])
    _require(type(job_id) is str and bool(job_id), "Resolve returned no render job ID")
    job = _job_for(project, job_id)
    render_evidence: dict[str, Any] = {
        "status": "queued_job_unverified",
        "outputPath": str(output_path),
        "jobId": job_id,
        "job": _native_value(job),
        "settings": {"requested": settings, "readback": settings_readback},
        "formatCodec": format_codec,
    }
    state["render"] = render_evidence
    _verify_job(job, job_id, output_path)
    status = _invoke(project, "GetRenderJobStatus", job_id)
    render_evidence["jobStatus"] = _native_value(status)
    _require(
        type(status) is dict and status.get("JobStatus") == "Ready",
        "new render job is not ready",
    )
    _require(not output_path.exists(), "render output appeared before explicit start")

    _context(state["resolve"], state["request"]["target"])
    jobs_before_start = _invoke(project, "GetRenderJobList")
    _require(
        type(jobs_before_start) in {list, tuple} and len(jobs_before_start) == 1,
        "render queue changed before exact-job start",
    )
    job = _job_for(project, job_id)
    _verify_job(job, job_id, output_path)
    render_evidence["job"] = _native_value(job)
    status = _invoke(project, "GetRenderJobStatus", job_id)
    _require(
        type(status) is dict and status.get("JobStatus") == "Ready",
        "new render job changed before start",
    )
    render_evidence["jobStatus"] = _native_value(status)
    started = _journal_effect(
        state, "render_start_exact_job", project, "StartRendering", [[job_id]]
    )
    _require(started is True, "Resolve refused the exact render job")
    render_evidence["status"] = "rendering_exact_job"
    deadline = time.monotonic() + RENDER_TIMEOUT_SECONDS
    last_status: Any = None
    while time.monotonic() < deadline:
        _check_live_window(state["request"])
        _context(state["resolve"], state["request"]["target"])
        last_status = _invoke(project, "GetRenderJobStatus", job_id)
        _require(
            type(last_status) is dict and type(last_status.get("JobStatus")) is str,
            "render status is unreadable",
        )
        state["renderStatus"] = _native_value(last_status)
        render_evidence["jobStatus"] = _native_value(last_status)
        if last_status["JobStatus"] in {"Complete", "Failed", "Cancelled"}:
            break
        time.sleep(0.5)
    else:
        _context(state["resolve"], state["request"]["target"])
        last_status = _invoke(project, "GetRenderJobStatus", job_id)
        _require(
            type(last_status) is dict and type(last_status.get("JobStatus")) is str,
            "render status is unreadable after timeout",
        )
        render_evidence["jobStatus"] = _native_value(last_status)
        final_job = _job_for(project, job_id)
        _verify_job(final_job, job_id, output_path)
        still_rendering = _invoke(project, "IsRenderingInProgress") is True
        render_evidence.update(
            status=(
                "active_timeout_retained"
                if still_rendering or last_status["JobStatus"] == "Rendering"
                else "timeout_job_retained"
            ),
            job=_native_value(final_job),
            jobStatus=_native_value(last_status),
        )
        raise ValueError(
            "exact render job did not reach a terminal state within 180 seconds"
        )
    final_job = _job_for(project, job_id)
    _verify_job(final_job, job_id, output_path)
    _require(
        last_status["JobStatus"] == "Complete",
        f"native render ended {last_status['JobStatus']}",
    )
    data = _read(output_path, limit=512 * 1024 * 1024)
    return {
        "status": "rendered_for_pcm_verification",
        "outputPath": str(output_path),
        "sha256": _sha(data),
        "jobId": job_id,
        "job": _native_value(final_job),
        "settings": {"requested": settings, "readback": settings_readback},
        "formatCodec": format_codec,
        "jobStatus": _native_value(last_status),
    }


def run_sample_precision_probe(
    resolve: Any,
    request_path: Path,
    *,
    expected_request_sha256: str,
) -> Path:
    """Run one finite baseline/lift/save/reopen/render experiment on one target."""
    request_path = Path(request_path)
    request_sha = _hash(expected_request_sha256, "request hash")
    installed_request_bytes = _read(request_path)
    _require(
        _sha(installed_request_bytes) == request_sha,
        "installed sample-precision request differs from caller pin",
    )
    request = load_probe_request(request_path, request_sha)
    host_request_path = Path(request["outputDir"]) / "request.json"
    host_request_bytes = _read(host_request_path)
    host_request_sha = _sha(host_request_bytes)
    _require(
        host_request_bytes == installed_request_bytes
        and host_request_sha == request_sha,
        "installed request differs from canonical host request",
    )
    release_root = Path(request["releaseRoot"])
    _require(
        _verify_release(release_root, request["releaseSha256"])
        == request["releaseSha256"],
        "precision release drift",
    )
    installed_root = Path(__file__).absolute().parents[3]
    _require(
        _verify_release(installed_root, request["releaseSha256"], installed=True)
        == request["releaseSha256"],
        "currently imported precision runtime differs from the request-pinned install",
    )
    pcm_sha, sample_count = _validate_source(Path(request["sourcePath"]))
    marker_sha, marker_path = _verify_review(Path(request["reviewPath"]))
    _require(
        _sha(_read(Path(request["reviewPath"]))) == request["reviewSha256"]
        and marker_sha == request["markerSha256"]
        and marker_path == Path(request["markerPath"])
        and pcm_sha == request["sourcePcmSha256"]
        and sample_count == request["sourceSamples"],
        "source or review changed after request preparation",
    )
    _check_live_window(request)
    product = _invoke(resolve, "GetProductName")
    version = _invoke(resolve, "GetVersion")
    _require(
        product == "DaVinci Resolve Studio" and list(version) == [21, 1, 1, 10, ""],
        "unsupported Resolve product/build",
    )
    manager, project, timeline, pool = _context(resolve, request["target"])
    profile_readback = _assert_target_settings(project, timeline)
    empty_readback = _check_empty_target(project, timeline, pool)
    _require(
        all(
            callable(getattr(manager, name, None))
            for name in ("SaveProject", "CloseProject", "LoadProject")
        ),
        "project save/reopen API is unavailable",
    )
    output_dir = Path(request["outputDir"])
    _no_symlink_ancestry(output_dir)
    _require(
        output_dir.is_dir() and not (output_dir / "result.json").exists(),
        "probe evidence directory is unavailable or already used",
    )
    request_bytes = _read(request_path)
    _require(
        request_bytes == installed_request_bytes
        and _sha(request_bytes) == request_sha
        and _read(host_request_path) == host_request_bytes,
        "installed or host sample-precision request changed before native effects",
    )

    target_intent, target_intent_sha = _claim_once(request, request_sha)
    journal_dir = output_dir / "journal"
    journal_dir.mkdir(mode=0o700, exist_ok=False)
    state: dict[str, Any] = {
        "resolve": resolve,
        "request": request,
        "requestSha256": request_sha,
        "journalDir": journal_dir,
        "effects": [],
        "observations": [],
        "render": {"status": "not_started"},
    }
    started_at = _now()
    result_status = "ambiguous"
    failure: dict[str, str] | None = None
    construction: dict[str, Any] = {}
    try:
        # Import original, unmodified source into this dedicated empty project.
        imported = _journal_effect(
            state,
            "import_original_source",
            pool,
            "ImportMedia",
            [[request["sourcePath"]]],
        )
        _require(
            type(imported) in {list, tuple} and len(imported) == 1,
            "Resolve did not import exactly one original source",
        )
        media = imported[0]
        media_uid = _invoke(media, "GetUniqueId")
        _require(
            type(media_uid) is str and bool(media_uid),
            "imported source UID is unreadable",
        )
        properties = _invoke(media, "GetClipProperty")
        _require(
            type(properties) is dict
            and properties.get("Online Status") == "Online"
            and properties.get("File Path") == request["sourcePath"],
            "Resolve imported a different or offline source",
        )
        baseline_info = {
            "mediaPoolItem": media,
            "startFrame": 0.0,
            "endFrame": 100.0,
            "mediaType": 2,
            "trackIndex": 1,
            "recordFrame": 0.0,
        }
        baseline_args = {
            key: (media_uid if key == "mediaPoolItem" else value)
            for key, value in baseline_info.items()
        }
        construction = {"baseline": baseline_args, "status": "baseline_prepared"}
        placed = _journal_effect(
            state,
            "append_baseline",
            pool,
            "AppendToTimeline",
            [[baseline_args]],
            call_arguments=[[baseline_info]],
        )
        _require(
            type(placed) in {list, tuple} and len(placed) == 1,
            "Resolve did not place baseline clip",
        )
        baseline_item_uid = _invoke(placed[0], "GetUniqueId")
        state["observations"].append(_snapshot("baseline", timeline, 1))
        project, timeline = _save_reopen(state, "baseline")
        state["observations"].append(_snapshot("baseline_after_reopen", timeline, 1))
        calibration = _calibrate_baseline(
            state["observations"][0], state["observations"][1]
        )
        construction.update(calibration=calibration, status="baseline_calibrated")
        pool = _invoke(project, "GetMediaPool")
        _validate_source(Path(request["sourcePath"]))
        media = _find_media(pool, media_uid, request["sourcePath"])

        items = _invoke(timeline, "GetItemListInTrack", "audio", 1)
        _require(
            len(items) == 1 and _invoke(items[0], "GetUniqueId") == baseline_item_uid,
            "baseline clip ownership changed before non-ripple delete",
        )
        # Native handles are never put in journal JSON; call only the target
        # timeline's documented non-ripple DeleteClips([TimelineItem], False).
        journal_sequence = len(state["effects"])
        journal_path = (
            journal_dir / f"effect-{journal_sequence + 1:02d}-{uuid.uuid4().hex}.json"
        )
        journal_value = {
            "schemaVersion": "vera-sample-precision-probe-effect/v1",
            "requestSha256": request_sha,
            "target": request["target"],
            "stage": "delete_own_baseline_nonripple",
            "method": "Timeline.DeleteClips",
            "arguments": {
                "timelineItemUids": [baseline_item_uid],
                "rippleDelete": False,
            },
            "preparedAt": _now().isoformat(),
            "status": "prepared_before_native_call",
        }
        _context(resolve, request["target"])
        _check_live_window(request)
        _write_immutable(journal_path, journal_value)
        delete_row = {
            "stage": "delete_own_baseline_nonripple",
            "method": "Timeline.DeleteClips",
            "arguments": journal_value["arguments"],
            "journalPath": str(journal_path),
            "journalSha256": _sha(_read(journal_path)),
            "returnValue": None,
            "status": "ambiguous",
        }
        state["effects"].append(delete_row)
        _context(resolve, request["target"])
        _check_live_window(request)
        delete_result = _invoke(timeline, "DeleteClips", [items[0]], False)
        delete_row.update(returnValue=_native_value(delete_result), status="returned")
        _require(
            delete_result is True,
            "Resolve did not confirm non-ripple baseline deletion",
        )
        _require(
            _invoke(timeline, "GetItemListInTrack", "audio", 1) == [],
            "non-ripple baseline delete did not leave the owned A1 track empty",
        )

        survivors = []
        exact_ranges = ((0, 232320), (241440, 400400))
        for source_start, source_end in exact_ranges:
            start_frame = source_start / PROGRAMME["frameSamples"]
            end_frame = (
                source_end / PROGRAMME["frameSamples"]
                + calibration["appendEndFrameAdjustment"]
            )
            record_frame = start_frame
            survivors.append(
                {
                    "mediaPoolItem": media,
                    "startFrame": start_frame,
                    "endFrame": end_frame,
                    "mediaType": 2,
                    "trackIndex": 1,
                    "recordFrame": record_frame,
                    "sourceStartSample": source_start,
                    "sourceEndSampleExclusive": source_end,
                }
            )
        append_infos = [
            {key: value for key, value in info.items() if not key.startswith("source")}
            for info in survivors
        ]
        append_evidence = {
            "infos": [{**info, "mediaPoolItem": media_uid} for info in append_infos],
            "sourceSampleRanges": [
                {"startSample": start, "endSampleExclusive": end}
                for start, end in exact_ranges
            ],
        }
        lifted = _journal_effect(
            state,
            "append_fractional_survivors",
            pool,
            "AppendToTimeline",
            [append_evidence],
            call_arguments=[append_infos],
        )
        _require(
            type(lifted) in {list, tuple} and len(lifted) == 2,
            "Resolve did not place exactly two survivor clips",
        )
        _require(
            len(_invoke(timeline, "GetItemListInTrack", "audio", 1)) == 2,
            "sample-lift construction has unexpected A1 inventory",
        )
        construction.update(
            {
                "delete": {"timelineItemUid": baseline_item_uid, "rippleDelete": False},
                "survivors": append_evidence,
                "status": "constructed_fractional_arguments",
            }
        )
        state["observations"].append(_snapshot("sample_lift", timeline, 2))
        project, timeline = _save_reopen(state, "sample_lift")
        state["observations"].append(_snapshot("sample_lift_after_reopen", timeline, 2))

        output_path = output_dir / "renders" / f"issue257-{request['requestId']}.mov"
        state["render"] = _render(state, project, output_path)
        post_render = _snapshot("sample_lift_after_render", timeline, 2)
        state["render"]["postRenderObservation"] = post_render
        _require(
            post_render["items"] == state["observations"][-1]["items"],
            "sample-lift geometry changed while the probe render ran",
        )
        result_status = "rendered_for_pcm_verification"
    except Exception as error:
        failure = {"type": type(error).__name__, "message": str(error)[:2000]}
        result_status = "ambiguous" if state["effects"] else "unsupported"
        if not construction:
            construction = {"status": "incomplete"}
        elif construction.get("status") in {
            "baseline_prepared",
            "baseline_calibrated",
        }:
            construction["status"] = "incomplete"
        if state["render"].get("status") == "not_started":
            state["render"] = {"status": "incomplete"}
    finished_at = _now()
    result = {
        "schemaVersion": RESULT_SCHEMA,
        "status": result_status,
        "requestPath": str(request_path),
        "requestSha256": request_sha,
        "hostRequestPath": str(host_request_path),
        "hostRequestSha256": host_request_sha,
        "releaseSha256": request["releaseSha256"],
        "target": request["target"],
        "source": {
            "path": request["sourcePath"],
            "sha256": request["sourceSha256"],
            "pcmSha256": request["sourcePcmSha256"],
            "sampleRate": request["sampleRate"],
            "channels": request["channels"],
            "bitDepth": request["bitDepth"],
            "samples": request["sourceSamples"],
        },
        "review": {
            "path": request["reviewPath"],
            "sha256": request["reviewSha256"],
            "markerPath": request["markerPath"],
            "markerSha256": request["markerSha256"],
        },
        "programme": {
            **PROGRAMME,
            "targetGap": request["targetGap"],
            "supports": request["supports"],
        },
        "profile": request["profile"],
        "oneUseIntentPath": str(target_intent),
        "oneUseIntentSha256": target_intent_sha,
        "startedAt": started_at.isoformat(),
        "finishedAt": finished_at.isoformat(),
        "preflight": {
            "runtimeProduct": product,
            "runtimeVersion": _native_value(version),
            "settings": _native_value(profile_readback),
            "emptyTarget": empty_readback,
        },
        "effects": state["effects"],
        "observations": state["observations"],
        "construction": construction,
        "calibration": construction.get("calibration"),
        "render": state["render"],
        "failure": failure,
    }
    result_path = output_dir / "result.json"
    _write_immutable(result_path, result)
    return result_path
