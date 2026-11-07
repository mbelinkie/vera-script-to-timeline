import { describe, expect, it } from "vitest";

import {
  applyRowEditV2,
  applyStashRowEditV2,
  createRowEditSessionV2,
  deserializeAuthoringDocumentV2,
  serializeAuthoringDocumentV2,
  stashGroupLocationProblemV2,
  stashGroupMembershipProblemV2,
  validateScriptDocumentV2,
} from "../src/authoring-v2.js";
import type { ScriptDocumentV2, StashRowGroupV2 } from "../src/generated/contracts-v2.js";
import { presentAttachedFootageForSortingV2 } from "../src/authoring-v2-rows.js";
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

describe("Stash group organization transactions (issue 366 phase 2)", () => {
  const revision = (doc: ScriptDocumentV2) => doc.rowEditRevision ?? 0;
  const apply = (doc: ScriptDocumentV2, command: Parameters<typeof applyRowEditV2>[2]) =>
    applyRowEditV2(doc, revision(doc), command);
  const gap = { sectionId: null, afterRowId: null, beforeRowId: null };

  it("forms a group from existing compact notes, retaining an embedded clip as ONE complete member and exact Undo", () => {
    const { doc, anchor, note, clip } = researchStashFixture();
    const original = structuredClone(doc);
    const session = createRowEditSessionV2(doc);
    const created = session.apply({ kind: "group_stash_rows", groupId: researchId(900001), rowIds: [anchor.id, note.id],
      createdBy: researchId(900002), createdAt: "2026-11-07T12:00:00Z" });
    expect(created.ok, JSON.stringify(created.diagnostics)).toBe(true);
    expect(created.document.stashGroups).toEqual([{ id: researchId(900001), rowIds: [anchor.id, note.id],
      createdBy: researchId(900002), createdAt: "2026-11-07T12:00:00Z" }]);
    expect(created.document.stashOutline!.map((entry) => entry.kind)).toEqual(["row", "row"]);
    expect(created.document.stash!.flatMap((bundle) => bundle.rows).map((row) => row.id)).toEqual([anchor.id, note.id]);
    expect((created.document.stash![1]!.rows[0] as typeof note).attachedFootage?.clip).toEqual(clip);
    expect(validateScriptDocumentV2(created.document).valid).toBe(true);
    expect(session.undo().ok).toBe(true);
    expect({ ...session.document, rowEditRevision: undefined }).toEqual({ ...original, rowEditRevision: undefined });
    expect(doc).toEqual(original);
  });

  it("group from contiguous Draft rows is one atomic stash operation, under an existing note and section", () => {
    const { doc, anchor, note, clip } = researchStashFixture();
    const parent = researchNote(910000);
    const sectionId = researchId(910100);
    doc.stash = [{ id: researchId(910200), rows: [parent], supportingItems: [] }];
    doc.stashSections = [{ id: sectionId, title: "Scene ideas", rowIds: [] }];
    doc.stashOutline = [{ rowId: parent.id, kind: "note", sectionId, parentRowId: null }];
    const draftNote = structuredClone(note);
    expect(presentAttachedFootageForSortingV2(draftNote)).toBe(true);
    doc.activeDraft.blocks = [structuredClone(anchor), draftNote];
    const original = structuredClone(doc);
    const session = createRowEditSessionV2(doc);
    const result = session.apply({ kind: "stash_group_rows", rowIds: [anchor.id, note.id],
      bundleId: researchId(910300), groupId: researchId(910400), sectionId,
      parentRowId: parent.id, afterRowId: null });
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(result.document.activeDraft.blocks).toEqual([]);
    expect(result.document.stashGroups![0]!.rowIds).toEqual([anchor.id, note.id]);
    expect(result.document.stashOutline!.map((entry) => [entry.rowId, entry.kind, entry.parentRowId, entry.sectionId])).toEqual([
      [parent.id, "note", null, sectionId],
      [anchor.id, "row", parent.id, sectionId],
      [note.id, "row", parent.id, sectionId],
    ]);
    expect((result.document.stash!.flatMap((bundle) => bundle.rows).find((row) => row.id === note.id) as typeof note).attachedFootage?.clip.id).toBe(clip.id);
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
    expect(session.undo().ok).toBe(true);
    expect({ ...session.document, rowEditRevision: undefined }).toEqual({ ...original, rowEditRevision: undefined });
  });

  it("moves an intact group to a named section and beneath a compact note; ungroup preserves rows and one Undo", () => {
    const { doc, members } = groupedDocument();
    const parent = researchNote(920000);
    const sectionId = researchId(920100);
    doc.stash!.push({ id: researchId(920200), rows: [parent], supportingItems: [] });
    doc.stashSections = [{ id: sectionId, title: "Picks", rowIds: [] }];
    doc.stashOutline!.push({ rowId: parent.id, kind: "note", sectionId, parentRowId: null });
    const session = createRowEditSessionV2(doc);
    const moved = session.apply({ kind: "move_stash_group", groupId: researchId(780001),
      sectionId, parentRowId: parent.id, afterRowId: null });
    expect(moved.ok, JSON.stringify(moved.diagnostics)).toBe(true);
    expect(moved.document.stashOutline!.slice(1).map((entry) => entry.parentRowId)).toEqual([parent.id, parent.id]);
    expect(moved.document.stashGroups![0]!.rowIds).toEqual(members);
    expect(validateScriptDocumentV2(moved.document).valid).toBe(true);
    expect(session.undo().ok).toBe(true);
    expect(session.document.stashOutline).toEqual(doc.stashOutline);
    expect(session.apply({ kind: "ungroup_stash_group", groupId: researchId(780001) }).ok).toBe(true);
    expect(session.document.stashGroups).toBeUndefined();
    expect(session.document.stash!.flatMap((bundle) => bundle.rows).length).toBe(3);
    expect(session.undo().ok).toBe(true);
    expect(session.document.stashGroups).toEqual(doc.stashGroups);
  });

  it("places a whole group as independent Draft rows, retaining visuals and reference identity, without group metadata", () => {
    const { doc, members } = groupedDocument();
    const session = createRowEditSessionV2(doc);
    const placed = session.apply({ kind: "place_stash_group", groupId: researchId(780001), destination: gap });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    expect(placed.document.stashGroups).toBeUndefined();
    expect(placed.document.activeDraft.blocks.map((row) => row.id)).toEqual(members);
    expect(placed.document.stashOutline).toBeUndefined();
    const attached = placed.document.activeDraft.blocks[1];
    expect(attached?.type).toBe("narration");
    if (attached?.type === "narration") {
      expect(attached.attachedFootage?.clip.id).toBe(researchId(730100));
      expect(attached.primaryVisualSequence?.slots[0]?.kind).toBe("content");
      const slot = attached.primaryVisualSequence?.slots[0];
      if (slot?.kind === "content") expect(slot.payload.kind).toBe("visual");
      expect(attached.stashOrigin?.kind).toBe("row");
    }
    expect(validateScriptDocumentV2(placed.document).valid).toBe(true);
    expect(session.undo().ok).toBe(true);
    expect(session.document.stashGroups).toEqual(doc.stashGroups);
    expect(session.document.stash).toEqual(doc.stash);
  });

  it("deletes an ordinary group and its rows atomically, but refuses implicit deletion of owned footage", () => {
    const { doc } = groupedDocument();
    const original = structuredClone(doc);
    const refused = apply(doc, { kind: "delete_stash_group", groupId: researchId(780001) });
    expect(refused.ok).toBe(false);
    expect(refused.diagnostics[0]?.code).toBe("STASH_ATTACHMENT_REVIEW_REQUIRED");
    expect(refused.document).toBe(doc);
    expect(doc).toEqual(original);
    const withoutAttachment = structuredClone(doc);
    const note = withoutAttachment.stash![1]!.rows[0];
    if (note.type === "narration") delete note.attachedFootage;
    const session = createRowEditSessionV2(withoutAttachment);
    const deleted = session.apply({ kind: "delete_stash_group", groupId: researchId(780001) });
    expect(deleted.ok, JSON.stringify(deleted.diagnostics)).toBe(true);
    expect(deleted.document.stashGroups).toBeUndefined();
    expect(deleted.document.stash).toEqual([]);
    expect(session.undo().ok).toBe(true);
    expect(session.document.stashGroups).toEqual(withoutAttachment.stashGroups);
  });

  it("refuses legacy partial placement, restore, deletion, outline reorder, section move and direct member edits", () => {
    const { doc, members } = groupedDocument();
    const original = structuredClone(doc);
    const failures: Parameters<typeof applyRowEditV2>[2][] = [
      { kind: "place_stash_rows", rowIds: [members[0]!], destination: gap },
      { kind: "restore_stash_rows", rowIds: [members[0]!], destination: gap },
      { kind: "restore_stash", bundleId: doc.stash![0]!.id, destination: gap },
      { kind: "delete_rows", rowIds: [members[0]!] },
      { kind: "move_stash_rows", rowIds: [members[0]!], sectionId: researchId(930100) },
      { kind: "set_stash_outline", entries: [...doc.stashOutline!].reverse() },
      { kind: "edit_row", rowId: members[0]!, row: structuredClone(doc.stash![0]!.rows[0]) },
    ];
    doc.stashSections = [{ id: researchId(930100), title: "Other", rowIds: [] }];
    for (const command of failures) {
      const result = apply(doc, command);
      expect(result.ok, command.kind + JSON.stringify(result.diagnostics)).toBe(false);
      expect(result.document).toBe(doc);
    }
    const edited = applyStashRowEditV2(doc, revision(doc), {
      bundleId: doc.stash![0]!.id, rowId: members[0]!, row: structuredClone(doc.stash![0]!.rows[0]),
    });
    expect(edited.ok).toBe(false);
    expect(edited.diagnostics[0]?.code).toBe("STASH_GROUP_ATOMIC_REQUIRED");
    expect({ ...doc, stashSections: undefined }).toEqual({ ...original, stashSections: undefined });
  });

  it("refuses noncontiguous or cross-section groups, ambiguous moves, malformed commands and stale revisions", () => {
    const { doc, members } = groupedDocument();
    delete doc.stashGroups;
    const extra = researchNote(940000);
    doc.stash!.push({ id: researchId(940100), rows: [extra], supportingItems: [] });
    doc.stashOutline!.splice(1, 0, { rowId: extra.id, kind: "row", parentRowId: null, sectionId: null });
    const before = structuredClone(doc);
    const no = apply(doc, { kind: "group_stash_rows", rowIds: members, groupId: researchId(940200) });
    expect(no.ok).toBe(false);
    expect(no.diagnostics[0]?.code).toBe("STASH_GROUP_INVALID");
    const malformed = apply(doc, { kind: "group_stash_rows", rowIds: members, groupId: researchId(940200),
      createdBy: undefined } as unknown as Parameters<typeof applyRowEditV2>[2]);
    expect(malformed.diagnostics[0]?.code).toBe("ROW_COMMAND_INVALID");
    const stale = applyRowEditV2(doc, 4, { kind: "group_stash_rows", rowIds: members, groupId: researchId(940200) });
    expect(stale.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    expect(doc).toEqual(before);
    const { doc: grouped } = groupedDocument();
    const badMove = apply(grouped, { kind: "move_stash_group", groupId: researchId(780001), sectionId: null,
      parentRowId: null, afterRowId: members[0]! });
    expect(badMove.ok).toBe(false);
    expect(badMove.document).toBe(grouped);
  });
});
