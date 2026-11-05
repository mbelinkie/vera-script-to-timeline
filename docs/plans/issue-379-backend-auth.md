# Issue #379 — backend project authorization (implementation record)

Concise record of contracts, ownership, call sequences and failure modes for
`packages/project-authorization`. This documents what shipped; it is not a new
process gate.

## Boundaries

- **Suite identity** is the only trusted authentication source. The app layer
  implements `SuiteIdentityPort.authenticate(request) -> {issuer, subject}` and
  calls `authenticateRequest()` per request. This package never reads
  identity, role, or Research links from client-supplied fields.
- **This package** maps a verified issuer+subject to an immutable actor UUID
  (`resolveActor`), checks current DB membership per request, and provides
  `withAuthorizedMutation`, `openWriteSession`, `changeMembership`, and
  `provisionFirstProducerInProjectTransaction`.
- **#380** owns project/document endpoints and MUST run every persisted
  mutation through `withAuthorizedMutation` (same transaction, row lock). It
  calls `provisionFirstProducerInProjectTransaction` only inside its own
  authenticated new-project transaction, after inserting the STT project.
- **A future socket host** LISTENs on `vera_membership_changed` but must still
  recheck membership per message; NOTIFY is a prompt, not a security boundary.
- **Research** is a separate authorization domain. `read_research` is not in
  the closed matrix; a linked Research ID grants nothing here.

## Tables (owned by this package's migration `vera_project_identity_membership_001`)

`vera_identity_actors` (immutable UUID per issuer+subject, `disabled_at`),
`vera_project_members` (project_id, actor_id, role, active, version),
`vera_project_write_sessions` (revoked_at, membership_version),
`vera_project_membership_audit` (append-only via trigger). Reuses the existing
`vera_schema_migrations` shape; does not alter the capture migration's schema.
`project_id` is an external UUID until #380's project persistence adds an FK.

## Call sequence (happy path)

1. `authenticateRequest(request, suiteIdentity)` -> actor `PrincipalRef`.
2. `authorizeRequest(projectId, principal, action, sessionId?)` -> decision;
   every call re-reads the DB (`recheckMode: "every_request"`).
3. Mutations: `withAuthorizedMutation(projectId, principal, action, op)` runs
   the permission check (`FOR SHARE`) and `op(db, actorId)` in one SERIALIZABLE
   transaction; a concurrent `changeMembership` (`FOR UPDATE` + project
   advisory lock) serializes after it. Consumer operation errors propagate
   unchanged; only this service's own DB failures become 503.
4. `openWriteSession` requires `edit_document`; sessions bind
   `membership_version`. Any role change/revoke bumps `version`, revokes open
   sessions in the same transaction, writes the audit row, and `pg_notify`s
   after commit. A stale session fails on next check (revoked -> 403, version
   mismatch -> 409).
5. SERIALIZABLE aborts (40001) and deadlock-victim aborts (40P01) surface as
   `ProjectSerializationConflictError` (`retryable: true`); consumers retry
   the whole mutation with bounded attempts and idempotent side effects.

## Capture service integration

The commit flow was re-checked and tightened: `ProjectAuthorizationPort`
gained an optional `authorizeInTransaction(client, ...)` variant, and
`commitAttempt` now rechecks `capture_commit` (and conditional
`capture_select`) on the publish transaction's own client, taking `FOR SHARE`
locks on the membership row. The decision and the published revision commit
atomically; a revocation either lands before the check (commit refused) or
serializes after the publish. This requires the membership tables and the
capture tables to share one PostgreSQL database, which matches the deployment
plan. The capture API boundary maps `ProjectAuthError` codes/statuses onto
the existing closed error contract (401/403/409/503) instead of the generic
fallback.

## Failure modes

- Missing/forged suite identity -> `authentication_required` 401; DB down ->
  `authorization_unavailable` 503; unknown action/role, non-UUID IDs, absent
  or inactive membership, unknown target actor, disabled actor ->
  `action_not_allowed` 403. Fail closed everywhere; no anonymous actor, no
  wildcards.
- Last active Producer cannot be removed or demoted (denied). Demotion of the
  last Producer requires promoting another Producer first.
- Migration is digest-checked; a tampered record aborts. Audit rows cannot be
  updated or deleted.

## Local test evidence (see test files)

- `packages/project-authorization/test/authorization.test.ts`: 23 tests,
  including revoke-after-session, last-Producer protection, disabled actor
  re-sign-in, unknown-actor refusal, tampered migration, append-only audit,
  same-connection LISTEN/NOTIFY payload, same-transaction rollback, consumer
  error passthrough, serialization-conflict mapping at both COMMIT and the
  locked permission query (PostgreSQL 40001 and 40P01), and the
  same-transaction `authorizeInTransaction` check. The locked-check regression
  failed before the fix (503 instead of retryable conflict) and passed after.
  Independent Linux container run on 2026-11-05: 23 passed with
  `--testTimeout=30000`; at the default 5000 ms timeout, 15 PGlite-backed
  tests timed out under this container's CPU constraints, not on assertions.
- `packages/public-page-capture/test/authorization-integration.test.ts`: 7
  tests proving the service structurally satisfies the existing
  `ProjectAuthorizationPort`, drives real create/queue/commit flows (shared
  database), refuses commit after revocation with nothing published, and maps
  refusals to closed API errors at the HTTP boundary.

## Proven but not proven

- PGlite (single connection) proves ordering and transactionality, NOT
  cross-process timing; a live PostgreSQL LISTEN fanout and bounded retry for
  SERIALIZABLE conflicts belong to #159/#72 consumers.
- `release_build` here is the role check only; the approved-checkpoint
  precondition stays a consumer gate in the build/checkpoint service.
