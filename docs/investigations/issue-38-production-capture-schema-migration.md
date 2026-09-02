# Issue 38 — production public-page capture schema and migration boundary

Status: **Proposed for Producer acceptance**

Scope: contract-change and migration plan only; no shared-schema or runtime edit

Authority: GitHub issue #38, Producer-accepted #27 commit `9143518`,
Producer-accepted #28 evidence commits `47a3569` and `fcdea1c`, and the product
specification Revision 2.2

## Decision in one sentence

Add three closed, versioned capture-contract roots and an additive PostgreSQL
schema in issue #39 so the hosted API remains the sole project-policy authority,
the local worker receives one expiring job/lease capability, every real attempt
and successful observation stays separately identifiable, and one database
transaction publishes an immutable revision plus its exact artifact,
provenance, change signal, optional conditional selection, protection reasons,
and audit evidence; expose no scheduler or deletion write surface.

This decision is not authoritative until the Producer records the acceptance
response in §14. It performs no implementation and changes no shared contract.

## 1. Reconciliation and hard boundary

### 1.1 Binding behavior carried from #27

The production contract must preserve all of these accepted distinctions:

- a `Capture` is stable project-owned intent, not a URL, image, path, or latest
  result;
- a `CaptureJob` is one logical authorized trigger and may commit at most one
  revision;
- a `JobLease` is one expiring worker capability epoch and authorizes at most
  one actual `CaptureAttempt`;
- a successful actual observation always creates a new immutable
  `CaptureRevision`, including when its raster bytes exactly equal an earlier
  artifact;
- exact bytes may reuse a project-scoped `Artifact`, but observation time,
  provenance, authorization, selection, protection, and audit do not merge;
- a revision has exactly one verified primary raster and exactly one complete,
  restricted provenance manifest;
- selections, use decisions, pins/protections, releases, and audit evidence are
  append-only records; there is no mutable `selectedRevisionId`, `latest`, or
  `pinned` boolean;
- a build or checkpoint names an exact revision and later recapture cannot
  alter it;
- failed, rejected, cancelled, abandoned, or late attempts create no revision;
  and
- only explicit `Now`/manual and immutable `On build` triggers execute.
  `Periodic` remains reserved and disabled.

### 1.2 What #28 proves and what it does not

Issue #28 is accepted evidence for fresh Chromium contexts, zero imported or
surviving cookies, a fixed hashed profile, bounded raster verification,
separate attempts/revisions, exact-byte reuse, immutable earlier output,
exclusive publication, SIGKILL recovery at eight boundaries, lease-expiry
denial, and lost-response idempotency. Its Finder-metadata fix also proves that
a known harmless local index entry can be handled narrowly without accepting
arbitrary history contents.

The spike deliberately has no production authorization, live resolver, TLS,
actual peer connection, object store, hosted API, database, scheduler, or
portable process sandbox. Its DNS and peer observations are synthetic and its
outer sandbox is macOS Seatbelt. Production code may reuse the tested policy
and publication ideas, but it must replace those seams with:

1. a current project-authorization decision owned by the hosted API;
2. a server-verified public-only resolver/egress path that observes actual
   peers for every top-level, redirect, frame, and subresource connection;
3. a deployment-specific disposable browser sandbox with no direct API or
   object-store credential;
4. immutable object staging whose bytes are reverified by the service; and
5. PostgreSQL uniqueness and compare-and-swap rather than a single local
   filesystem writer lock.

The #28 output store is evidence only. It is not legacy production data and is
never imported by this migration.

### 1.3 Product boundaries that remain external

The capture service consumes two narrow authority ports rather than inventing
their data:

- `ProjectAuthorizationPort` returns a current, stable actor/service principal,
  authoring-project membership and role, decision ID, membership version, and
  decision time for one named action. A source-product permission claim,
  renderer visibility, URL, hash, or capture record never satisfies it.
- `AuthoringReferencePort` validates an exact document occurrence,
  checkpoint, build snapshot, selection-evidence record, or hold owned by its
  subsystem and returns a project-bound immutable reference/version. The
  capture migration does not create broad collaboration, document, build, or
  Spotlight persistence.

If either port cannot provide its required current guarantee, the capture API
fails closed with `authorization_unavailable` before a job, lease, attempt, or
revision is created. Production activation is prohibited until the adapter can
couple a commit-time membership/build decision to the publication transaction;
an in-memory test adapter is not production authorization.

## 2. Explicit proposed contract change

### 2.1 What changes and why

After Producer acceptance, issue #39 may add exactly these shared roots:

| Proposed file | Root and purpose |
| --- | --- |
| `/contracts/public-page-capture-api-v1.schema.json` | `PublicPageCaptureApiV1`: closed discriminated union for authorized user/service requests, sanitized views, selection/use/pin commands, audit views, and errors. Its `$defs` own shared IDs, hashes, state enums, redacted locators, capture/configuration/job/revision/artifact/change/selection/protection records, and immutable external references. |
| `/contracts/public-page-capture-worker-v1.schema.json` | `PublicPageCaptureWorkerV1`: closed discriminated union for lease claim, attempt start, navigation-start evidence, renewal, immutable object staging descriptors, commit, terminal failure/abandonment, and their responses. A raw capability appears only in its one-time secret worker response field, marked `writeOnly`; persisted and non-secret response views contain only capability/scope digests. |
| `/contracts/public-page-capture-provenance-v1.schema.json` | `PublicPageCaptureProvenanceV1`: closed union of `revision_observation` and `terminal_attempt_evidence`. The revision form requires every #27 provenance group; the attempt form retains restricted denial/failure evidence without pretending a revision exists. |

All three use JSON Schema draft 2020-12, `additionalProperties: false`, an
exact `schemaVersion` const, bounded strings/arrays, UUID entity IDs, RFC 3339
UTC timestamps, and `sha256:<64 lowercase hex>` digests. API and worker unions
use a required `messageType` const for every member; provenance uses a required
`evidenceType`. Unknown message types or fields fail validation.

The REST/OpenAPI description in #39 may be generated or handwritten from these
roots, but it cannot weaken the schemas. Database rows are internal persistence
and are not accepted merely because they serialize as an API DTO.

### 2.2 Compatibility and what could break

- This is additive to the four existing v1 roots. It does not edit
  `ScriptDocument v1`, `CompilerDependencies v1`, `TimelineManifest v1`, or
  `BuildReport v1`; their schemas and exported named types remain byte- and
  behavior-compatible.
- There is no prior production capture wire or database representation to
  backfill. The #28 local spike format `issue-28-local-provenance/1` remains
  readable only by the spike; it is not accepted as the production v1 wire.
- Capture v1 is closed. Adding even an optional field to a closed message can
  break an older validator, so a changed wire uses a new message/schema version
  and explicit content negotiation rather than mutating v1 in place.
- The TypeScript generation harness may reference the three new roots as
  optional generation-only properties so `VeraContractsV1` does not gain new
  required members. Existing named types must produce no diff. New named roots
  and definitions are additive exports.
- The Python generator adds three modules and exports their root types from
  `python/vera_timeline_agent/generated/contracts/__init__.py`. Existing four
  generated modules must remain byte-identical; any generator-wide churn is a
  review failure unless separately explained and accepted.
- No compiler or authoring-document consumer may infer a Capture from these
  records yet. Binding a capture into `ScriptDocument`, compiler dependencies,
  a timeline manifest, or Resolve is a later explicit contract slice.

### 2.3 Generated types, fixtures, goldens, and acceptance implications

