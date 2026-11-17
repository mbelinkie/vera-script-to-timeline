import { describe, expect, it } from "vitest";

import {
  applyRowEditV2,
  createRowEditSessionV2,
  cutNarrationWordRangeV2,
  deserializeAuthoringDocumentV2,
  projectPrimarySequenceV2,
  serializeAuthoringDocumentV2,
  spliceSpokenStashNoteV2,
  copyStashNoteAsSpokenV2,
  validateScriptDocumentV2,
  type InsertStashNoteWordsCommandV2,
  type StashSelectedWordsCommandV2,
} from "../src/authoring-v2.js";
import type { ContentSlot, NarrationBlockV2, ReturnSlot, ScriptDocumentV2 } from "../src/generated/contracts-v2.js";

const id = (n: number): string => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
const textHash = `sha256:${"a".repeat(64)}`;

function row(n: number, text: string): NarrationBlockV2 {
  return {
    type: "narration", id: id(n), orderKey: `row-${n}`, text,
    tokens: [...text.matchAll(/\S+/gu)].map((match, index) => ({
      id: id(n * 100 + index + 1), value: match[0], startOffset: match.index,
      endOffset: match.index + match[0].length,
    })),
    primaryVisualSequence: {
      id: id(n * 100 + 50), version: 1,
      slots: [{
        id: id(n * 100 + 51), kind: "content", relation: { kind: "base" },
        boundaryBefore: { kind: "row_start" }, payload: { kind: "on_camera", presenterChoiceId: null },
        playoutPolicy: "match_structural_interval", version: 1,
      }],
    },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
}

function documentWith(source: NarrationBlockV2): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "Stash word cut",
    activeDraft: { blocks: [source], supportingItems: [] }, ideaOutline: [], extras: [],
    liveHeadSequence: 0, liveStateVector: "", liveContentHash: textHash,
  };
}

function command(source: NarrationBlockV2, from = 1, to = 2): StashSelectedWordsCommandV2 {
  return {
    kind: "stash_selected_words", rowId: source.id, bundleId: id(9001), stashRowId: id(9002),
    words: { startTokenId: source.tokens[from]!.id, endTokenId: source.tokens[to]!.id },
  };
}

function assertOffsets(row: NarrationBlockV2): void {
  for (const token of row.tokens) {
    expect(row.text.slice(token.startOffset, token.endOffset)).toBe(token.value);
  }
}

type Picture =
  | { at: number; kind: "visual"; number: number; clip?: boolean; cutawayFrom?: number }
  | { at: number; kind: "camera"; number: number; framing?: "wide" | "tight" }
  | { at: number; kind: "return"; number: number; from: number };

/** Exact word-start cues, including a preserved source trim, not inferred text matches. */
function withPictures(source: NarrationBlockV2, pictures: Picture[]): NarrationBlockV2 {
  const anchor = (at: number) => ({
    blockId: source.id, tokenId: source.tokens[at]!.id, quotedWord: source.tokens[at]!.value,
    affinity: "before" as const, anchorVersion: 1,
  });
  const slots: Array<ContentSlot | ReturnSlot> = pictures.map((picture, index) => {
    if (picture.kind === "return") return {
      id: id(picture.number), kind: "return", parentSlotId: id(picture.from), inpoint: anchor(picture.at), version: 1,
    };
    const payload: ContentSlot["payload"] = picture.kind === "camera"
      ? { kind: "on_camera", presenterChoiceId: null, ...(picture.framing ? { framing: picture.framing } : {}) }
      : picture.clip
        ? { kind: "visual", payloadId: id(picture.number + 1000), pictureKind: "clip",
          source: { kind: "media_reference", mediaReferenceId: id(9500) },
          sourceUsage: { sourceInFrame: 48 }, selectedSourceRange: { startFrame: 48, durationFrames: 96 },
          audioPolicy: "quiet", framingPolicy: "cover" }
        : { kind: "visual", payloadId: id(picture.number + 1000), pictureKind: "intentional_placeholder",
          source: { kind: "intentional_placeholder", text: `shot ${picture.number}` },
          sourceUsage: null, audioPolicy: "mute", framingPolicy: "contain" };
    return {
      id: id(picture.number), kind: "content",
      relation: picture.kind === "visual" && picture.cutawayFrom
        ? { kind: "cutaway", parentSlotId: id(picture.cutawayFrom) }
        : { kind: index === 0 ? "base" : "sequential" },
      boundaryBefore: index === 0 ? { kind: "row_start" } : { kind: "spoken_word", anchor: anchor(picture.at) },
      payload, playoutPolicy: "match_structural_interval", version: 1,
    };
  });
  source.primaryVisualSequence!.slots = slots;
  return source;
}

function assertCovered(doc: ScriptDocumentV2): void {
  expect(validateScriptDocumentV2(doc).diagnostics).toEqual([]);
  const active = doc.activeDraft.blocks[0] as NarrationBlockV2;
  const saved = doc.stash![0]!.rows[0] as NarrationBlockV2;
  for (const value of [active, saved]) assertOffsets(value);
  const allTokens = [...active.tokens, ...saved.tokens].map((token) => token.id);
  expect(new Set(allTokens).size).toBe(allTokens.length);
  const owned = [active, saved].flatMap((value) => value.primaryVisualSequence!.slots
    .filter((slot) => slot.kind === "content" && slot.payload.kind === "visual")
    .map((slot) => slot.id));
  expect(new Set(owned).size).toBe(owned.length);
  for (const source of [active, saved]) {
    if (source.plainDirection) continue;
    const projection = projectPrimarySequenceV2({ ...doc,
      activeDraft: { blocks: [source], supportingItems: [] },
      stash: undefined, stashOutline: undefined, stashSections: undefined,
    });
    expect(projection.rows[0]?.renderable).toBe(true);
    expect(projection.rows[0]?.tokens.every((token) => token.primarySlotId !== null)).toBe(true);
  }
  const roundTrip = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(doc));
  expect(roundTrip.ok).toBe(true);
  if (roundTrip.ok) expect(roundTrip.document).toEqual(doc);
}

