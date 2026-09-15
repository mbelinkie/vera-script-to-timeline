Continue working on the existing artifact:

**Script to Timeline - Resolve-to-Script Reconciliation S03.dc.html**

in the existing Claude Design project `VERA design feedback`.

Do not edit either Producer-accepted source artifact:

- `Script to Timeline — Two-Column Authoring S01–S03 v2`
- `Script to Timeline - Prompter Runtime and Suite Navigation S04-S06`
  (the historical filename contains accepted S04 and S05 only)

Reuse the accepted S05 design as much as possible, especially its white script
rows, typography, two-column structure, red/green comparisons with non-color
labels, filters, selection controls, counts, focus behavior, scrolling, and
responsive layout. Continue using your own design judgment. Before editing,
ask Matthew focused questions if any instruction below conflicts with the
current artifact or exposes a material edge case we have not resolved.

## Correct the row model

Rows are author-defined, useful units of content with a clean beginning and
end. A row is a closed visual container:

- Non-audio visuals cannot begin before its first word or end after its last
  word.
- Audio beds are the exception and may run across rows.
- A row may contain #56's ordered, non-overlapping full-frame visual sequence
  plus simultaneous stacked overlays. Overlay ranges may overlap the base
  picture or one another; show their ranges and compositing order clearly using
  the established S03 interaction language.
- If a Resolve visual bridges adjacent narration rows, accepting it is one
  compound change that adds/adopts the visual and merges those rows. Preserve
  every word, paragraph, OC/VO state, anchor, comment, and identity. Do not show
  a visual card spanning multiple rows.
- A valid merged row remains merged if that bridge is later shortened or
  deleted. VERA never auto-splits it merely because a split becomes possible.
- A visual crossing a section heading or other structural boundary cannot
  trigger a merge. Show a blocked review state instead.
- Footage with no trustworthy spoken-word anchor becomes a right-only visual
  row whose explicit timeline in/out defines the row bounds.

Revise the current one-sentence sample rows so they demonstrate this model
rather than implying every sentence or shot must be its own row. Replace the
current row-spanning highlight-reel after-state with the accepted compound row
merge.

## Use effective visible output, not hidden track inventory

Keep stacked cards for visuals that are simultaneously visible, such as a lower
third over On Camera. Overlapping ranges are valid.

When an opaque upper-track visual completely hides lower picture:

- Show the covered lower clips in reconciliation as comparison evidence.
- After acceptance, remove those fully hidden visual cards from the active
  script. The ordinary script shows what the viewer currently sees.
- Preserve the hidden lower clips silently in Resolve and reconciliation
  history as dormant alternatives; do not show grey dormant rows in the
  ordinary script and do not remove them during later outbound updates.
- If the editor later deletes the covering clip and the known lower clips
  become visible again, show one preselected compound inbound proposal that
  removes the covering card and restores the verified dormant cards to the
  script.
- If lower material is only partially hidden, keep it in the active script and
  show the overlapping ranges and layer order.

Treat script and timeline as reconciled when their effective visible and
audible output agrees. Hidden Resolve topology need not appear in the script.

## Replace Resolve-only terminology

Use **Added in Resolve** as provenance, not as a content type or a synonym for
unsupported content.

- A fully understood addition is selected by default. Accepting it creates an
  ordinary editable native card of the correct type, with a compact permanent
  **Added in Resolve** provenance badge and retained history.
- An unsupported or ambiguous addition is not automatic. It requires Accept,
  Reject, or Defer like other Resolve-originated changes.
- Accepting unsupported material creates a locked
  **Added in Resolve · Preserved as-is** card. Support a word-attached card and
  a standalone right-only row. Offer an optional descriptive name such as
  `Pre-made highlight reel`; make clear that the name is metadata and never
  appears in the video.
- Reject keeps the script and queues removal/correction in the next S05 update.
  Defer changes neither side and resurfaces later.
