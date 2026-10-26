# Prepared Sorting revision prompt — NOT SENT

Prepared 2026-10-25; music-bed instructions added 2026-10-26. This update
does not authorize design submission. Matthew separately authorized one Opus
CLI consultation on the full prompt on 2026-10-26; refinements are included.
Do not submit automatically.
Before sending, recheck the capability matrix in
[the revision brief](sorting-revision-brief.md), resolve its missing proofs,
and attach that brief plus [the fixed long-row copy](sorting-long-rows.md).
Do not assume Claude Design can read local repository paths. Supply both files
with the eventual request. No export is requested.
Sender note: this header is internal handoff context, not part of the design
message. Send only the prompt below, with the two referenced attachments.

## Prompt for the next focused comparison

Continue the actual r10 **S03 Outline Sorting Comparison** in the existing
VERA project. Neither A nor B has been selected. Preserve r10, the ordinary
S03 authoring renderer, the shared review pages and earlier sources; work on a
named successor comparison. Do not reconstruct S03 from these notes.

The decision is how compact an outline can be while preserving enough context
to recognize and rearrange long rows. Revise both Line and Strip with the SAME
attached 20 full rows, sections, coverage and behavior. Do not write replacement
copy or shorten underlying rows. Fixture IDs never appear as row numbers. Keep
literal opening/ending excerpts; no generated summaries. Several rows have
identical openings and endings on purpose: expansion reveals their middles.

Apply these corrections to the comparison:

1. Bold means On Camera at the exact word/range level. Voiceover stays normal.
   Preserve mixed spans in excerpts and full rows. Never bold a phrase merely
   because it is the beginning or end of a row.
2. Single-click a summary to expand it inline using the actual standard S03
   two-column row, read-only. Only one expands at a time. Click its summary
   again to collapse; expanded-body text selection/clicks do not collapse it.
   Provide an explicit collapse affordance and keyboard equivalent. Remove
   Open row, the separate open icon and double-click navigation. Expanding the
   next row should keep that row's summary in view.
3. One planned foreground visual gets one left thumbnail. Multiple foreground
   visuals get first on the LEFT and last on the RIGHT. Count sequence beats,
   not distinct images: presenter → insert → same presenter still gets both
   endpoints. Overlays do not add foreground beats. Keep unavailable endpoint
   slots with honest placeholders; do not invent acquired footage.
4. Show where middle text or visuals have been omitted. Try an orange vertical
   divider with space around it, plus a non-color shape/accessible meaning.
   It must read as skipped summary content, not a warning, cut or drop line.
   Two endpoint visuals omit no visual when the sequence has only two beats;
   three-plus beats can omit middle visuals even when endpoints look identical.
   Text and visual omission need not occur together.
5. Keep gutter click/drag/Shift selection within one section, the group outline,
   and one Move N rows handle on the LEFT by the selection. Body click expands;
   gutter drag selects; handle drag moves. Retain insertion line, Move to…,
   keyboard selection, cancellation and Undo. No checkbox squares.
6. Show a quiet Moved mark for rows deliberately moved from the starting order;
   clear it when returned to their original place, including through Undo.
   Do not mark every displaced neighbor. A section move marks the section.
   Keep moved/restored status distinct from omission and selection.
7. Show the attached **Quiet piano** music bed as a thin continuous line in a
   dedicated RIGHT gutter, outside ending thumbnails, with clear start/end
   marks. It spans the amber-lantern, chalk-crescent and paper-signal-frame
   rows. Preserve it in both layouts without reducing the ten-row target.
   When a covered row expands, the line continues through its expanded height
   in the same right gutter, including when Stash folds away. This line belongs
   to Sorting; do not add it to Back to script or the Stash preview unless the
   actual reused S03 renderer already provides it.

