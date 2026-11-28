import { describe, expect, it } from "vitest";

import {
  applyCommentOperationV2,
  applyRowEditV2,
  createCommentStateV2,
  createRowEditSessionV2,
  deserializeAuthoringDocumentV2,
  projectPrimarySequenceV2,
  serializeAuthoringDocumentV2,
  validateScriptDocumentV2,
  type RowEditCommandV2,
} from "@vera/contracts/authoring-v2";
import type { ContentSlot, NarrationBlockV2, ReturnSlot, RowAudioSpanIntentV2, ScriptDocumentV2 } from "@vera/contracts/v2";
import type { OnCameraFramingV2 } from "../src/authoring-v2.js";

/**
 * #579: split and join script rows, carrying visuals by the accepted rules
 * (S03 r29: D97, D114, D115, D124, D137, D138).
 *
 * Before/after table. Words are numbered from 0; "|" marks a row boundary.
 *
 * | Case                              | Before                                   | After                                              |
 * |-----------------------------------|------------------------------------------|----------------------------------------------------|
 * | Cursor split inside a visual      | [S1 0-14, OC 14-23, S2 23-29]            | [S1 0-8] | [OC 0-15, S2 15-21]                     |
 * | Cursor at end / before first word | [row]                                    | refused: no words to split off (that is Add row)   |
 * | Split, selection has first word   | [S1 0-9, OC 9-14, S2 14-20], select 0-4  | new [S1 0-5] | [OC 0-9, S2 9-15]                   |
 * | Split, selection has last word    | same row, select 12-19                   | [S1 0-9, OC 9-12] | new [OC 0-2, S2 2-8]           |
 * | Split, whole row or mid-row       | select 0-19 or 5-8                       | refused, nothing changes                           |
 * | Join selected words to row above  | A | [S1 0-9, ...], select 0-4            | A + 5 words (S1 on them) | rest of the row         |
 * | Join selected words to row below  | [.., S2 14-20] | B, select 16-19         | row keeps S2 14-16 | 4 words + B (On Camera)       |
 * | Join whole row above (Backspace)  | A | B                                    | A, paragraph break, B's words; B is removed        |
 * | Split then join straight back     | row -> two rows -> join                  | the original row exactly, clipped visual restored  |
 * | Split, another edit, then join    | row -> two rows -> edit -> join          | ordinary join: visual stays clipped                |
 * | Break after the final word        | "one two three\n", split before "two"    | "one" | "two three\n"                              |
 * | Join across a section break       | A | section | B                          | refused, nothing changes                           |
 */

const id = (value: number): string => `00000000-0000-4000-8000-${value.toString(16).padStart(12, "0")}`;
const rowId = (row: number): string => id(row * 100_000 + 6);
const tokenId = (row: number, index: number): string => id(row * 100_000 + 1000 + index);
const SLOT_NUMBERS = { S1: 101, S2: 102, S3: 103, OC1: 201, OC2: 202, R1: 301 } as const;
type SlotName = keyof typeof SLOT_NUMBERS;
const slotId = (row: number, name: SlotName): string => id(row * 100_000 + SLOT_NUMBERS[name]);

type Piece =
  | { at: number; still: "S1" | "S2" | "S3"; in?: SlotName }
  | { at: number; onCamera: "OC1" | "OC2"; framing?: OnCameraFramingV2 }
  | { at: number; resume: "R1"; of: SlotName };

/** A narration row. Words inside [square brackets] are a stage direction; `at` counts spoken words. */
function rowOf(row: number, text: string, pieces: Piece[] = [{ at: 0, onCamera: "OC1" }]): NarrationBlockV2 {
  const tokens: NarrationBlockV2["tokens"] = [];
  let inDirection = false;
  for (const match of text.matchAll(/\[|\]|[^\s[\]]+/gu)) {
    if (match[0] === "[") inDirection = true;
    else if (match[0] === "]") inDirection = false;
    else {
      tokens.push({
        id: tokenId(row, tokens.length), value: match[0], startOffset: match.index, endOffset: match.index + match[0].length,
        ...(inDirection ? { spoken: false } : {}),
      });
    }
  }
  const spoken = tokens.filter((token) => token.spoken !== false);
  const anchor = (at: number) => ({
    blockId: rowId(row), tokenId: spoken[at]!.id, affinity: "before" as const, quotedWord: spoken[at]!.value, anchorVersion: 1,
  });
  const slots = pieces.map((piece, index): ContentSlot | ReturnSlot => {
    if ("resume" in piece) {
      return { id: slotId(row, piece.resume), kind: "return", parentSlotId: slotId(row, piece.of), inpoint: anchor(piece.at), version: 1 };
    }
    const name = "still" in piece ? piece.still : piece.onCamera;
    return {
      id: slotId(row, name),
      kind: "content",
      relation: "still" in piece && piece.in ? { kind: "cutaway", parentSlotId: slotId(row, piece.in) } : { kind: index === 0 ? "base" : "sequential" },
      boundaryBefore: index === 0 ? { kind: "row_start" } : { kind: "spoken_word", anchor: anchor(piece.at) },
      payload: "still" in piece
        ? {
            kind: "visual", payloadId: id(row * 100_000 + SLOT_NUMBERS[name] + 5000),
            pictureKind: "intentional_placeholder", source: { kind: "intentional_placeholder", text: `${name} of row ${row}` },
            sourceUsage: null, audioPolicy: "mute", framingPolicy: "contain",
          }
        : { kind: "on_camera", presenterChoiceId: null, ...(piece.framing ? { framing: piece.framing } : {}) },
      playoutPolicy: "match_structural_interval",
      version: 1,
    };
  });
  return {
    type: "narration", id: rowId(row), orderKey: `row-${row}`, text, tokens,
    primaryVisualSequence: { id: id(row * 100_000 + 9), slots, version: 1 },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
}

const section = (value: number) => ({ type: "section" as const, id: id(value), orderKey: `section-${value}`, title: `Section ${value}`, version: 1 });

function documentOf(blocks: ScriptDocumentV2["activeDraft"]["blocks"], extra: Partial<ScriptDocumentV2> = {}): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "Split and join rows",
    activeDraft: { blocks, supportingItems: [] }, ideaOutline: [], extras: [], liveHeadSequence: 0,
    liveStateVector: "", liveContentHash: `sha256:${"a".repeat(64)}`, ...extra,
  };
}

