# Issue 127 plan — successor S03 canonical row system

## Authority and current milestone

Issue #127 is the active Sol/high design story. The accepted source is
`Script to Timeline - Two-Column Authoring S01-S03 v2.dc.html`, accepted under
#14 at commit `11cef62`. The unaccepted v3 artifact, #123 experiments, S05, and
production contracts remain evidence or downstream consumers, not authority to
change ordinary S03 authoring.

The controlled comparison ended when the Producer selected numbered visuals
with quieter singleton ordinals. The first successor pass was rejected during
Producer review. The corrected bounded successor passed its retained checks,
was imported into Claude as **Script to Timeline - S03 Successor Pilot - Issue
127**, received no requested revision, and was explicitly accepted by the
Producer on 25 September 2026.

## Slice ritual

- **Scope:** one successor copied from accepted v2, with five corrected visual
  rows and two music-bed cases: a Web Capture, transparent lower third plus
  opaque cutaway, Graphic spanning two base clips, ranged Need to Find with
  stable replacement, cross-row music, and contained-row music.
- **Exclusions:** no accepted v2/v3, #123, S05, production UI, persistence,
  schema, compiler, contract, fixture, golden, generated type, Resolve, or
  Fusion-content-editor change. No promotion before Producer acceptance.
- **Touched contracts/fixtures:** none.
- **Dependencies:** none added.
- **Automated check:** preserve the accepted-source hash and render default and
  small/0%-thumbnail states at `1280×800` and `1024×768`; verify numbering,
  range geometry, host-state wording, pointer/keyboard parity, music controls,
  replacement anchors, wrapping, card fit, and overflow.
- **Acceptance:** reconcile one focused Claude critique, then give the Producer
  the exact artifact and checklist. #127 stays open and not Done until explicit
  Producer acceptance.

## Settled design rules

- Visual ordinals reset in every semantic row. Timed non-On-Camera visuals are
  ordered by start anchor, with a base visual before an overlay on a tie. A
  singleton keeps a visible but quieter `1`.
- Human references use row identity plus row-local ordinal. Stable object IDs
  remain the downstream machine identity.
- Full-frame visuals use enclosing bracket endpoints and create VO over their
  range. Transparent Graphics use straight endpoint ticks and coexist with the
  base. Their cards have a fine dashed perimeter and no indentation, parent
  clip, return item, or persistent narration underline.
- Ordinary cards have one primary type pill. Composition, opacity, provenance,
  and replacement semantics live in accessible names and on-demand Details.
- The first presenter-visible interval in a row is **On Camera**. **On Camera
  resumes** is reserved for a genuine later return after an earlier presenter
  interval and an intervening opaque cutaway.
- Music uses a separate document-wide `M` namespace. Its thin right rail may
  cross independent rows without merging them. Focus/hover exposes exact word
  anchors plus trim/fade controls without inserting music marks into prose.

## Corrected scenario

| Row | Visual behavior | Music behavior |
| --- | --- | --- |
| 1 | Web Capture `1` from the first word through `successful upload.`; later plain On Camera | `M1` starts on `publishes` |
| 2 | Transparent Graphic `1` over continuous On Camera; opaque Footage `2`; genuine On Camera resume | `M1` continues |
| 3 | Footage `1`, Graphic `2` spanning the base-clip boundary, Footage `3` | `M1` ends on `falls` |
| 4 | Full-frame Need to Find `1`, replaced at identical anchors; later plain On Camera | None |
| 5 | Full-frame Footage `1`; later plain On Camera | `M2` starts on `a short` and ends on `sting fades` inside the row |

## Retained verification

Run:

```sh
rtk node docs/prototypes/issue-127/check-successor.mjs
```

Expected result: four states pass; accepted-source SHA-256 remains
`632cfce2b9fea8832b7c13387811d5739518f1247d10bb81ae605671b2005535`.
Screenshots are retained under
`docs/prototypes/issue-127/successor-evidence/`.

The check fails if visual ordinals do not reset, a singleton loses its number,
a Graphic uses clip brackets or indentation, its cross-clip anchors drift,
music identifiers enter narration, M1/M2 merge rows, first On Camera intervals
are mislabeled, secondary coverage pills return, the ranged request changes
anchors when fulfilled, focus/range inspection fails, or either viewport clips.

## Claude and Producer acceptance

Send only the corrected artifact, retained screenshots, `successor-handoff.md`,
and the bounded prompt in `claude-successor-critique.md`. Claude returns either
**Ready for Producer review** or **Needs one bounded revision** and may name only
the first unacceptable state plus the smallest correction.

After reconciling that response, the Producer opens the exact candidate and:

1. Confirms Row 1 has no stray music text and ends in plain On Camera.
2. Confirms each row resets visual numbering and singleton `1`s stay visible.
3. Confirms Row 2's Graphic is an unindented transparent layer and only the
   opaque cutaway owns the On Camera resume.
4. Confirms Row 3's `◇│2 … 2│` Graphic spans Footage `1` and `3` while all
   three cards/ranges remain independently inspectable.
5. Confirms Row 4's request is full-frame/VO and replacement retains `1` plus
   both anchors, with explanation confined to Details.
6. Confirms M1 crosses three independent rows, M2 stays inside Row 5, and both
   expose exact anchors, trim, and fade without altering prose or row height.
7. Repeats at `1024×768`, small text, and 0% thumbnails, then responds exactly:
   - `Issue #127 successor accepted.`
   - `Issue #127 successor needs revision: <first unacceptable state>.`
   - `Issue #127 successor rejected: <reason>.`

Both gates were satisfied on 25 September 2026. The Producer's exact response
was `Issue #127 successor accepted`. Relative font-size calibration was
deliberately deferred to a later complete, combined S03 v3 artifact, where the
full document hierarchy can be judged together. #123, S05, contracts, fixtures,
and production code remain unchanged by this slice.
