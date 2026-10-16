# Independent delta review

Actual reviewer `claude-opus-5-5`, high effort, tools disabled; Claude CLI 2.1.296. Session `56cde4df-2e79-40cb-911f-fb3150105cc2`; exact source `5ec08503d4c04f9d660592db7251fe8b94c1b7d8`, completed exit 0, `is_error: false`, source current. Raw response SHA256 `e1ff116e533f4527c2698de102be22a7367eb5a90b1bd86fcf9e6401b8372ca8`. Prompt SHA256 `9932e14a984bd47dc919880346e0053a6e8ba68aa87fef77864df6f59a141fd1`. Exact private command/input/result records remain in ignored `out/issue-202/`.

# Delta review: #202 at `5ec0850` (over accepted baseline `bd6048b`)

**Verdict: GO. I found no blocking findings in the supplied delta.** The candidate is ready for the complete `VITEST_MAX_WORKERS=1 npm run validate` gate and a qualifying #196 run. I reviewed only the supplied own-source and test delta and its connections to #191 and #177. Line references are to the pasted text.

## Invariants re-checked

### Unchanged by the delta
None of these paths were touched, so the initial analysis still holds:
- **Timeline freeze:** the preview compile is frozen into `dependencies.timeline`, recompiled, then the manifest/report/dependencies equality and `dependenciesHash` closure are checked. This all happens before `proposalHash`.
- **#191 binding:** `finalizeReplacementV2` still checks `priorDependenciesHash` against the unfrozen `stage.dependencies`.
- **Rational timing and D1 composition:** unchanged.
- **Refusal ordering:** the order of the `keys`, version, range and allowed-key checks is unchanged.

### `ready()`
- The semantics are identical to before: it refuses when `!ok` or when `status !== "ready"`.
- Serialization now happens only on failure, and only diagnostic codes are included. Successful compiles no longer serialize the manifest, the report or any locators.
- Narrowing for the return type still works.

### Hash identity and determinism
- `comparison` is now `[...textRows, ...rows]`. Both it and `comparisonText` sit inside `value`, so `proposalHash` binds them.
- `blockLabel` depends only on `input`, which is the baseline document.
- Event IDs and source IDs are sorted, so `decideRevisionV2`'s rebuild-and-compare stays deterministic.
- The existing tampered-`comparisonText` test still covers this.

### Labels
- No command adds or removes blocks or slots, so resolving labels against the baseline is sound.
- `Block 3 (narration), slot 2` correctly identifies slot `id(23)`: the blocks are r1, 40, r2, 50, 60, note, and r2's slots are 22, 23, 24.
- Events with a null block ID fall back to `Programme`.
- Narration-text rows are now in document order.

### Escaping
- `escapeCell` escapes backslashes before pipes and collapses newlines.
- It is applied uniformly to the label and both cells, and raw strings now pass through it too.

### Source rows
- Sources are compared per ID.
- Added and removed sources render as `Absent` against a summary.
- The full source objects remain in the structured `comparison`, so nothing is lost from the hash-bound record.

## New tests

Each new refusal is isolated to the intended guard:

| Test | Why it isolates the guard |
| --- | --- |
| Unrelated `prep:41` | `affected` is {20, 50}, and the owner of `prep:41` is visual-only block 40. `prep:51` is processed first, so the refusal can only come from 41. |
| Profile / authorization | Each changes only `preparedMedia[0]` (`prep:51`), which passes the allowed-key check. |
| Muted picture-only trim | The baseline is asserted `ready`. The A boundary applies cleanly first, then the trim guard refuses. |
| Unexpected handoff | A/B produce no regeneration, so the refusal can only come from `request.handoff !== null`. |
| Malformed history | `decision(proposal, history)` makes `historyHash` match, so only the format or uniqueness check can fail. |
| Wrong `proposalHash` | All earlier checks pass, and the rebuilt proposal equals the original. Only `decision.proposalHash` differs. |
| B audio endpoints | 48000 · 1001 / 24000 = 2002 samples per frame with origin 0. Asserting both exact endpoints is stronger than my span suggestion. |

Every mutation check is on the original `input`; the picture-only case uses a clone.

## Non-blocking (optional; no new scope)

### 1. Readable cells can still look identical when values differ
`readable()` summarizes only a subset of fields:
- **Events:** the summary omits `sourceId` and any `audio` fields other than policy, gain and `sampleRange`.
- **Delivered sources:** the summary shows only the media ID, original/delivered hashes and mapping hash.

If two unequal objects differ only in the omitted fields, the Before and After cells render the same. This doesn't affect hash binding, because the structured rows remain complete. A one-line guarantee would be to append `; impact ${sha256CanonicalJson(value)}` in the event and source branches.

### 2. Source-summary rendering is not positively asserted
The A/B assertions on `track`, `picture` and `mapping` are all satisfied by event rows alone. The C tests don't check `comparisonText` at all. One assertion would cover it, for example `toContain("narration text")` plus `toContain("Narration asset")` in a C case.

### 3. Older assertions are still unpinned
The original stale/malformed loop, the decision-input checks and the accept-after-accept check still use bare `.toThrow()`. The new tests are pinned.

### 4. Disposition wording
`review-disposition.md` still says "Before the final full gate, address…". Now that `5ec0850` implements those items, it reads like a to-do list. Consider rewording it in the past tense.

**My recommendation:** proceed to the full gate as-is and record #1–#3 as accepted limitations. Any change to source or tests would require another fast run and another delta review first.

## Limits
- **No tools were used.** I made no edits and ran nothing. Every claim comes from reading the supplied text.
- **Not independently verified:**
  - The fast receipt (`5ec0850`, tree `1ef1414`, both steps exit 0, `sourceCurrent: true`) is taken as supplied.
  - I can't confirm the claim that the #190 merge (12 new files) leaves the consumed compiler, validator, edit, omission and replacement sources, the frozen contracts and fixtures, the config and the lockfiles unchanged. The supplied own diff touches only the three #202 files.
- **#177:** only the guard fragment was available. The timeline, tracks and roles equalities hold by construction, as before.
- **No qualifying full gate has run yet**, so this is not acceptance.
- **Earlier failures remain failed.**
- **No native, provider or authentication claims** are made here; those remain with #192/#190.