const NEW_ROW = id(900_006);
const narration = (doc: ScriptDocumentV2): NarrationBlockV2[] =>
  doc.activeDraft.blocks.filter((block): block is NarrationBlockV2 => block.type === "narration");
const find = (doc: ScriptDocumentV2, blockId: string): NarrationBlockV2 => narration(doc).find((row) => row.id === blockId)!;
const words = (row: NarrationBlockV2): string => row.tokens.map((token) => token.value).join(" ");
const tokenIds = (row: NarrationBlockV2): string[] => row.tokens.map((token) => token.id);

/** A slot's name: "S1", "OC1"; a new On Camera slot the edit derived shows as "new". */
function nameOf(value: string): string {
  const number = Number.parseInt(value.slice(-12), 16) % 100_000;
  return (Object.entries(SLOT_NUMBERS).find(([, candidate]) => candidate === number)?.[0]) ?? "new";
}

/** One row's card stack as text: "S1 0-9", "OC wide 9-18", "OC wide resumes 12-20", "S2 unattached". */
function cards(doc: ScriptDocumentV2, blockId: string): string[] {
  return projectPrimarySequenceV2(doc).rows.find((row) => row.blockId === blockId)!.cards.map((card) => {
    if (card.kind === "unattached_visual") return `${nameOf(card.slotId)} unattached`;
    const label = card.kind === "on_camera" ? `OC ${card.framing}` : nameOf(card.slotId);
    return `${label}${card.compact ? " resumes" : ""} ${card.startTokenIndex}-${card.endTokenIndexExclusive}`;
  });
}

/** Valid, every word has exactly one picture, no visual or word is in two rows. */
function expectSound(doc: ScriptDocumentV2): void {
  expect(validateScriptDocumentV2(doc).diagnostics).toEqual([]);
  for (const row of projectPrimarySequenceV2(doc).rows) {
    expect(row.renderable).toBe(true);
    expect(row.tokens.every((token) => token.primarySlotId !== null)).toBe(true);
  }
  const slotIds = narration(doc).flatMap((row) => (row.primaryVisualSequence?.slots ?? []).map((slot) => slot.id));
  expect(new Set(slotIds).size).toBe(slotIds.length);
  const allTokens = narration(doc).flatMap(tokenIds);
  expect(new Set(allTokens).size).toBe(allTokens.length);
}

function apply(doc: ScriptDocumentV2, command: RowEditCommandV2): ScriptDocumentV2 {
  const result = applyRowEditV2(doc, doc.rowEditRevision ?? 0, command);
  expect(result.diagnostics).toEqual([]);
  expect(result.ok).toBe(true);
  expectSound(result.document);
  // Save and reload preserve the result.
  const reloaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(result.document));
  expect(reloaded.ok && reloaded.document).toEqual(result.document);
  return result.document;
}

/** A refusal names its reason and returns the very same document, untouched. */
function expectRefused(doc: ScriptDocumentV2, command: RowEditCommandV2, code: string): void {
  const before = structuredClone(doc);
  const result = applyRowEditV2(doc, doc.rowEditRevision ?? 0, command);
  expect(result.ok).toBe(false);
  expect(result.diagnostics.map((item) => item.code)).toEqual([code]);
  expect(result.diagnostics[0]!.message.length).toBeGreaterThan(10);
  expect(result.document).toBe(doc);
  expect(doc).toEqual(before);
}

const CHALK = 1;
/** r29 chalk-crescent, shortened: the first still runs past the sentence the split lands on. */
function chalkCrescent(): NarrationBlockV2 {
  return rowOf(
    CHALK,
    "A chalk crescent was drawn on the slate. The shape simply marked the moment. They can stay until someone else needs the slate. Since then the crescent has company.",
    [{ at: 0, still: "S1" }, { at: 14, onCamera: "OC1", framing: "wide" }, { at: 23, still: "S2" }],
  );
}

const TWENTY = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty";
/** [S1 0-9, OC 9-14, S2 14-20] */
const stills = (row: number): NarrationBlockV2 =>
  rowOf(row, TWENTY, [{ at: 0, still: "S1" }, { at: 9, onCamera: "OC1" }, { at: 14, still: "S2" }]);
const selection = (row: number, first: number, last: number) => ({ startTokenId: tokenId(row, first), endTokenId: tokenId(row, last) });

