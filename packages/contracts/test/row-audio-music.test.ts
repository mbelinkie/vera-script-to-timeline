import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { compileTimelineV2 } from "../src/compiler-core-v2.js";
import type { CompilerDependenciesV2, ScriptDocumentV2, VisualOnlyBlockV2 } from "../src/generated/contracts-v2.js";
import { planMusicSpanFrames, resolveMusicFadeOutFrames, type MusicRowBounds } from "../src/row-audio-music.js";

const rows: MusicRowBounds[] = [
  { id: "A", startFrame: 0, endFrame: 48, sectionId: "first", active: true },
  { id: "B", startFrame: 48, endFrame: 96, sectionId: "first", active: true },
  { id: "C", startFrame: 96, endFrame: 144, sectionId: "first", active: true },
];
const fps = { numerator: 24, denominator: 1 };

describe("explicit music fade-out", () => {
  it("converts physical durations and accepts the exact cue length and zero", () => {
    expect(resolveMusicFadeOutFrames(500, 96, fps)).toBe(12);
    expect(resolveMusicFadeOutFrames(3000, 72, fps)).toBe(72);
    expect(resolveMusicFadeOutFrames(0, 1, fps)).toBe(0);
    expect(resolveMusicFadeOutFrames(1, 1, fps)).toBe(1);
    const ntsc = { numerator: 24000, denominator: 1001 };
    expect(resolveMusicFadeOutFrames(1001, 24, ntsc)).toBe(24);
    expect(() => resolveMusicFadeOutFrames(1002, 24, ntsc)).toThrow(/longer than the cue/);
  });

  it("checks physical bounds exactly even with large integer products", () => {
    const max = Number.MAX_SAFE_INTEGER;
    expect(resolveMusicFadeOutFrames(max, max, { numerator: max, denominator: max })).toBe(9_007_199_254_741);
    expect(() => resolveMusicFadeOutFrames(max, 1, fps)).toThrow(/longer than the cue/);
    for (const invalid of [-1, 0.5, max + 1]) {
      expect(() => resolveMusicFadeOutFrames(invalid, 96, fps)).toThrow(/whole number/);
    }
  });
});

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

describe("#730 ordinary music bed overlap at compile time", () => {
  const id = (n: number): string => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
  const digest = (value: string): string => `sha256:${createHash("sha256").update(value).digest("hex")}`;
  function fixture() {
    const blocks: VisualOnlyBlockV2[] = [30, 32, 34].map((n, i) => ({
      type: "visual_only", id: id(n), orderKey: `a${i}`, version: 1,
      payload: { kind: "visual", payloadId: id(n + 1), pictureKind: "intentional_placeholder",
        source: { kind: "intentional_placeholder", text: "Synthetic slate" }, audioPolicy: "mute", framingPolicy: "contain" },
      visualOnlyTiming: { kind: "visual_only", durationOverrideMs: 4000 },
    }));
    const doc: ScriptDocumentV2 = {
      schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "Ordinary music beds",
      activeDraft: { blocks, supportingItems: [] }, ideaOutline: [], extras: [], liveHeadSequence: 0,
      liveStateVector: "", liveContentHash: `sha256:${"a".repeat(64)}`,
      rowAudioSpans: [0, 1].map((i) => ({ id: id(40 + i), startRowId: blocks[i]!.id, endRowId: blocks[i + 1]!.id,
        source: { mediaReferenceId: id(50 + i), artifactId: id(60 + i), artifactVersion: 1, contentHash: digest(`music ${i}`) },
        settings: { gainDb: -12 } })),
    };
    const deps = JSON.parse(readFileSync(new URL("../../../tests/data/authoring_v2/compiler-dependencies-v2.json", import.meta.url), "utf8")) as CompilerDependenciesV2;
    deps.narrationTimingMaps = [];
    deps.occurrenceResolutions = [];
    deps.preparedMedia = [];
    deps.document.textHash = digest("");
    deps.timeline.frameRate = fps;
    deps.tracks.push({ id: "placeholder", kind: "video", index: 2, name: "Placeholder" },
      { id: "presenter", kind: "video", index: 3, name: "Presenter" },
      { id: "markers", kind: "video", index: 4, name: "Markers" },
      { id: "music-a5", kind: "audio", index: 5, name: "A5 Music" });
    deps.roles.musicTrackId = "music-a5";
    deps.musicBindings = doc.rowAudioSpans!.map((span, i) => ({ spanId: span.id, source: structuredClone(span.source),
      displayFilename: `bed-${i}.wav`, status: "ready", sampleRate: 48000, channels: 1, durationSamples: 48000 * 16 }));
    return { doc, deps };
  }
  function compile(doc: ScriptDocumentV2, deps: CompilerDependenciesV2) {
    const result = compileTimelineV2(doc, deps);
    if (!result.ok) throw new Error(JSON.stringify(result.diagnostics));
    return result;
  }

  it("blocks overlapping A–B and B–C beds with a deterministic cue-specific diagnostic", () => {
    const { doc, deps } = fixture();
    const result = compile(doc, deps);
    expect(result.manifest.events.filter((event) => event.kind === "music").map((event) => event.recordRange))
      .toEqual([{ startFrame: 0, endFrame: 192 }, { startFrame: 96, endFrame: 288 }]);
    expect(result.report.status).toBe("blocked");
    const collisions = result.report.diagnostics.filter((item) => item.code === "MUSIC_SPAN_INVALID");
    expect(collisions).toHaveLength(1);
    expect(collisions[0]).toMatchObject({ severity: "blocking", entity: { id: id(41), path: `rowAudioSpans/${id(41)}` } });
    expect(collisions[0]!.message).toContain(id(40));
    expect(collisions[0]!.message).toContain(id(41));
    doc.rowAudioSpans!.reverse();
    deps.musicBindings!.reverse();
    expect(compile(doc, deps).report.diagnostics).toEqual(result.report.diagnostics);
  });

  it("keeps touching A and B–C beds ready", () => {
    const { doc, deps } = fixture();
    doc.rowAudioSpans![0]!.endRowId = doc.activeDraft.blocks[0]!.id;
    const result = compile(doc, deps);
    expect(result.report.status).toBe("ready");
    expect(result.manifest.events.filter((event) => event.kind === "music").map((event) => event.recordRange))
      .toEqual([{ startFrame: 0, endFrame: 96 }, { startFrame: 96, endFrame: 288 }]);
    expect(result.report.diagnostics).toEqual([]);
  });

  it("uses actual emitted intervals when a short source ends before the next bed", () => {
    const { doc, deps } = fixture();
    const binding = deps.musicBindings![0]!;
    if (binding.status !== "ready") throw new Error("Fixture requires a ready binding");
    binding.durationSamples = 48000 * 3;
    const result = compile(doc, deps);
    expect(result.report.status).toBe("ready");
    expect(result.manifest.events.filter((event) => event.kind === "music").map((event) => event.recordRange))
      .toEqual([{ startFrame: 0, endFrame: 72 }, { startFrame: 96, endFrame: 288 }]);
    expect(result.report.diagnostics.map((item) => item.code)).toEqual(["MUSIC_SOURCE_SHORTER"]);
  });
});
