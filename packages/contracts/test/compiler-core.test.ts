import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  canonicalJson,
  compileTimeline,
  frameAtMilliseconds,
  frameDurationForSamples,
  sha256CanonicalJson,
} from "../src/compiler-core.js";
import type {
  CompilerDependenciesV1,
  NarrationBlock,
  ScriptDocumentV1,
  VisualBlock,
} from "../src/generated/contracts.js";

const dataPath = (name: string): string =>
  fileURLToPath(new URL(`../../../tests/data/${name}`, import.meta.url));

function readJson<T = unknown>(name: string): T {
  return JSON.parse(readFileSync(dataPath(name), "utf8")) as T;
}

function clone<T>(value: T): T {
  return structuredClone(value);
}

function documentFixture(name: "minimal" | "torture"): ScriptDocumentV1 {
  return readJson(`slice_1_1/${name}.script-document.json`);
}

function dependenciesFixture(name: "minimal" | "torture"): CompilerDependenciesV1 {
  return readJson(`slice_1_3/${name}.compiler-dependencies.json`);
}

function narrationAt(document: ScriptDocumentV1, index: number): NarrationBlock {
  const block = document.activeDraft.blocks[index];
  if (block?.type !== "narration") throw new Error(`Expected narration at index ${index}.`);
  return block;
}

function visualAt(document: ScriptDocumentV1, index: number): VisualBlock {
  const block = document.activeDraft.blocks[index];
  if (block?.type !== "visual") throw new Error(`Expected visual at index ${index}.`);
  return block;
}

function compileFixture(name: "minimal" | "torture") {
  return compileTimeline(
    documentFixture(name),
    dependenciesFixture(name),
  );
}

function expectGolden(name: "minimal" | "torture"): void {
  const result = compileFixture(name);
  expect(result.ok).toBe(true);
  if (!result.ok) return;
  for (const [suffix, actual] of [
    ["manifest", result.manifestJson],
    ["report", result.reportJson],
  ] as const) {
    const path = dataPath(`slice_1_3/${name}.${suffix}.golden.json`);
    if (process.env.UPDATE_GOLDENS === "1") writeFileSync(path, actual, "utf8");
    expect(actual).toBe(readFileSync(path, "utf8"));
  }
}

describe("Slice 1.3 deterministic compiler primitives", () => {
  it("uses exact ceiling boundaries at rational frame rates", () => {
    expect(frameAtMilliseconds(0, { numerator: 24000, denominator: 1001 })).toBe(0);
    expect(frameAtMilliseconds(1, { numerator: 24000, denominator: 1001 })).toBe(1);
    expect(frameAtMilliseconds(500, { numerator: 24000, denominator: 1001 })).toBe(12);
    expect(frameAtMilliseconds(1001, { numerator: 24000, denominator: 1001 })).toBe(24);
    expect(frameAtMilliseconds(1000, { numerator: 30, denominator: 1 })).toBe(30);
  });

  it("uses exact samples rather than rounded milliseconds for duration", () => {
    expect(frameDurationForSamples(48_001, 48_000, { numerator: 24_000, denominator: 1_001 })).toBe(24);
  });

  it("canonicalizes keys recursively without reordering arrays", () => {
    const value = { z: [{ b: 2, a: 1 }], a: { y: true, x: false } };
    expect(canonicalJson(value)).toBe('{\n  "a": {\n    "x": false,\n    "y": true\n  },\n  "z": [\n    {\n      "a": 1,\n      "b": 2\n    }\n  ]\n}\n');
    expect(sha256CanonicalJson(value)).toMatch(/^sha256:[a-f0-9]{64}$/);
  });
});

