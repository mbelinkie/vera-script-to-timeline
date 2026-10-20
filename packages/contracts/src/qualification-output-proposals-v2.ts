/** Pure #215 bridge for authenticated #214 geometry and explicit decisions. */
import { createHash } from "node:crypto";
import { canonicalJson, sha256CanonicalJson } from "./compiler-core.js";
import { compileTimelineV2 } from "./compiler-core-v2.js";
import { applyVisualSequenceEditV2 } from "./authoring-v2-edits.js";
import { validateScriptDocumentV2 } from "./authoring-v2-validation.js";
import { boundaryEvidenceProblemV2 } from "./narration-boundary-evidence-v2.js";
import type {
  CompilerDependenciesV2,
  NarrationBoundaryEvidenceV1,
  PreparedMediaBindingV1,
  RationalTime,
  ScriptDocumentV2,
  TimelineEventV2,
  TimelineManifestV2,
} from "./generated/contracts-v2.js";
import {
  createRevisionProposalV2,
  decideRevisionV2,
  prepareRevisionInputsV2,
  type RevisionCommandsV2,
  type RevisionDecisionV2,
  type RevisionRequestV2,
} from "./issue-192-v2-revision-core.js";
import type { RowHandoffV2 } from "./issue-189-v2-replacement.js";

type RecordValue = Record<string, unknown>;
type CaseKind = "A" | "B" | "C";
const LANE = "bounded_output_residual_consistency" as const;
const MAX_JSON_BYTES = 8 * 1024 * 1024;
const FRAME_SAMPLES = 2002;
const CONTEXT_HASH_FIELDS = [
  "originalDocumentSha256", "originalDependenciesSha256", "executionDocumentSha256", "executionDependenciesSha256",
  "packageSha256", "preflightSha256", "manifestSha256", "reportSha256", "preparationSha256",
  "hostSourceGraphSha256", "nativeSourceGraphSha256", "installedReleaseSha256", "runtimeSha256", "profileSha256",
];
const CONTEXT_FIELDS = ["lane", "invocationId", "caseId", "phase", "target", ...CONTEXT_HASH_FIELDS, "binding"];
const GEOMETRY_FIELDS = ["context", "extentFrames", "rate", "tracks", "items", "sourceMappings"];
const TRACK_FIELDS = ["trackId", "kind", "index", "name", "enabled", "locked"];
const INPUT_BINDING_FIELDS = ["schemaVersion", "lane", "context", "delivery", "sourceEntries", "tracks", "itemMappings", "nativeSources"];
const DELIVERY_FIELDS = ["eventId", "kind", "recordRange", "sourceRange"];
const RANGE_FIELDS = ["startFrame", "durationFrames"];
const ITEM_MAPPING_FIELDS = ["itemUid", "eventId", "sourceId", "mediaUid"];
const SOURCE_FIELDS = [
  "sourceId", "nativeSourceSha256", "pcmMode", "provenanceReceiptSha256", "provenancePinsSha256",
  "deliveryDerivationSha256", "pcmFileSha256", "decodedSamplesSha256", "originalBitDepth", "channels",
  "durationSamples", "sampleRate", "pcmMappingSha256", "nativeFrameOrigin", "pcmSampleOrigin",
];
const NATIVE_SOURCE_FIELDS = ["sourceId", "nativeSourceSha256"];
const ITEM_FIELDS = [
  "itemUid", "eventId", "sourceId", "mediaUid", "kind", "trackId", "recordStart", "recordDuration",
  "sourceStart", "sourceDuration", "linkedItemUids", "online", "enabled", "speed", "sourceMappingSha256",
];
const COMPARISON_FIELDS = [
  "schemaVersion", "lane", "context", "status", "commitmentRawSha256", "commitmentPayloadSha256",
  "reservationRawSha256", "renderLineage", "decodeRecordRawSha256", "preGeometryRawSha256", "postGeometryRawSha256",
  "geometrySha256", "algorithmSha256", "metrics", "signalMetrics", "priorLedgerHeadSha256", "internalControls",
  "geometryStability", "controlStability", "futureAuthority", "comparisonReceiptSha256",
];
const LINEAGE_FIELDS = [
  "schemaVersion", "lane", "context", "commitmentRawSha256", "reservationRawSha256", "renderIntentSha256",
  "effectReceiptSha256", "startReceiptSha256", "completionReceiptSha256", "jobId", "sourceOutputRawSha256",
];
const PROPOSAL_FIELDS = ["schemaVersion", "lane", "inference", "inferenceDecision", "inferenceHistory", "request", "revision",
  "internalControls", "geometryStability", "controlStability", "futureAuthority", "proposalHash"];

export interface QualificationOutputObservationCaseV1 {
  schemaVersion: "qualification-output-observation/v1";
  lane: typeof LANE;
  caseId: string;
  pristineGeometryJson: string;
  editedGeometryJson: string;
  pristineInputBindingJson: string;
  editedInputBindingJson: string;
  pristineComparisonJson: string;
  editedComparisonJson: string;
  pairJson: string | null;
  audioEquality: QualificationOutputAudioEqualityV1 | null;
  omissionSupport: QualificationOutputOmissionSupportV2 | null;
}

export interface QualificationOutputAudioEqualityV1 {
  schemaVersion: "qualification-output-audio-equality/v1";
  lane: typeof LANE;
  caseId: string;
  pristinePredictionSha256: string;
  editedPredictionSha256: string;
  pristineDecodedSamplesSha256: string;
  editedDecodedSamplesSha256: string;
  predictionByteLength: number;
  decodedSampleByteLength: number;
  sampleCount: number;
}

/**
 * Machine-derived support for a word omission. The host derives this record from the
 * row's measured boundary evidence and the authenticated native cut geometry; the
 * bridge re-derives it independently and refuses any record that differs. It names
 * no token: the selected word is the one the observed cut uniquely isolates.
 * Hash fields ending in `Sha256` or named `timingHash` are bare lowercase hex; the
 * `...Hash` evidence pins carry the `sha256:` prefix used by the dependencies.
 */
export interface QualificationOutputOmissionSupportV2 {
  schemaVersion: "qualification-output-omission-support/v2";
  lane: typeof LANE;
  caseId: string;
  documentHash: string;
  dependenciesHash: string;
  blockId: string;
  blockRevision: number;
  method: "measured_audio_boundaries/v1";
  selectedTokenId: string;
  leftNeighborTokenId: string | null;
  rightNeighborTokenId: string | null;
  /** sha256CanonicalJson of the row's NarrationBoundaryEvidenceV1 in the dependencies. */
  boundaryEvidenceHash: string;
  /** verification.measurementArtifactHash of that evidence. */
  measurementArtifactHash: string;
  audioSha256: string;
  timingHash: string;
  onsetUncertainty: RationalTime;
  audibleEndUncertainty: RationalTime;
  /** From the bound PCM source entry of the narration item. */
  nativeFrameOrigin: number;
  pcmSampleOrigin: number;
  /** Whole-frame gap actually observed on the timeline (record) and in the narration source. */
  cutRecordFrames: { startFrame: number; endFrame: number };
  cutSourceFrames: { startFrame: number; endFrame: number };
  /** Narration-row-relative PCM samples: (sourceFrame - nativeFrameOrigin) * 2002 + pcmSampleOrigin. */
  cutSamples: { startSample: number; endSample: number };
  /** Inclusive integer-sample safe range for each cut edge, from evidence plus uncertainties. */
  cutStartEnvelope: { minSample: number; maxSample: number };
  cutEndEnvelope: { minSample: number; maxSample: number };
  pristineGeometryRawSha256: string;
  editedGeometryRawSha256: string;
  pristineComparisonRawSha256: string;
  editedComparisonRawSha256: string;
  pairRawSha256: string;
}

export interface QualificationOutputObservationBatchV1 {
  schemaVersion: "qualification-output-observation-batch/v1";
  lane: typeof LANE;
  documentHash: string;
  dependenciesHash: string;
  cases: QualificationOutputObservationCaseV1[];
}

export interface QualificationOutputDecisionV1 {
  schemaVersion: "qualification-output-decision/v1";
  proposalHash: string;
  historyHash: string;
  outcome: "accept" | "reject";
}

export interface QualificationOutputInferenceV1 {
  schemaVersion: "qualification-output-inference/v1";
  lane: typeof LANE;
  documentHash: string;
  dependenciesHash: string;
  evidenceHash: string;
  caseEvidenceHashes: string[];
  commands: RevisionCommandsV2;
  omission: { blockId: string; blockRevision: number; tokenIds: string[]; evidenceHash: string } | null;
  caseKinds: CaseKind[];
  inferenceHash: string;
  internalControls: "unverified";
  geometryStability: "not_claimed";
  controlStability: "not_claimed";
  futureAuthority: false;
}

export interface QualificationOutputRegenerationRequestV1 {
  schemaVersion: "qualification-output-regeneration-request/v1";
  lane: typeof LANE;
  policy: "replace_whole_row";
  blockId: string;
  blockRevision: number;
  text: string;
  textHash: string;
  revisedDocumentHash: string;
  evidenceHash: string;
  decisionHash: string;
}

export interface QualificationOutputProposalV1 {
  schemaVersion: "qualification-output-proposal/v1";
  lane: typeof LANE;
  inference: QualificationOutputInferenceV1;
  inferenceDecision: QualificationOutputDecisionV1;
  inferenceHistory: string[];
  request: RevisionRequestV2;
  revision: ReturnType<typeof createRevisionProposalV2>;
  proposalHash: string;
  internalControls: "unverified";
  geometryStability: "not_claimed";
  controlStability: "not_claimed";
  futureAuthority: false;
}

export interface QualificationOutputPureRequestV1 {
  schemaVersion: "qualification-output-pure-request/v1";
  mode: "baseline" | "infer" | "derive_omission" | "stage" | "proposal" | "decide";
  document: ScriptDocumentV2;
  dependencies: CompilerDependenciesV2;
  evidence: QualificationOutputObservationBatchV1 | null;
  preparedMedia: PreparedMediaBindingV1[];
  handoff: RowHandoffV2 | null;
  inferenceDecision: QualificationOutputDecisionV1 | null;
  inferenceHistory: string[];
  candidate: QualificationOutputProposalV1 | null;
  decision: QualificationOutputDecisionV1 | null;
  history: string[];
}

