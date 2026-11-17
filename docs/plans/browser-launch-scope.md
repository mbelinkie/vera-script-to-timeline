# Browser launch scope: the first version of VERA authoring

What the first browser version does, what waits, and what is not planned. It
is a cut of the accepted design, **S03 Integrated Authoring r29**
([accepted on #125](https://github.com/mbelinkie/vera-script-to-timeline/issues/125#issuecomment-6905736398),
files in [`docs/prototypes/issue-125/r29/`](../prototypes/issue-125/r29/)).
Nothing here changes how an accepted feature looks or behaves; a feature that
waits is simply absent, with no dimmed button in its place. § numbers are
sections of the r29 spec, D numbers are its design decisions, r numbers are the
dated passes in the decisions file, # numbers are the issues that build each
line.

**Status: proposed, waiting for Matthew's yes (#377).**

## First version: one writer, on your Mac

| # | What you can do | Design | Built by |
|---|---|---|---|
| 1 | Open the editor in a browser on your Mac. No sign-in. Start a script or open one; it saves as you work and is there after a reload. | — | #64 (saving: #380, done) |
| 2 | Aa size and Thumbnail size sliders, remembered in that browser. | §1, D33, D102 | #64 |
| 3 | Two-column rows. Add a row at a divider, delete a row, drag rows to reorder, select a range and delete it. | §2, D29, D101, D42 | #65 |
| 4 | Type, delete and paste plain text in narration. Visuals stay on their words. Erasing all the words keeps the row and its visuals. | §3, D135, D139, D119 | #65 on #580 |
| 5 | Stage directions: Make spoken, Make stage direction. | §3, D3, D68 | #65 (#341, done) |
| 6 | Paragraphs inside a row (Return). Split a row (Tab, or from a selection) and join rows (Backspace, or from a selection). | §2, §3, D97, D114, D115 | #65 on #581 (#579, done) |
| 7 | Sections: add, rename, delete a break. | §6, D106 | #65 on #582 |
| 8 | Undo, with the top-bar label and recent-actions menu, for the current session. | §1, D34 | #65 |
| 9 | Select words, Add visual, pick a type. Cards stack in cue order. Delete a visual; change its type. The kinds you can add are Onscreen Placeholder, Need to Find and Visual Undefined; On Camera appears by itself (line 11). | §3, §4, D93, D94, D100 | #67 on #578 |
| 10 | Footage, stills and web captures already in the script show as cards and can be re-ranged, moved to another row and attached to words, or deleted. | §4, D87, D88, D113 | #67 on #578 |
| 11 | Range brackets: drag a bracket or Reselect range. On Camera fills every word no visual covers, with Wide or Tight. | §4, D190, D192, D193, r19, r25 | #66 (#577, #119, done) |
| 12 | Rows with no narration: + Visual, several visuals in a chosen order, each with a hold in seconds. | §4, D96, r19 | #67 on #585 |
| 13 | Build the timeline from the saved script: one command writes the saved script to a file, then the existing Prep Media and build commands run as they do today. | — | #64 (build: README "One command") |

Two things to know about this cut:

- **Clips still enter a script the way they do today**, through the agent
  command for logged Research clips (#383). The editor shows them and lets you
  place and retime them (line 10), but you cannot search for a new clip inside
  the editor yet. This is the line most worth moving up if you want it; it adds
  #80 to the first version.
- **It runs only on your Mac.** The saving service exists only as a local one
  today. Putting it online comes with sign-in (#72).

## Later: accepted, waiting

| What | Design | Why it waits | Built by |
|---|---|---|---|
| Find and add a logged clip in the editor; Footage panel; clip player and trim | §5, D39, D98, D99, D125–D134 | Needs Research clip search, usage and transcript timing (#589, #591) | #80 |
| Your own files (stills, local footage) | §4 | Import screen not built; the backend is done (#381) | #85 |
| Web capture as a visual you add in the editor | §4, D93 | Editor control not built; the build side is done (#394) | #319 |
| Stash panel, Stash words, Stash a visual, Sort rows | §7, §9 | Three saved-document operations still open (#373, #583, #584) | #616 |
| Music cues and transitions at dividers | §2, D101, D191, r19, r26–r28 | Cue anchors and first-row transitions still open (#574, #586, #587, #590) | #617 |
| A name for one placement of a clip | r20 | Small; follows the cards | #588 |
| Comments | §8 | Needs accounts | #74 on #72 |
| Show contributions | §10, D108 | Needs accounts and more than one writer | #356 on #72, #73 |
| Sign-in, sharing, two people editing at once | — | Needs the service online | #72, #73 |
| Undo that reaches back into earlier sessions | §1, D34 | Needs saved history in the app | #75 |
| Section markers on the Resolve timeline | §6, D106 | Sections save in the first version; markers are a build change | #69 |
| Prompter export from inside the editor | — | The command works today; the button waits | #68 |
| Preview and Build buttons | — | Needs the Mac companion paired to the app | #70 |
| The 0% thumbnail coverage cue | §3, D118 | A trial you have not yet adopted | #66, once you decide |

## Not planned

Left out by the accepted design itself (spec §11). No issue owns these, on
purpose: rich-text paste from Google Docs (D121) · spell check · word count
and estimated length · comment-only access · other Options contents (D79) ·
reconnecting footage from Stash · music beyond #326 · motion and framing.

## Build order

#64, then #65, then #66 and #67 side by side. #580, #581, #582 and #585 are
saved-document operations with no screen of their own; they can run now, in
parallel with #64. #578 has an open pull request (#615).
