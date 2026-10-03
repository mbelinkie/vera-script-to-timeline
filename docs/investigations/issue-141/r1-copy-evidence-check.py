"""Check one actual R1 copy delta; --check exercises guards without Resolve."""

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[2] / "out/issue-141-observation-20260930-01a0f318"
MATRIX = "29ae8331-b86e-4041-a548-960695cc7b24"
ORIGINAL = {
    "video": "be502d02-0df5-40fc-9d93-3d6307dad029",
    "audio": "3a1a52ec-5a60-4972-8509-274b4a7d1f64",
}


def uid(item):
    return item["GetUniqueId"]["value"]


def matrix(pair):
    return next(t for t in pair["timelinePasses"][0]["timelines"] if uid(t) == MATRIX)


def track(timeline, kind):
    rows = [t for t in timeline["tracks"] if (t["type"], t["index"]) == (kind, 1)]
    assert len(rows) == 1
    return rows[0]


def consistency(pair):
    assert pair["selectedTimelineUid"] == MATRIX
    assert (
        pair["timelineConsistency"] == pair["poolConsistency"] == "equal-adjacent-reads"
    )
    for key in ("timelinePasses", "poolPasses"):
        assert len(pair[key]) == 2 and pair[key][0] == pair[key][1]


def expected_copy(before, new_ids):
    """Only exact copies, changed record position, new IDs/links and Usage+1."""
    expected = deepcopy(before)
    source_ids = set()
    for state in expected["timelinePasses"]:
        timeline = next(t for t in state["timelines"] if uid(t) == MATRIX)
        for kind, original_uid in ORIGINAL.items():
            items = track(timeline, kind)["items"]
            originals = [item for item in items if uid(item) == original_uid]
            assert len(originals) == 1
            item = originals[0]
            assert item["GetStart"] == {"value": 2000}
            assert item["GetEnd"] == {"value": 2199}
            assert item["GetSourceStartFrame"] == {"value": 0}
            assert item["GetSourceEndFrame"] == {"value": 199}
            assert item["GetLinkedItems"] == [
                {"value": ORIGINAL["audio" if kind == "video" else "video"]}
            ]
            source_ids.add(uid(item["GetMediaPoolItem"]))
            copied = deepcopy(item)
            copied["GetUniqueId"] = {"value": new_ids[kind]}
            copied["GetLinkedItems"] = [
                {"value": new_ids["audio" if kind == "video" else "video"]}
            ]
            for key in ("GetStart", "GetStart(True)", "GetEnd", "GetEnd(True)"):
                copied[key]["value"] += 250
            items.append(copied)
            items.sort(key=lambda row: json.dumps(row["GetUniqueId"], sort_keys=True))

    def usage(value):
        if isinstance(value, dict):
            identity = value.get("GetUniqueId", {}).get("value")
            if identity in source_ids:
                properties = value.get("GetClipProperty", {}).get("value", {})
                assert isinstance(properties.get("Usage"), str)
                properties["Usage"] = str(int(properties["Usage"]) + 1)
            for child in value.values():
                usage(child)
        elif isinstance(value, list):
            for child in value:
                usage(child)

    usage(expected)
    return expected


def verify(before, after):
    consistency(before)
    consistency(after)
    prior_ids = {
        uid(i)
        for t in before["timelinePasses"][0]["timelines"]
        for tr in t["tracks"]
        for i in tr["items"]
    }
    new_ids = {}
    for kind in ORIGINAL:
        candidates = [
            i
            for i in track(matrix(after), kind)["items"]
            if i["GetStart"] == {"value": 2250} and i["GetEnd"] == {"value": 2449}
        ]
        assert len(candidates) == 1, "Expected one copy at the reserved destination"
        new_ids[kind] = uid(candidates[0])
    assert len(set(new_ids.values())) == 2 and set(new_ids.values()).isdisjoint(
        prior_ids
    )
    assert expected_copy(before, new_ids) == after, "Unexpected full-state copy delta"
    return {"newUids": new_ids, "copiedMarkersAreNotUniqueBinding": True}


def demo():
    before = json.loads(
        (OUT / "av-output-20261001T063250.006372Z/full-pair-003.json").read_text()
    )
    after = expected_copy(
        before, {"video": "fake-video-copy", "audio": "fake-audio-copy"}
    )
    verify(before, after)
    for field, value in (
        ("GetSourceEndFrame", 198),
        ("GetUniqueId", ORIGINAL["video"]),
    ):
        wrong = deepcopy(after)
        for state in wrong["timelinePasses"]:
            timeline = next(t for t in state["timelines"] if uid(t) == MATRIX)
            copied = next(
                i
                for i in track(timeline, "video")["items"]
                if i["GetStart"] == {"value": 2250}
            )
            copied[field] = {"value": value}
        try:
            verify(before, wrong)
        except AssertionError:
            pass
        else:
            raise AssertionError("Retargeted source or old copy identity accepted")
    wrong = deepcopy(after)
    wrong["poolPasses"][0]["items"][0]["name"] = {"value": "unexpected"}
    wrong["poolPasses"][1] = deepcopy(wrong["poolPasses"][0])
    try:
        verify(before, wrong)
    except AssertionError:
        pass
    else:
        raise AssertionError("Unrelated pool change accepted")
    print("Copy evidence guard checks passed; fake copies only, no Resolve call.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        demo()
    else:
        assert len(sys.argv) == 3, "Pass two relative approved-output pair paths"
        paths = [OUT / arg for arg in sys.argv[1:]]
        assert all(
            p.resolve().is_relative_to(OUT.resolve()) and not p.is_symlink()
            for p in paths
        )
        print(json.dumps(verify(*(json.loads(p.read_text()) for p in paths))))
