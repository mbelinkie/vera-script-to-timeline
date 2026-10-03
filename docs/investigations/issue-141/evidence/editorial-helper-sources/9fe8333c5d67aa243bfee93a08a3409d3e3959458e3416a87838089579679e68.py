"""One guarded MOV/H264 plus Linear PCM calibration render candidate."""

import importlib.util
import json
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

READER_FILE = "r4-range-repair.py"
READER_SHA256 = "06eff080c45e5c520a1c8c31787e4d4f1604198a3a98a9e3c8e025917fcf455b"
CONTINUATION_RECORD_SHA256 = (
    "b169854fa9e6f9509dc22e1b8aa41e2d7e63b79baf74909c3246302c29fedc36"
)
MAX_SECONDS = 30
TERMINAL = {
    "Complete",
    "Render Complete",
    "Render Failed",
    "Render Cancelled",
    "Cancelled",
    "Background Render Cancelled",
    "Failed",
    "Remote Render Cancelled",
}
SUCCESS = {"Complete", "Render Complete"}
IMPORTED_MEDIA = {
    "base.mov",
    "cutaway.mov",
    "repeated.wav",
    "bed.wav",
    "overlay.png",
    "relink/base.mov",
}


def _sha(path):
    import hashlib

    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _load_reader(probe):
    path = Path(__file__).with_name(READER_FILE)
    if path.is_symlink() or _sha(path) != READER_SHA256:
        raise RuntimeError("Pinned full-state reader changed")
    spec = importlib.util.spec_from_file_location("av_output_reader", path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    return reader


def _inspect_output(path):
    completed = subprocess.run(
        [
            "/usr/local/bin/ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=format_name:stream=codec_type,codec_name,sample_rate,bits_per_sample,width,height,r_frame_rate,nb_frames",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(completed.stdout)


def _run(resolve, config, *, probe):
    reader = _load_reader(probe)
    root = Path(probe.ROOT).resolve()
    output = Path(config.get("outputDir", ""))
    media, expected_sources = reader._manifest(config, root, probe)
    pin_path = Path(config.get("checkpointPath", ""))
    pin_hash = config.get("checkpointSha256")
    if (
        config.get("action") not in {"av-output", "av-output-continue"}
        or config.get("externalScriptingSetting") != "None"
        or not config.get("projectName", "").startswith(
            "VERA Issue 141 Synthetic Probe "
        )
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != root / "out"
        or not output.name.startswith("issue-141-observation-")
        or pin_path.is_symlink()
        or not pin_path.is_file()
        or pin_path.parent.resolve() != output.resolve()
        or not isinstance(pin_hash, str)
        or _sha(pin_path) != pin_hash
        or not 0 < float(config.get("renderTimeoutSeconds", MAX_SECONDS)) <= MAX_SECONDS
    ):
        raise RuntimeError("Exact owned output/configuration required")

    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    if (
        pin.get("selectedTimelineUid") != reader.MATRIX_UID
        or pin.get("timelineConsistency") != "equal-adjacent-reads"
        or pin.get("poolConsistency") != "equal-adjacent-reads"
    ):
        raise RuntimeError("Complete selected-Matrix checkpoint required")
    baseline, base_pool = reader._validate_read_pair(pin, probe)
    if (
        baseline.get("projectId") != reader.PROJECT_ID
        or baseline.get("projectName") != config["projectName"]
    ):
        raise RuntimeError("Checkpoint belongs to a different project")
    continuation = config.get("action") == "av-output-continue"
    continuation_record = None
    continuation_xml = None
    continuation_preset = None
    if continuation:
        record_path = Path(config.get("continuationRecordPath", ""))
        if (
            record_path.is_symlink()
            or not record_path.is_file()
            or record_path.parent.resolve() != output.resolve()
            or record_path.name != "av-output-continuation-record.json"
            or _sha(record_path) != CONTINUATION_RECORD_SHA256
            or config.get("continuationRecordSha256") != CONTINUATION_RECORD_SHA256
        ):
            raise RuntimeError("Pinned direct-output continuation record required")
        continuation_record = json.loads(record_path.read_text(encoding="utf-8"))
        if (
            continuation_record.get("kind")
            != "issue-141-av-output-continuation-binding"
        ):
            raise RuntimeError("Continuation record kind mismatch")
        if continuation_record.get("checkpoint") != {
            "path": pin_path.name,
            "sha256": pin_hash,
        }:
            raise RuntimeError("Continuation checkpoint binding mismatch")
        prior = continuation_record.get("priorAttemptEvidence", {})
        prior_dir = output / "av-output-20261001T062051.400988Z"
        pinned_files = {
            "journal": prior_dir / "journal.jsonl",
            "finalLocalResult": prior_dir / "final-local-result.json",
            "snapshotXml": prior_dir
            / "VERA141_AV_OUTPUT_20261001T062051.400988Z.drp"
            / "VERA141_AV_OUTPUT_20261001T062051.400988Z.xml",
        }
        for key, path in pinned_files.items():
            expected = prior.get(key, {})
            if (
                path.is_symlink()
                or not path.is_file()
                or expected.get("path") != str(path.relative_to(output))
                or expected.get("sha256") != _sha(path)
            ):
                raise RuntimeError(f"Continuation evidence changed: {key}")
        previous_result = json.loads(pinned_files["finalLocalResult"].read_text())
        if previous_result.get("failure") != prior.get("expectedPriorRefusal"):
            raise RuntimeError(
                "Prior attempt is not the pinned preset-precondition refusal"
            )
        xml_root = ET.parse(pinned_files["snapshotXml"]).getroot()
        extra_info = {
            e.findtext("DbKey"): e.findtext("DbVal")
            for e in xml_root.findall(".//ExtraInfoMap/Element")
        }
        actual_fields = {
            "RecordFormatType": xml_root.findtext("RecordFormatType"),
            "RecordFormatSubType": xml_root.findtext("RecordFormatSubType"),
            "RecordAudioEnabled": xml_root.findtext("RecordAudioEnabled"),
            "RecordAudioBitDepth": xml_root.findtext("RecordAudioBitDepth"),
            "extra_info.aud_codec": extra_info.get("aud_codec"),
        }
        if actual_fields != prior.get("actualSnapshotFields"):
            raise RuntimeError("Continuation snapshot fields changed")
        continuation_xml = pinned_files["snapshotXml"]
        continuation_preset = prior.get("presetName")
        if not isinstance(continuation_preset, str) or not continuation_preset:
            raise RuntimeError("Continuation preset name missing")
    expected_imported = {str(media / name) for name in IMPORTED_MEDIA}
    if not expected_imported <= set(expected_sources):
        raise RuntimeError("Manifest lacks one of the six approved imported sources")
    proxy_uids = {
        row.get("poolItemUid", {}).get("value")
        for row in base_pool.get("timelineMappings", [])
    }
    observed_imported = set()
    for row in base_pool.get("items", []):
        evidence = row.get("evidence", {})
        props = evidence.get("GetClipProperty", {}).get("value", {})
        source = props.get("File Path")
        uid = row.get("uid")
        byte_evidence = evidence.get("sourceBytes", {})
        if uid in proxy_uids:
            if byte_evidence.get("status") != "timeline-uid-not-hashed":
                raise RuntimeError("Timeline proxy evidence classification changed")
            continue
        if not isinstance(source, str) or source not in expected_sources:
            raise RuntimeError("Pool source is not an approved generated manifest file")
        if (
            byte_evidence.get("status") != "reachable"
            or byte_evidence.get("sha256") != expected_sources[source]
            or byte_evidence.get("hashMatches") is not True
        ):
            raise RuntimeError("Reachable pool source bytes differ from manifest")
        observed_imported.add(source)
    if observed_imported != expected_imported:
        raise RuntimeError(
            "Pool does not contain exactly the six approved imported sources"
        )

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence_dir = output / f"av-output-{stamp}"
    evidence_dir.mkdir()
    journal = evidence_dir / "journal.jsonl"
    journal.touch()
    pair_number = 0

    def record(method, phase, value):
        with journal.open("a", encoding="utf-8") as stream:
            json.dump(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "method": method,
                    "phase": phase,
                    "value": value,
                },
                stream,
                sort_keys=True,
                allow_nan=False,
            )
            stream.write("\n")

    def call(obj, method, *args):
        record(method, "request", list(args))
        try:
            value = getattr(obj, method)(*args)
        except Exception as error:
            record(method, "failure", f"{type(error).__name__}: {error}")
            raise
        record(method, "return", value)
        return value

    identity = {"projectId": reader.PROJECT_ID, "projectName": config["projectName"]}

    def context(allowed_jobs=None, *, idle=True):
        if (
            resolve.GetProductName() != "DaVinci Resolve Studio"
            or resolve.GetVersion() != reader.BUILD
        ):
            raise RuntimeError("Exact Resolve Studio 21.1.0 build 14 required")
        project = reader._context(
            resolve, config, identity, probe, reader.MATRIX_UID, idle=idle
        )
        if project.GetRenderJobList() != ([] if allowed_jobs is None else allowed_jobs):
            raise RuntimeError("Render queue differs from the owned job set")
        return project

    def fresh_pair(allowed_jobs=None):
        nonlocal pair_number
        project = context(allowed_jobs)
        pair = reader._read_pair(
            resolve, config, identity, expected_sources, reader.MATRIX_UID, probe
        )
        pair_number += 1
        pair_path = evidence_dir / f"full-pair-{pair_number:03d}.json"
        with pair_path.open("x", encoding="utf-8") as stream:
            json.dump(pair, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        pair_hash = _sha(pair_path)
        record(
            "FullPair",
            f"captured-{pair_number:03d}",
            {"path": str(pair_path), "sha256": pair_hash},
        )
        timeline, pool = reader._validate_read_pair(pair, probe)
        if timeline != baseline or pool != base_pool:
            raise RuntimeError("Fresh full content/source state differs from pin")
        return project

    def state(project):
        def read():
            return {
                "formatCodec": call(project, "GetCurrentRenderFormatAndCodec"),
                "mode": call(project, "GetCurrentRenderMode"),
                "jobs": call(project, "GetRenderJobList"),
                "rendering": call(project, "IsRenderingInProgress"),
                "presets": call(project, "GetRenderPresetList"),
            }

        value = read()
        if value != read():
            raise RuntimeError("Adjacent render-state reads differ")
        if (
            value["formatCodec"] != {"format": "mov", "codec": "H264"}
            or value["mode"] != 1
            or value["jobs"] != []
            or value["rendering"] is not False
            or not isinstance(value["presets"], list)
        ):
            raise RuntimeError("MOV/H264 single-clip idle state required")
        return value

    project = fresh_pair()
    original = state(project)
    if continuation:
        preset = continuation_preset
        prior_visible = continuation_record["priorInitialVisibleState"]
        expected_visible = {
            **prior_visible,
            "presets": [*prior_visible["presets"], preset],
        }
        if original != expected_visible:
            raise RuntimeError(
                "Current visible state is not prior state plus owned preset"
            )
        if original["presets"].count(preset) != 1:
            raise RuntimeError("Owned continuation preset is not unique")
        xml = continuation_xml
    else:
        preset = f"VERA141_AV_OUTPUT_{stamp}"
        if preset in original["presets"]:
            raise RuntimeError("Unique owned preset name collision")
    preset_dir = evidence_dir / f"{preset}.drp"
    render_dir = evidence_dir / "render"
    render_dir.mkdir()

    # The continuation reuses its exact pinned recovery copy; it never saves or
    # exports a second preset. Fresh attempts save/export before changing state.
    if not continuation:
        fresh_pair()
        if call(project, "SaveAsNewRenderPreset", preset) is not True:
            raise RuntimeError("Snapshot save refused; settings untouched")
        if call(project, "GetRenderPresetList").count(preset) != 1:
            raise RuntimeError("Unique snapshot preset not confirmed")
        fresh_pair()
        if call(resolve, "ExportRenderPreset", preset, str(preset_dir)) is not True:
            raise RuntimeError("Snapshot export refused")
        xml = preset_dir / f"{preset}.xml"
        if (
            preset_dir.is_symlink()
            or not preset_dir.is_dir()
            or xml.is_symlink()
            or not xml.is_file()
            or {p.name for p in preset_dir.iterdir()} != {xml.name}
            or not xml.resolve().is_relative_to(evidence_dir.resolve())
        ):
            raise RuntimeError("Exported recovery XML is missing or unsafe")
        xml_bytes = xml.read_bytes()
        snapshot_root = ET.fromstring(xml_bytes)
        extra_info = {
            element.findtext("DbKey"): element.findtext("DbVal")
            for element in snapshot_root.findall(".//ExtraInfoMap/Element")
        }
        if (
            snapshot_root.findtext("RecordFormatType") != "mov"
            or snapshot_root.findtext("RecordFormatSubType") != "avc1"
            or snapshot_root.findtext("RecordAudioEnabled") != "true"
            or snapshot_root.findtext("RecordAudioBitDepth") != "24"
            or extra_info.get("aud_codec") != "lpcm"
        ):
            raise RuntimeError("Snapshot XML does not verify MOV/H264 plus lpcm")
        record(
            "RecoveryXml",
            "verified",
            {"path": str(xml), "sha256": _sha(xml), "bytes": len(xml_bytes)},
        )
    else:
        record("RecoveryXml", "reused-pinned", {"path": str(xml), "sha256": _sha(xml)})

    if config.get("sampleRateHz") != 48000:
        raise RuntimeError("Explicit 48 kHz calibration is required")
    settings = {
        "ExportVideo": True,
        "ExportAudio": True,
        "AudioCodec": "lpcm",
        "AudioSampleRate": 48000,
        "AudioBitDepth": 24,
        "FormatWidth": 640,
        "FormatHeight": 360,
        "FrameRate": 25.0,
        "MarkIn": 0,
        "MarkOut": 200,
        "SelectAllFrames": False,
        "TargetDir": str(render_dir),
        "CustomName": f"vera141-av-{stamp}",
    }
    fresh_pair()
    context()
    if call(project, "SetRenderSettings", settings) is not True:
        return {
            "status": "settings-refused-recovery-retained",
            "journal": str(journal),
            "snapshot": str(xml),
        }
    configured = state(project)
    if configured["presets"] != [*original["presets"], preset] and set(
        configured["presets"]
    ) != set(original["presets"]) | {preset}:
        raise RuntimeError("Preset list drift; preserve recovery")
    jobs = call(project, "GetRenderJobList")
    if jobs != []:
        raise RuntimeError("Unexpected queue after settings; preserve recovery")

    fresh_pair()
    context()
    job_id = call(project, "AddRenderJob")
    queued = call(project, "GetRenderJobList")
    if (
        not isinstance(job_id, str)
        or not job_id
        or len(queued) != 1
        or queued[0].get("JobId") != job_id
    ):
        return {
            "status": "queued-job-unverified-recovery-retained",
            "jobId": job_id,
            "journal": str(journal),
            "snapshot": str(xml),
        }
    job = queued[0]
    expected_name = settings["CustomName"] + ".mov"
    if (
        job.get("IsExportVideo") is not True
        or job.get("IsExportAudio") is not True
        or job.get("VideoFormat") not in {"QuickTime", "mov"}
        or job.get("VideoCodec") not in {"H.264", "H264"}
        or job.get("AudioCodec") != "lpcm"
        or job.get("AudioSampleRate") != 48000
        or job.get("AudioBitDepth") != 24
        or job.get("FormatWidth") != 640
        or job.get("FormatHeight") != 360
        or job.get("FrameRate") not in {"25", 25}
        or job.get("MarkIn") != 0
        or job.get("MarkOut") != 200
        or job.get("TargetDir") != str(render_dir)
        or job.get("OutputFilename") not in {expected_name, settings["CustomName"]}
    ):
        return {
            "status": "queued-job-metadata-unknown-recovery-retained",
            "jobId": job_id,
            "job": job,
            "journal": str(journal),
            "snapshot": str(xml),
        }
    target = render_dir / job["OutputFilename"]
    if target.exists() or target.is_symlink():
        return {
            "status": "output-path-exists-recovery-retained",
            "jobId": job_id,
            "journal": str(journal),
            "snapshot": str(xml),
        }

    fresh_pair(queued)
    context(queued)
    if call(project, "StartRendering", [job_id]) is not True:
        return {
            "status": "start-refused-recovery-retained",
            "jobId": job_id,
            "journal": str(journal),
            "snapshot": str(xml),
        }
    deadline = time.monotonic() + float(config.get("renderTimeoutSeconds", MAX_SECONDS))
    status = None
    while time.monotonic() < deadline:
        status = call(project, "GetRenderJobStatus", job_id)
        if not isinstance(status, dict):
            break
        if status.get("JobStatus") in TERMINAL:
            break
        context(queued, idle=False)
        running_state = {
            "formatCodec": call(project, "GetCurrentRenderFormatAndCodec"),
            "mode": call(project, "GetCurrentRenderMode"),
            "jobs": call(project, "GetRenderJobList"),
            "rendering": call(project, "IsRenderingInProgress"),
            "presets": call(project, "GetRenderPresetList"),
        }
        if (
            running_state["formatCodec"] != original["formatCodec"]
            or running_state["mode"] != original["mode"]
            or running_state["jobs"] != queued
            or running_state["rendering"] is not True
            or set(running_state["presets"]) != set(original["presets"]) | {preset}
        ):
            record("Render", "unrelated-state-drift", running_state)
            return {
                "status": "render-state-drift-recovery-retained",
                "jobId": job_id,
                "journal": str(journal),
                "snapshot": str(xml),
            }
        if call(project, "IsRenderingInProgress") is not True:
            break
        time.sleep(min(0.1, deadline - time.monotonic()))
    if not isinstance(status, dict) or status.get("JobStatus") not in TERMINAL:
        return {
            "status": "render-pending-or-ambiguous-recovery-retained",
            "jobId": job_id,
            "journal": str(journal),
            "snapshot": str(xml),
        }
    record("Render", "terminal", status)
    if status.get("JobStatus") not in SUCCESS:
        return {
            "status": "render-failed-recovery-retained",
            "jobId": job_id,
            "jobStatus": status,
            "journal": str(journal),
            "snapshot": str(xml),
        }
    if (
        call(project, "IsRenderingInProgress") is not False
        or not target.is_file()
        or target.is_symlink()
        or not target.resolve().is_relative_to(render_dir.resolve())
    ):
        raise RuntimeError(
            "Successful job lacks safe expected output; preserve recovery"
        )
    media_info = _inspect_output(target)
    streams = media_info.get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    if (
        "mov" not in media_info.get("format", {}).get("format_name", "").split(",")
        or len(video) != 1
        or len(audio) != 1
        or video[0].get("codec_name") != "h264"
        or video[0].get("width") != 640
        or video[0].get("height") != 360
        or video[0].get("r_frame_rate") != "25/1"
        or video[0].get("nb_frames") not in {"201", 201}
        or not audio[0].get("codec_name", "").startswith("pcm_s24")
        or audio[0].get("sample_rate") != "48000"
        or audio[0].get("bits_per_sample") != 24
    ):
        record("Output", "metadata-refused", media_info)
        return {
            "status": "render-output-metadata-unknown-recovery-retained",
            "jobId": job_id,
            "mediaInfo": media_info,
            "journal": str(journal),
            "snapshot": str(xml),
        }
    record(
        "Output",
        "retained",
        {
            "path": str(target),
            "bytes": target.stat().st_size,
            "sha256": _sha(target),
            "ffprobe": media_info,
        },
    )
    project = fresh_pair(queued)
    current = call(project, "GetRenderJobList")
    if current != queued:
        raise RuntimeError("Post-render queue drift; preserve recovery")
    # Load and verify the snapshot only after a successful terminal render and
    # full content/source equality. Hidden settings have no complete readback.
    fresh_pair(queued)
    if call(project, "LoadRenderPreset", preset) is not True:
        raise RuntimeError("Snapshot load refused; retain job and XML")
    restored = (
        call(project, "GetCurrentRenderFormatAndCodec") == original["formatCodec"]
    )
    restored = restored and call(project, "GetCurrentRenderMode") == original["mode"]
    restored = restored and call(project, "IsRenderingInProgress") is False
    restored_presets = (
        original["presets"] if continuation else [*original["presets"], preset]
    )
    restored = restored and call(project, "GetRenderPresetList") == restored_presets
    fresh_pair(queued)
    if not restored:
        raise RuntimeError(
            "Visible restoration/content verification failed; retain job and XML"
        )
    context(queued)
    if (
        call(project, "DeleteRenderJob", job_id) is not True
        or call(project, "GetRenderJobList") != []
    ):
        raise RuntimeError("Owned terminal job cleanup failed; retain XML")
    fresh_pair()
    context()
    final_presets = (
        [name for name in original["presets"] if name != preset]
        if continuation
        else original["presets"]
    )
    if (
        call(project, "DeleteRenderPreset", preset) is not True
        or call(project, "GetRenderPresetList") != final_presets
    ):
        raise RuntimeError("Owned snapshot cleanup failed; exported XML retained")
    fresh_pair()
    return {
        "status": "render-complete-restored",
        "jobStatus": status,
        "output": str(target),
        "outputSha256": _sha(target),
        "snapshotXml": str(xml),
        "snapshotSha256": _sha(xml),
        "ffprobe": media_info,
        "journal": str(journal),
        "hiddenRenderSettingsEquality": "not exposed",
    }


def run(resolve, config, *, probe):
    output = Path(config.get("outputDir", ""))
    prior = (
        {
            path.resolve()
            for path in output.glob("av-output-*")
            if path.is_dir() and not path.is_symlink()
        }
        if output.is_dir()
        else set()
    )
    result, failure = None, None
    try:
        result = _run(resolve, config, probe=probe)
    except Exception as error:
        failure = f"{type(error).__name__}: {error}"
    created = (
        [
            path
            for path in output.glob("av-output-*")
            if path.is_dir() and not path.is_symlink() and path.resolve() not in prior
        ]
        if output.is_dir()
        else []
    )
    environment = {
        "product": None,
        "version": None,
        "pythonExecutable": sys.executable,
        "pythonVersion": sys.version,
        "platform": platform.platform(),
    }
    try:
        environment["product"] = resolve.GetProductName()
        environment["version"] = resolve.GetVersion()
    except Exception as error:
        environment["resolveContextFailure"] = f"{type(error).__name__}: {error}"
    if created:
        final = {
            "kind": "av-output-final-local-result",
            "environment": environment,
            "result": result,
            "failure": failure,
        }
        with (created[-1] / "final-local-result.json").open(
            "x", encoding="utf-8"
        ) as stream:
            json.dump(final, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
    if failure:
        raise RuntimeError(failure)
    return result
