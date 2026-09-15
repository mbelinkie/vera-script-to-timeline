# Issue 123 plan — revise the Claude timeline-to-script reconciliation design

## Scope and authority

Issue #123 remains the active Sol/high, Producer-acceptance design slice for
reconciling changes made in a managed Resolve timeline back into the canonical
script. Its deliverable is the existing successor artifact in the Claude Design
project `VERA design feedback`, revised until the Producer accepts it. The
accepted S01–S05 artifacts remain unchanged.

The active claim is task `01a09d7d-49f0-7b12-b003-1163fb7d7959` on
`codex/issue-123-reconciliation-design`. Dependencies #14 and #58 are closed and
Done. #14 supplies S03, #58 supplies S05, and closed contract-design issue #56
supplies the more specific accepted row-bounded ordered-visual model used here.

This slice changes no production API, schema, fixture, compiler behavior,
generated type, or accepted artifact. A later technical story must reconcile
the design with frozen contracts and the broader product-spec language.

## Reconciliation decisions

VERA may compare the last applied build, current managed Resolve timeline, and
current script internally. The inbound review shows only Resolve-originated
changes. Script-only edits appear only when they intersect the same words,
audio item, or visual item as a Resolve change.

Reuse S05 wherever possible: white rows, script order, narration/production
columns, red/green comparisons with non-color labels, filters, controls,
selected/skipped counts, one-page scrolling, focus, and responsive reflow.

- Understood non-conflicting changes are preselected.
- Compatible intersecting changes require explicit **Combine both changes**.
- Incompatible changes have no default:
  - **Accept** adopts the Resolve result into the script.
  - **Reject** keeps the script and queues its version as default-selected in
    the next S05 update.
  - **Defer** changes neither side, resurfaces inbound, and remains unchecked
    in later outbound review.
- **Words cut** requires verified program-audio/transcript removal; a picture
  trim alone never deletes script words.
- **Reconcile script** may apply safe work while reporting deferred conflicts
  and partial out-of-sync status. It never changes Resolve.

## Rows, visuals, and Resolve additions

A row is an author-defined, closed visual container. Its length remains an
authoring choice, subject to these invariants:

- Non-audio visuals begin and end inside one row. Audio beds may span rows.
- A row may contain #56's ordered full-frame visual sequence plus simultaneous
  stacked overlays. Overlays may have overlapping ranges and explicit
  compositing order; the base full-frame sequence remains non-overlapping.
- A Resolve visual bridging adjacent narration rows creates one compound
  proposal: adopt the visual and merge the rows. Preserve words, paragraph
  structure, OC/VO state, anchors, comments, and identity through the merge.
- A valid merged row never splits automatically later.
- A visual crossing a section heading or other structural boundary blocks for
  review rather than merging across it.
- Content with no trustworthy spoken-word anchor uses a right-only visual row
  whose explicit timeline in/out defines its bounds.

**Added in Resolve** is provenance, not a content type:

- A fully understood accepted addition becomes an ordinary editable native
  card with a compact permanent **Added in Resolve** badge and history.
- An unsupported addition requires Accept/Reject/Defer. Accept creates a
  locked **Added in Resolve · Preserved as-is** card. It may be word-attached or
  a standalone right-only row and may have an optional descriptive name that
  never renders into video.

When an opaque upper visual completely covers lower picture, the inbound
comparison shows the covered material as evidence. After acceptance, only the
visible upper visual remains in the active script. The lower clips remain
dormant in Resolve and in reconciliation history; outbound updates preserve
them silently. If the upper visual is later deleted, verified dormant clips
becoming visible again are one preselected compound restoration proposal.
Partially visible lower footage remains in the script as stacked cards with
overlapping ranges.

Script/timeline agreement concerns effective visible and audible output, not an
exact duplicate of hidden Resolve track topology.

## Post-recording and outbound behavior

- Native understood visuals retime normally.
- An attached preserved-as-is clip moves its record start with a verified word
  anchor while retaining its source in/out and duration.
- When its fixed duration may no longer fit the row, VERA creates or updates one
  stable, non-rendered marker at the resulting outpoint, naming the item and
  asking the editor to confirm the ending.
- A verified safe fit receives no marker. A missing or ambiguous anchor blocks
  without movement or guessing.
- Standalone preserved-as-is content remains fixed; ambiguous collisions with
  changed surrounding timing block.
- Missing or unverifiable content is never replaced with a slate.

The later S05 examples must use actual white-row comparisons for rejected
script-wins changes, deferred unchecked changes, native and preserved additions,
dormant preservation/restoration, verified deletion, and missing-media blocking.

## Claude workflow and acceptance

1. Present the exact continuation prompt in
   `docs/prototypes/issue-123/claude-resolve-to-script-reconciliation-continuation.md`
   to the Producer. Do not send it until explicitly approved.
2. Continue the existing artifact
   **Script to Timeline — Resolve-to-Script Reconciliation S03** in the existing
   Claude project. Preserve the accepted S01–S05 artifacts.
3. Claude should ask focused questions when a material ambiguity remains, then
   implement and exercise the agreed states.
4. Retain evidence at `1280 × 800` and `1024 × 768` for S03 entry/no-change,
   native and preserved additions, compatible and incompatible conflicts,
   bridge-and-merge, overlapping layers, structural blocking, partial success,
   later S05 consequences, post-recording markers, unavailable/error states,
   naming, focus, non-color meaning, wrapping, scrolling, and overflow.
5. Move #123 to **In review** only after the artifact and evidence exist. Close
   only after explicit Producer acceptance.

## Follow-up record

After #123 acceptance, create the required technical story to prove row merging
and any cross-block representation, identity-preserving anchor/comment/history
migration, effective-output comparison, compositing order, native/preserved/
dormant identities, dormant restoration, verified audio-cut detection,
conflict/defer persistence, deletion, missing media, marker lifecycle, and all
required schema/generated-type changes.

Create a separate Producer-acceptance Inbox design issue, blocked by #123, for
drag-handle and keyboard reordering of ordinary S03 rows. It remains outside
#123 and is not Ready or authorized for implementation.

## Producer acceptance checklist

1. Open the exact successor artifact and confirm accepted S01–S05 files remain
   unchanged.
2. Confirm the S03 alert has a truthful count and no stale count when checking,
   in sync, or unavailable.
3. Confirm the inbound review feels like S05 in reverse and omits unrelated
   script-only edits.
4. Confirm safe, compatible, incompatible, rejected, and deferred decisions
   have the documented defaults and consequences.
5. Confirm bridge-and-merge rows, overlapping visual stacks, structural blocking,
   native and preserved additions, visual-only rows, dormant alternatives, and
   restoration are understandable.
6. Confirm post-recording marker placement and later S05 preservation/removal
   states are truthful and never invent or replace media.
7. Verify pointer and keyboard routes, non-color meaning, and no horizontal
   clipping at both viewports.
8. Reply `Accepted — update and close #123` or identify the first unacceptable
   state and expected correction.
