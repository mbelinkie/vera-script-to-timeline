# Checkpoint 10 plan review — bounded non-transcript omission evidence

Read-only review complete (`checkpoint-10-audio-evidence-plan.md`, checkpoint-01/04 dispositions, `docs/investigations/issue-149/workflow-reruns/w1-result.md`, `docs/investigations/issue-141/final-findings.md`, and the retained `measure-retained-w1.py`/measurements JSON already reviewed in checkpoints 3-4). This is pre-implementation plan review — no `roundtrip_audio.py` exists yet.

## Grounding check — the plan's specific numbers and cautions are not invented

I cross-checked the plan's concrete claims against the actual retained evidence rather than taking them at face value:
- The exact geometry it names — "A1 [0,99), [150,399) at records [0,99), [100,349)" — matches `w1-result.md`'s own stated native values precisely ("Raw native record Start/End values are 0/99 and 100/349; raw source Start/End values are 0/99 and 150/399"). Not invented.
- The target support `[216000, 234932)` samples falls entirely inside the omitted source gap `[99,150)` frames (`99×1920=190080` to `150×1920=288000`) — the omission geometry is internally consistent with the actual fixture, confirmed by arithmetic, not just asserted.
- "The historical collector did NOT attest arbitrary Solo/bus/sends/FX state" is not a generic hedge — I found the specific grounding for it: `final-findings.md:11,24` documents that W2's track Mute/Solo were set manually (not through a verified automated setter) and that "WI readback mute:true did not silence A2; the internal cause remains unknown." That is a *documented case of mute/solo readback disagreeing with actual audible behavior* in this exact codebase's own history. The plan's refusal to trust any unverified control-state readback isn't caution for its own sake — it's responding to a real, already-observed failure mode. Worth citing back to the plan explicitly, since it upgrades "unknown controls/effects refuse" from prudent to evidence-based.

## Is this an honest bounded building block?

Yes, on every dimension I checked:
- It correctly keeps the numeric RMS/20ms limits as a *secondary consistency check*, never a classifier — consistent with checkpoint 4/5's settled disposition, and it explicitly plans the near-boundary probes (opposite-channel, unchanged-neighbor, gains-out-of-range, quiet/tiny residual) that checkpoint 4 showed were previously missing.
- It correctly keeps synthetic-injected test evidence separate from #145's real qualification, consistent with checkpoint 6's confirmation of real `GetUniqueId` evidence being scoped to #141 only, and checkpoint 8's "no cryptographic live-readback provenance" principle.
- It correctly scopes the A3 fixture bed to math-only attribution, not reopening the music-spanning-rows product question I raised in checkpoint 7 (and which I separately confirmed has zero compiler support today).
- It correctly treats the `base.mov`/`a1_alpha.wav` equivalence as requiring hash-bound full-decode comparison, which is exactly what `measure-retained-w1.py` already enforces — carrying the check forward rather than silently dropping it.

## The one indispensable addition

**The plan needs an explicit render-receipt liveness caution, parallel to the one already in the main plan for the WI capture/inspector.** `issue-144-roundtrip-harness.md:40-45` already states, for the capture/inspector seam: "Nonce/receipt/hash consistency alone cannot distinguish a live capture from a package echo; no cryptographic live-readback provenance is claimed." The checkpoint-10 plan's "render receipt binding its exact target, observations, settings, extent, job and byte hashes" is the *same class of file-based claim* for a *different* native action — the render job. Nothing in checkpoint 10's plan says this receipt can't be fabricated the same way: a file that claims a specific job/settings/extent and matches its own declared byte hashes, without ever having come from a genuine Resolve render job. This is the same structural limitation I found in checkpoint 8, just not yet named for this specific seam.

**Minimal fix:** add one sentence to the plan, mirroring the existing one exactly — the render receipt's job/settings/extent/hash fields are not cryptographic proof of a genuine render; #145's real render-job polling and receipt construction need the same independent-review gate already named for the capture adapter and initial inspector. This is a documentation addition, not a code blocker for this segment — the verifier should accept whatever receipt shape it's given and trust the *caller* to have obtained it honestly, exactly as the capture protocol already does.

## Smaller precision notes (not blockers)

- The "every retained token's complete support must remain exactly once and in order" requirement needs the verifier to consume *every* word's sample-support range from the existing `media/manifest.json` fixture, not just the omitted word's — the fixture already carries this (confirmed: `measure-retained-w1.py` cherry-picks only `"charlie"` from a `words` list that evidently contains all of them), so this is an implementation-completeness note, not a missing capability.
- "Known fixed per-route gains" (singular, calibrated once) is consistent with — not a narrowing of — the earlier "bounded plausible range" language: it's the correct description for one closed, single-source profile, where gains are fit once from the unchanged reference and reused, exactly as `measure-retained-w1.py` already does. No regression.

## Smallest API/profile/test set that still holds the boundary

- **API:** one function (e.g. `verify_omission_evidence(profile, baseline_observation, observationA, observationB, render_receipt) -> EvidenceReport`), reusing hash/WAV/decode helpers extracted from the measurement script under the plan's own stated discipline (preserve the historical script at its original commit; state new code's own hashes; never imply old measurements used the new helper).
- **Profile (frozen, hash-bound):** frame rate 25/1, sample rate 48000, speed 100%, complete route inventory with declared per-word support ranges, target token/support range, calibrated per-route gains, render extent, and the consistency thresholds explicitly labeled non-classifier.
- **Test set:** the plan's own list is already close to minimal and complete. One addition: a render-receipt-fabrication test — a receipt whose claimed job/settings/extent don't match the actual byte-verified PCM — to exercise the one thing a file-based receipt protocol *can* check (internal consistency) even though it can't prove liveness, making the liveness caution concrete at the test level rather than only in prose.

## Verdict

No all-refused or lower-coverage substitute risk found. With the render-receipt liveness sentence added, this plan holds the same honest boundary already established across checkpoints 4, 5, 6, and 8, applied correctly to a new domain. Static advisory review only — not test execution or native acceptance.
