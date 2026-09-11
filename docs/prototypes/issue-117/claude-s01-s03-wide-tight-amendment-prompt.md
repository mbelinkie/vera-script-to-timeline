# Issue #117 — exact Claude Design amendment prompt

Status: **awaiting Producer approval; do not submit**.

The Producer must review this exact request and reply `send` or `send it`
before it may be submitted as plain text to the existing Claude Design
conversation `VERA design feedback`.

---

Create one new, separate VERA Suite design artifact named
**“Script to Timeline — Two-Column Authoring S01–S03 v3”** by duplicating the
Producer-accepted **“Script to Timeline — Two-Column Authoring S01–S03 v2”**
artifact and then editing only the duplicate. Preserve v2 unchanged as accepted
comparison evidence. Do not edit the original S01–S03 baseline, VERA Redesign,
Research, the shared system, any #32 artifact, or any S04–S19 artifact.

This is a small amendment to the accepted design, not a redesign. Preserve the
complete 22-row sample, endless white 60/40 document, near-black surround,
compact floating header, synchronized columns, range brackets and connectors,
card hierarchy, thumbnail and Authoring-size behavior, Preview/Trim, readiness,
Undo/history, reorder behavior, accessibility, responsive behavior, and every
other accepted v2 interaction unless this prompt explicitly changes it.

## Add one Wide/Tight control to every On Camera appearance

Add a compact segmented choice labeled **Wide** and **Tight** to:

- every ordinary `ON CAMERA` card; and
- every automatic `↩ ON CAMERA RESUMES` return.

Those are separate appearances. A return owns its own choice and may differ
from the parent On Camera card. No Logged Clip, Still Image, Onscreen
Placeholder, Need to Find, other B-roll visual, or `Visual Undefined` state may
show, announce, or retain this choice.

The control must fit the existing compact, non-expandable On Camera treatment.
Make its selected state obvious without relying on color and give the group and
both options accurate accessible names. It must work by pointer and keyboard,
including visible focus. Use normal two-option segmented-control behavior:
Tab reaches the group, arrow keys move between Wide and Tight, and Space/Enter
select when applicable. Do not add a settings panel, numeric zoom fields, an
inspector, a third treatment, or Resolve/color/audio controls.

When the user creates a new On Camera card or an automatic On Camera return,
seed it from the most recently authored On Camera treatment and immediately
store a separate explicit Wide or Tight choice. Changing an earlier appearance
later must not cascade into the new one. Undo and Redo must restore the exact
per-appearance choice.

## Picture behavior and continuity

Wide/Tight changes picture only. It must not imply that presenter footage or
dialogue was cut, restarted, skipped, repeated, duplicated, or retimed. A row
boundary alone is not a framing change: adjacent On Camera appearances with the
same treatment remain one continuous view. When adjacent appearances differ,
the treatment changes exactly at their authored boundary while the underlying
presenter recording and dialogue continue.

A B-roll cutaway temporarily covers that continuous presenter picture. Its
`↩ ON CAMERA RESUMES` return may come back Wide or Tight independently of the
parent. The return is not a new presenter take or a restarted source.

Do not add a waveform, source-time display, continuity badge, audio lane, color
panel, Resolve panel, or explanatory production copy to the product interface.
This continuity is interaction behavior and test-harness state, not a new
permanent UI surface.

## Presenter preview treatment

When the Project or Script has a configured presenter still and `Show presenter
thumbnail` is enabled, use that same still for both treatments: Wide shows the
wider composition and Tight shows a clearly closer crop. Changing the control
updates that appearance's thumbnail immediately. Any temporary preview that
uses the still in place of recorded presenter picture must use the selected
treatment for that appearance as well; never carry the presenter crop onto
B-roll.

When no presenter still exists, keep the accepted neutral silhouette concept
but provide two unmistakably different treatments: Wide shows more of the
presenter/body and surrounding frame; Tight shows a closer head-and-shoulders
composition. Do not use text-only `PRESENTER` tiles and do not rely on color to
distinguish them. Hiding presenter thumbnails still collapses the image exactly
as v2 does; the Wide/Tight text choice remains visible and operable.

## Amend only these sample appearances

Keep the accepted row order, count, narration, visuals, timing cases, and
placeholder rules except for the one phrase change named below.

1. Row 2, the On Camera greeting: set the ordinary On Camera card to **Wide**
   and its return after the future lower-third placeholder to **Wide**.
2. Row 6, the exact On Camera cutaway: set the parent On Camera card to **Wide**
   and `↩ ON CAMERA RESUMES` to **Tight**. In the narration, replace only
   `When we return to the wider view` with `When we return to me` so the copy no
   longer contradicts the authored return treatment.
3. Row 7, the backward-derived cutaway: set both the parent and return to
   **Tight**.
4. Row 18, the notebook demonstration: set the On Camera card to **Wide**.
5. Row 19, the adjacent closing On Camera row: set the On Camera card to
   **Tight**.

Rows 18 and 19 are the required direct `Wide → Tight` example. Treat them as
adjacent pieces of one continuous presenter recording and dialogue even though
the authoring row changes. Row 6 is the required
`Wide → B-roll cutaway → Tight return` example with no presenter-source or
audio restart. Rows 2 and 7 show that a temporary cutaway or row/card boundary
does not manufacture a framing change when the explicit choices are equal.

## Interaction and regression verification

Exercise the completed v3 artifact rather than stopping after describing it.
At both **1280 × 800** and **1024 × 768**, verify:

- every ordinary On Camera card and every On Camera return has exactly one
  visible, accessible Wide/Tight choice;
- no non-presenter visual has the control or an accessibility-only framing
  value;
- pointer selection, Tab focus, arrow-key movement, Space/Enter behavior, and
  visible focus all work;
- changing a treatment updates the configured-still preview immediately;
- the no-custom-still state uses distinct non-color Wide and Tight silhouettes;
- `Show presenter thumbnail` off hides only the thumbnail, not the choice;
- adding a new On Camera appearance after a Tight appearance starts with an
  explicit Tight choice, can be changed independently, and Undo/Redo restores
  each state exactly;
- row 6 remains one Wide presenter source covered by B-roll and returning Tight,
  with no source restart or dialogue interruption in the simulation state;
- rows 18–19 change Wide to Tight exactly at their boundary; setting both to
  Wide creates no framing change merely because a row boundary exists, and
  Undo restores the required Wide/Tight example;
- all controls remain inside the right column with no clipping, horizontal
  overflow, card collision, broken connector, hidden focus ring, or independent
  column scrolling;
- readiness results, word-range editing, card menus, insertion, reorder,
  thumbnail sizes 0/intermediate/100, Authoring-size extremes, Preview/Trim,
  simulated reload, and the 13-placeholder zero-swap-instruction rule remain
  unchanged from accepted v2.

Fix any issue found during that verification before replying. In the final
response, name the exact v3 artifact, list the changed appearances, report the
pointer/keyboard/preview/carry-forward/Undo checks at both viewports, confirm
that v2 remained unchanged, and identify any remaining limitation. This work
prepares issue #117 for Producer review; it does not accept or close the issue.
