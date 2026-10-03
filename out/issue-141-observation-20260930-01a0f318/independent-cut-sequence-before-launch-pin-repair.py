"""Guarded R2 single-track cut sequences; --check never contacts Resolve."""

import argparse
import importlib.util
import hashlib
import json
import re
import sys
import tempfile
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

SCRIPT_OUT = Path(__file__).resolve().parent
OUT = SCRIPT_OUT
ROOT = OUT.parents[1]
HERE = ROOT / "docs/investigations/issue-141"
SINGLE_CASES = ("R2-unlinked", "R2-picture", "R2-partial")
CASES_SHA256 = "1e1c2685de795bdc60ffa806c0fde10d75e300340fc2c1178b8ccf4d1a93f372"
CHECK_SHA256 = "0da0fb622bdadd33bb50510fdcc36680ad2dc4b88795d697348febd7bbb9dde2"
PROBE_SHA256 = "64a9c91da7093382f52d3ba1178d87d36fc10709276f93f383f6bec701b1eef2"
NATIVE_CALL_SHA256 = "3b20292b7e2cebdf0ec968a993fab20ce8146fd9396beb522d2c1da4e59c5c46"


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
    if case not in SINGLE_CASES:
        raise ValueError("Only supported R2 single-track cases are permitted")
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
            raise ValueError("Prior pair may not link or escape the approved output")
    if not path.is_file() or _sha(path) != digest:
        raise ValueError("Prior pair is missing or its SHA-256 differs")
    pair = json.loads(path.read_text())
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
    pair = result.get("pair", {})
    pair_path = Path(pair.get("path", ""))
    if (
        pair_path.is_symlink()
        or not pair_path.is_file()
        or not pair_path.resolve().is_relative_to(OUT.resolve())
        or _sha(pair_path) != pair.get("sha256")
    ):
        raise RuntimeError(f"{label} full-state pair pin is invalid")
    ref, clean = _save(directory, label + ".json", result)
    return ref, clean, pair_path, pair["sha256"]


def _single_targets(cases, preparation, uids):
    case = preparation["case"]
    track = cases.R2_SINGLE[case]["track"]
    return [
        (
            track,
            1,
            uids[track],
            preparation["target"]["sourceUids"][track],
            [],
        )
    ]


def _single_readback(native, directory, case, stage):
    return _readback(native, directory, f"r2-{case.removeprefix('R2-').lower()}-{stage}")


def _single_select(native, cases, reader, probe, directory, case, stage, preparation,
                   uids, expected_pair, expected_sha, playhead):
    track = cases.R2_SINGLE[case]["track"]
    native.invoke(menu="auto-none")
    native.invoke(menu="auto-a1" if track == "audio" else "auto-v1")
    native.invoke(menu="deselect")
    deselected_ref, deselected, _, deselected_sha = _single_readback(
        native, directory, case, "deselected" if stage == "first" else "second-position"
    )
    if (
        deselected_sha != expected_sha
        or any(row.get("items") for row in deselected.get("selectionPasses", []))
        or deselected["selectionPasses"][0].get("playhead") != playhead
    ):
        raise RuntimeError(f"{case} deselect changed state or missed its cut point")
    native.invoke(menu="select")
    label = (
        f"r2-{case.removeprefix('R2-').lower()}-selected"
        if stage == "first"
        else f"r2-{case.removeprefix('R2-').lower()}-second-selected"
    )
    selected_ref, selected, selected_pair_path, selected_sha = _single_readback(
        native, directory, case, "selected" if stage == "first" else "second-selected"
    )
    selection_pair = json.loads(selected_pair_path.read_text())
    selection = cases._selected_uids(
        reader,
        OUT,
        probe,
        {
            "selectionResult": selected_ref["path"],
            "selectionResultSha256": selected_ref["sha256"],
        },
        expected_pair,
        expected_sha,
        label,
        _single_targets(cases, preparation, uids),
    )
    if (
        selected_sha != expected_sha
        or selected["selectionPasses"][0].get("playhead") != playhead
        or len(selection) != 1
    ):
        raise RuntimeError(f"{case} single-track selected readback changed")
    return deselected_ref, selected_ref, selected, selection_pair


