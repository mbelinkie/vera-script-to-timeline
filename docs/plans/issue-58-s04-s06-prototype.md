# Issue 58 plan — prompter, runtime boundary, and suite navigation S04–S06

## Scope and authority

Issue #58 is the active Sol/high design slice for S04–S06 only:

- S04: prompter-readable spoken output, typed non-spoken cues, exclusions,
  deterministic simulated identity, missing-camera blocking, and unplaced
  point-marker recovery;
- S05: browser authoring versus trusted local-agent and Resolve requirements,
  honest Free/Studio terminology, synchronized Preview source identity, safe
  capability failure states, and durable simulated-job continuity; and
- S06: reciprocal Script/Research new-tab navigation with minimal safe context,
  destination reauthorization, and one/many/none/unauthorized/stale fallbacks.

The active claim is task `01a08441-2028-7993-9041-8c1adb448be3` on
`codex/issue-58-s04-s06`, routed to `gpt-5.6-sol` at high effort. Dependency
#14 is closed and Done. Acceptance is Producer.

Pinned inputs:

- `docs/Script-to-Timeline Product Spec - Fable Rev2.md`, especially §§6.5,
  6.8, 6.10, 9.1, 9.3–9.6, 10, 13, and 14;
- `docs/vera-suite-design-contract-and-claude-brief.md`, especially §§3.3,
  4, 5.1–5.4, and 7.4;
- the accepted #26 dossier's S04–S06, R05–R10, R14–R17, F03–F06, F10,
  F28, F32, F34, and E02/E04/E05/E06/E13 states; and
