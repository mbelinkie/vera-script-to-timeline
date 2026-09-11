# Issue #117 — Wide/Tight design-presence checklist

This checklist controls Producer review of
`Script to Timeline - Two-Column Authoring S01-S03 v3.dc.html`. The accepted v2
artifact remains the regression baseline. Nothing is sent to Claude until the
Producer approves the exact prompt in
`claude-s01-s03-wide-tight-amendment-prompt.md`.

## Integrity and scope

- [ ] v2 remains unchanged and v3 is a separate versioned artifact.
- [ ] The sample still contains the accepted 22 rows and all unrelated v2
      behavior.
- [ ] No production, contract, fixture, compiler, Resolve, S04–S19, multicamera,
      or automatic-switching interface was added.
- [ ] No numeric zoom/position, color, audio, source-time, or continuity panel
      appears in the authoring interface.

## Authoring behavior

- [ ] Every ordinary On Camera card and every `↩ ON CAMERA RESUMES` return has
      exactly one explicit `Wide | Tight` choice.
- [ ] The selected state is visible and accessible without relying on color.
- [ ] Pointer, Tab, arrow keys, Space/Enter, and visible focus work at both
      viewports.
- [ ] New On Camera appearances seed from the last treatment but immediately
      retain an independent explicit value.
- [ ] Editing an earlier appearance does not cascade; Undo/Redo restores the
      exact per-appearance history.
- [ ] Non-presenter visuals neither expose nor retain presenter framing.

## Preview and continuity examples

- [ ] Configured presenter stills render noticeably different Wide and Tight
      crops in cards and temporary previews and update immediately when the
      choice changes; B-roll is unaffected.
- [ ] Without a custom still, the neutral Wide and Tight silhouettes are
      distinct without color or text-only tiles.
- [ ] Hiding presenter thumbnails preserves the compact text choice.
- [ ] Row 2 is Wide before and after its temporary lower-third placeholder.
- [ ] Row 6 is Wide before B-roll and Tight on return; only the phrase
      `When we return to the wider view` changed to `When we return to me`.
- [ ] Row 7 is Tight before and after its backward-derived cutaway.
- [ ] Row 18 is Wide and adjacent row 19 is Tight, with the treatment change
      exactly at the row boundary and no implied presenter-source/audio cut.
- [ ] Temporarily making rows 18–19 both Wide creates no framing change at the
      row boundary; Undo restores the Wide/Tight example.

## Regression and responsive checks

- [ ] At 1280×800 and 1024×768, all controls stay within the right column with
      no clipping, collision, hidden focus ring, or horizontal overflow.
- [ ] The columns stay synchronized and never scroll independently.
- [ ] Connectors, range brackets, card hierarchy, card compaction, thumbnail
      sizes, Authoring-size extremes, Preview/Trim, readiness, reload, row and
      section actions, and reorder behavior match accepted v2.
- [ ] The artifact still contains 13 Onscreen Placeholder cards and zero
      placeholder swap instructions.

## Producer decision

- [ ] The Producer reviewed and approved the exact Claude prompt before it was
      sent.
- [ ] The Producer walked v3 at both target viewports and explicitly accepted
      #117 or recorded the first failed state.
