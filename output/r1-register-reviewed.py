#!/usr/bin/env python3
"""Register the reviewed local-only R1 actions without dispatching Resolve."""

import ast
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/issue-141-observation-20260930-01a0f318"
HERE = ROOT / "docs/investigations/issue-141"
PROBE = HERE / "probe.py"
CALLER = OUT / "independent-native-call.py"
CONFIG = Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins/vera-issue-141-observation.json")
HELPER = HERE / "r1-repeat-six.py"
SNAPSHOT = OUT / "r1-repeat-six-probe-snapshot-54bbbeee926a.py"
READER = HERE / "r4-range-repair.py"
CHECK = HERE / "r1-repeat-six-check.py"
DISPATCH_CHECK = HERE / "dispatch-registration-check.py"
EXPECTED_PROBE = "54bbbeee926a5ef423615b1f981ec8ebe6586e91f938a8aad05db441ecc53310"
EXPECTED_CALLER = "9bf342020431dc8059fb7a8b60976483826c285c1e9ce8ef671293c1b9c03d9e"
HELPER_HASH = "4aece3d8ab7c7e0ab215fc9eb841fc95b56b85fb0809859e7f587ce83b0e2c28"
SNAPSHOT_HASH = EXPECTED_PROBE
READER_HASH = "9b6977747a1f3decf957ead6134f10fc4f597bf9d0c3dc5c081b7bf2671879a4"
CASE = "R1-repeat-six"
ACTIONS = ("r1-repeat-reopen", "r1-repeat-duplicate")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pin(path, expected):
    if path.is_symlink() or not path.is_file() or sha(path.read_bytes()) != expected:
        raise RuntimeError(f"reviewed pin differs: {path}")


def replace_once(source, old, new, label):
    if source.count(old) != 1:
        raise RuntimeError(f"expected one source anchor for {label}")
    return source.replace(old, new, 1)


