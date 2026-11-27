import { describe, expect, it } from "vitest";
import { ADD_VISUAL_TYPES, captureSelectedDrop, selectedDropPlacement, selectedSpokenWords } from "../browser/visual-selection.js";

const words = [
  { id: "first", value: "😀alpha", startOffset: 0, endOffset: 7 },
  { id: "stage", value: "quiet", startOffset: 9, endOffset: 14, spoken: false },
  { id: "middle", value: "beta", startOffset: 16, endOffset: 20 },
  { id: "last", value: "alpha", startOffset: 21, endOffset: 26 },
];
const row = { text: "😀alpha [quiet] beta alpha", tokens: words };

describe("selected spoken picture cues", () => {
  it("offers exactly the three accepted source-free types", () => {
    expect(ADD_VISUAL_TYPES.map(({ type }) => type)).toEqual([
      "onscreen_placeholder", "need_to_find", "visual_undefined",
    ]);
  });

  it("snaps first and last partial words using UTF-16 offsets and preserves repeated-token identity", () => {
    expect(selectedSpokenWords(row, { start: 2, end: 3 }, true)).toMatchObject({
      startTokenId: "first", endTokenId: "first", startOffset: 0, endOffset: 7,
    });
    expect(selectedSpokenWords(row, { start: 22, end: 25 }, true)).toMatchObject({
      startTokenId: "last", endTokenId: "last", startOffset: 21, endOffset: 26,
    });
    expect(selectedSpokenWords(row, { start: 3, end: 25 }, true)).toMatchObject({
      startTokenId: "first", endTokenId: "last",
    });
  });

  it("refuses a collapsed, whitespace-only, direction-only or plain-direction selection", () => {
    for (const range of [{ start: 0, end: 0 }, { start: 7, end: 8 },
      { start: 9, end: 14 }, { start: -1, end: 3 }, { start: 0, end: 27 }]) {
      expect(selectedSpokenWords(row, range)).toBeNull();
    }
    expect(selectedSpokenWords({ ...row, plainDirection: true }, { start: 0, end: 7 })).toBeNull();
  });

  it("excludes stage tokens from visual endpoints and waits for real committed IDs", () => {
    expect(selectedSpokenWords(row, { start: 9, end: 20 }, true)).toMatchObject({
      startTokenId: "middle", endTokenId: "middle",
    });
    const optimistic = { ...row, tokens: words.map((token) => ({
      startOffset: token.startOffset, endOffset: token.endOffset,
      ...("spoken" in token ? { spoken: token.spoken } : {}),
    })) };
    expect(selectedSpokenWords(optimistic, { start: 16, end: 20 })).toMatchObject({
      startOffset: 16, endOffset: 20, startTokenId: null,
    });
    expect(selectedSpokenWords(optimistic, { start: 16, end: 20 }, true)).toBeNull();
  });
});

describe("strict selected drop snapshots", () => {
  const committed = { ...row, id: "row", type: "narration", state: "active", version: 4,
    primaryVisualSequence: { version: 7 } };
  const model = { id: "document", projectId: "project", activeDraft: { blocks: [committed] } };
  const target = { rowId: "row", text: row.text, rowVersion: 4, sequenceVersion: 7,
    selected: true, selection: { start: 17, end: 25 } };

  it("freezes the exact spoken identities including partial and repeated words", () => {
    const input = structuredClone(target);
    const snapshot = captureSelectedDrop(model, input);
    expect(snapshot).toMatchObject({ startTokenId: "middle", endTokenId: "last", startOffset: 16, endOffset: 26 });
    expect(Object.isFrozen(snapshot)).toBe(true);
    expect(Object.isFrozen(snapshot?.selection)).toBe(true);
    input.selection.start = 0;
    expect(selectedDropPlacement(structuredClone(model), snapshot)).toEqual({
      kind: "selected_words", rowId: "row", expectedRowVersion: 4,
      expectedSequenceVersion: 7, startTokenId: "middle", endTokenId: "last",
    });
  });

  it("rejects missing committed identity, invalid selection and stale capture", () => {
    for (const invalid of [
      { ...target, selected: false }, { ...target, rowId: "other" },
      { ...target, text: "changed" }, { ...target, rowVersion: 3 },
      { ...target, sequenceVersion: undefined }, { ...target, sequenceVersion: 8 },
      { ...target, selection: { start: 9, end: 14 } },
      { ...target, selection: { start: 17, end: 17 } },
    ]) expect(captureSelectedDrop(model, invalid)).toBeNull();
    for (const changed of [
      { ...committed, state: "excluded" }, { ...committed, plainDirection: true },
      { ...committed, tokens: words.map((word) => ({ ...word, id: undefined })) },
      { ...committed, primaryVisualSequence: { version: NaN } },
      { ...committed, version: 0 },
    ]) expect(captureSelectedDrop({ ...model, activeDraft: { blocks: [changed] } }, target)).toBeNull();
    expect(captureSelectedDrop({ ...model, activeDraft: { blocks: [
      { ...committed, version: Number.MAX_SAFE_INTEGER },
    ] } }, { ...target, rowVersion: Number.MAX_SAFE_INTEGER })).toBeNull();
  });

  it("refuses a changed project, document, row, range, or sequence instead of retargeting", () => {
    const snapshot = captureSelectedDrop(model, target);
    expect(snapshot).not.toBeNull();
    for (const changed of [
      { ...model, projectId: "different" }, { ...model, id: "different" },
      { ...model, activeDraft: { blocks: [] } },
      ...[
        { ...committed, text: "different text" },
        { ...committed, version: 5 },
        { ...committed, state: "excluded" },
        { ...committed, primaryVisualSequence: { version: 8 } },
        { ...committed, tokens: words.map((word) => word.id === "last" ? { ...word, id: "replacement" } : word) },
        { ...committed, tokens: words.map((word) => word.id === "middle" ? { ...word, startOffset: 17 } : word) },
      ].map((changedRow) => ({ ...model, activeDraft: { blocks: [changedRow] } })),
    ]) expect(selectedDropPlacement(changed, snapshot)).toBeNull();
  });
});