interface TrackV1 extends RecordValue {
  trackId: string; kind: "video" | "audio"; index: number; name: string; enabled: true; locked: boolean;
}
interface ItemV1 extends RecordValue {
  itemUid: string; eventId: string; sourceId: string; mediaUid: string; kind: "video" | "audio"; trackId: string;
  recordStart: number; recordDuration: number; sourceStart: number; sourceDuration: number;
  linkedItemUids: string[]; online: true; enabled: true; speed: { numerator: 1; denominator: 1 }; sourceMappingSha256: string;
}
interface GeometryV1 extends RecordValue {
  context: RecordValue; extentFrames: number; tracks: TrackV1[]; items: ItemV1[]; sourceMappings: RecordValue[];
}
interface ParsedGeometry {
  raw: string; rawSha256: string; envelope: RecordValue; geometry: GeometryV1; context: RecordValue; inputBinding: RecordValue;
}
interface ParsedComparison { raw: string; rawSha256: string; value: RecordValue; context: RecordValue; }
interface ParsedCase {
  source: QualificationOutputObservationCaseV1; pristine: ParsedGeometry; edited: ParsedGeometry;
  pristineComparison: ParsedComparison; editedComparison: ParsedComparison; pair: RecordValue | null;
}

function fact(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}
function record(value: unknown, label = "object record"): RecordValue {
  fact(value !== null && typeof value === "object" && !Array.isArray(value), `${label} required`);
  return value as RecordValue;
}
function shape(value: unknown, fields: string[], label: string): RecordValue {
  const result = record(value, label);
  fact(equal(Object.keys(result).sort(), [...fields].sort()), `unsupported ${label} fields`);
  return result;
}
function list(value: unknown, max = 4096): unknown[] {
  fact(Array.isArray(value) && value.length <= max, "bounded complete array required");
  return value;
}
function integer(value: unknown, label = "safe nonnegative integer"): number {
  fact(Number.isSafeInteger(value) && Number(value) >= 0, `${label} required`);
  return Number(value);
}
function identity(value: unknown, label = "bounded identity"): string {
  fact(typeof value === "string" && value.length > 0 && value.length <= 512 && !/[\p{Cc}\p{Cf}\p{Cs}]/u.test(value), `${label} required`);
  return value;
}
function bareHash(value: unknown, label = "raw lowercase SHA256"): string {
  fact(typeof value === "string" && /^[a-f0-9]{64}$/u.test(value), `${label} required`);
  return value;
}
const bare = (value: string): string => value.replace(/^sha256:/u, "");
function rawSha256(raw: string): string { return createHash("sha256").update(raw, "utf8").digest("hex"); }
function codepointCompare(a: string, b: string): number {
  const left = Array.from(a, (c) => c.codePointAt(0)!); const right = Array.from(b, (c) => c.codePointAt(0)!);
  for (let i = 0; i < Math.min(left.length, right.length); i++) if (left[i] !== right[i]) return left[i]! - right[i]!;
  return left.length - right.length;
}
function sortedJson(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortedJson);
  if (value !== null && typeof value === "object") {
    const output: RecordValue = {};
    for (const key of Object.keys(value).sort(codepointCompare)) output[key] = sortedJson((value as RecordValue)[key]);
    return output;
  }
  return value;
}
/** #214 Python JSON hashes are compact, UTF-8, codepoint-key-sorted bytes. */
function pythonJsonHash(value: unknown): string { return rawSha256(JSON.stringify(sortedJson(value))); }
function equal(a: unknown, b: unknown): boolean { return canonicalJson(a) === canonicalJson(b); }
function without(value: RecordValue, keys: string[]): RecordValue {
  return Object.fromEntries(Object.entries(value).filter(([key]) => !keys.includes(key)));
}

function checkJsonTree(value: unknown, depth = 0): void {
  fact(depth <= 64, "JSON nesting exceeds bound");
  if (value === null || typeof value === "boolean") return;
  if (typeof value === "string") {
    fact(value.length <= MAX_JSON_BYTES && !/[\p{Cs}]/u.test(value), "unsupported JSON string"); return;
  }
  if (typeof value === "number") {
    fact(Number.isFinite(value) && (!Number.isInteger(value) || Number.isSafeInteger(value)), "unsafe JSON number"); return;
  }
  if (Array.isArray(value)) { for (const child of value) checkJsonTree(child, depth + 1); return; }
  fact(value !== null && typeof value === "object", "unsupported JSON value");
  for (const [key, child] of Object.entries(value as RecordValue)) { checkJsonTree(key, depth + 1); checkJsonTree(child, depth + 1); }
}

function parseRaw(raw: unknown, label: string): RecordValue {
  fact(typeof raw === "string" && Buffer.byteLength(raw, "utf8") <= MAX_JSON_BYTES, `bounded ${label} JSON text required`);
  let parsed: unknown;
  try { parsed = JSON.parse(raw); } catch { throw new Error(`invalid ${label} JSON`); }
  checkJsonTree(parsed);
  const stack: { object: boolean; expectKey: boolean; keys: Set<string> }[] = [];
  const tokens = raw.matchAll(/"(?:[^"\\]|\\.)*"|[{}[\]:,]|[^\s{}[\]:,]+/gu);
  for (const match of tokens) {
    const token = match[0];
    const top = stack.at(-1);
    if (token === "{" || token === "[") {
      fact(stack.length < 64, `${label} nesting exceeds bound`);
      stack.push({ object: token === "{", expectKey: token === "{", keys: new Set() });
    } else if (token === "}" || token === "]") stack.pop();
    else if (token === ",") { if (top?.object) top.expectKey = true; }
    else if (token === ":") { if (top?.object) top.expectKey = false; }
    else if (token.startsWith('"') && top?.object && top.expectKey) {
      let key: unknown; try { key = JSON.parse(token); } catch { throw new Error(`invalid ${label} object key`); }
      fact(typeof key === "string" && !top.keys.has(key), `duplicate ${label} JSON key`);
      top.keys.add(key); top.expectKey = false;
    } else if (!token.startsWith('"') && token !== "true" && token !== "false" && token !== "null") {
      const number = Number(token);
      fact(Number.isFinite(number) && (!Number.isInteger(number) || Number.isSafeInteger(number)), `unsafe ${label} JSON integer`);
    }
  }
  return record(parsed, `${label} JSON object`);
}

function validateContext(value: unknown, phase: "pristine" | "edited", caseId: string): RecordValue {
  const context = shape(value, CONTEXT_FIELDS, "output context");
  fact(context.lane === LANE && context.phase === phase, "wrong output lane/phase");
  fact(identity(context.invocationId) && identity(context.caseId) === caseId, "output context case differs");
  const target = shape(context.target, ["projectName", "projectUid", "timelineName", "timelineUid"], "target");
  for (const value of Object.values(target)) identity(value, "target identity");
  for (const key of CONTEXT_HASH_FIELDS) bareHash(context[key], `${key} raw hash`);
  const binding = shape(context.binding, ["kind", "bindingSha256"], "baseline input binding");
  fact(binding.kind === "baseline", "revised output evidence cannot infer a source proposal");
  bareHash(binding.bindingSha256, "binding hash");
  const projection = without(context, ["preflightSha256", "preparationSha256", "invocationId", "binding"]);
  projection.binding = { kind: "baseline" };
  const calculatedBindingHash = pythonJsonHash(projection);
  fact(calculatedBindingHash === binding.bindingSha256, "stable host input binding hash differs");
  return context;
}

