"""Independently verify the retained R1 trim and unsaved context restoration."""

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "out/issue-141-observation-20260930-01a0f318"
EVIDENCE = ROOT / "docs/investigations/issue-141/evidence/r1-trim-success"
PREP = OUT / "editorial-case-20261001T055716.777793Z"
EDIT = OUT / "r1-trim-edited-20261001T055915.830603Z"
RESTORE = OUT / "editorial-case-20261001T060007.496396Z"
MATRIX = "29ae8331-b86e-4041-a548-960695cc7b24"
TARGETS = {
    "36b5882f-d928-4424-b4a6-ee3f7dcc8e03": ("video", 1),
    "17267938-81b0-4777-9db5-0a27d359dbfc": ("audio", 1),
}
EXPECTED_RAW = {
    "fresh_context": "8be8fc612618e874241f90b693a4c7a732e4eb0fbdd3de4afe17cd2756df82ff",
    "prep_after": "5eabacdb141908d6bc5aa805136d5148913c3ab63936e19fc1dc9801fa448fba",
    "prep_result": "21f2766e8a04eab2a51f77e2f5867d9b5e96c5af057f039e62c8526e9cd218b7",
    "edited_pair": "9458a22e3e6d68e5685c71aac52da906b7f7eecc84fbdf5a7e4eb2043cb9959b",
    "restore_after": "a668958e6441b0176e8926c932784bbebe9a747698fa0bf83a1509ba61434089",
    "restore_result": "01036b551cbd1e4b45b8cf3d58d7392d45b6e02dab83fc68c4515fd50755c29e",  # noqa: E501
}
MACRO_SHA256 = "70015c4731538662ec66255861cd69a1b10577ad0caf86f85b4a7da666e6528c"
SELECTION_RESULT_SHA256 = (
    "bb983aa7ac93348f6209dec31d1c53ead64417aeb4e8866178bba0f2f1b6ebac"
)
TRIM_FIELDS = {
    "GetEnd": 674,
    "GetEnd(True)": 674.0,
    "GetDuration": 174,
    "GetDuration(True)": 174.0,
    "GetSourceEndFrame": 174,
    "GetSourceEndTime": 6.96,
    "GetRightOffset": 26,
    "GetRightOffset(True)": 26.0,
}
PUBLISHED_INPUTS = {
    "prep/before.json": "editorial-case-20261001T055716.777793Z/before.json",
    "prep/after.json": "editorial-case-20261001T055716.777793Z/after.json",
    "prep/result.json": "editorial-case-20261001T055716.777793Z/result.json",
    "prep/journal.jsonl": "editorial-case-20261001T055716.777793Z/journal.jsonl",
    "fresh-context/result.json": "editorial-context-20261001T055304.180088Z/result.json",  # noqa: E501
    "fresh-context/journal.jsonl": "editorial-context-20261001T055304.180088Z/journal.jsonl",  # noqa: E501
    "fresh-context/pair.json": "editorial-context-20261001T055304.180088Z/pair.json",
    "deselected-055803/result.json": "r1-trim-deselected-20261001T055803.276684Z/result.json",  # noqa: E501
    "deselected-055803/journal.jsonl": "r1-trim-deselected-20261001T055803.276684Z/journal.jsonl",  # noqa: E501
    "deselected-055803/pair.json": "r1-trim-deselected-20261001T055803.276684Z/pair.json",  # noqa: E501
    "deselected-055833/result.json": "r1-trim-deselected-20261001T055833.870148Z/result.json",  # noqa: E501
    "deselected-055833/journal.jsonl": "r1-trim-deselected-20261001T055833.870148Z/journal.jsonl",  # noqa: E501
    "deselected-055833/pair.json": "r1-trim-deselected-20261001T055833.870148Z/pair.json",  # noqa: E501
    "selected/result.json": "r1-trim-selected-20261001T055856.627259Z/result.json",
    "selected/journal.jsonl": "r1-trim-selected-20261001T055856.627259Z/journal.jsonl",
    "selected/pair.json": "r1-trim-selected-20261001T055856.627259Z/pair.json",
    "edited/result.json": "r1-trim-edited-20261001T055915.830603Z/result.json",
    "edited/journal.jsonl": "r1-trim-edited-20261001T055915.830603Z/journal.jsonl",
    "edited/pair.json": "r1-trim-edited-20261001T055915.830603Z/pair.json",
    "edited/pair-after-selection.json": "r1-trim-edited-20261001T055915.830603Z/pair-after-selection.json",  # noqa: E501
    "restore/before.json": "editorial-case-20261001T060007.496396Z/before.json",
    "restore/after.json": "editorial-case-20261001T060007.496396Z/after.json",
    "restore/result.json": "editorial-case-20261001T060007.496396Z/result.json",
    "restore/journal.jsonl": "editorial-case-20261001T060007.496396Z/journal.jsonl",
    "launch/preparation.jsonl": "hammerspoon-launch-20261001T055713.551592Z.jsonl",
    "launch/deselect-1.jsonl": "hammerspoon-launch-20261001T055802.791021Z.jsonl",
    "launch/deselect-2.jsonl": "hammerspoon-launch-20261001T055833.407319Z.jsonl",
    "launch/select.jsonl": "hammerspoon-launch-20261001T055856.160995Z.jsonl",
    "launch/trim-end.jsonl": "hammerspoon-launch-20261001T055915.345689Z.jsonl",
    "launch/restore.jsonl": "hammerspoon-launch-20261001T060004.308890Z.jsonl",
    "macro/deselect.jsonl": "hammerspoon-editorial-deselect-20261001T055825.614018Z.jsonl",  # noqa: E501
    "macro/select.jsonl": "hammerspoon-editorial-select-20261001T055855.513542Z.jsonl",
    "macro/trim-end.jsonl": "hammerspoon-editorial-trim-end-20261001T055914.668802Z.jsonl",  # noqa: E501
    "readback/focus-only.json": "r1-trim-focus-only-context.json",
    "readback/fresh-context-installation.json": "DOCS/installation-r1-trim-fresh-context.json",  # noqa: E501
    "readback/preparation-installation.json": "DOCS/installation-r1-trim-prepare.json",
    "readback/restoration-installation.json": "DOCS/installation-r1-trim-restore.json",
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def raw(relative):
    return OUT / relative


def source_path(relative):
    if relative.startswith("DOCS/"):
        return ROOT / "docs/investigations/issue-141" / relative.removeprefix("DOCS/")
    return raw(relative)


def read_json(path):
    return json.loads(path.read_text())


def assert_stable_pair(pair):
    assert pair["timelineConsistency"] == "equal-adjacent-reads"
    assert pair["poolConsistency"] == "equal-adjacent-reads"
    assert len(pair["timelinePasses"]) == len(pair["poolPasses"]) == 2
    assert pair["timelinePasses"][0] == pair["timelinePasses"][1]
    assert pair["poolPasses"][0] == pair["poolPasses"][1]


def matrix(pair, pass_index=0):
    timelines = pair["timelinePasses"][pass_index]["timelines"]
    return next(
        timeline for timeline in timelines if timeline["GetUniqueId"]["value"] == MATRIX
    )


def target_items(pair, pass_index=0):
    found = {}
    timeline = matrix(pair, pass_index)
    for track in timeline["tracks"]:
        for item in track["items"]:
            uid = item.get("GetUniqueId", {}).get("value")
            if uid in TARGETS:
                assert (track["type"], track["index"]) == TARGETS[uid]
                found[uid] = item
    assert set(found) == set(TARGETS)
    return found


def set_trim_fields(pair):
    for pass_index in range(2):
        for item in target_items(pair, pass_index).values():
            for key, value in TRIM_FIELDS.items():
                item[key] = {"value": value}


def set_restored_locks(pair):
    for pass_index in range(2):
        for track in matrix(pair, pass_index)["tracks"]:
            if track["type"] in {"video", "audio"} and track["index"] in {2, 3}:
                assert track["GetIsTrackLocked"] == {"value": True}
                track["GetIsTrackLocked"] = {"value": False}


def public_bytes(data):
    text = data.decode("utf-8")
    text = text.replace(str(ROOT), "<WORKTREE>")
    text = text.replace("LOCAL_PATH/f8a901af18ed9782", "<HOME>")
    text = text.replace(
        "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins",  # noqa: E501
        "<RESOLVE_PLUGIN_DIR>",
    )
    return text.encode("utf-8")


def build_manifest():
    manifest = []
    for logical_name, source in PUBLISHED_INPUTS.items():
        original_path = source_path(source)
        data = original_path.read_bytes()
        published_path = EVIDENCE / logical_name
        published_path.parent.mkdir(parents=True, exist_ok=True)
        # Reuse a published full pair when the raw capture hash is identical.
        digest = sha256(data)
        reusable = next(
            (entry for entry in manifest if entry["rawSha256"] == digest), None
        )
        if reusable and original_path.name in {
            "pair.json",
            "after.json",
            "before.json",
        }:
            published_path = EVIDENCE / reusable["filename"]
        else:
            published_path.write_bytes(public_bytes(data))
        manifest.append(
            {
                "source": source,
                "filename": str(published_path.relative_to(EVIDENCE)),
                "rawSha256": digest,
                "publishedSha256": sha256(published_path.read_bytes()),
            }
        )
    (EVIDENCE / "hashes.json").write_text(json.dumps(manifest, indent=2) + "\n")


def verify_publication():
    manifest = read_json(EVIDENCE / "hashes.json")
    assert len(manifest) == len(PUBLISHED_INPUTS)
    for entry in manifest:
        origin_path = source_path(entry["source"])
        published_path = EVIDENCE / entry["filename"]
        original = origin_path.read_bytes()
        published = published_path.read_bytes()
        assert sha256(original) == entry["rawSha256"], origin_path
        assert sha256(published) == entry["publishedSha256"], published_path
        assert published == public_bytes(original), published_path


def verify_native_evidence():
    prep_after_path = PREP / "after.json"
    prep_result_path = PREP / "result.json"
    fresh_context_path = raw("editorial-context-20261001T055304.180088Z/pair.json")
    edited_path = EDIT / "pair.json"
    restore_after_path = RESTORE / "after.json"
    restore_result_path = RESTORE / "result.json"
    for path, expected in (
        (fresh_context_path, EXPECTED_RAW["fresh_context"]),
        (prep_after_path, EXPECTED_RAW["prep_after"]),
        (prep_result_path, EXPECTED_RAW["prep_result"]),
        (edited_path, EXPECTED_RAW["edited_pair"]),
        (restore_after_path, EXPECTED_RAW["restore_after"]),
        (restore_result_path, EXPECTED_RAW["restore_result"]),
    ):
        assert sha256(path.read_bytes()) == expected, path

    prepared = read_json(prep_after_path)
    fresh_context = read_json(
        raw("editorial-context-20261001T055304.180088Z/pair.json")
    )
    prep_before = read_json(PREP / "before.json")
    selected = read_json(raw("r1-trim-selected-20261001T055856.627259Z/pair.json"))
    edited = read_json(edited_path)
    restored_before = read_json(RESTORE / "before.json")
    restored = read_json(restore_after_path)
    for pair in (
        fresh_context,
        prep_before,
        prepared,
        selected,
        edited,
        restored_before,
        restored,
    ):
        assert_stable_pair(pair)
    assert fresh_context == prep_before, (
        "preparation did not start from the newly verified full context"
    )
    assert prepared == selected, "selection/context readback drifted before trim"
    assert restored_before == edited, (
        "restoration did not start from the exact edited state"
    )

    expected_edited = deepcopy(prepared)
    set_trim_fields(expected_edited)
    assert expected_edited == edited, (
        "trim pair contains an unapproved state difference"
    )
    expected_restored = deepcopy(edited)
    set_restored_locks(expected_restored)
    assert expected_restored == restored, (
        "restoration pair contains an unapproved difference"
    )

    before_items = target_items(prepared)
    after_items = target_items(edited)
    for uid, before in before_items.items():
        after = after_items[uid]
        assert before["GetStart"] == after["GetStart"]
        assert before["GetStart(True)"] == after["GetStart(True)"]
        assert before["GetSourceStartFrame"] == after["GetSourceStartFrame"]
        assert before["GetSourceStartTime"] == after["GetSourceStartTime"]
        assert before["GetMarkers"] == after["GetMarkers"]
        assert before["GetLinkedItems"] == after["GetLinkedItems"]
        assert before["GetUniqueId"] == after["GetUniqueId"]
        assert before["GetEnd"]["value"] - after["GetEnd"]["value"] == 25
    assert before_items["36b5882f-d928-4424-b4a6-ee3f7dcc8e03"]["GetLinkedItems"] == [
        {"value": "17267938-81b0-4777-9db5-0a27d359dbfc"}
    ]
    assert before_items["17267938-81b0-4777-9db5-0a27d359dbfc"]["GetLinkedItems"] == [
        {"value": "36b5882f-d928-4424-b4a6-ee3f7dcc8e03"}
    ]

    prep_result = read_json(prep_result_path)
    edit_result = read_json(EDIT / "result.json")
    restoration_result = read_json(restore_result_path)
    assert prep_result["status"] == "case-prepared"
    assert prep_result["target"]["trimPlayheadFrame"] == 674
    assert edit_result["status"] == "editorial-readback-retained"
    assert edit_result["failure"] is None and edit_result["readOnly"] is True
    assert edit_result["selectionShapes"] == [{"count": 2, "type": "list"}] * 2
    for selection in edit_result["selectionPasses"]:
        assert {item["GetUniqueId"]["value"] for item in selection["items"]} == set(
            TARGETS
        )
    assert restoration_result["status"] == "restored-unsaved"
    assert restoration_result["playheadAfter"] == "00:06:07:24"
    assert restoration_result["saveDispatched"] is False
    assert restoration_result["setters"] == ["SetTrackLock"] * 4 + [
        "SetCurrentTimecode"
    ]

    trim_log = raw(
        "hammerspoon-editorial-trim-end-20261001T055914.668802Z.jsonl"
    ).read_text()
    requests = [json.loads(line) for line in trim_log.splitlines()]
    assert len(requests) == 2
    request = requests[0]["value"]
    assert requests[0]["phase"] == "request"
    assert request["namedCommand"] == "trim-end"
    assert request["proofSha256"] == SELECTION_RESULT_SHA256
    assert request["preparedPairSha256"] == EXPECTED_RAW["prep_after"]
    assert request["macroSha256"] == MACRO_SHA256
    assert requests[1]["phase"] == "return"
    assert requests[1]["value"]["exitCode"] == 0


def main():
    if "--publish" in sys.argv:
        build_manifest()
    verify_native_evidence()
    verify_publication()
    print(
        json.dumps(
            {
                "status": "independently-verified",
                "onlyTargetRangeFieldsChanged": True,
                "trimFrames": 25,
                "targetUidsPreserved": sorted(TARGETS),
                "markersAndReciprocalLinksPreserved": True,
                "allOtherContentSettingsPoolAndTimelinesUnchanged": True,
                "restoredOnlyRecordedLocksAndPlayhead": True,
                "saveOrUndoDispatched": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
