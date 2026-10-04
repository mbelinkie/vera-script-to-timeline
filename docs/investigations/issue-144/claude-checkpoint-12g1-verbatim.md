# Claude checkpoint12g1 finished-code review

Read-only; 6 turns, 0 permission denials.

# Checkpoint composition review — `issue-144-composition.ts`

Read-only review complete. I traced the identity bridge, projection construction, and anchor-transfer logic directly against the already-reviewed `compiler-core.ts`/`issue-144-semantics.ts` behavior rather than trusting the new code's comments.

## Blockers

**None found.**

One thing I initially suspected as a bug and want to report honestly as resolved rather than silently drop: `visualInputs()`'s companion check (`issue-144-composition.ts:49-51`) compares `visual.id === item.eventId` — the *authored* `VisualEvent.id` against the *compiled* event's `id`. These look like two different namespaces, and I checked compiler-core.ts's visual-event construction specifically: it sets `id: authored.id` directly (not a derived UUID, unlike other event kinds), with `provenance.authoringId` set to that same value. So for visual events specifically, compiled `event.id` and authored `VisualEvent.id` are the same value by construction, and the already-proven `issue-144-semantics.ts` code (`visuals(document).find(event => event.id === authoringId)`, reviewed in checkpoint 6) already relies on exactly this equivalence. The new code's comparison is correct, not a bug — I verified this against the compiler's actual event-construction code rather than assuming it from the pattern alone.

## Confirmed sound by direct trace

- **Projection never leaves memory.** `visualInputs()` constructs the restored projection and passes it directly into `proposeVisuals(visual)` within the same function body; `inspectComposition` returns only `{visualReport, visualManifest}`, never `visual` itself. Both the TS test (`expect(Object.keys(inspected).sort()).toEqual(["visualManifest", "visualReport"])`) and the CLI test (`expect(receipt.result).not.toHaveProperty("projection")`) assert this directly at two different boundaries, not just at the function's own return type.
- **+25 move / -25 trim still come from actual compiler reproduction.** `inspectComposition` requires exactly two `proposeVisuals` rows, both `"supported"`, one `"move"` and one `"trim"` — and `proposeVisuals` itself is unchanged, with its hardcoded `+25`/`-25` detection and `candidates()`'s compiler-reproduction requirement untouched (checkpoint 6). The new code adds no parallel geometry logic; it only narrows which *shape* of already-validated report it will accept.
- **Surviving-anchor transfer order is correct.** `composeEdits` applies `applyAcceptedOmission` to the *original* document first, then transfers each accepted visual's already-validated `TextAnchorRange` onto the token IDs that survive in the *revised* document, re-checking `first !== undefined && last !== undefined` before accepting the transfer — meaning a move/trim target whose anchor endpoint happened to be removed by the omission is caught (`"composition visual endpoint removed"`), not silently mismapped.
- **Version/hash bookkeeping matches the established pattern.** One `anchorVersion`/`visual.version` bump per transferred proposal, one `liveHeadSequence`/narration-version increment via the unchanged omission transformer, `liveContentHash` recomputed excluding itself — all consistent with checkpoints 6 and 11's already-proven conventions, confirmed by the test's exact-value assertions (`anchorVersion: 2`, `row.version` delta of exactly 1), not just presence checks.
- **Runtime/CLI wiring is complete.** All four of `issue-144-composition.ts`'s own imports (`compiler-core.js`, `script-validator.js`, `issue-144-semantics.js`, `issue-144-text-revision.js`) have matching resolution-hook rules in the updated CLI; the one-input/two-input dispatch split matches exactly "inspect visual authority" vs. "prepare canonical revision," and the two Python source-hash inventories (`roundtrip_build.py` `CODE_PATHS`, `roundtrip_proof.py` `SEMANTIC_SOURCES`) both include the new file in their own existing conventions.

## Bounded, non-blocking notes

**Potential double version-bump if a move/trim anchor ever overlaps the omitted range — not exercised by the current fixture.** `composeEdits`'s transfer loop unconditionally does `visual.version += 1` for each accepted proposal, after `applyAcceptedOmission` has already run and may itself have bumped that same visual's version if its original anchor enclosed or was affected by the omitted tokens. The shipped fixture's ranges (move on tokens 4-5, trim on tokens 7-8, omission on token 3) never overlap, so this can't be observed today, but nothing in the code or a test establishes that the move/trim anchors must be disjoint from the omitted range as a precondition. Worth an explicit guard or test before this is generalized beyond the current fixture, not before this checkpoint.

**Minor, harmless duplication:** the safe-integer version-overflow check (`issue-144-composition.ts:127`) reimplements the same two-line check as `issue-144-text-revision.ts`'s private (unexported) `next()` helper rather than importing a shared one. Not worth exporting a previously-private helper just for this, but noting it as the one spot with repeated logic.

No projection leakage, no identity mismatch, no unreviewed reuse of `proposeVisuals`/`applyVisualDecisions`/`applyAcceptedOmission`/`compileTimeline`/`validateScriptDocument` — all five remain genuinely unchanged and are the actual authority for every claim this module makes. This is static review only; I did not execute anything.
