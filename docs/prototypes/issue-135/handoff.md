# Issue 135 — S03 v3 authoring artifact handoff

Status: **Producer accepted on 26 September 2026**.

Acceptance evidence: the Producer responded exactly **`Issue #135 S03 v3 artifact accepted`** after completing the checklist below.

## Exact artifact

| | File | Bytes | SHA-256 |
| --- | --- | --- | --- |
| **Handoff export** | `S03 v3 authoring artifact - issue 135 export v2.dc.html` | 3,943,452 | `c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea` |
| Reviewed source in Claude (final) | `S03 v3 authoring artifact.dc.html` | 3,505,013 | `01c5f5bb64d2d75831b8c83b652b529b5db15843d83b6a2367156f136f4c0bd7` |
| **Invalid and superseded — do not use** | `issue-135/S03 v3 authoring artifact - issue 135 export.dc.html` | 717,602 | `0a8ddef96b6627264a9ecf06a0797a59471423fc3654d9ffe6304b1497ab5c6a` |

The first export was invalid because its thumbnails were not embedded; all 10 thumbnail areas failed to load. It is not retained or used as evidence.

## Source and provenance

- Starting designs: accepted S03 v2 `Script to Timeline - Two-Column Authoring S01-S03 v2.dc.html` (`632cfce2…2005535`) and the accepted #127 pilot (`4d0f9217…77eca`).
- Not modified by this issue: accepted S03 v2, the #127 pilot, #123, S05, production contracts, fixtures, goldens, or generated types.
- The handoff export is a single file generated from the final reviewed Claude source. Nothing in the design was edited after export.
- Row 8's connection-line code matches `99 - Baseline - S03 v3 authoring artifact before row 8 connector trial.dc.html`; the lane trial was reverted.

### Non-visible export-enablement changes

1. A hidden `<template id="__bundler_thumbnail">` supplies the small S03 preview icon required by Claude's export tool. It renders nothing.
2. The seven `assets/…png` references were replaced with the byte-identical image data. Assignments are unchanged; the artifact converts the data into in-page links at load time.

| Thumbnail | Bytes | SHA-256 (original = embedded) |
| --- | --- | --- |
| harbor-mouth-wide.png | 354,849 | `32e0eb2f…3aaad10` |
| sensor-housing-waterline.png | 375,832 | `3326cd82…caac036f` |
| channel-light-ferry.png | 345,923 | `75d311e2…2b8774` |
| channel-light-second-blink.png | 329,828 | `63356ff4…6f12f4c` |
| fogged-lens-clearing.png | 319,652 | `99c77956…6aa71c9` |
| horizon-returns.png | 303,611 | `ef8feed1…3a0bbad` |
| gulls-lift-off.png | 389,730 | `93e6ecee…2d65d5f1` |

## Migration matrix: 22 rows

“Harness-only” means the state appears only when a review-harness Example button is on. It is never saved and never part of the seed.

| Row | v3 content in this export | Status vs v2 |
| --- | --- | --- |
| 1 | Visual-only opening placeholder, set to 3.0s (`3.0s needed`, plain number). Diagonal stripes, same as Need to Find. Face text limited to two lines with an ellipsis | Retained; styling adapted |
| 2 | On Camera (Wide) plus transparent Graphic 1 lower third | Adapted |
| 3 | Footage 1 (quiet) | Retained |
| 4 | Visual-only footage, Full sound, transcript on the card face | Retained |
| 5 | Footage 1, Footage 2 | Retained |
| 6 | On Camera, cutaway, then `On Camera resumes` (Tight return) | Retained |
| 7 | On Camera (Tight), cutaway, return | Retained |
| 8 | Footage 1; Graphic 2 across the Footage 1→3 cut; Footage 3; Footage 4. **M1 starts** on “From the western”. Connection lines match the baseline | Adapted |
| 9 | Footage 1 (quiet). M1 continues | Adapted |
| 10 | Line-chart placeholder. **M1 ends** on “back to the footage.” (explicit out-word, crosses three rows) | Adapted |
| 11 | Web Capture 1 through “communications failure.”, then On Camera (Wide) | Adapted |
| 12 | Still Image 1 `Archival photo · piling before installation`, Slow push. *Harness-only:* `Image file needed on this computer` with red outline, Locate file, and a readiness entry | Adapted |
| 13 | Web Capture 1 plus transparent Graphic 2. Highlight cue shown as `Highlight cue on the word “50,000”` | Adapted |
| 14 | Three sequential placeholders | Retained |
| 15 | On Camera card under transparent Graphic 1 (quote), then full-frame Graphic 2 | Adapted |
| 16 | Full-frame Graphic 1 (table), highlight cue on `west` | Adapted |
| 17 | Need to Find 1 through “reading changed.”, then On Camera (Wide) | Adapted |
| 18 | On Camera. *Harness-only:* **M3 EXAMPLE** collaborator cue `Keeper’s Notebook Piano`, `Audio file needed on this computer` on a red-outlined rail. Narration and row are not turned red | Retained plus harness example |
| 19 | On Camera (Tight). **M2 starts** on “The lesson”. Duration-driven, no out-word. Narration and direction text unchanged | Adapted |
| 20 | Visual-only ending placeholder. **M2 ends by duration**: rail fades out ~3.9s after “ends.”, no end tick. Card: `Holds through the M2 tail · ~3.9s` | Adapted |
| 21 | Undefined visual. The audio picker opens above its button when needed, so every option is reachable | Retained |
| 22 | Blank row, undefined visual | Retained |

