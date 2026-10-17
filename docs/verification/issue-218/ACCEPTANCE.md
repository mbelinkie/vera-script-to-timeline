# #218 — Automated acceptance evidence

The approved pure derived-graphic provenance core is implemented and reviewed.
The complete local final gate **passed** on
`2832f84cda774ee3d1395a89ebf9c9e137f70e47`, branch
`codex/issue-218-provenance-core`. The delivery commit containing this record
adds only the explicitly enumerated non-consumed evidence files. No executable,
test, contract, configuration, lockfile, fixture or runtime input changed after
the passing run. See [the post-test comparison](final/post-test-differences.json).

This supersedes the historical pause receipt. The Producer's conditional
instruction to start this existing #218 thread's full validation at the usage
reserve was verified from the coordinator's user-provided goal. The same
claimed owner resumed only after express heavy-slot release and actual drain.
There was no new claim, duplicate task, product-scope expansion or #8 work.

## Complete final gate

`VITEST_MAX_WORKERS=1 npm run validate` completed exit **0**,
2026-10-16 10:18:51Z–11:29:01Z. This is a new complete passing local gate,
not an aggregation of partial/reused passes or cloud substitution.

| Required stage | Actual result |
| --- | --- |
| Generated-currentness | Current through the normal generator |
| TypeScript lint and types | Passed |
| Contract tests | 27 files, 545 passed |
| Tooling test | 1 passed |
| Progress / roadmap / cloud-evidence tests | 6 / 23 / 32 passed; no failures or skips |
| Python Ruff / format | Passed; 549 files formatted |
| Python mypy | Passed; 158 files |
| Complete Python suite | 1,151 collected and passed; zero failures, errors or skips |
| Python JUnit inventory | 1,151 unique testcase identities, all successful |
| Frozen boundaries and whitespace | Passed; only approved changes |

Python tests took 4,128.92 seconds. The slowest 25 actual durations are retained
in [durations25.txt](final/durations25.txt). Report-only pytest options were
`--durations=25 --junitxml=out/issue218/full-final-2832f84/pytest-results.xml`;
no selection, skip, timeout or assertion was altered. `PYTHONUNBUFFERED=1`
enabled durable live output. The complete command/environment is retained in
[result.json](final/result.json).

Pinned runtime: Node 24.19.0, npm 11.17.0, uv 0.12.5, Python 3.12.14,
Darwin Intel; FFmpeg/FFprobe 8.1.2. Installed lock/venv metadata, options,
source/configuration/locks and all 7,074 tracked input hashes were recorded
before and after. The two inventories are identical. The actual worktree was
clean at start and finish, and every tracked file still matched afterward.
Raw hash identities and counts are in [qualification-audit.json](final/qualification-audit.json).

Retained artifacts: [full log](final/validation.log.gz),
[JUnit](final/pytest-results.xml.gz),
[before inventory](final/inputs-before.json.gz),
[after inventory](final/inputs-after.json.gz), and
[final boundary audit](final/frozen-boundary-audit.json).

## Criterion-by-criterion evidence

