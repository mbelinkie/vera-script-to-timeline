import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  applyVisualSequenceEditV2,
  createRowEditSessionV2,
  projectPrimarySequenceV2,
  validateScriptDocumentV2,
} from "@vera/contracts/authoring-v2";
import { compileTimelineV2 } from "../src/compiler-core-v2.js";
import type { CompilerDependenciesV2, ContentSlot, NarrationBlockV2, ReturnSlot, ScriptDocumentV2 } from "@vera/contracts/v2";
import type { OnCameraFramingV2, VisualSequenceEditCommandV2 } from "../src/authoring-v2.js";

/**
 * #577: On Camera fills the narration no visual covers (S03 D193).
 *
 * Sample rows are shortened from the archived r29 prototype
 * (docs/prototypes/issue-125/r29): each keeps the row's opening words and its
 * picture order. Word timing is a fixture: every word lasts half a second.
 */

const repo = fileURLToPath(new URL("../../../", import.meta.url));
const id = (value: number): string => `00000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;
const digest = (value: string): string => `sha256:${createHash("sha256").update(value, "utf8").digest("hex")}`;
const ROW = id(6);
const SEQUENCE = id(9);
const FRAMES_PER_WORD = 12;

/** Readable slot names for assertions: S1 is the row's first still, OC1 its first stored On Camera slot. */
const SLOT = { S1: id(101), S2: id(102), S3: id(103), OC1: id(201), OC2: id(202), R1: id(301), R2: id(302), ADD: id(401) } as const;
type SlotName = keyof typeof SLOT;
const nameOf = (slotId: string): string =>
  (Object.entries(SLOT).find(([, value]) => value === slotId)?.[0]) ?? `new:${slotId.slice(0, 8)}`;

type Piece =
  | { at: number; still: "S1" | "S2" | "S3"; in?: SlotName }
  | { at: number; onCamera: "OC1" | "OC2"; framing?: OnCameraFramingV2 }
  | { at: number; resume: "R1" | "R2"; of: SlotName };

function rowOf(text: string, pieces: Piece[]): NarrationBlockV2 {
  let offset = 0;
  const tokens = text.split(" ").map((value, index) => {
    const token = { id: id(1000 + index), value, startOffset: offset, endOffset: offset + value.length };
    offset += value.length + 1;
    return token;
  });
  const anchor = (at: number) => ({
    blockId: ROW, tokenId: tokens[at]!.id, affinity: "before" as const, quotedWord: tokens[at]!.value, anchorVersion: 1,
  });
  const slots = pieces.map((piece, index): ContentSlot | ReturnSlot => {
    if ("resume" in piece) {
      return { id: SLOT[piece.resume], kind: "return", parentSlotId: SLOT[piece.of], inpoint: anchor(piece.at), version: 1 };
    }
    const name = "still" in piece ? piece.still : piece.onCamera;
    return {
      id: SLOT[name],
      kind: "content",
      relation: "still" in piece && piece.in
        ? { kind: "cutaway", parentSlotId: SLOT[piece.in] }
        : { kind: index === 0 ? "base" : "sequential" },
      boundaryBefore: index === 0 ? { kind: "row_start" } : { kind: "spoken_word", anchor: anchor(piece.at) },
      payload: "still" in piece
        ? {
            kind: "visual", payloadId: id(Number.parseInt(SLOT[name].slice(-3), 16) + 0x1000),
            pictureKind: "intentional_placeholder", source: { kind: "intentional_placeholder", text: name },
            sourceUsage: null, audioPolicy: "mute", framingPolicy: "contain",
          }
        : { kind: "on_camera", presenterChoiceId: null, ...(piece.framing ? { framing: piece.framing } : {}) },
      playoutPolicy: "match_structural_interval",
      version: 1,
    };
  });
  return {
    type: "narration", id: ROW, orderKey: "a0", text, tokens: [tokens[0]!, ...tokens.slice(1)],
    primaryVisualSequence: { id: SEQUENCE, slots, version: 1 },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
}

function documentOf(row: NarrationBlockV2): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "On Camera coverage",
    activeDraft: { blocks: [row], supportingItems: [] }, ideaOutline: [], extras: [], liveHeadSequence: 0,
    liveStateVector: "", liveContentHash: `sha256:${"a".repeat(64)}`,
  };
}

const rowIn = (doc: ScriptDocumentV2): NarrationBlockV2 => doc.activeDraft.blocks[0] as NarrationBlockV2;
const wordId = (doc: ScriptDocumentV2, index: number): string => rowIn(doc).tokens[index]!.id;
const storedSlots = (doc: ScriptDocumentV2): (ContentSlot | ReturnSlot)[] => rowIn(doc).primaryVisualSequence!.slots;
const stored = (doc: ScriptDocumentV2, slot: SlotName): ContentSlot | ReturnSlot | undefined =>
  storedSlots(doc).find((candidate) => candidate.id === SLOT[slot]);

function setRange(slot: SlotName, doc: ScriptDocumentV2, first: number, last: number): VisualSequenceEditCommandV2 {
  return { kind: "set_visual_range", blockId: ROW, slotId: SLOT[slot], startTokenId: wordId(doc, first), endTokenId: wordId(doc, last) };
}

function addOnSelection(doc: ScriptDocumentV2, first: number, last: number): VisualSequenceEditCommandV2 {
  return {
    kind: "add_visual_on_selection", blockId: ROW, slotId: SLOT.ADD, payloadId: id(402),
    startTokenId: wordId(doc, first), endTokenId: wordId(doc, last), visualType: "onscreen_placeholder",
  };
}

/** The card stack as text: "S1 0-9", "OC wide 9-18", "OC wide resumes 12-20", "S1 resumes 14-20", "S2 unattached". */
function cards(doc: ScriptDocumentV2): string[] {
  return projectPrimarySequenceV2(doc).rows[0]!.cards.map((card) => {
    if (card.kind === "unattached_visual") return `${nameOf(card.slotId)} unattached`;
    const label = card.kind === "on_camera" ? `OC ${card.framing}` : nameOf(card.slotId);
    return `${label}${card.compact ? " resumes" : ""} ${card.startTokenIndex}-${card.endTokenIndexExclusive}`;
  });
}

function compilerDependencies(doc: ScriptDocumentV2): CompilerDependenciesV2 {
  const row = rowIn(doc);
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
  deps.timeline.durationFrames = row.tokens.length * FRAMES_PER_WORD;
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

/** The picture the compiled edit shows on each word: a cutaway sits over the visual it interrupts. */
function compiledCoverage(doc: ScriptDocumentV2): string[] {
  const compiled = compileTimelineV2(doc, compilerDependencies(doc));
  expect(compiled.ok, JSON.stringify(compiled).slice(0, 2000)).toBe(true);
  if (!compiled.ok) return [];
  const pictures = compiled.manifest.events.filter((event) => event.provenance.slotId && (event.kind === "placeholder" || event.kind === "primary_visual"));
  return rowIn(doc).tokens.map((_, index) => {
    const frame = index * FRAMES_PER_WORD;
    const showing = pictures.filter((event) => event.recordRange.startFrame <= frame && frame < event.recordRange.endFrame);
    const top = showing.find((event) => event.trackRole === "child") ?? showing[0];
    return top?.provenance.slotId ?? "nothing";
  });
}

/**
 * One coherent sequence: the words, the brackets, the card stack and the
 * compiled edit all describe the same pictures, and every word has exactly one.
 */
function expectCoherent(doc: ScriptDocumentV2): void {
  const validation = validateScriptDocumentV2(doc);
  expect(validation.diagnostics).toEqual([]);
  const row = projectPrimarySequenceV2(doc).rows[0]!;
  expect(row.renderable).toBe(true);
  const perWord = row.tokens.map((token) => token.primarySlotId);
  expect(perWord.every((slotId) => slotId !== null)).toBe(true);

  // Card connectors tile the row in order, with no gap and no overlap.
  const attached = row.cards.filter((card) => card.kind !== "unattached_visual");
  let cursor = 0;
  for (const card of attached) {
    expect(card.startTokenIndex).toBe(cursor);
    expect(card.endTokenIndexExclusive!).toBeGreaterThan(cursor);
    cursor = card.endTokenIndexExclusive!;
  }
  expect(cursor).toBe(row.tokens.length);

  // One card per On Camera passage, the first is never compact, and On Camera has no brackets or recovery.
  const onCamera = attached.filter((card) => card.kind === "on_camera");
  expect(attached.some((card, index) => card.kind === "on_camera" && attached[index + 1]?.kind === "on_camera")).toBe(false);
  expect(onCamera[0]?.compact ?? false).toBe(false);
  expect(row.cards.every((card) => card.kind === "unattached_visual" ? card.recovery === "attach_to_words" : card.recovery === null)).toBe(true);
  const onCameraSlotIds = new Set(storedSlots(doc).flatMap((slot) => slot.kind === "content" && slot.payload.kind === "on_camera" ? [slot.id] : []));
  expect(row.brackets.some((bracket) => onCameraSlotIds.has(bracket.slotId))).toBe(false);
  expect(row.unattached.some((item) => onCameraSlotIds.has(item.slotId))).toBe(false);

  // Brackets enclose exactly the words between a visual's first and last appearance.
  for (const bracket of row.brackets) {
    expect(bracket.startTokenIndex).toBe(perWord.indexOf(bracket.slotId));
    expect(bracket.endTokenIndexExclusive).toBe(perWord.lastIndexOf(bracket.slotId) + 1);
    expect(bracket.lastTokenId).toBe(row.tokens[bracket.endTokenIndexExclusive - 1]!.tokenId);
  }
  const placed = storedSlots(doc).flatMap((slot) => slot.kind === "content" && slot.payload.kind !== "on_camera" ? [slot.id] : []);
  expect(row.brackets.map((bracket) => bracket.slotId).sort()).toEqual([...placed].sort());

  // The compiled edit shows the same slot on every word as the script does.
  expect(compiledCoverage(doc)).toEqual(perWord);
}

function edit(doc: ScriptDocumentV2, command: VisualSequenceEditCommandV2): ScriptDocumentV2 {
  const result = applyVisualSequenceEditV2(doc, rowIn(doc).primaryVisualSequence!.version, command);
  expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
  expectCoherent(result.document);
  return result.document;
}

function expectRefused(doc: ScriptDocumentV2, command: VisualSequenceEditCommandV2, code: string): void {
  const before = JSON.stringify(doc);
  const session = createRowEditSessionV2(doc);
  const sessionBefore = JSON.stringify(session.document);
  const result = session.applyVisualEdit(command);
  expect(result.ok).toBe(false);
  expect(result.diagnostics.map((item) => item.code)).toEqual([code]);
  expect(result.diagnostics[0]!.message.length).toBeGreaterThan(20);
  expect(JSON.stringify(doc)).toBe(before);
  expect(JSON.stringify(session.document)).toBe(sessionBefore);
  expect(session.undoDepth).toBe(0);
}

// "A folded letter sat inside the sleeve…": still, On Camera, still.
function foldedLetter(): ScriptDocumentV2 {
  return documentOf(rowOf(
    "A folded letter sat inside the sleeve for months. I think this was meant for whoever came next. The archivist placed a blank card beside it.",
    [{ at: 0, still: "S1" }, { at: 9, onCamera: "OC1", framing: "tight" }, { at: 18, still: "S2" }],
  ));
}

// "The amber lantern was never…": one still over the whole row.
function amberLantern(): ScriptDocumentV2 {
  return documentOf(rowOf(
    "The amber lantern was never the brightest object in the room, but people kept gathering around it.",
    [{ at: 0, still: "S1" }],
  ));
}

// "Paper lanterns were folded…": still, On Camera, still.
function paperLanterns(): ScriptDocumentV2 {
  return documentOf(rowOf(
    "Paper lanterns were folded from ordinary sheets. I think a blank lantern can still hold a wish. The table looked empty afterward.",
    [{ at: 0, still: "S1" }, { at: 7, onCamera: "OC1" }, { at: 17, still: "S2" }],
  ));
}

// "This coat belonged to a person…": On Camera, the raincoat still as a cutaway, On Camera again.
function raincoat(): ScriptDocumentV2 {
  return documentOf(rowOf(
    "This coat belonged to a careful person. The fabric has been patched with green thread. I think the repair matters.",
    [{ at: 0, onCamera: "OC1" }, { at: 7, still: "S1", in: "OC1" }, { at: 15, resume: "R1", of: "OC1" }],
  ));
}

describe("#67 Add visual keeps coherent On Camera and cutaway coverage", () => {
  it("splits Amber Lantern's still into a genuine cutaway and one return, without breaking the build", () => {
    const start = amberLantern();
    const session = createRowEditSessionV2(start);
    const result = session.applyVisualEdit(addOnSelection(start, 4, 5));
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(cards(result.document)).toEqual(["S1 0-4", "ADD 4-6", `S1 resumes 6-${rowIn(start).tokens.length}`]);
    expectCoherent(result.document);
    expect(rowIn(result.document).primaryVisualSequence?.version).toBe(2);
    expect(session.undoDepth).toBe(1);
    expect(session.undo().document.activeDraft.blocks).toEqual(start.activeDraft.blocks);
  });

  it("cuts into Folded Letter's Tight On Camera passage and preserves its real return", () => {
    const start = foldedLetter();
    const result = edit(start, addOnSelection(start, 10, 12));
    expect(cards(result)).toEqual([
      "S1 0-9", "OC tight 9-10", "ADD 10-13", "OC tight resumes 13-18",
      `S2 18-${rowIn(start).tokens.length}`,
    ]);
    expect(stored(result, "OC1")).toMatchObject({ payload: { kind: "on_camera", framing: "tight" } });
  });

  it("extends over the join of two existing cues without a phantom resume or an extra version", () => {
    const start = foldedLetter();
    const result = edit(start, addOnSelection(start, 8, 10));
    expect(cards(result)).toEqual([
      "S1 0-8", "ADD 8-11", "OC tight 11-18", `S2 18-${rowIn(start).tokens.length}`,
    ]);
    expect(rowIn(result).primaryVisualSequence?.version).toBe(2);
  });
});

// "The recipe card was found…": On Camera, then Still Image 1 with Still Image 2 cutting away inside it.
function recipeCard(): ScriptDocumentV2 {
  return documentOf(rowOf(
    "The recipe card was found beneath envelopes. The cook left the measurement to whoever was in the room. Nobody prepared it exactly.",
    [{ at: 0, onCamera: "OC1" }, { at: 7, still: "S1" }, { at: 11, still: "S2", in: "S1" }, { at: 15, resume: "R1", of: "S1" }],
  ));
}

describe("#577 Folded Letter: moving the first still's end", () => {
  it("moves the end by one word and by several, both directions, touching the neighbour only where its words are covered", () => {
    const start = foldedLetter();
    expectCoherent(start);
    expect(cards(start)).toEqual(["S1 0-9", "OC tight 9-18", "S2 18-26"]);
    const cases: { last: number; expected: string[]; neighbourMoves: boolean }[] = [
      { last: 7, expected: ["S1 0-8", "OC tight 8-18", "S2 18-26"], neighbourMoves: false },
      { last: 4, expected: ["S1 0-5", "OC tight 5-18", "S2 18-26"], neighbourMoves: false },
      { last: 9, expected: ["S1 0-10", "OC tight 10-18", "S2 18-26"], neighbourMoves: false },
      { last: 13, expected: ["S1 0-14", "OC tight 14-18", "S2 18-26"], neighbourMoves: false },
      // Onto the last On Camera word: the passage is removed, not left as one word (D192).
      { last: 17, expected: ["S1 0-18", "S2 18-26"], neighbourMoves: false },
      // Past On Camera into the next still: only its covered words are taken.
      { last: 20, expected: ["S1 0-21", "S2 21-26"], neighbourMoves: true },
    ];
    for (const item of cases) {
      const session = createRowEditSessionV2(start);
      const result = session.applyVisualEdit(setRange("S1", start, 0, item.last));
      expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
      expectCoherent(result.document);
      expect(cards(result.document)).toEqual(item.expected);
      expect(JSON.stringify(stored(result.document, "S2")) === JSON.stringify(stored(start, "S2"))).toBe(!item.neighbourMoves);
      // Exactly one Undo entry, and it restores every range, the passage, its framing and the card order.
      expect(session.undoDepth).toBe(1);
      const undone = session.undo();
      expect(undone.ok).toBe(true);
      expect(session.undoDepth).toBe(0);
      expect(cards(undone.document)).toEqual(cards(start));
      expect(rowIn(undone.document)).toEqual(rowIn(start));
    }
  });

  it("keeps the surviving passage's framing and its slot", () => {
    const narrowed = edit(foldedLetter(), setRange("S1", foldedLetter(), 0, 12));
    expect(stored(narrowed, "OC1")).toMatchObject({ payload: { kind: "on_camera", framing: "tight" } });
    expect(storedSlots(narrowed).map((slot) => nameOf(slot.id))).toEqual(["S1", "OC1", "S2"]);
  });
});

describe("#577 Amber Lantern and Paper Lanterns: a confirmed Set range", () => {
  it("changes the stored range, the cards and the compiled coverage together", () => {
    const start = amberLantern();
    const session = createRowEditSessionV2(start);
    const result = session.applyVisualEdit(setRange("S1", start, 3, 8));
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expectCoherent(result.document);
    // The freed words are On Camera: a full card first, then a genuine return after the still.
    expect(cards(result.document)).toEqual(["OC wide 0-3", "S1 3-9", "OC wide resumes 9-17"]);
    expect(projectPrimarySequenceV2(result.document).rows[0]!.brackets).toMatchObject([
      { slotId: SLOT.S1, startTokenId: wordId(start, 3), lastTokenId: wordId(start, 8) },
    ]);
    expect(session.undoDepth).toBe(1);
    // Confirming the same words again changes nothing and adds no Undo entry.
    const again = session.applyVisualEdit(setRange("S1", result.document, 3, 8));
    expect(again.ok).toBe(false);
    expect(again.diagnostics[0]!.code).toBe("RANGE_UNCHANGED");
    expect(session.undoDepth).toBe(1);
    expect(rowIn(session.document)).toEqual(rowIn(result.document));
    expect(rowIn(session.undo().document)).toEqual(rowIn(start));
  });

  it("gives the second still a selection that reaches back into On Camera", () => {
    const start = paperLanterns();
    expectCoherent(start);
    const moved = edit(start, setRange("S2", start, 12, 18));
    expect(cards(moved)).toEqual(["S1 0-7", "OC wide 7-12", "S2 12-19", "OC wide resumes 19-22"]);
    expectRefused(moved, setRange("S2", moved, 12, 18), "RANGE_UNCHANGED");
  });

  it("gives a still a selection that covers its neighbour's first words", () => {
    const start = paperLanterns();
    const moved = edit(start, setRange("S1", start, 3, 18));
    expect(cards(moved)).toEqual(["OC wide 0-3", "S1 3-19", "S2 19-22"]);
  });
});

describe("#577 derived coverage and Attach to words recovery", () => {
  it("keeps a still that loses every word for Attach to words, and never offers that for On Camera", () => {
    const start = foldedLetter();
    const session = createRowEditSessionV2(start);
    const result = session.applyVisualEdit(setRange("S1", start, 0, 25));
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expectCoherent(result.document);
    expect(cards(result.document)).toEqual(["S1 0-26", "S2 unattached"]);
    expect(projectPrimarySequenceV2(result.document).rows[0]!.unattached).toEqual([
      { slotId: SLOT.S2, payloadId: rowIn(result.document).unattachedVisuals![0]!.payload.payloadId, recovery: "attach_to_words" },
    ]);
    expect(rowIn(result.document).unattachedVisuals).toHaveLength(1);
    expect(session.undoDepth).toBe(1);
    expect(rowIn(session.undo().document)).toEqual(rowIn(start));
  });

  it("stores Wide or Tight per passage as the only On Camera choice, as one Undo entry", () => {
    const start = paperLanterns();
    const session = createRowEditSessionV2(start);
    const result = session.applyVisualEdit({ kind: "set_on_camera_framing", blockId: ROW, slotId: SLOT.OC1, framing: "tight" });
    expect(result.ok).toBe(true);
    expectCoherent(result.document);
    expect(cards(result.document)).toEqual(["S1 0-7", "OC tight 7-17", "S2 17-22"]);
    expect(session.undoDepth).toBe(1);
    expect(rowIn(session.undo().document)).toEqual(rowIn(start));
    expectRefused(start, { kind: "set_on_camera_framing", blockId: ROW, slotId: SLOT.OC1, framing: "wide" }, "FRAMING_UNCHANGED");
    expectRefused(start, { kind: "set_on_camera_framing", blockId: ROW, slotId: SLOT.S1, framing: "tight" }, "FRAMING_SLOT_MISSING");
  });

  it("returns freed words to the shot already used in the row", () => {
    const start = documentOf(rowOf(
      "One two three four five six seven eight nine ten",
      [{ at: 0, onCamera: "OC1", framing: "tight" }, { at: 4, still: "S1" }],
    ));
    const shortened = edit(start, setRange("S1", start, 4, 6));
    // Shortening the last visual hands the freed words back as a real return to the same shot (D190).
    expect(cards(shortened)).toEqual(["OC tight 0-4", "S1 4-7", "OC tight resumes 7-10"]);
  });
});

describe("#577 one card per On Camera passage", () => {
  it("shows adjacent On Camera slots from an older document as one card, and the authored framing wins", () => {
    const legacy = documentOf(rowOf(
      "One two three four five six seven eight nine ten",
      [{ at: 0, onCamera: "OC1" }, { at: 3, onCamera: "OC2", framing: "tight" }, { at: 7, still: "S1" }],
    ));
    expect(validateScriptDocumentV2(legacy).diagnostics).toEqual([]);
    expect(cards(legacy)).toEqual(["OC tight 0-7", "S1 7-10"]);
    // The next edit in the row stores it as one passage.
    const edited = edit(legacy, setRange("S1", legacy, 8, 9));
    expect(cards(edited)).toEqual(["OC tight 0-8", "S1 8-10"]);
    expect(storedSlots(edited).map((slot) => nameOf(slot.id))).toEqual(["OC2", "S1"]);
  });

  it("makes the first On Camera a full card even after a still, and compact only for a real return to the same shot", () => {
    const afterStill = documentOf(rowOf("One two three four five six", [{ at: 0, still: "S1" }, { at: 3, onCamera: "OC1" }]));
    expectCoherent(afterStill);
    expect(cards(afterStill)).toEqual(["S1 0-3", "OC wide 3-6"]);

    // The same shot returning as a separate stored slot is still a return.
    const sameShot = documentOf(rowOf(
      "One two three four five six seven eight nine",
      [{ at: 0, onCamera: "OC1" }, { at: 3, still: "S1" }, { at: 6, onCamera: "OC2" }],
    ));
    expectCoherent(sameShot);
    expect(cards(sameShot)).toEqual(["OC wide 0-3", "S1 3-6", "OC wide resumes 6-9"]);

    // A different framing is a different shot, so it gets a full card.
    const otherShot = documentOf(rowOf(
      "One two three four five six seven eight nine",
      [{ at: 0, onCamera: "OC1" }, { at: 3, still: "S1" }, { at: 6, onCamera: "OC2", framing: "tight" }],
    ));
    expectCoherent(otherShot);
    expect(cards(otherShot)).toEqual(["OC wide 0-3", "S1 3-6", "OC tight 6-9"]);
  });
});

describe("#577 stale returns", () => {
  it("drops the return when the earlier On Camera appearance is removed, promoting the passage to a full card", () => {
    const start = raincoat();
    expectCoherent(start);
    expect(cards(start)).toEqual(["OC wide 0-7", "S1 7-15", "OC wide resumes 15-20"]);
    const covered = edit(start, setRange("S1", start, 0, 14));
    expect(cards(covered)).toEqual(["S1 0-15", "OC wide 15-20"]);
    expect(storedSlots(covered).some((slot) => slot.kind === "return")).toBe(false);
    expect(storedSlots(covered).map((slot) => nameOf(slot.id))).toEqual(["S1", "OC1"]);
  });

  it("drops the return when the intervening cutaway is removed", () => {
    const start = raincoat();
    const removed = edit(start, { kind: "delete_slot", blockId: ROW, slotId: SLOT.S1 });
    expect(cards(removed)).toEqual(["OC wide 0-20"]);
    expect(storedSlots(removed).map((slot) => nameOf(slot.id))).toEqual(["OC1"]);
  });

  it("drops the return when the cutaway is extended over the words it returned to", () => {
    const start = raincoat();
    const extended = edit(start, setRange("S1", start, 7, 19));
    expect(cards(extended)).toEqual(["OC wide 0-7", "S1 7-20"]);
    expect(storedSlots(extended).some((slot) => slot.kind === "return")).toBe(false);
  });

  it("merges On Camera when the still between two passages is removed", () => {
    const start = documentOf(rowOf(
      "One two three four five six seven eight nine",
      [{ at: 0, onCamera: "OC1", framing: "tight" }, { at: 3, still: "S1" }, { at: 6, onCamera: "OC2" }],
    ));
    const removed = edit(start, { kind: "delete_slot", blockId: ROW, slotId: SLOT.S1 });
    expect(cards(removed)).toEqual(["OC tight 0-9"]);
    expect(storedSlots(removed)).toHaveLength(1);
  });

  it("recipe card: shortening Still Image 1 to end before Still Image 2 leaves no 'Still Image 1 resumes'", () => {
    const start = recipeCard();
    expectCoherent(start);
    expect(cards(start)).toEqual(["OC wide 0-7", "S1 7-11", "S2 11-15", "S1 resumes 15-22"]);
    const shortened = edit(start, setRange("S1", start, 7, 8));
    // Still Image 2 stays where it is and the freed words are On Camera.
    expect(cards(shortened)).toEqual(["OC wide 0-7", "S1 7-9", "OC wide resumes 9-11", "S2 11-15", "OC wide resumes 15-22"]);
    expect(storedSlots(shortened).some((slot) => slot.kind === "return" && slot.parentSlotId === SLOT.S1)).toBe(false);
    expect(JSON.stringify(stored(shortened, "S2")).includes(wordId(start, 11))).toBe(true);
  });

  it("recipe card: a cutaway moved inside Still Image 1's words still resumes Still Image 1", () => {
    const start = recipeCard();
    const moved = edit(start, setRange("S2", start, 10, 16));
    expect(cards(moved)).toEqual(["OC wide 0-7", "S1 7-10", "S2 10-17", "S1 resumes 17-22"]);
    expect(stored(moved, "R1")).toMatchObject({ kind: "return", parentSlotId: SLOT.S1 });
  });
});

describe("#577 refusals leave the document and history untouched and name the reason", () => {
  it("refuses the current range, a selection outside the row, a reversed selection and On Camera", () => {
    const doc = foldedLetter();
    expectRefused(doc, setRange("S1", doc, 0, 8), "RANGE_UNCHANGED");
    expectRefused(doc, { kind: "set_visual_range", blockId: ROW, slotId: SLOT.S1, startTokenId: wordId(doc, 0), endTokenId: id(9999) }, "RANGE_OUTSIDE_ROW");
    expectRefused(doc, { kind: "set_visual_range", blockId: ROW, slotId: SLOT.S1, startTokenId: wordId(doc, 5), endTokenId: wordId(doc, 2) }, "RANGE_REVERSED");
    expectRefused(doc, setRange("OC1", doc, 9, 12), "ON_CAMERA_RANGE_DERIVED");
    expectRefused(doc, { kind: "swap_ranges", blockId: ROW, firstSlotId: SLOT.S1, secondSlotId: SLOT.OC1 }, "ON_CAMERA_RANGE_DERIVED");
  });

  it("refuses a range that would leave an orphaned return", () => {
    // Still 1 with two cutaways side by side: pulling them apart would need Still 1 to resume twice.
    const doc = documentOf(rowOf(
      "One two three four five six seven eight nine ten eleven twelve",
      [{ at: 0, still: "S1" }, { at: 3, still: "S2", in: "S1" }, { at: 6, still: "S3", in: "S1" }, { at: 9, resume: "R1", of: "S1" }],
    ));
    expectCoherent(doc);
    expectRefused(doc, setRange("S2", doc, 3, 3), "RANGE_RETURN_ORPHANED");
  });

  it("refuses a row whose cuts are not exact words yet", () => {
    const doc = raincoat();
    (stored(doc, "R1") as ReturnSlot).inpoint = null;
    expectRefused(doc, setRange("S1", doc, 7, 10), "RANGE_SEQUENCE_UNRESOLVED");
  });
});

describe("#577 regressions kept from the r29 review", () => {
  it("raincoat: whole row, narrow, whole again leaves no On Camera, and three Undos restore", () => {
    const start = raincoat();
    const session = createRowEditSessionV2(start);
    const whole = session.applyVisualEdit(setRange("S1", start, 0, 19));
    expect(cards(whole.document)).toEqual(["S1 0-20"]);
    const narrow = session.applyVisualEdit(setRange("S1", whole.document, 7, 14));
    expect(cards(narrow.document)).toEqual(["OC wide 0-7", "S1 7-15", "OC wide resumes 15-20"]);
    const wholeAgain = session.applyVisualEdit(setRange("S1", narrow.document, 0, 19));
    expect(cards(wholeAgain.document)).toEqual(["S1 0-20"]);
    for (const state of [whole, narrow, wholeAgain]) {
      expect(state.ok).toBe(true);
      expectCoherent(state.document);
    }
    expect(storedSlots(wholeAgain.document).map((slot) => nameOf(slot.id))).toEqual(["S1"]);
    expect(session.undoDepth).toBe(3);
    expect(rowIn(session.undo().document)).toEqual(rowIn(narrow.document));
    expect(rowIn(session.undo().document)).toEqual(rowIn(whole.document));
    expect(rowIn(session.undo().document)).toEqual(rowIn(start));
    expect(session.undoDepth).toBe(0);
  });

  it("workbench: full On Camera card, Still 1, On Camera, Still 2", () => {
    const start = documentOf(rowOf(
      "At the workbench a row of brushes dried. I would choose the tired brush. The tools were cleaned before closing.",
      [{ at: 0, onCamera: "OC1" }, { at: 3, still: "S1", in: "OC1" }, { at: 8, resume: "R1", of: "OC1" }, { at: 14, still: "S2" }],
    ));
    expectCoherent(start);
    expect(cards(start)).toEqual(["OC wide 0-3", "S1 3-8", "OC wide resumes 8-14", "S2 14-20"]);
    const moved = edit(start, setRange("S2", start, 15, 19));
    expect(cards(moved)).toEqual(["OC wide 0-3", "S1 3-8", "OC wide resumes 8-15", "S2 15-20"]);
    // The untouched cutaway and its return are stored exactly as before.
    for (const slot of ["OC1", "S1"] as const) expect(stored(moved, slot)).toEqual(stored(start, slot));
  });

  it("chalk crescent: the row after the split is one full Wide On Camera card, then the slate still", () => {
    // Built as the split leaves it: the first still stays in the row above, so its
    // former words here are uncovered and meet the authored Wide passage.
    const afterSplit = documentOf(rowOf(
      "The shape simply marked the moment. They can stay until someone else needs the slate. Since then the crescent has company.",
      [{ at: 0, onCamera: "OC2" }, { at: 6, onCamera: "OC1", framing: "wide" }, { at: 15, still: "S1" }],
    ));
    expect(cards(afterSplit)).toEqual(["OC wide 0-15", "S1 15-21"]);
    const edited = edit(afterSplit, setRange("S1", afterSplit, 16, 20));
    expect(cards(edited)).toEqual(["OC wide 0-16", "S1 16-21"]);
    expect(storedSlots(edited).map((slot) => nameOf(slot.id))).toEqual(["OC1", "S1"]);
  });
});

describe("#577 swap ranges", () => {
  it("exchanges two stills' words as one Undo entry while each keeps its own source", () => {
    const start = foldedLetter();
    const session = createRowEditSessionV2(start);
    const result = session.applyVisualEdit({ kind: "swap_ranges", blockId: ROW, firstSlotId: SLOT.S1, secondSlotId: SLOT.S2 });
    expect(result.ok).toBe(true);
    expectCoherent(result.document);
    const sourceAt = (doc: ScriptDocumentV2, word: number): unknown => {
      const slotId = projectPrimarySequenceV2(doc).rows[0]!.tokens[word]!.primarySlotId;
      const slot = storedSlots(doc).find((candidate) => candidate.id === slotId);
      return slot?.kind === "content" && slot.payload.kind === "visual" ? slot.payload.source : null;
    };
    expect(sourceAt(result.document, 0)).toEqual(sourceAt(start, 20));
    expect(sourceAt(result.document, 20)).toEqual(sourceAt(start, 0));
    expect(session.undoDepth).toBe(1);
    expect(rowIn(session.undo().document)).toEqual(rowIn(start));
  });
});
