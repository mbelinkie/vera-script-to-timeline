import { describe, expect, it } from "vitest";
import { sha256CanonicalJson } from "../src/compiler-core.js";
import { applyAcceptedOmissionV2 } from "../src/issue-189-v2-omission.js";
import {
  createQualificationOutputProposalV2,
  decideQualificationOutputV2,
  inferQualificationOutputV2,
  stageQualificationOutputV2,
} from "../src/qualification-output-proposals-v2.js";
import { boundaryChoiceCase } from "./issue-278-case.js";
import { hash, rational, timing } from "./issue-192-case.js";

function accept(proposalHash: string, history: string[] = [], boundaryChoice?: unknown) {
  return {
    schemaVersion: "qualification-output-decision/v1" as const,
    proposalHash,
    historyHash: sha256CanonicalJson(history),
    outcome: "accept" as const,
    ...(boundaryChoice === undefined ? {} : { boundaryChoice }),
  };
}

function freshTiming(row: Parameters<typeof timing>[0], frames: number) {
  const evidence = timing(row, frames, true);
  const denominator = 2 * row.tokens.length + 2;
  evidence.tokens = row.tokens.map((token, index) => ({
    tokenId: token.id,
    quotedText: token.value,
    startOffset: token.startOffset,
    endOffset: token.endOffset,
    onset: rational(evidence.audio.durationSamples * (2 * index + 1), evidence.audio.sampleRate * denominator),
    audibleEnd: rational(evidence.audio.durationSamples * (2 * index + 2), evidence.audio.sampleRate * denominator),
  }));
  return evidence;
}

