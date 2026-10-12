# Issue #196 checkpoint

Updated 2026-10-12. Record:
[docs/plans/issue-196-qualification.md](../../plans/issue-196-qualification.md).

## Identity

- **Owner:** task `claude:33ed0ca5-fcd6-4650-9bfd-63db45ef7a11`, model
  `claude-opus-5-5`, high effort, under the Producer's same-owner provider
  exception (not an ordinary model-match claim; routing labels unchanged).
- **Sessions:** the current CLI session is
  `9908bbc3-704d-42c5-896b-3da72b64dd71` (job `9908bbc3`). The coordinator
  resumed it from `da5a3fbd-c7c1-45af-bb5a-d3d5e12bf4b5`, which is done. That
  conversation began as `85843512-9132-4b84-9c1e-86173c4de542`, the identity
  the GitHub claim marker records, which is now retired.
- **Worktree:**
  `/Users/matthewbelinkie/Desktop/ONGOING/VERA Script to Timeline/worktrees/claude/issue-196-cloud-preparation`
- **Branch:** `claude/issue-196-cloud-validation-prep`, pushed. Draft PR #198
  is attached to the root by the coordinator.
- **Serial heavy-validation slot:** held by #196. Owned local commands have
  all drained. The fast runs completed with exit files, and nothing is left
  running.

## State

- Verified before execution:
  - #196 was Ready;
  - #193 is Closed/Done, and its PR #197 merged at `98b9a614`;
  - #184 is Closed/Done.
- Integrated: merge `4f49b55` = origin/main `98b9a614` + preparation `d2720d9`
  + plan (= `7ff426f`) + policy (= `5ab39b2` text).
- Commits `712ee15` (preparation-review fixes) and `ea5db6c` (independent
  review fixes) were pushed at 18:28Z.
- **Calibration round 1** (`ea5db6c`, tree `7c5ea7bc`):
  - push run 38291149935 succeeded in 39:55;
  - PR run 38291234081 succeeded in 29:59;
  - pytest 499/499, Vitest 403, node:test 60; no skips; no tracked-file changes.

  The round was refused as a qualification baseline because Vitest display
  names collide on `it.each` cases: 403 tests, 396 distinct names. See
  [cloud/ROUND1.md](cloud/ROUND1.md).
- **Fix:** duplicates are numbered in declaration order at collection time.
  This changes qualified controls, so round 2 must be two fresh runs on the
  fixed tree.

## Blocked actions (auto-mode classifier denials; not bypassed)

1. **Execution phase not recorded on #196.** The issue comment and the Project
   Status change Ready → In progress were denied as
   `[External System Writes]`, and nothing was posted.
   - Intended marker: vera-claim `phase: producer-authorized-same-owner-execution-active`.
   - Project item `PVTI_lAHOEuIric4BhyWqzhAMqrY`.
   - Status field `PVTSSF_lAHOEuIric4BhyWqzhgs1GI`, option In progress
     `2304b1f2`.
   - The push and the draft PR were later allowed. The issue comment was not
     retried.
2. **Policy pointers not carried.** `5ab39b2`'s pointer paragraphs in AGENTS.md,
   CLAUDE.md, README.md and the coordination SKILL were denied as
   `[Instruction Poisoning]`, and the cherry-pick was aborted. The policy
   document itself is on the branch.

## Local commands and results (`docs/verification/issue-196/`)

| Command | Exit | Retained |
| --- | --- | --- |
| `npm ci` (npm 11.17.0, Node v24.19.0) | 0 | `npm-ci.*` |
| `uv sync --frozen` (uv 0.12.5) | 0 | `uv-sync.*` |
| `npm run validate:fast`, attempt 1 | 1 (six ESLint errors in new scripts; fixed) | `validate-fast-attempt1-lint.*` |
| `npm run validate:fast`, attempt 2 | 0 | `validate-fast.*` |
| `npm run validate:fast`, after the review fixes | 0 | `validate-fast-delta.*` |
| `npm run validate:fast`, after the duplicate-ID fix (19:12:22–19:13:53Z) | **1**: 8 Vitest subprocess tests in `packages/contracts` hit their 5000 ms timeouts | `validate-fast-dupids.*` |
| `--draft-profile` on round-1 run A | 1 (refused: duplicate Vitest IDs) | `cloud/draft-run-A.*` |

### Duplicate-ID fast run diagnosis (retained failure, not re-run)

- **Load:** the host was heavily contended, with load averages 24.91 / 14.95 /
  11.23 at 19:14Z. CPU was dominated by desktop apps outside this task. No
  other test or media process was running.
- **Not caused by the delta:** the failing tests are subprocess CLI tests in
  `packages/contracts`. The delta touches only `scripts/cloud-evidence*`.
  `packages/`, `tests/`, `python/`, `fixtures/` and `contracts/` are
  byte-unchanged since `ea5db6c`. On that same tree, the contracts suite passed
  locally twice (`validate-fast.*`, `validate-fast-delta.*`) and 402/402 in
  both cloud round-1 runs.
- **Classification:** host-capacity timeouts, retained as a failed fast run.
- **Delta checks that did pass:** `eslint scripts/*.mjs` is clean, and the
  helper tests pass 32/32, including the two review-requested regression
  tests.
- **Not re-run:** repeating it under the same load would not add evidence.
  Round 2's full CI gate runs the whole suite on clean runners.

## Resume

1. Confirm the duplicate-ID delta's fast check and review. Commit and push
   (one push).
   - This starts round 2: a push run, plus a `pull_request` synchronize run on
     #198.
   - Record both run IDs below, then yield.
2. When both runs have completed:
   1. Draft the profile from the push run with
      `--draft-profile docs/verification/issue-196/cloud/profile-draft.json`.
   2. Add the PR run to `calibration.runs`.
   3. Evaluate both runs against a **local hypothetical** approval only.
   4. Compare against the #193 reference and write the go/no-go.
3. Real approval comes only from the Producer. Leave `qualified: false` in the
   retained draft.

## Round 2 runs (completed SUCCESS; evaluated, see GO-NO-GO.md)

Head `d9c63a84b2c7620b0f83cf9379fcf7e958bd0d85`, tree
`5eb5c6e808508b4973537fbe475693123870efe7`. Pushed at 19:15Z. This section
is uncommitted on disk, because a push would cancel the PR run and change the
tree.

- **Push run:** https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/38296397261
  (created 19:15:10Z)
- **PR #198 run:** https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/38296403984
  (created 19:15:13Z). The expected merge tree is `5eb5c6e8` (main is still
  `98b9a614`).

Both runs completed with success: the push run at 19:46:40Z and the PR run at 19:54:18Z. The profile was drafted (`cloud/profile-draft.json`, `qualified: false`, digest `1d6b3c41…`). Both runs passed evaluation at full scope against a hypothetical local approval only.

When both runs have completed:

1. Draft the profile:
   `node scripts/cloud-evidence-validate.mjs --draft-profile docs/verification/issue-196/cloud/profile-draft.json --repo mbelinkie/vera-script-to-timeline --run 38296397261 --attempt 1`
2. Add the PR run to `calibration.runs`.
3. Evaluate both runs with a local hypothetical approval only:
   - push run: `--event push --expected-tree 5eb5c6e8…`
   - PR run: `--event pull_request --pr 198 --expected-tree 5eb5c6e8…`
4. Write the go/no-go.
