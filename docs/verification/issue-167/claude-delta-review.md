# Delta review of #167 at `f326fac`: NO-GO (3 residual blockers)

All three fixes are small text edits, two in CN-167-P1 and one in either the CN or the design. The original blockers are mostly resolved. B1 is fully fixed. B2 and B3 are each fixed except for one rule that is still missing and affects determinism. One optional-field gap, R3, has the same determinism weakness that made B2 a blocker. I found no other related regressions.

## Original blockers

**B1 (adapter outcome permissions): fixed.** The CN v1 report row now lets the adapter replace a `planned_supported` result with `verified`, `failed`, `blocked` or `unqualified`. Only the compiler may choose `manual_required`. This matches each runtime row in design §6:
- `PROFILE_UNQUALIFIED` maps to `unqualified`.
- `NATIVE_BINDING_MISMATCH` maps to `blocked` with zero writes.
- `NATIVE_VERIFICATION_FAILED` maps to `failed`.

Free is detected from `graphicDeliveryTarget`, which the compiler can see, so reserving `manual_required` for the compiler is sound. The deferred v2 row inherits the same permissions.

**B2 (endpoint evidence shape): partially fixed.** The closed record, hash, inventory entry and verifier recomputation are all defined now. The cause chain also terminates:
- `next_cue_start` points only to a strictly later start.
- `duration_derived` points only to an opposite endpoint that is a word endpoint.
- When all three timed values exist, both endpoints stay word-based.

One gap remains, listed as R1 below.

**B3 (v1 anchor type): partially fixed.** The named v1 `GraphicCuePointAnchor` is defined, and the CN's generated-type list now includes the new anchor and timing definitions. Single-block ownership refuses cross-block cues. Audible-end anchors are refused explicitly for the `word_start_with_derived_end` format, with no fallback to the next word. This is consistent across design §3, design §4.2, the last row of §5, the CN, and the accepted `NarrationTiming` enum. The anchor-to-mark resolution rule is still missing, listed as R2 below.

## Remaining blockers and smallest fixes

### R1. Unspecified nullable evidence fields (residual of B2)

**Where:** CN, `GraphicCueEndpointEvidence`.

**Problem:**
- The CN gives nullness rules for `tokenId` and for the five causal fields on each basis.
- It never says whether `blockId`, `blockRevision`, `timingHash`, `audioHash`, `textHash` and `timingInputHash` are filled in or null on the derived bases: `duration_derived`, `next_cue_start` and `graphic_end`.
- The `graphic_end` boundary record uses `timingInputHash`, which suggests the fields are filled in, but nothing requires it.

**Counterexample:** Two conforming implementations build the record for a duration-derived end. One fills the fields from the owning block. The other sets them to null. Their `evidenceHash` values differ, so their `cueScheduleHash` values differ.

**Fix:** Add one sentence:

> For every basis, `blockId`, `blockRevision`, `timingHash`, `audioHash`, `textHash` and `timingInputHash` are non-null. They are copied from the owning block's single frozen `NarrationDependency` with `status:"ready"`. A `failed` or missing dependency refuses with `GRAPHIC_CUE_TIMING_UNQUALIFIED`.

Optionally, also add `schemaVersion` to the `occurrenceBoundaryHash` record, matching the other addressed records.

### R2. v1 `tokenId` to `TimingMark` resolution is undefined (residual of B3)

**Where:** CN anchor paragraph ("existing exact text/offset/audio checks") and design §4.2.

**Problem:**
- Accepted v1 `TimingMark` entries are keyed by `{kind,timeMs,startUtf16,endUtf16,value}`. They have no `tokenId`.
- The supplied inputs don't show any accepted v1 rule that maps an anchor `tokenId` to a mark, or define how the block-local `exactTime` is derived.
- Repeated words in a block make "match by text" ambiguous.

I could not verify from the inputs that v1 `NarrationBlock` exposes UUID token IDs with UTF-16 offsets. If it doesn't, the copied anchor has nothing in v1 to point at.

