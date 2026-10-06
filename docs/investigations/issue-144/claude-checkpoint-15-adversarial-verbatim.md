# Checkpoint15 whole-issue adversarial response — verbatim

## Claude d350510c-c1e3-48e8-bb2a-780ebaf0114a;64turns; no tests run

````text
## Verdict: closure blockers found, all at the runbook/handoff level

I found no P0 or P1 safety defects. On the paths I traced, these all held up:
- the synthetic and real lanes stay isolated;
- pointer compare-and-swap and promotion happen only after verification;
- the provider is called once per row, with no duplicates;
- replacement is whole-row, and untouched rows are only shifted in time;
- all three edits land in one revision.

Three P2 gaps do contradict explicit acceptance wording: an executable runbook, recoverable state, and an executable #145 run. Each is small to fix. I ran nothing; everything below comes from reading the code and tests.

## Actionable findings

### P2-1: A waiting or failed durable job can't be recovered from the CLI, and the advertised entry point causes exactly that state
*Code defect plus runbook mismatch.*

- **Where:** `roundtrip_driver.py:38-51` (no resume or recover action); `roundtrip_build.py:491-494` and `:565-573`; `build_jobs.py:486-494` (`_claim` returns `None` while the job is `waiting` or `failed`) and `:728-745` (`resume` is Python-only); `seam-matrix.md:25`; `operator-runbook.md:136-139` and `:289-290`.
- **Trigger:** any native stage that raises `NeedsAction`, `UncertainResult` or any other exception. Examples:
  - running `python -m vera_timeline_agent.roundtrip_build` as the #148 "preflight" (the seam matrix advertises this entry);
  - running `build` or `rebuild` once without `--boundary-file`;
  - a compiler or Node timeout inside a stage.
- **What happens:** the job is idempotent on `snapshot_id`, so a later run with the correct boundary gets the same job back. `_claim` then returns `None`, and the result is `waiting` (exit 2) forever. The tests get out of this only by calling `store.resume` directly (`test_issue144_omission_generation.py:279-284`, `test_issue144_native_build.py:245`).
- **Related permanent wedges with no recovery path:**
  - `NativeStages` treats an accepted `stopped_safely` result (e.g. Resolve not running, or a name collision, both documented as "no project mutation occurred") as permanently uncertain (`roundtrip_native.py:236-250`, `studio_assembly.py:130-157`). Even `resume` can't clear it.
  - `generate-omission` publishes `generation-inputs.json` before the validator subprocess and before `process_block` runs. Any failure in that window makes every retry refuse with "retained synthesis cache is missing", even though the provider was never called (`roundtrip_generation.py:264-275,131-136`, `roundtrip_narration.py:75-86,127`).
- **Rules affected:** "records recoverable state"; the runbook's claimed "read-only current-folder identification" and "explicit read-only recovery" don't exist; the #148 preflight should not poison the #145 proof root.
- **Repro:** after `_visual_inputs(root)`, call `main(["build","--proof-root",root])` and assert `waiting`. Then call `main(["build",...,"--boundary-file",f,"--boundary-sha256",h])` with a working `Boundary.native` and assert `complete`. Today it returns `waiting`.
- **Consequence:** fails safe, but the operator must start a new proof root, or re-decide with byte-different JSON. Both are undocumented.

### P2-2: The runbook never tells the operator to re-link the proof pairs on the rebuilt target before `promote`
*Runbook mismatch.*

- **Where:** `roundtrip_proof.py:491-511` (link check inside `_publish_baseline`) and `:808-809` (`promote` uses it); `operator-runbook.md:285-299` (sections 7–8 have no link step).
- **Why it matters:** every ready `use_source` video/audio pair on the new target must have reciprocal links, or `promote` refuses with "isolated proof link setup is unverified".
- The demo hides this. `WireBoundary.capture` links three pairs on whichever target it captures first, which is where the "six proof-link calls" come from (`issue144_wi_fixture.py:242-294`).
- **Repro:** in `run_demo`, set `linked=True` on the second `GraphStudio` before running `promote`. It is refused.

