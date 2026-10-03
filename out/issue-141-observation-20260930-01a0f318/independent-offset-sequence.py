"""Guarded one-frame A1 offset nudge for the Issue 141 R2-offset fixture."""

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
HERE = ROOT / "docs/investigations/issue-141"
PINS = OUT / "latest-reviewed-source-pins.json"
EXPECTED_PINS = {
    "editorial-cases.py": "4f8acafc4ba78483518f4b9b39946888b7c79a3109d47a72a610d975abe851c6",
    "editorial-cases-check.py": "6d6edf65b4b43971997c8b2fc48afd77959e9fa84c946e349c2308e33875b019",
    "probe.py": "2a6a3b1c40f80f98617a43c2ed08e925a4a9668b146c481f270de0e9a047e057",
    "independent-native-call.py": "61ef935b47f5138545df909f41edffc2f10c7dcf55283068948950248e2c0531",
}
MATRIX = "29ae8331-b86e-4041-a548-960695cc7b24"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_guard():
    pins = json.loads(PINS.read_text())
    for name, digest in EXPECTED_PINS.items():
        if pins.get("hashes", {}).get(name) != digest:
            raise RuntimeError("Registered source pin changed: " + name)
        source = OUT / name if name == "independent-native-call.py" else HERE / name
        if sha(source) != digest:
            raise RuntimeError("Source differs from registered pin: " + name)


def validate_pair(pair):
    if (
        pair.get("selectedTimelineUid") != MATRIX
        or pair.get("timelineConsistency") != "equal-adjacent-reads"
        or pair.get("poolConsistency") != "equal-adjacent-reads"
        or len(pair.get("timelinePasses", [])) != 2
        or pair["timelinePasses"][0] != pair["timelinePasses"][1]
        or len(pair.get("poolPasses", [])) != 2
        or pair["poolPasses"][0] != pair["poolPasses"][1]
    ):
        raise RuntimeError("Complete stable Matrix timeline/pool pair required")


def moved_pair(pair, uid):
    """Exact one-frame delta: A1 target timeline bounds only."""
    validate_pair(pair)
    expected = copy.deepcopy(pair)
    seen = 0
    for state in expected["timelinePasses"]:
        rows = [t for t in state["timelines"] if t["GetUniqueId"]["value"] == MATRIX]
        if len(rows) != 1:
            raise RuntimeError("Matrix timeline missing or duplicated")
        tracks = [t for t in rows[0]["tracks"] if (t["type"], t["index"]) == ("audio", 1)]
        if len(tracks) != 1:
            raise RuntimeError("A1 missing or duplicated")
        items = [i for i in tracks[0]["items"] if i["GetUniqueId"]["value"] == uid]
        if len(items) != 1:
            raise RuntimeError("Target A1 UID missing or duplicated")
        item = items[0]
        seen += 1
        for key in ("GetStart", "GetStart(True)", "GetEnd", "GetEnd(True)"):
            item[key]["value"] += 1
    if seen != 2:
        raise RuntimeError("Target did not occur in both timeline passes")
    return expected


def verify_delta(before, after, uid):
    try:
        return after == moved_pair(before, uid)
    except (KeyError, TypeError, RuntimeError):
        return False


