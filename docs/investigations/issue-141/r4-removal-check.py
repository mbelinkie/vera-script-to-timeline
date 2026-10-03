"""Focused fake checks reusing the existing complete R4 state model."""

import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


fake = load("removal_state_fake", "r4-range-repair-check.py")
removal = load("removal", "r4-removal.py")


class Media:
    def GetUniqueId(self):
        return fake.MODULE.MEDIA_UID


class Item:
    def GetUniqueId(self):
        return fake.MODULE.ITEM_UID

    def GetMediaPoolItem(self):
        return Media()


def get_items(self, track_type, index):
    assert self.uid == fake.MODULE.R4_UID and (track_type, index) == ("video", 1)
    return [Item()] if self._row()["tracks"][0]["items"] else []


def delete(self, handles, ripple):
    assert len(handles) == 1 and handles[0].GetUniqueId() == fake.MODULE.ITEM_UID
    assert ripple is False and self.uid == fake.MODULE.R4_UID
    self.store.delete_calls.append((handles[0].GetUniqueId(), ripple))
    if self.store.mode == "throw":
        raise RuntimeError("injected removal failure")
    if self.store.mode == "false":
        return False
    self._row()["tracks"][0]["items"] = []
    self.store.pool["items"][0]["evidence"]["GetClipProperty"]["value"]["Usage"] = "0"
    if self.store.mode == "drift-after":
        self.store.state["GetSettings"]["value"]["unexpected"] = True
    return self.store.mode != "partial-false"


fake.TimelineHandle.GetItemListInTrack = get_items
fake.TimelineHandle.DeleteClips = delete
fake.Project.GetCurrentRenderFormatAndCodec = lambda self: {
    "format": "mov",
    "codec": "H264",
}
fake.Project.GetRenderJobList = lambda self: []
fake.Resolve.GetCurrentPage = lambda self: "deliver"


def demo():
    for mode in (
        "true",
        "false",
        "throw",
        "partial-false",
        "drift-after",
        "drift-before",
        "bad-source",
        "wrong-selection",
        "bad-pin",
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            resolve, config, _ = fake._setup(root)
            config["action"] = "r4-occurrence-remove"
            store = resolve.store
            store.mode, store.selected_uid = mode, fake.MODULE.R4_UID
            store.delete_calls = []
            timeline = next(
                t
                for t in store.state["timelines"]
                if t["GetUniqueId"]["value"] == fake.MODULE.R4_UID
            )
            timeline.update(
                GetStartFrame={"value": 0},
                GetEndFrame={"value": 0},
                GetStartTimecode={"value": "00:00:00:00"},
            )
            item = timeline["tracks"][0]["items"][0]
            item.update(GetStart={"value": -90000}, GetEnd={"value": -89801})
            store.pool["items"][0]["evidence"]["GetClipProperty"]["value"]["Usage"] = (
                "1"
            )
            output = Path(config["outputDir"])
            cap = output / removal.CAPTURE_NAME
            pool = output / removal.POOL_NAME
            fake._write(
                cap,
                {
                    "consistency": "equal-adjacent-reads",
                    "passes": [store.state, store.state],
                },
            )
            removal.CAPTURE_SHA = fake.digest(cap)
            fake._write(
                pool,
                {
                    "status": "equal-read-only-pool-inventory",
                    "passes": [store.pool, store.pool],
                    "capture": {"sha256": removal.CAPTURE_SHA},
                },
            )
            removal.POOL_SHA = fake.digest(pool)
            if mode == "drift-before":
                store.state["GetSettings"]["value"]["unexpected"] = True
            if mode == "bad-source":
                store.source.write_bytes(b"changed source")
            if mode == "wrong-selection":
                store.selected_uid = fake.MODULE.MATRIX_UID
            if mode == "bad-pin":
                cap.write_text("changed pin")
            try:
                result = removal.run(resolve, config, probe=fake.Probe)
            except RuntimeError:
                assert mode in {
                    "drift-before",
                    "bad-source",
                    "wrong-selection",
                    "bad-pin",
                }, mode
                assert store.delete_calls == []
                continue
            assert len(store.delete_calls) == 1
            assert store.setter_calls == [] and store.selection_calls == []
            assert result["sourcePoolPresentAndOnline"] is True
            assert result["occurrenceAbsent"] == (mode not in {"false", "throw"})
            assert result["status"] == (
                "removed-source-retained"
                if mode == "true"
                else "removal-outcome-review-required"
            ), (mode, result)
            assert fake.digest(store.source) == store.expected[str(store.source)]
            rows = list(
                map(json.loads, Path(result["journal"]).read_text().splitlines())
            )
            assert (
                sum(
                    r["method"] == "Timeline.DeleteClips" and r["phase"] == "request"
                    for r in rows
                )
                == 1
            )
    print("R4 non-ripple occurrence-removal fake checks passed")


if __name__ == "__main__":
    demo()
