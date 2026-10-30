# Presenter Coverage — consultation brief

Status: Producer direction plus proposals for Claude CLI critique. No design-app
edit or presenter implementation is authorized by this document. Keep #125
moving independently of deferred presenter implementation (#353). #124 owns
the fuller presenter review design; #45/#46 own matching/approval, #91 playback,
and #47/#48 the later assembly chain. Record adopted decisions in #62.

Canonical adopted direction and answered questions:
<https://github.com/mbelinkie/vera-script-to-timeline/issues/62#issuecomment-6515836558>.
Playback result and supported limits:
<https://github.com/mbelinkie/vera-script-to-timeline/issues/91#issuecomment-6515912354>.

## Job and adopted direction

Choose usable recorded readings against script words, including partial takes,
without turning organizational rows into artificial take boundaries. An entire
video could be one row: the design must still handle several overlapping takes
and many cutaways. Use “row,” never invented row numbers as user-facing names.

- **View presenter coverage** keeps all script words in the left column and
  temporarily replaces the right column's ordinary visuals with take cards.
  Leaving the mode restores the ordinary visual presentation.
- Preserve bold as **On Camera**. This tells the reviewer where the presenter
  must be visible even while ordinary visual cards are hidden.
- A take has a matched script range. Ranges may overlap, nest or cover only part
  of another take. A row is a container, not the smallest selectable unit.
- Multiple take cards may contribute to the chosen performance. The newest
  explicit choice replaces only its overlapping words, leaving other chosen
  words intact. A longer take can therefore be **Partly used**. Each spoken
  word has at most one chosen recorded reading.
- Auditioning a candidate must remain distinct from choosing it. Partial
  choices stay within supported matched ranges. No automatic keeper decision.
- Uncovered words retain temporary voice and an honest **Needs take** state;
  do not imply recorded presenter picture exists there. Removing a partial
  choice reveals the prior longer choice where available, otherwise fallback.
- A join hidden beneath opaque cutaway footage is allowed. A visible presenter
  join with changed framing (Wide/Tight) is also allowed. For a same-framing
  visible join, offer the take with a framing change at that point; acceptance
  splits the OC appearance, not the script row. Preserve later explicit
  framing. One Undo reverses the combined choice/framing change. A transparent
  graphic does not hide the presenter. **Allow presenter jump cuts** is an
  opt-in setting, off by default. This supersedes the earlier blanket ban on
  visible presenter cuts.
- The Producer explicitly accepts **audio-only assembled preview** as enough
  to judge the selected readings. Selecting takes must not require rendering
  another composite video first.

## Candidate interaction to critique, not yet an adopted contract

Checkboxes express selected coverage, but a partly used take cannot truthfully
look like a simple binary checkbox. Recommend a clear partial state and how to
inspect exactly which words it supplies. Arrows may audition alternates;
**Use take** explicitly changes the assembly. Compare this with direct checkbox
selection rather than putting two redundant committing actions on every card.

A draft-then-Apply approach has been suggested, but is not a Producer decision.
Recommend whether this is needed or just adds a second confirmation. Explain
Cancel, Undo and leaving coverage mode under the recommended approach.

## Capability boundary

| Promise | Evidence / exact limit | Remaining owner |
| --- | --- | --- |
| Read-only local source ranges and a continuous audio assembly clock | #91 experiment / PR #374: fixed manually supplied edit lists using existing #44 proxy/audio handoffs; no matching or new encoded output. Final corrected measurements belong in the experiment README. | #91 production playback |
| Video switches, scrubbing and framing preview | Experimental native-video switching had visible stalls/drift. CSS Wide/Tight demonstrated presentation only. Do not promise seamless assembled picture. | #91; framing owner #119 |
| Real presenter proxy input | The authorized sample was rejected by normal source inspection: `unsupported_profile: decoded SDR metadata missing or changes`. No bypass or upload. | Existing media-ingest owners |
| Word matching, partial coverage selection, persisted assignments, visible-join repair and Resolve output | Product intentions, not proven by a manually supplied playlist. Existing #46/#124 scopes currently exclude intra-beat splicing and assume per-beat assignments; the new word-range direction requires a later scope amendment. | #45/#46/#124/#47/#48 |

This is consultation, not permission to depict unproved presenter mechanisms as
working. An audio experiment cannot clear the whole presenter capability gate
or block the rest of #125. Keep implementation limits outside the product frame.

## Smallest useful design test and critique request

Critique the interaction before editing any artifact. Use one long row with a
full take, a nested pickup and an overlapping partial that extends beyond it.
Include one hidden join, one same-framing visible join and uncovered words.
Evaluate 1280×800 and 1024×768, pointer and keyboard, without a timeline editor
or a huge simultaneous card wall.

Concentrate on selection versus audition, partial/overlapping coverage clarity,
reading and navigation in the one-long-row case, provenance after rewrites,
and whether the On Camera visibility/framing rule is understandable. Existing
comments, Stash, Sorting and Show Contributions must retain their accepted
semantics; coverage should not add another concurrent editing/review layer.

Return at most five concrete failure cases with recommended refinements, the
smallest focused comparison to show Matthew, and only questions whose answers
materially change behavior. Distinguish adopted direction from your proposals.
Do not implement, contact the design app, or start the deferred backend chain.

## Opus CLI critique — completed 2026-10-30

Text-only consultation completed without changing files, using the design app,
or starting implementation. This is interaction critique, not capability proof.

Useful refinements to test, **not yet adopted product decisions**:

- A checkbox alone cannot explain the order-dependent result of overlapping
  choices. Compare checked/partial states with explicit **Use take** plus a
  coverage status and focused-word source. A fully superseded choice needs a
  truthful state if it can still return later.
- Separate audition from committing. Claude recommends immediate **Use take**
  plus ordinary Undo, with **Stop/Escape** ending an audition and leaving the
  mode stopping it. A second draft/Apply layer appears unnecessary.
- Evaluate both entry and exit joins of a nested pickup together. Offer the
  required framing changes in one action and preserve later explicit framing.
  Do not silently assume the return join was repaired by changing the entry.
- A whole-video row needs focused-range filtering/navigation rather than every
  candidate displayed at once. Test one long row with a full take, nested
  pickup, overlapping partial, a hidden join and uncovered words. Keep identical
  behavior/content when comparing checkbox versus explicit-action presentation.
- Content changes need honest stale coverage; organizational moves preserve
  choices but re-evaluate joins. Word-level contribution highlights and coverage
  attribution could conflict; propose a clear mode precedence before adoption.

Three Producer questions were presented and have now been answered below.
The earlier recommendations alone did not establish these decisions:

1. Removing a partial: restore the most recent earlier choice for each word
   (recommended), or the longest earlier take? “Prior longer take” in the brief
   does not settle an overlap between several earlier choices.
2. VO words without an assigned cutaway: flag missing picture and require an
   actual placed cutaway to hide a cut (recommended), or treat the intended
   off-camera state as sufficient?
3. Rewritten recorded words: flag the affected reading for review while keeping
   it until explicitly replaced (recommended), or switch that affected reading
   to temporary voice? Do not silently splice generated single-word repairs.

The CLI also suggested punctuation-only retention, split/merge invariance,
specific underline treatments and auto-pausing Show Contributions. These remain
proposals, not facts established by the experiment or adopted requirements.
Its sample prose/range ordering must be checked before reuse; use a coherent
fixture with explicit word endpoints. No new capability gate is cleared.

## Producer answers — adopted 2026-10-30

- Removing a partial restores the most recently selected earlier reading for
  each affected word, rather than the longest take. This resolves ambiguous
  “prior longer choice” wording above.
- Off-camera words already have an assigned visual or a placeholder; that
  placeholder counts for hiding a presenter join. The hypothetical VO-with-no-
  visual state used in the question is invalid under this script model. Do not
  introduce an extra missing-picture gate for placeholders. The separate rule
  that a transparent graphic does not hide the presenter still applies.
- Rewriting recorded words flags the affected reading for review and retains
  it until explicitly replaced. Do not silently replace it with temporary voice
  or splice a generated replacement word. This does not establish a complete
  alignment-repair/staleness implementation.

All three consultation questions are resolved. Remaining presentation proposals
need a focused design comparison, not another backend proof campaign. No
Presenter Coverage construction is authorized merely by answering them.