function validateGeometry(raw: unknown, inputBindingRaw: unknown, label: string, phase: "pristine" | "edited", caseId: string): ParsedGeometry {
  const text = raw as string;
  const envelope = shape(parseRaw(text, label), ["schemaVersion", "lane", "geometry", "inputBindingSha256", "capturePhase", "capturedAt", "expiresAt", "receiptSha256"], `${label} geometry envelope`);
  fact(envelope.schemaVersion === "qualification-output-geometry/v1" && envelope.lane === LANE, "wrong geometry namespace/lane");
  fact(envelope.capturePhase === "pre_render", "proposal inference requires authenticated pre-render geometry");
  bareHash(envelope.inputBindingSha256, "input binding hash"); bareHash(envelope.receiptSha256, "geometry receipt hash");
  fact(typeof inputBindingRaw === "string", "raw input binding JSON text required");
  const inputBindingText = inputBindingRaw;
  const inputBinding = shape(parseRaw(inputBindingText, `${label} input binding`), INPUT_BINDING_FIELDS, `${label} input binding`);
  fact(rawSha256(inputBindingText) === envelope.inputBindingSha256, "geometry/input binding raw hash differs");
  fact(inputBinding.schemaVersion === "qualification-output-inputs/v1" && inputBinding.lane === LANE, "wrong input binding namespace/lane");
  fact(typeof envelope.capturedAt === "string" && typeof envelope.expiresAt === "string" &&
    Number.isFinite(Date.parse(envelope.capturedAt)) && Number.isFinite(Date.parse(envelope.expiresAt)) &&
    Date.parse(envelope.capturedAt) <= Date.parse(envelope.expiresAt), "geometry capture chronology differs");
  const geometry = shape(envelope.geometry, GEOMETRY_FIELDS, `${label} semantic geometry`) as GeometryV1;
  const context = validateContext(geometry.context, phase, caseId);
  fact(equal(inputBinding.context, context), "input binding context differs from geometry");
  const extent = integer(geometry.extentFrames, "programme extent"); fact(extent > 0 && extent <= 1498, "unsupported programme extent");
  const rate = shape(geometry.rate, ["numerator", "denominator"], "frame rate");
  fact(integer(rate.numerator) === 24000 && integer(rate.denominator) === 1001, "unsupported frame rate");

  const tracks = list(geometry.tracks, 64).map((value) => {
    const track = shape(value, TRACK_FIELDS, "native track") as TrackV1;
    identity(track.trackId); identity(track.name);
    fact(track.kind === "video" || track.kind === "audio", "unknown track kind");
    fact(integer(track.index) >= 1 && integer(track.index) <= 32 && track.enabled === true && typeof track.locked === "boolean", "unsupported track state");
    return track;
  });
  fact(new Set(tracks.map((t) => t.trackId)).size === tracks.length, "duplicate track UID");
  fact(equal(tracks.map((t) => t.trackId), [...tracks.map((t) => t.trackId)].sort(codepointCompare)), "unordered track inventory");
  const trackSlots = tracks.map((t) => `${t.kind}:${t.index}`);
  fact(new Set(trackSlots).size === tracks.length, "duplicate track index");
  for (const kind of ["video", "audio"]) {
    const indexes = tracks.filter((t) => t.kind === kind).map((t) => t.index).sort((a, b) => a - b);
    fact(indexes.every((n, i) => n === i + 1), "incomplete track index inventory");
  }

  const boundTracks = list(inputBinding.tracks, 64).map((value) => {
    const track = shape(value, TRACK_FIELDS, "bound input track") as TrackV1;
    identity(track.trackId); identity(track.name);
    fact((track.kind === "video" || track.kind === "audio") && integer(track.index) >= 1 && integer(track.index) <= 32 &&
      track.enabled === true && typeof track.locked === "boolean", "unsupported bound input track");
    return track;
  });
  fact(equal(boundTracks, tracks), "geometry tracks differ from input binding");

  const delivery = list(inputBinding.delivery, 2048).map((value) => {
    const row = shape(value, DELIVERY_FIELDS, "bound delivery row");
    identity(row.eventId, "delivery event identity"); identity(row.kind, "delivery event kind");
    for (const key of ["recordRange", "sourceRange"]) {
      const range = shape(row[key], RANGE_FIELDS, `delivery ${key}`);
      integer(range.startFrame); fact(integer(range.durationFrames) > 0, "delivery duration required");
    }
    return row;
  });
  const deliveryIds = delivery.map((row) => row.eventId as string);
  fact(new Set(deliveryIds).size === deliveryIds.length && equal(deliveryIds, [...deliveryIds].sort(codepointCompare)), "duplicate or unordered delivery inventory");

  const sourceEntries = list(inputBinding.sourceEntries, 16).map((value) => {
    const source = shape(value, SOURCE_FIELDS, "bound PCM source entry");
    identity(source.sourceId, "source entry identity");
    for (const key of SOURCE_FIELDS.filter((field) => field.endsWith("Sha256"))) bareHash(source[key], `source entry ${key}`);
    fact(source.pcmMode === "wav-direct" || source.pcmMode === "prepared-audio", "unsupported source PCM mode");
    fact([16, 24].includes(integer(source.originalBitDepth)) && integer(source.channels) >= 1 && integer(source.channels) <= 2 &&
      integer(source.durationSamples) >= 960 && integer(source.durationSamples) <= 16_000_000 && integer(source.sampleRate) === 48000 &&
      integer(source.pcmSampleOrigin) <= integer(source.durationSamples), "unsupported PCM source geometry");
    integer(source.nativeFrameOrigin);
    return source;
  });
  const sourceEntryIds = sourceEntries.map((source) => source.sourceId as string);
  fact(new Set(sourceEntryIds).size === sourceEntryIds.length && equal(sourceEntryIds, [...sourceEntryIds].sort(codepointCompare)), "duplicate or unordered PCM source inventory");
  fact(sourceEntries.reduce((cells, source) => cells + integer(source.channels) * integer(source.durationSamples), 0) <= 32_000_000,
    "aggregate PCM source sample cells exceed bound");

  const nativeSources = list(inputBinding.nativeSources, 64).map((value) => {
    const source = shape(value, NATIVE_SOURCE_FIELDS, "bound native source");
    identity(source.sourceId, "native source identity"); bareHash(source.nativeSourceSha256, "native source hash");
    return source;
  });
  const nativeIds = nativeSources.map((source) => source.sourceId as string);
  fact(new Set(nativeIds).size === nativeIds.length && equal(nativeIds, [...nativeIds].sort(codepointCompare)), "duplicate or unordered native source inventory");
  const nativeSourceMap = new Map(nativeSources.map((source) => [source.sourceId as string, source]));
  const sourceEntryMap = new Map(sourceEntries.map((source) => [source.sourceId as string, source]));
  for (const source of sourceEntries) {
    fact(nativeSourceMap.get(source.sourceId as string)?.nativeSourceSha256 === source.nativeSourceSha256,
      "PCM source native hash differs from complete native source binding");
  }

  const sources = list(geometry.sourceMappings, 16).map((value) => {
    const source = shape(value, ["sourceId", "nativeSourceSha256", "sourceEntrySha256"], "source mapping");
    identity(source.sourceId); bareHash(source.nativeSourceSha256); bareHash(source.sourceEntrySha256);
    return source;
  });
  fact(new Set(sources.map((s) => s.sourceId)).size === sources.length, "duplicate source identity");
  const sourceIds = sources.map((s) => s.sourceId as string);
  fact(equal(sourceIds, [...sourceIds].sort(codepointCompare)), "unordered source inventory");
  const expectedMappings = sourceEntries.map((source) => ({
    sourceId: source.sourceId,
    nativeSourceSha256: source.nativeSourceSha256,
    sourceEntrySha256: pythonJsonHash(source),
  }));
  fact(equal(sources, expectedMappings), "audio source mapping inventory differs from input binding");
  const trackMap = new Map(tracks.map((t) => [t.trackId, t]));
  const audioMappingBySource = new Map<string, string>();
  const items = list(geometry.items, 2048).map((value) => {
    const item = shape(value, ITEM_FIELDS, "native item") as ItemV1;
    for (const key of ["itemUid", "eventId", "sourceId", "mediaUid", "trackId"]) identity(item[key], `item ${key}`);
    fact(item.kind === "video" || item.kind === "audio", "unknown item kind");
    const track = trackMap.get(item.trackId); fact(track !== undefined && track.kind === item.kind, "unknown or mismatched item track");
    const nativeSource = nativeSourceMap.get(item.sourceId);
    fact(nativeSource !== undefined, "unknown item source");
    const recordStart = integer(item.recordStart); const recordDuration = integer(item.recordDuration);
    integer(item.sourceStart); const sourceDuration = integer(item.sourceDuration);
    fact(recordDuration > 0 && sourceDuration === recordDuration && recordStart + recordDuration <= extent, "unsupported item interval");
    const speed = shape(item.speed, ["numerator", "denominator"], "item speed");
    fact(integer(speed.numerator) === 1 && integer(speed.denominator) === 1 && item.enabled === true && item.online === true, "offline, disabled or non-unit-speed item");
    bareHash(item.sourceMappingSha256, "item source mapping hash");
    if (item.kind === "video") fact(item.sourceMappingSha256 === nativeSource.nativeSourceSha256, "video source mapping differs");
    else {
      const sourceEntry = sourceEntryMap.get(item.sourceId);
      fact(sourceEntry !== undefined, "audio item has no bound PCM source entry");
      const old = audioMappingBySource.get(item.sourceId);
      fact(old === undefined || old === item.sourceMappingSha256, "split audio source mapping differs");
      fact(item.sourceMappingSha256 === sourceEntry.pcmMappingSha256, "audio source mapping differs from bound PCM source entry");
      audioMappingBySource.set(item.sourceId, item.sourceMappingSha256);
    }
    const links = list(item.linkedItemUids, 2048).map((uid) => identity(uid, "linked item UID"));
    fact(!links.includes(item.itemUid) && new Set(links).size === links.length && equal(links, [...links].sort(codepointCompare)), "duplicate/self/unordered links");
    return item;
  });
  fact(new Set(items.map((i) => i.itemUid)).size === items.length, "duplicate native item UID");
  fact(equal(items, [...items].sort((a, b) => integer(a.recordStart) - integer(b.recordStart) || codepointCompare(a.itemUid, b.itemUid))), "unordered native item inventory");
  const byUid = new Map(items.map((item) => [item.itemUid, item]));
  for (const item of items) for (const uid of item.linkedItemUids) {
    const linked = byUid.get(uid); fact(linked !== undefined && linked.linkedItemUids.includes(item.itemUid), "incomplete/asymmetric item links");
  }
  const usedNativeIds = [...new Set(items.map((item) => item.sourceId))].sort(codepointCompare);
  fact(equal(nativeIds, usedNativeIds), "complete native source inventory differs from item source identities");
  fact(sourceEntries.every((source) => items.some((item) => item.kind === "audio" && item.sourceId === source.sourceId)), "unexplained PCM source inventory entry");
  const itemMappings = items.map((item) => ({ itemUid: item.itemUid, eventId: item.eventId, sourceId: item.sourceId, mediaUid: item.mediaUid }))
    .sort((a, b) => codepointCompare(a.itemUid, b.itemUid));
  const boundItemMappings = list(inputBinding.itemMappings, 2048).map((value) => {
    const mapping = shape(value, ITEM_MAPPING_FIELDS, "bound native item mapping");
    for (const key of ITEM_MAPPING_FIELDS) identity(mapping[key], `item mapping ${key}`);
    return mapping;
  });
  fact(equal(boundItemMappings, itemMappings), "native item mappings differ from input binding");
  const itemEventIds = [...new Set(items.map((item) => item.eventId))].sort(codepointCompare);
  fact(equal(deliveryIds, itemEventIds), "delivery inventory differs from native item mappings");
  return { raw: text, rawSha256: rawSha256(text), envelope, geometry, context, inputBinding };
}

function metricRows(value: unknown, consistentExpected: boolean | null): RecordValue[] {
  const rows = list(value, 2);
  fact(rows.length === 2, "exact two-channel residual metrics required");
  return rows.map((item) => {
    const metric = shape(item, ["residualRms", "maximumSliding20msResidualRms", "consistent"], "residual metric");
    const rms = metric.residualRms; const sliding = metric.maximumSliding20msResidualRms;
    fact(typeof rms === "number" && Number.isFinite(rms) && rms >= 0 && typeof sliding === "number" && Number.isFinite(sliding) && sliding >= 0, "invalid residual metric");
    const calculated = rms <= 0.0004 && sliding <= 0.006;
    fact(metric.consistent === calculated && (consistentExpected === null || calculated === consistentExpected), "residual gate differs");
    return metric;
  });
}

function validateComparison(raw: unknown, label: string, expectedContext: RecordValue): ParsedComparison {
  const text = raw as string;
  const value = shape(parseRaw(text, label), COMPARISON_FIELDS, `${label} terminal comparison`);
  fact(value.schemaVersion === "qualification-output-comparison/v1" && value.lane === LANE && value.status === "compared_consistent", "terminal comparison did not qualify");
  const context = validateContext(value.context, expectedContext.phase as "pristine" | "edited", expectedContext.caseId as string);
  fact(equal(context, expectedContext), "comparison/geometry context differs");
  for (const key of ["commitmentRawSha256", "commitmentPayloadSha256", "reservationRawSha256", "decodeRecordRawSha256",
    "preGeometryRawSha256", "postGeometryRawSha256", "geometrySha256", "algorithmSha256", "priorLedgerHeadSha256", "comparisonReceiptSha256"]) bareHash(value[key]);
  const lineage = shape(value.renderLineage, LINEAGE_FIELDS, "render lineage");
  fact(lineage.schemaVersion === "qualification-output-lineage/v1" && lineage.lane === LANE && equal(lineage.context, context), "render lineage context differs");
  for (const key of ["commitmentRawSha256", "reservationRawSha256", "renderIntentSha256", "effectReceiptSha256", "startReceiptSha256", "completionReceiptSha256", "sourceOutputRawSha256"]) bareHash(lineage[key]);
  identity(lineage.jobId, "native job UID");
  fact(lineage.commitmentRawSha256 === value.commitmentRawSha256 && lineage.reservationRawSha256 === value.reservationRawSha256, "comparison lineage hashes differ");
  fact(value.preGeometryRawSha256 !== value.postGeometryRawSha256, "comparison replayed its pre-render geometry capture");
  metricRows(value.metrics, true); metricRows(value.signalMetrics, false);
  fact(value.internalControls === "unverified" && value.geometryStability === "not_claimed" && value.controlStability === "not_claimed" && value.futureAuthority === false, "unsupported authority/control claim");
  return { raw: text, rawSha256: rawSha256(text), value, context };
}