describe("#278 omitted-word visual boundary choice", () => {
  it("lets the authenticated A boundary move resolve the C omission anchor", () => {
    const input = boundaryChoiceCase(true);
    const inference = inferQualificationOutputV2(input.document, input.dependencies, input.evidence);
    const originalRow = input.document.activeDraft.blocks.find((block) => block.type === "narration");
    if (originalRow?.type !== "narration") throw new Error("baseline narration row missing");
    expect(inference.caseKinds).toEqual(["A", "C"]);
    expect(inference.commands.boundary).toMatchObject({
      kind: "move_word_boundary",
      blockId: originalRow.id,
      boundaryOwnerId: input.boundaryOwnerId,
      tokenId: originalRow.tokens[7]!.id,
      affinity: "before",
    });
    expect(inference.omission?.tokenIds).toContain(input.tokenId);
    expect(inference.boundaryConflicts).toEqual([]);

    const stage = stageQualificationOutputV2(input.document, input.dependencies, input.evidence, accept(inference.inferenceHash), []);
    expect(stage.outcome).toBe("accept");
    expect(stage.decision.boundaryChoice).toBeUndefined();
    const row = stage.document.activeDraft.blocks.find((block) => block.type === "narration");
    if (row?.type !== "narration") throw new Error("staged narration row missing");
    const movedOwner = row.primaryVisualSequence?.slots.find((slot) => slot.id === input.boundaryOwnerId);
    expect(movedOwner?.kind === "content" && "anchor" in movedOwner.boundaryBefore ? movedOwner.boundaryBefore.anchor : null).toMatchObject({
      tokenId: row.tokens[7]!.id,
      affinity: "before",
    });
    expect(row.tokens.some((token) => token.id === input.tokenId)).toBe(false);
    expect(stage.regeneration?.blockRevision).toBe(row.version);
  }, 60000);

  it("requires one exact surviving choice and applies it before the omission", () => {
    const input = boundaryChoiceCase();
    const inference = inferQualificationOutputV2(input.document, input.dependencies, input.evidence);
    expect(inference.caseKinds).toEqual(["C"]);
    expect(inference.commands.boundary).toBeNull();
    expect(inference.omission?.tokenIds).toContain(input.tokenId);
    expect(inference.boundaryConflicts).toHaveLength(1);
    expect(inference.boundaryConflicts[0]).toMatchObject({
      blockId: input.document.activeDraft.blocks.find((block) => block.type === "narration")!.id,
      boundaryOwnerId: input.boundaryOwnerId,
      tokenId: input.tokenId,
      expectedSequenceVersion: input.document.activeDraft.blocks.find((block) => block.type === "narration")?.primaryVisualSequence?.version,
    });
    expect(inference.boundaryConflicts[0]!.choices.length).toBeGreaterThan(0);
    const { inferenceHash, ...inferenceBody } = inference;
    expect(sha256CanonicalJson(inferenceBody)).toBe(inferenceHash);

    const choice = inference.boundaryConflicts[0]!.choices[0]!;
    const decision = accept(inference.inferenceHash, [], choice);
    const stage = stageQualificationOutputV2(input.document, input.dependencies, input.evidence, decision, []);
    expect(stage.outcome).toBe("accept");
    expect(stage.decision).toEqual(decision);
    expect(stage.regeneration?.decisionHash).toBe(sha256CanonicalJson(decision));
    const row = stage.document.activeDraft.blocks.find((block) => block.type === "narration" && block.id === choice.blockId);
    expect(row?.type).toBe("narration");
    if (row?.type !== "narration") throw new Error("staged narration row missing");
    const owner = row.primaryVisualSequence?.slots.find((slot) => slot.id === choice.boundaryOwnerId);
    expect(owner?.kind === "content" && "anchor" in owner.boundaryBefore ? owner.boundaryBefore.anchor : null).toMatchObject({
      tokenId: choice.tokenId,
      affinity: choice.affinity,
    });
    expect(row.tokens.some((token) => token.id === input.tokenId)).toBe(false);
    expect(stage.regeneration?.blockRevision).toBe(row.version);
    expect(stage.regeneration?.text).not.toContain("slowly");
  }, 60000);

  it("keeps a conflict undecided or rejected without changing document or dependencies", () => {
    const input = boundaryChoiceCase();
    const inference = inferQualificationOutputV2(input.document, input.dependencies, input.evidence);
    expect(() => stageQualificationOutputV2(input.document, input.dependencies, input.evidence, accept(inference.inferenceHash), []))
      .toThrow(/boundary choice/);
    const rejected = {
      schemaVersion: "qualification-output-decision/v1" as const,
      proposalHash: inference.inferenceHash,
      historyHash: sha256CanonicalJson([]),
      outcome: "reject" as const,
    };
    const stage = stageQualificationOutputV2(input.document, input.dependencies, input.evidence, rejected, []);
    expect(stage.outcome).toBe("reject");
    expect(stage.document).toBe(input.document);
    expect(stage.dependencies).toBe(input.dependencies);
    expect(stage.regeneration).toBeNull();
  }, 60000);

  it("refuses altered, removed, unknown, stale and replayed choices before staging", () => {
    const input = boundaryChoiceCase();
    const inference = inferQualificationOutputV2(input.document, input.dependencies, input.evidence);
    const legal = inference.boundaryConflicts[0]!.choices[0]!;
    const narration = input.document.activeDraft.blocks.find((block) => block.type === "narration");
    if (narration?.type !== "narration") throw new Error("narration row missing");
    const collapsedBoundary = { ...legal, tokenId: narration.tokens[0].id, affinity: "before" };
    expect(inference.boundaryConflicts[0]!.choices).not.toContainEqual(collapsedBoundary);
    for (const boundaryChoice of [
      { ...legal, tokenId: input.tokenId },
      { ...legal, tokenId: "00000000-0000-4000-8000-999999999999" },
      { ...legal, expectedSequenceVersion: legal.expectedSequenceVersion + 1 },
      collapsedBoundary,
      { ...legal, affinity: "sideways" },
    ]) {
      expect(() => stageQualificationOutputV2(input.document, input.dependencies, input.evidence,
        accept(inference.inferenceHash, [], boundaryChoice), [])).toThrow(/boundary choice/);
    }

    expect(() => stageQualificationOutputV2(input.document, input.dependencies, input.evidence,
      accept(inference.inferenceHash, [inference.inferenceHash], legal), [inference.inferenceHash])).toThrow(/history/);

    const alteredEvidence = structuredClone(input.evidence);
    alteredEvidence.cases[0]!.omissionSupport!.audioSha256 = "0".repeat(64);
    expect(() => stageQualificationOutputV2(input.document, input.dependencies, alteredEvidence,
      accept(inference.inferenceHash, [], legal), [])).toThrow(/omission support differs/);
  }, 60000);

  it("keeps the strict omission transform and seals the selected choice into proposals", () => {
    const input = boundaryChoiceCase();
    const inference = inferQualificationOutputV2(input.document, input.dependencies, input.evidence);
    const omission = inference.omission!;
    expect(() => applyAcceptedOmissionV2(input.document, {
      schemaVersion: "issue-189-v2-accepted-omission/v1", expectedDocumentHash: sha256CanonicalJson(input.document),
      blockId: omission.blockId, blockRevision: omission.blockRevision, tokenIds: omission.tokenIds,
      evidenceHash: omission.evidenceHash, decisionHash: hash("legacy strict omission"),
    })).toThrow(/removed anchor word is unsupported/);

    const originalRow = input.document.activeDraft.blocks.find((block) => block.type === "narration");
    if (originalRow?.type !== "narration") throw new Error("narration row missing");
    const removedIndex = originalRow.tokens.findIndex((token) => token.id === input.tokenId);
    const leftNeighbor = originalRow.tokens[removedIndex - 1];
    const choice = inference.boundaryConflicts[0]!.choices.find((candidate) =>
      candidate.tokenId === leftNeighbor?.id && candidate.affinity === "before");
    if (!choice) throw new Error("left-neighbor boundary choice missing");
    const inferenceDecision = accept(inference.inferenceHash, [], choice);
    const stage = stageQualificationOutputV2(input.document, input.dependencies, input.evidence, inferenceDecision, []);
    const request = stage.regeneration!;
    const row = stage.document.activeDraft.blocks.find((block) => block.type === "narration" && block.id === request.blockId);
    if (row?.type !== "narration") throw new Error("staged narration row missing");
    const boundaryEvidence = freshTiming(row, 200);
    const handoff = {
      schemaVersion: "issue-189-v2-row-handoff/v1" as const,
      request: {
        schemaVersion: "issue-189-v2-row-request/v1" as const, policy: "replace_whole_row" as const,
        blockId: request.blockId, blockRevision: request.blockRevision, text: request.text, textHash: request.textHash,
        revisedDocumentHash: request.revisedDocumentHash, evidenceHash: request.evidenceHash, decisionHash: request.decisionHash,
      },
      priorDependenciesHash: sha256CanonicalJson(stage.dependencies), serviceRequestHash: hash("synthetic C service request"),
      generationReceiptHash: hash("synthetic C generation receipt"), assetRecordHash: hash("synthetic C asset record"),
      audioHash: boundaryEvidence.audioHash, providerTimingHash: boundaryEvidence.timingHash,
      reviewArtifactHash: (boundaryEvidence.verification as { reviewArtifactHash: string }).reviewArtifactHash, boundaryEvidence,
    };
    const candidate = createQualificationOutputProposalV2(input.document, input.dependencies, input.evidence,
      inferenceDecision, [], [], handoff);
    expect(candidate.request.commands.boundary).toEqual(choice);
    expect(candidate.inferenceDecision.boundaryChoice).toEqual(choice);
    const decision = accept(candidate.proposalHash);
    expect(decideQualificationOutputV2(input.document, input.dependencies, input.evidence, candidate, decision, []).outcome).toBe("accept");

    const tampered = structuredClone(candidate);
    tampered.request.commands.boundary!.affinity = tampered.request.commands.boundary!.affinity === "before" ? "after" : "before";
    expect(() => decideQualificationOutputV2(input.document, input.dependencies, input.evidence, tampered, decision, []))
      .toThrow(/proposal\/evidence\/revision identity changed/);
    const tamperedDecision = structuredClone(candidate);
    tamperedDecision.inferenceDecision.boundaryChoice!.affinity =
      tamperedDecision.inferenceDecision.boundaryChoice!.affinity === "before" ? "after" : "before";
    expect(() => decideQualificationOutputV2(input.document, input.dependencies, input.evidence, tamperedDecision, decision, []))
      .toThrow(/matching whole-row handoff required/);
  }, 60000);
});
