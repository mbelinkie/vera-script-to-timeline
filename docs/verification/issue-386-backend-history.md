# Issue #386 — attributed history, checkpoints, restore-as-new-head verification

Backend-only Phase 3.4B, checked in the locked pipeline worktree. This evidence is
for synthetic authorization/SQL/HTTP behavior, **not** browser design, Resolve,
production migration, or an end-to-end release-build approval gate.

## Implemented contracts and boundaries

- Forward-only project-history migration 003 adds immutable named checkpoint,
  Producer approval and restore-provenance tables after identity, documents 001
  and comments 002. Existing migrations and retained revisions remain intact.
  The QA host registers a checksum-pinned receipt and extends its table allowlist.
- Attributed 0..N revision reads, page cursors and deterministic typed semantic
  comparisons use saved project-scoped, digest-verified snapshots; comparison
  results are bounded at 200 changes with total/truncation metadata.
- Editor+ creates checkpoints; only Producer approves. Authorized Viewer may
  inspect immutable history and approval labels. Session/membership revocation
  is checked before mutation receipt replay.
- Restore takes checkpoint bytes from the immutable database source and, in an
  authorized SERIALIZABLE transaction, appends a **new** attributed revision,
  appends provenance and CAS-updates the live head. Comment reattachment is in
  the same transaction. Neither historical rows nor approval status are
  rewritten or silently inferred. Cross-operation mutation keys are guarded.
- Strict JSON/API methods reject anonymous, foreign, malformed, oversized and
  extra-field inputs; old document/settings/build HTTP behavior is retained.

## Executed test evidence

All commands ran in the requested pipeline worktree; retained detailed logs
reside in `.pipeline/386` (not in Git). This source review covered the whole
issue diff (service, model, migration, semantic comparison, API, host and tests).

- Earlier phase-4 verification: restored PGlite service/API suite **13/13
  PASS**, independent disposable PostgreSQL **3/3 PASS**, host routing
  regressions **9/9 PASS**, project-documents typecheck/ESLint PASS. Logs:
  `phase4-focused.log`, `phase4-postgres.log`, `phase4-host.log`.
- Phase-5 `VITEST_MAX_WORKERS=1 npm run validate:fast`: generated contracts,
  TypeScript lint/types/tests, Python Ruff and MyPy **PASS** (contracts
  **1246/1246 PASS**). Python tests **27 failed, 2873 passed, 43 skipped**;
  complete gate **exit 1** (654.793s). Full output:
  `phase5-validate-fast.log`. Failed Python areas include narration/ffmpeg,
  word timing, issue-182 report CLI and issue-208 native target-identity/
  approval behavior. No Python files were modified in this issue; a clean-main
  comparison is documented below.
- Phase-5 reversible mutations (one at a time): **6/6 expected targeted test
  failures**, with assertion failures, not mere startup failures. Mutations:
  checkpoint create role → Viewer permission; Producer approval role → Editor
  permission; skip checkpoint SHA check; bypass restore head-CAS result guard;
  bypass restore idempotency digest guard; bypass historical SHA check.
  `phase5-mutations.log` retains command/test/stack output. A first
  machine-readable summary misclassified colored output; a subsequent
  ANSI-stripped audit verified all six real failing assertions. The
  original service.ts bytes were restored and `git diff HEAD --` was empty.
- After restoring each mutation, phase-5 focused command
  `npm exec --workspace @vera/project-documents -- vitest run
  test/migration.test.ts test/semantic-diff.test.ts
  test/history.service.test.ts test/checkpoint.test.ts test/restore.test.ts
  test/api.test.ts --maxWorkers=1` **PASS 38/38 (six files, exit 0)**.
  Log: `phase5-focused-green.log`.
- On an isolated throwaway PostgreSQL database,
  `VERA_PROJECT_DOCUMENTS_TEST_DATABASE_URL=<scratch>
  npm exec --workspace @vera/project-documents -- vitest run
  test/postgres.integration.test.ts --maxWorkers=1` **PASS 3/3
  (exit 0)**, including concurrent restore-vs-PUT, two restores,
  and the retained document/comment race regressions. Log:
  `phase5-postgres.log`.
- An independent clean-main archive made from `origin/main` at
  `016a41fb` reproduced **2/2** known Python failures in a three-case
  representative run (`phase5-clean-main-baseline.log`): narration CLI
  and cloud word-timing both lack the system `ffmpeg` executable;
  the tested issue-208 target case passed alone. These two baseline
  failures are proven unrelated to #386, but that isolated selection does
  not alone establish the origin of all 27 fast-gate Python failures.

## Independent review disposition

The required **single** `npm run review -- notes.md` attempt exited before
review, because a simultaneous `origin/main` update caused its `git fetch`
to fail with a ref-lock compare-and-swap error. A direct read-only Claude review
fallback also exited without review: the account had reached its weekly usage
limit. No independent reviewer findings or approval are claimed. Logs:
`phase5-independent-review.log` and
`phase5-independent-review-fallback.log`. An adversarial self-review of all
new code/tests and backward-compatibility paths found no additional confirmed
issue; the normal CI/PR review is still required before merge.

## Limits and follow-up integration

- Project builds currently consume the live document head; approval labels in
  this backend do **not** establish the downstream approved-checkpoint gate for
  release builds. That remains integration work outside #386; the user-facing
  comparison/checkpoint UI remains #75.
- Test databases contain synthetic fixtures only. No native Resolve, Research
  integration, production data migration, deployment, or full `npm run validate`
  was attempted. Python fast-gate failures and unavailable independent review
  remain explicitly disclosed for the merge decision.
