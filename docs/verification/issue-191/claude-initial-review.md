# Claude CLI antagonist review: VERA #191, selected phrase proof and whole-row replacement

**Reviewed commit:** `2d9709d93a5300fad881a4c66283e3d05c20ab4c` (branch `codex/issue-191-selected-phrase-proof`, integration baseline `4e31565f…`)

**Basis:** Only the supplied content. That is the policy, the #191 requirements, #189 §§4–6 and CN-189-A/B, the eight complete new runtime/test files, the frozen connected sources, the walkthrough and the integrated fast log. I ran nothing and could not recompute the `source-audit-integrated.json` hashes. I reviewed the supplied text as if it were those files.

**Reviewer identity:** Claude Opus 5.5 (`claude-opus-5-5`). The CLI response metadata is the authoritative record.

---

## Blocking findings (fix before the final gate; both are small)

### B1. Medium: a zero-width outer join lets the transform split a written word and invent a space

- **Where:** `packages/contracts/src/issue-189-v2-omission.ts:17` (`JOINING_GAP = /^[ \t\r\n]*$/u`), used at `:368-373`, with the rebuild at `:386-389`.
- **Mechanism:** The gap loop checks the gap from the previous token into the phrase and from the phrase into the following token. Because the pattern uses `*`, an empty gap passes.
  - Take valid text `"Alpha BravoCharlie Delta Echo"`, tokenized as `Bravo [6,11]` and `Charlie [11,18]`. The v2 validator only requires ordered, non-overlapping exact slices, so this is valid.
  - Removing `Charlie` passes every check and produces `"Alpha Bravo Delta Echo"`.
  - The result removes part of one written word and inserts a space that was never there. This is the sub-word omission that #189 §4 C forbids ("never call a partial phoneme cut a word omission"). It happens on valid input, without refusal, inside a hash-bound accepted edit.
- **Minimal fix:**
  - Require the two outer gaps (`index === firstRemovedIndex` and `index === lastRemovedIndex + 1`) to match `/^[ \t\r\n]+$/u`.
  - Interior gaps between removed tokens can stay as they are, or be made strict as well.
- **Test:** `rowWith(["Alpha","Bravo","Charlie","Delta","Echo"], [" ", "", " ", " "])` must throw `/joining-gap/`. Add the mirror case with an empty gap after the phrase.
- **Optional, same spot:** a `\n` gap is currently collapsed to `" "`. Either refuse it or record it as an accepted judgment.

### B2. Medium (test evidence): three named refusal cases do not exercise the mechanism they are named for

None of the refusal tests at `tests/test_issue191_audio.py:450-522` assert a reason; they only check `status == "refused"`. Tracing each fault:

| Fault | What actually refuses it | Code path left unexercised |
|---|---|---|
| `extra-cut` (`:459-460`) | Segment `("extra", 8,9,7,8)` has `sourceStart 7 < previous_source 8`, so the `_observation` ordering check refuses it (`roundtrip_v2_audio.py:189-202`). | The "exactly one interior lift" count check (`:448-451`). No test has three well-formed segments. |
| `partial-render` (`:491-492`) | The edited render receipt still binds the original `outputHash`, so the fake authority refuses with "receipt binding mismatch". | `_pcm` decoded-extent refusal for a well-formed but short programme render. |
| `alias` (`:467-468`) | Duplicate `sha256`. | The decoded-alias check (`:329-330`). No test supplies the same PCM in different bytes. |

The issue explicitly requires tests that exercise extra-cut, partial and alias refusals, and the focus list names decoded aliases. By inspection the code checks themselves are correct. The acceptance evidence, however, overstates what was exercised.

**Minimal fix:**

- **`extra-cut`:** Use well-ordered segments: left `(0,2,0,2)`, `(3,4,3,4)`, right `(5,8,5,8)`. Expect "exactly one interior lift".
- **`partial-render`:** Bypass `native_render` authentication, as `test_malformed_render_returns_refusal` already does. Expect "decoded extent differs".
- **Decoded alias:** Add a source that re-encodes `speech` as 24-bit (`v*256`). It decodes to identical floats from different bytes. Expect "decoded source alias".
- **All cases:** Parametrize the expected reason substring and assert it.

---

## Non-blocking findings and suggestions

