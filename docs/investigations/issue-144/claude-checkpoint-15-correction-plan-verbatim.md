# Checkpoint15 correction plan response — verbatim

## Same read-only session;6turns; exit0/no denials

````text
## Verdict: approve with required changes

The plan is the right shape and stays within scope. It does not weaken the intent, immutability, staleness, whole-row or synthetic/real rules. As written, though, it leaves P2-2 unresolved, and three of its seams have holes. I traced each one below; none needs a broad recovery framework.

## Blocker 1: Documentation alone can't fix P2-2, because a failed link check permanently blocks promotion

The plan says existing refusal tests cover this. They don't: no test covers the "isolated proof link setup is unverified" refusal or a retry after it.

**What happens in the code:**
- `_publish_baseline` writes `baseline-validation/<snapshot_id>/inputs.json` as an immutable file *before* it runs the semantic check and the link check (`roundtrip_proof.py:481-486`, then `:493-511`). The file contains the observation that was just captured.
- `bind-baseline` and `promote` are what create the capture request (`:530-531`, `:808-809`). So an operator who follows the order the plan intends can easily capture the rebuilt target before linking it.
- That first attempt records the unlinked observation, then refuses.
- After the operator links the pairs, the second attempt captures a different observation. `publish_immutable_output` then raises "immutable stage receipt has different bytes".
- From then on that snapshot can never be promoted. The same trap exists for the original `bind-baseline`. The demo never hits it only because its capture callback links automatically.

**Smallest fix:** key the validation file by its content, e.g. `baseline-validation/<snapshot>/<digest(inputs)>/inputs.json`, the same way `proposal-inputs/<digest>` already works. Alternatively, run the link check before any immutable write.

**Required regression test:** rebuild, then promote with the new target unlinked (refused). Then link through WI `perform`, take a fresh capture, and promote (succeeds). Assert the old capture attempt and evidence still exist, the pointer advanced exactly once, and the provider and target counts are unchanged.

## Blocker 2: The generation-call intent has to be scoped to the request, not the decision

Section 2 puts `generation-call-intent.json` in each decision's directory, but the synthesis cache is shared across the whole proof root.

**What happens in the code:**
- A second decision key for the same report can be produced from byte-different JSON. The code doesn't prevent this; the plan only forbids it in prose.
- That second key has no call intent of its own. So when the cached synthesis is missing, `process_block` calls the provider again for the same request identity.
- That reopens the "uncertain call → second provider attempt" hole the plan is trying to close (`roundtrip_generation.py:264-275`, `roundtrip_narration.py:127`).

**Fix:** store the intent at a proof-root path keyed by the service request hash, e.g. `generation-calls/<requestHash>/intent.json`. The per-decision `generation.json` should bind to it. Any decision whose request hash has an existing intent but no synthesis cache must refuse.

**Constraints for the rest of section 2:**
- Publish the intent through the existing hook immediately before `process_block`, after the validator and row checks, while holding the proof lock.
- On replay (`finalize(publish=False)`), the hook may only confirm the intent already exists. It must never create one.
- `cache_replay` must run whenever the intent exists. Change the current `existing_input or not publish` condition to `intent_exists or not publish`.

**Tests to add on top of the plan's:**
- A second, byte-different accepted decision for the same report, with the synthesis cache removed after the first call: refused, provider still called once.
- A normalization failure after synthesis is cached: the retry succeeds without calling the provider.

## Required constraints for section 1 (P2-1)

**1. Exit codes.** The driver returns 2 only for `waiting`, `needs_action`, `failed` and `refused` (`roundtrip_driver.py:259-263`, and the same in `roundtrip_proof.py:851-855`). A new `recovery_blocked` status would exit 0, i.e. look like success. Add it to the exit-2 set in both CLIs, and test the exit code.

**2. Resume must hand off to the existing actions, not reimplement their gates.**
- `resume-build` should, under the lock: require the boundary, classify the job state (read-only), call `store.resume`, then immediately run the existing `build.run(adapter=…)` path.
- `resume-rebuild --decision-key` should do the same and then call the existing `_rebuild(key)`. That keeps the decision rederivation, the pointer staleness check, the fresh old-target capture and the `verify_preview` preflight in one place.
- The reason: if resume only flipped the job to queued, any later action that calls `_ready()` would run the queued job without an adapter (`roundtrip_proof.py:197-200` calls `build.run()`). The native stage would raise `NeedsAction` again and the job would be back to waiting. That's harmless but confusing.

**3. Classification must be read-only and strict.**
- Use the store's status and the files on disk. Don't call `run()` or `run_one()` to find out the state.
- **Resume is allowed when:**
  - no `native-intent.json` exists at all; or
  - the intent exactly matches `_intent(...)` and `native-result.json` shows status `verified`, `verified: true` and no discrepancies, so the existing `execute` path skips creation and only re-inspects.
- **`recovery_blocked` (read-only) when:**
  - the intent file exists in any form without a matching verified result. An empty or unparsable intent file counts as present, because a crash can leave it that way after `O_EXCL` creation;
  - a foreign intent;
  - any non-verified result (`stopped_safely`, `mutation_failed`, `verification_failed`);
  - the last job event is `integrity_failed`.
