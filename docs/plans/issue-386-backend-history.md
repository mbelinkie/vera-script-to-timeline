# #386 — Backend attributed history, immutable checkpoints and restore

## Scope and source of truth

Backend-only split from #75, using the accepted Rev2 product spec §6.7/6.9 and
§8 and the existing #379 authorization / #380 document service. Declared
predecessors are **#379 and #380 only**, both merged. The user-facing
comparison UI and visual flows remain in #75. No prerequisite is introduced
on #125, #377, #62, #382 or #385; #385's now-merged 002 migration is kept in
order. No native Resolve operation, Yjs operation ingestion, implicit share,
approval workflow beyond a single approved label or build gate is in scope.

## Existing contracts and authority

- `ScriptDocumentV2` is checked by `checkedDocument` and serialized through
  `@vera/contracts/authoring-v2`; `sha256(exactUtf8Json)` is the **storage**
  digest, not `liveContentHash`. Existing optional script settings and typed
  draft blocks/supporting items can be compared. `ideaOutline` and `extras`
  remain reserved zero-item arrays in the current contract; do not fabricate
  semantic movement. `liveHeadSequence`, state vector and digest are separate
  from **server** revision ordering.
- `stt_document_revisions` (001) already has immutable server-ordered
  `(project_id,revision)`, `actor_id`, `client_mutation_id`, `expected_revision`,
  `created_at`, saved document bytes and their digest. Do **not** add another
  journal or edit 001. Genesis revision 0 is a normal history entry.
- `ProjectAuthorizationService.withAuthorizedMutation` provides same-database
  authorization, revocation locking, SERIALIZABLE transaction and bounded
  retry. Use its existing closed action policy: `view_history` for Viewer+,
  `create_checkpoint` for Editor+, `approve_checkpoint` for Producer only,
  `edit_document` for Editor+ restores. Require a trusted authenticated
  `PrincipalRef`; never accept actor/role from payload or headers. Recheck
  permissions **before** idempotency receipt lookup.
- Reuse `ProjectDocumentError` and `ProjectDocumentInputError`: 400 invalid,
  403 authorization, 404 authorized missing, 409 stale/conflicting, 503
  corrupted or unavailable. Existing HTTP handler authenticates before
  parsing, caps streamed JSON at 512 KiB and sends no-store/nosniff responses.

## Persistence, migration and checkpoints (phase 1 schema; phase 3 service)

Apply identity, documents **001**, comments **002**, history **003** in that
order. `applyProjectHistoryMigration` adds its own transaction and advisory
lock, SHA-256 file checksum and exact `schema_version=3` receipt. QA host
strictly allowlists the three new tables and receipt in this order. Reapply
is a no-op only on exact receipt match; failed application rolls back. Never
rewrite 001/002 or modify historical receipts.

- `stt_document_checkpoints`: `(project_id,checkpoint_id)` primary key,
  case-insensitive unique `(project_id,lower(name))`, immutable name,
  `source_revision`, `document_id`, **exact** frozen document UTF-8 JSON,
  `source_digest`, trusted `created_by`, `client_mutation_id`, `request_digest`,
  server timestamp. Source points to same-project revision; SQL guards digest
  syntax and snapshot length; service verifies exact source bytes, SHA-256,
  document identity and typed shape. Names must be trimmed, 1–120 characters,
  nonempty, and reject controls; SQL length/trim is not enough.
- `stt_checkpoint_approvals`: one immutable event per checkpoint, same-project
  FK, trusted `approved_by`, mutation UUID, request fingerprint and server
  timestamp. Producer only, no upsert or mutation of existing approval;
  duplicate same-key request returns a receipt, different-key second approval
  is a conflict. No inferred approval during restore.
- `stt_document_restores`: immutable provenance keyed by
  `(project_id,new_revision)` referencing a **new** document revision; points
  to checkpoint's source revision and digest by composite FK, stores trusted
  `restored_by`, client mutation UUID and server timestamp. Never update or
  delete previous revisions/checkpoints. Same-actor mutation IDs are unique.