describe("#584 phase 1: select narration words to top-of-Stash plain note", () => {
  it("removes exact interior words, transfers IDs to a single unchecked literal note, and undoes in one step", () => {
    const source = row(100, "Alpha beta, charlie! delta");
    const input = documentWith(source);
    const session = createRowEditSessionV2(input);
    const result = session.apply(command(source));
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    const retained = result.document.activeDraft.blocks[0] as NarrationBlockV2;
    const note = result.document.stash?.[0]?.rows[0] as NarrationBlockV2;
    expect(retained.text).toBe("Alpha delta");
    expect(retained.tokens.map((token) => token.id)).toEqual([source.tokens[0]!.id, source.tokens[3]!.id]);
    expect(retained.version).toBe(2);
    expect(note.text).toBe("beta, charlie!");
    expect(note.tokens.map((token) => token.id)).toEqual([source.tokens[1]!.id, source.tokens[2]!.id]);
    expect(note.tokens.every((token) => token.spoken === false)).toBe(true);
    expect(note.plainDirection).toBe(true);
    expect(note.stashChecklist).toEqual({ completed: false, manualRevision: 0 });
    expect(result.document.stashOutline).toEqual([{ rowId: note.id, kind: "note", sectionId: null, parentRowId: null }]);
    expect(result.document.rowEditRevision).toBe(1);
    expect(session.undoDepth).toBe(1);
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
    assertOffsets(retained); assertOffsets(note);
    const persisted = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(result.document));
    expect(persisted.ok).toBe(true);
    if (persisted.ok) expect(persisted.document).toEqual(result.document);
    const undo = session.undo();
    expect(undo.ok).toBe(true);
    expect(undo.document.activeDraft).toEqual(input.activeDraft);
    expect(undo.document.stash).toBeUndefined();
    expect(undo.document.stashOutline).toBeUndefined();
    expect(undo.document.rowEditRevision).toBe(2);
    expect(session.undoDepth).toBe(0);
    expect(input).toEqual(documentWith(source));
  });

  it("uses UTF-16 offsets for emoji, non-ASCII speech and preserved trailing LF", () => {
    const source = row(110, "👋🏽 café 😀word then\nlast\n");
    const range = cutNarrationWordRangeV2(source, {
      startTokenId: source.tokens[1]!.id, endTokenId: source.tokens[2]!.id,
    });
    expect("code" in range).toBe(false);
    if ("code" in range) throw Error(range.message);
    expect(range.extracted.text).toBe("café 😀word");
    expect(range.remaining.text).toBe("👋🏽 then\nlast\n");
    const applied = applyRowEditV2(documentWith(source), 0, command(source));
    expect(applied.ok, JSON.stringify(applied.diagnostics)).toBe(true);
    const updated = applied.document.activeDraft.blocks[0] as NarrationBlockV2;
    const note = applied.document.stash![0]!.rows[0] as NarrationBlockV2;
    expect(updated.text).toBe("👋🏽 then\nlast\n");
    expect(note.text).toBe("café 😀word");
    assertOffsets(updated); assertOffsets(note);
  });

  it("preserves literal brackets, punctuation, and boundary paragraph text without inventing speech", () => {
    const literal = row(111, "alpha [literal] middle end");
    const bracketResult = applyRowEditV2(documentWith(literal), 0, command(literal, 1, 1));
    expect(bracketResult.ok, JSON.stringify(bracketResult.diagnostics)).toBe(true);
    expect((bracketResult.document.stash![0]!.rows[0] as NarrationBlockV2).text).toBe("[literal]");
    expect((bracketResult.document.activeDraft.blocks[0] as NarrationBlockV2).text).toBe("alpha middle end");

    const first = row(112, "first second third\n");
    const front = applyRowEditV2(documentWith(first), 0, command(first, 0, 0));
    expect(front.ok, JSON.stringify(front.diagnostics)).toBe(true);
    expect((front.document.activeDraft.blocks[0] as NarrationBlockV2).text).toBe("second third\n");
    expect((front.document.stash![0]!.rows[0] as NarrationBlockV2).text).toBe("first");

    const last = row(113, "first second third\n");
    const back = applyRowEditV2(documentWith(last), 0, command(last, 2, 2));
    expect(back.ok, JSON.stringify(back.diagnostics)).toBe(true);
    expect((back.document.activeDraft.blocks[0] as NarrationBlockV2).text).toBe("first second");
    expect((back.document.stash![0]!.rows[0] as NarrationBlockV2).text).toBe("third\n");
    expect(validateScriptDocumentV2(back.document).valid).toBe(true);
  });

  it("prepends an unsectioned note without changing section or nested descendant preorder", () => {
    const source = row(120, "keep take these words");
    const parent = row(121, "parent note");
    parent.plainDirection = true;
    parent.tokens.forEach((token) => { token.spoken = false; });
    const child = row(122, "child note");
    child.plainDirection = true;
    child.tokens.forEach((token) => { token.spoken = false; });
    const document = documentWith(source);
    document.stash = [{ id: id(8900), rows: [parent, child], supportingItems: [] }];
    document.stashSections = [{ id: id(8901), title: "Section", rowIds: [] }];
    document.stashOutline = [
      { rowId: parent.id, kind: "note", sectionId: id(8901), parentRowId: null },
      { rowId: child.id, kind: "note", sectionId: id(8901), parentRowId: parent.id },
    ];
    const prior = structuredClone(document.stashOutline);
    const applied = applyRowEditV2(document, 0, command(source));
    expect(applied.ok, JSON.stringify(applied.diagnostics)).toBe(true);
    expect(applied.document.stashOutline![0]).toEqual({ rowId: id(9002), kind: "note", sectionId: null, parentRowId: null });
    expect(applied.document.stashOutline!.slice(1)).toEqual(prior);
    expect(applied.document.stashSections).toEqual(document.stashSections);
    expect(document.stashOutline).toEqual(prior);
  });

  it("refuses invalid, stale, duplicate and whole-row selections without touching the input", () => {
    const source = row(130, "one two three four");
    const document = documentWith(source);
    const valid = command(source);
    const attempts: Array<{ revision: number; input: unknown; code: string }> = [
      { revision: 1, input: valid, code: "ROW_REVISION_STALE" },
      { revision: 0, input: { ...valid, words: { ...valid.words, startTokenId: id(777777) } }, code: "ROW_SELECTION_INVALID" },
      { revision: 0, input: { ...valid, words: { startTokenId: source.tokens[3]!.id, endTokenId: source.tokens[1]!.id } }, code: "ROW_SELECTION_INVALID" },
      { revision: 0, input: { ...valid, words: { startTokenId: source.tokens[0]!.id, endTokenId: source.tokens[3]!.id } }, code: "ROW_STASH_WHOLE_ROW" },
      { revision: 0, input: { ...valid, stashRowId: source.tokens[0]!.id }, code: "STASH_WORD_ID_DUPLICATE" },
      { revision: 0, input: { ...valid, bundleId: valid.stashRowId }, code: "STASH_WORD_ID_DUPLICATE" },
      { revision: 0, input: { ...valid, words: { ...valid.words, extra: true } }, code: "ROW_COMMAND_INVALID" },
      { revision: 0, input: { ...valid, newStuff: true }, code: "ROW_COMMAND_INVALID" },
      { revision: 0, input: { ...valid, stashRowId: "not-a-uuid" }, code: "ROW_COMMAND_INVALID" },
    ];
    for (const { revision, input, code } of attempts) {
      const snapshot = structuredClone(document);
      const result = applyRowEditV2(document, revision, input as StashSelectedWordsCommandV2);
      expect(result.ok, JSON.stringify(input)).toBe(false);
      expect(result.diagnostics.map((problem) => problem.code), JSON.stringify(input)).toContain(code);
      expect(result.document).toBe(document);
      expect(document).toEqual(snapshot);
    }
  });

  it("refuses selected stage directions and keeps a prior-start visual clipped behind", () => {
    const source = row(140, "one [quiet words] two three");
    source.tokens[1]!.spoken = false;
    source.tokens[2]!.spoken = false;
    const original = documentWith(source);
    const selectedDirection = command(source, 1, 2);
    const bad = applyRowEditV2(original, 0, selectedDirection);
    expect(bad.ok).toBe(false);
    expect(bad.diagnostics[0]?.code).toMatch(/DIRECTION|SELECTION/);
    expect(bad.document).toBe(original);

    const visualSource = row(141, "alpha beta gamma delta");
    const slot = visualSource.primaryVisualSequence!.slots[0]!;
    if (slot.kind === "content") slot.payload = {
      kind: "visual", payloadId: id(141050), pictureKind: "intentional_placeholder",
      source: { kind: "intentional_placeholder", text: "a picture" },
      sourceUsage: null, audioPolicy: "mute", framingPolicy: "contain",
    };
    const visual = documentWith(visualSource);
    const carried = applyRowEditV2(visual, 0, command(visualSource));
    expect(carried.ok, JSON.stringify(carried.diagnostics)).toBe(true);
    expect(carried.document.stashOutline![0]?.kind).toBe("note");
    const retained = carried.document.activeDraft.blocks[0] as NarrationBlockV2;
    const saved = carried.document.stash![0]!.rows[0] as NarrationBlockV2;
    expect(retained.primaryVisualSequence!.slots.some((candidate) => candidate.id === slot.id)).toBe(true);
    expect(saved.primaryVisualSequence!.slots.some((candidate) => candidate.id === slot.id)).toBe(false);
    const assigned = projectPrimarySequenceV2(carried.document).rows[0]!.tokens.map((token) => token.primarySlotId);
    expect(assigned.slice(0, 1)).toEqual([slot.id]);
    expect(assigned.slice(1).every((owner) => owner !== slot.id)).toBe(true);
    assertCovered(carried.document);
    expect(visual.activeDraft.blocks[0]).toEqual(visualSource);
  });

  it("refuses an optimistic cut when a word-anchored comment or music span might be stranded", () => {
    const source = row(142, "one two three four");
    const doc = documentWith(source);
    doc.rowReferences = [{
      id: id(14300), rowId: source.id, kind: "comment",
      anchor: { kind: "text", blockId: source.id,
        startTokenId: source.tokens[1]!.id, endTokenId: source.tokens[1]!.id },
    }];
    const refused = applyRowEditV2(doc, 0, command(source));
    expect(refused.ok).toBe(false);
    expect(refused.diagnostics.some((entry) => entry.code === "ROW_REFERENCE_REVIEW_REQUIRED")).toBe(true);
    expect(refused.document).toBe(doc);
    expect(doc.activeDraft.blocks[0]).toEqual(source);
  });
});

