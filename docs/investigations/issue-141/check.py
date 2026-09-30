"""Run with Python -S; these checks are harness evidence, never Resolve evidence."""

import importlib.util
import json
import struct
import sys
import tempfile
import wave
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "probe", Path(__file__).with_name("probe.py")
)
assert spec is not None and spec.loader is not None
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def refuses(call):
    try:
        call()
    except (ValueError, RuntimeError):
        return
    raise AssertionError("unsafe input was accepted")


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    media = root / "media.wav"
    media.write_bytes(b"synthetic")
    expected = {str(media): probe.sha256(media)}
    assert probe.source_evidence(str(media), expected)["hashMatches"] is True
    assert probe.source_evidence(str(root / "missing"), expected) == {
        "status": "unapproved-locator-not-accessed"
    }
    media.write_bytes(b"wrong bytes at the same locator")
    assert probe.source_evidence(str(media), expected)["hashMatches"] is False
    media.unlink()
    assert probe.source_evidence(str(media), expected)["status"] == "unavailable"
    config = {
        "projectName": "VERA Issue 141 Synthetic Probe test",
        "externalScriptingSetting": "None",
        "action": "prepare",
        "mediaDir": str(root),
        "outputDir": str(root / "evidence"),
    }
    probe.validate_config(config)
    for key, value in (
        ("externalScriptingSetting", "Local"),
        ("projectName", "Existing project"),
        ("action", "delete"),
        ("mediaDir", "relative"),
    ):
        refuses(
            lambda key=key, value=value: probe.validate_config({**config, key: value})
        )


class Item:
    def __getattr__(self, name):
        assert name.startswith("Get"), f"observer mutated via {name}"
        if name == "GetMediaPoolItem":
            return lambda: None
        if name == "GetLinkedItems":
            return lambda: []
        return lambda *args: "same"


class Broken:
    def GetUniqueId(self):
        raise RuntimeError("real getter failure")


raw = probe.read(Broken(), "GetUniqueId")
assert raw["error"] == "RuntimeError: real getter failure"
assert probe.read(Item(), "GetUniqueId") == {"value": "same"}
assert probe.item_evidence(Item(), {})["GetUniqueId"] == {"value": "same"}
assert probe.consistency({"items": [1]}, {"items": [1]}, []) == "equal-adjacent-reads"
assert probe.consistency({"items": [1]}, {"items": [2]}, []) == "inconsistent-refused"
assert (
    probe.consistency({"items": [1]}, {"items": [1]}, ["missing getter"])
    == "incomplete-refused"
)
assert probe.errors({"value": None}) == ["null-getter-result-not-established"]


class Project:
    def GetName(self):
        return "VERA Issue 141 Synthetic Probe test"

    def GetUniqueId(self):
        return "project-test"

    def GetTimelineCount(self):
        return 1

    def GetTimelineByIndex(self, index):
        assert index == 1
        return Timeline()

    def GetSettings(self):
        return probe.SETTINGS


class Timeline:
    def GetName(self):
        return "VERA 141 test"

    def GetTrackCount(self, kind):
        return 1 if kind == "video" else 0

    def GetItemListInTrack(self, kind, index):
        assert (kind, index) == ("video", 1)
        return [Item()]

    def __getattr__(self, name):
        assert name.startswith("Get"), f"Observer mutated timeline via {name}"
        return lambda *args: "same"


class Manager:
    def GetCurrentProject(self):
        return Project()


class Resolve:
    def GetProjectManager(self):
        return Manager()


identity = {"projectId": "project-test"}
assert (
    probe.require_current(Resolve(), config, identity).GetUniqueId() == "project-test"
)
refuses(lambda: probe.require_current(Resolve(), config, {"projectId": "wrong"}))
refuses(lambda: probe.require_current(Resolve(), config, {"projectId": None}))
observed = probe.observe(Resolve(), config, identity, {})
assert observed["timelines"][0]["tracks"][0]["items"][0]["GetUniqueId"] == {
    "value": "same"
}

