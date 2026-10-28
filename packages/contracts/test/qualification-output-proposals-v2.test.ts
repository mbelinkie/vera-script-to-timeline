import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { sha256CanonicalJson } from "../src/compiler-core.js";
import { compileTimelineV2 } from "../src/compiler-core-v2.js";
import type { NarrationBlockV2, NarrationBoundaryEvidenceV1, ScriptDocumentV2 } from "../src/generated/contracts-v2.js";
import { applyAcceptedOmissionV2 } from "../src/issue-189-v2-omission.js";
import type { RowHandoffV2 } from "../src/issue-189-v2-replacement.js";
import {
  decideQualificationOutputV2,
  createQualificationOutputProposalV2,
  deriveOmissionSupportV2,
  inferQualificationOutputV2,
  runQualificationOutputPureRequest,
  parseQualificationOutputPureRequest,
  stageQualificationOutputV2,
  type QualificationOutputObservationBatchV1,
  type QualificationOutputObservationCaseV1,
  type QualificationOutputAudioEqualityV1,
  requireInteriorOmissionIndex,
} from "../src/qualification-output-proposals-v2.js";
import { edits, hash, id, observations, rational, specimen, timing, type FakeRaw } from "./issue-192-case.js";

const bare = (value: string) => value.replace(/^sha256:/u, "");
const rawHash = (value: string) => createHash("sha256").update(value, "utf8").digest("hex");
function pythonSorted(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(pythonSorted);
  if (value !== null && typeof value === "object") {
    const output: Record<string, unknown> = {};
    for (const key of Object.keys(value).sort()) output[key] = pythonSorted((value as Record<string, unknown>)[key]);
    return output;
  }
  return value;
}
const pythonHash = (value: unknown) => rawHash(JSON.stringify(pythonSorted(value)));

interface Origins { nativeFrameOrigin: number; pcmSampleOrigin: number }
function geometryEnvelope(input: ReturnType<typeof specimen>, raw: FakeRaw, phase: "pristine" | "edited", caseId: string,
  executionDiffers = false, origins: Origins = { nativeFrameOrigin: 0, pcmSampleOrigin: 0 }, pcmMode = "wav-direct") {
  const compiled = compileTimelineV2(input.document, input.dependencies);
  if (!compiled.ok || compiled.report.status !== "ready") throw new Error("sanitized baseline compile failed");
  const manifest = compiled.manifest;
  const nativeSourceRows = new Map<string, { sourceId: string; nativeSourceSha256: string }>();
  for (const item of raw.items) nativeSourceRows.set(item.sourceId, { sourceId: item.sourceId, nativeSourceSha256: bare(item.sourceHash) });
  const audioItems = new Map<string, FakeRaw["items"][number]>();
  for (const item of raw.items.filter((row) => row.kind === "audio")) audioItems.set(item.sourceId, item);
  const sourceEntries = [...audioItems].map(([sourceId, item]) => ({
    sourceId, nativeSourceSha256: nativeSourceRows.get(sourceId)!.nativeSourceSha256, pcmMode,
    provenanceReceiptSha256: bare(hash(`entry:${sourceId}:receipt`)), provenancePinsSha256: bare(hash(`entry:${sourceId}:pins`)),
    deliveryDerivationSha256: bare(hash(`entry:${sourceId}:delivery`)), pcmFileSha256: pcmMode === "wav-direct" ? bare(input.dependencies.narrationBoundaryEvidence![0]!.audioHash) : bare(hash(`entry:${sourceId}:pcm-file`)),
    decodedSamplesSha256: bare(hash(`entry:${sourceId}:samples`)), originalBitDepth: 24, channels: 1,
    durationSamples: 4_000_000, sampleRate: 48000,
    pcmMappingSha256: bare(item.sourceHash), ...origins,
  })).sort((a, b) => a.sourceId.localeCompare(b.sourceId));
  const sourceEntriesById = new Map(sourceEntries.map((entry) => [entry.sourceId, entry]));
  const tracks = raw.tracks.map((track) => {
    const sourceTrack = manifest.tracks.find((row) => row.kind === track.kind && row.index === track.index);
    if (!sourceTrack) throw new Error("sanitized track mapping missing");
    return { trackId: sourceTrack.id, kind: track.kind, index: track.index, name: track.name, enabled: track.enabled, locked: track.locked };
  }).sort((a, b) => a.trackId.localeCompare(b.trackId));
  const items = raw.items.map((item) => {
    const event = manifest.events.find((row) => row.eventId === item.eventId);
    if (!event) throw new Error("sanitized event mapping missing");
    const sourceMappingSha256 = item.kind === "video" ? nativeSourceRows.get(item.sourceId)!.nativeSourceSha256 : sourceEntriesById.get(item.sourceId)!.pcmMappingSha256;
    return {
      itemUid: item.itemUid, eventId: item.eventId, sourceId: item.sourceId, mediaUid: item.mediaUid, kind: item.kind,
      trackId: event.trackId, recordStart: item.recordStart, recordDuration: item.recordEnd - item.recordStart,
      sourceStart: item.sourceStart, sourceDuration: item.sourceEnd - item.sourceStart, linkedItemUids: [...item.linkedUids].sort(),
      online: item.online, enabled: item.enabled, speed: item.speed, sourceMappingSha256,
    };
  }).sort((a, b) => a.recordStart - b.recordStart || a.itemUid.localeCompare(b.itemUid));
  const target = { projectName: "Sanitized output specimen", projectUid: "project-215-sanitized", timelineName: "Timeline 215", timelineUid: "timeline-215-sanitized" };
  const hashFields = ["originalDocumentSha256", "originalDependenciesSha256", "executionDocumentSha256", "executionDependenciesSha256", "packageSha256", "preflightSha256",
    "manifestSha256", "reportSha256", "preparationSha256", "hostSourceGraphSha256", "nativeSourceGraphSha256", "installedReleaseSha256", "runtimeSha256", "profileSha256"];
  const context: Record<string, unknown> = {
    lane: "bounded_output_residual_consistency", invocationId: `invocation-${caseId}-${phase}`, caseId, phase, target,
    ...Object.fromEntries(hashFields.map((key) => [key, bare(hash(`${caseId}:${key}`))])),
    binding: { kind: "baseline" },
  };
  const documentHash = bare(sha256CanonicalJson(input.document));
  const dependenciesHash = bare(sha256CanonicalJson(input.dependencies));
  context.originalDocumentSha256 = documentHash;
  context.executionDocumentSha256 = executionDiffers ? bare(hash(`${caseId}:authenticated execution document bytes`)) : documentHash;
  context.originalDependenciesSha256 = dependenciesHash;
  context.executionDependenciesSha256 = executionDiffers ? bare(hash(`${caseId}:authenticated execution dependency bytes`)) : dependenciesHash;
  const projection = Object.fromEntries(Object.entries(context).filter(([key]) =>
    !["preflightSha256", "preparationSha256", "invocationId"].includes(key)));
  projection.binding = { kind: "baseline" };
  context.binding = { kind: "baseline", bindingSha256: pythonHash(projection) };
  const delivery = manifest.events.filter((event) => event.kind !== "script_marker").map((event) => {
    const start = event.recordRange.startFrame; const duration = event.recordRange.endFrame - start;
    const sourceStart = event.sourceRange?.startFrame ?? 0;
    const sourceDuration = event.sourceRange === null ? duration : event.sourceRange.endFrame - sourceStart;
    return {
      eventId: event.eventId, kind: event.kind,
      recordRange: { startFrame: start, durationFrames: duration },
      sourceRange: { startFrame: sourceStart, durationFrames: sourceDuration },
    };
  }).sort((a, b) => a.eventId.localeCompare(b.eventId));
  const nativeSources = [...nativeSourceRows.values()].sort((a, b) => a.sourceId.localeCompare(b.sourceId));
  const itemMappings = items.map(({ itemUid, eventId, sourceId, mediaUid }) => ({ itemUid, eventId, sourceId, mediaUid }))
    .sort((a, b) => a.itemUid.localeCompare(b.itemUid));
  const inputBindingJson = JSON.stringify(pythonSorted({
    schemaVersion: "qualification-output-inputs/v1", lane: "bounded_output_residual_consistency", context,
    delivery, sourceEntries, tracks, itemMappings, nativeSources,
  }));
  const geometry = {
    context, extentFrames: raw.timeline.durationFrames, rate: { numerator: 24000, denominator: 1001 }, tracks,
    items, sourceMappings: sourceEntries.map((source) => ({
      sourceId: source.sourceId, nativeSourceSha256: source.nativeSourceSha256, sourceEntrySha256: pythonHash(source),
    })),
  };
  const envelope = {
    schemaVersion: "qualification-output-geometry/v1", lane: "bounded_output_residual_consistency", geometry,
    inputBindingSha256: rawHash(inputBindingJson), capturePhase: "pre_render",
    capturedAt: "2026-10-18T12:00:00Z", expiresAt: "2026-10-18T12:05:00Z", receiptSha256: bare(hash(`${caseId}:${phase}:receipt`)),
  };
  return { envelope, geometry, context, inputBindingJson };
}

