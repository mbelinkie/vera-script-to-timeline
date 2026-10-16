"""Fake checks for one-call re-preparation from a pinned removal checkpoint."""

import hashlib
import importlib.util
import json
import tempfile
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


fake = load("reprepare_state_fake", "r4-range-repair-check.py")
module = load("reprepare", "r4-reprepare.py")
reader = fake.MODULE


def digest(path):
    return hashlib.file_digest(Path(path).open("rb"), "sha256").hexdigest()


class MediaHandle:
    def __init__(self, uid):
        self.uid = uid

    def GetUniqueId(self):
        return self.uid


class Folder:
    def __init__(self, store):
        self.store = store

    def GetUniqueId(self):
        return "root"

    def GetClipList(self):
        return [MediaHandle(reader.MEDIA_UID)]

    def GetSubFolderList(self):
        return []


class Pool:
    def __init__(self, store):
        self.store = store

    def GetRootFolder(self):
        return Folder(self.store)

    def AppendToTimeline(self, clips):
        self.store.append_calls.append(clips)
        mode = self.store.mode
        if mode == "throw":
            raise RuntimeError("injected append failure")
        if mode == "false":
            return False
        row = next(
            t
            for t in self.store.state["timelines"]
            if t["GetUniqueId"]["value"] == reader.R4_UID
        )
        source = next(
            x for x in self.store.pool["items"] if x["uid"] == reader.MEDIA_UID
        )["evidence"]
        item = {
            "GetUniqueId": {"value": "new-item-uid"},
            "GetMediaPoolItem": deepcopy(source),
            "GetStart": {"value": 0},
            "GetEnd": {"value": 199},
            "GetDuration": {"value": 199},
            "GetSourceStartFrame": {"value": 0},
            "GetSourceEndFrame": {"value": 199},
            "GetTrackTypeAndIndex": {"value": ["video", 1]},
        }
        row["tracks"][0]["items"].append(item)
        row["GetEndFrame"] = {"value": 201 if mode == "drift" else 199}
        if mode == "drift":
            row["GetSettings"]["value"]["unexpected"] = True
        self.store.pool["items"][0]["evidence"]["GetClipProperty"]["value"]["Usage"] = (
            "1"
        )
        return [] if mode == "partial" else [MediaHandle("new-item-uid")]


fake.Project.GetMediaPool = lambda self: Pool(self.store)
fake.Project.GetCurrentRenderFormatAndCodec = lambda self: {
    "format": "mov",
    "codec": "H264",
}
fake.Project.GetRenderJobList = lambda self: []
fake.Resolve.GetCurrentPage = lambda self: (
    "edit" if self.store.append_calls else "deliver"
)
fake.Probe.source_evidence = staticmethod(
    lambda path, expected: {
        "sha256": digest(path),
        "hashMatches": digest(path) == expected[path],
    }
)
fake.Probe.ROOT = None


