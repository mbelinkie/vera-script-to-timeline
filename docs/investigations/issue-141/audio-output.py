"""One guarded audio-only output probe for Issue 141."""

import hashlib
import json
import time
import wave
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
MATRIX_ID = "29ae8331-b86e-4041-a548-960695cc7b24"
BUILD = [21, 1, 0, 14, ""]
# Accepted full selected-Matrix pair after verified R4 restoration.
PIN_NAME = "matrix-checkpoint-20261001T015209.473668Z-matrix-observation.json"
PIN_SHA256 = "0220a23be312aea5906900dd094c8e21b363294bb11f9b0f1201ab23f40c4cbf"
MAX_RENDER_SECONDS = 30
SUCCESS_TERMINAL = {"Complete", "Render Complete"}
TERMINAL = {
    *SUCCESS_TERMINAL,
    "Render Failed",
    "Render Cancelled",
    "Cancelled",
    "Background Render Cancelled",
    "Failed",
    "Remote Render Cancelled",
}
CONTINUATION_DIR = "audio-output-20261001T015945.287072Z"
CONTINUATION_JOURNAL_SHA = (
    "19bc611d3c32ac686f5f389f3dd414fff04bf3a899f50c962ef3b98a5f235509"
)
CONTINUATION_PREFLIGHT_SHA = (
    "7026b0ec5aa22f630314001d0e9562ff00121111791bed4b03d97e1e577a79cb"
)
CONTINUATION_XML_SHA = (
    "1b3b21a728c3216f9782d87aa2feae977747c377901eb6b81ed5a83a2da06595"
)
CONTINUATION_RESULT_NAME = (
    "vera-issue-141-observation-result-20261001T015945.257683Z.json"
)
CONTINUATION_RESULT_SHA = (
    "e0e74086ad9b4733623665f5e331dd11229042eb86ff11f1e4efe2e95e403f7d"
)
CONTINUATION_COMPARISON_SHA = (
    "c8155853d4d5c0be5dd9659423a1cf0aa9960842d5d01dc17eee99ace03f7d6e"
)
CONTINUATION_NAME = "VERA141_AUDIO_OUTPUT_20261001T015945.287072Z"
PLUGIN_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)


def _sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _append(path, method, phase, value):
    with Path(path).open("a", encoding="utf-8") as stream:
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


def _canonical(value):
    return json.loads(json.dumps(value, allow_nan=False))


def _inside(path, parent):
    path, parent = Path(path), Path(parent)
    try:
        return path.resolve(strict=True).is_relative_to(parent.resolve(strict=True))
    except (OSError, ValueError):
        return False


def _pin(path, probe):
    if (
        PIN_NAME == "PENDING"
        or PIN_SHA256 == "PENDING"
        or path.name != PIN_NAME
        or path.is_symlink()
        or not path.is_file()
        or _sha256(path) != PIN_SHA256
    ):
        raise RuntimeError("Accepted selected-Matrix checkpoint is missing or changed")
    value = json.loads(path.read_text(encoding="utf-8"))
    passes = value.get("timelinePasses")
    pools = value.get("poolPasses")
    if (
        value.get("selectedTimelineUid") != MATRIX_ID
        or value.get("timelineConsistency") != "equal-adjacent-reads"
        or value.get("poolConsistency") != "equal-adjacent-reads"
        or not isinstance(passes, list)
        or len(passes) != 2
        or passes[0] != passes[1]
        or probe.errors(passes)
        or not isinstance(pools, list)
        or len(pools) != 2
        or pools[0] != pools[1]
        or probe.errors(pools)
        or passes[0].get("projectId") != PROJECT_ID
    ):
        raise RuntimeError("Accepted selected-Matrix checkpoint is incomplete")
    timelines = [
        row
        for row in passes[0].get("timelines", [])
        if row.get("GetUniqueId", {}).get("value") == MATRIX_ID
    ]
    if len(timelines) != 1 or timelines[0].get("GetName") != {
        "value": "VERA 141 Batched Matrix"
    }:
        raise RuntimeError("Checkpoint does not pin the exact Matrix timeline")
    return passes[0]


