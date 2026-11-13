import { describe, expect, it } from "vitest";
import { planMusicSpanFrames, type MusicRowBounds } from "../src/row-audio-music.js";

const rows: MusicRowBounds[] = [
  { id: "A", startFrame: 0, endFrame: 48, sectionId: "first", active: true },
  { id: "B", startFrame: 48, endFrame: 96, sectionId: "first", active: true },
  { id: "C", startFrame: 96, endFrame: 144, sectionId: "first", active: true },
];
const fps = { numerator: 24, denominator: 1 };

describe("music row-span frame placement", () => {
  it("covers three inclusive rows with an exclusive endpoint and fixed fades", () => {
    const result = planMusicSpanFrames(rows, "A", "C", 48000 * 8, 48000, fps);
    expect(result).toEqual({
      recordRange: { startFrame: 0, endFrame: 144 },
      sourceRange: { startFrame: 0, endFrame: 144 },
      requestedEndFrame: 144,
      shorterThanRows: false,
      fadeInFrames: 6,
      fadeOutFrames: 6,
    });
  });

  it("ends a short source early without extending or looping audio", () => {
    const result = planMusicSpanFrames(rows, "B", "C", 48000 * 3, 48000, fps);
    expect(result?.recordRange).toEqual({ startFrame: 48, endFrame: 120 });
    expect(result?.sourceRange).toEqual({ startFrame: 0, endFrame: 72 });
    expect(result?.requestedEndFrame).toBe(144);
    expect(result?.shorterThanRows).toBe(true);
  });

  it("floors fractional source frames rather than requesting unavailable samples", () => {
    const result = planMusicSpanFrames(rows, "A", "A", 1999, 48000, fps);
    expect(result).toBeNull();
    const fullFrame = planMusicSpanFrames(rows, "A", "A", 2000, 48000, fps);
    expect(fullFrame?.recordRange).toEqual({ startFrame: 0, endFrame: 1 });
    expect([fullFrame?.fadeInFrames, fullFrame?.fadeOutFrames]).toEqual([0, 0]);
    const twoFrames = planMusicSpanFrames(rows, "A", "A", 4000, 48000, fps);
    expect([twoFrames?.fadeInFrames, twoFrames?.fadeOutFrames]).toEqual([1, 1]);
  });

  it("rejects reversed, missing, duplicate, inactive, cross-section or broken row spans", () => {
    expect(() => planMusicSpanFrames(rows, "C", "A", 48000, 48000, fps)).toThrow(RangeError);
    expect(() => planMusicSpanFrames(rows, "absent", "C", 48000, 48000, fps)).toThrow(RangeError);
    expect(() => planMusicSpanFrames([...rows, rows[0]!], "A", "C", 48000, 48000, fps)).toThrow(RangeError);
    expect(() => planMusicSpanFrames([rows[0]!, { ...rows[1]!, active: false }], "A", "B", 48000, 48000, fps)).toThrow(RangeError);
    expect(() => planMusicSpanFrames([rows[0]!, { ...rows[1]!, sectionId: "other" }], "A", "B", 48000, 48000, fps)).toThrow(RangeError);
    expect(() => planMusicSpanFrames([rows[0]!, { ...rows[1]!, startFrame: 50 }], "A", "B", 48000, 48000, fps)).toThrow(RangeError);
  });

  it("rejects invalid clocks, sample counts and unsafe timeline bounds", () => {
    for (const bad of [0, -1, 1.5, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
      expect(() => planMusicSpanFrames(rows, "A", "B", bad, 48000, fps)).toThrow(RangeError);
    }
    expect(() => planMusicSpanFrames(rows, "A", "B", 48000, 0, fps)).toThrow(RangeError);
    expect(() => planMusicSpanFrames(rows, "A", "B", 48000, 48000, { numerator: 24, denominator: 0 })).toThrow(RangeError);
    expect(() => planMusicSpanFrames(
      [{ id: "A", startFrame: Number.MAX_SAFE_INTEGER, endFrame: Number.MAX_SAFE_INTEGER + 1 }],
      "A", "A", 48000, 48000, fps,
    )).toThrow(RangeError);
  });
});
