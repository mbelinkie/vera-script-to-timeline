import { describe, expect, it } from "vitest";

import { validateScriptDocumentV2 } from "@vera/contracts/authoring-v2";
import type { NarrationBlockV2, ScriptDocumentV2 } from "@vera/contracts/v2";

import { createStashRowEditorDocument } from "../browser/stash-row-editor.js";

const researchId = (n: number): string => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;

function researchNote(n: number, text = "Look closer"): NarrationBlockV2 {
  return {
    type: "narration", id: researchId(n), orderKey: `note-${n}`, text, plainDirection: true,
    tokens: [
      { id: researchId(n + 1), value: "Look", startOffset: 0, endOffset: 4, spoken: false },
      { id: researchId(n + 2), value: "closer", startOffset: 5, endOffset: 11, spoken: false },
    ],
    primaryVisualSequence: { id: researchId(n + 3), version: 1, slots: [{
      id: researchId(n + 4), kind: "content", version: 1, relation: { kind: "base" },
      boundaryBefore: { kind: "row_start" }, payload: { kind: "on_camera", presenterChoiceId: null },
      playoutPolicy: "match_structural_interval",
    }] },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
}

function groupedDocument() {
  const members = [researchNote(720100), researchNote(720200)];
  const ids: [string, string] = [members[0]!.id, members[1]!.id];
  const sectionId = researchId(790001);
  const groupId = researchId(790002);
  const doc: ScriptDocumentV2 = {
    schemaVersion: "script-document/v2", id: researchId(1), projectId: researchId(2), title: "Editor stage",
    activeDraft: { blocks: [], supportingItems: [] }, ideaOutline: [], extras: [],
    liveHeadSequence: 0, liveStateVector: "", liveContentHash: `sha256:${"a".repeat(64)}`,
    stash: members.map((row, index) => ({ id: researchId(740100 + index), rows: [row], supportingItems: [] })),
    stashOutline: members.map((row) => ({ rowId: row.id, kind: "row", parentRowId: null, sectionId })),
  };
  doc.stashSections = [{ id: sectionId, title: "Interview", rowIds: [] }];
  doc.stashGroups = [{ id: groupId, rowIds: ids, createdBy: researchId(790003), createdAt: "2026-11-25T12:00:00Z" }];
  const valid = validateScriptDocumentV2(doc);
  expect(valid.valid, JSON.stringify(valid.diagnostics)).toBe(true);
  return { doc, ids, groupId, sectionId };
}

function expectValid(document: ScriptDocumentV2) {
  const result = validateScriptDocumentV2(document);
  expect(result.valid, JSON.stringify(result.diagnostics)).toBe(true);
}

describe("detached saved-row editor document", () => {
  it("moves a named Stash group to a private Draft lane without changing its source document", () => {
    const { doc, ids, groupId, sectionId } = groupedDocument();
    const before = structuredClone(doc);
    const members = doc.stash!.flatMap((bundle) => bundle.rows);

    const stage = createStashRowEditorDocument(doc, members, groupId);

    expectValid(stage);
    expect(stage.activeDraft.blocks.slice(-members.length)).toEqual(members);
    expect(stage.activeDraft.blocks.at(-members.length - 1)).toMatchObject({ type: "section", title: "Saved rows" });
    expect(stage.stash?.flatMap((bundle) => bundle.rows.map((row) => row.id)) ?? []).toEqual([]);
    expect(stage.stashOutline).toEqual([]);
    expect(stage.stashSections).toEqual([{ id: sectionId, title: "Interview", rowIds: [] }]);
    expect(stage.stashGroups).toBeUndefined();
    expect(doc).toEqual(before);
  });

  it("supports one saved row but refuses stale, grouped or mismatched member snapshots", () => {
    const { doc, groupId } = groupedDocument();
    const singleDoc = structuredClone(doc);
    delete singleDoc.stashGroups;
    singleDoc.stashOutline = singleDoc.stashOutline!.filter((entry) => entry.rowId !== researchId(720200));
    singleDoc.stash = singleDoc.stash!.filter((bundle) => bundle.rows[0]?.id !== researchId(720200));
    const anchor = singleDoc.stash![0]!.rows[0]!;
    const member = anchor;

    const stage = createStashRowEditorDocument(singleDoc, [member]);
    expectValid(stage);
    expect(stage.activeDraft.blocks.at(-1)).toEqual(member);
    expect(() => createStashRowEditorDocument(doc, [member], groupId)).toThrow(/membership changed/u);
    expect(() => createStashRowEditorDocument(singleDoc, [{ ...member, orderKey: "stale" }])).toThrow(/saved rows changed/u);
  });
});
