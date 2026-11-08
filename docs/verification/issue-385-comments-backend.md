# #385 — Anchored comments backend verification (2026-11-08)

## Scope and proof level

**Synthetic backend evidence only.** This review verifies typed-document/anchored-comment
storage, independent PostgreSQL concurrency, authenticated QA API/host tests, and the
existing frozen-build/agent manifest boundary. It does **not** claim a native Resolve
run, deployed multi-user UI, external identity provider, provider notification,
local-agent execution, or a Producer-media test.

Implementation boundaries are in
[`docs/plans/issue-385-comment-service.md`](../plans/issue-385-comment-service.md).
The only issue dependencies are #379 and #380. Browser discussion UI belongs to #74.

## Directly observed test evidence

| Command or check | Observed result | What it proves |
| --- | --- | --- |
| `npm run test --workspace @vera/project-documents -- test/comment-input.test.ts test/comments.test.ts test/comments-document.test.ts test/api.test.ts test/migration.test.ts test/service.test.ts` | **40/40 passed, six files** | Trusted actor stamping, four anchor shapes, mention bounds, inactive/cross-project/disabled members, role revocation, CAS/replay and 409 conflicts, immutable events, checksum/replay corruption refusal, explicit stale reattachment, atomic document updates/rollback, HTTP boundaries and migration checks |
| `VERA_PROJECT_DOCUMENTS_TEST_DATABASE_URL=<disposable local PostgreSQL> npm run test --workspace @vera/project-documents -- test/postgres.integration.test.ts` | **2/2 passed, real PostgreSQL 16** | Independent connections serialize competing document writes, two first comment creations, concurrent replies, document/comment writes and rechecked revocation. Exactly one of each same-CAS pair commits; surviving head/revision/event counts and state digest reconcile |
| `npm run test --workspace @vera/project-builds -- test/submission.test.ts` | **14/14 passed** | An authenticated Editor stores an anchored thread plus reply and active-member mentions; the unique comment sentinel exists in durable comment state. Builds created before and after contain identical exact live typed-document JSON and document digest. Frozen payload and authenticated, leased agent manifest exclude the comment sentinel |
| `npm run lint --workspace @vera/project-documents && npm run typecheck --workspace @vera/project-documents && npm run lint --workspace @vera/project-builds && npm run typecheck --workspace @vera/project-builds` | **Passed** | Static checks for changed service/test packages |

The build regression obtains the real `ProjectCommentService` state and positive-checks
that a unique comment-body/reply sentinel is present in `stt_comment_heads.state_json`.
It then reads `stt_build_submissions` via the guarded `loadFrozen`, checks the exact
`stt_document_heads.document_json` and its SHA-256 digest on both sides of the
comment writes, and reads the `ProjectBuildStatusService.frozenForAgent` manifest
under a genuine synthetic pairing/lease. The agent manifest and public status readback
are also negative-checked for the sentinel. A separate build target is minted for
each submission, so its *snapshot* digest legitimately differs even when source
document bytes are identical; replay of the first idempotency key must retain its
original snapshot digest. The existing contract consumer tests separately ensure
compiler, prompter, projection and media needs are unchanged by comment operations.

## Adversarial / reversible guard mutations

With the original file backed up byte-for-byte for every mutation, each variant
ran its named focused test before restoring the original bytes. **Six of six**
deliberate guard regressions produced failing tests; every touched source file
was restored byte-identically:

| Defeated guard | Detecting test |
| --- | --- |
| Authorize comment mutation as a viewer action | `comments.test.ts` — refuses Viewer writes and cross-project reads/writes |
| Admit an inactive same-project mentioned actor | `comments.test.ts` — refuses inactive same-project mention |
| Invert expected comment-revision CAS | `comments.test.ts` — original receipt and stale CAS |
| Disable stored comment state digest comparison | `comments.test.ts` — corrupt checksums and replay refusal |
| Permit reattachment of a non-stale thread | `comments.test.ts` — rejects already-attached reattachment |
| Skip document PUT's same-transaction comment reconciliation | `comments-document.test.ts` — stale exactly once and explicit reattach |

**Found and fixed during PostgreSQL verification:** A competing comment creation
originally surfaced `503` instead of the expected stale-CAS `409`, because the
comment service caught a PostgreSQL serialization conflict and converted it to
`service_unavailable` before the bounded outer retry. `ProjectCommentService`
now propagates `40001`/`40P01` and the typed serialization error from its inner
read/write guards; the whole authorized transaction is retried. Re-running
the disposable two-test PostgreSQL suite passed. This race was *not* detectable
with one-connection PGlite tests alone.

## Persistence and fail-closed guarantees

- Migration `002_stt_project_comments.sql` adds only separate authoring heads
  and append-only client-operation events, with checksum receipt and a strict
  QA-host table allowlist. `001` remains unchanged.
- Document PUT and client comment writes lock the same document row first, and
  persist compatible revisions in one authorized SERIALIZABLE transaction.
  Internal document replacements create no client event and never silently
  reattach stale threads.
- GET returns a narrow `{ projectId, documentRevision, commentRevision, threads }`
  view, not the replay history containing prior complete typed documents.
  HTTP authenticates before reading or parsing a request, caps actual body
  bytes, and rejects unauthorized tenants/operations.
- Historical authors and mentions persist after membership revocation, but
  revoked actors cannot read, write, or reuse a formerly successful key.
  Malformed, stale or tampered state fails closed, with no reset/backfill.

## Limits and remaining checks

Independent PostgreSQL testing used a throwaway local database and synthetic
suite principals. It does not establish production throughput, malicious
database-superuser resistance, or an end-to-end running QA-host session.
`activeDraft.blocks` alone are currently anchorable; Ideas/Extras anchors,
CRDT relative positions, notifications and browser UI remain out of scope.
No local-agent or Resolve process was launched and no private Producer data
was read. CI, PR review and merge remain conductor-owned after handoff.
