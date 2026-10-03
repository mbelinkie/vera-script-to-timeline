"""Operator-launched Workflow Integration, matching #110's injection boundary."""

import hashlib
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

PLUGIN_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)
CONFIG = PLUGIN_ROOT / "vera-issue-141-observation.json"
stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")

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
    spec.loader.exec_module(module)
    result = module.run(globals().get("resolve"), config)
    if config["action"] in {"prepare", "resume-preparation"} or (
        config["action"] in {"native-repeat", "native-duplicate", "native-context"}
        and result["status"] == "equal-adjacent-reads"
    ):
        config["action"] = "observe"
        config["stage"] = "baseline-repeat"
        CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
except Exception as error:
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
print(json.dumps(result, indent=2))
