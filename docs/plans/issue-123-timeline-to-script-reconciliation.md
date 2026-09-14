# Issue 123 plan — Claude design for timeline-to-script reconciliation

## Scope and authority

Issue #123 is the active Sol/high, Producer-acceptance design slice for reconciling
changes made in a managed Resolve timeline back into the canonical script. The
deliverable is a new Producer-approved Claude Design artifact in the existing
`VERA design feedback` project. The accepted S01–S03 and S04–S05 artifacts remain
unchanged.

The active claim is task `01a09d7d-49f0-7b12-b003-1163fb7d7959` on
`codex/issue-123-reconciliation-design`. Dependencies #14 and #58 are closed and
Done. #14 supplies the accepted S03 authoring surface; #58 supplies the accepted
S05 change-review language that this design deliberately reuses in reverse.

The checked-in HTML prototype and its screenshots were created before the
Producer reframed the workflow. They are exploratory reference only and are not
acceptance evidence.

## Slice ritual

Scope: revise the live issue, prepare and obtain Producer approval of the exact
Claude brief, create one successor Claude artifact, retain both required viewport
presentations, and provide a Producer walkthrough.

Exclusions: no Resolve observation or sync, diff engine, persistence, script
mutation, timeline build, authorization, production UI, API, schema, contract,
fixture, golden, generated-type, or accepted-artifact change.

New dependencies: none. A separate technical story created after design
acceptance will block implementation and define the observation, identity,
anchoring, preservation, deletion, reverse-mapping, and manual timing-marker
contracts.

## Product decisions

The comparison may use the last applied immutable build, current managed Resolve
timeline, and current script internally, but the user-facing review lists only
changes originating in Resolve. Script-only edits remain canonical and do not
require inbound approval.

The review reuses S05 wherever possible: white script rows, script order,
two-column narration/production structure, red/green before-and-after treatment,
non-color labels, row controls, filters, selected/skipped counts, one-page
scrolling, focus treatment, and responsive reflow.

- Understood, non-conflicting Resolve changes are preselected.
- Compatible same-row changes require explicit **Combine both changes**.
- Incompatible same-row changes have no default. The choices are:
  - **Keep current script — update Resolve next time**: suppress this inbound
    conflict and select the row by default in the next S05 outbound review.
  - **Adopt Resolve into script**: available only when VERA has a safe reverse
    representation.
  - **Defer**: change neither side, resurface the conflict in later inbound
    reviews, and leave the row unchecked by default in later S05 reviews.
- Other selected work may complete while a conflict is deferred. The result
  must say that the script and timeline remain partially out of sync.
- The primary action is **Reconcile script**. It updates the script or records
  explicit decisions; it never creates or updates a Resolve timeline.

## Resolve-only content

Reuse the existing placeholder card grammar with reversed ownership:

- **Onscreen Placeholder** is script-owned future intent that VERA renders as a
  stand-in.
- **Resolve-only content** is existing Resolve-owned material that VERA records
  and preserves without interpreting, rebuilding, or replacing it.

Recognized-but-unrepresentable and ambiguous/unrecognized timeline content is
automatically recorded as a locked Resolve-only row. It may be attached beside
understood narration when a trustworthy anchor exists, or standalone between
the nearest trustworthy rows when no safe anchor exists.

Every row retains the permanent system label **Resolve-only content** and offers
an optional editable descriptive name, such as `Pre-made highlight reel`. The
name is metadata only and is never rendered into video. Rows remain collapsed
but visible in ordinary script editing.

Attached content moves only with a verified anchor. Standalone content stays
fixed. Ambiguous movement, overlap, order, or timing collisions block the
affected operation for review. Future outbound updates preserve these regions
unchanged while continuing to update understood content around them. Missing or
unverifiable content is never replaced with a slate.

VERA continues observing the reference. A verified Resolve deletion appears as
a preselected proposed row removal; completing reconciliation removes the row
while retaining its descriptive name in reconciliation history.

After presenter footage replaces temporary narration timing, understood
word-anchored edits recompile to the recorded words. Resolve-only media remains
untouched. When its governing word anchor moves and the preserved edit may need
manual timing, VERA adds or updates one stable, non-rendered manual timing review
marker at the recalculated anchor. The marker names the Resolve-only row and
asks the editor to inspect its start and ending. Missing or ambiguous anchors
block instead of producing a guessed marker.

## Claude workflow and acceptance

1. Present the exact brief in
   `docs/prototypes/issue-123/claude-resolve-to-script-reconciliation-brief.md`
   to the Producer and do not send it until explicitly approved.
2. In Claude Design, create a new successor artifact named
   **Script to Timeline — Resolve-to-Script Reconciliation S03**. Preserve the
   accepted S01–S05 artifacts unchanged.
3. Claude first inspects the accepted S03 and S05 artifacts, proposes its design
   concept, and asks Matthew focused questions about material choices and missed
   edge cases. It waits for answers before editing.
4. Claude implements and exercises the agreed design, fixing issues it finds.
5. Retain evidence at `1280 × 800` and `1024 × 768` for the counted S03
   entry/no-change states, understood changes, compatible and incompatible
   same-row changes, both Resolve-only placements and naming, collapsed script
   presentation, later S05 preservation/script-wins/defer/removal states,
   post-presenter retiming with a manual timing review marker, partial success,
   unavailable/error states, keyboard focus, non-color meaning, and overflow.
6. Move #123 to **In review** only when the Claude artifact and evidence exist.
   Close only after explicit Producer acceptance.

## Producer acceptance checklist

1. Open the exact Claude Design artifact named above and confirm it is separate
   from the accepted S01–S05 artifacts.
2. Confirm the S03 entry makes a managed-timeline change obvious, states the
   number of changes to review, and offers a matching counted action without a
   false or stale count in no-change and unavailable states.
3. Confirm the review feels like S05 in reverse, uses white script rows, and
   omits script-only changes.
4. Confirm safe changes are preselected; same-row changes require the documented
   explicit decisions; script-wins and defer produce distinct future behavior.
5. Confirm attached and standalone Resolve-only rows, optional naming, collapsed
   script presentation, preservation, collision blocking, verified removal, and
   post-presenter manual timing markers that never alter opaque media.
6. Confirm completion can apply safe work while accurately reporting deferred
   conflicts and partial out-of-sync status, without claiming Resolve changed.
7. At both required viewports, verify pointer and keyboard routes, focus order,
   readable non-color states, and no horizontal clipping.
8. Reply `Accepted — update and close #123` if acceptable, or identify the first
   unacceptable artifact state and expected correction.