# Retain changed and failed capture passes, rather than losing the original error.
original_observe = probe.observe
with tempfile.TemporaryDirectory() as directory:
    output = Path(directory)
    values = iter([{"revision": 1}, {"revision": 2}])
    probe.observe = lambda *args: next(values)
    result = probe.capture(None, {}, {}, {}, output, "changed", {"test": True})
    assert result["status"] == "inconsistent-refused"
    retained = json.loads(Path(result["capturePath"]).read_text())
    assert retained["passes"] == [{"revision": 1}, {"revision": 2}]
    assert len(set(retained["contentFingerprints"])) == 2
    assert retained["applicationRevisionToken"] is None

    def failure(*args):
        raise RuntimeError("injected observation failed")

    probe.observe = failure
    result = probe.capture(None, {}, {}, {}, output, "failed", {"test": True})
    retained = json.loads(Path(result["capturePath"]).read_text())
    assert result["status"] == "incomplete-refused"
    assert retained["captureFailure"] == "RuntimeError: injected observation failed"
probe.observe = original_observe


# A real preparation attempt refuses collisions, changed bytes and manifest drift
# before CreateProject or even creation of the evidence directory.
class PreflightResolve(Resolve):
    def GetProductName(self):
        return "DaVinci Resolve Studio"

    def GetVersion(self):
        return [21, 1, 0, 14, ""]

    def GetProjectManager(self):
        class ExistingManager:
            def GetProjectListInCurrentFolder(self):
                return ["VERA Issue 141 Synthetic Probe test"]

            def CreateProject(self, name):
                raise AssertionError("Unsafe preparation reached mutation")

        return ExistingManager()


original_root = probe.ROOT
with tempfile.TemporaryDirectory() as directory:
    probe.ROOT = Path(directory)
    media_root = probe.ROOT / "out/issue-141-media-test"
    media_root.mkdir(parents=True)
    source = media_root / "source.wav"
    source.write_bytes(b"synthetic")
    manifest_path = media_root / "manifest.json"
    manifest = {
        "kind": "generated-synthetic-inputs-not-Resolve-evidence",
        "installedDocs": {},
        "files": [{"path": "source.wav", "sha256": probe.sha256(source)}],
    }
    manifest_path.write_text(json.dumps(manifest))
    trial = {
        **config,
        "mediaDir": str(media_root),
        "outputDir": str(probe.ROOT / "out/issue-141-observation-test"),
        "manifestSha256": probe.sha256(manifest_path),
    }
    refuses(lambda: probe.run(PreflightResolve(), trial))
    assert not Path(trial["outputDir"]).exists()
    source.write_bytes(b"unexpected bytes")
    refuses(lambda: probe.run(PreflightResolve(), trial))
    assert not Path(trial["outputDir"]).exists()
    manifest_path.write_text("{}")
    refuses(lambda: probe.run(PreflightResolve(), trial))
    assert not Path(trial["outputDir"]).exists()
probe.ROOT = original_root