| #218 criterion | Evidence and outcome |
| --- | --- |
| Exact approval, accepted foundations and bounded integration | [Plan](../../plans/issue-218-provenance-core.md), foundation-inputs.json, original accepted #7/#12/#20 patch archives, integration baseline/results and compatibility patch. Approved CN-166-P1 bytes and CN-218-A1/A2 notes/patches rechecked. No #8 code/history/native dependency. |
| Closed shapes, explicit classes, hashes, evidence validation and diagnostics | Seven approved schemas/generated types and pure resolver/compiler modules. Runtime finite JSON/safe-integer checks, project/identity/byte/hash/template validation, missing/duplicate/unused inventory and binding refusals pass. Full tests include all 45 owned core/compiler cases. |
| Create/repeat/refresh/migration and recovery matrix | Synthetic tests verify frozen repeat, retained evidence without upstream access, changed data including unchanged visible labels, explicit recovery from lost/invalid old template or source bytes, incompatible targets, project isolation and immutable inputs/older revisions. Methods are retained identities and never execute. |
| Existing semantic/template/use/copy identities and byte goldens | Accepted #7/#20 regressions pass. No original fixture changed. Three approved migrated input/report copies change only legacy classification/dependency hashes; compiled manifests remain byte-identical. Classification stays in complete dependency hash material. |
| Generation, consumers, boundaries, focused/fast/review/full policy | Normal generation is current. Consumer audit retains explicit unsupported adapter refusals. Approved existing-test exceptions only; original v2 script schema/models unchanged. Focused/fast evidence and independent adversarial Claude review/fixes/delta are retained; this final complete local gate passes. |
| Concrete API, example, responsibilities and rollout/handoffs | [API and synthetic example](../../design/issue-218-provenance-core-api.md) document injected records and pure proposals, #64 storage/auth/atomic publication/pruning, reader-first rollout, #8/#10 placement and #9/#67/#69 UI handoffs. No runtime/provider/persistent-storage support is claimed. |
| Exact delivered source, retained evidence and Automated completion | Tested source is pinned above, with a clean branch and enumerated evidence-only delivery delta. Required review and all final checks pass. Roadmap review/completion must reference the actual delivery commit and verify Closed/Done. No merge/deployment is implied. |

## Independent review and previous failures

Initial separate Claude adversarial review of `4bf02e0` returned NO-GO. Its
migration recovery and unsafe integer findings were reproduced, fixed and
covered by new negative/recovery tests. The `04d5abc` delta review returned GO.
The first complete full attempt then exposed the two frozen helper conflicts;
the Producer explicitly approved **CN-218-A2 at 79a7349**. Only that patch,
with equivalent lint-only wrapping, was applied. All 163 affected slow tests
and 657 fresh non-slow Python tests passed. The subsequent separate Claude
review returned **GO** for `7121f1e`, the helper changes and the verified
unchanged-input TypeScript evidence reuse. Reports/prompts/results and
dispositions remain beside this record. The final full run's executable inputs
are identical to that reviewed state.

Previous attempts remain failed: the initial corrected lint issue; default
parallel and later contended TypeScript timeouts; the `04d5abc` full result
(1,081 passed, 15 failed, 55 setup errors); and the resumed startup invocation
that exited 4 before Python collection because the report-only absolute JUnit
path contained spaces. The reporting path was corrected to a relative path,
arguments checked and the failed invocation drained before this final run.
Its [failed result](final/startup-report-path-failed-result.json) and
[log](final/startup-report-path-failed.log.gz) are retained. Nothing failed was
relabeled passing. This final complete pass resolves the acceptance gap and
the previously observed timeout risk on the quiet shared slot.

## Delivery and limits

Accepted main remains the required starting pin `22f65c4`. Retained binary-safe
patches separate [foundation integration](final/integration-source.patch.gz)
from [feature work](final/feature-source.patch.gz), with a
[complete source delta](final/complete-source.patch.gz) against that main.
The earlier integration-only compatibility archive remains available too.
Later consumers must integrate the exact accepted source explicitly and
reconcile identical already-accepted foundations if another owner integrated
them first, preserving both behaviors and rerunning applicable integration checks.

The delivery is **local, unmerged and undeployed**. No provider acquisition,
method execution, production storage/auth/head switch/pruning, native placement,
media generation, UI, new template, #8 work or external runtime qualification
was performed as product behavior. Historical legacy classification and trusted
template compatibility remain explicit upstream trust responsibilities; current
Python packages refuse new provenance formats pending their verified adapter.
These are declared owner boundaries, not new unresolved engineering findings
for the Astra risk register. No additional speculative entry is introduced.

The actual owned processes and global heavy-test inventory were empty after
completion. The shared heavy slot was explicitly **released** to the Sweden
sequence coordinator / #209 at the time recorded in
[heavy-slot-release.json](final/heavy-slot-release.json). The heartbeat is
canceled. Remaining work is bounded acceptance bookkeeping only; no new heavy
phase or next issue is dispatched. Post-closure final-session token accounting
belongs to the roadmap steward after this implementation task finishes.
