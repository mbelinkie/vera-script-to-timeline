# #192 initial independent review — NO-GO

Actual Claude Opus5.5, high effort, CLI2.1.299, tools disabled. Exact source d8107e752e8abe19d2ce2eeb809cd65d181285c4, base bd6048b02604954df037bf0b2dd01906e986d19d, session 55c6062c-71bc-4afc-aa91-70379f3f49ec. Completed exit0/is_error=false/sourceStillCurrent=true. Raw result SHA256 3de7f5be4d23bce079610d556ab9458418cc1dc0b6d17648fbd1bfa940a7d562. This is a NO-GO, not approval. Exact prompt/source/input/CLI/env/PID/log/exit provenance stays in out/issue192/claude-1 and review-input-1.json.

## Verbatim reviewer result

# Verdict: **NO-GO**

There is one blocking finding. It is a small, local fix inside #192-owned code. I found no other blocking defects. Everything below comes from reading the supplied source. I did not execute anything.

Line numbers for the new files are approximate. I counted them from the diff, so use the function names as the primary locator.

---

## Blocking finding

### B1. A composed or staged case is not bound to the evidence `evidence()` authenticated, so a hand-written C omission can stand in for #191's verified one

**Where**
- `python/vera_timeline_agent/roundtrip_v2_proof.py`:
  - `ProofSessionV2._observations_current`, single-case branch (≈L214–247)
  - `compose` (≈L249–268)
  - `stage`, `proposal` and `_decide_once`, which all consume through those two
- `python/vera_timeline_agent/roundtrip_v2_revised_build.py`: `verify_revised_preflight_v2`, the per-case omission check `all(value in retained_hashes for value in case["omission"]["inputHashes"].values())` (≈L245–258)

