import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { compareSecondaryTimingV2, SecondaryTimingComparisonErrorV2 } from "../src/authoring-v2.js";
import { compileTimelineV2 } from "../src/compiler-core-v2.js";
import type {
  CompilerDependenciesV2, NarrationBlockV2, ScriptDocumentV2,
  TimelineManifestV2, VisualOnlyBlockV2,
} from "../src/generated/contracts-v2.js";

const repo = fileURLToPath(new URL("../../../", import.meta.url));
const fixture = (name: string): string => `${repo}tests/data/authoring_v2/${name}`;
const digest = (value: string): string => `sha256:${createHash("sha256").update(value, "utf8").digest("hex")}`;
const id = (n: number): string => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;

function dependencies(): CompilerDependenciesV2 {
  const value = JSON.parse(readFileSync(fixture("compiler-dependencies-v2.json"), "utf8")) as CompilerDependenciesV2;
  const map = value.narrationTimingMaps[0]!;
  map.textHash = digest("hello");
  map.tokenizationVersion = "script-document/v2-frozen-tokens";
  map.audio = {
    narrationAssetId: map.narrationAssetId, audioHash: map.audioHash, timingHash: map.timingHash,
    cacheAssetId: "a".repeat(64), locator: "Builds/narration/hello.wav",
    durationSamples: 192_000, sampleRate: 48_000, channels: 1,
  };
  value.document.textHash = map.textHash;
  const prepared = value.preparedMedia[0]!;
  prepared.mode = "derived_cfr";
  prepared.derivation = {
    method: "cfr_sample/v1", sourceHash: prepared.originalSource.contentHash,
    outputHash: prepared.verification.deliveredHash,
    toolHash: prepared.profile.toolHash, profileHash: prepared.profile.profileHash,
    commandHash: digest("synthetic preparation command"),
  };
  value.tracks.push(
    { id: "placeholder", kind: "video", index: 2, name: "Placeholder" },
    { id: "presenter", kind: "video", index: 3, name: "Presenter" },
    { id: "markers", kind: "video", index: 4, name: "Markers" },
  );
  value.roles.presenterTrackId = "presenter";
  value.roles.placeholderTrackId = "placeholder";
  value.roles.markerTrackId = "markers";
  return value;
}