describe("#579 split a row", () => {
  it("chalk crescent: the visual stays in the first row, clipped; the second row opens with one full Wide On Camera card, then the slate still", () => {
    const start = documentOf([chalkCrescent()]);
    expectSound(start);
    expect(cards(start, rowId(CHALK))).toEqual(["S1 0-14", "OC wide 14-23", "S2 23-29"]);

    const session = createRowEditSessionV2(start);
    const result = session.apply({ kind: "split_row", rowId: rowId(CHALK), newRowId: NEW_ROW, at: { beforeTokenId: tokenId(CHALK, 8) } });
    expect(result.ok).toBe(true);
    expectSound(result.document);
    expect(narration(result.document).map((row) => row.id)).toEqual([rowId(CHALK), NEW_ROW]);
    expect(find(result.document, rowId(CHALK)).text).toBe("A chalk crescent was drawn on the slate.");
    expect(find(result.document, NEW_ROW).text).toBe("The shape simply marked the moment. They can stay until someone else needs the slate. Since then the crescent has company.");
    expect(cards(result.document, rowId(CHALK))).toEqual(["S1 0-8"]);
    expect(cards(result.document, NEW_ROW)).toEqual(["OC wide 0-15", "S2 15-21"]);
    // The words keep their identities, and the authored Wide passage keeps its own.
    expect([...tokenIds(find(result.document, rowId(CHALK))), ...tokenIds(find(result.document, NEW_ROW))]).toEqual(tokenIds(chalkCrescent()));
    expect(find(result.document, NEW_ROW).primaryVisualSequence!.slots.map((slot) => nameOf(slot.id))).toEqual(["OC1", "S2"]);

    // One Undo restores the row.
    expect(session.undoDepth).toBe(1);
    expect(session.undo().document.activeDraft.blocks).toEqual(start.activeDraft.blocks);
  });

  it("with no words on one side of the cursor there is nothing to split: refused, pointing at Add row", () => {
    const start = documentOf([stills(1)]);
    expectRefused(start, { kind: "split_row", rowId: rowId(1), newRowId: NEW_ROW, at: { beforeTokenId: null } }, "ROW_SPLIT_NO_WORDS");
    expectRefused(start, { kind: "split_row", rowId: rowId(1), newRowId: NEW_ROW, at: { beforeTokenId: tokenId(1, 0) } }, "ROW_SPLIT_NO_WORDS");
  });

  it("from a selection with the first word: the new row goes above and the visual that starts there travels, clipped to the selection", () => {
    const result = apply(documentOf([stills(1)]), { kind: "split_row", rowId: rowId(1), newRowId: NEW_ROW, at: selection(1, 0, 4) });
    expect(narration(result).map((row) => row.id)).toEqual([NEW_ROW, rowId(1)]);
    expect(words(find(result, NEW_ROW))).toBe("one two three four five");
    expect(cards(result, NEW_ROW)).toEqual(["S1 0-5"]);
    // The original row keeps its ID; the words S1 left behind go to On Camera.
    expect(cards(result, rowId(1))).toEqual(["OC wide 0-9", "S2 9-15"]);
  });

  it("from a selection with the last word: the new row goes below and takes the visuals that start in it", () => {
    const result = apply(documentOf([stills(1)]), { kind: "split_row", rowId: rowId(1), newRowId: NEW_ROW, at: selection(1, 12, 19) });
    expect(narration(result).map((row) => row.id)).toEqual([rowId(1), NEW_ROW]);
    expect(cards(result, rowId(1))).toEqual(["S1 0-9", "OC wide 9-12"]);
    expect(cards(result, NEW_ROW)).toEqual(["OC wide 0-2", "S2 2-8"]);
  });

  it("keeps a Tight choice on both sides when the split lands inside an On Camera passage", () => {
    const row = rowOf(1, TWENTY, [{ at: 0, still: "S1" }, { at: 9, onCamera: "OC1", framing: "tight" }]);
    const result = apply(documentOf([row]), { kind: "split_row", rowId: rowId(1), newRowId: NEW_ROW, at: { beforeTokenId: tokenId(1, 15) } });
    expect(cards(result, rowId(1))).toEqual(["S1 0-9", "OC tight 9-15"]);
    expect(cards(result, NEW_ROW)).toEqual(["OC tight 0-5"]);
  });

  it("a cutaway that starts after the split moves on its own; the visual it sat inside is clipped", () => {
    const row = rowOf(1, TWENTY, [{ at: 0, still: "S1" }, { at: 6, still: "S2", in: "S1" }, { at: 12, resume: "R1", of: "S1" }]);
    const start = documentOf([row]);
    expect(cards(start, rowId(1))).toEqual(["S1 0-6", "S2 6-12", "S1 resumes 12-20"]);
    const result = apply(start, { kind: "split_row", rowId: rowId(1), newRowId: NEW_ROW, at: { beforeTokenId: tokenId(1, 4) } });
    expect(cards(result, rowId(1))).toEqual(["S1 0-4"]);
    expect(cards(result, NEW_ROW)).toEqual(["OC wide 0-2", "S2 2-8", "OC wide resumes 8-16"]);
  });

  it("refuses a whole-row or mid-row selection, with a reason and no change", () => {
    const start = documentOf([stills(1)]);
    expectRefused(start, { kind: "split_row", rowId: rowId(1), newRowId: NEW_ROW, at: selection(1, 0, 19) }, "ROW_SPLIT_WHOLE_ROW");
    expectRefused(start, { kind: "split_row", rowId: rowId(1), newRowId: NEW_ROW, at: selection(1, 5, 8) }, "ROW_SPLIT_MID_ROW");
    expectRefused(start, { kind: "split_row", rowId: rowId(1), newRowId: rowId(1), at: { beforeTokenId: null } }, "ROW_COMMAND_INVALID");
    expectRefused(start, { kind: "split_row", rowId: rowId(1), newRowId: NEW_ROW, at: { beforeTokenId: tokenId(7, 0) } }, "ROW_SELECTION_INVALID");
  });

  it("a stage direction stays with its first word: a boundary inside it moves to its end", () => {
    const row = rowOf(1, "Hello there [pause here] friend again");
    const result = apply(documentOf([row]), { kind: "split_row", rowId: rowId(1), newRowId: NEW_ROW, at: { beforeTokenId: tokenId(1, 3) } });
    expect(find(result, rowId(1)).text).toBe("Hello there [pause here]");
    expect(find(result, NEW_ROW).text).toBe("friend again");
    // Selecting from inside the direction to the end moves only the words after it.
    const selected = apply(documentOf([row]), { kind: "split_row", rowId: rowId(1), newRowId: NEW_ROW, at: selection(1, 3, 5) });
    expect(find(selected, NEW_ROW).text).toBe("friend again");
    // A direction whose first word is selected moves whole.
    const whole = apply(documentOf([row]), { kind: "split_row", rowId: rowId(1), newRowId: NEW_ROW, at: selection(1, 2, 5) });
    expect(find(whole, rowId(1)).text).toBe("Hello there");
    expect(find(whole, NEW_ROW).text).toBe("[pause here] friend again");
    expect(find(whole, NEW_ROW).tokens.map((token) => token.spoken)).toEqual([false, false, undefined, undefined]);
  });

  it("a paragraph break after the final word moves with the split-off words, and comes back through a join (D137, D138)", () => {
    const row = rowOf(1, "one two three\n");
    const split = apply(documentOf([row]), { kind: "split_row", rowId: rowId(1), newRowId: NEW_ROW, at: { beforeTokenId: tokenId(1, 1) } });
    expect(find(split, rowId(1)).text).toBe("one");
    expect(find(split, NEW_ROW).text).toBe("two three\n");
    const joined = apply(split, { kind: "join_rows", rowId: NEW_ROW, direction: "previous", words: selection(1, 1, 2) });
    expect(narration(joined).map((item) => item.text)).toEqual(["one two three\n"]);
  });

  it("word-anchored notes and overlays follow their words; one that spans the boundary refuses the split", () => {
    const row = stills(1);
    const range = (first: number, last: number) => ({
      blockId: row.id, startTokenId: tokenId(1, first), endTokenId: tokenId(1, last), startAffinity: "before" as const, endAffinity: "after" as const,
      quotedText: row.text.slice(row.tokens[first]!.startOffset, row.tokens[last]!.endOffset), anchorVersion: 1,
    });
    row.annotations = [
      { id: id(71), kind: "performance_note", range: range(1, 2), value: "slowly", includeInPrompter: true, version: 1 },
      { id: id(72), kind: "performance_note", range: range(15, 16), value: "brightly", includeInPrompter: true, version: 1 },
    ];
    const result = apply(documentOf([row]), { kind: "split_row", rowId: rowId(1), newRowId: NEW_ROW, at: { beforeTokenId: tokenId(1, 10) } });
    expect(find(result, rowId(1)).annotations!.map((item) => item.id)).toEqual([id(71)]);
    expect(find(result, NEW_ROW).annotations).toEqual([{ ...row.annotations[1]!, range: { ...range(15, 16), blockId: NEW_ROW } }]);

    expectRefused(documentOf([row]), { kind: "split_row", rowId: rowId(1), newRowId: NEW_ROW, at: { beforeTokenId: tokenId(1, 16) } }, "ROW_ANCHOR_STRADDLES_BOUNDARY");
  });
});

