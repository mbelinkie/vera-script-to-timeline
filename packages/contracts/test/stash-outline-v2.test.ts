import { describe, expect, it } from "vitest";

import {
  applyRowEditV2,
  applyStageDirectionEditV2,
  applyStashRowEditV2,
  applyVisualSequenceEditV2,
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
    const first = authored.tokens[0]!;
    const second = authored.tokens[1]!;
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
    const childReturned = applyRowEditV2(placed.document, 3, { kind: "stash_rows", rowIds: [child.id], bundleId: id(320002) });
    expect(childReturned.ok, JSON.stringify(childReturned.diagnostics)).toBe(true);
    expect(childReturned.document.activeDraft.blocks.map((block) => block.id)).toEqual([parent.id]);
    expect(outline(childReturned.document)).toEqual([{ rowId: child.id, kind: "clip", parentRowId: null, sectionId: null }]);

    const parentReturned = applyRowEditV2(childReturned.document, 4, { kind: "stash_rows", rowIds: [parent.id], bundleId: id(320003) });
    expect(parentReturned.ok, JSON.stringify(parentReturned.diagnostics)).toBe(true);
    expect(outline(parentReturned.document)).toEqual([
      { rowId: parent.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: child.id, kind: "clip", parentRowId: null, sectionId: null },
    ]);
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

  it("preserves the current origin against forged whole-row replacement and marks compact edits as rows", () => {
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
    stored.stashOrigin = { kind: "note", parentRowId: null, sectionId: null, siblingIndex: 0, returnEligible: true };
    const replacement = structuredClone(stored);
    replacement.notes = ["Edited saved source."];
    replacement.stashOrigin = { kind: "clip", parentRowId: id(499999), sectionId: null, siblingIndex: 9, returnEligible: true };
    const edited = applyStashRowEditV2(doc, 1, { bundleId: id(400000), rowId: source.id, row: replacement });
    expect(edited.ok, JSON.stringify(edited.diagnostics)).toBe(true);
    expect(edited.document.stash?.[0]?.rows[0]?.stashOrigin).toEqual({ kind: "note", parentRowId: null, sectionId: null, siblingIndex: 0, returnEligible: false });
    expect(outline(edited.document)[0]?.kind).toBe("row");
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
    const token = row.tokens[0]!;
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
