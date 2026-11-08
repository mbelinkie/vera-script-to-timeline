import type {
  StashOriginV2,
  StashOutlineEntryV2,
  StashParentOriginContextV2,
} from "./generated/contracts-v2.js";

export type ReturnParentV2 =
  | { kind: "root" }
  | { kind: "note"; rowId: string }
  | { kind: "invalid" };

export type ReturnSlotV2 =
  | { kind: "after" | "before"; siblingRowId: string; parentRowId: string | null; sectionId: string | null }
  | { kind: "first_child"; parentRowId: string; sectionId: string | null }
  | { kind: "section_start"; parentRowId: null; sectionId: string | null }
  | { kind: "unsectioned_top"; parentRowId: null; sectionId: null };

export interface FrozenSiblingCandidatesV2 {
  precedingSiblingRowIds: string[];
  followingSiblingRowIds: string[];
}

/** Capture the original siblings in distance order before removing an outline entry. */
export function freezeOriginalSiblingCandidatesV2(
  entries: readonly StashOutlineEntryV2[],
  rowId: string,
): FrozenSiblingCandidatesV2 | null {
  const target = entries.find((entry) => entry.rowId === rowId);
  if (!target) return null;
  const peers = entries.filter((entry) =>
    entry.parentRowId === target.parentRowId && entry.sectionId === target.sectionId);
  const index = peers.findIndex((entry) => entry.rowId === rowId);
  if (index === -1) return null;
  return {
    precedingSiblingRowIds: peers.slice(0, index).reverse().map((entry) => entry.rowId),
    followingSiblingRowIds: peers.slice(index + 1).map((entry) => entry.rowId),
  };
}

/** The parent of this row is a note; freeze *its* location at the same time. */
export function freezeOriginalParentContextV2(
  entries: readonly StashOutlineEntryV2[],
  rowId: string,
): StashParentOriginContextV2 | null {
  const row = entries.find((entry) => entry.rowId === rowId);
  if (!row?.parentRowId) return null;
  const parent = entries.find((entry) => entry.rowId === row.parentRowId);
  if (!parent || parent.kind !== "note" || parent.sectionId !== row.sectionId) return null;
  const siblings = freezeOriginalSiblingCandidatesV2(entries, parent.rowId);
  if (!siblings) return null;
  return { parentRowId: parent.parentRowId, sectionId: parent.sectionId, ...siblings };
}

/**
 * Reject a reparented, resectioned or demonstrably reordered original note.
 * Newly inserted peers are not historical evidence, and do not invalidate it.
 */
export function originalParentUnmovedV2(
  entries: readonly StashOutlineEntryV2[],
  parentRowId: string,
  original: StashParentOriginContextV2,
): boolean {
  const parent = entries.find((entry) => entry.rowId === parentRowId);
  if (!parent || parent.kind !== "note" ||
      parent.parentRowId !== original.parentRowId || parent.sectionId !== original.sectionId) return false;

  const peers = entries.filter((entry) =>
    entry.parentRowId === original.parentRowId && entry.sectionId === original.sectionId);
  const at = peers.findIndex((entry) => entry.rowId === parentRowId);
  if (at < 0) return false;
  const indexByRowId = new Map(peers.map((entry, index) => [entry.rowId, index]));
  const historicalBefore = new Set(original.precedingSiblingRowIds);
  if (historicalBefore.has(parentRowId)) return false;
  if (original.followingSiblingRowIds.some((id) => id === parentRowId || historicalBefore.has(id))) return false;
  return original.precedingSiblingRowIds.every((id) =>
    !indexByRowId.has(id) || indexByRowId.get(id)! < at) &&
    original.followingSiblingRowIds.every((id) =>
      !indexByRowId.has(id) || indexByRowId.get(id)! > at);
}

/**
 * Resolve an original Stash address without moving data. The caller must
 * validate the document and perform insertion of the entire return batch.
 * `root` with promoted history is for an original parent still active in Draft.
 */
export function chooseReturnSlotV2(input: {
  origin: StashOriginV2 | undefined;
  entries: readonly StashOutlineEntryV2[];
  sectionIds: ReadonlySet<string>;
  parent: ReturnParentV2;
  promotedRootPreceding?: readonly string[];
  promotedRootFollowing?: readonly string[];
}): ReturnSlotV2 {
  const top: ReturnSlotV2 = { kind: "unsectioned_top", parentRowId: null, sectionId: null };
  const { origin, entries, parent } = input;
  if (!origin || parent.kind === "invalid" ||
      (origin.sectionId !== null && !input.sectionIds.has(origin.sectionId))) return top;

  if (parent.kind === "note" && (
    origin.parentRowId !== parent.rowId ||
    !origin.originalParentContext ||
    origin.originalParentContext.sectionId !== origin.sectionId ||
    !originalParentUnmovedV2(entries, parent.rowId, origin.originalParentContext)
  )) return top;
  if (parent.kind === "root" && origin.parentRowId !== null &&
      input.promotedRootPreceding === undefined && input.promotedRootFollowing === undefined) return top;

  const parentRowId = parent.kind === "note" ? parent.rowId : null;
  const peers = entries.filter((entry) =>
    entry.parentRowId === parentRowId && entry.sectionId === origin.sectionId);
  const peerIds = new Set(peers.map((entry) => entry.rowId));
  const promoted = parent.kind === "root" && origin.parentRowId !== null;
  // A promoted root must never read the child's historical nested peers.
  const preceding = promoted ? input.promotedRootPreceding ?? [] : origin.precedingSiblingRowIds ??
    (origin.afterSiblingRowId === null ? [] : [origin.afterSiblingRowId]);
  const following = promoted ? input.promotedRootFollowing ?? [] : origin.followingSiblingRowIds ??
    (origin.beforeSiblingRowId === null ? [] : [origin.beforeSiblingRowId]);
  const after = preceding.find((id) => peerIds.has(id));
  if (after !== undefined) return {
    kind: "after", siblingRowId: after, parentRowId, sectionId: origin.sectionId,
  };
  const before = following.find((id) => peerIds.has(id));
  if (before !== undefined) return {
    kind: "before", siblingRowId: before, parentRowId, sectionId: origin.sectionId,
  };
  if (parentRowId !== null) return {
    kind: "first_child", parentRowId, sectionId: origin.sectionId,
  };
  return { kind: "section_start", parentRowId: null, sectionId: origin.sectionId };
}
