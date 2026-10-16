# CN-218-A2 verification and failed fast-run disposition

Candidate `bb534bd191bedbc566f95560a0482e927826eae0` applies the approved
two helper edits. All four affected slow modules ran serially: **163 passed**
in 573.08 seconds. Raw log and atomic sequence result are retained here.

The following `VITEST_MAX_WORKERS=1 npm run validate:fast` **failed**, with
540 contract tests passing and five existing 5000ms timeout failures in
issue-144-omission-bridge, issue-144-proof-cli and issue-192-v2-integration.
No assertion or semantic diagnostic failed. The contract run took 216.65s,
compared with 61.80s for the same contract source/test inventory during the
earlier full attempt. This does not turn the failed run green.

## Verified TypeScript evidence reuse

Under `docs/VERIFICATION_POLICY.md`'s evidence-equivalence rule, retain and reuse
the completed passing TypeScript/generated-currentness evidence at `04d5abc`:
the complete passing fast run is `fast-04d5abc.log.gz` and its exit-zero result;
the earlier full attempt additionally completed the TypeScript stage with
545 contract tests, one tooling test and 6/23/32 progress/roadmap/cloud tests.
Its later Python failure remains failed acceptance evidence.

Compared the 7,048-file pre-full inventory at `04d5abc` against the current
tracked inventory. All contract/schema, TypeScript source/test, generated
code, assets, original fixtures/goldens, scripts/configuration and locks match.
Only the approved two Python helper files and enumerated plan/receipt/evidence
files differ. Node 24.19.0, npm 11.17.0, uv 0.12.5, Python 3.12.14, Darwin Intel,
installed lock/venv metadata and inherited check options match. The existing
single-worker profile is unchanged. Raw local inventories and the exact
comparison are retained under `out/issue218/`.

Read the check targets and searched source for the changed paths: TypeScript
lint/types use scripts/packages, generation reads fixed `/contracts` roots,
compiler tests read named fixture files, and dashboard/roadmap/cloud tests use
their named inputs or temporary test repositories. None reads the changed
Python helpers or new #218 evidence/plan files. No matching references exist
in packages/scripts, including an explicit no-ignore retry. The limited
directory reads found operate on temporary outputs or package controls.
Thus those changed files are not TypeScript check inputs. No source change
can explain this run's TypeScript slowdown; host contention was independently
observed (load averages 4.10/4.83/5.64 and several other active applications).
Do not kill or alter those unrelated processes. No timeouts are increased.

Fresh Python lint/types/non-slow checks on the approved helper state follow;
the earlier 163 affected slow passes provide changed-behavior coverage.
Claude must audit this reuse/failure disposition along with the helper delta.
No new full validation is authorized: the Producer explicitly paused before
that gate, and issue #218 remains open.
