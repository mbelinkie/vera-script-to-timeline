"""Stdlib-only acceptance check for the Issue 149 discriminator harness.

This check exercises guards and fake native objects only.  It does not launch
Resolve, touch Hammerspoon, invoke a UI, install files, or call GitHub.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
from copy import deepcopy
from pathlib import Path


HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load("issue149_harness_check", HERE / "harness.py")
launcher = _load("issue149_launcher_check", HERE / "launcher.py")


class Media:
    def __init__(self, uid="media-1", name="base.mov"):
        self.uid, self.name = uid, name

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name

    def GetClipProperty(self):
        return {"File Path": f"/synthetic/{self.name}", "Online Status": "Online"}

    def GetMarkers(self):
        return {}

    def GetAudioMapping(self):
        return {"track_mapping": {"1": {"mute": False}}}

    def GetMarkInOut(self):
        return {}


class Item(Media):
    def __init__(self, media, uid="item-1"):
        super().__init__(media.uid, media.name)
        self.media, self.uid = media, uid

    def GetStart(self, *args):
        return 0

    def GetEnd(self, *args):
        return 399

    def GetDuration(self, *args):
        return 400

    def GetLeftOffset(self, *args):
        return 0

    def GetRightOffset(self, *args):
        return 0

    def GetSourceStartFrame(self):
        return 0

    def GetSourceEndFrame(self):
        return 399

    def GetSourceStartTime(self):
        return 0.0

    def GetSourceEndTime(self):
        return 15.96

    def GetClipEnabled(self):
        return True

    def GetSpeed(self):
        return {"Percentage": 100.0, "PitchCorrection": True}

    def GetFlagList(self):
        return []

    def GetClipColor(self):
        return "None"

    def GetSourceAudioChannelMapping(self):
        return self.media.GetAudioMapping()

    def GetVoiceIsolationState(self):
        return None

    def GetTrackTypeAndIndex(self):
        return ["audio", 1]

    def GetMarkers(self):
        return {}

    def GetLinkedItems(self):
        return []

    def GetMediaPoolItem(self):
        return self.media

    def GetProperty(self, key=None):
        return {"Text": "synthetic"} if key == "Text" else {"Opacity": 1.0}


class Timeline:
    def __init__(self, project):
        self.project, self.uid, self.name = project, "timeline-1", "W1 synthetic"
        self.media = Media()
        self.item = Item(self.media)
        self.current_timecode = "00:00:00:00"
        self.set_current_timecode_calls = []

    def GetName(self):
        return self.name

    def GetUniqueId(self):
        return self.uid

    def GetStartFrame(self):
        return 0

    def GetEndFrame(self):
        return 399

    def GetStartTimecode(self):
        return "00:00:00:00"

    def GetCurrentTimecode(self):
        return self.current_timecode

    def SetCurrentTimecode(self, value):
        self.set_current_timecode_calls.append(value)
        self.current_timecode = value
        return True

    def GetMarkInOut(self):
        return {}

    def GetMarkers(self):
        return {}

    def GetTrackCount(self, kind):
        return 1 if kind == "audio" else 0

    def GetTrackName(self, kind, index):
        return f"{kind}-{index}"

    def GetTrackType(self, kind, index):
        return kind

    def GetIsTrackEnabled(self, kind, index):
        return True

    def GetIsTrackLocked(self, kind, index):
        return False

    def GetTrackSubType(self, kind, index):
        return "mono"

    def GetVoiceIsolationState(self, index):
        return None

    def GetItemListInTrack(self, kind, index):
        return [self.item] if kind == "audio" and index == 1 else []

    def GetSelectedClips(self):
        return [self.item]


class Folder:
    def __init__(self, clip):
        self.clip = clip

    def GetClipList(self):
        return [self.clip]

    def GetSubFolderList(self):
        return []


class Pool:
    def __init__(self, clip):
        self.clip, self.root = clip, Folder(clip)
        self.import_calls = []

    def GetRootFolder(self):
        return self.root

    def ImportMedia(self, entries):
        assert len(entries) == 1
        assert all(isinstance(entry, str) for entry in entries)
        self.import_calls.append(entries)
        return [self.clip]


class EmptyFolder:
    def __init__(self, clips=None):
        self.clips = [] if clips is None else list(clips)

    def GetClipList(self):
        return list(self.clips)

    def GetSubFolderList(self):
        return []


class EmptyPool:
    def __init__(self):
        self.root = EmptyFolder()

    def GetRootFolder(self):
        return self.root


class ImportPool(EmptyPool):
    def __init__(self, clip):
        super().__init__()
        self.clip, self.import_calls = clip, []

    def ImportMedia(self, entries):
        assert all(isinstance(entry, str) for entry in entries)
        self.import_calls.append(entries)
        self.root.clips.append(self.clip)
        return [self.clip]


class StartupProject:
    def __init__(
        self, name=harness.STARTUP_PROJECT_NAME, nonempty=False, timeline_count=None
    ):
        self.uid, self.name = "startup-project", name
        self.timeline = Timeline(self) if nonempty else None
        self.pool = Pool(self.timeline.media) if nonempty else EmptyPool()
        self.timeline_count = (
            (1 if nonempty else 0) if timeline_count is None else timeline_count
        )

    def GetName(self):
        return self.name

    def GetUniqueId(self):
        return self.uid

    def GetCurrentTimeline(self):
        return self.timeline

    def GetTimelineCount(self):
        return self.timeline_count

    def GetTimelineByIndex(self, index):
        assert index == 1 and self.timeline is not None
        return self.timeline

    def GetSettings(self):
        return {
            "timelineFrameRate": "25",
            "timelinePlaybackFrameRate": "25",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
            "timelineSampleRate": "48000",
        }

    def GetRenderJobList(self):
        return []

    def IsRenderingInProgress(self):
        return False

    def GetMediaPool(self):
        return self.pool


class Project:
    def __init__(self):
        self.uid, self.name, self.timeline = "project-1", harness.PROJECT_NAME, None
        self.timeline = Timeline(self)
        self.pool = Pool(self.timeline.media)
        self.set_current_timeline_calls = []

    def GetName(self):
        return self.name

    def GetUniqueId(self):
        return self.uid

    def GetCurrentTimeline(self):
        return self.timeline

    def SetCurrentTimeline(self, timeline):
        assert timeline is self.timeline
        self.set_current_timeline_calls.append(timeline.uid)
        return True

    def GetSettings(self):
        return {
            "timelineFrameRate": "25",
            "timelinePlaybackFrameRate": "25",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
            "timelineSampleRate": "48000",
        }

    def GetRenderJobList(self):
        return []

    def IsRenderingInProgress(self):
        return False

    def GetMediaPool(self):
        return self.pool

    def SetSettings(self, settings):
        self.settings = dict(settings)
        return True

    def GetTimelineCount(self):
        return 1

    def GetTimelineByIndex(self, index):
        assert index == 1
        return self.timeline


class PartialProject:
    """Native-shaped stopped preparation: named, saved, empty, playback 24."""

    def __init__(self):
        self.uid, self.name = (
            "1a05ff3a-8b04-43e3-95ab-c970b93b6415",
            harness.PROJECT_NAME,
        )
        self.pool = ImportPool(Media())
        self.settings_reads = 0
        self.settings_writes = 0

    def GetName(self):
        return self.name

    def GetUniqueId(self):
        return self.uid

    def GetCurrentTimeline(self):
        return None

    def GetTimelineCount(self):
        return 0

    def GetTimelineByIndex(self, index):
        raise AssertionError("empty partial project has no timelines")

    def GetSettings(self):
        self.settings_reads += 1
        return {
            "timelineFrameRate": "25",
            "timelinePlaybackFrameRate": "24",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
            "timelineSampleRate": "48000",
        }

    def SetSettings(self, settings):
        self.settings_writes += 1
        raise AssertionError("import-media must not set project settings")

    def GetRenderJobList(self):
        return []

    def IsRenderingInProgress(self):
        return False

    def GetMediaPool(self):
        return self.pool


class BuildItem:
    def __init__(self, uid, track, index):
        self.uid, self.track, self.index = uid, track, index
        self.enabled, self.links = True, []
        self.speed = {"Percentage": 100.0, "PitchCorrection": True}
        self.mapping = '{"track_mapping":{"1":{"mute":false,"channel":1}}}'

    def GetUniqueId(self):
        return self.uid

    def GetTrackTypeAndIndex(self):
        return [self.track, self.index]

    def GetLinkedItems(self):
        return list(self.links)

    def SetClipEnabled(self, enabled):
        self.enabled = enabled
        return True

    def GetClipEnabled(self):
        return self.enabled

    def GetSpeed(self):
        return dict(self.speed)

    def SetSpeed(self, options):
        self.speed = dict(options)
        return True

    def GetSourceAudioChannelMapping(self):
        return self.mapping

    def SetSourceAudioChannelMapping(self, mapping):
        self.mapping = mapping
        return True


class BuildTimeline:
    def __init__(self, project, name, uid):
        self.project, self.name, self.uid = project, name, uid
        self.tracks = {"video": [[]], "audio": [[]], "subtitle": []}
        self.subtypes = {"video": ["video"], "audio": ["mono"], "subtitle": []}
        self.settings = {
            "timelineFrameRate": 25,
            "timelinePlaybackFrameRate": "24",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
            "timelineSampleRate": "48000",
        }
        self.append_calls, self.start_timecode, self.link_calls = [], None, []

    def GetName(self):
        return self.name

    def GetUniqueId(self):
        return self.uid

    def GetSettings(self):
        return dict(self.settings)

    def SetStartTimecode(self, value):
        self.start_timecode = value
        return True

    def DuplicateTimeline(self, name):
        duplicate = BuildTimeline(
            self.project, name, f"timeline-{len(self.project.timelines) + 1}"
        )
        self.project.timelines.append(duplicate)
        return duplicate

    def CreateSubtitlesFromAudio(self):
        self.project.subtitle_job_running = True
        self.tracks["subtitle"] = [[BuildItem("subtitle-1", "subtitle", 1)]]
        self.project.subtitle_status = {
            "JobStatus": "Complete",
            "CompletionPercentage": 100,
        }
        return True

    def GetTrackCount(self, kind):
        return len(self.tracks[kind])

    def AddTrack(self, kind, subtype=None):
        self.tracks[kind].append([])
        self.subtypes[kind].append(subtype or kind)
        return True

    def GetTrackSubType(self, kind, index):
        return self.subtypes[kind][index - 1]

    def GetItemListInTrack(self, kind, index):
        return list(self.tracks[kind][index - 1])

    def SetClipsLinked(self, items, linked):
        self.link_calls.append((list(items), linked))
        for item in items:
            item.links = [other for other in items if other is not item] if linked else []
        return True

    def Export(self, path, export_type, export_subtype):
        Path(path).write_text("synthetic otio\n", encoding="utf-8")
        return True


class BuildFolder:
    def __init__(self, clips):
        self.clips = clips

    def GetClipList(self):
        return list(self.clips)

    def GetSubFolderList(self):
        return []


class BuildPool:
    def __init__(self, project):
        self.project = project
        self.clips = [
            Media("media-base", "base.mov"),
            Media("media-a2", "a2_numbers.wav"),
            Media("media-a3", "a3_bed.wav"),
        ]
        self.root = BuildFolder(self.clips)
        self.next_timeline, self.next_item = 1, 1

    def GetRootFolder(self):
        return self.root

    def CreateEmptyTimeline(self, name):
        timeline = BuildTimeline(self.project, name, f"timeline-{self.next_timeline}")
        self.next_timeline += 1
        self.project.timelines.append(timeline)
        return timeline

    def AppendToTimeline(self, entries):
        info = entries[0]
        timeline = self.project.current
        media = info["mediaPoolItem"]
        track = info["trackIndex"]
        if "mediaType" not in info:
            rows = [("video", 1), ("audio", 1)]
        else:
            rows = [("video" if info["mediaType"] == 1 else "audio", track)]
        result = []
        for kind, index in rows:
            item = BuildItem(f"item-{self.next_item}", kind, index)
            self.next_item += 1
            timeline.tracks[kind][index - 1].append(item)
            result.append(item)
        timeline.append_calls.append((media.GetName(), info))
        return result


class BuildProject:
    def __init__(self, timeline_rate=25):
        self.uid, self.name = "build-project", harness.PROJECT_NAME
        self.timelines, self.current = [], None
        self.pool = BuildPool(self)
        self.timeline_rate = timeline_rate
        self.render_mode = 0
        self.render_format = {"format": "mp4", "codec": "H264"}
        self.render_settings = {}
        self.render_jobs = []
        self.render_status = {}
        self.subtitle_status = {"JobStatus": "Complete", "CompletionPercentage": 100}
        self.subtitle_status_sequence = []
        self.subtitle_status_reads = 0
        self.subtitle_job_running = False

    def GetName(self):
        return self.name

    def GetUniqueId(self):
        return self.uid

    def GetTimelineCount(self):
        return len(self.timelines)

    def GetTimelineByIndex(self, index):
        return self.timelines[index - 1]

    def GetCurrentTimeline(self):
        return self.current

    def SetCurrentTimeline(self, timeline):
        self.current = timeline
        return True

    def GetSettings(self):
        return {"timelineSampleRate": "48000"}

    def GetMediaPool(self):
        return self.pool

    def GetRenderJobList(self):
        return list(self.render_jobs)

    def IsRenderingInProgress(self):
        return False

    def SetCurrentRenderMode(self, mode):
        self.render_mode = mode
        return True

    def GetCurrentRenderMode(self):
        return self.render_mode

    def SetCurrentRenderFormatAndCodec(self, format, codec):
        self.render_format = {"format": format, "codec": codec}
        return True

    def GetCurrentRenderFormatAndCodec(self):
        return dict(self.render_format)

    def SetRenderSettings(self, settings):
        self.render_settings = dict(settings)
        return True

    def AddRenderJob(self):
        job_id = f"render-{len(self.render_jobs) + 1}"
        settings = self.render_settings
        job = {
            "JobId": job_id,
            "IsExportVideo": settings["ExportVideo"],
            "IsExportAudio": settings["ExportAudio"],
            "FormatWidth": settings["FormatWidth"],
            "FormatHeight": settings["FormatHeight"],
            "FrameRate": str(settings["FrameRate"]),
            "AudioBitDepth": settings["AudioBitDepth"],
            "AudioSampleRate": settings["AudioSampleRate"],
            "AudioCodec": settings["AudioCodec"],
            "VideoFormat": "QuickTime",
            "VideoCodec": "H.264",
        }
        self.render_jobs.append(job)
        self.render_status[job_id] = {"JobStatus": "Ready", "CompletionPercentage": 0}
        return job_id

    def StartRendering(self, job_ids):
        for job_id in job_ids:
            self.render_status[job_id] = {
                "JobStatus": "Complete",
                "CompletionPercentage": 100,
            }
        return True

    def GetRenderJobStatus(self, job_id):
        return dict(self.render_status[job_id])

    def GetCreateSubtitlesFromAudioStatus(self):
        self.subtitle_status_reads += 1
        if self.subtitle_status_sequence:
            return dict(self.subtitle_status_sequence.pop(0))
        return dict(self.subtitle_status)


def _build_config():
    return {
        "timelineSpecs": [
            {
                "name": "build-defaults",
                "audioTracks": 2,
                "videoTracks": 0,
                "placements": [
                    {
                        "mediaName": "base.mov",
                        "sourceStart": 0,
                        "sourceEndExclusive": 400,
                        "recordFrame": 0,
                        "trackType": "av",
                        "trackIndex": 1,
                    },
                    {
                        "mediaName": "a2_numbers.wav",
                        "sourceStart": 0,
                        "sourceEndExclusive": 400,
                        "recordFrame": 0,
                        "trackType": "audio",
                        "trackIndex": 2,
                    },
                    {
                        "mediaName": "a3_bed.wav",
                        "sourceStart": 0,
                        "sourceEndExclusive": 400,
                        "recordFrame": 0,
                        "trackType": "audio",
                        "trackIndex": 3,
                    },
                ],
                "disabledAudioTracks": [1],
                "linkVideoAudio": True,
            }
        ]
    }


def _build_checks():
    with tempfile.TemporaryDirectory() as directory:
        config = _build_config()
        project = BuildProject()
        resolve = Resolve(project)
        journal = harness.Journal(Path(directory), "build-check")
        result = harness._build(resolve, config, project, journal)
        row = result["createdTimelines"][0]
        assert row["defaultTrackCounts"] == {"video": 1, "audio": 1}
        assert row["explicitTrackCounts"] == {"video": 1, "audio": 3}
        assert row["timelineShape"]["expected"]["timelineFrameRate"] == 25.0
        assert row["disabledAudioTracks"][0]["readback"] is False
        assert len(row["linkVideoAudio"]) == 1
        assert row["linkVideoAudio"][0]["readback"][0]["linkedUids"] == ["item-2"]
        assert row["linkVideoAudio"][0]["readback"][1]["linkedUids"] == ["item-1"]
        assert project.timelines[0].start_timecode == "00:00:00:00"
        assert [call[0] for call in project.timelines[0].append_calls] == [
            "base.mov",
            "a2_numbers.wav",
            "a3_bed.wav",
        ]
        assert resolve.manager.save_calls == 1

        bad_project = BuildProject(timeline_rate=24)
        bad_project.pool.CreateEmptyTimeline = lambda name: _bad_timeline(
            bad_project, name
        )
        bad_resolve = Resolve(bad_project)
        bad_journal = harness.Journal(Path(directory), "build-bad-fps")
        try:
            harness._build(bad_resolve, config, bad_project, bad_journal)
        except harness.HarnessError as error:
            assert "timeline setting differs" in str(error)
        else:
            raise AssertionError("24 fps timeline was accepted")
        assert bad_project.timelines[0].append_calls == []
        assert bad_resolve.manager.save_calls == 0

        fallback_project = BuildProject()
        fallback_project.pool.CreateEmptyTimeline = lambda name: _no_sample_timeline(
            fallback_project, name
        )
        fallback_journal = harness.Journal(Path(directory), "build-project-sample")
        fallback_result = harness._build(
            Resolve(fallback_project), config, fallback_project, fallback_journal
        )
        assert (
            fallback_result["createdTimelines"][0]["timelineShape"]["sampleRateSource"]
            == "project"
        )

        separate_config = deepcopy(config)
        separate_config["timelineSpecs"][0]["name"] = "build-separate"
        separate_config["timelineSpecs"][0]["placements"][0:1] = [
            {
                "mediaName": "base.mov",
                "sourceStart": 0,
                "sourceEndExclusive": 400,
                "recordFrame": 0,
                "trackType": "video",
                "trackIndex": 1,
            },
            {
                "mediaName": "base.mov",
                "sourceStart": 0,
                "sourceEndExclusive": 400,
                "recordFrame": 0,
                "trackType": "audio",
                "trackIndex": 1,
            },
        ]
        separate_project = BuildProject()
        separate_resolve = Resolve(separate_project)
        separate_journal = harness.Journal(Path(directory), "build-separate")
        separate_result = harness._build(
            separate_resolve, separate_config, separate_project, separate_journal
        )
        separate_links = separate_result["createdTimelines"][0]["linkVideoAudio"]
        assert len(separate_links) == 1
        assert separate_links[0]["readback"][0]["linkedUids"] == ["item-2"]
        assert separate_links[0]["readback"][1]["linkedUids"] == ["item-1"]
        selected = harness._select_timeline(
            separate_resolve,
            separate_project,
            {"timelineUid": "timeline-1", "page": "edit"},
            harness.Journal(Path(directory), "select-edit"),
        )
        assert selected["page"] == {"openReturn": True, "readback": "edit"}

        render_journal = harness.Journal(Path(directory), "render-stage")
        render = harness._render_stage(
            separate_resolve,
            separate_project,
            {
                "outputDir": directory,
                "timelineUid": "timeline-1",
                "render": {"settings": {"CustomName": "build-separate"}},
            },
            render_journal,
        )
        assert render["renderMode"]["readback"] == 1
        assert render["formatCodec"]["readback"] == {"format": "mov", "codec": "H264"}
        assert render["queuedJob"]["AudioBitDepth"] == 16
        assert render["queuedJob"]["FrameRate"] == "25"
        queue_count = len(separate_project.render_jobs)
        try:
            harness._render_stage(
                separate_resolve,
                separate_project,
                {
                    "outputDir": directory,
                    "timelineUid": "timeline-does-not-exist",
                    "render": {"settings": {}},
                },
                harness.Journal(Path(directory), "render-wrong-timeline"),
            )
        except harness.HarnessError as error:
            assert "timeline differs" in str(error)
        else:
            raise AssertionError("render accepted a non-current timeline")
        assert len(separate_project.render_jobs) == queue_count
        failed_id = render["jobId"]
        separate_project.render_status[failed_id] = {
            "JobStatus": "Failed",
            "CompletionPercentage": 10,
            "Error": "decode",
        }
        poll = harness._render_poll(
            separate_project,
            {"jobId": failed_id, "pollTimeoutSec": 0},
            harness.Journal(Path(directory), "render-failed"),
        )
        assert poll["classification"] == "adverse"
        for index, state in enumerate(
            ("Background Render Cancelled", "Remote Render Canceled"), start=1
        ):
            separate_project.render_status[failed_id] = {
                "JobStatus": state,
                "CompletionPercentage": 100,
            }
            cancelled = harness._render_poll(
                separate_project,
                {"jobId": failed_id, "pollTimeoutSec": 0},
                harness.Journal(Path(directory), f"render-cancelled-{index}"),
            )
            assert cancelled["renderPoll"] == "terminal"
            assert cancelled["classification"] == "terminal"

        exports = Path(directory) / "exports"
        exports.mkdir()
        speed = harness._w4_speed(
            separate_resolve,
            separate_project,
            {
                "timelineUid": "timeline-1",
                "itemUids": ["item-1", "item-3"],
                "speedOptions": {"Percentage": 37.5, "PitchCorrection": False},
                "outputDir": directory,
                "export": {"path": str(exports / "w4.otio")},
            },
            harness.Journal(Path(directory), "w4-speed"),
        )
        assert speed["itemUids"] == ["item-1", "item-3"]
        assert len(speed["speedReadbacks"]) == 2
        assert speed["otio"]["return"] is True

        mute = harness._w3_mute(
            separate_resolve,
            separate_project,
            {"timelineUid": "timeline-1", "itemUid": "item-3"},
            harness.Journal(Path(directory), "w3-mute"),
        )
        assert mute["targetOnlyDelta"]["onlyTarget"] is True
        assert json.loads(mute["mutedReadback"]) == json.loads(mute["mutedMapping"])
        restore = harness._w3_restore(
            separate_project,
            {
                "timelineUid": "timeline-1",
                "itemUid": "item-3",
                "mutedMapping": mute["mutedMapping"],
                "originalMapping": mute["originalMapping"],
            },
            harness.Journal(Path(directory), "w3-restore"),
        )
        assert restore["restoreRequest"] == mute["originalMapping"]
        assert json.loads(restore["restoredMapping"]) == json.loads(mute["originalMapping"])

        save_calls_before_request = separate_resolve.manager.save_calls
        request = harness._w1_request(
            separate_resolve,
            separate_project,
            {
                "duplicates": [
                    {"sourceTimelineUid": "timeline-1", "duplicateName": "w1-copy"}
                ]
            },
            harness.Journal(Path(directory), "w1-request"),
        )
        assert request["editPage"]["readback"] == "edit"
        assert request["saveCheckpointTiming"] == "before-subtitle-request"
        assert separate_resolve.manager.save_calls == save_calls_before_request + 1
        separate_project.subtitle_status_sequence = [
            {"JobStatus": "Queued", "CompletionPercentage": 100},
            {"JobStatus": "Complete", "CompletionPercentage": 100},
        ]
        poll = harness._w1_poll(
            separate_project,
            {
                "duplicateTimelineUids": ["timeline-2"],
                "pollTimeoutSec": 1,
                "pollIntervalSec": 0.05,
            },
            harness.Journal(Path(directory), "w1-poll"),
        )
        assert poll["status"] == "complete"
        assert poll["subtitlePoll"][0]["status"]["value"]["JobStatus"] == "Complete"
        assert separate_project.subtitle_status_reads >= 2


def _bad_timeline(project, name):
    timeline = BuildTimeline(project, name, "timeline-bad")
    timeline.settings["timelineFrameRate"] = 24
    project.timelines.append(timeline)
    return timeline


def _no_sample_timeline(project, name):
    timeline = BuildTimeline(project, name, "timeline-project-sample")
    del timeline.settings["timelineSampleRate"]
    project.timelines.append(timeline)
    return timeline


class Manager:
    def __init__(self, project=None, save_return=True):
        self.project, self.create_calls = project, 0
        self.save_return, self.save_calls = save_return, 0

    def GetCurrentProject(self):
        return self.project

    def CreateProject(self, name):
        self.create_calls += 1
        assert self.project is None or self.project.GetName() == harness.STARTUP_PROJECT_NAME
        self.project = Project()
        self.project.name = name
        return True

    def SaveProject(self):
        self.save_calls += 1
        if getattr(self.project, "subtitle_job_running", False):
            return None
        return self.save_return


class Resolve:
    def __init__(self, project=None, save_return=True):
        self.manager = Manager(project, save_return)
        self.page = "edit"

    EXPORT_OTIO = 1
    EXPORT_NONE = 0

    def GetVersion(self):
        return [21, 1, 1, 10, ""]

    def GetCurrentPage(self):
        return self.page

    def OpenPage(self, page):
        self.page = page
        return True

    def GetProjectManager(self):
        return self.manager


def _config(root: Path, action_id: str, action: str = "context") -> dict:
    out = root / "out" / harness.OUTPUT_NAME
    media = out / "media"
    media.mkdir(parents=True, exist_ok=True)
    probe = HERE / "harness.py"
    config = {
        "schemaVersion": harness.SCHEMA_VERSION,
        "externalScriptingSetting": "None",
        "projectName": harness.PROJECT_NAME,
        "action": action,
        "phase": action_id,
        "actionId": action_id,
        "probePath": str(probe),
        "probeSha256": hashlib.sha256(probe.read_bytes()).hexdigest(),
        "outputDir": str(out),
        "mediaDir": str(media),
    }
    if action == "prepare":
        config["allowEmptyUntitled"] = True
    return config


def _guard_checks():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        good = _config(root, "guard-01")
        harness._validate_config(good)
        for key, value in (
            ("externalScriptingSetting", "Local"),
            ("projectName", "old project"),
            ("action", "__disarmed__"),
        ):
            broken = dict(good)
            broken[key] = value
            try:
                harness._validate_config(broken)
            except harness.HarnessError:
                pass
            else:
                raise AssertionError(f"malformed guard accepted: {key}")


def _raw_status_checks():
    class Proxy:
        def __init__(self, apparent_class):
            self.apparent_class = apparent_class

        @property
        def __class__(self):
            return self.apparent_class

        def __repr__(self):
            return "<proxy>"

    class Broken:
        def GetError(self):
            raise RuntimeError("native getter failed")

        def GetNone(self):
            return None

    with tempfile.TemporaryDirectory() as directory:
        journal = harness.Journal(Path(directory), "raw-status")
        _, missing = harness._getter(journal, Broken(), "GetMissing")
        _, error = harness._getter(journal, Broken(), "GetError")
        value, empty = harness._getter(journal, Broken(), "GetNone")
        assert missing["status"] == "missing"
        assert error["status"] == "error"
        assert empty == {"status": "ok", "value": None}
        assert value is None
        for apparent_class in (None, lambda: None):
            encoded = harness._json_value(Proxy(apparent_class))
            assert encoded == {"__native_type__": "Proxy", "__repr__": "<proxy>"}


def _save_checkpoint_checks():
    for save_return, expected_status in ((True, "ok"), (False, "failure")):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = StartupProject(name=harness.PROJECT_NAME)
            resolve = Resolve(project, save_return=save_return)
            config = _config(root, f"save-checkpoint-{save_return}", "save-checkpoint")
            config.update(
                {
                    "stateId": f"save-checkpoint-{save_return}",
                    "owned": {
                        "projectUid": project.uid,
                        "timelineUids": [],
                        "itemUids": [],
                        "mediaUids": [],
                    },
                }
            )
            result = harness.run(resolve, config)
            assert result["status"] == expected_status
            assert resolve.manager.save_calls == 1
            evidence = Path(result["journal"]).parent
            assert (evidence / "pre.json").is_file()
            assert (evidence / ("post.json" if save_return else "post-partial.json")).is_file()


def _stable_snapshot_checks():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory)
        project = Project()
        resolve = Resolve(project)
        journal = harness.Journal(output, "stable-pair")
        first = harness.snapshot(resolve, journal, project)
        second = harness.snapshot(resolve, journal, project)
        assert first["complete"] is True
        assert first == second
        assert (
            first["project"]["timelines"][0]["tracks"]["audio"][0][
                "GetItemListInTrack"
            ]["value"][0]["GetSpeed"]["value"]["Percentage"]
            == 100.0
        )


def _select_timeline_timecode_checks():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        project = Project()
        resolve = Resolve(project)
        config = _config(root, "select-timecode-01", "select-timeline")
        config.update(
            {
                "stateId": "select-timecode-01",
                "timelineUid": project.timeline.uid,
                "page": "edit",
                "timecode": "00:00:02:00",
                "owned": {
                    "projectUid": project.uid,
                    "timelineUids": [project.timeline.uid],
                    "itemUids": [project.timeline.item.uid],
                    "mediaUids": [project.timeline.media.uid],
                },
            }
        )
        result = harness.run(resolve, config)
        assert result["status"] == "ok"
        assert result["setCurrentTimecodeReturn"] is True
        assert result["readbackTimecode"] == "00:00:02:00"
        assert project.set_current_timeline_calls == [project.timeline.uid]
        assert project.timeline.set_current_timecode_calls == ["00:00:02:00"]
        evidence = Path(result["journal"]).parent
        pre = json.loads((evidence / "pre.json").read_text())
        post = json.loads((evidence / "post.json").read_text())
        assert pre["complete"] is True and post["complete"] is True
        assert pre["project"]["timelines"][0]["getters"]["GetCurrentTimecode"]["value"] == "00:00:00:00"
        assert post["project"]["timelines"][0]["getters"]["GetCurrentTimecode"]["value"] == "00:00:02:00"


def _observe_checks():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        project = Project()
        resolve = Resolve(project)
        config = _config(root, "observe-01", "observe")
        config.update(
            {
                "stateId": "observe-01",
                "owned": {
                    "projectUid": project.uid,
                    "timelineUids": [project.timeline.uid],
                    "itemUids": [project.timeline.item.uid],
                    "mediaUids": [project.timeline.media.uid],
                },
            }
        )
        result = harness.run(resolve, config)
        assert result["status"] == "ok"
        assert result["observe"]["readOnly"] is True
        assert project.set_current_timeline_calls == []
        assert project.timeline.set_current_timecode_calls == []
        evidence = Path(result["journal"]).parent
        pre = json.loads((evidence / "pre.json").read_text())
        post = json.loads((evidence / "post.json").read_text())
        assert pre == post
        selected = pre["project"]["timelines"][0]["selectedClips"]
        assert selected["status"] == "ok" and isinstance(selected["value"], list)
        assert len(selected["value"]) == 1


def _import_media_checks():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        media = root / "out" / harness.OUTPUT_NAME / "media" / "base.mov"
        media.parent.mkdir(parents=True, exist_ok=True)
        media.write_bytes(b"synthetic-base")
        digest = hashlib.sha256(media.read_bytes()).hexdigest()
        config = _config(root, "import-media-01", "import-media")
        config.update(
            {
                "stateId": "import-media-01",
                "owned": {
                    "projectUid": "1a05ff3a-8b04-43e3-95ab-c970b93b6415",
                    "timelineUids": [],
                    "itemUids": [],
                    "mediaUids": [],
                },
                "media": [{"name": "base.mov", "relative": "base.mov", "sha256": digest}],
            }
        )
        resolve = Resolve(PartialProject())
        result = harness.run(resolve, config)
        assert result["status"] == "ok"
        assert result["state"]["projectUid"] == config["owned"]["projectUid"]
        assert result["media"][0]["name"] == "base.mov"
        assert resolve.manager.create_calls == 0
        assert resolve.manager.save_calls == 1
        assert resolve.manager.project.settings_writes == 0
        assert resolve.manager.project.pool.import_calls == [[str(media)]]

        bad_config = _config(root, "import-media-bad-hash", "import-media")
        bad_config.update(config)
        bad_config.update(
            {
                "actionId": "import-media-bad-hash",
                "phase": "import-media-bad-hash",
                "stateId": "import-media-bad-hash",
                "media": [
                    {"name": "base.mov", "relative": "base.mov", "sha256": digest},
                    {"name": "missing.mov", "relative": "base.mov", "sha256": "0" * 64},
                ],
            }
        )
        rejected_resolve = Resolve(PartialProject())
        rejected = harness.run(rejected_resolve, bad_config)
        assert rejected["status"] == "failure"
        assert rejected_resolve.manager.create_calls == 0
        assert rejected_resolve.manager.save_calls == 0
        assert rejected_resolve.manager.project.pool.import_calls == []


def _launcher_checks():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        config_path = root / "vera-issue-149-workflow-reruns.json"
        config = _config(root, "context-01")
        config_path.write_text(json.dumps(config), encoding="utf-8")
        returned = launcher.main(Resolve(), config_path)
        assert returned["status"] == "ok"
        assert json.loads(config_path.read_text())["action"] == "__disarmed__"
        try:
            launcher.main(Resolve(), config_path)
        except RuntimeError as error:
            assert "already been dispatched" in str(error)
        else:
            raise AssertionError("duplicate action was accepted")

        second = _config(root, "context-02")
        second_path = root / "second-config.json"
        second_path.write_text(json.dumps(second), encoding="utf-8")
        failed = launcher.main(None, second_path)
        assert failed["status"] == "launcher-failed"
        assert json.loads(second_path.read_text())["action"] == "__disarmed__"

        media = root / "out" / harness.OUTPUT_NAME / "media" / "base.mov"
        media.write_bytes(b"synthetic-base")
        bad = _config(root, "prepare-bad-hash", "prepare")
        bad["stateId"] = "prepare-bad-hash"
        bad["media"] = [
            {"name": "base.mov", "relative": "base.mov", "sha256": "0" * 64}
        ]
        bad_path = root / "prepare-bad-hash.json"
        bad_path.write_text(json.dumps(bad), encoding="utf-8")
        bad_resolve = Resolve(StartupProject())
        bad_result = launcher.main(bad_resolve, bad_path)
        assert bad_result["status"] == "failure"
        assert bad_resolve.manager.create_calls == 0

        readonly = _config(root, "prepare-readonly", "prepare")
        readonly["stateId"] = "prepare-readonly"
        readonly["settings"] = {"timelinePlaybackFrameRate": "25"}
        readonly["media"] = [
            {
                "name": "base.mov",
                "relative": "base.mov",
                "sha256": hashlib.sha256(media.read_bytes()).hexdigest(),
            }
        ]
        readonly_path = root / "prepare-readonly.json"
        readonly_path.write_text(json.dumps(readonly), encoding="utf-8")
        readonly_resolve = Resolve(StartupProject())
        readonly_result = launcher.main(readonly_resolve, readonly_path)
        assert readonly_result["status"] == "failure"
        assert readonly_resolve.manager.create_calls == 0

        media_hash = hashlib.sha256(media.read_bytes()).hexdigest()

        def rejected(action_id, resolve):
            rejected_config = _config(root, action_id, "prepare")
            rejected_config["stateId"] = action_id
            rejected_config["media"] = [
                {
                    "name": "base.mov",
                    "relative": "base.mov",
                    "sha256": media_hash,
                }
            ]
            rejected_path = root / f"{action_id}.json"
            rejected_path.write_text(json.dumps(rejected_config), encoding="utf-8")
            rejected_result = launcher.main(resolve, rejected_path)
            assert rejected_result["status"] == "failure"
            assert resolve.manager.create_calls == 0

        rejected("prepare-old-project", Resolve(StartupProject(name="Old Project")))
        rejected("prepare-nonempty", Resolve(StartupProject(nonempty=True)))
        rejected("prepare-float-timeline-count", Resolve(StartupProject(timeline_count=0.0)))

        prepare = _config(root, "prepare-01", "prepare")
        prepare["stateId"] = "prepare-01"
        prepare["media"] = [
            {
                "name": "base.mov",
                "relative": "base.mov",
                "sha256": media_hash,
            }
        ]
        prepare_path = root / "prepare-config.json"
        prepare_path.write_text(json.dumps(prepare), encoding="utf-8")
        prepare_resolve = Resolve(StartupProject())
        prepared = launcher.main(prepare_resolve, prepare_path)
        assert prepared["status"] == "ok"
        assert prepared["state"]["projectUid"] == "project-1"
        assert prepare_resolve.manager.create_calls == 1


def demo():
    _guard_checks()
    _raw_status_checks()
    _save_checkpoint_checks()
    _stable_snapshot_checks()
    _select_timeline_timecode_checks()
    _observe_checks()
    _build_checks()
    _import_media_checks()
    _launcher_checks()
    assert "scriptapp" not in (HERE / "harness.py").read_text()
    assert "scriptapp" not in (HERE / "launcher.py").read_text()
    print("Issue 149 discriminator harness checks passed; no native application was launched")


if __name__ == "__main__":
    demo()