function metricDifference(value: unknown): RecordValue[] {
  const rows = metricRows(value, null);
  fact(rows.some((row) => row.consistent === false), "audio-changing pair is not discriminable at fixed thresholds");
  return rows;
}
function validatePair(raw: unknown, pristine: ParsedComparison, edited: ParsedComparison, pristineGeometry: GeometryV1, editedGeometry: GeometryV1): RecordValue {
  fact(typeof raw === "string", "audio-changing proposal requires host-recomputed pair evidence");
  const pair = shape(parseRaw(raw, "pair comparison"), ["schemaVersion", "lane", "pristineComparisonRawSha256", "editedComparisonRawSha256",
    "pristineLedgerHeadSha256", "editedLedgerHeadSha256", "pristineSampleCount", "editedSampleCount", "commonInterval", "crossMetrics", "internalControls", "geometryStability", "controlStability", "futureAuthority"], "pair comparison");
  fact(pair.schemaVersion === "qualification-output-pair/v1" && pair.lane === LANE, "wrong pair namespace/lane");
  fact(pair.pristineComparisonRawSha256 === pristine.rawSha256 && pair.editedComparisonRawSha256 === edited.rawSha256, "pair comparison raw pins differ");
  bareHash(pair.pristineLedgerHeadSha256); bareHash(pair.editedLedgerHeadSha256);
  fact(pair.pristineLedgerHeadSha256 !== pair.editedLedgerHeadSha256, "replayed pair ledger head");
  const pristineSamples = integer(pair.pristineSampleCount, "pair pristine sample count");
  const editedSamples = integer(pair.editedSampleCount, "pair edited sample count");
  fact(pristineSamples === pristineGeometry.extentFrames * FRAME_SAMPLES && editedSamples === editedGeometry.extentFrames * FRAME_SAMPLES, "pair sample counts differ from geometry extents");
  const common = shape(pair.commonInterval, ["startSample", "endSample"], "pair common interval");
  fact(common.startSample === 0 && common.endSample === Math.min(pristineSamples, editedSamples) && integer(common.endSample, "pair common interval end") >= 960, "pair common interval differs from shared extent");
  const cross = shape(pair.crossMetrics, ["predictionDifference", "editedAgainstPristine", "pristineAgainstEdited"], "pair cross metrics");
  for (const metrics of Object.values(cross)) metricDifference(metrics);
  fact(pair.internalControls === "unverified" && pair.geometryStability === "not_claimed" && pair.controlStability === "not_claimed" && pair.futureAuthority === false, "unsupported pair authority/control claim");
  return pair;
}

function validateAudioEquality(value: unknown, caseId: string, a: GeometryV1, b: GeometryV1): void {
  const proof = shape(value, ["schemaVersion", "lane", "caseId", "pristinePredictionSha256", "editedPredictionSha256", "pristineDecodedSamplesSha256", "editedDecodedSamplesSha256", "predictionByteLength", "decodedSampleByteLength", "sampleCount"], "video-only audio equality proof");
  fact(proof.schemaVersion === "qualification-output-audio-equality/v1" && proof.lane === LANE && proof.caseId === caseId, "wrong audio equality namespace/case");
  const predictionA = bareHash(proof.pristinePredictionSha256); const predictionB = bareHash(proof.editedPredictionSha256);
  const decodedA = bareHash(proof.pristineDecodedSamplesSha256); const decodedB = bareHash(proof.editedDecodedSamplesSha256);
  const count = integer(proof.sampleCount, "audio sample count");
  fact(count > 0 && integer(proof.predictionByteLength) === count * 16 && integer(proof.decodedSampleByteLength) === count * 8 &&
    count === a.extentFrames * FRAME_SAMPLES && count === b.extentFrames * FRAME_SAMPLES, "audio equality byte geometry differs");
  fact(predictionA === predictionB && decodedA === decodedB, "video-only edit changed predicted or decoded audio bytes");
}

function parseCase(value: unknown): ParsedCase {
  const source = shape(value, ["schemaVersion", "lane", "caseId", "pristineGeometryJson", "editedGeometryJson", "pristineInputBindingJson", "editedInputBindingJson", "pristineComparisonJson", "editedComparisonJson", "pairJson", "audioEquality", "omissionSupport"], "observation case") as unknown as QualificationOutputObservationCaseV1;
  fact(source.schemaVersion === "qualification-output-observation/v1" && source.lane === LANE, "wrong observation namespace/lane");
  const caseId = identity(source.caseId, "case identity");
  fact(typeof source.pristineGeometryJson === "string" && typeof source.editedGeometryJson === "string" &&
    typeof source.pristineInputBindingJson === "string" && typeof source.editedInputBindingJson === "string" &&
    typeof source.pristineComparisonJson === "string" && typeof source.editedComparisonJson === "string", "raw authenticated JSON text required");
  const pristine = validateGeometry(source.pristineGeometryJson, source.pristineInputBindingJson, "pristine", "pristine", caseId);
  const edited = validateGeometry(source.editedGeometryJson, source.editedInputBindingJson, "edited", "edited", caseId);
  const pristineComparison = validateComparison(source.pristineComparisonJson, "pristine comparison", pristine.context);
  const editedComparison = validateComparison(source.editedComparisonJson, "edited comparison", edited.context);
  fact(equal(pristine.context.target, edited.context.target) && pristine.context.invocationId !== edited.context.invocationId, "target replay or target switch");
  const ignored = ["phase", "invocationId", "binding", "preflightSha256", "preparationSha256"];
  fact(equal(without(pristine.context, ignored), without(edited.context, ignored)), "pristine/edited authenticated input identities differ");
  for (const geometry of [pristine, edited]) {
    fact(pythonJsonHash(geometry.geometry) === (geometry === pristine ? pristineComparison : editedComparison).value.geometrySha256, "comparison/geometry semantic hash differs");
  }
  const pristineLineage = record(pristineComparison.value.renderLineage);
  const editedLineage = record(editedComparison.value.renderLineage);
  fact(pristineLineage.jobId !== editedLineage.jobId &&
    pristineLineage.sourceOutputRawSha256 !== editedLineage.sourceOutputRawSha256 &&
    pristineComparison.value.commitmentRawSha256 !== editedComparison.value.commitmentRawSha256 &&
    pristineComparison.value.reservationRawSha256 !== editedComparison.value.reservationRawSha256, "terminal output replay detected");
  fact(edited.geometry.extentFrames <= pristine.geometry.extentFrames, "observed edit lengthened capture extent");
  const pair = source.pairJson === null ? null : validatePair(source.pairJson, pristineComparison, editedComparison, pristine.geometry, edited.geometry);
  if (source.audioEquality !== null) validateAudioEquality(source.audioEquality, caseId, pristine.geometry, edited.geometry);
  return { source, pristine, edited, pristineComparison, editedComparison, pair };
}

function validateBatch(value: unknown, document: ScriptDocumentV2, dependencies: CompilerDependenciesV2): { batch: QualificationOutputObservationBatchV1; cases: ParsedCase[]; documentHash: string; dependenciesHash: string } {
  const batch = shape(value, ["schemaVersion", "lane", "documentHash", "dependenciesHash", "cases"], "observation batch") as unknown as QualificationOutputObservationBatchV1;
  const documentHash = sha256CanonicalJson(document); const dependenciesHash = sha256CanonicalJson(dependencies);
  fact(batch.schemaVersion === "qualification-output-observation-batch/v1" && batch.lane === LANE && batch.documentHash === documentHash && batch.dependenciesHash === dependenciesHash, "stale document/dependency observation batch");
  const rows = list(batch.cases, 3); fact(rows.length > 0, "one to three isolated observation cases required");
  const cases = rows.map((item) => parseCase(item));
  fact(new Set(cases.map((c) => c.source.caseId)).size === cases.length, "duplicate observation case identity");
  return { batch, cases, documentHash, dependenciesHash };
}

function checkBaselineGeometry(geometry: GeometryV1, manifest: TimelineManifestV2): Map<string, ItemV1> {
  fact(geometry.extentFrames === manifest.timeline.durationFrames, "pristine geometry extent differs from compiler");
  const events = manifest.events.filter((event) => event.kind !== "script_marker");
  const itemByEvent = new Map<string, ItemV1>();
  for (const item of geometry.items) {
    fact(!itemByEvent.has(item.eventId), "ambiguous pristine item/event mapping");
    itemByEvent.set(item.eventId, item);
  }
  fact(itemByEvent.size === events.length && events.every((event) => itemByEvent.has(event.eventId)), "incomplete pristine event geometry");
  for (const event of events) {
    const item = itemByEvent.get(event.eventId)!;
    checkItemAgainstEvent(item, event, null);
  }
  return itemByEvent;
}

function expectedKind(event: TimelineEventV2): "video" | "audio" {
  if (event.kind === "narration" || event.kind === "source_audio") return "audio";
  if (event.kind === "primary_visual" || event.kind === "overlay_visual" || event.kind === "placeholder") return "video";
  throw new Error("unsupported compiler event in native geometry");
}

function checkItemAgainstEvent(item: ItemV1, event: TimelineEventV2, base: ItemV1 | null): void {
  fact(item.eventId === event.eventId && item.kind === expectedKind(event) && item.trackId === event.trackId, "native item event/track mapping differs");
  const start = event.recordRange.startFrame; const duration = event.recordRange.endFrame - start;
  fact(item.recordStart === start && item.recordDuration === duration, "native record geometry differs from compiler");
  let sourceStart: number | null = null;
  if (event.sourceRange !== null) sourceStart = event.sourceRange.startFrame;
  else if (event.kind === "narration") sourceStart = 0;
  else if (base !== null) sourceStart = base.sourceStart;
  if (sourceStart !== null) fact(item.sourceStart === sourceStart, "native source start differs from compiled mapping");
  fact(item.sourceDuration === duration, "native source/record duration differs");
}

function compileForDocument(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2) {
  const compiled = compileTimelineV2(document, dependencies);
  fact(compiled.ok && compiled.report.status === "ready", "candidate compile refused");
  return compiled;
}
// Inference-only stand-in: it carries the prior key with the trimmed range, because the revision core
// matches a replacement to its occurrence by pinned inputs and adopts the replacement's own key. The
// honest key of a real preparation is computed by the preparation (identity of its inputs), not predicted here.
function exactPreparedMediaForTrim(dependencies: CompilerDependenciesV2, blockId: string, durationFrames: number): PreparedMediaBindingV1[] {
  const occurrences = dependencies.occurrenceResolutions.filter((row) => row.owner.kind === "visual_only_block" && row.owner.blockId === blockId);
  fact(occurrences.length === 1 && occurrences[0]!.preparedMediaRequirementKey !== null, "trim preparation occurrence is ambiguous");
  const requirementKey = occurrences[0]!.preparedMediaRequirementKey;
  const bindings = dependencies.preparedMedia.filter((row) => row.requirementKey === requirementKey);
  fact(bindings.length === 1, "trim prepared-media binding is ambiguous");
  const prior = bindings[0]!;
  const numerator = durationFrames * prior.targetRate.denominator;
  const denominator = prior.targetRate.numerator;
  fact(Number.isSafeInteger(numerator) && Number.isSafeInteger(denominator) && numerator > 0 && denominator > 0,
    "trim duration is outside the safe exact frame grid");
  let a = numerator; let b = denominator;
  while (b !== 0) [a, b] = [b, a % b];
  return [{
    ...structuredClone(prior),
    requestedRange: { ...structuredClone(prior.requestedRange), duration: { numerator: numerator / a, denominator: denominator / a } },
  }];
}
function dependenciesForDocument(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2): CompilerDependenciesV2 {
  const result = structuredClone(dependencies);
  result.document = { ...result.document, liveHeadSequence: document.liveHeadSequence, contentHash: document.liveContentHash };
  return result;
}

