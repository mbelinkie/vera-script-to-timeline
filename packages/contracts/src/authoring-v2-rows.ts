import type { ScriptDocumentV2, RowGapV2, SupportingItemV2, StashOutlineEntryV2, StashOriginV2, NarrationBlockV2, VisualOnlyBlockV2 } from "./generated/contracts-v2.js";
import type { AuthoringDiagnosticV2 } from "./authoring-v2.js";
import { validateScriptDocumentV2 } from "./authoring-v2-validation.js";
import { defaultDirectionNarrationRowV2 } from "./authoring-v2-stage-direction-edits.js";

type Block = ScriptDocumentV2["activeDraft"]["blocks"][number];
type Row = Exclude<Block, { type: "section" }>;
export type { RowGapV2 } from "./generated/contracts-v2.js";

export type RowEditCommandV2 =
  | { kind: "move_rows"; rowIds: string[]; destination: RowGapV2 }
  | { kind: "move_section"; sectionId: string; destination: { afterSectionId: string | null; beforeSectionId: string | null } }
  | { kind: "stash_rows"; rowIds: string[]; bundleId: string }
  | { kind: "restore_stash"; bundleId: string; destination: RowGapV2 }
  | { kind: "restore_stash_rows"; rowIds: string[]; destination: RowGapV2 }
  | { kind: "create_stash_section"; sectionId: string; title: string }
  | { kind: "move_stash_rows"; rowIds: string[]; sectionId: string | null }
  | { kind: "create_stash_note"; bundleId: string; row: NarrationBlockV2; sectionId: string | null; parentRowId: string | null; afterRowId: string | null; mode?: "default_direction" | "authored" }
  | { kind: "create_stash_clip"; bundleId: string; row: VisualOnlyBlockV2; sectionId: string | null; parentRowId: string | null; afterRowId: string | null }
  | { kind: "set_stash_outline"; entries: StashOutlineEntryV2[] }
  | { kind: "place_stash_rows"; rowIds: string[]; destination: RowGapV2 };

export interface RowEditResultV2 {
  ok: boolean;
  document: ScriptDocumentV2;
  diagnostics: AuthoringDiagnosticV2[];
}

interface Section { id: string | null; start: number; end: number; rows: Row[] }
function sections(blocks: Block[]): Section[] {
  const result: Section[] = [{ id: null, start: 0, end: 0, rows: [] }];
  blocks.forEach((block, index) => {
    if (block.type === "section") {
      result[result.length - 1]!.end = index;
      result.push({ id: block.id, start: index + 1, end: blocks.length, rows: [] });
    } else result[result.length - 1]!.rows.push(block);
  });
  result[result.length - 1]!.end = blocks.length;
  return result;
}

const diagnostic = (code: string, message: string): AuthoringDiagnosticV2 => ({ code, message, jsonPath: "/activeDraft" });
const refused = (document: ScriptDocumentV2, code: string, message: string): RowEditResultV2 => ({ ok: false, document, diagnostics: [diagnostic(code, message)] });

/** Range selection clamps to the anchor's section, in document order. */
export function selectRowRangeV2(document: ScriptDocumentV2, anchorRowId: string, focusRowId: string): { rowIds: string[]; boundaryReached: boolean; diagnostics: AuthoringDiagnosticV2[] } {
  const blocks = document.activeDraft.blocks;
  const section = sections(blocks).find((part) => part.rows.some((row) => row.id === anchorRowId));
  const focusIndex = blocks.findIndex((block) => block.id === focusRowId && block.type !== "section");
  if (!section || focusIndex < 0) return { rowIds: [], boundaryReached: false, diagnostics: [diagnostic("ROW_SELECTION_INVALID", "Select existing rows, rather than section headings.")] };
  const anchor = blocks.findIndex((block) => block.id === anchorRowId);
  const focus = Math.max(section.start, Math.min(section.end - 1, focusIndex));
  return { rowIds: blocks.slice(Math.min(anchor, focus), Math.max(anchor, focus) + 1).map((row) => row.id), boundaryReached: focus !== focusIndex, diagnostics: [] };
}

function selectedRows(blocks: Block[], ids: string[]): Row[] | null {
  if (!Array.isArray(ids) || ids.length === 0 || new Set(ids).size !== ids.length) return null;
  const section = sections(blocks).find((part) => part.rows.some((row) => row.id === ids[0]));
  const index = section?.rows.findIndex((row) => row.id === ids[0]) ?? -1;
  const rows = section?.rows.slice(index, index + ids.length);
  return rows?.length === ids.length && rows.every((row, i) => row.id === ids[i]) ? rows : null;
}

function gapIndex(blocks: Block[], gap: RowGapV2): number | null {
  if (!gap) return null;
  const section = sections(blocks).find((part) => part.id === gap.sectionId);
  if (!section) return null;
  for (let index = 0; index <= section.rows.length; index++) {
    if ((section.rows[index - 1]?.id ?? null) === gap.afterRowId && (section.rows[index]?.id ?? null) === gap.beforeRowId) return section.start + index;
  }
  return null;
}

/** Resolve only supported anchor fields, never quoted text or proximity. */
function supportingRows(item: SupportingItemV2, blocks: Block[]): Set<string> {
  const result = new Set<string>();
  const visit = (value: unknown): void => {
    if (!value || typeof value !== "object") return;
    for (const [key, child] of Object.entries(value)) {
      if (["blockId", "beforeBlockId", "afterBlockId"].includes(key) && typeof child === "string") result.add(child);
      else if (key === "eventId" && typeof child === "string") {
        const owner = blocks.find((block) => block.type === "narration" && block.overlayEvents.some((event) => event.id === child));
        if (owner) result.add(owner.id);
        else result.add(child); // Unknown anchors cannot be silently carried as row-local.
      } else visit(child);
    }
  };
  visit(item.placement);
  visit(item.displayAttachment);
  return result;
}

function locations(document: ScriptDocumentV2): Section[] {
  return [...sections(document.activeDraft.blocks), ...(document.stash ?? []).map((bundle) => ({ id: bundle.id, start: 0, end: bundle.rows.length, rows: bundle.rows }))];
}

