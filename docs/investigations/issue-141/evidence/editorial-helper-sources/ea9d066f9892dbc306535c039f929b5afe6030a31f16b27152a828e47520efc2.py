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
        if self.mode == "unknown-format" and self.settings.get("ExportVideo") is True:
            return {"format": "unknown", "codec": ""}
        return {"format": "mov", "codec": "H264"}

    def GetCurrentRenderMode(self):
        return 1

    def IsRenderingInProgress(self):
        return self.active

    def GetRenderPresetList(self):
        return list(self.presets)

    def SaveAsNewRenderPreset(self, name):
        self.presets.append(name)
        return True

    def LoadRenderPreset(self, name):
        self.settings = {"prior": True}
        return True

    def DeleteRenderPreset(self, name):
        self.presets.remove(name)
        return True

    def DeleteRenderJob(self, job_id):
        self.jobs.clear()
        return True

    def SetRenderSettings(self, settings):
        self.settings = dict(settings)
        return self.mode != "settings-false"

    def AddRenderJob(self):
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
            "FormatWidth": 640,
            "FormatHeight": 360,
            "FrameRate": "25",
            "MarkIn": 0,
            "MarkOut": 200,
        }
        if self.mode == "unknown-metadata":
            job.pop("AudioSampleRate")
        self.jobs.append(job)
        return "owned-job"

    def StartRendering(self, ids):
        self.started.append(ids)
        if self.mode == "timeout":
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
        directory = Path(path)
        directory.mkdir()
        (directory / f"{name}.xml").write_text(
            "<Preset><RecordFormatType>mov</RecordFormatType>"
            "<RecordFormatSubType>avc1</RecordFormatSubType>"
            "<RecordAudioEnabled>true</RecordAudioEnabled>"
            "<RecordAudioBitDepth>24</RecordAudioBitDepth>"
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
            {"GetUniqueId": {"value": uid}, "GetName": {"value": name}, "tracks": []}
            for uid, name in timeline_names
        ],
    }
    probe = Probe(root, mode)

    av._load_reader = lambda _probe: reader

    def read_pair(*args):
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
            "format": {"format_name": "mov,mp4"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 640,
                    "height": 360,
                    "r_frame_rate": "25/1",
                    "nb_frames": "201",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "pcm_s24le",
                    "sample_rate": "48000",
                    "bits_per_sample": 24,
                },
            ],
        }
        if mode != "output-metadata-unknown"
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
        "action": "av-output",
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
    return temp, config, probe, Resolve(project), project, media


def run_case(mode, expected_status):
    temp, config, probe, resolve, project, media = setup(mode)
    try:
        if mode == "unimported-input-changed":
            (media / "base.png").write_bytes(b"changed unimported generated input")
            try:
                av.run(resolve, config, probe=probe)
            except RuntimeError:
                assert not project.jobs and project.presets == ["Existing"]
                return
            raise AssertionError("Changed unimported manifest input was accepted")
        if mode == "unapproved-pool-source":
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
            result = av.run(resolve, config, probe=probe)
            assert result["status"] == expected_status, result
        except RuntimeError:
            assert expected_status == "raises"
        if mode == "success":
            assert project.started == [["owned-job"]]
            assert not project.jobs and project.presets == ["Existing"]
            finals = list(
                Path(config["outputDir"]).glob("av-output-*/final-local-result.json")
            )
            assert len(finals) == 1
            environment = json.loads(finals[0].read_text())["environment"]
            assert (
                environment["pythonVersion"]
                and environment["product"] == "DaVinci Resolve Studio"
            )
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
    finally:
        temp.cleanup()


if __name__ == "__main__":
    run_case("success", "render-complete-restored")
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
    print("AV output fake checks passed")
