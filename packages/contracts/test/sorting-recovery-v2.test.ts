import { describe, expect, it } from "vitest";

import {
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
