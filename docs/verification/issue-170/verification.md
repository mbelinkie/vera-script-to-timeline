# Issue #170 verification checkpoint

Status: implementation checkpoint committed; required full validation passed with retained output and exit status. This record supplies validation evidence and does not claim independent review or issue acceptance.

Branch: `codex/issue-170-authoring-v2-schemas`  
Baseline: `e32727f0c0e65dc5a8561e0f470ed28e59bd1809`  
Working directory: `/Users/matthewbelinkie/.codex/worktrees/issue-170-authoring-schemas/VERA Script to Timeline`

Validated implementation: `dd3c71bf302062f422e9e8bc5162a9dfd47af102`.

## Completed focused checks

- `PATH="/Users/matthewbelinkie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" ctx-wire run rtk npm run test --workspace @vera/contracts -- authoring-v2-schema.test.ts` — 15/15 tests passed.
- `PATH="/Users/matthewbelinkie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" ctx-wire run rtk npm run lint --workspace @vera/contracts` — passed.
- `PATH="/Users/matthewbelinkie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" ctx-wire run rtk npm run typecheck --workspace @vera/contracts` — passed.
- The focused schema test invokes `generate-contracts.mjs --check`; frozen v1 snapshots in `source-pins.json` show byte-identical v1 schemas, generated TS/Python, accepted tests, fixtures, and lockfiles.

## Required full gate passed

Exact command: `PATH="/Users/matthewbelinkie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" ctx-wire run rtk npm run validate > out/issue-170/npm-run-validate-attempt-6-captured.log 2>&1`

Attempt 6 started at `2026-10-09T03:24:47.807172Z` and finished at `2026-10-09T04:40:37.945537Z` (October 8, 11:24 p.m. through October 9, 12:40 a.m., America/New_York). The supervisor observed the complete command's actual exit status **0**. It retained stdout/stderr directly in a file and saved the status after waiting for completion.

Contract generation/currentness, all TypeScript lint/typechecking/tests, Python lint/formatting/typechecking, and Python tests passed. Test totals were 259 contract tests, one tooling-smoke test, six project-progress tests, 23 roadmap tests, and 369 Python tests. Python tests took 4505.73 seconds.

The exact captured console output is retained byte-for-byte in [full-validation-attempt-6.txt](full-validation-attempt-6.txt). [full-validation.json](full-validation.json) records the actual command status/timestamps, validated implementation commit, log hash, original attempt-5 observations, and executable paths/versions/SHA-256 hashes. Verified tool versions were Node 24.19.0, npm 11.17.0, Python 3.12.14, uv 0.12.5, rtk 0.44.2, and ctx-wire 0.1.71. All six pre-existing pinned artifacts matched their recorded byte lengths and SHA-256 hashes before this documentation update.

## Original pending run and prior attempts

Attempt 5 was allowed to finish without interruption. Its original exec session `46062` was unavailable in this chat, and its ctx-wire reader (PID `63499`) had already exited. A read-only macOS kqueue exit-status observer registered against the surviving processes recorded pytest (PID `64772`) and npm validation (PID `63516`) exiting **0** at `2026-10-09T03:22:37Z`; rtk (PID `63515`) then exited on **SIGPIPE (13)**. The original redirected log `out/issue-170/npm-run-validate-attempt-5-final.log` remained empty. Its actual exit events and empty-log hash are retained in `full-validation.json`; no missing output or outer ctx-wire exit status is inferred. Attempt 6 replaced this output-capture gap with a cleanly captured full gate.

Earlier attempts did not pass: attempt 1 exited 1 on two unchanged Issue #144 tests exceeding Vitest's default five-second timeout; attempt 3 exited 1 on the unchanged `issue-144-omission-bridge.test.ts` timeout (258 passed, one failed; log: `out/issue-170/npm-run-validate-attempt-3-failed.log`); attempt 4 was interrupted with exit 143. No implementation, accepted test, fixture, golden, lockfile, dependency, or timeout setting was changed during this verification continuation.

## Handoff

Full validation evidence is complete. Independent implementation review and integration remain pending; this record does not close or accept #170. No Producer action is required for this Automated-acceptance issue. Do not close #170 or create/push a PR from this implementation task.