def run_sequence(case, prior_pair, prior_sha, *, native=None, cases_module=None,
                 probe_obj=None, reader_obj=None, check_sources=True,
                 reviewed_preparation=None, reviewed_preparation_sha=None):
    if case not in SINGLE_CASES:
        raise ValueError("Only R2-unlinked, R2-picture, and R2-partial may run")
    prior = _boundary(case, prior_pair, prior_sha)
    if check_sources:
        for source, expected in (
            (HERE / "editorial-cases.py", CASES_SHA256),
            (HERE / "editorial-cases-check.py", CHECK_SHA256),
            (HERE / "probe.py", PROBE_SHA256),
            (SCRIPT_OUT / "independent-native-call.py", NATIVE_CALL_SHA256),
        ):
            if source.is_symlink() or _sha(source) != expected:
                raise RuntimeError(f"Pinned editorial source changed: {source.name}")
    native = native or _load(
        "independent_native_call", SCRIPT_OUT / "independent-native-call.py"
    )
    cases = cases_module or _load("editorial_cases", HERE / "editorial-cases.py")
    probe = probe_obj or _load("issue141_probe", HERE / "probe.py")
    reader = reader_obj or cases._reader(probe)
    directory = OUT / datetime.now(UTC).strftime(
        "independent-cut-sequence-%Y%m%dT%H%M%S.%fZ"
    )
    directory.mkdir()
    cleared = {
        "preparationResult": None,
        "preparationResultSha256": None,
        "firstSplitPair": None,
        "firstSplitPairSha256": None,
        "secondSplitPair": None,
        "secondSplitPairSha256": None,
        "secondPositionResult": None,
        "secondPositionResultSha256": None,
        "selectionResult": None,
        "selectionResultSha256": None,
        "firstSelectionResult": None,
        "firstSelectionResultSha256": None,
    }
    if reviewed_preparation is None:
        if reviewed_preparation_sha is not None:
            raise ValueError("A reviewed preparation path is required with its SHA-256")
        prep_result = native.invoke({
            "action": "editorial-case-prepare",
            "case": case,
            "priorPair": str(prior.resolve().relative_to(OUT.resolve())),
            "priorPairSha256": prior_sha,
            **cleared,
        })
    else:
        if (
            not isinstance(reviewed_preparation, str)
            or not reviewed_preparation
            or Path(reviewed_preparation).is_absolute()
            or not isinstance(reviewed_preparation_sha, str)
            or not re.fullmatch(r"[0-9a-f]{64}", reviewed_preparation_sha)
        ):
            raise ValueError("Reviewed preparation requires a contained path and SHA-256")
        reviewed_path = OUT / reviewed_preparation
        cursor = OUT
        for part in Path(reviewed_preparation).parts:
            if part in {"", ".", ".."}:
                raise ValueError("Reviewed preparation may not traverse output")
            cursor /= part
            if cursor.is_symlink() or not cursor.resolve().is_relative_to(OUT.resolve()):
                raise ValueError("Reviewed preparation escapes or links outside output")
        if not reviewed_path.is_file() or _sha(reviewed_path) != reviewed_preparation_sha:
            raise ValueError("Reviewed preparation is missing or changed from its pin")
        prep_result = json.loads(reviewed_path.read_text())
        if (
            prep_result.get("status") != "case-prepared"
            or prep_result.get("case") != case
            or prep_result.get("reviewOnly") is not True
            or prep_result.get("priorPair", {}).get("path")
            != str(prior.resolve().relative_to(OUT.resolve()))
            or prep_result.get("priorPair", {}).get("sha256") != prior_sha
            or not isinstance(prep_result.get("reviewedFrom"), dict)
        ):
            raise RuntimeError("Reviewed preparation does not bind the requested case and prior pair")
    prep_ref, preparation = _save(directory, "preparation.json", prep_result)
    prep_path, prep_sha = prep_ref["path"], prep_ref["sha256"]
    if preparation.get("status") != "case-prepared" or preparation.get("case") != case:
        raise RuntimeError(f"{case} preparation did not validate")
    prepared_ref = preparation.get("preparedPair", {})
    prepared_path = OUT / prepared_ref.get("path", "")
    _, prepared_state = _pin_prepared(reader, prepared_path, prepared_ref, probe)
    _, split_frame, split_tc = (
        cases.R2_SINGLE[case]["track"],
        cases.CASES[case]["start"] + cases.R2_SINGLE[case]["cutStart"],
        preparation["target"]["splitPlayheadTimecode"],
    )
    if preparation["target"].get("splitPlayheadFrame") != split_frame:
        raise RuntimeError(f"{case} preparation cut frame changed")
    _, first_selected_ref, _selected, prepared_pair = _single_select(
        native,
        cases,
        reader,
        probe,
        directory,
        case,
        "first",
        preparation,
        preparation["target"]["uids"],
        json.loads(prepared_path.read_text()),
        prepared_ref["sha256"],
        split_tc,
    )
    native.invoke(menu="split")
    first_ref, _first_readback, first_pair_path, first_sha = _single_readback(
        native, directory, case, "first-split"
    )
    if _first_readback["selectionPasses"][0].get("playhead") != split_tc:
        raise RuntimeError(f"{case} first split readback missed the cut point")
    first_pair = json.loads(first_pair_path.read_text())
    first_state, first_pool = reader._validate_read_pair(first_pair, probe)
    _, prepared_pool = reader._validate_read_pair(prepared_pair, probe)
    _parent, children = cases._single_first_split(
        preparation,
        prepared_state,
        first_state,
        first_pool,
        prepared_pool,
        reader,
        case,
    )
    first_split_uid = children[1]["GetUniqueId"]["value"]
    position_result = native.invoke({
        "action": "r2-linked-second-position",
        "case": case,
        "preparationResult": prep_path,
        "preparationResultSha256": prep_sha,
        "firstSplitPair": str(first_pair_path.resolve().relative_to(OUT.resolve())),
        "firstSplitPairSha256": first_sha,
    })
    position_ref, position = _save(directory, "second-position.json", position_result)
    target_frame = cases.CASES[case]["start"] + cases.R2_SINGLE[case]["cutEnd"]
    target_tc = cases._timecode(target_frame)
    if (
        position.get("status") != "second-position-ready"
        or position.get("target", {}).get("splitFrame") != target_frame
        or position.get("target", {}).get("timecode") != target_tc
        or position.get("target", {}).get("secondSplitUid") != first_split_uid
    ):
        raise RuntimeError(f"{case} second-position result changed")
    right_uids = {
        cases.R2_SINGLE[case]["track"]: position["target"]["secondSplitUid"]
    }
    _, second_selected_ref, _selected, _ = _single_select(
        native,
        cases,
        reader,
        probe,
        directory,
        case,
        "second",
        preparation,
        right_uids,
        first_pair,
        first_sha,
        target_tc,
    )
    native.invoke(menu="split")
    second_ref, _second_readback, second_pair_path, second_sha = _single_readback(
        native, directory, case, "second-split"
    )
    if _second_readback["selectionPasses"][0].get("playhead") != target_tc:
        raise RuntimeError(f"{case} second split readback missed the cut point")
    delete_result = native.invoke({
        "action": "r2-linked-interval-delete",
        "case": case,
        "preparationResult": prep_path,
        "preparationResultSha256": prep_sha,
        "firstSplitPair": str(first_pair_path.resolve().relative_to(OUT.resolve())),
        "firstSplitPairSha256": first_sha,
        "secondPositionResult": position_ref["path"],
        "secondPositionResultSha256": position_ref["sha256"],
        "secondSplitPair": str(second_pair_path.resolve().relative_to(OUT.resolve())),
        "secondSplitPairSha256": second_sha,
    })
    delete_ref, deleted_result = _save(directory, "interval-deletion.json", delete_result)
    if deleted_result.get("status") != "interval-deleted-unsaved":
        raise RuntimeError(f"{case} interval deletion did not validate")
    deleted_ref, deleted, deleted_pair_path, deleted_sha = _single_readback(
        native, directory, case, "deleted"
    )
    if deleted_sha != deleted_result.get("afterPair", {}).get("sha256"):
        raise RuntimeError(f"{case} deletion readback differs from validated postflight")
    restored_result = native.invoke({
        "action": "editorial-case-restore",
        "case": case,
        "preparationResult": prep_path,
        "preparationResultSha256": prep_sha,
        "postEditPair": str(deleted_pair_path.resolve().relative_to(OUT.resolve())),
        "postEditPairSha256": deleted_sha,
        "secondPositionResult": position_ref["path"],
        "secondPositionResultSha256": position_ref["sha256"],
        "firstSplitPairSha256": first_sha,
    })
    restore_ref, restored = _save(directory, "restoration.json", restored_result)
    if (
        restored.get("status") != "restored-unsaved"
        or restored.get("originalLocks") != preparation.get("originalLocks")
        or restored.get("originalPlayhead") != preparation.get("originalPlayhead")
    ):
        raise RuntimeError(f"{case} recorded lock/playhead restoration failed")
    for menu in ("auto-none", "auto-v1", "auto-a1"):
        native.invoke(menu=menu)
    final_ref, final_readback, _final_pair_path, final_sha = _single_readback(
        native, directory, case, "context"
    )
    restored_pair_ref = restored.get("restoredPair", {})
    if (
        final_sha != restored_pair_ref.get("sha256")
        or final_readback["selectionPasses"][0].get("playhead")
        != preparation.get("originalPlayhead")
    ):
        raise RuntimeError(f"{case} Auto Select reset changed restored state/playhead")
    return {
        "status": "single-track-sequence-complete",
        "case": case,
        "directory": str(directory),
        "preparation": prep_ref,
        "firstSelection": first_selected_ref,
        "firstSplit": first_ref,
        "secondPosition": position_ref,
        "secondSelection": second_selected_ref,
        "secondSplit": second_ref,
        "intervalDeletion": delete_ref,
        "deletedReadback": deleted_ref,
        "restoration": restore_ref,
        "autoSelectReset": final_ref,
        "saveDispatched": False,
    }


