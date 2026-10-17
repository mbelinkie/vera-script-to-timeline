# Pre-review evidence (not final acceptance)

Accepted integration baseline f4df73e plus retained compatibility patch passed
isolated types and107foundation/#144 regressions. CN-218-A1 at1a7cb50 was
explicitly approved in this owning chat; exact two guards are applied.

`VITEST_MAX_WORKERS=1 npm run validate:fast` exited0, log retained locally at
out/issue218/validate-fast-serial.log; managed session9564 returned exit0.
Input inventory captured for that run matches afterward with no differences.
Generated contracts current; TypeScript lint/types,534contracts+1tooling tests,
progress/roadmap/cloud tests; Python Ruff/format, mypy158files;657non-slow
Python tests passed in314.06s with two workers. Node24.19.0/npm11.17.0 and
Python3.12.14 frozen locks. Full acceptance has not run.

Earlier attempts remain failed: one lint finding fixed; a default parallel
Vitest run hit five existing5000ms test limits. The unchanged timeout/assertion/
inventory gates passed under the existing single-worker profile. No timeouts
were relaxed. Retain raw local logs validate-fast.log and validate-fast-fixed.log.

After the passing fast run, bounded read-only inspection identified two missing
core edge checks: legacy address UUID validation and unknown-format ID collision
refusal. Both are fixed; the two owned suites pass35tests on this source
(13core+22compiler). They change only the pure core and its new test. Fresh fast
validation follows for the review candidate; its result must be added before
review/full acceptance. Original frozen fixture/test boundary audit remains
unchanged. No claim of full validation, native runtime, merge or deployment.
