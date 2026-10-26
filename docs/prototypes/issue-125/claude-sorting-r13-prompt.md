# Sorting A — focused revision after r12

Prepared revision brief, consulted through the Claude CLI and submitted to Claude Design on Matthew's explicit instruction on 2026-10-26. Receipt was verified: Claude read the complete attachment and began listing project files. The whole design revision remains held while #337 and #326 lack their required proof, unless Matthew explicitly defers the affected scope. Submission and presentation corrections do not lift that gate.

## Decision and scope

Matthew has selected **A · Line**. Make A the adopted Sorting layout in a versioned successor to **S03 Outline Sorting Comparison r12**. Preserve r12 and the historical B comparison; do not keep developing B or redesign unrelated surfaces. No export.

Keep the supplied twenty long rows, their narration and word-level On Camera formatting intact. Add only the two separate fictional clip rows below. Use the existing thumbnail atlas and map; do not generate replacement imagery. The expanded-row photo mismatch is an acknowledged prototype limitation: this pass does not rebuild the S03 renderer.

## 1. One orange omission cue

Replace A's vertical orange omission line with **one orange ellipsis (…) between the literal opening and ending excerpts**. Remove the line and redundant truncation dots. Show this cue only when actual middle text is omitted; show short content once.

Choose excerpts at word boundaries and keep the ending readable. Do not use CSS ellipses that create additional omission markers. Preserve On Camera bolding only on words that have that meaning. The ellipsis is an omission control/indicator, not narration and not On Camera.

Its horizontal position follows the available space and the lengths of the two excerpts. It does not encode a time, a percentage of the row, or the amount omitted. Previously the nonshrinking ending excerpt, flexible opening and variable thumbnail-cluster width moved the orange line.

Reserve a consistent right-side cluster width across rows: two equally sized endpoint slots plus a fixed space for the fixture's +N indicator. Photo, On Camera and unavailable endpoint slots use the same dimensions. Right-align a lone thumbnail without drawing an empty second slot. Keep the music gutter separate. This stabilizes the text area; do not force the omission cue into a fixed column or imply that it represents timing.

## 2. Two standalone Full-audio clip rows

A clip with full audio MUST occupy its own row. Do not mix host narration with a Full-audio clip. Each example below is a separate visual-only footage row using existing S03 source-audio behavior. Its narration field is empty.

For compact Sorting, use its clip transcript as the text summary, in quotation marks and normal weight. Proposed wording: lead with a plain “Original audio” label so a quoted narration row cannot be mistaken for clip speech; do not introduce a new badge color or audio mode. Apply the same opening/ending omission rule when it will not fit. The quoted text represents source speech; it is not authored narration and must not be copied into the narration field. In the expanded S03 row, the transcript belongs on the right-hand clip card, with the narration column empty. Preserve the existing distinction in exports and other consumers.

Use the following fictional demonstration transcripts verbatim, without On Camera bolding. Existing atlas photos can act as clearly fictional footage poster frames; no real media, playback, transcription service or audio asset is needed or claimed.

**Clip example 1 — Harbor caretaker**
Insert after the tide-notebook row in Harbor Arrival. One footage clip, Original audio; atlas tile 2 (ticket window).
Transcript:
“The bell rings twice when the little ferry leaves, but nobody here agrees about what the third ring means. My aunt said it was for lost umbrellas. The man who repaired the roof said it was a warning about soup. I have worked at this window for twelve years, and every time I ask, somebody gives me another answer. So now I write them down in the blue notebook and let the passengers decide.”

**Clip example 2 — Workshop recording**
Insert after the paper-model row in Working Shore. One footage clip, Original audio; atlas tile 9 (paper model).
Transcript:
“We built the first version from a cereal box because that was what we had on the table. The tower leaned to the left, the doors were much too small, and someone had drawn a fish where the stairs should have been. But when we put the lamp behind it, the shadows looked exactly right. We kept the crooked tower in every version after that, even when we finally found some proper cardboard.”

Both new clip rows belong to the starting fixture, not the user's sorting history. Neither shows a Moved mark on load. Both insertion points are outside the existing Quiet piano span over amber lantern, chalk crescent and paper signal frame, so that span remains unchanged.

Make these rows recognizable as clip speech when collapsed. In expansion retain the source identity and established clip-audio controls. Use “Original audio” as the row-type label; this wording change introduces no new audio mode. Do not add editing controls to Sorting or introduce a new audio mode.

## 3. Stash: active Add Section, once proved

The requested behavior is an active **Add Section** under Stash: create and name a Stash section and organize saved rows into it. Organizing Stash is the deliberate exception to Sorting's content-edit restriction. Narration and clip transcripts remain read-only while sorting changes are pending.

Treat section creation, naming, membership and order as part of the same pending sorting changes: the read-only script preview must not silently accept them; Accept applies them and Discard restores the starting organization. Use one chronological Undo history for all completed pending sorting operations, including row moves, Stash membership and section creation, naming and order. After a row move followed by a Stash rename, two Undos reverse the rename and then the move. Cancellation while naming leaves no accidental empty section and adds no Undo entry. Accept or Discard ends that pending history.

Saved rows remain independent. Stashing several rows creates neither a mandatory bundle nor an automatic section. Explicit multiselection can restore multiple rows together. Keep Show Stash and its saved-row count; section headings do not add to that count.

**Capability hold:** #337 is still open. Its executable handoff must cover independent restore, Stash sections, local Undo and pending-change behavior before these interactions are shown as working. Do not fake active Add Section, silently retain the obsolete bundle behavior or substitute a backend investigation. Until proof is available, retain this requirement in the brief, preserve the existing artifact, and do not start this revision. A future authorized revision must not expose the old mandatory-bundle restore as the adopted interaction. Identify remaining limitations outside the product frame.

## Preserve established behavior

- Content-based row identity; left selection gutter, one left group-move handle, cross-section placement and complete-section movement.
- Colored Moved mark in its reserved left slot. It clears when the row returns to its starting place.
- Right-only endpoint thumbnails, +N between endpoints for hidden visual beats, neutral On Camera slots, honest unavailable images. No new thumbnails on the left.
- Photo hover/keyboard enlargement without layout shifts; no hover enlargement for On Camera or unavailable slots; suppress previews while dragging.
- Single-click summary expansion/collapse with a persistent summary header; interacting inside the expanded content does not collapse it. Preserve keyboard equivalents and Escape behavior.
- Quiet insertion line during movement; no visible destination sentences. Keep accessible destination announcements.
- Back to script shows the proposed ordering read-only with Accept sorting and Return to sorting, plus a clear Discard path. No user-facing “trial” or developer labels.
- The music-bed gutter and existing intact Quiet piano span remain. #326 still holds changed-span audio behavior: the intended rule is to retain the consecutive original sequence from the bed's start until its first interruption, warning at that endpoint. Do not substitute “always ends with its starting row” or claim unsupported playback/trim operations.

## Check the focused revision

At 1280×800 and 1024×768, verify at least ten readable collapsed rows with real atlas images. Do not shrink type to force the count. Check a long narration row, a short row without omission, mixed On Camera formatting, both standalone Full-audio rows, one/two endpoints, hidden visuals and unavailable imagery.

Check one orange ellipsis only, readable literal endings, quoted clip speech, empty narration in expanded Full-audio rows, left Moved marks, selection, expansion, keyboard operation, cancellation and Undo. Check Stash organization and Accept/Discard only after the proof hold is cleared. Report actual density and remaining limitations outside the product frame.

Stop after this focused A revision for Matthew's review. No export, production API/schema change or unrelated redesign.