### P2-3: The host's audio verdict isn't bound to the WI render records, and the evidence-directory format is undocumented
*Handoff gap, medium confidence it matters for #145.*

- **Where:** `roundtrip_omission.py:447-474,539-541`; `roundtrip_audio.py:350-437,654-676`; `roundtrip_wi.py:802-991`.
- **What happens:** `verify_omission_evidence` reads `render.json` and `calibration.json` in the `issue-144-audio-render/v1` format, which the trusted supplier writes. The job IDs in those files declare themselves.
  - Nothing compares them to the WI `wi-effects/*/intent|effect|complete.json` records (job ID, `outputHash`, `before` observation).
  - In the demo the job IDs are `"render.json"` and `"calibration.json"`, while the WI job ID is `render-<sha>` (`issue144_omission_fixture.py:387-396`). Calibration skips WI entirely (`issue144_wi_fixture.py:321-323`).
  - The runbook never specifies the supplier contract (`profile.json`, `baseline.json`, `observation-a/b.json`, `calibration.json`, `render.json`, `source-*.wav`). It also doesn't say how a WI job maps onto that format.
- **Rule affected:** "#145 with an executable three-edit run"; every needed decision must be resolved or named as a blocker.
- **Fix:** at minimum, name this as a #145 blocker. Preferably, have the host require `render.json.jobId`, `output.sha256` and `observationHash` to match a WI `complete.json`.

## Nonblocking (P3 or improvements)

- **Evidence level missing from some artifacts.** `rebuild.json`, `promotion.json`, the omission proposal receipt and `consumed.json` don't carry their evidence level (`roundtrip_proof.py:760-766,810`; `roundtrip_omission.py:637-645`). They only bind it indirectly, but acceptance criterion 1 says every artifact "identifies" its level.
- **`compare` runs outside `proof.lock`** (`roundtrip_driver.py:252-256`), while the publisher's `os.link` briefly gives the file a second hard link (`st_nlink==2`). A concurrent read could refuse spuriously.
- **A non-`ProofBuildError` from `validate`** (e.g. `observation.get` on a non-dict at `roundtrip_proof.py:252`) leaves that capture attempt pending with an immutable response. Every retry re-crashes, and the uncaught `AttributeError` exits with code 1, which isn't one of the documented exit codes. The checkpoint-13c review's "genuinely retriable" claim is wrong.
- **Captures don't compare markers** (`roundtrip_wi.py:511-524`), although runbook lines 189-191 imply they do.
- **The omission-only lane never asserts 25 fps.** `FRAME=1920` is assumed, and `frameRate:"25/1"` in the render receipt is just what the supplier declares (`roundtrip_audio.py:28,418-422`). Only the composed lane checks 25 fps in TypeScript.
- **The omission rebuild overwrites the driver's guarded `preflight` wrapper** (`roundtrip_proof.py:749-755` vs `roundtrip_driver.py:152-160`).
- **Decision idempotency is keyed on bytes.** A reformatted but identical decision creates a second revision and rebuild for the same report. There's no second provider call (cache), and a real name collision would stop a duplicate target.
- **Code pins leave out `studio_assembly.py` and `studio_spike.py`** (`roundtrip_build.py:44-88`).
- **`roundtrip_proof.main` is a second CLI** with different actions and exit-code mapping.
- **Narration format:** the runbook says sources may be "PCM16/24", but narration must be PCM24 (`roundtrip_build.py:336-341`).

## Acceptance criteria

