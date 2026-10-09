import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { compileTimelineV2, resolveMediaRequirementsV2 } from "../src/compiler-core-v2.js";
import type { CompilerDependenciesV2, NarrationBlockV2, ScriptDocumentV2, VisualOnlyBlockV2 } from "../src/generated/contracts-v2.js";

const repo = fileURLToPath(new URL("../../../", import.meta.url));
const fixture = (name: string): string => `${repo}tests/data/authoring_v2/${name}`;
const digest = (value: string): string => `sha256:${createHash("sha256").update(value, "utf8").digest("hex")}`;
const id = (n: number): string => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;

function dependencies(): CompilerDependenciesV2 {
  const value = JSON.parse(readFileSync(fixture("compiler-dependencies-v2.json"), "utf8")) as CompilerDependenciesV2;
  const map = value.narrationTimingMaps[0]!;
  map.textHash = digest("hello");
  map.tokenizationVersion = "script-document/v2-frozen-tokens";
  map.audio = { narrationAssetId: map.narrationAssetId, audioHash: map.audioHash, timingHash: map.timingHash, cacheAssetId: "a".repeat(64), locator: "Builds/narration/hello.wav", durationSamples: 192_000, sampleRate: 48_000, channels: 1 };
  value.document.textHash = map.textHash;
  const prepared = value.preparedMedia[0]!;
  prepared.mode = "derived_cfr";
  prepared.derivation = {
    method: "cfr_sample/v1",
    sourceHash: prepared.originalSource.contentHash,
    outputHash: prepared.verification.deliveredHash,
    toolHash: prepared.profile.toolHash,
    profileHash: prepared.profile.profileHash,
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
      slots: [{ id: id(16), kind: "content", relation: { kind: "base" }, boundaryBefore: { kind: "row_start" }, payload: {
        kind: "visual", payloadId: id(17), pictureKind: "clip", source: { kind: "media_reference", mediaReferenceId: id(8) },
        sourceUsage: { sourceInFrame: 0 }, audioPolicy: "mute", framingPolicy: "contain",
      }, playoutPolicy: "match_structural_interval", version: 1 }],
    },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1,
  };
  return {
    schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "Compiler v2 synthetic",
    activeDraft: { blocks: [row], supportingItems: [] }, ideaOutline: [], extras: [], liveHeadSequence: 0,
    liveStateVector: "", liveContentHash: `sha256:${"a".repeat(64)}`,
  };
}

function visualOnlyDocument(block: VisualOnlyBlockV2): ScriptDocumentV2 {
  const value = document();
  value.activeDraft.blocks = [block];
  return value;
}

function visualOnlyDependencies(): CompilerDependenciesV2 {
  const value = dependencies();
  value.narrationTimingMaps = [];
  value.occurrenceResolutions = [];
  value.preparedMedia = [];
  value.document.textHash = digest("");
  return value;
}

function intentionalSlateBlock(durationOverrideMs?: number): VisualOnlyBlockV2 {
  return {
    type: "visual_only", id: id(30), orderKey: "a0", version: 1,
    payload: { kind: "visual", payloadId: id(31), pictureKind: "intentional_placeholder", source: { kind: "intentional_placeholder", text: "Intentional slate" }, audioPolicy: "mute", framingPolicy: "contain" },
    visualOnlyTiming: { kind: "visual_only", ...(durationOverrideMs === undefined ? {} : { durationOverrideMs }) },
  };
}

function completeClipBoundaryFixture(words: readonly { value: string; start: { numerator: number; denominator: number }; audibleEnd?: { numerator: number; denominator: number } }[], audioDurationSamples = 576000): { doc: ScriptDocumentV2; deps: CompilerDependenciesV2; tokenIds: string[] } {
  const doc = document();
  const row = doc.activeDraft.blocks[0] as NarrationBlockV2;
  const root = row.primaryVisualSequence!.slots[0]!;
  if (root.kind !== "content" || root.payload.kind !== "visual") throw new Error("fixture must have a visual root");
  root.playoutPolicy = "complete_logged_clip";
  root.payload.sourceUsage = { sourceInFrame: 0 };
  const placeholderId = id(19);
  row.primaryVisualSequence!.slots.push({
    id: placeholderId, kind: "content", relation: { kind: "sequential" },
    boundaryBefore: { kind: "previous_media_end", controllingSlotId: root.id },
    payload: { kind: "visual", payloadId: id(18), pictureKind: "clip", source: { kind: "media_reference", mediaReferenceId: id(8) }, sourceUsage: { sourceInFrame: 0 }, audioPolicy: "mute", framingPolicy: "contain" },
    playoutPolicy: "match_structural_interval", version: 1,
  });
  const text = words.map((word) => word.value).join(" ");
  let offset = 0;
  const rowTokens = words.map((word, index) => {
    const startOffset = offset;
    const endOffset = startOffset + word.value.length;
    offset = endOffset + 1;
    return { id: id(40 + index), value: word.value, startOffset, endOffset };
  });
  const [first, ...rest] = rowTokens;
  row.text = text;
  row.tokens = [first!, ...rest];
  const deps = dependencies();
  const map = deps.narrationTimingMaps[0]!;
  map.textHash = digest(text);
  map.precision = "audible_word_marks";
  map.timingHash = digest("complete clip boundary timing");
  map.audio!.timingHash = map.timingHash;
  map.audio!.durationSamples = audioDurationSamples;
  const tokenTimingRows = words.map((word, index) => ({
    tokenId: id(40 + index), startOffset: rowTokens[index]!.startOffset, endOffset: rowTokens[index]!.endOffset,
    quotedText: word.value, startTime: word.start,
    ...(word.audibleEnd ? { audibleEnd: word.audibleEnd } : {}),
    endBasis: word.audibleEnd ? "evidenced_audible_end" as const : index + 1 < words.length ? "next_word_derived" as const : "unknown" as const,
  }));
  const [firstTiming, ...remainingTimings] = tokenTimingRows;
  map.tokens = [firstTiming!, ...remainingTimings];
  deps.document.textHash = digest(text);
  deps.timeline.frameRate = { numerator: 24000, denominator: 1001 };
  const descriptor = deps.occurrenceResolutions[0]!;
  descriptor.occurrenceSourceInFrame = 0;
  descriptor.selectedSourceRange = null;
  descriptor.logicalSourceBounds = { startFrame: 0, endFrame: 250, frameRate: { numerator: 25, denominator: 1 } };
  descriptor.sourceFrameMap.packageFrameZeroLogicalFrame = 0;
  descriptor.sourceFrameMap.decodedPackageFrameRate = { numerator: 25, denominator: 1 };
  descriptor.sourceFrameMap.decodedPackageFrameCount = 250;
  const binding = deps.preparedMedia[0]!;
  binding.requestedRange = { sourceInFrame: 0, duration: { numerator: 10, denominator: 1 }, preHandle: { numerator: 0, denominator: 1 }, postHandle: { numerator: 0, denominator: 1 } };
  binding.targetRate = { numerator: 24000, denominator: 1001 };
  binding.timeMapping.sourceOrigin = { numerator: 0, denominator: 1 };
  binding.timeMapping.sourceRate = { numerator: 25, denominator: 1 };
  binding.timeMapping.deliveredRate = { numerator: 24000, denominator: 1001 };
  binding.timeMapping.sourceFrameMap = structuredClone(descriptor.sourceFrameMap);
  binding.verification.decodedFrameCount = 240;
  binding.verification.decodedFrameRate = { numerator: 24000, denominator: 1001 };
  binding.verification.videoTimeBase = { numerator: 1001, denominator: 24000 };
  binding.derivation = { ...binding.derivation!, commandHash: digest("complete clip boundary preparation"), outputHash: binding.verification.deliveredHash };
  const secondDescriptor = structuredClone(descriptor);
  secondDescriptor.owner = { kind: "primary_slot", sequenceId: row.primaryVisualSequence!.id, slotId: placeholderId };
  secondDescriptor.payloadId = id(18);
  secondDescriptor.preparedMediaRequirementKey = "prep:after-complete";
  const secondBinding = structuredClone(binding);
  secondBinding.requirementKey = "prep:after-complete";
  secondBinding.requestedRange.duration = { numerator: 1001, denominator: 500 };
  secondBinding.verification.decodedFrameCount = 48;
  secondBinding.derivation = { ...secondBinding.derivation!, commandHash: digest("following root preparation") };
  secondBinding.artifactLocator = "prepared/after-complete.mov";
  deps.occurrenceResolutions.push(secondDescriptor);
  deps.preparedMedia.push(secondBinding);
  return { doc, deps, tokenIds: rowTokens.map((item) => item.id) };
}

function presenterDocument(): ScriptDocumentV2 {
  const value = document();
  const row = value.activeDraft.blocks[0] as NarrationBlockV2;
  const root = row.primaryVisualSequence!.slots[0]!;
  if (root.kind !== "content") throw new Error("fixture must have a root slot");
  root.payload = { kind: "on_camera", presenterChoiceId: null };
  return value;
}

function stillReference(mediaReferenceId: string, artifactId: string, filename: string, locator: string) {
  return {
    mediaReferenceId, artifactId, artifactVersion: 1, contentHash: digest(filename), projectRelativeLocator: locator,
    width: 1920, height: 1080, provenance: { origin: "local_import" as const, originalFilename: filename },
  };
}

function readGolden(name: string, actual: string): void {
  const path = fixture(`issue_173/compiler/${name}.golden.json`);
  if (process.env.UPDATE_COMPILER_V2_GOLDENS === "1") {
    mkdirSync(fixture("issue_173/compiler"), { recursive: true });
    writeFileSync(path, actual, "utf8");
  }
  expect(actual).toBe(readFileSync(path, "utf8"));
}

function readFrozenInput(name: string, doc: ScriptDocumentV2, deps: CompilerDependenciesV2): void {
  const path = fixture(`issue_173/compiler/${name}.input.golden.json`);
  const actual = `${JSON.stringify({ document: doc, dependencies: deps }, null, 2)}\n`;
  if (process.env.UPDATE_COMPILER_V2_GOLDENS === "1") {
    mkdirSync(fixture("issue_173/compiler"), { recursive: true });
    writeFileSync(path, actual, "utf8");
  }
  expect(actual).toBe(readFileSync(path, "utf8"));
  const beforeCompile = JSON.stringify([doc, deps]);
  const first = compileTimelineV2(doc, deps);
  const second = compileTimelineV2(doc, deps);
  expect(first.ok, JSON.stringify(first)).toBe(true);
  expect(second.ok, JSON.stringify(second)).toBe(true);
  if (first.ok && second.ok) {
    expect(first.manifestJson).toBe(second.manifestJson);
    expect(first.reportJson).toBe(second.reportJson);
    const manifestSourceIds = new Set(first.manifest.sources.map((source) => source.id));
    for (const event of first.manifest.events) {
      if (event.provenance.sourceId !== null) expect(manifestSourceIds.has(event.provenance.sourceId)).toBe(true);
    }
  }
  expect(JSON.stringify([doc, deps])).toBe(beforeCompile);
}

