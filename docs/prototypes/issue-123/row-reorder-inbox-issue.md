## Outcome

Design and obtain Producer acceptance for quickly reordering ordinary S03
script rows with a visible drag handle and an equivalent keyboard interaction.

## Scope

- Add a discoverable row handle without weakening the two-column writing
  hierarchy or making ordinary text selection difficult.
- Move a row's narration, sequential and overlapping visuals, attached audio,
  directions, comments, and identity as one atomic unit.
- Define pointer and keyboard placement feedback, permitted destinations,
  cancel, undo, and accessible announcements.
- Define behavior when a destination would violate section structure, visual
  bounds, audio-bed continuity, anchors, or other build invariants.
- Show how concurrent edits or row moves become an explicit recoverable
  conflict rather than silent data loss.
- Exercise representative desktop and narrow layouts using the accepted S03
  visual language.

## Acceptance criteria

- [ ] Pointer dragging and an equivalent keyboard route can move one ordinary
      row to a valid destination with clear before/after placement feedback.
- [ ] The entire row moves atomically without duplicating or dropping narration,
      visuals, audio, directions, comments, provenance, or identity.
- [ ] Invalid destinations are blocked with a readable non-color explanation;
      cancel and undo restore the prior order.
- [ ] Collaboration conflicts and stale anchors have explicit recoverable
      outcomes and never silently overwrite another accepted edit.
- [ ] Text selection, card interaction, section navigation, focus order, and
      responsive S03 behavior remain usable.
- [ ] The Producer accepts the exact design artifact or identifies the first
      unacceptable state.

## Dependencies

- Blocked by #123

## Exclusions

- No production editor, collaboration engine, persistence, schema, contract,
  generated-type, compiler, fixture, golden-file, or Resolve implementation.
- No reordering of Ideas or Extras; those retain their separately accepted
  interactions.

## Unresolved decisions

- Choose the final handle placement and whether it appears always, on row focus,
  or on hover/focus.
- Choose the keyboard command and announcement wording after testing the design.
- Decide whether multi-row selection/reordering belongs in this slice; do not
  assume it by default.

## Parent and routing rationale

Standalone S03 design follow-up discovered during #123. Tentative route:
`model:sol` / `effort:high`; `type:implementation`; Priority P2; Size S;
Workstream Product and UX; Acceptance Producer; Status Inbox.
