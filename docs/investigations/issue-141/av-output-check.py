"""Fake-only checks for the guarded MOV/H264 output candidate."""

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("av_output", HERE / "av-output.py")
av = importlib.util.module_from_spec(spec)
spec.loader.exec_module(av)
reader_spec = importlib.util.spec_from_file_location(
    "av_reader", HERE / "r4-range-repair.py"
)
reader = importlib.util.module_from_spec(reader_spec)
reader_spec.loader.exec_module(reader)

assert av.READER_SHA256 == hashlib.sha256(
    (HERE / "r4-range-repair.py").read_bytes()
).hexdigest()


class Timeline:
    def __init__(self, uid, name):
        self.uid, self.name = uid, name

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name


class Project:
    def __init__(self, mode, timelines):
        self.mode = mode
        self.timelines = timelines
        self.selected = timelines[0]
        self.settings = {"prior": True}
        self.presets = ["Existing"]
        self.jobs = []
        self.active = False
        self.started = []
        self.mutations = []
        self.setting_calls = []
        self.status = "Queued"

    def GetUniqueId(self):
        return reader.PROJECT_ID

    def GetName(self):
        return "VERA Issue 141 Synthetic Probe fake"

    def GetCurrentTimeline(self):
        return self.selected

    def GetTimelineCount(self):
        return len(self.timelines)

    def GetTimelineByIndex(self, index):
        return self.timelines[index - 1]

    def GetRenderJobList(self):
        return list(self.jobs)

    def GetCurrentRenderFormatAndCodec(self):
        if (
            self.mode in {"unknown-format", "full-queue-only-unknown-format"}
            and self.settings.get("ExportVideo") is True
        ):
            return {"format": "unknown", "codec": ""}
        return {"format": "mov", "codec": "H264"}

    def GetCurrentRenderMode(self):
        return 1

    def IsRenderingInProgress(self):
        return self.active

    def GetRenderPresetList(self):
        return list(self.presets)

    def GetRenderResolutions(self, fmt, codec):
        if self.mode in {
            "full-unsupported-resolution",
            "full-queue-only-unsupported-resolution",
        }:
            return [{"Width": 1280, "Height": 720}]
        return [{"Width": 1920, "Height": 1080}]

    def SaveAsNewRenderPreset(self, name):
        self.mutations.append("SaveAsNewRenderPreset")
        self.presets.append(name)
        return True

    def LoadRenderPreset(self, name):
        self.settings = {"prior": True}
        return True

    def DeleteRenderPreset(self, name):
        self.presets.remove(name)
        return True

    def DeleteRenderJob(self, job_id):
        if self.mode.startswith("drop-"):
            self.mutations.append("DeleteRenderJob")
        self.jobs.clear()
        return self.mode != "drop-delete-false"

    def SetRenderSettings(self, settings):
        self.mutations.append("SetRenderSettings")
        self.setting_calls.append(dict(settings))
        self.settings = dict(settings)
        return self.mode not in {"settings-false", "full-queue-only-settings-false"}

    def AddRenderJob(self):
        self.mutations.append("AddRenderJob")
        settings = self.settings
        job = {
            "JobId": "owned-job",
            "TargetDir": settings["TargetDir"],
            "OutputFilename": settings["CustomName"] + ".mov",
            "IsExportVideo": True,
            "IsExportAudio": True,
            "VideoFormat": "QuickTime",
            "VideoCodec": "H264",
            "AudioCodec": "lpcm",
            "AudioSampleRate": 48000,
            "AudioBitDepth": 24,
            "FormatWidth": settings.get("FormatWidth", 640),
            "FormatHeight": settings.get("FormatHeight", 360),
            "FrameRate": str(int(settings.get("FrameRate", 25)))
            if float(settings.get("FrameRate", 25)).is_integer()
            else str(settings.get("FrameRate")),
            "MarkIn": settings.get("MarkIn", 0),
            "MarkOut": settings.get(
                "MarkOut", 9200 if settings.get("SelectAllFrames") else 200
            ),
        }
        if self.mode == "full-wrong-range":
            job["MarkOut"] -= 1
        if self.mode == "full-queue-only-end-minus-one":
            job["MarkOut"] -= 1
        if self.mode == "full-queue-only-end-plus-one":
            job["MarkOut"] += 1
        if self.mode == "full-queue-only-end-noninteger":
            job["MarkOut"] = "9201"
        if self.mode == "full-wrong-dimensions":
            job["FormatWidth"] -= 1
        if self.mode in {"unknown-metadata", "queue-metadata-refusal"}:
            job.pop("AudioSampleRate")
        self.jobs.append(job)
        return "owned-job"

    def StartRendering(self, ids):
        self.mutations.append("StartRendering")
        self.started.append(ids)
        if self.mode in {"timeout", "full-continuation-timeout"}:
            self.active = True
            return True
        if self.mode == "start-false":
            return False
        if self.mode == "terminal-failure":
            self.status = "Failed"
            return True
        target = Path(self.jobs[0]["TargetDir"]) / self.jobs[0]["OutputFilename"]
        target.write_bytes(b"fake MOV with lpcm audio")
        self.status = "Complete"
        return True

    def GetRenderJobStatus(self, job_id):
        return {"JobStatus": self.status}


class Resolve:
    def __init__(self, project):
        self.project = project

    def GetProductName(self):
        return "DaVinci Resolve Studio"

    def GetVersion(self):
        return reader.BUILD

    def ExportRenderPreset(self, name, path):
        self.project.mutations.append("ExportRenderPreset")
        directory = Path(path)
        directory.mkdir()
        bit_depth = {
            "original-16": "16",
            "original-20": "20",
        }.get(self.project.mode, "24")
        (directory / f"{name}.xml").write_text(
            "<Preset><RecordFormatType>mov</RecordFormatType>"
            "<RecordFormatSubType>avc1</RecordFormatSubType>"
            "<RecordAudioEnabled>true</RecordAudioEnabled>"
            f"<RecordAudioBitDepth>{bit_depth}</RecordAudioBitDepth>"
            "<ExtraInfoMap><Element><DbKey>aud_codec</DbKey>"
            "<DbVal>lpcm</DbVal></Element></ExtraInfoMap></Preset>"
        )
        return True