Issue #39 must update `packages/contracts/scripts/generate-contracts.mjs` and
the shared schema-validation inventory for the three new roots, regenerate the
single TypeScript output and Python package, and add import/smoke tests for
`PublicPageCaptureApiV1`, `PublicPageCaptureWorkerV1`, and
`PublicPageCaptureProvenanceV1`.

New public-safe examples belong under
`tests/data/issue_39_public_page_capture/`. They use only reserved fictional
hosts such as `https://capture.example.org/bulletin?lang=en`, synthetic UUIDs,
and placeholder hashes. Required examples are create/configure, `Now`,
`On build`, lease/attempt, ready commit, review-required commit, same-byte new
revision, conditional-selection conflict, restricted provenance, sanitized
denial, late-epoch denial, and duplicate-response recovery.

Existing `/fixtures`, Slice 0/1 test data, compiler goldens, accepted tests, and
their hashes do not change. New capture examples are not compiler goldens and
must not contact their displayed host. Producer acceptance of #38 authorizes
only the proposed delta above; any fourth schema, existing-root edit, existing
fixture/golden edit, or new cross-product contract requires a new explicit
change note before issue #39 proceeds.

## 3. Exact shared domain shape

### 3.1 Common scalar and reference definitions

| Definition | Exact contract |
| --- | --- |
| `EntityId` | UUID string. IDs remain opaque and never authorize access. |
| `ContentDigest` | `sha256:<64 lowercase hex>` over canonical bytes. A digest is identity/integrity evidence, never a capability. |
| `UtcTimestamp` | RFC 3339 `date-time`, normalized to UTC on service output. Client times are evidence only and never order state. |
| `PrincipalRef` | `{ principalKind: user | service, principalId }`; worker installation is a separate field and is not a project actor. |
| `AuthorizationDecisionRef` | `{ decisionId, action, principal, projectId, role: producer | editor | viewer | service, membershipVersion, decidedAt, recheckMode }`; API responses may omit `membershipVersion`, while persisted/restricted evidence retains it. |
| `ExternalReference` | `{ projectId, kind, resourceId, resourceVersionDigest, occurrenceId? }`; `kind` is `draft_occurrence`, `document_revision`, `document_checkpoint`, `preview_build`, `release_build`, `selection_evidence`, `review_hold`, or `integrity_hold`. `occurrenceId` is required only for `draft_occurrence`. |
| `RedactedUrl` | `{ display, canonicalDigest, queryKeys[] }`; no query value, userinfo, fragment, object key, local path, or capability. |
| `ReviewClassification` | `ready | review_required`; failures never create this record. |

The exact requested/final URLs and redirect chain appear only in an authorized
worker envelope and restricted provenance. A secret-bearing rejected input is
never retained verbatim or as an ordinary SHA-256 dictionary target: denial
audit uses a rotating-key HMAC fingerprint plus sanitized reason class.

### 3.2 API entities and commands

`PublicPageCaptureApiV1` defines these exact logical records:

| Record | Required fields and constraints |
| --- | --- |
| `CaptureView` | `captureId`, `projectId`, lifecycle `draft | active | paused | retired`, `currentConfigurationVersion`, optimistic `rowVersion`, `createdBy`, `createdAt`, `updatedAt`, and current sanitized `CaptureConfigurationView`. It has no latest/selected revision pointer. |
| `CaptureConfigurationView` | `captureId`, positive `configurationVersion`, `requestedUrl: RedactedUrl`, region intent, `acquisitionPolicy`, `captureProfileId`, positive `captureProfileVersion`, `settingsDigest`, `previousConfigurationDigest?`, `createdBy`, `createdAt`. Policy is `now`, `on_build`, or `{ kind: periodic_reserved, execution: disabled }`. |
| `CaptureJobView` | `jobId`, project/capture/configuration IDs, executable trigger `now | on_build`, trigger reference, idempotency fingerprint, initiating authorization decision reference, frozen settings/profile IDs and digests, retry budget, state, output `revisionId?`, conditional-selection result, request/enqueue/available/terminal times, and optimistic `rowVersion`. It never returns the caller's raw idempotency key or exact URL. |
| `CaptureRevisionView` | project/capture/job/winning-attempt IDs, monotonically allocated revision number, exact `artifact`, restricted-provenance descriptor, `changeSignal`, `ready | review_required`, required warning codes, settings/profile digests, commit time, and the observation-not-reproduction statement. It is immutable and contains no object locator. |
| `ArtifactDescriptor` | opaque `artifactId`, project ID, kind `capture_raster | capture_provenance`, digest, byte length, MIME, verified dimensions/encoding/color/alpha when raster, verifier profile/version, verification time, and access class `project_visual | restricted_provenance`. |
| `ChangeSignal` | opaque ID, capture/current revision, optional baseline revision, current/baseline artifact IDs, signal `initial_observation | same_exact_bytes | different_exact_bytes | not_comparable`, six nullable difference flags (final URL, redirect chain, profile, region, warnings, load evidence), algorithm/version/time, and a const non-materiality statement. |
| `RevisionUseDecision` | append-only ID, revision, exact external use context, decision `preview_acknowledged | release_accepted`, actor/authorization, warning-set digest, idempotency effect digest, and server time. Editor/Producer may acknowledge preview; only Producer may accept release. |
| `RevisionSelection` | append-only ID, revision, exact target reference, target sequence, prior selection ID or null, expected prior selection ID or null, reason `manual | capture_and_use | checkpoint_restore`, actor/authorization, optional required use-decision ID, idempotency effect digest, and server time. |
| `RevisionProtection` | append-only ID, revision, reason `draft_selection | document_revision | checkpoint | preview_build | release_build | explicit_pin | selection_evidence | review_hold | integrity_hold`, exact source reference, actor/service authorization, idempotency effect digest, and add time. |
| `ProtectionRelease` | append-only ID, protection ID, actor/service authorization, reason, idempotency effect digest, and release time. A release never retargets or deletes the protection record. |
| `CaptureAuditEventView` | event ID, project, primary object kind/ID and object sequence, event type, actor/service reference, request/correlation IDs, policy/profile versions, before/after state identifiers, sanitized result code/details, optional correction target, and server time. Exact URLs, peers, page text, capabilities, object locators, and secrets are absent. |

Commands are closed request types for `create_capture`,
`create_configuration_version`, `request_capture_job`,
`record_revision_use_decision`, `select_revision`, `add_explicit_pin`, and
`release_explicit_pin`. Each mutation requires an opaque `Idempotency-Key`
header, a client request ID, and the expected row/selection version where
concurrency matters. `request_capture_job.trigger` is structurally limited to:

- `{ kind: now, commandId, selectionIntent: none | conditional }`; every manual
  recapture uses a new command/key; or
- `{ kind: on_build, buildSnapshot: ExternalReference }`; it may create a build
  protection but never moves Draft selection.

There is no `periodic` job union member. Posting one fails schema validation
and cannot reach queue persistence.

### 3.3 Worker messages and capabilities

The worker contract defines `claim_lease`, `start_attempt`,
`record_navigation_start`, `renew_lease`, `request_staging_grants`,
`commit_attempt`, `fail_attempt`, and `abandon_attempt` request/response pairs.
The hosted API authenticates the local-agent installation before considering a
claim. Claim and start are separate: the attempt row and `attempt_started`
event commit before the worker may launch a browser.