def _sources(config, probe, media, journal):
    manifest_path = media / "manifest.json"
    if (
        manifest_path.is_symlink()
        or not manifest_path.is_file()
        or _sha256(manifest_path) != config.get("manifestSha256")
    ):
        raise RuntimeError("Synthetic media manifest is missing or changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("kind") != "generated-synthetic-inputs-not-Resolve-evidence":
        raise RuntimeError("Only generated synthetic inputs are allowed")
    expected = {}
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise RuntimeError("Synthetic media manifest file list is invalid")
    for entry in entries:
        relative = Path(entry["path"])
        path = media / relative
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or path.is_symlink()
            or not _inside(path, media)
            or not isinstance(entry.get("sha256"), str)
            or len(entry["sha256"]) != 64
        ):
            raise RuntimeError("Unsafe synthetic media manifest entry")
        expected[str(path)] = entry["sha256"]
    if len(expected) != len(entries):
        raise RuntimeError("Synthetic media manifest has duplicate paths")
    _append(
        journal,
        "SyntheticManifest",
        "verified",
        {
            "sha256": config["manifestSha256"],
            "entries": expected,
            "note": "Live-source bytes are checked in complete pre/post captures.",
        },
    )
    return expected


def run(resolve, config, *, probe):
    """Render one bounded audio-only WAV, then restore its saved render preset."""
    root = Path(probe.ROOT).resolve()
    output = Path(config.get("outputDir", ""))
    media = Path(config.get("mediaDir", ""))
    if (
        config.get("action") not in {"audio-output", "audio-output-continue"}
        or config.get("externalScriptingSetting") != "None"
        or not config.get("projectName", "").startswith(probe.PREFIX)
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != (root / "out").resolve()
        or not output.name.startswith("issue-141-observation-")
        or not media.is_absolute()
        or media.is_symlink()
        or not media.is_dir()
        or media.parent.resolve() != (root / "out").resolve()
        or not media.name.startswith("issue-141-media-")
    ):
        raise RuntimeError(
            "Only owned Issue 141 output and synthetic media are allowed"
        )

    try:
        timeout = float(config.get("renderTimeoutSeconds", MAX_RENDER_SECONDS))
    except (TypeError, ValueError):
        raise RuntimeError("Render timeout must be between 0 and 30 seconds") from None
    if not 0 < timeout <= MAX_RENDER_SECONDS:
        raise RuntimeError("Render timeout must be between 0 and 30 seconds")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence = output / f"audio-output-{stamp}"
    evidence.mkdir()
    journal = evidence / "journal.jsonl"
    journal.open("x", encoding="utf-8").close()

    def record(method, phase, value):
        _append(journal, method, phase, value)

    def call(obj, method, *args):
        record(method, "request", list(args))
        try:
            value = getattr(obj, method)(*args)
        except Exception as error:
            record(method, "failure", f"{type(error).__name__}: {error}")
            raise
        record(method, "return", value)
        return value

    def context():
        if (
            resolve.GetProductName() != "DaVinci Resolve Studio"
            or resolve.GetVersion() != BUILD
        ):
            raise RuntimeError("Exact Resolve Studio 21.1.0 build 14 required")
        identity = {"projectId": PROJECT_ID, "projectName": config["projectName"]}
        project = probe.require_current(resolve, config, identity)
        timeline = project.GetCurrentTimeline()
        if timeline is None or timeline.GetUniqueId() != MATRIX_ID:
            raise RuntimeError("Exact Matrix timeline must remain selected")
        return project

    def capture(label, pinned):
        passes = []
        for _ in range(2):
            try:
                context()
                passes.append(
                    _canonical(
                        probe.observe(
                            resolve,
                            dict(config, stage="R2-audio-output"),
                            {
                                "projectId": PROJECT_ID,
                                "projectName": config["projectName"],
                            },
                            expected,
                        )
                    )
                )
                context()
            except Exception as error:
                passes.append({"error": f"{type(error).__name__}: {error}"})
        failures = probe.errors(passes)
        result = {
            "kind": "audio-output-capture",
            "label": label,
            "capturedAt": datetime.now(UTC).isoformat(),
            "passes": passes,
            "getterFailures": failures,
            "consistency": "equal-adjacent-reads"
            if passes[0] == passes[1] and not failures
            else "incomplete-or-inconsistent-refused",
        }
        _write(evidence / f"{label}.json", result)
        record("Capture", label, result)
        if result["consistency"] != "equal-adjacent-reads" or passes != [
            pinned,
            pinned,
        ]:
            raise RuntimeError(f"{label} differs from the accepted full checkpoint")
        return result

    def render_state(project):
        state = {
            "formatCodec": call(project, "GetCurrentRenderFormatAndCodec"),
            "mode": call(project, "GetCurrentRenderMode"),
            "jobs": call(project, "GetRenderJobList"),
            "rendering": call(project, "IsRenderingInProgress"),
            "presets": call(project, "GetRenderPresetList"),
        }
        if (
            not isinstance(state["formatCodec"], dict)
            or state["mode"] != 1
            or not isinstance(state["jobs"], list)
            or not isinstance(state["presets"], list)
            or not all(isinstance(name, str) for name in state["presets"])
            or state["rendering"] is not False
        ):
            raise RuntimeError("Render state is incomplete or a render is active")
        return state

    def basic_state(project, original, jobs):
        state = render_state(project)
        if (
            state["formatCodec"] != original["formatCodec"]
            or state["mode"] != original["mode"]
            or state["jobs"] != jobs
            or state["rendering"] is not False
        ):
            raise RuntimeError(
                "Render settings, queue, or context changed unexpectedly"
            )
        return state

    def restore(project, preset_name, original, expected_jobs):
        context()
        value = call(project, "LoadRenderPreset", preset_name)
        if value is not True:
            raise RuntimeError("Saved render preset refused restoration")
        state = basic_state(project, original, expected_jobs)
        if set(state["presets"]) != set(original["presets"]) | {preset_name}:
            raise RuntimeError("Render preset list changed outside the owned snapshot")
        return state

    def restore_unqueued(reason):
        """Restore only while exact context is current, idle, and queue is empty."""
        try:
            project = context()
            if (
                call(project, "IsRenderingInProgress") is not False
                or call(project, "GetRenderJobList") != []
            ):
                raise RuntimeError("Render is active or queue is not empty")
            restore(project, preset_name, original, [])
            capture("postflight", pinned)
            context()
            deleted = call(project, "DeleteRenderPreset", preset_name)
            presets = call(project, "GetRenderPresetList")
            if deleted is not True or presets != original_presets:
                raise RuntimeError("Could not remove owned snapshot after restoration")
            record("AudioOutput", "prequeue-restored", {"reason": reason})
        except Exception as restore_error:
            record(
                "AudioOutput",
                "prequeue-restoration-failure",
                f"{type(restore_error).__name__}: {restore_error}",
            )
            raise RuntimeError(
                "Prequeue refusal; recovery preset retained"
            ) from restore_error

    def restore_queued_idle(reason, detail):
        """Restore settings but retain every queued job and the recovery preset."""
        record("AudioOutput", "job-refused", {"reason": reason, "detail": detail})
        try:
            project = context()
            if call(project, "IsRenderingInProgress") is not False:
                raise RuntimeError("Render state is active or uncertain")
            jobs_before_restore = call(project, "GetRenderJobList")
            if call(project, "LoadRenderPreset", preset_name) is not True:
                raise RuntimeError("Snapshot load was refused")
            state = render_state(project)
            if (
                state["formatCodec"] != original["formatCodec"]
                or state["mode"] != original["mode"]
                or state["rendering"] is not False
                or state["jobs"] != jobs_before_restore
                or set(state["presets"]) != set(original["presets"]) | {preset_name}
            ):
                raise RuntimeError(
                    "Restored settings, queue, or recovery preset did not verify"
                )
            record("AudioOutput", "queue-refused-settings-restored", {"state": state})
        except Exception as restore_error:
            record(
                "AudioOutput",
                "queue-refusal-restore-failure",
                f"{type(restore_error).__name__}: {restore_error}",
            )
            raise RuntimeError(
                "Queued job is refused; preserve queue and recovery preset"
            ) from restore_error
        return {
            "status": "queued-job-refused-settings-restored",
            "reason": reason,
            "detail": detail,
            "journal": str(journal),
            "recoveryPreset": str(recovery_path),
            "recoverySha256": recovery_hash,
        }

    def owned_terminal_job(project, job_id):
        jobs = call(project, "GetRenderJobList")
        if (
            not isinstance(jobs, list)
            or len(jobs) != 1
            or jobs[0].get("JobId") != job_id
        ):
            raise RuntimeError("Only the single returned job can be cleaned up")
        status = call(project, "GetRenderJobStatus", job_id)
        if not isinstance(status, dict) or status.get("JobStatus") not in TERMINAL:
            raise RuntimeError("Owned render job is not in a terminal state")
        if call(project, "IsRenderingInProgress") is not False:
            raise RuntimeError(
                "Render remains active; preserve job and recovery preset"
            )
        return jobs, status

    expected = _sources(config, probe, media, journal)
    pin_path = Path(config.get("checkpointPath", ""))
    if (
        not PIN_NAME
        or PIN_NAME == "PENDING"
        or not pin_path.is_absolute()
        or pin_path.parent.resolve() != output.resolve()
        or not _inside(pin_path, output)
    ):
        raise RuntimeError("Configured checkpoint is not the owned output pin")
    pinned = _pin(pin_path, probe)
    record(
        "AudioOutput",
        "start",
        {
            "stage": "R2-audio-output",
            "checkpoint": PIN_NAME,
            "checkpointSha256": PIN_SHA256,
            "manifestSha256": config["manifestSha256"],
            "allowedMutations": [
                "SaveAsNewRenderPreset",
                "ExportRenderPreset",
                "SetRenderSettings(audio-only)",
                "AddRenderJob",
                "StartRendering([returnedJobId])",
                "LoadRenderPreset",
                "DeleteRenderJob(returned terminal job only)",
                "DeleteRenderPreset(owned snapshot only)",
            ],
        },
    )
    context()
    capture("preflight", pinned)
    project = context()
    original = render_state(project)
    if (
        original["formatCodec"] != {"format": "mov", "codec": "H264"}
        or original["mode"] != 1
        or original["jobs"] != []
        or original["rendering"] is not False
    ):
        raise RuntimeError(
            "Expected MOV/H264, single-clip mode, empty queue, idle render"
        )
    original_presets = original["presets"]
    continuation = config["action"] == "audio-output-continue"
    recovery_path = None
    if continuation:
        prior = output / CONTINUATION_DIR
        journal_path = prior / "journal.jsonl"
        preflight_path = prior / "preflight.json"
        comparison_path = output / "audio-export-refusal-independent-comparison.json"
        result_path = PLUGIN_ROOT / CONTINUATION_RESULT_NAME
        preset_name = CONTINUATION_NAME
        recovery_path = prior / f"{preset_name}.drp"
        xml_path = recovery_path / f"{preset_name}.xml"
        expected_events = [
            ("SyntheticManifest", "verified"),
            ("AudioOutput", "start"),
            ("Capture", "preflight"),
            ("GetCurrentRenderFormatAndCodec", "request"),
            ("GetCurrentRenderFormatAndCodec", "return"),
            ("GetCurrentRenderMode", "request"),
            ("GetCurrentRenderMode", "return"),
            ("GetRenderJobList", "request"),
            ("GetRenderJobList", "return"),
            ("IsRenderingInProgress", "request"),
            ("IsRenderingInProgress", "return"),
            ("GetRenderPresetList", "request"),
            ("GetRenderPresetList", "return"),
            ("SaveAsNewRenderPreset", "request"),
            ("SaveAsNewRenderPreset", "return"),
            ("GetRenderPresetList", "request"),
            ("GetRenderPresetList", "return"),
            ("ExportRenderPreset", "request"),
            ("ExportRenderPreset", "return"),
        ]
        if (
            prior.is_symlink()
            or not prior.is_dir()
            or journal_path.is_symlink()
            or not journal_path.is_file()
            or preflight_path.is_symlink()
            or not preflight_path.is_file()
            or _sha256(journal_path) != CONTINUATION_JOURNAL_SHA
            or _sha256(preflight_path) != CONTINUATION_PREFLIGHT_SHA
            or comparison_path.is_symlink()
            or not comparison_path.is_file()
            or _sha256(comparison_path) != CONTINUATION_COMPARISON_SHA
            or result_path.is_symlink()
            or not result_path.is_file()
            or _sha256(result_path) != CONTINUATION_RESULT_SHA
            or recovery_path.is_symlink()
            or not recovery_path.is_dir()
            or xml_path.is_symlink()
            or not xml_path.is_file()
            or {p.name for p in recovery_path.iterdir()} != {xml_path.name}
            or _sha256(xml_path) != CONTINUATION_XML_SHA
        ):
            raise RuntimeError("Pinned preset-recovery snapshot is missing or changed")
        prior_rows = [
            json.loads(line) for line in journal_path.read_text().splitlines()
        ]
        if [
            (row.get("method"), row.get("phase")) for row in prior_rows
        ] != expected_events:
            raise RuntimeError("Pinned preset-recovery journal sequence differs")
        if (
            prior_rows[-1].get("value") is not True
            or prior_rows[-2].get("value", [None])[0] != preset_name
        ):
            raise RuntimeError("Pinned preset export did not return literal True")
        preset_reads = [
            row["value"]
            for row in prior_rows
            if row.get("method") == "GetRenderPresetList"
            and row.get("phase") == "return"
        ]
        if (
            len(preset_reads) != 2
            or preset_reads[1] != [*preset_reads[0], preset_name]
            or preset_reads[0].count(preset_name) != 0
        ):
            raise RuntimeError("Pinned render-preset list transition differs")
        prior_capture = json.loads(preflight_path.read_text(encoding="utf-8"))
        if prior_capture.get("passes") != [pinned, pinned]:
            raise RuntimeError(
                "Pinned preset recovery preflight differs from checkpoint"
            )
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        refusal = json.loads(result_path.read_text(encoding="utf-8"))
        if (
            comparison.get("files", {}).get("journal.jsonl") != CONTINUATION_JOURNAL_SHA
            or comparison.get("files", {}).get("preflight.json")
            != CONTINUATION_PREFLIGHT_SHA
            or comparison.get("files", {}).get(f"{preset_name}.xml")
            != CONTINUATION_XML_SHA
            or comparison.get("files", {}).get(CONTINUATION_RESULT_NAME)
            != CONTINUATION_RESULT_SHA
            or comparison.get("setSettingsQueuedOrRendered") is not False
            or comparison.get("fullPreflightEqualsSelectedMatrixPin") is not True
            or refusal.get("status") != "launcher-failed"
        ):
            raise RuntimeError("Pinned export-refusal comparison differs")
        record(
            "PresetRecovery",
            "verified-existing",
            {
                "name": preset_name,
                "xmlSha256": CONTINUATION_XML_SHA,
                "priorJournalSha256": CONTINUATION_JOURNAL_SHA,
                "priorPreflightSha256": CONTINUATION_PREFLIGHT_SHA,
            },
        )
    else:
        preset_name = f"VERA141_AUDIO_OUTPUT_{stamp}"
        recovery_path = evidence / f"{preset_name}.drp"
    render_dir = evidence / "render"
    render_dir.mkdir()
    base_name = f"vera-issue-141-audio-{stamp}"
    render_settings = {
        "ExportVideo": False,
        "ExportAudio": True,
        "AudioFormat": "wav",
        "AudioCodec": "lpcm",
        "AudioSampleRate": 48000,
        "AudioBitDepth": 16,
        "SelectAllFrames": True,
        "TargetDir": str(render_dir),
        "CustomName": base_name,
    }

    if continuation:
        if original_presets != preset_reads[1]:
            raise RuntimeError("Owned recovery preset is absent or duplicated")
        original_presets = preset_reads[0]
        original["presets"] = original_presets
        if set(preset_reads[1]) != set(original_presets) | {preset_name}:
            raise RuntimeError("Render preset list differs from pinned recovery set")
        recovery_hash = CONTINUATION_XML_SHA
    else:
        context()
        saved = call(project, "SaveAsNewRenderPreset", preset_name)
        listed = call(project, "GetRenderPresetList")
        if (
            saved is not True
            or preset_name in original_presets
            or listed.count(preset_name) != 1
        ):
            raise RuntimeError("Could not prove unique render-preset snapshot")
        context()
        exported = call(resolve, "ExportRenderPreset", preset_name, str(recovery_path))
        xml_path = recovery_path / f"{preset_name}.xml"
        if (
            exported is not True
            or recovery_path.is_symlink()
            or not recovery_path.is_dir()
            or xml_path.is_symlink()
            or not xml_path.is_file()
            or {p.name for p in recovery_path.iterdir()} != {xml_path.name}
            or not _inside(xml_path, evidence)
        ):
            raise RuntimeError("Could not retain owned render-preset recovery copy")
        recovery_hash = _sha256(xml_path)
    recovery_path = xml_path
    record(
        "RenderPresetRecovery",
        "verified",
        {"name": preset_name, "path": str(recovery_path), "sha256": recovery_hash},
    )

    settings_value = None
    settings_error = None
    context()
    try:
        settings_value = call(project, "SetRenderSettings", render_settings)
    except Exception as error:
        settings_error = error
    if settings_error is not None or settings_value is not True:
        reason = (
            "SetRenderSettings raised "
            f"{type(settings_error).__name__}: {settings_error}"
            if settings_error is not None
            else "SetRenderSettings refused the audio-only request"
        )
        try:
            restore_unqueued(reason)
        except Exception as error:
            record(
                "AudioOutput", "restoration-failure", f"{type(error).__name__}: {error}"
            )
            raise RuntimeError("Audio settings refused; recovery retained") from error
        return {
            "status": "settings-refused-restored",
            "journal": str(journal),
            "recoverySha256": recovery_hash,
        }

    try:
        state_after_settings = basic_state(project, original, [])
        if state_after_settings["presets"] != [*original_presets, preset_name] and set(
            state_after_settings["presets"]
        ) != set(original_presets) | {preset_name}:
            raise RuntimeError("Render preset list changed outside the owned snapshot")
        capture("configured", pinned)
        # Resolve output naming varies only by whether it appends the .wav suffix.
        expected_names = {base_name, base_name + ".wav"}
        if any((render_dir / name).exists() for name in expected_names):
            raise RuntimeError("Refuse to overwrite an existing test output")
    except Exception as error:
        try:
            restore_unqueued(
                f"post-settings verification failed: {type(error).__name__}: {error}"
            )
        except Exception as restore_error:
            record(
                "AudioOutput",
                "restoration-failure",
                f"{type(restore_error).__name__}: {restore_error}",
            )
            raise RuntimeError(
                "Post-settings refusal; recovery retained"
            ) from restore_error
        raise RuntimeError(
            "Post-settings verification failed; original settings restored"
        ) from error

    try:
        project = context()
    except Exception as error:
        try:
            restore_unqueued(
                f"prequeue context guard failed: {type(error).__name__}: {error}"
            )
        except Exception as restore_error:
            record(
                "AudioOutput",
                "restoration-failure",
                f"{type(restore_error).__name__}: {restore_error}",
            )
            raise RuntimeError(
                "Prequeue context refusal; recovery retained"
            ) from restore_error
        raise RuntimeError(
            "Prequeue context changed; original settings restored"
        ) from error
    job_id = None
    try:
        job_id = call(project, "AddRenderJob")
    except Exception as error:
        return restore_queued_idle(
            f"AddRenderJob raised {type(error).__name__}: {error}", None
        )
    job_id_owned = isinstance(job_id, str) and bool(job_id)
    try:
        jobs = call(project, "GetRenderJobList")
    except Exception as error:
        return restore_queued_idle(
            f"GetRenderJobList after queueing raised {type(error).__name__}: {error}",
            {"returnedJobId": job_id},
        )
    if (
        not job_id_owned
        or not isinstance(jobs, list)
        or len(jobs) != 1
        or not isinstance(jobs[0], dict)
        or jobs[0].get("JobId") != job_id
    ):
        return restore_queued_idle(
            "AddRenderJob did not create exactly one attributable job", jobs
        )

    job = jobs[0]
    output_name = job.get("OutputFilename")
    if (
        job.get("TargetDir") != str(render_dir)
        or job.get("IsExportVideo") is not False
        or job.get("IsExportAudio") is not True
        or job.get("AudioSampleRate") != 48000
        or job.get("AudioBitDepth") != 16
        or job.get("AudioCodec") != "lpcm"
        or output_name not in expected_names
    ):
        return restore_queued_idle(
            "Queued job differs from the exact audio-only request", job
        )
    target = render_dir / output_name
    if target.is_symlink() or target.exists() or not _inside(render_dir, evidence):
        return restore_queued_idle(
            "Queued output path is unsafe or already exists", str(target)
        )
    try:
        state_after_queue = basic_state(project, original, jobs)
        if preset_name not in state_after_queue["presets"]:
            raise RuntimeError("Owned recovery preset disappeared before rendering")
        context()
        started = call(project, "StartRendering", [job_id])
        if started is not True:
            return restore_queued_idle(
                "StartRendering refused the exact returned job ID",
                {"job": job, "return": started},
            )
    except Exception as error:
        return restore_queued_idle(
            f"postqueue validation/start failed: {type(error).__name__}: {error}",
            {"job": job},
        )

    deadline = time.monotonic() + timeout
    status = None
    while time.monotonic() < deadline:
        status = call(project, "GetRenderJobStatus", job_id)
        if not isinstance(status, dict):
            raise RuntimeError("Render status is unreadable; preserve the job")
        state = status.get("JobStatus")
        if state in TERMINAL:
            break
        if call(project, "IsRenderingInProgress") is not True:
            raise RuntimeError("Render stopped without a documented terminal status")
        time.sleep(min(0.1, max(0, deadline - time.monotonic())))
    else:
        pending = call(project, "GetRenderJobStatus", job_id)
        record("AudioOutput", "pending", {"jobId": job_id, "status": pending})
        return {
            "status": "pending-active-render",
            "jobId": job_id,
            "journal": str(journal),
            "recoveryPreset": str(recovery_path),
            "recoverySha256": recovery_hash,
        }

    if call(project, "IsRenderingInProgress") is not False:
        record("AudioOutput", "pending", {"jobId": job_id, "status": status})
        return {
            "status": "pending-active-render",
            "jobId": job_id,
            "journal": str(journal),
            "recoveryPreset": str(recovery_path),
            "recoverySha256": recovery_hash,
        }

    output_evidence = None
    output_error = None
    if status.get("JobStatus") in SUCCESS_TERMINAL:
        try:
            if (
                target.is_symlink()
                or not target.is_file()
                or not _inside(target, render_dir)
            ):
                raise RuntimeError(
                    "Rendered WAV is missing or outside its owned directory"
                )
            with wave.open(str(target), "rb") as reader:
                params = {
                    "channels": reader.getnchannels(),
                    "sampleWidthBytes": reader.getsampwidth(),
                    "sampleRate": reader.getframerate(),
                    "frames": reader.getnframes(),
                    "compression": reader.getcomptype(),
                    "durationSeconds": reader.getnframes() / reader.getframerate(),
                }
            if (
                params["channels"] < 1
                or params["sampleWidthBytes"] != 2
                or params["sampleRate"] != 48000
                or params["frames"] < 1
                or params["compression"] != "NONE"
            ):
                raise RuntimeError("Rendered WAV metadata differs from the request")
            output_evidence = {
                "path": str(target),
                "bytes": target.stat().st_size,
                "sha256": _sha256(target),
                "wave": params,
            }
            _write(evidence / "output.json", output_evidence)
        except Exception as error:
            output_error = error
            record("RenderedOutput", "failure", f"{type(error).__name__}: {error}")
    else:
        output_error = RuntimeError(f"Render ended with {status.get('JobStatus')}")

    try:
        restore(project, preset_name, original, jobs)
        _terminal_jobs, terminal_status = owned_terminal_job(project, job_id)
        if terminal_status != status:
            raise RuntimeError("Render terminal status changed before cleanup")
        context()
        deleted_job = call(project, "DeleteRenderJob", job_id)
        if deleted_job is not True or call(project, "GetRenderJobList") != []:
            raise RuntimeError("Could not remove the exact owned terminal render job")
        context()
        deleted_preset = call(project, "DeleteRenderPreset", preset_name)
        if (
            deleted_preset is not True
            or call(project, "GetRenderPresetList") != original_presets
        ):
            raise RuntimeError("Could not remove the exact owned recovery preset")
        final = basic_state(project, original, [])
        if final["presets"] != original_presets:
            raise RuntimeError("Render preset list did not return to its prior state")
        capture("postflight", pinned)
    except Exception as error:
        record(
            "AudioOutput",
            "restoration-or-cleanup-failure",
            f"{type(error).__name__}: {error}",
        )
        raise RuntimeError(
            "Render finished but restoration/cleanup is incomplete"
        ) from error

    if output_error is not None:
        record("AudioOutput", "render-refused-restored", str(output_error))
        return {
            "status": "render-failed-restored",
            "jobId": job_id,
            "jobStatus": status,
            "output": output_evidence,
            "journal": str(journal),
            "recoverySha256": recovery_hash,
        }
    record("AudioOutput", "complete", {"jobId": job_id, "output": output_evidence})
    return {
        "status": "render-complete-restored",
        "jobId": job_id,
        "jobStatus": status,
        "output": output_evidence,
        "journal": str(journal),
        "preflight": str(evidence / "preflight.json"),
        "postflight": str(evidence / "postflight.json"),
        "recoverySha256": recovery_hash,
    }
