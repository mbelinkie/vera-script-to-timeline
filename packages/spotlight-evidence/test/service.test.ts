import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

import {
  PINNED_VISION_PROFILE,
  SpotlightEvidenceService,
  SpotlightError,
  frozenVisionResponse,
  type FrozenOcrResponse,
  type RasterRef,
} from "../src/index.js";

const digest = (letter: string) => `sha256:${letter.repeat(64)}`;
const PROJECT = "11111111-1111-4111-8111-111111111111";
const AUTHORIZATION = digest("c");
const REQUEST = digest("d");

function raster(revision: string, value: string): RasterRef {
  return { projectId: PROJECT, captureRevisionId: revision, rasterArtifactId: `artifact-${revision}`, rasterDigest: digest(value), width: 160, height: 40 };
}

function response(words: readonly string[]): FrozenOcrResponse {
  const positions = words.map((text, index) => ({
    granularity: "word" as const, rawOrdinal: index + 1, text,
    lineRawOrdinal: 0, confidenceMillionths: null,
    rect: { leftMicros: (index * 10) * 1_000_000, topMicros: 5 * 1_000_000, rightMicros: (index * 10 + 8) * 1_000_000, bottomMicros: 15 * 1_000_000 },
  }));
  return {
    rawResponseBytes: Buffer.from(JSON.stringify(words), "utf8"),
    elements: [{ granularity: "line", rawOrdinal: 0, text: words.join(" "), confidenceMillionths: 900_000, rect: { leftMicros: 0, topMicros: 5_000_000, rightMicros: words.length * 10_000_000, bottomMicros: 15_000_000 } }, ...positions],
  };
}

function service() {
  let sequence = 0;
  return new SpotlightEvidenceService({ id: () => `00000000-0000-4000-8000-${String(++sequence).padStart(12, "0")}`, now: () => new Date("2026-09-09T12:00:00.000Z") });
}

function errorCode(operation: () => unknown): string {
  try {
    operation();
  } catch (error) {
    if (error instanceof SpotlightError) return error.code;
    throw error;
  }
  throw new Error("Expected SpotlightError");
}

function batchFor(target: SpotlightEvidenceService, capture: RasterRef, words = ["Synthetic", "Review", "required", "before", "adjustment"]) {
  return target.recordFrozenOcr({ raster: capture, authorizationDigest: AUTHORIZATION, requestDigest: REQUEST, profile: PINNED_VISION_PROFILE, response: response(words) }).batch;
}

