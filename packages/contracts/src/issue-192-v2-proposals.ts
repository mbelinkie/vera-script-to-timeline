/** Bounded #189 inference. Receipt authentication is an executable host port. */
import { createHash } from "node:crypto";
import { canonicalJson, sha256CanonicalJson } from "./compiler-core.js";
import { compileTimelineV2 } from "./compiler-core-v2.js";
import { applyVisualSequenceEditV2 } from "./authoring-v2-edits.js";
import type { CompilerDependenciesV2, ScriptDocumentV2, TimelineEventV2 } from "./generated/contracts-v2.js";
import { prepareRevisionInputsV2, createRevisionProposalV2, decideRevisionV2, type RevisionCommandsV2, type RevisionRequestV2, type RevisionDecisionV2 } from "./issue-192-v2-revision-core.js";

type ObjectRecord = Record<string, unknown>;
export interface ObservationPacketV2 {
  rawJson: string; audioJson: string; receiptJson: string;
}
export interface InferenceEvidenceV2 {
  schemaVersion: "issue-192-v2-inference-evidence/v1";
  documentHash: string; dependenciesHash: string;
  bindingJson: string; baseline: ObservationPacketV2; current: ObservationPacketV2;
  omission: ObjectRecord | null;
}
export type InferenceAuthenticatorV2 = (context: {
  document: ScriptDocumentV2; dependencies: CompilerDependenciesV2; evidence: InferenceEvidenceV2;
}) => void;
export type CompositionEvidenceV2 = InferenceEvidenceV2 | InferenceEvidenceV2[];
const equal = (a: unknown, b: unknown) => canonicalJson(a) === canonicalJson(b);
const digest = (s: string) => `sha256:${createHash("sha256").update(s).digest("hex")}`;
function fact(value: unknown, reason: string): asserts value { if (!value) throw new Error(reason); }
function object(value: unknown): ObjectRecord {
  fact(value !== null && typeof value === "object" && !Array.isArray(value), "object record required");
  return value as ObjectRecord;
}
function shape(value: unknown, keys: string): ObjectRecord {
  const v = object(value); fact(equal(Object.keys(v).sort(), keys.split(" ").sort()), "unsupported record fields"); return v;
}
function list(value: unknown): unknown[] { fact(Array.isArray(value), "complete inventory required"); return value; }
function integer(value: unknown): number { fact(Number.isSafeInteger(value) && Number(value) >= 0, "exact nonnegative frame required"); return Number(value); }
function text(value: unknown): string { fact(typeof value === "string" && value.length > 0, "identity required"); return value; }
function parse(raw: string): ObjectRecord {
  fact(typeof raw === "string" && Buffer.byteLength(raw) <= 8 * 1024 * 1024, "bounded raw record required");
  const v = object(JSON.parse(raw));
  // Preserve #190's Python numeric spelling (e.g. 100.0); hashes bind raw bytes.
  const stack: { object: boolean; key: boolean; seen: Set<string> }[] = [];
  for (const match of raw.matchAll(/"(?:[^"\\]|\\.)*"|[{}\[\]:,]|[^\s{}\[\]:,]+/gu)) {
    const token = match[0]; const frame = stack.at(-1);
    if (token === "{" || token === "[") { fact(stack.length < 128, "bounded nesting required"); stack.push({ object: token === "{", key: token === "{", seen: new Set() }); }
    else if (token === "}" || token === "]") stack.pop();
    else if (token === "," && frame?.object) frame.key = true;
    else if (token === ":" && frame) frame.key = false;
    else if (token.startsWith('"') && frame?.object && frame.key) {
      const key = text(JSON.parse(token)); fact(!frame.seen.has(key), "duplicate raw key"); frame.seen.add(key); frame.key = false;
    } else if (!token.startsWith('"') && token !== ":" && token !== "," && !["null", "true", "false"].includes(token)) {
      const number = Number(token); fact(Number.isFinite(number) && (!Number.isInteger(number) || Number.isSafeInteger(number)), "unsafe raw number");
    }
  }
  return v;
}
interface Item {
  itemUid: string; mediaUid: string; eventId: string; sourceId: string;
  kind: string; trackIndex: number; recordStart: number; recordEnd: number;
  rawRecordEnd: number; sourceStart: number; sourceEnd: number;
  sourceRangeRate: unknown; authoredEvent: TimelineEventV2; sourceHash: string;
  sourcePath: string; enabled: true; online: true; speed: unknown;
  rawSpeedOptions: unknown; linkedUids: string[];
}
function item(value: unknown): Item {
  const v = shape(value, "itemUid mediaUid eventId sourceId kind trackIndex recordStart recordEnd rawRecordEnd sourceStart sourceEnd sourceRangeRate authoredEvent sourceHash sourcePath enabled online speed rawSpeedOptions linkedUids");
  for (const k of ["itemUid", "mediaUid", "eventId", "sourceId", "sourceHash", "sourcePath"]) text(v[k]);
  for (const k of ["trackIndex", "recordStart", "recordEnd", "rawRecordEnd", "sourceStart", "sourceEnd"]) integer(v[k]);
  fact(integer(v.recordEnd) > integer(v.recordStart) && integer(v.sourceEnd) > integer(v.sourceStart) && integer(v.trackIndex) > 0, "empty geometry");
  fact([integer(v.recordEnd), integer(v.recordEnd) - 1].includes(integer(v.rawRecordEnd)), "endpoint convention differs");
  const speed = shape(v.rawSpeedOptions, "Percentage PitchCorrection StretchKeyframesToFit RippleTimeline");
  fact(v.enabled === true && v.online === true && equal(v.speed, { numerator: 1, denominator: 1 }) &&
    speed.Percentage === 100 && typeof speed.PitchCorrection === "boolean" && speed.StretchKeyframesToFit === false && speed.RippleTimeline === false, "unsafe native controls/speed");
  fact(v.kind === "video" || v.kind === "audio", "unsupported item kind");
  const links = list(v.linkedUids).map(text); fact(new Set(links).size === links.length && !links.includes(text(v.itemUid)), "duplicate/self links");
  return v as unknown as Item;
}
function controls(raw: ObjectRecord, items: Item[]) {
  const c = shape(raw.controls, "programControls routes");
  fact(equal(c.programControls, { gainDb: 0, effects: [], limiter: false, automation: [], destination: "stereo-program" }), "unsupported programme controls");
  const seen = new Set<string>();
  const routes = list(c.routes).map((value) => {
    const r = shape(value, "itemUid sourceId controls");
    const i = items.find((entry) => entry.itemUid === r.itemUid && entry.kind === "audio");
    fact(i && !seen.has(i.itemUid) && i.sourceId === r.sourceId, "unknown/duplicate route owner"); seen.add(i.itemUid);
    const v = shape(r.controls, "enabled mute solo gainDb pan effects sends automation destination channelMap");
    fact(v.enabled === true && v.mute === false && v.solo === false && (v.gainDb === 0 || v.gainDb === -18) && v.pan === 0 &&
      equal(v.effects, []) && equal(v.sends, []) && equal(v.automation, []) && v.destination === "stereo-program" &&
      (v.channelMap === "mono-dual" || v.channelMap === "stereo-direct"), "unsupported route controls");
    fact((i.authoredEvent.kind === "narration" ? 0 : i.authoredEvent.audio?.gainDb) === v.gainDb, "route gain differs from compiler");
    return { sourceId: i.sourceId, controls: v };
  });
  fact(seen.size === items.filter((i) => i.kind === "audio").length, "missing route controls");
  const unique = new Map(routes.map((r) => [r.sourceId, r]));
  fact(routes.every((r) => equal(r, unique.get(r.sourceId))), "split source controls differ");
  return [...unique.values()].sort((a, b) => a.sourceId.localeCompare(b.sourceId));
}
function observation(packet: ObservationPacketV2, bindingHash: string, events: TimelineEventV2[]) {
  shape(packet, "rawJson audioJson receiptJson");
  const raw = parse(packet.rawJson); const audio = parse(packet.audioJson); const receipt = parse(packet.receiptJson);
  shape(raw, "schemaVersion target deliveryLineage nativeIdentity timeline tracks items controls markers");
  shape(receipt, "schemaVersion bindingHash rawHash derivedAudioHash mappingHash target deliveryLineage adjacentConsistent evidenceLevel");
  fact(raw.schemaVersion === "issue-189-v2-native-readback/v1" && receipt.schemaVersion === "issue-189-v2-observation-receipt/v1" &&
    receipt.bindingHash === bindingHash && receipt.rawHash === digest(packet.rawJson) && receipt.derivedAudioHash === digest(packet.audioJson) &&
    receipt.adjacentConsistent === true && receipt.evidenceLevel === "injected_execution_unqualified" &&
    equal(receipt.target, raw.target) && equal(receipt.deliveryLineage, raw.deliveryLineage), "unbound observation receipt");
  const target = shape(raw.target, "projectUid timelineUid"); text(target.projectUid); text(target.timelineUid);
  const timeline = shape(raw.timeline, "width height audioSampleRate startFrame durationFrames frameRate");
  fact(equal(timeline.frameRate, { numerator: 24000, denominator: 1001 }) && timeline.startFrame === 0 && timeline.audioSampleRate === 48000, "bounded rate/profile required");
  integer(timeline.durationFrames);
  const items = list(raw.items).map(item); const byUid = new Map(items.map((i) => [i.itemUid, i]));
  fact(byUid.size === items.length, "duplicate item identity");
  const mapping = Object.fromEntries(items.map((i) => [i.itemUid, { eventId: i.eventId, sourceId: i.sourceId }]));
  fact(receipt.mappingHash === sha256CanonicalJson(mapping), "item mapping hash differs");
  for (const i of items) {
    const event = events.find((e) => e.eventId === i.eventId);
    fact(event && equal(i.authoredEvent, event) && equal(i.sourceRangeRate, timeline.frameRate), "wrong/stale authored event owner");
    fact(i.recordEnd <= integer(timeline.durationFrames), "item outside programme");
    fact(i.linkedUids.every((uid) => byUid.get(uid)?.linkedUids.includes(i.itemUid)), "nonreciprocal links");
  }
  fact(new Set(items.map((i) => i.eventId)).size === events.filter((e) => e.kind !== "script_marker").length, "incomplete event inventory");
  const tracks = list(raw.tracks).map((v) => shape(v, "kind index name enabled locked"));
  fact(tracks.every((t) => t.enabled === true && typeof t.locked === "boolean" && (t.kind === "audio" || t.kind === "video") && integer(t.index) > 0), "unknown/disabled tracks");
  fact(new Set(tracks.map((t) => `${t.kind}:${t.index}`)).size === tracks.length && items.every((i) => tracks.some((t) => t.kind === i.kind && t.index === i.trackIndex)), "track inventory differs");
  shape(audio, "schemaVersion target extentFrames frameRate programControls routes");
  fact(audio.schemaVersion === "issue-189-v2-audio-observation/v1" && equal(audio.target, raw.target) &&
    equal(audio.frameRate, timeline.frameRate) && audio.extentFrames === timeline.durationFrames &&
    equal(audio.programControls, object(raw.controls).programControls), "derived programme binding differs");
  const seenAudio = new Set<string>(); const seenSources = new Set<string>();
  for (const value of list(audio.routes)) {
    const route = shape(value, "id sourceId controls segments"); text(route.id);
    const sourceId = text(route.sourceId); fact(!seenSources.has(sourceId), "duplicate derived source"); seenSources.add(sourceId);
    for (const segmentValue of list(route.segments)) {
      const segment = shape(segmentValue, "uid recordStart recordEnd sourceStart sourceEnd speed enabled online");
      const i = items.find((entry) => entry.itemUid === segment.uid && entry.kind === "audio");
      fact(i && i.sourceId === sourceId && !seenAudio.has(i.itemUid), "derived segment owner differs"); seenAudio.add(i.itemUid);
      fact(equal(segment, { uid: i.itemUid, recordStart: i.recordStart, recordEnd: i.recordEnd,
        sourceStart: i.sourceStart, sourceEnd: i.sourceEnd, speed: i.speed, enabled: i.enabled, online: i.online }), "derived audio geometry differs");
      const nativeRoute = list(object(raw.controls).routes).map(object).find((r) => r.itemUid === i.itemUid);
      fact(nativeRoute && equal(nativeRoute.controls, route.controls), "derived audio controls differ");
    }
  }
  fact(seenAudio.size === items.filter((i) => i.kind === "audio").length, "incomplete derived audio");
  return { raw, audio, receipt, items, controls: controls(raw, items) };
}
function stable(i: Item) {
  return Object.fromEntries(Object.entries(i).filter(([key]) => !["recordStart", "recordEnd", "rawRecordEnd", "sourceStart", "sourceEnd"].includes(key)));
}
function geometry(i: Item) { return [i.recordStart, i.recordEnd, i.sourceStart, i.sourceEnd]; }
function hold(i: Item) { return i.authoredEvent.kind === "placeholder" || i.authoredEvent.pictureTreatment?.kind === "still_frame"; }

