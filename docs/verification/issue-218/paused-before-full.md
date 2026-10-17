# #218 — reviewed candidate, paused before final full validation

Producer explicitly requested "pause before full validation". No new full gate
has launched. The issue remains open/Blocked, with its original owning task
and branch. Nothing is merged or deployed; #8 remains paused and untouched.

## Current evidence

- Helper source: `bb534bd191bedbc566f95560a0482e927826eae0`; exact CN-218-A2
  note/patch at `79a7349` explicitly approved by the Producer. Inline JavaScript
  is equivalently wrapped for the existing Ruff column limit.
- Reviewed candidate: `7121f1ec55c6b9a3126066301a2416b1c905b94b`, which adds
  evidence/disposition only. Separate read-only Claude review completed exit 0
  and **GO** for the bounded helper delta and verified TypeScript evidence reuse.
  Prompt, raw report, fast evidence and result are retained beside this file.
- All 163 affected slow regressions passed serially in 573.08 seconds on
  `bb534bd`; raw compressed log and atomic job result retained.
- Fresh Python checks on `7121f1e`: Ruff/format (547 files), mypy (158 files),
  and 657 non-slow tests passed; tests took 513.62 seconds with two workers.
- TypeScript check inputs are unchanged from the completed passing fast run
  on `04d5abc`. Claude explicitly accepted the equivalence/reuse disposition.
  This is reused evidence, not a newly passing whole `validate:fast` command.

## Failed attempts and Claude follow-up

The latest whole fast run remains **failed**: 540 contract tests passed and
five existing tests hit their unchanged 5000ms limit under host contention.
The prior full attempt also remains **failed**: 1,081 Python passes, 15 failures
and 55 setup errors. No aggregate passing full result is claimed.

Claude's non-blocking record gaps are completed here:

1. `evidence-reuse-current.json` extends the input comparison through the
   reviewed candidate and the final evidence-only additions, listing every
   post-test difference and its hash (except that record's self-reference).
   The additions are explicitly checked as non-consumed evidence inputs;
   no source/test/configuration/lockfile changed after review.
2. `full-04d5abc-failure-map.json` retains all 70 original failed/error node IDs
   and their module counts. All four modules were included in the 163-test
   passing rerun. Complete acceptance still requires the paused full gate.
3. The TypeScript timeout risk remains open for final validation on a quiet
   host. Recurrence without contention is a blocker; do not increase timeouts,
   remove cases or substitute the earlier evidence for a required final pass.

| Original failed-full module | Failed | Setup errors |
| --- | ---: | ---: |
| test_issue144_omission_bridge.py | 1 | 0 |
| test_issue190_build.py | 13 | 0 |
| test_issue190_native.py | 1 | 44 |
| test_issue192_proof.py | 0 | 11 |

## Resume boundary

Wait for explicit Producer resume before starting final full validation.
Then check the shared queue and host capacity; record the exact clean candidate,
toolchain and input hashes; run `VITEST_MAX_WORKERS=1 npm run validate` durably
with the required checkpoint and end-turn wait. Inspect complete evidence and
frozen boundaries. Only an actual qualifying passing full result permits
Automated review/completion and Closed/Done verification. No review waiver,
full-gate waiver, production operation, merge, deployment or new dispatch is
implied by the current GO or the full-access tool setting.
