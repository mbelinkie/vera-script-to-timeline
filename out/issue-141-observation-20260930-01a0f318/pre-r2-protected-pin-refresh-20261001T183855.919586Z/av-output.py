"""Guarded MOV/H264 output candidates and a stopped full-Matrix queue observation."""

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
READER_SHA256 = "9b6977747a1f3decf957ead6134f10fc4f597bf9d0c3dc5c081b7bf2671879a4"
CONTINUATION_RECORD_SHA256 = (
    "b169854fa9e6f9509dc22e1b8aa41e2d7e63b79baf74909c3246302c29fedc36"
)
APPLIED_SETTINGS_RECORD_SHA256 = (
    "8852c355e605a0d4e0be62f554f06f8fcdaca7a29e6a39b877633728928592df"
)
OWNED_UNSTARTED_JOB_ID = "9c4f9ad9-9acf-4c60-bac2-fb7cc9269ebd"
FULL_MATRIX_QUEUE_ONLY_ACTION = "av-output-full-matrix-queue-only"
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
PROTECTED_SOURCE_UID = "be5f1584-f0c4-4dd9-988b-73f3167e77d1"
PROTECTED_SOURCE_NAME = "semi1b.mp4"
PROTECTED_SOURCE_STATUS = "protected-locator-not-accessed"


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


def _leaf_diffs(before, after, path=()):
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            if key not in before or key not in after:
                yield ((*path, key), before.get(key), after.get(key))
            else:
                yield from _leaf_diffs(before[key], after[key], (*path, key))
    elif isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            yield ((*path, "length"), len(before), len(after))
        else:
            for index, (left, right) in enumerate(zip(before, after, strict=True)):
                yield from _leaf_diffs(left, right, (*path, index))
    elif before != after:
        yield (path, before, after)


def _verify_pool_out_delta(before, after, *, proxy_uid, timeline_uid):
    if (
        before.get("selectedTimelineUid") != timeline_uid
        or after.get("selectedTimelineUid") != timeline_uid
        or before.get("timelinePasses") != after.get("timelinePasses")
        or len(before.get("poolPasses", [])) != 2
        or len(after.get("poolPasses", [])) != 2
    ):
        raise RuntimeError("Applied-settings pair identity or pass count changed")
    expected_paths = set()
    for pass_index in range(2):
        left = before["poolPasses"][pass_index]
        right = after["poolPasses"][pass_index]
        left_items = [
            i
            for i, row in enumerate(left.get("items", []))
            if row.get("uid") == proxy_uid
        ]
        right_items = [
            i
            for i, row in enumerate(right.get("items", []))
            if row.get("uid") == proxy_uid
        ]
        left_maps = [
            i
            for i, row in enumerate(left.get("timelineMappings", []))
            if row.get("timelineUid", {}).get("value") == timeline_uid
            and row.get("poolItemUid", {}).get("value") == proxy_uid
        ]
        right_maps = [
            i
            for i, row in enumerate(right.get("timelineMappings", []))
            if row.get("timelineUid", {}).get("value") == timeline_uid
            and row.get("poolItemUid", {}).get("value") == proxy_uid
        ]
        if any(
            len(rows) != 1 for rows in (left_items, right_items, left_maps, right_maps)
        ):
            raise RuntimeError(
                "Expected one Matrix proxy and mapping in each pool pass"
            )
        expected_paths.update(
            {
                (
                    "poolPasses",
                    pass_index,
                    "items",
                    left_items[0],
                    "evidence",
                    "GetClipProperty",
                    "value",
                    "Out",
                ),
                (
                    "poolPasses",
                    pass_index,
                    "timelineMappings",
                    left_maps[0],
                    "poolItemProperties",
                    "value",
                    "Out",
                ),
            }
        )
        for pair, row_index, leaf in (
            (left, left_items[0], "items"),
            (right, right_items[0], "items"),
        ):
            value = (
                pair[leaf][row_index]
                .get("evidence", {})
                .get("GetClipProperty", {})
                .get("value", {})
                .get("Out")
            )
            if value != ("" if pair is left else "00:00:08:00"):
                raise RuntimeError("Matrix proxy Out value is not the pinned change")
        for pair, row_index in ((left, left_maps[0]), (right, right_maps[0])):
            value = (
                pair["timelineMappings"][row_index]
                .get("poolItemProperties", {})
                .get("value", {})
                .get("Out")
            )
            if value != ("" if pair is left else "00:00:08:00"):
                raise RuntimeError("Matrix mapping Out value is not the pinned change")
    actual = {path for path, _before, _after in _leaf_diffs(before, after)}
    if actual != expected_paths:
        raise RuntimeError("Applied-settings pair has an unexpected full-state delta")