function comparison(geometry: ReturnType<typeof geometryEnvelope>, phase: "pristine" | "edited", caseId: string) {
  const context = geometry.context;
  const lineage = {
    schemaVersion: "qualification-output-lineage/v1", lane: "bounded_output_residual_consistency", context,
    commitmentRawSha256: bare(hash(`${caseId}:${phase}:commitment`)), reservationRawSha256: bare(hash(`${caseId}:${phase}:reservation`)),
    renderIntentSha256: bare(hash(`${caseId}:${phase}:intent`)), effectReceiptSha256: bare(hash(`${caseId}:${phase}:effect`)),
    startReceiptSha256: bare(hash(`${caseId}:${phase}:start`)), completionReceiptSha256: bare(hash(`${caseId}:${phase}:completion`)),
    jobId: `job-${caseId}-${phase}`, sourceOutputRawSha256: bare(hash(`${caseId}:${phase}:mov`)),
  };
  const metric = (rms: number, sliding: number) => ({ residualRms: rms, maximumSliding20msResidualRms: sliding, consistent: rms <= 0.0004 && sliding <= 0.006 });
  return {
    schemaVersion: "qualification-output-comparison/v1", lane: "bounded_output_residual_consistency", context, status: "compared_consistent",
    commitmentRawSha256: lineage.commitmentRawSha256, commitmentPayloadSha256: bare(hash(`${caseId}:${phase}:payload`)),
    reservationRawSha256: lineage.reservationRawSha256, renderLineage: lineage,
    decodeRecordRawSha256: bare(hash(`${caseId}:${phase}:decode`)), preGeometryRawSha256: bare(hash(`${caseId}:${phase}:pre-geometry`)),
    postGeometryRawSha256: bare(hash(`${caseId}:${phase}:post-geometry`)), geometrySha256: pythonHash(geometry.geometry),
    algorithmSha256: bare(hash("214 algorithm")), metrics: [metric(0.0001, 0.0002), metric(0.0001, 0.0002)],
    signalMetrics: [metric(0.1, 0.2), metric(0.1, 0.2)], priorLedgerHeadSha256: bare(hash(`${caseId}:${phase}:prior-head`)),
    internalControls: "unverified", geometryStability: "not_claimed", controlStability: "not_claimed", futureAuthority: false,
    comparisonReceiptSha256: bare(hash(`${caseId}:${phase}:comparison-receipt`)),
  };
}

function pairRecord(pristineComparisonJson: string, editedComparisonJson: string, caseId: string, pristineFrames: number, editedFrames: number) {
  const pristineSampleCount = pristineFrames * 2002; const editedSampleCount = editedFrames * 2002;
  const differs = { residualRms: 0.001, maximumSliding20msResidualRms: 0.007, consistent: false };
  const pair = {
    schemaVersion: "qualification-output-pair/v1", lane: "bounded_output_residual_consistency",
    pristineComparisonRawSha256: rawHash(pristineComparisonJson), editedComparisonRawSha256: rawHash(editedComparisonJson),
    pristineLedgerHeadSha256: bare(hash(`${caseId}:pristine-ledger`)), editedLedgerHeadSha256: bare(hash(`${caseId}:edited-ledger`)),
    pristineSampleCount, editedSampleCount, commonInterval: { startSample: 0, endSample: Math.min(pristineSampleCount, editedSampleCount) },
    crossMetrics: { predictionDifference: [differs, differs], editedAgainstPristine: [differs, differs], pristineAgainstEdited: [differs, differs] },
    internalControls: "unverified", geometryStability: "not_claimed", controlStability: "not_claimed", futureAuthority: false,
  };
  return JSON.stringify(pair);
}

function equality(caseId: string, extentFrames: number): QualificationOutputAudioEqualityV1 {
  const sampleCount = extentFrames * 2002;
  return {
    schemaVersion: "qualification-output-audio-equality/v1", lane: "bounded_output_residual_consistency", caseId,
    pristinePredictionSha256: bare(hash(`${caseId}:same-prediction`)), editedPredictionSha256: bare(hash(`${caseId}:same-prediction`)),
    pristineDecodedSamplesSha256: bare(hash(`${caseId}:same-decoded`)), editedDecodedSamplesSha256: bare(hash(`${caseId}:same-decoded`)),
    predictionByteLength: sampleCount * 16, decodedSampleByteLength: sampleCount * 8, sampleCount,
  };
}

/** Real #182 campaign facts (omission-slowly.json, baseline evidence): the "slowly" word of the Polly narration. */
const CAMPAIGN = {
  slowlyIndex: 8,
  cutStartEnvelope: { minSample: 106555, maxSample: 112795 },
  cutEndEnvelope: { minSample: 140635, maxSample: 146971 },
  audioDurationSamples: 262200,
};

interface CaseOptions {
  executionDiffers?: boolean;
  /** Whole-frame gap (record == narration source frames) cut out of the narration item. */
  cut?: { startFrame: number; endFrame: number };
  origins?: Origins;
  pcmMode?: "wav-direct" | "prepared-audio";
  /** Models Resolve's retained-left/new-right split and rejected UID substitutions. */
  cUidLayout?: "replace-both" | "retain-left" | "retain-right" | "reuse-unrelated" | "duplicate";
  /** Edits the derived support before it is attached, to model a hand-authored or stale record. */
  tamperSupport?: (support: Record<string, unknown>) => void;
}

