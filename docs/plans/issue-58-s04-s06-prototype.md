# Issue 58 accepted plan — Prompter and Resolve timeline (S04–S05)

## Scope and authority

Issue #58 is the accepted Sol/high design slice for:

- S04: compact prompter-ready text, bracketed non-spoken annotations, optional
  section labels, narrow brief-camera-change simplification, and preflight
  blocking for missing camera state; and
- S05: first-time Resolve timeline creation, comprehensive outbound update
  review, row- and audio-level selection, accurate partial-update consequences,
  Resolve capability/failure states, and optional one-flow rendering.

The original S06 standalone suite-navigation page was retired by the Producer.
Normal product switching belongs in the shared application header; a possible
future web landing page is outside this slice.

The implementation claim was task `01a08441-2028-7993-9041-8c1adb448be3` on
`codex/issue-58-s04-s06`, routed to `gpt-5.6-sol` at high effort. Dependency
#14 is closed and Done. Acceptance authority is Producer.

## Slice ritual

Scope: one focused S04–S05 successor prototype, its retained prompts, semantic
state mapping, both viewport presentations, and Producer walkthrough.

Exclusions: S07–S19; production export, persistence, synchronization,
authorization, local-agent, media, job, Resolve, rendering, or cross-product
implementation; changes to the accepted S01–S03 artifact; and changes to
contracts, fixtures, goldens, generated types, or shared tokens.

Touched contracts and fixtures: none.

New dependencies: none. The design reuses the accepted #14 baseline and adds
no package or service.

Design checks: the represented states at internal `1280 × 800` and
`1024 × 768`, including pointer and keyboard routes, focus, non-color status,
readability, action descriptions, count derivation, and overflow behavior.

## Accepted design boundaries

1. S04 prepares ordinary prompter text; it is not itself a teleprompter player.
   Its primary action remains explicitly simulated.
2. Anything not spoken uses square brackets in plain prompter output. Pills are
   a display treatment only.
3. Brief camera-state simplification removes only qualifying OC/VO markers. It
   never rewrites narration or changes source assignments.
4. Missing camera state is caught before prompter creation. VERA identifies and
   links to the phrase rather than guessing a state.
5. S05 has no Preview/Release cutoff. The durable user model is Create timeline
   followed by Update timeline as the script and linked Resolve timeline evolve.
6. S05 shows only what VERA will push to Resolve. Any accepted reconciliation
   from Resolve back into the script is upstream S01–S03 work.
7. First creation omits the update diff. Updating shows every affected row in
   script order, with red old material, green new material, and row-level
   selected-by-default approval.
8. Row approval remains authoritative for compound moves, splits, and merges.
   Pure moves may share one decision when no other row change makes independent
   choice necessary; all partial outcomes are explained.
9. Visual coverage appears only on hover/focus. Current unchanged, new, and old
   ranges use gold, solid green, and dotted red respectively. Marker rows are
   zero-duration points, not coverage ranges.
10. Multi-row audio is an independent atomic change with whole-row
    start/continue/end rails. A moved bed can appear at both positions while
    retaining one mirrored decision and one count.
11. Bulk Select/Clear affects both row and audio changes. Counts, warnings,
    action availability, accessible descriptions, and results derive from the
    current selection; audio-only updates are valid.
12. Create/Update timeline acts immediately. Create/Update and render opens the
    Render settings dialog, whose final action starts the combined operation.
13. S06 is deleted. Shared-header navigation replaces the unnecessary page;
    no cross-product permission or data-transfer behavior is asserted here.

## Acceptance

The Producer completed iterative review in the Claude Design artifact, the
final Chrome verification covered the remaining S04 and S05 states at both
viewports, and Matthew Belinkie explicitly accepted the final design and S06
deletion on 2026-09-13 with:

`Accepted — update and close #58`

See `docs/prototypes/issue-58/evidence.md` for retained observations and the
artifact URL. The accepted simulation defines design intent only; implementation
requires separately scoped roadmap issues.
