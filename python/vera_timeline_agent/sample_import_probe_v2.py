"""One-use native Resolve OTIO-import probe for issue #259.

Question: does ``MediaPool.ImportTimelineFromFile`` keep the original WAV's
sample-exact source edges when an OTIO audio track is [0,232320) + Gap +
[241440,400400) at 48 kHz? Issue #257 showed the ``AppendToTimeline`` route
rounds those edges. This probe is separately and explicitly selected (its own
request schema and release inventory), is finite and single-use, and does no
editing: construction is only three ``ImportTimelineFromFile`` calls on OTIO
files the host prepared and hashed, each creating a NEW timeline in the
authorized, otherwise empty disposable target project.

The OTIO file is only a representation of the intended edit. It is not
evidence that Resolve preserved it; only native readback plus a decoded
same-job render can be.

The native half is stdlib-only. ``opentimelineio`` and ffmpeg are imported or
run lazily, host-side, when a request is prepared.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from contextlib import suppress
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

from . import sample_precision_probe_v2 as base

REQUEST_SCHEMA = "vera-sample-import-probe-request/v1"
RESULT_SCHEMA = "vera-sample-import-probe-result/v1"
EFFECT_SCHEMA = "vera-sample-import-probe-effect/v1"
INTENT_SCHEMA = "vera-sample-import-probe-intent/v1"
RENDER_TIMEOUT_SECONDS = 180
PROBE_STATE_ROOT = (
    Path.home() / "Library" / "Application Support" / "VERA" / "sample-import-probe-v1"
)
RELEASE_RUNTIME_FILES = (*base.RELEASE_RUNTIME_FILES, "sample_import_probe_v2.py")

FRAME_SAMPLES = 2002
SOURCE_SAMPLES = 400400
OTIO_RATE = 48000
PICTURE_FRAMES = 200
ROLES = ("control", "calibration", "candidate")
# Off-grid calibration clip: both internal source edges sit half a video frame
# (1001 samples) off the 2002-sample grid; its duration is exactly 50 frames.
OFFGRID_SOURCE = (100100 + 1001, 200200 + 1001)
_PLAN_CLIPS = {
    "control": [(0, SOURCE_SAMPLES, 0)],
    "calibration": [(OFFGRID_SOURCE[0], OFFGRID_SOURCE[1], 0)],
    "candidate": [
        (0, base.TARGET_GAP["startSample"], 0),
        (
            base.TARGET_GAP["endSample"],
            SOURCE_SAMPLES,
            base.TARGET_GAP["endSample"],
        ),
    ],
}
EXTRA_REQUEST_KEYS = {"inputsDir", "picture", "imports"}
REQUEST_KEYS = base.REQUEST_KEYS | EXTRA_REQUEST_KEYS
EFFECT_SEQUENCE = (
    ("import_control", "ImportTimelineFromFile"),
    ("select_control", "SetCurrentTimeline"),
    ("import_calibration", "ImportTimelineFromFile"),
    ("select_calibration", "SetCurrentTimeline"),
    ("import_candidate", "ImportTimelineFromFile"),
    ("select_candidate", "SetCurrentTimeline"),
    ("import_save", "SaveProject"),
    ("import_close", "CloseProject"),
    ("import_reopen", "LoadProject"),
    ("select_control_after_reopen", "SetCurrentTimeline"),
    ("select_calibration_after_reopen", "SetCurrentTimeline"),
    ("select_candidate_after_reopen", "SetCurrentTimeline"),
    ("render_select_format", "SetCurrentRenderFormatAndCodec"),
    ("render_select_single_clip", "SetCurrentRenderMode"),
    ("render_set_settings", "SetRenderSettings"),
    ("render_add_job", "AddRenderJob"),
    ("render_start_exact_job", "StartRendering"),
)
OBSERVATION_STAGES = (
    "control_imported",
    "calibration_imported",
    "candidate_imported",
    "control_after_reopen",
    "calibration_after_reopen",
    "candidate_after_reopen",
)
_GETTERS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("GetStart", (False,)),
    ("GetStart", (True,)),
    ("GetEnd", (False,)),
    ("GetEnd", (True,)),
    ("GetDuration", (False,)),
    ("GetDuration", (True,)),
    ("GetLeftOffset", (False,)),
    ("GetLeftOffset", (True,)),
    ("GetRightOffset", (False,)),
    ("GetRightOffset", (True,)),
    ("GetSourceStartFrame", ()),
    ("GetSourceEndFrame", ()),
    ("GetSourceStartTime", ()),
    ("GetSourceEndTime", ()),
)
_AUDIO_ONLY_GETTERS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("GetSourceAudioChannelMapping", ()),
)


class ProbeStop(ValueError):
    """A retained, explicitly classified end of the finite probe."""

    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


def getter_key(name: str, args: tuple[Any, ...]) -> str:
    return name if not args else f"{name}({','.join(map(str, args))})"


# --------------------------------------------------------------------------
# Deterministic plan, OTIO bytes and the disposable black picture (host side)
# --------------------------------------------------------------------------


def import_plan(role: str, *, with_picture: bool) -> dict[str, Any]:
    """The exact intended audio geometry for one import, in 48 kHz samples."""
    clips = [
        {
            "sourceStart": start,
            "sourceEnd": end,
            "recordStart": record,
            "recordEnd": record + (end - start),
        }
        for start, end, record in _PLAN_CLIPS[role]
    ]
    programme = max(clip["recordEnd"] for clip in clips)
    return {
        "audioClips": clips,
        "programmeSamples": programme,
        "pictureSamples": programme if with_picture else 0,
    }


def expected_imports(
    request_id: str, inputs_dir: Path, *, with_picture: bool
) -> list[dict[str, Any]]:
    return [
        {
            "role": role,
            "timelineName": f"VERA259-{role}-{request_id[:8]}",
            "otioPath": str(inputs_dir / f"{role}.otio"),
            "plan": import_plan(role, with_picture=with_picture),
        }
        for role in ROLES
    ]


def import_options(row: dict[str, Any]) -> dict[str, Any]:
    # Absolute ExternalReference paths: no search path is offered to Resolve.
    return {"timelineName": row["timelineName"], "importSourceClips": True}


def otio_bytes(
    row: dict[str, Any], *, source_path: str, picture_path: str | None
) -> bytes:
    """Host-side OTIO writer; every time is RationalTime(value, 48000)."""
    import opentimelineio as otio  # type: ignore[import-untyped]  # host-only

    def time_(value: int) -> Any:
        return otio.opentime.RationalTime(value, OTIO_RATE)

    def range_(start: int, duration: int) -> Any:
        return otio.opentime.TimeRange(time_(start), time_(duration))

    plan = row["plan"]
    timeline = otio.schema.Timeline(name=row["timelineName"])
    timeline.global_start_time = time_(0)
    if plan["pictureSamples"]:
        if picture_path is None:
            raise ValueError("picture plan requires a picture path")
        video = otio.schema.Track(name="V1", kind=otio.schema.Track.Kind.Video)
        video.append(
            otio.schema.Clip(
                name="black picture control",
                media_reference=otio.schema.ExternalReference(
                    target_url=picture_path,
                    available_range=range_(0, PICTURE_FRAMES * FRAME_SAMPLES),
                ),
                source_range=range_(0, plan["pictureSamples"]),
            )
        )
        timeline.tracks.append(video)
    audio = otio.schema.Track(name="A1", kind=otio.schema.Track.Kind.Audio)
    cursor = 0
    for clip in plan["audioClips"]:
        if clip["recordStart"] > cursor:
            audio.append(
                otio.schema.Gap(source_range=range_(0, clip["recordStart"] - cursor))
            )
        audio.append(
            otio.schema.Clip(
                name="original source",
                media_reference=otio.schema.ExternalReference(
                    target_url=source_path,
                    available_range=range_(0, SOURCE_SAMPLES),
                ),
                source_range=range_(
                    clip["sourceStart"], clip["sourceEnd"] - clip["sourceStart"]
                ),
            )
        )
        cursor = clip["recordEnd"]
    timeline.tracks.append(audio)
    text: str = otio.adapters.write_to_string(timeline, "otio_json")
    return (text if text.endswith("\n") else text + "\n").encode()


def verify_otio_payload(
    payload: bytes, row: dict[str, Any], *, source_path: str, picture_path: str | None
) -> None:
    """Check serialized OTIO times against the plan, independent of the writer.

    Every RationalTime must be a whole-sample value at 48000, the audio track
    must be exactly clip / Gap / clip as planned, and the original-source
    references must name the unmodified WAV with its full available range.
    """

    def stamp(value: Any, label: str) -> int:
        base._require(
            type(value) is dict
            and value.get("OTIO_SCHEMA") == "RationalTime.1"
            and value.get("rate") == float(OTIO_RATE)
            and type(value.get("value")) is float
            and value["value"] == int(value["value"]),
            f"OTIO {label} is not a whole-sample RationalTime at 48000",
        )
        return int(value["value"])

    def span(value: Any, label: str) -> tuple[int, int]:
        base._require(
            type(value) is dict and value.get("OTIO_SCHEMA") == "TimeRange.1",
            f"OTIO {label} is not a TimeRange",
        )
        return stamp(value["start_time"], label), stamp(value["duration"], label)

    def reference(clip: dict[str, Any], expected_path: str) -> None:
        references = clip.get("media_references")
        base._require(type(references) is dict, "OTIO clip has no media reference")
        active = cast(dict[str, Any], references).get(
            clip.get("active_media_reference_key", "")
        )
        base._require(
            type(active) is dict
            and active.get("OTIO_SCHEMA") == "ExternalReference.1"
            and active.get("target_url") == expected_path
            and span(active.get("available_range"), "available range")
            == (0, SOURCE_SAMPLES),
            "OTIO clip does not reference the unmodified original media",
        )

    document = base._json_object(payload)
    base._require(
        document.get("OTIO_SCHEMA") == "Timeline.1"
        and document.get("name") == row["timelineName"]
        and stamp(document.get("global_start_time"), "global start") == 0,
        "OTIO timeline header differs from the plan",
    )
    tracks = {
        child["kind"]: child
        for child in document["tracks"]["children"]
        if type(child) is dict and child.get("OTIO_SCHEMA") == "Track.1"
    }
    plan = row["plan"]
    expected_kinds = {"Audio"} | ({"Video"} if plan["pictureSamples"] else set())
    base._require(set(tracks) == expected_kinds, "OTIO track inventory differs")
    expected_audio: list[tuple[str, int, int]] = []
    cursor = 0
    for clip in plan["audioClips"]:
        if clip["recordStart"] > cursor:
            expected_audio.append(("Gap", 0, clip["recordStart"] - cursor))
        expected_audio.append(
            ("Clip", clip["sourceStart"], clip["sourceEnd"] - clip["sourceStart"])
        )
        cursor = clip["recordEnd"]
    children = tracks["Audio"]["children"]
    base._require(len(children) == len(expected_audio), "OTIO audio children differ")
    for child, (kind, start, duration) in zip(children, expected_audio, strict=True):
        base._require(
            child.get("OTIO_SCHEMA") == f"{kind}.{2 if kind == 'Clip' else 1}"
            and span(child.get("source_range"), kind) == (start, duration),
            f"OTIO audio {kind} range differs from the plan",
        )
        if kind == "Clip":
            reference(child, source_path)
    if plan["pictureSamples"]:
        base._require(picture_path is not None, "picture path is required")
        video = tracks["Video"]["children"]
        base._require(
            len(video) == 1
            and span(video[0].get("source_range"), "picture")
            == (0, plan["pictureSamples"]),
            "OTIO picture range differs from the plan",
        )
        references = video[0]["media_references"]
        active = references[video[0]["active_media_reference_key"]]
        base._require(
            active.get("target_url") == picture_path,
            "OTIO picture does not reference the disposable picture control",
        )


def _write_immutable_bytes(path: Path, payload: bytes) -> Path:
    base._no_symlink_ancestry(path.parent)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".sample-import-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o400)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def generate_black_picture(path: Path) -> None:
    """Generate the disposable 200-frame black ProRes picture control.

    Uses the pinned ffmpeg/ffprobe toolchain of the output decoder. This runs
    host-side at request preparation only; it never touches the source audio.
    """
    from . import qualification_output_decode_v2 as decoder

    toolchain = decoder._verify_toolchain()
    base._no_symlink_ancestry(path.parent)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    command = [
        toolchain.ffmpeg.path,
        "-nostdin",
        "-hide_banner",
        "-v",
        "error",
        "-n",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=1920x1080:r=24000/1001",
        "-frames:v",
        str(PICTURE_FRAMES),
        "-an",
        "-map_metadata",
        "-1",
        "-fflags",
        "+bitexact",
        "-flags:v",
        "+bitexact",
        "-c:v",
        "prores_ks",
        "-profile:v",
        "2",
        "-pix_fmt",
        "yuv422p10le",
        "-f",
        "mov",
        str(path),
    ]
    completed = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        cwd="/",
        env={"LANG": "C", "LC_ALL": "C"},
        timeout=120,
        check=False,
    )
    base._require(completed.returncode == 0, "black picture generation failed")
    raw = decoder._run_bounded(
        decoder._probe_command(str(path)), max_output_bytes=64 * 1024
    )
    stream = next(
        item for item in json.loads(raw)["streams"] if item.get("codec_type") == "video"
    )
    base._require(
        stream.get("codec_name") == "prores"
        and stream.get("width") == 1920
        and stream.get("height") == 1080
        and stream.get("r_frame_rate") == "24000/1001"
        and str(stream.get("nb_read_frames")) == str(PICTURE_FRAMES),
        "generated black picture differs from its fixed profile",
    )
    path.chmod(0o400)


# --------------------------------------------------------------------------
# Request
# --------------------------------------------------------------------------


def _validate_request(request: Any, *, require_live: bool = True) -> dict[str, Any]:
    value = base._closed(request, REQUEST_KEYS, "sample-import request")
    base._require(
        value["schemaVersion"] == REQUEST_SCHEMA, "unsupported sample-import request"
    )
    # Every fixed #257 binding (release, source, review, reviewed supports,
    # programme, profile, target, 30-minute window) is checked by the same code.
    core = {key: value[key] for key in base.REQUEST_KEYS}
    core["schemaVersion"] = base.REQUEST_SCHEMA
    checked = base._validate_request(core, require_live=require_live)
    value.update(
        {key: checked[key] for key in base.REQUEST_KEYS if key != "schemaVersion"}
    )
    request_id = checked["requestId"]
    base._require(
        re.fullmatch(r"[0-9a-f-]{36}", request_id) is not None, "invalid request ID"
    )
    inputs_dir = Path(value["inputsDir"])
    base._no_symlink_ancestry(inputs_dir)
    base._require(
        inputs_dir == PROBE_STATE_ROOT / "inputs" / request_id,
        "import inputs are not under the private probe state root",
    )
    output = Path(value["outputDir"])
    base._require(
        not output.is_relative_to(inputs_dir) and not inputs_dir.is_relative_to(output),
        "probe output overlaps the private import inputs",
    )
    picture = value["picture"]
    with_picture = picture is not None
    if with_picture:
        picture = base._closed(
            picture,
            {"path", "sha256", "frames", "width", "height", "frameRate"},
            "picture control",
        )
        base._hash(picture["sha256"], "picture hash")
        base._require(
            picture["path"] == str(inputs_dir / "black-picture.mov")
            and picture["frames"] == PICTURE_FRAMES
            and picture["width"] == 1920
            and picture["height"] == 1080
            and picture["frameRate"] == "24000/1001",
            "picture control differs from its fixed profile",
        )
    imports = value["imports"]
    base._require(
        type(imports) is list
        and len(imports) == len(ROLES)
        and all(type(row) is dict and "otioSha256" in row for row in imports),
        "invalid import list",
    )
    expected = expected_imports(request_id, inputs_dir, with_picture=with_picture)
    base._require(
        [{k: v for k, v in row.items() if k != "otioSha256"} for row in imports]
        == expected,
        "import plan differs from the fixed experiment",
    )
    for row in imports:
        base._hash(row["otioSha256"], "OTIO hash")
    return value


def load_import_request(
    path: Path, expected_sha256: str, *, require_live: bool = True
) -> dict[str, Any]:
    base._hash(expected_sha256, "expected request hash")
    payload = base._read(path)
    base._require(
        base._sha(payload) == expected_sha256, "sample-import request changed"
    )
    return _validate_request(base._json_object(payload), require_live=require_live)


def render_output_path(request: dict[str, Any]) -> Path:
    return (
        Path(request["outputDir"]) / "renders" / f"issue259-{request['requestId']}.mov"
    )


def prepare_import_request(
    *,
    release_root: Path,
    output: Path,
    source: Path,
    review: Path,
    target: dict[str, str],
    producer_authorization: str,
    task_id: str,
    with_picture: bool = False,
) -> Path:
    """Create the one-use request, its OTIO files and optional picture control."""
    release_root = Path(os.path.abspath(release_root))
    source = Path(os.path.abspath(source))
    review = Path(os.path.abspath(review))
    output = Path(os.path.abspath(output))
    for path in (release_root, source, review, output):
        base._no_symlink_ancestry(path)
    base._require(
        type(target) is dict and set(target) == base.TARGET_KEYS,
        "invalid target identity",
    )
    target = {key: base._text(target[key], key) for key in sorted(base.TARGET_KEYS)}
    producer_authorization = base._text(
        producer_authorization, "producer authorization", limit=4096
    )
    task_id = base._text(task_id, "task ID", limit=256)
    release_sha = base._verify_release(
        release_root, runtime_files=RELEASE_RUNTIME_FILES
    )
    source_pcm_sha, sample_count = base._validate_source(source)
    review_sha = base._sha(base._read(review))
    marker_sha, marker_path = base._verify_review(review)
    base._require(
        review_sha == base.REVIEW_SHA256
        and source_pcm_sha == base.SOURCE_PCM_SHA256
        and sample_count == SOURCE_SAMPLES,
        "source review does not match pinned source",
    )
    protected = (release_root, source, review, marker_path)
    base._require(
        all(
            not output.is_relative_to(path) and not path.is_relative_to(output)
            for path in protected
        ),
        "probe output overlaps release or reviewed input",
    )
    request_id = str(uuid.uuid4())
    inputs_dir = PROBE_STATE_ROOT / "inputs" / request_id
    base._no_symlink_ancestry(Path(os.path.abspath(inputs_dir.parent)))
    now = base._now()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    inputs_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    picture: dict[str, Any] | None = None
    if with_picture:
        picture_path = inputs_dir / "black-picture.mov"
        generate_black_picture(picture_path)
        picture = {
            "path": str(picture_path),
            "sha256": base._sha(base._read(picture_path, limit=512 * 1024 * 1024)),
            "frames": PICTURE_FRAMES,
            "width": 1920,
            "height": 1080,
            "frameRate": "24000/1001",
        }
    imports = []
    for row in expected_imports(request_id, inputs_dir, with_picture=with_picture):
        payload = otio_bytes(
            row,
            source_path=str(source),
            picture_path=None if picture is None else picture["path"],
        )
        _write_immutable_bytes(Path(row["otioPath"]), payload)
        imports.append({**row, "otioSha256": base._sha(payload)})
    value = {
        "schemaVersion": REQUEST_SCHEMA,
        "requestId": request_id,
        "releaseRoot": str(release_root),
        "releaseSha256": release_sha,
        "outputDir": str(output),
        "sourcePath": str(source),
        "sourceSha256": base.SOURCE_SHA256,
        "sourcePcmSha256": source_pcm_sha,
        "reviewPath": str(review),
        "reviewSha256": review_sha,
        "markerPath": str(marker_path),
        "markerSha256": marker_sha,
        **base.PROGRAMME,
        "targetGap": dict(base.TARGET_GAP),
        "supports": base.SUPPORTS,
        "profile": dict(base.PROFILE),
        "target": target,
        "taskId": task_id,
        "producerAuthorization": producer_authorization,
        "issuedAt": now.isoformat(),
        "expiresAt": (now + timedelta(seconds=base.AUTHORIZATION_SECONDS)).isoformat(),
        "inputsDir": str(inputs_dir),
        "picture": picture,
        "imports": imports,
    }
    _validate_request(value)
    return base._write_immutable(output / "request.json", value)


# --------------------------------------------------------------------------
# Native helpers
# --------------------------------------------------------------------------


def _claim_once(request: dict[str, Any], request_sha: str) -> tuple[Path, str]:
    identity = "\0".join(
        (request["target"]["projectUid"], request["target"]["timelineUid"])
    )
    intent_root = PROBE_STATE_ROOT / "intents"
    base._no_symlink_ancestry(Path(os.path.abspath(intent_root)))
    target_path = intent_root / f"target-{base._sha(identity.encode())}.json"
    invocation_path = intent_root / f"request-{request_sha}.json"
    record = {
        "schemaVersion": INTENT_SCHEMA,
        "requestSha256": request_sha,
        "target": request["target"],
        "claimedAt": base._now().isoformat(),
    }
    base._write_immutable(target_path, record)
    # Retain target ownership if invocation publication is uncertain.
    base._write_immutable(invocation_path, record)
    return target_path, base._sha(base._read(target_path))


def _project_context(state: dict[str, Any]) -> tuple[Any, Any]:
    target = state["request"]["target"]
    manager = base._invoke(state["resolve"], "GetProjectManager")
    project = base._invoke(manager, "GetCurrentProject")
    base._require(
        base._invoke(project, "GetUniqueId") == target["projectUid"]
        and base._invoke(project, "GetName") == target["projectName"],
        "current Resolve project differs from the explicitly authorized target",
    )
    expected = state["currentTimelineUid"]
    if expected is not None:
        base._require(
            base._invoke(base._invoke(project, "GetCurrentTimeline"), "GetUniqueId")
            == expected,
            "current Resolve timeline differs from the probe's expected timeline",
        )
    return manager, project


def _journal(
    state: dict[str, Any],
    stage: str,
    owner: Any,
    method: str,
    arguments: Any,
    *,
    call_arguments: list[Any] | None = None,
    project_required: bool = True,
) -> Any:
    request = state["request"]
    position = len(state["effects"])
    base._require(
        position < len(EFFECT_SEQUENCE)
        and EFFECT_SEQUENCE[position] == (stage, method),
        "native effect order deviates from the fixed experiment",
    )
    base._require(
        project_required or method == "LoadProject",
        "only the authorized named-project reopen may run without project context",
    )
    if project_required:
        _project_context(state)
    base._check_live_window(request)
    journal_path = (
        state["journalDir"] / f"effect-{position + 1:02d}-{uuid.uuid4().hex}.json"
    )
    base._write_immutable(
        journal_path,
        {
            "schemaVersion": EFFECT_SCHEMA,
            "requestSha256": state["requestSha256"],
            "target": request["target"],
            "stage": stage,
            "method": method,
            "arguments": arguments,
            "preparedAt": base._now().isoformat(),
            "status": "prepared_before_native_call",
        },
    )
    row = {
        "stage": stage,
        "method": method,
        "arguments": arguments,
        "journalPath": str(journal_path),
        "journalSha256": base._sha(base._read(journal_path)),
        "returnValue": None,
        "status": "ambiguous",
    }
    state["effects"].append(row)
    try:
        if project_required:
            _project_context(state)
        base._check_live_window(request)
        value = base._invoke(
            owner, method, *(arguments if call_arguments is None else call_arguments)
        )
        row["returnValue"] = base._native_value(value)
        row["status"] = "returned"
        return value
    except Exception as error:
        row["error"] = {"type": type(error).__name__, "message": str(error)[:1000]}
        raise


def _safe(owner: Any, method: str, *args: Any) -> dict[str, Any]:
    function = getattr(owner, method, None)
    if not callable(function):
        return {"status": "unsupported", "pythonType": None, "value": None}
    try:
        value = function(*args)
    except Exception as error:
        return {
            "status": "ambiguous",
            "pythonType": None,
            "value": None,
            "error": {"type": type(error).__name__, "message": str(error)[:500]},
        }
    return {
        "status": "supported",
        "pythonType": type(value).__name__,
        "value": base._native_value(value),
    }


def _supported(row: dict[str, Any]) -> Any:
    return row["value"] if row["status"] == "supported" else None


def _timeline_identity(timeline: Any) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "uid": _safe(timeline, "GetUniqueId"),
        "name": _safe(timeline, "GetName"),
        "startFrame": _safe(timeline, "GetStartFrame"),
        "startTimecode": _safe(timeline, "GetStartTimecode"),
        "frameRate": _safe(timeline, "GetSetting", "timelineFrameRate"),
        "width": _safe(timeline, "GetSetting", "timelineResolutionWidth"),
        "height": _safe(timeline, "GetSetting", "timelineResolutionHeight"),
        "audioTrackCount": _safe(timeline, "GetTrackCount", "audio"),
        "videoTrackCount": _safe(timeline, "GetTrackCount", "video"),
    }
    return identity


def _item_row(item: Any, *, audio: bool) -> dict[str, Any]:
    uid = _safe(item, "GetUniqueId")
    media_uid: Any = None
    media_path: Any = None
    online: Any = None
    with suppress(Exception):
        media = base._invoke(item, "GetMediaPoolItem")
        media_uid = base._invoke(media, "GetUniqueId")
        properties = base._invoke(media, "GetClipProperty")
        if type(properties) is dict:
            media_path = properties.get("File Path")
            online = properties.get("Online Status")
    raw: dict[str, Any] = {}
    names = (*_GETTERS, *(_AUDIO_ONLY_GETTERS if audio else ()))
    for name, args in names:
        row = _safe(item, name, *args)
        row["arguments"] = list(args)
        raw[getter_key(name, args)] = row
    return {
        "timelineItemUid": _supported(uid),
        "mediaUID": base._native_value(media_uid),
        "mediaFilePath": media_path,
        "mediaOnlineStatus": online,
        "rawGetters": raw,
    }


def _observe(stage: str, role: str, timeline: Any) -> dict[str, Any]:
    identity = _timeline_identity(timeline)
    tracks: dict[str, list[dict[str, Any]]] = {}
    for kind in ("audio", "video"):
        count = _supported(identity[f"{kind}TrackCount"])
        count = count if type(count) is int and 0 <= count <= 16 else 0
        rows = []
        for index in range(1, count + 1):
            listed: list[Any] = []
            listing = "ambiguous"
            with suppress(Exception):
                listed = list(base._invoke(timeline, "GetItemListInTrack", kind, index))
                listing = "supported"
            rows.append(
                {
                    "index": index,
                    "subType": (
                        _safe(timeline, "GetTrackSubType", kind, index)
                        if kind == "audio"
                        else None
                    ),
                    "listing": listing,
                    "items": [
                        _item_row(item, audio=kind == "audio") for item in listed
                    ],
                }
            )
        tracks[kind] = rows
    return {"stage": stage, "role": role, "timeline": identity, "tracks": tracks}


def _pin_identity(identity: dict[str, Any], expected_name: str, known: set[str]) -> str:
    uid = _supported(identity["uid"])
    if type(uid) is not str or not uid or _supported(identity["name"]) != expected_name:
        raise ProbeStop("ambiguous", "imported timeline name/UID did not read back")
    if uid in known:
        raise ProbeStop("ambiguous", "import did not create a new timeline")
    frame_rate = _supported(identity["frameRate"])
    start = _supported(identity["startFrame"])
    if str(frame_rate) != "23.976" or start != 0:
        raise ProbeStop(
            "unsupported",
            f"imported timeline is not 23.976 fps from frame 0 "
            f"(frameRate={frame_rate!r}, startFrame={start!r})",
        )
    return uid


def _find_timeline(project: Any, uid: str) -> Any:
    count = base._invoke(project, "GetTimelineCount")
    base._require(type(count) is int and 0 < count <= 64, "timeline count unreadable")
    found = [
        timeline
        for index in range(1, count + 1)
        if (timeline := base._invoke(project, "GetTimelineByIndex", index)) is not None
        and base._invoke(timeline, "GetUniqueId") == uid
    ]
    base._require(len(found) == 1, "pinned timeline is absent or duplicated")
    return found[0]


def _timeline_inventory(project: Any) -> list[dict[str, Any]]:
    count = base._invoke(project, "GetTimelineCount")
    base._require(type(count) is int and 0 < count <= 64, "timeline count unreadable")
    rows = []
    for index in range(1, count + 1):
        timeline = base._invoke(project, "GetTimelineByIndex", index)
        rows.append(
            {
                "uid": base._invoke(timeline, "GetUniqueId"),
                "name": base._invoke(timeline, "GetName"),
            }
        )
    return rows


def _check_target(
    manager: Any, project: Any, timeline: Any, pool: Any
) -> dict[str, Any]:
    """The authorized disposable target must be empty before any import."""
    base._require(
        base._invoke(timeline, "GetMarkers") == {}, "target timeline has markers"
    )
    counts: dict[str, int] = {}
    for kind in ("video", "audio", "subtitle"):
        count = base._invoke(timeline, "GetTrackCount", kind)
        base._require(type(count) is int and 0 <= count <= 32, "track inventory")
        counts[kind] = count
        for index in range(1, count + 1):
            items = base._invoke(timeline, "GetItemListInTrack", kind, index)
            base._require(
                type(items) in {list, tuple} and len(items) == 0,
                "target timeline is not empty",
            )
    inventory = _timeline_inventory(project)
    base._require(
        len(inventory) == 1
        and inventory[0]["uid"] == base._invoke(timeline, "GetUniqueId"),
        "target project holds timelines other than the authorized empty one",
    )
    root = base._invoke(pool, "GetRootFolder")
    media_items = base._invoke(root, "GetClipList")
    folders = base._invoke(root, "GetSubFolderList")
    timeline_media = base._invoke(timeline, "GetMediaPoolItem")
    base._require(
        type(media_items) in {list, tuple}
        and len(media_items) == 1
        and base._invoke(media_items[0], "GetUniqueId")
        == base._invoke(timeline_media, "GetUniqueId")
        and type(folders) in {list, tuple}
        and len(folders) == 0,
        "target media pool contains media other than its empty timeline",
    )
    base._require(
        base._invoke(project, "IsRenderingInProgress") is False,
        "Resolve is currently rendering",
    )
    jobs = base._invoke(project, "GetRenderJobList")
    base._require(
        type(jobs) in {list, tuple} and len(jobs) == 0,
        "target render queue is not empty",
    )
    base._require(
        callable(getattr(pool, "ImportTimelineFromFile", None))
        and all(
            callable(getattr(project, name, None))
            for name in (
                "GetTimelineCount",
                "GetTimelineByIndex",
                "SetCurrentTimeline",
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
        )
        and all(
            callable(getattr(manager, name, None))
            for name in ("SaveProject", "CloseProject", "LoadProject")
        ),
        "required import, reopen or bounded render API is unavailable",
    )
    base._require(
        base._invoke(project, "GetRenderFormats").get("QuickTime") == "mov"
        and base._invoke(project, "GetRenderCodecs", "mov").get("Apple ProRes 422")
        == "ProRes422"
        and base._invoke(project, "GetAudioRenderCodecs", "mov").get("Linear PCM")
        == "lpcm",
        "Resolve lacks the fixed MOV/ProRes422/lpcm render profile",
    )
    return {
        "trackCounts": counts,
        "timelines": inventory,
        "renderQueue": list(jobs),
        "markers": {},
    }


def _verify_inputs(request: dict[str, Any]) -> dict[str, Any]:
    """Re-hash the host-prepared OTIO files and picture; no native write."""
    record: dict[str, Any] = {"otio": {}, "picture": None}
    for row in request["imports"]:
        payload = base._read(Path(row["otioPath"]))
        base._require(
            base._sha(payload) == row["otioSha256"], "pinned OTIO file bytes changed"
        )
        record["otio"][row["role"]] = {
            "path": row["otioPath"],
            "sha256": row["otioSha256"],
        }
    picture = request["picture"]
    if picture is not None:
        payload = base._read(Path(picture["path"]), limit=512 * 1024 * 1024)
        base._require(
            base._sha(payload) == picture["sha256"], "pinned picture control changed"
        )
        record["picture"] = {"path": picture["path"], "sha256": picture["sha256"]}
    return record


def _save_reopen(state: dict[str, Any]) -> Any:
    manager, project = _project_context(state)
    target = state["request"]["target"]
    saved = _journal(state, "import_save", manager, "SaveProject", [])
    base._require(saved is True, "Resolve did not confirm SaveProject")
    closed = _journal(
        state,
        "import_close",
        manager,
        "CloseProject",
        [base._invoke(project, "GetUniqueId")],
        call_arguments=[project],
    )
    base._require(closed is True, "Resolve did not confirm CloseProject")
    state["currentTimelineUid"] = None
    loaded = _journal(
        state,
        "import_reopen",
        manager,
        "LoadProject",
        [target["projectName"]],
        call_arguments=[target["projectName"]],
        project_required=False,
    )
    base._require(loaded is not None, "Resolve did not reopen the saved project")
    _, project = _project_context(state)
    return project


def _select(
    state: dict[str, Any], stage: str, project: Any, uid: str, timeline: Any
) -> None:
    selected = _journal(
        state,
        stage,
        project,
        "SetCurrentTimeline",
        [uid],
        call_arguments=[timeline],
    )
    base._require(selected is True, f"{stage}: Resolve refused SetCurrentTimeline")
    state["currentTimelineUid"] = uid
    _project_context(state)


def _render(state: dict[str, Any], project: Any, output_path: Path) -> dict[str, Any]:
    request = state["request"]
    base._no_symlink_ancestry(output_path.parent)
    output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    base._require(not output_path.exists(), "probe render output already exists")
    prior_jobs = base._invoke(project, "GetRenderJobList")
    base._require(
        type(prior_jobs) in {list, tuple} and len(prior_jobs) == 0,
        "render queue changed before probe render",
    )
    base._require(
        base._invoke(project, "IsRenderingInProgress") is False,
        "render started before probe",
    )
    selected = _journal(
        state,
        "render_select_format",
        project,
        "SetCurrentRenderFormatAndCodec",
        ["mov", "ProRes422"],
    )
    format_codec = base._invoke(project, "GetCurrentRenderFormatAndCodec")
    base._require(
        selected is True and format_codec == {"format": "mov", "codec": "ProRes422"},
        "MOV/ProRes422 selection did not read back",
    )
    mode = _journal(
        state, "render_select_single_clip", project, "SetCurrentRenderMode", [1]
    )
    base._require(
        mode is True and base._invoke(project, "GetCurrentRenderMode") == 1,
        "single-clip render mode did not read back",
    )
    settings = base._render_settings(output_path)
    applied = _journal(
        state, "render_set_settings", project, "SetRenderSettings", [settings]
    )
    base._require(applied is True, "Resolve refused fixed MOV render settings")
    settings_readback: Any
    getter = getattr(project, "GetRenderSettings", None)
    if callable(getter):
        try:
            raw_settings = getter()
            base._require(
                type(raw_settings) is dict
                and all(raw_settings.get(k) == v for k, v in settings.items()),
                "render settings readback differs from the fixed profile",
            )
            settings_readback = base._native_value(raw_settings)
        except Exception as error:
            settings_readback = {
                "status": "ambiguous",
                "method": "Project.GetRenderSettings",
                "error": str(error)[:500],
            }
    else:
        settings_readback = {
            "status": "unsupported",
            "method": "Project.GetRenderSettings",
        }
    evidence: dict[str, Any] = {
        "status": "queue_attempted",
        "outputPath": str(output_path),
        "settings": {"requested": settings, "readback": settings_readback},
        "formatCodec": format_codec,
    }
    state["render"] = evidence
    job_id = _journal(state, "render_add_job", project, "AddRenderJob", [])
    if type(job_id) is not str or not job_id:
        # Explicit limited outcome. The cause is not assumed; the queue is
        # recorded and left exactly as found (never deleted or broadened).
        queue = base._invoke(project, "GetRenderJobList")
        evidence.update(
            status="add_render_job_returned_no_job",
            jobId=None,
            addRenderJobReturn=base._native_value(job_id),
            queueAfterAttempt=base._native_value(queue),
            renderInProgress=base._native_value(
                base._invoke(project, "IsRenderingInProgress")
            ),
        )
        raise ProbeStop("render_limited", "Resolve returned no render job ID")
    job = base._job_for(project, job_id)
    evidence.update(
        status="queued_job_unverified", jobId=job_id, job=base._native_value(job)
    )
    base._verify_job(job, job_id, output_path)
    status = base._invoke(project, "GetRenderJobStatus", job_id)
    evidence["jobStatus"] = base._native_value(status)
    base._require(
        type(status) is dict and status.get("JobStatus") == "Ready",
        "new render job is not ready",
    )
    base._require(not output_path.exists(), "render output appeared before start")
    jobs_before_start = base._invoke(project, "GetRenderJobList")
    base._require(
        type(jobs_before_start) in {list, tuple} and len(jobs_before_start) == 1,
        "render queue changed before exact-job start",
    )
    job = base._job_for(project, job_id)
    base._verify_job(job, job_id, output_path)
    evidence["job"] = base._native_value(job)
    started = _journal(
        state, "render_start_exact_job", project, "StartRendering", [[job_id]]
    )
    base._require(started is True, "Resolve refused the exact render job")
    evidence["status"] = "rendering_exact_job"
    deadline = time.monotonic() + RENDER_TIMEOUT_SECONDS
    last_status: Any = None
    while time.monotonic() < deadline:
        base._check_live_window(request)
        _project_context(state)
        last_status = base._invoke(project, "GetRenderJobStatus", job_id)
        base._require(
            type(last_status) is dict and type(last_status.get("JobStatus")) is str,
            "render status is unreadable",
        )
        evidence["jobStatus"] = base._native_value(last_status)
        if last_status["JobStatus"] in {"Complete", "Failed", "Cancelled"}:
            break
        time.sleep(0.5)
    else:
        last_status = base._invoke(project, "GetRenderJobStatus", job_id)
        base._require(
            type(last_status) is dict and type(last_status.get("JobStatus")) is str,
            "render status is unreadable after timeout",
        )
        final_job = base._job_for(project, job_id)
        base._verify_job(final_job, job_id, output_path)
        evidence.update(
            status=(
                "active_timeout_retained"
                if base._invoke(project, "IsRenderingInProgress") is True
                or last_status["JobStatus"] == "Rendering"
                else "timeout_job_retained"
            ),
            job=base._native_value(final_job),
            jobStatus=base._native_value(last_status),
        )
        raise ValueError(
            "exact render job did not reach a terminal state within 180 seconds"
        )
    final_job = base._job_for(project, job_id)
    base._verify_job(final_job, job_id, output_path)
    base._require(
        last_status["JobStatus"] == "Complete",
        f"native render ended {last_status['JobStatus']}",
    )
    data = base._read(output_path, limit=512 * 1024 * 1024)
    return {
        "status": "rendered_for_pcm_verification",
        "outputPath": str(output_path),
        "sha256": base._sha(data),
        "jobId": job_id,
        "job": base._native_value(final_job),
        "settings": {"requested": settings, "readback": settings_readback},
        "formatCodec": format_codec,
        "jobStatus": base._native_value(last_status),
    }


def run_sample_import_probe(
    resolve: Any, request_path: Path, *, expected_request_sha256: str
) -> Path:
    """Run one finite import/save/reopen/render experiment on one target."""
    request_path = Path(request_path)
    request_sha = base._hash(expected_request_sha256, "request hash")
    installed_bytes = base._read(request_path)
    base._require(
        base._sha(installed_bytes) == request_sha,
        "installed sample-import request differs from caller pin",
    )
    request = load_import_request(request_path, request_sha)
    host_request_path = Path(request["outputDir"]) / "request.json"
    host_bytes = base._read(host_request_path)
    base._require(
        host_bytes == installed_bytes and base._sha(host_bytes) == request_sha,
        "installed request differs from canonical host request",
    )
    release_root = Path(request["releaseRoot"])
    base._require(
        base._verify_release(
            release_root, request["releaseSha256"], runtime_files=RELEASE_RUNTIME_FILES
        )
        == request["releaseSha256"],
        "import release drift",
    )
    installed_root = Path(__file__).absolute().parents[3]
    base._require(
        base._verify_release(
            installed_root,
            request["releaseSha256"],
            installed=True,
            runtime_files=RELEASE_RUNTIME_FILES,
        )
        == request["releaseSha256"],
        "currently imported runtime differs from the request-pinned install",
    )
    source_path = Path(request["sourcePath"])
    pcm_sha, sample_count = base._validate_source(source_path)
    marker_sha, marker_path = base._verify_review(Path(request["reviewPath"]))
    base._require(
        base._sha(base._read(Path(request["reviewPath"]))) == request["reviewSha256"]
        and marker_sha == request["markerSha256"]
        and marker_path == Path(request["markerPath"])
        and pcm_sha == request["sourcePcmSha256"]
        and sample_count == request["sourceSamples"],
        "source or review changed after request preparation",
    )
    inputs_record = _verify_inputs(request)
    base._check_live_window(request)
    product = base._invoke(resolve, "GetProductName")
    version = base._invoke(resolve, "GetVersion")
    base._require(
        product == "DaVinci Resolve Studio" and list(version) == [21, 1, 1, 10, ""],
        "unsupported Resolve product/build",
    )
    target = request["target"]
    manager, project, timeline, pool = base._context(resolve, target)
    settings_readback = base._assert_target_settings(project, timeline)
    empty_readback = _check_target(manager, project, timeline, pool)
    output_dir = Path(request["outputDir"])
    base._no_symlink_ancestry(output_dir)
    base._require(
        output_dir.is_dir() and not (output_dir / "result.json").exists(),
        "probe evidence directory is unavailable or already used",
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
        "currentTimelineUid": target["timelineUid"],
    }
    started_at = base._now()
    result_status = "ambiguous"
    failure: dict[str, str] | None = None
    timelines: dict[str, Any] = {}
    try:
        known_uids = {target["timelineUid"]}
        for row in request["imports"]:
            role = row["role"]
            options = import_options(row)
            before = _timeline_inventory(base._invoke(manager, "GetCurrentProject"))
            imported = _journal(
                state,
                f"import_{role}",
                pool,
                "ImportTimelineFromFile",
                [row["otioPath"], options],
            )
            state["currentTimelineUid"] = None
            if imported is None or imported is False:
                after = _timeline_inventory(_project_context(state)[1])
                raise ProbeStop(
                    "unsupported" if after == before else "ambiguous",
                    "ImportTimelineFromFile returned no timeline"
                    + ("" if after == before else " but the timeline list changed"),
                )
            identity = _timeline_identity(imported)
            uid = _pin_identity(identity, row["timelineName"], known_uids)
            known_uids.add(uid)
            timelines[role] = {
                "uid": uid,
                "name": row["timelineName"],
                "identity": identity,
            }
            _, project = _project_context(state)
            _select(state, f"select_{role}", project, uid, imported)
            state["observations"].append(
                _observe(f"{role}_imported", role, _find_timeline(project, uid))
            )
        project = _save_reopen(state)
        pool = base._invoke(project, "GetMediaPool")
        for role in ROLES:
            uid = timelines[role]["uid"]
            timeline = _find_timeline(project, uid)
            _pin_identity(_timeline_identity(timeline), timelines[role]["name"], set())
            _select(state, f"select_{role}_after_reopen", project, uid, timeline)
            state["observations"].append(
                _observe(f"{role}_after_reopen", role, timeline)
            )
        # Render only the candidate (it is the current timeline after the loop).
        output_path = render_output_path(request)
        state["render"] = _render(state, project, output_path)
        post = _observe(
            "candidate_after_render",
            "candidate",
            _find_timeline(project, timelines["candidate"]["uid"]),
        )
        state["render"]["postRenderObservation"] = post
        reopened = state["observations"][-1]
        base._require(
            post["tracks"] == reopened["tracks"]
            and post["timeline"] == reopened["timeline"],
            "candidate geometry changed while the probe render ran",
        )
        result_status = "rendered_for_pcm_verification"
    except ProbeStop as error:
        failure = {"type": "ProbeStop", "message": str(error)[:2000]}
        result_status = error.status
        if state["render"].get("status") == "not_started":
            state["render"] = {"status": "incomplete"}
    except Exception as error:
        failure = {"type": type(error).__name__, "message": str(error)[:2000]}
        result_status = "ambiguous" if state["effects"] else "unsupported"
        if state["render"].get("status") == "not_started":
            state["render"] = {"status": "incomplete"}
    source_integrity: dict[str, Any]
    try:
        after_sha = base._sha(base._read(source_path, limit=64 * 1024 * 1024))
        source_integrity = {
            "beforeSha256": request["sourceSha256"],
            "afterSha256": after_sha,
            "unchanged": after_sha == request["sourceSha256"],
        }
    except Exception as error:
        source_integrity = {"unchanged": False, "error": str(error)[:500]}
    if source_integrity["unchanged"] is not True:
        result_status = "ambiguous"
    result = {
        "schemaVersion": RESULT_SCHEMA,
        "status": result_status,
        "requestPath": str(request_path),
        "requestSha256": request_sha,
        "hostRequestPath": str(host_request_path),
        "hostRequestSha256": base._sha(host_bytes),
        "releaseSha256": request["releaseSha256"],
        "target": target,
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
            **base.PROGRAMME,
            "targetGap": request["targetGap"],
            "supports": request["supports"],
        },
        "profile": request["profile"],
        "inputs": inputs_record,
        "sourceIntegrity": source_integrity,
        "oneUseIntentPath": str(target_intent),
        "oneUseIntentSha256": target_intent_sha,
        "startedAt": started_at.isoformat(),
        "finishedAt": base._now().isoformat(),
        "preflight": {
            "runtimeProduct": product,
            "runtimeVersion": base._native_value(version),
            "settings": base._native_value(settings_readback),
            "emptyTarget": empty_readback,
        },
        "effects": state["effects"],
        "timelines": timelines,
        "observations": state["observations"],
        "render": state["render"],
        "failure": failure,
    }
    return base._write_immutable(output_dir / "result.json", result)
