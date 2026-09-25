# Issue 127 — bounded read-only Claude consultation

Status: **response relayed by the Producer on 2026-09-25**

This is a consultation-only prompt. It does not authorize Claude to create,
edit, or promote any artifact.

## Exact prompt

```text
Act as a design critic for one bounded ordinary-authoring decision. Do not edit,
create, or propagate an artifact.

User and job: A VERA script writer must read continuous narration while
understanding which exact words control each shown or heard element.

Decision: In the accepted S03 successor, should Minimal use this objective row
rule: when a row contains two or more non-On-Camera visual cards, number every
one; when it contains exactly one, omit that card's persistent visible ordinal?
On Camera does not affect the count, and cross-row music keeps its own number.
The alternative Numbered mode gives every timed visual a visible ordinal.
Stable IDs, accessible names, endpoint brackets, and pointer/keyboard inspection
remain in both.

Authoritative behavior: narration paragraphs remain intact; rows are only
presentation conveniences; visual and audio events use exact word ranges;
opaque visuals are cutaways; transparent Graphics coexist with the visible
base; B-roll under narration is No or Quiet sound; Full sound is reserved for a
standalone program-audio clip. Accepted S03 v2's continuous 60/40 document,
compact cards, and numbered ranges are the visual precedent.

Controlled sample: one connected passage includes On Camera, quiet and silent
footage, one single-card web-capture row, a partial lower third, a quote
Graphic over moving footage, a cross-row music rail, a ranged Need to Find
request, stable intent-to-replacement toggles, and a standalone Full-sound clip.
Only the web-capture range loses its visible ordinal in Minimal. The first row
has footage plus a lower-third Graphic, so both are numbered; the third row has
footage, a quote Graphic, and a ranged request, so all three are numbered.
The cross-row music event stays separately numbered.
The sample uses light type tints reinforced by labels and no reconciliation
red/green.

Sol recommendation: Minimal with the objective two-card threshold, but only if
the lone unnumbered web-capture range remains immediately identifiable at
1024×768, small text, and 0% thumbnails. Numbered is the safe fallback.

Evaluation: reading flow, range certainty, non-color meaning, wrapping,
compactness, overlay-versus-cutaway clarity, music-span truthfulness, and
pointer/keyboard parity. Failure means the count rule makes a single visual
ambiguous, fails when a row's On Camera base/return coexists with one non-OC
card, or weakens transfer to reconciliation/S05 more than it helps ordinary
writing.

Challenge the framing. State whether Minimal and Numbered are genuinely
different enough to merit the Producer gate, identify the smallest hostile
scenario most likely to invalidate Minimal, and recommend Minimal, Numbered, or
a focused revision. Explain the product tradeoff and downstream effect on the
read-only reconciliation and outbound-update surfaces. Ask only a question
whose answer would materially change this comparison.
```

## Response record

The Producer relayed this Claude response verbatim:

> **Verdict: Numbered.** The two modes differ too little to justify a Producer
> gate, and Minimal has a hostile case that the sample doesn't test.
>
> **How different are they?** In this sample, the only difference is one
> missing ordinal on one web-capture range. Both modes keep the IDs, brackets,
> accessible names and inspection. So the gain is a single glyph in rows that
> already have the least clutter. Rows with two or more cards, where the reader
> actually needs help sorting cards, look the same in both modes. A difference
> this small doesn't need a Producer decision. The rule should be settled at
> the design level.
>
> **Framing problems**
>
> 1. The ordinal isn't only there to tell cards apart. It's also the word the
> writer uses to refer to a card ("move 4 to after 'river'"). Under Minimal,
> whether an event has that name depends on what else sits in its row. Rows are
> only presentation conveniences, so an event's label would depend on something
> with no meaning of its own.
> 2. "Immediately identifiable at 1024×768" is a legibility test. The real risk
> is the numbering breaking when the text changes, and a static screenshot
> won't show that.
>
> **The smallest hostile case that breaks Minimal** Take the first row: footage
> (1) plus the lower-third Graphic (2). The writer shortens the lower third so
> it ends earlier, or deletes it. Now the footage is the only card left in the
> row, and it loses its "1". The same thing happens in reverse when a narrow
> viewport or a narration edit changes where a row wraps. A new row boundary
> can split a pair, and both cards lose their numbers. Either way, a card's
> visible identity changes even though that card wasn't touched.
>
> Two smaller problems follow:
>
> - The On Camera base or return still takes up visual space in the row. A lone
> unnumbered card next to it can read as part of the base rather than a separate
> cutaway or overlay. It stops looking like a counted, timed event.
> - The music rail stays numbered in every row. So an unnumbered visual next to
> a numbered audio event looks like it ranks lower, or like it isn't timed at
> all.
>
> **Effect on reconciliation and S05** Both of those surfaces have to point at
> events without ambiguity ("3 replaced", "request 5 fulfilled"). If some
> events had no visible number while writing, then:
>
> - The read-only reconciliation view either adds numbers the writer never saw,
> breaking recognition, or refers to those events by ID or description, which
> makes the view uneven.
> - Outbound updates can't reliably quote what the writer saw on screen.
>
> Numbered keeps writing, reconciliation and outbound on the same set of
> references. Minimal saves one glyph and makes every downstream surface handle
> a special case.
>
> **Recommendation** Numbered, plus one small revision to keep what Minimal was
> trying to do. Keep the ordinal on every timed visual, but make it visually
> quiet on a card that is alone in its row (smaller, or tinted less). It stays
> present, stable and usable as a reference. Numbers should not change when rows
> reflow or when a neighbouring card is edited.
>
> **The one question that would change this** Do writers ever refer to events
> by ordinal outside the document, for example in notes to editors, producer
> comments, or S05 messages? If they never do, and every downstream surface
> uses stable IDs rather than visible ordinals, Minimal's cost drops to a reflow
> and legibility problem. In that case it would be worth a live test with
> editing and reflow, not a static one.

## Sol synthesis

Agree with **Numbered**. The hostile case invalidates Minimal without requiring
an answer to Claude's final question: even if writers never quote ordinals
outside the document, an untouched event should not gain or lose its visible
name because a neighboring card or presentation row changed. Stable ordinals
also preserve recognition when the same event appears in read-only
reconciliation and S05.

The controlled artifact now makes a singleton ordinal quieter while preserving
it. This is still only a recommendation. Claude's response is evidence for the
Producer's choice, not authority to change accepted S03 v2 or promote a
successor.