function stashRowsInVisibleOrder(document: ScriptDocumentV2): Row[] {
  const rows = (document.stash ?? []).flatMap((bundle) => bundle.rows);
  const byId = new Map(rows.map((row) => [row.id, row]));
  if (document.stashOutline) return document.stashOutline.flatMap((entry) => {
    const row = byId.get(entry.rowId);
    return row ? [row] : [];
  });
  const sectioned = new Set((document.stashSections ?? []).flatMap((section) => section.rowIds));
  return [
    ...rows.filter((row) => !sectioned.has(row.id)),
    ...(document.stashSections ?? []).flatMap((section) => section.rowIds.flatMap((id) => {
      const row = byId.get(id);
      return row ? [row] : [];
    })),
  ];
}

/** Upgrade legacy row/section order only when a command first writes the mixed outline. */
function ensureStashOutline(document: ScriptDocumentV2): StashOutlineEntryV2[] {
  if (document.stashOutline) return document.stashOutline;
  const sectionForRow = new Map((document.stashSections ?? []).flatMap((section) => section.rowIds.map((rowId) => [rowId, section.id] as const)));
  document.stashOutline = stashRowsInVisibleOrder(document).map((row) => ({
    rowId: row.id,
    kind: "row",
    parentRowId: null,
    sectionId: sectionForRow.get(row.id) ?? null,
  }));
  if (document.stashSections) document.stashSections = document.stashSections.map((section) => ({ ...section, rowIds: [] }));
  return document.stashOutline;
}

function outlineMap(entries: StashOutlineEntryV2[]): Map<string, StashOutlineEntryV2> {
  return new Map(entries.map((entry) => [entry.rowId, entry]));
}

function isOutlineDescendant(entry: StashOutlineEntryV2, ancestorRowId: string, byId: Map<string, StashOutlineEntryV2>): boolean {
  let parentRowId = entry.parentRowId;
  while (parentRowId !== null) {
    if (parentRowId === ancestorRowId) return true;
    parentRowId = byId.get(parentRowId)?.parentRowId ?? null;
  }
  return false;
}

function outlineSubtreeEnd(entries: StashOutlineEntryV2[], rootRowId: string): number {
  const byId = outlineMap(entries);
  let end = entries.findIndex((entry) => entry.rowId === rootRowId);
  for (let index = end + 1; index < entries.length; index += 1) {
    if (isOutlineDescendant(entries[index]!, rootRowId, byId)) end = index;
  }
  return end;
}

function outlineInsertionIndex(
  document: ScriptDocumentV2,
  entries: StashOutlineEntryV2[],
  parentRowId: string | null,
  sectionId: string | null,
  afterRowId: string | null,
): number | null {
  const siblings = entries.filter((entry) => entry.parentRowId === parentRowId && entry.sectionId === sectionId);
  if (afterRowId !== null) {
    if (!siblings.some((entry) => entry.rowId === afterRowId)) return null;
    return outlineSubtreeEnd(entries, afterRowId) + 1;
  }
  const lastSibling = siblings.at(-1);
  if (lastSibling) return outlineSubtreeEnd(entries, lastSibling.rowId) + 1;
  if (parentRowId !== null) {
    const parentIndex = entries.findIndex((entry) => entry.rowId === parentRowId);
    return parentIndex < 0 ? null : parentIndex + 1;
  }
  const sectionOrder = (id: string | null) => id === null ? -1 : (document.stashSections ?? []).findIndex((section) => section.id === id);
  const targetOrder = sectionOrder(sectionId);
  const nextSection = entries.findIndex((entry) => entry.parentRowId === null && sectionOrder(entry.sectionId) > targetOrder);
  return nextSection < 0 ? entries.length : nextSection;
}

function stashRowById(document: ScriptDocumentV2, rowId: string): Row | undefined {
  return document.stash?.flatMap((bundle) => bundle.rows).find((row) => row.id === rowId);
}

function sectionExists(document: ScriptDocumentV2, sectionId: string | null): boolean {
  return sectionId === null || (document.stashSections ?? []).some((section) => section.id === sectionId);
}

function outlineSiblingAnchors(entries: StashOutlineEntryV2[], rowId: string): { afterSiblingRowId: string | null; beforeSiblingRowId: string | null } | null {
  const entry = entries.find((item) => item.rowId === rowId);
  if (!entry) return null;
  const siblings = entries.filter((item) => item.parentRowId === entry.parentRowId && item.sectionId === entry.sectionId);
  const index = siblings.findIndex((item) => item.rowId === rowId);
  return {
    afterSiblingRowId: siblings[index - 1]?.rowId ?? null,
    beforeSiblingRowId: siblings[index + 1]?.rowId ?? null,
  };
}

function selectedOutlineSubtree(entries: StashOutlineEntryV2[], roots: string[]): StashOutlineEntryV2[] | null {
  if (!Array.isArray(roots) || roots.length === 0 || roots.some((rowId) => typeof rowId !== "string") || new Set(roots).size !== roots.length) return null;
  const byId = outlineMap(entries);
  if (roots.some((rowId) => !byId.has(rowId))) return null;
  const rootSet = new Set(roots);
  if (roots.some((rowId) => {
    let parentRowId = byId.get(rowId)!.parentRowId;
    while (parentRowId !== null) {
      if (rootSet.has(parentRowId)) return true;
      parentRowId = byId.get(parentRowId)?.parentRowId ?? null;
    }
    return false;
  })) return null;
  return entries.filter((entry) => rootSet.has(entry.rowId) || roots.some((rootRowId) => isOutlineDescendant(entry, rootRowId, byId)));
}

interface StashReturnPlan {
  entry: StashOutlineEntryV2;
  afterSiblingRowId: string | null;
  beforeSiblingRowId: string | null;
  appendToSection: boolean;
  activeOrder: number;
}

