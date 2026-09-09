# Issue 40 plan — Spotlight OCR evidence and supervised remap contract change

## Objective

Produce the bounded, Producer-reviewable contract-change proposal required by
GitHub issue #40. The proposal must connect an immutable public-page capture
revision to the accepted #29 Spotlight matte core through separately versioned
OCR/DOM proposals, manual geometry, author confirmation, recapture-remap
proposals and decisions, and an immutable derivation/build receipt. It performs
no OCR, capture, persistence migration, UI, composition, or shared-schema edit.

## Authority and accepted inputs

- GitHub issue #40 and the VERA roadmap are the live scope, routing,
  dependency, ownership, and acceptance authority. At claim time the issue was
  `Ready`, unclaimed, routed to `model:sol` / `effort:high`, and assigned
  `Producer` acceptance.
- The product specification Revision 2.2 supplies the separate-identity,
  immutable-build, replaceable-provider, trusted-local-agent, versioned shared
  contract, job, and visible-failure principles, plus Phase 5's immutable
  public-page recapture behavior.
- Producer-accepted issue #24 commit `e72aa24` supplies the OCR-derived inverse
  matte, confirmed target, supervised remap, normalized/source-pixel geometry,
  composition-order, and immutable build-evidence requirements.
- Producer-accepted issue #27 commit `9143518` supplies immutable
  `CaptureRevision`, revision-bound `SelectionEvidence`, proposal-versus-
  confirmation separation, and the keep-old / accept-remap / redraw boundary.
- Producer-accepted issue #29 commit `281a5e2` supplies the pure
  `vera.spotlight-matte.alpha8.v1` derivation behavior: exact capture-hash
  matching, integer half-open rectangles, order-independent union, bounded
  padding/dim alpha, manual fallback, and immutable matte/receipt hashes.
- Producer-accepted issue #38 commit `f35f85f` supplies the future production
  capture v1 identities, artifact descriptors, restricted provenance,
  project-scoped authorization/reference ports, protection graph, and additive
  migration rules. Issue #39 remains the implementation prerequisite for #41.
- Existing issue #41 is the bounded downstream backend implementation owner.
  It remains dependency-blocked by #39 and #40 and is not promoted, claimed, or
  dispatched by this issue.

## Scope

1. Define a narrow, replaceable OCR adapter seam that consumes only an
   authorized immutable capture raster and records provider, adapter, model,
   profile, privacy, cost, request, response, and canonical evidence identities.
2. Define deterministic word/line IDs, exact text/context, integer source-pixel
   rectangles, normalized geometry, confidence, reading order, and evidence
   hashes for frozen fictional provider results.
3. Keep OCR and optional DOM target proposals, manual geometry proposals,
   author confirmations, remap proposals, remap decisions, derivations, and
   build bindings as separate immutable records. Automation never creates an
   author confirmation.
4. Define a conservative deterministic v1 recapture-remap algorithm, including
   unique, missing, ambiguous, contradictory, incompatible-profile, and manual-
   redraw outcomes plus the exact allowed keep-old / accept-remap / redraw
   decisions.
5. Define the exact projection of a confirmed target into #29 and the wrapper
   receipt that pins capture, evidence, proposal, confirmation/decision,
   derivation parameters, #29 receipt, and matte artifact identities without
   changing #29's accepted receipt bytes.
6. Name the future shared root, generated TypeScript/Python effects, additive
   persistence migration, synthetic examples/tests, compatibility limits,
   failure behavior, and Producer acceptance evidence required before #41.

## Exclusions

- No edit to `/contracts`, `/fixtures`, generated types, existing test data,
  goldens, accepted tests, manifests, lockfiles, dependencies, application code,
  database migrations, API routes, workers, capture packages, or #29 code.
- No OCR/provider call, provider account or billing setup, page capture,
  recapture, browser/DOM extraction, production/private page text, screenshot,
  network request, object upload, database write, or research-project access.
