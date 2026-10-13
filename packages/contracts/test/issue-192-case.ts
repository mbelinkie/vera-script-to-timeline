/** New sanitized synthetic specimen, never private original script/media. */
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { canonicalJson, sha256CanonicalJson } from "../src/compiler-core.js";
import { compileTimelineV2 } from "../src/compiler-core-v2.js";
import type { CompilerDependenciesV2, NarrationBlockV2, NarrationBoundaryEvidenceV1, ScriptDocumentV2, TimelineEventV2 } from "../src/generated/contracts-v2.js";
import type { InferenceEvidenceV2, ObservationPacketV2 } from "../src/issue-192-v2-proposals.js";

export const id = (n: number) => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
export const hash = (s: string) => `sha256:${createHash("sha256").update(s).digest("hex")}`;
export const rate = { numerator: 24000, denominator: 1001 };
export function rational(numerator: number, denominator: number) {
  let a = numerator; let b = denominator; while (b) [a, b] = [b, a % b];
  return { numerator: numerator / a, denominator: denominator / a };
}
function row(n: number, count: number): NarrationBlockV2 {
  let text = "";
  const tokens = Array.from({ length: count }, (_, index) => {
    if (index) text += " "; const startOffset = text.length;
    const value = `Token${index}`; text += value;
    return { id: id(n * 100 + index), value, startOffset, endOffset: text.length };
  });
  return { type: "narration", id: id(n), orderKey: String(n), version: 1, text, tokens: [tokens[0]!, ...tokens.slice(1)],
    state: "active", notes: [], overlayEvents: [], timingPolicy: "narration_spine",
    primaryVisualSequence: { id: id(n + 1), version: 1, slots: [{ id: id(n + 2), kind: "content", relation: { kind: "base" },
      boundaryBefore: { kind: "row_start" }, payload: { kind: "on_camera", presenterChoiceId: null }, playoutPolicy: "match_structural_interval", version: 1 }] } };
}
export function timing(row: NarrationBlockV2, frames: number, fresh = false): NarrationBoundaryEvidenceV1 {
  const label = `${row.id}:${fresh ? "replacement" : "baseline"}`;
  const narrationAssetId = id(fresh ? 900 : row.id === id(10) ? 800 : 801);
  const audioHash = hash(`${label}:pcm`); const timingHash = hash(`${label}:timing`);
  return { schemaVersion: "narration-boundary-evidence/v1", blockId: row.id, blockRevision: row.version,
    textHash: hash(row.text), tokenizationVersion: "script-document/v2-frozen-tokens", narrationAssetId, audioHash, timingHash,
    alignmentVersion: "synthetic-192/v1", audio: { narrationAssetId, audioHash, timingHash, cacheAssetId: (fresh ? "b" : "a").repeat(64),
      locator: `Builds/${label}.wav`, durationSamples: frames * 2002, sampleRate: 48000, channels: 1 },
    tokens: [{ tokenId: row.tokens[0].id, quotedText: row.tokens[0].value, startOffset: 0, endOffset: row.tokens[0].endOffset, onset: { numerator: 0, denominator: 1 } }],
    verification: { method: "reviewed_audio_boundaries/v1", reviewId: id(fresh ? 999 : 998), reviewRevision: 1,
      reviewerReference: "synthetic fake only", reviewArtifactLocator: `Reviews/${label}.json`, reviewArtifactHash: hash(`${label}:review`) } };
}
export function specimen() {
  const dependencies = JSON.parse(readFileSync(new URL("../../../tests/data/authoring_v2/compiler-dependencies-v2.json", import.meta.url), "utf8")) as CompilerDependenciesV2;
  const one = row(10, 21); const two = row(20, 81);
  const document: ScriptDocumentV2 = { schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "#192 sanitized fake",
    activeDraft: { blocks: [one], supportingItems: [] }, ideaOutline: [], extras: [], liveHeadSequence: 0, liveStateVector: "", liveContentHash: hash("192 baseline") };
  dependencies.timeline.frameRate = rate; dependencies.narrationTimingMaps = [];
  dependencies.narrationBoundaryEvidence = [timing(one, 200), timing(two, 641)];
  dependencies.document.contentHash = document.liveContentHash; dependencies.document.textHash = hash(`${one.text}\n${two.text}`);
  dependencies.tracks.push({ id: "presenter", kind: "video", index: 2, name: "Presenter" }, { id: "placeholder", kind: "video", index: 3, name: "Placeholder" },
    { id: "markers", kind: "video", index: 4, name: "Markers" }, { id: "source", kind: "audio", index: 2, name: "Source" });
  dependencies.roles.sourceAudioTrackIds = ["source"];
  const occurrence = structuredClone(dependencies.occurrenceResolutions[0]!); const preparation = structuredClone(dependencies.preparedMedia[0]!);
  dependencies.occurrenceResolutions = []; dependencies.preparedMedia = [];
  function visual(n: number, owner: typeof occurrence.owner, start: number, frames: number, image = false) {
    const d = structuredClone(occurrence); const b = structuredClone(preparation);
    d.payloadId = id(n); d.owner = owner; d.mediaReferenceId = id(n + 500); d.occurrenceSourceInFrame = start;
    d.sourceSnapshot.contentHash = hash(`192 media${n}`); d.sourceSnapshot.probeHash = hash(`192 probe${n}`);
    d.selectedSourceRange = owner.kind === "visual_only_block" ? { startFrame: start, endFrame: start + frames } : null;
    d.logicalSourceBounds = { startFrame: 0, endFrame: image ? 1 : 5000, frameRate: rate };
    d.sourceFrameMap = { ...d.sourceFrameMap, decodedPackageFrameRate: rate, decodedPackageFrameCount: image ? 1 : 5000,
      packageVideoTimeBase: { numerator: 1001, denominator: 24000 }, probeHash: d.sourceSnapshot.probeHash,
      sourceAudioStreamMappings: image ? [] : [{ streamIndex: 0, sampleRate: 48000, packagePtsOrigin: { numerator: 0, denominator: 1 },
        loggedTimeAtPackageOrigin: { numerator: 0, denominator: 1 }, audioHash: hash(`192 pcm${n}`), probeHash: d.sourceSnapshot.probeHash }] };
    d.preparedMediaRequirementKey = `192:prep:${n}`; b.requirementKey = d.preparedMediaRequirementKey;
    b.originalSource = { mediaReferenceId: d.mediaReferenceId, contentHash: d.sourceSnapshot.contentHash, probeHash: d.sourceSnapshot.probeHash }; b.targetRate = rate;
    b.requestedRange = { sourceInFrame: start, duration: rational(frames * 1001, 24000), preHandle: { numerator: 0, denominator: 1 }, postHandle: { numerator: 0, denominator: 1 } };
    b.timeMapping = { ...b.timeMapping, sourceOrigin: { numerator: 0, denominator: 1 }, sourceRate: rate, deliveredRate: rate, sourceFrameMap: structuredClone(d.sourceFrameMap) };
    b.verification = { ...b.verification, deliveredHash: d.sourceSnapshot.contentHash, probeHash: d.sourceSnapshot.probeHash,
      decodedFrameCount: image ? 1 : 5000, decodedFrameRate: rate, videoTimeBase: { numerator: 1001, denominator: 24000 },
      sourceAudio: image ? b.verification.sourceAudio : { status: "aligned", offset: { numerator: 0, denominator: 1 }, maxDrift: { numerator: 0, denominator: 1 }, sampleRate: 48000 } };
    b.artifactLocator = `prepared/192-${n}.mov`; dependencies.occurrenceResolutions.push(d); dependencies.preparedMedia.push(b);
    return { kind: "visual" as const, payloadId: d.payloadId, pictureKind: image ? "image" as const : "clip" as const,
      source: { kind: "media_reference" as const, mediaReferenceId: d.mediaReferenceId }, audioPolicy: image ? "mute" as const : "full" as const, framingPolicy: "contain" as const };
  }
  const base = one.primaryVisualSequence!.slots[0]!;
  if (base.kind !== "content") throw new Error("base");
  base.payload = { ...visual(30, { kind: "primary_slot", sequenceId: one.primaryVisualSequence!.id, slotId: base.id }, 0, 200), sourceUsage: { sourceInFrame: 0 }, audioPolicy: "quiet" };
  const anchor = (n: number, affinity: "before" | "after") => ({ blockId: two.id, tokenId: two.tokens[n]!.id, quotedWord: two.tokens[n]!.value, anchorVersion: 1, affinity });
  two.primaryVisualSequence!.slots.push({ id: id(23), kind: "content", relation: { kind: "sequential" }, version: 1,
    boundaryBefore: { kind: "spoken_word", anchor: { ...anchor(20, "before"), affinity: "before" } }, playoutPolicy: "match_structural_interval",
    payload: { ...visual(31, { kind: "primary_slot", sequenceId: two.primaryVisualSequence!.id, slotId: id(23) }, 0, 1, true), sourceUsage: null, audioPolicy: "mute" } },
    { id: id(24), kind: "content", relation: { kind: "sequential" }, version: 1, boundaryBefore: { kind: "audible_word_end", anchor: { ...anchor(34, "after"), affinity: "after" } },
      playoutPolicy: "match_structural_interval", payload: { kind: "on_camera", presenterChoiceId: null } });
  for (const [n, onset, end] of [[20, 145, null], [34, 258, 281]] as const) dependencies.narrationBoundaryEvidence[1]!.tokens.push({ tokenId: two.tokens[n]!.id,
    quotedText: two.tokens[n]!.value, startOffset: two.tokens[n]!.startOffset, endOffset: two.tokens[n]!.endOffset, onset: rational(onset * 1001, 24000), ...(end === null ? {} : { audibleEnd: rational(end * 1001, 24000) }) });
  for (const [n, start, duration] of [[40, 0, 111], [50, 2664, 92], [60, 396, 63]] as const) {
    document.activeDraft.blocks.push({ type: "visual_only", id: id(n), orderKey: String(n), version: 1,
      payload: visual(n + 1, { kind: "visual_only_block", blockId: id(n) }, start, duration),
      visualOnlyTiming: { kind: "visual_only", selectedSourceRange: { startFrame: start, durationFrames: duration } } });
    if (n === 40) document.activeDraft.blocks.push(two);
  }
  document.activeDraft.blocks.push({ type: "note_draft", id: id(70), orderKey: "last", version: 1, text: "Retained parked note", state: "excluded" });
  return { document, dependencies };
}
export function patches(input: ReturnType<typeof specimen>, d1 = 200) {
  return [30, 51].map((n) => {
    const binding = structuredClone(input.dependencies.preparedMedia.find((p) => p.requirementKey === `192:prep:${n}`)!);
    binding.requestedRange.duration = rational((n === 30 ? d1 : 67) * 1001, 24000); return binding;
  });
}