function sameStableItem(a: ItemV1, b: ItemV1, allowUidChange = false): boolean {
  const fields = ITEM_FIELDS.filter((key) => !["recordStart", "recordDuration", "sourceStart", "sourceDuration", ...(allowUidChange ? ["itemUid"] : [])].includes(key));
  return equal(Object.fromEntries(fields.map((key) => [key, a[key]])), Object.fromEntries(fields.map((key) => [key, b[key]])));
}

function matchManifestGeometry(manifest: TimelineManifestV2, pristine: GeometryV1, edited: GeometryV1, options: { trimFrames: number }): boolean {
  if (!equal(pristine.tracks, edited.tracks) || !equal(pristine.sourceMappings, edited.sourceMappings)) return false;
  const expectedEvents = manifest.events.filter((event) => event.kind !== "script_marker");
  if (edited.items.length !== expectedEvents.length) return false;
  const beforeByUid = new Map(pristine.items.map((item) => [item.itemUid, item]));
  const afterByEvent = new Map(edited.items.map((item) => [item.eventId, item]));
  if (afterByEvent.size !== edited.items.length) return false;
  if (expectedEvents.some((event) => !afterByEvent.has(event.eventId))) return false;
  for (const event of expectedEvents) {
    const item = afterByEvent.get(event.eventId)!; const prior = beforeByUid.get(item.itemUid);
    if (prior === undefined || !sameStableItem(prior, item)) return false;
    try { checkItemAgainstEvent(item, event, prior); } catch { return false; }
  }
  if (options.trimFrames < 0 || edited.extentFrames !== pristine.extentFrames - options.trimFrames || manifest.timeline.durationFrames !== edited.extentFrames) return false;
  return edited.items.every((item) => item.recordStart + item.recordDuration <= manifest.timeline.durationFrames);
}

function sameEventGeometry(a: TimelineEventV2, b: TimelineEventV2): boolean {
  return equal(a.recordRange, b.recordRange) && equal(a.sourceRange, b.sourceRange) && equal(a.audio?.sampleRange ?? null, b.audio?.sampleRange ?? null);
}
function isHeldPicture(event: TimelineEventV2): boolean {
  return event.kind === "placeholder" || event.pictureTreatment?.kind === "still_frame";
}

function inferBoundaryCase(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2, input: ParsedCase, baseline: ReturnType<typeof compileForDocument>): RevisionCommandsV2["boundary"][] {
  const matches: RevisionCommandsV2["boundary"][] = [];
  const rows = document.activeDraft.blocks.filter((block) => block.type === "narration" && block.primaryVisualSequence !== undefined);
  for (const row of rows) {
    if (row.type !== "narration" || !row.primaryVisualSequence) continue;
    for (const slot of row.primaryVisualSequence.slots) {
      if (slot.kind !== "content") continue;
      for (const token of row.tokens) for (const affinity of ["before", "after"] as const) {
        const edit = { kind: "move_word_boundary" as const, blockId: row.id, boundaryOwnerId: slot.id, tokenId: token.id, affinity };
        const applied = applyVisualSequenceEditV2(document, row.primaryVisualSequence.version, edit);
        if (!applied.ok) continue;
        const candidateDependencies = dependenciesForDocument(applied.document, dependencies);
        const candidate = compileTimelineV2(applied.document, candidateDependencies);
        if (!candidate.ok || candidate.report.status !== "ready") continue;
        const changed = baseline.manifest.events.filter((event) => {
          const next = candidate.manifest.events.find((entry) => entry.eventId === event.eventId);
          return next !== undefined && !sameEventGeometry(event, next);
        });
        if (changed.length !== 2 || changed.some((event) => expectedKind(event) !== "video" || !isHeldPicture(event) || event.provenance.blockId !== row.id)) continue;
        if (!changed.some((event) => event.provenance.slotId === slot.id)) continue;
        if (!matchManifestGeometry(candidate.manifest, input.pristine.geometry, input.edited.geometry, { trimFrames: 0 })) continue;
        const priorEvents = baseline.manifest.events.filter((event) => event.kind !== "script_marker");
        const afterByUid = new Map(input.edited.geometry.items.map((item) => [item.itemUid, item]));
        if (input.pristine.geometry.items.some((item) => item.kind === "audio" && !equal(
          [item.recordStart, item.recordDuration, item.sourceStart, item.sourceDuration],
          afterByUid.has(item.itemUid) ? [afterByUid.get(item.itemUid)!.recordStart, afterByUid.get(item.itemUid)!.recordDuration, afterByUid.get(item.itemUid)!.sourceStart, afterByUid.get(item.itemUid)!.sourceDuration] : null,
        ))) continue;
        if (priorEvents.length !== candidate.manifest.events.filter((event) => event.kind !== "script_marker").length) continue;
        matches.push({ ...edit, expectedSequenceVersion: row.primaryVisualSequence.version });
      }
    }
  }
  return matches;
}

function inferTrimCase(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2, input: ParsedCase, pristineItems: Map<string, ItemV1>): RevisionCommandsV2["trim"][] {
  const matches: RevisionCommandsV2["trim"][] = [];
  const blocks = document.activeDraft.blocks.filter((block) => block.type === "visual_only" && block.payload.kind === "visual" && block.payload.pictureKind === "clip");
  for (const block of blocks) {
    if (block.type !== "visual_only" || block.payload.kind !== "visual" || block.payload.pictureKind !== "clip") continue;
    const authored = compileForDocument(document, dependencies).manifest.events.filter((event) => event.provenance.blockId === block.id && (event.kind === "primary_visual" || event.kind === "source_audio"));
    if (authored.length !== 2 || new Set(authored.map((event) => event.kind)).size !== 2) continue;
    const videoEvent = authored.find((event) => event.kind === "primary_visual");
    const audioEvent = authored.find((event) => event.kind === "source_audio");
    const video = videoEvent ? pristineItems.get(videoEvent.eventId) : undefined;
    const audio = audioEvent ? pristineItems.get(audioEvent.eventId) : undefined;
    if (video === undefined || audio === undefined) continue;
    if (video.kind !== "video" || audio.kind !== "audio" || video.recordStart !== audio.recordStart || video.recordDuration !== audio.recordDuration ||
      !equal(video.linkedItemUids, [audio.itemUid]) || !equal(audio.linkedItemUids, [video.itemUid])) continue;
    const afterByUid = new Map(input.edited.geometry.items.map((item) => [item.itemUid, item]));
    const videoAfter = afterByUid.get(video.itemUid); const audioAfter = afterByUid.get(audio.itemUid);
    if (!videoAfter || !audioAfter) continue;
    const delta = video.recordDuration - videoAfter.recordDuration;
    if (delta <= 0 || audio.recordDuration - audioAfter.recordDuration !== delta || videoAfter.recordStart !== video.recordStart ||
      audioAfter.recordStart !== audio.recordStart || videoAfter.sourceStart !== video.sourceStart || audioAfter.sourceStart !== audio.sourceStart ||
      videoAfter.sourceDuration !== videoAfter.recordDuration || audioAfter.sourceDuration !== audioAfter.recordDuration) continue;
    const selected = block.visualOnlyTiming.selectedSourceRange;
    if (!selected || selected.durationFrames <= delta) continue;
    const command = {
      blockId: block.id,
      expectedBlockVersion: block.version,
      expectedSelectedRange: { startFrame: selected.startFrame, durationFrames: selected.durationFrames },
      durationFrames: selected.durationFrames - delta,
    };
    const commands: RevisionCommandsV2 = { boundary: null, trim: command, omission: null };
    let stage: ReturnType<typeof prepareRevisionInputsV2>;
    try { stage = prepareRevisionInputsV2(document, dependencies, commands, exactPreparedMediaForTrim(dependencies, block.id, command.durationFrames)); } catch { continue; }
    const revisedDependencies = dependenciesForDocument(stage.document, stage.dependencies);
    const candidate = compileTimelineV2(stage.document, revisedDependencies);
    if (!candidate.ok || candidate.report.status !== "ready" || candidate.manifest.timeline.durationFrames !== input.edited.geometry.extentFrames ||
      input.pristine.geometry.extentFrames - delta !== input.edited.geometry.extentFrames) continue;
    if (!matchManifestGeometry(candidate.manifest, input.pristine.geometry, input.edited.geometry, { trimFrames: delta })) continue;
    matches.push(command);
  }
  return matches;
}

type Frac = { n: bigint; d: bigint };
const frac = (n: bigint | number, d: bigint | number = 1n): Frac => ({ n: BigInt(n), d: BigInt(d) });
const fracAdd = (a: Frac, b: Frac): Frac => frac(a.n * b.d + b.n * a.d, a.d * b.d);
const fracSub = (a: Frac, b: Frac): Frac => frac(a.n * b.d - b.n * a.d, a.d * b.d);
const fracCompare = (a: Frac, b: Frac): number => { const delta = a.n * b.d - b.n * a.d; return delta < 0n ? -1 : delta > 0n ? 1 : 0; };
const fracFloor = (a: Frac): bigint => (a.n >= 0n ? a.n / a.d : -((-a.n + a.d - 1n) / a.d));
const fracCeil = (a: Frac): bigint => -fracFloor(frac(-a.n, a.d));
const timeSamples = (time: RationalTime, sampleRate: number): Frac => frac(BigInt(time.numerator) * BigInt(sampleRate), time.denominator);

type BoundaryMark = NarrationBoundaryEvidenceV1["tokens"][number];
interface WordEnvelope {
  reasons: string[];
  start: { low: Frac; high: Frac } | null;
  end: { low: Frac; high: Frac } | null;
}

/**
 * Safe cut envelopes around one measured word, in narration-row PCM samples. Mirrors
 * python narration/omission_envelope.py: the cut may start between the left neighbour's
 * audible end and the word's onset and may end between the word's audible end and the
 * right neighbour's onset, each bound moved inward by the declared uncertainty. A missing
 * measured edge (connected speech) or a collapsed envelope makes the word unselectable.
 */
