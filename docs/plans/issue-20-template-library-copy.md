# Issue 20 plan — project-scoped external template library and new-project copy

## Objective

Implement the Producer-accepted issue #19 identity, provenance, revision,
authorization, and project-local immutable-snapshot copy semantics as a bounded
in-memory domain service with automated acceptance coverage. The service is the
transactional reference boundary that a later persistence or browser slice can
call; it does not introduce a shared wire contract or UI.

## Scope

1. Validate and register an externally assembled package revision, including
   exact declared bytes, canonical digest identity, provenance, validator
   profile, compatibility, and per-file rights declarations.
2. Atomically attach a valid registered revision to exactly one project's
   template library; invalid, unlicensed, incompatible, unauthorized, and
   duplicate registration attempts create no registry or library entry.
3. Enforce project membership plus explicit capabilities for registration,
   discovery, project-library management, copy-out, and new-project creation.
4. List only exact revisions currently available to the requested project;
   display names and lineage metadata never confer access.
5. Create a new project with None, Some, or All current eligible source
   templates. Freeze exact source revisions, preflight every choice, commit the
   project plus snapshots atomically, and return per-choice evidence.
6. Preserve exact project-owned revision identity for existing uses after
   supersession, retirement, withdrawal, or loss of source-project access.
7. Make successful new-project creation idempotent and reject reuse of an
   idempotency key for a different request.

## Exclusions

- No template design, animation, conversion, generation, repair, or native
  format execution.
- No compiler event, Resolve operation, semantic-input mutation, authoring
  form, browser UI, persistence adapter, object store, or production migration.
- No authentication/role system; callers supply capability grants that the
  service checks at every boundary.
- No shared `/contracts` schema, generated type, fixture, golden file,
  previously accepted test, dependency, or lockfile change.
- No real project, external package, filesystem, research data, or Resolve
  mutation.

## Accepted authority and dependency

- Blocked by #19, which is CLOSED and Done.
- Dependency justification: accepted commit `63114b7` chooses destination-owned
  immutable snapshots, exact revision selection, fail-closed validation,
  independent project authorization/lifecycle, and atomic None/Some/All copy.
- Relevant product-spec authority: immutable dependency revisions; the Phase 9
  `TemplateItem`, `TemplateRevision`, and `GraphicUse` concepts; and the rule
  that newer revisions never rewrite existing uses, checkpoints, or builds.
- Historical implementation progress is context only and authorizes no scope
  beyond issue #20.

## Touched surfaces

- `packages/contracts/src/template-library.ts`: internal domain-service types
  and implementation. Despite the existing workspace package name, this does
  not change or generate any shared JSON schema.
- `packages/contracts/test/template-library.test.ts`: slice-owned automated
  acceptance tests using synthetic package bytes and projects.
- `packages/contracts/package.json`: exports the internal module.
- This plan and the issue #20 Producer acceptance handoff.

## Test-first verification

1. Add failing tests for valid registration and scoped listing; malformed,
   unlicensed, incompatible, duplicate, and unauthorized intake; name-based
   non-access; None/Some/All copy; failed-copy atomicity; idempotency; and
   retained revision resolution after lifecycle/source-access changes.
2. Implement only enough internal service behavior to pass those tests.
3. Run the focused TypeScript tests, lint, typecheck, `git diff --check`, frozen
   boundary audits, and the full pinned `npm run validate` gate.
4. Reinspect #20 and move it only to In review with the exact commit and test
   evidence. Producer acceptance remains authoritative.

## Producer acceptance outline

The handoff will name the focused test command and exact test cases that exercise
registration, scoped listing, None/Some/All creation, fail-closed atomicity,
authorization, and retained revision identity. The Producer will run the
command, inspect the readable assertions/report objects, and respond with the
specified acceptance or failure sentence. Issue #20 remains In review until
that response is recorded.