/** Campaign-shaped narration: the real Polly row text, token structure and measured evidence in the sanitized specimen. */
function campaignInput(options: { commas?: boolean; durationSamples?: number } = {}) {
  const input = specimen();
  const row = input.document.activeDraft.blocks.find((block): block is NarrationBlockV2 => block.type === "narration" && block.id === id(10))!;
  const campaign = JSON.parse(readFileSync(new URL("./data/issue182-baseline.boundary-evidence.json", import.meta.url), "utf8")) as NarrationBoundaryEvidenceV1;
  const campaignDocument = JSON.parse(readFileSync(new URL("../../../tests/data/issue182/campaign/baseline.v2.script-document.json", import.meta.url), "utf8")) as ScriptDocumentV2;
  const source = campaignDocument.activeDraft.blocks[0]!;
  if (source.type !== "narration") throw new Error("campaign narration row missing");
  const text = options.commas === false ? source.text.replaceAll(",", "") : source.text;
  let cursor = 0;
  const tokens = campaign.tokens.map((mark, index) => {
    const startOffset = text.indexOf(mark.quotedText, cursor); cursor = startOffset + mark.quotedText.length;
    return { id: id(1000 + index), value: mark.quotedText, startOffset, endOffset: cursor };
  });
  row.text = text; row.tokens = [tokens[0]!, ...tokens.slice(1)];
  const evidence = structuredClone(campaign);
  evidence.blockId = row.id; evidence.blockRevision = row.version; evidence.textHash = hash(text);
  evidence.tokens = campaign.tokens.map((mark, index) => ({ ...structuredClone(mark), tokenId: tokens[index]!.id, startOffset: tokens[index]!.startOffset, endOffset: tokens[index]!.endOffset }));
  if (options.durationSamples !== undefined) evidence.audio.durationSamples = options.durationSamples;
  input.dependencies.narrationBoundaryEvidence![0] = evidence;
  // The primary slot's prepared clip must cover exactly the compiled narration frames.
  input.dependencies.preparedMedia.find((binding) => binding.requirementKey === "192:prep:30")!.requestedRange.duration =
    rational(Math.ceil(evidence.audio.durationSamples / 2002) * 1001, 24000);
  input.dependencies.document.textHash = hash(`${row.text}\n${(input.document.activeDraft.blocks.find((block) => block.id === id(20)) as NarrationBlockV2).text}`);
  return { ...input, row, evidence };
}

function splitNarration(
  raw: FakeRaw,
  cut: { startFrame: number; endFrame: number },
  uidLayout: NonNullable<CaseOptions["cUidLayout"]> = "replace-both",
): FakeRaw {
  const result = structuredClone(raw);
  const index = result.items.findIndex((item) => item.authoredEvent.kind === "narration" && item.recordStart === 0);
  const original = result.items[index]!; const left = structuredClone(original); const right = structuredClone(original);
  left.itemUid += ":left"; left.recordEnd = cut.startFrame; left.sourceEnd = left.sourceStart + cut.startFrame; left.rawRecordEnd = cut.startFrame - 1;
  right.itemUid += ":right"; right.recordStart = cut.endFrame; right.sourceStart += cut.endFrame;
  if (uidLayout === "retain-left") left.itemUid = original.itemUid;
  if (uidLayout === "retain-right") right.itemUid = original.itemUid;
  if (uidLayout === "reuse-unrelated") {
    const unrelated = result.items.find((item) => item.eventId !== original.eventId && item.linkedUids.length === 0);
    if (unrelated === undefined) throw new Error("unrelated unlinked item missing");
    right.itemUid = unrelated.itemUid;
    unrelated.itemUid += ":reassigned";
  }
  if (uidLayout === "duplicate") right.itemUid = left.itemUid;
  result.items.splice(index, 1, left, right);
  return result;
}

const DEFAULT_CUT = { startFrame: 55, endFrame: 72 };

function newCase(input: ReturnType<typeof specimen>, kind: "A" | "B" | "C", options: CaseOptions = {}): QualificationOutputObservationCaseV1 {
  const cut = options.cut ?? DEFAULT_CUT; const origins = options.origins ?? { nativeFrameOrigin: 0, pcmSampleOrigin: 0 };
  const pristineRaw = observations(input);
  const editedRaw = kind === "C" ? splitNarration(pristineRaw, cut, options.cUidLayout) : edits(pristineRaw, kind);
  const caseId = `isolated-${kind}`;
  const pristineGeometry = geometryEnvelope(input, pristineRaw, "pristine", caseId, options.executionDiffers, origins, options.pcmMode);
  const editedGeometry = geometryEnvelope(input, editedRaw, "edited", caseId, options.executionDiffers, origins, options.pcmMode);
  const pristineComparisonJson = JSON.stringify(comparison(pristineGeometry, "pristine", caseId));
  const editedComparisonJson = JSON.stringify(comparison(editedGeometry, "edited", caseId));
  const pairJson = kind === "A" ? null : pairRecord(pristineComparisonJson, editedComparisonJson, caseId, pristineGeometry.geometry.extentFrames, editedGeometry.geometry.extentFrames);
  let omissionSupport: QualificationOutputObservationCaseV1["omissionSupport"] = null;
  if (kind === "C") {
    const row = input.document.activeDraft.blocks.find((block): block is NarrationBlockV2 => block.type === "narration" && block.id === id(10))!;
    const boundary = input.dependencies.narrationBoundaryEvidence!.find((record) => record.blockId === row.id)!;
    const verification = boundary.verification as { measurementArtifactHash: string; onsetUncertainty: unknown; audibleEndUncertainty: unknown };
    const selectedIndex = CAMPAIGN.slowlyIndex;
    const sample = (frame: number) => (frame - origins.nativeFrameOrigin) * 2002 + origins.pcmSampleOrigin;
    const support: Record<string, unknown> = {
      schemaVersion: "qualification-output-omission-support/v2", lane: "bounded_output_residual_consistency", caseId,
      documentHash: sha256CanonicalJson(input.document), dependenciesHash: sha256CanonicalJson(input.dependencies),
      blockId: row.id, blockRevision: row.version, method: "measured_audio_boundaries/v1",
      selectedTokenId: row.tokens[selectedIndex]!.id, leftNeighborTokenId: row.tokens[selectedIndex - 1]!.id, rightNeighborTokenId: row.tokens[selectedIndex + 1]!.id,
      boundaryEvidenceHash: sha256CanonicalJson(boundary), measurementArtifactHash: verification.measurementArtifactHash,
      audioSha256: bare(boundary.audioHash), timingHash: bare(boundary.timingHash),
      onsetUncertainty: verification.onsetUncertainty, audibleEndUncertainty: verification.audibleEndUncertainty,
      ...origins,
      cutRecordFrames: { ...cut }, cutSourceFrames: { ...cut },
      cutSamples: { startSample: sample(cut.startFrame), endSample: sample(cut.endFrame) },
      cutStartEnvelope: CAMPAIGN.cutStartEnvelope, cutEndEnvelope: CAMPAIGN.cutEndEnvelope,
      pristineGeometryRawSha256: rawHash(JSON.stringify(pristineGeometry.envelope)), editedGeometryRawSha256: rawHash(JSON.stringify(editedGeometry.envelope)),
      pristineComparisonRawSha256: rawHash(pristineComparisonJson), editedComparisonRawSha256: rawHash(editedComparisonJson), pairRawSha256: rawHash(pairJson!),
    };
    options.tamperSupport?.(support);
    omissionSupport = support as unknown as QualificationOutputObservationCaseV1["omissionSupport"];
  }
  return {
    schemaVersion: "qualification-output-observation/v1", lane: "bounded_output_residual_consistency", caseId,
    pristineGeometryJson: JSON.stringify(pristineGeometry.envelope), editedGeometryJson: JSON.stringify(editedGeometry.envelope),
    pristineInputBindingJson: pristineGeometry.inputBindingJson, editedInputBindingJson: editedGeometry.inputBindingJson,
    pristineComparisonJson, editedComparisonJson, pairJson,
    audioEquality: kind === "A" ? equality(caseId, pristineGeometry.geometry.extentFrames) : null,
    omissionSupport,
  };
}