def label_guard():
    path = HERE / "editorial-readback.py"
    spec = importlib.util.spec_from_file_location("offset_labels", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert {"r2-offset-context", "r2-offset-deselected", "r2-offset-selected", "r2-offset-edited"} <= module.LABELS


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load approved local helper: " + str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pinned_pair(relative, digest):
    if (
        not isinstance(relative, str)
        or not relative
        or Path(relative).is_absolute()
        or any(part in {"", ".", ".."} for part in Path(relative).parts)
        or not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
    ):
        raise ValueError("Prior pair requires a contained output path and SHA-256")
    path, cursor = OUT / relative, OUT
    for part in Path(relative).parts:
        cursor /= part
        if cursor.is_symlink() or not cursor.resolve().is_relative_to(OUT.resolve()):
            raise ValueError("Prior pair may not link or escape OUT")
    if not path.is_file() or sha(path) != digest:
        raise ValueError("Prior pair is missing or its SHA-256 differs")
    pair = json.loads(path.read_text(encoding="utf-8"))
    validate_pair(pair)
    return path, pair


def retained_readback(native, label):
    result = native.invoke({"action": "editorial-readback", "editorialReadbackLabel": label})
    if (result.get("status") != "editorial-readback-retained"
            or result.get("failure") is not None or result.get("label") != label
            or result.get("readOnly") is not True):
        raise RuntimeError(label + " readback was not retained cleanly")
    ref = result.get("pair", {})
    path = Path(ref.get("path", ""))
    if (path.is_symlink() or not path.is_file()
            or not path.resolve().is_relative_to(OUT.resolve())
            or sha(path) != ref.get("sha256")):
        raise RuntimeError(label + " full pair pin is invalid")
    pair = json.loads(path.read_text(encoding="utf-8"))
    validate_pair(pair)
    passes = result.get("selectionPasses", [])
    if len(passes) != 2 or passes[0] != passes[1]:
        raise RuntimeError(label + " does not contain two equal selection passes")
    return result, pair, ref


def expect_selection(result, uid, source_uid, playhead, selected):
    passes = result["selectionPasses"]
    if any(row.get("playhead") != playhead for row in passes):
        raise RuntimeError("Selection readback has the wrong preparation playhead")
    for row in passes:
        items = row.get("items", [])
        if not selected:
            if items:
                raise RuntimeError("Deselected readback still contains a selection")
            continue
        if len(items) != 1 or items[0].get("GetUniqueId", {}).get("value") != uid:
            raise RuntimeError("Selected readback is not exactly the prepared A1 UID")
        item = items[0]
        if (item.get("GetMediaPoolItem", {}).get("GetUniqueId", {}).get("value") != source_uid
                or item.get("GetLinkedItems") != []):
            raise RuntimeError("Selected A1 source or empty-link evidence changed")


def run_sequence(prior_relative, prior_digest, native=None):
    prior_path, prior = pinned_pair(prior_relative, prior_digest)
    source_guard()
    native = native or load("independent_native_call", OUT / "independent-native-call.py")
    directory = OUT / datetime.now(UTC).strftime("independent-offset-sequence-%Y%m%dT%H%M%S.%fZ")
    directory.mkdir(exist_ok=False)

    preparation_result = native.invoke({
        "action": "editorial-case-prepare", "case": "R2-offset",
        "priorPair": str(prior_path.resolve().relative_to(OUT.resolve())),
        "priorPairSha256": prior_digest,
    })
    if preparation_result.get("status") != "case-prepared" or preparation_result.get("case") != "R2-offset":
        raise RuntimeError("Native R2-offset preparation did not validate")
    target = preparation_result.get("target", {})
    uid = target.get("uids", {}).get("audio")
    source_uid = target.get("sourceUids", {}).get("audio")
    playhead = target.get("selectionTimecode")
    prepared_ref = preparation_result.get("preparedPair", {})
    if not all((uid, source_uid, playhead, prepared_ref.get("path"), prepared_ref.get("sha256"))):
        raise RuntimeError("Prepared target UID/source, selection timecode, or pair pin missing")
    prep_path = directory / "preparation.json"
    prep_path.write_text(json.dumps({k: v for k, v in preparation_result.items() if not k.startswith("_")}, indent=2, sort_keys=True) + "\n")
    prep_sha = sha(prep_path)
    prep_relative = str(prep_path.resolve().relative_to(OUT.resolve()))
    prepared_path = OUT / prepared_ref["path"]
    if prepared_path.is_symlink() or not prepared_path.is_file() or sha(prepared_path) != prepared_ref["sha256"]:
        raise RuntimeError("Native preparation's full pair pin is invalid")
    prepared_pair = json.loads(prepared_path.read_text(encoding="utf-8"))
    validate_pair(prepared_pair)
    # Selection-mode setup and exact deselect/select evidence, with a complete pair each time.
    for menu in ("auto-none", "auto-a1"):
        native.invoke(menu=menu)
    native.invoke(menu="deselect")
    deselected, deselected_pair, _ = retained_readback(native, "r2-offset-deselected")
    if deselected_pair != prepared_pair:
        raise RuntimeError("Deselection changed the prepared full pair")
    expect_selection(deselected, uid, source_uid, playhead, False)
    native.invoke(menu="select")
    selected, selected_pair, _ = retained_readback(native, "r2-offset-selected")
    if selected_pair != prepared_pair:
        raise RuntimeError("Selection changed the prepared full pair")
    expect_selection(selected, uid, source_uid, playhead, True)

    native.invoke(menu="nudge-right")
    edited, edited_pair, edited_ref = retained_readback(native, "r2-offset-edited")
    expect_selection(edited, uid, source_uid, playhead, True)
    if not verify_delta(prepared_pair, edited_pair, uid):
        raise RuntimeError("Raw full-pair comparison found non-exact A1 one-frame delta; stopping without restoration")

    edited_relative = str(Path(edited_ref["path"]).resolve().relative_to(OUT.resolve()))
    restored = native.invoke({
        "action": "editorial-case-restore", "case": "R2-offset",
        "preparationResult": prep_relative, "preparationResultSha256": prep_sha,
        "postEditPair": edited_relative, "postEditPairSha256": edited_ref["sha256"],
    })
    if (restored.get("status") != "restored-unsaved"
            or restored.get("originalLocks") != preparation_result.get("originalLocks")
            or restored.get("originalPlayhead") != preparation_result.get("originalPlayhead")
            or restored.get("saveDispatched") is not False):
        raise RuntimeError("Bounded lock/playhead restoration did not validate")
    for menu in ("auto-none", "auto-v1", "auto-a1", "deselect"):
        native.invoke(menu=menu)
    final, final_pair, final_ref = retained_readback(native, "r2-offset-context")
    restored_pair_ref = restored.get("restoredPair", {})
    if (final_ref.get("sha256") != restored_pair_ref.get("sha256")
            or final_pair != json.loads((OUT / restored_pair_ref["path"]).read_text(encoding="utf-8"))):
        raise RuntimeError("Final full pair differs from native restored pair")
    expect_selection(final, uid, source_uid, preparation_result.get("originalPlayhead"), False)
    return {
        "status": "offset-sequence-complete", "case": "R2-offset",
        "priorPair": {"path": prior_relative, "sha256": prior_digest},
        "preparation": {"path": prep_relative, "sha256": prep_sha},
        "targetUid": uid, "sourceUid": source_uid,
        "deselectedLabel": "r2-offset-deselected", "selectedLabel": "r2-offset-selected",
        "editedLabel": "r2-offset-edited", "restoredLabel": "r2-offset-context",
        "editedPair": edited_ref, "restoredPair": restored_pair_ref,
        "finalPair": final_ref, "saveDispatched": False,
        "nativeResults": {name: {"path": result["_nativeResultPath"], "sha256": sha(result["_nativeResultPath"])}
                          for name, result in (("deselected", deselected), ("selected", selected), ("edited", edited), ("restoration", restored), ("finalReadback", final))},
    }


def check():
    label_guard()
    protocol = (
        (("auto-none", "auto-a1", "deselect"), "r2-offset-deselected"),
        (("select",), "r2-offset-selected"),
        (("nudge-right",), "r2-offset-edited"),
        (("auto-none", "auto-v1", "auto-a1", "deselect"), "r2-offset-context"),
    )
    allowed_menus = {"auto-none", "auto-a1", "auto-v1", "deselect", "select", "nudge-right"}
    labels = {"r2-offset-deselected", "r2-offset-selected", "r2-offset-edited", "r2-offset-context"}
    assert all(label in labels and set(menus) <= allowed_menus for menus, label in protocol)
    base = {"timelines": [{"GetUniqueId": {"value": MATRIX}, "tracks": [
        {"type": "audio", "index": 1, "items": [
            {"GetUniqueId": {"value": "A1"}, "GetStart": {"value": 5100}, "GetStart(True)": {"value": 5100.0}, "GetEnd": {"value": 5299}, "GetEnd(True)": {"value": 5299.0}, "GetMediaPoolItem": {"GetUniqueId": {"value": "SRC"}}, "GetLinkedItems": []},
            {"GetUniqueId": {"value": "OTHER"}, "GetStart": {"value": 0}, "GetStart(True)": {"value": 0.0}, "GetEnd": {"value": 1}, "GetEnd(True)": {"value": 1.0}},
        ]},
        {"type": "video", "index": 1, "items": [{"GetUniqueId": {"value": "V1"}, "GetStart": {"value": 5100}, "GetStart(True)": {"value": 5100.0}, "GetEnd": {"value": 5299}, "GetEnd(True)": {"value": 5299.0}}]},
    ]}]}
    pair = {"selectedTimelineUid": MATRIX, "timelineConsistency": "equal-adjacent-reads", "poolConsistency": "equal-adjacent-reads", "timelinePasses": [base, copy.deepcopy(base)], "poolPasses": [{"pool": []}, {"pool": []}]}
    good = moved_pair(pair, "A1")
    assert verify_delta(pair, good, "A1")
    wrong_target = copy.deepcopy(pair)
    for state in wrong_target["timelinePasses"]:
        item = state["timelines"][0]["tracks"][1]["items"][0]
        for key in ("GetStart", "GetStart(True)", "GetEnd", "GetEnd(True)"):
            item[key]["value"] += 1
    assert not verify_delta(pair, wrong_target, "A1")
    unrelated = copy.deepcopy(good)
    unrelated["timelinePasses"][0]["timelines"][0]["tracks"][1]["items"][0]["GetStart"]["value"] += 1
    unrelated["timelinePasses"][1] = copy.deepcopy(unrelated["timelinePasses"][0])
    assert not verify_delta(pair, unrelated, "A1")
    print("PASS: exact A1 raw delta, wrong-target refusal, unrelated-change refusal, and label inventory. Does not test native calls, captured Resolve schema completeness, locking, menus, or restoration.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--prior-pair")
    parser.add_argument("--prior-sha256")
    args = parser.parse_args()
    if args.check:
        check()
        return
    if not args.run or not args.prior_pair or not args.prior_sha256:
        parser.error("--run requires --prior-pair (relative to OUT) and --prior-sha256")
    print(json.dumps(run_sequence(args.prior_pair, args.prior_sha256), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