**Fix:** Add one sentence:

> v1 resolves `tokenId` to the frozen block token's `[startUtf16,endUtf16)`. It requires exactly one `kind:"word"` mark with equal offsets and `value === quotedWord`. `exactTime` is `timeMs/1000`, reduced, block-local. Zero or multiple matches refuse with `GRAPHIC_CUE_TIMING_UNQUALIFIED`.

If v1 blocks have no token IDs, name the accepted v1 token source, or change the v1 anchor to an offset-based shape.

### R3. `graphicCueResult` hash nullness per outcome is ambiguous (optional-field gap)

**Where:** CN v1 BuildReport row ("hashes null when no valid schedule/plan exists") and the execution-plan paragraph ("package-owned").

**Problem:** The text doesn't settle three cases:
- Whether the compiler computes `executionPlanHash` for `planned_supported`, or whether the plan is created later in the package.
- Whether a valid plan exists for `unqualified` or `manual_required`.
- Whether an adapter that replaces `planned_supported` with `blocked` keeps the compiler's hashes or nulls them. A compiler-side `blocked` result nulls them.

The required issue-owned report goldens can't be fixed byte-for-byte until this is settled.

**Fix:** Add a small table:
- The compiler deterministically derives the plan whenever it emits `planned_supported`, and both hashes are non-null.
- For `unqualified` and `manual_required` with valid semantics, `cueScheduleHash` is non-null and `executionPlanHash` is null.
- For a compiler-side `blocked` result from semantic refusal, both hashes are null.
- An adapter replacement keeps the compiler's hashes unchanged.

## Verified with no finding

- **v2 deferral:** Two explicit statements, the design's §7 paragraph and the CN's "Approval scope is v1 only" block, together with the deferred report row, make every v2 row and branch deferred and unowned. They are outside CN approval, and the existing closed-schema refusal stays in place. v2 schemas, `contracts-v2.ts`, v2 Python generated modules and `compiler-core-v2.ts` are explicitly unchanged.
- **Runtime owner:** #220 is v1-only and blocked by #8, #167, #218 and #99. This satisfies the live issue's requirement of #8 AND #167 plus #218. The design keeps the #8 hard gate and doesn't dispatch anything.
- **Earlier non-blocking items, now resolved:**
  - closed `contentPin` union,
  - a single addressed `recordRange` shape with an equality check against the v1 event,
  - `profileId` issued by #99 and the format of `profileEvidenceHash`,
  - prefixed `datasetSha256`,
  - required provenance on the new Table branch,
  - total diagnostic sort order.
- **Unchanged parts:** The algorithm in §4, all expected schedules in §5, the hash domains (`S`, `P`, byte hashes, #20) and the profile limits are unchanged from the earlier passing review. The delta does not regress them.

## Non-blocking cleanups

- **Generated-types sentence:** The CN reads "from changed v1/v2 script/dependency/manifest/report v1 roots". Drop "v1/v2" so it can't be read as regenerating v2.
- **Branches in the v1 schema:** State that the v1 schema includes only `visual_event` and `v1_curated`. Right now this follows only from the general "v2 union branch deferred" wording.
- **Locator in `timingInputHash`:** Hashing the full `NarrationDependency` pulls in `audio.locator`, so relocating the audio file changes `cueScheduleHash`. The result is deterministic, but it sits awkwardly with "locators outside content identity". Either accept this as build identity, or hash the dependency without the locator.
- **"Retained underlying artifact bytes":** Say whether this means the timing record or the narration audio bytes.
- **Empty cue-set array:** State that writers omit `graphicCueSets` rather than writing `[]`, so document bytes stay canonical.

## Not verified from the supplied inputs

- `runtime-handoff.md`, including the earlier "In progress" versus "In review" mismatch.
- The v1 `script-document` token and range shapes.
- The v1 `ContentHash` format compared with the prefixed `Hash`.

No runtime or full-suite evidence was assumed.