describe("#579 join rows", () => {
  const A = 1;
  const B = 2;
  const pair = (): ScriptDocumentV2 => documentOf([rowOf(A, "alpha beta gamma delta", [{ at: 0, still: "S3" }]), stills(B)]);

  it("to the row above moves only the selected words, with their IDs and the visual that starts on them", () => {
    const result = apply(pair(), { kind: "join_rows", rowId: rowId(B), direction: "previous", words: selection(B, 0, 4) });
    expect(narration(result).map((row) => row.id)).toEqual([rowId(A), rowId(B)]);
    expect(find(result, rowId(A)).text).toBe("alpha beta gamma delta one two three four five");
    expect(tokenIds(find(result, rowId(A))).slice(4)).toEqual([0, 1, 2, 3, 4].map((index) => tokenId(B, index)));
    expect(words(find(result, rowId(B)))).toBe("six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty");
    // S1 started on a selected word, so it travels and ends with the selection; no visual is in two rows.
    expect(cards(result, rowId(A))).toEqual(["S3 0-4", "S1 4-9"]);
    expect(cards(result, rowId(B))).toEqual(["OC wide 0-9", "S2 9-15"]);
  });

  it("to the row below moves only the selected words; a visual that began before them is clipped there", () => {
    const start = documentOf([stills(B), rowOf(A, "alpha beta gamma delta", [{ at: 0, still: "S3" }])]);
    const result = apply(start, { kind: "join_rows", rowId: rowId(B), direction: "next", words: selection(B, 16, 19) });
    expect(find(result, rowId(A)).text).toBe("seventeen eighteen nineteen twenty alpha beta gamma delta");
    expect(tokenIds(find(result, rowId(A))).slice(0, 4)).toEqual([16, 17, 18, 19].map((index) => tokenId(B, index)));
    expect(cards(result, rowId(B))).toEqual(["S1 0-9", "OC wide 9-14", "S2 14-16"]);
    expect(cards(result, rowId(A))).toEqual(["OC wide 0-4", "S3 4-8"]);
  });

  it("the whole row to the row above (Backspace) starts a new paragraph and removes the emptied row (D115)", () => {
    const start = pair();
    find(start, rowId(B)).notes = ["Check the count."];
    const session = createRowEditSessionV2(start);
    const result = session.apply({ kind: "join_rows", rowId: rowId(B), direction: "previous", words: null });
    expect(result.ok).toBe(true);
    expectSound(result.document);
    expect(narration(result.document).map((row) => row.id)).toEqual([rowId(A)]);
    const joined = find(result.document, rowId(A));
    expect(joined.text).toBe(`alpha beta gamma delta\n${TWENTY}`);
    expect(tokenIds(joined)).toEqual([...tokenIds(find(start, rowId(A))), ...tokenIds(find(start, rowId(B)))]);
    expect(joined.notes).toEqual(["Check the count."]);
    expect(cards(result.document, rowId(A))).toEqual(["S3 0-4", "S1 4-13", "OC wide 13-18", "S2 18-24"]);
    expect(session.undoDepth).toBe(1);
    expect(session.undo().document.activeDraft.blocks).toEqual(start.activeDraft.blocks);
  });

  it("refuses across a section break, at the script's edge and for a mid-row selection, with no change", () => {
    const start = documentOf([rowOf(A, "alpha beta gamma delta"), section(50), stills(B)]);
    expectRefused(start, { kind: "join_rows", rowId: rowId(B), direction: "previous", words: null }, "ROW_JOIN_SECTION_BREAK");
    expectRefused(start, { kind: "join_rows", rowId: rowId(A), direction: "next", words: selection(A, 2, 3) }, "ROW_JOIN_SECTION_BREAK");
    expectRefused(start, { kind: "join_rows", rowId: rowId(A), direction: "previous", words: null }, "ROW_JOIN_NO_NEIGHBOUR");
    expectRefused(pair(), { kind: "join_rows", rowId: rowId(B), direction: "previous", words: selection(B, 3, 6) }, "ROW_JOIN_MID_ROW");
    expectRefused(pair(), { kind: "join_rows", rowId: rowId(B), direction: "previous", words: selection(B, 12, 19) }, "ROW_JOIN_MID_ROW");
  });

  it("a wordless row's placed visual is kept for Attach to words when the row is joined away", () => {
    const wordless = rowOf(B, "[hold here]", []);
    wordless.primaryVisualSequence!.slots = [stills(B).primaryVisualSequence!.slots[0]!];
    const result = apply(documentOf([rowOf(A, "alpha beta gamma delta"), wordless]), { kind: "join_rows", rowId: rowId(B), direction: "previous", words: null });
    expect(narration(result).map((row) => row.id)).toEqual([rowId(A)]);
    expect(find(result, rowId(A)).text).toBe("alpha beta gamma delta\n[hold here]");
    expect(cards(result, rowId(A))).toEqual(["OC wide 0-4", "S1 unattached"]);
  });
});

