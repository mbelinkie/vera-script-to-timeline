# Checkpoint 11 finished-segment review — canonical row omission transformation

Read-only review complete, bounded to the plan/disposition, `issue-144-text-revision.ts`, its test file, and the `CODE_PATHS` diff. I hand-traced the arithmetic and logic rather than trusting the summary, since this is the most safety-critical text-transformation code in #144 so far.

## Core correctness — traced and confirmed sound

**Joining-gap coverage is complete, not approximate.** The loop `for (let index=first; index<=last+1; index+=1)` checks every adjacent pair from `previous`↔first-selected through all internal selected-token gaps to last-selected↔`following` — exactly the "preceding through selected to following, including internal gaps" requirement, with no position skipped.

**Silent unselected-text loss is structurally impossible, not just untested.** The replaced span is `[previous.endOffset, following.startOffset)`. Every character in that span is either inside a selected token's own value or inside a gap already verified pure-ASCII-whitespace by the loop above — there's no third category of character that could fall through unflagged. I verified this by construction rather than by enumerating cases: the gap-check loop and the selected-token set jointly and exhaustively partition that exact span.

**Sentence-punctuation refusal correctly covers both of its two distinct triggers**, and I confirmed both fire via different code paths in the three test strings: `previous.value` ending in `.!?` (case: `"Alpha Bravo. Charlie Delta Echo"` → `/\S+/gu` tokenizes "Bravo." as one token, caught by the first half of the check) versus terminal punctuation *inside* the selected span itself (case: `"Alpha Bravo Charlie. Delta Echo"` → "Charlie." is the selected token, caught by the second half scanning `tokens[first].startOffset` to `tokens[last].endOffset`). This is exactly the distinction the plan wanted — general punctuation inside a removed token is fine (the comma case), but `.!?` specifically is not, even when it's attached to the removed token's own value rather than sitting in a gap.

**UTF-16 delta arithmetic is correct** — I hand-traced the astral-before-cut case rather than trusting the assertion: for `"😀Alpha Bravo Charlie Delta Echo"`, `previous` ("Bravo") ends at unit 13, `following` ("Delta") starts at unit 22, so `delta = 1 - (22-13) = -8`, giving Delta's new `startOffset = 22-8 = 14`, matching the test's asserted `14` exactly. Native `.length`/`.slice`/`matchAll` all operate in UTF-16 code units already, so no special encoding step was needed here (the inverse concern from the Python-side narration handoff in checkpoint 9) — confirmed by the arithmetic, not just by reading the comment.

**Cross-narration and wrapper handling match the plan precisely.** `anchors()` tags every anchor-bearing entity with its owning narration ID (or `null` for a standalone `VisualBlock`), and the refusal `owner.narrationId===null||owner.narrationId===block.id` correctly allows standalone-visual reanchoring while refusing any anchor genuinely owned by a *different* narration row. The wrapper-version bump (`if(owner.wrapper)owner.wrapper.version=next(...)`) only executes inside the branch gated by `text!==owner.entity.range.quotedText`, so an unaffected standalone wrapper is provably never touched — confirmed by the "leaves another wrapper intact" test using full canonical-JSON equality, not a field-by-field spot check.

**Immutability, overflow guards, and hash computation** are all consistent with the already-reviewed patterns from checkpoint 6/9 (`structuredClone` before any mutation, `next()`'s safe-integer double-check applied identically to sequence/row/entity/anchor/wrapper versions, `liveContentHash` excluding itself). No divergence found.

## Two minor, non-blocking observations

- `requireFact(original?.type==="narration"&&original.state==="active", ...)` collapses three distinct failure modes (block not found, wrong block type, excluded state) into one message ("active narration row required"). Not a correctness issue — all three correctly refuse — just slightly less diagnostic than it could be. Not worth a code change on its own.
- The overflow test list (`["sequence","row","entity","anchor"]`) doesn't include a dedicated "wrapper" case. Since the wrapper bump uses the identical shared `next()` helper already proven correct by the entity/anchor cases, this isn't a correctness gap — but if you want the one missing line of coverage, add `wrapper` to that `it.each` array using the existing `standalone()` test helper.

## Scope and honesty check

Confirmed: no `compileTimeline` call anywhere in the module (validator-only, consistent with the stated reason that old narration dependencies are stale after a wording edit); no audio dependency fabricated in the return shape (`OmissionRevision.regeneration` carries only `policy/blockId/blockRevision/text/textHash`, nothing audio-shaped); no new contract/fixture/golden/dependency touched; `CODE_PATHS` gained exactly the one new file. The module makes no acceptance or authorization claim beyond what the plan specified, and the test suite's own count (37) matches direct enumeration of the file's test cases.

No blockers found. Static advisory review only — test-count and pass/fail claims were not independently executed by me.
