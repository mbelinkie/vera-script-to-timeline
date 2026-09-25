# Issue 127 plan — successor S03 canonical row system

## Authority and current milestone

Issue #127 is the active Sol/high design story. The accepted source is
`Script to Timeline - Two-Column Authoring S01-S03 v2.dc.html`, accepted under
#14 at commit `11cef62`. The unaccepted v3 artifact, issue #123 experiments,
S05, and production contracts are evidence or downstream consumers; none is
authority to change ordinary S03 authoring.

This first milestone ends at the controlled decision pilot and the Producer's
high-level choice. It does **not** build or promote the full successor.

## Slice ritual

- **Scope:** one isolated ordinary-authoring sample; an Adopt / Adapt / Defer
  matrix against accepted v2; a reversible Minimal / Numbered range-label
  comparison; compact typed visuals, honest footage audio, opaque cutaways,
  transparent overlays, a cross-row music rail, and stable ranged intent.
- **Exclusions:** no accepted v2/v3, #123, S05, production UI, persistence,
  schema, compiler, contract, fixture, golden, generated-type, Resolve, or full
  Fusion-content-editor change. No successor propagation before the Producer
  chooses a direction.
- **Touched contracts/fixtures:** none.
- **New dependencies:** none. The pilot is standalone semantic HTML, CSS, and
  JavaScript; its check uses Node and the installed Chrome application.
- **Automated checks:** render the exact pilot in both range-label modes at
  `1280x800` and `1024x768`; retain screenshots; reject horizontal overflow;
  assert stable range IDs, accessible names, non-orphaning endpoint groups,
  on-demand details, music controls, replacement-with-identical-anchor states,
  and the ordinary-authoring color boundary.
- **Producer acceptance:** complete the ordered checklist in this plan, choose
  Minimal, Numbered, revise, or reject both, and record the first unacceptable
  state. The issue remains open and not Done.

## Product/design brief

- **User and job:** a writer must keep reading and editing continuous narration
  while expressing what is seen and heard over exact word ranges.
- **Decision:** how much persistent range numbering ordinary authoring needs
  once type, opacity, hierarchy, and interaction are clearer.
- **Outcome:** preserve trustworthy range identity without letting range
  bookkeeping dominate ordinary reading.
- **Authoritative behavior:** narration paragraphs remain intact; rows are
  presentation conveniences; each build-relevant object keeps stable identity;
  every visual range is inspectable by pointer and keyboard; opaque visuals
  create cutaways while transparent graphics coexist with the visible base.
- **Accepted precedent:** v2's continuous 60/40 document, compact cards,
  numbered word ranges, derived On Camera returns, and progressive disclosure.
- **Open latitude tested:** Minimal followed an objective row rule: show
  ordinals when a row has two or more non-On-Camera visual cards; omit them
  when the row has exactly one. Claude's consultation exposed that this makes
  visible identity depend on non-semantic row membership and unrelated edits.
  The revised recommendation keeps every ordinal stable and only reduces the
  emphasis of a singleton ordinal. Type tints, range marks, card anatomy,
  overlay hierarchy, and the music rail may remain quiet if meaning stays
  explicit without color.
- **Representative scenario:** one connected harbor passage with a presenter,
  quiet footage, a web/still cutaway, a partial lower third, a quote Graphic
  over moving footage, a cross-row music bed, ranged visual intent, and a
  standalone Full-sound clip.
- **Evaluation rubric:** reading flow; range certainty; distinction between
  opaque cutaway and transparent overlay; truthful sound and music placement;
  compactness; replacement stability; pointer/keyboard parity; non-color
  meaning; wrapping; and card fit.
- **What would make this fail:** visible identity changes when a neighboring
  card is added/deleted or text reflows; brackets orphan when text wraps; type
  tint carries meaning alone; overlay and cutaway appear equivalent; music
  makes rows look merged; hidden bookkeeping becomes unreachable; replacing
  intent moves its anchors; or the compact layout clips at the narrow viewport.

## Scenario map

