"""Select the Issue 141 Matrix once and retain a complete read-only pair."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path


ACTION = "producer-matrix-selection-continuation"
PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
PROJECT_NAME = "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
MATRIX_UID = "29ae8331-b86e-4041-a548-960695cc7b24"
MATRIX_NAME = "VERA 141 Batched Matrix"
PRIOR_UID = "21436b8f-057c-49e6-80ba-5f733abe87b2"
PRIOR_NAME = "transcription test 1"
PROTECTED_INVENTORY = "protected-six"
PROTECTED_SOURCE_UID = "be5f1584-f0c4-4dd9-988b-73f3167e77d1"
PROTECTED_SOURCE_NAME = "semi1b.mp4"
PROBE_SHA256 = "cad63c88f400897fa37bc558d76fca410b7040bf1cc6b2a4ff270e0754b62fa8"
READER_SHA256 = "9b6977747a1f3decf957ead6134f10fc4f597bf9d0c3dc5c081b7bf2671879a4"
EDITORIAL_CASES_SHA256 = (
    "1e1c2685de795bdc60ffa806c0fde10d75e300340fc2c1178b8ccf4d1a93f372"
)
PRIOR_PAIR = (
    "protected-six-r4-pool-20261001T180848.009764Z/pair.json"
)
PRIOR_PAIR_SHA256 = (
    "5131589527428829afe6e1503e245609a4f17bb3207a2fe61a874db4289601b3"
)
BUILD = [21, 1, 0, 14, ""]

ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = ROOT / "docs/investigations/issue-141/probe.py"
READER_PATH = ROOT / "docs/investigations/issue-141/r4-range-repair.py"


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _jsonable(value):
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except Exception as serialization_error:
        try:
            type_name = getattr(type(value), "__name__", None) or "opaque"
        except Exception:  # pragma: no cover - defensive remote proxy boundary
            type_name = "opaque"
        try:
            rendered = repr(value)
        except Exception:  # pragma: no cover - defensive remote proxy boundary
            rendered = "<opaque>"
        return {
            "unserializableType": type_name,
            "repr": rendered,
            "serializationError": (
                f"{type(serialization_error).__name__}: {serialization_error}"
            ),
        }


def _call(obj, method, *args):
    try:
        value = getattr(obj, method)(*args)
    except Exception as error:
        return {"state": "error", "error": f"{type(error).__name__}: {error}"}, None
    return {"state": "value", "value": _jsonable(value)}, value


def _identity(obj):
    uid, uid_value = _call(obj, "GetUniqueId")
    name, name_value = _call(obj, "GetName")
    return {"GetUniqueId": uid, "GetName": name}, uid_value, name_value


def _append(path, method, phase, value):
    with Path(path).open("a", encoding="utf-8") as stream:
        json.dump(
            {
                "at": datetime.now(UTC).isoformat(),
                "method": method,
                "phase": phase,
                "value": _jsonable(value),
            },
            stream,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")


def _write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _load(path, name, digest):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or sha256(path) != digest:
        raise RuntimeError(f"Pinned {name} source changed")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load pinned {name} source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _modules():
    return (
        _load(PROBE_PATH, "producer_matrix_selection_probe", PROBE_SHA256),
        _load(READER_PATH, "producer_matrix_selection_reader", READER_SHA256),
    )


def _pin(output, relative, digest, reader, probe):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise RuntimeError("A relative approved-output pair pin is required")
    path, cursor = output / relative, output
    for part in Path(relative).parts:
        if part in {".", ".."}:
            raise RuntimeError("Pair pin may not traverse output")
        cursor /= part
        if cursor.is_symlink() or not cursor.resolve().is_relative_to(output.resolve()):
            raise RuntimeError("Pair pin escapes or links outside output")
    return reader._pin(path, path.name, digest, probe)


def _context(resolve, project):
    project_id, _ = _call(project, "GetUniqueId")
    project_name, _ = _call(project, "GetName")
    selected_read, selected = _call(project, "GetCurrentTimeline")
    if selected is None:
        selected_identity = None
        playhead = {"state": "value", "value": None}
    else:
        selected_identity, _, _ = _identity(selected)
        playhead, _ = _call(selected, "GetCurrentTimecode")
    page, _ = _call(resolve, "GetCurrentPage")
    product, _ = _call(resolve, "GetProductName")
    version, _ = _call(resolve, "GetVersion")
    rendering, _ = _call(project, "IsRenderingInProgress")
    jobs, _ = _call(project, "GetRenderJobList")
    format_codec, _ = _call(project, "GetCurrentRenderFormatAndCodec")
    return {
        "productName": product,
        "version": version,
        "project": {"GetUniqueId": project_id, "GetName": project_name},
        "currentTimeline": {
            "getter": selected_read,
            "identity": selected_identity,
        },
        "playhead": playhead,
        "currentPage": page,
        "formatCodec": format_codec,
        "jobs": jobs,
        "rendering": rendering,
    }


def _value(read):
    if not isinstance(read, dict) or "value" not in read:
        return None
    if "state" in read and read.get("state") != "value":
        return None
    return read.get("value")


def _context_guard(context, expected_uid):
    project = context.get("project", {})
    selected = context.get("currentTimeline", {}).get("identity") or {}
    selected_uid = _value(selected.get("GetUniqueId", {}))
    if (
        _value(context.get("productName", {})) != "DaVinci Resolve Studio"
        or _value(context.get("version", {})) != BUILD
        or _value(project.get("GetUniqueId", {})) != PROJECT_ID
        or _value(project.get("GetName", {})) != PROJECT_NAME
        or selected_uid != expected_uid
        or _value(context.get("currentPage", {})) != "edit"
        or _value(context.get("formatCodec", {})) != {"format": "mov", "codec": "H264"}
        or _value(context.get("jobs", {})) != []
        or _value(context.get("rendering", {})) is not False
    ):
        raise RuntimeError("Exact protected-six project/Edit/idle context required")


def _pair_content(pair, reader, probe, expected):
    if (
        pair.get("selectedTimelineUid") not in {PRIOR_UID, MATRIX_UID}
        or pair.get("timelineInventory") != PROTECTED_INVENTORY
    ):
        raise RuntimeError("Protected-six pair selection or metadata is invalid")
    state, pool = reader._validate_read_pair(pair, probe)
    if (
        state.get("projectId") != PROJECT_ID
        or state.get("projectName") != PROJECT_NAME
        or state.get("timelineInventory") != PROTECTED_INVENTORY
    ):
        raise RuntimeError("Protected-six pair project identity changed")
    _timeline_map(state, reader)
    _source_evidence(pair, expected)
    return state, pool


def _timeline_map(state, reader):
    expected = reader.PROTECTED_TIMELINE_IDENTITIES
    rows = state.get("timelines")
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise RuntimeError("Protected-six timeline count changed")
    found = {}
    for row in rows:
        uid = _value(row.get("GetUniqueId", {}))
        name = _value(row.get("GetName", {}))
        if not isinstance(uid, str) or not isinstance(name, str) or uid in found:
            raise RuntimeError("Protected-six timeline identity is missing or duplicated")
        found[uid] = name
    if found != expected:
        raise RuntimeError("Protected-six timeline UID/name map changed")
    return found


def _source_evidence(value, expected):
    statuses = {
        "reachable",
        "offline-locator-not-accessed",
        "protected-locator-not-accessed",
        "timeline-uid-not-hashed",
    }
    protected_count = 0
    generated_count = 0

    def visit(node):
        nonlocal protected_count, generated_count
        if isinstance(node, dict):
            uid = _value(node.get("GetUniqueId", {}))
            if uid == PROTECTED_SOURCE_UID:
                protected_count += 1
                if (
                    node.get("GetName") != {"value": PROTECTED_SOURCE_NAME}
                    or node.get("sourceBytes")
                    != {"status": "protected-locator-not-accessed"}
                    or any(key in node.get("sourceBytes", {}) for key in ("sha256", "hashMatches"))
                ):
                    raise RuntimeError("Protected source was normalized or hashed")
            source_bytes = node.get("sourceBytes")
            if isinstance(source_bytes, dict) and "status" in source_bytes:
                status = source_bytes.get("status")
                if status not in statuses:
                    raise RuntimeError("Unknown source evidence status")
                if status == "reachable":
                    generated_count += 1
                    digest = source_bytes.get("sha256")
                    if (
                        source_bytes.get("hashMatches") is not True
                        or digest not in set(expected.values())
                    ):
                        raise RuntimeError("Generated source bytes are not allowlisted")
                elif status == "offline-locator-not-accessed":
                    approved = source_bytes.get("approvedLocator")
                    if source_bytes.get("expectedSha256") != expected.get(approved):
                        raise RuntimeError("Offline generated source is not allowlisted")
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    if protected_count == 0:
        raise RuntimeError("Protected source evidence is missing")
    return {
        "protectedSourceEvidenceCount": protected_count,
        "generatedReachableEvidenceCount": generated_count,
        "protectedSourceStatus": "protected-locator-not-accessed",
    }


def _protected_metadata(value):
    rows = []

    def visit(node, path=""):
        if isinstance(node, dict):
            if _value(node.get("GetUniqueId", {})) == PROTECTED_SOURCE_UID:
                rows.append({"path": path, "value": deepcopy(node)})
            for key, child in node.items():
                visit(child, f"{path}/{key}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, f"{path}/{index}")

    visit(value)
    return rows


def _context_differences(before, after):
    differences = []

    def visit(left, right, path=""):
        if type(left) is not type(right):
            differences.append({"path": path or "/", "before": left, "after": right})
            return
        if isinstance(left, dict):
            for key in sorted(set(left) | set(right)):
                if key not in left or key not in right:
                    differences.append(
                        {"path": f"{path}/{key}", "before": left.get(key), "after": right.get(key)}
                    )
                else:
                    visit(left[key], right[key], f"{path}/{key}")
        elif isinstance(left, list):
            if len(left) != len(right):
                differences.append({"path": path, "before": left, "after": right})
            else:
                for index, (left_item, right_item) in enumerate(zip(left, right)):
                    visit(left_item, right_item, f"{path}/{index}")
        elif left != right:
            differences.append({"path": path, "before": left, "after": right})

    visit(before, after)
    return differences


def _selection_context_is_safe(before, after):
    immutable_paths = (
        "/productName",
        "/version",
        "/project",
        "/currentPage",
        "/formatCodec",
        "/jobs",
        "/rendering",
    )
    for path in immutable_paths:
        left, right = before, after
        for part in path.strip("/").split("/"):
            left, right = left[part], right[part]
        if left != right:
            raise RuntimeError(f"Selection changed immutable context field {path}")
    before_uid = _value(before["currentTimeline"]["identity"]["GetUniqueId"])
    after_uid = _value(after["currentTimeline"]["identity"]["GetUniqueId"])
    if (before_uid, after_uid) != (PRIOR_UID, MATRIX_UID):
        raise RuntimeError("SetCurrentTimeline readback does not show producer-to-Matrix")


def _ref(path, output, digest):
    return {"path": str(Path(path).resolve().relative_to(output.resolve())), "sha256": digest}


def _result_config(config, output, after_ref):
    return {
        "action": "editorial-case-prepare",
        "case": "R2-picture",
        "externalScriptingSetting": "None",
        "projectId": PROJECT_ID,
        "projectName": PROJECT_NAME,
        "outputDir": str(output),
        "mediaDir": config.get("mediaDir"),
        "manifestSha256": config.get("manifestSha256"),
        "timelineInventory": PROTECTED_INVENTORY,
        "priorPair": after_ref["path"],
        "priorPairSha256": after_ref["sha256"],
        "sourceReview": {
            "probe.py": PROBE_SHA256,
            "r4-range-repair.py": READER_SHA256,
            "editorial-cases.py": EDITORIAL_CASES_SHA256,
        },
    }


def run(resolve, config):
    """Run one guarded Matrix selection; never save or retry after a setter."""
    output = Path(config.get("outputDir", ""))
    if (
        config.get("action") != ACTION
        or config.get("projectId", PROJECT_ID) != PROJECT_ID
        or config.get("projectName") != PROJECT_NAME
        or config.get("externalScriptingSetting") != "None"
        or config.get("timelineInventory") != PROTECTED_INVENTORY
        or config.get("priorPair") != PRIOR_PAIR
        or config.get("priorPairSha256") != PRIOR_PAIR_SHA256
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.resolve().parent != (ROOT / "out").resolve()
        or not output.name.startswith("issue-141-observation-")
    ):
        raise RuntimeError("Exact protected-six Matrix-selection continuation is required")

    probe, reader = _modules()
    _, expected = reader._manifest(config, ROOT, probe)
    identity = {"projectId": PROJECT_ID, "projectName": PROJECT_NAME}
    pinned = _pin(output, PRIOR_PAIR, PRIOR_PAIR_SHA256, reader, probe)
    pinned_state, pinned_pool = _pair_content(pinned, reader, probe, expected)
    if pinned.get("selectedTimelineUid") != PRIOR_UID:
        raise RuntimeError("Pinned pair must be selected on transcription test 1")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence = output / f"producer-matrix-selection-{stamp}"
    evidence.mkdir(exist_ok=False)
    journal = evidence / "journal.jsonl"
    journal.touch()
    _append(
        journal,
        ACTION,
        "start",
        {
            "projectId": PROJECT_ID,
            "matrixUid": MATRIX_UID,
            "priorUid": PRIOR_UID,
            "sourceReview": {
                "probe.py": PROBE_SHA256,
                "r4-range-repair.py": READER_SHA256,
                "editorial-cases.py": EDITORIAL_CASES_SHA256,
            },
            "python": platform.python_version(),
        },
    )
    report = {
        "kind": ACTION,
        "status": "refused",
        "readOnly": False,
        "contextMutation": True,
        "contentMutation": False,
        "projectId": PROJECT_ID,
        "projectName": PROJECT_NAME,
        "selectionDispatched": False,
        "saveDispatched": False,
        "menuCommandDispatched": False,
        "sourceReview": {
            "probe.py": PROBE_SHA256,
            "r4-range-repair.py": READER_SHA256,
            "editorial-cases.py": EDITORIAL_CASES_SHA256,
        },
        "priorPair": _ref(output / PRIOR_PAIR, output, PRIOR_PAIR_SHA256),
        "journal": str(journal),
        "failure": None,
    }

    try:
        project = reader._context(resolve, config, identity, probe, PRIOR_UID)
        before_context = _context(resolve, project)
        _context_guard(before_context, PRIOR_UID)
        _write(evidence / "context-before.json", before_context)
        _append(journal, "Context", "before", before_context)

        before_pair = reader._read_pair(
            resolve, config, identity, expected, PRIOR_UID, probe
        )
        before_state, before_pool = _pair_content(before_pair, reader, probe, expected)
        if before_pair != pinned or before_state != pinned_state or before_pool != pinned_pool:
            raise RuntimeError("Fresh producer-selected pair differs from pinned pair")
        before_pair_path = evidence / "before-pair.json"
        _write(before_pair_path, before_pair)
        before_pair_ref = _ref(before_pair_path, output, sha256(before_pair_path))
        report["beforePair"] = before_pair_ref
        _append(journal, "FullReadback", "before", before_pair_ref)

        matches = []
        for index in range(1, project.GetTimelineCount() + 1):
            timeline = project.GetTimelineByIndex(index)
            if timeline.GetUniqueId() == MATRIX_UID:
                matches.append(timeline)
        if len(matches) != 1 or matches[0].GetName() != MATRIX_NAME:
            raise RuntimeError("Exact Matrix timeline handle is missing or duplicated")
        _append(journal, "SetCurrentTimeline", "request", MATRIX_UID)
        report["selectionDispatched"] = True
        try:
            returned = project.SetCurrentTimeline(matches[0])
        except Exception as error:
            failure = f"{type(error).__name__}: {error}"
            _append(journal, "SetCurrentTimeline", "failure", failure)
            raise RuntimeError("SetCurrentTimeline failed; retain selection evidence") from error
        _append(journal, "SetCurrentTimeline", "return", returned)
        if returned is not True:
            raise RuntimeError("SetCurrentTimeline refused")
        readback = project.GetCurrentTimeline()
        selected_uid = readback.GetUniqueId() if readback is not None else None
        _append(journal, "SetCurrentTimeline", "readback", selected_uid)
        if selected_uid != MATRIX_UID:
            raise RuntimeError("SetCurrentTimeline readback differs")

        matrix_project = reader._context(resolve, config, identity, probe, MATRIX_UID)
        after_context = _context(resolve, matrix_project)
        _context_guard(after_context, MATRIX_UID)
        _write(evidence / "context-after.json", after_context)
        _append(journal, "Context", "after", after_context)
        _selection_context_is_safe(before_context, after_context)

        after_pair = reader._read_pair(
            resolve, config, identity, expected, MATRIX_UID, probe
        )
        after_state, after_pool = _pair_content(after_pair, reader, probe, expected)
        after_pair_path = evidence / "after-pair.json"
        _write(after_pair_path, after_pair)
        after_pair_ref = _ref(after_pair_path, output, sha256(after_pair_path))
        report["afterPair"] = after_pair_ref
        _append(journal, "FullReadback", "after", after_pair_ref)

        producer_uids = {PRIOR_UID, "2db0b2d1-6d81-48d4-b49c-360f56e012cd"}
        producer_before = {
            uid: next(row for row in before_state["timelines"] if _value(row["GetUniqueId"]) == uid)
            for uid in producer_uids
        }
        producer_after = {
            uid: next(row for row in after_state["timelines"] if _value(row["GetUniqueId"]) == uid)
            for uid in producer_uids
        }
        protected_before = _protected_metadata({"state": before_state, "pool": before_pool})
        protected_after = _protected_metadata({"state": after_state, "pool": after_pool})
        content_equal = before_state == after_state and before_pool == after_pool
        context_differences = _context_differences(before_context, after_context)
        _write(evidence / "context-differences.json", context_differences)
        content_comparison = {
            "fullTimelineContentEqual": before_state == after_state,
            "fullPoolContentEqual": before_pool == after_pool,
            "producerTimelineContentEqual": producer_before == producer_after,
            "protectedSourceMetadataEqual": protected_before == protected_after,
            "selectedTimelineUidBefore": before_pair["selectedTimelineUid"],
            "selectedTimelineUidAfter": after_pair["selectedTimelineUid"],
            "contextDifferences": context_differences,
        }
        _write(evidence / "content-comparison.json", content_comparison)
        report["contextDifferences"] = "context-differences.json"
        report["contentComparison"] = "content-comparison.json"
        if not content_equal or producer_before != producer_after or protected_before != protected_after:
            raise RuntimeError("Matrix selection changed protected or full timeline/pool content")

        r2_config = _result_config(config, output, after_pair_ref)
        r2_config_path = evidence / "r2-picture-prepare-config.json"
        _write(r2_config_path, r2_config)
        r2_config_ref = _ref(r2_config_path, output, sha256(r2_config_path))
        report.update(
            {
                "status": "matrix-selected-read-only-r2-picture-ready",
                "contextBefore": "context-before.json",
                "contextAfter": "context-after.json",
                "r2PicturePrepareConfig": r2_config_ref,
                "r2PicturePrepare": r2_config,
                "selection": {
                    "method": "SetCurrentTimeline",
                    "targetUid": MATRIX_UID,
                    "targetName": MATRIX_NAME,
                    "priorUid": PRIOR_UID,
                    "priorName": PRIOR_NAME,
                },
            }
        )
    except Exception as error:
        report["status"] = (
            "refused-partial-state-retained"
            if report["selectionDispatched"]
            else "refused"
        )
        report["failure"] = f"{type(error).__name__}: {error}"
    _write(evidence / "result.json", report)
    _append(journal, ACTION, "complete", report)
    return report
