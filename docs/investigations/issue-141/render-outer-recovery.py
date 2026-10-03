"""One guarded restoration of Issue 141's first full-Matrix render settings."""

import hashlib
import importlib.util
import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
PROJECT_NAME = "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
MATRIX_UID = "29ae8331-b86e-4041-a548-960695cc7b24"
PRESET = "VERA141_AV_OUTPUT_20261001T231540.921062Z"
ATTEMPT = "av-output-20261001T231540.921062Z"
PROXY_UID = "de8efefa-310d-451c-863c-d6b847e8b82e"
READER_FILE = "r4-range-repair.py"
READER_SHA256 = "9b6977747a1f3decf957ead6134f10fc4f597bf9d0c3dc5c081b7bf2671879a4"
BUILD = [21, 1, 0, 14, ""]

def _load_reader():
    path = Path(__file__).with_name(READER_FILE)
    if path.is_symlink() or _sha(path) != READER_SHA256:
        raise RuntimeError("Pinned full-state reader changed")
    spec = importlib.util.spec_from_file_location("outer_recovery_reader", path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    return reader


def _sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _log(path, method, phase, value):
    with Path(path).open("a", encoding="utf-8") as stream:
        json.dump({"at": datetime.now(UTC).isoformat(), "method": method,
                   "phase": phase, "value": value}, stream, sort_keys=True,
                  allow_nan=False)
        stream.write("\n")


def _leaf_diffs(a, b, path=()):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                yield (*path, key)
            else:
                yield from _leaf_diffs(a[key], b[key], (*path, key))
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            yield from _leaf_diffs(x, y, (*path, i))
    elif a != b:
        yield path


def _only_captured_proxy_out(before, after):
    expected = set()
    for n in range(2):
        for collection, uid_path, uid in (
            ("items", ("uid",), PROXY_UID),
            ("timelineMappings", ("timelineUid", "value"), MATRIX_UID),
        ):
            rows = after["poolPasses"][n].get(collection, [])
            matches = []
            for i, row in enumerate(rows):
                if collection == "items":
                    match = row.get("uid") == uid
                else:
                    match = (row.get("timelineUid", {}).get("value") == uid and
                             row.get("poolItemUid", {}).get("value") == PROXY_UID)
                if match:
                    matches.append(i)
            if len(matches) != 1:
                raise RuntimeError("captured Matrix proxy/mapping is ambiguous")
            i = matches[0]
            leaf = (("evidence", "GetClipProperty", "value", "Out")
                    if collection == "items" else ("poolItemProperties", "value", "Out"))
            node = rows[i]
            for key in leaf:
                node = node.get(key, {}) if isinstance(node, dict) else {}
            value_after = node if isinstance(node, str) else None
            oldrow = before["poolPasses"][n][collection][i]
            old = oldrow
            for key in leaf:
                old = old.get(key, {}) if isinstance(old, dict) else {}
            if old != "00:01:37:24" or value_after != "":
                raise RuntimeError("Matrix proxy Out delta differs from retained capture")
            expected.add(("poolPasses", n, collection, i, *leaf))
    actual = set(_leaf_diffs(before["poolPasses"], after["poolPasses"], ("poolPasses",)))
    if before["timelinePasses"] != after["timelinePasses"] or actual != expected:
        raise RuntimeError("original queue attempt contains unrelated state changes")


def _pair(reader, resolve, config, identity, probe):
    _, expected = reader._manifest(config, Path(probe.ROOT).resolve(), probe)
    value = reader._read_pair(resolve, config, identity, expected, MATRIX_UID, probe)
    timeline, pool = reader._validate_read_pair(value, probe)
    return timeline, pool, value


def run(resolve, config, *, probe, reader=None):
    """Restore first-attempt settings; preserve all evidence and stop on drift."""
    if config.get("action") != "render-outer-recovery" or config.get("externalScriptingSetting") != "None":
        raise RuntimeError("wrong action or scripting mode")
    reader = reader or _load_reader()
    root = Path(probe.ROOT).resolve()
    output = Path(config.get("outputDir", ""))
    if (not output.is_absolute() or output.is_symlink() or output.parent.resolve() != (root / "out").resolve()
            or not output.name.startswith("issue-141-observation-")):
        raise RuntimeError("output directory is not owned")
    pin = Path(config.get("checkpointPath", ""))
    reader._pin(pin, config.get("checkpointName", ""), config.get("checkpointSha256", ""), probe)
    if config.get("timelineInventory") != "protected-six":
        raise RuntimeError("fresh protected-six checkpoint required")
    attempt = output / ATTEMPT
    journal = attempt / "journal.jsonl"
    xml = attempt / f"{PRESET}.drp" / f"{PRESET}.xml"
    for path, key in ((journal, "originalJournalSha256"), (xml, "originalXmlSha256")):
        if path.is_symlink() or not path.is_file() or _sha(path) != config.get(key):
            raise RuntimeError(f"original attempt evidence changed: {path.name}")
    if config.get("originalAttemptPath") != str(attempt):
        raise RuntimeError("original attempt path binding differs")
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    calls = [(r.get("method"), r.get("phase")) for r in rows]
    for method in ("SaveAsNewRenderPreset", "ExportRenderPreset", "SetRenderSettings"):
        requests = [r for r in rows if r.get("method") == method and r.get("phase") == "request"]
        returns = [r for r in rows if r.get("method") == method and r.get("phase") == "return"]
        if len(requests) != 1 or len(returns) != 1 or returns[0].get("value") is not True:
            raise RuntimeError("original journal does not prove exact successful snapshot/settings calls")
    if rows[[i for i, row in enumerate(rows) if row.get("method") == "SaveAsNewRenderPreset"][0]]["value"] != [PRESET]:
        raise RuntimeError("original journal preset name differs")
    if any(m in {"AddRenderJob", "StartRendering"} for m, _ in calls):
        raise RuntimeError("original attempt contains a queued or started render")
    visible_methods = ("GetCurrentRenderFormatAndCodec", "GetCurrentRenderMode", "GetRenderJobList", "IsRenderingInProgress", "GetRenderPresetList")
    save_index = next(i for i, row in enumerate(rows) if row.get("method") == "SaveAsNewRenderPreset" and row.get("phase") == "request")
    expected_visible = {}
    for method in visible_methods:
        reads = [i for i, row in enumerate(rows) if row.get("method") == method and row.get("phase") == "return" and i < save_index]
        if len(reads) < 2:
            raise RuntimeError("original journal lacks two visible-state reads before preset save")
        if method in {"GetCurrentRenderFormatAndCodec", "GetCurrentRenderMode"}:
            values = [rows[i]["value"] for i in reads]
            if any(value != values[0] for value in values):
                raise RuntimeError("original visible render format/mode was unstable")
            expected_visible[method] = values[0]
    base = next((r["value"] for r in rows if r.get("method") == "GetRenderPresetList" and r.get("phase") == "return"), None)
    if resolve.GetProductName() != "DaVinci Resolve Studio" or resolve.GetVersion() != BUILD:
        raise RuntimeError("Exact Resolve Studio 21.1.0 build 14 required")
    current = resolve.GetProjectManager().GetCurrentProject()
    presets = current.GetRenderPresetList()
    if (not isinstance(base, list) or presets != [*base, PRESET] or
            current.GetUniqueId() != PROJECT_ID or current.GetName() != PROJECT_NAME):
        raise RuntimeError("project or exact owned-preset inventory differs")
    xmlroot = ET.parse(xml).getroot()
    extra = {e.findtext("DbKey"): e.findtext("DbVal") for e in xmlroot.findall(".//ExtraInfoMap/Element")}
    if (xmlroot.findtext("RecordFormatType") != "mov" or
            xmlroot.findtext("RecordFormatSubType") != "avc1" or
            xmlroot.findtext("RecordAudioEnabled") != "true" or
            extra.get("aud_codec") != "lpcm"):
        raise RuntimeError("owned preset XML is not the retained MOV/H264/PCM preset")
    before_path, after_path = Path(config["originalBeforePairPath"]), Path(config["originalAfterPairPath"])
    if before_path != attempt / "full-pair-004.json" or after_path != attempt / "full-pair-005.json":
        raise RuntimeError("original pair paths differ from retained attempt")
    for path, key in ((before_path, "originalBeforePairSha256"), (after_path, "originalAfterPairSha256")):
        if path.is_symlink() or not path.is_file() or _sha(path) != config.get(key):
            raise RuntimeError("original full-state pair pin changed")
    before, after = json.loads(before_path.read_text()), json.loads(after_path.read_text())
    _only_captured_proxy_out(before, after)
    identity = {"projectId": PROJECT_ID}
    if resolve.GetProductName() != "DaVinci Resolve Studio" or resolve.GetVersion() != BUILD:
        raise RuntimeError("Exact Resolve Studio 21.1.0 build 14 required")
    identity["projectName"] = PROJECT_NAME
    _, expected_sources = reader._manifest(config, root, probe)
    timeline0, pool0, fresh = _pair(reader, resolve, config, identity, probe)
    checkpoint = json.loads(pin.read_text(encoding="utf-8"))
    reader._validate_read_pair(checkpoint, probe)
    if fresh != checkpoint:
        raise RuntimeError("fresh full-state pair differs from supplied checkpoint")
    allowed = ((before["timelinePasses"][0], before["poolPasses"][0]),
               (after["timelinePasses"][0], after["poolPasses"][0]))
    selected = next(((t, p) for t, p in allowed if (timeline0, pool0) == (t, p)), None)
    if selected is None or current.IsRenderingInProgress() is not False or current.GetRenderJobList() != []:
        raise RuntimeError("fresh state/jobs differ from retained before/after attempt state")
    target_t, target_p = selected
    journal_out = Path(config.get("journalPath", ""))
    if (journal_out.exists() or journal_out.is_symlink() or not journal_out.parent.is_dir()
            or journal_out.parent.is_symlink()
            or not journal_out.resolve().is_relative_to(attempt.resolve())):
        raise RuntimeError("recovery journal must be a new path contained in the owned attempt")
    # Retain raw pairs and hashes before any preset mutation.
    pair_dir = journal_out.parent
    for label, pair in (("fresh", fresh),):
        raw = pair_dir / f"{label}-pair.json"
        raw.write_text(json.dumps(pair, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        _log(journal_out, "FullPair", "captured-" + label, {"path": str(raw), "sha256": _sha(raw)})
    _log(journal_out, "LoadRenderPreset", "request", PRESET)
    loaded = current.LoadRenderPreset(PRESET)
    _log(journal_out, "LoadRenderPreset", "return", loaded)
    if loaded is not True:
        raise RuntimeError("LoadRenderPreset did not return True; preserve preset")
    def verify_visible():
        for method, expected_value in expected_visible.items():
            _log(journal_out, method, "request", [])
            actual = getattr(current, method)()
            _log(journal_out, method, "return", actual)
            if actual != expected_value:
                raise RuntimeError("loaded render format/mode differs; preserve owned preset")
    verify_visible()
    verify_visible()
    t1, p1, pair1 = _pair(reader, resolve, config, identity, probe)
    t2, p2, pair2 = _pair(reader, resolve, config, identity, probe)
    for label, pair in (("after-load-1", pair1), ("after-load-2", pair2)):
        raw = journal_out.parent / f"{label}-pair.json"
        raw.write_text(json.dumps(pair, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        _log(journal_out, "FullPair", "captured-" + label, {"path": str(raw), "sha256": _sha(raw)})
    if (t1 != target_t or p1 != target_p or t2 != target_t or p2 != target_p or
            pair1["timelinePasses"][0] != pair1["timelinePasses"][1] or
            pair1["poolPasses"][0] != pair1["poolPasses"][1] or
            pair2["timelinePasses"][0] != pair2["timelinePasses"][1] or
            pair2["poolPasses"][0] != pair2["poolPasses"][1] or
            current.GetRenderPresetList() != [*base, PRESET] or
            current.IsRenderingInProgress() is not False or current.GetRenderJobList() != []):
        raise RuntimeError("loaded visible state/pool differs; preserve owned preset")
    if current.GetRenderPresetList() != [*base, PRESET] or current.IsRenderingInProgress() is not False or current.GetRenderJobList() != []:
        raise RuntimeError("pre-delete owned preset/jobs/rendering guard failed")
    _log(journal_out, "DeleteRenderPreset", "request", PRESET)
    deleted = current.DeleteRenderPreset(PRESET)
    _log(journal_out, "DeleteRenderPreset", "return", deleted)
    if deleted is not True or current.GetRenderPresetList() != base:
        raise RuntimeError("owned preset cleanup refused or inventory differs")
    verify_visible()
    tf, pf, final = _pair(reader, resolve, config, identity, probe)
    if (tf != target_t or pf != target_p or final["timelinePasses"][0] != final["timelinePasses"][1]
            or final["poolPasses"][0] != final["poolPasses"][1]
            or current.GetRenderPresetList() != base or current.IsRenderingInProgress() is not False
            or current.GetRenderJobList() != []):
        raise RuntimeError("final protected state is not an equal restored pair")
    final_path = journal_out.parent / "final-pair.json"
    final_path.write_text(json.dumps(final, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    _log(journal_out, "FullPair", "captured-final", {"path": str(final_path), "sha256": _sha(final_path)})
    return {"status": "original-render-settings-restored", "loaded": True,
            "ownedPresetDeleted": True, "visiblePairPath": str(final_path),
            "visiblePairSha256": _sha(final_path),
            "hiddenRenderSettingsEquality": "not exposed by Resolve",
            "pcmOrRouteSupport": "not claimed", "evidencePreserved": True}
