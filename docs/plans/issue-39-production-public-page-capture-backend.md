# Issue 39 plan — production public-page capture API and local worker

## Objective

Implement GitHub issue #39 exactly from the Producer-accepted #27 lifecycle and
security contract and the Producer-accepted #38 schema/migration boundary.
The result is a production-shaped hosted API, PostgreSQL persistence adapter,
immutable object-store seam, and local Chromium worker that can be exercised
entirely with controlled synthetic public fixtures. It does not ship a browser
authoring interface or deploy production infrastructure.

## Authority and prerequisites

- The VERA roadmap is the live scope and ownership authority. Before claim,
  issue #39 was `Ready`, exactly routed to `model:sol` / `effort:max`, marked
  `Automated`, dependency #38 was closed and `Done`, and no other claim existed.
- This task runs as `gpt-5.6-sol` at `max`, uses task
  `01a081c4-981f-7570-a944-fc7dc40cc2cd`, and claimed the dedicated branch
  `codex/issue-39-public-capture-backend` from `origin/main`.
- Accepted #27 commit `9143518` supplies the immutable identities, role and
  authorization rules, public-only trust boundary, provenance, idempotency,
  lease/attempt, exact-byte deduplication, selection, protection, failure, and
  deferred-Periodic requirements.
- Accepted #28 commits `47a3569` and `fcdea1c` are evidence for isolated
  Chromium, zero ambient state, immutable local publication, exact-byte reuse,
  and crash/lost-response behavior. Their offline transport, synthetic network
  claims, macOS-only storage, single writer lock, and lack of project
  authorization are not production assumptions or migration inputs.
- Accepted #38 commit `f35f85f` authorizes exactly three new v1 schema roots,
  additive generated exports, the PostgreSQL shape, API/worker separation,
  atomic publication/recovery rules, and the empty-only rollback boundary.

## Scope

1. Add exactly the three closed Draft 2020-12 roots approved by #38:
   `PublicPageCaptureApiV1`, `PublicPageCaptureWorkerV1`, and
   `PublicPageCaptureProvenanceV1`; generate additive TypeScript/Python types
   and add public-safe examples under `tests/data/issue_39_public_page_capture/`.
2. Add one TypeScript workspace, `@vera/public-page-capture`, containing:
   - closed-message validation and sanitized REST routing under project-scoped
     and worker-scoped paths;
   - injected `ProjectAuthorizationPort` and `AuthoringReferencePort` checks so
     no URL, ID, digest, locator, renderer visibility, or worker token becomes
     project authority;
   - opaque, signed, expiring lease and staging capabilities whose raw bytes
     are never persisted or returned after first issuance;
   - authorized `Now`, deliberate manual recapture, and immutable `On build`
     job admission with exact idempotency/fingerprint behavior;
   - lease epochs, one attempt per lease, retry under one job, late-commit
     denial, terminal attempt evidence, and lost-response recovery;
   - immutable object staging and verification, a single transaction that
     publishes the artifact/provenance/revision/change/audit bundle, byte-for-
     byte project-scoped artifact reuse, conditional selection, and independent
     append-only protection/release records; and
   - authorized raster/provenance reads that expose neither object locators nor
     restricted evidence through identifiers alone.
3. Add the additive `public_page_capture_v1_expand` PostgreSQL migration,
   named constraints/indexes/immutability guards/least-privilege roles, disabled
   execution default, checksum record, and fail-closed empty-only down path.
   Add a `pg` repository that uses project-qualified queries, serializable
   transactions, row locks, unique constraints, and advisory locks.
4. Add a local worker that launches one disposable Chromium context only after
   `start_attempt` is durably acknowledged. Browser traffic has no direct
   socket fallback: every top-level, redirect, frame, and subresource request
   is intercepted and fulfilled through a public-only egress guard that
   canonicalizes URLs, rejects secret shapes and nonpublic DNS sets, pins
   admitted addresses, and verifies the actual connected peer. The browser
   receives no API, worker, staging, object-store, environment, cookie, profile,
   local-file, listener, WebSocket, WebRTC, download, or device authority.
5. Freeze and hash one conservative v1 capture profile: a 1920x1080 CSS
   viewport at scale 2, producing a 3840x2160 PNG for routine zoom inspection,
   PNG/sRGB, UTC/en-US, bounded sandboxed JavaScript, no interaction, a fixed
   settle rule, ports 80/443, GET/HEAD only, zero popups, finite URL/DNS/
   redirect/request/frame/byte/pixel/raster/diagnostic/time/CPU/memory/process/
   concurrency/retry/lease/heartbeat limits, and warning-to-review rules. Tests
   exercise every bound; changing it later creates a new profile version.
6. Provide one synthetic acceptance command. Its transport never opens a real
   socket and reports DNS/TLS/peer data as synthetic/unavailable. It exercises
   safe initial/same-byte/changed-byte captures, duplicate delivery, an unsafe
   redirect/private-peer denial before browser navigation/publication, lease
   loss/crash recovery, receipts/history, and zero ambient state.

## Explicit exclusions

- No authoring UI, #14 browser design, Tiptap/Yjs integration, or
  `ScriptDocument`/compiler/build-manifest binding.
