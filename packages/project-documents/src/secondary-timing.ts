/**
 * Authorization-checked secondary timing read, preview and supported writes.
 *
 * A host may inject ONLY a trusted immutable artifact reader: it must verify
 * stored artifact hashes, build/project ownership and frozen compiler/source
 * pins before returning. Request bodies and HTTP headers are never evidence.
 * Even the trusted adapter's response is rechecked against the current head
 * and an independently compiled manifest, or the request fails closed.
 */
import type { PrincipalRef } from "@vera/contracts";
import type { CompilerDependenciesV2, TimelineManifestV2 } from "@vera/contracts/v2";
import {
  compareSecondaryTimingV2,
  previewSecondaryTimingReconcileV2,
  type SecondaryTimingReconcileCommandV2,
} from "@vera/contracts/authoring-v2";
import { compileTimelineV2 } from "@vera/contracts/compiler-core-v2";

import { fingerprint, ProjectDocumentError, ProjectDocumentInputError,
  requireObject, requireRevision, requireUuid } from "./model.js";
import type { DocumentView, ProjectDocumentService } from "./service.js";

export interface SecondaryTimingEvidenceRequest {
  projectId: string;
  documentId: string;
  revision: number;
  digest: string;
}

/** The port MUST authenticate the immutable artifact's origin, not merely
 * recompute these hashes from arbitrary bytes supplied by the requester.
 * No caller-facing build/manifest selector or payload is supported here.
 */
export interface VerifiedSecondaryTimingEvidencePort {
  readVerified(input: SecondaryTimingEvidenceRequest): Promise<unknown>;
}

export interface VerifiedSecondaryTimingEvidence extends SecondaryTimingEvidenceRequest {
  manifestHash: string;
  dependenciesHash: string;
  manifest: TimelineManifestV2;
  dependencies: CompilerDependenciesV2;
}

export interface SecondaryTimingPreviewInput {
  expectedRevision: number;
  expectedDigest: string;
  command: SecondaryTimingReconcileCommandV2;
}

export interface SecondaryTimingOperationInput extends SecondaryTimingPreviewInput {
  clientMutationId: string;
  writeSessionId?: string;
}

const digestPattern = /^sha256:[a-f0-9]{64}$/u;
const unavailable = (): ProjectDocumentError =>
  new ProjectDocumentError("service_unavailable", 503, { reason: "timing_evidence_unavailable" });

function exact(value: unknown, keys: readonly string[]): Record<string, unknown> {
  const record = requireObject(value);
  if (Object.keys(record).length !== keys.length || keys.some((key) => !Object.hasOwn(record, key))) {
    throw new ProjectDocumentInputError("Invalid secondary timing request shape.");
  }
  return record;
}

function safePositive(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value <= 0) {
    throw new ProjectDocumentInputError("Expected a positive safe integer.");
  }
  return value;
}

function safeSigned(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value)) {
    throw new ProjectDocumentInputError("Expected a signed safe integer.");
  }
  return value;
}

function recordFrame(value: unknown): number {
  return requireRevision(value);
}

function range(value: unknown): { startFrame: number; endFrame: number } {
  const item = exact(value, ["startFrame", "endFrame"]);
  const startFrame = recordFrame(item.startFrame);
  const endFrame = recordFrame(item.endFrame);
  if (startFrame >= endFrame) throw new ProjectDocumentInputError("Collapsed frame range.");
  return { startFrame, endFrame };
}

/** Strictly parse all three currently approved command variants; never cast
 * a JSON object into a compiler command without checking its closed shape.
 */
