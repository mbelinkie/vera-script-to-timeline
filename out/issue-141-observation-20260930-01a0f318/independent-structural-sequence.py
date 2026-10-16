"""Guarded R3 Graphic/boundary single-split sequences; --check is fake-only."""

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
CASES_SHA256 = "4f8acafc4ba78483518f4b9b39946888b7c79a3109d47a72a610d975abe851c6"
CHECK_SHA256 = "6d6edf65b4b43971997c8b2fc48afd77959e9fa84c946e349c2308e33875b019"
PROBE_SHA256 = "2a6a3b1c40f80f98617a43c2ed08e925a4a9668b146c481f270de0e9a047e057"
NATIVE_CALL_SHA256 = "61ef935b47f5138545df909f41edffc2f10c7dcf55283068948950248e2c0531"
CASES = ("R3-Graphic", "R3-boundary")
SOURCE_PINS = {
    "editorial-cases.py": CASES_SHA256,
    "editorial-cases-check.py": CHECK_SHA256,
    "probe.py": PROBE_SHA256,
    "independent-native-call.py": NATIVE_CALL_SHA256,
}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load pinned helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _boundary(case, relative, digest):
    if case not in CASES:
        raise ValueError("Only R3-Graphic and R3-boundary may run")
    if (
        not isinstance(relative, str)
        or not relative
        or Path(relative).is_absolute()
        or any(part in {"", ".", ".."} for part in Path(relative).parts)
    ):
        raise ValueError("Prior pair must be a contained relative output path")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Prior pair SHA-256 must be 64 lowercase hex characters")
    path = OUT / relative
    cursor = OUT
    for part in Path(relative).parts:
        cursor /= part
        if cursor.is_symlink() or not cursor.resolve().is_relative_to(OUT.resolve()):
            raise ValueError("Prior pair may not link or escape approved output")
    if not path.is_file() or _sha(path) != digest:
        raise ValueError("Prior pair is missing or its SHA-256 differs")
    pair = json.loads(path.read_text(encoding="utf-8"))
    if (
        pair.get("selectedTimelineUid") != "29ae8331-b86e-4041-a548-960695cc7b24"
        or pair.get("timelineConsistency") != "equal-adjacent-reads"
        or pair.get("poolConsistency") != "equal-adjacent-reads"
    ):
        raise ValueError("Prior pair must be a complete stable Matrix readback")
    return path


def _save(directory, name, value):
    path = directory / name
    clean = {key: val for key, val in value.items() if not key.startswith("_")}
    path.write_text(json.dumps(clean, indent=2, sort_keys=True) + "\n")
    return {
        "path": str(path.resolve().relative_to(OUT.resolve())),
        "sha256": _sha(path),
    }, clean


def _readback(native, directory, label):
    result = native.invoke(
        {"action": "editorial-readback", "editorialReadbackLabel": label}
    )
    if (
        result.get("status") != "editorial-readback-retained"
        or result.get("failure") is not None
        or result.get("label") != label
        or result.get("readOnly") is not True
    ):
        raise RuntimeError(f"{label} readback was not retained cleanly")
    pair_ref = result.get("pair", {})
    pair_path = Path(pair_ref.get("path", ""))
    if (
        pair_path.is_symlink()
        or not pair_path.is_file()
        or not pair_path.resolve().is_relative_to(OUT.resolve())
        or _sha(pair_path) != pair_ref.get("sha256")
    ):
        raise RuntimeError(f"{label} full-state pair pin is invalid")
    ref, clean = _save(directory, label + ".json", result)
    return ref, clean, pair_path, pair_ref["sha256"]


