# #310 — provisional Sorting and saved-Stash capability handoff

All public functions below are exported from `@vera/contracts/authoring-v2`.
This extends #307's domain operations; it does not deliver an editor or lift
#125's design pause.

## Trial boundary

`createSortingTrialV2(canonical)` snapshots the complete saved authoring
document. Its `apply(command, expectedRevision?)` and `undo()` reuse #307's
row session. Script and Stash content are read-only in the trial: only
`move_rows`, `move_section`, `stash_rows` and `restore_stash` are accepted.

- `document` and `preview()` return isolated snapshots. Preview blocks row
  changes; `returnToSorting()` retains the intended result and Undo history.
- `accept(currentCanonical)` compares the complete current canonical document
  with the starting baseline, including Stash, content and live-head fields.
  A changed baseline refuses atomically; there is no collaboration merge.
- Successful acceptance returns the complete document and `changed`. The
  caller installs that result as one transaction. A changed result advances
  `rowEditRevision` once, regardless of the number of trial operations.
  No change returns the original canonical object without advancing it.
  Accepted/discarded sessions refuse repeated acceptance or further edits.
- `discard(currentCanonical)` leaves that canonical document untouched and
  closes the trial. Both trial surfaces and marks are cleared. A concurrent
  canonical edit is preserved rather than overwritten with the old baseline.
- `movedRowIds` includes only deliberately selected rows that remain away
  from their original section/row position or Stash bundle position. Rows
  merely displaced by another move are unmarked. Undo removes its selection
  from marking history; returning to the original position clears the mark.

`trial.serialize()` and `resumeSortingTrialV2(json)` provide a bounded local
round trip: complete baseline plus successful public row commands/Undo,
replayed through the same operations. Preview state, intended result, marks
and local Undo history survive. Limit: 1,000 successful actions, 5,000,000
serialized JavaScript string characters. No storage service, checkpoint
system, version migration or multi-client Undo is implied.

## Saved-Stash content

Outside a trial, `applyStashRowEditV2(document, expectedRevision,
{ bundleId, rowId, row })` replaces a complete saved row immutably. The row's
ID/type, bundle order/metadata, supporting attachments and document-level
relationships are retained. Text/tokens, annotations, OC/VO sequence boundaries,
visual payloads, source ranges and settings can change. Existing entity IDs
are retained in the proof; new entities receive new IDs. This is replacement
of authored content, not automatic text tokenization or anchor repair.

The normal serializer/validator rejects invalid schema, duplicate IDs and
invalid saved-row references. Parked semantic problems remain warnings and
are never silently repaired; restoring a row refuses newly active errors.
Stale revisions, missing targets, identity changes and no-change edits refuse
without mutation.

## Consumers and retained limits

Edited, unrestored Stash remains excluded from real prompter, timeline,
media-needs and Python narration/build consumers. Restore makes the edited
content eligible again. Changed narration requires fresh timing/audio under
the existing compiler rules; old audio is not silently reused.

#307's transition/audio intent rules still apply. Separated original pairs
retain their settings for review; new joins are cuts. Returning a row clears
its moved mark but does not silently reactivate an effect needing review, so
acceptance can honestly report a relationship-state change at the original
row order. Undo restores the previous relationship state exactly.

The adopted broken audio-span move follows its starting row, retains previous
settings/endpoints and uses “Music now ends with this row. Review”. Unsettled
audio-span operations still refuse. Real playback, trimming, mixing, fades,
arbitrary transition discovery and Resolve/media mutations remain unavailable.

Executable coverage: `row-edits-v2.test.ts`, `stash-edits-v2.test.ts`,
`row-edit-consumers-v2.test.ts`, and `tests/test_row_stash_v2_consumers.py`;
existing compiler golden and boundary tests remain unchanged.
