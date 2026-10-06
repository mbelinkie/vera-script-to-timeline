# Checkpoint15 completed correction responses — verbatim

## Source187c420;26turns;389.21s; no tests run

````text
## Verdict: the source logic passes, but the package isn't ready for full validation or handoff yet

I found no safety or logic defects in the corrected source. Two small fixes are needed first:

1. **An unchanged issue-owned test will fail.** It's a test expectation, not a product bug.
2. **The new audio contract misstates one implemented threshold.** It's a one-line doc fix.

Neither needs a change to product code. All three original P2s are resolved once these are applied.

## Required before full validation and handoff

### R1. `test_failed_rebuild_retains_authoritative_baseline_and_old_inputs` will fail
*High confidence from tracing the code; I didn't run it.*

- **Where:** `tests/test_issue144_proof_session.py:264-278`, which this package doesn't touch, still expects `"waiting"`.
- **What happens now:**
  - `fail_rebuild` makes the second studio raise inside `create_project` (`test_issue144_proof_session.py:134`, `test_issue144_native_build.py:75-76`).
  - Accepted assembly turns that into a `mutation_failed` result. `_result` then raises `UncertainResult`, so the job waits.
  - The new post-run check (`roundtrip_build.py:700-707`) then returns `recovery_blocked`, and `_rebuild` passes that status straight through (`roundtrip_proof.py:781-782`).
- **Why it hasn't shown up:** none of the runs reported so far include this file (the 30-pass native/prepared/driver run, focus run 2, capture).
- **Fix:** assert `status == "recovery_blocked"` and that the inner job status is `waiting`. Keep the existing promote-refusal, pointer and `create_count` assertions. Then include `test_issue144_proof_session.py` in the focused rerun.

### R2. The audio contract states the wrong residual metric
- **Where:** `audio-evidence-contract.md:65-66` says "maximum absolute residual≤0.006".
- **What the code checks:** the maximum RMS over a sliding 20 ms (960-sample) window, `maximumSliding20msResidualRms` (`roundtrip_audio.py:332-346`). Individual samples can exceed 0.006 and still pass.
- **Also missing:** the pristine calibration must itself pass both thresholds (`roundtrip_audio.py:679-681`), and the doc doesn't say so.
- **Fix:** change the wording to match the code. Don't tighten the code; the code is what has been reviewed and tested.

## Nonblocking notes

- **P3, runbook mechanism wording** (`operator-runbook.md:343-344`). It says changing the decision key "cannot authorize a fresh uncertain target." That holds for the provider, because the shared request intent blocks it. It is not enforced for native targets:
  - A byte-different decision gets a new `decisions/<K2>/build/runs/<same snapshot>/` with no intent file, so `rebuild` would try to create a target.
  - The real protection is that the project name is the same, so accepted assembly's `check_project_name_available` stops it (as `stopped_safely`, which then becomes `recovery_blocked`). That's an external check #145 has to qualify.
  - Either say that, or add a small guard in `_rebuild` that refuses when any other decision has a `native-intent.json` for the same `snapshot_id`.
- **P3, narrow exception list in classification.** `recovery_reason` only catches `ProofBuildError` and `UncertainResult` (`roundtrip_native.py:299`). A WI inspector `RuntimeError` or an `OSError` escapes and is reported as `refused` or `fault` instead of `recovery_blocked`. That's still safe: nothing executes and nothing is written.
- **P3, misleading label.** `recovery_blocked` is also returned for complete jobs, e.g. replaying `build` with a boundary after the three edits, or `resume-*` without a boundary. Before the change this was `refused`. Both exit 2.
- **P3, pre-existing.** Job statuses `queued` and `running` still exit 0 in both CLIs. This mainly matters within the 300 s lease after a crash.
- **Note on deleted evidence.** If both `native-intent.json` and the result are deleted before the native stage completes, classification would allow creation again. That needs deliberate deletion of immutable evidence, so it's out of scope; the case where the stage had completed is guarded and tested.
- **Note on observation hashes.** The contract says observation hashes use the canonical receipt encoding, but `render.observationHash` hashes the literal bytes of `observation-a.json`. Advise suppliers to write the canonical encoding.

## Plan constraints checked against the code