class Probe:
    PREFIX = "VERA Issue 141 Synthetic Probe "

    def __init__(self, root, mode):
        self.ROOT, self.mode = root, mode

    def sha256(self, path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def errors(self, values):
        return [row for row in values if isinstance(row, dict) and "error" in row]

    def require_current(self, resolve, config, identity):
        return resolve.project


def _json_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setup(mode):
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    out = root / "out"
    out.mkdir()
    output = out / "issue-141-observation-test"
    output.mkdir()
    media = out / "issue-141-media-test"
    media.mkdir()
    names = [
        "base.mov",
        "base.png",
        "bed.wav",
        "cutaway.mov",
        "cutaway.png",
        "echo.aiff",
        "echo.wav",
        "overlay.png",
        "relink/base.mov",
        "repeated.wav",
        "wrong/base.mov",
    ]
    entries = []
    for name in names:
        path = media / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"synthetic:{name}".encode())
        entries.append(
            {"path": name, "sha256": _json_hash(path), "sizeBytes": path.stat().st_size}
        )
    manifest = {
        "kind": "generated-synthetic-inputs-not-Resolve-evidence",
        "files": entries,
    }
    manifest_path = media / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    timeline_names = [
        (reader.MATRIX_UID, reader.MATRIX_NAME),
        ("88f7923d-55a7-471f-b09b-cf10f9fae8ad", "VERA 141 Baseline"),
        ("aa2b8e36-83bd-4292-9e33-217c00ca192f", "VERA 141 R1 identity"),
        (reader.R4_UID, reader.R4_NAME),
    ]
    handles = [Timeline(uid, name) for uid, name in timeline_names]
    project = Project(mode, handles)
    continuation_preset = "VERA141_AV_OUTPUT_20261001T062051.400988Z"
    if mode.startswith("continuation"):
        project.presets.append(continuation_preset)
    media_items = []
    expected_imported = sorted(av.IMPORTED_MEDIA)
    for index, name in enumerate(expected_imported):
        path = media / name
        digest = _json_hash(path)
        media_items.append(
            {
                "uid": f"media-{index}",
                "name": {"value": Path(name).name},
                "evidence": {
                    "GetUniqueId": {"value": f"media-{index}"},
                    "GetClipProperty": {
                        "value": {
                            "File Path": str(path),
                            "File Name": Path(name).name,
                            "Online Status": "Online",
                        }
                    },
                    "sourceBytes": {
                        "status": "reachable",
                        "sha256": digest,
                        "hashMatches": True,
                    },
                },
            }
        )
    media_items.append(
        {
            "uid": av.PROTECTED_SOURCE_UID,
            "name": {"value": av.PROTECTED_SOURCE_NAME},
            "evidence": {
                "GetUniqueId": {"value": av.PROTECTED_SOURCE_UID},
                "GetName": {"value": av.PROTECTED_SOURCE_NAME},
                "GetClipProperty": {
                    "value": {
                        "File Path": "/private/protected/semi1b.mp4",
                        "File Name": av.PROTECTED_SOURCE_NAME,
                        "Online Status": "Online",
                    }
                },
                "sourceBytes": {"status": av.PROTECTED_SOURCE_STATUS},
            },
        }
    )
    mappings = []
    proxy_ids = []
    for index, (uid, name) in enumerate(timeline_names):
        proxy = f"proxy-{index}"
        proxy_ids.append(proxy)
        mappings.append(
            {"timelineUid": {"value": uid}, "poolItemUid": {"value": proxy}}
        )
        media_items.append(
            {
                "uid": proxy,
                "name": {"value": name},
                "evidence": {
                    "GetUniqueId": {"value": proxy},
                    "GetClipProperty": {"value": {"File Path": ""}},
                    "sourceBytes": {"status": "timeline-uid-not-hashed"},
                },
            }
        )
    pool = {"items": media_items, "timelineMappings": mappings}
    baseline = {
        "projectId": reader.PROJECT_ID,
        "projectName": project.GetName(),
        "GetSettings": {"value": {}},
        "timelines": [
            {
                "GetUniqueId": {"value": uid},
                "GetName": {"value": name},
                "GetSettings": {
                    "value": {
                        "timelineResolutionWidth": 1920,
                        "timelineResolutionHeight": 1080,
                        "timelineFrameRate": 25.0,
                    }
                }
                if uid == reader.MATRIX_UID
                else {"value": {}},
                "GetStartFrame": {"value": 0},
                "GetEndFrame": {"value": 9200 if uid == reader.MATRIX_UID else 100},
                "tracks": [],
            }
            for uid, name in timeline_names
        ],
    }
    probe = Probe(root, mode)

    av._load_reader = lambda _probe: reader

    def read_pair(*args):
        if (
            mode in {"full-settings-drift", "full-queue-only-settings-drift"}
            and "SetRenderSettings" in project.mutations
        ):
            changed = json.loads(json.dumps(baseline))
            matrix = next(
                row
                for row in changed["timelines"]
                if row["GetUniqueId"]["value"] == reader.MATRIX_UID
            )
            matrix["GetEndFrame"]["value"] = 9199
            changed_pool = json.loads(json.dumps(pool))
            matrix_proxy = next(
                row
                for row in changed_pool["items"]
                if row.get("name", {}).get("value") == reader.MATRIX_NAME
            )
            matrix_proxy["evidence"]["GetClipProperty"]["value"]["Out"] = "drift"
            return {
                "selectedTimelineUid": reader.MATRIX_UID,
                "timelineConsistency": "equal-adjacent-reads",
                "poolConsistency": "equal-adjacent-reads",
                "timelinePasses": [changed, changed],
                "poolPasses": [changed_pool, changed_pool],
            }
        if mode == "drift":
            changed = {**baseline, "projectName": "different"}
            return {
                "selectedTimelineUid": reader.MATRIX_UID,
                "timelineConsistency": "equal-adjacent-reads",
                "poolConsistency": "equal-adjacent-reads",
                "timelinePasses": [baseline, changed],
                "poolPasses": [pool, pool],
            }
        return {
            "selectedTimelineUid": reader.MATRIX_UID,
            "timelineConsistency": "equal-adjacent-reads",
            "poolConsistency": "equal-adjacent-reads",
            "timelinePasses": [baseline, baseline],
            "poolPasses": [pool, pool],
        }

    reader._read_pair = read_pair
    av._inspect_output = lambda _path: (
        {
            "format": {
                "format_name": "mov,mp4",
                "duration": "368.04" if mode.startswith("full-") else "8.04",
            },
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920 if mode.startswith("full-") else 640,
                    "height": 1080 if mode.startswith("full-") else 360,
                    "r_frame_rate": "25/1",
                    "nb_frames": "9201" if mode.startswith("full-") else "201",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "pcm_s24le",
                    "sample_rate": "48000",
                    "bits_per_sample": 24,
                },
            ],
        }
        if mode not in {"output-metadata-unknown", "full-output-metadata-unknown"}
        else {"format": {"format_name": "mov,mp4"}, "streams": []}
    )
    pin_path = output / "pin.json"
    pin = {
        "selectedTimelineUid": reader.MATRIX_UID,
        "timelineConsistency": "equal-adjacent-reads",
        "poolConsistency": "equal-adjacent-reads",
        "timelinePasses": [baseline, baseline],
        "poolPasses": [pool, pool],
    }
    pin_path.write_text(json.dumps(pin))
    config = {
        "action": "av-output-full-matrix"
        if mode.startswith("full-")
        else "av-output-continue"
        if mode.startswith("continuation")
        else "av-output",
        "externalScriptingSetting": "None",
        "projectName": project.GetName(),
        "outputDir": str(output),
        "mediaDir": str(media),
        "manifestSha256": _json_hash(manifest_path),
        "checkpointPath": str(pin_path),
        "checkpointSha256": _json_hash(pin_path),
        "sampleRateHz": 48000,
        "renderTimeoutSeconds": 0.01,
    }
    if mode.startswith("continuation"):
        prior_dir = output / "av-output-20261001T062051.400988Z"
        preset_dir = prior_dir / f"{continuation_preset}.drp"
        preset_dir.mkdir(parents=True)
        journal = prior_dir / "journal.jsonl"
        final = prior_dir / "final-local-result.json"
        xml = preset_dir / f"{continuation_preset}.xml"
        journal.write_text("prior journal evidence\n")
        final.write_text(
            json.dumps(
                {
                    "failure": (
                        "RuntimeError: Snapshot XML does not verify MOV/H264 plus lpcm"
                    )
                }
            )
        )
        xml.write_text(
            "<Preset><RecordFormatType>mov</RecordFormatType>"
            "<RecordFormatSubType>avc1</RecordFormatSubType>"
            "<RecordAudioEnabled>true</RecordAudioEnabled>"
            "<RecordAudioBitDepth>16</RecordAudioBitDepth>"
            "<ExtraInfoMap><Element><DbKey>aud_codec</DbKey>"
            "<DbVal>lpcm</DbVal></Element></ExtraInfoMap></Preset>"
        )
        actual_fields = {
            "RecordFormatType": "mov",
            "RecordFormatSubType": "avc1",
            "RecordAudioEnabled": "true",
            "RecordAudioBitDepth": "16",
            "extra_info.aud_codec": "lpcm",
        }
        record = {
            "kind": "issue-141-av-output-continuation-binding",
            "checkpoint": {
                "path": pin_path.name,
                "sha256": config["checkpointSha256"],
            },
            "priorAttemptEvidence": {
                "journal": {
                    "path": f"{prior_dir.name}/journal.jsonl",
                    "sha256": _json_hash(journal),
                },
                "finalLocalResult": {
                    "path": f"{prior_dir.name}/final-local-result.json",
                    "sha256": _json_hash(final),
                },
                "snapshotXml": {
                    "path": f"{prior_dir.name}/{preset_dir.name}/{xml.name}",
                    "sha256": _json_hash(xml),
                },
                "expectedPriorRefusal": (
                    "RuntimeError: Snapshot XML does not verify MOV/H264 plus lpcm"
                ),
                "actualSnapshotFields": actual_fields,
                "presetName": continuation_preset,
            },
            "priorInitialVisibleState": {
                "formatCodec": {"format": "mov", "codec": "H264"},
                "mode": 1,
                "jobs": [],
                "rendering": False,
                "presets": ["Existing"],
            },
        }
        record_path = output / "av-output-continuation-record.json"
        record_path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
        av.CONTINUATION_RECORD_SHA256 = _json_hash(record_path)
        config["continuationRecordPath"] = str(record_path)
        config["continuationRecordSha256"] = av.CONTINUATION_RECORD_SHA256
        if mode == "continuation-state-drift":
            project.presets.append("Unrelated")
        if mode == "continuation-pin-mismatch":
            config["checkpointSha256"] = "0" * 64
    return temp, config, probe, Resolve(project), project, media


