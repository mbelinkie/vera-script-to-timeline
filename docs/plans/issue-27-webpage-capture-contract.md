# Issue 27 plan — webpage-capture engine, trust, and revision contract

## Objective

Produce the bounded, Producer-reviewable technical decision package required by
GitHub issue #27. The package must make public-webpage capture safe to implement
later by separating durable capture intent from execution, immutable observations,
artifact bytes, selection evidence, and build use. It must also reconcile the
accepted issue #24 `Periodic` concept with the product specification's still-
binding deferred-monitoring trigger.

## Scope

1. Define the identities, cardinalities, lifecycles, and invariants for:
   `Capture`, `CaptureJob`, `JobLease`, `CaptureAttempt`, `CaptureRevision`,
   immutable `Artifact`, `ChangeSignal`, `RevisionSelection`,
   `SelectionEvidence`, pins, and retention decisions.
2. Define authorization and trust boundaries for the hosted authoring API,
   trusted local worker, isolated browser, artifact service, build compiler,
   future scheduler, and future retention worker.
3. Define the public-page-only admission and egress rules, including URL
   canonicalization, redirects, DNS rebinding defenses, public-address
   classification, metadata/private-network denial, credential isolation,
   query-secret handling, browser isolation, and bounded resources.
4. Define complete, access-controlled provenance and audit evidence, plus the
   honest limit that a later live-page fetch is a new observation rather than a
   guaranteed reproduction.
5. Define idempotency, lease-loss, failure, exact-byte deduplication,
   non-semantic change signals, selection, pinning, and non-destructive
   retention behavior.
6. Record a proposed explicit decision on production periodic recapture and
   the bounded handoff to later capture-engine and Spotlight slices.

## Exclusions

- No application, API, worker, browser, scheduler, database, object-store,
  queue, OCR, compositor, Resolve, or notification implementation.
- No webpage navigation or capture, private-project access, browser extension,
  cookie import, authenticated/paywalled capture, or user-supplied secret use.
- No production UI or high-fidelity design; issue #14 remains separate.
- No visual-token or style decision; issue #21 remains separate.
- No shared contract, schema, generated type, fixture, golden, accepted test,
  dependency, manifest, lockfile, or application-code change.
- No material-change threshold, automatic revision replacement, notification
  rule, production schedule frequency, numeric retention default, or deletion.
- No implementation of issue #24's OCR-derived Spotlight, YouTube page
  composite, motion, or automatic remapping decisions.

## Authority and accepted inputs

- GitHub issue #27 and the VERA roadmap are the live scope, routing,
  dependency, ownership, and review authority.
- `docs/Script-to-Timeline Product Spec - Fable Rev2.md` supplies the immutable
  artifact/build principles, local-media authority, Phase 5 public-page capture
  behavior, visible failures, and section 14 monitoring trigger.
- Producer-accepted issue #24 commit `e72aa24` supplies decisions D24-11 through
  D24-13, D24-16, D24-17, and D24-19: Image/Capture separation; `Now`,
  `On build`, and `Periodic` policy vocabulary; immutable revisions; protected
  bounded retention; separate clip/page identities; confirmed Spotlight
  evidence; and supervised remapping.
- Producer-accepted issue #13 commit `a23459d` supplies the hosted Web client,
  trusted local-agent, project authorization, product data-ownership, and
  runtime-boundary decisions. It does not authorize a capture UI.

## Slice boundary before writing

- Roadmap dependencies: `#13` and `#24`; both are closed and `Done`.
- Touched shared contracts: none.
- Touched fixtures or golden files: none.
- Touched application or infrastructure code: none.
- New dependencies: none.
- Planned issue artifacts: this plan and
  `docs/investigations/issue-27-webpage-capture-contract.md` only.
- Dependency justification: #13 defines the hosted/local authorization split;
  #24 is the Producer-accepted source of capture-policy, revision, retention,
  and Spotlight-selection concepts that this issue must make implementable.

## Decision method

The contract will use these tests for every decision:

1. Can a later recapture alter a selected revision, checkpoint, build, or
   artifact? If yes, reject the design.
2. Can untrusted page content reach local/private networks, ambient browser
   credentials, local files, or project secrets? If yes, reject the design.
3. Can a duplicate command, retry, lease loss, or late worker commit produce
   two logical outcomes or silently select a different revision? If yes, reject
   the design.
4. Can provenance explain what was observed, under which conditions, without
   claiming the live page can be fetched identically later? If no, reject the
   design.
5. Can retention remove anything still selected, pinned, checkpoint/build-
   referenced, or needed by confirmed selection evidence? If yes, reject the
   design.
6. Does any decision require #14 UI, #21 tokens, OCR, scheduling, or deletion
   to be valid? If yes, move that behavior to the bounded handoff.

## Verification

1. Map every issue #27 acceptance criterion to a named contract section.
2. Check the package against the accepted product-spec and issue #24/#13
   boundaries, including the exact deferred-monitoring trigger.
3. Run `git diff --check` and inspect the full diff for scope drift.
4. Confirm that only the two issue #27 documentation artifacts changed.
5. Confirm contracts, fixtures, goldens, generated types, accepted tests,
   dependency manifests, lockfiles, and application code are unchanged.
6. Run the repository's pinned `npm run validate` gate.
7. Reinspect issue #27 and move it only to `In review` with actual commit and
   verification evidence. Never mark it `Done`.

## Producer acceptance outline

The final handoff will direct the Producer to the exact lifecycle diagram,
authorization table, threat model, provenance/idempotency/retention rules,
periodic-recapture decision, and implementation handoff. Each step will name
the expected safe result and the exact acceptance or failure response. The
issue remains `In review` until the Producer explicitly accepts it.