export interface FakeItem {
  itemUid: string; mediaUid: string; eventId: string; sourceId: string; kind: "video" | "audio";
  trackIndex: number; recordStart: number; recordEnd: number; rawRecordEnd: number; sourceStart: number; sourceEnd: number;
  sourceRangeRate: typeof rate; authoredEvent: TimelineEventV2; sourceHash: string; sourcePath: string;
  enabled: boolean; online: boolean; speed: { numerator: number; denominator: number };
  rawSpeedOptions: { Percentage: number; PitchCorrection: boolean; StretchKeyframesToFit: boolean; RippleTimeline: boolean }; linkedUids: string[];
}
export interface FakeRaw {
  schemaVersion: string; target: { projectUid: string; timelineUid: string }; deliveryLineage: unknown; nativeIdentity: unknown;
  timeline: { width: number; height: number; audioSampleRate: number; startFrame: number; durationFrames: number; frameRate: typeof rate };
  tracks: { kind: string; index: number; name: string; enabled: boolean; locked: boolean }[];
  items: FakeItem[]; controls: { programControls: unknown; routes: { itemUid: string; sourceId: string; controls: Record<string, unknown> }[] }; markers: unknown;
}
export function observations(input: ReturnType<typeof specimen>) {
  const c = compileTimelineV2(input.document, input.dependencies); if (!c.ok || c.report.status !== "ready") throw new Error(canonicalJson(c));
  const items: FakeItem[] = c.manifest.events.filter((e) => e.kind !== "script_marker").map((e) => {
    const track = c.manifest.tracks.find((t) => t.id === e.trackId)!;
    const duration = e.recordRange.endFrame - e.recordRange.startFrame;
    const sourceStart = e.kind === "source_audio" ? e.audio!.sampleRange.startFrame / 2002 : e.sourceRange?.startFrame ?? 0;
    return { itemUid: `fake-item:${e.eventId}`, mediaUid: `fake-media:${e.provenance.sourceId ?? e.eventId}`, eventId: e.eventId,
      sourceId: e.provenance.sourceId ?? `slate:${e.eventId}`, kind: track.kind as "video" | "audio", trackIndex: track.index,
      recordStart: e.recordRange.startFrame, recordEnd: e.recordRange.endFrame, rawRecordEnd: e.recordRange.endFrame - 1,
      sourceStart, sourceEnd: sourceStart + duration, sourceRangeRate: rate, authoredEvent: e,
      sourceHash: hash(`fake bytes:${e.provenance.sourceId ?? e.eventId}`), sourcePath: `/synthetic-192/${e.eventId}.media`,
      enabled: true, online: true, speed: { numerator: 1, denominator: 1 }, rawSpeedOptions: { Percentage: 100, PitchCorrection: false, StretchKeyframesToFit: false, RippleTimeline: false }, linkedUids: [] };
  });
  for (const i of items.filter((i) => [id(40), id(50), id(60)].includes(i.authoredEvent.provenance.blockId ?? "")))
    i.linkedUids = items.filter((p) => p.itemUid !== i.itemUid && p.authoredEvent.provenance.blockId === i.authoredEvent.provenance.blockId).map((p) => p.itemUid);
  const raw: FakeRaw = { schemaVersion: "issue-189-v2-native-readback/v1", target: { projectUid: "fake-project", timelineUid: "fake-edited-timeline" },
    deliveryLineage: { kind: "externally_supplied_target", target: { projectUid: "fake-project", timelineUid: "fake-edited-timeline" } }, nativeIdentity: { product: "DaVinci Resolve Studio", version: [21, 1, 1, 10, ""] },
    timeline: c.manifest.timeline, tracks: c.manifest.tracks.map((t) => ({ kind: t.kind, index: t.index, name: t.name, enabled: true, locked: false })), items,
    controls: { programControls: { gainDb: 0, effects: [], limiter: false, automation: [], destination: "stereo-program" }, routes: [] }, markers: {} };
  return raw;
}
const routeControls = (i: FakeItem) => ({ enabled: true, mute: false, solo: false, gainDb: i.authoredEvent.audio?.gainDb ?? 0,
  pan: 0, effects: [], sends: [], automation: [], destination: "stereo-program", channelMap: "mono-dual" });