function document(): ScriptDocumentV2 {
  const row: NarrationBlockV2 = {
    type: "narration", id: id(6), orderKey: "a0", text: "hello",
    tokens: [{ id: id(7), value: "hello", startOffset: 0, endOffset: 5 }],
    primaryVisualSequence: {
      id: id(9), version: 1,
      slots: [{
        id: id(16), kind: "content", relation: { kind: "base" },
        boundaryBefore: { kind: "row_start" },
        payload: {
          kind: "visual", payloadId: id(17), pictureKind: "clip",
          source: { kind: "media_reference", mediaReferenceId: id(8) },
          sourceUsage: { sourceInFrame: 0 }, audioPolicy: "mute", framingPolicy: "contain",
        },
        playoutPolicy: "match_structural_interval", version: 1,
      }],
    },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
  return {
    schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "Secondary timing synthetic",
    activeDraft: { blocks: [row], supportingItems: [] }, ideaOutline: [], extras: [], liveHeadSequence: 0,
    liveStateVector: "", liveContentHash: `sha256:${"a".repeat(64)}`,
  };
}

function compiled(doc: ScriptDocumentV2, deps: CompilerDependenciesV2): TimelineManifestV2 {
  const result = compileTimelineV2(doc, deps);
  expect(result.ok, JSON.stringify(result.ok ? result.report.diagnostics : result.diagnostics)).toBe(true);
  if (!result.ok) throw new Error(JSON.stringify(result.diagnostics));
  return result.manifest;
}

function root(): TimelineManifestV2 {
  return compiled(document(), dependencies());
}

function twoVisualOnlyRows(ms: number): { doc: ScriptDocumentV2; deps: CompilerDependenciesV2 } {
  const doc = document();
  const slate = (n: number, orderKey: string, durationOverrideMs: number): VisualOnlyBlockV2 => ({
    type: "visual_only", id: id(n), orderKey, version: 1,
    payload: { kind: "visual", payloadId: id(n + 1), pictureKind: "intentional_placeholder",
      source: { kind: "intentional_placeholder", text: "Synthetic slate" },
      audioPolicy: "mute", framingPolicy: "contain" },
    visualOnlyTiming: { kind: "visual_only", durationOverrideMs },
  });
  doc.activeDraft.blocks = [slate(30, "a0", ms), slate(32, "a1", 1000)];
  const deps = dependencies();
  deps.timeline.frameRate = { numerator: 24000, denominator: 1001 };
  deps.narrationTimingMaps = [];
  deps.occurrenceResolutions = [];
  deps.preparedMedia = [];
  deps.document.textHash = digest("");
  return { doc, deps };
}

function refusal(code: SecondaryTimingComparisonErrorV2["code"], before: TimelineManifestV2, after: TimelineManifestV2): void {
  expect(() => compareSecondaryTimingV2(before, after)).toThrow(SecondaryTimingComparisonErrorV2);
  try {
    compareSecondaryTimingV2(before, after);
    throw new Error("Expected refusal");
  } catch (error) {
    expect(error).toBeInstanceOf(SecondaryTimingComparisonErrorV2);
    expect((error as SecondaryTimingComparisonErrorV2).code).toBe(code);
  }
}

describe("#391 read-only exact secondary timing differences", () => {
  it("returns deterministic unchanged structural/event intervals without modifying signed inputs", () => {
    const before = root();
    const after = structuredClone(before);
    const frozen = JSON.stringify([before, after]);
    const result = compareSecondaryTimingV2(before, after);
    expect(result.disposition).toBe("proposed_not_applied");
    expect(result.boundaries).toHaveLength(1);
    expect(result.boundaries[0]).toMatchObject({
      blockId: id(6), ownerId: id(16), relation: "root", beforeFrame: 0, afterFrame: 0,
      deltaFrames: 0, durationDeltaFrames: 0,
    });
    expect(result.visualEvents.filter((item) => item.kind === "primary_visual")).toHaveLength(1);
    expect(result.visualEvents.every((item) => item.startDeltaFrames === 0 && item.endDeltaFrames === 0)).toBe(true);
    expect(compareSecondaryTimingV2(before, after)).toEqual(result);
    result.boundaries[0]!.beforeRange!.endFrame += 1;
    expect(JSON.stringify([before, after])).toBe(frozen);
  });

  it("compares two REAL compiler outputs: 24000/1001 fps, exact +2 frames and the adjacent visual row", () => {
    const a = twoVisualOnlyRows(1000);
    const b = twoVisualOnlyRows(1084);
    const beforeInputs = JSON.stringify([a.doc, a.deps, b.doc, b.deps]);
    const before = compiled(a.doc, a.deps);
    const after = compiled(b.doc, b.deps);
    const changes = compareSecondaryTimingV2(before, after);
    expect(changes.frameRate).toEqual({ numerator: 24000, denominator: 1001 });
    expect(changes.boundaries).toEqual([]);
    expect([...changes.visualEvents].sort((left, right) => left.ownerId.localeCompare(right.ownerId)).map((item) => ({ owner: item.ownerId, from: item.beforeRange, to: item.afterRange,
      start: item.startDeltaFrames, end: item.endDeltaFrames, duration: item.durationDeltaFrames }))).toEqual([
      { owner: id(31), from: { startFrame: 0, endFrame: 24 }, to: { startFrame: 0, endFrame: 26 }, start: 0, end: 2, duration: 2 },
      { owner: id(33), from: { startFrame: 24, endFrame: 48 }, to: { startFrame: 26, endFrame: 50 }, start: 2, end: 2, duration: 0 },
    ]);
    expect(JSON.stringify([a.doc, a.deps, b.doc, b.deps])).toBe(beforeInputs);
  });

  it("accepts mathematically identical rational rates, but never converts via floating milliseconds", () => {
    const before = root();
    before.timeline.frameRate = { numerator: 24000, denominator: 1001 };
    const after = structuredClone(before);
    after.timeline.frameRate = { numerator: 48000, denominator: 2002 };
    expect(compareSecondaryTimingV2(before, after).frameRate).toEqual({ numerator: 24000, denominator: 1001 });
    after.timeline.frameRate.denominator = 2001;
    refusal("RATE_MISMATCH", before, after);
    after.timeline.frameRate = { numerator: Number.MAX_SAFE_INTEGER + 1, denominator: 1 };
    refusal("RATE_MISMATCH", before, after);
  });

  it("refuses missing, duplicate and changed structural owners or sequence grammar", () => {
    const before = root();
    const after = structuredClone(before);
    after.visualSequenceResolutions.push(structuredClone(after.visualSequenceResolutions[0]!));
    refusal("DUPLICATE_OWNER", before, after);
    after.visualSequenceResolutions.pop();
    after.visualSequenceResolutions[0]!.slotId = null;
    refusal("STRUCTURE_CHANGED", before, after);
    after.visualSequenceResolutions[0]!.slotId = id(16);
    after.visualSequenceResolutions[0]!.sequenceVersion += 1;
    // A legitimate version bump is allowed when the immutable slot and boundary grammar stay the same.
    expect(compareSecondaryTimingV2(before, after).boundaries).toHaveLength(1);
    after.visualSequenceResolutions[0]!.sequenceId = id(300);
    refusal("STRUCTURE_CHANGED", before, after);
    after.visualSequenceResolutions = [];
    refusal("STRUCTURE_CHANGED", before, after);
  });

  it("preserves a continuous parent under a cutaway and treats a return as a boundary, never a fresh source event", () => {
    // Synthetic structural shape, NOT a signed build or proof of a native edit.
    // The separate 23.976 test above supplies the compiler-produced timing change.
    const before = root();
    const rootOwner = before.visualSequenceResolutions[0]!;
    const rootEvent = before.events.find((event) => event.provenance.slotId === rootOwner.slotId)!;
    const rootRange = rootOwner.rootRanges[0]!;
    const childRange = { startFrame: rootRange.startFrame + 24, endFrame: rootRange.startFrame + 48 };
    expect(rootRange.endFrame).toBeGreaterThan(childRange.endFrame);
    const childEvent = structuredClone(rootEvent);
    childEvent.eventId = id(50);
    childEvent.trackId = "video-child";
    childEvent.trackRole = "child";
    childEvent.recordRange = childRange;
    childEvent.provenance.slotId = id(18);
    childEvent.provenance.payloadId = id(19);
    before.events.push(childEvent);
    before.tracks.push({ id: "video-child", kind: "video", name: "Child", index: 5 });
    before.roles.childTrackIds.push("video-child");
    before.composition.childTrackIds.push("video-child");
    const childOwner = structuredClone(rootOwner);
    Object.assign(childOwner, {
      relation: "child", slotId: id(18), payloadId: id(19), structuralSlotIndex: 1,
      resolvedRecordFrame: childRange.startFrame, rootRanges: [], childRanges: [childRange],
      eventIds: [childEvent.eventId], topmostAppearances: [{ eventId: childEvent.eventId, recordRange: childRange }],
    });
    const returnOwner = structuredClone(rootOwner);
    Object.assign(returnOwner, {
      relation: "return", slotId: null, payloadId: null, returnSlotId: id(20), structuralSlotIndex: 2,
      resolvedRecordFrame: childRange.endFrame, rootRanges: [], childRanges: [], eventIds: [],
      topmostAppearances: [], sourceRange: null, sourceTimeMapping: null,
      preparationRequirementKey: null, presenterChoice: "not_applicable",
    });
    before.visualSequenceResolutions.push(childOwner, returnOwner);
    before.composition.returns.push({ returnSlotId: id(20), rootEventId: rootEvent.eventId,
      recordFrame: childRange.endFrame, emitsNewSourceEvent: false });
    const after = structuredClone(before);
    after.visualSequenceResolutions[2]!.resolvedRecordFrame -= 2;
    after.composition.returns[0]!.recordFrame -= 2;
    const diff = compareSecondaryTimingV2(before, after);
    expect(diff.boundaries.find((item) => item.relation === "root")?.durationDeltaFrames).toBe(0);
    expect(diff.boundaries.find((item) => item.relation === "child")?.durationDeltaFrames).toBe(0);
    expect(diff.boundaries.find((item) => item.relation === "return")).toMatchObject({
      deltaFrames: -2, beforeRange: null, afterRange: null, durationDeltaFrames: null,
    });
    expect(diff.visualEvents.every((item) => item.durationDeltaFrames === 0)).toBe(true);
    after.composition.returns[0]!.recordFrame += 1;
    refusal("INCONSISTENT_RANGE", before, after);
    after.composition.returns[0]!.recordFrame -= 1;
    after.visualSequenceResolutions[2]!.sourceRange = { startFrame: 0, endFrame: 1 };
    refusal("INCONSISTENT_RANGE", before, after);
  });

  it("rejects shifted source/timing identity even when owner names and record frames match", () => {
    const before = root();
    const after = structuredClone(before);
    after.document.textHash = digest("different words");
    refusal("DOCUMENT_MISMATCH", before, after);
    after.document = structuredClone(before.document);
    after.sources[0] = { ...after.sources[0]!, id: id(400) };
    refusal("EVIDENCE_MISMATCH", before, after);
    after.sources = structuredClone(before.sources);
    after.durationBasis.narrationTimingMapHash = digest("different timing");
    refusal("EVIDENCE_MISMATCH", before, after);
    after.durationBasis = structuredClone(before.durationBasis);
    after.events[0]!.provenance.timingMapHash = digest("different audio");
    refusal("EVIDENCE_MISMATCH", before, after);
    after.events = structuredClone(before.events);
    after.visualSequenceResolutions[0]!.boundaryEvidenceHash = digest("unrelated measured source");
    refusal("STRUCTURE_CHANGED", before, after);
    after.visualSequenceResolutions = structuredClone(before.visualSequenceResolutions);
    after.visualSequenceResolutions[0]!.sourceRange!.startFrame += 1;
    refusal("EVIDENCE_MISMATCH", before, after);
    after.visualSequenceResolutions = structuredClone(before.visualSequenceResolutions);
    const visual = after.events.find((item) => item.kind === "primary_visual")!;
    visual.sourceRange!.startFrame += 1;
    refusal("EVIDENCE_MISMATCH", before, after);
    after.events = structuredClone(before.events);
    after.boundaryEvidence[0]!.resolvedRecordFrame += 1;
    refusal("EVIDENCE_MISMATCH", before, after);
  });

  it("refuses unsupported reordered/forged intervals, duplicate events, non-visual drift and unsafe integers", () => {
    const before = root();
    const after = structuredClone(before);
    after.events.push(structuredClone(after.events[0]!));
    refusal("DUPLICATE_OWNER", before, after);
    after.events.pop();
    after.visualSequenceResolutions[0]!.rootRanges[0]!.startFrame = 1;
    refusal("INCONSISTENT_RANGE", before, after);
    after.visualSequenceResolutions[0]!.rootRanges[0]!.startFrame = 0;
    after.visualSequenceResolutions[0]!.rootRanges[0]!.endFrame = 0;
    refusal("INCONSISTENT_RANGE", before, after);
    after.visualSequenceResolutions = structuredClone(before.visualSequenceResolutions);
    after.events[0]!.recordRange.endFrame = Number.MAX_SAFE_INTEGER + 1;
    refusal("UNSAFE_FRAME", before, after);
    after.events = structuredClone(before.events);
    const narration = after.events.find((item) => item.kind === "narration")!;
    narration.recordRange.startFrame += 1;
    refusal("EVIDENCE_MISMATCH", before, after);
  });

  it("keeps frozen fixture files and baseline goldens byte-unchanged", () => {
    const paths = [fixture("timeline-manifest-v2.json"), fixture("compiler-dependencies-v2.json")];
    const original = paths.map((path) => digest(readFileSync(path, "utf8")));
    expect(root()).toMatchObject({ schemaVersion: "timeline-manifest/v2" });
    expect(paths.map((path) => digest(readFileSync(path, "utf8")))).toEqual(original);
  });
});