/** No caller-authored command is accepted as inference. Only exact finite A/B/C. */
export function proposeV2Edits(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2, evidence: InferenceEvidenceV2, authenticate: InferenceAuthenticatorV2) {
  shape(evidence, "schemaVersion documentHash dependenciesHash bindingJson baseline current omission");
  fact(evidence.schemaVersion === "issue-192-v2-inference-evidence/v1" && evidence.documentHash === sha256CanonicalJson(document) &&
    evidence.dependenciesHash === sha256CanonicalJson(dependencies) && typeof authenticate === "function", "stale/untrusted inference inputs");
  const compiled = compileTimelineV2(document, dependencies);
  fact(compiled.ok && compiled.report.status === "ready" && compiled.manifest.timeline.durationFrames === 1107, "ready R16-shaped baseline required");
  const binding = parse(evidence.bindingJson);
  shape(binding, "schemaVersion attestationHash proofPackageHash sourceHashes evidenceRoot projectName timelineName authorityHash");
  fact(binding.schemaVersion === "issue-189-v2-native-binding/v1", "unsupported native binding");
  const before = observation(evidence.baseline, digest(evidence.bindingJson), compiled.manifest.events);
  const after = observation(evidence.current, digest(evidence.bindingJson), compiled.manifest.events);
  // Authenticate the complete bytes, package/source/currentness and edit ancestry, not a copied marker.
  authenticate(structuredClone({ document, dependencies, evidence }));
  fact(equal(before.raw.target, after.raw.target) && equal(before.raw.deliveryLineage, after.raw.deliveryLineage) &&
    equal(before.raw.nativeIdentity, after.raw.nativeIdentity) && equal(before.raw.tracks, after.raw.tracks) &&
    equal(before.raw.markers, after.raw.markers) && equal(before.controls, after.controls), "unexplained identity/control delta");
  fact(equal({ ...object(before.raw.timeline), durationFrames: 0 }, { ...object(after.raw.timeline), durationFrames: 0 }) &&
    equal(before.raw.timeline, compiled.manifest.timeline), "baseline/settings differ");
  fact(before.items.length === compiled.manifest.events.filter((e) => e.kind !== "script_marker").length, "ambiguous baseline occurrence");
  for (const i of before.items) fact(equal({ startFrame: i.recordStart, endFrame: i.recordEnd }, i.authoredEvent.recordRange), "baseline record differs from compiler");
  const commands: RevisionCommandsV2 = { boundary: null, trim: null, omission: null };
  const expected = structuredClone(before.items);
  const changedVideo = before.items.filter((i) => i.kind === "video" && !equal(geometry(i), geometry(after.items.find((a) => a.itemUid === i.itemUid) ?? i)));
  const aRight = changedVideo.filter((i) => i.recordStart === 456 && i.recordEnd === 592 && i.authoredEvent.provenance.slotId !== null);
  if (aRight.length) {
    fact(aRight.length === 1, "ambiguous A occurrence"); const right = aRight[0]!;
    const left = before.items.filter((i) => i.kind === "video" && i.recordStart === 311 && i.recordEnd === 456 &&
      i.authoredEvent.provenance.blockId === right.authoredEvent.provenance.blockId);
    fact(left.length === 1 && hold(left[0]!) && hold(right), "A picture hold pair required");
    const row = document.activeDraft.blocks.find((b) => b.id === right.authoredEvent.provenance.blockId);
    fact(row?.type === "narration" && row.primaryVisualSequence, "A narration sequence owner required");
    const owner = row.primaryVisualSequence.slots.find((s) => s.id === right.authoredEvent.provenance.slotId);
    fact(owner?.kind === "content" && owner.payload.kind === "visual" && owner.payload.pictureKind === "image", "A image owner required");
    const matches: NonNullable<RevisionCommandsV2["boundary"]>[] = [];
    for (const token of row.tokens) {
      const edit = { kind: "move_word_boundary" as const, blockId: row.id, boundaryOwnerId: owner.id, tokenId: token.id, affinity: "before" as const };
      const applied = applyVisualSequenceEditV2(document, row.primaryVisualSequence.version, edit);
      if (!applied.ok) continue;
      const preview = compileTimelineV2(applied.document, { ...dependencies, document: { ...dependencies.document,
        liveHeadSequence: applied.document.liveHeadSequence, contentHash: applied.document.liveContentHash } });
      if (preview.ok && preview.report.status === "ready" && preview.manifest.events.some((e) => e.eventId === right.eventId && e.recordRange.startFrame === 569 && e.recordRange.endFrame === 592))
        matches.push({ ...edit, expectedSequenceVersion: row.primaryVisualSequence.version });
    }
    fact(matches.length === 1 && row.tokens[34]?.id === matches[0]!.tokenId, "A reviewed token/affinity is ambiguous or differs");
    commands.boundary = matches[0]!;
    const expectedLeft = expected.find((i) => i.itemUid === left[0]!.itemUid)!;
    expectedLeft.recordEnd = 569; expectedLeft.sourceEnd += 113;
    const expectedRight = expected.find((i) => i.itemUid === right.itemUid)!;
    expectedRight.recordStart = 569; expectedRight.sourceEnd -= 113;
  }
  const bVideo = changedVideo.filter((i) => i.recordStart === 952 && i.recordEnd === 1044);
  if (bVideo.length) {
    fact(bVideo.length === 1, "ambiguous B occurrence"); const b = bVideo[0]!;
    const block = document.activeDraft.blocks.find((entry) => entry.id === b.authoredEvent.provenance.blockId);
    fact(block?.type === "visual_only" && equal(block.visualOnlyTiming.selectedSourceRange, { startFrame: 2664, durationFrames: 92 }), "B selected logical range differs");
    const descriptor = dependencies.occurrenceResolutions.filter((d) => d.payloadId === block.payload.payloadId);
    fact(descriptor.length === 1 && equal(descriptor[0]!.owner, { kind: "visual_only_block", blockId: block.id }) &&
      equal(descriptor[0]!.logicalSourceBounds.frameRate, { numerator: 24000, denominator: 1001 }) &&
      descriptor[0]!.logicalSourceBounds.endFrame >= 2756, "B exact logical-rate ownership/handles required");
    const pair = before.items.filter((i) => i.authoredEvent.provenance.blockId === block.id);
    const final = before.items.filter((i) => i.recordStart === 1044 && i.recordEnd === 1107);
    function linkedAv(items: Item[]) {
      fact(items.length === 2 && items.some((i) => i.kind === "video") && items.some((i) => i.kind === "audio") &&
        items.every((i) => equal(i.linkedUids, [items.find((p) => p.itemUid !== i.itemUid)!.itemUid])), "exact reciprocal AV pair required");
    }
    linkedAv(pair); linkedAv(final);
    fact(pair.every((i) => i.recordStart === 952 && i.recordEnd === 1044) &&
      final.every((i) => i.authoredEvent.provenance.blockId === final[0]!.authoredEvent.provenance.blockId), "B/final owner differs");
    commands.trim = { blockId: block.id, expectedBlockVersion: block.version, expectedSelectedRange: { startFrame: 2664, durationFrames: 92 }, durationFrames: 67 };
    for (const i of expected) {
      if (pair.some((p) => p.itemUid === i.itemUid)) { i.recordEnd -= 25; i.sourceEnd -= 25; }
      if (final.some((p) => p.itemUid === i.itemUid)) { i.recordStart -= 25; i.recordEnd -= 25; }
    }
  }
  let omission: { blockId: string; blockRevision: number; tokenIds: string[]; evidenceHash: string } | null = null;
  if (evidence.omission !== null) {
    const o = shape(evidence.omission, "schemaVersion status evidenceLevel documentHash baselineHash currentHash profileHash blockId channels limitations blockRevision tokenIds sourceIntervalSamples recordIntervalFrames inputHashes");
    fact(o.schemaVersion === "issue-189-v2-omission-evidence/v1" && o.status === "verified" && o.evidenceLevel === "local_consistency_only" &&
      o.documentHash === evidence.documentHash && o.baselineHash === before.receipt.derivedAudioHash && o.currentHash === after.receipt.derivedAudioHash &&
      equal(o.recordIntervalFrames, { start: 121, end: 127 }), "unbound/refused C evidence");
    const row = document.activeDraft.blocks.find((b) => b.id === o.blockId);
    fact(row?.type === "narration" && row.version === o.blockRevision && equal(o.tokenIds, [row.tokens[11]?.id]), "C must select only approved token11");
    const original = before.items.filter((i) => i.authoredEvent.kind === "narration" && i.authoredEvent.provenance.blockId === row.id);
    fact(original.length === 1 && original[0]!.recordStart === 0 && original[0]!.recordEnd === 200 && original[0]!.linkedUids.length === 0, "C exact primary row required");
    const prior = original[0]!; const segments = after.items.filter((i) => i.eventId === prior.eventId).sort((a, b) => a.recordStart - b.recordStart);
    fact(segments.length === 2 && segments.every((i) => i.itemUid !== prior.itemUid) && equal(segments.map((i) => [i.recordStart, i.recordEnd, i.sourceStart, i.sourceEnd]),
      [[0, 121, prior.sourceStart, prior.sourceStart + 121], [127, 200, prior.sourceStart + 127, prior.sourceEnd]]), "C exact non-ripple lift required");
    for (const segment of segments) fact(equal({ ...stable(segment), itemUid: prior.itemUid }, stable(prior)), "C split ownership/control delta");
    expected.splice(expected.findIndex((i) => i.itemUid === prior.itemUid), 1, ...structuredClone(segments));
    omission = { blockId: row.id, blockRevision: row.version, tokenIds: [row.tokens[11]!.id], evidenceHash: sha256CanonicalJson(o) };
  }
  fact(after.items.length === expected.length && expected.every((i) => {
    const actual = after.items.find((a) => a.itemUid === i.itemUid);
    return actual && equal(stable(actual), stable(i)) && equal(geometry(actual), geometry(i));
  }), "D: picture-only, ambiguous or unexplained native delta");
  fact(object(after.raw.timeline).durationFrames === (commands.trim ? 1082 : 1107), "unexplained programme extent/ripple");
  fact(commands.boundary || commands.trim || omission, "no approved native-derived change");
  fact(Number(commands.boundary !== null) + Number(commands.trim !== null) + Number(omission !== null) === 1,
    "A/B/C require independently isolated native evidence");
  return { schemaVersion: "issue-192-v2-inference/v1" as const, documentHash: evidence.documentHash,
    dependenciesHash: evidence.dependenciesHash, evidenceHash: sha256CanonicalJson(evidence), commands, omission };
}

