# Issue #180 — implementation and blocked Automated acceptance

**Status: Blocked. No acceptance or closure has been recorded.**

Issue: https://github.com/mbelinkie/vera-script-to-timeline/issues/180.
Owner: `gpt-6.1-sol/high`, chat `01a121fe-5af9-7e11-a9b6-cebf5627e71b`.
Branch: `codex/issue-180-picture-boundary-evidence`. Acceptance: Automated.

## Authority and exact source

Producer accepted the #179 design and CN-179 at
`03f1d333b85cceacd89be85a27723783c84ed310`:
https://github.com/mbelinkie/vera-script-to-timeline/issues/179#issuecomment-6087100716.
#179 was Closed/Done before the claim. Standing policy
`24141d6977c5171439c1131187593dd0f0999816` was integrated as `e0aef5e`.

Implementation: `59276a33e271615401d98956fc79e9367b76444c`.
Latest full-gate source: `7b3cbd63a8e572d9e4f99c3427a74afee3fb8ccc`, tree
`e23fd0275292d9989c8b5566a4e0cdd854f9112e`.
Changes after the implementation commit are issue plan/evidence files only.
All 43 pinned source/lockfile/golden files match the tested snapshot.
The final evidence delivery revision is pinned in the roadmap blocked comment;
this local branch has not been pushed.

## Behavior and review

Picture cuts now accept separate sparse reviewed boundary evidence. Only
observations requested by actual operations are required; every supplied
observation is validated. Before gamma preserves the pause following beta;
after beta uses beta's independently evidenced audible end. End-only evidence
can serve an after edge. Row endpoints preserve the full narration samples,
including trailing audio. Missing required observations block picture/needs
without substituting a neighboring word or row endpoint.

Compiler and media-needs share resolution. Authoring validators, keys, projection
and atomic commands preserve the explicit edge. Editorial order distinguishes
before/after on the same token; coverage uses the separate after offset.
Sparse observations never enter the positional full-map preview estimator.
Old documents need no migration; older closed-schema consumers must upgrade
before reading the new capability. No dependency was added.

Review covered all affected public seams, generator selections and Python
exports. Exact reduced times, quantization/deltas, immutable audio bindings,
whole-envelope currentness, frozen-token adjacency, row-picture suppression,
parent continuity and unsupported-capability refusal follow accepted §§3–6.
No new unresolved product decision or model escalation was identified.

## Checks and complete full-gate failures

The unchanged gate arguments are `VITEST_MAX_WORKERS=1 npm run validate`.
`run-full-validation.mjs` requires a clean checkout, pins source/tree, runs the
gate with locked Node PATH, and records completion/exit/log SHA-256.

| Attempt | Exact source | Compile cache | Result |
| --- | --- | --- | --- |
| 1 | `59276a33e271615401d98956fc79e9367b76444c` | Off | Exit 1; 6 existing CLI 5,000 ms timeouts; 396/402 contract tests passed |
| 2 | `1a67d5e19db262aa02dfa0e0f7c7e19a74deeceb` | Off | Exit 1; 12 existing CLI 5,000 ms timeouts; 390/402 passed |
| 3 | `7b3cbd63a8e572d9e4f99c3427a74afee3fb8ccc` | Recorded Node cache | Exit 1; 12 existing CLI 5,000 ms timeouts; 390/402 passed |

All 82 new boundary tests passed in each attempt. Every reported full-gate
failure was an unchanged deadline in frozen CLI tests; no assertion failure or
changed golden was reported. Those v1 CLI paths do not import the changed v2
implementation. The full command stopped before its Python stage, so **the
complete required regression gate has not passed**. Progress/roadmap and full
Python results are not claimed from these aborted command chains.

Generated-currentness, TypeScript lint/types and tooling-smoke tests passed.
Python lint/format and mypy passed (101 source files). The separate 394-item
Python run reported no test failures before the owner stopped it with SIGTERM
(exit 143) to avoid duplication/resource competition with the third full gate.
Its raw status/log are `python-validation-status.json` / `python-validate.log.gz`;
that intentional stop is neither a passing full Python suite nor a product failure.