function pairFrames(row: QualificationOutputObservationCaseV1, phase: "pristine" | "edited"): number {
  const text = phase === "pristine" ? row.pristineGeometryJson : row.editedGeometryJson;
  return (JSON.parse(text) as { geometry: { extentFrames: number } }).geometry.extentFrames;
}

function replaceInputBinding(row: QualificationOutputObservationCaseV1, phase: "pristine" | "edited", binding: unknown): void {
  const bindingKey = phase === "pristine" ? "pristineInputBindingJson" : "editedInputBindingJson";
  const geometryKey = phase === "pristine" ? "pristineGeometryJson" : "editedGeometryJson";
  const raw = JSON.stringify(pythonSorted(binding));
  row[bindingKey] = raw;
  const envelope = JSON.parse(row[geometryKey]) as { inputBindingSha256: string };
  envelope.inputBindingSha256 = rawHash(raw);
  row[geometryKey] = JSON.stringify(envelope);
}

function batch(input: ReturnType<typeof specimen>, kinds: ("A" | "B" | "C")[], executionDiffers: boolean | CaseOptions = false): QualificationOutputObservationBatchV1 {
  const options: CaseOptions = typeof executionDiffers === "boolean" ? { executionDiffers } : executionDiffers;
  return {
    schemaVersion: "qualification-output-observation-batch/v1", lane: "bounded_output_residual_consistency",
    documentHash: sha256CanonicalJson(input.document), dependenciesHash: sha256CanonicalJson(input.dependencies),
    cases: kinds.map((kind) => newCase(input, kind, options)),
  };
}

function accept(proposalHash: string, history: string[] = []) {
  return { schemaVersion: "qualification-output-decision/v1" as const, proposalHash, historyHash: sha256CanonicalJson(history), outcome: "accept" as const };
}

function replacementHandoff(stage: ReturnType<typeof stageQualificationOutputV2>): RowHandoffV2 {
  const request = stage.regeneration;
  if (request === null) throw new Error("C stage did not request whole-row regeneration");
  const row = stage.document.activeDraft.blocks.find((block) => block.id === request.blockId);
  if (row?.type !== "narration") throw new Error("C replacement row missing");
  const boundaryEvidence = timing(row, 200, true);
  return {
    schemaVersion: "issue-189-v2-row-handoff/v1",
    request: {
      schemaVersion: "issue-189-v2-row-request/v1", policy: "replace_whole_row",
      blockId: request.blockId, blockRevision: request.blockRevision, text: request.text, textHash: request.textHash,
      revisedDocumentHash: request.revisedDocumentHash, evidenceHash: request.evidenceHash, decisionHash: request.decisionHash,
    },
    priorDependenciesHash: sha256CanonicalJson(stage.dependencies), serviceRequestHash: hash("synthetic C service request"),
    generationReceiptHash: hash("synthetic C generation receipt"), assetRecordHash: hash("synthetic C asset record"),
    audioHash: boundaryEvidence.audioHash, providerTimingHash: boundaryEvidence.timingHash,
    reviewArtifactHash: (boundaryEvidence.verification as { reviewArtifactHash: string }).reviewArtifactHash, boundaryEvidence,
  };
}

