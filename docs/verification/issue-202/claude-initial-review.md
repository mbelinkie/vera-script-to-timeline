# Independent initial review

Actual reviewer: `claude-opus-5-5`; Claude CLI 2.1.296, high effort, tools disabled. Session `08c7b17a-b822-44bb-88d4-ea9105263ab3`. Reviewed `77b82b3ea83bac5f9125571b352cfc0acfc3041b`; completed exit 0, `is_error: false`, source current. Raw response SHA256 `aa12d1e717f4d2340bfebb738f3bf717cb8193cd8bbe536fa7ba528d1a70aebb`. Exact prompt/response/command receipts retained in ignored `out/issue-202/`.

# Adversarial review: #202 pure v2 revision core @ `77b82b3`

**Verdict: GO for review. I found no blocking findings in the supplied source.** Full acceptance is still pending: there is no complete `VITEST_MAX_WORKERS=1 npm run validate`, and no qualifying #196 cloud run. Because that run hasn't happened yet, this is the cheapest time to add the recommended tests. Adding them later would invalidate a completed full run.

Line numbers below are approximate. I counted them from the pasted text, not from the repository.

## The timeline-freeze fix (`issue-192-v2-revision-core.ts:~190–199`)

The fix is correct and sufficient for the #177 invariant you reported.

- **Freezing once is enough.** `compileTimelineV2` sets `manifest.timeline = { ...dependencies.timeline, durationFrames: resolved.durationFrames }`. It reads only `timeline.frameRate` from the input timeline, never the input `durationFrames`. The report copies `manifest.timeline`. So assigning `dependencies.timeline` from the preview compile and recompiling gives manifest == report == dependencies.
- **The #191 binding is preserved.** The freeze happens after `finalizeReplacementV2` checks `handoff.priorDependenciesHash` against the un-frozen `stage.dependencies`. Neither `stage.regeneration` nor `priorDependenciesHash` changes.
- **The hash closure is ordered correctly.** `report.dependenciesHash === sha256(dependencies)` is checked after the freeze and before `proposalHash`. Build IDs are seeded before the freeze, which is harmless because `proposalHash` binds the full frozen dependencies.
- **Coverage is adequate.** The runtime `fact` at ~195 guards every proposal, including the A-only and B-only ones, which run without asserting. The combined A/B test and the C tests at D1 = 187, 200 and 213 assert it directly. I can't check any other #177 cross-file equalities from the guard fragment you pasted. Tracks, roles, document, compiler and preparation bindings are equal by construction, since the manifest copies them from `dependencies`.

## Seams inspected with no defect found

- **Hash identity, history and duplicates.**
  - `decideRevisionV2` checks the decision's closed keys, the history format, uniqueness and `historyHash`, the "already decided" condition, and the baseline document, dependencies and live head.
  - It then rebuilds the full proposal and compares the whole canonical object, including `comparisonText` and `proposalHash`. Tampering with any field is refused.
  - Reject returns the input objects themselves (same identity) and records the hash, which blocks a later accept.
- **Refusal without mutation.**
  - All edits work on `structuredClone`s or on the edit module's own working copy.
  - Commands, the trim range, the request, the decision and the handoff are closed records.
  - Version fields are checked for exact equality or as safe integers.
- **A (boundary move).**
  - The legal interval for owner 23 is (0, 34.5), so token 34 "before" is accepted.
  - Expected ranges: slot 23 at 311 + 258 = 569, slot 24 at 592, total 1107.
  - The anchor is token-addressed. It goes through the accepted `moveBoundary`, which bumps the anchor and sequence versions.
- **B (end trim 92 → 67).**
  - Requires a linked Full/Quiet clip with no duration override, an exact version, an exact range and a unique owned descriptor.
  - The descriptor's selected range and the block range change together. `occurrenceSourceInFrame` stays put, so `authoredSelectionMismatch` stays false.
  - A stale binding is refused by the compiler's `requestedRange` equality. Downstream shifts by −25.
- **C (omission and regeneration).**
  - Token 11 alone is removed and 10/12 are kept. The omission binds to the A/B-stamped document hash.
  - D1 comes from fresh `durationSamples` (D1·2002 samples at 48 kHz = D1 frames), not a 6-frame subtraction.
  - Downstream offsets are `+delta` for all three D1 values. Parked note 70 and row 20's evidence are preserved.
