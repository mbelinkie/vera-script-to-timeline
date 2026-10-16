# Checkpoint 7 review — Producer row-audio policy vs. corrected plan

Read-only review complete (`producer-row-audio-policy.md`, the current plan, and spec §§6.5, 6.15, 8.3, and Slice 7.5 in `docs/Script-to-Timeline Product Spec - Fable Rev2.md`). This is advisory only.

## Plain-language summary

The Producer's rule — "a row's VO is one disposable clip; any wording change burns the whole clip and gets a fresh one, never a cut-and-paste of the old recording" — is not a new invention, it's the written spec's existing per-block replacement model (§8.3) being applied explicitly to #144's omission-rebuild step. The plan has already been corrected to match: I searched the whole document for every remaining mention of "splice," "fragment," "lossless," and "old duration," and every single hit left is a negation ("withdraws," "do not," "not permission to," "no fragment splicing") — there is no surviving affirmative assumption that contradicts whole-row regeneration. The one real open question is narrower than the plan text: what happens if "the row" already has an *approved recorded* take (post-shoot), not just temporary synthetic audio — and that question is already honestly flagged as deferred rather than answered by assumption.

## 1. Remaining splice/old-timing/old-frame assumptions

**None found.** I grepped the entire plan for `splice|lossless|frame-aligned|fragment|old.*duration` and checked every hit:
- Lines 217-225, 231-234, 293-303, 318: all are explicit disclaimers of the withdrawn route ("Do not concatenate retained fragments, reuse their word timings, subtract the old cut duration from later marks," "not an old-audio splice segment map," "no fragment splicing or stale timing reuse").
- The one remaining "old geometry must match" check is in the **visual-only** move/trim module (`issue-144-semantics.ts`, reviewed checkpoint 6), which never touches narration text and is correctly scoped: for a visual-only edit, old-frame-equivalence *is* the right invariant, since nothing about timing should have changed. The narration-rebuild path explicitly says the opposite ("do not require frame equality with the old edited timeline," plan line 299). These are two different scenarios each using the rule that's correct for it — not a contradiction, but worth saying explicitly since skimming both documents side by side could look inconsistent.

**Settled**, not unresolved.

## 2. Does the corrected approach safely recompile against new pacing/duration/coverage?

Yes, structurally, for the reason the plan itself gives: visual anchors are stored as **token-ID ranges**, not frame numbers. Recompiling through the unchanged compiler against a `NarrationDependency` with brand-new timing marks automatically repositions every anchored visual correctly — that's a property of the existing architecture, not new logic #144 has to invent. The plan already requires the two things §6.15 cares about most:
- "Validate source handles, coverage and supported composition, refusing uncertainty" (line 300) — directly answers §6.15's `fixed_source_excerpt` concern ("report a coverage gap/overlap if the new narration no longer fits") by refusing rather than inventing a fix.
- "Recompile every text-anchored cut in the row and downstream positions affected by duration" (line 225) — matches §6.15's "text-anchored events move with the corresponding recorded words."

#144 only ever implements the one bounded linked-case, not §6.15's full five-policy table (`follow_text_anchors`/`stretchable_still_or_graphic`/`fixed_source_excerpt`/`clip_led`/`protected_manual_timing`) — that's correct given scope, not a gap, since that table belongs to Phase 7's general recorded-conform, not this proof.

**Settled at the policy level; the specific refusal behavior (what exactly happens when a shorter re-recording leaves a `fixed_source_excerpt` visual without coverage) is unverified because the regeneration handoff doesn't exist in code yet** — worth a concrete test once it's built, not a current defect.

## 3. Smallest compatible generation/preparation handoff

Recommend following the pattern already used twice in this codebase rather than inventing a new one: an issue-owned, **injected** generation adapter behind the same shape as `NativeStages`' `adapter_factory`/`inspector` injection (checkpoint 5) and `PreparedBuild`'s verify-only speech stage (checkpoint 4) — never importing `narration/service.py`/`polly.py`, labeled `synthetic_injected` for #144's own tests. For #145, the real route should go through the spec's **already-documented** `SpeechSynthesisProvider` contract (§8.3: "accepts normalized block text, voice/profile settings, pronunciations, and requested timing output, and returns audio plus timing/provenance metadata") rather than a bespoke #144-only generation path — same separation principle as #144's fake Studio adapter vs. #145's real `run_studio_assembly`.