| State | Pilot evidence | Failure condition |
| --- | --- | --- |
| Normal | Presenter, quiet B-roll, web/still cutaway, and Full-sound standalone clip | Reading order or sound purpose is unclear |
| Overlay | Partial lower third and quote Graphic over an existing moving base | Overlay reads as a replacement/cutaway |
| Cross-row | Music starts on `under` and ends on `clear.` without merging rows | Rail obscures text or implies a visual-row span |
| Unresolved | Need to Find and placeholder intent retain visible ranges | Unresolved intent disappears or looks build-ready |
| Replacement | Intent/card toggles replace content while preserving the exact range ID and endpoints | Replacement silently changes anchors |
| Compact | `0%` thumbnails and small text at `1024x768` | Cards clip, ranges lose identity, or controls become unreachable |

## Controlled comparison

The pilot changes only one decision:

- **Minimal:** a row with exactly one non-On-Camera visual card omits that
  card's visible ordinal. A row with two or more non-On-Camera visual cards
  numbers all of them. On Camera never changes the count; cross-row music keeps
  its own numbered rail. Stable IDs, accessible names, endpoint groups, and
  inspection remain in every case.
- **Numbered:** every timed visual and music range shows a persistent ordinal,
  preserving accepted v2's strongest visible bookkeeping. The revised
  treatment makes a singleton visual's ordinal smaller and quieter without
  removing or renaming it.

All narration, cards, anchors, controls, type treatments, viewports, and
surrounding context remain identical. The Matrix document contains the broader
Adopt / Adapt / Defer recommendations.

## Claude consultation and Sol synthesis

The Producer relayed Claude's read-only consultation response. Claude
recommended **Numbered** and identified the smallest hostile case: deleting or
shortening a neighboring Graphic, or reflowing text across a presentation row,
would cause an untouched visual to gain or lose its visible name. Because rows
are non-semantic conveniences, they cannot control event identity. Claude also
noted that reconciliation and S05 need stable references to the same events and
that numbered music beside an unnumbered visual creates a false hierarchy.

Sol agrees. The in-document identity failure is decisive even without evidence
that writers quote ordinals in external notes. Recommend **Numbered with a
quieter singleton ordinal**. Minimal saves one glyph in the least crowded row
but creates a state-dependent naming exception and downstream recognition
cost. The exact relayed response is retained in
`docs/prototypes/issue-127/claude-read-only-consultation.md`.

## Stop gate and Producer review

Do not build a successor from this sample yet.

1. Open `docs/prototypes/issue-127/pilot.html` in a browser at `1280x800`.
2. Leave **Range labels** on the recommended **Numbered** mode. Read the passage
   top to bottom. Confirm every timed visual retains a visible ordinal and the
   second row's singleton web/still ordinal is quieter, not absent. On Camera
   and On Camera resumes are not numbered visual events; accessible range names
   and stable IDs remain.
3. Use pointer hover and keyboard focus on each narration range and visual
   card. Confirm both sides identify the same range and every opening/closing
   bracket stays attached to its first/last word.
4. Switch briefly to **Minimal** to see the rejected risk: only R3 disappears.
   Switch back to **Numbered** and confirm no card, wording, anchor, row height,
   or range identity changes.
5. Toggle **Intent / replacement** for both the Need to Find footage and quote
   Graphic. Confirm the card changes but the shown start/end words and stable
   range ID do not.
6. Open footage **Details** with pointer and keyboard. Confirm collapsed B-roll
   shows one type pill, thumbnail, useful length, Quiet/No sound, and optional
   zoom, while source bookkeeping is available on demand. Confirm the
   standalone Full-sound clip alone shows transcript as program content.
7. Focus the right-margin **Music 6** rail. Confirm its popover names start
   word `under`, out-word `clear.`, source trim, and fade; operate the native
   trim/fade controls and confirm no script row moves or expands.
8. Confirm the lower third and quote Graphic use a dashed transparent-overlay
   perimeter over a continuing base, while opaque footage/still cards read as
   cutaways. Confirm no reconciliation red/green, Added in Resolve language, or
   decision controls appear.
9. Repeat steps 2–8 at `1024x768`, small text, and `0%` thumbnails. Confirm
   visible focus, wrapping, card fit, and no horizontal overflow.
10. Reply with one precise result:
    - `Issue #127 pilot direction: Numbered with quieter singleton ordinals. Proceed to the bounded successor pilot.`
    - `Issue #127 pilot needs revision: <first unacceptable state>.`
    - `Issue #127 pilot rejected: <reason>.`

The response selects a high-level direction only. A later exact successor still
requires its own Producer acceptance before #127 can close.
