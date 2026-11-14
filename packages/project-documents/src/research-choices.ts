/** Read-only Research revision choices. No Research bearer or Timeline grant is interchangeable. */
import type { PrincipalRef } from "@vera/contracts";
import type {
  NarrationBlockV2, ResearchClipSnapshotV2, ScriptDocumentV2, VisualOnlyBlockV2,
} from "@vera/contracts/v2";
import {
  assessResearchRevision,
  type ResearchRevisionAssessment,
  type ResearchRevisionChangedField,
} from "@vera/contracts/research-revision-choice";
import { ProjectAuthError } from "@vera/project-authorization";

import { ProjectDocumentError, ProjectDocumentInputError, requireUuid } from "./model.js";
import type { DocumentView, ProjectDocumentService } from "./service.js";

/** Implementations MUST reauthorize this exact principal with Research for EVERY read.
 * A process-wide development bearer, cached grant, or Timeline membership is not proof.
 * The port must only issue authorized Research GETs, never updates or exports.
 */
export interface ResearchAuthorizedReadPort {
  readCurrentClip(principal: PrincipalRef, researchProjectId: string, clipId: string): Promise<unknown>;
}

/** The trusted port uses this only for a real Research permission refusal. */
export class ResearchReadDeniedError extends Error {
  override readonly name = "ResearchReadDeniedError";
  constructor() { super("research_access_denied"); }
}

export type ResearchOccurrenceLocation =
  | { kind: "active_visual" | "stash_visual"; rowId: string; stashBundleId?: string }
  | { kind: "active_attachment" | "stash_attachment"; rowId: string; stashBundleId?: string }
  | { kind: "active_primary" | "stash_primary"; rowId: string; slotId: string; stashBundleId?: string }
  | { kind: "active_overlay" | "stash_overlay"; rowId: string; eventId: string; stashBundleId?: string };

export interface ResearchOccurrence {
  occurrenceId: string;
  location: ResearchOccurrenceLocation;
  pinned: ResearchClipSnapshotV2;
}

export interface ResearchChoiceSummary {
  occurrenceId: string;
  location: ResearchOccurrenceLocation;
  pinnedVersion: number;
  state: ResearchRevisionAssessment["kind"];
  latestVersion?: number;
  changedFields?: ResearchRevisionChangedField[];
  reason?: "identity" | "older_version" | "same_version_changed";
}

export interface ResearchChoicesView {
  projectId: string;
  revision: number;
  digest: string;
  occurrences: ResearchChoiceSummary[];
}

export interface ResearchCompareView {
  projectId: string;
  revision: number;
  digest: string;
  occurrenceId: string;
  location: ResearchOccurrenceLocation;
  assessment: ResearchRevisionAssessment;
}

/** Bound entire scans and network requests; never return a truncated, misleading list. */
export const MAX_RESEARCH_OCCURRENCES = 256;

/** Ordered by saved active rows, then Stash bundles, and by local slot/event order.
 * The active mirror of an attached clip is only a projection, not a second occurrence.
 */
export function enumerateResearchOccurrences(document: ScriptDocumentV2): ResearchOccurrence[] {
  const occurrences: ResearchOccurrence[] = [];
  const identities = new Set<string>();
  const add = (occurrenceId: string, pinned: ResearchClipSnapshotV2 | undefined,
    location: ResearchOccurrenceLocation): void => {
    if (!pinned) return;
    const id = requireUuid(occurrenceId);
    // Never accidentally merge unrelated uses of the same Research source.
    if (identities.has(id)) throw new ProjectDocumentError("service_unavailable", 503);
    if (occurrences.length >= MAX_RESEARCH_OCCURRENCES) {
      throw new ProjectDocumentInputError("Too many Research occurrences to compare at once.");
    }
    identities.add(id);
    occurrences.push({ occurrenceId: id, pinned: structuredClone(pinned), location });
  };

  const visual = (row: VisualOnlyBlockV2, stashed: boolean, bundleId?: string): void =>
    add(row.id, row.researchClip, {
      kind: stashed ? "stash_visual" : "active_visual", rowId: row.id,
      ...(bundleId ? { stashBundleId: bundleId } : {}),
    });
  const narration = (row: NarrationBlockV2, stashed: boolean, bundleId?: string): void => {
    const suffix = bundleId ? { stashBundleId: bundleId } : {};
    if (row.attachedFootage) {
      const clip = row.attachedFootage.clip;
      add(clip.id, clip.researchClip, {
        kind: stashed ? "stash_attachment" : "active_attachment", rowId: row.id, ...suffix,
      });
    }
    for (const slot of row.primaryVisualSequence?.slots ?? []) {
      if (slot.kind !== "content" || slot.payload.kind !== "visual") continue;
      // An active converted attached note projects its authoritative attachment
      // into a base slot; the schema validator enforces an exact mirror.
      const mirrored = !stashed && !!row.attachedFootage &&
        row.stashOrigin?.kind === "note" && row.stashOrigin.returnEligible &&
        row.primaryVisualSequence?.slots.length === 1 &&
        slot.relation.kind === "base" && slot.boundaryBefore.kind === "row_start";
      if (!mirrored) add(slot.payload.payloadId, slot.payload.researchClip, {
        kind: stashed ? "stash_primary" : "active_primary", rowId: row.id, slotId: slot.id, ...suffix,
      });
    }
    for (const event of row.overlayEvents) {
      add(event.payload.payloadId, event.payload.researchClip, {
        kind: stashed ? "stash_overlay" : "active_overlay", rowId: row.id, eventId: event.id, ...suffix,
      });
    }
  };
  const visit = (row: ScriptDocumentV2["activeDraft"]["blocks"][number],
    stashed: boolean, bundleId?: string): void => {
    if (row.type === "visual_only") visual(row, stashed, bundleId);
    else if (row.type === "narration") narration(row, stashed, bundleId);
  };
  for (const row of document.activeDraft.blocks) visit(row, false);
  for (const bundle of document.stash ?? []) {
    for (const row of bundle.rows) visit(row, true, bundle.id);
  }
  return occurrences;
}