# Exercise the bounded native repeat without Resolve, including its load guard.
with tempfile.TemporaryDirectory() as directory:
    original_root = probe.ROOT
    original_observe = probe.observe
    original_capture = probe.capture
    probe.ROOT = Path(directory)
    project_name = "VERA Issue 141 Synthetic Probe test"
    baseline_id = "88f7923d-55a7-471f-b09b-cf10f9fae8ad"
    project_id = "project-test"
    duplicate_name = "VERA 141 R1 identity"

    def snapshot(project):
        timelines = []
        for timeline in project.timelines:
            timelines.append(
                {
                    "GetName": {"value": timeline.name},
                    "GetUniqueId": {"value": timeline.uid},
                    "tracks": [
                        {
                            "type": "video" if index < 3 else "audio",
                            "index": index % 3 + 1,
                            "items": [{"GetUniqueId": {"value": f"item-{index}"}}],
                        }
                        for index in range(6)
                    ],
                }
            )
        return {
            "projectId": project_id,
            "projectName": project_name,
            "timelines": timelines,
        }

    class NativeTimeline:
        def __init__(self, project, name, uid):
            self.project, self.name, self.uid = project, name, uid

        def GetName(self):
            return self.name

        def GetUniqueId(self):
            return self.uid

        def DuplicateTimeline(self, name):
            duplicate = NativeTimeline(self.project, name, "duplicate-test")
            self.project.timelines.append(duplicate)
            return duplicate

    class NativeProject:
        def __init__(self, extra=False):
            self.timelines = [NativeTimeline(self, "VERA 141 Baseline", baseline_id)]
            if extra:
                self.timelines.append(
                    NativeTimeline(self, "VERA 141 unexpected", "extra")
                )
            self.current = self.timelines[0]

        def GetName(self):
            return project_name

        def GetUniqueId(self):
            return project_id

        def GetTimelineCount(self):
            return len(self.timelines)

        def GetTimelineByIndex(self, index):
            return self.timelines[index - 1]

        def GetCurrentTimeline(self):
            return self.current

        def SetCurrentTimeline(self, timeline):
            self.current = timeline
            return True

    class NativeManager:
        def __init__(self, project, other_after_close=False):
            self.current = project
            self.other_after_close = other_after_close
            self.loads = []

        def GetCurrentProject(self):
            return self.current

        def SaveProject(self):
            return True

        def CloseProject(self, project):
            assert project is self.current
            self.current = NativeProject() if self.other_after_close else None
            return True

        def LoadProject(self, name):
            self.loads.append(name)
            self.current = prepared_project
            return prepared_project

    class NativeResolve:
        def __init__(self, project, other_after_close=False):
            self.manager = NativeManager(project, other_after_close)

        def GetProjectManager(self):
            return self.manager

    expected_identity = {
        "projectId": project_id,
        "projectName": project_name,
        "baselineTimelineId": baseline_id,
    }
    native_config = {
        "projectName": project_name,
        "manifestSha256": "manifest-hash",
        "action": "native-repeat",
    }
    environment = {"version": [21, 1, 0, 14, ""]}
    output = Path(directory) / "out/issue-141-observation-test"
    output.mkdir(parents=True)
    probe.write_json(
        output / "prepared.json",
        {"identity": expected_identity, "manifestSha256": "manifest-hash"},
    )
    baseline_pass = snapshot(NativeProject())
    baseline_path = output / "capture-20260930T173943.043191Z.json"
    probe.write_json(
        baseline_path,
        {
            "consistency": "equal-adjacent-reads",
            "passes": [baseline_pass, baseline_pass],
        },
    )
    original_sha256 = probe.sha256
    probe.sha256 = lambda path: (
        "92c04d10bafe86499b7d11a27d457e655893ee6340d73a290a80e29e35887161"
        if Path(path) == baseline_path
        else original_sha256(path)
    )
    probe.observe = lambda resolve, *args: snapshot(resolve.GetProjectManager().current)

    def native_capture(resolve, config, identity, expected, output, stamp, environment):
        value = snapshot(resolve.GetProjectManager().current)
        path = output / f"capture-{stamp}.json"
        probe.write_json(path, {"passes": [value, value]})
        return {"status": "equal-adjacent-reads", "capturePath": str(path)}

    probe.capture = native_capture
    prepared_project = NativeProject()
    resolve = NativeResolve(prepared_project)
    result = probe.native_repeat(
        resolve,
        native_config,
        {"projectId": project_id, "projectName": project_name},
        {},
        output,
        "native-test",
        environment,
    )
    assert result["status"] == "equal-adjacent-reads"
    assert resolve.manager.loads == [project_name]
    assert prepared_project.GetCurrentTimeline().GetName() == duplicate_name
    records = [
        json.loads(line)
        for line in (output / "native-repeat-native-test.jsonl")
        .read_text()
        .splitlines()
    ]
    assert [row["method"] for row in records if row["phase"] == "request"] == [
        "SaveProject",
        "CloseProject",
        "LoadProject",
        "DuplicateTimeline",
        "SetCurrentTimeline",
        "SaveProject",
    ]

    # Unexpected preexisting timeline state refuses before SaveProject.
    wrong = NativeProject(extra=True)
    wrong_resolve = NativeResolve(wrong)
    refuses(
        lambda: probe.native_repeat(
            wrong_resolve,
            native_config,
            {"projectId": project_id, "projectName": project_name},
            {},
            output,
            "wrong-state",
            environment,
        )
    )
    assert wrong_resolve.manager.loads == []

    # A project appearing after close blocks LoadProject from replacing it.
    blocked_project = NativeProject()
    blocked_resolve = NativeResolve(blocked_project, other_after_close=True)
    refuses(
        lambda: probe.native_repeat(
            blocked_resolve,
            native_config,
            {"projectId": project_id, "projectName": project_name},
            {},
            output,
            "load-guard",
            environment,
        )
    )
    assert blocked_resolve.manager.loads == []
    probe.observe, probe.capture, probe.sha256, probe.ROOT = (
        original_observe,
        original_capture,
        original_sha256,
        original_root,
    )

