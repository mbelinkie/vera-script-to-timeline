/** Independently authorized Research revision choices; no shared Research/Timeline grants. */
import type { PrincipalRef } from "@vera/contracts";
import { snapshotResearchCandidateV2 } from "@vera/contracts/authoring-v2";
import type {
  NarrationBlockV2, ResearchClipSnapshotV2, ScriptDocumentV2, VisualOnlyAdditionalV2, VisualOnlyBlockV2,
} from "@vera/contracts/v2";
import {
  assessResearchRevision,
  type ResearchRevisionAssessment,
  type ResearchRevisionChangedField,
} from "@vera/contracts/research-revision-choice";
import { ProjectAuthError } from "@vera/project-authorization";

import { fingerprint, ProjectDocumentError, ProjectDocumentInputError, requireRevision, requireUuid } from "./model.js";
import type { DocumentView, ProjectDocumentService, ResearchChoiceInput } from "./service.js";

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

interface SavedVisualOwner {
  occurrenceId: string;
  location: ResearchOccurrenceLocation;
  pinned?: ResearchClipSnapshotV2;
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

/** Only replace one saved occurrence. All other pins, placements and rows are copied untouched.
 * Unresolved visual sources cannot inherit verified bytes or source frames from another version.
 */
export function updateResearchOccurrence(
  document: ScriptDocumentV2, occurrenceId: string, latest: ResearchClipSnapshotV2,
): ScriptDocumentV2 {
  const copy = structuredClone(document);
  let changed = 0;
  const unresolved = { kind: "unresolved_visual" as const,
    description: "Research clip lacks verified Timeline media/frame binding" };
  const replaceClip = (clip: VisualOnlyAdditionalV2): void => {
    if (!clip.researchClip) throw new ProjectDocumentError("version_conflict", 409);
    clip.researchClip = structuredClone(latest);
    delete clip.frameBinding;
    clip.payload.pictureKind = "unresolved_visual";
    clip.payload.source = structuredClone(unresolved);
    delete clip.visualOnlyTiming.selectedSourceRange;
    changed++;
  };
  const updateClip = (clip: VisualOnlyBlockV2): void => {
    if (clip.id !== occurrenceId) return;
    replaceClip(clip);
    clip.version += 1;
  };
  const updateNarration = (row: NarrationBlockV2, stashed: boolean): void => {
    const clip = row.attachedFootage?.clip;
    if (clip?.id === occurrenceId) {
      updateClip(clip);
      // The sole active projected slot is not independently selectable.
      if (!stashed && row.stashOrigin?.kind === "note" && row.stashOrigin.returnEligible) {
        const slot = row.primaryVisualSequence?.slots[0];
        if (!slot || row.primaryVisualSequence?.slots.length !== 1 ||
            slot.kind !== "content" || slot.payload.kind !== "visual") {
          throw new ProjectDocumentError("service_unavailable", 503);
        }
        slot.payload.researchClip = structuredClone(latest);
        delete slot.payload.frameBinding;
        delete slot.payload.selectedSourceRange;
        slot.payload.pictureKind = "unresolved_visual";
        slot.payload.source = structuredClone(unresolved);
        slot.payload.sourceUsage = null;
        slot.version++;
        row.primaryVisualSequence.version++;
      }
      row.version++;
      return;
    }
    for (const slot of row.primaryVisualSequence?.slots ?? []) {
      if (slot.kind !== "content" || slot.payload.kind !== "visual" ||
          slot.payload.payloadId !== occurrenceId) continue;
      if (!slot.payload.researchClip) throw new ProjectDocumentError("version_conflict", 409);
      slot.payload.researchClip = structuredClone(latest);
      delete slot.payload.frameBinding;
      delete slot.payload.selectedSourceRange;
      slot.payload.pictureKind = "unresolved_visual";
      slot.payload.source = structuredClone(unresolved);
      slot.payload.sourceUsage = null;
      slot.version++;
      if (row.primaryVisualSequence) row.primaryVisualSequence.version++;
      row.version++;
      changed++;
    }
    for (const event of row.overlayEvents) {
      if (event.payload.payloadId !== occurrenceId) continue;
      if (!event.payload.researchClip) throw new ProjectDocumentError("version_conflict", 409);
      event.payload.researchClip = structuredClone(latest);
      delete event.payload.frameBinding;
      delete event.payload.selectedSourceRange;
      event.payload.pictureKind = "unresolved_visual";
      event.payload.source = structuredClone(unresolved);
      event.payload.sourceUsage = null;
      event.version++;
      row.version++;
      changed++;
    }
  };
  const visit = (row: ScriptDocumentV2["activeDraft"]["blocks"][number], stashed: boolean): void => {
    if (row.type === "visual_only") {
      updateClip(row);
      for (const child of row.additionalVisuals ?? []) {
        if (child.payload.payloadId !== occurrenceId) continue;
        replaceClip(child);
        // Additional placements have no independent version; the row owns it.
        row.version++;
      }
    } else if (row.type === "narration") updateNarration(row, stashed);
  };
  for (const row of copy.activeDraft.blocks) visit(row, false);
  for (const bundle of copy.stash ?? []) for (const row of bundle.rows) visit(row, true);
  if (changed !== 1) throw new ProjectDocumentError("version_conflict", 409);
  return copy;
}

/** Ordered by saved active rows, then Stash bundles, and by local slot/event order.
 * The active mirror of an attached clip is only a projection, not a second occurrence.
 */
function savedVisualOwners(document: ScriptDocumentV2): SavedVisualOwner[] {
  const owners: SavedVisualOwner[] = [];
  const identities = new Set<string>();
  const add = (occurrenceId: string, pinned: ResearchClipSnapshotV2 | undefined,
    location: ResearchOccurrenceLocation): void => {
    const id = requireUuid(occurrenceId);
    // Never accidentally merge unrelated uses of the same Research source.
    if (identities.has(id)) throw new ProjectDocumentError("service_unavailable", 503);
    identities.add(id);
    owners.push({ occurrenceId: id, ...(pinned ? { pinned: structuredClone(pinned) } : {}), location });
  };

  const visual = (row: VisualOnlyBlockV2, stashed: boolean, bundleId?: string): void => {
    const location: ResearchOccurrenceLocation = {
      kind: stashed ? "stash_visual" : "active_visual", rowId: row.id,
      ...(bundleId ? { stashBundleId: bundleId } : {}),
    };
    add(row.id, row.researchClip, location);
    for (const child of row.additionalVisuals ?? []) {
      add(child.payload.payloadId, child.researchClip, location);
    }
  };
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
  return owners;
}

export function enumerateResearchOccurrences(document: ScriptDocumentV2): ResearchOccurrence[] {
  const occurrences = savedVisualOwners(document).filter(
    (owner): owner is ResearchOccurrence => owner.pinned !== undefined);
  if (occurrences.length > MAX_RESEARCH_OCCURRENCES) {
    throw new ProjectDocumentInputError("Too many Research occurrences to compare at once.");
  }
  return occurrences;
}

/** Generic whole-document saves may move, trim, insert and delete visual uses,
 * but must never change or unpin an existing saved Research occurrence.
 * A replaced payload in the same persistent slot/event/attachment is a retarget,
 * not a deletion. Only the separately authorized choice operation may update it.
 */
export function assertFrozenResearchPinsOnPut(previous: ScriptDocumentV2, next: ScriptDocumentV2): void {
  const prior = savedVisualOwners(previous).filter(
    (owner): owner is ResearchOccurrence => owner.pinned !== undefined);
  const after = savedVisualOwners(next);
  const byId = new Map(after.map((owner) => [owner.occurrenceId, owner] as const));
  const locationKey = (owner: SavedVisualOwner): string => {
    const location = owner.location;
    return JSON.stringify([location.kind, location.rowId,
      "slotId" in location ? location.slotId : null,
      "eventId" in location ? location.eventId : null,
      location.stashBundleId ?? null,
      // Each additional visual is its own saved placement, not the row root.
      (location.kind === "active_visual" || location.kind === "stash_visual") &&
        owner.occurrenceId !== location.rowId ? owner.occurrenceId : null]);
  };
  const byLocation = new Map(after.map((owner) => [locationKey(owner), owner] as const));
  for (const owner of prior) {
    const retained = byId.get(owner.occurrenceId);
    if (retained) {
      if (!retained.pinned || fingerprint(owner.pinned) !== fingerprint(retained.pinned)) {
        throw new ProjectDocumentError("version_conflict", 409);
      }
    } else if (byLocation.has(locationKey(owner))) {
      // Same saved owner, different payload identity: refuse a disguised replacement.
      throw new ProjectDocumentError("version_conflict", 409);
    }
  }
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

  private async readCandidate(principal: PrincipalRef,
    pinned: Pick<ResearchClipSnapshotV2, "researchProjectId" | "clipId">): Promise<unknown> {
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

  async choose(projectIdInput: string, principal: PrincipalRef, input: ResearchChoiceInput) {
    const projectId = requireUuid(projectIdInput);
    if (input.choice !== "keep" && input.choice !== "update") {
      throw new ProjectDocumentInputError("Unknown Research choice.");
    }
    const occurrenceId = requireUuid(input.occurrenceId);
    const researchProjectId = requireUuid(input.researchProjectId);
    const clipId = requireUuid(input.clipId);
    requireRevision(input.expectedRevision);
    if (requireRevision(input.expectedClipVersion) < 1 ||
        requireRevision(input.expectedLatestVersion) < 1) {
      throw new ProjectDocumentInputError("Expected positive Research versions.");
    }
    if (input.choice === "update") requireUuid(input.clientMutationId);
    else if (input.clientMutationId !== undefined) {
      throw new ProjectDocumentInputError("Keep cannot create a mutation receipt.");
    }
    // Check Timeline *edit* rights before even probing the independent Research service.
    const document = await this.documents.getEditableResearchChoiceDocument(projectId, principal,
      input.writeSessionId);
    const occurrence = enumerateResearchOccurrences(document.document)
      .find((item) => item.occurrenceId === occurrenceId);
    if (!occurrence && input.choice === "keep") throw new ProjectDocumentError("not_found", 404);
    const sameSource = !!occurrence &&
      occurrence.pinned.researchProjectId.toLowerCase() === researchProjectId &&
      occurrence.pinned.clipId.toLowerCase() === clipId;
    if (!sameSource && input.choice === "keep") throw new ProjectDocumentError("version_conflict", 409);
    // Read the *original* Research identity on a retry even if the occurrence was
    // subsequently removed or retargeted: a valid receipt must remain replayable.
    const candidate = await this.readCandidate(principal, { researchProjectId, clipId });
    let latest: ResearchClipSnapshotV2;
    if (sameSource) {
      const assessment = this.assess(occurrence.pinned, candidate);
      if (assessment.kind === "inconsistent") throw new ProjectDocumentError("version_conflict", 409);
      latest = assessment.kind === "update_available" ? assessment.latest : assessment.pinned;
    } else {
      // This path cannot create a new mutation: the authorized SQL operation must
      // find an exact matching old receipt or reject the missing/stale occurrence.
      try {
        latest = snapshotResearchCandidateV2(candidate as Parameters<typeof snapshotResearchCandidateV2>[0]);
      } catch { throw unavailable(); }
      if (latest.researchProjectId.toLowerCase() !== researchProjectId ||
          latest.clipId.toLowerCase() !== clipId) throw unavailable();
    }
    // Explicitly reviewed version is essential even for stateless keep and replay.
    if (latest.clipVersion !== input.expectedLatestVersion) {
      throw new ProjectDocumentError("version_conflict", 409);
    }
    return await this.documents.applyResearchChoice(projectId, principal, input, latest);
  }
}