function wordEnvelope(marks: readonly BoundaryMark[], index: number, sampleRate: number, durationSamples: number,
  onsetUncertainty: Frac, endUncertainty: Frac): WordEnvelope {
  const selected = marks[index]!; const left = index > 0 ? marks[index - 1]! : null; const right = index + 1 < marks.length ? marks[index + 1]! : null;
  const reasons: string[] = [];
  if (!selected.onset) reasons.push(`${selected.quotedText} has no measured onset`);
  if (!selected.audibleEnd) reasons.push(`${selected.quotedText} has no measured audible end (connected speech)`);
  if (left !== null && !left.audibleEnd) reasons.push(`left neighbour ${left.quotedText} has no measured audible end (connected speech)`);
  if (right !== null && !right.onset) reasons.push(`right neighbour ${right.quotedText} has no measured onset`);
  if (reasons.length > 0) return { reasons, start: null, end: null };
  const startLow = left === null ? frac(0) : fracAdd(timeSamples(left.audibleEnd!, sampleRate), endUncertainty);
  const startHigh = fracSub(timeSamples(selected.onset!, sampleRate), onsetUncertainty);
  const endLow = fracAdd(timeSamples(selected.audibleEnd!, sampleRate), endUncertainty);
  const endHigh = right === null ? frac(durationSamples) : fracSub(timeSamples(right.onset!, sampleRate), onsetUncertainty);
  if (fracCompare(startHigh, startLow) <= 0) reasons.push(`cut start envelope of ${selected.quotedText} collapses under the declared uncertainty`);
  if (fracCompare(endHigh, endLow) <= 0) reasons.push(`cut end envelope of ${selected.quotedText} collapses under the declared uncertainty`);
  if (reasons.length > 0) return { reasons, start: null, end: null };
  return { reasons, start: { low: startLow, high: startHigh }, end: { low: endLow, high: endHigh } };
}

interface WordSelection { index: number; envelope: { start: { low: Frac; high: Frac }; end: { low: Frac; high: Frac } } }

function insideEnvelope(sample: bigint, range: { low: Frac; high: Frac }): boolean {
  const value = frac(sample);
  return fracCompare(value, range.low) >= 0 && fracCompare(value, range.high) <= 0;
}

/** The one measured word whose envelopes contain the observed cut; refuses partial, straddling, ambiguous and connected cuts. */
function selectOmittedWord(marks: readonly BoundaryMark[], sampleRate: number, durationSamples: number, onsetUncertainty: Frac,
  endUncertainty: Frac, cutStart: number, cutEnd: number): WordSelection {
  const start = BigInt(cutStart); const end = BigInt(cutEnd);
  const hits: WordSelection[] = [];
  const unmeasured: string[] = [];
  for (let index = 0; index < marks.length; index++) {
    const envelope = wordEnvelope(marks, index, sampleRate, durationSamples, onsetUncertainty, endUncertainty);
    if (envelope.start === null || envelope.end === null) {
      const onset = marks[index]!.onset;
      const nextOnset = marks.slice(index + 1).find((mark) => mark.onset)?.onset;
      const spanStart = onset ? timeSamples(onset, sampleRate) : null;
      const spanEnd = nextOnset ? timeSamples(nextOnset, sampleRate) : frac(durationSamples);
      if (spanStart !== null && fracCompare(frac(start), spanStart) >= 0 && fracCompare(frac(start), spanEnd) < 0) unmeasured.push(envelope.reasons.join("; "));
      continue;
    }
    if (insideEnvelope(start, envelope.start) && insideEnvelope(end, envelope.end)) hits.push({ index, envelope: { start: envelope.start, end: envelope.end } });
  }
  fact(hits.length <= 1, "ambiguous omission cut: more than one measured word is compatible with it");
  fact(hits.length === 1, "omission cut does not isolate exactly one measured word between its neighbours (partial-word, multi-word or neighbour-straddling cut)" +
    (unmeasured.length > 0 ? `; the cut touches a word without a safe measured envelope: ${unmeasured.join("; ")}` : ""));
  return hits[0]!;
}

/** The omission transform joins a previous and a following token, so inference refuses first/last tokens the same way. */
export function requireInteriorOmissionIndex(index: number, tokenCount: number): void {
  fact(index > 0 && index < tokenCount - 1, "first or last narration token omission is unsupported; only interior tokens can be omitted");
}

function narrationEvidence(dependencies: CompilerDependenciesV2, blockId: string): NarrationBoundaryEvidenceV1 {
  const evidence = (dependencies.narrationBoundaryEvidence ?? []).filter((row) => row.blockId === blockId);
  fact(evidence.length === 1, "narration boundary evidence required");
  return evidence[0]!;
}

const OMISSION_SUPPORT_FIELDS = ["schemaVersion", "lane", "caseId", "documentHash", "dependenciesHash", "blockId", "blockRevision", "method",
  "selectedTokenId", "leftNeighborTokenId", "rightNeighborTokenId", "boundaryEvidenceHash", "measurementArtifactHash", "audioSha256", "timingHash",
  "onsetUncertainty", "audibleEndUncertainty", "nativeFrameOrigin", "pcmSampleOrigin", "cutRecordFrames", "cutSourceFrames", "cutSamples",
  "cutStartEnvelope", "cutEndEnvelope", "pristineGeometryRawSha256", "editedGeometryRawSha256", "pristineComparisonRawSha256",
  "editedComparisonRawSha256", "pairRawSha256"];

function inferOmissionCase(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2, input: ParsedCase, documentHash: string, dependenciesHash: string): { omission: QualificationOutputInferenceV1["omission"]; evidence: QualificationOutputOmissionSupportV2 } | null {
  if (input.source.omissionSupport === null) return null;
  const supplied = shape(input.source.omissionSupport, OMISSION_SUPPORT_FIELDS, "omission support") as unknown as QualificationOutputOmissionSupportV2;
  fact(supplied.schemaVersion === "qualification-output-omission-support/v2" && supplied.lane === LANE && supplied.caseId === input.source.caseId &&
    supplied.documentHash === documentHash && supplied.dependenciesHash === dependenciesHash, "stale omission support binding");
  for (const key of ["audioSha256", "timingHash", "pristineGeometryRawSha256", "editedGeometryRawSha256",
    "pristineComparisonRawSha256", "editedComparisonRawSha256", "pairRawSha256"] as const) bareHash(supplied[key]);
  fact(supplied.pristineGeometryRawSha256 === input.pristine.rawSha256 && supplied.editedGeometryRawSha256 === input.edited.rawSha256 &&
    supplied.pristineComparisonRawSha256 === input.pristineComparison.rawSha256 && supplied.editedComparisonRawSha256 === input.editedComparison.rawSha256 &&
    input.source.pairJson !== null && supplied.pairRawSha256 === rawSha256(input.source.pairJson), "omission support raw evidence pins differ");
  const row = document.activeDraft.blocks.find((block) => block.type === "narration" && block.id === supplied.blockId);
  fact(row?.type === "narration" && row.version === supplied.blockRevision, "omission support names a stale or unknown narration row");
  const derived = deriveOmissionSupport(document, dependencies, input, row, documentHash, dependenciesHash);
  fact(equal(derived, supplied), "omission support differs from the record derived from measured evidence and the observed cut");
  return { omission: { blockId: row.id, blockRevision: row.version, tokenIds: [derived.selectedTokenId], evidenceHash: sha256CanonicalJson(derived) }, evidence: derived };
}

/**
 * Host-facing derivation: the support for the one narration row whose pristine item the
 * observed edit split into two. The host passes the raw evidence with omissionSupport null.
 */
export function deriveOmissionSupportV2(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2, evidence: QualificationOutputObservationBatchV1): QualificationOutputOmissionSupportV2 {
  fact(validateScriptDocumentV2(document).valid, "invalid baseline script document");
  const checked = validateBatch(evidence, document, dependencies);
  fact(checked.cases.length === 1 && checked.cases[0]!.source.omissionSupport === null, "one observation case without a support record required");
  const input = checked.cases[0]!;
  const split = compileForDocument(document, dependencies).manifest.events.filter((event) => event.kind === "narration" &&
    input.pristine.geometry.items.filter((item) => item.eventId === event.eventId).length === 1 &&
    input.edited.geometry.items.filter((item) => item.eventId === event.eventId).length === 2);
  fact(split.length === 1, "the observed edit does not split exactly one narration item");
  const row = document.activeDraft.blocks.find((block) => block.type === "narration" && block.id === split[0]!.provenance.blockId);
  fact(row?.type === "narration", "split narration event names an unknown row");
  return deriveOmissionSupport(document, dependencies, input, row, checked.documentHash, checked.dependenciesHash);
}