It also defines one required immutable `CaptureProfileV1`. The profile carries
`profileId`, positive version, adapter/security-policy versions, and its own
canonical digest; exact `http|https`, ports 80/443, and `GET|HEAD` admission;
IDNA/canonicalization, DNS/peer/redirect/subresource rules; disposable-context,
cookie/storage/cache/extension/download/permission/filesystem/local-network/
inbound-listener isolation; WebSocket/WebRTC/popup policy; JavaScript mode
(`disabled | sandboxed_bounded`); viewport, device scale, region, encoding,
color/background, locale, timezone, user-agent, animation/reduced-motion, font,
media, load/stability, and warning-classification policy; and positive finite
limits for URL length, redirects/loop detection, DNS answers, connections,
top-level/frame/subresource/total requests, per-response/total bytes, frame
depth, popups, navigation/stability/script-CPU/total time, memory, processes,
worker concurrency, viewport/output pixels, raster bytes, diagnostic count/
field length, retries, lease duration, and heartbeat interval. Security rules
that define anonymous public-only capture cannot be relaxed by a job. Numeric
values are selected and tested in #39; the #28 numbers are evidence rather than
silent production defaults.

The signed lease capability is returned once and contains only:

`issuer`, `audience = vera-public-capture-worker/v1`, random `jti`, worker
installation ID, project/capture/configuration/job/lease IDs, lease epoch,
allowed attempt ID after start, frozen settings/profile IDs and digests,
allowed operations, staging byte/type limits, issue/expiry times, and a commit
nonce. The database stores only the JTI digest and scope digest. The raw token
is never logged, persisted in provenance, placed on a command line, forwarded
to the browser, or accepted as user/project membership.

An object-staging grant is separately random, single-purpose (`raster` or
`provenance`), single-use, attempt/lease-epoch bound, size/type constrained,
and shorter-lived than the lease. A staging object ID is not readable by a
project member and cannot become visible until the database publication
transaction creates an authorized artifact reference.

`commit_attempt` carries the lease capability, attempt and commit nonce,
staging object IDs, worker-observed digests/metadata, complete restricted
provenance, warnings, and the requested conditional-selection/build-protection
effect. The API/object service re-reads and verifies all bytes and policy
evidence; worker claims alone never commit a revision.

The isolated browser receives none of these capabilities. It receives only the
fixed attempt profile and guarded public request path; raster/diagnostic output
returns to the worker through bounded IPC.

### 3.4 Restricted provenance and failure evidence

`revision_observation` requires every group below. A value the worker cannot
observe is an explicit typed `unavailable` item with reason and observing
component; it is never silently omitted.

| Group | Required fields |
| --- | --- |
| Identity | Project, capture, configuration version, job, winning lease/epoch, attempt, revision/number, raster artifact, provenance artifact/manifest, optional comparison baseline, and change-signal IDs. |
| Authorization | Trigger, initiating actor/service, role/policy decision, request and decision IDs/times, membership/build recheck mode, and exact originating document/checkpoint/build reference when present. |
| Request | Restricted exact requested URL, redacted URL, canonical digest, benign query-key names, frozen settings/profile IDs and digests, requested region, idempotency scope/key digest, and request/enqueue times. No rejected secret value is retained. |
| Network | Controlled resolver/version/time; each A/AAAA answer and address class; admitted sets; actual peers; TLS result; restricted exact and redacted redirect chains; statuses; final exact/redacted URL and sanitized title; bounded response metadata; subresource/frame manifest digest; denials/failures; and request/byte/redirect counters. Synthetic test evidence must say synthetic and report zero live connections. |
| Runtime | Worker/local-agent build and installation, OS/container/sandbox identity, browser engine/build, adapter version, policy hash, clean-profile ID, `importedState: false`, initial/final cookie counts, locale/timezone/user-agent, viewport/scale/color/output, and blocked capabilities. |
| Timing/stability | Server and worker wall/monotonic start/end, actual navigation/load milestones, wait/stability rule/outcome, deadline/bounds reached, retries, lease history, and capture instant. Worker time is evidence; server time orders state. |
| Output | Region in source/normalized coordinates, output dimensions/encoding, artifact digest/length/MIME, decoder/verifier result, color/alpha, staging IDs, and commit verification result. No object locator is included. |
| Honesty/warnings | Warning codes, review classification, partial-state reason, redaction version, unavailable observations, and the exact statement that stored bytes/provenance are reproducible while a later live page is not guaranteed to match. |

`terminal_attempt_evidence` uses the same identity, authorization, request,
network, runtime, and timing groups available before failure, plus sanitized
terminal code, first denied class/bound, `navigationStarted`, lease disposition,
and explicit `revisionId: null`. It has no artifact/revision claim. Secret-
bearing admission rejection stores only the keyed fingerprint and reason, not a
restricted exact URL.

## 4. PostgreSQL persistence proposal

### 4.1 Shared conventions

- All IDs are PostgreSQL `uuid`; hashes are `bytea` with 32-byte checks; server
  times are `timestamptz`; positive sequences/versions are `bigint`.
- Evolvable states are `text` plus named `CHECK` constraints rather than
  PostgreSQL enums. Contract schema versions are explicit columns.
- Every project-owned table carries `project_id`. Composite unique keys and
  composite foreign keys include it so a reference cannot cross projects by
  UUID accident. Repositories always query by project and ID.
- No table uses `ON DELETE CASCADE`. The application/migration role receives no
  runtime `DELETE` permission for capture records.
- Exact URLs are application-level AEAD ciphertext with key version and AAD
  bound to project/capture/configuration/digest. Object locators are held behind
  `ImmutableObjectStorePort`, not returned by this schema. Ordinary audit and
  response rows retain only redacted displays/digests.
- `captures`, `capture_jobs`, `capture_leases`, and `capture_attempts` are
  optimistic current-state projections. Every accepted projection change and
  its append-only audit event occur in one transaction; direct projection
  writes outside repository transition functions are denied. The event stream
  remains the durable explanation of state.

### 4.2 Intent, configuration, job, lease, and attempt tables

| Table | Required columns and key constraints |
| --- | --- |
| `captures` | `project_id`, `capture_id` PK component, state, `current_configuration_version`, `next_revision_number` default 1, `row_version` default 1, creator and timestamps. `UNIQUE(project_id,capture_id)`; state check `draft|active|paused|retired`; positive version checks. It has no URL, latest revision, selection, or pin column. |
| `capture_configurations` | Project/capture/version composite PK and FK; schema version; canonical URL digest; bounded redacted display and query-key names; encrypted restricted-request envelope/key version; region/settings JSON validated against the shared definition; acquisition policy; capture profile ID/version; settings and prior-configuration digests; creator/time. Immutable. Policy check permits `now|on_build|periodic_reserved`; no execution flag can be true for the reserved value. |
| `capture_jobs` | Project/job PK; capture/configuration FK; executable trigger and trigger reference; initiating principal and commit recheck mode; authorization decision/membership version/time; request ID; idempotency-key digest and immutable request fingerprint; frozen settings/profile JSON and digests; retry budget; conditional selection intent; state, optional output revision, row version, request/enqueue/availability/terminal times. Trigger check is only `now|on_build`. Committed states require output revision; every other state requires null. |
| `capture_leases` | Project/lease PK; job/capture FK; positive epoch; worker installation; capability JTI/scope digests; state projection; issued/current-expiry/heartbeat/terminal times; row version. `UNIQUE(job_id,epoch)`, unique JTI digest, and one partial unique nonterminal lease per job. Renewal changes expiry/state projection and appends an event; it never expands the stored scope digest. |
| `capture_attempts` | Project/attempt PK; job/capture and lease FKs; positive attempt number; state; clean-profile ID; browser/adapter/security/profile versions/digests; start/navigation/stage/terminal times; sanitized terminal code/diagnostic digest; row version. `UNIQUE(lease_id)` enforces at most one attempt per lease; `UNIQUE(job_id,attempt_number)` preserves retry order. The start transaction commits before browser launch. |

