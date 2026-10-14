# #202 candidate and #192 integration handoff

Status: **candidate only; acceptance incomplete**. Claim remains owned by chat
`01a1373c-fd02-7d01-bc90-d2955c92a464` on
`codex/issue-202-v2-revision-core`, accepted base
`9be24e8173fd8d75fe7470ba936e10a24b525216`. #192 stays open.

The coordinator authorized parallel coding and bounded serial focused checks.
#190 retains the heavy validation/review/media/native reservation. No fast,
full, Claude, Python, media, native or provider job ran in this task. No PR,
merge or issue closure is supplied by this checkpoint.

## Delivered internal seam

Import directly from `packages/contracts/src/issue-192-v2-revision-core.ts`;
no shared package export or generated contract changed.

1. Supply a validator/compiler-ready baseline and closed `RevisionCommandsV2`.
   Boundary inputs name exact block/owner/token/affinity/sequence version.
   Trim inputs name exact selected range/block version and shorter positive
   source duration for a Full/Quiet standalone clip. The compiler calculates
   linked picture/audio and downstream placements in the accepted rational
   coordinate domains. There is no picture-only trim command.
2. To combine C, prepare A/B first without C, using only their preparation
   replacements. Bind accepted #191 omission to that staged document's
   canonical hash. Then `prepareRevisionInputsV2` with A/B/C and all affected
   preparation replacements returns the final staged document, dependencies
   and exact whole-row regeneration request. Bind the accepted #191 handoff
   to **these staged dependencies**, including explicitly supplied refreshed
   preparation bindings. Their document binding remains the prior binding
   until accepted replacement finalization updates it. The accepted #191
   Python request-validation seam permits this explicit prior-dependency hash;
   this task did not invoke it or authorize any service.
3. `createRevisionProposalV2` consumes that exact handoff, calls accepted
   `finalizeReplacementV2`, compiles deterministically, and binds full inputs,
   revised document/dependencies, manifest/report and readable comparison.
   Actual fresh compiled row duration supplies placement impact. D1 examples
   187/200/213 are synthetic tests, not native or provider receipts.
4. `decideRevisionV2` reconstructs against current document/dependencies and
   checks exact proposal, live head, explicit outcome and history hash.
   Persist its returned history atomically with its returned revision. Reject
   preserves original document/dependency object identities. This pure core
   has no persistent transaction or permission/authentication service.

#192/#190 must authenticate ownership, adjacent observations, raw bytes,
currentness, source maps, preparation/media receipts, upstream omission
decision and replacement service authorization. Explicit commands alone do not
establish inferred-native truth. #192 retains fresh package/delivery/reopen and
the exact combined-tree acceptance gates. No qualification flag unlocks those.

## Source correspondence

Raw SHA256, without the runtime canonical `sha256:` prefix:

| Source | SHA256 |
| --- | --- |
| New revision core | `fab92854cf37138f8aa4ef9b00705b4454dfb95e2fce8ecbbec889b41a8a1709` |
| New tests | `98413874c847c4fb46a3aa9a315d36b04f79517ac8596237c3633d2cc5aa31a7` |
| Accepted validator | `136ad93f3279dfe75fed07ea91e419c17c897ade7cdcf253f5e690c96dd97f79` |
| Accepted sequence edits | `3f9621ac9d23ec1390a60c898c5db58100a7f5f882f5831f712eaab217f4f1ee` |
| Accepted v2 compiler | `9fdf3929143a2f3787f94ae9878c607dcc08381265b65bda825807d8f8bd06ea` |
| Accepted omission | `37310708a6152a8845c91466d2472c2e18b649d40ffd8c5f8c2cf49b71e0a226` |
| Accepted replacement finalizer | `b8fe145e2dcfb842963a256935ca83af8b0b0130d84a04a9bc031741e818f3be` |

All five accepted TS API hashes match the accepted source pins. Changes are
confined to four new sibling source/test/plan/checkpoint files; no frozen
contracts, generated files, fixtures, goldens or accepted tests are changed.

## Focused evidence and retained failures

Node 24.19.0, npm 11.17.0, Darwin/x64; TypeScript 6.0.3, ESLint 10.9.1,
Vitest 4.1.11, AJV 8.20.0 and ajv-formats 3.0.1. Existing retired #177
dependencies were reused via an ignored local overlay, with root package,
lock and all three workspace package manifests hash-identical to this base.
All three `@vera` workspace links resolve to this task's own packages. No
installation or package/lock change occurred. Exact origin/paths are retained
privately in ignored `out/issue-202/dependency-origin.json`.

Commands use pinned Node, with serial execution:

- `node node_modules/typescript/bin/tsc --project packages/contracts/tsconfig.json`:
  final `tsc-delta2` exit 0 for the source/test hashes above.
- `node node_modules/eslint/bin/eslint.js <new-core> <new-test> --max-warnings=0`:
  `eslint-delta1` exit 0. Core is unchanged since this pass. Later test-only
  changes received `eslint-delta2` exit 0 against the final test hash.
- From `packages/contracts`,
  `node ../../node_modules/vitest/vitest.mjs run test/issue-202-v2-revision-core.test.ts --maxWorkers=1`:
  initial exit 1, four unchanged A/B/decision/refusal cases passed, four C
  setup cases failed. Only the C setup helper was corrected afterward.
- Same single-file command with `-t 'composes|source shortage'`:
  `vitest-delta1` exit 1; all three D1 cases passed, one source-shortage error
  expectation failed. The other four tests were intentionally filtered out.
- Same single-file command with `-t 'source shortage'`:
  `vitest-delta2` exit 1 because the independent diagnostic check omitted the
  revised text hash. Corrected only that test's document binding.
  `vitest-delta3` exit 0, one passed/seven intentionally filtered out. It
  proves direct `SOURCE_INSUFFICIENT` plus accepted finalizer refusal.

These retained runs exercise all eight cases across affected deltas; they are
**not a complete green whole-file, fast or full acceptance run**. Reused
passing focused cases remain unchanged: the sole post-initial setup-helper
change affects C tests only, and subsequent edits affect the source-shortage
test only. Core is unchanged across all Vitest runs. No assertions, timeout,
test inventory or accepted boundary was weakened.

The first startup attempt exited 1 before TypeScript could load because the
new worktree had no dependencies. The first actual type check exited 2 for a
synthetic narrated-image audio-policy type mismatch. The first lint check
exited 1 for primitive formatting and an unused test-helper parameter. All
failures remain failures; all follow-up fixes are in the two new files only.
Individual logs, immutable command/result/source/tool receipts and checkpoint
are retained under ignored `out/issue-202/`. No live owned job remains.

## Next required gates

Coordinator slot grant/drain → fast checks and full frozen/golden/currentness
coverage → independent adversarial Claude review of identity, hashing, paths,
freshness, rational timing and composition → fixes/affected checks/delta review
→ complete qualifying final evidence against the exact reviewed delivered
tree. Pure-logic #196 substitution is conditional on all accepted policy
conditions and accepted-main validator exit 0; CI color alone is insufficient.

Only after these gates: attach the PR, merge as authorized, record roadmap
review/Automated completion, independently confirm Closed/Done and release
ownership as required. No new Producer judgment is requested for this pure
scope; real native/provider/audio/visual acceptance remains outside #202.
