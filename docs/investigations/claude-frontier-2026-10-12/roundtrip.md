# Claude engineering frontier review — roundtrip

Advisory review, 2026-10-12. Model: claude-opus-5-5; session: 177210f5-0a62-4531-b071-a0d0d329fec5. Public issue-body packet only; no code/runtime inspection or implementation.

Steward limitations: Scope findings only: #189's accepted plan and #109/#191 implementations were outside the packet. Verify those retained authorities before adopting any proposed amendment; do not infer a real Resolve capability or accepted-code defect from missing issue-body wording. Proposed synthesis-before-decision would need an explicit privacy/cost authorization and is not adopted here.

## Retained Claude response (unverified recommendations)

# Roundtrip review: R16 v2 authoring → package → injected Resolve → edits → revision → fresh rebuild

**Basis.** I reviewed only the supplied bodies of #177, #178, #190, #192, #145 and #189. I did not inspect code, the #189 plan text, or the bodies of #109, #171–#174, #180 or #191. Per the lane constraints, I ran no tools and wrote no files. Every finding is an **issue-scope gap or contradiction**, not a proven code defect.

**Check this first.** #145 says the "#177/#178 prerequisite refinements in #189 remain steward proposals; accepting this amendment does not imply they are implemented." The live #177 and #178 bodies contain only a "Selected execution route" appendix. The #189 plan may already answer F1–F3. The cheapest first step is to diff the plan's proposed #177/#178 refinements against the live bodies.

---

## Findings

### F1: #178's picture-render measurements have no render owner
**Severity:** High. **Proof impact:** blocks the headless proof via #145→#178. **Classification:** Missing.

**Evidence**
- #178's acceptance criteria require:
  - "Target cadence/frame count exact apart from bounded container-tick probe error"
  - "decoded duration within one target frame"
  - judder/quality inspection
  - a "bound render" proving root/child/overlay behaviour
- #178 also says "A render without native job/settings binding is insufficient."
- #178's selected port is #190. #190's render binding is explicitly a "proof-only local PCM … whole-programme WAV … not #71's production MP4/Drive service."
- #178 excludes a "general render service."

**Failure scenario**
- At #178 claim, map each acceptance measurement to its bound evidence producer.
- Three measurements have no producer with job/settings/output binding: container-tick cadence, decoded-frame duration, and render-based overlay independence.
- Either #178 cannot close, so #145 stays blocked, or an implementer adds an unbound picture render or reaches into #71. Either path violates #190's stop rule.

**Minimal action:** the steward picks one.
- **(a)** Amend #190's render criterion to "proof-only local picture + PCM render under one job/settings/output binding," still excluding MP4, Drive and scheduling.
- **(b)** Split #178's acceptance into two parts:
  - the PCM/readback/refusal/recovery subset that #145 actually consumes, which stays on #145's path;
  - a picture-render subset with a named owner, gating #160 rather than #145.
- Option (b) is the smaller change for the headless proof.
- Whether the injected native object can render picture locally is unverified.

---

### F2: #177's package validation has no admitted kind for non-P5 R16 preparation attestations
**Severity:** High. **Proof impact:** blocks the headless proof. **Classification:** Partial.

**Evidence**
- #177's acceptance binds "prepared source/derived hashes," and its rationale says "P5 supplies verified prepared bytes."
- #177 excludes changing #148.
- #190 must "consume only hash-bound R16 private reuse/PNG-still preparation attestations … never claim generic P5 created them," via "accepted #177 package verification."
- If #177 needs amendment, #190 must "stop for explicit ownership and change-note approval."

**Failure scenario**
- #177 closes with a receipt union that recognises only P5-produced receipts.
- #190 then has two options, both bad:
  - refuse the R16 package and stop for a change note after #177 is already Done; or
  - wrap the #148 attestations as P5 receipts, which is exactly the misattribution #190 forbids.
- #177's own synthetic tests cannot detect either outcome.

**Minimal action:** add one acceptance criterion to #177 before Ready.
- The v2 receipt/mapping union carries an explicit producer discriminant: P5-generated versus externally attested reuse or still.
- Both kinds are hash-bound to bytes, probe and source revision, and checked by the same strict path.
- Negative tests:
  - attestation hash matches the record but file bytes changed → refuse;
  - reuse attestation whose probed rate is 24/1, or an unqualified "23.976" → refuse;
  - P5-kind receipt presented for an asset declared as reuse → refuse;
  - attestation bound to a superseded #148 revision → refuse;
  - PNG-still attestation carrying a frame rate → stated behaviour (refuse or ignore, but defined).