1. **Low: adjacent-read equality is type-loose.** `roundtrip_v2_audio.py:422` uses `current == second` on parsed JSON. Python treats `true == 1` and `0 == 0.0` as equal, so two adjacent reads that differ in type compare equal. Only `current-a` passes through `_observation`'s type checks. The v1 verifier compared canonical bytes.
   - The `frameRate == RATE` checks at `:112` and `:305` are similarly loose: `24000.0` passes, and the integer types are not checked as they are for `speed`.
   - Fix: compare `files.hashes["current-a.json"] == files.hashes["current-b.json"]` (or canonical bytes), and add `type(...) is int` checks on the rate parts.
2. **Low: a malformed document can raise instead of returning a refusal report.** If `row["text"]` is not a string, `.encode` at `:287` raises `AttributeError`, which is not in the except list at `:557-565`. The caller-pinned compiler-canonical document makes this unlikely.
   - Fix: add `fact(isinstance(row["text"], str), …)`.
   - Separately, the port contract should state that authenticators raise `ProofBuildError`. The fake's `assert` for `selected_review` (`tests/test_issue191_audio.py:327-328`) raises `AssertionError`, and would silently accept anything under `python -O`.
3. **Low/Medium coverage: no non-unity gain is ever tested.** Every route uses `gainDb: 0` (`tests/test_issue191_audio.py:172`), so `10 ** (gainDb/20)` at `_mix:215` is never checked against an independently built render. The focus list names "known observed gains".
   - Add a positive case with, for example, −6 dB and −3.5 dB routes, plus a negative case where the observed gain differs from the rendered gain.
   - This also confirms that `_parse`'s float type (`_number`, not supplied to me) survives `type(gain) in {float, int}`.
4. **Low: generation source pins are incomplete.** `_sources()` at `roundtrip_v2_narration.py:34-43` globs `packages/contracts/src/*.ts` non-recursively.
   - It omits `src/generated/**` and the Python modules this flow executes: `roundtrip_audio.py` (`_pcm`), `roundtrip_build.py` and `roundtrip_proof.py`.
   - The authorization binding therefore does not cover all the code that shapes the receipt. Fix: glob recursively and add those three modules.
5. **Low/question: finalize rebuilds the document header without binding the prior dependencies to the base document.**
   - `issue-189-v2-replacement.ts:61-63` builds `dependencies.document` from the revised document and `prior.document.revision + 1`.
   - Nothing in B3 checks that `prior` was compiled for the omission's base document (`edit.expectedDocumentHash`). That binding rests entirely on the authorization port.
   - Per-row revision and text-hash checks limit the damage. Still, it would be cheap to carry the base document hash or `liveHeadSequence` in the request and check `prior.document.liveHeadSequence + 1 === document.liveHeadSequence`.
   - I could not verify that the `liveContentHash` formula (`omission.ts:403-405`) or the `textHash` join formula (`replacement.ts:63`) match the repository convention. The compiler accepted both in the fake path.
6. **Low: punctuation coverage is narrow.** The sentence-punctuation guard only covers `.!?`. A selection such as `"(Charlie"` or `"“Charlie"` whose closing pair lies outside the phrase leaves the text unbalanced. Optionally refuse bracket and quote characters in the selected text or at the join.
7. **Evidence/process: attempt 2 has no recorded disposition.** The diff adds `attempt-2-full-validation.{json,log.gz}`, but `acceptance.md` only describes the interrupted attempt 1, and you state that no full gate has passed. Record attempt 2's outcome and disposition before closure, and never present it as acceptance.
8. **Limit, not a defect: anchor-owner completeness.** The transform enumerates these anchor owners:
   - slots (content `boundaryBefore`, return `inpoint`)
   - overlay timing
   - annotations and performance beats
   - supporting-item placement and `displayAttachment`

   Without the generated v2 schema I cannot confirm that `notes`, `ideaOutline`, `extras` or payload fields carry no anchors. A schema-walking completeness test would turn this into evidence.

---

## Verified as sound (adversarially traced)

