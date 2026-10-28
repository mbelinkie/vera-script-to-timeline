import { describe, expect, it } from "vitest";

import {
  applyRowEditV2,
  createSortingTrialV2,
  deserializeAuthoringDocumentV2,
  resumeSortingTrialV2,
  serializeAuthoringDocumentV2,
  validateScriptDocumentV2,
  type RowEditCommandV2,
} from "../src/authoring-v2.js";
import type { NarrationBlockV2, ScriptDocumentV2, SupportingItemV2 } from "../src/generated/contracts-v2.js";

const id = (value: number): string => `00000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;

function row(value: number): NarrationBlockV2 {
  const text = `Words${value}`;
  return {
    id: id(value),
    type: "narration",
    orderKey: `${value}`,
    text,
    tokens: [{ id: id(value + 1000), value: text, startOffset: 0, endOffset: text.length }],
    primaryVisualSequence: {
      id: id(value + 2000),
      version: 1,
      slots: [{
        id: id(value + 3000),
        kind: "content",
        relation: { kind: "base" },
        boundaryBefore: { kind: "row_start" },
        payload: { kind: "on_camera", presenterChoiceId: null },
        playoutPolicy: "match_structural_interval",
        version: 1,
      }],
    },
    overlayEvents: [],
    timingPolicy: "narration_spine",
    state: "active",
    notes: [],
    version: 1,
  };
}

function document(): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2",
    id: id(1),
    projectId: id(2),
    title: "Sorting recovery",
    activeDraft: { blocks: [row(100), row(200), row(300), row(400)], supportingItems: [] },
    ideaOutline: [],
    extras: [],
    liveHeadSequence: 0,
    liveStateVector: "",
    liveContentHash: `sha256:${"a".repeat(64)}`,
  };
}

const gap = (afterRowId: string | null, beforeRowId: string | null) => ({ sectionId: null, afterRowId, beforeRowId });

function apply(trial: ReturnType<typeof createSortingTrialV2>, command: RowEditCommandV2): void {
  const result = trial.apply(command);
  expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
}

function applyDocument(documentValue: ScriptDocumentV2, command: RowEditCommandV2): ScriptDocumentV2 {
  const result = applyRowEditV2(documentValue, documentValue.rowEditRevision ?? 0, command);
  expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
  return result.document;
}

function activeIds(value: ScriptDocumentV2): string[] {
  return value.activeDraft.blocks.filter((block) => block.type !== "section").map((block) => block.id);
}

function rowReference(rowValue: NarrationBlockV2): SupportingItemV2 {
  const token = rowValue.tokens[0];
  const anchor = {
    blockId: rowValue.id,
    tokenId: token.id,
    affinity: "before" as const,
    quotedWord: token.value,
    anchorVersion: rowValue.version,
  };
  return {
    id: id(9000),
    version: 1,
    orderKey: "row-reference",
    role: "reference",
    content: "Reference attached to one row",
    placement: { kind: "point", anchor: { kind: "word", anchor } },
    displayAttachment: { kind: "word", anchor },
  };
}

describe("Sorting recovery", () => {
  it.each([false, true])("refuses a return origin whose new parent sorting-only removes (deleted: %s)", (deleted) => {
    const baseline = applyDocument(document(), { kind: "stash_rows", rowIds: [id(100)], bundleId: id(5200) });
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "create_stash_note", row: row(5300), bundleId: id(5201), sectionId: null, parentRowId: null, afterRowId: id(100), mode: "authored" });
    const entries = trial.document.stashOutline!;
    apply(trial, { kind: "set_stash_outline", entries: [entries.find((entry) => entry.rowId === id(5300))!, { ...entries.find((entry) => entry.rowId === id(100))!, parentRowId: id(5300) }] });
    apply(trial, { kind: "place_stash_rows", rowIds: [id(100)], destination: gap(id(400), null) });
    if (deleted) apply(trial, { kind: "delete_rows", rowIds: [id(100)] });
    const resumed = resumeSortingTrialV2(trial.serialize());
    const pending = resumed.document;
    expect(resumed.accept(baseline, "sorting_only")).toMatchObject({ ok: false, changed: false, document: baseline, diagnostics: [{ code: "SORTING_PROJECTION_DEPENDENCY_INVALID" }] });
    expect(resumed.document).toEqual(pending);
    expect(resumed.phase).toBe("sorting");
    expect(resumed.accept(baseline).ok).toBe(true);
  });

  it.each([false, true] as const)("keeps the chosen Stash return section through sorting-only after an edit (deleted=%s)", (deleteAfterEdit) => {
    const sectionA = id(5002);
    const sectionB = id(5003);
    const note = row(5000);
    let baseline = applyDocument(document(), { kind: "create_stash_section", sectionId: sectionA, title: "A" });
    baseline = applyDocument(baseline, { kind: "create_stash_section", sectionId: sectionB, title: "B" });
    baseline = applyDocument(baseline, {
      kind: "create_stash_note", bundleId: id(5001), row: note,
      sectionId: sectionA, parentRowId: null, afterRowId: null, mode: "authored",
    });
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "move_stash_rows", rowIds: [note.id], sectionId: sectionB });
    apply(trial, { kind: "place_stash_rows", rowIds: [note.id], destination: gap(id(400), null) });
    const placed = trial.document.activeDraft.blocks.find((block) => block.id === note.id);
    if (placed?.type !== "narration") throw new Error("Missing placed Stash note");
    const editedText = "Edited note";
    apply(trial, {
      kind: "edit_row", rowId: note.id,
      row: { ...placed, text: editedText, tokens: [{ ...placed.tokens[0], value: editedText, startOffset: 0, endOffset: editedText.length }], version: placed.version + 1 },
    });
    if (deleteAfterEdit) apply(trial, { kind: "delete_rows", rowIds: [note.id] });

    const accepted = resumeSortingTrialV2(trial.serialize()).accept(baseline, "sorting_only");
    expect(accepted.ok, JSON.stringify(accepted.diagnostics)).toBe(true);
    if (!accepted.ok) return;
    const restored = accepted.document.activeDraft.blocks.find((block) => block.id === note.id);
    if (restored?.type !== "narration") throw new Error("Sorting-only did not restore the saved note");
    expect(restored.text).toBe(note.text);
    expect(restored.stashOrigin).toMatchObject({ kind: "note", sectionId: sectionB, returnEligible: true });

    const returned = applyDocument(accepted.document, { kind: "stash_rows", rowIds: [note.id], bundleId: id(5004) });
    expect(returned.stashOutline?.find((entry) => entry.rowId === note.id)).toMatchObject({ kind: "note", sectionId: sectionB });
    expect(returned.stash?.flatMap((bundle) => bundle.rows).find((saved) => saved.id === note.id)).toEqual(note);
    expect(validateScriptDocumentV2(returned).valid).toBe(true);
  });

  it("restores original compact-note kind and return eligibility after sorting-only re-placement", () => {
    const note = row(5100);
    let baseline = applyDocument(document(), {
      kind: "create_stash_note", bundleId: id(5101), row: note,
      sectionId: null, parentRowId: null, afterRowId: null, mode: "authored",
    });
    baseline = applyDocument(baseline, { kind: "place_stash_rows", rowIds: [note.id], destination: gap(id(400), null) });
    const original = baseline.activeDraft.blocks.find((block) => block.id === note.id);
    if (original?.type !== "narration") throw new Error("Missing baseline placed note");
    expect(original.stashOrigin).toMatchObject({ kind: "note", returnEligible: true });

    const trial = createSortingTrialV2(baseline);
    const editedText = "Edited note";
    apply(trial, {
      kind: "edit_row", rowId: note.id,
      row: { ...original, text: editedText, tokens: [{ ...original.tokens[0], value: editedText, startOffset: 0, endOffset: editedText.length }], version: original.version + 1 },
    });
    apply(trial, { kind: "stash_rows", rowIds: [note.id], bundleId: id(5102) });
    apply(trial, { kind: "place_stash_rows", rowIds: [note.id], destination: gap(id(400), null) });

    const accepted = resumeSortingTrialV2(trial.serialize()).accept(baseline, "sorting_only");
    expect(accepted.ok, JSON.stringify(accepted.diagnostics)).toBe(true);
    if (!accepted.ok) return;
    const restored = accepted.document.activeDraft.blocks.find((block) => block.id === note.id);
    if (restored?.type !== "narration") throw new Error("Missing sorting-only note");
    expect(restored.text).toBe(original.text);
    expect(restored.stashOrigin).toMatchObject({ kind: "note", returnEligible: true });

    const returned = applyDocument(accepted.document, { kind: "stash_rows", rowIds: [note.id], bundleId: id(5103) });
    expect(returned.stashOutline?.find((entry) => entry.rowId === note.id)).toMatchObject({ kind: "note", sectionId: null });
    expect(validateScriptDocumentV2(returned).valid).toBe(true);
  });

  it("restores row-local attachments through Undo, trial reload, and sorting-only", () => {
    const baseline = document();
    const attachedRow = row(200);
    const attachment = rowReference(attachedRow);
    baseline.activeDraft.supportingItems = [attachment];
    expect(validateScriptDocumentV2(baseline).valid).toBe(true);

    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "delete_rows", rowIds: [attachedRow.id] });
    expect(trial.document.activeDraft.supportingItems).toEqual([]);

    const resumedForUndo = resumeSortingTrialV2(trial.serialize());
    expect(resumedForUndo.undo().ok).toBe(true);
    expect({ ...resumedForUndo.document, rowEditRevision: 0 }).toEqual({ ...baseline, rowEditRevision: 0 });
    expect(resumedForUndo.document.activeDraft.supportingItems).toEqual([attachment]);

    const resumedForAcceptance = resumeSortingTrialV2(trial.serialize());
    const accepted = resumedForAcceptance.accept(baseline, "sorting_only");
    expect(accepted.ok, JSON.stringify(accepted.diagnostics)).toBe(true);
    expect(activeIds(accepted.document)).toEqual(activeIds(baseline));
    expect(accepted.document.activeDraft.supportingItems).toEqual([attachment]);
    expect(validateScriptDocumentV2(accepted.document).valid).toBe(true);

    const loaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(accepted.document));
    expect(loaded.ok).toBe(true);
    if (loaded.ok) expect(loaded.document).toEqual(accepted.document);
  });

  it("drops a move whose only destination was a deleted new row and keeps a mixed-anchor move", () => {
    const baseline = document();
    const dependent = createSortingTrialV2(baseline);
    apply(dependent, {
      kind: "create_row",
      row: { type: "note_draft", id: id(700), orderKey: "700", text: "Temporary", state: "excluded", version: 1 },
      destination: gap(id(400), null),
    });
    apply(dependent, { kind: "move_rows", rowIds: [id(100)], destination: gap(id(700), null) });
    apply(dependent, { kind: "delete_rows", rowIds: [id(700)] });

    const restored = resumeSortingTrialV2(dependent.serialize()).accept(baseline, "sorting_only");
    expect(restored.ok, JSON.stringify(restored.diagnostics)).toBe(true);
    expect(activeIds(restored.document)).toEqual(activeIds(baseline));
    expect(validateScriptDocumentV2(restored.document).valid).toBe(true);

    const mixed = createSortingTrialV2(baseline);
    apply(mixed, {
      kind: "create_row",
      row: { type: "note_draft", id: id(701), orderKey: "701", text: "Temporary", state: "excluded", version: 1 },
      destination: gap(id(100), id(200)),
    });
    apply(mixed, { kind: "move_rows", rowIds: [id(300)], destination: gap(id(701), id(200)) });

    const mixedResult = mixed.accept(baseline, "sorting_only");
    expect(mixedResult.ok, JSON.stringify(mixedResult.diagnostics)).toBe(true);
    expect(activeIds(mixedResult.document)).toEqual([id(100), id(300), id(200), id(400)]);
    expect(validateScriptDocumentV2(mixedResult.document).valid).toBe(true);
  });
});