- No authoring UI, accessibility interaction or presentation, visual tokens,
  motion, timing UI, YouTube composite, compositor, nested sequence, native
  Resolve/Fusion mask, delivery adapter, deployment, monitoring, retention, or
  deletion.
- No automatic confirmation or target movement, fuzzy/semantic/LLM remapping,
  cross-profile automatic remapping, background recapture, or fallback to an
  unapproved OCR provider.
- No promotion, claim, dispatch, implementation, or closure of issue #41 or any
  other roadmap item.

## Slice boundary before writing

- Canonical dependency: `#38`, closed and `Done` at claim time.
- Dependency justification: #38 fixes the capture revision/artifact,
  authorization, provenance, and protection identities this proposal may
  reference. The design can be approved before #39 implements those identities;
  #41 remains blocked on both implementations/contracts.
- Touched shared contracts: none. The investigation proposes one future closed
  v1 root for explicit Producer approval.
- Touched fixtures or golden files: none.
- Touched application, provider, capture, persistence, compiler, or
  infrastructure code: none.
- New dependencies: none.
- Planned issue artifacts: this plan and
  `docs/investigations/issue-40-spotlight-ocr-remap-contract.md` only.

## Decision tests

Reject any proposed boundary for which one of these answers is wrong:

1. Can provider output, OCR/DOM automation, a confidence score, or a unique
   remap create author confirmation? It must not.
2. Can a new capture, OCR rerun, model/profile change, remap, or later build
   edit or relabel an earlier evidence record, confirmation, matte, or build?
   It must not.
3. Can missing, multiple, contradictory, incompatible, or malformed remap
   evidence move a target or publish a new matte? It must not.
4. Can an implementation derive with anything other than exact confirmed
   source-pixel geometry for the same capture hash? It must not.
5. Can a remote OCR provider receive a URL, cookie, credential, provenance
   manifest, project/user identity, or more raster data than the authorized
   request names? It must not.
6. Can provider timeout, cost exhaustion, invalid geometry, migration failure,
   or stale evidence silently fall back or alter a prior build? It must not.
7. Can Spotlight fit into a current closed compiler/build v1 root without an
   explicit versioned companion or later contract change? It must not be
   claimed to do so.
8. Does this issue require UI, accessibility presentation, live provider proof,
   capture execution, matte rendering, or Resolve behavior to be accepted? If
   yes, move that behavior to its existing later owner rather than expanding
   #40.

## Verification

1. Trace every #40 acceptance criterion to a named investigation section and
   to one fictional confirmed-text, manual fallback, changed-capture, or stale-
   remap scenario.
2. Cross-check the proposed input projection against accepted #29 fields and
   rules, including exact capture hash, integer half-open boxes, stable IDs,
   sorted union, padding, clamping, and no result on failure.
3. Cross-check capture/revision/protection references against accepted #38 and
   label #39 implementation assumptions explicitly.
4. Verify examples use reserved fictional hosts, synthetic UUIDs/digests, and
   fictional text only; no OCR request or external URL is executed.
5. Run `git diff --check`, inspect the full diff, and confirm only the two issue
   #40 documentation artifacts changed.
6. Confirm `/contracts`, `/fixtures`, generated types, existing tests/goldens,
   manifests/locks, and all application/provider/persistence/compiler code have
   no diff.
7. Run the repository's pinned `npm run validate` gate.
8. Reinspect issues #40 and #41, commit and push the bounded artifacts, and move
   only #40 to `In review` with concrete evidence. Never mark it `Done` and do
   not promote, claim, or dispatch #41.

## Producer acceptance outline

The final handoff will direct the Producer to the exact investigation sections
for the identity chain, provider/privacy/cost seam, OCR geometry and hashing,
proposal/confirmation boundary, deterministic remap state machine, #29
projection, future contract/migration ledger, fictional scenario traces, and
failure behavior. Each step will name the expected safe result and the exact
acceptance or failure response. Issue #40 remains `In review` until the Producer
explicitly replies `Accepted Spotlight OCR evidence and remap contract.`
