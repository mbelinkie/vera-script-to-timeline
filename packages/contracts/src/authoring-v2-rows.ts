import type { ScriptDocumentV2, RowGapV2, SupportingItemV2, StashOutlineEntryV2, StashOriginV2, NarrationBlockV2, NarratedVisualPayloadV2, VisualOnlyBlockV2 } from "./generated/contracts-v2.js";
import type { AuthoringDiagnosticV2 } from "./authoring-v2.js";
import { validateScriptDocumentV2 } from "./authoring-v2-validation.js";
import { applyStageDirectionEditV2, defaultDirectionNarrationRowV2, type StageDirectionEditCommandV2 } from "./authoring-v2-stage-direction-edits.js";
import { applyStashRowEditV2 } from "./authoring-v2-stash.js";
import { markStashOriginEditedV2, preserveStashOriginAfterEditV2 } from "./authoring-v2-stash-origin.js";
import { trimResearchClipOccurrenceV2 } from "./authoring-v2-research-snapshot.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";
import { chooseReturnSlotV2, freezeOriginalParentContextV2, freezeOriginalSiblingCandidatesV2 } from "./authoring-v2-stash-return-location.js";

type Block = ScriptDocumentV2["activeDraft"]["blocks"][number];
type Row = Exclude<Block, { type: "section" }>;
export type { RowGapV2 } from "./generated/contracts-v2.js";

/** Exact outline gap for a deliberate Stash drop (not an active-Draft RowGap). */
export type StashReturnDestinationV2 = RowGapV2 & { parentRowId: string | null };

export type RowEditCommandV2 =
  | { kind: "move_rows"; rowIds: string[]; destination: RowGapV2 }
  | { kind: "move_section"; sectionId: string; destination: { afterSectionId: string | null; beforeSectionId: string | null } }
  | { kind: "stash_rows"; rowIds: string[]; bundleId: string; destination?: StashReturnDestinationV2 }
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

