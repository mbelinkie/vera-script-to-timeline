"""Verify the actual R1 split against complete retained native pairs."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "out/issue-141-observation-20260930-01a0f318"
BEFORE = OUT / "r1-razor-20261001T050302.404809Z/prepared.json"
AFTER = OUT / "r1-razor-split-20261001T051603.732674Z/pair.json"
MATRIX = "29ae8331-b86e-4041-a548-960695cc7b24"
OLD = ("33270bc5-52d0-4361-a6e3-96eb2b6d4a91", "4d08e64a-85fd-4dfe-ac80-77e4d9d28835")
NEW = ("43a86094-c5b5-40f0-b781-a419923f25fe", "9b7c5a04-8349-4a68-aa4b-9fcc81065cc8")
SOURCES = {
    "9202163a-8381-43e6-9157-3a60f35c6f79",
    "a7ad9e19-d49b-428b-9fd5-95c90d60e6f8",
}


def uid(item):
    return item["GetUniqueId"]["value"]


def usage(value):
    if isinstance(value, dict):
        if (
            value.get("GetUniqueId", {}).get("value") in SOURCES
            and "GetClipProperty" in value
        ):
            props = value["GetClipProperty"]["value"]
            props["Usage"] = str(int(props["Usage"]) + 1)
        for child in value.values():
            usage(child)
    elif isinstance(value, list):
        for child in value:
            usage(child)


def demo():
    assert hashlib.sha256(BEFORE.read_bytes()).hexdigest() == (
        "ea8525413c0b32a7fbefc290be8b9463a9c6aa8a977449af3f69da8664f21903"
    )
    assert hashlib.sha256(AFTER.read_bytes()).hexdigest() == (
        "5eabacdb141908d6bc5aa805136d5148913c3ab63936e19fc1dc9801fa448fba"
    )
    before, after = [json.loads(path.read_text()) for path in (BEFORE, AFTER)]
    prior_ids = {
        uid(item)
        for t in before["timelinePasses"][0]["timelines"]
        for track in t["tracks"]
        for item in track["items"]
    }
    assert set(OLD) <= prior_ids and set(NEW).isdisjoint(prior_ids)
    assert len(set(OLD + NEW)) == 4
    for pair in (before, after):
        assert (
            pair["timelineConsistency"]
            == pair["poolConsistency"]
            == "equal-adjacent-reads"
        )
        assert pair["timelinePasses"][0] == pair["timelinePasses"][1]
        assert pair["poolPasses"][0] == pair["poolPasses"][1]
    expected = deepcopy(before)
    for state in expected["timelinePasses"]:
        matrix = next(t for t in state["timelines"] if uid(t) == MATRIX)
        for track in matrix["tracks"]:
            if (track["type"], track["index"]) not in {("video", 1), ("audio", 1)}:
                continue
            n = 0 if track["type"] == "video" else 1
            index = next(
                i for i, item in enumerate(track["items"]) if uid(item) == OLD[n]
            )
            left = deepcopy(track["items"][index])
            right = deepcopy(left)
            for key, value in {
                "GetEnd": 1600,
                "GetEnd(True)": 1600.0,
                "GetDuration": 100,
                "GetDuration(True)": 100.0,
                "GetSourceEndFrame": 100,
                "GetSourceEndTime": 4.0,
                "GetRightOffset": 100,
                "GetRightOffset(True)": 100.0,
            }.items():
                left[key] = {"value": value}
            for key, value in {
                "GetUniqueId": NEW[n],
                "GetStart": 1600,
                "GetStart(True)": 1600.0,
                "GetDuration": 99,
                "GetDuration(True)": 99.0,
                "GetSourceStartFrame": 100,
                "GetSourceStartTime": 4.0,
                "GetLeftOffset": 100,
                "GetLeftOffset(True)": 100.0,
            }.items():
                right[key] = {"value": value}
            right["GetLinkedItems"] = [{"value": NEW[1 - n]}]
            track["items"][index : index + 1] = [left, right]
            track["items"].sort(
                key=lambda item: json.dumps(item["GetUniqueId"], sort_keys=True)
            )
    usage(expected)
    assert expected == after, "Unexpected state delta; stop and retain evidence"
    restored_path = OUT / "editorial-restore-20261001T053345.903721Z/after.json"
    assert hashlib.sha256(restored_path.read_bytes()).hexdigest() == (
        "8be8fc612618e874241f90b693a4c7a732e4eb0fbdd3de4afe17cd2756df82ff"
    )
    for state in expected["timelinePasses"]:
        matrix = next(t for t in state["timelines"] if uid(t) == MATRIX)
        for track in matrix["tracks"]:
            if track["index"] in (2, 3) and track["type"] in ("video", "audio"):
                assert track["GetIsTrackLocked"] == {"value": True}
                track["GetIsTrackLocked"] = {"value": False}
    assert expected == json.loads(restored_path.read_text())
    restoration = json.loads(restored_path.with_name("result.json").read_text())
    assert restoration["status"] == "restored-unsaved"
    assert restoration["playheadAfter"] == "00:06:07:24"
    assert restoration["setters"] == ["SetTrackLock"] * 4 + ["SetCurrentTimecode"]
    print(
        json.dumps(
            {
                "fullExpectedMatch": True,
                "leftUidsPreserved": list(OLD),
                "rightUidsNew": list(NEW),
                "recordRanges": [[1500, 1600], [1600, 1699]],
                "sourceRanges": [[0, 100], [100, 199]],
                "copiedMarkersAreNotUniqueBinding": True,
                "sourceUsageIncrement": 1,
                "contextRestoredSplitPreserved": True,
                "afterPairSha256": hashlib.sha256(AFTER.read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    demo()
