"""Single fixed-menu, read-only protected-six R4 pool dispatch."""
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
PLUGINS = Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins")
CONFIG = PLUGINS / "vera-issue-141-observation.json"
PROBE = ROOT / "docs/investigations/issue-141/probe.py"
MACRO = ROOT / "docs/investigations/issue-141/hammerspoon-launch.lua"
HS = "/Applications/Hammerspoon.app/Contents/Frameworks/hs/hs"
PROJECT = "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
PROTECTED = "protected-six"
PROBE_SHA = "cad63c88f400897fa37bc558d76fca410b7040bf1cc6b2a4ff270e0754b62fa8"
MACRO_SHA = "f3c9a76b5c95f6fbb04d546f33a5ae23d37579e8f890851a86f3daf9a9d5f5b1"
PROTECTED_UID = "be5f1584-f0c4-4dd9-988b-73f3167e77d1"
PROTECTED_NAME = "semi1b.mp4"
TIMELINES = {
    "29ae8331-b86e-4041-a548-960695cc7b24": "VERA 141 Batched Matrix",
    "64de8a4c-86bd-4f19-9d20-47b8940f610b": "VERA 141 R4 availability",
    "88f7923d-55a7-471f-b09b-cf10f9fae8ad": "VERA 141 Baseline",
    "aa2b8e36-83bd-4292-9e33-217c00ca192f": "VERA 141 R1 identity",
    "21436b8f-057c-49e6-80ba-5f733abe87b2": "transcription test 1",
    "2db0b2d1-6d81-48d4-b49c-360f56e012cd": "transcription test 2",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def uid_name_rows(rows):
    found = {}
    for row in rows:
        uid = row.get("GetUniqueId", {}).get("value")
        name = row.get("GetName", {}).get("value")
        if not isinstance(uid, str) or not isinstance(name, str) or uid in found:
            raise RuntimeError("timeline identity missing or duplicated")
        found[uid] = name
    return found


def iter_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def media_records(value):
    return [
        node
        for node in iter_dicts(value)
        if node.get("GetUniqueId", {}).get("value") == PROTECTED_UID
    ]


def validate_native(result_path):
    summary = json.loads(result_path.read_text(encoding="utf-8"))
    if summary.get("status") != "equal-read-only-pool-inventory":
        raise RuntimeError(f"native status is {summary.get('status')!r}")
    inventory_ref = summary.get("inventoryPath")
    if not isinstance(inventory_ref, str) or not inventory_ref:
        raise RuntimeError("native result has no inventory binding")
    inventory_path = Path(inventory_ref)
    if not inventory_path.is_file():
        raise RuntimeError("bound pool inventory is missing")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if inventory.get("status") != "equal-read-only-pool-inventory":
        raise RuntimeError("bound pool inventory status differs")
    if inventory.get("capture") != summary.get("capture"):
        raise RuntimeError("native summary/capture binding differs from inventory")
    if inventory.get("contextBefore") != inventory.get("contextAfter"):
        raise RuntimeError("read-only context changed")
    pool_passes = inventory.get("passes")
    if not isinstance(pool_passes, list) or len(pool_passes) != 2 or pool_passes[0] != pool_passes[1]:
        raise RuntimeError("pool passes are missing or unequal")
    pool = pool_passes[0]
    pool_rows = pool.get("timelineMappings")
    if not isinstance(pool_rows, list) or uid_name_rows([
        {"GetUniqueId": row.get("timelineUid"), "GetName": row.get("timelineName")}
        for row in pool_rows
    ]) != TIMELINES:
        raise RuntimeError("pool timeline inventory is not the exact protected six")
    capture_summary = summary.get("capture")
    capture_path = Path(capture_summary.get("capturePath", "")) if isinstance(capture_summary, dict) else Path()
    if not capture_path.is_file():
        raise RuntimeError("full timeline capture path is missing")
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    if capture.get("consistency") != "equal-adjacent-reads":
        raise RuntimeError("timeline capture is not equal-adjacent-reads")
    timeline_passes = capture.get("passes")
    if not isinstance(timeline_passes, list) or len(timeline_passes) != 2 or timeline_passes[0] != timeline_passes[1]:
        raise RuntimeError("timeline passes are missing or unequal")
    state = timeline_passes[0]
    if state.get("timelineInventory") != PROTECTED:
        raise RuntimeError("timeline capture lacks protected-six metadata")
    if uid_name_rows(state.get("timelines", [])) != TIMELINES:
        raise RuntimeError("timeline capture is not the exact protected six")
    protected = media_records(state) + media_records(pool)
    if not protected:
        raise RuntimeError("protected source UID absent from item/pool evidence")
    for record in protected:
        if record.get("GetName") != {"value": PROTECTED_NAME}:
            raise RuntimeError("protected source name changed")
        source = record.get("sourceBytes", {})
        if source.get("status") != "protected-locator-not-accessed" or "sha256" in source or "hashMatches" in source:
            raise RuntimeError("protected source was hashed or lacked protected status")
    reachable = [node for node in iter_dicts(state) if node.get("sourceBytes", {}).get("status") == "reachable"]
    if not reachable or any(node["sourceBytes"].get("hashMatches") is not True for node in reachable):
        raise RuntimeError("generated source byte verification is absent or failed")
    return {
        "status": "pass",
        "timelineInventory": PROTECTED,
        "timelineCount": len(state["timelines"]),
        "poolPasses": 2,
        "timelinePasses": 2,
        "protectedEvidenceCount": len(protected),
        "generatedReachableEvidenceCount": len(reachable),
        "capturePath": str(capture_path),
        "captureSha256": capture_summary.get("sha256"),
        "resultPath": str(result_path),
        "resultSha256": sha(result_path),
        "inventoryPath": str(inventory_path),
        "inventorySha256": sha(inventory_path),
    }


def offline_check(result_path, audit):
    """Validate retained native bindings without Resolve or media access."""
    audit = Path(audit)
    staged = json.loads((audit / "staged-config.json").read_text(encoding="utf-8"))
    drift = json.loads((audit / "configuration-drift.json").read_text(encoding="utf-8"))
    expected_disarm = {**staged, "action": "observe", "stage": "baseline-repeat"}
    if drift != expected_disarm:
        raise RuntimeError("retained configuration drift is not the exact launcher self-disarm")
    restored = json.loads((audit / "configuration-restored-after-review.json").read_text(encoding="utf-8"))
    if restored.get("restored") is not True or restored.get("action") != "observe":
        raise RuntimeError("retained configuration restoration is incomplete")
    review = validate_native(Path(result_path))
    summary = json.loads(Path(result_path).read_text(encoding="utf-8"))
    inventory_path = Path(summary["inventoryPath"])
    capture_path = Path(summary["capture"]["capturePath"])
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    pair = {
        "poolConsistency": "equal-adjacent-reads",
        "poolPasses": inventory["passes"],
        "selectedTimelineUid": "21436b8f-057c-49e6-80ba-5f733abe87b2",
        "timelineConsistency": capture["consistency"],
        "timelineInventory": PROTECTED,
        "timelinePasses": capture["passes"],
    }
    reader_path = ROOT / "docs/investigations/issue-141/r4-range-repair.py"
    if sha(reader_path) != "9b6977747a1f3decf957ead6134f10fc4f597bf9d0c3dc5c081b7bf2671879a4":
        raise RuntimeError("reviewed R4 reader hash changed")
    import importlib.util
    import sys as _sys
    probe_spec = importlib.util.spec_from_file_location("issue141_probe_check", PROBE)
    reader_spec = importlib.util.spec_from_file_location("issue141_reader_check", reader_path)
    if probe_spec is None or reader_spec is None or probe_spec.loader is None or reader_spec.loader is None:
        raise RuntimeError("could not load reviewed readers")
    probe = importlib.util.module_from_spec(probe_spec)
    reader = importlib.util.module_from_spec(reader_spec)
    _sys.modules[probe_spec.name] = probe
    probe_spec.loader.exec_module(probe)
    reader_spec.loader.exec_module(reader)
    state, pool = reader._validate_read_pair(pair, probe)
    if state != capture["passes"][0] or pool != inventory["passes"][0]:
        raise RuntimeError("validated pair does not preserve exact native passes")
    pair_path = audit / "pair.json"
    write(pair_path, pair)
    bindings = {
        "summary": {"path": str(result_path), "sha256": sha(Path(result_path))},
        "inventory": {"path": str(inventory_path), "sha256": sha(inventory_path)},
        "capture": {"path": str(capture_path), "sha256": sha(capture_path)},
        "selectedTimelineUid": pair["selectedTimelineUid"],
        "timelineInventory": PROTECTED,
    }
    write(audit / "pair-bindings.json", bindings)
    review.update({"pairPath": str(pair_path), "pairSha256": sha(pair_path)})
    write(audit / "offline-review.json", review)
    return review


def dispatch():
    if sha(PROBE) != PROBE_SHA or sha(MACRO) != MACRO_SHA:
        raise RuntimeError("reviewed source hash changed")
    original = CONFIG.read_bytes()
    before = json.loads(original)
    if (
        before.get("action") != "observe"
        or before.get("externalScriptingSetting") != "None"
        or before.get("projectName") != PROJECT
    ):
        raise RuntimeError("private configuration is not the approved idle baseline")
    audit = OUT / ("protected-six-r4-pool-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ"))
    audit.mkdir()
    write(audit / "previous-config.json", before)
    check = subprocess.run(
        [HS, "-c", "return dofile(" + json.dumps(str(MACRO)) + ").check()"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    write(audit / "project-check.json", {"exitCode": check.returncode, "stdout": check.stdout, "stderr": check.stderr})
    if check.returncode != 0:
        raise RuntimeError("approved project check refused")
    try:
        checked = json.loads(check.stdout.strip())
    except json.JSONDecodeError as error:
        raise RuntimeError("approved project check was not JSON") from error
    if checked.get("windowTitle") != PROJECT or checked.get("menuFound") is not True or checked.get("menuEnabled") is not True:
        raise RuntimeError("exact project/menu preflight failed")
    staged = {
        **before,
        "action": "r4-pool-read-only",
        "stage": "R4-protected-six-pool-read-only",
        "probePath": str(PROBE),
        "probeSha256": PROBE_SHA,
        "timelineInventory": PROTECTED,
    }
    write(audit / "staged-config.json", staged)
    CONFIG.write_text(json.dumps(staged, indent=2) + "\n", encoding="utf-8")
    prior = set(PLUGINS.glob("vera-issue-141-observation-result-*.json"))
    try:
        launch = subprocess.run(
            [HS, "-c", "return dofile(" + json.dumps(str(MACRO)) + ").run()"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        write(audit / "launch.json", {"exitCode": launch.returncode, "stdout": launch.stdout, "stderr": launch.stderr})
        if launch.returncode != 0:
            raise RuntimeError("fixed menu dispatch refused; no retry")
        deadline = time.monotonic() + 120
        result_path = None
        while time.monotonic() < deadline:
            fresh = set(PLUGINS.glob("vera-issue-141-observation-result-*.json")) - prior
            if len(fresh) > 1:
                raise RuntimeError("multiple native results appeared; stop")
            if fresh:
                candidate = fresh.pop()
                try:
                    json.loads(candidate.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    time.sleep(0.2)
                    continue
                result_path = candidate
                break
            time.sleep(0.2)
        if result_path is None:
            raise RuntimeError("native result pending after one dispatch; do not retry")
        write(audit / "result-reference.json", {"path": str(result_path), "sha256": sha(result_path)})
        review = validate_native(result_path)
        write(audit / "native-review.json", review)
        return {"auditDirectory": str(audit), "review": review}
    finally:
        live = json.loads(CONFIG.read_text(encoding="utf-8"))
        disarmed = {**staged, "action": "observe", "stage": "baseline-repeat"}
        if live not in (staged, disarmed):
            write(audit / "configuration-drift.json", live)
            raise RuntimeError("private configuration changed unexpectedly; retain and stop")
        CONFIG.write_bytes(original)
        write(audit / "configuration-restored.json", {"restored": CONFIG.read_bytes() == original, "action": json.loads(original).get("action")})


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--check":
        print(json.dumps(offline_check(sys.argv[2], sys.argv[3]), sort_keys=True))
    elif len(sys.argv) == 1:
        print(json.dumps(dispatch(), sort_keys=True))
    else:
        raise SystemExit("usage: dispatch.py [--check SUMMARY_PATH AUDIT_DIR]")