def offline_sequence_check():
    """Run each single-track path and empty-selection refusal on fake Stores."""
    _check_readback_labels(
        {
            f"r2-{case.removeprefix('R2-').lower()}-{stage}"
            for case in SINGLE_CASES
            for stage in (
                "context", "deselected", "selected", "first-split",
                "second-position", "second-selected", "second-split", "deleted",
            )
        }
    )
    checker = _load("editorial_cases_checker", HERE / "editorial-cases-check.py")
    cases = _load("editorial_cases_for_fake", HERE / "editorial-cases.py")
    global OUT
    original_out = OUT
    try:
        with tempfile.TemporaryDirectory(prefix="independent-cut-sequence-") as temp:
            root = Path(temp)
            for case in SINGLE_CASES:
                output = root / "out" / f"issue-141-observation-{case.lower()}"
                output.mkdir(parents=True)
                media = root / "out" / f"issue-141-media-{case.lower()}"
                media.mkdir()
                for fail_selection in (False, True):
                    OUT = output
                    store = checker.Store("success", case)
                    store.playhead = "00:01:30:00"
                    for row in store.matrix_state()["tracks"]:
                        if (row["type"], row["index"]) in cases.LOCKS:
                            row["GetIsTrackLocked"]["value"] = True
                    project = checker.Project(store)
                    resolve = SimpleNamespace(
                        GetProductName=lambda: "DaVinci Resolve Studio",
                        GetVersion=lambda: cases.BUILD,
                        GetCurrentPage=lambda: store.page,
                        OpenPage=lambda page: checker.open_page(store, page),
                        GetProjectManager=lambda: SimpleNamespace(
                            GetCurrentProject=lambda: project
                        ),
                    )
                    probe = SimpleProbe(root)

                    def validate_pair(value, _probe):
                        if (
                            value.get("selectedTimelineUid") != cases.MATRIX_UID
                            or value.get("timelinePasses", [None])[0]
                            != value.get("timelinePasses", [None, None])[1]
                            or value.get("poolPasses", [None])[0]
                            != value.get("poolPasses", [None, None])[1]
                        ):
                            raise RuntimeError("Fake stable pair refused")
                        return value["timelinePasses"][0], value["poolPasses"][0]

                    def read_pair(*_args):
                        store.sync_usages()
                        return make_pair(deepcopy(store.state), deepcopy(store.pool))

                    def timeline(state, uid):
                        rows = [row for row in state["timelines"]
                                if row["GetUniqueId"]["value"] == uid]
                        if len(rows) != 1:
                            raise RuntimeError("Fake timeline missing")
                        return rows[0]

                    reader = SimpleNamespace(
                        _manifest=lambda *_: (media, {"synthetic": "fixture"}),
                        _pin=lambda path, name, digest, _probe: (
                            json.loads(Path(path).read_text())
                            if Path(path).name == name and _sha(path) == digest
                            else (_ for _ in ()).throw(RuntimeError("Fake pin changed"))
                        ),
                        _validate_read_pair=validate_pair,
                        _timeline=timeline,
                        _context=lambda _resolve, _config, _identity, _probe, uid: (
                            project
                            if project.GetCurrentTimeline().GetUniqueId() == uid
                            else (_ for _ in ()).throw(RuntimeError("Fake selection changed"))
                        ),
                        _read_pair=read_pair,
                        _write=lambda path, value: Path(path).write_text(
                            json.dumps(value, indent=2, sort_keys=True) + "\n"
                        ),
                    )
                    initial_pair = read_pair()
                    prior_path = output / "prior.json"
                    reader._write(prior_path, initial_pair)
                    prior_sha = _sha(prior_path)
                    fake = FakeNativeSequence(
                        case, cases, reader, probe, resolve, store, media, output,
                        fail_selection=fail_selection,
                    )
                    try:
                        result = run_sequence(
                            case, "prior.json", prior_sha, native=fake,
                            cases_module=cases, probe_obj=probe, reader_obj=reader,
                            check_sources=False,
                        )
                    except RuntimeError as error:
                        if not fail_selection or "selected-item readback is incomplete" not in str(error):
                            raise
                        if "split" in fake.menus:
                            raise AssertionError(f"{case} selection refusal dispatched Split")
                    else:
                        if fail_selection:
                            raise AssertionError(f"{case} empty selection was accepted")
                        if result["status"] != "single-track-sequence-complete":
                            raise AssertionError(f"{case} fake sequence did not complete")
                        expected_locks = fake.preparation["originalLocks"]
                        if store.playhead != "00:01:30:00" or any(
                            row["GetIsTrackLocked"]["value"]
                            != expected_locks[f"{row['type']}:{row['index']}"]
                            for row in store.matrix_state()["tracks"]
                        ):
                            raise AssertionError(f"{case} locks/playhead were not restored")
                        target = cases.R2_SINGLE[case]["track"]
                        auto = "auto-a1" if target == "audio" else "auto-v1"
                        expected_menus = [
                            "auto-none", auto, "deselect", "select", "split",
                            "auto-none", auto, "deselect", "select", "split",
                            "auto-none", "auto-v1", "auto-a1",
                        ]
                        if fake.menus != expected_menus:
                            raise AssertionError(f"{case} Auto Select order changed")
                        if case == SINGLE_CASES[0]:
                            store.state = deepcopy(initial_pair["timelinePasses"][0])
                            store.pool = deepcopy(initial_pair["poolPasses"][0])
                            store.playhead = "00:01:30:00"
                            resumed_fake = FakeNativeSequence(
                                case, cases, reader, probe, resolve, store, media, output
                            )
                            reviewed = resumed_fake.invoke({
                                "action": "editorial-case-prepare",
                                "case": case,
                                "priorPair": "prior.json",
                                "priorPairSha256": prior_sha,
                            })
                            reviewed.update(
                                reviewOnly=True,
                                reviewedFrom={"partialResult": {"path": "fake-refusal.json"}},
                            )
                            reviewed_path = output / "reviewed-preparation.json"
                            reviewed_path.write_text(json.dumps(reviewed))
                            reviewed_sha = _sha(reviewed_path)
                            resumed_fake.actions.clear()
                            resumed = run_sequence(
                                case,
                                "prior.json",
                                prior_sha,
                                native=resumed_fake,
                                cases_module=cases,
                                probe_obj=probe,
                                reader_obj=reader,
                                check_sources=False,
                                reviewed_preparation="reviewed-preparation.json",
                                reviewed_preparation_sha=reviewed_sha,
                            )
                            if (
                                resumed.get("status") != "single-track-sequence-complete"
                                or "editorial-case-prepare" in resumed_fake.actions
                            ):
                                raise AssertionError(
                                    "Reviewed preparation was replayed or failed to resume"
                                )
    finally:
        OUT = original_out