def _selection(
    native, directory, cases, case, stage, preparation, expected_pair, expected_sha
):
    cut_tc = preparation["target"]["splitPlayheadTimecode"]
    if stage == "first":
        selected_label = {
            "R3-Graphic": "r3-graphic-selected",
            "R3-boundary": "r3-boundary-selected",
        }[case]
        deselected_label = selected_label.removesuffix("-selected") + "-deselected"
    else:
        raise ValueError("Only the first named R3 split is supported")
    for menu in ("auto-none", "auto-v1", "auto-a1"):
        native.invoke(menu=menu)
    native.invoke(menu="deselect")
    deselect_ref, deselected, _, deselected_sha = _readback(
        native, directory, deselected_label
    )
    if (
        deselected_sha != expected_sha
        or any(row.get("items") for row in deselected.get("selectionPasses", []))
        or len(deselected.get("selectionPasses", [])) != 2
        or any(row.get("playhead") != cut_tc for row in deselected["selectionPasses"])
    ):
        raise RuntimeError(f"{case} deselect changed state or missed the cut point")
    native.invoke(menu="select")
    selection_ref, selected, _, selected_sha = _readback(
        native, directory, selected_label
    )
    selection_passes = selected.get("selectionPasses", [])
    if (
        selected_sha != expected_sha
        or len(selection_passes) != 2
        or any(row.get("playhead") != cut_tc for row in selection_passes)
    ):
        raise RuntimeError(f"{case} selected readback changed full state or playhead")
    uids = [preparation["target"]["uids"][k] for k in ("video", "audio")]
    selected_rows = selection_passes[0].get("items", [])
    if (
        len(selected_rows) != 2
        or [row.get("GetUniqueId", {}).get("value") for row in selected_rows] != uids
    ):
        raise RuntimeError(
            f"{case} selected readback did not bind the exact linked UIDs"
        )
    ready = native.invoke(
        {
            "action": "r2-named-split-ready",
            "case": case,
            "stage": "first",
            "preparationResult": preparation["_ref"]["path"],
            "preparationResultSha256": preparation["_ref"]["sha256"],
            "firstSelectionResult": selection_ref["path"],
            "firstSelectionResultSha256": selection_ref["sha256"],
        }
    )
    ready_ref, ready = _save(directory, f"{case}-split-ready.json", ready)
    expected_frame = cases.CASES[case]["start"] + cases.R2_LINKED_SPLITS[case][0]
    if (
        ready.get("status") != "split-ready"
        or ready.get("case") != case
        or ready.get("stage") != "first"
        or ready.get("selectedUids") != uids
        or ready.get("splitFrame") != expected_frame
        or ready.get("menuCommandDispatched") is not False
    ):
        raise RuntimeError(f"{case} native split-ready binding refused")
    return deselect_ref, selection_ref, ready_ref, cut_tc


def run_sequence(case, prior_pair, prior_sha, *, native=None, cases_module=None):
    prior = _boundary(case, prior_pair, prior_sha)
    sources = {
        "editorial-cases.py": HERE / "editorial-cases.py",
        "editorial-cases-check.py": HERE / "editorial-cases-check.py",
        "probe.py": HERE / "probe.py",
        "independent-native-call.py": OUT / "independent-native-call.py",
    }
    for name, source in sources.items():
        expected = SOURCE_PINS[name]
        if source.is_symlink() or _sha(source) != expected:
            raise RuntimeError(f"Pinned editorial source changed: {source.name}")
    native = native or _load(
        "independent_native_call", OUT / "independent-native-call.py"
    )
    cases = cases_module or _load("editorial_cases", HERE / "editorial-cases.py")
    directory = OUT / datetime.now(UTC).strftime(
        "independent-structural-sequence-%Y%m%dT%H%M%S.%fZ"
    )
    directory.mkdir()
    cleared = {
        "preparationResult": None,
        "preparationResultSha256": None,
        "firstSplitPair": None,
        "firstSplitPairSha256": None,
        "firstSelectionResult": None,
        "firstSelectionResultSha256": None,
        "selectionResult": None,
        "selectionResultSha256": None,
    }
    preparation_result = native.invoke(
        {
            "action": "editorial-case-prepare",
            "case": case,
            "priorPair": str(prior.resolve().relative_to(OUT.resolve())),
            "priorPairSha256": prior_sha,
            **cleared,
        }
    )
    prep_ref, preparation = _save(directory, "preparation.json", preparation_result)
    if preparation.get("status") != "case-prepared" or preparation.get("case") != case:
        raise RuntimeError(f"{case} preparation did not validate")
    preparation["_ref"] = prep_ref
    prepared_ref = preparation.get("preparedPair", {})
    prepared_path = OUT / prepared_ref.get("path", "")
    if (
        prepared_path.is_symlink()
        or not prepared_path.is_file()
        or _sha(prepared_path) != prepared_ref.get("sha256")
    ):
        raise RuntimeError("Prepared full-state pair pin is invalid")
    prepared_pair = json.loads(prepared_path.read_text(encoding="utf-8"))
    _, _, _, selected_sha = _readback(
        native, directory, f"{case.lower()}-context"
    )
    if selected_sha != prepared_ref.get("sha256"):
        raise RuntimeError("Fresh prepared readback differs from preparation pin")
    _, selection_ref, ready_ref, cut_tc = _selection(
        native,
        directory,
        cases,
        case,
        "first",
        preparation,
        prepared_pair,
        prepared_ref["sha256"],
    )
    native.invoke(menu="split")
    split_ref, split_readback, split_pair_path, split_sha = _readback(
        native, directory, f"{case.lower()}-split"
    )
    if split_readback["selectionPasses"][0].get("playhead") != cut_tc:
        raise RuntimeError(f"{case} split readback missed the cut point")
    split_result = native.invoke(
        {
            "action": "r2-named-split-review",
            "case": case,
            "preparationResult": prep_ref["path"],
            "preparationResultSha256": prep_ref["sha256"],
            "firstSelectionResult": selection_ref["path"],
            "firstSelectionResultSha256": selection_ref["sha256"],
            "firstSplitPair": str(split_pair_path.resolve().relative_to(OUT.resolve())),
            "firstSplitPairSha256": split_sha,
        }
    )
    review_ref, split_review = _save(directory, "split-review.json", split_result)
    if (
        split_review.get("status") != "split-readback-retained"
        or split_review.get("case") != case
        or split_review.get("saveDispatched") is not False
        or split_review.get("menuCommandDispatched") is not False
    ):
        raise RuntimeError(f"{case} full-state split review refused")
    restore_result = native.invoke(
        {
            "action": "editorial-case-restore",
            "case": case,
            "preparationResult": prep_ref["path"],
            "preparationResultSha256": prep_ref["sha256"],
            "postEditPair": str(split_pair_path.resolve().relative_to(OUT.resolve())),
            "postEditPairSha256": split_sha,
        }
    )
    restore_ref, restored = _save(directory, "restoration.json", restore_result)
    if (
        restored.get("status") != "restored-unsaved"
        or restored.get("originalLocks") != preparation.get("originalLocks")
        or restored.get("originalPlayhead") != preparation.get("originalPlayhead")
        or restored.get("saveDispatched") is not False
    ):
        raise RuntimeError(f"{case} lock/playhead restoration failed")
    for menu in ("auto-none", "auto-v1", "auto-a1", "deselect"):
        native.invoke(menu=menu)
    final_ref, final_readback, _, final_sha = _readback(
        native, directory, f"{case.lower()}-context"
    )
    if final_sha != restored.get("restoredPair", {}).get("sha256") or final_readback[
        "selectionPasses"
    ][0].get("playhead") != preparation.get("originalPlayhead"):
        raise RuntimeError(
            f"{case} final context readback differs after Auto Select reset"
        )
    if len(final_readback.get("selectionPasses", [])) != 2 or any(
        row.get("items") != [] or row.get("playhead") != preparation["originalPlayhead"]
        for row in final_readback["selectionPasses"]
    ):
        raise RuntimeError(f"{case} temporary selection or playhead was not restored")
    return {
        "status": "structural-sequence-complete",
        "case": case,
        "directory": str(directory),
        "priorPair": {"path": prior_pair, "sha256": prior_sha},
        "sourcePins": SOURCE_PINS,
        "preparation": prep_ref,
        "firstSelection": selection_ref,
        "splitReady": ready_ref,
        "splitPair": split_ref,
        "splitReview": review_ref,
        "restoration": restore_ref,
        "autoSelectReset": final_ref,
        "finalPairSha256": final_sha,
        "saveDispatched": False,
    }