def transform(probe_source, caller_source):
    probe_new = probe_source
    probe_new = replace_once(
        probe_new,
        '        "r3-boundary-a3-split-review",\n        "offline-cycle",\n        "offline-picture-continuation",\n        "matrix-checkpoint",',
        '        "r3-boundary-a3-split-review",\n        "r1-repeat-reopen",\n        "r1-repeat-duplicate",\n        "offline-cycle",\n        "offline-picture-continuation",\n        "matrix-checkpoint",',
        "probe config allowlist",
    )
    probe_new = replace_once(
        probe_new,
        '        "r3-boundary-a3-split-review",\n        "offline-cycle",\n        "offline-picture-continuation",\n    }:',
        '        "r3-boundary-a3-split-review",\n        "r1-repeat-reopen",\n        "r1-repeat-duplicate",\n        "offline-cycle",\n        "offline-picture-continuation",\n    }:',
        "probe runtime action gate",
    )
    probe_new = replace_once(
        probe_new,
        '            "offline-cycle": (\n                "offline-cycle.py",\n                "0cb39d2479a15071052523b2525bcde392c07f71d68ad9843245b61195ded092",\n            ),\n',
        '            "offline-cycle": (\n                "offline-cycle.py",\n                "0cb39d2479a15071052523b2525bcde392c07f71d68ad9843245b61195ded092",\n            ),\n'
        f'            "r1-repeat-reopen": ("r1-repeat-six.py", "{HELPER_HASH}"),\n'
        f'            "r1-repeat-duplicate": ("r1-repeat-six.py", "{HELPER_HASH}"),\n',
        "probe owned-module pins",
    )

    caller_new = caller_source
    caller_new = replace_once(
        caller_new,
        '    "r3-boundary-a3-prepare", "r3-boundary-a3-split-ready", "r3-boundary-a3-split-review",\n}',
        '    "r3-boundary-a3-prepare", "r3-boundary-a3-split-ready", "r3-boundary-a3-split-review",\n'
        '    "r1-repeat-reopen", "r1-repeat-duplicate",\n}',
        "caller action allowlist",
    )
    caller_new = replace_once(
        caller_new,
        'DISPATCH_MODULES = {\n    "editorial-readback": (',
        'DISPATCH_MODULES = {\n'
        f'    "r1-repeat-reopen": ("r1-repeat-six.py", "{HELPER_HASH}"),\n'
        f'    "r1-repeat-duplicate": ("r1-repeat-six.py", "{HELPER_HASH}"),\n'
        '    "editorial-readback": (',
        "caller reviewed helper pins",
    )
    caller_new = replace_once(
        caller_new,
        '        if updates["action"] != "editorial-readback":\n            assert updates.get("case", "").startswith(("R2-", "R3-"))',
        '        if updates["action"] in {"r1-repeat-reopen", "r1-repeat-duplicate"}:\n'
        f'            assert updates.get("case") == {CASE!r}\n'
        '        elif updates["action"] != "editorial-readback":\n'
        '            assert updates.get("case", "").startswith(("R2-", "R3-"))',
        "caller exact R1 case allowance",
    )
    caller_new = replace_once(
        caller_new,
        '    validate({"action": "editorial-case-prepare", "case": "R2-linked"}, None)\n',
        '    validate({"action": "editorial-case-prepare", "case": "R2-linked"}, None)\n'
        f'    validate({{"action": "r1-repeat-reopen", "case": {CASE!r}}}, None)\n'
        f'    validate({{"action": "r1-repeat-duplicate", "case": {CASE!r}}}, None)\n',
        "caller positive R1 cases",
    )
    caller_new = replace_once(
        caller_new,
        f'    validate({{"action": "r1-repeat-duplicate", "case": {CASE!r}}}, None)\n',
        f'    validate({{"action": "r1-repeat-duplicate", "case": {CASE!r}}}, None)\n'
        '    assert_dispatch_module("r1-repeat-reopen")\n'
        '    assert_dispatch_module("r1-repeat-duplicate")\n',
        "caller helper dispatch pins",
    )
    caller_new = replace_once(
        caller_new,
        '    for updates, menu in [({"action": "prepare"}, None), ({"action": "editorial-case-prepare", "case": "R1-copy"}, None),',
        '    for updates, menu in [({"action": "prepare"}, None), '
        f'({{"action": "r1-repeat-duplicate", "case": "R1-copy"}}, None), '
        '({"action": "editorial-case-prepare", "case": "R1-copy"}, None),',
        "caller R1-copy refusal",
    )
    ast.parse(probe_new)
    ast.parse(caller_new)
    probe_tree = ast.parse(probe_new)
    allowed_sets = [ast.literal_eval(node) for node in ast.walk(probe_tree)
                    if isinstance(node, ast.Set) and isinstance(node.elts[0] if node.elts else None, ast.Constant)
                    and "prepare" in {e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}]
    runtime_sets = [ast.literal_eval(node.comparators[0]) for node in ast.walk(probe_tree)
                    if isinstance(node, ast.Compare) and len(node.comparators) == 1
                    and isinstance(node.comparators[0], ast.Set)
                    and any(isinstance(e, ast.Constant) and e.value == "av-output" for e in node.comparators[0].elts)]
    assert any(set(ACTIONS) <= allowed for allowed in allowed_sets)
    assert any(set(ACTIONS) <= runtime for runtime in runtime_sets)
    tables = [ast.literal_eval(node.value) for node in ast.walk(probe_tree)
              if isinstance(node, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "owned_modules" for t in node.targets)]
    assert len(tables) == 1
    for action in ACTIONS:
        assert tables[0][action] == ("r1-repeat-six.py", HELPER_HASH)
    caller_tree = ast.parse(caller_new)
    action_sets = [ast.literal_eval(node.value) for node in ast.walk(caller_tree)
                   if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "ACTIONS" for t in node.targets)]
    dispatch_sets = [ast.literal_eval(node.value) for node in ast.walk(caller_tree)
                     if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "DISPATCH_MODULES" for t in node.targets)]
    assert len(action_sets) == len(dispatch_sets) == 1
    for action in ACTIONS:
        assert action in action_sets[0]
        assert dispatch_sets[0][action] == ("r1-repeat-six.py", HELPER_HASH)
    namespace = {"__name__": "reviewed_registration_check", "__file__": str(CALLER)}
    exec(compile(caller_new, str(CALLER), "exec"), namespace)
    for action in ACTIONS:
        namespace["validate"]({"action": action, "case": CASE}, None)
        try:
            namespace["validate"]({"action": action, "case": "R1-copy"}, None)
        except AssertionError:
            pass
        else:
            raise AssertionError("R1-copy was admitted for repeat action")
    return probe_new, caller_new