function deriveOmissionSupport(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2, input: ParsedCase, row: Extract<ScriptDocumentV2["activeDraft"]["blocks"][number], { type: "narration" }>, documentHash: string, dependenciesHash: string): QualificationOutputOmissionSupportV2 {
  const pairJson = input.source.pairJson;
  fact(pairJson !== null, "omission support requires the authenticated pair comparison");
  const boundary = narrationEvidence(dependencies, row.id);
  const problem = boundaryEvidenceProblemV2(row, boundary);
  fact(problem === null, `narration boundary evidence refused: ${problem?.message}`);
  const verification = boundary.verification;
  fact(verification.method === "measured_audio_boundaries/v1", "measured narration boundary evidence required for omission inference");
  fact(boundary.tokens.length === row.tokens.length && boundary.tokens.every((mark, index) => mark.tokenId === row.tokens[index]!.id),
    "measured evidence must cover every frozen token of the row in order");
  const audio = boundary.audio;
  fact(audio.sampleRate === 48000 && audio.channels === 1 && audio.durationSamples > 0, "48 kHz mono narration audio evidence required");

  const event = compileForDocument(document, dependencies).manifest.events.filter((item) => item.kind === "narration" && item.provenance.blockId === row.id);
  fact(event.length === 1, "selected narration event is ambiguous");
  const original = input.pristine.geometry.items.filter((item) => item.eventId === event[0]!.eventId);
  const segments = input.edited.geometry.items.filter((item) => item.eventId === event[0]!.eventId).sort((a, b) => a.recordStart - b.recordStart);
  fact(original.length === 1 && segments.length === 2 && segments.every((item) => item.itemUid !== original[0]!.itemUid), "C must split one narration item into two new UIDs");
  const prior = original[0]!; const [left, right] = segments as [ItemV1, ItemV1];
  const gapRecordStart = left.recordStart + left.recordDuration; const gapRecordEnd = right.recordStart;
  const gapSourceStart = left.sourceStart + left.sourceDuration; const gapSourceEnd = right.sourceStart;
  fact(left.recordStart === prior.recordStart && right.recordStart > gapRecordStart && right.recordStart < prior.recordStart + prior.recordDuration &&
    right.recordStart + right.recordDuration === prior.recordStart + prior.recordDuration && left.sourceStart === prior.sourceStart &&
    right.sourceStart + right.sourceDuration === prior.sourceStart + prior.sourceDuration && gapRecordEnd - gapRecordStart > 0 &&
    gapRecordEnd - gapRecordStart === gapSourceEnd - gapSourceStart && gapSourceEnd > gapSourceStart,
  "C split is not a bounded non-ripple whole-frame lift");
  for (const segment of segments) fact(sameStableItem({ ...prior, itemUid: segment.itemUid }, segment), "C split changed source, track, link or control identity");
  const eventIds = new Set(input.pristine.geometry.items.map((item) => item.eventId));
  const untouched = input.edited.geometry.items.filter((item) => item.eventId !== event[0]!.eventId);
  fact(untouched.length === input.pristine.geometry.items.length - 1 && untouched.every((item) => {
    const old = input.pristine.geometry.items.find((priorItem) => priorItem.itemUid === item.itemUid);
    return old !== undefined && sameStableItem(old, item) && equal([old.recordStart, old.recordDuration, old.sourceStart, old.sourceDuration],
      [item.recordStart, item.recordDuration, item.sourceStart, item.sourceDuration]);
  }) && eventIds.has(event[0]!.eventId), "C cut caused ripple or unrelated geometry change");

  // Sample origins come from the authenticated PCM source binding, never from the support record.
  const entryFor = (parsed: ParsedGeometry) => {
    const entries = list(parsed.inputBinding.sourceEntries, 16).filter((entry) => record(entry).sourceId === prior.sourceId);
    fact(entries.length === 1, "narration item has no unique bound PCM source entry");
    return record(entries[0]);
  };
  const entry = entryFor(input.pristine);
  fact(equal(entry, entryFor(input.edited)), "narration PCM source binding differs between pristine and edited captures");
  const nativeFrameOrigin = integer(entry.nativeFrameOrigin, "native frame origin");
  const pcmSampleOrigin = integer(entry.pcmSampleOrigin, "PCM sample origin");
  fact(integer(entry.sampleRate) === audio.sampleRate && integer(entry.durationSamples) >= audio.durationSamples, "bound PCM source is shorter than the measured narration audio");
  fact(entry.pcmMode === "wav-direct", "measured-evidence omission requires a wav-direct narration source");
  fact(entry.pcmFileSha256 === bare(boundary.audioHash), "bound PCM file differs from the measured narration audio");
  fact(gapSourceStart >= nativeFrameOrigin, "cut precedes native frame origin");
  const cutStart = integer((gapSourceStart - nativeFrameOrigin) * FRAME_SAMPLES + pcmSampleOrigin, "cut start sample");
  const cutEnd = integer((gapSourceEnd - nativeFrameOrigin) * FRAME_SAMPLES + pcmSampleOrigin, "cut end sample");
  fact(cutEnd - cutStart === (gapRecordEnd - gapRecordStart) * FRAME_SAMPLES && cutEnd <= audio.durationSamples, "cut escapes the measured narration audio");

  const onsetUncertainty = timeSamples(verification.onsetUncertainty, audio.sampleRate);
  const endUncertainty = timeSamples(verification.audibleEndUncertainty, audio.sampleRate);
  const selection = selectOmittedWord(boundary.tokens, audio.sampleRate, audio.durationSamples, onsetUncertainty, endUncertainty, cutStart, cutEnd);
  const marks = boundary.tokens;
  requireInteriorOmissionIndex(selection.index, marks.length);
  const selected = marks[selection.index]!;
  const derived: QualificationOutputOmissionSupportV2 = {
    schemaVersion: "qualification-output-omission-support/v2", lane: LANE, caseId: input.source.caseId, documentHash, dependenciesHash,
    blockId: row.id, blockRevision: row.version, method: "measured_audio_boundaries/v1", selectedTokenId: selected.tokenId,
    leftNeighborTokenId: marks[selection.index - 1]?.tokenId ?? null, rightNeighborTokenId: marks[selection.index + 1]?.tokenId ?? null,
    boundaryEvidenceHash: sha256CanonicalJson(boundary), measurementArtifactHash: verification.measurementArtifactHash,
    audioSha256: bare(boundary.audioHash), timingHash: bare(boundary.timingHash),
    onsetUncertainty: verification.onsetUncertainty, audibleEndUncertainty: verification.audibleEndUncertainty,
    nativeFrameOrigin, pcmSampleOrigin,
    cutRecordFrames: { startFrame: gapRecordStart, endFrame: gapRecordEnd }, cutSourceFrames: { startFrame: gapSourceStart, endFrame: gapSourceEnd },
    cutSamples: { startSample: cutStart, endSample: cutEnd },
    cutStartEnvelope: { minSample: Number(fracCeil(selection.envelope.start.low)), maxSample: Number(fracFloor(selection.envelope.start.high)) },
    cutEndEnvelope: { minSample: Number(fracCeil(selection.envelope.end.low)), maxSample: Number(fracFloor(selection.envelope.end.high)) },
    pristineGeometryRawSha256: input.pristine.rawSha256, editedGeometryRawSha256: input.edited.rawSha256,
    pristineComparisonRawSha256: input.pristineComparison.rawSha256, editedComparisonRawSha256: input.editedComparison.rawSha256,
    pairRawSha256: rawSha256(pairJson),
  };
  return derived;
}

function inferCase(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2, input: ParsedCase,
  baseline: ReturnType<typeof compileForDocument>, pristineItems: Map<string, ItemV1>, documentHash: string, dependenciesHash: string): { kind: CaseKind; boundary: RevisionCommandsV2["boundary"]; trim: RevisionCommandsV2["trim"]; omission: QualificationOutputInferenceV1["omission"] } {
  const possible: { kind: CaseKind; boundary: RevisionCommandsV2["boundary"]; trim: RevisionCommandsV2["trim"]; omission: QualificationOutputInferenceV1["omission"] }[] = [];
  if (input.source.omissionSupport === null) {
    for (const boundary of inferBoundaryCase(document, dependencies, input, baseline)) possible.push({ kind: "A", boundary, trim: null, omission: null });
  }
  if (input.source.omissionSupport === null) {
    for (const trim of inferTrimCase(document, dependencies, input, pristineItems)) possible.push({ kind: "B", boundary: null, trim, omission: null });
  }
  const omission = inferOmissionCase(document, dependencies, input, documentHash, dependenciesHash);
  if (omission !== null) possible.push({ kind: "C", boundary: null, trim: null, omission: omission.omission });
  fact(possible.length === 1, "observation must yield one unique supported A/B/C proposal");
  const selected = possible[0]!;
  if (selected.kind !== "B") fact(input.pristine.geometry.extentFrames === input.edited.geometry.extentFrames, "only an authenticated linked trim may shorten the capture extent");
  if (selected.kind === "A") {
    fact(input.pair === null && input.source.audioEquality !== null, "A picture-only move requires byte-identical predicted/decoded audio evidence");
  } else {
    fact(input.pair !== null && input.source.audioEquality === null, "audio-changing B/C requires pair discriminability only");
  }
  if (selected.kind !== "C") fact(input.source.omissionSupport === null, "unexpected omission support outside C");
  return selected;
}

/** Derive supported A/B/C proposals only from complete host-authenticated raw evidence. */
export function inferQualificationOutputV2(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2, evidence: QualificationOutputObservationBatchV1): QualificationOutputInferenceV1 {
  fact(validateScriptDocumentV2(document).valid, "invalid baseline script document");
  const checked = validateBatch(evidence, document, dependencies);
  const baseline = compileForDocument(document, dependencies);
  fact(baseline.manifest.timeline.durationFrames === checked.cases[0]!.pristine.geometry.extentFrames, "compiled baseline extent differs from observed geometry");
  const cases = checked.cases.map((input) => {
    const items = checkBaselineGeometry(input.pristine.geometry, baseline.manifest);
    fact(input.pristine.geometry.extentFrames === checked.cases[0]!.pristine.geometry.extentFrames, "case baseline extent differs");
    return { input, items, inference: inferCase(document, dependencies, input, baseline, items, checked.documentHash, checked.dependenciesHash) };
  });
  const kinds = cases.map(({ inference }) => inference.kind);
  fact(new Set(kinds).size === kinds.length, "duplicate A/B/C inference");
  const boundaries = cases.flatMap(({ inference }) => inference.boundary ? [inference.boundary] : []);
  const trims = cases.flatMap(({ inference }) => inference.trim ? [inference.trim] : []);
  const omissions = cases.flatMap(({ inference }) => inference.omission ? [inference.omission] : []);
  fact(boundaries.length <= 1 && trims.length <= 1 && omissions.length <= 1, "duplicate semantic revision command");
  const commands: RevisionCommandsV2 = { boundary: boundaries[0] ?? null, trim: trims[0] ?? null, omission: null };
  const body = {
    schemaVersion: "qualification-output-inference/v1" as const, lane: LANE,
    documentHash: checked.documentHash, dependenciesHash: checked.dependenciesHash,
    evidenceHash: sha256CanonicalJson(checked.batch), caseEvidenceHashes: checked.cases.map((c) => sha256CanonicalJson(c.source)),
    commands, omission: omissions[0] ?? null, caseKinds: kinds,
    internalControls: "unverified" as const, geometryStability: "not_claimed" as const,
    controlStability: "not_claimed" as const, futureAuthority: false as const,
  };
  return { ...body, inferenceHash: sha256CanonicalJson(body) };
}

function validateDecision(value: unknown, proposalHash: string, history: string[]): QualificationOutputDecisionV1 {
  const decision = shape(value, ["schemaVersion", "proposalHash", "historyHash", "outcome"], "explicit decision") as unknown as QualificationOutputDecisionV1;
  fact(decision.schemaVersion === "qualification-output-decision/v1" && decision.proposalHash === proposalHash &&
    decision.historyHash === sha256CanonicalJson(history) && (decision.outcome === "accept" || decision.outcome === "reject"), "stale or unsupported explicit decision");
  fact(Array.isArray(history) && history.every((hash) => typeof hash === "string" && /^sha256:[a-f0-9]{64}$/u.test(hash)) &&
    new Set(history).size === history.length && !history.includes(proposalHash), "duplicate or malformed decision history");
  return decision;
}

function acceptedCommands(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2, inference: QualificationOutputInferenceV1,
  decision: QualificationOutputDecisionV1, preparedMedia: PreparedMediaBindingV1[]): RevisionCommandsV2 {
  fact(decision.outcome === "accept", "rejected inference cannot stage a revision");
  const commands: RevisionCommandsV2 = structuredClone(inference.commands);
  if (inference.omission !== null) {
    const beforeOmission = commands.boundary !== null || commands.trim !== null
      ? prepareRevisionInputsV2(document, dependencies, commands, preparedMedia)
      : { document };
    commands.omission = {
      schemaVersion: "issue-189-v2-accepted-omission/v1",
      expectedDocumentHash: sha256CanonicalJson(beforeOmission.document),
      ...inference.omission,
      decisionHash: sha256CanonicalJson(decision),
    };
  }
  // Validate the selected command set through the accepted canonical transform.
  prepareRevisionInputsV2(document, dependencies, commands, preparedMedia);
  return commands;
}