- Keep preserved-as-is cards collapsed but visible in ordinary script editing.

Fix the current naming-state bug in which opening the name field for one added
clip can reuse another added clip's name.

## Reconciliation decisions and evidence

The inbound review shows only Resolve-originated changes. Script-only changes
stay canonical and absent unless they intersect the same words, audio item, or
visual item as a Resolve change.

- Preselect understood non-conflicting changes.
- When intersecting changes are compatible, require explicit
  **Combine both changes** confirmation.
- For an incompatible change, select nothing initially and offer:
  - **Accept** — adopt the Resolve result into the script.
  - **Reject** — keep the script; queue its version as default-selected in the
    next S05 update. Do not imply Resolve changes immediately.
  - **Defer** — change neither side, resurface inbound, and leave it unchecked
    in later S05 review.

Include these concrete conflicts:

1. Compatible: the script inserts prose before a stable visual anchor while
   Resolve lengthens that same visual's outpoint. Show how both results can be
   combined, but require confirmation.
2. Incompatible: the author splits a row at a chosen sentence boundary while
   Resolve adds a visual crossing that exact boundary. Accept merges the rows;
   Reject keeps the split and queues correction of the Resolve visual; Defer
   leaves the mismatch.

Retain a partial-success result where other work completes but deferred changes
leave script and timeline partly out of sync. Repair the current “deferred last
time” state so its selected control and counts actually show a deferred change.

For **Words cut**, demonstrate a verified cut to program VO or on-camera audio
and its aligned transcript. Do not infer removed words from a B-roll or picture
trim.

Remove “visual note,” “notes it,” and similar ambiguous language. Use visual,
clip, card, row, or the actual media type.

## Post-recording timing behavior

Native understood visuals retime normally when presenter timing replaces the
temporary narration.

For a word-attached **Preserved as-is** clip:

- Move its record start with its verified start-word anchor.
- Preserve its source in/out and duration; do not trim, stretch, freeze, loop,
  or otherwise alter its source edit.
- If the fixed duration may no longer end cleanly inside the row, add or update
  one stable, non-rendered VERA timing-review marker at the resulting outpoint.
  The marker names the clip and asks the editor to confirm the ending.
- A later build updates the same marker rather than adding another.
- If ending fit is verified, create no marker.
- If the intended start anchor is missing or ambiguous, block without moving
  the clip or guessing.

Standalone preserved-as-is content has no word anchor and remains fixed. If
changed surrounding timing creates an ambiguous collision, block for review.

## Required corrected states

Keep the good existing S03 changed, in-sync, checking, unavailable, observation
failure, partial-result, focus, and responsive treatments, then add or correct:

- understood added content becoming a native card with its provenance badge;
- attached and standalone preserved-as-is additions and optional naming;
- collapsed ordinary-script presentation;
- compatible and incompatible intersecting changes;
- verified program-audio Words cut;
- bridge-and-merge acceptance and blocked structural-boundary span;
- sequential and overlapping visible visual stacks;
- opaque coverage with dormant alternatives absent from ordinary script;
- later verified reveal restoring dormant cards;
- actual S05 white-row future states for Reject selected by default, Defer
  unchecked, native/preserved/dormant preservation, verified deletion, and
  missing/unverifiable content blocking without a slate;
- post-recording safe fit, outpoint marker, marker update, missing anchor, and
  standalone collision states.

Exercise and verify all required states at internal `1280 × 800` and
`1024 × 768`, including pointer and keyboard routes, visible logical focus,
non-color meaning, readable errors, wrapping, vertical scrolling, and no
horizontal overflow.

Keep every action simulated. Do not create or claim production Resolve
inspection, synchronization, persistence, script mutation, timeline building,
APIs, schemas, contracts, fixtures, generated types, or Producer acceptance.
After implementing, report the exact artifact, states exercised, S05 reuse,
accessibility/responsive results, edge cases you found, and any remaining
Producer decision. Stop after this artifact revision.
