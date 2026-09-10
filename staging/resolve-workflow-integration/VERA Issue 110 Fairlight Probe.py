"""Python 3.14-safe launcher for the issue 110 Fairlight probe."""

import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)
STARTED_PATH = PLUGIN_ROOT / "vera-issue-110-fairlight-probe-started.txt"
CONFIG_PATH = PLUGIN_ROOT / "vera-issue-110-fairlight-probe.json"
RESULT_PATH = PLUGIN_ROOT / "vera-issue-110-fairlight-probe-result.json"


def main(injected_resolve: object) -> None:
    raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    python_path = raw_config.get("pythonPath")
    if not isinstance(python_path, str) or not Path(python_path).is_absolute():
        raise RuntimeError("pythonPath must be an absolute repository python path")
    sys.path.insert(0, python_path)
    from vera_timeline_agent.fairlight_capability import (
        load_probe_config,
        run_fairlight_capability_probe,
        write_operator_handoff,
    )

    config = load_probe_config(CONFIG_PATH)
    report = run_fairlight_capability_probe(injected_resolve, config)
    report_path = config.output_dir / "capability-report.json"
    handoff_path = config.output_dir / "operator-handoff.md"
    report_path.write_text(report.to_json(), encoding="utf-8")
    write_operator_handoff(report, handoff_path)
    RESULT_PATH.write_text(report.to_json(), encoding="utf-8")
    print(report.to_json(), end="")


STARTED_PATH.write_text("started\n", encoding="utf-8")
injected_resolve = globals().get("resolve")
try:
    if injected_resolve is None:
        raise RuntimeError("Resolve did not inject the 'resolve' workflow object")
    main(injected_resolve)
except Exception as error:
    failure = (
        json.dumps(
            {"status": "fairlight_probe_launcher_failed", "detail": str(error)},
            indent=2,
        )
        + "\n"
    )
    RESULT_PATH.write_text(failure, encoding="utf-8")
    print(failure, end="")
