import { describe, expect, it } from "vitest";

import {
  applyRowEditV2,
  createRowEditSessionV2,
  cutNarrationWordRangeV2,
  deserializeAuthoringDocumentV2,
  serializeAuthoringDocumentV2,
  validateScriptDocumentV2,
  type StashSelectedWordsCommandV2,
} from "../src/authoring-v2.js";
import type { NarrationBlockV2, ScriptDocumentV2 } from "../src/generated/contracts-v2.js";

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

  it("refuses selected stage directions and any placed visuals or anchored objects until ownership handling", () => {
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
    const denied = applyRowEditV2(visual, 0, command(visualSource));
    expect(denied.ok).toBe(false);
    expect(denied.diagnostics[0]?.code).toBe("STASH_WORD_OWNERSHIP_REVIEW_REQUIRED");
    expect(denied.document).toBe(visual);
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
