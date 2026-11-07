import type { ScriptDocumentV2, RowGapV2, SupportingItemV2, StashOutlineEntryV2, StashOriginV2, StashRowGroupV2, NarrationBlockV2, NarratedVisualPayloadV2, VisualOnlyBlockV2 } from "./generated/contracts-v2.js";
import type { AuthoringDiagnosticV2 } from "./authoring-v2.js";
import { validateScriptDocumentV2 } from "./authoring-v2-validation.js";
import { applyStageDirectionEditV2, defaultDirectionNarrationRowV2, type StageDirectionEditCommandV2 } from "./authoring-v2-stage-direction-edits.js";
import { applyStashRowEditV2 } from "./authoring-v2-stash.js";
import { markStashOriginEditedV2, preserveStashOriginAfterEditV2 } from "./authoring-v2-stash-origin.js";
import { trimResearchClipOccurrenceV2 } from "./authoring-v2-research-snapshot.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";
import type { SaveStashGroupCommandV2 } from "./authoring-v2-stash-groups.js";

type Block = ScriptDocumentV2["activeDraft"]["blocks"][number];
type Row = Exclude<Block, { type: "section" }>;
export type { RowGapV2 } from "./generated/contracts-v2.js";

export type RowEditCommandV2 =
  | { kind: "move_rows"; rowIds: string[]; destination: RowGapV2 }
  | { kind: "move_section"; sectionId: string; destination: { afterSectionId: string | null; beforeSectionId: string | null } }
  | { kind: "stash_rows"; rowIds: string[]; bundleId: string }
  | { kind: "stash_group_rows"; rowIds: string[]; bundleId: string; groupId: string; sectionId: string | null; parentRowId: string | null; afterRowId: string | null; createdBy?: string; createdAt?: string }
  | { kind: "group_stash_rows"; rowIds: string[]; groupId: string; createdBy?: string; createdAt?: string }
  | { kind: "move_stash_group"; groupId: string; sectionId: string | null; parentRowId: string | null; afterRowId: string | null }
  | { kind: "ungroup_stash_group"; groupId: string }
  | { kind: "delete_stash_group"; groupId: string }
  | { kind: "place_stash_group"; groupId: string; destination: RowGapV2 }
  | { kind: "save_stash_group"; groupId: string; expectedRevision: number; expectedRowIds: string[]; members: Row[] }
  | { kind: "restore_stash"; bundleId: string; destination: RowGapV2 }
  | { kind: "restore_stash_rows"; rowIds: string[]; destination: RowGapV2 }
  | { kind: "create_stash_section"; sectionId: string; title: string }
  | { kind: "move_stash_rows"; rowIds: string[]; sectionId: string | null }
  | { kind: "create_stash_note"; bundleId: string; row: NarrationBlockV2; sectionId: string | null; parentRowId: string | null; afterRowId: string | null; mode?: "default_direction" | "authored" }
  | { kind: "create_stash_clip"; bundleId: string; row: VisualOnlyBlockV2; sectionId: string | null; parentRowId: string | null; afterRowId: string | null }
  | { kind: "attach_stash_footage"; noteRowId: string; clipRowId: string }
  | { kind: "replace_stash_footage"; noteRowId: string; clipRowId: string; releasedBundleId: string }
  | { kind: "detach_stash_footage"; noteRowId: string; bundleId: string }
  | { kind: "cleanup_blank_stash_note"; noteRowId: string; clipBundleId: string }
  | { kind: "trim_research_clip"; clipRowId: string; edge: "in" | "out"; frame: number }
  | { kind: "trim_research_clip"; clipRowId: string; edge: "clear_out" }
  | { kind: "place_attached_footage"; noteRowId: string; destination: RowGapV2 }
  | { kind: "set_stash_outline"; entries: StashOutlineEntryV2[] }
  | { kind: "place_stash_rows"; rowIds: string[]; destination: RowGapV2; includeDescendants?: boolean }
  | { kind: "edit_row"; rowId: string; row: Row }
  | { kind: "create_row"; row: Row; destination: RowGapV2 }
  | { kind: "delete_rows"; rowIds: string[] }
  | StageDirectionEditCommandV2;

/** Public bounded Stash ownership commands, used through applyRowEditV2. */
export type StashFootageCommandV2 = Extract<RowEditCommandV2, {
  kind: "attach_stash_footage" | "replace_stash_footage" |
    "detach_stash_footage" | "cleanup_blank_stash_note" | "trim_research_clip" | "place_attached_footage";
}>;

/** One-revision, no-nesting Stash organization commands; group IDs are not bundle IDs. */
export type StashGroupCommandV2 = Extract<RowEditCommandV2, {
  kind: "stash_group_rows" | "group_stash_rows" | "move_stash_group" |
    "ungroup_stash_group" | "delete_stash_group" | "place_stash_group" | "save_stash_group";
}>;

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

function plainObject(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  try {
    if (Object.getPrototypeOf(value) !== Object.prototype) return false;
    return Reflect.ownKeys(value).every((key) => typeof key === "string" && "value" in Object.getOwnPropertyDescriptor(value, key)!);
  } catch {
    return false;
  }
}

function exactKeys(value: Record<string, unknown>, keys: string[]): boolean {
  const ownKeys = Reflect.ownKeys(value);
  return ownKeys.length === keys.length && keys.every((key) => Object.hasOwn(value, key));
}

function isJsonValue(value: unknown, ancestors = new Set<object>()): boolean {
  if (value === null || typeof value === "string" || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value !== "object" || ancestors.has(value)) return false;
  try {
    if (Array.isArray(value)) {
      if (Object.getPrototypeOf(value) !== Array.prototype || Object.getOwnPropertySymbols(value).length > 0 || Object.getOwnPropertyNames(value).length !== value.length + 1) return false;
      ancestors.add(value);
      const valid = value.every((item, index) => Object.hasOwn(value, index) && isJsonValue(item, ancestors));
      ancestors.delete(value);
      return valid;
    }
    if (Object.getPrototypeOf(value) !== Object.prototype || Object.getOwnPropertySymbols(value).length > 0) return false;
    ancestors.add(value);
    const valid = Reflect.ownKeys(value).every((key) => {
      if (typeof key !== "string") return false;
      const descriptor = Object.getOwnPropertyDescriptor(value, key);
      return !!descriptor?.enumerable && "value" in descriptor && isJsonValue(descriptor.value, ancestors);
    });
    ancestors.delete(value);
    return valid;
  } catch {
    ancestors.delete(value);
    return false;
  }
}

function rowPayload(value: unknown): value is Row {
  return plainObject(value) && isJsonValue(value) && typeof value.id === "string" && value.id.length > 0 &&
    ["narration", "direction", "visual_only", "note_draft"].includes(String(value.type));
}

function rowGapPayload(value: unknown): value is RowGapV2 {
  return plainObject(value) && exactKeys(value, ["sectionId", "afterRowId", "beforeRowId"]) &&
    (value.sectionId === null || typeof value.sectionId === "string") &&
    (value.afterRowId === null || typeof value.afterRowId === "string") &&
    (value.beforeRowId === null || typeof value.beforeRowId === "string");
}

function rowIdsPayload(value: unknown): value is string[] {
  if (!Array.isArray(value)) return false;
  try {
    if (Object.getPrototypeOf(value) !== Array.prototype || Object.getOwnPropertySymbols(value).length > 0 || Object.getOwnPropertyNames(value).length !== value.length + 1) return false;
    for (let index = 0; index < value.length; index += 1) {
      const descriptor = Object.getOwnPropertyDescriptor(value, String(index));
      if (!descriptor?.enumerable || !("value" in descriptor) || typeof descriptor.value !== "string" || descriptor.value.length === 0) return false;
    }
    return true;
  } catch {
    return false;
  }
}

function isStageDirectionKind(kind: unknown): kind is StageDirectionEditCommandV2["kind"] {
  return kind === "make_stage_direction" || kind === "make_spoken" || kind === "delete_direction_delimiter";
}

function validStageDirectionCommand(value: unknown): value is StageDirectionEditCommandV2 {
  if (!plainObject(value) || typeof value.blockId !== "string" || value.blockId.length === 0) return false;
  if (value.kind === "delete_direction_delimiter") return exactKeys(value, ["kind", "blockId", "offset"]) && Number.isSafeInteger(value.offset);
  return (value.kind === "make_stage_direction" || value.kind === "make_spoken") &&
    exactKeys(value, ["kind", "blockId", "startOffset", "endOffset"]) &&
    Number.isSafeInteger(value.startOffset) && Number.isSafeInteger(value.endOffset);
}

function validAuthoredRowCommand(value: unknown): boolean {
  try {
    if (!plainObject(value)) return false;
    if (value.kind === "edit_row") {
      return exactKeys(value, ["kind", "rowId", "row"]) && typeof value.rowId === "string" && value.rowId.length > 0 &&
        rowPayload(value.row) && value.row.id === value.rowId;
    }
    if (value.kind === "create_row") {
      return exactKeys(value, ["kind", "row", "destination"]) && rowPayload(value.row) &&
        !Object.hasOwn(value.row, "stashOrigin") && rowGapPayload(value.destination);
    }
    if (value.kind === "delete_rows") {
      return exactKeys(value, ["kind", "rowIds"]) && rowIdsPayload(value.rowIds) && value.rowIds.length > 0 && new Set(value.rowIds).size === value.rowIds.length;
    }
    return false;
  } catch {
    return false;
  }
}

