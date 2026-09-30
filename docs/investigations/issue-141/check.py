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