function newRegenerationRequest(core: NonNullable<ReturnType<typeof prepareRevisionInputsV2>["regeneration"]>): QualificationOutputRegenerationRequestV1 {
  const { blockId, blockRevision, text, textHash, revisedDocumentHash, evidenceHash, decisionHash } = core;
  return { schemaVersion: "qualification-output-regeneration-request/v1", lane: LANE, policy: "replace_whole_row", blockId, blockRevision,
    text, textHash, revisedDocumentHash, evidenceHash, decisionHash };
}

export function stageQualificationOutputV2(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2,
  evidence: QualificationOutputObservationBatchV1, decisionValue: unknown, history: string[], preparedMedia: PreparedMediaBindingV1[] = []) {
  const inference = inferQualificationOutputV2(document, dependencies, evidence);
  const decision = validateDecision(decisionValue, inference.inferenceHash, history);
  if (decision.outcome === "reject") return {
    schemaVersion: "qualification-output-stage/v1" as const, lane: LANE, inference, decision,
    decisionHash: sha256CanonicalJson(decision), outcome: "reject" as const, document, dependencies, regeneration: null,
    history: [...history, inference.inferenceHash], internalControls: "unverified" as const, geometryStability: "not_claimed" as const,
    controlStability: "not_claimed" as const, futureAuthority: false as const,
  };
  const commands = acceptedCommands(document, dependencies, inference, decision, preparedMedia);
  const stage = prepareRevisionInputsV2(document, dependencies, commands, preparedMedia);
  return {
    schemaVersion: "qualification-output-stage/v1" as const, lane: LANE, inference, decision,
    decisionHash: sha256CanonicalJson(decision), outcome: "accept" as const, document: stage.document, dependencies: stage.dependencies,
    regeneration: stage.regeneration ? newRegenerationRequest(stage.regeneration) : null,
    history: [...history, inference.inferenceHash], internalControls: "unverified" as const, geometryStability: "not_claimed" as const,
    controlStability: "not_claimed" as const, futureAuthority: false as const,
  };
}

function checkedInferenceDecision(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2,
  evidence: QualificationOutputObservationBatchV1, value: unknown, history: string[]) {
  const inference = inferQualificationOutputV2(document, dependencies, evidence);
  const decision = validateDecision(value, inference.inferenceHash, history);
  fact(decision.outcome === "accept", "only an accepted inference can create a revision proposal");
  return { inference, decision };
}

/** The compiler ceils a regenerated row to whole frames, so only the audio format must be exact. */
function requireReplacementAudioFormat(handoff: RowHandoffV2): void {
  const audio = record(handoff.boundaryEvidence.audio, "fresh replacement audio");
  fact(integer(audio.sampleRate, "replacement audio sample rate") === 48000 && integer(audio.channels, "replacement audio channels") === 1 &&
    integer(audio.durationSamples, "replacement audio duration samples") > 0, "whole-row replacement requires positive-length 48 kHz mono audio");
}

export function createQualificationOutputProposalV2(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2,
  evidence: QualificationOutputObservationBatchV1, inferenceDecisionValue: unknown, inferenceHistory: string[],
  preparedMedia: PreparedMediaBindingV1[], handoff: RowHandoffV2 | null): QualificationOutputProposalV1 {
  const { inference, decision } = checkedInferenceDecision(document, dependencies, evidence, inferenceDecisionValue, inferenceHistory);
  if (handoff !== null) requireReplacementAudioFormat(handoff);
  const commands = acceptedCommands(document, dependencies, inference, decision, preparedMedia);
  const request: RevisionRequestV2 = { commands, preparedMedia, handoff };
  const revision = createRevisionProposalV2(document, dependencies, request);
  const body = {
    schemaVersion: "qualification-output-proposal/v1" as const, lane: LANE, inference, inferenceDecision: decision,
    inferenceHistory: [...inferenceHistory], request, revision,
    internalControls: "unverified" as const, geometryStability: "not_claimed" as const,
    controlStability: "not_claimed" as const, futureAuthority: false as const,
  };
  return { ...body, proposalHash: sha256CanonicalJson(body) };
}

export function decideQualificationOutputV2(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2,
  evidence: QualificationOutputObservationBatchV1, candidateValue: unknown, decisionValue: unknown, history: string[]) {
  const candidate = shape(candidateValue, PROPOSAL_FIELDS, "qualification output proposal") as unknown as QualificationOutputProposalV1;
  fact(candidate.schemaVersion === "qualification-output-proposal/v1" && candidate.lane === LANE, "wrong proposal namespace/lane");
  const decision = validateDecision(decisionValue, candidate.proposalHash, history);
  const rebuilt = createQualificationOutputProposalV2(document, dependencies, evidence, candidate.inferenceDecision,
    candidate.inferenceHistory, candidate.request.preparedMedia, candidate.request.handoff);
  fact(equal(rebuilt, candidate) && decision.proposalHash === rebuilt.proposalHash, "proposal/evidence/revision identity changed");
  const coreDecision: RevisionDecisionV2 = {
    schemaVersion: "issue-202-v2-decision/v1", proposalHash: rebuilt.revision.proposalHash,
    historyHash: sha256CanonicalJson([]), outcome: decision.outcome,
  };
  const result = decideRevisionV2(document, dependencies, rebuilt.revision, coreDecision, []);
  return {
    schemaVersion: "qualification-output-decision-result/v1" as const, lane: LANE, proposalHash: rebuilt.proposalHash,
    outcome: decision.outcome, document: result.document, dependencies: result.dependencies,
    decisionHash: sha256CanonicalJson(decision), history: [...history, rebuilt.proposalHash],
    internalControls: "unverified" as const, geometryStability: "not_claimed" as const,
    controlStability: "not_claimed" as const, futureAuthority: false as const,
  };
}

export function parseQualificationOutputPureRequest(raw: Uint8Array): QualificationOutputPureRequestV1 {
  fact(raw.byteLength <= MAX_JSON_BYTES, "bounded pure request required");
  const decoded = new TextDecoder("utf-8", { fatal: true }).decode(raw);
  const request = shape(parseRaw(decoded, "pure request"), ["schemaVersion", "mode", "document", "dependencies", "evidence", "preparedMedia", "handoff", "inferenceDecision", "inferenceHistory", "candidate", "decision", "history"], "qualification output pure request") as unknown as QualificationOutputPureRequestV1;
  fact(request.schemaVersion === "qualification-output-pure-request/v1" && ["baseline", "infer", "derive_omission", "stage", "proposal", "decide"].includes(request.mode), "unsupported pure request");
  for (const rows of [request.inferenceHistory, request.history]) {
    fact(Array.isArray(rows) && rows.every((hash) => typeof hash === "string" && /^sha256:[a-f0-9]{64}$/u.test(hash)) && new Set(rows).size === rows.length, "malformed replay history");
  }
  fact(Array.isArray(request.preparedMedia) && (request.evidence === null || typeof request.evidence === "object") &&
    (request.handoff === null || typeof request.handoff === "object") && (request.candidate === null || typeof request.candidate === "object") &&
    (request.inferenceDecision === null || typeof request.inferenceDecision === "object") && (request.decision === null || typeof request.decision === "object"), "malformed pure request fields");
  checkJsonTree(request);
  const emptyHistory = (rows: unknown) => Array.isArray(rows) && rows.length === 0;
  if (request.mode === "baseline") {
    fact(request.evidence === null && request.preparedMedia.length === 0 && request.handoff === null && request.inferenceDecision === null &&
      emptyHistory(request.inferenceHistory) && request.candidate === null && request.decision === null && emptyHistory(request.history),
    "baseline request contains unused proposal fields");
  } else if (request.mode === "infer" || request.mode === "derive_omission") {
    fact(request.evidence !== null && request.preparedMedia.length === 0 && request.handoff === null && request.inferenceDecision === null &&
      emptyHistory(request.inferenceHistory) && request.candidate === null && request.decision === null && emptyHistory(request.history),
    "inference request contains unused decision/stage fields");
  } else if (request.mode === "stage") {
    fact(request.evidence !== null && request.inferenceDecision !== null && request.handoff === null && request.candidate === null &&
      request.decision === null && emptyHistory(request.history), "stage request contains unused proposal/decision fields");
  } else if (request.mode === "proposal") {
    fact(request.evidence !== null && request.inferenceDecision !== null && request.candidate === null && request.decision === null &&
      emptyHistory(request.history), "proposal request contains unused candidate/decision fields");
  } else {
    fact(request.evidence !== null && request.inferenceDecision === null && emptyHistory(request.inferenceHistory) &&
      request.candidate !== null && request.decision !== null, "decision request requires a candidate and explicit decision");
    const candidate = shape(request.candidate, PROPOSAL_FIELDS, "qualification output proposal");
    const candidateRequest = shape(candidate.request, ["commands", "preparedMedia", "handoff"], "candidate revision request");
    fact(equal(request.preparedMedia, candidateRequest.preparedMedia) && equal(request.handoff, candidateRequest.handoff),
      "decision request/candidate material differs");
  }
  return request;
}

export function runQualificationOutputPureRequest(request: QualificationOutputPureRequestV1): unknown {
  const { document, dependencies } = request;
  if (request.mode === "baseline") {
    const compiled = compileForDocument(document, dependencies);
    return { documentHash: sha256CanonicalJson(document), dependenciesHash: sha256CanonicalJson(dependencies),
      documentJson: canonicalJson(document), manifest: compiled.manifest };
  }
  fact(request.evidence !== null, "host-verified output evidence required");
  if (request.mode === "derive_omission") return deriveOmissionSupportV2(document, dependencies, request.evidence);
  if (request.mode === "infer") return inferQualificationOutputV2(document, dependencies, request.evidence);
  if (request.mode === "stage") {
    fact(request.inferenceDecision !== null, "explicit inference decision required");
    return stageQualificationOutputV2(document, dependencies, request.evidence, request.inferenceDecision, request.inferenceHistory, request.preparedMedia);
  }
  if (request.mode === "proposal") {
    fact(request.inferenceDecision !== null, "explicit accepted inference decision required");
    return createQualificationOutputProposalV2(document, dependencies, request.evidence, request.inferenceDecision, request.inferenceHistory,
      request.preparedMedia, request.handoff);
  }
  fact(request.candidate !== null && request.decision !== null, "candidate and explicit revision decision required");
  fact(equal(request.preparedMedia, request.candidate.request.preparedMedia) && equal(request.handoff, request.candidate.request.handoff), "decision request/candidate material differs");
  return decideQualificationOutputV2(document, dependencies, request.evidence, request.candidate, request.decision, request.history);
}

