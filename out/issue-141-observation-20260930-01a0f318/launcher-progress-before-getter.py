"""Operator-launched Workflow Integration, matching #110's injection boundary."""

import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PLUGIN_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)
CONFIG = PLUGIN_ROOT / "vera-issue-141-observation.json"
stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
progress = PLUGIN_ROOT / f"vera-issue-141-observation-progress-{stamp}.jsonl"


def record(phase, **details):
    with progress.open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps({"phase": phase, "at": datetime.now(UTC).isoformat(), **details})
            + "\n"
        )


record("started", resolveInjected=globals().get("resolve") is not None)

try:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    path = Path(config["probePath"])
    if not path.is_absolute():
        raise ValueError("probePath must name the absolute issue-owned source")
    with path.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != config["probeSha256"]:
            raise ValueError("Probe source differs from the staged hash; stop")
    spec = importlib.util.spec_from_file_location("vera_141_observation", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the stdlib-only observation probe")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    record("module-loaded", action=config["action"])
    # Disarm before invocation: an exception may follow a successful mutation.
    # The unchanged original config is still passed to the one staged action.
    if config["action"] != "observe":
        disarmed = {**config, "action": "observe", "stage": "baseline-repeat"}
        CONFIG.write_text(json.dumps(disarmed, indent=2) + "\n", encoding="utf-8")
    record("probe-request")
    result = module.run(globals().get("resolve"), config)
    record("probe-return", status=result.get("status"))

except Exception as error:
    record("probe-failure", error=f"{type(error).__name__}: {error}")
    result = {
        "status": "launcher-failed",
        "detail": f"{type(error).__name__}: {error}",
        "instruction": (
            "Retain evidence and stop. Do not rerun preparation "
            "or change scripting mode."
        ),
    }

result_path = PLUGIN_ROOT / f"vera-issue-141-observation-result-{stamp}.json"
with result_path.open("x", encoding="utf-8") as stream:
    json.dump(result, stream, indent=2, sort_keys=True)
    stream.write("\n")
record("result-written")
print(json.dumps(result, indent=2))
