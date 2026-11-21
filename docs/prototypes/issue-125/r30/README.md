# S03 r30 Library design brief

[#642](https://github.com/mbelinkie/vera-script-to-timeline/issues/642) revises the exact accepted [S03 r29](../r29/README.md) for a writer who wants to turn a saved Research quote into narration and timed visuals while staying in the script. The behavior comes from the [accepted Research Sources spec §8](../../../plans/research-sources-spec.md#8-editor-the-125-r30-design-642). The [Research #75 r14 handoff](https://github.com/mbelinkie/vera-research-video-clips/blob/321910eaf4819c2a9249e2dbd8c4c40c3d5405ab/docs/design/claude-design/RESEARCH-R14-HANDOFF.md) supplies Library language, excerpt-first reading order, separate row actions, compact focus behavior and the project-wide Hide rule for future placements. Research has Sources and Library as its two approved tabs.

## Capability evidence

| Promised action | Delivered evidence | Supported limit and remaining work |
| --- | --- | --- |
| Find, inspect and place logged footage | [Timeline #80](https://github.com/mbelinkie/vera-script-to-timeline/pull/669) and [#672](https://github.com/mbelinkie/vera-script-to-timeline/pull/678) deliver authorized search and placement and saved-range playback. | Preserve real clip availability and the saved range. Mixed search, filter and placement integration belongs to [#643](https://github.com/mbelinkie/vera-script-to-timeline/issues/643). |
| Find authorized web and typed quotes and their pictures | Research delivered the [mixed records](https://github.com/mbelinkie/vera-research-video-clips/pull/86), [quote API](https://github.com/mbelinkie/vera-research-video-clips/pull/87), [typed quotes](https://github.com/mbelinkie/vera-research-video-clips/pull/115) and [extension](https://github.com/mbelinkie/vera-research-video-clips/pull/93). [#641](https://github.com/mbelinkie/vera-script-to-timeline/issues/641#issuecomment-7000022677) captured immutable top and passage pictures and verified the saved rectangle against real page pixels. | #643 owns the Timeline authorization, kept-picture handoff and mixed Library. Treat no picture differently from a denied quote. Respect project-wide hiding for new uses and preserve existing placements. |
| Insert at a gap or attach to selected words, with one Undo | [#680 / PR #681](https://github.com/mbelinkie/vera-script-to-timeline/pull/681) is merged. Its focused tests exercise one document command, exact anchors, Need to Find and refusal with the original document intact. | #643 binds browser pointer and keyboard targets, checks save/reload, extends an adjacent same-article background and retains source-list attribution after deleting the cards. The shared picture with two separate boxes has native precedent below. |
| Edit a per-use quote box over a still or article picture | [#629 Studio evidence](https://github.com/mbelinkie/vera-script-to-timeline/issues/629#issuecomment-6985290208) shows three editable V4 boxes over a continuous drifting V1 still after reopen. [#630](https://github.com/mbelinkie/vera-script-to-timeline/pull/660) verifies per-use citation overrides and Unicode italics in the pinned EV24 title. | Keep independent range marks and the fixed template. The browser box editor and latest-used text default belong to #643. Arbitrary templates belong to #647. |
| Place a kept still | [Research #82](https://github.com/mbelinkie/vera-research-video-clips/pull/91) and [Timeline #673](https://github.com/mbelinkie/vera-script-to-timeline/issues/673#issuecomment-7045731858) prove the authorized picker and ordinary still build after the original URL goes away. | Q200 has a still picker. Full Library drag and quick search stay with [#645](https://github.com/mbelinkie/vera-script-to-timeline/issues/645). |
| Show Audio cards and add a Mac file to the shared Library | The [extension](https://github.com/mbelinkie/vera-research-video-clips/pull/93) can register an audio-link source. Timeline [#381](https://github.com/mbelinkie/vera-script-to-timeline/issues/381) supplies project-media preparation. | Research waveform and role placement are later [Research #83](https://github.com/mbelinkie/vera-research-video-clips/issues/83) and [Timeline #646](https://github.com/mbelinkie/vera-script-to-timeline/issues/646) work. Editor file registration, sharing and relink are later [Timeline #85](https://github.com/mbelinkie/vera-script-to-timeline/issues/85) and [Research #84](https://github.com/mbelinkie/vera-research-video-clips/issues/84) work. A waveform fixture or file-picker mock cannot verify either path. |
| Turn on “Highlight the passage” and return to the top picture when off | #641 proved the capture inputs. [#169's Studio probe](https://github.com/mbelinkie/vera-script-to-timeline/issues/169#issuecomment-6933622488) verified precomposed synthetic Spotlight stills after reopen through probe-only OTIO. | **Open proof in #644.** Build one public or synthetic quote using its actual saved passage picture and rectangle. Reopen and verify the visible highlight with the transparent box and drift, then verify that off restores the pinned top picture. This is independent of the Library UI. |

Matthew approved the Q200 scope on November 20, 2026. The Library shows All, Footage and Quotes, and the existing kept-still picker remains available through the visual picker. Quote placement is the design target for #643. Audio, “+ Add file,” full still placement from the Library and “Highlight the passage” are deferred to the issues above. The Spotlight build proof gates that later control.

## Representative scenario

Use one r29 narration row with a clip and a short synthetic article quote in the Library. Show the quote approaching the space between two spoken words and an existing two-word selection in that same row. Hold the panel, data and surrounding script constant. Compare how clearly the two destinations show what will change. Use one consistent mechanism for pointer and keyboard. The existing **Place in script…** action can reuse the destination flow and selection conventions. The decision is how to show insertion versus attachment at the destination. Both options use the same quote placement behavior. Add the same-article second quote and the existing kept-still picker to the coverage after the focused comparison.

A gap inserts the source quote as spoken words and places its background and dashed transparent quote box. A selected word range keeps the spoken text and attaches the two visuals. Reject stale or invalid targets before any visible edit. One Undo restores the previous words, visuals and ranges and restores both the script target and the Library user's place. The quote box follows the accepted #123 layer rules, keeps its own brackets and never creates an On Camera return. An adjacent second quote from the same article keeps one continuous background and adds an independent box. Undoing the second use restores the first background extent.

## Coverage and review

- Preserve the r29 panel geometry and compact cards, clip transcript and preview, search, logger, Topic, usage, Sort, thumbnail sizing, usage jumps and the existing clip-specific row and gap placement. Rename **Show footage** to **Show library**. Search should match quote text, speaker and source title as well as clip titles and transcripts. Preserve query and filters across placement and Undo.
- For the pilot after Producer selection, exercise gap insertion, attach, and safe cancel or refusal at 1280×800 and 1024×768. From the keyboard use ⌘⇧F and Place in script…, confirm or Escape, and check focus return. Use an inline caret versus word brackets and plain-language feedback so color alone carries no meaning. Keep the compact script target visible when the Library is open.
- For expansion, cover the adjacent second quote and Undo, the typed quote with a picture, and **Need to Find** for a typed quote without a picture. Show an editable quote box with per-use display text, speaker name and title, citation and the template. A display edit leaves the saved source and narration intact. Preserve the latest-used default and the source link when both cards are removed.
- Distinguish an empty Library, no search matches, unavailable media and denied access. Retain the r29 Open in VERA Research and recovery patterns where appropriate. Denied access must disclose no quote or image. A thumbnail at 0% must leave the card type and quote text legible. No placement action may silently insert text when attaching was intended.
- Keep every unrelated r29 surface, including Stash, Sorting, playback, On Camera and the existing #125 range-review fixtures. Use synthetic material or approved public sources. Retain the exact Claude Design source and export after review at both sizes. The Producer chooses between focused options before the pilot, then accepts the exact full revision.

## Claude Design consultation

Use [S03 Integrated Authoring r29.dc.html](https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=S03+Integrated+Authoring+r29.dc.html), with `support.js` in the [r29 archive](../r29/S03%20Integrated%20Authoring%20r29.zip), and the [approved Research r14 review](https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=VERA+Research+r14+-+Final+review.dc.html). Bring back Claude’s written recommendation for review before requesting a visual comparison.

```text
Act as co-designer for VERA Timeline #642, S03 r30. Use the exact
S03 Integrated Authoring r29.dc.html and the approved VERA Research r14
- Final review.dc.html as references. Leave the design files untouched
for this consultation.

The writer wants to place a saved Research quote without leaving the
script. For the approved Q200 scope, repurpose the r29 Footage panel as
Show library with All, Footage and Quotes. Reuse the r29 panel, cards
and placement controls, and r14's excerpt-first quote hierarchy.
Keep the existing kept-still picker. Spotlight, Audio, + Add file
and still placement directly from the Library are follow-up work.

Compare only the cues for two destinations within the same r29
narration row. Hold the viewport, row, clip and synthetic article
quote constant. At a word gap, placement inserts spoken quote text
and adds the article background and transparent quote box. On an
existing word range it attaches both visuals and keeps the narration.
Each is one Undo. Keyboard placement through Place in script… and
quick search must communicate the same distinction.

Return two materially different cue approaches, the most likely
misread for each, and your recommendation. Consider 1280×800 and
1024×768, keyboard focus and how the cue reads without color. Flag
any conflict with the accepted designs. Stop after the written
consultation. We will review both treatments with Matthew.
```

## Consultation review

Claude and Sol recommend a labeled cursor or range outline. The target stays in place under the pointer at compact width, and the two verbs communicate the result without color. Compare it with an in-place outcome preview, which shows more detail before committing and may compete with the existing words and brackets. The Producer decision follows the rendered comparison.

- [Research PR #112](https://github.com/mbelinkie/vera-research-video-clips/pull/112) records r14 approval after the older in-project log. [Timeline #673](https://github.com/mbelinkie/vera-script-to-timeline/pull/679) delivered the kept-still picker in the editor. The quote's article picture comes from its source.
- [Research Sources §8.2–8.5](../../../plans/research-sources-spec.md#82-the-quote-box-is-a-transparent-graphic-no-new-layering-design) applies the accepted transparent Graphic precedent to S03 and specifies the Need to Find fallback. The background takes ordinary picture coverage. The overlay has its own range and keeps the base visible. A conflict with an existing clip follows the ordinary background coverage rules. The comparison keeps the clip outside the target so that it tests the two cues directly.
- The A/B comparison used one narration row. Preserve the open Library query and original focus on Escape. Quick search attaches on an exact selection and inserts at a valid collapsed caret. Give keyboard destinations the same text as pointer destinations. Count actual quote placements in usage, with speaker and citation visible on the Library quote card. See the Producer's later decision below for the row-divider target.

## Focused comparison prompt

```text
In Claude Design create a separate page, S03 r30 — Quote placement
comparison, from the exact S03 Integrated Authoring r29.dc.html.
Preserve the accepted source and shared components. Use the approved
Research r14 handoff for excerpt-first quote cards with speaker and
citation. Its approval is recorded in Research PR #112.

Compare two treatments at 1024×768 on one screen or through an A/B
switch. Use Show library with All, Footage and Quotes, the same
synthetic quote and the same r29 row beginning “Across the channel”.
Use the gap before “second” and the range “second gauge.” in its
first sentence. The Channel light clip later in the row stays as-is.
At the gap, insert the quote as spoken text with the article picture
and dashed transparent quote box. On the range, attach both visuals
and keep the words. Give each one Undo. The picture owns primary
coverage and the box has its own word range under the §8.2 rules.

A · In-place outcome preview. Show ghost narration only for the gap,
the proposed words for the range, and the two pending visuals.
Make the preview recognizable as uncommitted without color.

B · Labeled target. Show a caret for “Insert quote” or an outline for
“Attach quote · narration unchanged”. Keep the row still and keep
the label readable beside a compact column edge.

Use the same drop and keyboard semantics. Show the corresponding
keyboard destination and visible focus, with the same action wording
in Place in script… and ⌘⇧F. On Escape restore the initiating control.
Keep all other r29 content and controls intact. Reuse r29 word
selection and keyboard conventions. Row gaps remain footage targets. Spotlight,
audio, file registration, and direct Library still placement are
future work. Need to Find and adjacent same-article placement come
after this comparison.

Return the comparison link and export, the hardest case for each
option and your recommendation. Stop for Matthew's choice.
```

## Producer feedback on the comparison

Matthew reported difficulty with both drag destinations on November 21. His usual task is to have the host read the same quote seen on screen. Put that case first in the review. A single insertion should put matching quote text in the narration and quote box, place the article picture and graphic over the inserted words, and take one Undo. On first placement, use the same quote wording in both columns. If a previously shortened quote is offered as the default, verify that the inserted text matches the box for this read-aloud workflow. Later edits to either remain independent.

Recommend making the existing **Place in script…** action easy to find on quote cards and letting it insert at a chosen caret. The user should be able to complete the main task without aiming at a narrow drop zone. For attachment, test Matthew's exact sequence: select a sentence, start dragging a Library quote, confirm the sentence remains visibly targeted, and drop on it. Check that the words stay intact and one Undo removes both visuals. Include the case where dragging from the sidebar clears the browser selection. In that case the editor needs to retain the target range and must refuse a lost or stale target.

## Live comparison review

Inspected the [Claude Design comparison](https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=S03+r30+-+Quote+placement+comparison.dc.html) in Chrome. In the compact 1024×768 frames, the preview at the gap rendered two extra lines in A and kept the row at its original height in B. B's **Insert quote** added the 12 spoken words, the article picture and the transparent Graphic. Its **Attach quote** added the picture and Graphic over “second gauge.” and preserved narration. One Undo restored the original row for each. The later Channel light clip remained present.

In the 1280×800 prototype page, pointer insertion just before “second” worked. Dragging onto “second gauge.” after choosing the test helper **Select “second gauge.”** attached both cards. Selecting the full first sentence by hand and dropping on the selection left the script unchanged, including when the drop was on “second gauge.” The comparison only demonstrates the two preset destinations. The “Open interactive” link returned “preview token required.” The prototype page opened inside Claude Design through the page picker.

Recommend B with **Place in script… → Insert quote** easy to find for the read-aloud case. The current Graphic preview is a placeholder with the type and speaker. Before accepting a pilot, show the matching quote wording in both columns and verify a normal sentence boundary, a hand-selected full sentence, Undo, and compact keyboard and pointer behavior. Keep the attach label off the narration it describes.

## Producer choice and pilot

Matthew chose B on November 21, 2026. The labeled caret and range outline preserve the row layout while placing. A's ghost narration and pending cards reflowed the compact row before commit. The remaining risks are a hidden placement action, a lost sentence selection and a label that covers the narration. The choice authorizes the bounded pilot.

```text
Matthew chose B, the labeled caret or range outline. Copy
S03 r30 Quote Placement Prototype.dc.html to a separate
S03 r30 - B quote placement pilot.dc.html. Preserve r29 and the A/B
comparison. Use the existing synthetic quote and “Across the channel”
row, keeping the later Channel light clip.

1. Read-aloud. Click a sentence boundary in the narration. Make
   Place in script… visible on the Library quote card and lead with
   Insert quote at that caret. Commit the same quote wording in the
   narration and the Graphic preview. The article picture and Graphic
   each cover the inserted words. Show the actual quote text in the
   Graphic preview. One Undo restores the original row.
2. Attach. Select the full first sentence by hand, then drag the
   quote onto it. Retain the intended sentence while dragging from
   the Library. Show B's range outline and Attach quote label without
   obscuring the text. Add both visuals to exactly that range while
   leaving the narration intact. One Undo removes both. A cancelled
   drag or lost target leaves the document intact.

Run both flows at 1280×800 and 1024×768 with real pointer input.
Check the keyboard paths through Place in script… and ⌘⇧F, including
visible focus, equivalent destinations, Enter and Escape, and focus
return on cancel. Check the caret and range cues without color.
Return the pilot link and export, what passed at each size, and
anything still limited to fixtures. Stop at these two flows.
```

## Independent B pilot review

Reviewed the [live B pilot](https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=S03+r30+B+Pilot.dc.html) with browser pointer and keyboard input at 1280×800 and 1024×768. The pilot needs a correction before expansion.

| Check | Result |
| --- | --- |
| Insert at the existing sentence boundary | Passed at both sizes. The quote card's visible action opens Insert quote. The narration and Graphic card use the same 12 words, the picture and Graphic cover the inserted range, and Channel light remains present. One Undo restores the original. |
| Attach after selecting the first sentence by hand | Passed at 1024×768, including exact first/last anchors and one Undo. At 1280×800 a native drag attached both cards and duplicated the existing sentence. The live message said narration was unchanged. The next Undo removed the duplicate, and a second removed the cards. An off-target drop left the row intact. |
| Quote in its own row | **Fails at both sizes.** Add row creates and focuses a blank narration row. At that caret, Place in script… says “No place chosen in the script” and offers Close. A direct quote drop between rows at 1024×768 made no new row. |
| Keyboard and focus | Tab reached the quote card action. Place in script… focused Insert quote and Escape returned to its button. The compact ⌘⇧F flow attached the selected sentence, Escape restored focus and selection, and Enter plus one Undo passed. ⌘⇧F insertion passed after a clean reload at 1280×800 and at 1024×768. At 1280×800 it also offered Insert on a visibly highlighted full sentence. In an earlier wide trial after changing sizes, Escape → reopen → Enter left the dialog open and put a paragraph break into the narration. At 1024×768, ⌘⇧F inside a sentence gave only a live-region message. |
| Compact presentation | The quote text is legible on the Graphic card at 1024×768. The Insert dialog covers the Library card's action. Undo restores the row and leaves a stale placement message in the live region. The visible caret/outline and the action names carry the distinction without depending on color. |
| Library | Kind switching and searches for quote text, speaker and publication worked. An unmatched query gave a no-results message and the quote stayed legible at 0% thumbnails. Footage still appeared in its own filter. The logger choices omit the quote's fixture logger, Maya Chen. “Research: none logged” still shows the synthetic quote, so it exercises a footage-empty state. Reset sample removes the pilot narration row until reload. |

The one-quote pilot has no fixtures for adjacent quotes, missing pictures, media unavailability or denied access. Quote-box editing, multiple-use stepping, and the delivered kept-still picker are still due for the broader r30 review. Claude reported a single-file export. This review used the live pilot and browser accessibility state.

For the correction, keep B and give the blank narration row's caret the same Insert quote action as a sentence boundary. Validate that a browser drop cannot create a text edit in addition to the quote command. Use the currently visible selection for ⌘⇧F and keep Enter inside the active placement dialog. Show a visible unavailable-target message and clear the placement announcement on Undo. Retest the three placement cases with physical selections at both sizes before expanding.

## B Pilot r2 correction review

Verified the [live B Pilot r2](https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=S03+r30+B+Pilot+r2.dc.html&present=1) in Chrome at 1280×800 and 1024×768.

- **Separate row:** Add row focused the new blank narration. Place in script… named that blank row and Insert quote added matching spoken and displayed wording, with an article picture and Graphic. The previous row stayed unchanged. One Undo restored the blank row and left Add row as the next Undo.
- **Full-sentence drag:** On a hand-selected first sentence at both sizes, the picture and Graphic attached from “Across” through “gauge.” The spoken words stayed identical and one Undo restored the original rendered narration, with Channel light present. A wide drop off the target changed nothing.
- **Keyboard:** ⌘⇧F opened Attach on a hand-selected sentence at both sizes. Escape restored text focus and the selected range, and Enter after reopening committed once. Insert passed with a chosen caret and one Undo, including the wide clicked caret after switching sizes. The wide test helper “Caret before sentence 2” targeted the first word once immediately after switching from compact. Clicking the intended caret selected the correct location.
- **Feedback:** The compact placement dialog cleared the quote action. Undo cleared the stale success announcement. A mid-sentence shortcut in the wide test displayed “Not a place for a quote” and left the script intact.

This review covers the live corrected pilot. The broader Library cases and the standalone export still need review.

## Producer notes after B Pilot r2

On November 21, Matthew asked for a highlighted boundary that creates a new narration row when the writer drops a quote between rows, and quotation marks around every quote inserted into the narration. The row boundary reuses the accepted r29 D185 insertion line, labeled **Insert quote as new row** for a quote. User direction fixes the destination and behavior, so reuse the established treatment in the next focused B pass.

| Promised action | Evidence and limit |
| --- | --- |
| Create a complete quote row at a valid boundary in one Undo | #80 accepts an exact row gap, and the existing authored row command creates a complete row in one edit. A focused synthetic contract check prepared a new row with #680's quote edit, then committed it to the original document once through the exact gap. Validation passed and Undo restored the original block list. Browser integration belongs to #643. |
| Wrap only the inserted narration in quotation marks | The same check verified a single pair of curly double quotation marks in the saved narration and independent display copy in the overlay. Treat those marks as punctuation. Retain interior punctuation and avoid doubling a matched outer pair. |

The fresh pilot should cover a drop at an existing row seam between two rows in the same section, a quote inserted at a caret, and attachment to existing words. Check a loss or cancellation of the seam, one Undo for the whole new row, one Undo for the in-row insert, the approved B target label without color, and preservation of the adjacent footage. For the separate-row keyboard path, use Add row and the existing Place in script… action. The new [footage replacement issue #686](https://github.com/mbelinkie/vera-script-to-timeline/issues/686) owns the clip-on-card gesture.

## B Pilot r3 review

Reviewed the [completed live r3 pilot and Claude handoff](https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=S03+r30+B+Pilot+r3.dc.html). Claude reported 91 scripted passes across 1280×800, 1024×768 and a return to 1280×800, including the gold divider, the “Insert quote as new row” label, cancellation and outer-quote normalization. The standalone export is `exports/issue-642-r30b/S03 r30 B Pilot r3 - export.html` in Claude Design. The live harness did not expose a result on rerun. The following checks used the rendered live pilot.

- At both sizes, a pointer drop below “Across the channel” created one row at that exact divider. The 12 spoken words had one pair of curly quotation marks. The article picture and transparent Graphic used the same first and last words, with the Graphic's display copy independent. One Undo removed the row and cards and preserved the neighboring narration and Channel light. An off-target wide drop left the script intact.
- At 1024×768, a clicked sentence boundary and ⌘⇧F opened Insert. Escape, reopen and Enter committed once, and Undo restored the original narration and Channel light anchors. Add row followed by Place in script… opened a compact dialog clear of the quote action. Insert added the quoted narration and both visuals. One Undo restored the blank row.
- At 1024×768, a live drag onto the first sentence selected by the test harness attached both visuals through “gauge.” The script words did not change. A previous failed selection left “Select words within one row” visible after that successful attach and Undo. Clear obsolete target feedback when a valid target is acquired or a placement succeeds, cancels or is undone. Verify the available article picture renders as a recognizable thumbnail on the placed card. It appeared as a dark tile at the sample thumbnail size.

Use r3's mechanics in the integrated r30 next, based on the accepted r29 authoring artifact. Keep divider drops on existing r29 Add row targets in authoring. Use the visible divider hit area for the row action and sentence carets inside narration. Fix the stale feedback during integration. Complete the broader Library scenarios above and retain and inspect the exact integrated source and export at both sizes before Producer acceptance.