function validAttachmentCommand(value: unknown): boolean {
  if (!plainObject(value) || typeof value.kind !== "string") return false;
  if (value.kind === "trim_research_clip") {
    return typeof value.clipRowId === "string" && value.clipRowId.length > 0 &&
      (value.edge === "clear_out" ? exactKeys(value, ["kind", "clipRowId", "edge"]) :
        (value.edge === "in" || value.edge === "out") &&
        exactKeys(value, ["kind", "clipRowId", "edge", "frame"]) &&
        Number.isSafeInteger(value.frame) && (value.frame as number) >= 0);
  }
  if (typeof value.noteRowId !== "string" || value.noteRowId.length === 0) return false;
  switch (value.kind) {
    case "place_attached_footage":
      return exactKeys(value, ["kind", "noteRowId", "destination"]) && rowGapPayload(value.destination);
    case "attach_stash_footage":
      return exactKeys(value, ["kind", "noteRowId", "clipRowId"]) && typeof value.clipRowId === "string" && value.clipRowId.length > 0;
    case "replace_stash_footage":
      return exactKeys(value, ["kind", "noteRowId", "clipRowId", "releasedBundleId"]) &&
        typeof value.clipRowId === "string" && value.clipRowId.length > 0 &&
        typeof value.releasedBundleId === "string" && value.releasedBundleId.length > 0;
    case "detach_stash_footage":
      return exactKeys(value, ["kind", "noteRowId", "bundleId"]) && typeof value.bundleId === "string" && value.bundleId.length > 0;
    case "cleanup_blank_stash_note":
      return exactKeys(value, ["kind", "noteRowId", "clipBundleId"]) && typeof value.clipBundleId === "string" && value.clipBundleId.length > 0;
    default: return false;
  }
}

function attachmentKind(kind: unknown): boolean {
  return kind === "attach_stash_footage" || kind === "replace_stash_footage" ||
    kind === "detach_stash_footage" || kind === "cleanup_blank_stash_note" ||
    kind === "trim_research_clip" || kind === "place_attached_footage";
}

function groupKind(kind: unknown): kind is StashGroupCommandV2["kind"] {
  return ["stash_group_rows", "group_stash_rows", "move_stash_group", "ungroup_stash_group", "delete_stash_group", "place_stash_group", "save_stash_group"].includes(String(kind));
}

function validGroupCommand(value: unknown): boolean {
  if (!plainObject(value) || !groupKind(value.kind) || !isJsonValue(value) ||
    typeof value.groupId !== "string" || value.groupId.length === 0) return false;
  const location = (): boolean =>
    (value.sectionId === null || typeof value.sectionId === "string") &&
    (value.parentRowId === null || typeof value.parentRowId === "string") &&
    (value.afterRowId === null || typeof value.afterRowId === "string");
  const metadata = (): boolean =>
    (value.createdBy === undefined || typeof value.createdBy === "string") &&
    (value.createdAt === undefined || typeof value.createdAt === "string");
  const created = (): boolean => {
    const keys = ["kind", "groupId", "rowIds", ...(value.kind === "stash_group_rows" ? ["bundleId", "sectionId", "parentRowId", "afterRowId"] : []),
      ...(Object.hasOwn(value, "createdBy") ? ["createdBy"] : []), ...(Object.hasOwn(value, "createdAt") ? ["createdAt"] : [])];
    return exactKeys(value, keys) && rowIdsPayload(value.rowIds) && value.rowIds.length >= 2 &&
      new Set(value.rowIds).size === value.rowIds.length && metadata();
  };
  switch (value.kind) {
    case "save_stash_group":
      return exactKeys(value, ["kind", "groupId", "expectedRevision", "expectedRowIds", "members"]) &&
        Number.isSafeInteger(value.expectedRevision) && (value.expectedRevision as number) >= 0 &&
        rowIdsPayload(value.expectedRowIds) && value.expectedRowIds.length >= 2 &&
        new Set(value.expectedRowIds).size === value.expectedRowIds.length &&
        Array.isArray(value.members) && value.members.every(rowPayload) &&
        new Set(value.members.map((row) => row.id)).size === value.members.length;
    case "stash_group_rows": return created() && typeof value.bundleId === "string" && value.bundleId.length > 0 && location();
    case "group_stash_rows": return created();
    case "move_stash_group": return exactKeys(value, ["kind", "groupId", "sectionId", "parentRowId", "afterRowId"]) && location();
    case "place_stash_group": return exactKeys(value, ["kind", "groupId", "destination"]) && rowGapPayload(value.destination);
    default: return exactKeys(value, ["kind", "groupId"]);
  }
}

/** Shared exact command gate for direct edits and serialized Sorting trials. */
export function isStashGroupCommandV2(value: unknown): value is StashGroupCommandV2 {
  return validGroupCommand(value);
}

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

function groupById(document: ScriptDocumentV2, groupId: string): StashRowGroupV2 | undefined {
  return document.stashGroups?.find((group) => group.id === groupId);
}

function removeGroup(document: ScriptDocumentV2, groupId: string): void {
  if (document.stashGroups) document.stashGroups = document.stashGroups.filter((group) => group.id !== groupId);
  if (document.stashGroups?.length === 0) delete document.stashGroups;
}

/** Move only an entire flat sibling range; never silently reparent its children. */
function relocateGroupRows(
  document: ScriptDocumentV2, rowIds: string[], sectionId: string | null,
  parentRowId: string | null, afterRowId: string | null,
): string | null {
  const outline = ensureStashOutline(document);
  if (!sectionExists(document, sectionId)) return "Choose an existing Stash section.";
  const selected = new Set(rowIds);
  if (parentRowId !== null) {
    const parent = outline.find((entry) => entry.rowId === parentRowId);
    if (!parent || parent.kind !== "note" || parent.sectionId !== sectionId || selected.has(parentRowId)) {
      return "Group rows may be nested only under an existing compact note in the destination section.";
    }
  }
  if (afterRowId !== null && selected.has(afterRowId)) return "The destination must be outside the moving group.";
  const moving = rowIds.map((rowId) => outline.find((entry) => entry.rowId === rowId));
  if (moving.some((entry) => !entry)) return "Every member must exist in the Stash outline.";
  const remaining = outline.filter((entry) => !selected.has(entry.rowId));
  const index = outlineInsertionIndex(document, remaining, parentRowId, sectionId, afterRowId);
  if (index === null) return "Choose a current sibling position in the destination Stash section.";
  remaining.splice(index, 0, ...moving.map((entry) => ({
    ...entry!, kind: "row" as const, sectionId, parentRowId,
  })));
  document.stashOutline = remaining;
  return null;
}

/** Convert compact rows to full independent members, preserving each canonical payload. */
function formStashGroup(
  document: ScriptDocumentV2, rowIds: string[], groupId: string,
  createdBy?: string, createdAt?: string,
  destination?: { sectionId: string | null; parentRowId: string | null; afterRowId: string | null },
): string | null {
  if (groupById(document, groupId)) return "Choose an unused group identity.";
  const outline = ensureStashOutline(document);
  const byId = outlineMap(outline);
  if (rowIds.some((id) => !byId.has(id) || !stashRowById(document, id) ||
    document.stashGroups?.some((group) => group.rowIds.includes(id)))) {
    return "Select existing, ungrouped Stash rows.";
  }
  const selected = new Set(rowIds);
  if (outline.some((entry) => rowIds.some((id) =>
    entry.rowId !== id && isOutlineDescendant(entry, id, byId)))) {
    return "A compact Stash note with children cannot be converted without reviewing its dependent branch.";
  }
  if (destination) {
    const problem = relocateGroupRows(document, rowIds, destination.sectionId, destination.parentRowId, destination.afterRowId);
    if (problem) return problem;
  } else {
    const positions = rowIds.map((id) => outline.findIndex((entry) => entry.rowId === id));
    const first = byId.get(rowIds[0]!)!;
    if (positions.some((position, index) => position !== positions[0]! + index) ||
      rowIds.some((id) => byId.get(id)!.parentRowId !== first.parentRowId || byId.get(id)!.sectionId !== first.sectionId)) {
      return "Select consecutive sibling rows in the same Stash section, in visible order.";
    }
    for (const entry of outline) if (selected.has(entry.rowId)) entry.kind = "row";
  }
  for (const id of rowIds) {
    const row = stashRowById(document, id)!;
    if (row.stashOrigin?.kind !== "row" && row.stashOrigin) row.stashOrigin.returnEligible = false;
  }
  (document.stashGroups ??= []).push({
    id: groupId, rowIds: [...rowIds] as [string, string, ...string[]],
    ...(createdBy === undefined ? {} : { createdBy }),
    ...(createdAt === undefined ? {} : { createdAt }),
  });
  return null;
}

/** An attachment is owned by a note, never by its ordinary outline children. */
function compactNote(document: ScriptDocumentV2, rowId: string): NarrationBlockV2 | null {
  const row = stashRowById(document, rowId);
  return row?.type === "narration" &&
    document.stashOutline?.some((entry) => entry.rowId === rowId && entry.kind === "note")
    ? row : null;
}