def _check_readback_labels(labels):
    reader = _load("editorial_readback_labels", HERE / "editorial-readback.py")
    invalid = sorted(set(labels) - reader.LABELS)
    if invalid:
        raise AssertionError(f"Unsupported editorial readback labels: {invalid}")


def make_pair(state, pool):
    return {
        "selectedTimelineUid": "29ae8331-b86e-4041-a548-960695cc7b24",
        "timelineConsistency": "equal-adjacent-reads",
        "poolConsistency": "equal-adjacent-reads",
        "timelinePasses": [deepcopy(state), deepcopy(state)],
        "poolPasses": [deepcopy(pool), deepcopy(pool)],
    }


class FakeNativeSequence:
    def __init__(self, case, cases, reader, probe, resolve, store, media, output,
                 *, fail_selection=False):
        self.case = case
        self.cases, self.reader, self.probe = cases, reader, probe
        self.resolve, self.store, self.media, self.output = resolve, store, media, output
        self.fail_selection = fail_selection
        self.config = {
            "action": "observe",
            "case": case,
            "externalScriptingSetting": "None",
            "projectName": store.project_name,
            "outputDir": str(output),
            "mediaDir": str(media),
            "priorPair": "prior.json",
            "priorPairSha256": _sha(output / "prior.json"),
        }
        self.menus, self.selected, self.first_right, self.split_count = [], [], {}, 0
        self.actions = []

    def invoke(self, updates=None, menu=None):
        if menu is not None:
            self.menus.append(menu)
            if menu == "deselect":
                self.selected = []
            elif menu == "select":
                if self.fail_selection:
                    self.selected = []
                else:
                    kind = self.cases.R2_SINGLE[self.case]["track"]
                    uid = (
                        self.preparation["target"]["uids"][kind]
                        if self.split_count == 0 else self.first_right[kind]
                    )
                    self.selected = [uid]
            elif menu == "split":
                self._split()
            return {"menu": menu, "dispatched": True}

        self.config.update(updates)
        action = self.config["action"]
        self.actions.append(action)
        if action == "editorial-case-prepare":
            self.preparation = self.cases.prepare(
                self.resolve, self.config, probe=self.probe, reader=self.reader
            )
            return self.preparation
        if action == "editorial-readback":
            return self._readback(self.config["editorialReadbackLabel"])
        if action == "r2-linked-second-position":
            return self.cases.second_position(
                self.resolve, self.config, probe=self.probe, reader=self.reader
            )
        if action == "r2-linked-interval-delete":
            return self.cases.interval_delete(
                self.resolve, self.config, probe=self.probe, reader=self.reader
            )
        if action == "editorial-case-restore":
            return self.cases.restore(
                self.resolve, self.config, probe=self.probe, reader=self.reader
            )
        raise AssertionError(f"Unexpected fake action: {action}")

    def _readback(self, label):
        pair = self.reader._read_pair(
            self.resolve, self.config, {}, {}, self.cases.MATRIX_UID, self.probe
        )
        directory = self.output / (label + "-fake")
        directory.mkdir(exist_ok=True)
        pair_path = directory / "pair.json"
        self.reader._write(pair_path, pair)
        selected = []
        for kind in ("video", "audio"):
            track = next(
                row for row in self.store.matrix_state()["tracks"]
                if row["type"] == kind and row["index"] == 1
            )
            selected.extend(
                deepcopy(item) for item in track["items"]
                if item["GetUniqueId"]["value"] in self.selected
            )
        passes = [
            {"playhead": self.store.playhead, "items": deepcopy(selected)}
            for _ in range(2)
        ]
        result = {
            "status": "editorial-readback-retained",
            "label": label,
            "readOnly": True,
            "failure": None,
            "pair": {"path": str(pair_path.resolve()), "sha256": _sha(pair_path)},
            "selectionPasses": passes,
            "selectionShapes": [
                {"type": "list", "count": len(selected)} for _ in range(2)
            ],
            "fakeSelectedUids": list(self.selected),
        }
        self.last_result = result
        return result

    def _split(self):
        self.split_count += 1
        case_spec = self.cases.R2_SINGLE[self.case]
        kind = case_spec["track"]
        spec = self.cases.CASES[self.case]
        track = next(
            row for row in self.store.matrix_state()["tracks"]
            if row["type"] == kind and row["index"] == 1
        )
        parent_uid = (
            self.preparation["target"]["uids"][kind]
            if self.split_count == 1 else self.first_right[kind]
        )
        parent = next(
            item for item in track["items"]
            if item["GetUniqueId"]["value"] == parent_uid
        )
        if self.split_count == 1:
            cut = case_spec["cutStart"]
            record_start, source_start = spec["start"], 0
            record_cut, source_cut = spec["start"] + cut, cut
            right_uid = f"fake-first-{kind}"
        else:
            cut = case_spec["cutEnd"]
            record_start = spec["start"] + case_spec["cutStart"]
            source_start = case_spec["cutStart"]
            record_cut, source_cut = spec["start"] + cut, cut
            right_uid = f"fake-tail-{kind}"
        left = self.cases._razor_child(
            parent, deepcopy(parent), record_start, record_cut, source_start, source_cut
        )
        right = deepcopy(parent)
        right["GetUniqueId"] = {"value": right_uid}
        right = self.cases._razor_child(
            parent, right, record_cut, spec["end"], source_cut, 199
        )
        left["GetLinkedItems"], right["GetLinkedItems"] = [], []
        track["items"] = [item for item in track["items"] if item is not parent] + [left, right]
        track["items"].sort(key=lambda item: item["GetStart"]["value"])
        self.first_right[kind] = right_uid
        source_uid = self.preparation["target"]["sourceUids"][kind]
        pool_row = next(row for row in self.store.pool["items"] if row["uid"] == source_uid)
        usage = pool_row["evidence"]["GetClipProperty"]["value"]["Usage"]
        pool_row["evidence"]["GetClipProperty"]["value"]["Usage"] = str(int(usage) + 1)