export function inferCompositionV2(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2,
  evidence: CompositionEvidenceV2, authenticate: InferenceAuthenticatorV2) {
  const cases = Array.isArray(evidence) ? evidence : [evidence];
  fact(cases.length > 0 && cases.length <= 3, "one to three isolated cases required");
  const inferences = cases.map((c) => proposeV2Edits(document, dependencies, c, authenticate));
  const boundaries = inferences.flatMap((i) => i.commands.boundary ? [i.commands.boundary] : []);
  const trims = inferences.flatMap((i) => i.commands.trim ? [i.commands.trim] : []);
  const omissions = inferences.flatMap((i) => i.omission ? [i.omission] : []);
  fact(boundaries.length <= 1 && trims.length <= 1 && omissions.length <= 1, "duplicate or ambiguous case inference");
  return { schemaVersion: "issue-192-v2-composed-inference/v1" as const,
    documentHash: sha256CanonicalJson(document), dependenciesHash: sha256CanonicalJson(dependencies),
    evidenceHash: sha256CanonicalJson(cases), caseEvidenceHashes: inferences.map((i) => i.evidenceHash),
    commands: { boundary: boundaries[0] ?? null, trim: trims[0] ?? null, omission: null } satisfies RevisionCommandsV2,
    omission: omissions[0] ?? null };
}