describe("#584 phase 3: inline note speech and independent first-word footage", () => {
  const note = (n: number, text = "[literal] words"): NarrationBlockV2 => {
    const result = row(n, text);
    result.plainDirection = true;
    result.tokens.forEach((token) => { token.spoken = false; });
    return result;
  };
  const withAttachment = (source: NarrationBlockV2): void => {
    source.attachedFootage = { clip: {
      type: "visual_only", id: id(45000), orderKey: "stash-clip",
      payload: { kind: "visual", payloadId: id(45001), pictureKind: "clip",
        source: { kind: "media_reference", mediaReferenceId: id(45002) },
        audioPolicy: "quiet", framingPolicy: "contain" },
      visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 13, durationFrames: 55 } },
      version: 1,
    } };
  };
  const fixture = (attach = false) => {
    const target = row(300, "Alpha beta");
    const source = note(301);
    const child = note(302, "untouched child");
    if (attach) withAttachment(source);
    const doc = documentWith(target);
    doc.stash = [
      { id: id(46000), rows: [source], supportingItems: [] },
      { id: id(46001), rows: [child], supportingItems: [] },
    ];
    doc.stashOutline = [
      { rowId: source.id, kind: "note", parentRowId: null, sectionId: null },
      { rowId: child.id, kind: "note", parentRowId: source.id, sectionId: null },
    ];
    const command: InsertStashNoteWordsCommandV2 = {
      kind: "insert_stash_note_words", rowId: target.id, noteRowId: source.id,
      beforeTokenId: target.tokens[1]!.id,
    };
    return { doc, target, source, child, command };
  };
  const saved = (doc: ScriptDocumentV2, id: string) => doc.stash!.flatMap((bundle) => bundle.rows)
    .find((item) => item.id === id) as NarrationBlockV2;

  it("splices brackets as spoken words with original neighbor IDs, checks only the source and survives save/reload", () => {
    const { doc, target, source, child, command } = fixture();
    const session = createRowEditSessionV2(doc);
    const added = session.apply(command);
    expect(added.ok, JSON.stringify(added.diagnostics)).toBe(true);
    const placed = added.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(placed.text).toBe("Alpha [literal] words beta");
    expect(placed.tokens.map((token) => token.value)).toEqual(["Alpha", "[literal]", "words", "beta"]);
    expect(placed.tokens.map((token) => token.id).filter((id) => target.tokens.some((t) => t.id === id)))
      .toEqual(target.tokens.map((token) => token.id));
    expect(placed.tokens.slice(1, 3).every((token) => token.spoken === true)).toBe(true);
    expect(placed.stashOrigin).toBeUndefined();
    expect(placed.version).toBe(2);
    assertOffsets(placed);
    expect(saved(added.document, source.id).stashChecklist).toEqual({ completed: true, manualRevision: 0 });
    expect(saved(added.document, source.id).text).toBe(source.text);
    expect(saved(added.document, child.id)).toEqual(child);
    expect(added.document.stashOutline).toEqual(doc.stashOutline);
    expect(added.document.rowEditRevision).toBe(1);
    expect(session.undoDepth).toBe(1);
    expect(validateScriptDocumentV2(added.document).valid).toBe(true);
    const restored = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(added.document));
    expect(restored.ok).toBe(true);
    if (restored.ok) expect(restored.document).toEqual(added.document);
    const undone = session.undo();
    expect(undone.ok).toBe(true);
    expect({ ...undone.document, rowEditRevision: undefined }).toEqual({ ...doc, rowEditRevision: undefined });
    expect(session.undoDepth).toBe(0);
    const redone = session.redo();
    expect(redone.ok).toBe(true);
    expect({ ...redone.document, rowEditRevision: undefined })
      .toEqual({ ...added.document, rowEditRevision: undefined });
    expect(redone.document.rowEditRevision).toBe(3);
    expect(session.redoDepth).toBe(0);
  });

  it("copies trimmed footage to exactly the first inserted word with fresh visual ownership", () => {
    const { doc, target, source, command } = fixture(true);
    const original = structuredClone(source.attachedFootage);
    const applied = applyRowEditV2(doc, 0, command);
    expect(applied.ok, JSON.stringify(applied.diagnostics)).toBe(true);
    const active = applied.document.activeDraft.blocks[0] as NarrationBlockV2;
    const visuals = active.primaryVisualSequence!.slots.filter((slot) =>
      slot.kind === "content" && slot.payload.kind === "visual") as ContentSlot[];
    expect(visuals).toHaveLength(1);
    const inserted = active.tokens[1]!;
    expect(visuals[0]!.boundaryBefore).toMatchObject({ kind: "spoken_word", anchor: { tokenId: inserted.id } });
    expect(visuals[0]!.id).not.toBe(source.primaryVisualSequence!.slots[0]!.id);
    expect(visuals[0]!.payload.kind).toBe("visual");
    if (visuals[0]!.payload.kind !== "visual") throw Error("missing copied clip");
    expect(visuals[0]!.payload.payloadId).not.toBe(original!.clip.payload.payloadId);
    expect(visuals[0]!.payload.source).toEqual(original!.clip.payload.source);
    expect(visuals[0]!.payload.selectedSourceRange).toEqual({ startFrame: 13, durationFrames: 55 });
    expect(visuals[0]!.payload.audioPolicy).toBe("quiet");
    expect(active.attachedFootage).toBeUndefined();
    expect(saved(applied.document, source.id).attachedFootage).toEqual(original);
    expect(source.attachedFootage).toEqual(original);
    const assigned = projectPrimarySequenceV2(applied.document).rows[0]!.tokens;
    expect(assigned[1]!.primarySlotId).toBe(visuals[0]!.id);
    expect(assigned[2]!.primarySlotId).not.toBe(visuals[0]!.id);
    expect(assigned[0]!.primarySlotId).not.toBe(visuals[0]!.id);
    expect(assigned[3]!.primarySlotId).not.toBe(visuals[0]!.id);
    expect(active.tokens[0]!.id).toBe(target.tokens[0]!.id);
    expect(validateScriptDocumentV2(applied.document).diagnostics).toEqual([]);

    const second = applyRowEditV2(applied.document, 1, command);
    expect(second.ok, JSON.stringify(second.diagnostics)).toBe(true);
    const again = second.document.activeDraft.blocks[0] as NarrationBlockV2;
    const slots = again.primaryVisualSequence!.slots.filter((slot) =>
      slot.kind === "content" && slot.payload.kind === "visual") as ContentSlot[];
    expect(slots).toHaveLength(2);
    expect(new Set(slots.map((slot) => slot.id)).size).toBe(2);
    expect(saved(second.document, source.id).attachedFootage).toEqual(original);
    expect(saved(second.document, source.id).stashChecklist).toEqual({ completed: true, manualRevision: 0 });
  });

  it("preserves manual checkbox history and never overwrites an earlier automatic copy identity", () => {
    const { doc, source, command } = fixture();
    source.stashChecklist = { completed: true, manualRevision: 7, automaticCopyId: id(47000) };
    const result = applyRowEditV2(doc, 0, command);
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(saved(result.document, source.id).stashChecklist).toEqual(source.stashChecklist);
    const unchecked = structuredClone(doc);
    saved(unchecked, source.id).stashChecklist = { completed: false, manualRevision: 8 };
    const first = applyRowEditV2(unchecked, 0, command);
    expect(first.ok).toBe(true);
    expect(saved(first.document, source.id).stashChecklist).toEqual({ completed: true, manualRevision: 8 });
  });

  it("keeps existing real stage directions and UTF-16 offsets, while inserted brackets stay literal", () => {
    const { doc, source, target, command } = fixture();
    source.text = "🎬 [literal] words\n";
    source.tokens = [...source.text.matchAll(/\S+/gu)].map((match, index) => ({
      id: id(48000 + index), value: match[0], startOffset: match.index,
      endOffset: match.index + match[0].length, spoken: false,
    }));
    target.text = "Hello [quiet] there beta\n";
    target.tokens = [
      { ...target.tokens[0]!, value: "Hello", startOffset: 0, endOffset: 5 },
      { id: id(48010), value: "quiet", startOffset: 7, endOffset: 12, spoken: false },
      { id: id(48011), value: "there", startOffset: 14, endOffset: 19 },
      { ...target.tokens[1]!, value: "beta", startOffset: 20, endOffset: 24 },
    ];
    expect(validateScriptDocumentV2(doc).valid).toBe(true);
    const copied = copyStashNoteAsSpokenV2(source, "pure-test-584");
    const pure = spliceSpokenStashNoteV2(target, copied, command.beforeTokenId);
    expect("error" in pure).toBe(false);
    if ("error" in pure) throw Error(pure.error);
    expect(pure.row.text).toBe("Hello [quiet] there 🎬 [literal] words\nbeta\n");
    expect(pure.row.tokens[1]!.spoken).toBe(false);
    expect(pure.row.tokens.slice(3, 6).every((token) => token.spoken === true)).toBe(true);
    assertOffsets(pure.row);
    const applied = applyRowEditV2(doc, 0, command);
    expect(applied.ok, JSON.stringify(applied.diagnostics)).toBe(true);
    expect((applied.document.activeDraft.blocks[0] as NarrationBlockV2).text).toBe(pure.row.text);
    expect(validateScriptDocumentV2(applied.document).valid).toBe(true);
  });

  it("refuses invalid gap, source, stale revision, malformed command and unsafe attachment atomically", () => {
    const { doc, source, target, command } = fixture(true);
    const cases: Array<{ input: unknown; rev?: number; code: string }> = [
      { input: command, rev: 1, code: "ROW_REVISION_STALE" },
      { input: { ...command, beforeTokenId: target.tokens[0]!.id }, code: "STASH_NOTE_INSERT_INVALID" },
      { input: { ...command, beforeTokenId: id(59999) }, code: "STASH_NOTE_INSERT_INVALID" },
      { input: { ...command, noteRowId: id(59998) }, code: "STASH_NOTE_CONTENT_INVALID" },
      { input: { ...command, extra: true }, code: "ROW_COMMAND_INVALID" },
      { input: { ...command, rowId: "not-uuid" }, code: "ROW_COMMAND_INVALID" },
    ];
    for (const { input, rev = 0, code } of cases) {
      const before = structuredClone(doc);
      const refused = applyRowEditV2(doc, rev, input as InsertStashNoteWordsCommandV2);
      expect(refused.ok, JSON.stringify(input)).toBe(false);
      expect(refused.diagnostics.map((item) => item.code), JSON.stringify(input)).toContain(code);
      expect(refused.document).toBe(doc);
      expect(doc).toEqual(before);
    }
    const fullAudio = structuredClone(doc);
    saved(fullAudio, source.id).attachedFootage!.clip.payload.audioPolicy = "full";
    const refused = applyRowEditV2(fullAudio, 0, command);
    expect(refused.ok).toBe(false);
    expect(refused.diagnostics[0]?.code).toBe("STASH_ATTACHMENT_VISUAL_CONFLICT");
    expect(refused.document).toBe(fullAudio);

    const brokenOffset = structuredClone(doc);
    (brokenOffset.activeDraft.blocks[0] as NarrationBlockV2).tokens[0]!.endOffset = 1;
    const bad = applyRowEditV2(brokenOffset, 0, command);
    expect(bad.ok).toBe(false);
    expect(bad.document).toBe(brokenOffset);

    const collision = structuredClone(doc);
    const minted = copyStashNoteAsSpokenV2(source,
      `${doc.id}:0:${source.id}:inline:${target.id}`);
    (collision.activeDraft.blocks[0] as NarrationBlockV2).tokens[0]!.id = minted.tokens[0]!.id;
    const duplicated = applyRowEditV2(collision, 0, command);
    expect(duplicated.ok).toBe(false);
    expect(duplicated.diagnostics[0]?.code).toBe("STASH_WORD_ID_DUPLICATE");
    expect(duplicated.document).toBe(collision);
  });

  it("refuses blank notes, genuine nonspoken direction gaps and destination rows with owned footage", () => {
    const { doc, source, command } = fixture();
    source.text = "";
    source.tokens = [];
    const blank = applyRowEditV2(doc, 0, command);
    expect(blank.ok).toBe(false);
    expect(blank.diagnostics[0]?.code).toBe("STASH_NOTE_CONTENT_INVALID");
    expect(blank.document).toBe(doc);

    const withDirection = fixture();
    const receiver = withDirection.target;
    receiver.text = "Alpha [quiet] beta";
    receiver.tokens = [
      { ...receiver.tokens[0]!, value: "Alpha", startOffset: 0, endOffset: 5 },
      { id: id(48020), value: "quiet", startOffset: 7, endOffset: 12, spoken: false },
      { ...receiver.tokens[1]!, value: "beta", startOffset: 14, endOffset: 18 },
    ];
    expect(validateScriptDocumentV2(withDirection.doc).valid).toBe(true);
    const badGap = applyRowEditV2(withDirection.doc, 0, withDirection.command);
    expect(badGap.ok).toBe(false);
    expect(badGap.diagnostics[0]?.code).toBe("STASH_NOTE_INSERT_INVALID");
    expect(badGap.document).toBe(withDirection.doc);

    const ownedTarget = fixture();
    withAttachment(ownedTarget.target);
    const conflict = applyRowEditV2(ownedTarget.doc, 0, ownedTarget.command);
    expect(conflict.ok).toBe(false);
    expect(conflict.diagnostics[0]?.code).toBe("NARRATION_TEXT_TARGET_INVALID");
    expect(conflict.document).toBe(ownedTarget.doc);
  });

  it("does not retain stale redo after a new edit, and failed edits add no Undo", () => {
    const { doc, target, command } = fixture();
    const session = createRowEditSessionV2(doc);
    expect(session.apply({ ...command, beforeTokenId: target.tokens[0]!.id }).ok).toBe(false);
    expect(session.undoDepth).toBe(0);
    expect(session.apply(command).ok).toBe(true);
    expect(session.undo().ok).toBe(true);
    expect(session.redoDepth).toBe(1);
    expect(session.apply(command).ok).toBe(true);
    expect(session.redoDepth).toBe(0);
    expect(session.redo().diagnostics[0]?.code).toBe("ROW_REDO_EMPTY");
  });
});