The clean seed contains **M1 and M2 only**. The next new audio bed is **M3**.

## Normal controls

| Control | Status in this export |
| --- | --- |
| S01 entry, narration writing, + Row / + Section | Retained |
| Visual insertion, reordering, range drag / keys / right-click | Retained |
| Range inspection by hover and focus | Retained |
| Media actions, delete, audio-conflict dialog, undo / redo | Retained |
| Settings (presenter picture and name, text size), thumbnail slider including 0% | Retained |
| Viewport 1280×800 / 1024×768, column divider | Retained |
| **Add audio** (button, row menu) and **audio picker** (library, `Log a local audio file…`) | Adapted: Audio terminology; picker flips above its button; full keyboard support |
| Audio bed ⌈♪ ♪⌋ anchors, rail, label, trim/fade details | Retained. Duration-driven end added for M2 |
| Locate file for a cue or image known to the project but missing here | Added as harness examples. A name or size mismatch requires **Use this file anyway** or **Choose another file…** |
| **Check readiness** | Adapted: count remains on button; list links each issue to its row; local files are a separate `Files needed on this computer` group |
| Top-bar status | `✓ Saved in this browser` (prototype stores locally; no project sync) |
| Harness: `Locally modified preview · Reset to clean seed` | Added; shown only when saved content differs from the seed |

### Exercised authoring interactions on the exact export

- Edited narration, then used Undo and Redo; the text moved backward and forward as expected.
- Inserted a row, observed the document grow from 22 to 23 rows, then undid the insertion and returned to 22.
- Moved a timed range endpoint with the keyboard; the narration anchor changed and the focused endpoint showed a visible 2px solid outline.
- Used a visual card's pointer control to focus its narration range, then right-clicked the start endpoint and confirmed the exact-range menu exposed Change start/end word and derive media/word endpoint actions.
- Used row 5's visual move menu to put its second Footage item before the first.
- Opened Footage details and exercised the source-video, transcript, cut-on-word/media-outpoint, preview, trim, quiet-sound, and provenance controls.
- Moved the document-wide column divider from 60% to 62%, then used Home to restore 60%.
- Opened the S01 entry and confirmed the authorable Harbor Lights project, the two no-authoring-access examples, section choices, and Open script control.
- Opened Settings and confirmed the presenter-thumbnail toggle, configured presenter name, authoring-size control, explanatory copy, and Reset; the review view was restored to 100% text afterward.
- Reloaded the non-saving `?seed=clean` control copy and confirmed that it returned to the clean 22-row seed.

Pointer and keyboard range inspection plus the right-click endpoint menu were exercised. This handoff does not claim an exhaustive pass over every possible drag path or every command in that menu.

## Content preservation and deterministic verification

- Compared with the accepted v2 seed: 22 of 22 rows, same order, zero narration differences, and the same four section titles.
- The export contains the seed and zero `assets/` or other neighbouring-file references. All seven PNGs are embedded; all 10 thumbnail areas render.
- Clean seed has M1 and M2 only; `♪ Add audio` offers M3.
- Exact local size and SHA-256 match Claude's report.
- Accepted v2 still hashes to `632cfce2b9fea8832b7c13387811d5739518f1247d10bb81ae605671b2005535`.
- `rtk node docs/prototypes/issue-135/check.mjs` passes.
- `rtk git diff --check` passes.
- Repository-wide `rtk npm run validate` did not reach validation because this worktree has no installed `json-schema-to-typescript` package. The active Node runtime is 26.5.0 while the repository requires 24.19.x. No dependency or toolchain installation was performed for this design-artifact handoff.