Job states are `requested`, `queued`, `leased`, `running`,
`committed_ready`, `committed_review_required`, `rejected`, `failed`, and
`cancelled`. Lease projections are `issued`, `active`, `released`, `expired`,
or `revoked`; renewal is an event while remaining active. Attempt states are
`started`, `staged`, `committed`, `failed`, `cancelled`, or `abandoned`.
Capture transitions are exactly `draft -> active`, `active -> paused`,
`paused -> active`, and `draft|active|paused -> retired`. Job transitions are
`requested -> rejected|queued`, `queued -> leased`, `leased -> running`, and
`leased|running -> queued|committed_ready|committed_review_required|failed|
cancelled`; the return to queued is legal only after a lease expires/revokes
inside the frozen retry budget. Lease transitions are `issued -> active` and
`active -> released|expired|revoked`, with zero or more bounded renewal events.
Attempt transitions are `started -> staged -> committed` or
`started|staged -> failed|cancelled|abandoned`. Repository transition functions
lock the row, compare `row_version`, reject any other edge, update the
projection, and append the corresponding audit event.

### 4.3 Artifact, provenance, revision, and comparison tables

| Table | Required columns and key constraints |
| --- | --- |
| `capture_artifacts` | Project/artifact PK; kind/access class; opaque immutable object-store ID; digest, byte length, MIME; raster dimensions/encoding/color/alpha or provenance schema; verifier profile/version/time; encryption key version; creator service/time. Immutable. `UNIQUE(project_id,object_store_id)` and a project-scoped exact-byte candidate key over kind, digest, length, MIME, verified raster metadata, and verifier profile. Cross-project physical deduplication is disabled in v1. |
| `capture_provenance_manifests` | Project/provenance PK; capture/job/attempt FKs; evidence type `revision_observation | terminal_attempt_evidence`; unique provenance artifact FK of kind `capture_provenance`; schema version; manifest digest/length; redaction version; bounded sanitized summary JSON; created time. Immutable and `UNIQUE(attempt_id)`. Restricted bytes live only in the authorized immutable object; a revision may reference only `revision_observation`, while a failed/abandoned attempt may retain terminal evidence without a revision. |
| `capture_revisions` | Project/revision PK; capture/configuration/job/winning-attempt FKs; positive revision number; raster artifact FK; unique provenance FK; status; frozen settings/profile digests; committed time. Immutable. Unique `(capture_id,revision_number)`, unique job, unique winning attempt, and unique provenance enforce one output and one evidence bundle. |
| `capture_change_signals` | Project/change PK; capture/current revision and optional baseline revision composite FKs; corresponding artifact IDs; signal, six nullable difference flags, algorithm/version/time, and non-materiality const/version. Immutable. `UNIQUE(current_revision_id)`; initial requires no baseline, non-initial requires one; both revisions must share project/capture. |

The object service must stream-compare candidate bytes before reusing an
existing artifact; a matching digest alone is insufficient. A project/digest
advisory transaction lock serializes the compare/insert race. Metadata mismatch
or unequal bytes under the same candidate key is an integrity incident and
aborts publication. Even when the artifact row is reused, a new provenance
manifest, revision, and change signal are mandatory.

### 4.4 Use, selection, protection, and audit tables

| Table | Required columns and key constraints |
| --- | --- |
| `capture_revision_use_decisions` | Project/decision PK; capture/revision FK; decision and exact external context; actor/authorization decision; warning-set digest; effect digest; server time. Immutable. Unique effect digest and unique `(revision,context,decision)` prevent duplicate acknowledgment. Role checks are enforced by API and retained in evidence. |
| `capture_revision_selections` | Project/selection PK; capture/revision FK; exact target kind/resource/version/occurrence; monotonically allocated target sequence; previous and expected-previous selection FKs; reason; actor/authorization; optional use-decision FK; effect digest; server time. Immutable. Unique target sequence and effect digest. The transaction compares expected previous with the derived current selection; there is no mutable current-selection column. |
| `capture_revision_protections` | Project/protection PK; capture/revision FK; reason; exact source reference/version; actor/service authorization; effect digest; add time. Immutable. Unique `(revision,reason,source kind,source ID,source version)` and effect digest. |
| `capture_protection_releases` | Project/release PK; protection FK; actor/service authorization; reason; effect digest; release time. Immutable. `UNIQUE(protection_id)` and effect digest. Active protection is an added record with no release row. |
| `capture_audit_events` | Project/event PK; primary object kind/ID and positive object sequence; event type; actor/service; request/correlation IDs; policy/profile versions; before/after states; sanitized result/detail JSON; optional corrected event; server time. Immutable. `UNIQUE(project_id,primary_object_kind,primary_object_id,object_sequence)`. A correction points to an earlier event; it never updates it. |

Selections and protections use `AuthoringReferencePort` validation before
insert. Composite project/revision keys prevent capture-local cross-project
references; the stored authorization/reference decision proves why an external
opaque ID was accepted. A `review_required` revision needs a matching preview
acknowledgment or Producer release acceptance before its selection/build
protection can commit.

V1 has no retention-policy, eligibility, tombstone, prune, delete, schedule,
notification, or material-change table. All committed artifacts and provenance
remain referenced and retained. Physical object bytes cannot be removed while
any revision refers to them, and no v1 API can request removal.

### 4.5 Named constraints and required indexes

Issue #39's migration and migration tests must retain these named guarantees:

- `uq_capture_configuration_version` and
  `fk_capture_current_configuration` bind the current version to the same
  project/capture.
- `uq_capture_job_idempotency_scope` covers project, capture, initiating
  principal, trigger, and key digest; the stored fingerprint detects same-key
  different-payload misuse. `uq_capture_job_build` is partial on `on_build` and
  covers capture plus immutable build ID/version.
- `uq_capture_lease_epoch`, `uq_capture_active_lease` (partial on issued/active),
  `uq_capture_attempt_lease`, and `uq_capture_attempt_number` enforce one
  current epoch and one actual attempt per lease.
- `uq_capture_revision_number`, `uq_capture_revision_job`,
  `uq_capture_revision_attempt`, `uq_capture_revision_provenance`, and
  `uq_capture_change_current_revision` enforce immutable cardinality.
- `uq_capture_artifact_exact_candidate` is project scoped and never used for
  authorization; byte comparison precedes reuse.
- `uq_capture_selection_target_sequence`, `uq_capture_selection_effect`,
  `uq_capture_protection_source`, `uq_capture_protection_effect`, and
  `uq_capture_protection_release` make append-only effects idempotent.
- `uq_capture_audit_object_sequence` preserves ordered object history.
- Work indexes cover queued jobs `(state,available_at,requested_at)`, current
  lease expiry `(expires_at)` for nonterminal leases, capture jobs/revisions by
  `(project_id,capture_id,requested_at|revision_number DESC)`, target selections
  by target key/sequence descending, active protections by revision, and audit
  reads by `(project_id,server_time,event_id)` and correlation ID.
- There is no global URL, URL-digest, object-key, path, or artifact-digest lookup
  endpoint. Any internal URL-digest index begins with `project_id` and is an
  optimization only.