def _owned_checkpoint(path, output):
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        return False
    try:
        if not path.resolve().is_relative_to(output.resolve()):
            return False
    except OSError:
        return False
    parent = path.parent
    while parent != output:
        if parent == parent.parent or parent.is_symlink():
            return False
        parent = parent.parent
    return True


def _iter_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_dicts(child)


def _protected_source_in_matrix(matrix):
    """Return source-bearing Matrix records that identify protected media."""
    found = []
    for node in _iter_dicts(matrix):
        uid = node.get("GetUniqueId", {}).get("value")
        name = node.get("GetName", {}).get("value")
        props = node.get("GetClipProperty", {}).get("value", {})
        if (
            uid == PROTECTED_SOURCE_UID
            or name == PROTECTED_SOURCE_NAME
            or (
                isinstance(props, dict)
                and (
                    props.get("File Name") == PROTECTED_SOURCE_NAME
                    or props.get("Clip Name") == PROTECTED_SOURCE_NAME
                    or Path(str(props.get("File Path", ""))).name
                    == PROTECTED_SOURCE_NAME
                )
            )
        ):
            found.append(node)
    return found


def _verify_matrix_excludes_protected(timeline):
    if _protected_source_in_matrix(timeline):
        raise RuntimeError(
            "Protected real source semi1b.mp4 is present in the Matrix timeline"
        )


def _verify_protected_pool_exception(row):
    evidence = row.get("evidence", {})
    if (
        row.get("uid") != PROTECTED_SOURCE_UID
        or row.get("name") != {"value": PROTECTED_SOURCE_NAME}
        or evidence.get("GetUniqueId") != {"value": PROTECTED_SOURCE_UID}
        or evidence.get("GetName") != {"value": PROTECTED_SOURCE_NAME}
        or evidence.get("sourceBytes")
        != {"status": PROTECTED_SOURCE_STATUS}
        or any(
            key in evidence.get("sourceBytes", {})
            for key in ("sha256", "hashMatches")
        )
    ):
        raise RuntimeError("Protected pool source exception is not exact")