def setup_full_queue_only_case(mode):
    temp, config, probe, resolve, project, media = setup(mode)
    config["action"] = av.FULL_MATRIX_QUEUE_ONLY_ACTION
    return temp, config, probe, resolve, project, media


def setup_full_matrix_continue_case(mode):
    temp, config, probe, resolve, project, media = setup_full_queue_only_case(
        "full-queue-only-end-equal"
    )
    av.run(resolve, config, probe=probe)
    final_path = next(
        path
        for path in Path(config["outputDir"]).glob(
            "av-output-*/final-local-result.json"
        )
        if json.loads(path.read_text()).get("kind")
        == "av-output-final-local-result"
    )
    result = json.loads(final_path.read_text())["result"]
    journal_path = Path(result["journal"])
    settings = next(
        row["value"][0]
        for row in (json.loads(line) for line in journal_path.read_text().splitlines())
        if row.get("method") == "SetRenderSettings" and row.get("phase") == "request"
    )
    config.update(
        action=av.FULL_MATRIX_CONTINUE_ACTION,
        checkpointPath=result["afterPair"],
        checkpointSha256=result["afterPairSha256"],
        queueResultPath=str(final_path),
        queueResultSha256=_json_hash(final_path),
        queueJobId=result["jobId"],
        queueJobSha256=av._value_sha(result["job"]),
        queueAfterPairPath=result["afterPair"],
        queueAfterPairSha256=result["afterPairSha256"],
        queueJournalPath=str(journal_path),
        queueJournalSha256=_json_hash(journal_path),
        queueSnapshotXmlPath=result["snapshotXml"],
        queueSnapshotSha256=result["snapshotSha256"],
        queueSettingsSha256=av._value_sha(settings),
        queuePresetName=Path(result["snapshotXml"]).parent.name.removesuffix(".drp"),
    )
    project.mutations.clear()
    project.started.clear()
    project.mode = mode
    probe.mode = mode
    if mode == "full-continuation-job-mismatch":
        project.jobs[0]["JobId"] = "different-job"
    if mode == "full-continuation-drift":
        project.presets.append("Unrelated")
    return temp, config, probe, resolve, project, media


