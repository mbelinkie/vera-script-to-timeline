import { describe, expect, it } from "vitest";

import {
  deserializeAuthoringDocumentV2,
  serializeAuthoringDocumentV2,
  stashGroupLocationProblemV2,
  stashGroupMembershipProblemV2,
  validateScriptDocumentV2,
} from "../src/authoring-v2.js";
import type { ScriptDocumentV2, StashRowGroupV2 } from "../src/generated/contracts-v2.js";
import { researchId, researchNote, researchStashFixture } from "./issue-367-fixture.js";

function groupedDocument(): { doc: ScriptDocumentV2; group: StashRowGroupV2; members: string[] } {
  const { doc, anchor, note } = researchStashFixture();
  const members: [string, string] = [anchor.id, note.id];
  doc.stashOutline = doc.stashOutline!.map((entry) => ({ ...entry, kind: "row" }));
  const group: StashRowGroupV2 = {
    id: researchId(780001), rowIds: members,
    createdBy: researchId(780002), createdAt: "2026-11-07T12:00:00Z",
  };
  doc.stashGroups = [group];
  return { doc, group, members };
}

function expectGroupRefusal(document: ScriptDocumentV2, message: RegExp): void {
  const result = validateScriptDocumentV2(document);
  expect(result.valid).toBe(false);
  expect(result.diagnostics.some((diagnostic) =>
    diagnostic.code === "STASH_GROUP_INVALID" && message.test(diagnostic.message)),
  ).toBe(true);
}

