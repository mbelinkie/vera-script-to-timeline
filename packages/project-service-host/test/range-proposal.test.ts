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
    expect(stepVisualBracket(bracket, "end", -99, 7)).toEqual({ startIndex: 0, endIndexExclusive: 1 });
    expect(stepVisualBracket(bracket, "end", 99, 7)).toEqual({ startIndex: 0, endIndexExclusive: 7 });
    expect(stepVisualBracket(bracket, "start", 99, 7)).toEqual({ startIndex: 2, endIndexExclusive: 3 });
    expect(moveVisualBracket(bracket, "end", 7, 7)).toEqual({ startIndex: 0, endIndexExclusive: 7 });
    expect(moveVisualBracket(bracket, "start", 5, 7)).toEqual({ startIndex: 2, endIndexExclusive: 3 });
    expect(moveVisualBracket(bracket, "end", -3, 7)).toEqual({ startIndex: 0, endIndexExclusive: 1 });
  });
});