def setup_queue_case(mode):
    temp, config, probe, resolve, project, media = setup("continuation-success")
    project.mode = probe.mode = mode
    config["action"] = "av-output-queue-from-settings"
    pin_path = Path(config["checkpointPath"])
    before = json.loads(pin_path.read_text())
    for pool_pass in before["poolPasses"]:
        proxy = next(
            row
            for row in pool_pass["items"]
            if row.get("name", {}).get("value") == reader.MATRIX_NAME
        )
        proxy["evidence"]["GetClipProperty"]["value"]["Out"] = ""
        mapping = next(
            row
            for row in pool_pass["timelineMappings"]
            if row.get("timelineUid", {}).get("value") == reader.MATRIX_UID
        )
        mapping["poolItemUid"] = {"value": proxy["uid"]}
        mapping["poolItemProperties"] = {"value": {"Out": ""}}
    pin_path.write_text(json.dumps(before))
    config["checkpointSha256"] = _json_hash(pin_path)
    continuation_record_path = Path(config["continuationRecordPath"])
    continuation_record = json.loads(continuation_record_path.read_text())
    continuation_record["checkpoint"]["sha256"] = config["checkpointSha256"]
    continuation_record_path.write_text(
        json.dumps(continuation_record, sort_keys=True, indent=2) + "\n"
    )
    av.CONTINUATION_RECORD_SHA256 = _json_hash(continuation_record_path)
    config["continuationRecordSha256"] = av.CONTINUATION_RECORD_SHA256
    post = json.loads(json.dumps(before))
    for pool_pass in post["poolPasses"]:
        proxy = next(
            row
            for row in pool_pass["items"]
            if row.get("name", {}).get("value") == reader.MATRIX_NAME
        )
        proxy["evidence"]["GetClipProperty"]["value"]["Out"] = "00:00:08:00"
        mapping = next(
            row
            for row in pool_pass["timelineMappings"]
            if row.get("timelineUid", {}).get("value") == reader.MATRIX_UID
        )
        mapping["poolItemProperties"]["value"]["Out"] = "00:00:08:00"
    if mode == "queue-delta-drift":
        post["timelinePasses"][0]["projectName"] = "unexpected project drift"
    prior_dir = Path(config["outputDir"]) / "av-output-20261001T063250.006372Z"
    prior_dir.mkdir()
    pair001, pair002, pair003 = (
        prior_dir / f"full-pair-{i:03d}.json" for i in (1, 2, 3)
    )
    pair001.write_bytes(pin_path.read_bytes())
    pair002.write_bytes(pin_path.read_bytes())
    pair003.write_text(json.dumps(post, sort_keys=True, indent=2) + "\n")
    render_dir = prior_dir / "render"
    render_dir.mkdir(exist_ok=True)
    settings = {
        "AudioBitDepth": 24,
        "AudioCodec": "lpcm",
        "AudioSampleRate": 48000,
        "CustomName": "vera141-av-20261001T063250.006372Z",
        "ExportAudio": True,
        "ExportVideo": True,
        "FormatHeight": 360,
        "FormatWidth": 640,
        "FrameRate": 25.0,
        "MarkIn": 0,
        "MarkOut": 200,
        "SelectAllFrames": False,
        "TargetDir": str(render_dir),
    }
    project.settings = dict(settings)
    state = {
        "GetCurrentRenderFormatAndCodec": {"format": "mov", "codec": "H264"},
        "GetCurrentRenderMode": 1,
        "GetRenderJobList": [],
        "IsRenderingInProgress": False,
        "GetRenderPresetList": [
            "Existing",
            "VERA141_AV_OUTPUT_20261001T062051.400988Z",
        ],
    }
    journal_entries = []
    for _ in range(2):
        for method, value in state.items():
            journal_entries.append(
                {"method": method, "phase": "return", "value": value}
            )
    journal_entries += [
        {"method": "SetRenderSettings", "phase": "request", "value": [settings]},
        {"method": "SetRenderSettings", "phase": "return", "value": True},
    ]
    journal = prior_dir / "journal.jsonl"
    journal.write_text("".join(json.dumps(e) + "\n" for e in journal_entries))
    final = prior_dir / "final-local-result.json"
    final.write_text(
        json.dumps(
            {
                "failure": (
                    "RuntimeError: Fresh full content/source state differs from pin"
                )
            }
        )
    )
    proxy = next(
        row
        for row in post["poolPasses"][0]["items"]
        if row.get("name", {}).get("value") == reader.MATRIX_NAME
    )
    record = {
        "kind": "issue-141-av-applied-settings-queue-checkpoint",
        "priorAttempt": prior_dir.name,
        "priorAttemptJournal": {
            "path": f"{prior_dir.name}/journal.jsonl",
            "sha256": _json_hash(journal),
        },
        "priorFinalResult": {
            "path": f"{prior_dir.name}/final-local-result.json",
            "sha256": _json_hash(final),
        },
        "beforePair": {
            "path": f"{prior_dir.name}/full-pair-002.json",
            "sha256": _json_hash(pair002),
        },
        "afterPair": {
            "path": f"{prior_dir.name}/full-pair-003.json",
            "sha256": _json_hash(pair003),
        },
        "changedPoolProxyUid": proxy["uid"],
        "changedTimelineUid": reader.MATRIX_UID,
        "onlyObservedDelta": {
            "field": "GetClipProperty.Out / poolItemProperties.Out",
            "before": "",
            "after": "00:00:08:00",
            "occurrencesAcrossTwoPoolPasses": 4,
        },
        "setter": "SetRenderSettings",
        "setterReturned": True,
        "appliedSettings": settings,
        "noReplay": [
            "SaveAsNewRenderPreset",
            "ExportRenderPreset",
            "SetRenderSettings",
        ],
        "neverDispatched": [
            "AddRenderJob",
            "StartRendering",
            "LoadRenderPreset",
            "DeleteRenderJob",
            "DeleteRenderPreset",
        ],
    }
    record_path = Path(config["outputDir"]) / "av-applied-settings-record.json"
    record_path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    av.APPLIED_SETTINGS_RECORD_SHA256 = _json_hash(record_path)
    config["appliedSettingsRecordPath"] = str(record_path)
    config["appliedSettingsRecordSha256"] = av.APPLIED_SETTINGS_RECORD_SHA256
    probe._queue_pair = post
    reader._read_pair = lambda *args: probe._queue_pair
    if mode == "queue-state-drift":
        project.presets.append("Unrelated")
    return temp, config, probe, resolve, project, media


