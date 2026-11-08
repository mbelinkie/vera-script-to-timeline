# #385 — Backend anchored comments, mentions and stale reattachment

## Accepted scope and boundaries

This is the service-only half of #74. Implement against the existing four
`CommentAnchorV2` variants and `CommentOperationV2` in
`packages/contracts/src/authoring-v2-comments.ts`; do not change the type of
`ScriptDocumentV2` or the comment engine's strict, evidence-based stale rule.
Only `activeDraft.blocks` are currently addressable: Ideas/Extras anchors,
Yjs relative positions, browser UI, notifications and review workflows are
not provided by this ticket. #379 authorization and #380 project document
storage are the only declared predecessors, both already merged.

```
suite-authenticated request -> project API -> project authorization / membership
                                            |             (same SQL transaction)
                                            v
                              document head -> comment head -> pure anchor engine
                                                    |                 |
                                                    +-- immutable client event
                                                    +-- comment state/digest

successful document PUT -> same authorized transaction -> document head lock
                                                -> comment head stale reconciliation

build submission -> exact typed document head and settings -> frozen build
                  (no comment table or comment payload on this path)
```

## Storage, migration and integrity

Migration order is existing #379 identity/membership, immutable **001**
`applyProjectDocumentsMigration`, then **002**
`applyProjectCommentsMigration`. Each has its own SHA-256 migration receipt,
version (`001`: 1, `002`: 2), advisory transaction lock and atomic rollback.
002 adds only `stt_comment_heads` and `stt_comment_events`; QA host's strict
table allowlist and expected migration receipts must be extended in phase 3.
No edit/backfill of 001, and no extension to `stt_document_heads.document_json`.

`stt_comment_heads` is one row per STT project: `project_id` PK/FK, immutable
`document_id` enforced in the service, `document_revision` (the bound server
document revision), `comment_revision` (sequential pure-engine CAS),
`state_json` (exact serialized replay bytes), `state_digest` (SHA-256 over those
UTF-8 bytes), `updated_by` (trusted actor FK) and `updated_at`. There is no
comment head until the first accepted comment operation; GET is read-only and
derives `createCommentStateV2` from the current checked document. The state
size is capped at 8 MiB in SQL. Phase 2 additionally caps history growth
(at most 5,000 operations) before insert/update; refuse, never truncate.

`stt_comment_events` is immutable history **of client comments only**, keyed
by `(project_id, comment_revision)`; `(project_id,actor_id,client_mutation_id)`
is also unique. Each event records the expected and resulting comment CAS
revision, bound `document_revision`, actual trusted `actor_id`, caller's
mutation UUID, canonical `request_digest`, exact `operation_json`, and time.
`comment_revision = expected_comment_revision + 1` and digest shapes are SQL
CHECKs. Events cannot be UPDATEd or DELETEd because 002 installs an immutable
trigger using 001's `stt_revision_immutable()`. A document-only internal
`replace_document` changes the replay state/revision without creating a
client event, so event revision numbers need not be contiguous.

Never trust a head merely because its checksum is present: verify digest of
the exact bytes, `deserializeCommentStateV2` historical replay, project and
document identities, and canonical state document equality with the current
checked typed document. If any check fails, return 503 and roll back; never
reset state, silently reattach or skip a bad history item. Historical replay
embeds past full typed documents and must remain in comment-only storage.
Never return `state_json` or internal `replace_document.document` in a public
response or send them to build/compiler/prompter/agent.

## Trust and operations

The sole HTTP routes added in phase 3 will be:

| Route | Auth action | Input/response |
| --- | --- | --- |
| `GET /v1/projects/:id/comments` | `view_comments` | `{projectId,documentRevision,commentRevision,threads}` (no persisted history blob) |
| `POST /v1/projects/:id/comments/operations` | `comment` | Exactly `{expectedCommentRevision,clientMutationId,operation}`; receipt `{projectId,clientMutationId,commentRevision,digest,duplicateDelivery}` |