const unavailable = (): ProjectDocumentError => new ProjectDocumentError("service_unavailable", 503);

function summary(occurrence: ResearchOccurrence, assessment: ResearchRevisionAssessment): ResearchChoiceSummary {
  const base = { occurrenceId: occurrence.occurrenceId, location: occurrence.location,
    pinnedVersion: occurrence.pinned.clipVersion, state: assessment.kind };
  if (assessment.kind === "update_available") {
    return { ...base, latestVersion: assessment.latest.clipVersion, changedFields: assessment.changedFields };
  }
  if (assessment.kind === "inconsistent") return { ...base, reason: assessment.reason };
  return base;
}

/** Do not return any candidate when any Research read is denied or malformed. */
export class ResearchChoiceReadService {
  constructor(
    private readonly documents: ProjectDocumentService,
    private readonly research: ResearchAuthorizedReadPort,
  ) {}

  private async readCandidate(principal: PrincipalRef, pinned: ResearchClipSnapshotV2): Promise<unknown> {
    try {
      return await this.research.readCurrentClip(principal, pinned.researchProjectId, pinned.clipId);
    } catch (error) {
      if (error instanceof ResearchReadDeniedError ||
        error instanceof ProjectAuthError && error.status === 403) {
        throw new ProjectAuthError("action_not_allowed", 403);
      }
      throw unavailable();
    }
  }

  private assess(pinned: ResearchClipSnapshotV2, candidate: unknown): ResearchRevisionAssessment {
    try {
      const assessment = assessResearchRevision(pinned,
        candidate as Parameters<typeof assessResearchRevision>[1]);
      // A provider returning another user's clip is a broken trust boundary, not
      // a legitimate revision to compare or a chance to disclose its contents.
      if (assessment.kind === "inconsistent" && assessment.reason === "identity") throw unavailable();
      return assessment;
    } catch {
      throw unavailable();
    }
  }

  private async begin(projectId: string, principal: PrincipalRef): Promise<{
    document: DocumentView; occurrences: ResearchOccurrence[];
  }> {
    // Timeline authorization happens before Research access, including unknown ids.
    const document = await this.documents.getDocument(projectId, principal);
    return { document, occurrences: enumerateResearchOccurrences(document.document) };
  }

  private async recheck(document: DocumentView, principal: PrincipalRef): Promise<void> {
    // Fail closed on mid-read Timeline revocation or a changed document head.
    const latest = await this.documents.getDocument(document.projectId, principal);
    if (latest.revision !== document.revision || latest.digest !== document.digest) {
      throw new ProjectDocumentError("version_conflict", 409);
    }
  }

  async list(projectIdInput: string, principal: PrincipalRef): Promise<ResearchChoicesView> {
    const projectId = requireUuid(projectIdInput);
    const { document, occurrences } = await this.begin(projectId, principal);
    // A request-scoped cache only. Each request rechecks Research permission.
    const assessed = new Map<string, unknown>();
    const result: ResearchChoiceSummary[] = [];
    for (const occurrence of occurrences) {
      const key = `${occurrence.pinned.researchProjectId.toLowerCase()}/${occurrence.pinned.clipId.toLowerCase()}`;
      if (!assessed.has(key)) {
        // Cached *candidate*, not an assessment against the first occurrence's pin.
        assessed.set(key, await this.readCandidate(principal, occurrence.pinned));
      }
      result.push(summary(occurrence, this.assess(occurrence.pinned, assessed.get(key))));
    }
    await this.recheck(document, principal);
    return { projectId, revision: document.revision, digest: document.digest, occurrences: result };
  }

  async compare(projectIdInput: string, principal: PrincipalRef, occurrenceIdInput: string): Promise<ResearchCompareView> {
    const projectId = requireUuid(projectIdInput);
    const occurrenceId = requireUuid(occurrenceIdInput);
    const { document, occurrences } = await this.begin(projectId, principal);
    const occurrence = occurrences.find((item) => item.occurrenceId === occurrenceId);
    if (!occurrence) throw new ProjectDocumentError("not_found", 404);
    const assessment = this.assess(occurrence.pinned, await this.readCandidate(principal, occurrence.pinned));
    await this.recheck(document, principal);
    return { projectId, revision: document.revision, digest: document.digest,
      occurrenceId, location: occurrence.location, assessment };
  }
}
