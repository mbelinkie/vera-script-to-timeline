"""Single audited independent action; never retries or handles Copy/Paste."""

import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
HERE = ROOT / "docs/investigations/issue-141"
PLUGINS = Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins")
CONFIG = PLUGINS / "vera-issue-141-observation.json"
HS = "/Applications/Hammerspoon.app/Contents/Frameworks/hs/hs"
HASHES = {
    "hammerspoon-launch.lua": "f3c9a76b5c95f6fbb04d546f33a5ae23d37579e8f890851a86f3daf9a9d5f5b1",
    "hammerspoon-editorial.lua": "47b6ec354c00e3ef1296a70c29e8846e1661fef692177d90bc96f27ba5b6bc6d",
}
ACTIONS = {
    "editorial-readback", "editorial-case-prepare", "editorial-case-restore",
    "editorial-case-review-preparation",
    "av-output-queue-from-fresh-checkpoint",
    "av-output-drop-unstarted-owned-job",
    "av-output-full-matrix", "av-output-full-matrix-queue-only",
    "r2-linked-second-position", "r2-linked-interval-delete",
    "r2-named-split-ready", "r2-named-split-review",
    "r3-boundary-a3-prepare", "r3-boundary-a3-split-ready", "r3-boundary-a3-split-review",
}
IMMUTABLE = {"projectName", "externalScriptingSetting", "mediaDir", "outputDir", "manifestSha256", "probePath", "probeSha256"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(updates, menu):
    if menu is not None:
        assert updates is None and menu in {"edit-page", "step-forward", "timeline-start", "save-project", "focus-timeline", "auto-none", "auto-v1", "auto-a1", "auto-a3", "deselect", "select", "split", "nudge-right"}
    else:
        assert isinstance(updates, dict) and updates.get("action") in ACTIONS
        assert not IMMUTABLE.intersection(updates)
        if updates["action"] != "editorial-readback":
            assert updates.get("case", "").startswith(("R2-", "R3-"))


def invoke(updates=None, menu=None):
    validate(updates, menu)
    config = json.loads(CONFIG.read_text())
    assert config["action"] == "observe" and config["externalScriptingSetting"] == "None"
    assert config.get("timelineInventory") == "protected-six"
    assert config["projectName"] == "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
    assert Path(config["outputDir"]).resolve() == OUT
    assert Path(config["probePath"]) == HERE / "probe.py"
    assert config["probeSha256"] == sha(HERE / "probe.py")
    filename = "hammerspoon-launch.lua" if menu is None else "hammerspoon-editorial.lua"
    macro = HERE / filename
    assert not macro.is_symlink() and sha(macro) == HASHES[filename]
    prior = set(PLUGINS.glob("vera-issue-141-observation-result-*.json"))
    directory = OUT / datetime.now(UTC).strftime("independent-action-%Y%m%dT%H%M%S.%fZ")
    directory.mkdir()
    (directory / "previous-config.json").write_text(json.dumps(config, indent=2) + "\n")
    if updates is not None:
        config.update(updates, timelineInventory="protected-six")
        (directory / "staged-config.json").write_text(json.dumps(config, indent=2) + "\n")
        CONFIG.write_text(json.dumps(config, indent=2) + "\n")
    lua = "return dofile(" + json.dumps(str(macro)) + ").run("
    lua += "" if menu is None else json.dumps(menu)
    lua += ")"
    returned = subprocess.run([HS, "-c", lua], capture_output=True, text=True, timeout=10)
    (directory / "launch.json").write_text(json.dumps({"menu": menu, "sourceSha256": sha(macro), "exitCode": returned.returncode, "stdout": returned.stdout, "stderr": returned.stderr}, indent=2) + "\n")
    if returned.returncode != 0:
        # Disarm only the staged local configuration. No Resolve retry/cleanup.
        live = json.loads(CONFIG.read_text())
        live.update(action="observe", stage="baseline-repeat")
        CONFIG.write_text(json.dumps(live, indent=2) + "\n")
        raise RuntimeError("Menu refused; evidence at " + str(directory / "launch.json"))
    if menu is not None:
        return {"auditDirectory": str(directory), "menu": menu, "dispatched": True}
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        fresh = set(PLUGINS.glob("vera-issue-141-observation-result-*.json")) - prior
        if fresh:
            assert len(fresh) == 1, "Multiple native results; stop"
            path = fresh.pop()
            try:
                result = json.loads(path.read_text())
            except json.JSONDecodeError:
                time.sleep(.2)
                continue
            (directory / "result-reference.json").write_text(json.dumps({"path": str(path), "sha256": sha(path)}, indent=2) + "\n")
            return {**result, "_nativeResultPath": str(path), "_auditDirectory": str(directory)}
        time.sleep(.2)
    raise RuntimeError("Native result pending; do not relaunch; evidence at " + str(directory))


def demo():
    validate({"action": "editorial-readback"}, None)
    validate({"action": "editorial-case-prepare", "case": "R2-linked"}, None)
    for updates, menu in [({"action": "prepare"}, None), ({"action": "editorial-case-prepare", "case": "R1-copy"}, None), ({"action": "editorial-readback", "externalScriptingSetting": "Local"}, None), (None, "paste")]:
        try:
            validate(updates, menu)
        except AssertionError:
            pass
        else:
            raise AssertionError("Unapproved action accepted")
    print("Independent action input guards pass; no native action.")


if __name__ == "__main__":
    assert sys.argv[1:] == ["--check"]
    demo()
