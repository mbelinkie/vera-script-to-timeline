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
    offline_locator = "OFFLINE - " + str(media)
    expected_offline = {
        "status": "offline-locator-not-accessed",
        "approvedLocator": str(media),
        "expectedSha256": expected[str(media)],
    }
    original_hash = probe.sha256
    probe.sha256 = lambda path: (_ for _ in ()).throw(
        AssertionError("Offline display locator must not be accessed")
    )
    assert probe.source_evidence(offline_locator, expected, offline=True) == (
        expected_offline
    )
    assert probe.source_evidence(offline_locator, expected) == {
        "status": "unapproved-locator-not-accessed"
    }
    assert probe.source_evidence(
        "OFFLINE - " + str(root / "unknown"), expected, offline=True
    ) == {"status": "unapproved-locator-not-accessed"}
    probe.sha256 = original_hash
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
                    "GetSettings": {"value": timeline.GetSettings()},
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
            "GetSettings": {"value": project.GetSettings()},
            "timelines": timelines,
        }

    class NativeTimeline:
        def __init__(self, project, name, uid):
            self.project, self.name, self.uid = project, name, uid
            self.cache = project.timeline_cache

        def GetSettings(self):
            return {
                "perfCacheClipsLocation": self.cache,
                "otherSetting": self.project.other_setting,
            }

        def GetName(self):
            return self.name

        def GetUniqueId(self):
            return self.uid

        def DuplicateTimeline(self, name):
            self.project.mutations.append("DuplicateTimeline")
            duplicate = NativeTimeline(self.project, name, "duplicate-test")
            self.project.timelines.append(duplicate)
            return duplicate

    class NativeProject:
        def __init__(
            self,
            extra=False,
            project_cache=None,
            timeline_cache=None,
            other_setting="same",
            set_settings_ok=True,
            set_settings_applies=True,
        ):
            self.project_cache = (
                str(pinned_cache_path) if project_cache is None else project_cache
            )
            self.timeline_cache = (
                str(pinned_cache_path) if timeline_cache is None else timeline_cache
            )
            self.other_setting = other_setting
            self.set_settings_ok = set_settings_ok
            self.set_settings_applies = set_settings_applies
            self.mutations = []
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

        def GetSettings(self):
            return {
                "perfCacheClipsLocation": self.project_cache,
                "otherSetting": self.other_setting,
            }

        def SetSettings(self, requested):
            self.mutations.append("SetSettings")
            if not self.set_settings_ok or set(requested) != {"perfCacheClipsLocation"}:
                return False
            if not self.set_settings_applies:
                return True
            value = requested["perfCacheClipsLocation"]
            self.project_cache = value
            self.timeline_cache = value
            for timeline in self.timelines:
                timeline.cache = value
            return True

        def GetTimelineCount(self):
            return len(self.timelines)

        def GetTimelineByIndex(self, index):
            return self.timelines[index - 1]

        def GetCurrentTimeline(self):
            return self.current

        def SetCurrentTimeline(self, timeline):
            self.mutations.append("SetCurrentTimeline")
            self.current = timeline
            return True

    class NativeManager:
        def __init__(self, project, other_after_close=False):
            self.current = project
            self.other_after_close = other_after_close
            self.loads = []
            self.mutations = []

        def GetCurrentProject(self):
            return self.current

        def SaveProject(self):
            self.mutations.append("SaveProject")
            self.current.mutations.append("SaveProject")
            return True

        def CloseProject(self, project):
            self.mutations.append("CloseProject")
            assert project is self.current
            self.current = NativeProject() if self.other_after_close else None
            return True

        def LoadProject(self, name):
            self.mutations.append("LoadProject")
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
    pinned_cache_path = output / "storage" / "cache"
    pinned_cache_path.mkdir(parents=True)
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

    capture_changed = False

    def native_capture(resolve, config, identity, expected, output, stamp, environment):
        value = snapshot(resolve.GetProjectManager().current)
        if capture_changed:
            value["timelines"][0]["GetName"]["value"] = "VERA 141 changed"
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

    # The duplicate-only action treats its guarded current-project capture as
    # the operator-reopened comparison and performs no project lifecycle calls.
    duplicate_config = {**native_config, "action": "native-duplicate"}
    duplicate_only_project = NativeProject()
    duplicate_only_resolve = NativeResolve(duplicate_only_project)
    duplicate_only = probe.native_repeat(
        duplicate_only_resolve,
        duplicate_config,
        {"projectId": project_id, "projectName": project_name},
        {},
        output,
        "duplicate-only",
        environment,
    )
    assert duplicate_only["action"] == "native-duplicate"
    assert duplicate_only["preflightStage"] == "reopened-before-duplicate"
    assert "not independently verified" in duplicate_only["reopenEvidence"]
    assert duplicate_only_resolve.manager.loads == []
    duplicate_records = [
        json.loads(line)
        for line in (output / "native-duplicate-duplicate-only.jsonl")
        .read_text()
        .splitlines()
    ]
    assert [
        row["method"] for row in duplicate_records if row["phase"] == "request"
    ] == ["DuplicateTimeline", "SetCurrentTimeline", "SaveProject"]
    assert (output / "capture-duplicate-only-reopened-before-duplicate.json").is_file()

    # Exactly the two CacheClip fields may be restored before duplication.
    cache_project = NativeProject(project_cache="CacheClip", timeline_cache="CacheClip")
    cache_resolve = NativeResolve(cache_project)
    cache_result = probe.native_repeat(
        cache_resolve,
        duplicate_config,
        {"projectId": project_id, "projectName": project_name},
        {},
        output,
        "cache-restore",
        environment,
    )
    assert [
        row["method"]
        for row in map(
            json.loads,
            (output / "native-duplicate-cache-restore.jsonl").read_text().splitlines(),
        )
        if row["phase"] == "request"
    ] == [
        "SetSettings",
        "DuplicateTimeline",
        "SetCurrentTimeline",
        "SaveProject",
    ]
    assert cache_project.mutations == [
        "SetSettings",
        "DuplicateTimeline",
        "SetCurrentTimeline",
        "SaveProject",
    ]
    assert any(
        capture["capturePath"].endswith("cache-restore-cache-restoration.json")
        for capture in cache_result["captures"]
    )
    original_cache_capture = json.loads(
        Path(cache_result["captures"][0]["capturePath"]).read_text()
    )["passes"][0]
    assert (
        original_cache_capture["GetSettings"]["value"]["perfCacheClipsLocation"]
        == "CacheClip"
    )
    assert (
        original_cache_capture["timelines"][0]["GetSettings"]["value"][
            "perfCacheClipsLocation"
        ]
        == "CacheClip"
    )

    # Any extra difference, one changed cache field, or another cache value refuses.
    for suffix, project in (
        ("extra", NativeProject(other_setting="changed")),
        ("single-cache", NativeProject(project_cache="CacheClip")),
        (
            "other-cache",
            NativeProject(project_cache="OtherCache", timeline_cache="OtherCache"),
        ),
    ):
        refused_resolve = NativeResolve(project)
        refuses(
            lambda refused_resolve=refused_resolve, suffix=suffix: probe.native_repeat(
                refused_resolve,
                duplicate_config,
                {"projectId": project_id, "projectName": project_name},
                {},
                output,
                f"cache-refuse-{suffix}",
                environment,
            )
        )
        assert project.mutations == []
        assert refused_resolve.manager.mutations == []

    original_baseline_text = baseline_path.read_text()
    outside_cache = output.parent / "outside-cache"
    outside_cache.mkdir()
    symlink_cache = output / "storage" / "cache-link"
    symlink_cache.symlink_to(pinned_cache_path, target_is_directory=True)
    for suffix, path_value in (
        ("relative", "cache"),
        ("outside", str(outside_cache)),
        ("symlink", str(symlink_cache)),
    ):
        unsafe_baseline = json.loads(original_baseline_text)
        unsafe_pass = unsafe_baseline["passes"][0]
        unsafe_pass["GetSettings"]["value"]["perfCacheClipsLocation"] = path_value
        unsafe_pass["timelines"][0]["GetSettings"]["value"][
            "perfCacheClipsLocation"
        ] = path_value
        baseline_path.write_text(json.dumps(unsafe_baseline))
        unsafe_project = NativeProject(
            project_cache="CacheClip", timeline_cache="CacheClip"
        )
        refuses(
            lambda suffix=suffix, unsafe_project=unsafe_project: probe.native_repeat(
                NativeResolve(unsafe_project),
                duplicate_config,
                {"projectId": project_id, "projectName": project_name},
                {},
                output,
                f"cache-path-{suffix}",
                environment,
            )
        )
        assert unsafe_project.mutations == []
        assert not (output / f"native-duplicate-cache-path-{suffix}.jsonl").exists()
    baseline_path.write_text(original_baseline_text)

    # A refused setter still records failure and an immediate raw capture.
    failed_cache_project = NativeProject(
        project_cache="CacheClip",
        timeline_cache="CacheClip",
        set_settings_ok=False,
    )
    failed_cache_resolve = NativeResolve(failed_cache_project)
    refuses(
        lambda: probe.native_repeat(
            failed_cache_resolve,
            duplicate_config,
            {"projectId": project_id, "projectName": project_name},
            {},
            output,
            "cache-setter-refused",
            environment,
        )
    )
    assert failed_cache_project.mutations == ["SetSettings"]
    assert (output / "capture-cache-setter-refused-cache-restoration.json").is_file()
    failure_rows = [
        json.loads(line)
        for line in (output / "native-duplicate-cache-setter-refused.jsonl")
        .read_text()
        .splitlines()
    ]
    assert any(
        row["method"] == "SetSettings" and row["phase"] == "failure"
        for row in failure_rows
    )

    stale_cache_project = NativeProject(
        project_cache="CacheClip",
        timeline_cache="CacheClip",
        set_settings_applies=False,
    )
    refuses(
        lambda: probe.native_repeat(
            NativeResolve(stale_cache_project),
            duplicate_config,
            {"projectId": project_id, "projectName": project_name},
            {},
            output,
            "cache-readback-refused",
            environment,
        )
    )
    assert stale_cache_project.mutations == ["SetSettings"]
    assert (output / "capture-cache-readback-refused-cache-restoration.json").is_file()
    stale_rows = [
        json.loads(line)
        for line in (output / "native-duplicate-cache-readback-refused.jsonl")
        .read_text()
        .splitlines()
    ]
    assert [row["method"] for row in stale_rows if row["phase"] == "request"] == [
        "SetSettings"
    ]

    # A baseline-mismatched preflight is retained and refuses before mutation.
    capture_changed = True
    mismatch_project = NativeProject()
    mismatch_resolve = NativeResolve(mismatch_project)
    refuses(
        lambda: probe.native_repeat(
            mismatch_resolve,
            duplicate_config,
            {"projectId": project_id, "projectName": project_name},
            {},
            output,
            "duplicate-mismatch",
            environment,
        )
    )
    retained_mismatch = json.loads(
        (
            output / "capture-duplicate-mismatch-reopened-before-duplicate.json"
        ).read_text()
    )
    assert retained_mismatch["passes"][0]["timelines"][0]["GetName"]["value"] == (
        "VERA 141 changed"
    )
    assert mismatch_resolve.manager.mutations == []
    assert mismatch_resolve.manager.loads == []
    capture_changed = False

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
    assert wrong_resolve.manager.mutations == []

    # A changed preflight snapshot is retained before refusing all mutations.
    capture_changed = True
    changed = NativeProject()
    changed_resolve = NativeResolve(changed)
    refuses(
        lambda: probe.native_repeat(
            changed_resolve,
            native_config,
            {"projectId": project_id, "projectName": project_name},
            {},
            output,
            "changed-state",
            environment,
        )
    )
    saved = json.loads((output / "capture-changed-state-before.json").read_text())
    assert saved["passes"][0]["timelines"][0]["GetName"]["value"] == (
        "VERA 141 changed"
    )
    assert changed_resolve.manager.mutations == []
    capture_changed = False

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
    assert blocked_resolve.manager.mutations == ["SaveProject", "CloseProject"]
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

