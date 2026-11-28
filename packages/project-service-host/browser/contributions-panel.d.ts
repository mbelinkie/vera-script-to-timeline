import type { ProjectRole } from "@vera/project-authorization";

export type ContributionRange = "rev" | "visit" | "d1" | "d7" | "all" | "custom";
export interface ContributionReference {
  sourceCursor: unknown;
  actorId: string | null;
  occurredAt: string;
  origin: "user" | "system" | "unknown";
  targetKind: string;
  semanticId: string;
  changeKind: string;
  evidence: unknown;
  /** Adapter-projected comparison-only removal, not inferred from text. */
  removed?: boolean;
  label?: string;
}
export interface ContributionSummary { actorId: string | null; text: string }
export interface ContributionsProjection {
  selfActorId: string;
  boundaryToken: string | null;
  pendingCount: number;
  rangeCount: number;
  coverage: "complete" | "partial" | "unavailable";
  contributors: readonly { actorId: string; displayName: string; count: number }[];
  visibleReferences: readonly ContributionReference[];
  removedSummaries: readonly ContributionSummary[];
  overwrittenSummaries: readonly ContributionSummary[];
}
export interface ContributionFilter {
  range: ContributionRange;
  actorId: string | null;
  showRemoved: boolean;
  from: string | null;
  to: string | null;
  valid: boolean;
  active: boolean;
  boundaryToken: string | null;
}
interface Context {
  projection: ContributionsProjection;
  role: ProjectRole;
  autoOpen?: boolean;
  sorting?: boolean;
}
export function mountContributionsPanel(options: Context & {
  root: HTMLElement;
  setFilter(filter: ContributionFilter): void | ContributionsProjection | Promise<void | ContributionsProjection>;
  /** On success, return or publish the authoritative refreshed projection. */
  acknowledge(boundaryToken: string): Promise<void | ContributionsProjection>;
  focusTarget(reference: ContributionReference): void;
}): { update(context: Partial<Context>): void; destroy(): void };