export function parseSecondaryTimingPreview(value: unknown): SecondaryTimingPreviewInput {
  const top = exact(value, ["expectedRevision", "expectedDigest", "command"]);
  const expectedRevision = requireRevision(top.expectedRevision);
  if (typeof top.expectedDigest !== "string" || !digestPattern.test(top.expectedDigest)) {
    throw new ProjectDocumentInputError("Invalid expected document digest.");
  }
  const command = requireObject(top.command);
  if (command.kind === "primary_frame_offset") {
    const c = exact(command, ["kind", "blockId", "slotId", "expectedSequenceVersion",
      "expectedBaselineFrame", "deltaFrames"]);
    return { expectedRevision, expectedDigest: top.expectedDigest,
      command: { kind: "primary_frame_offset", blockId: requireUuid(c.blockId), slotId: requireUuid(c.slotId),
        expectedSequenceVersion: safePositive(c.expectedSequenceVersion),
        expectedBaselineFrame: recordFrame(c.expectedBaselineFrame), deltaFrames: safeSigned(c.deltaFrames) } };
  }
  if (command.kind === "visual_only_duration") {
    const c = exact(command, ["kind", "blockId", "expectedBlockVersion", "expectedRange", "durationOverrideMs"]);
    return { expectedRevision, expectedDigest: top.expectedDigest,
      command: { kind: "visual_only_duration", blockId: requireUuid(c.blockId),
        expectedBlockVersion: safePositive(c.expectedBlockVersion), expectedRange: range(c.expectedRange),
        durationOverrideMs: safePositive(c.durationOverrideMs) } };
  }
  if (command.kind === "overlay_duration") {
    const c = exact(command, ["kind", "blockId", "overlayEventId", "expectedEventVersion", "expectedRange", "durationMs"]);
    return { expectedRevision, expectedDigest: top.expectedDigest,
      command: { kind: "overlay_duration", blockId: requireUuid(c.blockId),
        overlayEventId: requireUuid(c.overlayEventId), expectedEventVersion: safePositive(c.expectedEventVersion),
        expectedRange: range(c.expectedRange), durationMs: safePositive(c.durationMs) } };
  }
  throw new ProjectDocumentInputError("Unsupported secondary timing command.");
}

/** The write request contains an actor-scoped replay key, never a proposed
 * document or a claimed artifact. A session lease is optional for hosts that
 * do not use live collaboration, but is always checked when supplied. */
export function parseSecondaryTimingOperation(value: unknown): SecondaryTimingOperationInput {
  const input = requireObject(value);
  const keys = Object.hasOwn(input, "writeSessionId") ?
    ["expectedRevision", "expectedDigest", "command", "clientMutationId", "writeSessionId"] :
    ["expectedRevision", "expectedDigest", "command", "clientMutationId"];
  const operation = exact(input, keys);
  const preview = parseSecondaryTimingPreview({ expectedRevision: operation.expectedRevision,
    expectedDigest: operation.expectedDigest, command: operation.command });
  return { ...preview, clientMutationId: requireUuid(operation.clientMutationId),
    ...(Object.hasOwn(operation, "writeSessionId") ?
      { writeSessionId: requireUuid(operation.writeSessionId) } : {}) };
}

function evidenceMatches(value: unknown, basis: DocumentView): value is VerifiedSecondaryTimingEvidence {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const item = value as Record<string, unknown>;
  if (Object.keys(item).length !== 8 ||
      !["projectId", "documentId", "revision", "digest", "manifestHash", "dependenciesHash", "manifest", "dependencies"]
        .every((key) => Object.hasOwn(item, key)) ||
      item.projectId !== basis.projectId || item.documentId !== basis.document.id ||
      item.revision !== basis.revision || item.digest !== basis.digest ||
      typeof item.manifestHash !== "string" || !digestPattern.test(item.manifestHash) ||
      typeof item.dependenciesHash !== "string" || !digestPattern.test(item.dependenciesHash) ||
      !item.manifest || typeof item.manifest !== "object" ||
      !item.dependencies || typeof item.dependencies !== "object") return false;
  try {
    return fingerprint(item.manifest) === item.manifestHash &&
      fingerprint(item.dependencies) === item.dependenciesHash;
  } catch { return false; }
}

export class SecondaryTimingReadService {
  constructor(
    private readonly documents: ProjectDocumentService,
    private readonly evidence: VerifiedSecondaryTimingEvidencePort,
  ) {}

