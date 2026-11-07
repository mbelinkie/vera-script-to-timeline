import type { RowStashBundleV2, ScriptDocumentV2, StashRowGroupV2 } from "./generated/contracts-v2.js";

export type StashGroupMemberV2 = RowStashBundleV2["rows"][number];

/** Private, unsaved editor state: all member payloads are detached from the document. */
export interface StashGroupMemberStageV2 {
  groupId: string;
  expectedRevision: number;
  expectedRowIds: string[];
  members: StashGroupMemberV2[];
}

/** A complete, replayable single-transaction Save (not a series of row edits). */
export interface SaveStashGroupCommandV2 {
  kind: "save_stash_group";
  groupId: string;
  expectedRevision: number;
  expectedRowIds: string[];
  members: StashGroupMemberV2[];
}

export function beginStashGroupMemberStageV2(document: ScriptDocumentV2, groupId: string): StashGroupMemberStageV2 | null {
  const group = document.stashGroups?.find((candidate) => candidate.id === groupId);
  if (!group || stashGroupLocationProblemV2(document, group)) return null;
  const rows = new Map((document.stash ?? []).flatMap((bundle) => bundle.rows.map((row) => [row.id, row] as const)));
  return {
    groupId,
    expectedRevision: document.rowEditRevision ?? 0,
    expectedRowIds: [...group.rowIds],
    members: group.rowIds.map((id) => structuredClone(rows.get(id)!)),
  };
}

/** Editing, adding, removing and reordering happen only in the detached stage. */
export function stageStashGroupMembersV2(stage: StashGroupMemberStageV2, members: StashGroupMemberV2[]): StashGroupMemberStageV2 {
  return { ...structuredClone(stage), members: structuredClone(members) };
}

/** Cancel is intentionally not a document command, so it creates no revision or Undo. */
export function cancelStashGroupMemberStageV2(stage: StashGroupMemberStageV2): null {
  void stage;
  return null;
}

export function saveStashGroupStageCommandV2(stage: StashGroupMemberStageV2): SaveStashGroupCommandV2 {
  return { kind: "save_stash_group", groupId: stage.groupId,
    expectedRevision: stage.expectedRevision, expectedRowIds: [...stage.expectedRowIds], members: structuredClone(stage.members) };
}

/** Check one group's flat, ordered range against the *canonical* saved-row outline. */
export function stashGroupLocationProblemV2(
  document: ScriptDocumentV2,
  group: StashRowGroupV2,
): string | null {
  const outline = document.stashOutline;
  if (!outline) return "Saved groups require the canonical Stash outline.";
  if (group.rowIds.length < 2 || new Set(group.rowIds).size !== group.rowIds.length) {
    return "A saved group requires at least two distinct row IDs.";
  }

  const saved = new Map((document.stash ?? []).flatMap((bundle) =>
    bundle.rows.map((row) => [row.id, row] as const)));
  const positions = new Map(outline.map((entry, index) => [entry.rowId, index] as const));
  const indices = group.rowIds.map((id) => positions.get(id));
  if (indices.some((index, n) => index === undefined || !saved.has(group.rowIds[n]!))) {
    return "Every group member must be a saved row in the canonical Stash outline.";
  }

  const firstIndex = indices[0]!;
  const first = outline[firstIndex]!;
  if (indices.some((index, n) => index !== firstIndex + n)) {
    return "Group members must be consecutive in canonical Stash order.";
  }
  if (indices.some((index) => {
    const entry = outline[index!]!;
    return entry.kind !== "row" || entry.parentRowId !== first.parentRowId ||
      entry.sectionId !== first.sectionId;
  })) {
    return "Group members must be ordinary sibling rows in the same Stash section.";
  }
  if (group.rowIds.some((id) => {
    const origin = saved.get(id)?.stashOrigin;
    return origin?.returnEligible === true && origin.kind !== "row";
  })) {
    return "A grouped row cannot retain compact note or clip return eligibility.";
  }
  return null;
}

/** No row may be claimed by multiple persisted groups. Does not mutate its input. */
export function stashGroupMembershipProblemV2(document: ScriptDocumentV2): string | null {
  const claimed = new Set<string>();
  for (const group of document.stashGroups ?? []) {
    const problem = stashGroupLocationProblemV2(document, group);
    if (problem) return problem;
    for (const rowId of group.rowIds) {
      if (claimed.has(rowId)) return "A saved row cannot belong to multiple Stash groups.";
      claimed.add(rowId);
    }
  }
  return null;
}
