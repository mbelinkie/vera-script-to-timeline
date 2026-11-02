# Synthetic workflow run policy

Implement solve(payload) in target.ts. The public task is only this file; do
not change the visible check or wrapper. Run it with Node 26, which strips this
file's erasable TypeScript types directly. No external imports are needed. All
types, key names, and reason codes are defined in target.ts.

The payload must have exactly expected, actual, and now. expected must have
exactly repository, workflow_head, and not_before. actual must have exactly
repository, workflow_head, started_at, run_id, url, and conclusion.

Repositories use owner/name with two non-empty ASCII components containing
letters, digits, period, underscore, or hyphen; a component cannot be . or ...
Workflow heads are exactly 40 lowercase hexadecimal characters. Timestamps
use the exact UTC form YYYY-MM-DDTHH:MM:SSZ and must be real calendar times.
run_id is a positive safe integer; a boolean is not an integer. The conclusion
is a string.

Return exactly {ok: true, reason: "ok"} only if all checks pass; otherwise
return {ok: false, reason: CODE}. Use this validation order:

1. Wrong payload keys or non-object payload: invalid_payload.
2. Wrong expected keys, types, or formats: invalid_expected.
3. Wrong actual keys, types, or formats: invalid_actual.
4. Invalid now timestamp: invalid_now.
5. conclusion other than success: run_not_successful.
6. Repository mismatch: repository_mismatch.
7. Workflow-head mismatch: workflow_head_mismatch.
8. URL mismatch: invalid_run_url. The URL must exactly equal
   https://github.com/REPOSITORY/actions/runs/RUN_ID.
9. started_at before expected.not_before: started_before_window.
10. started_at after now: started_in_future.

The function is a deterministic policy check. It receives all required types,
keys, and reason definitions in the editable file; do not infer missing
interfaces, mutate the input, or use network access.