def _drop_unstarted(resolve, config, *, probe, reader, output, pin, expected_sources):
    attempt_dir = Path(config.get("queuedAttemptPath", ""))
    attempt_hash = config.get("queuedAttemptSha256")
    journal_hash = config.get("queuedJournalSha256")
    if (
        not attempt_dir.is_absolute()
        or attempt_dir.is_symlink()
        or attempt_dir.parent.resolve() != output.resolve()
        or attempt_dir.name != "av-output-20261001T115327.250767Z"
        or not attempt_dir.is_dir()
    ):
        raise RuntimeError("Exact owned queued-attempt directory required")
    final_path = attempt_dir / "final-local-result.json"
    journal_path = attempt_dir / "journal.jsonl"
    if (
        final_path.is_symlink()
        or not final_path.is_file()
        or _sha(final_path) != attempt_hash
        or journal_path.is_symlink()
        or not journal_path.is_file()
        or _sha(journal_path) != journal_hash
    ):
        raise RuntimeError("Queued-attempt evidence hash mismatch")
    final = json.loads(final_path.read_text(encoding="utf-8"))
    result = final.get("result", {})
    job_id, job = result.get("jobId"), result.get("job")
    if (
        final.get("kind") != "av-output-final-local-result"
        or result.get("status") != "queued-job-metadata-unknown-recovery-retained"
        or result.get("journal") != str(journal_path)
        or job_id != OWNED_UNSTARTED_JOB_ID
        or not isinstance(job, dict)
        or job.get("JobId") != job_id
        or result.get("snapshot") is None
    ):
        raise RuntimeError("Queued-attempt result does not bind one retained job")
    journal = [
        json.loads(line)
        for line in journal_path.read_text(encoding="utf-8").splitlines()
    ]
    add_returns = [
        row
        for row in journal
        if row.get("method") == "AddRenderJob" and row.get("phase") == "return"
    ]
    if (
        len(add_returns) != 1
        or add_returns[0].get("value") != job_id
        or any(row.get("method") == "StartRendering" for row in journal)
    ):
        raise RuntimeError("Original journal does not prove an unstarted owned job")
    target_dir = Path(job.get("TargetDir", ""))
    target = target_dir / str(job.get("OutputFilename", ""))
    if (
        target_dir.is_symlink()
        or not target_dir.is_dir()
        or target_dir.name != "render"
        or target_dir.parent.parent.resolve() != output.resolve()
        or not target_dir.parent.name.startswith("av-output-")
        or target.exists()
        or target.is_symlink()
    ):
        raise RuntimeError("Owned render destination is unsafe or already populated")

    evidence_dir = (
        output / f"av-output-drop-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S.%fZ')}"
    )
    evidence_dir.mkdir()
    journal_out = evidence_dir / "journal.jsonl"
    journal_out.touch()

    def record(method, phase, value):
        with journal_out.open("a", encoding="utf-8") as stream:
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

    identity = {"projectId": reader.PROJECT_ID, "projectName": config["projectName"]}
    project = reader._context(resolve, config, identity, probe, reader.MATRIX_UID)
    visible = {
        "formatCodec": project.GetCurrentRenderFormatAndCodec(),
        "mode": project.GetCurrentRenderMode(),
        "presets": project.GetRenderPresetList(),
    }
    if (
        resolve.GetProductName() != "DaVinci Resolve Studio"
        or resolve.GetVersion() != reader.BUILD
        or visible["formatCodec"] != {"format": "mov", "codec": "H264"}
        or visible["mode"] != 1
        or not isinstance(visible["presets"], list)
        or project.IsRenderingInProgress() is not False
        or project.GetRenderJobList() != [job]
    ):
        raise RuntimeError("Exact idle Resolve state and sole retained job required")
    pair = reader._read_pair(
        resolve, config, identity, expected_sources, reader.MATRIX_UID, probe
    )
    pair_path = evidence_dir / "before-pair.json"
    pair_path.write_text(
        json.dumps(pair, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    record("FullPair", "before", {"path": str(pair_path), "sha256": _sha(pair_path)})
    actual_state, actual_pool = reader._validate_read_pair(pair, probe)
    pinned_state, pinned_pool = reader._validate_read_pair(pin, probe)
    if actual_state != pinned_state or actual_pool != pinned_pool:
        raise RuntimeError(
            "Fresh complete checkpoint differs from live content/source state"
        )
    if (
        project.GetRenderJobList() != [job]
        or project.IsRenderingInProgress() is not False
    ):
        raise RuntimeError(
            "Render queue or active state changed before owned-job removal"
        )
    record("DeleteRenderJob", "request", [job_id])
    removed = project.DeleteRenderJob(job_id)
    record("DeleteRenderJob", "return", removed)
    if removed is not True:
        raise RuntimeError("Owned unstarted job removal refused; no retry")
    if project.GetRenderJobList() != []:
        raise RuntimeError("Queue did not become empty after owned-job removal")
    after = reader._read_pair(
        resolve, config, identity, expected_sources, reader.MATRIX_UID, probe
    )
    after_path = evidence_dir / "after-pair.json"
    after_path.write_text(
        json.dumps(after, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    record("FullPair", "after", {"path": str(after_path), "sha256": _sha(after_path)})
    after_state, after_pool = reader._validate_read_pair(after, probe)
    if after_state != actual_state or after_pool != actual_pool:
        raise RuntimeError("Content/source state drifted during owned-job removal")
    visible_after = {
        "formatCodec": project.GetCurrentRenderFormatAndCodec(),
        "mode": project.GetCurrentRenderMode(),
        "presets": project.GetRenderPresetList(),
    }
    if visible_after != visible or project.GetRenderJobList() != []:
        raise RuntimeError("Visible render state drifted during owned-job removal")
    return {
        "status": "owned-unstarted-job-removed",
        "jobId": job_id,
        "beforePair": str(pair_path),
        "afterPair": str(after_path),
        "journal": str(journal_out),
    }


def _run(resolve, config, *, probe):
    reader = _load_reader(probe)
    root = Path(probe.ROOT).resolve()
    output = Path(config.get("outputDir", ""))
    media, expected_sources = reader._manifest(config, root, probe)
    pin_path = Path(config.get("checkpointPath", ""))
    pin_hash = config.get("checkpointSha256")
    action = config.get("action")
    queue_from_fresh_checkpoint = action == "av-output-queue-from-fresh-checkpoint"
    full_matrix_queue_only = action == FULL_MATRIX_QUEUE_ONLY_ACTION
    full_matrix = action in {"av-output-full-matrix", FULL_MATRIX_QUEUE_ONLY_ACTION}
    queue_from_settings = action == "av-output-queue-from-settings"
    queue_from_applied_settings = queue_from_settings or queue_from_fresh_checkpoint
    if (
        action
        not in {
            "av-output",
            "av-output-continue",
            "av-output-queue-from-settings",
            "av-output-queue-from-fresh-checkpoint",
            "av-output-full-matrix",
            FULL_MATRIX_QUEUE_ONLY_ACTION,
            "av-output-drop-unstarted-owned-job",
        }
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
        or (
            pin_path.parent.resolve() != output.resolve()
            and not (
                (
                    queue_from_fresh_checkpoint
                    or full_matrix
                    or action == "av-output-drop-unstarted-owned-job"
                )
                and _owned_checkpoint(pin_path, output)
            )
        )
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
    _verify_matrix_excludes_protected(reader._timeline(baseline, reader.MATRIX_UID))
    if action == "av-output-drop-unstarted-owned-job":
        return _drop_unstarted(
            resolve,
            config,
            probe=probe,
            reader=reader,
            output=output,
            pin=pin,
            expected_sources=expected_sources,
        )
    continuation = config.get("action") in {
        "av-output-continue",
        "av-output-queue-from-settings",
        "av-output-queue-from-fresh-checkpoint",
    }
    continuation_record = None
    continuation_xml = None
    continuation_preset = None
    applied_record = None
    applied_before = None
    applied_after = None
    applied_visible = None
    render_dir = None
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
        historical_checkpoint = continuation_record.get("checkpoint", {})
        if queue_from_fresh_checkpoint:
            historical_path = output / historical_checkpoint.get("path", "")
            if (
                historical_path.name != historical_checkpoint.get("path")
                or historical_path.is_symlink()
                or not historical_path.is_file()
                or historical_path.parent.resolve() != output.resolve()
                or _sha(historical_path) != historical_checkpoint.get("sha256")
                or pin_hash == historical_checkpoint.get("sha256")
            ):
                raise RuntimeError(
                    "Fresh checkpoint is stale or historical provenance changed"
                )
        elif historical_checkpoint != {"path": pin_path.name, "sha256": pin_hash}:
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
    if queue_from_applied_settings:
        record_path = Path(config.get("appliedSettingsRecordPath", ""))
        if (
            record_path.is_symlink()
            or not record_path.is_file()
            or record_path.parent.resolve() != output.resolve()
            or record_path.name != "av-applied-settings-record.json"
            or _sha(record_path) != APPLIED_SETTINGS_RECORD_SHA256
            or config.get("appliedSettingsRecordSha256")
            != APPLIED_SETTINGS_RECORD_SHA256
        ):
            raise RuntimeError("Pinned applied-settings record required")
        applied_record = json.loads(record_path.read_text(encoding="utf-8"))
        prior_name = "av-output-20261001T063250.006372Z"
        prior_dir = output / prior_name
        prior_paths = {
            "priorAttemptJournal": prior_dir / "journal.jsonl",
            "priorFinalResult": prior_dir / "final-local-result.json",
            "beforePair": prior_dir / "full-pair-002.json",
            "afterPair": prior_dir / "full-pair-003.json",
        }
        expected_refs = {
            "priorAttemptJournal": f"{prior_name}/journal.jsonl",
            "priorFinalResult": f"{prior_name}/final-local-result.json",
            "beforePair": f"{prior_name}/full-pair-002.json",
            "afterPair": f"{prior_name}/full-pair-003.json",
        }
        if (
            applied_record.get("kind")
            != "issue-141-av-applied-settings-queue-checkpoint"
            or applied_record.get("priorAttempt") != prior_name
            or applied_record.get("setter") != "SetRenderSettings"
            or applied_record.get("setterReturned") is not True
            or applied_record.get("noReplay")
            != ["SaveAsNewRenderPreset", "ExportRenderPreset", "SetRenderSettings"]
            or applied_record.get("neverDispatched")
            != [
                "AddRenderJob",
                "StartRendering",
                "LoadRenderPreset",
                "DeleteRenderJob",
                "DeleteRenderPreset",
            ]
        ):
            raise RuntimeError(
                "Applied-settings record is not the pinned stopped state"
            )
        for key, path in prior_paths.items():
            ref = applied_record.get(key, {})
            if (
                path.is_symlink()
                or not path.is_file()
                or ref.get("path") != expected_refs[key]
                or ref.get("sha256") != _sha(path)
            ):
                raise RuntimeError(f"Applied-settings source changed: {key}")
        if (
            queue_from_settings
            and applied_record.get("beforePair", {}).get("sha256") != pin_hash
        ):
            raise RuntimeError(
                "Applied-settings pre-pair differs from selected checkpoint"
            )
        applied_before = json.loads(
            prior_paths["beforePair"].read_text(encoding="utf-8")
        )
        applied_after = json.loads(prior_paths["afterPair"].read_text(encoding="utf-8"))
        first_pair_path = prior_dir / "full-pair-001.json"
        if (
            first_pair_path.is_symlink()
            or not first_pair_path.is_file()
            or (queue_from_settings and _sha(first_pair_path) != pin_hash)
        ):
            raise RuntimeError("Applied-settings first pair differs from checkpoint")
        _verify_pool_out_delta(
            applied_before,
            applied_after,
            proxy_uid=applied_record.get("changedPoolProxyUid"),
            timeline_uid=applied_record.get("changedTimelineUid"),
        )
        previous_result = json.loads(prior_paths["priorFinalResult"].read_text())
        if (
            previous_result.get("failure")
            != "RuntimeError: Fresh full content/source state differs from pin"
        ):
            raise RuntimeError("Applied-settings attempt has an unexpected stop reason")
        journal_entries = [
            json.loads(line)
            for line in prior_paths["priorAttemptJournal"].read_text().splitlines()
        ]
        setters = [e for e in journal_entries if e.get("method") == "SetRenderSettings"]
        if (
            len(setters) != 2
            or setters[0].get("phase") != "request"
            or setters[1].get("phase") != "return"
            or setters[1].get("value") is not True
            or setters[0].get("value") != [applied_record.get("appliedSettings")]
            or any(
                e.get("method")
                in {
                    "SaveAsNewRenderPreset",
                    "ExportRenderPreset",
                    "AddRenderJob",
                    "StartRendering",
                    "LoadRenderPreset",
                    "DeleteRenderJob",
                    "DeleteRenderPreset",
                }
                for e in journal_entries
            )
        ):
            raise RuntimeError(
                "Prior mutation journal does not match applied-settings record"
            )
        state_methods = {
            "GetCurrentRenderFormatAndCodec": "formatCodec",
            "GetCurrentRenderMode": "mode",
            "GetRenderJobList": "jobs",
            "IsRenderingInProgress": "rendering",
            "GetRenderPresetList": "presets",
        }
        values = {key: [] for key in state_methods}
        for entry in journal_entries:
            if entry.get("method") == "SetRenderSettings":
                break
            if entry.get("method") in values and entry.get("phase") == "return":
                values[entry["method"]].append(entry.get("value"))
        applied_visible = {}
        for method, key in state_methods.items():
            if len(values[method]) != 2 or values[method][0] != values[method][1]:
                raise RuntimeError("Prior visible state lacks equal adjacent reads")
            applied_visible[key] = values[method][0]
        if (
            applied_visible["formatCodec"] != {"format": "mov", "codec": "H264"}
            or applied_visible["mode"] != 1
            or applied_visible["jobs"] != []
            or applied_visible["rendering"] is not False
            or applied_visible["presets"].count(continuation_preset) != 1
        ):
            raise RuntimeError(
                "Prior visible state was not the stopped owned-preset state"
            )
        applied_settings = applied_record.get("appliedSettings", {})
        expected_static = {
            "AudioBitDepth": 24,
            "AudioCodec": "lpcm",
            "AudioSampleRate": 48000,
            "ExportAudio": True,
            "ExportVideo": True,
            "FormatHeight": 360,
            "FormatWidth": 640,
            "FrameRate": 25.0,
            "MarkIn": 0,
            "MarkOut": 200,
            "SelectAllFrames": False,
        }
        if any(applied_settings.get(k) != v for k, v in expected_static.items()):
            raise RuntimeError("Applied render settings differ from bounded candidate")
        render_dir = Path(applied_settings.get("TargetDir", ""))
        if (
            not isinstance(applied_settings.get("CustomName"), str)
            or applied_settings["CustomName"]
            != f"vera141-av-{prior_name.removeprefix('av-output-')}"
            or render_dir.is_symlink()
            or not render_dir.is_dir()
            or render_dir.parent.resolve() != prior_dir.resolve()
            or render_dir.name != "render"
            or any(render_dir.iterdir())
        ):
            raise RuntimeError(
                "Pinned applied-settings output directory is not safely empty"
            )
    expected_imported = {str(media / name) for name in IMPORTED_MEDIA}
    if not expected_imported <= set(expected_sources):
        raise RuntimeError("Manifest lacks one of the six approved imported sources")
    proxy_uids = {
        row.get("poolItemUid", {}).get("value")
        for row in base_pool.get("timelineMappings", [])
    }
    if PROTECTED_SOURCE_UID in proxy_uids:
        raise RuntimeError("Protected source UID is mapped as a Matrix timeline proxy")
    observed_imported = set()
    protected_rows = []
    for row in base_pool.get("items", []):
        evidence = row.get("evidence", {})
        props = evidence.get("GetClipProperty", {}).get("value", {})
        source = props.get("File Path")
        uid = row.get("uid")
        byte_evidence = evidence.get("sourceBytes", {})
        if uid == PROTECTED_SOURCE_UID:
            _verify_protected_pool_exception(row)
            protected_rows.append(row)
            continue
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
    if len(protected_rows) > 1:
        raise RuntimeError("Protected source UID is duplicated in the media pool")
    expected_states = [applied_after if queue_from_settings else pin]

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

    def fresh_pair(allowed_jobs=None, *, return_match=False, return_capture=False):
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
        _verify_matrix_excludes_protected(reader._timeline(timeline, reader.MATRIX_UID))
        matches = []
        for expected_index, expected_pair in enumerate(expected_states):
            expected_timeline, expected_pool = reader._validate_read_pair(
                expected_pair, probe
            )
            if timeline == expected_timeline and pool == expected_pool:
                matches.append(expected_index)
        if not matches:
            raise RuntimeError("Fresh full content/source state differs from pin")
        if return_capture:
            return project, pair_path
        return (project, pair, matches[0]) if return_match else project

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
    matrix_settings = None
    matrix_bounds = None
    if full_matrix:
        matrix_pin = reader._timeline(baseline, reader.MATRIX_UID)
        raw_settings = matrix_pin.get("GetSettings", {}).get("value", {})
        try:
            width = int(raw_settings["timelineResolutionWidth"])
            height = int(raw_settings["timelineResolutionHeight"])
            frame_rate = float(raw_settings["timelineFrameRate"])
            start_frame = matrix_pin["GetStartFrame"]["value"]
            end_frame = matrix_pin["GetEndFrame"]["value"]
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError(
                "Fresh Matrix dimensions, rate, or bounds are unreadable"
            ) from error
        if (
            width <= 0
            or height <= 0
            or frame_rate <= 0
            or not isinstance(start_frame, int)
            or not isinstance(end_frame, int)
            or end_frame < start_frame
        ):
            raise RuntimeError("Fresh Matrix dimensions, rate, or bounds are invalid")
        if full_matrix_queue_only and (width, height, frame_rate) != (1920, 1080, 25.0):
            raise RuntimeError("Queue-only full Matrix requires 1920x1080 at 25 fps")
        resolutions = call(project, "GetRenderResolutions", "mov", "H264")
        if not isinstance(resolutions, list) or not any(
            row.get("Width") == width and row.get("Height") == height
            for row in resolutions
            if isinstance(row, dict)
        ):
            raise RuntimeError("Matrix resolution is not supported for MOV/H264")
        matrix_settings = {
            "width": width,
            "height": height,
            "frameRate": frame_rate,
            "resolutions": resolutions,
        }
        matrix_bounds = {"startFrame": start_frame, "endFrame": end_frame}
    if continuation:
        preset = continuation_preset
        if queue_from_applied_settings:
            expected_visible = applied_visible
        else:
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
    if not queue_from_applied_settings:
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

    queue_before_path = None
    if queue_from_applied_settings:
        settings = applied_settings
        fresh_pair()
        context()
    else:
        if config.get("sampleRateHz") != 48000:
            raise RuntimeError("Explicit 48 kHz calibration is required")
        settings = {
            "ExportVideo": True,
            "ExportAudio": True,
            "AudioCodec": "lpcm",
            "AudioSampleRate": 48000,
            "AudioBitDepth": 24,
            "FormatWidth": matrix_settings["width"] if full_matrix else 640,
            "FormatHeight": matrix_settings["height"] if full_matrix else 360,
            "FrameRate": matrix_settings["frameRate"] if full_matrix else 25.0,
            "SelectAllFrames": full_matrix,
            "TargetDir": str(render_dir),
            "CustomName": f"vera141-av-{stamp}",
        }
        if not full_matrix:
            settings.update({"MarkIn": 0, "MarkOut": 200})
        if full_matrix_queue_only:
            project, queue_before_path = fresh_pair(return_capture=True)
        else:
            fresh_pair()
        context()
        settings_result = call(project, "SetRenderSettings", settings)
        if full_matrix_queue_only:
            fresh_pair()
        if settings_result is not True:
            return {
                "status": "settings-refused-recovery-retained",
                "journal": str(journal),
                "snapshot": str(xml),
            }
    configured = state(project)
    expected_configured_presets = (
        original["presets"] if continuation else [*original["presets"], preset]
    )
    if configured["presets"] != expected_configured_presets:
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
        or job.get("FormatWidth") != (matrix_settings["width"] if full_matrix else 640)
        or job.get("FormatHeight")
        != (matrix_settings["height"] if full_matrix else 360)
        or job.get("FrameRate")
        not in (
            {
                str(matrix_settings["frameRate"]),
                matrix_settings["frameRate"],
                int(matrix_settings["frameRate"])
                if matrix_settings["frameRate"].is_integer()
                else matrix_settings["frameRate"],
                str(int(matrix_settings["frameRate"]))
                if matrix_settings["frameRate"].is_integer()
                else str(matrix_settings["frameRate"]),
            }
            if full_matrix
            else {"25", 25}
        )
        or (
            not full_matrix_queue_only
            and job.get("MarkIn") != (matrix_bounds["startFrame"] if full_matrix else 0)
        )
        or (
            not full_matrix_queue_only
            and job.get("MarkOut")
            != (matrix_bounds["endFrame"] if full_matrix else 200)
        )
        or job.get("TargetDir") != str(render_dir)
        or job.get("OutputFilename") not in {expected_name, settings["CustomName"]}
    ):
        if full_matrix_queue_only:
            _project, after_pair_path = fresh_pair(queued, return_capture=True)
            queued_endpoints = {
                "MarkIn": job.get("MarkIn"),
                "MarkOut": job.get("MarkOut"),
                "timelineStartFrame": matrix_bounds["startFrame"],
                "timelineEndFrame": matrix_bounds["endFrame"],
                "selectionMode": "SelectAllFrames",
                "endpointSemantics": "diagnostic-only; inclusive/exclusive unknown",
            }
            record("QueuedEndpoints", "observed", queued_endpoints)
            return {
                "status": "queued-job-metadata-unknown-recovery-retained",
                "jobId": job_id,
                "job": job,
                "queuedEndpoints": queued_endpoints,
                "beforePair": str(queue_before_path),
                "beforePairSha256": _sha(queue_before_path),
                "afterPair": str(after_pair_path),
                "afterPairSha256": _sha(after_pair_path),
                "journal": str(journal),
                "snapshot": str(xml),
            }
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

    if full_matrix_queue_only:
        # SelectAllFrames ignores requested marks; endpoint inclusivity is
        # undocumented, so retain the returned values without interpreting them.
        queued_endpoints = {
            "MarkIn": job.get("MarkIn"),
            "MarkOut": job.get("MarkOut"),
            "timelineStartFrame": matrix_bounds["startFrame"],
            "timelineEndFrame": matrix_bounds["endFrame"],
            "selectionMode": "SelectAllFrames",
            "endpointSemantics": "diagnostic-only; inclusive/exclusive unknown",
        }
        project, after_pair_path = fresh_pair(queued, return_capture=True)
        record("QueuedEndpoints", "observed", queued_endpoints)
        if any(type(job.get(key)) is not int for key in ("MarkIn", "MarkOut")):
            return {
                "status": "queued-job-endpoints-unknown-recovery-retained",
                "jobId": job_id,
                "job": job,
                "queuedEndpoints": queued_endpoints,
                "beforePair": str(queue_before_path),
                "beforePairSha256": _sha(queue_before_path),
                "afterPair": str(after_pair_path),
                "afterPairSha256": _sha(after_pair_path),
                "journal": str(journal),
                "snapshot": str(xml),
            }
        context(queued)
        if (
            project.GetRenderJobList() != [job]
            or project.IsRenderingInProgress() is not False
        ):
            raise RuntimeError(
                "Queued full-Matrix job or idle state changed before stop"
            )
        return {
            "status": "full-matrix-queued-unstarted-recovery-retained",
            "action": FULL_MATRIX_QUEUE_ONLY_ACTION,
            "jobId": job_id,
            "job": job,
            "queuedEndpoints": queued_endpoints,
            "beforePair": str(queue_before_path),
            "beforePairSha256": _sha(queue_before_path),
            "afterPair": str(after_pair_path),
            "afterPairSha256": _sha(after_pair_path),
            "snapshotXml": str(xml),
            "snapshotSha256": _sha(xml),
            "journal": str(journal),
            "neverDispatched": [
                "StartRendering",
                "GetRenderJobStatus",
                "DeleteRenderJob",
                "DeleteRenderPreset",
            ],
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
        time.sleep(min(0.1, max(0, deadline - time.monotonic())))
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
        or video[0].get("width") != (matrix_settings["width"] if full_matrix else 640)
        or video[0].get("height") != (matrix_settings["height"] if full_matrix else 360)
        or video[0].get("r_frame_rate")
        not in (
            {f"{matrix_settings['frameRate']}/1", str(matrix_settings["frameRate"])}
            | (
                {
                    f"{int(matrix_settings['frameRate'])}/1",
                    str(int(matrix_settings["frameRate"])),
                }
                if matrix_settings["frameRate"].is_integer()
                else set()
            )
            if full_matrix
            else {"25/1"}
        )
        or video[0].get("nb_frames")
        not in (
            {
                str(matrix_bounds["endFrame"] - matrix_bounds["startFrame"] + 1),
                matrix_bounds["endFrame"] - matrix_bounds["startFrame"] + 1,
            }
            if full_matrix
            else {"201", 201}
        )
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
    if not restored:
        raise RuntimeError(
            "Visible restoration/content verification failed; retain job and XML"
        )
    restored_pool_state = "pinned-pre-settings"
    only_pool_out_remains = False
    if queue_from_settings:
        expected_states = [pin, applied_after]
        project, restored_pair, pair_match = fresh_pair(queued, return_match=True)
        restored_pool_state = (
            "pinned-pre-settings" if pair_match == 0 else "verified-post-settings"
        )
        only_pool_out_remains = pair_match == 1
        record(
            "RestoredPair",
            "complete-state-accepted",
            {
                "match": restored_pool_state,
                "onlyPoolOutChangeRemains": only_pool_out_remains,
                "sha256": _sha(evidence_dir / f"full-pair-{pair_number:03d}.json"),
            },
        )
        expected_states = [restored_pair]
    else:
        fresh_pair(queued)
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
        **(
            {
                "restoredPoolState": restored_pool_state,
                "onlyPoolOutChangeRemains": only_pool_out_remains,
            }
            if queue_from_settings
            else {}
        ),
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
