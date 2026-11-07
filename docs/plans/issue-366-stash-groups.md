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
or Resolve.

## Phase 4 — Sorting projections and consumers

All seven group commands pass Sorting's shared exact JSON command gate and
replay as **one operation** with local Undo, preview/return and saved-trial
resume. Group member selections and move marks use canonical row IDs, not a
synthetic group row or duplicated attachment. The four finishes are:

- **All:** commit complete trial content, outline and group records once.
- **Edits-only:** use baseline group organization while retaining authored row
  replacements/deletions and new members. A new member authored in a group Save
  is placed directly after the baseline group in edits-only, without adopting
  a staged reordering of surviving baseline members. Incorporating an existing
  independent Stash row into a group is organization, not a copied birth.
- **Sorting-only:** keep current group organization/placements and baseline
  row content. Reconstruct original members deleted by a group Save or deletion
  when their exact sorted Stash slots can be proven. A converted compact
  note/clip in a retained group remains an ordinary complete group row.
- **Discard:** return the unmodified baseline and comment state.

Zero/one-member selective results normalize without a persisted group. A
split/nonadjacent projected group, unrecoverable sibling gap, mixed parent or
section, duplicate membership/identity, incompatible attachment or unresolved
supporting reference **refuses** the entire selective outcome; the pending
trial, comment state and Undo remain available. Reuse of a removed group ID
is ambiguous for selective acceptance and also refuses. There is no partial
action replay on a projected document. The existing comment-reconciliation
API applies once at acceptance, never during pending edits.

`row-edit-consumers-v2.test.ts` proves grouped saved rows and citations remain
excluded from prompter, compiler and media requirements, while an explicitly
flattened group has the same consumer outputs as placing its independent rows.
The Python narration/compiler boundary reads active Draft material, not
`stashGroups`; its existing saved-Stash consumer integration test remains
applicable and no Python code/schema change is needed for this metadata.

## Phase 5 — verification, guard mutation and #125 handoff

- **Generated types/current contracts:** `npm run check:contracts-generated` passed after all changes; schema remains `script-document/v2` with optional `stashGroups`. No legacy schema, golden media or external storage changes.
- **Restored-source focused gate:** `npm run typecheck -w @vera/contracts`, `npm run lint -w @vera/contracts`, and 11 targeted Vitest suites (279 tests) passed; `uv run --frozen pytest tests/test_row_stash_v2_consumers.py` passed (1 test). These cover form/move/ungroup/delete/place, complete stage Save/Cancel/Undo, source/attached clip, audio, supporting citations, comments, Sorting four outcomes, preview/return, resume and consumers.
- **Repository `npm run validate:fast`:** generated contract check, all TypeScript lint/typecheck/fast suites, Python Ruff and mypy passed. Python parallel fast suite finished **2,768 passed, 43 skipped, 21 failed** in unchanged narration, word-timing, #182, #208 target-identity/clock and M4 test files. These same unrelated families failed in prior #366 phase 1/3 fast runs; this is **not** a green repository-wide local gate. Exact output: `.pipeline/366/phase5-validate-fast.log`. Do not represent this branch as CI-green on that basis.
- **Red/green loader regression:** a malformed group with reversed stored `rowIds` was previously accepted by `deserializeAuthoringDocumentV2`; the new `stash-groups-v2.test.ts` assertion failed before the fix and passed after adding `STASH_GROUP_INVALID` to the loader's fatal diagnostic set. Invalid groups now refuse serialization as well. Evidence: `.pipeline/366/phase5-serializer-red.log` plus passing focused suite.
- **Reversible mutation audit:** for each mutation below, the focused negative test failed when its guard was weakened; the script restored the source bytes exactly and the 279-case restored suite passed afterward. Command: `python3 ../../.pipeline/366/phase5-mutations.py`; raw results `.pipeline/366/phase5-mutations.json`.
  1. Disable group row adjacency check → `refuses absent members, wrong order, non-adjacency and mixed sibling ownership` failed.
  2. Disable duplicate group-membership validation → `rejects duplicate membership, duplicate group identity and stale compact-return eligibility` failed.
  3. Bypass owned-clip deletion refusal → `deletes an ordinary group and its rows atomically, but refuses implicit deletion of owned footage` failed.
  4. Bypass group-audio move precondition → `guards audio intent and refuses dependent outline children instead of flattening a compact note` failed.
  5. Bypass mixed saved supporting-reference boundary → `keeps row-local citations with a flattened group and refuses cross-boundary supporting anchors atomically` failed.
- **Review:** read the entire source/test/schema diff against `origin/main` and found/fixed the loader fatal-diagnostic gap. Created 10-line `notes.md`; invoked `npm run review -- notes.md` **once**, but Claude replied `You've hit your weekly limit · resets Nov 9, 3pm (UTC)`. No external Claude code review was obtained; the complete self-review and recorded test-of-tests are the available local checks.

For #125, the **domain-only public capability** is `StashRowGroupV2`, seven typed group row commands (`stash_group_rows`, `group_stash_rows`, `move_stash_group`, `ungroup_stash_group`, `delete_stash_group`, `place_stash_group`, `save_stash_group`), pure staging helpers, Sorting four-way projection and saved-row consumer exclusion. A group consists of ordinary contiguous saved sibling rows, not a new bundle/row/mandatory Return unit. Group creator metadata is caller-supplied only. Cross-section selection, nested groups, production group UI, live collaboration, Research/Resolve writes, automatic editing in Resolve, unauthorized clip repairs, unsupported full audio policy and ambiguous/mixed supporting references remain out of scope or refuse atomically. Only **current-head full GitHub Actions `TypeScript and Python` green CI** may authorize merging; these pure tests are not real-app or Producer UI acceptance.
