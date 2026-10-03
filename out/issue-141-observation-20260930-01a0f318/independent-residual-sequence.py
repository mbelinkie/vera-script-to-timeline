#!/usr/bin/env python3
"""Guarded R2-residual sequence; --check is fake-only and --run is native."""
import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
HERE = ROOT / "docs/investigations/issue-141"
PINS = {
    "probe.py": "f0c87c02070163fa6790e5f7f317303b12f57e319024b749b8ab061d573e4c99",
    "editorial-cases.py": "2963ad80449c93fd13831a761f36a35ac9c38749b7240ceb8d3cf115c8008154",
    "editorial-cases-check.py": "66a11c2ce1ed1b0b2e1d22044f3d30088f219e2030ec8dfda959812b65eac1cf",
    "independent-native-call.py": "71c8d21654f67e467caab726820a9e4b06d83301c18d62a0486d97653043870e",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pin_sources(*, native=True):
    paths = {
        "probe.py": HERE / "probe.py",
        "editorial-cases.py": HERE / "editorial-cases.py",
        "editorial-cases-check.py": HERE / "editorial-cases-check.py",
        "independent-native-call.py": OUT / "independent-native-call.py",
    }
    for name, path in paths.items():
        if not native and name in {"probe.py", "independent-native-call.py"}:
            continue
        if path.is_symlink() or not path.is_file() or sha(path) != PINS[name]:
            raise RuntimeError(f"Reviewed source pin changed: {path.resolve()}")
    return paths


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load reviewed helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contained_prior(relative, digest):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("Prior pair must be a contained relative output path")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Prior pair SHA-256 must be 64 lowercase hex characters")
    path = OUT / relative
    cursor = OUT
    for part in Path(relative).parts:
        if part in {"", ".", ".."}:
            raise ValueError("Prior pair path may not traverse output")
        cursor /= part
        if cursor.is_symlink() or not cursor.resolve().is_relative_to(OUT.resolve()):
            raise ValueError("Prior pair may not link or escape approved output")
    if not path.is_file() or sha(path) != digest:
        raise ValueError("Prior pair is missing or its SHA-256 differs")
    pair = json.loads(path.read_text(encoding="utf-8"))
    if (pair.get("selectedTimelineUid") != "29ae8331-b86e-4041-a548-960695cc7b24"
            or pair.get("timelineConsistency") != "equal-adjacent-reads"
            or pair.get("poolConsistency") != "equal-adjacent-reads"
            or not isinstance(pair.get("timelinePasses"), list)
            or len(pair["timelinePasses"]) != 2
            or pair["timelinePasses"][0] != pair["timelinePasses"][1]
            or not isinstance(pair.get("poolPasses"), list)
            or len(pair["poolPasses"]) != 2
            or pair["poolPasses"][0] != pair["poolPasses"][1]):
        raise ValueError("Prior pair is not a stable full-state Matrix readback")
    # The independently reviewed path+digest is the handoff. Keep this case
    # agnostic so a later reviewed boundary pair can continue the sequence.
    return path, pair


def contained_record(relative, digest):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("Resume record must be a contained relative output path")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Resume record SHA-256 must be 64 lowercase hex characters")
    path = OUT / relative
    cursor = OUT
    for part in Path(relative).parts:
        if part in {"", ".", ".."}:
            raise ValueError("Resume record path may not traverse output")
        cursor /= part
        if cursor.is_symlink() or not cursor.resolve().is_relative_to(OUT.resolve()):
            raise ValueError("Resume record may not link or escape approved output")
    if not path.is_file() or sha(path) != digest:
        raise ValueError("Resume record is missing or its SHA-256 differs")
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError("Resume record must be a JSON object")
    return path, record


def save(directory, name, value):
    path = directory / name
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": str(path.resolve().relative_to(OUT.resolve())), "sha256": sha(path)}, value


def bound_path(reference):
    rel, digest = reference["path"], reference["sha256"]
    path = OUT / rel
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(OUT.resolve()) or sha(path) != digest:
        raise RuntimeError(f"Evidence pin changed: {rel}")
    return path


def readback(native, directory, label):
    value = native.invoke({"action": "editorial-readback", "editorialReadbackLabel": label})
    if (value.get("status") != "editorial-readback-retained" or value.get("failure") is not None
            or value.get("label") != label or value.get("readOnly") is not True):
        raise RuntimeError(f"{label} full-state readback refused")
    pair = value.get("pair", {})
    pair_path = Path(pair.get("path", ""))
    if pair_path.is_symlink() or not pair_path.is_file() or not pair_path.resolve().is_relative_to(OUT.resolve()) or sha(pair_path) != pair.get("sha256"):
        raise RuntimeError(f"{label} full-state pair pin invalid")
    ordinal = len(list(directory.glob("*.json"))) + 1
    ref, clean = save(directory, f"{ordinal:03d}-{label}.json", value)
    return ref, clean, pair_path, pair["sha256"]


def _selection_labels(stage):
    assert stage in {"first", "second"}
    return "r2-residual-deselected", "r2-residual-" + ("" if stage == "first" else "second-") + "selected"


def select_linked(native, directory, case, stage, preparation_ref, pair_ref, target_uids,
                  expected_tc, position_ref=None, first_pair_ref=None, *,
                  preparation, cases, reader, probe):
    deselected_label, selected_label = _selection_labels(stage)
    for menu in ("auto-none", "auto-v1", "auto-a1"):
        native.invoke(menu=menu)
    native.invoke(menu="deselect")
    _, deselected, _, deselected_sha = readback(native, directory, deselected_label)
    if deselected_sha != pair_ref["sha256"] or len(deselected.get("selectionPasses", [])) != 2 or any(row.get("items") for row in deselected["selectionPasses"]):
        raise RuntimeError(f"{stage} deselection changed pair or did not clear selection")
    native.invoke(menu="select")
    selected_ref, selected, _, selected_sha = readback(native, directory, selected_label)
    passes = selected.get("selectionPasses", [])
    ids = [row.get("GetUniqueId", {}).get("value") for row in (passes[0].get("items", []) if passes else [])]
    if selected_sha != pair_ref["sha256"] or len(passes) != 2 or any(p.get("playhead") != expected_tc for p in passes) or ids != target_uids or passes[1].get("items") != passes[0].get("items"):
        raise RuntimeError(f"{stage} selected readback did not bind exact ordered linked UIDs")
    expected_pair = json.loads(bound_path(pair_ref).read_text(encoding="utf-8"))
    target_map = {kind: target_uids[index] for index, kind in enumerate(("video", "audio"))}
    cases._selected_uids(
        reader,
        OUT,
        probe,
        {"selectionResult": selected_ref["path"], "selectionResultSha256": selected_ref["sha256"]},
        expected_pair,
        pair_ref["sha256"],
        selected_label,
        cases._linked_selection_targets(preparation, target_map),
    )
    action = native.invoke({
        "action": "r2-named-split-ready", "case": case, "stage": stage,
        "preparationResult": preparation_ref["path"], "preparationResultSha256": preparation_ref["sha256"],
        "firstSelectionResult": selected_ref["path"] if stage == "first" else None,
        "firstSelectionResultSha256": selected_ref["sha256"] if stage == "first" else None,
        "selectionResult": selected_ref["path"] if stage == "second" else None,
        "selectionResultSha256": selected_ref["sha256"] if stage == "second" else None,
        "firstSplitPair": first_pair_ref["path"] if stage == "second" else None,
        "firstSplitPairSha256": first_pair_ref["sha256"] if stage == "second" else None,
        "secondPositionResult": position_ref["path"] if stage == "second" else None,
        "secondPositionResultSha256": position_ref["sha256"] if stage == "second" else None,
    })
    return selected_ref, selected, action


def run_sequence(relative, digest, *, native=None):
    prior_path, _ = contained_prior(relative, digest)
    sources = pin_sources()
    native = native or load("independent_native_call", sources["independent-native-call.py"])
    cases = load("residual_editorial_cases", sources["editorial-cases.py"])
    probe = load("residual_probe", sources["probe.py"])
    reader = cases._reader(probe)
    case = "R2-residual"
    directory = OUT / datetime.now(UTC).strftime("independent-residual-sequence-%Y%m%dT%H%M%S.%fZ")
    directory.mkdir()
    initial = native.invoke({
        "action": "editorial-case-prepare", "case": case,
        "priorPair": str(prior_path.resolve().relative_to(OUT.resolve())), "priorPairSha256": digest,
        "preparationResult": None, "preparationResultSha256": None,
        "firstSplitPair": None, "firstSplitPairSha256": None,
        "firstSelectionResult": None, "firstSelectionResultSha256": None,
        "selectionResult": None, "selectionResultSha256": None,
    })
    prep_ref, prep = save(directory, "preparation.json", initial)
    if prep.get("status") != "case-prepared" or prep.get("case") != case:
        raise RuntimeError("R2-residual preparation refused")
    prepared_ref = prep.get("preparedPair", {})
    prepared_path = bound_path(prepared_ref)
    prepared_pair = json.loads(prepared_path.read_text(encoding="utf-8"))
    prepared_state, prepared_pool = reader._validate_read_pair(prepared_pair, probe)
    _, _, actual_prepared, actual_sha = readback(native, directory, "r2-residual-context")
    if sha(actual_prepared) != prepared_ref["sha256"]:
        raise RuntimeError("Fresh prepared-state readback differs from preparation pair")
    uids = [prep["target"]["uids"][kind] for kind in ("video", "audio")]
    cut1 = prep["target"]["splitPlayheadTimecode"]
    first_selection, _, ready1 = select_linked(
        native, directory, case, "first", prep_ref, prepared_ref, uids, cut1,
        preparation=prep, cases=cases, reader=reader, probe=probe,
    )
    if (ready1.get("status") != "split-ready" or ready1.get("stage") != "first" or ready1.get("selectedUids") != uids or ready1.get("splitFrame") != 4560 or ready1.get("menuCommandDispatched") is not False):
        raise RuntimeError("First split-ready guard refused")
    save(directory, "first-split-ready.json", ready1)
    native.invoke(menu="split")
    first_read_ref, first_read, first_pair_path, first_sha = readback(native, directory, "r2-residual-first-split")
    if first_read["selectionPasses"][0].get("playhead") != cut1:
        raise RuntimeError("First split readback missed frame 4560")
    first_pair = json.loads(first_pair_path.read_text(encoding="utf-8"))
    first_state, first_pool = reader._validate_read_pair(first_pair, probe)
    first_children = cases._named_linked_children(
        prep, prepared_state, prepared_pool, first_state, first_pool, reader, case, "first"
    )
    first_proof = {
        "status": "local-first-split-proof",
        "case": case,
        "preparationResult": prep_ref,
        "firstSplitPair": {"path": str(first_pair_path.resolve().relative_to(OUT.resolve())), "sha256": first_sha},
        "childUids": {kind: [item["GetUniqueId"]["value"] for item in rows] for kind, rows in first_children.items()},
        "ranges": [[4500, 4560, 0, 60], [4560, 4699, 60, 199]],
        "saveDispatched": False,
        "menuCommandDispatched": False,
        "proof": "_named_linked_children exact complete timeline/pool derivation",
    }
    save(directory, "first-split-local-proof.json", first_proof)
    position = native.invoke({
        "action": "r2-linked-second-position", "case": case,
        "preparationResult": prep_ref["path"], "preparationResultSha256": prep_ref["sha256"],
        "firstSplitPair": str(first_pair_path.resolve().relative_to(OUT.resolve())), "firstSplitPairSha256": first_sha,
    })
    position_ref, position = save(directory, "second-position.json", position)
    if position.get("status") != "second-position-ready" or position.get("case") != case or position.get("target", {}).get("splitFrame") != 4570 or position.get("menuCommandDispatched") is not False:
        raise RuntimeError("Second-position guard refused")
    position_pair = position.get("secondPositionPair", {})
    position_pair_path = bound_path(position_pair)
    position_pair_value = json.loads(position_pair_path.read_text(encoding="utf-8"))
    position_state, position_pool = reader._validate_read_pair(position_pair_value, probe)
    if (position_state != first_state or position_pool != first_pool
            or position.get("target", {}).get("firstSplitUids") != {
                kind: [item["GetUniqueId"]["value"] for item in rows]
                for kind, rows in first_children.items()
            }):
        raise RuntimeError("Second-position readback does not bind the first split")
    second_uids = position.get("target", {}).get("firstSplitUids", {})
    ordered_second = [second_uids[kind][1] for kind in ("video", "audio")]
    second_selection, _, ready2 = select_linked(
        native, directory, case, "second", prep_ref, position_pair, ordered_second,
        "00:03:02:20", position_ref,
        {"path": str(first_pair_path.resolve().relative_to(OUT.resolve())), "sha256": first_sha},
        preparation=prep, cases=cases, reader=reader, probe=probe,
    )
    if ready2.get("status") != "split-ready" or ready2.get("stage") != "second" or ready2.get("selectedUids") != ordered_second or ready2.get("splitFrame") != 4570 or ready2.get("menuCommandDispatched") is not False:
        raise RuntimeError("Second split-ready guard refused")
    save(directory, "second-split-ready.json", ready2)
    native.invoke(menu="split")
    second_read_ref, second_read, second_pair_path, second_sha = readback(native, directory, "r2-residual-second-split")
    if second_read["selectionPasses"][0].get("playhead") != "00:03:02:20":
        raise RuntimeError("Second split readback missed frame 4570")
    second_pair = json.loads(second_pair_path.read_text(encoding="utf-8"))
    second_state, second_pool = reader._validate_read_pair(second_pair, probe)
    second_children = cases._named_linked_children(
        prep, first_state, first_pool, second_state, second_pool, reader, case, "second"
    )
    review2 = native.invoke({
        "action": "r2-named-split-review", "case": case,
        "preparationResult": prep_ref["path"], "preparationResultSha256": prep_ref["sha256"],
        "firstSelectionResult": first_selection["path"], "firstSelectionResultSha256": first_selection["sha256"],
        "firstSplitPair": str(first_pair_path.resolve().relative_to(OUT.resolve())), "firstSplitPairSha256": first_sha,
        "secondPositionResult": position_ref["path"], "secondPositionResultSha256": position_ref["sha256"],
        "selectionResult": second_selection["path"], "selectionResultSha256": second_selection["sha256"],
        "secondSplitPair": str(second_pair_path.resolve().relative_to(OUT.resolve())), "secondSplitPairSha256": second_sha,
        "stage": "second",
    })
    review2_ref, review2 = save(directory, "second-split-review.json", review2)
    if (review2.get("status") != "split-readback-retained"
            or review2.get("saveDispatched") is not False
            or review2.get("childUids") != {
                kind: [item["GetUniqueId"]["value"] for item in rows]
                for kind, rows in second_children.items()
            }
            or review2.get("ranges") != [[4500, 4560, 0, 60], [4560, 4570, 60, 70], [4570, 4699, 70, 199]]):
        raise RuntimeError("Second split full-state review refused")
    # The audited interval-delete action requires the exact guarded selected IDs.
    for menu in ("auto-none", "auto-v1", "auto-a1"):
        native.invoke(menu=menu)
    native.invoke(menu="deselect")
    readback(native, directory, "r2-residual-deselected")
    native.invoke(menu="select")
    interval_selected_ref, interval_selected, _, interval_selected_sha = readback(native, directory, "r2-residual-interval-selected")
    expected_interval_uids = [second_children[kind][1]["GetUniqueId"]["value"] for kind in ("video", "audio")]
    selected_passes = interval_selected.get("selectionPasses", [])
    selected_ids = [x.get("GetUniqueId", {}).get("value") for x in (selected_passes[0].get("items", []) if selected_passes else [])]
    if interval_selected_sha != second_sha or len(selected_passes) != 2 or selected_ids != expected_interval_uids or selected_passes[1].get("items") != selected_passes[0].get("items"):
        raise RuntimeError("Interval selection did not bind the exact linked residual IDs")
    cases._selected_uids(
        reader,
        OUT,
        probe,
        {"selectionResult": interval_selected_ref["path"], "selectionResultSha256": interval_selected_ref["sha256"]},
        second_pair,
        second_sha,
        "r2-residual-interval-selected",
        cases._linked_selection_targets(
            prep,
            {kind: second_children[kind][1]["GetUniqueId"]["value"] for kind in ("video", "audio")},
        ),
    )
    delete = native.invoke({
        "action": "r2-linked-interval-delete", "case": case,
        "preparationResult": prep_ref["path"], "preparationResultSha256": prep_ref["sha256"],
        "firstSplitPair": str(first_pair_path.resolve().relative_to(OUT.resolve())), "firstSplitPairSha256": first_sha,
        "secondPositionResult": position_ref["path"], "secondPositionResultSha256": position_ref["sha256"],
        "secondSplitPair": str(second_pair_path.resolve().relative_to(OUT.resolve())), "secondSplitPairSha256": second_sha,
        "selectionResult": interval_selected_ref["path"], "selectionResultSha256": interval_selected_ref["sha256"],
    })
    delete_ref, delete = save(directory, "interval-delete.json", delete)
    if delete.get("status") != "interval-deleted-unsaved" or delete.get("saveDispatched") is not False:
        raise RuntimeError("Guarded non-ripple interval delete failed; retain evidence and stop")
    deleted_pair = delete.get("afterPair", {})
    bound_path(deleted_pair)
    _, deleted_read, deleted_pair_path, deleted_sha = readback(native, directory, "r2-residual-deleted")
    if deleted_sha != deleted_pair["sha256"]:
        raise RuntimeError("Fresh deleted-state readback differs from guarded delete result")
    restored = native.invoke({
        "action": "editorial-case-restore", "case": case,
        "preparationResult": prep_ref["path"], "preparationResultSha256": prep_ref["sha256"],
        "postEditPair": deleted_pair["path"], "postEditPairSha256": deleted_pair["sha256"],
    })
    restore_ref, restored = save(directory, "restoration.json", restored)
    if restored.get("status") != "restored-unsaved" or restored.get("originalLocks") != prep.get("originalLocks") or restored.get("originalPlayhead") != prep.get("originalPlayhead") or restored.get("saveDispatched") is not False:
        raise RuntimeError("Own lock/playhead context restoration failed; retain evidence")
    for menu in ("auto-none", "auto-v1", "auto-a1"):
        native.invoke(menu=menu)
    native.invoke(menu="deselect")
    final_ref, final_read, final_pair_path, final_sha = readback(native, directory, "r2-residual-context")
    restored_pair = restored.get("restoredPair", {})
    final_passes = final_read.get("selectionPasses", [])
    if (final_sha != restored_pair.get("sha256")
            or len(final_passes) != 2
            or any(row.get("items") != [] or row.get("playhead") != prep.get("originalPlayhead")
                   for row in final_passes)):
        raise RuntimeError("Final full-state pair differs from recorded restoration")
    evidence = [{"path": str(path.resolve().relative_to(OUT.resolve())), "sha256": sha(path)} for path in sorted(directory.glob("*.json"))]
    return {"status": "complete", "case": case, "directory": str(directory), "pins": PINS, "evidence": evidence,
            "priorPair": {"path": relative, "sha256": digest}, "preparation": prep_ref,
            "firstSelection": first_selection, "firstSplit": first_read_ref, "firstReview": None,
            "secondPosition": position_ref, "secondSelection": second_selection, "secondSplit": second_read_ref,
            "secondReview": review2_ref, "intervalSelection": interval_selected_ref,
            "intervalDelete": delete_ref, "deletedReadback": {"path": str(deleted_pair_path.resolve().relative_to(OUT.resolve())), "sha256": deleted_sha},
            "restoration": restore_ref, "finalReadback": final_ref, "finalPairSha256": final_sha,
            "saveDispatched": False}


def run_resume_sequence(relative, digest, resume_relative, resume_digest, *, native=None,
                        position_relative=None, position_digest=None):
    prior_path, _ = contained_prior(relative, digest)
    resume_path, resume_record = contained_record(resume_relative, resume_digest)
    if resume_record.get("status") != "residual-resume-authorized" or resume_record.get("case") != "R2-residual":
        raise ValueError("Resume record is not the retained R2-residual authorization")
    sources = pin_sources()
    native = native or load("independent_native_call", sources["independent-native-call.py"])
    cases = load("residual_editorial_cases", sources["editorial-cases.py"])
    probe = load("residual_probe", sources["probe.py"])
    reader = cases._reader(probe)
    case = "R2-residual"
    directory = OUT / datetime.now(UTC).strftime("independent-residual-resume-%Y%m%dT%H%M%S.%fZ")
    directory.mkdir()
    resume_ref = {
        "path": str(resume_path.resolve().relative_to(OUT.resolve())),
        "sha256": resume_digest,
    }
    initial = None if position_relative else native.invoke({
        "action": "editorial-case-prepare", "case": case,
        "priorPair": str(prior_path.resolve().relative_to(OUT.resolve())), "priorPairSha256": digest,
        "residualResumeRecord": resume_ref["path"], "residualResumeRecordSha256": resume_ref["sha256"],
        "preparationResult": None, "preparationResultSha256": None,
        "firstSplitPair": None, "firstSplitPairSha256": None,
        "firstSelectionResult": None, "firstSelectionResultSha256": None,
        "selectionResult": None, "selectionResultSha256": None,
    })
    if position_relative:
        if position_digest != "cdd615061aed1e3fd7d5136d4732d27f26ec500a3ec24fab0991d3dfcea03a93":
            raise ValueError("Unreviewed position checkpoint hash")
        position_checkpoint_path, checkpoint = contained_record(position_relative, position_digest)
        if (checkpoint.get("schema") != "issue141-residual-position-continuation/v1"
                or checkpoint.get("case") != case
                or checkpoint.get("resumeRecord") != resume_ref
                or checkpoint.get("priorTerminal", {}).get("path") != "residual-resume-native-executor-result.json"):
            raise ValueError("Position checkpoint does not bind this R2-residual resume")
        for field in ("preparation", "position", "priorTerminal"):
            bound_path(checkpoint[field])
        prep_ref = checkpoint["preparation"]
        _, prep = contained_record(prep_ref["path"], prep_ref["sha256"])
        position_ref = checkpoint["position"]
        _, position = contained_record(position_ref["path"], position_ref["sha256"])
        if (prep.get("status") != "case-prepared" or prep.get("case") != case
                or prep.get("resumedFirstSplit") is None
                or prep.get("resumedFirstSplit", {}).get("record") != resume_ref
                or prep.get("resumedFirstSplit", {}).get("selection") != resume_record["firstSelection"]
                or position.get("status") != "second-position-ready" or position.get("case") != case
                or position.get("preparationResult") != prep_ref
                or position.get("playheadAfter") != "00:03:02:20"
                or position.get("target", {}).get("splitFrame") != 4570
                or position.get("target", {}).get("firstSplitUids") != prep.get("resumedFirstSplit", {}).get("childUids")
                or position.get("menuCommandDispatched") is not False):
            raise ValueError("Retained preparation/position checkpoint metadata differs")
        first_current_ref = prep["preparedPair"]
        position_pair_ref = position["secondPositionPair"]
        if position_pair_ref.get("sha256") != first_current_ref.get("sha256"):
            raise ValueError("Retained position pair differs from prepared first-split pair")
        pair = json.loads(bound_path(position_pair_ref).read_text(encoding="utf-8"))
        fresh_ref, fresh_read, fresh_path, fresh_sha = readback(native, directory, "r2-residual-context")
        if fresh_sha != prep["preparedPair"]["sha256"]:
            raise RuntimeError("Fresh read-only context differs from retained preparation pair")
        passes = fresh_read.get("selectionPasses", [])
        if len(passes) != 2 or any(row.get("playhead") != "00:03:02:20" or row.get("items") for row in passes):
            raise ValueError("Fresh context is not empty at the approved second-position playhead")
        prep_ref = {"path": str(prep_ref["path"]), "sha256": prep_ref["sha256"]}
        first_current_path = bound_path(first_current_ref)
        first_current_pair = cases._r2_pin(reader, OUT, first_current_ref["path"], first_current_ref["sha256"], probe,
                                            "retained current first-split pair")
        first_state, first_pool = reader._validate_read_pair(first_current_pair, probe)
        first_children = cases._named_linked_children(prep, first_state, first_pool, first_state, first_pool, reader, case, "first")
        first_proof_ref, _ = save(directory, "retained-first-split-proof.json", {
            "status": "retained-first-split-proof", "case": case,
            "preparationResult": prep_ref, "firstSplitPair": first_current_ref,
            "positionCheckpoint": {"path": position_relative, "sha256": position_digest},
            "childUids": {kind: [item["GetUniqueId"]["value"] for item in rows]
                          for kind, rows in first_children.items()},
            "menuCommandDispatched": False,
        })
        # Checkpoint's historical resume metadata is authoritative; keep its genuine selection.
        first_selection_ref = resume_record["firstSelection"]
        position_pair_path = bound_path(position_pair_ref)
        position_state, position_pool = reader._validate_read_pair(pair, probe)
    else:
        prep_ref, prep = save(directory, "preparation.json", initial)
    if not position_relative and (prep.get("status") != "case-prepared" or prep.get("case") != case or prep.get("resumedFirstSplit") is None):
        raise RuntimeError("R2-residual resume preparation refused")
    if not position_relative:
        first_current_ref = prep.get("preparedPair", {})
        first_current_path = bound_path(first_current_ref)
        first_current_pair = cases._r2_pin(
            reader, OUT, first_current_ref["path"], first_current_ref["sha256"], probe,
            "resumed current first-split pair",
        )
        first_state, first_pool = reader._validate_read_pair(first_current_pair, probe)
        first_children = cases._named_linked_children(
            prep, first_state, first_pool, first_state, first_pool, reader, case, "first"
        )
        first_proof_ref, _ = save(directory, "resumed-first-split-proof.json", {
            "status": "resumed-first-split-proof",
            "case": case,
            "resumeRecord": resume_ref,
            "preparationResult": prep_ref,
            "firstSplitPair": first_current_ref,
            "childUids": {
                kind: [item["GetUniqueId"]["value"] for item in rows]
                for kind, rows in first_children.items()
            },
            "ranges": [[4500, 4560, 0, 60], [4560, 4699, 60, 199]],
            "offsetDeltaOnly": True,
            "saveDispatched": False,
            "menuCommandDispatched": False,
        })
        position = native.invoke({
            "action": "r2-linked-second-position", "case": case,
            "preparationResult": prep_ref["path"], "preparationResultSha256": prep_ref["sha256"],
            "firstSplitPair": first_current_ref["path"], "firstSplitPairSha256": first_current_ref["sha256"],
        })
        position_ref, position = save(directory, "second-position.json", position)
        if position.get("status") != "second-position-ready" or position.get("case") != case or position.get("target", {}).get("splitFrame") != 4570 or position.get("menuCommandDispatched") is not False:
            raise RuntimeError("Resumed second-position guard refused")
        position_pair_ref = position.get("secondPositionPair", {})
        position_pair_path = bound_path(position_pair_ref)
        position_pair = cases._r2_pin(
            reader, OUT, position_pair_ref["path"], position_pair_ref["sha256"], probe,
            "resumed second-position pair",
        )
        position_state, position_pool = reader._validate_read_pair(position_pair, probe)
        if position_state != first_state or position_pool != first_pool:
            raise RuntimeError("Resumed second-position readback changed the first split")
    second_uids = position.get("target", {}).get("firstSplitUids", {})
    ordered_second = [second_uids[kind][1] for kind in ("video", "audio")]
    if not position_relative:
        first_selection_ref = resume_record["firstSelection"]
    second_selection, _, ready2 = select_linked(
        native, directory, case, "second", prep_ref, position_pair_ref, ordered_second,
        "00:03:02:20", position_ref, first_current_ref,
        preparation=prep, cases=cases, reader=reader, probe=probe,
    )
    if ready2.get("status") != "split-ready" or ready2.get("stage") != "second" or ready2.get("selectedUids") != ordered_second or ready2.get("splitFrame") != 4570 or ready2.get("menuCommandDispatched") is not False:
        raise RuntimeError("Resumed second split-ready guard refused")
    save(directory, "second-split-ready.json", ready2)
    native.invoke(menu="split")
    second_read_ref, second_read, second_pair_path, second_sha = readback(native, directory, "r2-residual-second-split")
    if second_read["selectionPasses"][0].get("playhead") != "00:03:02:20":
        raise RuntimeError("Resumed second split readback missed frame 4570")
    second_pair = json.loads(second_pair_path.read_text(encoding="utf-8"))
    second_state, second_pool = reader._validate_read_pair(second_pair, probe)
    second_children = cases._named_linked_children(
        prep, first_state, first_pool, second_state, second_pool, reader, case, "second"
    )
    review2 = native.invoke({
        "action": "r2-named-split-review", "case": case,
        "preparationResult": prep_ref["path"], "preparationResultSha256": prep_ref["sha256"],
        "firstSelectionResult": first_selection_ref["path"], "firstSelectionResultSha256": first_selection_ref["sha256"],
        "firstSplitPair": first_current_ref["path"], "firstSplitPairSha256": first_current_ref["sha256"],
        "secondPositionResult": position_ref["path"], "secondPositionResultSha256": position_ref["sha256"],
        "selectionResult": second_selection["path"], "selectionResultSha256": second_selection["sha256"],
        "secondSplitPair": str(second_pair_path.resolve().relative_to(OUT.resolve())), "secondSplitPairSha256": second_sha,
        "stage": "second",
    })
    review2_ref, review2 = save(directory, "second-split-review.json", review2)
    if (review2.get("status") != "split-readback-retained" or review2.get("saveDispatched") is not False
            or review2.get("childUids") != {kind: [item["GetUniqueId"]["value"] for item in rows] for kind, rows in second_children.items()}
            or review2.get("ranges") != [[4500, 4560, 0, 60], [4560, 4570, 60, 70], [4570, 4699, 70, 199]]):
        raise RuntimeError("Resumed second split full-state review refused")
    for menu in ("auto-none", "auto-v1", "auto-a1"):
        native.invoke(menu=menu)
    native.invoke(menu="deselect")
    readback(native, directory, "r2-residual-deselected")
    native.invoke(menu="select")
    interval_selected_ref, interval_selected, _, interval_selected_sha = readback(native, directory, "r2-residual-interval-selected")
    expected_interval_uids = [second_children[kind][1]["GetUniqueId"]["value"] for kind in ("video", "audio")]
    selected_passes = interval_selected.get("selectionPasses", [])
    selected_ids = [x.get("GetUniqueId", {}).get("value") for x in (selected_passes[0].get("items", []) if selected_passes else [])]
    if interval_selected_sha != second_sha or len(selected_passes) != 2 or selected_ids != expected_interval_uids or selected_passes[1].get("items") != selected_passes[0].get("items"):
        raise RuntimeError("Resumed interval selection did not bind exact linked IDs")
    cases._selected_uids(
        reader, OUT, probe,
        {"selectionResult": interval_selected_ref["path"], "selectionResultSha256": interval_selected_ref["sha256"]},
        second_pair, second_sha, "r2-residual-interval-selected",
        cases._linked_selection_targets(prep, {kind: second_children[kind][1]["GetUniqueId"]["value"] for kind in ("video", "audio")}),
    )
    delete = native.invoke({
        "action": "r2-linked-interval-delete", "case": case,
        "preparationResult": prep_ref["path"], "preparationResultSha256": prep_ref["sha256"],
        "firstSplitPair": first_current_ref["path"], "firstSplitPairSha256": first_current_ref["sha256"],
        "secondPositionResult": position_ref["path"], "secondPositionResultSha256": position_ref["sha256"],
        "secondSplitPair": str(second_pair_path.resolve().relative_to(OUT.resolve())), "secondSplitPairSha256": second_sha,
        "selectionResult": interval_selected_ref["path"], "selectionResultSha256": interval_selected_ref["sha256"],
    })
    delete_ref, delete = save(directory, "interval-delete.json", delete)
    if delete.get("status") != "interval-deleted-unsaved" or delete.get("saveDispatched") is not False:
        raise RuntimeError("Resumed guarded interval delete failed; retain evidence and stop")
    deleted_pair = delete.get("afterPair", {})
    bound_path(deleted_pair)
    _, deleted_read, deleted_pair_path, deleted_sha = readback(native, directory, "r2-residual-deleted")
    if deleted_sha != deleted_pair["sha256"]:
        raise RuntimeError("Resumed deleted-state readback differs from delete result")
    restored = native.invoke({
        "action": "editorial-case-restore", "case": case,
        "preparationResult": prep_ref["path"], "preparationResultSha256": prep_ref["sha256"],
        "postEditPair": deleted_pair["path"], "postEditPairSha256": deleted_pair["sha256"],
    })
    restore_ref, restored = save(directory, "restoration.json", restored)
    if restored.get("status") != "restored-unsaved" or restored.get("originalLocks") != prep.get("originalLocks") or restored.get("originalPlayhead") != prep.get("originalPlayhead") or restored.get("saveDispatched") is not False:
        raise RuntimeError("Resumed lock/playhead restoration failed; retain evidence")
    for menu in ("auto-none", "auto-v1", "auto-a1"):
        native.invoke(menu=menu)
    native.invoke(menu="deselect")
    final_ref, final_read, final_pair_path, final_sha = readback(native, directory, "r2-residual-context")
    restored_pair = restored.get("restoredPair", {})
    final_passes = final_read.get("selectionPasses", [])
    if final_sha != restored_pair.get("sha256") or len(final_passes) != 2 or any(row.get("items") != [] or row.get("playhead") != prep.get("originalPlayhead") for row in final_passes):
        raise RuntimeError("Resumed final full-state pair differs from restoration")
    evidence = [{"path": str(path.resolve().relative_to(OUT.resolve())), "sha256": sha(path)} for path in sorted(directory.glob("*.json"))]
    return {
        "status": "complete",
        "case": case,
        "resumeRecord": resume_ref,
        "alreadyCompletedSkipped": ["preparation", "first-cut", "position"] if position_relative else [],
        "directory": str(directory),
        "pins": PINS,
        "evidence": evidence,
        "priorPair": {"path": relative, "sha256": digest},
        "preparation": prep_ref,
        "resumedFirstSplitProof": first_proof_ref,
        "firstSplit": first_current_ref,
        "firstSelection": first_selection_ref,
        "secondPosition": position_ref,
        "secondSelection": second_selection,
        "secondSplit": second_read_ref,
        "secondReview": review2_ref,
        "intervalSelection": interval_selected_ref,
        "intervalDelete": delete_ref,
        "deletedReadback": {"path": str(deleted_pair_path.resolve().relative_to(OUT.resolve())), "sha256": deleted_sha},
        "restoration": restore_ref,
        "finalReadback": final_ref,
        "finalPairSha256": final_sha,
        "saveDispatched": False,
    }


def check():
    sources = pin_sources(native=False)
    checker = load("residual_fake_checker", sources["editorial-cases-check.py"])
    # Exercise this driver's own stage validators with fake checker outputs.
    pass_result, store = checker.run_case("R2-residual", named_sequence=True, held_context=True)
    assert pass_result["firstReady"]["status"] == "split-ready"
    assert pass_result["position"]["status"] == "second-position-ready"
    assert pass_result["secondReady"]["status"] == "split-ready"
    assert pass_result["review"]["ranges"] == [[4500,4560,0,60],[4560,4570,60,70],[4570,4699,70,199]]
    assert pass_result["delete"]["status"] == "interval-deleted-unsaved" and pass_result["restore"]["status"] == "restored-unsaved"
    assert pass_result["restore"]["originalPlayhead"] == "00:01:30:00"
    assert store.playhead == "00:01:30:00"
    assert all(
        row["GetIsTrackLocked"]["value"] == ((row["type"], row["index"]) in checker.module.LOCKS)
        for row in store.matrix_state()["tracks"]
    )
    assert next(i for t in store.matrix_state()["tracks"] if t["type"]=="audio" and t["index"]==2 for i in t["items"] if i["GetUniqueId"]["value"]=="residual-a2")["GetClipEnabled"] == {"value":True}
    refuse, refused_store = checker.run_case("R2-residual", named_sequence=True, phase_mode="wrong-first-selection-id")
    assert "first_ready_refusal" in refuse and "selected UIDs" in refuse["first_ready_refusal"]
    assert not any(call[0] == "Razor" for call in refused_store.calls)
    readback = load("residual_actual_readback", HERE / "editorial-readback.py")
    assert all(label in readback.LABELS for stage in ("first", "second") for label in _selection_labels(stage))
    assert "r2-residual-second-deselected" not in readback.LABELS
    print("R2-residual orchestration fake pass and pre-split wrong-selection refusal pass; no native action.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="fake-only local check")
    group.add_argument("--run", action="store_true", help="guarded native sequence; requires separate authorization")
    parser.add_argument("--prior-pair")
    parser.add_argument("--prior-sha256")
    parser.add_argument("--resume-record")
    parser.add_argument("--resume-sha256")
    parser.add_argument("--position-record")
    parser.add_argument("--position-sha256")
    args = parser.parse_args(argv)
    if args.check:
        if args.prior_pair or args.prior_sha256 or args.resume_record or args.resume_sha256 or args.position_record or args.position_sha256:
            parser.error("--check takes no native checkpoint arguments")
        check()
        return 0
    if not args.prior_pair or not args.prior_sha256:
        parser.error("--run requires --prior-pair and --prior-sha256")
    if bool(args.resume_record) != bool(args.resume_sha256):
        parser.error("--resume-record and --resume-sha256 must be supplied together")
    if bool(args.position_record) != bool(args.position_sha256):
        parser.error("--position-record and --position-sha256 must be supplied together")
    if args.position_record and not args.resume_record:
        parser.error("--position-record requires the retained resume record")
    result = (
        run_resume_sequence(args.prior_pair, args.prior_sha256, args.resume_record, args.resume_sha256,
                            position_relative=args.position_record, position_digest=args.position_sha256)
        if args.resume_record
        else run_sequence(args.prior_pair, args.prior_sha256)
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    sys.exit(main())
