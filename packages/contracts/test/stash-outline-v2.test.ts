import { describe, expect, it } from "vitest";

import {
  applyRowEditV2,
  applyStageDirectionEditV2,
  applyStashRowEditV2,
  applyVisualSequenceEditV2,
  createResearchClipOccurrenceV2,
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

function persistedPlainNote(text: string, value = 600000): ScriptDocumentV2 {
  const row = narration(value);
  row.text = text;
  row.plainDirection = true;
  row.tokens = [...text.matchAll(/\S+/gu)].map((word, index) => ({
    id: id(value + 10000 + index),
    value: word[0],
    startOffset: word.index,
    endOffset: word.index + word[0].length,
    spoken: false,
  }));
  const document = documentWith();
  document.stash = [{ id: id(value + 20000), rows: [row], supportingItems: [] }];
  document.stashOutline = [{ rowId: row.id, kind: "note", parentRowId: null, sectionId: null }];
  return document;
}

function rawNote(value: number, text: string): NarrationBlockV2 {
  const row = narration(value);
  row.text = text;
  row.tokens = [...text.matchAll(/\S+/gu)].map((word, index) => ({
    id: id(value + 10000 + index),
    value: word[0],
    startOffset: word.index,
    endOffset: word.index + word[0].length,
  }));
  return row;
}

function attachmentFixture(blank = false): {
  doc: ScriptDocumentV2; note: NarrationBlockV2; ordinary: VisualOnlyBlockV2;
  attached: VisualOnlyBlockV2; nested: NarrationBlockV2; grandchild: VisualOnlyBlockV2; other: VisualOnlyBlockV2;
} {
  const note = narration(1000000);
  note.plainDirection = true;
  note.tokens.forEach((token) => { token.spoken = false; });
  if (blank) { note.text = ""; note.tokens = []; }
  const ordinary = clip(1020000);
  const attached = clip(1040000);
  const nested = narration(1060000);
  nested.plainDirection = true;
  nested.tokens.forEach((token) => { token.spoken = false; });
  const grandchild = clip(1080000);
  const other = clip(1100000);
  const rows = [note, ordinary, nested, grandchild, attached, other];
  const doc = documentWith();
  doc.stash = rows.map((row, index) => ({ id: id(1500000 + index), rows: [row], supportingItems: [] }));
  doc.stashOutline = [
    { rowId: note.id, kind: "note", parentRowId: null, sectionId: null },
    { rowId: ordinary.id, kind: "clip", parentRowId: note.id, sectionId: null },
    { rowId: nested.id, kind: "note", parentRowId: note.id, sectionId: null },
    { rowId: grandchild.id, kind: "clip", parentRowId: nested.id, sectionId: null },
    { rowId: attached.id, kind: "clip", parentRowId: note.id, sectionId: null },
    { rowId: other.id, kind: "clip", parentRowId: null, sectionId: null },
  ];
  return { doc, note, ordinary, attached, nested, grandchild, other };
}

describe("exclusive Stash footage transactions (issue 367 phase 2)", () => {
  const content = (doc: ScriptDocumentV2) => ({ ...doc, rowEditRevision: undefined });
  const attach = (doc: ScriptDocumentV2, noteId: string, clipId: string) =>
    applyRowEditV2(doc, doc.rowEditRevision ?? 0, { kind: "attach_stash_footage", noteRowId: noteId, clipRowId: clipId });

  it("keeps an exclusive parked clip through a cross-section place, return and re-place", () => {
    const { doc, note, attached } = attachmentFixture();
    const originalFootage = structuredClone(attached);
    const owned = attach(doc, note.id, attached.id);
    expect(owned.ok, JSON.stringify(owned.diagnostics)).toBe(true);
    const first = id(1190000);
    const later = id(1190001);
    const document = structuredClone(owned.document);
    document.activeDraft.blocks.push(
      { type: "section", id: first, title: "First", orderKey: "1", version: 1 },
      { type: "section", id: later, title: "Later", orderKey: "2", version: 1 },
    );
    const placed = applyRowEditV2(document, 1, {
      kind: "place_stash_rows", rowIds: [note.id], includeDescendants: false,
      destination: gap(later, null, null),
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const active = placed.document.activeDraft.blocks.at(-1) as NarrationBlockV2;
    expect(active.attachedFootage?.clip).toEqual(originalFootage);
    const parked = applyRowEditV2(placed.document, 2, {
      kind: "stash_rows", rowIds: [note.id], bundleId: id(1190002),
    });
    expect(parked.ok, JSON.stringify(parked.diagnostics)).toBe(true);
    const parkedNote = parked.document.stash!.flatMap((bundle) => bundle.rows).find((row) => row.id === note.id) as NarrationBlockV2;
    expect(parkedNote.attachedFootage?.clip).toEqual(originalFootage);
    expect(parkedNote.primaryVisualSequence?.slots[0]).toMatchObject({ payload: { kind: "on_camera" } });
    const reloaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(parked.document));
    expect(reloaded.ok).toBe(true);
    if (!reloaded.ok) return;
    const restored = applyRowEditV2(reloaded.document, 3, {
      kind: "place_stash_rows", rowIds: [note.id], includeDescendants: false,
      destination: gap(first, null, null),
    });
    expect(restored.ok, JSON.stringify(restored.diagnostics)).toBe(true);
    expect((restored.document.activeDraft.blocks[1] as NarrationBlockV2).attachedFootage?.clip).toEqual(originalFootage);
    expect(restored.document.extras).toEqual([]);
    expect(validateScriptDocumentV2(restored.document).valid).toBe(true);
    expect(doc).toEqual(attachmentFixture().doc);
  });

  it("attaches only an explicitly selected clip, persists exactly one owner, and places parent-only with descendants promoted", () => {
    const { doc, note, ordinary, attached, nested, grandchild, other } = attachmentFixture();
    const original = structuredClone(doc);
    const transaction = createRowEditSessionV2(doc);
    const a = transaction.apply({ kind: "attach_stash_footage", noteRowId: note.id, clipRowId: attached.id });
    expect(a.ok, JSON.stringify(a.diagnostics)).toBe(true);
    expect(validateScriptDocumentV2(a.document).valid).toBe(true);
    expect(a.document.stash!.flatMap((bundle) => bundle.rows).map((row) => row.id)).not.toContain(attached.id);
    expect((a.document.stash!.flatMap((bundle) => bundle.rows).find((row) => row.id === note.id) as NarrationBlockV2).attachedFootage?.clip).toEqual(attached);
    expect(outline(a.document).find((entry) => entry.rowId === ordinary.id)?.parentRowId).toBe(note.id);
    const saved = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(a.document));
    expect(saved.ok).toBe(true);
    if (!saved.ok) return;

    const placed = transaction.apply({
      kind: "place_stash_rows", rowIds: [note.id], destination: gap(null, null, null), includeDescendants: false,
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const replay = applyRowEditV2(saved.document, 1, {
      kind: "place_stash_rows", rowIds: [note.id], destination: gap(null, null, null), includeDescendants: false,
    });
    expect(replay.document).toEqual(placed.document); // stable derived payload IDs across replay
    expect(placed.document.activeDraft.blocks.map((row) => row.id)).toEqual([note.id]);
    const activeNote = placed.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(activeNote.plainDirection).toBe(true);
    expect(activeNote.attachedFootage?.clip.id).toBe(attached.id);
    const slot = activeNote.primaryVisualSequence?.slots[0];
    expect(slot?.kind).toBe("content");
    if (slot?.kind === "content") {
      expect(slot.payload.kind).toBe("visual");
      if (slot.payload.kind === "visual") {
        expect(slot.payload.pictureKind).toBe("clip");
        expect(slot.payload.source).toEqual(attached.payload.source);
        expect(slot.payload.selectedSourceRange).toEqual(attached.visualOnlyTiming.selectedSourceRange);
        expect(slot.playoutPolicy).toBe("match_structural_interval");
      }
    }
    expect(outline(placed.document)).toEqual([
      { rowId: ordinary.id, kind: "clip", parentRowId: null, sectionId: null },
      { rowId: nested.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: grandchild.id, kind: "clip", parentRowId: nested.id, sectionId: null },
      { rowId: other.id, kind: "clip", parentRowId: null, sectionId: null },
    ]);
    expect(validateScriptDocumentV2(placed.document).valid).toBe(true);
    const returned = transaction.apply({ kind: "stash_rows", rowIds: [note.id], bundleId: id(1599000) });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    const returnedNote = returned.document.stash!.flatMap((bundle) => bundle.rows).find((row) => row.id === note.id) as NarrationBlockV2;
    expect(returnedNote.attachedFootage?.clip.id).toBe(attached.id);
    expect(returnedNote.primaryVisualSequence).toEqual(note.primaryVisualSequence);
    expect(validateScriptDocumentV2(returned.document).valid).toBe(true);
    expect(transaction.undo().ok).toBe(true); // undo return
    expect(content(transaction.document)).toEqual(content(placed.document));
    expect(transaction.undo().ok).toBe(true); // undo placement
    expect(content(transaction.document)).toEqual(content(a.document));
    expect(transaction.undo().ok).toBe(true); // undo attach
    expect(content(transaction.document)).toEqual(content(original));
  });

  it("places a complete branch in preorder but never emits a separate attached clip row", () => {
    const { doc, note, ordinary, attached, nested, grandchild, other } = attachmentFixture();
    const a = attach(doc, note.id, attached.id);
    expect(a.ok).toBe(true);
    const result = applyRowEditV2(a.document, 1, {
      kind: "place_stash_rows", rowIds: [note.id], destination: gap(null, null, null), includeDescendants: true,
    });
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(result.document.activeDraft.blocks.map((row) => row.id)).toEqual([note.id, ordinary.id, nested.id, grandchild.id]);
    expect(outline(result.document).map((entry) => entry.rowId)).toEqual([other.id]);
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
  });

  it("creates and places an unresolved logged Research clip without inventing media bindings", () => {
    const note = narration(1800000);
    const pending = createResearchClipOccurrenceV2({
      candidate: {
        id: id(1900000), projectId: id(1900001), catalogVideoId: id(1900002),
        version: 2, createdBy: id(1900003),
        video: { youtubeVideoId: "synthetic", canonicalUrl: "https://youtu.be/synthetic", title: "Synthetic" },
        selection: {
          trackId: id(1900004), transcriptVersion: 3,
          firstSegmentId: id(1900005), lastSegmentId: id(1900006),
          transcriptStartMs: 1000, transcriptEndMs: 2000,
          exportStartMs: 500, exportEndMs: 2500,
          text: "Synthetic", timingPrecision: "cue",
        },
        englishText: "Synthetic",
      },
      rowId: id(1910000), payloadId: id(1910001), orderKey: "unresolved-logged-clip",
    });
    expect(pending.payload.pictureKind).toBe("unresolved_visual");
    const createdNote = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(1910002), row: note, sectionId: null,
      parentRowId: null, afterRowId: null,
    });
    expect(createdNote.ok).toBe(true);
    const createdClip = applyRowEditV2(createdNote.document, 1, {
      kind: "create_stash_clip", bundleId: id(1910003), row: pending,
      sectionId: null, parentRowId: note.id, afterRowId: null,
    });
    expect(createdClip.ok, JSON.stringify(createdClip.diagnostics)).toBe(true);
    const attached = applyRowEditV2(createdClip.document, 2, {
      kind: "attach_stash_footage", noteRowId: note.id, clipRowId: pending.id,
    });
    expect(attached.ok, JSON.stringify(attached.diagnostics)).toBe(true);
    const placed = applyRowEditV2(attached.document, 3, {
      kind: "place_stash_rows", rowIds: [note.id], destination: gap(null, null, null),
      includeDescendants: false,
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const row = placed.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(row.attachedFootage?.clip).toEqual(pending);
    const slot = row.primaryVisualSequence?.slots[0];
    expect(slot?.kind).toBe("content");
    if (slot?.kind === "content" && slot.payload.kind === "visual") {
      expect(slot.payload.pictureKind).toBe("unresolved_visual");
      expect(slot.payload.researchClip?.createdBy).toBe(id(1900003));
      expect(slot.payload.frameBinding).toBeUndefined();
      expect(slot.payload.selectedSourceRange).toBeUndefined();
    }
    expect(validateScriptDocumentV2(placed.document).valid).toBe(true);
    expect(deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(placed.document)).ok).toBe(true);
  });

  it("replaces and detaches without losing either clip and Undo exactly recovers both transactions", () => {
    const { doc, note, ordinary, attached } = attachmentFixture();
    const session = createRowEditSessionV2(doc);
    expect(session.apply({ kind: "attach_stash_footage", noteRowId: note.id, clipRowId: attached.id }).ok).toBe(true);
    const afterAttach = session.document;
    const replaced = session.apply({
      kind: "replace_stash_footage", noteRowId: note.id, clipRowId: ordinary.id, releasedBundleId: id(1600000),
    });
    expect(replaced.ok, JSON.stringify(replaced.diagnostics)).toBe(true);
    expect((replaced.document.stash!.flatMap((bundle) => bundle.rows).find((row) => row.id === note.id) as NarrationBlockV2).attachedFootage?.clip.id).toBe(ordinary.id);
    expect(outline(replaced.document).find((entry) => entry.rowId === attached.id)?.parentRowId).toBe(note.id);
    expect(replaced.document.stash!.flatMap((bundle) => bundle.rows).filter((row) => row.id === attached.id)).toEqual([attached]);
    expect(validateScriptDocumentV2(replaced.document).valid).toBe(true);
    const detached = session.apply({ kind: "detach_stash_footage", noteRowId: note.id, bundleId: id(1600001) });
    expect(detached.ok, JSON.stringify(detached.diagnostics)).toBe(true);
    expect((detached.document.stash!.flatMap((bundle) => bundle.rows).find((row) => row.id === note.id) as NarrationBlockV2).attachedFootage).toBeUndefined();
    expect(outline(detached.document).find((entry) => entry.rowId === ordinary.id)?.parentRowId).toBe(note.id);
    expect(validateScriptDocumentV2(detached.document).valid).toBe(true);
    expect(session.undo().ok).toBe(true);
    expect(content(session.document)).toEqual(content(replaced.document));
    expect(session.undo().ok).toBe(true);
    expect(content(session.document)).toEqual(content(afterAttach));
  });

  it("replaces a blank note at its exact outline position with owned footage and promotes ordinary descendants", () => {
    const { doc, note, ordinary, attached, nested, grandchild, other } = attachmentFixture(true);
    const session = createRowEditSessionV2(doc);
    const a = session.apply({ kind: "attach_stash_footage", noteRowId: note.id, clipRowId: attached.id });
    expect(a.ok, JSON.stringify(a.diagnostics)).toBe(true);
    const cleaned = session.apply({ kind: "cleanup_blank_stash_note", noteRowId: note.id, clipBundleId: id(1600002) });
    expect(cleaned.ok, JSON.stringify(cleaned.diagnostics)).toBe(true);
    expect(outline(cleaned.document)).toEqual([
      { rowId: attached.id, kind: "clip", parentRowId: null, sectionId: null },
      { rowId: ordinary.id, kind: "clip", parentRowId: null, sectionId: null },
      { rowId: nested.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: grandchild.id, kind: "clip", parentRowId: nested.id, sectionId: null },
      { rowId: other.id, kind: "clip", parentRowId: null, sectionId: null },
    ]);
    expect(cleaned.document.stash!.flatMap((bundle) => bundle.rows).some((row) => row.id === note.id)).toBe(false);
    expect(validateScriptDocumentV2(cleaned.document).valid).toBe(true);
    expect(session.undo().ok).toBe(true);
    expect(content(session.document)).toEqual(content(a.document));
  });

  it("refuses stale, occupied, missing, malformed, referenced, nonblank-cleanup and implicit child ownership atomically", () => {
    const { doc, note, ordinary, attached } = attachmentFixture();
    const snapshot = JSON.stringify(doc);
    const invalid: unknown[] = [
      { kind: "attach_stash_footage", noteRowId: note.id, clipRowId: note.id },
      { kind: "attach_stash_footage", noteRowId: note.id, clipRowId: id(9999999) },
      { kind: "attach_stash_footage", noteRowId: note.id, clipRowId: ordinary.id, extra: true },
      { kind: "detach_stash_footage", noteRowId: note.id, bundleId: id(1600010) },
      { kind: "cleanup_blank_stash_note", noteRowId: note.id, clipBundleId: id(1600011) },
      { kind: "place_stash_rows", rowIds: [note.id], destination: gap(null, null, null), includeDescendants: "false" },
      { kind: "place_stash_rows", rowIds: [note.id], destination: gap(null, null, null), includeDescendants: undefined },
      { kind: "place_stash_rows", rowIds: [note.id], destination: gap(null, null, null), includeDescendants: false, extra: 2 },
    ];
    for (const value of invalid) {
      const result = applyRowEditV2(doc, 0, value as Parameters<typeof applyRowEditV2>[2]);
      expect(result.ok, JSON.stringify(value)).toBe(false);
      expect(result.document).toBe(doc);
      expect(JSON.stringify(doc)).toBe(snapshot);
    }
    const a = attach(doc, note.id, attached.id);
    expect(a.ok, JSON.stringify(a.diagnostics)).toBe(true);
    const occupied = applyRowEditV2(a.document, 1, { kind: "attach_stash_footage", noteRowId: note.id, clipRowId: ordinary.id });
    expect(occupied.ok).toBe(false);
    expect(occupied.document).toBe(a.document);
    const stale = applyRowEditV2(a.document, 0, { kind: "detach_stash_footage", noteRowId: note.id, bundleId: id(1600012) });
    expect(stale.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    const existingId = applyRowEditV2(a.document, 1, { kind: "detach_stash_footage", noteRowId: note.id, bundleId: a.document.stash![0]!.id });
    expect(existingId.ok).toBe(false);
    expect(JSON.stringify(a.document)).toBe(JSON.stringify(attach(doc, note.id, attached.id).document));
    const forbiddenDelete = applyRowEditV2(a.document, 1, { kind: "delete_rows", rowIds: [note.id, ordinary.id] });
    expect(forbiddenDelete.ok).toBe(false);
    expect(forbiddenDelete.document).toBe(a.document);

    const referenced = structuredClone(doc);
    referenced.rowReferences = [{ id: id(1600013), rowId: attached.id, kind: "reference", anchor: { source: "clip" } }];
    const notTransferred = attach(referenced, note.id, attached.id);
    expect(notTransferred.ok).toBe(false);
    expect(notTransferred.document).toBe(referenced);
    expect(referenced.stashOutline).toEqual(doc.stashOutline);
  });

  it("refuses unsupported full-source audio instead of silently muting footage in the note", () => {
    const { doc, note, attached } = attachmentFixture();
    attached.payload.audioPolicy = "full";
    const a = attach(doc, note.id, attached.id);
    expect(a.ok, JSON.stringify(a.diagnostics)).toBe(true);
    const placed = applyRowEditV2(a.document, 1, {
      kind: "place_stash_rows", rowIds: [note.id], destination: gap(null, null, null),
      includeDescendants: false,
    });
    expect(placed.ok).toBe(false);
    expect(placed.diagnostics[0]?.code).toBe("STASH_ATTACHMENT_VISUAL_CONFLICT");
    expect(placed.document).toBe(a.document);
  });

  it("refuses to discard edited active visual content when a note is returned", () => {
    const { doc, note, attached } = attachmentFixture();
    const a = attach(doc, note.id, attached.id);
    expect(a.ok).toBe(true);
    const placed = applyRowEditV2(a.document, 1, {
      kind: "place_stash_rows", rowIds: [note.id], destination: gap(null, null, null), includeDescendants: false,
    });
    expect(placed.ok).toBe(true);
    const changed = structuredClone(placed.document.activeDraft.blocks[0]) as NarrationBlockV2;
    const slot = changed.primaryVisualSequence!.slots[0]!;
    if (slot.kind !== "content" || slot.payload.kind !== "visual") throw new Error("Expected derived footage");
    slot.payload.sourceUsage = { sourceInFrame: 8 };
    changed.version++;
    const edited = applyRowEditV2(placed.document, 2, { kind: "edit_row", rowId: note.id, row: changed });
    expect(edited.ok, JSON.stringify(edited.diagnostics)).toBe(true);
    const rejected = applyRowEditV2(edited.document, 3, {
      kind: "stash_rows", rowIds: [note.id], bundleId: id(1700000),
    });
    expect(rejected.ok).toBe(false);
    expect(rejected.document).toBe(edited.document);
    expect(edited.document.activeDraft.blocks[0]).toEqual(changed.stashOrigin
      ? { ...changed, stashOrigin: { ...changed.stashOrigin, returnEligible: false } }
      : changed);
  });
});

describe("forgiving return integration", () => {
  it("freezes the full sibling history and falls back after an old parent is deleted", () => {
    const parent = narration(951000);
    const child = clip(951010);
    const other = narration(951020);
    let document = documentWith();
    for (const [row, bundle, parentRowId, afterRowId] of [
      [parent, id(951100), null, null], [child, id(951101), parent.id, null],
      [other, id(951102), null, parent.id],
    ] as const) {
      const command = row.type === "narration"
        ? { kind: "create_stash_note" as const, bundleId: bundle, row, sectionId: null, parentRowId, afterRowId }
        : { kind: "create_stash_clip" as const, bundleId: bundle, row, sectionId: null, parentRowId, afterRowId };
      const result = applyRowEditV2(document, document.rowEditRevision ?? 0, command);
      expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
      document = result.document;
    }
    const placed = applyRowEditV2(document, 3, {
      kind: "place_stash_rows", rowIds: [child.id], destination: gap(null, null, null),
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const original = (placed.document.activeDraft.blocks[0] as VisualOnlyBlockV2).stashOrigin!;
    expect(original.originalParentContext).toMatchObject({ parentRowId: null, sectionId: null, followingSiblingRowIds: [other.id] });
    const deleted = applyRowEditV2(placed.document, 4, { kind: "delete_rows", rowIds: [parent.id] });
    expect(deleted.ok, JSON.stringify(deleted.diagnostics)).toBe(true);
    const session = createRowEditSessionV2(deleted.document);
    const returned = session.apply({ kind: "stash_rows", rowIds: [child.id], bundleId: id(951103) });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    expect(outline(returned.document)).toEqual([
      { rowId: child.id, kind: "clip", sectionId: null, parentRowId: null },
      { rowId: other.id, kind: "note", sectionId: null, parentRowId: null },
    ]);
    expect(session.undo().document).toEqual({ ...deleted.document, rowEditRevision: 7 });
  });

  it("allows a deliberate exact drop over historical order but refuses stale or malformed gaps", () => {
    const a = narration(952000);
    const b = narration(952010);
    const c = narration(952020);
    let doc = documentWith();
    for (const [index, row] of [a, b, c].entries()) {
      const next = applyRowEditV2(doc, index, {
        kind: "create_stash_note", row, bundleId: id(952100 + index), sectionId: null,
        parentRowId: null, afterRowId: index === 0 ? null : [a, b][index - 1]!.id,
      });
      expect(next.ok, JSON.stringify(next.diagnostics)).toBe(true);
      doc = next.document;
    }
    const placed = applyRowEditV2(doc, 3, {
      kind: "place_stash_rows", rowIds: [b.id], destination: gap(null, null, null),
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const destination = { ...gap(null, c.id, null), parentRowId: null };
    for (const invalid of [
      { ...destination, sectionId: id(999990) },
      { ...destination, afterRowId: a.id },
      { ...destination, extra: true },
      { ...destination, parentRowId: id(999991) },
    ]) {
      const refused = applyRowEditV2(placed.document, 4, {
        kind: "stash_rows", rowIds: [b.id], bundleId: id(952104), destination: invalid,
      });
      expect(refused.ok, JSON.stringify(invalid)).toBe(false);
      expect(refused.document).toBe(placed.document);
    }
    const stale = applyRowEditV2(placed.document, 3, { kind: "stash_rows", rowIds: [b.id], bundleId: id(952104), destination });
    expect(stale.diagnostics[0]?.code).toBe("ROW_REVISION_STALE");
    const explicit = applyRowEditV2(placed.document, 4, {
      kind: "stash_rows", rowIds: [b.id], bundleId: id(952104), destination,
    });
    expect(explicit.ok, JSON.stringify(explicit.diagnostics)).toBe(true);
    expect(outline(explicit.document).map((entry) => entry.rowId)).toEqual([a.id, c.id, b.id]);
  });

  it("returns an edited parent as a saved row and preserves note/clip descendants in one Undoable batch", () => {
    const parent = narration(953000);
    const child = narration(953010);
    const grandchild = clip(953020);
    const neighbor = narration(953030);
    let doc = documentWith();
    const commands = [
      { kind: "create_stash_note" as const, row: parent, bundleId: id(953100), sectionId: null, parentRowId: null, afterRowId: null },
      { kind: "create_stash_note" as const, row: child, bundleId: id(953101), sectionId: null, parentRowId: parent.id, afterRowId: null },
      { kind: "create_stash_clip" as const, row: grandchild, bundleId: id(953102), sectionId: null, parentRowId: child.id, afterRowId: null },
      { kind: "create_stash_note" as const, row: neighbor, bundleId: id(953103), sectionId: null, parentRowId: null, afterRowId: parent.id },
    ];
    for (const command of commands) {
      const next = applyRowEditV2(doc, doc.rowEditRevision ?? 0, command);
      expect(next.ok, JSON.stringify(next.diagnostics)).toBe(true);
      doc = next.document;
    }
    const placed = applyRowEditV2(doc, 4, {
      kind: "place_stash_rows", rowIds: [parent.id], destination: gap(null, null, null),
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const replacement = structuredClone(placed.document.activeDraft.blocks[0]) as NarrationBlockV2;
    replacement.version += 1;
    replacement.orderKey = "edited-parent";
    const edited = applyRowEditV2(placed.document, 5, { kind: "edit_row", rowId: parent.id, row: replacement });
    expect(edited.ok, JSON.stringify(edited.diagnostics)).toBe(true);
    expect((edited.document.activeDraft.blocks[0] as NarrationBlockV2).stashOrigin?.returnEligible).toBe(false);
    const session = createRowEditSessionV2(edited.document);
    const returned = session.apply({ kind: "stash_rows", rowIds: [parent.id, child.id, grandchild.id], bundleId: id(953104) });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    expect(outline(returned.document)).toEqual([
      { rowId: parent.id, kind: "row", parentRowId: null, sectionId: null },
      { rowId: child.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: grandchild.id, kind: "clip", parentRowId: child.id, sectionId: null },
      { rowId: neighbor.id, kind: "note", parentRowId: null, sectionId: null },
    ]);
    expect(validateScriptDocumentV2(returned.document).valid).toBe(true);
    const independentlyPlaced = applyRowEditV2(returned.document, 7, {
      kind: "place_stash_rows", rowIds: [grandchild.id], destination: gap(null, null, null),
    });
    expect(independentlyPlaced.ok, JSON.stringify(independentlyPlaced.diagnostics)).toBe(true);
    const invalidParentDrop = applyRowEditV2(independentlyPlaced.document, 8, {
      kind: "stash_rows", rowIds: [grandchild.id], bundleId: id(953105),
      destination: { ...gap(null, null, null), parentRowId: parent.id },
    });
    expect(invalidParentDrop.ok).toBe(false);
    expect(invalidParentDrop.document).toBe(independentlyPlaced.document);
    expect(session.undo().document).toEqual({ ...edited.document, rowEditRevision: 8 });
  });

  it("returns to unsectioned top when the original named section no longer exists", () => {
    const sectionId = id(954000);
    const row = narration(954010);
    let doc = applyRowEditV2(documentWith(), 0, { kind: "create_stash_section", sectionId, title: "Temporary" }).document;
    doc = applyRowEditV2(doc, 1, { kind: "create_stash_note", row, bundleId: id(954100), sectionId, parentRowId: null, afterRowId: null }).document;
    const placed = applyRowEditV2(doc, 2, { kind: "place_stash_rows", rowIds: [row.id], destination: gap(null, null, null) });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const withoutSection = structuredClone(placed.document);
    delete withoutSection.stashSections;
    const returned = applyRowEditV2(withoutSection, 3, { kind: "stash_rows", rowIds: [row.id], bundleId: id(954101) });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    expect(outline(returned.document)).toEqual([{ rowId: row.id, kind: "note", parentRowId: null, sectionId: null }]);
  });
});

describe("persisted plain-direction intent (phase 1)", () => {
  it("refuses unpaired UTF-16 surrogates even in an untokenized plain note", () => {
    for (const invalidText of ["\ud83d", "a\udc00b", "\ud83d\ud83d\ude00"]) {
      const document = persistedPlainNote(invalidText);
      const result = validateScriptDocumentV2(document);
      expect(result.valid, invalidText).toBe(false);
      expect(result.diagnostics.some((item) => item.code === "PLAIN_DIRECTION_INTENT_INVALID"), invalidText).toBe(true);
      expect(deserializeAuthoringDocumentV2(JSON.stringify(document)).ok, invalidText).toBe(false);
    }
  });

  it("round-trips empty, whitespace, multiline, Unicode and literal brackets without normalizing raw text", () => {
    for (const text of ["", "  \t\n ", " [outer [inner]] missing] ‘quote’ 😀\nnext [line\n "]) {
      const document = persistedPlainNote(text);
      expect(validateScriptDocumentV2(document)).toEqual({ valid: true, diagnostics: [] });
      const saved = serializeAuthoringDocumentV2(document);
      const loaded = deserializeAuthoringDocumentV2(saved);
      expect(loaded.ok).toBe(true);
      if (!loaded.ok) continue;
      const row = loaded.document.stash?.[0]?.rows[0] as NarrationBlockV2;
      expect(row.text).toBe(text);
      expect(row.plainDirection).toBe(true);
      expect(row.tokens.every((token) => token.spoken === false)).toBe(true);
      expect(loaded.document.stashOutline).toEqual(document.stashOutline);
      expect(JSON.stringify(loaded.document)).toBe(JSON.stringify(document));
    }
  });

  it("rejects corrupt semantic intent even when the row is parked in Stash", () => {
    const originals = persistedPlainNote("😀 [hello] more");
    const changes: [string, (row: NarrationBlockV2) => void][] = [
      ["spoken token", (row) => { row.tokens[0]!.spoken = true; }],
      ["missing nonspoken marker", (row) => { delete row.tokens[0]!.spoken; }],
      ["wrong frozen text", (row) => { row.tokens[0]!.value = "changed"; }],
      ["wrong UTF-16 offset", (row) => { row.tokens[0]!.endOffset += 1; }],
      ["split surrogate", (row) => {
        row.tokens[0]!.value = "\ud83d";
        row.tokens[0]!.endOffset = 1;
      }],
    ];
    for (const [name, corrupt] of changes) {
      const document = structuredClone(originals);
      const row = document.stash![0]!.rows[0] as NarrationBlockV2;
      corrupt(row);
      const snapshot = JSON.stringify(document);
      const validation = validateScriptDocumentV2(document);
      expect(validation.valid, name).toBe(false);
      expect(validation.diagnostics.some((item) =>
        item.code === "PLAIN_DIRECTION_INTENT_INVALID" &&
        item.jsonPath.includes("/stash/0/rows/0/tokens/0"),
      ), name).toBe(true);
      expect(deserializeAuthoringDocumentV2(snapshot).ok, name).toBe(false);
      expect(() => serializeAuthoringDocumentV2(document), name).toThrow();
      expect(JSON.stringify(document), name).toBe(snapshot);
    }
    expect(JSON.stringify(originals)).toBe(serializeAuthoringDocumentV2(originals));
  });

  it("retains old saved narration notes and real paired direction syntax without migration", () => {
    const doc = persistedPlainNote("old text", 630000);
    const row = doc.stash![0]!.rows[0] as NarrationBlockV2;
    delete row.plainDirection;
    row.text = "[old]";
    row.tokens = [{ id: id(645000), value: "old", startOffset: 1, endOffset: 4, spoken: false }];
    expect(validateScriptDocumentV2(doc).valid).toBe(true);
    const reloaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(doc));
    expect(reloaded.ok).toBe(true);
    if (reloaded.ok) expect(reloaded.document.stash?.[0]?.rows[0]).toEqual(row);

    const emptyOld = structuredClone(doc);
    (emptyOld.stash![0]!.rows[0] as NarrationBlockV2).text = "";
    (emptyOld.stash![0]!.rows[0] as NarrationBlockV2).tokens = [];
    expect(validateScriptDocumentV2(emptyOld).valid).toBe(false);
    expect(deserializeAuthoringDocumentV2(JSON.stringify(emptyOld)).ok).toBe(false);
  });
});

describe("mixed Stash outline contract", () => {
  it("saves, places and returns literal nested/unmatched and empty notes without inventing syntax or identities", () => {
    const literal = "  [outer [inner]] ] unmatched 'quoted' 😀\nsecond line [\n ";
    const parent = rawNote(810000, literal);
    const child = rawNote(825000, "");
    const created = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(830000), row: parent,
      sectionId: null, parentRowId: null, afterRowId: null,
    });
    expect(created.ok, JSON.stringify(created.diagnostics)).toBe(true);
    const nested = applyRowEditV2(created.document, 1, {
      kind: "create_stash_note", bundleId: id(830001), row: child,
      sectionId: null, parentRowId: parent.id, afterRowId: null,
    });
    expect(nested.ok, JSON.stringify(nested.diagnostics)).toBe(true);
    const loaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(nested.document));
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    const saved = loaded.document.stash!.flatMap((bundle) => bundle.rows) as NarrationBlockV2[];
    expect(saved.map((row) => [row.id, row.text, row.plainDirection])).toEqual([
      [parent.id, literal, true], [child.id, "", true],
    ]);
    expect(saved[0]!.tokens.map((token) => token.id)).toEqual(parent.tokens.map((token) => token.id));
    expect(saved.every((row) => row.tokens.every((token) => token.spoken === false))).toBe(true);
    const placed = applyRowEditV2(loaded.document, 2, {
      kind: "place_stash_rows", rowIds: [parent.id], destination: gap(null, null, null),
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    const active = placed.document.activeDraft.blocks as NarrationBlockV2[];
    expect(active.map((row) => [row.id, row.text, row.stashOrigin?.returnEligible])).toEqual([
      [parent.id, literal, true], [child.id, "", true],
    ]);
    const literalBracket = applyStageDirectionEditV2(placed.document, active[0]!.version, {
      kind: "delete_direction_delimiter", blockId: parent.id, offset: 2,
    });
    expect(literalBracket.diagnostics[0]?.code).toBe("STAGE_DIRECTION_PAIR_NOT_FOUND");
    expect(literalBracket.document).toBe(placed.document);
    const emptySpeech = applyStageDirectionEditV2(placed.document, active[1]!.version, {
      kind: "make_spoken", blockId: child.id, startOffset: 0, endOffset: 0,
    });
    expect(emptySpeech.diagnostics[0]?.code).toBe("STAGE_DIRECTION_SELECTION_INVALID");
    expect(emptySpeech.document).toBe(placed.document);
    const returned = applyRowEditV2(placed.document, 3, {
      kind: "stash_rows", rowIds: [parent.id, child.id], bundleId: id(830002),
    });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    expect(outline(returned.document)).toEqual(outline(loaded.document));
    expect(returned.document.stash!.flatMap((bundle) => bundle.rows).map((row) => [row.id, (row as NarrationBlockV2).text, (row as NarrationBlockV2).plainDirection])).toEqual([
      [parent.id, literal, true], [child.id, "", true],
    ]);
  });

  it("keeps exact raw note data and eligibility across explicit whole-row conversion and Undo", () => {
    const source = rawNote(850000, " [literal [nested]] odd] 😀\n last ");
    const created = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(890000), row: source,
      sectionId: null, parentRowId: null, afterRowId: null,
    });
    const placed = applyRowEditV2(created.document, 1, {
      kind: "place_stash_rows", rowIds: [source.id], destination: gap(null, null, null),
    });
    expect(placed.ok).toBe(true);
    const original = placed.document.activeDraft.blocks[0] as NarrationBlockV2;
    const spoken = applyStageDirectionEditV2(placed.document, original.version, {
      kind: "make_spoken", blockId: source.id, startOffset: 0, endOffset: original.text.length,
    });
    expect(spoken.ok, JSON.stringify(spoken.diagnostics)).toBe(true);
    const spokenRow = spoken.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(spokenRow).toMatchObject({ id: source.id, text: source.text, version: original.version + 1 });
    expect(spokenRow.plainDirection).toBeUndefined();
    expect(spokenRow.tokens.every((token) => token.spoken === undefined)).toBe(true);
    expect(spokenRow.stashOrigin?.returnEligible).toBe(false);
    const restaged = applyStageDirectionEditV2(spoken.document, spokenRow.version, {
      kind: "make_stage_direction", blockId: source.id, startOffset: 0, endOffset: source.text.length,
    });
    expect(restaged.ok, JSON.stringify(restaged.diagnostics)).toBe(true);
    const directionRow = restaged.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(directionRow.text).toBe(source.text);
    expect(directionRow.plainDirection).toBe(true);
    expect(directionRow.tokens.every((token) => token.spoken === false)).toBe(true);
    expect(directionRow.stashOrigin?.returnEligible).toBe(false);
    const restored = undoStageDirectionEditV2(spoken.document, spoken.undo!);
    expect(restored.ok, JSON.stringify(restored.diagnostics)).toBe(true);
    const restoredRow = restored.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect({ ...restoredRow, version: original.version }).toEqual(original);
    const returned = applyRowEditV2(restored.document, restored.document.rowEditRevision ?? 0, {
      kind: "stash_rows", rowIds: [source.id], bundleId: id(890001),
    });
    expect(returned.ok).toBe(true);
    expect(returned.document.stashOutline?.[0]?.kind).toBe("note");
  });

  it("stores default-direction notes, explicit mixed notes, and standalone footage in saved-row payloads", () => {
    const plain = narration(100000);
    const authored = narration(110000);
    const first = authored.tokens[0]!;
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
    expect(defaultNote.text).toBe(plain.text);
    expect(defaultNote.plainDirection).toBe(true);
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
    // Returning a child must never rewrite the parent's frozen original history.
    expect((childReturned.document.activeDraft.blocks[0] as NarrationBlockV2).stashOrigin?.beforeSiblingRowId).toBeNull();
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
    expect((firstReturned.document.activeDraft.blocks[0] as NarrationBlockV2).stashOrigin?.beforeSiblingRowId).toBeNull();
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
      kind: "make_spoken", blockId: before.id, startOffset: 0, endOffset: before.text.length,
    });
    expect(spoken.ok, JSON.stringify(spoken.diagnostics)).toBe(true);
    const afterEdit = spoken.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(afterEdit.stashOrigin?.returnEligible).toBe(false);
    const undo = undoStageDirectionEditV2(spoken.document, spoken.undo!);
    expect(undo.ok, JSON.stringify(undo.diagnostics)).toBe(true);
    expect((undo.document.activeDraft.blocks[0] as NarrationBlockV2).stashOrigin?.returnEligible).toBe(true);

    const rewrittenFromOriginal = undo.document.activeDraft.blocks[0] as NarrationBlockV2;
    const opened = applyStageDirectionEditV2(undo.document, rewrittenFromOriginal.version, {
      kind: "make_spoken", blockId: rewrittenFromOriginal.id, startOffset: 0, endOffset: rewrittenFromOriginal.text.length,
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
      kind: "make_spoken", blockId: before.id, startOffset: 0, endOffset: before.text.length,
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

  it("returns incomplete sibling runs without inventing a missing anchor", () => {
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
    expect(outOfRange.ok, JSON.stringify(outOfRange.diagnostics)).toBe(true);
    expect(outline(outOfRange.document).map((entry) => entry.rowId)).toEqual([second.id]);
    const returnedFirst = applyRowEditV2(placed.document, 3, {
      kind: "stash_rows", rowIds: [first.id], bundleId: id(610003),
    });
    expect(returnedFirst.ok, JSON.stringify(returnedFirst.diagnostics)).toBe(true);
    expect(outline(returnedFirst.document).map((entry) => entry.rowId)).toEqual([first.id]);
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

  it("resolves two rows with an identical historical gap in selected run order", () => {
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
    const returned = applyRowEditV2(document, 2, {
      kind: "stash_rows", rowIds: [returningA.id, returningB.id], bundleId: id(840002),
    });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    expect(outline(returned.document).map((entry) => entry.rowId)).toEqual([first.id, returningA.id, returningB.id, second.id]);
  });

  it("falls back to unsectioned top after a parent moves and nests again when restored", () => {
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
    const fallback = applyRowEditV2(movedParent.document, 5, {
      kind: "stash_rows", rowIds: [child.id], bundleId: id(650002),
    });
    expect(fallback.ok, JSON.stringify(fallback.diagnostics)).toBe(true);
    expect(outline(fallback.document)).toEqual([
      { rowId: child.id, kind: "clip", parentRowId: null, sectionId: null },
      { rowId: parent.id, kind: "note", parentRowId: null, sectionId },
    ]);
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
    const corruptLiteral = rawNote(715000, "literal [unmatched 😀");
    corruptLiteral.tokens[0]!.startOffset += 1;
    const mismatched = applyRowEditV2(document, 0, {
      kind: "create_stash_note", bundleId: id(725000), row: corruptLiteral,
      sectionId: null, parentRowId: null, afterRowId: null,
    });
    expect(mismatched.ok).toBe(false);
    expect(mismatched.diagnostics.some((item) => item.code === "PLAIN_DIRECTION_INTENT_INVALID")).toBe(true);
    expect(mismatched.document).toBe(document);
    const corruptFlag = rawNote(716000, "plain [literal]");
    corruptFlag.tokens[0]!.spoken = "not-a-boolean" as unknown as false;
    const malformedIntent = applyRowEditV2(document, 0, {
      kind: "create_stash_note", bundleId: id(726000), row: corruptFlag,
      sectionId: null, parentRowId: null, afterRowId: null,
    });
    expect(malformedIntent.diagnostics[0]?.code).toBe("STASH_NOTE_CONTENT_INVALID");
    expect(malformedIntent.document).toBe(document);
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

  it("resolves missing source slots and replays only allowed Sorting operations", () => {
    const parent = narration(410000);
    const created = applyRowEditV2(documentWith(), 0, {
      kind: "create_stash_note", bundleId: id(420000), row: parent,
      sectionId: null, parentRowId: null, afterRowId: null,
    });
    const placed = applyRowEditV2(created.document, 1, { kind: "place_stash_rows", rowIds: [parent.id], destination: gap(null, null, null) });
    expect(placed.ok).toBe(true);
    const missing = structuredClone(placed.document);
    (missing.activeDraft.blocks[0] as NarrationBlockV2).stashOrigin!.parentRowId = id(499998);
    const fallback = applyRowEditV2(missing, 2, { kind: "stash_rows", rowIds: [parent.id], bundleId: id(420001) });
    expect(fallback.ok, JSON.stringify(fallback.diagnostics)).toBe(true);
    expect(outline(fallback.document)).toEqual([{ rowId: parent.id, kind: "note", sectionId: null, parentRowId: null }]);

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
    const recovered = applyRowEditV2(missingSibling, 4, { kind: "stash_rows", rowIds: [second.id], bundleId: id(460002) });
    expect(recovered.ok, JSON.stringify(recovered.diagnostics)).toBe(true);
    expect(outline(recovered.document)).toEqual([{ rowId: second.id, kind: "note", sectionId, parentRowId: null }]);

    const trial = createSortingTrialV2(sectioned);
    expect(trial.apply({
      kind: "set_stash_outline",
      entries: [...outline(sectioned)].reverse(),
    }).ok).toBe(true);
    expect(trial.apply({ kind: "create_stash_note", bundleId: id(470000), row: narration(470100), sectionId: null, parentRowId: null, afterRowId: null }).ok).toBe(true);
    const selectedRoot = trial.document.stashOutline![0]!.rowId;
    expect(trial.apply({ kind: "place_stash_rows", rowIds: [selectedRoot], destination: gap(null, null, null) }).ok).toBe(true);
    const resumed = resumeSortingTrialV2(trial.serialize());
    expect(resumed.document.stashOutline).toEqual(trial.document.stashOutline);
    expect(resumed.document.activeDraft.blocks.map((block) => block.id)).toEqual([selectedRoot]);
  });

  it("upgrades legacy section rowIds on placement and returns a historical six-field batch in order", () => {
    const first = narration(610000);
    const second = narration(620000);
    const sectionId = id(630000);
    const legacy = documentWith();
    legacy.stash = [{ id: id(640000), rows: [first, second], supportingItems: [] }];
    legacy.stashSections = [{ id: sectionId, title: "Old saved section", rowIds: [first.id, second.id] }];
    const placed = applyRowEditV2(legacy, 0, {
      kind: "place_stash_rows", rowIds: [first.id, second.id], destination: gap(null, null, null),
    });
    expect(placed.ok, JSON.stringify(placed.diagnostics)).toBe(true);
    if (!placed.ok) return;

    // An older client persisted the original six fields but not frozen history arrays.
    const oldJson = structuredClone(placed.document);
    for (const block of oldJson.activeDraft.blocks) {
      if (block.type === "section" || !block.stashOrigin) continue;
      delete block.stashOrigin.precedingSiblingRowIds;
      delete block.stashOrigin.followingSiblingRowIds;
      delete block.stashOrigin.originalParentContext;
    }
    const loaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(oldJson));
    expect(loaded.ok, JSON.stringify(loaded)).toBe(true);
    if (!loaded.ok) return;
    const returned = applyRowEditV2(loaded.document, 1, {
      kind: "stash_rows", rowIds: [first.id, second.id], bundleId: id(650000),
    });
    expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
    expect(outline(returned.document)).toEqual([
      { rowId: first.id, kind: "row", parentRowId: null, sectionId },
      { rowId: second.id, kind: "row", parentRowId: null, sectionId },
    ]);
    expect(returned.document.stashSections).toEqual([{ id: sectionId, title: "Old saved section", rowIds: [] }]);
    expect(returned.document.activeDraft.blocks).toEqual([]);
    expect(validateScriptDocumentV2(returned.document).valid).toBe(true);
  });
});
