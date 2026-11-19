import { describe, expect, it } from "vitest";
import { ADD_VISUAL_TYPES, selectedSpokenWords } from "../browser/visual-selection.js";

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