- **Unrelated preparation state.** Only requirement keys owned by affected rows can be replaced. Identity, profile, rate, authorization and mode must match. A key shared with an unaffected occurrence would fail the compiler's range check rather than change silently.

## Non-blocking recommendations

### 1. Coverage gaps (add before the full run)

The most valuable missing test covers the guard that protects unrelated state.

- **Unrelated-key replacement (`:~125`) is untested.** Only the duplicate key is covered. An exact clone of an unaffected binding is the case that would otherwise pass the compiler:
  ```ts
  (r) => { r.preparedMedia.push(structuredClone(input.dependencies.preparedMedia.find((b) => b.requirementKey === "prep:41")!)); },
  ```
- **Changed authorization or profile (`:~129`):** for example, `r.preparedMedia[0]!.authorizationReference = "other"`.
- **Picture-only trim refusal (`:~90`).** The existing `pictureOnly` case only exercises `keys()`. Set block 50's `audioPolicy` to `"mute"` in a clone; the baseline still compiles, and the trim should be refused with "linked standalone AV clip required".
- **Unexpected handoff (`:~187`):** an A/B request carrying `cCase(200).handoff`.
- **Malformed decisions:** an extra key, `outcome: "maybe"`, a non-hash history entry, and duplicate history entries.
- **Source-audio impact for B.** The test asserts the source-audio `recordRange`, which comes from the same `range` as the picture. It doesn't show the audio was trimmed. Because both endpoints use ceil and 67·2002 is an integer, the span is exact:
  ```ts
  const a = events.find((e) => e.provenance.blockId === id(50) && e.kind === "source_audio")!.audio!;
  expect(a.sampleRange.endFrame - a.sampleRange.startFrame).toBe(67 * 2002);
  ```
- **Pin refusal messages.** Bare `.toThrow()` in the "refuses stale/malformed" loop and decision checks can pass for the wrong reason. Use regexes such as `/stale selected/`, `/unrelated\/duplicate/` and `/identity changed/`.

### 2. Readability of `comparisonText` (`:~157–177`)

- **Source dump:** any B or C proposal changes `sources`, through the new `deliveredSourceId` or narration asset. The table then gets one cell containing the full canonical JSON of every source, including frame maps.
- **Labels:** event rows are labelled by UUID, and `readable()` drops `blockId` and `slotId`, which `eventImpact` already holds.
- **Invisible changes:** changes only to the track, picture treatment, time mapping or binding hash render as identical Before/After cells.
- Suggestion: label rows by block and slot, and summarise sources as added, removed or changed by ID.
- **Minor:**
  - `rows.unshift` lists narration rows in reverse document order.
  - Backslashes aren't escaped before `\|`.

### 3. Eager serialization in `ready()` (`:~57`)

The template literal serializes the entire compile result, including both JSON strings, on every call, even when the compile succeeds. That happens about 5–7 times per proposal, doubled during a decision.

On failure, the `Error.message` carries the whole manifest and report, including locators. This mirrors the accepted #191 pattern, but limiting it to diagnostic codes and IDs, built lazily, is cheaper and keeps logs narrower.

### 4. Live head advances by 2 for A/B + C

`stamp` runs, and then the #191 omission increments the head again. This is consistent with binding C to the staged A/B document, as the plan describes. One sentence in the plan would stop a host from assuming +1.

### 5. Clarify `priorDependenciesHash` ordering in the doc comment (`:~61`)

The hash must be computed after media for the actual fresh D1 is prepared. A clip slot in the regenerated row needs a D1-sized binding inside `stage.dependencies`. The test sidesteps this by knowing D1 in advance.

## Evidence limitations

- **No tool access.** I made no edits and ran nothing. Every claim above comes from reading the supplied source.
- **Unconfirmed claims:**
  - I couldn't check that existing frozen modules, contracts, fixtures, goldens and accepted tests are unchanged.
  - I couldn't check that the fast receipt's tree matches `77b82b3`.
  - I couldn't check the earlier red reproduction on `e66b744`.
- **Unseen code:** I only saw a fragment of the #177 Python guard. The fixture `compiler-dependencies-v2.json` and the `canonicalJson` implementation were not supplied.
- **Process:** test additions need a fast rerun and delta review, followed by a complete, qualifying full run. Native, provider and authentication gates remain with #192/#190.
