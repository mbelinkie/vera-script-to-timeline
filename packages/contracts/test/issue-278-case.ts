/** Sanitized, synthetic anchored C case for the #278 Python/TypeScript seam. */
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";
import { pathToFileURL } from "node:url";
import type { NarrationBlockV2, NarrationBoundaryEvidenceV1 } from "../src/generated/contracts-v2.js";
import type { QualificationOutputObservationBatchV1, QualificationOutputObservationCaseV1 } from "../src/qualification-output-proposals-v2.js";

const contracts = new URL("../", import.meta.url).href;
const hooks = registerHooks({
  resolve(specifier, context, nextResolve) {
    return context.parentURL?.startsWith(contracts) && specifier.startsWith(".") && specifier.endsWith(".js")
      ? nextResolve(specifier.slice(0, -3) + ".ts", context)
      : nextResolve(specifier, context);
  },
});
const { specimen, observations, hash, id } = await import("./issue-192-case.ts");
const { compileTimelineV2 } = await import("../src/compiler-core-v2.ts");
const { sha256CanonicalJson, canonicalJson } = await import("../src/compiler-core.ts");
const { applyVisualSequenceEditV2 } = await import("../src/authoring-v2-edits.ts");
const { wordAnchorForTokenV2 } = await import("../src/authoring-v2-validation.ts");
hooks.deregister();

const LANE = "bounded_output_residual_consistency" as const;
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