# Replay the settings boundary with the installed API's read-only playback rule.
with tempfile.TemporaryDirectory() as directory:
    probe.ROOT = Path(directory)
    media_root = probe.ROOT / "out/issue-141-media-test"
    media_root.mkdir(parents=True)
    source = media_root / "source.wav"
    source.write_bytes(b"synthetic")
    probe.write_json(
        media_root / "manifest.json",
        {
            "kind": "generated-synthetic-inputs-not-Resolve-evidence",
            "installedDocs": {},
            "files": [{"path": "source.wav", "sha256": probe.sha256(source)}],
        },
    )

    class SettingsProject(Project):
        def GetTimelineCount(self):
            return 0

        def __init__(self, playback):
            self.settings = {
                **probe.SETTINGS,
                "timelineFrameRate": 25.0,
                "timelinePlaybackFrameRate": playback,
            }
            self.requests = []

        def GetSettings(self):
            return dict(self.settings)

        def SetSettings(self, requested):
            self.requests.append(dict(requested))
            if "timelinePlaybackFrameRate" in requested:
                return False
            self.settings.update(requested)
            return True

        def GetMediaPool(self):
            return self

        def ImportMedia(self, *args):
            raise RuntimeError("Synthetic import boundary reached")

    class SettingsResolve(PreflightResolve):
        def GetProjectManager(self):
            return self

        def GetProjectListInCurrentFolder(self):
            return []

        def CreateProject(self, name):
            assert name == settings_project.GetName()
            return settings_project

        def GetCurrentProject(self):
            return settings_project

    for playback, expected_error in (
        ("25", "Synthetic import boundary reached"),
        ("24", "Operator required: set Playback frame rate to 25 in Project Settings"),
    ):
        settings_project = SettingsProject(playback)
        output = probe.ROOT / f"out/issue-141-observation-settings-{playback}"
        trial = {
            **config,
            "action": "prepare",
            "mediaDir": str(media_root),
            "outputDir": str(output),
            "manifestSha256": probe.sha256(media_root / "manifest.json"),
        }
        try:
            probe.run(SettingsResolve(), trial)
        except RuntimeError as error:
            assert str(error) == expected_error, str(error)
        else:
            raise AssertionError("Preparation did not stop at the tested boundary")
        assert all(
            len(request) == 1 and "timelinePlaybackFrameRate" not in request
            for request in settings_project.requests
        )
        if playback == "24":
            assert settings_project.requests == []
        assert not (output / "prepared.json").exists()
probe.ROOT = original_root

# Replay the actual failed readback through the preparation guard's shared seam.
actual_settings = json.loads(
    (Path(__file__).parent / "evidence/attempt-1/project-settings.json").read_text()
)["value"]
original_request = json.loads(
    (
        Path(__file__).parent
        / "evidence/attempt-1/preparation-20260930T165637.925707Z.jsonl"
    )
    .read_text()
    .splitlines()[2]
)["value"][0]
assert probe.settings_match(actual_settings, original_request), (
    "25.0 must equal the requested 25 fps"
)
assert not probe.settings_match(
    actual_settings, {**probe.SETTINGS, "timelinePlaybackFrameRate": "25"}
), "Inherited 24 fps playback requires the operator, not a read-only property write"
for invalid in (24, "24.999", None, True, "NaN", "Infinity", "bad"):
    assert not probe.settings_match(
        {**actual_settings, "timelineFrameRate": invalid}, original_request
    )
