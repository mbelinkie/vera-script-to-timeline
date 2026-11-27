import type { ScriptDocumentV2 } from "@vera/contracts/v2";

import { fingerprint, ProjectDocumentInputError } from "./model.js";

/** Semantic document facts, not a CRDT operation log or an arbitrary JSON patch. */
export type SemanticSurface = "document" | "draft_block" | "supporting_item";
export type SemanticKind = "added" | "removed" | "modified" | "reordered";
export interface SemanticChange {
  readonly surface: SemanticSurface;
  readonly entityId: string;
  readonly kind: SemanticKind;
  readonly fields: readonly string[];
}

const byCodeUnit = (a: string, b: string): number => a < b ? -1 : a > b ? 1 : 0;
const equal = (a: unknown, b: unknown): boolean =>
  fingerprint({ value: a }) === fingerprint({ value: b });

function changedFields(before: Record<string, unknown>, after: Record<string, unknown>): string[] {
  return [...new Set([...Object.keys(before), ...Object.keys(after)])]
    .sort(byCodeUnit).filter((field) => !equal(before[field], after[field]));
}

function byId<T extends { id: string }>(items: readonly T[]): Map<string, T> {
  const indexed = new Map<string, T>();
  for (const item of items) {
    if (indexed.has(item.id)) throw new ProjectDocumentInputError("Duplicate semantic identity.");
    indexed.set(item.id, item);
  }
  return indexed;
}

/** Mark both endpoints of each relative-order inversion, not shifted absolute indices.
 * Snapshots cannot tell which of two inverted blocks the editor actually moved.
 */
function relativeOrderChanges<T extends { id: string }>(
  before: readonly T[], after: readonly T[],
): Set<string> {
  const positions = new Map(before.map((item, index) => [item.id, index]));
  const retained = after.flatMap(({ id }) => {
    const index = positions.get(id);
    return index === undefined ? [] : [{ id, index }];
  });
  const reordered = new Set<string>();
  let highest = -1;
  for (const { id, index } of retained) {
    if (index < highest) reordered.add(id);
    highest = Math.max(highest, index);
  }
  let lowest = before.length;
  for (let i = retained.length - 1; i >= 0; i--) {
    const { id, index } = retained[i]!;
    if (index > lowest) reordered.add(id);
    lowest = Math.min(lowest, index);
  }
  return reordered;
}

function compareEntities<T extends { id: string }>(
  surface: "draft_block" | "supporting_item", before: readonly T[], after: readonly T[],
): SemanticChange[] {
  const left = byId(before);
  const right = byId(after);
  const reordered = surface === "draft_block" ? relativeOrderChanges(before, after) : new Set<string>();
  const result: SemanticChange[] = [];
  for (const id of [...new Set([...left.keys(), ...right.keys()])].sort(byCodeUnit)) {
    const old = left.get(id);
    const next = right.get(id);
    if (!old) {
      result.push({ surface, entityId: id, kind: "added", fields: [] });
    } else if (!next) {
      result.push({ surface, entityId: id, kind: "removed", fields: [] });
    } else {
      const fields = changedFields(old, next);
      // "order" describes the Draft sequence; "orderKey" remains an actual stored field.
      if (reordered.has(id)) fields.push("order");
      fields.sort(byCodeUnit);
      if (fields.length) result.push({ surface, entityId: id,
        kind: fields.every((field) => field === "orderKey" || field === "order")
          ? "reordered" : "modified", fields });
    }
  }
  return result;
}

/** Stable surface-then-ID ordering, including typed nested visual/anchor field names. */
export function compareDocuments(before: ScriptDocumentV2, after: ScriptDocumentV2): SemanticChange[] {
  if (before.id !== after.id || before.projectId !== after.projectId) {
    throw new ProjectDocumentInputError("Cannot compare different documents.");
  }
  const documentFields = changedFields(
    {
      title: before.title, scriptSettings: before.scriptSettings,
      stash: before.stash, stashSections: before.stashSections,
      stashOutline: before.stashOutline, stashGroups: before.stashGroups, stashResearchItems: before.stashResearchItems,
      rowTransitions: before.rowTransitions, rowAudioSpans: before.rowAudioSpans,
      rowReferences: before.rowReferences,
    },
    {
      title: after.title, scriptSettings: after.scriptSettings,
      stash: after.stash, stashSections: after.stashSections,
      stashOutline: after.stashOutline, stashGroups: after.stashGroups, stashResearchItems: after.stashResearchItems,
      rowTransitions: after.rowTransitions, rowAudioSpans: after.rowAudioSpans,
      rowReferences: after.rowReferences,
    },
  );
  return [
    ...(documentFields.length ? [{ surface: "document" as const, entityId: before.id,
      kind: "modified" as const, fields: documentFields }] : []),
    ...compareEntities("draft_block", before.activeDraft.blocks, after.activeDraft.blocks),
    ...compareEntities("supporting_item",
      before.activeDraft.supportingItems, after.activeDraft.supportingItems),
  ];
}