**1. Preflight.**
- It freezes the inputs, runs `_verify_speech` and the actual `_compile`, and writes `preflight.json` with level `local_prepared`.
- It creates no job and the driver refuses boundary flags (`roundtrip_build.py:514-546`, `roundtrip_driver.py:248-251`).
- The receipt lists the full positive-readiness profile as unchecked.

**2. Resume and recovery classification.** All of the following hold:
- An integrity failure is checked first (`roundtrip_build.py:610-618`), before any custom callback.
- Classification is read-only, and complete jobs with no adapter skip it entirely, so `_ready` still works.
- Continuation is allowed only when no intent exists and no native stage is complete. Otherwise an exact matching intent plus a verified result must pass a fresh read-only inspection; creation is skipped because the intent exists.
- These all block: empty or foreign intent, result without intent, unverified or `stopped_safely` result, completed stage with missing records.
- `resume-*` needs the native boundary and calls `store.resume` and then `run_one` under the proof lock.
- `resume-rebuild` goes through `_rebuild`, so the decision, pointer, fresh-capture and composed preview gates all run before any continuation.
- Both CLIs map `recovery_blocked` to exit 2.

**3. Generation call intent.**
- The intent lives at `generation-calls/<requestHash>/intent.json` and binds the service identity. It's published by `before_process` after the validator and row checks and immediately before `process_block` (`roundtrip_generation.py:262-326`, `roundtrip_narration.py:129-131`).
- If an intent exists, the synthesis cache must exist too, for every decision key.
- Replays only confirm the intent; they never create one. The finalized receipt binds `callIntentHash`.
- The normalization-failure retry works because a failed asset gets a different `asset_id`, while the synthesis cache is reused (`service.py:279-319`).

**4. Linking (P2-2).**
- Validation inputs are now stored by content hash (`roundtrip_proof.py:495-502`).
- Capture no longer links anything. `link_pairs` is now an explicit step in the demo for both targets.
- The demo shows the premature unlinked promotion refused, its record kept, then explicit links, a fresh capture, a single CAS promotion and replay, with one provider request and two studios.

**5. Adjacent fixes.**
- The guard and preview preflight are composed, not replaced (`roundtrip_proof.py:770-779`).
- `studio_assembly.py` and `studio_spike.py` are now pinned.
- Malformed captures and malformed response JSON now produce a terminal `ProofBuildError`.
- The 25 fps check is enforced in `OmissionProof.__init__`.
- The PCM24 and marker wording is corrected.
- The real lane is still hard-closed: `NativeStages`, `OmissionProof`, service and narration gates are unchanged.

## Disposition of each P2

- **P2-1: resolved.** Fix R1 so the test suite matches the new behaviour.
- **P2-2: resolved** by content-addressed validation inputs, explicit links on both targets, and the demo regression.
- **P2-3: resolved** by the contract and the corrected overclaims, once R2 is fixed. The #145 bridge blocker is named exactly: job, settings, output path and bytes, the raw-before vs derived-audio observation hashes, and calibration plus edited plus rebuilt renders.

## Coverage

**Read in full or traced:**
- Current `roundtrip_proof`, `roundtrip_build`, `roundtrip_native`, `roundtrip_generation` and the `roundtrip_driver` changes.
- The `roundtrip_narration` hook and the `roundtrip_omission` 25 fps check.
- `build_jobs` `submit`, `status` and `resume`; `NarrationService` `_raw_result`, `_normalized` and `process_block`.
- The full correction diff: the demo, fixture, recovery, generation-recovery, capture and native test changes, plus the contract, runbook, seam matrix and plan.
- The unchanged tests that assert job statuses.

**Not inspected:** the unchanged `roundtrip_wi.py` and TypeScript (no diff), the test logs, and the parallel `claude-finished-review` files. I ran nothing.
````

## Source1b87f05;7turns;74.79s; final source approval conditional on tests

````text
## Verdict: the follow-up is approved, and no defect needs fixing before final validation

I confirm R1, R2 and the dispatch fix. With these applied, the code settles all three original P2s, conditional on the pending native/recovery/ProofSession run and final full validation passing. I ran nothing.

You're right about my miss. On `187c420`, the classification block only ran for a complete job when a native record still existed. With both records deleted, the reconcile loop reached `_result` and raised `UncertainResult` instead of returning `recovery_blocked`. I traced the helper but not its caller condition.

