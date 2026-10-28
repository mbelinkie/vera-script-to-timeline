import { describe, expect, it } from "vitest";

import {
  createSortingTrialV2,
  resumeSortingTrialV2,
  validateScriptDocumentV2,
  type RowEditCommandV2,
} from "../src/authoring-v2.js";
import type { NarrationBlockV2, ScriptDocumentV2 } from "../src/generated/contracts-v2.js";

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

function document(rowNumbers = [100, 200, 300, 400, 500]): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2",
    id: id(1),
    projectId: id(2),
    title: "Sorting edit invariants",
    activeDraft: { blocks: rowNumbers.map(row), supportingItems: [] },
    ideaOutline: [],
    extras: [],
    liveHeadSequence: 0,
    liveStateVector: "",
    liveContentHash: `sha256:${"a".repeat(64)}`,
  };
}

const gap = (afterRowId: string | null, beforeRowId: string | null) => ({
  sectionId: null,
  afterRowId,
  beforeRowId,
});

function comparable(value: ScriptDocumentV2): ScriptDocumentV2 {
  const copy = structuredClone(value);
  delete copy.rowEditRevision;
  if (copy.stash?.length === 0) delete copy.stash;
  return copy;
}

function commandsFor(caseIndex: number): RowEditCommandV2[] {
  const currentIds = [id(100), id(200), id(300), id(400), id(500)];
  const commands: RowEditCommandV2[] = [];
  let step = 0;
  let birth = 0;

  const create = () => {
    const rowId = 10_000 + caseIndex * 10 + birth;
    const index = (caseIndex + birth * 3 + step) % (currentIds.length + 1);
    commands.push({
      kind: "create_row",
      row: row(rowId),
      destination: gap(currentIds[index - 1] ?? null, currentIds[index] ?? null),
    });
    currentIds.splice(index, 0, id(rowId));
    birth += 1;
    step += 1;
  };

  const remove = (count: 1 | 2) => {
    const first = (caseIndex * 3 + step) % (currentIds.length - count + 1);
    const selected = currentIds.slice(first, first + count);
    commands.push({ kind: "delete_rows", rowIds: selected });
    currentIds.splice(first, count);
    step += 1;
  };

  switch (caseIndex % 4) {
    case 0:
      create();
      create();
      remove(1);
      break;
    case 1:
      remove(2);
      create();
      if (caseIndex % 8 === 1) create();
      break;
    case 2:
      create();
      remove(1);
      create();
      break;
    case 3:
      create();
      create();
      remove(2);
      break;
  }

  return commands;
}

describe("Sorting row-edit invariants", () => {
  it.each(Array.from({ length: 65 }, (_, index) => index))("keeps content-only acceptance outcomes consistent for sequence %i", (caseIndex) => {
    // These 64 deterministic cases vary exact insertion gaps, fresh row IDs,
    // single/adjacent-pair deletions, and whether deletion comes before or
    // after creation. The final case deletes all three baseline rows before
    // creating at the empty-list null/null gap. Every operation goes through
    // the public trial API.
    const baseline = caseIndex === 64 ? document([100, 200, 300]) : document();
    const trial = createSortingTrialV2(baseline);
    const commands: RowEditCommandV2[] = caseIndex === 64
      ? [
        { kind: "delete_rows", rowIds: [id(100), id(200), id(300)] },
        { kind: "create_row", row: row(80_000), destination: gap(null, null) },
      ]
      : commandsFor(caseIndex);
    for (const command of commands) {
      const result = trial.apply(command);
      expect(result.ok, `case ${caseIndex}: ${JSON.stringify(result.diagnostics)}`).toBe(true);
    }

    const saved = trial.serialize();
    const all = resumeSortingTrialV2(saved).accept(baseline);
    const editsOnly = resumeSortingTrialV2(saved).accept(baseline, "edits_only");
    const sortingOnly = resumeSortingTrialV2(saved).accept(baseline, "sorting_only");

    for (const [outcome, result] of [["all", all], ["edits_only", editsOnly], ["sorting_only", sortingOnly]] as const) {
      expect(result.ok, `case ${caseIndex}, ${outcome}: ${JSON.stringify(result.diagnostics)}`).toBe(true);
      if (!result.ok) throw new Error(`case ${caseIndex}, ${outcome} was refused`);
      expect(validateScriptDocumentV2(result.document).valid, `case ${caseIndex}, invalid ${outcome} result`).toBe(true);
    }

    if (!all.ok || !editsOnly.ok || !sortingOnly.ok) throw new Error(`case ${caseIndex} acceptance failed`);
    expect(comparable(editsOnly.document), `case ${caseIndex}: edits_only differs from default all`).toEqual(comparable(all.document));
    expect(comparable(sortingOnly.document), `case ${caseIndex}: sorting_only differs from baseline`).toEqual(comparable(baseline));
  });
});
