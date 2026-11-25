import { describe, expect, it } from "vitest";

import { parseHoldSeconds, planVisualOnlyReorder, visualOnlyIds } from "../browser/visual-only-actions.js";

const row = {
  type: "visual_only", id: "row",
  payload: { payloadId: "still-a" },
  additionalVisuals: [
    { payload: { payloadId: "clip-b" } },
    { payload: { payloadId: "still-c" } },
  ],
};

describe("wordless picture controls use the exact model command shape", () => {
  it("moves a whole placement to an exact permutation without changing the saved row", () => {
    expect(visualOnlyIds(row)).toEqual(["still-a", "clip-b", "still-c"]);
    expect(planVisualOnlyReorder(row, "still-c", "clip-b")).toEqual({
      kind: "reorder_visual_only", rowId: "row", payloadIds: ["still-a", "still-c", "clip-b"],
    });
    expect(planVisualOnlyReorder(row, "still-a", null)).toEqual({
      kind: "reorder_visual_only", rowId: "row", payloadIds: ["clip-b", "still-c", "still-a"],
    });
    expect(row.additionalVisuals.map((item) => item.payload.payloadId)).toEqual(["clip-b", "still-c"]);
  });

  it("refuses no-op, missing/self target, duplicate and invalid row shapes", () => {
    expect(planVisualOnlyReorder(row, "still-a", "clip-b")).toBeNull();
    expect(planVisualOnlyReorder(row, "still-a", "still-a")).toBeNull();
    expect(planVisualOnlyReorder(row, "missing", "clip-b")).toBeNull();
    expect(planVisualOnlyReorder(row, "still-a", "missing")).toBeNull();
    expect(planVisualOnlyReorder({ ...row, additionalVisuals: [] }, "still-a")).toBeNull();
    expect(visualOnlyIds({ ...row, additionalVisuals: [{ payload: { payloadId: "still-a" } }] })).toBeNull();
    expect(visualOnlyIds({ ...row, additionalVisuals: {} })).toBeNull();
    expect(visualOnlyIds({ ...row, type: "narration" })).toBeNull();
  });

  it("parses positive holds to integral milliseconds without exponent or overflow", () => {
    for (const [raw, seconds] of [["6.0", 6], [" 2.500 ", 2.5], ["1.001", 1.001], [".001", 0.001], ["4", 4]] as const) {
      expect(parseHoldSeconds(raw)).toBe(seconds);
    }
    for (const raw of ["", "-2", "0", "0.000", "NaN", "Infinity", "4e2", "1.0009", "abc", "1.", "9007199254740992", 6]) {
      expect(parseHoldSeconds(raw)).toBeNull();
    }
  });
});
