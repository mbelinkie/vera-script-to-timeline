## Outcome

Design and obtain Producer acceptance for the S04 Prompter script and S05
Resolve timeline experiences. Record the adopted decision to retire S06 as a
standalone page: ordinary suite switching belongs in the shared application
header, with any future cross-project landing experience designed separately.

## Scope

- S04 presents compact prompter-ready wording from the continuously saved
  script, with options before the text and literal square brackets for every
  non-spoken item in copied/exported output.
- S04 can simplify brief mid-sentence OC/VO islands without rewriting narration
  or changing the script's source camera assignments. Missing camera state
  blocks prompter creation and links back to the affected phrase.
- S05 is the user-facing **Resolve timeline** page. It creates the first
  timeline or reviews a complete outbound current-script-to-linked-timeline
  update; it does not review inbound Resolve edits.
- S05 preserves the S03 script-row conventions and gives every affected row a
  selected-by-default checkbox. Added/current material is green, removed/old
  material is red, moves appear at both positions, and partial selection is
  allowed with explicit consequence warnings.
- S05 represents narration, camera-state, visual, visual-range, row
  split/merge, section-marker, and multi-row audio changes. Audio spanning
  rows is an atomic independently selectable change, including when displayed
  at both locations for a move.
- **Create timeline** and **Update timeline** act immediately. **Create and
  render** and **Update and render** open Render settings for format,
  resolution, quality, destination, filename, saved presets, and one continuous
  section range.
- Resolve Studio, Resolve Free, closed/unreachable Resolve, unsupported
  versions, and broken-link states are represented without claiming real
  execution from the browser prototype.

## Acceptance criteria

- [x] S04 visibly distinguishes spoken text, OC/VO changes, and bracketed
      non-spoken content; the brief-camera-change option preserves every spoken
      word and missing camera state blocks creation without guessing.
- [x] S05 omits the update-diff section on first creation and, for updates,
      comprehensively shows every outbound affected row in script order with
      row-level inclusion and accurate partial-update consequences.
- [x] Visual coverage is quiet until hover/focus; unchanged, new, and previous
      ranges use the accepted gold, green, and dotted-red treatments. Resolve
      markers remain zero-duration points rather than visual ranges.
- [x] Multi-row audio changes show start/continue/end rails, independent atomic
      selection, linked move decisions, selected/skipped counts, bulk
      Select/Clear behavior, and a valid audio-only update path.
- [x] Create/Update timeline and Create/Update-and-render use the accepted
      immediate-action versus Render-settings-dialog behavior and accurately
      describe the selected row and audio changes.
- [x] Resolve capability and failure states use user-facing product language
      and do not imply production export, synchronization, authentication,
      local-agent, media, background-job, or Resolve execution.
- [x] The represented states remain readable and operable at internal
      `1280 × 800` and `1024 × 768` viewports with keyboard/focus, non-color,
      status, and overflow treatment retained.
- [x] S06 is absent. Suite switching is represented by the shared header
      control rather than a standalone navigation page.
- [x] Producer accepted the final S04–S05 artifact and the intentional S06
      deletion on 2026-09-13.

## Dependencies

- Blocked by #14

## Exclusions

No S07-S19 work; no implementation of production export, synchronization,
authentication, local-agent, media, background jobs, Resolve operations,
rendering, or cross-product navigation; no frozen contract, fixture, golden,
generated-type, or shared-token changes.

## Retained evidence

- Claude Design artifact: `Script to Timeline - Prompter Runtime and Suite
  Navigation S04-S06.dc.html` (the historical filename is retained; the final
  artifact contains only S04 and S05).
- Review URL: <https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=Script+to+Timeline+-+Prompter+Runtime+and+Suite+Navigation+S04-S06.dc.html>
- Evidence record: `docs/prototypes/issue-58/evidence.md`
- Accepted plan and decisions: `docs/plans/issue-58-s04-s06-prototype.md`

## Producer acceptance

Matthew Belinkie replied `Accepted — update and close #58` after the final
Chrome review confirmed the remaining bulk-selection, combined-count,
audio-only-action, Graphic Overlay terminology, missing-camera blocking, and
two-viewport checks.
