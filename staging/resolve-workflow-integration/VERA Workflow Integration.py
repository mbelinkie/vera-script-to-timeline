"""Manual staging wrapper for Resolve's Python Workflow Integration menu."""

from __future__ import annotations

import json
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("vera-workflow-integration.json")


def main(injected_resolve: object) -> None:
    """Load local staging configuration and use Resolve's injected API object."""
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    repository_python = Path(config["repositoryPythonPath"])
    package_dir = Path(config["packageDir"])
    project_name = config["projectName"]
    if not isinstance(project_name, str) or not project_name:
        raise RuntimeError("projectName must be a nonempty unique name")
    sys.path.insert(0, str(repository_python))
    from vera_timeline_agent.workflow_integration import run_workflow_integration

    result = run_workflow_integration(
        injected_resolve,
        package_dir,
        project_name=project_name,
    )
    print(result.to_json(), end="")


injected_resolve = globals().get("resolve")
if injected_resolve is None:
    raise RuntimeError("Resolve did not inject the required resolve object")
main(injected_resolve)
