# Issue #180 automated acceptance

Issue: https://github.com/mbelinkie/vera-script-to-timeline/issues/180.
Owner: `gpt-6.1-sol/high`, chat `01a121fe-5af9-7e11-a9b6-cebf5627e71b`.
Branch: `codex/issue-180-picture-boundary-evidence`. Acceptance: Automated.

## Authority and revisions

Producer accepted the exact #179 design and CN-179 at
`03f1d333b85cceacd89be85a27723783c84ed310`:
https://github.com/mbelinkie/vera-script-to-timeline/issues/179#issuecomment-6087100716.
#179 was Closed/Done before the #180 claim. Standing automated-closure policy
`24141d6977c5171439c1131187593dd0f0999816` was integrated as `e0aef5e`.

The implementation source revision under the first full gate is
`59276a33e271615401d98956fc79e9367b76444c`, tree
`a2655976600cb79e2c8ef4aa2b211d4ac3677886`. The completed passing gate's exact
revision/tree are retained in `full-validation-status.json`. The delivery commit is pinned in
the roadmap review/closure evidence. Changes after this tested revision are
limited to this verification directory and the issue-owned plan; production
sources, generated types, tests and goldens retain the tested hashes.

## Result and retained commands

The authoritative gate is `VITEST_MAX_WORKERS=1 npm run validate`, launched
from a clean checkout with `node docs/verification/issue-180/run-full-validation.mjs`.
The launcher pins revision/tree before starting and records completion, exit
code, elapsed time and log SHA-256. See `full-validation-status.json` and
`validate.log.gz` for the completed result. Logs are losslessly compressed;
the status SHA-256 refers to the decompressed original bytes. The gate includes generated-currentness,
TypeScript lint/types/tests, progress/roadmap tests, Python lint/format/types/tests.
No gate or accepted test was weakened.

Attempt 1 retained in `attempt-1-status.json` / `attempt-1-validate.log.gz` failed
only on six existing #144 CLI tests exceeding the unchanged 5,000 ms timeout.
All 82 new boundary tests passed; 396 of 402 contract tests passed. These v1
CLI consumers do not import the changed v2 implementation. The identical
gate is retried without changing accepted tests, timeout or worker settings.
Acceptance remains pending until the complete retry passes.

Attempt 2 also failed only existing CLI deadlines (12 cases; 390/402 contract
tests passed, including all 82 new cases). `runtime-gate-investigation.md`
retains the focused replay and environment-only probes; these are not a
substitute for a completed passing gate. Python checks are running separately
to finish the remaining regression evidence while host capacity is unresolved.

Additional retained check:
`node docs/verification/issue-180/audit.mjs` validates frozen bytes and reverses
only the authorized schema additions before comparing all original semantics.
`git diff --check` must pass before delivery.

Commands use the locked Node runtime at
`/Users/matthewbelinkie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin`
and `uv run --frozen` for Python. Exact versions, executable hashes and execution
profile are in `tool-profile.json`; source/lockfile hashes are in
`source-input-pins.json`; all 18 new input/manifest/report golden hashes are
in `golden-pins.json`. `frozen-source-pins.json` retains SHA-256 for 6,270 frozen
files and `frozen-boundary-audit.json` records the approved-change audit.

## Acceptance coverage and review

| Criterion | Retained evidence |
| --- | --- |
| Exact accepted authority | Producer comment and accepted revision above; resolved #179 dependency in roadmap inspection |
| Sparse required edges, no fallback | New TS tests: holes before/between/after requests, end-only/empty observations, separately missing beta/gamma onset/end; both compile and needs use the same resolver and refuse required missing evidence |
| Before/after pause and tail semantics | Nine cases at 24, 25 and 24000/1001 fps; exact rational deltas, unchanged narration samples, continuous parent ranges, distinct same-token edge ordering; 18 new frozen byte goldens at 25 and 24000/1001 |
| Identity and evidence refusals | Closed schema plus whole-envelope validation; stale/missing/inactive row, identity/currentness/source/audio/timing bindings, receipts, duplicate/conflicting capabilities, exact UTF-16 ID/quote matching including Unicode/repetition, unused invalid observations, unsafe/collapsed/crossed/overflow times |
| Honest media relations | Exact onset precedence, evidenced end, inside support, adjacent frozen-token gaps, nonadjacent/unsupported relation unknown; missing relation does not prevent a legal media cut |
| All pure consumers and compatibility | New overlay/supporting point and command/projection tests; atomic edge-preserving insert/convert/flatten/delete/swap/move/promote/playout; sparse data cannot satisfy full speech/recorded alignment; full existing provider/v1/#144/#173 regressions and all old goldens run in the full gate |
| Schemas/types and frozen boundaries | Root generated-currentness; Python generated-type/public export and new golden schema tests; frozen inventory and exact CN-179 semantic audit |
| Exact pins and limits | Tested source/tree, locked tools/profile, source/lockfiles and output hashes, completed gate status/log; closure comment binds delivery revision |

Review followed every affected public seam: authoring types, structural and point
validation, all existing edit commands, placement keys, sparse projection,
compiler/needs row selection and resolution, schema generation and Python exports.
No dependency was added. `wordIndexV2` remains a token index; separate edge-order
and coverage offsets keep before/after consumers honest. Sparse input never enters
the positional full-map preview estimator. Existing full-map/v1 bytes stay frozen.

Judgment calls retain the accepted design: a missing required observation suppresses
the row's picture while retaining the known audio spine; reviewed end-only data
does not require an invented onset; media relations depend on actual supplied
support and frozen adjacency. Frame rounding preserves exact input time and delta,
and collapsed structural supports refuse. New closed-schema capability requires
an upgraded consumer; old documents need no migration.

Synthetic receipt tests check source/audio/receipt bytes, hashes and review-status
binding in a local assembling self-check. The pure compiler validates the frozen
attestation's consistency. Neither qualifies acoustic review, real preparation,
provider output, real delivery, native/Resolve execution or the #145 proof version.
No private media, provider adapter, UI, persistence or retiming was changed.

No unresolved engineering risk emerged beyond the explicitly excluded future
assembling/application work already assigned elsewhere; no speculative Astra
register entry or successor dispatch was added. No push, merge or deployment.

## Automated closing checklist

1. Retain completed full-gate status with exit 0 and matching log hash.
2. Re-run frozen/CN-179 audit; confirm generated-currentness and diff checks.
3. Confirm delivery differs from tested source only by issue plan/evidence files.
4. Record exact delivery revision and this evidence with `roadmap -- review 180`.
5. Complete as Automated and re-inspect for Closed/Done.

The steward records the claimed chat's final cumulative local token total only
after this implementation chat finishes; no live or estimated total is used here.
