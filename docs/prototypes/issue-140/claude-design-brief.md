# Issue 140 — Claude Design connector-routing correction

## Bounded objective

Create a separate corrected successor to the accepted S03 v3 authoring
artifact. Change connector routing only: every numbered narration-to-visual
relationship must use its own nested lane, and connector lines must never
share route segments, cross, overlap, or intersect one another.

## Exact source and geometry authority

- Start from the attached accepted export
  `S03 v3 authoring artifact - issue 135 export v2.dc.html`.
- Accepted export size: `3,943,452` bytes.
- Accepted export SHA-256:
  `c6bdb9db77f4ce6484649a028c68d9dd49fcb72a8250b70c11cfd5d534ecfbea`.
- The attached Producer reference image is `904 × 1080`, `350,825` bytes,
  SHA-256
  `f408090f78509e522a79a8930bd4f9f43948091a66d66ed43826c995b20f2590`.
  It is the geometry authority: the four numbered relationships occupy four
  visibly separate nested lanes, with no shared connector segments or
  connector-to-connector intersections.

Create a new, separate Design artifact named:

**S03 v3 authoring artifact — issue 140 connector lanes**

Do not overwrite or rename the accepted S03 v3 artifact.

## Required correction

1. Preserve the accepted artifact's complete S01–S03 content, 22-row seed,
   authoring behavior, controls, typography, visual-card grammar, embedded
   images, review harness, and exact viewport controls.
2. Change only the connector-routing implementation wherever numbered
   narration ranges connect to visual cards.
3. Give every numbered relationship one dedicated nested lane. A relationship
   may use its own vertical and horizontal segments, but no part of its route
   may be shared with another relationship.
4. Order the nested lanes so the routes remain visually monotonic from the
   narration endpoints to the cards. No route may cross, overlap, touch, or
   intersect another route.
5. Preserve each relationship's number, color, narration start/end endpoints,
   and matching visual-card endpoint. The same relationship must remain
   traceable in both directions.
6. Exercise the dense four-connector row 8 and representative ordinary rows
   with one, two, and three numbered relationships.
7. At exact `1280 × 800` and `1024 × 768` viewports, connector lines must not
   touch cards, thumbnails, labels, readable narration, controls, or audio
   rails, and the document must have no horizontal overflow.
8. Preserve pointer and keyboard inspection. Hovering or focusing either
   endpoint must expose the same corresponding relationship, and keyboard
   focus must remain visibly outlined.

## Exclusions

- No change to S01–S03 wording, row order, sections, media assignments, anchor
  words, audio behavior, saved-state behavior, controls, or visual-card style.
- No new workflow, scenario, review foundation, #123 behavior, S05 behavior,
  production renderer, or Resolve integration.
- No visual redesign beyond the connector lanes.
- No replacement of the accepted artifact with a rough approximation.

## Deliverable and self-check

Produce the exact self-contained Claude Design source/export for the new
artifact. Before declaring it ready:

1. Compare row 8 at `1280 × 800` and `1024 × 768` against the attached nested
   lane reference.
2. Confirm one unique route per numbered relationship and zero shared route
   segments, crossings, overlaps, or intersections.
3. Confirm ordinary rows retain correct one-to-one number/color/endpoints.
4. Confirm no connector touches card or readable content and there is no
   horizontal overflow.
5. Confirm pointer and keyboard inspection still correspond with visible
   focus.
6. List every intentional difference from the accepted source. The expected
   list contains connector-routing code and resulting connector geometry only.

Return the new artifact's exact filename and a concise completion report. Do
not claim Producer acceptance.
