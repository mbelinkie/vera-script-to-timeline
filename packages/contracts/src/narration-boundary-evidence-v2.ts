import { createHash } from "node:crypto";
import { Ajv2020 } from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";
import dependenciesSchema from "../../../contracts/compiler-dependencies-v2.schema.json" with { type: "json" };
import documentSchema from "../../../contracts/script-document-v2.schema.json" with { type: "json" };
import type { NarrationBlockV2, NarrationBoundaryEvidenceV1, RationalTime } from "./generated/contracts-v2.js";

const ajv = new Ajv2020({ allErrors: true, strict: true });
formatsModule.default.default(ajv);
ajv.addSchema(documentSchema);
ajv.addSchema(dependenciesSchema);
const validate = ajv.compile<NarrationBoundaryEvidenceV1>({ $ref: `${dependenciesSchema.$id}#/$defs/NarrationBoundaryEvidenceV1` });

const compare = (a: RationalTime, b: RationalTime): number => {
  const delta = BigInt(a.numerator) * BigInt(b.denominator) - BigInt(b.numerator) * BigInt(a.denominator);
  return delta < 0n ? -1 : delta > 0n ? 1 : 0;
};
function reduced(time: RationalTime): boolean {
  if (!Number.isSafeInteger(time.numerator) || time.numerator < 0 || !Number.isSafeInteger(time.denominator) || time.denominator <= 0) return false;
  let a = BigInt(time.numerator); let b = BigInt(time.denominator);
  while (b) [a, b] = [b, a % b];
  return a === 1n;
}

/** Evidence-method label for manifest/provenance output; measured evidence must never read as reviewed. */
export function boundaryEvidenceOutputFieldsV2(evidence: NarrationBoundaryEvidenceV1, hash: string): { boundaryEvidenceHash: string; boundaryEvidenceMethod?: "measured_audio_boundaries/v1" } {
  return evidence.verification.method === "measured_audio_boundaries/v1" ? { boundaryEvidenceHash: hash, boundaryEvidenceMethod: evidence.verification.method } : { boundaryEvidenceHash: hash };
}

/** Check frozen attestations; receipt/audio byte verification belongs to the assembling flow. */
export function boundaryEvidenceProblemV2(row: NarrationBlockV2, input: unknown): { code: "STALE_TIMING_MAP" | "TEXT_HASH_MISMATCH" | "TIMING_HASH_MISMATCH" | "COLLAPSED_BOUNDARY"; message: string } | null {
  const stale = (message: string) => ({ code: "STALE_TIMING_MAP" as const, message });
  if (!validate(input)) return stale("Boundary evidence does not match its closed versioned schema.");
  const evidence = input;
  if (Buffer.from(row.text, "utf8").toString("utf8") !== row.text || row.tokens.some((token) => Buffer.from(token.value, "utf8").toString("utf8") !== token.value)) return stale("Frozen narration text and tokens must have valid Unicode boundaries.");
  if (evidence.blockId !== row.id || evidence.blockRevision !== row.version) return stale("Boundary evidence names a stale narration row or revision.");
  const textHash = `sha256:${createHash("sha256").update(row.text, "utf8").digest("hex")}`;
  if (evidence.textHash !== textHash) return { code: "TEXT_HASH_MISMATCH", message: "Boundary evidence names a different frozen narration text." };
  const verification = evidence.verification;
  if (verification.method === "measured_audio_boundaries/v1" && (!reduced(verification.onsetUncertainty) || !reduced(verification.audibleEndUncertainty))) return stale("Measured boundary uncertainties must be reduced non-negative rationals.");
  const audio = evidence.audio;
  if (audio.narrationAssetId !== evidence.narrationAssetId || audio.audioHash !== evidence.audioHash) return stale("Boundary evidence and verified audio asset/hash disagree.");
  if (audio.timingHash !== evidence.timingHash) return { code: "TIMING_HASH_MISMATCH", message: "Boundary evidence and cached audio pin different timing sources." };
  const duration = { numerator: audio.durationSamples, denominator: audio.sampleRate };
  let priorIndex = -1;
  let priorOnset: RationalTime | undefined;
  let priorEnd: RationalTime | undefined;
  for (const mark of evidence.tokens) {
    const index = row.tokens.findIndex((token) => token.id === mark.tokenId);
    const token = row.tokens[index];
    if (!token || index <= priorIndex || token.startOffset !== mark.startOffset || token.endOffset !== mark.endOffset || token.value !== mark.quotedText || row.text.slice(mark.startOffset, mark.endOffset) !== mark.quotedText) return stale("Every supplied observation must match a unique frozen token ID, order, UTF-16 range and exact quote.");
    const onset = mark.onset; const end = mark.audibleEnd;
    if (onset && (!reduced(onset) || compare(onset, duration) >= 0 || priorOnset && compare(onset, priorOnset) <= 0 || priorEnd && compare(priorEnd, onset) > 0) ||
        end && (!reduced(end) || end.numerator === 0 || compare(end, duration) > 0 || priorEnd && compare(end, priorEnd) <= 0 || onset && compare(onset, end) >= 0 || priorOnset && compare(priorOnset, end) >= 0)) {
      return { code: "COLLAPSED_BOUNDARY", message: "Observed edges must be reduced, safe, increasing, noncrossing and within exact audio duration." };
    }
    priorIndex = index;
    if (onset) priorOnset = onset;
    if (end) priorEnd = end;
  }
  return null;
}