Immutable tables receive a database trigger that rejects `UPDATE` and
`DELETE`. Runtime roles have no permission to disable it. Projection tables
reject `DELETE`, and their state updates occur only through transaction
functions that also append audit. Migration-owner authority is not available
to the running API.

## 5. REST and authorization boundary

### 5.1 Authorized project API

All routes are under `/v1/projects/{projectId}` and authenticate before any
resource lookup. Unknown projects/resources and callers without Viewer
membership return the same nonrevealing response.

| Route | Minimum authority and exact effect |
| --- | --- |
| `POST /captures` | Editor. Validate URL syntax/secret policy before domain persistence, then create stable intent plus configuration v1 and audit. Capture-on-add is a separate explicit `Now` job so a failed acquisition cannot erase the card. |
| `POST /captures/{captureId}/configurations` | Editor plus expected capture row version. Create a new immutable configuration and advance only the current projection/event. Retired captures cannot be edited or resurrected. |
| `POST /captures/{captureId}/jobs` | Editor/Producer for `Now`; Editor for preview `On build`; Producer for release `On build`. Revalidate exact external build reference and idempotency scope before creating one queued job. Paused/retired/Draft captures reject. |
| `GET /captures/{captureId}` and `/jobs/{jobId}` | Viewer only through an authorized capture/document/history/build reference they may view. Sanitized views only. |
| `GET /captures/{captureId}/revisions` and `/revisions/{revisionId}` | Viewer only through an authorized capture/document/history/build reference they may view. Exact immutable revision/artifact descriptors; no object locator or restricted provenance bytes. |
| `GET /artifacts/{artifactId}/content` | Viewer only after the API resolves a currently authorized project reference to the artifact. Stream a reverified inert raster as `image/png` with `nosniff`, non-executable disposition, and private/no-store caching, or return a shorter-lived reference-specific read grant with the same restrictions. Never serve HTML, script, browser profiles, downloads, or a raw object key. |
| `GET /revisions/{revisionId}/provenance` | Viewer with a visible project reference. Return restricted evidence through the API or a short-lived reference-specific read grant and append a read-grant audit event. The digest/ID alone never works. |
| `POST /revisions/{revisionId}/use-decisions` | Editor/Producer preview acknowledgment; Producer only for release acceptance. Append only. |
| `POST /revisions/{revisionId}/selections` | Editor/Producer, exact target authorization, expected prior selection, and any required use decision. Append only; conflict changes no prior record. |
| `POST /revisions/{revisionId}/pins` and `POST /pins/{pinId}:release` | Editor/Producer explicit pin only. System reference protections use an authenticated internal owning-subsystem command. Release removes one reason only. |
| `GET /captures/{captureId}/audit-events` | Viewer; sanitized event view. Restricted attempt/provenance access is separate and audited. |

Viewer can never mutate. The API rechecks current membership on every call.
Role removal ends new writes immediately; commit follows §6.2's recheck rule.
No route accepts an object key, local path, source-product permission assertion,
browser session, cookie jar, or arbitrary capability scope.

### 5.2 Worker API

Worker routes are under `/v1/capture-worker` and require both the registered
local-agent installation credential and the matching lease capability after
claim. A worker cannot choose a project, URL, schedule, selection, pin, review
decision, retry budget, profile, or retention action. The server chooses one
queued job whose required profile the installation supports.

A missing, unknown, mismatched, revoked, or expired worker/lease capability
returns one byte-equivalent `invalid_or_expired_job_capability` response; it
does not reveal whether a job, project, lease, epoch, or object exists. A
current capability with a stale epoch receives `job_not_committable` and the
late attempt becomes append-only evidence only.

The browser is not an API principal. It cannot call hosted or object-storage
routes. Every network-bearing browser request remains behind the egress guard.

### 5.3 Exact error/privacy semantics

Every error is `{ schemaVersion, requestId, code, safeMessage, retryable,
fieldPaths[] }`. It never echoes a supplied value, exact URL, query value,
address, page title, response body, capability, object ID not already visible,
object locator, local path, stack trace, or untrusted browser diagnostic.

| HTTP | Code | Meaning |
| --- | --- | --- |
| 400 | `request_invalid` | Closed-schema/type/length failure; safe JSON pointers only. A `periodic` job request lands here. |
| 401 | `authentication_required` or `invalid_or_expired_job_capability` | One generic human or worker authentication failure respectively. |
| 403 | `action_not_allowed` | Current project member may know the resource but lacks the required role/action. |
| 404 | `resource_not_found` | Unknown project/resource and nonmember access are intentionally indistinguishable. |
| 409 | `version_conflict`, `idempotency_key_reused`, `selection_conflict`, `revision_requires_review`, or `job_not_committable` | Safe concurrency/lifecycle conflict. Duplicate same-fingerprint delivery is not an error; it returns the existing outcome. |
| 413 | `capture_resource_limit` | A configured input/staging bound was exceeded; no offending content echoed. |
| 422 | `capture_request_denied` | Sanitized policy reason such as scheme, port, userinfo, secret shape, nonpublic address, redirect, peer, or subresource denial. Initial admission creates no job/attempt/revision; runtime denial terminates the already-authorized job with no revision. |
| 503 | `authorization_unavailable`, `capture_worker_unavailable`, or `object_verification_unavailable` | Required authority/safety component cannot make the guarantee; fail closed and do not commit. |

The unauthorized and nonexistent cases are tested for identical status, code,
body shape, and absence of resource-specific fields. Timing equality is not
claimed; implementation must authorize project visibility before querying a
named capture and avoid existence-dependent response branches.

## 6. Atomic publication, recovery, and concurrency

### 6.1 Before navigation

1. The human/service API authenticates, obtains current project/action
   authorization, validates the closed request, rejects secret-bearing or
   structurally unsafe URLs without retaining them, validates the capture
   lifecycle/configuration/build reference, and resolves the idempotency scope.
2. A same-scope key with the same fingerprint returns the existing job/outcome.
   The same key with a different fingerprint returns
   `idempotency_key_reused`. Only then may one job and its request/audit events
   commit.
3. Lease claim locks the queued job, increments the epoch, records the narrow
   scope/JTI digests and expiry, changes the projection, and appends lease/job
   events in one transaction. One partial unique active-lease index resolves
   claim races.
4. `start_attempt` inserts the one attempt for that lease and its start event,
   then returns acknowledgment. Only after that acknowledgment may the worker
   launch the disposable browser.
5. The worker repeats URL/query admission and applies controlled DNS/public
   address/actual-peer policy to every top-level, redirect, frame, and
   subresource request. Any inability to verify a peer denies the request; no
   direct browser fallback exists.

### 6.2 Commit-time algorithm

The worker stages complete raster and provenance candidates under two
attempt/epoch-bound, non-readable object grants. Object service verification
checks length, digest, MIME, raster decoder/dimensions/encoding, provenance
schema/canonicalization, and staging-grant scope. It promotes bytes to an
immutable internal object ID before the database transaction, but an object is
not published or readable until the database creates a project reference.
Interrupted/unreferenced staging is retained for evidence under this contract;
no cleanup deletion is authorized.

The hosted API then executes one serializable/retry-safe transaction:

1. Lock project-scoped job, capture, current lease, and attempt rows. Require
   the supplied job/attempt/nonce, lease epoch/scope, nonexpired server time,
   nonterminal job, staged attempt, frozen configuration/settings/profile, and
   object verification receipts to match.
2. Recheck the initiating actor's current Editor/Producer authority for
   `Now`, or validate the already-authorized immutable build snapshot for
   `On build`. If the deployed authorization adapter cannot make this check
   transaction-coupled, abort with `authorization_unavailable`.