`operation` accepts exactly `create`, `reply`, `resolve`, `reopen`, `reattach`,
and the fields for its discriminant. `src/comment-input.ts` strips **no**
unexpected fields: it rejects them, including client `actorId`, `id`,
`document`, `role` and internal `replace_document`. It obtains `actorId` from
the trusted `SuiteIdentityPort` + `withAuthorizedMutation` callback and `id`
from the validated top-level `clientMutationId`, never from the operation
object. Thread, message and anchor IDs are UUIDs; body must be nonblank and
at most 20,000 UTF-8 bytes; at most 25 unique, normalized actor UUID mentions.
The pure contract determines anchor existence and ambiguity, not the parser.
At commit time every mentioned actor must still be enabled and an active
member of this same project (`vera_project_members` joined to
`vera_identity_actors`, with held authorization transaction). Invalid mentions
all get the same 400 with no UUID enumeration. Stored historical authorship
and mentions are not removed when membership changes.

Every GET and POST reauthenticates, including duplicate delivery. Viewer may
read but never mutate; Producer and Editor may comment, resolve/reopen, and
explicitly reattach stale anchors. Deny unknown/revoked/cross-project actors
before any scoped content is visible. Use existing error classes: 400 invalid,
403 unauthorized, 404 authorized missing project, 409 stale CAS or reused key,
503 unavailable/corrupt. Preserve 512 KiB HTTP request cap, no-store and no
query-parameter body transport.

## Transaction order, idempotency and document coupling

Use #379's `withAuthorizedMutation` (SERIALIZABLE with bounded whole-operation
retries) and this lock order for **both** comment writes and document PUT:

1. Authenticate and lock current member/identity through authorization.
2. Lock the existing `stt_document_heads` row `FOR UPDATE` for this project.
   This guaranteed row also serializes **first comment-head creation**;
   no separate document-independent writer may bypass the ordering.
3. Lock `stt_comment_heads` if present, validate digest/replay/bound-document
   identity/revision. For a missing head, derive ephemeral empty revision 0.
4. For client writes, look up `(project,actor,mutationId)` event after current
   authorization. Fingerprint the semantic request including expected comment
   revision and normalized operation. Exact replay returns the original
   receipt with `duplicateDelivery:true`, changed request returns 409.
   Otherwise check comment revision CAS, then mentions and anchor-engine
   operation. Persist new state digest/head and the immutable event in **one**
   transaction. A failed operation must leave no head/event side effect.
5. For a successful new `putDocument`, before commit validate the prior bound
   comment state against the old typed document, then call the pure engine's
   internal `replace_document` with ID `document-revision:<newRevision>` and
   the actual trusted document editor. Persist state + bound document revision
   atomically with the typed document revision/head. For unchanged document
   bytes that still increment document revision, only advance bound revision:
   the pure engine intentionally rejects semantic no-ops. An idempotent
   document delivery must change neither comments nor their revisions.

Never retry a stale CAS as if it were a transaction conflict. An aborted
mutation, invalid mention, corrupt state or failed SQL insert must roll back
both sides of any document/comment transaction. Only explicitly requested
`reattach` on a currently stale thread may change its anchor; quote-search or
automatic reattachment is prohibited. Retain original quote, message IDs,
authorship and stale state across edits.

## Implementation sequence and evidence

- Phase 1 (this commit): checksum-pinned additive SQL, strict trusted parser,
  isolated schema and validation tests, and PGlite fixture migration.
- Phase 2: durable `ProjectCommentService` using shared pool/auth and existing
  pure contract. PGlite tests for role/tenant/mention, corruption, atomicity,
  all anchor kinds, CAS, replays and persisted reload.
- Phase 3: same-transaction document write bridge and QA HTTP/host migration
  allowlist. Test old/new head binding and no-op/duplicate document edits.
- Phase 4: PGlite, disposable multi-connection PostgreSQL concurrency, host
  tests, and a negative sentinel regression for build snapshot and agent
  payload isolation; mutation checks and full `validate:fast`. Retain synthetic
  evidence without implying native Resolve verification.

**Boundaries:** The QA host shares the existing Postgres pool, authentication
port and request bounds; there is no new external identity provider, Research
permission, deployment, notification delivery, worker or native/local-agent
endpoint. `packages/project-builds/src/submission.ts` already freezes exact
`stt_document_heads` bytes and `src/status.ts` passes only that frozen payload
to the local agent. Neither calls this service. Preserve compiler, prompter,
build and local-agent schemas byte-for-byte; prove the negative boundary in
tests rather than adding a comment field or a filtering step to builds.
