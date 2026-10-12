# Issue 20 Producer acceptance — external template library and new-project copy

Issue #20 must remain **In review** until the Producer records the exact
acceptance response at the end of this checklist. The automated gate proves the
transactional domain behavior with synthetic bytes and projects; the Producer
judges whether the readable flow matches the accepted issue #19 policy.

## Automated evidence to reproduce

From the repository root on the issue branch, run:

```sh
rtk npm ci
rtk npm run test --workspace @vera/contracts -- test/template-library.test.ts
rtk npm run validate
```

Expected results:

- the focused file reports 15 passing tests;
- the full repository gate reports generated contracts current, TypeScript
  lint/typecheck/tests passing, and Python lint/typecheck/tests passing; and
- no command touches a real template, project, research asset, or Resolve.

## Producer judgment steps

1. Open `packages/contracts/test/template-library.test.ts` and review the first
   `describe` block, **issue #20 external template registration**.
   **Expected:** a valid manifest plus exact synthetic bytes creates one
   digest-pinned project revision. Malformed hashes, missing rights,
   incompatibility, duplicate bytes, and missing authority each return a named
   visible failure while the state-count assertions prove no partial entry.
2. Review the test **does not infer discovery access from a matching template
   name**.
   **Expected:** two projects may have the same visible name, but an actor with
   Project A grants can list only A and receives a nonrevealing denial for B.
3. Review the None, Some, and All tests in the second `describe` block.
   **Expected:** None creates an empty project explicitly; Some copies only the
   selected exact revisions into new destination-owned IDs; All copies the
   current eligible set and reports a withdrawn non-current revision as an
   exclusion rather than silently substituting it.
4. Review **reports duplicate and unavailable Some choices and creates no
   project or association** and **denies unauthorized source and destination
   combinations before creating a project**.
   **Expected:** every requested exact choice is preflighted; duplicate,
   withdrawn, unauthorized, or destination-rights-denied input returns readable per-choice findings; the
   before/after counts and `hasProject` assertion prove atomic failure.
5. Review the idempotency test.
   **Expected:** retrying the exact committed request returns the same logical
   destination and does not add rows; reusing its key for changed input fails.
6. Review **keeps exact uses and copied snapshots reproducible...**.
   **Expected:** the original use still resolves to its exact R1 digest after R2
   supersedes it and the source item/revision is retired/withdrawn. An actor
   with destination-only grants still sees the copied destination revision,
   proving source access and lifecycle were not inherited.
7. Open `packages/contracts/src/template-library.ts` and inspect the exported
   `TemplateLibraryService` boundary.
   **Expected:** it is an in-memory, persistence-agnostic reference service;
   performs no filesystem, network, compiler, Resolve, or real-project action;
   and retains capabilities, exact package/revision IDs, per-project
   ownership, copy evidence, lifecycle state, and append-only audit events.
8. Confirm the diff contains no change under `/contracts`, `/fixtures`,
   `tests/data`, generated types, accepted tests, dependency manifests, or
   lockfiles, and no template design/conversion, compiler, Resolve, UI, or
   migration implementation.

## Response that records the decision

- Acceptance: `Accept issue #20 project-scoped external template library and new-project immutable-copy implementation.`
- Failure: `Issue #20 acceptance failed at checklist step <number>: <observed mismatch>.`

Do not mark issue #20 Done from automated evidence or agent self-report.