describe("pure v2 compiler", () => {
  it("compiles a synthetic derived source to byte-stable canonical artifacts", () => {
    const doc = document();
    const deps = dependencies();
    const before = JSON.stringify([doc, deps]);
    readFrozenInput("flat", doc, deps);
    const first = compileTimelineV2(doc, deps);
    const second = compileTimelineV2(doc, deps);
    expect(first.ok).toBe(true);
    if (!first.ok || !second.ok) return;
    expect(first.manifestJson).toBe(second.manifestJson);
    expect(first.reportJson).toBe(second.reportJson);
    expect(JSON.stringify([doc, deps])).toBe(before);
    readGolden("flat.manifest", first.manifestJson);
    readGolden("flat.report", first.reportJson);
    expect(first.manifest.events.map((event) => event.kind)).toEqual(["primary_visual", "narration"]);
    expect(first.manifest.timeline.durationFrames).toBe(96);
    expect(first.report.status).toBe("ready");
  });

  it("reuses same-rate source bytes with a nonzero authored inpoint", () => {
    const doc = document();
    const deps = dependencies();
    const row = doc.activeDraft.blocks[0] as NarrationBlockV2;
    const root = row.primaryVisualSequence!.slots[0]!;
    if (root.kind !== "content" || root.payload.kind !== "visual") throw new Error("fixture requires a visual root");
    root.payload.sourceUsage = { sourceInFrame: 30 };
    deps.timeline.frameRate = { numerator: 30, denominator: 1 };

    const descriptor = deps.occurrenceResolutions[0]!;
    descriptor.occurrenceSourceInFrame = 30;
    descriptor.selectedSourceRange = null;
    const binding = deps.preparedMedia[0]!;
    binding.mode = "verified_reuse";
    delete binding.derivation;
    binding.requestedRange.sourceInFrame = 30;
    binding.targetRate = { numerator: 30, denominator: 1 };
    binding.timeMapping.sourceOrigin = { numerator: 0, denominator: 1 };
    binding.timeMapping.deliveredOrigin = { numerator: 0, denominator: 1 };
    binding.timeMapping.sourceRate = { numerator: 30, denominator: 1 };
    binding.timeMapping.deliveredRate = { numerator: 30, denominator: 1 };
    binding.timeMapping.sourceFrameMap = structuredClone(descriptor.sourceFrameMap);
    binding.verification.deliveredHash = descriptor.sourceSnapshot.contentHash;
    binding.verification.probeHash = descriptor.sourceSnapshot.probeHash;
    binding.verification.decodedFrameCount = descriptor.sourceFrameMap.decodedPackageFrameCount;
    binding.verification.decodedFrameRate = { numerator: 30, denominator: 1 };
    binding.verification.videoTimeBase = structuredClone(descriptor.sourceFrameMap.packageVideoTimeBase);

    readFrozenInput("reuse-nonzero-inpoint", doc, deps);
    const compiled = compileTimelineV2(doc, deps);
    expect(compiled.ok).toBe(true);
    if (!compiled.ok) return;
    expect(compiled.report.status).toBe("ready");
    expect(compiled.report.mediaPreparation.requirements[0]?.status).toBe("reused");
    expect(compiled.manifest.events.find((event) => event.kind === "primary_visual")?.sourceRange).toEqual({ startFrame: 30, endFrame: 150 });
    readGolden("reuse-nonzero-inpoint.manifest", compiled.manifestJson);
    readGolden("reuse-nonzero-inpoint.report", compiled.reportJson);

    for (const mutate of [
      (copy: CompilerDependenciesV2) => { copy.preparedMedia[0]!.verification.deliveredHash = digest("not original bytes"); },
      (copy: CompilerDependenciesV2) => { copy.preparedMedia[0]!.verification.decodedFrameCount = 120; },
    ]) {
      const invalid = structuredClone(deps);
      mutate(invalid);
      const refused = compileTimelineV2(doc, invalid);
      expect(refused.ok).toBe(true);
      if (refused.ok) {
        expect(refused.report.status).toBe("blocked");
        expect(refused.manifest.events.filter((event) => event.kind === "primary_visual")).toHaveLength(0);
      }
    }
  });

  it("refuses unknown narration duration and blocks stale token timing without partial picture rows", () => {
    const doc = document();
    const noAudio = dependencies();
    delete noAudio.narrationTimingMaps[0]!.audio;
    const refused = compileTimelineV2(doc, noAudio);
    expect(refused.ok).toBe(false);

    const stale = dependencies();
    stale.narrationTimingMaps[0]!.tokens[0].quotedText = "hullo";
    const blocked = compileTimelineV2(doc, stale);
    expect(blocked.ok).toBe(true);
    if (blocked.ok) {
      expect(blocked.report.diagnostics.map((item) => item.code)).toContain("STALE_TIMING_MAP");
      expect(blocked.manifest.events.filter((event) => event.kind === "primary_visual")).toHaveLength(0);
      expect(blocked.manifest.timeline.durationFrames).toBe(96);
    }

    const missingMedia = dependencies();
    missingMedia.occurrenceResolutions = [];
    missingMedia.preparedMedia = [];
    const unbound = compileTimelineV2(doc, missingMedia);
    expect(unbound.ok).toBe(true);
    if (unbound.ok) {
      expect(unbound.report.diagnostics.map((item) => item.code)).toContain("MISSING_OCCURRENCE_BINDING");
      expect(unbound.manifest.events.filter((event) => event.kind === "primary_visual")).toHaveLength(0);
      expect(unbound.manifest.timeline.durationFrames).toBe(96);
    }

    const staleHash = dependencies();
    staleHash.narrationTimingMaps[0]!.audio!.timingHash = digest("stale immutable timing pin");
    const stalePin = compileTimelineV2(doc, staleHash);
    expect(stalePin.ok).toBe(true);
    if (stalePin.ok) {
      expect(stalePin.report.diagnostics.map((item) => item.code)).toContain("TIMING_HASH_MISMATCH");
      expect(stalePin.manifest.events.filter((event) => event.kind === "primary_visual")).toHaveLength(0);
      expect(stalePin.manifest.timeline.durationFrames).toBe(96);
    }
  });

  it("refuses an empty duration-bearing program instead of fabricating a one-frame timeline", () => {
    const doc = document();
    doc.activeDraft.blocks = [];
    const deps = dependencies();
    deps.narrationTimingMaps = [];
    deps.document.textHash = digest("");
    const compiled = compileTimelineV2(doc, deps);
    expect(compiled.ok).toBe(false);
    if (!compiled.ok) expect(compiled.diagnostics.map((item) => item.code)).toContain("EMPTY_PROGRAM");
  });

  it("fails closed on document, text, settings, and prepared-source hash mismatches", () => {
    const doc = document();
    const cases = [
      { change: (deps: CompilerDependenciesV2) => { deps.document.contentHash = digest("wrong document head"); }, code: "DOCUMENT_BINDING_MISMATCH" },
      { change: (deps: CompilerDependenciesV2) => { deps.document.textHash = digest("wrong document text"); }, code: "DOCUMENT_BINDING_MISMATCH" },
      { change: (deps: CompilerDependenciesV2) => { deps.document.settingsHash = digest("wrong project settings"); }, code: "SETTINGS_BINDING_MISMATCH" },
    ];
    for (const item of cases) {
      const result = compileTimelineV2(doc, (() => { const deps = dependencies(); item.change(deps); return deps; })());
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.diagnostics.map((entry) => entry.code)).toContain(item.code);
    }

    const staleSource = dependencies();
    staleSource.preparedMedia[0]!.originalSource.contentHash = digest("unbound source bytes");
    const blocked = compileTimelineV2(doc, staleSource);
    expect(blocked.ok).toBe(true);
    if (blocked.ok) {
      expect(blocked.report.status).toBe("blocked");
      expect(blocked.report.diagnostics.map((item) => item.code)).toContain("PREPARATION_HASH_MISMATCH");
      expect(blocked.manifest.events.filter((event) => event.kind === "primary_visual")).toHaveLength(0);
    }
  });

  it("reports preparation blocked without fabricating a source hash or delivered artifact", () => {
    const doc = document();
    const descriptor = dependencies().occurrenceResolutions[0]!;
    for (const mutate of [
      (deps: CompilerDependenciesV2) => { deps.preparedMedia = []; },
      (deps: CompilerDependenciesV2) => { deps.preparedMedia[0]!.timeMapping.deliveredOrigin = { numerator: 4, denominator: 1 }; },
    ]) {
      const deps = dependencies();
      mutate(deps);
      const compiled = compileTimelineV2(doc, deps);
      expect(compiled.ok).toBe(true);
      if (compiled.ok) {
        expect(compiled.report.status).toBe("blocked");
        expect(compiled.report.mediaPreparation.status).toBe("blocked");
        expect(compiled.report.mediaPreparation.requirements[0]).toMatchObject({
          status: "blocked",
          originalHash: descriptor.sourceSnapshot.contentHash,
          deliveredHash: null,
          bindingHash: null,
        });
        expect(compiled.manifest.events.filter((event) => event.kind === "primary_visual")).toHaveLength(0);
      }
    }
  });

  it("refuses inconsistent source maps, duplicate prepared keys, tracks, and narration audio identities", () => {
    const doc = document();
    const invalidMap = dependencies();
    invalidMap.occurrenceResolutions[0]!.sourceFrameMap.packageFrameZeroLogicalFrame = 1;
    const compileMap = compileTimelineV2(doc, invalidMap);
    expect(compileMap.ok).toBe(false);
    if (!compileMap.ok) expect(compileMap.diagnostics.map((item) => item.code)).toContain("SOURCE_MAPPING_MISMATCH");
    const needsMap = resolveMediaRequirementsV2(doc, {
      timing: dependencies().narrationTimingMaps,
      defaults: invalidMap.authoringDefaults,
      sourceDescriptors: invalidMap.occurrenceResolutions,
      frameRate: invalidMap.timeline.frameRate,
    });
    expect(needsMap.ok).toBe(false);

    const negativeOrigin = dependencies();
    negativeOrigin.occurrenceResolutions[0]!.sourceFrameMap.packageVideoPtsOrigin = { numerator: -1, denominator: 2 };
    const negativeNeeds = resolveMediaRequirementsV2(doc, {
      timing: negativeOrigin.narrationTimingMaps,
      defaults: negativeOrigin.authoringDefaults,
      sourceDescriptors: negativeOrigin.occurrenceResolutions,
      frameRate: negativeOrigin.timeline.frameRate,
    });
    expect(negativeNeeds.ok).toBe(false);

    const invalidDefaults = dependencies();
    Object.assign(invalidDefaults.authoringDefaults.sourceAudioLevelPolicy, { quietGainDb: 1 });
    const defaultsNeeds = resolveMediaRequirementsV2(doc, {
      timing: invalidDefaults.narrationTimingMaps,
      defaults: invalidDefaults.authoringDefaults,
      sourceDescriptors: invalidDefaults.occurrenceResolutions,
      frameRate: invalidDefaults.timeline.frameRate,
    });
    expect(defaultsNeeds.ok).toBe(false);
    if (!defaultsNeeds.ok) expect(defaultsNeeds.diagnostics.map((item) => item.code)).toContain("DEPENDENCIES_SCHEMA_INVALID");

    const duplicateTrack = dependencies();
    duplicateTrack.tracks.push({ ...duplicateTrack.tracks[0] });
    const duplicateTrackResult = compileTimelineV2(doc, duplicateTrack);
    expect(duplicateTrackResult.ok).toBe(false);
    if (!duplicateTrackResult.ok) expect(duplicateTrackResult.diagnostics.map((item) => item.code)).toContain("TRACK_ROLE_COLLISION");

    const wrongNarrationKind = dependencies();
    wrongNarrationKind.tracks.find((track) => track.id === wrongNarrationKind.roles.narrationTrackId)!.kind = "video";
    const wrongNarrationKindResult = compileTimelineV2(doc, wrongNarrationKind);
    expect(wrongNarrationKindResult.ok).toBe(false);
    if (!wrongNarrationKindResult.ok) expect(wrongNarrationKindResult.diagnostics.map((item) => item.code)).toContain("TRACK_ROLE_COLLISION");

    const aliasedSourceAudio = dependencies();
    aliasedSourceAudio.roles.sourceAudioTrackIds = [aliasedSourceAudio.roles.narrationTrackId];
    const aliasedSourceAudioResult = compileTimelineV2(doc, aliasedSourceAudio);
    expect(aliasedSourceAudioResult.ok).toBe(false);
    if (!aliasedSourceAudioResult.ok) expect(aliasedSourceAudioResult.diagnostics.map((item) => item.code)).toContain("TRACK_ROLE_COLLISION");

    const duplicateRequirement = dependencies();
    duplicateRequirement.preparedMedia.push(structuredClone(duplicateRequirement.preparedMedia[0]!));
    const duplicateRequirementResult = compileTimelineV2(doc, duplicateRequirement);
    expect(duplicateRequirementResult.ok).toBe(false);
    if (!duplicateRequirementResult.ok) expect(duplicateRequirementResult.diagnostics.map((item) => item.code)).toContain("PREPARATION_HASH_MISMATCH");

    const conflictingAsset = dependencies();
    const secondMap = structuredClone(conflictingAsset.narrationTimingMaps[0]!);
    secondMap.blockId = id(90);
    secondMap.audio!.durationSamples += 1;
    conflictingAsset.narrationTimingMaps.push(secondMap);
    const conflictingResult = compileTimelineV2(doc, conflictingAsset);
    expect(conflictingResult.ok).toBe(false);
    if (!conflictingResult.ok) expect(conflictingResult.diagnostics.map((item) => item.code)).toContain("NARRATION_AUDIO_BINDING_MISMATCH");

    const visualOnly = visualOnlyDocument(intentionalSlateBlock());
    const extraMap = visualOnlyDependencies();
    extraMap.narrationTimingMaps = [dependencies().narrationTimingMaps[0]!];
    extraMap.narrationTimingMaps[0]!.blockId = (visualOnly.activeDraft.blocks[0] as VisualOnlyBlockV2).id;
    const extraMapResult = compileTimelineV2(visualOnly, extraMap);
    expect(extraMapResult.ok).toBe(true);
    if (extraMapResult.ok) expect(extraMapResult.report.diagnostics.map((item) => item.code)).toContain("STALE_TIMING_MAP");
  });

  it("rejects unpaired surrogates and UTF-16 token offsets that split a valid pair", () => {
    const malformedRow = document();
    const malformed = malformedRow.activeDraft.blocks[0] as NarrationBlockV2;
    malformed.text = "hello\ud800";
    malformed.tokens[0] = { ...malformed.tokens[0], value: "hello\ud800", endOffset: 6 };
    const invalidText = compileTimelineV2(malformedRow, dependencies());
    expect(invalidText.ok).toBe(false);
    if (!invalidText.ok) expect(invalidText.diagnostics.map((item) => item.code)).toContain("DOCUMENT_TEXT_INVALID");

    const splitPairRow = document();
    const splitPair = splitPairRow.activeDraft.blocks[0] as NarrationBlockV2;
    splitPair.text = "🌍";
    splitPair.tokens[0] = { ...splitPair.tokens[0], value: "\ud83c", startOffset: 0, endOffset: 1 };
    const invalidToken = compileTimelineV2(splitPairRow, dependencies());
    expect(invalidToken.ok).toBe(false);
    if (!invalidToken.ok) expect(invalidToken.diagnostics.map((item) => item.code)).toContain("DOCUMENT_TOKEN_TEXT_INVALID");
  });

  it("refuses exact boundary evidence that cannot be represented safely on the wire", () => {
    const doc = document();
    const deps = dependencies();
    deps.timeline.frameRate = { numerator: 24000, denominator: 1001 };
    deps.preparedMedia[0]!.targetRate = { numerator: 24000, denominator: 1001 };
    deps.preparedMedia[0]!.timeMapping.deliveredRate = { numerator: 24000, denominator: 1001 };
    deps.preparedMedia[0]!.verification.decodedFrameRate = { numerator: 24000, denominator: 1001 };
    deps.preparedMedia[0]!.verification.videoTimeBase = { numerator: 1001, denominator: 24000 };
    deps.preparedMedia[0]!.verification.decodedFrameCount = 96;
    deps.narrationTimingMaps[0]!.tokens[0].startTime = { numerator: 1, denominator: 9007199254740881 };
    const result = compileTimelineV2(doc, deps);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.diagnostics.map((item) => item.code)).toContain("COMPILATION_PRECONDITION_FAILED");
  });

  it("shares exact source requirements with P5 and reports original-bound insufficiency", () => {
    const doc = document();
    const deps = dependencies();
    const needs = resolveMediaRequirementsV2(doc, { timing: deps.narrationTimingMaps, defaults: deps.authoringDefaults, sourceDescriptors: deps.occurrenceResolutions, frameRate: deps.timeline.frameRate });
    expect(needs.ok).toBe(true);
    if (needs.ok) expect(needs.requirements[0]?.requiredSourceRange).toEqual({ startFrame: 0, endFrame: 120 });

    deps.occurrenceResolutions[0]!.logicalSourceBounds.endFrame = 100;
    const blocked = compileTimelineV2(doc, deps);
    expect(blocked.ok).toBe(true);
    if (blocked.ok) {
      expect(blocked.report.diagnostics.map((item) => item.code)).toContain("SOURCE_INSUFFICIENT");
      expect(blocked.manifest.events.filter((event) => event.kind === "primary_visual")).toHaveLength(0);
    }
  });

  it("keys two trims of the same media reference to their own prepared source identity", () => {
    const doc = document();
    const row = doc.activeDraft.blocks[0] as NarrationBlockV2;
    const overlayId = id(20);
    const overlayPayloadId = id(21);
    row.overlayEvents.push({
      id: overlayId,
      version: 1,
      payload: {
        kind: "visual", payloadId: overlayPayloadId, pictureKind: "clip",
        source: { kind: "media_reference", mediaReferenceId: id(8) },
        sourceUsage: { sourceInFrame: 30 }, audioPolicy: "mute", framingPolicy: "contain",
      },
      timing: {
        kind: "timed", durationMs: 1000,
        start: { kind: "word", anchor: { blockId: row.id, tokenId: id(7), affinity: "before", quotedWord: "hello", anchorVersion: row.version } },
      },
    });

    const deps = dependencies();
    const descriptor = structuredClone(deps.occurrenceResolutions[0]!);
    descriptor.owner = { kind: "overlay_event", blockId: row.id, overlayEventId: overlayId };
    descriptor.payloadId = overlayPayloadId;
    descriptor.occurrenceSourceInFrame = 30;
    descriptor.selectedSourceRange = { startFrame: 30, endFrame: 90 };
    descriptor.preparedMediaRequirementKey = "prep:occurrence-2";
    const binding = structuredClone(deps.preparedMedia[0]!);
    binding.requirementKey = "prep:occurrence-2";
    binding.requestedRange.sourceInFrame = 30;
    binding.requestedRange.duration = { numerator: 1, denominator: 1 };
    binding.timeMapping.sourceOrigin = { numerator: 1, denominator: 1 };
    binding.timeMapping.mappingHash = digest("overlay preparation mapping");
    binding.verification.deliveredHash = digest("overlay prepared media");
    binding.verification.decodedFrameCount = 24;
    binding.derivation = { ...binding.derivation!, outputHash: binding.verification.deliveredHash };
    binding.artifactLocator = "prepared/overlay-trim.mov";
    deps.occurrenceResolutions.push(descriptor);
    deps.preparedMedia.push(binding);

    const compiled = compileTimelineV2(doc, deps);
    expect(compiled.ok).toBe(true);
    if (compiled.ok) {
      const visuals = compiled.manifest.events.filter((event) => event.kind === "primary_visual" || event.kind === "overlay_visual");
      const byPayload = new Map(visuals.map((event) => [event.provenance.payloadId, event.provenance.sourceId]));
      expect(byPayload.get(id(17))).toBeDefined();
      expect(byPayload.get(overlayPayloadId)).toBeDefined();
      expect(byPayload.get(id(17))).not.toBe(byPayload.get(overlayPayloadId));
      expect(compiled.manifest.sources.filter((source) => "mediaReferenceId" in source)).toHaveLength(2);
    }
  });

  it("blocks overlapping Quiet source-audio occurrences rather than mixing them", () => {
    const doc = document();
    const row = doc.activeDraft.blocks[0] as NarrationBlockV2;
    const root = row.primaryVisualSequence!.slots[0]!;
    if (root.kind !== "content" || root.payload.kind !== "visual") throw new Error("fixture must have a visual root");
    root.payload.audioPolicy = "quiet";
    row.text = "hello later";
    row.tokens.push({ id: id(26), value: "later", startOffset: 6, endOffset: 11 });
    const overlayId = id(20);
    const overlayPayloadId = id(21);
    row.overlayEvents.push({
      id: overlayId, version: 1,
      payload: { kind: "visual", payloadId: overlayPayloadId, pictureKind: "clip", source: { kind: "media_reference", mediaReferenceId: id(8) }, sourceUsage: { sourceInFrame: 30 }, audioPolicy: "quiet", framingPolicy: "contain" },
      timing: { kind: "timed", durationMs: 1000, start: { kind: "word", anchor: { blockId: row.id, tokenId: id(7), affinity: "before", quotedWord: "hello", anchorVersion: row.version } } },
    });
    const nestedOverlayId = id(28);
    const nestedOverlayPayloadId = id(29);
    row.overlayEvents.push({
      id: nestedOverlayId, version: 1,
      payload: { kind: "visual", payloadId: nestedOverlayPayloadId, pictureKind: "clip", source: { kind: "media_reference", mediaReferenceId: id(27) }, sourceUsage: { sourceInFrame: 90 }, audioPolicy: "quiet", framingPolicy: "contain" },
      timing: { kind: "timed", durationMs: 1000, start: { kind: "word", anchor: { blockId: row.id, tokenId: id(26), affinity: "before", quotedWord: "later", anchorVersion: row.version } } },
    });
    const deps = dependencies();
    deps.document.textHash = digest(row.text);
    deps.narrationTimingMaps[0]!.textHash = digest(row.text);
    deps.narrationTimingMaps[0]!.timingHash = digest("nested audio overlap timing");
    deps.narrationTimingMaps[0]!.audio!.timingHash = deps.narrationTimingMaps[0]!.timingHash;
    deps.narrationTimingMaps[0]!.tokens.push({ tokenId: id(26), startOffset: 6, endOffset: 11, quotedText: "later", startTime: { numerator: 2, denominator: 1 }, audibleEnd: { numerator: 5, denominator: 2 }, endBasis: "evidenced_audible_end" });
    const sourceHash = digest("source audio bytes");
    const rootDescriptor = deps.occurrenceResolutions[0]!;
    const stream = { streamIndex: 0, sampleRate: 48000, packagePtsOrigin: { numerator: 0, denominator: 1 }, loggedTimeAtPackageOrigin: { numerator: 0, denominator: 1 }, audioHash: sourceHash, probeHash: rootDescriptor.sourceSnapshot.probeHash };
    rootDescriptor.sourceFrameMap.sourceAudioStreamMappings = [stream];
    deps.preparedMedia[0]!.timeMapping.sourceFrameMap = structuredClone(rootDescriptor.sourceFrameMap);
    deps.preparedMedia[0]!.verification.sourceAudio = { status: "aligned", offset: { numerator: 0, denominator: 1 }, maxDrift: { numerator: 0, denominator: 1 }, sampleRate: 48000 };

    const overlayDescriptor = structuredClone(rootDescriptor);
    overlayDescriptor.owner = { kind: "overlay_event", blockId: row.id, overlayEventId: overlayId };
    overlayDescriptor.payloadId = overlayPayloadId;
    overlayDescriptor.occurrenceSourceInFrame = 30;
    overlayDescriptor.selectedSourceRange = { startFrame: 30, endFrame: 90 };
    overlayDescriptor.preparedMediaRequirementKey = "prep:quiet-overlay";
    const overlayBinding = structuredClone(deps.preparedMedia[0]!);
    overlayBinding.requirementKey = "prep:quiet-overlay";
    overlayBinding.requestedRange = { sourceInFrame: 30, duration: { numerator: 1, denominator: 1 }, preHandle: { numerator: 0, denominator: 1 }, postHandle: { numerator: 0, denominator: 1 } };
    overlayBinding.timeMapping.sourceOrigin = { numerator: 1, denominator: 1 };
    overlayBinding.timeMapping.sourceFrameMap = structuredClone(overlayDescriptor.sourceFrameMap);
    overlayBinding.verification.decodedFrameCount = 24;
    overlayBinding.verification.sourceAudio = { status: "aligned", offset: { numerator: 0, denominator: 1 }, maxDrift: { numerator: 0, denominator: 1 }, sampleRate: 48000 };
    overlayBinding.verification.deliveredHash = digest("quiet overlay prepared media");
    overlayBinding.derivation = { ...overlayBinding.derivation!, commandHash: digest("quiet overlay command"), outputHash: overlayBinding.verification.deliveredHash };
    deps.occurrenceResolutions.push(overlayDescriptor);
    deps.preparedMedia.push(overlayBinding);

    const nestedOverlayDescriptor = structuredClone(rootDescriptor);
    nestedOverlayDescriptor.owner = { kind: "overlay_event", blockId: row.id, overlayEventId: nestedOverlayId };
    nestedOverlayDescriptor.payloadId = nestedOverlayPayloadId;
    nestedOverlayDescriptor.mediaReferenceId = id(27);
    nestedOverlayDescriptor.occurrenceSourceInFrame = 90;
    nestedOverlayDescriptor.selectedSourceRange = null;
    nestedOverlayDescriptor.preparedMediaRequirementKey = "prep:quiet-overlay-nested";
    const nestedOverlayBinding = structuredClone(deps.preparedMedia[0]!);
    nestedOverlayBinding.requirementKey = "prep:quiet-overlay-nested";
    nestedOverlayBinding.originalSource.mediaReferenceId = id(27);
    nestedOverlayBinding.requestedRange = { sourceInFrame: 90, duration: { numerator: 1, denominator: 1 }, preHandle: { numerator: 0, denominator: 1 }, postHandle: { numerator: 0, denominator: 1 } };
    nestedOverlayBinding.timeMapping.sourceOrigin = { numerator: 3, denominator: 1 };
    nestedOverlayBinding.timeMapping.sourceFrameMap = structuredClone(nestedOverlayDescriptor.sourceFrameMap);
    nestedOverlayBinding.verification.decodedFrameCount = 24;
    nestedOverlayBinding.verification.sourceAudio = { status: "aligned", offset: { numerator: 0, denominator: 1 }, maxDrift: { numerator: 0, denominator: 1 }, sampleRate: 48000 };
    nestedOverlayBinding.verification.deliveredHash = digest("nested quiet overlay prepared media");
    nestedOverlayBinding.artifactLocator = "prepared/quiet-overlay-nested.mov";
    nestedOverlayBinding.derivation = { ...nestedOverlayBinding.derivation!, commandHash: digest("nested quiet overlay command"), outputHash: nestedOverlayBinding.verification.deliveredHash };
    deps.occurrenceResolutions.push(nestedOverlayDescriptor);
    deps.preparedMedia.push(nestedOverlayBinding);
    deps.tracks.push({ id: "source-audio", kind: "audio", index: 5, name: "Source audio" });
    deps.roles.sourceAudioTrackIds = ["source-audio"];

    const compiled = compileTimelineV2(doc, deps);
    expect(compiled.ok).toBe(true);
    if (compiled.ok) {
      expect(compiled.report.status).toBe("blocked");
      expect(compiled.report.diagnostics.map((item) => item.code)).toContain("SOURCE_AUDIO_OVERLAP");
      expect(compiled.manifest.events.filter((event) => event.kind === "source_audio").map((event) => event.audio?.gainDb)).toEqual([-18, -18, -18]);
      expect(compiled.manifest.events.filter((event) => event.kind === "source_audio")).toHaveLength(3);
      const nestedAudioId = compiled.manifest.events.find((event) => event.kind === "source_audio" && event.provenance.overlayEventId === nestedOverlayId)?.eventId;
      expect(compiled.report.diagnostics.some((item) => item.code === "SOURCE_AUDIO_OVERLAP" && item.entity.id === nestedAudioId)).toBe(true);
    }
  });

  it("keeps mixed-rate source-read coverage separate from delivered frames and audio samples", () => {
    const doc = document();
    const row = doc.activeDraft.blocks[0] as NarrationBlockV2;
    const slot = row.primaryVisualSequence!.slots[0]!;
    if (slot.kind !== "content" || slot.payload.kind !== "visual") throw new Error("fixture must have a visual root");
    slot.payload.sourceUsage = { sourceInFrame: 3010 };
    slot.payload.audioPolicy = "quiet";

    const deps = dependencies();
    deps.timeline.frameRate = { numerator: 24000, denominator: 1001 };
    const timing = deps.narrationTimingMaps[0]!;
    timing.audio!.durationSamples = 480480;
    const descriptor = deps.occurrenceResolutions[0]!;
    descriptor.logicalSourceBounds = { startFrame: 3000, endFrame: 4000, frameRate: { numerator: 25, denominator: 1 } };
    descriptor.occurrenceSourceInFrame = 3010;
    descriptor.selectedSourceRange = null;
    descriptor.sourceFrameMap.packageFrameZeroLogicalFrame = 3000;
    descriptor.sourceFrameMap.decodedPackageFrameRate = { numerator: 25, denominator: 1 };
    descriptor.sourceFrameMap.decodedPackageFrameCount = 1000;
    descriptor.sourceFrameMap.loggedTimeAtPackageFrameZero = { numerator: 0, denominator: 1 };
    descriptor.sourceFrameMap.sourceAudioStreamMappings = [{
      streamIndex: 0, sampleRate: 48000,
      packagePtsOrigin: { numerator: 0, denominator: 1 },
      loggedTimeAtPackageOrigin: { numerator: 0, denominator: 1 },
      audioHash: digest("source audio bytes"), probeHash: descriptor.sourceSnapshot.probeHash,
    }];
    const binding = deps.preparedMedia[0]!;
    binding.requestedRange = { sourceInFrame: 3010, duration: { numerator: 1001, denominator: 100 }, preHandle: { numerator: 0, denominator: 1 }, postHandle: { numerator: 0, denominator: 1 } };
    binding.targetRate = { numerator: 24000, denominator: 1001 };
    binding.timeMapping.sourceOrigin = { numerator: 2, denominator: 5 };
    binding.timeMapping.sourceRate = { numerator: 25, denominator: 1 };
    binding.timeMapping.deliveredRate = { numerator: 24000, denominator: 1001 };
    binding.timeMapping.sourceFrameMap = structuredClone(descriptor.sourceFrameMap);
    binding.verification.decodedFrameCount = 240;
    binding.verification.decodedFrameRate = { numerator: 24000, denominator: 1001 };
    binding.verification.videoTimeBase = { numerator: 1001, denominator: 24000 };
    binding.verification.sourceAudio = { status: "aligned", offset: { numerator: 0, denominator: 1 }, maxDrift: { numerator: 0, denominator: 1 }, sampleRate: 48000 };
    binding.derivation = { ...binding.derivation!, commandHash: digest("mixed-rate prepare"), outputHash: binding.verification.deliveredHash };
    deps.tracks.push({ id: "source-audio", kind: "audio", index: 5, name: "Source audio" });
    deps.roles.sourceAudioTrackIds = ["source-audio"];

    const needs = resolveMediaRequirementsV2(doc, { timing: deps.narrationTimingMaps, defaults: deps.authoringDefaults, sourceDescriptors: deps.occurrenceResolutions, frameRate: deps.timeline.frameRate });
    expect(needs.ok).toBe(true);
    if (needs.ok) {
      expect(needs.requirements[0]?.requiredSourceRange).toEqual({ startFrame: 3010, endFrame: 3261 });
      expect(needs.requirements[0]?.requestedRange).toMatchObject({ sourceInFrame: 3010, duration: { numerator: 1001, denominator: 100 } });
    }
    const compiled = compileTimelineV2(doc, deps);
    expect(compiled.ok).toBe(true);
    if (compiled.ok) {
      expect(compiled.manifest.timeline.durationFrames).toBe(240);
      expect(compiled.manifest.events.find((event) => event.kind === "primary_visual")?.sourceRange).toEqual({ startFrame: 0, endFrame: 240 });
      expect(compiled.manifest.events.find((event) => event.kind === "source_audio")?.audio?.sampleRange).toEqual({ startFrame: 19200, endFrame: 499680 });
    }
  });

  it("quantizes visual-only default and override durations once at NTSC and alternate rates", () => {
    const cases = [
      { name: "visual-only-default-ntsc", rate: { numerator: 24000, denominator: 1001 }, override: undefined, expectedFrames: 72 },
      { name: "visual-only-default-25fps", rate: { numerator: 25, denominator: 1 }, override: undefined, expectedFrames: 75 },
      { name: "visual-only-override-ntsc", rate: { numerator: 24000, denominator: 1001 }, override: 2500, expectedFrames: 60 },
    ];
    for (const item of cases) {
      const doc = visualOnlyDocument(intentionalSlateBlock(item.override));
      const deps = visualOnlyDependencies();
      deps.timeline.frameRate = item.rate;
      readFrozenInput(item.name, doc, deps);
      const compiled = compileTimelineV2(doc, deps);
      expect(compiled.ok, JSON.stringify(compiled)).toBe(true);
      if (compiled.ok) {
        expect(compiled.manifest.timeline.durationFrames).toBe(item.expectedFrames);
        expect(compiled.manifest.events[0]?.recordRange).toEqual({ startFrame: 0, endFrame: item.expectedFrames });
        readGolden(`${item.name}.manifest`, compiled.manifestJson);
        readGolden(`${item.name}.report`, compiled.reportJson);
      }
    }
  });

  it("holds one verified still frame for each media-backed visual-only kind", () => {
    const mediaKinds = [
      { name: "visual-only-image-still", pictureKind: "image", source: { kind: "media_reference", mediaReferenceId: id(60) }, system: "local_import", mediaReferenceId: id(60) },
      { name: "visual-only-capture-still", pictureKind: "capture", source: { kind: "capture_revision", captureId: id(61), revisionId: id(62) }, system: "captured_frame", mediaReferenceId: id(63) },
      { name: "visual-only-graphic-still", pictureKind: "graphic", source: { kind: "graphic_revision", graphicId: id(64), revisionId: id(65) }, system: "graphic_asset", mediaReferenceId: id(66) },
    ] as const;
    const timingCases = [
      { name: "ntsc-default", rate: { numerator: 24000, denominator: 1001 }, durationOverrideMs: undefined, expectedFrames: 72 },
      { name: "25fps-default", rate: { numerator: 25, denominator: 1 }, durationOverrideMs: undefined, expectedFrames: 75 },
      { name: "ntsc-override", rate: { numerator: 24000, denominator: 1001 }, durationOverrideMs: 2500, expectedFrames: 60 },
    ] as const;
    for (const item of mediaKinds) {
      for (const timingCase of timingCases) {
      const scenarioName = `${item.name}-${timingCase.name}`;
      const block: VisualOnlyBlockV2 = {
        type: "visual_only", id: id(30), orderKey: "a0", version: 1,
        payload: { kind: "visual", payloadId: id(31), pictureKind: item.pictureKind, source: item.source, audioPolicy: "mute", framingPolicy: "contain" },
        visualOnlyTiming: { kind: "visual_only", ...(timingCase.durationOverrideMs === undefined ? {} : { durationOverrideMs: timingCase.durationOverrideMs }) },
      };
      const doc = visualOnlyDocument(block);
      const deps = dependencies();
      deps.narrationTimingMaps = [];
      deps.document.textHash = digest("");
      deps.timeline.frameRate = timingCase.rate;
      const descriptor = deps.occurrenceResolutions[0]!;
      descriptor.owner = { kind: "visual_only_block", blockId: block.id };
      descriptor.payloadId = block.payload.payloadId;
      descriptor.mediaReferenceId = item.mediaReferenceId;
      descriptor.sourceSnapshot.system = item.system;
      descriptor.occurrenceSourceInFrame = 0;
      descriptor.selectedSourceRange = null;
      descriptor.logicalSourceBounds = { startFrame: 0, endFrame: 1, frameRate: { numerator: 25, denominator: 1 } };
      descriptor.sourceFrameMap.packageFrameZeroLogicalFrame = 0;
      descriptor.sourceFrameMap.decodedPackageFrameRate = { numerator: 25, denominator: 1 };
      descriptor.sourceFrameMap.decodedPackageFrameCount = 1;

      const binding = deps.preparedMedia[0]!;
      binding.originalSource.mediaReferenceId = item.mediaReferenceId;
      binding.requestedRange = { sourceInFrame: 0, duration: { numerator: 1, denominator: 25 }, preHandle: { numerator: 0, denominator: 1 }, postHandle: { numerator: 0, denominator: 1 } };
      binding.targetRate = timingCase.rate;
      binding.timeMapping.sourceOrigin = { numerator: 0, denominator: 1 };
      binding.timeMapping.deliveredOrigin = { numerator: 0, denominator: 1 };
      binding.timeMapping.sourceRate = { numerator: 25, denominator: 1 };
      binding.timeMapping.deliveredRate = timingCase.rate;
      binding.timeMapping.sourceFrameMap = structuredClone(descriptor.sourceFrameMap);
      binding.verification.decodedFrameCount = 1;
      binding.verification.decodedFrameRate = timingCase.rate;
      binding.verification.videoTimeBase = { numerator: timingCase.rate.denominator, denominator: timingCase.rate.numerator };
      binding.verification.deliveredHash = digest(`${scenarioName} delivered still`);
      binding.derivation = { ...binding.derivation!, outputHash: binding.verification.deliveredHash, commandHash: digest(`${scenarioName} command`) };

      readFrozenInput(scenarioName, doc, deps);
      const compiled = compileTimelineV2(doc, deps);
      expect(compiled.ok, JSON.stringify(compiled)).toBe(true);
      if (compiled.ok) {
        expect(compiled.manifest.durationBasis.kind).toBe("visual_only_duration");
        expect(compiled.manifest.timeline.durationFrames).toBe(timingCase.expectedFrames);
        expect(compiled.manifest.events[0]?.recordRange).toEqual({ startFrame: 0, endFrame: timingCase.expectedFrames });
        expect(compiled.manifest.events[0]?.sourceRange).toEqual({ startFrame: 0, endFrame: 1 });
        expect(compiled.manifest.events[0]?.pictureTreatment).toEqual({ kind: "still_frame", pictureKind: item.pictureKind, framingPolicy: "contain" });
        expect(compiled.report.mediaPreparation.requirements[0]?.status).toBe("prepared");
        readGolden(`${scenarioName}.manifest`, compiled.manifestJson);
        readGolden(`${scenarioName}.report`, compiled.reportJson);
      }
      }
    }
  });

  it("serializes one-frame holds for narrated primary and overlay images", () => {
    const doc = document();
    const row = doc.activeDraft.blocks[0] as NarrationBlockV2;
    const root = row.primaryVisualSequence!.slots[0]!;
    if (root.kind !== "content" || root.payload.kind !== "visual") throw new Error("fixture requires a visual root");
    root.payload.pictureKind = "image";
    root.payload.sourceUsage = null;
    root.payload.framingPolicy = "contain";

    const overlayId = id(83);
    const overlayPayloadId = id(84);
    row.overlayEvents.push({
      id: overlayId, version: 1,
      payload: { kind: "visual", payloadId: overlayPayloadId, pictureKind: "image", source: { kind: "media_reference", mediaReferenceId: id(8) }, sourceUsage: null, audioPolicy: "mute", framingPolicy: "cover" },
      timing: { kind: "timed", durationMs: 1000, start: { kind: "word", anchor: { blockId: row.id, tokenId: id(7), affinity: "before", quotedWord: "hello", anchorVersion: row.version } } },
    });

    const deps = dependencies();
    const rootDescriptor = deps.occurrenceResolutions[0]!;
    rootDescriptor.selectedSourceRange = null;
    const rootBinding = deps.preparedMedia[0]!;
    rootBinding.requestedRange = { sourceInFrame: 0, duration: { numerator: 1, denominator: 30 }, preHandle: { numerator: 0, denominator: 1 }, postHandle: { numerator: 0, denominator: 1 } };
    rootBinding.targetRate = { numerator: 24, denominator: 1 };
    rootBinding.timeMapping.sourceOrigin = { numerator: 0, denominator: 1 };
    rootBinding.timeMapping.sourceRate = { numerator: 30, denominator: 1 };
    rootBinding.timeMapping.deliveredRate = { numerator: 24, denominator: 1 };
    rootBinding.timeMapping.sourceFrameMap = structuredClone(rootDescriptor.sourceFrameMap);
    rootBinding.verification.decodedFrameCount = 1;
    rootBinding.verification.decodedFrameRate = { numerator: 24, denominator: 1 };
    rootBinding.verification.videoTimeBase = { numerator: 1, denominator: 24 };
    rootBinding.verification.deliveredHash = digest("narrated primary still frame");
    rootBinding.derivation = { ...rootBinding.derivation!, commandHash: digest("narrated primary still command"), outputHash: rootBinding.verification.deliveredHash };

    const overlayDescriptor = structuredClone(rootDescriptor);
    overlayDescriptor.owner = { kind: "overlay_event", blockId: row.id, overlayEventId: overlayId };
    overlayDescriptor.payloadId = overlayPayloadId;
    overlayDescriptor.occurrenceSourceInFrame = 30;
    overlayDescriptor.preparedMediaRequirementKey = "prep:narrated-image-overlay";
    const overlayBinding = structuredClone(rootBinding);
    overlayBinding.requirementKey = "prep:narrated-image-overlay";
    overlayBinding.requestedRange.sourceInFrame = 30;
    overlayBinding.timeMapping.sourceOrigin = { numerator: 1, denominator: 1 };
    overlayBinding.timeMapping.sourceFrameMap = structuredClone(overlayDescriptor.sourceFrameMap);
    overlayBinding.verification.deliveredHash = digest("narrated overlay still frame");
    overlayBinding.derivation = { ...overlayBinding.derivation!, commandHash: digest("narrated overlay still command"), outputHash: overlayBinding.verification.deliveredHash };
    overlayBinding.artifactLocator = "prepared/narrated-overlay-still.mov";
    deps.occurrenceResolutions.push(overlayDescriptor);
    deps.preparedMedia.push(overlayBinding);
    deps.tracks.push({ id: "video-overlay", kind: "video", index: 5, name: "Overlay" });
    deps.roles.overlayTrackIds = ["video-overlay"];

    readFrozenInput("narrated-image-still-holds", doc, deps);
    const compiled = compileTimelineV2(doc, deps);
    expect(compiled.ok, JSON.stringify(compiled)).toBe(true);
    if (compiled.ok) {
      const rootEvent = compiled.manifest.events.find((event) => event.kind === "primary_visual");
      const overlayEvent = compiled.manifest.events.find((event) => event.kind === "overlay_visual");
      expect(rootEvent?.recordRange).toEqual({ startFrame: 0, endFrame: 96 });
      expect(rootEvent?.sourceRange).toEqual({ startFrame: 0, endFrame: 1 });
      expect(rootEvent?.pictureTreatment).toEqual({ kind: "still_frame", pictureKind: "image", framingPolicy: "contain" });
      expect(overlayEvent?.recordRange).toEqual({ startFrame: 0, endFrame: 24 });
      expect(overlayEvent?.sourceRange).toEqual({ startFrame: 0, endFrame: 1 });
      expect(overlayEvent?.pictureTreatment).toEqual({ kind: "still_frame", pictureKind: "image", framingPolicy: "cover" });
      readGolden("narrated-image-still-holds.manifest", compiled.manifestJson);
      readGolden("narrated-image-still-holds.report", compiled.reportJson);
    }
  });

  it("freezes presenter-still fallback, project default, and a distinct script override", () => {
    const cases = [
      { name: "presenter-still-fallback", project: null, override: null, locator: "assets/vera/generic-torso-v1.svg" },
      { name: "presenter-still-project-default", project: stillReference(id(50), id(51), "project-presenter.svg", "assets/project/presenter.svg"), override: null, locator: "assets/project/presenter.svg" },
      { name: "presenter-still-script-override", project: stillReference(id(52), id(53), "project-default.svg", "assets/project/default.svg"), override: stillReference(id(54), id(55), "script-override.svg", "assets/script/override.svg"), locator: "assets/script/override.svg" },
    ];
    for (const item of cases) {
      const doc = presenterDocument();
      if (item.override) doc.scriptSettings = { presenterStillOverride: item.override };
      const deps = dependencies();
      deps.occurrenceResolutions = [];
      deps.preparedMedia = [];
      deps.authoringDefaults.presenterStill = item.project;
      readFrozenInput(item.name, doc, deps);
      const compiled = compileTimelineV2(doc, deps);
      expect(compiled.ok, JSON.stringify(compiled)).toBe(true);
      if (compiled.ok) {
        const event = compiled.manifest.events.find((candidate) => candidate.kind === "placeholder");
        expect(event?.pictureTreatment).toMatchObject({ kind: "still", reference: { projectRelativeLocator: item.locator }, composition: { framingPolicy: "contain", horizontalAlignment: "center", verticalAlignment: "center", backgroundColor: "#000000", motionPreset: "none" } });
        expect(compiled.report.manualCompletionItems).toHaveLength(1);
        expect(compiled.report.eventResults.find((result) => result.eventId === event?.eventId)?.disposition).toBe("manual_completion");
        if (item.override) expect(compiled.manifest.authoringDefaults.presenterStill).toEqual(item.override);
        readGolden(`${item.name}.manifest`, compiled.manifestJson);
        readGolden(`${item.name}.report`, compiled.reportJson);
      }
    }

    const recordedDocument = presenterDocument();
    const recordedRow = recordedDocument.activeDraft.blocks[0] as NarrationBlockV2;
    const recordedSlot = recordedRow.primaryVisualSequence!.slots[0]!;
    if (recordedSlot.kind !== "content" || recordedSlot.payload.kind !== "on_camera") throw new Error("fixture requires an On Camera slot");
    recordedSlot.payload.presenterChoiceId = id(81);
    const recordedDeps = dependencies();
    recordedDeps.occurrenceResolutions = [];
    recordedDeps.preparedMedia = [];
    recordedDeps.presenterAlignmentResolutions = [{
      schemaVersion: "presenter-alignment/v1", slotId: recordedSlot.id, takeId: id(81),
      masterIdentity: { masterId: id(82), contentHash: digest("presenter master"), probeHash: digest("presenter probe"), frameRate: { numerator: 30, denominator: 1 } },
      sourceStartFrame: 0, alignmentVersion: "alignment/v1", precision: "audible_word",
      expectedWord: { tokenId: id(7), text: "hello" }, recognizedWord: { text: "hello" },
    }];
    readFrozenInput("recorded-presenter-without-provider", recordedDocument, recordedDeps);
    const recorded = compileTimelineV2(recordedDocument, recordedDeps);
    expect(recorded.ok).toBe(true);
    if (recorded.ok) {
      expect(recorded.report.status).toBe("blocked");
      expect(recorded.manifest.visualSequenceResolutions[0]?.presenterChoice).toBe("recorded");
      expect(recorded.manifest.events.filter((event) => event.kind === "placeholder")).toHaveLength(0);
      expect(recorded.report.diagnostics.map((item) => item.code)).toContain("MIGRATION_REVIEW_REQUIRED");
      expect(recorded.report.manualCompletionItems).toHaveLength(0);
      readGolden("recorded-presenter-without-provider.manifest", recorded.manifestJson);
      readGolden("recorded-presenter-without-provider.report", recorded.reportJson);
    }
  });

  it("forces undefined request slates only in Preview and rejects them for Release", () => {
    const makeUndefined = (): ScriptDocumentV2 => {
      const value = document();
      const row = value.activeDraft.blocks[0] as NarrationBlockV2;
      const root = row.primaryVisualSequence!.slots[0]!;
      if (root.kind !== "content") throw new Error("fixture must have a root slot");
      root.payload = { kind: "undefined", payloadId: id(17), description: "Choose a picture" };
      return value;
    };
    const previewDoc = makeUndefined();
    const previewDeps = dependencies();
    previewDeps.occurrenceResolutions = [];
    previewDeps.preparedMedia = [];
    readFrozenInput("undefined-preview-not-forced", previewDoc, previewDeps);
    const ordinary = compileTimelineV2(previewDoc, previewDeps);
    expect(ordinary.ok).toBe(true);
    if (ordinary.ok) {
      expect(ordinary.report.status).toBe("blocked");
      expect(ordinary.report.diagnostics.map((item) => item.code)).toContain("VISUAL_UNDEFINED");
      expect(ordinary.manifest.events.filter((event) => event.kind === "placeholder")).toHaveLength(0);
      expect(ordinary.report.summary.placeholderCount).toBe(0);
      readGolden("undefined-preview-not-forced.manifest", ordinary.manifestJson);
      readGolden("undefined-preview-not-forced.report", ordinary.reportJson);
    }

    previewDeps.build.forcePreviewVisuals = true;
    readFrozenInput("undefined-preview-forced", previewDoc, previewDeps);
    const forced = compileTimelineV2(previewDoc, previewDeps);
    expect(forced.ok).toBe(true);
    if (forced.ok) {
      expect(forced.report.status).toBe("blocked");
      const slate = forced.manifest.events.find((event) => event.kind === "placeholder");
      expect(slate?.pictureTreatment).toEqual({ kind: "slate", purpose: "undefined", text: "Choose a picture" });
      const slateResult = forced.report.eventResults.find((result) => result.eventId === slate?.eventId);
      expect(slateResult?.disposition).toBe("blocked");
      expect(slateResult?.message).toContain("Blocked undefined visual");
      expect(forced.report.summary).toMatchObject({ blockedCount: 1, placeholderCount: 0 });
      readGolden("undefined-preview-forced.manifest", forced.manifestJson);
      readGolden("undefined-preview-forced.report", forced.reportJson);
    }

    const releaseDeps = structuredClone(previewDeps);
    releaseDeps.build.buildClass = "release";
    const release = compileTimelineV2(previewDoc, releaseDeps);
    expect(release.ok).toBe(false);
    if (!release.ok) expect(release.diagnostics.map((item) => item.code)).toContain("DEPENDENCIES_SCHEMA_INVALID");

    const unresolvedDoc = document();
    const unresolvedRow = unresolvedDoc.activeDraft.blocks[0] as NarrationBlockV2;
    const unresolvedRoot = unresolvedRow.primaryVisualSequence!.slots[0]!;
    if (unresolvedRoot.kind !== "content") throw new Error("fixture must have a root slot");
    unresolvedRoot.payload = { kind: "visual", payloadId: id(17), pictureKind: "unresolved_visual", source: { kind: "unresolved_visual", description: "Find a safe image" }, sourceUsage: null, audioPolicy: "mute", framingPolicy: "contain" };
    const unresolvedDeps = dependencies();
    unresolvedDeps.occurrenceResolutions = [];
    unresolvedDeps.preparedMedia = [];
    unresolvedDeps.build.forcePreviewVisuals = true;
    readFrozenInput("unresolved-preview-forced", unresolvedDoc, unresolvedDeps);
    const unresolved = compileTimelineV2(unresolvedDoc, unresolvedDeps);
    expect(unresolved.ok).toBe(true);
    if (unresolved.ok) {
      const slate = unresolved.manifest.events.find((event) => event.kind === "placeholder");
      expect(slate?.pictureTreatment).toEqual({ kind: "slate", purpose: "unresolved", text: "Find a safe image" });
      const slateResult = unresolved.report.eventResults.find((result) => result.eventId === slate?.eventId);
      expect(slateResult?.disposition).toBe("blocked");
      expect(slateResult?.message).toContain("Blocked unresolved visual request");
      expect(unresolved.report.summary).toMatchObject({ blockedCount: 1, placeholderCount: 0 });
      readGolden("unresolved-preview-forced.manifest", unresolved.manifestJson);
      readGolden("unresolved-preview-forced.report", unresolved.reportJson);
    }
  });

  it("places exact editor-note markers and retains explicit blocking for unavailable supporting media", () => {
    const noteDocument = document();
    const narration = noteDocument.activeDraft.blocks[0] as NarrationBlockV2;
    noteDocument.activeDraft.supportingItems.push({
      id: id(70), version: 1, orderKey: "a1", role: "editor_note", content: "Check the opening pronunciation.",
      placement: { kind: "point", anchor: { kind: "word", anchor: { blockId: narration.id, tokenId: id(7), affinity: "before", quotedWord: "hello", anchorVersion: narration.version } } },
    });
    const noteDeps = dependencies();
    readFrozenInput("editor-note-marker", noteDocument, noteDeps);
    const noteBuild = compileTimelineV2(noteDocument, noteDeps);
    expect(noteBuild.ok).toBe(true);
    if (noteBuild.ok) {
      const marker = noteBuild.manifest.events.find((event) => event.kind === "script_marker");
      expect(marker).toMatchObject({ recordRange: { startFrame: 0, endFrame: 1 }, marker: { supportingItemId: id(70), text: "Check the opening pronunciation." } });
      expect(noteBuild.report.itemResults.find((item) => item.itemId === id(70))).toMatchObject({ disposition: "placed", recordRange: { startFrame: 0, endFrame: 1 } });
      readGolden("editor-note-marker.manifest", noteBuild.manifestJson);
      readGolden("editor-note-marker.report", noteBuild.reportJson);
    }

    const unavailableDocument = document();
    const unavailableRow = unavailableDocument.activeDraft.blocks[0] as NarrationBlockV2;
    unavailableDocument.activeDraft.supportingItems.push(
      { id: id(71), version: 1, orderKey: "a1", role: "picture", content: "Image suggestion", pictureKind: "image", source: { kind: "media_reference", mediaReferenceId: id(72) }, placement: { kind: "point", anchor: { kind: "word", anchor: { blockId: unavailableRow.id, tokenId: id(7), affinity: "before", quotedWord: "hello", anchorVersion: unavailableRow.version } } } },
      { id: id(73), version: 1, orderKey: "a2", role: "audio_cue", content: "Add a soft chime", placement: { kind: "unplaced", reason: "Needs an approved cue asset" } },
    );
    const unavailableDeps = dependencies();
    readFrozenInput("unavailable-supporting-media", unavailableDocument, unavailableDeps);
    const unavailable = compileTimelineV2(unavailableDocument, unavailableDeps);
    expect(unavailable.ok).toBe(true);
    if (unavailable.ok) {
      expect(unavailable.report.status).toBe("blocked");
      expect(unavailable.report.diagnostics.map((item) => item.code)).toContain("MIGRATION_REVIEW_REQUIRED");
      expect(unavailable.report.itemResults.find((item) => item.itemId === id(71))?.disposition).toBe("blocked");
      const cueResult = unavailable.report.itemResults.find((item) => item.itemId === id(73));
      expect(cueResult?.disposition).toBe("blocked");
      expect(cueResult?.reason).toContain("Audio-cue execution is unavailable");
      expect(unavailable.manifest.events.some((event) => event.kind === "source_audio" && event.provenance.payloadId === id(73))).toBe(false);
      readGolden("unavailable-supporting-media.manifest", unavailable.manifestJson);
      readGolden("unavailable-supporting-media.report", unavailable.reportJson);
    }
  });

  it("leaves terminal and between-block editor notes visibly unplaced", () => {
    const terminalDocument = document();
    const terminalRow = terminalDocument.activeDraft.blocks[0] as NarrationBlockV2;
    const terminalOverlayId = id(77);
    const terminalOverlayPayloadId = id(78);
    terminalRow.overlayEvents.push({
      id: terminalOverlayId, version: 1,
      payload: { kind: "visual", payloadId: terminalOverlayPayloadId, pictureKind: "clip", source: { kind: "media_reference", mediaReferenceId: id(8) }, sourceUsage: { sourceInFrame: 0 }, audioPolicy: "mute", framingPolicy: "contain" },
      timing: { kind: "timed", durationMs: 4000, start: { kind: "word", anchor: { blockId: terminalRow.id, tokenId: id(7), affinity: "before", quotedWord: "hello", anchorVersion: terminalRow.version } } },
    });
    terminalDocument.activeDraft.supportingItems.push({
      id: id(74), version: 1, orderKey: "a1", role: "editor_note", content: "This note lands after the final audio sample.",
      placement: { kind: "point", anchor: { kind: "event_edge", eventId: terminalOverlayId, edge: "end" } },
    });
    const terminalDeps = dependencies();
    const terminalMap = terminalDeps.narrationTimingMaps[0]!;
    terminalMap.precision = "audible_word_marks";
    terminalMap.timingHash = digest("terminal note timing");
    terminalMap.audio!.timingHash = terminalMap.timingHash;
    terminalMap.tokens[0].audibleEnd = { numerator: 4, denominator: 1 };
    terminalMap.tokens[0].endBasis = "evidenced_audible_end";
    const terminalDescriptor = structuredClone(terminalDeps.occurrenceResolutions[0]!);
    terminalDescriptor.owner = { kind: "overlay_event", blockId: terminalRow.id, overlayEventId: terminalOverlayId };
    terminalDescriptor.payloadId = terminalOverlayPayloadId;
    terminalDescriptor.selectedSourceRange = null;
    terminalDescriptor.preparedMediaRequirementKey = "prep:terminal-overlay";
    const terminalBinding = structuredClone(terminalDeps.preparedMedia[0]!);
    terminalBinding.requirementKey = "prep:terminal-overlay";
    terminalBinding.requestedRange = { sourceInFrame: 0, duration: { numerator: 4, denominator: 1 }, preHandle: { numerator: 0, denominator: 1 }, postHandle: { numerator: 0, denominator: 1 } };
    terminalBinding.timeMapping.sourceFrameMap = structuredClone(terminalDescriptor.sourceFrameMap);
    terminalBinding.verification.deliveredHash = digest("terminal overlay bytes");
    terminalBinding.verification.decodedFrameCount = 96;
    terminalBinding.derivation = { ...terminalBinding.derivation!, commandHash: digest("terminal overlay command"), outputHash: terminalBinding.verification.deliveredHash };
    terminalBinding.artifactLocator = "prepared/terminal-overlay.mov";
    terminalDeps.occurrenceResolutions.push(terminalDescriptor);
    terminalDeps.preparedMedia.push(terminalBinding);
    terminalDeps.tracks.push({ id: "video-overlay", kind: "video", index: 5, name: "Overlay" });
    terminalDeps.roles.overlayTrackIds = ["video-overlay"];
    readFrozenInput("editor-note-terminal", terminalDocument, terminalDeps);
    const terminal = compileTimelineV2(terminalDocument, terminalDeps);
    expect(terminal.ok).toBe(true);
    if (terminal.ok) {
      expect(terminal.manifest.timeline.durationFrames).toBe(96);
      expect(terminal.manifest.events.filter((event) => event.kind === "script_marker")).toHaveLength(0);
      const noteResult = terminal.report.itemResults.find((item) => item.itemId === id(74));
      expect(noteResult?.disposition).toBe("unplaced");
      expect(noteResult?.reason).toContain("exclusive programme end");
      readGolden("editor-note-terminal.manifest", terminal.manifestJson);
      readGolden("editor-note-terminal.report", terminal.reportJson);
    }

    const betweenDocument = document();
    const laterVisual = intentionalSlateBlock();
    laterVisual.orderKey = "a2";
    betweenDocument.activeDraft.blocks.push({ type: "section", id: id(75), orderKey: "a1", title: "Undurationed spacer", version: 1 }, laterVisual);
    betweenDocument.activeDraft.supportingItems.push({
      id: id(76), version: 1, orderKey: "a1", role: "editor_note", content: "Position is not inferable across the section.",
      placement: { kind: "point", anchor: { kind: "between_blocks", beforeBlockId: id(75), afterBlockId: laterVisual.id } },
    });
    const betweenDeps = dependencies();
    readFrozenInput("editor-note-between-unknown-duration", betweenDocument, betweenDeps);
    const between = compileTimelineV2(betweenDocument, betweenDeps);
    expect(between.ok).toBe(true);
    if (between.ok) {
      expect(between.manifest.events.filter((event) => event.kind === "script_marker")).toHaveLength(0);
      const noteResult = between.report.itemResults.find((item) => item.itemId === id(76));
      expect(noteResult?.disposition).toBe("unplaced");
      expect(noteResult?.reason).toContain("no exact timeline time");
      readGolden("editor-note-between-unknown-duration.manifest", between.manifestJson);
      readGolden("editor-note-between-unknown-duration.report", between.reportJson);
    }
  });

  it("compiles an exact selected clip range with Full source audio ending at source duration", () => {
    const block: VisualOnlyBlockV2 = {
      type: "visual_only", id: id(30), orderKey: "a0", version: 1,
      payload: { kind: "visual", payloadId: id(31), pictureKind: "clip", source: { kind: "media_reference", mediaReferenceId: id(8) }, audioPolicy: "full", framingPolicy: "contain" },
      visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 0, durationFrames: 250 } },
    };
    const doc = visualOnlyDocument(block);
    const deps = dependencies();
    deps.narrationTimingMaps = [];
    deps.document.textHash = digest("");
    deps.timeline.frameRate = { numerator: 24000, denominator: 1001 };
    const descriptor = deps.occurrenceResolutions[0]!;
    descriptor.owner = { kind: "visual_only_block", blockId: block.id };
    descriptor.payloadId = block.payload.payloadId;
    descriptor.occurrenceSourceInFrame = 0;
    descriptor.logicalSourceBounds = { startFrame: 0, endFrame: 400, frameRate: { numerator: 25, denominator: 1 } };
    descriptor.selectedSourceRange = { startFrame: 0, endFrame: 250 };
    descriptor.sourceFrameMap.packageFrameZeroLogicalFrame = 0;
    descriptor.sourceFrameMap.decodedPackageFrameRate = { numerator: 25, denominator: 1 };
    descriptor.sourceFrameMap.decodedPackageFrameCount = 400;
    descriptor.sourceFrameMap.sourceAudioStreamMappings = [{
      streamIndex: 0, sampleRate: 48000,
      packagePtsOrigin: { numerator: 0, denominator: 1 }, loggedTimeAtPackageOrigin: { numerator: 0, denominator: 1 },
      audioHash: digest("standalone audio bytes"), probeHash: descriptor.sourceSnapshot.probeHash,
    }];
    const binding = deps.preparedMedia[0]!;
    binding.requestedRange = { sourceInFrame: 0, duration: { numerator: 10, denominator: 1 }, preHandle: { numerator: 0, denominator: 1 }, postHandle: { numerator: 0, denominator: 1 } };
    binding.targetRate = { numerator: 24000, denominator: 1001 };
    binding.timeMapping.sourceOrigin = { numerator: 0, denominator: 1 };
    binding.timeMapping.sourceRate = { numerator: 25, denominator: 1 };
    binding.timeMapping.deliveredRate = { numerator: 24000, denominator: 1001 };
    binding.timeMapping.sourceFrameMap = structuredClone(descriptor.sourceFrameMap);
    binding.verification.decodedFrameCount = 240;
    binding.verification.decodedFrameRate = { numerator: 24000, denominator: 1001 };
    binding.verification.videoTimeBase = { numerator: 1001, denominator: 24000 };
    binding.verification.sourceAudio = { status: "aligned", offset: { numerator: 0, denominator: 1 }, maxDrift: { numerator: 0, denominator: 1 }, sampleRate: 48000 };
    binding.derivation = { ...binding.derivation!, commandHash: digest("standalone full audio preparation"), outputHash: binding.verification.deliveredHash };
    deps.tracks.push({ id: "source-audio", kind: "audio", index: 5, name: "Source audio" });
    deps.roles.sourceAudioTrackIds = ["source-audio"];

    readFrozenInput("selected-clip-ntsc", doc, deps);
    const needs = resolveMediaRequirementsV2(doc, { timing: [], defaults: deps.authoringDefaults, sourceDescriptors: deps.occurrenceResolutions, frameRate: deps.timeline.frameRate });
    expect(needs.ok).toBe(true);
    if (needs.ok) {
      expect(needs.durationFrames).toBe(240);
      expect(needs.requirements[0]?.requiredSourceRange).toEqual({ startFrame: 0, endFrame: 250 });
      expect(needs.requirements[0]?.requestedRange.duration).toEqual({ numerator: 10, denominator: 1 });
    }
    const compiled = compileTimelineV2(doc, deps);
    expect(compiled.ok).toBe(true);
    if (compiled.ok) {
      expect(compiled.manifest.timeline.durationFrames).toBe(240);
      expect(compiled.manifest.durationBasis).toMatchObject({ kind: "standalone_clip", sourceRange: { startFrame: 0, endFrame: 250 }, recordFrames: 240 });
      expect(compiled.manifest.events.find((event) => event.kind === "primary_visual")?.sourceRange).toEqual({ startFrame: 0, endFrame: 240 });
      const sourceAudio = compiled.manifest.events.find((event) => event.kind === "source_audio");
      expect(sourceAudio?.recordRange).toEqual({ startFrame: 0, endFrame: 240 });
      expect(sourceAudio?.audio).toMatchObject({ audioPolicy: "full", gainDb: 0, sampleRange: { startFrame: 0, endFrame: 480000 } });
      readGolden("selected-clip-ntsc.manifest", compiled.manifestJson);
      readGolden("selected-clip-ntsc.report", compiled.reportJson);
    }
  });

  it("refuses a visual-only selected range that disagrees with its bound descriptor", () => {
    const block: VisualOnlyBlockV2 = {
      type: "visual_only", id: id(30), orderKey: "a0", version: 1,
      payload: { kind: "visual", payloadId: id(31), pictureKind: "clip", source: { kind: "media_reference", mediaReferenceId: id(8) }, audioPolicy: "mute", framingPolicy: "contain" },
      visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: 1, durationFrames: 249 } },
    };
    const doc = visualOnlyDocument(block);
    const deps = dependencies();
    deps.narrationTimingMaps = [];
    deps.document.textHash = digest("");
    const descriptor = deps.occurrenceResolutions[0]!;
    descriptor.owner = { kind: "visual_only_block", blockId: block.id };
    descriptor.payloadId = block.payload.payloadId;
    descriptor.selectedSourceRange = { startFrame: 0, endFrame: 250 };
    const needs = resolveMediaRequirementsV2(doc, { timing: [], defaults: deps.authoringDefaults, sourceDescriptors: deps.occurrenceResolutions, frameRate: deps.timeline.frameRate });
    expect(needs.ok).toBe(false);
    const compiled = compileTimelineV2(doc, deps);
    expect(compiled.ok).toBe(true);
    if (compiled.ok) {
      expect(compiled.report.status).toBe("blocked");
      expect(compiled.report.diagnostics.map((item) => item.code)).toContain("MISSING_OCCURRENCE_BINDING");
      expect(compiled.manifest.events.filter((event) => event.kind === "primary_visual")).toHaveLength(0);
    }
  });

  it("classifies exact media-end cuts without inferring silence from derived word ends", () => {
    const cases = [
      { relation: "at_word_start", name: "media-end-at-word-start", words: [{ value: "alpha", start: { numerator: 0, denominator: 1 } }, { value: "beta", start: { numerator: 10, denominator: 1 } }, { value: "gamma", start: { numerator: 11, denominator: 1 } }], related: id(41) },
      { relation: "inside_word", name: "media-end-inside-word", words: [{ value: "alpha", start: { numerator: 0, denominator: 1 } }, { value: "beta", start: { numerator: 19, denominator: 2 }, audibleEnd: { numerator: 21, denominator: 2 } }, { value: "gamma", start: { numerator: 11, denominator: 1 } }], related: id(41) },
      { relation: "between_words", name: "media-end-between-words", words: [{ value: "alpha", start: { numerator: 0, denominator: 1 } }, { value: "beta", start: { numerator: 9, denominator: 1 }, audibleEnd: { numerator: 19, denominator: 2 } }, { value: "gamma", start: { numerator: 21, denominator: 2 } }], related: null },
      { relation: "derived_or_unknown", name: "media-end-unknown-word-relation", words: [{ value: "alpha", start: { numerator: 0, denominator: 1 } }, { value: "beta", start: { numerator: 19, denominator: 2 } }, { value: "gamma", start: { numerator: 11, denominator: 1 } }], related: null },
    ] as const;
    for (const item of cases) {
      const { doc, deps, tokenIds } = completeClipBoundaryFixture(item.words);
      readFrozenInput(item.name, doc, deps);
      const compiled = compileTimelineV2(doc, deps);
      expect(compiled.ok, JSON.stringify(compiled)).toBe(true);
      if (compiled.ok) {
        const boundary = compiled.manifest.boundaryEvidence.find((evidence) => evidence.kind === "media_end");
        expect(boundary).toMatchObject({
          wordRelation: item.relation,
          relatedTokenId: item.related,
          inputTime: { numerator: 10, denominator: 1 },
          resolvedRecordFrame: 240,
          delta: { numerator: 1, denominator: 100 },
        });
        expect(compiled.manifest.boundaryEvidence.filter((evidence) => evidence.kind === "word_start").map((evidence) => evidence.entityId)).toEqual(tokenIds);
        expect(compiled.manifest.timeline.durationFrames).toBe(288);
        expect(compiled.manifest.events.find((event) => event.kind === "primary_visual")?.recordRange).toEqual({ startFrame: 0, endFrame: 240 });
        readGolden(`${item.name}.manifest`, compiled.manifestJson);
        readGolden(`${item.name}.report`, compiled.reportJson);
      }
    }
  });

  it("blocks a complete-media end that reverses the next root boundary without emitting partial visuals", () => {
    const { doc, deps } = completeClipBoundaryFixture([
      { value: "alpha", start: { numerator: 0, denominator: 1 } },
      { value: "beta", start: { numerator: 2, denominator: 1 } },
      { value: "gamma", start: { numerator: 4, denominator: 1 } },
    ], 384000);
    readFrozenInput("reversed-media-end-blocked", doc, deps);
    const compiled = compileTimelineV2(doc, deps);
    expect(compiled.ok).toBe(true);
    if (compiled.ok) {
      expect(compiled.report.status).toBe("blocked");
      expect(compiled.report.diagnostics.map((item) => item.code)).toContain("COLLAPSED_BOUNDARY");
      expect(compiled.manifest.events.filter((event) => event.kind === "primary_visual" || event.kind === "overlay_visual")).toHaveLength(0);
      readGolden("reversed-media-end-blocked.manifest", compiled.manifestJson);
      readGolden("reversed-media-end-blocked.report", compiled.reportJson);
    }
  });

  it("keeps a B-roll root advancing below an On Camera child and cross-boundary overlay", () => {
    const doc = document();
    const row = doc.activeDraft.blocks[0] as NarrationBlockV2;
    const root = row.primaryVisualSequence!.slots[0]!;
    if (root.kind !== "content" || root.payload.kind !== "visual") throw new Error("fixture must have a visual root");
    const text = "alpha beta gamma";
    const wordRows = [
      { id: id(40), value: "alpha", startOffset: 0, endOffset: 5, time: { numerator: 0, denominator: 1 } },
      { id: id(41), value: "beta", startOffset: 6, endOffset: 10, time: { numerator: 1, denominator: 1 } },
      { id: id(42), value: "gamma", startOffset: 11, endOffset: 16, time: { numerator: 2, denominator: 1 } },
    ];
    row.text = text;
    const authoredTokens = wordRows.map(({ id: tokenId, value, startOffset, endOffset }) => ({ id: tokenId, value, startOffset, endOffset }));
    const [firstAuthoredToken, ...remainingAuthoredTokens] = authoredTokens;
    row.tokens = [firstAuthoredToken!, ...remainingAuthoredTokens];
    const childSlotId = id(19);
    row.primaryVisualSequence!.slots.push({
      id: childSlotId, kind: "content", relation: { kind: "cutaway", parentSlotId: root.id },
      boundaryBefore: { kind: "spoken_word", anchor: { blockId: row.id, tokenId: id(41), affinity: "before", quotedWord: "beta", anchorVersion: row.version } },
      payload: { kind: "on_camera", presenterChoiceId: null },
      playoutPolicy: "match_structural_interval", version: 1,
    });
    row.primaryVisualSequence!.slots.push({ id: id(22), kind: "return", parentSlotId: root.id, inpoint: { blockId: row.id, tokenId: id(42), affinity: "before", quotedWord: "gamma", anchorVersion: row.version }, version: 1 });
    const overlayId = id(23);
    const overlayPayloadId = id(24);
    row.overlayEvents.push({
      id: overlayId, version: 1,
      payload: { kind: "visual", payloadId: overlayPayloadId, pictureKind: "clip", source: { kind: "media_reference", mediaReferenceId: id(25) }, sourceUsage: { sourceInFrame: 60 }, audioPolicy: "mute", framingPolicy: "contain" },
      timing: { kind: "timed", durationMs: 2500, start: { kind: "word", anchor: { blockId: row.id, tokenId: id(41), affinity: "before", quotedWord: "beta", anchorVersion: row.version } } },
    });

    const deps = dependencies();
    deps.timeline.frameRate = { numerator: 24, denominator: 1 };
    deps.document.textHash = digest(text);
    deps.tracks.find((track) => track.id === "placeholder")!.index = 4;
    deps.tracks.find((track) => track.id === "presenter")!.index = 5;
    deps.tracks.find((track) => track.id === "markers")!.index = 6;
    deps.tracks.push({ id: "video-child", kind: "video", index: 2, name: "Child" }, { id: "video-overlay", kind: "video", index: 3, name: "Overlay" });
    deps.roles.childTrackIds = ["video-child"];
    deps.roles.overlayTrackIds = ["video-overlay"];
    const timing = deps.narrationTimingMaps[0]!;
    timing.textHash = digest(text);
    const timingRows = wordRows.map((word, index) => ({ tokenId: word.id, quotedText: word.value, startOffset: word.startOffset, endOffset: word.endOffset, startTime: word.time, ...(index < 2 ? { audibleEnd: { numerator: index + 1, denominator: 1 } } : {}), endBasis: index < 2 ? "evidenced_audible_end" as const : "unknown" as const }));
    const [firstTiming, ...remainingTiming] = timingRows;
    timing.tokens = [firstTiming!, ...remainingTiming];
    const rootDescriptor = deps.occurrenceResolutions[0]!;
    rootDescriptor.selectedSourceRange = null;
    const makeOccurrence = (payloadId: string, owner: { kind: "primary_slot"; sequenceId: string; slotId: string } | { kind: "overlay_event"; blockId: string; overlayEventId: string }, mediaReferenceId: string, sourceIn: number, duration: { numerator: number; denominator: number }, deliveredFrames: number, sourceOrigin: { numerator: number; denominator: number }, key: string, label: string) => {
      const descriptor = structuredClone(rootDescriptor);
      descriptor.owner = owner;
      descriptor.payloadId = payloadId;
      descriptor.mediaReferenceId = mediaReferenceId;
      descriptor.occurrenceSourceInFrame = sourceIn;
      descriptor.preparedMediaRequirementKey = key;
      descriptor.sourceFrameMap.packageFrameZeroLogicalFrame = 0;
      descriptor.sourceFrameMap.sourceAudioStreamMappings = [];
      const binding = structuredClone(deps.preparedMedia[0]!);
      binding.requirementKey = key;
      binding.originalSource.mediaReferenceId = mediaReferenceId;
      binding.requestedRange = { sourceInFrame: sourceIn, duration, preHandle: { numerator: 0, denominator: 1 }, postHandle: { numerator: 0, denominator: 1 } };
      binding.timeMapping.sourceOrigin = sourceOrigin;
      binding.timeMapping.sourceFrameMap = structuredClone(descriptor.sourceFrameMap);
      binding.verification.decodedFrameCount = deliveredFrames;
      binding.verification.deliveredHash = digest(`${label} delivered bytes`);
      binding.derivation = { ...binding.derivation!, commandHash: digest(`${label} command`), outputHash: binding.verification.deliveredHash };
      binding.artifactLocator = `prepared/${label}.mov`;
      return { descriptor, binding };
    };
    const overlay = makeOccurrence(overlayPayloadId, { kind: "overlay_event", blockId: row.id, overlayEventId: overlayId }, id(25), 60, { numerator: 5, denominator: 2 }, 60, { numerator: 2, denominator: 1 }, "prep:overlay", "overlay");
    deps.occurrenceResolutions.push(overlay.descriptor);
    deps.preparedMedia.push(overlay.binding);

    readFrozenInput("root-child-overlay-return", doc, deps);
    const compiled = compileTimelineV2(doc, deps);
    expect(compiled.ok, JSON.stringify(compiled)).toBe(true);
    if (compiled.ok) {
      const rootEvent = compiled.manifest.events.find((event) => event.kind === "primary_visual" && event.provenance.slotId === root.id)!;
      const childEvent = compiled.manifest.events.find((event) => event.kind === "placeholder" && event.provenance.slotId === childSlotId)!;
      const overlayEvent = compiled.manifest.events.find((event) => event.kind === "overlay_visual")!;
      expect(rootEvent.trackId).toBe("video-root");
      expect(rootEvent.recordRange).toEqual({ startFrame: 0, endFrame: 96 });
      expect(childEvent.trackId).toBe("video-child");
      expect(childEvent.recordRange).toEqual({ startFrame: 24, endFrame: 48 });
      expect(childEvent.pictureTreatment?.kind).toBe("still");
      expect(overlayEvent.trackId).toBe("video-overlay");
      expect(overlayEvent.recordRange).toEqual({ startFrame: 24, endFrame: 84 });
      expect(compiled.manifest.composition.returns).toEqual([{ returnSlotId: id(22), rootEventId: rootEvent.eventId, recordFrame: 48, emitsNewSourceEvent: false }]);
      expect(compiled.manifest.events.filter((event) => event.kind === "primary_visual" || event.kind === "overlay_visual")).toHaveLength(2);
      readGolden("root-child-overlay-return.manifest", compiled.manifestJson);
      readGolden("root-child-overlay-return.report", compiled.reportJson);
    }

    for (const mutate of [
      (copy: ScriptDocumentV2) => { const ret = (copy.activeDraft.blocks[0] as NarrationBlockV2).primaryVisualSequence!.slots.find((slot) => slot.kind === "return"); if (ret?.kind === "return") ret.inpoint = null; },
      (copy: ScriptDocumentV2) => { const ret = (copy.activeDraft.blocks[0] as NarrationBlockV2).primaryVisualSequence!.slots.find((slot) => slot.kind === "return"); if (ret?.kind === "return" && ret.inpoint) ret.inpoint.tokenId = id(99); },
    ]) {
      const invalidReturn = structuredClone(doc);
      mutate(invalidReturn);
      const blockedReturn = compileTimelineV2(invalidReturn, deps);
      expect(blockedReturn.ok).toBe(false);
      if (!blockedReturn.ok) expect(blockedReturn.diagnostics.map((item) => item.code)).toMatchObject([expect.stringMatching(/RETURN_INPOINT_MISSING|STALE_WORD_ANCHOR/)]);
    }
  });

  it("compiles the Python golden's repeated, punctuated, combining, and surrogate-pair token map", () => {
    const map = JSON.parse(readFileSync(fixture("issue_173/python/narration-timing-map-v2.json"), "utf8")) as CompilerDependenciesV2["narrationTimingMaps"][number];
    expect(map.tokenizationVersion).toBe("script-document/v2-frozen-tokens");
    const text = "go, can't élan 🌍 go?";
    expect(map.textHash).toBe(digest(text));
    expect(map.tokens.map((item) => text.slice(item.startOffset, item.endOffset))).toEqual(map.tokens.map((item) => item.quotedText));
    expect(map.tokens.at(-1)?.endOffset).toBe(21);

    const doc = document();
    const row = doc.activeDraft.blocks[0] as NarrationBlockV2;
    row.id = map.blockId;
    row.version = map.blockRevision;
    row.text = text;
    const [firstToken, ...remainingTokens] = map.tokens.map((item) => ({ id: item.tokenId, value: item.quotedText, startOffset: item.startOffset, endOffset: item.endOffset }));
    row.tokens = [firstToken!, ...remainingTokens];
    const deps = dependencies();
    deps.narrationTimingMaps = [map];
    deps.document.textHash = map.textHash;
    const compiled = compileTimelineV2(doc, deps);
    expect(compiled.ok).toBe(true);
    if (compiled.ok) {
      expect(compiled.manifest.events.filter((event) => event.kind === "narration")).toHaveLength(1);
      expect(compiled.manifest.boundaryEvidence.map((item) => item.entityId)).toEqual(map.tokens.map((item) => item.tokenId));
    }
  });
});
