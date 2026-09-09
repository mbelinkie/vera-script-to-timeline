"""Python 3.14-safe launcher for Resolve's injected workflow API object."""

import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)
STARTED_PATH = PLUGIN_ROOT / "vera-workflow-integration-started.txt"
CONFIG_PATH = PLUGIN_ROOT / "vera-workflow-integration.json"
RESULT_PATH = PLUGIN_ROOT / "vera-workflow-integration-result.json"


def main(injected_resolve: object) -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    python_path = config.get("pythonPath")
    attestation_path = config.get("attestationPath")
    if not isinstance(python_path, str) or not Path(python_path).is_absolute():
        raise RuntimeError("pythonPath must be an absolute repository python path")
    if (
        not isinstance(attestation_path, str)
        or not Path(attestation_path).is_absolute()
    ):
        raise RuntimeError("attestationPath must be an absolute path")
    sys.path.insert(0, python_path)
    from vera_timeline_agent.workflow_integration import run_workflow_integration

    result = run_workflow_integration(
        injected_resolve,
        Path(attestation_path),
    )
    RESULT_PATH.write_text(result.to_json(), encoding="utf-8")
    print(result.to_json(), end="")


STARTED_PATH.write_text("started\n", encoding="utf-8")
injected_resolve = globals().get("resolve")
try:
    if injected_resolve is None:
        raise RuntimeError("Resolve did not inject the 'resolve' workflow object")
    main(injected_resolve)
except Exception as error:
    failure = (
        json.dumps(
            {"status": "workflow_launcher_failed", "detail": str(error)}, indent=2
        )
        + "\n"
    )
    RESULT_PATH.write_text(failure, encoding="utf-8")
    print(failure, end="")
