import type { ScriptDocumentV2, RowGapV2, SupportingItemV2 } from "./generated/contracts-v2.js";
import type { AuthoringDiagnosticV2 } from "./authoring-v2.js";
import { validateScriptDocumentV2 } from "./authoring-v2-validation.js";

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
  | { kind: "move_stash_rows"; rowIds: string[]; sectionId: string | null };

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
  const sectioned = new Set((document.stashSections ?? []).flatMap((section) => section.rowIds));
  return [
    ...rows.filter((row) => !sectioned.has(row.id)),
    ...(document.stashSections ?? []).flatMap((section) => section.rowIds.flatMap((id) => {
      const row = byId.get(id);
      return row ? [row] : [];
    })),
  ];
}

function moveStashRowsToSection(document: ScriptDocumentV2, rowIds: string[], sectionId: string | null, visibleOrder: string[]): void {
  const selected = new Set(rowIds);
  const target = sectionId === null ? undefined : document.stashSections?.find((section) => section.id === sectionId);
  for (const section of document.stashSections ?? []) {
    if (section !== target) section.rowIds = section.rowIds.filter((id) => !selected.has(id));
  }
  if (target) {
    const existing = new Set(target.rowIds);
    target.rowIds.push(...visibleOrder.filter((id) => selected.has(id) && !existing.has(id)));
  }
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
    if (!oldRows || command.kind === "stash_rows" || command.kind === "restore_stash" || command.kind === "restore_stash_rows") return problem();
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
    if (command.kind === "restore_stash") {
      const bundleIndex = working.stash?.findIndex((bundle) => bundle.id === command.bundleId) ?? -1;
      if (bundleIndex < 0) return refused(document, "ROW_DESTINATION_INVALID", "Choose an existing Stash bundle.");
      const bundle = working.stash!.splice(bundleIndex, 1)[0]!;
      moved = bundle.rows;
      const movedIds = new Set(moved.map((row) => row.id));
      for (const section of working.stashSections ?? []) section.rowIds = section.rowIds.filter((id) => !movedIds.has(id));
      working.activeDraft.supportingItems.push(...bundle.supportingItems);
    } else {
      if (!Array.isArray(command.rowIds) || command.rowIds.length === 0 || command.rowIds.some((id) => typeof id !== "string") || new Set(command.rowIds).size !== command.rowIds.length) {
        return refused(document, "ROW_SELECTION_INVALID", "Select one or more distinct saved rows.");
      }
      const selected = new Set(command.rowIds);
      const stashRows = stashRowsInVisibleOrder(working);
      moved = stashRows.filter((row) => selected.has(row.id));
      if (moved.length !== selected.size) return refused(document, "ROW_SELECTION_INVALID", "Every selected row must still be in Stash.");

      const restoredItems: SupportingItemV2[] = [];
      const allRows = [...blocks, ...(working.stash ?? []).flatMap((bundle) => bundle.rows)];
      for (const bundle of working.stash ?? []) {
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
          const touchesSelected = [...references].some((id) => selectedBundleIds.has(id));
          const touchesRemaining = [...references].some((id) => remainingBundleIds.has(id));
          if (!references.size || touchesSelected && touchesRemaining) {
            return refused(document, "ROW_REFERENCE_REVIEW_REQUIRED", "A supporting item crosses the selected row boundary or has no row anchor. Review its anchors before restoring these rows.");
          }
          if (touchesSelected) restoredItems.push(item);
          else remainingItems.push(item);
        }
        bundle.supportingItems = remainingItems;
      }
      if (working.stash) {
        working.stash = working.stash.filter((bundle) => {
          const remainingRows = bundle.rows.filter((row) => !selected.has(row.id));
          if (remainingRows.length === 0) return false;
          if (remainingRows.length !== bundle.rows.length) bundle.rows = [remainingRows[0]!, ...remainingRows.slice(1)];
          return true;
        });
      }
      for (const section of working.stashSections ?? []) section.rowIds = section.rowIds.filter((id) => !selected.has(id));
      working.activeDraft.supportingItems.push(...restoredItems);
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
      blocks.splice(from, rows.length);
      working.activeDraft.supportingItems = working.activeDraft.supportingItems.filter((item) => !items.includes(item));
      (working.stash ??= []).push({ id: command.bundleId, rows: [rows[0]!, ...rows.slice(1)], supportingItems: items, originalGap });
    }
  } else if (command.kind === "create_stash_section") {
    if (typeof command.sectionId !== "string" || !command.sectionId || typeof command.title !== "string" || !command.title) {
      return refused(document, "STASH_SECTION_INVALID", "Provide a section ID and a non-empty title.");
    }
    (working.stashSections ??= []).push({ id: command.sectionId, title: command.title, rowIds: [] });
  } else if (command.kind === "move_stash_rows") {
    if (!Array.isArray(command.rowIds) || command.rowIds.length === 0 || command.rowIds.some((id) => typeof id !== "string") || new Set(command.rowIds).size !== command.rowIds.length) {
      return refused(document, "ROW_SELECTION_INVALID", "Select one or more distinct saved rows.");
    }
    const selected = new Set(command.rowIds);
    const stashRows = stashRowsInVisibleOrder(working);
    moved = stashRows.filter((row) => selected.has(row.id));
    if (moved.length !== selected.size) return refused(document, "ROW_SELECTION_INVALID", "Every selected row must still be in Stash.");
    if (command.sectionId !== null && !(working.stashSections ?? []).some((section) => section.id === command.sectionId)) {
      return refused(document, "STASH_SECTION_NOT_FOUND", "Choose an existing Stash section or the unsectioned Stash area.");
    }
    moveStashRowsToSection(working, moved.map((row) => row.id), command.sectionId, stashRows.map((row) => row.id));
  } else return refused(document, "ROW_COMMAND_INVALID", "Unknown row edit command.");
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