function hasExternalRowReferences(document: ScriptDocumentV2, rowId: string): boolean {
  if ((document.rowReferences ?? []).some((item) => item.rowId === rowId) ||
    (document.rowTransitions ?? []).some((item) => item.fromRowId === rowId || item.toRowId === rowId) ||
    (document.rowAudioSpans ?? []).some((item) => item.startRowId === rowId || item.endRowId === rowId)) return true;
  const rows = [...document.activeDraft.blocks, ...(document.stash ?? []).flatMap((bundle) => bundle.rows)];
  if (rows.some((row) => row.id !== rowId && row.type !== "section" &&
    row.stashOrigin && [row.stashOrigin.parentRowId, row.stashOrigin.afterSiblingRowId, row.stashOrigin.beforeSiblingRowId].includes(rowId))) return true;
  if ((document.stash ?? []).some((bundle) =>
    bundle.originalGap?.afterRowId === rowId || bundle.originalGap?.beforeRowId === rowId)) return true;
  return [document.activeDraft.supportingItems, ...(document.stash ?? []).map((bundle) => bundle.supportingItems)]
    .some((items) => items.some((item) => supportingRows(item, rows).has(rowId)));
}

function removeOrdinaryStashClip(document: ScriptDocumentV2, rowId: string): VisualOnlyBlockV2 | null {
  const entry = document.stashOutline?.find((candidate) => candidate.rowId === rowId);
  const bundle = document.stash?.find((candidate) => candidate.rows.some((row) => row.id === rowId));
  const row = bundle?.rows.find((candidate) => candidate.id === rowId);
  // Do not silently migrate supporting-item or origin references into an embedded owner.
  if (!entry || entry.kind !== "clip" || !bundle || row?.type !== "visual_only" ||
    bundle.supportingItems.length > 0 || hasExternalRowReferences(document, rowId)) return null;
  bundle.rows = bundle.rows.filter((candidate) => candidate.id !== rowId) as typeof bundle.rows;
  document.stash = document.stash!.filter((candidate) => candidate.rows.length > 0);
  document.stashOutline = document.stashOutline!.filter((candidate) => candidate.rowId !== rowId);
  for (const section of document.stashSections ?? []) section.rowIds = section.rowIds.filter((id) => id !== rowId);
  const result = structuredClone(row);
  delete result.stashOrigin;
  return result;
}

function releaseAttachedClip(
  document: ScriptDocumentV2, noteId: string, bundleId: string, parentRowId: string | null,
  sectionId: string | null, insertAt: number,
): VisualOnlyBlockV2 | null {
  const note = compactNote(document, noteId);
  if (!note?.attachedFootage || document.stash?.some((bundle) => bundle.id === bundleId)) return null;
  const clip = note.attachedFootage.clip;
  delete note.attachedFootage;
  const released = structuredClone(clip);
  delete released.stashOrigin;
  (document.stash ??= []).push({ id: bundleId, rows: [released], supportingItems: [] });
  document.stashOutline!.splice(insertAt, 0, { rowId: released.id, kind: "clip", parentRowId, sectionId });
  return released;
}

/** Stable synthetic payload identity, so command replay and Sorting snapshots are deterministic. */
function attachedVisualPayloadId(noteId: string, clipId: string, slotId: string): string {
  const source = ["attached-footage/v1", noteId, clipId, slotId].join(":");
  const pieces = [2166136261, 2166136261 ^ 0x9e3779b9, 2166136261 ^ 0x85ebca6b, 2166136261 ^ 0xc2b2ae35].map((seed, index) => {
    let hash = seed >>> 0;
    for (let position = 0; position < source.length; position++) {
      hash = Math.imul(hash ^ (source.charCodeAt(position) + index), 16777619) >>> 0;
    }
    return hash.toString(16).padStart(8, "0");
  });
  const hex = pieces.join("");
  return [hex.slice(0, 8), hex.slice(8, 12), "4" + hex.slice(13, 16), "8" + hex.slice(17, 20), hex.slice(20)].join("-");
}

function mirroredAttachmentPayload(noteId: string, clip: VisualOnlyBlockV2, slotId: string): NarratedVisualPayloadV2 {
  const selected = clip.visualOnlyTiming.selectedSourceRange;
  return {
    kind: "visual", payloadId: attachedVisualPayloadId(noteId, clip.id, slotId), pictureKind: clip.payload.pictureKind,
    source: structuredClone(clip.payload.source), sourceUsage: selected ? { sourceInFrame: selected.startFrame } : null,
    audioPolicy: clip.payload.audioPolicy === "quiet" ? "quiet" : "mute",
    framingPolicy: clip.payload.framingPolicy,
    ...(clip.researchClip ? { researchClip: structuredClone(clip.researchClip) } : {}),
    ...(clip.frameBinding ? { frameBinding: structuredClone(clip.frameBinding) } : {}),
    ...(selected ? { selectedSourceRange: structuredClone(selected) } : {}),
  };
}

/** Active representation mirrors the owned clip in one primary visual slot; no second clip row is created. */
export function presentAttachedFootageForSortingV2(note: NarrationBlockV2): boolean {
  const clip = note.attachedFootage?.clip;
  if (!clip) return true;
  // A narration visual cannot represent independent full-source audio. Never mute it implicitly.
  if (clip.payload.audioPolicy === "full") return false;
  const sequence = note.primaryVisualSequence;
  const slot = sequence?.slots.length === 1 ? sequence.slots[0] : undefined;
  if (!slot || slot.kind !== "content" || slot.relation.kind !== "base" ||
    slot.boundaryBefore.kind !== "row_start" || slot.playoutPolicy !== "match_structural_interval" ||
    slot.payload.kind !== "on_camera" || slot.payload.presenterChoiceId !== null) return false;
  slot.payload = mirroredAttachmentPayload(note.id, clip, slot.id);
  return true;
}

