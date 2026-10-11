import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";
import { compileTimelineV2, resolveMediaRequirementsV2 } from "../src/compiler-core-v2.js";
import { canonicalJson, sha256CanonicalJson } from "../src/compiler-core.js";
import { applyVisualSequenceEditV2, projectPrimarySequenceV2, validateScriptDocumentV2 } from "../src/authoring-v2.js";
import type { WordBoundaryAnchorV2, VisualSequenceEditCommandV2 } from "../src/authoring-v2.js";
import type { CompilerDependenciesV2, NarrationBlockV2, NarrationBoundaryEvidenceV1, ContentSlot, ReturnSlot, ScriptDocumentV2, PointPlacement } from "../src/generated/contracts-v2.js";

type Input = { document: ScriptDocumentV2; dependencies: CompilerDependenciesV2 };
const root = fileURLToPath(new URL("../../../", import.meta.url));
const golden = `${root}tests/data/authoring_v2/issue_180/`;
const id = (n: number) => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;
const hash = (bytes: string) => `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
const time = (numerator: number, denominator = 1) => ({ numerator, denominator });
function specimen(): Input {
  const input = JSON.parse(readFileSync(`${root}docs/verification/issue-179/complete.input.json`, "utf8")) as Input;
  input.document.title = "Issue 180 synthetic boundary evidence";
  const map = input.dependencies.narrationTimingMaps[0]!;
  const evidence: NarrationBoundaryEvidenceV1 = {
    schemaVersion: "narration-boundary-evidence/v1", blockId: map.blockId, blockRevision: map.blockRevision, textHash: map.textHash,
    tokenizationVersion: "script-document/v2-frozen-tokens", narrationAssetId: map.narrationAssetId, audioHash: map.audioHash, timingHash: map.timingHash,
    alignmentVersion: map.alignmentVersion, audio: structuredClone(map.audio!),
    tokens: map.tokens.slice(1).map((mark) => ({ tokenId: mark.tokenId, startOffset: mark.startOffset, endOffset: mark.endOffset,
      quotedText: mark.quotedText, onset: mark.startTime, ...(mark.audibleEnd ? { audibleEnd: mark.audibleEnd } : {}) })),
    verification: { method: "reviewed_audio_boundaries/v1", reviewId: id(180), reviewRevision: 1,
      reviewerReference: "synthetic-test-reviewer", reviewArtifactLocator: "Reviews/synthetic-180.json", reviewArtifactHash: hash("synthetic receipt") },
  };
  input.dependencies.narrationTimingMaps = [];
  input.dependencies.narrationBoundaryEvidence = [evidence];
  return input;
}
function row(input: Input): NarrationBlockV2 {
  const value = input.document.activeDraft.blocks[0]!;
  if (value.type !== "narration") throw new Error("synthetic row missing");
  return value;
}
const evidence = (input: Input) => input.dependencies.narrationBoundaryEvidence![0]!;
function child(input: Input): ContentSlot {
  const slot = row(input).primaryVisualSequence!.slots[1]!;
  if (slot.kind !== "content") throw new Error("child missing");
  return slot;
}
function returned(input: Input): ReturnSlot {
  const slot = row(input).primaryVisualSequence!.slots[2]!;
  if (slot.kind !== "return") throw new Error("return missing");
  return slot;
}
function anchor(input: Input, index: number, affinity: "before" | "after" = "before"): WordBoundaryAnchorV2 {
  const block = row(input); const token = block.tokens[index]!;
  return { blockId: block.id, tokenId: token.id, affinity, quotedWord: token.value, anchorVersion: 1 };
}
function needs(input: Input) {
  return resolveMediaRequirementsV2(input.document, { timing: input.dependencies.narrationTimingMaps,
    boundaryEvidence: input.dependencies.narrationBoundaryEvidence ?? [], defaults: input.dependencies.authoringDefaults,
    sourceDescriptors: input.dependencies.occurrenceResolutions, frameRate: input.dependencies.timeline.frameRate });
}
function compiled(input: Input) {
  const result = compileTimelineV2(input.document, input.dependencies);
  if (!result.ok) throw new Error(JSON.stringify(result));
  return result;
}
function refused(input: Input, code?: string) {
  const result = compileTimelineV2(input.document, input.dependencies);
  const codes = result.ok ? result.report.diagnostics.map((item) => item.code) : result.diagnostics.map((item) => item.code);
  expect(result.ok ? result.report.status : "blocked").toBe("blocked");
  if (code) expect(codes).toContain(code);
  expect(needs(input).ok).toBe(false);
  return result;
}
function endpointsOnly(input: Input) {
  row(input).primaryVisualSequence!.slots.splice(1);
  evidence(input).tokens = [];
}

for (const [rate, expected] of [
  [time(24), [24, 36, 48, 66, 96]], [time(25), [25, 38, 50, 69, 100]], [time(24000, 1001), [24, 36, 48, 66, 96]],
] as const) {
  for (const mode of ["before-gamma", "after-beta", "final-tail"] as const) test(`${mode} at ${rate.numerator}/${rate.denominator} preserves audio and exact deltas`, () => {
    const input = specimen(); input.dependencies.timeline.frameRate = rate;
    // These scenarios exercise speech cuts independently of media preparation rate.
    const base = row(input).primaryVisualSequence!.slots[0]!;
    if (base.kind !== "content") throw new Error("root missing");
    base.payload = { kind: "on_camera", presenterChoiceId: null };
    input.dependencies.occurrenceResolutions = []; input.dependencies.preparedMedia = [];
    if (mode === "after-beta") { returned(input).inpoint = anchor(input, 1, "after"); evidence(input).tokens.splice(1); }
    if (mode === "final-tail") {
      const before = anchor(input, 2); if (before.affinity !== "before") throw new Error("wrong affinity");
      child(input).boundaryBefore = { kind: "spoken_word", anchor: before };
      returned(input).inpoint = anchor(input, 2, "after"); evidence(input).tokens.splice(0, 1);
    }
    const result = compiled(input);
    expect(result.report.status).toBe("ready");
    expect(result.manifest.events.find((event) => event.trackRole === "child")?.recordRange).toEqual({
      startFrame: mode === "final-tail" ? expected[2] : expected[0], endFrame: mode === "before-gamma" ? expected[2] : mode === "after-beta" ? expected[1] : expected[3],
    });
    expect(result.manifest.events.find((event) => event.trackRole === "primary_root")?.recordRange).toEqual({ startFrame: 0, endFrame: expected[4] });
    expect(result.manifest.events.find((event) => event.kind === "narration")?.recordRange).toEqual({ startFrame: 0, endFrame: expected[4] });
    expect(result.manifest.sources.find((source) => source.id === evidence(input).narrationAssetId)).toEqual({ id: evidence(input).narrationAssetId, narrationAudio: evidence(input).audio });
    const boundaryHash = sha256CanonicalJson(evidence(input));
    expect(result.manifest.events.every((event) => event.provenance.boundaryEvidenceHash === boundaryHash)).toBe(true);
    expect(result.manifest.visualSequenceResolutions.every((item) => item.boundaryEvidenceHash === boundaryHash)).toBe(true);
    const ret = result.manifest.boundaryEvidence.find((item) => item.entityId === returned(input).id)!;
    const exact = mode === "after-beta" ? time(3, 2) : mode === "final-tail" ? time(11, 4) : time(2);
    expect(ret.inputTime).toEqual(exact);
    expect(ret.kind).toBe(mode === "before-gamma" ? "word_start" : "word_end");
    expect(ret.precision).toBe(mode === "before-gamma" ? "verified_onset" : "audible_word");
    expect(ret.delta.numerator * exact.denominator * rate.numerator).toBe(
      (ret.resolvedRecordFrame * rate.denominator * exact.denominator - exact.numerator * rate.numerator) * ret.delta.denominator,
    );
    expect(needs(input)).toEqual({ ok: true, requirements: [], durationFrames: expected[4] });
    expect(compileTimelineV2(input.document, input.dependencies)).toEqual(result);
    if (rate.numerator !== 24) {
      const name = `${mode}-${rate.numerator}-${rate.denominator}`;
      const outputs = { input: canonicalJson(input), manifest: result.manifestJson, report: result.reportJson };
      if (process.env.WRITE_ISSUE_180_GOLDENS === "1") {
        mkdirSync(golden, { recursive: true });
        for (const [kind, bytes] of Object.entries(outputs)) writeFileSync(`${golden}${name}.${kind}.golden.json`, bytes);
      }
      for (const [kind, bytes] of Object.entries(outputs)) expect(bytes).toBe(readFileSync(`${golden}${name}.${kind}.golden.json`, "utf8"));
    }
  });
}

test("missing unrelated edges do not alter picture needs; subset identity changes build identity", () => {
  const input = specimen();
  const initial = compiled(input);
  expect(initial.report.status).toBe("ready");
  const req = needs(input); expect(req.ok).toBe(true);
  if (!req.ok) throw new Error("needs refused");
  expect(req.requirements[0]?.recordRange).toEqual(initial.manifest.events.find((event) => event.kind === "primary_visual")?.recordRange);
  for (const mark of evidence(input).tokens) delete mark.audibleEnd;
  const subset = compiled(input);
  expect(subset.report.status).toBe("ready"); expect(needs(input)).toEqual(req);
  expect(subset.report.dependenciesHash).not.toBe(initial.report.dependenciesHash);
  expect(subset.manifest.events[0]?.provenance.timingMapHash).toBe(initial.manifest.events[0]?.provenance.timingMapHash);
  expect(subset.manifest.events[0]?.provenance.boundaryEvidenceHash).not.toBe(initial.manifest.events[0]?.provenance.boundaryEvidenceHash);
});

for (const missing of ["beta-onset", "gamma-onset", "beta-end", "gamma-end"] as const) test(`required ${missing} blocks without substitute`, () => {
  const input = specimen();
  if (missing === "beta-end") { returned(input).inpoint = anchor(input, 1, "after"); delete evidence(input).tokens[0]!.audibleEnd; }
  else if (missing === "gamma-end") { const before = anchor(input, 2); if (before.affinity !== "before") throw new Error("edge"); child(input).boundaryBefore = { kind: "spoken_word", anchor: before }; returned(input).inpoint = anchor(input, 2, "after"); delete evidence(input).tokens[1]!.audibleEnd; }
  else delete evidence(input).tokens[missing === "beta-onset" ? 0 : 1]!.onset;
  const result = refused(input, "BOUNDARY_EVIDENCE_REQUIRED");
  expect(result.ok).toBe(true);
  if (!result.ok) throw new Error("expected diagnostic manifest");
  expect(result.manifest.events.every((item) => item.kind === "narration")).toBe(true);
  expect(result.manifest.timeline.durationFrames).toBe(96);
  expect(result.report.diagnostics.find((item) => item.code === "BOUNDARY_EVIDENCE_REQUIRED")?.message).toContain(missing.endsWith("end") ? "after" : "before");
});

test("empty tokens support only fixed row endpoints; an end-only mark resolves after without onset", () => {
  const input = specimen(); endpointsOnly(input);
  expect(compiled(input).report.status).toBe("ready"); expect(needs(input).ok).toBe(true);
  const after = anchor(input, 1, "after"); if (after.affinity !== "after") throw new Error("edge");
  const rootSlot = row(input).primaryVisualSequence!.slots[0]!;
  if (rootSlot.kind !== "content") throw new Error("root");
  rootSlot.payload = { kind: "on_camera", presenterChoiceId: null };
  input.dependencies.occurrenceResolutions = []; input.dependencies.preparedMedia = [];
  row(input).primaryVisualSequence!.slots.push({ ...structuredClone(rootSlot), id: id(181), relation: { kind: "sequential" }, boundaryBefore: { kind: "audible_word_end", anchor: after } });
  const beta = row(input).tokens[1]!;
  evidence(input).tokens = [{ tokenId: beta.id, startOffset: beta.startOffset, endOffset: beta.endOffset, quotedText: beta.value, audibleEnd: time(3, 2) }];
  const result = compiled(input); expect(result.report.status).toBe("ready");
  expect(result.manifest.visualSequenceResolutions.find((item) => item.slotId === id(181))?.resolvedRecordFrame).toBe(36);
});

const mutations: Array<[string, (input: Input) => void, string?]> = [
  ["wrong version", (x) => { Object.assign(evidence(x), { schemaVersion: "candidate/v1" }); }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["missing receipt", (x) => { Reflect.deleteProperty(evidence(x), "verification"); }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["candidate receipt", (x) => { Object.assign(evidence(x).verification, { method: "candidate" }); }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["missing review id", (x) => { Reflect.deleteProperty(evidence(x).verification, "reviewId"); }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["zero review revision", (x) => { evidence(x).verification.reviewRevision = 0; }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["malformed review hash", (x) => { evidence(x).verification.reviewArtifactHash = "bad"; }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["unsafe review path", (x) => { evidence(x).verification.reviewArtifactLocator = "../receipt.json"; }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["double slash review path", (x) => { evidence(x).verification.reviewArtifactLocator = "Reviews//receipt.json"; }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["missing reviewer", (x) => { evidence(x).verification.reviewerReference = ""; }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["wrong row", (x) => { evidence(x).blockId = id(999); }],
  ["missing row", (x) => { x.dependencies.narrationBoundaryEvidence = []; }],
  ["stale row revision", (x) => { evidence(x).blockRevision++; }, "STALE_TIMING_MAP"],
  ["stale text", (x) => { evidence(x).textHash = hash("wrong"); }, "TEXT_HASH_MISMATCH"],
  ["wrong tokenization", (x) => { Object.assign(evidence(x), { tokenizationVersion: "new" }); }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["asset mismatch", (x) => { evidence(x).narrationAssetId = id(999); }],
  ["audio mismatch", (x) => { evidence(x).audioHash = hash("wrong"); }],
  ["timing mismatch", (x) => { evidence(x).timingHash = hash("wrong"); }, "TIMING_HASH_MISMATCH"],
  ["invalid cache", (x) => { evidence(x).audio.cacheAssetId = "bad"; }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["invalid audio locator", (x) => { evidence(x).audio.locator = "/tmp/audio.wav"; }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["zero samples", (x) => { evidence(x).audio.durationSamples = 0; }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["unsafe sample rate", (x) => { evidence(x).audio.sampleRate = Number.MAX_SAFE_INTEGER + 1; }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["invalid channels", (x) => { evidence(x).audio.channels = 0; }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["duplicate rows", (x) => { x.dependencies.narrationBoundaryEvidence!.push(structuredClone(evidence(x))); }, "STALE_TIMING_MAP"],
  ["dual capabilities", (x) => { const old = JSON.parse(readFileSync(`${root}docs/verification/issue-179/complete.input.json`, "utf8")) as Input; x.dependencies.narrationTimingMaps = old.dependencies.narrationTimingMaps; }, "STALE_TIMING_MAP"],
  ["inactive row", (x) => { row(x).state = "excluded"; }],
  ["unknown token", (x) => { evidence(x).tokens[0]!.tokenId = id(999); }, "STALE_TIMING_MAP"],
  ["duplicate token", (x) => { evidence(x).tokens.push(structuredClone(evidence(x).tokens[0]!)); }, "STALE_TIMING_MAP"],
  ["reordered token", (x) => { evidence(x).tokens.reverse(); }, "STALE_TIMING_MAP"],
  ["wrong UTF16", (x) => { evidence(x).tokens[0]!.startOffset++; }, "STALE_TIMING_MAP"],
  ["wrong quote", (x) => { evidence(x).tokens[0]!.quotedText = "Beta"; }, "STALE_TIMING_MAP"],
  ["negative onset", (x) => { evidence(x).tokens[0]!.onset = time(-1); }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["zero denominator", (x) => { evidence(x).tokens[0]!.onset = time(1, 0); }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["unsafe onset", (x) => { evidence(x).tokens[0]!.onset = time(Number.MAX_SAFE_INTEGER + 1); }, "DEPENDENCIES_SCHEMA_INVALID"],
  ["nonreduced onset", (x) => { evidence(x).tokens[0]!.onset = time(2, 2); }, "COLLAPSED_BOUNDARY"],
  ["onset at audio end", (x) => { evidence(x).tokens[1]!.onset = time(4); delete evidence(x).tokens[1]!.audibleEnd; }, "COLLAPSED_BOUNDARY"],
  ["end beyond audio", (x) => { evidence(x).tokens[1]!.audibleEnd = time(5); }, "COLLAPSED_BOUNDARY"],
  ["zero end", (x) => { evidence(x).tokens[0]!.audibleEnd = time(0); }, "COLLAPSED_BOUNDARY"],
  ["collapsed support", (x) => { evidence(x).tokens[0]!.audibleEnd = time(1); }, "COLLAPSED_BOUNDARY"],
  ["crossed supports", (x) => { evidence(x).tokens[0]!.audibleEnd = time(5, 2); }, "COLLAPSED_BOUNDARY"],
  ["decreasing ends", (x) => { delete evidence(x).tokens[1]!.onset; evidence(x).tokens[1]!.audibleEnd = time(5, 4); }, "COLLAPSED_BOUNDARY"],
  ["invalid unused mark", (x) => { endpointsOnly(x); evidence(x).tokens = [{ tokenId: id(999), startOffset: 0, endOffset: 5, quotedText: "alpha", onset: time(0) }]; }, "STALE_TIMING_MAP"],
  ["no observation", (x) => { delete evidence(x).tokens[0]!.onset; delete evidence(x).tokens[0]!.audibleEnd; }, "DEPENDENCIES_SCHEMA_INVALID"],
];
for (const [name, mutate, code] of mutations) test(`refuses ${name} at both seams`, () => { const input = specimen(); mutate(input); refused(input, code); });

test("same-token edge ordering permits before→after; duplicate, reverse and subframe edges refuse", () => {
  const input = specimen(); returned(input).inpoint = anchor(input, 1, "after");
  expect(validateScriptDocumentV2(input.document).valid).toBe(true);
  const projection = projectPrimarySequenceV2(input.document, { narrationBoundaryEvidence: [evidence(input)] });
  expect(projection.rows[0]?.tokens.map((item) => item.primarySlotId)).toEqual([row(input).primaryVisualSequence!.slots[0]!.id, child(input).id, row(input).primaryVisualSequence!.slots[0]!.id]);
  returned(input).inpoint = anchor(input, 1); refused(input, "BOUNDARY_DUPLICATE");
  returned(input).inpoint = anchor(input, 0, "after"); refused(input, "BOUNDARY_ORDER_INVALID");
  returned(input).inpoint = anchor(input, 1, "after"); evidence(input).tokens[0]!.onset = time(1001, 1000); evidence(input).tokens[0]!.audibleEnd = time(501, 500);
  refused(input, "COLLAPSED_BOUNDARY");
});

test("complete maps can explicitly resolve after edges; derived ends cannot substitute", () => {
  const input = JSON.parse(readFileSync(`${root}docs/verification/issue-179/complete.input.json`, "utf8")) as Input;
  returned(input).inpoint = anchor(input, 1, "after"); expect(compiled(input).report.status).toBe("ready");
  const mark = input.dependencies.narrationTimingMaps[0]!.tokens[1]!; delete mark.audibleEnd; mark.endBasis = "next_word_derived";
  refused(input, "STALE_ANCHOR");
});

function command(input: Input, value: VisualSequenceEditCommandV2) {
  return applyVisualSequenceEditV2(input.document, row(input).primaryVisualSequence!.version, value);
}
test("atomic moves preserve affinity by default and can select an explicit edge", () => {
  const input = specimen(); returned(input).inpoint = anchor(input, 1, "after");
  const blockId = row(input).id; const boundaryOwnerId = returned(input).id;
  const moved = command(input, { kind: "move_word_boundary", blockId, boundaryOwnerId, tokenId: row(input).tokens[2]!.id });
  expect(moved.ok).toBe(true); input.document = moved.document;
  expect(returned(input).inpoint?.affinity).toBe("after"); expect(returned(input).inpoint?.quotedWord).toBe("gamma");
  const explicit = command(input, { kind: "move_word_boundary", blockId, boundaryOwnerId, tokenId: row(input).tokens[2]!.id, affinity: "before" });
  expect(explicit.ok).toBe(true); input.document = explicit.document; expect(returned(input).inpoint?.affinity).toBe("before");
  const before = canonicalJson(input.document);
  const bad = command(input, { kind: "move_word_boundary", blockId, boundaryOwnerId, tokenId: row(input).tokens[1]!.id, affinity: "before" });
  expect(bad.ok).toBe(false); expect(canonicalJson(bad.document)).toBe(before);
});

function mediaBoundaryInput(): Input {
  const input = JSON.parse(readFileSync(`${root}tests/data/authoring_v2/issue_173/compiler/media-end-between-words.input.golden.json`, "utf8")) as Input;
  const map = input.dependencies.narrationTimingMaps[0]!;
  const value = evidence(specimen());
  Object.assign(value, { blockId: map.blockId, blockRevision: map.blockRevision, textHash: map.textHash, narrationAssetId: map.narrationAssetId,
    audioHash: map.audioHash, timingHash: map.timingHash, alignmentVersion: map.alignmentVersion, audio: map.audio });
  value.tokens = map.tokens.slice(1).map((item) => ({ tokenId: item.tokenId, startOffset: item.startOffset, endOffset: item.endOffset,
    quotedText: item.quotedText, onset: item.startTime, ...(item.audibleEnd ? { audibleEnd: item.audibleEnd } : {}) }));
  input.dependencies.narrationTimingMaps = []; input.dependencies.narrationBoundaryEvidence = [value];
  return input;
}
for (const relation of ["at_word_start", "at_word_end", "inside_word", "between_words", "derived_or_unknown", "nonadjacent"] as const) {
  test(`media relation ${relation} uses only evidenced supports and frozen adjacency`, () => {
    const input = mediaBoundaryInput(); const marks = evidence(input).tokens;
    // The complete clip ends at exactly ten seconds, independently of word timing.
    if (relation === "at_word_start") marks[1]!.onset = time(10);
    if (relation === "at_word_end") marks[0]!.audibleEnd = time(10);
    if (relation === "inside_word") marks[0]!.audibleEnd = time(41, 4);
    if (relation === "derived_or_unknown") delete marks[0]!.audibleEnd;
    if (relation === "nonadjacent") {
      const block = row(input); block.text = "alpha beta missing gamma";
      block.tokens.splice(2, 0, { id: id(200), value: "missing", startOffset: 11, endOffset: 18 });
      block.tokens[3]!.startOffset = 19; block.tokens[3]!.endOffset = 24;
      marks[1]!.startOffset = 19; marks[1]!.endOffset = 24;
      evidence(input).textHash = hash(block.text); input.dependencies.document.textHash = hash(block.text);
    }
    const result = compiled(input); expect(result.report.status).toBe("ready"); expect(needs(input).ok).toBe(true);
    const cut = result.manifest.boundaryEvidence.find((item) => item.kind === "media_end")!;
    expect(cut.inputTime).toEqual(time(10));
    expect(cut.wordRelation).toBe(relation === "nonadjacent" ? "derived_or_unknown" : relation);
    expect(cut.precision).toBe(relation === "at_word_start" ? "verified_onset" : relation === "at_word_end" || relation === "inside_word" ? "audible_word" : relation === "between_words" ? "between_words" : "unknown");
    expect(cut.boundaryEvidenceHash).toBe(sha256CanonicalJson(evidence(input)));
    const sequenceBoundary = result.manifest.visualSequenceResolutions.find((item) => item.boundaryKind === "media_end")!;
    expect(sequenceBoundary.alignmentPrecision).toBe(cut.precision);
    expect(sequenceBoundary.boundaryDelta).toEqual(cut.delta);
  });
}
test("coincident end/onset uses onset precedence and keeps its token identity", () => {
  const input = mediaBoundaryInput(); evidence(input).tokens[0]!.audibleEnd = time(10); evidence(input).tokens[1]!.onset = time(10);
  const cut = compiled(input).manifest.boundaryEvidence.find((item) => item.kind === "media_end")!;
  expect(cut.wordRelation).toBe("at_word_start"); expect(cut.relatedTokenId).toBe(evidence(input).tokens[1]!.tokenId);
});

test("conflicting reused audio bindings across capability kinds refuse", () => {
  const input = specimen();
  const other = structuredClone(row(input)); other.id = id(500); other.orderKey = "b0";
  other.primaryVisualSequence = { id: id(501), version: 1, slots: [{ id: id(502), kind: "content", relation: { kind: "base" }, boundaryBefore: { kind: "row_start" }, payload: { kind: "on_camera", presenterChoiceId: null }, playoutPolicy: "match_structural_interval", version: 1 }] };
  other.tokens.forEach((item, index) => { item.id = id(510 + index); });
  input.document.activeDraft.blocks.push(other);
  input.dependencies.document.textHash = hash(`${row(input).text}\n${other.text}`);
  const old = JSON.parse(readFileSync(`${root}docs/verification/issue-179/complete.input.json`, "utf8")) as Input;
  const map = old.dependencies.narrationTimingMaps[0]!; map.blockId = other.id;
  map.tokens.forEach((item, index) => { item.tokenId = other.tokens[index]!.id; });
  map.audio!.locator = "Narration/conflicting.wav"; input.dependencies.narrationTimingMaps = [map];
  refused(input, "NARRATION_AUDIO_BINDING_MISMATCH");
});

test("punctuation, repeated words, combining characters and surrogate pairs bind by ID and exact UTF16", () => {
  const input = specimen(); const block = row(input);
  const words = ["😀", "don't,", "don't,", "e\u0301", "é"];
  block.text = words.join(" "); let cursor = 0;
  block.tokens = words.map((value, index) => { const startOffset = cursor; cursor += value.length + 1; return { id: id(700 + index), value, startOffset, endOffset: cursor - 1 }; }) as NarrationBlockV2["tokens"];
  evidence(input).textHash = hash(block.text); input.dependencies.document.textHash = hash(block.text);
  const a = anchor(input, 1); if (a.affinity !== "before") throw new Error("edge");
  child(input).boundaryBefore = { kind: "spoken_word", anchor: a }; returned(input).inpoint = anchor(input, 3);
  evidence(input).tokens = [1, 3].map((index) => ({ tokenId: block.tokens[index]!.id, startOffset: block.tokens[index]!.startOffset, endOffset: block.tokens[index]!.endOffset, quotedText: block.tokens[index]!.value, onset: time(index) }));
  expect(compiled(input).report.status).toBe("ready");
  evidence(input).tokens[0]!.tokenId = block.tokens[2]!.id; refused(input, "STALE_TIMING_MAP");
  evidence(input).tokens[0]!.tokenId = block.tokens[1]!.id; evidence(input).tokens[1]!.quotedText = "é"; refused(input, "STALE_TIMING_MAP");
  evidence(input).tokens[1]!.quotedText = "e\u0301";
  evidence(input).tokens.unshift({ tokenId: block.tokens[0].id, startOffset: 1, endOffset: 2, quotedText: "\ude00", onset: time(0) });
  refused(input, "STALE_TIMING_MAP");
});

test("editor after-point accepts end-only evidence and missing end is an operation-local blocker", () => {
  const input = specimen(); endpointsOnly(input);
  const after = anchor(input, 1, "after"); if (after.affinity !== "after") throw new Error("edge");
  const placement: PointPlacement = { kind: "point", anchor: { kind: "audible_word_end", anchor: after } };
  input.document.activeDraft.supportingItems.push({ id: id(800), orderKey: "a0", version: 1, role: "editor_note", content: "Synthetic note", placement });
  const beta = row(input).tokens[1]!;
  evidence(input).tokens = [{ tokenId: beta.id, startOffset: beta.startOffset, endOffset: beta.endOffset, quotedText: beta.value, audibleEnd: time(3, 2) }];
  const result = compiled(input); expect(result.report.status).toBe("ready");
  expect(result.manifest.events.find((item) => item.kind === "script_marker")?.recordRange).toEqual({ startFrame: 36, endFrame: 37 });
  evidence(input).tokens = []; refused(input, "BOUNDARY_EVIDENCE_REQUIRED");
});

test("synthetic assembling-flow checks source/audio/receipt bytes, current binding and review status", () => {
  const input = specimen(); const value = evidence(input);
  const audioBytes = "synthetic normalized audio bytes"; const sourceBytes = "synthetic reviewed timing source";
  value.audioHash = value.audio.audioHash = hash(audioBytes); value.timingHash = value.audio.timingHash = hash(sourceBytes);
  const currentAudio = structuredClone(value.audio);
  const receiptPayload = () => {
    const { verification, ...binding } = value;
    const review = { method: verification.method, reviewId: verification.reviewId, reviewRevision: verification.reviewRevision, reviewerReference: verification.reviewerReference };
    return { status: "reviewed", binding, review };
  };
  const receiptBytes = canonicalJson(receiptPayload()); value.verification.reviewArtifactHash = hash(receiptBytes);
  const assemble = (audio: string, source: string, receipt: string, status = "reviewed") => {
    if (status !== "reviewed" || hash(audio) !== value.audioHash || hash(source) !== value.timingHash || hash(receipt) !== value.verification.reviewArtifactHash ||
      canonicalJson(value.audio) !== canonicalJson(currentAudio) || receipt !== canonicalJson(receiptPayload())) throw new Error("Unverified or stale synthetic assembly");
    return input;
  };
  expect(compiled(assemble(audioBytes, sourceBytes, receiptBytes)).report.status).toBe("ready");
  expect(() => assemble(`${audioBytes}!`, sourceBytes, receiptBytes)).toThrow();
  expect(() => assemble(audioBytes, `${sourceBytes}!`, receiptBytes)).toThrow();
  expect(() => assemble(audioBytes, sourceBytes, `${receiptBytes}!`)).toThrow();
  expect(() => assemble(audioBytes, sourceBytes, receiptBytes, "candidate")).toThrow();
  value.verification.reviewRevision++; expect(() => assemble(audioBytes, sourceBytes, receiptBytes)).toThrow(); value.verification.reviewRevision--;
  value.tokens[0]!.onset = time(5, 4); expect(() => assemble(audioBytes, sourceBytes, receiptBytes)).toThrow(); value.tokens[0]!.onset = time(1);
  value.audio.locator = "Narration/stale.wav"; expect(() => assemble(audioBytes, sourceBytes, receiptBytes)).toThrow();
});

function overlayInput(): Input {
  const input = specimen();
  const seed = JSON.parse(readFileSync(`${root}tests/data/authoring_v2/issue_173/compiler/root-child-overlay-return.input.golden.json`, "utf8")) as Input;
  const overlay = row(seed).overlayEvents[0]!;
  const after = anchor(input, 1, "after"); if (after.affinity !== "after") throw new Error("edge");
  after.anchorVersion = 3;
  overlay.timing.end = { kind: "audible_word_end", anchor: after }; delete overlay.timing.durationMs;
  row(input).overlayEvents = [overlay];
  input.dependencies.occurrenceResolutions.push(seed.dependencies.occurrenceResolutions[1]!);
  const binding = seed.dependencies.preparedMedia[1]!;
  binding.requestedRange.duration = time(1, 2); binding.verification.decodedFrameCount = 12;
  input.dependencies.preparedMedia.push(binding);
  return input;
}
test("overlay before/end anchors share required evidence, current keyed edges and exact needs", () => {
  const input = overlayInput(); const result = compiled(input);
  expect(result.report.status).toBe("ready");
  const event = result.manifest.events.find((item) => item.kind === "overlay_visual")!;
  expect(event.recordRange).toEqual({ startFrame: 24, endFrame: 36 });
  const req = needs(input); if (!req.ok) throw new Error(JSON.stringify(req));
  expect(req.requirements.find((item) => item.payloadId === event.provenance.payloadId)?.recordRange).toEqual(event.recordRange);
  delete evidence(input).tokens[0]!.audibleEnd; refused(input, "BOUNDARY_EVIDENCE_REQUIRED");
});
test("overlay event-edge dependencies resolve exact intervals; cycles and inconsistent two-of-three refuse", () => {
  const input = overlayInput();
  const first = row(input).overlayEvents[0]!; delete first.timing.end; first.timing.durationMs = 500;
  const second = structuredClone(first); second.id = id(901); second.payload.payloadId = id(902);
  second.timing = { kind: "timed", start: { kind: "event_edge", eventId: first.id, edge: "end" }, durationMs: 500 };
  row(input).overlayEvents.push(second);
  const descriptor = structuredClone(input.dependencies.occurrenceResolutions[1]!);
  descriptor.payloadId = second.payload.payloadId; descriptor.owner = { kind: "overlay_event", blockId: row(input).id, overlayEventId: second.id }; descriptor.preparedMediaRequirementKey = "prep:dependent-overlay";
  input.dependencies.occurrenceResolutions.push(descriptor);
  const binding = structuredClone(input.dependencies.preparedMedia[1]!); binding.requirementKey = descriptor.preparedMediaRequirementKey;
  input.dependencies.preparedMedia.push(binding);
  const result = compiled(input); expect(result.report.status).toBe("ready");
  expect(result.manifest.events.find((item) => item.provenance.overlayEventId === second.id)?.recordRange).toEqual({ startFrame: 36, endFrame: 48 });
  const view = projectPrimarySequenceV2(input.document, { narrationBoundaryEvidence: [evidence(input)] });
  expect(view.rows[0]!.overlays.map((item) => item.humanOrdinal)).toEqual([2, 3]);
  first.timing.start = { kind: "event_edge", eventId: second.id, edge: "end" }; refused(input, "STALE_ANCHOR");
  const original = overlayInput(); row(original).overlayEvents[0]!.timing.durationMs = 600; refused(original, "STALE_ANCHOR");
});
test("overlay row endpoints use adjacent blocks without inventing final-word ends", () => {
  const input = overlayInput(); endpointsOnly(input);
  const next = structuredClone(row(input)); next.id = id(910); next.orderKey = "b0"; next.overlayEvents = [];
  next.tokens.forEach((item, index) => { item.id = id(920 + index); });
  next.primaryVisualSequence = { id: id(930), version: 1, slots: [{ id: id(931), kind: "content", relation: { kind: "base" }, boundaryBefore: { kind: "row_start" }, payload: { kind: "on_camera", presenterChoiceId: null }, playoutPolicy: "match_structural_interval", version: 1 }] };
  input.document.activeDraft.blocks.push(next);
  input.dependencies.document.textHash = hash(`${row(input).text}\n${next.text}`);
  const nextEvidence = structuredClone(evidence(input)); nextEvidence.blockId = next.id;
  input.dependencies.narrationBoundaryEvidence!.push(nextEvidence);
  row(input).overlayEvents[0]!.timing = { kind: "timed", end: { kind: "between_blocks", beforeBlockId: row(input).id, afterBlockId: next.id }, durationMs: 500 };
  const result = compiled(input); expect(result.report.status).toBe("ready");
  expect(result.manifest.events.find((item) => item.kind === "overlay_visual")?.recordRange).toEqual({ startFrame: 84, endFrame: 96 });
  expect(result.manifest.timeline.durationFrames).toBe(192); expect(needs(input).ok).toBe(true);
});

test("insert, convert, flatten, swap and delete preserve explicit after edges", () => {
  const input = specimen(); endpointsOnly(input);
  const blockId = row(input).id;
  const inserted = command(input, { kind: "insert_sequential", blockId, slotId: id(1000), boundary: anchor(input, 1, "after"), payload: { kind: "on_camera", presenterChoiceId: null } });
  expect(inserted.ok).toBe(true); input.document = inserted.document;
  expect(child(input).boundaryBefore.kind).toBe("audible_word_end");
  const converted = command(input, { kind: "convert_sequential_to_cutaway", blockId, slotId: id(1000), returnSlotId: id(1001) });
  expect(converted.ok).toBe(true); input.document = converted.document;
  expect(child(input).boundaryBefore.kind).toBe("audible_word_end");
  const ret = command(input, { kind: "move_word_boundary", blockId, boundaryOwnerId: id(1001), tokenId: row(input).tokens[2]!.id, affinity: "after" });
  expect(ret.ok).toBe(true); input.document = ret.document;
  const flat = command(input, { kind: "flatten_cutaway_group", blockId, parentSlotId: row(input).primaryVisualSequence!.slots[0]!.id });
  expect(flat.ok).toBe(true); input.document = flat.document;
  expect(child(input).boundaryBefore.kind).toBe("audible_word_end");
  const swap = command(input, { kind: "swap_payloads", blockId, firstSlotId: row(input).primaryVisualSequence!.slots[0]!.id, secondSlotId: id(1000) });
  expect(swap.ok).toBe(true); input.document = swap.document;
  expect(child(input).boundaryBefore.kind).toBe("audible_word_end");
  const removed = command(input, { kind: "delete_slot", blockId, slotId: id(1000) }); expect(removed.ok).toBe(true);
});
test("cutaway insertion and root deletion keep before/after on one token as distinct edges", () => {
  const input = specimen(); endpointsOnly(input); const blockId = row(input).id; const parentSlotId = row(input).primaryVisualSequence!.slots[0]!.id;
  const inserted = command(input, { kind: "insert_cutaway", blockId, slotId: id(1010), returnSlotId: id(1011), parentSlotId, boundary: anchor(input, 1), payload: { kind: "on_camera", presenterChoiceId: null } });
  expect(inserted.ok).toBe(true); input.document = inserted.document;
  const ret = command(input, { kind: "move_word_boundary", blockId, boundaryOwnerId: id(1011), tokenId: row(input).tokens[1]!.id, affinity: "after" });
  expect(ret.ok).toBe(true); input.document = ret.document;
  const removed = command(input, { kind: "delete_slot", blockId, slotId: parentSlotId, replacementSlotId: id(1012), replacementPayloadId: id(1013) });
  expect(removed.ok).toBe(true);
  const afters = (removed.document.activeDraft.blocks[0] as NarrationBlockV2).primaryVisualSequence!.slots.filter((item) => item.kind === "content" && item.boundaryBefore.kind === "audible_word_end");
  expect(afters).toHaveLength(1);
});
test("boundary-only data cannot masquerade as full speech coverage or recorded alignment", () => {
  const input = specimen();
  Object.assign(input.dependencies, { narrationTimingMaps: [evidence(input)] }); refused(input, "DEPENDENCIES_SCHEMA_INVALID");
  input.dependencies.narrationTimingMaps = []; child(input).payload = { kind: "on_camera", presenterChoiceId: id(1100) };
  const result = compiled(input); expect(result.report.status).toBe("blocked");
  expect(result.report.diagnostics.some((item) => item.code === "MIGRATION_REVIEW_REQUIRED")).toBe(true);
  expect(result.manifest.events.filter((item) => item.trackRole === "child")).toEqual([]);
});
test("rational quantization overflow and return at row end refuse without truncating audio", () => {
  const input = specimen(); returned(input).inpoint = anchor(input, 2, "after"); evidence(input).tokens[1]!.audibleEnd = time(4);
  refused(input, "COLLAPSED_BOUNDARY");
  endpointsOnly(input); evidence(input).audio.durationSamples = Number.MAX_SAFE_INTEGER; evidence(input).audio.sampleRate = 1;
  refused(input);
});

test("playout restoration adopts the explicit after edge; sparse projection keeps honest preview fallback", () => {
  const input = mediaBoundaryInput();
  const view = projectPrimarySequenceV2(input.document, { narrationBoundaryEvidence: [evidence(input)], mediaBounds: input.dependencies.occurrenceResolutions.map((item) => ({ mediaReferenceId: item.mediaReferenceId, contentHash: item.sourceSnapshot.contentHash, loggedStartFrame: item.logicalSourceBounds.startFrame, loggedEndExclusiveFrame: item.logicalSourceBounds.endFrame, frameRate: item.logicalSourceBounds.frameRate })) });
  expect(view.rows[0]!.mediaCutEstimates[0]!.timingSource).toBe("400ms_per_token_fallback");
  const result = command(input, { kind: "set_playout_policy", blockId: row(input).id, slotId: row(input).primaryVisualSequence!.slots[0]!.id, policy: "match_structural_interval", nextBoundary: anchor(input, 1, "after") });
  expect(result.ok).toBe(true); input.document = result.document;
  expect(child(input).boundaryBefore.kind).toBe("audible_word_end");
});
test("cross-row move and supporting-picture promotion preserve explicit destination edges atomically", () => {
  const input = specimen(); const destination = structuredClone(row(input)); destination.id = id(1200); destination.orderKey = "b0";
  destination.tokens.forEach((item, index) => { item.id = id(1210 + index); });
  destination.primaryVisualSequence = { id: id(1220), version: 1, slots: [{ id: id(1221), kind: "content", relation: { kind: "base" }, boundaryBefore: { kind: "row_start" }, payload: { kind: "on_camera", presenterChoiceId: null }, playoutPolicy: "match_structural_interval", version: 1 }] };
  input.document.activeDraft.blocks.push(destination);
  const target = { blockId: destination.id, tokenId: destination.tokens[1]!.id, affinity: "after" as const, quotedWord: "beta", anchorVersion: 1 };
  const moved = command(input, { kind: "move_payload", sourceBlockId: row(input).id, sourceSlotId: child(input).id, sourceRepair: "reject", destinationBlockId: destination.id, expectedDestinationSequenceVersion: 1, destination: { kind: "sequential", boundary: target, slotId: id(1230) } });
  expect(moved.ok).toBe(true);
  const targetRow = moved.document.activeDraft.blocks[1] as NarrationBlockV2;
  const movedSlot = targetRow.primaryVisualSequence!.slots[1]!;
  expect(movedSlot.kind === "content" && movedSlot.boundaryBefore.kind).toBe("audible_word_end");
  input.document = moved.document;
  input.document.activeDraft.supportingItems.push({ id: id(1240), version: 1, orderKey: "a0", role: "picture", content: "Synthetic picture", pictureKind: "clip", source: { kind: "media_reference", mediaReferenceId: id(1241) }, placement: { kind: "unplaced", reason: "not yet placed" } });
  const result = command(input, { kind: "promote_supporting_picture", blockId: row(input).id, supportingItemId: id(1240), destination: { kind: "sequential", boundary: anchor(input, 1, "after"), slotId: id(1242) }, audioPolicy: "mute", framingPolicy: "contain", sourceUsage: { sourceInFrame: 0 } });
  expect(result.ok).toBe(true); input.document = result.document;
  expect(child(input).boundaryBefore.kind).toBe("audible_word_end");
  expect(input.document.activeDraft.supportingItems).toEqual([]);
});

test("picture requirements tolerate holes before, between and after requested onsets", () => {
  const input = specimen(); const block = row(input);
  block.text = "alpha beta missing delta tail";
  const values = ["alpha", "beta", "missing", "delta", "tail"]; let offset = 0;
  block.tokens = values.map((value, index) => { const startOffset = offset; offset += value.length + 1; return { id: id(1300 + index), value, startOffset, endOffset: offset - 1 }; }) as NarrationBlockV2["tokens"];
  evidence(input).textHash = hash(block.text); input.dependencies.document.textHash = hash(block.text);
  const before = anchor(input, 1); if (before.affinity !== "before") throw new Error("edge");
  child(input).boundaryBefore = { kind: "spoken_word", anchor: before }; returned(input).inpoint = anchor(input, 3);
  evidence(input).tokens = [1, 3].map((index, position) => ({ tokenId: block.tokens[index]!.id, quotedText: block.tokens[index]!.value, startOffset: block.tokens[index]!.startOffset, endOffset: block.tokens[index]!.endOffset, onset: time(position + 1) }));
  expect(compiled(input).manifest.events.find((item) => item.trackRole === "child")?.recordRange).toEqual({ startFrame: 24, endFrame: 48 });
  expect(needs(input).ok).toBe(true);
});
test("sparse evidence preserves source shortage and frozen document identity refusals", () => {
  const input = specimen(); input.dependencies.occurrenceResolutions[0]!.logicalSourceBounds.endFrame = 1;
  refused(input, "SOURCE_INSUFFICIENT");
  for (const field of ["documentId", "projectId", "liveHeadSequence", "contentHash", "textHash", "settingsHash"] as const) {
    const stale = specimen(); const binding = stale.dependencies.document;
    if (field === "liveHeadSequence") binding[field]++;
    else binding[field] = field === "documentId" || field === "projectId" ? id(1400) : hash("stale");
    const result = compileTimelineV2(stale.document, stale.dependencies);
    expect(result.ok).toBe(false);
  }
});
