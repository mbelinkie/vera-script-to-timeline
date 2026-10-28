# #342 — editable Sorting and selective resolution

This extends the real #310 trial and #337/#340 saved-row operations. It is a
domain API for #125/#62 and later editor owners; delivery still requires this
branch's review, green full CI and merge. It does not resume design construction.

## Public operations

Import from `@vera/contracts/authoring-v2`:

- `createSortingTrialV2(canonical)` owns the complete pending document.
  `apply(command, expectedRevision?)`, `undo()`, `document`, `revision`,
  `undoDepth`, `movedRowIds`, `preview()` and `returnToSorting()` keep the #310
  transaction boundary. Preview snapshots are isolated and content is read-only.
- `RowEditCommandV2` retains row/section moves, independent Stash restore,
  section/outline organization and #340 note/clip creation/branch placement.
  It adds `edit_row { rowId, row }`, `create_row { row, destination }` and
  `delete_rows { rowIds }`. `edit_row` replaces an active or saved row while
  preserving ID/type and protected Stash origin. This is complete authored
  content replacement, not automatic tokenization or text-anchor repair.
- #341's `make_stage_direction`, `make_spoken` and
  `delete_direction_delimiter` are also row-session/trial commands. Their
  bounded offset, token, paired-bracket and anchor rules remain unchanged.
  Every successful operation has one full-document local Undo snapshot.
- `accept(currentCanonical, outcome?, comments?)` defaults to `"all"`.
  Alternative outcomes are `"edits_only"` and `"sorting_only"`.
  `discard(currentCanonical, comments?)` is separate. Acceptance returns a
  complete document plus `changed`, advancing `rowEditRevision` once when
  changed. The caller installs the complete result atomically.

## Classification and identity

Moves, Stash placement/return, section order and outline organization count as
organization. Authored row content and row creation/deletion count as edits.
Each selective outcome composes row snapshots and organization by stable ID;
it does not filter and replay commands against a partially reconstructed script.

Edits-only restores baseline organization, retains authored content/deletion
and places surviving new rows at their exact birth locations. A note placed
from Stash and then edited returns to its original Stash location as an edited
ordinary row. Editing a compact item while it stays in Stash preserves its
compact kind, as in #340.

Sorting-only retains organization with baseline content. Deleted baseline rows
return to their last known sorted locations. New rows are removed, together
with moves whose sole destination was a discarded new row. Unedited converted
notes/clips retain their original content and outline-return eligibility.

The projection retains creation/deletion and placement provenance separately
from the visible document. A missing exact birth/deletion slot, missing parent
or section, incompatible parent kind, or unsafe attachment split refuses the
whole selective result. The pending document and Undo history remain available.
An edited parent that must become an ordinary Stash row cannot silently retain
note-only children or flatten them; that incompatible result refuses.

## Comments are separate discussion state

Keep `CommentStateV2` on the current canonical document while Sorting is pending.
Use ordinary `applyCommentOperationV2` for create/reply/resolve/reopen/reattach.
Discussion activity neither enters row Undo nor changes conversion eligibility.
Do not replace the comment document for temporary preview moves/deletions.

For finalization, pass `{ state, id, actorId }` as the optional `comments`
argument. `resolveSortingCommentsV2(canonical, intended, context)` is the same
public seam outside a trial. It validates discussion history and the canonical
document, then reconciles once against the chosen result through #324's real
`replace_document` operation. The returned `comments` must be installed with
the returned document. Failure refuses trial finalization before either changes.

Messages/replies survive all outcomes. A retained deleted/moved/rewritten target
uses #324's attached/stale evidence rules; restoration by sorting-only or Discard
does not first orphan an unchanged baseline target. Already stale threads stay
stale and explicit reattachment is still required. This API does not support
comments created against rows that exist only in pending work: a discussion
document differing from canonical refuses finalization rather than losing them.
No concurrent discussion merge or persistent comment service is supplied.

## Recovery and boundaries

`serialize()` / `resumeSortingTrialV2(json)` replay the complete successful
public action/Undo history, rebuilding content, projection provenance, marks,
eligibility and local Undo. Preview/Return survives reload. The unchanged local
format is `sorting-trial/v1`: at most 1,000 edits plus their Undos and 5,000,000
JavaScript string characters. Save discussion state separately with
`serializeCommentStateV2` / `deserializeCommentStateV2`.

Acceptance still compares the complete outside canonical document with its
starting snapshot. Own pending edits are valid; an outside change atomically
refuses and preserves pending work. Discard preserves the supplied current
canonical document, including outside changes.

Deletion requires safe complete row selections and complete selected Stash
branches. It removes row-local supporting items/references and refuses cross-row
attachments, intersecting audio spans and unsafe transition/origin dependencies.
Creation requires an identity not already used in the pending trial; restore a
deleted row with Undo rather than creating a different row under its identity.
Undo restores content, attachments, relationships and eligibility together.
Existing #307/#310/RK-42 audio and transition limits remain. Changed active
narration requires fresh timing/audio; compiler output rules are unchanged.

No production UI, storage service, collaboration merge, native Resolve/media
operation, provider, upload or paid service is included. No persisted schema or
generated contract changes are required; existing compiler goldens stay intact.