/** Bind C to the exact A/B-staged document; the accepted #202 core owns transforms. */
export function prepareInferredRevisionV2(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2,
  inference: ReturnType<typeof inferCompositionV2>, preparedMedia: RevisionRequestV2["preparedMedia"], decisionHash: string) {
  fact(inference.documentHash === sha256CanonicalJson(document) && inference.dependenciesHash === sha256CanonicalJson(dependencies), "stale inference");
  const commands: RevisionCommandsV2 = structuredClone(inference.commands);
  if (inference.omission) {
    fact(/^sha256:[a-f0-9]{64}$/u.test(decisionHash), "explicit omission decision hash required");
    const ab = commands.boundary || commands.trim
      ? prepareRevisionInputsV2(document, dependencies, commands, preparedMedia)
      : { document, dependencies };
    commands.omission = { schemaVersion: "issue-189-v2-accepted-omission/v1", expectedDocumentHash: sha256CanonicalJson(ab.document),
      ...inference.omission, decisionHash };
  }
  return { commands, ...prepareRevisionInputsV2(document, dependencies, commands, preparedMedia) };
}

export function createInferredRevisionV2(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2,
  evidence: CompositionEvidenceV2, authenticate: InferenceAuthenticatorV2, request: Omit<RevisionRequestV2, "commands">, omissionDecisionHash: string) {
  const inference = inferCompositionV2(document, dependencies, evidence, authenticate);
  const stage = prepareInferredRevisionV2(document, dependencies, inference, request.preparedMedia, omissionDecisionHash);
  return { inference, proposal: createRevisionProposalV2(document, dependencies, { ...request, commands: stage.commands }) };
}

/** Re-infer against current authenticated facts at consumption, then use #202 history. */
export function decideInferredRevisionV2(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2,
  evidence: CompositionEvidenceV2, authenticate: InferenceAuthenticatorV2,
  candidate: ReturnType<typeof createInferredRevisionV2>, decision: RevisionDecisionV2, history: string[]) {
  const current = inferCompositionV2(document, dependencies, evidence, authenticate);
  fact(equal(current, candidate.inference), "inference evidence changed before decision");
  const stage = prepareInferredRevisionV2(document, dependencies, current, candidate.proposal.request.preparedMedia,
    candidate.proposal.request.commands.omission?.decisionHash ?? "");
  fact(equal(stage.commands, candidate.proposal.request.commands), "proposal commands differ from inference");
  return decideRevisionV2(document, dependencies, candidate.proposal, decision, history);
}
