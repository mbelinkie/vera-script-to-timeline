/** Test-only A observation from the sanitized #192 specimen; never native evidence. */
import { createHash } from "node:crypto";
import { registerHooks } from "node:module";
import type { QualificationOutputObservationBatchV1 } from "../src/qualification-output-proposals-v2.js";

const contracts = new URL("../", import.meta.url).href;
const hooks = registerHooks({
  resolve(specifier, context, nextResolve) {
    return context.parentURL?.startsWith(contracts) && specifier.startsWith(".") && specifier.endsWith(".js")
      ? nextResolve(specifier.slice(0, -3) + ".ts", context)
      : nextResolve(specifier, context);
  },
});
const { specimen, observations, edits, hash } = await import("./issue-192-case.ts");
const { compileTimelineV2 } = await import("../src/compiler-core-v2.ts");
const { sha256CanonicalJson } = await import("../src/compiler-core.ts");
const { inferQualificationOutputV2 } = await import("../src/qualification-output-proposals-v2.ts");
hooks.deregister();

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

function geometryEnvelope(
  input: ReturnType<typeof specimen>,
  raw: ReturnType<typeof observations>,
  phase: "pristine" | "edited",
) {
  const compiled = compileTimelineV2(input.document, input.dependencies);
  if (!compiled.ok || compiled.report.status !== "ready") throw new Error("sanitized baseline compile failed");
  const manifest = compiled.manifest;
  const nativeSourceRows = new Map<string, { sourceId: string; nativeSourceSha256: string }>();
  for (const item of raw.items) nativeSourceRows.set(item.sourceId, { sourceId: item.sourceId, nativeSourceSha256: bare(item.sourceHash) });
  const audioItems = new Map<string, ReturnType<typeof observations>["items"][number]>();
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
    return {
      trackId: sourceTrack.id, kind: track.kind, index: track.index, name: track.name,
      enabled: track.enabled, locked: track.locked,
    };
  }).sort((a, b) => a.trackId.localeCompare(b.trackId));
  const items = raw.items.map((item) => {
    const event = manifest.events.find((row) => row.eventId === item.eventId);
    if (!event) throw new Error("sanitized event mapping missing");
    const sourceMappingSha256 = item.kind === "video"
      ? nativeSourceRows.get(item.sourceId)!.nativeSourceSha256
      : sourceEntriesById.get(item.sourceId)!.pcmMappingSha256;
    return {
      itemUid: item.itemUid, eventId: item.eventId, sourceId: item.sourceId, mediaUid: item.mediaUid,
      kind: item.kind, trackId: event.trackId, recordStart: item.recordStart,
      recordDuration: item.recordEnd - item.recordStart, sourceStart: item.sourceStart,
      sourceDuration: item.sourceEnd - item.sourceStart, linkedItemUids: [...item.linkedUids].sort(),
      online: item.online, enabled: item.enabled, speed: item.speed, sourceMappingSha256,
    };
  }).sort((a, b) => a.recordStart - b.recordStart || a.itemUid.localeCompare(b.itemUid));
  const target = {
    projectName: "Sanitized output specimen", projectUid: "project-215-sanitized",
    timelineName: "Timeline 215", timelineUid: "timeline-215-sanitized",
  };
  const hashFields = [
    "originalDocumentSha256", "originalDependenciesSha256", "executionDocumentSha256", "executionDependenciesSha256",
    "packageSha256", "preflightSha256", "manifestSha256", "reportSha256", "preparationSha256",
    "hostSourceGraphSha256", "nativeSourceGraphSha256", "installedReleaseSha256", "runtimeSha256", "profileSha256",
  ];
  const context: Record<string, unknown> = {
    lane: "bounded_output_residual_consistency", invocationId: `invocation-A-${phase}`, caseId: "isolated-A", phase, target,
    ...Object.fromEntries(hashFields.map((key) => [key, bare(hash(`isolated-A:${key}`))])),
    binding: { kind: "baseline" },
  };
  const documentHash = bare(sha256CanonicalJson(input.document));
  const dependenciesHash = bare(sha256CanonicalJson(input.dependencies));
  context.originalDocumentSha256 = documentHash;
  context.executionDocumentSha256 = documentHash;
  context.originalDependenciesSha256 = dependenciesHash;
  context.executionDependenciesSha256 = dependenciesHash;
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
    context, extentFrames: raw.timeline.durationFrames, rate: { numerator: 24000, denominator: 1001 }, tracks, items,
    sourceMappings: sourceEntries.map((source) => ({
      sourceId: source.sourceId, nativeSourceSha256: source.nativeSourceSha256, sourceEntrySha256: pythonHash(source),
    })),
  };
  return {
    envelope: {
      schemaVersion: "qualification-output-geometry/v1", lane: "bounded_output_residual_consistency", geometry,
      inputBindingSha256: rawHash(inputBindingJson), capturePhase: "pre_render",
      capturedAt: "2026-10-18T12:00:00Z", expiresAt: "2026-10-18T12:05:00Z",
      receiptSha256: bare(hash(`isolated-A:${phase}:receipt`)),
    },
    geometry,
    context,
    inputBindingJson,
  };
}

