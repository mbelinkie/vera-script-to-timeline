# Issue 127 bounded S03 successor handoff

Status: **accepted by the Producer on 25 September 2026**

## Exact artifact and authority

- Successor candidate: `s03-successor-pilot.dc.html` (self-contained; runtime,
  shared CSS, and referenced thumbnails are bundled into this file)
- Automated check: `check-successor.mjs`
- Accepted source copy: `source-v2/Script to Timeline - Two-Column Authoring S01-S03 v2.dc.html`
- Accepted-source SHA-256: `632cfce2b9fea8832b7c13387811d5739518f1247d10bb81ae605671b2005535`
- Source authority: accepted S03 v2 from #14 at commit `11cef62`

Accepted v2 remains unchanged. The successor is a separate duplicate retaining
its ordinary editing controls. Its accepted rules are input to a later complete
combined S03 v3; this bounded artifact does not itself replace accepted v2.

## Exact bounded cases

1. A full-frame Web Capture covers Row 1 from its first word through
   `successful upload.` Its quiet singleton ordinal is `1`; the later presenter
   interval is the row's first **On Camera**, not a resume.
2. Row 2 resets numbering. An unindented transparent lower-third Graphic is
   `1`; an opaque footage cutaway is `2`; only the genuine return after that
   cutaway says **On Camera resumes**.
3. Row 3 has Footage `1`, Graphic `2`, and Footage `3`. The Graphic's independent
   range crosses the boundary between both clips without belonging to either.
4. Row 4 has a quiet singleton full-frame Need to Find `1`. Found footage
   replaces the card while retaining ordinal `1` and identical word anchors.
5. Row 5 has a quiet singleton Footage `1`, followed by the row's first
   **On Camera** interval, plus a music bed contained within the row.

## Adopted rules

- Visual ordinals reset to `1` in every semantic row and follow start-anchor
  order; a base visual precedes an overlay when both start on the same word.
  Singletons stay visible with quieter styling.
- Clip/full-frame ranges use enclosing brackets. Transparent Graphic ranges use
  straight endpoint ticks (`│2` and `2│`); an optional spoken trigger diamond
  precedes the opening tick. The dashed perimeter belongs to the Graphic card,
  never to a persistent narration underline.
- A transparent Graphic is an independent layer with its own word range. It is
  not indented under, parented to, or returned from a base clip.
- Ordinary card faces carry one primary type pill. Opacity, composition,
  provenance, and replacement behavior live in accessible names and Details.
- On Camera means the presenter is visible. **On Camera resumes** is reserved
  for a later return after an earlier presenter interval and an intervening
  opaque cutaway.
- Music uses a document-wide `M1`/`M2` namespace separate from row-local visual
  ordinals. `M1` spans Rows 1–3 from `publishes` through `falls`; `M2` starts and
  ends inside Row 5. Focus/hover reveals those anchor words without inserting
  music brackets or identifiers into the prose.

## Rejected from the first successor pass

- Global visual numbering across rows.
- `Transparent overlay`, `Opaque cutaway`, `Opaque moving imagery`, ranged
  request, or replacement-status secondary pills on ordinary card faces.
- Overlay indentation, parent-clip ownership, or synthetic overlay-return rows.
- Music identity rendered as `⟦6 … 6⟧` inside narration.
- Calling the first presenter-visible interval in a row a resume.

## Downstream rule for #123 and successor S05

Human references use **row identity plus row-local visual ordinal**; stable IDs
remain the machine identity. Reconciliation and outbound updates must preserve
the visual's exact row, ordinal, layer kind, and word anchors. Music retains its
separate `M` identity. Neither downstream surface may flatten a Graphic into a
cutaway or synthesize music text inside narration.

## Verification and stop condition

`rtk node docs/prototypes/issue-127/check-successor.mjs` renders four states at
`1280×800` and `1024×768`, with default and small text plus default and 0%
thumbnails. It verifies the accepted-source hash, row-local numbering, quiet
singletons, non-orphaning clip and Graphic endpoints, independent cross-clip
Graphic coverage, correct host-state labels, no secondary coverage pills,
pointer/keyboard parity, two independent music cases, no music glyphs in prose,
card fit, request replacement with identical anchors, and that the handoff HTML
has no local `source-v2` dependency.

Retained screenshots are in `successor-evidence/`. Claude requested no bounded
revision, and the Producer responded `Issue #127 successor accepted` on 25
September 2026. Relative font-size calibration is deferred to the later complete
combined S03 v3. Propagation to #123/S05 remains a separate downstream slice.