# Exercise the actual native-context branch against an injected project. Captures
# are deterministic fake-native reads and never count as Resolve evidence.
with tempfile.TemporaryDirectory() as directory:
    original_root = probe.ROOT
    original_sha256 = probe.sha256
    original_capture = probe.capture
    probe.ROOT = Path(directory)
    output = probe.ROOT / "out/issue-141-observation-context"
    output.mkdir(parents=True)
    project_id = "context-project"
    baseline_id = probe.BASELINE_ID
    r1_id = probe.R1_ID
    context_identity = {
        "projectId": project_id,
        "projectName": "VERA Issue 141 Synthetic Probe context",
        "baselineTimelineId": baseline_id,
    }
    native_context_config = {
        "projectName": context_identity["projectName"],
        "manifestSha256": "context-manifest",
        "action": "native-context",
    }

    def context_pass(track_enabled=True, changed_source=False):
        names = [
            "base.mov",
            "cutaway.mov",
            "overlay.png",
            "repeated.wav",
            "repeated.wav",
            "bed.wav",
        ]
        usages = ["2", "2", "2", "4", "4", "2"]
        tracks = []
        for index, (name, usage) in enumerate(zip(names, usages, strict=True)):
            locator = f"/synthetic/{name}"
            if changed_source and index == 0:
                locator = "/synthetic/other.mov"
            tracks.append(
                {
                    "type": "audio" if index >= 3 else "video",
                    "index": index + 1,
                    "GetTrackName": {"value": f"track-{index}"},
                    "GetIsTrackEnabled": {"value": track_enabled},
                    "GetIsTrackLocked": {"value": False},
                    "items": [
                        {
                            "GetUniqueId": {"value": f"item-{index}"},
                            "GetMediaPoolItem": {
                                "GetClipProperty": {
                                    "value": {
                                        "File Path": locator,
                                        "Usage": usage,
                                    }
                                }
                            },
                        }
                    ],
                }
            )
        return {
            "projectId": project_id,
            "projectName": context_identity["projectName"],
            "GetSettings": {"value": {"timelineFrameRate": "25"}},
            "timelines": [
                {
                    "GetName": {"value": "VERA 141 Baseline"},
                    "GetUniqueId": {"value": baseline_id},
                    "tracks": tracks,
                },
                {
                    "GetName": {"value": "VERA 141 R1 identity"},
                    "GetUniqueId": {"value": r1_id},
                    "tracks": [],
                },
            ],
        }

    baseline_original = context_pass(track_enabled=True)
    baseline_original["timelines"] = baseline_original["timelines"][:1]
    for track in baseline_original["timelines"][0]["tracks"]:
        name = Path(
            track["items"][0]["GetMediaPoolItem"]["GetClipProperty"]["value"][
                "File Path"
            ]
        ).name
        original_values = {
            "base.mov": "1",
            "cutaway.mov": "1",
            "overlay.png": "1",
            "bed.wav": "1",
            "repeated.wav": "2",
        }
        track["items"][0]["GetMediaPoolItem"]["GetClipProperty"]["value"]["Usage"] = (
            original_values[name]
        )
    pinned_value = context_pass(track_enabled=False)
    # R1 selection sees the exact pinned duplicate; baseline selection has the
    # original track state and only the five-source/six-leaf Usage changes.
    duplicate_value = context_pass(track_enabled=False)
    duplicate_value["timelines"][1] = {
        "GetName": {"value": "VERA 141 R1 identity"},
        "GetUniqueId": {"value": r1_id},
        "tracks": [],
    }
    pinned_value["timelines"][1] = duplicate_value["timelines"][1]
    pinned_file = output / probe.CONTEXT_CAPTURE
    probe.write_json(
        pinned_file,
        {
            "consistency": "equal-adjacent-reads",
            "passes": [pinned_value, pinned_value],
        },
    )
    baseline_file = output / probe.CONTEXT_BASELINE_CAPTURE
    probe.write_json(
        baseline_file,
        {
            "consistency": "equal-adjacent-reads",
            "passes": [baseline_original, baseline_original],
        },
    )
    pinned_hashes = {
        pinned_file: probe.CONTEXT_CAPTURE_SHA256,
        baseline_file: probe.CONTEXT_BASELINE_SHA256,
    }
    probe.sha256 = lambda path: pinned_hashes.get(Path(path), original_sha256(path))

    class ContextTimeline:
        def __init__(self, uid):
            self.uid = uid

        def GetUniqueId(self):
            return self.uid

    class ContextProject:
        def __init__(self, initially=None, setter_fails=False):
            self.timelines = [ContextTimeline(baseline_id), ContextTimeline(r1_id)]
            self.current = self.timelines[1 if initially is None else initially]
            self.setter_fails = setter_fails
            self.calls = []

        def GetName(self):
            return context_identity["projectName"]

        def GetUniqueId(self):
            return project_id

        def GetTimelineCount(self):
            return len(self.timelines)

        def GetTimelineByIndex(self, index):
            return self.timelines[index - 1]

        def GetCurrentTimeline(self):
            return self.current

        def SetCurrentTimeline(self, timeline):
            self.calls.append(timeline.uid)
            if self.setter_fails:
                return False
            self.current = timeline
            return True

    class ContextManager:
        def __init__(self, project):
            self.project = project

        def GetCurrentProject(self):
            return self.project

    class ContextResolve:
        def __init__(self, project):
            self.manager = ContextManager(project)

        def GetProjectManager(self):
            return self.manager

    selected_values = {
        baseline_id: context_pass(track_enabled=True),
        r1_id: pinned_value,
    }
    active = {"preflight": pinned_value}

    def context_capture(resolve, cfg, ident, expected, out, stamp, environment):
        selected = (
            resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline().uid
        )
        value = active.get(stamp.rsplit("-", 1)[-1], selected_values[selected])
        path = out / f"capture-{stamp}.json"
        probe.write_json(path, {"passes": [value, value]})
        return {"status": "equal-adjacent-reads", "capturePath": str(path)}

    probe.capture = context_capture
    probe.write_json(
        output / "prepared.json",
        {
            "identity": context_identity,
            "manifestSha256": "context-manifest",
            "environment": {"version": probe.CONTEXT_ENVIRONMENT},
        },
    )
    environment = {"version": probe.CONTEXT_ENVIRONMENT}
    identity_file_shape = {
        "projectId": project_id,
        "projectName": context_identity["projectName"],
    }
    result = probe.native_context(
        ContextResolve(ContextProject()),
        native_context_config,
        identity_file_shape,
        {},
        output,
        "context-success",
        environment,
    )
    assert result["status"] == "equal-adjacent-reads"
    assert result["comparisons"]["R1"].startswith("exactly equal")
    requests = [
        json.loads(line) for line in Path(result["journal"]).read_text().splitlines()
    ]
    assert [row["value"] for row in requests if row["phase"] == "request"] == [
        [baseline_id],
        [r1_id],
    ]

    # Wrong preflight, initial selection, selected timeline, source and track all
    # refuse without allowing the launcher to advance.
    active["preflight"] = {**pinned_value, "projectName": "unexpected"}
    mismatch = probe.native_context(
        ContextResolve(ContextProject()),
        native_context_config,
        context_identity,
        {},
        output,
        "context-wrong-preflight",
        environment,
    )
    assert mismatch["status"] == "context-mismatch-refused"
    active.pop("preflight")
    wrong_current = probe.native_context(
        ContextResolve(ContextProject(initially=0)),
        native_context_config,
        context_identity,
        {},
        output,
        "context-wrong-current",
        environment,
    )
    assert wrong_current["status"] == "context-mismatch-refused"
    active["preflight"] = json.loads(json.dumps(pinned_value))
    active["preflight"]["timelines"][1]["GetUniqueId"]["value"] = "wrong-r1-id"
    refused_timeline = probe.native_context(
        ContextResolve(ContextProject()),
        native_context_config,
        context_identity,
        {},
        output,
        "context-wrong-timeline",
        environment,
    )
    assert refused_timeline["status"] == "context-mismatch-refused"
    active.pop("preflight")

    selected_values[baseline_id] = context_pass(track_enabled=True, changed_source=True)
    source_mismatch = probe.native_context(
        ContextResolve(ContextProject()),
        native_context_config,
        context_identity,
        {},
        output,
        "context-wrong-source",
        environment,
    )
    assert source_mismatch["status"] == "context-mismatch-refused"
    selected_values[baseline_id] = context_pass(track_enabled=False)
    track_mismatch = probe.native_context(
        ContextResolve(ContextProject()),
        native_context_config,
        context_identity,
        {},
        output,
        "context-wrong-track",
        environment,
    )
    assert track_mismatch["status"] == "context-mismatch-refused"
    selected_values[baseline_id] = baseline_original

    setter_project = ContextProject(setter_fails=True)
    setter_result = probe.native_context(
        ContextResolve(setter_project),
        native_context_config,
        context_identity,
        {},
        output,
        "context-setter-failure",
        environment,
    )
    assert setter_result["status"] == "selection-failed-refused"
    assert setter_project.calls == [baseline_id]
    assert setter_result["captures"][-1]["capturePath"].endswith(
        "failure-best-effort.json"
    )
    assert Path(setter_result["captures"][-1]["capturePath"]).is_file()
    setter_rows = [
        json.loads(line)
        for line in Path(setter_result["journal"]).read_text().splitlines()
    ]
    assert any(row["phase"] == "failure" for row in setter_rows)
    assert [row["value"] for row in setter_rows if row["phase"] == "request"] == [
        [baseline_id]
    ]

    probe.capture = original_capture
    probe.sha256 = original_sha256
    probe.ROOT = original_root

