import { describe, expect, it } from "vitest";
import type { ScriptDocumentV2, NarrationBlockV2, SupportingItemV2, VisualOnlyBlockV2 } from "../src/generated/contracts-v2.js";
import { applyRowEditV2, type RowEditCommandV2 } from "../src/authoring-v2-rows.js";
import {
  createSortingProjectionV2,
  projectSortingDocumentV2,
  updateSortingProjectionV2,
} from "../src/authoring-v2-sorting-projection.js";

const id = (n: number) => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;

function row(n: number): NarrationBlockV2 {
  const text = `Words${n}`;
  return {
    id: id(n), type: "narration", orderKey: `${n}`, text,
    tokens: [{ id: id(n + 1000), value: text, startOffset: 0, endOffset: text.length }],
    primaryVisualSequence: { id: id(n + 2000), version: 1, slots: [{
      id: id(n + 3000), kind: "content", relation: { kind: "base" }, boundaryBefore: { kind: "row_start" },
      payload: { kind: "on_camera", presenterChoiceId: null }, playoutPolicy: "match_structural_interval", version: 1,
    }] }, overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
}

function clip(n: number): VisualOnlyBlockV2 {
  return {
    id: id(n), type: "visual_only", orderKey: `${n}`, version: 1,
    payload: { kind: "visual", payloadId: id(n + 1000), pictureKind: "clip", source: { kind: "media_reference", mediaReferenceId: id(n + 2000) }, audioPolicy: "mute", framingPolicy: "contain" },
    visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 0, durationFrames: 48 } },
  };
}

function document(): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "Sorting projection",
    activeDraft: { blocks: [], supportingItems: [] }, ideaOutline: [], extras: [], liveHeadSequence: 0,
    liveStateVector: "", liveContentHash: `sha256:${"a".repeat(64)}`,
  };
}

const gap = (afterRowId: string | null, beforeRowId: string | null, sectionId: string | null = null) => ({ sectionId, afterRowId, beforeRowId });

function apply(document: ScriptDocumentV2, command: RowEditCommandV2): ScriptDocumentV2 {
  const result = applyRowEditV2(document, document.rowEditRevision ?? 0, command);
  expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
  return result.document;
}