def main():
    check_only = sys.argv[1:] == ["--check"]
    if sys.argv[1:] not in ([], ["--check"]):
        raise RuntimeError("Usage: r1-register-reviewed.py [--check]")
    if OUT.is_symlink() or OUT.resolve().parent != (ROOT / "out").resolve():
        raise RuntimeError("Unexpected issue-141 output root")
    pin(PROBE, EXPECTED_PROBE)
    pin(CALLER, EXPECTED_CALLER)
    pin(HELPER, HELPER_HASH)
    pin(SNAPSHOT, SNAPSHOT_HASH)
    pin(READER, READER_HASH)
    if CONFIG.is_symlink() or not CONFIG.is_file():
        raise RuntimeError("Installed config is missing or a symlink")
    config_bytes = CONFIG.read_bytes()
    config = json.loads(config_bytes)
    if (config.get("action") != "observe" or config.get("timelineInventory") != "protected-six"
            or config.get("externalScriptingSetting") != "None"
            or config.get("probePath") != str(PROBE) or config.get("probeSha256") != EXPECTED_PROBE
            or config.get("projectName") != "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
            or Path(config.get("outputDir", "")).resolve() != OUT.resolve()):
        raise RuntimeError("Installed config is not the pinned observe/protected-six state")

    probe_new, caller_new = transform(PROBE.read_text(encoding="utf-8"), CALLER.read_text(encoding="utf-8"))
    new_probe_hash = sha(probe_new.encode())
    if check_only:
        print(json.dumps({"status": "registration-transform-valid", "probeAfterSha256": new_probe_hash,
                          "callerAfterSha256": sha(caller_new.encode()), "actions": list(ACTIONS),
                          "r1CopyRefused": True, "filesWritten": False, "nativeDispatchPerformed": False}, sort_keys=True))
        return

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    audit = OUT / f"r1-registration-{stamp}"
    audit.mkdir(exist_ok=False)
    (audit / "probe.py.before").write_bytes(PROBE.read_bytes())
    (audit / "independent-native-call.py.before").write_bytes(CALLER.read_bytes())
    (audit / "installed-config.json.before").write_bytes(config_bytes)
    (audit / "pins.json").write_text(json.dumps({
        "probeBeforeSha256": EXPECTED_PROBE,
        "probeAfterSha256": new_probe_hash,
        "callerBeforeSha256": EXPECTED_CALLER,
        "callerAfterSha256": sha(caller_new.encode()),
        "helperSha256": HELPER_HASH,
        "snapshotSha256": SNAPSHOT_HASH,
        "readerSha256": READER_HASH,
        "actions": list(ACTIONS),
        "case": CASE,
        "nativeDispatchPerformed": False,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    try:
        PROBE.write_text(probe_new, encoding="utf-8")
        CALLER.write_text(caller_new, encoding="utf-8")
        config["probeSha256"] = new_probe_hash
        if config.get("action") != "observe" or config.get("timelineInventory") != "protected-six":
            raise RuntimeError("Config action/inventory changed during registration")
        CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        pin(PROBE, new_probe_hash)
        pin(CALLER, sha(caller_new.encode()))
        fresh = json.loads(CONFIG.read_text(encoding="utf-8"))
        if fresh.get("probeSha256") != new_probe_hash or fresh.get("action") != "observe" or fresh.get("timelineInventory") != "protected-six":
            raise RuntimeError("Installed config did not stay observe/protected-six")
        run = subprocess.run([sys.executable, "-S", str(CHECK)], cwd=ROOT, check=True)
        dispatch_check = subprocess.run([sys.executable, "-S", str(DISPATCH_CHECK)], cwd=ROOT, check=True)
        caller_check = subprocess.run([sys.executable, "-S", str(CALLER), "--check"], cwd=ROOT, check=True)
        (audit / "checks.json").write_text(json.dumps({
            "repeatCheckExit": run.returncode,
            "dispatchCheckExit": dispatch_check.returncode,
            "callerCheckExit": caller_check.returncode,
            "installedAction": fresh["action"],
            "installedTimelineInventory": fresh["timelineInventory"],
            "installedProbeSha256": fresh["probeSha256"],
            "nativeDispatchPerformed": False,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        PROBE.write_bytes((audit / "probe.py.before").read_bytes())
        CALLER.write_bytes((audit / "independent-native-call.py.before").read_bytes())
        CONFIG.write_bytes((audit / "installed-config.json.before").read_bytes())
        raise
    print(json.dumps({"status": "registered-reviewed-actions", "audit": str(audit),
                      "probeSha256": new_probe_hash, "callerSha256": sha(caller_new.encode()),
                      "configAction": "observe", "timelineInventory": "protected-six",
                      "nativeDispatchPerformed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