function geometryEnvelope(input: ReturnType<typeof specimen>, raw: ReturnType<typeof observations>, phase: "pristine" | "edited") {
  const compiled = compileTimelineV2(input.document, input.dependencies);
  if (!compiled.ok || compiled.report.status !== "ready") throw new Error("sanitized baseline compile failed");
  const manifest = compiled.manifest;
  const nativeSourceRows = new Map<string, { sourceId: string; nativeSourceSha256: string }>();
  for (const item of raw.items) nativeSourceRows.set(item.sourceId, { sourceId: item.sourceId, nativeSourceSha256: bare(item.sourceHash) });
  const audioItems = new Map<string, ReturnType<typeof observations>["items"][number]>();
  for (const item of raw.items.filter((row) => row.kind === "audio")) audioItems.set(item.sourceId, item);
  const sourceEntries = [...audioItems].map(([sourceId, item]) => ({
    sourceId, nativeSourceSha256: nativeSourceRows.get(sourceId)!.nativeSourceSha256, pcmMode: "wav-direct",
    provenanceReceiptSha256: bare(hash(`entry:${sourceId}:receipt`)), provenancePinsSha256: bare(hash(`entry:${sourceId}:pins`)),
    deliveryDerivationSha256: bare(hash(`entry:${sourceId}:delivery`)), pcmFileSha256: bare(input.dependencies.narrationBoundaryEvidence![0]!.audioHash),
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
  const target = { projectName: "Sanitized output specimen", projectUid: "project-278-sanitized", timelineName: "Timeline 278", timelineUid: "timeline-278-sanitized" };
  const hashFields = ["originalDocumentSha256", "originalDependenciesSha256", "executionDocumentSha256", "executionDependenciesSha256", "packageSha256", "preflightSha256",
    "manifestSha256", "reportSha256", "preparationSha256", "hostSourceGraphSha256", "nativeSourceGraphSha256", "installedReleaseSha256", "runtimeSha256", "profileSha256"];
  const context: Record<string, unknown> = {
    lane: LANE, invocationId: `invocation-278-${phase}`, caseId: "anchored-C", phase, target,
    ...Object.fromEntries(hashFields.map((key) => [key, bare(hash(`anchored-C:${key}`))])), binding: { kind: "baseline" },
  };
  const documentHash = bare(sha256CanonicalJson(input.document));
  const dependenciesHash = bare(sha256CanonicalJson(input.dependencies));
  context.originalDocumentSha256 = documentHash; context.executionDocumentSha256 = documentHash;
  context.originalDependenciesSha256 = dependenciesHash; context.executionDependenciesSha256 = dependenciesHash;
  const projection = Object.fromEntries(Object.entries(context).filter(([key]) => !["preflightSha256", "preparationSha256", "invocationId"].includes(key)));
  projection.binding = { kind: "baseline" };
  context.binding = { kind: "baseline", bindingSha256: pythonHash(projection) };
  const delivery = manifest.events.filter((event) => event.kind !== "script_marker").map((event) => {
    const start = event.recordRange.startFrame; const duration = event.recordRange.endFrame - start;
    const sourceStart = event.sourceRange?.startFrame ?? 0;
    const sourceDuration = event.sourceRange === null ? duration : event.sourceRange.endFrame - sourceStart;
    return { eventId: event.eventId, kind: event.kind, recordRange: { startFrame: start, durationFrames: duration }, sourceRange: { startFrame: sourceStart, durationFrames: sourceDuration } };
  }).sort((a, b) => a.eventId.localeCompare(b.eventId));
  const nativeSources = [...nativeSourceRows.values()].sort((a, b) => a.sourceId.localeCompare(b.sourceId));
  const itemMappings = items.map(({ itemUid, eventId, sourceId, mediaUid }) => ({ itemUid, eventId, sourceId, mediaUid })).sort((a, b) => a.itemUid.localeCompare(b.itemUid));
  const inputBindingJson = JSON.stringify(pythonSorted({ schemaVersion: "qualification-output-inputs/v1", lane: LANE, context, delivery, sourceEntries, tracks, itemMappings, nativeSources }));
  const geometry = {
    context, extentFrames: raw.timeline.durationFrames, rate: { numerator: 24000, denominator: 1001 }, tracks, items,
    sourceMappings: sourceEntries.map((source) => ({ sourceId: source.sourceId, nativeSourceSha256: source.nativeSourceSha256, sourceEntrySha256: pythonHash(source) })),
  };
  const envelope = {
    schemaVersion: "qualification-output-geometry/v1", lane: LANE, geometry, inputBindingSha256: rawHash(inputBindingJson), capturePhase: "pre_render",
    capturedAt: "2026-10-18T12:00:00Z", expiresAt: "2026-10-18T12:05:00Z", receiptSha256: bare(hash(`anchored-C:${phase}:receipt`)),
  };
  return { envelope, geometry, context, inputBindingJson };
}

function comparison(geometry: ReturnType<typeof geometryEnvelope>, phase: "pristine" | "edited") {
  const context = geometry.context;
  const lineage = {
    schemaVersion: "qualification-output-lineage/v1", lane: LANE, context,
    commitmentRawSha256: bare(hash(`anchored-C:${phase}:commitment`)), reservationRawSha256: bare(hash(`anchored-C:${phase}:reservation`)),
    renderIntentSha256: bare(hash(`anchored-C:${phase}:intent`)), effectReceiptSha256: bare(hash(`anchored-C:${phase}:effect`)),
    startReceiptSha256: bare(hash(`anchored-C:${phase}:start`)), completionReceiptSha256: bare(hash(`anchored-C:${phase}:completion`)),
    jobId: `job-anchored-C-${phase}`, sourceOutputRawSha256: bare(hash(`anchored-C:${phase}:mov`)),
  };
  const metric = (rms: number, sliding: number) => ({ residualRms: rms, maximumSliding20msResidualRms: sliding, consistent: rms <= 0.0004 && sliding <= 0.006 });
  return {
    schemaVersion: "qualification-output-comparison/v1", lane: LANE, context, status: "compared_consistent",
    commitmentRawSha256: lineage.commitmentRawSha256, commitmentPayloadSha256: bare(hash(`anchored-C:${phase}:payload`)), reservationRawSha256: lineage.reservationRawSha256,
    renderLineage: lineage, decodeRecordRawSha256: bare(hash(`anchored-C:${phase}:decode`)),
    preGeometryRawSha256: bare(hash(`anchored-C:${phase}:pre-geometry`)), postGeometryRawSha256: bare(hash(`anchored-C:${phase}:post-geometry`)),
    geometrySha256: pythonHash(geometry.geometry), algorithmSha256: bare(hash("214 algorithm")),
    metrics: [metric(0.0001, 0.0002), metric(0.0001, 0.0002)], signalMetrics: [metric(0.1, 0.2), metric(0.1, 0.2)],
    priorLedgerHeadSha256: bare(hash(`anchored-C:${phase}:prior-head`)), internalControls: "unverified", geometryStability: "not_claimed",
    controlStability: "not_claimed", futureAuthority: false, comparisonReceiptSha256: bare(hash(`anchored-C:${phase}:comparison-receipt`)),
  };
}

function pairRecord(pristineJson: string, editedJson: string, pristineFrames: number, editedFrames: number) {
  const differs = { residualRms: 0.001, maximumSliding20msResidualRms: 0.007, consistent: false };
  return JSON.stringify({
    schemaVersion: "qualification-output-pair/v1", lane: LANE,
    pristineComparisonRawSha256: rawHash(pristineJson), editedComparisonRawSha256: rawHash(editedJson),
    pristineLedgerHeadSha256: bare(hash("anchored-C:pristine-ledger")), editedLedgerHeadSha256: bare(hash("anchored-C:edited-ledger")),
    pristineSampleCount: pristineFrames * 2002, editedSampleCount: editedFrames * 2002,
    commonInterval: { startSample: 0, endSample: Math.min(pristineFrames, editedFrames) * 2002 },
    crossMetrics: { predictionDifference: [differs, differs], editedAgainstPristine: [differs, differs], pristineAgainstEdited: [differs, differs] },
    internalControls: "unverified", geometryStability: "not_claimed", controlStability: "not_claimed", futureAuthority: false,
  });
}

function boundaryEvidence(input: ReturnType<typeof specimen>): QualificationOutputObservationCaseV1["omissionSupport"] {
  const row = input.document.activeDraft.blocks.find((block): block is NarrationBlockV2 => block.type === "narration" && block.id === id(10))!;
  const measured = input.dependencies.narrationBoundaryEvidence!.find((record) => record.blockId === row.id)!;
  const verification = measured.verification as { measurementArtifactHash: string; onsetUncertainty: unknown; audibleEndUncertainty: unknown };
  const support: Record<string, unknown> = {
    schemaVersion: "qualification-output-omission-support/v2", lane: LANE, caseId: "anchored-C",
    documentHash: sha256CanonicalJson(input.document), dependenciesHash: sha256CanonicalJson(input.dependencies),
    blockId: row.id, blockRevision: row.version, method: "measured_audio_boundaries/v1",
    selectedTokenId: row.tokens[8]!.id, leftNeighborTokenId: row.tokens[7]!.id, rightNeighborTokenId: row.tokens[9]!.id,
    boundaryEvidenceHash: sha256CanonicalJson(measured), measurementArtifactHash: verification.measurementArtifactHash,
    audioSha256: bare(measured.audioHash), timingHash: bare(measured.timingHash), onsetUncertainty: verification.onsetUncertainty,
    audibleEndUncertainty: verification.audibleEndUncertainty, nativeFrameOrigin: 0, pcmSampleOrigin: 0,
    cutRecordFrames: { startFrame: 55, endFrame: 72 }, cutSourceFrames: { startFrame: 55, endFrame: 72 },
    cutSamples: { startSample: 55 * 2002, endSample: 72 * 2002 },
    cutStartEnvelope: { minSample: 106555, maxSample: 112795 }, cutEndEnvelope: { minSample: 140635, maxSample: 146971 },
    pristineGeometryRawSha256: "", editedGeometryRawSha256: "", pristineComparisonRawSha256: "", editedComparisonRawSha256: "", pairRawSha256: "",
  };
  return support as unknown as QualificationOutputObservationCaseV1["omissionSupport"];
}

export function boundaryChoiceCase() {
  const input = specimen();
  const row = input.document.activeDraft.blocks.find((block): block is NarrationBlockV2 => block.type === "narration" && block.id === id(10))!;
  const measured = JSON.parse(readFileSync(new URL("./data/issue182-baseline.boundary-evidence.json", import.meta.url), "utf8")) as NarrationBoundaryEvidenceV1;
  const campaignDocument = JSON.parse(readFileSync(new URL("../../../tests/data/issue182/campaign/baseline.v2.script-document.json", import.meta.url), "utf8")) as { activeDraft: { blocks: { text: string }[] } };
  const campaignText = campaignDocument.activeDraft.blocks[0]!.text;
  let cursor = 0;
  const tokens = measured.tokens.map((mark, index) => {
    const startOffset = campaignText.indexOf(mark.quotedText, cursor); cursor = startOffset + mark.quotedText.length;
    return { id: id(1000 + index), value: mark.quotedText, startOffset, endOffset: cursor };
  });
  row.text = campaignText; row.tokens = [tokens[0]!, ...tokens.slice(1)];
  const narrationEvidence = structuredClone(measured);
  narrationEvidence.blockId = row.id; narrationEvidence.blockRevision = row.version; narrationEvidence.textHash = hash(campaignText);
  narrationEvidence.tokens = measured.tokens.map((mark, index) => ({ ...structuredClone(mark), tokenId: tokens[index]!.id, startOffset: tokens[index]!.startOffset, endOffset: tokens[index]!.endOffset }));
  input.dependencies.narrationBoundaryEvidence![0] = narrationEvidence;
  const baseSlot = row.primaryVisualSequence!.slots[0]!;
  if (baseSlot.kind !== "content") throw new Error("narration base visual slot missing");
  baseSlot.payload = { kind: "on_camera", presenterChoiceId: null };
  const primarySequenceId = row.primaryVisualSequence!.id;
  input.dependencies.occurrenceResolutions = input.dependencies.occurrenceResolutions.filter((entry) =>
    entry.owner.kind !== "primary_slot" || entry.owner.sequenceId !== primarySequenceId || entry.owner.slotId !== baseSlot.id);
  input.dependencies.preparedMedia = input.dependencies.preparedMedia.filter((binding) => binding.requirementKey !== "192:prep:30");
  input.dependencies.document.textHash = hash(`${row.text}\n${(input.document.activeDraft.blocks.find((block) => block.id === id(20)) as NarrationBlockV2).text}`);

  const initialSequence = row.primaryVisualSequence!;
  const inserted = applyVisualSequenceEditV2(input.document, initialSequence.version, {
    kind: "insert_sequential", blockId: row.id,
    boundary: wordAnchorForTokenV2(row, row.tokens[8]!.id, 1, "before")!,
    slotId: id(278), payload: { kind: "on_camera", presenterChoiceId: null },
  });
  if (!inserted.ok) throw new Error(`could not add synthetic visual boundary: ${canonicalJson(inserted.diagnostics)}`);
  input.document = inserted.document;
  const boundRow = input.document.activeDraft.blocks.find((block): block is NarrationBlockV2 => block.type === "narration" && block.id === id(10))!;
  const checkedCompile = compileTimelineV2(input.document, input.dependencies);
  if (!checkedCompile.ok || checkedCompile.report.status !== "ready") {
    throw new Error(JSON.stringify({ diagnostics: checkedCompile.ok ? checkedCompile.report.diagnostics : checkedCompile.diagnostics, status: checkedCompile.ok ? checkedCompile.report.status : "invalid" }));
  }
  const pristineRaw = observations(input);
  const editedRaw = structuredClone(pristineRaw);
  const narrationItem = editedRaw.items.find((item) => item.authoredEvent.kind === "narration" && item.recordStart === 0)!;
  const left = structuredClone(narrationItem); const right = structuredClone(narrationItem);
  left.itemUid += ":left"; left.recordEnd = 55; left.sourceEnd = left.sourceStart + 55; left.rawRecordEnd = 54;
  right.itemUid += ":right"; right.recordStart = 72; right.sourceStart += 72;
  editedRaw.items.splice(editedRaw.items.indexOf(narrationItem), 1, left, right);

  const pristine = geometryEnvelope(input, pristineRaw, "pristine"); const edited = geometryEnvelope(input, editedRaw, "edited");
  const pristineComparisonJson = JSON.stringify(comparison(pristine, "pristine"));
  const editedComparisonJson = JSON.stringify(comparison(edited, "edited"));
  const pairJson = pairRecord(pristineComparisonJson, editedComparisonJson, pristine.geometry.extentFrames, edited.geometry.extentFrames);
  const omissionSupport = boundaryEvidence(input)! as unknown as Record<string, unknown>;
  omissionSupport.pristineGeometryRawSha256 = rawHash(JSON.stringify(pristine.envelope));
  omissionSupport.editedGeometryRawSha256 = rawHash(JSON.stringify(edited.envelope));
  omissionSupport.pristineComparisonRawSha256 = rawHash(pristineComparisonJson);
  omissionSupport.editedComparisonRawSha256 = rawHash(editedComparisonJson);
  omissionSupport.pairRawSha256 = rawHash(pairJson);
  const evidence: QualificationOutputObservationBatchV1 = {
    schemaVersion: "qualification-output-observation-batch/v1", lane: LANE,
    documentHash: sha256CanonicalJson(input.document), dependenciesHash: sha256CanonicalJson(input.dependencies),
    cases: [{
      schemaVersion: "qualification-output-observation/v1", lane: LANE, caseId: "anchored-C",
      pristineGeometryJson: JSON.stringify(pristine.envelope), editedGeometryJson: JSON.stringify(edited.envelope),
      pristineInputBindingJson: pristine.inputBindingJson, editedInputBindingJson: edited.inputBindingJson,
      pristineComparisonJson, editedComparisonJson, pairJson, audioEquality: null,
      omissionSupport: omissionSupport as unknown as QualificationOutputObservationCaseV1["omissionSupport"],
    }],
  };
  return { document: input.document, dependencies: input.dependencies, evidence, boundaryOwnerId: id(278), tokenId: boundRow.tokens[8]!.id };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.stdout.write(JSON.stringify(boundaryChoiceCase()));
}
