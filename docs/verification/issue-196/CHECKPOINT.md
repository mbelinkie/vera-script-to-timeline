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

See "Final local full gate" below.

## Round 2 runs (completed SUCCESS; evaluated, see GO-NO-GO.md)

Head `d9c63a84b2c7620b0f83cf9379fcf7e958bd0d85`, tree
`5eb5c6e808508b4973537fbe475693123870efe7`. Pushed at 19:15Z.

- **Push run:** https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/38296397261
  (created 19:15:10Z)
- **PR #198 run:** https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/38296403984
  (created 19:15:13Z). The expected merge tree is `5eb5c6e8` (main is still
  `98b9a614`).

Both runs completed with success: the push run at 19:46:40Z and the PR run at 19:54:18Z. The profile was drafted (`cloud/profile-draft.json`, `qualified: false`, digest `1d6b3c41…`). Both runs passed evaluation at full scope against a hypothetical local approval only.

Evaluation commands, retained with their logs in `cloud/`: `round2-draft-push.log`, `round2-eval-push.log` and `round2-eval-pr.log`.

## Final local full gate (completed)

- **Command:** `PYTEST_ADDOPTS=--durations=25 VITEST_MAX_WORKERS=1 npm run validate`
  on `289a080` (tree `173fb6e6`).
- **Process:** PID 56180, started 20:13:45Z, finished 21:13:06Z, **exit 0**.
- **Results:**
  - Vitest 402 + 1, node:test 6 + 23 + 32;
  - ruff and format clean, mypy clean;
  - pytest 499 passed in 58:02, with `--durations=25` retained in the log;
  - owner-run post-gate `git status --porcelain --untracked-files=no` was
    empty (not retained as a file).
- **Retained:** `validate-final.{metadata,log,exit,finished}`. The run was not
  repeated.

## Verdict and approval (see GO-NO-GO.md)

- **Qualification verdict: GO** by this owner, after the evidence and three
  independent reviews.
- **Approval:** the Producer's conditional instruction, "I approve 196 if
  Claude is happy with it", is satisfied by that GO. It is recorded in the
  GO-NO-GO receipt and in `cloud/profile-qualified.json`, bound to digest
  `1d6b3c41…`. `profileProblems` is clean.
- **Real-profile evaluation:** both round-2 runs pass at full scope against
  the bound profile (`cloud/round2-eval-qualified-*.log`, exit 0).
- **Activation: NOT IN EFFECT.**
  - The classifier denied the `docs/VERIFICATION_POLICY.md` and playbook
    edit: `[Instruction Poisoning]`.
  - The owner withdrew its own uncommitted AGENTS, CLAUDE, README and SKILL
    edits with `git restore`, so no guidance points at a missing section.
  - A follow-up read was also denied: `[Self-Modification]`.
  - The exact text an authorized editor must apply together is listed in
    GO-NO-GO under "Activation blocker".
  - Until then, local full acceptance remains the rule.

## Release

- **Owned processes:** no owned long-running local process remains. PID 56180
  has exited; no local test, pytest, vitest or media job from this owner is
  running.
- **Serial heavy-validation slot:** **released** by the #196 owner, session
  `9908bbc3-704d-42c5-896b-3da72b64dd71`, at this handoff.
- **What the push starts:** it starts CI runs for PR #198's final head on
  GitHub-hosted runners. They do not use the serial slot.
- **Not done:**
  - PR #198 merge and #196 closure. The integration gates and the activation
    blocker remain.
  - Next-issue dispatch; #191 stays held for the coordinator.
  - Any #174 action.