## R1: confirmed
`test_issue144_proof_session.py:271-277` now expects `recovery_blocked`, with the actual job inside `["job"]["job"]` still `waiting`. That nesting is right: `_rebuild` wraps the recovery result, which in turn wraps the store status. The promote refusal, the unchanged pointer and `create_count == 1` are all still asserted.

## R2: confirmed
`audio-evidence-contract.md:65-67` matches `_metrics` (`roundtrip_audio.py:332-346`):
- residual RMS over the whole programme ≤ 0.0004;
- the maximum RMS over any 960-sample (20 ms) window ≤ 0.006;
- both limits apply to each channel, for the pristine calibration and for the edited render;
- the doc says these are RMS limits, not peak-sample limits.

The runbook text at `:343-348` is now accurate. A byte-different decision gets its own local build root but the same deterministic project name. The protection is accepted assembly's name-collision check, which #145 must qualify; the shared request intent separately protects synthesis.

## Dispatch fix: confirmed
Checked at the caller, `roundtrip_build.py:607-696`:

- **Order.** The integrity-failed event, then `_verify_completed`, then the media, compiler and package checks all run before any custom callback (`:610-632`). The existing corrupt-stage test still refuses before the inspector runs.
- **When classification runs.** It now runs whenever the job is `waiting` or `failed`, on resume, or whenever any adapter is present (`:633`). Complete jobs read without an adapter (`_ready`, `_baseline`) still skip it.
- **The lost-intent-and-result case.** A complete job with both records deleted now hits "completed native stage lacks its intent/result" (`roundtrip_native.py:275-279`) and returns `recovery_blocked` before the reconcile loop.
- **No side effects.** When no intent exists, classification only reads job status. It never calls `_manifest` or the factory, so a fresh first build, a build whose core stages haven't run, and resume after a missing boundary all proceed normally.
- **When an intent exists.** Classification only reads: the package, the preflight guard and `verify_preview`, the JSON records, and the inspector. The `recovery-read-only` output path is never written.
- **Verified-result recovery.** It still passes and still skips creation, because the intent already exists.
- **Core-stage failures.** They classify to `None`, so plain `failed`/`waiting` comes back and the job can be resumed.
- **The waiting adapter path.** Without `resume`, it still returns `waiting`, matching `test_issue144_recovery.py:139`.
- **Other adapters.** A non-`NativeStages` adapter is blocked only when native records exist.

## Nonblocking notes (none are new defects)

- **Hash wording in the contract** (`:25-30`). `baseline.json` must be canonical bytes, because its literal hash is compared to `baselineHash`. `render.observationHash` is the hash of the literal bytes of `observation-a.json`. Telling suppliers to write canonical encoding makes these the same, and a supplier that doesn't is refused rather than wrongly accepted. One clarifying sentence would make it exact.
- **Narrow exception list in classification.** `recovery_reason` still catches only `ProofBuildError` and `UncertainResult`. A WI-inspector `RuntimeError` surfaces as `refused` rather than `recovery_blocked`; nothing executes either way.
- **Exit code for in-progress jobs.** `queued` and `running` still exit 0 in both CLIs. This was already the case before these corrections.
- **Deleted evidence.**
  - If intent and result are deleted while the native stage is waiting and its receipt exists, `reconcile` raises `UncertainResult` before `execute`. You get plain `waiting`, not the structured block, but nothing is created.
  - If they're deleted before any receipt exists, creation can happen again. That requires deleting immutable evidence, so it's out of scope.

## Original P2s
- **P2-1:** settled. Preflight, explicit locked resume, read-only classification, terminal uncertain or `stopped_safely` results, and the shared generation call intent are all in place.
- **P2-2:** settled. Content-addressed validation inputs, explicit links on both targets, and the demo regression cover it.
- **P2-3:** settled. The exact supplier contract and the named #145 WI-to-host render bridge are documented, with no remaining overclaims.

The real-lane gates are still hard-closed and no positive case was weakened.

**Coverage:** I read the current `roundtrip_build.run`, `NativeStages.recovery_reason`, the R1 test, the contract and the runbook changes, and checked them against the unchanged `_metrics`, `_rebuild` and the native and recovery tests I traced earlier. I did not re-read unchanged files beyond those, or any test logs.
````
