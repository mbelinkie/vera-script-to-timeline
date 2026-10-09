# Issue #173 verification

Acceptance authority: Automated. **Full acceptance is pending.** The source is
implemented in an isolated `codex/issue-173-compiler-v2` worktree from accepted
#172 commit `792b09bc2c1c91867fca99eb558ee6250bbd4cdd`.

## Retained focused evidence

- Additive narration/picture/marker schema tests and existing v2 schema suites:
  `npm run test --workspace @vera/contracts -- test/compiler-v2-schema.test.ts
  test/authoring-v2-schema.test.ts test/compiler-v2-bindings.test.ts` — 30 passed.
- Token adapter, generated Python v2 surface, and frozen v1 adapter regression:
  `uv run --frozen pytest tests/test_narration_v2_dependencies.py
  tests/test_issue171_generated_contracts.py
  tests/test_narration_compiler_dependencies.py -q` — 11 passed.
- `npm run test --workspace @vera/contracts -- test/compiler-v2.test.ts` — 26
  passed with golden updates disabled. The active package has 33 frozen inputs
  and matching canonical manifest/report goldens; repeated compilation checks
  exact bytes, unchanged inputs and resolved source IDs. The matrix covers
  flat/reversed root-child-return/independent overlay, all static durations,
  default/override/slate choices, complete/selected endpoints and refusal paths.
  Obsolete draft still goldens were removed; no accepted fixture was removed.
- `npm run typecheck --workspace @vera/contracts` and
  `npm run lint --workspace @vera/contracts` — passed.
- `npm run check:contracts-generated` — current. New Python adapter/test Ruff
  check, Ruff format check and mypy — passed (two source files).
- `frozen-boundary-check.json` verifies 125 baseline source/fixture/test hashes
  and restricts existing-file changes to the six approved additive v2 files.
  Recheck after the final compiler package; accepted v1/P2/P3 data is unchanged.

All npm commands use Node 24.19.0/npm 11.17.0 at the runtime path recorded in
`tool-profile.json`; Python uses the frozen uv lock. No tests or concurrency
settings are weakened. No dependencies are added.

## Full-gate continuation

After committing the complete source, run the checked-in
`run-full-validation.mjs` once with locked Node. It launches
`VITEST_MAX_WORKERS=1 npm run validate`, saves full stdout/stderr under ignored
`test-results/issue-173/full-validation/validate.log`, and atomically saves
`status.json` with source commit/tree, process IDs, exit code, elapsed seconds,
and final log SHA256. The owner and workers stop sampling after launch. The
parent performs the deferred completion check; a pending or failed status is
not acceptance and must not close the issue.

After a passing completion, verify the source pin still matches, retain the
final completion evidence and log hash, publish the exact accepted commit,
move #173 through review/Automated completion with `npm run roadmap`, and hand
the exact APIs/commit to the #148 owner through the parent. Real P5 preparation,
native delivery, Producer acceptance and the private programme remain outside
this gate.