# Exercise native-matrix orchestration with an injected fake pool/timeline. This
# proves guard and refusal behavior only; it cannot establish Resolve evidence.
with tempfile.TemporaryDirectory() as directory:
    original_root = probe.ROOT
    original_sha = probe.sha256
    original_capture = probe.capture
    original_media_evidence = probe.media_evidence
    original_item_evidence = probe.item_evidence
    probe.ROOT = Path(directory)
    root = probe.ROOT / "out/issue-141-observation-matrix"
    root.mkdir(parents=True)
    media_root = probe.ROOT / "out/issue-141-media-matrix"
    media_root.mkdir()
    filenames = ["base.mov", "cutaway.mov", "overlay.png", "repeated.wav", "bed.wav"]
    source_ids = {
        "base.mov": "media-base",
        "cutaway.mov": "media-cutaway",
        "overlay.png": "media-overlay",
        "repeated.wav": "media-repeated",
        "bed.wav": "media-bed",
    }
    source_files = {}
    for name in filenames:
        path = media_root / name
        path.write_bytes(f"fake-{name}".encode())
        source_files[name] = str(path)
    source_hashes = {name: probe.sha256(path) for name, path in source_files.items()}
    expected_sources = {source_files[name]: source_hashes[name] for name in filenames}
    # The real manifest also has same-name relink/wrong-byte candidates.
    for folder, content in (("relink", b"fake-base.mov"), ("wrong", b"wrong-base")):
        path = media_root / folder / "base.mov"
        path.parent.mkdir()
        path.write_bytes(content)
        expected_sources[str(path)] = probe.sha256(path)
    project_id = "matrix-project"
    project_name = "VERA Issue 141 Synthetic Probe matrix"
    identity = {
        "projectId": project_id,
        "projectName": project_name,
        "baselineTimelineId": probe.BASELINE_ID,
    }
    matrix_config = {
        "action": "native-matrix",
        "mediaDir": str(media_root),
        "projectName": project_name,
        "manifestSha256": "matrix-manifest",
    }
    baseline_timeline = {
        "GetName": {"value": "VERA 141 Baseline"},
        "GetUniqueId": {"value": probe.BASELINE_ID},
        "tracks": [],
    }
    old_timeline = {
        "GetName": {"value": "VERA 141 R1 identity"},
        "GetUniqueId": {"value": probe.R1_ID},
        "tracks": [],
    }
    for timeline in (baseline_timeline, old_timeline):
        for track_index, (name, count) in enumerate(
            (
                ("base.mov", 1),
                ("cutaway.mov", 1),
                ("overlay.png", 1),
                ("repeated.wav", 2),
                ("bed.wav", 1),
            ),
            start=1,
        ):
            rows = []
            for index in range(count):
                rows.append(
                    {
                        "GetUniqueId": {
                            "value": (
                                f"old-{timeline['GetUniqueId']['value']}-{name}-{index}"
                            )
                        },
                        "GetMediaPoolItem": {
                            "GetUniqueId": {"value": source_ids[name]},
                            "GetClipProperty": {
                                "value": {
                                    "File Path": source_files[name],
                                    "Usage": "4" if name == "repeated.wav" else "2",
                                }
                            },
                            "sourceBytes": {
                                "sha256": source_hashes[name],
                                "hashMatches": True,
                            },
                        },
                    }
                )
            timeline["tracks"].append(
                {
                    "type": "video" if track_index < 4 else "audio",
                    "index": track_index,
                    "items": rows,
                    "GetTrackName": {"value": f"track-{track_index}"},
                    "GetIsTrackEnabled": {"value": True},
                    "GetIsTrackLocked": {"value": False},
                }
            )
    pinned_pass = {
        "projectId": project_id,
        "projectName": project_name,
        "GetSettings": {"value": {"timelineFrameRate": "25"}},
        "timelines": [baseline_timeline, old_timeline],
    }
    probe.write_json(
        root / "prepared.json",
        {
            "identity": identity,
            "manifestSha256": "matrix-manifest",
        },
    )
    pinned_path = root / probe.CONTEXT_CAPTURE
    probe.write_json(
        pinned_path,
        {"consistency": "equal-adjacent-reads", "passes": [pinned_pass, pinned_pass]},
    )
    baseline_path = root / probe.CONTEXT_BASELINE_CAPTURE
    probe.write_json(
        baseline_path,
        {
            "consistency": "equal-adjacent-reads",
            "passes": [{**pinned_pass, "timelines": [baseline_timeline]}] * 2,
        },
    )

    class FakeMedia:
        def __init__(self, name):
            self.name = name

        def GetUniqueId(self):
            return source_ids[self.name]

        def GetClipProperty(self):
            return {"File Path": source_files[self.name], "Usage": "2"}

        def GetMarkers(self):
            return {}

        def GetAudioMapping(self):
            return {}

    class FakeItem:
        def __init__(self, project, name, record, duration, enabled, uid):
            self.project, self.name, self.record = project, name, record
            self.duration, self.enabled, self.uid = duration, enabled, uid
            self.marker = None
            self.linked = []

        def GetUniqueId(self):
            return self.uid

        def GetName(self):
            return self.name

        def GetType(self):
            return (
                "video"
                if self.name in {"base.mov", "cutaway.mov", "overlay.png"}
                else "audio"
            )

        def GetTrackTypeAndIndex(self):
            return ["track", 1]

        def GetMarkers(self):
            return {0: self.marker} if self.marker else {}

        def GetProperties(self):
            return {}

        def GetSpeed(self):
            return 1

        def GetClipEnabled(self):
            return self.enabled

        def GetSourceStartFrame(self):
            return 0

        def GetSourceEndFrame(self):
            return self.duration - 1

        def GetSourceStartTime(self):
            return 0

        def GetSourceEndTime(self):
            return self.duration - 1

        def GetFusionCompCount(self):
            return 0

        def GetFusionCompNameList(self):
            return []

        def GetSourceAudioChannelMapping(self):
            return {}

        def GetVoiceIsolationState(self):
            return {}

        def GetStart(self, *args):
            return self.record

        def GetEnd(self, *args):
            return self.record + (
                125 if self.name == "overlay.png" else self.duration - 1
            )

        def GetDuration(self, *args):
            return 125 if self.name == "overlay.png" else self.duration - 1

        def GetLeftOffset(self, *args):
            return 0

        def GetRightOffset(self, *args):
            return 0

        def GetLinkedItems(self):
            return self.linked

        def GetMediaPoolItem(self):
            return self.project.media[self.name]

        def SetClipEnabled(self, enabled):
            self.enabled = enabled
            return True

        def AddMarker(self, frame, color, name, note, duration, custom):
            self.marker = {
                "color": color,
                "name": name,
                "note": note,
                "duration": duration,
                "customData": custom,
            }
            return True

    class FakeTimeline:
        def __init__(self, project, name, uid, old=False):
            self.project, self.name, self.uid, self.old = project, name, uid, old
            self.tracks = {"video": [[], [], []], "audio": [[], [], []]}
            self.markers = {}

        def GetName(self):
            return self.name

        def GetUniqueId(self):
            return self.uid

        def GetTrackCount(self, kind):
            return len(self.tracks[kind])

        def GetItemListInTrack(self, kind, index):
            if self.old:
                if self.project.change_selection_during_validation:
                    self.project.current = self.project.timelines[0]
                media = next(
                    self.project.media[row[0]]
                    for row in probe.MATRIX_RECIPE
                    if row[1:3] == (kind, index)
                )

                class BoundOccurrence:
                    def GetMediaPoolItem(self):
                        return media

                return [BoundOccurrence()]
            return self.tracks[kind][index - 1]

        def AddTrack(self, kind, subtype=None):
            self.tracks[kind].append([])
            return True

        def SetStartTimecode(self, value):
            return True

        def AddMarker(self, frame, color, name, note, duration, custom):
            self.markers[str(frame)] = {
                "color": color,
                "name": name,
                "note": note,
                "duration": duration,
                "customData": custom,
            }
            return True

        def SetClipsLinked(self, items, linked):
            items[0].linked = [items[1]] if linked else []
            items[1].linked = [items[0]] if linked else []
            return True

    class FakePool:
        def __init__(self, project):
            self.project = project
            self.create_count = 0
            self.append_count = 0

        def GetRootFolder(self):
            return self

        def GetClipList(self):
            raise AssertionError(
                "Reuse verified occurrence handles, not pool enumeration"
            )

        def CreateEmptyTimeline(self, name):
            self.create_count += 1
            timeline = FakeTimeline(self.project, name, probe.MATRIX_PARTIAL_ID)
            self.project.timelines.append(timeline)
            self.project.matrix = timeline
            if self.project.auto_select_created:
                self.project.current = timeline
            return timeline

        def AppendToTimeline(self, infos):
            self.append_count += 1
            info = infos[0]
            source = next(
                name
                for name, item in self.project.media.items()
                if item.GetUniqueId() == info["mediaPoolItem"].GetUniqueId()
            )
            record = info["recordFrame"] + (
                1 if self.project.bad_placement and not self.project.items else 0
            )
            name = source
            duration = info["endFrame"] - info["startFrame"] + 1
            item = FakeItem(
                self.project,
                name,
                record,
                duration,
                False,
                f"new-{len(self.project.items)}",
            )
            self.project.items.append(item)
            kind = "video" if info["mediaType"] == 1 else "audio"
            self.project.matrix.tracks[kind][info["trackIndex"] - 1].append(item)
            if self.project.change_selection and len(self.project.items) == 1:
                self.project.current = self.project.timelines[0]
            return [item]

    class FakeProject:
        def __init__(
            self,
            bad_placement=False,
            mutate_old=False,
            wrong_source=False,
            change_selection=False,
            change_selection_during_validation=False,
            auto_select_created=False,
        ):
            self.media = {name: FakeMedia(name) for name in filenames}
            if wrong_source:
                self.media["base.mov"].GetClipProperty = lambda: {
                    "File Path": "/wrong/base.mov"
                }
            self.timelines = [
                FakeTimeline(self, "VERA 141 Baseline", probe.BASELINE_ID, old=True),
                FakeTimeline(self, "VERA 141 R1 identity", probe.R1_ID, old=True),
            ]
            self.current = self.timelines[1]
            self.matrix = None
            self.items = []
            self.bad_placement, self.mutate_old = bad_placement, mutate_old
            self.change_selection = change_selection
            self.auto_select_created = auto_select_created
            self.change_selection_during_validation = change_selection_during_validation
            self.pool = FakePool(self)
            self.usage = {
                name: ("4" if name == "repeated.wav" else "2") for name in filenames
            }

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

        def GetMediaPool(self):
            return self.pool

    class FakeManager:
        def __init__(self, project):
            self.project = project
            self.save_count = 0

        def GetCurrentProject(self):
            return self.project

        def SaveProject(self):
            self.save_count += 1
            return True

    class FakeResolve:
        def __init__(self, project):
            self.manager = FakeManager(project)

        def GetProjectManager(self):
            return self.manager

    def fake_media_evidence(item, allowed):
        name = item.name
        return {
            "GetUniqueId": {"value": item.GetUniqueId()},
            "GetClipProperty": {"value": item.GetClipProperty()},
            "sourceBytes": {
                "status": "reachable",
                "sha256": source_hashes[name],
                "hashMatches": item.GetClipProperty()["File Path"]
                == source_files[name],
            },
        }

    def fake_item_evidence(item, allowed):
        name = item.name
        duration = 125 if name == "overlay.png" else item.duration - 1
        return {
            "GetUniqueId": {"value": item.uid},
            "GetSourceStartFrame": {"value": 0},
            "GetSourceEndFrame": {
                "value": 0 if name == "overlay.png" else item.duration - 1
            },
            "GetMediaPoolItem": {
                "GetUniqueId": {"value": source_ids[name]},
                "GetClipProperty": {
                    "value": {"File Path": source_files[name], "Usage": "2"}
                },
                "sourceBytes": {"hashMatches": True, "sha256": source_hashes[name]},
            },
            "GetClipEnabled": {"value": item.enabled},
            "GetStart": {"value": item.record},
            "GetDuration": {"value": duration},
            "GetEnd": {
                "value": item.record + (125 if name == "overlay.png" else duration)
            },
            "GetMarkers": {"value": {0: item.marker} if item.marker else {}},
            "GetLinkedItems": [{"value": link.uid} for link in item.linked],
        }

    def old_snapshot(timeline, usage):
        copied = json.loads(json.dumps(timeline))
        for track in copied["tracks"]:
            for item in track["items"]:
                name = Path(
                    item["GetMediaPoolItem"]["GetClipProperty"]["value"]["File Path"]
                ).name
                item["GetMediaPoolItem"]["GetClipProperty"]["value"]["Usage"] = usage[
                    name
                ]
        return copied

    def matrix_snapshot(project):
        tracks = []
        for kind in ("video", "audio"):
            for index, items in enumerate(project.matrix.tracks[kind], start=1):
                tracks.append(
                    {
                        "type": kind,
                        "index": index,
                        **(
                            {
                                "GetTrackSubType": {
                                    "value": "stereo" if index == 1 else "mono"
                                }
                            }
                            if kind == "audio"
                            else {}
                        ),
                        "items": [
                            fake_item_evidence(item, expected_sources) for item in items
                        ],
                    }
                )
        return {
            "GetName": {"value": probe.MATRIX_NAME},
            "GetUniqueId": {"value": project.matrix.GetUniqueId()},
            "GetMarkers": {"value": project.matrix.markers},
            "tracks": tracks,
        }

    state = {"active_project": None, "preflight_wrong": False}

    def fake_capture(resolve, cfg, ident, sources, out, stamp, env):
        project = resolve.GetProjectManager().GetCurrentProject()
        if stamp.endswith("preflight"):
            value = dict(getattr(project, "continuation_preflight", pinned_pass))
            if state["preflight_wrong"]:
                value["projectName"] = "wrong"
        else:
            usage = dict(project.usage)
            if project.items:
                usage = {
                    name: str(
                        int(value) + sum(item.name == name for item in project.items)
                    )
                    for name, value in usage.items()
                }
            old = [
                old_snapshot(baseline_timeline, usage),
                old_snapshot(old_timeline, usage),
            ]
            if project.mutate_old and project.items:
                old[0]["Unexpected"] = True
            timelines = [*old]
            if project.matrix is not None:
                timelines.append(matrix_snapshot(project))
            value = {
                "projectId": project_id,
                "projectName": project_name,
                "GetSettings": {"value": {"timelineFrameRate": "25"}},
                "timelines": timelines,
            }
        path = out / f"capture-{stamp}.json"
        probe.write_json(path, {"passes": [value, value]})
        return {"status": "equal-adjacent-reads", "capturePath": str(path)}

    fake_hashes = {}
    probe.sha256 = lambda path: fake_hashes.get(Path(path), original_sha(path))
    probe.media_evidence = fake_media_evidence
    probe.item_evidence = fake_item_evidence
    probe.capture = fake_capture
    env = {"version": probe.CONTEXT_ENVIRONMENT}

    def run_matrix(label, **options):
        out = root / label
        out.mkdir()
        continuing = options.pop("continue_first", False)
        wrong_first = options.pop("wrong_first", False)
        project = FakeProject(**options)
        resolve = FakeResolve(project)
        probe.write_json(
            out / "prepared.json",
            {
                "identity": identity,
                "manifestSha256": "matrix-manifest",
                "environment": {"version": probe.CONTEXT_ENVIRONMENT},
            },
        )
        # Pinned evidence is local to each output path.
        probe.write_json(
            out / probe.CONTEXT_CAPTURE,
            {
                "consistency": "equal-adjacent-reads",
                "passes": [pinned_pass, pinned_pass],
            },
        )
        probe.write_json(
            out / probe.CONTEXT_BASELINE_CAPTURE,
            {
                "consistency": "equal-adjacent-reads",
                "passes": [{**pinned_pass, "timelines": [baseline_timeline]}] * 2,
            },
        )
        fake_hashes[out / probe.CONTEXT_CAPTURE] = probe.CONTEXT_CAPTURE_SHA256
        fake_hashes[out / probe.CONTEXT_BASELINE_CAPTURE] = (
            probe.CONTEXT_BASELINE_SHA256
        )
        cfg = dict(matrix_config)
        if continuing:
            project.matrix = FakeTimeline(
                project, probe.MATRIX_NAME, probe.MATRIX_PARTIAL_ID
            )
            project.timelines.append(project.matrix)
            project.current = project.matrix
            empty = fake_capture(
                resolve, cfg, identity, expected_sources, out, "seed-empty", env
            )
            (out / probe.MATRIX_EMPTY_CAPTURE).write_bytes(
                Path(empty["capturePath"]).read_bytes()
            )
            project.matrix.AddMarker(
                0,
                "Green",
                "141 calibration",
                "Synthetic matrix case boundary",
                1,
                json.dumps(
                    {"issue": 141, "section": "calibration", "index": 0}, sort_keys=True
                ),
            )
            first = FakeItem(
                project,
                "base.mov",
                0,
                200,
                True,
                "wrong-first" if wrong_first else probe.MATRIX_FIRST_ITEM_ID,
            )
            first.AddMarker(
                0,
                "Blue",
                "141 calibration item 0",
                "Synthetic matrix occurrence",
                1,
                json.dumps(
                    {"issue": 141, "section": "calibration", "occurrence": 0},
                    sort_keys=True,
                ),
            )
            project.items.append(first)
            project.matrix.tracks["video"][0].append(first)
            partial = fake_capture(
                resolve, cfg, identity, expected_sources, out, "seed-partial", env
            )
            (out / probe.MATRIX_PARTIAL_CAPTURE).write_bytes(
                Path(partial["capturePath"]).read_bytes()
            )
            project.continuation_preflight = json.loads(
                Path(partial["capturePath"]).read_text()
            )["passes"][0]
            for filename, digest in probe.MATRIX_CONTINUATION_HASHES.items():
                if not (out / filename).exists():
                    (out / filename).write_text(
                        "fake retained journal; not Resolve evidence"
                    )
                fake_hashes[out / filename] = digest
            cfg["stage"] = "R1-R3-matrix-marker-continuation"
            (out / "matrix-00-item-0-after.json").write_text("retain-first-item")
        return probe.native_matrix(
            resolve, cfg, identity, expected_sources, out, label, env
        ), project

    result, success_project = run_matrix("matrix-success")
    assert result["status"] == "equal-adjacent-reads"
    assert result["sections"] == 19 and result["occurrences"] == 114
    assert len(success_project.timelines) == 3

    # Finalization revalidates the retained complete matrix before its only
    # allowed mutation, SaveProject. Retained hashes are fixed in production;
    # this fake maps the exact staged filenames to those pinned values.
    matrix_resolve = FakeResolve(success_project)
    complete_bytes = Path(result["captures"][2]["capturePath"]).read_bytes()
    empty_bytes = Path(result["captures"][1]["capturePath"]).read_bytes()
    baseline_bytes = (
        root / "matrix-success" / probe.CONTEXT_BASELINE_CAPTURE
    ).read_bytes()
    matrix_config_finalize = {**matrix_config, "action": "matrix-finalize"}

    def finalize_fixture(name, *, changed_preflight=False, changed_layout=False):
        out = root / f"matrix-finalize-{name}"
        out.mkdir()
        checkpoint = json.loads(complete_bytes)["passes"][0]
        if changed_layout:
            checkpoint = json.loads(json.dumps(checkpoint))
            matrix = next(
                row
                for row in checkpoint["timelines"]
                if row["GetUniqueId"]["value"] == probe.MATRIX_PARTIAL_ID
            )
            matrix["tracks"][0]["items"][0]["GetStart"]["value"] += 1
        (out / probe.MATRIX_COMPLETE_CAPTURE).write_text(
            json.dumps({"passes": [checkpoint, checkpoint]})
        )
        (out / probe.MATRIX_EMPTY_CAPTURE).write_bytes(empty_bytes)
        (out / probe.CONTEXT_BASELINE_CAPTURE).write_bytes(baseline_bytes)
        journal_name = next(
            filename
            for filename in probe.MATRIX_FINALIZE_HASHES
            if filename.startswith("native-matrix-")
        )
        (out / journal_name).write_text("fake audited preparation journal")
        for filename, digest in probe.MATRIX_FINALIZE_HASHES.items():
            fake_hashes[out / filename] = digest
        success_project.continuation_preflight = (
            {**checkpoint, "projectName": "wrong"} if changed_preflight else checkpoint
        )
        return out, checkpoint

    save_count = matrix_resolve.manager.save_count
    create_count = success_project.pool.create_count
    append_count = success_project.pool.append_count
    success_out, _ = finalize_fixture("success")
    finalized = probe.matrix_finalize(
        matrix_resolve,
        matrix_config_finalize,
        identity,
        expected_sources,
        success_out,
        "finalize-success",
        env,
    )
    assert finalized["status"] == "equal-adjacent-reads"
    assert matrix_resolve.manager.save_count == save_count + 1
    assert success_project.pool.create_count == create_count
    assert success_project.pool.append_count == append_count

    save_count = matrix_resolve.manager.save_count
    changed_preflight_out, _ = finalize_fixture(
        "changed-preflight", changed_preflight=True
    )
    changed_preflight_result = probe.matrix_finalize(
        matrix_resolve,
        matrix_config_finalize,
        identity,
        expected_sources,
        changed_preflight_out,
        "finalize-changed-preflight",
        env,
    )
    assert changed_preflight_result["status"] == "matrix-finalize-refused"
    assert matrix_resolve.manager.save_count == save_count

    changed_layout_out, _ = finalize_fixture("changed-layout", changed_layout=True)
    changed_layout_result = probe.matrix_finalize(
        matrix_resolve,
        matrix_config_finalize,
        identity,
        expected_sources,
        changed_layout_out,
        "finalize-changed-layout",
        env,
    )
    assert changed_layout_result["status"] == "matrix-finalize-refused"
    assert matrix_resolve.manager.save_count == save_count

    success_project.continuation_preflight = json.loads(complete_bytes)["passes"][0]
    success_project.current = success_project.timelines[0]
    changed_selection_out, _ = finalize_fixture("changed-selection")
    changed_selection_result = probe.matrix_finalize(
        matrix_resolve,
        matrix_config_finalize,
        identity,
        expected_sources,
        changed_selection_out,
        "finalize-changed-selection",
        env,
    )
    assert changed_selection_result["status"] == "matrix-finalize-refused"
    assert matrix_resolve.manager.save_count == save_count
    success_project.current = success_project.matrix
    continued, continued_project = run_matrix("matrix-continue", continue_first=True)
    assert (
        continued["status"] == "equal-adjacent-reads"
        and len(continued_project.items) == 114
    )
    requests = [
        r
        for r in (
            json.loads(line)
            for line in Path(continued["journal"]).read_text().splitlines()
        )
        if r["phase"] == "request"
    ]
    assert sum(r["method"] == "AppendToTimeline" for r in requests) == 113
    assert not any(
        r["method"]
        in {"CreateEmptyTimeline", "SetCurrentTimeline", "SetStartTimecode", "AddTrack"}
        for r in requests
    )
    assert (
        root / "matrix-continue/matrix-00-item-0-after.json"
    ).read_text() == "retain-first-item"
    refused_first, first_project = run_matrix(
        "matrix-wrong-first", continue_first=True, wrong_first=True
    )
    assert (
        refused_first["status"] == "matrix-partial-refused"
        and len(first_project.items) == 1
    )
    assert all(
        json.loads(line)["phase"] != "request"
        for line in Path(refused_first["journal"]).read_text().splitlines()
    )
    assert probe._marker_at({0: {"id": "x"}}, 0) == {"id": "x"}
    assert probe._marker_at({"0": {}, "0.0": {}}, 0) == {}
    auto_selected, _ = run_matrix("matrix-auto-selected", auto_select_created=True)
    assert auto_selected["status"] == "equal-adjacent-reads"
    state["preflight_wrong"] = True
    wrong, refused_project = run_matrix("matrix-wrong-preflight")
    assert wrong["status"] == "matrix-preflight-refused"
    assert len(refused_project.timelines) == 2
    state["preflight_wrong"] = False
    bad_source, bad_source_project = run_matrix(
        "matrix-wrong-source", wrong_source=True
    )
    assert bad_source["status"] == "matrix-partial-refused"
    assert len(bad_source_project.timelines) == 2
    bad_place, bad_place_project = run_matrix(
        "matrix-bad-placement", bad_placement=True
    )
    assert bad_place["status"] == "matrix-partial-refused"
    assert len(bad_place_project.timelines) == 3
    assert bad_place["captures"][-1]["capturePath"].endswith("failure-postflight.json")
    changed_old, _ = run_matrix("matrix-old-change", mutate_old=True)
    assert changed_old["status"] == "matrix-partial-refused"
    assert changed_old["captures"][-1]["capturePath"].endswith(
        "failure-postflight.json"
    )
    changed_selection, selection_project = run_matrix(
        "matrix-selection-change", change_selection=True
    )
    assert changed_selection["status"] == "matrix-partial-refused"
    assert len(selection_project.items) == 1
    assert len(selection_project.timelines) == 3
    precreate_change, unchanged_project = run_matrix(
        "matrix-precreate-selection-change",
        change_selection_during_validation=True,
    )
    assert precreate_change["status"] == "matrix-partial-refused"
    assert not unchanged_project.items
    assert len(unchanged_project.timelines) == 2

    probe.sha256 = original_sha
    probe.capture = original_capture
    probe.media_evidence = original_media_evidence
    probe.item_evidence = original_item_evidence
    probe.ROOT = original_root

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
