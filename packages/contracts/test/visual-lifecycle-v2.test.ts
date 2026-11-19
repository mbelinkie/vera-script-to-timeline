import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  applyVisualSequenceEditV2,
  applyCommentOperationV2,
  createCommentStateV2,
  createRowEditSessionV2,
  deserializeAuthoringDocumentV2,
  projectPrimarySequenceV2,
  serializeAuthoringDocumentV2,
  validateScriptDocumentV2,
} from "@vera/contracts/authoring-v2";
import { compileTimelineV2 } from "../src/compiler-core-v2.js";
import type {
  CompilerDependenciesV2,
  ContentSlot,
  NarratedVisualPayloadV2,
  NarrationBlockV2,
  ReturnSlot,
  ScriptDocumentV2,
  VisualOnlyBlockV2,
} from "@vera/contracts/v2";
import type { RowEditCommandV2, VisualSequenceEditCommandV2, VisualSequenceEditResultV2 } from "../src/authoring-v2.js";

type MoveCommand = Extract<VisualSequenceEditCommandV2, { kind: "move_visual_to_row" }>;
type AttachCommand = Extract<VisualSequenceEditCommandV2, { kind: "attach_visual_to_words" }>;
type AddCommand = Extract<VisualSequenceEditCommandV2, { kind: "add_visual_on_selection" }>;
type ChangeCommand = Extract<VisualSequenceEditCommandV2, { kind: "change_visual_type" }>;
type StashCommand = Extract<RowEditCommandV2, { kind: "stash_visual" }>;

/**
 * #578: move a visual to another row unattached, attach it to words, change
 * its type, delete it, and stash it (S03 D87, D88, D91, D93, D100, D113, D146).
 *
 * Each row is ten or so plain words so ranges read as word numbers. Row 1 is
 * the row a visual leaves, row 2 the row it arrives in, row 3 has no narration.
 */

