# Checkpoint 12a finished-code review — primary narration source binding extension

Read-only review complete, bounded to `roundtrip_audio.py`'s current state (diffed against my memory of the pre-extension version from the checkpoint-12 plan review) and the new same-row/wrong-primary tests.

## The extension matches the two-part fix precisely, traced line by line

In my checkpoint-12 plan review I identified that implementing this correctly required exactly two coordinated changes to the old code. I verified both are present:

1. **The old `row in rows` uniqueness check is gone.** The `rows: set[str]` variable no longer exists in the source-loading loop; only `identity in sources` (duplicate ID) and `source["sha256"] in hashes` (duplicate bytes) remain as uniqueness guards (lines 519-522) — correctly keeping the alias/duplicate-content protections global while removing only the per-row restriction.
2. **Selection is now by caller-supplied ID, not by row:** `selected = sources.get(primary_source_id)` (line 535), followed by an explicit, separate check `selected["rowId"] != row_id` (line 538). This is exactly "select first by trusted identity, then verify the row" rather than "select by row and hope it's unique" — the design property that actually makes "operator profile cannot pick a different primary" true, since `profile.json` never supplies the value used for selection.

`primary_source_id` is validated as a well-formed ID (`_id(primary_source_id, "primary source")`, line 480) before any file is read, consistent with how `row_id`/`baseline_hash`/`target` are already treated as caller-trusted, not operator-derived.

## Report binding — confirmed correct

`report["primarySourceId"] = primary_source_id` is set at report construction (line 465), before any validation runs — so even a refused report truthfully records what the caller requested, not just what was eventually verified. The separate `sourceId` field set later on success (line 642) is redundant with `primarySourceId` by construction at that point (since `selected["id"] == primary_source_id` is already guaranteed), which is intentional clarity, not a bug.

## New tests — traced, not just read as a checklist

`test_same_row_auxiliary_supports_do_not_choose_primary` gives source-1 the *same* `rowId` as source-0 and a plausible-looking, non-empty `supports` list (aliased token IDs derived from source-0's own words) — a genuine attempt to construct a same-row auxiliary that could pass a naive heuristic — and confirms the explicit `primary_source_id="source-0"` still correctly produces the real omission result.

`test_trusted_primary_and_row_binding_refuse`'s three cases are well-chosen, and I hand-traced the third one specifically since it's the subtle one: `primary_source_id="source-1"` (the unedited auxiliary) with `row_id="row-0"` (which now matches, since the fixture gave source-1 the same row). This passes the shallow existence/row checks — but since source-0 is the route that was *actually* edited in the test fixture, and the verifier now treats source-0 as "not selected" (because source-1 was chosen as primary), the existing `source["id"] != selected["id"] and old != new` check correctly catches that the real edit landed on a route the caller didn't designate as primary, refusing with "untouched route changed." This is a materially harder case than "unknown ID" or "wrong row" — it tests that a *plausible but wrong* primary selection is still caught by the downstream geometry check, not just the upfront binding check. Good test design, not just coverage padding.

## No regressions found in ancestry/alias discipline

The global `identity in sources` and `sha256 in hashes` checks are untouched in placement and behavior; the per-route `old != new` untouched-route requirement still applies uniformly regardless of row-sharing, so an auxiliary source — same row or not — still cannot change without being refused unless it's the caller-designated primary. I traced this through the full decomposition loop and found no path where multiple sources sharing a row weakens any existing excision/neighbor-preservation check; it only removes the single restriction that made auxiliary sources impossible to express at all.

## No blockers found

One trivial, non-functional note not worth a code change on its own: the error message `"ambiguous row/source binding or alias"` (line 522) is now only reachable via the sha256-alias path (the row-binding half of that condition was removed), so the wording is slightly stale relative to what it actually checks — cosmetic only.

Could not independently verify the exact "48 audio checks" count or that all pass — that's test execution, which I didn't run. Everything above was confirmed by direct code trace, not by trusting the summary.
