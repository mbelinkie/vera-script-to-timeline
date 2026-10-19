import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";
import { sha256CanonicalJson } from "../src/compiler-core.js";
import { compileTimelineV2 } from "../src/compiler-core-v2.js";
import type { NarrationBlockV2 } from "../src/generated/contracts-v2.js";
import type { RowHandoffV2 } from "../src/issue-189-v2-replacement.js";
import {
  decideQualificationOutputV2,
  createQualificationOutputProposalV2,
  inferQualificationOutputV2,
  parseQualificationOutputPureRequest,
  stageQualificationOutputV2,
  type QualificationOutputObservationBatchV1,
  type QualificationOutputObservationCaseV1,
  type QualificationOutputAudioEqualityV1,
} from "../src/qualification-output-proposals-v2.js";
import { edits, hash, observations, specimen, timing, type FakeRaw } from "./issue-192-case.js";

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

function geometryEnvelope(input: ReturnType<typeof specimen>, raw: FakeRaw, phase: "pristine" | "edited", caseId: string,
  executionDiffers = false) {
  const compiled = compileTimelineV2(input.document, input.dependencies);
  if (!compiled.ok || compiled.report.status !== "ready") throw new Error("sanitized baseline compile failed");
  const manifest = compiled.manifest;
  const nativeSourceRows = new Map<string, { sourceId: string; nativeSourceSha256: string }>();
  for (const item of raw.items) nativeSourceRows.set(item.sourceId, { sourceId: item.sourceId, nativeSourceSha256: bare(item.sourceHash) });
  const audioItems = new Map<string, FakeRaw["items"][number]>();
  for (const item of raw.items.filter((row) => row.kind === "audio")) audioItems.set(item.sourceId, item);
  const sourceEntries = [...audioItems].map(([sourceId, item]) => ({
    sourceId, nativeSourceSha256: nativeSourceRows.get(sourceId)!.nativeSourceSha256, pcmMode: "prepared-audio",
    provenanceReceiptSha256: bare(hash(`entry:${sourceId}:receipt`)), provenancePinsSha256: bare(hash(`entry:${sourceId}:pins`)),
    deliveryDerivationSha256: bare(hash(`entry:${sourceId}:delivery`)), pcmFileSha256: bare(hash(`entry:${sourceId}:pcm-file`)),
    decodedSamplesSha256: bare(hash(`entry:${sourceId}:samples`)), originalBitDepth: 24, channels: 1,
    durationSamples: 4_000_000, sampleRate: 48000,
    pcmMappingSha256: bare(item.sourceHash), nativeFrameOrigin: 0, pcmSampleOrigin: 0,
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

function newCase(input: ReturnType<typeof specimen>, kind: "A" | "B" | "C", executionDiffers = false, uncutC = false): QualificationOutputObservationCaseV1 {
  const pristineRaw = observations(input);
  const editedRaw = edits(pristineRaw, uncutC ? "A" : kind);
  const caseId = `isolated-${kind}`;
  const pristineGeometry = geometryEnvelope(input, pristineRaw, "pristine", caseId, executionDiffers);
  const editedGeometry = geometryEnvelope(input, editedRaw, "edited", caseId, executionDiffers);
  const pristineComparisonJson = JSON.stringify(comparison(pristineGeometry, "pristine", caseId));
  const editedComparisonJson = JSON.stringify(comparison(editedGeometry, "edited", caseId));
  const pairJson = kind === "A" ? null : pairRecord(pristineComparisonJson, editedComparisonJson, caseId, pristineGeometry.geometry.extentFrames, editedGeometry.geometry.extentFrames);
  let omissionSupport: QualificationOutputObservationCaseV1["omissionSupport"] = null;
  if (kind === "C" && !uncutC) {
    const row = input.document.activeDraft.blocks.find((block): block is NarrationBlockV2 => block.type === "narration" && block.tokens.length > 12)!;
    const boundary = input.dependencies.narrationBoundaryEvidence!.find((record) => record.blockId === row.id)!;
    const compiled = compileTimelineV2(input.document, input.dependencies);
    if (!compiled.ok) throw new Error("sanitized C compile failed");
    const rowEventId = compiled.manifest.events.find((event) => event.kind === "narration" && event.provenance.blockId === row.id)!.eventId;
    const left = editedGeometry.geometry.items.find((item) => item.eventId === rowEventId && item.recordStart === 0)!;
    const right = editedGeometry.geometry.items.find((item) => item.eventId === left.eventId && item.recordStart > left.recordStart)!;
    const nativeFrameOrigin = 3;
    const pcmSampleOrigin = 37;
    const cutStartSamples = (left.sourceStart + left.sourceDuration - nativeFrameOrigin) * 2002 + pcmSampleOrigin;
    const cutEndSamples = (right.sourceStart - nativeFrameOrigin) * 2002 + pcmSampleOrigin;
    omissionSupport = {
      schemaVersion: "qualification-output-omission-support/v1", lane: "bounded_output_residual_consistency", caseId,
      documentHash: sha256CanonicalJson(input.document), dependenciesHash: sha256CanonicalJson(input.dependencies),
      blockId: row.id, blockRevision: row.version, selectedTokenId: row.tokens[11]!.id, leftNeighborTokenId: row.tokens[10]!.id, rightNeighborTokenId: row.tokens[12]!.id,
      nativeFrameOrigin, pcmSampleOrigin,
      leftNeighborSourceInterval: { startSample: 200000, endSample: cutStartSamples - 10 },
      selectedSourceInterval: { startSample: cutStartSamples, endSample: cutEndSamples },
      rightNeighborSourceInterval: { startSample: cutEndSamples + 1, endSample: cutEndSamples + 5000 },
      recordIntervalFrames: { startFrame: left.recordStart + left.recordDuration, endFrame: right.recordStart },
      audioSha256: bare(boundary.audioHash), timingHash: bare(boundary.timingHash), reviewArtifactSha256: bare(boundary.verification.reviewArtifactHash),
      reviewReceiptSha256: bare(hash("independent acoustic/listening review receipt")),
      pristineGeometryRawSha256: rawHash(JSON.stringify(pristineGeometry.envelope)), editedGeometryRawSha256: rawHash(JSON.stringify(editedGeometry.envelope)),
      pristineComparisonRawSha256: rawHash(pristineComparisonJson), editedComparisonRawSha256: rawHash(editedComparisonJson), pairRawSha256: rawHash(pairJson!),
    };
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

function batch(input: ReturnType<typeof specimen>, kinds: ("A" | "B" | "C")[], executionDiffers = false): QualificationOutputObservationBatchV1 {
  return {
    schemaVersion: "qualification-output-observation-batch/v1", lane: "bounded_output_residual_consistency",
    documentHash: sha256CanonicalJson(input.document), dependenciesHash: sha256CanonicalJson(input.dependencies),
    cases: kinds.map((kind) => newCase(input, kind, executionDiffers)),
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
    reviewArtifactHash: boundaryEvidence.verification.reviewArtifactHash, boundaryEvidence,
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
  });

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

  it("requires token 11 plus pinned neighbor listening support before staging C regeneration", () => {
    const input = specimen(); const evidence = batch(input, ["C"]);
    const support = evidence.cases[0]!.omissionSupport!;
    // Speech supports are acoustic sample edges inside a frame-aligned cut;
    // their independent review differs from the prior sparse picture review.
    support.selectedSourceInterval.startSample += 37;
    support.selectedSourceInterval.endSample -= 61;
    support.reviewArtifactSha256 = rawHash("new independent token support review");
    expect([support.nativeFrameOrigin, support.pcmSampleOrigin]).toEqual([3, 37]);
    const inference = inferQualificationOutputV2(input.document, input.dependencies, evidence);
    expect(inference.omission?.tokenIds).toEqual([input.document.activeDraft.blocks.find((b) => b.type === "narration")!.tokens[11]!.id]);
    const decision = accept(inference.inferenceHash);
    const stage = stageQualificationOutputV2(input.document, input.dependencies, evidence, decision, []);
    expect(stage.outcome).toBe("accept");
    expect(stage.regeneration).toMatchObject({ schemaVersion: "qualification-output-regeneration-request/v1", policy: "replace_whole_row" });
    expect(stage.regeneration?.decisionHash).toBe(sha256CanonicalJson(decision));
    const handoff = replacementHandoff(stage);
    const proposal = createQualificationOutputProposalV2(input.document, input.dependencies, evidence, decision, [], [], handoff);
    expect(proposal.schemaVersion).toBe("qualification-output-proposal/v1");
    for (const field of ["nativeFrameOrigin", "pcmSampleOrigin"] as const) {
      const invalidOrigins = structuredClone(evidence);
      invalidOrigins.cases[0]!.omissionSupport![field] += 0.5;
      expect(() => inferQualificationOutputV2(input.document, input.dependencies, invalidOrigins)).toThrow();
    }
    const fractional = structuredClone(handoff);
    fractional.boundaryEvidence.audio.durationSamples += 1;
    expect(() => createQualificationOutputProposalV2(input.document, input.dependencies, evidence, decision, [], [], fractional))
      .toThrow(/fractional whole-row replacement duration refused/);
  });

  it("composes isolated A/B/C commands and stages C before any provider handoff", () => {
    const input = specimen(); const evidence = batch(input, ["A", "B", "C"]);
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

  describe("C one-frame snapped cut (Producer route A)", () => {
    // Token edges relative to the actual native cut: cutStart = start - startGap, cutEnd = end + endGap.
    function snapped(startGap: number, endGap: number, leftOverlap = 0, rightOverlap = 0) {
      const input = specimen(); const evidence = batch(input, ["C"]);
      const support = evidence.cases[0]!.omissionSupport!;
      const cutStart = support.selectedSourceInterval.startSample; const cutEnd = support.selectedSourceInterval.endSample;
      support.selectedSourceInterval = { startSample: cutStart + startGap, endSample: cutEnd - endGap };
      const selected = support.selectedSourceInterval;
      support.leftNeighborSourceInterval = { startSample: 200000, endSample: Math.min(cutStart + leftOverlap, selected.startSample) };
      support.rightNeighborSourceInterval = { startSample: Math.max(cutEnd - rightOverlap, selected.endSample), endSample: cutEnd + 9000 };
      return { input, evidence, support, cutStart, cutEnd };
    }

    it("accepts a -88/+802 snapped cut and reports measured clip and residual samples", () => {
      const { input, evidence, cutStart, cutEnd } = snapped(88, 802);
      const inference = inferQualificationOutputV2(input.document, input.dependencies, evidence);
      expect(inference.omissionMeasurement).toEqual({
        cutStartSample: cutStart, cutEndSample: cutEnd, selectedStartSample: cutStart + 88, selectedEndSample: cutEnd - 802,
        cutStartOffsetSamples: -88, cutEndOffsetSamples: 802,
        leftNeighborClippedSamples: 0, rightNeighborClippedSamples: 0, residualTokenSamplesLeft: 0, residualTokenSamplesRight: 0,
      });
      expect(stageQualificationOutputV2(input.document, input.dependencies, evidence, accept(inference.inferenceHash), []).outcome).toBe("accept");
    });

    it("accepts a neighbor clipped within tolerance and reports residual token samples", () => {
      const { input, evidence, cutStart, cutEnd } = snapped(-300, -400, 0, 0);
      const support = evidence.cases[0]!.omissionSupport!;
      // Cut starts 300 samples inside the token (residue left) and ends 400 samples inside it (residue right).
      support.leftNeighborSourceInterval.endSample = cutStart - 300;
      support.rightNeighborSourceInterval.startSample = cutEnd + 400;
      const inside = inferQualificationOutputV2(input.document, input.dependencies, evidence).omissionMeasurement!;
      expect([inside.residualTokenSamplesLeft, inside.residualTokenSamplesRight]).toEqual([300, 400]);
      const clipped = snapped(88, 802, 50, 70);
      const m = inferQualificationOutputV2(clipped.input.document, clipped.input.dependencies, clipped.evidence).omissionMeasurement!;
      expect([m.leftNeighborClippedSamples, m.rightNeighborClippedSamples]).toEqual([50, 70]);
    });

    it("refuses a cut edge a full frame or more from the reviewed token", () => {
      for (const [startGap, endGap] of [[2002, 0], [-2002, 0], [0, 2002], [0, -2002], [3000, 3000]] as const) {
        const { input, evidence } = snapped(startGap, endGap);
        expect(() => inferQualificationOutputV2(input.document, input.dependencies, evidence)).toThrow(/full frame or more/);
      }
      const edge = snapped(2001, -2001);
      expect(inferQualificationOutputV2(edge.input.document, edge.input.dependencies, edge.evidence).omissionMeasurement).not.toBeNull();
    });

    it("refuses a missing cut", () => {
      const { input, evidence, support } = snapped(88, 802);
      const row = evidence.cases[0]!;
      // Replace the edited side with an uncut capture (the edited A-shaped geometry) and re-pin every raw hash.
      const uncut = newCase(input, "C", false, true);
      row.editedGeometryJson = uncut.editedGeometryJson; row.editedInputBindingJson = uncut.editedInputBindingJson;
      row.editedComparisonJson = uncut.editedComparisonJson;
      row.pairJson = pairRecord(row.pristineComparisonJson, row.editedComparisonJson, row.caseId, pairFrames(row, "pristine"), pairFrames(row, "edited"));
      support.editedGeometryRawSha256 = rawHash(row.editedGeometryJson); support.editedComparisonRawSha256 = rawHash(row.editedComparisonJson);
      support.pairRawSha256 = rawHash(row.pairJson);
      expect(() => inferQualificationOutputV2(input.document, input.dependencies, evidence)).toThrow(/two new UIDs/);
    });

    it("refuses downstream ripple", () => {
      const { input, evidence } = snapped(88, 802);
      const row = evidence.cases[0]!;
      const envelope = JSON.parse(row.editedGeometryJson) as { geometry: { items: { recordStart: number; recordDuration: number; eventId: string }[] } };
      const eventIds = new Set(envelope.geometry.items.map((item) => item.eventId));
      const later = envelope.geometry.items.filter((item) => item.recordStart > 0).sort((a, b) => b.recordStart - a.recordStart)[0]!;
      expect(eventIds.size).toBeGreaterThan(1);
      later.recordStart += 1;
      row.editedGeometryJson = JSON.stringify(envelope);
      expect(() => inferQualificationOutputV2(input.document, input.dependencies, evidence)).toThrow(/unsupported item interval|ripple/);
    });
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
