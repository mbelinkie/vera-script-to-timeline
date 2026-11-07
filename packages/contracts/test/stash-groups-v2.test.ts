import { describe, expect, it } from "vitest";

import {
  applyRowEditV2,
  applyStashRowEditV2,
  beginStashGroupMemberStageV2,
  cancelStashGroupMemberStageV2,
  createRowEditSessionV2,
  deserializeAuthoringDocumentV2,
  serializeAuthoringDocumentV2,
  saveStashGroupStageCommandV2,
  stageStashGroupMembersV2,
  stashGroupLocationProblemV2,
  stashGroupMembershipProblemV2,
  validateScriptDocumentV2,
} from "../src/authoring-v2.js";
import type { ScriptDocumentV2, StashRowGroupV2, SupportingItemV2 } from "../src/generated/contracts-v2.js";
import { presentAttachedFootageForSortingV2 } from "../src/authoring-v2-rows.js";
import { researchId, researchNote, researchOccurrence, researchStashFixture } from "./issue-367-fixture.js";

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

  it("rejects semantically invalid saved groups during deserialization and serialization", () => {
    const { doc } = groupedDocument();
    doc.stashGroups![0]!.rowIds.reverse();
    const diagnostics = validateScriptDocumentV2(doc).diagnostics;
    expect(diagnostics.some((item) => item.code === "STASH_GROUP_INVALID")).toBe(true);
    const restored = deserializeAuthoringDocumentV2(JSON.stringify(doc));
    expect(restored.ok).toBe(false);
    if (!restored.ok) expect(restored.diagnostics.some((item) => item.code === "STASH_GROUP_INVALID")).toBe(true);
    expect(() => serializeAuthoringDocumentV2(doc)).toThrow(/consecutive/);
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

  it("keeps row-local citations with a flattened group and refuses cross-boundary supporting anchors atomically", () => {
    const { doc, members } = groupedDocument();
    const row = doc.stash![0]!.rows[0];
    if (row.type !== "narration") throw new Error("Fixture requires a narration member");
    delete row.plainDirection;
    for (const token of row.tokens) delete token.spoken;
    const word = row.tokens[0]!;
    const wordAnchor = (blockId: string, tokenId: string, quotedWord: string) => ({
      kind: "word" as const,
      anchor: { blockId, tokenId, quotedWord, affinity: "before" as const, anchorVersion: 1 },
    });
    const citation: SupportingItemV2 = {
      id: researchId(950001), version: 1, orderKey: "cited",
      role: "citation", content: "Evidence from this shot",
      placement: { kind: "point", anchor: wordAnchor(row.id, word.id, word.value) },
      displayAttachment: wordAnchor(row.id, word.id, word.value),
    };
    doc.stash![0]!.supportingItems.push(citation);
    const original = structuredClone(doc);
    const placed = apply(doc, { kind: "place_stash_group", groupId: researchId(780001), destination: gap });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    expect(placed.document.activeDraft.supportingItems).toEqual([citation]);
    expect(placed.document.activeDraft.blocks.map((block) => block.id)).toEqual(members);
    expect(doc).toEqual(original);

    const mixed = structuredClone(doc);
    const extra = researchNote(950100);
    delete extra.plainDirection;
    for (const token of extra.tokens) delete token.spoken;
    mixed.stash![0]!.rows.push(extra);
    mixed.stashOutline!.push({ rowId: extra.id, kind: "row", parentRowId: null, sectionId: null });
    mixed.stash![0]!.supportingItems[0]!.displayAttachment = wordAnchor(extra.id, extra.tokens[0]!.id, extra.tokens[0]!.value);
    const before = structuredClone(mixed);
    const refused = apply(mixed, { kind: "place_stash_group", groupId: researchId(780001), destination: gap });
    expect(refused.ok).toBe(false);
    expect(refused.diagnostics.some((item) => item.code === "ROW_REFERENCE_REVIEW_REQUIRED")).toBe(true);
    expect(refused.document).toBe(mixed);
    expect(mixed).toEqual(before);
  });

  it("guards audio intent and refuses dependent outline children instead of flattening a compact note", () => {
    const { doc, members } = groupedDocument();
    doc.rowAudioSpans = [{ id: researchId(960001), startRowId: members[0]!, endRowId: members[0]!,
      source: { mediaReferenceId: researchId(960002), artifactId: researchId(960003),
        artifactVersion: 1, contentHash: `sha256:${"c".repeat(64)}` }, settings: {} }];
    const original = structuredClone(doc);
    const moving = apply(doc, { kind: "move_stash_group", groupId: researchId(780001),
      sectionId: null, parentRowId: null, afterRowId: null });
    expect(moving.ok).toBe(false);
    expect(moving.diagnostics[0]?.code).toBe("AUDIO_REVIEW_REQUIRED");
    const placing = apply(doc, { kind: "place_stash_group", groupId: researchId(780001), destination: gap });
    expect(placing.ok).toBe(false);
    expect(placing.diagnostics.some((item) => item.code === "AUDIO_REVIEW_REQUIRED")).toBe(true);
    const reordered = apply(doc, { kind: "set_stash_outline", entries: [...doc.stashOutline!].reverse() });
    expect(reordered.diagnostics[0]?.code).toBe("AUDIO_REVIEW_REQUIRED");
    expect(doc).toEqual(original);

    const { doc: compact, anchor, note } = researchStashFixture();
    compact.stashOutline![1]!.parentRowId = anchor.id;
    // The parent and its child are both selected. Converting the parent would
    // silently discard the child relationship unless refused explicitly.
    const refused = apply(compact, { kind: "group_stash_rows", rowIds: [anchor.id, note.id], groupId: researchId(960004) });
    expect(refused.ok).toBe(false);
    expect(refused.diagnostics[0]?.message).toMatch(/dependent branch/);
  });

  it("preserves original active transition pairs and refuses standalone edits to an embedded grouped clip", () => {
    const { doc, members } = groupedDocument();
    doc.stash = [{ id: researchId(970001), rows: [doc.stash![0]!.rows[0], doc.stash![1]!.rows[0]], supportingItems: [] }];
    doc.rowTransitions = [{ id: researchId(970002), fromRowId: members[0]!, toRowId: members[1]!,
      effect: "crossfade", settings: { frames: 6 }, state: "active" }];
    expect(validateScriptDocumentV2(doc).valid).toBe(true);
    const trim = apply(doc, { kind: "trim_research_clip", clipRowId: researchId(730100), edge: "in", frame: 30 });
    expect(trim.ok).toBe(false);
    expect(trim.diagnostics[0]?.code).toBe("STASH_GROUP_ATOMIC_REQUIRED");
    const placed = apply(doc, { kind: "place_stash_group", groupId: researchId(780001), destination: gap });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    expect(placed.document.rowTransitions).toEqual(doc.rowTransitions);
    expect(validateScriptDocumentV2(placed.document).valid).toBe(true);
  });
});