describe("#579 split then join (D124)", () => {
  const splitChalk: RowEditCommandV2 = { kind: "split_row", rowId: rowId(CHALK), newRowId: NEW_ROW, at: { beforeTokenId: tokenId(CHALK, 8) } };
  const backspace: RowEditCommandV2 = { kind: "join_rows", rowId: NEW_ROW, direction: "previous", words: null };

  it("joining straight back restores the row exactly, including the clipped visual's range", () => {
    const start = documentOf([chalkCrescent()]);
    const session = createRowEditSessionV2(start);
    expect(session.apply(splitChalk).ok).toBe(true);
    const joined = session.apply(backspace);
    expect(joined.ok).toBe(true);
    expect(joined.document.activeDraft.blocks).toEqual(start.activeDraft.blocks);
    expect(cards(joined.document, rowId(CHALK))).toEqual(["S1 0-14", "OC wide 14-23", "S2 23-29"]);
    expect(joined.document.rowEditRevision).toBe(2);
    // The join is its own Undo step: one Undo returns to the two rows, a second to the original.
    expect(session.undoDepth).toBe(2);
    expect(narration(session.undo().document).map((row) => row.id)).toEqual([rowId(CHALK), NEW_ROW]);
    expect(session.undo().document.activeDraft.blocks).toEqual(start.activeDraft.blocks);
  });

  it("still restores the split after an intervening command is refused", () => {
    const start = documentOf([chalkCrescent()]);
    const session = createRowEditSessionV2(start);
    const split = session.apply(splitChalk);
    expect(split.ok).toBe(true);
    const refused = session.apply({ kind: "join_rows", rowId: NEW_ROW, direction: "next", words: null });
    expect(refused.ok).toBe(false);
    expect(refused.diagnostics.map((item) => item.code)).toEqual(["ROW_JOIN_NO_NEIGHBOUR"]);
    expect(refused.document).toEqual(split.document);
    expect(session.undoDepth).toBe(1);

    const joined = session.apply(backspace);
    expect(joined.ok).toBe(true);
    expect(joined.document.activeDraft.blocks).toEqual(start.activeDraft.blocks);
  });

  it("an edit in between makes it an ordinary join: a new paragraph, and the visual stays clipped", () => {
    const session = createRowEditSessionV2(documentOf([chalkCrescent()]));
    expect(session.apply(splitChalk).ok).toBe(true);
    const framed = session.applyVisualEdit({
      kind: "set_on_camera_framing", blockId: NEW_ROW, slotId: slotId(CHALK, "OC1"), framing: "tight",
    });
    expect(framed.ok).toBe(true);
    const joined = session.apply(backspace);
    expect(joined.ok).toBe(true);
    expectSound(joined.document);
    const row = find(joined.document, rowId(CHALK));
    expect(row.text).toBe(chalkCrescent().text.replace("slate. The shape", "slate.\nThe shape"));
    expect(tokenIds(row)).toEqual(tokenIds(chalkCrescent()));
    expect(cards(joined.document, rowId(CHALK))).toEqual(["S1 0-8", "OC tight 8-23", "S2 23-29"]);
  });

  it("an Undo and a fresh split, or a join of other rows, do not restore", () => {
    const start = documentOf([chalkCrescent(), rowOf(2, "alpha beta gamma delta")]);
    const session = createRowEditSessionV2(start);
    session.apply(splitChalk);
    // Joining the unrelated third row is an ordinary join and uses up the restore.
    expect(session.apply({ kind: "join_rows", rowId: rowId(2), direction: "previous", words: null }).ok).toBe(true);
    const joined = session.apply(backspace);
    expect(joined.ok).toBe(true);
    expect(cards(joined.document, rowId(CHALK)).slice(0, 2)).toEqual(["S1 0-8", "OC wide 8-23"]);
  });

  it("outside a session there is no memory of the split, so a join is always the ordinary join", () => {
    const split = apply(documentOf([chalkCrescent()]), splitChalk);
    const joined = apply(split, backspace);
    expect(cards(joined, rowId(CHALK))).toEqual(["S1 0-8", "OC wide 8-23", "S2 23-29"]);
  });
});

