import { describe, expect, it } from "vitest";
import { moveVisualBracket, proposeVisualRange, stepVisualBracket } from "../browser/range-proposal.js";

const projection = {
  blockId: "row-1",
  tokens: Array.from({ length: 7 }, (_, index) => ({ tokenId: `word-${index}` })),
  brackets: [
    { slotId: "still-1", startTokenIndex: 0, endTokenIndexExclusive: 3 },
    { slotId: "still-2", startTokenIndex: 4, endTokenIndexExclusive: 7 },
  ],
};

describe("#66 bracket proposals use projected spoken word identities", () => {
  it("translates an inclusive last word exactly once and preserves a neighbouring range", () => {
    expect(proposeVisualRange(projection, "still-1", 0, 2)).toMatchObject({
      ok: true, wordCount: 2,
      setCommand: { kind: "set_visual_range", blockId: "row-1", slotId: "still-1",
        startTokenId: "word-0", endTokenId: "word-1" },
      swapCommand: null,
    });
    expect(projection.brackets[1]).toEqual({ slotId: "still-2", startTokenIndex: 4, endTokenIndexExclusive: 7 });
  });

  it("offers exact-match swap only, and never commits empty, stale, or unchanged ranges", () => {
    expect(proposeVisualRange(projection, "still-1", 4, 7)).toMatchObject({
      swapCommand: { kind: "swap_ranges", firstSlotId: "still-1", secondSlotId: "still-2" },
    });
    expect(proposeVisualRange(projection, "still-1", 4, 6)).toMatchObject({ swapCommand: null });
    for (const [start, end] of [[0, 3], [3, 3], [-1, 3], [2, 8]] as const) {
      expect(proposeVisualRange(projection, "still-1", start, end).ok).toBe(false);
    }
    expect(proposeVisualRange(projection, "absent", 0, 1).ok).toBe(false);
  });

  it("steps and drags at word boundaries, keeping at least one word", () => {
    const bracket = projection.brackets[0]!;
    const context = { originalRange: bracket, brackets: [bracket] };
    expect(stepVisualBracket(bracket, "end", -99, 7, context)).toEqual({ startIndex: 0, endIndexExclusive: 1 });
    expect(stepVisualBracket(bracket, "end", 99, 7, context)).toEqual({ startIndex: 0, endIndexExclusive: 7 });
    expect(stepVisualBracket(bracket, "start", 99, 7, context)).toEqual({ startIndex: 2, endIndexExclusive: 3 });
    expect(moveVisualBracket(bracket, "end", 7, 7, context)).toEqual({ startIndex: 0, endIndexExclusive: 7 });
    expect(moveVisualBracket(bracket, "start", 5, 7, context)).toEqual({ startIndex: 2, endIndexExclusive: 3 });
    expect(moveVisualBracket(bracket, "end", -3, 7, context)).toEqual({ startIndex: 0, endIndexExclusive: 1 });
  });

  it("D192 clamps both edges before consuming the last word of a projected non-camera neighbour", () => {
    // The middle [9,18) passage is On Camera: it has no projected bracket.
    const left = { startTokenIndex: 0, endTokenIndexExclusive: 9 };
    const right = { startTokenIndex: 18, endTokenIndexExclusive: 26 };
    const brackets = [left, right];
    const leftContext = { originalRange: left, brackets };
    const rightContext = { originalRange: right, brackets };
    expect(moveVisualBracket(left, "end", 26, 26, leftContext)).toEqual({ startIndex: 0, endIndexExclusive: 25 });
    expect(stepVisualBracket(left, "end", 100, 26, leftContext)).toEqual({ startIndex: 0, endIndexExclusive: 25 });
    expect(moveVisualBracket(right, "start", 0, 26, rightContext)).toEqual({ startIndex: 9, endIndexExclusive: 26 });
    expect(stepVisualBracket(right, "start", -100, 26, rightContext)).toEqual({ startIndex: 9, endIndexExclusive: 26 });

    // The clamp must remain in force after a pending range overlaps a neighbour.
    const pending = { startTokenIndex: 0, endTokenIndexExclusive: 25 };
    expect(stepVisualBracket(pending, "end", 1, 26, leftContext)).toEqual({ startIndex: 0, endIndexExclusive: 25 });
    expect(moveVisualBracket(pending, "end", 26, 26, leftContext)).toEqual({ startIndex: 0, endIndexExclusive: 25 });
    expect(stepVisualBracket(pending, "end", -1, 26, leftContext)).toEqual({ startIndex: 0, endIndexExclusive: 24 });
    const reversePending = { startTokenIndex: 9, endTokenIndexExclusive: 26 };
    expect(stepVisualBracket(reversePending, "start", -1, 26, rightContext)).toEqual({ startIndex: 9, endIndexExclusive: 26 });
  });

  it("D192 allows whole On Camera coverage but cannot cross a one-word neighbour", () => {
    const middle = { startTokenIndex: 9, endTokenIndexExclusive: 18 };
    const context = { originalRange: middle, brackets: [middle] };
    expect(moveVisualBracket(middle, "end", 26, 26, context)).toEqual({ startIndex: 9, endIndexExclusive: 26 });
    expect(stepVisualBracket(middle, "start", -100, 26, context)).toEqual({ startIndex: 0, endIndexExclusive: 18 });

    const first = { startTokenIndex: 0, endTokenIndexExclusive: 1 };
    const last = { startTokenIndex: 25, endTokenIndexExclusive: 26 };
    const guarded = { originalRange: middle, brackets: [last, middle, first] };
    expect(moveVisualBracket(middle, "start", 0, 26, guarded)).toEqual({ startIndex: 1, endIndexExclusive: 18 });
    expect(stepVisualBracket(middle, "end", 100, 26, guarded)).toEqual({ startIndex: 9, endIndexExclusive: 25 });
  });
});
