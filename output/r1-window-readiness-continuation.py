#!/usr/bin/env python3
"""Use the reviewed R1 executor with continuation-only evidence paths."""

import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
DRIVER = OUTPUT / "r1-final-native-executor-20261002.py"
READINESS = OUTPUT / "r1-window-readiness-continuation-readiness.json"
STATE = OUTPUT / "r1-window-readiness-continuation-state.json"
DECISION = OUTPUT / "r1-window-readiness-continuation-decision.json"
CURRENT_WINDOW = OUTPUT / "r1-current-window-readiness.json"
PRIOR_STATE = OUTPUT / "r1-final-native-executor-20261002-state.json"
PRIOR_READINESS = OUTPUT / "r1-final-native-executor-20261002-readiness.json"
PRIOR_LAUNCH = ROOT / "out/issue-141-observation-20260930-01a0f318/independent-action-20261002T125424.498570Z/launch.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_driver():
    if sha(DRIVER) != "375263529a07069bdf9c6acfb58645b8567b931e61afdc63ca5feb32cbb8b78e":
        raise RuntimeError("Reviewed executor source changed")
    spec = importlib.util.spec_from_file_location("issue141_executor_continuation", DRIVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.READINESS = READINESS
    module.STATE = STATE
    return module


def add_provenance():
    record = json.loads(READINESS.read_text(encoding="utf-8"))
    record["status"] = "continuation-authorized-before-restore"
    record["continuationProvenance"] = {
        "priorTerminalState": {"path": str(PRIOR_STATE), "sha256": sha(PRIOR_STATE)},
        "priorTerminalReadiness": {"path": str(PRIOR_READINESS), "sha256": sha(PRIOR_READINESS)},
        "priorMenuRefusal": {"path": str(PRIOR_LAUNCH), "sha256": sha(PRIOR_LAUNCH)},
        "currentWindowReadiness": {"path": str(CURRENT_WINDOW), "sha256": sha(CURRENT_WINDOW)},
        "coordinatorDecision": {"path": str(DECISION), "sha256": sha(DECISION)},
        "driver": {"path": str(DRIVER), "sha256": sha(DRIVER)},
        "authorizedAction": "one r1-repeat-restore-selection; no duplicate",
        "preparedAt": datetime.now(UTC).isoformat(),
    }
    READINESS.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    if sys.argv[1:] == ["--prepare"]:
        driver = load_driver()
        if READINESS.exists() or STATE.exists():
            raise RuntimeError("Continuation preparation already exists; refusing overwrite")
        driver.prepare()
        add_provenance()
        return
    if sys.argv[1:] == ["--restore"]:
        load_driver().restore()
        return
    raise SystemExit("Usage: r1-window-readiness-continuation.py [--prepare|--restore]")


if __name__ == "__main__":
    main()
