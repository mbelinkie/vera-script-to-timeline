# Waiting for guarded Studio delivery

The normal `VERA Delivery v2.py` build can take longer than an agent tool's
60-second call window. Use the parent below instead of executing the whole
build inside that call. It runs the same guarded installed script in Resolve's
bundled Python, on the worker's main thread. Resolve must already be running
with External Scripting set to **Local**. The parent does not change preferences.
Open the Edit page with a current project; an empty project is sufficient.
No providers, network uploads or rendering are added.

First use the existing `workflow_v2_cli attest`, `release` and `request` flow
with a fresh attestation, fresh release directory and fresh evidence directory.
The request must occupy `vera-delivery-v2/request.json` in that release. A build
requires `--authorize-new-nonproduction --external-scripting-local`. This
explicitly records the external connection actually used by the child. The
existing injected Workflow Integration route still supports
`--external-scripting-none`; that request cannot be dispatched by this parent.
Check that no other operator, render or unresolved delivery owns Resolve before
starting. Preserve previous targets and evidence; a new attestation creates a
new disposable target, never permission to reuse a previous one.

With `REQUEST` set to that installed request, `REQUEST_SHA256` to its SHA256,
and `RESOLVE_PYTHON` to Resolve's bundled Python executable:

```sh
uv run --frozen python -m vera_timeline_agent.workflow_v2_parent start \
  --request "$REQUEST" --request-sha256 "$REQUEST_SHA256" \
  --python "$RESOLVE_PYTHON"

uv run --frozen python -m vera_timeline_agent.workflow_v2_parent resume \
  --request "$REQUEST" --request-sha256 "$REQUEST_SHA256" --wait-seconds 30
```

`status` returns immediately. `resume` waits up to 50 seconds per call and can
be repeated. Both only inspect the existing operation. A wait expiration never
kills, retries or replaces it. Repeating `start` also inspects the original
reservation; it does not create a second worker. The normal launcher reserves
its request digest before calling Resolve, protecting direct request replays.

| State | Meaning |
| --- | --- |
| `live` | The worker still holds its inherited operation lock. |
| `unknown` | Liveness or completion cannot be established. Inspect retained evidence; do not start another write. |
| `failed` | The worker exited but lacks valid final evidence, or failed itself. Resolve's partial outcome needs inspection; do not replay. |
| `terminal` | The worker exited and the normal result, start and hash records match this request. Read the result's status: terminal can include a failed build. |

Only `terminal` with `verified: true` means the normal saved/reopened build
passed. Polling does not promote partial results or a caller timeout to success.
Elapsed seconds run from the parent's durable reservation to the worker's exit;
while live they measure time since reservation. They exclude attestation/release
preparation. Keep these records private: the normal reports contain local paths
and target identities.

Retain `parent.json`, `parent-exit.json`, `parent-console.log`, `parent.lock` and
the normal `started-*`, `result-*`, `hashes-*` records together. The start and
final records must name this parent's invocation; a concurrent menu launch of
the same request cannot be credited as this worker's completion. Missing, corrupt
or mismatched records remain non-retriable under the same reservation. Legacy
start-only evidence has no liveness proof and is not resumable execution. This
parent resumes waiting, not partially executed Resolve mutations. It requires
macOS/Linux file locks; it does not alter Resolve's scripting preferences.
