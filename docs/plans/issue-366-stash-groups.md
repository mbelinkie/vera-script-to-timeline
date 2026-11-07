# Issue #366 — persisted Stash row groups

## Domain boundary

Groups are optional metadata (`stashGroups`) referencing canonical row IDs; they are **not** Stash bundles or duplicate row payloads. A valid group contains at least two consecutive, same-section/same-parent ordinary `row` entries in `stashOutline`. Its members stay in their original `stash` bundles with existing content, member authorship, citations, supporting items and attached-footage owner. A group can be nested directly under a compact Stash `note`, never another group. The section/parent slot is conveyed by each member's outline entry, not a second group location record. Old documents without `stashGroups` are unchanged.

## Phase 2 — atomic public commands

All commands below use `applyRowEditV2(document, expectedRevision, command)` or `createRowEditSessionV2`; one successful call is one `rowEditRevision` increment and one Undo entry. Inputs must be JSON/plain exact commands. Refusals leave the caller's document untouched.

| Command | Required parameters | Effect |
| --- | --- | --- |
| `group_stash_rows` | `groupId`, ordered `rowIds` (2+) | Convert consecutive saved siblings (including an eligible compact note/clip) to full ordinary members and attach group metadata; optional `createdBy`/`createdAt` are **explicit caller-supplied**, never inferred from members. |
| `stash_group_rows` | `groupId`, `bundleId`, ordered contiguous Draft `rowIds`, `sectionId`, `parentRowId`, `afterRowId` | Stash the Draft selection together using the regular origin/supporting-item/attachment guards, convert to full rows, insert the group at the specified Stash sibling slot; optional creator metadata as above. |
| `move_stash_group` | `groupId`, `sectionId`, `parentRowId`, `afterRowId` | Move the entire group as one contiguous block to a valid section or compact-note child location. |
| `ungroup_stash_group` | `groupId` | Remove only group metadata; keep all canonical saved rows and their outline locations. |
| `delete_stash_group` | `groupId` | Remove metadata and all member rows through existing row-deletion, audio, attachment and relationship guards. |
| `place_stash_group` | `groupId`, `destination: RowGapV2` | Transfer all member rows at once into the exact Draft gap, updating supported attachment visuals and associated supporting items. Delete the group metadata; resulting active rows are independent, with ordinary row-level Stash origin (never a compact Return or group Return). |

The optional creator fields label the **group**, not its member authors. `bundleId` is storage provenance, not `groupId`. A note with embedded footage contributes one member. The editor's existing `presentAttachedFootageForSortingV2` and `parkAttachedFootageForSortingV2` protect the clip's exclusive owner and visual mirror; unresolved/unsupported source-audio policies refuse rather than mutate media or invent timing. Group operations never invoke Resolve.

## Refusal and recovery behavior

- Group creation refuses missing, duplicate, non-adjacent, cross-section/cross-parent rows; selection of a compact parent with dependent outline children; overlapping membership; and group-from-Draft footage that would reattach to an existing saved note rather than stay a selected member.
- Moves require an exact destination sibling or compact-note parent. Inserting inside another group or splitting an existing group is rejected by full-document postvalidation. Legacy placement/restore/delete/outline/section commands cannot leave a partial or split group. Independent `edit_row` and `applyStashRowEditV2` cannot bypass the future group's one-Save staged edit boundary.
- Deleting an attached owner still requires explicit detach/cleanup; a mixed supporting-item anchor, stale audio span or ambiguous relationship refuses the complete transaction. No member is silently discarded and no media is deleted.
- Every successful action stays serializable and undoable. Sessions undo the canonical snapshot without inventing group history, aside from the monotonically advancing local revision.

## Phase 3 — local staged member editor and one Save

The public pure helpers are `beginStashGroupMemberStageV2(document, groupId)`,
`stageStashGroupMembersV2(stage, completeMembers)`, `cancelStashGroupMemberStageV2(stage)`
and `saveStashGroupStageCommandV2(stage)`. They copy complete saved row payloads;
no staging or Cancel operation touches the canonical document, consumes a
revision, or creates an Undo. Save produces a replayable JSON command:

`{ kind: "save_stash_group", groupId, expectedRevision, expectedRowIds, members }`

Apply with `applyRowEditV2(document, stage.expectedRevision, command)` or
`createRowEditSessionV2.apply(command)`; the command itself also pins the
original revision, so it cannot silently save against a newer session. The
expected member IDs must equal the current complete group in order. `members`
is the **complete new order** of full rows, not a patch. Existing IDs and row
types are immutable, their saved origin is retained and made ineligible for
compact Return upon an authored change, and the group creator never becomes
the author of its members. New rows need distinct identities and no forged
origin. Existing ungrouped Stash rows may be incorporated only from an adjacent
same-parent/same-section sibling range, without copying their bundles or
supporting items. The result is one row-edit revision and one local Undo.

A Save with one surviving row removes group metadata and leaves that row as an
ordinary Stash item; zero removes the metadata and rows via protected deletion.
Reordering also changes only canonical outline order, never payload identities.
Removal refuses when it would silently drop owned footage, a citation, comment
reference, audio intent, a surviving return-location anchor or an ambiguous
supporting item. Existing word/event anchors are checked before whole-member
replacement; footage owner, speech intent and frozen clip source changes require
the existing explicit review commands. Invalid member payloads, duplicate IDs,
overlapping groups, nonadjacent saved additions and stale Save requests refuse
atomically with the exact input document preserved. Save does not update media
or Resolve. Phase 4 will add Sorting's acceptance/replay policy for the new Save.

## Later phases

Phase 4 owns Sorting's four finish outcomes and projection classification; group commands are intentionally not yet in the Sorting whitelist. Phase 5 owns the full mutation audit, complete fast gate and final review. No production UI, remote collaboration or real-Resolve acceptance is claimed by these domain tests.