One principle worth stating explicitly, carried over from the audio-gate review in checkpoint 4: the injected test adapter's fake output must be a genuine function of the *new row text* (e.g., deterministically derived from it), not a pre-baked fixture file picked because its hash happens to match an expected value — otherwise the "integrated regeneration" test is a replay, not a real exercise of the handoff. This is exactly the "manually rewritten input or merely relabeled old recording" failure mode the prompt is asking me to rule out.

## 4. Other product mismatches for the Producer

- **Visual-only vs. VO edits:** already correctly scoped in `producer-row-audio-policy.md:41-43`, and matches what's actually built — `issue-144-semantics.ts` never mutates narration text/tokens for a visual move/trim. No correction needed.
- **Lock beginning at export, not audio import:** §6.5 describes the prompter export freezing a revision-bound beat-map sidecar and explicitly designing for *reconstructability* after later script changes ("a shoot made from a pre-Phase-6 prompter export is not stranded") — it does **not** describe any warning/lock UI. The Producer's checkpoint is a genuinely new UX behavior layered on top of an existing export property, not something already specified. The policy doc itself correctly defers "the left-side lock's exact controls" to the owning authoring/conform design (line 61) — flag this to the Producer as *settled direction, unspecified mechanism*, and confirm it's frontend/authoring-workflow scope, not something #144's headless proof builds.
- **Retained unchanged recorded beats vs. whole-row reshoot — the one real tension worth surfacing plainly:** §8.3's "Locked audio" rule says once a human recording is attached, "a normal rebuild must not regenerate it." If "every row is one piece of temporary audio... any wording change... replaces the entire recording" is read to also cover rows that already carry an *approved recorded* take, it would directly contradict Locked Audio. The policy doc already recognizes this and defers it ("whether a changed row must replace every unchanged recorded beat in a later conform remains a separate product decision," line 51) — I'd recommend the Producer confirm explicitly, in one sentence, that whole-row regeneration applies to the pre-approval/temp-VO stage only, and that post-approval rows instead follow §6.15's staleness marking (stale + needs-recording, never silent replacement of the approved asset). That one-sentence confirmation would remove any ambiguity for whoever eventually builds Phase 7.
- **Failure behavior:** consistent. §8.3's "Synthesis failure creates audible and visible placeholders; the timeline is never silently compressed to hide a missing line" matches the plan's "[missing audio/timing] is a named readiness blocker, not permission to splice, invent marks, use paid services, or claim the positive omission proof complete" (lines 231-234) — same principle, correctly adapted to #144's no-synthesis proof context.

## 5. Hidden reduction of #144's named positive?

**None found.** The "Spoken omission" detection section (plan lines 186-213 — the W1 audio-residual/structural-excision gate work from checkpoints 3–4) is untouched by this correction; I confirmed by grep that none of the splice-withdrawal language appears anywhere near it. Detection answers "is Charlie already audibly absent from this existing rendered mix," which has nothing to do with how replacement audio is later generated. Only the **rebuild** step's audio-sourcing method changed (splice → whole-row regeneration), and that step was already "not yet implemented" in every prior checkpoint — so nothing already-achieved is being walked back; only a not-yet-built mechanism's design changed.

## Settled vs. unresolved — quick index

**Settled:** whole-row replacement is the unit (matches §8.3, not new); no splicing/fragment reuse/old-duration-subtraction anywhere in the plan; visual-only edits are unaffected; detection bar for the named positive is unchanged; failure must stay visible, never silently hidden.

**Unresolved, correctly deferred (not #144's job to answer):** exact lock/warning UI mechanics at prompter export; whether whole-row replacement extends to rows with an already-approved recorded take, or only to pre-approval temp VO; prompter changed-rows-since-last-export selection semantics.

This is advisory review only; it does not change Producer policy or constitute acceptance.