def setup_drop_case(mode):
    temp, config, probe, resolve, project, media = setup_queue_case("queue-success")
    project.mode = probe.mode = mode
    config["action"] = "av-output-drop-unstarted-owned-job"
    pin_dir = Path(config["outputDir"]) / "fresh-drop-checkpoint"
    pin_dir.mkdir()
    pin_path = pin_dir / "pair.json"
    pin_path.write_text(json.dumps(probe._queue_pair, sort_keys=True, indent=2) + "\n")
    config["checkpointPath"] = str(pin_path)
    config["checkpointSha256"] = _json_hash(pin_path)
    attempt = Path(config["outputDir"]) / "av-output-20261001T115327.250767Z"
    attempt.mkdir()
    render_dir = (
        Path(config["outputDir"]) / "av-output-20261001T063250.006372Z" / "render"
    )
    render_dir.mkdir(exist_ok=True)
    job = {
        "JobId": "9c4f9ad9-9acf-4c60-bac2-fb7cc9269ebd",
        "TargetDir": str(render_dir),
        "OutputFilename": "vera141-av-20261001T063250.006372Z.mov",
        "IsExportVideo": True,
        "IsExportAudio": True,
        "VideoFormat": "QuickTime",
        "VideoCodec": "H.264",
        "AudioCodec": "lpcm",
        "AudioSampleRate": 48000,
        "AudioBitDepth": 24,
        "FormatWidth": 1920,
        "FormatHeight": 1080,
        "FrameRate": "25",
        "MarkIn": 0,
        "MarkOut": 2449,
    }
    project.jobs = [job]
    if mode == "drop-active":
        project.active = True
    if mode == "drop-content-drift":
        for timeline_pass in probe._queue_pair["timelinePasses"]:
            timeline_pass["projectName"] = "live drift"
    journal = attempt / "journal.jsonl"
    journal.write_text(
        json.dumps({"method": "AddRenderJob", "phase": "request", "value": []})
        + "\n"
        + json.dumps(
            {"method": "AddRenderJob", "phase": "return", "value": job["JobId"]}
        )
        + "\n"
    )
    result = {
        "status": "queued-job-metadata-unknown-recovery-retained",
        "jobId": job["JobId"],
        "job": job,
        "journal": str(journal),
        "snapshot": str(Path(config["outputDir"]) / "snapshot.xml"),
    }
    final = attempt / "final-local-result.json"
    final.write_text(
        json.dumps({"kind": "av-output-final-local-result", "result": result})
    )
    config.update(
        queuedAttemptPath=str(attempt),
        queuedAttemptSha256=_json_hash(final),
        queuedJournalSha256=_json_hash(journal),
    )
    if mode == "drop-wrong-job":
        project.jobs[0] = {**job, "JobId": "different-job"}
    return temp, config, probe, resolve, project, media


