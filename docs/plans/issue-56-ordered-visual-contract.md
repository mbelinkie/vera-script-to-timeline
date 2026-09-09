# Issue 56 plan — ordered visual, hierarchy, and source-trim contract

## Objective

Produce only the bounded, Producer-reviewable production contract required by
GitHub issue #56. The result must turn the Producer-accepted issue #14 visual
behavior into deterministic data, edit, projection, compiler, source-trim,
thumbnail, presenter-sync, and failure rules before any implementation issue
becomes Ready.

## Authority and accepted inputs

- GitHub issue #56 and the VERA roadmap are the live scope, routing,
  dependency, ownership, and review authority.
- `docs/Script-to-Timeline Product Spec - Fable Rev2.md` supplies the durable
  narration-first authoring, stable-anchor, exact coverage, logged-clip,
  immutable build, recorded-conform, no-hidden-retime, and recovery rules.
- Producer-accepted issue #14 evidence is retained in commit
  `11cef62fad9800bdca2934343515dd9a0c3d5172`, especially
  `docs/plans/issue-14-browser-authoring-prototype.md`,
  `docs/prototypes/issue-14/producer-acceptance.md`, and
  `docs/prototypes/issue-14/traceability-ledger.md` at that commit.
- The current frozen v1 schemas, generated types, validator, compiler, fixtures,
  and goldens are inspected only to identify the exact future compatibility and
  migration boundary. They are not edited by this issue.

## Slice ritual

Scope:

1. Define the authoritative ordered full-frame visual sequence for narrated
   rows, including sequential roots, one-level cutaways, explicit returns, and
   derived host visibility and coverage.
2. Define exact edit operations and invalid/transient states for anchor repair,
   word-boundary edits, swaps, hierarchy conversion, cross-row moves, and base
   deletion.
3. Define recorded and temporary presenter synchronization.
4. Define occurrence-owned logged-source inpoints, narration-driven endpoints,
   duration validation, Research handoff, and deterministic thumbnails.
5. Define complete-clip playout, its non-authoritative five-word drafting
   estimate, and exact media-timed build boundary.
6. Produce a contract-change note covering schema, compiler dependencies,
   manifest/build report, compatibility, migration, generated types, fixtures,
   goldens, diagnostics, and acceptance.

Exclusions:

- No production schema, contract, fixture, golden, generated-type, validator,
  compiler, UI, media-worker, Resolve, Research, or product-spec edit.
- No #14 prototype implementation or modification.
- No direct YouTube logging or URL entry in Script to Timeline.
- No nested cutaway depth beyond the single level explicitly proposed here.
- No hold, freeze, retime, loop, reverse, or generative source extension.
- No generalized transition, overlay, collaboration, concurrency, or
  frame-level manual-timing design beyond the boundaries named by #56.

Touched shared contracts and fixtures: **none**.

Planned issue artifacts:

- this plan; and
- `docs/investigations/issue-56-ordered-visual-contract.md`.

New dependencies: **none**.

Dependency justification: canonical dependency #14 is closed and `Done`; its
accepted S01-S03 artifact is the visual-design evidence this production
contract must formalize. No other issue is required to decide the bounded
contract.

## Decision tests

Every proposed rule must pass all of these tests:

1. Can the visible and compiled primary picture at every narration time be
   derived from row start, strictly ordered boundaries, a return, or row end?
2. Can any edit silently move an anchor to a different word, create a
   zero-length interval, overlap two topmost full-frame visuals, or lose a
   payload? If yes, reject it.
3. Can authoring projection, compiler output, or the manifest disagree about
   which boundary is authoritative? If yes, reject it.
4. Can a trim, thumbnail refresh, presenter mismatch, short source, retry, or
   Research handoff mutate source media or another occurrence? If yes, reject
   it.
5. Can an estimated media-led boundary look like an exact word boundary? If
   yes, reject it.
6. Can v1 data be silently reinterpreted as hierarchy or can accepted v1 bytes
   change? If yes, reject the migration.

## Verification

1. Map every issue #56 acceptance criterion and unresolved decision to a named
   section in the contract.
2. Cross-check the proposal against product-spec §§6.1-6.2, 6.10-6.11, 6.15,
   8.3-8.5, the Phase 6/7 gates, and the failure matrix.
3. Cross-check the proposed UI projections against the accepted #14 artifact
   evidence without treating prototype-only data behavior as production truth.
4. Run `git diff --check` and inspect the complete diff for scope drift.
5. Confirm only the two issue #56 documentation artifacts changed.
6. Confirm every file under `contracts/`, `fixtures/`, generated contract
   directories, compiler/application code, and accepted tests is unchanged.
7. Run the repository's pinned `npm run validate` gate.
8. Commit the review artifacts, retain exact command evidence on issue #56,
   move it to `In review`, and never mark it `Done` without explicit Producer
   acceptance.

## Producer acceptance outline

The final handoff directs the Producer to the exact decision summary, state
model, edit table, source/presenter failure table, complete-clip boundary
example, contract-change note, and acceptance mapping. Each step names the
expected result and the exact acceptance or failure response. Agent
self-report, tests, or silence never count as Producer acceptance.