### Selected phrase and neighbors
- Selection is contiguous and interior, and supports equal the selection plus exactly the immediate neighbors (`zip(..., strict=True)`).
- Token ID, UTF-16 offsets and quote must match the validated frozen tokens; boolean and float offsets are refused.
- Supports are ordered and non-overlapping, and lie within the source.
- The cut is `left.end ≤ cut_in ≤ first selected onset` and `last selected end ≤ cut_out ≤ right onset`, with neighbors inside the whole segment. Neighbors stay fully retained and every selected token is removed.

### Geometry
- FRAME 2002 equals 48000 × 1001 / 24000, and the rate must equal exactly 24000/1001.
- Speed must be integer 1/1.
- Segment checks enforce record span = source span, non-overlapping ordered segments per route, `sourceEnd*FRAME ≤ source length` and `end ≤ extent`.
- Split checks require preserved left start and right end, a non-empty gap, record gap = source gap (no ripple), and new split UIDs.

### Inventory
- Routes and sources form an exact bijection. Unknown control keys are refused by exact shape.
- Booleans are refused for gain, pan and limiter.
- Sources are de-aliased by path, bytes and per-channel decoded hash. Unrelated routes must be identical.
- The aggregate budget is checked before decoding, and partial source frames are refused (`readframes(count+1)` plus a length check).

### Residuals
- Both full stereo programmes are reconstructed per channel using the established `_metrics` thresholds of 0.0004 RMS and 0.006 maximum over a sliding 20 ms window.
- The sliding-window, right-channel and later-frame test is genuine: the burst stays under the RMS gate but exceeds the sliding gate.
- A result labels itself `local_consistency_only`, and every authenticity claim goes through the required injected port.

### Transform
- The document is validated before and after. The input is never mutated (clone, with tests).
- Every removed endpoint is refused before cloning, and cross-row owners are refused.
- Only enclosing same-row ranges refresh, using exact affinities, with version bumps. Astral text, surrogates and determinism are covered.

### Narration
- The request and currentness checks run before any provider call.
- A cache-scoped intent sits under a lock keyed by request hash. An uncertain missing synthesis is refused from any directory, and threaded concurrency yields one call.
- Replay reverifies all cache layers.
- Fresh asset ID, audio, timing and revision are enforced on both sides, so identical timing hashes, including empty ones, are refused. The old review cannot supply boundaries.
- Only the target row's dependency is replaced, with two byte-identical compiles plus an input-preservation check. Old cache files and other rows are preserved.

---

## Cloud eligibility

**Eligible for the qualified `--scope excluding-media-sensitive` substitution, subject to the conditions below.**

**Why it is eligible:**
- The diff adds no FFmpeg/FFprobe caller, renderer or prober.
- It changes no existing media path, manifest, lockfile, workflow, profile or tool configuration.
- The new verifier decodes already-produced PCM with stdlib `wave`, in-process and deterministically, the same way frozen #144 does.
- The narration tests inject `FakeProvider` and `FakeNormalizer`. The only subprocess is `node`.

**Conditions:**
1. The accepted-main validator must exit 0 on the exact delivered tree, with the required profile digest.
2. If the profile's media-sensitive selector classifies `tests/test_issue191_*.py` (for example alongside the #144 audio tests), those tests drop out of cloud coverage and must run serially on the Mac.
3. The cloud runner must provide exactly Node v24.19.0. Otherwise the bridge refuses and the narration tests fail closed, which is not a false pass.
4. I could not verify that the base `Normalizer.__init__` never probes FFmpeg. Confirm that before relying on the cloud run.

Cloud evidence certifies none of the following: Mac media tools, real renders, provider calls or listening.

---

## Verdict

**NO-GO at `2d9709d`** for the two small blocking items:

- **B1:** a code fix plus one test.
- **B2:** test-evidence fixes for extra-cut, partial-render and decoded alias, plus reason assertions.

After those fixes, focused tests, `validate:fast` and a Claude delta re-review, I expect **GO** for this bounded B3 implementation. That GO stays conditional on one complete passing final gate on the reviewed source: either the serial local `VITEST_MAX_WORKERS=1 npm run validate` or a qualifying cloud run as described above. The non-blocking items are recommended but do not affect the GO.

**Scope of the GO:**
- It covers local consistency and fake-service evidence only, within #189 B3.
- It does not qualify real acoustic review, native lifts or renders, provider calls, cost or consent, or #190/#178/#145 work.
