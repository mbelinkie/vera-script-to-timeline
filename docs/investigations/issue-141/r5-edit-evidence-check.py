"""Review three full R5 note/move pairs; no Resolve calls or file mutations."""

import gzip
import hashlib
import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "move_evidence", HERE / "r1-move-evidence-check.py"
)
move = importlib.util.module_from_spec(spec)
spec.loader.exec_module(move)
TARGETS = {
    "video": "3f2de461-d510-46f8-939f-0c794d48e38b",
    "audio": "22561398-bce0-4c22-b55f-a73d3ad5e4cf",
}
NOTE = "Issue 141 R5 marker-note observation"
ORIGINAL_MARKER = {
    "color": "Green",
    "customData": '{"index": 0, "issue": 141, "section": "calibration"}',
    "duration": 1,
    "name": "141 calibration",
    "note": "Synthetic matrix case boundary",
}


def item(pair, kind, pass_index):
    track = [
        row
        for row in move.matrix(pair, pass_index)["tracks"]
        if (row["type"], row["index"]) == (kind, 1)
    ]
    assert len(track) == 1
    rows = [
        row
        for row in track[0]["items"]
        if row.get("GetUniqueId", {}).get("value") == TARGETS[kind]
    ]
    assert len(rows) == 1
    return rows[0]


def fingerprint(pair):
    return hashlib.sha256(
        json.dumps(pair["timelinePasses"][0], sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def review(before, noted, moved):
    for pair in (before, noted, moved):
        move.full_pair(pair)
    expected_note = deepcopy(before)
    for pass_index in range(2):
        state = before["timelinePasses"][pass_index]
        assert state["projectId"] == "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
        assert state["projectName"] == (
            "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
        )
        marker = move.matrix(expected_note, pass_index)["GetMarkers"]["value"]["0"]
        assert marker == ORIGINAL_MARKER
        marker["note"] = NOTE
        for kind, uid in TARGETS.items():
            target = item(before, kind, pass_index)
            assert target["GetStart"] == {"value": 0}
            assert target["GetEnd"] == {"value": 199}
            assert target["GetSourceStartFrame"] == {"value": 0}
            assert target["GetSourceEndFrame"] == {"value": 199}
            assert target["GetClipEnabled"] == {"value": True}
            assert target["GetLinkedItems"] == [
                {"value": next(value for value in TARGETS.values() if value != uid)}
            ]
    assert noted == expected_note, "Delta exceeds the exact marker-note edit"
    expected_move = deepcopy(noted)
    for pass_index in range(2):
        for kind in TARGETS:
            target = item(expected_move, kind, pass_index)
            for field in ("GetStart", "GetStart(True)", "GetEnd", "GetEnd(True)"):
                target[field]["value"] += 1
    assert moved == expected_move, "Delta exceeds the linked one-frame record move"
    fingerprints = [fingerprint(pair) for pair in (before, noted, moved)]
    assert len(set(fingerprints)) == 3
    return {
        "fullNoteOnlyDelta": True,
        "fullLinkedMoveOnlyDelta": True,
        "contentFingerprints": fingerprints,
        "limits": [
            "Raw pairs alone do not establish the operator/menu mechanism or build.",
            "Retain version-stamped native results and exact selection/menu journals.",
            "No atomic snapshot token or ABA exclusion is established.",
        ],
    }


def load(path, expected_hash):
    assert not path.is_symlink() and path.is_file()
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == expected_hash, "Evidence hash changed"
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def demo():
    before = load(
        HERE
        / "evidence/r1-copy-paste-stopped"
        / "r1-copy-pasted-20261001T072554.638674Z/pair.json.gz",
        "4c03d06a8746255ecded62f362e3e95abba76c9cbd5dccc1374fafad74299eee",
    )
    noted = deepcopy(before)
    for pass_index in range(2):
        move.matrix(noted, pass_index)["GetMarkers"]["value"]["0"]["note"] = NOTE
    moved = deepcopy(noted)
    for pass_index in range(2):
        for kind in TARGETS:
            for field in ("GetStart", "GetStart(True)", "GetEnd", "GetEnd(True)"):
                item(moved, kind, pass_index)[field]["value"] += 1
    assert review(before, noted, moved)["fullLinkedMoveOnlyDelta"]
    for mode in ("source-drift", "marker-color", "one-track-only", "interpass"):
        bad_note, bad_move = deepcopy(noted), deepcopy(moved)
        if mode == "marker-color":
            for pass_index in range(2):
                move.matrix(bad_note, pass_index)["GetMarkers"]["value"]["0"][
                    "color"
                ] = "Red"
        elif mode == "interpass":
            item(bad_move, "audio", 1)["GetEnd"]["value"] += 1
        else:
            for pass_index in range(2):
                target = item(bad_move, "audio", pass_index)
                if mode == "source-drift":
                    target["GetSourceStartFrame"]["value"] = 1
                else:
                    target["GetStart"]["value"] = 0
        try:
            review(before, bad_note, bad_move)
        except AssertionError:
            pass
        else:
            raise AssertionError(f"Accepted {mode}")
    print("R5 note/move guard checks pass; no live R5 edit evidence claimed.")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        demo()
    else:
        assert len(sys.argv) == 7, "Supply before/hash, noted/hash, moved/hash"
        pairs = [
            load(Path(sys.argv[index]), sys.argv[index + 1]) for index in (1, 3, 5)
        ]
        print(json.dumps(review(*pairs), indent=2))