def offline_check():
    """Exercise existing fake stores/validators and the exact selection refusal."""
    labels = {
        f"{case.lower()}-{stage}"
        for case in CASES
        for stage in ("context", "deselected", "selected", "split")
    }
    reader = _load("editorial_readback_labels", HERE / "editorial-readback.py")
    invalid = sorted(labels - reader.LABELS)
    if invalid:
        raise AssertionError(f"Unsupported editorial readback labels: {invalid}")
    sources = {
        "editorial-cases.py": HERE / "editorial-cases.py",
        "editorial-cases-check.py": HERE / "editorial-cases-check.py",
        "probe.py": HERE / "probe.py",
        "independent-native-call.py": OUT / "independent-native-call.py",
    }
    for name, source in sources.items():
        if source.is_symlink() or _sha(source) != SOURCE_PINS[name]:
            raise RuntimeError(f"Pinned editorial source changed: {source.name}")
    checker = _load("editorial_cases_checker", HERE / "editorial-cases-check.py")
    result, store = checker.run_case("R3-Graphic", named_sequence=True)
    assert result["ready"]["status"] == "split-ready"
    assert result["review"]["status"] == "split-readback-retained"
    assert result["review"]["saveDispatched"] is False
    graphic = next(
        item
        for track in store.matrix_state()["tracks"]
        if track["type"] == "video" and track["index"] == 3
        for item in track["items"]
        if item["GetUniqueId"]["value"] == "graphic-v3"
    )
    assert graphic["GetClipEnabled"] == {"value": True}
    refused, store = checker.run_case(
        "R3-Graphic", named_sequence=True, phase_mode="wrong-first-selection-id"
    )
    assert "first_ready_refusal" in refused
    assert "split changed" not in str(refused)
    assert not any(call[0] == "Razor" for call in store.calls)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, default="R3-Graphic")
    parser.add_argument("--prior-pair", required=True)
    parser.add_argument("--prior-sha256", required=True)
    parser.add_argument("--check", action="store_true", help="fake-only verification")
    parser.add_argument(
        "--run", action="store_true", help="execute guarded native sequence"
    )
    args = parser.parse_args(argv)
    if args.check == args.run:
        parser.error("choose exactly one of --check or --run")
    prior = _boundary(args.case, args.prior_pair, args.prior_sha256)
    if args.check:
        offline_check()
        print(
            f"Fake R3 sequence checks pass; input pin: {prior.name}; no Resolve action."
        )
        return 0
    result = run_sequence(args.case, args.prior_pair, args.prior_sha256)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
