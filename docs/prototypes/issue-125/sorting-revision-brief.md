# Sorting revision brief

## Current direction — after r12, 2026-10-26

Matthew selected **A · Line**. The next prepared request is the
[focused r13 prompt](claude-sorting-r13-prompt.md), following the rendered
[r12 comparison](https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=S03+Outline+Sorting+Comparison+r12.dc.html).
It supersedes the earlier comparison notes below where they differ:

- One orange ellipsis replaces the vertical text-omission line in A.
- Thumbnails stay on the right, with a consistent cluster footprint; On Camera
  remains neutral and bold script words retain their camera meaning.
- Two fictional Full-audio clips each occupy their own row with empty narration.
  Sorting shows quoted source speech with a proposed “Original audio” label;
  expansion keeps the transcript on the right clip card.
- Add Section in Stash is requested as an organization exception to read-only
  content. Its changes share pending Accept/Discard and chronological Undo.
- Preserve B and prior artifacts as history; no further comparison is requested.

One tools-disabled Opus/high CLI product consultation on the full r13 draft
completed on 2026-10-26. The prepared prompt incorporates the resulting
clarifications. On Matthew's subsequent explicit “Send it” instruction, the
complete r13 prompt was attached and sent in a fresh Claude Design chat in the
existing project. Receipt was verified through Claude's reading activity.
The cover message retained the proof limits and requested no export. Submission
did not lift the design hold; no timer or automatic submission was created.

The design revision remains held on the required #337 Stash and #326 music
proofs, unless Matthew explicitly defers the affected scope. New clip rows are
fixture presentation under existing source-clip audio behavior, not a new media API
or audio operation. They start outside the Quiet piano span and do not count
as user sorting changes.

## Earlier comparison direction — historical where superseded above

1. Use the same [20 long narration rows](sorting-long-rows.md) in both density
   treatments. The copy is fixed test material, not a script Claude must write
   or improve. Retain a short row and a visual-only control separately so the
   no-omission case is visible. Do not shorten the underlying content to make
   it fit. Fixture IDs are never visible row numbers.
2. Semibold means On Camera at the actual word/range level; VO stays normal.
   Beginning and ending excerpts have equal semantic styling. Preserve mixed
   OC/VO spans when slicing text; no emphasis based on excerpt position.
3. Single-clicking the summary expands that row inline into the actual S03
   two-column rendering, read-only. Only one row is expanded at a time.
   Clicking its summary again collapses it. Remove Open row, the separate
   open-in-script icon, and double-click navigation from the sorting rows.
4. One planned foreground visual: one thumbnail at the left. Multiple planned
   foreground visuals: first at the left and last at the right. Determine this
   from the planned sequence, not image uniqueness. OC → VO → OC still has
   multiple visuals even when both endpoints show the same presenter framing.
   An overlay alone does not create another foreground visual. An unavailable
   endpoint retains its slot and placeholder.
5. Explicitly mark omitted middle text or visuals, beyond a bare ellipsis.
   Try the Producer's orange vertical divider with a visible gap around it.
   It represents hidden summary content, not an authored cut or lost content.
   Add a non-color shape/label and accessible explanation. No marker when no
   content was skipped. Text and visual omissions are separate: two displayed
   endpoint visuals with nothing between them omit no visual; X → Y → X does.
6. Select contiguous rows in the left gutter, stopping at section boundaries.
   Keep the continuous group outline and put its single Move N rows handle
   on the LEFT beside that selection, not at the right end. No checkbox
   squares. Body click expands; handle drag moves; gutter drag selects.
7. Persist a quiet mark on deliberately moved rows during the sorting session.
   Do not mark every row displaced by another row's move. Undo updates marks.
   Clear the mark when the row returns to its original place. This is a net
   change from the session baseline, not an activity history. Matthew selected
   this behavior on 2026-10-25.
8. Sorting is a TRIAL until accepted. Original script and Stash stay unchanged
   while the trial is being arranged. Back to script displays the proposed
   order using the real S03 renderer, read-only. A floating bottom bar offers
   Accept sorting and Return to sorting. Accept commits; returning preserves
   the trial. Discard sorting returns both script and Stash to the starting
   state. Script and Stash text remain read-only until Accept or Discard;
   ordinary content editing resumes afterward. Matthew explicitly selected
   these trial semantics, including the text-edit restriction on 2026-10-25.