- `build` and `rebuild` should also report `recovery_blocked` in these cases instead of plain `waiting`.

**4. Treating `stopped_safely` as terminal is enough for #144,** since the real lane is closed and no new native action is added. The runbook must state the recovery path correctly for each case:
- **Baseline build:** a fresh authorized run means editing the build IDs in `compiler-dependencies.json` before any pointer exists. That gives a new snapshot, run directory and job in the same proof root, and keeps the old run.
- **Rebuild:** the build ID comes deterministically from `finalizeOmission`'s seed and the operator can't change it. Re-deciding gives the same project name. The only fresh path is a new proof run from the original inputs, which repeats generation. Name that as a #145 cost/readiness item.
- **Optional for #145, not needed for #144:** a no-effect live preflight before intent reservation, using the accepted `run_studio_assembly(action="preflight")`. A failed preflight would surface as `NeedsAction` with no intent written, so the job stays resumable. It's a live read and needs qualifying, so don't add it in #144.

**5. The preflight action must check the bounded profile, or say it doesn't.** The plan says #148 uses this exact command, but compiling and checking bytes doesn't check #148's main readiness criteria. Either add pure local checks against the compiled manifest, or have the receipt list them as `unchecked`:
- 25 fps and a zero start frame;
- `durationFrames` ≤ 1562 (the 3M-sample cap);
- only ready audio/video sources (the WI reader refuses stills and placeholders);
- every audio source mono 48 kHz PCM16/24, frame-aligned and not aliased, at most 8;
- narration in PCM24;
- the selected row with at most 64 tokens;
- exactly one authored muted full-row companion plus two distinct ready `use_source` visuals.

  The smallest way is to factor the check out of `OmissionProof._sources` and its row-selection checks into a function that doesn't need a baseline. Preflight must still create no job, load no boundary and generate nothing.

**6. Resume tests.** "Waiting at native stage, resume with boundary, complete" through the actual `main()`. Plus the blocked cases with zero creation calls and no files deleted: an existing intent with no result, a `stopped_safely` result, and an empty intent file.

## Section 3 (P2-2)

Once Blocker 1 is fixed, the documentation part is enough. The runbook must give the exact order:
1. Run `promote`; it returns `needs_action` with the capture request path.
2. Read the new target with `read_native` and link each pair through `perform`. The action requests copy the 14 bound fields from that pending request; `identityPath` must point under `decisions/<key>/build/runs/...`.
3. Run `wi.capture`.
4. Run `promote` again.

In the demo, do these new-target links as explicit numbered steps before the promote capture, not hidden inside the capture callback.

## Section 4 (P2-3)

Settling this with documentation is enough for #144. The real lane is hard-closed in seven places, and #144's acceptance is synthetic. A synthetic host bridge would only add a half-qualified authority. Conditions:

**Correct the existing overclaims:**
- the runbook's section 2 claim that "current full-program stereo queue/inspection use their actual implementations" (around lines 46-52);
- `seam-matrix.md:44`;
- the demo docstring.

They should say the WI render path is executed but not used by the host's verdict, and that calibration bypasses WI.

**The contract should list, with the code location that enforces each one:**
- the exact file names in the evidence directory;
- that the supplier's output directory must be inside the proof root;
- the 32 MiB per-file and 8 MiB JSON limits;
- the field sets checked in `roundtrip_audio.py` and `roundtrip_omission.py`;
- source limits: 1–8 sources, ≤ 64 supports per source and ≥ 3 for the primary, ≤ 65 segments;
- the gain range [0.25, 1.5] and the residual thresholds;
- that the calibration and edited renders must have distinct job IDs;
- that calibration and profile files must be byte-identical between preparation and proposal.

**The #145 blocker** should say the bridge must bind the supplier receipt's job ID, settings and output hash to the WI `complete.json` for the same output path and target. The WI `before` observation must be the same raw capture used for the audio observation. The pristine calibration, the edited render and the rebuilt render all need qualifying.

## Adjacent triage: accepted, with limits

| Item | Constraint |
|---|---|
| Guard composition | Wrap the existing preflight and `verify_preview`; don't replace either one. |
| Pinning `studio_assembly.py` and `studio_spike.py` | Fine; this changes every snapshot ID, as expected. |
| Malformed capture responses | Add explicit dict/shape checks at the start of `_occurrence_identity` that raise `ProofBuildError`. Don't widen the `except` to `Exception`; real process or I/O faults must stay non-terminal. |
| 25 fps in the omission-only lane | Check it against the manifest in `OmissionProof.__init__`. |

Leave compare locking, byte-keyed decision identity and the legacy CLI as documented notes. Blocker 2 already removes the only concrete harm from byte-keyed identity.

## Disposition of each P2

- **P2-1: resolved once constraints 1–6 are applied.** Treating uncertain creation and `stopped_safely` as terminal is acceptable for #144.
- **P2-2: not resolved by the plan as written.** It needs Blocker 1's fix and its regression test.
- **P2-3: resolved by documentation alone,** provided the overclaims are corrected and the #145 blocker is stated exactly.

Everything above comes from reading the code. I ran nothing.
````