describe("Sorting selective projections", () => {
  it("refuses edits-only when an edited converted note would strand its baseline child", () => {
    const parent = row(10);
    const child = clip(20);
    let baseline = apply(document(), {
      kind: "create_stash_note", bundleId: id(30), row: parent, sectionId: null, parentRowId: null, afterRowId: null, mode: "authored",
    });
    baseline = apply(baseline, {
      kind: "create_stash_clip", bundleId: id(31), row: child, sectionId: null, parentRowId: parent.id, afterRowId: null,
    });
    const state = createSortingProjectionV2(baseline);
    const placement: RowEditCommandV2 = { kind: "place_stash_rows", rowIds: [parent.id], destination: gap(null, null) };
    const placed = apply(baseline, placement);
    const afterPlace = updateSortingProjectionV2(state, baseline, placed, placement);
    const placedParent = placed.activeDraft.blocks.find((block) => block.id === parent.id);
    if (placedParent?.type !== "narration") throw new Error("Missing converted note");
    const edited = apply(placed, {
      kind: "edit_row", rowId: parent.id,
      row: { ...placedParent, text: "Edited parent", tokens: [{ ...placedParent.tokens[0], value: "Edited parent", startOffset: 0, endOffset: 13 }], version: 2 },
    });
    const stateWithEdit = updateSortingProjectionV2(afterPlace, placed, edited, {
      kind: "edit_row", rowId: parent.id,
      row: { ...placedParent, text: "Edited parent", tokens: [{ ...placedParent.tokens[0], value: "Edited parent", startOffset: 0, endOffset: 13 }], version: 2 },
    });

    const projected = projectSortingDocumentV2(stateWithEdit, edited, "edits_only");
    expect(projected.ok).toBe(false);
    expect(projected.diagnostics[0]?.code).toBe("SORTING_PROJECTION_DEPENDENCY_INVALID");
    expect(projected.document).toBe(edited);
  });

  it("refuses an edits-only birth whose original Stash section was created during Sorting", () => {
    const baseline = document();
    const sectionId = id(40);
    let state = createSortingProjectionV2(baseline);
    const createSection: RowEditCommandV2 = { kind: "create_stash_section", sectionId, title: "Temporary" };
    const sectioned = apply(baseline, createSection);
    state = updateSortingProjectionV2(state, baseline, sectioned, createSection);
    const createNote: RowEditCommandV2 = {
      kind: "create_stash_note", bundleId: id(41), row: row(42), sectionId, parentRowId: null, afterRowId: null, mode: "authored",
    };
    const withNote = apply(sectioned, createNote);
    state = updateSortingProjectionV2(state, sectioned, withNote, createNote);

    const projected = projectSortingDocumentV2(state, withNote, "edits_only");
    expect(projected.ok).toBe(false);
    expect(projected.diagnostics[0]?.code).toBe("SORTING_PROJECTION_DESTINATION_INVALID");
    expect(projected.document).toBe(withNote);
  });

  it("refuses to route one supporting item across the projected Draft and Stash boundary", () => {
    const first = row(50);
    const second = row(51);
    const item: SupportingItemV2 = {
      id: id(52), version: 1, orderKey: "source", role: "citation", content: "A source across both rows",
      placement: { kind: "point", anchor: { kind: "between_blocks", afterBlockId: first.id, beforeBlockId: second.id } },
    };
    const baseline = { ...document(), activeDraft: { blocks: [first, second], supportingItems: [item] } };
    const current: ScriptDocumentV2 = {
      ...baseline,
      activeDraft: { blocks: [first], supportingItems: [] },
      stash: [{ id: id(53), rows: [second], supportingItems: [item] }],
    };
    const command: RowEditCommandV2 = { kind: "stash_rows", rowIds: [second.id], bundleId: id(53) };
    const state = updateSortingProjectionV2(createSortingProjectionV2(baseline), baseline, current, command);

    const projected = projectSortingDocumentV2(state, current, "sorting_only");
    expect(projected.ok).toBe(false);
    expect(projected.diagnostics[0]?.code).toBe("SORTING_PROJECTION_ATTACHMENT_INVALID");
    expect(projected.document).toBe(current);
  });

  it("restores a simultaneously deleted run in exact order and preserves surviving row references", () => {
    const first = row(60);
    const left = row(61);
    const right = row(62);
    const last = row(63);
    const baseline: ScriptDocumentV2 = {
      ...document(),
      activeDraft: { blocks: [first, left, right, last], supportingItems: [] },
      rowReferences: [
        { id: id(64), rowId: left.id, kind: "comment", anchor: { tokenId: left.tokens[0].id } },
        { id: id(65), rowId: right.id, kind: "reference", anchor: { source: "kept" } },
      ],
    };
    const state = createSortingProjectionV2(baseline);
    const command: RowEditCommandV2 = { kind: "delete_rows", rowIds: [left.id, right.id] };
    const deleted = apply(baseline, command);
    const updated = updateSortingProjectionV2(state, baseline, deleted, command);

    const sorting = projectSortingDocumentV2(updated, deleted, "sorting_only");
    expect(sorting.ok, JSON.stringify(sorting.diagnostics)).toBe(true);
    expect(sorting.document.activeDraft.blocks.map((block) => block.id)).toEqual([first.id, left.id, right.id, last.id]);
    expect(sorting.document.rowReferences).toEqual(baseline.rowReferences);

    const edits = projectSortingDocumentV2(updated, deleted, "edits_only");
    expect(edits.ok, JSON.stringify(edits.diagnostics)).toBe(true);
    expect(edits.document.activeDraft.blocks.map((block) => block.id)).toEqual([first.id, last.id]);
    expect(edits.document.rowReferences).toBeUndefined();
  });

  it("keeps a surviving birth when edits-only removes its deleted birth anchor", () => {
    const first = row(80);
    const second = row(81);
    const anchor = row(82);
    const born = row(83);
    const baseline = { ...document(), activeDraft: { blocks: [first, second, anchor], supportingItems: [] } };
    let state = createSortingProjectionV2(baseline);
    let current: ScriptDocumentV2 = baseline;
    const create: RowEditCommandV2 = { kind: "create_row", row: born, destination: gap(anchor.id, null) };
    const withBirth = apply(current, create);
    state = updateSortingProjectionV2(state, current, withBirth, create);
    current = withBirth;
    const remove: RowEditCommandV2 = { kind: "delete_rows", rowIds: [anchor.id] };
    const deletedAnchor = apply(current, remove);
    state = updateSortingProjectionV2(state, current, deletedAnchor, remove);

    const projected = projectSortingDocumentV2(state, deletedAnchor, "edits_only");
    expect(projected.ok, JSON.stringify(projected.diagnostics)).toBe(true);
    expect(projected.document.activeDraft.blocks.map((block) => block.id)).toEqual([first.id, second.id, born.id]);
  });

  it("places a birth in the gap left by a baseline row deleted earlier in the trial", () => {
    const first = row(93);
    const deleted = row(94);
    const last = row(95);
    const born = row(96);
    const baseline = { ...document(), activeDraft: { blocks: [first, deleted, last], supportingItems: [] } };
    let state = createSortingProjectionV2(baseline);
    const remove: RowEditCommandV2 = { kind: "delete_rows", rowIds: [deleted.id] };
    const afterDelete = apply(baseline, remove);
    state = updateSortingProjectionV2(state, baseline, afterDelete, remove);
    const create: RowEditCommandV2 = { kind: "create_row", row: born, destination: gap(first.id, last.id) };
    const current = apply(afterDelete, create);
    state = updateSortingProjectionV2(state, afterDelete, current, create);

    const projected = projectSortingDocumentV2(state, current, "edits_only");
    expect(projected.ok, JSON.stringify(projected.diagnostics)).toBe(true);
    expect(projected.document.activeDraft.blocks.map((block) => block.id)).toEqual([first.id, born.id, last.id]);
  });

  it("restores a deleted baseline row while its neighboring birth is still present", () => {
    const first = row(84);
    const deleted = row(85);
    const last = row(86);
    const born = row(87);
    const baseline = { ...document(), activeDraft: { blocks: [first, deleted, last], supportingItems: [] } };
    let state = createSortingProjectionV2(baseline);
    const create: RowEditCommandV2 = { kind: "create_row", row: born, destination: gap(first.id, deleted.id) };
    const withBirth = apply(baseline, create);
    state = updateSortingProjectionV2(state, baseline, withBirth, create);
    const remove: RowEditCommandV2 = { kind: "delete_rows", rowIds: [deleted.id] };
    const current = apply(withBirth, remove);
    state = updateSortingProjectionV2(state, withBirth, current, remove);

    const projected = projectSortingDocumentV2(state, current, "sorting_only");
    expect(projected.ok, JSON.stringify(projected.diagnostics)).toBe(true);
    expect(projected.document.activeDraft.blocks.map((block) => block.id)).toEqual([first.id, deleted.id, last.id]);
  });

  it("keeps a later birth after omitting an earlier deleted birth", () => {
    const first = row(88);
    const second = row(89);
    const last = row(90);
    const firstBirth = row(91);
    const secondBirth = row(92);
    const baseline = { ...document(), activeDraft: { blocks: [first, second, last], supportingItems: [] } };
    let state = createSortingProjectionV2(baseline);
    let current: ScriptDocumentV2 = baseline;
    const createFirst: RowEditCommandV2 = { kind: "create_row", row: firstBirth, destination: gap(last.id, null) };
    const withFirst = apply(current, createFirst);
    state = updateSortingProjectionV2(state, current, withFirst, createFirst);
    current = withFirst;
    const remove: RowEditCommandV2 = { kind: "delete_rows", rowIds: [firstBirth.id] };
    const afterDelete = apply(current, remove);
    state = updateSortingProjectionV2(state, current, afterDelete, remove);
    const createSecond: RowEditCommandV2 = { kind: "create_row", row: secondBirth, destination: gap(last.id, null) };
    const currentAfterBirth = apply(afterDelete, createSecond);
    state = updateSortingProjectionV2(state, afterDelete, currentAfterBirth, createSecond);

    const projected = projectSortingDocumentV2(state, currentAfterBirth, "edits_only");
    expect(projected.ok, JSON.stringify(projected.diagnostics)).toBe(true);
    expect(projected.document.activeDraft.blocks.map((block) => block.id)).toEqual([first.id, second.id, last.id, secondBirth.id]);
  });

  it("does not restore a deleted birth when sorting-only has no dependency on it", () => {
    const first = row(97);
    const second = row(98);
    const last = row(99);
    const deletedBirth = row(100);
    const survivingBirth = row(101);
    const baseline = { ...document(), activeDraft: { blocks: [first, second, last], supportingItems: [] } };
    let state = createSortingProjectionV2(baseline);
    const createDeleted: RowEditCommandV2 = { kind: "create_row", row: deletedBirth, destination: gap(last.id, null) };
    const withDeleted = apply(baseline, createDeleted);
    state = updateSortingProjectionV2(state, baseline, withDeleted, createDeleted);
    const remove: RowEditCommandV2 = { kind: "delete_rows", rowIds: [deletedBirth.id] };
    const afterDelete = apply(withDeleted, remove);
    state = updateSortingProjectionV2(state, withDeleted, afterDelete, remove);
    const createSurviving: RowEditCommandV2 = { kind: "create_row", row: survivingBirth, destination: gap(last.id, null) };
    const current = apply(afterDelete, createSurviving);
    state = updateSortingProjectionV2(state, afterDelete, current, createSurviving);

    const projected = projectSortingDocumentV2(state, current, "sorting_only");
    expect(projected.ok, JSON.stringify(projected.diagnostics)).toBe(true);
    expect(projected.document.activeDraft.blocks.map((block) => block.id)).toEqual([first.id, second.id, last.id]);
  });

  it("restores a deleted baseline row and its deleted birth anchor in one ordering batch", () => {
    const first = row(102);
    const second = row(103);
    const deleted = row(104);
    const born = row(105);
    const baseline = { ...document(), activeDraft: { blocks: [first, second, deleted], supportingItems: [] } };
    let state = createSortingProjectionV2(baseline);
    const create: RowEditCommandV2 = { kind: "create_row", row: born, destination: gap(deleted.id, null) };
    const withBirth = apply(baseline, create);
    state = updateSortingProjectionV2(state, baseline, withBirth, create);
    const removeBoth: RowEditCommandV2 = { kind: "delete_rows", rowIds: [deleted.id, born.id] };
    const current = apply(withBirth, removeBoth);
    state = updateSortingProjectionV2(state, withBirth, current, removeBoth);

    const projected = projectSortingDocumentV2(state, current, "sorting_only");
    expect(projected.ok, JSON.stringify(projected.diagnostics)).toBe(true);
    expect(projected.document.activeDraft.blocks.map((block) => block.id)).toEqual([first.id, second.id, deleted.id]);
  });

  it("restores a baseline row whose deleted birth anchor is separated by another surviving birth", () => {
    const first = row(109);
    const second = row(110);
    const deleted = row(111);
    const anchorBirth = row(112);
    const unrelatedBirth = row(113);
    const baseline = { ...document(), activeDraft: { blocks: [first, second, deleted], supportingItems: [] } };
    let state = createSortingProjectionV2(baseline);
    const createAnchor: RowEditCommandV2 = { kind: "create_row", row: anchorBirth, destination: gap(deleted.id, null) };
    const withAnchor = apply(baseline, createAnchor);
    state = updateSortingProjectionV2(state, baseline, withAnchor, createAnchor);
    const createUnrelated: RowEditCommandV2 = { kind: "create_row", row: unrelatedBirth, destination: gap(first.id, second.id) };
    const withBoth = apply(withAnchor, createUnrelated);
    state = updateSortingProjectionV2(state, withAnchor, withBoth, createUnrelated);
    const remove: RowEditCommandV2 = { kind: "delete_rows", rowIds: [deleted.id, anchorBirth.id] };
    const current = apply(withBoth, remove);
    state = updateSortingProjectionV2(state, withBoth, current, remove);

    const projected = projectSortingDocumentV2(state, current, "sorting_only");
    expect(projected.ok, JSON.stringify(projected.diagnostics)).toBe(true);
    expect(projected.document.activeDraft.blocks.map((block) => block.id)).toEqual([first.id, second.id, deleted.id]);
  });

  it("projects a birth made after all baseline rows are deleted", () => {
    const first = row(106);
    const second = row(107);
    const born = row(108);
    const baseline = { ...document(), activeDraft: { blocks: [first, second], supportingItems: [] } };
    let state = createSortingProjectionV2(baseline);
    const remove: RowEditCommandV2 = { kind: "delete_rows", rowIds: [first.id, second.id] };
    const afterDelete = apply(baseline, remove);
    state = updateSortingProjectionV2(state, baseline, afterDelete, remove);
    const create: RowEditCommandV2 = { kind: "create_row", row: born, destination: gap(null, null) };
    const current = apply(afterDelete, create);
    state = updateSortingProjectionV2(state, afterDelete, current, create);

    const edits = projectSortingDocumentV2(state, current, "edits_only");
    expect(edits.ok, JSON.stringify(edits.diagnostics)).toBe(true);
    expect(edits.document.activeDraft.blocks.map((block) => block.id)).toEqual([born.id]);

    const sorting = projectSortingDocumentV2(state, current, "sorting_only");
    expect(sorting.ok, JSON.stringify(sorting.diagnostics)).toBe(true);
    expect(sorting.document.activeDraft.blocks.map((block) => block.id)).toEqual([first.id, second.id]);
  });

  it("restores Stash rows deleted in separate operations to their original bundle order", () => {
    const first = row(69);
    const second = row(72);
    const bundleId = id(73);
    const baseline: ScriptDocumentV2 = {
      ...document(),
      stash: [{ id: bundleId, rows: [first, second], supportingItems: [] }],
      stashOutline: [
        { rowId: first.id, kind: "row", parentRowId: null, sectionId: null },
        { rowId: second.id, kind: "row", parentRowId: null, sectionId: null },
      ],
    };
    let state = createSortingProjectionV2(baseline);
    let current: ScriptDocumentV2 = baseline;
    for (const rowId of [first.id, second.id]) {
      const command: RowEditCommandV2 = { kind: "delete_rows", rowIds: [rowId] };
      const after = apply(current, command);
      state = updateSortingProjectionV2(state, current, after, command);
      current = after;
    }

    const projected = projectSortingDocumentV2(state, current, "sorting_only");
    expect(projected.ok, JSON.stringify(projected.diagnostics)).toBe(true);
    expect(projected.document.stash?.[0]?.id).toBe(bundleId);
    expect(projected.document.stash?.[0]?.rows.map((saved) => saved.id)).toEqual([first.id, second.id]);
    expect(projected.document.stashOutline?.map((entry) => entry.rowId)).toEqual([first.id, second.id]);
  });

  it("restores a deleted row to its last stable slot when its final move targeted a discarded birth", () => {
    const first = row(66);
    const second = row(67);
    const born = row(68);
    const baseline = { ...document(), activeDraft: { blocks: [first, second], supportingItems: [] } };
    let state = createSortingProjectionV2(baseline);
    let current: ScriptDocumentV2 = baseline;
    const create: RowEditCommandV2 = { kind: "create_row", row: born, destination: gap(second.id, null) };
    const withBirth = apply(current, create);
    state = updateSortingProjectionV2(state, current, withBirth, create);
    current = withBirth;
    const move: RowEditCommandV2 = { kind: "move_rows", rowIds: [first.id], destination: gap(born.id, null) };
    const moved = apply(current, move);
    state = updateSortingProjectionV2(state, current, moved, move);
    current = moved;
    const remove: RowEditCommandV2 = { kind: "delete_rows", rowIds: [first.id] };
    const deleted = apply(current, remove);
    state = updateSortingProjectionV2(state, current, deleted, remove);

    const projected = projectSortingDocumentV2(state, deleted, "sorting_only");
    expect(projected.ok, JSON.stringify(projected.diagnostics)).toBe(true);
    expect(projected.document.activeDraft.blocks.map((block) => block.id)).toEqual([first.id, second.id]);
  });

  it.each(["born", "baseline"] as const)("refuses selective projection after a %s row ID is reused", (origin) => {
    const original = row(origin === "born" ? 70 : 71);
    const baseline = { ...document(), activeDraft: { blocks: origin === "baseline" ? [original] : [], supportingItems: [] } };
    let state = createSortingProjectionV2(baseline);
    let current: ScriptDocumentV2 = baseline;
    if (origin === "born") {
      const create: RowEditCommandV2 = { kind: "create_row", row: original, destination: gap(null, null) };
      const afterCreate = apply(current, create);
      state = updateSortingProjectionV2(state, current, afterCreate, create);
      current = afterCreate;
    }
    const remove: RowEditCommandV2 = { kind: "delete_rows", rowIds: [original.id] };
    const afterDelete = apply(current, remove);
    state = updateSortingProjectionV2(state, current, afterDelete, remove);
    current = afterDelete;
    const recreate: RowEditCommandV2 = { kind: "create_row", row: original, destination: gap(null, null) };
    const afterRecreate = apply(current, recreate);
    state = updateSortingProjectionV2(state, current, afterRecreate, recreate);

    const projected = projectSortingDocumentV2(state, afterRecreate, "sorting_only");
    expect(projected.ok).toBe(false);
    expect(projected.diagnostics[0]?.code).toBe("SORTING_PROJECTION_IDENTITY_AMBIGUOUS");
    expect(projected.document).toBe(afterRecreate);
  });
});