9. Use Show Stash with an adjacent saved-row count. In Sorting it opens a
   sidebar accepting dragged rows and supporting drag back to explicit outline
   gaps, with keyboard alternatives. Preserve each saved bundle's order.
   Clicking a Stash item opens a WIDE TEMPORARY PREVIEW over the main area;
   closing it restores the outline/sidebar positions. This preview choice was
   explicitly selected by Matthew. Normal authoring must also access Stash
   and permit editing its full content. Stash remains distinct from Ideas/Extras.
10. Show music beds connecting rows with a thin line in a dedicated RIGHT
    gutter outside ending thumbnails, with clear start/end marks. The fixture
    supplies Quiet piano across the amber-lantern, chalk-crescent and paper-
    signal-frame rows. Moving that complete group intact preserves the bed.
    Moving only the ending row elsewhere in the same section shortens it to
    the end of the unchanged chalk-crescent row, where the original covered
    sequence first breaks. Preserve the consecutive original covered rows in
    their original order from the bed's starting row. Thus A–B–C–D–E changed
    to A–B–C–E–D ends after C, with no restart on the separated tail or new
    coverage across unrelated rows. This 2026-10-26 Producer correction
    supersedes the earlier starting-row-only fallback and CLI clarification.
    Put a warning icon at that new endpoint:
    **Music shortened by this move**, with its previous ending identified by
    row content and retained settings. Preview while dragging; cancellation
    removes the preview; Undo restores the original span and clears the warning.
    Distinguish music, omission, moved marks and insertion cues without relying
    on color. Matthew adopted this addition on 2026-10-26.
    Continue the line through an expanded row's height in Sorting, including
    when Stash folds away. Do not add it to the reused normal-script/Stash
    preview renderer unless already supported there. Ten readable collapsed
    rows remains the target; report an unmet target without shrinking text or
    removing thumbnails/excerpts.

## Implementation recommendations

- Expanded body clicks select/read text or inspect read-only cards; they never
  collapse the row. Keep a summary/collapse strip and keyboard equivalent.
  Expanding another row anchors that row's summary on screen. Collapse an
  expansion before dragging so moving targets do not resize unexpectedly.
- If the actual two-column row cannot fit beside the sidebar at 1024 pixels,
  temporarily fold Stash away and restore it on collapse. Verify the fit before
  choosing that treatment; do not shrink or rebuild S03 into a different row.
- Inspecting a saved multirow bundle previews the whole bundle, starting at the
  clicked row. Preview does not restore it or alter trial selection.
- Proposed normal-authoring entry: Show Stash opens its sidebar; Edit Stash
  opens a full-width view of editable saved rows. Excluded status stays clear.
  Do not pretend that changing a trial Stash edits the original saved Stash.
- Whole-section movement gets a section mark instead of marking every child.
  Restored rows get a distinct Restored mark; stashed rows live in the sidebar,
  without gap-filling tombstones in the outline. Keep these separate from the
  orange omission shape, selection and insertion line.
- For a trial with no changes, Done returns without writing. Provide Discard
  sorting in the sorting toolbar; confirm only when it would lose trial work.
  Leaving/reopening should preserve a recoverable trial, never silently accept
  or discard it. If the canonical document changes, refuse stale acceptance,
  retain the trial, and offer review/discard; no automatic merge or overwrite.
  Use the bounded #310 storage/recovery handoff below.

## Opus CLI consultation

One tools-disabled Opus/high CLI consultation completed on 2026-10-25. This was
product critique, not a code review or a Claude Design request. Main dispositions:

- Keep literal opening/ending excerpts. Identical collapsed summaries are a
  deliberate hard case; click expansion should reveal their different middles.
  Do not invent summaries or secretly find different opening words.
- Orange can look like a cut or warning. Test the gap shape in context with
  selection, moved marks and a drop line, including grayscale. Reserve its
  meaning locally for omitted summary content.