describe("#579 split/join review regressions", () => {
  function wordlessWithPayload(row: number, payload: ContentSlot["payload"]): NarrationBlockV2 {
    const block = rowOf(row, "[hold here]", [{ at: 0, onCamera: "OC1" }]);
    const slot = block.primaryVisualSequence!.slots[0];
    if (!slot || slot.kind !== "content") throw new Error("Expected the wordless row's base slot.");
    block.primaryVisualSequence!.slots[0] = { ...slot, payload };
    return block;
  }

  const undefinedPayload = (row: number): ContentSlot["payload"] => ({
    kind: "undefined", payloadId: id(row * 100_000 + 90_001), description: "Need aerial of bridge",
  });

  it("keeps a wordless destination's placed visual as unattached when spoken words join it", () => {
    const visual = rowOf(299, "picture", [{ at: 0, still: "S1" }]).primaryVisualSequence!.slots[0];
    if (!visual || visual.kind !== "content" || visual.payload.kind !== "visual") throw new Error("Expected a visual slot.");
    const destination = wordlessWithPayload(210, visual.payload);
    const source = rowOf(211, "New spoken words");
    const result = apply(documentOf([destination, source]), {
      kind: "join_rows", rowId: rowId(211), direction: "previous", words: null,
    });

    expect(find(result, rowId(210)).unattachedVisuals).toEqual([{
      slotId: slotId(210, "OC1"), payload: visual.payload, version: 1,
    }]);
    expect(cards(result, rowId(210))).toContain("OC1 unattached");
  });

  it("refuses when a wordless source's undefined picture or chosen On Camera take cannot be preserved", () => {
    const undefinedSource = wordlessWithPayload(220, undefinedPayload(220));
    const chosenTake = wordlessWithPayload(222, { kind: "on_camera", presenterChoiceId: id(900_222), framing: "tight" });
    for (const source of [undefinedSource, chosenTake]) {
      expectRefused(documentOf([rowOf(221, "Previous words"), source]), {
        kind: "join_rows", rowId: source.id, direction: "previous", words: null,
      }, "ROW_SPLIT_JOIN_UNSUPPORTED");
    }
  });

  it("refuses when a wordless destination's undefined picture or chosen take cannot be kept", () => {
    const undefinedDestination = wordlessWithPayload(230, undefinedPayload(230));
    const chosenTake = wordlessWithPayload(232, { kind: "on_camera", presenterChoiceId: null, framing: "tight" });
    for (const destination of [undefinedDestination, chosenTake]) {
      expectRefused(documentOf([destination, rowOf(231, "Incoming words")]), {
        kind: "join_rows", rowId: rowId(231), direction: "previous", words: null,
      }, "ROW_SPLIT_JOIN_UNSUPPORTED");
    }

    const generated = apply(documentOf([rowOf(234, "[hold here]"), rowOf(235, "Incoming words")]), {
      kind: "join_rows", rowId: rowId(235), direction: "previous", words: null,
    });
    expect(words(find(generated, rowId(234)))).toContain("Incoming");
  });

  it("follows a saved card reference when its card moves and refuses if the card becomes unattached", () => {
    const cardId = slotId(241, "S1");
    const reference = (owner: number, card: string) => ({
      id: id(owner), rowId: rowId(owner), kind: "reference" as const,
      anchor: { kind: "card", blockId: rowId(owner), cardId: card },
    });
    const moving = documentOf([rowOf(240, "Prior words"), stills(241)], {
      rowReferences: [reference(241, cardId)],
    });
    const result = apply(moving, {
      kind: "join_rows", rowId: rowId(241), direction: "previous", words: selection(241, 0, 4),
    });
    expect(result.rowReferences).toEqual([{
      ...reference(241, cardId), rowId: rowId(240),
      anchor: { ...reference(241, cardId).anchor, blockId: rowId(240) },
    }]);

    const visual = rowOf(299, "picture", [{ at: 0, still: "S1" }]).primaryVisualSequence!.slots[0];
    if (!visual || visual.kind !== "content" || visual.payload.kind !== "visual") throw new Error("Expected a visual slot.");
    const destination = wordlessWithPayload(242, visual.payload);
    expectRefused(documentOf([destination, rowOf(243, "Incoming words")], {
      rowReferences: [reference(242, slotId(242, "OC1"))],
    }), { kind: "join_rows", rowId: rowId(243), direction: "previous", words: null }, "ROW_REFERENCE_REVIEW_REQUIRED");
  });

  it("keeps supporting-item gap endpoints in their documented order", () => {
    const gap = (value: number, before: number, after: number) => ({
      id: id(value), version: 1, orderKey: `support-${value}`, role: "editor_note" as const, content: "Review this gap",
      placement: { kind: "point" as const, anchor: { kind: "between_blocks" as const, beforeBlockId: rowId(before), afterBlockId: rowId(after) } },
    });
    const [a, b, c] = [250, 251, 252].map((row) => rowOf(row, `Words in ${row}`));
    const crossing = documentOf([a!, b!], { activeDraft: { blocks: [a!, b!], supportingItems: [gap(254, 250, 251)] } });
    expectRefused(crossing, { kind: "join_rows", rowId: rowId(251), direction: "previous", words: null }, "ROW_REFERENCE_REVIEW_REQUIRED");

    const trailingGap = gap(255, 251, 252);
    const beforeSplit = documentOf([a!, b!, c!], { activeDraft: { blocks: [a!, b!, c!], supportingItems: [trailingGap] } });
    const split = apply(beforeSplit, {
      kind: "split_row", rowId: rowId(251), newRowId: NEW_ROW, at: { beforeTokenId: tokenId(251, 2) },
    });
    expect(split.activeDraft.supportingItems[0]!.placement).toEqual({
      kind: "point", anchor: { kind: "between_blocks", beforeBlockId: NEW_ROW, afterBlockId: rowId(252) },
    });
  });
});

