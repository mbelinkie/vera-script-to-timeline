import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";
import { compileTimelineV2, resolveMediaRequirementsV2 } from "../src/compiler-core-v2.js";
import { sha256CanonicalJson } from "../src/compiler-core.js";
import type { WordBoundaryAnchorV2 } from "../src/authoring-v2.js";
import { boundaryEvidenceProblemV2 } from "../src/narration-boundary-evidence-v2.js";
import type { CompilerDependenciesV2, NarrationBlockV2, NarrationBoundaryEvidenceV1, ContentSlot, ReturnSlot, ScriptDocumentV2 } from "../src/generated/contracts-v2.js";

type Input = { document: ScriptDocumentV2; dependencies: CompilerDependenciesV2 };
const root = fileURLToPath(new URL("../../../", import.meta.url));
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
const omit = (value: object, keys: string[]) => Object.fromEntries(Object.entries(value).filter(([key]) => !keys.includes(key)));


const measuredVerification = (): NarrationBoundaryEvidenceV1["verification"] => ({
  method: "measured_audio_boundaries/v1",
  algorithm: { id: "vera-polly-marks-energy-ends", version: "1", parametersHash: hash("params"), parameters: { windowMs: 5, hopMs: 5, relativeDb: -30 } },
  measurementArtifactLocator: "Measurements/synthetic-182.json", measurementArtifactHash: hash("measurement artifact"),
  onsetBasis: "provider_word_marks_lag_verified", onsetUncertainty: time(1, 100), audibleEndUncertainty: time(1, 200),
});
function measured(): Input { const input = specimen(); evidence(input).verification = measuredVerification(); return input; }
function configure(input: Input, mode: "before-gamma" | "after-beta" | "final-tail") {
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
  return input;
}

for (const mode of ["before-gamma", "after-beta", "final-tail"] as const) test(`measured evidence anchors ${mode} identically to reviewed and keeps its method`, () => {
  const reviewed = compiled(configure(specimen(), mode));
  const result = compiled(configure(measured(), mode));
  expect(result.report.status).toBe("ready");
  const ranges = (r: typeof result) => r.manifest.events.map((event) => event.recordRange);
  expect(ranges(result)).toEqual(ranges(reviewed));
  expect(result.manifest.boundaryEvidence.map((item) => omit(item, ["boundaryEvidenceHash", "boundaryEvidenceMethod"])))
    .toEqual(reviewed.manifest.boundaryEvidence.map((item) => omit(item, ["boundaryEvidenceHash"])));
  const hashOf = sha256CanonicalJson(evidence(configure(measured(), mode)));
  for (const event of result.manifest.events) { expect(event.provenance.boundaryEvidenceHash).toBe(hashOf); expect(event.provenance.boundaryEvidenceMethod).toBe("measured_audio_boundaries/v1"); }
  expect(result.manifest.visualSequenceResolutions.every((item) => item.boundaryEvidenceMethod === "measured_audio_boundaries/v1")).toBe(true);
  expect(result.manifest.boundaryEvidence.every((item) => item.boundaryEvidenceMethod === "measured_audio_boundaries/v1")).toBe(true);
  expect(result.manifest.boundaryEvidence.length).toBeGreaterThan(0);
  // Reviewed output never gains a method label; measured never reads as reviewed.
  expect(reviewed.manifest.events.every((event) => event.provenance.boundaryEvidenceMethod === undefined)).toBe(true);
  expect(JSON.stringify(result.manifest)).not.toContain("reviewed_audio_boundaries");
});

test("measured token without audibleEnd fails closed for an after-word anchor", () => {
  const input = specimen();
  evidence(input).verification = measuredVerification();
  returned(input).inpoint = anchor(input, 1, "after");
  delete evidence(input).tokens[0]!.audibleEnd;
  const result = refused(input, "BOUNDARY_EVIDENCE_REQUIRED");
  expect(result.ok).toBe(true);
  if (result.ok) expect(result.manifest.events.every((item) => item.kind === "narration")).toBe(true);
});

const malformed: Array<[string, (v: Record<string, unknown>) => void]> = [
  ["bad parametersHash", (v) => { (v.algorithm as Record<string, unknown>).parametersHash = "sha256:xyz"; }],
  ["negative uncertainty", (v) => { v.onsetUncertainty = time(-1, 100); }],
  ["negative end uncertainty", (v) => { v.audibleEndUncertainty = time(-1, 200); }],
  ["unreduced uncertainty", (v) => { v.onsetUncertainty = time(2, 200); }],
  ["unknown method", (v) => { v.method = "measured_audio_boundaries/v2"; }],
  ["missing algorithm", (v) => { delete v.algorithm; }],
  ["wrong algorithm id", (v) => { (v.algorithm as Record<string, unknown>).id = "other"; }],
  ["unknown onset basis", (v) => { v.onsetBasis = "raw_provider_marks"; }],
  ["extra reviewed field mixed in", (v) => { v.reviewId = id(1); }],
  ["bad artifact hash", (v) => { v.measurementArtifactHash = "sha256:00"; }],
  ["absolute artifact locator", (v) => { v.measurementArtifactLocator = "/etc/passwd"; }],
];
for (const [name, mutate] of malformed) test(`malformed measured verification is refused: ${name}`, () => {
  const input = measured();
  mutate(evidence(input).verification as unknown as Record<string, unknown>);
  expect(boundaryEvidenceProblemV2(row(input), evidence(input))).not.toBeNull();
  refused(input);
});

test("reviewed verification still validates unchanged and a measured shape cannot pose as reviewed", () => {
  const input = specimen();
  expect(boundaryEvidenceProblemV2(row(input), evidence(input))).toBeNull();
  const mixed = evidence(input).verification as unknown as Record<string, unknown>;
  mixed.method = "reviewed_audio_boundaries/v1"; Object.assign(mixed, { algorithm: measuredVerification() });
  expect(boundaryEvidenceProblemV2(row(input), evidence(input))).not.toBeNull();
});
