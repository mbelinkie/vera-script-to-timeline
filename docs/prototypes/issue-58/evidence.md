# Issue 58 retained evidence — accepted S04–S05 prototype

## Artifact and boundary

- Claude Design project: `VERA design feedback`
- Artifact: `Script to Timeline - Prompter Runtime and Suite Navigation
  S04-S06.dc.html`
- Review URL: <https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=Script+to+Timeline+-+Prompter+Runtime+and+Suite+Navigation+S04-S06.dc.html>
- The filename is historical. The accepted artifact contains S04 and S05 only;
  S06 was intentionally deleted.
- Visual baseline: the Producer-accepted `Script to Timeline - Two-Column
  Authoring S01-S03 v2.dc.html`.

The artifact labels itself as a design simulation. It does not implement or
claim production export, synchronization, authentication, local-agent, media,
background-job, Resolve, rendering, or cross-product behavior. No contracts,
fixtures, golden files, generated types, or shared tokens changed.

## Retained design briefs

- `claude-s04-s06-prompt.md`
- `claude-s04-producer-correction-1.md`
- `claude-s04-producer-correction-2.md`
- `claude-s04-s05-combined-edits-and-s06-removal.md`
- `claude-s05-guided-redesign-brief.md`
- `claude-s05-comprehensive-outbound-diff.md`
- `claude-s05-final-logic-corrections.md`
- `claude-s05-final-semantic-corrections.md`
- `claude-s05-complex-scenarios-and-render-settings.md`

## Accepted product decisions

### S04 — Prompter script

- The screen is a compact document-like prompter-preparation flow, not a
  teleprompter player or a source-data inventory.
- Options precede the text. Non-spoken annotations and optional section labels
  use literal square brackets in plain output while the application may render
  them as pills.
- Ordinary VO and OC presentation follows the accepted S03 conventions.
  Brief mid-sentence camera islands may be simplified only under the displayed
  narrow rule; narration and source camera assignments never change.
- A missing camera assignment is an authoring preflight failure. The design
  identifies the phrase, links back to it, and disables prompter creation
  without inventing OC or VO.

### S05 — Resolve timeline

- The user-facing page name is **Resolve timeline**. There is no Preview versus
  Release cutoff: the continuing workflow is **Create timeline** followed by
  any number of **Update timeline** operations.
- First creation does not show an update diff. Updating shows the complete set
  of outbound changes from the current script to the linked timeline version,
  in script order. Inbound Resolve reconciliation belongs in S01–S03, not S05.
- Each affected script row has a selected-by-default checkbox. Skipping a row
  is deliberate and allowed; split, merge, and compound-move cases explain the
  resulting partial timeline instead of silently forcing atomicity.
- Added/current material uses green treatment and removed/old material uses red
  treatment. Moved material appears at both locations. Narration, camera state,
  visuals, coverage changes, splits/merges, and section markers retain the S03
  row widths, thumbnails, and typography.
- Visual ranges remain quiet until hover or focus. Unchanged current coverage
  uses gold, new coverage uses solid green, and previous coverage uses dotted
  red. Old and new visual cards paint only their own version's range. Resolve
  markers are zero-duration points and never paint narration coverage.
- A music or SFX bed spanning rows is one independently selectable atomic audio
  change. Start/continue/end rails show its whole-row range. A moved bed may be
  displayed in two sections, but both controls mirror one decision and count as
  one audio change.
- Row and audio counts remain separate but appear together. Select all and
  Clear all affect both kinds. Skipped counts appear only when nonzero, and an
  audio-only selection keeps Update timeline available with an incoherence
  warning when relevant rows are skipped.
- **Create timeline** and **Update timeline** are immediate actions. **Create
  and render** and **Update and render** open a proper Render settings dialog;
  its final action performs the combined operation. Settings include last-used
  values, saved presets, codec/container, resolution, Draft/Standard/High,
  destination, filename, and a continuous section range.
- Resolve Free/Studio, closed/unreachable Resolve, unsupported versions, and a
  broken link remain prototype states with truthful remediation and no browser
  execution claim.

### S06 — intentionally retired

- S06 is not a user-facing page and is absent from the accepted artifact.
- Ordinary movement between VERA products belongs in the shared application
  header. A possible future web landing page for projects is outside this
  issue.

## Final verification

Final Chrome review on 2026-09-13 confirmed:

1. S04 base and missing-camera states at `1280 × 800`; the affected phrase is
   named and both the primary action and supporting copy are disabled until the
   camera state is resolved.
2. S05's comprehensive connected/update scenario retained eight affected rows,
   selected-by-default row controls, section-marker rename, moved-row linking,
   and the accepted red/green/non-color semantics.
3. The multi-row-audio scenario retained four logical audio changes, including
   new, removed, within-section moved, and cross-section moved examples. The
   cross-section move is displayed twice but remains one atomic decision.
4. `Select all` and `Clear all` explicitly cover all five affected rows and all
   four audio changes. Clearing produces `0` selected and accurate skipped
   counts across headers, rails, summary, and disabled actions.
5. Selecting only one audio change re-enables Update timeline, reports `0 row
   changes selected; 5 skipped` and `1 audio change selected; 3 skipped`, and
   shows the intended warning instead of blocking the operation.
6. Update timeline's accessible description includes both row and audio counts.
   The reset-control and related callout cards use **Graphic Overlay** rather
   than the obsolete **Onscreen Placeholder** label.
7. The same multi-row-audio state remained readable without horizontal
   overflow at `1024 × 768`; the top badges, bulk controls, row checkboxes,
   audio header, rails, narration, and production cards remained legible.

## Producer acceptance

After the remaining corrections and final verification, Matthew Belinkie
replied on 2026-09-13:

`Accepted — update and close #58`

This is Producer acceptance of the final S04–S05 design and the intentional
deletion of S06. The artifact remains design evidence, not implementation
evidence.