---

### F3: The per-event ownership carrier is never checked across real save/reopen or a native trim
**Severity:** High. **Proof impact:** blocks the proof, but would only surface at #145 Stage B. **Classification:** Partial.

**Evidence**
- #192 must "map B1 v2 observation identities to manifest slot/payload/standalone block ownership."
- #192 must also distinguish B (a "linked source end-trim") from D (a "picture-only trim").
- #177 tests "event metadata" only through a fake readback.
- #178's native readback proves "timing/settings and source/derivative identity," which is media identity, not event-to-slot ownership.
- #190 retains "complete native identity" only in fakes.

**Failure scenarios**
1. **Carrier lost in real Resolve.** Whatever #109 writes to identify each event survives in fakes but not after real save/close/reopen, or not after a native roll/trim.
   - Every prerequisite closes green.
   - At #145 Stage B, A, B and C all refuse as unknown ownership.
   - #145 states that "refusal of every case cannot supply success," so the proof fails late.
2. **Linked audio disagrees.** B's linked audio item lacks a carrier, or reports a 24-frame end delta (48 048 samples at 48 kHz) against the video's 25. B1 must refuse rather than classify it as B or D.
3. **No-policy event.** A picture trim on a No-policy event (no source audio emitted, per #177) looks like a "picture-only trim." It cannot be classified correctly unless the classifier reads the manifest's audio policy.

**Minimal action**
- Add to #178's native readback criterion: every event's ownership carrier, as written by accepted #109, is re-read and matched after save/close/reopen. This includes linked Quiet/Full source-audio items and PNG/default stills.
- Add to #190's fake tests:
  - native ID changes across an edit but the carrier is intact → map;
  - carrier duplicated by blade or copy → refuse;
  - carrier missing → refuse;
  - linked A/V end deltas differ → refuse;
  - a D fixture on a No-policy event, with classification keyed to the manifest audio policy.
- Steward call: whether #178 may observe carrier persistence after one operator trim on its disposable target without breaching its "inbound reconciliation" exclusion.

---

### F4: Native-to-rational clock normalization and programme sample rate are not pinned
**Severity:** Medium. **Proof impact:** blocks case C. **Classification:** Partial.

**Evidence**
- #145 fixes frame-exact invariants at 24000/1001:
  - A: [456,592) → [569,592)
  - B: −25 frames → 1082
  - C: lift [121,127)
- #177 refuses unqualified fractional rates.
- #190 retains "rational timing."
- #178 bounds derived PCM boundaries to "one output sample."
- No issue states any of the following:
  - how the native timeline start offset is handled;
  - whether native end frames are inclusive;
  - whether readback is frame index or NDF timecode;
  - the programme render sample rate.

**Arithmetic**
- At 48 kHz, one 24000/1001 frame is exactly 2002 samples:
  - C's lift is samples [242 242, 254 254);
  - B's trim is 50 050 samples;
  - 1082 frames is 2 166 164 samples.
- At 44.1 kHz, one frame is 1839.3375 samples. Boundaries are non-integral, so "within one sample" needs a declared rounding rule.

**Failure scenarios**
1. **Convention mismatch.** The fakes and B1 share a zero-offset, half-open convention, but real readback uses a start offset or an inclusive end.
   - A normalizes to [570,593).
   - Best case, it is refused as stale ownership. Worst case, it becomes a plausible off-by-one proposal that the Producer accepts.
2. **Truncated sample boundary.** C's acoustic cut is derived from a 44.1 kHz render with truncation.
   - It lands one sample early and passes "within one sample."
   - It may still clip the onset of retained neighbour token 12.

**Minimal action**
- #190's raw observation schema records:
  - rate as an integer pair;
  - timeline start offset;
  - native end convention;
  - normalized half-open frames under a versioned normalization function.
- Fakes include a nonzero-start, inclusive-end variant.
- #145 Stage A (and #178) require zero-residual equality between normalized readback and manifest frame integers for every event before any Stage B edit. This doubles as empirical calibration of the convention.
- #190/#191 pin the programme PCM rate and the frame-to-sample rounding rule.

---

### F5: Decision/synthesis ordering and per-case observation chaining can lose decisions or self-refuse
**Severity:** Medium. **Proof impact:** blocks Stage B/C completion. **Classification:** Partial.

**Evidence**
- #192: "hash-bound accept/reject decisions create one new validator-passing v2 revision."
- #192 consumes the "B3 … omission/replacement handoff."
- #145: C is "lifted without ripple, followed by actual whole-row replacement speech" with "fresh timings."
- #145: A, B and C are "individually captured."
- #192 refuses "duplicate/unexplained delta."
- #192 rebuilds into a "fresh target rather than changing the edited one."

**Gaps**
1. **Synthesis order is unstated.**
   - If synthesis follows the text decision, the narration binding is stale at decision time, so a validator-passing revision cannot exist yet.
   - If synthesis precedes the decision, the decision must bind the replacement audio hash.
2. **Observation chaining is unstated.** If each case is diffed against the pristine baseline, B's after-state still contains A. B is then refused as an "unexplained delta" even though it is a valid positive.
3. **Save state of after-observations is unstated.** A live read taken before saving cannot be re-observed later from the retained edited target.

**Failure scenario**
- The Producer accepts A, B and C, then synthesis is refused.
- #192 correctly emits no revision.
- With no persisted decision record, a retry means re-deciding and possibly re-editing.
- Alternatively, the decision ends up bound to a stale proposal hash.

**Minimal action**
- **#192:** add a persisted decision ledger containing:
  - base revision, package and target identity;
  - per-case before/after observation hashes, where case *k*'s "before" equals case *k−1*'s "after";
  - proposal hash, decision, and replacement narration hash or "pending."
- **#192:** materialize the revision only when every accepted proposal's assets verify.
- **#192:** state the synthesis order. I recommend synthesizing the proposed row before the decision.
- **#145:**
  - capture each after-observation post-save, with adjacent consistent reads;
  - run D last;
  - define "intact" as re-observation hash equality with no adapter-issued save;
  - define "fresh target" as a new project, consistent with #178's "never overwrite an existing project."

---

## Accepted invariants (do not relitigate)
- **#189 plan:** accepted at `094b1ca` (`sha256:7fc7f361…`), with CN-189-A/B approved.
- **#109:** injected delivery selected and Closed/Done. CN-4 remains unapproved.
- **Frozen v1:** #144/#145 v1/25-fps evidence, fixtures and goldens stay frozen. No v2→v1 cast; #148 is not reopened.
- **Native safety:** refusal before native mutation; immutable attestation; unique fresh targets; partial-target retention; read-only uncertain recovery; no in-place rebuild.
- **Case definitions:**
  - A: [456,592) → [569,592), with the previous OC extended to 569.
  - B: 25-frame linked trim → 1082.
  - C: token 11 only, lift [121,127), using the actual new-row duration.
  - D: refuses without any revision or rebuild effect.
- **Evidence rules:** fakes never claim real success; all three positives are required.
- **Dependency direction:** #178 is not a dependency of #190 (no cycle).

## Dependency / interface map
```
#148 R16 rev3 + private reuse/still attestations ─┐
#171 → #172 → #173 compileTimelineV2/resolveMediaRequirementsV2
#174 P5 product gate ─────────────────────────────┤
#177 v2 package verify ........ [I1 attestation kind F2][I2 carrier spec F3]
  → #190 B1 preflight → #109 injected delivery (unique target, effect ledger)
      → raw observations [I3 clock normalization F4] → PCM port [I4 rate F4]
  → #178 real qualification ..... [picture-render owner F1]
#145 Stage A → operator edits A,B,C,D → #190 observations [I5 chain F5]
  → #192 proposals A/B/D + #191 C evidence/replacement → decision ledger [I6 F5]
  → revision + comparison → #173/#177/#190/#109 new project → save/reopen
  → #145 Stage C
```

## Post-launch robustness (not proof blockers)
- **Trims on P5 derivatives.** Mapping trims on rate-converted derivatives back to original source in/out points is unowned for production. R16 is reuse-only; #101–#104 own production inbound.
- **Other audio rates.** 44.1 kHz or mixed programme audio needs more than the rounding rule in F4.
- **Edit concurrency.** Multiple or concurrent edits per case, and native project-database backup or recovery.
- **Production picture render.** Remains with #71.

## What remains unverified
- **#189 plan:** its text, and its proposed #177/#178 refinements.
- **#109 interface:** the identity carrier it writes and the native field it uses.
- **Unsupplied issue bodies:** #191, #174, #171–#173, #180.
- **Resolve behaviour** (no API facts assumed):
  - item identity across a trim or roll;
  - start-offset and end-inclusivity conventions;
  - picture and PCM render capability through the injected object.
- **Specimen:** R16's narration and source sample rates.
- **#190 scope:** whether its "capture" includes picture capture.
