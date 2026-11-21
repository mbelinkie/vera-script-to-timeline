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
- Limit quote destinations to one narration row, keeping r29 row-gap behavior for footage. Preserve the open Library query and original focus on Escape. Quick search attaches on an exact selection and inserts at a valid collapsed caret. Give keyboard destinations the same text as pointer destinations. Count actual quote placements in usage, with speaker and citation visible on the Library quote card.

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

The link or export is needed to reproduce the drag problem and review the comparison before choosing a pilot.
