# Claude brief: make S05 a comprehensive outbound timeline-change review

Continue editing the existing **Script to Timeline — Prompter Runtime and Suite Navigation S04–S06** design artifact. Work only on S05 unless a shared label must change for consistency. Preserve the approved S04 experience and keep S06 deleted.

Use your own product-design and interaction-design judgment. You may pause before editing to ask Matthew focused questions about the design, especially if row density, responsive presentation, or interaction behavior remains unclear. Do not guess through a material product decision. You do not need to ask questions if the brief is clear. Once any questions are resolved, implement, exercise, and verify the design rather than merely describing it. This remains a design simulation and is not Producer acceptance.

## Product decision

S05 is now solely a review of what VERA is about to push from the current script into a new Resolve timeline version. It is not the place to review changes made in Resolve or align those changes back into the script.

Remove the entire inbound Resolve-change experience from S05, including:

- **Changes in Resolve**;
- **Review Resolve changes** and its review panel;
- accepted-cut and restore controls in S05;
- Resolve-side conflict cards and the **Keep my Resolve edit / Take the script change** chooser.

Inbound comparison and reconciliation will belong in the S01–S03 authoring experience, now or in a later design pass. Do not redesign S01–S03 in this artifact. For this S05 prototype, assume any required inbound reconciliation has already happened before the user reaches the outbound update review.

Preserve the distinction between:

- first-time **Create timeline**, where no change-review section is needed; and
- later **Update timeline**, where the comprehensive outbound review described below is required.

Every update still creates a new timeline version beside the current one and never overwrites the current version.

## Replace the summary list with a comprehensive row-level diff

The current **Changes in the script** list is too abstract. Replace it with a detailed view of every affected script row and the exact change that will be sent to Resolve.

Use a self-explanatory heading such as **Changes to send to Resolve**. The page should answer, without requiring the user to return to the script:

- which script rows are affected;
- where each affected row sits in the script;
- what content is being added, removed, or changed;
- what VERA will do to the new Resolve timeline version for that row; and
- which row changes the user has chosen to include or skip.

Show affected rows in script order and group them by section. Preserve the recognizable two-column script structure where useful: narration on the left and the corresponding visual, media, direction, or production content on the right. Do not collapse multiple affected rows into one high-level sentence.

### Exact Revision A to current-script example

Use the following eight logical row changes in the connected Update timeline scenario. All eight are included by default. Replace the current abstract summaries, including **Two new narration lines about the archive view**, with these actual affected rows and their exact timeline consequences.

1. **Added row — archive capture**
   - Revision A: row absent.
   - Current narration: `[VO] The archive preserves one view each morning.`
   - Current production content: `Periodic Webpage Capture: https://page.example.invalid/archive; motion Slow drift — top center v1`.
   - Location: immediately after `[VO] The warning appears directly beneath the second reading.`
   - Timeline consequence: **Add narration and capture items**.

2. **Added row — uploaded sensor image**
   - Revision A: row absent.
   - Current narration: `[OC] Here is the sensor before the trial began.`
   - Current production content: `Uploaded Image asset-demo-still-01; slow zoom; focus subject face`.
   - Location: immediately after the new archive-capture row.
   - Timeline consequence: **Add narration and image items**.

3. **Removed row — earlier-review screenshot**
   - Revision A narration: `[VO] This frozen screenshot came from an earlier review.`
   - Revision A production content: `User-uploaded screenshot asset-demo-screenshot-01`.
   - Current script: row absent.
   - Old location: immediately after `[VO] A second still shows the repaired housing.`
   - Timeline consequence: **Remove narration and image items**.

4. **Partially changed narration row — operator description**
   - Revision A narration: `[VO] The operator described the change as “slow.”`
   - Current narration: `[VO] The operator described the change as “slow, then sudden.”`
   - Production content remains: `Logged source clip, selected range 00:24–00:32; source audio on`.
   - Timeline consequence: **Replace the narration text; keep the existing source-clip instruction**.

5. **Partially changed production column — housing image motion**
   - Narration remains: `[VO] A second still shows the repaired housing.`
   - Revision A production content: `Linked Image https://images.example.invalid/housing.png; focus Center`.
   - Current production content: `Linked Image https://images.example.invalid/housing.png; motion Slow zoom v1; focus Center`.
   - Timeline consequence: **Update this row's visual treatment to add Slow zoom v1**.

6. **Moved row — chime**
   - Narration in both revisions: `[VO] A short chime marks the second reading.`
   - Production content in both revisions: `Music/SFX cue demo-chime-v1; start at the anchored phrase`.
   - Revision A location: immediately after `[VO] Viewers saw the demonstration in its original online context.`
   - Current location: immediately after `[VO] The warning appears directly beneath the second reading.` and before the new archive-capture row.
   - Timeline consequence: **Move the narration and chime cue together to the new position**.
   - Display the complete row in red at the old location and in green at the new location. These are two representations of one atomic selected change, not two counted changes.

7. **Partially changed section-marker row**
   - Revision A: `Section: Conclusion`.
   - Current script: `Section: Closing`.
   - Timeline consequence: **Rename the Resolve marker from Conclusion to Closing**.