function orderReturningSiblings(entries: StashOutlineEntryV2[], plans: StashReturnPlan[]): string[] | null {
  if (plans.length === 0) return [];
  const parentRowId = plans[0]!.entry.parentRowId;
  const sectionId = plans[0]!.entry.sectionId;
  if (plans.some((plan) => plan.entry.parentRowId !== parentRowId || plan.entry.sectionId !== sectionId)) return null;
  const current = entries.filter((entry) => entry.parentRowId === parentRowId && entry.sectionId === sectionId);
  const ids = [...current.map((entry) => entry.rowId), ...plans.map((plan) => plan.entry.rowId)];
  const nodeIds = new Set(ids);
  if (nodeIds.size !== ids.length) return null;
  const outgoing = new Map(ids.map((id) => [id, new Set<string>()]));
  const incoming = new Map(ids.map((id) => [id, 0]));
  const addEdge = (before: string, after: string): void => {
    if (before === after || !nodeIds.has(before) || !nodeIds.has(after)) return;
    const edges = outgoing.get(before)!;
    if (edges.has(after)) return;
    edges.add(after);
    incoming.set(after, incoming.get(after)! + 1);
  };
  for (let index = 1; index < current.length; index += 1) addEdge(current[index - 1]!.rowId, current[index]!.rowId);

  for (const plan of plans) {
    const { afterSiblingRowId: after, beforeSiblingRowId: before } = plan;
    if (after === plan.entry.rowId || before === plan.entry.rowId) return null;
    const hasAfter = after !== null && nodeIds.has(after);
    const hasBefore = before !== null && nodeIds.has(before);
    const historicalAnchors = Number(after !== null) + Number(before !== null);
    if (historicalAnchors > 0 && !hasAfter && !hasBefore && !plan.appendToSection) return null;
    if (hasAfter) addEdge(after, plan.entry.rowId);
    if (hasBefore) addEdge(plan.entry.rowId, before);

    if (hasAfter && hasBefore && current.some((entry) => entry.rowId === after) && current.some((entry) => entry.rowId === before)) {
      const afterIndex = current.findIndex((entry) => entry.rowId === after);
      const beforeIndex = current.findIndex((entry) => entry.rowId === before);
      if (beforeIndex !== afterIndex + 1) return null;
    }
    if (!plan.appendToSection && Number(hasAfter) + Number(hasBefore) === 1) {
      if (hasAfter && current.some((entry) => entry.rowId === after) && !hasBefore) {
        const index = current.findIndex((entry) => entry.rowId === after);
        const next = current[index + 1];
        if (next) addEdge(plan.entry.rowId, next.rowId);
      } else if (hasBefore && current.some((entry) => entry.rowId === before) && !hasAfter) {
        const index = current.findIndex((entry) => entry.rowId === before);
        const previous = current[index - 1];
        if (previous) addEdge(previous.rowId, plan.entry.rowId);
      }
    }
  }

  const appended = plans.filter((plan) => plan.appendToSection).sort((left, right) => left.activeOrder - right.activeOrder);
  if (appended.length > 0) {
    if (current.length > 0) for (const plan of appended) addEdge(current.at(-1)!.rowId, plan.entry.rowId);
    for (let index = 1; index < appended.length; index += 1) addEdge(appended[index - 1]!.entry.rowId, appended[index]!.entry.rowId);
  }

  const remaining = new Set(ids);
  const order: string[] = [];
  while (remaining.size > 0) {
    const ready = [...remaining].filter((id) => incoming.get(id) === 0);
    if (ready.length !== 1) return null;
    const next = ready[0]!;
    order.push(next);
    remaining.delete(next);
    for (const child of outgoing.get(next)!) incoming.set(child, incoming.get(child)! - 1);
  }
  for (const plan of plans) {
    if (plan.appendToSection) continue;
    const index = order.indexOf(plan.entry.rowId);
    const hasAfter = plan.afterSiblingRowId !== null && nodeIds.has(plan.afterSiblingRowId);
    const hasBefore = plan.beforeSiblingRowId !== null && nodeIds.has(plan.beforeSiblingRowId);
    if (hasAfter && order[index - 1] !== plan.afterSiblingRowId) return null;
    if (hasBefore && order[index + 1] !== plan.beforeSiblingRowId) return null;
  }
  return order;
}

function insertReturningSiblingGroup(document: ScriptDocumentV2, entries: StashOutlineEntryV2[], plans: StashReturnPlan[]): boolean {
  const order = orderReturningSiblings(entries, plans);
  if (!order) return false;
  const planById = new Map(plans.map((plan) => [plan.entry.rowId, plan]));
  for (let index = 0; index < order.length; index += 1) {
    const plan = planById.get(order[index]!);
    if (!plan) continue;
    const isSibling = (entry: StashOutlineEntryV2): boolean => entry.parentRowId === plan.entry.parentRowId && entry.sectionId === plan.entry.sectionId;
    const previous = order.slice(0, index).reverse().find((rowId) => entries.some((entry) => entry.rowId === rowId && isSibling(entry)));
    const next = order.slice(index + 1).find((rowId) => entries.some((entry) => entry.rowId === rowId && isSibling(entry)));
    const parentIndex = plan.entry.parentRowId === null ? -1 : entries.findIndex((entry) => entry.rowId === plan.entry.parentRowId);
    const insertAt = previous
      ? outlineSubtreeEnd(entries, previous) + 1
      : next
        ? entries.findIndex((entry) => entry.rowId === next)
        : parentIndex >= 0
          ? outlineSubtreeEnd(entries, plan.entry.parentRowId!) + 1
          : outlineInsertionIndex(document, entries, null, plan.entry.sectionId, null) ?? -1;
    if (insertAt < 0) return false;
    entries.splice(insertAt, 0, plan.entry);
  }
  return true;
}

