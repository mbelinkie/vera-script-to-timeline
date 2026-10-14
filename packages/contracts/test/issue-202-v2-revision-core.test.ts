import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { canonicalJson, sha256CanonicalJson } from "../src/compiler-core.js";
import { compileTimelineV2 } from "../src/compiler-core-v2.js";
import type { CompilerDependenciesV2, NarrationBlockV2, NarrationBoundaryEvidenceV1, ScriptDocumentV2 } from "../src/generated/contracts-v2.js";
import type { RowHandoffV2 } from "../src/issue-189-v2-replacement.js";
import { createRevisionProposalV2, decideRevisionV2, prepareRevisionInputsV2, type RevisionCommandsV2 } from "../src/issue-192-v2-revision-core.js";

const id = (n: number) => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
const hash = (s: string) => `sha256:${createHash("sha256").update(s).digest("hex")}`;
const rate = { numerator: 24000, denominator: 1001 };
function rational(numerator: number, denominator: number) {
  let a = numerator; let b = denominator;
  while (b) [a, b] = [b, a % b];
  return { numerator: numerator / a, denominator: denominator / a };
}
function row(n: number, count: number): NarrationBlockV2 {
  let text = "";
  const tokens = Array.from({ length: count }, (_, i) => {
    if (i) text += " ";
    const startOffset = text.length; const value = `Word${i}`; text += value;
    return { id: id(n * 100 + i), value, startOffset, endOffset: text.length };
  });
  return { type: "narration", id: id(n), orderKey: `${n}`, text, tokens: [tokens[0]!, ...tokens.slice(1)],
    primaryVisualSequence: { id: id(n + 1), version: 1, slots: [{ id: id(n + 2), kind: "content", relation: { kind: "base" },
      boundaryBefore: { kind: "row_start" }, payload: { kind: "on_camera", presenterChoiceId: null }, playoutPolicy: "match_structural_interval", version: 1 }] },
    overlayEvents: [], timingPolicy: "narration_spine", state: "active", notes: [], version: 1 };
}
function boundary(row: NarrationBlockV2, frames: number, fresh = false): NarrationBoundaryEvidenceV1 {
  const suffix = fresh ? "fresh" : "old";
  const audioHash = hash(`${row.id}:${suffix}:audio`); const timingHash = hash(`${row.id}:${suffix}:timing`);
  return { schemaVersion: "narration-boundary-evidence/v1", blockId: row.id, blockRevision: row.version,
    textHash: hash(row.text), tokenizationVersion: "script-document/v2-frozen-tokens", narrationAssetId: id(parseInt(row.id.slice(-2), 16) + (fresh ? 900 : 800)),
    audioHash, timingHash, alignmentVersion: "synthetic/v1",
    audio: { narrationAssetId: id(parseInt(row.id.slice(-2), 16) + (fresh ? 900 : 800)), audioHash, timingHash,
      cacheAssetId: (fresh ? "b" : "a").repeat(64), locator: `Builds/${row.id}-${suffix}.wav`, durationSamples: frames * 2002, sampleRate: 48000, channels: 1 },
    tokens: [{ tokenId: row.tokens[0].id, quotedText: row.tokens[0].value, startOffset: 0, endOffset: row.tokens[0].endOffset, onset: { numerator: 0, denominator: 1 } }],
    verification: { method: "reviewed_audio_boundaries/v1", reviewId: id(fresh ? 999 : 998), reviewRevision: 1,
      reviewerReference: "synthetic-only", reviewArtifactLocator: `Reviews/${suffix}.json`, reviewArtifactHash: hash(`${suffix}:review`) } };
}
function specimen() {
  const dependencies = JSON.parse(readFileSync(new URL("../../../tests/data/authoring_v2/compiler-dependencies-v2.json", import.meta.url), "utf8")) as CompilerDependenciesV2;
  const r1 = row(10, 21); const r2 = row(20, 81);
  const document: ScriptDocumentV2 = { schemaVersion: "script-document/v2", id: id(1), projectId: id(2), title: "#202 synthetic only",
    activeDraft: { blocks: [r1], supportingItems: [] }, ideaOutline: [], extras: [], liveHeadSequence: 0, liveStateVector: "", liveContentHash: hash("baseline") };
  dependencies.timeline.frameRate = rate;
  dependencies.narrationTimingMaps = [];
  dependencies.narrationBoundaryEvidence = [boundary(r1, 200), boundary(r2, 641)];
  dependencies.document.contentHash = document.liveContentHash;
  dependencies.document.textHash = hash(`${r1.text}\n${r2.text}`);
  dependencies.tracks.push({ id: "presenter", kind: "video", index: 2, name: "Presenter" }, { id: "placeholder", kind: "video", index: 3, name: "Placeholder" },
    { id: "markers", kind: "video", index: 4, name: "Markers" }, { id: "source", kind: "audio", index: 2, name: "Source" });
  dependencies.roles.sourceAudioTrackIds = ["source"];
  const descriptorTemplate = structuredClone(dependencies.occurrenceResolutions[0]!);
  const bindingTemplate = structuredClone(dependencies.preparedMedia[0]!);
  dependencies.occurrenceResolutions = []; dependencies.preparedMedia = [];
  function media(payloadId: number, owner: typeof descriptorTemplate.owner, start: number, frames: number, image = false) {
    const descriptor = structuredClone(descriptorTemplate); const binding = structuredClone(bindingTemplate);
    descriptor.payloadId = id(payloadId); descriptor.owner = owner; descriptor.mediaReferenceId = id(payloadId + 500);
    descriptor.sourceSnapshot.contentHash = hash(`media:${payloadId}`); descriptor.sourceSnapshot.probeHash = hash(`probe:${payloadId}`);
    descriptor.occurrenceSourceInFrame = start;
    descriptor.selectedSourceRange = owner.kind === "visual_only_block" ? { startFrame: start, endFrame: start + frames } : null;
    descriptor.logicalSourceBounds = { startFrame: 0, endFrame: image ? 1 : 5000, frameRate: rate };
    descriptor.sourceFrameMap = { ...descriptor.sourceFrameMap, decodedPackageFrameRate: rate, decodedPackageFrameCount: image ? 1 : 5000,
      packageVideoTimeBase: { numerator: 1001, denominator: 24000 }, probeHash: descriptor.sourceSnapshot.probeHash,
      sourceAudioStreamMappings: image ? [] : [{ streamIndex: 0, sampleRate: 48000, packagePtsOrigin: { numerator: 0, denominator: 1 },
        loggedTimeAtPackageOrigin: { numerator: 0, denominator: 1 }, audioHash: hash(`pcm:${payloadId}`), probeHash: descriptor.sourceSnapshot.probeHash }] };
    descriptor.preparedMediaRequirementKey = `prep:${payloadId}`;
    binding.requirementKey = descriptor.preparedMediaRequirementKey;
    binding.originalSource = { mediaReferenceId: descriptor.mediaReferenceId, contentHash: descriptor.sourceSnapshot.contentHash, probeHash: descriptor.sourceSnapshot.probeHash };
    binding.targetRate = rate;
    binding.requestedRange = { sourceInFrame: start, duration: rational(frames * 1001, 24000), preHandle: { numerator: 0, denominator: 1 }, postHandle: { numerator: 0, denominator: 1 } };
    binding.timeMapping = { ...binding.timeMapping, sourceOrigin: { numerator: 0, denominator: 1 }, sourceRate: rate, deliveredRate: rate, sourceFrameMap: structuredClone(descriptor.sourceFrameMap) };
    binding.verification = { ...binding.verification, deliveredHash: descriptor.sourceSnapshot.contentHash, probeHash: descriptor.sourceSnapshot.probeHash,
      decodedFrameCount: image ? 1 : 5000, decodedFrameRate: rate, videoTimeBase: { numerator: 1001, denominator: 24000 },
      sourceAudio: image ? binding.verification.sourceAudio : { status: "aligned", offset: { numerator: 0, denominator: 1 }, maxDrift: { numerator: 0, denominator: 1 }, sampleRate: 48000 } };
    binding.artifactLocator = `prepared/${payloadId}.mov`;
    dependencies.occurrenceResolutions.push(descriptor); dependencies.preparedMedia.push(binding);
    return { kind: "visual" as const, payloadId: descriptor.payloadId, pictureKind: image ? "image" as const : "clip" as const,
      source: { kind: "media_reference" as const, mediaReferenceId: descriptor.mediaReferenceId },
      audioPolicy: image ? "mute" as const : "full" as const, framingPolicy: "contain" as const };
  }
  const base = r1.primaryVisualSequence!.slots[0]!;
  if (base.kind !== "content") throw new Error("base");
  base.payload = { ...media(30, { kind: "primary_slot", sequenceId: r1.primaryVisualSequence!.id, slotId: base.id }, 0, 200), sourceUsage: { sourceInFrame: 0 }, audioPolicy: "quiet" };
  const anchor = (i: number, affinity: "before" | "after") => ({ blockId: r2.id, tokenId: r2.tokens[i]!.id, quotedWord: r2.tokens[i]!.value, anchorVersion: 1, affinity });
  r2.primaryVisualSequence!.slots.push({ id: id(23), kind: "content", relation: { kind: "sequential" }, boundaryBefore: { kind: "spoken_word", anchor: { ...anchor(20, "before"), affinity: "before" } },
    payload: { ...media(31, { kind: "primary_slot", sequenceId: r2.primaryVisualSequence!.id, slotId: id(23) }, 0, 1, true), sourceUsage: null, audioPolicy: "mute" }, playoutPolicy: "match_structural_interval", version: 1 },
    { id: id(24), kind: "content", relation: { kind: "sequential" }, boundaryBefore: { kind: "audible_word_end", anchor: { ...anchor(34, "after"), affinity: "after" } },
      payload: { kind: "on_camera", presenterChoiceId: null }, playoutPolicy: "match_structural_interval", version: 1 });
  const r2e = dependencies.narrationBoundaryEvidence[1]!;
  for (const [i, start, end] of [[20, 145, undefined], [34, 258, 281]] as const) r2e.tokens.push({ tokenId: r2.tokens[i]!.id, quotedText: r2.tokens[i]!.value,
    startOffset: r2.tokens[i]!.startOffset, endOffset: r2.tokens[i]!.endOffset, onset: rational(start * 1001, 24000), ...(end ? { audibleEnd: rational(end * 1001, 24000) } : {}) });
  for (const [n, start, frames] of [[40, 0, 111], [50, 2664, 92], [60, 396, 63]]) {
    const block = { type: "visual_only" as const, id: id(n!), orderKey: `${n}`, version: 1,
      payload: media(n! + 1, { kind: "visual_only_block", blockId: id(n!) }, start!, frames!),
      visualOnlyTiming: { kind: "visual_only" as const, selectedSourceRange: { startFrame: start!, durationFrames: frames! } } };
    document.activeDraft.blocks.push(block);
    if (n === 40) document.activeDraft.blocks.push(r2);
  }
  document.activeDraft.blocks.push({ type: "note_draft", id: id(70), orderKey: "last", text: "Parked and unchanged", state: "excluded", version: 1 });
  return { document, dependencies };
}
function commands(): RevisionCommandsV2 {
  return { boundary: { kind: "move_word_boundary", blockId: id(20), boundaryOwnerId: id(23), tokenId: id(2034), affinity: "before", expectedSequenceVersion: 1 },
    trim: { blockId: id(50), expectedBlockVersion: 1, expectedSelectedRange: { startFrame: 2664, durationFrames: 92 }, durationFrames: 67 }, omission: null };
}
function patches(input: ReturnType<typeof specimen>, d1 = 200) {
  return [30, 51].map((n) => {
    const binding = structuredClone(input.dependencies.preparedMedia.find((b) => b.requirementKey === `prep:${n}`)!);
    binding.requestedRange.duration = rational((n === 30 ? d1 : 67) * 1001, 24000); return binding;
  });
}
function decision(proposal: ReturnType<typeof createRevisionProposalV2>, history: string[] = [], outcome: "accept" | "reject" = "accept") {
  return { schemaVersion: "issue-202-v2-decision/v1" as const, proposalHash: proposal.proposalHash, historyHash: sha256CanonicalJson(history), outcome };
}
function cCase(d1: number) {
  const input = specimen(); const command = commands();
  const ab = prepareRevisionInputsV2(input.document, input.dependencies, command, patches(input, d1).slice(1));
  command.omission = { schemaVersion: "issue-189-v2-accepted-omission/v1", expectedDocumentHash: sha256CanonicalJson(ab.document), blockId: id(10), blockRevision: 1,
    tokenIds: [id(1011)], evidenceHash: hash("synthetic omission"), decisionHash: hash("synthetic upstream decision") };
  const stage = prepareRevisionInputsV2(input.document, input.dependencies, command, patches(input, d1));
  const revisedRow = stage.document.activeDraft.blocks[0] as NarrationBlockV2;
  const evidence = boundary(revisedRow, d1, true);
  const handoff: RowHandoffV2 = { schemaVersion: "issue-189-v2-row-handoff/v1", request: stage.regeneration!, priorDependenciesHash: sha256CanonicalJson(stage.dependencies),
    serviceRequestHash: hash("fake service request"), generationReceiptHash: hash("fake receipt"), assetRecordHash: hash("fake asset"), audioHash: evidence.audioHash,
    providerTimingHash: evidence.timingHash, reviewArtifactHash: evidence.verification.reviewArtifactHash, boundaryEvidence: evidence };
  return { input, command, handoff, preparedMedia: patches(input, d1) };
}
describe("#202 pure explicit commands (synthetic, no native/provider authentication)", () => {
  it("isolates A and B and preserves unrelated compiled events", () => {
    const input = specimen(); const baseline = compileTimelineV2(input.document, input.dependencies);
    if (!baseline.ok) throw new Error(canonicalJson(baseline));
    const a = commands(); a.trim = null;
    const pa = createRevisionProposalV2(input.document, input.dependencies, { commands: a, preparedMedia: [], handoff: null });
    expect(pa.manifest.timeline.durationFrames).toBe(1107);
    expect(pa.manifest.events.find((e) => e.provenance.slotId === id(22))!.recordRange).toEqual({ startFrame: 311, endFrame: 569 });
    expect(pa.manifest.events.filter((e) => e.provenance.blockId !== id(20))).toEqual(baseline.manifest.events.filter((e) => e.provenance.blockId !== id(20)));
    const b = commands(); b.boundary = null;
    const pb = createRevisionProposalV2(input.document, input.dependencies, { commands: b, preparedMedia: patches(input).slice(1), handoff: null });
    expect(pb.manifest.events.filter((e) => e.recordRange.startFrame < 952)).toEqual(baseline.manifest.events.filter((e) => e.recordRange.startFrame < 952));
    expect(pb.manifest.events.find((e) => e.kind === "primary_visual" && e.provenance.blockId === id(60))!.sourceRange).toEqual({ startFrame: 396, endFrame: 459 });
  });
  it("compiles baseline and A/B with exact source, linked audio and downstream ranges", () => {
    const input = specimen(); const bytes = canonicalJson(input);
    const baseline = compileTimelineV2(input.document, input.dependencies);
    expect(baseline.ok && baseline.report.status).toBe("ready");
    const proposal = createRevisionProposalV2(input.document, input.dependencies, { commands: commands(), preparedMedia: patches(input).slice(1), handoff: null });
    expect(proposal.manifest.timeline.durationFrames).toBe(1082);
    expect(proposal.dependencies.timeline).toEqual(proposal.manifest.timeline);
    expect(proposal.report.timeline).toEqual(proposal.dependencies.timeline);
    const events = proposal.manifest.events;
    expect(events.find((e) => e.provenance.slotId === id(23))!.recordRange).toEqual({ startFrame: 569, endFrame: 592 });
    for (const kind of ["primary_visual", "source_audio"]) {
      expect(events.find((e) => e.provenance.blockId === id(50) && e.kind === kind)!.recordRange).toEqual({ startFrame: 952, endFrame: 1019 });
      expect(events.find((e) => e.provenance.blockId === id(60) && e.kind === kind)!.recordRange).toEqual({ startFrame: 1019, endFrame: 1082 });
    }
    expect(events.find((e) => e.provenance.blockId === id(50) && e.kind === "primary_visual")!.sourceRange).toEqual({ startFrame: 2664, endFrame: 2731 });
    const audio = events.find((e) => e.provenance.blockId === id(50) && e.kind === "source_audio")!.audio!;
    expect(audio.sampleRange).toEqual({ startFrame: 2664 * 2002, endFrame: 2731 * 2002 });
    expect(proposal.comparisonText).toContain("Before | After");
    expect(proposal.comparisonText).toContain("Block 3 (narration), slot 2");
    expect(proposal.comparisonText).toContain("track ");
    expect(proposal.comparisonText).toContain("picture ");
    expect(proposal.comparisonText).toContain("mapping ");
    expect(proposal.comparisonText).not.toContain("decodedPackageFrameCount");
    expect(canonicalJson(input)).toBe(bytes);
  });
  for (const d1 of [187, 200, 213]) it(`composes actual fresh compiled D1=${d1}, preserves neighbors and parked state`, () => {
    const { input, command, handoff, preparedMedia } = cCase(d1); const bytes = canonicalJson(input);
    const proposal = createRevisionProposalV2(input.document, input.dependencies, { commands: command, preparedMedia, handoff });
    const delta = d1 - 200;
    expect(proposal.manifest.timeline.durationFrames).toBe(1082 + delta);
    expect(proposal.dependencies.timeline).toEqual(proposal.manifest.timeline);
    expect(proposal.report.timeline).toEqual(proposal.dependencies.timeline);
    expect(proposal.report.dependenciesHash).toBe(sha256CanonicalJson(proposal.dependencies));
    expect(proposal.manifest.events.find((e) => e.kind === "narration" && e.provenance.blockId === id(20))!.recordRange.startFrame).toBe(311 + delta);
    expect(proposal.manifest.events.find((e) => e.provenance.slotId === id(23))!.recordRange).toEqual({ startFrame: 569 + delta, endFrame: 592 + delta });
    expect(proposal.manifest.events.find((e) => e.kind === "primary_visual" && e.provenance.blockId === id(50))!.recordRange).toEqual({ startFrame: 952 + delta, endFrame: 1019 + delta });
    expect(proposal.manifest.events.find((e) => e.kind === "primary_visual" && e.provenance.blockId === id(60))!.recordRange).toEqual({ startFrame: 1019 + delta, endFrame: 1082 + delta });
    const row1 = proposal.document.activeDraft.blocks[0] as NarrationBlockV2;
    expect(row1.tokens.map((t) => t.id)).not.toContain(id(1011));
    expect(row1.tokens.map((t) => t.id)).toEqual(expect.arrayContaining([id(1010), id(1012)]));
    expect(proposal.document.activeDraft.blocks.at(-1)).toEqual(input.document.activeDraft.blocks.at(-1));
    expect(proposal.dependencies.narrationBoundaryEvidence![1]).toEqual(input.dependencies.narrationBoundaryEvidence![1]);
    expect(canonicalJson(input)).toBe(bytes);
  });
  it("rejects explicitly without mutation and prevents duplicate accept/reject", () => {
    const input = specimen(); const proposal = createRevisionProposalV2(input.document, input.dependencies, { commands: commands(), preparedMedia: patches(input).slice(1), handoff: null });
    const rejected = decideRevisionV2(input.document, input.dependencies, proposal, decision(proposal, [], "reject"), []);
    expect(rejected.document).toBe(input.document); expect(rejected.dependencies).toBe(input.dependencies);
    expect(() => decideRevisionV2(input.document, input.dependencies, proposal, decision(proposal, rejected.history), rejected.history)).toThrow(/already decided/);
    const accepted = decideRevisionV2(input.document, input.dependencies, proposal, decision(proposal), []);
    expect(accepted.document).toEqual(proposal.document);
    expect(() => decideRevisionV2(accepted.document, accepted.dependencies, proposal, decision(proposal, accepted.history), accepted.history)).toThrow();
  });
  it("refuses stale/malformed/ambiguous commands and changed decision inputs", () => {
    const input = specimen(); const bytes = canonicalJson(input);
    const request = { commands: commands(), preparedMedia: patches(input).slice(1), handoff: null };
    const proposal = createRevisionProposalV2(input.document, input.dependencies, request);
    for (const mutate of [
      (r: typeof request) => { r.commands.boundary!.expectedSequenceVersion = 2; },
      (r: typeof request) => { r.commands.boundary!.tokenId = id(99999); },
      (r: typeof request) => { r.commands.trim!.expectedBlockVersion = 2; },
      (r: typeof request) => { r.commands.trim!.durationFrames = 93; },
      (r: typeof request) => { Object.assign(r.commands.trim!, { pictureOnly: true }); },
      (r: typeof request) => { r.preparedMedia.push(structuredClone(r.preparedMedia[0]!)); },
    ]) { const bad = structuredClone(request); mutate(bad); expect(() => createRevisionProposalV2(input.document, input.dependencies, bad)).toThrow(); }
    const changedDoc = structuredClone(input.document); changedDoc.title += " changed";
    expect(() => decideRevisionV2(changedDoc, input.dependencies, proposal, decision(proposal), [])).toThrow();
    const changedDeps = structuredClone(input.dependencies); changedDeps.compiler.profileHash = hash("changed");
    expect(() => decideRevisionV2(input.document, changedDeps, proposal, decision(proposal), [])).toThrow();
    const tampered = structuredClone(proposal); tampered.comparisonText += " wrong";
    expect(() => decideRevisionV2(input.document, input.dependencies, tampered, decision(tampered), [])).toThrow();
    expect(() => decideRevisionV2(input.document, input.dependencies, proposal, { ...decision(proposal), historyHash: hash("wrong") }, [])).toThrow();
    expect(canonicalJson(input)).toBe(bytes);
  });
  it("refuses source shortage and invalid or missing whole-row handoff", () => {
    const c = cCase(213); const bytes = canonicalJson(c.input);
    const bad = structuredClone(c.handoff); bad.audioHash = hash("wrong audio");
    expect(() => createRevisionProposalV2(c.input.document, c.input.dependencies, { commands: c.command, preparedMedia: c.preparedMedia, handoff: bad })).toThrow();
    expect(() => createRevisionProposalV2(c.input.document, c.input.dependencies, { commands: c.command, preparedMedia: c.preparedMedia, handoff: null })).toThrow();
    const short = structuredClone(c.input); short.dependencies.occurrenceResolutions.find((d) => d.payloadId === id(30))!.logicalSourceBounds.endFrame = 205;
    const shortStage = prepareRevisionInputsV2(short.document, short.dependencies, c.command, c.preparedMedia);
    const shortHandoff = { ...c.handoff, priorDependenciesHash: sha256CanonicalJson(shortStage.dependencies) };
    const shortDeps = structuredClone(shortStage.dependencies);
    shortDeps.document.contentHash = shortStage.document.liveContentHash;
    shortDeps.document.liveHeadSequence = shortStage.document.liveHeadSequence;
    shortDeps.document.textHash = hash(shortStage.document.activeDraft.blocks.filter((b) => b.type === "narration").map((b) => b.text).join("\n"));
    shortDeps.narrationBoundaryEvidence![0] = shortHandoff.boundaryEvidence;
    const blocked = compileTimelineV2(shortStage.document, shortDeps);
    expect(blocked.ok && blocked.report.status).toBe("blocked");
    expect(blocked.ok && blocked.report.diagnostics.map((d) => d.code)).toContain("SOURCE_INSUFFICIENT");
    expect(() => createRevisionProposalV2(short.document, short.dependencies, { commands: c.command, preparedMedia: c.preparedMedia, handoff: shortHandoff })).toThrow("blocked/nondeterministic/mutated replacement preview");
    expect(canonicalJson(c.input)).toBe(bytes);
  });
  it("refuses unrelated media, changed profile/authorization, real picture-only input and unexpected handoff", () => {
    const input = specimen(); const bytes = canonicalJson(input);
    const request = { commands: commands(), preparedMedia: patches(input).slice(1), handoff: null };
    const unrelated = structuredClone(request);
    unrelated.preparedMedia.push(structuredClone(input.dependencies.preparedMedia.find((b) => b.requirementKey === "prep:41")!));
    expect(() => createRevisionProposalV2(input.document, input.dependencies, unrelated)).toThrow(/unrelated\/duplicate/);
    for (const key of ["profile", "authorization"] as const) {
      const changed = structuredClone(request);
      if (key === "profile") changed.preparedMedia[0]!.profile.profileHash = hash("different profile");
      else changed.preparedMedia[0]!.authorizationReference = "different authority";
      expect(() => createRevisionProposalV2(input.document, input.dependencies, changed)).toThrow(/source\/profile\/authorization changed/);
    }
    const pictureOnly = structuredClone(input);
    const block = pictureOnly.document.activeDraft.blocks.find((b) => b.id === id(50));
    if (block?.type !== "visual_only") throw new Error("standalone missing");
    block.payload.audioPolicy = "mute";
    const baseline = compileTimelineV2(pictureOnly.document, pictureOnly.dependencies);
    expect(baseline.ok && baseline.report.status).toBe("ready");
    expect(() => createRevisionProposalV2(pictureOnly.document, pictureOnly.dependencies, request)).toThrow(/linked standalone AV clip required/);
    expect(() => createRevisionProposalV2(input.document, input.dependencies, { ...request, handoff: cCase(200).handoff })).toThrow(/unexpected whole-row handoff/);
    expect(canonicalJson(input)).toBe(bytes);
  });
  it("refuses malformed decisions and duplicate/invalid histories without mutation", () => {
    const input = specimen(); const bytes = canonicalJson(input);
    const proposal = createRevisionProposalV2(input.document, input.dependencies, { commands: commands(), preparedMedia: patches(input).slice(1), handoff: null });
    expect(() => decideRevisionV2(input.document, input.dependencies, proposal, Object.assign(decision(proposal), { unknown: true }), [])).toThrow(/unsupported pure input fields/);
    expect(() => decideRevisionV2(input.document, input.dependencies, proposal, Object.assign(decision(proposal), { outcome: "maybe" }), [])).toThrow(/unsupported decision/);
    for (const history of [["not a hash"], [hash("old"), hash("old")]]) {
      expect(() => decideRevisionV2(input.document, input.dependencies, proposal, decision(proposal, history), history)).toThrow(/stale\/malformed decision history/);
    }
    expect(() => decideRevisionV2(input.document, input.dependencies, proposal, { ...decision(proposal), proposalHash: hash("different proposal") }, [])).toThrow(/identity changed/);
    expect(canonicalJson(input)).toBe(bytes);
  });
});