3. Acquire the project/digest advisory lock. Reuse an artifact only after the
   object service proves byte-for-byte equality and verified metadata equality;
   otherwise insert a new immutable raster artifact. A collision/mismatch
   aborts as an integrity incident.
4. Allocate `revision_number` from the locked capture projection. Insert the
   immutable provenance artifact/manifest, revision, and change signal. Unique
   job, attempt, provenance, and revision-number constraints are the final
   exactly-once guard.
5. For explicit `capture_and_use`, compare the exact target's current derived
   selection to `expectedPreviousSelectionId`. If it matches, insert one
   selection and its Draft protection. If it does not, keep the valid revision
   unselected, record `selection_conflict` in the job result/audit, and do not
   alter another author's selection.
6. For a `ready` `On build` result, require the exact immutable build reference
   and insert its preview/release protection in this same transaction. A
   `review_required` result commits as an unselected candidate without a build
   protection; the build waits for the separately authorized use-decision
   transaction to add that exact protection. Never alter Draft selection and
   never fall back to an older revision silently.
7. Mark the attempt committed, release the lease, set the job's single output
   and terminal classification, advance the capture revision allocator, and
   append artifact/provenance/revision/change/selection/protection/attempt/
   lease/job audit events.
8. Commit, then return the stored job result. No response construction invents
   a second effect.

If a review-required revision lacks the required use decision for a requested
selection/build, the transaction commits it as an unselected candidate without
that use protection and records the blocked-use result. The authoring/build
action waits for a later explicit decision on the exact revision; it never
silently treats warnings as accepted or reruns capture under the same job.

### 6.3 Failure and recovery outcomes

| Failure point | Durable result |
| --- | --- |
| Initial auth/schema/secret/URL denial | Sanitized denial audit only; no capture job, lease, attempt, artifact, revision, selection, or protection. |
| DNS/peer/redirect/subresource denial after authorized job | Terminal job/attempt evidence; no revision. A safe raster with only profile-classified visible warnings may instead commit `review_required`. |
| Browser/sandbox/bound/decoder/provenance failure | Terminal attempt/job evidence and retained nonpublished staging; no revision. |
| Lease expiry/revocation before commit | Attempt `abandoned`; late commit denied. Retry, if within frozen budget, uses a new lease epoch and attempt under the same job. |
| Crash before database commit | Zero visible revision/effects. Immutable staging may remain inaccessible. Existing prior history is unchanged. |
| Database commits, response is lost | Retry by job/idempotency key or commit nonce returns the stored job/revision/selection/protection IDs. It never launches a new browser. |
| Duplicate worker commit or another attempt already won | Unique job output returns the existing winner; late attempt records duplicate/abandoned evidence and cannot add selection. |
| Conditional selection loses a race | New revision remains valid and unselected; no prior selection changes. |
| Artifact/provenance bytes later fail integrity read | Integrity incident/hold and nonrevealing failure; never overwrite the artifact, provenance, or revision under the same ID. |
| Cancel races with commit | Row lock orders them. Cancel first prevents commit; commit first remains immutable and a later cancel cannot erase it. |

## 7. Fictional end-to-end traces

These examples are review aids, not live records or network instructions.

### 7.1 `Now`, selection, build protection, and lost reply

1. Editor `10000000-0000-4000-8000-000000000001` is currently authorized in
   fictional project `10000000-0000-4000-8000-000000000002` and creates Capture
   `10000000-0000-4000-8000-000000000003`. Configuration v1 stores a restricted
   encrypted `https://capture.example.org/bulletin?lang=en`, while normal views
   contain only a redacted display, query key `lang`, and digest.
2. The Editor submits a new `Now` command and idempotency key with conditional
   selection for fictional Draft occurrence
   `10000000-0000-4000-8000-000000000004`, expecting no prior selection. One
   job is queued after authorization and safe structural admission.
3. Registered worker `10000000-0000-4000-8000-000000000005` obtains lease
   epoch 1, starts one recorded attempt, launches a clean browser only after
   acknowledgment, and produces verified raster/provenance candidates through
   the guarded public-only path.
4. The single commit transaction creates raster artifact
   `10000000-0000-4000-8000-000000000006`, provenance
   `10000000-0000-4000-8000-000000000007`, revision 1
   `10000000-0000-4000-8000-000000000008`, an
   `initial_observation` signal, selection sequence 1, and the Draft-selection
   protection; then it terminates attempt/lease/job and appends audit.
5. A later preview build validates that exact revision and adds a distinct
   `preview_build` protection. Releasing the explicit Draft selection cannot
   release the build protection.
6. If the original commit response was lost, replaying the commit nonce or API
   idempotency key returns those same IDs. No browser runs again and no second
   selection or protection appears.

The URL did not grant access; current membership did. The object ID/digest did
not grant artifact access; the authorized Draft/build reference did.

### 7.2 Same bytes and changed bytes

A deliberate manual recapture uses a new command/key and therefore a new job,
lease, attempt, provenance manifest, revision 2, change signal, and audit
history. If the verified raster is byte-for-byte equal, revision 2 references
the same artifact and reports `same_exact_bytes`; it stays unselected. A later
changed raster creates a new artifact and revision 3 with
`different_exact_bytes`. Revisions 1 and 2, their provenance, selection, and
both protection reasons remain unchanged.

### 7.3 `On build`

An authorized immutable preview/release build request submits one `On build`
job keyed by Capture plus exact build ID/version. A duplicate build delivery
converges on that job. Its successful transaction creates a new observation and
the exact build protection only; it never moves the authoring occurrence. A
capture failure blocks the build or requires a separately authorized explicit
choice of a named older revision. There is no `latest` resolution or silent
fallback.

## 8. Migration, activation, and rollback

### 8.1 Additive expand migration

Issue #39 may add one transactionally applied migration named
`public_page_capture_v1_expand` in the authoring API's chosen migration system.
It acquires the repository/application migration lock, creates the tables,
named checks, composite FKs, indexes, immutability/transition functions and
least-privilege grants from §4, records its checksum/schema version, and leaves
`public_page_capture_execution` disabled.

There is no legacy backfill. The migration asserts that no conflicting tables
or schema-version row exists and never imports #28 output. Schema application
and verification run before any route or lease claim is enabled. DDL is
transactional; a failure leaves no partial database schema.

Activation is an application capability, not a data migration:

1. validate all three shared roots and generated currentness;
2. apply/verify the empty additive schema;
3. start API read/denial paths with lease issuance disabled;
4. prove current project authorization and object-store verification adapters;
5. run synthetic `Now`, manual recapture, and `On build` security/fault tests;
6. enable only those executable triggers for the controlled acceptance
   environment; and
7. retain `Periodic`, scheduler, notifications, and all delete permissions as
   absent.

No production deployment or real-page capture is authorized by issues #38 or
#39.

### 8.2 Compatibility window

The migration is additive, so the pre-capture application binary can run with
the new unused tables present. The new service refuses capture messages without
the exact v1 media type/schema version. Old clients see no new required field
in any existing contract. New clients must treat `503 authorization_unavailable`
as a hard stop, not fall back to an unauthenticated/local path.

All mutable projections include `row_version`; rolling forward code may add
nullable columns/indexes in later expand migrations but cannot reinterpret an
existing schema version or immutable record. Contract bytes and database
migration checksums are retained with acceptance evidence.

### 8.3 Fail-closed rollback

