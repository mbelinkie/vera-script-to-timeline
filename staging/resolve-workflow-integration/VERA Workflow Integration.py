"""Non-mutating, standard-library probe for Resolve's injected workflow API.

Resolve executes direct Workflow Integration scripts without ``__file__``.
It currently embeds Python 3.14, while this checkout's native VERA packages
are built for Python 3.12. Keep this probe dependency-free until the runtime
boundary has a compatible adapter design.
"""

import json
from pathlib import Path


PLUGIN_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)
STARTED_PATH = PLUGIN_ROOT / "vera-workflow-integration-started.txt"
RESULT_PATH = PLUGIN_ROOT / "vera-workflow-integration-result.json"


def main(injected_resolve: object) -> None:
    result = {
        "status": "injected_probe_passed",
        "productName": injected_resolve.GetProductName(),
        "version": injected_resolve.GetVersion(),
    }
    RESULT_PATH.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


STARTED_PATH.write_text("started\n", encoding="utf-8")
injected_resolve = globals().get("resolve")
try:
    if injected_resolve is None:
        raise RuntimeError("Resolve did not inject the 'resolve' workflow object")
    main(injected_resolve)
except Exception as error:
    failure = json.dumps(
        {"status": "workflow_launcher_failed", "detail": str(error)}, indent=2
    ) + "\n"
    RESULT_PATH.write_text(failure, encoding="utf-8")
    print(failure, end="")