## Exact-size Chrome verification

Codex opened the exact retained export from a local folder with no neighbouring `assets/` directory in Chrome. Explicit viewport overrides were applied at **1280×800** and **1024×768**, with text 100%.

| Check | Result |
| --- | --- |
| Ten thumbnail areas render from seven unique embedded images | Pass |
| Horizontal overflow at 1280×800 and 1024×768 | None |
| Row 1 face text is limited to two lines and visibly ellipsized | Pass at both sizes |
| Thumbnail size 22% and 0% | Pass at both sizes |
| Authoring text 100% and small 80% | Pass at both sizes |
| Row 21 audio picker: all choices visible, focus starts on first item, `Log a local audio file…` visible, Escape returns focus | Pass at 1024×768 |
| M2 details: `No out-word`; selected 0:04.0–0:17.0; 13.0s play; 3.0s fade; end placement ~3.9s after `ends.` | Pass at 1024×768 |
| M2 rail enters row 20, fades out, has no end tick; row 20 wording agrees | Pass |
| Readiness: first item focused; list stays in viewport; Escape returns focus; local-file group shows two harness items | Pass at 1024×768 |
| Harness examples: M3 EXAMPLE and image warning display; examples leave saved seed unchanged | Pass |

### Retained screenshots

| View | Evidence |
| --- | --- |
| Default, thumbnails 22%, 1280×800 | `evidence/default-1280x800.png` |
| Default, thumbnails 22%, 1024×768 | `evidence/default-1024x768.png` |
| Thumbnails 0%, 1280×800 | `evidence/thumbnails-zero-1280x800.png` |
| Thumbnails 0%, 1024×768 | `evidence/thumbnails-zero-1024x768.png` |
| Readiness with both local-file examples, 1024×768 | `evidence/readiness-1024x768.png` |
| Row 21 audio picker, 1024×768 | `evidence/audio-picker-1024x768.png` |
| M2 settings, 1024×768 | `evidence/m2-details-1024x768.png` |
| Row 18 M3 EXAMPLE, 1024×768 | `evidence/harness-examples-1024x768.png` |
| Small text 80%, lower-row density, 1024×768 | `evidence/small-1024x768.png` |
| Small text 80%, lower-row density, 1280×800 | `evidence/small-1280x800.png` |

Claude's project-preview timing was approximately 1.5s to load (content ready around 0.9s), with thumbnail changes at 65–122ms. The exact local export remained responsive during the retained Chrome checks.

## Known limitations

- Audio timing uses the prototype's word-count estimate (0.38s per word); values marked `~` will change with real voice-over.
- Saved state lives in this browser only. There is no project sync, file storage, upload, or transfer; Locate file records only the local choice.
- The image harness example has no logged filename or size, so it cannot demonstrate the mismatch-confirmation branch.
- A first-presenter fill created by later editing shows the compact bar from earlier rounds.

## Producer acceptance checklist

Use only the retained export with SHA-256 `c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea`. Deterministic integrity, content preservation, and exact-size checks above are already complete.

1. Open the exact export and review row 1 at 1280×800 and 1024×768. Expected: the card face ends with an ellipsis, thumbnails render, and the page has no horizontal scrollbar.
2. Set thumbnails to 0%. Expected: the content hierarchy remains readable and the rows do not develop avoidable dead space.
3. At row 19, open M2. Expected: a 13.0s selection, 3.0s fade, no out-word, and an estimated end ~3.9s into row 20; the row 20 card agrees.
4. At row 21, open `♪ Add audio`. Expected: every library choice plus `Log a local audio file…` is reachable; Escape returns focus to the button.
5. Open Check readiness. Expected: the undefined row is the actionable issue. Turn on both Examples and reopen readiness; the two local-file items appear in their own group and link to rows 18 and 12.
6. Turn both Examples off. Expected: M3 disappears, only M1 and M2 remain, and no `Locally modified` indicator appears.
7. Judge whether the combined rows, Audio workflow, readiness behavior, and density are suitable as the main S03 authoring space.

Acceptance was recorded with the exact response **`Issue #135 S03 v3 artifact accepted`** on 26 September 2026.
