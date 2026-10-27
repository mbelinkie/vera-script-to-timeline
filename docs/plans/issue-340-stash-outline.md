# Issue 340: Stash outline handoff

## Persisted shape

`ScriptDocumentV2.stashOutline` is optional for backward compatibility. When present, it is the complete visible-order and nesting source for Stash:

```ts
{ rowId, kind: "note" | "clip" | "row", parentRowId, sectionId }
```

`rowId` references the existing saved row identity. Note and clip content remains in the existing saved-row payloads; `kind` controls compact presentation and consumer exclusion, while `row` means ordinary full-row presentation. A note may contain clips or notes; a clip cannot be a parent. Children stay in the parent's section. Each subtree appears contiguously in deterministic preorder. In canonical mode, `stashSections` remains present as needed for section titles, but each `rowIds` value is `[]`.

Older documents without `stashOutline` remain valid. The first outline write upgrades their visible order deterministically: unsectioned rows first, followed by each existing section's rows in section order. The upgrade then clears the legacy `rowIds` arrays.

## Row origin and return

Rows placed from Stash receive optional `stashOrigin` metadata: original compact kind, parent, section, sibling index, and `returnEligible`. The row itself remains the sole content copy. Successful authored mutations set `returnEligible: false`; moves, comments, and replies do not. Exact stage-direction Undo restores the row snapshot, including its earlier eligibility. Whole-row Stash edits preserve origin location/kind from the current row and cannot forge eligibility.

`stash_rows` uses an eligible origin to restore a note or clip compactly. An edited item returns as `kind: "row"`. Successful return consumes the origin metadata because the current outline now records its placement. Returning a child while its original parent is active places it at top level in the original section. If the parent remains in Stash, the child returns at its original nested sibling slot. Unselected relatives are not moved or reparented.

## Authored operations

- `create_stash_note` creates an existing NarrationBlock payload as a compact note. Omitted `mode` defaults to `default_direction`; explicitly authored `mode: "authored"` preserves mixed speech/direction content. The default conversion uses the #341 direction wrapper and exact token offsets.
- `create_stash_clip` stores an existing VisualOnlyBlock payload as a compact clip.
- `set_stash_outline` changes order, parent and section only. It cannot create, remove or reclassify rows; creation uses the create commands with new row identities.
- `place_stash_rows` moves selected roots and their complete descendant branches into a precise active-row gap.
- Existing `stash_rows` and ordinary restore commands continue to handle independent full rows. Legacy restore commands refuse compact or nested entries; use `place_stash_rows` for those entries so their Stash origin is recorded.

The Sorting trial may organize the existing outline and place existing branches. It still rejects note/clip creation and authored content edits; those remain ordinary authoring operations for the later Sorting scope.

## Refusal boundaries

Validation requires unique outline row references, exact coverage of all saved rows, valid section references, empty canonical section row lists, note-only parents, same-section parent/child relationships, no cycles, and valid preorder. Operations refuse missing destinations, ambiguous original sibling slots, partial cross-section branches, and unsupported audio/attachment cases atomically. A note that cannot be converted by the bounded #341 default-direction helper must be created with explicit authored mode or left as an ordinary row. The implementation adds no UI, persistent bundle, duplicate payload model, or new authoring service.
