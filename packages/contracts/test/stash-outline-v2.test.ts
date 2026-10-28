import { describe, expect, it } from "vitest";

import {
  applyRowEditV2,
  applyStageDirectionEditV2,
  applyStashRowEditV2,
  applyVisualSequenceEditV2,
  createRowEditSessionV2,
  createSortingTrialV2,
  deserializeAuthoringDocumentV2,
  resumeSortingTrialV2,
  serializeAuthoringDocumentV2,
  undoStageDirectionEditV2,
  validateScriptDocumentV2,
} from "../src/authoring-v2.js";
import type { NarrationBlockV2, ScriptDocumentV2, StashOutlineEntryV2, VisualOnlyBlockV2 } from "../src/generated/contracts-v2.js";

const id = (value: number) => `00000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;
const contentHash = `sha256:${"a".repeat(64)}`;

function narration(value: number): NarrationBlockV2 {
  const first = `note${value}`;
  const text = `${first} words`;
  return {
    type: "narration",
    id: id(value),
    orderKey: `note-${value}`,
    text,
    tokens: [
      { id: id(value + 1000), value: first, startOffset: 0, endOffset: first.length },
      { id: id(value + 2000), value: "words", startOffset: first.length + 1, endOffset: text.length },
    ],
    primaryVisualSequence: {
      id: id(value + 3000),
      version: 1,
      slots: [{
        id: id(value + 4000), kind: "content", version: 1, relation: { kind: "base" },
        boundaryBefore: { kind: "row_start" }, payload: { kind: "on_camera", presenterChoiceId: null },
        playoutPolicy: "match_structural_interval",
      }],
    },
    overlayEvents: [],
    timingPolicy: "narration_spine",
    state: "active",
    notes: [],
    version: 1,
  };
}

function clip(value: number): VisualOnlyBlockV2 {
  return {
    type: "visual_only",
    id: id(value),
    orderKey: `clip-${value}`,
    payload: {
      kind: "visual",
      payloadId: id(value + 1000),
      pictureKind: "clip",
      source: { kind: "media_reference", mediaReferenceId: id(value + 2000) },
      audioPolicy: "mute",
      framingPolicy: "contain",
    },
    visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 0, durationFrames: 48 } },
    version: 1,
  };
}

function documentWith(blocks: ScriptDocumentV2["activeDraft"]["blocks"] = []): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2",
    id: id(1),
    projectId: id(2),
    title: "Nested Stash outline test",
    activeDraft: { blocks, supportingItems: [] },
    ideaOutline: [],
    extras: [],
    liveHeadSequence: 0,
    liveStateVector: "",
    liveContentHash: contentHash,
  };
}

function gap(sectionId: string | null, afterRowId: string | null, beforeRowId: string | null) {
  return { sectionId, afterRowId, beforeRowId };
}

function outline(doc: ScriptDocumentV2) {
  return doc.stashOutline ?? [];
}

describe("mixed Stash outline contract", () => {
  it("stores default-direction notes, explicit mixed notes, and standalone footage in saved-row payloads", () => {
    const plain = narration(100000);
    const authored = narration(110000);
    const first = authored.tokens[0];
    const second = authored.tokens[1];
    if (!second) throw new Error("The authored fixture needs two tokens.");
    authored.text = `[${first.value}] ${second.value}`;
    authored.tokens = [
      { ...first, startOffset: 1, endOffset: first.value.length + 1, spoken: false },
      { ...second, startOffset: first.value.length + 3, endOffset: authored.text.length },
    ];
    let result = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(120000), row: plain,
      sectionId: null, parentRowId: null, afterRowId: null,
    });
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    const defaultNote = result.document.stash?.[0]?.rows[0] as NarrationBlockV2;
    expect(defaultNote.text).toBe(`[${plain.text}]`);
    expect(defaultNote.tokens.map((token) => token.id)).toEqual(plain.tokens.map((token) => token.id));
    expect(defaultNote.tokens.every((token) => token.spoken === false)).toBe(true);

    result = applyRowEditV2(result.document, 1, {
      kind: "create_stash_note", bundleId: id(120001), row: authored,
      sectionId: null, parentRowId: null, afterRowId: plain.id, mode: "authored",
    });
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(result.document.stash?.[1]?.rows[0]).toEqual(authored);

    result = applyRowEditV2(result.document, 2, {
      kind: "create_stash_clip", bundleId: id(120002), row: clip(130000),
      sectionId: null, parentRowId: null, afterRowId: authored.id,
    });
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(outline(result.document)).toEqual([
      { rowId: plain.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: authored.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: id(130000), kind: "clip", parentRowId: null, sectionId: null },
    ]);
    const saved = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(result.document));
    expect(saved.ok).toBe(true);
    if (saved.ok) expect(saved.document.stashOutline).toEqual(result.document.stashOutline);
  });

  it("creates, saves, and places a plain Stash note before the first active row exists", () => {
    const note = narration(105000);
    const created = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(105001), row: note,
      sectionId: null, parentRowId: null, afterRowId: null,
    });
    expect(created.ok, JSON.stringify(created.diagnostics)).toBe(true);
    const saved = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(created.document));
    expect(saved.ok).toBe(true);
    if (!saved.ok) return;
    const placed = applyRowEditV2(saved.document, 1, {
      kind: "place_stash_rows", rowIds: [note.id], destination: gap(null, null, null),
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    expect(placed.document.activeDraft.blocks.map((block) => block.id)).toEqual([note.id]);
    expect(outline(placed.document)).toEqual([]);
  });

  it("upgrades legacy section order once and keeps the mixed outline as the ordering source", () => {
    const unsectioned = narration(140000);
    const sectioned = narration(150000);
    const legacy = documentWith();
    legacy.stash = [{ id: id(160000), rows: [sectioned, unsectioned], supportingItems: [] }];
    legacy.stashSections = [{ id: id(160001), title: "Research", rowIds: [sectioned.id] }];
    const upgraded = applyRowEditV2(legacy, 0, { kind: "move_stash_rows", rowIds: [unsectioned.id], sectionId: null });
    expect(upgraded.ok, JSON.stringify(upgraded.diagnostics)).toBe(true);
    expect(upgraded.document.stashSections).toEqual([{ id: id(160001), title: "Research", rowIds: [] }]);
    expect(outline(upgraded.document)).toEqual([
      { rowId: unsectioned.id, kind: "row", parentRowId: null, sectionId: null },
      { rowId: sectioned.id, kind: "row", parentRowId: null, sectionId: id(160001) },
    ]);
    const invalid = structuredClone(upgraded.document);
    invalid.stashOutline![0]!.rowId = id(199999);
    expect(validateScriptDocumentV2(invalid).diagnostics.some((item) => item.code === "ROW_REFERENCE_INVALID")).toBe(true);
  });

  it("places a mixed branch in preorder and returns its source kinds without bundling unselected notes", () => {
    const ordinary = narration(200000);
    const parent = narration(210000);
    const childClip = clip(220000);
    const untouched = narration(230000);
    let document = applyRowEditV2(documentWith([ordinary]), 0, { kind: "stash_rows", rowIds: [ordinary.id], bundleId: id(240000) }).document;
    document = applyRowEditV2(document, 1, {
      kind: "create_stash_note", bundleId: id(240001), row: parent,
      sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 2, {
      kind: "create_stash_clip", bundleId: id(240002), row: childClip,
      sectionId: null, parentRowId: parent.id, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 3, {
      kind: "create_stash_note", bundleId: id(240003), row: untouched,
      sectionId: null, parentRowId: null, afterRowId: parent.id,
    }).document;
    const arranged: StashOutlineEntryV2[] = [
      { rowId: parent.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: childClip.id, kind: "clip", parentRowId: parent.id, sectionId: null },
      { rowId: ordinary.id, kind: "row", parentRowId: parent.id, sectionId: null },
      { rowId: untouched.id, kind: "note", parentRowId: null, sectionId: null },
    ];
    const organized = applyRowEditV2(document, 4, { kind: "set_stash_outline", entries: arranged });
    expect(organized.ok, JSON.stringify(organized.diagnostics)).toBe(true);
    const placed = applyRowEditV2(organized.document, 5, { kind: "place_stash_rows", rowIds: [parent.id], destination: gap(null, null, null) });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    expect(placed.document.activeDraft.blocks.map((block) => block.id)).toEqual([parent.id, childClip.id, ordinary.id]);
    expect(outline(placed.document)).toEqual([arranged[3]]);
    expect(placed.document.stash?.flatMap((bundle) => bundle.rows.map((row) => row.id))).toEqual([untouched.id]);
    expect(placed.document.activeDraft.blocks.filter((block) => block.type !== "section").map((block) => block.stashOrigin?.kind)).toEqual(["note", "clip", "row"]);

    const oldRestore = applyRowEditV2(placed.document, 6, { kind: "restore_stash_rows", rowIds: [parent.id], destination: gap(null, ordinary.id, null) });
    expect(oldRestore.diagnostics[0]?.code).toBe("STASH_OUTLINE_PLACEMENT_REQUIRED");
    expect(oldRestore.document).toBe(placed.document);

    const returned = applyRowEditV2(placed.document, 6, { kind: "stash_rows", rowIds: [parent.id, childClip.id, ordinary.id], bundleId: id(240004) });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    expect(outline(returned.document)).toEqual([...arranged]);
    expect(outline(returned.document).map((entry) => entry.rowId)).toEqual([parent.id, childClip.id, ordinary.id, untouched.id]);
    expect(returned.document.stash?.flatMap((bundle) => bundle.rows).every((row) => row.stashOrigin === undefined)).toBe(true);
    const reloaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(returned.document));
    expect(reloaded.ok).toBe(true);
    if (reloaded.ok) expect(reloaded.document.stashOutline).toEqual(returned.document.stashOutline);
  });

  it("returns a child at top level while its parent stays active, and never reparents it later", () => {
    const parent = narration(300000);
    const child = clip(310000);
    let document = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(320000), row: parent,
      sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 1, {
      kind: "create_stash_clip", bundleId: id(320001), row: child,
      sectionId: null, parentRowId: parent.id, afterRowId: null,
    }).document;
    const placed = applyRowEditV2(document, 2, { kind: "place_stash_rows", rowIds: [parent.id], destination: gap(null, null, null) });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const session = createRowEditSessionV2(placed.document);
    const childReturned = session.apply({ kind: "stash_rows", rowIds: [child.id], bundleId: id(320002) });
    expect(childReturned.ok, JSON.stringify(childReturned.diagnostics)).toBe(true);
    expect(childReturned.document.activeDraft.blocks.map((block) => block.id)).toEqual([parent.id]);
    expect((childReturned.document.activeDraft.blocks[0] as NarrationBlockV2).stashOrigin?.beforeSiblingRowId).toBe(child.id);
    expect(outline(childReturned.document)).toEqual([{ rowId: child.id, kind: "clip", parentRowId: null, sectionId: null }]);
    const undoneChildReturn = session.undo();
    expect(undoneChildReturn.ok).toBe(true);
    expect(undoneChildReturn.document.activeDraft.blocks.map((block) => block.id)).toEqual([parent.id, child.id]);
    expect((undoneChildReturn.document.activeDraft.blocks[0] as NarrationBlockV2).stashOrigin?.beforeSiblingRowId).toBeNull();
    expect(outline(undoneChildReturn.document)).toEqual(outline(placed.document));

    const parentReturned = applyRowEditV2(childReturned.document, 4, { kind: "stash_rows", rowIds: [parent.id], bundleId: id(320003) });
    expect(parentReturned.ok, JSON.stringify(parentReturned.diagnostics)).toBe(true);
    expect(outline(parentReturned.document)).toEqual([
      { rowId: parent.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: child.id, kind: "clip", parentRowId: null, sectionId: null },
    ]);
  });

  it("returns an active parent's child to its anchored root gap when Stash has other roots", () => {
    const before = narration(360000);
    const parent = narration(370000);
    const child = clip(380000);
    const after = narration(390000);
    let document = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(400000), row: before,
      sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 1, {
      kind: "create_stash_note", bundleId: id(400001), row: parent,
      sectionId: null, parentRowId: null, afterRowId: before.id,
    }).document;
    document = applyRowEditV2(document, 2, {
      kind: "create_stash_clip", bundleId: id(400002), row: child,
      sectionId: null, parentRowId: parent.id, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 3, {
      kind: "create_stash_note", bundleId: id(400003), row: after,
      sectionId: null, parentRowId: null, afterRowId: parent.id,
    }).document;
    const placed = applyRowEditV2(document, 4, {
      kind: "place_stash_rows", rowIds: [parent.id], destination: gap(null, null, null),
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const childReturned = applyRowEditV2(placed.document, 5, {
      kind: "stash_rows", rowIds: [child.id], bundleId: id(400004),
    });
    expect(childReturned.ok, JSON.stringify(childReturned.diagnostics)).toBe(true);
    expect(outline(childReturned.document).map((entry) => entry.rowId)).toEqual([before.id, child.id, after.id]);
    expect(childReturned.document.activeDraft.blocks.map((block) => block.id)).toEqual([parent.id]);
    const parentReturned = applyRowEditV2(childReturned.document, 6, {
      kind: "stash_rows", rowIds: [parent.id], bundleId: id(400005),
    });
    expect(parentReturned.ok, JSON.stringify(parentReturned.diagnostics)).toBe(true);
    expect(outline(parentReturned.document).map((entry) => entry.rowId)).toEqual([before.id, parent.id, child.id, after.id]);
  });

  it("returns children into an empty outline and preserves their parent gap when the parent returns later", () => {
    const before = narration(410000);
    const parent = narration(420000);
    const child = clip(430000);
    let document = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(440000), row: before,
      sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 1, {
      kind: "create_stash_note", bundleId: id(440001), row: parent,
      sectionId: null, parentRowId: null, afterRowId: before.id,
    }).document;
    document = applyRowEditV2(document, 2, {
      kind: "create_stash_clip", bundleId: id(440002), row: child,
      sectionId: null, parentRowId: parent.id, afterRowId: null,
    }).document;
    const placed = applyRowEditV2(document, 3, {
      kind: "place_stash_rows", rowIds: [before.id, parent.id], destination: gap(null, null, null),
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    expect(outline(placed.document)).toEqual([]);
    const childReturned = applyRowEditV2(placed.document, 4, {
      kind: "stash_rows", rowIds: [child.id], bundleId: id(440003),
    });
    expect(childReturned.ok, JSON.stringify(childReturned.diagnostics)).toBe(true);
    expect(outline(childReturned.document).map((entry) => entry.rowId)).toEqual([child.id]);
    const parentReturned = applyRowEditV2(childReturned.document, 5, {
      kind: "stash_rows", rowIds: [before.id, parent.id], bundleId: id(440004),
    });
    expect(parentReturned.ok, JSON.stringify(parentReturned.diagnostics)).toBe(true);
    expect(outline(parentReturned.document).map((entry) => entry.rowId)).toEqual([before.id, parent.id, child.id]);
  });

  it("returns one child at the active parent's source gap before its active sibling", () => {
    const before = narration(450000);
    const parent = narration(460000);
    const firstChild = clip(470000);
    const secondChild = clip(480000);
    let document = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(490000), row: before,
      sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 1, {
      kind: "create_stash_note", bundleId: id(490001), row: parent,
      sectionId: null, parentRowId: null, afterRowId: before.id,
    }).document;
    document = applyRowEditV2(document, 2, {
      kind: "create_stash_clip", bundleId: id(490002), row: firstChild,
      sectionId: null, parentRowId: parent.id, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 3, {
      kind: "create_stash_clip", bundleId: id(490003), row: secondChild,
      sectionId: null, parentRowId: parent.id, afterRowId: firstChild.id,
    }).document;
    document = applyRowEditV2(document, 4, {
      kind: "create_stash_note", bundleId: id(490004), row: narration(495000),
      sectionId: null, parentRowId: null, afterRowId: parent.id,
    }).document;
    const placed = applyRowEditV2(document, 5, {
      kind: "place_stash_rows", rowIds: [parent.id], destination: gap(null, null, null),
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const firstReturned = applyRowEditV2(placed.document, 6, {
      kind: "stash_rows", rowIds: [firstChild.id], bundleId: id(490005),
    });
    expect(firstReturned.ok, JSON.stringify(firstReturned.diagnostics)).toBe(true);
    expect(outline(firstReturned.document).map((entry) => entry.rowId)).toEqual([before.id, firstChild.id, id(495000)]);
    expect(firstReturned.document.activeDraft.blocks.map((block) => block.id)).toEqual([parent.id, secondChild.id]);
    const secondReturned = applyRowEditV2(firstReturned.document, 7, {
      kind: "stash_rows", rowIds: [secondChild.id], bundleId: id(490006),
    });
    expect(secondReturned.ok, JSON.stringify(secondReturned.diagnostics)).toBe(true);
    expect(outline(secondReturned.document).map((entry) => entry.rowId)).toEqual([before.id, firstChild.id, secondChild.id, id(495000)]);
    const parentReturned = applyRowEditV2(secondReturned.document, 8, {
      kind: "stash_rows", rowIds: [parent.id], bundleId: id(490007),
    });
    expect(parentReturned.ok, JSON.stringify(parentReturned.diagnostics)).toBe(true);
    expect(outline(parentReturned.document).map((entry) => entry.rowId)).toEqual([before.id, parent.id, firstChild.id, secondChild.id, id(495000)]);
  });

  for (const reverseActiveOrder of [false, true]) {
    it(`returns a selected child batch at its active parent's root gap${reverseActiveOrder ? " despite reversed active order" : ""}`, () => {
      const firstId = reverseActiveOrder ? 510000 : 500000;
      const before = narration(firstId);
      const parent = narration(firstId + 1);
      const firstChild = clip(firstId + 2);
      const secondChild = clip(firstId + 3);
      let document = applyRowEditV2(documentWith(), 0, {
        kind: "create_stash_note", bundleId: id(firstId + 10), row: before,
        sectionId: null, parentRowId: null, afterRowId: null,
      }).document;
      document = applyRowEditV2(document, 1, {
        kind: "create_stash_note", bundleId: id(firstId + 11), row: parent,
        sectionId: null, parentRowId: null, afterRowId: before.id,
      }).document;
      document = applyRowEditV2(document, 2, {
        kind: "create_stash_clip", bundleId: id(firstId + 12), row: firstChild,
        sectionId: null, parentRowId: parent.id, afterRowId: null,
      }).document;
      document = applyRowEditV2(document, 3, {
        kind: "create_stash_clip", bundleId: id(firstId + 13), row: secondChild,
        sectionId: null, parentRowId: parent.id, afterRowId: firstChild.id,
      }).document;
      const placed = applyRowEditV2(document, 4, {
        kind: "place_stash_rows", rowIds: [parent.id], destination: gap(null, null, null),
      });
      expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
      let active = placed.document;
      if (reverseActiveOrder) {
        const reordered = applyRowEditV2(active, 5, {
          kind: "move_rows", rowIds: [secondChild.id], destination: gap(null, parent.id, firstChild.id),
        });
        expect(reordered.ok, JSON.stringify(reordered.diagnostics)).toBe(true);
        active = reordered.document;
      }
      const childBatch = reverseActiveOrder ? [secondChild.id, firstChild.id] : [firstChild.id, secondChild.id];
      const returned = applyRowEditV2(active, reverseActiveOrder ? 6 : 5, {
        kind: "stash_rows", rowIds: childBatch, bundleId: id(firstId + 14),
      });
      expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
      expect(outline(returned.document).map((entry) => entry.rowId)).toEqual([before.id, firstChild.id, secondChild.id]);
      expect(returned.document.activeDraft.blocks.map((block) => block.id)).toEqual([parent.id]);
      const parentReturned = applyRowEditV2(returned.document, reverseActiveOrder ? 7 : 6, {
        kind: "stash_rows", rowIds: [parent.id], bundleId: id(firstId + 15),
      });
      expect(parentReturned.ok, JSON.stringify(parentReturned.diagnostics)).toBe(true);
      expect(outline(parentReturned.document).map((entry) => entry.rowId)).toEqual([before.id, parent.id, firstChild.id, secondChild.id]);
    });
  }

  it("keeps multiple independently returned children in source order before returning their parent", () => {
    const parent = narration(900000);
    const firstChild = clip(910000);
    const secondChild = clip(920000);
    let document = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(930000), row: parent,
      sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 1, {
      kind: "create_stash_clip", bundleId: id(930001), row: firstChild,
      sectionId: null, parentRowId: parent.id, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 2, {
      kind: "create_stash_clip", bundleId: id(930002), row: secondChild,
      sectionId: null, parentRowId: parent.id, afterRowId: firstChild.id,
    }).document;
    const placed = applyRowEditV2(document, 3, {
      kind: "place_stash_rows", rowIds: [parent.id], destination: gap(null, null, null),
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const secondReturned = applyRowEditV2(placed.document, 4, {
      kind: "stash_rows", rowIds: [secondChild.id], bundleId: id(930003),
    });
    expect(secondReturned.ok, JSON.stringify(secondReturned.diagnostics)).toBe(true);
    const firstReturned = applyRowEditV2(secondReturned.document, 5, {
      kind: "stash_rows", rowIds: [firstChild.id], bundleId: id(930004),
    });
    expect(firstReturned.ok, JSON.stringify(firstReturned.diagnostics)).toBe(true);
    expect(firstReturned.document.activeDraft.blocks.map((block) => block.id)).toEqual([parent.id]);
    expect((firstReturned.document.activeDraft.blocks[0] as NarrationBlockV2).stashOrigin?.beforeSiblingRowId).toBe(firstChild.id);
    expect(outline(firstReturned.document).map((entry) => entry.rowId)).toEqual([firstChild.id, secondChild.id]);
    const parentReturned = applyRowEditV2(firstReturned.document, 6, {
      kind: "stash_rows", rowIds: [parent.id], bundleId: id(930005),
    });
    expect(parentReturned.ok, JSON.stringify(parentReturned.diagnostics)).toBe(true);
    expect(outline(parentReturned.document).map((entry) => entry.rowId)).toEqual([parent.id, firstChild.id, secondChild.id]);
    expect(outline(parentReturned.document).map((entry) => entry.parentRowId)).toEqual([null, null, null]);
  });

  it("returns a child to its original nested slot when its parent is already in Stash", () => {
    const parent = narration(330000);
    const first = clip(340000);
    const second = clip(350000);
    let document = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(360000), row: parent,
      sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 1, {
      kind: "create_stash_clip", bundleId: id(360001), row: first,
      sectionId: null, parentRowId: parent.id, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 2, {
      kind: "create_stash_clip", bundleId: id(360002), row: second,
      sectionId: null, parentRowId: parent.id, afterRowId: first.id,
    }).document;
    const placed = applyRowEditV2(document, 3, { kind: "place_stash_rows", rowIds: [first.id], destination: gap(null, null, null) });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    expect(outline(placed.document)).toEqual([
      { rowId: parent.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: second.id, kind: "clip", parentRowId: parent.id, sectionId: null },
    ]);
    const returned = applyRowEditV2(placed.document, 4, { kind: "stash_rows", rowIds: [first.id], bundleId: id(360003) });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    expect(outline(returned.document)).toEqual([
      { rowId: parent.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: first.id, kind: "clip", parentRowId: parent.id, sectionId: null },
      { rowId: second.id, kind: "clip", parentRowId: parent.id, sectionId: null },
    ]);
  });

  it("clears eligibility for authored changes, restores it only through exact Undo, and never infers it from matching text", () => {
    const source = narration(370000);
    const created = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(380000), row: source,
      sectionId: null, parentRowId: null, afterRowId: null,
    });
    const placed = applyRowEditV2(created.document, 1, { kind: "place_stash_rows", rowIds: [source.id], destination: gap(null, null, null) });
    expect(placed.ok).toBe(true);
    const before = placed.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(before.stashOrigin?.returnEligible).toBe(true);

    const spoken = applyStageDirectionEditV2(placed.document, before.version, {
      kind: "make_spoken", blockId: before.id, startOffset: 1, endOffset: before.text.length - 1,
    });
    expect(spoken.ok, JSON.stringify(spoken.diagnostics)).toBe(true);
    const afterEdit = spoken.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(afterEdit.stashOrigin?.returnEligible).toBe(false);
    const undo = undoStageDirectionEditV2(spoken.document, spoken.undo!);
    expect(undo.ok, JSON.stringify(undo.diagnostics)).toBe(true);
    expect((undo.document.activeDraft.blocks[0] as NarrationBlockV2).stashOrigin?.returnEligible).toBe(true);

    const rewrittenFromOriginal = undo.document.activeDraft.blocks[0] as NarrationBlockV2;
    const opened = applyStageDirectionEditV2(undo.document, rewrittenFromOriginal.version, {
      kind: "make_spoken", blockId: rewrittenFromOriginal.id, startOffset: 1, endOffset: rewrittenFromOriginal.text.length - 1,
    });
    expect(opened.ok).toBe(true);
    const rewrapped = applyStageDirectionEditV2(opened.document, (opened.document.activeDraft.blocks[0] as NarrationBlockV2).version, {
      kind: "make_stage_direction", blockId: source.id, startOffset: 0, endOffset: source.text.length,
    });
    expect(rewrapped.ok).toBe(true);
    const manuallyRestored = rewrapped.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(manuallyRestored.text).toBe(before.text);
    expect(manuallyRestored.stashOrigin?.returnEligible).toBe(false);
    const returned = applyRowEditV2(rewrapped.document, rewrapped.document.rowEditRevision ?? 0, { kind: "stash_rows", rowIds: [source.id], bundleId: id(380001) });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    expect(outline(returned.document)).toEqual([{ rowId: source.id, kind: "row", parentRowId: null, sectionId: null }]);
    expect(returned.document.stash?.flatMap((bundle) => bundle.rows)[0]?.stashOrigin).toBeUndefined();
  });

  it("preserves the current origin against forged whole-row replacement without reclassifying compact notes", () => {
    const source = narration(390000);
    const created = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(400000), row: source,
      sectionId: null, parentRowId: null, afterRowId: null,
    });
    const reclassified = applyRowEditV2(created.document, 1, {
      kind: "set_stash_outline",
      entries: [{ ...outline(created.document)[0]!, kind: "row" }],
    });
    expect(reclassified.diagnostics[0]?.code).toBe("STASH_OUTLINE_KIND_IMMUTABLE");
    expect(reclassified.document).toBe(created.document);
    const doc = created.document;
    const stored = doc.stash![0]!.rows[0] as NarrationBlockV2;
    stored.stashOrigin = { kind: "note", parentRowId: null, sectionId: null, afterSiblingRowId: null, beforeSiblingRowId: null, returnEligible: true };
    const replacement = structuredClone(stored);
    replacement.notes = ["Edited saved source."];
    replacement.stashOrigin = { kind: "clip", parentRowId: id(499999), sectionId: null, afterSiblingRowId: id(499997), beforeSiblingRowId: id(499998), returnEligible: true };
    const edited = applyStashRowEditV2(doc, 1, { bundleId: id(400000), rowId: source.id, row: replacement });
    expect(edited.ok, JSON.stringify(edited.diagnostics)).toBe(true);
    expect(edited.document.stash?.[0]?.rows[0]?.stashOrigin).toEqual({ kind: "note", parentRowId: null, sectionId: null, afterSiblingRowId: null, beforeSiblingRowId: null, returnEligible: false });
    expect(outline(edited.document)[0]?.kind).toBe("note");
  });

  it("keeps compact parent notes and children intact across saved-row and direction edits", () => {
    const replacementParent = narration(500000);
    const replacementChild = clip(510000);
    let replacementDoc = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(520000), row: replacementParent,
      sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    replacementDoc = applyRowEditV2(replacementDoc, 1, {
      kind: "create_stash_clip", bundleId: id(520001), row: replacementChild,
      sectionId: null, parentRowId: replacementParent.id, afterRowId: null,
    }).document;
    const savedParent = structuredClone(replacementDoc.stash![0]!.rows[0] as NarrationBlockV2);
    savedParent.notes = ["Edited compact note source."];
    const savedEdit = applyStashRowEditV2(replacementDoc, 2, {
      bundleId: id(520000), rowId: replacementParent.id, row: savedParent,
    });
    expect(savedEdit.ok, JSON.stringify(savedEdit.diagnostics)).toBe(true);
    expect(outline(savedEdit.document)).toEqual([
      { rowId: replacementParent.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: replacementChild.id, kind: "clip", parentRowId: replacementParent.id, sectionId: null },
    ]);

    const directionParent = narration(530000);
    const directionChild = clip(540000);
    let directionDoc = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(550000), row: directionParent,
      sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    directionDoc = applyRowEditV2(directionDoc, 1, {
      kind: "create_stash_clip", bundleId: id(550001), row: directionChild,
      sectionId: null, parentRowId: directionParent.id, afterRowId: null,
    }).document;
    const before = structuredClone(directionDoc.stash![0]!.rows[0] as NarrationBlockV2);
    const spoken = applyStageDirectionEditV2(directionDoc, before.version, {
      kind: "make_spoken", blockId: before.id, startOffset: 1, endOffset: before.text.length - 1,
    });
    expect(spoken.ok, JSON.stringify(spoken.diagnostics)).toBe(true);
    expect(outline(spoken.document)[0]?.kind).toBe("note");
    expect(outline(spoken.document)[1]?.parentRowId).toBe(directionParent.id);
    const undo = undoStageDirectionEditV2(spoken.document, spoken.undo!);
    expect(undo.ok, JSON.stringify(undo.diagnostics)).toBe(true);
    expect(outline(undo.document)[0]?.kind).toBe("note");
    expect((undo.document.stash![0]!.rows[0] as NarrationBlockV2).text).toBe(before.text);
    expect(outline(undo.document)[1]?.parentRowId).toBe(directionParent.id);
  });

  it("keeps whole-bundle restore in saved-row order after canonical outline upgrade", () => {
    const sectioned = narration(560000);
    const unsectioned = narration(570000);
    const document = documentWith();
    document.stash = [{ id: id(580000), rows: [sectioned, unsectioned], supportingItems: [] }];
    document.stashSections = [{ id: id(580001), title: "Research", rowIds: [sectioned.id] }];
    const restored = applyRowEditV2(document, 0, {
      kind: "restore_stash", bundleId: id(580000), destination: gap(null, null, null),
    });
    expect(restored.ok, JSON.stringify(restored.diagnostics)).toBe(true);
    expect(restored.document.activeDraft.blocks.map((row) => row.id)).toEqual([sectioned.id, unsectioned.id]);
  });

  it("refuses incomplete sibling returns atomically but resolves the complete return batch", () => {
    const first = narration(590000);
    const second = narration(600000);
    let document = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(610000), row: first,
      sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 1, {
      kind: "create_stash_note", bundleId: id(610001), row: second,
      sectionId: null, parentRowId: null, afterRowId: first.id,
    }).document;
    const placed = applyRowEditV2(document, 2, {
      kind: "place_stash_rows", rowIds: [first.id, second.id], destination: gap(null, null, null),
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const outOfRange = applyRowEditV2(placed.document, 3, {
      kind: "stash_rows", rowIds: [second.id], bundleId: id(610002),
    });
    expect(outOfRange.diagnostics[0]?.code).toBe("STASH_ORIGIN_DESTINATION_INVALID");
    expect(outOfRange.document).toBe(placed.document);
    const returnedFirst = applyRowEditV2(placed.document, 3, {
      kind: "stash_rows", rowIds: [first.id], bundleId: id(610003),
    });
    expect(returnedFirst.diagnostics[0]?.code).toBe("STASH_ORIGIN_DESTINATION_INVALID");
    expect(returnedFirst.document).toBe(placed.document);
    const returnedBoth = applyRowEditV2(placed.document, 3, {
      kind: "stash_rows", rowIds: [first.id, second.id], bundleId: id(610004),
    });
    expect(returnedBoth.ok, JSON.stringify(returnedBoth.diagnostics)).toBe(true);
    expect(outline(returnedBoth.document).map((entry) => entry.rowId)).toEqual([first.id, second.id]);
  });

  it("returns a placed last sibling after its stable right neighbor despite a new row before the original outline", () => {
    const first = narration(610000);
    const middle = narration(620000);
    const last = narration(630000);
    const inserted = narration(640000);
    let document = documentWith();
    for (const [index, row] of [first, middle, last].entries()) {
      document = applyRowEditV2(document, index, {
        kind: "create_stash_note", bundleId: id(650000 + index), row,
        sectionId: null, parentRowId: null, afterRowId: index === 0 ? null : [first, middle][index - 1]!.id,
      }).document;
    }
    const placed = applyRowEditV2(document, 3, {
      kind: "place_stash_rows", rowIds: [last.id], destination: gap(null, null, null),
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    let withNew = applyRowEditV2(placed.document, 4, {
      kind: "create_stash_note", bundleId: id(650010), row: inserted,
      sectionId: null, parentRowId: null, afterRowId: middle.id,
    });
    expect(withNew.ok, JSON.stringify(withNew.diagnostics)).toBe(true);
    withNew = applyRowEditV2(withNew.document, 5, {
      kind: "set_stash_outline",
      entries: [
        { rowId: inserted.id, kind: "note", parentRowId: null, sectionId: null },
        { rowId: first.id, kind: "note", parentRowId: null, sectionId: null },
        { rowId: middle.id, kind: "note", parentRowId: null, sectionId: null },
      ],
    });
    expect(withNew.ok, JSON.stringify(withNew.diagnostics)).toBe(true);
    const returned = applyRowEditV2(withNew.document, 6, {
      kind: "stash_rows", rowIds: [last.id], bundleId: id(650011),
    });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    expect(outline(returned.document).map((entry) => entry.rowId)).toEqual([inserted.id, first.id, middle.id, last.id]);
  });

  it("returns C after B when C and then A are placed separately", () => {
    const first = narration(660000);
    const middle = narration(670000);
    const last = narration(680000);
    let document = documentWith();
    for (const [index, row] of [first, middle, last].entries()) {
      document = applyRowEditV2(document, index, {
        kind: "create_stash_note", bundleId: id(690000 + index), row,
        sectionId: null, parentRowId: null, afterRowId: index === 0 ? null : [first, middle][index - 1]!.id,
      }).document;
    }
    const placedLast = applyRowEditV2(document, 3, {
      kind: "place_stash_rows", rowIds: [last.id], destination: gap(null, null, null),
    });
    expect(placedLast.ok, JSON.stringify(placedLast.diagnostics)).toBe(true);
    const placedFirst = applyRowEditV2(placedLast.document, 4, {
      kind: "place_stash_rows", rowIds: [first.id], destination: gap(null, null, last.id),
    });
    expect(placedFirst.ok, JSON.stringify(placedFirst.diagnostics)).toBe(true);
    const returnedLast = applyRowEditV2(placedFirst.document, 5, {
      kind: "stash_rows", rowIds: [last.id], bundleId: id(690010),
    });
    expect(returnedLast.ok, JSON.stringify(returnedLast.diagnostics)).toBe(true);
    expect(outline(returnedLast.document).map((entry) => entry.rowId)).toEqual([middle.id, last.id]);
    const returnedFirst = applyRowEditV2(returnedLast.document, 6, {
      kind: "stash_rows", rowIds: [first.id], bundleId: id(690011),
    });
    expect(returnedFirst.ok, JSON.stringify(returnedFirst.diagnostics)).toBe(true);
    expect(outline(returnedFirst.document).map((entry) => entry.rowId)).toEqual([first.id, middle.id, last.id]);
  });

  it("refuses two rows claiming the same sibling gap instead of choosing an arbitrary order", () => {
    const first = narration(800000);
    const second = narration(810000);
    const returningA = narration(820000);
    const returningB = narration(830000);
    let document = documentWith([returningA, returningB]);
    document = applyRowEditV2(document, 0, {
      kind: "create_stash_note", bundleId: id(840000), row: first,
      sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 1, {
      kind: "create_stash_note", bundleId: id(840001), row: second,
      sectionId: null, parentRowId: null, afterRowId: first.id,
    }).document;
    for (const row of document.activeDraft.blocks) {
      if (row.type === "section") throw new Error("unexpected section in active rows");
      row.stashOrigin = {
        kind: "note", parentRowId: null, sectionId: null,
        afterSiblingRowId: first.id, beforeSiblingRowId: second.id, returnEligible: true,
      };
    }
    const refused = applyRowEditV2(document, 2, {
      kind: "stash_rows", rowIds: [returningA.id, returningB.id], bundleId: id(840002),
    });
    expect(refused.diagnostics[0]?.code).toBe("STASH_ORIGIN_DESTINATION_INVALID");
    expect(refused.document).toBe(document);
    expect(outline(refused.document).map((entry) => entry.rowId)).toEqual([first.id, second.id]);
  });

  it("refuses to guess a new parent section and succeeds after restoring the original context", () => {
    const sectionId = id(620000);
    const parent = narration(630000);
    const child = clip(640000);
    let document = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_section", sectionId, title: "Research",
    }).document;
    document = applyRowEditV2(document, 1, {
      kind: "create_stash_note", bundleId: id(650000), row: parent,
      sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 2, {
      kind: "create_stash_clip", bundleId: id(650001), row: child,
      sectionId: null, parentRowId: parent.id, afterRowId: null,
    }).document;
    const placedChild = applyRowEditV2(document, 3, {
      kind: "place_stash_rows", rowIds: [child.id], destination: gap(null, null, null),
    });
    expect(placedChild.ok, JSON.stringify(placedChild.diagnostics)).toBe(true);
    const movedParent = applyRowEditV2(placedChild.document, 4, {
      kind: "move_stash_rows", rowIds: [parent.id], sectionId,
    });
    expect(movedParent.ok, JSON.stringify(movedParent.diagnostics)).toBe(true);
    const refused = applyRowEditV2(movedParent.document, 5, {
      kind: "stash_rows", rowIds: [child.id], bundleId: id(650002),
    });
    expect(refused.diagnostics[0]?.code).toBe("STASH_ORIGIN_DESTINATION_INVALID");
    expect(refused.document).toBe(movedParent.document);
    const restoredParent = applyRowEditV2(movedParent.document, 5, {
      kind: "move_stash_rows", rowIds: [parent.id], sectionId: null,
    });
    expect(restoredParent.ok, JSON.stringify(restoredParent.diagnostics)).toBe(true);
    const returnedChild = applyRowEditV2(restoredParent.document, 6, {
      kind: "stash_rows", rowIds: [child.id], bundleId: id(650003),
    });
    expect(returnedChild.ok, JSON.stringify(returnedChild.diagnostics)).toBe(true);
    expect(outline(returnedChild.document)).toEqual([
      { rowId: parent.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: child.id, kind: "clip", parentRowId: parent.id, sectionId: null },
    ]);
  });

  it("moves selected rows to the end of the target section without disturbing other outline rows", () => {
    const sectionId = id(660000);
    const unsectionedA = narration(670000);
    const unsectionedB = narration(680000);
    const existing = narration(690000);
    let document = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_section", sectionId, title: "Research",
    }).document;
    document = applyRowEditV2(document, 1, {
      kind: "create_stash_note", bundleId: id(700000), row: unsectionedA,
      sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 2, {
      kind: "create_stash_note", bundleId: id(700001), row: unsectionedB,
      sectionId: null, parentRowId: null, afterRowId: unsectionedA.id,
    }).document;
    document = applyRowEditV2(document, 3, {
      kind: "create_stash_note", bundleId: id(700002), row: existing,
      sectionId, parentRowId: null, afterRowId: null,
    }).document;
    const moved = applyRowEditV2(document, 4, {
      kind: "move_stash_rows", rowIds: [unsectionedB.id], sectionId,
    });
    expect(moved.ok, JSON.stringify(moved.diagnostics)).toBe(true);
    expect(outline(moved.document)).toEqual([
      { rowId: unsectionedA.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: existing.id, kind: "note", parentRowId: null, sectionId },
      { rowId: unsectionedB.id, kind: "note", parentRowId: null, sectionId },
    ]);
    expect(moved.document.stashSections).toEqual([{ id: sectionId, title: "Research", rowIds: [] }]);
  });

  it("leaves already-targeted roots and their children in place when moving another root", () => {
    const sectionId = id(760100);
    const existing = narration(760200);
    const child = clip(760300);
    const other = narration(760400);
    let document = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_section", sectionId, title: "Research",
    }).document;
    document = applyRowEditV2(document, 1, {
      kind: "create_stash_note", bundleId: id(760500), row: existing,
      sectionId, parentRowId: null, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 2, {
      kind: "create_stash_clip", bundleId: id(760600), row: child,
      sectionId, parentRowId: existing.id, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 3, {
      kind: "create_stash_note", bundleId: id(760700), row: other,
      sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    const moved = applyRowEditV2(document, 4, {
      kind: "move_stash_rows", rowIds: [existing.id, other.id], sectionId,
    });
    expect(moved.ok, JSON.stringify(moved.diagnostics)).toBe(true);
    expect(outline(moved.document)).toEqual([
      { rowId: existing.id, kind: "note", parentRowId: null, sectionId },
      { rowId: child.id, kind: "clip", parentRowId: existing.id, sectionId },
      { rowId: other.id, kind: "note", parentRowId: null, sectionId },
    ]);
  });

  it("refuses to split a nested branch across Stash sections and preserves kinds on a complete move", () => {
    const sectionId = id(750000);
    const parent = narration(760000);
    const child = clip(770000);
    let document = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_section", sectionId, title: "Research",
    }).document;
    document = applyRowEditV2(document, 1, {
      kind: "create_stash_note", bundleId: id(780000), row: parent,
      sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    document = applyRowEditV2(document, 2, {
      kind: "create_stash_clip", bundleId: id(780001), row: child,
      sectionId: null, parentRowId: parent.id, afterRowId: null,
    }).document;
    const partial = applyRowEditV2(document, 3, {
      kind: "move_stash_rows", rowIds: [parent.id], sectionId,
    });
    expect(partial.ok).toBe(false);
    expect(partial.document).toBe(document);
    const complete = applyRowEditV2(document, 3, {
      kind: "move_stash_rows", rowIds: [parent.id, child.id], sectionId,
    });
    expect(complete.ok, JSON.stringify(complete.diagnostics)).toBe(true);
    expect(outline(complete.document)).toEqual([
      { rowId: parent.id, kind: "note", parentRowId: null, sectionId },
      { rowId: child.id, kind: "clip", parentRowId: parent.id, sectionId },
    ]);
  });

  it("refuses malformed compact row payloads atomically", () => {
    const document = documentWith();
    const malformedNote = JSON.parse(JSON.stringify({
      type: "narration", id: id(710000), orderKey: "missing-tokens", text: "Incomplete row",
    })) as NarrationBlockV2;
    const noteResult = applyRowEditV2(document, 0, {
      kind: "create_stash_note", bundleId: id(720000), row: malformedNote,
      sectionId: null, parentRowId: null, afterRowId: null,
    });
    expect(noteResult.diagnostics[0]?.code).toBe("STASH_NOTE_CONTENT_INVALID");
    expect(noteResult.document).toBe(document);
    const malformedClip = JSON.parse(JSON.stringify({
      type: "visual_only", id: id(730000), orderKey: "missing-payload", visualOnlyTiming: { kind: "visual_only" }, version: 1,
    })) as VisualOnlyBlockV2;
    const clipResult = applyRowEditV2(document, 0, {
      kind: "create_stash_clip", bundleId: id(740000), row: malformedClip,
      sectionId: null, parentRowId: null, afterRowId: null,
    });
    expect(clipResult.diagnostics[0]?.code).toBe("STASH_CLIP_CONTENT_INVALID");
    expect(clipResult.document).toBe(document);
  });

  it("clears eligibility when an active converted row receives a visual edit", () => {
    const source = narration(405000);
    const created = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(450000), row: source,
      sectionId: null, parentRowId: null, afterRowId: null, mode: "authored",
    });
    expect(created.ok, JSON.stringify(created.diagnostics)).toBe(true);
    const placed = applyRowEditV2(created.document, 1, { kind: "place_stash_rows", rowIds: [source.id], destination: gap(null, null, null) });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const row = placed.document.activeDraft.blocks[0] as NarrationBlockV2;
    const token = row.tokens[0];
    const visualEdit = applyVisualSequenceEditV2(placed.document, row.primaryVisualSequence!.version, {
      kind: "insert_sequential",
      blockId: row.id,
      boundary: { blockId: row.id, tokenId: token.id, affinity: "after", quotedWord: token.value, anchorVersion: row.version },
      slotId: id(450001),
      undefinedPayloadId: id(450002),
    });
    expect(visualEdit.ok, JSON.stringify(visualEdit.diagnostics)).toBe(true);
    expect((visualEdit.document.activeDraft.blocks[0] as NarrationBlockV2).stashOrigin?.returnEligible).toBe(false);
  });

  it("refuses missing or ambiguous source slots atomically and replays only allowed Sorting operations", () => {
    const parent = narration(410000);
    const created = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(420000), row: parent,
      sectionId: null, parentRowId: null, afterRowId: null,
    });
    const placed = applyRowEditV2(created.document, 1, { kind: "place_stash_rows", rowIds: [parent.id], destination: gap(null, null, null) });
    expect(placed.ok).toBe(true);
    const missing = structuredClone(placed.document);
    (missing.activeDraft.blocks[0] as NarrationBlockV2).stashOrigin!.parentRowId = id(499998);
    const refused = applyRowEditV2(missing, 2, { kind: "stash_rows", rowIds: [parent.id], bundleId: id(420001) });
    expect(refused.diagnostics[0]?.code).toBe("STASH_ORIGIN_DESTINATION_INVALID");
    expect(refused.document).toBe(missing);

    const sectionId = id(430000);
    let sectioned = applyRowEditV2(documentWith(), 0, { kind: "create_stash_section", sectionId, title: "Research" }).document;
    const first = narration(440000);
    const second = narration(450000);
    sectioned = applyRowEditV2(sectioned, 1, {
      kind: "create_stash_note", bundleId: id(460000), row: first,
      sectionId, parentRowId: null, afterRowId: null,
    }).document;
    sectioned = applyRowEditV2(sectioned, 2, {
      kind: "create_stash_note", bundleId: id(460001), row: second,
      sectionId, parentRowId: null, afterRowId: first.id,
    }).document;
    const moved = applyRowEditV2(sectioned, 3, { kind: "place_stash_rows", rowIds: [second.id], destination: gap(null, null, null) });
    expect(moved.ok).toBe(true);
    const missingSibling = structuredClone(moved.document);
    missingSibling.stash = missingSibling.stash!.filter((bundle) => !bundle.rows.some((row) => row.id === first.id));
    missingSibling.stashOutline = missingSibling.stashOutline!.filter((entry) => entry.rowId !== first.id);
    const ambiguous = applyRowEditV2(missingSibling, 4, { kind: "stash_rows", rowIds: [second.id], bundleId: id(460002) });
    expect(ambiguous.diagnostics[0]?.code).toBe("STASH_ORIGIN_DESTINATION_INVALID");
    expect(ambiguous.document).toBe(missingSibling);

    const trial = createSortingTrialV2(sectioned);
    expect(trial.apply({
      kind: "set_stash_outline",
      entries: [...outline(sectioned)].reverse(),
    }).ok).toBe(true);
    expect(trial.apply({ kind: "create_stash_note", bundleId: id(470000), row: narration(470100), sectionId: null, parentRowId: null, afterRowId: null }).diagnostics[0]?.code).toBe("SORTING_CONTENT_READ_ONLY");
    const selectedRoot = trial.document.stashOutline![0]!.rowId;
    expect(trial.apply({ kind: "place_stash_rows", rowIds: [selectedRoot], destination: gap(null, null, null) }).ok).toBe(true);
    const resumed = resumeSortingTrialV2(trial.serialize());
    expect(resumed.document.stashOutline).toEqual(trial.document.stashOutline);
    expect(resumed.document.activeDraft.blocks.map((block) => block.id)).toEqual([selectedRoot]);
  });
});
