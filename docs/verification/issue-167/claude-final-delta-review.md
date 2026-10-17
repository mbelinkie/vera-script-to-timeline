# GO: delta review of #167 at `824923d`

R1, R2 and R3 are all fixed. I found no related regression that blocks the design. The rules below are deterministic and fail closed. The non-blocking notes after them are wording clarifications and do not need to be fixed before design acceptance.

## R1. Nullable evidence fields: fixed

- **Non-null fields:** For every basis, `blockId`, `blockRevision`, `timingHash`, `audioHash`, `textHash` and `timingInputHash` are now non-null. They are copied from one owning frozen input.
- **Refusals:** The input must have `status:"ready"`. Missing, failed or ambiguous dependencies refuse with `GRAPHIC_CUE_TIMING_UNQUALIFIED`. "Ambiguous" covers duplicate `NarrationDependency` entries for the same block.
- **What may be null:** Only `tokenId` and the listed causal fields. Nothing is left to choice between null and filled, so the duration-derived counterexample from the previous review is closed.
- **Locator omission:** The `timingInputHash` rule now names one deletion, `audio.locator`. It keeps `{durationSamples,sampleRate,channels}`, `assetId`, `status`, `timing` and all other fields, and forbids any other normalization. Two implementations therefore produce the same bytes.
- **Accepted #7 schema fit:**
  - `status:"ready"` excludes `failureReason` through the accepted `if/else`, so a ready record has no optional-field ambiguity.
  - `NarrationAudio` requires all four fields, so removing the locator leaves a fixed three-field object.
- **Trust limit:** Relinking the audio no longer changes the cue hash. Integrity is still enforced: the package keeps the exact audio bytes, verifies `audioHash`, and keeps the original locator-bearing dependency for audit.
- **`schemaVersion`:** Added to the `occurrenceBoundaryHash` record.
- **Inherited hash material:** Semantic, provenance and build hash material is unchanged by this delta.

## R2. v1 `tokenId` to `TimingMark` resolution: fixed

- **Token source exists:** Accepted #7 `NarrationBlock.tokens` is required with at least one item. Each `NarrationToken` has a UUID `id`, a nonempty `value`, and `startOffset`/`endOffset`. The anchor therefore has a real v1 target.
- **Resolution chain:** The rule resolves the token by `id`, requires `token.value === quotedWord`, then requires exactly one `kind:"word"` mark with equal start, end and value.
- **Repeated words:** Offsets differ for every token position, so identical words cannot match each other. Duplicate token IDs, zero matches and multiple matches all refuse.
- **`exactTime`:** Reduced `timeMs/1000` is exact. `timeMs` is a nonnegative integer, so the numerator and denominator are safe integers.
- **Consistency:** The design §4.2 and the CN state the same rule.

## R3. Report hash nullness by outcome: fixed

- **Golden bytes:** The new table fixes both hashes for every outcome reachable at the compiler and adapter stages, so the report goldens are byte-determinable.
- **Compiler vs adapter results:** They stay distinguishable even within the three-field `graphicCueResult`:
  - An adapter `unqualified` or `blocked` result keeps a non-null `executionPlanHash`.
  - The compiler forms of those outcomes have a null plan, or both hashes null for `blocked`.
- **Refusal containment:** Adapters can only replace a `planned_supported` result. The package verifier independently re-derives the plan and refuses a mismatch. A compiler refusal therefore cannot become a verified delivery.
- **Earlier cleanups:** The cleanups from the previous review are resolved: v1-only regeneration wording, the v1 union branches, omitting the empty array, and the locator decision.

## Non-blocking notes

These need at most one clause each.

1. **Offset units.** `NarrationToken` offsets are described only as "offsets into `NarrationBlock.text`", while `TimingMark` uses `startUtf16`/`endUtf16`. If they are counted in different units, text with non-BMP characters could, in rare cases, match the wrong same-valued mark.
   - Fix: add "token offsets are the accepted #7 UTF-16 code-unit offsets".
   - The synthetic ASCII Table probe is unaffected.
2. **Timing artifact verification.** The removed sentence said "declared content hash without verified bytes is insufficient". Its replacement says the package retains "the frozen timing record and exact narration audio bytes" and "verifies declared timing artifact hash". That is satisfiable only if accepted #7's `timing.contentHash` covers bytes the package actually keeps.
   - Fix: add "retain exactly the bytes over which accepted #7 `timing.contentHash` is defined".
   - This fails closed either way.
3. **Stale-anchor diagnostic code.** The CN maps stale anchor, version or text to `GRAPHIC_CUE_TIMING_UNQUALIFIED`. If design §6 defines a separate stale-anchor or anchor-mismatch code, say which one takes precedence so diagnostic goldens agree. I could not check this, because §6 was not provided.
4. **Version equality.** Say explicitly that the dependency's `blockRevision` must equal the frozen block version, or refuse. This is currently implied by "copied from" together with "frozen owner version".
5. **Editorial.**
   - In the design, the inserted text leaves "the name does not qualify its derived ends…" starting lowercase and separated from the `word_start_with_derived_end` name it refers to.
   - In the R3 table, "derives the exact package-owned plan algorithm" should read "applies the exact package-owned plan algorithm".
   - "Compiler `blocked` (any cause)" would read more clearly than "from semantic/integration refusal".

## Scope

- **Not reopened:** B1, the timing, profile and aggregation items, and v2 deferral were not reopened. No runtime or full-suite evidence was assumed.
- **Separate decisions:** Producer approval of CN-167-P1 is still a separate decision. The v2 wire scope stays deferred, unowned and outside this approval.
