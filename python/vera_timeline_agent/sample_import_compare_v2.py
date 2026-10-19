"""Host-side finalizer for the issue #259 native OTIO-import probe.

A "supported" verdict needs BOTH (i) exact native candidate geometry (surviving
source edges 232320 and 241440 and record positions, read back before and after
save/reopen through getter semantics calibrated from the untouched control and
the off-grid calibration import) AND (ii) the same-job decoded PCM matching the
original source with only [232320,241440) exactly zero, under the unchanged
#257 thresholds. Anything rounded, shifted, missing or ambiguous is an explicit
"unsupported" or "ambiguous" verdict with the measured specifics. No fitting,
lag search, gain, padding or resampling is ever applied.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from . import sample_import_probe_v2 as probe
from . import sample_precision_compare_v2 as pcm_base
from . import sample_precision_probe_v2 as native_base

SamplePrecisionCompareError = pcm_base.SamplePrecisionCompareError
_EvidenceError = pcm_base._EvidenceError
FRAME_SAMPLES = probe.FRAME_SAMPLES
SAMPLE_RATE = probe.OTIO_RATE
GAP_START = native_base.TARGET_GAP["startSample"]
GAP_END = native_base.TARGET_GAP["endSample"]
_RESULT_KEYS = {
    "schemaVersion",
    "status",
    "requestPath",
    "requestSha256",
    "hostRequestPath",
    "hostRequestSha256",
    "releaseSha256",
    "target",
    "source",
    "review",
    "programme",
    "profile",
    "inputs",
    "sourceIntegrity",
    "oneUseIntentPath",
    "oneUseIntentSha256",
    "startedAt",
    "finishedAt",
    "preflight",
    "effects",
    "timelines",
    "observations",
    "render",
    "failure",
}
_NATIVE_STATUSES = {
    "rendered_for_pcm_verification",
    "render_limited",
    "unsupported",
    "ambiguous",
}
_TOLERANCE = 0.5
_RECORD_ADJUSTMENTS = (("exclusive", 0), ("inclusive_frame", 1))
_SOURCE_UNITS = (("seconds", SAMPLE_RATE), ("milliseconds", SAMPLE_RATE / 1000))
_SOURCE_ENDPOINTS = (
    ("exclusive", 0),
    ("inclusive_sample", 1),
    ("inclusive_frame", 2002),
)


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------


def _observations_by_stage(observations: Any) -> dict[str, dict[str, Any]]:
    if type(observations) is not list or len(observations) != len(
        probe.OBSERVATION_STAGES
    ):
        raise _EvidenceError("ambiguous", "native import lifecycle is incomplete")
    stages: dict[str, dict[str, Any]] = {}
    for stage, snapshot in zip(probe.OBSERVATION_STAGES, observations, strict=True):
        if type(snapshot) is not dict or snapshot.get("stage") != stage:
            raise _EvidenceError("ambiguous", "native observation order differs")
        if snapshot.get("role") != stage.split("_", maxsplit=1)[0]:
            raise _EvidenceError("ambiguous", "native observation role differs")
        stages[stage] = snapshot
    return stages


def _identity_value(snapshot: dict[str, Any], key: str) -> Any:
    row = snapshot.get("timeline", {}).get(key)
    if type(row) is not dict or row.get("status") != "supported":
        raise _EvidenceError(
            "ambiguous", f"{snapshot.get('stage')}: timeline {key} is unavailable"
        )
    return row.get("value")


def _check_timeline_identity(stages: dict[str, dict[str, Any]], timelines: Any) -> None:
    for stage, snapshot in stages.items():
        role = snapshot["role"]
        pinned = timelines.get(role) if type(timelines) is dict else None
        if (
            type(pinned) is not dict
            or _identity_value(snapshot, "uid") != pinned.get("uid")
            or _identity_value(snapshot, "name") != pinned.get("name")
        ):
            raise _EvidenceError(
                "ambiguous", f"{stage}: timeline identity differs from its pin"
            )
        if (
            str(_identity_value(snapshot, "frameRate")) != "23.976"
            or _identity_value(snapshot, "startFrame") != 0
        ):
            raise _EvidenceError(
                "unsupported",
                f"{stage}: timeline is not 23.976 fps from frame 0 "
                f"(frameRate={_identity_value(snapshot, 'frameRate')!r}, "
                f"startFrame={_identity_value(snapshot, 'startFrame')!r})",
            )


def _audio_items(
    snapshot: dict[str, Any], clips: list[dict[str, Any]], source_path: str
) -> list[dict[str, Any]]:
    stage = snapshot["stage"]
    tracks = snapshot.get("tracks", {}).get("audio")
    if type(tracks) is not list or len(tracks) != 1:
        raise _EvidenceError(
            "unsupported", f"{stage}: unexpected audio track inventory"
        )
    items = tracks[0].get("items")
    if (
        tracks[0].get("listing") != "supported"
        or type(items) is not list
        or len(items) != len(clips)
    ):
        raise _EvidenceError("unsupported", f"{stage}: unexpected audio item count")
    for item in items:
        if type(item) is not dict:
            raise _EvidenceError("ambiguous", f"{stage}: item row is malformed")
        uid = item.get("timelineItemUid")
        if type(uid) is not str or not uid:
            raise _EvidenceError("unsupported", f"{stage}: item identity is incomplete")
        if item.get("mediaFilePath") != source_path:
            raise _EvidenceError(
                "ambiguous",
                f"{stage}: item media is not proven to be the original source",
            )
    if len({item["timelineItemUid"] for item in items}) != len(items):
        raise _EvidenceError("ambiguous", f"{stage}: duplicate timeline item UIDs")
    return sorted(
        items, key=lambda item: pcm_base._getter_number(item, "GetStart(True)")
    )


def _raw(item: dict[str, Any]) -> dict[str, float]:
    getter = pcm_base._getter_number
    return {
        "startFrames": getter(item, "GetStart(True)"),
        "endFrames": getter(item, "GetEnd(True)"),
        "durationFrames": getter(item, "GetDuration(True)"),
        "sourceStartSeconds": getter(item, "GetSourceStartTime"),
        "sourceEndSeconds": getter(item, "GetSourceEndTime"),
    }


def _measure(
    raw: dict[str, float], clip: dict[str, Any], semantics: dict[str, Any]
) -> dict[str, Any]:
    actual = {
        "recordStart": raw["startFrames"] * FRAME_SAMPLES,
        "recordEndExclusive": (raw["endFrames"] + semantics["recordEndAdjustment"])
        * FRAME_SAMPLES,
        "recordDuration": raw["durationFrames"] * FRAME_SAMPLES,
        "sourceStart": raw["sourceStartSeconds"] * semantics["sourceScale"],
        "sourceEndExclusive": raw["sourceEndSeconds"] * semantics["sourceScale"]
        + semantics["sourceEndAdjustment"],
    }
    expected = {
        "recordStart": clip["recordStart"],
        "recordEndExclusive": clip["recordEnd"],
        "recordDuration": clip["recordEnd"] - clip["recordStart"],
        "sourceStart": clip["sourceStart"],
        "sourceEndExclusive": clip["sourceEnd"],
    }
    errors = {key: actual[key] - expected[key] for key in expected}
    return {
        "expected": expected,
        "actual": actual,
        "errorsSamples": errors,
        "pass": all(abs(error) < _TOLERANCE for error in errors.values()),
    }


def _semantics_space() -> list[dict[str, Any]]:
    return [
        {
            "recordEndEndpoint": record_name,
            "recordEndAdjustment": record_adjustment,
            "sourceUnit": unit,
            "sourceScale": scale,
            "sourceEndEndpoint": endpoint,
            "sourceEndAdjustment": source_adjustment,
        }
        for record_name, record_adjustment in _RECORD_ADJUSTMENTS
        for unit, scale in _SOURCE_UNITS
        for endpoint, source_adjustment in _SOURCE_ENDPOINTS
    ]


def _semantics_label(semantics: dict[str, Any]) -> dict[str, Any]:
    return {
        key: semantics[key]
        for key in ("recordEndEndpoint", "sourceUnit", "sourceEndEndpoint")
    }


def analyze_geometry(
    observations: Any, timelines: Any, imports: list[dict[str, Any]], source_path: str
) -> dict[str, Any]:
    """Interpret getters only through semantics calibrated from the controls."""
    try:
        stages = _observations_by_stage(observations)
        _check_timeline_identity(stages, timelines)
        plans = {row["role"]: row["plan"]["audioClips"] for row in imports}
        raws: dict[str, list[dict[str, Any]]] = {}
        uids: dict[str, list[str]] = {}
        for stage, snapshot in stages.items():
            items = _audio_items(snapshot, plans[snapshot["role"]], source_path)
            raws[stage] = [_raw(item) for item in items]
            uids[stage] = [item["timelineItemUid"] for item in items]
        for role in probe.ROLES:
            if uids[f"{role}_imported"] != uids[f"{role}_after_reopen"]:
                raise _EvidenceError(
                    "ambiguous", f"{role}: timeline item UIDs changed after reopen"
                )
    except _EvidenceError as error:
        return {"status": error.status, "reason": str(error)}

    def stage_rows(
        role: str, semantics: dict[str, Any]
    ) -> dict[str, list[dict[str, Any]]]:
        return {
            stage: [
                _measure(raw, clip, semantics)
                for raw, clip in zip(raws[stage], plans[role], strict=True)
            ]
            for stage in (f"{role}_imported", f"{role}_after_reopen")
        }

    def all_pass(rows: dict[str, list[dict[str, Any]]]) -> bool:
        return all(row["pass"] for measured in rows.values() for row in measured)

    control_candidates = [
        semantics
        for semantics in _semantics_space()
        if all_pass(stage_rows("control", semantics))
    ]
    if len(control_candidates) != 1:
        return {
            "status": "ambiguous",
            "reason": (
                "getter endpoint semantics are not uniquely calibrated by the "
                f"untouched control ({len(control_candidates)} candidates)"
            ),
            "rawGetterValues": raws,
        }
    semantics = control_candidates[0]
    calibration = stage_rows("calibration", semantics)
    candidate = stage_rows("candidate", semantics)
    calibration_exact = all_pass(calibration)
    candidate_exact = all_pass(candidate)
    if candidate_exact and calibration_exact:
        status, reason = "pass", None
    elif calibration_exact:
        status, reason = (
            "mismatch",
            "candidate source/record edges differ although the off-grid "
            "calibration reads back exactly (import quantization or shift)",
        )
    elif candidate_exact:
        status, reason = (
            "ambiguous",
            "candidate reads exact but the off-grid calibration does not",
        )
    else:
        status, reason = (
            "ambiguous",
            "off-grid calibration and candidate both differ: getter versus "
            "import quantization are not separable",
        )
    return {
        "status": status,
        "reason": reason,
        "semantics": _semantics_label(semantics),
        "calibrationOffGridExact": calibration_exact,
        "candidateExact": candidate_exact,
        "controlChecks": stage_rows("control", semantics),
        "calibrationChecks": calibration,
        "candidateChecks": candidate,
        "rawGetterValues": raws,
    }


# --------------------------------------------------------------------------
# Authentication of the native record
# --------------------------------------------------------------------------


def _current_release(request: dict[str, Any]) -> None:
    from . import workflow_v2_cli
    from .workflow_package import sha256

    root = Path(request["releaseRoot"])
    manifest = workflow_v2_cli._verify_release_files(
        root, workflow_v2_cli.SAMPLE_IMPORT_RUNTIME_FILES
    )
    if sha256(manifest) != request["releaseSha256"]:
        raise SamplePrecisionCompareError("request-pinned release manifest changed")
    if (
        native_base._verify_release(
            root, request["releaseSha256"], runtime_files=probe.RELEASE_RUNTIME_FILES
        )
        != request["releaseSha256"]
    ):
        raise SamplePrecisionCompareError("native import release binding changed")


def _current_inputs(request: dict[str, Any]) -> dict[str, Any]:
    """Re-verify OTIO bytes (hash AND serialized sample times) and the picture."""
    picture = request["picture"]
    picture_path = None if picture is None else picture["path"]
    record: dict[str, Any] = {"otio": {}, "picture": None}
    try:
        for row in request["imports"]:
            payload = pcm_base._read_record(Path(row["otioPath"]), immutable=True)
            if hashlib.sha256(payload).hexdigest() != row["otioSha256"]:
                raise SamplePrecisionCompareError("pinned OTIO file bytes changed")
            probe.verify_otio_payload(
                payload,
                row,
                source_path=request["sourcePath"],
                picture_path=picture_path,
            )
            record["otio"][row["role"]] = {
                "path": row["otioPath"],
                "sha256": row["otioSha256"],
            }
        if picture is not None:
            if pcm_base._file_sha256(Path(picture["path"])) != picture["sha256"]:
                raise SamplePrecisionCompareError("pinned picture control changed")
            record["picture"] = {"path": picture["path"], "sha256": picture["sha256"]}
    except ValueError as error:
        if isinstance(error, SamplePrecisionCompareError):
            raise
        raise SamplePrecisionCompareError(str(error)) from error
    return record


def _verify_result_bindings(
    request: dict[str, Any],
    request_path: Path,
    result: dict[str, Any],
    result_path: Path,
) -> None:
    if (
        set(result) != _RESULT_KEYS
        or result.get("schemaVersion") != probe.RESULT_SCHEMA
    ):
        raise SamplePrecisionCompareError(
            "native result schema or closed shape differs"
        )
    if result.get("status") not in _NATIVE_STATUSES:
        raise SamplePrecisionCompareError("native result status is invalid")
    output_dir = Path(request["outputDir"])
    host_sha = hashlib.sha256(
        pcm_base._read_record(request_path, immutable=True)
    ).hexdigest()
    if (
        request_path != output_dir / "request.json"
        or result_path != output_dir / "result.json"
        or result.get("hostRequestPath") != str(request_path)
        or result.get("hostRequestSha256") != host_sha
        or type(result.get("requestPath")) is not str
        or Path(result["requestPath"]) != pcm_base._INSTALLED_REQUEST_PATH
        or result.get("requestSha256") != host_sha
        or result.get("releaseSha256") != request["releaseSha256"]
        or result.get("target") != request["target"]
        or result.get("source")
        != {
            "path": request["sourcePath"],
            "sha256": request["sourceSha256"],
            "pcmSha256": request["sourcePcmSha256"],
            "sampleRate": request["sampleRate"],
            "channels": request["channels"],
            "bitDepth": request["bitDepth"],
            "samples": request["sourceSamples"],
        }
        or result.get("review")
        != {
            "path": request["reviewPath"],
            "sha256": request["reviewSha256"],
            "markerPath": request["markerPath"],
            "markerSha256": request["markerSha256"],
        }
        or result.get("programme")
        != {
            "frameSamples": request["frameSamples"],
            "sampleRate": request["sampleRate"],
            "channels": request["channels"],
            "bitDepth": request["bitDepth"],
            "sourceSamples": request["sourceSamples"],
            "programmeSamples": request["programmeSamples"],
            "targetGap": request["targetGap"],
            "supports": request["supports"],
        }
        or result.get("profile") != request["profile"]
    ):
        raise SamplePrecisionCompareError("native result does not bind to this request")
    intent_root = probe.PROBE_STATE_ROOT / "intents"
    target_key = hashlib.sha256(
        "\0".join(
            (request["target"]["projectUid"], request["target"]["timelineUid"])
        ).encode()
    ).hexdigest()
    target_intent = intent_root / f"target-{target_key}.json"
    invocation_intent = intent_root / f"request-{result['requestSha256']}.json"
    if result.get("oneUseIntentPath") != str(target_intent):
        raise SamplePrecisionCompareError("native result intent target differs")
    target_bytes = pcm_base._read_record(target_intent, immutable=True)
    invocation_bytes = pcm_base._read_record(invocation_intent, immutable=True)
    target_record = pcm_base._load_json(target_bytes, "target intent")
    if (
        hashlib.sha256(target_bytes).hexdigest() != result.get("oneUseIntentSha256")
        or target_record != pcm_base._load_json(invocation_bytes, "invocation intent")
        or target_record.get("schemaVersion") != probe.INTENT_SCHEMA
        or target_record.get("requestSha256") != result["requestSha256"]
        or target_record.get("target") != request["target"]
    ):
        raise SamplePrecisionCompareError("native one-use intent binding differs")
    expected_inputs = {
        "otio": {
            row["role"]: {"path": row["otioPath"], "sha256": row["otioSha256"]}
            for row in request["imports"]
        },
        "picture": (
            None
            if request["picture"] is None
            else {
                "path": request["picture"]["path"],
                "sha256": request["picture"]["sha256"],
            }
        ),
    }
    if result.get("inputs") != expected_inputs:
        raise SamplePrecisionCompareError(
            "native result inputs differ from the request"
        )


def _verify_effect_journals(
    request: dict[str, Any], result: dict[str, Any], request_sha: str
) -> None:
    effects = result.get("effects")
    sequence = probe.EFFECT_SEQUENCE
    status = result["status"]
    if type(effects) is not list or len(effects) > len(sequence):
        raise SamplePrecisionCompareError("native effect list is malformed")
    if status == "rendered_for_pcm_verification" and len(effects) != len(sequence):
        raise SamplePrecisionCompareError("completed native result is incomplete")
    if status == "render_limited" and len(effects) != len(sequence) - 1:
        raise SamplePrecisionCompareError("limited render result sequence differs")
    timelines = result.get("timelines")
    journal_dir = Path(request["outputDir"]) / "journal"
    seen: set[Path] = set()
    imports = {row["role"]: row for row in request["imports"]}
    for index, row in enumerate(effects):
        stage, method = sequence[index]
        if type(row) is not dict or (row.get("stage"), row.get("method")) != (
            stage,
            method,
        ):
            raise SamplePrecisionCompareError("native effect sequence differs")
        journal_path = Path(row.get("journalPath", ""))
        if (
            journal_path.parent != journal_dir
            or not journal_path.name.startswith(f"effect-{index + 1:02d}-")
            or journal_path in seen
        ):
            raise SamplePrecisionCompareError("native effect journal path differs")
        seen.add(journal_path)
        payload = pcm_base._read_record(journal_path, immutable=True)
        if hashlib.sha256(payload).hexdigest() != row.get("journalSha256"):
            raise SamplePrecisionCompareError("native effect journal hash differs")
        journal = pcm_base._load_json(payload, "native effect journal")
        if (
            set(journal)
            != {
                "schemaVersion",
                "requestSha256",
                "target",
                "stage",
                "method",
                "arguments",
                "preparedAt",
                "status",
            }
            or journal.get("schemaVersion") != probe.EFFECT_SCHEMA
            or journal.get("requestSha256") != request_sha
            or journal.get("target") != result["target"]
            or (journal.get("stage"), journal.get("method")) != (stage, method)
            or journal.get("arguments") != row.get("arguments")
            or journal.get("status") != "prepared_before_native_call"
        ):
            raise SamplePrecisionCompareError("native effect journal content differs")
        arguments = row.get("arguments")
        if method == "ImportTimelineFromFile":
            plan_row = imports[stage.removeprefix("import_")]
            if arguments != [plan_row["otioPath"], probe.import_options(plan_row)]:
                raise SamplePrecisionCompareError(
                    "native import effect differs from the pinned OTIO request"
                )
        elif method == "SetCurrentTimeline":
            role = stage.split("_")[1]
            pinned = timelines.get(role) if type(timelines) is dict else None
            if type(pinned) is not dict or arguments != [pinned.get("uid")]:
                raise SamplePrecisionCompareError(
                    "native timeline selection differs from the pinned UID"
                )
        if (
            status == "rendered_for_pcm_verification"
            and row.get("status") != "returned"
        ):
            raise SamplePrecisionCompareError("completed native effect did not return")
    if status in {"rendered_for_pcm_verification", "render_limited"}:
        render = result.get("render")
        if type(render) is not dict or type(render.get("outputPath")) is not str:
            raise SamplePrecisionCompareError("result has no fixed render path")
        expected_settings = native_base._render_settings(Path(render["outputPath"]))
        names = {row["stage"]: row for row in effects}
        if (
            names["render_select_format"]["arguments"] != ["mov", "ProRes422"]
            or names["render_select_single_clip"]["arguments"] != [1]
            or names["render_set_settings"]["arguments"] != [expected_settings]
            or names["render_add_job"]["arguments"] != []
        ):
            raise SamplePrecisionCompareError("render effects differ from the request")
        if status == "rendered_for_pcm_verification" and names[
            "render_start_exact_job"
        ]["arguments"] != [[render.get("jobId")]]:
            raise SamplePrecisionCompareError("render start effect journal differs")


def _verdict(
    native_status: str,
    geometry: dict[str, Any],
    pcm: dict[str, Any],
    *,
    source_unchanged: bool,
) -> tuple[str, str | None]:
    if pcm.get("status") == "fail":
        return "unsupported", "measured_pcm_mismatch"
    if geometry.get("status") == "mismatch":
        return "unsupported", "measured_geometry_mismatch"
    if geometry.get("status") == "ambiguous":
        return "ambiguous", "geometry_or_getter_ambiguous"
    if geometry.get("status") != "pass":
        return "unsupported", "required_observation_unavailable"
    if not source_unchanged:
        return "ambiguous", "source_integrity_unproven"
    if native_status == "ambiguous":
        return "ambiguous", "native_probe_ambiguous"
    if native_status == "render_limited":
        return "ambiguous", "render_limited"
    if pcm.get("status") != "pass":
        return "unsupported", "pcm_decode_unavailable"
    if native_status != "rendered_for_pcm_verification":
        return "unsupported", "native_probe_unsupported"
    return "supported", None


def _authenticate_render(
    request: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    render = result.get("render")
    expected_mov = probe.render_output_path(request)
    if (
        type(render) is not dict
        or render.get("status") != "rendered_for_pcm_verification"
        or render.get("outputPath") != str(expected_mov)
        or type(render.get("sha256")) is not str
        or render.get("formatCodec") != {"format": "mov", "codec": "ProRes422"}
        or type(render.get("jobId")) is not str
        or type(render.get("job")) is not dict
        or type(render.get("jobStatus")) is not dict
        or render["jobStatus"].get("JobStatus") != "Complete"
    ):
        raise SamplePrecisionCompareError(
            "native render profile or terminal job binding differs"
        )
    try:
        native_base._verify_job(render["job"], render["jobId"], expected_mov)
    except (ValueError, TypeError, KeyError) as error:
        raise SamplePrecisionCompareError(
            "native render job differs from the fixed profile"
        ) from error
    requested = native_base._render_settings(expected_mov)
    settings = render.get("settings")
    if type(settings) is not dict or settings.get("requested") != requested:
        raise SamplePrecisionCompareError("native render requested settings differ")
    readback = settings.get("readback")
    if type(readback) is not dict:
        raise SamplePrecisionCompareError("render settings readback is malformed")
    if readback.get("status") in {"unsupported", "ambiguous"}:
        if readback.get("method") != "Project.GetRenderSettings":
            raise SamplePrecisionCompareError("render settings diagnostic differs")
    elif any(readback.get(key) != value for key, value in requested.items()):
        raise SamplePrecisionCompareError("render settings getter differs")
    mov_sha = pcm_base._file_sha256(expected_mov)
    if mov_sha != render["sha256"]:
        raise SamplePrecisionCompareError("native render bytes differ from result hash")
    observations = result["observations"]
    post = render.get("postRenderObservation")
    reopened = observations[-1] if type(observations) is list and observations else None
    if (
        type(post) is not dict
        or type(reopened) is not dict
        or post.get("stage") != "candidate_after_render"
        or post.get("tracks") != reopened.get("tracks")
        or post.get("timeline") != reopened.get("timeline")
    ):
        raise SamplePrecisionCompareError(
            "candidate geometry changed or is unverified after native render"
        )
    return {
        "status": "authenticated",
        "path": str(expected_mov),
        "sha256": mov_sha,
        "jobId": render["jobId"],
        "job": render["job"],
        "jobStatus": render["jobStatus"],
        "formatCodec": render["formatCodec"],
        "settings": settings,
    }


def finalize_import_probe(request_path: Path, result_path: Path, output: Path) -> Path:
    """Authenticate a native import probe and publish the host verdict."""
    from .workflow_package import write_immutable_json

    request_path, result_path, output = map(Path, (request_path, result_path, output))
    for path in (request_path, result_path, output):
        native_base._no_symlink_ancestry(Path(os.path.abspath(path)))
    if output.exists() or output.is_symlink():
        raise SamplePrecisionCompareError("finalization report path already exists")
    if not (
        request_path.is_absolute()
        and result_path.is_absolute()
        and output.is_absolute()
    ):
        raise SamplePrecisionCompareError("finalization paths must be absolute")
    request_bytes = pcm_base._read_record(request_path, immutable=True)
    request_sha = hashlib.sha256(request_bytes).hexdigest()
    request = probe.load_import_request(request_path, request_sha, require_live=False)
    result_bytes = pcm_base._read_record(result_path, immutable=True)
    result_sha = hashlib.sha256(result_bytes).hexdigest()
    result = pcm_base._load_json(result_bytes, "native result")
    _verify_result_bindings(request, request_path, result, result_path)
    _current_release(request)
    source_wav = pcm_base._source_and_review_current(request)
    inputs = _current_inputs(request)
    _verify_effect_journals(request, result, request_sha)

    geometry = analyze_geometry(
        result.get("observations"),
        result.get("timelines"),
        request["imports"],
        request["sourcePath"],
    )
    native_render: dict[str, Any] = {"status": "unsupported"}
    pcm: dict[str, Any] = {
        "status": "unsupported",
        "reason": "native render was not authenticated",
    }
    comparator_sha = hashlib.sha256(pcm_base._read_record(Path(__file__))).hexdigest()
    decoder_identity: dict[str, Any] | None = None
    if result["status"] == "rendered_for_pcm_verification":
        native_render = _authenticate_render(request, result)
        try:
            decoded, decoder_identity = pcm_base._decode_probe_mov(
                Path(native_render["path"]), native_render["sha256"]
            )
            pcm = pcm_base.compare_pcm(
                source_wav,
                decoded,
                source_wav_sha256=request["sourceSha256"],
                source_pcm_sha256=request["sourcePcmSha256"],
                native_pcm_sha256=hashlib.sha256(decoded).hexdigest(),
                native_sample_format="s24-s32le",
                gap_start=GAP_START,
                gap_end=GAP_END,
            )
        except (
            SamplePrecisionCompareError,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            pcm = {"status": "unsupported", "reason": str(error)[:1000]}
    elif result["status"] == "render_limited":
        pcm["reason"] = "native render was limited: no job was queued, no MOV exists"
    else:
        pcm["reason"] = "PCM comparison not run: native probe produced no render/MOV"

    # Recheck every mutable binding after the potentially long decode.
    _current_release(request)
    if (
        hashlib.sha256(pcm_base._read_record(request_path, immutable=True)).hexdigest()
        != request_sha
        or hashlib.sha256(
            pcm_base._read_record(result_path, immutable=True)
        ).hexdigest()
        != result_sha
    ):
        raise SamplePrecisionCompareError("probe record changed during finalization")
    if (
        hashlib.sha256(pcm_base._source_and_review_current(request)).hexdigest()
        != request["sourceSha256"]
        or _current_inputs(request) != inputs
    ):
        raise SamplePrecisionCompareError("pinned inputs changed during finalization")
    if (
        native_render.get("status") == "authenticated"
        and pcm_base._file_sha256(Path(native_render["path"]))
        != native_render["sha256"]
    ):
        raise SamplePrecisionCompareError("native MOV changed during finalization")
    if (
        hashlib.sha256(pcm_base._read_record(Path(__file__))).hexdigest()
        != comparator_sha
    ):
        raise SamplePrecisionCompareError("host comparator changed during finalization")

    verdict, reason = _verdict(
        result["status"],
        geometry,
        pcm,
        source_unchanged=result["sourceIntegrity"].get("unchanged") is True,
    )
    report = {
        "schemaVersion": "vera-sample-import-probe-finalization/v1",
        "status": verdict,
        "reasonCategory": reason,
        "requestPath": str(request_path),
        "requestSha256": request_sha,
        "resultPath": str(result_path),
        "resultSha256": result_sha,
        "releaseSha256": request["releaseSha256"],
        "nativeResultStatus": result["status"],
        "nativeRequestPath": result["requestPath"],
        "target": request["target"],
        "source": result["source"],
        "review": result["review"],
        "sourceIntegrity": result["sourceIntegrity"],
        "inputs": inputs,
        "timelines": result["timelines"],
        "nativeRender": native_render,
        "geometry": geometry,
        "pcm": pcm,
        "decoder": decoder_identity,
        "hostComparatorSha256": comparator_sha,
        "failure": result.get("failure"),
    }
    protected = (
        Path(request["sourcePath"]).parent,
        Path(request["reviewPath"]).parent,
        Path(request["markerPath"]).parent,
        Path(request["releaseRoot"]),
    )
    if any(
        output.is_relative_to(path) or path.is_relative_to(output) for path in protected
    ):
        raise SamplePrecisionCompareError(
            "finalization output overlaps reviewed media or evidence"
        )
    write_immutable_json(output, report)
    return output
