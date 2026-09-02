# Issue 38 plan — production public-page capture schemas and migration

## Objective

Produce the bounded, Producer-reviewable contract-change and persistence
migration proposal required by GitHub issue #38. The proposal translates the
Producer-accepted #27 lifecycle/security contract and #28 isolated-capture
evidence into exact shared JSON-schema, PostgreSQL, REST, worker-capability,
atomic-publication, recovery, and test boundaries for later issue #39.

This issue changes documentation only. It neither changes a shared contract nor
authorizes a migration or capture execution. Producer acceptance of this issue
is the explicit contract-change approval that issue #39 must follow without
additional schema invention.

## Authority and accepted inputs

- GitHub issue #38 and the VERA roadmap are the live scope, routing, ownership,
  dependency, and review authority. The issue was Ready, dependency-free,
  unclaimed, and exactly routed to Sol/xhigh before this task claimed it.
- `docs/investigations/issue-27-webpage-capture-contract.md` at accepted commit
  `9143518` supplies the binding identities, cardinalities, authorization,
  public-only trust boundary, provenance, idempotency, lease, failure,
  deduplication, change-signal, selection, protection, retention, and deferred
  Periodic decisions.
- Accepted issue #28 commits `47a3569` and `fcdea1c`, its issue evidence,
  `docs/investigations/issue-28-isolated-public-capture.md`, and
  `spikes/public-capture/` prove bounded offline mechanics: fresh Chromium
  contexts, no imported cookies, immutable revisions, exact-byte artifact
  reuse, atomic local publication, lost-response recovery, and fail-closed
  crash/security behavior. Synthetic DNS/peer evidence, macOS Seatbelt, and the
  offline fixture transport are evidence, not production authorization or live
  egress guarantees.
- The product specification supplies the immutable artifact/build rules,
  project roles, trusted local-agent boundary, PostgreSQL/REST/object-storage
  architecture, Phase 5 public-page behavior, visible failures, and the
  section 14 stale-capture trigger for any future scheduled monitoring.
- `docs/IMPLEMENTATION_PROGRESS.md` is historical acceptance context only; it
  is not used as a live ownership or status source.
- Issue #39 is the already-bounded implementation follow-up. It remains
  unclaimed and dependency-blocked by open issue #38.

## Scope

1. Name the exact new versioned JSON-schema roots and generated TypeScript and
   Python surfaces proposed for issue #39, without editing `/contracts` or
   generated files here.
2. Define the minimum PostgreSQL records, columns, lifecycle projections,
   append-only evidence, composite foreign keys, uniqueness, checks, indexes,
   immutability protections, and project scoping needed by #27.
3. Define sanitized human/API REST messages and a separate narrow local-worker
   protocol, including project authorization, idempotency, lease epochs,
   staging capabilities, provenance access, and nonrevealing errors.
4. Define one atomic logical publication boundary across immutable object
   staging and PostgreSQL, including same-byte races, late commits, conditional
   selection, build pins, partial publication, and lost responses.
5. Define additive migration, activation, compatibility, fail-closed rollback,
   generated-type, fixture, golden, and acceptance implications.
6. Map every accepted #27 invariant to a schema, API, database constraint, or
   explicit deferral and specify adversarial verification for every threat class
   named by #38.

## Exclusions

- No edit to `/contracts`, generated TypeScript/Python, existing fixtures,
  goldens, accepted tests, application code, manifests, lockfiles, or
  dependencies.
- No PostgreSQL database, API route, object store, job queue, worker, browser,
  live network, deployment, UI, scheduler, notification, OCR, Spotlight,
  motion, compiler, Resolve, or retention/deletion implementation.
- No authenticated/paywalled capture, attached browser, cookie/profile import,
  source-product credential, query secret, production URL, production locator,
  private project record, or real external capture.
- No material-change semantics, automatic revision replacement, periodic
  frequency/timezone/retry policy, numeric retention policy, pruning,
  tombstoning, or destructive rollback.
- No new roadmap issue or dispatch. Existing issue #39 is identified only as
  the dependency-blocked implementation handoff.

## Slice boundary before writing

- Roadmap dependencies: `None`.
- Touched shared contracts: none; the investigation proposes three future v1
  roots for explicit Producer approval.
- Touched fixtures or golden files: none.
- Touched application/infrastructure code: none.
- New dependencies: none.
- Planned issue artifacts: this plan and
  `docs/investigations/issue-38-production-capture-schema-migration.md` only.
- Dependency justification: none. #27 and #28 are accepted evidence rather than
  unresolved dependencies; issue #39 is downstream and remains blocked by #38.

## Decision tests

Reject or explicitly defer any design for which the answer to one of these is
wrong:

1. Can a URL, object key, path, digest, job ID, revision ID, or renderer-visible
   record grant access without current project authorization? It must not.
2. Can one job commit two revisions, one lease authorize two attempts, or a
   late epoch commit after lease loss? It must not.
3. Can identical bytes merge observation time, provenance, revision identity,
   selection, protection, or audit evidence? They must not.
4. Can an object-store or database failure expose a partial revision, or can a
   lost response cause a logically new job? It must not.
5. Can a recapture, selection, pin release, rollback, or migration edit or
   remove an earlier revision, artifact, checkpoint/build reference, or audit
   event? It must not.
6. Can page content reach a private/local/metadata peer, inherit ambient state,
   escape resource limits, or receive a hosted/user/object-store credential?
   It must not.
7. Can a reserved Periodic value create a job, lease, timer, scheduler record,
   notification, retention decision, or deletion? It must not.
8. Does the proposal depend on the pending browser presentation, OCR/Spotlight,
   Resolve, or broad collaboration persistence to be safe? If yes, the behavior
   is outside #38.

## Verification

1. Cross-reference every #27 section and numbered cardinality invariant against
   a named contract, table constraint, endpoint rule, or explicit deferral.
2. Compare each production seam with #28 evidence and label every spike-only
   assumption that issue #39 must replace or retain only as a test adapter.
3. Verify the proposed contract-change ledger states compatibility, generated
   types, migration/rollback, fixture/golden effects, and acceptance impact.
4. Check that examples use only reserved fictional hosts/identities and contain
   no secrets, cookies, private addresses as eligible targets, real object
   locators, or production data.
5. Run `git diff --check`, inspect the complete diff, and confirm only the two
   issue #38 documentation artifacts changed.
6. Confirm the diff is empty for `/contracts`, `/fixtures`, generated types,
   existing test data/goldens, dependency manifests/locks, and all application
   and infrastructure code.
7. Run the repository's pinned `npm run validate` gate.
8. Reinspect issues #38 and #39, commit/push the bounded artifacts, and move
   only #38 to `In review` with concrete evidence. Never move it to `Done` and
   never promote, claim, or dispatch #39.

## Producer acceptance outline

The final handoff will direct the Producer to the exact investigation sections
for the contract-change ledger, fictional end-to-end trace, database
constraints, worker/API boundaries, atomic commit/recovery algorithm,
threat-model tests, migration/rollback, and deferred features. Every step will
name the expected safe result and the exact acceptance or failure response.
Issue #38 remains `In review` until the Producer explicitly accepts it.