def run_case(mode, expected_status):
    original_record_hash = av.CONTINUATION_RECORD_SHA256
    original_applied_hash = av.APPLIED_SETTINGS_RECORD_SHA256
    if mode.startswith("drop-"):
        temp, config, probe, resolve, project, media = setup_drop_case(mode)
    elif mode.startswith("full-continuation-"):
        temp, config, probe, resolve, project, media = setup_full_matrix_continue_case(
            mode
        )
    elif mode.startswith("full-queue-only-"):
        temp, config, probe, resolve, project, media = setup_full_queue_only_case(mode)
    elif mode.startswith("queue-") or mode.startswith("fresh-queue-"):
        temp, config, probe, resolve, project, media = setup_queue_case(mode)
    else:
        temp, config, probe, resolve, project, media = setup(mode)
    try:
        if mode.startswith("fresh-queue-"):
            config["action"] = "av-output-queue-from-fresh-checkpoint"
            pin_dir = Path(config["outputDir"]) / "r2-linked-context-fresh"
            pin_dir.mkdir()
            fresh_pin = pin_dir / "pair.json"
            fresh_pin.write_text(
                json.dumps(probe._queue_pair, sort_keys=True, indent=2) + "\n"
            )
            config["checkpointPath"] = str(fresh_pin)
            config["checkpointSha256"] = _json_hash(fresh_pin)
            project.mutations.clear()
        if mode.startswith("drop-"):
            project.mutations.clear()
        if mode == "unimported-input-changed":
            (media / "base.png").write_bytes(b"changed unimported generated input")
            try:
                av.run(resolve, config, probe=probe)
            except RuntimeError:
                assert not project.jobs and project.presets == ["Existing"]
                return
            raise AssertionError("Changed unimported manifest input was accepted")
        if mode in {"unapproved-pool-source", "full-queue-only-unapproved-pool-source"}:
            pair = json.loads(Path(config["checkpointPath"]).read_text())
            pair["poolPasses"][0]["items"].append(
                {
                    "uid": "unexpected",
                    "evidence": {
                        "GetClipProperty": {
                            "value": {"File Path": str(media / "not-in-manifest.mov")}
                        },
                        "sourceBytes": {
                            "status": "reachable",
                            "sha256": "0" * 64,
                            "hashMatches": True,
                        },
                    },
                }
            )
            pair["poolPasses"][1] = pair["poolPasses"][0]
            pin = Path(config["checkpointPath"])
            pin.write_text(json.dumps(pair))
            config["checkpointSha256"] = _json_hash(pin)
        if mode == "full-queue-only-protected-pool-status":
            pair = json.loads(Path(config["checkpointPath"]).read_text())
            for pool_pass in pair["poolPasses"]:
                protected = next(
                    row
                    for row in pool_pass["items"]
                    if row.get("uid") == av.PROTECTED_SOURCE_UID
                )
                protected["evidence"]["sourceBytes"] = {
                    "status": av.PROTECTED_SOURCE_STATUS,
                    "sha256": "0" * 64,
                }
            pin = Path(config["checkpointPath"])
            pin.write_text(json.dumps(pair))
            config["checkpointSha256"] = _json_hash(pin)
        if mode == "full-queue-only-matrix-protected-source":
            pair = json.loads(Path(config["checkpointPath"]).read_text())
            occurrence = {
                "GetMediaPoolItem": {
                    "GetUniqueId": {"value": av.PROTECTED_SOURCE_UID},
                    "GetName": {"value": av.PROTECTED_SOURCE_NAME},
                    "GetClipProperty": {
                        "value": {
                            "File Name": av.PROTECTED_SOURCE_NAME,
                            "File Path": "/private/protected/semi1b.mp4",
                        }
                    },
                }
            }
            for timeline_pass in pair["timelinePasses"]:
                matrix = next(
                    row
                    for row in timeline_pass["timelines"]
                    if row["GetUniqueId"]["value"] == reader.MATRIX_UID
                )
                matrix["tracks"] = [{"type": "video", "index": 1, "items": [occurrence]}]
            pin = Path(config["checkpointPath"])
            pin.write_text(json.dumps(pair))
            config["checkpointSha256"] = _json_hash(pin)
        if mode in {"missing-imported-source", "bad-pool-source-hash"}:
            pin = Path(config["checkpointPath"])
            pair = json.loads(pin.read_text())
            for pool_pass in pair["poolPasses"]:
                if mode == "missing-imported-source":
                    pool_pass["items"] = [
                        row
                        for row in pool_pass["items"]
                        if row.get("name", {}).get("value") != "cutaway.mov"
                    ]
                else:
                    row = next(
                        row
                        for row in pool_pass["items"]
                        if row.get("name", {}).get("value") == "base.mov"
                    )
                    row["evidence"]["sourceBytes"]["hashMatches"] = False
            pin.write_text(json.dumps(pair))
            config["checkpointSha256"] = _json_hash(pin)
        try:
            if mode == "full-continuation-timeout":
                first = av.run(resolve, config, probe=probe)
                assert first["status"] == "render-pending-or-ambiguous-recovery-retained"
                assert project.started == [["owned-job"]]
                target = Path(project.jobs[0]["TargetDir"]) / project.jobs[0]["OutputFilename"]
                target.write_bytes(b"fake MOV with lpcm audio after timeout")
                project.status = "Complete"
                project.active = False
                config["resumeExistingJob"] = True
                result = av.run(resolve, config, probe=probe)
                assert result["status"] == "render-complete-restored", result
                assert project.started == [["owned-job"]]
                assert not project.jobs and project.presets == ["Existing"]
                return
            result = av.run(resolve, config, probe=probe)
            assert result["status"] == expected_status, result
        except RuntimeError:
            assert expected_status == "raises"
        if mode in {
            "success",
            "full-success",
            "continuation-success",
            "queue-success",
            "fresh-queue-success",
        }:
            assert project.started == [["owned-job"]]
            assert not project.jobs and project.presets == ["Existing"]
            if mode in {"continuation-success", "queue-success", "fresh-queue-success"}:
                assert "SaveAsNewRenderPreset" not in project.mutations
                assert "ExportRenderPreset" not in project.mutations
            if mode == "queue-success":
                assert "SetRenderSettings" not in project.mutations
                assert project.mutations == ["AddRenderJob", "StartRendering"]
            if mode == "fresh-queue-success":
                assert "SetRenderSettings" not in project.mutations
                assert "SaveAsNewRenderPreset" not in project.mutations
                assert "ExportRenderPreset" not in project.mutations
                assert project.mutations == ["AddRenderJob", "StartRendering"]
            finals = list(
                Path(config["outputDir"]).glob("av-output-*/final-local-result.json")
            )
            expected_final_count = 1 if mode in {"success", "full-success"} else 2
            if mode == "queue-success":
                expected_final_count = 3
            if mode == "fresh-queue-success":
                expected_final_count = 3
            assert len(finals) == expected_final_count
            if mode == "full-success":
                settings = project.setting_calls[0]
                assert settings["FormatWidth"] == 1920
                assert settings["FormatHeight"] == 1080
                assert settings["FrameRate"] == 25.0
                assert settings["SelectAllFrames"] is True
                assert "MarkIn" not in settings and "MarkOut" not in settings
            result_file = next(
                path
                for path in finals
                if json.loads(path.read_text()).get("kind")
                == "av-output-final-local-result"
            )
            environment = json.loads(result_file.read_text())["environment"]
            assert (
                environment["pythonVersion"]
                and environment["product"] == "DaVinci Resolve Studio"
            )
        if mode in {
            "full-queue-only-end-equal",
            "full-queue-only-end-minus-one",
            "full-queue-only-end-plus-one",
        }:
            assert project.started == []
            assert len(project.jobs) == 1 and len(project.presets) == 2
            assert project.mutations == [
                "SaveAsNewRenderPreset",
                "ExportRenderPreset",
                "SetRenderSettings",
                "AddRenderJob",
            ]
            settings = project.setting_calls[0]
            assert settings == {
                "ExportVideo": True,
                "ExportAudio": True,
                "AudioCodec": "lpcm",
                "AudioSampleRate": 48000,
                "AudioBitDepth": 24,
                "FormatWidth": 1920,
                "FormatHeight": 1080,
                "FrameRate": 25.0,
                "SelectAllFrames": True,
                "TargetDir": settings["TargetDir"],
                "CustomName": settings["CustomName"],
            }
            finals = list(
                Path(config["outputDir"]).glob("av-output-*/final-local-result.json")
            )
            assert len(finals) == 1
            final = json.loads(finals[0].read_text())
            result = final["result"]
            assert result["status"] == "full-matrix-queued-unstarted-recovery-retained"
            assert result["jobId"] == "owned-job"
            assert result["job"]["JobId"] == result["jobId"]
            expected_mark_out = {
                "full-queue-only-end-equal": 9200,
                "full-queue-only-end-minus-one": 9199,
                "full-queue-only-end-plus-one": 9201,
            }[mode]
            assert result["queuedEndpoints"] == {
                "MarkIn": 0,
                "MarkOut": expected_mark_out,
                "timelineStartFrame": 0,
                "timelineEndFrame": 9200,
                "selectionMode": "SelectAllFrames",
                "endpointSemantics": "diagnostic-only; inclusive/exclusive unknown",
            }
            before = Path(result["beforePair"])
            after = Path(result["afterPair"])
            assert before.is_file() and after.is_file()
            assert result["beforePairSha256"] == _json_hash(before)
            assert result["afterPairSha256"] == _json_hash(after)
            assert before.read_bytes() == after.read_bytes()
            journal = Path(result["journal"]).read_text()
            assert '"method": "StartRendering"' not in journal
        if mode == "full-queue-only-end-noninteger":
            assert project.started == []
            assert len(project.jobs) == 1 and len(project.presets) == 2
            final = next(
                Path(config["outputDir"]).glob("av-output-*/final-local-result.json")
            )
            result = json.loads(final.read_text())["result"]
            assert result["status"] == "queued-job-endpoints-unknown-recovery-retained"
            assert result["queuedEndpoints"]["MarkOut"] == "9201"
            assert '"method": "StartRendering"' not in Path(
                result["journal"]
            ).read_text()
        if mode == "full-queue-only-unsupported-resolution":
            assert (
                project.mutations == [] and not project.jobs and project.started == []
            )
        if mode == "full-queue-only-unknown-format":
            assert project.mutations == [
                "SaveAsNewRenderPreset",
                "ExportRenderPreset",
                "SetRenderSettings",
            ]
            assert not project.jobs and project.started == []
        if mode == "full-queue-only-settings-false":
            assert project.mutations == [
                "SaveAsNewRenderPreset",
                "ExportRenderPreset",
                "SetRenderSettings",
            ]
            assert not project.jobs and project.started == []
        if mode == "full-queue-only-settings-drift":
            assert project.mutations == [
                "SaveAsNewRenderPreset",
                "ExportRenderPreset",
                "SetRenderSettings",
            ]
            assert not project.jobs and project.started == []
            pair_files = list(
                Path(config["outputDir"]).glob("av-output-*/full-pair-*.json")
            )
            assert len(pair_files) >= 1
            assert any(
                next(
                    row
                    for row in pair["timelinePasses"][0]["timelines"]
                    if row["GetUniqueId"]["value"] == reader.MATRIX_UID
                )["GetEndFrame"]["value"]
                == 9199
                and any(
                    row.get("name", {}).get("value") == reader.MATRIX_NAME
                    and row["evidence"]["GetClipProperty"]["value"]["Out"] == "drift"
                    for row in pair["poolPasses"][0]["items"]
                )
                for path in pair_files
                for pair in [json.loads(path.read_text())]
            )
            finals = list(
                Path(config["outputDir"]).glob("av-output-*/final-local-result.json")
            )
            assert len(finals) == 1
            assert json.loads(finals[0].read_text())["failure"].startswith(
                "RuntimeError: Fresh full content/source state differs from pin"
            )
            journals = list(Path(config["outputDir"]).glob("av-output-*/journal.jsonl"))
            assert len(journals) == 1
            assert '"method": "StartRendering"' not in journals[0].read_text()
        if mode == "full-queue-only-unapproved-pool-source":
            assert not project.jobs and project.presets == ["Existing"]
        if mode in {
            "unknown-metadata",
            "start-false",
            "terminal-failure",
            "timeout",
            "output-metadata-unknown",
        }:
            assert project.jobs and len(project.presets) == 2
        if mode == "unknown-format":
            assert not project.jobs and len(project.presets) == 2
        if mode == "full-unsupported-resolution":
            assert (
                project.mutations == [] and not project.jobs and project.started == []
            )
        if mode in {"full-wrong-range", "full-wrong-dimensions"}:
            assert project.mutations[-1:] == ["AddRenderJob"]
            assert project.jobs and project.started == []
        if mode == "full-settings-drift":
            assert project.mutations == [
                "SaveAsNewRenderPreset",
                "ExportRenderPreset",
                "SetRenderSettings",
            ]
            assert not project.jobs and project.started == []
        if mode in {
            "unapproved-pool-source",
            "missing-imported-source",
            "bad-pool-source-hash",
        }:
            assert not project.jobs and project.presets == ["Existing"]
        if mode == "drift":
            assert not project.jobs and project.presets == ["Existing"]
            pair_files = list(
                Path(config["outputDir"]).glob("av-output-*/full-pair-*.json")
            )
            assert len(pair_files) == 1
        if mode in {"continuation-state-drift", "continuation-pin-mismatch"}:
            assert not project.mutations and not project.jobs and project.started == []
        if mode in {"queue-state-drift", "queue-delta-drift"}:
            assert not project.mutations and not project.jobs and project.started == []
        if mode in {"drop-wrong-job", "drop-active", "drop-content-drift"}:
            assert not project.mutations
        if mode == "drop-delete-false":
            assert project.mutations == ["DeleteRenderJob"]
        if mode == "drop-success":
            assert project.mutations == ["DeleteRenderJob"]
            assert not project.jobs and project.started == []
            assert (
                len(
                    list(
                        Path(config["outputDir"]).glob(
                            "av-output-drop-*/before-pair.json"
                        )
                    )
                )
                == 1
            )
            assert (
                len(
                    list(
                        Path(config["outputDir"]).glob(
                            "av-output-drop-*/after-pair.json"
                        )
                    )
                )
                == 1
            )
        if mode == "queue-metadata-refusal":
            assert project.mutations == ["AddRenderJob"]
            assert project.jobs and project.started == []
            assert len(project.presets) == 2
    finally:
        av.CONTINUATION_RECORD_SHA256 = original_record_hash
        av.APPLIED_SETTINGS_RECORD_SHA256 = original_applied_hash
        temp.cleanup()


