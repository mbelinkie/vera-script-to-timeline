"""One hash-bound named-menu dispatch. A timeout never causes a second launch."""
import argparse
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / "out/issue149-workflow-reruns-20261002-kit-01"
PLUGINS = Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins")
CONFIG = PLUGINS / "vera-issue-149-workflow-reruns.json"
ENTRY = PLUGINS / "VERA Issue 149 Workflow Reruns.py"
HS = "/Applications/Hammerspoon.app/Contents/Frameworks/hs/hs"
PROJECT = "VERA Issue 149 Workflow Reruns 20261002-kit-01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(receipt):
    previous = set(receipt["previousResults"])
    found = [p for p in OUT.glob("vera-issue-149-workflow-reruns-result-*.json") if str(p) not in previous]
    if len(found) != 1:
        return {"status": "pending" if not found else "multiple-results-refused", "count": len(found), "retryAllowed": False}
    path = found[0]
    try:
        result = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"status": "result-write-pending", "retryAllowed": False}
    if result.get("actionId") != receipt["actionId"]:
        return {"status": "result-attribution-refused", "expectedActionId": receipt["actionId"],
                "observedActionId": result.get("actionId"), "retryAllowed": False}
    result_ref = {"path": str(path), "sha256": sha(path), "status": result.get("status"), "actionId": receipt["actionId"]}
    (OUT / "dispatches" / (receipt["actionId"] + "-result.json")).write_text(json.dumps(result_ref, indent=2) + "\n")
    return result_ref


def dispatch(params, initial=False):
    cfg = json.loads(params.read_text())
    if cfg.get("projectName", PROJECT) != PROJECT or cfg.get("externalScriptingSetting", "None") != "None":
        raise ValueError("Only the named new project under the None attestation is allowed")
    aid = cfg.get("actionId", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", aid):
        raise ValueError("A unique safe actionId is required")
    if initial and cfg.get("action") not in {"context", "prepare"}:
        raise ValueError("Initial Project Manager permission is context/prepare only")
    if not initial and cfg.get("action") in {"context", "prepare"}:
        raise ValueError("Creation requires the explicit initial guard")
    if cfg.get("outputDir", str(OUT)) != str(OUT) or cfg.get("mediaDir", str(OUT / "media")) != str(OUT / "media"):
        raise ValueError("Unexpected output/media directory")
    # A receipt with no terminal native result is an uncertain dispatch, never permission to advance.
    for prior in (OUT / "dispatches").glob("*.json"):
        value = json.loads(prior.read_text())
        if isinstance(value, dict) and "previousResults" in value and "config" in value:
            terminal = prior.with_name(value["actionId"] + "-result.json")
            if not terminal.exists() and not value.get("rootReviewedBeforeNativeRefusal", False):
                raise ValueError("Previous dispatch pending/refused; collect or retain root review: " + prior.name)
    if CONFIG.exists():
        previous = json.loads(CONFIG.read_text())
        if previous.get("action") not in {"observe", "disarmed", "__disarmed__"}:
            raise ValueError("Previous configuration is still armed; retain evidence before any next stage")
    if not ENTRY.is_file() or sha(ENTRY) != sha(HERE / "launcher.py"):
        raise ValueError("Installed launcher differs from reviewed source")
    source = HERE / "harness.py"
    digest = sha(source)
    if cfg.get("probeSha256") != digest or cfg.get("launcherSha256") != sha(ENTRY):
        raise ValueError("Source changed since parameter review; no staging or dispatch")
    archive = OUT / "sources" / digest / "harness.py"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists() and sha(archive) != digest:
        raise ValueError("Immutable source archive changed")
    if not archive.exists():
        archive.write_bytes(source.read_bytes())
    cfg.update(schemaVersion="issue-149-workflow-reruns-v1", projectName=PROJECT,
               externalScriptingSetting="None", outputDir=str(OUT), mediaDir=str(OUT / "media"),
               probePath=str(archive), probeSha256=digest, launcherPath=str(ENTRY), launcherSha256=sha(ENTRY))
    folder = OUT / "dispatches"
    folder.mkdir(parents=True, exist_ok=True)
    receipt_path = folder / (aid + ".json")
    receipt = {"actionId": aid, "at": datetime.now(UTC).isoformat(), "config": cfg,
               "launcherSha256": sha(ENTRY), "macroSha256": sha(HERE / "hammerspoon-launch.lua"),
               "previousResults": [str(p) for p in OUT.glob("vera-issue-149-workflow-reruns-result-*.json")],
               "retryAllowed": False}
    # Exclusive receipt precedes staging and launch. A failed/uncertain dispatch is retained.
    with receipt_path.open("x") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    CONFIG.write_text(json.dumps(cfg, indent=2) + "\n")
    lua = "return dofile(" + json.dumps(str(HERE / "hammerspoon-launch.lua")) + ").run(" + ("true" if initial else "false") + ")"
    try:
        done = subprocess.run([HS, "-c", lua], capture_output=True, text=True, timeout=30)
        launch = {"exitCode": done.returncode, "stdout": done.stdout, "stderr": done.stderr}
    except subprocess.TimeoutExpired as exc:
        launch = {"status": "dispatch-process-timeout", "stdout": str(exc.stdout), "stderr": str(exc.stderr)}
    (folder / (aid + "-launch.json")).write_text(json.dumps(launch, indent=2) + "\n")
    print(json.dumps({"receipt": str(receipt_path), "launch": launch, "result": collect(receipt)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("params", type=Path)
    parser.add_argument("--initial", action="store_true")
    parser.add_argument("--collect", action="store_true")
    args = parser.parse_args()
    if args.collect:
        print(json.dumps(collect(json.loads(args.params.read_text())), indent=2))
    else:
        dispatch(args.params, args.initial)