describe("one-Save staged Stash group member editor (issue 366 phase 3)", () => {
  const revision = (doc: ScriptDocumentV2) => doc.rowEditRevision ?? 0;
  const apply = (doc: ScriptDocumentV2, command: Parameters<typeof applyRowEditV2>[2]) =>
    applyRowEditV2(doc, revision(doc), command);
  const withoutOwnedFootage = () => {
    const { doc, group, members } = groupedDocument();
    const note = doc.stash![1]!.rows[0];
    if (note.type !== "narration") throw new Error("Expected a narration member");
    delete note.attachedFootage;
    return { doc, group, members };
  };

  it("stages independently and Cancel leaves the exact document and revision untouched", () => {
    const { doc, group } = groupedDocument();
    const original = structuredClone(doc);
    const opened = beginStashGroupMemberStageV2(doc, group.id)!;
    expect(opened.expectedRowIds).toEqual(group.rowIds);
    const edited = structuredClone(opened.members);
    edited[0]!.orderKey = "edited only in staging";
    const staged = stageStashGroupMembersV2(opened, [...edited, researchNote(980001)]);
    staged.members[0]!.orderKey = "further local edits";
    expect(opened.members[0]!.orderKey).not.toBe(staged.members[0]!.orderKey);
    expect(cancelStashGroupMemberStageV2(staged)).toBeNull();
    expect(doc).toEqual(original);
    expect(revision(doc)).toBe(0);
    expect(beginStashGroupMemberStageV2(doc, researchId(980000))).toBeNull();
  });

  it("commits mixed replacement, new member, removed member and anchored citation in one revision / one Undo", () => {
    const { doc, group } = withoutOwnedFootage();
    const anchor = doc.stash![0]!.rows[0];
    if (anchor.type !== "narration") throw new Error("Expected narration");
    delete anchor.plainDirection;
    for (const token of anchor.tokens) delete token.spoken;
    const token = anchor.tokens[0]!;
    const cite: SupportingItemV2 = {
      id: researchId(981100), version: 1, orderKey: "citation", role: "citation", content: "Original research",
      placement: { kind: "point", anchor: { kind: "word", anchor: {
        blockId: anchor.id, tokenId: token.id, quotedWord: token.value, affinity: "before", anchorVersion: 1,
      } } },
    };
    doc.stash![0]!.supportingItems.push(cite);
    doc.rowReferences = [{ id: researchId(981101), rowId: anchor.id, kind: "comment", anchor: { tokenId: token.id } }];
    anchor.stashOrigin = { kind: "row", parentRowId: null, sectionId: null,
      afterSiblingRowId: null, beforeSiblingRowId: null, returnEligible: true };
    const original = structuredClone(doc);
    const opened = beginStashGroupMemberStageV2(doc, group.id)!;
    const edited = structuredClone(opened.members[0]!);
    edited.orderKey = "authored reorder label";
    edited.stashOrigin = { ...anchor.stashOrigin, returnEligible: true, sectionId: researchId(981102) };
    const newRow = researchNote(982000);
    const session = createRowEditSessionV2(doc);
    const command = saveStashGroupStageCommandV2(stageStashGroupMembersV2(opened, [newRow, edited]));
    const saved = session.apply(command, opened.expectedRevision);
    expect(saved.ok, JSON.stringify(saved.diagnostics)).toBe(true);
    expect(saved.document.rowEditRevision).toBe(1);
    expect(session.undoDepth).toBe(1);
    expect(saved.document.stashGroups).toEqual([{ ...group, rowIds: [newRow.id, anchor.id] }]);
    expect(saved.document.stashOutline!.map((entry) => entry.rowId)).toEqual([newRow.id, anchor.id]);
    const surviving = saved.document.stash!.flatMap((bundle) => bundle.rows).find((row) => row.id === anchor.id)!;
    expect(surviving.orderKey).toBe(edited.orderKey);
    expect(surviving.stashOrigin).toEqual({ ...anchor.stashOrigin, returnEligible: false });
    expect(saved.document.stash!.flatMap((bundle) => bundle.supportingItems)).toEqual([cite]);
    expect(saved.document.rowReferences).toEqual(original.rowReferences);
    expect(saved.document.stashGroups![0]!.createdBy).toBe(group.createdBy);
    expect(validateScriptDocumentV2(saved.document).valid).toBe(true);
    const restored = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(saved.document));
    expect(restored.ok).toBe(true);
    if (restored.ok) expect(restored.document).toEqual(saved.document);
    expect(session.undo().ok).toBe(true);
    expect({ ...session.document, rowEditRevision: undefined }).toEqual({ ...original, rowEditRevision: undefined });
    expect(doc).toEqual(original);
  });

  it("reorders existing members and incorporates adjacent independent saved rows without copying provenance", () => {
    const { doc, group, members } = groupedDocument();
    const extra = researchNote(983000);
    doc.stash!.push({ id: researchId(983100), rows: [extra], supportingItems: [] });
    doc.stashOutline!.push({ rowId: extra.id, kind: "row", parentRowId: null, sectionId: null });
    const input = structuredClone(doc);
    const opened = beginStashGroupMemberStageV2(doc, group.id)!;
    const stage = stageStashGroupMembersV2(opened, [opened.members[1]!, extra, opened.members[0]!]);
    const saved = apply(doc, saveStashGroupStageCommandV2(stage));
    expect(saved.ok, JSON.stringify(saved.diagnostics)).toBe(true);
    expect(saved.document.stashGroups![0]!.rowIds).toEqual([members[1], extra.id, members[0]]);
    expect(saved.document.stashOutline!.map((entry) => entry.rowId)).toEqual([members[1], extra.id, members[0]]);
    expect(saved.document.stash!.flatMap((bundle) => bundle.rows).length).toBe(3);
    expect(saved.document.stash![2]!.rows).toEqual([extra]);
    expect(validateScriptDocumentV2(saved.document).valid).toBe(true);
    expect(doc).toEqual(input);
  });

  it("normalizes one member to an ordinary saved row and zero to no group or saved members", () => {
    const one = withoutOwnedFootage();
    const original = structuredClone(one.doc);
    const session = createRowEditSessionV2(one.doc);
    const opened = beginStashGroupMemberStageV2(one.doc, one.group.id)!;
    const saved = session.apply(saveStashGroupStageCommandV2(stageStashGroupMembersV2(opened, [opened.members[0]!])), opened.expectedRevision);
    expect(saved.ok, JSON.stringify(saved.diagnostics)).toBe(true);
    expect(saved.document.stashGroups).toBeUndefined();
    expect(saved.document.stashOutline!.map((entry) => entry.rowId)).toEqual([one.members[0]]);
    expect(saved.document.stash!.flatMap((bundle) => bundle.rows).length).toBe(1);
    expect(session.undo().ok).toBe(true);
    expect({ ...session.document, rowEditRevision: undefined }).toEqual({ ...original, rowEditRevision: undefined });

    const zero = withoutOwnedFootage();
    const stage = beginStashGroupMemberStageV2(zero.doc, zero.group.id)!;
    const removed = apply(zero.doc, saveStashGroupStageCommandV2(stageStashGroupMembersV2(stage, [])));
    expect(removed.ok, JSON.stringify(removed.diagnostics)).toBe(true);
    expect(removed.document.stashGroups).toBeUndefined();
    expect(removed.document.stash).toEqual([]);
    expect(removed.document.stashOutline).toBeUndefined();
    expect(validateScriptDocumentV2(removed.document).valid).toBe(true);
  });

  it("refuses stale membership, stale revisions, malformed or duplicate members with original-object identity", () => {
    const { doc, group } = groupedDocument();
    const stage = beginStashGroupMemberStageV2(doc, group.id)!;
    const command = saveStashGroupStageCommandV2(stage);
    const candidates: Parameters<typeof applyRowEditV2>[2][] = [
      { ...command, expectedRowIds: [...stage.expectedRowIds].reverse() },
      { ...command, members: [stage.members[0]!, stage.members[0]!] },
      { ...command, members: [stage.members[0]!, { ...stage.members[1]!, id: stage.members[0]!.id }] },
      { ...command, members: [researchNote(984200), ...stage.members], ignored: true } as unknown as Parameters<typeof applyRowEditV2>[2],
      { ...command, members: [{ ...researchNote(984400), stashOrigin: {
        kind: "row", sectionId: null, parentRowId: null, afterSiblingRowId: null, beforeSiblingRowId: null, returnEligible: true,
      } }, ...stage.members] },
    ];
    for (const candidate of candidates) {
      const before = structuredClone(doc);
      const refused = apply(doc, candidate);
      expect(refused.ok, JSON.stringify(refused.diagnostics)).toBe(false);
      expect(refused.document).toBe(doc);
      expect(doc).toEqual(before);
    }
    const stale = applyRowEditV2(doc, 8, command);
    expect(stale.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    expect(stale.document).toBe(doc);
    const advanced = apply(doc, { kind: "create_stash_section", sectionId: researchId(984500), title: "After opening" });
    expect(advanced.ok, JSON.stringify(advanced.diagnostics)).toBe(true);
    const staleStage = apply(advanced.document, command);
    expect(staleStage.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    expect(staleStage.document).toBe(advanced.document);
    const missing = apply(doc, { ...command, groupId: researchId(984300) });
    expect(missing.diagnostics[0]?.code).toBe("STASH_GROUP_NOT_FOUND");
  });

  it("refuses nonadjacent additions, identity/type swaps, owned-clip changes and audio without partial publication", () => {
    const { doc, group } = groupedDocument();
    const opened = beginStashGroupMemberStageV2(doc, group.id)!;
    const extra = researchNote(985000);
    const separator = researchNote(985100);
    doc.stash!.push({ id: researchId(985200), rows: [separator, extra], supportingItems: [] });
    doc.stashOutline!.push({ rowId: separator.id, kind: "row", parentRowId: null, sectionId: null },
      { rowId: extra.id, kind: "row", parentRowId: null, sectionId: null });
    const no = apply(doc, saveStashGroupStageCommandV2(stageStashGroupMembersV2(opened, [...opened.members, extra])));
    expect(no.ok).toBe(false);
    expect(no.diagnostics[0]?.code).toBe("STASH_GROUP_MEMBERS_INVALID");
    expect(no.document).toBe(doc);

    const attached = structuredClone(opened.members[1]!);
    if (attached.type !== "narration" || !attached.attachedFootage) throw new Error("Expected owned clip");
    attached.attachedFootage.clip.id = researchId(985300);
    const clipEdit = apply(doc, saveStashGroupStageCommandV2(stageStashGroupMembersV2(opened, [opened.members[0]!, attached])));
    expect(clipEdit.diagnostics[0]?.code).toBe("STASH_ATTACHMENT_REVIEW_REQUIRED");
    const removedOwner = apply(doc, saveStashGroupStageCommandV2(stageStashGroupMembersV2(opened, [opened.members[0]!])));
    expect(removedOwner.diagnostics[0]?.code).toBe("STASH_ATTACHMENT_REVIEW_REQUIRED");
    const badType = apply(doc, saveStashGroupStageCommandV2(stageStashGroupMembersV2(opened, [
      { ...researchOccurrence(985500), id: opened.members[0]!.id }, opened.members[1]!,
    ])));
    expect(badType.ok).toBe(false);
    expect(badType.diagnostics[0]?.code).toBe("STASH_GROUP_MEMBERS_INVALID");
    doc.rowAudioSpans = [{ id: researchId(985400), startRowId: opened.members[0]!.id,
      endRowId: opened.members[0]!.id, source: { mediaReferenceId: researchId(985401),
        artifactId: researchId(985402), artifactVersion: 1, contentHash: `sha256:${"b".repeat(64)}` }, settings: {} }];
    const original = structuredClone(doc);
    const reordered = apply(doc, saveStashGroupStageCommandV2(stageStashGroupMembersV2(opened, [...opened.members].reverse())));
    expect(reordered.diagnostics[0]?.code).toBe("AUDIO_REVIEW_REQUIRED");
    expect(reordered.document).toBe(doc);
    expect(doc).toEqual(original);
  });

  it("refuses missing supporting evidence and source identity conflicts rather than silently dropping citations", () => {
    const { doc, group } = withoutOwnedFootage();
    const first = doc.stash![0]!.rows[0];
    if (first.type !== "narration") throw new Error("Expected note");
    delete first.plainDirection;
    first.tokens.forEach((token) => { delete token.spoken; });
    doc.stash![0]!.supportingItems.push({ id: researchId(986000), version: 1, orderKey: "citation", role: "citation", content: "Evidence",
      placement: { kind: "point", anchor: { kind: "word", anchor: {
        blockId: first.id, tokenId: first.tokens[0]!.id, quotedWord: first.tokens[0]!.value,
        affinity: "before", anchorVersion: 1,
      } } },
    });
    const opened = beginStashGroupMemberStageV2(doc, group.id)!;
    const lost = apply(doc, saveStashGroupStageCommandV2(stageStashGroupMembersV2(opened, [opened.members[1]!])));
    expect(lost.diagnostics[0]?.code).toBe("ROW_REFERENCE_REVIEW_REQUIRED");
    const edited = structuredClone(opened.members[0]!);
    if (edited.type !== "narration") throw new Error("Expected note");
    edited.tokens[0]!.value = "WRONG";
    const invalid = apply(doc, saveStashGroupStageCommandV2(stageStashGroupMembersV2(opened, [edited, opened.members[1]!])));
    expect(invalid.diagnostics[0]?.code).toBe("ROW_REFERENCE_REVIEW_REQUIRED");
    const collision = researchNote(986100);
    collision.id = opened.members[0]!.id;
    expect(apply(doc, saveStashGroupStageCommandV2(stageStashGroupMembersV2(opened, [opened.members[0]!, collision, opened.members[1]!]))).ok).toBe(false);
  });

  it("refuses missing Research source provenance, duplicate embedded clip owners and stale comment token anchors", () => {
    const { doc, group } = groupedDocument();
    const opened = beginStashGroupMemberStageV2(doc, group.id)!;
    const missingSource = researchOccurrence(987000);
    delete missingSource.researchClip;
    const invalidSource = apply(doc, saveStashGroupStageCommandV2(stageStashGroupMembersV2(opened, [
      ...opened.members, missingSource,
    ])));
    expect(invalidSource.ok).toBe(false);
    expect(invalidSource.diagnostics.some((item) => item.code === "RESEARCH_CLIP_INVALID")).toBe(true);
    expect(invalidSource.document).toBe(doc);

    const duplicateOwner = researchOccurrence(987100);
    duplicateOwner.id = researchId(730100);
    const duplicate = apply(doc, saveStashGroupStageCommandV2(stageStashGroupMembersV2(opened, [
      ...opened.members, duplicateOwner,
    ])));
    expect(duplicate.ok).toBe(false);
    expect(duplicate.diagnostics.some((item) => item.code === "FOOTAGE_OWNER_DUPLICATE" || item.code === "ENTITY_ID_DUPLICATE")).toBe(true);
    expect(duplicate.document).toBe(doc);

    const anchor = doc.stash![0]!.rows[0];
    if (anchor.type !== "narration") throw new Error("Expected narration");
    doc.rowReferences = [{ id: researchId(987200), kind: "comment", rowId: anchor.id,
      anchor: { tokenId: anchor.tokens[0]!.id, quotedWord: anchor.tokens[0]!.value } }];
    const prior = structuredClone(doc);
    const changed = structuredClone(opened.members[0]!);
    if (changed.type !== "narration") throw new Error("Expected narration");
    changed.tokens[0]!.id = researchId(987201);
    const refused = apply(doc, saveStashGroupStageCommandV2(stageStashGroupMembersV2(opened, [changed, opened.members[1]!])));
    expect(refused.diagnostics[0]?.code).toBe("ROW_REFERENCE_REVIEW_REQUIRED");
    expect(refused.document).toBe(doc);
    expect(doc).toEqual(prior);
  });
});