const repo = fileURLToPath(new URL("../../../", import.meta.url));
const id = (value: number): string => `00000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;
const digest = (value: string): string => `sha256:${createHash("sha256").update(value, "utf8").digest("hex")}`;
const rowId = (row: number): string => id(row * 10_000);
const slotId = (row: number, name: string): string => id(row * 10_000 + NAMES.indexOf(name) + 1);
const NAMES = ["F", "S1", "S2", "S3", "OC1", "OC2", "R1", "ADD"];
const MEDIA = id(777);

const nameOf = (value: string): string => {
  const index = (Number.parseInt(value.slice(-12), 16) % 10_000) - 1;
  return NAMES[index] ?? `new:${value.slice(0, 8)}`;
};

/** Footage with a trim: in at frame 48, 96 frames long, quiet source sound, filling the frame. */
function footage(row: number): NarratedVisualPayloadV2 {
  return {
    kind: "visual", payloadId: id(row * 10_000 + 501), pictureKind: "clip",
    source: { kind: "media_reference", mediaReferenceId: MEDIA },
    sourceUsage: { sourceInFrame: 48 }, selectedSourceRange: { startFrame: 48, durationFrames: 96 },
    audioPolicy: "quiet", framingPolicy: "cover",
  };
}

function placeholder(row: number, name: string): NarratedVisualPayloadV2 {
  return {
    kind: "visual", payloadId: id(row * 10_000 + 500 + NAMES.indexOf(name) + 1), pictureKind: "intentional_placeholder",
    source: { kind: "intentional_placeholder", text: `${name} card` }, sourceUsage: null, audioPolicy: "mute", framingPolicy: "contain",
  };
}

type Piece =
  | { at: number; visual: "F" | "S1" | "S2" | "S3"; in?: string }
  | { at: number; onCamera: "OC1" | "OC2" }
  | { at: number; resume: "R1"; of: string };

function rowOf(row: number, text: string, pieces: Piece[]): NarrationBlockV2 {
  let offset = 0;
  const tokens = text.split(" ").map((value, index) => {
    const token = { id: id(row * 10_000 + 1000 + index), value, startOffset: offset, endOffset: offset + value.length };
    offset += value.length + 1;
    return token;
  });
  const anchor = (at: number) => ({
    blockId: rowId(row), tokenId: tokens[at]!.id, affinity: "before" as const, quotedWord: tokens[at]!.value, anchorVersion: 1,
  });
  const slots = pieces.map((piece, index): ContentSlot | ReturnSlot => {
    if ("resume" in piece) {
      return { id: slotId(row, piece.resume), kind: "return", parentSlotId: slotId(row, piece.of), inpoint: anchor(piece.at), version: 1 };
    }
    const name = "visual" in piece ? piece.visual : piece.onCamera;
    return {
      id: slotId(row, name),
      kind: "content",
      relation: "visual" in piece && piece.in ? { kind: "cutaway", parentSlotId: slotId(row, piece.in) } : { kind: index === 0 ? "base" : "sequential" },
      boundaryBefore: index === 0 ? { kind: "row_start" } : { kind: "spoken_word", anchor: anchor(piece.at) },
      payload: "visual" in piece
        ? piece.visual === "F" ? footage(row) : placeholder(row, name)
        : { kind: "on_camera", presenterChoiceId: null },
      playoutPolicy: "match_structural_interval",
      version: 1,
    };
  });
  return {
    type: "narration", id: rowId(row), orderKey: `a${row}`, text, tokens: [tokens[0]!, ...tokens.slice(1)],
    primaryVisualSequence: { id: id(row * 10_000 + 9), slots, version: 1 },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
}

/** A row with no narration: its text is a direction, never spoken. */
function wordlessRow(row: number, pieces: Piece[]): NarrationBlockV2 {
  const row_ = rowOf(row, "Hold on the harbour at dusk", pieces);
  const tokens = row_.tokens.map((token) => ({ ...token, spoken: false as const }));
  return { ...row_, tokens: [tokens[0]!, ...tokens.slice(1)], plainDirection: true };
}

function documentOf(rows: NarrationBlockV2[]): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "Visual lifecycle",
    activeDraft: { blocks: rows, supportingItems: [] }, ideaOutline: [], extras: [], liveHeadSequence: 0,
    liveStateVector: "", liveContentHash: `sha256:${"a".repeat(64)}`,
  };
}

function wordlessPictures(rowNumber: number): VisualOnlyBlockV2 {
  const primary = placeholder(rowNumber, "S1");
  const next = placeholder(rowNumber, "S2");
  return {
    type: "visual_only", id: rowId(rowNumber), orderKey: `a${rowNumber}`, version: 1,
    payload: standalone(primary), visualOnlyTiming: { kind: "visual_only", durationOverrideMs: 4000 },
    additionalVisuals: [{ payload: standalone(next), visualOnlyTiming: { kind: "visual_only", durationOverrideMs: 2500 } }],
  };
}

function standalone(payload: NarratedVisualPayloadV2): VisualOnlyBlockV2["payload"] {
  return Object.fromEntries(Object.entries(payload).filter(([key]) =>
    !["sourceUsage", "selectedSourceRange", "researchClip", "frameBinding"].includes(key))) as VisualOnlyBlockV2["payload"];
}

const TEN = "one two three four five six seven eight nine ten";
const find = (doc: ScriptDocumentV2, row: number): NarrationBlockV2 =>
  doc.activeDraft.blocks.find((block) => block.id === rowId(row)) as NarrationBlockV2;
const word = (doc: ScriptDocumentV2, row: number, index: number): string => find(doc, row).tokens[index]!.id;
const placed = (doc: ScriptDocumentV2, row: number, name: string): ContentSlot | undefined =>
  find(doc, row).primaryVisualSequence!.slots.find((slot): slot is ContentSlot => slot.kind === "content" && slot.id === slotId(row, name));

/** One row's card stack as text: "F 0-4", "OC wide 4-10", "S1 resumes 6-10", "F unattached", "undefined 0-4". */
function cards(doc: ScriptDocumentV2, row: number): string[] {
  const projected = projectPrimarySequenceV2(doc).rows.find((candidate) => candidate.blockId === rowId(row))!;
  return projected.cards.map((card) => {
    if (card.kind === "unattached_visual") return `${nameOf(card.slotId)} unattached`;
    const label = card.kind === "on_camera" ? `OC ${card.framing}` : card.kind === "undefined" ? `undefined(${nameOf(card.slotId)})` : nameOf(card.slotId);
    return `${label}${card.compact ? " resumes" : ""} ${card.startTokenIndex}-${card.endTokenIndexExclusive}`;
  });
}

/** Apply through a session, as the editor does, and prove the three promises every action makes. */
function act(
  start: ScriptDocumentV2,
  command: VisualSequenceEditCommandV2 | RowEditCommandV2,
): { document: ScriptDocumentV2; dropped: { what: string; message: string }[] } {
  const session = createRowEditSessionV2(start);
  const result = isVisualCommand(command) ? session.applyVisualEdit(command) : session.apply(command);
  expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
  expect(validateScriptDocumentV2(result.document).diagnostics.filter((item) => item.severity !== "warning")).toEqual([]);
  // One Undo.
  expect(session.undoDepth).toBe(1);
  const undone = session.undo().document;
  expect({ ...undone, rowEditRevision: 0 }).toEqual({ ...start, rowEditRevision: 0 });
  // Survives save and reload.
  const reloaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(result.document));
  expect(reloaded.ok).toBe(true);
  if (reloaded.ok) expect(reloaded.document).toEqual(result.document);
  const dropped = (result as VisualSequenceEditResultV2).evidence?.dropped ?? [];
  return { document: result.document, dropped };
}

function isVisualCommand(command: VisualSequenceEditCommandV2 | RowEditCommandV2): command is VisualSequenceEditCommandV2 {
  return ["move_visual_to_row", "attach_visual_to_words", "add_visual_on_selection", "change_visual_type", "delete_visual"].includes(command.kind);
}

function refusedWith(start: ScriptDocumentV2, command: VisualSequenceEditCommandV2 | RowEditCommandV2, code: string): string {
  const before = JSON.stringify(start);
  const session = createRowEditSessionV2(start);
  const result = isVisualCommand(command) ? session.applyVisualEdit(command) : session.apply(command);
  expect(result.ok).toBe(false);
  expect(result.diagnostics.map((item) => item.code)).toEqual([code]);
  expect(result.diagnostics[0]!.message.length).toBeGreaterThan(20);
  expect(JSON.stringify(start)).toBe(before);
  expect(session.undoDepth).toBe(0);
  return result.diagnostics[0]!.message;
}

const move = (name: string, from = 1, to = 2): MoveCommand =>
  ({ kind: "move_visual_to_row", blockId: rowId(from), slotId: slotId(from, name), destinationBlockId: rowId(to) });

/** Row 1 opens on footage then On Camera; row 2 is two stills meeting at word 5. */
function twoRows(): ScriptDocumentV2 {
  return documentOf([
    rowOf(1, TEN, [{ at: 0, visual: "F" }, { at: 4, onCamera: "OC1" }]),
    rowOf(2, TEN, [{ at: 0, visual: "S1" }, { at: 5, visual: "S2" }]),
  ]);
}

const addedPayloadId = id(800001);
const add = (doc: ScriptDocumentV2, row: number, first: number, last: number,
  visualType: AddCommand["visualType"] = "onscreen_placeholder"): AddCommand => ({
  kind: "add_visual_on_selection", blockId: rowId(row), slotId: slotId(row, "ADD"), payloadId: addedPayloadId,
  startTokenId: word(doc, row, first), endTokenId: word(doc, row, last), visualType,
});

describe("#67 atomic Add visual on selected words", () => {
  it("takes the first and final word, without disturbing the next cue or adding a return at row end", () => {
    const start = twoRows();
    const first = act(start, add(start, 2, 0, 0)).document;
    expect(cards(first, 2)).toEqual(["ADD 0-1", "S1 1-5", "S2 5-10"]);
    const last = act(start, add(start, 2, 9, 9)).document;
    expect(cards(last, 2)).toEqual(["S1 0-5", "S2 5-9", "ADD 9-10"]);
    expect(find(first, 2).primaryVisualSequence?.version).toBe(2);
    expect(find(last, 2).primaryVisualSequence?.version).toBe(2);
  });

  it("becomes a cutaway inside one picture and returns to the unchanged neighbour", () => {
    const start = twoRows();
    const result = applyVisualSequenceEditV2(start, 1, add(start, 2, 2, 3));
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(cards(result.document, 2)).toEqual(["S1 0-2", "ADD 2-4", "S1 resumes 4-5", "S2 5-10"]);
    expect(result.evidence).toMatchObject({
      kind: "add_visual_on_selection",
      beforeSequenceVersions: { [rowId(2)]: 1 }, afterSequenceVersions: { [rowId(2)]: 2 },
    });
    act(start, add(start, 2, 2, 3)); // one session Undo and exact save/reload
  });

  it("cuts across two visuals while preserving the unused starts and ends", () => {
    const start = twoRows();
    expect(cards(act(start, add(start, 2, 3, 6)).document, 2)).toEqual([
      "S1 0-3", "ADD 3-7", "S2 7-10",
    ]);
  });

  it("adds all three source-free types, and Undefined has no leftover temporary waiting visual", () => {
    for (const type of ["onscreen_placeholder", "need_to_find", "visual_undefined"] as const) {
      const start = twoRows();
      const result = act(start, add(start, 2, 3, 6, type)).document;
      const row = result.activeDraft.blocks[1];
      const slot = row?.type === "narration"
        ? row.primaryVisualSequence!.slots.find((candidate) => candidate.id === slotId(2, "ADD"))
        : undefined;
      expect(slot?.kind).toBe("content");
      if (slot?.kind !== "content") continue;
      if (slot.payload.kind === "on_camera") throw new Error("Added visual must not be On Camera");
      expect(slot.payload.payloadId).toBe(addedPayloadId);
      expect(slot.payload.kind).toBe(type === "visual_undefined" ? "undefined" : "visual");
      if (slot.payload.kind === "visual") {
        expect(slot.payload.pictureKind).toBe(type === "need_to_find" ? "unresolved_visual" : "intentional_placeholder");
      }
      expect(cards(result, 2)).toEqual([
        "S1 0-3", type === "visual_undefined" ? "undefined(ADD) 3-7" : "ADD 3-7", "S2 7-10",
      ]);
      expect(find(result, 2).unattachedVisuals).toBeUndefined();
      expect(find(result, 2).primaryVisualSequence!.version).toBe(2);
    }
  });

  it("refuses stale versions, duplicate slot/payload IDs, malformed types and invalid word anchors without mutation", () => {
    const start = twoRows();
    const before = JSON.stringify(start);
    const stale = applyVisualSequenceEditV2(start, 0, add(start, 2, 2, 3));
    expect(stale.ok).toBe(false);
    expect(stale.document).toBe(start);
    expect(stale.diagnostics[0]?.code).toBe("SEQUENCE_VERSION_STALE");

    refusedWith(start, { ...add(start, 2, 2, 3), slotId: slotId(2, "S1") }, "VISUAL_SLOT_ID_DUPLICATE");
    for (const collision of [
      { ...add(start, 2, 2, 3), slotId: slotId(1, "F") },
      { ...add(start, 2, 2, 3), payloadId: placeholder(2, "S1").payloadId },
    ]) {
      const session = createRowEditSessionV2(start);
      const result = session.applyVisualEdit(collision);
      expect(result.ok).toBe(false);
      expect(result.diagnostics.map((item) => item.code)).toContain("ENTITY_ID_DUPLICATE");
      expect(session.undoDepth).toBe(0);
    }
    refusedWith(start, { ...add(start, 2, 2, 3), visualType: "footage" as AddCommand["visualType"] }, "ADD_VISUAL_TYPE_INVALID");
    refusedWith(start, { ...add(start, 2, 2, 3), endTokenId: word(start, 1, 3) }, "RANGE_OUTSIDE_ROW");
    // The pure model route, not just the session wrapper, must return the
    // caller's exact document on a failed attach substep (atomic refusal).
    const failedAttach = applyVisualSequenceEditV2(start, 1, {
      ...add(start, 2, 2, 3), endTokenId: word(start, 1, 3),
    });
    expect(failedAttach.ok).toBe(false);
    expect(failedAttach.diagnostics[0]?.code).toBe("RANGE_OUTSIDE_ROW");
    expect(failedAttach.document).toBe(start);
    refusedWith(start, add(start, 2, 6, 3), "RANGE_REVERSED");
    const waiting = act(start, move("F")).document;
    refusedWith(waiting, { ...add(waiting, 2, 2, 3), slotId: slotId(1, "F") }, "VISUAL_SLOT_ID_DUPLICATE");
    expect(JSON.stringify(start)).toBe(before);
  });
});

describe("#578 move a visual to another row", () => {
  it("keeps the trim and source, lets On Camera fill the gap, and lands unattached", () => {
    const start = twoRows();
    const { document } = act(start, move("F"));
    expect(cards(document, 1)).toEqual(["OC wide 0-10"]);
    expect(cards(document, 2)).toEqual(["S1 0-5", "S2 5-10", "F unattached"]);
    expect(find(document, 2).unattachedVisuals).toEqual([{ slotId: slotId(1, "F"), payload: footage(1), version: 1 }]);
    const row = projectPrimarySequenceV2(document).rows[1]!;
    expect(row.unattached).toEqual([{ slotId: slotId(1, "F"), payloadId: footage(1).payloadId, recovery: "attach_to_words" }]);
  });

  it("moves a visual that is itself waiting for words, and leaves a cutaway inside the moved visual standing on its own", () => {
    const start = twoRows();
    const waiting = act(start, move("F")).document;
    const back = act(waiting, { kind: "move_visual_to_row", blockId: rowId(2), slotId: slotId(1, "F"), destinationBlockId: rowId(1) }).document;
    expect(cards(back, 2)).toEqual(["S1 0-5", "S2 5-10"]);
    expect(cards(back, 1)).toEqual(["OC wide 0-10", "F unattached"]);
    expect(find(back, 2).unattachedVisuals).toBeUndefined();

    const nested = documentOf([
      rowOf(1, TEN, [{ at: 0, visual: "S1" }, { at: 3, visual: "S2", in: "S1" }, { at: 6, resume: "R1", of: "S1" }]),
      rowOf(2, TEN, [{ at: 0, onCamera: "OC1" }]),
    ]);
    expect(cards(act(nested, move("S1")).document, 1)).toEqual(["OC wide 0-3", "S2 3-6", "OC wide resumes 6-10"]);
  });

  it("does not mark a visual unattached in a row with no narration", () => {
    const start = documentOf([rowOf(1, TEN, [{ at: 0, visual: "F" }, { at: 4, onCamera: "OC1" }]), wordlessRow(3, [{ at: 0, onCamera: "OC1" }])]);
    const { document } = act(start, move("F", 1, 3));
    const destination = find(document, 3);
    expect(destination.unattachedVisuals).toBeUndefined();
    expect(destination.primaryVisualSequence!.slots).toEqual([{
      id: slotId(1, "F"), kind: "content", relation: { kind: "base" }, boundaryBefore: { kind: "row_start" },
      payload: footage(1), playoutPolicy: "match_structural_interval", version: 1,
    }]);
    expect(projectPrimarySequenceV2(document).rows[1]!.unattached).toEqual([]);
    // Moving it out again gives the wordless row back its single On Camera card.
    const out = act(document, { kind: "move_visual_to_row", blockId: rowId(3), slotId: slotId(1, "F"), destinationBlockId: rowId(1) }).document;
    expect(find(out, 3).primaryVisualSequence!.slots.map((slot) => slot.kind === "content" && slot.payload.kind)).toEqual(["on_camera"]);
  });

  it("refuses On Camera, Visual Undefined, the same row, a missing row and a wordless row that already holds a picture", () => {
    const start = twoRows();
    expect(refusedWith(start, move("OC1"), "ON_CAMERA_NOT_A_VISUAL")).toContain("On Camera");
    refusedWith(start, { ...move("F"), destinationBlockId: rowId(1) }, "CROSS_ROW_REQUIRED");
    refusedWith(start, { ...move("F"), destinationBlockId: rowId(8) }, "MOVE_DESTINATION_MISSING");
    refusedWith(start, { ...move("F"), slotId: id(424242) }, "VISUAL_SLOT_MISSING");
    const taken = documentOf([rowOf(1, TEN, [{ at: 0, visual: "F" }]), wordlessRow(3, [{ at: 0, visual: "S1" }])]);
    refusedWith(taken, move("F", 1, 3), "WORDLESS_ROW_VISUAL_TAKEN");
    const undefinedOnly = documentOf([rowOf(1, TEN, [{ at: 0, visual: "S1" }]), rowOf(2, TEN, [{ at: 0, onCamera: "OC1" }])]);
    placed(undefinedOnly, 1, "S1")!.payload = { kind: "undefined", payloadId: id(909), description: "Not chosen" };
    refusedWith(undefinedOnly, move("S1"), "VISUAL_UNDEFINED_EMPTY");
  });
});

describe("#621 move whole pictures across narrated and wordless rows", () => {
  it("promotes a genuinely blank narrated row on first + Visual and appends another at 4.0 seconds", () => {
    const start = twoRows();
    const blank = rowOf(3, "one", [{ at: 0, onCamera: "OC1" }]);
    blank.text = "";
    blank.tokens = [];
    start.activeDraft.blocks.push(blank);
    const first = act(start, { kind: "add_visual_to_wordless_row", rowId: blank.id,
      payloadId: id(93010), slotId: id(93011), visualType: "onscreen_placeholder" }).document;
    const promoted = first.activeDraft.blocks[2] as VisualOnlyBlockV2;
    expect(promoted.type).toBe("visual_only");
    expect(promoted.payload.payloadId).toBe(id(93010));
    expect(promoted.visualOnlyTiming.durationOverrideMs).toBe(4000);
    const next = act(first, { kind: "add_visual_to_wordless_row", rowId: blank.id,
      payloadId: id(93012), slotId: id(93013), visualType: "need_to_find" }).document;
    expect((next.activeDraft.blocks[2] as VisualOnlyBlockV2).additionalVisuals![0].visualOnlyTiming.durationOverrideMs).toBe(4000);
    refusedWith(first, { kind: "add_visual_to_wordless_row", rowId: blank.id,
      payloadId: id(93010), slotId: id(93014), visualType: "onscreen_placeholder" }, "VISUAL_ID_DUPLICATE");
    refusedWith(first, { kind: "add_visual_to_wordless_row", rowId: blank.id,
      payloadId: id(93015), slotId: id(93016), visualType: "footage" } as unknown as RowEditCommandV2, "ROW_COMMAND_INVALID");
  });

  it("promotes an existing single picture into a mapped wordless stack without changing its original identity", () => {
    const start = twoRows();
    const blank = rowOf(3, "one", [{ at: 0, visual: "S1" }]);
    blank.text = "";
    blank.tokens = [];
    start.activeDraft.blocks.push(blank);
    const { document } = act(start, { kind: "add_visual_to_wordless_row", rowId: blank.id,
      payloadId: id(93017), slotId: id(93018), visualType: "onscreen_placeholder" });
    const converted = document.activeDraft.blocks[2] as VisualOnlyBlockV2;
    expect(converted.payload.payloadId).toBe(placeholder(3, "S1").payloadId);
    expect(converted.additionalVisuals![0].payload.payloadId).toBe(id(93017));
    expect(converted.clearedNarration!.slots.map((item) => item.id)).toEqual([slotId(3, "S1"), id(93018)]);
    const restored = createRowEditSessionV2(document).apply({ kind: "edit_narration_text",
      rowId: blank.id, startOffset: 0, endOffset: 0, insertedText: "Now", editId: id(93019) });
    expect(restored.ok, JSON.stringify(restored.diagnostics)).toBe(true);
    const narrated = restored.document.activeDraft.blocks[2] as NarrationBlockV2;
    expect(narrated.type).toBe("narration");
    expect(narrated.unattachedVisuals!.map((item) => item.slotId)).toEqual([slotId(3, "S1"), id(93018)]);
  });

  it("appends a trimmed clip and its source metadata to a real wordless row, with one Undo", () => {
    const start = twoRows();
    start.activeDraft.blocks.push(wordlessPictures(3));
    const { document } = act(start, {
      ...move("F", 1, 3), expectedDestinationRowVersion: 1,
    });
    const destination = document.activeDraft.blocks[2] as VisualOnlyBlockV2;
    expect(destination.additionalVisuals).toHaveLength(2);
    expect(destination.additionalVisuals![1]).toEqual({
      payload: standalone(footage(1)),
      visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 48, durationFrames: 96 } },
    });
    expect(cards(document, 1)).toEqual(["OC wide 0-10"]);
    refusedWith(start, move("F", 1, 3), "ROW_REVISION_STALE");
    refusedWith(start, { ...move("F", 1, 3), expectedDestinationRowVersion: 0 }, "ROW_REVISION_STALE");
    const invalid = structuredClone(start);
    delete (placed(invalid, 1, "F")!.payload as NarratedVisualPayloadV2).selectedSourceRange;
    refusedWith(invalid, { ...move("F", 1, 3), expectedDestinationRowVersion: 1 }, "WORDLESS_CLIP_TRIM_REQUIRED");
    const complete = structuredClone(start);
    placed(complete, 1, "F")!.playoutPolicy = "complete_logged_clip";
    refusedWith(complete, { ...move("F", 1, 3), expectedDestinationRowVersion: 1 }, "WORDLESS_PLAYOUT_UNSUPPORTED");
  });

  it("adds a narrated visual to a mapped wordless row without orphaning original slot IDs", () => {
    const start = twoRows();
    const mapped = wordlessPictures(3);
    mapped.clearedNarration = { id: id(93300), version: 2, slots: [
      { id: id(93301), version: 1, visualId: mapped.payload.payloadId },
      { id: id(93302), version: 1, visualId: mapped.additionalVisuals![0].payload.payloadId },
    ] };
    start.activeDraft.blocks.push(mapped);
    const { document } = act(start, { ...move("F", 1, 3), expectedDestinationRowVersion: 1 });
    const updated = document.activeDraft.blocks[2] as VisualOnlyBlockV2;
    expect(updated.clearedNarration!.slots).toHaveLength(3);
    expect(updated.clearedNarration!.slots[2]).toEqual({ id: slotId(1, "F"), version: 1,
      visualId: footage(1).payloadId });
    expect(updated.additionalVisuals![1]!.visualOnlyTiming.selectedSourceRange).toEqual({ startFrame: 48, durationFrames: 96 });
  });

  it("moves a wordless picture onto spoken words as a waiting visual, preserving trim and IDs", () => {
    const start = twoRows();
    const source = wordlessPictures(3);
    source.payload = standalone(footage(3));
    source.visualOnlyTiming = { kind: "visual_only", selectedSourceRange: { startFrame: 48, durationFrames: 96 } };
    start.activeDraft.blocks.push(source);
    const { document } = act(start, {
      kind: "move_wordless_visual", sourceRowId: source.id, payloadId: source.payload.payloadId,
      destinationRowId: rowId(2), destinationSlotId: id(91000), expectedDestinationSequenceVersion: 1,
    });
    const target = find(document, 2);
    expect(target.unattachedVisuals![0]).toEqual({ slotId: id(91000), payload: footage(3), version: 1 });
    expect((document.activeDraft.blocks[2] as VisualOnlyBlockV2).payload.payloadId).toBe(placeholder(3, "S2").payloadId);
    refusedWith(start, {
      kind: "move_wordless_visual", sourceRowId: source.id, payloadId: source.payload.payloadId,
      destinationRowId: rowId(2), destinationSlotId: id(91001), expectedDestinationSequenceVersion: 2,
    }, "SEQUENCE_VERSION_STALE");
  });

  it("moves the last wordless picture without deleting its row, using a new visible four-second placeholder", () => {
    const start = twoRows();
    const source = wordlessPictures(3);
    delete source.additionalVisuals;
    start.activeDraft.blocks.push(source, wordlessPictures(4));
    refusedWith(start, {
      kind: "move_wordless_visual", sourceRowId: source.id, payloadId: source.payload.payloadId,
      destinationRowId: rowId(4),
    }, "WORDLESS_EMPTY_SOURCE");
    const { document } = act(start, {
      kind: "move_wordless_visual", sourceRowId: source.id, payloadId: source.payload.payloadId,
      destinationRowId: rowId(4), replacementPayloadId: id(92000),
    });
    const remaining = document.activeDraft.blocks[2] as VisualOnlyBlockV2;
    const destination = document.activeDraft.blocks[3] as VisualOnlyBlockV2;
    expect(remaining.id).toBe(source.id);
    expect(remaining.payload.payloadId).toBe(id(92000));
    expect(remaining.visualOnlyTiming.durationOverrideMs).toBe(4000);
    expect(destination.additionalVisuals![1]!.payload.payloadId).toBe(source.payload.payloadId);
  });

  it("refuses moves that would orphan a cleared-narration identity map", () => {
    const start = twoRows();
    const source = wordlessPictures(3);
    source.clearedNarration = { id: id(93000), version: 1, slots: [
      { id: id(93001), version: 1, visualId: source.payload.payloadId },
      { id: id(93002), version: 1, visualId: source.additionalVisuals![0].payload.payloadId },
    ] };
    start.activeDraft.blocks.push(source);
    refusedWith(start, {
      kind: "move_wordless_visual", sourceRowId: source.id, payloadId: source.payload.payloadId,
      destinationRowId: rowId(2), expectedDestinationSequenceVersion: 1,
    }, "CLEARED_NARRATION_REVIEW_REQUIRED");
    const added = act(start, { kind: "add_visual_to_wordless_row", rowId: source.id,
      payloadId: id(93003), slotId: id(93004), visualType: "onscreen_placeholder" }).document;
    const moved = act(added, { kind: "move_wordless_visual", sourceRowId: source.id,
      payloadId: id(93003), destinationRowId: rowId(2), expectedDestinationSequenceVersion: 1 }).document;
    const map = (moved.activeDraft.blocks[2] as VisualOnlyBlockV2).clearedNarration!;
    expect(map.slots).toHaveLength(2);
    expect(find(moved, 2).unattachedVisuals![0]!.slotId).toBe(id(93004));
  });
});

describe("#578 an unattached visual and the build", () => {
  function compilerDependencies(doc: ScriptDocumentV2): CompilerDependenciesV2 {
    const row = find(doc, 2);
    const deps = JSON.parse(readFileSync(`${repo}tests/data/authoring_v2/compiler-dependencies-v2.json`, "utf8")) as CompilerDependenciesV2;
    const half = (count: number) => count % 2 === 0 ? { numerator: count / 2, denominator: 1 } : { numerator: count, denominator: 2 };
    const map = deps.narrationTimingMaps[0]!;
    map.blockId = row.id;
    map.blockRevision = row.version;
    map.textHash = digest(row.text);
    map.tokenizationVersion = "script-document/v2-frozen-tokens";
    const timed = row.tokens.map((token, index) => ({
      tokenId: token.id, startOffset: token.startOffset, endOffset: token.endOffset, quotedText: token.value,
      startTime: half(index), audibleEnd: half(index + 1), endBasis: "evidenced_audible_end" as const,
    }));
    map.tokens = [timed[0]!, ...timed.slice(1)];
    map.audio = {
      narrationAssetId: map.narrationAssetId, audioHash: map.audioHash, timingHash: map.timingHash, cacheAssetId: "a".repeat(64),
      locator: "Builds/narration/row.wav", durationSamples: row.tokens.length * 24_000, sampleRate: 48_000, channels: 1,
    };
    deps.document.textHash = map.textHash;
    deps.timeline.durationFrames = row.tokens.length * 12;
    deps.occurrenceResolutions = [];
    deps.preparedMedia = [];
    deps.tracks.push(
      { id: "placeholder", kind: "video", index: 2, name: "Placeholder" },
      { id: "presenter", kind: "video", index: 3, name: "Presenter" },
      { id: "markers", kind: "video", index: 4, name: "Markers" },
      { id: "video-child", kind: "video", index: 5, name: "Cutaways" },
    );
    deps.roles.presenterTrackId = "presenter";
    deps.roles.placeholderTrackId = "placeholder";
    deps.roles.markerTrackId = "markers";
    deps.roles.childTrackIds = ["video-child"];
    return deps;
  }

  it("leaves the unattached visual out of the build and reports why", () => {
    const moved = act(twoRows(), move("F")).document;
    // Build the receiving row on its own: the fixture supplies timing for one row.
    const doc = documentOf([find(moved, 2)]);
    const compiled = compileTimelineV2(doc, compilerDependencies(doc));
    expect(compiled.ok, JSON.stringify(compiled).slice(0, 2000)).toBe(true);
    if (!compiled.ok) return;
    const built = JSON.stringify(compiled.manifest);
    expect(built).not.toContain(slotId(1, "F"));
    expect(built).not.toContain(footage(1).payloadId);
    const reasons = compiled.report.diagnostics.filter((item) => item.code === "UNATTACHED_VISUAL");
    expect(reasons).toHaveLength(1);
    expect(reasons[0]).toMatchObject({
      severity: "warning",
      entity: { kind: "slot", id: slotId(1, "F") },
      recoveryActionKinds: ["reattach_unplaced_item"],
    });
    expect(reasons[0]!.message).toContain("left out of the build");
  });
});

describe("#578 attach to words", () => {
  const attach = (doc: ScriptDocumentV2, first: number, last: number): AttachCommand => ({
    kind: "attach_visual_to_words", blockId: rowId(2), slotId: slotId(1, "F"),
    startTokenId: word(doc, 2, first), endTokenId: word(doc, 2, last),
  });

  it("gives it the whole selection across two visuals: the earlier one ends there and the later one starts on the next word", () => {
    const waiting = act(twoRows(), move("F")).document;
    const { document } = act(waiting, attach(waiting, 3, 6));
    expect(cards(document, 2)).toEqual(["S1 0-3", "F 3-7", "S2 7-10"]);
    expect(find(document, 2).unattachedVisuals).toBeUndefined();
    expect(placed(document, 2, "F")).toBeUndefined();
    const attached = find(document, 2).primaryVisualSequence!.slots.find((slot) => slot.id === slotId(1, "F")) as ContentSlot;
    // Same card, same trim and source as before the move.
    expect(attached.payload).toEqual(footage(1));
  });

  it("becomes a cutaway that returns when the selection sits inside one visual or one On Camera passage", () => {
    const insideStill = act(documentOf([
      rowOf(1, TEN, [{ at: 0, visual: "F" }, { at: 4, onCamera: "OC1" }]),
      rowOf(2, TEN, [{ at: 0, visual: "S1" }]),
    ]), move("F")).document;
    expect(cards(act(insideStill, attach(insideStill, 3, 5)).document, 2)).toEqual(["S1 0-3", "F 3-6", "S1 resumes 6-10"]);

    const insideCamera = act(documentOf([
      rowOf(1, TEN, [{ at: 0, visual: "F" }, { at: 4, onCamera: "OC1" }]),
      rowOf(2, TEN, [{ at: 0, onCamera: "OC1" }]),
    ]), move("F")).document;
    expect(cards(act(insideCamera, attach(insideCamera, 3, 5)).document, 2)).toEqual(["OC wide 0-3", "F 3-6", "OC wide resumes 6-10"]);
  });

  it("keeps a visual it covers completely for Attach to words in its turn", () => {
    const waiting = act(twoRows(), move("F")).document;
    const { document } = act(waiting, attach(waiting, 0, 6));
    expect(cards(document, 2)).toEqual(["F 0-7", "S2 7-10", "S1 unattached"]);
  });

  it("refuses a visual that is not waiting, and a selection outside the row or reversed", () => {
    const waiting = act(twoRows(), move("F")).document;
    refusedWith(waiting, { ...attach(waiting, 3, 6), slotId: slotId(2, "S1") }, "ATTACH_VISUAL_MISSING");
    refusedWith(waiting, { ...attach(waiting, 3, 6), endTokenId: word(waiting, 1, 6) }, "RANGE_OUTSIDE_ROW");
    refusedWith(waiting, attach(waiting, 6, 3), "RANGE_REVERSED");
  });
});

describe("#578 change type", () => {
  const change = (name: string, to: ChangeCommand["to"], row = 1): ChangeCommand =>
    ({ kind: "change_visual_type", blockId: rowId(row), slotId: slotId(row, name), to });

  it("keeps the slot's words and the comment on its card, and says what the new type dropped", () => {
    const start = twoRows();
    const commented = applyCommentOperationV2(createCommentStateV2(start), 0, {
      id: "op-1", actorId: "writer", kind: "create", threadId: "thread-1", messageId: "message-1",
      body: "Is this the right shot?", mentionActorIds: [], anchor: { kind: "card", blockId: rowId(1), cardId: slotId(1, "F") },
    });
    expect(commented.ok).toBe(true);

    const { document, dropped } = act(start, change("F", { type: "still_image" }));
    expect(cards(document, 1)).toEqual(["F 0-4", "OC wide 4-10"]);
    const slot = placed(document, 1, "F")!;
    expect(slot.boundaryBefore).toEqual(placed(start, 1, "F")!.boundaryBefore);
    expect(slot.payload).toEqual({
      kind: "visual", payloadId: footage(1).payloadId, pictureKind: "unresolved_visual",
      source: { kind: "unresolved_visual", description: "Still Image to choose", wantedPictureKind: "image" },
      sourceUsage: null, audioPolicy: "mute", framingPolicy: "cover",
    });
    expect(dropped.map((item) => item.what)).toEqual(["source", "trim", "source_audio"]);
    expect(dropped[0]!.message).toBe("The media file was dropped, because Still Image does not use it.");

    const after = applyCommentOperationV2(commented.state, 1, { id: "op-2", actorId: "writer", kind: "replace_document", document });
    expect(after.ok).toBe(true);
    expect(after.state.threads[0]!.attachment).toMatchObject({ status: "attached", anchor: { kind: "card", cardId: slotId(1, "F") } });
  });

  it("carries a placeholder's words into Need to Find and back with nothing dropped", () => {
    const start = twoRows();
    const { document, dropped } = act(start, change("S1", { type: "need_to_find" }, 2));
    expect(dropped).toEqual([]);
    expect(placed(document, 2, "S1")!.payload).toMatchObject({ pictureKind: "unresolved_visual", source: { kind: "unresolved_visual", description: "S1 card" } });
    const back = act(document, change("S1", { type: "onscreen_placeholder" }, 2));
    expect(back.dropped).toEqual([]);
    expect(placed(back.document, 2, "S1")!.payload).toEqual(placeholder(2, "S1"));
  });

  it("takes new media for the chosen type, and keeps the trim only for the same footage", () => {
    const start = twoRows();
    const still = act(start, change("S1", { type: "still_image", source: { kind: "media_reference", mediaReferenceId: id(888) } }, 2));
    expect(placed(still.document, 2, "S1")!.payload).toMatchObject({ pictureKind: "image", source: { mediaReferenceId: id(888) }, sourceUsage: null });
    expect(still.dropped.map((item) => item.what)).toEqual(["source"]);

    const replaced = act(start, change("F", { type: "footage", source: { kind: "media_reference", mediaReferenceId: id(889) } }));
    expect(placed(replaced.document, 1, "F")!.payload).toMatchObject({ pictureKind: "clip", sourceUsage: { sourceInFrame: 0 }, audioPolicy: "quiet" });
    expect(replaced.dropped.map((item) => item.what)).toEqual(["source", "trim"]);
    expect(replaced.dropped[0]!.message).toBe("The media file was dropped, replaced by the new one.");
  });

  it("reaches every type on the list from footage and from a placeholder", () => {
    const types = ["footage", "still_image", "web_capture", "graphic", "onscreen_placeholder", "need_to_find", "visual_undefined", "on_camera"] as const;
    const start = twoRows();
    for (const type of types) {
      if (type !== "footage") expect(act(start, change("F", { type })).document).toBeDefined();
      if (type !== "onscreen_placeholder") expect(act(start, change("S1", { type }, 2)).document).toBeDefined();
    }
    const undefinedCard = act(start, change("F", { type: "visual_undefined" }));
    expect(cards(undefinedCard.document, 1)).toEqual(["undefined(F) 0-4", "OC wide 4-10"]);
    expect(undefinedCard.dropped.map((item) => item.what)).toEqual(["source", "trim", "source_audio"]);
    // And back out of Visual Undefined, with nothing left to drop.
    expect(act(undefinedCard.document, change("F", { type: "graphic" })).dropped).toEqual([]);
  });

  it("removes the visual when On Camera is chosen, because On Camera is what fills uncovered words", () => {
    const { document, dropped } = act(twoRows(), change("S1", { type: "on_camera" }, 2));
    expect(cards(document, 2)).toEqual(["OC wide 0-5", "S2 5-10"]);
    expect(dropped).toEqual([{ what: "visual", message: "The visual was removed, and On Camera now fills its words." }]);
  });

  it("changes the type of a visual that is waiting for words", () => {
    const waiting = act(twoRows(), move("F")).document;
    const command: ChangeCommand = { kind: "change_visual_type", blockId: rowId(2), slotId: slotId(1, "F"), to: { type: "need_to_find", description: "Harbour at dusk" } };
    const { document } = act(waiting, command);
    expect(cards(document, 2)).toEqual(["S1 0-5", "S2 5-10", "F unattached"]);
    expect(find(document, 2).unattachedVisuals![0]).toMatchObject({ version: 2, payload: { source: { description: "Harbour at dusk" } } });
    refusedWith(waiting, { ...command, to: { type: "visual_undefined" } }, "CHANGE_TYPE_NEEDS_WORDS");
  });

  it("refuses On Camera, the type it already is, and empty words", () => {
    const start = twoRows();
    refusedWith(start, change("OC1", { type: "footage" }), "ON_CAMERA_NOT_A_VISUAL");
    refusedWith(start, change("F", { type: "footage" }), "CHANGE_TYPE_UNCHANGED");
    refusedWith(start, change("S1", { type: "onscreen_placeholder" }, 2), "CHANGE_TYPE_UNCHANGED");
    refusedWith(start, change("S1", { type: "need_to_find", description: "  " }, 2), "CHANGE_TYPE_TEXT_EMPTY");
  });
});

describe("#578 delete a visual", () => {
  const remove = (name: string, row: number): VisualSequenceEditCommandV2 => ({ kind: "delete_visual", blockId: rowId(row), slotId: slotId(row, name) });

  it("lets On Camera fill the words while the row still has another visual", () => {
    const { document } = act(twoRows(), remove("S1", 2));
    expect(cards(document, 2)).toEqual(["OC wide 0-5", "S2 5-10"]);
  });

  it("leaves Visual Undefined on the words of the row's last visual", () => {
    const start = twoRows();
    const { document } = act(start, remove("F", 1));
    expect(cards(document, 1)).toEqual(["undefined(F) 0-4", "OC wide 4-10"]);
    const slot = placed(document, 1, "F")!;
    expect(slot.payload.kind).toBe("undefined");
    expect(slot.payload.kind === "undefined" && slot.payload.payloadId).not.toBe(footage(1).payloadId);
    refusedWith(document, remove("F", 1), "VISUAL_UNDEFINED_LAST");

    const twoLeft = act(start, remove("S1", 2)).document;
    expect(cards(act(twoLeft, remove("S2", 2)).document, 2)).toEqual(["OC wide 0-5", "undefined(S2) 5-10"]);
  });

  it("deletes a visual that is waiting for words, and refuses On Camera", () => {
    const waiting = act(twoRows(), move("F")).document;
    const { document } = act(waiting, { kind: "delete_visual", blockId: rowId(2), slotId: slotId(1, "F") });
    expect(cards(document, 2)).toEqual(["S1 0-5", "S2 5-10"]);
    expect(find(document, 2).unattachedVisuals).toBeUndefined();
    refusedWith(twoRows(), remove("OC1", 1), "ON_CAMERA_NOT_A_VISUAL");
  });
});

describe("#578 stash one visual", () => {
  const stash = (name: string, row: number): StashCommand => ({
    kind: "stash_visual", rowId: rowId(row), slotId: slotId(row, name), bundleId: id(60_001), stashRowId: id(60_002),
    sectionId: null, parentRowId: null, afterRowId: null,
  });

  it("creates one Stash clip with the footage's trim, and On Camera fills the row", () => {
    const { document } = act(twoRows(), stash("F", 1));
    expect(cards(document, 1)).toEqual(["OC wide 0-10"]);
    expect(document.stash).toHaveLength(1);
    expect(document.stashOutline).toEqual([{ rowId: id(60_002), kind: "clip", parentRowId: null, sectionId: null }]);
    const clip = document.stash![0]!.rows[0] as VisualOnlyBlockV2;
    expect(document.stash![0]!.rows).toHaveLength(1);
    expect(clip).toMatchObject({
      type: "visual_only", id: id(60_002),
      payload: { payloadId: footage(1).payloadId, pictureKind: "clip", source: footage(1).source, audioPolicy: "quiet", framingPolicy: "cover" },
      visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 48, durationFrames: 96 } },
    });
  });

  it("stashes a visual that is not footage as one saved row, and one that is waiting for words", () => {
    const { document } = act(twoRows(), stash("S1", 2));
    expect(cards(document, 2)).toEqual(["OC wide 0-5", "S2 5-10"]);
    expect(document.stashOutline).toEqual([{ rowId: id(60_002), kind: "row", parentRowId: null, sectionId: null }]);
    expect((document.stash![0]!.rows[0] as VisualOnlyBlockV2).payload).toMatchObject({ pictureKind: "intentional_placeholder", source: { text: "S1 card" } });

    const waiting = act(twoRows(), move("F")).document;
    const stashed = act(waiting, { ...stash("F", 2), slotId: slotId(1, "F") }).document;
    expect(cards(stashed, 2)).toEqual(["S1 0-5", "S2 5-10"]);
    expect(stashed.stash).toHaveLength(1);
  });

  it("is refused for On Camera, for footage with no chosen length, and for IDs already in use", () => {
    const start = twoRows();
    expect(refusedWith(start, stash("OC1", 1), "ON_CAMERA_NOT_A_VISUAL")).toContain("On Camera");
    refusedWith(start, { ...stash("F", 1), stashRowId: rowId(2) }, "ROW_ID_DUPLICATE");
    refusedWith(start, { ...stash("F", 1), sectionId: id(31337) }, "STASH_SECTION_NOT_FOUND");
    const untrimmed = twoRows();
    delete (placed(untrimmed, 1, "F")!.payload as NarratedVisualPayloadV2).selectedSourceRange;
    refusedWith(untrimmed, stash("F", 1), "STASH_VISUAL_TRIM_REQUIRED");
  });
});

describe("#588 a name belongs to one visual placement", () => {
  it("keeps a single clip's name/source/trim through move, waiting, attach, Stash, reload and return", () => {
    const duplicate = rowOf(4, TEN, [{ at: 0, visual: "F" }]);
    const start = twoRows();
    start.activeDraft.blocks.push(duplicate);
    // The two placements intentionally refer to the same media, but have different payload IDs.
    expect(footage(1).source).toEqual(footage(4).source);
    const name = "Window angle ✨";
    const renamed = act(start, {
      kind: "rename_visual_placement", rowId: rowId(1), payloadId: footage(1).payloadId, name,
    }).document;
    expect((placed(renamed, 1, "F")!.payload as NarratedVisualPayloadV2).displayName).toBe(name);
    expect(placed(renamed, 4, "F")!.payload).toEqual(footage(4));

    const moved = act(renamed, move("F")).document;
    const named = { ...footage(1), displayName: name };
    expect(find(moved, 2).unattachedVisuals![0]!.payload).toEqual(named);
    expect(placed(moved, 4, "F")!.payload).toEqual(footage(4));
    const attached = act(moved, {
      kind: "attach_visual_to_words", blockId: rowId(2), slotId: slotId(1, "F"),
      startTokenId: word(moved, 2, 3), endTokenId: word(moved, 2, 6),
    }).document;
    const placedClip = find(attached, 2).primaryVisualSequence!.slots.find((slot) => slot.id === slotId(1, "F")) as ContentSlot;
    expect(placedClip.payload).toEqual(named);

    const stashed = act(attached, {
      kind: "stash_visual", rowId: rowId(2), slotId: slotId(1, "F"),
      bundleId: id(60_001), stashRowId: id(60_002), sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    const saved = stashed.stash![0]!.rows[0] as VisualOnlyBlockV2;
    expect(saved.payload).toEqual({
      kind: "visual", payloadId: named.payloadId, pictureKind: "clip", source: named.source,
      audioPolicy: "quiet", framingPolicy: "cover", displayName: name,
    });
    expect(saved.visualOnlyTiming.selectedSourceRange).toEqual(named.selectedSourceRange);
    const loaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(stashed));
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    const returned = act(loaded.document, {
      kind: "place_stash_rows", rowIds: [saved.id],
      destination: { sectionId: null, afterRowId: rowId(4), beforeRowId: null },
    }).document;
    expect(returned.activeDraft.blocks.at(-1)).toMatchObject({ id: saved.id, payload: saved.payload });
    expect(placed(returned, 4, "F")!.payload).toEqual(footage(4));
  });

  it("keeps a still's placement name when stashed without changing its source", () => {
    const start = documentOf([rowOf(1, TEN, [{ at: 0, visual: "F" }])]);
    const base = placed(start, 1, "F")!.payload as NarratedVisualPayloadV2;
    base.pictureKind = "image";
    base.audioPolicy = "mute";
    base.sourceUsage = null;
    delete base.selectedSourceRange;
    const renamed = act(start, {
      kind: "rename_visual_placement", rowId: rowId(1), payloadId: base.payloadId, name: "Low light still",
    }).document;
    const stashed = act(renamed, {
      kind: "stash_visual", rowId: rowId(1), slotId: slotId(1, "F"),
      bundleId: id(60_001), stashRowId: id(60_002), sectionId: null, parentRowId: null, afterRowId: null,
    }).document;
    const clip = stashed.stash![0]!.rows[0] as VisualOnlyBlockV2;
    expect(clip.payload).toMatchObject({
      payloadId: base.payloadId, pictureKind: "image", displayName: "Low light still", source: base.source,
    });
    expect(clip.visualOnlyTiming.selectedSourceRange).toBeUndefined();
    const returned = act(stashed, {
      kind: "place_stash_rows", rowIds: [clip.id],
      destination: { sectionId: null, afterRowId: rowId(1), beforeRowId: null },
    }).document;
    expect((returned.activeDraft.blocks[1] as VisualOnlyBlockV2).payload).toEqual(clip.payload);
  });

  it("preserves names on a source-preserving footage trim/retype, but clears them for different media or type", () => {
    const named = act(twoRows(), {
      kind: "rename_visual_placement", rowId: rowId(1), payloadId: footage(1).payloadId, name: "Close detail",
    }).document;
    const changedTrim = act(named, {
      kind: "change_visual_type", blockId: rowId(1), slotId: slotId(1, "F"),
      to: { type: "footage", source: { kind: "media_reference", mediaReferenceId: MEDIA }, sourceInFrame: 64 },
    }).document;
    expect(placed(changedTrim, 1, "F")!.payload).toMatchObject({
      pictureKind: "clip", displayName: "Close detail", sourceUsage: { sourceInFrame: 64 },
    });
    const replaced = act(changedTrim, {
      kind: "change_visual_type", blockId: rowId(1), slotId: slotId(1, "F"),
      to: { type: "footage", source: { kind: "media_reference", mediaReferenceId: id(889) } },
    }).document;
    expect(placed(replaced, 1, "F")!.payload).not.toHaveProperty("displayName");
    const unsupported = act(named, {
      kind: "change_visual_type", blockId: rowId(1), slotId: slotId(1, "F"), to: { type: "graphic" },
    }).document;
    expect(placed(unsupported, 1, "F")!.payload).not.toHaveProperty("displayName");
  });
});