function planStashReturn(document: ScriptDocumentV2, rows: Row[], entries: StashOutlineEntryV2[]): StashOutlineEntryV2[] | null {
  const selected = new Set(rows.map((row) => row.id));
  const result = structuredClone(entries);
  const originalParents = outlineMap(entries);
  const resultingKinds = new Map(rows.map((row) => [row.id, row.stashOrigin?.returnEligible && row.stashOrigin.kind !== "row" ? row.stashOrigin.kind : "row"] as const));
  const pending: StashReturnPlan[] = [];
  for (const [activeOrder, row] of rows.entries()) {
    const origin: StashOriginV2 | undefined = row.stashOrigin;
    const kind = origin?.returnEligible && origin.kind !== "row" ? origin.kind : "row";
    let parentRowId = origin?.parentRowId ?? null;
    const afterSiblingRowId = origin?.afterSiblingRowId ?? null;
    const beforeSiblingRowId = origin?.beforeSiblingRowId ?? null;
    let appendToSection = origin === undefined;
    if (parentRowId !== null) {
      if (selected.has(parentRowId)) {
        if (resultingKinds.get(parentRowId) !== "note") return null;
      } else if (document.activeDraft.blocks.some((block) => block.id === parentRowId && block.type !== "section")) {
        const activeParent = document.activeDraft.blocks.find((block) => block.id === parentRowId);
        parentRowId = null;
        appendToSection = !entries.some((entry) => entry.parentRowId === null && entry.sectionId === (origin?.sectionId ?? null));
        if (activeParent?.type !== "section" && activeParent?.stashOrigin) {
          const parentOrigin = activeParent.stashOrigin;
          if (parentOrigin.afterSiblingRowId === null && parentOrigin.beforeSiblingRowId === null) {
            parentOrigin.beforeSiblingRowId = row.id;
          } else if (parentOrigin.beforeSiblingRowId !== null && origin?.beforeSiblingRowId === parentOrigin.beforeSiblingRowId) {
            parentOrigin.beforeSiblingRowId = row.id;
          }
        }
      } else {
        const parent = originalParents.get(parentRowId);
        if (!parent || parent.kind !== "note") return null;
      }
    }
    const sectionId = origin?.sectionId ?? null;
    if (!sectionExists(document, sectionId)) return null;
    const selectedParent = selected.has(origin?.parentRowId ?? "") ? rows.find((candidate) => candidate.id === origin!.parentRowId) : undefined;
    if (selectedParent?.stashOrigin && selectedParent.stashOrigin.sectionId !== sectionId) return null;
    const existingParent = parentRowId === null ? undefined : originalParents.get(parentRowId);
    if (existingParent && existingParent.sectionId !== sectionId) return null;
    pending.push({
      entry: { rowId: row.id, kind, parentRowId, sectionId },
      afterSiblingRowId,
      beforeSiblingRowId,
      appendToSection,
      activeOrder,
    });
  }

  while (pending.length > 0) {
    const ready = pending.find((plan) => plan.entry.parentRowId === null || result.some((entry) => entry.rowId === plan.entry.parentRowId));
    if (!ready) return null;
    const groupPlans = pending.filter((plan) => plan.entry.parentRowId === ready.entry.parentRowId && plan.entry.sectionId === ready.entry.sectionId);
    if (!insertReturningSiblingGroup(document, result, groupPlans)) return null;
    for (const plan of groupPlans) pending.splice(pending.indexOf(plan), 1);
  }
  return result;
}

function takeStashRows(document: ScriptDocumentV2, selected: Set<string>, visibleOrder: string[]): { rows: Row[] } | AuthoringDiagnosticV2 {
  const moved = visibleOrder.filter((rowId) => selected.has(rowId)).map((rowId) => stashRowById(document, rowId)).filter((row): row is Row => row !== undefined);
  if (moved.length !== selected.size) return diagnostic("ROW_SELECTION_INVALID", "Every selected row must still be in Stash.");
  const restoredItems: SupportingItemV2[] = [];
  const allRows = [...document.activeDraft.blocks, ...(document.stash ?? []).flatMap((bundle) => bundle.rows)];
  for (const bundle of document.stash ?? []) {
    const selectedInBundle = bundle.rows.filter((row) => selected.has(row.id));
    if (selectedInBundle.length === 0) continue;
    if (selectedInBundle.length === bundle.rows.length) {
      restoredItems.push(...bundle.supportingItems);
      bundle.supportingItems = [];
      continue;
    }
    const selectedBundleIds = new Set(selectedInBundle.map((row) => row.id));
    const remainingBundleIds = new Set(bundle.rows.filter((row) => !selected.has(row.id)).map((row) => row.id));
    const remainingItems: SupportingItemV2[] = [];
    for (const item of bundle.supportingItems) {
      const references = supportingRows(item, allRows);
      if (item.placement.kind === "timed") {
        if (!item.placement.start || !item.placement.end) return diagnostic("ROW_REFERENCE_REVIEW_REQUIRED", "Review duration-ended supporting items before restoring part of their saved rows.");
        const placementOnly = { ...item };
        delete placementOnly.displayAttachment;
        const placementReferences = supportingRows(placementOnly, bundle.rows);
        const positions = bundle.rows.flatMap((row, index) => placementReferences.has(row.id) ? [index] : []);
        if (positions.length > 1) {
          for (let position = Math.min(...positions); position <= Math.max(...positions); position += 1) references.add(bundle.rows[position]!.id);
        }
      }
      const touchesSelected = [...references].some((id) => selectedBundleIds.has(id));
      const touchesRemaining = [...references].some((id) => remainingBundleIds.has(id));
      if (!references.size || touchesSelected && touchesRemaining) return diagnostic("ROW_REFERENCE_REVIEW_REQUIRED", "A supporting item crosses the selected row boundary or has no row anchor. Review its anchors before restoring these rows.");
      if (touchesSelected) restoredItems.push(item);
      else remainingItems.push(item);
    }
    bundle.supportingItems = remainingItems;
  }
  if (document.stash) {
    document.stash = document.stash.flatMap((bundle) => {
      const rows = bundle.rows.filter((row) => !selected.has(row.id));
      return rows.length ? [{ ...bundle, rows: [rows[0]!, ...rows.slice(1)] }] : [];
    });
  }
  for (const section of document.stashSections ?? []) section.rowIds = section.rowIds.filter((rowId) => !selected.has(rowId));
  if (document.stashOutline) document.stashOutline = document.stashOutline.filter((entry) => !selected.has(entry.rowId));
  document.activeDraft.supportingItems.push(...restoredItems);
  return { rows: moved };
}

