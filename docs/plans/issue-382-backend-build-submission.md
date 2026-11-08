# #382 — Backend build submission, pairing and immutable evidence

Status: phase-3 frozen submission and durable status implementation (2026-11-08).
Pairing and observational polling are in an **unmounted** private API.
Submission and epoch-CAS status are service methods, not deployed HTTP
routes or a local-agent runner. No native completion has been verified.

## Authority and boundaries

- **Web/service:** The #379 \`ProjectAuthorizationService\` is the sole user
  identity/membership authority. It authenticates the request through the
  trusted SuiteIdentityPort. Producer may manage agents and submit release;
  Producer/Editor may submit preview; Viewer may only read authorized results.
  Every user mutation, including freezing a build, uses
  \`withAuthorizedMutation(projectId, principal, action, ...)\` in one
  SERIALIZABLE PostgreSQL transaction. The agent is NOT a user principal.
- **Document owner:** #380 stores canonical exact \`document_json\`,
  \`content_digest\`, head revision, and separate settings
  (\`settings_json\`, \`content_digest\`, \`settings_revision\`). The new service
  reads those exact stored bytes under the same authorization transaction;
  it must not trust caller-supplied document bytes or call two independent
  document GETs. Its submit input contains only expected revision/digest,
  selected source *identities*, build class/mode and request UUID; never a
  filesystem path, credential, shell command, or client-supplied role.
- **Agent:** a separate local credential with project scope and revocation
  proves possession of one-time pairing. #158 operator readiness JSON is
  advisory evidence only. Agent may fetch only an assigned immutable manifest,
  heartbeat, and report scoped attempts/evidence; cannot grant project access.
- **Local execution:** #157 \`SnapshotRepository\`, \`BuildComposition\`,
  \`BuildJobStore\`, accepted StagePorts and receipt inspection own local
  snapshot verification/stage leases. The service is only submission, status
  mirror and assignment lease. Never create another PostgreSQL stage
  scheduler, assume success from a receipt, or run the simulation CLI as real
  native proof. No automatic providers, uploads, renders or Resolve calls.
- **Host:** #159 development-QA HTTP remains loopback-only, with its existing
  owner-only credentials, Host/size/no-CORS rules and strict backup/restore
  schema allowlists. No remote endpoint, browser UI or production deployment
  is authorized. #70 owns subsequent UI; #71 external delivery.

RK-01 is evidence for manually imported Free OTIO; RK-02 distinguishes
external, parent and injected Resolve routes. Neither constitutes a current
native proof. Studio native success requires independently checked saved,
closed, reopened and read-back timeline, by #157's existing native ports.

## Versioned request/result contract (private \`/v1\`)

Strict \`BuildIntent\`: exact properties
\`buildClass: preview|release\`, \`mode: free|studio\`,
\`expectedRevision\` (nonnegative safe integer), \`expectedDigest\`
(\`sha256:\` + 64 lowercase hex, matching #380), \`idempotencyKey\`
(UUID), \`selectedSources\` (0–256 distinct, source-ID UUID, nonblank bounded
revision string and \`sha256:\` hash), \`render: false\`,
\`delivery: false\`. Reject unknown fields, unsafe or oversize inputs,
prototype tricks, duplicate IDs and all caller-provided local paths. A
source ID here is an *assertion*, not proof of an accepted source. Until a
specific verified accepted-source adapter resolves every pin, return an
actionable durable block rather than inventing a verified asset. Neither
preview nor release grants new money/native permissions.

The service computes its own stable request fingerprint from parsed
semantic values, and compares the project, *authenticated* actor and UUID
idempotency key. Exact repeat returns one job; same key/different request
is 409. Read the current head, settings and *selected* accepted source
versions atomically; compare caller expected head revision/digest, recompute
exact stored-byte hashes, and freeze content, revisions, pins, class and
actor. Jobs carry unique immutable target IDs. Never union branches, silently
rebase stale heads or overwrite prior timelines. A later head/settings
change before agent preparation yields \`stale_snapshot\`/\`needs_action\`
with prior receipts preserved and a new submission required.

Minimal private API shapes to implement in later phases:

| Endpoint | Authority | Semantics |
| --- | --- | --- |
| POST /v1/projects/:id/agent-pairing-offers | Producer manage_settings | Short TTL, random single-use offer; return secret once, store digest |
| POST /v1/agent-pairing/consume | One-time offer possession | Atomic offer consume; independent 256-bit agent secret |
| DELETE /v1/projects/:id/agents/:agentId | Producer manage_settings | Revoke/rotate, stop future claims |
| GET /v1/projects/:id/agent-readiness | Authorized viewer | Advisory diagnostics plus authenticated current heartbeat; never nativeVerified |
| POST /v1/projects/:id/builds | Editor/Producer preview_build; Producer release_build | Frozen job ID, digest, \`accepted\` or \`blocked\`, never native success |
| GET /v1/projects/:id/builds/:jobId | view_build_results | Redacted progress/partial evidence, no secrets/private paths |
| POST /v1/projects/:id/builds/:jobId/{resume,cancel} | Build-class authority | Serialized status transition; never replay unverified native effects |
| POST /v1/agent/jobs/{claim,progress,result} | Active scoped agent credential | Epoch-CAS lease, exact job/project/stage receipt hashes, append-only evidence |

HTTP authenticates the correct category *before* revealing job or parsing
untrusted content. Responses use bounded redacted refusal codes, e.g.
\`invalid_build_intent\`, \`action_not_allowed\`, \`idempotency_conflict\`,
\`stale_snapshot\`, \`source_unverified\`, \`agent_revoked\`,
\`lease_expired\`, \`needs_action\`, \`waiting_reconcile\`. Refusals retain
the frozen job/partial results if a job already exists; an invalid HTTP body
is rejected before any row is created.

## Database: finite additive schema and ownership

\`packages/project-builds/migrations/001_project_builds.sql\` creates the
original seven tables; a separate additive \`002_preflight_refusals.sql\`
retains missing-settings refusals without changing the first migration:

| Table | Role | Mutable? |
| --- | --- | --- |
| \`stt_build_pairing_offers\` | project, issuing Producer, SHA-256 offer digest, protocol, creation/expiry/one-time consume/revoke | consume/revoke only by scoped service |
| \`stt_project_build_agents\` | project, offer, independently hashed rotating credential/version, protocol/capabilities, heartbeat/revocation | authenticated credential/revocation transitions |
| \`stt_build_submissions\` | job/unique target, project, actor, request UUID/fingerprint, frozen exact document/settings JSON and hashes, expected revisions, class/mode | **no UPDATE/DELETE** |
| \`stt_build_source_pins\` | selected source ID/revision/digest by job only | **no UPDATE/DELETE** |
| \`stt_build_dispatches\` | one status/assigned agent/epoch/expiry per job | CAS guarded by service |
| \`stt_build_events\` | sequenced job/epoch/stage/state/reason/attestation metadata | **no UPDATE/DELETE** |
| \`stt_build_evidence\` | job/stage receipt digest, independently classified evidence/provenance | **no UPDATE/DELETE** |
| \`stt_build_preflight_refusals\` | actor/request UUID scoped refusal when no #380 settings exist (not a build or dispatch) | **no UPDATE/DELETE** |

Additive foreign keys enforce project scope; unique offer/agent digests,
unique \`(project, actor, request_uuid)\`, unique \`(job, source_id)\`, one
dispatch per job; checks bound hashes, lengths, statuses, nonnegative epoch
and counters. No raw secrets or original filesystem paths persist. The
mutable dispatch/heartbeat columns are **not** evidence of native success.
Immutable tables have database update/delete-denial triggers. All rows are
retained for QA; expiry removes authority, not history. Archival/deletion
policy and any production retention job are out of scope.

Transaction and evidence flow:

\`\`\`text
trusted SuiteIdentityPort → #379 SERIALIZABLE project authorization
  └─ READ stored #380 head/settings + verified selected source references
     └─ INSERT immutable submission + pins + first dispatch + event [commit]
        └─ paired agent polls by scoped credential; CAS claim epoch [commit]
           └─ #157 local frozen snapshot / SQLite jobs / StagePorts
              └─ append agent report + independently inspected proof
                 └─ status mirror (not a second execution scheduler)
                    └─ optional Studio native one-use intent and readback
\`\`\`

Apply migrations in order: #379 identity → #380 project-documents → #382
build 001 → build refusal 002. The two build migration steps require the
existing receipt table, hold a PostgreSQL advisory transaction lock, hash
exact checked-in SQL with SHA-256, reject mismatched receipt versions/checksums
and are idempotent. No existing migration file is edited. Host startup,
smoke tests and ops allowlists must be changed *together in phase 4*;
until then host startup does **not** apply build migrations. Backup/restore to
a new private QA database must include all eight new tables and both new
receipts before deployment is claimed. No down migration/destructive rollback; a failed
DDL transaction rolls back, a rolled-forward installation stays additive.

## Validation ladder and phase owners

1. Phase 1: pure strict parser, checksum/replay/additive PGlite and immutability
   guard tests. No pairing service or submission endpoint exists yet.
2. Phase 2: fake-clock offer TTL/consume/reuse/rotation/revocation, project
   scope and separate machine authentication, strict API authentication.
3. Phase 3: transactional #379/#380 freeze, accepted sources, replay/409,
   role revocation, stale-head and source refusal, events/CAS/epoch and
   retained progress across service restarts.
4. Phase 4: private agent HTTP adapter + existing #157 local build ports;
   host schema/backup allowlists, synthetic PostgreSQL/SQLite/restart
   evidence. No native app operation without separate explicit permission.
5. Phase 5: focused + fast validation, mutation of auth/digest/epoch
   guards, one independent self-review and truthful final evidence.

An accepted HTTP request, reported stage, signed receipt, verified package,
native API response and independently saved/reopened Resolve timeline are
**different** evidence tiers. Test-only synthetic proof is labeled synthetic;
Free can reach ready-to-import but not automatically imported; Studio can
be called verified-native **only** after current readback evidence. This
issue's backend tests cannot establish production deployment or general
native parity. Dependencies are exactly #157, #158, #159 and #379.

## Phase 2 implementation notes (unmounted developer-only transport)

- `ProjectAgentPairingService` creates a 5-minute, random 256-bit
  `stto_` offer through #379's `manage_settings` transaction. Only a Producer
  can create or cancel an outstanding offer; the agent consumes it by proving
  possession while the service rechecks the issuing Producer's *current* role
  in the same transaction. A locked, atomic
  one-use consume stores only a SHA-256 digest and issues a separate random
  256-bit `sttag_` machine credential. The raw offer and agent credential are
  returned only in their single successful creation/consume responses.
- Machine authentication does not use `SuiteIdentityPort` and never produces
  a user actor. Each heartbeat or observational assigned-job poll locks and
  rechecks credential digest, version, revocation, exact project ID,
  supported protocol and issuing Producer's current role. Revoked Producer
  authority disables their previously paired agent. A current credential
  permits reconnect; Producer rotation increments credential version and
  invalidates the old token; revocation is permanent. No machine credential
  grants membership, submission, stage execution, native effects or payments.
- Valid protocol is `stt-build-agent/v1`. The bounded, strictly validated
  claimed capability names are `free_package_v1` and
  `studio_readback_v1`; they are *claims*, not native authorization or proof.
  `GET /v1/agent/projects/:id/jobs` only describes existing assignments
  (job ID, status, lease epoch and expiry) for a matching authenticated agent.
  It does **not** claim or lease, fetch frozen inputs or dispatch effects;
  those are phase-3/4 obligations.
- Other phase-2 endpoints: `POST /v1/projects/:id/agent-pairing-offers`,
  `DELETE /v1/projects/:id/agent-pairing-offers/:offerId`,
  `POST /v1/agent-pairing/consume`, `POST /v1/agent/projects/:id/heartbeat`,
  `POST /v1/projects/:id/agents/:agentId/rotate`,
  `DELETE /v1/projects/:id/agents/:agentId`, and
  `GET /v1/projects/:id/agent-readiness`. User routes require a trusted suite
  identity adapter, agent routes require a scoped Bearer token plus positive
  `X-Agent-Credential-Version`; API JSON is strictly shaped and 4-KiB bounded.
  Readiness reports a recent authenticated heartbeat but **always** returns
  `canBuild=false` and `nativeVerified=false`, never granting authority from
  #158 untrusted operator observations.
- This TypeScript handler intentionally remains **unmounted** until phase 4
  extends the existing QA host's loopback-only transport restrictions,
  migration allowlists and backup rules. The HTTP handler alone does not
  establish local transport safety, TLS, deployment or a usable build runner.

## Phase 3 implementation and evidence

- \`ProjectBuildSubmissionService.submit\` locks #379 project membership inside
  the SERIALIZABLE transaction that reads exact #380 document/settings bytes
  and freezes the build. Digest and project identity are rechecked against
  those original stored JSON bytes, not caller-supplied payloads. Preview is
  Editor/Producer; release is Producer. The frozen record binds immutable
  job/target UUIDs, actor, intent hash, head revision, settings revision and
  an independent snapshot fingerprint over the selected source pins. A live
  head mismatch returns 409; a changed head/settings at claim/manifest fetch
  retains an explicit \`stale_snapshot\` event and requires a new job.
- \`AcceptedSourceAuthority\` is an explicit trusted, SQL-transaction-scoped
  adapter. It must confirm *every* selected source identity/revision/hash from
  previously accepted records; the client list is never proof. The current
  project-documents schema has **no authoritative accepted-source table**.
  Tests supply a SQL-backed fake to exercise successful exact matching,
  cross-project mismatch, unselected source exclusion and later revocation.
  Until an actual adapter exists, nonempty selections remain durably
  \`blocked/source_unverified\`; zero selected sources means an explicit empty
  set, **not** a verified runnable build or permission to use providers.
- Missing #380 settings cannot be frozen as fake JSON. Migration 002 therefore
  records an immutable actor/request-key-scoped \`settings_unavailable\`
  preflight refusal. Reusing the UUID gives the same refusal, conflicting
  request bytes return 409 and submitting after fixing settings requires a
  new UUID. The accepted/refused key namespaces share a transaction advisory
  lock and whole-transaction serialization retries.
- Only a pre-execution \`blocked\` source-selection refusal may be rechecked
  by \`resume\`. \`needs_action\`, \`failed\`, and \`waiting_reconcile\` might
  already contain an uncertain native effect, and cannot be automatically
  requeued. Such partials require independent manual/local reconciliation
  through the #157 safety path.
- \`ProjectBuildStatusService\` provides authorized, redacted viewer status
  and append-only event/evidence readback. A separate authenticated machine
  credential can claim a bounded service lease and fetch only its assigned
  frozen manifest. Every claim/progress/fetch rechecks agent credential,
  credential version, current issuer/submitter role, project, epoch and lease
  expiry. Leases are NOT #157 stage authorizations. Expired work never
  silently retries; cancelling in-flight work moves to \`waiting_reconcile\`.
- Machine progress remains \`untrusted_report\`, with no verified-native
  status upgrade from a client claim. A trusted
  \`IndependentEvidenceInspector\` adapter must independently inspect a
  receipt/output and return verified hashes before any evidence row is
  accepted. Tests exercise only \`synthetic\` evidence; real package verification
  and Studio save/close/reopen readback are still unverified and remain for
  later phases. The API/host/Python transport are **not** implemented in
  phase 3. This phase's PostgreSQL-shaped PGlite tests (including DB dump and
  re-import) demonstrate backend persistence, not deployed native capability.