- the Producer-accepted #14 artifact `Script to Timeline - Two-Column
  Authoring S01-S03 v2.dc.html` in the Claude Design project
  `VERA design feedback`, as the visual and interaction baseline only.

## Slice ritual

Scope: one focused S04–S06 successor prototype, its exact prompt, semantic
state mapping, two-viewport evidence, and Producer walkthrough.

Exclusions: S07–S19; production export, persistence, synchronization,
authorization, local-agent, media, job, Resolve, or cross-product behavior;
changes to the accepted S01–S03 artifact; and changes to contracts, fixtures,
goldens, generated types, shared tokens, or Research artifacts.

Touched contracts and fixtures: none.

New dependencies: none. The design reuses the accepted #14 baseline and the
existing #26 dossier; no package or service is added.

Automated checks: repository validation; whitespace and scope review; exact
artifact/prompt/evidence file presence; and frozen-boundary diff checks.

Design checks: every represented branch at real internal `1280 × 800` and
`1024 × 768` layouts, with pointer and keyboard routes, logical visible focus,
non-color identification, readable copy, status announcements, modal focus
return, and no horizontal or independently scrolling column overflow.

Producer acceptance: review the exact retained prompt and named artifact, then
walk S04, S05, and S06 using the retained checklist. The issue moves to
`In review` with evidence but never to Done without an explicit Producer reply.

## Design boundary decisions

1. After Producer correction 1, S04 uses `Create prompter export` and labels
   every result `Simulated — no file written`. It demonstrates export
   preparation and intended use without introducing a production export
   surface.
2. Typed PAUSE and pronunciation cues are visibly non-spoken and separately
   toggleable. Direction, citation, production marker, excluded draft note,
   and source transcript examples never enter spoken output.
3. A missing camera assignment blocks the preview and identifies the affected
   spoken range. It never invents OC/VO. A lost production-marker target is a
   separate zero-duration unplaced warning with explicit reattach/dismiss.
4. Runtime validity comes only from the represented typed capability state.
   Browser identity does not confer local execution, Free never claims external
   Resolve control, and Studio requires a supported running installation with
   external scripting enabled. Invalid actions are absent from the DOM.
5. A simulated durable job retains one job ID, frozen source revision, and
   current stage through a simulated browser close/reopen. This is state-design
   evidence, not a running job or persistence implementation.
6. Suite navigation carries only source product ID, opaque source-project hint,
   and bounded intent. The destination treats the hint as untrusted, rechecks
   its own session and membership, and never exposes protected names/content or
   creates a link. All navigation remains simulated inside the artifact.
7. Producer correction 1 removes S04's input-boundary inventory and theatrical
   prompter sizing. S04 becomes a compact single-column export-preparation flow
   with options first, ordinary document-sized text, and an explicit simulated
   creation result that explains how the prompter text is used.
8. The new `Simplify brief mid-sentence camera changes` option affects only
   prompter OC/VO markers. It suppresses both markers around an OC/VO island of
   five spoken words or fewer when the island starts and ends inside one
   sentence and is surrounded by the same state. It never changes narration or
   source camera assignments, and its value participates in deterministic
   export identity.
9. Producer correction 1 also replaces parenthesized non-spoken notation with
   square brackets in prompter text. The application may render those bracketed
   values as pills, but copied/downloaded plain text preserves literal forms
   such as `[OC]`, `[VO]`, `[PAUSE]`, and `[SAY: …]`. The current product spec
   still names `(OC)`/`(VO)`; accepting this correction therefore requires a
   later explicit specification-format update before implementation. No schema
   or generated type changes are implicated.

## Producer acceptance checklist

1. Open the initial prompt at
   `docs/prototypes/issue-58/claude-s04-s06-prompt.md` and Producer correction
   at `docs/prototypes/issue-58/claude-s04-producer-correction-1.md`, then open
   the resulting Claude Design artifact named in the retained evidence.
2. At `1280 × 800`, reset S04. Confirm there is no input-boundary/source
   inventory; all three options precede compact document-sized prompter text;
   and the page explains that the created text is used in a teleprompter while
   companion data supports later recorded-take matching.
3. With brief-change simplification on, confirm every F04 word remains but the
   five-word `as the tide turns and` island no longer creates VO/OC markers.
   Turn the option off and confirm the exact OC → VO → OC transitions return.
   Toggle annotations and section labels and confirm only those controlled
   non-spoken differences change. Excluded content never enters the output.
4. Create the simulated export twice with the same revision/settings and
   confirm identities are unchanged; change brief-change simplification and
   confirm identity changes. Verify simulated Download/Copy controls and the
   secondary technical details disclosure. Trigger missing camera and confirm
   creation is blocked without an invented state. Trigger F28's lost target and
   confirm a zero-duration unplaced warning with Reattach/Dismiss and no delete.
5. Reset S05. Walk local changes → syncing → synced, then freeze simulated
   Preview B and advance the live head. Confirm Preview stays on B and shows a
   newer-live notice. Inspect no-agent, disconnected, Free, supported Studio,
   Resolve closed/scripting off, and version-mismatch states; confirm browser,
   local-agent, and Resolve actions/failures use the specification's exact
   terminology and invalid actions are absent rather than disabled.
6. Start the authorized simulated durable job, simulate closing and reopening
   the browser view, and confirm the same job ID, source revision, and stage
   return without cancellation or duplication.
7. Reset S06. Use pointer, then reset and use keyboard, to select Research from
   the product switcher. Confirm new-tab intent and preserved source context;
   verify the displayed payload contains only source product ID, opaque project
   hint, and bounded intent.
8. Exercise one, many, and no linked destinations; then unauthorized, stale,
   archived, unlinked, and unavailable states. Repeat the reciprocal
   Research-to-Script route. Confirm destination reauthorization, authorized
   chooser/home fallback, no hidden project names/content, no permission grant,
   no automatic link, and a distinct same-product project switcher.
9. Repeat relevant S04–S06 paths at `1024 × 768`. Confirm readable prompter and
   boundary explanations, visible focus, logical forward/reverse keyboard
   order, non-color states, modal Escape/focus return, status announcements,
   safe long-name overflow, no horizontal overflow, and no separate scrolling
   content columns.
10. Reply exactly `Accept #58 S04–S06 prototype states` to accept, or
    `Correction: <S04|S05|S06> — <first misrepresented state and intended
    meaning>` to report the first failure. Simulations are design evidence, not
    implementation evidence.