function moveOutlineRowsToSection(document: ScriptDocumentV2, rowIds: string[], sectionId: string | null): string | null {
  const entries = ensureStashOutline(document);
  const selected = new Set(rowIds);
  const byId = outlineMap(entries);
  const selectedEntries = entries.filter((entry) => selected.has(entry.rowId));
  if (selectedEntries.length !== selected.size) return "Every selected row must still appear in the Stash outline.";
  if (sectionId !== null && !sectionExists(document, sectionId)) return "Choose an existing Stash section or the unsectioned Stash area.";
  for (const entry of selectedEntries) {
    if (entry.parentRowId !== null && !selected.has(entry.parentRowId) && byId.get(entry.parentRowId)?.sectionId !== sectionId) {
      return "Move a nested item only with its parent section or move its complete branch.";
    }
    if (entry.sectionId !== sectionId && entries.some((child) => isOutlineDescendant(child, entry.rowId, byId) && !selected.has(child.rowId))) {
      return "Move a nested item only with its complete branch.";
    }
  }
  if (selectedEntries.every((entry) => entry.sectionId === sectionId)) return null;
  const moving = selectedEntries.map((entry) => ({ ...entry, sectionId }));
  const remaining = entries.filter((entry) => !selected.has(entry.rowId));
  const targetRoots = remaining.filter((entry) => entry.parentRowId === null && entry.sectionId === sectionId);
  const insertionIndex = targetRoots.length
    ? outlineSubtreeEnd(remaining, targetRoots.at(-1)!.rowId) + 1
    : outlineInsertionIndex(document, remaining, null, sectionId, null);
  if (insertionIndex === null || insertionIndex < 0) return "The destination Stash section has no unambiguous outline slot.";
  remaining.splice(insertionIndex, 0, ...moving);
  document.stashOutline = remaining;
  return null;
}

function updateRelationships(before: ScriptDocumentV2, after: ScriptDocumentV2, command: RowEditCommandV2, moved: Set<string>): AuthoringDiagnosticV2 | null {
  const priorLocations = locations(before);
  const nextLocations = locations(after);
  for (const pair of after.rowTransitions ?? []) {
    if (pair.state === "needs_review") continue;
    const together = nextLocations.some((part) => part.rows.some((row, index) => row.id === pair.fromRowId && part.rows[index + 1]?.id === pair.toRowId));
    if (!together) pair.state = "needs_review";
  }
  const spans = before.rowAudioSpans ?? [];
  const flattenedCoverage = (document: ScriptDocumentV2, start: string, end: string): string[] | null => {
    const rows = document.activeDraft.blocks.filter((row) => row.type !== "section");
    const from = rows.findIndex((row) => row.id === start);
    const to = rows.findIndex((row) => row.id === end);
    // Even reversed endpoints bound a safety fence, never an inferred audible span.
    return from >= 0 && to >= 0 ? rows.slice(Math.min(from, to), Math.max(from, to) + 1).map((row) => row.id) : null;
  };
  const covered = (parts: Section[], start: string, end: string): string[] | null => {
    const part = parts.find((part) => part.rows.some((row) => row.id === start));
    const from = part?.rows.findIndex((row) => row.id === start) ?? -1;
    const to = part?.rows.findIndex((row) => row.id === end) ?? -1;
    return part && to >= from && from >= 0 ? part.rows.slice(from, to + 1).map((row) => row.id) : null;
  };
  for (const [index, span] of spans.entries()) {
    const oldRows = covered(priorLocations, span.startRowId, span.endRowId);
    const nextRows = covered(nextLocations, span.startRowId, span.endRowId);
    const oldFlat = flattenedCoverage(before, span.startRowId, span.endRowId);
    const nextFlat = flattenedCoverage(after, span.startRowId, span.endRowId);
    const touches = moved.has(span.startRowId) || moved.has(span.endRowId) || oldRows?.some((id) => moved.has(id)) || oldFlat?.some((id) => moved.has(id)) || JSON.stringify(oldRows) !== JSON.stringify(nextRows) || JSON.stringify(oldFlat) !== JSON.stringify(nextFlat);
    if (!touches) continue;
    const problem = () => diagnostic("AUDIO_REVIEW_REQUIRED", "This audio-span edit has no adopted audible policy. Review it explicitly before moving these rows.");
    if (!oldRows || command.kind === "stash_rows" || command.kind === "restore_stash" || command.kind === "restore_stash_rows" || command.kind === "place_stash_rows") return problem();
    const overlaps = spans.some((other, otherIndex) => otherIndex !== index && covered(priorLocations, other.startRowId, other.endRowId)?.some((id) => oldRows.includes(id)));
    if (overlaps) return problem();
    if (JSON.stringify(oldRows) === JSON.stringify(nextRows)) continue;
    const oldSection = priorLocations.find((part) => part.rows.some((row) => row.id === span.startRowId));
    const newStartSection = nextLocations.find((part) => part.rows.some((row) => row.id === span.startRowId));
    const newEndSection = nextLocations.find((part) => part.rows.some((row) => row.id === span.endRowId));
    const endpointMove = command.kind === "move_rows" && moved.size === 1 && (moved.has(span.startRowId) || moved.has(span.endRowId));
    if (!endpointMove || oldSection?.id !== newStartSection?.id || oldSection?.id !== newEndSection?.id) return problem();
    const target = after.rowAudioSpans![index]!;
    target.review ??= { previousEndRowId: span.endRowId, previousSettings: structuredClone(span.settings), alert: "Music now ends with this row. Review" };
    target.endRowId = target.startRowId;
  }
  return null;
}