assert not probe.settings_match(
    {
        key: value
        for key, value in actual_settings.items()
        if key != "timelineSampleRate"
    },
    original_request,
)


class EmptyProject(Project):
    timeline_count = 0
    clips = ()

    def GetTimelineCount(self):
        return self.timeline_count

    def GetMediaPool(self):
        owner = self

        class Pool:
            def GetRootFolder(self):
                return self

            def GetClipList(self):
                return list(owner.clips)

            def GetSubFolderList(self):
                return []

        return Pool()


class EmptyResolve(Resolve):
    def GetProjectManager(self):
        class Current:
            def GetCurrentProject(self):
                return empty_project

        return Current()


empty_project = EmptyProject()
with tempfile.TemporaryDirectory() as directory:
    output = Path(directory)
    probe.write_json(output / "identity.json", identity)
    failure_path = output / "preparation-failure-test.json"
    probe.write_json(
        failure_path,
        {
            "identity": identity,
            "error": "RuntimeError: SetSettings refused operation",
        },
    )
    journal = output / "preparation-test.jsonl"
    journal.write_text(
        "".join(
            json.dumps({"method": method, "phase": phase}) + "\n"
            for method, phase in (
                ("SetSettings", "request"),
                ("SetSettings", "failure"),
            )
        )
    )
    recovery = {
        **config,
        "resumeFailure": failure_path.name,
        "resumeFailureSha256": probe.sha256(failure_path),
        "resumeJournal": journal.name,
        "resumeJournalSha256": probe.sha256(journal),
    }
    assert probe.resume_project(EmptyResolve(), recovery, output) == (
        empty_project,
        identity,
    )
    empty_project.timeline_count = 1
    refuses(lambda: probe.resume_project(EmptyResolve(), recovery, output))
    empty_project.timeline_count = 0
    empty_project.clips = ["unexpected media"]
    refuses(lambda: probe.resume_project(EmptyResolve(), recovery, output))
    empty_project.clips = []
    refuses(
        lambda: probe.resume_project(
            EmptyResolve(), {**recovery, "resumeFailureSha256": "wrong"}, output
        )
    )
    refuses(
        lambda: probe.resume_project(
            EmptyResolve(),
            {**recovery, "resumeFailure": "../preparation-failure-test.json"},
            output,
        )
    )

if len(sys.argv) > 1:
    media_root = Path(sys.argv[1])
    manifest = json.loads((media_root / "manifest.json").read_text())
    for entry in manifest["files"]:
        assert probe.sha256(media_root / entry["path"]) == entry["sha256"]
        if entry["path"].endswith(".mov"):
            video = next(
                stream
                for stream in entry["ffprobe"]["streams"]
                if stream["codec_type"] == "video"
            )
            assert video["r_frame_rate"] == "25/1"
            assert video["time_base"] == "1/12800"
            assert int(video["nb_frames"]) == 200
    with wave.open(str(media_root / "repeated.wav")) as reader:
        assert (
            reader.getframerate(),
            reader.getnchannels(),
            reader.getsampwidth(),
            reader.getnframes(),
        ) == (48000, 1, 2, 384000)
        pcm = reader.readframes(reader.getnframes())
    with wave.open(str(media_root / "echo.wav")) as reader:
        kernel = reader.readframes(reader.getnframes())
    assert (
        len(
            {
                (word["sourceSampleEndExclusive"] - word["sourceSampleStart"])
                for word in manifest["words"]
            }
        )
        == 1
    )
    for word in manifest["words"]:
        start, end = word["kernelSampleStart"], word["kernelSampleEndExclusive"]
        assert pcm[start * 2 : end * 2] == kernel
        values = [
            value[0] for value in struct.iter_unpack("<h", pcm[start * 2 : end * 2])
        ]
        nonzero = [index for index, value in enumerate(values) if value]
        assert start + nonzero[0] == word["sourceSampleStart"]
        assert start + nonzero[-1] + 1 == word["sourceSampleEndExclusive"]
    assert any(word["sourceSampleEndExclusive"] % 1920 for word in manifest["words"])
    print("Exact synthetic hashes, time bases and repeated sample intervals passed")
print("issue-141 harness checks passed (no live Resolve evidence)")