8. **Partially changed closing narration row**
   - Revision A narration: `[OC] We adjust only after the second reading.`
   - Current narration: `[OC] The second reading tells us when to adjust.`
   - Timeline consequence: **Replace the closing narration text**.

Present these changes in their actual script positions rather than in the numbered order above when that order differs. The connected scenario begins with the summary **8 row changes selected; none skipped**. Although the moved row is rendered at two positions, it counts once, so the total remains eight.

### Required change treatments

- **Entirely new row:** show the complete row as an addition, with a green addition treatment and an explicit non-color label such as **Added row**.
- **Entirely removed row:** show the complete prior row as a removal, with a red removal treatment, strikethrough where readable, and an explicit label such as **Removed row**.
- **Partially changed row:** show enough unchanged context to identify the row, with removed text/content in red and replacement or added text/content in green. Make the before/after meaning unambiguous without depending on color alone.
- **Moved row:** show it at both affected locations—red where it is removed from the old location and green where it is inserted at the new location—with explicit **Moved from** and **Moved to** labels and enough shared identity to make clear that these are the same move, not a deletion plus an unrelated addition.
- Cover changes in either script column, not narration only. If a row's media, visual instruction, cue, marker, camera state, or other timeline-relevant content changes, show that exact affected content and the resulting timeline action.

The review must be comprehensive: every row that would cause any timeline change appears, whether the whole row is new/removed or only part of the row changed. Rows with no timeline effect do not need to appear.

## Row selection

Put a checkbox at the left of every affected row entry. All changes are included by default.

- A checked row means **include this row's displayed change in the new timeline version**.
- Clearing the checkbox means **skip this row's displayed change for this update**.
- Use accessible labels that name the row and whether the action is currently included or skipped.
- Provide a concise selected/skipped count that updates everywhere it appears, including the sticky action area and confirmation.
- Begin with **8 row changes selected; none skipped**. Use the same eight-change denominator in the review header, sticky action area, confirmation, and result. For example, after clearing one checkbox, show **7 row changes selected; 1 skipped**.
- If useful, provide **Select all** and **Clear all**, but do not let bulk controls replace the row-level checkboxes.

For a move shown at both its old and new locations, treat the move as one atomic change. The two visible occurrences should clearly share one selection state; toggling either occurrence includes or skips the whole move. Do not allow an accidental half-move that silently duplicates or deletes the row. If you believe independent control is important, ask Matthew before implementing it.

## Action and confirmation

The primary action remains **Update timeline** when Resolve Studio is available. Before applying, show a confirmation that summarizes:

- the number of affected rows;
- how many row changes will be sent and how many will be skipped;
- that the update starts from a duplicate of the current Resolve timeline;
- that the current timeline version remains untouched; and
- any limits that still require checking by hand.

The confirmation need not repeat the entire diff, because the comprehensive review remains directly behind it and can be revisited. After the simulated update, report the same counts in past tense and identify the newly created timeline version.

Resolve Free remains a truthful manual-import flow. Its review should still show the comprehensive selected outbound row changes, but it must not claim to inspect or preserve edits in the existing Resolve timeline. Its primary action prepares a timeline file/package and then gives explicit manual-import instructions.

Disconnected, unsupported-version, and broken-link states may still let the user inspect and select outbound row changes, but cannot perform the update until the connection problem is resolved. Do not show stale inbound Resolve-change data as part of this review.

The broken-link state still needs explicit recovery actions: one to find/link the existing timeline and one to create a fresh timeline from the current script. Do not leave the user with only a disabled Update button.

## Visual and interaction requirements

- Green and red are semantic aids, not the only signal. Pair them with addition/removal wording, icons, and/or strikethrough.
- Keep row identity and section/location legible at both supported viewports.
- Prefer one vertically scrolling review over independently scrolling columns.
- Preserve visible keyboard focus and logical checkbox order.
- At `1024 × 768`, stack or reflow the two-column row content without losing the association between narration and its paired production content.
- Keep the interface detailed but scannable: compact rows, clear section dividers, and progressive disclosure for secondary timeline-action detail are preferable to oversized cards.

## Verification before replying

Exercise at `1280 × 800` and `1024 × 768`:

1. First-time Create timeline, confirming there is no update-diff section.
2. Connected Update timeline containing:
   - both wholly added rows named above;
   - the wholly removed screenshot row;
   - both partial narration changes;
   - the housing-image production-column change;
   - the section-marker rename; and
   - the chime row shown at both its old and new positions.
3. Toggle all eight logical row changes off and on individually and verify selected/skipped counts after each action.
4. Toggle a move from both visible locations and verify it remains one atomic selection.
5. Confirm and complete the simulated Studio update, verifying consistent counts and new-version language.
6. Exercise the Resolve Free preparation/import path without inbound-inspection claims.
7. Exercise disconnected, unsupported, and broken-link states, including both broken-link recovery actions.
8. Confirm that no **Changes in Resolve**, **Review Resolve changes**, accepted-cut/restore control, or Resolve-side conflict chooser remains anywhere in S05, including accessible labels and dead interactions.

Fix issues discovered during verification before replying. Do not mark issue #58 complete or imply Producer acceptance.
