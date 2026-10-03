"""Forward one bounded invocation; retain its complete result locally."""
import importlib.util
import json
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("native", here / "independent-native-call.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
request = json.loads(sys.argv[1])
result = native.invoke(**request)
(here / "independent-last-result.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({key: result[key] for key in result if key in {
    "status", "case", "stage", "label", "failure", "postflightFailure",
    "directory", "preparedPair", "restoredPair", "afterPair", "secondPositionPair",
    "target", "originalLocks", "originalPlayhead", "playheadAfter", "pair",
    "selectionShapes", "_nativeResultPath", "_auditDirectory", "auditDirectory",
    "menu", "dispatched", "selectedUids", "intervalUids", "deleteReturn",
}}, indent=2))