describe("Slice 1.3 compiler", () => {
  it("matches the minimal golden bytes", () => expectGolden("minimal"));
  it("matches the torture golden bytes", () => expectGolden("torture"));

  it("is byte-identical across runs and does not mutate either input", () => {
    const document = documentFixture("torture");
    const dependencies = dependenciesFixture("torture");
    const beforeDocument = canonicalJson(document);
    const beforeDependencies = canonicalJson(dependencies);
    const first = compileTimeline(document, dependencies);
    const second = compileTimeline(document, dependencies);
    expect(first.ok && second.ok).toBe(true);
    if (first.ok && second.ok) {
      expect(first.manifestJson).toBe(second.manifestJson);
      expect(first.reportJson).toBe(second.reportJson);
    }
    expect(canonicalJson(document)).toBe(beforeDocument);
    expect(canonicalJson(dependencies)).toBe(beforeDependencies);
  });

  it("compiles exact markers, adjustable tracks, source audio, and presenter placeholders", () => {
    const result = compileFixture("torture");
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.manifest.markers.map((marker) => [marker.name, marker.note, marker.color])).toEqual([
      ["Mid-sentence coverage", "Section: Mid-sentence coverage", "Blue"],
      ["Direction", "Keep the paragraph intact through every visual cut.", "Yellow"],
    ]);
    expect(result.manifest.events.some((event) => event.kind === "audio" && event.trackId === "audio-3")).toBe(true);
    expect(result.manifest.events.filter((event) => event.kind === "placeholder" && event.trackId === "video-1")).toHaveLength(2);
    expect(result.manifest.sources.every((source) => source.id[14] === "5")).toBe(true);
    expect(result.report.manifest.contentHash).toBe(sha256CanonicalJson(result.manifest));
  });

  it("honors half-open affinities with shared compiled boundaries", () => {
    const document = documentFixture("minimal");
    const second = narrationAt(document, 1).visualEvents[0]!;
    second.range.startAffinity = "after";
    second.range.quotedText = "world";
    const first = clone(second);
    first.id = "11000000-0000-4000-8000-000000000009";
    first.range.startAffinity = "before";
    first.range.endAffinity = "before";
    first.range.quotedText = "Hello";
    narrationAt(document, 1).visualEvents.unshift(first);
    const result = compileTimeline(document, dependenciesFixture("minimal"));
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const visual = result.manifest.events.find((event) => event.id === "11000000-0000-4000-8000-000000000008");
    expect(visual?.recordRange).toEqual({ startFrame: 12, durationFrames: 36 });
    expect(result.manifest.transitions).toEqual([
      expect.objectContaining({
        kind: "hard_cut",
        fromEventId: "11000000-0000-4000-8000-000000000009",
        toEventId: "11000000-0000-4000-8000-000000000008",
        atFrame: 12,
        durationFrames: 0,
      }),
    ]);
  });

  it("uses the exact sample-derived block end for a final derived word end", () => {
    const dependencies = dependenciesFixture("minimal");
    dependencies.narration[0]!.audio.durationSamples = 40_040;
    const result = compileTimeline(documentFixture("minimal"), dependencies);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.manifest.timeline.durationFrames).toBe(20);
    expect(
      result.manifest.events.find(
        (event) => event.id === "11000000-0000-4000-8000-000000000008",
      )?.recordRange,
    ).toEqual({ startFrame: 0, durationFrames: 20 });
  });

  it("compiles an alternate NTSC rational rate without floating-point drift", () => {
    const dependencies = dependenciesFixture("minimal");
    dependencies.build.timeline.frameRate = {
      numerator: 30_000,
      denominator: 1_001,
    };
    const result = compileTimeline(documentFixture("minimal"), dependencies);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.manifest.timeline.durationFrames).toBe(60);
  });

  it("does not compare provider mark values to authored token text", () => {
    const dependencies = dependenciesFixture("minimal");
    dependencies.narration[0]!.timing.marks[0]!.value = "pronunciation-alias";
    const result = compileTimeline(documentFixture("minimal"), dependencies);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.report.status).toBe("ready_with_warnings");
  });

  it("accepts sentence timing only for complete sentence coverage", () => {
    const dependencies = dependenciesFixture("minimal");
    dependencies.narration[0]!.timing.precision = "sentence_start";
    dependencies.narration[0]!.timing.marks = [{ kind: "sentence", timeMs: 0, startUtf16: 0, endUtf16: 12, value: "Hello world." }];
    const result = compileTimeline(documentFixture("minimal"), dependencies);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.manifest.events.find((event) => event.kind === "placeholder")?.timingPrecision).toBe("sentence_start_with_derived_end");
  });

  it("rejects sentence marks that cut through an accepted token", () => {
    const dependencies = dependenciesFixture("minimal");
    dependencies.narration[0]!.timing.precision = "sentence_start";
    dependencies.narration[0]!.timing.marks = [
      {
        kind: "sentence",
        timeMs: 0,
        startUtf16: 1,
        endUtf16: 12,
        value: "ello world.",
      },
    ];
    const result = compileTimeline(documentFixture("minimal"), dependencies);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.report.status).toBe("blocked");
    expect(result.report.issues).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ code: "NARRATION_TIMING_UNAVAILABLE" }),
      ]),
    );
  });

  it("does not invent a transition for an abutting cross-track switch", () => {
    const result = compileFixture("torture");
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(
      result.manifest.transitions.some(
        (transition) =>
          transition.fromEventId === "12000000-0000-4000-8000-000000000018" &&
          transition.toEventId === "12000000-0000-4000-8000-000000000020",
      ),
    ).toBe(false);
    const issue = result.report.issues.find(
      (candidate) =>
        candidate.code === "CROSS_TRACK_CUT_IMPLIED" &&
        candidate.message.includes(
          "event 12000000-0000-4000-8000-000000000018 to track video-5 event 12000000-0000-4000-8000-000000000020 at frame 24",
        ),
    );
    expect(issue?.severity).toBe("info");
  });

  it("rejects source-audio policy on a still instead of silently dropping it", () => {
    const document = documentFixture("torture");
    narrationAt(document, 2).visualEvents[0]!.audioPolicy = "use_source";
    const result = compileTimeline(document, dependenciesFixture("torture"));
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.diagnostics).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ code: "VISUAL_SOURCE_AUDIO_UNAVAILABLE" }),
        ]),
      );
    }
  });

  it.each([
    ["timeline start", (dependencies: CompilerDependenciesV1) => {
      dependencies.build.timeline.startFrame = Number.MAX_SAFE_INTEGER + 1;
    }],
    ["visual source start", (dependencies: CompilerDependenciesV1) => {
      dependencies.resolvedVisuals[1]!.sourceStartFrame =
        Number.MAX_SAFE_INTEGER + 1;
    }],
  ])("rejects an unsafe integer in %s before identity-bearing arithmetic", (_name, mutate) => {
    const dependencies = dependenciesFixture("torture");
    mutate(dependencies);
    const result = compileTimeline(documentFixture("torture"), dependencies);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.diagnostics).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ code: "INTEGER_UNSAFE" }),
        ]),
      );
    }
  });

  it("rejects cumulative frame overflow from individually safe integers", () => {
    const dependencies = dependenciesFixture("minimal");
    dependencies.build.timeline.startFrame = Number.MAX_SAFE_INTEGER - 1;
    const result = compileTimeline(documentFixture("minimal"), dependencies);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.diagnostics).toEqual([
        expect.objectContaining({
          code: "COMPILATION_PRECONDITION_FAILED",
          message: "narration block end frame exceeds JavaScript's safe integer range",
        }),
      ]);
    }
  });

  it("preserves duration and emits a blocking slate for failed narration", () => {
    const dependencies = dependenciesFixture("torture");
    dependencies.narration[0]!.status = "failed";
    dependencies.narration[0]!.failureReason = "provider: unavailable";
    dependencies.narration[0]!.timing.precision = "none";
    dependencies.narration[0]!.timing.marks = [];
    const result = compileTimeline(documentFixture("torture"), dependencies);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.report.status).toBe("blocked");
    expect(result.manifest.timeline.durationFrames).toBe(48);
    expect(result.manifest.events).toHaveLength(2);
    expect(result.manifest.events.map((event) => event.timingPrecision)).toEqual(["unavailable", "unavailable"]);
    expect(result.report.manualCompletionItems).toHaveLength(1);
  });

  it("uses the blocked-output path for malformed ready timing", () => {
    const dependencies = dependenciesFixture("minimal");
    dependencies.narration[0]!.timing.marks[1]!.startUtf16 = 5;
    const result = compileTimeline(documentFixture("minimal"), dependencies);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.report.status).toBe("blocked");
    expect(result.manifest.events.some((event) => event.timingPrecision === "unavailable")).toBe(true);
  });

  it.each([
    ["duplicate order keys", (document: ScriptDocumentV1) => { document.activeDraft.blocks[1]!.orderKey = document.activeDraft.blocks[0]!.orderKey; }, "ORDER_KEY_DUPLICATE"],
    ["missing narration dependency", (_document: ScriptDocumentV1, dependencies: CompilerDependenciesV1) => { dependencies.narration = []; }, "NARRATION_DEPENDENCY_MISSING"],
    ["wrong narration revision", (_document: ScriptDocumentV1, dependencies: CompilerDependenciesV1) => { dependencies.narration[0]!.blockRevision = 2; }, "NARRATION_REVISION_MISMATCH"],
    ["wrong narration text hash", (_document: ScriptDocumentV1, dependencies: CompilerDependenciesV1) => { dependencies.narration[0]!.textHash = `sha256:${"0".repeat(64)}`; }, "NARRATION_TEXT_HASH_MISMATCH"],
    ["duplicate track index", (_document: ScriptDocumentV1, dependencies: CompilerDependenciesV1) => { dependencies.tracks[1]!.index = 1; }, "TRACK_INDEX_DUPLICATE"],
  ])("rejects %s without outputs", (_name, mutate, code) => {
    const document = documentFixture("minimal");
    const dependencies = dependenciesFixture("minimal");
    mutate(document, dependencies);
    const result = compileTimeline(document, dependencies);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.diagnostics.some((item) => item.code === code)).toBe(true);
  });

  it("rejects a visual anchored to excluded narration", () => {
    const document = clone(documentFixture("torture"));
    const excludedVisual = clone(visualAt(document, 4));
    excludedVisual.id = "12000000-0000-4000-8000-000000000028";
    excludedVisual.orderKey = "a4b";
    excludedVisual.event.id = "12000000-0000-4000-8000-000000000029";
    excludedVisual.event.status = "unresolved";
    excludedVisual.event.source = { kind: "placeholder", description: "Excluded target", unresolvedVisual: true };
    const range = excludedVisual.event.range;
    range.blockId = "12000000-0000-4000-8000-000000000021";
    range.startTokenId = "12000000-0000-4000-8000-000000000022";
    range.endTokenId = "12000000-0000-4000-8000-000000000023";
    range.quotedText = "Unused alternative";
    document.activeDraft.blocks.push(excludedVisual);
    const result = compileTimeline(document, readJson("slice_1_3/torture.compiler-dependencies.json"));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.diagnostics.some((item) => item.code === "ANCHOR_TARGET_EXCLUDED")).toBe(true);
  });
});
