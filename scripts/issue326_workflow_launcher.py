"""Issue-owned, one-operation launcher; leaves every existing plugin untouched."""

import hashlib
import json
import runpy
import traceback
from pathlib import Path

root = Path.home() / ".local/share/vera/issue-326-native"
request_bytes = (root / "request.json").read_bytes()
request_sha256 = hashlib.sha256(request_bytes).hexdigest()
request = json.loads(request_bytes)
operation = request["operationId"]
if not operation or any(
    c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in operation
):
    raise ValueError("invalid operation identifier")
started = root / (operation + ".started.json")
result_path = root / (operation + ".result.json")
with started.open("x") as stream:
    json.dump(request, stream, indent=2)
try:
    source = Path(request["script"])
    if hashlib.sha256(source.read_bytes()).hexdigest() != request["scriptSha256"]:
        raise ValueError("native probe source changed")
    native = globals().get("resolve")
    if native is None:
        raise ValueError("Resolve did not inject its native object")
    result = runpy.run_path(str(source))["run"](native, request)
except Exception as error:
    result = {"status": "failed", "traceback": traceback.format_exc()}
    mutations = getattr(error, "native_mutation_attempts", None)
    if mutations:
        result["nativeMutationAttempts"] = mutations
    partial_evidence = getattr(error, "partial_evidence", None)
    if type(partial_evidence) is dict:
        result["partialEvidence"] = partial_evidence
with result_path.open("x") as stream:
    json.dump(
        {"request": request, "requestSha256": request_sha256, "result": result},
        stream,
        indent=2,
    )
print(json.dumps(result, indent=2))