describe("#584 phase 2: saved visual row ownership and reference fences", () => {
  const words = "one two three four five six seven eight nine ten eleven twelve";
  const original = (n: number, pictures: Picture[]) => withPictures(row(n, words), pictures);
  const save = (source: NarrationBlockV2, from: number, to: number): ScriptDocumentV2 => {
    const applied = applyRowEditV2(documentWith(source), 0, command(source, from, to));
    expect(applied.ok, JSON.stringify(applied.diagnostics)).toBe(true);
    expect(applied.document.stashOutline![0]?.kind).toBe("row");
    assertCovered(applied.document);
    expect([
      ...(applied.document.activeDraft.blocks[0] as NarrationBlockV2).tokens,
      ...(applied.document.stash![0]!.rows[0] as NarrationBlockV2).tokens,
    ].map((token) => token.id).sort()).toEqual(source.tokens.map((token) => token.id).sort());
    return applied.document;
  };

  it("moves only a visual starting in the selection and preserves clip trim, source, and audio choices", () => {
    const source = original(160, [
      { kind: "camera", number: 7001, at: 0 },
      { kind: "visual", number: 7002, at: 3, clip: true },
      { kind: "camera", number: 7003, at: 8, framing: "tight" },
    ]);
    const result = save(source, 2, 5);
    const retained = result.activeDraft.blocks[0] as NarrationBlockV2;
    const saved = result.stash![0]!.rows[0] as NarrationBlockV2;
    const originalClip = source.primaryVisualSequence!.slots[1] as ContentSlot;
    const arrived = saved.primaryVisualSequence!.slots.find((slot) => slot.id === originalClip.id) as ContentSlot;
    expect(arrived.payload).toEqual(originalClip.payload);
    expect(saved.tokens.map((token) => token.value)).toEqual(["three", "four", "five", "six"]);
    expect(retained.primaryVisualSequence!.slots.some((slot) => slot.id === originalClip.id)).toBe(false);
    expect(saved.primaryVisualSequence!.slots[0]?.kind).toBe("content");
    expect((saved.primaryVisualSequence!.slots[0] as ContentSlot).boundaryBefore.kind).toBe("row_start");
  });

  it("a visual starting at the first removed word has exactly one owner, even at a prefix boundary", () => {
    const source = original(165, [
      { kind: "visual", number: 7501, at: 0, clip: true },
      { kind: "camera", number: 7502, at: 4 },
      { kind: "visual", number: 7503, at: 8 },
    ]);
    const result = save(source, 0, 2);
    const sourceRow = result.activeDraft.blocks[0] as NarrationBlockV2;
    const savedRow = result.stash![0]!.rows[0] as NarrationBlockV2;
    expect(savedRow.primaryVisualSequence!.slots.some((slot) => slot.id === id(7501))).toBe(true);
    expect(sourceRow.primaryVisualSequence!.slots.some((slot) => slot.id === id(7501))).toBe(false);
    expect(sourceRow.primaryVisualSequence!.slots.some((slot) => slot.id === id(7503))).toBe(true);
    expect(savedRow.tokens.map((token) => token.id)).toEqual(source.tokens.slice(0, 3).map((token) => token.id));
  });

  it("a visual-bearing word cut is one atomic Undo, restoring the exact source and Stash", () => {
    const source = original(168, [
      { kind: "camera", number: 7801, at: 0 },
      { kind: "visual", number: 7802, at: 3, clip: true },
    ]);
    const initial = documentWith(source);
    const session = createRowEditSessionV2(initial);
    const result = session.apply(command(source, 2, 5));
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    assertCovered(result.document);
    expect(session.undoDepth).toBe(1);
    const restored = session.undo();
    expect(restored.ok).toBe(true);
    expect(restored.document.activeDraft).toEqual(initial.activeDraft);
    expect(restored.document.stash).toBeUndefined();
    expect(restored.document.stashOutline).toBeUndefined();
    expect(initial).toEqual(documentWith(source));
  });

  it("moves two starts, leaves an earlier-start visual behind, and retains Tight coverage on both sides", () => {
    const source = original(161, [
      { kind: "visual", number: 7101, at: 0 },
      { kind: "camera", number: 7102, at: 3, framing: "tight" },
      { kind: "visual", number: 7103, at: 5 },
      { kind: "visual", number: 7104, at: 7 },
      { kind: "camera", number: 7105, at: 10 },
    ]);
    const result = save(source, 4, 8);
    const active = result.activeDraft.blocks[0] as NarrationBlockV2;
    const saved = result.stash![0]!.rows[0] as NarrationBlockV2;
    expect(active.primaryVisualSequence!.slots.some((slot) => slot.id === id(7101))).toBe(true);
    expect(active.primaryVisualSequence!.slots.some((slot) => slot.id === id(7103) || slot.id === id(7104))).toBe(false);
    expect(saved.primaryVisualSequence!.slots.some((slot) => slot.id === id(7103))).toBe(true);
    expect(saved.primaryVisualSequence!.slots.some((slot) => slot.id === id(7104))).toBe(true);
    expect(saved.primaryVisualSequence!.slots.some((slot) => slot.kind === "content" && slot.payload.kind === "on_camera" && slot.payload.framing === "tight")).toBe(true);
  });

  it("a Tight On Camera choice that starts before the cut stays behind; a choice starting inside is saved", () => {
    const source = original(167, [
      { kind: "camera", number: 7701, at: 0, framing: "tight" },
      { kind: "camera", number: 7702, at: 8, framing: "wide" },
    ]);
    const beforeStart = applyRowEditV2(documentWith(source), 0, command(source, 2, 4));
    expect(beforeStart.ok, JSON.stringify(beforeStart.diagnostics)).toBe(true);
    expect(beforeStart.document.stashOutline![0]!.kind).toBe("note");
    const note = beforeStart.document.stash![0]!.rows[0] as NarrationBlockV2;
    expect(note.plainDirection).toBe(true);
    expect(note.primaryVisualSequence!.slots).toHaveLength(1);
    expect((note.primaryVisualSequence!.slots[0] as ContentSlot).payload).toEqual({ kind: "on_camera", presenterChoiceId: null });
    assertCovered(beforeStart.document);

    const insideStart = save(source, 8, 10);
    const moved = insideStart.stash![0]!.rows[0] as NarrationBlockV2;
    expect(moved.plainDirection).toBeUndefined();
    expect(moved.primaryVisualSequence!.slots.some((slot) => slot.id === id(7702))).toBe(true);
  });

  it("a cutaway starting inside a selection moves as a single visual, with no orphan return", () => {
    const source = original(162, [
      { kind: "visual", number: 7201, at: 0 },
      { kind: "visual", number: 7202, at: 4, cutawayFrom: 7201 },
      { kind: "return", number: 7203, at: 7, from: 7201 },
      { kind: "camera", number: 7204, at: 10 },
    ]);
    const result = save(source, 3, 6);
    const active = result.activeDraft.blocks[0] as NarrationBlockV2;
    const saved = result.stash![0]!.rows[0] as NarrationBlockV2;
    expect(saved.primaryVisualSequence!.slots.some((slot) => slot.id === id(7202))).toBe(true);
    expect(active.primaryVisualSequence!.slots.some((slot) => slot.id === id(7202))).toBe(false);
    expect(saved.primaryVisualSequence!.slots.every((slot) => slot.kind !== "return" ||
      saved.primaryVisualSequence!.slots.some((other) => other.kind === "content" && other.id === slot.parentSlotId))).toBe(true);
  });

  it("moving an anchored annotation rewrites its row while a straddling annotation refuses atomically", () => {
    const source = original(163, [{ kind: "camera", number: 7301, at: 0 }, { kind: "visual", number: 7302, at: 2 }]);
    const range = (from: number, to: number) => ({
      blockId: source.id, startTokenId: source.tokens[from]!.id, endTokenId: source.tokens[to]!.id,
      startAffinity: "before" as const, endAffinity: "after" as const,
      quotedText: source.text.slice(source.tokens[from]!.startOffset, source.tokens[to]!.endOffset), anchorVersion: 1,
    });
    source.annotations = [{ id: id(7601), kind: "performance_note", range: range(3, 4),
      value: "gentle", includeInPrompter: true, version: 1 }];
    const result = save(source, 2, 5);
    const saved = result.stash![0]!.rows[0] as NarrationBlockV2;
    expect(saved.annotations?.[0]?.range.blockId).toBe(saved.id);
    expect((result.activeDraft.blocks[0] as NarrationBlockV2).annotations).toEqual([]);

    const straddling = structuredClone(source);
    straddling.annotations![0]!.range = range(1, 3);
    const input = documentWith(straddling);
    const refused = applyRowEditV2(input, 0, command(straddling, 2, 5));
    expect(refused.ok).toBe(false);
    expect(refused.diagnostics.map((entry) => entry.code)).toContain("ROW_ANCHOR_STRADDLES_BOUNDARY");
    expect(refused.document).toBe(input);
    expect(input).toEqual(documentWith(straddling));
  });

  it("parks words with an anchored performance note as a spoken saved row even without placed visuals", () => {
    const source = row(166, "alpha beta gamma delta");
    source.annotations = [{
      id: id(7901), kind: "performance_note",
      range: { blockId: source.id, startTokenId: source.tokens[1]!.id,
        endTokenId: source.tokens[1]!.id, startAffinity: "before", endAffinity: "after",
        quotedText: "beta", anchorVersion: 1 },
      value: "pause", includeInPrompter: true, version: 1,
    }];
    const result = applyRowEditV2(documentWith(source), 0, command(source, 1, 1));
    expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
    expect(result.document.stashOutline?.[0]?.kind).toBe("row");
    const saved = result.document.stash![0]!.rows[0] as NarrationBlockV2;
    expect(saved.plainDirection).toBeUndefined();
    expect(saved.annotations?.[0]?.range.blockId).toBe(saved.id);
    expect(saved.tokens[0]?.spoken).not.toBe(false);
    assertCovered(result.document);
  });

  it("refuses row transitions, music spanning the row, card comments and unattached footage without mutation", () => {
    const source = original(164, [{ kind: "camera", number: 7401, at: 0 }, { kind: "visual", number: 7402, at: 2 }]);
    const scenarios: ScriptDocumentV2[] = [];
    const transition = documentWith(source);
    transition.activeDraft.blocks.push(row(169, "outside row"));
    transition.rowTransitions = [{ id: id(7602), fromRowId: source.id, toRowId: id(169),
      effect: "crossfade", settings: { frames: 6 }, state: "active" }];
    scenarios.push(transition);
    const music = documentWith(source);
    music.rowAudioSpans = [{ id: id(7606), startRowId: source.id, endRowId: source.id,
      source: { mediaReferenceId: id(7607), artifactId: id(7608), artifactVersion: 1,
        contentHash: textHash }, settings: { gainDb: -12 } }];
    scenarios.push(music);
    const comment = documentWith(source);
    comment.rowReferences = [{ id: id(7603), kind: "comment", rowId: source.id,
      anchor: { kind: "card", blockId: source.id, cardId: id(7402) } }];
    scenarios.push(comment);
    const unowned = structuredClone(source);
    unowned.unattachedVisuals = [{ slotId: id(7604), payload: {
      kind: "visual", payloadId: id(7605), pictureKind: "intentional_placeholder",
      source: { kind: "intentional_placeholder", text: "unattached" }, sourceUsage: null,
      audioPolicy: "mute", framingPolicy: "contain",
    }, version: 1 }];
    scenarios.push(documentWith(unowned));
    for (const [index, input] of scenarios.entries()) {
      expect(validateScriptDocumentV2(input).diagnostics, `fixture ${index}`).toEqual([]);
      const before = structuredClone(input);
      const result = applyRowEditV2(input, 0, command(source, 2, 5));
      expect(result.ok).toBe(false);
      expect(result.diagnostics.map((entry) => entry.code)).toContain(index === 3
        ? "STASH_WORD_OWNERSHIP_REVIEW_REQUIRED" : "ROW_REFERENCE_REVIEW_REQUIRED");
      expect(result.document).toBe(input);
      expect(input).toEqual(before);
    }
  });
});