describe("#215 authenticated output observation to explicit revision bridge", () => {
  it("derives a unique generic held-boundary move from raw #214 geometry", () => {
    const input = specimen(); const evidence = batch(input, ["A"]);
    const inference = inferQualificationOutputV2(input.document, input.dependencies, evidence);
    expect(inference.caseKinds).toEqual(["A"]);
    expect(inference.commands.boundary).not.toBeNull();
    expect(inference.commands.trim).toBeNull(); expect(inference.omission).toBeNull();
    expect(inference.commands.boundary?.expectedSequenceVersion).toBe(1);
    expect(inference.internalControls).toBe("unverified"); expect(inference.futureAuthority).toBe(false);
  }, 15_000);

  it("keeps video native sources outside the audio PCM source mappings", () => {
    const input = specimen(); const evidence = batch(input, ["A"]); const row = evidence.cases[0]!;
    const geometry = JSON.parse(row.pristineGeometryJson) as { geometry: { items: { kind: string; sourceId: string }[]; sourceMappings: { sourceId: string }[] } };
    const binding = JSON.parse(row.pristineInputBindingJson) as {
      nativeSources: { sourceId: string }[]; sourceEntries: { sourceId: string }[];
    };
    const audioIds = new Set(geometry.geometry.items.filter((item) => item.kind === "audio").map((item) => item.sourceId));
    const videoOnlyId = geometry.geometry.items.find((item) => item.kind === "video" && !audioIds.has(item.sourceId))!.sourceId;
    expect(binding.nativeSources.map((source) => source.sourceId)).toContain(videoOnlyId);
    expect(binding.sourceEntries.map((source) => source.sourceId)).not.toContain(videoOnlyId);
    expect(geometry.geometry.sourceMappings.map((source) => source.sourceId)).toEqual(binding.sourceEntries.map((source) => source.sourceId));
    expect(inferQualificationOutputV2(input.document, input.dependencies, evidence).caseKinds).toEqual(["A"]);

    const unknown = batch(input, ["A"]); const unknownRow = unknown.cases[0]!;
    const unknownBinding = JSON.parse(unknownRow.pristineInputBindingJson) as { nativeSources: { sourceId: string }[] };
    unknownBinding.nativeSources = unknownBinding.nativeSources.filter((source) => source.sourceId !== videoOnlyId);
    replaceInputBinding(unknownRow, "pristine", unknownBinding);
    expect(() => inferQualificationOutputV2(input.document, input.dependencies, unknown)).toThrow(/unknown item source/);

    const tampered = batch(input, ["A"]); const tamperedRow = tampered.cases[0]!;
    const tamperedBinding = JSON.parse(tamperedRow.pristineInputBindingJson) as {
      nativeSources: { sourceId: string; nativeSourceSha256: string }[];
    };
    tamperedBinding.nativeSources.find((source) => source.sourceId === videoOnlyId)!.nativeSourceSha256 = "0".repeat(64);
    replaceInputBinding(tamperedRow, "pristine", tamperedBinding);
    expect(() => inferQualificationOutputV2(input.document, input.dependencies, tampered)).toThrow(/video source mapping differs/);
  });

  it("refuses a changed input binding unless its raw geometry hash and PCM mappings agree", () => {
    const input = specimen();
    const stale = batch(input, ["A"]); const staleRow = stale.cases[0]!;
    staleRow.pristineInputBindingJson = staleRow.pristineInputBindingJson.replace("qualification-output-inputs/v1", "changed-input-binding/v1");
    expect(() => inferQualificationOutputV2(input.document, input.dependencies, stale)).toThrow(/geometry\/input binding raw hash differs/);

    const pcm = batch(input, ["A"]); const pcmRow = pcm.cases[0]!;
    const pcmBinding = JSON.parse(pcmRow.pristineInputBindingJson) as {
      sourceEntries: { sourceId: string; pcmMappingSha256: string }[];
    };
    pcmBinding.sourceEntries[0]!.pcmMappingSha256 = "0".repeat(64);
    replaceInputBinding(pcmRow, "pristine", pcmBinding);
    expect(() => inferQualificationOutputV2(input.document, input.dependencies, pcm)).toThrow(/audio source mapping inventory differs from input binding/);
  });

  it("preserves distinct authenticated original/execution pins and rejects pair pin disagreement", () => {
    const input = specimen();
    const valid = batch(input, ["B"], true);
    expect(inferQualificationOutputV2(input.document, input.dependencies, valid).caseKinds).toEqual(["B"]);

    const mismatched = batch(input, ["B"], true);
    const row = mismatched.cases[0]!;
    const editedEnvelope = JSON.parse(row.editedGeometryJson) as { inputBindingSha256: string; geometry: { context: Record<string, unknown> } };
    const context = editedEnvelope.geometry.context;
    context.originalDocumentSha256 = bare(hash("different authenticated original document"));
    context.originalDependenciesSha256 = bare(hash("different authenticated original dependencies"));
    const projection = Object.fromEntries(Object.entries(context).filter(([key]) =>
      !["preflightSha256", "preparationSha256", "invocationId"].includes(key)));
    projection.binding = { kind: "baseline" };
    context.binding = { kind: "baseline", bindingSha256: pythonHash(projection) };
    const editedInputBinding = JSON.parse(row.editedInputBindingJson) as { context: Record<string, unknown> };
    editedInputBinding.context = structuredClone(context);
    row.editedInputBindingJson = JSON.stringify(pythonSorted(editedInputBinding));
    editedEnvelope.inputBindingSha256 = rawHash(row.editedInputBindingJson);
    row.editedGeometryJson = JSON.stringify(editedEnvelope);

    const editedComparison = JSON.parse(row.editedComparisonJson) as {
      context: Record<string, unknown>; renderLineage: { context: Record<string, unknown> }; geometrySha256: string;
    };
    editedComparison.context = structuredClone(context);
    editedComparison.renderLineage.context = structuredClone(context);
    editedComparison.geometrySha256 = pythonHash(editedEnvelope.geometry);
    row.editedComparisonJson = JSON.stringify(editedComparison);
    row.pairJson = pairRecord(row.pristineComparisonJson, row.editedComparisonJson, row.caseId, pairFrames(row, "pristine"), pairFrames(row, "edited"));

    expect(() => inferQualificationOutputV2(input.document, input.dependencies, mismatched))
      .toThrow(/pristine\/edited authenticated input identities differ/);
  }, 15000);

  it("derives an AV ripple trim from geometry with a genuinely shortened programme extent", () => {
    const input = specimen(); const inference = inferQualificationOutputV2(input.document, input.dependencies, batch(input, ["B"]));
    expect(inference.caseKinds).toEqual(["B"]);
    expect(inference.commands.trim?.blockId).toEqual(expect.any(String));
    expect(inference.commands.trim).toMatchObject({ expectedBlockVersion: 1, durationFrames: 67 });
    expect(inference.commands.boundary).toBeNull();
    const trimBatch = batch(input, ["B"]);
    const extents = [pairFrames(trimBatch.cases[0]!, "pristine"), pairFrames(trimBatch.cases[0]!, "edited")];
    expect(extents[1]).toBeLessThan(extents[0]!); // fixture ripple: edited programme is pristine minus the trim delta, no padding
    const stage = stageQualificationOutputV2(input.document, input.dependencies, batch(input, ["B"]), accept(inference.inferenceHash), []);
    expect(stage.outcome).toBe("accept");
    const trimmed = stage.document.activeDraft.blocks.find((block) => block.id === inference.commands.trim?.blockId);
    expect(trimmed?.type === "visual_only" ? trimmed.visualOnlyTiming.selectedSourceRange?.durationFrames : null).toBe(67);
  }, 15000);

  describe("machine-derived word omission from measured campaign evidence", () => {
    const infer = (input: ReturnType<typeof campaignInput>, options: CaseOptions = {}) =>
      inferQualificationOutputV2(input.document, input.dependencies, batch(input, ["C"], options));

    it("accepts Resolve's retained-left/new-right item UID split", () => {
      const input = campaignInput();
      const observed = batch(input, ["C"], { cUidLayout: "retain-left" }).cases[0]!;
      const pristine = JSON.parse(observed.pristineGeometryJson) as { geometry: { items: { itemUid: string; eventId: string }[] } };
      const edited = JSON.parse(observed.editedGeometryJson) as { geometry: { items: { itemUid: string; eventId: string; recordStart: number }[] } };
      const compiled = compileTimelineV2(input.document, input.dependencies);
      if (!compiled.ok || compiled.report.status !== "ready") throw new Error("sanitized baseline compile failed");
      const eventId = compiled.manifest.events.find((event) => event.kind === "narration" && event.provenance.blockId === input.row.id)!.eventId;
      const [original] = pristine.geometry.items.filter((item) => item.eventId === eventId);
      const segments = edited.geometry.items.filter((item) => item.eventId === eventId).sort((a, b) => a.recordStart - b.recordStart);
      expect(original).toBeDefined();
      expect(segments).toHaveLength(2);
      expect(segments[0]!.itemUid).toBe(original!.itemUid);
      expect(segments[1]!.itemUid).not.toBe(original!.itemUid);
      expect(pristine.geometry.items.some((item) => item.eventId !== eventId && item.itemUid === segments[1]!.itemUid)).toBe(false);
      expect(infer(input, { cUidLayout: "retain-left" }).omission?.tokenIds).toEqual([input.row.tokens[CAMPAIGN.slowlyIndex]!.id]);
    });

    it("refuses old UID only on the right, unrelated baseline UID reuse, and duplicate segment UIDs", () => {
      const input = campaignInput();
      expect(() => infer(input, { cUidLayout: "retain-right" })).toThrow(/retain the original UID on the left or use two distinct new UIDs/);
      expect(() => infer(input, { cUidLayout: "reuse-unrelated" })).toThrow(/reuses an unrelated baseline item UID/);
      expect(() => infer(input, { cUidLayout: "duplicate" })).toThrow(/duplicate native item UID/);
    });

    it("accepts a frame-snapped cut on the unique word the #182 evidence isolates, with no token named by the host", () => {
      const input = campaignInput();
      expect(input.evidence.audio.durationSamples).toBe(CAMPAIGN.audioDurationSamples);
      const inference = infer(input);
      expect(inference.caseKinds).toEqual(["C"]);
      expect(inference.omission?.tokenIds).toEqual([input.row.tokens[CAMPAIGN.slowlyIndex]!.id]);
      expect(input.row.tokens[CAMPAIGN.slowlyIndex]!.value).toBe("slowly");
      const cases = batch(input, ["C"]).cases[0]!;
      const support = cases.omissionSupport!;
      expect(support.schemaVersion).toBe("qualification-output-omission-support/v2");
      expect(support.method).toBe("measured_audio_boundaries/v1");
      expect(support.cutSamples).toEqual({ startSample: 55 * 2002, endSample: 72 * 2002 });
      expect(inference.omission?.evidenceHash).toBe(sha256CanonicalJson(support));
      expect(Object.keys(support)).not.toContain("reviewArtifactSha256");
    });

    it("derives the support from raw evidence alone (the host bridge) and inference accepts exactly that record", () => {
      const input = campaignInput();
      const full = batch(input, ["C"]);
      const expected = full.cases[0]!.omissionSupport!;
      const bare = structuredClone(full); bare.cases[0]!.omissionSupport = null;
      const derived = deriveOmissionSupportV2(input.document, input.dependencies, bare);
      expect(derived).toEqual(expected);
      const request = { schemaVersion: "qualification-output-pure-request/v1", mode: "derive_omission", document: input.document, dependencies: input.dependencies,
        evidence: bare, preparedMedia: [], handoff: null, inferenceDecision: null, inferenceHistory: [], candidate: null, decision: null, history: [] };
      const parsed = parseQualificationOutputPureRequest(new TextEncoder().encode(JSON.stringify(request)));
      expect(runQualificationOutputPureRequest(parsed)).toEqual(expected);
      const attached = structuredClone(bare); attached.cases[0]!.omissionSupport = derived;
      expect(inferQualificationOutputV2(input.document, input.dependencies, attached).omission?.tokenIds).toEqual([input.row.tokens[CAMPAIGN.slowlyIndex]!.id]);
      // Golden for the python parity test; regenerate with VERA_WRITE_GOLDEN=1.
      if (process.env.VERA_WRITE_GOLDEN === "1") {
        const directory = new URL("../../../tests/data/issue215/", import.meta.url);
        mkdirSync(directory, { recursive: true });
        writeFileSync(new URL("omission-derive-case.json", directory), `${JSON.stringify({ document: input.document, dependencies: input.dependencies, evidence: bare, expectedSupport: expected })}\n`);
      }
    });

    it("refuses to derive support when the edit does not split one narration item", () => {
      const input = campaignInput();
      const none = batch(input, ["A"]);
      expect(() => deriveOmissionSupportV2(input.document, input.dependencies, none)).toThrow(/does not split exactly one narration item/);
    });

    it("accepts every whole-frame edge inside the python envelope and refuses the first frame outside it on each side", () => {
      const input = campaignInput();
      const pairs = [[54, 71], [56, 73], [55, 73], [56, 71]] as const;
      for (const [startFrame, endFrame] of pairs) {
        expect(infer(input, { cut: { startFrame, endFrame } }).omission?.tokenIds).toHaveLength(1);
      }
      // 53 clips the tail of "harbor"; 57 starts inside "slowly"; 70 ends inside "slowly"; 74 clips "toward".
      for (const [startFrame, endFrame] of [[53, 72], [57, 72], [55, 70], [55, 74]] as const) {
        expect(() => infer(input, { cut: { startFrame, endFrame } }), `${startFrame}-${endFrame}`).toThrow(/does not isolate exactly one measured word/);
      }
    });

    it("refuses a cut that straddles a neighbour or spans several words", () => {
      const input = campaignInput();
      expect(() => infer(input, { cut: { startFrame: 50, endFrame: 72 } })).toThrow(/does not isolate exactly one measured word/);
      expect(() => infer(input, { cut: { startFrame: 55, endFrame: 90 } })).toThrow(/does not isolate exactly one measured word/);
      expect(() => infer(input, { cut: { startFrame: 30, endFrame: 90 } })).toThrow(/does not isolate exactly one measured word/);
    });

    it("refuses a cut on a connected word whose audible end was not measured", () => {
      const input = campaignInput();
      // "toward" (token 9) starts at sample 148171 and has no measured audible end.
      expect(() => infer(input, { cut: { startFrame: 75, endFrame: 79 } })).toThrow(/does not isolate exactly one measured word.*connected speech/);
      // "harbor" is measured, but its left neighbour "the" is connected, so it cannot be isolated either.
      expect(() => infer(input, { cut: { startFrame: 41, endFrame: 53 } })).toThrow(/does not isolate exactly one measured word/);
    });

    it("refuses reviewed evidence, incomplete token coverage and a tampered or hand-authored support record", () => {
      const reviewed = campaignInput();
      reviewed.dependencies.narrationBoundaryEvidence![0] = { ...timing(reviewed.row, 131), textHash: hash(reviewed.row.text) };
      expect(() => infer(reviewed)).toThrow(/measured narration boundary evidence required/);

      const gap = campaignInput();
      gap.evidence.tokens.splice(3, 1);
      expect(() => infer(gap)).toThrow(/cover every spoken frozen token/);

      const input = campaignInput();
      const mutations: ((support: Record<string, unknown>) => void)[] = [
        (support) => { support.selectedTokenId = input.row.tokens[CAMPAIGN.slowlyIndex + 1]!.id; },
        (support) => { support.measurementArtifactHash = hash("another measurement"); },
        (support) => { support.boundaryEvidenceHash = hash("another evidence"); },
        (support) => { support.cutStartEnvelope = { minSample: 100000, maxSample: 120000 }; },
        (support) => { support.pcmSampleOrigin = 5; },
      ];
      for (const tamperSupport of mutations) {
        expect(() => infer(input, { tamperSupport })).toThrow(/omission support differs from the record derived/);
      }
      expect(() => infer(input, { tamperSupport: (support) => { support.schemaVersion = "qualification-output-omission-support/v1"; } })).toThrow(/stale omission support binding/);
      expect(() => infer(input, { tamperSupport: (support) => { support.reviewArtifactSha256 = "0".repeat(64); } })).toThrow(/unsupported omission support fields/);
    });

    it("refuses measured-evidence omission when the narration source is not wav-direct", () => {
      const input = campaignInput();
      expect(() => infer(input, { pcmMode: "prepared-audio" })).toThrow(/requires a wav-direct narration source/);
      expect(infer(input).omission).not.toBeNull();
    });

    it("refuses first and last token omissions so inference agrees with the interior-only transform", () => {
      expect(() => requireInteriorOmissionIndex(0, 12)).toThrow(/first or last narration token omission is unsupported/);
      expect(() => requireInteriorOmissionIndex(11, 12)).toThrow(/first or last narration token omission is unsupported/);
      expect(() => requireInteriorOmissionIndex(CAMPAIGN.slowlyIndex, 12)).not.toThrow();
    });

    it("takes PCM sample origins from the bound source entry, not from the support record", () => {
      const input = campaignInput();
      const origins = { nativeFrameOrigin: 3, pcmSampleOrigin: 37 };
      // (58 - 3) * 2002 + 37 = 110147 and (75 - 3) * 2002 + 37 = 144181 sit inside the unchanged envelope.
      const cut = { startFrame: 58, endFrame: 75 };
      const inference = infer(input, { origins, cut });
      expect(inference.omission?.tokenIds).toEqual([input.row.tokens[CAMPAIGN.slowlyIndex]!.id]);
      expect(batch(input, ["C"], { origins, cut }).cases[0]!.omissionSupport).toMatchObject({ nativeFrameOrigin: 3, pcmSampleOrigin: 37, cutSamples: { startSample: 110147, endSample: 144181 } });
      expect(() => infer(input, { tamperSupport: (support) => { support.nativeFrameOrigin = 3; } })).toThrow(/omission support differs/);
      // The same frames with different bound origins fall outside the envelope: 58 * 2002 + 5000 = 121116.
      expect(() => infer(input, { origins: { nativeFrameOrigin: 0, pcmSampleOrigin: 5000 }, cut })).toThrow(/does not isolate exactly one measured word/);
    });

    it("stages the whole-row regeneration for the campaign omission and accepts a non-frame-aligned replacement row", () => {
      const input = campaignInput({ commas: false });
      const evidence = batch(input, ["C"]);
      const inference = inferQualificationOutputV2(input.document, input.dependencies, evidence);
      const decision = accept(inference.inferenceHash);
      // The revised row compiles to 132 frames, so the primary slot carries a re-prepared clip of exactly that length.
      const reprepared = [{ ...structuredClone(input.dependencies.preparedMedia.find((binding) => binding.requirementKey === "192:prep:30")!) }];
      reprepared[0]!.requestedRange.duration = rational(132 * 1001, 24000);
      const stage = stageQualificationOutputV2(input.document, input.dependencies, evidence, decision, [], reprepared);
      expect(stage.outcome).toBe("accept");
      expect(stage.regeneration).toMatchObject({ schemaVersion: "qualification-output-regeneration-request/v1", policy: "replace_whole_row",
        text: "Every morning the old ferry crosses the harbor toward the little island where the market opens at nine." });
      expect(stage.regeneration?.decisionHash).toBe(sha256CanonicalJson(decision));
      const handoff = replacementHandoff(stage);
      handoff.boundaryEvidence.audio.durationSamples = 131 * 2002 + 999; // a real Polly duration, not on the 2002-sample grid
      const proposal = createQualificationOutputProposalV2(input.document, input.dependencies, evidence, decision, [], reprepared, handoff);
      expect(proposal.schemaVersion).toBe("qualification-output-proposal/v1");
      for (const [label, change, message] of [
        ["stereo", (audio: { channels: number }) => { audio.channels = 2; }, /48 kHz mono/],
        ["44.1 kHz", (audio: { sampleRate: number }) => { audio.sampleRate = 44100; }, /48 kHz mono/],
        ["empty", (audio: { durationSamples: number }) => { audio.durationSamples = 0; }, /48 kHz mono|duration samples/],
      ] as const) {
        const bad = structuredClone(handoff);
        (change as (audio: unknown) => void)(bad.boundaryEvidence.audio);
        expect(() => createQualificationOutputProposalV2(input.document, input.dependencies, evidence, decision, [], reprepared, bad), label).toThrow(message);
      }
    });

    it("documents what applyAcceptedOmissionV2 does to the campaign baseline text", () => {
      const baseline = JSON.parse(readFileSync(new URL("../../../tests/data/issue182/campaign/baseline.v2.script-document.json", import.meta.url), "utf8")) as ScriptDocumentV2;
      const row = baseline.activeDraft.blocks[0] as NarrationBlockV2;
      const edit = (document: ScriptDocumentV2) => applyAcceptedOmissionV2(document, {
        schemaVersion: "issue-189-v2-accepted-omission/v1", expectedDocumentHash: sha256CanonicalJson(document), blockId: row.id,
        blockRevision: row.version, tokenIds: [row.tokens[CAMPAIGN.slowlyIndex]!.id], evidenceHash: hash("evidence"), decisionHash: hash("decision"),
      });
      expect(row.text).toContain("harbor, slowly, toward");
      const revised = edit(baseline).document.activeDraft.blocks[0] as NarrationBlockV2;
      // The real baseline sets "slowly" off by commas; the single-word parenthetical rule keeps exactly one comma ("harbor, toward").
      expect(revised.text).toBe("Every morning the old ferry crosses the harbor, toward the little island where the market opens at nine.");
      for (const token of revised.tokens) expect(revised.text.slice(token.startOffset, token.endOffset)).toBe(token.value);
      const plain = structuredClone(baseline);
      const plainRow = campaignInput({ commas: false }).row;
      const target = plain.activeDraft.blocks[0] as NarrationBlockV2;
      target.text = plainRow.text; target.tokens = plainRow.tokens.map((token, index) => ({ ...token, id: row.tokens[index]!.id })) as NarrationBlockV2["tokens"];
      expect(edit(plain).regeneration.text).toBe("Every morning the old ferry crosses the harbor toward the little island where the market opens at nine.");
    });
  });

  it("composes isolated A/B/C commands and stages C before any provider handoff", () => {
    const input = campaignInput({ commas: false, durationSamples: 200 * 2002 }); const evidence = batch(input, ["A", "B", "C"]);
    const inference = inferQualificationOutputV2(input.document, input.dependencies, evidence);
    expect(inference.caseKinds).toEqual(["A", "B", "C"]);
    expect(inference.commands.boundary).not.toBeNull(); expect(inference.commands.trim).not.toBeNull();
    const inferenceDecision = accept(inference.inferenceHash);
    const stage = stageQualificationOutputV2(input.document, input.dependencies, evidence, inferenceDecision, []);
    expect(stage.regeneration).not.toBeNull();
  }, 20000);

  it("creates canonical revision only after both new-domain decisions and refuses replay", () => {
    const input = specimen(); const evidence = batch(input, ["A"]);
    const inference = inferQualificationOutputV2(input.document, input.dependencies, evidence);
    const inferenceDecision = accept(inference.inferenceHash);
    const candidate = createQualificationOutputProposalV2(input.document, input.dependencies, evidence, inferenceDecision, [], [], null);
    const decision = accept(candidate.proposalHash);
    const result = decideQualificationOutputV2(input.document, input.dependencies, evidence, candidate, decision, []);
    expect(result.outcome).toBe("accept"); expect(result.document).toEqual(candidate.revision.document);
    expect(result.history).toEqual([candidate.proposalHash]);
    expect(() => decideQualificationOutputV2(input.document, input.dependencies, evidence, candidate,
      { ...decision, historyHash: sha256CanonicalJson(result.history) }, result.history)).toThrow(/history/);
  }, 20000);

  it("rejects duplicate UIDs, unknown sources, unexplained geometry and missing pair evidence", () => {
    const input = specimen();
    const duplicate = batch(input, ["A"]); const row = duplicate.cases[0]!;
    const edited = JSON.parse(row.editedGeometryJson) as { geometry: { items: unknown[] } };
    edited.geometry.items.push(structuredClone(edited.geometry.items[0])); row.editedGeometryJson = JSON.stringify(edited);
    expect(() => inferQualificationOutputV2(input.document, input.dependencies, duplicate)).toThrow(/duplicate native item UID/);

    const unknown = batch(input, ["A"]); const unknownCase = unknown.cases[0]!;
    const unknownGeometry = JSON.parse(unknownCase.editedGeometryJson) as { geometry: { items: Record<string, unknown>[] } };
    unknownGeometry.geometry.items[0]!.sourceId = "not-in-source-inventory"; unknownCase.editedGeometryJson = JSON.stringify(unknownGeometry);
    expect(() => inferQualificationOutputV2(input.document, input.dependencies, unknown)).toThrow(/unknown item source/);

    const extra = batch(input, ["A"]); const extraGeometry = JSON.parse(extra.cases[0]!.editedGeometryJson) as Record<string, unknown>;
    (extraGeometry.geometry as Record<string, unknown>).untrustedExtension = true;
    extra.cases[0]!.editedGeometryJson = JSON.stringify(extraGeometry);
    expect(() => inferQualificationOutputV2(input.document, input.dependencies, extra)).toThrow(/unsupported .*semantic geometry fields/);

    const unexplained = batch(input, ["A"]); const unexplainedCase = unexplained.cases[0]!;
    const changed = JSON.parse(unexplainedCase.editedGeometryJson) as { geometry: { items: { recordStart: number }[] } };
    changed.geometry.items.at(-1)!.recordStart += 1; unexplainedCase.editedGeometryJson = JSON.stringify(changed);
    expect(() => inferQualificationOutputV2(input.document, input.dependencies, unexplained)).toThrow(/unsupported item interval|unique supported A\/B\/C/);

    const noPair = batch(input, ["B"]); noPair.cases[0]!.pairJson = null;
    expect(() => inferQualificationOutputV2(input.document, input.dependencies, noPair)).toThrow(/pair evidence|pair comparison|pair discriminability/);
  });

  describe("shortened render extent and pair sample evidence", () => {
    function setExtent(row: QualificationOutputObservationCaseV1, extentFrames: number): void {
      const edited = JSON.parse(row.editedGeometryJson) as { geometry: { extentFrames: number } };
      edited.geometry.extentFrames = extentFrames; row.editedGeometryJson = JSON.stringify(edited);
      const comparisonValue = JSON.parse(row.editedComparisonJson) as { geometrySha256: string };
      comparisonValue.geometrySha256 = pythonHash(edited.geometry); row.editedComparisonJson = JSON.stringify(comparisonValue);
    }
    function mutatePair(row: QualificationOutputObservationCaseV1, change: (pair: Record<string, unknown>) => void): void {
      const pair = JSON.parse(row.pairJson!) as Record<string, unknown>; change(pair); row.pairJson = JSON.stringify(pair);
    }
    const run = (input: ReturnType<typeof specimen>, evidence: QualificationOutputObservationBatchV1) =>
      () => inferQualificationOutputV2(input.document, input.dependencies, evidence);

    it("refuses an edited extent longer than the pristine extent", () => {
      const input = specimen(); const evidence = batch(input, ["B"]); const row = evidence.cases[0]!;
      setExtent(row, pairFrames(row, "pristine") + 1);
      expect(run(input, evidence)).toThrow(/lengthened capture extent/);
    });

    it("yields no trim proposal when the edited extent is not pristine minus the trim delta", () => {
      const input = specimen(); const evidence = batch(input, ["B"]); const row = evidence.cases[0]!;
      const pristineFrames = pairFrames(row, "pristine");
      setExtent(row, pristineFrames - 23);
      row.pairJson = pairRecord(row.pristineComparisonJson, row.editedComparisonJson, row.caseId, pristineFrames, pristineFrames - 23);
      expect(run(input, evidence)).toThrow(/unique supported A\/B\/C/);
    });

    it("refuses a shortened extent on a non-trim video-only case", () => {
      const input = specimen(); const evidence = batch(input, ["A"]); const row = evidence.cases[0]!;
      setExtent(row, pairFrames(row, "pristine") - 1);
      expect(run(input, evidence)).toThrow(/unsupported item interval|only an authenticated linked trim/);
    });

    it("refuses a shortened extent on a non-trim omission case", () => {
      const input = specimen(); const evidence = batch(input, ["C"]); const row = evidence.cases[0]!;
      const pristineFrames = pairFrames(row, "pristine");
      setExtent(row, pristineFrames - 1);
      row.pairJson = pairRecord(row.pristineComparisonJson, row.editedComparisonJson, row.caseId, pristineFrames, pristineFrames - 1);
      expect(run(input, evidence)).toThrow(/unsupported item interval|only an authenticated linked trim/);
    });

    it("refuses pair sample counts and common interval that disagree with geometry", () => {
      const input = specimen();
      for (const change of [
        (pair: Record<string, unknown>) => { pair.pristineSampleCount = (pair.pristineSampleCount as number) + 1; },
        (pair: Record<string, unknown>) => { pair.editedSampleCount = (pair.editedSampleCount as number) + 2002; },
        (pair: Record<string, unknown>) => { pair.commonInterval = { startSample: 1, endSample: (pair.commonInterval as { endSample: number }).endSample }; },
        (pair: Record<string, unknown>) => { pair.commonInterval = { startSample: 0, endSample: pair.pristineSampleCount }; },
        (pair: Record<string, unknown>) => { pair.commonInterval = { startSample: 0, endSample: 959 }; },
      ]) {
        const evidence = batch(input, ["B"]); mutatePair(evidence.cases[0]!, change);
        expect(run(input, evidence)).toThrow(/pair sample counts|pair common interval/);
      }
    });

    it("refuses a pair record missing the new sample fields", () => {
      const input = specimen();
      for (const key of ["pristineSampleCount", "editedSampleCount", "commonInterval"]) {
        const evidence = batch(input, ["B"]); mutatePair(evidence.cases[0]!, (pair) => { delete pair[key]; });
        expect(run(input, evidence)).toThrow(/pair comparison/);
      }
    });
  });

  it("rejects C cut geometry without a new closed support record", () => {
    const input = specimen(); const evidence = batch(input, ["C"]); evidence.cases[0]!.omissionSupport = null;
    expect(() => inferQualificationOutputV2(input.document, input.dependencies, evidence)).toThrow(/unique supported A\/B\/C/);
  });

  it("keeps the pure CLI request closed", () => {
    const input = specimen(); const evidence = batch(input, ["A"]);
    const request = {
      schemaVersion: "qualification-output-pure-request/v1", mode: "infer", document: input.document, dependencies: input.dependencies,
      evidence, preparedMedia: [], handoff: null, inferenceDecision: null, inferenceHistory: [], candidate: null, decision: null, history: [],
    };
    const raw = JSON.stringify(request);
    expect(parseQualificationOutputPureRequest(new TextEncoder().encode(raw)).mode).toBe("infer");
    expect(() => parseQualificationOutputPureRequest(new TextEncoder().encode(JSON.stringify({ ...request, unexpected: true })))).toThrow(/unsupported qualification output pure request fields/);
    expect(() => parseQualificationOutputPureRequest(new TextEncoder().encode(raw.replace('"mode":"infer"', '"mode":"infer","mode":"infer"')))).toThrow(/duplicate .* JSON key/);
    expect(() => parseQualificationOutputPureRequest(new TextEncoder().encode(JSON.stringify({ ...request,
      document: { ...input.document, unsafeInteger: 9007199254740992 },
    })))).toThrow(/unsafe JSON number/);
  });
});