/** One immutable local transaction. A refusal returns the original input object. */
export function applyRowEditV2(document: ScriptDocumentV2, expectedRevision: number, command: RowEditCommandV2): RowEditResultV2 {
  if (!command || typeof command !== "object") return refused(document, "ROW_COMMAND_INVALID", "Provide a row edit command.");
  const before = validateScriptDocumentV2(document);
  if (before.diagnostics.some((item) => ["SCHEMA_INVALID", "ENTITY_ID_DUPLICATE", "BLOCK_ID_DUPLICATE", "ROW_REFERENCE_INVALID"].includes(item.code))) return { ok: false, document, diagnostics: before.diagnostics };
  if (!Number.isSafeInteger(expectedRevision) || expectedRevision !== (document.rowEditRevision ?? 0) || expectedRevision === Number.MAX_SAFE_INTEGER) return refused(document, "ROW_REVISION_STALE", "The row document changed before this edit, or its revision cannot advance.");
  const working = structuredClone(document);
  const blocks = working.activeDraft.blocks;
  let moved: Row[] = [];
  if (command.kind === "restore_stash" || command.kind === "restore_stash_rows") {
    const index = gapIndex(blocks, command.destination);
    if (index === null) return refused(document, "ROW_DESTINATION_INVALID", "Choose an exact current section gap.");
    const outline = ensureStashOutline(working);
    if (command.kind === "restore_stash") {
      const bundleIndex = working.stash?.findIndex((bundle) => bundle.id === command.bundleId) ?? -1;
      if (bundleIndex < 0) return refused(document, "ROW_DESTINATION_INVALID", "Choose an existing Stash bundle.");
      const bundle = working.stash![bundleIndex]!;
      moved = [...bundle.rows];
      const movedIds = new Set(moved.map((row) => row.id));
      const compactOrNested = outline.some((entry) => movedIds.has(entry.rowId) && (entry.kind !== "row" || entry.parentRowId !== null || outline.some((child) => isOutlineDescendant(child, entry.rowId, outlineMap(outline)))));
      if (compactOrNested) return refused(document, "STASH_OUTLINE_PLACEMENT_REQUIRED", "Use place_stash_rows for compact or nested Stash items so their source positions are preserved.");
      working.stash!.splice(bundleIndex, 1);
      for (const section of working.stashSections ?? []) section.rowIds = section.rowIds.filter((id) => !movedIds.has(id));
      working.stashOutline = outline.filter((entry) => !movedIds.has(entry.rowId));
      working.activeDraft.supportingItems.push(...bundle.supportingItems);
    } else {
      if (!Array.isArray(command.rowIds) || command.rowIds.length === 0 || command.rowIds.some((id) => typeof id !== "string") || new Set(command.rowIds).size !== command.rowIds.length) {
        return refused(document, "ROW_SELECTION_INVALID", "Select one or more distinct saved rows.");
      }
      const selected = new Set(command.rowIds);
      const stashRows = stashRowsInVisibleOrder(working);
      const byId = outlineMap(outline);
      const compactOrNested = command.rowIds.some((rowId) => {
        const entry = byId.get(rowId);
        return !entry || entry.kind !== "row" || entry.parentRowId !== null || outline.some((child) => isOutlineDescendant(child, rowId, byId));
      });
      if (compactOrNested) return refused(document, "STASH_OUTLINE_PLACEMENT_REQUIRED", "Use place_stash_rows for compact or nested Stash items so their source positions are preserved.");
      moved = stashRows.filter((row) => selected.has(row.id));
      if (moved.length !== selected.size) return refused(document, "ROW_SELECTION_INVALID", "Every selected row must still be in Stash.");
      const taken = takeStashRows(working, selected, stashRows.map((row) => row.id));
      if ("code" in taken) return { ok: false, document, diagnostics: [taken] };
      moved = taken.rows;
    }
    blocks.splice(index, 0, ...moved);
  } else if (command.kind === "move_section") {
    const section = sections(blocks).find((part) => part.id === command.sectionId && part.id !== null);
    const headings = blocks.filter((block) => block.type === "section");
    const gap = headings.findIndex((heading, index) => heading.id === command.destination?.beforeSectionId && (headings[index - 1]?.id ?? null) === command.destination?.afterSectionId);
    const atEnd = command.destination?.beforeSectionId === null && (headings.at(-1)?.id ?? null) === command.destination?.afterSectionId;
    if (!section || gap < 0 && !atEnd || command.destination.afterSectionId === command.sectionId || command.destination.beforeSectionId === command.sectionId) return refused(document, "ROW_DESTINATION_INVALID", "Choose an exact section gap outside the moved section.");
    const index = atEnd ? blocks.length : blocks.findIndex((block) => block.id === headings[gap]!.id);
    const from = section.start - 1;
    const selected = blocks.splice(from, section.end - from);
    blocks.splice(index > from ? index - selected.length : index, 0, ...selected);
    moved = section.rows;
  } else if (command.kind === "move_rows" || command.kind === "stash_rows") {
    const rows = selectedRows(blocks, command.rowIds);
    if (!rows) return refused(document, "ROW_SELECTION_INVALID", "Select an ordered contiguous run within one section.");
    moved = rows;
    const from = blocks.findIndex((block) => block.id === rows[0]!.id);
    if (command.kind === "move_rows") {
      const index = gapIndex(blocks, command.destination);
      if (index === null || rows.some((row) => row.id === command.destination.afterRowId || row.id === command.destination.beforeRowId)) return refused(document, "ROW_DESTINATION_INVALID", "Choose an exact current gap outside the moved rows.");
      blocks.splice(from, rows.length);
      blocks.splice(index > from ? index - rows.length : index, 0, ...rows);
    } else {
      if (typeof command.bundleId !== "string" || !command.bundleId || (working.stash ?? []).some((bundle) => bundle.id === command.bundleId)) {
        return refused(document, "ROW_COMMAND_INVALID", "Provide an unused Stash bundle ID.");
      }
      const selected = new Set(rows.map((row) => row.id));
      const items: SupportingItemV2[] = [];
      for (const item of working.activeDraft.supportingItems) {
        const refs = supportingRows(item, blocks);
        if (![...refs].some((id) => selected.has(id))) continue;
        if ([...refs].some((id) => !selected.has(id))) return refused(document, "ROW_REFERENCE_REVIEW_REQUIRED", "A supporting item crosses the selected bundle boundary. Review its anchors before stashing.");
        items.push(item);
      }
      const section = sections(blocks).find((part) => part.rows.includes(rows[0]!))!;
      const rowIndex = section.rows.indexOf(rows[0]!);
      const originalGap: RowGapV2 = { sectionId: section.id, afterRowId: section.rows[rowIndex - 1]?.id ?? null, beforeRowId: section.rows[rowIndex + rows.length]?.id ?? null };
      const outline = ensureStashOutline(working);
      const returnedOutline = planStashReturn(working, rows, outline);
      if (!returnedOutline) return refused(document, "STASH_ORIGIN_DESTINATION_INVALID", "The original Stash section or sibling slot is missing, ambiguous, or no longer accepts this branch.");
      blocks.splice(from, rows.length);
      working.activeDraft.supportingItems = working.activeDraft.supportingItems.filter((item) => !items.includes(item));
      for (const row of rows) delete row.stashOrigin;
      (working.stash ??= []).push({ id: command.bundleId, rows: [rows[0]!, ...rows.slice(1)], supportingItems: items, originalGap });
      working.stashOutline = returnedOutline;
    }
  } else if (command.kind === "create_stash_section") {
    if (typeof command.sectionId !== "string" || !command.sectionId || typeof command.title !== "string" || !command.title) {
      return refused(document, "STASH_SECTION_INVALID", "Provide a section ID and a non-empty title.");
    }
    ensureStashOutline(working);
    (working.stashSections ??= []).push({ id: command.sectionId, title: command.title, rowIds: [] });
  } else if (command.kind === "move_stash_rows") {
    if (!Array.isArray(command.rowIds) || command.rowIds.length === 0 || command.rowIds.some((id) => typeof id !== "string") || new Set(command.rowIds).size !== command.rowIds.length) {
      return refused(document, "ROW_SELECTION_INVALID", "Select one or more distinct saved rows.");
    }
    const selected = new Set(command.rowIds);
    const stashRows = stashRowsInVisibleOrder(working);
    moved = stashRows.filter((row) => selected.has(row.id));
    if (moved.length !== selected.size) return refused(document, "ROW_SELECTION_INVALID", "Every selected row must still be in Stash.");
    if (command.sectionId !== null && typeof command.sectionId !== "string") return refused(document, "STASH_SECTION_NOT_FOUND", "Choose an existing Stash section or the unsectioned Stash area.");
    const moveError = moveOutlineRowsToSection(working, moved.map((row) => row.id), command.sectionId);
    if (moveError) return refused(document, "STASH_SECTION_NOT_FOUND", moveError);
  } else if (command.kind === "create_stash_note" || command.kind === "create_stash_clip") {
    if (
      !command || typeof command.bundleId !== "string" || !command.bundleId ||
      !command.row || typeof command.row !== "object" ||
      command.row.stashOrigin !== undefined ||
      typeof command.sectionId !== "string" && command.sectionId !== null ||
      typeof command.parentRowId !== "string" && command.parentRowId !== null ||
      typeof command.afterRowId !== "string" && command.afterRowId !== null
    ) return refused(document, "STASH_COMPACT_COMMAND_INVALID", "Provide a new saved note or clip and an exact Stash outline location.");
    if ((working.stash ?? []).some((bundle) => bundle.id === command.bundleId)) return refused(document, "ROW_COMMAND_INVALID", "Provide an unused Stash bundle ID.");
    if (blocks.some((block) => block.id === command.row.id) || stashRowById(working, command.row.id)) return refused(document, "ROW_ID_DUPLICATE", "A compact Stash item needs a new saved-row ID.");
    ensureStashOutline(working);
    const entries = working.stashOutline!;
    if (!sectionExists(working, command.sectionId)) return refused(document, "STASH_SECTION_NOT_FOUND", "Choose an existing Stash section or the unsectioned Stash area.");
    if (command.parentRowId !== null) {
      const parent = entries.find((entry) => entry.rowId === command.parentRowId);
      if (!parent || parent.kind !== "note" || parent.sectionId !== command.sectionId) return refused(document, "STASH_OUTLINE_PARENT_INVALID", "Nest an item under a saved note in the same Stash section.");
    }
    const insertAt = outlineInsertionIndex(working, entries, command.parentRowId, command.sectionId, command.afterRowId);
    if (insertAt === null) return refused(document, "STASH_OUTLINE_SLOT_INVALID", "Choose a current sibling in the same Stash outline location.");
    let row: Row;
    let kind: StashOutlineEntryV2["kind"];
    if (command.kind === "create_stash_note") {
      if (command.row.type !== "narration" || command.mode !== undefined && command.mode !== "default_direction" && command.mode !== "authored") {
        return refused(document, "STASH_NOTE_CONTENT_INVALID", "A Stash note needs a narration row and a supported authored-content mode.");
      }
      let note: NarrationBlockV2 | null;
      try {
        note = command.mode === "authored" ? structuredClone(command.row) : defaultDirectionNarrationRowV2(command.row);
      } catch {
        return refused(document, "STASH_NOTE_CONTENT_INVALID", "A Stash note needs a complete narration row with usable text tokens.");
      }
      if (!note) return refused(document, "STASH_NOTE_CONTENT_INVALID", "The note's token range cannot be wrapped as one stage direction; authored mixed content must be explicit.");
      row = note;
      kind = "note";
    } else {
      const payload = (command.row as unknown as { payload?: unknown }).payload;
      if (command.row.type !== "visual_only" || !payload || typeof payload !== "object" || Array.isArray(payload) || (payload as { pictureKind?: unknown }).pictureKind !== "clip") {
        return refused(document, "STASH_CLIP_CONTENT_INVALID", "A compact Stash clip needs a standalone footage row.");
      }
      row = structuredClone(command.row);
      kind = "clip";
    }
    entries.splice(insertAt, 0, { rowId: row.id, kind, parentRowId: command.parentRowId, sectionId: command.sectionId });
    (working.stash ??= []).push({ id: command.bundleId, rows: [row], supportingItems: [] });
  } else if (command.kind === "set_stash_outline") {
    if (!Array.isArray(command.entries)) return refused(document, "STASH_OUTLINE_COMMAND_INVALID", "Provide the complete ordered Stash outline.");
    const current = ensureStashOutline(working);
    const currentKinds = outlineMap(current);
    if (command.entries.some((entry) => !entry || typeof entry !== "object" || currentKinds.get(entry.rowId)?.kind !== entry.kind) || command.entries.length !== current.length) {
      return refused(document, "STASH_OUTLINE_KIND_IMMUTABLE", "Organizing the outline cannot create, remove, or reclassify saved rows.");
    }
    working.stashOutline = structuredClone(command.entries);
  } else if (command.kind === "place_stash_rows") {
    const index = gapIndex(blocks, command.destination);
    if (index === null) return refused(document, "ROW_DESTINATION_INVALID", "Choose an exact current section gap.");
    const entries = ensureStashOutline(working);
    const subtree = selectedOutlineSubtree(entries, command.rowIds);
    if (!subtree) return refused(document, "ROW_SELECTION_INVALID", "Select distinct Stash outline items without selecting a descendant twice; each selected item's descendants move with it.");
    const selected = new Set(subtree.map((entry) => entry.rowId));
    const origins = new Map<string, StashOriginV2>();
    for (const entry of subtree) {
      const anchors = outlineSiblingAnchors(entries, entry.rowId);
      if (!anchors) return refused(document, "ROW_SELECTION_INVALID", "Each selected row needs a current Stash outline location.");
      origins.set(entry.rowId, {
        kind: entry.kind,
        parentRowId: entry.parentRowId,
        sectionId: entry.sectionId,
        ...anchors,
        returnEligible: true,
      });
    }
    for (const entry of subtree) {
      const row = stashRowById(working, entry.rowId);
      if (row) row.stashOrigin = origins.get(entry.rowId)!;
    }
    const stashOrder = stashRowsInVisibleOrder(working).map((row) => row.id);
    const taken = takeStashRows(working, selected, stashOrder);
    if ("code" in taken) return { ok: false, document, diagnostics: [taken] };
    moved = taken.rows;
    blocks.splice(index, 0, ...moved);
  } else return refused(document, "ROW_COMMAND_INVALID", "Unknown row edit command.");
  if (working.stashSections?.length === 0) delete working.stashSections;
  if (working.stashOutline?.length === 0 && !working.stashSections?.length) delete working.stashOutline;
  if (working.stash?.length === 0 && document.stash === undefined) delete working.stash;
  if (JSON.stringify(working) === JSON.stringify(document)) return refused(document, "ROW_EDIT_NO_CHANGE", "The edit would leave Stash and Draft unchanged.");
  const relationshipProblem = updateRelationships(document, working, command, new Set(moved.map((row) => row.id)));
  if (relationshipProblem) return { ok: false, document, diagnostics: [relationshipProblem] };
  working.rowEditRevision = expectedRevision + 1;
  const after = validateScriptDocumentV2(working);
  const signature = (document: ScriptDocumentV2, item: AuthoringDiagnosticV2) => {
    const path = item.jsonPath.replace(/^\/activeDraft\/(blocks|supportingItems)\/(\d+)(?=\/|$)/, (_match: string, collection: "blocks" | "supportingItems", index: string) => `/activeDraft/${collection}/${document.activeDraft[collection][Number(index)]?.id ?? index}`);
    return JSON.stringify([item.code, item.blockId, item.entityId, item.message, path]);
  };
  const existing = new Map<string, number>();
  before.diagnostics.filter((item) => item.severity !== "warning").forEach((item) => {
    const key = signature(document, item);
    existing.set(key, (existing.get(key) ?? 0) + 1);
  });
  const errors = after.diagnostics.filter((item) => {
    if (item.severity === "warning") return false;
    const key = signature(working, item);
    const count = existing.get(key) ?? 0;
    if (count === 0) return true;
    existing.set(key, count - 1);
    return false;
  });
  return errors.length ? { ok: false, document, diagnostics: errors } : { ok: true, document: working, diagnostics: [] };
}