- All three tables reuse 001's `stt_revision_immutable()` BEFORE UPDATE/DELETE
  trigger. SQL foreign keys prevent foreign-project joins and missing sources;
  they cannot prove JSON/hash equality, which service must verify.

## Typed service and HTTP contracts (future phases)

Phase 2 exposes bounded, stable descending revision list with cursor/limit,
single revision view, and comparison by two integer revisions under
`view_history`. Return server revision, trusted actor, client mutation UUID,
accepted timestamp, revision/digest metadata. A pure `compareDocuments` yields
sorted `{surface,entityId,kind,fields}` for documented typed surfaces, with
stable IDs and no noisy live collaboration metadata. Bound number and size
of changes; either explicitly signal truncation or refuse oversized requests.
Authorize the project and verify stored source digest/typed identity before
comparing. Do not disclose revision count or digest across projects.

Phase 3 exposes list/get/create checkpoint and Producer approval with
`create_checkpoint`/`approve_checkpoint`; require UUIDs, exact allowed fields
and checked names. Validate snapshot revision exists in this project and
matches the stored digest *in the same authorized transaction*. A checkpoint
created from revision 0 remains byte-identical after later edits. Receipt
replay must verify the request fingerprint and still-current authorization.

Phase 4 adds restore accepting `{checkpointId,expectedRevision,
clientMutationId}` with optional authenticated write session. Under an
`edit_document` transaction: authorize; check same-key revision receipt
(fingerprint distinguishes PUT from restore); load and hash-check source
revision **and** checkpoint, compare exact bytes/document IDs; lock current
document head and verify its digest and expected revision; insert new
`stt_document_revisions` at `expectedRevision+1` with current actor and exact
checkpoint bytes/digest; insert `stt_document_restores`; CAS update
`stt_document_heads` on expected revision; reconcile #385's comments in the
**same** transaction as normal document replacement, or rollback. A replay
does not create a second head even after later edits. Stale CAS => 409; only
40001/40P01 may retry; any failed insert/head update is atomic rollback.
No checkpoint/approval is implicitly cloned to the new head. Build snapshots,
release eligibility and settings remain unchanged in this backend issue.

HTTP routes belong under the existing `/v1/projects/:projectId` namespace:
`GET /history`, `GET /history/:revision`, `GET /history/compare?` is **not**
allowed by the existing no-query policy, so use explicit path segments
`GET /history/compare/:before/:after`; `GET/POST /checkpoints`,
`GET /checkpoints/:checkpointId`, `POST /checkpoints/:checkpointId/approval`,
and `POST /checkpoints/:checkpointId/restore`. Parse literal `compare`
before generic revision matching; reject unknown methods, query strings,
client-supplied actor/role/approval, malformed UUID/revision and oversized
requests. Exact response shapes are typed from current service interfaces
when implemented; no UI contract change is implied.

## Boundaries, ordering and verification

`createProjectApiHandler` is the trust boundary, authorization service is
the permission boundary, PostgreSQL/PGlite is the persistence boundary.
`project-service-host` owns QA migration preflight only; it does not grant
identity or open any new external service. Local agent, Resolve, research API,
provider acquisition, native media, release builds and production deployment
remain untouched. The source checkpoint is a document revision, **not** a
frozen build snapshot or delivery artifact. This backend cannot certify the
existing build lifecycle's release-checkpoint enforcement; record that
integration gap rather than silently broadening this issue.

Five ordered phases: (1) schema/receipt/QA allowlist and migration negatives;
(2) attributed history, semantic comparison and scoped-read negatives;
(3) create/list/read/approve with tamper/role/idempotency/restart tests;
(4) atomic restore and HTTP auth/serialization/concurrent CAS tests;
(5) focused suites, single-worker `validate:fast`, reversible security/data
guard mutations and retained evidence. PGlite tests prove fake service paths,
not independent-connection races; use separately connected disposable
PostgreSQL for that assertion, or mark it unverified. Self-review every diff,
and do not run full `validate` locally.
