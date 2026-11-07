# #368 — Forgiving Stash return and mixed edited-parent recovery

This is the reusable **v2 document/domain** implementation of the Producer's
Stash return decision. It supersedes #340/#342's ambiguous-location and
edited-parent refusal only. It does not supply a production Stash picker, UI,
workspace service, Research transport, collaboration, or media operation.

## Public commands and persisted history

Use `applyRowEditV2(document, document.rowEditRevision ?? 0, command)` or
`createRowEditSessionV2(document).apply(command)` from
`@vera/contracts/authoring-v2`. A normal menu return omits `destination`:

```ts
{ kind: "stash_rows", rowIds: [rowAId, rowBId], bundleId: newBundleId }
```

`rowIds` must be the **ordered, contiguous, same-Draft-section** run. An
explicit outline drop can instead supply exactly these four fields:

```ts
{
  kind: "stash_rows", rowIds: [rowAId, rowBId], bundleId: newBundleId,
  destination: {
    sectionId: existingStashSectionIdOrNull,
    parentRowId: existingCompactNoteIdOrNull,
    afterRowId: currentPreviousSiblingIdOrNull,
    beforeRowId: currentNextSiblingIdOrNull,
  },
}
```

The destination names a **currently adjacent sibling gap** in a surviving
Stash section/valid note, including exact start/end or empty-sibling gaps.
It overrides frozen origin location, but not note-only parenthood or other
safety checks. An unknown property, nonadjacent/missing anchor, wrong section,
non-note parent, bad row run, reused bundle ID, or stale revision refuses the
whole command. This drop shape is *not* `RowGapV2` (which has no parent).

`place_stash_rows` freezes `stashOrigin` on each Draft row. Its original six
fields (`kind`, `parentRowId`, `sectionId`, `afterSiblingRowId`,
`beforeSiblingRowId`, `returnEligible`) are unchanged. New **optional** fields
capture `precedingSiblingRowIds` / `followingSiblingRowIds` in nearest-first
order, plus `originalParentContext` (parent's own former parent/section and
nearest-first sibling lists). These values record historical relationships,
not the current position. A legacy six-field origin and a legacy document
with only `stashSections[].rowIds` remain accepted and serialize without an
invented history; the first Stash outline write upgrades old section arrays.

## Menu return precedence

1. If the original section and valid original note parent survive unmoved,
   insert after the **nearest surviving original preceding sibling** (after
   its complete subtree). Otherwise insert before the nearest surviving
   original following sibling; ignore newly interposed/reordered unrelated
   rows. Historical arrays, not UUID/text sorting, provide that evidence.
2. With neither surviving sibling, insert as first child of that still-valid
   note, or at the beginning of the original section for a root.
3. If the section is gone, parent is gone/reparented/resectioned or provably
   moved relative to original siblings, or origin cannot defend a location,
   insert at index zero of **unsectioned Stash**. Never rebuild a missing
   section/parent or change unselected relatives to make a location fit.

The caller inserts selected rows as one transaction. A same-slot cursor
preserves batch order, including multiple rows falling back to unsectioned
top. Descendant rows wait for their selected ancestor. Returning a child while
its original parent remains **active in Draft** promotes the child to Stash's
root level, using the parent's historical root location/previously returned
siblings when defensible. If the original note survives compactly in Stash,
the child can return under it. An edited parent with `returnEligible: false`
returns as a complete `kind: "row"` saved payload; its unedited child notes
and clips promote to an appropriate sibling level, retaining deeper valid
note/clip descendants. A full saved row never owns outline children.

An independently placed former attached clip may reattach **only** to its
proven original empty note slot. If that slot is occupied it remains a single
ordinary saved clip; no duplicate footage owner is created and nothing is
overwritten. Edited embedded-footage owners that cannot safely become full
rows, unsupported audio spans, cross-row supporting references, stale visual
mirrors, invalid Research frame evidence and duplicate identities still refuse
atomically. A refusal returns the exact input document object. Successful
commands consume return origin, advance the row revision once, and one session
Undo restores the prior script, Stash, outline, attachments and history (with
monotonic session revision).

## Sorting and downstream consumers

`createSortingTrialV2` accepts the same exact optional destination, restores
full pending history through serialize/resume, and projects the **same**
location/parent-kind policy for `all`, `edits_only`, `sorting_only` and
`discard`. It does not filter-replay partial edit commands. Selective
acceptance still refuses unsupported relationships, newly born-section
dependencies and changed outside-canonical baselines; pending state survives
refusals. Comments stay in their independent reconciliation boundary.

`compileTimelineV2`, `resolveMediaRequirementsV2` and `exportPrompter` consume
the **active Draft** only: parked rows, Stash sections, outline position,
origin history and saved media cannot add beats, manifest events or build
requirements. The actual v2 compiler and prompter tests compare identical
outputs before/after parked content, while active unresolved Research
occurrences still refuse with `RESEARCH_MEDIA_UNRESOLVED`, even with preview
overrides. There is no change to compiler goldens or consumers. No native
application, real media, Research API, or Resolve acceptance is claimed.

## Verification ownership

Phase 4 covers old JSON roundtrip, legacy-section batch return, synthetic
compiler/prompter exclusion and the superseded ambiguous attached-footage
expectation. Phase 5 owns full `npm run validate:fast`, independent mutation
checks for outline/ownership/explicit-drop/revision guards, whole-diff review
and the PR; full `npm run validate` belongs to GitHub Actions.
