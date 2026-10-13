# Claude CLI antagonist delta re-review: VERA #191

**Reviewed commit:** `858d08ea21295690b689502f50267c0058ff92ca`. Per the stated check-input equivalence, its executable and check source is `590c7ed817acdb386d1023010d88f2f3c7a023b8`. The fix delta is measured against the initial NO-GO at `2d9709d93a5300fad881a4c66283e3d05c20ab4c`.

**Basis:** I used only the supplied content: the fix diff, current sources, current tests, the schema excerpt, the frozen `Normalizer` excerpts and the retained delta evidence. I did not execute anything or recompute any hash. Where I say a check is reached, I traced it by inspection. The 53/53 focused run and the fast-gate log corroborate those traces.

**Reviewer identity:** Claude Opus 5.5 (`claude-opus-5-5`). The CLI response metadata is the authoritative record.

## Verdict

**GO, conditional on one complete passing final gate on the delivered tree.** Both initial blockers are closed. I found no remaining blocking or substantive defect in the fixes or the adjacent trust, timing and refusal seams.

---

## Closure of the initial blockers

### B1 (zero-width outer join): **Closed**

- **The fix:** `issue-189-v2-omission.ts:17` now uses `/^[ \t\r\n]+$/u`. The loop at `:368-373` runs from `index = firstRemovedIndex` to `lastRemovedIndex + 1`, so it covers three gaps:
  - previous token → first removed token
  - every interior gap
  - last removed token → following token
- **Why this is sufficient:** A gap is exactly the text between two consecutive tokens. Every character between `previous.endOffset` and `following.startOffset` is therefore either a removed token or plain whitespace.
  - The rebuild at `:386-389` keeps only the text up to `previous.endOffset` and from `following.startOffset` onward.
  - So every removed token is bounded by whitespace on both sides, and no written word can be split.
  - The neighbors stay byte-identical.
- **Tests:** `issue-191-omission.test.ts` covers both mirror cases (`["", ...]` before the phrase and `"" ` after it). Each first asserts that the v2 validator accepts the input, then expects `/joining-gap/`. This is the exact counterexample from the initial review.
- **Side effect:** Interior zero-width gaps now refuse as well. For example, `BravoCharlie` tokenized as two tokens can no longer be removed as one written word. This is a conservative false refusal, not a false accept, and it is disclosed in the disposition.
- **Line breaks:** Collapsing `\n` to a single space is recorded as an accepted judgment. That disposes of the optional item.

### B2 (refusal tests not exercising their named mechanisms): **Closed**

| Fault | Path traced on the current test | Reaches |
|---|---|---|
| `extra-cut` | The segments `(0,2,0,2)`, `(3,4,3,4)` and `(5,8,5,8)` pass every `_observation` check: order, span equality, `8*FRAME ≤ len`, `end ≤ 12` and unique UIDs. Routes and controls are unchanged and the unrelated routes are equal. | `len(new["segments"]) == 2` at `roundtrip_v2_audio.py:452-455` |
| `partial-render` | The pristine render authenticates and passes. Only `native_render` is bypassed for the 11-frame edited render. `_pcm(raw, 2, 12*FRAME)` then refuses. The test ID in the log confirms the reason. | Frozen `_pcm` decoded-extent refusal at `:527` |
| `decoded-alias` | The 24-bit source holds `v*256` in its own file, and the test asserts its pin differs from speech. It decodes as `v*256/2^23 = v/2^15`, the same floats as the 16-bit speech. `speech` is processed first, so its channel hash is already in `decoded`. | `:334` "decoded source alias" |
| All 19 cases | Each case now asserts its reason substring. I traced each reason against the source; all match the intended check. | — |

---

## Non-blocking dispositions from the initial review (verified)

1. **Adjacent reads and rate types: fixed correctly.**
   - Adjacent reads are now compared by raw byte hash (`:426`). Because `current-b` is byte-identical to the `_observation`-checked `current-a`, it is fully type-checked as well.
   - The integer-rate checks at `:114` and `:309` short-circuit after `== RATE`, so a non-dict value cannot raise `AttributeError`.
   - The regressions assert exact reasons.
2. **Malformed text and port contract: fixed.**
   - The text check at `:289` comes before `.encode`.
   - The port docstring now states that rejected receipts raise `ProofBuildError`.
   - The fake authority raises `ProofBuildError` explicitly instead of using `assert`.
3. **Non-unity gain: fixed.**
   - The positive case uses −6, −3.5 and −2 dB with a single final `round()`. That gives a residual RMS of about 0.5/√3/32768 ≈ 8.8e-6, under the 2e-5 assertion. It also confirms that `_parse` floats survive `type(gain) in {float, int}`.
   - The negative case changes only the speech gain in both observations, bypasses only native receipts and fails with the exact residual reason.
4. **Source pins: fixed** for every named seam: recursive `src/**/*.ts`, generated types and the three executed frozen helpers. There is a regression test for this.
5. **Base-document binding: disposition accepted.**
   - `finalizeReplacementV2` checks `priorDependenciesHash === sha256(prior)`.
   - The authorization binding authenticates that hash together with `revisedDocumentHash`.
   - Binding prior to base is the trusted port's job by design, not an optional flag.
