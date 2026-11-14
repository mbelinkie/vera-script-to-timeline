/** Pure comparison of one saved Research pin with a newly authorized Research read. */
import type { ResearchClipSnapshotV2 } from "./generated/contracts-v2.js";
import {
  snapshotResearchCandidateV2,
  type ResearchLoggedCandidateInputV2,
} from "./authoring-v2-research-snapshot.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";

/** Frozen fields whose differences can be displayed without comparing transient DTO metadata. */
export type ResearchRevisionChangedField =
  | "catalogVideoId"
  | "video"
  | "loggedSelection"
  | "englishText"
  | "originalText"
  | "createdBy"
  | "createdAt"
  | "updatedAt";

const frozenFields: readonly ResearchRevisionChangedField[] = [
  "catalogVideoId", "video", "loggedSelection", "englishText",
  "originalText", "createdBy", "createdAt", "updatedAt",
];

export type ResearchRevisionAssessment =
  | { kind: "current"; pinned: ResearchClipSnapshotV2 }
  | {
    kind: "update_available";
    pinned: ResearchClipSnapshotV2;
    latest: ResearchClipSnapshotV2;
    changedFields: ResearchRevisionChangedField[];
  }
  | { kind: "inconsistent"; reason: "identity" | "older_version" | "same_version_changed" };

/**
 * The caller must obtain `candidate` through an independently authorized Research read.
 * This function performs no network, persistence, permission, or media operations.
 * A Research version bump is an available update even if no frozen fields changed.
 * A same-version content drift or older/mismatched result must never be silently accepted.
 */
export function assessResearchRevision(
  pinned: ResearchClipSnapshotV2,
  candidate: ResearchLoggedCandidateInputV2,
): ResearchRevisionAssessment {
  // Validate the *whole* current candidate before comparing or returning any evidence.
  const latest = snapshotResearchCandidateV2(candidate);

  if (pinned.researchProjectId.toLowerCase() !== latest.researchProjectId.toLowerCase() ||
    pinned.clipId.toLowerCase() !== latest.clipId.toLowerCase()) {
    return { kind: "inconsistent", reason: "identity" };
  }
  if (latest.clipVersion < pinned.clipVersion) {
    return { kind: "inconsistent", reason: "older_version" };
  }

  const changedFields = frozenFields.filter((field) =>
    !sameAuthoringJsonV2(pinned[field], latest[field]));
  if (latest.clipVersion === pinned.clipVersion) {
    return changedFields.length > 0
      ? { kind: "inconsistent", reason: "same_version_changed" }
      : { kind: "current", pinned: structuredClone(pinned) };
  }
  return {
    kind: "update_available",
    pinned: structuredClone(pinned),
    latest,
    changedFields,
  };
}