**Mechanism**
- Only `ProofSessionV2.evidence()` runs these checks:
  - `_verify_exact_view` on the baseline
  - the `roundtrip_inference_observations` authentication
  - `verify_selected_omission_v2` (#191)
- `compose()`, `stage()`, `proposal()` and `decide()` never require their case dicts to be the value `evidence()` returned. They only call `_observations_current`.
- `_observations_current` checks just two things:
  - `evidence["current"]["rawJson"]` was captured by this session.
  - A fresh capture reproduces the same raw and derived-audio hashes.
- It does not check `bindingJson`, the `baseline` packet, `current.receiptJson` or `omission`.
- `compose()` then registers whatever dict it was given in `case_sessions`.
- The TS checks in `proposeV2Edits` for C are all values a caller can compute from the captured packets:
  - `baselineHash` and `currentHash` equal the two receipts' `derivedAudioHash`
  - the literal `recordIntervalFrames {121,127}`
  - `tokenIds == [row.tokens[11].id]`
  - status and evidence-level strings

**Concrete failure**
1. Capture C before and after the real non-ripple lift.
2. Build a dict using the real `bindingJson` and packets, plus a hand-authored `omission`:
   - `status: "verified"`, `evidenceLevel: "local_consistency_only"`
   - matching `documentHash`, `baselineHash`, `currentHash`
   - row 1, `blockRevision: 1`, `tokenIds: [token11]`, `recordIntervalFrames: {121,127}`
   - `channels: []`, `inputHashes: {}`
3. Pass it to `compose([...])`, or straight to `stage()` for a C-only flow.

What happens next:
- Inference yields C.
- The flow proceeds through #191 synthesis, proposal, the #202 decision and `PreparedRevisedProofBuildV2.preflight()`.
- `verify_revised_preflight_v2` passes the C pin check vacuously, because `inputHashes` is empty.
- No selected-window review, pristine/edited render comparison or listening receipt was ever verified.

The only remaining stop is the external authority callbacks (`roundtrip_inference_currentness`, `roundtrip_row_handoff`, `revised_proof_lineage`). They could only refuse if they kept their own ledger of what `evidence()` produced. That duty is not documented for these new `roundtrip_*` kinds, and the test authority does not model it.

This breaks the issue's requirement: "Consume B3 independently verified C … no manual AI rewrite or authored proposal JSON stands in for inference." A weaker form of the same gap lets a caller supply a forged `bindingJson` or baseline receipt, because only `current` raw/audio is re-observed.

**Smallest fix**
1. In `evidence()`, before the final `_observations_current(value)`:
   - immutably publish and pin the returned record, for example at `root/evidence/<identity>.json`;
   - add its identity to an `authenticated_evidence` set.
2. In the single-case branch of `_observations_current`, require:
   - that the case's identity is in that set;
   - that `bindingJson` equals this session's `binding_pin` bytes.

   `compose`, `stage`, `proposal`, `decide` and `accepted_revision` then inherit the check.
3. In `verify_revised_preflight_v2`:
   - require each case's pinned evidence record to be present in `verifiedFiles`;
   - require a non-empty #191 `inputHashes` for C, ideally the verifier's required keys.
4. Add a negative test: a hand-authored omission, a foreign `bindingJson` and a forged receipt are each refused at `compose`/`stage`, with zero provider or native effects.

---

## Non-blocking defects and hardening

These are recommended, and none is gating.

- **N1. Reopened-target check is incomplete.**
  - `ProofSessionV2._verify_exact_view`, used by `verify_reopened`, compares inventory, extent, track, record/source range, `sourceId` and `authoredEvent`.
  - It does not compare route `gainDb`/`channelMap` against the view event's `gainDb`, or AV link topology.
  - A reopened target with the Quiet source at 0 dB instead of −18 dB, or with unlinked B/final AV pairs, returns `status: "verified"`.
  - This is not blocking because `verify_reopened` already requires #177's owned verified delivery first. It is still the place a later drift would be caught.
  - Fix: add the gain/channel and link-group comparison.

- **N2. The synthetic rebuild shortcut does not exclude real R16 originals.**
  - `_require_accepted_rebuild` accepts the shortcut whenever both requests say `synthetic_local`.
  - #190's frozen synthetic lane does not reject `R16_INPUTS`, so R16 bytes run in that lane could be rebuilt as "synthetic", without the revised lineage guard.
  - Mitigations: the authority receives `originalInputs`, and #177 refuses fractional creation before the adapter.
  - Fix: one line requiring `self.baseline.original != R16_INPUTS` on that path.

- **N3. The revised build is not tied to the revised native route.**
  - `request_fresh_delivery` does not assert `fresh.revised_preflight_hash is not None` when `revised` is a `PreparedRevisedProofBuildV2`.
  - Exploiting this requires crafting a local initial-shaped proof package and preflight, so the risk is low.
  - The fix is cheap.

- **N4. Currentness capture names collide across sessions.**
  - `_observations_current` names its captures `integration_current_{n}` with a per-instance counter.
  - A restarted or second session on the same boundary root hits an uncaught `FileExistsError` from `_exclusive`.
  - This fails closed, but it blocks the restage path described below.

---

## Actual-D1 evaluation (the requested gap analysis)

What holds:
- Production code contains no hard-coded D1 and no six-frame subtraction.
- Composed placement comes from the fresh boundary evidence `durationSamples` through the compiler.
- TS cases 187/200/213 assert the δ algebra.
- The public path measures compiled D1 from injected-provider output (187).

The gap:
- Prepared media, including row 1's D1-dependent base requirement (`192:prep:30`), must be supplied at `stage()`, before synthesis.
- #191's handoff binds `priorDependenciesHash` to those staged dependencies (`finalizeReplacementV2`).
- `staged-*.json` files are immutable per session root.
- The public test only succeeds because the provider and the preparation are both configured to 187.

What this means for a real run:
- It needs a probe pass to learn D1, then a restage in a fresh session root. That is feasible: #191's intent and cache replay prevents a second provider call. It is undocumented, untested and hindered by N4.
- No test covers actual D1 differing from the prepared duration.

Two things I could not establish:
- This ordering comes from #202's design (its comment says to bind #191 "after preparing media for the actual fresh row duration"), and that design is circular.
- I could not tell from the supplied source whether a longer prepared range merely covers the need or must match it exactly.

Assessment:
- This is not a safety defect, because a mismatch blocks the compile.
- Recommended: add a mismatch test and document the flow, or ask the #202 owner to apply D1-dependent preparation after finalize.

---

## Verified, with no defect found

- **Frozen #190 boundary.** The native change is additive.
  - The initial constructor's shapes, versions, R16 guard, locks, effects and recovery are unchanged; only its tail was refactored into `_initialize_binding`.
  - The initial route refuses revised records by shape.
  - The revised route rechecks lineage on every `_guard` call.
- **Hash domains are used correctly.**
  - Compiler domain (`_compiler_hash`): `proposalHash`, `decisionHash`, `historyHash`, `revisedDocumentHash`, `priorDependenciesHash`, baseline document/dependency hashes.
  - Python raw/identity hashes: file pins and `inferenceHash`.
  - The fractional evidence bridge binds the runtime, the exact stdin bytes and the pinned CLI source. The TS hash of Python float JSON round-trips consistently.
- **C split UIDs.** Each split must be a distinct new UID with otherwise identical stable fields. The 0–200 narration-only check and Quiet-source preservation are enforced.
- **A/B checks.**
  - Recognition is finite and exact.
  - B checks reciprocal AV links, the 24000/1001 logical rate and the explicit final shift.
  - D (picture-only), ripple, track, marker, speed, enable/online, source and target deltas all refuse.
- **#202 decision path.** Decisions recompute the full proposal, so a forged candidate fails. Decisions are single-use per session root.
- **No relabeling inside the revised consumer.** The R16 biconditional holds, and prior builds and targets are untouched.

---

## Speculation (not findings)

- **Real Resolve behaviour is unqualified.** The A still-image head trim is modelled as `sourceEnd −113` (generator semantics). The endpoint convention and speed fields are likewise unqualified against real Resolve; #178 owns that.
- **Decision uniqueness across session roots** depends on the authority. It receives enough context (`proposalHash`, `history`) to enforce this.

---

## Acceptance status

This is not closure. Still outstanding:
- The full serial gate is pending.
- #202 is not canonically Closed/Done, which blocks Ready and claim.
- A successful fresh delivery and save/reopen is exercised only through the transport double. The genuine revised path stops truthfully at #177's fractional refusal.
- All authority, native and provider ports are fakes. #178 and #145 gates remain open.

After B1 is fixed, a delta review plus affected focused and fast checks should precede the final full run.
