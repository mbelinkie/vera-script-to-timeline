# #218 — approved derived-graphic provenance core

Owner: task `01a1416d-5da8-7003-9494-e9a75a62f1a5`,
`gpt-6.1-sol/high`, branch `codex/issue-218-provenance-core`.
Starting accepted main: `22f65c4f2b4ff61e7b08f530cdda3d92fea11d08` (actual HEAD).
Normal live inspection and claim passed; #166/#7/#20 are Closed/Done.

## Authority and bounded scope

Implement only #218 and CN-166-P1 at
`0c50a30a4e78fd771b51ee6732e78641ceb3da7b`, exact note SHA-256
`7b3949440d81e955a1306aeb1de0eed7990539619aed1b60c040295cd4d20716`.
Producer approval: #166 comment 6193340833 and #218 comment 6193341284;
receipt retained on accepted design branch under
`docs/verification/issue-166/producer-approval.md`.

Pure schemas, trusted injected retained-record resolution, immutable proposed
content revisions, canonical/byte hashing, v1/v2 compiler propagation and
negative synthetic tests. No acquisition, executable supplied methods,
persistence, authorization grant, selection/head switch, pruning, providers,
UI, registration, media generation, placement, Resolve, merge or deployment.
#8 remains paused and untouched. #64 owns durable authorization/storage and
atomic activation; #9/#67/#69 own authoring/citation UI, #8/#10 placement,
#99 registration, #167 cue design and #220 cue runtime.

## Foundation integration before feature work

Import exact accepted deltas, never merge their history or reconstruct them:

- #7 `7cb942e4d9b8d75d87ae6adc8aac97fba5d5d6ab` relative to
  `4c5e8786c9acbe99ebab3ef387c82fb5ff39e43f`.
- #20 `951c658bf06fc9b06caeab88c9d43809c41cef94` relative to
  `f1b432aa4822a2afca55483359605b909a1a1840`.
- #12 `59838d6a8bf7fa536af3382788a947f5701a7d2c` relative to
  `85d2313e2ebefb38af241c6ef16209d160e01b50`; exact module, assets,
  regression tests and export. Producer acceptance is the #12 comment of
  2026-09-22T02:15:17Z (explicit `ACCEPT #12`, Matt Belinkie, steps 1–5).
- #3 capability source `b8850c20238c02555d9c5096cc0d717a512428b7`
  plus `cc39f29acab6ec4347131e2f6f8cc626be3a396a` is accepted evidence,
  with Producer receipt in `84fbf3b`'s
  `docs/verification/issue-3/producer-checklist.md`. No #3 runtime import is
  required: #7 imports only #12's EV24 setting hash. Its Python spike/CLI and
  tests have no transitive callers in these foundations and stay excluded.

Retain an integration-only patch/source inventory separately from the feature
diff. Import required executable code, schemas, assets and regression tests;
do not import unrelated historical documentation or #8-only code. Resolve
overlaps only by preserving both accepted current-main and foundation behavior.
Unsafe separation or any extra unaccepted foundation is a stop condition.
Run applicable accepted #7/#20 and prerequisite regression checks before the
feature. Reassess active-work forecast immediately afterward.

The isolated integrated baseline exposed #144 source-union assumptions.
Producer approved CN-218-A1 at `1a7cb50`; retain its receipt under
`docs/verification/issue-218/compatibility-approval.md`. Only its two refusal
guards modify the accepted #144 helper/observation seam. Original assertions
and goldens stay unchanged. Mechanical source compatibility additionally
replaces #7's non-erasable constructor shorthand and teaches the #144 native-TS
loaders their exact new compiler dependency graph, keeping source-hash receipts
in sync with Python consumers. No native operation or graphic support is added.
The retained integration-only compatibility patch excludes new provenance
feature code; isolated types and 107 regression tests passed.

## Contracts, fixtures and consumers

Only the seven v1/v2 schema deltas enumerated by CN-166-P1, its common
dependency definitions and their generated TypeScript/Python outputs change.
The v2 script schema remains identical. No new software dependency is needed:
use existing Ajv, canonical serializer, crypto and contract generators.
Audit all exhaustive compiler/package/validator consumers. Existing unsupported
runtime paths must continue to refuse rather than claim provenance support.

The pinned TypeScript generator overflows on a recursive union reached through
aggregate roots. A bounded generator adjustment supplies an `unknown` type
hint only in temporary TypeScript input copies; checked-in recursive JSON
Schemas and Python generation stay strict. Generated unknown JSON values
require runtime validation. No package or alternate canonicalizer is added.

All original frozen fixtures/goldens stay unchanged. CN-166-P1's existing-test
exception is the media-backed graphic branch of `compiler-v2.test.ts` and
slice-owned migrated input/report copies of the three named
`visual-only-graphic-still-*` fixtures under `issue_173/compiler`.
Only required legacy classification and resulting dependency/transitive report
hashes change. Migrated manifests compare byte-for-byte with original goldens;
non-graphic v2 and legacy v1 output remain byte-identical. Any additional
frozen-test change stops for revised approval; CN-218-A1 is the separately
approved one-line #144 test-helper guard described above.

## Checks and acceptance

Test-first where practical: closed shapes; finite JSON; canonical keys, arrays,
nulls and source sorting; verified byte hashes; missing/duplicate/unused records;
project/source/content/template mismatch; explicit classification; v1 omission
trust residual and false trusted v2 classification; materialized-media binding;
manual/derived create, repeat with upstream unavailable, changed-data refresh
(including unchanged visible values), incompatible migration and input/old
revision immutability. Preserve #7 semantic/source IDs and #20 use/copy hashes.

Focused baseline and feature tests, `npm run validate:fast`, generated-currentness,
frozen-boundary audit and `git diff --check`; separate read-only adversarial
Claude review of integration plus feature, fixes and delta review; then final
full acceptance under accepted-main `docs/VERIFICATION_POLICY.md`. Preserve
the expensive-check queue; owner runs long checks. Cloud substitution requires
the actual accepted-main validator; changed manifests/configuration/locks make
it ineligible. Claude unavailable means stop for a revision-specific waiver.

Retain exact commands/toolchain/results/tested source and criterion coverage.
Automated acceptance requires no Producer repetition of deterministic checks:
record `roadmap -- review`, then `complete --accepted-by Automated` only after
all gates pass; verify Closed/Done. Deliver a clean reviewed branch/commit and
integration patch, explicitly unmerged/undeployed. Later consumers must
explicitly integrate this source and reconcile identical accepted foundations
if #8 lands separately, rerunning applicable integration checks.

Initial forecast: 5–9 active hours, moderate confidence; foundation separation
is the main uncertainty. Approval/external/queue waits are separate. For any
unattended check or queue wait expected to take at least ten minutes, retain a
durable job/log/result and checkpoint, confirm one 15-minute thread heartbeat,
then end the active turn. Cancel it on completion, failure or blocker.
