"""Manual staging wrapper for Resolve's Python Workflow Integration menu."""

import json
import sys
from pathlib import Path

# Resolve can hide script errors. Leave a local trace before loading VERA so
# this spike can distinguish a launcher failure from a dependency failure.
STARTED_PATH = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins/vera-workflow-integration-started.txt"
)
with STARTED_PATH.open("w") as stream:
    stream.write("started\n")

CONFIG_PATH = Path(__file__).with_name("vera-workflow-integration.json")
RESULT_PATH = Path(__file__).with_name("vera-workflow-integration-result.json")


def main(injected_resolve: object) -> None:
    """Load local staging configuration and use Resolve's injected API object."""
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    python_paths = config["pythonPaths"]
    package_dir = Path(config["packageDir"])
    project_name = config["projectName"]
    if not isinstance(python_paths, list) or not all(
        isinstance(value, str) and value for value in python_paths
    ):
        raise RuntimeError("pythonPaths must be a nonempty list of absolute paths")
    if not isinstance(project_name, str) or not project_name:
        raise RuntimeError("projectName must be a nonempty unique name")
    for value in reversed(python_paths):
        sys.path.insert(0, value)
    from vera_timeline_agent.workflow_integration import run_workflow_integration

    result = run_workflow_integration(
        injected_resolve,
        package_dir,
        project_name=project_name,
    )
    RESULT_PATH.write_text(result.to_json(), encoding="utf-8")
    print(result.to_json(), end="")


injected_resolve = globals().get("resolve")
if injected_resolve is None:
    raise RuntimeError("Resolve did not inject the required resolve object")
try:
    main(injected_resolve)
except Exception as error:
    failure = json.dumps(
        {"status": "workflow_launcher_failed", "detail": str(error)},
        indent=2,
        sort_keys=True,
    ) + "\n"
    RESULT_PATH.write_text(failure, encoding="utf-8")
    print(failure, end="")
    raise