- No authenticated, paywalled, attached-browser, extension, cookie/profile,
  client-certificate, source-product credential, or user-secret capture.
- No executable `Periodic` message, scheduler, frequency/timezone/backoff,
  unattended monitoring, notification, material-change decision, or automatic
  selection/replacement.
- No OCR, Spotlight, selection-evidence payload/remapping, YouTube composite,
  motion/drift/compositing, transitions, Resolve, upload, sharing, or deployment.
- No retention eligibility, pruning, deletion, tombstone, garbage collection,
  staging cleanup, destructive post-data rollback, or production data access.
- No fourth schema root, edit to an existing root, cross-product contract,
  existing fixture/golden/accepted-test edit, or import of #28 output. Any such
  need stops this slice for a new Producer-approved contract-change note.

## Contracts, fixtures, migrations, and dependencies

- Touched contracts: only the three #38-approved new roots. The five current
  roots and their existing generated named types must remain byte-identical.
- Touched fixtures/goldens: none. New issue-specific JSON/HTML/PNG inputs live
  only under `tests/data/issue_39_public_page_capture/` and are not compiler
  goldens or live network targets.
- Touched persistence: one additive capture migration and its empty-only down
  migration; no existing schema or data exists to backfill.
- `pg` is required for the accepted production PostgreSQL protocol.
- `playwright` is required for actual disposable Chromium contexts and complete
  request interception, the browser boundary already evidenced by #28.
- `pngjs` is required to fully decode and CRC-check bounded PNGs before commit.
- `ajv` and `ajv-formats` are required to enforce the three closed schemas at
  the public API, worker, and immutable provenance boundaries.
- `@electric-sql/pglite` is development-only and supplies deterministic
  PostgreSQL migration/constraint tests without a production database, network,
  container daemon, or credential.
- `@types/pg` and `@types/pngjs` provide strict TypeScript checking only.

No other dependency is authorized by this plan.

## Test-first and automated verification

Tests are added before the corresponding implementation where practical.
Required retained checks are:

1. Contract compilation, positive/negative examples, closed unions, bounds,
   generated imports, and byte-identity checks for every existing schema,
   generated named type, frozen fixture, and compiler golden.
2. Authorization/privacy tests for unknown/nonmember equivalence, role removal,
   commit recheck, adapter outage, visible-reference artifact access, secret
   rejection, and capability/log/provenance non-leakage.
3. URL/egress tests for parser ambiguity, numeric/raw IPs, userinfo, schemes,
   ports, local/metadata names, query secrets, every denied IPv4/IPv6 class,
   mixed DNS, rebind/peer mismatch, redirect/frame/subresource escape,
   WebSocket/WebRTC, direct fallback, and unverifiable peers.
4. Real disposable-browser tests against frozen intercepted fixtures for zero
   initial/final cookies and storage, no imported profile, per-attempt context,
   blocked local files/listeners/downloads/devices, and no real connection.
5. Raster/object tests for size/type/decode/dimension/CRC/metadata verification,
   staging scope/single-use/expiry, mutation/collision rejection, and
   project-scoped byte-for-byte reuse.
6. PostgreSQL migration tests for clean apply/checksum/reapply, named constraints
   and indexes, disabled default, cross-project/cardinality/immutability
   rejection, transaction rollback, old-client compatibility, and destructive
   down refusal after any row or staged-object reference.
7. Fault/concurrency tests around every job/lease/attempt/stage/verify/artifact/
   provenance/revision/change/selection/protection/terminal/commit/response
   boundary, including simultaneous claims, epoch loss, late commit, duplicate
   messages, same-key/different-payload, cancellation, selection and same-byte
   races, crash, lost acknowledgment, and retained-byte corruption.
8. The focused synthetic acceptance command, then the repository's pinned
   `npm run validate`, `git diff --check`, complete diff review, and a boundary
   audit proving no existing contracts, fixtures, goldens, accepted tests, or
   unrelated application surfaces changed.

## Producer synthetic acceptance checklist

1. Run the documented synthetic acceptance command and inspect its safe receipt.
   Expect current fictional authorization, one clean disposable context,
   `importedState: false`, zero ambient cookies/storage, and explicitly
   synthetic/unavailable network evidence.
2. Inspect the unchanged and changed recaptures. Expect distinct jobs, leases,
   attempts, provenance, revisions, and change signals; the unchanged raster
   alone reuses an artifact; the changed raster creates another immutable
   artifact; duplicate delivery returns the original IDs.
3. Inspect the unsafe redirect/private-peer case. Expect a sanitized denial,
   no browser navigation, no revision or selection/protection effect, and no
   real/private connection.
4. Inspect the lease-loss/crash/lost-response case. Expect complete terminal
   attempt evidence, exactly one winning revision and optional selection, late
   epoch denial, and recovery returning stored IDs without another browser run.
5. Confirm selections/protections/audit are append-only, releasing an explicit
   pin preserves Draft/checkpoint/build/evidence/hold reasons, no delete or
   Periodic surface exists, and reply `Accepted production public-page capture
   backend.` or report the first mismatch.

Issue #39 remains `In review`; this task does not mark it `Done` or infer the
Producer's response.