export function parkAttachedFootageForSortingV2(note: NarrationBlockV2): boolean {
  if (!note.attachedFootage) return true;
  const slot = note.primaryVisualSequence?.slots[0];
  if (!slot || note.primaryVisualSequence?.slots.length !== 1 ||
    slot.kind !== "content" || slot.payload.kind !== "visual" ||
    slot.relation.kind !== "base" || slot.boundaryBefore.kind !== "row_start" ||
    slot.playoutPolicy !== "match_structural_interval") return false;
  const clip = note.attachedFootage.clip;
  if (!sameAuthoringJsonV2(slot.payload, mirroredAttachmentPayload(note.id, clip, slot.id))) return false;
  slot.payload = { kind: "on_camera", presenterChoiceId: null };
  return true;
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

function insertReturningSiblingGroup(document: ScriptDocumentV2, entries: StashOutlineEntryV2[], plans: StashReturnPlan[], order: string[]): boolean {
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
  const activeParentContexts = new Map<string, { row: Row; origin: StashOriginV2 | undefined; returnedChildIds: Set<string> }>();
  for (const row of rows) {
    const parentRowId = row.stashOrigin?.parentRowId;
    if (!parentRowId || activeParentContexts.has(parentRowId)) continue;
    const parent = document.activeDraft.blocks.find((block) => block.id === parentRowId && block.type !== "section");
    if (parent && parent.type !== "section") activeParentContexts.set(parentRowId, {
      row: parent,
      origin: parent.stashOrigin ? { ...parent.stashOrigin } : undefined,
      returnedChildIds: new Set(),
    });
  }
  const pending: StashReturnPlan[] = [];
  for (const [activeOrder, row] of rows.entries()) {
    const origin: StashOriginV2 | undefined = row.stashOrigin;
    const kind = origin?.returnEligible && origin.kind !== "row" ? origin.kind : "row";
    let parentRowId = origin?.parentRowId ?? null;
    let afterSiblingRowId = origin?.afterSiblingRowId ?? null;
    let beforeSiblingRowId = origin?.beforeSiblingRowId ?? null;
    const sectionId = origin?.sectionId ?? null;
    // A separated attachment has no historical *clip* sibling slot. With an
    // unchanged owner it can safely append as an ordinary child when occupied.
    let appendToSection = origin === undefined || !!origin?.originalAttachedNoteRowId &&
      parentRowId === origin.originalAttachedNoteRowId && afterSiblingRowId === null && beforeSiblingRowId === null;
    if (parentRowId !== null) {
      if (selected.has(parentRowId)) {
        if (resultingKinds.get(parentRowId) !== "note") return null;
      } else if (document.activeDraft.blocks.some((block) => block.id === parentRowId && block.type !== "section")) {
        const originalParentRowId = parentRowId;
        const parentContext = activeParentContexts.get(originalParentRowId);
        const parentOrigin = parentContext?.origin;
        if (parentOrigin && parentOrigin.sectionId !== sectionId) return null;
        const currentRoots = entries.filter((entry) => entry.parentRowId === null && entry.sectionId === sectionId);
        const currentRootIds = new Set(currentRoots.map((entry) => entry.rowId));
        const returningSiblingIds = new Set(rows
          .filter((candidate) => candidate.id !== row.id && candidate.stashOrigin?.parentRowId === originalParentRowId && candidate.stashOrigin.sectionId === sectionId)
          .map((candidate) => candidate.id));
        const isTopLevelAnchor = (anchor: string | null): boolean => anchor !== null && (currentRootIds.has(anchor) || returningSiblingIds.has(anchor));
        if (parentOrigin) {
          const resolvedAfter = isTopLevelAnchor(afterSiblingRowId);
          const resolvedBefore = isTopLevelAnchor(beforeSiblingRowId);
          if (!resolvedAfter) afterSiblingRowId = parentOrigin.afterSiblingRowId;
          if (!resolvedBefore && !(resolvedAfter && afterSiblingRowId === parentOrigin.beforeSiblingRowId)) beforeSiblingRowId = parentOrigin.beforeSiblingRowId;
          if (!resolvedAfter && resolvedBefore && beforeSiblingRowId === parentOrigin.afterSiblingRowId) afterSiblingRowId = null;
        }
        parentRowId = null;
        appendToSection = currentRoots.length === 0;
        parentContext?.returnedChildIds.add(row.id);
      } else {
        const parent = originalParents.get(parentRowId);
        if (!parent || parent.kind !== "note") return null;
      }
    }
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
    const order = orderReturningSiblings(result, groupPlans);
    if (!order) return null;
    for (const context of activeParentContexts.values()) {
      const firstReturnedChild = order.find((rowId) => context.returnedChildIds.has(rowId));
      if (!firstReturnedChild || !context.row.stashOrigin) continue;
      const oldBefore = context.origin?.beforeSiblingRowId ?? null;
      const oldBeforeIndex = oldBefore === null ? -1 : order.indexOf(oldBefore);
      if (oldBefore === null || oldBeforeIndex < 0 || order.indexOf(firstReturnedChild) < oldBeforeIndex) {
        context.row.stashOrigin.beforeSiblingRowId = firstReturnedChild;
      }
    }
    if (!insertReturningSiblingGroup(document, result, groupPlans, order)) return null;
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
    if (!oldRows || command.kind === "stash_rows" || command.kind === "stash_group_rows" || command.kind === "restore_stash" || command.kind === "restore_stash_rows" || command.kind === "place_stash_rows" || command.kind === "place_stash_group") return problem();
    const overlaps = spans.some((other, otherIndex) => otherIndex !== index && covered(priorLocations, other.startRowId, other.endRowId)?.some((id) => oldRows.includes(id)));
    if (overlaps) return problem();
    if (JSON.stringify(oldRows) === JSON.stringify(nextRows)) continue;
    const oldSection = priorLocations.find((part) => part.rows.some((row) => row.id === span.startRowId));
    const newStartSection = nextLocations.find((part) => part.rows.some((row) => row.id === span.startRowId));
    const newEndSection = nextLocations.find((part) => part.rows.some((row) => row.id === span.endRowId));
    const withinSectionMove = command.kind === "move_rows" && [...moved].every((id) =>
      priorLocations.find((part) => part.rows.some((row) => row.id === id))?.id === oldSection?.id &&
      nextLocations.find((part) => part.rows.some((row) => row.id === id))?.id === oldSection?.id);
    if (!withinSectionMove || !newStartSection || oldSection?.id !== newStartSection.id || oldSection?.id !== newEndSection?.id) return problem();
    const startIndex = newStartSection.rows.findIndex((row) => row.id === span.startRowId);
    let retainedEndRowId = span.startRowId;
    for (let offset = 1; offset < oldRows.length; offset++) {
      if (newStartSection.rows[startIndex + offset]?.id !== oldRows[offset]) break;
      retainedEndRowId = oldRows[offset]!;
    }
    const target = after.rowAudioSpans![index]!;
    target.review ??= { previousEndRowId: span.endRowId, previousSettings: structuredClone(span.settings), alert: "Music shortened by this move" };
    target.review.alert = "Music shortened by this move";
    target.endRowId = retainedEndRowId;
  }
  return null;
}

function audioSpanTouchesRows(document: ScriptDocumentV2, selected: Set<string>): boolean {
  const activeRows = document.activeDraft.blocks.filter((block): block is Row => block.type !== "section");
  const places = locations(document);
  return (document.rowAudioSpans ?? []).some((span) => {
    if (selected.has(span.startRowId) || selected.has(span.endRowId)) return true;
    const samePlace = places.find((part) => part.rows.some((row) => row.id === span.startRowId) && part.rows.some((row) => row.id === span.endRowId));
    if (samePlace) {
      const start = samePlace.rows.findIndex((row) => row.id === span.startRowId);
      const end = samePlace.rows.findIndex((row) => row.id === span.endRowId);
      if (samePlace.rows.slice(Math.min(start, end), Math.max(start, end) + 1).some((row) => selected.has(row.id))) return true;
    }
    const start = activeRows.findIndex((row) => row.id === span.startRowId);
    const end = activeRows.findIndex((row) => row.id === span.endRowId);
    return start >= 0 && end >= 0 && activeRows.slice(Math.min(start, end), Math.max(start, end) + 1).some((row) => selected.has(row.id));
  });
}

function deleteRows(working: ScriptDocumentV2, rowIds: string[]): { rows: Row[] } | AuthoringDiagnosticV2 {
  const activeRows = working.activeDraft.blocks.filter((block): block is Row => block.type !== "section");
  const stashedRows = (working.stash ?? []).flatMap((bundle) => bundle.rows);
  const activeIds = new Set(activeRows.map((row) => row.id));
  const stashIds = new Set(stashedRows.map((row) => row.id));
  const activeSelected = rowIds.filter((rowId) => activeIds.has(rowId));
  const stashSelected = rowIds.filter((rowId) => stashIds.has(rowId));
  if (activeSelected.length + stashSelected.length !== rowIds.length || activeSelected.length > 0 && stashSelected.length > 0) {
    return diagnostic("ROW_SELECTION_INVALID", "Delete existing rows from Draft or Stash in separate edits.");
  }

  const selected = new Set(rowIds);
  const removedRows = [...activeRows, ...stashedRows].filter((row) => selected.has(row.id));
  if (removedRows.some((row) => row.type === "narration" && row.attachedFootage)) {
    return diagnostic("STASH_ATTACHMENT_REVIEW_REQUIRED", "Detach the owned footage or use explicit blank-note cleanup before deleting its note.");
  }
  if (audioSpanTouchesRows(working, selected)) return diagnostic("AUDIO_REVIEW_REQUIRED", "A saved row audio span touches these rows. Review or remove that audio intent before deleting them.");

  for (const pair of working.rowTransitions ?? []) {
    const fromSelected = selected.has(pair.fromRowId);
    const toSelected = selected.has(pair.toRowId);
    if (fromSelected !== toSelected) return diagnostic("ROW_REFERENCE_REVIEW_REQUIRED", "A row transition links a selected row to a surviving row. Review or remove that transition before deleting these rows.");
  }

  const survivingRows = [...activeRows, ...stashedRows].filter((row) => !selected.has(row.id));
  for (const row of survivingRows) {
    const origin = row.stashOrigin;
    if (origin && [origin.parentRowId, origin.afterSiblingRowId, origin.beforeSiblingRowId].some((rowId) => rowId !== null && selected.has(rowId))) {
      return diagnostic("ROW_REFERENCE_REVIEW_REQUIRED", "A surviving row's Stash return location uses a selected row. Review that saved relationship before deleting these rows.");
    }
  }
  if (activeSelected.length > 0 && (working.stash ?? []).some((bundle) =>
    bundle.rows.some((row) => !selected.has(row.id)) &&
    (selected.has(bundle.originalGap?.afterRowId ?? "") || selected.has(bundle.originalGap?.beforeRowId ?? "")))) {
    return diagnostic("ROW_REFERENCE_REVIEW_REQUIRED", "A saved Stash row uses a selected row as its restore boundary. Restore or review that saved relationship before deleting these rows.");
  }

  if (stashSelected.length > 0) {
    const outline = ensureStashOutline(working);
    const byId = outlineMap(outline);
    if (stashSelected.some((rowId) => !byId.has(rowId))) return diagnostic("ROW_SELECTION_INVALID", "Every selected row must still appear in the Stash outline.");
    if (outline.some((entry) => stashSelected.some((root) => isOutlineDescendant(entry, root, byId)) && !selected.has(entry.rowId))) {
      return diagnostic("STASH_OUTLINE_BRANCH_REQUIRED", "Select a complete Stash branch before deleting a parent row.");
    }
  }

  const allRows = [...working.activeDraft.blocks, ...stashedRows];
  const filterSupportingItems = (items: SupportingItemV2[]): SupportingItemV2[] | null => {
    const retained: SupportingItemV2[] = [];
    for (const item of items) {
      const references = supportingRows(item, allRows);
      const touchesSelected = [...references].some((rowId) => selected.has(rowId));
      if (!touchesSelected) {
        retained.push(item);
        continue;
      }
      if ([...references].some((rowId) => !selected.has(rowId))) return null;
    }
    return retained;
  };
  const activeItems = filterSupportingItems(working.activeDraft.supportingItems);
  if (!activeItems) return diagnostic("ROW_REFERENCE_REVIEW_REQUIRED", "A supporting item crosses the selected row boundary. Review its anchors before deleting these rows.");
  const bundleItems = new Map<string, SupportingItemV2[]>();
  for (const bundle of working.stash ?? []) {
    const items = filterSupportingItems(bundle.supportingItems);
    if (!items) return diagnostic("ROW_REFERENCE_REVIEW_REQUIRED", "A saved supporting item crosses the selected row boundary. Review its anchors before deleting these rows.");
    if (bundle.rows.every((row) => selected.has(row.id)) && items.length > 0) {
      return diagnostic("ROW_REFERENCE_REVIEW_REQUIRED", "A saved supporting item has no safe row anchor in the deleted Stash bundle. Review it before deleting these rows.");
    }
    bundleItems.set(bundle.id, items);
  }

  working.activeDraft.supportingItems = activeItems;
  for (const bundle of working.stash ?? []) bundle.supportingItems = bundleItems.get(bundle.id)!;
  if (working.rowTransitions) working.rowTransitions = working.rowTransitions.filter((pair) => !(selected.has(pair.fromRowId) && selected.has(pair.toRowId)));
  if (working.rowReferences) working.rowReferences = working.rowReferences.filter((reference) => !selected.has(reference.rowId));
  if (working.rowTransitions?.length === 0) delete working.rowTransitions;
  if (working.rowReferences?.length === 0) delete working.rowReferences;
  if (activeSelected.length > 0) {
    working.activeDraft.blocks = working.activeDraft.blocks.filter((block) => !selected.has(block.id));
  } else {
    if (working.stash) working.stash = working.stash.flatMap((bundle) => {
      const rows = bundle.rows.filter((row) => !selected.has(row.id));
      return rows.length ? [{ ...bundle, rows: [rows[0]!, ...rows.slice(1)] }] : [];
    });
    for (const section of working.stashSections ?? []) section.rowIds = section.rowIds.filter((rowId) => !selected.has(rowId));
    if (working.stashOutline) working.stashOutline = working.stashOutline.filter((entry) => !selected.has(entry.rowId));
  }
  return { rows: removedRows };
}

/** Save a detached group stage against the exact membership it was opened with. */
function saveStashGroup(working: ScriptDocumentV2, command: SaveStashGroupCommandV2): AuthoringDiagnosticV2 | null {
  const problem = (code: string, message: string) => diagnostic(code, message);
  const group = groupById(working, command.groupId);
  if (!group) return problem("STASH_GROUP_NOT_FOUND", "Choose an existing Stash group to save.");
  if (!sameAuthoringJsonV2(group.rowIds, command.expectedRowIds)) {
    return problem("STASH_GROUP_STALE", "The saved group membership changed while the member editor was open.");
  }
  const outline = ensureStashOutline(working);
  const currentIds = new Set(group.rowIds);
  const desiredIds = new Set(command.members.map((row) => row.id));
  const deletedIds = group.rowIds.filter((id) => !desiredIds.has(id));
  const stored = new Map((working.stash ?? []).flatMap((bundle) => bundle.rows.map((row) => [row.id, row] as const)));
  const activeIds = new Set(working.activeDraft.blocks.map((row) => row.id));
  const addedSaved = command.members.filter((row) => !currentIds.has(row.id) && stored.has(row.id));
  const outsideGroup = new Set((working.stashGroups ?? []).filter((other) => other.id !== group.id).flatMap((other) => other.rowIds));
  const first = outline.find((entry) => entry.rowId === group.rowIds[0])!;
  const selected = new Set([...group.rowIds, ...addedSaved.map((row) => row.id)]);
  const existingPositions = outline.flatMap((entry, index) => selected.has(entry.rowId) ? [index] : []);
  if (addedSaved.some((row) => {
    const entry = outline.find((candidate) => candidate.rowId === row.id);
    return !entry || entry.kind !== "row" || entry.sectionId !== first.sectionId ||
      entry.parentRowId !== first.parentRowId || outsideGroup.has(row.id);
  }) || existingPositions.length !== selected.size ||
      existingPositions.some((index, offset) => index !== existingPositions[0]! + offset)) {
    return problem("STASH_GROUP_MEMBERS_INVALID", "Additional saved members must be ungrouped, adjacent sibling rows in the group's current Stash location.");
  }
  if (command.members.some((row) => activeIds.has(row.id))) {
    return problem("STASH_GROUP_MEMBERS_INVALID", "An active Draft row cannot be copied into a saved group.");
  }
  const proposedOrder = command.members.map((row) => row.id);
  if ((!sameAuthoringJsonV2(proposedOrder, group.rowIds) || deletedIds.length > 0) &&
      audioSpanTouchesRows(working, selected)) {
    return problem("AUDIO_REVIEW_REQUIRED", "Review the saved audio span before changing group membership or order.");
  }
  const allItems = [...working.activeDraft.supportingItems, ...(working.stash ?? []).flatMap((bundle) => bundle.supportingItems)];
  if (deletedIds.some((id) => (working.rowReferences ?? []).some((reference) => reference.rowId === id) ||
      allItems.some((item) => supportingRows(item, [...working.activeDraft.blocks, ...stored.values()]).has(id)))) {
    return problem("ROW_REFERENCE_REVIEW_REQUIRED", "Removing a group member would discard a citation or saved row reference. Review its anchors first.");
  }

  const anchorBundle = working.stash?.find((bundle) => bundle.rows.some((row) => row.id === group.rowIds[0]));
  if (!anchorBundle) return problem("STASH_GROUP_MEMBERS_INVALID", "The group's original saved-row bundle is missing.");
  for (const member of command.members) {
    const previous = stored.get(member.id);
    if (!previous) {
      if (member.stashOrigin) return problem("STASH_GROUP_MEMBERS_INVALID", "New group members cannot forge saved-return provenance.");
      anchorBundle.rows.push(structuredClone(member));
      continue;
    }
    if (previous.type !== member.type) {
      return problem("STASH_GROUP_MEMBERS_INVALID", "Existing saved members must keep their row identity and type.");
    }
    if (previous.type === "narration" && member.type === "narration" &&
        (previous.plainDirection !== member.plainDirection ||
          !sameAuthoringJsonV2(previous.attachedFootage, member.attachedFootage))) {
      return problem("STASH_ATTACHMENT_REVIEW_REQUIRED", "A group Save cannot silently change speech intent or owned footage. Use explicit review commands.");
    }
    if (previous.type === "visual_only" && member.type === "visual_only" &&
        (!sameAuthoringJsonV2(previous.researchClip, member.researchClip) ||
         !sameAuthoringJsonV2(previous.frameBinding, member.frameBinding) ||
         !sameAuthoringJsonV2(previous.payload, member.payload) ||
         !sameAuthoringJsonV2(previous.visualOnlyTiming, member.visualOnlyTiming))) {
      return problem("STASH_ATTACHMENT_REVIEW_REQUIRED", "Footage identity and source ranges require an explicit clip command, not a group member replacement.");
    }
    // Exact provenance is kept until an authored change marks an origin ineligible.
    const authoredBefore = structuredClone(previous);
    const authoredNext = structuredClone(member);
    delete authoredBefore.stashOrigin;
    delete authoredNext.stashOrigin;
    const edited = !sameAuthoringJsonV2(authoredBefore, authoredNext);
    const replacement = edited ? preserveStashOriginAfterEditV2(previous, structuredClone(member)) : structuredClone(previous);
    if (!currentIds.has(member.id) && replacement.stashOrigin?.kind !== "row" && replacement.stashOrigin) {
      replacement.stashOrigin.returnEligible = false;
    }
    // A surviving supporting anchor must still identify its original word/event.
    const inspect = (value: unknown, referenceRowId?: string): boolean => {
        if (!value || typeof value !== "object") return true;
        if (!Array.isArray(value) && ("blockId" in value && value.blockId === member.id || referenceRowId === member.id) &&
            "tokenId" in value && typeof value.tokenId === "string") {
          const tokens = replacement.type === "narration" ? replacement.tokens : [];
          const token = tokens.find((candidate) => candidate.id === value.tokenId);
          if (!token || "quotedWord" in value && token.value !== value.quotedWord) return false;
        }
        if (!Array.isArray(value) && "eventId" in value && typeof value.eventId === "string" &&
            previous.type === "narration" && previous.overlayEvents.some((event) => event.id === value.eventId) &&
            (replacement.type !== "narration" || !replacement.overlayEvents.some((event) => event.id === value.eventId))) {
          return false;
        }
        return Object.values(value).every((child) => inspect(child, referenceRowId));
    };
    if (allItems.some((item) => !inspect(item.placement) || !inspect(item.displayAttachment)) ||
        (working.rowReferences ?? []).some((reference) => reference.rowId === member.id && !inspect(reference.anchor, member.id))) {
      return problem("ROW_REFERENCE_REVIEW_REQUIRED", "A group edit would invalidate an existing citation or comment anchor.");
      }
    const bundle = working.stash!.find((candidate) => candidate.rows.some((row) => row.id === member.id))!;
    bundle.rows[bundle.rows.findIndex((row) => row.id === member.id)] = replacement;
  }

  // Remove the group metadata before using the regular protected row deletion.
  // No intermediate state is returned or revisioned; any refusal discards it all.
  removeGroup(working, group.id);
  if (deletedIds.length > 0) {
    const deleted = deleteRows(working, deletedIds);
    if ("code" in deleted) return deleted;
  }
  const insertion = outline.slice(0, existingPositions[0]).filter((entry) => !selected.has(entry.rowId)).length;
  const otherEntries = outline.filter((entry) => !selected.has(entry.rowId));
  const oldEntries = new Map(outline.map((entry) => [entry.rowId, entry] as const));
  otherEntries.splice(insertion, 0, ...command.members.map((member) => oldEntries.get(member.id) ?? {
    rowId: member.id, kind: "row" as const, sectionId: first.sectionId, parentRowId: first.parentRowId,
  }));
  working.stashOutline = otherEntries;
  if (command.members.length >= 2) {
    (working.stashGroups ??= []).push({ ...group, rowIds: proposedOrder as [string, string, ...string[]] });
  }
  return null;
}

/** One immutable local transaction. A refusal returns the original input object. */
export function applyRowEditV2(document: ScriptDocumentV2, expectedRevision: number, command: RowEditCommandV2): RowEditResultV2 {
  if (!plainObject(command)) return refused(document, "ROW_COMMAND_INVALID", "Provide a row edit command.");
  try {
    if (groupKind(command.kind) && !validGroupCommand(command)) return refused(document, "ROW_COMMAND_INVALID", "Provide an exact Stash group command with distinct row IDs and an unambiguous location.");
    if ((command.kind === "edit_row" || command.kind === "create_row" || command.kind === "delete_rows") && !validAuthoredRowCommand(command)) return refused(document, "ROW_COMMAND_INVALID", "Provide a complete authored row edit command with exact row IDs and destinations.");
    if (attachmentKind(command.kind) && (!isJsonValue(command) || !validAttachmentCommand(command))) return refused(document, "ROW_COMMAND_INVALID", "Provide an exact footage attachment command.");
    if (command.kind === "place_stash_rows" &&
      (!isJsonValue(command) ||
        !exactKeys(command, Object.hasOwn(command, "includeDescendants") ? ["kind", "rowIds", "destination", "includeDescendants"] : ["kind", "rowIds", "destination"]) ||
        !rowIdsPayload(command.rowIds) || !rowGapPayload(command.destination) ||
        Object.hasOwn(command, "includeDescendants") && typeof command.includeDescendants !== "boolean")) {
      return refused(document, "ROW_COMMAND_INVALID", "Provide a valid Stash placement with an optional boolean includeDescendants.");
    }
    if (isStageDirectionKind(command.kind) && !validStageDirectionCommand(command)) return refused(document, "ROW_COMMAND_INVALID", "Provide a complete stage-direction edit command.");
  } catch {
    return refused(document, "ROW_COMMAND_INVALID", "Provide a complete row edit command with plain JSON values.");
  }
  const before = validateScriptDocumentV2(document);
  if (before.diagnostics.some((item) => ["SCHEMA_INVALID", "ENTITY_ID_DUPLICATE", "BLOCK_ID_DUPLICATE", "ROW_REFERENCE_INVALID", "PLAIN_DIRECTION_INTENT_INVALID", "FOOTAGE_OWNER_DUPLICATE", "RESEARCH_CLIP_INVALID", "STASH_GROUP_INVALID"].includes(item.code))) return { ok: false, document, diagnostics: before.diagnostics };
  if (!Number.isSafeInteger(expectedRevision) || expectedRevision !== (document.rowEditRevision ?? 0) || expectedRevision === Number.MAX_SAFE_INTEGER) return refused(document, "ROW_REVISION_STALE", "The row document changed before this edit, or its revision cannot advance.");
  if (command.kind === "save_stash_group" && command.expectedRevision !== expectedRevision) {
    return refused(document, "ROW_REVISION_STALE", "A staged group Save must use the exact revision at which its member editor opened.");
  }

  // Existing single-member edit routes cannot bypass the group's atomic Save boundary.
  const grouped = new Set((document.stashGroups ?? []).flatMap((group) => group.rowIds));
  if (command.kind === "edit_row" && grouped.has(command.rowId) ||
    isStageDirectionKind(command.kind) && grouped.has((command as StageDirectionEditCommandV2).blockId)) {
    return refused(document, "STASH_GROUP_ATOMIC_REQUIRED", "Edit grouped members with a single group Save, not an independent row command.");
  }
  if (command.kind === "trim_research_clip" && (grouped.has(command.clipRowId) ||
    document.stash?.some((bundle) => bundle.rows.some((row) =>
      grouped.has(row.id) && row.type === "narration" && row.attachedFootage?.clip.id === command.clipRowId)))) {
    return refused(document, "STASH_GROUP_ATOMIC_REQUIRED", "Trim a grouped row's footage through the staged group editor, not an independent row edit.");
  }

  if (isStageDirectionKind(command.kind)) {
    const stageCommand = command as unknown as StageDirectionEditCommandV2;
    const row = document.activeDraft.blocks.find((block): block is NarrationBlockV2 => block.id === stageCommand.blockId && block.type === "narration") ??
      document.stash?.flatMap((bundle) => bundle.rows).find((item): item is NarrationBlockV2 => item.id === stageCommand.blockId && item.type === "narration");
    const edited = applyStageDirectionEditV2(document, row?.version ?? -1, stageCommand);
    if (!edited.ok) return { ok: false, document, diagnostics: edited.diagnostics };
    const serialized = serializedDocument({ ...edited.document, rowEditRevision: expectedRevision + 1 });
    return serialized
      ? { ok: true, document: serialized, diagnostics: [] }
      : refused(document, "ROW_CONTENT_INVALID", "The edited row must be losslessly representable as valid saved JSON.");
  }

  if (command.kind === "edit_row") {
    const bundle = document.stash?.find((candidate) => candidate.rows.some((row) => row.id === command.rowId));
    if (bundle) {
      try {
        return applyStashRowEditV2(document, expectedRevision, { bundleId: bundle.id, rowId: command.rowId, row: command.row });
      } catch {
        return refused(document, "ROW_CONTENT_INVALID", "The edited row must be losslessly representable as valid saved JSON.");
      }
    }
  }

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
  } else if (command.kind === "move_rows" || command.kind === "stash_rows" || command.kind === "stash_group_rows") {
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
      const reattached = new Set<string>();
      for (const row of rows) {
        if (row.type !== "visual_only" || !row.stashOrigin?.originalAttachedNoteRowId) continue;
        const origin = row.stashOrigin;
        const ownerId = origin.originalAttachedNoteRowId;
        if (!ownerId) continue;
        const owner = compactNote(working, ownerId);
        const ownerEntry = outline.find((entry) => entry.rowId === ownerId);
        const ownerAnchors = ownerEntry ? outlineSiblingAnchors(outline, ownerId) : null;
        const ownerUnmoved = !!owner && !!ownerEntry && ownerEntry.sectionId === origin.sectionId &&
          ownerEntry.parentRowId === origin.originalAttachedNoteParentRowId &&
          (origin.originalAttachedNoteAfterSiblingRowId === null ||
            origin.originalAttachedNoteAfterSiblingRowId === ownerAnchors?.afterSiblingRowId) &&
          (origin.originalAttachedNoteBeforeSiblingRowId === null ||
            origin.originalAttachedNoteBeforeSiblingRowId === ownerAnchors?.beforeSiblingRowId);
        if (origin.returnEligible && ownerUnmoved && !owner.attachedFootage) {
          if (hasExternalRowReferences(working, row.id) || items.some((item) => supportingRows(item, blocks).has(row.id))) {
            return refused(document, "ROW_REFERENCE_REVIEW_REQUIRED", "The independently placed footage has references that cannot be transferred into an attachment.");
          }
          const attached = structuredClone(row);
          delete attached.stashOrigin;
          owner.attachedFootage = { clip: attached };
          reattached.add(row.id);
          continue;
        }
        if (!ownerUnmoved && (!owner || !!ownerEntry)) {
          // Original owner was deleted, moved, or the occurrence was edited.
          // Reuse anchored return ordering to the ORIGINAL location; ambiguity
          // refuses the transaction rather than choosing another note.
          if (!owner || ownerEntry) {
            origin.parentRowId = origin.originalAttachedNoteParentRowId ?? null;
            origin.afterSiblingRowId = origin.originalAttachedNoteAfterSiblingRowId ?? null;
            origin.beforeSiblingRowId = origin.originalAttachedNoteBeforeSiblingRowId ?? null;
          }
        }
      }
      const ordinaryReturns = rows.filter((row) => !reattached.has(row.id));
      if (command.kind === "stash_group_rows" && reattached.size) {
        return refused(document, "STASH_GROUP_ATTACHMENT_REVIEW_REQUIRED", "A group must retain each selected row; returning separate footage to its old note would change membership.");
      }
      const returnedOutline = planStashReturn(working, ordinaryReturns, outline);
      if (!returnedOutline) return refused(document, "STASH_ORIGIN_DESTINATION_INVALID", "The original Stash section or sibling slot is missing, ambiguous, or no longer accepts this branch.");
      for (const row of rows) {
        if (row.type === "narration" && !parkAttachedFootageForSortingV2(row)) {
          return refused(document, "STASH_ATTACHMENT_VISUAL_CONFLICT", "The attached footage's active visual slot changed; review it before returning the note.");
        }
      }
      blocks.splice(from, rows.length);
      working.activeDraft.supportingItems = working.activeDraft.supportingItems.filter((item) => !items.includes(item));
      for (const row of rows) delete row.stashOrigin;
      if (ordinaryReturns.length) (working.stash ??= []).push({ id: command.bundleId, rows: [ordinaryReturns[0]!, ...ordinaryReturns.slice(1)], supportingItems: items, originalGap });
      working.stashOutline = returnedOutline;
      if (command.kind === "stash_group_rows") {
        const problem = formStashGroup(working, command.rowIds, command.groupId, command.createdBy, command.createdAt, {
          sectionId: command.sectionId, parentRowId: command.parentRowId, afterRowId: command.afterRowId,
        });
        if (problem) return refused(document, "STASH_GROUP_INVALID", problem);
      }
    }
  } else if (command.kind === "group_stash_rows") {
    const problem = formStashGroup(working, command.rowIds, command.groupId, command.createdBy, command.createdAt);
    if (problem) return refused(document, "STASH_GROUP_INVALID", problem);
  } else if (command.kind === "move_stash_group") {
    const group = groupById(working, command.groupId);
    if (!group) return refused(document, "STASH_GROUP_NOT_FOUND", "Choose an existing saved group.");
    if (audioSpanTouchesRows(working, new Set(group.rowIds))) return refused(document, "AUDIO_REVIEW_REQUIRED", "Review group audio intent before moving these saved rows.");
    const problem = relocateGroupRows(working, group.rowIds, command.sectionId, command.parentRowId, command.afterRowId);
    if (problem) return refused(document, "STASH_GROUP_DESTINATION_INVALID", problem);
    moved = group.rowIds.map((rowId) => stashRowById(working, rowId)!);
  } else if (command.kind === "ungroup_stash_group") {
    if (!groupById(working, command.groupId)) return refused(document, "STASH_GROUP_NOT_FOUND", "Choose an existing saved group.");
    removeGroup(working, command.groupId);
  } else if (command.kind === "delete_stash_group") {
    const group = groupById(working, command.groupId);
    if (!group) return refused(document, "STASH_GROUP_NOT_FOUND", "Choose an existing saved group.");
    removeGroup(working, command.groupId);
    const deleted = deleteRows(working, group.rowIds);
    if ("code" in deleted) return { ok: false, document, diagnostics: [deleted] };
    moved = deleted.rows;
  } else if (command.kind === "place_stash_group") {
    const group = groupById(working, command.groupId);
    if (!group) return refused(document, "STASH_GROUP_NOT_FOUND", "Choose an existing saved group.");
    const index = gapIndex(blocks, command.destination);
    if (index === null) return refused(document, "ROW_DESTINATION_INVALID", "Choose an exact current Draft gap.");
    const outline = ensureStashOutline(working);
    for (const rowId of group.rowIds) {
      const entry = outline.find((item) => item.rowId === rowId)!;
      const anchors = outlineSiblingAnchors(outline, rowId)!;
      const row = stashRowById(working, rowId)!;
      row.stashOrigin = { kind: "row", parentRowId: entry.parentRowId, sectionId: entry.sectionId,
        ...anchors, returnEligible: true };
      if (row.type === "narration" && !presentAttachedFootageForSortingV2(row)) {
        return refused(document, "STASH_ATTACHMENT_VISUAL_CONFLICT", "The attached footage cannot be represented safely in the active row's visual slot.");
      }
    }
    const order = stashRowsInVisibleOrder(working).map((row) => row.id);
    removeGroup(working, command.groupId);
    const taken = takeStashRows(working, new Set(group.rowIds), order);
    if ("code" in taken) return { ok: false, document, diagnostics: [taken] };
    moved = taken.rows;
    blocks.splice(index, 0, ...moved);
  } else if (command.kind === "save_stash_group") {
    const problem = saveStashGroup(working, command);
    if (problem) return { ok: false, document, diagnostics: [problem] };
    // All surviving and removed members participate in relationship/audio review.
    moved = document.stash?.flatMap((bundle) => bundle.rows).filter((row) => command.expectedRowIds.includes(row.id)) ?? [];
  } else if (command.kind === "edit_row") {
    const index = blocks.findIndex((block) => block.type !== "section" && block.id === command.rowId);
    if (index < 0) return refused(document, "ROW_NOT_FOUND", "Choose an existing Draft or Stash row to edit.");
    const current = blocks[index] as Row;
    let replacement: Row;
    try { replacement = structuredClone(command.row); }
    catch { return refused(document, "ROW_CONTENT_INVALID", "The edited row must be losslessly representable as valid saved JSON."); }
    if (replacement.id !== current.id || replacement.type !== current.type) return refused(document, "ROW_IDENTITY_INVALID", "An authored row edit must preserve the row's existing ID and type.");
    if (current.type === "narration" && replacement.type === "narration" && current.plainDirection !== replacement.plainDirection) {
      return refused(document, "ROW_CONTENT_INVALID", "Use explicit Make spoken or Make stage direction to change plain-note speech intent.");
    }
    if (current.type === "narration" && replacement.type === "narration" &&
      !sameAuthoringJsonV2(current.attachedFootage, replacement.attachedFootage)) {
      return refused(document, "STASH_ATTACHMENT_REVIEW_REQUIRED", "Use explicit footage commands to change an attached clip.");
    }
    const currentContent = structuredClone(current);
    const replacementContent = structuredClone(replacement);
    delete currentContent.stashOrigin;
    delete replacementContent.stashOrigin;
    if (sameAuthoringJsonV2(currentContent, replacementContent)) return refused(document, "ROW_EDIT_NO_CHANGE", "The row already has this content.");
    blocks[index] = preserveStashOriginAfterEditV2(current, replacement);
  } else if (command.kind === "create_row") {
    const index = gapIndex(blocks, command.destination);
    if (index === null) return refused(document, "ROW_DESTINATION_INVALID", "Choose an exact current section gap.");
    const row = structuredClone(command.row);
    if ([...blocks, ...(working.stash ?? []).flatMap((bundle) => bundle.rows)].some((existing) => existing.id === row.id)) return refused(document, "ROW_ID_DUPLICATE", "A new row needs an unused row ID.");
    blocks.splice(index, 0, row);
    moved = [row];
  } else if (command.kind === "delete_rows") {
    const deleted = deleteRows(working, command.rowIds);
    if ("code" in deleted) return { ok: false, document, diagnostics: [deleted] };
    moved = deleted.rows;
  } else if (attachmentKind(command.kind)) {
    // Exact payload discrimination is checked above; all graph changes happen only on the clone.
    const attachmentCommand = command as StashFootageCommandV2;
    if (attachmentCommand.kind === "trim_research_clip") {
      const stashClip = stashRowById(working, attachmentCommand.clipRowId);
      const activeClip = blocks.find((row) => row.id === attachmentCommand.clipRowId);
      const owner = [...blocks, ...(working.stash ?? []).flatMap((bundle) => bundle.rows)].find(
        (row): row is NarrationBlockV2 => row.type === "narration" &&
          row.attachedFootage?.clip.id === attachmentCommand.clipRowId,
      );
      const clip = owner?.attachedFootage?.clip ?? (stashClip?.type === "visual_only" ? stashClip :
        activeClip?.type === "visual_only" ? activeClip : undefined);
      if (!clip) return refused(document, "RESEARCH_CLIP_NOT_FOUND", "Choose an existing Research clip occurrence, including an attached one.");
      let trimmed: VisualOnlyBlockV2;
      try {
        trimmed = trimResearchClipOccurrenceV2(clip, attachmentCommand.edge === "clear_out"
          ? { edge: "clear_out" } : { edge: attachmentCommand.edge, frame: attachmentCommand.frame });
      } catch {
        return refused(document, "RESEARCH_CLIP_TRIM_INVALID", "The selected source frame must remain inside the original evidenced logged interval, with a positive duration.");
      }
      if (sameAuthoringJsonV2(trimmed.visualOnlyTiming, clip.visualOnlyTiming)) {
        return refused(document, "ROW_EDIT_NO_CHANGE", "The clip already uses this source range.");
      }
      trimmed.version = clip.version + 1;
      if (!Number.isSafeInteger(trimmed.version)) return refused(document, "RESEARCH_CLIP_TRIM_INVALID", "The clip revision cannot advance.");
      if (owner) {
        owner.attachedFootage = { clip: trimmed };
        // Active note visuals are derived from this one authoritative clip.
        // Verify the old mirror before refreshing it, never replace an unrelated edit.
        if (blocks.includes(owner)) {
          const slot = owner.primaryVisualSequence?.slots[0];
          if (!slot || owner.primaryVisualSequence?.slots.length !== 1 || slot.kind !== "content" ||
            !sameAuthoringJsonV2(slot.payload, mirroredAttachmentPayload(owner.id, clip, slot.id))) {
            return refused(document, "STASH_ATTACHMENT_VISUAL_CONFLICT", "The active note's visual no longer matches its owned footage.");
          }
          slot.payload = mirroredAttachmentPayload(owner.id, trimmed, slot.id);
        }
      } else {
        const target = stashClip?.type === "visual_only" ? stashClip : activeClip as VisualOnlyBlockV2;
        const replacement = { ...trimmed, ...(target.stashOrigin ? { stashOrigin: structuredClone(target.stashOrigin) } : {}) };
        markStashOriginEditedV2(replacement);
        if (stashClip) {
          const bundle = working.stash!.find((b) => b.rows.some((row) => row.id === target.id))!;
          bundle.rows.splice(bundle.rows.findIndex((row) => row.id === target.id), 1, replacement);
        } else blocks.splice(blocks.findIndex((row) => row.id === target.id), 1, replacement);
      }
    } else if (attachmentCommand.kind === "place_attached_footage") {
      const index = gapIndex(blocks, attachmentCommand.destination);
      if (index === null) return refused(document, "ROW_DESTINATION_INVALID", "Choose an exact current Draft gap for the footage.");
      const entries = ensureStashOutline(working);
      const note = compactNote(working, attachmentCommand.noteRowId);
      const entry = entries.find((item) => item.rowId === attachmentCommand.noteRowId);
      const anchors = outlineSiblingAnchors(entries, attachmentCommand.noteRowId);
      if (!note || !entry || !anchors || !note.attachedFootage) {
        return refused(document, "STASH_ATTACHMENT_SLOT_EMPTY", "Choose an attached clip on an existing compact Stash note.");
      }
      if (hasExternalRowReferences(working, note.attachedFootage.clip.id)) {
        return refused(document, "ROW_REFERENCE_REVIEW_REQUIRED", "The attached footage has unsupported external references.");
      }
      const clip = structuredClone(note.attachedFootage.clip);
      delete note.attachedFootage;
      clip.stashOrigin = {
        kind: "clip", parentRowId: note.id, sectionId: entry.sectionId,
        afterSiblingRowId: null, beforeSiblingRowId: null, returnEligible: true,
        originalAttachedNoteRowId: note.id,
        originalAttachedNoteParentRowId: entry.parentRowId,
        originalAttachedNoteAfterSiblingRowId: anchors.afterSiblingRowId,
        originalAttachedNoteBeforeSiblingRowId: anchors.beforeSiblingRowId,
      };
      blocks.splice(index, 0, clip);
      moved = [clip];
    } else {
    const entries = ensureStashOutline(working);
    const note = compactNote(working, attachmentCommand.noteRowId);
    const noteEntry = entries.find((entry) => entry.rowId === attachmentCommand.noteRowId);
    if (!note || !noteEntry) return refused(document, "STASH_ATTACHMENT_NOTE_INVALID", "Choose an existing compact Stash note.");
    if (attachmentCommand.kind === "attach_stash_footage" || attachmentCommand.kind === "replace_stash_footage") {
      if (attachmentCommand.kind === "attach_stash_footage" && note.attachedFootage ||
        attachmentCommand.kind === "replace_stash_footage" && !note.attachedFootage) {
        return refused(document, "STASH_ATTACHMENT_SLOT_OCCUPIED", "Attach only to an empty slot; replace only an occupied slot.");
      }
      const clipEntry = entries.find((entry) => entry.rowId === attachmentCommand.clipRowId);
      if (!clipEntry || clipEntry.kind !== "clip") return refused(document, "STASH_ATTACHMENT_CLIP_INVALID", "Choose an independent saved footage clip, not a note or an already owned clip.");
      const clip = removeOrdinaryStashClip(working, attachmentCommand.clipRowId);
      if (!clip) return refused(document, "STASH_ATTACHMENT_CLIP_REFERENCED", "This clip has external references or a saved supporting item; it cannot be transferred implicitly.");
      if (attachmentCommand.kind === "replace_stash_footage") {
        const at = working.stashOutline!.findIndex((entry) => entry.rowId === note.id) + 1;
        if (!releaseAttachedClip(working, note.id, attachmentCommand.releasedBundleId, note.id, noteEntry.sectionId, at)) {
          return refused(document, "STASH_ATTACHMENT_BUNDLE_INVALID", "Choose an unused bundle ID for the released footage.");
        }
      }
      note.attachedFootage = { clip };
    } else if (attachmentCommand.kind === "detach_stash_footage") {
      if (!note.attachedFootage) return refused(document, "STASH_ATTACHMENT_SLOT_EMPTY", "This note has no footage to detach.");
      const at = entries.findIndex((entry) => entry.rowId === note.id) + 1;
      if (!releaseAttachedClip(working, note.id, attachmentCommand.bundleId, note.id, noteEntry.sectionId, at)) {
        return refused(document, "STASH_ATTACHMENT_BUNDLE_INVALID", "Choose an unused bundle ID for the detached footage.");
      }
    } else {
      const noteSlot = note.primaryVisualSequence?.slots.length === 1 ? note.primaryVisualSequence.slots[0] : undefined;
      if (!note.attachedFootage || note.plainDirection !== true || note.text.trim() !== "" ||
        note.tokens.length !== 0 || note.overlayEvents.length !== 0 ||
        note.annotations?.length || note.performanceBeats?.length || note.notes.length !== 0 ||
        noteSlot?.kind !== "content" || noteSlot.relation.kind !== "base" ||
        noteSlot.boundaryBefore.kind !== "row_start" || noteSlot.payload.kind !== "on_camera" ||
        noteSlot.payload.presenterChoiceId !== null) {
        return refused(document, "STASH_BLANK_NOTE_REQUIRED", "Only a truly blank plain-direction note with attached footage can be cleaned up.");
      }
      const noteBundle = working.stash!.find((bundle) => bundle.rows.some((row) => row.id === note.id));
      if (!noteBundle || noteBundle.supportingItems.length > 0 || hasExternalRowReferences(working, note.id)) {
        return refused(document, "ROW_REFERENCE_REVIEW_REQUIRED", "The blank note has referenced content; review it before removal.");
      }
      const at = entries.findIndex((entry) => entry.rowId === note.id);
      if (!releaseAttachedClip(working, note.id, attachmentCommand.clipBundleId, noteEntry.parentRowId, noteEntry.sectionId, at + 1)) {
        return refused(document, "STASH_ATTACHMENT_BUNDLE_INVALID", "Choose an unused bundle ID for the promoted footage.");
      }
      // Promote only direct children; deeper descendants retain their own note parents.
      for (const entry of working.stashOutline!) if (entry.parentRowId === note.id) entry.parentRowId = noteEntry.parentRowId;
      working.stashOutline = working.stashOutline!.filter((entry) => entry.rowId !== note.id);
      noteBundle.rows = noteBundle.rows.filter((row) => row.id !== note.id) as typeof noteBundle.rows;
      working.stash = working.stash!.filter((bundle) => bundle.rows.length > 0);
      for (const section of working.stashSections ?? []) section.rowIds = section.rowIds.filter((id) => id !== note.id);
    }
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
    const byId = outlineMap(ensureStashOutline(working));
    moved = moved.filter((row) => byId.get(row.id)?.sectionId !== command.sectionId);
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
      if (!note) return refused(document, "STASH_NOTE_CONTENT_INVALID", "A note must supply valid raw text and frozen tokens; literal brackets need no special syntax.");
      row = note;
      kind = "note";
    } else {
      const payload = (command.row as unknown as { payload?: unknown }).payload;
      const unresolvedResearch = command.row.type === "visual_only" &&
        command.row.payload?.pictureKind === "unresolved_visual" &&
        command.row.payload?.source?.kind === "unresolved_visual" &&
        command.row.researchClip !== undefined && command.row.frameBinding === undefined &&
        command.row.visualOnlyTiming?.selectedSourceRange === undefined;
      if (command.row.type !== "visual_only" || !payload || typeof payload !== "object" || Array.isArray(payload) ||
        (payload as { pictureKind?: unknown }).pictureKind !== "clip" && !unresolvedResearch) {
        return refused(document, "STASH_CLIP_CONTENT_INVALID", "A compact Stash clip needs a saved footage row or an unresolved Research-logged occurrence.");
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
    for (const group of working.stashGroups ?? []) {
      if (!audioSpanTouchesRows(working, new Set(group.rowIds))) continue;
      const location = (entries: StashOutlineEntryV2[]) => entries.flatMap((entry, index) =>
        group.rowIds.includes(entry.rowId) ? [{ rowId: entry.rowId, index, parentRowId: entry.parentRowId, sectionId: entry.sectionId }] : []);
      if (!sameAuthoringJsonV2(location(current), location(command.entries))) {
        return refused(document, "AUDIO_REVIEW_REQUIRED", "Review the grouped audio intent before changing this Stash outline location.");
      }
    }
    working.stashOutline = structuredClone(command.entries);
  } else if (command.kind === "place_stash_rows") {
    const index = gapIndex(blocks, command.destination);
    if (index === null) return refused(document, "ROW_DESTINATION_INVALID", "Choose an exact current section gap.");
    const entries = ensureStashOutline(working);
    const subtree = selectedOutlineSubtree(entries, command.rowIds);
    if (!subtree) return refused(document, "ROW_SELECTION_INVALID", "Select distinct Stash outline items without selecting a descendant twice; each selected item's descendants move with it.");
    const selected = new Set((command.includeDescendants === false ? subtree.filter((entry) => command.rowIds.includes(entry.rowId)) : subtree).map((entry) => entry.rowId));
    const origins = new Map<string, StashOriginV2>();
    for (const entry of subtree.filter((candidate) => selected.has(candidate.rowId))) {
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
    for (const entry of subtree.filter((candidate) => selected.has(candidate.rowId))) {
      const row = stashRowById(working, entry.rowId);
      if (row) {
        row.stashOrigin = origins.get(entry.rowId)!;
        if (row.type === "narration" && !presentAttachedFootageForSortingV2(row)) {
          return refused(document, "STASH_ATTACHMENT_VISUAL_CONFLICT", "The note needs an unambiguous primary visual slot and footage with an explicitly muted or quiet source-audio policy.");
        }
      }
    }
    if (command.includeDescendants === false) {
      // Keep ordinary children in Stash and promote only direct children of moved roots.
      for (const entry of entries) {
        if (entry.parentRowId !== null && selected.has(entry.parentRowId)) {
          entry.parentRowId = origins.get(entry.parentRowId)!.parentRowId;
        }
      }
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
  if (errors.length) return { ok: false, document, diagnostics: errors };
  if (command.kind === "edit_row" || command.kind === "create_row" || command.kind === "delete_rows" || command.kind === "save_stash_group") {
    const saved = serializedDocument(working);
    return saved
      ? { ok: true, document: saved, diagnostics: [] }
      : refused(document, "ROW_CONTENT_INVALID", "The row edit must be losslessly representable as valid saved JSON.");
  }
  return { ok: true, document: working, diagnostics: [] };
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

function serializedDocument(document: ScriptDocumentV2): ScriptDocumentV2 | null {
  try {
    return JSON.parse(serializeAuthoringDocumentV2(document)) as ScriptDocumentV2;
  } catch {
    return null;
  }
}

export function deserializeAuthoringDocumentV2(json: string): { ok: true; document: ScriptDocumentV2 } | { ok: false; diagnostics: AuthoringDiagnosticV2[] } {
  let document: unknown;
  try { document = JSON.parse(json); } catch { return { ok: false, diagnostics: [diagnostic("DOCUMENT_JSON_INVALID", "The saved document is not valid JSON.")] }; }
  const validation = validateScriptDocumentV2(document);
  const fatal = validation.diagnostics.filter((item) => ["SCHEMA_INVALID", "ENTITY_ID_DUPLICATE", "BLOCK_ID_DUPLICATE", "ROW_REFERENCE_INVALID", "PLAIN_DIRECTION_INTENT_INVALID", "FOOTAGE_OWNER_DUPLICATE", "RESEARCH_CLIP_INVALID"].includes(item.code));
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
