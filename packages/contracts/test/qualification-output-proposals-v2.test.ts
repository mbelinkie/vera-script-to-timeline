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
  const sourceRows = new Map<string, { sourceId: string; nativeSourceSha256: string; sourceEntrySha256: string }>();
  for (const item of raw.items) sourceRows.set(item.sourceId, {
    sourceId: item.sourceId,
    nativeSourceSha256: bare(item.sourceHash),
    sourceEntrySha256: bare(hash(`entry:${item.sourceId}`)),
  });
  const tracks = raw.tracks.map((track) => {
    const sourceTrack = manifest.tracks.find((row) => row.kind === track.kind && row.index === track.index);
    if (!sourceTrack) throw new Error("sanitized track mapping missing");
    return { trackId: sourceTrack.id, kind: track.kind, index: track.index, name: track.name, enabled: track.enabled, locked: track.locked };
  }).sort((a, b) => a.trackId.localeCompare(b.trackId));
  const items = raw.items.map((item) => {
    const event = manifest.events.find((row) => row.eventId === item.eventId);
    if (!event) throw new Error("sanitized event mapping missing");
    const sourceMappingSha256 = item.kind === "video" ? sourceRows.get(item.sourceId)!.nativeSourceSha256 : bare(item.sourceHash);
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
  const geometry = {
    context, extentFrames: raw.timeline.durationFrames, rate: { numerator: 24000, denominator: 1001 }, tracks,
    items, sourceMappings: [...sourceRows.values()].sort((a, b) => a.sourceId.localeCompare(b.sourceId)),
  };
  const envelope = {
    schemaVersion: "qualification-output-geometry/v1", lane: "bounded_output_residual_consistency", geometry,
    inputBindingSha256: bare(hash(`${caseId}:${phase}:input-binding`)), capturePhase: "pre_render",
    capturedAt: "2026-10-18T12:00:00Z", expiresAt: "2026-10-18T12:05:00Z", receiptSha256: bare(hash(`${caseId}:${phase}:receipt`)),
  };
  return { envelope, geometry, context };
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

function pairRecord(pristineComparisonJson: string, editedComparisonJson: string, caseId: string) {
  const differs = { residualRms: 0.001, maximumSliding20msResidualRms: 0.007, consistent: false };
  const pair = {
    schemaVersion: "qualification-output-pair/v1", lane: "bounded_output_residual_consistency",
    pristineComparisonRawSha256: rawHash(pristineComparisonJson), editedComparisonRawSha256: rawHash(editedComparisonJson),
    pristineLedgerHeadSha256: bare(hash(`${caseId}:pristine-ledger`)), editedLedgerHeadSha256: bare(hash(`${caseId}:edited-ledger`)),
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

function newCase(input: ReturnType<typeof specimen>, kind: "A" | "B" | "C", executionDiffers = false): QualificationOutputObservationCaseV1 {
  const pristineRaw = observations(input);
  const editedRaw = edits(pristineRaw, kind);
  if (kind === "B") editedRaw.timeline.durationFrames = pristineRaw.timeline.durationFrames; // Real B retains the original extent and ends with silence.
  const caseId = `isolated-${kind}`;
  const pristineGeometry = geometryEnvelope(input, pristineRaw, "pristine", caseId, executionDiffers);
  const editedGeometry = geometryEnvelope(input, editedRaw, "edited", caseId, executionDiffers);
  const pristineComparisonJson = JSON.stringify(comparison(pristineGeometry, "pristine", caseId));
  const editedComparisonJson = JSON.stringify(comparison(editedGeometry, "edited", caseId));
  const pairJson = kind === "A" ? null : pairRecord(pristineComparisonJson, editedComparisonJson, caseId);
  let omissionSupport: QualificationOutputObservationCaseV1["omissionSupport"] = null;
  if (kind === "C") {
    const row = input.document.activeDraft.blocks.find((block): block is NarrationBlockV2 => block.type === "narration" && block.tokens.length > 12)!;
    const boundary = input.dependencies.narrationBoundaryEvidence!.find((record) => record.blockId === row.id)!;
    const compiled = compileTimelineV2(input.document, input.dependencies);
    if (!compiled.ok) throw new Error("sanitized C compile failed");
    const rowEventId = compiled.manifest.events.find((event) => event.kind === "narration" && event.provenance.blockId === row.id)!.eventId;
    const left = editedGeometry.geometry.items.find((item) => item.eventId === rowEventId && item.recordStart === 0)!;
    const right = editedGeometry.geometry.items.find((item) => item.eventId === left.eventId && item.recordStart > left.recordStart)!;
    omissionSupport = {
      schemaVersion: "qualification-output-omission-support/v1", lane: "bounded_output_residual_consistency", caseId,
      documentHash: sha256CanonicalJson(input.document), dependenciesHash: sha256CanonicalJson(input.dependencies),
      blockId: row.id, blockRevision: row.version, selectedTokenId: row.tokens[11]!.id, leftNeighborTokenId: row.tokens[10]!.id, rightNeighborTokenId: row.tokens[12]!.id,
      leftNeighborSourceInterval: { startSample: 200000, endSample: 240000 },
      selectedSourceInterval: { startSample: (left.sourceStart + left.sourceDuration) * 2002, endSample: right.sourceStart * 2002 },
      rightNeighborSourceInterval: { startSample: right.sourceStart * 2002 + 1, endSample: right.sourceStart * 2002 + 5000 },
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
    pristineComparisonJson, editedComparisonJson, pairJson,
    audioEquality: kind === "A" ? equality(caseId, pristineGeometry.geometry.extentFrames) : null,
    omissionSupport,
  };
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

  it("preserves distinct authenticated original/execution pins and rejects pair pin disagreement", () => {
    const input = specimen();
    const valid = batch(input, ["B"], true);
    expect(inferQualificationOutputV2(input.document, input.dependencies, valid).caseKinds).toEqual(["B"]);

    const mismatched = batch(input, ["B"], true);
    const row = mismatched.cases[0]!;
    const editedEnvelope = JSON.parse(row.editedGeometryJson) as { geometry: { context: Record<string, unknown> } };
    const context = editedEnvelope.geometry.context;
    context.originalDocumentSha256 = bare(hash("different authenticated original document"));
    context.originalDependenciesSha256 = bare(hash("different authenticated original dependencies"));
    const projection = Object.fromEntries(Object.entries(context).filter(([key]) =>
      !["preflightSha256", "preparationSha256", "invocationId"].includes(key)));
    projection.binding = { kind: "baseline" };
    context.binding = { kind: "baseline", bindingSha256: pythonHash(projection) };
    row.editedGeometryJson = JSON.stringify(editedEnvelope);

    const editedComparison = JSON.parse(row.editedComparisonJson) as {
      context: Record<string, unknown>; renderLineage: { context: Record<string, unknown> }; geometrySha256: string;
    };
    editedComparison.context = structuredClone(context);
    editedComparison.renderLineage.context = structuredClone(context);
    editedComparison.geometrySha256 = pythonHash(editedEnvelope.geometry);
    row.editedComparisonJson = JSON.stringify(editedComparison);
    row.pairJson = pairRecord(row.pristineComparisonJson, row.editedComparisonJson, row.caseId);

    expect(() => inferQualificationOutputV2(input.document, input.dependencies, mismatched))
      .toThrow(/pristine\/edited authenticated input identities differ/);
  }, 15000);

  it("derives an AV end trim from geometry while preserving the original extent as a silence tail", () => {
    const input = specimen(); const inference = inferQualificationOutputV2(input.document, input.dependencies, batch(input, ["B"]));
    expect(inference.caseKinds).toEqual(["B"]);
    expect(inference.commands.trim?.blockId).toEqual(expect.any(String));
    expect(inference.commands.trim).toMatchObject({ expectedBlockVersion: 1, durationFrames: 67 });
    expect(inference.commands.boundary).toBeNull();
    const stage = stageQualificationOutputV2(input.document, input.dependencies, batch(input, ["B"]), accept(inference.inferenceHash), []);
    expect(stage.outcome).toBe("accept");
    const trimmed = stage.document.activeDraft.blocks.find((block) => block.id === inference.commands.trim?.blockId);
    expect(trimmed?.type === "visual_only" ? trimmed.visualOnlyTiming.selectedSourceRange?.durationFrames : null).toBe(67);
  }, 15000);

  it("requires token 11 plus pinned neighbor listening support before staging C regeneration", () => {
    const input = specimen(); const evidence = batch(input, ["C"]);
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
