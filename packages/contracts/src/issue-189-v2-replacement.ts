/** Pure finalization; the host has just verified service/cache/review bytes. */
import { createHash } from "node:crypto";
import { canonicalJson, sha256CanonicalJson } from "./compiler-core.js";
import { compileTimelineV2 } from "./compiler-core-v2.js";
import { validateScriptDocumentV2 } from "./authoring-v2-validation.js";
import { boundaryEvidenceProblemV2 } from "./narration-boundary-evidence-v2.js";
import type { CompilerDependenciesV2, NarrationBoundaryEvidenceV1, ScriptDocumentV2 } from "./generated/contracts-v2.js";

export interface RowRequestV2 {
  schemaVersion: "issue-189-v2-row-request/v1"; policy: "replace_whole_row";
  blockId: string; blockRevision: number; text: string; textHash: string;
  revisedDocumentHash: string; evidenceHash: string; decisionHash: string;
}
export interface RowHandoffV2 {
  schemaVersion: "issue-189-v2-row-handoff/v1"; request: RowRequestV2;
  priorDependenciesHash: string; serviceRequestHash: string; generationReceiptHash: string;
  assetRecordHash: string; audioHash: string; providerTimingHash: string;
  reviewArtifactHash: string; boundaryEvidence: NarrationBoundaryEvidenceV1;
}
const equal = (a: unknown, b: unknown): boolean => canonicalJson(a) === canonicalJson(b);
function fact(value: boolean, reason: string): asserts value { if (!value) throw new Error(reason); }
const hash = (value: string): string => `sha256:${createHash("sha256").update(value, "utf8").digest("hex")}`;
const keys = (value: object, expected: string): boolean => equal(Object.keys(value).sort(), expected.split(" ").sort());

export function validateRowRequestV2(document: ScriptDocumentV2, request: RowRequestV2) {
  fact(validateScriptDocumentV2(document).valid, "v2 validator refused revised document");
  fact(keys(request, "schemaVersion policy blockId blockRevision text textHash revisedDocumentHash evidenceHash decisionHash") &&
    request.schemaVersion === "issue-189-v2-row-request/v1" && request.policy === "replace_whole_row", "unsupported whole-row request");
  fact([request.textHash, request.revisedDocumentHash, request.evidenceHash, request.decisionHash].every((v) => /^sha256:[a-f0-9]{64}$/u.test(v)), "request hash pins required");
  fact(request.revisedDocumentHash === sha256CanonicalJson(document), "stale revised document");
  const row = document.activeDraft.blocks.find((b) => b.id === request.blockId);
  fact(row?.type === "narration" && row.state === "active" && row.version === request.blockRevision &&
    row.text === request.text && request.textHash === hash(row.text), "row/text/revision request differs");
  return row;
}

export function finalizeReplacementV2(document: ScriptDocumentV2, prior: CompilerDependenciesV2, handoff: RowHandoffV2) {
  fact(keys(handoff, "schemaVersion request priorDependenciesHash serviceRequestHash generationReceiptHash assetRecordHash audioHash providerTimingHash reviewArtifactHash boundaryEvidence") &&
    handoff.schemaVersion === "issue-189-v2-row-handoff/v1", "unsupported replacement handoff");
  const row = validateRowRequestV2(document, handoff.request);
  fact([handoff.priorDependenciesHash, handoff.serviceRequestHash, handoff.generationReceiptHash, handoff.assetRecordHash,
    handoff.audioHash, handoff.providerTimingHash, handoff.reviewArtifactHash].every((v) => /^sha256:[a-f0-9]{64}$/u.test(v)), "handoff hash pins required");
  fact(handoff.priorDependenciesHash === sha256CanonicalJson(prior), "prior dependencies changed");
  const evidence = handoff.boundaryEvidence;
  fact(boundaryEvidenceProblemV2(row, evidence) === null && evidence.audioHash === handoff.audioHash &&
    evidence.timingHash === handoff.providerTimingHash && evidence.verification.reviewArtifactHash === handoff.reviewArtifactHash,
    "fresh sparse boundary/audio/timing/review binding differs");
  const old = [...prior.narrationTimingMaps, ...(prior.narrationBoundaryEvidence ?? [])].filter((r) => r.blockId === row.id);
  const previous = old[0];
  fact(old.length === 1 && previous !== undefined && previous.blockRevision + 1 === row.version && previous.audioHash !== evidence.audioHash &&
    previous.narrationAssetId !== evidence.narrationAssetId && previous.timingHash !== evidence.timingHash &&
    previous.audio?.cacheAssetId !== evidence.audio.cacheAssetId, "fresh whole-row asset/revision/timing required");
  fact(!("verification" in previous) || previous.verification.reviewArtifactHash !== handoff.reviewArtifactHash,
    "old acoustic review cannot supply new boundaries");
  const dependencies = structuredClone(prior);
  dependencies.narrationTimingMaps = dependencies.narrationTimingMaps.filter((r) => r.blockId !== row.id);
  const boundaries = dependencies.narrationBoundaryEvidence ?? [];
  const index = boundaries.findIndex((r) => r.blockId === row.id);
  if (index < 0) boundaries.push(structuredClone(evidence)); else boundaries[index] = structuredClone(evidence);
  dependencies.narrationBoundaryEvidence = boundaries;
  dependencies.document = { ...prior.document, contentHash: document.liveContentHash,
    liveHeadSequence: document.liveHeadSequence, revision: prior.document.revision + 1,
    textHash: hash(document.activeDraft.blocks.filter((b) => b.type === "narration").map((b) => b.text).join("\n")) };
  // New deterministic build IDs ensure this preview cannot overwrite the prior target.
  const seed = sha256CanonicalJson({ document, prior, handoff });
  const id = (suffix: string): string => {
    const bytes = createHash("sha256").update(`${seed}:${suffix}`).digest("hex");
    return `${bytes.slice(0, 8)}-${bytes.slice(8, 12)}-4${bytes.slice(13, 16)}-8${bytes.slice(17, 20)}-${bytes.slice(20, 32)}`;
  };
  dependencies.build = { ...prior.build, buildId: id("build"), manifestId: id("manifest"), reportId: id("report") };
  const before = canonicalJson({ document, prior, handoff });
  const a = compileTimelineV2(document, dependencies); const b = compileTimelineV2(document, dependencies);
  fact(a.ok && b.ok, `replacement compile refused: ${canonicalJson(a.ok ? b : a)}`);
  fact(a.report.status !== "blocked" && a.manifestJson === b.manifestJson && a.reportJson === b.reportJson &&
    before === canonicalJson({ document, prior, handoff }), "blocked/nondeterministic/mutated replacement preview");
  return { dependencies, manifest: a.manifest, report: a.report, manifestJson: a.manifestJson, reportJson: a.reportJson };
}
