# Issue #173 verification

Acceptance authority: Automated. **The full gate passed.** Tested source commit
`96fd70f573c3eaa1fc2b342de87ee9df00c64eaa`, tree
`a199b7ee8feb370f694c23f4d7b975d7264a1f8f`, is on dedicated branch
`codex/issue-173-compiler-v2` from accepted #172 commit
`792b09bc2c1c91867fca99eb558ee6250bbd4cdd`.

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
  Rechecked after the full gate: accepted v1/P2/P3 data remains unchanged,
  and every source-input hash matches the tested source.

All npm commands use Node 24.19.0/npm 11.17.0 at the runtime path recorded in
`tool-profile.json`; Python uses the frozen uv lock. No tests or concurrency
settings are weakened. No dependencies are added.

## Full gate and consumer handoff

`VITEST_MAX_WORKERS=1 npm run validate` passed with exit 0 on the exact source
above. Contracts: 320 tests in 18 files; tooling: 1 test; Node progress/roadmap:
6 + 23 tests; Python: 375 tests in 3006.58 seconds. Generated-currentness,
TypeScript lint/typecheck, Python Ruff check/format and mypy (100 source files)
also passed. Total elapsed time was 3094.986 seconds, from
`2026-10-09T15:18:16.944Z` to `2026-10-09T16:09:51.931Z`.

`full-validation-result.json` retains the atomic completion receipt. The complete
local log remains in ignored `test-results/issue-173/full-validation/validate.log`;
its verified SHA256 is
`d20d1f40ad0fdf695d58957be18956d499ce3bc92bd1b924a923b81771d15904`.
`source-input-pins.json`, `tool-profile.json` and the fixture `sha256.json` retain
source, runtime, generator, lock and fixture evidence. The final evidence commit
changes documentation only; it does not replace the tested source pin. No long
gate was rerun after this passing result.

Public seams: `@vera/contracts/compiler-core-v2` exports
`compileTimelineV2(document, dependencies)` and
`resolveMediaRequirementsV2(document, {timing, defaults, sourceDescriptors,
frameRate})`. The Python sibling exports
`narration_v2_dependency_from_asset(asset, provider_timing_json, frozen_block)`.
Media preparation consumes the returned exact requested/source/record ranges;
it must not recalculate them from UI ranges. Positive narration requires the
exact optional-wire audio binding. Consumers must refuse `ok:false` and any
`ok:true` result whose report is blocked. Derived word ends remain unknown for
audible-support claims. Recorded presenter and audio-cue execution remain
explicitly unavailable; terminal notes that lack a representable point retain
a visible unplaced warning. All media attestations here are synthetic verified
P5-shaped evidence; real preparation, native delivery and the private programme
retain their separate acceptance owners.

No new unresolved P4 engineering risk was exposed for the Astra register; solved
review findings are covered by the retained matrix. The canonical internal claim
does not unambiguously name a final local session record, so no token metric is
posted or estimated.
