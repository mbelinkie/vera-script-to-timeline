# Checkpoint 7 follow-up — row boxes and preservation boundary

Read-only review complete (updated `producer-row-audio-policy.md`, current plan, and `compiler-core.ts`'s block-sequencing logic). Findings below use concrete code/line evidence where I could get it, not just the documents' own claims about themselves.

## 1. Compatibility with the compiler's block-local timing and sequential assembly

**Confirmed compatible — and the Producer's "box" framing isn't new behavior to build, it's a description of code that already exists.** I traced the actual compile loop, not just the schema: `compiler-core.ts:376-397` maintains `let cursor = dependencies.build.timeline.startFrame`, and for each narration block in document order sets `startFrame: cursor`, computes `endFrame = cursor + durationFrames`, then `cursor = endFrame` before moving to the next block. Word-timing marks inside a block are local milliseconds from zero (`timeMs`), converted to frames and added to that block's own `blockStart` (`frameRange`, lines 559-576). That is exactly "validate each row individually, then string them together in order" — not an approximation of it.

**One genuine gap, correctly excluded rather than hidden:** I grepped `compiler-core.ts` for any concept of a cross-block audio occurrence (`music`, `bed`, `backgroundAudio`) and found nothing — the compiler has no entity today that spans multiple narration blocks independently of block boundaries. The plan's own text already treats this correctly as an *exclusion*, not an implicit claim: "Music can span rows and requires a separate assembly-level check. No other cross-row operation is qualified by this bounded proof" (`issue-144-roundtrip-harness.md:16-18`). I'd just make sure nobody reads that sentence as "and #144 validates it" — it doesn't, and there's no compiler feature to validate it against yet.

## 2. Fresh-timeline limitation — is it clearly surfaced, and what's the minimal test?

**Partially surfaced — in the wrong document.** The disclaimer exists, clearly, in `producer-row-audio-policy.md:59-63` ("Equal untouched-row content is not proof of reusing native timeline objects or retaining all human refinements in the new target... production #104 scope"). But I grepped the *plan itself* (`issue-144-roundtrip-harness.md`) for `#104`, `native object`, `human refinement`, `selective regeneration`, and `fresh timeline` — **zero matches.** The plan is the document that's supposed to be the "corrected executable plan"; right now this limitation lives only in a side memo. Concrete fix: add one sentence near the "Row-box framing" banner or the "Fresh rebuild" table row stating plainly that every #144 rebuild target is a newly created Studio project/timeline (never an edit of an existing one), and that content-equality for untouched rows proves nothing about native-object reuse.

That "fresh timeline" claim is itself independently verifiable in code, which is worth citing: `check_project_name_available` (`studio_spike.py:540-544`) explicitly refuses if a project with the target name already exists ("refusing to overwrite or reuse it") — there is no code path anywhere in `studio_assembly.py`/`roundtrip_native.py` that edits an existing target. So "fresh timeline only" isn't an assumption, it's an enforced fact.

**Minimal test that establishes content preservation honestly:** don't test native-object identity (impossible to test, since nothing is reused) — test *compiled logical content* equality instead. Build once; accept an edit that changes one row's duration; recompile; then assert, for every *other* row: (a) its narration dependency's `audioHash`/text/revision are byte-identical to before (already verifiable via the existing hash-binding in `PreparedBuild._verify_speech`), and (b) its compiled events have identical `sourceId`/content and identical *block-local* token-to-frame mapping, with only the *absolute* `recordRange.startFrame` shifted by exactly the preceding row's duration delta. This is the same style of check already proven for the visual-only case (`applyVisualDecisions`'s accepted-geometry re-verification, checkpoint 6) — same pattern, no new claim about Resolve internals, no native action required.

## 3. Post-prompter override with locked recordings — confirmed, my prior caution was overcautious

I accept the correction and can show why it resolves cleanly rather than just taking it on faith. My checkpoint-7 recommendation assumed "regenerate row temp VO" meant mutating the *same* audio asset a locked recording occupies, which would conflict with §8.3's Locked Audio rule. But #144's own revision model never does that: a new revision gets fresh build/manifest/report IDs (the UUIDv5 `revisionId` scheme reviewed in checkpoint 6) and the plan already requires "Retain old files and targets" (`issue-144-roundtrip-harness.md:85`) and "Preserve old bytes only as historical build evidence" (line 227). So "an explicit override regenerates the row's temp VO" means: bind a *new* temporary audio asset to the *new, now-stale* revision, while the *old* revision — including whatever locked/approved recording it pointed to — remains fully intact and untouched under its own prior build pointer. "An ordinary rebuild does not unlock it" is already true structurally today: `PreparedBuild._verify_speech` only ever *verifies* existing audio against its declared hash — there is no generation code path in `roundtrip_build.py` at all, so an ordinary rebuild of an unchanged, locked row can only re-confirm it, never regenerate it. No contradiction with §8.3 remains once "regenerate" is understood as "bind a new asset to a new revision" rather than "overwrite in place."

**Confirmed, no remaining discrepancy.**

## 4. Keep lock/export UI details in #153

The plan and policy memo currently have zero references to `#153` or "Inbox" (grepped both). The deferral itself is already correctly worded ("The warning/lock UI, reshoot state and changed-row prompter export are future authoring/recorded-workflow work, not frontend implementation inside #144," plan banner lines 13-18 region / policy doc line 66-67) — it just isn't yet *linked* to the tracking issue the Producer named. Smallest fix: add "(tracked in #153)" to that existing sentence in both documents so the deferral points somewhere concrete instead of floating.

## Concise confirmations (no discrepancy)

- Row = narration block, boxes strung together: matches the compiler's actual sequential-cursor assembly, verified in code, not just plausible.
- "Rearranged" rows (moved, content unchanged) get the same free benefit as duration-shifted rows: since blocks compile in document order, reordering a block in the document naturally repositions it via the same cursor mechanism, with its own internal block-local mapping untouched. No new logic needed for this to already be true.
- Historical locked recordings vs. a currently-stale edited row with fresh temp VO: consistent with §8.3 and #144's existing revision/asset-binding model.

## Unresolved product decisions remaining (none the Producer hasn't already settled for #144's purposes)

I don't have a new open product question to raise — everything in this follow-up was either a confirmation or a documentation-location fix. The only non-product items are the two concrete, bounded corrections above (surface the #104 fresh-timeline disclaimer in the plan itself; link the lock/export deferral to #153 by name).

Advisory only — does not change Producer policy or constitute acceptance.
