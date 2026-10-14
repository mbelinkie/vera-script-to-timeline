# #192 first focused set — completed, not acceptance

Producer directly resumed this chat on 2026-10-13. The coordinator confirmed
the retained sole-local-heavy reservation and first focused set. Usage at
resume was 2% five-hour / 47% weekly on account
76e395df-e4f8-4a1a-a63b-3de3fb5abca5; no reset or credit was used. The previous
97% stop remains historical evidence. No competing validation/pytest/media
process was found before this set.

The tested source is parent a97b370 plus the exact working changes pinned in
`focused-first-set.json`. That index retains commands, timestamps, completed
exit codes and log/receipt hashes for all 21 attempts. Full scrubbed logs and
input/tool/environment receipts remain in this checkout's ignored
`out/issue192/focused-*` directories. No failed attempt is a passing gate.

## Results and fixes

| Check | Evidence |
| --- | --- |
| Contracts TypeScript types | Initial focused-1 passed; fresh focused-7 passes after the inference correction |
| ESLint, five new #192 TypeScript files | focused-2 failed four rules; focused-3 passes; focused-6 passes for the later changed source |
| Single-worker #192/#202 Vitest | focused-4: 30 passed, five failed; unchanged #202 file passes all 10 tests. After the fix, focused-5 passes all 25 #192 tests |
| Own frozen Python setup | focused-8: `uv sync --frozen --python 3.12.14`, exit zero, 47 installed packages, lockfiles unchanged |
| Ruff, seven new/delegated Python files | focused-9/10/12 failures retained; focused-13 passes. Later changed test helpers pass focused-19 |
| Ruff format | focused-14 passes all seven; focused-20 found one missing blank line; focused-21 passes that final delta |
| Strict mypy | focused-15 reports 33 errors only in three new test files; four other selected files have no diagnostics. focused-16 failed because the narrowed invocation resolved the installed untyped package. Correct source resolution (`MYPYPATH=python`) in focused-18 passes all three affected test files and their followed source imports |

The composition failure was a real integration error: the preliminary A/B
document-identity stage received C's prepared-media replacement before the
omission affected that row. That preliminary stage now receives no media;
the complete A/B/C stage still checks and applies every replacement through
the unchanged #202 core. Actual-duration cases 187, 200 and 213, source-handle
refusal and stale-handoff negatives now pass without assertion changes.

Python changes organize imports, wrap lines/literals, remove unused imports,
and type the new JSON/test-helper values. Dynamic instance replacements remain
explicit test doubles; transport tests still cannot supply genuine combined
acceptance. Native source formatting has an identical Python AST to its
pre-format a97b370 version. No initial native guard/effect was changed by this
focused fix. All changed paths are owned siblings or the approved delegated
native hook. `git diff --check` passes. Contracts, fixtures and generated
contracts are byte-identical to accepted #190 baseline bd6048.

## Evidence reuse and remaining gates

TypeScript inputs are unchanged since focused-7 and focused-5 respectively;
Python-only formatting/test-helper changes do not enter these TS checks. The
#202 core/test and every dependency manifest/lock remain unchanged. The final
Python blank-line change has no AST effect; affected format evidence is fresh.
This is focused delta evidence, not a full gate or a claim that the initially
failing seven-file mypy command passed.

Native/proof source hashes changed, invalidating earlier precomputed packages,
bindings and receipts. Rebuild them through public APIs on the final combined
source; do not patch prior hashes. The final source pins are in the index.

Not started: Python runtime tests (including public B1/B3 path), global fast or
full validation, adversarial/Claude review, real native/provider/media work.
The next serial focused Python runtime set needs the coordinator's separate
grant. #202 actual accepted dependency state remains to be confirmed; no
Ready claim, PR, merge or closure is authorized by these focused results.

Producer walkthrough remains pending: review exact A/B/C/D results, immutable
before/after comparison, measured fresh-row placement, preserved prior target,
truthful native refusal, discrepancy and read-only recovery. #178/#145 retain
their separate real application, provider, listening and visual gates.