/** Serialized authoring drafts may contain unresolved intent; schema/identity corruption is refused. */
export function serializeAuthoringDocumentV2(document: ScriptDocumentV2): string {
  const ancestors = new Set<object>();
  const isJson = (value: unknown): boolean => {
    if (value === null || typeof value === "string" || typeof value === "boolean") return true;
    if (typeof value === "number") return Number.isFinite(value);
    if (typeof value !== "object" || ancestors.has(value)) return false;
    if (!Array.isArray(value) && Object.getPrototypeOf(value) !== Object.prototype) return false;
    ancestors.add(value);
    const valid = Object.values(value).every(isJson);
    ancestors.delete(value);
    return valid;
  };
  if (!isJson(document)) throw new Error("Saved authoring data must be losslessly representable as JSON.");
  const result = deserializeAuthoringDocumentV2(JSON.stringify(document));
  if (!result.ok) throw new Error(result.diagnostics.map((item) => item.message).join("; "));
  return JSON.stringify(result.document);
}

export function deserializeAuthoringDocumentV2(json: string): { ok: true; document: ScriptDocumentV2 } | { ok: false; diagnostics: AuthoringDiagnosticV2[] } {
  let document: unknown;
  try { document = JSON.parse(json); } catch { return { ok: false, diagnostics: [diagnostic("DOCUMENT_JSON_INVALID", "The saved document is not valid JSON.")] }; }
  const validation = validateScriptDocumentV2(document);
  const fatal = validation.diagnostics.filter((item) => ["SCHEMA_INVALID", "ENTITY_ID_DUPLICATE", "BLOCK_ID_DUPLICATE", "ROW_REFERENCE_INVALID"].includes(item.code));
  return fatal.length ? { ok: false, diagnostics: fatal } : { ok: true, document: document as ScriptDocumentV2 };
}