def setup(root, mode="success"):
    resolve, config, _ = fake._setup(root)
    store = resolve.store
    store.mode = mode
    store.selected_uid = reader.R4_UID
    store.append_calls = []
    config["action"] = "r4-reprepare"
    config["externalScriptingSetting"] = "None"
    media = Path(config["mediaDir"])
    (media / "relink").mkdir()
    source = media / "relink/base.mov"
    source.write_bytes(b"synthetic base media")
    config["manifestSha256"] = fake.digest(media / "manifest.json")
    # The configured manifest is replaced to pin the exact isolated relink bytes.
    manifest = {
        "kind": "generated-synthetic-inputs-not-Resolve-evidence",
        "files": [
            {
                "path": "relink/base.mov",
                "sha256": digest(source),
                "sizeBytes": source.stat().st_size,
            }
        ],
    }
    (media / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    config["manifestSha256"] = digest(media / "manifest.json")
    store.expected = {str(source): digest(source)}
    item = store.state["timelines"][1]["tracks"][0]["items"].pop()
    store.state["timelines"][1].update(
        GetStartFrame={"value": 0},
        GetEndFrame={"value": 0},
        GetStartTimecode={"value": "00:00:00:00"},
    )
    store.pool["items"][0]["evidence"]["GetClipProperty"]["value"]["File Path"] = str(
        source
    )
    store.pool["items"][0]["evidence"]["GetClipProperty"]["value"]["Usage"] = "0"
    store.pool["items"][0]["evidence"]["sourceBytes"] = {
        "status": "reachable",
        "sha256": digest(source),
        "hashMatches": True,
    }
    store.state["timelines"][1]["tracks"][0]["items"] = []
    checkpoint = Path(config["outputDir"]) / module.REMOVAL_DIR
    checkpoint.mkdir()
    pre_state = deepcopy(store.state)
    pre_state["timelines"][1]["tracks"][0]["items"] = [item]
    pre_state["timelines"][1].update(
        GetStartFrame={"value": 0}, GetEndFrame={"value": 0}
    )
    pre_pool = deepcopy(store.pool)
    pre_pool["items"][0]["evidence"]["GetClipProperty"]["value"]["Usage"] = "1"

    def pin(name, value):
        path = checkpoint / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return digest(path)

    module.REMOVAL_RESULT_SHA = pin(
        module.REMOVAL_RESULT,
        {
            "status": "removed-source-retained",
            "deleteReturn": True,
            "deleteError": None,
            "occurrenceAbsent": True,
            "removedOccurrenceUid": reader.ITEM_UID,
            "sourcePoolUid": reader.MEDIA_UID,
            "sourcePoolPresentAndOnline": True,
            "after": str(checkpoint / module.REMOVAL_POST),
        },
    )

    def pair(state, pool):
        return {
            "selectedTimelineUid": reader.R4_UID,
            "timelineConsistency": "equal-adjacent-reads",
            "poolConsistency": "equal-adjacent-reads",
            "timelinePasses": [state, deepcopy(state)],
            "poolPasses": [pool, deepcopy(pool)],
        }

    module.REMOVAL_PRE_SHA = pin(module.REMOVAL_PRE, pair(pre_state, pre_pool))
    module.REMOVAL_POST_SHA = pin(module.REMOVAL_POST, pair(store.state, store.pool))
    journal = checkpoint / module.REMOVAL_JOURNAL
    journal.write_text(
        json.dumps({"method": "Timeline.DeleteClips", "phase": "request"}) + "\n",
        encoding="utf-8",
    )
    module.REMOVAL_JOURNAL_SHA = digest(journal)
    if mode == "bad-pin":
        (checkpoint / module.REMOVAL_POST).write_text("tampered", encoding="utf-8")
    if mode == "bad-source":
        source.write_bytes(b"changed source bytes")
    # Let the test exercise the pinned-reader binding against this checkout.
    module.RANGE_REPAIR_SHA = digest(HERE / "r4-range-repair.py")
    fake.Probe.ROOT = root
    return resolve, config, store


def demo():
    for mode in (
        "success",
        "false",
        "throw",
        "partial",
        "drift",
        "bad-source",
        "bad-pin",
    ):
        with tempfile.TemporaryDirectory() as temporary:
            resolve, config, store = setup(Path(temporary), mode)
            if mode in {"bad-source", "bad-pin"}:
                try:
                    module.run(resolve, config, probe=fake.Probe)
                except RuntimeError:
                    assert store.append_calls == []
                    continue
                raise AssertionError(f"{mode} must refuse before append")
            result = module.run(resolve, config, probe=fake.Probe)
            assert len(store.append_calls) == 1
            request = store.append_calls[0]
            assert (
                len(request) == 1
                and request[0]["mediaPoolItem"].GetUniqueId() == reader.MEDIA_UID
            )
            assert {
                k: request[0][k]
                for k in (
                    "startFrame",
                    "endFrame",
                    "mediaType",
                    "trackIndex",
                    "recordFrame",
                )
            } == {
                "startFrame": 0,
                "endFrame": 199,
                "mediaType": 1,
                "trackIndex": 1,
                "recordFrame": 0,
            }
            assert store.selection_calls == [] and store.setter_calls == []
            if mode == "success":
                assert result["sourceAndRangeVerified"] is True
                assert result["newOccurrenceUid"] != reader.ITEM_UID
            else:
                assert result["sourceAndRangeVerified"] is (mode == "drift")
                if mode == "drift":
                    assert result["nativeDeltas"]["timelineChangedPaths"]
    print("R4 re-preparation fake checks passed")


if __name__ == "__main__":
    demo()