def _pin_prepared(reader, path, ref, probe):
    if (
        path.is_symlink()
        or not path.is_file()
        or not path.resolve().is_relative_to(OUT.resolve())
        or _sha(path) != ref.get("sha256")
    ):
        raise RuntimeError("Prepared pair escaped or changed from its pin")
    pair = json.loads(path.read_text())
    state, _ = reader._validate_read_pair(pair, probe)
    return pair, state


class SimpleProbe:
    def __init__(self, root):
        self.ROOT = root

    @staticmethod
    def sha256(path):
        return _sha(path)

    @staticmethod
    def errors(value):
        if isinstance(value, dict):
            return (
                ([value["error"]] if "error" in value else [])
                + (["null-getter-result-not-established"]
                   if value.get("value", False) is None else [])
                + (["source-hash-mismatch"] if value.get("hashMatches") is False else [])
                + [error for child in value.values() for error in SimpleProbe.errors(child)]
            )
        if isinstance(value, list):
            return [error for child in value for error in SimpleProbe.errors(child)]
        return []


def check(case, prior_pair, prior_sha):
    path = _boundary(case, prior_pair, prior_sha)
    rejected = [
        ("R1-copy", prior_pair, prior_sha),
        (case, "../" + prior_pair, prior_sha),
        (case, prior_pair, "0" * 64),
    ]
    for case, relative, digest in rejected:
        try:
            _boundary(case, relative, digest)
        except (ValueError, OSError, json.JSONDecodeError):
            continue
        raise AssertionError("Input boundary accepted an invalid case or pair pin")
    offline_sequence_check()
    print(f"Input boundary passes for {path.name}; no native action dispatched.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=SINGLE_CASES, default=SINGLE_CASES[0])
    parser.add_argument("--prior-pair", required=True)
    parser.add_argument("--prior-sha256", required=True)
    parser.add_argument("--reviewed-preparation")
    parser.add_argument("--reviewed-preparation-sha256")
    parser.add_argument("--check", action="store_true", help="validate only; no Resolve action")
    parser.add_argument("--run", action="store_true", help="execute the guarded native sequence")
    args = parser.parse_args(argv)
    if args.check == args.run:
        parser.error("choose exactly one of --check or --run")
    if args.check:
        check(args.case, args.prior_pair, args.prior_sha256)
        return 0
    result = run_sequence(
        args.case,
        args.prior_pair,
        args.prior_sha256,
        reviewed_preparation=args.reviewed_preparation,
        reviewed_preparation_sha=args.reviewed_preparation_sha256,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
