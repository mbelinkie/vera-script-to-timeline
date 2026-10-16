"""Guarded native A3-only split; --check uses fake stores only."""

import argparse
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
REGISTRY = OUT / "latest-reviewed-source-pins.json"
SOURCES = ("probe.py", "editorial-cases.py", "editorial-cases-check.py", "independent-native-call.py")
LABELS = tuple(f"r3-boundary-a3-{s}" for s in ("context", "deselected", "selected", "split"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pins():
    registry = json.loads(REGISTRY.read_text())
    registered = registry.get("hashes", {})
    for name in SOURCES:
        path = OUT / name if name == "independent-native-call.py" else HERE / name
        if path.is_symlink() or registered.get(name) != sha(path):
            raise RuntimeError(f"Registered source pin missing or stale: {name}")
    return {name: registered[name] for name in SOURCES}


def contained(path, digest, label):
    if not isinstance(path, str) or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError(f"{label} requires a path and lowercase SHA-256")
    p = Path(path)
    if not p.is_absolute():
        p = OUT / p
    if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(OUT.resolve()) or sha(p) != digest:
        raise ValueError(f"{label} is not the exact pinned output file")
    return p.resolve()


def run(prior_path, prior_sha, split_path, split_sha, restore_path, restore_sha):
    source_pins = pins()
    prior = contained(prior_path, prior_sha, "priorPair")
    split_file = contained(split_path, split_sha, "baseSplitResult")
    restore_file = contained(restore_path, restore_sha, "baseRestoreResult")
    split = json.loads(split_file.read_text())
    restored = json.loads(restore_file.read_text())
    if split.get("status") != "split-readback-retained" or split.get("case") != "R3-boundary" or split.get("saveDispatched") is not False:
        raise ValueError("baseSplitResult must be successful exact R3-boundary review")
    if restored.get("status") != "restored-unsaved" or restored.get("case") != "R3-boundary" or restored.get("saveDispatched") is not False:
        raise ValueError("baseRestoreResult must be successful exact R3-boundary restore")
    native = load("independent_native_call", OUT / "independent-native-call.py")
    stamp = datetime.now(UTC).strftime("independent-boundary-a3-%Y%m%dT%H%M%S.%fZ")
    directory = OUT / stamp
    directory.mkdir()

    def save(name, obj):
        path = directory / name
        clean = {k: v for k, v in obj.items() if not k.startswith("_")}
        path.write_text(json.dumps(clean, indent=2, sort_keys=True) + "\n")
        return {"path": str(path.relative_to(OUT)), "sha256": sha(path)}, clean

    def read(label):
        result = native.invoke({"action": "editorial-readback", "editorialReadbackLabel": label})
        pair = result.get("pair", {})
        pairpath = contained(pair.get("path"), pair.get("sha256"), label + " pair")
        if result.get("status") != "editorial-readback-retained" or result.get("label") != label or result.get("failure") is not None:
            raise RuntimeError(f"Readback refused: {label}")
        ref, clean = save(label + ".json", result)
        return ref, clean, pairpath, pair["sha256"]

    clear = {k: None for k in ("preparationResult", "preparationResultSha256", "firstSplitPair", "firstSplitPairSha256", "firstSelectionResult", "firstSelectionResultSha256", "selectionResult", "selectionResultSha256")}
    prep_raw = native.invoke({"action": "editorial-case-prepare", "case": "R3-boundary-A3", "priorPair": str(prior.relative_to(OUT)), "priorPairSha256": prior_sha, "baseSplitResult": str(split_file.relative_to(OUT)), "baseSplitResultSha256": split_sha, "baseRestoreResult": str(restore_file.relative_to(OUT)), "baseRestoreResultSha256": restore_sha, **clear})
    prep_ref, prep = save("preparation.json", prep_raw)
    if prep.get("status") != "case-prepared" or prep.get("case") != "R3-boundary-A3":
        raise RuntimeError("A3 preparation refused")
    prepared = prep.get("preparedPair", {})
    prepared_pair = contained(prepared.get("path"), prepared.get("sha256"), "prepared pair")
    _, context, _, ctx_sha = read(LABELS[0])
    if ctx_sha != prepared["sha256"]:
        raise RuntimeError("Prepared context changed")
    for menu in ("auto-none", "auto-a3", "deselect"):
        native.invoke(menu=menu)
    deselect_ref, deselect, _, deselect_sha = read(LABELS[1])
    passes = deselect.get("selectionPasses", [])
    cut = prep.get("target", {}).get("splitPlayheadTimecode")
    if deselect_sha != ctx_sha or len(passes) != 2 or any(x.get("items") != [] or x.get("playhead") != cut for x in passes):
        raise RuntimeError("A3 deselection was not two empty passes at split frame")
    uid = prep["target"]["uid"]
    source = prep["target"]["sourceUid"]
    selection_config = {"action": "editorial-readback"}
    native.invoke(menu="select")
    selected_ref, selected, _, selected_sha = read(LABELS[2])
    passes = selected.get("selectionPasses", [])
    if selected_sha != ctx_sha or len(passes) != 2 or any(x.get("playhead") != cut for x in passes):
        raise RuntimeError("A3 selection changed state or playhead")
    chosen = passes[0].get("items", [])
    if len(chosen) != 1 or chosen[0].get("GetUniqueId", {}).get("value") != uid or chosen[0].get("GetMediaPoolItem", {}).get("GetUniqueId", {}).get("value") != source:
        raise RuntimeError("A3 exact source selection refused")
    ready = native.invoke({"action": "r3-boundary-a3-split-ready", "case": "R3-boundary-A3", "preparationResult": prep_ref["path"], "preparationResultSha256": prep_ref["sha256"], "selectionResult": selected_ref["path"], "selectionResultSha256": selected_ref["sha256"]})
    if ready.get("status") != "split-ready" or ready.get("selectedUids") != [uid] or ready.get("splitFrame") != 9100:
        raise RuntimeError("Named A3 split-ready refused")
    ready_ref, ready = save("split-ready.json", ready)
    native.invoke(menu="split")
    split_ref, split_readback, split_pair, split_pair_sha = read(LABELS[3])
    review = native.invoke({"action": "r3-boundary-a3-split-review", "case": "R3-boundary-A3", "preparationResult": prep_ref["path"], "preparationResultSha256": prep_ref["sha256"], "selectionResult": selected_ref["path"], "selectionResultSha256": selected_ref["sha256"], "splitPair": str(split_pair.relative_to(OUT)), "splitPairSha256": split_pair_sha})
    if review.get("status") != "split-readback-retained":
        raise RuntimeError("Named A3 split review refused")
    restore = native.invoke({"action": "editorial-case-restore", "case": "R3-boundary-A3", "preparationResult": prep_ref["path"], "preparationResultSha256": prep_ref["sha256"], "postEditPair": str(split_pair.relative_to(OUT)), "postEditPairSha256": split_pair_sha})
    restore_ref, restored_a3 = save("restoration.json", restore)
    if restored_a3.get("status") != "restored-unsaved":
        raise RuntimeError("A3 temporary state restore refused")
    for menu in ("auto-none", "auto-v1", "auto-a1", "deselect"):
        native.invoke(menu=menu)
    final_ref, final, final_pair, final_sha = read(LABELS[0])
    passes = final.get("selectionPasses", [])
    if final_sha != restored_a3.get("restoredPair", {}).get("sha256") or len(passes) != 2 or any(x.get("items") != [] or x.get("playhead") != prep.get("originalPlayhead") for x in passes):
        raise RuntimeError("A3 final context did not restore original playhead/empty selection")
    result = {"status": "a3-sequence-complete", "preparation": prep_ref, "deselection": deselect_ref, "selection": selected_ref, "splitReady": ready_ref, "splitReadback": split_ref, "splitReview": save("split-review.json", review)[0], "restoration": restore_ref, "finalReadback": final_ref, "finalPair": {"path": str(final_pair.relative_to(OUT)), "sha256": final_sha}, "sourcePins": source_pins, "baseSplitResult": {"path": str(split_file.relative_to(OUT)), "sha256": split_sha}, "baseRestoreResult": {"path": str(restore_file.relative_to(OUT)), "sha256": restore_sha}, "saveDispatched": False}
    (directory / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def check():
    reader = load("editorial_readback", HERE / "editorial-readback.py")
    if any(label not in reader.LABELS for label in LABELS):
        raise AssertionError("A3 readback label is not registered")
    pins()
    checker = load("editorial_cases_checker", HERE / "editorial-cases-check.py")
    result, _ = checker.run_case("R3-boundary", named_sequence=True, phase_mode="wrong-first-selection-id")
    refusal = result.get("first_ready_refusal")
    if not refusal or "selected UIDs" not in refusal:
        raise AssertionError("Exact wrong-selection refusal was not exercised")
    return {"check": "passed", "driverSha256": sha(__file__), "labels": list(LABELS), "sourcePins": pins(), "wrongSelectionRefusal": refusal, "scope": "fake editorial checker helpers only; does not exercise driver orchestration or native dispatch"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prior-pair", required=True)
    p.add_argument("--prior-sha256", required=True)
    p.add_argument("--base-split-result")
    p.add_argument("--base-split-sha256")
    p.add_argument("--base-restore-result")
    p.add_argument("--base-restore-sha256")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--run", action="store_true")
    a = p.parse_args()
    # Require exact current prior pin even for --check; no app is touched here.
    contained(a.prior_pair, a.prior_sha256, "priorPair")
    if a.check:
        result = check()
        path = OUT / "independent-boundary-a3-check-readiness.json"
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if not all((a.base_split_result, a.base_split_sha256, a.base_restore_result, a.base_restore_sha256)):
        p.error("--run requires exact --base-split-result/--base-split-sha256 and --base-restore-result/--base-restore-sha256")
    print(json.dumps(run(a.prior_pair, a.prior_sha256, a.base_split_result, a.base_split_sha256, a.base_restore_result, a.base_restore_sha256), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