- **Before activation and while every capture table is empty:** the down step
  may revoke capture grants and drop only the newly created objects after
  explicit zero-row and no-object-reference assertions. It fails rather than
  cascade. This is migration rollback, not retention.
- **After any capture/configuration/job/attempt/artifact/provenance/revision/
  selection/protection/audit row or staged immutable object exists:** destructive
  down migration is forbidden. Disable lease issuance and all capture writes,
  keep read/integrity access for authorized references, deploy the prior
  application binary against the additive database, and roll forward a fix.
  No committed or staged evidence is deleted.
- **After a partially deployed service:** disabling the capability prevents new
  leases; current leases are revoked/allowed to expire and late commits fail.
  Already committed revisions remain readable. Database/object reconciliation
  is a non-destructive report only.
- Restoring a backup never rewrites a retained build/checkpoint to a newer
  revision and never recycles IDs or revision numbers.

The rollback contains no pruning, tombstone, garbage-collection, or object
deletion policy. Any future destructive behavior requires its own Producer-
approved contract and audited product flow.

## 9. Required automated and adversarial verification for #39

### 9.1 Contract and compatibility tests

- All three schemas compile together with existing schemas; representative
  roots validate and unknown fields/message types fail.
- Every bounded string/array, UUID, timestamp, digest, state-specific required
  field, `review_required` decision, and executable-trigger union has positive
  and negative tests.
- A `periodic` job, object locator, raw capability, cookie/storage state,
  source-product permission claim, path, or secret query value cannot validate
  in a normal API message.
- Generated TS/Python roots import and typecheck; existing root schemas,
  generated named types, fixtures, and compiler goldens remain byte-identical.

### 9.2 Authorization and privacy tests

- Unknown resource and nonmember access yield byte-equivalent 404 bodies;
  Viewer mutation yields safe 403; membership removal blocks the next request.
- Commit-time actor recheck and immutable-build authorization are exercised;
  authorization-adapter outage yields 503 and no publication.
- Artifact/restricted-provenance reads require a current project-owned visible
  reference; URL, path, object ID, revision ID, and digest alone all fail.
- Raw human/worker/staging capabilities never appear in logs, audit, database
  evidence JSON, provenance, command lines, browser environment, or errors.
- Secret-shaped URLs are rejected before job creation and are absent even from
  restricted evidence; only a keyed fingerprint and sanitized class remain.

### 9.3 Public-only egress and ambient-state tests

- Reject parser ambiguity, alternate numeric IPs, raw IP literals, userinfo,
  unsupported schemes/ports, local/metadata names, suspected query secrets,
  and every IPv4/IPv6 loopback/private/link-local/CGNAT/benchmark/
  documentation/multicast/unspecified/reserved/transition/mapped class before
  navigation.
- Reject mixed public/nonpublic DNS, DNS rebind, actual-peer mismatch, unsafe
  redirect, redirect loop/limit, private frame/subresource, WebSocket/WebRTC,
  direct browser-network fallback, and an unverifiable peer.
- Prove the positive synthetic fixture never reaches a real external or private
  service and labels its DNS/TLS/peer data synthetic/unavailable.
- Launch a disposable profile for every actual attempt; prove no attached
  browser, extension, cookie, cache, local/session storage, password/client
  certificate, proxy secret, environment credential, local file, inbound
  listener, or prior-attempt state is available. Page-set cookies do not reach
  another attempt.

### 9.4 Resource, integrity, failure, and concurrency tests

- Enforce finite URL/DNS/redirect/request/frame/response/total-byte/pixel/
  raster/diagnostic/time/CPU/memory/process/concurrency/retry/lease/heartbeat
  fields from the immutable hashed profile. The numeric profile is selected and
  Producer-reviewed in #39; #28 values are evidence, not silent production
  defaults.
- Reject truncated/corrupt/oversized/wrong-type raster, unsafe decode path,
  dimensions/encoding mismatch, missing or invalid provenance, staging-scope
  mismatch, and post-stage mutation before publication.
- Fault-inject before/after job, lease, attempt, each object stage/promotion,
  byte verification, artifact reuse, provenance/revision/change insert,
  conditional selection, protection, terminal transitions, transaction commit,
  and response. At every point, authorized readers see either the old complete
  history or the new complete bundle, never a partial revision.
- Exercise simultaneous lease claims, renew/expire/revoke, retry epochs, late
  commits, two workers, duplicate API/worker deliveries, same key/different
  fingerprint, cancellation races, conditional-selection races, same-byte
  artifact races, lost acknowledgments, and corruption of retained bytes.
- Prove one job has at most one revision, one lease at most one attempt, one
  attempt at most one revision, one current revision at most one change signal,
  and every successful new command a distinct observation even with same bytes.
- Prove releasing an explicit pin leaves Draft/checkpoint/build/evidence/hold
  protections active and no v1 path deletes anything.

### 9.5 Migration tests

- Apply the expand migration to a clean PostgreSQL database; verify every named
  constraint/index/trigger/grant and feature-disabled default.
- Reapply/check checksum behavior without duplicating objects; abort cleanly on
  a conflicting partial schema.
- Insert adversarial cross-project and cardinality rows directly and verify the
  database rejects them even without API validation.
- Run the empty-only down path successfully, then prove any row/object reference
  makes it refuse destructively.
- Start the pre-capture binary against the expanded unused schema and the new
  binary with execution disabled; both remain healthy.
- Run repository validation and a schema/object/database reconciliation report
  that performs no cleanup.

## 10. Accepted-#27 traceability matrix

| #27 obligation | Exact #38 mapping |
| --- | --- |
| Separate Capture, job, lease, attempt, revision, artifact, provenance, change, selection/evidence, and protection identities | §§3–4 tables and closed shared definitions. Spotlight evidence internals remain #40; the exact revision-bound external reference and protection obligation are accepted here. |
| Ten cardinality/immutability invariants | Unique job/attempt/provenance/change/revision constraints in §§4.2–4.5; no latest pointer; composite project FKs; immutable triggers; §6 transaction and duplicate recovery. |
| Capture/job/lease/attempt lifecycle | Exact state sets and transition repository functions in §4.2; routes and failure behavior in §§5–6. |
| Ready/review-required and use decisions | Revision status plus append-only use-decision table and role rules in §§3.2, 4.3–4.4, and 5.1. Hard failures create no revision. |
| Selection evidence remains revision-bound and stale/remap never silent | `ExternalReference(kind=selection_evidence)` requires exact project/resource/version; protection targets the original revision. Evidence payload/OCR/remap is explicitly deferred to #40/#41. |
| Hosted API is policy authority; worker/browser/artifact/build scopes stay narrow | Authority ports §1.3, capability split §3.3, route boundaries §5, and commit recheck §6. Browser gets no authority. |
| Roles, membership removal, and nonrevealing failure | §§1.3, 5.1, 5.3, 6.2, and authorization/privacy tests §9.2. |
| URL/hash/path is not authorization and artifact is inert/private | Project-scoped descriptors/no locators §§3–5; authorized read route; raster verification; dedicated restricted provenance. |
| Public-only URL/redirect/DNS/peer/subresource and clean browser rules | Restricted provenance §3.4, worker/egress boundary §§3.3 and 6.1, and exhaustive tests §9.3. |
| Immutable hashed resource/profile fields | Configuration/job/provenance fields §§3–4 and test requirement §9.4. #39 selects tested numeric production values. |
| Complete honest provenance and append-only audit | Provenance groups §3.4, manifest/artifact/audit tables §4, and access/error rules §5. |
| Idempotency, at-least-once execution, exactly-once effects, late/uncertain commits | Job scope/constraints §4.5, worker nonce/capability §3.3, transaction/recovery §6, concurrency tests §9.4. |
| Trigger-specific selection | Closed `Now`/`On build` unions §3.2; conditional selection and build protection §§6.2 and 7. Draft is never moved by `On build`. |
| Exact-byte dedup is not observation dedup; change is non-semantic | Artifact byte-compare rule §4.3, mandatory new revision/change §6, and fictional recapture §7.2. |
| Append-only selection, independent protection reasons, no destructive retention | §§3.2, 4.4, 6.2, 7.1, 8.3, and protection tests §9.4. There is no delete API/table/grant. |
| Stored observation is reproducible; live page is not promised | Required provenance honesty group §3.4 and every revision view §3.2. |
| Production Periodic remains deferred | Config may display only `periodic_reserved/disabled`; executable job schema and database check permit only `now|on_build`; no schedule/notification/retention/delete surface exists. |
| Bounded capture implementation handoff | Existing issue #39 consumes exactly this accepted delta; §12 keeps it dependency-blocked and forbids extra contract invention. |

