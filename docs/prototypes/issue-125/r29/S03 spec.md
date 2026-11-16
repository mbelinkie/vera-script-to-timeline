# S03 spec: current state

How S03 authoring works now. History and reasoning are in `S03 design decisions.md`; numbers in brackets (D84) point there. Update this file at the end of every notes round.

**Status:** Built (rN) = in the named build · Planned = agreed, on `Implementation backlog.md` · Deferred
**Backend:**
- **Proven**: covered by a merged ticket (#337 create sections and move items; #340 stash, create, place; #341 direction/spoken conversion; #342 returns; #326 music; #119 Wide/Tight)
- **Ticketed**: designed, ticket filed, not delivered (#365–#368, #373)
- **#356**: Show contributions production implementation (backend persistence and change tracking). Requirements are in #62 (S03-CONTRIB-001–008); design and integration are #125.
- **UI**: front end only, no backend work
- **NEW**: invented during design, no ticket yet. Each needs a backend ticket (D107).

Status comes from the decision log. r11 parts 1 and 2 are built (part 2 is `S03 Integrated Authoring r12.dc.html`). The Footage refinements (D125–D134) are built in `S03 Integrated Authoring r13.dc.html`; the Writing integrity pass (D135–D140) is built in `S03 Integrated Authoring r14.dc.html`; the Stash refinements (D141–D142) are built in `S03 Integrated Authoring r15.dc.html`; the Comments, Contributions and workspace pass is built in `S03 Integrated Authoring r16.dc.html`; final verification fixes are in `S03 Integrated Authoring r17.dc.html`; the Chrome-review fixes are in `S03 Integrated Authoring r18.dc.html`, the last complete build; producer follow-up pass 1 is in `S03 Integrated Authoring r19.dc.html`; pass 2 (Footage panel and cards) is in `S03 Integrated Authoring r20.dc.html`; the Timeline #125 passes run through r24–r28; the closeout (D187–D193) is in `S03 Integrated Authoring r29.dc.html`, the current build and the #125 review revision (export in `exports/issue-125-r29/`; awaiting Matthew's sign-off); r13 was partly checked in the UI on 2026-11-13 (see the checklist). Nothing here is production-backed unless the Backend column says Proven.

---

## 1. Layout and top bar
| Rule | Status | Backend |
|---|---|---|
| Top bar order: Aa slider, Sort rows, Show contributions, Show stash, Comments, Options (D78) | Built r8 | UI |
| Options holds one item, Short transcripts (D129); other contents deferred (D79) | Built r13 | **NEW**: per-user preference storage |
| Undo in the top bar, with a recent-actions menu; its label names what Cmd/Ctrl+Z will undo; hidden in Sorting (D34) | Built r16 | UI |
| Top bar fits at both sizes: one row at 1280 × 800; two rows at 1024 × 768 (title, Undo and sliders, then panel buttons and Options) | Built r16 | UI (open question for Matthew) |
| Sentence case for all buttons and labels, "stash" lowercase (D104) | Built r11 (top bar) | UI |
| Thumbnail size slider in the top bar, 0–100%; at 0% only words show and visuals preview on hover or keyboard focus, using the visual's image or its sample thumbnail tile; missing-image visuals don't preview (D102, D110) | Fixed r17 | UI |
| Authoring size 80–150%; text, cards, controls and spacing scale together (D33) | Built | **NEW**: per-user preference storage |
| One sidebar at a time: Footage, Stash or Comments. The active button has a gold outline (D16, D99) | Built r12 | UI |
| Sidebar resizes by dragging the divider: sidebar ≥260px, script ≥560px, double-click resets (D17) | Built | UI |

## 2. Rows
| Rule | Status | Backend |
|---|---|---|
| Two columns: narration left, visuals right | Built | Proven |
| Row ⋯ (Stash, Delete row, Select range) appears on row hover at the top-right, completely inside the row and partly over the first card, and doubles as the drag handle. No reserved strip (D29, D101, D122) | Built r12 | UI |
| No between-row strips. Hovering a divider shows a two-sided **Add row \| Add transition** button; Add row has a ▾ holding Add section. "Comment on gap" is removed (D101, D106) | Built r11 | UI |
| Transitions are allowed at every divider, including before the first row and between sections (D101) | Built r11 | **NEW** if not covered by existing transition work |
| Split and join from a selection. A selection that includes a row's start or end gets Join to previous, Join to next and Split into new row. Join moves only the selected words. Join is disabled across a section break. Split places the new row before or after the original; it's hidden for whole-row selections. Visuals follow their start word; a visual that starts before the selection is clipped at the split; no visual appears in two rows. A stage direction moves only if its start is selected (D97) | Built r11 | **NEW** |
| Select range, then Stash group / Delete group, with keyboard range mode; ranges stay within one section (D42, D60) | Built | Ticketed #366 |
| Screen-reader labels name content, not row numbers; names stay correct after insertion, move and Undo (D61) | Fixed r16 | UI |

## 3. Narration and selection
| Rule | Status | Backend |
|---|---|---|
| Typing in narration, with Make spoken / Make stage direction (D3, D68) | Built r4 | Proven #341 (typing and paste are unproved) |
| Erasing all narration keeps the row and its visuals; word positions and paragraphs are cleared; one Undo restores everything; Delete row stays in the row menu (D135) | Built r14 | **NEW**: empty-narration row with visuals |
| While narration is focused, the status area shows "Return: paragraph · Tab: split row · Esc: leave text" (D136) | Built r14 | UI |
| Escape leaves narration and focuses the row's first visual card (D140) | Built r14 | UI |
| Visuals stay on their intended words after edits, including repeated phrases and non-Latin text; deleted cue words leave the visual without a start word; IME composition is respected (D139) | Built r14 | **NEW**: production text identity for anchors |
| Deleting either bracket of a direction removes its partner (D4, D68) | Built | Proven #341 |
| Return inserts a paragraph break within the row; Tab splits the row at the cursor (empty row at the end, one Undo step), visuals following D97; Esc leaves the text box. A break after the final word moves with a split-off suffix (D114, D137, D138) | Built r14 | **NEW**: paragraph breaks in row text |
| Selections snap to whole words **while dragging**; punctuation goes with the word before it (D95, D105) | Built r12 (live highlight in browsers with CSS highlights) | UI |
| Backspace at a row's start joins it to the row above as a new paragraph; blocked across sections. Straight after a Tab split, it restores any visual the split clipped (D115, D124) | Built r12 | **NEW** (with split/join) |
| Paste: a blank line starts a new row; a single line break is a paragraph break; one Undo reverses only that paste. Rich-text paste (Google Docs) is Deferred (D119, D121, D138) | Built r14 (plain text) | **NEW** |
| Selection menu order: Add visual, Add comment · Split, Join previous, Join next · Stash words; inapplicable items hidden (D120) | Built r11 | UI |
| ⌘⇧F on a selection opens footage quick search (D117) | Built r12 | UI |
| Coverage cue at 0%: a margin line per visual range, Visual Undefined distinct (D118) | Trial r12 | UI |
| Selected words → Add visual opens the type menu, with cutaway and end rules (D94) | Built r10 | **NEW** |
| Selected words → Stash words. Plain words become a note; words with cues become a saved row (D90) | Built r10 | **NEW** |
| Selected words → Add comment | Built | Proven #342 (comment limits) |

## 4. Visuals
| Rule | Status | Backend |
|---|---|---|
| Types: Footage, On Camera, Still Image, Web Capture, Graphic, Onscreen Placeholder, Need to Find, Visual Undefined (D93) | Built | Proven |
| + Visual appears only on rows with no narration; elsewhere, select words (D96) | Built r11 | UI |
| Visual ⋯ menu: Trim (player with in/out handles), Change type, Stash, Comment, Delete, labels only with no helper text. Replaces "comment on this visual" (D100, D123) | Built r12 | **NEW** (Change type, Delete) |
| Deleting a row's last visual leaves a Visual Undefined card (D100) | Built r11 | **NEW** |
| Cards stack in cue order and flash gold when they move (D89) | Built r9 | UI |
| Drag a card to another row: it keeps its trim, lands unattached, and shows Attach to words (D87, D88) | Built r10 | **NEW** |
| Attach to words follows Add visual's rules: the new visual takes the full selection, and neighbouring visuals' ranges shrink or shift around it (D113) | Fixed r11 | **NEW** |
| Stash one visual (not On Camera) (D91) | Built r10 | **NEW** |
| On Camera Wide/Tight toggle | Fixed r11 | Proven #119 (picture transform only) |
| Clip player: movable, resizable, Set in/out, trim handles, transcript click-to-seek (D39) | Built | **NEW**: persisting trims on script footage |
| On Camera fills whatever narration no visual covers and gives way to any visual; Wide/Tight is its only choice, stored per passage (D193) | Principle; prototype audit not done | **NEW**: derive On Camera from uncovered words |
| The first On Camera in each row is a full-size card, even if a still comes first; the compact "OC resumes" card only for a genuine return to the same shot after an intervening cutaway (D190, D193) | Built r29 | **NEW** |
| After range edits and splits: no wordless OC cards; adjacent OC in a row coalesced (D190) | Built r29 | **NEW**: general split/overlap/cutaway validation |
| Dragging a bracket across a whole On Camera passage removes it; other visuals keep at least one word (D192) | Built r29 (known failures below) | **NEW** |
| Range edits: displayed coverage matches the confirmed edit; one Undo restores the full prior sequence | ✗ Fails in r29 (Folded Letter, Amber Lantern, Paper Lanterns); open for implementation | **NEW**: production range-edit issue |
| Timing: at normal speed any three of source in/out and timeline in/out determine the fourth, for visuals and audio; end-anchored audio #574 (D191) | Rule recorded | **NEW** |

## 5. Footage
| Rule | Status | Backend |
|---|---|---|
| Clips are logged Research clips (YouTube). Search matches title and transcript only, everywhere, using the full transcript; logger is a dropdown, dates are Sort (D12, D130) | Built r13 (sample data) | **NEW**: Research clip reference (#340 payload unproved) |
| Quick search ranks transcript matches for the selected words first (D116, trial) | Trial r12 | **NEW**: transcript matching |
| Quick add: search box (title or transcript), unused clips only by default, Show used toggle. Opening it commits nothing; Escape/outside click change nothing; choosing a clip is one Undo step (D98, D131) | Built r13 | **NEW**: search, usage index |
| Footage sidepanel: all project footage, search, logger/label/usage filters, Sort (newest default, oldest, title A–Z; remembered), own thumbnail slider. Clips drag into rows and land unattached (D99, D128) | Built r13 | **NEW** |
| Clicking a clip (panel, Stash, script) opens the player; in the script it plays that use's in/out, in the panel the remembered trim or logged range. Previewing changes nothing (D125) | Built r13 | UI |
| Usage pill "Used once" / "Used N times" goes to the use and flashes it gold; ‹ 1/N › steps through several (D126) | Built r13 | **NEW**: usage index |
| Clip labels: shown, + Label (pick or create), × removes, single-label filter. Labels belong to the source clip and are intended to be Research's set (D127) | Built r13 (fixture, session only) | **NEW**: Research clip-label API; Research naming ("Topics") and colours to confirm |
| Full transcripts by default; Options › Short transcripts shows excerpts with per-clip Show full transcript / Show less (D129) | Built r13 | **NEW**: per-user preference |
| Place in script… from the panel, using the Stash gap chooser; makes a Footage row (D132) | Built r13 | **NEW** |
| Research: none logged empties the panel and quick search with Open in VERA Research (D133) | Built r13 | UI |
| A clip remembers its latest manual trim, even after that instance is changed or deleted. New placements use it; existing instances keep their own trims (D99) | Built r12 (this session only) | **NEW**: clip-level trim |
| Unavailable clips can be placed; the card shows the reason and offers Replace clip… and Open in VERA Research (D15) | Fixed r17 | Proven (placement); **NEW** (Research reconnect) |
| Open in VERA Research when a clip isn't logged yet (D13) | Built | Research owner |
| Brief transition between sidebar panels | Build note only | UI (production) |

## 6. Sections (script)
| Rule | Status | Backend |
|---|---|---|
| Sections are organizational markers exported to Resolve; breaks go only between rows (D106) | Built r11 | **NEW**: Resolve marker export |
| Add section from the divider's ▾ opens an inline title field (D106) | Built r11 | **NEW** |
| Section header ⋯: Rename, Delete break. Deleting merges into the previous section (D106) | Built r11 | **NEW** |

## 7. Stash
| Rule | Status | Backend |
|---|---|---|
| Notes, clips, saved rows and groups in user sections. Add note, Add section, Add clip at the top (D9, D35, D57) | Built | Proven #337, #340 |
| Count covers every entry; the header breaks it down by kind; group rows count, the group itself doesn't (D1, D45) | Built | UI |
| Notes are plain text with literal brackets (D56) | Built | Ticketed #365 |
| Notes are checklist items, with Hide completed (D62, D63) | Built r5 | Ticketed #373 |
| Placing a note copies it as **spoken** text and checks the original (D64, D84) | Built r8 | Ticketed #373 (spoken vs direction is **NEW**) |
| Per-insertion return of untouched copies (D66) | Built r5 | Ticketed #373 |
| Attached footage: one clip per note, shown as a strip, with Replace and Detach (D49–D53) | Built | Ticketed #367 |
| Include items below (D58, D65) | Built | UI over #340 |
| Drag into the script between rows, or into a row: a gold text cursor for notes, a gold line on the visuals side for clips (D18, D86) | Built r10 | Proven (between rows); **NEW** (into a row) |
| A note dropped into a paragraph inserts spoken words (literal brackets), checks the note, copies attached footage to the first inserted word, has no return link; nested items stay put; one Undo/redo (D141, D142) | Built r15 | **NEW** |
| Stash clips sit in their level's checkbox lane | Built r15 | UI |
| Place in script: destination filter; preview and toast say spoken text and what's copied vs moved; row action reads Return to stash | Built r15 | UI |
| Stash player for an unavailable source shows the reason and logged range, with no Play | Built r15 | UI (reconnect deferred) |
| The drag ghost trails the pointer from its top-left corner (about 12px offset) so the gold cursor and line stay visible (D85, D112) | Built r11 | UI |
| Drag out of the script into Stash; drag within Stash to reorder and nest (D19, D20, D82) | Built | Proven #337, #340 |
| Saved rows and groups open in the script's row renderer, ask to save on close, and groups can add or remove rows (D41, D47, D48, D59) | Built | Ticketed #366 |
| Returns go to their original place, otherwise the top of Stash unsectioned; mixed returns allowed (D40, D54, D55) | Built | Ticketed #368 |
| One-click delete with Undo (D26) | Built | Proven |
| Attribution @name · date, hidden on your own items (D32) | Built | **NEW** if not in #340 |
| Stash text size slider 80–200% (D33, D46) | Built | **NEW**: per-user preference |
| Rename Stash sections; deleting one moves its items to unsorted at the top (D109) | Built r12 | **NEW** |
| Reconnect missing footage from Stash | Deferred | — |

## 8. Comments
| Rule | Status | Backend |
|---|---|---|
| Comments sidebar; yellow words open a discussion; orphaned comments collapse | Built | Proven #342 |
| Comments show in Sorting. Clicking one expands its row and scrolls to it; clicking another collapses the first (D103) | Built r12 | UI |
| Comment-only access to a document | Deferred | — |

## 9. Sorting
| Rule | Status | Backend |
|---|---|---|
| Sort rows opens Sorting; ← Back to script is gold (D80) | Built | UI |
| Accept/Discard; organization vs edits classification (D67) | Built r4 | Proven #342 |
| Show contributions hides in Sorting; Stash stays available (D77) | Built | UI |

## 10. Show contributions (option B, D108; requirements #62, design #125, production #356)
| Rule | Status | Backend |
|---|---|---|
| Bar: See contributions, first-name chips, ✕ top-right, timeframe count pill, gold Mark all reviewed (D69–D74). Mark all reviewed acknowledges every pending change by others up to the frozen boundary, whatever chip or Show removed setting; later arrivals stay pending; a failed save marks nothing; Sorting Accept/Discard acknowledges nothing (verified r16; scope question open for Matthew) | Built r8 | #356 |
| Removed rows use the Reconciliation format; Show removed default follows the range (D75, D76) | Built r8 | #356 |
| Overwritten-change catch-up line (D71) | Built r8 | #356 |

## 11. Deferred
Rich-text paste from Google Docs (D121) · spell check · word count and estimated length · comment-only access · Options contents · reconnecting footage from Stash · music beyond #326 · motion and framing.

---

## Pending producer choices (Matthew)
- **Sign off the #125 handoff** on r29 (review revision, source and export in `exports/issue-125-r29/`), with the range-edit failures open for implementation.
- Mark all reviewed scope: stay global, or only what's shown for the selected person / with removed items hidden?
- Who may Resolve, Reopen and Reattach comments?
- Adopt the 0% coverage cue trial (D118)?
- Two-row top bar at 1024 × 768, or shorter labels?

## Unscoped functionality (needs backend tickets)
Every **NEW** item above, grouped as possible tickets:
1. **Row restructuring:** split and join from a selection, with visual carry rules (§2).
2. **Script sections:** create, rename and delete, with Resolve marker export (§6).
3. **Visual lifecycle:** delete, change type, move between rows with unattached state and Attach to words, stash one visual, add on a selection with cutaway rules (§3, §4).
4. **Word-level Stash operations:** stash selected words; drop a note into an existing row (§3, §7).
5. **Footage library:** Research clip reference, title/transcript search, usage index, clip-level remembered trim, trim persistence on script footage, shared clip labels read and written through Research, per-user Sort and Short transcripts preferences (§4, §5).
6. **Stash sections:** rename and delete to unsorted (§7).
7. **Notes as spoken text** on placement (D84), versus #373's direction behavior (§7).
8. **Per-user view preferences:** Authoring size, Stash size, Thumbnail size (§1, §7).
9. **Paragraph breaks and paste** (D114, D119, D138): paragraph storage, prompter and export; paste parsing into rows (§3). Prototype behaviour only; real persistence, prompter output and Resolve export are integration requirements (R16).
13. **Picture-sequence validation and timing** (D190–D191): split, overlap and cutaway validation in one edit; the three-of-four timing rule for visuals and audio; end-anchored audio (#574). Estimated-endpoint visuals wait for the Footage design story.
14. **Range edits** (D190, D192, D193; one production issue, open for implementation): after a bracket drag, keyboard bracket move or confirmed Reselect, the displayed brackets, cards and On Camera passages match the confirmed edit; a neighbour's start moves only where its words are now covered; one Undo restores every range, On Camera passage and framing, and card order. Known r29 failures are in the test checklist.
12. **Empty narration rows and anchor identity** (D135, D139): storing a row with visuals and no words; a production text-identity model for visual anchors (the prototype uses edit-position mapping).
10. **Transitions at every divider**, if not already covered (§2).
11. **Attribution on Stash items**, if #340 doesn't store author and date (§7).

---

## Test checklist
Run against each build. ☐ = untested.

**Top bar and view**
- ☐ The top bar reads, in order: Aa, Thumbnails, Sort rows, Show contributions, Show footage, Show stash, Comments, Options; all labels in sentence case
- ☐ Thumbnail size at 0% hides every card's image; hovering any visual shows its preview, reliably, in every row
- ☐ Thumbnail size at 100% and 50% scales cards; the value persists after reload
- ☐ Authoring size scales text, cards and controls together
- ☐ Only one sidebar opens at a time; the active button has a gold outline
- ☐ The sidebar divider respects 260px and 560px minimums; double-click resets it

**Rows**
- ☐ No space is reserved between rows; hovering a divider shows Add row | Add transition on the line
- ☐ Add row's ▾ offers Add section
- ☐ Add transition works before the first row, between rows, and between sections
- ☐ Row ⋯ appears only on hover, at the top-right, completely inside the row and over the first card; the first card sits near the top of the column
- ☐ Row ⋯ dragged into Stash stashes the row
- ☐ Select range: the pointer and ↑/↓/Enter/Esc both work; a range can't cross sections

**Split and join**
- ☐ A selection including the row start offers Join to previous and Split; one including the end offers Join to next and Split
- ☐ A whole-row selection offers both joins, no Split; a mid-row selection offers none
- ☐ Join is disabled when the neighbouring row is in another section
- ☐ A visual whose start word is selected moves with the selection and its end is clipped
- ☐ A visual that starts before the selection stays and ends at the split
- ☐ No visual appears in both rows
- ☐ A stage direction moves only when its start is selected
- ☐ Split places the new row before (start selected) or after (end selected) the original
- ☐ Undo reverses each of these exactly

**Narration**
- ☐ Selection grows a whole word at a time while dragging, never by letter
- ☐ Punctuation is selected with the word before it; range brackets are skipped
- ☐ Make spoken / Make stage direction follow the selection; deleting one bracket removes its pair
- ☐ Return adds a paragraph break inside the row; Backspace at the start of a paragraph removes it; Return at a row's start explains Tab instead
- ☐ Paragraphs survive Undo, split, join, Stash and Sorting (export not in the prototype)
- ☐ Tab mid-row splits at the cursor; visuals after the cursor move, one spanning it is clipped; Undo restores
- ☐ Tab at the end of a row adds an empty row; Esc leaves the text box
- ☐ Backspace at a row's start joins it above as a new paragraph; blocked at a section break; Undo restores
- ☐ Tab mid-visual, then Backspace straight away: the clipped visual gets its original range back
- ☐ Pasting text with blank lines makes one row per block; single line breaks stay as paragraphs; one Undo reverses the paste
- ☐ Pasting into a Stash saved-row editor keeps everything in that row (blank lines become paragraphs)
- ☐ The selection menu shows groups in order, hiding items that don't apply
- ☐ ⌘⇧F on a selection opens footage quick search
- ☐ At 0% thumbnails, the coverage cue shows every visual range and makes Visual Undefined stand out
- ☐ Add visual on a selection: the type menu opens; the start, end and cutaway rules match D94

**Visuals**
- ☐ + Visual appears only on rows with empty narration
- ☐ Visual ⋯ offers Trim, Change type, Stash, Comment, Delete, with no helper text; no separate comment button
- ☐ Trim opens the player with in/out handles; the trim saves
- ☐ Change type works between every pair of types
- ☐ Deleting the last visual leaves Visual Undefined
- ☐ On Camera Wide/Tight changes the framing
- ☐ No stray mini On Camera card appears (regression: the "But when he competed in Melodifestivalen this year," row)
- ☐ Dragging a card to another row keeps its trim and lands unattached; Attach to words then works; Esc cancels
- ☐ Attaching to a span that crosses two visuals: the new visual gets the full span, the earlier visual ends where it begins, and the later one starts after it
- ☐ Cards reorder by cue with a gold flash

**Footage**
r13 UI results (2026-11-13 and 2026-11-14, run in the prototype at 1280 × 800): ✓ passed · ✗ failed · ☐ not checked
- ✓ Unused clip (panel body) and used clip (panel title) open the player; panel preview plays the remembered trim, else the logged range
- ✓ Three uses of one clip (harness "Footage: 3 uses") keep distinct trims in the script (1.0–4.0, 3.0–7.5, 5.0–9.0)
- ✓ Usage pill and ‹ › go to and flash the correct visual; position text updates; the panel stays open
- ✓ Labels: pick existing, create new (appears in the label filter), remove; × does not open the preview; Escape in + Label closes it and returns focus to + Label
- ✓ Regression: select all of "The harbor light is green.", Add visual › Footage, Escape: no new visual, On Camera unchanged. Choosing a clip then one Undo restores the row
- ✓ Sort: newest (harbor, sensor, k2, ferry, blink, k1, fog, horizon, gulls), oldest and Title A–Z orders correct, including same-date tie-breaks
- ✓ Filters combine: label Channel light → 2 clips; + logger Wren → 2; + sort Title → same 2 in title order; + Used → none, with "No clips match" and Clear search and filters (clears filters, keeps the sort)
- ✓ Metadata-only queries "Dana", "Aug" and "2026" match nothing; "umbrellas" (late in a transcript) finds Harbor caretaker
- ✓ Full transcripts by default. Options › Short transcripts: unchecked by default; checking it shows excerpts and stores the preference in this browser. Show full transcript on one clip shows all 249 characters, other clips stay short; Show less collapses only it; the checkbox stays checked; with a search, the excerpt is centred on the match
- ✓ Usage radio group: one tab stop; ArrowRight, End and Home select and move focus
- ✓ Enter on a nested ⋯ inside a Footage card is not taken by the card; Enter on the card opens the player with focus inside; Escape closes it and focus returns to the card. Panel title preview → Escape returns focus to the title
- ✓ Place in script…: the gap chooser opens with 29 destinations; Escape cancels and focus returns to Place in script…; placing adds one Footage row (pill shows Used once, panel search and sort kept); one Undo removes it
- ✓ Research: none logged: the panel shows the empty state with Open in VERA Research, the top-bar count reads 0, and quick search says no clips are logged and offers Open in VERA Research
- ✓ Stash clip click opens the player (including the unavailable Night ferry clip, which shows its reason in the Stash item)
- ☐ Unavailable Footage card in the script (expand-for-recovery on click): test placement timed out
- ☐ Remembered Short transcripts after a page reload (storage write confirmed; reload not performed)
- ☐ 0% thumbnails with a real pointer: only synthetic mouseover events were possible here, so this isn't counted as a pass; keyboard focus preview not separated from it
- ☐ 1024 × 768 layout of the panel and Options: the screenshots timed out
r14 Writing results (2026-11-14, run in the prototype; synthetic keyboard, paste and edit events in a real browser page): ✓ passed · ✗ failed · ☐ not checked
- ✓ Clearing all narration in a row with three visuals: row and visuals stay (ordinals removed), the cell is empty, the hint disappears on blur; Sorting and back: still empty; one Undo restores the words and both visual ranges
- ☐ Row menu Delete row checked separately in r14 (not run)
- ✓ The hint appears only while narration is focused; Escape removes it and puts focus on the row's first visual card
- ✓ Tab at the end of a row: one new row, focus in it; one Undo removes it, redo re-adds it, Undo again removes it
- ✓ Add row above the first row and Add row from a row divider: one row each, one Undo each
- ✓ Paragraph breaks mid-row and after the final word; Tab split of the suffix moves the terminal break into the new row; immediate Backspace restores the original row (3 breaks); after an edit, Backspace joins normally (adds the join break, keeps the terminal break); Undo steps back through join, edit and split exactly
- ✓ Paste "a\nb\n\nc" at a row end: one paragraph break, one new row; one Undo returns the row to exactly its prior text
- ✓ After an earlier narration edit, pasting identical words with a blank line splits the row; one Undo removes only the paste, the earlier edit stays
- ✗→✓ A paste sometimes didn't create its row on the slow page (timing race), seen twice; fixed in r14 and passed after reload
- ✓ Repeated cue phrase: inserting a copy before both, then text between them, keeps the visual on the second occurrence (positions 112 → 117 → 122 → 128)
- ✓ Non-Latin: replacing the anchor words with 東京 大阪 京都 keeps the visual on them; inserting 札幌 before 東京 moves the cue to 東京; deleting the anchor words leaves the visual without a range rather than jumping to an earlier copy; Undo restores position 112
- ☐ Real IME composition (only the code guard exists; no IME was available to test)
- ✓ Tab through a spanning visual (⟦1 clipped), then switching Stash/Footage/Comments and 1280→1024, then Backspace: exact original text and both ranges restored, viewport stays 1024
- ✓ Backspace at the start of a section's first row is refused ("Rows don’t join across a section break.")
- ✓ Card keyboard: r13 nested-control fix kept (not retested in r14)
- ✓ Footage smoke check in r14: 9 clips, labels shown, Used once pill flashes the right visual, title opens the player; Short transcripts and the Title sort were still applied after a page reload
Residual Footage checks: ✓ Short transcripts across reload (passed in r14) · ☐ unavailable Footage card in the script · ☐ 0% thumbnails with a real pointer, keyboard focus preview separately · ☐ 1024 × 768 layout of the Footage panel and Options (screenshots time out on this page)
r15 Stash results (2026-11-14, run in the prototype with synthetic pointer, keyboard and edit events): ✓ passed · ✗ failed · ☐ not checked
- ✓ Unchecked note dropped into a paragraph by pointer drag: gold vertical text cursor shown during the drag, spoken words inserted at the cursor, note checked and still in Stash, no Return button on the row; Undo removes the words and unchecks; redo reapplies; deleting the inserted words later leaves the note checked
- ✓ Completed note with footage and brackets dropped mid-paragraph: brackets stay plain text (not direction styling), a Footage visual starts on the first inserted word, the note keeps its footage strip, nested notes/clip keep their levels and checkboxes; one Undo removes words and footage and keeps the note's prior (checked) state
- ✓ Include items below with completed child and unfinished grandchild: preview "Places 3 rows (spoken text + footage, then the items below). Notes are copied … 1 clip or saved row moves out of Stash." Placing skips the completed child, copies root and grandchild, moves the clip; one Undo restores; a completed root places the same way
- ✓ Return to stash on untouched copies: a manually checked root stays checked; a grandchild checked by the insertion unchecks; no duplicate saved rows; manual uncheck/recheck after a placement keeps it checked on return
- ✓ An edited copy has no Return to stash; row ⋯ › Stash says "Saves this row in Stash (its link to the note ended)" and creates a saved row while the note stays checked
- ✓ Root and nested clips align with their level's checkbox lane (x within 1px)
- ✓ Destination filter: "harbor" narrows to matching rows and keeps a valid selection; no match shows "No destinations match" with Place disabled; Escape cancels and focus returns to the item's ⋯ (focusin observed)
- ✓ Deleting a Stash section moves its items, in order and nesting, to the top; one Undo restores
- ✓ Unavailable Stash clip: reason, logged range and placeability shown, no Play; an available clip still plays
- ✓ Smoke: narration hint, Footage panel, panel preview
- ☐ Group editor Save/Cancel, close confirmation and one/zero-member cases (code unchanged; no group in the current sample)
- ☐ Completed-note gold drag feedback with a real pointer (only synthetic events)
- ☐ IME, screenshots and real-pointer checks remain unavailable in this environment
r16 results (2026-11-14, run in the prototype with synthetic events): ✓ passed · ✗ failed · ☐ not checked
- ✓ Sorting: opening a comment expands its own row (aria-expanded) and scrolls it near the top; opening another collapses the first
- ✓ Replacing a commented shot (Change type › Still Image): the comment moves to Orphaned with "Shot replaced" and saved context naming the original clip; one Undo reattaches it
- ✓ Mark all reviewed with Dana selected and Show removed off: all 6 pending changes acknowledged; simulated failure: "Couldn’t save your review. Nothing was marked reviewed." with 6 still pending; with the boundary frozen, a later arrival stays pending (7 → 1) with "Anything later stays pending"
- ✓ Sorting Accept and Discard all both leave 6 pending
- ✓ D71: with Jonah selected, "Your later edit replaced 1 unreviewed change by Jonah Reyes in …"; chip shows 3; after Mark all reviewed, chips and line are gone
- ✓ Top bar: 1280 × 800 one row, title not clipped; 1024 × 768 two rows, title full width, Options and panel buttons on row 2, nothing overlapping
- ✓ Persistent Undo: "Nothing to undo in this session" at start (disabled); after an edit "Undo Edit narration (Cmd/Ctrl+Z)"; the ▾ menu lists it first above earlier-session entries; clicking Undo reverts exactly and the label returns to nothing
- ✗→✓ Card accessible names after Add row named the row above (seen before the fix, and already off by one for later rows); after the fix every card name matches its row after insertion, Undo, stashing a row and placing it elsewhere
- ✓ Compact fixture: Contributions bar, toast and player don't overlap at 1024 × 768
- ☐ Comment Resolve/Reopen/Reattach permissions (product question)
- ☐ Real-pointer checks (0% hover, drag feedback), IME composition and screenshots remain unavailable here
r17 results (2026-11-14): method in brackets. ✓ passed · ✗ failed · ☐ not checked
- ✗→✓ 0% keyboard focus on "Harbor caretaker" (Footage) and two Still Images ("Ticket window…", "Recipe card"): no preview in r16 (no image of their own); in r17 each shows its thumbnail tile, and blur and Escape dismiss it [programmatic focus/blur; first run was after moving the slider to 0%]
- ✗→✓ Fresh load with 0% saved: before the fix nothing previewed until the slider was moved (found by review); after the fix, mouseover on Harbor caretaker opens the preview and mouseout closes it [reload with saved 0%; synthetic mouseover/mouseout]
- ✗→✓ Focus on an offscreen card (Tab scrolls it into view): the preview flashed for under 100 ms then closed (found by review); after the fix it stays open for the whole 1 s sample on both the Recipe card and Harbor caretaker, sits beside the scrolled card, and blur closes it; a hover preview still closes on scroll [programmatic focus() from the top of the script, sampled every 100 ms]
- ✗→✓ Card-to-card focus (fast Tab): the new card's preview closed about 160 ms later (found by review); after the fix it stays open for the full 0.8 s sample, both between two visible Still Images in one row and from Harbor caretaker to an offscreen Still Image; moving focus off the cards (to Undo) closes it [programmatic focus() sequences, sampled every 100 ms]
- ☐ On Camera at 0% doesn't preview (existing behaviour: its thumbnail is the presenter frame)
- ☐ Missing-image visual at 0% (no "Image file needed" visual in the current sample)
- ✓ Row ⋯ › Delete row: confirmation, deletion, one Undo restores it in place with identical text [UI clicks]
- ✗→✓ Unavailable clip placed from Stash: r16 showed the reason but no recovery; r17 shows Replace clip… and Open in VERA Research; Replace clip… → choosing a clip clears the warning; one Undo restores the unavailable clip [UI clicks]
- ✓ Two-row range → Stash group; Place group back (2 ordinary rows, all 6 visuals kept); one Undo returns the group; another Undo restores the rows in place [UI clicks + keyboard range]
- ☐ Group with nested notes or attached footage (none in the sample)
- ☐ Real pointer hover and native drag feedback, IME composition, screenshots (not available in this environment)
Independent Chrome review of r17 (Matthew, native keyboard and pointer): ✓ passed
- ✓ With 0% saved, native Tab and real pointer movement show the thumbnail on the Recipe card (Still Image) and Harbor caretaker (Footage); Tab away or moving past the card dismisses it
- ✓ Row ⋯ › Delete row, then one toolbar Undo, restores the short row and its On Camera visual
- ✓ Night ferry clip placed from Stash shows its recovery choices; Undo returns it to Stash
- ✓ Cold open group, Include items below: two unfinished notes copied, completed note skipped, Gulls over the pier moved, horn attachment kept; one Undo restores hierarchy, attachment and completion marks
- ✗ (fixed r18) After the delete and toolbar Undo, the delete toast still offered Undo
- ✗ (fixed r18) The placed Night ferry card's accessible name ended "Image file needed on this computer"
r18 results (2026-11-14, prototype; UI clicks and keyboard events):
- ✓ An older narration edit, then Delete row on "The harbor light is green", then toolbar Undo: row and On Camera back; toast reads "Undid Delete “The harbor light is green”." with no Undo; the toolbar now offers "Undo Edit narration", and the older edit is still in the text
- ✓ Same sequence with Cmd/Ctrl+Z: same result
- ✓ Same sequence with the toast's own Undo: one copy of the row restored, "Restored … with its discussions attached as before.", toolbar still offers "Undo Edit narration"
- ✓ Night ferry placed from Stash: accessible name ends "Source unavailable · the video was removed from this project’s media"; Replace clip… and Open in VERA Research still shown
- ☐ Genuine IME composition and native drag feedback (hands-on check still pending)
r19 pass 1 results (2026-11-14, prototype; scripted clicks, value changes and synthetic pointer drags — not native input): ✓ passed · ✗ failed · ☐ not checked
- ✓ Audio: row ⋯ on a narration row shows Add audio bed starting in this row; the picker opens on the row; Escape closes it with no bed, no Undo entry, focus on row ⋯
- ✓ Audio: picking Harbor Tide Bed adds M3 with its panel; Source trim 0 → 0.5 then Fade out 2 → 2.5; toolbar label read "Undo Change source trim of M3", then "Undo Change fade of M3"; three Undos: fade back to 2.0, trim back to 0.0, then M3 removed, label "Nothing to undo in this session"
- ✓ Quiet piano in Sorting: start and end marks on s16/s18; details show its start and end rows
- ✓ Reselect range: shown on footage card hover and in the visual ⋯ menu; selecting words opens a confirm; Escape keeps the brackets unchanged with no Undo entry and focus back on the card
- ✓ Partial overlap ("generous … traveler" across visuals 1 and 2): Set range made room under D113 (visual 1 resumes after); one Undo restored ⟦1 1⟧ ⟦2 2⟧ ⟦3 3⟧
- ✓ Exact match (visual 2 → visual 3's words): Swap ranges offered and focused; after the swap the cards read 1 Still, 2 Still, 3 Footage (cue order); footage trim note unchanged ("8.0s of footage remains"); one Undo restored order and brackets
- ✓ Visuals-only row: a stashed Still dropped into Harbor caretaker arrives with no Attach to words and Hold 4.0 s; dragging it below the Footage reorders (one Undo); Hold 6 committed with Enter; −2 refused ("Kept 6.0 s")
- ✓ Match audio duration: offered only once a bed spans the row (fixture); checking it follows M3 (132.0 s, read-only); with two cues a chooser appears and M4 can be picked; removing M4 falls back to 6.0 s with a note; Undo restores the match
- ✓ Undo to the start restores s01's three visuals, brackets and Harbor caretaker's single Footage card
- ✓ Row ⋯ and first visual ⋯: row ⋯ at least 12 px above the first card at 1280 × 800 and 10 px at 1024 × 768; each hit test lands on its own button
- ✓ No coverage-cue lines render at 0% thumbnails
- ☐ Footage trim after a move between two visuals-only rows (existing D87–88 behaviour, not re-checked in r19)
- ✗→✓ Toolbar Undo label after audio Undo (reported stale by review). After the fix, one step per check: add → "Undo Add audio bed M3…"; trim 1 → "Undo Change source trim of M3"; fade 2.5 → "Undo Change fade of M3"; Undo → "Undo Change source trim of M3" (1 bed); Undo → "Undo Add audio bed M3…" (1 bed); Undo → "Nothing to undo in this session" (0 beds)
- ☐ Slider Undo label with real ArrowRight keys (hands-on)
- ☐ Native pointer drag feel, IME composition
Codex observations of r19: ✓ keyboard trim/fade with correct Undo labels; ✓ separate row/visual ⋯ targets at 1024 × 768.
r20 pass 2 results (2026-11-14, prototype; scripted clicks, keyboard events and simulated pointer events — not native pointer):
- ✓ Script Footage card click plays that use's trim and shows a Trim button; Trim opens the controls (aria-expanded true, label Hide trim)
- ✓ Three uses of Harbor mouth play 1.0–4.0, 3.0–7.5 and 5.0–9.0 s; the panel preview opens paused with trim open on the remembered 5.0–9.0; Clear out in the panel → a later placement plays 5.0–10.0 while the three uses keep their trims
- ✓ Short transcripts checkbox under the panel search, checked from the stored preference; Options control gone
- ✓ Timed clip at logged bounds: opening excerpt. Trimmed 15.0–20.0 s: "…The old schedule is still pinned behind the glass. I copy the routes by hand on a clean sheet,…" with note; updated live while the in point moved (7.4 s showed later speech); Show full transcript/Show less toggles one clip, checkbox stays on; 9.0–13.0 s: "No speech between 9.0 and 13.0 s." with Show full transcript
- ✓ Harbor mouth trimmed (no timings): full transcript with "A trimmed excerpt isn’t available…" note
- ✓ Clicking the label Tide filters the panel to Harbor mouth, no player, focus on the label control; Any label clears it (10 clips)
- ✓ Place in script: a pointerdown outside closes it with no placement or Undo entry; inside keeps it; Escape closes
- ✓ Rename Harbor caretaker's placement to "Caretaker at the window": card shows the name and "Source: Harbor caretaker"; card and comment-marker names use it; one Undo entry; Escape cancels; Undo restores; offered for Still Image, not On Camera
- ✓ 0% hover/focus previews as listed in the decisions build notes (simulated events)
- ☐ Native pointer hover at 0% (Codex)
- ☐ Production transcript timing availability/granularity
Codex observations of r20 (Chrome): ✓ panel click opens the player with trim open; ✓ Short transcripts checkbox in the panel; ✓ native pointer hover at saved 0% on preloaded Harbor caretaker.
r21 pass 3 results (2026-11-14, prototype; scripted clicks):
- ✓ Cold open, Include items below: preview and result 4 rows in outline order (Cold open with its horn Footage, Ask Dana (checked), Check the crossing board, Gulls over the pier moved); notes stay in Stash, checked; one Undo restores rows, hierarchy, footage strip and original checks (Ask Dana stays checked)
- ✓ Add clip renders below Add note
- ✓ Night ferry: Find original › verified fixture match restores it (logged 0:12–0:20 kept) as one Undo entry; Undo makes it unavailable again; Replace clip › Harbor mouth replaces it; Undo restores
- ☐ Wrong-file rejection message and Cancel focus return (built; checks timed out)
- ✓ Comments list shows "Gap before “When the harbor… nobody has to wait alone.”"
- ✓ Permissions and Mark all reviewed scope unchanged from r16 (not retested)
- ☐ Gold flash at the destination (built; not observed)
r22 results (2026-11-14, prototype; scripted clicks; the dirty edits were applied to the editor's model directly because scripted typing into the saved-row editor didn't reach it):
- ✓ Root saved row s06 starts at x 976, the checkbox lane is 977 and the root clip is 976
- ✓ Opening saved row s06 shows only that row (no other rows, no section headings) with Stash open
- ✓ Clean switch s06 → s08 opens s08 directly
- ✓ Dirty switch: the prompt appears with the pending item; Keep editing stays on s08 with its edit and clears the pending switch; Don't save discards s08's edit and opens s06; Save stores s06's edit (one Undo entry, "Saved the row in Stash") and opens s08
- ✓ (Codex, Chrome) Wrong-file rejection shows "Nothing changed"; Cancel returns focus to Find original…
- ✓ (Codex, Chrome) Real typing in a saved row → dirty-switch prompt; Keep editing keeps the draft; Don't save opens the requested row
r23 results (2026-11-14, prototype; synthetic pointer drags, rendered-state sampling every 150 ms):
- ✗→✓ Inline drop of "Hold on the bell rope…" into s05: before the fix, a whole text span (including surrounding words) was tinted or nothing flashed; after it, gold overlays sit on exactly the 9 inserted words ("Hold … line.") and are removed after about 1.25 s
- ✓ Branch drop of Cold open between rows: 4 rows inserted; all four rows' text turned gold (rgba 242 220 156) and then cleared; one Undo removed them
- ✓ Footer reads "Everyone can Resolve, Reopen and Reattach comments."

r24 (2026-11-15, prototype; synthetic events):
- ✓ Still Image in s01 shows Reselect range on hover and on keyboard focus
- ☐ Reselect in ⋯ menu + confirm/Undo/cancel on a Still; trim-editor brackets (drag, ← →); playback scope with Trim open/closed; slider slow-drag/keys; ferry short excerpt "it goes, and the ferry is" and update after a new trim; full-mode highlight; single comment count; row labels; Add note ▾ Add clip; group placement skipping completed (mixed, all-checked → disabled, attached footage, Undo); 6 s popups with hover pause; 1024 × 768 layout — built, not yet checked (usage limit)
r25 Pass 1 (2026-11-15, prototype; synthetic pointer/keyboard events and programmatic selections — not native input):
- ✓ Opening Still (Recipe card): ⋯ stays at the same position with and without hover; Reselect range is a separate button below the header with no overlap; clicking ⋯ opens the menu (Rename…, Reselect range, …) and doesn't start Reselect — 1280 × 800 and 1024 × 768
- ✓ ⋯ › Reselect range, focus the active control, Escape: mode ends, brackets unchanged, "Reselect cancelled…", focus returns to ⋯ (1280) / the Reselect button (1024)
- ✓ Confirmation: 22 highlight boxes across 3 wrapped lines for a 22-word span; old brackets unchanged while open; highlight cleared on Set range/Escape
- ✓ Recipe Card shorten (Still 1 → "The cook … the room."): 1⟧ moves before "One note", ⟦2 unchanged, "↩ OC resumes", no Still Image 1 resumes; one Undo restores the original sequence
- ✓ Cutaway inside Still 1 (Still 2 → 11 words in Still 1): "Still Image 1 resumes" correct; then shortening Still 1 before it: the confirmation names "Recipe card no longer resumes after it"; Escape keeps the prior sequence
- ✓ Dialogue Footage (Harbor mouth in the opening row): Reselect → 9-word span highlighted, Set range moves it and Still 1 resumes after; one Undo restores all brackets
- ✓ (Codex, Chrome) ⋯ click; Escape → focus on ⋯; one-word commit + Undo at 1280; compact Escape keeps brackets
- ✗→✓ Keyboard Reselect (Codex repro): after the fix, 6 word-extensions show "1…6 words selected · Enter to review", with no confirmation and no selection toolbar; Enter opens "6 words" with 6 highlight boxes; Set range commits exactly "The cook who wrote it had" (6 words); Undo restores. At 1024 × 768: 8 extensions, no toolbar, Enter → confirmation, Escape cancels with the brackets unchanged and focus on ⋯ [synthetic keyup + Selection.modify]
- ✓ Pointer selection: release opens "10 words" with 10 highlight boxes, no toolbar; extending during the confirmation changes nothing; Set range commits 10 words
- ✓ (Codex, Chrome) r25 six-word keyboard review, Set range, one Undo at 1280; compact Escape
r26 Pass 2 (2026-11-15, prototype; scripted clicks/keys, simulated media and fixture/simulated word timings):
- ✓ Two uses of Harbor mouth: the cards show different in-trim words; extending use 1's out point to 6.0 s updated only use 1's transcript; the panel preview trim (5.0–9.0 s) was unchanged
- ✓ Player opens 520 px wide at 1280; the transcript box grows up to 210 px
- ✓ Panel, Short transcripts on: Channel light (logged 1.2–7.4 s) shows "it goes, and the ferry is" highlighted; caretaker clip with no trim shows the opening with "…" and Show full transcript; whole clip explicitly selected shows all 307 characters highlighted, "Whole clip selected", no button, in both modes
- ✓ Quiet piano: ⌈♪ in "The amber lantern…" and "♪ Quiet piano⌋" in "A chalk crescent…", visible; no purple rail; new cue "Harbor Tide Bed": Undo label, trim label, panel name and accessible names show no Mn IDs
- ✓ Hide completed hides checked Gulls; Cold open branch with all items checked: Place in script… disabled, grey, "every item here is completed"
- ✓ (Codex, Chrome) Hide completed hides checked Gulls; mixed Cold open places 2 rows with horn footage + one Undo; Place disabled for all-completed branch; exact Channel light short text; wider player opens at 1024 × 768
- ✗ (Codex) 1024 × 768 with Contributions bar: bar covered/intercepted the trim transcript; player extended below the frame → fix built (post-render clamp to frame, above the bar, internal scroll)
- ☐ Player inside frame and above the bar at 1280 × 800 and 1024 × 768 — not verified (preview unresponsive to checks this session)
- ☐ Overnight regressions; six-word keyboard smoke in r26 — not run
r27 (2026-11-15, prototype; scripted clicks/keys and synthetic mouse drags — no native pointer; simulated media):
- ✓ Workshop recording player: rows don't overlap at 1280 and 1024; with the Contributions bar visible at 1024 the player is at 277–717 × 12–647, inside the frame and above the bar (top 655), and scrolls internally
- ✓ Trim drag (synthetic mousedown/move on the in handle): player top stayed at 12 px through 8 moves and after release
- ✓ Paper Lanterns: "Each one…show through." and "board…the" each give Still 1 · On Camera · Still 2 with no extra "OC resumes"; one Undo restores the original brackets
- ✓ Quiet piano: no row badge; ♪⌋ in text; "♪ Quiet piano ends" shown outside the narration on focus and hover
- ✓ Harbor door ⋯ › Add audio starting at this row’s start: Harbor Tide Bed face on the row, end in the next row, hold stays 4.0 s, Match audio duration offered; one Undo
- ✓ Footage card: header above a full-width transcript; no arrows or trim notes; "Used 3 times" lists rows 25–27 and each jumps there; Place in script… appears on keyboard focus, places one visuals-only row, one Undo
- ☐ Real framing change across a row break; narrow panel width; reload check of the cue label
- ✓ (Codex, Chrome) Workshop: no overlap; real out-handle drag 22.0→18.6 s (1280) and 18.2 s (1024) with bounds unchanged, restored; three-use list; keyboard gap placement + Undo; Harbor Tide Bed on Harbor door keeps 4.0 s and continues into "Rain gathers along the window"
r28 (2026-11-15, prototype; synthetic pointer events):
- ✗→✓ Pointer drop of Workshop recording on the line below Harbor door: before the fix, no target (the seam strip covered the line); after, the ghost reads "New visuals-only row here" with a 6 px gold line, and one row is inserted between Harbor door and Rain gathers; one Undo removes it — title drag at 1280, thumbnail drag at 1024
- ✓ Drop onto Harbor door's visual: "Add to this row", the visual is added; one Undo
- ✓ Harbor door ⋯ › Add audio: picker reads "starts at the start of “Harbor door”"
- ☐ Ending a cue at a visuals-only row boundary: not possible in the prototype model; moved to working-app acceptance
r29 (2026-11-15, prototype; scripted fixtures through the component plus rendered-DOM reads at 1217 × 747; no screenshots, no real pointer):
- ✓ Harbor mouth (trim 5.0–9.0 s): before, during "mouth" and after clearing, identical in both modes — Short: only "just after the turn, … starts to slide"; full: whole transcript with that passage marked; "Used 3 times" pill kept
- ✓ No [data-qpline] stripe in Authoring on a clean load; Quiet piano ⌈♪ … ♪⌋ brackets present
- ✓ "♪ Quiet piano ends": shows on keyboard focus, clears after scripted .blur(); shows on pointerover, clears on pointerout
- ✓ Raincoat still → whole row: both On Camera cards gone (one card left); narrowed back to its words, then whole again: no leftover OC; narrowing gives OC · Still · ↩ OC resumes; 3 Undos restore the original
- ✓ Workbench, Still 1 from "little tin…": full On Camera card · Still 1 · On Camera · Still 2 (no compact chip first); one Undo restores
- ✓ Chalk crescent split before "The shape simply marked…": second row is one On Camera card (the original, Wide) · slate still; one Undo restores the row count and visuals
- ✓ Paper Lanterns "Each one…through." and "board…the": On Camera · Still 1 · On Camera · Still 2, ranges contiguous; one Undo each restores
- ☐ 1024 × 768 and 1280 × 800 frame checks; native-pointer Reselect and Tab split; a newly added cue's brackets and label
- ✓ "A folded letter…": dragging Still 1's ⟧ to the last On Camera word removes On Camera (Still 1 · Still 2); Reselect over the same words does the same (scripted; superseded by the review failures below)
r29 review failures (2026-11-15; open for implementation in one production range-edit issue):
- ✗ Folded Letter: dragging the bracket removed On Camera, but Undo stayed disabled
- ✗ Folded Letter: shortening the still by one word moved the neighboring still's start
- ✗ Amber Lantern and Paper Lanterns: confirming the highlighted selection created an Undo entry while the displayed brackets stayed put
Production acceptance for that issue:
- ☐ After a bracket drag, keyboard bracket move or confirmed Reselect, the displayed brackets, cards and On Camera passages match the confirmed edit
- ☐ Shortening a visual by one word changes only that visual's end and hands the freed word to On Camera; the neighbour's start doesn't move
- ☐ Removing On Camera by a bracket drag creates one Undo entry; that Undo restores On Camera with its framing
- ☐ One Undo restores the full prior sequence (every range, On Camera passage and framing, card order) on Folded Letter, Amber Lantern and Paper Lanterns
- ☐ The first On Camera in each row is full-size, even after a still; a compact card appears only for a return after an intervening cutaway
- ☐ Untrimmed clip during a search shows the ordinary excerpt (code path unchanged; not exercised)
- ☐ Adding Footage opens quick search with the cursor in the box; typing filters on title and transcript
- ☐ Clips whose transcripts match the selected words appear first, with the matching words listed
- ☐ Enter in the search box picks the top clip; ↑/↓ move through results; Esc closes
- ☐ Unused clips only by default; Show used reveals used clips, marked as used
- ☐ Works smoothly with 100+ clips
- ☐ Show footage panel lists all footage with a detailed search and its own thumbnail slider
- ☐ Clicking a used clip scrolls to its placement; a clip used 3 times steps 1/3, 2/3, 3/3
- ☐ Dragging a clip from the panel into a row lands it unattached
- ☐ Re-trimming a clip, deleting that instance, then placing the clip again uses the new trim; other instances keep theirs
- ☐ Unavailable clips place and show recovery options

**Sections (script)**
- ☐ Add section inserts a break between rows with an inline title field
- ☐ A break can't be placed mid-row
- ☐ Section ⋯ › Rename works; Delete break merges into the previous section; Undo restores it
- ☐ Exported markers match section titles and positions

**Stash**
- ☐ The count and header breakdown match after every add, delete, place and return
- ☐ Notes keep literal brackets through save, place, return and export
- ☐ Placing a note creates spoken text and checks the original; Hide completed works
- ☐ An untouched copy returns and unchecks the source only if that insertion checked it
- ☐ Attached footage: Replace keeps the old clip as a child; Detach and Undo work; blanking the text keeps the footage
- ☐ Dragging a note into a row shows a gold text cursor between words, never inside a direction
- ☐ Dragging a clip onto the visuals side shows a gold line between cards
- ☐ The drag ghost never covers the gold text cursor or insertion line
- ☐ Stash words: plain words become a note; words with cues become a saved row
- ☐ Completed notes show the gold drop line when dragged (D83 retest)
- ☐ Saved row and group editors: Save, Cancel, ask on close, add and remove rows in a group
- ☐ Returns go to the original place, or the top of Stash when it's unclear
- ☐ Rename a Stash section; deleting one moves its items to unsorted at the top, keeping order and nesting
- ☐ Delete is one click, and Undo restores it

**Comments**
- ☐ Yellow words open their discussion
- ☐ In Sorting, comments show in the sidebar (Show footage hides; Footage switches to Stash); clicking one expands its row and scrolls to it; clicking another collapses the first

**Sorting**
- ☐ Accept/Discard work; Undo history survives Sorting
- ☐ Show contributions hides in Sorting; Stash stays

**Show contributions**
- ☐ Chips use first names; Since last reviewed omits You
- ☐ The green pill appears only when the bar opened itself
- ☐ Removed rows show in the Reconciliation format with a typed visual
- ☐ Show removed default follows the range