  private async verified(projectIdInput: string, principal: PrincipalRef,
    expected?: Pick<SecondaryTimingPreviewInput, "expectedRevision" | "expectedDigest">): Promise<{
    basis: DocumentView; evidence: VerifiedSecondaryTimingEvidence;
  }> {
    const projectId = requireUuid(projectIdInput);
    // Check Timeline permissions before calling the artifact reader, even for
    // a foreign/unknown project, to avoid cross-project artifact disclosure.
    const basis = await this.documents.getVerifiedSecondaryTimingBasis(projectId, principal);
    if (expected && (basis.revision !== expected.expectedRevision || basis.digest !== expected.expectedDigest)) {
      throw new ProjectDocumentError("version_conflict", 409);
    }
    const request = { projectId, documentId: basis.document.id, revision: basis.revision, digest: basis.digest };
    let evidence: unknown;
    try { evidence = await this.evidence.readVerified(request); } catch { throw unavailable(); }
    if (!evidenceMatches(evidence, basis)) throw unavailable();
    try {
      // SQL heads are zero-based; the frozen v2 compiler identity is one-based.
      // Do not treat either revision namespace as interchangeable.
      if (basis.revision === Number.MAX_SAFE_INTEGER) throw unavailable();
      const compiled = compileTimelineV2(basis.document, evidence.dependencies);
      if (!compiled.ok || compiled.report.readiness.preview !== "ready" ||
          fingerprint(compiled.manifest) !== evidence.manifestHash ||
          evidence.manifest.document.projectId !== projectId ||
          evidence.manifest.document.documentId !== basis.document.id ||
          evidence.manifest.document.revision !== basis.revision + 1 ||
          evidence.dependencies.document.revision !== basis.revision + 1) throw unavailable();
    } catch { throw unavailable(); }
    // A document can be saved or a membership revoked during external IO.
    const latest = await this.documents.getVerifiedSecondaryTimingBasis(projectId, principal);
    if (latest.revision !== basis.revision || latest.digest !== basis.digest ||
        latest.document.id !== basis.document.id) throw new ProjectDocumentError("version_conflict", 409);
    return { basis, evidence };
  }

  async read(projectId: string, principal: PrincipalRef) {
    const { basis, evidence } = await this.verified(projectId, principal);
    try {
      return { schemaVersion: "secondary-timing/v1" as const, projectId: basis.projectId,
        revision: basis.revision, digest: basis.digest, disposition: "verified_read_only" as const,
        manifestHash: evidence.manifestHash, dependenciesHash: evidence.dependenciesHash,
        comparison: compareSecondaryTimingV2(evidence.manifest, evidence.manifest) };
    } catch { throw unavailable(); }
  }

  async preview(projectId: string, principal: PrincipalRef, input: SecondaryTimingPreviewInput) {
    const { basis, evidence } = await this.verified(projectId, principal, input);
    try {
      return { schemaVersion: "secondary-timing/v1" as const, projectId: basis.projectId,
        revision: basis.revision, digest: basis.digest,
        manifestHash: evidence.manifestHash, dependenciesHash: evidence.dependenciesHash,
        result: previewSecondaryTimingReconcileV2(basis.document, evidence.dependencies,
          evidence.manifest, input.command) };
    } catch { throw unavailable(); }
  }

  /** A replay is authorized and checked against the immutable SQL receipt
   * BEFORE asking for evidence from an older head. Fresh commands are then
   * fully checked again under the same head lock as PUT/live collaboration.
   * Nothing here asserts that a subsequent Resolve build took place. */
  async apply(projectId: string, principal: PrincipalRef, input: SecondaryTimingOperationInput) {
    const prior = await this.documents.getSecondaryTimingReplay(projectId, principal, input);
    if (prior) return { schemaVersion: "secondary-timing/v1" as const,
      projectId: prior.projectId, disposition: "authoring_revision_saved" as const, receipt: prior };
    const { evidence } = await this.verified(projectId, principal, input);
    const receipt = await this.documents.applySecondaryTimingOperation(projectId, principal, input, evidence);
    return { schemaVersion: "secondary-timing/v1" as const,
      projectId: receipt.projectId, disposition: "authoring_revision_saved" as const, receipt };
  }
}