- Preserve multi-visual X → Y → X endpoints; indicate the hidden middle visual.
- Actual S03 renderer reuse, expansion with Stash open, and provisional-session
  acceptance are the highest risks. Do not use another approximate script view.
- Keep the first comparison focused on density/context; demonstrate the session
  and Stash controls in a second controlled state using the same content.
- Opus suggested 1440×900 for one check; retain this issue's actual required
  viewports, 1280×800 and 1024×768, instead.

## Capability boundary and next checks

| Promised action | Existing evidence | Limit / work before construction |
| --- | --- | --- |
| Row/group/section move, saved ordered Stash/restore, local Undo | #307 / merged PR #308; real row-edit and consumer tests | Reuse; no new proof campaign for already tested behavior. |
| Long-copy excerpts, OC styling, endpoint thumbnails, omission marker, left handle | Existing typed content and ordinary presentation changes | Check fixtures and rendered pointer/keyboard behavior; no provider or Resolve work. |
| Exact expanded/previewed S03 row | Accepted S03 renderer is source authority | Reuse it in read-only mode; compare actual structure/rendering. The r10 navigation stand-in is insufficient. |
| Trial Accept/Discard, stale accept, recovery | #310 / merged PR #315; focused trial and consumer tests | Reuse the [bounded handoff](../../plans/issue-310-sorting-stash.md); canonical installation is one caller transaction, local serialization has explicit limits, and no storage service/collaboration merge is delivered. |
| Edit saved Stash content | #310 / merged PR #315; saved-content editing, restore and real consumer tests | Reuse the handoff's identity/attachment and exclusion limits; this is not automatic text tokenization or anchor repair. |
| Music-bed line, intact group, first-interruption shortening, cancellation and Undo | #307/#310 prove intact moves, prior-endpoint retention and Undo, but the former shortening always ends at the starting row | [#326](https://github.com/mbelinkie/vera-script-to-timeline/issues/326) must prove the corrected first-interruption rule before functional construction. The fixture records intended behavior, not completed proof. Rendered layout/accessibility/density checks also remain pending. |
| Audio/transition intent and runtime delivery | Exact #307 handoff and #292 limits | Keep supported intent/refusal states. No new audible trim, fade, mix, delivery, or implicit Resolve update. |

The bounded #310 proof is now Closed, delivered through merged PR #315 with
successful Validate. Its handoff supplements #307; it does not authorize a
design restart or lift unrelated capability/Producer holds. This preparation
dispatches no implementation or design request. The separately authorized
CLI-only prompt consultation does not lift any design hold.
The later music correction adds an unresolved #326 capability requirement;
the old starting-row-only result must not be presented as equivalent evidence.

Acceptance checks for the eventual revision:

- Both densities use the same long fixture; report fully visible collapsed rows
  with no expansion at both required viewports. Do not treat expanded mode as
  needing ten visible rows. Human recognition still needs Producer judgment.
- OC → VO → OC styling survives excerpting and expansion; same opening/ending
  rows expose their different middles on click without generated text.
- One, two and three-plus foreground visuals, identical endpoints, missing
  endpoint and overlay-only controls use correct thumbnails/omission markers.
- One full S03 row expands/collapses without accidental selection/move, text
  selection remains usable, the next expansion preserves position, and the
  narrow viewport/sidebar conflict is resolved explicitly.
- The left range handle, keyboard alternative, session marks and Undo agree.
- With Quiet piano present, both layouts still target ten fully visible
  collapsed rows at both viewports. Verify the right gutter outside thumbnails,
  start/end marks, intact group move without warning, supported ending-row
  move with warning after the last uninterrupted covered row (chalk-crescent
  in this fixture), the five-row D/E swap ending after C, keyboard/click
  explanation, drag cancellation and Undo. These rendered checks are pending
  the future authorized design pass; no audio playback is claimed.
- Trial move/Stash/restore → read-only script preview → Return retains trial;
  Accept applies it once; Discard leaves the starting script/Stash intact.
  No-change, interrupted session and stale acceptance have honest outcomes.
- Show Stash supports drag in/out plus explicit keyboard placement; item
  preview preserves positions. Normal-mode full Stash editing preserves
  identity and exclusion when restored. No exports are required for this pass.