Final focused checks are retained in `focused-typescript-status.json` /
`focused-typescript.log.gz` and `focused-python-status.json` /
`focused-python.log.gz`. Boundary/authoring: 102 passed; Python: 19 passed.
The corrected compiler/binding/schema capture is `focused-compiler-status.json`
/ `focused-compiler.log.gz`: 41 passed. Their exact argument arrays and results
are recorded against the latest tested source (143 TS tests total). These
focused passes do not replace the full gate.

`runtime-gate-investigation.md` retains the actual replay probe, measurements
and environment-only cache/application-policy tests. A later uncached replay
passed at 2.37 s with identical bytes, and the exact omission-finalization case
passed at 3.91 s with the cache. The full retry still failed; no cache or isolated
pass is treated as acceptance. No accepted test, timeout, fixture, golden,
dependency or production source was changed to make a failure pass.

## Matrix and retained pins

| Accepted requirement | Implemented evidence |
| --- | --- |
| Sparse required edges and no fallback | TS holes before/between/after, empty/end-only evidence, separately missing beta/gamma onset/end; shared needs/compile refusals |
| Pause/tail and exact arithmetic | Nine cases at 24, 25 and 24000/1001 fps; exact deltas, narration samples, continuous parent and distinct same-token edges; 18 new byte goldens at 25 and 24000/1001 |
| Identity/receipt/currentness and unsafe input | Closed-schema, whole-envelope, source/audio/timing/row/receipt refusals; duplicate/conflicting capabilities; unused invalid observations; exact UTF-16 ID/quote tests including punctuation, repetition, combining characters and surrogate pairs; unsafe/reduced/crossed/overflow times |
| Honest media relations | Exact onset precedence, evidenced end, inside support, adjacent frozen-token gap and nonadjacent/unsupported unknown relation |
| All pure consumers | Overlay/supporting points and event-edge/cycle checks; atomic insert/convert/flatten/delete/swap/move/promote/playout; honest projection fallback; boundary-only cannot satisfy full speech/recorded alignment |
| Schema/generated types | Root generated-currentness, public Python type/export checks and all 18 new golden schema cases |
| Frozen compatibility | 6,270 protected baseline files byte-identical; exactly CN-179 additive schema semantics; old compiler/authoring golden regression coverage in focused TS checks; full legacy CLI deadline gate remains pending |

`source-input-pins.json` and `golden-pins.json` pin all 43 source/lockfile/new
input/output files. `frozen-source-pins.json` retains SHA-256 for 6,270 protected
files; `frozen-boundary-audit.json` records exact CN-179 reversal/comparison.
`tool-profile.json` records model/effort/task, locked versions, executable hashes,
worker setting and the third gate's Node cache directory. `artifact-pins.json`
pins profile, source/input/output inventories, evidence scripts, logs and statuses.
Logs are losslessly compressed; status log SHA-256 values refer to decompressed
original bytes. `git diff --check` passes on delivery changes.

Synthetic receipt self-checks verify source/audio/receipt bytes, hashes and
review-status binding locally. The compiler validates frozen attestation
consistency. This does not qualify acoustic review, real preparation/provider
output/delivery, native/Resolve execution or the #145 proof version. No private
media, provider adapter, UI, persistence or retiming changed. No merge, push,
deployment or successor dispatch occurred.

## Resume and closing authority

Keep the same active claim and exact Sol/high route. Stable execution capacity
and one complete passing locked-toolchain gate are required; do not waive the
frozen deadlines or request Producer reapproval of already accepted CN-179.

1. Start from a clean checkout on this branch; verify source/golden pins.
2. Run `node docs/verification/issue-180/run-full-validation.mjs` with the locked
   Node PATH and the recorded cache setting if desired. Retain the complete
   status/log, including every required language/progress/roadmap check.
3. After exit 0, revalidate frozen/CN-179 and generated-currentness/diff checks;
   bind tested and delivered revisions, allowing only plan/evidence differences.
4. Record passing evidence with `roadmap -- review 180`, complete as Automated,
   then re-inspect for Closed/Done. No closure is authorized by current evidence.

Post-closure final cumulative local token accounting belongs to the steward
only after this claimed implementation chat finishes; no live estimate is used.
The Astra register step applies after completion; no speculative risk or dispatch
entry was added during this blocked implementation.