function comparison(geometry: ReturnType<typeof geometryEnvelope>, phase: "pristine" | "edited") {
  const context = geometry.context;
  const lineage = {
    schemaVersion: "qualification-output-lineage/v1", lane: "bounded_output_residual_consistency", context,
    commitmentRawSha256: bare(hash(`isolated-A:${phase}:commitment`)),
    reservationRawSha256: bare(hash(`isolated-A:${phase}:reservation`)),
    renderIntentSha256: bare(hash(`isolated-A:${phase}:intent`)),
    effectReceiptSha256: bare(hash(`isolated-A:${phase}:effect`)),
    startReceiptSha256: bare(hash(`isolated-A:${phase}:start`)),
    completionReceiptSha256: bare(hash(`isolated-A:${phase}:completion`)),
    jobId: `job-isolated-A-${phase}`, sourceOutputRawSha256: bare(hash(`isolated-A:${phase}:mov`)),
  };
  const metric = (rms: number, sliding: number) => ({
    residualRms: rms, maximumSliding20msResidualRms: sliding, consistent: rms <= 0.0004 && sliding <= 0.006,
  });
  return {
    schemaVersion: "qualification-output-comparison/v1", lane: "bounded_output_residual_consistency",
    context, status: "compared_consistent", commitmentRawSha256: lineage.commitmentRawSha256,
    commitmentPayloadSha256: bare(hash(`isolated-A:${phase}:payload`)), reservationRawSha256: lineage.reservationRawSha256,
    renderLineage: lineage, decodeRecordRawSha256: bare(hash(`isolated-A:${phase}:decode`)),
    preGeometryRawSha256: bare(hash(`isolated-A:${phase}:pre-geometry`)),
    postGeometryRawSha256: bare(hash(`isolated-A:${phase}:post-geometry`)), geometrySha256: pythonHash(geometry.geometry),
    algorithmSha256: bare(hash("214 algorithm")), metrics: [metric(0.0001, 0.0002), metric(0.0001, 0.0002)],
    signalMetrics: [metric(0.1, 0.2), metric(0.1, 0.2)], priorLedgerHeadSha256: bare(hash(`isolated-A:${phase}:prior-head`)),
    internalControls: "unverified", geometryStability: "not_claimed", controlStability: "not_claimed", futureAuthority: false,
    comparisonReceiptSha256: bare(hash(`isolated-A:${phase}:comparison-receipt`)),
  };
}

const input = specimen();
const pristineRaw = observations(input);
const editedRaw = edits(pristineRaw, "A");
const pristineGeometry = geometryEnvelope(input, pristineRaw, "pristine");
const editedGeometry = geometryEnvelope(input, editedRaw, "edited");
const pristineComparisonJson = JSON.stringify(comparison(pristineGeometry, "pristine"));
const editedComparisonJson = JSON.stringify(comparison(editedGeometry, "edited"));
const sampleCount = pristineGeometry.geometry.extentFrames * 2002;
const evidence: QualificationOutputObservationBatchV1 = {
  schemaVersion: "qualification-output-observation-batch/v1",
  lane: "bounded_output_residual_consistency",
  documentHash: sha256CanonicalJson(input.document),
  dependenciesHash: sha256CanonicalJson(input.dependencies),
  cases: [{
    schemaVersion: "qualification-output-observation/v1", lane: "bounded_output_residual_consistency", caseId: "isolated-A",
    pristineGeometryJson: JSON.stringify(pristineGeometry.envelope), editedGeometryJson: JSON.stringify(editedGeometry.envelope),
    pristineInputBindingJson: pristineGeometry.inputBindingJson, editedInputBindingJson: editedGeometry.inputBindingJson,
    pristineComparisonJson, editedComparisonJson, pairJson: null,
    audioEquality: {
      schemaVersion: "qualification-output-audio-equality/v1", lane: "bounded_output_residual_consistency", caseId: "isolated-A",
      pristinePredictionSha256: bare(hash("isolated-A:same-prediction")), editedPredictionSha256: bare(hash("isolated-A:same-prediction")),
      pristineDecodedSamplesSha256: bare(hash("isolated-A:same-decoded")), editedDecodedSamplesSha256: bare(hash("isolated-A:same-decoded")),
      predictionByteLength: sampleCount * 16, decodedSampleByteLength: sampleCount * 8, sampleCount,
    },
    omissionSupport: null,
  }],
};
const inference = inferQualificationOutputV2(input.document, input.dependencies, evidence);
const inferenceDecision = {
  schemaVersion: "qualification-output-decision/v1", proposalHash: inference.inferenceHash,
  historyHash: sha256CanonicalJson([]), outcome: "accept",
};
process.stdout.write(JSON.stringify({ document: input.document, dependencies: input.dependencies, evidence, inferenceDecision }));