function stashReturnDestinationPayload(value: unknown): value is StashReturnDestinationV2 {
  return plainObject(value) && exactKeys(value, ["sectionId", "parentRowId", "afterRowId", "beforeRowId"]) &&
    (value.parentRowId === null || typeof value.parentRowId === "string" && value.parentRowId.length > 0) &&
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

/**
 * Plan against a cloned outline. Selected rows are inserted as one transaction;
 * no live parent, unrelated outline peer, or media owner is moved to make room.
 */
function planStashReturn(
  document: ScriptDocumentV2, rows: Row[], entries: StashOutlineEntryV2[],
  destination?: StashReturnDestinationV2,
): StashOutlineEntryV2[] | null {
  const result = structuredClone(entries);
  const selected = new Map(rows.map((row) => [row.id, row]));
  const returnedKinds = new Map(rows.map((row) => [row.id,
    row.stashOrigin?.returnEligible && row.stashOrigin.kind !== "row" ? row.stashOrigin.kind : "row"] as const));
  // An edited note cannot turn into an ordinary full row while carrying an
  // embedded clip owner. Never copy or silently detach that owned occurrence.
  if (rows.some((row) => row.type === "narration" && row.attachedFootage && returnedKinds.get(row.id) === "row")) return null;
  const sectionIds = new Set((document.stashSections ?? []).map((section) => section.id));
  const original = new Map(rows.map((row) => [row.id, row.stashOrigin] as const));
  const placed = new Set<string>();
  const cursors = new Map<string, string>();

  if (destination) {
    if (!sectionExists(document, destination.sectionId)) return null;
    if (destination.parentRowId !== null && !result.some((entry) =>
      entry.rowId === destination.parentRowId && entry.kind === "note" && entry.sectionId === destination.sectionId)) return null;
    const peers = result.filter((entry) =>
      entry.parentRowId === destination.parentRowId && entry.sectionId === destination.sectionId);
    const after = peers.findIndex((entry) => entry.rowId === destination.afterRowId);
    const before = peers.findIndex((entry) => entry.rowId === destination.beforeRowId);
    // An explicit drop names the CURRENT adjacent gap, including its edges.
    if (destination.afterRowId === null ? before !== 0 && peers.length !== 0 :
      after < 0 || (destination.beforeRowId === null ? after !== peers.length - 1 : before !== after + 1)) return null;
    if (destination.beforeRowId !== null && before < 0) return null;
    if (destination.afterRowId === null && destination.beforeRowId === null && peers.length !== 0) return null;
  }

  // A row must wait until its selected ancestor is placed: no row may become
  // the child of a saved full row (only a genuine saved note owns children).
  const pending = [...rows];
  while (pending.length > 0) {
    const index = pending.findIndex((row) => {
      const parentId = original.get(row.id)?.parentRowId;
      return !parentId || !selected.has(parentId) || placed.has(parentId);
    });
    if (index < 0) return null; // cyclic/corrupt selected parent chain
    const row = pending.splice(index, 1)[0]!;
    const source = original.get(row.id);
    const sourceParentId = source?.parentRowId ?? null;
    const selectedParent = sourceParentId ? selected.get(sourceParentId) : undefined;
    const parentEntry = selectedParent ? result.find((entry) => entry.rowId === sourceParentId) : undefined;
    if (selectedParent && !parentEntry) return null;
    const nestedInSelectedNote = !!parentEntry && parentEntry.kind === "note";
    const promotedBySelectedRow = !!parentEntry && parentEntry.kind !== "note";
    const activeParent = sourceParentId && !selectedParent
      ? document.activeDraft.blocks.find((item): item is Row => item.type !== "section" && item.id === sourceParentId)
      : undefined;
    const storedParent = sourceParentId && !selectedParent
      ? result.find((entry) => entry.rowId === sourceParentId)
      : undefined;
    const ownerAnchors = storedParent ? outlineSiblingAnchors(result, storedParent.rowId) : null;
    const stableFormerAttachment = !destination && !!source?.originalAttachedNoteRowId &&
      storedParent?.kind === "note" && storedParent.rowId === source.originalAttachedNoteRowId &&
      storedParent.sectionId === source.sectionId &&
      storedParent.parentRowId === (source.originalAttachedNoteParentRowId ?? null) &&
      (source.originalAttachedNoteAfterSiblingRowId == null || source.originalAttachedNoteAfterSiblingRowId === ownerAnchors?.afterSiblingRowId) &&
      (source.originalAttachedNoteBeforeSiblingRowId == null || source.originalAttachedNoteBeforeSiblingRowId === ownerAnchors?.beforeSiblingRowId);
    const promotedByActiveParent = !!activeParent;
    let parentRowId: string | null = null;
    let sectionId: string | null = source?.sectionId ?? null;
    let parentChoice: { kind: "root" } | { kind: "note"; rowId: string } | { kind: "invalid" } = { kind: "root" };
    let historical = source;
    let promotedRootPreceding: string[] | undefined;
    let promotedRootFollowing: string[] | undefined;

    if (destination && !selectedParent) {
      parentRowId = destination.parentRowId;
      sectionId = destination.sectionId;
    } else if (nestedInSelectedNote) {
      parentRowId = parentEntry.rowId;
      sectionId = parentEntry.sectionId;
      parentChoice = { kind: "note", rowId: parentRowId };
      // The selected note was just returned in this same atomic transaction.
      // Its location is intentional even if its own old parent disappeared.
      historical = source && { ...source, sectionId, parentRowId,
        originalParentContext: {
          parentRowId: parentEntry.parentRowId, sectionId,
          precedingSiblingRowIds: [], followingSiblingRowIds: [],
        } };
    } else if (promotedBySelectedRow) {
      parentRowId = parentEntry.parentRowId;
      sectionId = parentEntry.sectionId;
      parentChoice = parentRowId === null ? { kind: "root" } : { kind: "note", rowId: parentRowId };
      historical = source && { ...source, sectionId,
        ...(parentRowId !== null ? { parentRowId, originalParentContext: {
          parentRowId: result.find((entry) => entry.rowId === parentRowId)?.parentRowId ?? null,
          sectionId, precedingSiblingRowIds: [], followingSiblingRowIds: [],
        } } : {}) };
      promotedRootPreceding = [parentEntry.rowId];
      promotedRootFollowing = [];
    } else if (storedParent) {
      parentRowId = storedParent.rowId;
      parentChoice = { kind: "note", rowId: parentRowId };
    } else if (promotedByActiveParent) {
      // A formerly nested child becomes a root while its note is still Draft.
      // Only historical *root* anchors or previously returned sibling roots
      // can give evidence; current unrelated neighbors cannot.
      const parentOrigin = activeParent.stashOrigin;
      parentRowId = null;
      if (parentOrigin && parentOrigin.sectionId === sectionId) {
        const siblingRoots = result.filter((entry) => entry.parentRowId === null && entry.sectionId === sectionId);
        const oldSiblings = (ids: readonly string[] | undefined) => (ids ?? []).filter((id) =>
          siblingRoots.some((entry) => entry.rowId === id));
        const siblingBefore = oldSiblings(source?.precedingSiblingRowIds ?? (source?.afterSiblingRowId ? [source.afterSiblingRowId] : []));
        const siblingAfter = oldSiblings(source?.followingSiblingRowIds ?? (source?.beforeSiblingRowId ? [source.beforeSiblingRowId] : []));
        // A formerly nested sibling returned separately outranks the original
        // parent's root neighbors; otherwise reversed Draft order wins.
        const hasReturnedSibling = siblingBefore.length > 0 || siblingAfter.length > 0;
        promotedRootPreceding = hasReturnedSibling ? siblingBefore :
          oldSiblings(parentOrigin.precedingSiblingRowIds ?? (parentOrigin.afterSiblingRowId ? [parentOrigin.afterSiblingRowId] : []));
        promotedRootFollowing = hasReturnedSibling ? siblingAfter :
          oldSiblings(parentOrigin.followingSiblingRowIds ?? (parentOrigin.beforeSiblingRowId ? [parentOrigin.beforeSiblingRowId] : []));
      } else parentChoice = { kind: "invalid" };
    } else if (sourceParentId !== null) {
      parentChoice = { kind: "invalid" };
    }

    let insertAt: number;
    if (destination) {
      if (!selectedParent) {
        const cursor = cursors.get("explicit-root");
        insertAt = cursor ? outlineSubtreeEnd(result, cursor) + 1 : destination.beforeRowId !== null
          ? result.findIndex((entry) => entry.rowId === destination.beforeRowId)
          : destination.afterRowId !== null
            ? outlineSubtreeEnd(result, destination.afterRowId) + 1
            : outlineInsertionIndex(document, result, parentRowId, sectionId, null) ?? -1;
        if (destination.afterRowId === null && destination.beforeRowId === null) {
          // The exact empty target may be a named section or an empty note.
          insertAt = cursor ? outlineSubtreeEnd(result, cursor) + 1 :
            parentRowId === null ? (result.findIndex((entry) => entry.parentRowId === null && entry.sectionId === sectionId) >= 0
              ? -1 : outlineInsertionIndex(document, result, null, sectionId, null) ?? -1)
              : result.findIndex((entry) => entry.rowId === parentRowId) + 1;
        }
        cursors.set("explicit-root", row.id);
      } else if (nestedInSelectedNote) {
        const cursor = cursors.get(`explicit-child:${parentRowId}`);
        insertAt = cursor ? outlineSubtreeEnd(result, cursor) + 1 : result.findIndex((entry) => entry.rowId === parentRowId) + 1;
        cursors.set(`explicit-child:${parentRowId}`, row.id);
      } else {
        const cursor = cursors.get(`explicit-promoted:${parentEntry!.rowId}`);
        insertAt = cursor ? outlineSubtreeEnd(result, cursor) + 1 : outlineSubtreeEnd(result, parentEntry!.rowId) + 1;
        cursors.set(`explicit-promoted:${parentEntry!.rowId}`, row.id);
      }
    } else if (stableFormerAttachment) {
      // #367: a separately placed clip returns as an ordinary saved child if
      // the original note remains in its proven slot but is now occupied.
      // Never create a second embedded owner or overwrite the occupied slot.
      parentRowId = storedParent.rowId;
      sectionId = storedParent.sectionId;
      insertAt = outlineSubtreeEnd(result, parentRowId) + 1;
    } else {
      const slot = chooseReturnSlotV2({
        origin: historical, entries: result, sectionIds, parent: parentChoice,
        ...(promotedByActiveParent || promotedBySelectedRow && parentRowId === null
          ? { promotedRootPreceding: promotedRootPreceding ?? [], promotedRootFollowing: promotedRootFollowing ?? [] } : {}),
      });
      parentRowId = slot.parentRowId;
      sectionId = slot.sectionId;
      if (slot.kind === "after") {
        const key = `after:${slot.siblingRowId}`;
        const anchor = cursors.get(key) ?? slot.siblingRowId;
        insertAt = outlineSubtreeEnd(result, anchor) + 1;
        cursors.set(key, row.id);
      } else if (slot.kind === "before") {
        insertAt = result.findIndex((entry) => entry.rowId === slot.siblingRowId);
      } else {
        const key = `${slot.kind}:${parentRowId ?? ""}:${sectionId ?? ""}`;
        const cursor = cursors.get(key);
        insertAt = cursor ? outlineSubtreeEnd(result, cursor) + 1 :
          slot.kind === "unsectioned_top" ? 0 :
          slot.kind === "first_child" ? result.findIndex((entry) => entry.rowId === parentRowId) + 1 :
          (() => { const first = result.findIndex((entry) => entry.parentRowId === null && entry.sectionId === sectionId);
            return first >= 0 ? first : outlineInsertionIndex(document, result, null, sectionId, null) ?? -1; })();
        cursors.set(key, row.id);
      }
    }
    if (insertAt < 0 || insertAt > result.length) return null;
    result.splice(insertAt, 0, { rowId: row.id, kind: returnedKinds.get(row.id)!, parentRowId, sectionId });
    placed.add(row.id);
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

  // stashOrigin holds *historical location evidence*, not a live relationship.
  // Deleting an old anchor/parent is safe: the return resolver can fall back.
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

/** One immutable local transaction. A refusal returns the original input object. */
export function applyRowEditV2(document: ScriptDocumentV2, expectedRevision: number, command: RowEditCommandV2): RowEditResultV2 {
  if (!plainObject(command)) return refused(document, "ROW_COMMAND_INVALID", "Provide a row edit command.");
  try {
    if (command.kind === "stash_rows" && (!isJsonValue(command) ||
      !exactKeys(command, Object.hasOwn(command, "destination") ? ["kind", "rowIds", "bundleId", "destination"] : ["kind", "rowIds", "bundleId"]) ||
      !rowIdsPayload(command.rowIds) || typeof command.bundleId !== "string" || command.bundleId.length === 0 ||
      Object.hasOwn(command, "destination") && !stashReturnDestinationPayload(command.destination))) {
      return refused(document, "ROW_COMMAND_INVALID", "Provide a valid Stash return and an exact optional outline drop destination.");
    }
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
  if (before.diagnostics.some((item) => ["SCHEMA_INVALID", "ENTITY_ID_DUPLICATE", "BLOCK_ID_DUPLICATE", "ROW_REFERENCE_INVALID", "PLAIN_DIRECTION_INTENT_INVALID", "FOOTAGE_OWNER_DUPLICATE", "RESEARCH_CLIP_INVALID"].includes(item.code))) return { ok: false, document, diagnostics: before.diagnostics };
  if (!Number.isSafeInteger(expectedRevision) || expectedRevision !== (document.rowEditRevision ?? 0) || expectedRevision === Number.MAX_SAFE_INTEGER) return refused(document, "ROW_REVISION_STALE", "The row document changed before this edit, or its revision cannot advance.");

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
        // A deliberate Stash outline drop always wins over auto-reattachment,
        // even when the historical note's footage slot is still empty.
        if (!command.destination && origin.returnEligible && ownerUnmoved && !owner.attachedFootage) {
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
      const returnedOutline = planStashReturn(working, ordinaryReturns, outline, command.destination);
      if (!returnedOutline) return refused(document, "STASH_ORIGIN_DESTINATION_INVALID", "The requested Stash outline destination, return hierarchy, or attachment ownership cannot be preserved.");
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
    }
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
        ...(freezeOriginalSiblingCandidatesV2(entries, entry.rowId) ?? {}),
        ...(freezeOriginalParentContextV2(entries, entry.rowId) ? {
          originalParentContext: freezeOriginalParentContextV2(entries, entry.rowId)!,
        } : {}),
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
  if (command.kind === "edit_row" || command.kind === "create_row" || command.kind === "delete_rows") {
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