Keep the first comparison focused on context and density. Also retain three
small no-omission/overlay controls outside the 20 long rows: one short On Camera
row (**The harbor light is green.**, presenter only); one visual-only row
(harbor door, no narration); one short VO row (Rain gathers along the window.,
window foreground plus a lower-third overlay). These are fixture controls,
not more text for you to invent.

For the related interaction demonstration, use the same data and shared
components. Do not create a separate approximation of S03:

- Sorting is a provisional trial. Moves, Stash and restore change the trial.
  Script and Stash text stay read-only until Accept or Discard. Back to script
  shows the proposed order in the REAL S03 renderer, read-only, with a floating
  bottom bar: Accept sorting / Return to sorting. Returning retains the trial.
  Accept commits it once; Discard sorting restores the starting script AND
  Stash. A no-change session can return with Done. Keep pending/stale-session
  outcomes within the attached capability evidence; never silently overwrite.
- Use Show Stash with an adjacent saved-row count in both normal and Sorting
  views. In Sorting, the sidebar accepts dragged rows and lets bundles drag
  back to explicit gaps; include keyboard placement alternatives. Preserve
  bundle order and row identities.
- Clicking a saved item opens a wide temporary read-only preview over the main
  area, starting at that item within its bundle. Closing returns to the same
  sidebar/outline positions without restoring anything or changing selection.
  If expanded S03 cannot fit beside Stash at 1024 pixels, temporarily fold the
  sidebar and restore it on collapse; verify the fit rather than squeezing S03.
- In normal authoring, Show Stash must also lead to full-width editing of saved
  rows. Clearly retain exclusion from the active script/build. During a trial,
  explain that content editing resumes after accepting or discarding sorting.
- Demonstrate the music-bed cases specified in the fixture, resetting between
  cases. Moving all three covered rows together preserves the bed without a
  warning. Moving only its ending row after the paper-lanterns row, within
  the same section, shortens the bed to the end of its starting amber-lantern
  row. The bed now covers ONLY amber-lantern; chalk-crescent is no longer
  covered even though it did not move, per the proved starting-row rule.
  Put a warning icon at THAT new endpoint, even though the starting row
  did not move. Clicking or keyboard-activating it says **Music shortened by
  this move** and identifies the previous ending by the row's content.
  Retain the original endpoint/settings for review. Preview the interruption
  while dragging without committing it; cancellation clears that preview.
  After dropping, Undo restores the bed, row order and warning-free line.
  Keep music warnings distinct from the orange omission marker, selection,
  moved marks and drop line using shape/labels as well as color. Use rows
  outside the bed for Stash tests; retain explicit review/refusal for other
  unsupported audio-span edits, rather than simulating their success.
- Preserve the existing attachment, transition-review and audio intent limits
  in the attached brief. New joins are cuts; separated original transition
  pairs need explicit review/reapplication. No implicit Resolve update and no
  new claim of audible trimming, fades or mixing.

Verify both **1280×800 and 1024×768**. Report fully visible collapsed row counts
for A and B, aiming for at least ten without unreadably tiny text. Expanded
states do not need ten rows. If the gutter prevents ten readable collapsed
rows, report the actual count and unmet target; do not shrink text, remove
thumbnails/excerpts or claim a pass to recover the count.
Test mixed OC/VO, identical excerpts, single/multi
visuals, missing thumbnails, omission in grayscale, gutter versus summary
clicks, the left group handle and keyboard focus. Check Stash empty/populated
and sidebar/expanded-row width. Verify the music line/endpoints, intact versus
interrupted moves, warning explanation, drag cancellation and Undo in both
layouts at both viewports; report their collapsed density with the music
gutter present. These rendered checks await the future authorized design pass;
the fixture supplies no audio asset or playback. Do not claim a prototype
proves production mechanisms; use the attached evidence and state any mismatch.

Recommend A or B based on context retained per screen, recognition failures,
and expansion cost. Report the hardest case for each. STOP after the focused
comparison and representative interaction state; wait for Matthew's choice
before propagating either layout. No full redesign or export.