describe("persisted Stash groups — identity and location (issue 366 phase 1)", () => {
  it("leaves exact legacy Stash documents valid and unchanged without group metadata", () => {
    const { doc } = researchStashFixture();
    const before = structuredClone(doc);
    expect(validateScriptDocumentV2(doc).valid).toBe(true);
    const saved = serializeAuthoringDocumentV2(doc);
    const restored = deserializeAuthoringDocumentV2(saved);
    expect(restored.ok).toBe(true);
    if (restored.ok) expect(restored.document).toEqual(before);
    expect(doc).toEqual(before);
    expect(Object.hasOwn(doc, "stashGroups")).toBe(false);
    // Legacy without a saved Stash or canonical outline stays valid as well.
    const empty = structuredClone(doc);
    delete empty.stash;
    delete empty.stashOutline;
    expect(validateScriptDocumentV2(empty).valid).toBe(true);
  });

  it("persists references to two full rows, including one owned Research attachment, without copying payloads", () => {
    const { doc, group, members } = groupedDocument();
    const before = structuredClone(doc);
    expect(stashGroupLocationProblemV2(doc, group)).toBeNull();
    expect(stashGroupMembershipProblemV2(doc)).toBeNull();
    const valid = validateScriptDocumentV2(doc);
    expect(valid.valid, JSON.stringify(valid.diagnostics)).toBe(true);
    expect(doc.stash!.flatMap((bundle) => bundle.rows).map((row) => row.id)).toEqual(members);
    const note = doc.stash![1]!.rows[0];
    expect(note.type).toBe("narration");
    if (note.type === "narration") expect(note.attachedFootage?.clip.id).toBe(researchId(730100));
    const stored = serializeAuthoringDocumentV2(doc);
    const restored = deserializeAuthoringDocumentV2(stored);
    expect(restored.ok).toBe(true);
    if (restored.ok) expect(restored.document).toEqual(before);
    expect(doc).toEqual(before);
  });

  it("accepts group siblings below a compact note within one named Stash section", () => {
    const { doc, group } = groupedDocument();
    const parent = researchNote(760000);
    const sectionId = researchId(770000);
    doc.stash!.unshift({ id: researchId(770100), rows: [parent], supportingItems: [] });
    doc.stashSections = [{ id: sectionId, title: "Selected moments", rowIds: [] }];
    doc.stashOutline = [
      { rowId: parent.id, kind: "note", parentRowId: null, sectionId },
      ...doc.stashOutline!.map((entry) => ({ ...entry, parentRowId: parent.id, sectionId })),
    ];
    expect(stashGroupLocationProblemV2(doc, group)).toBeNull();
    expect(validateScriptDocumentV2(doc).valid).toBe(true);
  });

  it("refuses absent members, wrong order, non-adjacency and mixed sibling ownership", () => {
    const { doc, group, members } = groupedDocument();
    const missingOutline = structuredClone(doc);
    delete missingOutline.stashOutline;
    expectGroupRefusal(missingOutline, /canonical Stash outline/);

    const missingMember = structuredClone(doc);
    missingMember.stashGroups![0]!.rowIds[1] = researchId(899901);
    expectGroupRefusal(missingMember, /Every group member/);

    const wrongOrder = structuredClone(doc);
    wrongOrder.stashGroups![0]!.rowIds.reverse();
    expectGroupRefusal(wrongOrder, /consecutive/);

    const nonAdjacent = structuredClone(doc);
    const extra = researchNote(760100);
    nonAdjacent.stash!.push({ id: researchId(770101), rows: [extra], supportingItems: [] });
    nonAdjacent.stashOutline!.splice(1, 0, { rowId: extra.id, kind: "row", parentRowId: null, sectionId: null });
    expectGroupRefusal(nonAdjacent, /consecutive/);

    const mixedParent = structuredClone(doc);
    mixedParent.stashOutline![1]!.parentRowId = members[0]!;
    expectGroupRefusal(mixedParent, /ordinary sibling/);

    const mixedSection = structuredClone(doc);
    mixedSection.stashSections = [{ id: researchId(770000), title: "Other", rowIds: [] }];
    mixedSection.stashOutline![1]!.sectionId = mixedSection.stashSections[0]!.id;
    expectGroupRefusal(mixedSection, /ordinary sibling/);

    const compact = structuredClone(doc);
    compact.stashOutline![0]!.kind = "note";
    expectGroupRefusal(compact, /ordinary sibling/);
    expect(stashGroupLocationProblemV2(doc, group)).toBeNull();
  });

  it("rejects duplicate membership, duplicate group identity and stale compact-return eligibility", () => {
    const { doc, group } = groupedDocument();
    const overlap = structuredClone(doc);
    overlap.stashGroups!.push({ id: researchId(780003), rowIds: [...group.rowIds] });
    expect(stashGroupMembershipProblemV2(overlap)).toMatch(/multiple/);
    expectGroupRefusal(overlap, /multiple/);

    const duplicateId = structuredClone(doc);
    duplicateId.stashGroups![0]!.id = duplicateId.stash![0]!.id;
    const check = validateScriptDocumentV2(duplicateId);
    expect(check.valid).toBe(false);
    expect(check.diagnostics.some((diagnostic) => diagnostic.code === "ENTITY_ID_DUPLICATE" &&
      diagnostic.jsonPath === "/stashGroups/0/id")).toBe(true);

    const compactReturn = structuredClone(doc);
    compactReturn.stash![0]!.rows[0].stashOrigin = {
      kind: "note", parentRowId: null, sectionId: null, afterSiblingRowId: null,
      beforeSiblingRowId: null, returnEligible: true,
    };
    expectGroupRefusal(compactReturn, /return eligibility/);

    // An ordinary row's historical return is not a compact note/clip Return.
    const ordinaryReturn = structuredClone(doc);
    ordinaryReturn.stash![0]!.rows[0].stashOrigin = {
      kind: "row", parentRowId: null, sectionId: null, afterSiblingRowId: null,
      beforeSiblingRowId: null, returnEligible: true,
    };
    expect(validateScriptDocumentV2(ordinaryReturn).valid).toBe(true);
  });

  it("preserves exclusive ownership: a grouped note attachment is one row, never an additional clip", () => {
    const { doc } = groupedDocument();
    expect(validateScriptDocumentV2(doc).diagnostics.some((d) => d.code === "FOOTAGE_OWNER_DUPLICATE")).toBe(false);
    const duplicatedClip = structuredClone(doc.stash![1]!.rows[0]);
    expect(duplicatedClip.type).toBe("narration");
    if (duplicatedClip.type !== "narration") return;
    const clip = duplicatedClip.attachedFootage!.clip;
    const invalid = structuredClone(doc);
    invalid.stash!.push({ id: researchId(799999), rows: [clip], supportingItems: [] });
    invalid.stashOutline!.push({ rowId: clip.id, kind: "row", parentRowId: null, sectionId: null });
    const result = validateScriptDocumentV2(invalid);
    expect(result.valid).toBe(false);
    expect(result.diagnostics.some((d) => d.code === "FOOTAGE_OWNER_DUPLICATE")).toBe(true);
  });
});
