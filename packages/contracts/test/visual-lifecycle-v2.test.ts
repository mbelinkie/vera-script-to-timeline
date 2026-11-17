import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
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
import type { RowEditCommandV2, VisualSequenceEditCommandV2 } from "../src/authoring-v2.js";

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
const NAMES = ["F", "S1", "S2", "S3", "OC1", "OC2", "R1"];
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
  const visual = isVisualCommand(command);
  const result = visual ? session.applyVisualEdit(command) : session.apply(command);
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
  const dropped = "evidence" in result ? result.evidence?.dropped ?? [] : [];
  return { document: result.document, dropped };
}

function isVisualCommand(command: VisualSequenceEditCommandV2 | RowEditCommandV2): command is VisualSequenceEditCommandV2 {
  return ["move_visual_to_row", "attach_visual_to_words", "change_visual_type", "delete_visual"].includes(command.kind);
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

const move = (name: string, from = 1, to = 2): VisualSequenceEditCommandV2 =>
  ({ kind: "move_visual_to_row", blockId: rowId(from), slotId: slotId(from, name), destinationBlockId: rowId(to) });

/** Row 1 opens on footage then On Camera; row 2 is two stills meeting at word 5. */
function twoRows(): ScriptDocumentV2 {
  return documentOf([
    rowOf(1, TEN, [{ at: 0, visual: "F" }, { at: 4, onCamera: "OC1" }]),
    rowOf(2, TEN, [{ at: 0, visual: "S1" }, { at: 5, visual: "S2" }]),
  ]);
}

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
  const attach = (doc: ScriptDocumentV2, first: number, last: number): VisualSequenceEditCommandV2 => ({
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
  const change = (name: string, to: Extract<VisualSequenceEditCommandV2, { kind: "change_visual_type" }>["to"], row = 1): VisualSequenceEditCommandV2 =>
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
    const command: VisualSequenceEditCommandV2 = { kind: "change_visual_type", blockId: rowId(2), slotId: slotId(1, "F"), to: { type: "need_to_find", description: "Harbour at dusk" } };
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
  const stash = (name: string, row: number): RowEditCommandV2 => ({
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
    const stashed = act(waiting, { ...stash("F", 2), slotId: slotId(1, "F") } as RowEditCommandV2).document;
    expect(cards(stashed, 2)).toEqual(["S1 0-5", "S2 5-10"]);
    expect(stashed.stash).toHaveLength(1);
  });

  it("is refused for On Camera, for footage with no chosen length, and for IDs already in use", () => {
    const start = twoRows();
    expect(refusedWith(start, stash("OC1", 1), "ON_CAMERA_NOT_A_VISUAL")).toContain("On Camera");
    refusedWith(start, { ...stash("F", 1), stashRowId: rowId(2) } as RowEditCommandV2, "ROW_ID_DUPLICATE");
    refusedWith(start, { ...stash("F", 1), sectionId: id(31337) } as RowEditCommandV2, "STASH_SECTION_NOT_FOUND");
    const untrimmed = twoRows();
    delete (placed(untrimmed, 1, "F")!.payload as NarratedVisualPayloadV2).selectedSourceRange;
    refusedWith(untrimmed, stash("F", 1), "STASH_VISUAL_TRIM_REQUIRED");
  });
});