/** Session-owned history is independent of consumer views; no collaborative undo is implied. */
export function createRowEditSessionV2(initial: ScriptDocumentV2) {
  let current = structuredClone(initial);
  let revision = current.rowEditRevision ?? 0;
  const history: ScriptDocumentV2[] = [];
  return {
    get document() { return structuredClone(current); },
    get revision() { return revision; },
    get undoDepth() { return history.length; },
    view(kind: "script" | "outline" | "stash") {
      if (kind === "stash") return structuredClone(current.stash ?? []);
      return structuredClone(kind === "outline" ? current.activeDraft.blocks.filter((block) => block.type === "section") : current.activeDraft.blocks);
    },
    apply(command: RowEditCommandV2, expectedRevision = revision): RowEditResultV2 {
      if (expectedRevision !== revision) return refused(structuredClone(current), "ROW_REVISION_STALE", "The session changed before this edit.");
      const result = applyRowEditV2(current, current.rowEditRevision ?? 0, command);
      if (result.ok) { history.push(current); current = result.document; revision++; }
      return { ...result, document: structuredClone(result.document) };
    },
    undo(): RowEditResultV2 {
      if (revision === Number.MAX_SAFE_INTEGER) return refused(structuredClone(current), "ROW_REVISION_STALE", "The session revision cannot advance.");
      const previous = history.pop();
      if (!previous) return refused(structuredClone(current), "ROW_UNDO_EMPTY", "There is no row transaction to undo.");
      revision++;
      current = { ...previous, rowEditRevision: revision };
      return { ok: true, document: structuredClone(current), diagnostics: [] };
    },
  };
}
