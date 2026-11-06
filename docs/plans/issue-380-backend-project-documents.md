# #380 — Backend project setup and durable typed document storage

Scope: new `@vera/project-documents` workspace. No browser UI, hosted API server,
identity provider, Research access, local companion, Resolve, media, or migration
of existing v1 projects. #379's `ProjectAuthorizationService` owns identity,
membership, roles and write-session revocation; this service shares its **same**
PostgreSQL pool. Deployed Postgres, backups and secrets remain with #159.

## Contract and endpoint boundary (package-local HTTP v1)

All requests use JSON with a hard 512 KiB request-body limit, and all responses
use JSON, `Cache-Control: no-store`, and `X-Content-Type-Options: nosniff`.
Trusted suite authentication is checked **before** any request-body parsing;
without a configured `SuiteIdentityPort`, even syntactically correct requests
fail 401. The adapter must never trust issuer, subject, actor, role, or Research
IDs from user-controlled JSON/headers. Unknown input properties are rejected.

| Method | Route | JSON input | JSON output |
| --- | --- | --- | --- |
| POST | `/v1/projects` | `{clientRequestId: UUID, projectId: UUID, title: string, document: ScriptDocumentV2, settings?: AuthoringProjectSettingsV1}` | `{project, documentRevision, documentDigest, duplicateDelivery}` (201 new, 200 replay) |
| GET | `/v1/projects/{id}` | none | `{project}` |
| PATCH | `/v1/projects/{id}` | `{expectedProjectVersion,clientMutationId:UUID,title}` | `{project,clientMutationId,duplicateDelivery}` |
| GET | `/v1/projects/{id}/document` | none | `{projectId,revision,digest,document}` |
| PUT | `/v1/projects/{id}/document` | `{expectedRevision,clientMutationId:UUID,document,writeSessionId?:UUID}` | `{projectId,clientMutationId,revision,digest,duplicateDelivery}` |
| GET | `/v1/projects/{id}/settings` | none | `{projectId,settingsRevision,digest,settings}`; 404 if not configured |
| PUT | `/v1/projects/{id}/settings` | `{expectedSettingsRevision,clientMutationId:UUID,settings}` | `{projectId,clientMutationId,revision,digest,duplicateDelivery}` |

`project` contains only `{projectId,title,projectVersion,linkedResearchProjectIds:[]}`.
The API does not link a Research project or add any Research permission. `id`
in routes is the STT project UUID. New projects require a complete *caller*
provided v2 document; the backend never fabricates a collaboration hash or a
new blank typed document. Existing v1 documents are not converted.

Successful saves and idempotent replays are HTTP 200. Auth failures are 401
(untrusted/missing identity) or 403 (membership, role, disabled actor or
revoked session), invalid JSON/schema/IDs/revision keys are 400, unknown
resources after a membership check are 404, stale CAS or key reuse are 409,
and database outages/exhausted serialization retries are 503. Conflict
metadata includes only current revision/version and digest **after**
authorization; error responses never leak SQL, provider details or media paths.
Unauthorised requests to both unknown and existing project IDs are equally
refused without exposing the document.

## Transactions and invariants

Migration ordering: existing #379 `applyProjectAuthorizationMigration`, then
`applyProjectDocumentsMigration`, under an independent advisory transaction
lock with a verified SHA-256 entry in `vera_schema_migrations`. No old
migration files or membership foreign keys change. The new forward-only
tables are `stt_projects`, `stt_document_heads`, `stt_document_revisions`,
`stt_project_settings`, `stt_settings_revisions`, and
`stt_project_title_mutations`. Revisions and title history have database
triggers forbidding UPDATE/DELETE. All persisted snapshots are **text**, not
JSONB (which can reorder normalized JSON); each has a separate server-side
SHA-256 of the exact UTF-8 text.

Create: authenticate; validate the complete v2 document, project and optional
settings; begin SERIALIZABLE; inspect `(creator_actor_id, clientRequestId)`;
an identical replay must recheck current membership, while a changed payload
gets 409; otherwise INSERT new project, revision-0 head and immutable genesis,
optional settings head/history, then call #379's
`provisionFirstProducerInProjectTransaction` on the **same** SQL connection,
and commit. A duplicate `projectId` is a 409 rather than a grant/invite.

Document write: #379's `withAuthorizedMutation(...,'edit_document', operation,
writeSessionId?)` checks role and session under lock inside the transaction.
Only *then* look up the scoped `(project,actor,clientMutationId)` receipt;
same canonical request fingerprint returns its original revision/digest,
changed payload or expected revision is a 409. Otherwise compare the server
revision and immutable document.id/projectId, INSERT the revision snapshot,
then conditional `UPDATE head WHERE revision = expectedRevision`, and COMMIT.
Rollback on any error; retry only the complete SERIALIZABLE transaction up to
three times for SQLSTATE 40001/40P01. No optimistic retry of stale CAS or
silent overwrite. `liveHeadSequence`, `liveStateVector`, and `liveContentHash`
belong to the existing collaboration contract and are preserved verbatim;
they are **not** storage-revision values.

Project title and settings write: #379's `manage_settings` check shares the
same serializable write transaction. Both use a server CAS/version, scoped
idempotency key and immutable audit history. `settings.id` is immutable once
created. Optional settings start absent; first PUT with
`expectedSettingsRevision:0` creates server settings revision 1. The typed
`settings.version` and `settingsHash` remain as **supplied** and validated by
the existing schema. The contract does not define a canonical settingsHash
derivation, so this backend **does not recompute or assert** it represents
the current settings bytes. Instead it separately computes `digest` over
exact saved text; `settingsHash` cannot grant permissions or override that
digest. This avoids falsely claiming a caller hash was independently verified.

## Acceptance evidence and boundaries

Use isolated PGlite for schema, typed validation, create/replay, CAS,
attribution/history counts, permission loss/session invalidation, malformed
HTTP inputs and rollback; read data after constructing a new service instance
against the retained DB. Run a two-connection disposable PostgreSQL test for
true concurrent CAS/role-write serialization (not possible to prove with a
single PGlite connection). Focused tests and typecheck/lint must pass in phase
1; phase 2 runs `npm run validate:fast`, mutation tests and whole-diff review.
No local-agent/Resolve or media manipulation is a valid check for #380.