export function packet(rawInput: FakeRaw, bindingJson: string): ObservationPacketV2 {
  const raw = structuredClone(rawInput);
  raw.items.sort((a, b) => a.itemUid.localeCompare(b.itemUid));
  raw.controls.routes = raw.items.filter((i) => i.kind === "audio").map((i) => ({ itemUid: i.itemUid, sourceId: i.sourceId, controls: routeControls(i) }));
  const sources = [...new Set(raw.items.filter((i) => i.kind === "audio").map((i) => i.sourceId))].sort();
  const audio = { schemaVersion: "issue-189-v2-audio-observation/v1", target: raw.target, extentFrames: raw.timeline.durationFrames,
    frameRate: rate, programControls: raw.controls.programControls, routes: sources.map((sourceId) => {
      const items = raw.items.filter((i) => i.kind === "audio" && i.sourceId === sourceId).sort((a, b) => a.recordStart - b.recordStart);
      return { id: `native-route:${sourceId}`, sourceId, controls: routeControls(items[0]!), segments: items.map((i) => ({ uid: i.itemUid,
        recordStart: i.recordStart, recordEnd: i.recordEnd, sourceStart: i.sourceStart, sourceEnd: i.sourceEnd, speed: i.speed, enabled: i.enabled, online: i.online })) };
    }) };
  const rawJson = canonicalJson(raw); const audioJson = canonicalJson(audio);
  const receiptJson = canonicalJson({ schemaVersion: "issue-189-v2-observation-receipt/v1", bindingHash: hash(bindingJson), rawHash: hash(rawJson),
    derivedAudioHash: hash(audioJson), mappingHash: sha256CanonicalJson(Object.fromEntries(raw.items.map((i) => [i.itemUid, { eventId: i.eventId, sourceId: i.sourceId }]))),
    target: raw.target, deliveryLineage: raw.deliveryLineage, adjacentConsistent: true, evidenceLevel: "injected_execution_unqualified" });
  return { rawJson, audioJson, receiptJson };
}
export function edits(raw: FakeRaw, cases = "AB") {
  const result = structuredClone(raw);
  for (const item of result.items) {
    if (cases.includes("A") && item.kind === "video") {
      if (item.recordStart === 311 && item.recordEnd === 456) { item.recordEnd += 113; item.sourceEnd += 113; }
      else if (item.recordStart === 456 && item.recordEnd === 592) { item.recordStart += 113; item.sourceEnd -= 113; }
    }
    if (cases.includes("B")) {
      if (item.recordStart === 952) { item.recordEnd -= 25; item.sourceEnd -= 25; }
      else if (item.recordStart === 1044) { item.recordStart -= 25; item.recordEnd -= 25; }
    }
    item.rawRecordEnd = item.recordEnd - 1;
  }
  if (cases.includes("B")) result.timeline.durationFrames = 1082;
  if (cases.includes("C")) {
    const index = result.items.findIndex((i) => i.authoredEvent.kind === "narration" && i.recordStart === 0);
    const original = result.items[index]!; const left = structuredClone(original); const right = structuredClone(original);
    left.recordEnd = 121; left.sourceEnd = left.sourceStart + 121; left.rawRecordEnd = 120;
    right.itemUid += ":split"; right.recordStart = 127; right.sourceStart += 127;
    result.items.splice(index, 1, left, right);
  }
  return result;
}
export function evidence(input: ReturnType<typeof specimen>, before: FakeRaw, after: FakeRaw, c = false): InferenceEvidenceV2 {
  const bindingJson = canonicalJson({ schemaVersion: "issue-189-v2-native-binding/v1", attestationHash: hash("fake package"), proofPackageHash: hash("fake proof"),
    sourceHashes: {}, evidenceRoot: "/synthetic-192/evidence", projectName: "fake-project", timelineName: "fake-timeline", authorityHash: hash("fake authority") });
  const baseline = packet(before, bindingJson); const current = packet(after, bindingJson);
  return { schemaVersion: "issue-192-v2-inference-evidence/v1", documentHash: sha256CanonicalJson(input.document), dependenciesHash: sha256CanonicalJson(input.dependencies),
    bindingJson, baseline, current, omission: c ? { schemaVersion: "issue-189-v2-omission-evidence/v1", status: "verified", evidenceLevel: "local_consistency_only",
      documentHash: sha256CanonicalJson(input.document), baselineHash: hash(baseline.audioJson), currentHash: hash(current.audioJson), profileHash: hash("fake191profile"), blockId: id(10), channels: [], limitations: ["Synthetic fake only"],
      blockRevision: 1, tokenIds: [id(1011)], sourceIntervalSamples: { start: 121 * 2002, end: 127 * 2002 }, recordIntervalFrames: { start: 121, end: 127 }, inputHashes: {} } : null };
}