describe("Issue 41 Spotlight OCR evidence and supervised remap backend", () => {
  it.each(["clean-page", "mixed-layout", "multilingual", "scaled-rotated", "unreadable"])("canonicalizes the retained local Vision %s fixture deterministically", (fixture) => {
    const bytes = readFileSync(new URL(`../../../docs/investigations/issue-105-spotlight-ocr-engine/outputs/apple-vision/${fixture}.json`, import.meta.url));
    const parsed = JSON.parse(bytes.toString("utf8")) as { rasterWidth: number; rasterHeight: number; words: unknown[]; lines: unknown[] };
    const sourceRaster: RasterRef = { projectId: PROJECT, captureRevisionId: "44444444-4444-4444-8444-444444444444", rasterArtifactId: `artifact-${fixture}`, rasterDigest: digest("f"), width: parsed.rasterWidth, height: parsed.rasterHeight };
    const one = service().recordFrozenOcr({ raster: sourceRaster, authorizationDigest: AUTHORIZATION, requestDigest: REQUEST, profile: PINNED_VISION_PROFILE, response: frozenVisionResponse(bytes, sourceRaster) }).batch;
    const two = service().recordFrozenOcr({ raster: sourceRaster, authorizationDigest: AUTHORIZATION, requestDigest: REQUEST, profile: PINNED_VISION_PROFILE, response: frozenVisionResponse(bytes, sourceRaster) }).batch;
    expect(one.elements).toHaveLength(parsed.words.length + parsed.lines.length);
    expect(one.evidenceDigest).toBe(two.evidenceDigest);
    expect(one.elements.map(({ elementId }) => elementId)).toEqual(two.elements.map(({ elementId }) => elementId));
  });

  it("keeps frozen local OCR deterministic, provenance-complete, and unconfirmed", () => {
    const first = service();
    const second = service();
    const capture = raster("revision-a", "a");
    const batchA = batchFor(first, capture);
    const batchB = batchFor(second, capture);

    expect(batchA.evidenceDigest).toBe(batchB.evidenceDigest);
    expect(batchA.elements.map(({ elementId }) => elementId)).toEqual(batchB.elements.map(({ elementId }) => elementId));
    expect(batchA.profile).toEqual(PINNED_VISION_PROFILE);
    const proposal = first.proposeOcr(batchA.recordId, "word", batchA.elements.filter(({ granularity }) => granularity === "word").slice(1, 3).map(({ elementId }) => elementId));
    expect(errorCode(() => first.derive({ confirmationId: proposal.recordId }))).toBe("evidence_not_found");
    expect(first.repository.records().map(({ recordType }) => recordType)).toEqual(["ocr_attempt_evidence", "ocr_evidence_batch", "automated_target_proposal"]);
  });

  it("only derives a bright target from an explicit human confirmation or manual geometry", () => {
    const target = service();
    const batch = batchFor(target, raster("revision-a", "a"));
    const proposal = target.proposeOcr(batch.recordId, "word", batch.elements.filter(({ granularity }) => granularity === "word").slice(1, 3).map(({ elementId }) => elementId));
    expect(errorCode(() => target.confirm({ proposalId: proposal.recordId, actorId: "service", actorKind: "service", authorizationDigest: AUTHORIZATION, expectedBindingSequence: 0 }))).toBe("confirmation_required");
    const confirmation = target.confirm({ proposalId: proposal.recordId, actorId: "editor-1", actorKind: "editor", authorizationDigest: AUTHORIZATION, expectedBindingSequence: 0 });
    const derived = target.derive({ confirmationId: confirmation.recordId, parameters: { dimAlpha: 191, paddingPx: 0 } });
    expect(derived.matteBytes.some((value) => value === 0)).toBe(true);
    expect(derived.matteBytes.some((value) => value === 191)).toBe(true);
    expect(derived.wrapperDigest).toMatch(/^sha256:/);

    const manual = target.proposeManual(raster("revision-manual", "b"), { x: 5, y: 5, width: 10, height: 10 });
    const manualConfirmation = target.confirm({ proposalId: manual.recordId, actorId: "producer-1", actorKind: "producer", authorizationDigest: AUTHORIZATION, expectedBindingSequence: 1 });
    expect(target.derive({ confirmationId: manualConfirmation.recordId }).matteDigest).toMatch(/^sha256:/);
  });

  it("makes unique recapture matches proposed and ambiguity stale without a new artifact", () => {
    const target = service();
    const repeating = ["Review", "required", "Review", "required", "Review", "required"];
    const firstBatch = batchFor(target, raster("revision-a", "a"), repeating);
    const proposal = target.proposeOcr(firstBatch.recordId, "word", firstBatch.elements.filter(({ granularity }) => granularity === "word").slice(2, 4).map(({ elementId }) => elementId));
    const confirmation = target.confirm({ proposalId: proposal.recordId, actorId: "editor-1", actorKind: "editor", authorizationDigest: AUTHORIZATION, expectedBindingSequence: 0 });
    const secondRaster = raster("revision-b", "b");
    const secondBatch = batchFor(target, secondRaster, repeating);
    const unique = target.assessRemap({ oldConfirmationId: confirmation.recordId, newBatchId: secondBatch.recordId, newRaster: secondRaster });
    expect(unique.outcome).toBe("unique_candidate");
    expect(errorCode(() => target.derive({ confirmationId: unique.recordId }))).toBe("evidence_not_found");
    const accepted = target.decideRemap({ remapProposalId: unique.recordId, decision: "accept_remap", actorId: "editor-1", actorKind: "editor", authorizationDigest: AUTHORIZATION, expectedBindingSequence: 1 });
    expect(accepted.confirmation).not.toBeNull();
    expect(target.derive({ confirmationId: accepted.confirmation!.recordId }).matteDigest).toMatch(/^sha256:/);

    const ambiguousRaster = raster("revision-c", "e");
    const ambiguousBatch = batchFor(target, ambiguousRaster, ["Review", "required", "Review", "required", "Review", "required", "Review", "required", "Review", "required"]);
    const ambiguous = target.assessRemap({ oldConfirmationId: confirmation.recordId, newBatchId: ambiguousBatch.recordId, newRaster: ambiguousRaster });
    expect(ambiguous.outcome).toBe("stale_ambiguous");
    expect(errorCode(() => target.decideRemap({ remapProposalId: ambiguous.recordId, decision: "accept_remap", actorId: "editor-1", actorKind: "editor", authorizationDigest: AUTHORIZATION, expectedBindingSequence: 2 }))).toBe("spotlight_stale");
  });

  it("fails closed for invalid geometry and an unapproved engine profile", () => {
    const target = service();
    const capture = raster("revision-a", "a");
    expect(errorCode(() => target.recordFrozenOcr({ raster: capture, authorizationDigest: AUTHORIZATION, requestDigest: REQUEST, profile: { ...PINNED_VISION_PROFILE, profileVersion: "2" }, response: response(["Synthetic"]) }))).toBe("engine_profile_unavailable");
    const invalid: FrozenOcrResponse = { rawResponseBytes: Buffer.from("bad"), elements: [{ granularity: "line", rawOrdinal: 0, text: "Bad", confidenceMillionths: 1, rect: { leftMicros: 0, topMicros: 0, rightMicros: 161_000_000, bottomMicros: 1_000_000 } }] };
    expect(() => target.recordFrozenOcr({ raster: capture, authorizationDigest: AUTHORIZATION, requestDigest: REQUEST, profile: PINNED_VISION_PROFILE, response: invalid })).toThrow(SpotlightError);
  });

  it("records terminal failures and never turns missing, contradictory, or manual evidence into a remap", () => {
    const target = service();
    const oldRaster = raster("revision-a", "a");
    const oldBatch = batchFor(target, oldRaster);
    const proposal = target.proposeOcr(oldBatch.recordId, "word", oldBatch.elements.filter(({ granularity }) => granularity === "word").slice(1, 3).map(({ elementId }) => elementId));
    const confirmation = target.confirm({ proposalId: proposal.recordId, actorId: "editor-1", actorKind: "editor", authorizationDigest: AUTHORIZATION, expectedBindingSequence: 0 });
    const missingRaster = raster("revision-b", "b");
    const missing = target.assessRemap({ oldConfirmationId: confirmation.recordId, newBatchId: batchFor(target, missingRaster, ["No", "matching", "text"]).recordId, newRaster: missingRaster });
    expect(missing.outcome).toBe("stale_missing");
    const contradictoryRaster = raster("revision-c", "c");
    const contradictory = target.assessRemap({ oldConfirmationId: confirmation.recordId, newBatchId: batchFor(target, contradictoryRaster, ["Changed", "Review", "required", "later", "context"]).recordId, newRaster: contradictoryRaster });
    expect(contradictory.outcome).toBe("stale_contradictory");
    const manual = target.proposeManual(oldRaster, { x: 1, y: 1, width: 4, height: 4 });
    const manualConfirmation = target.confirm({ proposalId: manual.recordId, actorId: "editor-1", actorKind: "editor", authorizationDigest: AUTHORIZATION, expectedBindingSequence: 1 });
    const manualRaster = raster("revision-d", "d");
    const manualRemap = target.assessRemap({ oldConfirmationId: manualConfirmation.recordId, newBatchId: batchFor(target, manualRaster).recordId, newRaster: manualRaster });
    expect(manualRemap.outcome).toBe("stale_manual_redraw_required");
    const failure = target.recordOcrFailure({ raster: raster("revision-e", "e"), authorizationDigest: AUTHORIZATION, requestDigest: REQUEST, profile: PINNED_VISION_PROFILE, terminalCode: "engine_unavailable" });
    expect(failure).toMatchObject({ outcome: "failed", terminalCode: "engine_unavailable", batchId: null });
  });
});