if __name__ == "__main__":
    run_case("original-16", "render-complete-restored")
    run_case("original-20", "raises")
    run_case("success", "render-complete-restored")
    run_case("full-success", "render-complete-restored")
    run_case("full-unsupported-resolution", "raises")
    run_case("full-wrong-range", "queued-job-metadata-unknown-recovery-retained")
    run_case("full-wrong-dimensions", "queued-job-metadata-unknown-recovery-retained")
    run_case("full-settings-drift", "raises")
    run_case("unknown-metadata", "queued-job-metadata-unknown-recovery-retained")
    run_case("start-false", "start-refused-recovery-retained")
    run_case("terminal-failure", "render-failed-recovery-retained")
    run_case("timeout", "render-pending-or-ambiguous-recovery-retained")
    run_case(
        "output-metadata-unknown", "render-output-metadata-unknown-recovery-retained"
    )
    run_case("drift", "raises")
    run_case("settings-false", "settings-refused-recovery-retained")
    run_case("unknown-format", "raises")
    run_case("unapproved-pool-source", "raises")
    run_case("missing-imported-source", "raises")
    run_case("bad-pool-source-hash", "raises")
    run_case("unimported-input-changed", "raises")
    run_case("continuation-success", "render-complete-restored")
    run_case("continuation-state-drift", "raises")
    run_case("continuation-pin-mismatch", "raises")
    run_case("queue-success", "render-complete-restored")
    run_case("queue-metadata-refusal", "queued-job-metadata-unknown-recovery-retained")
    run_case("queue-state-drift", "raises")
    run_case("queue-delta-drift", "raises")
    run_case("fresh-queue-success", "render-complete-restored")
    run_case("drop-success", "owned-unstarted-job-removed")
    run_case("drop-wrong-job", "raises")
    run_case("drop-active", "raises")
    run_case("drop-content-drift", "raises")
    run_case("drop-delete-false", "raises")
    run_case(
        "full-queue-only-end-equal",
        "full-matrix-queued-unstarted-recovery-retained",
    )
    run_case(
        "full-queue-only-end-minus-one",
        "full-matrix-queued-unstarted-recovery-retained",
    )
    run_case(
        "full-queue-only-end-plus-one",
        "full-matrix-queued-unstarted-recovery-retained",
    )
    run_case(
        "full-queue-only-end-noninteger",
        "queued-job-endpoints-unknown-recovery-retained",
    )
    run_case("full-queue-only-unsupported-resolution", "raises")
    run_case("full-queue-only-unknown-format", "raises")
    run_case("full-queue-only-settings-false", "settings-refused-recovery-retained")
    run_case("full-queue-only-settings-drift", "raises")
    run_case("full-queue-only-unapproved-pool-source", "raises")
    run_case(
        "full-queue-only-protected-pool-status", "raises"
    )
    run_case(
        "full-queue-only-matrix-protected-source", "raises"
    )
    run_case(
        "full-queue-only-protected-pool", 
        "full-matrix-queued-unstarted-recovery-retained",
    )
    run_case("full-continuation-success", "render-complete-restored")
    run_case("full-continuation-job-mismatch", "raises")
    run_case("full-continuation-drift", "raises")
    run_case("full-continuation-timeout", "render-complete-restored")
    print("AV output fake checks passed")