describe("#579 what still points at a split or joined row", () => {
  it("follows a music cue's word and trailing edge through a split and join", () => {
    const row = rowOf(1, "one two three four");
    const cue = span(70, row.id, row.id);
    const word = row.tokens[2]!;
    cue.timing = {
      sourceInFrame: 0,
      timelineIn: { kind: "word", anchor: { blockId: row.id, tokenId: word.id, affinity: "before", quotedWord: word.value, anchorVersion: row.version } },
      timelineOut: { kind: "row_edge", blockId: row.id, edge: "end" },
    };
    const initial = documentOf([row], { rowAudioSpans: [cue] });
    const split = apply(initial, { kind: "split_row", rowId: row.id, newRowId: NEW_ROW, at: { beforeTokenId: word.id } });
    expect(split.rowAudioSpans?.[0]).toMatchObject({
      endRowId: NEW_ROW,
      timing: { timelineIn: { anchor: { blockId: NEW_ROW, tokenId: word.id } }, timelineOut: { blockId: NEW_ROW, edge: "end" } },
    });
    const joined = apply(split, { kind: "join_rows", rowId: NEW_ROW, direction: "previous", words: null });
    expect(joined.rowAudioSpans).toEqual([cue]);
  });

  const A = 1;
  const B = 2;
  const C = 3;
  const plain = (row: number): NarrationBlockV2 => rowOf(row, `r${row}a r${row}b r${row}c r${row}d`);
  const span = (value: number, startRowId: string, endRowId: string): RowAudioSpanIntentV2 => ({
    id: id(value), startRowId, endRowId,
    source: { mediaReferenceId: id(value + 1), artifactId: id(value + 2), artifactVersion: 1, contentHash: `sha256:${"b".repeat(64)}` },
    settings: { gainDb: -12 },
  });
  const transition = (value: number, fromRowId: string, toRowId: string) =>
    ({ id: id(value), fromRowId, toRowId, effect: "crossfade", settings: { frames: 6 }, state: "active" as const });

  it("split: the outgoing transition and a music cue's end follow the last words to the new row", () => {
    const start = documentOf([plain(A), plain(B), plain(C)], {
      rowTransitions: [transition(60, rowId(A), rowId(B)), transition(61, rowId(B), rowId(C))],
      rowAudioSpans: [span(70, rowId(A), rowId(B))],
    });
    const result = apply(start, { kind: "split_row", rowId: rowId(B), newRowId: NEW_ROW, at: { beforeTokenId: tokenId(B, 2) } });
    expect(result.rowTransitions).toEqual([transition(60, rowId(A), rowId(B)), transition(61, NEW_ROW, rowId(C))]);
    expect(result.rowAudioSpans).toEqual([span(70, rowId(A), NEW_ROW)]);
    // A selection split that puts the new row above moves the incoming side instead.
    const above = apply(start, { kind: "split_row", rowId: rowId(B), newRowId: NEW_ROW, at: selection(B, 0, 1) });
    expect(above.rowTransitions).toEqual([transition(60, rowId(A), NEW_ROW), transition(61, rowId(B), rowId(C))]);
    expect(above.rowAudioSpans).toEqual([span(70, rowId(A), rowId(B))]);
  });

  it("join: references to the removed row move to the joined row when they still mean the same place", () => {
    const start = documentOf([plain(A), plain(B), plain(C)], {
      rowTransitions: [transition(61, rowId(B), rowId(C))],
      rowAudioSpans: [span(70, rowId(A), rowId(B))],
    });
    const result = apply(start, { kind: "join_rows", rowId: rowId(B), direction: "previous", words: null });
    expect(result.rowTransitions).toEqual([transition(61, rowId(A), rowId(C))]);
    expect(result.rowAudioSpans).toEqual([span(70, rowId(A), rowId(A))]);
  });

  it("join: refused when a transition sits between the rows or a music cue covers only one of them", () => {
    const between = documentOf([plain(A), plain(B)], { rowTransitions: [transition(60, rowId(A), rowId(B))] });
    expectRefused(between, { kind: "join_rows", rowId: rowId(B), direction: "previous", words: null }, "ROW_REFERENCE_REVIEW_REQUIRED");
    // Moving only some words keeps both rows, so the transition between them stays valid.
    const partial = apply(between, { kind: "join_rows", rowId: rowId(B), direction: "previous", words: selection(B, 0, 1) });
    expect(partial.rowTransitions).toEqual(between.rowTransitions);

    const music = documentOf([plain(A), plain(B), plain(C)], { rowAudioSpans: [span(70, rowId(B), rowId(C))] });
    expectRefused(music, { kind: "join_rows", rowId: rowId(B), direction: "previous", words: null }, "ROW_REFERENCE_REVIEW_REQUIRED");
    expectRefused(music, { kind: "join_rows", rowId: rowId(B), direction: "previous", words: selection(B, 0, 1) }, "ROW_REFERENCE_REVIEW_REQUIRED");
    expectRefused(music, { kind: "join_rows", rowId: rowId(A), direction: "next", words: selection(A, 2, 3) }, "ROW_REFERENCE_REVIEW_REQUIRED");
    // Inside the cue, words can move freely.
    expect(apply(music, { kind: "join_rows", rowId: rowId(C), direction: "previous", words: selection(C, 0, 1) }).rowAudioSpans).toEqual(music.rowAudioSpans);
  });

  it("a saved word comment follows its words to their new row; one spanning the boundary refuses the edit", () => {
    const reference = (value: number, first: number, last: number) => ({
      id: id(value), rowId: rowId(B), kind: "comment" as const,
      anchor: { kind: "text", blockId: rowId(B), startTokenId: tokenId(B, first), endTokenId: tokenId(B, last) },
    });
    const start = documentOf([plain(A), plain(B)], { rowReferences: [reference(80, 0, 1), reference(81, 2, 3)] });
    const result = apply(start, { kind: "split_row", rowId: rowId(B), newRowId: NEW_ROW, at: { beforeTokenId: tokenId(B, 2) } });
    expect(result.rowReferences).toEqual([
      reference(80, 0, 1),
      { ...reference(81, 2, 3), rowId: NEW_ROW, anchor: { ...reference(81, 2, 3).anchor, blockId: NEW_ROW } },
    ]);
    expectRefused(documentOf([plain(A), plain(B)], { rowReferences: [reference(82, 1, 2)] }),
      { kind: "split_row", rowId: rowId(B), newRowId: NEW_ROW, at: { beforeTokenId: tokenId(B, 2) } }, "ROW_REFERENCE_REVIEW_REQUIRED");
  });

  it("a comment thread on moved words stays attached, in the row that now holds them", () => {
    const start = documentOf([plain(A), plain(B)]);
    let comments = createCommentStateV2(start);
    const created = applyCommentOperationV2(comments, 0, {
      id: "op-1", actorId: "writer", kind: "create", threadId: "thread-1", messageId: "message-1", body: "Check this.", mentionActorIds: [],
      anchor: { kind: "text", blockId: rowId(B), startTokenId: tokenId(B, 2), endTokenId: tokenId(B, 3) },
    });
    expect(created.ok).toBe(true);
    comments = created.state;
    const split = apply(start, { kind: "split_row", rowId: rowId(B), newRowId: NEW_ROW, at: { beforeTokenId: tokenId(B, 2) } });
    const replaced = applyCommentOperationV2(comments, 1, { id: "op-2", actorId: "writer", kind: "replace_document", document: split });
    expect(replaced.ok).toBe(true);
    expect(replaced.state.threads[0]!.attachment).toMatchObject({
      status: "attached", quotedText: "r2c r2d",
      anchor: { kind: "text", blockId: NEW_ROW, startTokenId: tokenId(B, 2), endTokenId: tokenId(B, 3) },
    });
  });
});
