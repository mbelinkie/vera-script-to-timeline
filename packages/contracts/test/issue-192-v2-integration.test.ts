import { describe, expect, it } from "vitest";
import { canonicalJson, sha256CanonicalJson } from "../src/compiler-core.js";
import { compileTimelineV2 } from "../src/compiler-core-v2.js";
import type { NarrationBlockV2 } from "../src/generated/contracts-v2.js";
import type { RowHandoffV2 } from "../src/issue-189-v2-replacement.js";
import { createInferredRevisionV2, decideInferredRevisionV2, inferCompositionV2, prepareInferredRevisionV2, proposeV2Edits } from "../src/issue-192-v2-proposals.js";
import { edits, evidence, hash, id, observations, patches, specimen, timing, type FakeRaw } from "./issue-192-case.js";

const fakeAuthentication = () => { /* Synthetic geometry tests only, no external qualification. */ };
function caseEvidence(input: ReturnType<typeof specimen>, kind: "A" | "B" | "C") {
  const raw = observations(input); return evidence(input, raw, edits(raw, kind), kind === "C");
}
function composed(d1: number) {
  const input = specimen(); const cases = ["A", "B", "C"].map((kind) => caseEvidence(input, kind as "A" | "B" | "C"));
  const inference = inferCompositionV2(input.document, input.dependencies, cases, fakeAuthentication);
  const preparedMedia = patches(input, d1); const decisionHash = hash("explicit fake C decision");
  const stage = prepareInferredRevisionV2(input.document, input.dependencies, inference, preparedMedia, decisionHash);
  const row = stage.document.activeDraft.blocks.find((b) => b.id === id(10)) as NarrationBlockV2;
  const fresh = timing(row, d1, true);
  const handoff: RowHandoffV2 = { schemaVersion: "issue-189-v2-row-handoff/v1", request: stage.regeneration!,
    priorDependenciesHash: sha256CanonicalJson(stage.dependencies), serviceRequestHash: hash("fake service request"), generationReceiptHash: hash("fake actual receipt"),
    assetRecordHash: hash("fake asset record"), audioHash: fresh.audioHash, providerTimingHash: fresh.timingHash,
    reviewArtifactHash: fresh.verification.reviewArtifactHash, boundaryEvidence: fresh };
  const candidate = createInferredRevisionV2(input.document, input.dependencies, cases, fakeAuthentication,
    { preparedMedia, handoff }, decisionHash);
  return { input, cases, candidate, handoff, stage, preparedMedia, decisionHash };
}
describe("#192 independent native-derived inference (sanitized fake only)", () => {
  it("derives A's exact owner/token/affinity/version from the observed boundary", () => {
    const input = specimen(); const bytes = canonicalJson(input);
    const e = caseEvidence(input, "A"); const inferred = proposeV2Edits(input.document, input.dependencies, e, fakeAuthentication);
    expect(inferred.commands.boundary).toEqual({ kind: "move_word_boundary", blockId: id(20), boundaryOwnerId: id(23),
      tokenId: id(2034), affinity: "before", expectedSequenceVersion: 1 });
    expect(inferred.commands.trim).toBeNull(); expect(inferred.omission).toBeNull();
    const { proposal } = createInferredRevisionV2(input.document, input.dependencies, e, fakeAuthentication, { preparedMedia: [], handoff: null }, "");
    expect(proposal.manifest.timeline.durationFrames).toBe(1107);
    expect(proposal.manifest.events.find((event) => event.provenance.slotId === id(22))!.recordRange).toEqual({ startFrame: 311, endFrame: 569 });
    expect(proposal.manifest.events.find((event) => event.provenance.slotId === id(23))!.recordRange).toEqual({ startFrame: 569, endFrame: 592 });
    expect(proposal.manifest.events.find((event) => event.provenance.slotId === id(24))!.recordRange.startFrame).toBe(592);
    const before = compileTimelineV2(input.document, input.dependencies); if (!before.ok) throw new Error("baseline");
    expect(proposal.manifest.events.filter((event) => event.provenance.blockId !== id(20))).toEqual(before.manifest.events.filter((event) => event.provenance.blockId !== id(20)));
    expect(canonicalJson(input)).toBe(bytes);
  });
  it("derives only reciprocal B trim and the explicit final shift", () => {
    const input = specimen(); const e = caseEvidence(input, "B");
    const inferred = proposeV2Edits(input.document, input.dependencies, e, fakeAuthentication);
    expect(inferred.commands.trim).toEqual({ blockId: id(50), expectedBlockVersion: 1, expectedSelectedRange: { startFrame: 2664, durationFrames: 92 }, durationFrames: 67 });
    expect(inferred.commands.boundary).toBeNull();
    const { proposal } = createInferredRevisionV2(input.document, input.dependencies, e, fakeAuthentication, { preparedMedia: patches(input).slice(1), handoff: null }, "");
    expect(proposal.manifest.timeline.durationFrames).toBe(1082);
    for (const kind of ["primary_visual", "source_audio"]) {
      expect(proposal.manifest.events.find((event) => event.kind === kind && event.provenance.blockId === id(50))!.recordRange).toEqual({ startFrame: 952, endFrame: 1019 });
      expect(proposal.manifest.events.find((event) => event.kind === kind && event.provenance.blockId === id(60))!.recordRange).toEqual({ startFrame: 1019, endFrame: 1082 });
    }
    expect(proposal.manifest.events.find((event) => event.kind === "primary_visual" && event.provenance.blockId === id(50))!.sourceRange).toEqual({ startFrame: 2664, endFrame: 2731 });
    expect(proposal.manifest.events.find((event) => event.kind === "primary_visual" && event.provenance.blockId === id(60))!.sourceRange).toEqual({ startFrame: 396, endFrame: 459 });
  });
  it("consumes isolated C token11 evidence and retains neighbors without guessing D1", () => {
    const input = specimen(); const e = caseEvidence(input, "C");
    const inferred = inferCompositionV2(input.document, input.dependencies, e, fakeAuthentication);
    expect(inferred.omission?.tokenIds).toEqual([id(1011)]);
    const stage = prepareInferredRevisionV2(input.document, input.dependencies, inferred, [], hash("fake accepted C"));
    const row = stage.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(row.tokens.map((t) => t.id)).not.toContain(id(1011));
    expect(row.tokens.map((t) => t.id)).toEqual(expect.arrayContaining([id(1010), id(1012)]));
    expect(stage.regeneration?.policy).toBe("replace_whole_row");
    expect(stage.regeneration?.revisedDocumentHash).toBe(sha256CanonicalJson(stage.document));
  });
  it.each([187, 200, 213])("composes isolated A/B/C using actual fresh row duration %i", (d1) => {
    const c = composed(d1); const beforeBytes = canonicalJson(c.input); const delta = d1 - 200;
    const { proposal } = c.candidate;
    expect(proposal.manifest.timeline.durationFrames).toBe(1082 + delta);
    expect(proposal.manifest.events.find((e) => e.kind === "narration" && e.provenance.blockId === id(10))!.recordRange).toEqual({ startFrame: 0, endFrame: d1 });
    expect(proposal.manifest.events.find((e) => e.provenance.slotId === id(22))!.recordRange).toEqual({ startFrame: 311 + delta, endFrame: 569 + delta });
    expect(proposal.manifest.events.find((e) => e.provenance.slotId === id(23))!.recordRange).toEqual({ startFrame: 569 + delta, endFrame: 592 + delta });
    for (const kind of ["primary_visual", "source_audio"]) {
      expect(proposal.manifest.events.find((e) => e.kind === kind && e.provenance.blockId === id(50))!.recordRange).toEqual({ startFrame: 952 + delta, endFrame: 1019 + delta });
      expect(proposal.manifest.events.find((e) => e.kind === kind && e.provenance.blockId === id(60))!.recordRange).toEqual({ startFrame: 1019 + delta, endFrame: 1082 + delta });
    }
    expect(c.handoff.priorDependenciesHash).toBe(sha256CanonicalJson(c.stage.dependencies));
    expect(proposal.comparisonText).toContain("| Change | Before | After |");
    expect(proposal.comparisonText).toContain(String(1082 + delta));
    expect(proposal.document.activeDraft.blocks.at(-1)).toEqual(c.input.document.activeDraft.blocks.at(-1));
    const decision = { schemaVersion: "issue-202-v2-decision/v1" as const, proposalHash: proposal.proposalHash, historyHash: sha256CanonicalJson([]), outcome: "accept" as const };
    const result = decideInferredRevisionV2(c.input.document, c.input.dependencies, c.cases, fakeAuthentication, c.candidate, decision, []);
    expect(result.document).toEqual(proposal.document);
    expect(canonicalJson(c.input)).toBe(beforeBytes);
  });
  it("rejects through #202 without changing original objects or allowing duplicate consumption", () => {
    const input = specimen(); const e = caseEvidence(input, "A");
    const candidate = createInferredRevisionV2(input.document, input.dependencies, e, fakeAuthentication, { preparedMedia: [], handoff: null }, "");
    const decision = { schemaVersion: "issue-202-v2-decision/v1" as const, proposalHash: candidate.proposal.proposalHash,
      historyHash: sha256CanonicalJson([]), outcome: "reject" as const };
    const result = decideInferredRevisionV2(input.document, input.dependencies, e, fakeAuthentication, candidate, decision, []);
    expect(result.document).toBe(input.document); expect(result.dependencies).toBe(input.dependencies);
    expect(() => decideInferredRevisionV2(input.document, input.dependencies, e, fakeAuthentication, candidate,
      { ...decision, historyHash: sha256CanonicalJson(result.history) }, result.history)).toThrow(/already decided/);
  });
  it.each(["picture-only", "missing-shift", "extra-ripple", "wrong-owner", "duplicate", "missing", "nonreciprocal", "disabled", "offline", "speed", "source", "track", "marker", "target", "extra-field"])("refuses independent %s native delta", (attack) => {
    const input = specimen(); const bytes = canonicalJson(input); const raw = observations(input); const after = edits(raw, "B");
    const video = after.items.find((i) => i.kind === "video" && i.recordStart === 952)!;
    if (attack === "picture-only") {
      const audio = after.items.find((i) => i.kind === "audio" && i.recordStart === 952)!; audio.recordEnd += 25; audio.sourceEnd += 25; audio.rawRecordEnd += 25;
    } else if (attack === "missing-shift") for (const i of after.items.filter((i) => i.recordStart === 1019)) { i.recordStart += 25; i.recordEnd += 25; i.rawRecordEnd += 25; }
    else if (attack === "extra-ripple") after.items[0]!.recordStart += 1;
    else if (attack === "wrong-owner") video.authoredEvent.provenance.blockId = id(60);
    else if (attack === "duplicate") after.items.push(structuredClone(video));
    else if (attack === "missing") after.items.splice(after.items.indexOf(video), 1);
    else if (attack === "nonreciprocal") video.linkedUids = [];
    else if (attack === "disabled") video.enabled = false;
    else if (attack === "offline") video.online = false;
    else if (attack === "speed") video.rawSpeedOptions.Percentage = 99;
    else if (attack === "source") video.sourceHash = hash("substituted source");
    else if (attack === "track") after.tracks[0]!.locked = !after.tracks[0]!.locked;
    else if (attack === "marker") after.markers = { invented: true };
    else if (attack === "target") after.target.timelineUid = "wrong-target";
    else Object.assign(video, { unexpected: true });
    expect(() => proposeV2Edits(input.document, input.dependencies, evidence(input, raw, after), fakeAuthentication)).toThrow();
    expect(canonicalJson(input)).toBe(bytes);
  });
  it("refuses stale/hash/control/receipt/authentication and unexplained audio facts", () => {
    const input = specimen(); const valid = caseEvidence(input, "A");
    const attacks = [
      (e: typeof valid) => { e.documentHash = hash("old document"); },
      (e: typeof valid) => { e.dependenciesHash = hash("old dependencies"); },
      (e: typeof valid) => { e.current.rawJson += " "; },
      (e: typeof valid) => { const raw = JSON.parse(e.current.rawJson) as FakeRaw;
        const receipt = JSON.parse(e.current.receiptJson) as Record<string, unknown>;
        receipt.mappingHash = sha256CanonicalJson(Object.fromEntries(raw.items.map((i) => [i.itemUid, { eventId: i.eventId, sourceId: i.sourceId }])));
        e.current.receiptJson = canonicalJson(receipt); },
      (e: typeof valid) => { const r = JSON.parse(e.current.receiptJson) as Record<string, unknown>; r.adjacentConsistent = false; e.current.receiptJson = canonicalJson(r); },
      (e: typeof valid) => { const r = JSON.parse(e.current.rawJson) as FakeRaw; r.controls.routes[0]!.controls.solo = true;
        e.current.rawJson = canonicalJson(r); const receipt = JSON.parse(e.current.receiptJson) as Record<string, unknown>; receipt.rawHash = hash(e.current.rawJson); e.current.receiptJson = canonicalJson(receipt); },
      (e: typeof valid) => { const r = JSON.parse(e.current.audioJson) as { routes: { segments: { recordStart: number }[] }[] }; r.routes[0]!.segments[0]!.recordStart += 1;
        e.current.audioJson = canonicalJson(r); const receipt = JSON.parse(e.current.receiptJson) as Record<string, unknown>; receipt.derivedAudioHash = hash(e.current.audioJson); e.current.receiptJson = canonicalJson(receipt); },
    ];
    for (const mutate of attacks) { const e = structuredClone(valid); mutate(e); expect(() => proposeV2Edits(input.document, input.dependencies, e, fakeAuthentication)).toThrow(); }
    expect(() => proposeV2Edits(input.document, input.dependencies, valid, () => { throw new Error("untrusted authority"); })).toThrow("untrusted authority");
  });
  it("refuses combined native C, duplicate inference, unverified/extra token C and stale handoff", () => {
    const input = specimen(); const raw = observations(input);
    expect(() => proposeV2Edits(input.document, input.dependencies, evidence(input, raw, edits(raw, "ABC"), true), fakeAuthentication)).toThrow(/isolated/);
    const a = caseEvidence(input, "A"); expect(() => inferCompositionV2(input.document, input.dependencies, [a, a], fakeAuthentication)).toThrow(/duplicate/);
    for (const mutate of [(e: ReturnType<typeof caseEvidence>) => { e.omission!.status = "refused"; },
      (e: ReturnType<typeof caseEvidence>) => { e.omission!.tokenIds = [id(1011), id(1012)]; },
      (e: ReturnType<typeof caseEvidence>) => { e.omission!.currentHash = hash("stale audio"); }]) {
      const c = caseEvidence(input, "C"); mutate(c); expect(() => proposeV2Edits(input.document, input.dependencies, c, fakeAuthentication)).toThrow();
    }
    const c = composed(213); const bad = structuredClone(c.handoff); bad.priorDependenciesHash = hash("baseline, not staged dependencies");
    expect(() => createInferredRevisionV2(c.input.document, c.input.dependencies, c.cases, fakeAuthentication, { preparedMedia: c.preparedMedia, handoff: bad }, c.decisionHash)).toThrow(/prior dependencies/);
    expect(() => createInferredRevisionV2(c.input.document, c.input.dependencies, c.cases, fakeAuthentication, { preparedMedia: c.preparedMedia, handoff: null }, c.decisionHash)).toThrow(/handoff/);
  });
  it("refuses fresh speech whose actual duration outgrows source handles", () => {
    const input = specimen();
    input.dependencies.occurrenceResolutions.find((d) => d.payloadId === id(30))!.logicalSourceBounds.endFrame = 205;
    const cases = ["A", "B", "C"].map((kind) => caseEvidence(input, kind as "A" | "B" | "C"));
    const inference = inferCompositionV2(input.document, input.dependencies, cases, fakeAuthentication);
    const preparedMedia = patches(input, 213); const decisionHash = hash("fake C accepted");
    const stage = prepareInferredRevisionV2(input.document, input.dependencies, inference, preparedMedia, decisionHash);
    const row = stage.document.activeDraft.blocks[0] as NarrationBlockV2; const fresh = timing(row, 213, true);
    const handoff: RowHandoffV2 = { schemaVersion: "issue-189-v2-row-handoff/v1", request: stage.regeneration!,
      priorDependenciesHash: sha256CanonicalJson(stage.dependencies), serviceRequestHash: hash("fake request"), generationReceiptHash: hash("fake receipt"),
      assetRecordHash: hash("fake asset"), audioHash: fresh.audioHash, providerTimingHash: fresh.timingHash,
      reviewArtifactHash: fresh.verification.reviewArtifactHash, boundaryEvidence: fresh };
    expect(() => createInferredRevisionV2(input.document, input.dependencies, cases, fakeAuthentication,
      { preparedMedia, handoff }, decisionHash)).toThrow(/blocked/);
  });
});
