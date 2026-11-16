# Unified Stash: design decisions (#125, Stash-first pass)

Started 2026-10-28. Producer decisions for the Stash-first phase. Updated as decisions are made.

## Scope
- This pass designs the unified Stash itself: mixed compact notes, standalone clips and complete script rows, nesting, user sections, editing, empty states and supported refusal states.
- S03/Sorting integration is a separate, later pass. No competing Stash design issue.
- Starting files: `S03 Outline Sorting Comparison r14.dc.html` (Sorting) and `S03 Comments Placement Comparison r1.dc.html` (comments sidebar, built on Shared S03 Review Foundation r11). Preserve accepted baselines and the existing visual language.
- Only operations proven by #337, #340, #341 and #342 are depicted as working. #342's discussion limits and ambiguous-projection refusals still apply. This is not a production editor or a collaboration service.
- Music (#326), motion and framing gaps stay explicitly stated. #125's Producer review and faithful-export requirements still apply.
- This authorizes the Stash-first phase only, not acceptance of the whole issue.

## Settled before this pass (not reopened)
- Plain notes become nonspoken stage directions when placed. Explicit spoken intent is kept.
- An untouched item returns to its note or clip form. An edited item returns as an ordinary script row. Undoing the edit restores the note or clip return.
- Partial return: if the parent is still in the script, the child returns as a top-level note in its original section. If the parent is in Stash, the child returns to its original nested slot.

## Decisions
1. **Stash count.** Every entry counts equally, top-level and nested alike, because a top-level note may be a subject header or real material. The button shows the total. The header breaks it down by kind, for example "6 notes · 1 clip · 2 rows", and the button and header always agree. *Revised 2026-10-28: previously the button counted top-level items only.*
2. **Notes are plain text.** Stash does not distinguish speech from stage directions. Notes show no brackets, no Spoken tag and no Make spoken. Nothing in Stash is spoken or built, so the distinction is left to the script. When placed, a whole note becomes one stage direction (the settled default). The writer marks spoken words in the script with the existing #341 controls. Saved rows in Stash keep their spoken and direction text unchanged. *Revised 2026-10-28: replaces muted-italic directions with a per-note Spoken tag. Cost accepted: a mixed note arrives as one direction and is split in the script.*
3. **Word action while editing (script rows and saved rows only).** The action follows the selected words: direction text offers **Make spoken**, spoken text offers **Make stage direction**. Deleting either bracket of a direction pair removes both (#341). Notes have neither action. *Revised 2026-10-28.*
4. **Lone or unmatched `[` (script rows and saved rows).** Only the bracket character gets the stage-direction style (muted gray italic). The surrounding words stay spoken style. No automatic classification and no prompt (#341). In a note, a typed `[` is ordinary text and is kept (see decision 56). Build note: the lone bracket is muted gray but not italic, so it reads differently from a real direction pair. *Revised 2026-10-28.*
5. **Parent note whose children are all placed.** It stays in Stash as an ordinary note with no expand arrow. An untouched child can return under it later.
6. **Edited parent and untouched children returned together.** #342 refuses this. Nothing changes. The message explains why and offers one action: return only the untouched notes. No Undo shortcut, because Undo always reverses the latest action, not a chosen edit. *Revised 2026-10-28. **Superseded 2026-10-29 by decision 54:** the refusal is removed as intended product behavior.*
7. **Variants.** One design, no side-by-side comparison.
8. **Surface.** The light authoring sidebar from Comments r1. The dark Sorting drawer waits for the integration pass.
9. **Creating and nesting notes.** **Add note** at the top of the sidebar, plus a quiet **+ Note** at the end of each section (Add clip joins the top controls: decision 57). Enter adds a sibling, Tab indents, Shift+Tab outdents.
10. **Where editing happens.** Notes edit inline in the sidebar. Saved rows open in the wide Edit Stash view.
11. **Return to notes.** A placed note or clip that is still untouched shows a **Return to notes** button on its script row. The button disappears once the row is edited, and reappears if that edit is undone. Edited rows can still be stashed through ⋯ › Stash, and return as rows. The button lives on the script row, so it is drawn in the S03/Sorting integration pass. *Added 2026-10-28.*
12. **Clips are logged Research clips.** A Stash clip is a clip already logged in VERA Research for this project: a source video plus its logged in/out range, excerpt and provenance. Local files from the computer are not the intended use. The typical flow: scribble a note, then pick footage that would work for it. The clip sits under the note as a child. A clip can also stand alone at the top level. *Added 2026-10-28.*
13. **Adding a clip.** The note's **+ Footage** action, and **+ Clip** at the end of each section, open the existing "Clips already logged in VERA Research for this project" picker from S03 footage cards, including **Open in VERA Research** when the needed clip is not logged yet. *Added 2026-10-28; replaces the "Stash this visual" entry from the review commitments.*
14. **Placing a clip.** A placed clip becomes a regular Footage row with its logged range, exactly as if it had been chosen on a footage card. A placed note with clip children becomes a direction row followed by separate footage rows, in outline order. Clips are never automatically attached to a neighboring narration row. *Added 2026-10-28.*
15. **Unavailable clips can be placed.** If a logged clip's source is unavailable (the video was removed or made private, or the media was never downloaded), placement is allowed. The footage row shows the existing S03 unavailable-media state and recovery entry points. *Added 2026-10-28; resolves the open missing-clip question.*

16. **Active sidebar button.** The active Stash or Comments button gets a gold (#c49b50) outline. *Added 2026-10-28.*
17. **Resizable sidebar.** The divider between script and sidebar drags to resize. The sidebar is at least 260px wide, and the script is never narrower than 560px, the width the two-column row needs. Double-click resets. *Added 2026-10-28.*
18. **Drag into the script.** Stash items drag into the script, grabbed anywhere on the item. A gold insertion line between script rows, section starts included, marks the gap. A note drags with everything under it. Alt/Option-drag places the note alone, and its children move up a level in Stash. Place in script… stays in ⋯ as the keyboard path. *Added 2026-10-28. Revised 2026-10-29: attached footage always goes with its note, including with Alt/Option; keyboard parity through Include items below (decision 58).*
19. **Drag out of the script.** While Stash is open, hovering a script row shows a grip. Dragging it into Stash moves the row out of the script (same result as ⋯ › Stash). An untouched placed note or clip returns as a note or clip; anything else arrives as a row. *Added 2026-10-28.*
20. **Drag within Stash.** Items drag to reorder, change section, and indent or outdent by dragging right or left. A gold insertion line shifts right to show the nesting level. Only notes hold items; notes, clips and saved rows can all sit under a note. *Added 2026-10-28.*
21. **Saved-row editor.** Clicking a saved row opens a standard two-column row (narration and visuals) floating near the top of the script, with the script dimmed behind it. It is editable, with Save and Cancel. *Revised 2026-10-28: replaces the light wide view.*
22. **Density.** 3px bullet, 10px indent per level. *Added 2026-10-28.*
23. **Sidebar shade.** Stash background #f0f1f3, grayer than r1's #fbfbfa. *Added 2026-10-28.*
24. **Collapsible sections.** Clicking a section title collapses it. A collapsed section shows its title and item count only. *Added 2026-10-28.*
25. **⋯ menu kept in full** for now (Delete, Place in script…, Edit, Add subnote, + Footage, Edit row, Move to section). No hover icons. *Added 2026-10-28. Revised 2026-10-28: Delete moved to first.*
26. **One-click delete.** Delete removes the item (and everything under it) with no confirmation. The toast and header Undo restore it. *Added 2026-10-28.*
27. **No help line.** The sidebar line "Nothing in Stash is in the script, prompter or build…" is removed. *Added 2026-10-28.*
28. **No bullets.** Notes show no bullet. Decision 22's bullet is withdrawn; 10px indent per level stays. *Added 2026-10-28.*
29. **Row ⋯ at top right is the handle.** The row menu (⋯: Stash, Delete row) applies to the whole row, so it sits at the row's top right, not under the last visual. It is also the drag handle: click opens the menu, drag into Stash stashes the row. No separate grip. The visuals column reserves a 24px strip above the first visual for it, on every row. + Visual stays under the visuals. *Added 2026-10-28. Revised 2026-10-28 (several passes; final).* Conflicts with Add row, Transition and comment controls are re-checked in the integration pass. Known: the between-row Transition button (Comments r1 pilot) is right-aligned in the 26px seam, about 6px above ⋯ on the same right edge; fixes if it crowds are nudging ⋯ left or showing only the control under the pointer.
30. **Saved row on white.** A saved row opens on white, laid out like a regular script row (narration left, visuals right), with only a slim Save/Cancel bar. No bracket instructions. *Added 2026-10-28; revises decision 21's presentation.*
31. **Saved rows place independently.** Rows are self-contained, so no row is ever refused for being placed alone. r2's citation-pairing refusal ("Can’t place this row by itself") is removed. *Added 2026-10-28.*
32. **Attribution.** Stash items carry their author and date, shown as in comments (@name · date) under the item. Your own items show no attribution. *Added 2026-10-28.*
33. **Text size.** The sidebar follows the script's Authoring size (80–150%). Controls are tiny Aa sliders, no A−/A+: one in the top bar beside Stash/Comments, one in Stash beside Add note / Add section, which scales Stash (80–200%) on top, so Stash text can match or exceed the script. Both persist per user. The sidebar's width stays as set; text reflows inside it. *Added 2026-10-28.*
34. **Undo lives in the top bar**, beside the text-size slider and the Stash/Comments buttons, not in the Stash header. *Added 2026-10-28.*
35. **Stash buttons read "Add note" and "Add section".** *Added 2026-10-28; revises decision 9's labels.*
36. **Note ⋯ menu simplified.** Delete, Place in script…, Add footage, Move to section. Edit note and Add subnote are removed (click a note to edit it; Tab nests). Clip and saved-row menus are unchanged. *Added 2026-10-28; revises decisions 13 and 25 for notes. Revised 2026-10-29: a note with footage shows Replace footage and Detach footage instead of Add footage (decisions 50–51).*
37. **Add footage puts the clip on the note's row.** A clip added with the note's Add footage is that note's footage. When placed, the note becomes the direction on the left and the clip the visual on the right, in the same row. Clips nested under a note any other way (dragged, Tab, + Clip) still become separate Footage rows. Moving the clip out from under its note ends the link. An untouched return brings the note back with its footage under it. *Added 2026-10-28; revises decision 14. Presentation and lifecycle revised 2026-10-29 by decisions 49–53: the footage shows inside the note, not under it.*
38. **Blank notes are removed.** Clicking away from a blank note removes it, the same as Escape. *Added 2026-10-28. Revised 2026-10-28: briefly kept blank notes on blur; reverted. Exception 2026-10-29: a blank note with footage never deletes the footage (decision 52).*
39. **Clicking a clip opens the standard clip player.** It is the same Clip player as clicking footage in the script (movable, resizable, Play/Pause, logged range), opened beside Stash. Its edit controls are on: Set in, Set out, Clear out, draggable in/out handles on the trim track, and the source transcript with click-to-seek. (In the current S03 review baseline those controls are switched off for script footage; turning them back on there is an integration-pass item.) Edits sync to the Stash clip and carry into the script when it is placed. Actions stay in ⋯. *Added 2026-10-28. Revised 2026-10-28: replaces a Stash-only player.* Proof gap: whether #340's stored clip payload accepts player edits while in Stash is not shown; transcript text is sample.

40. **Returns go back where they came from.** A row returned to Stash, untouched or edited, by Return to notes or ⋯ › Stash, goes back to its original section and position: after the nearest original sibling still in Stash, else before the next one, else as the first item under its note, else at the start of its section. An edited item returns as a row under its original note if that note is still in Stash in the same section. If the note is in the script or came back as a row, the item returns top-level where the note sat. Dragging into Stash still places the item at the drop point. *Added 2026-10-29. Fallback revised 2026-10-29 by decision 55.*
41. **Saved rows use the script's own row.** A saved row opens in the same row renderer as the script: cue brackets showing visual ranges, footage cards, stage-direction styling and the same controls. Whatever works on a script row works here, and nothing else. Save keeps the changes in Stash. *Added 2026-10-29; replaces decision 30's custom editor and its Make spoken / Make stage direction bar.*
42. **Select range in the script.** **Select range** is the last item in the row ⋯ menu (after Stash and Delete row). That row becomes the start, and the next click on a row ends the range (a hint bar says so; Esc or Cancel stops). The selected rows get one gold outline with a row count, and **every selected row shows its ⋯**. Each offers **Stash group**, **Delete group** (asks first, Undo stays available) and **Select new range** (keyboard mode: decision 60), and the range drags from anywhere inside it (not only its ⋯) into Stash, where it lands as a group at the drop point. With one row selected, the labels read Stash and Delete row. A range stays within one section: clicking a row in another section is refused with a message, and the range keeps waiting for its end. Clicking outside the range clears it. *Added 2026-10-29. Revised 2026-10-29: moved last, no ellipsis; the bottom action bar is replaced by ⋯ on every selected row; ranges can't cross sections.*
43. **Groups in Stash.** A stashed range becomes one group item: a "N ROWS" badge, the first row's excerpt, an orange **+N** for the rows between, and the last row's excerpt (just first and last for two rows). It drags, moves and places whole, and can sit under a note but holds nothing else. Clicking it opens all its rows together in the script's row renderer, with one Save. ⋯ has Delete, Place in script…, Edit rows, Ungroup and Move to section. Groups contain script rows only. An untouched note or clip in a range becomes a row (accepted). Saving, Undo and member rules are in decision 59. *Added 2026-10-29. Revised 2026-10-29: first row, +N, last row replaces the full bracketed list.*
44. **Placed groups aren't remembered.** A placed group becomes ordinary script rows in order. Nothing in the script records that they were a group, and no Return group exists. To stash them together again, select them as a range. Deleting or stashing them works like any other row, with no "came from Stash" warning. *Added 2026-10-29. Revised 2026-10-29: replaces Return group and the group's remembered origin.*
45. **Group count.** The Stash count includes the rows inside groups. The group itself isn't counted, like a section. The header reads, for example, "4 rows (2 in 1 group)". *Added 2026-10-29; extends decision 1. Attached footage counts as a clip (decision 49).*
46. **Stash size slider doesn't scale its own controls.** The Stash header and the Add note / Add section / Aa row follow only the script's Authoring size, so the slider doesn't move while you drag it. *Added 2026-10-29; revises decision 33.*
47. **Groups can grow while editing.** In the production design, the group editor lets you add rows (Add row between or after its rows, as in the script) and remove them, and Save writes the longer or shorter group back to Stash. Not simulated in r3, where the editor only edits existing rows. *Added 2026-10-29; extends decision 43.*
48. **Closing the row editor.** A saved row or group open over the script closes when you click the dimmed script around it, press Esc, or click the ✕ at the top right of the editor bar. With no changes it just closes. With changes, a bar asks "Save your changes to this row?" (or group) with Save, Don’t save and Keep editing. Cancel still discards without asking. *Added 2026-10-29. Revised 2026-10-29: asks about saving when there are changes.*
49. **Attached footage sits inside its note.** A note's attached clip shows as a compact footage strip below the note's text (thumbnail, clip title, duration), inside one subtle shared background or outline. The note text keeps full width, even in a narrow Stash. The attached clip is never drawn as another indented child item, and no explanatory label is added. Ordinary child clips and other items stay outside the shared background as separate indented items. Pointer: clicking the words edits the note; clicking the thumbnail or title opens the shared clip player (decision 39); dragging the note moves both; dragging the strip itself detaches the clip (dropped in Stash it becomes an ordinary item at the drop point, dropped in the script it becomes a Footage row). Tab/Shift+Tab, Move to section and Delete act on the note and its footage together, and the Delete toast names the clip. Count: the attached clip still counts as a clip in the button total and the header breakdown. *Added 2026-10-29; revises decision 37's presentation.*
50. **One footage clip per note.** A note holds at most one attached clip, because a direction row gives a second visual no spoken cue to start from. Once a note has footage, Add footage becomes **Replace footage**. Replacing keeps the old clip as an ordinary child item directly under the note; nothing is deleted. Ordinary child clips are never attached silently. *Added 2026-10-29.*
51. **Detach footage.** The note's ⋯ offers **Detach footage** when it has footage. The clip becomes an ordinary child item directly under the note, focus moves to it, and Undo restores the link. Nothing is deleted. To remove the footage, detach it and then delete it. This is the keyboard path for detaching. *Added 2026-10-29.*
52. **Blank text never deletes footage.** If a note with attached footage is left blank (Escape, or clicking away, as in decision 38), the footage stays as a standalone clip in the note's place. *Added 2026-10-29; exception to decision 38.*
53. **Separately placed attached clip.** Placing the attached clip by itself (dragging the strip into the script) makes an independent Footage row, and the note stays in Stash with no footage. When that clip returns untouched, it reattaches only to its original note, only if that note is still in Stash and its footage slot is empty. Otherwise it returns as an ordinary clip at the applicable return location (decision 55). It never replaces existing footage and never attaches to an unrelated note. Exact Undo restores the previous links and content. *Added 2026-10-29.*
54. **Mixed return of an edited parent and untouched children.** Allowed, with no refusal. The edited parent returns as a saved row. Its untouched children return independently in their note or clip form, keeping their order relative to each other, at the locations decision 55 gives (normally top level, right after the parent's row). *Added 2026-10-29; supersedes decision 6. Changed backend scope: not a claim that #342 supports it.*
55. **Return placement and fallback.** Returning by menu or button goes to the original location when it is still clear. Clear means the original section still exists and the item either had no parent or its parent is still in that section (as a note in Stash, or in the script under the settled partial-return rule). The item then goes after its nearest original sibling still present, else before the next one, else first under its note, else at the start of its section (decision 40). Otherwise (section gone, parent deleted, parent moved to another section, or no usable anchor) the material goes to the **very top of Stash, unsectioned**. No destination prompt and no invented section. A deliberate drop always uses its drop point. *Added 2026-10-29; replaces r3's "parent moved to another section" refusal and any destination-picker idea. New backend requirement, not claimed from #340.*
56. **Plain notes keep literal text, brackets included.** A note is plain text and saves any characters, including `[` and `]`. No note-level Make spoken, speech tags, quotation parsing or bracket parsing. A placed whole note is one nonspoken direction by default; the existing script and saved-row controls convert selected text explicitly (decision 3). Literal characters are preserved through placement, return, export and prompter. The r1 refusal to save a note containing a bracket is **obsolete**. If #341's conversion can't carry literal brackets inside a direction, that is a backend gap: notes are never refused and characters are never stripped. *Added 2026-10-29; closes the open bracket question.*
57. **Add clip at the top.** **Add clip** sits beside Add note and Add section, including in an empty Stash. It opens the Research picker (decision 13) and inserts the clip at the very top of Stash, unsectioned, with no note or section needed. The per-section + Clip stays. The empty-state text mentions it. *Added 2026-10-29.*
58. **Place in script… with Include items below.** When a note has items below it, the placement dialog shows an **Include items below** checkbox, on by default, with a live preview, for example "Places 1 row (direction + footage)" against "Places 4 rows". Attached footage always goes with its note. Unchecked, the note and its footage are placed and the items below stay in Stash, moved up a level, as with Alt/Option-drag. The checkbox is hidden when nothing is below. *Added 2026-10-29; keyboard parity for decision 18.*
59. **Saving groups.** Save, Cancel and Undo apply to the whole group change at once. Members keep their identities, content, author and date, comments and citations. Saving with one member left turns the group into an ordinary saved row. Saving with none removes the group, with a "Group removed" toast and Undo. Undo of creating a group restores the earlier state exactly, including placed notes and clips that could still return in their note or clip form. Placement stays flattened, with no remembered group (decision 44). *Added 2026-10-29; extends decisions 43 and 47.*
60. **Keyboard range mode.** After Select range, focus moves to the range. ↑/↓ moves the end of the range, kept within the section. Enter confirms and moves focus to the first selected row's ⋯. Escape cancels. Arrows are taken only in this mode, never while a text editor or the player has focus. The pointer range (decision 42) stays. Shift+arrows from ordinary row focus is a possible later addition; the script has no row-focus selection model today. *Added 2026-10-29; replaces the keyboard-range proof-gap note.*
61. **Screen-reader labels name content, not numbers.** Rows, ranges and groups are announced by content and selected count, for example "3 rows selected, from 'The tide has just turned' to 'faithfully'". No row numbers (Matthew's standing rule). *Added 2026-10-29.*

## Build commitments from the adversarial review (no objection raised)
- Keyboard placement: "Place in script…" with a gap picker, Esc to cancel, Undo afterwards.
- Typing in notes is shown working. Tokenization and paste handling are recorded as unproved (#341 and #342 cover only bounded commands and complete-row replacement).
- Indentation is capped visually at three levels. Saved-row summaries stay to one line at 1024.
- The sidebar shows Stash or Comments, one at a time. Comments r1's "Read-only here" Stash copy is replaced.
- Return actions state their result: "Returns as a note" or "Returns as a row (edited)".
- Comments on items that exist only in pending Sorting work refuse at acceptance (#342). Recorded for the Sorting pass.

## Open
- ~~Brackets typed in a note (conflict with decision 4).~~ **Closed 2026-10-29 by decision 56.** Notes keep literal brackets, and the r1–r3 save refusal is obsolete. The remaining backend question is recorded under proof gaps.

- **Reconnecting missing footage in Stash (deferred).** A Stash clip whose source is unavailable shows the reason, but Stash offers no way to reconnect it. Once placed, the script row has S03's recovery entry points (decision 15). A Stash-side path, such as Locate or replace in VERA Research from the clip's ⋯ or player, is likely outside this stage. Revisit in the integration pass or a Research pass. *Recorded 2026-10-29.*

## Artifact
- `S03 Unified Stash r1.dc.html` (2026-10-28): first Stash-first build on the Comments r1 light sidebar and the shared S03 read-only renderer.
- `S03 Unified Stash r2.dc.html` (2026-10-28): Producer notes on r1 (decisions 16–25).
- `S03 Unified Stash r3.dc.html` (2026-10-28, updated through 2026-10-29): Producer notes on r2 (decisions 25–32), then decisions 33–48. **r3 does not yet show decisions 49–61.** It still refuses notes containing brackets, shows the decision 6 refusal and the cross-section-parent refusal, draws attached footage as an indented child, and has no Add clip at the top, Include items below or keyboard range mode. Those changes go into the integration build.

## Recorded proof gaps
- Renaming or deleting Stash sections: #337 provides only create and move, so r1 offers neither.
- #340's `create_stash_clip` stores an existing VisualOnlyBlock payload. Whether a Research-logged clip reference is accepted as that payload is not shown in the handoff, and Research integration is simulated in Comments r1.
- Typing and paste handling in notes (see build commitments).
- **Groups.** #337/#340 have no group entity. A Stash group (decisions 42–47) is a new kind of Stash entry and needs backend support.
- ~~Keyboard range selection.~~ Decided in decision 60 (a UI behavior, not a backend gap).
- **Bounded backend follow-ups for decisions 49–61.** Filed 2026-10-29, all in Inbox and none delivered. None is proved by #337/#340/#341/#342, and no simulated label claims otherwise:
  - **#365, literal plain-note text (decision 56):** saving any characters in a note, and placing a note with literal brackets as one nonspoken direction without nesting or stripping. That needs structural direction marking or an escaping rule.
  - **#367, attached footage and clip snapshots (decisions 49–53):** a single footage link on a note; place and return with the note; detach; replace while keeping the old clip; reattach only to the original note's empty slot; blank note keeping its clip; exact Undo of links.
  - **#366, saved groups (decisions 42–47, 59):** the group entity; one Save/Cancel/Undo for the whole change; one and zero member rules; members keeping identity, comments and citations; Undo of creation restoring earlier placed records; adding and removing rows in the editor.
  - **#368, forgiving and mixed returns (decisions 54–55):** original-location rules with the very-top-of-Stash fallback, and an edited parent returning with its untouched children (replaces #342's refusal).
- Research clip and trim persistence in Stash (decision 39) and broader production Research and UI stay with their existing owners.
- ~~Stashing an accepted script row by drag.~~ Reclassified 2026-10-29: a drag that calls the same proved atomic Stash command as ⋯ › Stash is not a separate missing backend mechanism. Drag stays pointer-only, and ⋯ remains the keyboard path.

## Capability gate (2026-10-29)
No new functional depiction or integration of decisions 42–47 and 49–61 until the relevant ticket (#365–#368) delivers proof, or the Producer explicitly defers it. Drawing these as "pending" does not clear the gate. Work that is UI only (clip-player trim, Delete group, Include items below, and similar) claims no more than the current APIs exactly prove. #125 stays open.

**Scoped exception (2026-10-29, Matthew):** Matthew has authorized finishing #125's integrated design before #365–#368 are implemented. The exception covers only those four (literal plain-note text, saved row groups, attached footage and clip snapshots, forgiving and mixed returns), which he treats as ordinary application behavior to implement while he reviews the design. They are **not delivered**. Backend dispatch is separate. The gate above still applies to everything else. Canonical record: https://github.com/mbelinkie/vera-script-to-timeline/issues/125#issuecomment-6504144978

**Proof updates (2026-10-29):**
- #326 is merged and closed (PR352). Its bound synthetic adapter proves intact movement and first-interruption shortening: A-B-C-D-E → A-B-C-E-D ends after C. Not proved: production compilation of active spans, arbitrary curves, ducking, stereo routing, or crossing, overlap and Stash operations.
- #119 is merged and closed (PR358). It qualifies the Studio Wide/Tight picture-only transform, continuity, and unchanged dialogue and B-roll. Its synthetic tuples are not approved production looks. Free qualification stays with #355, the full presenter pipeline is separate, image auto-zoom is #325, and native motion #336 stays open.

## Integration checklist (planning only; #125 stays open)
**Sources to reuse:**
- `S03 Outline Sorting Comparison r14.dc.html` (Sorting and the dark drawer).
- `S03 Comments Placement Comparison r1.dc.html` on `Shared S03 Review Foundation - issue 137 r11.dc.html` (comments and sidebar).
- `S03 Unified Stash r3.dc.html` plus decisions 1–61 (Stash behavior).
- `Script to Timeline - issue 128 S03 v3 read-only renderer.dc.html` (row renderer, with its opt-in menuGap, playClip, onRowsChange and onPlayerClose hooks; no replacement renderer).
- The exact #119 and #326 handoffs.

**Can be shown working (exact merged subsets only):**
- #337: create sections; move items.
- #340: stash, create and place within its exact subset; the Research-clip payload stays unproved.
- #341: explicit direction and spoken conversion in rows; bracket-pair deletion; lone-bracket styling.
- #342: untouched and edited returns; partial return; refusals for comment limits, unclear placement and pending-only comments.

**Built on proved commands, claiming nothing beyond them:**
- Sidebar arrangement, buttons, divider, sliders and top-bar Undo.
- Return to notes on script rows.
- Row ⋯ placement, checked against the Transition, Add row and comment controls.
- Saved rows in the script renderer, with close and ask-to-save.
- Clip-player trim on script footage.
- Include items below.
- Content-based screen-reader labels.
- Both viewports and the empty states.

**Held behind the gate:** #365 literal note text; #366 groups, including range-to-group, Delete group, group Save/Undo and adding or removing rows; #367 attached-footage strip and its lifecycle; #368 forgiving and mixed returns.

**Stated gaps, not fixed:** typing and paste in notes; renaming or deleting sections; reconnecting missing footage from Stash (deferred); motion and framing; music beyond #326.

**Acceptance:** Sorting Accept/Discard alongside Stash; exports match the design; final source and handoff review against #62 and this doc.

## Change log
- 2026-10-28: Decisions 1–10 recorded. Decision 4 revised.
- 2026-10-28: Adversarial review. Decision 1 revised (count every entry). Decision 2 revised (muted italic directions, one Spoken tag per note). Review points 1, 2 and 4 pending clarification.
- 2026-10-28: Decision 3 revised (action follows selection; whole-note Make spoken). Decision 6 revised (no Undo in refusal). Decision 11 added (Return to notes button).
- 2026-10-28: Decision 2 revised (no speech/direction distinction in Stash). Decisions 3 and 4 limited to script and saved rows. Review build commitments recorded.
- 2026-10-28: Decisions 12–15 added (clips are logged Research clips; picker entry; placement as regular Footage rows; unavailable clips placeable). Open question closed.
- 2026-10-28: Built S03 Unified Stash r1. Recorded the note-bracket conflict with decision 4 and the section rename/delete gap.
- 2026-10-28: Producer review of r1. Decisions 16–25 added (gold active outline, resizable sidebar, drag in/out/within, floating two-column row editor, density, shade, collapsible sections, ⋯ kept). Built r2.
- 2026-10-28: Producer review of r2. Decision 25 revised (Delete first). Decisions 26–32 added (one-click delete, help line removed, no bullets, right-edge grip, saved row on white, no row-pairing refusal, comment-style attribution hidden on own items). Built r3.
- 2026-10-28: Decision 29 revised (row ⋯ doubles as the drag handle; separate grip removed). r3 updated.
- 2026-10-28: Decision 33 added (Stash follows Authoring size, plus its own A−/A+). r3 updated.
- 2026-10-28: Decision 33 revised (sliders replace A−/A+). Decisions 34–35 added (Undo in top bar; "Add note" / "Add section"). r3 updated.
- 2026-10-28: Decision 29 revised again (separate grip at row top right; ⋯ is menu only). Row-control conflicts deferred to integration.
- 2026-10-28: Decision 29 final: ⋯ moves to row top right and doubles as the drag handle; 24px strip reserved above first visual (renderer gains an opt-in menuGap prop). r3 updated.
- 2026-10-28: Decisions 36–38 added (simplified note menu; Add footage lands on the note's row; blank notes kept on blur). Decision 14 revised. r3 updated.
- 2026-10-28: Decision 38 revised (clicking away from a blank note removes it, like Escape).
- 2026-10-28: Decision 39 added (clicking a clip opens a player with full transcript). r3 updated.
- 2026-10-28: Decision 39 revised (Stash clips open the script's own clip player, all edit controls live). Renderer gains opt-in playClip / onRowsChange / onPlayerClose hooks. r3 updated.
- 2026-10-29: Decisions 40–41 added (returns keep original section and position; saved rows open in the script's row renderer). Row groups opened for brainstorming. r3 updated.
- 2026-10-29: Recorded reconnecting missing footage in Stash as a deferred open item.
- 2026-10-29: Decision 48 revised (closing with changes asks about saving).
- 2026-10-29: Decision 48 added (click the dimmed script or ✕ to close the row editor).
- 2026-10-29: Decision 42 revised (a selected range drags from anywhere inside it).
- 2026-10-29: Decisions 42–44 revised (ranges stay in one section; group shows first row, orange +N, last row; placed groups become ordinary rows, no Return group). Group backend and keyboard range recorded as gaps.
- 2026-10-29: Decision 42 revised (⋯ on every selected row with Stash group / Delete group / Select new range; drag any to stash; click outside clears).
- 2026-10-29: Decision 47 added (group editor can add and remove rows; production requirement, not simulated).
- 2026-10-29: Decisions 42–46 added (select range, groups in Stash, placed groups, group count, slider region excluded from Stash scaling). r3 updated.
- 2026-10-29: Decision 39: trim controls and source transcript switched on in the Stash Clip player.
- 2026-10-29: Matthew/Codex review batch adopted. Decisions 49–61 added (attached footage inside the note, one clip per note with Replace and Detach, blank text keeps footage, reattach rule, mixed return allowed, return fallback to the very top of Stash, literal note text, Add clip at the top, Include items below, group save rules, keyboard range mode, content-based screen-reader labels). Decision 6 superseded. Decisions 4, 9, 18, 36, 37, 38, 40, 42, 43 and 45 marked with revisions. Bracket open item closed. Backend follow-ups listed under proof gaps. No HTML changed.
- 2026-10-29: Follow-ups mapped to #365 (literal note text), #366 (saved groups), #367 (attached footage and clip snapshots) and #368 (forgiving and mixed returns), all Inbox. Capability gate recorded. Drag-to-stash reclassified as the same proved command. Integration checklist kept as planning. No HTML changed.
- 2026-10-29: Scoped exception recorded: #365–#368 behavior may be designed into the #125 integrated successor before delivery (not delivered). #326 and #119 recorded as merged, with their exact limits.


### 2026-10-29 · S03 Integrated r2.1
- Sorting rows that share both the visible opening and the visible ending get a compact "later “…”" chip. The chip shows the first 5 words where the row's text diverges from the other row. It is added to the accessible name, and the script text is not changed. No row numbers or invented titles.
- The Sorting exit control is always "← Back to script".
Change log: r2.1 adds the distinguishing chip, the A · Line dark surface in Sorting, the embedded atlas, and the Back to script label.

### 2026-10-30 · S03 Integrated r3 (integration build, no new decisions)
- Decisions 1–61 were integrated into `S03 Integrated Authoring r3.dc.html` as the shared authoring and Sorting Stash.
- Build interpretation: a group's editor places the member rows at the top of the script in the standard renderer, with the rest of the script inert (decisions 41 and 48).
- Change log: integrated r3 built. Authoring Undo history now survives Sorting; Accept adds one "Sorting" Undo step.

### 2026-10-30 · S03 Integrated r4 (repair build, settled decisions only)
- Build interpretation for decision 56/#365: a placed note becomes one direction by structure (a row-level flag), not by wrapping brackets, so literal brackets stay plain characters. Make spoken on such a row is refused while it contains literal brackets.
- Change log: r4 restores narration typing with Make spoken / Make stage direction, the saved-row and group editor in Sorting (+ Add row, decision 47), Include items below in Sorting, the #342 organization-versus-edits split for selective Accept including Stash organization, persistent empty sections, Quiet piano shown in authoring and preview, content-based saved-row labels, and corrected return order.

### 2026-10-30 · Checklist notes and note copies (#62 S03-STASH-020–026; integrated r5)
Authority: #62 S03-STASH-020–026 and the #125 integration record (comment 6513852065). This **supersedes** earlier wording on notes moving out of Stash and returning, including decisions 11, 14, 18, 37, 40, 53–55 and 58 where they conflict. Standalone clips and saved rows still move out.
62. **Notes are checklist items.** Every note has a small native checkbox in a fixed gutter where bullets used to be; new notes start unchecked. Footage (including the attached strip), saved rows, groups and sections have no checkbox. Space or click toggles the checkbox without expanding, selecting or dragging the note. A checked note turns gray, stays editable and keeps its outline position. Parent and child completion are independent, with no cascade.
63. **Hide completed.** A toggle beside the Stash text-size slider, off by default. Standalone footage, saved rows and unfinished descendants stay visible. A completed ancestor stays as muted context, with its attached footage, when it holds unfinished material. Counts include hidden material; nothing is lost or reordered.
64. **Placing a note copies it.** Placing or dragging a note creates an independent script row with fresh ids: one nonspoken direction holding the exact whole text, literal brackets included. The original note and its attached footage stay in Stash, checked, in place. A completed note can be placed again; it stays completed.
65. **Include items below with checklists.** It skips completed descendant notes (with their attached footage) but continues through them to unfinished deeper notes. Standalone clips and saved rows still move out. An explicitly chosen completed root is placeable. Notes left behind keep their hierarchy. The preview shows the actual row count. Parent-only and Option-drag remain.
66. **Per-insertion return.**
   - Each insertion remembers its source note and whether that insertion caused the check.
   - Returning one untouched, linked insertion removes the script copy and saves no extra row.
   - It unchecks the source only if that insertion caused the check and no later manual checkbox change overrides it. There is no reference counting.
   - Any authored edit to the copy, the source note or its attached footage breaks the link. Stashing such a copy then saves a complete row, with no checkbox change.
   - Moves, section changes and comments do not break links.
   - Stashing a group keeps every member as a row and ends its links, without changing checkboxes.
   - If the source is missing, the copy is kept as a saved row; the source is not recreated.
   - Undo restores content, completion and links exactly.
67. **Sorting.** Checkbox changes, note-copy placement and untouched returns count as edits. A placement gesture that contains note copies is one atomic edit, including any clips or rows it moved out. Pure footage and row moves keep the organization classification.
68. **Semantic directions versus literal brackets (#341/#365).**
   - Deleting either semantic delimiter of a bracketed direction by typing removes its partner, and the segment becomes spoken (Undo restores).
   - Brackets inside a note copy, or inside a row whose directions are marked per word, are literal characters, not delimiters.
   - Make spoken / Make stage direction on such rows changes the per-word direction marking and keeps every character. This replaces r4's refusal.
Backend status: #373 (note copies, completion and manual history, per-insertion return links) is designed, not delivered, alongside #365–368.
Change log: decisions 62–68 added; integrated r5 built.

### 2026-10-30 · Show Contributions (#62 S03-CONTRIB-001–011, Producer answers after CLI critique)
These are recorded here because this project keeps one Producer decision log.
- Pending Sorting edits or moves pause contribution highlights. The alert and pending indication stay available. Accept or Discard does not acknowledge.
- Show removed defaults to on. Off hides comparison evidence only.
- When the viewer overwrites another person's pending text, highlighting follows the latest editor. A catch-up summary is kept until explicit review, and old words are never resurrected.
Change log: the r7 A/B comparison was built for review; no option has been chosen.


### 2026-10-30 · Producer notes on r7.1 → integrated r8
Recorded here while Codex is out; this file is the single decision record.
**Show Contributions (Option B adopted; A kept only as reference)**
69. **Bar wording.** The bar's first line reads **See contributions**, followed by person chips. The chips use first names ("Dana", "Jonah") and **You**, so three people plus you fit on one line. More than four writers is treated as rare; extra chips wrap.
70. **Since last reviewed leaves you out.** In that range the chips show only other people. Other ranges include You.
71. **Overwritten contributions.** A person's count drops when the viewer's later edit replaces their unreviewed words. The catch-up line ("Your later edit replaced 1 unreviewed change by Jonah Reyes in “…”.") shows **only while that person is selected**, and it stays until Mark all reviewed succeeds. *Revised 2026-10-30: the trailing explanation was cut.*
72. **✕ in the corner.** The close button is pinned to the bar's top-right corner, whatever the number of chips.
73. **Reason highlight.** When the bar opened by itself because of unreviewed changes, the timeframe control shows its count in a **green pill**. Otherwise the count pill is neutral gray.
74. **Color roles.** Green means another person's contribution (the top-bar badge, chips, highlighted words, the reason pill). **Mark all reviewed is gold**, as the bar's primary action.
75. **Removed rows use the Reconciliation format.** A 3px red border, a red header strip reading "REMOVED · 1 ROW" with the person and time, the thin red X, and the row's two columns (narration, visual). The visual column shows a real typed visual (its kind and name, On Camera at least), never a bare "Visual". No explanatory "was after…" text. The fixture's removed row now sits mid-script, not at the bottom.
76. **Show removed default follows the range.** On for Since last reviewed, Since last visit and Past 24 hours; off for Past 7 days, All time and Custom. The person can still switch it. In All time, cycling through every person accounts for every sentence and visual, removed words included.
77. **No Contributions or Comments in Sorting.** Both top-bar buttons hide while Sorting is open, and the bar and highlights are not shown. Stash stays available; a sidebar showing Comments switches to Stash on entering Sorting.

**Top bar**
78. **Order:** Aa slider, Sort rows, Show Contributions, Show Stash, Comments, **Options** (far right). Sort rows is a neutral button like the others.
79. **Options button.** Present as an empty placeholder for project-wide settings; its contents are not yet decided.
80. **Back to script.** In Sorting, **← Back to script** replaces Sort rows in the top bar and is gold (the way out). The left-side Back button in the Sorting toolbar is removed.

**Stash**
81. **Nesting guides.** A thin vertical line (1px #a9b0b9) runs down from a parent with open children along the left edge of everything under it.
82. **Unnest by dragging left.** Dragging a nested item left by more than about 16px over its own place moves it out one level (same result as Shift+Tab while editing). Dragging it right the same way indents it under the item above (same as Tab), with the usual refusals: only notes hold items, three levels at most. Dropping below the last item in a branch with the pointer moved left places it at the ancestor level the pointer indicates, shown by the insertion line's indent. With Hide completed on, a completed parent disappears as soon as its last unfinished child leaves.
83. **Checked notes drag like unchecked ones** into the script (decision 64). A reported failure to get the gold line is under investigation in r8; the logic does not block completed notes.

Change log: decisions 69–83 added from Producer notes on r7.1; integrated r8 built (`S03 Integrated Authoring r8.dc.html`).
- 2026-10-30: Decision 82 extended: drag right over an item's own place indents it (fixes: an outdented clip couldn't be re-indented).
- 2026-10-30: Decision 71 text shortened; decision 75 removed rows show a typed visual; decision 49 refined: an attached footage strip aligns with the note's checkbox, and the shared background extends to include the checkbox.

### 2026-10-30 · Placed notes are ordinary text
84. **Notes enter the script as regular spoken text, not stage directions.** Placing or dragging a note makes a row whose words are plain narration, with the note's exact text. Literal brackets stay plain characters, not direction delimiters. The writer can still mark a direction with Make stage direction. Reason: most writers would otherwise just delete the brackets. **Supersedes** the settled "plain notes become nonspoken stage directions" rule and the direction parts of decisions 2, 56, 64 and 68 (note copies and literal brackets otherwise unchanged). Applies to dropping a note into an existing row too (in design).
Change log: decision 84 added; r8 places notes as spoken text (per-word marking, all spoken). The r4/r5 automated checks that expect a direction are now out of date.

### 2026-10-30 · Drag into rows, moving visuals, stashing selections (designed; build split across r9 and r10)
85. **Drag feedback.** On drag start, the source gets a gold outline and stays in place. A translucent copy follows the pointer.
86. **Drop into an existing row.** Besides making a new row, a Stash item can drop into a row. A note drops into the narration at a gold text cursor, which snaps between words and never lands inside a stage direction. It goes in as spoken text (decision 84). A note with footage brings the footage as a visual cued to the note's first word. A note can't drop on the visuals side. Clips and other visuals drop on the visuals side at a gold horizontal line between visuals.
87. **Dropped or moved visuals land unattached.** A visual dropped into a row (from Stash or dragged from another row) shows a gold **Attach to words** prompt and isn't built until attached. Click Attach to words, then select words in the narration.
88. **Moving a visual between rows** keeps its trim. Its out-point stays on its words; if those words aren't in the new row, it ends with the row.
89. **Stack follows cues.** When a visual's start words change, its card moves to its place in the stack by cue order, with a brief gold flash.
90. **Cut words to Stash.** Selected narration can be stashed; the words leave the script (Undo restores). Words with no visual cues inside become a note. Words carrying visual cues become a saved row with those visuals. A visual starting inside the selection goes with it; one starting before stays and ends where the cut was.
91. **Stash one visual.** A single visual can be stashed from its row, which moves it out (Undo restores). It arrives as a clip with its trim. Allowed for Footage, Still Image, Web Capture, Graphic and Placeholder / Need to Find, not On Camera.
92. **Build order.** r9: drag feedback (85), the Add visual → Footage defect, stack order (89). Next pass: 86–88, 90–91.
Change log: decisions 85–92 added.

### 2026-10-30 · + Visual button
93. **+ Visual is one dropdown of visual types.** A single button opens a type menu. It starts with Footage, then On Camera, then Still Image, Web Capture, Graphic, Onscreen Placeholder, Need to Find and Visual Undefined. The old "Add next visual (sequential)" and "Add cutaway" choices are gone. Picking a type adds it at the next cue; Footage then opens the Research clip picker right away. Built in r10.
Change log: decision 93 added (Producer answer); refined the same day, when the Producer asked for a type list starting with Footage, then On Camera. r9 keeps the split button.

### 2026-10-30 · r10 build interpretations (decisions 86–88, 90–91)
- 86: the gold text cursor appears only while dragging a note over a row's narration. Over the visuals column, or within 8px of a row's top or bottom edge, the note makes a new row as before. The placed note is a copy, and the Stash note is checked (decision 62).
- 87: an unattached visual has a dashed gold outline and a gold "Attach to words" button. After clicking it, the next word selection in that row attaches the visual; Esc cancels. Without a remembered end, a multi-word selection sets the end.
- 88: dragging a card from one row to another keeps its trim. It remembers the two words where its range ended and looks for them when attached.
- 90: the selected-words toolbar gains "Stash words". New Stash entries go to the top of Stash.
- 91: each eligible card has a hover "Stash" button. A card can also be dragged onto Stash. Stashed Still Image, Web Capture, Graphic, Placeholder and Need to Find keep their full visual and show their type in place of a duration. They can't open in the clip player.
Change log: r10 built (`S03 Integrated Authoring r10.dc.html`).

### 2026-10-30 · Add a visual on selected words
94. **Selecting words, then Add visual, asks for the type right away** (the same list as + Visual: Footage first, then On Camera). It creates the visual starting on the first selected word. Footage then opens the Research clip picker.
   - Range brackets in a selection don't count. Selecting across "2⟧⟦3" is a normal word selection.
   - A visual whose start falls inside the selection moves its start to the word after the selection. If that word is taken or the row ends there, it becomes unattached (Attach to words). Any other starts inside the selection also become unattached.
   - A visual that starts before the selection ends where the selection begins. If the selection sits inside one visual's range with words after it, the new visual is a cutaway that returns to that visual after the selection. On Camera ends on the last selected word instead.
   - The sequential/cutaway dialog no longer opens from a selection.
   - + Visual still adds after the last visual (Producer: adding to the end is useful).
Change log: decision 94 added; built in r10.

95. **Word selections snap to whole words.** When a selection in narration ends, it widens to the start of its first word and the end of its last word. Range brackets are skipped.
Change log: decision 95 added; built in r10.

### 2026-10-30 · Producer notes on r10 (backlog: `Implementation backlog.md`)
96. **+ Visual only on rows with no narration.** Once a row has text, visuals are added by selecting words (decision 94). *Revises decision 93 and the last bullet of 94.*
97. **Split and join rows from a selection.** If a selection includes a row's first or last word, the right-click menu offers Join to previous row (selection includes the start), Join to next row (includes the end) and Split into new row. A whole-row selection offers both joins. A mid-row selection gets none of these. Join moves only the selected words. A visual whose start word is in the selection travels with it, and its end is clipped to the selection. A visual that starts before the selection stays and ends at the split. A visual never appears in two rows. Split puts the new row before the original if the selection includes the start, after it if it includes the end, and is hidden for a whole-row selection. Join is disabled across a section break. A stage direction moves only if its start is in the selection.
98. **Footage quick search.** Adding Footage opens a search box that filters on title, transcript, logger and date logged. By default it shows only unused clips. Research logs from YouTube supply only these fields.
   The quick-search box has a **Show used** toggle.
99. **Show Footage sidepanel.** A third sidebar button joins Show Stash and Comments. It lists all project footage with a detailed search and its own thumbnail-size slider (like Stash). Clicking a used clip scrolls to its placement. A clip used several times shows small arrows to step through its placements (1/3, 2/3, 3/3). A clip remembers its latest manual trim, even after that instance is changed or deleted, and every new placement uses it; other placed instances keep their own trims. Clips drag out of the panel into any row and land unattached (decision 87). Only one sidebar is open at a time. Build note: a brief transition between panels would be nice, but it's out of scope for the preview.
100. **Visual ⋯ menu.** Trim (opens the player with in/out handles), Change type, Stash, Comment, Delete. Replaces the "comment on this visual" button. Deleting a row's last visual leaves a Visual Undefined card, as on a fresh row.
101. **No between-row control strips.** "Comment on gap" is removed. Hovering a row divider shows a two-sided **Add row | Add transition** button on the line, with no reserved space. Transitions are allowed at every divider, including before the first row (fade up from black) and between sections. The row ⋯ menu shows only on row hover, at the top-right, partly overlapping the first card, so the first visual card moves back up near the top of the column.
102. **Thumbnail size slider in the top bar** (0–100%; 0 shows words only, with images previewed on hover), as in `Script to Timeline - S03 Rows Read-only v2`. Settings contents stay in flux until the design settles.
103. **Comments in Sorting.** *Revises decision 77 for Comments.* Comments show in the sidebar while Sorting is open. Clicking a comment expands its row and scrolls it into view; clicking another collapses the first.
104. **Sentence case for all buttons and labels**, including "stash" (not capitalized).
105. **Selections snap live.** *Extends decision 95.* While you drag, the highlight grows a whole word at a time. Punctuation is selected with the word before it.
106. **Section breaks.** Sections are organizational only: markers that appear in Resolve and need clean cuts. **Add section** sits in a small ▾ on the divider's Add row half. Breaks go only between rows. A new section opens with an inline title field. The section header's ⋯ offers Rename and Delete break; deleting merges the section into the previous one.
107. **Design leads, backend follows.** *Supersedes the capability gate (2026-10-29) and the proof-gap limits.* Build the intended product behavior, record each decision here, then write backend tickets to match.
108. **Show contributions: option B**, as currently built (closes the r7 A/B).
109. **Stash sections can be renamed and deleted** (previously blocked by the #337 proof gap). Deleting a section moves its items to unsorted at the top of Stash, above all sections, keeping their order and nesting. They don't merge into a neighbouring section, which is likely about something else. Backend ticket to follow.
110. **Thumbnail size 0% is a primary writing mode.** Hover previews of visuals must work reliably at 0%.
111. **Deferred features:** spell check; word count and estimated length; comment-only access to a document.
Change log: 2026-10-30, added `S03 spec.md` (current-state spec, unscoped-functionality list, test checklist); update it each notes round. File renamed from `Stash design decisions.md` to `S03 design decisions.md` (it now covers all of S03 authoring). Decisions 96–111 added (Producer notes on r10). Not built yet.

### 2026-10-31 · Drag ghost position
112. **The drag ghost trails the pointer.** *Refines decision 85.* The pointer sits at the ghost's top-left corner, and the ghost is offset about 12px below and to the right, so the gold text cursor and insertion line are never covered. Applies to every drag.
Change log: decision 112 added (Producer note on r10). Not built yet.

113. **Attach to words makes room like Add visual.** *Extends decisions 87 and 94.* Attaching an unattached visual to a selection applies decision 94's rules. The new visual takes the full selected range, and the neighbouring visuals' ranges change around it: one starting before the selection ends where it begins, and one starting inside it moves its start to the word after the selection (or becomes unattached if that word is taken or the row ends). This also covers selections that cross the boundary between two visuals. r10 fails here (Producer test, 2026-10-31).
Change log: decision 113 added; r10 bug logged.

114. **Return and Tab in narration.** Return inserts a paragraph break within the row; a row can hold several paragraphs. Tab splits the row at the cursor: the text after the cursor moves to a new row directly below, and the cursor goes to the start of that row. At the end of a row this makes an empty row. Visuals follow decision 97: one starting after the cursor moves to the new row, and one running across the cursor stays and ends at the split. Undo reverses it; moved cards flash gold (decision 89). Esc leaves the text box so keyboard users can move focus on. Tab in Stash notes still indents (decision 9).
Change log: decision 114 added; revised the same day from "Tab makes an empty row, no text moves" to split at the cursor (Producer). Not built yet.

### 2026-10-31 · Keyboard, paste and selection menu
115. **Backspace at the start of a row joins it to the row above.** The opposite of Tab (decision 114). The joined text starts a new paragraph inside the row above. Visuals follow decision 97. Blocked across a section break.
116. **Footage quick search is seeded with the selection** (trial). When Footage is added on selected words, clips whose transcripts match those words rank first. *Extends decision 98.*
117. **Add footage shortcut.** ⌘⇧F (Ctrl+Shift+F) on a selection opens footage quick search. The shortcut is shown in the menu. Low priority; the Producer prefers the mouse.
118. **Coverage cue at 0% thumbnails** (trial). A thin margin line beside the narration shows each visual's range, with Visual Undefined in a distinct colour. Built as an example for review before it's adopted.
119. **Paste.** A blank line in pasted text starts a new row; a single line break becomes a paragraph break inside the row. Rich-text paste (Google Docs) is still open.
120. **Selection menu order.** Create (Add visual, Add comment), then restructure (Split into new row, Join to previous row, Join to next row), then move out (Stash words), separated by dividers. Items that don't apply are hidden.
Change log: decisions 115–120 added (Producer, 2026-10-31). Not built yet.

### 2026-11-02 · Rich-text paste deferred
121. **Pasting from Google Docs (rich text) is deferred.** Plain-text paste follows decision 119. Doc paragraphs, two-column narration/visuals tables and bracketed text are not interpreted for now. *Closes the open part of decision 119.*
Change log: decision 121 added (Producer, 2026-11-02). r11 build started from the backlog.

### 2026-11-02 · r11 build, part 1 (build interpretations)
- 96: + Visual shows only on rows with no narration.
- 97/120: the selection bar reads Add visual, Add comment | Split into new row, Join to previous row, Join to next row | Stash words. Join across a section break shows as disabled and explains why. When a selection's edge falls inside a stage direction, the direction stays with its first word and the selection shrinks or grows to match. A row emptied by a join is removed. Any row left without a visual on its first word gets a Visual Undefined card.
- 100: the visual ⋯ (top right of each card, on hover) offers Trim (only for visuals with media), Change type…, Stash, Comment, Delete. The card's Stash pill and "Comment on this visual" button are gone.
- 101: dividers take no space. Hovering a divider shows a split pill centred on the column line: Add row (with ▾ › Add section) on the narration side, Add transition on the visuals side. A divider that has a transition keeps showing it. The first row has its own divider above it ("Add transition · from black"), and the last row's divider offers "to black". The row ⋯ straddles the row's top edge at the right, so it sits just above the first card.
- 102/110: the thumbnail slider sits in the top bar after Aa, 0–100% in steps of 5, and is remembered in this browser. At 0% hovering a visual with a picture shows its preview.
- 106: a new section opens an inline title field. Enter saves; Escape or an empty title removes the new break. Add section is hidden where the next row already starts a section, and after the last row. The first section has no Delete break.
- 112: every Stash drag ghost now trails 12px below and right of the pointer.
- 113: Attach to words now uses the same rule as Add visual on a selection.
- 114/115: Tab splits at the cursor (mid-word splits before that word); Tab at the end makes an empty row; Backspace at a row's start joins it to the row above; Esc leaves the text box. **Return still adds a row** until paragraph breaks are stored (part 2).
- Bug fixes: Wide/Tight buttons now work; they were drawn as labels with no click handler. The stray mini On Camera card came from a typed-into blank row whose Visual Undefined had no start word; that card now covers the row from its first word.
- Not in part 1: Footage quick search and sidepanel (98, 99, 116, 117), comments in Sorting (103), live word snapping (105), paragraph breaks and paste (114 Return, 119), coverage cue (118), Stash section rename and delete (109).
Change log: r11 part 1 built (`S03 Integrated Authoring r11.dc.html`).

### 2026-11-02 · Producer notes on r11 part 1
122. **Row ⋯ sits completely inside its row.** *Refines decision 101.* It must not straddle the row's top edge, so it reads as belonging to that row. It stays at the top right, partly over the first card.
123. **The visual ⋯ menu has no explanatory text.** Items show their labels only (Trim, Change type…, Stash, Comment, Delete).
124. **Tab then Backspace restores the split.** *Extends decisions 114 and 115.* If Backspace joins a row straight back after a Tab split, with nothing edited in between, any visual that the split clipped gets its original range back, as if the split never happened.
Change log: decisions 122–124 added (Producer, 2026-11-02). Queued for the next build round.

### 2026-11-02 · r11 build, part 2 (build interpretations)
Built in `S03 Integrated Authoring r12.dc.html` (copy of r11; new code in the r12* methods and r12Vals(), which runs after r11Vals()).
- 98/116/117: choosing Footage (from Add visual on a selection, Change type, or ⌘⇧F / Ctrl+Shift+F on a selection) opens an **Add footage** quick search in place of the old clip list. Cursor starts in the box; Enter picks the top result, ↑/↓ move, Esc closes. Unused clips only; **Show used** adds used ones with a Used tag. With a selection, clips whose transcripts share words with it (4+ letters, common words ignored) rank first and list the matching words. "Open in VERA Research" stays at the bottom. The Footage menu item shows the shortcut.
- 99: **Show footage** sits before Show stash in the top bar. The panel searches the same fields, adds a logger filter and All / Unused / Used, and has its own thumbnail slider (0% titles only, 60%+ stacked). Clicking a used clip scrolls to it; ‹ 1/3 › steps through placements. Dragging a clip into a row lands it unattached with Attach to words. The remembered trim is the latest change made while the player's trim controls are open; it lasts for this session in the prototype. Hidden in Sorting.
- 103: Comments stay available in Sorting. Clicking a comment expands its row (opening its Sorting section if collapsed) and scrolls to it; the previously expanded row collapses.
- 105: while dragging, the highlight snaps to whole words, and a punctuation-only token goes with the word before it. The same rule applies on release. Live highlight uses the browser's CSS highlight support; without it, snapping happens on release only.
- 109: each Stash section header has a ⋯ with Rename (inline field; Enter saves, Esc cancels, blur saves) and Delete section. Delete moves its items, in order and with their children, to the top of Stash above all sections; Undo restores.
- 114: Return adds a paragraph break at the cursor (mid-word breaks before that word). Return at a row's very start shows a hint to use Tab. Backspace at the start of a paragraph removes the break. Paragraphs are stored on the row as word positions and travel with split and join; Backspace-join (D115) inserts the paragraph break it describes.
- 118 trial: at thumbnails 0–2%, each visual range gets a thin margin line left of the narration. Lines alternate two blues so neighbours read apart, cutaways are lilac and inset, Visual Undefined is dashed orange-red. Hover shows the visual's name. Overlays are not drawn.
- 119: plain-text paste only (D121). A blank line starts a new row (new rows inherit the visuals that start inside them, per D97); a single line break becomes a paragraph. Pasting into a Stash saved-row editor never creates rows. One Undo reverses the paste.
- 122: row ⋯ moved inside the row, 6px from the top right, over the first card; that card's own ⋯ steps left so they don't overlap.
- 123: no helper text in the visual ⋯ menu or its Change type submenu.
- 124: Backspace straight after a Tab split, with nothing changed in between, restores the row exactly as before the split, including any visual's clipped range. The restored visual flashes gold and a toast says so. Any edit in between falls back to the normal join (D115).
Change log: r11 part 2 built (`S03 Integrated Authoring r12.dc.html`). Not yet tested by the Producer.

### 2026-11-13 · Footage refinements (Producer direction) → integrated r13
Built in `S03 Integrated Authoring r13.dc.html` (copy of r12; new code in the r13* methods and r13Vals(), plus targeted edits to r12Vals, addTyped/addAtSel, slotBy/setMedia and the visual card's click and key handlers).
125. **Clicking footage previews it; usage controls navigate.** *Supersedes D99's "clicking a used clip scrolls to it" and, for Footage cards, the click-to-expand card detail.* Clicking a clip's title, thumbnail or body opens the clip player in the Footage panel, Stash and script. In the script it plays that use's own in/out. In the panel it plays the remembered trim (D99), else the Research logged range. Opening, playing and closing change nothing. Drag still places. Nested controls (usage pill, arrows, labels, Show full transcript, Place in script…) do only their own action. Unavailable or removed clips keep the old expand-for-recovery behaviour.
126. **Usage pill.** "Used once" / "Used N times" is a larger clickable pill. It scrolls to that visual in the right column and flashes it gold; the panel, its search and filters stay. Several uses keep ‹ 1/N › stepping (D99); the pill goes to the selected use, the arrows select, go to and flash the others.
127. **Clip labels.** Named, colour-coded labels show on each panel clip, with × to remove and a compact + Label (pick an existing project label or create one). Labels belong to the source clip, not to one script use, and are meant to be the same set Research uses. A single-label filter sits beside the logger filter.
128. **Sort.** One dropdown: Newest logged first (default), Oldest logged first, Title A–Z. Ties break by title, then key (Title A–Z ties break newest first). Filters keep working; the choice is remembered in this browser.
129. **Full transcripts by default; Options › Short transcripts.** *Supersedes r12's truncated panel excerpts.* The panel shows each clip's complete logged-clip transcript (never trimmed to a use, never the whole YouTube video). Options gains one checkbox, Short transcripts, off by default and remembered per browser. When on, each clip shows the compact excerpt (around the search match where possible) ending in Show full transcript, which expands that clip only; Show less collapses it. The global checkbox is unaffected.
130. **Search wording and fields.** *Supersedes D98/D99 field list.* Footage search reads "Search title or transcript" and matches only those fields, in the panel and in quick search. Logger has its dropdown, dates are handled by Sort, labels by their filter. The selection-seeded ranking trial (D116) is unchanged. Search always uses the full transcript.
131. **The footage picker commits nothing until a clip is chosen.** *Corrects r12.* Add visual › Footage (on a selection or from + Visual) and ⌘⇧F open quick search without creating a visual or moving coverage. Escape, outside click or dismissal leave the document and Undo as they were. Choosing a clip is one Undo step ("Add footage …").
132. **Place in script… from the Footage panel.** A non-drag route reuses the Stash gap chooser. Placing at a gap makes a Footage row with no narration (the Stash clip rule); dragging into a row still lands unattached with Attach to words (D87).
133. **Keyboard and empty states.** The card's key handler ignores keys from nested controls. The Usage filter is a proper radio group (one tab stop, arrow keys, Home/End). "Research: none logged" empties the panel and quick search, shows "No footage is logged for this project yet" with Open in VERA Research, and the top-bar count reads 0. No results offers Clear search and filters.
134. **D110 kept.** At 0% thumbnails, pointer hover and keyboard focus still preview a visual's image without a click and without changing trims; clicking a Footage card now opens the player (D125).
Build interpretations and limits:
- Research's current design calls the clip-level set *Topics* (round chips, gold when set) and defines no per-topic colours. This build uses the word "label" as directed and fixture colours (shared oklch lightness/chroma, varied hue). Naming and colours need confirming with the Research owner.
- Labels are fixture data held in this session; nothing is written to Research and there is no Undo for label changes (they are clip metadata, not script edits). Production needs Research to own the clip-label set and an API for Authoring to read, add and remove clip labels.
- A trim changed in a panel preview's trim controls becomes the clip's remembered trim (D99). Session only.
- Quick search keeps compact match excerpts; the Short transcripts preference applies to the Footage panel.
- Choosing a clip on a selection that covered a whole On Camera range follows D113: the On Camera visual is displaced and shows Attach to words. Undo restores it.
- Harness: "Footage: 3 uses" places "Harbor mouth, tide running out" three times with trims 1.0–4.0, 3.0–7.5 and 5.0–9.0 (fixture only; it also sets the remembered trim).
Change log: decisions 125–134 added (Producer, 2026-11-13); integrated r13 built. Partly tested in the UI (see `S03 spec.md` test checklist).

### 2026-11-14 · Writing integrity and visual attachment → integrated r14
Built in `S03 Integrated Authoring r14.dc.html` (copy of r13; new code in r14Map, r14Init and r14Vals, plus targeted edits to reanchor, bare/findWord, r11Cut, r11ProseKey, r12Paste, r12SplitMany and pilotAddRow).
135. **Erasing narration keeps the row and its visuals.** Deleting all of a row's words commits empty narration ("Cleared narration", one Undo step). The row and every visual stay with their source, trims and settings. Word positions (cues, ends, returns, highlights, music start/out) and paragraph and direction flags are cleared, so nothing points at missing words. Cutaways become ordinary visuals because they have no return word. The empty cell is the existing blank-row cell. Delete row stays a separate action in the row menu.
136. **Keyboard hint in the status area.** While script narration has focus, the bottom status area adds "Return: paragraph · Tab: split row · Esc: leave text". It goes when narration loses focus and doesn't appear in Sorting. Other status content stays.
Build corrections and interpretations:
- 137 (R52): Add row from the row divider and Tab at the end of a row are now one authoring Undo step each, with redo, restoring row order, section membership and transitions. Add row above the first row already was. In Sorting, Add row keeps Sorting's pending-change model and adds nothing to authoring Undo.
- 138 (R06/R09): splitting off a suffix keeps a paragraph break after the final word, and it travels through join and Undo. A multi-row paste merges only with the narration edit that this paste created, so pasting identical words with a new row structure no longer swallows an earlier edit. A timing race that sometimes stopped a paste from creating its rows on a slow page is fixed (the row split waits for the pasted words to be committed).
- 139 (R05/R07/R08): after an edit, a visual's cue, end, return and highlight follow the edit position. Words before and after the edited span keep their positions. An edited span that swaps the same number of words keeps positions. Otherwise the anchor's 3-word phrase is looked for inside the edited span, nearest its old place. If the cue words are gone, the visual is left without a start word (the existing missing-cue state) instead of jumping to an earlier copy. Word matching is Unicode-aware, so accented and non-Latin words are compared, not collapsed. Structural keys (Return, Tab, Backspace, Escape) are ignored while an input method is composing.
- 140: Escape leaves narration and moves focus to the first visual card in the same row, so Tab continues through that row's controls. D124's Tab → Backspace restoration is unchanged; panel switching and the 1024/1280 viewport toggle don't invalidate it.
- Nested visual-card controls: the r13 fix (card ignores keys from nested controls) is kept; no further change.
Change log: decisions 135–136 added (Matthew, 2026-11-14); build notes 137–140 recorded; integrated r14 built and UI-checked (results in `S03 spec.md`).

### 2026-11-14 · Stash refinements → integrated r15
Built in `S03 Integrated Authoring r15.dc.html` (copy of r14; new code in r15Vals, r15PlanNote and r15T, plus targeted edits to stDropWords, stPlaceDo, the Place in script dialog, the Stash player row and the Escape handler).
141. **A note dropped into a paragraph becomes ordinary spoken words.** It inserts at the gold text cursor with literal brackets kept as plain characters. The source note is checked and stays in Stash. Attached footage is copied as a visual starting on the first inserted word; the source attachment and its settings stay on the note. The inserted passage has no return link. Later editing or removing those words doesn't change the note's checkbox. Undo and redo treat the words, the copied footage, shifted anchors and the previous checkbox state as one action. *Extends D64, D84, D86.*
142. **Only the dragged note (and its footage) enters the paragraph.** Its nested notes, clips and rows stay where they are, with their own completion. Place in script › Include items below still places a branch as rows (D65 unchanged).
Build interpretations and corrections:
- Inline drop: paragraph breaks after the cursor and music start/out positions now shift with the inserted words (they didn't in r14). In a row with no per-word direction flags, a note containing brackets is inserted with per-word spoken flags so its brackets stay literal; existing bracket directions in that row keep their flags.
- Top-level and nested Stash clips sit in the checkbox lane of their level (no blank checkbox space); attached-footage strips and nesting are unchanged.
- Place in script preview says "spoken text + footage" (D84), and says what's copied versus moved ("Notes are copied and stay in Stash, checked; 1 clip or saved row moves out of Stash"). The toast after placing says the same. The return action in a row is "Return to stash"; its tooltip still explains it removes the copy.
- Place in script has a "Filter destinations" box. It matches row and section text, keeps section headings for matches, reselects the first visible destination if the chosen one is filtered out, shows "No destinations match" (Place disabled), and Escape still cancels. Escape and Cancel return focus to the item's ⋯ (or the panel's Place in script… for footage).
- Stash player, unavailable source: Play is hidden and the player shows the reason, the logged range and that the clip can still be placed (the script row has recovery options). Reconnect stays deferred to Research.
- The built-in r4 check that expected "(direction + footage)" now expects "(spoken text + footage)".
Change log: decisions 141–142 added (Matthew, 2026-11-14); integrated r15 built and UI-checked (results in `S03 spec.md`).

### 2026-11-14 · Comments, Contributions and workspace → integrated r16 (no new product decisions)
Built in `S03 Integrated Authoring r16.dc.html` (copy of r15; new code in r16Vals, plus targeted edits to the top bar template and cmScrub).
- Comments in Sorting (D103) and saved context for a replaced shot work as decided; Undo of the replacement reattaches the comment. No change.
- Mark all reviewed (D69–D74, as built): it is offered only for "Since last reviewed". It acknowledges every pending change by others up to the review boundary, whichever person chip is selected and whether Show removed is on. The boundary is frozen when the bar first opens with pending changes, so a later arrival stays pending ("Marked reviewed through … Anything later stays pending."). A simulated failed save marks nothing and says so. Accepting or discarding Sorting changes acknowledges nothing. No change.
- D71 catch-up line, as built: with a contributor selected, it says "Your later edit replaced 1 unreviewed change by Jonah Reyes in …". Jonah's chip count (3) includes the replaced change. After Mark all reviewed, the chips and the line are gone. No change.
- Top bar: the title and size controls no longer overlap at 1024 × 768. The bar wraps onto two rows at that size: row 1 has the title, Undo and the view sliders; row 2 has the panel buttons and Options, right-aligned. At 1280 × 800 everything fits on one row with slightly tighter gaps. *Restores D34:* a persistent ↶ Undo with a ▾ recent-actions menu sits in the top bar in authoring (hidden in Sorting, which keeps its own Undo). Its label names the action that Cmd/Ctrl+Z will undo, and it reads "Nothing to undo in this session" when only earlier-session entries remain (those can't be undone, by keyboard or button).
- Accessible names: a visual card's or range marker's "Row N" was being turned into a row name by position, so after an insertion or a move it named the row above. Names in a row's own labels now come from that row's identity (D61 naming style unchanged).
- Compact fixture: with the Contributions bar, a toast and the clip player open at 1024 × 768 there was no overlap (toast ends 8px above the bar), so no spacing change was made.
Questions for Matthew:
- Should Mark all reviewed stay global (all people, removed items included, up to the boundary) or acknowledge only what's shown when a person is selected or removed items are hidden?
- Who may Resolve, Reopen and Reattach a comment? The prototype lets anyone.
- Adopt the 0% coverage cue (D118 trial)?
- Is the two-row top bar at 1024 × 768 acceptable, or should some labels shorten instead?
Change log: r16 built and UI-checked (results in `S03 spec.md`).

### 2026-11-14 · Final verification → integrated r17
Built in `S03 Integrated Authoring r17.dc.html` (copy of r16; new code in r17Tile and r17Vals, plus small edits to the card's hover/focus handlers, the 0% preview, the footage pick and the Stash placement toast). r16 is unchanged.
- **0% thumbnail previews (D110).** Cause found: in the sample, Still Image and Footage cards such as "Harbor caretaker" have no image of their own; their thumbnails exist only as tiles in the shared sample thumbnail sheet (shown in Sorting and in the Footage panel). The preview required an image, so it showed nothing. Fix: at 0%, hover and keyboard focus now preview a visual using its own image or, failing that, its existing sample tile. Visuals marked "Image file needed" and removed visuals still don't preview. The coverage cue is untouched. Card thumbnails above 0% keep their current placeholder styling (no card styling change).
- **Unavailable footage in the script (D15).** Cause found: a placed clip whose source was removed showed its reason but offered no recovery. Its card now offers **Replace clip…** (the existing footage search; choosing a clip clears the unavailable state and is one Undo step) and **Open in VERA Research** (a route only in this prototype).
- **0% after reload.** A second cause, found by the review: when 0% was the saved thumbnail size, the restored value didn't reach the card handlers (they still saw the old size), so neither hover nor focus previewed until the slider was moved. The saved size is now restored through the same refresh as the slider. On Camera cards don't preview at 0% (unchanged; their thumbnail is the presenter frame, not a visual image).
- **0% focus while scrolling.** A third cause, also found by review: focusing an offscreen card (as Tab does) scrolls it into view, and two scroll handlers closed every preview. A keyboard-focus preview now stays open while its card keeps focus, and moves with the card. A hover preview still closes on scroll. Moving focus straight from one card to the next (fast Tab or key repeat) let the previous card's delayed blur close the new card's preview; each card's blur now closes only its own preview.
- Placing a Stash group: the toast now reads "Placed 2 rows from the group" (it repeated the group's name before).
- Verified unchanged: row ⋯ › Delete row asks first, deletes, and one Undo restores the row in place with its text; stashing a two-row range as a group and placing the group back (as ordinary rows, D44) each take one Undo step, with every visual intact.
Change log: r17 built; outcomes in `S03 spec.md`.

### 2026-11-14 · Chrome review of r17 → integrated r18
Built in `S03 Integrated Authoring r18.dc.html` (copy of r17; edits to undoThrough, redo and the visual card's accessible name). r17 is unchanged.
- **Stale removal toast.** Cause: deleting or stashing a row from the row menu shows a toast with its own Undo; reversing the deletion from the toolbar or with Cmd/Ctrl+Z restored the row but left that toast and its Undo armed, so it could act on an unrelated older step. Now any toolbar or keyboard Undo/redo replaces the toast with "Undid …" / "Redid …" (no Undo button) and reattaches the removed row's comments as the toast's Undo would. The toast's own Undo is unchanged.
- **Accessible name for unavailable footage.** A placed Footage card whose source is unavailable now ends its name with the source status shown on the card (for example "Source unavailable · the video was removed from this project’s media"), not "Image file needed on this computer". Still Images with a missing file keep "Image file needed on this computer". Recovery actions are unchanged.
- **Independent Chrome observations (Matthew's review of r17, native input):** with 0% already saved, native Tab and real pointer movement revealed thumbnails on the Recipe card (Still Image) and Harbor caretaker (Footage); Tab away or moving the pointer beyond the card dismissed them. Row ⋯ › Delete row and one toolbar Undo restored the short row and its On Camera visual. The Night ferry clip placed with its recovery choices, and Undo returned it to Stash. Placing the Cold open group with Include items below copied the two unfinished notes, skipped the already-completed note, moved Gulls over the pier and kept the horn attachment; one Undo restored the source hierarchy, the attachment and the original completion marks. These close the earlier pointer, hover and placement verification gaps.
Change log: r18 built; outcomes in `S03 spec.md`.

### 2026-11-14 · Producer follow-up pass 1 (superseded by the completed entry below) → integrated r19
`S03 Integrated Authoring r19.dc.html` (copy of r18; r18 unchanged). Matthew approved the scope, chose the exact-match swap option and an editable 4.0 s default hold. Work stopped partway at the usage limit.
- Built: "Add audio bed starting in this row" is back in the integrated row ⋯ menu for rows with narration (Stash · Add audio bed · Delete row · Select range). It opens the existing audio picker (four sample library cues and Log a local audio file…). Picking a cue adds the bed as one Undo entry. Escape closes the picker with no Undo entry, and focus returns to the row ⋯.
- Built, not yet verified: Source trim and Fade out sliders restored in the audio bed panel. A slider gesture is one Undo entry (inputs within 1.5 s merge), and Undo restores the previous trim/fade.
- Not started: brackets/Reselect range/Swap ranges, no-dialogue reorder and 4.0 s hold/Match audio duration, separate row/visual ⋯ strip and removing the D118 coverage cue.
- Interpretation: the integrated build has no separate audio "draft" editor (its template was removed before r12); cancelling a draft is taken as cancelling the picker before a cue is chosen.

### 2026-11-14 · Producer follow-up pass 1 complete → integrated r19
Built in `S03 Integrated Authoring r19.dc.html` (r18 unchanged). Matthew approved the scope, the exact-match swap option and an editable default hold.
143. **Audio bed authoring restored in the integrated row ⋯ menu.** For rows with narration, the menu reads Stash · Add audio bed starting in this row · Delete row · Select range. The existing picker, cue panel and bed rendering are reused. The panel gets back Source trim and Fade out sliders, plus Remove audio bed. Each slider gesture is one Undo entry (inputs within 1.5 s merge). Adding a cue, adjusting it and removing it are each one Undo entry, and the toolbar label names them. Cancelling the picker before choosing a cue leaves no bed and no Undo entry. No separate draft editor. Prototype cue settings only; no import of arbitrary audio and no Resolve output.
144. **Larger footage bracket hit areas.** Each ⟦n / n⟧ word bracket gets 3 px of horizontal padding and an invisible hit area 6 px above and below. It adds no horizontal overlap, so neighbouring words and controls aren't covered.
145. **Reselect range for footage in a dialogue row.** It's offered on card hover/focus (replacing the card's top button while shown) and in the visual ⋯ menu. The existing word selection is the input. Nothing changes until the writer confirms. Escape or Cancel keeps the old range, adds no Undo entry and returns focus to the card.
   - If the selection exactly matches one other visual's range in the row, **Swap ranges** is offered first. It exchanges only the two placements' word anchors (cue, level, parent, return and end anchors) as one Undo entry. Sources, trims and comments stay with each visual, and the card stack follows cue order.
   - Any other selection uses **Set range**, which applies D113's make-room rule.
146. **Visuals-only rows.**
   - Card order comes from in-row dragging; the drag label reads "Reorder in this row". The reorder is one Undo entry.
   - A visual arriving in a row without words is not marked unattached, so no Attach to words or Set range is shown.
   - Untimed non-footage cards (Still Image and others without media) get a positive, editable Hold in seconds, defaulting to 4.0 s. It commits on Enter or blur; a non-positive entry is refused with a message.
   - When an audio bed spans the row, an explicit **Match audio duration** checkbox appears. With several cues, a chooser picks one. The hold then follows that cue's sample length after its source trim, and the field is read-only.
   - If the matched cue is removed, the hold falls back to the last fixed value (4.0 s if never set) and says so.
   - This is prototype authoring state only, with no promises about output timing (see the #326 limits).
147. **Row and visual ⋯ have separate targets.** A 26 px strip at the top of every row's visual column holds the row ⋯; the first visual starts below it, at least 10–12 px clear at both sizes.
148. **D118 coverage cue removed.** Its lines and measuring are off; brackets, connector lanes and 0% previews stay. *Supersedes D118's trial.*
Build notes:
- Harness fixture "Audio over visuals-only row" adds a Pier Morning Strings bed spanning the rows around Harbor caretaker, so Match audio duration can be exercised. It's one Undo entry.
- Stale toolbar Undo label after audio Undo: reported by Matthew and reproduced by review after an audio Undo, though not in my own runs. Fix: the next-undo label and disabled state are now computed last from the committed stack, and the toolbar refreshes after every Undo and every cue adjustment. Re-tested add → trim → fade → Undo ×3, reading the label after each step.
- A wordless row's name comes from its first visual, so reorder messages now say "Moved … to position N of M in this visuals-only row".

### 2026-11-14 · Producer follow-up pass 2 → integrated r20
Built in `S03 Integrated Authoring r20.dc.html` (r19 unchanged).
Codex observations of r19 (independent): keyboard trim/fade and their toolbar Undo labels behaved correctly; the row and visual ⋯ were separate targets at 1024 × 768.
149. **Panel versus script clicks.**
   - Clicking a clip in the Footage panel opens the shared player paused, with trim controls already open on the remembered trim (or the logged range). Trims there become the remembered trim for future placements (D99).
   - Clicking a Footage card in the script plays that placement's own trim. The player shows a visible Trim button (aria-expanded, aria-controls) that opens the controls in the same player; with them open it reads Hide trim.
   - Existing placements keep their own trims.
   - Unavailable media keeps its recovery flow and shows no Trim button.
150. **Short transcripts is a Footage panel preference.**
   - The checkbox sits under the panel search, and its remembered value carries over (same browser key).
   - The toolbar Options control held only this setting, so it's removed. *Supersedes D131's placement in Options.*
   - With Short transcripts on, a clip at its logged bounds shows the opening excerpt, as before.
   - A trimmed clip with transcript timings shows only the timed segments that overlap its in/out, with "…" where a segment runs past either edge. A trimmed range with no speech says "No speech between X and Y s." Either way, Show full transcript expands it inline.
   - A trimmed clip without timings shows the full transcript and explains that a trimmed excerpt isn't available.
   - The excerpt updates as the trim changes. A search query keeps the existing match excerpt.
   - Timings are fixture data on one new 30 s clip, "Caretaker on the schedule (timed transcript)". Whether production Research provides timings, and at what granularity, needs verification.
151. **Label chips filter.** Clicking a label name on a clip sets the panel's label filter to it. It stays in the panel, doesn't open the player and doesn't start a drag. The label control (Any label) clears it, and × still removes the label.
152. **Place in script closes on an outside click** without choosing or placing; Escape and Cancel work as before.
153. **Rename… for Footage and Still Image placements.**
   - Rename… in the visual ⋯ menu opens a small dialog with the current name. Enter or Save commits one Undo entry; Escape or Cancel leaves it unchanged.
   - The name applies to that placement only. The card shows it with "Source: …" underneath, and the card name, comment markers and messages use it. The source title, filename and other placements are unchanged.
   - Leaving the name empty restores the source name.
Build notes:
- 0% hover (D110), checked with simulated pointer/mouse events and programmatic focus: preloaded Footage (Harbor caretaker), newly placed Footage (Sensor housing), a Still Image, and Harbor caretaker after a reload at the saved 0% each showed a poster preview and dismissed on leave. Focus showed previews for Harbor caretaker, Workshop recording and a Still. No missing thumbnail mapping or lost hover path was demonstrated, so no hover code changed. Native pointer remains for Codex.
- The new timed fixture clip has no poster (honest "No thumbnail").

### 2026-11-14 · Producer follow-up pass 3 — checkpoint (superseded by the entry below)
`S03 Integrated Authoring r21.dc.html` exists as an unchanged copy of r20; no pass 3 edits yet (usage limit reached). r20 is unchanged.
Codex observations of r20 (independent, Chrome): the Footage panel click opens the player with trim open; the Short transcripts checkbox works in the panel; real pointer hover on preloaded Harbor caretaker at saved 0% shows its thumbnail. My r20 fixture tests stand (see `S03 spec.md`).
Pass 3 scope still to build (approved by Matthew):
1. Include items below places every note as its own spoken row in outline order, including checked descendants such as "Ask Dana" (changes D65's skip-completed rule; current code in stPlan skips `x.done` descendants). Footage stays with its note's row; clips and saved rows move; note originals and hierarchy stay in Stash; inline drop unchanged; one Undo; gold flash at the destination.
2. Add clip under Add note; root saved rows in the checkbox column; saved row/group editor shows only the saved material in the script area with Stash alongside; clicking another saved row switches directly when clean, keeps the save/discard flow when dirty.
3. Missing Stash footage (night-ferry-departure.mov): inline Find original (fixture verified match, wrong-file rejection, Cancel; identity and trim kept) and a separate Replace clip. Real relink and save/reopen stay production verification items; a filename match doesn't prove identity; no upload.
4. Gap threads stay readable. Label the fixture "Gap before ‘When the harbor… nobody has to wait alone.’", using start/end text where openings repeat (current label uses cmRowName of the next row). Confirm: everyone can Resolve, Reopen and Reattach; Mark all reviewed covers all people and hidden removals up to the frozen boundary, with new arrivals pending (matches r16 findings).

### 2026-11-14 · Producer follow-up pass 3 → integrated r21
Built in `S03 Integrated Authoring r21.dc.html` (r20 unchanged).
154. **Include items below places every note as its own spoken row, in outline order, including checked descendants** (e.g. Ask Dana). Attached footage stays on its note's row; separate clips and saved rows move out of Stash; note originals and hierarchy stay in Stash, checked. Inline drop is unchanged. One Undo. Inserted rows' text and cards flash gold at the destination. *Supersedes D65's skipping of completed descendants.*
155. **Add clip sits under Add note** in the Stash controls.
156. **Find original… and Replace clip… on missing Stash footage**, inline under the clip.
   - **Find original** means locating the same file. The prototype offers two fixture candidates: a verified match restores the clip with its identity and trim (0:12–0:20) as one Undo entry, and a similarly named file with different content is refused. Cancel leaves the clip unchanged.
   - **Replace clip** chooses a different source. The clip's identity changes and the new source's logged range is used; one Undo entry.
   - No file is read or uploaded, and a filename match isn't treated as proof of identity.
157. **Gap threads stay readable.** They are labelled with the next row's opening and closing words, e.g. "Gap before ‘When the harbor… nobody has to wait alone.’"; rows of up to 8 words are shown in full.
158. **Confirmed current behaviour:** everyone can Resolve, Reopen and Reattach; Mark all reviewed covers all people and hidden removals up to the frozen review boundary, with new arrivals pending (as found in r16). No change.
Not done in this pass (checkpoint): root saved rows aligned with the checkbox column; the saved row/group editor showing only the saved material with Stash alongside; switching directly between clean saved rows (the save/discard flow stays for dirty edits).

### 2026-11-14 · Producer follow-up pass 3 finished → integrated r22
Built in `S03 Integrated Authoring r22.dc.html` (r21 unchanged). Completes the items listed as "not done" in the r21 entry.
159. **Root saved rows and groups sit in the checkbox column** of their level, like clips (D141 build notes).
160. **Editing a saved row or group shows only that material** in the script area: other rows and their section headings are hidden (previously dimmed to 30%). Stash stays alongside.
161. **Switching between saved rows and groups.** Clicking another saved row or group while editing:
   - If there are no unsaved edits, it switches directly.
   - If there are unsaved edits, the existing prompt appears (Save / Don't save / Keep editing).
     - **Save** stores the edits (one Undo entry) and then opens the requested item.
     - **Don't save** discards the edits and opens it.
     - **Keep editing** (the Cancel choice) stays on the current item with its edits and forgets the pending switch.
Build note: Cancel in Find original now returns focus to Find original… (r21 used a focus helper that didn't reach the Stash).

### 2026-11-14 · Final verification → integrated r23
Built in `S03 Integrated Authoring r23.dc.html` (r22 unchanged).
Codex checks of r22 (Chrome, native input): Find original refuses the similarly named wrong-file fixture with "Nothing changed"; Cancel returns focus to Find original…; real keyboard typing in a saved row triggers the dirty-switch prompt; Keep editing keeps the draft; Don't save opens the requested row. Temporary moves were undone.
Build notes (defects found and fixed; no new product decisions):
- **Inline note drop flash.** Dropping a Stash note into a paragraph flashed only its copied footage card (none when the note has no footage), so the inserted words got no gold feedback. Now the inserted words are highlighted in gold for about a second, and only those words: a text span can include surrounding words, so the highlight is drawn over the inserted words' own positions.
- **Branch drop between rows.** It already flashed each inserted row's text and cards (r21). No change.
- **Footer.** It now says everyone can Resolve, Reopen and Reattach comments (D158), not that permissions are still open.

### 2026-11-15 · Timeline #125 producer refinements → integrated r24 (built; checks paused at usage limit)
Built in `S03 Integrated Authoring r24.dc.html` (r23 unchanged).
162. **Reselect range for Still Images too.** Cause of "missing": r19 offered it only for Footage, and no dialogue row in the sample has Footage, so it never appeared. Now it's offered for Footage and Still Image cards with a range in a dialogue row: as the button at the top of the card on hover or focus, and as Reselect range in the card's ⋯ menu.
163. **Trim editor transcript uses ⟦ ⟧ brackets** instead of gold per-word fill. They work like the script's range controls: they snap to word boundaries, can be dragged or moved one word with ← → (Home/End), and set the same trim as the play-bar handles. The word being played is underlined.
   - Timings are word-level for the ferry fixture and interpolated within segments for the caretaker fixture. Elsewhere they're simulated and labelled.
   - The trim still applies immediately, as before; there's no separate Save/Cancel for trim in this prototype.
164. **Playback scope.** With Trim closed, Play starts and stops within the saved trim. With Trim open, Play and scrubbing cover the whole logged clip, and auditioning outside the selection leaves the trim alone. Playback is simulated.
165. **Footage panel transcripts.**
   - With Short transcripts on, the panel shows the words inside the panel trim, or the opening excerpt when the clip is untrimmed (0 to its full length).
   - With it off, the panel shows the full transcript with the trim marked subtly.
   - Per-clip expansion is unchanged.
   - Ferry fixture word timings added: its trim of 1.2–7.4 s gives "it goes, and the ferry is".
   - The panel trim stays separate from each placement's own trim.
166. **One comment count per footage card.** Each distinct thread counts once, with a Research thread counted as one. It uses the regular ❝ marker, which opens the discussion; the separate "Research · N" pill is gone.
167. **Comment row labels use the row's first 3 and last 5 words** (e.g. "When the harbor… nobody has to wait alone."). Rows of 8 words or fewer show once in full. Selected quotes stay separate.
168. **Stash Add note is the primary action, with Add clip under its ▾ menu.** Standalone clips get a completion checkbox.
169. **Place in script skips completed items whatever Hide completed is set to.** Descendants are judged one by one, and footage attached to a skipped note stays with it. Place is disabled with a message when nothing live can be placed. *Supersedes D154's placement of checked descendants.*
170. **Audio and popups.** "Creates M3. Audio isn’t a visual." is removed. Routine popups dismiss after 6 s; the timer pauses on hover or focus and resumes on leave. Errors (Couldn’t…, must be…, Nothing changed…) stay. Toolbar Undo is unaffected.
Build note: thumbnail slider. The handler now ignores repeated values and keeps the first visible script row at the same screen position as sizes change. This is the likely cause of the jump, but it hasn't been confirmed with a native pointer.
CHECKPOINT: only item 1 has been UI-checked (Reselect range shows on Still hover and focus). Everything else is built but not yet checked.

### 2026-11-15 · Timeline #125 Pass 1: Reselect range and cutaway returns → integrated r25
Built in `S03 Integrated Authoring r25.dc.html` (r24 unchanged). This supersedes the r24 follow-up that stopped at the usage limit. The other r24 items (D163–D170) are carried forward unchanged; Codex reported in Chrome that the Channel light short/full transcript, the trim refresh, both trim controls on the keyboard, and expanded playback outside the trim work. They aren't re-verified here.
171. **Reselect range has its own control, separate from ⋯.** Cause of the Chrome misclick: in r24 the hover button replaced the card's top line, which pushed ⋯ down under the pointer. Reselect range is now a separate button below the card header. It appears on hover or keyboard focus, for Still Image and Footage attached to dialogue. ⋯ doesn't move (its position is unchanged with and without hover), and the ⋯ menu still lists Reselect range.
172. **Escape always exits Reselect**, including when focus is on its active "Select new words · Esc keeps the current range" control. The old anchors stay, the message "Reselect cancelled. The range didn’t change." is shown, and focus returns to the control that opened it (⋯ or the Reselect button).
173. **The proposed range is highlighted while confirming.** Every word in the new span is highlighted in the script, across wrapped lines, until Set range, Swap or Cancel. The confirmation shows the word count instead of a one-word endpoint preview. The old range stays until Set range. One Undo restores it.
174. **Cutaway returns are recalculated with the edit and validated first.** The confirmation says when an edit removes a return ("Recipe card no longer resumes after it") or creates one ("On Camera · Wide resumes after it"). Set range is refused, with the reason, when the selection is the current range, falls outside the row, or would leave an orphaned return or one with no words; nothing changes.
   - **Recipe Card:** shortening Still Image 1 to end before Still Image 2 ends it on its last selected word. Still Image 2 stays where it is, there's no "Still Image 1 resumes", and the uncovered gap uses On Camera ("OC resumes").
   - A cutaway placed inside Still Image 1's words correctly resumes Still Image 1.
**Production rule (not prototype evidence):** the whole affected picture sequence must be recalculated and validated in the same edit, with guards against orphaned and zero-length returns. An invalid proposal keeps the previous state and explains why. Production acceptance covers moving editable brackets by pointer and keyboard; drag responsiveness is judged in working software. The baseline is `docs/prototypes/issue-125/integrated-s03-checklist.md`, which isn't in this project, so it wasn't consulted here.

### 2026-11-15 · Codex r25 review fix → integrated r25 (same file, checkpoint)
Codex (Chrome, native input) confirmed: ⋯ click opens the menu; Escape returns focus to ⋯; a one-word commit and its Undo at 1280; and Escape at compact width keeping the old brackets.
175. **Reselect by keyboard waits for Enter.** Defect: while Reselect was active, the first Shift+arrow key opened the confirmation for one word. Later keys extended the blue selection and brought up the ordinary Add visual / Add comment toolbar, but the confirmation stayed at one word and Set range committed only that word. Now:
   - Shift/Option+arrow selection only updates the pending range. The active control reads "N words selected · Enter to review · Esc cancels".
   - Enter in the narration opens the confirmation; with nothing selected it explains what to do.
   - Pointer selection still opens the confirmation on release.
   - The ordinary selection toolbar is suppressed while Reselect is active, and selection changes are ignored while the confirmation is open, so the highlight, the word count and what Set range commits always match.
   - Escape cancels at any point.
   - The proposed-range highlight is redrawn if a re-render removes it (seen once at 1024 × 768 in r25).

### 2026-11-15 · Timeline #125 Pass 2: Footage, audio, Stash → integrated r26 (checkpoint at usage limit)
Built in `S03 Integrated Authoring r26.dc.html` (r25 unchanged). Codex (Chrome) confirmed the r25 six-word keyboard review, Set range, one Undo at 1280, and compact Escape.
176. **Script Footage card transcripts follow that placement's trim.** They show every word inside the placement's in/out and update as soon as the trim changes. Word times come from the fixtures where they exist; otherwise words are spread evenly (simulated).
    - **Placement trims no longer change the Footage panel's preview trim.** *Supersedes D99's rule that the latest trim made in the script was remembered for future placements.* Only trims made in the panel set the panel preview.
177. **Trim player opens wider** (520 px, 440 px compact) with a taller transcript (up to 210 px), and stays inside the frame. Brackets and play-bar handles still set the same trim. With Trim closed, playback covers the trim; with it open, the whole logged clip (r24). Playback is simulated.
    - Production acceptance (not provable here): one-source-frame transport steps and I/O to set in/out at the playhead, checked against real media with a known picture change. Transcript brackets step by word.
178. **Short transcripts, three states.**
    - **No explicit trim:** the opening ~24 words, with "…" only when text is cut.
    - **Explicit trim** (set in the panel, or a logged Research range narrower than the clip): every word inside it, lightly highlighted, with no excerpt ellipsis; Show full transcript reveals surrounding words if there are any.
    - **Explicit whole clip:** every word in both modes, labelled "Whole clip selected", with no expansion button.
179. **Audio names.**
    - The purple rail in Authoring is removed.
    - Quiet piano is now an Authoring fixture from "The amber lantern was never…" to "A chalk crescent appeared…". Its ⌈♪ start and ♪ Quiet piano⌋ end brackets are visible without hover.
    - Internal cue IDs (M3, M4…) are removed from the cue face, panel, picker, status messages, Undo labels and accessible names. The cue name and its timing stay.
180. **Stash.**
    - Hide completed also hides checked clips with no live descendants (e.g. Gulls).
    - Place in script… is disabled, with grey text and "· every item here is completed", when a branch has nothing live.
CHECKPOINT (usage limit): Pass 2 items 1–5 are built and partly checked. Not yet run:
- the mixed-branch placement with one Undo;
- 1024 × 768 for the player and panel;
- the overnight regression checks (thumbnail slider drag and keys, 0% hover, one comment count, row labels, popup expiry, Add clip under ▾);
- the six-word keyboard smoke test in r26.

### 2026-11-15 · r26 focused correction: clip player vs Contributions bar (same file)
Chrome (Codex) confirmed in r26:
- Gulls disappears when checked with Hide completed on.
- A mixed Cold open branch places the two expected rows with the horn footage, and one Undo reverses it.
- Place in script is disabled for the all-completed branch.
- The Channel light short transcript is exact.
- The wider player opens at 1024 × 768.
Defect (Codex): at 1024 × 768, with Show contributions on, opening Channel light from the Footage panel left the Contributions bar painted over the trim transcript and intercepting clicks on it, and the player reached below the Authoring frame.
Fix (built): after each render the player measures the Authoring frame and the Contributions bar. It keeps itself inside the frame (8 px inset) and ends at least 8 px above the bar, is drawn above the bar, and scrolls internally when its content is taller (maxHeight from the space available). This also applies when the player has been dragged, and is recalculated on resize.
- An earlier version that measured during render could leave the preview unresponsive. It was replaced by the post-render measurement.
- **Not verified:** the preview stopped responding to checks after reloads, so the fix couldn't be measured at 1280 × 800 or 1024 × 768 in this session.
The separate panel trim (D176) is unchanged.

### 2026-11-15 · Timeline #125 Authoring corrections → integrated r27
Built in `S03 Integrated Authoring r27.dc.html` (r26 unchanged).
181. **Trim player rows.** The player's rows are sized to their content: preview, transport, trim controls and transcript sit in separate rows, and the player scrolls internally when it's taller than the space available. It stays inside the Authoring frame and above the Contributions bar (r26 fix). Its position is frozen during a trim drag (rail, ⟦ ⟧ or words), even if the card or transcript changes height, and it re-clamps on release. Moving and resizing the player explicitly still work.
182. **Contiguous On Camera is one passage after a range edit.**
    - A visual that now ends before the existing On Camera card moves that card's start up to meet it, instead of leaving an "OC resumes" card before it.
    - A return to On Camera that runs straight into an On Camera card becomes that card's earlier start.
    - Adjacent On Camera cards with the same framing are joined. The existing card keeps its framing.
    - Real returns across an intervening visual stay.
    - A direct Tight/Wide cut still needs a row break (unchanged; not exercised here).
183. **Audio.**
    - The legacy Quiet piano row badge is removed; the r26 purple rail stays removed.
    - The end bracket is back to ♪⌋ in the text. Its cue name ("♪ Quiet piano ends") appears outside the narration on hover and keyboard focus.
    - Visuals-only rows offer "Add audio starting at this row’s start" in the row ⋯. The cue's face sits on that row; it ends in the next narration row and can be dragged from there. The visual keeps its own hold by default, and Match audio duration appears on the still.
    - Ending the cue exactly at the visual row's boundary isn't available in this prototype (cue ends are word anchors).
184. **Compact Footage cards.**
    - **Header:** thumbnail beside the title, quiet metadata and labels with + Label.
    - **Below:** the transcript at full card width, then Show full transcript (when useful) and one usage pill.
    - **Removed:** status text, trim messages, ‹ › arrows and the n/N counter. Place in script… is hidden until it gets keyboard focus.
    - **Used once** jumps to the placement. **Used N times** opens a short list of the script locations (row and first/last words), each of which jumps there.
    - Harbor mouth now has three uses in the default sample, kept out of Undo.
    - Dropping on a row is unchanged; dropping in a gap, or Place in script… to a gap, creates one visuals-only row, with one Undo.
Build note: the end-bracket name label could linger after a programmatic blur in the scripted check; real focus changes clear it.

### 2026-11-15 · Focused r27 review → integrated r28
Built in `S03 Integrated Authoring r28.dc.html` (r27 unchanged; the Workshop player and Paper Lanterns fixes are kept).
Codex (Chrome, real pointer) checks of r27:
- Workshop recording at both sizes: preview and Play don't overlap. A real drag on the out handle changed 22.0 s to 18.6 s (1280) and to 18.2 s (1024) with the player's bounds unchanged, and it was restored to 22.0 s.
- The default three-use list works.
- Keyboard gap placement works, with one Undo.
- Harbor Tide Bed added to Harbor door keeps the 4.0 s hold, and the cue continues into "Rain gathers along the window".
185. **Pointer placement from the Footage panel.**
    - **Defect:** library clips could only target a row's visual column, and the Add-row seam strip covered the boundary between rows, so a drop on the line created nothing. Dragging from the card margin selected page text.
    - **Now:** the card is a drag source (grab cursor, no text selection; transcript text stays selectable). Dropping on the boundary between rows creates one visuals-only row; the gap target is 14 px on each side of the line, including the seam strip. The ghost reads "New visuals-only row here", and a 6 px gold line marks the target. Dropping on a row's visuals still adds to that row. Each is one Undo.
186. **Cue anchor wording.** A cue starting in a visuals-only row is described as "the start of “Harbor door”". Word anchors name the row by its first and last words instead of a row number, in the picker, the brackets and the face's accessible names.
**Working-app acceptance (not supported by the prototype model):** cue ends attach to words, so ending a cue exactly at a visuals-only row's boundary isn't possible here. In working software: start a cue at Harbor door's start edge, end it at that row's end boundary without entering "Rain gathers along the window", and confirm the still keeps its own hold unless Match audio duration is chosen.

### 2026-11-15 · Closeout pass after r28 → r29
Built in `S03 Integrated Authoring r29.dc.html` (r28 unchanged).
187. **Footage search keeps the trim display.** A search query filters the list but no longer replaces the card's transcript. Filtered and unfiltered cards show the same thing: in Short transcripts mode an explicit trim shows the entire selected passage; in full mode the full transcript with the selection highlighted; an untrimmed clip shows the ordinary opening excerpt. Compact card, usage pill and three-use list unchanged; clicking still opens the saved panel trim.
188. **Stray lavender stripe removed.** The leftover 3 px Quiet piano stripe at the left edge of "The amber lantern…", "A chalk crescent…" and "We built this frame…" is gone from Authoring. In-script ⌈♪ … ♪⌋ brackets and the cue's own spine beside the visuals stay. The Sorting outline's music column is not Authoring and is unchanged.
189. **End-bracket cue name.** "♪ Quiet piano ends" shows while the pointer is over ♪⌋ or while it has keyboard focus. It clears on pointer exit, blur (including a scripted blur), window blur, or when the bracket leaves the page. A mouse click alone doesn't keep it open.
190. **On Camera coherence after range edits and splits.**
    - On Camera that loses all its words is removed, including leftovers from repeated edits. Stills, clips and other non-camera visuals keep Attach to words.
    - When On Camera opens a row it's a normal full On Camera card. The compact "OC resumes" chip is only for a real return after an intervening visual in the same row, so it's never first.
    - Shortening the last visual in a row hands the freed words back to On Camera as a real return.
    - Adjacent On Camera coverage within a row is coalesced after a range edit or a split, whatever its framing: one uninterrupted passage, one card, one framing. The authored card is kept (with its framing) over one the prototype generated. A real return after a cutaway stays. A direct Wide/Tight cut needs a row break.
191. **Shared timing rule (visuals and audio).** At normal speed, any three of source in, source out, timeline in and timeline out determine the fourth. End-anchored audio: [#574](https://github.com/mbelinkie/vera-script-to-timeline/issues/574). How estimated endpoints look in the script and clip transcript (including fading edges) is left to the later Footage design story.
192. **Dragging a bracket can remove On Camera.** Dragging a visual's ⟦ or ⟧ across the whole of the neighbouring On Camera card removes that card. Before, the drag stopped one word short and left a one-word On Camera (Matthew, "A folded letter…"). Reselect range already did this. Applies to authored On Camera only. A still, clip or other visual still keeps at least one word.
193. **On Camera fills uncovered narration; Wide/Tight is the framing choice (Matthew 2026-11-15; made explicit at the #125 handoff, 2026-11-15).**
    - On Camera isn't a visual the Producer places. It fills whatever narration no visual covers, and gives way wherever a visual is placed or extended. It never blocks a range change, never keeps a leftover word, and never needs Attach to words.
    - The only On Camera choice is framing: Wide or Tight, stored per passage.
    - The first On Camera in each row is a full-size card, even if a still comes first.
    - A compact card ("OC resumes") is reserved for a genuine return to the same shot after an intervening cutaway.
    - D190 and D192 follow from this. This wording replaces D190's "when On Camera opens a row" condition.
    - Production model: On Camera is derived from the uncovered words, not stored as cards with ranges.
    - To audit in the prototype: On Camera actions in menus (delete, move, stash, change type), ordinals and Undo labels that treat it as an item, and drag/drop that targets it.
**Production acceptance (needs the real editing model):** general validation of splits, overlaps and cutaways: recalculate the whole picture sequence in the same edit, with no orphaned or zero-length returns and no duplicate On Camera passages.
Change log: decisions 187–193 added (Matthew, 2026-11-15); integrated r29 built. D193 made explicit at the #125 handoff (entry below).

### 2026-11-15 · #125 handoff closeout (r29 review revision; documentation and export only)
No prototype code changed in this pass.
- **Review revision:** `S03 Integrated Authoring r29.dc.html`. It is a complete build of D187–D192. D193 is a recorded principle; its prototype audit was not done.
- **What was interrupted:** the documentation and export closeout after r29. The r29 entry above had no change-log line, `S03 spec.md` still named r20 as the current build and didn't list D192–D193, and no r29 export existed. All three are completed here.
- **Export:** `exports/issue-125-r29/` holds a byte-identical copy of the r29 source with its `support.js`, and a self-contained single-file export.

**Known prototype failures (r29), for one production range-edit issue. Status: open for implementation.**
- **Folded Letter** ("A folded letter sat inside the sleeve…"): dragging the bracket removed On Camera but left Undo disabled.
- **Folded Letter:** shortening the still by one word moved the neighboring still's start.
- **Amber Lantern** ("The amber lantern was never…") and **Paper Lanterns** ("Paper lanterns were folded…"): confirming the highlighted selection created an Undo entry while the displayed brackets stayed put.
- These supersede the r29 scripted pass on Folded Letter (`S03 spec.md`, r29 results).

**Production requirement:** after a range edit (bracket drag, keyboard bracket move or confirmed Reselect), the displayed coverage matches the confirmed edit: brackets, cards, On Camera passages (D193) and neighbouring visuals. A neighbour's start moves only where the edited visual now covers its words. One Undo restores the full prior sequence: every visual's range, every On Camera passage with its framing, and card order.

**Sign-off:** stopped for Matthew's sign-off of the #125 handoff. #125 stays open.
Change log: D193 made explicit (On Camera fills uncovered narration; Wide/Tight is the framing choice; first On Camera per row is full-size; compact only for a genuine return). Range-edit failures recorded as open for implementation. r29 export made.
