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

function compareEntities<T extends { id: string }>(
  surface: "draft_block" | "supporting_item", before: readonly T[], after: readonly T[],
): SemanticChange[] {
  const left = byId(before);
  const right = byId(after);
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
      if (fields.length) result.push({ surface, entityId: id,
        kind: fields.length === 1 && fields[0] === "orderKey" ? "reordered" : "modified", fields });
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
      stashOutline: before.stashOutline, stashGroups: before.stashGroups,
      rowTransitions: before.rowTransitions, rowAudioSpans: before.rowAudioSpans,
      rowReferences: before.rowReferences,
    },
    {
      title: after.title, scriptSettings: after.scriptSettings,
      stash: after.stash, stashSections: after.stashSections,
      stashOutline: after.stashOutline, stashGroups: after.stashGroups,
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