6. **Punctuation profile: disposition accepted.** It is conservative, and an unsupported join refuses.
7. **Attempt 2: disposition recorded.** Both interrupted local attempts remain non-passing history.
8. **Anchor-owner completeness: confirmed for every supplied definition.**
   - Anchors live in four places:
     - `annotations` and `performanceBeats` (`range`)
     - slot `boundaryBefore` with `spoken_word` or `audible_word_end`, and return `inpoint`
     - overlay `timing`
     - supporting `placement` (all four kinds, including `priorAnchor`) and `displayAttachment`
   - These carry no anchors:
     - `notes` (strings)
     - `previous_media_end` (only a slot ID)
     - `between_blocks` and `event_edge` (only block or event IDs; `checkPointAnchor` checks them as stale-only)
     - `NoteDraftBlock`
     - `ideaOutline` and `extras` (fixed at `maxItems: 0`)
   - Four definitions were not supplied: `PrimaryVisualPayload`/`NarratedVisualPayloadV2`, `SlotRelation`, `SourceReference` and `ScriptSettings`. I accept them on the stated representation that they hold no anchor references. A `$ref`-walking test would turn that into evidence.

---

## Remaining findings

**None blocking.** These optional, low-severity suggestions need no unrelated cleanup:

- **S1. Test precision (`tests/test_issue191_audio.py:519`).** The `alias` case expects the substring `"source alias"`, which also appears inside `"decoded source alias"`. By trace it does reach the byte-hash check at `:325`, because the duplicate `sha256` refuses first. The assertion just could not tell if that changed.
  - Minimal fix: compare the reason exactly for this case, e.g. `result["reason"] == reason`.
- **S2. Profile consistency (`roundtrip_v2_audio.py:346-356`).** The audio verifier accepts any contiguous interior token selection without the transform's whole-word join rule. A "verified" consistency report can therefore exist for a sub-word token selection that `applyAcceptedOmissionV2` would refuse. The transform remains the only path to a hash-bound edit, so nothing unsafe is accepted.
  - Optional fix: apply the same nonempty-whitespace gap check over `tokens[first-1 : last+2]` to `row["text"]` and refuse with the same reason.
- **S3. Evidence sanitization.** The retained `status.json` redacts the worktree as `<local-worktree>` but keeps `PATH` entries under `/Users/<user>/…`. If the committed `docs/verification/issue-191/delta-check*.json` or the receipt carries the same `PATH`, redaction is inconsistent with the "sanitized documentation" requirement. Let the frozen privacy audit decide; redact if it does not already permit this.
- **S4. Disposition wording correction.** The fake normalizer does not override `tool_fingerprint`. It pre-seeds `_fingerprint` in `__init__`, so the lazy property returns the cached value and never reaches `_run`. The conclusion is unchanged: no media tool is invoked through that path.

---

## Cloud eligibility under `--scope excluding-media-sensitive`

**Confirmed eligible, with one correction (S4 above).**

Why it qualifies:
- The delta changes only these files: issue-owned TS and Python source, issue-owned tests, and evidence documents.
- It touches no profile, approval file, `scripts/cloud-evidence*`, workflow, package or Python manifest, lockfile or tool configuration.
- It adds no FFmpeg/FFprobe caller, renderer or prober.
- The added PCM handling is stdlib `wave` decoding only, as in frozen #144.
- The frozen `Normalizer.__init__` only stores tool names and the profile; probing is lazy.

Eligibility is necessary but not sufficient. Accepted-main `cloud-evidence-validate.mjs` must exit 0 on the exact delivered tree with:

- profile digest `1d6b3c41…257c7`
- `manifest.source` taken from the run artifact
- tested tree equal to the delivered tree on the required integration baseline
- every same-source attempt either green or dispositioned

Two practical points:

- **Avoid changing the tree after the cloud gate.** The cloud validator compares exact trees. Commit this retained review and its disposition before triggering the gate. Recording the gate result afterwards changes the tree, so that receipt must either stay out of the tested tree or follow the policy's documentation-equivalence route. Check this before relying on the run.
- **Media-sensitive tests and the Mac.** If the profile classifies `tests/test_issue191_*.py` as media-sensitive, those tests must still run serially on the Mac.

A cloud failure caused by a hidden media-tool call in `NarrationService` paths not shown here, or by toolchain drift, would fail closed, not pass falsely.

## Final gate conditions

The GO stands only after **one complete passing final gate** on `858d08e` or a later delivered tree whose additional changes are proven unread by checks. That gate is either:

- the serial local `VITEST_MAX_WORKERS=1 npm run validate`, or
- a qualifying cloud `Validate` run meeting every condition above.

Running the gate on the delivered tree makes the `590c7ed` → `858d08e` documentation-equivalence claim non-load-bearing for full acceptance. That claim still matters for reusing the fast evidence, and I accept it as stated.

## Scope of the GO

This GO covers #189 B3 local consistency and fake-authority evidence only. The authentication port is a required trusted dependency. The fake authority and local proofs do not certify:

- real acoustic review or listening
- native Resolve lifts, renders or observations
- provider identity, consent, cost or calls
- #190/#178/#145 work
