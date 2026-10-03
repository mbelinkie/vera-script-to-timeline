"""Verify and publish the retained R1 25-nudge move evidence."""

import gzip
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "out/issue-141-observation-20260930-01a0f318"
EVIDENCE = ROOT / "docs/investigations/issue-141/evidence/r1-move-success"
PREP = OUT / "editorial-case-20261001T060727.115823Z"
DRIVER = OUT / "r1-move-driver-20261001T060812.416709Z"
EDIT = OUT / "r1-move-edited-20261001T061131.524595Z"
RESTORE = OUT / "editorial-case-20261001T061824.736740Z"
MATRIX = "29ae8331-b86e-4041-a548-960695cc7b24"
TARGETS = {
    "9e990622-a172-4bab-96fc-1198d84b1279": ("video", 1),
    "6f7c7dd4-9e80-444d-a4ae-b225cb5f5839": ("audio", 1),
}
EXPECTED = {
    "preparation_result": "33136cd643c402835ad2c5daa4d26f92fd8f1d056887f002212e963befa5471b",  # noqa: E501
    "final_pair": "1124201a733b74e487e44d53b9bbac99a89c2f7131af347f7169d565df84f1cc",
    "macro": "70015c4731538662ec66255861cd69a1b10577ad0caf86f85b4a7da666e6528c",
    "launcher": "f3c9a76b5c95f6fbb04d546f33a5ae23d37579e8f890851a86f3daf9a9d5f5b1",
}
SOURCES = {
    "preparation/before.json": "editorial-case-20261001T060727.115823Z/before.json",
    "preparation/after.json": "editorial-case-20261001T060727.115823Z/after.json",
    "preparation/result.json": "editorial-case-20261001T060727.115823Z/result.json",
    "preparation/journal.jsonl": "editorial-case-20261001T060727.115823Z/journal.jsonl",
    "context/result.json": "r1-move-context-20261001T060812.872493Z/result.json",
    "context/journal.jsonl": "r1-move-context-20261001T060812.872493Z/journal.jsonl",
    "deselected/result.json": "r1-move-deselected-20261001T060819.152004Z/result.json",
    "deselected/journal.jsonl": "r1-move-deselected-20261001T060819.152004Z/journal.jsonl",  # noqa: E501
    "selected/result.json": "r1-move-selected-20261001T060825.432197Z/result.json",
    "selected/journal.jsonl": "r1-move-selected-20261001T060825.432197Z/journal.jsonl",
    "driver/result.json": "r1-move-driver-20261001T060812.416709Z/result.json",
    "driver/journal.jsonl": "r1-move-driver-20261001T060812.416709Z/journal.jsonl",
    "edited/result.json": "r1-move-edited-20261001T061131.524595Z/result.json",
    "edited/journal.jsonl": "r1-move-edited-20261001T061131.524595Z/journal.jsonl",
    "edited/pair-after-selection.json": "r1-move-edited-20261001T061131.524595Z/pair-after-selection.json",  # noqa: E501
    "restore/before.json": "editorial-case-20261001T061824.736740Z/before.json",
    "restore/after.json": "editorial-case-20261001T061824.736740Z/after.json",
    "restore/result.json": "editorial-case-20261001T061824.736740Z/result.json",
    "restore/journal.jsonl": "editorial-case-20261001T061824.736740Z/journal.jsonl",
    "launch/preparation.jsonl": "hammerspoon-launch-20261001T060723.975993Z.jsonl",
    "launch/restoration.jsonl": "hammerspoon-launch-20261001T061821.562537Z.jsonl",
    "installation/preparation.json": "DOCS/installation-r1-move-prepare.json",
    "installation/restoration.json": "DOCS/installation-r1-move-restore.json",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_path(name):
    if name.startswith("DOCS/"):
        return ROOT / "docs/investigations/issue-141" / name.removeprefix("DOCS/")
    return OUT / name


def load_json(path):
    return json.loads(path.read_text())


def full_pair(pair):
    assert pair["timelineConsistency"] == "equal-adjacent-reads"
    assert pair["poolConsistency"] == "equal-adjacent-reads"
    assert len(pair["timelinePasses"]) == len(pair["poolPasses"]) == 2
    assert pair["timelinePasses"][0] == pair["timelinePasses"][1]
    assert pair["poolPasses"][0] == pair["poolPasses"][1]
    assert pair["selectedTimelineUid"] == MATRIX


def matrix(pair, pass_index=0):
    return next(
        item
        for item in pair["timelinePasses"][pass_index]["timelines"]
        if item["GetUniqueId"]["value"] == MATRIX
    )


def target_items(pair, pass_index=0):
    found = {}
    for track in matrix(pair, pass_index)["tracks"]:
        for item in track["items"]:
            uid = item.get("GetUniqueId", {}).get("value")
            if uid in TARGETS:
                assert (track["type"], track["index"]) == TARGETS[uid]
                found[uid] = item
    assert set(found) == set(TARGETS)
    return found


def moved_pair(baseline, steps):
    result = deepcopy(baseline)
    for pass_index in range(2):
        for item in target_items(result, pass_index).values():
            for key in ("GetStart", "GetStart(True)", "GetEnd", "GetEnd(True)"):
                old = target_items(baseline, pass_index)[item["GetUniqueId"]["value"]][
                    key
                ]["value"]
                item[key] = {"value": old + steps}
    return result


def restored_pair(edited):
    result = deepcopy(edited)
    for pass_index in range(2):
        for track in matrix(result, pass_index)["tracks"]:
            if track["type"] in {"video", "audio"} and track["index"] in {2, 3}:
                assert track["GetIsTrackLocked"] == {"value": True}
                track["GetIsTrackLocked"] = {"value": False}
    return result


def public_bytes(data):
    text = data.decode("utf-8").replace(str(ROOT), "<WORKTREE>")
    text = text.replace("LOCAL_PATH/f8a901af18ed9782", "<HOME>")
    text = text.replace(
        "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins",  # noqa: E501
        "<RESOLVE_PLUGIN_DIR>",
    )
    return text.encode("utf-8")


def driver_records():
    path = DRIVER / "journal.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    states = [row for row in rows if row["phase"] == "full-state-verified"]
    return rows, states


def verify_raw():
    prep_result_path = PREP / "result.json"
    final_pair_path = EDIT / "pair.json"
    assert digest(prep_result_path.read_bytes()) == EXPECTED["preparation_result"]
    assert digest(final_pair_path.read_bytes()) == EXPECTED["final_pair"]
    prep_result = load_json(prep_result_path)
    assert prep_result["status"] == "case-prepared"
    assert prep_result["target"]["startFrame"] == 1000
    assert prep_result["target"]["endFrame"] == 1199
    assert prep_result["target"]["frameRate"] == 25
    assert prep_result["target"]["uids"] == {
        "audio": "6f7c7dd4-9e80-444d-a4ae-b225cb5f5839",
        "video": "9e990622-a172-4bab-96fc-1198d84b1279",
    }

    baseline = load_json(PREP / "after.json")
    assert full_pair(baseline) is None
    prepared_before = load_json(PREP / "before.json")
    assert prepared_before == load_json(
        OUT / "editorial-case-20261001T060007.496396Z/after.json"
    )
    for relative in (
        "r1-move-context-20261001T060812.872493Z/pair.json",
        "r1-move-deselected-20261001T060819.152004Z/pair.json",
        "r1-move-selected-20261001T060825.432197Z/pair.json",
    ):
        assert baseline == load_json(OUT / relative)
    for track in matrix(baseline)["tracks"]:
        if track["type"] in {"video", "audio"}:
            assert track["GetIsTrackLocked"] == {"value": track["index"] in {2, 3}}

    rows, states = driver_records()
    assert len(states) == 28
    assert [Path(row["value"]["pair"]).parent.name for row in states[:3]] == [
        "r1-move-context-20261001T060812.872493Z",
        "r1-move-deselected-20261001T060819.152004Z",
        "r1-move-selected-20261001T060825.432197Z",
    ]
    move_states = states[3:]
    assert len(move_states) == 25
    requests = [row for row in rows if row["phase"] == "menu-request"]
    returns = [row for row in rows if row["phase"] == "menu-return"]
    assert len(requests) == len(returns) == 55
    commands = [row["value"].get("namedCommand") for row in requests]
    expected_commands = [
        "observation",
        "deselect",
        "observation",
        "select",
        "observation",
    ]
    for _ in range(25):
        expected_commands.extend(("nudge-right", "observation"))
    assert commands == expected_commands
    assert all(row["value"]["exitCode"] == 0 for row in returns)
    assert all(
        row["value"]["sourceSha256"] == EXPECTED["macro"]
        for row in requests
        if row["value"].get("namedCommand") in {"nudge-right", "deselect", "select"}
    )
    assert all(
        row["value"]["sourceSha256"] == EXPECTED["launcher"]
        for row in requests
        if row["value"].get("namedCommand") == "observation"
    )

    for index, record in enumerate(states):
        path = OUT / record["value"]["pair"]
        data = path.read_bytes()
        assert digest(data) == record["value"]["sha256"]
        pair = json.loads(data)
        full_pair(pair)
        if index == 1:
            assert record["value"]["selectedUids"] == []
        elif index >= 2:
            assert set(record["value"]["selectedUids"]) == set(TARGETS)
        expected = moved_pair(baseline, max(0, index - 2))
        assert expected == pair, f"unexpected drift in driver readback {index + 1}"

    final = load_json(final_pair_path)
    assert final == load_json(OUT / move_states[-1]["value"]["pair"])
    before_items = target_items(baseline)
    final_items = target_items(final)
    for uid, item in before_items.items():
        after = final_items[uid]
        assert item["GetSourceStartFrame"] == after["GetSourceStartFrame"]
        assert item["GetSourceEndFrame"] == after["GetSourceEndFrame"]
        assert item["GetMarkers"] == after["GetMarkers"]
        assert item["GetLinkedItems"] == after["GetLinkedItems"]
        assert item["GetUniqueId"] == after["GetUniqueId"]
        assert after["GetStart"]["value"] - item["GetStart"]["value"] == 25
        assert after["GetEnd"]["value"] - item["GetEnd"]["value"] == 25

    restore_result = load_json(RESTORE / "result.json")
    restore_before = load_json(RESTORE / "before.json")
    restore_after = load_json(RESTORE / "after.json")
    assert full_pair(restore_before) is None
    assert full_pair(restore_after) is None
    assert restore_before == final
    assert restored_pair(final) == restore_after
    assert restore_result["status"] == "restored-unsaved"
    assert restore_result["playheadAfter"] == "00:06:07:24"
    assert restore_result["saveDispatched"] is False
    assert restore_result["setters"] == ["SetTrackLock"] * 4 + ["SetCurrentTimecode"]

    driver_result = load_json(DRIVER / "result.json")
    assert driver_result["completedNudges"] == 25
    assert driver_result["failure"] is None
    assert driver_result["preparationSha256"] == EXPECTED["preparation_result"]
    assert driver_result["lastReadback"]["sha256"] == EXPECTED["final_pair"]
    edit_result = load_json(EDIT / "result.json")
    assert edit_result["failure"] is None and edit_result["readOnly"] is True
    for selection in edit_result["selectionPasses"]:
        assert {item["GetUniqueId"]["value"] for item in selection["items"]} == set(
            TARGETS
        )
    return rows, states


def publish(rows, states):
    manifest = []
    sources = dict(SOURCES)
    for number, state in enumerate(states, 1):
        path = state["value"]["pair"]
        sources[f"driver-readback-{number:02}.json"] = path

    for public_name, raw_name in sources.items():
        original = source_path(raw_name)
        data = original.read_bytes()
        redacted = public_bytes(data)
        if public_name.startswith("driver-readback-") or (
            public_name.endswith(".json") and len(data) > 100_000
        ):
            filename = f"snapshots/{public_name}.gz"
            published = gzip.compress(redacted, compresslevel=9, mtime=0)
        else:
            filename = public_name
            published = redacted
        path = EVIDENCE / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(published)
        manifest.append(
            {
                "source": raw_name,
                "filename": filename,
                "encoding": "gzip" if filename.endswith(".gz") else "utf-8",
                "rawSha256": digest(data),
                "publishedSha256": digest(published),
            }
        )
    (EVIDENCE / "hashes.json").write_text(json.dumps(manifest, indent=2) + "\n")


def verify_publication():
    manifest = load_json(EVIDENCE / "hashes.json")
    expected_sources = dict(SOURCES)
    _, states = driver_records()
    for number, state in enumerate(states, 1):
        expected_sources[f"driver-readback-{number:02}.json"] = state["value"]["pair"]
    assert len(manifest) == len(expected_sources)
    for entry in manifest:
        original = source_path(entry["source"]).read_bytes()
        published = (EVIDENCE / entry["filename"]).read_bytes()
        assert digest(original) == entry["rawSha256"]
        assert digest(published) == entry["publishedSha256"]
        decoded = (
            gzip.decompress(published) if entry["encoding"] == "gzip" else published
        )
        assert decoded == public_bytes(original)


def main():
    rows, states = verify_raw()
    if "--publish" in sys.argv:
        publish(rows, states)
    verify_publication()
    print(
        json.dumps(
            {
                "status": "independently-verified",
                "oneFrameNudges": 25,
                "fullStateReadbacks": len(states),
                "onlyTargetStartEndFieldsChanged": True,
                "sourceRangesMetadataLinksAndOtherContentUnchanged": True,
                "onlyRecordedLocksAndPlayheadRestored": True,
                "saveOrUndoDispatched": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
