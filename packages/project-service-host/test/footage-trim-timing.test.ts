import { describe, expect, it } from "vitest";
import { cueExcerpt } from "../browser/footage-trim-timing.js";

describe("caption timing fallback", () => {
  const cues = [
    { startMs: 133, endMs: 1468, text: "First caption" },
    { startMs: 1468, endMs: 5205, text: "Second caption" },
  ];
  it("returns only overlapping cues and marks cut edges as approximate", () => {
    expect(cueExcerpt(cues, 800, 3336, "Full transcript")).toEqual({
      kind: "cue", text: "… First caption Second caption …", note: "Approximate excerpt from caption timing.",
    });
    expect(cueExcerpt(cues, 1468, 5205, "Full transcript")).toMatchObject({ kind: "cue", text: "Second caption" });
  });
  it("never invents silence, words, or timing from missing or malformed evidence", () => {
    for (const evidence of [null, [], [{ startMs: 100, endMs: 99, text: "bad" }], cues]) {
      expect(cueExcerpt(evidence, 5205, 6000, "Full transcript")).toMatchObject({ kind: "full", text: "Full transcript" });
    }
    expect(cueExcerpt(cues, 3336, 800, "Full transcript")).toMatchObject({ kind: "full" });
  });
});