## 11. Explicitly deferred items

The following are intentional mappings, not omissions:

- **Periodic execution:** reserved display vocabulary only. No scheduler,
  schedule slot, frequency, timezone, retry/backoff, unattended lease,
  material-change evaluator, notification, or periodic pruning. Revival still
  requires the product-spec trigger and a new Producer-approved issue.
- **Retention eligibility and deletion:** no numeric count/age, dry-run
  eligibility workflow, tombstone, garbage collection, delete, recovery window,
  backup interaction, or staging cleanup. V1 retains everything. A later dry-
  run or destructive step needs its own Producer-approved policy contract.
- **SelectionEvidence payload/OCR/remap:** #38 accepts only the exact immutable
  revision-bound external reference and protection duty. Issues #40/#41 own the
  OCR/suggestion/confirmation/remap contract and implementation.
- **UI and authoring-document shape:** issue #14 and later contract slices own
  presentation and `ScriptDocument` binding. A UI cannot weaken this authority.
- **Compiler/build materialization:** this backend may validate an exact build
  reference and pin a revision; adding capture dependencies to compiler/build
  schemas, motion, YouTube composite, Resolve, or release delivery is later
  work.
- **Authenticated/paywalled or attached-browser capture:** user-supplied Image
  remains the fallback. No cookies, credentials, source-product tokens, or
  browser profile enter this service.
- **Cross-project physical deduplication:** disabled in v1. A future storage
  optimization must prove no existence, authorization, encryption, or retention
  coupling before approval.
- **Production deployment:** #39 itself prohibits production data, network,
  credentials, deployment, upload, or sharing during implementation/acceptance.

## 12. Bounded implementation handoff

The separately bounded follow-up is existing GitHub issue #39, “Implement the
production public-page capture API and local-worker backend.” It is unclaimed
and currently dependency-blocked by open #38. This investigation creates no
task and does not promote, claim, dispatch, or edit #39.

After #38 is explicitly accepted and closed `Done` by the authorized roadmap
flow, the steward may evaluate `npm run roadmap -- ready 39`. Issue #39 must:

1. implement only the three accepted roots and migration boundary in §2/§8;
2. plan and justify any new runtime dependency before adding it;
3. use only controlled synthetic public fixtures and prove no real private or
   external capture occurs;
4. retain all exclusions and deferred items in §11;
5. stop for a new contract-change note if implementation requires another
   field/root/table/authority or an existing schema/fixture/golden edit; and
6. remain `In review` until its own Producer acceptance.

## 13. Acceptance-criteria mapping

| Issue #38 acceptance criterion | Evidence in this proposal |
| --- | --- |
| Map every #27 identity/cardinality, authorization, idempotency, lease, provenance, selection, pin/protection, and failure invariant | §§1, 3–7, and exhaustive matrix §10; deliberate deferrals §11. |
| State compatibility, rollback, generated types, fixture/golden effects, and transaction boundaries without Periodic/deletion | Contract-change ledger §2, transaction §6, migration/rollback §8, and absent surfaces §§4.4/11. |
| Specify threat tests for network denial, isolation, bounds, late commits, duplicates, partial publication, and nonrevealing authorization | §9. |
| Confirm URL/path/hash is not authorization, revision is immutable, and same bytes remain separate observations | §§3–7 and Producer steps 2–4 below. |
| Identify a separate bounded implementation issue still blocked until acceptance | §12: existing dependency-blocked issue #39; no new task created. |

## 14. Producer acceptance checklist

Automated repository evidence is reported on issue #38 with the review commit.
The following are Producer judgment checks. Run them in order:

1. Open this document at §2 and review the three-file contract-change ledger.
   **Expected:** it adds capture API, worker, and restricted-provenance v1 roots
   without editing the four existing root contracts; it names generated TS and
   Python changes, only new fictional test data, no compiler golden change, and
   a stop condition for any extra delta.
2. Read §§3–5, then trace the fictional `Now` path in §7.1 from actor
   authorization through lease, attempt, artifact, provenance, revision,
   change signal, conditional selection, Draft protection, later build
   protection, and duplicate-response recovery.
   **Expected:** authorization comes only from current project membership; a
   URL, path, object ID, revision ID, or hash grants nothing; one job/attempt
   produces at most one immutable revision; the build names that exact revision;
   and replay returns the same effects.
3. Review the persistence tables and named constraints in §4 plus the commit
   algorithm/failure matrix in §6.
   **Expected:** partial object/database work is never visible as a revision;
   late epochs and duplicate workers cannot win; lost replies cannot rerun a
   browser; selection conflict leaves a new unselected candidate; there is no
   mutable latest/selected/pinned field and no update/delete of immutable rows.
4. Read the same-/changed-byte trace in §7.2 and protection rules in §4.4.
   **Expected:** same bytes may reuse only a verified project artifact after
   byte comparison, while a new attempt, provenance manifest, revision, change
   signal, and audit remain distinct; releasing one pin cannot defeat Draft,
   checkpoint, build, evidence, or hold protection.
5. Review API/worker separation and exact errors in §5, provenance in §3.4,
   and threat tests in §9.
   **Expected:** the browser has no hosted/object/user credential or ambient
   profile; every redirect/frame/subresource/actual peer is checked; resource
   bounds are mandatory; secret URLs are not retained; unauthorized and unknown
   resources are nonrevealing; #28 synthetic network evidence is never labeled
   live production proof.
6. Review migration/rollback §8 and deferrals §11.
   **Expected:** expansion starts disabled and needs no legacy import; empty-only
   rollback may remove unused schema, but any retained evidence forces
   disable-and-roll-forward with no deletion; `Periodic`, scheduler,
   notifications, materiality, OCR/Spotlight, UI, compiler/Resolve, authenticated
   capture, cross-project dedup, and destructive retention remain impossible or
   separately bounded.
7. Open issue #39 and confirm it remains unclaimed and dependency-blocked by
   #38; compare its scope with §12.
   **Expected:** it is the already-identified implementation slice, no new task
   was created, and it cannot become Ready until this contract is explicitly
   accepted/Done through the roadmap flow.
8. Record exactly one response on issue #38:
   - acceptance: `Accepted production capture schema and migration boundary.`
   - failure: `Issue #38 acceptance failed at checklist step <number>: <first unsafe or missing mapping>.`

Leave issue #38 `In review` until that response is explicit. Agent self-report,
passing checks, silence, or acceptance of #27/#28/#33 never closes this issue.