| Criterion | Status |
|---|---|
| Numbered runbook with evidence levels | Partial: P2-1, P2-2, P2-3, plus the evidence-level P3 |
| Focused refusal tests (target, duplicate, stale, malformed, partial-word, picture-only, residual, offline), synthetic labeling, #141-derived media | Covered |
| Validator-passing revision; reject or unsupported leaves inputs unchanged; identical replay; stale decisions refuse | Covered (byte-keyed caveat) |
| Interrupted rebuild preserves authority; no promotion before verification | Preservation and ordering hold; recovery isn't executable (P2-1) |
| Frozen boundary unchanged | Holds: only issue-owned files plus the timeout change from 15 to 90 |
| Full validation passes | Evidence provided (I didn't run it) |
| Real observations listed for the next issue | Covered (`seam-matrix.md:76-85`) |
| Seam matrix | Present; row 25's entry point causes P2-1 |
| Plan settles retry/interruption semantics and names #148/#145 blockers | Partial (P2-1, P2-3) |
| Non-transcript omission path | Covered; real qualification deferred to #145 |
| #148 preflight and #145 executable run | Partial: no safe #148 preflight command; P2-2 and P2-3 |

## Explicit assessments

- **Whole-row replacement and untouched rows: holds.**
  - At most one changed row, generated from its complete text. The new audio hash and asset ID must differ from the old ones, and the version must increase by exactly one.
  - Word marks must match the tokens at the UTF-16 level, and anchors are recompiled from the new marks (`roundtrip_narration.py:98-200`, `issue-144-omission-build.ts:33-46`).
  - Untouched rows' dependencies and sources are unchanged. The test shows the following row shifted by −39 frames with its source ranges intact.
- **Fresh target, pointer and replay safety: holds.** Native intent and WI intent are both exclusive. The new target's UIDs must differ from the prior identity. Pointer CAS happens under `flock`. Replays rederive the full report and decision chain, and stale decisions refuse.
- **Three-edit composition: holds.**
  - TypeScript requires exactly one supported move and one supported trim, both in the omission row.
  - The audio allowances for the two visual pairs come from the actual compiled preview.
  - All of it ends up in one validated revision (`issue-144-composition.ts:100-137`).
- **Synthetic vs real isolation: holds.** The real lane is hard-closed in seven places:
  1. `NativeStages.__init__`
  2. `OmissionProof.__init__`
  3. `service_inputs`
  4. `replace_row_narration`
  5. `verify_omission_evidence`
  6. TypeScript `finalizeOmission`
  7. the composition evidence-level check

  The docs don't claim that synthetic acceptance equals live support.

## #145 and future risks (not #144 blockers)

- **Frame alignment.** Narration from the accepted normalizer isn't frame-aligned (`normalize.py:158`), but `_sources` rejects sources whose length isn't a multiple of 1920 samples. So the #148 narration will almost certainly fail.
- **Quiet residue.** Residue below the numeric thresholds passes. This is an explicit, documented limitation.
- **Rebuilt render.** There's no render of the rebuilt program here, and the regenerated row could push the program over the cap.
- **Word-mark mismatch.** A real provider's word marks may not match the script tokens exactly.
- **WI conventions.** The WI reader's endpoint conventions still need live qualification.

## Coverage

I read these in full:
- **Host and entry:** `roundtrip_driver`, `roundtrip_proof`, `roundtrip_build`, `roundtrip_native`, `roundtrip_omission`, `roundtrip_generation`, `roundtrip_narration`, `roundtrip_audio`, `roundtrip_wi`.
- **TypeScript:** `issue-144-semantics.ts`, `issue-144-composition.ts`, `issue-144-text-revision.ts`, `issue-144-omission-build.ts`, `issue-144-proof-cli.ts`, `issue-144-compile-cli.ts`.
- **Existing code:** `studio_assembly`, and `build_jobs` (`publish_immutable_output`, `_claim`, `run_one`, `resume`).
- **Demo and tests:** the demo and all three fixtures, plus `test_issue144_wi_flow`, `test_issue144_composition` and `test_issue144_driver`.
- **Docs:** the runbook, seam matrix, producer policy, and the 12f/13c review records.

I only skimmed the names and parts of the remaining tests. I didn't fully trace `compiler-core`, the validator, or the TypeScript test files.
````
